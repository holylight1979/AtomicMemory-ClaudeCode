#!/usr/bin/env python3
"""health-weekly.py — 每週記憶系統健檢（Windows 工作排程器驅動，無 CC session 依賴）。

「靜默死 27 天」類問題的最後防線：管線可以壞，但壞了必須在一週內浮出。

檢查面（全部唯讀，不自動修）：
  1. memory-audit.py --json --global-only   → issues / duplicates（review 級）
  2. atom-health-check.py --report --json   → broken_refs（紅）/ stale / shadow（黃）
  3. sync-atom-index.py --check             → 索引一致性（紅）
  4. skill-index.py --check                 → skill 計數 drift（紅）
  5. vector 服務 GET :3849/health           → 離線屬 INFO（服務隨 session 啟動）；
     LanceDB 目錄缺失才是紅
  6'. 官方健檢摘要：claude -p "/skill-doctor"、"/context"（skill 數與成本前五、固定成本）；
     /doctor prompt-audit 太慢只留手動提示；CLI 不在或失敗 → 黃燈
  6. 管線鮮度（死因偵測核心）：近 FRESH_DAYS 天內有 session（state-*.json mtime）
     但 _promotion_audit.jsonl / episodic/ 無新增 → 紅（管線靜默停擺）；
     無 session → INFO（停擺屬預期）

產出：
  - workflow/health-reports/health-YYYYMMDD.md（保留最近 KEEP_REPORTS 份）
  - workflow/health-last-run.json {at, red, yellow, report} ——
    SessionStart 死人開關讀此檔：缺檔或 at 逾 STALE_RUN_DAYS 天 → 排程器本身死了，
    session 內浮出警示（fail-open 必告知）。

手動執行：python tools/health-weekly.py [--json]
排程註冊：見本檔尾 REGISTER 說明（schtasks 每週一 09:00 pythonw 靜默跑）。
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# pythonw（Task Scheduler 靜默跑）下 sys.stdout/stderr 為 None——直接
# reconfigure 會 AttributeError 秒死。None → devnull，有的才轉 UTF-8。
for _name in ("stdout", "stderr"):
    _s = getattr(sys, _name)
    if _s is None:
        setattr(sys, _name, open(os.devnull, "w", encoding="utf-8", newline="\n"))
    else:
        _s.reconfigure(encoding="utf-8")

CODE_DIR = Path(__file__).resolve().parent.parent   # 程式碼根（本檔所在的樹）：tools、hooks、子行程 cwd
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
from lib.atom_index_json import load_personal_rows  # noqa: E402
from lib.sensitive_gate import is_secret_path, secret_value_found  # noqa: E402
from lib.project_root import claude_data_dir  # noqa: E402
CLAUDE_DIR = claude_data_dir()   # 使用者資料根（WG_CLAUDE_DIR 或 ~/.claude）：workflow、memory、Logs
TOOLS = CODE_DIR / "tools"
WORKFLOW = CLAUDE_DIR / "workflow"
MEMORY = CLAUDE_DIR / "memory"
REPORT_DIR = WORKFLOW / "health-reports"
LAST_RUN = WORKFLOW / "health-last-run.json"
RECALL_MISS_LOG = CLAUDE_DIR / "Logs" / "recall-miss.jsonl"

FRESH_DAYS = 14        # 管線鮮度門檻：有 session 卻 N 天無管線輸出 = 停擺
KEEP_REPORTS = 12      # 報告保留份數（~3 個月）
RECALL_MISS_DAYS = 14  # 失念窗：近 N 天
RECALL_MISS_MIN = 3    # 同一 atom 失念 ≥ N 次 → 黃燈
VECTOR_PORT = 3849
PY = sys.executable


def _run_json(args: list[str], timeout: int = 300) -> dict | None:
    """跑子工具收 JSON；失敗回 None（呼叫端記紅——工具自身壞掉也是健檢發現）。"""
    try:
        r = subprocess.run(
            [PY, *args], capture_output=True, text=True, encoding="utf-8",
            timeout=timeout, cwd=str(CODE_DIR),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return json.loads(r.stdout)
    except Exception:
        return None


def _load_config() -> dict:
    try:
        return json.loads((WORKFLOW / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _provenance_anti_rot(now: datetime, days: int) -> tuple[int, int, str]:
    """回 (補成功數, 候選數, 錯誤訊息)。候選＝Source 為 session:… 且日期距今 ≥days、無 Quote、該 session transcript 仍在。"""
    import importlib.util
    import re
    tool = TOOLS / "atom-provenance-backfill.py"
    if not tool.exists():
        return 0, 0, "tools/atom-provenance-backfill.py 不存在"
    spec = importlib.util.spec_from_file_location("atom_provenance_backfill", tool)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["atom_provenance_backfill"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    from lib.provenance import find_transcript, parse_source
    src_re = re.compile(r"^- Source:\s*(\S.*)$", re.M)
    quote_re = re.compile(r"^- Quote:\s*\S", re.M)
    cands: list[str] = []
    for _layer, path in mod.collect_atoms("all"):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        if quote_re.search(text):
            continue
        m = src_re.search(text)
        if not m:
            continue
        ps = parse_source(m.group(1).strip())
        if ps.get("kind") != "session" or not ps.get("date"):
            continue
        try:
            age = (now.date() - datetime.strptime(ps["date"], "%Y-%m-%d").date()).days
        except ValueError:
            continue
        if age < days or not find_transcript(ps["sid8"]):
            continue
        cands.append(str(path).replace("\\", "/"))
    if not cands:
        return 0, 0, ""
    rep = mod.backfill(apply=True, only=cands)
    fixed = sum(1 for r in rep["results"] if r.get("written"))
    return fixed, len(cands), ""


def _secret_leaks() -> list[str] | None:
    """會進版控的記憶卡與索引裡，提到 secret 卡名或含密碼／token 真實值的檔（相對路徑）；None＝查不了。
    只回路徑：報告與開場提示都不寫出卡名。還沒提交的新卡也算，提交了就留在歷史裡。"""
    names = [a["name"] for a in load_personal_rows(MEMORY)
             if isinstance(a, dict) and a.get("name") and is_secret_path(a.get("path", ""))]
    try:
        r = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "memory", "_AIDocs/_atoms"],
                           capture_output=True, timeout=60, cwd=str(CLAUDE_DIR),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    hits = []
    for rel in r.stdout.decode("utf-8", errors="replace").split("\0"):
        if not rel.endswith((".md", ".json")):
            continue
        try:
            text = (CLAUDE_DIR / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if secret_value_found(text) or any(name in text for name in names):
            hits.append(rel)
    return hits


def _run_check(args: list[str], timeout: int = 120) -> tuple[bool, str]:
    """跑 --check 型工具；回 (通過, 摘要輸出)。"""
    try:
        r = subprocess.run(
            [PY, "-X", "utf8", *args], capture_output=True, text=True, encoding="utf-8",
            timeout=timeout, cwd=str(CODE_DIR),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return r.returncode == 0, _check_summary(((r.stdout or "") + (r.stderr or "")).strip())
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _check_summary(out: str) -> str:
    """輸出是 JSON（sync-atom-index --check）就摘成「哪類 幾筆（前兩個名字）」；最後一行只會是 `}`，報告看不出哪張卡。其餘取最後一行。"""
    try:
        d = json.loads(out)
    except ValueError:
        lines = out.splitlines()
        return lines[-1] if lines else ""
    if not isinstance(d, dict):
        return out[-300:]
    parts = []
    for kind, items in d.items():
        if not isinstance(items, list) or not items:
            continue
        names = [str(i.get("atom") or i.get("path") or i) if isinstance(i, dict) else str(i) for i in items[:2]]
        parts.append(f"{kind} {len(items)} 筆（{'、'.join(names)}）")
    return "；".join(parts) or out[-300:]


def _newest_mtime(pattern_dir: Path, glob: str) -> datetime | None:
    try:
        files = list(pattern_dir.glob(glob))
        if not files:
            return None
        return datetime.fromtimestamp(max(f.stat().st_mtime for f in files))
    except OSError:
        return None


def _episodic_status(fresh_cut: datetime) -> tuple[datetime | None, dict]:
    """episodic 產物最新 mtime（根層＋各專案層）＋近窗事件計數（Logs/guard-episodic.jsonl）。"""
    from collections import Counter
    dirs = [MEMORY / "episodic"]
    try:
        hooks_dir = str(CODE_DIR / "hooks")
        if hooks_dir not in sys.path:
            sys.path.insert(0, hooks_dir)
        from wg_core import discover_all_project_memory_dirs  # noqa: WPS433
        dirs += [mem_dir / "episodic" for _slug, mem_dir in discover_all_project_memory_dirs()]
    except Exception:
        pass
    mtimes = [m for m in (_newest_mtime(d, "episodic-*.md") for d in dirs) if m is not None]
    newest = max(mtimes) if mtimes else None

    # 以 session 為單位計（同場 pre_compact/session_end 可能各記一次、失敗重試會累加）：
    # 一場只算一種結果，優先序 generated > failed > skipped。
    per_session: Dict[str, str] = {}
    reasons: Counter = Counter()
    rank = {"generated": 3, "failed": 2, "skipped": 1}
    log_path = CLAUDE_DIR / "Logs" / "guard-episodic.jsonl"
    try:
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = json.loads(line)
                at = datetime.fromisoformat(rec["at"]).replace(tzinfo=None)
            except (ValueError, KeyError, TypeError):
                continue
            if at < fresh_cut:
                continue
            ev = rec.get("event", "")
            if ev not in rank:
                continue
            sid = str(rec.get("session_id") or f"?{rec.get('at')}")
            if rank[ev] > rank.get(per_session.get(sid, ""), 0):
                per_session[sid] = ev
            if ev == "skipped":
                reasons[str(rec.get("reason", "")).split("(")[0]] += 1
    except OSError:
        pass
    counts = Counter({"generated": 0, "skipped": 0, "failed": 0})
    for ev in per_session.values():
        counts[ev] += 1
    return newest, {"counts": counts, "reasons": reasons}


def _promotion_last_ts() -> datetime | None:
    """_promotion_audit.jsonl 最後一筆 ts（append-only，讀尾 4KB 即可）。"""
    p = MEMORY / "_promotion_audit.jsonl"
    try:
        with open(p, "rb") as f:
            f.seek(max(0, p.stat().st_size - 4096))
            lines = f.read().decode("utf-8", errors="replace").strip().splitlines()
        for line in reversed(lines):
            try:
                return datetime.fromisoformat(json.loads(line)["ts"])
            except (ValueError, KeyError):
                continue
    except OSError:
        pass
    return None


def _recall_miss_counts(days: int) -> dict[str, int]:
    """Logs/recall-miss.jsonl 近 N 天 atom → 失念次數（缺檔/壞行計為零）。"""
    counts: dict[str, int] = {}
    cut = datetime.now().astimezone() - timedelta(days=days)
    try:
        for line in RECALL_MISS_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                at = datetime.fromisoformat(str(rec.get("at", "")))
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
            if at.tzinfo is None:
                at = at.astimezone()
            if at >= cut and rec.get("atom"):
                counts[str(rec["atom"])] = counts.get(str(rec["atom"]), 0) + 1
    except OSError:
        pass
    return counts


def _hooks_on_path() -> None:
    hooks_dir = str(CODE_DIR / "hooks")
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)


def _run_selftest(st: dict, cwd: Path) -> dict:
    """跑一筆 tool_selftests {name, cmd, expected(PASS|FAIL|DONE), sentinel?, runtime_gate, timeout_s}。
    runtime_gate 非 0 → skipped（環境未就緒屬預期，不算紅）。判定：取 stdout 的**最後一個非空行**當哨兵行
    （規矩：哨兵是尾行；先 PASS 後 traceback／雜訊就不是尾行），有給 sentinel 名就連名字一起比；
    stderr 非空視為可疑：expected PASS／DONE 時紅。exit 非零：expected PASS／DONE 一律紅，expected FAIL 可綠。
    subprocess 的 stdout／stderr 是分開收的（沒有時間順序），所以用「stdout 尾行＋stderr 非空」這個近似。"""
    _hooks_on_path()
    from wg_verify_ledger import parse_sentinels  # noqa: WPS433
    name = str(st.get("name") or st.get("cmd") or "?")
    expected = str(st.get("expected") or "PASS").upper()
    timeout = float(st.get("timeout_s") or 60)
    res = {"name": name, "expected": expected, "got": [], "ok": False, "status": "ran", "ms": 0, "detail": ""}
    gate = str(st.get("runtime_gate") or "").strip()
    try:
        if gate:
            g = subprocess.run(shlex.split(gate.replace("\\", "/")), capture_output=True, text=True,
                               timeout=timeout, cwd=str(cwd),
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if g.returncode != 0:
                res.update(status="skipped", detail=f"runtime_gate exit {g.returncode}")
                return res
        t0 = time.monotonic()
        r = subprocess.run(shlex.split(str(st.get("cmd") or "").replace("\\", "/")), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=str(cwd),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        res["ms"] = int((time.monotonic() - t0) * 1000)
        out_lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
        last_line = out_lines[-1] if out_lines else ""
        sent = parse_sentinels(last_line)
        res["got"] = [f"{s['name']} {s['verdict']}" for s in parse_sentinels((r.stdout or "") + "\n" + (r.stderr or ""))]
        res["exit_code"] = r.returncode
        res["last_line"] = last_line[:160]
        want_name = str(st.get("sentinel") or "").strip()
        last = sent[-1] if sent else None
        ok = bool(last) and last["verdict"] == expected and (not want_name or last["name"] == want_name)
        stderr_text = (r.stderr or "").strip()
        if expected in ("PASS", "DONE"):
            if r.returncode != 0:
                ok = False
                err_tail = stderr_text.splitlines()[-1][:120] if stderr_text else ""
                res["detail"] = f"exit {r.returncode}（expected {expected} 不接受非零 exit）{'：' + err_tail if err_tail else ''}"
            elif stderr_text:
                ok = False
                res["detail"] = "stderr 有輸出（可疑）：" + stderr_text.splitlines()[-1][:120]
        if not ok and not res["detail"]:
            res["detail"] = (f"尾行「{last_line[:100]}」不是 {expected} 哨兵" if out_lines else "（無輸出）")
            if stderr_text and not out_lines:
                res["detail"] = stderr_text.splitlines()[-1][:160]
        res["ok"] = ok
    except subprocess.TimeoutExpired:
        res.update(status="timeout", detail=f"逾時 {timeout}s")
    except (OSError, ValueError) as e:
        res.update(status="error", detail=f"{type(e).__name__}: {e}"[:160])
    return res


def _selftests_block(selftests: list, cwd: Path) -> tuple[list[str], list[str], list[dict]]:
    """H7：登記的工具自測逐筆跑；哨兵不符 expected（含壞依賴沒輸出、壞接線印別的名、壞哨兵小寫）→ 紅。
    回 (red, info, results)。"""
    red: list[str] = []
    info: list[str] = []
    results: list[dict] = []
    for st in selftests or []:
        if not isinstance(st, dict) or not st.get("cmd"):
            continue
        r = _run_selftest(st, cwd)
        results.append(r)
        if r["status"] == "skipped":
            info.append(f"selftest {r['name']}：跳過（{r['detail']}）")
        elif r["ok"]:
            info.append(f"selftest {r['name']}：{r['expected']} 如預期（{r['ms']} ms）")
        else:
            got = "、".join(r["got"]) if r["got"] else "沒有任何哨兵"
            red.append(f"selftest {r['name']} 預期 {r['expected']}，實得 {got}（{r['status']}；{r['detail']}）"
                       "；工具自身壞掉或哨兵格式不合 `<NAME>_CHECK PASS|FAIL`")
    return red, info, results


def _depends_block(hc: dict, coverage_min: float) -> tuple[list[str], list[str]]:
    """H7：Depends 壞滅緣（路徑消失）黃、依賴比卡新黃、覆蓋率 info（低於 depends_coverage_min 黃）。回 (yellow, info)。"""
    yellow: list[str] = []
    info: list[str] = []
    n_stale = len(hc.get("stale_deps") or [])
    if n_stale:
        yellow.append(f"stale_deps {n_stale} 筆：Depends 指向的路徑已不存在（atom-health-check.py --deps-check）")
    n_foreign = len(hc.get("foreign_deps") or [])
    if n_foreign:
        info.append(f"他機路徑的 Depends {n_foreign} 筆（作者機的絕對路徑，本機不可驗、不算壞滅緣；atom-health-check.py --deps-check）")
    mt = hc.get("stale_mtime_deps") or []
    if mt:
        names = ", ".join(f"{d.get('atom')}←{Path(str(d.get('dep', ''))).name}" for d in mt[:5])
        yellow.append(f"依賴比卡新 {len(mt)} 筆（Depends 檔改於卡最近驗證日之後，卡可能過期）：{names}")
    cov = hc.get("depends_coverage") or {}
    if cov:
        ratio = float(cov.get("ratio") or 0.0)
        info.append(f"Depends 覆蓋率 {cov.get('with_depends', 0)}/{cov.get('total', 0)} = {ratio:.1%}")
        if ratio < float(coverage_min or 0):
            yellow.append(f"Depends 覆蓋率 {ratio:.1%} 低於 depends_coverage_min {float(coverage_min):.1%}")
    return yellow, info


# config verify_ledger.sentinel_regex 兩條內建 pytest 規則的現行值（版控庫 workflow/config.json 的那兩筆）。install 只做頂層合併，
# 使用者保留的舊 config 不會跟著更新；hook 端（wg_verify_ledger._builtin_pytest_rule）只自動補 pytest_summary 旗標，regex 不補：
# 停在最早版 regex 的機器把「1 passed, 1 error」判成 PASS。這裡只浮訊號，修法在 Install-forAI §3 升級段。
_CURRENT_PYTEST_REGEX = (r"^(?:=+ )?(?P<verdict>\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|warnings?|deselected|rerun)"
                         r"(?:, \d+ [a-z]+)*) in \d")
_CURRENT_PYTEST_VERDICT_MAP = {
    "PYTEST": {"failed": "FAIL", "error": "FAIL", "passed": "PASS", "xpassed": "PASS"},
    "PYTEST_MEASURE": {"failed": "FAIL", "error": "FAIL", "passed": "DONE", "xpassed": "DONE"},
}


def _pytest_regex_block(cfg: dict) -> list[str]:
    """config 內建 PYTEST／PYTEST_MEASURE 規則（verify_ledger.sentinel_regex）不是現行版 → 黃（WARN）。
    regex、verdict_map、pytest_summary 三樣任一與現行值不同就報；兩條缺一條也報。自訂名稱的規則不管。
    verdict_map 的值只比大小寫無關的結論（hook 端 compile_sentinel_rules 一樣 upper()，`pass` 與 `PASS` 執行期同義，不算舊版）。"""
    vl = cfg.get("verify_ledger") if isinstance(cfg.get("verify_ledger"), dict) else {}
    rules = vl.get("sentinel_regex") if isinstance(vl.get("sentinel_regex"), list) else []
    yellow: list[str] = []
    seen: set[str] = set()
    for r in rules:
        if not isinstance(r, dict):
            continue
        name = str(r.get("name") or "").strip()
        want = _CURRENT_PYTEST_VERDICT_MAP.get(name)
        if not want:
            continue
        seen.add(name)
        vm = r.get("verdict_map") if isinstance(r.get("verdict_map"), dict) else {}
        wrong = [label for label, bad in (
            ("regex", r.get("regex") != _CURRENT_PYTEST_REGEX),
            ("verdict_map", {str(k): str(v).upper() for k, v in vm.items()} != want),
            ("pytest_summary", r.get("pytest_summary") is not True),
        ) if bad]
        if wrong:
            yellow.append(f"config 內建 {name} regex 非現行版（{'、'.join(wrong)} 與版控庫 workflow/config.json 不同；"
                          f"舊版把「1 passed, 1 error」判成 {want['passed']}）→ 手動對齊 verify_ledger.sentinel_regex（Install-forAI §3 升級段）")
    for name in _CURRENT_PYTEST_VERDICT_MAP:
        if name not in seen:
            yellow.append(f"config 內建 {name} 規則缺失（verify_ledger.sentinel_regex 沒有這條）→ 補成版控庫 workflow/config.json 的現行值")
    return yellow


def _reconcile_overflow_block(days: int) -> list[str]:
    """對帳閘預算用完放行（guard-reconcile_overflow.jsonl）近 N 天有事件 → 紅（放行要可見）。"""
    p = CLAUDE_DIR / "Logs" / "guard-reconcile_overflow.jsonl"
    cut = datetime.now().astimezone() - timedelta(days=days)
    n = 0
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                at = datetime.fromisoformat(str(json.loads(line).get("at", "")))
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
            if at.tzinfo is None:
                at = at.astimezone()
            if at >= cut:
                n += 1
    except OSError:
        return []
    return [f"對帳閘預算用完放行 {n} 次（近 {days} 天；Logs/guard-reconcile_overflow.jsonl）；收尾宣稱連續對不上收據"] if n else []


def _user_release_block(days: int) -> list[str]:
    """閘擋滿後使用者放行（Logs/guard-*.jsonl 的 event=user_release）近 N 天有事件 → 紅（放行要可見，按閘分計）。"""
    cut = datetime.now().astimezone() - timedelta(days=days)
    per: dict[str, int] = {}
    for p in sorted((CLAUDE_DIR / "Logs").glob("guard-*.jsonl")):
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            if '"user_release"' not in line:
                continue
            try:
                rec = json.loads(line)
                at = datetime.fromisoformat(str(rec.get("at", "")))
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
            if rec.get("event") != "user_release":
                continue
            if at.tzinfo is None:
                at = at.astimezone()
            if at >= cut:
                gate = p.stem[len("guard-"):]
                per[gate] = per.get(gate, 0) + 1
    if not per:
        return []
    detail = "、".join(f"{g} {n} 次" for g, n in sorted(per.items()))
    return [f"閘擋滿後由使用者放行（近 {days} 天；{detail}；Logs/guard-<閘>.jsonl event=user_release）；閘連續擋滿仍未解"]


def _instructions_loaded_block(days: int = 7) -> list[str]:
    """Logs/instructions-loaded.jsonl（InstructionsLoaded hook 的帳）近 N 天 → 一行：各載入原因次數、壓縮後有沒有重載 CLAUDE.md 與 MEMORY.md。
    沒有帳（hook 還沒掛或這週沒開 session）回空；壓縮過的 session 有缺重載另給一行。"""
    p = CLAUDE_DIR / "Logs" / "instructions-loaded.jsonl"
    if not p.exists():
        return []
    cut = datetime.now().astimezone() - timedelta(days=days)
    reasons: dict[str, int] = {}
    compacted: dict[str, set[str]] = {}   # session → 壓縮後重載過的檔名
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            rec = json.loads(line)
            at = datetime.fromisoformat(str(rec.get("at", "")))
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
        if at.tzinfo is None:
            at = at.astimezone()
        if at < cut:
            continue
        why = str(rec.get("load_reason", "?"))
        reasons[why] = reasons.get(why, 0) + 1
        if why == "compact":
            compacted.setdefault(str(rec.get("session_id", "")), set()).add(Path(str(rec.get("file_path", ""))).name)
    if not reasons:
        return []
    out = [f"規則／索引載入（近 {days} 天；Logs/instructions-loaded.jsonl）：" + "、".join(f"{k} {v}" for k, v in sorted(reasons.items()))]
    if compacted:
        n = len(compacted)
        out.append(f"壓縮後重載：{n} 場有壓縮，其中重載 CLAUDE.md {sum('CLAUDE.md' in f for f in compacted.values())} 場、"
                   f"@memory/MEMORY.md {sum('MEMORY.md' in f for f in compacted.values())} 場")
    return out


def _find_claude() -> str | None:
    """claude CLI 路徑：PATH → 原生安裝位置 ~/.local/bin（排程器的 PATH 常沒有它）。"""
    import shutil
    found = shutil.which("claude")
    if found:
        return found
    p = Path.home() / ".local" / "bin" / ("claude.exe" if sys.platform == "win32" else "claude")
    return str(p) if p.exists() else None


def _claude_p(cli: str, prompt: str, timeout: int = 60) -> str:
    """無頭跑一個斜線命令回 result 文字；失敗丟例外（呼叫端轉成黃燈）。"""
    r = subprocess.run(
        [cli, "-p", prompt, "--model", "haiku", "--output-format", "json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        stdin=subprocess.DEVNULL, cwd=str(CODE_DIR),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    d = json.loads(r.stdout)
    if d.get("is_error"):
        raise RuntimeError(str(d.get("result"))[:100])
    return d.get("result") or ""


def _skill_doctor_summary(text: str) -> list[str]:
    """/skill-doctor 表格 → skill 數、context 成本前五、從沒叫過的提示行。"""
    import re
    rows = []
    for m in re.finditer(r"^  (\S+)\s{2,}(.+?)\s{2,}(~\d+|<\s*\d+|-)\s{2,}", text, re.M):
        cost = int(re.sub(r"\D", "", m.group(3)) or 0) if m.group(3) != "-" else 0
        rows.append((m.group(1), cost))
    if not rows:
        return ["/skill-doctor 輸出解析不到 skill 表（格式變了？）"]
    top = sorted(rows, key=lambda x: -x[1])[:5]
    out = [f"skill {len(rows)} 個；context 成本前五：" + "、".join(f"{n}(~{c})" for n, c in top)]
    out += [m.group(0).strip()[:120] for m in re.finditer(r"^\d+ skills?.*never invoked.*$", text, re.M)]
    return out


def _context_summary(text: str) -> list[str]:
    """/context 類別表 → 固定成本（不含 deferred／Messages／Free／Autocompact）。"""
    import re
    fixed = ("System prompt", "System tools", "MCP tools", "MCP server instructions", "Memory files", "Skills")
    cells = dict(re.findall(r"^\| ([^|]+?) \| ([^|]+?) \|", text, re.M))
    parts = [f"{k} {cells[k]}" for k in fixed if k in cells]
    total = re.search(r"\*\*Tokens:\*\* (\S+)", text)
    if not parts:
        return ["/context 輸出解析不到類別表（格式變了？）"]
    return ["/context 固定成本：" + "、".join(parts) + (f"；開場合計 {total.group(1)}" if total else "")]


def _official_block(cli: str | None, run=_claude_p) -> tuple[list[str], list[str]]:
    """官方健檢摘要 → (official 行, 黃燈)。/skill-doctor 與 /context 無頭可跑（不呼叫模型、各約 20 秒，並行跑）；
    /doctor prompt-audit 會呼叫模型審查，無頭實測 170 秒未完成，只留手動提示。CLI 不在或失敗 → 黃燈。"""
    manual = ("要手動跑 /doctor prompt-audit（審 CLAUDE.md／rules／skills 有沒有過時或矛盾）："
              "會呼叫模型審查，無頭實測超過 170 秒，不放進週健檢；結果寫 memory/_staging/prompt-audit-<日期>.md，由人挑著改")
    if not cli:
        return [manual], ["官方健檢沒跑：找不到 claude CLI（PATH 與 ~/.local/bin 都沒有）"]
    from concurrent.futures import ThreadPoolExecutor
    jobs = (("/skill-doctor", _skill_doctor_summary), ("/context", _context_summary))
    lines: list[str] = []
    yellow: list[str] = []

    def one(job):
        cmd, summarize = job
        try:
            return summarize(run(cli, cmd))
        except Exception as e:
            yellow.append(f"官方健檢 {cmd} 沒跑成：{type(e).__name__}: {str(e)[:80]}")
            return [f"{cmd} 沒跑成（見需留意）"]

    with ThreadPoolExecutor(len(jobs)) as ex:
        for part in ex.map(one, jobs):
            lines.extend(part)
    lines.append(manual)
    return lines, yellow


def collect() -> dict:
    now = datetime.now()
    red: list[str] = []      # 需處理
    yellow: list[str] = []   # 需留意
    info: list[str] = []     # 純資訊
    selftests: list[dict] = []

    # 1. memory-audit
    ma = _run_json([str(TOOLS / "memory-audit.py"), "--json", "--global-only"])
    if ma is None:
        red.append("memory-audit.py 執行失敗（工具自身壞掉）")
    else:
        n_iss, n_dup = len(ma.get("issues") or []), len(ma.get("duplicates") or [])
        if n_iss or n_dup:
            yellow.append(f"memory-audit：issues {n_iss} / duplicates {n_dup}（跑 /memory health 檢視）")

    # 2. atom-health-check
    hc = _run_json([str(TOOLS / "atom-health-check.py"), "--report", "--json"])
    if hc is None:
        red.append("atom-health-check.py 執行失敗（工具自身壞掉）")
    else:
        br = len(hc.get("broken_refs") or [])
        if br:
            red.append(f"broken_refs {br} 筆（/memory health 走 L2 自癒）")
        for k in ("stale_atoms", "shadow_atoms", "missing_reverse_refs"):
            n = len(hc.get(k) or [])
            if n:
                yellow.append(f"{k} {n} 筆")
        # 2b. Depends：壞滅緣（路徑消失）、依賴比卡新、覆蓋率
        dy, di = _depends_block(hc, float(_load_config().get("depends_coverage_min", 0) or 0))
        yellow.extend(dy)
        info.extend(di)

    # 2c. 工具自測（config tool_selftests[]）：壞依賴／壞接線／壞哨兵都要在一週內浮出
    sr, si, selftests = _selftests_block(_load_config().get("tool_selftests") or [], CODE_DIR)
    red.extend(sr)
    info.extend(si)
    # 2d. 對帳閘預算用完放行（舊 overflow 紀錄）＋擋滿後使用者放行
    red.extend(_reconcile_overflow_block(FRESH_DAYS))
    red.extend(_user_release_block(FRESH_DAYS))
    info.extend(_instructions_loaded_block())
    # 2d'. config 內建 PYTEST／PYTEST_MEASURE regex 停在舊版（只更新 hooks、沒對 config 的機器）
    yellow.extend(_pytest_regex_block(_load_config()))

    # 3/4. 索引一致性
    for name, args in (
        ("atom index", [str(TOOLS / "sync-atom-index.py"), "--check"]),
        ("skill index", [str(TOOLS / "skill-index.py"), "--check"]),
    ):
        ok, msg = _run_check(args)
        if not ok:
            red.append(f"{name} drift：{msg}")
    leaks = _secret_leaks()
    if leaks is None:
        yellow.append("個人敏感資訊外流檢查沒跑成（git ls-files 失敗）")
    elif leaks:
        red.append(f"進版控的卡或索引提到 secret 卡名、或含密碼／token 真實值 {len(leaks)} 個檔，會隨 repo 外流：{'、'.join(leaks[:5])}"
                   "（搬進 personal/<user>/secret/，或改寫內容；連結寫在 secret 卡那邊）")
    # 換行殘留（repo 全部 LF；有 CRLF/mixed 就黃燈，修法：python tools/normalize-eol.py --root --include-dirty）
    ok, msg = _run_check([str(TOOLS / "normalize-eol.py"), "--root", "--check"])
    if not ok:
        yellow.append(f"換行殘留（非 LF）：{msg[:300]}")
    # 專案層索引（全部登記專案，從 ~/.claude 一鍵掃；黃燈：不必逐專案開 session 整理，
    # 修法同一支：sync-atom-index.py --all-projects --fix-scope-from-path）
    ok, msg = _run_check([str(TOOLS / "sync-atom-index.py"), "--all-projects", "--check"], timeout=300)
    if not ok:
        yellow.append(f"專案層 atom index drift：{msg[:300]}")

    # 5. vector
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{VECTOR_PORT}/health", timeout=3
        ) as resp:
            info.append(f"vector 服務在線（HTTP {resp.status}）")
    except Exception:
        info.append("vector 服務離線（隨 session 啟動，離線非異常）")
    if not (MEMORY / "_vectordb").exists():
        red.append("memory/_vectordb 目錄不存在（向量庫遺失）")

    # 5b. 注入效果報表（token 稅 / 死重 / 使用證據——效果面，非結構面）
    er = _run_json([str(TOOLS / "memory-effect-report.py"), "--json"])
    if er is None:
        red.append("memory-effect-report.py 執行失敗（工具自身壞掉）")
    else:
        n_tax = len(er.get("exposure_tax") or [])
        n_dead = len(er.get("dead_candidates") or [])
        n_useful = len(er.get("top_useful") or [])
        if n_tax:
            names = ", ".join(r["name"] for r in er["exposure_tax"][:5])
            yellow.append(f"高曝光零使用（token 稅）{n_tax} 筆：{names}"
                          f"（跑 memory-effect-report.py 看 trigger 收斂建議）")
        if n_useful == 0:
            yellow.append("30 天內無任何 atom 效用證據——效用閉環（α/β）或 rescue 管線疑似停擺")
        info.append(f"注入效果：top 有用 {n_useful} / token 稅 {n_tax} / 零曝光候選 {n_dead}")

    # 5c. 失念（recall-miss）：近 14 天同一 atom 反覆「該想起而未想起」→ 黃燈
    rm = _recall_miss_counts(RECALL_MISS_DAYS)
    flagged = {a: c for a, c in rm.items() if c >= RECALL_MISS_MIN}
    if flagged:
        tops = ", ".join(
            f"{a}×{c}" for a, c in
            sorted(flagged.items(), key=lambda x: (-x[1], x[0]))[:5]
        )
        yellow.append(
            f"失念 recall-miss {len(flagged)} atom：{tops}"
            f"（近 {RECALL_MISS_DAYS} 天 ≥{RECALL_MISS_MIN} 次；"
            f"檢視 trigger 是否該補詞，詳 memory-effect-report.py D 節）"
        )

    # 6. 管線鮮度（死人偵測核心）
    fresh_cut = now - timedelta(days=FRESH_DAYS)
    last_session = _newest_mtime(WORKFLOW, "state-*.json")
    sessions_active = last_session is not None and last_session > fresh_cut
    checks = {
        "promotion audit（heartbeat / 晉升事件）": _promotion_last_ts(),
    }
    for label, ts in checks.items():
        if ts is None or ts < fresh_cut:
            age = "無資料" if ts is None else f"最後 {ts:%Y-%m-%d}"
            if sessions_active:
                red.append(f"{label} 停擺（{age}，但近 {FRESH_DAYS} 天有 session）——疑管線靜默失效")
            else:
                info.append(f"{label} {age}；近 {FRESH_DAYS} 天無 session，屬預期")

    # 6b. episodic：產物看根層＋各專案層；沒產物時用事件 log 分辨「正常跳過／失敗／沒被呼叫」。
    #     以前只掃 memory/episodic 且一律判停擺——09-18 的產出其實在專案層，唯讀 session 本來就跳過。
    ep_newest, ep_events = _episodic_status(fresh_cut)
    ep_counts = ep_events["counts"]
    ep_summary = (f"近 {FRESH_DAYS} 天（按 session）generated {ep_counts['generated']} / "
                  f"skipped {ep_counts['skipped']} / failed {ep_counts['failed']}")
    # 失敗告警獨立判斷：別的專案有近期產物不代表這場沒失敗
    if ep_counts["failed"] > 0:
        red.append(f"episodic 生成失敗 {ep_counts['failed']} 場（Logs/guard-episodic.jsonl）；{ep_summary}")
    if ep_newest is not None and ep_newest > fresh_cut:
        info.append(f"episodic 生成 最後 {ep_newest:%Y-%m-%d}（含專案層）；{ep_summary}")
    elif not sessions_active:
        info.append(f"episodic 生成 無新產物；近 {FRESH_DAYS} 天無 session，屬預期")
    elif ep_counts["failed"] > 0:
        pass  # 已在上面獨立報紅
    elif ep_counts["skipped"] > 0 and ep_counts["generated"] == 0:
        reasons = ", ".join(f"{k}×{v}" for k, v in ep_events["reasons"].most_common(3))
        info.append(f"episodic 近 {FRESH_DAYS} 天無產物：全部為正常跳過（{reasons}）——非故障")
    elif sum(ep_counts.values()) == 0:
        yellow.append(
            f"episodic 近 {FRESH_DAYS} 天無產物也無事件紀錄（含專案層）——"
            "事件 log 自 2026-09-21 起才有；下週仍空＝生成端未被呼叫，需查 session_end/pre_compact"
        )
    else:
        red.append(f"episodic 有 generated 事件但找不到近期產物——寫檔或路徑異常；{ep_summary}")

    # 7. 來源防腐：Source 指到 session、transcript 還在、距今 ≥ anti_rot_days、尚無 Quote → 搶在 transcript 清掉前補原句
    try:
        prov_cfg = (_load_config().get("provenance") or {})
        if prov_cfg.get("enabled", True):
            n_fixed, n_cand, err = _provenance_anti_rot(now, int(prov_cfg.get("anti_rot_days", 25)))
            if err:
                yellow.append(f"來源防腐執行失敗：{err[:200]}")
            elif n_cand:
                info.append(f"來源防腐：{n_cand} 顆快到期的 session 來源補原句，成功 {n_fixed}")
    except Exception as e:
        yellow.append(f"來源防腐例外：{type(e).__name__}: {e}")

    # 8. 官方健檢摘要（放最後：claude -p 會起一場 session，不能干擾上面的管線鮮度判斷）
    official, off_yellow = _official_block(_find_claude())
    yellow.extend(off_yellow)

    return {"at": now.isoformat(timespec="seconds"), "red": red,
            "yellow": yellow, "info": info, "official": official, "selftests": selftests,
            "last_session": last_session.isoformat(timespec="seconds") if last_session else None}


def write_report(result: dict) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    day = result["at"][:10].replace("-", "")
    path = REPORT_DIR / f"health-{day}.md"
    lines = [f"# 週健檢報告 {result['at']}", ""]
    for title, key, mark in (("需處理", "red", "🔴"), ("需留意", "yellow", "🟡"),
                             ("資訊", "info", "·")):
        items = result[key]
        lines.append(f"## {title}（{len(items)}）")
        lines.extend(f"- {mark} {x}" for x in items)
        if not items:
            lines.append("- ✓ 無")
        lines.append("")
    if result.get("official"):
        lines.append(f"## 官方健檢（{len(result['official'])}）")
        lines.extend(f"- {x}" for x in result["official"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    # 輪替：保留最近 KEEP_REPORTS 份
    reports = sorted(REPORT_DIR.glob("health-*.md"))
    for old in reports[:-KEEP_REPORTS]:
        old.unlink(missing_ok=True)
    return path


def main() -> int:
    result = collect()
    report = write_report(result)
    LAST_RUN.write_text(json.dumps({
        "at": result["at"], "red": len(result["red"]),
        "yellow": len(result["yellow"]),
        "selftests_failed": sum(1 for s in result.get("selftests") or [] if s.get("status") != "skipped" and not s.get("ok")),
        "report": str(report),
    }, ensure_ascii=False), encoding="utf-8", newline="\n")
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print(f"[health-weekly] 紅 {len(result['red'])} / 黃 {len(result['yellow'])}"
              f" / 資訊 {len(result['info'])} → {report}")
    return 1 if result["red"] else 0


# REGISTER（一次性，已由安裝流程執行；重灌時照抄）：
#   schtasks /Create /TN "Claude-Memory-WeeklyHealth" /SC WEEKLY /D MON /ST 09:00
#     /TR "%USERPROFILE%/AppData/Local/Python/bin/pythonw.exe
#          %USERPROFILE%/.claude/tools/health-weekly.py"
# 錯過排程（關機）→ 下次開機由 Task Scheduler 設定補跑；SessionStart 死人開關兜底。
if __name__ == "__main__":
    sys.exit(main())
