"""
handlers/post_compact.py — PostCompact hook handler（壓縮後把卡片內文送回去：組卡函式＋補位暫存）

壓縮的事件順序：PreCompact（快照壓縮前已注入的卡名 pre_compact_injected_atoms）→ SessionStart(source=compact)
→ PostCompact（輸入帶 trigger∈{manual,auto} 與 compact_summary）。
主路：SessionStart(compact) 用本檔的 recovery_blob 組緊湊內文、以 additionalContext 直接送出，並記
compact_reinjected_at（規則 COMPACT_REINJECT_AT_SESSION_START）。
補位：PostCompact 沒有輸出可以送進對話（官方 hooks.md 決策控制表：PostCompact「無決定控制，用於副作用」，
不收 additionalContext），所以本 handler 只在沒有 compact_reinjected_at 時把內文暫存進 state、設 pending_reinjection，
由下一個 PostToolBatch 一次性送出（見 post_tool_batch.py）。

只補卡片內文：atom 索引（MEMORY.md）經 CLAUDE.md @import 常駐系統提示、壓縮後重載，不重送。
名單來源＝PreCompact 快照，沒有快照才退回 injected_atoms；內文經 wg_atoms.load_atoms_within_budget
（印象式精簡＋預算，config atoms.post_compact_budget，預設 800 tok）。

壓縮摘要填交接單（規則 COMPACT_SUMMARY_TO_HANDOFF）：輸入的 compact_summary 寫進這一輪 PreCompact 剛寫的自動交接單
（next-phase-auto.md）的「壓縮前脈絡」段，見 fill_handoff_summary。
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from wg_core import _ensure_state, write_state, output_nothing, _now_iso, MEMORY_DIR
from wg_atoms import load_atoms_within_budget

_DEFAULT_BUDGET = 800   # 印象式重注入 token 預算（緊湊；config: atoms.post_compact_budget）
_SUMMARY_BEGIN = "<!-- compact-summary:begin -->"   # 交接單裡壓縮摘要那段的頭尾記號：只換記號之間，其他內容不動
_SUMMARY_END = "<!-- compact-summary:end -->"
_SUMMARY_ANCHOR = "## 1.【前置脈絡】"   # 摘要段插在這個標題前；找不到就接在檔尾

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


def recovery_blob(state: Dict[str, Any], config: Dict[str, Any], trigger: str = "") -> Tuple[str, List[str], List[str]]:
    """壓縮前已注入卡的緊湊內文（SessionStart(compact) 主路與本檔補位共用）。卡路徑照 state 的 atom_index 解析。
    回 (內文, 送出的卡名, 索引查不到的卡名)；名單空或載不到 → ("", [], 查不到的)。"""
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
    when = f"壓縮（{trigger}）後" if trigger else "壓縮後"
    header = (
        f"[Atom Recovery] {when}復原 {len(injected)} 條長期記憶緊湊內文"
        f"（壓縮前已載入；atom 索引仍常駐系統提示，故僅補內文）："
    )
    return header + "\n\n" + "\n\n".join(lines), injected, unresolved


def fill_handoff_summary(state: Dict[str, Any], summary: str, trigger: str = "") -> str:
    """規則 COMPACT_SUMMARY_TO_HANDOFF：壓縮摘要寫進這一輪 PreCompact 剛寫的自動交接單（handoff_stub_at 不早於
    pre_compact_snapshot）。只寫記號之間那段：已有就換新、沒有就插在「前置脈絡」標題前，檔裡其他內容原樣。
    這一輪沒寫自動交接單（沒改檔、或有新鮮的手寫交接單）就不寫：手寫的可能是別的 session 的，自動交接單的修改時間
    一動也會把開場「先讀最新交接檔」的指標搶過來。回寫入的檔路徑，沒寫回空字串。"""
    summary = (summary or "").strip()
    stub = state.get("handoff_stub_path") or ""
    stub_at = state.get("handoff_stub_at") or ""
    snap = state.get("pre_compact_snapshot") or ""
    if not summary or not stub or not snap or stub_at < snap:
        return ""
    path = Path(stub)
    if not path.is_file():
        return ""
    how = f"（{trigger}）" if trigger else ""
    block = (
        f"{_SUMMARY_BEGIN}\n"
        "## 0.【壓縮前脈絡】（壓縮摘要原文）\n"
        f"> 來源：PostCompact 的 compact_summary{how}，{_now_iso()}。壓縮時模型寫的對話摘要，屬推論；"
        "動工前對照檔案與 git 核實。\n\n"
        f"{summary}\n"
        f"{_SUMMARY_END}\n"
    )
    text = path.read_text(encoding="utf-8")
    b, e = text.find(_SUMMARY_BEGIN), text.find(_SUMMARY_END)
    if b >= 0 and e > b:
        tail = text[e + len(_SUMMARY_END):]
        text = text[:b] + block + (tail[1:] if tail.startswith("\n") else tail)
    elif _SUMMARY_ANCHOR in text:
        i = text.index(_SUMMARY_ANCHOR)
        text = text[:i] + block + "\n" + text[i:]
    else:
        text = text.rstrip("\n") + "\n\n" + block
    path.write_text(text, encoding="utf-8", newline="\n")
    return str(path)


def handle_post_compact(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    try:
        written = fill_handoff_summary(state, input_data.get("compact_summary", ""), input_data.get("trigger", ""))
        if written:
            print(f"[auto-handoff] 壓縮摘要已寫進交接單：{written}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"[auto-handoff] 壓縮摘要沒寫進交接單（交接單照舊只有客觀區塊）：{type(e).__name__}: {e}", file=sys.stderr)

    try:
        if state.get("compact_reinjected_at"):   # 規則 COMPACT_REINJECT_AT_SESSION_START：SessionStart(compact) 已送過這次壓縮的卡
            state["post_compact_at"] = _now_iso()   # 壓縮時間點照記（ups_inject.delivered_forms 用它判「壓縮後送過」）
            write_state(session_id, state)
            output_nothing()
            return

        trigger = input_data.get("trigger", "")
        atom_blob, injected, unresolved = recovery_blob(state, config, trigger)
        if not atom_blob:
            output_nothing()
            return

        state["pending_reinjection"] = True
        state["pending_reinjection_blob"] = atom_blob
        state["pending_reinjection_atoms"] = injected
        state["post_compact_at"] = _now_iso()
        if unresolved:   # no-silent-cap：未解析名單留痕
            state["pending_reinjection_unresolved"] = unresolved
        write_state(session_id, state)
    except Exception as e:
        print(f"[#4] post_compact stash error: {e}", file=sys.stderr)

    # PostCompact 的輸出送不進對話 → 不輸出；暫存的內文交給下一個 PostToolBatch
    output_nothing()
