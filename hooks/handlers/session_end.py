"""
handlers/session_end.py — SessionEnd hook handler

收尾：DocDrift summary / state cleanup / extract worker / user-extract worker /
session evaluator / iteration metrics / oscillation / self-iterate atoms /
wisdom reflect / staging reminder / conflict detection / atom health fix /
episodic gen / review marker / vector reindex。
"""

import json
import sys
from typing import Any, Dict

from wg_core import (
    CLAUDE_DIR, EPISODIC_DIR, WORKFLOW_DIR,
    _ensure_state, _now_iso, write_state,
    _atom_debug_error,
    discover_all_project_memory_dirs, get_project_memory_dir, resolve_staging_dir,
)
from wg_atoms import (
    _self_iterate_atoms, _trigger_incremental_index, _sweep_realm_auto_migrate,
)
from wg_extraction import _spawn_extract_worker
from wg_episodic import (
    _detect_atom_conflicts, _generate_episodic_atom, _purge_expired_episodic,
)
from wg_handoff import build_handoff_stub, should_write_stub
from wg_recall_miss import detect_recall_misses
from wg_evasion import (
    evaluate_session, flush_outcome_stats,
    _collect_iteration_metrics, _detect_oscillation, _save_oscillation_state,
    _save_review_marker,
)
from handlers._shared import (
    _cleanup_old_states,
    _maybe_spawn_user_extract_worker,
    WISDOM_AVAILABLE, wisdom_reflect,
    DOCDRIFT_AVAILABLE, build_drift_advisory,
)


def _auto_commit_promotions(promoted, config: Dict[str, Any]) -> None:
    """晉升 sweep 改到的 atom 當場提交（選擇性 pathspec，fail-open）。

    為何自動提交：sweep 是**程式**改檔，改動面完全可預測（只有 `- Confidence:`
    行與知識行的 `[臨]` 前綴），內容不動、不需人審。不當場提交就留在工作樹，
    而使用者常多 session 共用同一 git 工作樹 → 這些改動會被別的 session 收尾時
    誤夾帶進不相干的 commit（見 atom 併發-session-共用工作樹-收尾選擇性-staging）。

    為何用 `git commit -- <paths>` 而非 `git add` + commit：pathspec 形式只提交
    指定路徑的工作樹內容，**完全不碰 index**——別的 session 已 stage 的東西原封
    不動。共用工作樹下這是唯一安全的提交形式。

    push 走背景 detached（SessionEnd 只有 30s 預算，網路不可控），輸出落
    `Logs/auto-commit.log`；push 失敗時 commit 仍在本地，下次 `git status -sb`
    的 ahead 數會顯示。任何一步失敗只印 stderr、不阻斷 SessionEnd。
    """
    import subprocess
    from pathlib import Path

    si_config = config.get("self_iteration", {}) or {}
    if not si_config.get("auto_commit_promotions", True):
        return
    if not (CLAUDE_DIR / ".git").exists():
        return

    paths = []
    for p in promoted:
        raw = p.get("path")
        if not raw:
            continue
        f = Path(raw)
        try:
            rel = f.resolve().relative_to(CLAUDE_DIR.resolve())
        except (OSError, ValueError):
            continue  # 樹外的檔不碰（理論上不會有，晉升掃描面全在 ~/.claude）
        if f.exists():
            paths.append(rel.as_posix())
    if not paths:
        return

    def _git(*args, **kw):
        return subprocess.run(
            ["git", "-C", str(CLAUDE_DIR), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)

    try:
        st = _git("status", "--porcelain", "--", *paths, timeout=10)
        if st.returncode != 0 or not st.stdout.strip():
            return  # 沒有實際改動（例如別的 session 已提交）→ 什麼都不做
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[auto-commit] git status 失敗，晉升改動留在工作樹: {e}", file=sys.stderr)
        return

    names = ", ".join(p.get("atom", "?") for p in promoted[:5])
    if len(promoted) > 5:
        names += f" 等 {len(promoted)} 顆"
    msg = (f"chore(memory): atom 信心 [臨]→[觀] 晉升\n\n"
           f"{names}\n\n"
           f"SessionEnd 晉升 sweep 自動提交（僅 Confidence 與知識行前綴，內容未動）。\n")

    # index.lock 競態：別的 session 正在 commit → 短重試，仍失敗就放手
    committed = False
    for attempt in range(3):
        try:
            r = _git("commit", "-m", msg, "--", *paths, timeout=20)
        except (OSError, subprocess.SubprocessError) as e:
            print(f"[auto-commit] git commit 例外: {e}", file=sys.stderr)
            return
        if r.returncode == 0:
            committed = True
            break
        if "index.lock" not in (r.stderr or ""):
            print(f"[auto-commit] git commit 失敗，晉升改動留在工作樹: "
                  f"{(r.stderr or r.stdout).strip()[:200]}", file=sys.stderr)
            return
        if attempt < 2:
            import time
            time.sleep(1)
    if not committed:
        print("[auto-commit] index.lock 持續被占用（他 session 正在提交），"
              "晉升改動留在工作樹待下次", file=sys.stderr)
        return

    print(f"[auto-commit] 已提交 {len(paths)} 顆晉升 atom", file=sys.stderr)

    if not si_config.get("auto_push_promotions", True):
        return
    try:
        log_path = CLAUDE_DIR / "Logs" / "auto-commit.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logf = open(log_path, "a", encoding="utf-8", newline="\n")
        logf.write(f"\n=== {_now_iso()} push {len(paths)} promoted atoms ===\n")
        logf.flush()
        # origin 掛兩個 push URL（GitHub + GitLab），一次 push 同一份歷史到兩邊
        subprocess.Popen(
            ["git", "-C", str(CLAUDE_DIR), "push", "--quiet", "origin", "main"],
            stdout=logf, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, ValueError) as e:
        print(f"[auto-commit] 背景 push 起不來（commit 已在本地）: {e}", file=sys.stderr)


def _se_sentinel_path(session_id: str):
    # 取 wg_core.WORKFLOW_DIR 即時值（非 import 時綁定）：測試 monkeypatch 後仍生效
    import wg_core
    return wg_core.WORKFLOW_DIR / "se-sentinel" / f"{session_id}.json"


def _se_sentinel_arm(session_id: str) -> None:
    """SessionEnd 開頭 touch 哨兵、結尾清（_se_sentinel_clear）。哨兵殘留＝
    收尾流程未跑完即中斷（harness timeout / 例外）→ 下個 SessionStart 檢殘留
    浮一行告警（比照 UPS 哨兵；可觀測性鐵律：擁擠超時不得靜默）。fail-open。"""
    if not session_id:
        return
    try:
        p = _se_sentinel_path(session_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({"at": _now_iso()}, ensure_ascii=False), encoding="utf-8", newline="\n")
    except OSError:
        pass


def _se_sentinel_clear(session_id: str) -> None:
    if not session_id:
        return
    try:
        p = _se_sentinel_path(session_id)
        if p.exists():
            p.unlink()
    except OSError:
        pass


def handle_session_end(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        sys.exit(0)
        return

    _se_sentinel_arm(session_id)

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
        print(f"SessionEnd cleanup error: {e}", file=sys.stderr)

    rc = config.get("response_capture", {})
    # session_end 全文萃取 worker 的唯一下游是 session_end_flush（已停產）；
    # gate 綁 flush.enabled，避免每次 SessionEnd 白燒本機 LLM 30-60s 產出被 DEVNULL 丟棄的結果。
    # episodic 生成在本 handler 內（_generate_episodic_atom）、failure 萃取走獨立路徑，皆不受此 gate 影響。
    _sef_enabled = rc.get("session_end_flush", {}).get("enabled", True)
    if rc.get("enabled", True) and _sef_enabled:
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
            print(f"extract-worker spawned (pid={pid}, intent={intent})", file=sys.stderr)
        state["extract_worker_pid"] = 0

    # 效用歸因遙測：outcome unknown 比率落 workflow/outcome_stats.jsonl；連續偏高
    # → 寫 advisory marker（SessionStart 讀後注入並清除，同 realm automove 模式）。
    # 防換模型後完成語 regex 失配 → unknown 全吞 → α/β 晉升軌靜默停滯。
    try:
        _ow_advisory = flush_outcome_stats(state, config, session_id)
        if _ow_advisory:
            _ow_marker = WORKFLOW_DIR / "outcome-unknown-advisory.json"
            _ow_marker.write_text(
                json.dumps({"msg": _ow_advisory, "at": _now_iso()}, ensure_ascii=False),
                encoding="utf-8",
            newline="\n")
            print(_ow_advisory, file=sys.stderr)
    except Exception as e:
        _atom_debug_error("session_end:outcome_watch", e)

    worker_spawned = _maybe_spawn_user_extract_worker(session_id, state, config)

    if not worker_spawned and ue_config.get("enabled", False):
        try:
            evaluate_session(session_id, state, config, worker_stats=None)
        except Exception as e:
            _atom_debug_error("session_evaluator_fallback", e)

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
                    f"Oscillation detected: {osc['atom']} "
                    f"({osc['count']} sessions)",
                    file=sys.stderr,
                )
        _save_oscillation_state(oscillations if oscillations else [])
    except Exception as e:
        print(f"Self-iteration metrics error: {e}", file=sys.stderr)

    try:
        si_results = _self_iterate_atoms(state, config)
        if si_results.get("promoted"):
            for p in si_results["promoted"]:
                print(
                    f"Auto-promoted [臨]→[觀] in {p['atom']}: "
                    f"{len(p['items'])} items",
                    file=sys.stderr,
                )
            try:
                _auto_commit_promotions(si_results["promoted"], config)
            except Exception as e:
                # 提交失敗絕不能拖垮 SessionEnd；改動留在工作樹等人處理
                print(f"[auto-commit] 未預期錯誤，晉升改動留在工作樹: {e}",
                      file=sys.stderr)
        if si_results.get("archive_candidates"):
            _fr = si_results.get("forget") or {}
            if _fr.get("mode") == "isolated" and _fr.get("forgotten"):
                print(
                    f"Selective-forget: isolated "
                    f"{len(_fr['forgotten'])} stale atoms → _distant/ (可逆)",
                    file=sys.stderr,
                )
            else:
                # 報告落候選 atom 所屬記憶庫的 _staging（全域候選 → ~/.claude/memory/_staging，
                # 非 cwd 專案庫），故印實際路徑而非相對 "_staging/"。
                for rp in si_results.get("reports") or []:
                    print(
                        f"Archive candidates: "
                        f"{len(si_results['archive_candidates'])} atoms (low decay score; "
                        f"dry-run → {rp}, forget-candidates.md 同目錄)",
                        file=sys.stderr,
                    )
    except Exception as e:
        print(f"Self-iteration error: {e}", file=sys.stderr)

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
            print(f"Wisdom reflect error: {e}", file=sys.stderr)

    try:
        edit_counts = state.get("edit_counts", {})
        if edit_counts:
            reverted = sum(1 for c in edit_counts.values() if c >= 2)
            if reverted > 0:
                print(
                    f"Over-engineering: {reverted}/{len(edit_counts)} files "
                    f"edited 2+ times",
                    file=sys.stderr,
                )
    except Exception as e:
        print(f"Over-engineering metrics error: {e}", file=sys.stderr)

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
                , newline="\n")
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
                f"_staging/ 有 {len(staging_files)} 個暫存檔案待清理",
                file=sys.stderr,
            )

    try:
        conflict_warnings = _detect_atom_conflicts(state, config)
        if conflict_warnings:
            state["conflict_warnings"] = conflict_warnings
            for cw in conflict_warnings:
                print(
                    f"Conflict: {cw['source']} ↔ {cw['target']} "
                    f"(score={cw['score']})",
                    file=sys.stderr,
                )
    except Exception as e:
        print(f"Conflict detection error: {e}", file=sys.stderr)

    # atom-health-check 修參照：fire-and-forget（不 wait）——SessionEnd 30s 窗擁擠，
    # 兩個子行程各可吃 10s；其輸出本就丟棄、結果不影響收尾流程，detach 即可。
    try:
        import subprocess as _sp
        _hc_script = str(CLAUDE_DIR / "tools" / "atom-health-check.py")
        _hc_kwargs: Dict[str, Any] = {
            "stdin": _sp.DEVNULL, "stdout": _sp.DEVNULL, "stderr": _sp.DEVNULL,
        }
        if sys.platform == "win32":
            _hc_kwargs["creationflags"] = _sp.CREATE_NO_WINDOW
        else:
            _hc_kwargs["start_new_session"] = True
        _sp.Popen([sys.executable, _hc_script, "--fix-refs"], **_hc_kwargs)
        _proj_mem = get_project_memory_dir(state.get("session", {}).get("cwd", ""))
        if _proj_mem:
            _sp.Popen(
                [sys.executable, _hc_script, "--fix-refs", "--memory-root", str(_proj_mem)],
                **_hc_kwargs,
            )
    except Exception as e:
        print(f"fix-refs error: {e}", file=sys.stderr)

    episodic_generated = state.get("episodic_checkpoint_done", False)
    if not episodic_generated and config.get("episodic", {}).get("auto_generate", True):
        try:
            _generate_episodic_atom(session_id, state, config)
            episodic_generated = True
        except Exception as e:
            print(f"[episodic] generation failed: {e}", file=sys.stderr)
            _atom_debug_error("萃取:_generate_episodic_atom", e)

    # ── 輕量 episodic purge：兌現 24d TTL（decay/forget 皆 SKIP episodic，此為唯一淘汰者）──
    # 先生成本 session 的 episodic（今建、24d 後才過期），再把過期舊檔搬 _distant/（可逆、
    # 被 index/vector 排除→不再注入）。獨立 pass、fail-open，不阻斷收尾主流程。
    purged_count = 0
    if config.get("episodic", {}).get("purge_expired", True):
        try:
            purged = _purge_expired_episodic()
            purged_count = len(purged)
            if purged:
                _preview = ", ".join(purged[:5]) + ("…" if purged_count > 5 else "")
                print(
                    f"[episodic] purged {purged_count} expired → _distant/ (可逆): {_preview}",
                    file=sys.stderr,
                )
        except Exception as e:
            _atom_debug_error("session_end:episodic_purge", e)

    # ── 失念偵測（recall-miss）：本 session 有失敗證據、庫中未注入 atom 的 trigger
    # 卻命中 ≥2 詞 → 落 Logs/recall-miss.jsonl（浮出走 effect-report D 節 + 週健檢黃燈）。
    # 純本地字串比對、fail-open 浮訊號，不阻斷收尾。
    if config.get("recall_miss", {}).get("enabled", True):
        try:
            _rm = detect_recall_misses(session_id, state)
            if _rm:
                _rm_names = ", ".join(r["atom"] for r in _rm[:5])
                print(
                    f"[recall-miss] {len(_rm)} atom 該想起而未想起: {_rm_names}",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"[recall-miss] error: {e}", file=sys.stderr)
            _atom_debug_error("session_end:recall_miss", e)

    if state.get("review_due"):
        try:
            total = sum(1 for _ in EPISODIC_DIR.glob("episodic-*.md")) if EPISODIC_DIR.exists() else 0
            for _slug, _mem_dir in discover_all_project_memory_dirs():
                _ep = _mem_dir / "episodic"
                if _ep.exists():
                    total += sum(1 for _ in _ep.glob("episodic-*.md"))
            _save_review_marker(total)
            print(f"Review marker saved (total={total})", file=sys.stderr)
        except Exception as e:
            print(f"Review marker save error: {e}", file=sys.stderr)

    write_state(session_id, state)

    modified = state.get("modified_files", [])
    has_atom_changes = any(
        "/memory/" in m.get("path", "").replace("\\", "/")
        and m.get("path", "").endswith(".md")
        for m in modified
    )
    if has_atom_changes or episodic_generated or purged_count:
        _trigger_incremental_index(config)

    # 走到這裡＝收尾完整跑完 → 拆哨兵（timeout 砍掉時到不了這行，哨兵殘留告警）
    _se_sentinel_clear(session_id)

    sys.exit(0)
