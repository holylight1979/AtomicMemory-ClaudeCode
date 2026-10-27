"""wg_need_goal_points — 需求目標流程的 4.3、4.4 與軌五：讀入範圍變大、被使用者糾正、同檔改多次的提醒，
問使用者之前要掛節點，壓縮後重送與續接單的目標樹，session 結束時記下沒對照的樹。
只透過 wg_need_goal 的公開函式讀寫目標檔（契約第八節）。

三個提醒都不擋：讀入範圍與同檔多次由 PostToolBatch 合併成一則送（batch_lines）；糾正在 UserPromptSubmit 當場送。
提問（AskUserQuestion／ExitPlanMode）兩種模式，看 settings.json 的 PreToolUse matcher 有沒有掛這兩個工具：
  擋：PreToolUse 呼叫 on_ask，寫碼類沒掛節點就 deny；處理過的提問記進 state["need_goal_asks"]。
  事後記錄＋提醒：PreToolUse 沒掛（或沒觸發）時，PostToolBatch 從 tool_calls 找出沒處理過的提問，照同一套判斷記錄並提醒。

樹上 `points`（本模組獨有，契約第十二節）：
  scope_parts      [部位鍵…]             這棵樹開了之後碰過的部位
  scope_dirs       {mark, dirs, sent}    樹最後一次更新（mark＝節點 history 最大 seq）之後讀過的頂層目錄
  scope_pending    [{kind, label, prev}] 還沒送出的讀入範圍提示
  scope_sent_turn  int                   最近一次送讀入範圍提示的回合（一回合一則）
  multi_hinted     [路徑…]                已送過「改了好幾次」的檔
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import wg_core
import wg_need_goal as ng
import wg_release
import wg_release_rules as rr

ASK_TOOLS = ("AskUserQuestion", "ExitPlanMode")
RELEASE_LABELS = (wg_release.OPT_RELEASE, wg_release.OPT_KEEP)
MULTI_EDIT_MIN = 3
ASK_IDS_MAX = 20
PLAN_CHARS = 50000
_PLAN_FILE_RE = re.compile(r"[\\/]plans[\\/][^\\/]+\.md$", re.IGNORECASE)

NO_TREE_HINT = ("[NeedGoal] 還沒有需求目標樹：這題問完，把使用者的答案寫進 need_goal"
                "（action=set 寫下這個需求真正要達成什麼；純問答可以不寫）。")


# ─── 共用 ────────────────────────────────────────────────────────────────

def _guard(event: str, sid: Any, turn: Optional[int], **kw: Any) -> None:
    wg_core.append_guard_log("need_goal", {"event": event, "session_id": str(sid or "").split("#agent:")[0],
                                           "turn_seq": turn, **kw})


def _warn(where: str, sid: Any, turn: Optional[int], e: Exception) -> None:
    """記錄類失敗（鎖拿不到、目標檔壞了）：stderr 一行＋守門紀錄，不中斷 hook。"""
    print(f"[NeedGoal] {where} 失敗（不擋）：{type(e).__name__}: {e}", file=sys.stderr)
    kind = ("lock_timeout" if isinstance(e, ng.NeedGoalLockTimeout)
            else "corrupt" if isinstance(e, ng.NeedGoalCorrupt) else "points_error")
    _guard(kind, sid, turn, where=where, error=f"{type(e).__name__}: {e}")


def _live(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """目前的樹，結束的不算。"""
    tree = ng.active_tree(doc)
    return tree if tree and tree.get("status") != "closed" else None


def _points(tree: Dict[str, Any]) -> Dict[str, Any]:
    p = tree.setdefault("points", {})
    p.setdefault("scope_parts", [])
    p.setdefault("scope_dirs", {"mark": None, "dirs": [], "sent": False})
    p.setdefault("scope_pending", [])
    p.setdefault("scope_sent_turn", None)
    p.setdefault("multi_hinted", [])
    return p


def _last_update_seq(tree: Dict[str, Any]) -> int:
    """樹最後一次更新：所有節點 history 裡最大的 seq（開樹、增改節點、對照、匯入都會記 history）。
    程式自己記的（by=program：改檔後的進度、代填的對照）不算更新——AI 沒重看目標，跨頂層目錄的計數不歸零。"""
    seqs = [int(h.get("seq") or 0) for n in (tree.get("nodes") or {}).values() if isinstance(n, dict)
            for h in n.get("history") or [] if isinstance(h, dict) and h.get("by") != "program"]
    return max(seqs, default=int(tree.get("created_seq") or 0))


def _label(key: str) -> str:
    """部位鍵（<root>|<部位>）或目錄鍵（<root>|<頂層目錄>）→ 顯示用：根的末段／後半。"""
    root, _, rest = str(key).rpartition("|")
    return f"{Path(root).name}/{rest}" if root else rest


def _load(sid: Any, where: str, turn: Optional[int] = None) -> Optional[Dict[str, Any]]:
    try:
        return ng.load(sid)
    except (ng.NeedGoalCorrupt, OSError) as e:
        _warn(where, sid, turn, e)
        return None


def _update(sid: Any, fn: Any, where: str, turn: Optional[int] = None) -> Any:
    try:
        return ng.update_locked(sid, fn)
    except (ng.NeedGoalLockTimeout, ng.NeedGoalCorrupt, OSError) as e:
        _warn(where, sid, turn, e)
        return None


# ─── 4.3 讀入範圍變大 ─────────────────────────────────────────────────────

# 「用目標視角重看」三個提示（讀入範圍變大、收到外部主張、目標改了）共用的批判與舉一反三兩問（原話輯 G1 2026-10-15）：
# 只送題、不擋，要記下判斷就寫進目標樹（need_goal update 的 why，選填）
CRITIQUE_TWO = "看到的這段寫法（或這個主張）合不合理？不合理就說更好的做法；同類別處還有沒有？"
CRITIQUE_QUESTIONS = CRITIQUE_TWO + ng.CRITIQUE_CASES


def critique_questions(full: bool = True) -> str:
    """兩問＋三種情況：full＝全文（CRITIQUE_QUESTIONS）；送過全文之後（規則 CRITIQUE_CASES_ONCE_PER_SESSION）三種情況換成指回句。"""
    return CRITIQUE_TWO + ng.critique_cases(full)


def _queue_text(items: List[Dict[str, Any]], full: bool = True) -> str:
    labels = [i["label"] for i in items]
    parts = [f"【{_label(i['label'])}】" for i in items if i.get("kind") == "part"]
    dirs = [i for i in items if i.get("kind") == "dirs"]
    prev: List[str] = []
    for i in items:
        if i.get("kind") == "part":
            prev += [p for p in i.get("prev") or [] if p not in prev and p not in labels]
    bits = []
    if parts:
        bits.append("擴到部位" + "".join(parts))
    if dirs:
        d = dirs[-1]["prev"]
        bits.append(f"樹最後一次更新後讀過的檔跨了 {len(d)} 個頂層目錄（{'、'.join(_label(x) for x in d)}）")
    where = f"先前在{''.join(f'【{_label(p)}】' for p in prev[-3:])}的判斷要改觀嗎？" if prev else "先前的判斷要改觀嗎？"
    return (f"[NeedGoal] 讀入範圍變大：{'；'.join(bits)}。目標樹要長新的子目標嗎？{where}{critique_questions(full)}"
            "有改就用 need_goal（add／update）記下並寫為什麼。")


def scope_growth_line(sid: Any, part_label: str, cfg: Dict[str, Any]) -> Optional[str]:
    """讀到某部位（part_label＝部位鍵 <root>|<部位>）：樹開了之後第二個起的每個新部位排進待送，回排進去的那句；
    每棵樹每部位一次。實際由 batch_lines 在 PostToolBatch 合併成一則送出（同一批並行讀檔不各送一則）。"""
    if not cfg.get("enabled", True) or not part_label:
        return None
    doc = _load(sid, "scope_growth_line")
    tree = _live(doc) if doc else None
    if not tree or part_label in _points(tree)["scope_parts"]:
        return None

    def fn(doc: Dict[str, Any]) -> Optional[str]:
        tree = _live(doc)
        if not tree:
            return None
        pts = _points(tree)
        if part_label in pts["scope_parts"]:
            return None
        prev = list(pts["scope_parts"])
        pts["scope_parts"].append(part_label)
        if not prev:
            return None
        item = {"kind": "part", "label": part_label, "prev": prev[-3:]}
        pts["scope_pending"].append(item)
        return _queue_text([item])

    return _update(sid, fn, "scope_growth_line")


def scope_dir_line(sid: Any, dir_label: str, cfg: Dict[str, Any]) -> Optional[str]:
    """讀到某頂層目錄（dir_label＝<root>|<頂層目錄>）：樹最後一次更新之後讀過的頂層目錄達 scope_growth_dirs 個 → 排進待送，
    回排進去的那句；樹再更新（mark 變了）就重新算。"""
    if not cfg.get("enabled", True) or not dir_label:
        return None
    need = int(cfg.get("scope_growth_dirs") or 3)
    doc = _load(sid, "scope_dir_line")
    tree = _live(doc) if doc else None
    if not tree:
        return None
    sd = _points(tree)["scope_dirs"]
    if sd.get("mark") == _last_update_seq(tree) and (dir_label in sd.get("dirs", []) or sd.get("sent")):
        return None

    def fn(doc: Dict[str, Any]) -> Optional[str]:
        tree = _live(doc)
        if not tree:
            return None
        pts = _points(tree)
        mark = _last_update_seq(tree)
        if pts["scope_dirs"].get("mark") != mark:
            pts["scope_dirs"] = {"mark": mark, "dirs": [], "sent": False}
        sd = pts["scope_dirs"]
        if dir_label in sd["dirs"] or sd["sent"]:
            return None
        sd["dirs"].append(dir_label)
        if len(sd["dirs"]) < need:
            return None
        sd["sent"] = True
        item = {"kind": "dirs", "label": dir_label, "prev": list(sd["dirs"])}
        pts["scope_pending"].append(item)
        return _queue_text([item])

    return _update(sid, fn, "scope_dir_line")


def scope_on_read(state: Dict[str, Any], sid: Any, tool_name: str, tool_input: Any, cwd: str,
                  config: Dict[str, Any]) -> bool:
    """PostToolUse（Read／Bash／PowerShell／Grep）：讀到的檔落在哪個部位、哪個頂層目錄，記進目前的目標樹；有新提示排進待送就標
    state["need_goal_batch"]（回 True），由 PostToolBatch 合併送。不看 OverviewHub 開關：關掉時沒有部位，跨頂層目錄照算。
    「讀了什麼」與 OverviewHub 的 on_read 同一支（wg_overview.read_targets：Grep 內容讀檔算、暫存目錄下的檔不算）。
    這個 session 還沒寫過樹就什麼都不做（每次讀檔都走這裡）。"""
    if not ng.goal_path(sid).exists():
        return False
    import wg_overview
    queued = False
    for p in wg_overview.read_targets(tool_name, tool_input, cwd):
        root, part, dir_key = wg_overview.read_scope_keys(p, config)
        cfg = ng.cfg_of(config, root)
        if not dir_key or not cfg.get("enabled", True):
            continue
        hits = [scope_growth_line(sid, part, cfg) if part else None, scope_dir_line(sid, dir_key, cfg)]
        queued = queued or any(hits)
    if queued:
        state["need_goal_batch"] = True
    return queued


# ─── 4.3 收到外部主張（第二意見、審查報告） ─────────────────────────────────

CLAIM_HEAD = ("①這段服務目標樹哪一條？②這個框架是誰給的（使用者原話、審查者）？"
              "③如果照做的成本是零，你會怎麼裁？再兩問：")
CLAIM_QUESTIONS = CLAIM_HEAD + CRITIQUE_QUESTIONS
REPORT_TOOLS = ("mcp__workflow-guardian__second_opinion_result",)
# 讀到審查報告：檔名帶 codex／review／審查／second-opinion 的 .md／.txt
_REPORT_PATH_RE = re.compile(r"(?i)[\\/][^\\/]*(?:codex|review|審查|second[-_]?opinion)[^\\/]*\.(?:md|txt)$")


def claim_calls(tool_calls: Any) -> List[Tuple[str, str]]:
    """這批工具裡的外部主張：審查結果工具、讀審查報告檔。回 [(種類, 來源)]。"""
    out: List[Tuple[str, str]] = []
    for c in tool_calls if isinstance(tool_calls, list) else []:
        name, inp, _tid = _call_parts(c)
        path = str((inp or {}).get("file_path") or "") if isinstance(inp, dict) else ""
        if name in REPORT_TOOLS:
            out.append(("審查報告", name))
        elif name == "Read" and _REPORT_PATH_RE.search(path):
            out.append(("審查報告", Path(path).name))
    return out


def _claim_checkpoint(doc: Dict[str, Any], turn: int) -> None:
    t = _live(doc)
    if t:
        ng.add_checkpoint(doc, t, turn, "scope", t["id"])


def on_external_claim(sid: Any, kind: str, source: str, turn: Optional[int] = None) -> str:
    """收到外部主張、要裁定之前（讀入範圍變大的一種）：送一次「用目標視角重看」三問，有樹附 brief_for、沒樹提醒先回原話
    （沒樹時三種情況照送全文，不為記已送建目標檔）。記 checkpoint scope 與守門紀錄 external_claim。"""
    doc = _load(sid, "on_external_claim", turn)
    tree = _live(doc) if doc else None
    full = ng.critique_once(sid) if tree else True
    head = f"[NeedGoal] 收到外部主張（{kind}：{source}），裁定之前用目標視角重看：{CLAIM_HEAD}{critique_questions(full)}"
    _guard("external_claim", sid, turn, kind=kind, source=source, tree=tree["id"] if tree else None)
    if not tree:
        return head + "（還沒有目標樹：先回到使用者原話，想清楚這件事要達成什麼。）"
    _update(sid, lambda d: _claim_checkpoint(d, int(turn or 0)), "on_external_claim", turn)
    return head + "\n" + ng.brief_for(tree)


def on_correction(sid: Any, hits: List[str], turn: Optional[int] = None) -> Optional[str]:
    """使用者本人打的字命中糾正偵測（wg_friction.record_correction 的回傳）→ 提醒回頭看目標樹，附 brief_for；沒有樹不送。"""
    if not hits:
        return None
    doc = _load(sid, "on_correction", turn)
    tree = ng.active_tree(doc) if doc else None
    if not tree:
        return None

    def fn(doc: Dict[str, Any]) -> None:
        t = ng.active_tree(doc)
        if t:
            ng.add_checkpoint(doc, t, int(turn or 0), "correction", t["id"])

    _update(sid, fn, "on_correction", turn)
    _guard("correction", sid, turn, tree=tree["id"], kw=list(hits)[:3])
    return (f"[NeedGoal] 使用者糾正了（命中：{'、'.join(list(hits)[:3])}）：目標樹哪一條要改？做法還對準嗎？"
            f"糾正是對 {tree['id']} 的修正，改這棵樹、不開新樹（update 改節點、作廢的標放棄；"
            "set 不帶 new_task 改寫樹根；糾正裡多出的要求用 add 長成子目標）。\n" + ng.brief_for(tree))


# ─── 4.4 問使用者之前 ─────────────────────────────────────────────────────

def _strings(x: Any) -> Iterator[str]:
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def _plan_file(tool_input: Any, state: Dict[str, Any]) -> Optional[Path]:
    """ExitPlanMode 的計畫檔：工具輸入裡指到的 .md，否則本 session 最近改過（last_seq 最大）的 plans/*.md。
    modified_files 改到既有的檔只更新 last_seq、不換位置，清單順序不是改檔順序。"""
    for s in _strings(tool_input):
        if len(s) < 400 and s.lower().endswith(".md") and Path(s).is_file():
            return Path(s)
    plans = [m for m in state.get("modified_files") or [] if isinstance(m, dict)
             and _PLAN_FILE_RE.search(str(m.get("path") or "")) and Path(str(m["path"])).is_file()]
    newest = max(plans, key=lambda m: int(m.get("last_seq") or 0), default=None)
    return Path(str(newest["path"])) if newest else None


def ask_text(tool_name: str, tool_input: Any, state: Dict[str, Any]) -> str:
    """提問的全文：工具輸入裡所有字串；ExitPlanMode 另加計畫檔內容（計畫正文可能不在工具輸入裡）。"""
    text = "\n".join(_strings(tool_input))
    if tool_name == "ExitPlanMode":
        pf = _plan_file(tool_input, state)
        if pf:
            try:
                text += "\n" + pf.read_text(encoding="utf-8", errors="replace")[:PLAN_CHARS]
            except OSError:
                pass
    return text


def _node_order(nid: str) -> Tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", nid))


def _node_texts(tree: Dict[str, Any]) -> Dict[str, str]:
    """沒放棄的節點 {編號: 原文}，依編號排（原文片段命中多個時取編號最前的）。"""
    nodes = tree.get("nodes") or {}
    return {nid: str(nodes[nid].get("text") or "") for nid in sorted(nodes, key=_node_order)
            if isinstance(nodes[nid], dict) and nodes[nid].get("status") != "dropped"}


def _linked(tree: Optional[Dict[str, Any]], text: str) -> Optional[str]:
    """一段文字指到的節點：先認編號（wg_need_goal.node_ref），再認原文片段（規則 ASK_LINKED_TO_GOAL）。"""
    return (ng.node_ref(tree, text) or rr.node_fragment_ref(_node_texts(tree), text)) if tree else None


def _links(tree: Optional[Dict[str, Any]], tool_name: str, tool_input: Any, state: Dict[str, Any], pending: bool
           ) -> List[Tuple[str, Optional[str]]]:
    """每個要掛節點的單位 (標籤, 指到的節點或 None)：AskUserQuestion 每一題一個（rr.ask_link_units，不含 header；pending 時
    放行題不算）；ExitPlanMode 或題目判不了 → 整份 ask_text 一個。沒有樹、或真有待放行紀錄而整次全是放行題 → []。"""
    if not tree:
        return []
    if tool_name == "AskUserQuestion":
        if pending and rr.ask_release_only(tool_input, wg_release.RELEASE_TAG, RELEASE_LABELS):
            return []
        units = rr.ask_link_units(tool_input, pending, wg_release.RELEASE_TAG, RELEASE_LABELS)
        if units:
            return [(lab, _linked(tree, text)) for lab, text in units]
    label = "整份計畫" if tool_name == "ExitPlanMode" else "這次提問"
    return [(label, _linked(tree, ask_text(tool_name, tool_input, state)))]


def _all_linked(links: List[Tuple[str, Optional[str]]]) -> Optional[str]:
    """每個單位都指到節點 → 第一個節點；有單位沒指到（或沒有單位）→ None。"""
    return links[0][1] if links and all(n for _l, n in links) else None


def _part_reads(state: Dict[str, Any]) -> int:
    """OverviewHub 各部位（含表外目錄）記下的 part_files_read 總數：規則 ASK_OVERVIEW_BEFORE_DECISION 退回判定的事實。"""
    hub = state.get("overview_hub") if isinstance(state, dict) else None
    return sum(len(r.get("part_files_read") or []) for r in (hub or {}).values() if isinstance(r, dict))


def _named_parts(tool_name: str, tool_input: Any, state: Dict[str, Any]) -> List[Tuple[str, str, int]]:
    """題目提到的路徑（rr.ask_paths；相對路徑照 session cwd 解，沒記就用行程 cwd）經 wg_overview.read_scope_keys 對到部位（跟讀檔紀錄同一套鍵），
    每個部位一筆 (題目裡的寫法, 部位名, 該部位 part_files_read 檔數)：規則 ASK_OVERVIEW_BEFORE_DECISION 的事實。
    只看 AskUserQuestion；對不到部位的路徑不列（規則退回總數判定）。"""
    if tool_name != "AskUserQuestion":
        return []
    import os
    import wg_overview
    cwd = ng.hook_cwd({}, state) or os.getcwd()     # state 沒記 session cwd：hook 行程就開在 session 的 cwd
    hub = state.get("overview_hub") if isinstance(state.get("overview_hub"), dict) else {}
    try:
        config = wg_core.load_config()
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 讀設定失敗，部位對映照預設開關：{type(e).__name__}: {e}", file=sys.stderr)
        config = {}
    out: List[Tuple[str, str, int]] = []
    seen: List[str] = []
    for raw in rr.ask_paths(tool_input):
        p = raw if os.path.isabs(raw) else (os.path.join(cwd, raw) if cwd else "")
        try:   # 這條只是提醒：對映炸了不能讓整個提問被 PreToolUse 外層一律擋，這個路徑當沒對到（規則退回總數判定）
            key = wg_overview.read_scope_keys(os.path.normpath(p), config)[1] if p else None
        except Exception as e:  # noqa: BLE001
            print(f"[NeedGoal] 題目路徑對部位失敗（{raw}，當沒對到）：{type(e).__name__}: {e}", file=sys.stderr)
            key = None
        if not key or key in seen:
            continue
        seen.append(key)
        rec = hub.get(key) if isinstance(hub.get(key), dict) else {}
        out.append((raw, str(rec.get("part") or key.rpartition("|")[2]), len(rec.get("part_files_read") or [])))
    return out


def note_ask_blocked(state: Dict[str, Any], deny: Optional[str]) -> None:
    """PreToolUse 擋了一次提問：累計次數（PostToolBatch 的審計看這個，掛上節點後歸零）。"""
    if deny:
        state["need_goal_ask_blocks"] = int(state.get("need_goal_ask_blocks") or 0) + 1


def _ask_audit(sid: Any, state: Dict[str, Any], tool_calls: Any, turn: int) -> None:
    """PostToolBatch：這批每一次提問記一筆審計（擋過幾次、最後掛上哪個節點、沒掛上的備註）；這題已過得了提問閘
    （附了推薦，而且掛上節點或不是寫碼類）就把擋的次數歸零。"""
    doc = None
    for c in tool_calls if isinstance(tool_calls, list) else []:
        name, inp, tid = _call_parts(c)
        if name not in ASK_TOOLS:
            continue
        doc = doc or _load(sid, "ask_audit", turn)
        tree = _live(doc) if doc else None
        kind = tree.get("kind") if tree else None
        links = _links(tree, name, inp, state, wg_release.pending_any(state, str(sid)))
        release_only = bool(tree) and not links          # 真有待放行紀錄、整次全是放行題：不用掛節點
        linked = _all_linked(links)
        _guard("ask_audit", sid, turn, tool=name, tool_use_id=tid, tree=tree["id"] if tree else None,
               blocked=int(state.get("need_goal_ask_blocks") or 0), linked=linked,
               note=None if release_only else rr.ask_audit_note(kind, linked))
        rec_ok = name != "AskUserQuestion" or not rr.ask_recommendation_verdict(
            inp, wg_release.RELEASE_TAG, RELEASE_LABELS).owed
        if rec_ok and (linked or release_only or kind != "code"):
            state["need_goal_ask_blocks"] = 0


def _ask_checkpoint(doc: Dict[str, Any], turn: int, nid: str) -> None:
    t = _live(doc)
    if t:
        ng.add_checkpoint(doc, t, turn, "ask", nid)


def _judge_ask(sid: Any, tool_name: str, tool_input: Any, state: Dict[str, Any], after: bool
               ) -> Tuple[Optional[str], Optional[str], List[Dict[str, Any]]]:
    """蒐集事實（題目全文、目標樹、部位檔讀了幾個）交 wg_release_rules 的三條提問規則判，組成擋訊息或提示。
    有任何一條要擋（事前模式）→ 所有句子併成一則擋訊息；否則併成一則提示。事後模式只提示。
    第三個回傳值＝提醒件清單（規則名、現象、做法、block＝這條本來是擋）：PreToolUse 拿規則名查 gate_mode 決定照擋還是改提醒
    （規則 GATE_MODE_TABLE）；判定與文字不因送法而變。"""
    turn = int(state.get("turn_seq", 0) or 0)
    mode = "after" if after else "pre"
    pending = wg_release.pending_any(state, str(sid))
    if (tool_name == "AskUserQuestion" and pending
            and rr.ask_release_only(tool_input, wg_release.RELEASE_TAG, RELEASE_LABELS)):
        return None, None, []
    blocks: List[str] = []
    hints: List[str] = []
    hits: List[Dict[str, Any]] = []
    if tool_name == "AskUserQuestion":
        rec = rr.ask_recommendation_verdict(tool_input, wg_release.RELEASE_TAG, RELEASE_LABELS)
        if rec.owed:
            fix = rr.ask_recommendation_fix(tool_input, wg_release.RELEASE_TAG, RELEASE_LABELS)
            blocks.append(f"[NeedGoal] {rr.format_hit('提問', rec)}\n" + fix)
            hits.append({"rule": rec.rule, "what": rec.why, "fix": fix, "block": True})
            _guard("ask_no_recommendation", sid, turn, tool=tool_name, missing=len(rec.evidence), mode=mode)
    view = rr.ask_overview_verdict(tool_name, tool_input, _part_reads(state), _named_parts(tool_name, tool_input, state))
    try:
        doc = ng.load(sid)
    except ng.NeedGoalCorrupt as e:
        _guard("corrupt", sid, turn, where="on_ask", error=str(e))
        blocks.append(f"[NeedGoal] 目標檔壞了，判不了這題掛哪個節點（{e}）：先用 need_goal(action=set, goal=…) 重寫樹根"
                      "（壞檔會自動備份），再問。" + ng.NO_TOOL_HINT)
        hits.append({"rule": "GATE_SELF_ERROR", "what": f"目標檔壞了，判不了這題掛哪個節點（{e}）",
                     "fix": "need_goal(action=set, goal=…) 重寫樹根（壞檔會自動備份）", "block": True})
        doc = None
    tree = _live(doc) if doc else None
    if doc is not None and not tree:
        _guard("ask_hint", sid, turn, tool=tool_name, reason="no_tree", mode=mode)
        hints.append(NO_TREE_HINT)
        hits.append({"rule": "ASK_LINKED_TO_GOAL", "what": "還沒有需求目標樹", "fix": "這題問完把使用者的答案寫進 need_goal(action=set, goal=…)",
                     "block": False})
    links = _links(tree, tool_name, tool_input, state, pending)
    nid = _all_linked(links)
    if tree and nid:
        _update(sid, lambda d: _ask_checkpoint(d, turn, nid), "on_ask", turn)
    elif tree:
        # ASK_LINKED_TO_GOAL 只記錄不擋、不送：掛節點是記帳不是判斷，問句看得懂全貌靠推薦與理由
        link = rr.ask_goal_link_verdict(tree.get("kind"), links)
        _guard("ask_unlinked", sid, turn, tool=tool_name, tree=tree["id"], kind=tree.get("kind"), mode=mode,
               owed=link.owed)
    if view.owed:
        hints.append(f"[NeedGoal] {rr.format_hit('提問', view)}")
        hits.append({"rule": view.rule, "what": view.why, "fix": "先 Read 題目點名的部位的檔再問改法", "block": False})
    if blocks and not after:
        return "\n\n".join(blocks + hints), None, hits
    return None, "\n\n".join(blocks + hints) or None, hits


def on_ask_full(sid: Any, tool_name: str, tool_input: Any, state: Dict[str, Any]
                ) -> Tuple[Optional[str], Optional[str], List[Dict[str, Any]]]:
    """on_ask 加第三個值：提醒件清單（PreToolUse 查 gate_mode 用，見 _judge_ask）。"""
    return _judge_ask(sid, tool_name, tool_input, state, after=False)


def on_ask(sid: Any, tool_name: str, tool_input: Any, state: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """4.4（PreToolUse）：回（擋的理由或 None、提示或 None）。三條規則（wg_release_rules）：
    ASK_NEEDS_RECOMMENDATION 每一題要附推薦（不分有沒有樹）；ASK_LINKED_TO_GOAL 有樹就要指到節點（編號或原文片段），
    寫碼類沒指到擋並列節點、知識類只提示、還沒有樹送「問完把答案寫進 need_goal」；ASK_OVERVIEW_BEFORE_DECISION 問改法而
    還沒讀過部位檔，擋訊息或提示多一句（不單獨擋）。題目含【收尾放行確認】且真有待放行紀錄整題豁免。通過記 checkpoint ask。"""
    return _judge_ask(sid, tool_name, tool_input, state, after=False)[:2]


def ask_key(tool_input: Any) -> str:
    """沒有 tool_use_id 時用工具輸入的雜湊對應同一次提問（PreToolUse 與 PostToolBatch 兩邊都算得出來）。"""
    raw = json.dumps(tool_input, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "h:" + hashlib.sha1(raw).hexdigest()[:12]


def mark_asked(state: Dict[str, Any], tool_use_id: str, tool_input: Any) -> None:
    """記下這次提問已處理過（tool_use_id 與輸入雜湊），PreToolUse 處理過的 PostToolBatch 不再事後處理。"""
    seen = [k for k in state.get("need_goal_asks") or [] if isinstance(k, str)]
    seen += [k for k in (tool_use_id, ask_key(tool_input)) if k and k not in seen]
    state["need_goal_asks"] = seen[-ASK_IDS_MAX:]


def _call_parts(c: Any) -> Tuple[str, Any, str]:
    c = c if isinstance(c, dict) else {}
    return (str(c.get("tool_name") or c.get("name") or ""), c.get("tool_input", c.get("input")) or {},
            str(c.get("tool_use_id") or c.get("id") or ""))


def has_ask_calls(tool_calls: Any) -> bool:
    return any(_call_parts(c)[0] in ASK_TOOLS for c in (tool_calls if isinstance(tool_calls, list) else []))


def asks_after(sid: Any, state: Dict[str, Any], tool_calls: Any) -> List[str]:
    """事後記錄＋提醒（PostToolBatch）：這批裡 PreToolUse 沒處理過的提問，照 on_ask 同一套判斷，只提醒不擋。"""
    out: List[str] = []
    for c in tool_calls if isinstance(tool_calls, list) else []:
        name, inp, tid = _call_parts(c)
        seen = set(state.get("need_goal_asks") or [])
        if name not in ASK_TOOLS or (tid and tid in seen) or ask_key(inp) in seen:
            continue
        mark_asked(state, tid, inp)
        _deny, hint, _hits = _judge_ask(sid, name, inp, state, after=True)
        if hint:
            out.append(hint)
    return out


# ─── PostToolBatch：合併送出 ───────────────────────────────────────────────

def multi_edit_due(state: Dict[str, Any]) -> bool:
    """同檔放行改到第 MULTI_EDIT_MIN 次以上、而且次數比上次檢查時多 → 要去目標檔看一次（省得每批都讀檔）。"""
    checked = state.get("need_goal_multi_checked") or {}
    return any(int(n) >= MULTI_EDIT_MIN and checked.get(p) != n for p, n in (state.get("edit_counts") or {}).items())


def _multi_paths(tree: Dict[str, Any]) -> List[Tuple[str, int, str]]:
    """這棵樹裡改了 MULTI_EDIT_MIN 次以上、還沒提醒過的檔：(路徑, 次數, 最後一次掛的節點)。"""
    counts: Dict[str, List[Dict[str, Any]]] = {}
    for e in tree.get("edits") or []:
        if isinstance(e, dict) and e.get("path"):
            counts.setdefault(str(e["path"]), []).append(e)
    hinted = set(_points(tree)["multi_hinted"])
    return [(p, len(es), str(es[-1].get("node") or tree["id"])) for p, es in counts.items()
            if len(es) >= MULTI_EDIT_MIN and p not in hinted]


def _flush(doc: Dict[str, Any], sid: Any, turn: int) -> Tuple[List[str], bool]:
    """送出待送的讀入範圍（這回合還沒送過才送）與同檔多次提醒；回（要送的句子、還有沒送出的讀入範圍）。"""
    tree = _live(doc)
    if not tree:
        return [], False
    pts = _points(tree)
    out: List[str] = []
    if pts["scope_pending"] and pts["scope_sent_turn"] != turn:
        items = pts["scope_pending"]
        b = ng.brief_mark(doc, tree, turn)                     # 同回合已附過同一份就不重附
        out.append(_queue_text(items, ng.critique_mark(doc)) + (f"\n{b}" if b else ""))
        pts["scope_pending"] = []
        pts["scope_sent_turn"] = turn
        ng.add_checkpoint(doc, tree, turn, "scope", tree["id"])
        _guard("scope", sid, turn, tree=tree["id"], items=[{"kind": i["kind"], "label": i["label"]} for i in items])
    for path, n, node in _multi_paths(tree):
        pts["multi_hinted"].append(path)
        out.append(f"[NeedGoal] 這一處改了好幾次（{Path(path).name} 第 {n} 次，掛在 {node}）：是不是繞路了？"
                   f"回頭看 {node} 的目標還對準嗎。")
        _guard("multi_edit", sid, turn, tree=tree["id"], path=path, edits=n, node=node)
    return out, bool(pts["scope_pending"])


def batch_due(state: Dict[str, Any], tool_calls: Any) -> bool:
    """PostToolBatch 要不要跑 batch_lines：讀檔標了待送、同檔改多次到門檻、這批有提問或外部主張（不讀目標檔）。"""
    return (bool(state.get("need_goal_batch")) or multi_edit_due(state) or has_ask_calls(tool_calls)
            or bool(claim_calls(tool_calls)))


def batch_lines(sid: Any, state: Dict[str, Any], tool_calls: Any, cfg: Dict[str, Any]) -> List[str]:
    """PostToolBatch：讀入範圍待送的合併成一則（一回合最多一則，留下的下一回合第一批送）、同檔改多次提醒、事後的提問提醒。"""
    if not cfg.get("enabled", True):
        return []
    turn = int(state.get("turn_seq", 0) or 0)
    lines: List[str] = []
    scope_due = bool(state.pop("need_goal_batch", None))
    multi_due = multi_edit_due(state)
    if multi_due:
        state["need_goal_multi_checked"] = dict(state.get("edit_counts") or {})
    if scope_due or multi_due:
        doc = _load(sid, "batch_lines", turn)
        tree = _live(doc) if doc else None
        pts = _points(tree) if tree else {}
        left = bool(pts.get("scope_pending"))
        if tree and ((left and pts["scope_sent_turn"] != turn) or _multi_paths(tree)):
            sent, left = _update(sid, lambda d: _flush(d, sid, turn), "batch_lines", turn) or ([], left)
            lines += sent
        if left:
            state["need_goal_batch"] = True   # 這回合送過了：留到下一回合第一批
    if has_ask_calls(tool_calls):
        lines += asks_after(sid, state, tool_calls)
        _ask_audit(sid, state, tool_calls, turn)
    claims = claim_calls(tool_calls)
    if claims:
        kinds = "、".join(dict.fromkeys(k for k, _s in claims))
        lines.append(on_external_claim(sid, kinds, "、".join(s for _k, s in claims), turn))
    return lines


# ─── 4.3 目標改變後導讀卡改用目標視角 ─────────────────────────────────────

def goal_view_text(sid: Any, part: str, knowledge: bool = False, part_key: Optional[str] = None) -> Optional[str]:
    """目標改了之後，已碰過的部位再讀到時，導讀卡前面加的那段：目標視角的提問＋brief_for（part_key＝部位鍵，
    那個部位掛的節點優先當當前節點）；沒有樹回 None。knowledge＝知識類部位（不要求定位行），不叫它重交定位。"""
    doc = _load(sid, "goal_view_text")
    tree = _live(doc) if doc else None
    if not tree:
        return None
    redo = "" if knowledge else "改這裡前要重交定位四行與第五行批判。"
    return (f"[NeedGoal] 目標改了，用目標視角重看【{part}】：這一塊在新目標裡扮演什麼角色？先前在這裡的判斷還成立嗎？"
            f"{critique_questions(ng.critique_once(sid))}{redo}\n" + ng.brief_for(tree, part_key))


# ─── 軌五：壓縮後重送、續接單 ──────────────────────────────────────────────

def recovery_text(sid: Any, config: Dict[str, Any], cwd: str = "") -> str:
    """壓縮後獨立重送的【需求目標樹】（recovery_blob，上限＝兩倍 render_chars）；沒有樹、流程關掉（照 cwd 所在專案的設定）、
    判不了 → ""（判不了寫 stderr）。PostCompact 存、PostToolBatch 送；SessionStart(compact) 當場送。
    壓縮後 context 裡沒有批判題全文了：同時清掉已送紀錄（forget_reminders），下一則提示照送全文。"""
    try:
        cfg = ng.cfg_for_cwd(config, cwd)
        if not cfg.get("enabled", True):
            return ""
        ng.forget_reminders(sid)
        return ng.recovery_blob(sid, 2 * int(cfg.get("render_chars") or 1200))
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 壓縮後目標樹組不出來（不送）：{type(e).__name__}: {e}", file=sys.stderr)
        return ""


def handoff_note(sid: Any, text: str) -> str:
    """續接單裡有【需求目標樹】區塊時，接續指標後面補的那句；沒有區塊回 ""。
    本 session 自己匯出的（壓縮前的自動續接單）→ 樹還在；別的 session 的 → Read 時會自動匯入（wg_need_goal 的匯入）。"""
    if "need-goal:begin" not in (text or ""):
        return ""
    if ng.handoff_session_of(text) == str(sid or "").split("#agent:")[0]:
        return "（裡面的【需求目標樹】是本 session 自己匯出的，樹還在目標檔裡，不用匯入）"
    return ("（裡面有【需求目標樹】：Read 時若還沒有樹會自動匯入並送回眼前；已經有樹就用 "
            "need_goal(action=set, import_from=<這份檔>) 接續）")


def has_open_tree(sid: Any) -> bool:
    """這個 session 還有沒結束的樹（不只看目前的樹）：自動續接單要不要寫的條件之一。判不了 → False（stderr＋守門紀錄）。"""
    doc = _load(sid, "has_open_tree")
    return any(isinstance(t, dict) and t.get("status") != "closed" for t in (doc or {}).get("trees", {}).values())


def handoff_section(sid: Any) -> str:
    """自動續接單的【需求目標樹】區塊（handoff_block）；沒有未結束的樹、或判不了 → ""（判不了寫 stderr）。"""
    try:
        return ng.handoff_block(sid)
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 續接單的目標樹區塊組不出來（不附）：{type(e).__name__}: {e}", file=sys.stderr)
        return ""


# ─── session 結束 ─────────────────────────────────────────────────────────

def silent_unreconciled(sid: Any, turn: Optional[int] = None) -> List[Dict[str, Any]]:
    """session 結束：還沒結束的樹裡，沒有對得上目前目標版本的完整對照、還欠對照的改動、或知識類樹在對照之後又改了檔
    → 每棵一筆守門紀錄（知識類＝有樹沒對照；寫碼類＝一直沒交付）；沒樹時改了記憶知識類的檔（untreed 還在）另記一筆
    「沒樹改了知識類」。不打擾使用者，健檢看得到。回寫了哪幾筆。"""
    doc = _load(sid, "silent_unreconciled", turn)
    out: List[Dict[str, Any]] = []
    for t in (doc or {}).get("trees", {}).values():
        if not isinstance(t, dict) or t.get("status") == "closed":
            continue
        lr = t.get("last_reconcile") or {}
        fresh = ng.reconcile_fresh(t)
        owed = sum(1 for e in t.get("edits") or [] if isinstance(e, dict) and e.get("owed"))
        if fresh and not owed and (t.get("kind") == "code" or not ng._edited_since_reconcile(t)):
            continue
        rec = {"tree": t.get("id"), "kind": t.get("kind"), "status": t.get("status"), "goal_rev": t.get("goal_rev"),
               "reconciled_rev": lr.get("goal_rev"), "owed": owed, "nodes": len(t.get("nodes") or {}),
               "why": "寫碼類一直沒交付完整對照" if t.get("kind") == "code" else "有樹沒對照"}
        _guard("silent_unreconciled", sid, turn, **rec)
        out.append(rec)
    untreed = [e for e in (doc or {}).get("untreed") or [] if isinstance(e, dict)]
    if untreed:
        rec = {"tree": None, "kind": "knowledge", "files": len(untreed) + int((doc or {}).get("untreed_dropped") or 0),
               "paths": [str(e.get("path")) for e in untreed[:5]], "why": "沒樹改了記憶知識類的檔"}
        _guard("silent_unreconciled", sid, turn, **rec)
        out.append(rec)
    return out
