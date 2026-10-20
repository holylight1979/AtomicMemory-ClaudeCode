"""wg_data_file.py：動使用者資料檔要先宣告（規則 USER_DATA_FILE_NEEDS_DECLARATION）——收事實、找宣告行、留帳。

做什麼：PreToolUse 的 Edit／Write／NotebookEdit 要動的檔，與 Bash／PowerShell 指令的每個寫入目標（wg_core.write_paths_from_tool），
收四件事實——(a) 不是程式檔且副檔名在資料／設定清單、(b) 呼叫前已存在、(c) 不是本 session 新建的、(d) 本 session 使用者原話
沒點名——再從三管道（回覆文字／工具呼叫參數／thinking；重用 overview_hub 的 LOCATE_CHANNELS 與 assistant_text_after）找
「動資料檔｜<路徑>：<為什麼>」。判定在 wg_release_rules.data_file_verdict；這裡只收事實、出擋訊息、記 state、
寫 Logs/guard-data_file.jsonl（denied／declared／exempt）。本 session 新建的檔記進 state created_files：Write 由
handlers/post_tool_use.py 呼叫 note_created；Bash／PowerShell 由這裡記下呼叫前不存在的目標、post_tool_use 呼叫
confirm_shell_created 確認存在後轉進去。
開關與清單：workflow/config.json 的 guard.data_file_ask（enabled 預設 True；extensions 給了就整份取代預設清單）。
怎麼跑案例：python -X utf8 -m pytest -q hooks/verify/verify_data_file_ask.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import append_guard_log, read_state_status, transcripts_of, user_typed_prompts, user_typed_text, write_state
import wg_release_rules as _rr

GUARD = "data_file"
TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")
SHELL_TOOLS = ("Bash", "PowerShell")
DEFAULT_EXTENSIONS = [".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".csv", ".tsv", ".xml",
                      ".properties", ".plist"]


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
    整個 session 都留著不淘汰：淘汰掉就會把 AI 自己建的檔當成使用者既有。結果沒有 type（判不出是不是新建）不記：
    之後改它會被問一次，寧可多問。回有沒有改 state。"""
    if tool_name != "Write" or not file_path or not isinstance(tool_response, dict) or tool_response.get("type") != "create":
        return False
    key = _rr.canon_path(file_path)
    lst = state.setdefault("created_files", [])
    if key in lst:
        return False
    lst.append(key)
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
    """三管道（回覆文字／工具呼叫參數／thinking）整個 session 的宣告行 → [(路徑, 為什麼, 那一行, 管道)]。
    工具呼叫參數只認 `#` 開頭的註解行（Bash／PowerShell 開頭的註解）；寫進檔案內容、替換文字裡的字樣不算宣告。"""
    from overview_hub import LOCATE_CHANNELS, assistant_text_after
    out: List[Tuple[str, str, str, str]] = []
    for ch in LOCATE_CHANNELS:
        text = assistant_text_after(transcript_path, 0, ch)
        if ch == "tool_input":
            text = "\n".join(ln for ln in text.splitlines() if ln.lstrip().startswith("#"))
        out.extend(d + (ch,) for d in _rr.parse_data_file_decls(text))
    return out


def _command_decls(command: str) -> List[Tuple[str, str, str, str]]:
    """這次 Bash／PowerShell 指令自己開頭的 `#` 註解行裡的宣告：PreToolUse 當下這則工具呼叫還不一定寫進 transcript。"""
    text = "\n".join(ln for ln in str(command or "").splitlines() if ln.lstrip().startswith("#"))
    return [d + ("tool_input",) for d in _rr.parse_data_file_decls(text)]


def _rel(path: str, cwd: str) -> str:
    """相對 cwd 的路徑（正斜線）；不在 cwd 底下就原樣。"""
    try:
        rel = os.path.relpath(path, cwd) if cwd else path
    except ValueError:
        return path
    return path if rel.startswith("..") else rel.replace("\\", "/")


def confirm_shell_created(state: Dict[str, Any], tool_use_id: str) -> bool:
    """PostToolUse：PreToolUse 記下這次 Bash／PowerShell 要寫、呼叫前還不存在的資料檔（data_file_pending_new[tool_use_id]），
    現在真的存在了 → 轉進 created_files（事實 (c)）。PostToolUse 當下檔已寫完、分不出新建或覆寫，所以靠呼叫前那一眼。
    回有沒有改 state。"""
    paths = (state.get("data_file_pending_new") or {}).pop(tool_use_id, None)
    if paths is None:
        return False
    created = state.setdefault("created_files", [])
    for p in paths:
        key = _rr.canon_path(p)
        if os.path.exists(p) and key not in created:
            created.append(key)
    return True


def _targets(tool_name: str, tool_input: Dict[str, Any], cwd: str) -> List[str]:
    """這次工具呼叫要寫的檔：Edit 類取 file_path；Bash／PowerShell 取 wg_core.write_paths_from_tool 算得出的每個目標
    （算不出的 UNKNOWN 由 OverviewHub 擋，本閘不管）。"""
    if tool_name in TOOLS:
        p = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        return [p] if p else []
    from wg_core import write_paths_from_tool
    return [p for p in write_paths_from_tool(tool_name, tool_input, cwd or None) if not p.startswith("UNKNOWN:")]


def gate(tool_name: str, tool_input: Dict[str, Any], input_data: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Optional[str]:
    """PreToolUse：回擋訊息或 None。一條指令寫好幾個資料檔，每個都要對到宣告或各自豁免，沒對到的全列出來。
    閘自己出錯（state 讀壞、例外）＝判不了 → 擋並寫 stderr 與守門紀錄 error。"""
    enabled, exts = cfg_of(config)
    if not enabled or tool_name not in TOOLS + SHELL_TOOLS:
        return None
    sid = str(input_data.get("session_id") or "")
    paths: List[str] = []
    try:
        paths = [p for p in dict.fromkeys(_targets(tool_name, tool_input, str(input_data.get("cwd") or ""))) if _ext_of(p) in exts]
        return _judge(tool_name, paths, sid, input_data, config) if paths else None
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        sys.stderr.write(f"[Guardian:DataFileAsk] 閘內部錯誤（已擋）：{err}\n")
        append_guard_log(GUARD, {"event": "error", "session_id": sid, "tool": tool_name, "paths": paths, "error": err})
        return (f"[Guardian:DataFileAsk] 這次要寫的檔可能是資料／設定檔，但閘判不了它是不是使用者既有的資料（{err}），一律擋。"
                "先用 Read 查原因；拿不準要不要動就用 AskUserQuestion 問使用者（附推薦）。")


def _verdict_for(path: str, rel: str, state: Dict[str, Any], ctx: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Tuple[_rr.Verdict, str]:
    """一個寫入目標的四件事實＋宣告 → (Verdict, 對上宣告的管道；state＝本 session 宣告過；沒對上宣告為空)。
    原話與宣告行整次呼叫只讀一次 transcript（ctx 快取）。"""
    from wg_need_goal import writes_code
    key = _rr.canon_path(path)
    facts = {"code": writes_code(path, config), "ext": _ext_of(path), "ext_listed": True, "existed": os.path.exists(path),
             "created": key in (state.get("created_files") or [])}
    if facts["code"] or not facts["existed"] or facts["created"]:
        return _rr.data_file_verdict(path, rel, facts, []), ""
    if key in (state.get("data_file_declared") or {}):
        return _rr.Verdict("USER_DATA_FILE_NEEDS_DECLARATION", False, f"本 session 宣告過 {rel}"), "state"
    if "prompts" not in ctx:
        ctx["prompts"] = session_prompts(state, ctx["main_tp"])
    facts.update(named=_rr.prompt_names_file(ctx["prompts"], path), prompts=len(ctx["prompts"]))
    if facts["named"]:
        return _rr.data_file_verdict(path, rel, facts, []), ""
    if "decls" not in ctx:
        ctx["decls"] = [d for tp in ctx["decl_tps"] for d in declarations(tp)] + _command_decls(ctx["cmd"])
    v = _rr.data_file_verdict(path, rel, facts, [d[:3] for d in ctx["decls"]])
    via = next((d[3] for d in ctx["decls"] if v.evidence and not v.owed and d[2] == v.evidence[0]), "")
    return v, via


def _judge(tool_name: str, paths: List[str], sid: str, input_data: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Optional[str]:
    cwd = str(input_data.get("cwd") or "")
    state, status = read_state_status(sid) if sid else (None, "missing")
    if status == "error":
        raise RuntimeError(f"state 檔讀不到（workflow/state-{sid[:8]}….json），判不了是不是本 session 建的")
    state = state or {}
    main_tp, decl_tps = transcripts_of(str(input_data.get("transcript_path") or ""), str(input_data.get("agent_id") or ""))
    ctx: Dict[str, Any] = {"main_tp": main_tp, "decl_tps": decl_tps,
                           "cmd": str((input_data.get("tool_input") or {}).get("command") or "") if tool_name in SHELL_TOOLS else ""}
    owed: List[Tuple[str, _rr.Verdict]] = []
    pending: List[str] = []
    changed = False
    for path in paths:
        rel = _rel(path, cwd)
        v, via = _verdict_for(path, rel, state, ctx, config)
        if v.owed:
            event = "denied"
        elif via:
            event = "declared"
        else:
            event = "exempt"
        append_guard_log(GUARD, {"session_id": sid, "tool": tool_name, "path": path, "event": event, "why": v.why,
                                 **({"via": via} if via else {})})
        if v.owed:
            owed.append((rel, v))
            continue
        if via and via != "state":       # 有宣告行對上：記 state，同 session 同檔不再擋
            state.setdefault("data_file_declared", {})[_rr.canon_path(path)] = {"line": v.evidence[0], "via": via}
            changed = True
        if tool_name in SHELL_TOOLS and not os.path.exists(path):
            pending.append(path)
    if pending and not owed:             # 指令會建出來的檔：PostToolUse 確認存在後記成本 session 建（confirm_shell_created）
        state.setdefault("data_file_pending_new", {})[str(input_data.get("tool_use_id") or "")] = pending
        changed = True
    if changed and status == "ok":
        write_state(sid, state)
    if not owed:
        return None
    return ("[Guardian:DataFileAsk] 要改使用者既有的資料檔／設定檔：先問使用者，或先宣告一行再改（留帳給健檢抽查）。"
            "一條指令寫好幾個資料檔，每個都要各自宣告。\n"
            + "\n".join(_rr.format_hit("df", v) for _, v in owed) + "\n"
            + "\n".join(_rr.data_file_hint(rel) for rel, _ in owed))
