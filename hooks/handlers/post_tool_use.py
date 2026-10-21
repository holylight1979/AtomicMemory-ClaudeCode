"""
handlers/post_tool_use.py — PostToolUse hook handler

追蹤 modified_files / vcs_queries（accessed_files 由 Stop 端從 transcript 尾段
一次回收，matcher 不含 Read——省去每次讀檔一個 hook 行程）；
偵測測試失敗、_CHANGELOG 自動 roll、staging 命名、路徑強制、docdrift、hot cache mid-turn 注入。
"""

import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (
    _ensure_state, _now_iso, write_state, output_json, output_nothing,
    _atom_debug_error, append_guard_log, WORKFLOW_DIR,
)
from wg_episodic import _check_output_quality
from wg_extraction import _is_lease_valid  # noqa: F401
from wg_hook_timing import lap as _hook_lap
from wg_evasion import (
    is_test_command, detect_test_failure, tail_lines, aec_severity, crosscheck_aec_severity,
    _aec_blank, aec_pending_items,
)
from wg_atoms import _trigger_incremental_index
from wg_extraction import is_plan_filename
from wg_harvest import (
    parse_receipt, record_atom_op, apply_report, append_ledger, validated_this_turn,
    is_error_response,
)
from wg_verify_ledger import (
    compile_sentinel_rules, parse_sentinels, response_text, exit_code_of, vcs_snapshot,
    append_verify_ledger, record_receipt, receipts_of, spec_paths_of, modified_this_turn, agent_receipt_key,
    aec_evidence_missing, aec_evidence_autofill, aec_followups_missing, next_event_seq, has_cd, env_snapshot,
    commit_snapshot, reconcile_cfg, head_new_code, copied_glob_source, _git_root_of, reverted_code_files, is_code_file, ledger_path,
    small_content_sha,
)
from wg_release_rules import (canon_path, in_user_turn, deliberate_red_verdict, green_clears_red, green_ran_cases_verdict,
                              red_case_facts, red_case_names, retry_round_verdict, same_test_run)
try:
    # track-a1 寫的 Bash／PowerShell 改檔目標擷取；沒合併前退回只記 Edit／Write／MultiEdit／NotebookEdit 目標
    from wg_core import write_paths_from_tool as _write_paths_from_tool
except ImportError:
    _write_paths_from_tool = None
try:
    from wg_vcs_sync import spawn_vcs_sync  # 收割 validated 後背景 commit/push 記憶目錄
except ImportError:
    spawn_vcs_sync = None
from handlers import aec_ledger
import wg_data_file  # T2.16 動使用者資料檔要先宣告：記本 session 新建的檔
from handlers._shared import (
    _hud_alive,
    _is_ephemeral_path,
    WISDOM_AVAILABLE, wisdom_track_retry,
    DOCDRIFT_AVAILABLE, check_source_drift, resolve_doc_update, prune_committed_entries,
    entry_note,
)
import wg_oldtest


_CHANGELOG_TABLE_DATA_RE = re.compile(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|")

# git/svn commit 指令偵測（供 ScanReport 閘「本 turn 已 commit → 豁免收尾檢核」）。
# 限 commit 出現在首個管線/串接段之前，故 `git log | grep commit` 不誤中。
_VCS_COMMIT_RE = re.compile(r"\b(?:git|svn)\b[^|&;\n]*?\bcommit\b", re.IGNORECASE)

# 從 sub-agent prompt 的注入 header 回推 atom 清單。
#   header 形如：[WG:SubagentMemory] …… atoms=a,b,c
_SUBAGENT_ATOMS_RE = re.compile(r"\[WG:SubagentMemory\][^\n]*?atoms=([^\n]+)")
_SUBAGENT_INJ_CAP = 50          # state 中保留最近 N 筆 spawn 記錄
_SUBAGENT_SUMMARY_CAP = 400     # agent 輸出摘要字元上限


def _extract_agent_output_summary(tool_response: Dict[str, Any], cap: int = _SUBAGENT_SUMMARY_CAP) -> str:
    """從 Agent tool_response.content 擷取文字摘要。content 為 [{type,text}, ...]。"""
    content = tool_response.get("content", "")
    text = ""
    if isinstance(content, list):
        parts = []
        for blk in content:
            if isinstance(blk, dict) and blk.get("type") == "text":
                parts.append(str(blk.get("text", "")))
            elif isinstance(blk, str):
                parts.append(blk)
        text = "\n".join(parts)
    elif isinstance(content, str):
        text = content
    text = text.strip().replace("\r", " ")
    return text[:cap]


def _record_subagent_injection(state: Dict[str, Any], input_data: Dict[str, Any]) -> bool:
    """記錄某次 sub-agent spawn 注入了哪些 atom + 輸出摘要。回 True 表示有寫入。

    無狀態回推：注入清單來自 tool_response.prompt（注入後完整 prompt）的 blob marker；
    無 marker（本次未注入）→ 不記錄、回 False。
    """
    tr = input_data.get("tool_response", {})
    if not isinstance(tr, dict):
        return False
    prompt = tr.get("prompt", "") or input_data.get("tool_input", {}).get("prompt", "") or ""
    m = _SUBAGENT_ATOMS_RE.search(prompt)
    if not m:
        return False
    atoms = [a.strip() for a in m.group(1).split(",") if a.strip()]
    if not atoms:
        return False

    rec = {
        "agent_id": tr.get("agentId", "") or "",
        "agent_type": tr.get("agentType", "") or "",
        "atoms": atoms,
        "status": tr.get("status", "") or "",
        "output_summary": _extract_agent_output_summary(tr),
        "tool_use_id": input_data.get("tool_use_id", "") or "",
        "turn_seq": int(state.get("turn_seq", 0) or 0),  # 來源回合：Stop 只結算本輪的紀錄
        "at": _now_iso(),
    }
    injections = state.setdefault("subagent_injections", [])
    injections.append(rec)
    if len(injections) > _SUBAGENT_INJ_CAP:
        state["subagent_injections"] = injections[-_SUBAGENT_INJ_CAP:]
    return True


def _maybe_auto_roll_changelog(file_path: str, config: Dict[str, Any]) -> None:
    """Detached roll when _CHANGELOG.md rows exceed threshold. Fail-open."""
    try:
        normalized = file_path.replace("\\", "/")
        if not normalized.endswith("/_CHANGELOG.md") and not normalized.endswith("_CHANGELOG.md"):
            return
        if normalized.endswith("_CHANGELOG_ARCHIVE.md"):
            return
        cfg = (config or {}).get("changelog_auto_roll", {}) or {}
        if not cfg.get("enabled", True):
            return
        threshold = int(cfg.get("threshold", 8))
        cl_path = Path(file_path)
        if not cl_path.exists():
            return
        rows = 0
        for line in cl_path.read_text(encoding="utf-8").splitlines():
            if _CHANGELOG_TABLE_DATA_RE.match(line):
                rows += 1
        if rows <= threshold:
            return
        tool_path = Path(__file__).resolve().parent.parent.parent / "tools" / "changelog-roll.py"
        if not tool_path.exists():
            return
        bg_kwargs: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            bg_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            bg_kwargs["start_new_session"] = True
        subprocess.Popen(
            [sys.executable, str(tool_path),
             "--changelog", str(cl_path),
             f"--keep={threshold}", "--quiet"],
            **bg_kwargs,
        )
    except Exception as e:
        _atom_debug_error("post_tool_use:changelog_auto_roll", e)
        pass


def _maybe_sync_skill_index(file_path: str, config: Dict[str, Any]) -> None:
    """Detached `skill-index.py --write` when a skills/*/SKILL.md is added/edited.

    skill 計數 SoT 自動同步：重生 _skill_index.json + 重寫文件 marker。Bash 刪除等
    本 hook 漏接的情況由 SessionStart --check 防呆。Fail-open。"""
    try:
        normalized = file_path.replace("\\", "/")
        if "/skills/" not in normalized or not normalized.endswith("/SKILL.md"):
            return
        cfg = (config or {}).get("skill_index", {}) or {}
        if not cfg.get("enabled", True):
            return
        tool_path = Path(__file__).resolve().parent.parent.parent / "tools" / "skill-index.py"
        if not tool_path.exists():
            return
        bg_kwargs: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            bg_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            bg_kwargs["start_new_session"] = True
        subprocess.Popen([sys.executable, str(tool_path), "--write"], **bg_kwargs)
    except Exception as e:
        _atom_debug_error("post_tool_use:skill_index_sync", e)
        pass


# ─── Anti-Evasion HUD：one-writer 寫入者（MCP tool 只 emit、此處獨佔寫 state/檔）──


def _write_aec_report_file(session_id: str, turn_seq: int, report: Dict[str, Any]) -> None:
    """落 per-turn 報告檔 workflow/aec-report/<sid>-t<turn>.json（atomic tmp→rename）。

    供 HUD 唯讀輪詢最新卡 + 歷史格瀏覽；港口持有者 glob 子夾供頁、與哪個 session 的 MCP
    跑了 tool 無關（Python 寫 disk，跨 instance 安全）。命名比照 codex-companion
    _assessment_turn_path。Fail-open。"""
    try:
        d = WORKFLOW_DIR / "aec-report"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{session_id}-t{turn_seq}.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        tmp.replace(p)
    except OSError as e:
        _atom_debug_error("post_tool_use:aec_report_write", e)


def _collect_aec_evidence(
    state: Dict[str, Any], session_id: str
) -> List[Dict[str, Any]]:
    """收集本 session「上次 AEC emit 之後」的 hook 實測退避證據，供 (b) 欄
    cross-check（模型自評 vs hook 實測，不信自評）。

    來源：state["evasion_events"]（Stop 端 detect_evasion 命中即存，不受
    evasion_flag 被 UPS 注入後清空影響）+ 現行未清的 evasion_flag。
    窗口用 >=：同 turn 內 Stop（記事件）永遠在 emit 之後，事件 turn_seq ==
    上份報告 turn_seq 者必然是 emit 後才發生，屬下一份報告的證據。"""
    prev = state.get("anti_evasion_report") or {}
    prev_turn = (
        int(prev.get("turn_seq", -1))
        if prev.get("session_id") == session_id else -1
    )
    evidence = [
        e for e in (state.get("evasion_events") or [])
        if int(e.get("turn_seq", 0)) >= prev_turn
    ]
    ev = state.get("evasion_flag")
    if ev and not any(x.get("at") == ev.get("at") for x in evidence):
        evidence.append({
            "phrase": ev.get("phrase", ""),
            "turn_seq": int(state.get("turn_seq", 0)),
            "at": ev.get("at", ""),
        })
    return evidence


def _find_edge() -> str:
    """定位 msedge 執行檔（僅 Windows 主環境；找不到回 ""）。"""
    if sys.platform == "win32":
        for c in (
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ):
            if Path(c).exists():
                return c
    return ""


def _spawn_hud_edge(port: int) -> None:
    """no-shell spawn Edge --app 開 HUD（config gate 已過）。全庫唯一 browser 外呼，
    刻意 shell=False（AV 安全，比照 server.js 純 Node 設計）。Fail-open。"""
    edge = _find_edge()
    if not edge:
        return
    url = f"http://127.0.0.1:{port}/aec/hud"
    bg: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        bg["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        bg["start_new_session"] = True
    try:
        subprocess.Popen([edge, f"--app={url}"], shell=False, **bg)
    except (OSError, ValueError) as e:
        _atom_debug_error("post_tool_use:aec_spawn_edge", e)


def _maybe_spawn_hud(sev: str, state: Dict[str, Any], config: Dict[str, Any],
                     session_id: str = "") -> None:
    """窗活著（HUD 頁連線在，或心跳新）→ 會輪詢渲染、無需 fallback。窗死：config.aec.hud_autospawn
    才嘗試 spawn Edge（預設關）；且 sev∈{notable,real-evasion} → 標 aec_hud_fallback 供 Stop
    再查一次後大聲補 chat（可觀測性鐵律：push 不到窗不得 fail-silent）。routine 窗死只落 disk
    （無退避訊號、可事後由歷史格瀏覽，非違反可觀測性）。判死原因一律落 guard-aec_hud.jsonl。Fail-open。"""
    try:
        aec_cfg = (config or {}).get("aec", {}) or {}
        port = int((config or {}).get("dashboard_port", 3848))
        threshold = int(aec_cfg.get("hud_stale_s", 30))
        alive, info = _hud_alive(port, threshold)
        if alive:
            return
        append_guard_log("aec_hud", {
            "where": "post_tool_use", "session_id": session_id, "severity": sev, **info,
        })
        # B：只有 notable/real-evasion 才彈窗（routine 靜默入 disk、不打擾）。
        if aec_cfg.get("hud_autospawn", False) and sev in ("notable", "real-evasion"):
            _spawn_hud_edge(port)
        if sev in ("notable", "real-evasion"):
            state["aec_hud_fallback"] = True
    except Exception as e:
        _atom_debug_error("post_tool_use:aec_maybe_spawn_hud", e)


def _run_companion_hooks(input_data: Dict[str, Any], config: Dict[str, Any]):
    """原 standalone PostToolUse hook（version_guard / acceptance_spec）併入本程序，省每次
    Edit/Write 多起兩支 Python。各自 try/except 隔離，錯誤只進 debug log、不影響 guardian 主流程。
    回 (systemMessage 訊息, additionalContext 訊息)；兩檔仍保留 __main__ 可獨跑——
    回滾＝settings.json 的 PostToolUse 加回那兩行。"""
    sys_msgs: List[str] = []
    ctx_msgs: List[str] = []
    try:
        import version_guard
        sys_msgs = list(version_guard.run(input_data, config.get("version_guard", {})))
    except Exception as e:
        _atom_debug_error("post_tool_use:version_guard", e)
    try:
        import acceptance_spec
        ctx_msgs = list(acceptance_spec.run(input_data, config.get("acceptance_spec", {})))
    except Exception as e:
        _atom_debug_error("post_tool_use:acceptance_spec", e)
    return sys_msgs, ctx_msgs


def _emit_post_tool_output(advisories: List[str], sys_msgs: List[str]) -> None:
    """單一出口：additionalContext（給模型）＋ systemMessage／stderr（給使用者，version_guard 原格式）。"""
    for m in sys_msgs:
        print(m, file=sys.stderr)
    out: Dict[str, Any] = {}
    if sys_msgs:
        out["systemMessage"] = "\n".join(sys_msgs)
    if advisories:
        out["hookSpecificOutput"] = {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(advisories),
        }
    if out:
        output_json(out)
    else:
        output_nothing()


DELIBERATE_REDS_CAP = 20
RETRY_ROUNDS_CAP = 20
MOVED_DIRS_CAP = 20
_MOVE_SCAN_FILES = 5000                 # 判「目錄裡有沒有程式檔」最多看幾個檔
_SEG_SPLIT_RE = re.compile(r"&&|\|\||;|\n")
_CD_WORDS = ("cd", "set-location", "sl", "pushd", "push-location", "chdir")


_MOVE_HEADS = ("mv", "move-item", "move", "mi")
_RENAME_HEADS = ("rename-item", "ren", "rni")
_PS_VALUE_PARAMS = {"-path": "src", "-literalpath": "src", "-destination": "dest", "-newname": "dest"}


def _ps_args(toks: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """PowerShell 參數：具名的（-Path／-LiteralPath／-Destination／-NewName）取值，其他 - 開頭的開關略過，剩下照位置。"""
    pos: List[str] = []
    named: Dict[str, str] = {}
    i = 0
    while i < len(toks):
        t = toks[i]
        key = _PS_VALUE_PARAMS.get(t.lower())
        if key and i + 1 < len(toks):
            named[key], i = toks[i + 1], i + 2
            continue
        if not t.startswith("-"):
            pos.append(t)
        i += 1
    return pos, named


def _move_pairs(command: str, cwd: str, posix: bool) -> List[Tuple[str, str]]:
    """指令裡每個搬移的（目的地, 來源）絕對路徑：跟著同一條指令前面的 cd／Set-Location／pushd 換目錄。認 mv、Move-Item
    （位置或 -Path／-Destination）、Rename-Item（新名字在同一層，位置或 -Path／-NewName）、`git [-C <目錄>] mv`；
    一次搬多個來源時最後一個參數是目的地。解析不了的段落略過。"""
    pairs: List[Tuple[str, str]] = []
    here = cwd
    for seg in _SEG_SPLIT_RE.split(command or ""):
        try:
            toks = [t.strip("'\"") for t in shlex.split(seg, posix=posix)]
        except ValueError:
            continue
        if not toks:
            continue
        head, base, args = toks[0].lower(), here, toks[1:]
        if head in _CD_WORDS:
            pos, named = _ps_args(args)
            target = named.get("src") or (pos[0] if pos else "")
            here = os.path.normpath(os.path.join(here, target)) if target else here
            continue
        if head in ("git", "git.exe"):
            i = 0
            while i + 1 < len(args) and args[i] == "-C":
                base, i = os.path.normpath(os.path.join(base, args[i + 1])), i + 2
            if i >= len(args) or args[i] != "mv":
                continue
            head, args = "mv", args[i + 1:]
        if head in _MOVE_HEADS:
            pos, named = _ps_args(args)
            srcs = ([named["src"]] if "src" in named else pos[:-1] if "dest" not in named else pos)
            dest = named.get("dest") or (pos[-1] if pos and "dest" not in named else "")
            if dest and srcs:
                pairs += [(os.path.normpath(os.path.join(base, dest)), os.path.normpath(os.path.join(base, s))) for s in srcs]
        elif head in _RENAME_HEADS:
            pos, named = _ps_args(args)
            src, new_name = named.get("src") or (pos[0] if pos else ""), named.get("dest") or (pos[-1] if len(pos) > 1 else "")
            if src and new_name:
                old = os.path.normpath(os.path.join(base, src))
                pairs.append((os.path.join(os.path.dirname(old), os.path.basename(new_name)), old))
    return pairs
_SCAN_HIT_RE = re.compile(r"^\S+:\d+: ")


def _has_code(d: Path, exts: Any) -> bool:
    n = 0
    for dirpath, _dirs, files in os.walk(d):
        for name in files:
            n += 1
            if is_code_file(os.path.join(dirpath, name), exts):
                return True
            if n >= _MOVE_SCAN_FILES:
                return False
    return False


def _note_moved_code_dirs(state: Dict[str, Any], sid: str, tool_name: str, tool_input: Dict[str, Any], cwd: str,
                          config: Optional[Dict[str, Any]], agent_id: str = "") -> bool:
    """規則 MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE 的事實：這次 Bash／PowerShell 把含程式檔的目錄搬走了（mv、Move-Item 的來源
    取自 wg_core.write_sources_from_tool，另照 _move_pairs 解析 mv、Move-Item、Rename-Item、git mv 與前面的換目錄），記 state["moved_code_dirs"]（舊、新路徑、時間、
    子代理搬的帶 agent_id）。複製（來源還在）、搬的是單一檔案、目錄裡沒有程式檔都不記。回有沒有記。"""
    if tool_name not in ("Bash", "PowerShell"):
        return False
    from wg_core import write_sources_from_tool
    pairs = []
    for target, sources in write_sources_from_tool(tool_name, tool_input, cwd).items():
        pairs += [(target, s) for s in sources]
    pairs += _move_pairs(str(tool_input.get("command") or ""), cwd, posix=tool_name != "PowerShell")
    exts = reconcile_cfg(config or {}).get("code_exts") or []
    seen = set()
    for new, old in pairs:
        dest, src = Path(new), Path(old)
        if not dest.exists() and dest.name == src.name and dest.parent.is_dir():
            dest = dest.parent            # 搬完才看：write_sources_from_tool 照「搬進既有目錄」推成 <目的地>/<名字>，那個路徑不存在
        elif dest.is_dir() and (dest / src.name).exists():
            dest = dest / src.name        # 搬進既有目錄：實際落點是 <目的地>/<名字>（搬單一檔案時這裡就是那個檔，下面不記）
        key = (canon_path(str(src)), canon_path(str(dest)))
        if key in seen or src.exists() or copied_glob_source(str(src)) or not dest.is_dir() or not _has_code(dest, exts):
            continue
        seen.add(key)
        lst = state.setdefault("moved_code_dirs", [])
        lst.append({"old": str(src), "new": str(dest), "at": _now_iso(), "seq": next_event_seq(state),
                    "session_id": sid, "agent_id": agent_id, "turn_seq": int(state.get("turn_seq", 0))})
        del lst[:-MOVED_DIRS_CAP]
    return bool(seen)


def _read_exit_code(tool_response: Any) -> Optional[int]:
    """讀檔用的結束碼：dict 回應只信 exit_code／returncode 欄（stdout 是被讀的檔內容，裡面一行「Exit code 1」不能當失敗）；
    字串回應（實機非零 exit 時整包是 "Error: Exit code N…"）照 exit_code_of 看文字。"""
    if isinstance(tool_response, dict):
        return exit_code_of({k: tool_response.get(k) for k in ("exit_code", "returncode")})
    return exit_code_of(tool_response)


def _note_move_scan_hits(state: Dict[str, Any], command: str, tool_response: Any, cwd: str) -> bool:
    """搬目錄掃描工具（move-dir-check.py scan）印的命中清單前幾筆，記 state["move_scan_hits"][舊路徑]，
    擋訊息照列（只供顯示；欠不欠看收據）。"""
    if "move-dir-check.py" not in command or " scan" not in command:
        return False
    m = re.search(r"--old(?:=|\s+)(\"[^\"]+\"|'[^']+'|\S+)", command)
    if not m:
        return False
    old = m.group(1).strip("'\"")
    key = canon_path(old if os.path.isabs(old) else os.path.join(cwd, old))
    lines = [ln.strip() for ln in response_text(tool_response).splitlines() if _SCAN_HIT_RE.match(ln.strip())]
    state.setdefault("move_scan_hits", {})[key] = lines[:5]
    return True


def _note_retry_round(state: Dict[str, Any], sid: str, command: str, failure: str, cwd: str) -> None:
    """又跑紅了：蒐集事實（同一組測試還活著的紅、它們上次跑之後改過的檔、這次的指令與紅案）交給規則
    RETRY_COUNTS_RERUN_CYCLES 判；算一輪就重試加一，並記下這一輪的證據（FixEscalation／DeepPostMortem 印）。
    同一組的改檔紀錄這次用掉就清空（新紅測條目從零記起），別組的紅與它們的改檔不動。"""
    same = [f for f in state.get("failing_tests") or []
            if isinstance(f, dict) and f.get("session_id") == sid and not f.get("deliberate")
            and same_test_run(f.get("cmd", ""), command, f.get("cwd") or None, cwd or None)]
    edited: Dict[str, int] = {}
    for f in same:
        for path, n in (f.pop("edits_since_run", None) or {}).items():
            edited[path] = edited.get(path, 0) + int(n or 0)
    red = red_case_names(failure)
    count = int(state.get("wisdom_retry_count", 0) or 0)
    v = retry_round_verdict(same[-1] if same else None, edited, count + 1, command, red)
    if not v.owed:
        return
    state["wisdom_retry_count"] = count + 1
    summary = next((ln.strip() for ln in str(failure).splitlines()
                    if ln.strip() and not ln.strip().startswith("Error: Exit code")), "")
    rounds = state.setdefault("retry_rounds", [])
    rounds.append({"round": count + 1, "cmd": command[:200], "red": red[:5], "summary": summary[:160],
                   "edited": sorted(edited)[:5], "session_id": sid, "turn_seq": int(state.get("turn_seq", 0)), "at": _now_iso()})
    del rounds[:-RETRY_ROUNDS_CAP]


def _supersede_reds(state: Dict[str, Any], sid: str, command: str, failure: str) -> None:
    """規則 GREEN_CLEARS_ONLY_CASES_IT_RAN 的紅那一面：這次紅完整列出失敗（red_case_facts：列出的支數等於結算的 failed＋error）→
    本 session 舊紅裡這次也跑到的那幾支以這次為準（還紅的這次照列）：全跑到的整筆拿掉、跑到一部分的記進 cleared_units。
    輸出不完整（截斷、沒列）不動舊紅——不然截過的那筆對不到名字、又沒有綠能清，會一直擋。"""
    if not red_case_facts(failure)[1]:
        return
    keep: List[Dict[str, Any]] = []
    for f in state.get("failing_tests") or []:
        if not isinstance(f, dict) or f.get("session_id") != sid:
            keep.append(f)
            continue
        v, ran = green_ran_cases_verdict(f.get("cmd", ""), f.get("summary", ""), command, f.get("cleared_units") or ())
        if not v.owed:
            continue
        if ran:
            f["cleared_units"] = list(dict.fromkeys([*(f.get("cleared_units") or []), *ran]))
        keep.append(f)
    state["failing_tests"] = keep


def _track_test_result(state: Dict[str, Any], input_data: Dict[str, Any], command: str,
                       tool: str = "Bash", config: Optional[Dict[str, Any]] = None) -> bool:
    """Bash／PowerShell 測試指令 → 記／清 state.failing_tests；回傳是否動到 state。
    條目蓋 session_id：共用 state／merged state 下 Stop 與清帳只認自己的（隔壁 session 的紅測不擋本 session、
    本 session 的綠測不清隔壁的；沒蓋 sid 的舊條目視為他人，不擋不清）。
    子代理（hook 輸入帶 agent_id）自己迭代中的紅測不記進主 session，也不替主 session 清帳。
    exit_code 三來源（wg_verify_ledger.exit_code_of）：tool_response 欄位 → 文字 `Exit code N` → None；
    非零 exit 一律建紅測（哨兵 FAIL 也算失敗樣式）；清帳只在 exit 為 0／None 且無失敗樣式時。"""
    if not is_test_command(command) or input_data.get("agent_id"):
        return False
    sid = str(input_data.get("session_id") or state.get("session", {}).get("id") or "")
    tr = input_data.get("tool_response", {}) or {}
    if isinstance(tr, dict):
        stdout = tr.get("stdout", "") or ""
        stderr = tr.get("stderr", "") or ""
        interrupted = bool(tr.get("interrupted", False))
    else:
        stdout, stderr, interrupted = str(tr), "", False
    exit_code = exit_code_of(tr)
    failure = detect_test_failure(stdout, stderr, interrupted)
    if failure is None and exit_code not in (None, 0):
        failure = tail_lines(stdout + "\n" + stderr, 20) or f"(exit code {exit_code}, no output)"
    if failure:
        # 規則 RED_WHILE_REVERTED：跑紅時本 session 改過的程式檔有內容等於非 HEAD 已提交版本（退回舊碼反證）→ 刻意紅：
        # 不進 failing_tests（TestFailGate、重試計數、DPM 都不吃），另記 deliberate_reds 留痕
        own_mods = [m for m in (state.get("modified_files") or []) if (m or {}).get("session_id", sid) == sid]
        try:
            reverted, pending_code = reverted_code_files(own_mods, reconcile_cfg(config or {}))
        except Exception as e:  # noqa: BLE001
            reverted, pending_code = [], ["?"]
            print(f"[verify-ledger] 判斷刻意紅失敗，照算真的紅：{type(e).__name__}: {e}", file=sys.stderr)
        verdict = deliberate_red_verdict(reverted, pending_code)
        if not verdict.owed:
            print(f"[Guardian:TestFail] 規則 {verdict.rule}：{verdict.why}｜證據：{'；'.join(verdict.evidence)}", file=sys.stderr)
            lst = state.setdefault("deliberate_reds", [])
            lst.append({"cmd": command[:200], "session_id": sid, "turn_seq": int(state.get("turn_seq", 0)), "at": _now_iso(),
                        "rule": verdict.rule, "evidence": list(verdict.evidence)[:3]})
            del lst[:-DELIBERATE_REDS_CAP]
            return True
        _note_retry_round(state, sid, command, failure, str(input_data.get("cwd") or ""))
        _supersede_reds(state, sid, command, failure)
        state.setdefault("failing_tests", []).append({
            "tool": tool,
            "session_id": sid,
            "agent_id": str(input_data.get("agent_id") or ""),
            "exit_code": exit_code,
            "cmd": command[:200],
            # cmd 截 200 字會把串在後段的 pytest 截掉 → 綠的 pytest 對不上、永遠清不掉；
            # 記錄時就用全文判定一次
            "pytest": "pytest" in command.lower(),
            "summary": failure,
            "at": _now_iso(),
            # 供 Stop 端 outcome 歸因「只認本 turn 失敗」（sync/test-fail
            # gate 等其他消費者仍看全量清單，語意不變）
            "turn_seq": int(state.get("turn_seq", 0)),
            "cwd": str(input_data.get("cwd") or ""),          # GREEN_SAME_CASE_CLEARS 比絕對路徑用（同名不同目錄的案例不互清）
        })
        return True
    if not state.get("failing_tests"):
        return False
    cmd_prefix = command[:80].strip()
    is_pytest_success = "pytest" in command.lower()
    before = state["failing_tests"]
    shrunk: List[Dict[str, Any]] = []

    def _clears(f: Dict[str, Any]) -> bool:
        if f.get("session_id") != sid:          # 只清自己的；沒蓋 sid 的舊條目不是自己的
            return False
        matched = (f.get("cmd", "").startswith(cmd_prefix[:40])
                   or green_clears_red(f.get("cmd", ""), command, f.get("cwd") or None,
                                       str(input_data.get("cwd") or "") or None)   # 規則 GREEN_SAME_CASE_CLEARS：綠的點名同一個案例檔
                   or (is_pytest_success and (f.get("pytest") or "pytest" in f.get("cmd", "").lower()
                                              or "short test summary" in f.get("summary", ""))))   # legacy 看 pytest 輸出特徵
        if not matched:
            return False
        # 規則 GREEN_CLEARS_ONLY_CASES_IT_RAN（篩選另見 GREEN_NARROWED_KEEPS_UNCOVERED_RED）：綠只清它跑到的紅案；只跑到一部分 →
        # 跑到的那幾支記進 cleared_units、那筆紅與它的改檔紀錄照留（放行要對那支紅測自己的最後一次執行，不是最後一次任何 pytest）
        keep, ran = green_ran_cases_verdict(f.get("cmd", ""), f.get("summary", ""), command, f.get("cleared_units") or ())
        if keep.owed:
            print(f"[Guardian:TestFail] 規則 {keep.rule}：{keep.why}｜證據：{'；'.join(keep.evidence)}", file=sys.stderr)
            if ran:
                f["cleared_units"] = list(dict.fromkeys([*(f.get("cleared_units") or []), *ran]))
                shrunk.append(f)
        return not keep.owed

    after = [f for f in before if not _clears(f)]
    if len(after) == len(before):
        return bool(shrunk)
    state["failing_tests"] = after
    return True


def _note_commit(state: Dict[str, Any], command: str, config: Optional[Dict[str, Any]] = None,
                 session_id: str = "", snapshot: bool = True) -> bool:
    """跑了 git／svn commit → state["last_commit_turn_seq"]＝本回合；回有沒有記。一般與裁判 PostToolUse 共用這一條：
    ScanReport 閘據此豁免收尾檢核（工作已寫進 VCS 歷史＝可稽核），寫碼查核判「改過又原樣還原」也看它（改完 commit 了，
    工作樹乾淨不代表沒改）。同時記 commit_snapshot（本 session 改過的檔此刻的內容雜湊＋當時不欠案例的程式檔）：commit 之後
    做反證、把檔退回舊版又還原，Stop 看內容回到這個快照就不重算補案例。新快照先拿舊快照判一次：對舊快照已經成立「回到不欠
    案例的狀態」的程式檔照算不欠（還原後再 commit --amend 只改訊息，不會又欠一次）。快照算失敗只少了這個豁免（照擋），stderr 說一聲。"""
    if not _VCS_COMMIT_RE.search(command):
        return False
    turn = int(state.get("turn_seq", 0))
    state["last_commit_turn_seq"] = turn
    own = [m for m in (state.get("modified_files") or []) if (m or {}).get("session_id", session_id) == session_id]
    _note_committed_new_code(state, own, reconcile_cfg(config or {}))
    if not snapshot:                                  # 這條指令的寫入目標沒算出來：不拍快照（可能漏掉同一條指令改的檔）
        state.pop("commit_snapshot", None)
        print("[verify-ledger] commit 指令的寫入目標算不出來，不記內容快照；commit 之後的反證還原照算改碼", file=sys.stderr)
        return True
    every = [m["path"] for m in own if (m or {}).get("path")]          # 同根要一起比的改檔：與 Stop 同一份（主 session＋子代理）
    for _mods in (state.get("agent_modified_files") or {}).values():
        every += [m["path"] for m in _mods or [] if isinstance(m, dict) and m.get("path")]
    try:
        rg = reconcile_cfg(config or {})
        check = None
        import wg_verify_scope as vs
        if vs.scope_cfg(config or {}).get("enabled", True):
            # 「當時不欠案例」與 Stop 的 (d) 同一個判法：照 LLM 的案例宣告（case_for）判，驗證範圍閘關掉才退回時序判法
            from wg_overview import _lookup
            from wg_verify_ledger import load_self_runs
            check = vs.case_check(state, session_id, own, receipts_of(state, session_id), rg, _lookup, load_self_runs())
        state["commit_snapshot"] = commit_snapshot(own, turn, rg, prev=state.get("commit_snapshot"), session_paths=every,
                                                   case_check=check)
    except Exception as e:  # noqa: BLE001
        state.pop("commit_snapshot", None)
        print(f"[verify-ledger] commit 內容快照失敗，commit 之後的反證還原照算改碼：{type(e).__name__}: {e}", file=sys.stderr)
    return True


def _note_committed_new_code(state: Dict[str, Any], own: List[Dict[str, Any]], cfg: Dict[str, Any]) -> None:
    """commit 之後，本 session 改過的檔所在的每個 git 根，記下 HEAD 那筆提交新增、改名、複製進來的程式檔
    （state["committed_new_code"][根]＝{shas, paths}）。寫碼查核判「已不存在的改檔是刪掉還是搬走」時用：搬完又 commit，
    工作樹的 status 就看不到新路徑了。讀不到只少這份證據（已不存在的改檔照欠），stderr 由 head_new_code 說。"""
    rec = state.setdefault("committed_new_code", {})
    seen = set()
    for m in own:
        hit = _git_root_of(str((m or {}).get("path") or ""))
        if not hit or hit[0] in seen:
            continue
        seen.add(hit[0])
        sha, new = head_new_code(hit[1], cfg)
        r = rec.setdefault(hit[0], {"shas": [], "paths": []})
        if sha and sha not in r["shas"]:
            r["shas"] = (r["shas"] + [sha])[-50:]
            r["paths"] = list(dict.fromkeys(r["paths"] + new))[-200:]


def _note_modified(state: Dict[str, Any], session_id: str, file_path: str, tool_name: str, agent_id: str = "") -> None:
    """modified_files 以 (path, session_id) 去重：重複編輯只累加 count、刷 at／tool／last_turn_seq，
    不無限累積 entry。turn_seq＝第一次改的回合、last_turn_seq＝最近一次改的回合（對帳閘「本 turn 改了哪些」用）。
    消費端計「編輯次數」者（wisdom track_retry / episodic 工作區統計）讀 count 欄（legacy 無 count → 預設 1）。
    子代理（agent_id 非空）改的檔另記一份到 agent_modified_files[agent_id]（SubagentStop 的對帳／量尺閘只看子代理自己的）；
    主 session 的 modified_files 照舊也記，主 session 行為不變。
    sha＝寫完之後的內容雜湊（small_content_sha，太大的檔不記）；檔已不存在（rm、搬走）就留上一次的：Stop 判已不存在的檔
    是不是搬到同根新出現的程式檔（規則 MOVED_NEW_CODE_SEEN）要比它最後的內容。"""
    sha = small_content_sha(file_path)
    _upsert_modified(state, state.setdefault("modified_files", []), session_id, file_path, tool_name, sha)
    if agent_id:
        _upsert_modified(state, state.setdefault("agent_modified_files", {}).setdefault(agent_id, []),
                         session_id, file_path, tool_name, sha)
    state["sync_pending"] = True


def _upsert_modified(state: Dict[str, Any], mods: List[Dict[str, Any]], session_id: str, file_path: str,
                     tool_name: str, sha: Optional[str] = None) -> None:
    """同一個檔不論哪種寫法（Edit 的反斜線、Bash 的正斜線、大小寫、`..`）只留一筆，比對用 canon_path；
    path 欄保留第一次記下的原字串。sha 是 None（檔不在、讀不到）不蓋掉舊值。"""
    turn = int(state.get("turn_seq", 0))
    key = canon_path(file_path)
    for m in mods:
        if (
            isinstance(m, dict)
            and m.get("path")
            and canon_path(m["path"]) == key
            and m.get("session_id", session_id) == session_id
        ):
            m["count"] = int(m.get("count", 1)) + 1
            m["at"] = _now_iso()
            m["last_at"] = m["at"]
            m["last_seq"] = next_event_seq(state)
            m["tool"] = tool_name
            m["last_turn_seq"] = turn
            m.setdefault("turn_seq", turn)
            if sha:
                m["sha"] = sha
            break
    else:
        now = _now_iso()
        mods.append({
            "path": file_path,
            "tool": tool_name,
            "session_id": session_id,
            "at": now,
            "last_at": now,
            "last_seq": next_event_seq(state),
            "count": 1,
            "turn_seq": turn,
            "last_turn_seq": turn,
            **({"sha": sha} if sha else {}),
        })


UNKNOWN_WRITES_CAP = 20
EXEC_TURN_KEYS_CAP = 50          # exec_turn_seq 最多記幾個 session／子代理（主 session＋每個子代理各一個鍵）


def _note_unknown_write(state: Dict[str, Any], session_id: str, target: str, command: str, tool_name: str,
                        agent_id: str = "") -> None:
    """寫入目標算不出來（write_paths_from_tool 回 UNKNOWN:…）→ 記一筆「未知寫入」：知道有寫、不知道寫了哪個檔，
    不能當成沒寫。裁判 Stop（unknown_writes）與子代理 Stop（agent_unknown_writes[agent_id]）有這筆就擋到底；
    主 session 的 PreToolUse 本來就 deny UNKNOWN，主 Stop 不看這份。每份最多留 UNKNOWN_WRITES_CAP 筆。"""
    rec = {"cmd": " ".join(str(command or "").split())[:120], "target": str(target)[:60], "tool": tool_name,
           "session_id": session_id, "turn_seq": int(state.get("turn_seq", 0)), "at": _now_iso()}
    lst = (state.setdefault("agent_unknown_writes", {}).setdefault(agent_id, []) if agent_id
           else state.setdefault("unknown_writes", []))
    lst.append(rec)
    del lst[:-UNKNOWN_WRITES_CAP]


def _track_sentinels(state: Dict[str, Any], input_data: Dict[str, Any], command: str, tool_name: str,
                     config: Dict[str, Any], session_id: str) -> bool:
    """Bash／PowerShell 輸出的哨兵（`<NAME>_CHECK PASS|FAIL|DONE`、`<NAME> DONE k=v`）與 exit code → 驗證帳本
    workflow/verify-ledger/<sid>.jsonl ＋ state["verify_receipts"][sid]（cap 50）。只在有哨兵或是測試指令時落帳。
    每筆記 env＝啟動當下繼承的縮限變數（env_snapshot），Stop 採認時與指令內的環境指定合併；沒 env 欄的舊收據不算證據。
    子代理（agent_id 非空）不入主帳：另落 <sid>.agents.jsonl、不進 state 收據。總耗時進 guard log（[verify-ledger] ms）。"""
    cfg = config.get("verify_ledger") or {}
    if not cfg.get("enabled", True):
        return False
    t0 = time.monotonic()
    tr = input_data.get("tool_response")
    sentinels = parse_sentinels(response_text(tr), compile_sentinel_rules(cfg.get("sentinel_regex")))
    if not sentinels and not is_test_command(command):
        return False
    turn_seq = int(state.get("turn_seq", 0))
    agent_id = str(input_data.get("agent_id") or "")
    cwd = input_data.get("cwd", "") or state.get("session", {}).get("cwd", "") or ""
    own = [m for m in (state.get("modified_files") or []) if (m or {}).get("session_id", session_id) == session_id]
    mod_turn = modified_this_turn(own, turn_seq)
    project_root = ""
    try:
        from project_root import resolve_project_root
        project_root = str(resolve_project_root(cwd).path or "") if cwd else ""
    except Exception:
        project_root = ""
    exit_code = exit_code_of(tr)
    env = env_snapshot()          # 指令啟動當下繼承的縮限變數（hook 與工具子 shell 同一個父行程）：採認時與指令內的指定合併
    red_cases, red_known = red_case_facts(response_text(tr))     # 紅了哪幾支、清單完不完整（SCOPE_RED_ONLY_ITS_CASES 逐項判紅綠）
    record = {
        "at": _now_iso(),
        "session_id": session_id,
        "agent_id": agent_id,
        "turn_seq": turn_seq,
        "tool": tool_name,
        "cmd": command,               # 完整指令：量尺比對要看到尾段（截斷後接的假哨兵也要看得到）；顯示時才截
        "cmd_full": True,
        "env": env,
        "cwd": cwd,
        "project_root": project_root,
        "sentinels": [{"name": s["name"], "verdict": s["verdict"], "line": s["line"]} for s in sentinels],
        "exit_code": exit_code,
        "vcs": vcs_snapshot(cwd, mod_turn, state, float(cfg.get("vcs_budget_s", 1.5))),
        "modified_files_turn": mod_turn,
        "spec": spec_paths_of(session_id, WORKFLOW_DIR),
        # 指令裡有 cd／pushd／Set-Location → 真正的 cwd 不是 hook 給的 cwd，量尺閘與「對得上」不採用這筆
        "root_uncertain": has_cd(command),
    }
    append_verify_ledger(session_id, record, base_dir=WORKFLOW_DIR, suffix=".agents" if agent_id else "")
    # 子代理的收據不進主 session 的收據（主帳不變），另放 agent_receipt_key(sid, agent_id)，給 SubagentStop 對帳用
    record_receipt(state, agent_receipt_key(session_id, agent_id) if agent_id else session_id, {
        "at": record["at"], "seq": next_event_seq(state), "turn_seq": turn_seq, "tool": tool_name,
        "cmd": command, "cmd_full": True, "env": env,
        "sentinels": [{"name": s["name"], "verdict": s["verdict"], "kv": s.get("kv") or {}} for s in sentinels],
        "exit_code": exit_code, "cwd": cwd, "project_root": project_root,
        "root_uncertain": record["root_uncertain"],
        **({"red_cases": red_cases, "red_known": red_known} if red_cases else {}),
    })
    ms = int((time.monotonic() - t0) * 1000)
    append_guard_log("verify_ledger", {
        "session_id": session_id, "turn_seq": turn_seq, "tool": tool_name, "ms": ms,
        "sentinels": len(sentinels), "exit_code": exit_code, "agent": bool(agent_id),
        "truncated": any(v.get("truncated") for v in record["vcs"]),
    })
    return True


_EDIT_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")


def _need_goal_after_tool(state: Dict[str, Any], session_id: str, tool_name: str, tool_input: Dict[str, Any],
                          input_data: Dict[str, Any], config: Dict[str, Any]) -> Tuple[Optional[str], bool]:
    """需求目標樹（wg_need_goal）：need_goal 工具呼叫套用到目標樹並送回整棵樹、目標改了清各部位的「已定位」、
    改檔與收據蓋號、讀到帶【需求目標樹】區塊的續接單時匯入。回（要送回 AI 的提示, state 有沒有變）。
    目標檔自己整段上鎖；這裡出錯只 stderr＋守門紀錄，不影響工具結果。"""
    import wg_need_goal as ng
    is_ng = tool_name.endswith("need_goal")
    if not (is_ng or tool_name in _EDIT_TOOLS or tool_name in ("Bash", "PowerShell")
            or (tool_name == "Read" and ng.HANDOFF_NAME_RE.search(str(tool_input.get("file_path") or "")))):
        return None, False
    if is_ng and is_error_response(input_data.get("tool_response")):
        return None, False                       # MCP 已拒收：不套用
    if is_ng and (tool_input or {}).get("action") == "verify_scope":
        return _verify_scope_declare(state, session_id, tool_input, input_data, config), True
    turn = int(state.get("turn_seq", 0))
    cwd = input_data.get("cwd", "") or state.get("session", {}).get("cwd", "") or ""
    transcript_path = input_data.get("transcript_path", "") or ""
    try:
        if not ng.cfg_for_cwd(config, cwd)["enabled"]:
            return ("[NeedGoal] need_goal 在這一層關閉（overview_hub.need_goal.enabled=false），沒有套用" if is_ng else None), False
        if is_ng:
            res = ng.apply_op(session_id, turn, tool_input, cwd)
            changed = False
            if res["goal_changed"]:
                from wg_overview import on_goal_changed
                changed = on_goal_changed(state, transcript_path, turn) > 0
            return res["text"], changed
        if tool_name == "Read":
            return _need_goal_import(ng, state, session_id, str(tool_input.get("file_path")), turn, transcript_path)
        if tool_name in _EDIT_TOOLS:
            fp = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
            targets = [fp] if fp else []
        else:
            targets = _write_paths_from_tool(tool_name, tool_input, cwd) if _write_paths_from_tool is not None else []
        agent_id = str(input_data.get("agent_id") or "")
        lines: List[str] = []
        for p in targets or []:
            if p and not p.startswith("UNKNOWN:") and not _is_ephemeral_path(p):
                line = ng.stamp_edit(session_id, p, agent_id, turn, config)   # 沒樹時改了知識類：要寫輕樹（一回合一次）
                if line:
                    lines.append(line)
        hint = None
        if tool_name in ("Bash", "PowerShell"):
            ng.stamp_receipts(session_id, state, turn)
        elif targets:
            # 改了計畫類文件（_staging、plans 下的 .md）：交出計畫、開工句、清單之前的一問，一回合一次
            from wg_need_goal_points import handout_edit_line
            hint = handout_edit_line(state, session_id, str(targets[0]), turn)
            if hint:
                lines.append(hint)
        if lines:
            return "\n".join(lines), bool(hint)
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] PostToolUse 蓋號／套用失敗（{tool_name}）：{type(e).__name__}: {e}", file=sys.stderr)
        ng._guard("stamp_error", session_id, tool=tool_name, error=f"{type(e).__name__}: {e}")
        if is_ng:
            return f"[NeedGoal] 這次 need_goal 沒寫進目標檔（{type(e).__name__}: {e}），請重新呼叫一次。", False
    return None, False


def _scope_key(session_id: str, input_data: Dict[str, Any]) -> str:
    agent_id = str(input_data.get("agent_id") or "")
    return agent_receipt_key(session_id, agent_id) if agent_id else session_id


def _verify_scope_declare(state: Dict[str, Any], session_id: str, tool_input: Dict[str, Any],
                          input_data: Dict[str, Any], config: Dict[str, Any]) -> str:
    """need_goal(action=verify_scope)：LLM 判斷的驗證範圍交 wg_verify_scope 收件（存在 state，不經目標檔、不受 need_goal 開關影響）。"""
    cwd = input_data.get("cwd", "") or state.get("session", {}).get("cwd", "") or ""
    try:
        import wg_verify_scope as vs
        return vs.declare(state, _scope_key(session_id, input_data), tool_input, cwd, config)
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:VerifyScope] 收件失敗：{type(e).__name__}: {e}", file=sys.stderr)
        return f"[Guardian:VerifyScope] 這次 verify_scope 沒收下（{type(e).__name__}: {e}），請重新呼叫一次。"


def _observe_scope_run(state: Dict[str, Any], input_data: Dict[str, Any], session_id: str, config: Dict[str, Any]) -> None:
    """剛落帳的這輪測試記進驗證範圍的測試帳（跑了哪些、哪些紅）；紅的測試找範圍漏判，新記的放 _verify_scope_advisory 送回。"""
    key = _scope_key(session_id, input_data)
    receipts = receipts_of(state, key)
    if not receipts:
        return
    try:
        import wg_verify_scope as vs
        if not vs.scope_cfg(config)["enabled"]:
            return
        note = vs.observe_run(state, key, receipts[-1], response_text(input_data.get("tool_response")), reconcile_cfg(config))
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:VerifyScope] 記測試帳失敗（不影響這次工具）：{type(e).__name__}: {e}", file=sys.stderr)
        return
    if note:
        state["_verify_scope_advisory"] = note


def _need_goal_import(ng: Any, state: Dict[str, Any], session_id: str, fp: str, turn: int,
                      transcript_path: str) -> Tuple[Optional[str], bool]:
    """讀到續接單：帶【需求目標樹】區塊而且這個 session 還沒有樹 → 自動匯入並送回；已經有樹 → 提示怎麼接續。"""
    try:
        text = Path(fp).read_text(encoding="utf-8")
    except OSError:
        return None, False
    if "need-goal:begin" not in text or ng.handoff_session_of(text) == session_id:
        return None, False                       # 沒有區塊，或是本 session 自己匯出的（樹還在目標檔裡）
    if ng.load(session_id).get("trees"):
        return (f"[NeedGoal] 續接單 {fp} 帶【需求目標樹】區塊，但這個 session 已經有目標樹；要接續請 "
                f"need_goal(action=set, import_from=\"{fp}\")。"), False
    res = ng.import_handoff(session_id, text, fp, turn)
    if not res["imported"]:
        return (f"[NeedGoal] 續接單的需求目標樹沒有匯入：{res.get('skipped')}" if res.get("skipped") else None), False
    from wg_overview import on_goal_changed
    return res["text"], on_goal_changed(state, transcript_path, turn) > 0


def handle_judge_post_tool_use(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    """裁判子 session（CLAUDE_COMPANION_JUDGE=1）的 PostToolUse 最小記帳：只記改了哪些檔、目標不明的寫入、commit 回合與驗證收據，
    給 stop.handle_judge_stop 的寫碼查核閘用；不注入、不跑其他閘、不建完整 state（不重建 atom index，防裁判觸發裁判）。"""
    session_id = input_data.get("session_id", "") or ""
    if not session_id:
        output_nothing()
        return
    from wg_core import read_state as _read_state
    tool_name = input_data.get("tool_name", "") or ""
    tool_input = input_data.get("tool_input") or {}
    cwd = input_data.get("cwd", "") or ""
    state = _read_state(session_id) or {"session": {"id": session_id, "cwd": cwd}, "turn_seq": 0, "judge": True}
    if tool_name in ("Write", "Edit", "NotebookEdit", "MultiEdit"):
        fp = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
        if fp and not _is_ephemeral_path(fp):
            _note_modified(state, session_id, fp, tool_name)
    elif tool_name in ("Bash", "PowerShell"):
        command = tool_input.get("command", "") or ""
        targets = _write_paths_from_tool(tool_name, tool_input, cwd) if _write_paths_from_tool is not None else []
        for p in targets or []:
            if p and p.startswith("UNKNOWN:"):
                _note_unknown_write(state, session_id, p, command, tool_name)
            elif p and not _is_ephemeral_path(p):
                _note_modified(state, session_id, p, tool_name)
        _note_commit(state, command, config, session_id)
        if _track_sentinels(state, input_data, command, tool_name, config, session_id):
            _observe_scope_run(state, input_data, session_id, config)
            state.pop("_verify_scope_advisory", None)        # 裁判不注入；漏判已入帳，下次宣告時送回
    elif tool_name.endswith("need_goal") and (tool_input or {}).get("action") == "verify_scope":
        if not is_error_response(input_data.get("tool_response")):
            _verify_scope_declare(state, session_id, tool_input, input_data, config)
    write_state(session_id, state)
    output_nothing()


def handle_post_tool_use_failure(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    """PostToolUseFailure：工具失敗時 Claude Code 不送 PostToolUse、改送這個。Bash／PowerShell 指令非零結束時：
    - 前段已經寫下去的檔照樣進 modified_files（閱讀路徑量尺、寫碼查核都讀它）與目標樹的待對照改動；例：`cat > a.py <<EOF … && pytest`
      測試紅了，a.py 已經改了。目標用成功路徑同一支 write_paths_from_tool 算；失敗的指令不一定寫到，只記這次開始後改過的現存檔，目標不明的不記。
    - 測試指令紅了記紅測（failing_tests）與驗證收據，跟成功路徑同一套函式；失敗事件沒有 tool_response，錯誤全文（"Exit code N\\n輸出…"）
      在 error 欄，當字串回應餵進去。error 裡讀不到結束碼（指令沒跑或沒跑完，例：被 hook 擋下）不算測試結果。
    只記帳不擋；裁判子 session 只讀既有 state（不重建 atom index）、不記紅測、不送提示。"""
    tool_name = input_data.get("tool_name", "") or ""
    session_id = input_data.get("session_id", "") or ""
    if tool_name not in ("Bash", "PowerShell") or not session_id:
        output_nothing()
        return
    cwd = input_data.get("cwd", "") or ""
    judge = bool(os.environ.get("CLAUDE_COMPANION_JUDGE"))
    if judge:
        from wg_core import read_state as _read_state
        state = _read_state(session_id) or {"session": {"id": session_id, "cwd": cwd}, "turn_seq": 0, "judge": True}
    else:
        state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return
    aid = str(input_data.get("agent_id") or "")
    command = str((input_data.get("tool_input") or {}).get("command") or "")
    noted = _note_failed_writes(state, input_data, tool_name, session_id, aid, cwd) if _write_paths_from_tool is not None else []
    dirty = bool(noted)
    event = {**input_data, "tool_response": str(input_data.get("error") or "")}
    if exit_code_of(event["tool_response"]) is not None:
        if not judge and _track_test_result(state, event, command, tool_name, config):
            dirty = True
        try:
            if _track_sentinels(state, event, command, tool_name, config, session_id):
                dirty = True
                _observe_scope_run(state, event, session_id, config)
        except Exception as e:  # noqa: BLE001
            print(f"[verify-ledger] error (fail-open): {e}", file=sys.stderr)
            _atom_debug_error("post_tool_use_failure:verify_ledger", e)
    advisories = [] if judge else _need_goal_stamp_failed(state, session_id, noted, aid, cwd, config)
    note = state.pop("_verify_scope_advisory", None)                 # 裁判不注入；漏判已入帳，下次宣告時送回
    if note and not judge:
        advisories.append(str(note))
    if dirty:
        write_state(session_id, state)
    if advisories:
        output_json({"hookSpecificOutput": {"hookEventName": "PostToolUseFailure", "additionalContext": "\n".join(advisories)}})
    else:
        output_nothing()


def _note_failed_writes(state: Dict[str, Any], input_data: Dict[str, Any], tool_name: str, session_id: str,
                        aid: str, cwd: str) -> List[str]:
    """失敗指令寫到的檔記進 modified_files，回記了哪些。指令開始時間從 transcript 找；找不到就只要存在就記，並浮一行。"""
    started = _tool_started_at(str(input_data.get("transcript_path") or ""), str(input_data.get("tool_use_id") or ""))
    if started is None:
        print("[post_tool_use_failure] 找不到這次工具呼叫的開始時間，失敗指令的目標檔只要存在就記成改過（可能多記沒寫到的檔）",
              file=sys.stderr)
    noted: List[str] = []
    try:
        for p in _write_paths_from_tool(tool_name, input_data.get("tool_input") or {}, cwd or (state.get("session") or {}).get("cwd") or "") or []:
            if not p or p.startswith("UNKNOWN:") or _is_ephemeral_path(p) or not os.path.isfile(p):
                continue
            if started is not None and os.path.getmtime(p) < started - 2:      # 指令開始前就是這樣：沒寫到（失敗在寫之前）
                continue
            _note_modified(state, session_id, p, tool_name, aid)
            noted.append(p)
    except Exception as e:  # noqa: BLE001
        _atom_debug_error("post_tool_use_failure:write_paths_from_tool", e)
    return noted


def _need_goal_stamp_failed(state: Dict[str, Any], session_id: str, noted: List[str], aid: str, cwd: str,
                            config: Dict[str, Any]) -> List[str]:
    """失敗指令寫到的檔蓋進目標樹的待對照改動、新收據蓋號（成功路徑 _need_goal_after_tool 的 Bash 段，目標換成真的寫到的檔）。
    回要送回 AI 的提示；出錯只 stderr，不影響記帳。"""
    import wg_need_goal as ng
    turn = int(state.get("turn_seq", 0))
    try:
        if not ng.cfg_for_cwd(config, cwd or str((state.get("session") or {}).get("cwd") or ""))["enabled"]:
            return []
        lines = [ln for ln in (ng.stamp_edit(session_id, p, aid, turn, config) for p in noted) if ln]
        ng.stamp_receipts(session_id, state, turn)
        return lines
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] PostToolUseFailure 蓋號失敗：{type(e).__name__}: {e}", file=sys.stderr)
        return []


def _tool_started_at(transcript_path: str, tool_use_id: str) -> Optional[float]:
    """transcript 尾段（最後 512KB）找這次 tool_use 那筆 assistant 紀錄的時間（epoch 秒）；找不到或讀不到回 None。"""
    from datetime import datetime
    if not transcript_path or not tool_use_id:
        return None
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - 512 * 1024))
            tail = fh.read().decode("utf-8", "replace")
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        if tool_use_id not in line:
            continue
        try:
            rec = json.loads(line)
            if rec.get("type") == "assistant" and rec.get("timestamp"):
                return datetime.fromisoformat(str(rec["timestamp"]).replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            continue
    return None


def handle_post_tool_use(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        sys_msgs, ctx_msgs = _run_companion_hooks(input_data, config)
        _emit_post_tool_output(ctx_msgs, sys_msgs)
        return
    _hook_lap("讀 state")

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    # NotebookEdit 的路徑欄位是 notebook_path，映射進同一條 modified_files 軌
    file_path = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")

    # dirty-flag 模式：本函式所有 state 變異只標 dirty，函式尾單次 write_state
    # （原先單事件最多 5 次全量寫）。殘餘競窗：read（_ensure_state）→ 尾端 write
    # 之間他 hook 行程的寫入會被本次覆蓋——write_state 的 msvcrt lock 只保護單次
    # 寫入原子性，不涵蓋整段 R-M-W；要全程上鎖需把 lock 提出 write_state 重構
    # 所有 caller，改動過大，接受此窗（同 turn 內 PostToolUse 序列執行，實際窗極小）。
    dirty = False
    aec_reject_msgs: List[str] = []   # anti_evasion_report 分支填；尾端併入 advisories 回給模型

    # ─── 救援日誌：工具呼叫命中已注入 atom 的高特異 token → rescue-log ───
    try:
        from wg_rescue import check_rescue_hits
        if check_rescue_hits(state, session_id, tool_name, tool_input):
            dirty = True
    except Exception as e:
        print(f"rescue check error: {e}", file=sys.stderr)

    # ─── 工具結果體積：每筆量長度落 per-session 檔（不進 state）；單筆超門檻 → advisory ───
    try:
        from wg_friction import record_tool_result
        _trs_adv = record_tool_result(
            state, session_id, tool_name, tool_input, input_data.get("tool_response"), config,
            base_dir=WORKFLOW_DIR,
        )
        if _trs_adv:
            state["_tool_result_advisory"] = _trs_adv
            dirty = True
    except Exception as e:
        print(f"tool result size error: {e}", file=sys.stderr)

    # ─── sub-agent 注入歸因記錄 ───────────────────────────────
    # PostToolUse 對 Agent/Task 自足：tool_response 含 agentId / content / prompt
    # （注入後的完整 prompt）。從 blob marker 回推注入清單 + 擷取輸出摘要，
    # keyed by agentId 寫入 state，供注入→使用→結果歸因。
    if tool_name in ("Agent", "Task"):
        try:
            if _record_subagent_injection(state, input_data):
                dirty = True
        except Exception as e:
            print(f"sub-agent inject record error: {e}", file=sys.stderr)

    if tool_name in ("Edit", "Write") and file_path:
        _maybe_auto_roll_changelog(file_path, config)
        _maybe_sync_skill_index(file_path, config)

    if tool_name in ("Edit", "Write", "NotebookEdit", "Bash", "PowerShell"):
        # 產出物帳本：這次工具呼叫建立的檔、資料夾、git 工作樹／分支／臨時 repo → 進帳，HUD 現場查還在的列出來。
        try:
            aec_ledger.record_tool_artifacts(
                session_id, tool_name, tool_input,
                input_data.get("cwd", "") or state.get("session", {}).get("cwd", "") or os.getcwd(),
                int(state.get("turn_seq", 0)))
        except Exception as e:
            _atom_debug_error("post_tool_use:aec_ledger_write", e)

    # 本 session 新建的檔（呼叫前不存在）→ state created_files：動資料檔閘的事實 (c)，暫存檔也記。
    # Write 看結果 type=create；Bash／PowerShell 看 PreToolUse 記下的呼叫前不存在的目標
    if wg_data_file.note_created(state, tool_name, file_path, input_data.get("tool_response")):
        dirty = True
    if wg_data_file.confirm_shell_created(state, str(input_data.get("tool_use_id") or "")):
        dirty = True
    # ── OldTestDeclare（T2.17）：Bash／PowerShell／NotebookEdit 改了既有測試 → 拿 PreToolUse 拍的改前快照比，沒宣告的記 state，
    # 下一個工具呼叫在 PreToolUse 擋；Edit／Write 撤回了欠帳的那一筆就清掉。比對失敗只能 stderr＋留帳（事後擋不了這一次）。
    if tool_name in ("Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "PowerShell"):
        try:
            if wg_oldtest.after_tool(state, input_data, config):
                dirty = True
        except Exception as e:
            print(f"[Guardian:OldTestDeclare] 事後比對失敗（這次改測試檔沒核對到）：{type(e).__name__}: {e}", file=sys.stderr)
            append_guard_log("old_test", {"event": "after_error", "session": session_id, "tool": tool_name,
                                          "error": f"{type(e).__name__}: {e}"})

    if (
        tool_name in ("Edit", "Write", "NotebookEdit", "MultiEdit")
        and file_path
        and not _is_ephemeral_path(file_path)
    ):
        _note_modified(state, session_id, file_path, tool_name, str(input_data.get("agent_id") or ""))

        edit_counts = state.setdefault("edit_counts", {})
        edit_counts[file_path] = edit_counts.get(file_path, 0) + 1

        if WISDOM_AVAILABLE:
            try:
                wisdom_track_retry(state, file_path)
            except Exception as e:
                print(f"Wisdom retry track error: {e}", file=sys.stderr)

        try:
            qf = _check_output_quality(file_path, session_id, config)
            if qf:
                state.setdefault("quality_feedback", {}).setdefault(
                    "rewritten_files", []
                ).append(qf)
                print(
                    f"Quality feedback: {file_path} was also modified "
                    f"in session {qf['original_session']}",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"Quality check error: {e}", file=sys.stderr)

        dirty = True

        normalized = file_path.replace("\\", "/")
        if "/memory/" in normalized and normalized.endswith(".md"):
            _trigger_incremental_index(config)

        if "/_staging/" in normalized and normalized.endswith(".md"):
            # 只檢 _staging/ 頂層檔：子資料夾是多檔工作區（彙整/評估文件），
            # 非 /continue 交接入口，不套 next-phase 命名慣例
            staging_tail = normalized.split("/_staging/", 1)[-1]
            staging_fname = staging_tail.rsplit("/", 1)[-1]
            # 命名慣例＝ `next-phase*.md`（與 wg_handoff.should_write_stub 的
            # glob、codex_companion._NEXT_PHASE_RE 同源）：多份計畫並存為常態，
            # 不得要求收斂成單一 next-phase.md。
            if "/" not in staging_tail and not staging_fname.startswith("next-phase"):
                state["_staging_advisory"] = (
                    f"⚠ `_staging/{staging_fname}` 非標準檔名。"
                    f"/continue 掃 `next-phase*.md`。"
                    f"建議重新命名：mv → next-phase-<主題>.md"
                )
                print(
                    f"Staging name gate: {staging_fname}", file=sys.stderr
                )

        _claude_projects_pat = "/.claude/projects/"
        if _claude_projects_pat in normalized and "/memory/" in normalized:
            _proj_root = state.get("atom_index", {}).get("project_root", "")
            if _proj_root:
                _rel_part = normalized.split("/memory/", 1)[-1]
                _exempt = (
                    _rel_part == "MEMORY.md"
                    or _rel_part.startswith("episodic/")
                    or _rel_part == "access.json"
                )
                if not _exempt:
                    _proj_root_norm = _proj_root.replace("\\", "/")
                    _correct_base = f"{_proj_root_norm}/.claude/memory/"
                    state["_path_enforcement_advisory"] = (
                        f"🚫 **路徑錯誤** — 寫入了舊個人層路徑 `~/.claude/projects/*/memory/`。\n"
                        f"規則：專案記憶必須寫到 `{_correct_base}`。\n"
                        f"正確路徑：`{_correct_base}{_rel_part}`\n"
                        f"請立即搬移檔案並刪除錯誤路徑的副本。"
                    )
                    print(
                        f"Path enforcement BLOCKED: {normalized} → should be {_correct_base}{_rel_part}",
                        file=sys.stderr,
                    )

        if "/_AIDocs/" in normalized or "/_aidocs/" in normalized.lower():
            fname = normalized.rsplit("/", 1)[-1]
            if is_plan_filename(fname):
                state["_aidocs_advisory"] = (
                    f"⚠ {fname} 看起來是暫時性文件，"
                    f"建議放 memory/_staging/ 而非 _AIDocs/。"
                    f"判斷基準：實作完成後是否仍有長期參考價值？"
                )
                print(f"AIDocs gate triggered: {fname}", file=sys.stderr)

        if DOCDRIFT_AVAILABLE and config.get("docdrift", {}).get("enabled", True):
            try:
                if "/_aidocs/" in normalized.lower():
                    resolve_doc_update(file_path, state, config)
                else:
                    check_source_drift(file_path, state, config)
                dirty = True
            except Exception as e:
                print(f"DocDrift error: {e}", file=sys.stderr)

    elif tool_name in ("Bash", "PowerShell"):
        command = tool_input.get("command", "")
        # 寫碼查核 (c)「說試過／跑了」看本回合有沒有執行過指令：記最後一次執行的 turn_seq（主 session 用 sid、子代理用它自己的收據鍵），
        # 同伴訊息讓 transcript 另起一段之後，同一個使用者回合裡較早跑的指令照樣算（規則 TURN_SINCE_USER_PROMPT）
        _exec_aid = str(input_data.get("agent_id") or "")
        _exec = state.setdefault("exec_turn_seq", {})
        _exec_key = agent_receipt_key(session_id, _exec_aid) if _exec_aid else session_id
        _exec.pop(_exec_key, None)                                          # 重新插入排到最後，超量時先丟最久沒執行的
        _exec[_exec_key] = int(state.get("turn_seq", 0))
        for _old in list(_exec)[:-EXEC_TURN_KEYS_CAP]:
            _exec.pop(_old, None)
        dirty = True
        if re.search(r"\b(git\s+(log|blame|show|diff)|svn\s+(log|blame|diff))\b", command):
            vcs = state.setdefault("vcs_queries", [])
            vcs.append({"command": command[:200], "at": _now_iso()})
            dirty = True

        # Bash／PowerShell 改檔目標（>、>>、tee、sed -i、cp、mv、Set-Content…）也進 modified_files；
        # 先記目標再落帳，帳本的 modified_files_turn 才含本次寫入；commit 快照也在記完之後才拍
        # （`sed -i a.py && git commit` 這種同一條指令改檔又 commit，快照要看得到這次改了 a.py）
        _writes_ok = True
        if _write_paths_from_tool is not None:
            try:
                _cwd = input_data.get("cwd", "") or state.get("session", {}).get("cwd", "") or ""
                _aid = str(input_data.get("agent_id") or "")
                for _p in _write_paths_from_tool(tool_name, tool_input, _cwd) or []:
                    if _p and _p.startswith("UNKNOWN:"):    # 目標不明：記未知寫入（子代理 Stop 據此擋到底），不當成某個檔
                        _note_unknown_write(state, session_id, _p, command, tool_name, _aid)
                    elif _p and not _is_ephemeral_path(_p):
                        _note_modified(state, session_id, _p, tool_name, _aid)
                    else:
                        continue
                    dirty = True
            except Exception as e:
                _atom_debug_error("post_tool_use:write_paths_from_tool", e)
                _writes_ok = False
        # 規則 MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE：記搬了哪個程式目錄（子代理搬的也記，帶 agent_id）、掃描工具的命中清單
        # （Stop 寫碼查核 (v) 用）
        try:
            _mv_cwd = input_data.get("cwd", "") or state.get("session", {}).get("cwd", "") or ""
            if _note_moved_code_dirs(state, session_id, tool_name, tool_input, _mv_cwd, config,
                                     agent_id=str(input_data.get("agent_id") or "")):
                dirty = True
            if _note_move_scan_hits(state, command, input_data.get("tool_response"), _mv_cwd):
                dirty = True
        except Exception as e:  # noqa: BLE001
            print(f"[Guardian:ReconcileGate] 記搬目錄事實失敗（不影響這次工具）：{type(e).__name__}: {e}", file=sys.stderr)

        if _note_commit(state, command, config, session_id, snapshot=_writes_ok):
            dirty = True
            import wg_gate_bypass  # T2.19：commit 跑完、落在上次被病形閘擋的 repo → 清掉 smell_deny_last
            wg_gate_bypass.note_commit_done(state, session_id, command, tool_name, input_data.get("cwd", "") or "")

        if _track_test_result(state, input_data, command, tool_name, config):
            dirty = True
        try:
            if _track_sentinels(state, input_data, command, tool_name, config, session_id):
                dirty = True
                _observe_scope_run(state, input_data, session_id, config)
        except Exception as e:
            print(f"[verify-ledger] error (fail-open): {e}", file=sys.stderr)
            _atom_debug_error("post_tool_use:verify_ledger", e)

    elif tool_name.endswith("anti_evasion_report"):
        # MCP 結構化收尾 emit（one-writer spine）：MCP tool 只回 chip、不碰 state；
        # 由此 PostToolUse 分支獨佔寫 state + 落 per-turn 報告檔 + 判 HUD fallback。
        # session_id 用原始 input_data["session_id"]（與 modified_files 的 session_id 戳
        # 同源）＝sibling 隔離關鍵：Stop 閘以 turn_seq+session_id 雙鍵讀，隔壁 session 的
        # emit 不誤放行本 session。turn_seq 由 UserPromptSubmit 每真 prompt +1。
        _AEC_KEYS = ("a", "b", "d", "e", "f", "g", "h", "i")   # (c) Token 警示欄已刪（與 85% 預警重複）；舊客戶端送來照收不存
        vals = {k: str(tool_input.get(k, "") or "") for k in _AEC_KEYS}
        # (j)(k)：鍵不存在＝舊格式呼叫（MCP 還沒載到新 schema），不寫進報告、Stop 也不拿它擋；明給空字串才擋
        for _k in ("j_evidence_path", "k_followups"):
            if _k in tool_input:
                vals[_k] = str(tool_input.get(_k) or "")
        a, b = vals["a"], vals["b"]
        # (i) 是給使用者裁決的路徑清單：「無（…括號解釋…）」一律正規化成「無」，
        # 模型的多嘴說明（執行期狀態檔、已刪了什麼）不得變成 HUD 上要人裁決的一列。
        if _aec_blank(vals["i"]):
            vals["i"] = "無"
        i_paths = vals["i"]
        turn_seq = int(state.get("turn_seq", 0))
        sev = aec_severity(a, b)
        # (b) 欄 cross-check：hook 實測到退避但模型自評「無」→ 升 real-evasion +
        # 附 hook 證據（升級只發生在 Python one-writer；Node chip 純內容判定，
        # 顯示可能不同步——report 檔 + Stop fallback 為準）。
        evidence = _collect_aec_evidence(state, session_id)
        sev, upgraded = crosscheck_aec_severity(sev, b, evidence)
        report = {
            "session_id": session_id,
            "turn_seq": turn_seq,
            **vals,
            "severity": sev,
            "at": _now_iso(),
        }
        if upgraded:
            report["severity_upgraded_by"] = "hook:evasion-crosscheck"
            report["hook_evidence"] = evidence[-5:]
            # (b) 卡片只渲染 b 欄；升級卻留「無」會出現「紅框指著空卡」（可觀測性
            # 鐵律：訊號必須帶內容浮出）。把 hook 證據寫進 b，模型原自評另存 b_model。
            report["b_model"] = b
            ev_lines = "；".join(
                f"turn {e.get('turn_seq', '?')}『{e.get('phrase', '')}』"
                for e in evidence[-5:] if e.get("phrase")
            )
            report["b"] = (
                f"模型自評「{b or '無'}」，但 hook 實測 {len(evidence)} 筆退避命中：{ev_lines}"
                "（cross-check 升級，不信自評）"
            )
        # (d)/(h) pending：把「記憶寫入」推到之後（尚未寫／見下一動／下一動＝寫 atom）。
        # 報告是收尾檢核，不是待辦清單——落 d_pending 供 HUD 標紅，並回告模型當回合補寫；
        # Stop 端讀 d_pending 擋一次（AEC-Pending Gate），逼 atom_write 後重新 emit。
        # 本 turn 已有 validated 收割 → (d) 的記憶收錄帳已由收割核對過，不再判 d_pending；(h) 照舊。
        hv_done = validated_this_turn(state, session_id, turn_seq)
        pending = aec_pending_items("" if hv_done else vals["d"], vals["h"])
        # (d) 只寫「見收割報告」：本使用者回合要真的交過核對過的收割報告，否則這份記憶收錄帳等於沒寫
        if not hv_done and re.match(r"^\s*見收割報告", vals["d"]):
            pending.insert(0, "(d) 寫「見收割報告」，但本回合沒有核對過的收割報告（先呼叫 knowledge_harvest_report）")
        if pending:
            report["d_pending"] = pending
            aec_reject_msgs.append(
                f"[Guardian:AEC-Pending] (d)/(h) 有 {len(pending)} 項把記憶寫入推到之後：\n"
                + "\n".join(f"  ✗ {x}" for x in pending)
                + "\n值得寫就現在 atom_write 寫完，再重新呼叫 anti_evasion_report 把該項改成"
                "「→ 已寫入 atom <名>」（或「→ 不寫（理由）」）；否則 Stop 會擋。"
            )
        # (j) 證據持久路徑：本 session 有驗證收據時必須給真存在的路徑；模型留空／「無」而帳本在 → 系統帶入帳本絕對路徑
        # （帳本在資料根，跟專案 cwd 不同根）。(k) 追蹤項：空字串不收（「無」可）。
        # 判定落 report 供 HUD 標紅；Stop 的對帳閘 (e) 讀 report 裡（帶入後）的 j，以同一對函式擋。
        if "j_evidence_path" in vals:
            _has_receipts = bool(receipts_of(state, session_id))
            _ledger = str(ledger_path(session_id, WORKFLOW_DIR))
            _j = aec_evidence_autofill(vals["j_evidence_path"], _has_receipts, _ledger)
            if _j != vals["j_evidence_path"]:
                vals["j_evidence_path"] = report["j_evidence_path"] = _j
                report["j_autofilled"] = True
                aec_reject_msgs.append(f"[Guardian:AEC-Evidence] (j) 已自動帶入 {_j}（本 session 的驗證收據帳本），不必重送。")
            report["j_missing"] = aec_evidence_missing(_j, _has_receipts)
        if "k_followups" in vals:
            report["k_missing"] = aec_followups_missing(vals["k_followups"])
        if report.get("j_missing"):
            aec_reject_msgs.append(
                "[Guardian:AEC-Evidence] (j) 證據持久路徑缺或不存在，但本 session 有驗證收據。"
                f"留空讓系統帶入帳本（{ledger_path(session_id, WORKFLOW_DIR)}），或填其他真存在的證據檔絕對路徑，再重新 emit；"
                "否則 Stop 會擋。"
            )
        if report.get("k_missing"):
            aec_reject_msgs.append("[Guardian:AEC-Followups] (k) 追蹤項是空字串：有就一行一項，沒有寫「無」；否則 Stop 會擋。")
        # (k) 追蹤項 → workflow/tracking/<slug>.jsonl（k=「無」不寫；slug＝tracking_slug(cwd)：最近部位表根 → 專案根 → cwd，
        # 根層是 c--users-<user>--claude；cwd 空寫 _no-cwd 並 stderr；讀回端 wg_overview／session_start 用同一支）
        try:
            from wg_harvest import tracking_entries, append_tracking, tracking_slug
            _k_entries = tracking_entries(session_id, turn_seq, vals.get("k_followups", ""))
            if _k_entries:
                _k_cwd = state.get("session", {}).get("cwd", "") or input_data.get("cwd", "")
                append_tracking(tracking_slug(_k_cwd), _k_entries)
        except ImportError:
            print("[Guardian:AEC] wg_harvest.tracking_entries 尚未合併（track-c），(k) 追蹤項本次不入 workflow/tracking", file=sys.stderr)
        except Exception as e:
            _atom_debug_error("post_tool_use:aec_tracking", e)
        # 目前的寫碼類需求目標樹（原話摘要＋節點＋對照結果）附進報告，HUD 顯示「目標對照」；收尾檢核本身不多欄
        try:
            import wg_need_goal as _ng
            _ng_cwd = state.get("session", {}).get("cwd", "") or input_data.get("cwd", "") or ""
            _ng_on = _ng.cfg_for_cwd(config, _ng_cwd)["enabled"]
            _ng_snap = _ng.snapshot_for_report(session_id) if _ng_on else None
            if _ng_snap:
                report["need_goal"] = _ng_snap
            if _ng_on:
                # 收尾檢核之後就是收尾報告（常帶下一步、開工句）：交出前一問在這裡也送一次
                aec_reject_msgs.append(f"[NeedGoal] 收尾檢核收下。{_ng.handout_check_text(session_id)}")
        except Exception as e:
            _atom_debug_error("post_tool_use:aec_need_goal", e)
        state["anti_evasion_report"] = report
        _write_aec_report_file(session_id, turn_seq, report)
        # 殘檔帳本：(i) 一行一路徑宣告 + session scratchpad 掃描 → 進帳（HUD 讀帳本 + exists()）。
        # (i) 裡的受保護路徑（VCS 追蹤檔 / memory、_AIDocs / 索引類）拒收並回告模型——
        # 「已改未 commit 的正式檔」屬 (a)(b)/(g) 未同步事項，不是衍生暫存；靜默丟掉會讓模型一直錯報。
        try:
            _cwd = state.get("session", {}).get("cwd", "") or input_data.get("cwd", "")
            _rejected: List[Dict[str, str]] = []
            aec_ledger.collect_at_completion(session_id, _cwd, i_paths, turn_seq, rejected=_rejected)
            if _rejected:
                _protected = any(not r["path"].startswith("branch:") for r in _rejected)
                aec_reject_msgs.append(
                    "[Guardian:AEC-Ledger] (i) 衍生暫存清單有幾行沒收下：\n"
                    + "\n".join(f"  ✗ {r['path']} — {r['reason']}" for r in _rejected)
                    + ("\n受保護路徑是正式產出、不是暫存，不得進 HUD 刪除候選：未 commit 的正式檔請改列於 (a)/(b)/(g)；"
                       "(i) 只放你自己產生的暫存／中間產物。" if _protected else "")
                )
        except Exception as e:
            _atom_debug_error("post_tool_use:aec_ledger_collect", e)
        _maybe_spawn_hud(sev, state, config, session_id)
        dirty = True

    elif tool_name.endswith("atom_write") or tool_name.endswith("atom_retire"):
        # atom 工具成功時結果最後一行 `receipt: {json}`（失敗呼叫沒有 receipt → 不記）。
        # 入帳 state["atom_ops"][sid]，收割回報用它逐項核對（exists()/全域 resolver 驗不出
        # 專案層 atom、append 是否真發生、索引是否成功；receipt 可以）。
        receipt = parse_receipt(input_data.get("tool_response"))
        if receipt:
            record_atom_op(state, session_id, int(state.get("turn_seq", 0)), receipt)
            dirty = True
            if tool_name.endswith("atom_write"):
                # 來源自動填：剛建／改的 atom 補 Source／Quote（失敗只記 log，不阻斷）
                from wg_provenance import autofill_from_receipt
                autofill_from_receipt(receipt, input_data, state)

    elif tool_name.endswith("knowledge_harvest_report"):
        # 收割回報（one-writer）：items ↔ 本 session 自上次 validated 收割以來的 receipts 逐項核對，
        # 落本 session 分區 + ledger；核不過 → pending（Stop 的 Harvest-Pending 閘擋一次要求補）。
        # MCP 端已拒收（isError）的呼叫不是回報：不核對、不落分區、不 spawn，否則拒收的 items
        # 會被當成 validated 放行。
        if is_error_response(input_data.get("tool_response")):
            print("[Guardian:Harvest] knowledge_harvest_report 被 MCP 拒收，本次不核對", file=sys.stderr)
        else:
            turn_seq = int(state.get("turn_seq", 0))
            sec = apply_report(state, session_id, turn_seq, tool_input.get("items"), tool_input.get("note", ""))
            append_ledger(session_id, {
                "at": sec["at"], "session_id": session_id, "turn_seq": turn_seq,
                "validated": sec["validated"], "items": sec["items"], "pending": sec["pending"],
                "retired_paths": sec["retired_paths"], "note": sec["note"],
            }, base_dir=WORKFLOW_DIR)
            if sec["validated"]:
                # 本回合（規則 TURN_SINCE_USER_PROMPT，同伴訊息不另開回合）先 emit 的 AEC 報告：(d) 的記憶收錄帳
                # 已由收割核對過 → 用 (h) 重算 d_pending。(d)/(h) 共用 d_pending，整個 pop 會把 (h)「下一動＝寫 atom」一起放掉。
                aec = state.get("anti_evasion_report") or {}
                if (aec.get("session_id") == session_id and in_user_turn(aec.get("turn_seq"), state, turn_seq)
                        and aec.get("d_pending")):
                    still = aec_pending_items("", aec.get("h", ""))
                    if still:
                        aec["d_pending"] = still
                    else:
                        aec.pop("d_pending", None)
                    _write_aec_report_file(session_id, turn_seq, aec)
                _cwd = state.get("session", {}).get("cwd", "") or input_data.get("cwd", "")
                if spawn_vcs_sync is None:
                    print("[Guardian:Harvest] wg_vcs_sync 不可用，記憶目錄未背景上版控（fail-open）", file=sys.stderr)
                else:
                    # retired_paths 只帶本次 validated 且有 ok:true retire receipt 的退役檔（apply_report 算好）。
                    try:
                        spawn_vcs_sync(session_id, _cwd, reason="harvest", retired_paths=sec["retired_paths"])
                    except Exception as e:
                        print(f"[Guardian:Harvest] spawn_vcs_sync failed (fail-open): {e}", file=sys.stderr)
            else:
                aec_reject_msgs.append(
                    f"[Guardian:Harvest-Pending] 收割回報有 {len(sec['pending'])} 項核不過："
                    + "".join("\n  ✗ " + x for x in sec["pending"][:6])
                    + "\n先用 atom_write／atom_retire 真的做完（或改 action=skip 附 reason），"
                    "再重新呼叫 knowledge_harvest_report；否則 Stop 會擋。"
                )
            dirty = True

    # 分段計時（wg_hook_timing）：累計過 hook 上限的 80% → degraded，後面只記不問——提示類段落（導讀卡、depends 召回、
    # 跨 session 碰撞、同伴檢查、MCP 切入點註記）不跑；docdrift 清帳、讀入範圍、目標樹蓋號、寫 state 照做
    degraded = _hook_lap("工具記帳")
    if DOCDRIFT_AVAILABLE and config.get("docdrift", {}).get("enabled", True):
        try:
            if prune_committed_entries(state, config) > 0:
                dirty = True
        except Exception as e:
            _atom_debug_error("post_tool_use:docdrift_prune", e)
            pass

    # OverviewHub：Read／Bash／PowerShell 讀到某部位第一個檔 → 整張注入導讀卡；已注入 → 記注入後讀檔數（fail-open）
    hub_ctx = None
    if not degraded and tool_name in ("Read", "Bash", "PowerShell", "Grep"):      # Grep：規則 GREP_CONTENT_IS_READ（wg_overview._read_paths）
        try:
            from wg_overview import on_read as _hub_on_read
            hub_ctx = _hub_on_read(
                state, session_id, tool_name, tool_input, input_data.get("cwd", "") or "",
                input_data.get("transcript_path", "") or "", config,
                exit_code=_read_exit_code(input_data.get("tool_response")),   # 規則 BASH_READONLY_COUNTS_AS_READ：失敗的讀不算
            )
            dirty = True   # reads_after 也要落盤
        except Exception as e:
            print(f"overview hub read error: {e}", file=sys.stderr)

    degraded = _hook_lap("導讀卡")

    # 需求目標 4.3 讀入範圍：讀到的部位與頂層目錄記進目標樹（不看 OverviewHub 開關；提示由 PostToolBatch 合併送）；
    # 「讀了什麼」與上面 on_read 同一支（wg_overview.read_targets），所以工具清單也相同
    if tool_name in ("Read", "Bash", "PowerShell", "Grep"):
        try:
            from wg_need_goal_points import scope_on_read
            if scope_on_read(state, session_id, tool_name, tool_input, input_data.get("cwd", "") or "", config):
                dirty = True   # need_goal_batch 要落盤
        except Exception as e:  # noqa: BLE001
            print(f"[NeedGoal] 讀入範圍記錄失敗（不影響讀檔）：{type(e).__name__}: {e}", file=sys.stderr)

    # Depends 召回（A3.5）：讀到的檔若是某張卡的壞滅緣（索引 depends path:），一行一卡指標；文件／計畫檔命中 authority_map 一次性注入地圖
    dep_ctx = None
    if not degraded and tool_name in ("Read", "Bash", "PowerShell"):
        try:
            from wg_depends import on_read_depends as _on_read_depends
            dep_ctx = _on_read_depends(state, session_id, tool_name, tool_input, input_data.get("cwd", "") or "", config)
            if dep_ctx:
                dirty = True   # depends_hints／authority_map_injected 要落盤
        except Exception as e:
            print(f"depends recall error: {e}", file=sys.stderr)

    _hook_lap("綜觀與召回")
    ng_ctx, ng_changed = _need_goal_after_tool(state, session_id, tool_name, tool_input, input_data, config)
    dirty = dirty or ng_changed
    _hook_lap("目標樹")

    advisories = list(aec_reject_msgs)
    if ng_ctx:
        advisories.append(ng_ctx)
    if hub_ctx:
        advisories.append(hub_ctx)
    if dep_ctx:
        advisories.append(dep_ctx)
    if state:
        for key, prefix in [
            ("_path_enforcement_advisory", "[Guardian:PathEnforce]"),
            ("_aidocs_advisory", "[Guardian:AIDocs]"),
            ("_staging_advisory", "[Guardian:StagingName]"),
            ("_docdrift_advisory", "[Guardian:DocDrift]"),
            ("_tool_result_advisory", "[Guardian:ToolResultSize]"),
            ("_verify_scope_advisory", ""),                  # 自帶 [Guardian:VerifyScope] 開頭
        ]:
            val = state.get(key)
            if val:
                advisories.append(f"{prefix} {val}" if prefix else str(val))
                del state[key]
                dirty = True

    # 函式尾單次寫（dirty-flag 收斂）
    if dirty:
        write_state(session_id, state)
    degraded = _hook_lap("寫 state")

    # ─── 跨 session late-collision（寫後補償；必須在 write_state 之後查——
    # 兩 session 同時首寫時，寫前掃描雙方都看不見對方，落盤後才可見）───
    if (
        not degraded
        and (config.get("coordination") or {}).get("enabled", False)
        and tool_name in ("Edit", "Write", "NotebookEdit")
        and file_path
        and not _is_ephemeral_path(file_path)
    ):
        try:
            from wg_coordination import (
                check_cross_session_conflict, format_late_collision,
                _warn_cache_suppressed, _norm_path,
            )
            _hit = check_cross_session_conflict(
                session_id, file_path, config,
                entry_window_s=60, use_cache=False, ev="late_collision",
            )
            if _hit:
                # log 恆記；advisory 僅在 PreToolUse 近期未警過同檔時附加（防洗版）
                _sup_s = float((config.get("coordination") or {}).get("warn_suppress_min", 10)) * 60
                if not _warn_cache_suppressed(session_id, _norm_path(file_path), _sup_s):
                    _msg = format_late_collision(_hit)
                    advisories.append(_msg)
                    print(_msg, file=sys.stderr)
        except Exception as e:
            _atom_debug_error("post_tool_use:late_collision", e)

    # 併入的兩支輕檢查放在 write_state 之後：acceptance_spec 從磁碟讀 state 數修改檔，
    # 讓本次事件的檔已入帳（原本兩程序並行時先後不定）
    degraded = _hook_lap("跨 session 碰撞")
    sys_msgs, ctx_msgs = ([], []) if degraded else _run_companion_hooks(input_data, config)
    advisories.extend(ctx_msgs)
    degraded = _hook_lap("同伴檢查")
    # 切入點契約（TECH §7.10）：MCP 工具的回覆（工具本體回的文字＋上面補的提醒）認得出切入點就接判準卡並留帳
    if not degraded and tool_name.startswith("mcp__"):
        _mcp_text = "\n".join([response_text(input_data.get("tool_response")), *advisories])
        _note = entry_note(_mcp_text, "mcp_reply", session_id=session_id, state=state, config=config)
        if _note:
            advisories.append(_note)
    _emit_post_tool_output(advisories, sys_msgs)
