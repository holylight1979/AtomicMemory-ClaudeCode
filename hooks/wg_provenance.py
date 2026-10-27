"""wg_provenance — PostToolUse 對剛寫入的 atom 自動補來源（Source／Quote）。

做什麼：atom_write 成功（receipt op=create|replace）後，從 hook input 與 state 取
「這張卡片是哪個 session、哪則使用者訊息觸發的」，用 lib.atom_io.edit_metadata 補
`- Source: session:<sid8>#<uuid8> <日期>` 與 `- Quote: 「使用者原話」`。不靠模型記得填。

規則：
- 檔內已有 `- Quote:` → 不動（呼叫者自填或已補過）。
- 呼叫者已給非空 Source（例：會議轉錄的逐字稿路徑）→ 只補 Quote。
- Quote 取 state["turn_prompts"][-1]（本回合最後一則使用者原話，≤500 字）消毒後 ≤200 字；
  空字串不寫。uuid 從 transcript 尾端最後一則真人訊息取，取不到只寫 session＋日期。
- 規則 QUOTE_FROM_USER_OPENED_TURN：Quote 只取「寫卡那一回合是使用者本人打字開的」那回合的原話（回填工具同一條，not_user_turn）。
  - 主 session：state["turn_typed"] 是 False（同伴訊息、背景通知開的續跑回合）→ 不填。turn_prompts 在續跑回合沿用前一個
    使用者回合的原話（口令閘要它跨過背景等待），那不是這張卡的觸發句。
  - 子代理（hook input 帶 agent_id）：不看 state——主 session 現在的回合不一定是派它的那一回合（背景子代理寫卡時，使用者
    可能已經開了下一回合）；也不拿子代理 transcript 裡的 user 訊息（那是主 session 的 AI 寫給它的任務）。改看派它的那一回合：
    子代理檔第一筆的 promptId 對到主檔開那一回合的紀錄（_subagent_opener），是真人訊息（lib/provenance.is_human_record）才取它
    的原話，Source 的 uuid 也指它；是同伴訊息、背景通知、對不到 → 不填。
- 那則原話是開工句（lib/harness_text.is_kickoff_prompt：派工樣板整則對上，或以「你是…工作 session」開場）→ 不填 Quote：
  開工句是派給這個 session 的指示，不是哪張卡片的使用者原話。貼上的內容（`<pasted_content>`）不是本人打的字，
  lib/provenance.sanitize_quote 會剔掉。Source（session 指標）照補。原卡已有 Quote 一律不動（上面第一條）。
- 任何失敗只記 Logs/guard-provenance.jsonl，不阻斷 hook。

入口：autofill_from_receipt(receipt, input_data, state) → dict（結果摘要，供測試與日誌）。
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from wg_core import CLAUDE_DIR, append_guard_log, transcripts_of

_QUOTE_LINE_RE = re.compile(r"^- Quote:\s*\S", re.MULTILINE)
_SOURCE_LINE_RE = re.compile(r"^- Source:\s*(\S.*)$", re.MULTILINE)


def _is_root_layer(path: Path) -> bool:
    """卡片落在根層（~/.claude 底下：全域、本人跨專案、根層專用）。"""
    try:
        p, home = path.resolve(), CLAUDE_DIR.resolve()
    except OSError:
        return False
    return home in p.parents


def _last_turn_prompt(state: Dict[str, Any]) -> str:
    """本回合最後一則使用者本人打的字（user_typed_text，保留換行）；舊 state 裡混進的通知、其他 session 的訊息不算。"""
    from wg_core import user_typed_text
    prompts = state.get("turn_prompts") or []
    if not isinstance(prompts, list):
        return ""
    for p in reversed(prompts):
        typed = user_typed_text(p, keep_lines=True) if isinstance(p, str) else ""
        if typed:
            return typed
    return ""


def _subagent_opener(transcript_path: str, agent_id: str) -> Optional[Dict[str, Any]]:
    """子代理是在主 session 哪一回合派出的：子代理檔第一筆紀錄（派工 prompt）的 promptId，對主檔裡第一筆同 promptId 的 user 紀錄
    ＝開那一回合的訊息（使用者、同伴訊息、背景通知…；實查本機 237 份子代理檔全對得上）。hook 給主檔或子代理檔都行；讀不到、對不上 → None。"""
    main, files = transcripts_of(transcript_path, agent_id)
    if not main or len(files) < 2:
        return None
    try:
        with open(files[1], encoding="utf-8", errors="replace") as fh:
            first = json.loads(fh.readline() or "null")
        pid = first.get("promptId") if isinstance(first, dict) else None
        if not isinstance(pid, str) or not pid:
            return None
        with open(main, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if pid not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and rec.get("promptId") == pid and rec.get("type") == "user":
                    return rec
    except (OSError, ValueError):
        return None
    return None


def _turn_quote(input_data: Dict[str, Any], state: Dict[str, Any]) -> Tuple[str, Optional[str], str]:
    """規則 QUOTE_FROM_USER_OPENED_TURN（見模組說明）→ (原話（使用者本人打的字，可能空）, Source 要指的真人訊息 uuid 或 None, 不填的原因)。"""
    from wg_core import user_typed_text
    agent_id = str(input_data.get("agent_id") or "")
    if not agent_id:
        if state.get("turn_typed") is False:
            return "", None, "not_user_turn"
        return _last_turn_prompt(state), None, ""
    from lib.provenance import is_human_record, record_text
    opener = _subagent_opener(str(input_data.get("transcript_path") or ""), agent_id)
    if opener is None or not is_human_record(opener):
        return "", None, "not_user_turn"
    return user_typed_text(record_text(opener), keep_lines=True), str(opener.get("uuid") or "") or None, ""


def _last_human_uuid(transcript_path: str) -> Optional[str]:
    if not transcript_path:
        return None
    p = Path(transcript_path)
    if not p.is_file():
        return None
    try:
        import sys
        lib_root = str(Path(__file__).resolve().parents[1])   # 程式碼用本檔位置，CLAUDE_DIR 只定位資料
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
        lib_root = str(Path(__file__).resolve().parents[1])   # 程式碼用本檔位置，CLAUDE_DIR 只定位資料
        if lib_root not in sys.path:
            sys.path.insert(0, lib_root)
        from lib.atom_io import edit_metadata
        from lib.harness_text import is_kickoff_prompt
        from lib.provenance import format_quote, format_source_session, sanitize_quote, usable_quote

        session_id = str(input_data.get("session_id") or state.get("session", {}).get("id") or "")
        quote_raw, opener_uuid, skipped = _turn_quote(input_data, state)
        if skipped:
            out["quote_skipped"] = skipped
        if (input_data.get("tool_input") or {}).get("quote") == "":
            out["quote_skipped"] = "caller_cleared"      # 呼叫者明傳 quote="" 是要清掉，不拿原話補回
            quote_raw = ""
        if quote_raw and is_kickoff_prompt(quote_raw):
            out["quote_skipped"] = "kickoff"
            quote_raw = ""
        if _is_root_layer(path):
            # 根層卡片不帶專案名與專案路徑；原話照抄會把它們帶進來
            from lib.realm_gate import anonymize_projects
            quote_raw = anonymize_projects(quote_raw)
        quote_clean = usable_quote(quote_raw)
        if not quote_clean and sanitize_quote(quote_raw):
            out["quote_skipped"] = "too_short"           # 「A」這類一兩個字的回覆說不出卡從哪來
        elif not quote_clean and quote_raw.strip():
            out["quote_skipped"] = "pasted"              # 整則是貼上的內容（別人寫的開工句、派工、日誌）：不是本人打的字
        quote_line = format_quote(quote_clean) if quote_clean else None

        sm = _SOURCE_LINE_RE.search(text)
        has_source = bool(sm and sm.group(1).strip())
        provenance = None
        if not has_source and session_id:
            # uuid 只在主 session 的 transcript 找（子代理的 hook 給哪一份都換回主檔：子代理檔裡的 user 訊息不是使用者的）
            main_transcript = transcripts_of(str(input_data.get("transcript_path") or ""),
                                             str(input_data.get("agent_id") or ""))[0]
            uuid = opener_uuid or _last_human_uuid(main_transcript)
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
