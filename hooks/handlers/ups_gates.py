"""
handlers/ups_gates.py — UserPromptSubmit detect 段（前置閘）

從 user_prompt_submit.py 拆出（2026-06-12 複雜度熱點重構）。
職責：每輪 prompt 的前置偵測與輕量通知，全部在 atom 注入之前執行：
- evasion guard 旁路（追蹤近 5 則 prompt、清 failing_tests）
- V4.1 user decision detector gate
- confirmed extractions / veto
- long_die response（停用/保持 backend）
- Hot Cache 注入
- atom-write guard reminder（建議階段不該宣告 [固]/[觀]）
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

from wg_core import _now_iso, _atom_debug_log, _atom_debug_error
from wg_extraction import detect_signal
from wg_evasion import is_dismiss_prompt
from handlers._shared import (
    read_hot_cache, mark_injected, format_injection_line,
)

# Ollama client（dispatcher 已加 tools/ 到 sys.path）
sys.path.insert(0, str(Path.home() / ".claude" / "tools"))
try:
    from ollama_client import check_long_die_status, disable_backend, OllamaClient
except ImportError:
    check_long_die_status = lambda: None  # noqa: E731
    disable_backend = lambda *a, **k: False  # noqa: E731
    OllamaClient = None


def run_pre_gates(
    session_id: str,
    state: Dict[str, Any],
    config: Dict[str, Any],
    clean_prompt: str,
    prompt_lower: str,
    lines: List[str],
) -> int:
    """執行 detect 段全部前置閘。mutate state / append lines，回傳 hot_cache_tokens。"""
    # ── Evasion Guard: 追蹤近 5 則 user prompt ─────
    rup = state.setdefault("recent_user_prompts", [])
    rup.append(clean_prompt[:500])
    if len(rup) > 5:
        state["recent_user_prompts"] = rup[-5:]

    if state.get("failing_tests") and is_dismiss_prompt(clean_prompt):
        state["failing_tests"] = []

    # ─── V4.1: User Decision Detector gate ────────────────────────────
    ue_config = config.get("userExtraction", {})
    if ue_config.get("enabled", False):
        try:
            det = detect_signal(clean_prompt)
            if det.get("signal"):
                turn_n = state.get("topic_tracker", {}).get("prompt_count", 0)
                pending = state.setdefault("pending_user_extract", [])
                pending.append({
                    "turn_id": f"{session_id}-{turn_n}",
                    "prompt": clean_prompt,
                    "score": det["score"],
                    "matched": det["matched"],
                    "ts": _now_iso(),
                })
                if len(pending) > 10:
                    state["pending_user_extract"] = pending[-10:]
        except Exception as e:
            _atom_debug_error("V4.1:user_extract_gate", e)

    # ─── V4.1 [F5]: Confirmed extractions ──
    confirmed = state.get("confirmed_extractions", [])
    if confirmed:
        veto = any(kw in prompt_lower for kw in ("否", "不要記", "別記", "取消記憶"))
        if veto:
            for ext in confirmed:
                _atom_debug_log(
                    "user-extract:rejected",
                    f"User vetoed: {ext.get('statement', '')[:80]}",
                    config,
                )
            state["confirmed_extractions"] = []
        else:
            for ext in confirmed:
                stmt = ext.get("statement", "")
                lines.append(
                    f"[V4.1] 偵測到決策語句：「{stmt}」— 將記為 atom。回覆「否」可攔截。"
                )
            state["confirmed_extractions"] = []

    # ─── Dual-Backend: long_die user response ─────
    try:
        long_die = check_long_die_status()
        if long_die:
            backend_name = long_die.get("backend", "")
            if any(kw in prompt_lower for kw in ("停用", "disable")):
                if disable_backend(backend_name):
                    if OllamaClient is not None:
                        OllamaClient._clear_long_die_marker()
                    lines.append(
                        f"[Dual-Backend] 已永久停用 '{backend_name}'。"
                        f"如需重新啟用，修改 config.json 中 enabled: true。"
                    )
                else:
                    lines.append(f"[Dual-Backend] 停用 '{backend_name}' 失敗，請手動修改 config.json。")
            elif any(kw in prompt_lower for kw in ("保持", "keep", "忽略")):
                if OllamaClient is not None:
                    OllamaClient._clear_long_die_marker()
                lines.append(f"[Dual-Backend] 保持 '{backend_name}'，long_die 將在時間段到期後自動恢復。")
    except Exception as e:
        print(f"[dual-backend] Long DIE response error: {e}", file=sys.stderr)

    # ─── Hot Cache Fast Path ───────────────────────────────
    hot_cache_tokens = 0
    if read_hot_cache:
        try:
            hot_data = read_hot_cache(session_id)
            if hot_data:
                lines.append(format_injection_line(hot_data))
                hot_cache_tokens = hot_data.get("token_estimate", 50)
                mark_injected(session_id)
        except Exception:
            pass

    # ─── Atom-Write Guard: confidence gate reminder ─────────────────────
    atom_write_triggers = (
        "記住", "記下來", "存起來", "存下來", "值得存", "值得記",
        "寫成 atom", "寫 atom", "存成 atom", "存atom", "存成[固]", "存成 [固]",
        "存成[觀]", "存成 [觀]", "記為[固]", "記為 [固]",
    )
    if any(kw in clean_prompt for kw in atom_write_triggers):
        lines.append(
            "[Atom-Write Guard] 偵測到記憶寫入意圖。硬規則："
            "(1) 新 atom 一律 [臨]，MCP atom_write 會 reject [固]/[觀]；"
            "(2) 單次成功 ≠ 穩定模式，需 4+ session 命中才建議晉升；"
            "(3) 晉升走 atom_promote（Confirmations ≥4→[觀]/≥10→[固] 主軌，或效用 Wilson 下界 ≥0.6 且 n≥3；ReadHits 已退出晉升、僅純曝光計數），不手動改 frontmatter；"
            "(4) 若是更新既有 atom，用 mode=append 並保留原 confidence。"
        )

    return hot_cache_tokens
