"""wg_need_goal_points — 需求目標流程的 4.3 與軌五：讀入範圍變大、被使用者糾正、同檔改多次的提醒，
壓縮後重送與續接單的目標樹，session 結束時記下沒對照的樹。提問閘在 wg_ask_gate。
只透過 wg_need_goal 的公開函式讀寫目標檔（契約第八節）。

三個提醒都不擋：讀入範圍與同檔多次由 PostToolBatch 合併成一則送（batch_lines）；糾正在 UserPromptSubmit 當場送。

樹上 `points`（本模組獨有，契約第十二節）：
  scope_parts      [部位鍵…]             這棵樹開了之後碰過的部位
  scope_dirs       {mark, dirs, sent}    樹最後一次更新（mark＝節點 history 最大 seq）之後讀過的頂層目錄
  scope_pending    [{kind, label, prev}] 還沒送出的讀入範圍提示
  scope_sent_turn  int                   最近一次送讀入範圍提示的回合（一回合一則）
  multi_hinted     [路徑…]                已送過「改了好幾次」的檔
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import wg_core
import wg_need_goal as ng

MULTI_EDIT_MIN = 3


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


def _call_parts(c: Any) -> Tuple[str, Any, str]:
    c = c if isinstance(c, dict) else {}
    return (str(c.get("tool_name") or c.get("name") or ""), c.get("tool_input", c.get("input")) or {},
            str(c.get("tool_use_id") or c.get("id") or ""))


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
    """PostToolBatch 要不要跑 batch_lines：讀檔標了待送、同檔改多次到門檻、這批有外部主張（不讀目標檔）。"""
    return bool(state.get("need_goal_batch")) or multi_edit_due(state) or bool(claim_calls(tool_calls))


def batch_lines(sid: Any, state: Dict[str, Any], tool_calls: Any, cfg: Dict[str, Any]) -> List[str]:
    """PostToolBatch：讀入範圍待送的合併成一則（一回合最多一則，留下的下一回合第一批送）、同檔改多次提醒、外部主張。"""
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
