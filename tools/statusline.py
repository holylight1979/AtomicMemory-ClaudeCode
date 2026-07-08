#!/usr/bin/env python3
"""statusline.py — Claude Code statusLine 渲染器（Guardian 常駐可觀測層）。

settings.json `statusLine` 指到本檔：stdin 吃 CC 的 status JSON（session_id /
model / context_window…），stdout 回一行 ANSI 上色狀態列。chat 內純資訊性注入
（UPS [Guardian] Reminder）由此取代——零 token 常駐可見。

資料源（全部本地檔讀取、無 subprocess、pure stdlib）：
  - workflow/state-<session_id>.json → 改檔數 / 讀檔數 / 知識佇列
    （accessed_files 由 Stop 端從 transcript 尾段回收，更新頻率 = 每 turn 一次）
  - workflow/vector_ready.flag      → vector 服務健康（SessionStart 健檢寫入）
  - workflow/aec-report/<sid>-t*.json（最大 turn）→ 本輪 AEC severity

Fail-open 必告知：state 缺失/壞檔 → 顯示 `WG:?`（不裝沒事）；stdin 壞 → 印最小
降級行。本檔永遠印出一行，絕不拋例外（statusLine 靜默失敗 = 可觀測層自身失明）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = CLAUDE_DIR / "workflow"

# ANSI（Windows Terminal / VSCode 終端皆支援）
RESET = "\x1b[0m"
DIM = "\x1b[2m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
RED = "\x1b[31;1m"
CYAN = "\x1b[36m"

_SEV_STYLE = {"routine": DIM + GREEN, "notable": YELLOW, "real-evasion": RED}


def _ctx_segment(data: dict) -> str:
    cw = data.get("context_window") or {}
    pct = cw.get("used_percentage")
    if pct is None:
        return ""
    color = GREEN if pct < 60 else (YELLOW if pct < 85 else RED)
    return f"{color}ctx{pct:.0f}%{RESET}"


def _guardian_segments(session_id: str) -> list[str]:
    """讀 Guardian state / vector flag / AEC report → 各段字串。壞檔即 WG:?。"""
    segs: list[str] = []
    state_path = WORKFLOW_DIR / f"state-{session_id}.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        mod = len(state.get("modified_files") or [])
        acc = len(state.get("accessed_files") or [])
        kq = len(state.get("knowledge_queue") or [])
        mod_color = YELLOW if mod else DIM
        segs.append(f"{mod_color}改{mod}{RESET} {DIM}讀{acc}{RESET}")
        if kq:
            segs.append(f"{YELLOW}佇{kq}{RESET}")
    except (OSError, ValueError):
        segs.append(f"{RED}WG:?{RESET}")  # state 不可讀 → 降級可見，不裝沒事

    if (WORKFLOW_DIR / "vector_ready.flag").exists():
        segs.append(f"{GREEN}vec✓{RESET}")
    else:
        segs.append(f"{RED}vec✗{RESET}")

    sev = _latest_aec_severity(session_id)
    if sev:
        segs.append(f"{_SEV_STYLE.get(sev, YELLOW)}AEC:{sev}{RESET}")
    return segs


def _latest_aec_severity(session_id: str) -> str | None:
    """本 session 最大 turn 的 aec-report severity；無報告（尚未收尾）→ None。"""
    d = WORKFLOW_DIR / "aec-report"
    best_turn, best_path = -1, None
    try:
        for p in d.glob(f"{session_id}-t*.json"):
            m = re.search(r"-t(\d+)\.json$", p.name)
            if m and int(m.group(1)) > best_turn:
                best_turn, best_path = int(m.group(1)), p
        if best_path is None:
            return None
        return json.loads(best_path.read_text(encoding="utf-8")).get("severity")
    except (OSError, ValueError):
        return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        print(f"{DIM}statusline: no input{RESET}")
        return
    parts: list[str] = []
    model = (data.get("model") or {}).get("display_name")
    if model:
        parts.append(f"{CYAN}{model}{RESET}")
    ctx = _ctx_segment(data)
    if ctx:
        parts.append(ctx)
    parts.extend(_guardian_segments(data.get("session_id") or ""))
    print(f" {DIM}·{RESET} ".join(parts))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 最外層兜底：任何未預期錯誤仍印一行（不失明）
        print(f"{RED}statusline err: {type(e).__name__}{RESET}")
