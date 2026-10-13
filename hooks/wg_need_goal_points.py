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

ASK_TOOLS = ("AskUserQuestion", "ExitPlanMode")
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
    """樹最後一次更新：所有節點 history 裡最大的 seq（開樹、增改節點、對照、匯入都會記 history）。"""
    seqs = [int(h.get("seq") or 0) for n in (tree.get("nodes") or {}).values() if isinstance(n, dict)
            for h in n.get("history") or [] if isinstance(h, dict)]
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

def _queue_text(items: List[Dict[str, Any]]) -> str:
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
    return (f"[NeedGoal] 讀入範圍變大：{'；'.join(bits)}。目標樹要長新的子目標嗎？{where}"
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
    """PostToolUse（Read／Bash／PowerShell）：讀到的檔落在哪個部位、哪個頂層目錄，記進目前的目標樹；有新提示排進待送就標
    state["need_goal_batch"]（回 True），由 PostToolBatch 合併送。不看 OverviewHub 開關：關掉時沒有部位，跨頂層目錄照算。
    這個 session 還沒寫過樹就什麼都不做（每次讀檔都走這裡）。"""
    if not ng.goal_path(sid).exists():
        return False
    import wg_overview
    from overview_hub import read_paths_from_tool
    queued = False
    for p in read_paths_from_tool(tool_name, tool_input, cwd):
        root, part, dir_key = wg_overview.read_scope_keys(p, config)
        cfg = ng.cfg_of(config, root)
        if not dir_key or not cfg.get("enabled", True):
            continue
        hits = [scope_growth_line(sid, part, cfg) if part else None, scope_dir_line(sid, dir_key, cfg)]
        queued = queued or any(hits)
    if queued:
        state["need_goal_batch"] = True
    return queued


# ─── 4.3 收到外部主張（同伴訊息、審查報告、交付信） ─────────────────────────

CLAIM_QUESTIONS = ("①這段服務目標樹哪一條？②這個框架是誰給的（使用者原話、同伴、審查者）？"
                   "③如果照做的成本是零，你會怎麼裁？")
REPORT_TOOLS = ("mcp__workflow-guardian__second_opinion_result",)
# 同伴訊息：整則以 <cross-session-message> 開頭；transcript 與畫面上前面多一行 harness 說明，也要認得
_PEER_START_RE = re.compile(r"^\s*(?:Another Claude session sent a message(?: while you were working)?:\s*)?"
                            r"<cross-session-message\b")
_PEER_FROM_RE = re.compile(r'<cross-session-message\b[^>]*?\bfrom-name="([^"]*)"')
# 讀到交付信或審查報告：總控台信箱、檔名帶 codex／review／審查／second-opinion 的 .md／.txt
_REPORT_PATH_RE = re.compile(r"(?i)[\\/]v6-inbox[\\/]|[\\/][^\\/]*(?:codex|review|審查|second[-_]?opinion)[^\\/]*\.(?:md|txt)$")


def peer_of_prompt(prompt: str) -> Optional[str]:
    """這則 prompt 是同伴 session 送來的訊息（開頭就是同伴標籤，可帶 harness 說明行）→ 回發送者名稱（沒有名稱回 ""）；
    不是回 None。使用者打字裡提到這個標籤不算。"""
    text = str(prompt or "")
    if not _PEER_START_RE.match(text):
        return None
    m = _PEER_FROM_RE.search(text, 0, 800)
    return m.group(1) if m else ""


def claim_calls(tool_calls: Any) -> List[Tuple[str, str]]:
    """這批工具裡的外部主張：審查結果工具、讀交付信或審查報告檔。回 [(種類, 來源)]。"""
    out: List[Tuple[str, str]] = []
    for c in tool_calls if isinstance(tool_calls, list) else []:
        name, inp, _tid = _call_parts(c)
        path = str((inp or {}).get("file_path") or "") if isinstance(inp, dict) else ""
        if name in REPORT_TOOLS:
            out.append(("審查報告", name))
        elif name == "Read" and _REPORT_PATH_RE.search(path):
            out.append(("報告或交付信", Path(path).name))
    return out


def _claim_checkpoint(doc: Dict[str, Any], turn: int) -> None:
    t = _live(doc)
    if t:
        ng.add_checkpoint(doc, t, turn, "scope", t["id"])


def on_external_claim(sid: Any, kind: str, source: str, turn: Optional[int] = None) -> str:
    """收到外部主張、要裁定之前（讀入範圍變大的一種）：送一次「用目標視角重看」三問，有樹附樹頭、沒樹提醒先回原話。
    記 checkpoint scope 與守門紀錄 external_claim。"""
    head = f"[NeedGoal] 收到外部主張（{kind}：{source}），裁定之前用目標視角重看：{CLAIM_QUESTIONS}"
    doc = _load(sid, "on_external_claim", turn)
    tree = _live(doc) if doc else None
    _guard("external_claim", sid, turn, kind=kind, source=source, tree=tree["id"] if tree else None)
    if not tree:
        return head + "（還沒有目標樹：先回到使用者原話，想清楚這件事要達成什麼。）"
    _update(sid, lambda d: _claim_checkpoint(d, int(turn or 0)), "on_external_claim", turn)
    return head + "\n" + ng.render(tree, "header")


PEER_SCAN_CAP = 256 * 1024     # 一批最多讀 transcript 新增段的位元組數，超過只取最後一段


def _peer_scan_error(sid: Any, turn: Optional[int], err: str) -> None:
    """掃 transcript 失敗：不擋，stderr 一行，目標檔記 peer_scan_error。"""
    print(f"[NeedGoal] 掃工作中途的同伴訊息失敗（不擋）：{err}", file=sys.stderr)
    _update(sid, lambda d: d.__setitem__("peer_scan_error", {"at": wg_core._now_iso(), "turn": turn, "error": err}),
            "peer_scan_error", turn)


def peer_claim_lines(sid: Any, transcript_path: str, config: Dict[str, Any], turn: Optional[int] = None) -> List[str]:
    """PostToolBatch：工作中途送到的同伴訊息不經任何 hook，只在 transcript 記成 attachment queued_command。
    從目標檔頂層 peer_offset 往後讀新增段（最多 PEER_SCAN_CAP，超過只取最後一段並記 peer_scan_truncated），
    找到同伴訊息就照外部主張送三問。只在本 session 有目標檔時掃；第一次只記位置不回溯；只吃到最後一個完整行。"""
    if not transcript_path or not ng.goal_path(sid).exists() or not ng.cfg_of(config).get("enabled", True):
        return []
    doc = _load(sid, "peer_claim_lines", turn)
    if doc is None:
        return []
    off = doc.get("peer_offset")
    try:
        size = Path(transcript_path).stat().st_size
        if not isinstance(off, int) or off > size:
            _update(sid, lambda d: d.__setitem__("peer_offset", size), "peer_claim_lines", turn)
            return []
        start = max(off, size - PEER_SCAN_CAP)
        with open(transcript_path, "rb") as f:
            f.seek(start)
            raw = f.read(size - start)
    except OSError as e:
        _peer_scan_error(sid, turn, f"{type(e).__name__}: {e}")
        return []
    end = raw.rfind(b"\n") + 1
    chunk = raw[:end]
    if start > off:                                   # 截過：第一行可能只剩半行
        chunk = chunk[chunk.find(b"\n") + 1:]
    names: List[str] = []
    bad = 0
    for line in chunk.splitlines():
        if b"queued_command" not in line or b"cross-session-message" not in line:
            continue
        try:
            o = json.loads(line)
        except ValueError:
            bad += 1
            continue
        att = o.get("attachment") if isinstance(o, dict) else None
        peer = peer_of_prompt(att.get("prompt")) if isinstance(att, dict) and att.get("type") == "queued_command" else None
        if peer is not None:
            names.append(peer or "同伴 session")

    def fn(d: Dict[str, Any]) -> None:
        d["peer_offset"] = start + end
        if start > off:
            d["peer_scan_truncated"] = {"at": wg_core._now_iso(), "turn": turn, "skipped": start - off}

    if end:
        _update(sid, fn, "peer_claim_lines", turn)
    if bad:
        _peer_scan_error(sid, turn, f"{bad} 行同伴訊息 JSON 解析失敗")
    if not names:
        return []
    return [on_external_claim(sid, "同伴訊息（工作中途送到）", "、".join(dict.fromkeys(names)), turn)]


# ─── 4.3 被使用者糾正 ─────────────────────────────────────────────────────

def on_correction(sid: Any, hits: List[str], turn: Optional[int] = None) -> Optional[str]:
    """使用者本人打的字命中糾正偵測（wg_friction.record_correction 的回傳）→ 提醒回頭看目標樹，附目前的樹；沒有樹不送。"""
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
            "有改就用 need_goal（update 改節點、set 改樹根）記下並寫為什麼。\n" + ng.render(tree, "compact"))


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


def _suggest_node(tree: Dict[str, Any]) -> Tuple[str, str]:
    """建議這題掛哪個節點：還沒完成的節點裡編號最前的那個（不含樹根），都完成了就掛樹根。回（編號, 文字）。"""
    nodes = tree.get("nodes") or {}
    open_ids = [n for n in sorted(nodes, key=_node_order) if n != tree["id"]
                and (nodes[n] or {}).get("status") in ("todo", "doing", "partial")]
    nid = open_ids[0] if open_ids else tree["id"]
    return nid, str((nodes.get(nid) or {}).get("text") or "")


def _ask_message(tree: Dict[str, Any], code: bool, after: bool) -> str:
    """擋或提醒的理由：AI 讀得到但不一定自己補（D(1) 實測），所以給照做就能過的修法。"""
    head = ("[NeedGoal] 剛才的提問沒寫掛在目標樹哪個節點（這次提問前沒攔到，事後提醒）" if after else
            "[NeedGoal] 提問前要寫出這題掛在目標樹哪個節點" + ("" if code else "（記憶知識類不擋，只提醒）"))
    nid, text = _suggest_node(tree)
    fix = (f"照做：{'下次提問' if after else '在題目（或計畫）裡'}寫上節點編號再問，例如在題目後面加「（掛 {nid}）」"
           f"；目前最可能的是 {nid}（{text}），換成真正對應的節點也可以。這題不屬於任何節點 → "
           "先用 need_goal(action=add, parent=…) 長出那個節點，再掛上它問。")
    return (f"{head}。{fix}全貌還沒對齊就先補，自己判斷得了的不推給人；問完把答案寫進 need_goal。目前的樹：\n"
            + ng.render(tree, "compact"))


def note_ask_blocked(state: Dict[str, Any], deny: Optional[str]) -> None:
    """PreToolUse 擋了一次提問：累計次數（PostToolBatch 的審計看這個，掛上節點後歸零）。"""
    if deny:
        state["need_goal_ask_blocks"] = int(state.get("need_goal_ask_blocks") or 0) + 1


def _ask_audit(sid: Any, state: Dict[str, Any], tool_calls: Any, turn: int) -> None:
    """PostToolBatch：這批每一次提問記一筆審計（擋過幾次、最後掛上哪個節點）；掛上了就把擋的次數歸零。"""
    doc = None
    for c in tool_calls if isinstance(tool_calls, list) else []:
        name, inp, tid = _call_parts(c)
        if name not in ASK_TOOLS:
            continue
        doc = doc or _load(sid, "ask_audit", turn)
        tree = _live(doc) if doc else None
        linked = ng.node_ref(tree, ask_text(name, inp, state)) if tree else None
        _guard("ask_audit", sid, turn, tool=name, tool_use_id=tid, tree=tree["id"] if tree else None,
               blocked=int(state.get("need_goal_ask_blocks") or 0), linked=linked)
        if linked:
            state["need_goal_ask_blocks"] = 0


def _ask_checkpoint(doc: Dict[str, Any], turn: int, nid: str) -> None:
    t = _live(doc)
    if t:
        ng.add_checkpoint(doc, t, turn, "ask", nid)


def _judge_ask(sid: Any, tool_name: str, tool_input: Any, state: Dict[str, Any], after: bool
               ) -> Tuple[Optional[str], Optional[str]]:
    turn = int(state.get("turn_seq", 0) or 0)
    text = ask_text(tool_name, tool_input, state)
    if wg_release.RELEASE_TAG in text and wg_release.pending_any(state, str(sid)):
        return None, None
    try:
        doc = ng.load(sid)
    except ng.NeedGoalCorrupt as e:
        _guard("corrupt", sid, turn, where="on_ask", error=str(e))
        msg = (f"[NeedGoal] 目標檔壞了，判不了這題掛哪個節點（{e}）：先用 need_goal(action=set, goal=…) 重寫樹根"
               "（壞檔會自動備份），再問。")
        return (None, msg) if after else (msg, None)
    tree = _live(doc)
    if not tree:
        _guard("ask_hint", sid, turn, tool=tool_name, reason="no_tree", mode="after" if after else "pre")
        return None, NO_TREE_HINT
    nid = ng.node_ref(tree, text)
    if nid:
        _update(sid, lambda d: _ask_checkpoint(d, turn, nid), "on_ask", turn)
        return None, None
    code = tree.get("kind") == "code"
    msg = _ask_message(tree, code, after)
    if code and not after:
        _guard("ask_blocked", sid, turn, tool=tool_name, tree=tree["id"])
        return msg, None
    _guard("ask_hint", sid, turn, tool=tool_name, tree=tree["id"], kind=tree.get("kind"), mode="after" if after else "pre")
    return None, msg


def on_ask(sid: Any, tool_name: str, tool_input: Any, state: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """4.4（PreToolUse）：回（擋的理由或 None、提示或 None）。有樹就要題目裡掛節點編號：寫碼類沒掛擋並列節點，
    知識類只提示；豁免①題目含【收尾放行確認】且真有待放行紀錄 ②還沒有樹（改送「問完把答案寫進 need_goal」）。
    通過記 checkpoint ask。"""
    return _judge_ask(sid, tool_name, tool_input, state, after=False)


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
        _deny, hint = _judge_ask(sid, name, inp, state, after=True)
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
        out.append(_queue_text(items) + "\n" + ng.render(tree, "header"))
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

def goal_view_text(sid: Any, part: str) -> Optional[str]:
    """目標改了之後，已碰過的部位再讀到時，導讀卡前面加的那段：目標視角的提問＋目前的樹；沒有樹回 None。"""
    doc = _load(sid, "goal_view_text")
    tree = _live(doc) if doc else None
    if not tree:
        return None
    return (f"[NeedGoal] 目標改了，用目標視角重看【{part}】：這一塊在新目標裡扮演什麼角色？先前在這裡的判斷還成立嗎？"
            "改這裡前要重交定位四行。\n" + ng.render(tree, "compact"))


# ─── 軌五：壓縮後重送、續接單 ──────────────────────────────────────────────

def recovery_text(sid: Any, config: Dict[str, Any]) -> str:
    """壓縮後獨立重送的【需求目標樹】（recovery_blob，上限＝兩倍 render_chars）；沒有樹、流程關掉、判不了 → ""
    （判不了寫 stderr）。PostCompact 存、PostToolBatch 送；SessionStart(compact) 當場送。"""
    try:
        cfg = ng.cfg_of(config)
        if not cfg.get("enabled", True):
            return ""
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
    """session 結束：還沒結束的樹裡，沒有對得上目前目標版本的完整對照、或還欠對照的改動 → 每棵一筆守門紀錄
    （知識類＝有樹沒對照；寫碼類＝一直沒交付）。不打擾使用者，健檢看得到。回寫了哪幾筆。"""
    doc = _load(sid, "silent_unreconciled", turn)
    out: List[Dict[str, Any]] = []
    for t in (doc or {}).get("trees", {}).values():
        if not isinstance(t, dict) or t.get("status") == "closed":
            continue
        lr = t.get("last_reconcile") or {}
        fresh = bool(lr) and lr.get("goal_rev") == t.get("goal_rev")
        owed = sum(1 for e in t.get("edits") or [] if isinstance(e, dict) and e.get("owed"))
        if fresh and not owed:
            continue
        rec = {"tree": t.get("id"), "kind": t.get("kind"), "status": t.get("status"), "goal_rev": t.get("goal_rev"),
               "reconciled_rev": lr.get("goal_rev"), "owed": owed, "nodes": len(t.get("nodes") or {}),
               "why": "寫碼類一直沒交付完整對照" if t.get("kind") == "code" else "有樹沒對照"}
        _guard("silent_unreconciled", sid, turn, **rec)
        out.append(rec)
    return out
