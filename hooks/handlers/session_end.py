"""
handlers/session_end.py — SessionEnd hook handler

收尾：DocDrift summary / state cleanup / extract worker / user-extract worker /
session evaluator / iteration metrics / oscillation / self-iterate atoms /
wisdom reflect / staging reminder / conflict detection / atom health fix /
episodic gen / review marker / vector reindex。
"""

import sys
from typing import Any, Dict

from wg_core import (
    CLAUDE_DIR, EPISODIC_DIR,
    _ensure_state, _now_iso, write_state,
    _atom_debug_error,
    discover_all_project_memory_dirs, get_project_memory_dir, resolve_staging_dir,
)
from wg_atoms import (
    _self_iterate_atoms, _trigger_incremental_index, _sweep_realm_auto_migrate,
)
from wg_extraction import _spawn_extract_worker
from wg_episodic import _detect_atom_conflicts, _generate_episodic_atom
from wg_handoff import build_handoff_stub, should_write_stub
from wg_evasion import (
    evaluate_session,
    _collect_iteration_metrics, _detect_oscillation, _save_oscillation_state,
    _save_review_marker,
)
from handlers._shared import (
    _cleanup_old_states,
    _maybe_spawn_user_extract_worker,
    WISDOM_AVAILABLE, wisdom_reflect,
    DOCDRIFT_AVAILABLE, build_drift_advisory,
)


def handle_session_end(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        sys.exit(0)
        return

    state["ended_at"] = _now_iso()
    state["phase"] = "done"

    if DOCDRIFT_AVAILABLE and config.get("docdrift", {}).get("enabled", True):
        try:
            drift_msg = build_drift_advisory(state, config)
            if drift_msg:
                print(f"[Guardian:DocDrift] {drift_msg}", file=sys.stderr)
        except Exception as e:
            _atom_debug_error("session_end:docdrift_advisory", e)

    ue_config = config.get("userExtraction", {})
    if not ue_config.get("enabled", False) and state.get("pending_user_extract"):
        state["pending_user_extract"] = []

    try:
        _cleanup_old_states()
    except Exception as e:
        print(f"[v3] SessionEnd cleanup error: {e}", file=sys.stderr)

    rc = config.get("response_capture", {})
    if rc.get("enabled", True):
        cwd = state.get("session", {}).get("cwd", "")
        tracker = state.get("topic_tracker", {})
        dist = tracker.get("intent_distribution", {})
        intent = max(dist, key=dist.get, default="build") if dist else "build"
        worker_ctx = {
            "session_id": session_id,
            "cwd": cwd,
            "config": config,
            "knowledge_queue": state.get("knowledge_queue", []),
            "session_intent": intent,
            "byte_offset": state.get("extraction_offset", 0),
        }
        pid = _spawn_extract_worker(worker_ctx)
        if pid:
            print(f"[v2.12] extract-worker spawned (pid={pid}, intent={intent})", file=sys.stderr)
        state["extract_worker_pid"] = 0

    worker_spawned = _maybe_spawn_user_extract_worker(session_id, state, config)

    if not worker_spawned and ue_config.get("enabled", False):
        try:
            evaluate_session(session_id, state, config, worker_stats=None)
        except Exception as e:
            _atom_debug_error("V4.1:session_evaluator_fallback", e)

    mod_count = len(state.get("modified_files", []))
    kq_count = len(state.get("knowledge_queue", []))
    if state.get("sync_pending") and (mod_count > 0 or kq_count > 0):
        print(
            f"Warning: Session ending with unsaved work. "
            f"{mod_count} modified files, {kq_count} knowledge items.",
            file=sys.stderr,
        )

    try:
        metrics = _collect_iteration_metrics(state)
        state["iteration_metrics"] = metrics

        oscillations = _detect_oscillation(state, config)
        if oscillations:
            state["iteration_metrics"]["oscillations"] = oscillations
            for osc in oscillations:
                print(
                    f"[v2.6] Oscillation detected: {osc['atom']} "
                    f"({osc['count']} sessions)",
                    file=sys.stderr,
                )
        _save_oscillation_state(oscillations if oscillations else [])
    except Exception as e:
        print(f"[v2.6] Self-iteration metrics error: {e}", file=sys.stderr)

    try:
        si_results = _self_iterate_atoms(state, config)
        if si_results.get("promoted"):
            for p in si_results["promoted"]:
                print(
                    f"[v2.16] Auto-promoted [臨]→[觀] in {p['atom']}: "
                    f"{len(p['items'])} items",
                    file=sys.stderr,
                )
        if si_results.get("archive_candidates"):
            print(
                f"[v2.16] Archive candidates: "
                f"{len(si_results['archive_candidates'])} atoms (low decay score)",
                file=sys.stderr,
            )
    except Exception as e:
        print(f"[v2.16] Self-iteration error: {e}", file=sys.stderr)

    # V5+ Realm 維度：自動歸類 sweep（高信心 core→local；永不靜默，下個 SessionStart 提示）
    try:
        realm_moved = _sweep_realm_auto_migrate(config)
        if realm_moved:
            for m in realm_moved:
                print(
                    f"[realm] auto-migrated {m['slug']} → local/{m['domain']} "
                    f"({m['from']} → {m['to']})",
                    file=sys.stderr,
                )
    except Exception as e:
        print(f"[realm] auto-migrate sweep error: {e}", file=sys.stderr)

    if WISDOM_AVAILABLE:
        try:
            wisdom_reflect(state)
        except Exception as e:
            print(f"[v2.8] Wisdom reflect error: {e}", file=sys.stderr)

    try:
        edit_counts = state.get("edit_counts", {})
        if edit_counts:
            reverted = sum(1 for c in edit_counts.values() if c >= 2)
            if reverted > 0:
                print(
                    f"[v2.11] Over-engineering: {reverted}/{len(edit_counts)} files "
                    f"edited 2+ times",
                    file=sys.stderr,
                )
    except Exception as e:
        print(f"[v2.11] Over-engineering metrics error: {e}", file=sys.stderr)

    cwd = state.get("session", {}).get("cwd", "")
    staging_dir = resolve_staging_dir(cwd)

    # ── Layer 4: Auto-Handoff SessionEnd 兜底 ──
    # 補「PreCompact 沒觸發、session 直接結束」缺口：有未完成工作且無既有 handoff 時，
    # 寫客觀 stub 供下個 session /continue。session 已結束、無壓縮上下文壓力 → 只填客觀
    # 區塊、主觀照 TODO 佔位（不設 pending_handoff_emit，已無 PostToolBatch 可消費）。
    # should_write_stub 的 modified_files 檢查與 sync_pending 同源（post_tool_use.py:168
    # 兩者一併設、session 內不清），已涵蓋 plan line 79「modified_files + sync_pending」。
    # 寫在 staging reminder 前，使其計入下方暫存檔提示。fail-open 不影響收尾主流程。
    ah = config.get("auto_handoff", {}) or {}
    if ah.get("enabled", True) and ah.get("sessionend_fallback", True):
        try:
            stub_name = ah.get("stub_filename", "next-phase-auto.md")
            if should_write_stub(staging_dir, state, stub_name):
                staging_dir.mkdir(parents=True, exist_ok=True)
                (staging_dir / stub_name).write_text(
                    build_handoff_stub(state, cwd), encoding="utf-8"
                )
                state["handoff_stub_path"] = str(staging_dir / stub_name)
                state["handoff_stub_at"] = _now_iso()
                print(
                    f"[auto-handoff] sessionend fallback stub: {staging_dir / stub_name}",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"[auto-handoff] sessionend fallback error: {e}", file=sys.stderr)

    if staging_dir.exists():
        staging_files = list(staging_dir.glob("*.md"))
        if staging_files:
            print(
                f"[v2.10] _staging/ 有 {len(staging_files)} 個暫存檔案待清理",
                file=sys.stderr,
            )

    try:
        conflict_warnings = _detect_atom_conflicts(state, config)
        if conflict_warnings:
            state["conflict_warnings"] = conflict_warnings
            for cw in conflict_warnings:
                print(
                    f"[v2.11] Conflict: {cw['source']} ↔ {cw['target']} "
                    f"(score={cw['score']})",
                    file=sys.stderr,
                )
    except Exception as e:
        print(f"[v2.11] Conflict detection error: {e}", file=sys.stderr)

    try:
        import subprocess as _sp
        _hc_script = str(CLAUDE_DIR / "tools" / "atom-health-check.py")
        _sp.run(
            [sys.executable, _hc_script, "--fix-refs"],
            capture_output=True, timeout=10,
        )
        _proj_mem = get_project_memory_dir(state.get("session", {}).get("cwd", ""))
        if _proj_mem:
            _sp.run(
                [sys.executable, _hc_script, "--fix-refs", "--memory-root", str(_proj_mem)],
                capture_output=True, timeout=10,
            )
    except Exception as e:
        print(f"[v2.18] fix-refs error: {e}", file=sys.stderr)

    episodic_generated = state.get("episodic_checkpoint_done", False)
    if not episodic_generated and config.get("episodic", {}).get("auto_generate", True):
        try:
            _generate_episodic_atom(session_id, state, config)
            episodic_generated = True
        except Exception as e:
            print(f"[episodic] generation failed: {e}", file=sys.stderr)
            _atom_debug_error("萃取:_generate_episodic_atom", e)

    if state.get("review_due"):
        try:
            total = sum(1 for _ in EPISODIC_DIR.glob("episodic-*.md")) if EPISODIC_DIR.exists() else 0
            for _slug, _mem_dir in discover_all_project_memory_dirs():
                _ep = _mem_dir / "episodic"
                if _ep.exists():
                    total += sum(1 for _ in _ep.glob("episodic-*.md"))
            _save_review_marker(total)
            print(f"[v2.6] Review marker saved (total={total})", file=sys.stderr)
        except Exception as e:
            print(f"[v2.6] Review marker save error: {e}", file=sys.stderr)

    write_state(session_id, state)

    modified = state.get("modified_files", [])
    has_atom_changes = any(
        "/memory/" in m.get("path", "").replace("\\", "/")
        and m.get("path", "").endswith(".md")
        for m in modified
    )
    if has_atom_changes or episodic_generated:
        _trigger_incremental_index(config)

    sys.exit(0)
