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

# EnterPlanMode 不觸發：進 plan mode 當下計畫尚不存在，審必空
# （動作紀錄不得替代內容本體）。
_PLAN_TOOLS = {"ExitPlanMode"}
_WRITE_TOOLS = {"Edit", "Write"}
# 跨 session 交接檔：_staging/next-phase*.md 或檔名含 handoff（持久化 artifact，
# /continue 接手端實際讀的就是它）。命中 → 對抗式 handoff 自檢（Q2）。
_NEXT_PHASE_RE = re.compile(r"(?:next-phase|next_phase|handoff)[^/\\]*\.md$", re.IGNORECASE)
# plan-mode 工作流：計畫先 Write 到 plans/<name>.md 再 ExitPlanMode。
_PLAN_ARTIFACT_RE = re.compile(r"/plans/[^/]+\.md$", re.IGNORECASE)
# 驗收規格檔（Phase 1 落地契約）與其「完成」標記 — acceptance_review 的權威觸發訊號。
_SPEC_PATH_RE = re.compile(r"/\.claude/verify/acceptance-[^/]+\.md$", re.IGNORECASE)
_STATUS_DONE_RE = re.compile(r"^status:\s*done\s*$", re.IGNORECASE | re.MULTILINE)


def _resolve_plan_artifact(tool_input: Any, tool_trace: list) -> tuple[str, str]:
    """回 (artifact_path, plan_inline) 供 plan_review 取計畫正文。

    主路徑：反掃本 session trace，取最近一筆 Write/Edit 到 plans/*.md 的路徑
    （assessor 於審計時點讀實體檔，拿到最新版全文）。
    保險路徑：舊版 harness 的 ExitPlanMode 帶 tool_input.plan 全文 → inline。
    兩者皆空 → caller skip 本次審計，不拿動作紀錄冒充計畫。
    """
    inline = ""
    if isinstance(tool_input, dict):
        p = tool_input.get("plan", "")
        if isinstance(p, str):
            inline = p.strip()
    for t in reversed(tool_trace or []):
        if t.get("tool") not in _WRITE_TOOLS:
            continue
        path = (t.get("path") or "").strip()
        if path and _PLAN_ARTIFACT_RE.search(path.replace("\\", "/")):
            return path, inline
    return "", inline


def _detect_checkpoint(
    tool_name: str, file_path: str, config: Dict[str, Any]
) -> Optional[str]:
    """Determine if this tool use triggers a checkpoint.

    (1) ExitPlanMode → plan_review
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


# ─── Event handlers ──────────────────────────────────────────────────────────
# （artifact 內容實體化與 prompt 材料組裝集中在 tools/codex-companion/
#   artifact_io.py + assessor.build_prompt；hook 只傳觸發事實。）


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

    # 首個非空 prompt = 使用者原始目標（codex brief 的「背景」要件；
    # state.set_user_goal 為 write-once，後續 prompt 不覆寫）
    try:
        import state as companion_state
        companion_state.set_user_goal(
            session_id, str(input_data.get("prompt", "") or "")
        )
    except Exception as e:
        _log_err("codex:user_goal_capture", e)

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
        # acceptance_review 影子期同樣降至 medium：影子數據要「看得見」才校得準（fail 預設 medium）。
        atype_eff = str(data.get("type", assessment.get("_assessment_type", ""))).lower()
        eff_threshold = (min(inject_threshold, 1)
                         if atype_eff in ("handoff_review", "acceptance_review")
                         else inject_threshold)
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
        "acceptance_review": "驗收裁判（影子）",
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


def _within_audit_cap(
    session_id: str, max_audits: int, config: Optional[Dict[str, Any]] = None,
    assessment_type: str = "",
) -> bool:
    """配額閘（Q8 分桶：acceptance_review 與既有審查互不餓死）。

    共用總量 max_audits（預設 30）之上加兩條邊界：
      - acceptance_review 自己最多用 `acceptance_review_max`（其他類型永遠
        保有 max_audits - max 的空間）
      - 其他類型最多用 max_audits - `acceptance_review_min`
        （acceptance_review 永遠保有 min 個名額，不被前面燒光）

    State 由 record_checkpoint 在 spawn audit 之前 +1。subprocess 失敗不會
    decrement → 保守路徑（under-runs not over-runs）。
    """
    import state as companion_state
    st = companion_state.read_state(session_id) or {}
    total = int(st.get("assessments_requested", 0))
    if total >= max_audits:
        return False

    quota = (config or {}).get("audit_quota", {}) or {}
    acc_min = int(quota.get("acceptance_review_min", 6))
    acc_max = int(quota.get("acceptance_review_max", 8))
    by_type = st.get("assessments_by_type", {}) or {}
    acc_used = int(by_type.get("acceptance_review", 0))

    if assessment_type == "acceptance_review":
        return acc_used < acc_max
    # 其他類型：留 acc_min 個名額給驗收裁判
    others_used = total - acc_used
    return others_used < max(0, max_audits - acc_min)


# ─── acceptance_review（Phase 2 影子裁判） ───────────────────────────────────


def _acceptance_enabled(config: Dict[str, Any]) -> bool:
    return bool(config.get("acceptance_review", {}).get("enabled", True))


def _record_unbound(
    session_id: str, turn_index: int, cwd: str, binding_info: Dict[str, Any],
    trigger: str,
) -> None:
    """綁不到規格檔 → 不發裁判，直接落一筆 uncertain。

    INV-CASE-BINDING-OR-UNCERTAIN：不得用「最新一份」猜案卷。
    只在 ambiguous/other_session 落筆（`none` 代表本任務不在分級線上，
    每次收尾都記等於噪音）。
    """
    import acceptance
    import state as companion_state
    if binding_info.get("binding") == acceptance.BINDING_NONE:
        return
    acceptance.append_audit({
        "session_id": session_id, "turn_index": turn_index, "cwd": cwd,
        "spec_path": "", "task_slug": "",
        "binding": binding_info.get("binding", ""),
        "trigger": trigger,
        "verdict": "uncertain", "score": -1,
        "problems": [], "problems_count": 0,
        "summary": "案卷未組（任務與驗收規格檔無法唯一對應）",
        "uncertain_reason": binding_info.get("uncertain_reason", ""),
        "candidates": binding_info.get("candidates", [])[:10],
    })
    try:
        companion_state.increment_metric(session_id, "acceptance_unbound")
    except Exception as e:
        _log_err("codex:metric_acceptance_unbound", e)


def _maybe_spawn_acceptance_review(
    session_id: str, turn_index: int, cwd: str, config: Dict[str, Any],
    trigger: str, spec_path_hint: str = "",
) -> None:
    """解析綁定 → 過閘 → spawn 案卷審計。影子模式：全程不 block。

    trigger: "stop_claim"（收尾宣稱完成）或 "spec_done"（規格檔 status 改 done）。
    spec_path_hint：spec_done 觸發時必傳——剛標 done 的規格檔已非 open，
    resolve_binding 掃不到它；但「哪份規格剛完成」本身就是唯一綁定事實，
    直接對 hint 檔驗 session_id 歸屬即可，不經 open 掃描。
    """
    import acceptance
    import state as companion_state

    if spec_path_hint:
        fm, text = acceptance.read_spec(spec_path_hint)
        if not text:
            return  # 檔案讀不到（已被移走等）→ 無案卷可綁，靜默
        if fm.get("session_id", "") == session_id:
            info = {
                "binding": acceptance.BINDING_BOUND,
                "spec_path": spec_path_hint,
                "task_slug": fm.get("task_slug", ""),
                "candidates": [spec_path_hint],
                "uncertain_reason": "",
            }
        else:
            info = {
                "binding": acceptance.BINDING_OTHER_SESSION,
                "spec_path": "", "task_slug": "",
                "candidates": [spec_path_hint],
                "uncertain_reason": (
                    "被標記完成的規格檔 frontmatter session_id 屬其他 session，"
                    "無法確認是本 session 的任務，依綁定契約回 uncertain。"
                ),
            }
    else:
        info = acceptance.resolve_binding(session_id, cwd)
    if info["binding"] != acceptance.BINDING_BOUND:
        _record_unbound(session_id, turn_index, cwd, info, trigger)
        return

    spec_path = info["spec_path"]
    st = companion_state.read_state(session_id) or {}
    per_spec = (st.get("acceptance_reviews", {}) or {})
    max_per_spec = int(config.get("acceptance_review", {}).get("max_per_spec", 2))
    if int(per_spec.get(spec_path.replace("\\", "/"), 0)) >= max_per_spec:
        return

    dedup = WORKFLOW_DIR / (
        f"companion-assessment-{session_id}-t{turn_index}-acceptance_review.json"
    )
    if dedup.exists():
        return

    max_audits = int(config.get("max_audits_per_session", 30))
    if not _within_audit_cap(session_id, max_audits, config, "acceptance_review"):
        # 可觀測性鐵律：撞配額不得無聲跳過
        _log_err(
            "codex:acceptance_quota",
            RuntimeError(f"acceptance_review quota exhausted (session total cap {max_audits})"),
        )
        try:
            companion_state.increment_metric(session_id, "acceptance_quota_blocked")
        except Exception as e:
            _log_err("codex:metric_acceptance_quota", e)
        return

    companion_state.record_checkpoint(session_id, "acceptance_review", spec_path=spec_path)
    try:
        companion_state.increment_metric(session_id, "acceptance_reviews_spawned")
    except Exception as e:
        _log_err("codex:metric_acceptance_spawned", e)
    _spawn_audit_subprocess({
        "session_id": session_id,
        "turn_index": turn_index,
        "assessment_type": "acceptance_review",
        "cwd": cwd,
        "context": {
            "spec_path": spec_path,
            "task_slug": info.get("task_slug", ""),
            "binding": info["binding"],
            "binding_reason": "",
            "trigger": trigger,
        },
    })


_SEV_RANK = {"low": 0, "medium": 1, "high": 2}


def _enforce_acceptance_gate(
    session_id: str, turn_index: int, cwd: str, config: Dict[str, Any],
    merged_state: Dict[str, Any], last_assistant_tail: str,
) -> None:
    """Phase 3 轉正閘：Stop 時同步審驗收，fail 且 severity 達標才 block。

    紅線（全部程式化）：
      - 只有 bound（本 session 唯一 open 規格）才審；其餘 uncertain 記錄後放行。
      - block 必經 map_acceptance_verdict（unbound/無證據 fail → uncertain 不 block）。
      - 修訂上限＝top-level stop_gate_max_blocks（預設 2）；達上限不再審、
        強制放行 + 揭露（advisory 次輪注入 + metric）。
      - 裁判逾時/無效 → uncertain → 放行 + 揭露，不卡收尾。
    無 block 需要時靜默返回（advisory 走既有 assessment 檔管道）。
    """
    import acceptance
    import state as companion_state

    info = acceptance.resolve_binding(session_id, cwd)
    if info["binding"] != acceptance.BINDING_BOUND:
        _record_unbound(session_id, turn_index, cwd, info, "stop_enforce")
        return
    spec_path = info["spec_path"]

    # 修訂上限：第 3 次起不再審，強制放行＋揭露
    try:
        full_cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        full_cfg = {}
    max_blocks = int(full_cfg.get("stop_gate_max_blocks", 2))
    blocks_used = companion_state.get_spec_blocks(session_id, spec_path)
    if blocks_used >= max_blocks:
        try:
            companion_state.increment_metric(session_id, "acceptance_forced_release")
        except Exception as e:
            _log_err("codex:metric_forced_release", e)
        _log_err("codex:acceptance_force_release", RuntimeError(
            f"spec {Path(spec_path).name} 已達 {max_blocks} 次修訂上限，強制放行"))
        companion_state.write_assessment(session_id, turn_index, "acceptance_review", {
            "status": "needs_followup", "severity": "high",
            "category": "completion_risk", "delivery": "inject",
            "confidence": "high", "applies_until": "next_prompt",
            "turn_index": turn_index, "verdict": "fail",
            "summary": f"驗收修訂已達 {max_blocks} 次上限，本次強制放行",
            "evidence": f"規格檔：{spec_path}",
            "corrective_prompt": (
                "【強制放行揭露】此任務的驗收裁判連續未過且已達修訂上限。"
                "請在下一則回覆向 user 誠實列出：哪些驗收條目未過、為什麼、"
                "目前的實際狀態——不得宣稱全部完成。"
            ),
        })
        return

    # 配額與 per-spec 上限（與影子路共用計數）
    st = companion_state.read_state(session_id) or {}
    per_spec = (st.get("acceptance_reviews", {}) or {})
    max_per_spec = int(config.get("acceptance_review", {}).get("max_per_spec", 2))
    if int(per_spec.get(spec_path.replace("\\", "/"), 0)) >= max_per_spec:
        return
    max_audits = int(config.get("max_audits_per_session", 30))
    if not _within_audit_cap(session_id, max_audits, config, "acceptance_review"):
        try:
            companion_state.increment_metric(session_id, "acceptance_quota_blocked")
        except Exception as e:
            _log_err("codex:metric_acceptance_quota", e)
        return

    # 同步審（在 hook 行程內；settings.json Stop timeout 已配合放寬）
    companion_state.record_checkpoint(session_id, "acceptance_review", spec_path=spec_path)
    try:
        companion_state.increment_metric(session_id, "acceptance_reviews_spawned")
    except Exception as e:
        _log_err("codex:metric_acceptance_spawned", e)

    import assessor
    digest, diff_truncated = acceptance.collect_diff_digest(cwd)
    enforce_cfg = dict(config)
    enforce_cfg["assessment_timeout"] = int(
        config.get("acceptance_review", {}).get("enforce_timeout", 60))
    ctx = {
        "spec_path": spec_path, "task_slug": info.get("task_slug", ""),
        "binding": "bound", "binding_reason": "", "trigger": "stop_enforce",
        "turn_index": turn_index,
        "user_goal": st.get("user_goal", ""),
        "last_assistant_tail": last_assistant_tail,
        "diff_digest": digest,
    }
    result = assessor.run_assessment(
        "acceptance_review", session_id, st.get("tool_trace", []), cwd, ctx, enforce_cfg)
    result["_turn_index"] = turn_index

    # 雙軌數據不中斷：enforce 判定照寫 jsonl + assessment 檔
    problems = result.get("problems") or []
    acceptance.append_audit({
        "session_id": session_id, "turn_index": turn_index, "cwd": cwd,
        "model": config.get("model", ""), "spec_path": spec_path,
        "task_slug": info.get("task_slug", ""), "binding": "bound",
        "trigger": "stop_enforce",
        "verdict": result.get("verdict", ""), "score": result.get("score", -1),
        "severity": result.get("severity", "low"),
        "confidence": result.get("confidence", ""),
        "summary": result.get("summary", ""),
        "problems_count": len(problems), "problems": problems[:10],
        "uncertain_reason": result.get("uncertain_reason", ""),
        "prompt_chars": result.get("_prompt_chars", 0),
        "diff_truncated": diff_truncated,
        "codex_attempts": result.get("_attempts", 1),
        "enforce_blocks_used": blocks_used,
    })
    companion_state.write_assessment(
        session_id, turn_index, "acceptance_review", result)

    verdict = str(result.get("verdict", "")).lower()
    if verdict == "uncertain" and result.get("notify_next_turn"):
        # 裁判失效（逾時/無效輸出）→ 放行 + 訊號（advisory 次輪注入）
        try:
            companion_state.increment_metric(session_id, "acceptance_judge_degraded")
        except Exception as e:
            _log_err("codex:metric_judge_degraded", e)
        return

    threshold = _SEV_RANK.get(str(
        config.get("acceptance_review", {}).get("enforce_severity_threshold", "high")
    ).lower(), 2)
    sev = _SEV_RANK.get(str(result.get("severity", "low")).lower(), 0)
    if verdict != "fail" or sev < threshold:
        return  # pass / uncertain / 低嚴重度 fail → 放行，advisory 照既有管道

    new_count = companion_state.increment_spec_blocks(session_id, spec_path)
    try:
        companion_state.increment_metric(session_id, "acceptance_enforce_blocks")
    except Exception as e:
        _log_err("codex:metric_enforce_blocks", e)
    lines = [
        f"[驗收裁判] 收尾被擋（第 {new_count}/{max_blocks} 次；"
        f"第 {max_blocks + 1} 次將強制放行並要求向 user 誠實揭露未過項）。",
        f"規格檔：{spec_path}",
        f"判定：{result.get('summary', '')}",
        "未達標條目（逐條證據）：",
    ]
    for p in problems[:5]:
        lines.append(f"  - {p.get('criterion', '?')}｜事證：{p.get('evidence', '')}"
                     f"｜{p.get('explanation', '')}")
    lines.append(
        "請按證據補做或修正後再收尾；若裁判誤判，請在回覆中說明依據並再次收尾。")
    _output_block("\n".join(lines), session_id=session_id)


def _spec_marked_done(tool_name: str, file_path: str, tool_input: Any) -> bool:
    """規格檔被改成 status: done — 「宣稱完成」的權威訊號（案卷最完整的時點）。

    Write 看 content、Edit 看 new_string；讀不到內容就不猜。
    """
    if tool_name not in _WRITE_TOOLS or not file_path:
        return False
    if not _SPEC_PATH_RE.search(file_path.replace("\\", "/")):
        return False
    if not isinstance(tool_input, dict):
        return False
    body = str(tool_input.get("content", "") or tool_input.get("new_string", "") or "")
    return bool(_STATUS_DONE_RE.search(body))


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
    output_summary, _failed = _summarize_tool_response(tool_response)

    companion_state.append_event(session_id, {
        "type": "tool_use",
        "tool": tool_name,
        "input": input_summary,
        "output_summary": output_summary,
        "path": file_path,
    })

    # 驗收規格檔改成 status: done → 權威完成訊號，立刻組案卷（影子，不阻斷）
    if _acceptance_enabled(config) and _spec_marked_done(tool_name, file_path, tool_input):
        try:
            st = companion_state.read_state(session_id) or {}
            _maybe_spawn_acceptance_review(
                session_id, int(st.get("turn_index", 0)),
                st.get("cwd", "") or input_data.get("cwd", ""),
                config, "spec_done", spec_path_hint=file_path,
            )
        except Exception as e:
            _log_err("codex:acceptance_spec_done", e)

    checkpoint = _detect_checkpoint(tool_name, file_path, config)
    if checkpoint:
        max_audits = int(config.get("max_audits_per_session", 30))
        if _within_audit_cap(session_id, max_audits, config, checkpoint):
            st = companion_state.read_state(session_id) or {}
            # ctx 只傳觸發事實；內容實體化在 assessor（規則唯一來源）
            ctx: Dict[str, Any] = {}
            if checkpoint == "plan_review":
                artifact_path, plan_inline = _resolve_plan_artifact(
                    tool_input, st.get("tool_trace", [])
                )
                if not artifact_path and not plan_inline:
                    # 無計畫正文可審 → skip（動作紀錄不得替代內容本體）；
                    # fail-open 但留訊號：stderr + metric
                    _log_err(
                        "codex:plan_artifact_missing",
                        ValueError(f"no plan artifact resolved (trigger={tool_name})"),
                    )
                    try:
                        companion_state.increment_metric(
                            session_id, "audits_skipped_no_artifact"
                        )
                    except Exception as e:
                        _log_err("codex:metric_skip_no_artifact", e)
                    _output_nothing()
                if artifact_path:
                    ctx["artifact_path"] = artifact_path
                if plan_inline:
                    ctx["plan_inline"] = plan_inline
            elif checkpoint == "handoff_review" and file_path:
                ctx["artifact_path"] = file_path
            companion_state.record_checkpoint(session_id, checkpoint)
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

    # ── acceptance_review（enforce=同步閘；否則影子 async）─────────────────
    # 觸發條件：完成宣稱 + 本 turn 真有改動 + 綁得到本 session 唯一 open 規格。
    # enforce 開啟 → 同步審，fail+severity 達標才 block（其餘一律放行）；
    # enforce 關閉 → 維持影子 async，全程 advisory。
    if _acceptance_enabled(config):
        try:
            import heuristics as _heur
            claimed = _heur._has_completion_claim(merged_state, last_assistant_tail)
            changed = _heur._has_state_change(merged_state)
            if claimed and changed:
                cwd_eff = comp_state.get("cwd", "") or input_data.get("cwd", "")
                if bool(config.get("acceptance_review", {}).get("enforce", False)):
                    _enforce_acceptance_gate(
                        session_id, turn_index_post, cwd_eff, config,
                        merged_state, last_assistant_tail,
                    )
                else:
                    _maybe_spawn_acceptance_review(
                        session_id, turn_index_post, cwd_eff, config, "stop_claim",
                    )
        except SystemExit:
            raise  # block 路徑的正常出口
        except Exception as e:
            _log_err("codex:acceptance_stop", e)

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
    if not _within_audit_cap(session_id, max_audits, config, "turn_audit"):
        _output_nothing()

    # ── trigger turn_audit via audit.py subprocess ───────────────────────
    # 實際送出 audit 前 +1（audit ratio 分母）
    try:
        companion_state.increment_metric(session_id, "audits_total_attempted")
    except Exception as e:
        _log_err("codex:metric_audit_attempt", e)
        pass

    companion_state.record_checkpoint(session_id, "turn_audit")
    _spawn_audit_subprocess({
        "session_id": session_id,
        "turn_index": turn_index_post,
        "assessment_type": "turn_audit",
        "cwd": comp_state.get("cwd", ""),
        "context": {
            "last_assistant_tail": last_assistant_tail,
            "turn_score": score,
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
