"""wg_provenance — PostToolUse 對剛寫入的 atom 自動補來源（Source／Quote）。

做什麼：atom_write 成功（receipt op=create|replace）後，從 hook input 與 state 取
「這張卡片是哪個 session、哪則使用者訊息觸發的」，用 lib.atom_io.edit_metadata 補
`- Source: session:<sid8>#<uuid8> <日期>` 與 `- Quote: 「使用者原話」`。不靠模型記得填。

規則：
- 檔內已有 `- Quote:` → 不動（呼叫者自填或已補過）。
- 呼叫者已給非空 Source（例：會議轉錄的逐字稿路徑）→ 只補 Quote。
- Quote 取 state["turn_prompts"][-1]（本回合最後一則使用者原話，≤500 字）消毒後 ≤200 字；
  空字串不寫。uuid 從 transcript 尾端最後一則真人訊息取，取不到只寫 session＋日期。
- 任何失敗只記 Logs/guard-provenance.jsonl，不阻斷 hook。

入口：autofill_from_receipt(receipt, input_data, state) → dict（結果摘要，供測試與日誌）。
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from wg_core import CLAUDE_DIR, append_guard_log

_QUOTE_LINE_RE = re.compile(r"^- Quote:\s*\S", re.MULTILINE)
_SOURCE_LINE_RE = re.compile(r"^- Source:\s*(\S.*)$", re.MULTILINE)


def _last_turn_prompt(state: Dict[str, Any]) -> str:
    prompts = state.get("turn_prompts") or []
    if not isinstance(prompts, list) or not prompts:
        return ""
    last = prompts[-1]
    return last if isinstance(last, str) else ""


def _last_human_uuid(transcript_path: str) -> Optional[str]:
    if not transcript_path:
        return None
    p = Path(transcript_path)
    if not p.is_file():
        return None
    try:
        import sys
        lib_root = str(CLAUDE_DIR)
        if lib_root not in sys.path:
            sys.path.insert(0, lib_root)
        from lib.provenance import last_human_record  # noqa: WPS433
        rec = last_human_record(p)
    except Exception:
        return None
    if not rec:
        return None
    uuid = rec.get("uuid") or ""
    return uuid or None


def autofill_from_receipt(receipt: Dict[str, Any], input_data: Dict[str, Any],
                          state: Dict[str, Any]) -> Dict[str, Any]:
    """對 receipt 指到的 atom 補 Source／Quote。回傳 {"done": bool, "reason": str, ...}。"""
    out: Dict[str, Any] = {"done": False, "reason": ""}
    try:
        if not receipt or not receipt.get("ok") or receipt.get("op") not in ("create", "replace"):
            out["reason"] = "not_create_or_replace"
            return out
        path_s = receipt.get("path") or ""
        path = Path(path_s)
        if not path_s or not path.is_file():
            out["reason"] = "path_missing"
            return out
        text = path.read_text(encoding="utf-8-sig")
        if _QUOTE_LINE_RE.search(text):
            out["reason"] = "has_quote"
            return out

        import sys
        lib_root = str(CLAUDE_DIR)
        if lib_root not in sys.path:
            sys.path.insert(0, lib_root)
        from lib.atom_io import edit_metadata
        from lib.provenance import format_quote, format_source_session, sanitize_quote

        session_id = str(input_data.get("session_id") or state.get("session", {}).get("id") or "")
        quote_raw = _last_turn_prompt(state)
        quote_clean = sanitize_quote(quote_raw)
        quote_line = format_quote(quote_clean) if quote_clean else None

        sm = _SOURCE_LINE_RE.search(text)
        has_source = bool(sm and sm.group(1).strip())
        provenance = None
        if not has_source and session_id:
            uuid = _last_human_uuid(str(input_data.get("transcript_path") or ""))
            provenance = format_source_session(session_id, uuid, date.today().isoformat())

        if provenance is None and quote_line is None:
            out["reason"] = "nothing_to_fill"
            return out
        res = edit_metadata(path, provenance=provenance, quote=quote_line, source="hook:provenance")
        out.update({"done": bool(res.ok), "reason": "" if res.ok else (res.error or "edit_failed"),
                    "path": path_s, "source": provenance, "quote": quote_line})
        if not res.ok:
            append_guard_log("provenance", {"event": "edit_failed", "path": path_s, "error": res.error})
        return out
    except Exception as e:  # hook 永不因此崩
        out["reason"] = f"exception: {type(e).__name__}: {e}"
        try:
            append_guard_log("provenance", {"event": "exception", "path": receipt.get("path") if receipt else "",
                                            "error": out["reason"]})
        except Exception:
            pass
        return out
