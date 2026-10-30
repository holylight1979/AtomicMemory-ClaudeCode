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

需求目標樹：另組一段【需求目標樹】（wg_need_goal_points.recovery_text）存 pending_reinjection_goal，atom 名單空也照存；
PostToolBatch 注入順序 atom 內文先、目標樹後，pending 都一次性 pop。SessionStart(compact) 已當場送過
（need_goal_recovery_sent）就不再存，避免同一次壓縮送兩次。
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import _ensure_state, write_state, output_nothing, _now_iso, MEMORY_DIR, v6_enabled
from wg_atoms import load_atoms_within_budget

_DEFAULT_BUDGET = 800   # 印象式重注入 token 預算（緊湊；config: atoms.post_compact_budget）
_GOAL_SENT_WINDOW_S = 300   # SessionStart(compact) 送過目標樹後多久內的 PostCompact 算同一次壓縮

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


def _atom_blob(state: Dict[str, Any], config: Dict[str, Any], trigger: str) -> Tuple[str, List[str], List[str]]:
    """壓縮前已注入 atom 的緊湊內文 blob。回 (blob, injected, unresolved)；名單空或載不到 → ("", [], [])。"""
    raw = state.get("pre_compact_injected_atoms") or state.get("injected_atoms") or []
    names = list(dict.fromkeys(raw))  # 去重保序
    if not names:
        return "", [], []
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
        return "", [], unresolved
    header = (
        f"[Atom Recovery] 壓縮（{trigger or '?'}）後復原 {len(injected)} 條長期記憶緊湊內文"
        f"（壓縮前已載入；atom 索引仍常駐系統提示，故僅補內文）："
    )
    return header + "\n\n" + "\n\n".join(lines), injected, unresolved


def goal_blob(session_id: str, config: Dict[str, Any], input_data: Optional[Dict[str, Any]] = None,
              state: Optional[Dict[str, Any]] = None) -> str:
    """需求目標樹獨立重送的那段（照這次事件的 cwd 解設定）；模組載不進來 → stderr、不送。"""
    try:
        import wg_need_goal as _ng
        from wg_need_goal_points import recovery_text
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 需求目標模組載入失敗，壓縮後不重送目標樹：{type(e).__name__}: {e}", file=sys.stderr)
        return ""
    return recovery_text(session_id, config, _ng.hook_cwd(input_data, state))


def handle_post_compact(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    try:
        trigger = input_data.get("trigger", "")
        # atom 名單空不 return：需求目標樹照送；兩樣都空才什麼都不留
        atom_blob, injected, unresolved = _atom_blob(state, config, trigger)
        sent_at, goal = None, ""
        if v6_enabled(config):      # 寫碼守門關閉時只復原 atom 內文（9e476fd0 的行為）
            sent_at = state.pop("need_goal_recovery_sent", None)
            goal_sent = isinstance(sent_at, (int, float)) and time.time() - sent_at < _GOAL_SENT_WINDOW_S
            goal = "" if goal_sent else goal_blob(session_id, config, input_data, state)
        if not atom_blob and not goal:
            if sent_at is not None:   # 旗標已 pop，要落盤
                write_state(session_id, state)
            output_nothing()
            return

        state["pending_reinjection"] = True
        if atom_blob:
            state["pending_reinjection_blob"] = atom_blob
            state["pending_reinjection_atoms"] = injected
        if goal:
            state["pending_reinjection_goal"] = goal
        state["post_compact_at"] = _now_iso()
        if unresolved:   # no-silent-cap：未解析名單留痕
            state["pending_reinjection_unresolved"] = unresolved
        write_state(session_id, state)
    except Exception as e:
        print(f"[#4] post_compact stash error: {e}", file=sys.stderr)

    # PostCompact 不支援 additionalContext → 不輸出；注入交給下一個 PostToolBatch
    output_nothing()
