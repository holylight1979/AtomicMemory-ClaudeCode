"""acceptance.py — 驗收裁判（acceptance_review）的案卷材料與稽核落盤。

一個檔看完三件事（刻意不拆檔，避免跨檔跳轉）：

1. **任務↔規格檔綁定**（`resolve_binding`）——硬性契約：
   只有「本 session 寫的、唯一一份 status=open 的規格檔」算 `bound`，
   才准發審計。多份 open / 只有他 session 的規格 / 完全沒有 → 一律
   不發 codex，直接記 uncertain。**綁不到絕不用「最新一份」猜案卷**
   （INV-CASE-BINDING-OR-UNCERTAIN）。

2. **案卷 diff 採樣**（`collect_diff_digest`）——`--stat` 全給（檔案清單
   完整），逐檔 unified diff 頭尾採樣，超預算的檔案列成「未採樣清單」，
   untracked 新檔取檔頭。**任何截斷附 in-band 標記**，讓裁判知道自己
   看的是節錄而非「作者沒寫」（INV-EVIDENCE-PIPE-HONESTY）。

3. **稽核落盤**（`append_audit`）——影子期唯一的數據來源，
   `workflow/acceptance-audit.jsonl`，含 `human_label` 供事後標註精確率。

裁判永不授權副作用；本模組純讀取 + append-only 落盤。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SERVICE_DIR = Path(__file__).resolve().parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

CLAUDE_DIR = Path.home() / ".claude"
WORKFLOW_DIR = CLAUDE_DIR / "workflow"
SIDECAR_DIR = WORKFLOW_DIR / "acceptance-spec"
AUDIT_JSONL = WORKFLOW_DIR / "acceptance-audit.jsonl"
AUDIT_JSONL_MAX_BYTES = 2 * 1024 * 1024

_TZ = timezone(timedelta(hours=8))

# 案卷材料預算（Q3：回測第一輪實證後加碼——預算太瘦時裁判大量回
# uncertain「核心實作未採樣」，加碼直接換判定信心；總量對應 config
# acceptance_review.max_prompt_chars）
SPEC_HEAD, SPEC_TAIL = 2400, 600
GOAL_HEAD, GOAL_TAIL = 1200, 400
DIFF_BUDGET_CHARS = 9000          # Q4：unified diff 逐檔採樣總預算
DIFF_PER_FILE_HEAD = 2000
DIFF_PER_FILE_TAIL = 600
# stat 是「檔案不在清單＝沒做」反證推理的骨幹，寧大勿截
DIFF_STAT_MAX_CHARS = 6000
UNTRACKED_MAX_FILES = 3           # 新檔取檔頭的檔數上限
UNTRACKED_HEAD_CHARS = 800
EVIDENCE_MAX_ITEMS = 8
EVIDENCE_MAX_CHARS = 1500

_SPEC_GLOB = "acceptance-*.md"
_FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")
_GIT_TIMEOUT = 20


def _now_iso() -> str:
    return datetime.now(_TZ).isoformat(timespec="seconds")


def _log(msg: str) -> None:
    try:
        sys.stderr.write(f"[acceptance] {msg}\n")
    except OSError:
        pass


# ─── 1. 任務↔規格檔綁定（Q10） ───────────────────────────────────────────────

# binding 值域：
#   bound              本 session 唯一 open 規格 → 唯一准發審計的狀態
#   ambiguous_multiple 本 session 有 ≥2 份 open 規格 → 案卷會綁錯，必 uncertain
#   other_session      只有他 session 的 open 規格（跨 session 長任務，Q9）→ 必 uncertain
#   none               沒有任何 open 規格 → 本任務不在分級線上，不審
BINDING_BOUND = "bound"
BINDING_AMBIGUOUS = "ambiguous_multiple"
BINDING_OTHER_SESSION = "other_session"
BINDING_NONE = "none"

_UNCERTAIN_REASON = {
    BINDING_AMBIGUOUS: (
        "本 session 同時有多份 status=open 的驗收規格檔，無法唯一對應到這次收尾的任務；"
        "依綁定契約不得猜「最新一份」，故回 uncertain。請把已完成的規格檔 status 改 done 後再收尾。"
    ),
    BINDING_OTHER_SESSION: (
        "找到 status=open 的驗收規格檔，但其 frontmatter session_id 屬其他 session"
        "（跨 session 續作或陳舊規格），無法確認就是本次任務的驗收標準，故回 uncertain。"
    ),
    BINDING_NONE: "本任務沒有 status=open 的驗收規格檔，無案卷可審。",
}


def parse_frontmatter(text: str) -> Dict[str, str]:
    """極簡 frontmatter 解析（`---` 包夾的 key: value，最多掃 30 行）。

    刻意不引 yaml：規格檔格式由 acceptance_spec.py 的模板固定，值皆為純量。
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: Dict[str, str] = {}
    for line in lines[1:31]:
        if line.strip() == "---":
            break
        m = _FRONTMATTER_KEY_RE.match(line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def read_spec(path: str) -> Tuple[Dict[str, str], str]:
    """回 (frontmatter, 全文)；讀不到回 ({}, "")。"""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        return {}, ""
    return parse_frontmatter(text), text


def read_spec_with_done_fallback(path: str) -> Tuple[Dict[str, str], str]:
    """讀規格檔，原路徑失敗時退同目錄 done/ 下同名檔。

    收尾慣例是「status→done 後移入 done/」；spec_done 觸發到 audit 子程序
    實際讀檔之間有競態窗，移檔不應讓已綁定的審計退化成 uncertain。
    """
    fm, text = read_spec(path)
    if text:
        return fm, text
    p = Path(path)
    return read_spec(str(p.parent / "done" / p.name))


def _sidecar_spec_paths(session_id: str) -> List[str]:
    try:
        data = json.loads(
            (SIDECAR_DIR / f"{session_id}.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return []
    paths = data.get("spec_paths", [])
    return [p for p in paths if isinstance(p, str) and p]


def _project_spec_paths(cwd: str) -> List[str]:
    """掃 <cwd 所在 git root>/.claude/verify/acceptance-*.md（不含 done/）。

    git root 解析失敗 → 退回 cwd 本身（單層），不向上亂爬。
    """
    root = git_root(cwd) or cwd
    if not root:
        return []
    verify_dir = Path(root) / ".claude" / "verify"
    try:
        return [str(p) for p in sorted(verify_dir.glob(_SPEC_GLOB)) if p.is_file()]
    except OSError:
        return []


def resolve_binding(session_id: str, cwd: str) -> Dict[str, Any]:
    """任務↔規格檔唯一綁定。回 dict：

        {binding, spec_path, task_slug, candidates, uncertain_reason}

    只有 binding == BINDING_BOUND 時 spec_path 非空、才准發審計。
    """
    seen: set = set()
    candidates: List[str] = []
    for p in _sidecar_spec_paths(session_id) + _project_spec_paths(cwd):
        norm = p.replace("\\", "/")
        if norm in seen:
            continue
        seen.add(norm)
        candidates.append(p)

    mine: List[Tuple[str, Dict[str, str]]] = []
    others: List[str] = []
    for p in candidates:
        fm, text = read_spec(p)
        if not text:
            continue  # 已移入 done/ 或已刪 → 不是活規格
        if str(fm.get("status", "")).lower() != "open":
            continue
        if fm.get("session_id", "") == session_id:
            mine.append((p, fm))
        else:
            others.append(p)

    if len(mine) == 1:
        path, fm = mine[0]
        return {
            "binding": BINDING_BOUND,
            "spec_path": path,
            "task_slug": fm.get("task_slug", ""),
            "candidates": candidates,
            "uncertain_reason": "",
        }
    if len(mine) > 1:
        detail = "；候選：" + ", ".join(Path(p).name for p, _ in mine)
        return {
            "binding": BINDING_AMBIGUOUS, "spec_path": "", "task_slug": "",
            "candidates": candidates,
            "uncertain_reason": _UNCERTAIN_REASON[BINDING_AMBIGUOUS] + detail,
        }
    if others:
        detail = "；候選：" + ", ".join(Path(p).name for p in others)
        return {
            "binding": BINDING_OTHER_SESSION, "spec_path": "", "task_slug": "",
            "candidates": candidates,
            "uncertain_reason": _UNCERTAIN_REASON[BINDING_OTHER_SESSION] + detail,
        }
    return {
        "binding": BINDING_NONE, "spec_path": "", "task_slug": "",
        "candidates": candidates,
        "uncertain_reason": _UNCERTAIN_REASON[BINDING_NONE],
    }


# ─── 2. 案卷 diff 採樣（Q4） ─────────────────────────────────────────────────


def _run_git(args: List[str], cwd: str) -> str:
    """跑唯讀 git 指令回 stdout；任何失敗回 ''（caller 須給 in-band 說明）。"""
    if not cwd or not os.path.isdir(cwd):
        return ""
    try:
        r = subprocess.run(
            ["git", "-C", cwd] + args,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=_GIT_TIMEOUT,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.SubprocessError) as e:
        _log(f"git {' '.join(args[:2])} failed: {e}")
        return ""
    if r.returncode != 0:
        return ""
    return r.stdout or ""


def git_root(cwd: str) -> str:
    return _run_git(["rev-parse", "--show-toplevel"], cwd).strip()


def _sample(text: str, head: int, tail: int, label: str) -> str:
    """頭尾採樣 + in-band 標記（本模組自帶，語意比通用版更貼 diff 場景）。"""
    if len(text) <= head + tail:
        return text
    return (
        text[:head]
        + f"\n…（{label} 中段省略：全段共 {len(text)} 字，此處僅含開頭 {head} 字"
          f"與結尾 {tail} 字；此為案卷採樣截斷，不是檔案本身缺漏）…\n"
        + text[-tail:]
    )


def _split_diff_by_file(diff_text: str) -> List[Tuple[str, str]]:
    """把 unified diff 依 `diff --git` 切成 [(檔名, 該檔 diff 全文)]。"""
    if not diff_text:
        return []
    chunks: List[Tuple[str, str]] = []
    cur_name = ""
    cur: List[str] = []
    for line in diff_text.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if cur:
                chunks.append((cur_name, "".join(cur)))
            cur = [line]
            parts = line.split(" b/", 1)
            cur_name = parts[1].strip() if len(parts) == 2 else line.strip()
        else:
            cur.append(line)
    if cur:
        chunks.append((cur_name, "".join(cur)))
    return chunks


def _untracked_files(cwd: str) -> List[str]:
    out = _run_git(["status", "--porcelain", "--untracked-files=all"], cwd)
    files = []
    for line in out.splitlines():
        if line.startswith("?? "):
            files.append(line[3:].strip().strip('"'))
    return files


def build_diff_digest_from_text(
    stat_text: str,
    diff_text: str,
    untracked_blocks: Optional[List[Tuple[str, str]]] = None,
    force_skip_files: Optional[List[str]] = None,
) -> Tuple[str, bool]:
    """由現成 diff 文字組案卷變更摘要（採樣/標記規則的唯一來源）。

    工作樹版 `collect_diff_digest` 與回測（歷史 commit 回放）共用本函式，
    確保兩邊的採樣行為與 in-band 標記完全一致、不 drift。

    force_skip_files：這些檔名即使預算足夠也強制列入「未採樣清單」
    （回測 C 組用——驗證裁判對缺席內容守 uncertain 紀律）。
    """
    truncated = False
    parts: List[str] = []
    force_skip = set(force_skip_files or [])

    stat = (stat_text or "").strip()
    if stat:
        if len(stat) > DIFF_STAT_MAX_CHARS:
            stat = _sample(stat, DIFF_STAT_MAX_CHARS - 400, 400, "變更檔案清單")
            truncated = True
        parts.append("### 變更檔案清單（git diff --stat）\n" + stat)
    else:
        parts.append("### 變更檔案清單（git diff --stat）\n"
                     "（無已追蹤檔案變更；可能全部已 commit，或改動僅在新增未追蹤檔）")

    chunks = _split_diff_by_file(diff_text or "")
    used = 0
    shown: List[str] = []
    skipped: List[str] = []
    for name, body in chunks:
        if used >= DIFF_BUDGET_CHARS or name in force_skip:
            skipped.append(name)
            continue
        sampled = _sample(body, DIFF_PER_FILE_HEAD, DIFF_PER_FILE_TAIL, f"{name} 的 diff")
        if len(sampled) < len(body):
            truncated = True
        shown.append(f"--- {name} ---\n{sampled}")
        used += len(sampled)

    if shown:
        parts.append("### 變更內容（逐檔採樣）\n" + "\n\n".join(shown))
    if skipped:
        truncated = True
        parts.append(
            f"### 未採樣的變更檔案（{len(skipped)} 檔，因案卷預算未納入內容）\n"
            + "\n".join(f"- {n}" for n in skipped)
            + "\n（這些檔案「有」變更，只是內容未附；勿因未見內容就判定沒做，"
              "如需依據請以 uncertain 回報）"
        )

    for name, block in (untracked_blocks or []):
        parts.append(block)

    return "\n\n".join(parts), truncated


def collect_diff_digest(cwd: str) -> Tuple[str, bool]:
    """組工作樹的案卷變更摘要，回 (digest_text, truncated)。

    組成：
      A. `git diff HEAD --stat` — 檔案清單求完整（超長才採樣並標記）
      B. 逐檔 unified diff 頭尾採樣，累積至 DIFF_BUDGET_CHARS；
         超預算的檔案不靜默丟掉，改列成「未採樣檔案清單」
      C. untracked 新檔：前 N 檔取檔頭，其餘列清單（新檔在 diff HEAD 看不到，
         漏掉會讓裁判把「新增了 X」誤判成沒做）
    採樣邏輯共用 build_diff_digest_from_text（規則唯一來源）。
    """
    if not cwd or not os.path.isdir(cwd):
        return ("（無法取得工作目錄，本次案卷沒有變更內容可依據；"
                "請以 uncertain 回報，勿臆測改了什麼）", True)

    root = git_root(cwd) or cwd
    stat = _run_git(["diff", "HEAD", "--stat"], root)
    raw_diff = _run_git(["diff", "HEAD"], root)
    digest, truncated = build_diff_digest_from_text(stat, raw_diff)
    parts: List[str] = [digest] if digest else []

    untracked = _untracked_files(root)
    if untracked:
        heads: List[str] = []
        for name in untracked[:UNTRACKED_MAX_FILES]:
            try:
                text = (Path(root) / name).read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                heads.append(f"--- {name}（新增檔，內容無法讀取）---")
                continue
            head = text[:UNTRACKED_HEAD_CHARS]
            mark = ("\n…（新增檔僅附開頭 "
                    f"{UNTRACKED_HEAD_CHARS} 字，全檔共 {len(text)} 字）…"
                    if len(text) > UNTRACKED_HEAD_CHARS else "")
            if mark:
                truncated = True
            heads.append(f"--- {name}（新增檔）---\n{head}{mark}")
        rest = untracked[UNTRACKED_MAX_FILES:]
        block = "### 新增未追蹤檔案\n" + "\n\n".join(heads)
        if rest:
            truncated = True
            block += ("\n\n其餘新增檔（僅列名，內容未附）：\n"
                      + "\n".join(f"- {n}" for n in rest))
        parts.append(block)

    return "\n\n".join(parts), truncated


def collect_verification_evidence(tool_trace: List[Dict[str, Any]]) -> str:
    """驗證證據（含實際輸出）——比 turn_audit 版多帶 output_summary。

    案卷要回答的是「說測過的真的有測試輸出嗎」，只給指令不給輸出等於沒證據。
    """
    try:
        import heuristics
        verify_re = heuristics._VERIFY_CMD_RE
    except Exception:
        return "（無法載入驗證指令規則，本次案卷無測試證據可依據）"

    hits: List[str] = []
    for i, t in enumerate(tool_trace or [], 1):
        if t.get("tool") not in ("Bash", "PowerShell"):
            continue
        cmd = t.get("input", "") or ""
        if not verify_re.search(cmd):
            continue
        out = (t.get("output_summary", "") or "").strip()
        outcome = "FAILED" if out.startswith("[FAILED]") else "ok"
        hits.append(f"#{i} [{outcome}] $ {cmd[:160]}\n    輸出：{out[:300] or '(無輸出擷取)'}")

    if not hits:
        return ("（tool trace 中找不到任何測試/驗證指令；注意 trace 只收錄"
                "受監測工具，缺席不等於沒跑過——若這是判斷關鍵請回 uncertain）")
    total = len(hits)
    tail = hits[-EVIDENCE_MAX_ITEMS:]
    text = "\n".join(tail)
    header = (f"（共 {total} 條驗證指令，此處顯示最近 {len(tail)} 條）\n"
              if total > len(tail) else "")
    if len(text) > EVIDENCE_MAX_CHARS:
        text = text[:EVIDENCE_MAX_CHARS] + "\n…（驗證證據因案卷預算截斷）…"
    return header + text


# ─── 3. 稽核落盤 ─────────────────────────────────────────────────────────────


def append_audit(record: Dict[str, Any]) -> None:
    """append 一筆到 acceptance-audit.jsonl（影子期唯一數據來源）。

    含 `human_label`（null）供事後標註精確率：Phase 3 開工前一次性回顧，
    不逐次打擾。超過 2MB 輪替成 .1（單層，舊的直接覆蓋）。
    """
    record.setdefault("ts", _now_iso())
    record.setdefault("human_label", None)
    try:
        WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
        if AUDIT_JSONL.exists() and AUDIT_JSONL.stat().st_size > AUDIT_JSONL_MAX_BYTES:
            AUDIT_JSONL.replace(AUDIT_JSONL.with_suffix(".jsonl.1"))
        with open(AUDIT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        _log(f"audit append failed: {e}")


def read_audits(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """讀回稽核紀錄（新到舊）。供 Q5 門檻統計與人工標註流程用。"""
    try:
        lines = AUDIT_JSONL.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
        if limit and len(out) >= limit:
            break
    return out


def promotion_stats(records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Q5 轉正門檻統計（N≥20 / precision≥60% / uncertain≤30%）。

    precision 只算已人工標註（human_label ∈ {true_hit, false_alarm}）的 fail 判定；
    未標註的不猜（沒標＝沒數據，不是通過）。
    """
    recs = records if records is not None else read_audits()
    effective = [r for r in recs if r.get("verdict") in ("pass", "fail", "uncertain")]
    n_eff = len(effective)
    n_uncertain = sum(1 for r in effective if r.get("verdict") == "uncertain")
    labeled = [r for r in effective
               if r.get("verdict") == "fail"
               and r.get("human_label") in ("true_hit", "false_alarm")]
    n_true = sum(1 for r in labeled if r["human_label"] == "true_hit")
    precision = (n_true / len(labeled)) if labeled else None
    uncertain_rate = (n_uncertain / n_eff) if n_eff else None

    ready = bool(
        n_eff >= 20
        and precision is not None and precision >= 0.60
        and uncertain_rate is not None and uncertain_rate <= 0.30
    )
    kill = bool(precision is not None and len(labeled) >= 10 and precision < 0.50)
    return {
        "samples": n_eff,
        "uncertain": n_uncertain,
        "uncertain_rate": uncertain_rate,
        "fail_labeled": len(labeled),
        "true_hits": n_true,
        "precision": precision,
        "unlabeled_fails": sum(1 for r in effective
                               if r.get("verdict") == "fail"
                               and r.get("human_label") not in ("true_hit", "false_alarm")),
        "promotion_ready": ready,
        "kill_switch": kill,
    }


# ─── 材料採樣（供 assessor 組 prompt） ────────────────────────────────────────


def sample_spec(text: str) -> str:
    return _sample(text, SPEC_HEAD, SPEC_TAIL, "驗收規格檔")


def sample_goal(text: str) -> str:
    return _sample(text, GOAL_HEAD, GOAL_TAIL, "需求原話")
