"""
handlers/stop.py — Stop hook handler

四個 gate：
1. Test-Fail Gate（測試未綠 + 宣告完成 → 硬阻）
2. Evasion 偵測（軟糾正）
3. Scan-Report Gate（宣告完成但缺掃描報告 → 硬阻）
4. Sync Reminder Gate（modified_files>0 仍未 commit → 軟阻）
+ 一般 sync block 邏輯
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from wg_core import (
    _ensure_state, _now_iso, write_state, output_nothing, output_block,
)
from wg_evasion import (
    detect_test_failure, is_test_command, claims_completion, detect_evasion,
    is_dismiss_prompt, get_last_assistant_text, detect_missing_scan_report,
)
from wg_episodic import _find_session_transcript
from wg_extraction import _maybe_spawn_per_turn_extraction
from handlers._shared import (
    _maybe_spawn_user_extract_worker,
    DOCDRIFT_AVAILABLE,
)


def _detect_uncommitted_files(
    modified_files: List[Dict[str, Any]],
) -> Optional[List[str]]:
    """偵測 modified_files 裡仍未提交的檔案。

    回傳:
      - List[str]: 未提交檔案路徑（已去重）
      - []: 全已提交
      - None: 偵測失敗（非 git/svn 工作區）— 跳過此閘
    """
    unique_paths: List[str] = []
    seen: set = set()
    for m in modified_files:
        p = (m or {}).get("path", "")
        if p and p not in seen:
            seen.add(p)
            unique_paths.append(p)
    if not unique_paths:
        return []

    uncommitted: List[str] = []
    detected_any_vcs = False

    for path in unique_paths:
        if not os.path.exists(path):
            continue
        parent = str(Path(path).parent)
        committed_via_git = False
        try:
            r = subprocess.run(
                ["git", "status", "--porcelain", "--", path],
                cwd=parent, capture_output=True, text=True, timeout=3,
            )
            if r.returncode == 0:
                detected_any_vcs = True
                committed_via_git = True
                if r.stdout.strip():
                    uncommitted.append(path)
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            pass
        if committed_via_git:
            continue
        try:
            r = subprocess.run(
                ["svn", "status", path],
                cwd=parent, capture_output=True, text=True, timeout=3,
            )
            stderr_low = (r.stderr or "").lower()
            not_a_wc = (
                "is not a working copy" in stderr_low
                or "w155007" in stderr_low
                or "e155007" in stderr_low
            )
            if r.returncode == 0 and not not_a_wc:
                detected_any_vcs = True
                if r.stdout.strip():
                    uncommitted.append(path)
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            pass

    if not detected_any_vcs:
        return None
    return uncommitted


def handle_stop(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    max_blocks = config.get("stop_gate_max_blocks", 2)
    stop_count = state.get("stop_blocked_count", 0)
    phase = state.get("phase", "working")

    # ── Test-Fail Gate ────────────────────────────────────────────
    failing = state.get("failing_tests") or []
    last_text = ""
    cwd = state.get("session", {}).get("cwd", "") or input_data.get("cwd", "")
    transcript = _find_session_transcript(session_id, cwd) if cwd else None
    if failing:
        last_text = get_last_assistant_text(transcript)
        if claims_completion(last_text):
            state["stop_blocked_count"] = stop_count + 1
            write_state(session_id, state)
            reason = (
                f"[Guardian:TestFailGate] 測試未綠（{len(failing)} 項失敗），"
                "不得宣告完成。\n"
                + "\n".join(
                    f"  - {f.get('cmd', '')[:60]}: "
                    f"{(f.get('summary', '').splitlines() or [''])[0][:100]}"
                    for f in failing[-3:]
                )
                + "\n選 (a) 修復 (b) 明確說明為何不修並標記為已知 regression "
                "(c) 降級任務定義。不得籠統帶過。"
            )
            output_block(reason)
            return

    if not state.get("evasion_flag"):
        if not last_text:
            last_text = get_last_assistant_text(transcript)
        recent_prompts = state.get("recent_user_prompts", []) or []
        ev = detect_evasion(last_text, recent_prompts)
        if ev:
            ev["at"] = _now_iso()
            state["evasion_flag"] = ev
            write_state(session_id, state)

    # ── Scan-Report Gate ────────────────────────────────────────
    mod_files_all = state.get("modified_files", []) or []
    if mod_files_all and not state.get("scan_report_warned"):
        if not last_text:
            last_text = get_last_assistant_text(transcript)
        recent_prompts = state.get("recent_user_prompts", []) or []
        if detect_missing_scan_report(last_text, len(mod_files_all), recent_prompts):
            state["stop_blocked_count"] = stop_count + 1
            state["scan_report_warned"] = True
            write_state(session_id, state)
            reason = (
                "[Guardian:ScanReport] 宣告完成但未提交掃描報告，違反 IDENTITY「反退避契約」。\n"
                "依格式強制，報告尾端必須包含下列之一：\n"
                "  (a) 順手修補清單：- 檔:行 — 改了什麼\n"
                "      （若確實無則明寫「本次無發現 drift」）\n"
                "  (b) 需另開 session：項目 X — 超出原因：Y\n"
                "請補上後再宣告完成；不得用「不在範圍 / 留給未來」籠統帶過。"
            )
            output_block(reason)
            return

    # ── Sync Reminder Gate ──────────────────────────────────────
    sr_config = config.get("sync_reminder", {}) or {}
    sr_enabled = sr_config.get("enabled", True)
    sr_max = int(sr_config.get("max_reminders", 1))
    sr_count = int(state.get("sync_reminder_count", 0))
    if (
        sr_enabled
        and mod_files_all
        and not state.get("muted")
        and phase not in ("done", "syncing")
        and sr_count < sr_max
    ):
        uncommitted = _detect_uncommitted_files(mod_files_all)
        if uncommitted:
            state["sync_reminder_count"] = sr_count + 1
            state["stop_blocked_count"] = stop_count + 1
            write_state(session_id, state)
            shown = uncommitted[:8]
            names = "\n".join(f"  - {p}" for p in shown)
            more = (
                f"\n  ...（共 {len(uncommitted)} 檔，僅顯示前 8）"
                if len(uncommitted) > 8 else ""
            )
            reason = (
                f"[Guardian:SyncReminder] 偵測到 {len(uncommitted)} 個已修改但"
                "尚未提交的檔案，依 rules/core.md「完成修改後主動提出 "
                ".git→commit+push」應提示同步。\n"
                f"{names}{more}\n"
                "請選一個方向：\n"
                "  (a) 上 GIT — 立刻 commit + push\n"
                "  (b) 我不打算上 — 請說明原因（會跳過本次提醒）\n"
                "  (c) 已在前一輪上過了 — git/svn clean 後本 gate 自動清旗標"
            )
            output_block(reason)
            return

    # ── Anti-loop guard ─────────────────────────────────────────
    if stop_count >= max_blocks:
        state["phase"] = "done"
        write_state(session_id, state)
        _maybe_spawn_per_turn_extraction(session_id, state, config)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    if phase in ("done", "syncing"):
        _maybe_spawn_per_turn_extraction(session_id, state, config)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    mod_count = len(state.get("modified_files", []))
    kq_count = len(state.get("knowledge_queue", []))
    unique_files = list({m["path"] for m in state.get("modified_files", [])})
    min_files = config.get("min_files_to_block", 2)

    if state.get("muted"):
        _maybe_spawn_per_turn_extraction(session_id, state, config)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    if mod_count == 0 and kq_count == 0:
        state["phase"] = "done"
        write_state(session_id, state)
        _maybe_spawn_per_turn_extraction(session_id, state, config)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    if len(unique_files) < min_files and kq_count == 0:
        state["phase"] = "done"
        write_state(session_id, state)
        _maybe_spawn_per_turn_extraction(session_id, state, config)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    state["stop_blocked_count"] = stop_count + 1
    write_state(session_id, state)
    _maybe_spawn_per_turn_extraction(session_id, state, config)
    _maybe_spawn_user_extract_worker(session_id, state, config)

    file_names = ", ".join(f.rsplit("/", 1)[-1] for f in unique_files[:8])

    reason = (
        f"[Workflow Guardian] {len(unique_files)} file(s) modified"
        + (f", {kq_count} knowledge pending" if kq_count else "")
        + f". Files: {file_names}.\n"
        "Sync: _AIDocs→_CHANGELOG | knowledge→atom | .git→add+commit+push | .svn→add+commit"
    )

    if DOCDRIFT_AVAILABLE:
        try:
            dp = state.get("docdrift_pending", {})
            if dp:
                docs = sorted(set(v["doc"] for v in dp.values()))
                reason += f"\n[DocDrift] {len(dp)} source change(s) → consider updating: {', '.join(docs[:5])}"
        except Exception:
            pass

    output_block(reason)
