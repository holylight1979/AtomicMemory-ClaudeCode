"""
handlers/post_tool_use.py — PostToolUse hook handler

追蹤 modified_files / vcs_queries（accessed_files 由 Stop 端從 transcript 尾段
一次回收，matcher 不含 Read——省去每次讀檔一個 hook 行程）；
偵測測試失敗、_CHANGELOG 自動 roll、staging 命名、路徑強制、docdrift、hot cache mid-turn 注入。
"""

import json
import re
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
    aec_evidence_missing, aec_followups_missing, next_event_seq, has_cd, env_snapshot, commit_snapshot, reconcile_cfg,
    head_new_code, _git_root_of,
)
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
from handlers._shared import (
    _hud_alive,
    _is_ephemeral_path,
    WISDOM_AVAILABLE, wisdom_track_retry,
    DOCDRIFT_AVAILABLE, check_source_drift, resolve_doc_update, prune_committed_entries,
)


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


def _track_test_result(state: Dict[str, Any], input_data: Dict[str, Any], command: str,
                       tool: str = "Bash") -> bool:
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
        })
        return True
    if not state.get("failing_tests"):
        return False
    cmd_prefix = command[:80].strip()
    is_pytest_success = "pytest" in command.lower()
    before = state["failing_tests"]
    after = [
        f for f in before
        if f.get("session_id") != sid          # 只清自己的；沒蓋 sid 的舊條目不是自己的
        or (
            not f.get("cmd", "").startswith(cmd_prefix[:40])
            and not (is_pytest_success and (
                f.get("pytest")
                or "pytest" in f.get("cmd", "").lower()
                or "short test summary" in f.get("summary", "")   # legacy 無 flag 者看 pytest 輸出特徵
            ))
        )
    ]
    if len(after) == len(before):
        return False
    state["failing_tests"] = after
    return True


def _note_commit(state: Dict[str, Any], command: str, config: Optional[Dict[str, Any]] = None,
                 session_id: str = "", snapshot: bool = True) -> bool:
    """跑了 git／svn commit → state["last_commit_turn_seq"]＝本回合；回有沒有記。一般與裁判 PostToolUse 共用這一條：
    ScanReport 閘據此豁免收尾檢核（工作已寫進 VCS 歷史＝可稽核），寫碼查核判「改過又原樣還原」也看它（改完 commit 了，
    工作樹乾淨不代表沒改）。同時記 commit_snapshot（本 session 改過的檔此刻的內容雜湊＋當時不欠案例的程式檔）：commit 之後
    做反證、把檔退回舊版又還原，Stop 看內容回到這個快照就不重算補案例。快照算失敗只少了這個豁免（照擋），stderr 說一聲。"""
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
    try:
        state["commit_snapshot"] = commit_snapshot(own, turn, reconcile_cfg(config or {}))
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
    主 session 的 modified_files 照舊也記，主 session 行為不變。"""
    _upsert_modified(state, state.setdefault("modified_files", []), session_id, file_path, tool_name)
    if agent_id:
        _upsert_modified(state, state.setdefault("agent_modified_files", {}).setdefault(agent_id, []),
                         session_id, file_path, tool_name)
    state["sync_pending"] = True


def _upsert_modified(state: Dict[str, Any], mods: List[Dict[str, Any]], session_id: str, file_path: str,
                     tool_name: str) -> None:
    turn = int(state.get("turn_seq", 0))
    for m in mods:
        if (
            isinstance(m, dict)
            and m.get("path") == file_path
            and m.get("session_id", session_id) == session_id
        ):
            m["count"] = int(m.get("count", 1)) + 1
            m["at"] = _now_iso()
            m["last_at"] = m["at"]
            m["last_seq"] = next_event_seq(state)
            m["tool"] = tool_name
            m["last_turn_seq"] = turn
            m.setdefault("turn_seq", turn)
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
        })


UNKNOWN_WRITES_CAP = 20


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
        for p in targets or []:
            if p and not p.startswith("UNKNOWN:") and not _is_ephemeral_path(p):
                ng.stamp_edit(session_id, p, agent_id, turn, config)
        if tool_name in ("Bash", "PowerShell"):
            ng.stamp_receipts(session_id, state, turn)
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] PostToolUse 蓋號／套用失敗（{tool_name}）：{type(e).__name__}: {e}", file=sys.stderr)
        ng._guard("stamp_error", session_id, tool=tool_name, error=f"{type(e).__name__}: {e}")
        if is_ng:
            return f"[NeedGoal] 這次 need_goal 沒寫進目標檔（{type(e).__name__}: {e}），請重新呼叫一次。", False
    return None, False


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
        _track_sentinels(state, input_data, command, tool_name, config, session_id)
    write_state(session_id, state)
    output_nothing()


def handle_post_tool_use(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        sys_msgs, ctx_msgs = _run_companion_hooks(input_data, config)
        _emit_post_tool_output(ctx_msgs, sys_msgs)
        return

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

    if tool_name in ("Edit", "Write", "NotebookEdit") and file_path:
        # 殘檔帳本：工具寫進系統 tempdir（scratchpad 等）的檔 → 進帳，HUD 以 exists() 列尚存者。
        try:
            aec_ledger.record_temp_write(session_id, file_path, int(state.get("turn_seq", 0)))
        except Exception as e:
            _atom_debug_error("post_tool_use:aec_ledger_write", e)

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

        if _note_commit(state, command, config, session_id, snapshot=_writes_ok):
            dirty = True

        if _track_test_result(state, input_data, command, tool_name):
            dirty = True
        try:
            if _track_sentinels(state, input_data, command, tool_name, config, session_id):
                dirty = True
        except Exception as e:
            print(f"[verify-ledger] error (fail-open): {e}", file=sys.stderr)
            _atom_debug_error("post_tool_use:verify_ledger", e)

    elif tool_name.endswith("anti_evasion_report"):
        # MCP 結構化收尾 emit（one-writer spine）：MCP tool 只回 chip、不碰 state；
        # 由此 PostToolUse 分支獨佔寫 state + 落 per-turn 報告檔 + 判 HUD fallback。
        # session_id 用原始 input_data["session_id"]（與 modified_files 的 session_id 戳
        # 同源）＝sibling 隔離關鍵：Stop 閘以 turn_seq+session_id 雙鍵讀，隔壁 session 的
        # emit 不誤放行本 session。turn_seq 由 UserPromptSubmit 每真 prompt +1。
        _AEC_KEYS = ("a", "b", "c", "d", "e", "f", "g", "h", "i")
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
        if pending:
            report["d_pending"] = pending
            aec_reject_msgs.append(
                f"[Guardian:AEC-Pending] (d)/(h) 有 {len(pending)} 項把記憶寫入推到之後：\n"
                + "\n".join(f"  ✗ {x}" for x in pending)
                + "\n值得寫就現在 atom_write 寫完，再重新呼叫 anti_evasion_report 把該項改成"
                "「→ 已寫入 atom <名>」（或「→ 不寫（理由）」）；否則 Stop 會擋。"
            )
        # (j) 證據持久路徑：本 session 有驗證收據時必須給真存在的路徑；(k) 追蹤項：空字串不收（「無」可）。
        # 判定落 report 供 HUD 標紅；Stop 的對帳閘 (e) 以同一對函式擋。
        if "j_evidence_path" in vals:
            report["j_missing"] = aec_evidence_missing(vals["j_evidence_path"], bool(receipts_of(state, session_id)))
        if "k_followups" in vals:
            report["k_missing"] = aec_followups_missing(vals["k_followups"])
        if report.get("j_missing"):
            aec_reject_msgs.append(
                "[Guardian:AEC-Evidence] (j) 證據持久路徑缺或不存在，但本 session 有驗證收據。"
                f"填帳本路徑 workflow/verify-ledger/{session_id}.jsonl 或其他真存在的證據檔，再重新 emit；否則 Stop 會擋。"
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
            _ng_snap = _ng.snapshot_for_report(session_id) if _ng.cfg_for_cwd(config, _ng_cwd)["enabled"] else None
            if _ng_snap:
                report["need_goal"] = _ng_snap
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
                aec_reject_msgs.append(
                    "[Guardian:AEC-Ledger] (i) 衍生暫存清單拒收受保護路徑（正式產出不是暫存，"
                    "不得進 HUD 刪除候選）：\n"
                    + "\n".join(f"  ✗ {r['path']} — {r['reason']}" for r in _rejected)
                    + "\n未 commit 的正式檔請改列於 (a)/(b)/(g)；(i) 只放你自己產生的暫存／中間產物。"
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
                # 同 turn 先 emit 的 AEC 報告：(d) 的記憶收錄帳已由收割核對過 → 用 (h) 重算 d_pending。
                # (d)/(h) 共用 d_pending，整個 pop 會把 (h)「下一動＝寫 atom」一起放掉。
                aec = state.get("anti_evasion_report") or {}
                if aec.get("session_id") == session_id and aec.get("turn_seq") == turn_seq and aec.get("d_pending"):
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

    if DOCDRIFT_AVAILABLE and config.get("docdrift", {}).get("enabled", True):
        try:
            if prune_committed_entries(state, config) > 0:
                dirty = True
        except Exception as e:
            _atom_debug_error("post_tool_use:docdrift_prune", e)
            pass

    # OverviewHub：Read／Bash／PowerShell 讀到某部位第一個檔 → 整張注入導讀卡；已注入 → 記注入後讀檔數（fail-open）
    hub_ctx = None
    if tool_name in ("Read", "Bash", "PowerShell"):
        try:
            from wg_overview import on_read as _hub_on_read
            hub_ctx = _hub_on_read(
                state, session_id, tool_name, tool_input, input_data.get("cwd", "") or "",
                input_data.get("transcript_path", "") or "", config,
            )
            dirty = True   # reads_after 也要落盤
        except Exception as e:
            print(f"overview hub read error: {e}", file=sys.stderr)

    # Depends 召回（A3.5）：讀到的檔若是某張卡的壞滅緣（索引 depends path:），一行一卡指標；文件／計畫檔命中 authority_map 一次性注入地圖
    dep_ctx = None
    if tool_name in ("Read", "Bash", "PowerShell"):
        try:
            from wg_depends import on_read_depends as _on_read_depends
            dep_ctx = _on_read_depends(state, session_id, tool_name, tool_input, input_data.get("cwd", "") or "", config)
            if dep_ctx:
                dirty = True   # depends_hints／authority_map_injected 要落盤
        except Exception as e:
            print(f"depends recall error: {e}", file=sys.stderr)

    ng_ctx, ng_changed = _need_goal_after_tool(state, session_id, tool_name, tool_input, input_data, config)
    dirty = dirty or ng_changed

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
        ]:
            val = state.get(key)
            if val:
                advisories.append(f"{prefix} {val}")
                del state[key]
                dirty = True

    # 函式尾單次寫（dirty-flag 收斂）
    if dirty:
        write_state(session_id, state)

    # ─── 跨 session late-collision（寫後補償；必須在 write_state 之後查——
    # 兩 session 同時首寫時，寫前掃描雙方都看不見對方，落盤後才可見）───
    if (
        (config.get("coordination") or {}).get("enabled", False)
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
    sys_msgs, ctx_msgs = _run_companion_hooks(input_data, config)
    advisories.extend(ctx_msgs)
    _emit_post_tool_output(advisories, sys_msgs)
