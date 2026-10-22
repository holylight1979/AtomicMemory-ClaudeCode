"""wg_data_file.py：動使用者資料檔要先宣告（規則 USER_DATA_FILE_NEEDS_DECLARATION）——收事實、找宣告行、留帳。

做什麼：PreToolUse 的 Edit／Write／NotebookEdit 要動的檔，與 Bash／PowerShell 指令的每個寫入目標（wg_core.write_paths_from_tool），
收四件事實——(a) 不是程式檔且副檔名在資料／設定清單、(b) 呼叫前已存在、(c) 不是本 session 新建的、(d) 本 session 使用者原話
沒點名——再從三管道（回覆文字／工具呼叫參數／thinking；重用 overview_hub 的 LOCATE_CHANNELS 與 assistant_text_after）找
「動資料檔｜<路徑>：<為什麼>」。判定在 wg_release_rules.data_file_verdict；這裡只收事實、出擋訊息、記 state、
寫 Logs/guard-data_file.jsonl（denied／declared／exempt／cap_released：同一個使用者回合同一個檔擋滿兩次就放行，
wg_core.deny_cap）。本 session 新建的檔記進 state created_files：Write 由
handlers/post_tool_use.py 呼叫 note_created；Bash／PowerShell 由這裡記下呼叫前不存在的目標、post_tool_use 呼叫
confirm_shell_created 確認存在後轉進去。
開關與清單：workflow/config.json 的 guard.data_file_ask（enabled 預設 True；extensions 給了就整份取代預設清單）。
.md 也算（README、病灶清單這類團隊共有文件）；_AIDocs／memory／.claude 底下的 .md 是系統文件，照舊不問（SYSTEM_DOC_DIRS）。
怎麼跑案例：python -X utf8 -m pytest -q hooks/verify/verify_data_file_ask.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (append_guard_log, deny_cap, read_state_status, transcripts_of, user_typed_prompts, user_typed_text,
                     write_state)
import wg_release_rules as _rr

GUARD = "data_file"
TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")
SHELL_TOOLS = ("Bash", "PowerShell")
DEFAULT_EXTENSIONS = [".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".csv", ".tsv", ".xml",
                      ".properties", ".plist", ".md"]
# 系統文件目錄（記憶卡片、AI 依規維護的專案文件、部位表）：裡面的 .md 照舊不當資料檔問；同目錄的 json 等設定照問
SYSTEM_DOC_DIRS = ("_aidocs", "memory", ".claude")


def _system_doc_md(path: str) -> bool:
    parts = [p.lower() for p in Path(str(path)).parts[:-1]]
    return _ext_of(path) == ".md" and any(d in parts for d in SYSTEM_DOC_DIRS)


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


def _transcript_user_entries(transcript_path: str) -> List[Tuple[int, str]]:
    """transcript 裡每一則使用者訊息 [(這一行結束的位元組位置, 清理後的字 user_typed_text)]；工具結果、isMeta、壓縮摘要不算。
    讀不到回空。"""
    if not transcript_path:
        return []
    try:
        with open(transcript_path, "rb") as f:
            lines = f.readlines()
    except OSError as e:      # 讀不到＝原話點名與後話作廢都判不到，要出聲
        sys.stderr.write(f"[Guardian:DataFileAsk] 讀不到 transcript（原話點名、宣告作廢這次判不到）：{type(e).__name__}: {e}\n")
        append_guard_log(GUARD, {"event": "transcript_error", "path": transcript_path, "error": f"{type(e).__name__}: {e}"})
        return []
    out: List[Tuple[int, str]] = []
    at = 0
    for raw in lines:
        at += len(raw)
        try:
            obj = json.loads(raw.decode("utf-8", "ignore"))
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
            out.append((at, typed))
    return out


def _user_entries(ctx: Dict[str, Any]) -> List[Tuple[int, str]]:
    """主 transcript 的使用者原話（_transcript_user_entries）；ctx 快取，整次呼叫只讀一次 transcript。"""
    if "user_entries" not in ctx:
        ctx["user_entries"] = _transcript_user_entries(ctx["main_tp"])
    return ctx["user_entries"]


def _size(path: str) -> int:
    try:
        return os.path.getsize(path) if path else 0
    except OSError:
        return 0


def _mention_at(ctx: Dict[str, Any], path: str) -> int:
    """主 transcript 裡最後一則提到這個檔（否定的也算）的使用者原話結束的位元組位置；沒有回 0。ctx 快取。"""
    return _latest_mention(ctx, path)[0]


def _latest_mention(ctx: Dict[str, Any], path: str) -> Tuple[int, str]:
    """主 transcript 裡最後一則提到這個檔的使用者原話 (結束位元組位置, 原話)；沒有回 (0, "")。ctx 快取。"""
    cache = ctx.setdefault("latest_mention", {})
    if path not in cache:
        cache[path] = next(((at, t) for at, t in reversed(_user_entries(ctx)) if _rr.prompt_mentions_file(t, path)), (0, ""))
    return cache[path]


def _void_stale_declaration(state: Dict[str, Any], path: str, ctx: Dict[str, Any], sid: str, tool_name: str) -> bool:
    """規則 DATA_FILE_DECL_VOIDED_BY_LATER_MENTION：帳上宣告過這個檔，但宣告之後使用者原話又提到它（不管有沒有否定）
    → 舊帳作廢（拿掉、留帳 declared_voided），這次照重新判。回有沒有改 state。"""
    key = _rr.canon_path(path)
    entry = (state.get("data_file_declared") or {}).get(key)
    if entry is None or _mention_at(ctx, path) <= int(entry.get("at") or 0):
        return False
    state["data_file_declared"].pop(key)
    append_guard_log(GUARD, {"session_id": sid, "tool": tool_name, "path": path, "event": "declared_voided",
                             "rule": "DATA_FILE_DECL_VOIDED_BY_LATER_MENTION", "line": entry.get("line", "")})
    return True


def session_prompts(state: Dict[str, Any], ctx: Dict[str, Any]) -> List[str]:
    """本 session 使用者原話：state 的近期清單與本回合清單（各截 500 字），加上 transcript 裡每一則使用者訊息（不截；
    與點名位置共用 ctx 那一份，不另讀 transcript）。"""
    kept = list(state.get("recent_user_prompts") or []) + list(state.get("turn_prompts") or [])
    return user_typed_prompts([str(p) for p in kept]) + [t for _, t in _user_entries(ctx)]


def declarations(transcript_path: str, since: int = 0) -> List[Tuple[str, str, str, str]]:
    """三管道（回覆文字／工具呼叫參數／thinking）從 since（位元組）之後的宣告行 → [(路徑, 為什麼, 那一行, 管道)]。
    工具呼叫參數只認 `#` 開頭的註解行（Bash／PowerShell 開頭的註解）；寫進檔案內容、替換文字裡的字樣不算宣告。"""
    from overview_hub import LOCATE_CHANNELS, assistant_text_after
    out: List[Tuple[str, str, str, str]] = []
    for ch in LOCATE_CHANNELS:
        text = assistant_text_after(transcript_path, since, ch)
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
    （算不出的 UNKNOWN 本閘不管，由 UNKNOWN_TARGET_LOGGED 放行留帳）。"""
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
        paths = [p for p in dict.fromkeys(_targets(tool_name, tool_input, str(input_data.get("cwd") or "")))
                 if _ext_of(p) in exts and not _system_doc_md(p)]
        return _judge(tool_name, paths, sid, input_data, config) if paths else None
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        sys.stderr.write(f"[Guardian:DataFileAsk] 閘內部錯誤（已擋）：{err}\n")
        append_guard_log(GUARD, {"event": "error", "session_id": sid, "tool": tool_name, "paths": paths, "error": err})
        return (f"[Guardian:DataFileAsk] 這次要寫的檔可能是資料／設定檔，但閘判不了它是不是使用者既有的資料（{err}），一律擋。"
                "先用 Read 查原因；拿不準要不要動就用 AskUserQuestion 問使用者（附推薦）。")


def _verdict_for(path: str, rel: str, state: Dict[str, Any], ctx: Dict[str, Any],
                 config: Optional[Dict[str, Any]]) -> Tuple[_rr.Verdict, str, str]:
    """一個寫入目標的四件事實＋宣告 → (Verdict, 對上宣告的管道；state＝本 session 宣告過；沒對上宣告為空, 點名那則原話的片段)。
    使用者點名先判、本 session 宣告過才判：點名是使用者要的，帳要記成點名豁免，不能被 AI 自己的舊宣告蓋過。
    原話與宣告行整次呼叫只讀一次 transcript（ctx 快取）。"""
    from wg_need_goal import writes_code
    key = _rr.canon_path(path)
    facts = {"code": writes_code(path, config), "ext": _ext_of(path), "ext_listed": True, "existed": os.path.exists(path),
             "created": key in (state.get("created_files") or [])}
    if facts["code"] or not facts["existed"] or facts["created"]:
        return _rr.data_file_verdict(path, rel, facts, []), "", ""
    if "prompts" not in ctx:
        ctx["prompts"] = session_prompts(state, ctx)
    facts.update(named=_rr.prompt_names_file(ctx["prompts"], path), prompts=len(ctx["prompts"]))
    latest = _latest_mention(ctx, path)[1]
    if facts["named"] and latest and not _rr.prompt_names_file([latest], path):
        facts["named"] = None       # 最後一則提到它的原話只有否定：早先的點名被後話推翻（NEGATED_MENTION_IS_NOT_NAMING）
    if facts["named"]:
        return _rr.data_file_verdict(path, rel, facts, []), "", str(facts["named"]).strip()
    if key in (state.get("data_file_declared") or {}):
        return _rr.Verdict("USER_DATA_FILE_NEEDS_DECLARATION", False, f"本 session 宣告過 {rel}"), "state", ""
    # 宣告只認最後一則提到這個檔的使用者原話之後寫的（DATA_FILE_DECL_VOIDED_BY_LATER_MENTION）；子代理檔沒有使用者原話、
    # 位置跟主檔對不起來：使用者提過這個檔就不認子代理檔的宣告（分不出寫在後話之前或之後），沒提過才從頭找
    since = _mention_at(ctx, path)
    if ("decls", since) not in ctx:
        tps = [ctx["main_tp"]] if since else ctx["decl_tps"]
        ctx[("decls", since)] = ([d for tp in tps for d in declarations(tp, since if tp == ctx["main_tp"] else 0)]
                                 + _command_decls(ctx["cmd"]))
    decls = ctx[("decls", since)]
    v = _rr.data_file_verdict(path, rel, facts, [d[:3] for d in decls])
    via = next((d[3] for d in decls if v.evidence and not v.owed and d[2] == v.evidence[0]), "")
    return v, via, ""


def _judge(tool_name: str, paths: List[str], sid: str, input_data: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Optional[str]:
    cwd = str(input_data.get("cwd") or "")
    state, status = read_state_status(sid) if sid else (None, "missing")
    if status == "error":
        raise RuntimeError(f"state 檔讀不到（workflow/state-{sid[:8]}….json），判不了是不是本 session 建的")
    state = state or {}
    main_tp, decl_tps = transcripts_of(str(input_data.get("transcript_path") or ""), str(input_data.get("agent_id") or ""))
    ctx: Dict[str, Any] = {"main_tp": main_tp, "decl_tps": decl_tps,
                           "cmd": str((input_data.get("tool_input") or {}).get("command") or "") if tool_name in SHELL_TOOLS else ""}
    owed: Dict[str, Tuple[str, str, _rr.Verdict]] = {}
    pending: List[str] = []
    changed = False
    for path in paths:
        rel = _rel(path, cwd)
        changed = _void_stale_declaration(state, path, ctx, sid, tool_name) or changed
        v, via, quote = _verdict_for(path, rel, state, ctx, config)
        if v.owed:
            owed[_rr.canon_path(path)] = (path, rel, v)
            continue
        append_guard_log(GUARD, {"session_id": sid, "tool": tool_name, "path": path, "event": "declared" if via else "exempt",
                                 "why": v.why, **({"via": via} if via else {}), **({"quote": quote} if quote else {})})
        if via and via != "state":       # 有宣告行對上：記 state，同 session 同檔不再擋；at＝這時主 transcript 寫到哪（之後的原話會作廢它）
            state.setdefault("data_file_declared", {})[_rr.canon_path(path)] = {"line": v.evidence[0], "via": via,
                                                                                 "at": _size(main_tp)}
            changed = True
        if tool_name in SHELL_TOOLS and not os.path.exists(path):
            pending.append(path)
    # 擋次上限（wg_core.deny_cap）：同一個使用者回合同一個檔擋滿兩次就放行、留帳 cap_released；沒有 state 可記照擋
    denied, released = deny_cap(state if status == "ok" else None, GUARD, list(owed))
    changed = changed or bool(owed and status == "ok")
    for key in owed:
        path, _, v = owed[key]
        if key in denied or key in released:
            append_guard_log(GUARD, {"session_id": sid, "tool": tool_name, "path": path,
                                     "event": "denied" if key in denied else "cap_released", "why": v.why})
    if pending and not denied:           # 指令會建出來的檔：PostToolUse 確認存在後記成本 session 建（confirm_shell_created）
        state.setdefault("data_file_pending_new", {})[str(input_data.get("tool_use_id") or "")] = pending
        changed = True
    if changed and status == "ok":
        write_state(sid, state)
    if not denied:
        return None
    hits = [owed[k] for k in denied]
    return ("[Guardian:DataFileAsk] 要改使用者既有的資料檔／設定檔，先宣告一行再改：宣告行要比這次工具呼叫早一則訊息送出"
            "（跟工具呼叫同一則送出的文字，這裡還看不到），或寫成 Bash／PowerShell 指令開頭的 `#` 註解。"
            "拿不準要不要動就先問使用者。一條指令寫好幾個資料檔，每個都要各自宣告（留帳給健檢抽查）。\n"
            + "\n".join(_rr.format_hit("df", v) for _, _, v in hits) + "\n"
            + "\n".join(_rr.data_file_hint(rel) for _, rel, _ in hits))
