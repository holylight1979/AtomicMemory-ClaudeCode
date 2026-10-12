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

A2.2 OverviewHub 綜觀：PreCompact 另快照 pre_compact_overview_hub／pre_compact_turn_intent；這裡每部位組一段
（主目標／部位／層／卡路徑／病灶前 N／定位三行已交否，各截 overview_hub.post_compact_chars）存 pending_reinjection_overview，
atom 名單空也照存；PostToolBatch 注入順序 atom 內文先、綜觀後，兩個 pending 都一次性 pop。
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


def _overview_blob(state: Dict[str, Any], config: Dict[str, Any], trigger: str) -> Tuple[str, List[str]]:
    """A2.2：壓縮前已注入的每個部位各組一段「主目標／部位／層／卡路徑／病灶前 N／定位三行已交否」，各截 post_compact_chars；
    名單來源 PreCompact 快照（pre_compact_overview_hub），fallback 現存 overview_hub。順帶把現存 rec 標 reinjected_after_compact=True
    （只設不清）。回 (blob, 部位名清單)；沒有已注入部位 → ("", [])。"""
    from wg_overview import _cfg, defects_top_n
    summary = state.get("pre_compact_overview_hub") or {
        k: v for k, v in (state.get("overview_hub") or {}).items() if "(unmapped)" not in k
    }
    intent = state.get("pre_compact_turn_intent") or state.get("turn_intent") or "general"
    blobs: List[str] = []
    parts: List[str] = []
    for key, rec in summary.items():
        if not isinstance(rec, dict) or "(unmapped)" in key:
            continue
        part = rec.get("part") or key.split("|", 1)[-1]
        root = Path(rec["root"]) if rec.get("root") else None
        cfg = _cfg(config, root)
        limit = int(cfg.get("post_compact_chars") or 1500)
        rec_intent = rec.get("intent") or intent
        gw = (cfg.get("goal_weights") or {}).get(rec_intent) or {}
        goal = rec_intent + (f"（視角：{gw.get('lens') or '無'}；先問：{gw.get('ask_first') or '無'}）" if gw.get("lens") or gw.get("ask_first") else "")
        cards = [str(c) for c in (rec.get("card_paths") or [])]
        defects = defects_top_n(cards, int(cfg.get("candidate_top_n") or 5))
        edited = rec.get("edited_files") or {}
        # 短欄在前（部位／層／三行已交否），長的（主目標說明、卡路徑、病灶、同檔多次清單）在後，截斷只切到尾巴
        lines = [
            f"【{part}】層：{rec.get('layer') or '單層'}｜定位三行：{'已交' if rec.get('located') else '未交'}"
            f"（本 session 改過 {int(rec.get('edits') or 0)} 次）",
            f"  主目標：{goal}｜專案根：{root or '?'}",
            f"  卡路徑：{'；'.join(cards) or '無'}",
        ]
        multi = [p for p, n in edited.items() if int(n) >= 2]
        if multi:
            lines.append("  同檔多次：" + "、".join(multi))
        if defects:
            lines.append("  病灶前 N：\n" + "\n".join(f"    {d}" for d in defects))
        blob = "\n".join(lines)
        if len(blob) > limit:
            blob = blob[:limit] + f"\n  …（超過 post_compact_chars={limit} 截斷）"
        blobs.append(blob)
        parts.append(part)
        live = (state.get("overview_hub") or {}).get(key)
        if isinstance(live, dict):
            live["reinjected_after_compact"] = True
    if not blobs:
        return "", []
    header = (f"[Overview Recovery] 壓縮（{trigger or '?'}）後重注本 session 已碰過的 {len(blobs)} 個部位綜觀"
              f"（壓縮前意圖：{intent}；每部位主目標／層／卡／病灶／定位三行已交否；atom 內文在前、綜觀在後）：")
    return header + "\n\n" + "\n\n".join(blobs), parts


def handle_post_compact(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    try:
        trigger = input_data.get("trigger", "")
        # atom 名單空不 return（A2.2）：只注入過導讀卡的 session 也要 stash 綜觀；兩邊都空才什麼都不留
        atom_blob, injected, unresolved = _atom_blob(state, config, trigger)
        overview_blob, parts = _overview_blob(state, config, trigger)
        if not atom_blob and not overview_blob:
            output_nothing()
            return

        state["pending_reinjection"] = True
        if atom_blob:
            state["pending_reinjection_blob"] = atom_blob
            state["pending_reinjection_atoms"] = injected
        if overview_blob:
            state["pending_reinjection_overview"] = overview_blob
            state["pending_reinjection_parts"] = parts
        state["post_compact_at"] = _now_iso()
        if unresolved:   # no-silent-cap：未解析名單留痕
            state["pending_reinjection_unresolved"] = unresolved
        write_state(session_id, state)
    except Exception as e:
        print(f"[#4] post_compact stash error: {e}", file=sys.stderr)

    # PostCompact 不支援 additionalContext → 不輸出；注入交給下一個 PostToolBatch
    output_nothing()
