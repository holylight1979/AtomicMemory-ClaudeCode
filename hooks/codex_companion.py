"""codex_companion.py — Codex Companion hook (subprocess model).

in-process state + spawn `tools/codex-companion/audit.py` 短命子程序執行
codex assessment（無常駐 daemon）。

Events handled:
  SessionStart    → companion_state.ensure_state
  UserPromptSubmit → drain companion-assessment-*.json → additionalContext
  PostToolUse     → state.append_event + checkpoint detect → spawn audit
  Stop            → state ops + heuristic soft gate + score gate → spawn audit
  SessionEnd      → flush metrics to reflection_metrics.json

Fast path: config disabled / codex CLI missing → exit(0) immediately.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

CLAUDE_DIR = Path.home() / ".claude"
WORKFLOW_DIR = CLAUDE_DIR / "workflow"
CONFIG_PATH = WORKFLOW_DIR / "config.json"
COMPANION_DIR = CLAUDE_DIR / "tools" / "codex-companion"
AUDIT_SCRIPT = COMPANION_DIR / "audit.py"

# Add companion dir to path for heuristics/state import
sys.path.insert(0, str(COMPANION_DIR))
sys.path.insert(0, str(CLAUDE_DIR / "hooks"))


# ─── Config ──────────────────────────────────────────────────────────────────


def _load_config() -> Dict[str, Any]:
    try:
        full = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return full.get("codex_companion", {})
    except (json.JSONDecodeError, OSError):
        return {}


# ─── Always-on error log（standalone：不依賴 wg_core，寫 stderr）─────────────


def _log_err(source: str, exc: Exception) -> None:
    try:
        sys.stderr.write(f"[{source}] {type(exc).__name__}: {exc}\n")
    except OSError:
        pass


# ─── Output helpers (same protocol as workflow-guardian) ──────────────────────


def _output_json(data: Dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False))
    sys.exit(0)


def _output_context(event_name: str, text: str) -> None:
    _output_json({
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": text,
        }
    })


def _output_block(reason: str, session_id: str = "") -> None:
    # 觀測：每次 BLOCK 累加 behavior_gap_blocks
    if session_id:
        try:
            import state as companion_state
            companion_state.increment_metric(session_id, "behavior_gap_blocks")
        except Exception as e:
            _log_err("codex:metric_block_count", e)
            pass
    _output_json({"decision": "block", "reason": reason})


def _output_nothing() -> None:
    sys.exit(0)


# ─── Checkpoint detection (V5: moved from service.py) ────────────────────────

_PLAN_TOOLS = {"ExitPlanMode", "EnterPlanMode"}
_WRITE_TOOLS = {"Edit", "Write"}
# 跨 session 交接檔：_staging/next-phase*.md 或檔名含 handoff（持久化 artifact，
# /continue 接手端實際讀的就是它）。命中 → 對抗式 handoff 自檢（Q2）。
_NEXT_PHASE_RE = re.compile(r"(?:next-phase|next_phase|handoff)[^/\\]*\.md$", re.IGNORECASE)


def _detect_checkpoint(
    tool_name: str, file_path: str, config: Dict[str, Any]
) -> Optional[str]:
    """Determine if this tool use triggers a checkpoint.

    (1) ExitPlanMode/EnterPlanMode → plan_review
    (2) 結構性檔案 Edit/Write + soft_gate.architecture_review=true → architecture_review
    (3) next-phase/handoff 檔 Edit/Write（soft_gate.handoff_review，預設開）→ handoff_review
        ——跨 session 交接文件的對抗式自檢，把作者「自評」升級為獨立「他評」（補盲點）。
    """
    if tool_name in _PLAN_TOOLS:
        return "plan_review"
    if (tool_name in _WRITE_TOOLS and file_path
            and config.get("soft_gate", {}).get("handoff_review", True)
            and _NEXT_PHASE_RE.search(file_path.replace("\\", "/"))
            # 範本檔（templates/）是骨架非交接內容，審它必然「全是佔位符」誤報
            and "/templates/" not in file_path.replace("\\", "/")):
        return "handoff_review"
    if (tool_name in _WRITE_TOOLS and file_path
            and config.get("soft_gate", {}).get("architecture_review", False)):
        try:
            import heuristics as _heur
            if _heur._ARCH_FILE_RE.search(file_path):
                return "architecture_review"
        except ImportError:
            pass
    return None


# ─── Audit subprocess spawn ─────────────────────


def _spawn_audit_subprocess(turn_data: Dict[str, Any]) -> None:
    """Fire-and-forget subprocess: python audit.py <stdin: turn_data JSON>.

    Detached so the hook returns immediately. audit.py reads stdin, runs
    assessor.run_assessment, writes via state.write_assessment.
    """
    if not AUDIT_SCRIPT.exists():
        return

    log_path = CLAUDE_DIR / "Logs" / "codex-audit.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        log_fh = open(str(log_path), "a", encoding="utf-8")
    except OSError:
        log_fh = subprocess.DEVNULL

    try:
        kwargs: Dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.DEVNULL,
            "stderr": log_fh,
        }
        if sys.platform == "win32":
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            CREATE_BREAKAWAY_FROM_JOB = 0x01000000
            kwargs["creationflags"] = (
                CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_BREAKAWAY_FROM_JOB
            )
        else:
            kwargs["start_new_session"] = True

        proc = subprocess.Popen([sys.executable, str(AUDIT_SCRIPT)], **kwargs)
        try:
            proc.stdin.write(
                json.dumps(turn_data, ensure_ascii=False).encode("utf-8")
            )
        finally:
            proc.stdin.close()
    except Exception as e:
        # Fail silently — companion is optional
        _log_err("codex:assessor_spawn", e)
        if hasattr(log_fh, "close"):
            try:
                log_fh.close()
            except Exception:
                pass


# ─── Stop-text helpers (三層 fallback) ───────────────────────────────────────


def _get_last_assistant_tail(input_data: Dict[str, Any]) -> str:
    """Stop hook 文本三層 fallback：
    1. input_data["last_assistant_message"]（若 ClaudeCode 提供）
    2. 自寫 transcript jsonl tail parser（不過長度過濾，不放掉「已完成。」「Done.」短句）
    3. wg_evasion.get_last_assistant_text()（>30 字過濾）作兜底
    """
    direct = input_data.get("last_assistant_message", "")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()[:2000]

    transcript_path = input_data.get("transcript_path", "")
    if transcript_path:
        try:
            last = ""
            with open(transcript_path, "r", encoding="utf-8") as f:
                for raw in f:
                    try:
                        obj = json.loads(raw)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if obj.get("type") != "assistant":
                        continue
                    content = obj.get("message", {}).get("content", [])
                    if not isinstance(content, list):
                        continue
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            t = block.get("text", "")
                            if t:
                                last = t
            if last:
                return last[:2000]
        except (OSError, UnicodeDecodeError) as e:
            _log_err("codex:stop_text_transcript", e)
            pass

        try:
            import wg_evasion
            tail = wg_evasion.get_last_assistant_text(Path(transcript_path))
            if tail:
                return tail[:2000]
        except Exception as e:
            _log_err("codex:stop_text_fallback", e)
            pass

    return ""


def _summarize_tool_response(tool_response: Any) -> tuple[str, bool]:
    """- 從 tool_response 取 stdout/stderr 截 300 字組摘要
    - 偵測失敗訊號 (error / exit_code != 0 / stderr / is_error) → prefix [FAILED]
    回傳 (summary, failed)
    """
    if not isinstance(tool_response, dict):
        text = str(tool_response or "")
        return text[:300], False

    stdout = tool_response.get("stdout", "") or tool_response.get("output", "")
    stderr = tool_response.get("stderr", "")
    error = tool_response.get("error", "")
    exit_code = tool_response.get("exit_code", tool_response.get("returncode", 0))
    is_error = bool(tool_response.get("is_error", False))

    failed = (
        bool(error)
        or bool(stderr and str(stderr).strip())
        or (isinstance(exit_code, int) and exit_code != 0)
        or is_error
    )

    parts: list[str] = []
    if stdout:
        parts.append(f"stdout: {str(stdout)[:200]}")
    if stderr:
        parts.append(f"stderr: {str(stderr)[:200]}")
    if error:
        parts.append(f"error: {str(error)[:200]}")
    summary = " | ".join(parts)[:300] if parts else ""

    if failed and summary:
        summary = f"[FAILED] {summary}"
    elif failed:
        summary = "[FAILED] (no detail)"

    return summary, failed


def _summarize_files_examined(
    tool_trace: list, max_items: int = 30, max_chars: int = 1500
) -> str:
    """從 tool_trace 萃取「代理人已接觸的檔案」摘要供 codex prompt 用。

    含 Read/Glob/Grep（直接讀檔/搜檔）+ Edit/Write/NotebookEdit（修改即接觸）+
    Agent（sub-agent 代理活動：input=description / output_summary 含 sub-agent 讀的檔）。
    Cap max_items 條 / max_chars 字，避免 prompt token 膨脹。
    """
    if not tool_trace:
        return "(none)"

    read_tools = {"Read", "Glob", "Grep"}
    write_tools = {"Edit", "Write", "NotebookEdit"}

    lines: list[str] = []
    seen_paths: set[str] = set()

    for t in tool_trace:
        tool = t.get("tool", "")
        path = (t.get("path") or "").strip()
        inp = (t.get("input") or "").strip()
        out = (t.get("output_summary") or "").strip()

        if tool in read_tools:
            label = path or inp
            if label and label not in seen_paths:
                lines.append(f"- [{tool}] {label[:160]}")
                seen_paths.add(label)
        elif tool in write_tools:
            if path and path not in seen_paths:
                lines.append(f"- [{tool}] {path[:160]}")
                seen_paths.add(path)
        elif tool == "Agent":
            # sub-agent 活動：description + output 尾巴
            desc = inp[:120] if inp else "(no desc)"
            out_snip = out[:240] if out else ""
            entry = f"- [Agent] {desc}"
            if out_snip:
                entry += f"\n    → result: {out_snip}"
            lines.append(entry)

        if len(lines) >= max_items:
            break

    if not lines:
        return "(none)"

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n…(truncated)"
    return text


def _read_handoff_content(file_path: str, head: int = 4500, tail: int = 1500) -> str:
    """讀 next-phase/handoff 檔供 codex 對抗式自檢（utf-8-sig 容 BOM）。失敗→''。

    超長檔取頭+尾採樣並**明確標記截斷**（可觀測性鐵律：靜默截斷會讓 codex 把
    「輸入被切斷」誤判成「文件本身斷鏈」，且看不到文末的授權/收尾段）。
    """
    try:
        text = Path(file_path).read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    if len(text) <= head + tail:
        return text
    return (
        text[:head]
        + f"\n\n…（中段省略：全文共 {len(text)} 字，此處僅含開頭 {head} 字與結尾 {tail} 字；"
        f"審查時勿把此採樣截斷誤判為文件本身截斷/斷鏈）…\n\n"
        + text[-tail:]
    )


def _build_verification_signals(input_data: Dict[str, Any], tool_response: Any) -> Dict[str, Any]:
    """給 codex 的最小化 verification_signals 包。"""
    sig: Dict[str, Any] = {
        "tool_name": input_data.get("tool_name", ""),
    }
    if isinstance(tool_response, dict):
        for k in ("exit_code", "returncode", "is_error"):
            if k in tool_response:
                sig[k] = tool_response[k]
    return sig


# ─── Event handlers ──────────────────────────────────────────────────────────


def handle_session_start(input_data: Dict[str, Any], config: Dict[str, Any]):
    import state as companion_state

    session_id = input_data.get("session_id", "")
    cwd = input_data.get("cwd", "")

    if session_id:
        companion_state.ensure_state(session_id, cwd)

    _output_nothing()


_CONFIDENCE_LABEL = {
    "low": "低信心",
    "medium": "中信心",
    "high": "高信心",
}

_APPLIES_LABEL = {
    "next_prompt": "限本輪",
    "until_arch_change": "直到架構變動",
}


def _mark_injected(path: Path, data: Dict[str, Any]) -> None:
    try:
        data["injected"] = True
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError as e:
        _log_err("codex:assessment_mark_injected", e)
        pass


def handle_user_prompt_submit(input_data: Dict[str, Any], config: Dict[str, Any]):
    """Inject pending per-turn Codex assessments as additionalContext.

    drain 掃 companion-assessment-{sid}-t*.json，依 turn_index 排序。
    依 codex 回的 delivery 路由：
      delivery=ignore → 標 injected 略過注入（codex 自判此 turn 不打擾）
      delivery=inject → 注入文字並加 confidence + applies_until 標籤
    """
    session_id = input_data.get("session_id", "")
    if not session_id:
        _output_nothing()

    pattern = f"companion-assessment-{session_id}-t*.json"
    paths = sorted(WORKFLOW_DIR.glob(pattern))
    if not paths:
        _output_nothing()

    # 靜默過濾門檻。預設 high；config 可調。
    # 只有同時滿足 (severity >= max_inject_severity) AND
    # (status in {error, needs_followup}) AND (corrective_prompt 非空)
    # 的 advisory 才浮上來。其他自動標 injected 落盤但不展示。
    max_inject_severity = str(config.get("max_inject_severity", "high")).lower()
    _SEV_ORDER = {"low": 0, "medium": 1, "high": 2}
    inject_threshold = _SEV_ORDER.get(max_inject_severity, 2)
    actionable_statuses = {"error", "needs_followup"}

    pending: list[tuple[int, str, Path, Dict[str, Any]]] = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            _log_err("codex:assessment_read", e)
            continue
        if data.get("injected", False):
            continue
        assessment = data.get("assessment") or {}
        if not assessment or assessment.get("status") == "error":
            _mark_injected(path, data)  # 錯誤 assessment 標掉避免堆積
            continue

        # delivery=ignore 直接標掉、不注入
        delivery = str(assessment.get("delivery", "inject")).lower()
        if delivery == "ignore":
            _mark_injected(path, data)
            continue

        # 靜默過濾。低於門檻 / 非可行動狀態 / 無 corrective_prompt → 不注入
        sev = _SEV_ORDER.get(str(assessment.get("severity", "low")).lower(), 0)
        status = str(assessment.get("status", "ok")).lower()
        corrective = (assessment.get("corrective_prompt", "")
                      or assessment.get("recommended_action", ""))
        # handoff_review 是 user 主動要求的跨 session 交接自檢 → 降門檻至 medium，不被預設 high
        # 靜默吞掉（交接缺口即使中度也該讓本 session 當場補，避免下個 session 失真/跑錯）。
        atype_eff = str(data.get("type", assessment.get("_assessment_type", ""))).lower()
        eff_threshold = min(inject_threshold, 1) if atype_eff == "handoff_review" else inject_threshold
        if (sev < eff_threshold
                or status not in actionable_statuses
                or not corrective):
            _mark_injected(path, data)
            try:
                import state as companion_state
                companion_state.increment_metric(session_id, "advisory_suppressed_silent")
            except Exception as e:
                _log_err("codex:metric_suppressed", e)
                pass
            continue

        turn_index = int(data.get("turn_index", 0))
        atype = data.get("type", assessment.get("_assessment_type", "review"))
        pending.append((turn_index, atype, path, data))

    if not pending:
        _output_nothing()

    pending.sort(key=lambda x: (x[0], x[1]))
    pending = pending[:3]

    type_label_map = {
        "plan_review": "Plan Review",
        "turn_audit": "Turn Audit",
        "architecture_review": "Architecture Review",
        "handoff_review": "Handoff 自檢",
    }

    blocks: list[str] = []
    notify_summaries: list[str] = []  # notify_next_turn 短訊收集
    for turn_index, atype, path, data in pending:
        assessment = data.get("assessment", {})
        type_label = type_label_map.get(atype, "Review")
        severity = assessment.get("severity", "low")
        status = assessment.get("status", "ok")
        confidence = str(assessment.get("confidence", "medium")).lower()
        conf_label = _CONFIDENCE_LABEL.get(confidence, "中信心")
        applies = str(assessment.get("applies_until", "next_prompt")).lower()
        applies_label = _APPLIES_LABEL.get(applies, "限本輪")

        summary = assessment.get("summary", "")
        evidence = assessment.get("evidence", "")
        corrective = assessment.get("corrective_prompt", "") or assessment.get("recommended_action", "")

        # assessor 在失敗回退時會帶 notify_next_turn=True
        if assessment.get("notify_next_turn"):
            notify_summaries.append(f"t{turn_index} {summary or status}")

        header = (
            f"[Codex Companion: {type_label} t{turn_index}] "
            f"status={status} severity={severity} "
            f"confidence={confidence}({conf_label}) applies={applies_label}"
        )
        lines = [header]
        if summary:
            lines.append(f"摘要：{summary}")
        if evidence:
            lines.append(f"事證：{evidence}")
        if corrective:
            lines.append(f"建議：{corrective}")
        blocks.append("\n".join(lines))

        _mark_injected(path, data)

    if not blocks:
        _output_nothing()

    # 若任一 pending 帶 notify_next_turn，前置一段提醒短訊
    if notify_summaries:
        reminder = (
            "[Codex Companion 提醒] 上輪審查未取得有效回應，本輪暫退回 heuristics-only。"
            f"來源：{'; '.join(notify_summaries[:3])}"
        )
        blocks.insert(0, reminder)

    # 觀測：累加注入次數（每實際送出 1 個 inject 即 +1）
    try:
        import state as companion_state
        companion_state.increment_metric(session_id, "quality_gap_advises", len(blocks))
    except Exception as e:
        _log_err("codex:metric_advises", e)
        pass

    context_text = "\n\n".join(blocks)
    # Token budget guard: ~600 chars Chinese ≈ 300 tokens per block，整體 cap 1800
    if len(context_text) > 1800:
        context_text = context_text[:1800] + "…(截斷)"

    _output_context("UserPromptSubmit", context_text)


def _within_audit_cap(session_id: str, max_audits: int) -> bool:
    """in-process counter via state.assessments_requested。

    State 由 record_checkpoint 在 spawn audit 之前 +1。subprocess 失敗不會
    decrement → 保守路徑（under-runs not over-runs）。
    """
    import state as companion_state
    st = companion_state.read_state(session_id) or {}
    return int(st.get("assessments_requested", 0)) < max_audits


def handle_post_tool_use(input_data: Dict[str, Any], config: Dict[str, Any]):
    """Accumulate events + spawn audit subprocess on checkpoint.

    直接寫 state；checkpoint 命中 → spawn audit.py。
    """
    import state as companion_state

    session_id = input_data.get("session_id", "")
    tool_name = input_data.get("tool_name", "")

    if not session_id:
        _output_nothing()

    tool_input = input_data.get("tool_input", "")
    if isinstance(tool_input, dict):
        file_path = tool_input.get("file_path", "")
        input_summary = file_path or json.dumps(tool_input, ensure_ascii=False)[:200]
    elif isinstance(tool_input, str):
        file_path = ""
        input_summary = tool_input[:200]
    else:
        file_path = ""
        input_summary = str(tool_input)[:200]

    tool_response = input_data.get("tool_response", "")
    output_summary, failed = _summarize_tool_response(tool_response)

    companion_state.append_event(session_id, {
        "type": "tool_use",
        "tool": tool_name,
        "input": input_summary,
        "output_summary": output_summary,
        "path": file_path,
    })

    checkpoint = _detect_checkpoint(tool_name, file_path, config)
    if checkpoint:
        max_audits = int(config.get("max_audits_per_session", 30))
        if _within_audit_cap(session_id, max_audits):
            companion_state.record_checkpoint(session_id, checkpoint)
            st = companion_state.read_state(session_id) or {}
            verification = _build_verification_signals(input_data, tool_response)
            files_examined = _summarize_files_examined(st.get("tool_trace", []))
            ctx: Dict[str, Any] = {
                "trigger_tool": tool_name,
                "trigger_file": file_path,
                "tool_failed": failed,
                "verification_signals": verification,
                "files_examined": files_examined,
            }
            if checkpoint == "handoff_review" and file_path:
                # 餵 handoff 全文給 codex 對抗式自檢（assessor 經 extra_context 取用）
                ctx["handoff_content"] = _read_handoff_content(file_path)
                ug = st.get("user_goal", "")
                if ug:
                    ctx["user_goal"] = ug
            _spawn_audit_subprocess({
                "session_id": session_id,
                "turn_index": int(st.get("turn_index", 0)),
                "assessment_type": checkpoint,
                "cwd": st.get("cwd", ""),
                "context": ctx,
            })

    _output_nothing()


def handle_stop(input_data: Dict[str, Any], config: Dict[str, Any]):
    """Run heuristic soft gate + score-gated turn audit (subprocess).

    last_assistant_tail 三層 fallback。
    score gate + dedup + max_audits cap。
    state ops in-process；audit 以 subprocess 啟動。
    """
    import state as companion_state

    session_id = input_data.get("session_id", "")
    if not session_id:
        _output_nothing()

    last_assistant_tail = _get_last_assistant_tail(input_data)

    # State：persist tail + increment turn_index
    if last_assistant_tail:
        companion_state.update_last_assistant_tail(session_id, last_assistant_tail)
    companion_state.increment_turn(session_id)

    # ── 共用：讀 guardian + companion state，組 merged_state ─────────────
    guardian_state_path = WORKFLOW_DIR / f"state-{session_id}.json"
    try:
        guardian_state = json.loads(guardian_state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        guardian_state = {}

    comp_state = companion_state.read_state(session_id) or {}
    merged_state = {
        "modified_files": guardian_state.get("modified_files", []),
        "accessed_files": guardian_state.get("accessed_files", []),
        "tool_trace": comp_state.get("tool_trace", []),
        "last_assistant_tail": last_assistant_tail,
    }
    turn_index_post = int(comp_state.get("turn_index", 0))

    # ── heuristic soft gate（BLOCK 權只屬 confident_completion）─
    # silent_advisory 開啟時 heuristic 結果只計數 + 落盤觀測，
    # 不 BLOCK，不打擾對話。BLOCK 路徑保留給未來「明確失敗訊號」用。
    soft_gate_config = config.get("soft_gate", {})
    silent_advisory = bool(config.get("silent_advisory", False))
    if soft_gate_config.get("completion_evidence", True):
        try:
            import heuristics
            results = heuristics.triggered_results(merged_state, stop_text=last_assistant_tail)
            if results:
                threshold = soft_gate_config.get("block_severity_threshold", "high")
                if heuristics.severity_at_or_above(results, threshold):
                    if silent_advisory:
                        try:
                            companion_state.increment_metric(
                                session_id, "silent_advisory_suppressed"
                            )
                        except Exception as e:
                            _log_err("codex:metric_silent_advisory", e)
                            pass
                    else:
                        detail = heuristics.format_for_context(results)
                        template = config.get(
                            "block_template",
                            "Codex Companion 軟閘：偵測到高風險缺漏。\n{detail}\n請補充驗證或修正後再收尾。",
                        )
                        try:
                            block_reason = template.format(detail=detail)
                        except (KeyError, IndexError):
                            block_reason = template + "\n" + detail
                        _output_block(block_reason, session_id=session_id)
        except Exception as e:
            _log_err("codex:heuristics_gate", e)
            pass  # Heuristics failure → degrade gracefully

    # ── score gate / dedup / cap ─────────────────────
    score_threshold = int(config.get("score_threshold", 4))
    max_audits = int(config.get("max_audits_per_session", 30))

    try:
        sys.path.insert(0, str(COMPANION_DIR))
        import scorer
        score = scorer.compute_turn_score(merged_state, stop_text=last_assistant_tail)
    except Exception as e:
        _log_err("codex:turn_score", e)
        score = 99  # 算分失敗安全預設：不抑制觸發，避免漏審查

    if score < score_threshold:
        try:
            companion_state.increment_metric(session_id, "audits_skipped_by_score")
        except Exception as e:
            _log_err("codex:metric_skip_score", e)
            pass
        _output_nothing()

    # Dedup：同 turn_index + turn_audit 已落盤 → skip
    dedup_path = WORKFLOW_DIR / f"companion-assessment-{session_id}-t{turn_index_post}-turn_audit.json"
    if dedup_path.exists():
        _output_nothing()

    # max_audits cap via state counter
    if not _within_audit_cap(session_id, max_audits):
        _output_nothing()

    # ── trigger turn_audit via audit.py subprocess ───────────────────────
    user_goal_hint = (guardian_state.get("user_goal_hint")
                      or guardian_state.get("user_intent") or "")[:500]

    # 實際送出 audit 前 +1（audit ratio 分母）
    try:
        companion_state.increment_metric(session_id, "audits_total_attempted")
    except Exception as e:
        _log_err("codex:metric_audit_attempt", e)
        pass

    companion_state.record_checkpoint(session_id, "turn_audit")
    files_examined = _summarize_files_examined(comp_state.get("tool_trace", []))
    _spawn_audit_subprocess({
        "session_id": session_id,
        "turn_index": turn_index_post,
        "assessment_type": "turn_audit",
        "cwd": comp_state.get("cwd", ""),
        "context": {
            "user_goal_hint": user_goal_hint,
            "last_assistant_tail": last_assistant_tail,
            "turn_score": score,
            "files_examined": files_examined,
            "verification_signals": {
                "stop_text_len": len(last_assistant_tail),
                "stop_text_source": "fallback_layered",
            },
        },
    })

    _output_nothing()


def _flush_metrics_to_reflection(session_id: str) -> None:
    """觀測：把本 session 的 codex_companion 計數附加到
    memory/wisdom/reflection_metrics.json 的 codex_companion.sessions 陣列。

    最多保留最近 100 筆，與 wisdom_engine 既有結構共存（top-level codex_companion
    為新欄位，wisdom_engine 不讀，不破壞既有路徑）。
    全 zero 的 session 跳過避免噪音。
    """
    try:
        import state as companion_state
        metrics = companion_state.read_metrics(session_id)
    except Exception as e:
        _log_err("codex:metrics_read", e)
        return
    if not metrics or not any(metrics.values()):
        return

    metrics_path = CLAUDE_DIR / "memory" / "wisdom" / "reflection_metrics.json"
    try:
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return  # 既有檔不存在/壞檔不主動建立，避免覆寫風險

    section = data.setdefault("codex_companion", {})
    sessions = section.setdefault("sessions", [])
    from datetime import datetime, timezone
    sessions.append({
        "session_id": session_id,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **metrics,
    })
    if len(sessions) > 100:
        section["sessions"] = sessions[-100:]
    try:
        tmp = metrics_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(metrics_path)
    except OSError as e:
        _log_err("codex:metrics_flush_write", e)
        pass


def handle_session_end(input_data: Dict[str, Any], config: Dict[str, Any]):
    session_id = input_data.get("session_id", "")
    if session_id:
        _flush_metrics_to_reflection(session_id)
    _output_nothing()


# ─── Main dispatcher ─────────────────────────────────────────────────────────

HANDLERS = {
    "SessionStart": handle_session_start,
    "UserPromptSubmit": handle_user_prompt_submit,
    "PostToolUse": handle_post_tool_use,
    "Stop": handle_stop,
    "SessionEnd": handle_session_end,
}


def main():
    # Force UTF-8 on Windows
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")

    # Fast path: read config, check enabled
    config = _load_config()
    if not config.get("enabled", False):
        sys.exit(0)

    # 沒裝 codex CLI 的環境直接退出，避免每輪 spawn 失敗後落盤 assessment 檔與 log
    codex_bin = config.get("codex_binary", "codex")
    if not (os.path.isfile(codex_bin) or shutil.which(codex_bin)):
        sys.exit(0)

    # Read stdin
    try:
        raw = sys.stdin.buffer.read()
        input_data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    event = input_data.get("hook_event_name", "")
    handler = HANDLERS.get(event)
    if handler is None:
        sys.exit(0)

    try:
        handler(input_data, config)
    except SystemExit:
        raise
    except Exception as e:
        # Never crash — log to stderr and exit cleanly
        print(f"[codex_companion] Error in {event}: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
