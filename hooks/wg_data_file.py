"""wg_data_file.py：動使用者資料檔要先宣告（規則 USER_DATA_FILE_NEEDS_DECLARATION）——收事實、找宣告行、留帳。

做什麼：PreToolUse 的 Edit／Write／NotebookEdit 要動的檔，收四件事實——(a) 不是程式檔且副檔名在資料／設定清單、
(b) 呼叫前已存在、(c) 不是本 session Write 新建的、(d) 本 session 使用者原話沒點名——再從三管道（回覆文字／工具呼叫參數／
thinking；重用 overview_hub 的 LOCATE_CHANNELS 與 assistant_text_after）找「動資料檔｜<路徑>：<為什麼>」。
判定在 wg_release_rules.data_file_verdict；這裡只收事實、出擋訊息、記 state、寫 Logs/guard-data_file.jsonl
（denied／declared／exempt）。本 session Write 新建的檔由 handlers/post_tool_use.py 呼叫 note_created 記進 state created_files。
開關與清單：workflow/config.json 的 guard.data_file_ask（enabled 預設 True；extensions 給了就整份取代預設清單）。
怎麼跑案例：python -X utf8 -m pytest -q hooks/verify/verify_data_file_ask.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import append_guard_log, read_state_status, user_typed_prompts, user_typed_text, write_state
import wg_release_rules as _rr

GUARD = "data_file"
TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")
DEFAULT_EXTENSIONS = [".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".csv", ".tsv", ".xml",
                      ".properties", ".plist"]
CREATED_CAP = 200


def cfg_of(config: Optional[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """(開著沒, 資料／設定副檔名清單)。清單只決定程式要不要把它當資料檔問，該不該改仍是 AI 判。"""
    sec = ((config or {}).get("guard") or {}).get("data_file_ask") or {}
    exts = sec.get("extensions")
    exts = [str(e).lower() for e in exts] if isinstance(exts, list) else list(DEFAULT_EXTENSIONS)
    return sec.get("enabled", True) is not False, exts


def _ext_of(path: str) -> str:
    """副檔名（小寫）；`.env` 這種整個檔名就是點開頭的，副檔名就是檔名本身。"""
    name = Path(str(path)).name.lower()
    suffix = Path(name).suffix
    return suffix or (name if name.startswith(".") else "")


def note_created(state: Dict[str, Any], tool_name: str, file_path: str, tool_response: Any) -> bool:
    """PostToolUse：Write 成功且呼叫前檔不存在（Claude Code 的 Write 結果 type="create"）→ state created_files 加 canon_path。
    結果沒有 type（判不出是不是新建）不記：之後改它會被問一次，寧可多問。回有沒有改 state。"""
    if tool_name != "Write" or not file_path or not isinstance(tool_response, dict) or tool_response.get("type") != "create":
        return False
    key = _rr.canon_path(file_path)
    lst = state.setdefault("created_files", [])
    if key in lst:
        return False
    lst.append(key)
    del lst[:-CREATED_CAP]
    return True


def _transcript_user_texts(transcript_path: str) -> List[str]:
    """transcript 裡每一則使用者訊息清理後的字（user_typed_text）；工具結果、isMeta、壓縮摘要不算。讀不到回空。"""
    if not transcript_path:
        return []
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except OSError:
        return []
    out: List[str] = []
    for raw in lines:
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if (not isinstance(obj, dict) or obj.get("type") != "user" or obj.get("isMeta") or obj.get("isCompactSummary")
                or "toolUseResult" in obj):
            continue
        content = (obj.get("message") or {}).get("content")
        if isinstance(content, list):
            content = "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
        typed = user_typed_text(content) if isinstance(content, str) else ""
        if typed:
            out.append(typed)
    return out


def session_prompts(state: Dict[str, Any], transcript_path: str) -> List[str]:
    """本 session 使用者原話：state 的近期清單與本回合清單（各截 500 字），加上 transcript 裡每一則使用者訊息（不截）。"""
    kept = list(state.get("recent_user_prompts") or []) + list(state.get("turn_prompts") or [])
    return user_typed_prompts([str(p) for p in kept]) + _transcript_user_texts(transcript_path)


def declarations(transcript_path: str) -> List[Tuple[str, str, str, str]]:
    """三管道（回覆文字／工具呼叫參數／thinking）整個 session 的宣告行 → [(路徑, 為什麼, 那一行, 管道)]。"""
    from overview_hub import LOCATE_CHANNELS, assistant_text_after
    out: List[Tuple[str, str, str, str]] = []
    for ch in LOCATE_CHANNELS:
        out.extend(d + (ch,) for d in _rr.parse_data_file_decls(assistant_text_after(transcript_path, 0, ch)))
    return out


def _rel(path: str, cwd: str) -> str:
    """相對 cwd 的路徑（正斜線）；不在 cwd 底下就原樣。"""
    try:
        rel = os.path.relpath(path, cwd) if cwd else path
    except ValueError:
        return path
    return path if rel.startswith("..") else rel.replace("\\", "/")


def gate(tool_name: str, tool_input: Dict[str, Any], input_data: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Optional[str]:
    """PreToolUse：回擋訊息或 None。閘自己出錯（state 讀壞、例外）＝判不了 → 擋並寫 stderr 與守門紀錄 error。"""
    if tool_name not in TOOLS:
        return None
    path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
    enabled, exts = cfg_of(config)
    ext = _ext_of(path)
    if not enabled or not path or ext not in exts:
        return None
    sid = str(input_data.get("session_id") or "")
    try:
        return _judge(tool_name, path, ext, sid, input_data, config)
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        sys.stderr.write(f"[Guardian:DataFileAsk] 閘內部錯誤（已擋）：{err}\n")
        append_guard_log(GUARD, {"event": "error", "session_id": sid, "tool": tool_name, "path": path, "error": err})
        return (f"[Guardian:DataFileAsk] 要改的 {path} 是資料／設定檔，但閘判不了它是不是使用者既有的資料（{err}），一律擋。"
                "先用 Read 查原因；拿不準要不要動就用 AskUserQuestion 問使用者（附推薦）。")


def _judge(tool_name: str, path: str, ext: str, sid: str, input_data: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Optional[str]:
    from wg_need_goal import writes_code
    cwd = str(input_data.get("cwd") or "")
    rel = _rel(path, cwd)
    tp = str(input_data.get("transcript_path") or "")
    log = {"session_id": sid, "tool": tool_name, "path": path}
    state, status = read_state_status(sid) if sid else (None, "missing")
    if status == "error":
        raise RuntimeError(f"state 檔讀不到（workflow/state-{sid[:8]}….json），判不了是不是本 session 建的")
    state = state or {}
    key = _rr.canon_path(path)
    facts = {"code": writes_code(path, config), "ext": ext, "ext_listed": True, "existed": os.path.exists(path),
             "created": key in (state.get("created_files") or [])}
    decls: List[Tuple[str, str, str, str]] = []
    if not facts["code"] and facts["existed"] and not facts["created"]:     # (a)(b)(c) 成立才花力氣讀 transcript
        if key in (state.get("data_file_declared") or {}):
            append_guard_log(GUARD, {**log, "event": "declared", "via": "state"})
            return None
        prompts = session_prompts(state, tp)
        facts.update(named=_rr.prompt_names_file(prompts, path), prompts=len(prompts))
        if not facts["named"]:
            decls = declarations(tp)
    v = _rr.data_file_verdict(path, rel, facts, [d[:3] for d in decls])
    if v.owed:
        append_guard_log(GUARD, {**log, "event": "denied", "why": v.why})
        return ("[Guardian:DataFileAsk] 要改使用者既有的資料檔／設定檔：先問使用者，或先宣告一行再改（留帳給健檢抽查）。\n"
                + _rr.format_hit("df", v) + "\n" + _rr.data_file_hint(rel))
    if v.evidence:      # 有宣告行對上：記 state，同 session 同檔不再擋
        via = next((d[3] for d in decls if d[2] == v.evidence[0]), "")
        append_guard_log(GUARD, {**log, "event": "declared", "via": via, "line": v.evidence[0]})
        if status == "ok":
            state.setdefault("data_file_declared", {})[key] = {"line": v.evidence[0], "via": via}
            write_state(sid, state)
        return None
    append_guard_log(GUARD, {**log, "event": "exempt", "why": v.why})
    return None
