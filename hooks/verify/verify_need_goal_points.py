"""verify_need_goal_points.py — 需求目標流程 4.3、4.4、軌五（hooks/wg_need_goal_points.py 與各 hook 的呼叫點）。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_need_goal_points.py
  目標檔模組 hooks/wg_need_goal.py（track-b2）在本樹就用真的；不在就用本檔照契約第八節簽名寫的替身。
  NEED_GOAL_REAL=<某個 wg_need_goal.py 的路徑> 可指定拿那一份真模組來跑（合併前先對 b2 工作樹接一次）。

守住：
  4.3 讀入範圍：樹開了之後第二個起的新部位、樹更新後跨 3 個頂層目錄各排一次；PostToolBatch 合併成一則、一回合一則；
      同檔放行改 3 次以上提醒一次；糾正命中且有樹才送；目標改變後導讀卡用目標視角重送一次、不重置讀檔紀錄。
  4.4 提問：寫碼類沒掛節點擋並列節點、掛了放行記 checkpoint、知識類只提示、沒樹送「問完寫進 need_goal」、
      【收尾放行確認】要對得上真的待放行紀錄、ExitPlanMode 讀計畫檔；PreToolUse 處理過的 PostToolBatch 不再處理，
      沒處理過的事後提醒（不擋）。
  軌五：壓縮後沒有部位也重送目標樹、綜觀的主目標指向它、SessionStart(compact) 送過就不再存；自動續接單帶區塊；
      續接指標分自己匯出與別人匯出；session 結束記沒對照的樹。
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import os
import re
import sys
import time
import types
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_core  # noqa: E402


# ─── 目標檔模組：真的或替身 ─────────────────────────────────────────────

def _fake_need_goal() -> types.ModuleType:
    """契約第八節的簽名、第二節的格式；只做本檔用得到的行為。"""
    m = types.ModuleType("wg_need_goal")

    class NeedGoalLockTimeout(RuntimeError):
        pass

    class NeedGoalCorrupt(ValueError):
        pass

    def goal_path(sid):
        return Path(wg_core.WORKFLOW_DIR) / "need-goal" / f"{str(sid).split('#agent:')[0]}.json"

    def _skeleton(sid):
        return {"version": 1, "session_id": str(sid), "seq": 0, "next_tree": 1, "active": None, "cwd": "",
                "user_msgs": 0, "said_log": [], "hint_sent": {"first": False, "after": []}, "trees": {},
                "receipts": [], "imports": []}

    def load(sid):
        p = goal_path(sid)
        if not p.exists():
            return _skeleton(sid)
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            raise NeedGoalCorrupt(str(e))

    def update_locked(sid, fn):
        try:
            doc = load(sid)
        except NeedGoalCorrupt:
            doc = _skeleton(sid)
        res = fn(doc)
        p = goal_path(sid)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return res

    def next_seq(doc):
        doc["seq"] = int(doc.get("seq") or 0) + 1
        return doc["seq"]

    def active_tree(doc):
        return (doc.get("trees") or {}).get(doc.get("active") or "")

    def cfg_of(config, root=None):
        return {"enabled": True, "scope_growth_dirs": 3, "render_chars": 1200,
                **(((config or {}).get("overview_hub") or {}).get("need_goal") or {})}

    def render(tree, form, chars=None, doc=None):
        if not tree:
            return ""
        root = tree["nodes"][tree["id"]]["text"]
        if form == "header":
            return f"{tree['id']}：{root}"
        return "\n".join(f"{nid} [{n['status']}] {n['text']}" for nid, n in sorted(tree["nodes"].items()))

    def node_ref(tree, text):
        for mm in re.finditer(r"(?<![A-Za-z0-9_])T\d+(?:\.\d+)*", str(text or "")):
            n = (tree.get("nodes") or {}).get(mm.group(0))
            if n and n.get("status") != "dropped":
                return mm.group(0)
        return None

    def add_checkpoint(doc, tree, turn, point, node):
        tree.setdefault("checkpoints", []).append({"seq": next_seq(doc), "turn": turn, "point": point, "node": node})
        tree["checkpoints"] = tree["checkpoints"][-200:]

    def handoff_block(sid):
        doc = load(sid)
        live = [t for t in doc["trees"].values() if t.get("status") != "closed"]
        if not live:
            return ""
        data = {"version": 1, "session_id": str(sid), "active": doc.get("active"), "trees": live}
        return ("## 【需求目標樹】\n\n<!-- need-goal:begin v1 -->\n```json\n" + json.dumps(data, ensure_ascii=False)
                + "\n```\n<!-- need-goal:end -->")

    def handoff_session_of(text):
        blocks = re.findall(r"<!--\s*need-goal:begin[^>]*-->\s*```json\s*(.*?)\s*```", text or "", re.S)
        try:
            return json.loads(blocks[-1]).get("session_id") if blocks else None
        except ValueError:
            return None

    def recovery_blob(sid, limit):
        tree = active_tree(load(sid))
        if not tree:
            return ""
        return ("【需求目標樹】（壓縮後重送）\n" + render(tree, "compact"))[:limit]

    for f in (NeedGoalLockTimeout, NeedGoalCorrupt, goal_path, load, update_locked, next_seq, active_tree, cfg_of,
              render, node_ref, add_checkpoint, handoff_block, handoff_session_of, recovery_blob):
        setattr(m, f.__name__, f)
    return m


def _install_need_goal() -> str:
    real = os.environ.get("NEED_GOAL_REAL")
    if real:
        spec = importlib.util.spec_from_file_location("wg_need_goal", real)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["wg_need_goal"] = mod
        spec.loader.exec_module(mod)
        return f"real:{real}"
    if (HOOKS_DIR / "wg_need_goal.py").exists():
        import wg_need_goal  # noqa: F401
        return "real:hooks/wg_need_goal.py"
    sys.modules["wg_need_goal"] = _fake_need_goal()
    return "fake"


NG_SOURCE = _install_need_goal()
import wg_need_goal as ng  # noqa: E402
import wg_need_goal_points as ngp  # noqa: E402
import wg_overview as wo  # noqa: E402
import wg_release  # noqa: E402
from handlers import post_compact as pc  # noqa: E402
from handlers import post_tool_batch as ptb  # noqa: E402
from handlers import pre_tool_use as ptu  # noqa: E402
from handlers import session_start as ss  # noqa: E402
import wg_handoff  # noqa: E402

SID = "sid-points-0001"
CFG = {"enabled": True, "scope_growth_dirs": 3, "render_chars": 1200}


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    """資料根與守門紀錄都進 tmp：目標檔在 tmp/workflow/need-goal，守門紀錄在 tmp/Logs。"""
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path / "workflow")
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path / "Logs")
    (tmp_path / "workflow").mkdir()
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    return tmp_path


def guard(tmp_path):
    p = tmp_path / "Logs" / "guard-need_goal.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def make_tree(kind="code", children=(".1", ".2"), status="doing", sid=SID):
    """照契約第二節直接寫一棵樹（不經 apply_op，只靠 update_locked／next_seq）。回樹號。"""
    def fn(doc):
        seq = ng.next_seq(doc)
        tid = f"T{int(doc.get('next_tree') or 1)}"
        doc["next_tree"] = int(doc.get("next_tree") or 1) + 1

        def node(parent, text, st):
            return {"parent": parent, "text": text, "origin": "user" if parent is None else "inferred",
                    "clarity": "clear", "status": st, "history": [{"seq": seq, "turn": 1, "what": "create", "why": ""}],
                    "evidence": [], "followup": "", "note": ""}
        nodes = {tid: node(None, "把目標送回眼前", "doing")}
        for c in children:
            nodes[tid + c] = node(tid, f"子目標{c}", "todo")
        doc["trees"][tid] = {"id": tid, "status": status, "kind": kind, "goal_rev": 1, "created_turn": 1,
                             "created_seq": seq, "user_said": [{"seq": seq, "turn": 1, "text": "使用者原話"}],
                             "peer_said": [], "links": {"parts": {}}, "edits": [], "last_reconcile": None,
                             "goal_changed": {"seq": seq, "turn": 1}, "imported_from": None, "checkpoints": [],
                             "nodes": nodes}
        doc["active"] = tid
        return tid
    return ng.update_locked(sid, fn)


def tree_now(sid=SID):
    return ng.active_tree(ng.load(sid))


def bump_tree(sid=SID):
    """樹更新一次（節點 history 多一筆更大的 seq）。"""
    def fn(doc):
        t = ng.active_tree(doc)
        t["nodes"][t["id"]]["history"].append({"seq": ng.next_seq(doc), "turn": 2, "what": "text", "why": "改"})
    ng.update_locked(SID, fn)


def add_edits(path, n, node=None, sid=SID):
    def fn(doc):
        t = ng.active_tree(doc)
        for _ in range(n):
            t["edits"].append({"seq": ng.next_seq(doc), "turn": 1, "path": path, "node": node or t["id"],
                               "agent_id": "", "code": True, "owed": True})
    ng.update_locked(sid, fn)


def run_handler(fn, *args):
    """hook 入口會 sys.exit；抓 stdout 的 JSON（沒輸出回 None）。"""
    import io
    buf, old = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        fn(*args)
    except SystemExit:
        pass
    finally:
        sys.stdout = old
    out = buf.getvalue().strip()
    return json.loads(out) if out else None


# ─── 4.3 讀入範圍 ─────────────────────────────────────────────────────────

def test_scope_first_part_silent_then_each_new_part_once():
    make_tree()
    assert ngp.scope_growth_line(SID, "c:/p|戰鬥", CFG) is None              # 第一個部位不提醒
    line = ngp.scope_growth_line(SID, "c:/p|網路", CFG)
    assert line and "【p/網路】" in line and "【p/戰鬥】" in line            # 第二個部位排進待送，帶先前的部位
    assert ngp.scope_growth_line(SID, "c:/p|網路", CFG) is None              # 每棵樹每部位一次
    pts = tree_now()["points"]
    assert pts["scope_parts"] == ["c:/p|戰鬥", "c:/p|網路"] and len(pts["scope_pending"]) == 1


def test_scope_without_tree_records_nothing():
    assert ngp.scope_growth_line(SID, "c:/p|戰鬥", CFG) is None
    assert ngp.scope_dir_line(SID, "c:/p|src", CFG) is None
    assert not ng.goal_path(SID).exists()


def test_scope_dirs_threshold_resets_after_tree_update():
    make_tree()
    assert ngp.scope_dir_line(SID, "c:/p|a", CFG) is None
    assert ngp.scope_dir_line(SID, "c:/p|b", CFG) is None
    line = ngp.scope_dir_line(SID, "c:/p|c", CFG)
    assert line and "跨了 3 個頂層目錄" in line
    assert ngp.scope_dir_line(SID, "c:/p|d", CFG) is None                     # 同一段只排一次
    bump_tree()                                                              # 樹更新 → 重新算
    assert ngp.scope_dir_line(SID, "c:/p|a", CFG) is None
    assert ngp.scope_dir_line(SID, "c:/p|e", CFG) is None
    assert ngp.scope_dir_line(SID, "c:/p|f", CFG)


def test_scope_disabled_does_nothing():
    make_tree()
    off = {**CFG, "enabled": False}
    ngp.scope_growth_line(SID, "c:/p|a", off)
    assert ngp.scope_growth_line(SID, "c:/p|b", off) is None and "points" not in tree_now()


def test_batch_flush_merges_one_message_per_turn(world):
    make_tree()
    for part in ("c:/p|a", "c:/p|b", "c:/p|c"):
        ngp.scope_growth_line(SID, part, CFG)
    state = {"turn_seq": 4, "need_goal_batch": True}
    lines = ngp.batch_lines(SID, state, [], CFG)
    assert len(lines) == 1 and "【p/b】【p/c】" in lines[0] and "【p/a】" in lines[0]   # 合併成一則
    t = tree_now()
    assert t["points"]["scope_pending"] == [] and t["checkpoints"][-1]["point"] == "scope"
    assert [g["event"] for g in guard(world)] == ["scope"]
    ngp.scope_growth_line(SID, "c:/p|d", CFG)                                  # 同回合又來一個 → 這回合不再送
    state["need_goal_batch"] = True
    assert ngp.batch_lines(SID, state, [], CFG) == [] and state["need_goal_batch"] is True
    state["turn_seq"] = 5                                                     # 下一回合第一批送出
    nxt = ngp.batch_lines(SID, state, [], CFG)
    assert len(nxt) == 1 and "【p/d】" in nxt[0]


def test_multi_edit_flush_does_not_resend_scope_same_turn():
    make_tree()
    for part in ("c:/p|a", "c:/p|b"):
        ngp.scope_growth_line(SID, part, CFG)
    state = {"turn_seq": 4, "need_goal_batch": True}
    assert len(ngp.batch_lines(SID, state, [], CFG)) == 1
    ngp.scope_growth_line(SID, "c:/p|c", CFG)                                   # 同回合又排一個部位
    add_edits("c:/p/x.py", 3)                                                 # 同時同檔改到第三次 → 這批要讀目標檔
    state.update(need_goal_batch=True, edit_counts={"c:/p/x.py": 3})
    lines = ngp.batch_lines(SID, state, [], CFG)
    assert len(lines) == 1 and "改了好幾次" in lines[0]                       # 只送同檔提醒，讀入範圍留到下一回合
    assert [i["label"] for i in tree_now()["points"]["scope_pending"]] == ["c:/p|c"]
    assert state.get("need_goal_batch") is True                               # 留下的那筆要標著，下一回合才會送（codex P2）
    state["turn_seq"] = 5
    nxt = ngp.batch_lines(SID, state, [], CFG)
    assert len(nxt) == 1 and "【p/c】" in nxt[0]


def test_batch_flush_lock_timeout_keeps_pending_and_logs(world, monkeypatch):
    """送出時鎖拿不到：這批不送、待送旗標留著（下一批再試）、stderr＋守門紀錄 lock_timeout，不讓 hook 炸掉。"""
    make_tree()
    for part in ("c:/p|a", "c:/p|b"):
        ngp.scope_growth_line(SID, part, CFG)

    def busy(sid, fn):
        raise ng.NeedGoalLockTimeout("鎖被別的行程拿著")
    monkeypatch.setattr(ng, "update_locked", busy)
    state = {"turn_seq": 3, "need_goal_batch": True}
    assert ngp.batch_lines(SID, state, [], CFG) == []
    assert state.get("need_goal_batch") is True
    assert guard(world)[-1]["event"] == "lock_timeout" and guard(world)[-1]["where"] == "batch_lines"


def test_multi_edit_hint_once_per_file(world):
    make_tree()
    add_edits("c:/p/x.py", 3, node="T1.1")
    state = {"turn_seq": 2, "edit_counts": {"c:/p/x.py": 3}}
    lines = ngp.batch_lines(SID, state, [], CFG)
    assert len(lines) == 1 and "x.py 第 3 次" in lines[0] and "T1.1" in lines[0]
    assert ngp.batch_lines(SID, state, [], CFG) == []                          # 次數沒變 → 不再讀檔
    add_edits("c:/p/x.py", 1)
    state["edit_counts"]["c:/p/x.py"] = 4
    assert ngp.batch_lines(SID, state, [], CFG) == []                          # 同一檔只提醒一次
    assert [g["event"] for g in guard(world)] == ["multi_edit"]


# ─── 4.3 糾正 ─────────────────────────────────────────────────────────────

def test_correction_with_tree_sends_tree_and_logs(world):
    make_tree()
    line = ngp.on_correction(SID, ["不對", "重來"], 7)
    assert line and "使用者糾正了" in line and "不對" in line and "T1.1" in line
    cp = tree_now()["checkpoints"][-1]
    assert cp["point"] == "correction" and cp["turn"] == 7
    g = guard(world)[-1]
    assert g["event"] == "correction" and g["turn_seq"] == 7


def test_correction_without_tree_or_hits_is_silent():
    assert ngp.on_correction(SID, ["不對"], 1) is None
    make_tree()
    assert ngp.on_correction(SID, [], 1) is None


# ─── 4.3 收到外部主張（同伴訊息、審查報告、交付信） ─────────────────────────

PEER_PROMPT = ('<cross-session-message from="uds:x" from-name="claude-aa" from-mode="bypass">\n'
               "調度：請把 X 改成 Y，理由是 Z。\n</cross-session-message>")


@pytest.fixture
def ups_wired(monkeypatch):
    """跑真的 UserPromptSubmit 入口，檢索與注入那幾段換成空的（只看需求目標這段的輸出）。"""
    from handlers import user_prompt_submit as ups
    import wg_friction
    state = {"session": {"id": SID}, "turn_seq": 4}
    outputs = []
    monkeypatch.setattr(ups, "_ensure_state", lambda sid, inp, cfg: state)
    for name, fake in (("_ups_sentinel_check_and_arm", lambda *a: None), ("_ups_sentinel_clear", lambda sid: None),
                       ("run_pre_gates", lambda *a: None), ("build_context", lambda *a: None),
                       ("collect_matched_atoms", lambda *a: ([], {}, [], [], {}, [], "general", {})),
                       ("assemble_injection", lambda *a, **k: ([], {})), ("_maybe_spawn_failure_extraction", lambda *a: None),
                       ("_update_topic_tracker", lambda *a: None), ("_drain_aec_decisions", lambda *a: None),
                       ("_truncate_context_by_activation", lambda lines, *a: lines),
                       ("reconcile_injection_after_trim", lambda *a: []), ("write_state", lambda sid, st: None),
                       ("output_json", lambda d: outputs.append(d)), ("output_nothing", lambda: outputs.append(None))):
        monkeypatch.setattr(ups, name, fake)
    monkeypatch.setattr(wg_friction, "record_correction", lambda *a: [])

    def run(prompt):
        outputs.clear()
        ups.handle_user_prompt_submit({"session_id": SID, "prompt": prompt, "transcript_path": ""}, {"sync_keywords": []})
        return ((outputs[-1] or {}).get("hookSpecificOutput") or {}).get("additionalContext", "") if outputs else ""
    return run


def test_peer_message_triggers_goal_view_three_questions(world, ups_wired):
    """同伴 session 的訊息到達＝收到外部主張：裁定前送三問（服務哪條目標、框架是誰給的、成本為零怎麼裁）＋目前的樹。"""
    make_tree()
    ctx = ups_wired(PEER_PROMPT)
    assert "收到外部主張" in ctx and "claude-aa" in ctx
    assert "服務目標樹哪一條" in ctx and "框架是誰給的" in ctx and "成本是零" in ctx and "T1" in ctx
    assert tree_now()["checkpoints"][-1]["point"] == "scope" and guard(world)[-1]["event"] == "external_claim"


def test_user_prompt_does_not_trigger_external_claim(world, ups_wired):
    make_tree()
    assert "收到外部主張" not in ups_wired("請把 X 改成 Y")                     # 使用者本人打的字不觸發
    assert not any(g["event"] == "external_claim" for g in guard(world))


def test_user_correction_prompt_is_correction_not_external_claim(world, ups_wired, monkeypatch):
    """使用者本人打的糾正：只送糾正提醒，不當成外部主張（外部主張只認同伴訊息）。"""
    import wg_friction
    make_tree()
    monkeypatch.setattr(wg_friction, "record_correction", lambda *a: ["不對"])
    ctx = ups_wired("不對，請把 X 改成 Y")
    assert "使用者糾正了" in ctx and "收到外部主張" not in ctx


def test_peer_message_without_tree_still_asks(world, ups_wired):
    ctx = ups_wired(PEER_PROMPT)
    assert "收到外部主張" in ctx and "還沒有目標樹" in ctx
    assert ng.active_tree(ng.load(SID)) is None                                # 不替它開樹（b2 的 4.1 會另記同伴轉述）


def test_review_report_and_delivery_letter_in_batch_trigger(world, tmp_path):
    """審查結果（second_opinion_result）與讀交付信／審查報告檔：PostToolBatch 合併送一則三問；讀一般檔不觸發。"""
    make_tree()
    state = {"turn_seq": 5}
    plain = [{"tool_name": "Read", "tool_input": {"file_path": str(tmp_path / "src" / "a.py")}, "tool_use_id": "r1"}]
    assert not ngp.batch_due(state, plain) and ngp.batch_lines(SID, state, plain, CFG) == []
    calls = [{"tool_name": "mcp__workflow-guardian__second_opinion_result", "tool_input": {"job_id": "j1"}, "tool_use_id": "r2"},
             {"tool_name": "Read", "tool_input": {"file_path": "C:/x/workflow/v6-inbox/from-track-a/001-done.md"},
              "tool_use_id": "r3"}]
    assert ngp.batch_due(state, calls)
    lines = ngp.batch_lines(SID, state, calls, CFG)
    assert len(lines) == 1 and "收到外部主張" in lines[0] and "001-done.md" in lines[0] and "審查" in lines[0]


# ─── 4.4 提問 ─────────────────────────────────────────────────────────────

ASK = {"questions": [{"question": "要用哪個做法？", "header": "做法", "multiSelect": False,
                      "options": [{"label": "A", "description": "甲"}, {"label": "B", "description": "乙"}]}]}


def ask_with(text):
    return {"questions": [{**ASK["questions"][0], "question": text}]}


def test_ask_code_tree_unlinked_is_blocked_with_nodes(world):
    make_tree("code")
    deny, hint = ngp.on_ask(SID, "AskUserQuestion", ASK, {"turn_seq": 3})
    assert deny and "掛在目標樹哪個節點" in deny and "T1.1" in deny and hint is None
    assert guard(world)[-1]["event"] == "ask_blocked"


def test_ask_linked_passes_and_records_checkpoint():
    make_tree("code")
    assert ngp.on_ask(SID, "AskUserQuestion", ask_with("T1.2 卡在這：要用哪個？"), {"turn_seq": 3}) == (None, None)
    cp = tree_now()["checkpoints"][-1]
    assert cp == {**cp, "point": "ask", "node": "T1.2", "turn": 3}


def test_ask_dropped_or_foreign_node_does_not_count():
    make_tree("code")
    deny, _ = ngp.on_ask(SID, "AskUserQuestion", ask_with("T9.1 要用哪個？"), {"turn_seq": 1})
    assert deny


def test_ask_knowledge_tree_hints_only(world):
    make_tree("knowledge")
    deny, hint = ngp.on_ask(SID, "AskUserQuestion", ASK, {"turn_seq": 1})
    assert deny is None and hint and "記憶知識類不擋" in hint
    assert guard(world)[-1]["event"] == "ask_hint"


def test_ask_without_tree_or_closed_tree_hints_write_answer(world):
    assert ngp.on_ask(SID, "AskUserQuestion", ASK, {}) == (None, ngp.NO_TREE_HINT)
    make_tree("code", status="closed")
    assert ngp.on_ask(SID, "AskUserQuestion", ASK, {}) == (None, ngp.NO_TREE_HINT)
    assert guard(world)[-1]["reason"] == "no_tree"


def test_release_tag_exempt_only_with_real_pending():
    make_tree("code")
    q = ask_with(f"{wg_release.RELEASE_TAG} 要放行這一回合嗎？")
    deny, _ = ngp.on_ask(SID, "AskUserQuestion", q, {"turn_seq": 2})
    assert deny                                                               # 光加標記不算
    state = {"turn_seq": 2}
    wg_release.mark_block(state, SID, "reconcile", None, 2)
    wg_release.set_pending(state, SID, "reconcile", 2, "now", "擋滿")
    assert ngp.on_ask(SID, "AskUserQuestion", q, state) == (None, None)


def test_release_pending_any_needs_same_gate_block_and_pending():
    """wg_release.pending_any：同一個閘 last_block 與 pending_release 都在才算（on_ask 與壞掉時的放行題共用這一支）。"""
    s = {}
    wg_release.mark_block(s, SID, "reconcile", None, 1)
    assert wg_release.pending_any(s, SID) is False                              # 只擋過、沒擋滿
    s2 = {}
    wg_release.set_pending(s2, SID, "reconcile", 1, "now", "擋滿")
    assert wg_release.pending_any(s2, SID) is False                             # 只有待放行、沒有擋的位置
    wg_release.mark_block(s2, SID, "shared", None, 1)
    assert wg_release.pending_any(s2, SID) is False                             # 不同閘不算
    wg_release.mark_block(s2, SID, "reconcile", None, 1)
    assert wg_release.pending_any(s2, SID) is True and wg_release.pending_any(s2, "別的 session") is False


def test_exit_plan_mode_reads_plan_field_and_plan_file(tmp_path):
    make_tree("code")
    assert ngp.on_ask(SID, "ExitPlanMode", {"plan": "對準 T1.1 的計畫"}, {})[0] is None
    assert ngp.on_ask(SID, "ExitPlanMode", {}, {})[0]                           # 沒有計畫正文 → 擋
    plan = tmp_path / "plans" / "p.md"
    plan.parent.mkdir()
    plan.write_text("# 計畫\n服務 T1.2：先改 A 再改 B", encoding="utf-8")
    assert ngp.on_ask(SID, "ExitPlanMode", {}, {"modified_files": [{"path": str(plan)}]})[0] is None
    assert ngp.on_ask(SID, "ExitPlanMode", {"planFilePath": str(plan)}, {})[0] is None


def test_exit_plan_mode_picks_most_recently_edited_plan(tmp_path):
    """modified_files 改到既有的檔只更新 last_seq、不換位置：要照 last_seq 挑最近改的計畫，不是照清單順序（codex P2）。"""
    make_tree("code")
    a, b = tmp_path / "plans" / "a.md", tmp_path / "plans" / "b.md"
    a.parent.mkdir()
    a.write_text("新計畫：服務 T1.1", encoding="utf-8")
    b.write_text("舊計畫：沒寫節點", encoding="utf-8")
    mods = [{"path": str(a), "last_seq": 9}, {"path": str(b), "last_seq": 4}]   # 先建 A、再建 B、回頭又改 A
    assert ngp.on_ask(SID, "ExitPlanMode", {}, {"modified_files": mods})[0] is None
    mods = [{"path": str(a), "last_seq": 2}, {"path": str(b), "last_seq": 4}]
    assert ngp.on_ask(SID, "ExitPlanMode", {}, {"modified_files": mods})[0]


def test_asks_after_skips_handled_and_hints_unhandled(world):
    make_tree("code")
    state = {"turn_seq": 6}
    ngp.mark_asked(state, "tu1", ASK)
    calls = [{"tool_name": "AskUserQuestion", "tool_input": ASK, "tool_use_id": "tu1"}]
    assert ngp.batch_lines(SID, state, calls, CFG) == []                       # PreToolUse 處理過
    calls2 = [{"tool_name": "AskUserQuestion", "tool_input": ask_with("另一題"), "tool_use_id": "tu2"}]
    lines = ngp.batch_lines(SID, state, calls2, CFG)
    assert len(lines) == 1 and "事後提醒" in lines[0]                          # 沒攔到 → 事後提醒、不擋
    assert guard(world)[-1]["mode"] == "after"
    assert ngp.batch_lines(SID, state, calls2, CFG) == []                      # 同一題不重複提醒


# ─── hook 入口：PreToolUse／PostToolBatch ────────────────────────────────

def _pre_input(tool_input, tid="tu1", tool="AskUserQuestion"):
    return {"session_id": SID, "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
            "tool_use_id": tid, "cwd": str(HOOKS_DIR.parent)}


def test_pre_tool_use_handler_blocks_then_passes_and_marks(world):
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 3})
    make_tree("code")
    out = run_handler(ptu.handle_pre_tool_use, _pre_input(ASK, "tu1"), {})
    assert out, "PreToolUse 沒擋沒掛節點的提問"
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny" and "T1.1" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(ask_with("T1.1：要用哪個？"), "tu2"), {}) is None
    assert {"tu1", "tu2"} <= set(wg_core.read_state(SID)["need_goal_asks"])


def test_pre_tool_use_handler_knowledge_hint_and_subagent_skip(world):
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 1})
    make_tree("knowledge")
    out = run_handler(ptu.handle_pre_tool_use, _pre_input(ASK), {})
    assert out, "知識類提問沒有提示"
    assert "記憶知識類不擋" in out["hookSpecificOutput"]["additionalContext"]
    assert run_handler(ptu.handle_pre_tool_use, {**_pre_input(ASK), "agent_id": "a1"}, {}) is None


def _broken_points(monkeypatch):
    """提問前檢查壞掉：wg_need_goal_points 載不進來（import 時丟 ImportError）。"""
    monkeypatch.setitem(sys.modules, "wg_need_goal_points", None)


def test_pre_tool_use_broken_gate_blocks_normal_question(world, monkeypatch):
    """提問前檢查自己壞了 → 照契約擋（fail-closed）＋stderr＋守門紀錄 ask_error（claude-91 裁定）。"""
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 2})
    _broken_points(monkeypatch)
    out = run_handler(ptu.handle_pre_tool_use, _pre_input(ASK), {})
    assert out, "提問前檢查壞掉時沒擋"
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "提問前檢查壞了" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert guard(world)[-1]["event"] == "ask_error"


def test_pre_tool_use_broken_gate_still_lets_real_release_question_through(world, monkeypatch):
    """壞了也要放過【收尾放行確認】：本 session 真有擋滿待放行紀錄時才放，否則收尾會死鎖；光加標記照擋。"""
    q = ask_with(f"{wg_release.RELEASE_TAG} 要放行這一回合嗎？")
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 2})
    _broken_points(monkeypatch)
    out = run_handler(ptu.handle_pre_tool_use, _pre_input(q), {})
    assert out and out["hookSpecificOutput"]["permissionDecision"] == "deny"     # 沒有待放行紀錄：照擋
    state = {"session": {"id": SID}, "turn_seq": 2}
    wg_release.mark_block(state, SID, "reconcile", None, 2)
    wg_release.set_pending(state, SID, "reconcile", 2, "now", "擋滿")
    wg_core.write_state(SID, state)
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(q, "tu5"), {}) is None


def test_pre_tool_use_disabled_by_config(world):
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 1})
    make_tree("code")
    off = {"overview_hub": {"need_goal": {"enabled": False}}}
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(ASK), off) is None


def test_post_tool_batch_handler_emits_scope_and_after_ask(world):
    make_tree("code")
    ngp.scope_growth_line(SID, "c:/p|a", CFG)
    ngp.scope_growth_line(SID, "c:/p|b", CFG)
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 2, "need_goal_batch": True})
    inp = {"session_id": SID, "hook_event_name": "PostToolBatch",
           "tool_calls": [{"tool_name": "AskUserQuestion", "tool_input": ASK, "tool_use_id": "tu9"}]}
    out = run_handler(ptb.handle_post_tool_batch, inp, {})
    assert out, "PostToolBatch 沒送需求目標提醒"
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "讀入範圍變大" in ctx and "事後提醒" in ctx
    assert "need_goal_batch" not in wg_core.read_state(SID)


def test_post_tool_batch_idle_without_anything(world):
    make_tree("code")
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 2})
    inp = {"session_id": SID, "hook_event_name": "PostToolBatch", "tool_calls": [{"tool_name": "Read", "tool_input": {}}]}
    assert run_handler(ptb.handle_post_tool_batch, inp, {}) is None


# ─── 4.3 on_read 呼叫點：讀入範圍、目標視角重送 ─────────────────────────────

@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "proj"
    (root / ".claude" / "memory" / "shared" / "戰鬥").mkdir(parents=True)
    (root / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
        "| `Game/Battle/` | 戰鬥 | `戰鬥知識導讀-hub索引` | 有 |\n"
        "| `Game/Net/` | 網路 | 無 | 無 |\n", encoding="utf-8")
    (root / ".claude" / "memory" / "shared" / "戰鬥" / "戰鬥知識導讀-hub索引.md").write_text("# 戰鬥導讀\n病灶：共用字典", encoding="utf-8")
    for d in ("Game/Battle", "Game/Net", "Tools", "Docs"):
        (root / d).mkdir(parents=True, exist_ok=True)
    return root


def _tp(tmp_path):
    tp = tmp_path / "t.jsonl"
    tp.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "看看"}]}}) + "\n",
                  encoding="utf-8")
    return str(tp)


def _post_read(monkeypatch, tmp_path, state, path, cwd, config):
    """經真的 post_tool_use 入口送一次 Read（state 與落盤換成記憶體；回補給 AI 的提示或 None）。"""
    from handlers import post_tool_use as pt
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    out = run_handler(pt.handle_post_tool_use, {
        "session_id": SID, "hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": {"file_path": path},
        "tool_response": {}, "cwd": cwd, "transcript_path": _tp(tmp_path)}, {"docdrift": {"enabled": False}, **config})
    return ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext")


def test_post_tool_use_read_records_parts_and_dirs_with_hub_on(proj, tmp_path, monkeypatch):
    """OverviewHub 開著：行為跟以前一樣，第二個部位起排進待送、跨 3 個頂層目錄排一次，導讀卡照樣注入。"""
    make_tree()
    cfg = {"overview_hub": {"enabled": True}}
    state = {"turn_seq": 2, "session": {"id": SID, "cwd": str(proj)}}
    ctx = _post_read(monkeypatch, tmp_path, state, str(proj / "Game/Battle/A.cs"), str(proj), cfg)
    assert ctx and "戰鬥導讀" in ctx and not state.get("need_goal_batch")   # 第一個部位、第一個目錄：不排
    _post_read(monkeypatch, tmp_path, state, str(proj / "Game/Net/B.cs"), str(proj), cfg)
    assert state.get("need_goal_batch")                                        # 第二個部位：排進待送
    for f in ("Tools/x.py", "Docs/y.md"):
        _post_read(monkeypatch, tmp_path, state, str(proj / f), str(proj), cfg)
    kinds = [i["kind"] for i in tree_now()["points"]["scope_pending"]]
    assert kinds == ["part", "dirs"]                                           # Game、Tools、Docs 三個頂層目錄


def test_post_tool_use_read_scope_works_with_hub_off(tmp_path, monkeypatch):
    """OverviewHub 關掉（或專案沒有部位表）：沒有部位概念，但跨頂層目錄的讀入擴張照樣偵測、照樣排進待送（claude-91 改判）。"""
    root = tmp_path / "plain"
    (root / ".git").mkdir(parents=True)
    for d in ("src", "docs", "tools"):
        (root / d).mkdir()
    make_tree()
    cfg = {"overview_hub": {"enabled": False}}
    state = {"turn_seq": 2, "session": {"id": SID, "cwd": str(root)}}
    for f in ("src/a.py", "docs/b.md", "tools/c.py"):
        assert _post_read(monkeypatch, tmp_path, state, str(root / f), str(root), cfg) is None   # 沒有導讀卡
    pending = tree_now().get("points", {}).get("scope_pending", [])
    assert [i["kind"] for i in pending] == ["dirs"] and len(pending[0]["prev"]) == 3
    assert state.get("need_goal_batch") is True and "overview_hub" not in state


def test_scope_on_read_without_goal_file_skips_work(proj, tmp_path, monkeypatch):
    """這個 session 還沒寫過樹：連讀入範圍的計算都不做（每次讀檔都走這裡，要省）；寫了樹才算。"""
    assert hasattr(wo, "read_scope_keys"), "部位與頂層目錄要由 wg_overview.read_scope_keys 算（不看 OverviewHub 開關）"
    called = []
    monkeypatch.setattr(ngp, "scope_growth_line", lambda *a: called.append("part"))
    monkeypatch.setattr(ngp, "scope_dir_line", lambda *a: called.append("dir"))
    cfg = {"overview_hub": {"enabled": True}}
    state = {"turn_seq": 1}
    for f in ("Game/Battle/A.cs", "Tools/x.py"):
        ngp.scope_on_read(state, SID, "Read", {"file_path": str(proj / f)}, str(proj), cfg)
    assert called == [] and not ng.goal_path(SID).exists() and not state.get("need_goal_batch")
    make_tree()
    ngp.scope_on_read(state, SID, "Read", {"file_path": str(proj / "Docs/y.md")}, str(proj), cfg)
    assert called == ["dir"]


def test_goal_change_resends_card_in_goal_view_once(proj, tmp_path):
    make_tree()
    cfg = {"overview_hub": {"enabled": True}}
    state = {"turn_seq": 2}
    tp = _tp(tmp_path)
    f = str(proj / "Game/Battle/A.cs")
    assert "戰鬥導讀" in wo.on_read(state, SID, "Read", {"file_path": f}, str(proj), tp, cfg)
    rec = next(v for k, v in state["overview_hub"].items() if k.endswith("|戰鬥"))
    assert wo.on_read(state, SID, "Read", {"file_path": f}, str(proj), tp, cfg) is None
    rec["goal_reset_turn"] = 4                                                # b2 on_goal_changed 記的
    view = wo.on_read(state, SID, "Read", {"file_path": f}, str(proj), tp, cfg)
    assert view and "目標視角" in view and "戰鬥導讀" in view and "T1.1" in view
    assert rec["goal_view_turn"] == 4 and rec["part_files_read"] == [f]       # 讀檔紀錄沒被重置
    assert wo.on_read(state, SID, "Read", {"file_path": f}, str(proj), tp, cfg) is None   # 只重送一次


# ─── 軌五：壓縮、續接單、session 結束 ─────────────────────────────────────

def _state_io(monkeypatch, state):
    holder = {"state": state}
    for mod in (pc, ptb):
        monkeypatch.setattr(mod, "_ensure_state", lambda sid, inp, cfg: holder["state"])
        monkeypatch.setattr(mod, "write_state", lambda sid, st: holder.__setitem__("state", st))
    return holder


def test_post_compact_resends_goal_without_any_part(monkeypatch):
    make_tree()
    holder = _state_io(monkeypatch, {"session": {"id": SID}, "turn_seq": 3})
    run_handler(pc.handle_post_compact, {"session_id": SID, "trigger": "auto"}, {})
    assert "【需求目標樹】" in holder["state"].get("pending_reinjection_goal", "")
    out = run_handler(ptb.handle_post_tool_batch, {"session_id": SID, "tool_calls": []}, {})
    assert out and "【需求目標樹】" in out["hookSpecificOutput"]["additionalContext"]
    assert "pending_reinjection_goal" not in holder["state"]                   # 一次性


def test_post_compact_overview_main_goal_points_to_tree(monkeypatch, tmp_path):
    make_tree()
    rec = {"part": "戰鬥", "root": str(tmp_path), "layer": "", "located": False, "card_paths": [], "edits": 0}
    holder = _state_io(monkeypatch, {"session": {"id": SID}, "overview_hub": {"x|戰鬥": rec}, "turn_intent": "perf"})
    run_handler(pc.handle_post_compact, {"session_id": SID, "trigger": "auto"}, {})
    assert "主目標：見【需求目標樹】那段（意圖分類附註：perf" in holder["state"].get("pending_reinjection_overview", "")


def test_post_compact_skips_goal_when_session_start_just_sent(monkeypatch):
    make_tree()
    holder = _state_io(monkeypatch, {"session": {"id": SID}, "need_goal_recovery_sent": time.time()})
    run_handler(pc.handle_post_compact, {"session_id": SID, "trigger": "manual"}, {})
    assert "pending_reinjection_goal" not in holder["state"] and "need_goal_recovery_sent" not in holder["state"]
    holder["state"]["need_goal_recovery_sent"] = time.time() - 3600           # 很久以前送的不算同一次壓縮
    run_handler(pc.handle_post_compact, {"session_id": SID, "trigger": "auto"}, {})
    assert "【需求目標樹】" in holder["state"].get("pending_reinjection_goal", "")


def test_recovery_text_respects_enabled():
    make_tree()
    assert "【需求目標樹】" in ngp.recovery_text(SID, {})
    assert ngp.recovery_text(SID, {"overview_hub": {"need_goal": {"enabled": False}}}) == ""


def test_auto_handoff_stub_carries_goal_block():
    state = {"session": {"id": SID}, "modified_files": [{"path": "a.py"}]}
    assert "need-goal:begin" not in wg_handoff.build_handoff_stub(state, "")
    make_tree()
    stub = wg_handoff.build_handoff_stub(state, "")
    assert "## 【需求目標樹】" in stub and "need-goal:begin" in stub
    assert stub.index("## 6.【決策依據】") < stub.index("【需求目標樹】")


def test_auto_handoff_written_for_open_tree_without_edits(tmp_path):
    """沒改過檔、但還有沒結束的目標樹（例：記憶知識類任務做到一半）也要寫自動續接單，樹才帶得到下一個 session。"""
    staging = tmp_path / "staging"
    state = {"session": {"id": SID}, "modified_files": []}
    assert wg_handoff.should_write_stub(staging, state, "next-phase-auto.md") is False   # 沒樹沒改檔：不寫
    make_tree("knowledge")
    assert wg_handoff.should_write_stub(staging, state, "next-phase-auto.md") is True
    make_tree("knowledge", status="closed")                                            # 目前的樹結束了，但前一棵還沒
    assert wg_handoff.should_write_stub(staging, state, "next-phase-auto.md") is True
    staging.mkdir()
    (staging / "next-phase-hand.md").write_text("手寫", encoding="utf-8")              # 有新鮮手寫續接單：照舊尊重不覆蓋
    assert wg_handoff.should_write_stub(staging, state, "next-phase-auto.md") is False


def test_has_open_tree_corrupt_goal_file_is_false_and_logged(world):
    """目標檔壞了：判成沒有樹（不因此多寫續接單），但要留 stderr 與守門紀錄 corrupt，不靜默。"""
    p = ng.goal_path(SID)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{壞掉的 JSON", encoding="utf-8")
    assert ngp.has_open_tree(SID) is False
    g = guard(world)[-1]
    assert g["event"] == "corrupt" and g["where"] == "has_open_tree"


def test_next_phase_pointer_tells_own_vs_other_handoff(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    staging.mkdir()
    monkeypatch.setattr(ss, "MEMORY_DIR", tmp_path / "nomem")
    import wg_core as core
    monkeypatch.setattr(core, "resolve_staging_dir", lambda cwd: staging)
    make_tree()
    f = staging / "next-phase-x.md"
    f.write_text("# 續接\n" + ng.handoff_block(SID), encoding="utf-8")
    assert "session_id" in inspect.signature(ss._next_phase_pointer).parameters, "接續指標不知道是哪個 session"
    own = ss._next_phase_pointer(str(tmp_path), "compact", SID)
    assert own and "本 session 自己匯出" in own[0]
    other = ss._next_phase_pointer(str(tmp_path), "resume", "sid-other")
    assert "自動匯入" in other[0]
    f.write_text("# 續接\n沒有樹", encoding="utf-8")
    assert "需求目標樹" not in ss._next_phase_pointer(str(tmp_path), "resume", SID)[0]


def test_silent_unreconciled_logs_unreconciled_trees_only(world):
    t1 = make_tree("knowledge")                                              # 有樹沒對照
    t2 = make_tree("code")
    add_edits("c:/p/x.py", 1)                                                 # 寫碼類欠對照

    def fn(doc):
        t3 = doc["trees"][t1]
        t3["last_reconcile"] = {"seq": 1, "turn": 1, "goal_rev": 1}
    ng.update_locked(SID, fn)                                                 # 知識類交過對照、版本對得上 → 不記
    make_tree("code", status="closed")                                       # 結束的不記
    recs = ngp.silent_unreconciled(SID, 9)
    assert [r["tree"] for r in recs] == [t2] and recs[0]["owed"] == 1 and recs[0]["why"].startswith("寫碼類")
    g = guard(world)
    assert [e["event"] for e in g] == ["silent_unreconciled"] and g[0]["turn_seq"] == 9


# ─── 呼叫點接線（hook 檔真的呼叫到） ─────────────────────────────────────

def _calls(path, name):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and getattr(n.func, "id", getattr(n.func, "attr", None)) == name]


@pytest.mark.parametrize("rel,name", [
    ("handlers/session_end.py", "silent_unreconciled"),
    ("handlers/user_prompt_submit.py", "on_correction"),
    ("handlers/pre_tool_use.py", "on_ask"),
    ("handlers/post_tool_batch.py", "batch_lines"),
    ("handlers/post_tool_use.py", "scope_on_read"),
])
def test_hook_files_call_points(rel, name):
    assert _calls(HOOKS_DIR / rel, name), f"{rel} 沒呼叫 {name}"


def test_overview_on_read_no_longer_counts_scope():
    """讀入範圍只從 post_tool_use 算一次：wg_overview.on_read 不再呼叫，避免 hub 開著時兩條路各算各的。"""
    assert not _calls(HOOKS_DIR / "wg_overview.py", "scope_growth_line")
    assert not _calls(HOOKS_DIR / "wg_overview.py", "scope_dir_line")


def test_settings_pre_tool_use_matcher_has_ask_tools():
    data = json.loads((HOOKS_DIR.parent / "settings.json").read_text(encoding="utf-8"))
    matchers = [e.get("matcher", "") for e in data["hooks"]["PreToolUse"]
                if any("workflow-guardian.py" in h.get("command", "") for h in e.get("hooks") or [])]
    assert any({"AskUserQuestion", "ExitPlanMode"} <= set(m.split("|")) for m in matchers)


def test_report_need_goal_source():
    """印出這次跑的是真模組還是替身（不判對錯，給交付紀錄用）。"""
    print(f"NEED_GOAL_SOURCE={NG_SOURCE}")
