"""wg_overview — OverviewHub 的 state 層：三個 hook 各呼叫一個函式。

做什麼：第一次碰到某部位（Read／Bash 讀檔、提示詞提到路徑、或直接 Edit）就整張注入該部位導讀卡，
一個 session 一個部位只注入一次；之後記「注入後讀了幾個檔、跨幾個頂層目錄」；Edit 前查 AI 有沒有交
定位三行——dry_run 時只警告，關掉 dry_run 才擋。每個事件各落一行 jsonl 到 workflow/overview-hub.log 當量測資料。

state["overview_hub"] = {
  "<root>|<part>": {"injected_turn", "injected_at", "transcript_offset", "reads_after": [...], "located": bool, "edits": n}
}
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import CLAUDE_DIR

sys.path.insert(0, str(CLAUDE_DIR / "lib"))
from overview_hub import (  # noqa: E402
    assistant_text_after, build_injection, find_map, locate_present, match_row,
    parse_map, read_paths_from_tool, resolve_card, top_dir, transcript_size,
)

LOG_PATH = CLAUDE_DIR / "workflow" / "_overview-hub.log"   # _*.log 不進版控
_DEFAULT = {"enabled": True, "dry_run": True, "max_card_chars": 6000}


def _cfg(config: Dict[str, Any], root: Optional[Path] = None) -> Dict[str, Any]:
    """根層 config.json 的 overview_hub 段，再被專案 `<root>/.claude/overview-hub.json` 覆蓋（專案可自己調 dry_run 等）。"""
    c = dict(_DEFAULT)
    c.update(config.get("overview_hub") or {})
    if root is not None:
        try:
            ov = root / ".claude" / "overview-hub.json"
            if ov.is_file():
                c.update(json.loads(ov.read_text(encoding="utf-8")))
        except (OSError, ValueError) as e:
            sys.stderr.write(f"[Guardian:OverviewHub] 專案覆蓋檔讀取失敗（用根層設定）：{e}\n")
    return c


def _log(event: str, session_id: str, **kw: Any) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "event": event,
                                "session": session_id[:8], **kw}, ensure_ascii=False) + "\n")
    except OSError as e:
        sys.stderr.write(f"[Guardian:OverviewHub] log 寫入失敗（不影響注入）：{e}\n")


def _lookup(path: str) -> Optional[Tuple[Path, Dict[str, Any]]]:
    """路徑 → (專案根, 命中的表列)；找不到表或沒命中回 None。"""
    found = find_map(path)
    if not found:
        return None
    root, map_path = found
    try:
        rows = parse_map(map_path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    row = match_row(path, root, rows)
    return (root, row) if row else None


def _key(root: Path, row: Dict[str, Any]) -> str:
    return f"{str(root).replace(chr(92), '/').lower()}|{row['part_short']}"


def _inject(state: Dict[str, Any], session_id: str, root: Path, row: Dict[str, Any],
            hit_path: str, via: str, transcript_path: str, cfg: Dict[str, Any]) -> str:
    card_path = resolve_card(root, row["card"]) if row["status"] in ("有", "部分", "索引") else None
    text = build_injection(row, card_path, hit_path, int(cfg["max_card_chars"]))
    hub = state.setdefault("overview_hub", {})
    hub[_key(root, row)] = {
        "injected_turn": int(state.get("turn_seq", 0)),
        "injected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "transcript_offset": transcript_size(transcript_path),
        "reads_after": [],
        "located": False,
        "edits": 0,
    }
    _log("inject", session_id, part=row["part_short"], status=row["status"], via=via,
         path=hit_path, card=str(card_path) if card_path else None, chars=len(text))
    return text


def on_read(state: Dict[str, Any], session_id: str, tool_name: str, tool_input: Dict[str, Any],
            cwd: str, transcript_path: str, config: Dict[str, Any]) -> Optional[str]:
    """PostToolUse（Read／Bash）：第一次讀到某部位 → 回注入文字；已注入 → 記 reads_after。"""
    cfg = _cfg(config)
    if not cfg["enabled"]:
        return None
    for p in read_paths_from_tool(tool_name, tool_input, cwd):
        hit = _lookup(p)
        if not hit:
            continue
        root, row = hit
        rec = (state.get("overview_hub") or {}).get(_key(root, row))
        if rec is None:
            cfg = _cfg(config, root)
            if not cfg["enabled"]:
                return None
            return _inject(state, session_id, root, row, p, tool_name.lower(), transcript_path, cfg)
        if p not in rec["reads_after"]:
            rec["reads_after"].append(p)
    return None


def on_prompt(state: Dict[str, Any], session_id: str, prompt: str, transcript_path: str,
              config: Dict[str, Any]) -> Optional[str]:
    """UserPromptSubmit：提示詞裡出現的絕對路徑命中某部位且未注入 → 注入。"""
    import re
    cfg = _cfg(config)
    if not cfg["enabled"]:
        return None
    for m in re.finditer(r"[A-Za-z]:[\\/][^\s`'\"<>|]+", prompt):
        hit = _lookup(m.group(0))
        if not hit:
            continue
        root, row = hit
        if _key(root, row) not in (state.get("overview_hub") or {}):
            cfg = _cfg(config, root)
            if not cfg["enabled"]:
                return None
            return _inject(state, session_id, root, row, m.group(0), "prompt", transcript_path, cfg)
    return None


def on_edit(state: Dict[str, Any], session_id: str, file_path: str, transcript_path: str,
            config: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """PreToolUse（Edit／Write）：回 (警告文字, deny 理由)。dry_run 時 deny 恆 None。"""
    cfg = _cfg(config)
    if not cfg["enabled"] or not file_path:
        return (None, None)
    hit = _lookup(file_path)
    if not hit:
        return (None, None)
    root, row = hit
    cfg = _cfg(config, root)
    if not cfg["enabled"]:
        return (None, None)
    key = _key(root, row)
    rec = (state.get("overview_hub") or {}).get(key)
    if rec is None:
        text = _inject(state, session_id, root, row, file_path, "edit", transcript_path, cfg)
        msg = (f"[Guardian:OverviewHub] 要改【{row['part_short']}】部位的檔但本 session 還沒看過這個部位的導讀卡——"
               f"卡片現在才注入（下面）。先讀完、在回覆交出定位三行，再改。\n{text}")
        _log("edit_before_inject", session_id, part=row["part_short"], path=file_path)
        return (msg, None if cfg["dry_run"] else msg.split("\n", 1)[0])
    rec["edits"] = int(rec.get("edits", 0)) + 1
    reads = rec.get("reads_after", [])
    dirs = sorted({top_dir(p, root) for p in reads})
    if not rec.get("located"):
        text = assistant_text_after(transcript_path, int(rec.get("transcript_offset", 0)))
        rec["located"] = locate_present(text, row["part_short"]) if text else False
        verifiable = transcript_size(transcript_path) > 0   # transcript 讀得到就可驗；沒文字＝沒交
    else:
        verifiable = True
    _log("edit", session_id, part=row["part_short"], path=file_path, located=rec["located"],
         verifiable=verifiable, reads_after_inject=len(reads), dirs_after_inject=len(dirs),
         edits=rec["edits"], dry_run=cfg["dry_run"])
    if rec["located"] or not verifiable:
        return (None, None)
    msg = (f"[Guardian:OverviewHub] 改【{row['part_short']}】部位的檔（{file_path}）前還沒交出定位三行"
           f"（注入導讀卡後讀了 {len(reads)} 個檔、跨 {len(dirs)} 個目錄）。"
           f"請先在回覆寫：定位｜部位：…／定位｜根因層：…／定位｜前例：…"
           + ("（目前 dry-run，只提醒不擋）" if cfg["dry_run"] else ""))
    return (msg, None if cfg["dry_run"] else msg)
