"""wg_scorecard：每個 session 收尾算一行過程量（S1／S3／S5）落 `workflow/scorecard/<yyyymm>.jsonl`。

做什麼：只讀 state 的 `overview_hub`（每部位：注入後讀了幾個檔、交沒交定位三行、改了幾次）與 `modified_files`，
算三個比例，單次 append 一行（<100 ms；無 state 不寫；沒注入過任何部位也不寫，沒東西可量）。
報表與候選卡由 `tools/scorecard-report.py` 另算；本模組不讀報表、不讀 candidates.json（回路單向：M4 讀候選，候選不回餵量尺）。

S1＝有改的部位裡，導讀卡注入後曾讀過至少一個檔的比例（state 的 `reads_after` 只記「注入後」，不分改前改後；
預計畫附錄 C「首改前有沒有讀卡」要等 wg_overview 凍結 reads_before_edit 才量得準）。
S3＝有改的部位裡，交出定位三行的比例（`located`）。
S5＝被注入的部位裡，之後讀過卡片檔（memory／_atoms 下的 .md）的比例。
分母為零 → None（不是 0）。

health_block()：給 health-weekly 兩行（讀 `workflow/scorecard/candidates.json`；沒報表就說沒報表）。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SCORECARD_DIR_NAME = "scorecard"
CANDIDATES_NAME = "candidates.json"
MAX_PARTS = 50
REPORT_CMD = "python ~/.claude/tools/scorecard-report.py"


def _workflow_dir() -> Path:
    import wg_core   # 取即時值，verify monkeypatch wg_core.WORKFLOW_DIR 後仍生效
    return wg_core.WORKFLOW_DIR


def scorecard_dir() -> Path:
    return _workflow_dir() / SCORECARD_DIR_NAME


def _ratio(num: int, den: int) -> Optional[float]:
    return None if den <= 0 else round(num / den, 3)


def _is_card_path(p: Any) -> bool:
    if not isinstance(p, str):
        return False
    q = p.replace("\\", "/").lower()
    return q.endswith(".md") and ("/memory/" in q or "/_atoms/" in q)


def compute_session_scores(state: Any) -> Optional[Dict[str, Any]]:
    """state → {s1, s3, s5, parts_injected, parts_edited, modified_files, parts:[…]}；state 不是 dict → None。"""
    if not isinstance(state, dict):
        return None
    hub = state.get("overview_hub")
    hub = hub if isinstance(hub, dict) else {}
    mods = state.get("modified_files")
    mods = mods if isinstance(mods, list) else []
    parts: List[Dict[str, Any]] = []
    for key, rec in hub.items():
        if not isinstance(rec, dict):
            continue
        root, _, part = str(key).rpartition("|")
        reads = rec.get("reads_after")
        reads = reads if isinstance(reads, list) else []
        parts.append({
            "key": str(key), "root": root, "part": part,
            "edits": int(rec.get("edits", 0) or 0), "reads": len(reads),
            "located": bool(rec.get("located")), "located_via": rec.get("located_via"),
            "card_read": any(_is_card_path(p) for p in reads),
        })
    edited = [p for p in parts if p["edits"] > 0]
    return {
        "s1": _ratio(sum(1 for p in edited if p["reads"] > 0), len(edited)),
        "s3": _ratio(sum(1 for p in edited if p["located"]), len(edited)),
        "s5": _ratio(sum(1 for p in parts if p["card_read"]), len(parts)),
        "parts_injected": len(parts), "parts_edited": len(edited),
        "modified_files": sum(1 for m in mods if isinstance(m, dict)),
        "parts": parts[:MAX_PARTS],
    }


def append_scorecard_line(state: Any, session_id: str, now: Optional[float] = None) -> Optional[Path]:
    """SessionEnd 用：算分、append 一行；回寫到的檔路徑。無 state／沒注入過部位 → None 不寫。"""
    scores = compute_session_scores(state)
    if scores is None or scores["parts_injected"] == 0:
        return None
    ts = now if now is not None else time.time()
    line = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)),
        "session_id": session_id or "",
        "cwd": str((state.get("session") or {}).get("cwd", "")) if isinstance(state.get("session"), dict) else "",
        **scores,
    }
    path = scorecard_dir() / f"{time.strftime('%Y%m', time.localtime(ts))}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return path


def health_block() -> List[str]:
    """health-weekly 的 scorecard 段：恆兩行。第一行基線與低於基線的部位數，第二行下一張該寫的卡。"""
    path = scorecard_dir() / CANDIDATES_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"scorecard：尚無報表（跑 {REPORT_CMD}）", "下一張該寫的卡：無資料（先產報表）"]
    except (OSError, ValueError) as e:
        return [f"scorecard：candidates.json 讀不出來（{e}）→ 重跑 {REPORT_CMD}", "下一張該寫的卡：無資料"]
    if not isinstance(data, dict):
        return [f"scorecard：candidates.json 不是物件（{type(data).__name__}）→ 重跑 {REPORT_CMD}", "下一張該寫的卡：無資料"]
    base, recent = data.get("baseline_s1"), data.get("recent_s1")
    base = base if isinstance(base, (int, float)) else None
    recent = recent if isinstance(recent, (int, float)) else None
    below = [b for b in (data.get("below_baseline") or []) if isinstance(b, dict)]
    top = [t for t in (data.get("top") or []) if isinstance(t, dict)]
    fmt = lambda v: "無" if v is None else f"{v:.2f}"  # noqa: E731
    line1 = (f"scorecard：{str(data.get('generated_at', ''))[:10]} 基線 S1 {fmt(base)}／近週 S1 {fmt(recent)}，"
             f"低於基線部位 {len(below)}" + (f"（{'、'.join(str(b.get('part', '')) for b in below[:3])}）" if below else ""))
    names = "、".join(str(t.get("part", "")) for t in top[:3]) or "無"
    line2 = f"下一張該寫的卡：{names}（{path}）"
    return [line1, line2]
