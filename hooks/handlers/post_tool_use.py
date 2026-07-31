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
from pathlib import Path
from typing import Any, Dict, List

from wg_core import (
    _ensure_state, _now_iso, write_state, output_json, output_nothing,
    _atom_debug_error, WORKFLOW_DIR,
)
from wg_episodic import _check_output_quality
from wg_extraction import _is_lease_valid  # noqa: F401
from wg_evasion import (
    is_test_command, detect_test_failure, aec_severity, crosscheck_aec_severity,
)
from wg_atoms import _trigger_incremental_index
from wg_extraction import is_plan_filename
from handlers._shared import (
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
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
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


def _hud_beat_fresh(port: int, threshold_s: int) -> bool:
    """GET /api/aec/beat-status → age_s < threshold？不可達 / 舊碼(404) / 逾時 → False（窗死）。"""
    try:
        import urllib.request
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/aec/beat-status", timeout=0.6
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
        return int(data.get("age_s", 10 ** 9)) < threshold_s
    except Exception:
        return False


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


def _maybe_spawn_hud(sev: str, state: Dict[str, Any], config: Dict[str, Any]) -> None:
    """窗活著（心跳新）→ 會輪詢渲染、無需 fallback。窗死：config.aec.hud_autospawn 才嘗試
    spawn Edge（預設關）；且 sev∈{notable,real-evasion} → 標 aec_hud_fallback 供 Stop 大聲
    補 chat（可觀測性鐵律：push 不到窗不得 fail-silent）。routine 窗死只落 disk（無退避訊號、
    可事後由歷史格瀏覽，非違反可觀測性）。Fail-open。"""
    try:
        aec_cfg = (config or {}).get("aec", {}) or {}
        port = int((config or {}).get("dashboard_port", 3848))
        threshold = int(aec_cfg.get("hud_stale_s", 30))
        if _hud_beat_fresh(port, threshold):
            return
        # B：只有 notable/real-evasion 才彈窗（routine 靜默入 disk、不打擾）。
        if aec_cfg.get("hud_autospawn", False) and sev in ("notable", "real-evasion"):
            _spawn_hud_edge(port)
        if sev in ("notable", "real-evasion"):
            state["aec_hud_fallback"] = True
    except Exception as e:
        _atom_debug_error("post_tool_use:aec_maybe_spawn_hud", e)


def handle_post_tool_use(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
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

    # ─── 救援日誌：工具呼叫命中已注入 atom 的高特異 token → rescue-log ───
    try:
        from wg_rescue import check_rescue_hits
        if check_rescue_hits(state, session_id, tool_name, tool_input):
            dirty = True
    except Exception as e:
        print(f"rescue check error: {e}", file=sys.stderr)

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

    if (
        tool_name in ("Edit", "Write", "NotebookEdit")
        and file_path
        and not _is_ephemeral_path(file_path)
    ):
        # modified_files 以 (path, session_id) 去重：重複編輯只累加 count + 刷 at，
        # 不無限累積 entry。消費端計「編輯次數」者（wisdom track_retry / episodic
        # 工作區統計）改讀 count 欄（legacy 重複 entry 無 count → 預設 1，語意不變）。
        mods = state.setdefault("modified_files", [])
        for m in mods:
            if (
                isinstance(m, dict)
                and m.get("path") == file_path
                and m.get("session_id", session_id) == session_id
            ):
                m["count"] = int(m.get("count", 1)) + 1
                m["at"] = _now_iso()
                m["tool"] = tool_name
                break
        else:
            mods.append({
                "path": file_path,
                "tool": tool_name,
                "session_id": session_id,
                "at": _now_iso(),
                "count": 1,
            })
        state["sync_pending"] = True

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
            if "/" not in staging_tail and staging_fname != "next-phase.md":
                state["_staging_advisory"] = (
                    f"⚠ `_staging/{staging_fname}` 非標準檔名。"
                    f"/continue 優先讀 `next-phase.md`。"
                    f"建議重新命名：mv → next-phase.md"
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

    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if re.search(r"\b(git\s+(log|blame|show|diff)|svn\s+(log|blame|diff))\b", command):
            vcs = state.setdefault("vcs_queries", [])
            vcs.append({"command": command[:200], "at": _now_iso()})
            dirty = True

        # 本 turn 有跑 git/svn commit → 記 turn_seq，供 ScanReport 閘豁免收尾檢核
        # （工作已寫進 VCS 歷史＝可稽核、與「藏」相反，anti-evasion 目的消解）。
        if _VCS_COMMIT_RE.search(command):
            state["last_commit_turn_seq"] = int(state.get("turn_seq", 0))
            dirty = True

        if is_test_command(command):
            tr = input_data.get("tool_response", {}) or {}
            if isinstance(tr, dict):
                stdout = tr.get("stdout", "") or ""
                stderr = tr.get("stderr", "") or ""
                interrupted = bool(tr.get("interrupted", False))
            else:
                stdout, stderr, interrupted = str(tr), "", False
            failure = detect_test_failure(stdout, stderr, interrupted)
            if failure:
                ft = state.setdefault("failing_tests", [])
                ft.append({
                    "tool": "Bash",
                    "cmd": command[:200],
                    "summary": failure,
                    "at": _now_iso(),
                    # 供 Stop 端 outcome 歸因「只認本 turn 失敗」（sync/test-fail
                    # gate 等其他消費者仍看全量清單，語意不變）
                    "turn_seq": int(state.get("turn_seq", 0)),
                })
                dirty = True
            elif state.get("failing_tests"):
                cmd_prefix = command[:80].strip()
                cmd_lower = command.lower()
                is_pytest_success = "pytest" in cmd_lower
                before = state["failing_tests"]
                after = [
                    f for f in before
                    if not f.get("cmd", "").startswith(cmd_prefix[:40])
                    and not (is_pytest_success and "pytest" in f.get("cmd", "").lower())
                ]
                if len(after) != len(before):
                    state["failing_tests"] = after
                    dirty = True

    elif tool_name.endswith("anti_evasion_report"):
        # MCP 結構化收尾 emit（one-writer spine）：MCP tool 只回 chip、不碰 state；
        # 由此 PostToolUse 分支獨佔寫 state + 落 per-turn 報告檔 + 判 HUD fallback。
        # session_id 用原始 input_data["session_id"]（與 modified_files 的 session_id 戳
        # 同源）＝sibling 隔離關鍵：Stop 閘以 turn_seq+session_id 雙鍵讀，隔壁 session 的
        # emit 不誤放行本 session。turn_seq 由 UserPromptSubmit 每真 prompt +1。
        a, b, c, d = (str(tool_input.get(k, "") or "") for k in ("a", "b", "c", "d"))
        turn_seq = int(state.get("turn_seq", 0))
        sev = aec_severity(a, b, c, d)
        # (b) 欄 cross-check：hook 實測到退避但模型自評「無」→ 升 real-evasion +
        # 附 hook 證據（升級只發生在 Python one-writer；Node chip 純內容判定，
        # 顯示可能不同步——report 檔 + Stop fallback 為準）。
        evidence = _collect_aec_evidence(state, session_id)
        sev, upgraded = crosscheck_aec_severity(sev, b, evidence)
        report = {
            "session_id": session_id,
            "turn_seq": turn_seq,
            "a": a, "b": b, "c": c, "d": d,
            "severity": sev,
            "at": _now_iso(),
        }
        if upgraded:
            report["severity_upgraded_by"] = "hook:evasion-crosscheck"
            report["hook_evidence"] = evidence[-5:]
        state["anti_evasion_report"] = report
        _write_aec_report_file(session_id, turn_seq, report)
        _maybe_spawn_hud(sev, state, config)
        dirty = True

    if DOCDRIFT_AVAILABLE and config.get("docdrift", {}).get("enabled", True):
        try:
            if prune_committed_entries(state, config) > 0:
                dirty = True
        except Exception as e:
            _atom_debug_error("post_tool_use:docdrift_prune", e)
            pass

    advisories = []
    if state:
        for key, prefix in [
            ("_path_enforcement_advisory", "[Guardian:PathEnforce]"),
            ("_aidocs_advisory", "[Guardian:AIDocs]"),
            ("_staging_advisory", "[Guardian:StagingName]"),
            ("_docdrift_advisory", "[Guardian:DocDrift]"),
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

    if advisories:
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "\n".join(advisories),
            }
        })
    else:
        output_nothing()
