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
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# pythonw（Task Scheduler 靜默跑）下 sys.stdout/stderr 為 None——直接
# reconfigure 會 AttributeError 秒死。None → devnull，有的才轉 UTF-8。
for _name in ("stdout", "stderr"):
    _s = getattr(sys, _name)
    if _s is None:
        setattr(sys, _name, open(os.devnull, "w", encoding="utf-8"))
    else:
        _s.reconfigure(encoding="utf-8")

CLAUDE_DIR = Path(__file__).resolve().parent.parent
TOOLS = CLAUDE_DIR / "tools"
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
            timeout=timeout, cwd=str(CLAUDE_DIR),
        )
        return json.loads(r.stdout)
    except Exception:
        return None


def _run_check(args: list[str], timeout: int = 120) -> tuple[bool, str]:
    """跑 --check 型工具；回 (通過, 摘要輸出)。"""
    try:
        r = subprocess.run(
            [PY, *args], capture_output=True, text=True, encoding="utf-8",
            timeout=timeout, cwd=str(CLAUDE_DIR),
        )
        tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        return r.returncode == 0, (tail[-1] if tail else "")
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _newest_mtime(pattern_dir: Path, glob: str) -> datetime | None:
    try:
        files = list(pattern_dir.glob(glob))
        if not files:
            return None
        return datetime.fromtimestamp(max(f.stat().st_mtime for f in files))
    except OSError:
        return None


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


def collect() -> dict:
    now = datetime.now()
    red: list[str] = []      # 需處理
    yellow: list[str] = []   # 需留意
    info: list[str] = []     # 純資訊

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

    # 3/4. 索引一致性
    for name, args in (
        ("atom index", [str(TOOLS / "sync-atom-index.py"), "--check"]),
        ("skill index", [str(TOOLS / "skill-index.py"), "--check"]),
    ):
        ok, msg = _run_check(args)
        if not ok:
            red.append(f"{name} drift：{msg}")

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
        "promotion audit（confirmations 流）": _promotion_last_ts(),
        "episodic 生成": _newest_mtime(MEMORY / "episodic", "episodic-*.md"),
    }
    for label, ts in checks.items():
        if ts is None or ts < fresh_cut:
            age = "無資料" if ts is None else f"最後 {ts:%Y-%m-%d}"
            if sessions_active:
                red.append(f"{label} 停擺（{age}，但近 {FRESH_DAYS} 天有 session）——疑管線靜默失效")
            else:
                info.append(f"{label} {age}；近 {FRESH_DAYS} 天無 session，屬預期")

    return {"at": now.isoformat(timespec="seconds"), "red": red,
            "yellow": yellow, "info": info,
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
    path.write_text("\n".join(lines), encoding="utf-8")
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
        "report": str(report),
    }, ensure_ascii=False), encoding="utf-8")
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print(f"[health-weekly] 紅 {len(result['red'])} / 黃 {len(result['yellow'])}"
              f" / 資訊 {len(result['info'])} → {report}")
    return 1 if result["red"] else 0


# REGISTER（一次性，已由安裝流程執行；重灌時照抄）：
#   schtasks /Create /TN "Claude-Memory-WeeklyHealth" /SC WEEKLY /D MON /ST 09:00
#     /TR "C:/Users/holylight/AppData/Local/Python/bin/pythonw.exe
#          C:/Users/holylight/.claude/tools/health-weekly.py"
# 錯過排程（關機）→ 下次開機由 Task Scheduler 設定補跑；SessionStart 死人開關兜底。
if __name__ == "__main__":
    sys.exit(main())
