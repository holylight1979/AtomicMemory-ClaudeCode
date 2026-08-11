"""
handlers/ups_context.py — UserPromptSubmit context build 段

從 user_prompt_submit.py 拆出（複雜度熱點重構）。
職責：atom 注入前的場景脈絡建構：
- session context（first prompt only：episodic 搜尋 + proactive classification）
- wisdom engine situation classification
- parallel agent suggestion
- _AIDocs keyword matching
- JIT internal pipeline reference（記憶系統開發場景）

公開函式 build_context() 回傳扣除保留量後的 budget。
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

from wg_core import (
    MEMORY_DIR, EPISODIC_DIR, _atom_debug_error,
    _estimate_tokens, truncate_to_tokens,
)
from wg_atoms import (
    any_trigger_hit,
    _search_episodic_context, _build_session_context,
    _proactive_classify,
)
from handlers._shared import WISDOM_AVAILABLE, classify_situation

# lib funnel（atom_access）：episodic 注入曝光遙測。確保 ~/.claude 在 path（handler 執行時 cwd 不定）。
_LIB_PARENT = str(Path.home() / ".claude")
if _LIB_PARENT not in sys.path:
    sys.path.insert(0, _LIB_PARENT)
from lib.atom_access import increment_read_hits  # noqa: E402


def _record_episodic_exposure(injected: List[Dict[str, Any]]) -> None:
    """對「實際注入」的 episodic atom read_hits++，讓 episodic 效用可測。

    背景：56 顆 episodic 長期 read_hits=0（注入從不 increment）→ 系統對「episodic
    有沒有用」永久自盲、易被誤判雞肋誤拔。read_hits 定義＝注入曝光次數，此處補上。

    以 file_path（vector 回傳，跨 scope 正確）定位、`is_file()` 驗證後才計數 —— 對已被
    purge 搬走/不存在的路徑一律跳過，避免 `increment_read_hits` 憑空建 sidecar 污染。
    走 lib.atom_access funnel、fail-open（逐筆 try/except，不阻斷注入）。
    """
    for ep in injected:
        try:
            fp = ep.get("file_path") or ""
            path = Path(fp) if fp else None
            if not (path and path.is_file()):
                name = ep.get("atom_name", "")
                cand = EPISODIC_DIR / f"{name}.md" if name else None
                path = cand if (cand and cand.is_file()) else None
            if path is None:
                continue
            increment_read_hits(path, source="hook:atom-inject")
        except (OSError, ValueError) as e:
            _atom_debug_error("注入:episodic_read_hits", e)


def _is_memory_system_dev(prompt_lower: str, cwd: str) -> bool:
    """嚴格判斷是否為記憶系統開發場景。需 2+ 命中或 CWD 匹配。"""
    cwd_norm = cwd.replace("\\", "/")
    if "/.claude/hooks" in cwd_norm or "/.claude/tools" in cwd_norm:
        return True
    MEM_KEYWORDS = [
        "workflow-guardian", "wg_", "atom memory", "原子記憶",
        "wisdom_engine", "記憶系統", "memory system",
        "hot_cache", "extract-worker", "vector service",
        "hook pipeline", "萃取管線", "注入管線",
    ]
    hits = sum(1 for kw in MEM_KEYWORDS if kw in prompt_lower)
    return hits >= 2


def build_context(
    session_id: str,
    state: Dict[str, Any],
    config: Dict[str, Any],
    prompt: str,
    clean_prompt: str,
    prompt_lower: str,
    budget: int,
    lines: List[str],
) -> int:
    """執行 context build 段。mutate state / append lines，回傳調整後 budget。"""
    # ─── Phase 0: Session Context Injection ────────
    if not state.get("session_context_injected", False):
        state["session_context_injected"] = True
        episodic_results = _search_episodic_context(prompt, config, session_id=session_id)
        if episodic_results:
            ctx_lines = _build_session_context(episodic_results)
            if ctx_lines:
                lines.extend(ctx_lines)
                sc_config = config.get("session_context", {})
                reserved = sc_config.get("reserved_tokens", 200)
                budget = max(budget - reserved, 500)
                # 效用遙測：ctx_lines[0] 是 header，其餘資料行由 _build_session_context 按序
                # 納入 episodic_results 直到 char_budget 用完 → 被注入者精準對應其前綴。
                _record_episodic_exposure(episodic_results[:len(ctx_lines) - 1])
            proactive_lines = _proactive_classify(state, episodic_results, prompt, config)
            lines.extend(proactive_lines)

    # ─── Wisdom Engine — situation classification ──────────
    if WISDOM_AVAILABLE and classify_situation is not None:
        try:
            mod_paths = [m["path"] for m in state.get("modified_files", [])]
            tracker = state.get("topic_tracker", {})
            prompt_analysis = {
                "intent": tracker.get("intent_distribution", {}).get("top", ""),
                "keywords": tracker.get("keyword_signals", []),
                "estimated_files": max(len(mod_paths), 1),
            }
            result = classify_situation(prompt_analysis)
            if result.get("inject"):
                lines.append(result["inject"])
            cur = result.get("approach", "direct")
            prev = state.get("wisdom_approach", "direct")
            rank = {"direct": 0, "confirm": 1, "plan": 2}
            if rank.get(cur, 0) > rank.get(prev, 0):
                state["wisdom_approach"] = cur
        except Exception as e:
            print(f"Wisdom prompt error: {e}", file=sys.stderr)

    # ─── Research Fan-out Suggestion ───────────────
    # 先於 parallel 判定：research 提示已含並行指示，命中則抑制 parallel 免重複佔位。
    research_hit = False
    try:
        from wg_research import detect_research_fanout
        research_line = detect_research_fanout(clean_prompt, state, config)
        if research_line:
            lines.append(research_line)
            research_hit = True
    except Exception as e:
        _atom_debug_error("ResearchFanout", e)

    # ─── Parallel Agent Suggestion ─────────────────
    if not research_hit:
        try:
            from wg_parallel import detect_parallel_opportunity
            parallel_line = detect_parallel_opportunity(clean_prompt, state, config)
            if parallel_line:
                lines.append(parallel_line)
        except Exception as e:
            _atom_debug_error("ParallelSuggest", e)

    # ─── _AIDocs keyword matching ──────────────────
    aidocs_state = state.get("aidocs", {})
    aidocs_kw_map = aidocs_state.get("keywords", {})
    max_matches = config.get("aidocs", {}).get("max_prompt_matches", 3)
    if aidocs_kw_map and prompt.strip():
        matched_docs: List[str] = []
        for fname, keywords in aidocs_kw_map.items():
            if any_trigger_hit(keywords, prompt_lower):
                matched_docs.append(fname)
        if matched_docs and len(matched_docs) <= 5:
            aidocs_root = aidocs_state.get("project_root", "")
            pointer_lines = ["[Guardian:AIDocs] Relevant project docs:"]
            for doc in matched_docs[:max_matches]:
                desc = ""
                for f, d in aidocs_state.get("entries", []):
                    if f == doc:
                        desc = d
                        break
                doc_path = f"_AIDocs/{doc}" if aidocs_root else doc
                pointer_lines.append(f"  → Read `{doc_path}` — {desc[:80]}")
            lines.extend(pointer_lines)

    # ── JIT load internal pipeline reference for memory system dev ──
    if _is_memory_system_dev(prompt_lower, state.get("session", {}).get("cwd", "")):
        ref_path = MEMORY_DIR / "_reference" / "internal-pipeline.md"
        if ref_path.exists():
            try:
                ref_text = ref_path.read_text(encoding="utf-8")
                ref_tokens = _estimate_tokens(ref_text)
                jit_budget = min(ref_tokens, 250)
                if jit_budget <= budget:
                    lines.append(
                        f"[JIT:InternalPipeline]\n{truncate_to_tokens(ref_text, jit_budget)}"
                    )
                    budget -= jit_budget
            except (OSError, UnicodeDecodeError):
                pass

    return budget
