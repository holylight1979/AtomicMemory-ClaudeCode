"""
handlers/post_compact.py — PostCompact hook handler（選配 #4：壓縮後 atom 內文復原 / stash 端）

PostCompact 於壓縮完成後觸發（CC 2.1.159+；payload: trigger∈{manual,auto} + compact_summary）。
反編譯實證：PostCompact **不支援** hookSpecificOutput.additionalContext（無法注入），故本 handler
只負責 **stash**——把壓縮前已注入的 atom 緊湊內文寫進 state + 設 pending_reinjection flag。
實際「一次性重注入」由下一個 PostToolBatch 完成（見 post_tool_batch.py）。

失憶真實缺口僅 = mid-turn auto-compact 丟失的**完整 atom 內文**；atom 索引(MEMORY.md) 經
CLAUDE.md @import 常駐系統提示 + InstructionsLoaded(compact) 重載，壓縮不丟，故不重注入索引。

名單來源 = PreCompact 快照（pre_compact_injected_atoms，免受 SessionStart(compact) 清空順序影響），
fallback 現存 injected_atoms。複用 wg_atoms.load_atoms_within_budget（內走印象式 strip + budget + 緊湊）。
設計：plans/deep-wobbling-bentley.md（Option B）。
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from wg_core import _ensure_state, write_state, output_nothing, _now_iso, MEMORY_DIR
from wg_atoms import load_atoms_within_budget

_DEFAULT_BUDGET = 800   # 印象式重注入 token 預算（緊湊；config: atoms.post_compact_budget）

AtomEntry = Tuple[str, str, List[str]]


def _resolve_injected_entries(
    state: Dict[str, Any], names: List[str],
) -> Tuple[List[AtomEntry], List[AtomEntry], List[str]]:
    """把 atom 名單解析回 (name, rel_path, triggers) entry。

    回 (global_matched, project_matched, unresolved)。rel_path 格式（_atom_index.json 實證）：
    global = 'memory/x.md' / '_AIDocs/Failures/x.md'，相對 MEMORY_DIR.parent（與 build_injection_blob 同基準）。
    """
    idx = state.get("atom_index", {}) or {}
    g = {e[0]: (e[0], e[1], list(e[2])) for e in idx.get("global", []) if e}
    p = {e[0]: (e[0], e[1], list(e[2])) for e in idx.get("project", []) if e}
    gm: List[AtomEntry] = []
    pm: List[AtomEntry] = []
    unresolved: List[str] = []
    for n in names:
        if n in g:
            gm.append(g[n])
        elif n in p:
            pm.append(p[n])
        else:
            unresolved.append(n)
    return gm, pm, unresolved


def handle_post_compact(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    try:
        # 名單：PreCompact 快照優先（免受 SessionStart(compact) 清空順序影響），fallback 現存
        raw = state.get("pre_compact_injected_atoms") or state.get("injected_atoms") or []
        names = list(dict.fromkeys(raw))  # 去重保序
        if not names:
            output_nothing()
            return

        budget = int(config.get("atoms", {}).get("post_compact_budget", _DEFAULT_BUDGET))
        gm, pm, unresolved = _resolve_injected_entries(state, names)

        lines: List[str] = []
        injected: List[str] = []
        if gm:
            gl, gi, used = load_atoms_within_budget(gm, MEMORY_DIR.parent, budget, [])
            lines += gl
            injected += gi
            budget -= used
        if pm and budget > 0:
            proj_mem = state.get("atom_index", {}).get("project_memory_dir", "")
            if proj_mem:
                base_proj = Path(proj_mem).parent
                pl, pi, _u = load_atoms_within_budget(pm, base_proj, budget, [])
                lines += pl
                injected += pi

        if not injected:
            output_nothing()
            return

        trigger = input_data.get("trigger", "")
        header = (
            f"[Atom Recovery] 壓縮（{trigger or '?'}）後復原 {len(injected)} 條長期記憶緊湊內文"
            f"（壓縮前已載入；atom 索引仍常駐系統提示，故僅補內文）："
        )
        state["pending_reinjection"] = True
        state["pending_reinjection_blob"] = header + "\n\n" + "\n\n".join(lines)
        state["pending_reinjection_atoms"] = injected
        state["post_compact_at"] = _now_iso()
        if unresolved:   # no-silent-cap：未解析名單留痕
            state["pending_reinjection_unresolved"] = unresolved
        write_state(session_id, state)
    except Exception as e:
        print(f"[#4] post_compact stash error: {e}", file=sys.stderr)

    # PostCompact 不支援 additionalContext → 不輸出；注入交給下一個 PostToolBatch
    output_nothing()
