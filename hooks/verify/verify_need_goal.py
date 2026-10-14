"""verify_need_goal.py：需求目標樹（hooks/wg_need_goal.py）與它的接點。

覆蓋：五個動作與編號、拒收理由、證據組合與先後、目標版本作廢舊對照、狀態轉換、待對照的清法、
兩個行程交錯寫同一個目標檔不掉節點、壞檔留證、鎖拿不到不降級；4.1 新需求開始（第一則提醒、同伴轉述、系統通知不記）；
4.2 第一層（寫碼類沒樹擋、知識類／暫存／關掉不擋）與第二層（定位第四行、編號存在、目標改了要重交、導讀卡附樹）；
4.5 (f1) 不看措辭、(f2) 只在交付邊界、commit 前、子代理不跑；收尾檢核附樹、續接單寫出與匯入、壓縮重送、審查材料；
code_exts 聯集與 `#!` 腳本、hub_config 的 need_goal 段、post_tool_use／user_prompt_submit 的接線。
不碰 live：目標檔、state、守門紀錄、OverviewHub log 全落 tmp。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_need_goal.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_core  # noqa: E402
import wg_need_goal as ng  # noqa: E402
import wg_overview as wo  # noqa: E402
from handlers import _shared  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
from handlers import pre_tool_use as ptu  # noqa: E402
from handlers import stop as st  # noqa: E402
from handlers import user_prompt_submit as ups  # noqa: E402
import hub_config  # noqa: E402
import overview_hub  # noqa: E402
import wg_verify_ledger as vl  # noqa: E402

SID = "sess-goal-0001"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """tmp 資料根：目標檔、state、守門紀錄、OverviewHub log 都在 tmp；pytest 暫存目錄不當成暫存檔（測的就是正式檔的行為：
    暫存檔判定換成 /eph/，OverviewHub 的 TEMP_COPY_NOT_PROJECT 關掉）。"""
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    wf = tmp_path / "wf"
    wf.mkdir()
    guard = []
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_core, "append_guard_log", lambda g, p: guard.append((g, p)))
    monkeypatch.setattr(wg_core, "_rebuild_min_atom_index", lambda cwd: {})
    monkeypatch.setattr(wg_core, "_find_active_sibling_state", lambda *a, **k: None)
    monkeypatch.setattr(wg_core, "_atom_debug_log", lambda *a, **k: None)
    monkeypatch.setattr(_shared, "_is_ephemeral_path", lambda p: "/eph/" in str(p).replace("\\", "/"))
    monkeypatch.setattr(pt, "_is_ephemeral_path", lambda p: "/eph/" in str(p).replace("\\", "/"))
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    proj = tmp_path / "proj"
    proj.mkdir()
    return {"wf": wf, "guard": guard, "proj": proj, "tmp": tmp_path}


def _op(action, turn=1, sid=SID, cwd="", **kw):
    return ng.apply_op(sid, turn, {"action": action, **kw}, cwd)


def _doc(sid=SID):
    return ng.load(sid)


def _tree(sid=SID):
    return ng.active_tree(_doc(sid))


def _receipt_state(*entries, sid=SID):
    return {"verify_receipts": {sid: [dict(e) for e in entries]}}


def _rcpt(seq, cmd="pytest -q x", verdict="PASS", turn=2):
    return {"seq": seq, "at": f"2026-10-13T00:00:{seq:02d}", "turn_seq": turn, "cmd": cmd,
            "sentinels": [{"name": "X_CHECK", "verdict": verdict}], "exit_code": 0}


# ─── 五個動作、編號、拒收 ─────────────────────────────────────────────────

def test_set_creates_tree_seeds_user_said_and_numbers(env):
    ng.on_prompt(SID, "幫我讓設定改完不用重開程式", 1, {})
    r = _op("set", goal="改完設定不用重開就生效")
    assert r["ok"] and r["tree"] == "T1" and r["goal_changed"]
    t = _tree()
    assert t["id"] == "T1" and t["status"] == "doing" and t["kind"] == "knowledge" and t["goal_rev"] == 1
    assert t["user_said"][0]["text"] == "幫我讓設定改完不用重開程式"
    assert "T1" in r["text"] and "使用者原話（權威）" in r["text"]
    assert _op("add", items=[{"text": "舊設定的檔不能壞"}, {"text": "方向：要不要通知", "clarity": "open"}])["ok"]
    assert _op("add", parent="T1.1", items=[{"text": "下層"}])["ok"]
    assert sorted(_tree()["nodes"]) == ["T1", "T1.1", "T1.1.1", "T1.2"]
    assert _tree()["goal_rev"] == 3 and _tree()["nodes"]["T1.2"]["clarity"] == "open"
    bad = _op("add", parent="T9", items=[{"text": "x"}])
    assert not bad["ok"] and "T9" in bad["rejected"][0]


def test_validate_rejects_like_js(env):
    assert "goal" in _op("set")["rejected"][0]
    assert any("why" in x for x in _op("update", items=[{"id": "T1", "status": "done"}])["rejected"])
    assert any("終點" in x for x in _op("reconcile", items=[{"id": "T1", "status": "doing"}])["rejected"])
    r = _op("reconcile", items=[{"id": "T1", "status": "done", "evidence": [{"kind": "proof", "ref": "x", "level": "sure"}]}])
    assert any("kind" in x for x in r["rejected"]) and any("level" in x for x in r["rejected"])
    assert "action" in _op("explode")["rejected"][0]
    assert not ng.goal_path(SID).exists()                                   # 拒收的不建檔


def test_add_update_reconcile_need_a_tree(env):
    for action, kw in (("add", {"items": [{"text": "x"}]}), ("update", {"items": [{"id": "T1", "status": "done", "why": "w"}]}),
                       ("reconcile", {"items": [{"id": "T1", "status": "dropped", "note": "n"}]})):
        r = _op(action, **kw)
        assert not r["ok"] and "還沒有目標樹" in r["rejected"][0], action


def test_set_rewrite_needs_why_new_task_opens_new_tree(env):
    _op("set", goal="A")
    r = _op("set", goal="B")
    assert not r["ok"] and "why" in r["rejected"][0]
    r = _op("set", goal="B", why="使用者改口要 B")
    assert r["ok"] and _tree()["nodes"]["T1"]["text"] == "B" and _tree()["goal_rev"] == 2
    r = _op("set", goal="C", new_task=True, turn=3)
    assert r["tree"] == "T2" and _doc()["active"] == "T2" and _doc()["trees"]["T1"]["status"] == "doing"


def test_update_status_text_and_close_on_root_dropped(env):
    _op("set", goal="A")
    _op("add", items=[{"text": "a1"}])
    rev = _tree()["goal_rev"]
    assert _op("update", items=[{"id": "T1.1", "status": "doing", "why": "開始做"}])["ok"]
    assert _tree()["goal_rev"] == rev                                       # 只改狀態不加版本
    assert _op("update", items=[{"id": "T1.1", "text": "a1 改寫", "why": "讀到新資訊"}])["goal_changed"]
    assert _tree()["goal_rev"] == rev + 1
    assert not _op("update", items=[{"id": "T7", "status": "done", "why": "x"}])["ok"]
    _op("update", items=[{"id": "T1", "status": "dropped", "why": "整個需求不做了"}])
    assert _tree()["status"] == "closed"


# ─── 改檔、收據、待對照 ─────────────────────────────────────────────────────

def test_stamp_edit_code_vs_knowledge_and_owed(env):
    proj = env["proj"]
    ng.stamp_edit(SID, str(proj / "a.py"), "", 1, {})                       # 沒樹不記
    assert not ng.goal_path(SID).exists()
    _op("set", goal="A")
    ng.stamp_edit(SID, str(proj / "notes.md"), "", 2, {})
    assert _tree()["kind"] == "knowledge" and not ng._owed(_tree())
    ng.stamp_edit(SID, str(proj / "a.py"), "agent7", 2, {})
    t = _tree()
    assert t["kind"] == "code" and len(ng._owed(t)) == 1 and t["edits"][-1]["agent_id"] == "agent7"
    assert t["edits"][-1]["node"] == "T1"                                   # 沒部位表：掛樹根


def test_update_clears_owed_of_node_and_ancestors_only(env):
    proj = env["proj"]
    _op("set", goal="A")
    _op("add", items=[{"text": "a1"}, {"text": "a2"}])
    ng.update_locked(SID, lambda d: ng.active_tree(d)["links"]["parts"].__setitem__("k2", {"node": "T1.2", "seq": 1}))
    ng.stamp_edit(SID, str(proj / "root.py"), "", 2, {})                    # 掛 T1
    monkey_key = {"v": "k2"}
    orig = ng._hub_key_of
    ng._hub_key_of = lambda p: monkey_key["v"]
    try:
        ng.stamp_edit(SID, str(proj / "two.py"), "", 2, {})                 # 掛 T1.2
    finally:
        ng._hub_key_of = orig
    _op("update", items=[{"id": "T1.1", "status": "doing", "why": "這次改動讓 a1 更接近"}], turn=2)
    owed = {e["node"] for e in ng._owed(_tree())}
    assert owed == {"T1.2"}                                                 # T1 的被 T1.1（在它底下）清掉；T1.2 的還在


def test_stamp_receipts_dedupe_and_agent_key(env):
    _op("set", goal="A")
    state = _receipt_state(_rcpt(5))
    state["verify_receipts"][f"{SID}#agent:ab"] = [_rcpt(6, cmd="node smoke.js")]
    state["verify_receipts"]["other-sid"] = [_rcpt(7)]
    assert ng.stamp_receipts(SID, state, 2) == 2
    assert ng.stamp_receipts(SID, state, 2) == 0                            # 同一筆不重蓋
    rs = _doc()["receipts"]
    assert {r["key"] for r in rs} == {SID, f"{SID}#agent:ab"} and rs[0]["verdicts"] == ["X_CHECK:PASS"]
    assert ng.stamp_receipts("no-file-sid", state, 2) == 0                  # 目標檔不存在不蓋


# ─── 完整對照（第 3～7 條）與先後 ───────────────────────────────────────────

def _code_tree(env):
    proj = env["proj"]
    _op("set", goal="A", cwd=str(proj))
    _op("add", items=[{"text": "a1"}, {"text": "a2"}])
    ng.stamp_edit(SID, str(proj / "a.py"), "", 2, {})
    return proj


def test_reconcile_rejections_cover_each_rule(env):
    proj = _code_tree(env)
    (proj / "a.py").write_text("x", encoding="utf-8")
    ng.stamp_receipts(SID, _receipt_state(_rcpt(9)), 2)
    rno = f"R{_doc()['receipts'][-1]['seq']}"
    cases = [
        ([{"id": "T1", "status": "done", "evidence": [{"kind": "receipt", "ref": rno, "level": "measured"}]}],
         "T1.1 沒在對照裡"),
        ([{"id": "T1", "status": "done"}, {"id": "T1.1", "status": "dropped", "note": "n"},
          {"id": "T1.2", "status": "dropped", "note": "n"}], "沒附證據"),
        ([{"id": "T1", "status": "done", "evidence": [{"kind": "file", "ref": str(proj / "a.py"), "level": "measured"}]},
          {"id": "T1.1", "status": "dropped", "note": "n"}, {"id": "T1.2", "status": "dropped", "note": "n"}],
         "實測只能配收據"),
        ([{"id": "T1", "status": "done", "evidence": [{"kind": "receipt", "ref": rno, "level": "read"}]},
          {"id": "T1.1", "status": "dropped", "note": "n"}, {"id": "T1.2", "status": "dropped", "note": "n"}],
         "收據只能標實測"),
        ([{"id": "T1", "status": "done", "evidence": [{"kind": "receipt", "ref": "R999", "level": "measured"}]},
          {"id": "T1.1", "status": "dropped", "note": "n"}, {"id": "T1.2", "status": "dropped", "note": "n"}],
         "R999 找不到"),
        ([{"id": "T1", "status": "done", "evidence": [{"kind": "file", "ref": str(proj / "a.py") + ":3", "level": "inferred"}]},
          {"id": "T1.1", "status": "dropped", "note": "n"}, {"id": "T1.2", "status": "dropped", "note": "n"}],
         "只有推論"),
        ([{"id": "T1", "status": "partial", "evidence": [{"kind": "file", "ref": "a.py", "level": "read"}]},
          {"id": "T1.1", "status": "dropped", "note": "n"}, {"id": "T1.2", "status": "dropped", "note": "n"}],
         "要寫 followup"),
        ([{"id": "T1", "status": "partial", "evidence": [{"kind": "file", "ref": "a.py", "level": "read"}], "followup": "f"},
          {"id": "T1.1", "status": "dropped"}, {"id": "T1.2", "status": "dropped", "note": "n"}],
         "要在 note 寫為什麼"),
        ([{"id": "T1", "status": "partial", "evidence": [{"kind": "file", "ref": "nope.py", "level": "read"}], "followup": "f"},
          {"id": "T1.1", "status": "dropped", "note": "n"}, {"id": "T1.2", "status": "dropped", "note": "n"}],
         "不在磁碟上"),
        ([{"id": "T1", "status": "done", "evidence": [{"kind": "receipt", "ref": rno, "level": "measured", "covers": ["T5"]}]},
          {"id": "T1.1", "status": "dropped", "note": "n"}, {"id": "T1.2", "status": "dropped", "note": "n"}],
         "不存在的節點 T5"),
    ]
    for items, want in cases:
        r = _op("reconcile", items=items, turn=3, cwd=str(proj))
        assert not r["ok"] and any(want in x for x in r["rejected"]), (want, r["rejected"])
        assert _tree()["last_reconcile"] is None                            # 整批拒收、一項都沒套用
    assert len(ng._owed(_tree())) == 1


_NODE_ID_CASE_SRC = """
def test_alpha():
    pass


class TestGroup:
    def test_beta(self):
        pass
"""


@pytest.mark.parametrize("ref, want", [
    ("{case}::test_alpha", None),                                        # pytest 節點 id 收（改前被當檔名擋）
    ("{case}::TestGroup::test_beta[1-2]", None),                         # 類別＋參數也收
    ("{case}::test_nope", "def test_nope 找到=否"),                        # 檔在、def 不在 → 擋
    ("{proj}/nope_x.py::test_alpha", "檔在=否"),                           # 檔不在 → 擋
    ("{case}::TestGroup::test_alpha", "def test_alpha 找到=否"),           # 有寫類別就要在那個類別裡
], ids=["func", "class-param", "missing-def", "missing-file", "wrong-class"])
def test_reconcile_case_accepts_pytest_node_id_only_when_def_found(env, ref, want):
    """裁定 #25：案例證據接受 pytest 節點 id（第一個 :: 切出檔，最後一段去 [...] 當測試名），檔要在、檔裡要有那個 def；
    對不上的擋訊息印規則名與查到的證據。「檔:行」照舊。"""
    proj = _code_tree(env)
    case = proj / "test_x.py"
    case.write_text(_NODE_ID_CASE_SRC, encoding="utf-8")
    ev = {"kind": "case", "ref": ref.format(case=case, proj=proj), "level": "read"}
    items = [{"id": "T1", "status": "partial", "evidence": [ev], "followup": "f"},
             {"id": "T1.1", "status": "dropped", "note": "n"}, {"id": "T1.2", "status": "dropped", "note": "n"}]
    r = _op("reconcile", items=items, turn=3, cwd=str(proj))
    if want is None:
        assert r["ok"], r["rejected"]
        return
    assert not r["ok"] and any("CASE_NODE_ID_NEEDS_DEF" in x and want in x for x in r["rejected"]), r["rejected"]


def test_receipt_must_follow_last_edit_of_covered_nodes(env):
    proj = _code_tree(env)                                                  # a.py 改動掛 T1（樹根）
    ng.stamp_receipts(SID, _receipt_state(_rcpt(3)), 2)                     # 收據在改動之後
    early = _doc()["receipts"][-1]["seq"]
    ng.stamp_edit(SID, str(proj / "b.py"), "", 2, {})                       # 又改了（掛樹根）
    items = [{"id": "T1.1", "status": "done", "evidence": [{"kind": "receipt", "ref": f"R{early}", "level": "measured"}]},
             {"id": "T1", "status": "partial", "evidence": [{"kind": "receipt", "ref": f"R{early}", "level": "measured"}],
              "followup": "等 B"},
             {"id": "T1.2", "status": "none", "followup": "下一輪"}]
    r = _op("reconcile", items=items, turn=3, cwd=str(proj))
    assert not r["ok"] and any("改完沒重跑" in x and "b.py" in x for x in r["rejected"])   # 祖先上的改動也要對
    ng.stamp_receipts(SID, _receipt_state(_rcpt(3), _rcpt(4)), 2)
    late = _doc()["receipts"][-1]["seq"]
    for it in items[:2]:
        it["evidence"][0]["ref"] = f"R{late}"
    r = _op("reconcile", items=items, turn=3, cwd=str(proj))
    assert r["ok"], r["rejected"]
    t = _tree()
    assert t["status"] == "reconciled" and t["last_reconcile"]["goal_rev"] == t["goal_rev"] and not ng._owed(t)


def test_unrelated_node_edit_does_not_force_reverify(env):
    proj = env["proj"]
    _op("set", goal="A", cwd=str(proj))
    _op("add", items=[{"text": "a1"}, {"text": "a2"}])
    for nid, name in (("T1.1", "one.py"), ("T1.2", "two.py")):
        ng.update_locked(SID, lambda d, n=nid, k=name: ng.active_tree(d)["links"]["parts"].__setitem__(k, {"node": n, "seq": 1}))
    orig = ng._hub_key_of
    ng._hub_key_of = lambda p: Path(p).name
    try:
        ng.stamp_edit(SID, str(proj / "one.py"), "", 2, {})
        ng.stamp_receipts(SID, _receipt_state(_rcpt(3)), 2)
        rno = f"R{_doc()['receipts'][-1]['seq']}"
        ng.stamp_edit(SID, str(proj / "two.py"), "", 2, {})                 # 改的是 T1.2，不影響 T1.1 的證據
    finally:
        ng._hub_key_of = orig
    (proj / "one.py").write_text("x", encoding="utf-8")
    r = _op("reconcile", turn=3, cwd=str(proj), items=[
        {"id": "T1", "status": "partial", "evidence": [{"kind": "file", "ref": "one.py", "level": "read"}], "followup": "T1.2"},
        {"id": "T1.1", "status": "done", "evidence": [{"kind": "receipt", "ref": rno, "level": "measured"}]},
        {"id": "T1.2", "status": "none", "followup": "還沒驗"}])
    assert r["ok"], r["rejected"]


# ─── C-G3／C-G10：寫碼類的「達成」要指到試過的案例或收據；案例先紅後綠留紀錄 ─────────────────

def _done_items(evidence):
    return [{"id": "T1", "status": "done", "evidence": evidence},
            {"id": "T1.1", "status": "dropped", "note": "n"}, {"id": "T1.2", "status": "dropped", "note": "n"}]


def _kind_tree(env, code):
    """code=True：改過 a.py 的寫碼類樹；False：只改過 notes.md 的記憶知識類樹。兩種都有 a.py、verify_a.py 可引用。"""
    proj = env["proj"]
    _op("set", goal="A", cwd=str(proj))
    _op("add", items=[{"text": "a1"}, {"text": "a2"}])
    ng.stamp_edit(SID, str(proj / ("a.py" if code else "notes.md")), "", 2, {})
    (proj / "a.py").write_text("x", encoding="utf-8")
    (proj / "verify_a.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    assert _tree()["kind"] == ("code" if code else "knowledge")
    return proj


@pytest.mark.parametrize("code, evidence, verdict, want", [
    (True, [("file", "a.py", "read")], None, "GOAL_DONE_NEEDS_CASE_OR_RECEIPT"),        # 只有檔案 → 擋
    (True, [("case", "verify_a.py::test_a", "read")], None, None),                       # 有案例 → 收
    (True, [("receipt", "R", "measured")], "PASS", None),                                # 有綠收據 → 收
    (True, [("receipt", "R", "measured")], "FAIL", "GOAL_DONE_NEEDS_CASE_OR_RECEIPT"),   # 只有紅收據 → 擋
    (True, [("case", "verify_a.py", "inferred"), ("file", "a.py", "read")], None,
     "GOAL_DONE_NEEDS_CASE_OR_RECEIPT"),                                                  # 案例只標推論不算試過
    (False, [("file", "a.py", "read")], None, None),                                     # 記憶知識類不擋
    (True, [("file", "a.py", "inferred")], None, "GOAL_INFERRED_MAX_PARTIAL"),           # 只有推論 → 擋
    (False, [("file", "a.py", "inferred")], None, "GOAL_INFERRED_MAX_PARTIAL"),          # 推論最多部分，不分類別
], ids=["code-file", "code-case", "code-receipt-pass", "code-receipt-fail", "code-case-inferred",
        "knowledge-file", "code-inferred", "knowledge-inferred"])
def test_goal_done_needs_case_or_receipt(env, code, evidence, verdict, want):
    """GOAL_DONE_NEEDS_CASE_OR_RECEIPT／GOAL_INFERRED_MAX_PARTIAL：走真的 reconcile。擋訊息印規則名、節點、現有證據是哪種。"""
    proj = _kind_tree(env, code)
    ev = []
    for kind, ref, level in evidence:
        if kind == "receipt":
            ng.stamp_receipts(SID, _receipt_state(_rcpt(9, verdict=verdict)), 2)
            ref = f"R{_doc()['receipts'][-1]['seq']}"
        ev.append({"kind": kind, "ref": ref, "level": level})
    r = _op("reconcile", items=_done_items(ev), turn=3, cwd=str(proj))
    if want is None:
        assert r["ok"], r["rejected"]
        assert ng.goal_gate_reason(SID, True, {}) is None                   # 交付邊界的 (f2) 用同一套判定，收了就不再擋
        return
    hit = [x for x in r["rejected"] if f"規則 {want}" in x]
    assert not r["ok"] and hit, r["rejected"]
    assert "T1 " in hit[0] and "現有證據：" in hit[0] and ng.LABEL["ekind"][evidence[0][0]] in hit[0], hit[0]
    assert _tree()["last_reconcile"] is None


_PYTEST = "python -X utf8 -m pytest -q "
_LONG = _PYTEST + " ".join(f"hooks/verify/verify_example_{i}.py" for i in range(8)) + " verify_a.py"   # 超過 200 字


@pytest.mark.parametrize("ref, runs, want", [
    ("verify_a.py::test_a", [(_PYTEST + "verify_a.py", "FAIL"), (_PYTEST + "verify_a.py", "PASS")], True),
    ("verify_a.py::test_a", [(_PYTEST + "verify_a.py", "PASS")], False),                          # 只有綠
    ("verify_a.py::test_a", [(_PYTEST + "verify_b.py", "FAIL"), (_PYTEST + "verify_a.py", "PASS")], False),
    ("verify_a.py::test_a", [(_PYTEST + "verify_a.py", "PASS"), (_PYTEST + "verify_a.py", "FAIL"),
                             (_PYTEST + "x.py", "PASS")], False),                                 # 先綠後紅不算
    ("verify_a.py::test_a", [(_LONG, "FAIL"), (_LONG, "PASS")], True),                            # 長指令尾端的案例（codex BLOCK 2）
    ("verify_a.py::test_a", [("cd sub && " + _PYTEST + "verify_a.py", "FAIL"),
                             ("cd sub && " + _PYTEST + "verify_a.py", "PASS")], False),           # 跑的是 sub/ 底下的（codex BLOCK 3）
    ("my tests/verify_s.py::test_a", [(_PYTEST + '"my tests/verify_s.py"', "FAIL"),
                                      (_PYTEST + '"my tests/verify_s.py::test_a"', "PASS")], True),  # 引號裡有空白（codex BLOCK 1）
], ids=["red-then-green", "green-only", "other-file-red", "green-then-red", "long-cmd", "cd-elsewhere", "quoted-space"])
def test_case_red_then_green_recorded_not_gated(env, ref, runs, want):
    """CASE_RED_THEN_GREEN：案例證據對上目標檔收據裡同一檔先紅後綠 → 該筆證據記 red_then_green=true、摘要印出；
    對不上照收，摘要印「案例未見先紅」。只是紀錄，不是閘。收據用完整指令與它的 cwd 解出點名的案例檔；指令裡換目錄的不比。"""
    proj = _kind_tree(env, True)
    (proj / "my tests").mkdir()
    (proj / "my tests" / "verify_s.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    rows = [{**_rcpt(i + 3, cmd=cmd, verdict=v), "cwd": str(proj)} for i, (cmd, v) in enumerate(runs)]
    ng.stamp_receipts(SID, _receipt_state(*rows), 2)
    r = _op("reconcile", items=_done_items([{"kind": "case", "ref": ref, "level": "read"}]),
            turn=3, cwd=str(proj))
    assert r["ok"], r["rejected"]
    assert _tree()["nodes"]["T1"]["evidence"][0].get("red_then_green") is want
    assert ("red_then_green" in r["text"]) is want and ("案例未見先紅" in r["text"]) is (not want), r["text"]


def test_reconcile_followups_go_to_tracking(env, monkeypatch):
    rows = []
    import wg_harvest
    monkeypatch.setattr(wg_harvest, "append_tracking", lambda slug, entries, base_dir=None: rows.extend(entries))
    proj = env["proj"]
    _op("set", goal="A", cwd=str(proj))
    r = _op("reconcile", turn=2, cwd=str(proj), items=[{"id": "T1", "status": "none", "followup": "下次補驗證"}])
    assert r["ok"] and _tree()["status"] == "reconciled"
    assert rows and "需求目標 T1（沒有）：下次補驗證" in rows[0]["text"]


def test_goal_change_after_reconcile_voids_it(env):
    proj = _code_tree(env)
    ng.stamp_receipts(SID, _receipt_state(_rcpt(3)), 2)
    rno = f"R{_doc()['receipts'][-1]['seq']}"
    ok = _op("reconcile", turn=3, cwd=str(proj), items=[
        {"id": "T1", "status": "done", "evidence": [{"kind": "receipt", "ref": rno, "level": "measured"}]},
        {"id": "T1.1", "status": "done", "evidence": [{"kind": "receipt", "ref": rno, "level": "measured"}]},
        {"id": "T1.2", "status": "dropped", "note": "不做"}])
    assert ok["ok"] and _tree()["status"] == "closed"
    assert ng.goal_gate_reason(SID, True, {}) is None
    _op("add", items=[{"text": "後來長出的"}], turn=4)
    t = _tree()
    assert t["status"] == "doing"
    reason = ng.goal_gate_reason(SID, True, {})
    assert reason and "(f2)" in reason and "舊對照作廢" in reason


def test_code_edit_reopens_reconciled_tree(env):
    proj = env["proj"]
    _op("set", goal="A", cwd=str(proj))
    _op("reconcile", turn=2, cwd=str(proj), items=[{"id": "T1", "status": "none", "followup": "f"}])
    assert _tree()["status"] == "reconciled"
    ng.stamp_edit(SID, str(proj / "x.py"), "", 3, {})
    assert _tree()["status"] == "doing" and _tree()["kind"] == "code"


def test_old_tree_owed_after_topic_switch_can_still_be_cleared(env):
    proj = env["proj"]
    _op("set", goal="A", cwd=str(proj))
    _op("add", items=[{"text": "a1"}])
    ng.stamp_edit(SID, str(proj / "a.py"), "", 2, {})
    _op("set", goal="B", new_task=True, turn=3)                             # 換題：T2 成為目前的樹
    assert "(f1)" in ng.goal_gate_reason(SID, False, {})                    # T1 欠的照樣要交
    r = _op("update", items=[{"id": "T1", "status": "doing", "why": "a.py 的改動讓 A 更接近"}], turn=3)
    assert r["ok"] and r["tree"] == "T1" and ng.goal_gate_reason(SID, False, {}) is None
    assert _doc()["active"] == "T2"                                          # 交舊樹不切換目前的樹
    assert _op("add", parent="T1.1", items=[{"text": "舊樹長出的"}], turn=3)["tree"] == "T1"
    mixed = _op("reconcile", turn=3, items=[{"id": "T1", "status": "none", "followup": "f"},
                                             {"id": "T2", "status": "none", "followup": "f"}])
    assert not mixed["ok"] and "只對一棵樹" in mixed["rejected"][0]
    r = _op("reconcile", turn=3, cwd=str(proj), items=[
        {"id": "T1", "status": "none", "followup": "f"}, {"id": "T1.1", "status": "dropped", "note": "不做"},
        {"id": "T1.1.1", "status": "none", "followup": "f"}])
    assert r["ok"] and _doc()["trees"]["T1"]["last_reconcile"] and _doc()["active"] == "T2"


def test_imported_code_tree_needs_reconcile_even_without_new_edits(env):
    proj = _code_tree(env)
    block = ng.handoff_block(SID)
    ng.import_handoff("sess-cont", block, str(proj / "next-phase-c.md"), 1)
    assert ng.active_tree(ng.load("sess-cont"))["kind"] == "code"
    reason = ng.goal_gate_reason("sess-cont", True, {})
    assert reason and "(f2)" in reason and "還沒交完整對照" in reason          # 續接後只補驗證就交付也要對照
    assert "(f2)" in ng.commit_gate("sess-cont", {})


def test_caps_never_drop_owed_or_last_edit_order(env, monkeypatch):
    monkeypatch.setattr(ng, "EDITS_MAX", 3)
    proj = env["proj"]
    _op("set", goal="A", cwd=str(proj))
    ng.stamp_edit(SID, str(proj / "x.py"), "", 2, {})
    ng.stamp_edit(SID, str(proj / "x.py"), "", 2, {})
    assert len(ng._owed(_tree())) == 1                                      # 同一檔還欠著：併成一筆
    for name in ("a.py", "b.py", "c.py", "d.py"):
        ng.stamp_edit(SID, str(proj / name), "", 2, {})
    assert len(ng._owed(_tree())) == 5                                      # 全都欠著：一筆都不丟
    _op("update", items=[{"id": "T1", "status": "doing", "why": "都對過了"}], turn=2)
    ng.stamp_receipts(SID, _receipt_state(_rcpt(3)), 2)
    rno = f"R{_doc()['receipts'][-1]['seq']}"
    for name in ("e.py", "f.py", "g.py"):
        ng.stamp_edit(SID, str(proj / name), "", 3, {})
    t = _tree()
    assert len(t["edits"]) <= 5 and not any(Path(e["path"]).name == "x.py" for e in t["edits"])   # 截掉已清的舊紀錄
    (proj / "g.py").write_text("x", encoding="utf-8")
    r = _op("reconcile", turn=3, cwd=str(proj), items=[
        {"id": "T1", "status": "done", "evidence": [{"kind": "receipt", "ref": rno, "level": "measured"}]}])
    assert not r["ok"] and any("改完沒重跑" in x for x in r["rejected"])     # 先後讀 node_last_edit，不受截短影響


def test_receipt_trim_keeps_cited_and_never_restamps(env, monkeypatch):
    monkeypatch.setattr(ng, "RECEIPTS_MAX", 2)
    _op("set", goal="A")
    state = _receipt_state(_rcpt(1))
    ng.stamp_receipts(SID, state, 2)
    cited = _doc()["receipts"][-1]["seq"]
    _op("reconcile", turn=2, items=[{"id": "T1", "status": "done",
                                      "evidence": [{"kind": "receipt", "ref": f"R{cited}", "level": "measured"}]}])
    state = _receipt_state(_rcpt(1), _rcpt(2), _rcpt(3), _rcpt(4))
    ng.stamp_receipts(SID, state, 3)
    seqs = [r["seq"] for r in _doc()["receipts"]]
    assert cited in seqs and len(seqs) == 2                                  # 被引用的留著
    assert ng.stamp_receipts(SID, state, 3) == 0                            # 截掉的不會被重新蓋成新號
    assert ng.goal_gate_reason(SID, True, {}) is None


def test_prune_keeps_lock_files(env):
    d = ng.goal_dir()
    d.mkdir(parents=True, exist_ok=True)
    old = 10 ** 9
    for name in ("other.json", "other.lock", "x.1.ab.tmp"):
        (d / name).write_text("{}", encoding="utf-8")
        os.utime(d / name, (old, old))
    _op("set", goal="A")
    assert not (d / "other.json").exists() and not (d / "x.1.ab.tmp").exists() and (d / "other.lock").exists()


def test_project_level_switch_turns_gates_off(env):
    proj = env["proj"]
    (proj / ".git").mkdir()
    (proj / ".claude").mkdir()
    (proj / ".claude" / "overview-hub.json").write_text('{"need_goal": {"enabled": false}}', encoding="utf-8")
    _op("set", goal="A", cwd=str(proj))
    ng.update_locked(SID, lambda d: ng.active_tree(d).update(kind="code"))
    ng.update_locked(SID, lambda d: ng.active_tree(d)["edits"].append(
        {"seq": 99, "turn": 1, "path": str(proj / "a.py"), "node": "T1", "agent_id": "", "code": True, "owed": True}))
    assert ng.goal_gate_reason(SID, True, {}) is None and ng.commit_gate(SID, {}) is None
    assert ng.edit_gate(SID, str(proj / "b.py"), {}) is None


# ─── 並行、損毀、鎖 ─────────────────────────────────────────────────────────

_WORKER = r"""
import os, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import wg_need_goal as ng
sid, tag, n = sys.argv[3], sys.argv[4], int(sys.argv[5])
for i in range(n):
    def fn(doc, i=i):
        t = ng.active_tree(doc)
        nid = ng._child_id(t, t["id"])
        t["nodes"][nid] = {"parent": t["id"], "text": f"{tag}-{i}", "origin": "grown", "clarity": "clear",
                           "status": "todo", "history": [], "evidence": [], "followup": "", "note": ""}
        ng.next_seq(doc)
    ng.update_locked(sid, fn)
print("WORKER DONE", tag)
"""


def test_two_processes_interleaving_lose_no_nodes(env, tmp_path):
    root = tmp_path / "root"
    (root / "workflow").mkdir(parents=True)
    script = tmp_path / "worker.py"
    script.write_text(_WORKER, encoding="utf-8")
    # 子行程照正式路徑寫進 tmp 資料根（拿掉 PYTEST_CURRENT_TEST）；守門紀錄預設寫家目錄的 .claude/Logs、不跟 WG_CLAUDE_DIR 走，
    # 所以守門紀錄目錄與家目錄（USERPROFILE／HOME 兩個都要）也導到 tmp
    envv = {**os.environ, "WG_CLAUDE_DIR": str(root), "WG_TEST_LOGS_DIR": str(root / "Logs"),
            "USERPROFILE": str(tmp_path / "home"), "HOME": str(tmp_path / "home"), "PYTHONIOENCODING": "utf-8"}
    envv.pop("PYTEST_CURRENT_TEST", None)
    seed = [sys.executable, "-X", "utf8", "-c",
            f"import sys; sys.path.insert(0, {str(HOOKS_DIR)!r}); sys.path.insert(0, {str(HOOKS_DIR.parent / 'lib')!r});"
            f"import wg_need_goal as ng; ng.apply_op({SID!r}, 1, {{'action': 'set', 'goal': 'G'}})"]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.run(seed, env=envv, check=True, creationflags=flags, capture_output=True)
    procs = [subprocess.Popen([sys.executable, "-X", "utf8", str(script), str(HOOKS_DIR), str(HOOKS_DIR.parent / "lib"),
                               SID, tag, "25"], env=envv, creationflags=flags,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) for tag in ("a", "b")]
    outs = [p.communicate(timeout=120) for p in procs]
    assert all(p.returncode == 0 for p in procs), [o[1].decode("utf-8", "replace")[-500:] for o in outs]
    doc = json.loads((root / "workflow" / "need-goal" / f"{SID}.json").read_text(encoding="utf-8"))
    texts = [n["text"] for n in doc["trees"]["T1"]["nodes"].values()]
    assert len(texts) == 51 and sum(t.startswith("a-") for t in texts) == 25 and sum(t.startswith("b-") for t in texts) == 25
    assert doc["seq"] == 2 + 50                                              # 開樹 2 號（樹＋checkpoint）＋每次 1 號，一號都沒掉
    assert '"session_id": "sess-goal-0001"' in (root / "Logs" / "guard-need_goal.jsonl").read_text(encoding="utf-8")   # 守門紀錄落 tmp


def test_corrupt_file_is_backed_up_and_gate_denies(env):
    p = ng.goal_path(SID)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ng.NeedGoalCorrupt):
        ng.load(SID)
    deny = ng.edit_gate(SID, str(env["proj"] / "a.py"), {})
    assert deny and "目標檔損毀" in deny
    r = _op("set", goal="重寫")
    assert r["ok"] and "損毀" in r["text"]
    assert list(p.parent.glob(f"{p.stem}.corrupt-*.json")) and _tree()["id"] == "T1"


def test_lock_timeout_raises_instead_of_unlocked_write(env, monkeypatch):
    monkeypatch.setattr(ng, "LOCK_WAIT_S", 0.2)
    _op("set", goal="A")
    with ng._locked(ng.goal_path(SID).with_suffix(".lock")):
        with pytest.raises(ng.NeedGoalLockTimeout):
            ng.update_locked(SID, lambda d: ng.next_seq(d))
        r = pt._need_goal_after_tool({"turn_seq": 2}, SID, "mcp__workflow-guardian__need_goal",
                                     {"action": "add", "items": [{"text": "x"}]}, {"tool_response": {}}, {})
    assert "沒寫進目標檔" in r[0] and len(_tree()["nodes"]) == 1


# ─── 4.1 新需求開始 ──────────────────────────────────────────────────────

def test_on_prompt_first_hint_only_once_and_header_with_tree(env):
    assert ng.on_prompt(SID, "幫我修登入", 1, {}) == ng.HINT_LINE
    assert ng.on_prompt(SID, "還有這個", 2, {}) is None
    _op("set", goal="登入要能用", turn=2)
    line = ng.on_prompt(SID, "順便看一下", 3, {})
    assert line.startswith("[NeedGoal] 目前需求目標 T1：登入要能用") and "new_task=true" in line
    said = [s["text"] for s in _tree()["user_said"]]
    assert said == ["幫我修登入", "還有這個", "順便看一下"]                 # 沒樹時收的話開樹時搬進去（首則＝原始需求），之後的話照記


def test_on_prompt_peer_and_notifications(env):
    _op("set", goal="G")
    peer = '<cross-session-message from="uds:x" from-name="claude-9f">請你上GIT</cross-session-message>'
    line = ng.on_prompt(SID, peer, 2, {})
    t = _tree()
    assert line and "T1" in line and t["peer_said"][-1]["from"] == "claude-9f" and "上GIT" in t["peer_said"][-1]["text"]
    assert all("上GIT" not in s["text"] for s in t["user_said"])
    assert ng.on_prompt(SID, "<task-notification>agent done</task-notification>", 3, {}) is None
    assert len(_tree()["user_said"]) == 0 and _doc()["user_msgs"] == 0


def test_on_prompt_hint_after_reconcile_once(env):
    _op("set", goal="G")
    _op("reconcile", items=[{"id": "T1", "status": "none", "followup": "f"}], turn=2)
    first = ng.on_prompt(SID, "下一件事", 3, {})
    assert "開新樹" in first
    assert "開新樹" not in ng.on_prompt(SID, "再一件", 4, {})


def test_user_said_caps(env):
    _op("set", goal="G")
    for i in range(25):
        ng.on_prompt(SID, f"第{i}則 " + "字" * 1200, 2 + i, {})
    said = _tree()["user_said"]
    assert len(said) == ng.SAID_MAX and said[0]["text"].startswith("第0則") and said[-1]["text"].startswith("第24則")
    assert len(said[-1]["text"]) == ng.USER_CAP


def test_ups_handler_puts_goal_line_before_hub(env, monkeypatch):
    state = {"turn_seq": 4}
    outputs = []
    for name, val in (("_ensure_state", lambda sid, inp, cfg: state), ("_ups_sentinel_check_and_arm", lambda *a: None),
                      ("_ups_sentinel_clear", lambda sid: None), ("run_pre_gates", lambda *a: None),
                      ("build_context", lambda *a: None),
                      ("collect_matched_atoms", lambda *a: ([], {}, [], [], {}, [], "general", {})),
                      ("assemble_injection", lambda *a, **k: ([], {})), ("_maybe_spawn_failure_extraction", lambda *a: None),
                      ("_update_topic_tracker", lambda *a: None), ("_drain_aec_decisions", lambda *a: None),
                      ("_truncate_context_by_activation", lambda lines, *a: lines),
                      ("reconcile_injection_after_trim", lambda *a: []), ("write_state", lambda sid, s: None),
                      ("output_json", lambda d: outputs.append(d)), ("output_nothing", lambda: outputs.append(None))):
        monkeypatch.setattr(ups, name, val)
    import wg_friction
    monkeypatch.setattr(wg_friction, "record_correction", lambda *a: None)
    monkeypatch.setattr(wo, "on_prompt", lambda *a, **k: "[Guardian:OverviewHub] HUB")
    ups.handle_user_prompt_submit({"session_id": SID, "prompt": "幫我加一個匯出功能", "transcript_path": ""}, {"sync_keywords": []})
    ctx = outputs[0]["hookSpecificOutput"]["additionalContext"]
    assert ng.HINT_LINE in ctx and ctx.index(ng.HINT_LINE) < ctx.index("HUB")
    assert _doc()["said_log"][-1]["turn"] == 5                               # 這則的回合號＝turn_seq＋1


# ─── 4.2 第一層與第二層 ────────────────────────────────────────────────────

def test_edit_gate_layers(env, monkeypatch):
    proj = env["proj"]
    py = str(proj / "a.py")
    assert "need_goal(action=set" in ng.edit_gate(SID, py, {})
    assert ng.edit_gate(SID, str(proj / "README.md"), {}) is None           # 知識類不擋
    assert ng.edit_gate(SID, str(proj / "eph" / "x.py"), {}) is None        # 暫存檔不管
    assert ng.edit_gate(SID, "UNKNOWN:echo", {}) is None                    # 交給 OverviewHub
    assert ng.edit_gate(SID, py, {"overview_hub": {"need_goal": {"enabled": False}}}) is None
    with pytest.MonkeyPatch.context() as mp:                                # 只撤這兩個，不撤 env 的資料根導向
        mp.setattr(overview_hub, "KIND_KNOWLEDGE", "knowledge", raising=False)
        mp.setattr(overview_hub, "path_kind", lambda p, stop_at=None: "knowledge", raising=False)
        assert ng.edit_gate(SID, py, {}) is None                            # 部位類別是知識類 → 不擋
    _op("set", goal="G")
    assert ng.goal_path(SID).parent.parent == env["wf"]                    # 目標檔落在 tmp 資料根
    assert ng.edit_gate(SID, py, {}) is None


def test_is_code_path_union_and_shebang(env):
    proj = env["proj"]
    script = proj / "deploy"
    script.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    plain = proj / "LICENSE"
    plain.write_text("MIT", encoding="utf-8")
    assert ng.is_code_path(str(script), {}) and not ng.is_code_path(str(plain), {})
    assert ng.is_code_path(str(proj / "a.py"), {"reconcile_gate": {"code_exts": []}})      # 設定清空也拿不掉
    cfg = {"reconcile_gate": {"code_exts": [".tbl"]}}
    assert ng.is_code_path(str(proj / "x.tbl"), cfg) and ng.is_code_path(str(proj / "a.py"), cfg)
    assert ".py" in vl.reconcile_cfg({"reconcile_gate": {"code_exts": [".tbl"]}})["code_exts"]


def _ptu_run(tool, tool_input, cwd, tp, outputs, sid=SID, config=None):
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": tool, "tool_input": tool_input, "session_id": sid, "cwd": str(cwd),
                                 "transcript_path": tp}, config or {})
    return outputs[-1]


def _deny_text(out):
    hs = (out or {}).get("hookSpecificOutput", {})
    return hs.get("permissionDecisionReason") if hs.get("permissionDecision") == "deny" else None


@pytest.fixture
def hooked(env, monkeypatch):
    outputs = []

    def _out(d):
        outputs.append(d)
        raise SystemExit(0)

    def _nothing():
        outputs.append(None)
        raise SystemExit(0)
    monkeypatch.setattr(ptu, "output_json", _out)
    monkeypatch.setattr(ptu, "output_nothing", _nothing)
    tp = env["tmp"] / "t.jsonl"
    tp.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "先看"}]}}) + "\n",
                  encoding="utf-8")
    env.update(outputs=outputs, tp=str(tp))
    return env


def test_pretool_write_code_without_tree_denied_then_allowed(hooked):
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    target = str(proj / "src" / "a.py")
    deny = _deny_text(_ptu_run("Write", {"file_path": target, "content": "x"}, proj, tp, outputs))
    assert deny and deny.startswith("[NeedGoal]") and "目標樹" in deny
    deny = _deny_text(_ptu_run("Bash", {"command": f'echo x > "{target}"'}, proj, tp, outputs))
    assert deny and deny.startswith("[NeedGoal]")
    assert _deny_text(_ptu_run("Write", {"file_path": str(proj / "notes.md"), "content": "x"}, proj, tp, outputs)) is None
    off = {"overview_hub": {"enabled": False}}
    assert _deny_text(_ptu_run("Write", {"file_path": target, "content": "x"}, proj, tp, outputs, config=off))  # OverviewHub 關掉照查
    _op("set", goal="G")
    assert _deny_text(_ptu_run("Write", {"file_path": target, "content": "x"}, proj, tp, outputs)) is None


def test_pretool_move_code_dir_and_new_shebang_script_need_tree(hooked):
    """搬或複製含程式檔的目錄（目的地還不存在、看不到副檔名）、新建沒副檔名而內容以 #! 開頭的腳本：都算改程式，
    沒樹就擋；搬純文件目錄、寫沒副檔名的純文字不擋；有樹就放行。"""
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    (proj / "src" / "lib").mkdir(parents=True)
    (proj / "src" / "lib" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (proj / "docs").mkdir()
    (proj / "docs" / "a.md").write_text("# a\n", encoding="utf-8")
    shebang = {"file_path": str(proj / "deploy"), "content": "#!/bin/sh\necho hi\n"}
    for tool, cmd in (("Bash", "mv src pkg"), ("Bash", "cp -r src pkg2"), ("PowerShell", "Move-Item src pkg")):
        deny = _deny_text(_ptu_run(tool, {"command": cmd}, proj, tp, outputs))
        assert deny and deny.startswith("[NeedGoal]") and "目標樹" in deny, cmd
    deny = _deny_text(_ptu_run("Write", shebang, proj, tp, outputs))
    assert deny and deny.startswith("[NeedGoal]")
    assert _deny_text(_ptu_run("Bash", {"command": "mv docs manual"}, proj, tp, outputs)) is None
    assert _deny_text(_ptu_run("Write", {"file_path": str(proj / "NOTES"), "content": "純文字"}, proj, tp, outputs)) is None
    _op("set", goal="G")
    assert _deny_text(_ptu_run("Bash", {"command": "mv src pkg"}, proj, tp, outputs)) is None
    assert _deny_text(_ptu_run("Write", shebang, proj, tp, outputs)) is None


def _mapped_world(env):
    proj = env["proj"]
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 |\n|---|---|---|---|\n| `Game\\Battle\\` | 戰鬥 | `戰鬥導讀` | 有 |\n", encoding="utf-8")
    (proj / ".claude" / "memory" / "shared" / "戰鬥導讀.md").write_text(
        "# 戰鬥導讀\n\n## 知識\n\n- [臨] **已知病灶**：共用字典\n", encoding="utf-8")
    (proj / "Game" / "Battle").mkdir(parents=True)
    f1 = proj / "Game" / "Battle" / "A.cs"
    f1.write_text("x", encoding="utf-8")
    return str(f1)


def _say(tp, text):
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}},
                           ensure_ascii=False) + "\n")


def _read_part(f1, proj, tp):
    state = json.loads(wg_core.state_file_path(SID).read_text(encoding="utf-8"))
    wo.on_read(state, SID, "Read", {"file_path": f1}, str(proj), tp, {})
    wg_core.write_state(SID, state)


THREE = "定位｜部位：戰鬥：A.cs\n定位｜根因層：邏輯層\n定位｜前例：共用字典"


def test_fourth_line_required_checked_linked_and_reset_on_goal_change(hooked):
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    f1 = _mapped_world(hooked)
    _op("set", goal="戰鬥不卡")
    _op("add", items=[{"text": "共用字典不再被兩邊改"}])
    first = _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert first and "[NeedGoal] 目前的需求目標" in first and "T1.1" in first   # 導讀卡開頭附樹
    _read_part(f1, proj, tp)
    _say(tp, THREE)
    deny = _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert deny and "沒交第四行" in deny and "T1.1" in deny
    _say(tp, THREE + "\n定位｜目標：T9（不存在）")
    deny = _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert deny and "T9" in deny and "不在目前的樹" in deny
    _say(tp, THREE + "\n定位｜目標：<節點編號>（這一塊在目標裡的角色）")
    assert "沒交第四行" in _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))   # 照抄範本不算
    _say(tp, THREE + "\n定位｜目標：T1.1（共用字典就是這一塊）")
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)) is None
    links = _tree()["links"]["parts"]
    assert list(links.values())[0]["node"] == "T1.1"
    ng.stamp_edit(SID, f1, "", 2, {})
    assert _tree()["edits"][-1]["node"] == "T1.1"                           # 之後這個部位的改動掛到 T1.1
    r = pt._need_goal_after_tool({"turn_seq": 3, **json.loads(wg_core.state_file_path(SID).read_text(encoding="utf-8"))},
                                 SID, "mcp__workflow-guardian__need_goal",
                                 {"action": "add", "items": [{"text": "新長出的"}]}, {"tool_response": {}, "transcript_path": tp},
                                 {})
    assert r[1] is True                                                     # 目標改了 → 清定位
    state = json.loads(wg_core.state_file_path(SID).read_text(encoding="utf-8"))
    wo.on_goal_changed(state, tp, 3)
    wg_core.write_state(SID, state)
    rec = next(v for k, v in state["overview_hub"].items() if k.endswith("|戰鬥"))
    assert rec["located"] is False and "goal_node" not in rec and rec["goal_reset_turn"] == 3
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))   # 舊的那組不算，要重交
    _say(tp, THREE + "\n定位｜目標：T1.2（新長出的那條）")
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)) is None


def test_three_lines_enough_without_tree_for_non_code(hooked):
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    _mapped_world(hooked)
    doc = proj / "Game" / "Battle" / "notes.md"
    doc.write_text("x", encoding="utf-8")
    _op("set", goal="G")
    _ptu_run("Edit", {"file_path": str(doc)}, proj, tp, outputs)
    _read_part(str(doc), proj, tp)
    _say(tp, THREE)
    assert _deny_text(_ptu_run("Edit", {"file_path": str(doc)}, proj, tp, outputs)) is None   # 非程式檔不要第四行


def test_locate_groups_parse_goal_key():
    g = overview_hub.locate_groups(THREE + "\n定位｜目標：T2.1（角色）")
    assert g[-1]["目標"].startswith("T2.1")
    g = overview_hub.locate_groups(THREE + "\n# 定位｜目標：<節點編號>（這一塊在目標裡的角色）")
    assert "目標" not in g[-1]


# ─── 4.5 (f1)(f2)、Stop、commit ─────────────────────────────────────────────

def test_goal_gate_f1_every_time_f2_only_on_boundary(env):
    proj = _code_tree(env)
    r = ng.goal_gate_reason(SID, False, {})
    assert r and "(f1)" in r and "a.py" in r and "(f2)" not in r            # 不看措辭
    assert "(f2)" in ng.goal_gate_reason(SID, True, {})
    _op("update", items=[{"id": "T1.1", "status": "doing", "why": "改了 a.py 讓 a1 接近"}], turn=2)
    assert ng.goal_gate_reason(SID, False, {}) is None
    assert "還沒交完整對照" in ng.goal_gate_reason(SID, True, {})
    assert ng.goal_gate_reason(SID, True, {"overview_hub": {"need_goal": {"enabled": False}}}) is None


def test_knowledge_tree_never_blocks(env):
    proj = env["proj"]
    _op("set", goal="整理卡片")
    ng.stamp_edit(SID, str(proj / "a.md"), "", 2, {})
    assert ng.goal_gate_reason(SID, True, {}) is None and ng.commit_gate(SID, {}) is None
    assert ng.snapshot_for_report(SID) is None


def test_stop_verify_gates_merges_goal_only_for_main_session(env):
    _code_tree(env)
    off = {"enabled": False}
    state = {"turn_seq": 3}
    reason, report, kind, _ = st._verify_gates(state, SID, 3, "好了", None, "", [], off, off, {}, False,
                                               goal=True, goal_cfg={})
    assert reason and "(f1)" in reason and kind == "reconcile"
    reason, _, kind, _ = st._verify_gates(state, SID, 3, "全部完成。", None, "", [], off, off, {}, False,
                                          goal=True, goal_cfg={})
    assert "(f2)" in reason                                                 # 宣告完成＝交付邊界
    reason, _, kind, _ = st._verify_gates(state, f"{SID}#agent:x", 3, "全部完成。", None, "", [], off, off, {}, False)
    assert reason is None                                                   # 子代理、裁判不傳 goal


def test_stop_handle_blocks_with_f1_under_reconcile_budget(env, monkeypatch, capsys):
    _code_tree(env)
    state = {"turn_seq": 3, "session": {"id": SID, "cwd": str(env["proj"])}, "modified_files": [], "turn_open": True}
    for name, val in (("_ensure_state", lambda *a, **k: state), ("_find_session_transcript", lambda *a, **k: None),
                      ("get_last_assistant_text", lambda *a, **k: "好"), ("token_warn_payload", lambda *a, **k: ""),
                      ("write_state", lambda *a, **k: None), ("append_guard_log", lambda *a, **k: None)):
        monkeypatch.setattr(st, name, val)
    with pytest.raises(SystemExit):
        st.handle_stop({"session_id": SID, "last_assistant_message": "這輪先到這。"}, {"reconcile_gate": {}, "measure_gate": {}})
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out.get("decision") == "block" and "(f1)" in out.get("reason", "")
    assert state["reconcile_gate_turn"][SID]["count"] == 1                  # 吃寫碼查核同一個預算


def _stop_env(env, monkeypatch, state):
    for name, val in (("_ensure_state", lambda *a, **k: state), ("_find_session_transcript", lambda *a, **k: None),
                      ("get_last_assistant_text", lambda *a, **k: "好"), ("token_warn_payload", lambda *a, **k: ""),
                      ("write_state", lambda *a, **k: None), ("append_guard_log", lambda *a, **k: None)):
        monkeypatch.setattr(st, name, val)


def test_stop_budget_exhausts_to_pending_and_clears_after_update(env, monkeypatch, capsys):
    from wg_release import RELEASE_TAG, pending_of
    _code_tree(env)
    state = {"turn_seq": 3, "turn_prompts_seq": 3, "session": {"id": SID, "cwd": str(env["proj"])}, "modified_files": []}
    _stop_env(env, monkeypatch, state)
    reasons = []
    for _ in range(3):
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": SID, "last_assistant_message": "這輪先到這。"}, {})
        reasons.append(json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason"])
    assert all("(f1)" in r for r in reasons)
    assert pending_of(state, SID, "reconcile") is not None                  # 擋滿：記 pending、改問使用者
    assert RELEASE_TAG in reasons[-1] or "沒有人能回答" in reasons[-1] or "無法互動" in reasons[-1]
    _op("update", items=[{"id": "T1", "status": "doing", "why": "a.py 讓 A 更接近"}], turn=3)
    try:
        st.handle_stop({"session_id": SID, "last_assistant_message": "這輪先到這。"}, {})
    except SystemExit:
        pass
    assert pending_of(state, SID, "reconcile") is None                      # 原因真的消失 → 清 pending


def test_subagent_stop_does_not_run_goal_check(env, monkeypatch, capsys):
    proj = _code_tree(env)
    state = {"turn_seq": 3, "session": {"id": SID, "cwd": str(proj)}, "agent_modified_files": {
        "ag1": [{"path": str(proj / "a.py"), "session_id": SID, "turn_seq": 3, "last_turn_seq": 3, "count": 1}]}}
    monkeypatch.setattr(st, "read_state", lambda sid: state)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda *a, **k: None)
    try:
        st.handle_subagent_stop({"session_id": SID, "agent_id": "ag1", "last_assistant_message": "全部完成。"}, {})
    except SystemExit:
        pass
    out = capsys.readouterr().out
    assert "(f1)" not in out and "(f2)" not in out


def test_commit_gate_and_pretool_commit_denied(hooked, monkeypatch):
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    _code_tree(hooked)
    assert "(f1)" in ng.commit_gate(SID, {})
    monkeypatch.setattr(ptu, "check_git_commit_order", lambda *a, **k: None)
    monkeypatch.setattr(ptu, "check_git_privacy", lambda *a, **k: None)
    deny = _deny_text(_ptu_run("Bash", {"command": 'git commit -m "x"'}, proj, tp, outputs))
    assert deny and deny.startswith("[NeedGoal] commit 前") and "(f2)" in deny
    assert _deny_text(_ptu_run("Bash", {"command": "git log -1"}, proj, tp, outputs)) is None


def test_gate_messages_point_to_reload_when_tool_missing(env):
    """裁定 #23：合併前就開著的分頁 MCP 是舊的、叫不到 need_goal，擋下訊息只說「先用 need_goal」會走不下去；
    改檔閘、commit 閘（含目標檔損毀）的擋下訊息都要指路：Reload Window 或開新 session。"""
    proj = env["proj"]
    deny = ng.edit_gate(SID, str(proj / "a.py"), {})
    assert "還沒有目標樹" in deny and "Reload Window" in deny                      # 原因要對，不只指路句在
    _code_tree(env)
    deny = ng.commit_gate(SID, {})
    assert "目標對照沒過" in deny and "Reload Window" in deny
    ng.goal_path(SID).write_text("{not json", encoding="utf-8")
    for deny in (ng.edit_gate(SID, str(proj / "a.py"), {}), ng.commit_gate(SID, {})):
        assert "目標檔損毀" in deny and "Reload Window" in deny


def test_commit_gate_ignores_commit_examples_inside_heredoc(hooked, monkeypatch):
    """heredoc 本文裡的 git／svn commit 是文件內容（操作說明、派工單），不觸發 commit_gate；heredoc 結束後真的執行的
    commit 照擋。與 CommitOrder 共用同一支判定。"""
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    _code_tree(hooked)
    monkeypatch.setattr(ptu, "check_git_commit_order", lambda *a, **k: None)
    monkeypatch.setattr(ptu, "check_git_privacy", lambda *a, **k: None)
    doc = "cat > guide.md <<'EOF'\n步驟：\ngit commit -m example\nsvn commit -m example\nEOF"
    assert _deny_text(_ptu_run("Bash", {"command": doc}, proj, tp, outputs)) is None
    deny = _deny_text(_ptu_run("Bash", {"command": doc + "\ngit commit -m real"}, proj, tp, outputs))
    assert deny and deny.startswith("[NeedGoal] commit 前")


# ─── 收尾檢核、審查材料、續接單、壓縮重送 ─────────────────────────────────────

def test_aec_report_gets_snapshot(env, monkeypatch, capsys):
    _code_tree(env)
    state = {"turn_seq": 7}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", env["wf"])
    monkeypatch.setattr(pt, "_hud_alive", lambda *a, **k: (False, {"reason": "test"}))
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_spawn_hud_edge", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"session_id": SID, "tool_name": "mcp__workflow-guardian__anti_evasion_report",
                                 "tool_input": {k: "無" for k in "abcdefgi"} | {"h": "可關閉"}, "tool_response": {}},
                                {"docdrift": {"enabled": False}, "aec": {}})
    snap = state["anti_evasion_report"]["need_goal"]
    assert snap["tree"] == "T1" and snap["reconcile"]["ok"] is False and snap["owed"] == 1
    data = json.loads((env["wf"] / "aec-report" / f"{SID}-t7.json").read_text(encoding="utf-8"))
    assert data["need_goal"]["nodes"][0]["id"] == "T1"


def test_review_material_three_sections_within_limit(env):
    ng.on_prompt(SID, "原話" * 400, 1, {})
    _op("set", goal="G")
    ng.on_prompt(SID, '<cross-session-message from-name="claude-aa">同伴的話</cross-session-message>', 2, {})
    m = ng.review_material(SID)
    assert m.index("【使用者原話（權威）】") < m.index("【同伴轉述") < m.index("【目標樹（AI 自己的解讀")
    assert "claude-aa" in m and len(m) <= ng.REVIEW_CHARS
    import codex_companion
    assert codex_companion._review_goal(SID, "第一則") == m
    assert codex_companion._review_goal("no-tree-sid", "第一則") == "第一則"


def test_handoff_roundtrip_import_remaps_and_marks_prior(env):
    proj = _code_tree(env)
    ng.on_prompt(SID, "要快", 2, {})
    ng.stamp_receipts(SID, _receipt_state(_rcpt(3)), 2)
    rno = f"R{_doc()['receipts'][-1]['seq']}"
    _op("reconcile", turn=3, cwd=str(proj), items=[
        {"id": "T1", "status": "partial", "evidence": [{"kind": "receipt", "ref": rno, "level": "measured"}], "followup": "f"},
        {"id": "T1.1", "status": "done", "evidence": [{"kind": "receipt", "ref": rno, "level": "measured"}]},
        {"id": "T1.2", "status": "none", "followup": "還沒做"}])
    block = ng.handoff_block(SID)
    assert block.startswith("## 【需求目標樹】") and "need-goal:begin" in block and "要快" in block
    new_sid = "sess-next"
    _op("set", goal="別的事", sid=new_sid)                                   # 新 session 先有一棵 T1
    res = ng.import_handoff(new_sid, block, str(proj / "next-phase-x.md"), 1)
    assert res["imported"] == ["T2"] and res["map"] == {"T1": "T2"}
    t = ng.active_tree(ng.load(new_sid))
    assert t["id"] == "T2" and sorted(t["nodes"]) == ["T2", "T2.1", "T2.2"] and t["nodes"]["T2.1"]["parent"] == "T2"
    assert all(e["prior"] for e in t["nodes"]["T2.1"]["evidence"]) and t["user_said"][0]["prior"]
    assert t["imported_from"]["map"]["T1.1"] == "T2.1" and t["last_reconcile"] is None and t["edits"] == []
    assert "已匯入過" in ng.import_handoff(new_sid, block, str(proj / "next-phase-x.md"), 1)["skipped"]
    assert ng.import_handoff(SID, block, "p", 4).get("own") is True          # 自己匯出的不重複匯入
    probs = ng._problems(ng.load(new_sid), t, {}, "", None)
    assert any("前一個 session 的證據不算" in p for p in probs)


def test_post_tool_read_handoff_imports_or_hints(env):
    proj = _code_tree(env)
    block = ng.handoff_block(SID)
    staging = proj / ".claude" / "memory" / "_staging"
    staging.mkdir(parents=True)
    f = staging / "next-phase-x.md"
    f.write_text("# 續接\n\n" + block, encoding="utf-8")
    inp = {"tool_response": {}, "transcript_path": ""}
    ctx, _ = pt._need_goal_after_tool({"turn_seq": 1}, "sess-new", "Read", {"file_path": str(f)}, inp, {})
    assert ctx and "從續接單匯入需求目標樹" in ctx and ng.active_tree(ng.load("sess-new"))["id"] == "T1"
    ctx, _ = pt._need_goal_after_tool({"turn_seq": 2}, "sess-new2", "Read", {"file_path": str(f)}, inp, {})
    assert ng.load("sess-new2")["trees"]
    _op("set", goal="自己的", sid="sess-busy")
    ctx, _ = pt._need_goal_after_tool({"turn_seq": 2}, "sess-busy", "Read", {"file_path": str(f)}, inp, {})
    assert "import_from" in ctx
    ctx, _ = pt._need_goal_after_tool({"turn_seq": 2}, SID, "Read", {"file_path": str(f)}, inp, {})
    assert ctx is None                                                      # 自己匯出的：不提示


def test_recovery_blob_independent_of_overview(env):
    ng.on_prompt(SID, "讓匯出變快", 1, {})
    _op("set", goal="匯出變快")
    _op("set", goal="另一件", new_task=True, turn=2)
    blob = ng.recovery_blob(SID, 600)
    assert blob.startswith("【需求目標樹】") and "另一件" in blob and "其他未結束的樹" in blob and len(blob) <= 600
    assert ng.recovery_blob("nobody", 600) == ""


# ─── post_tool_use 接線、hub_config ─────────────────────────────────────────

def test_post_tool_use_need_goal_branch_applies_and_skips_errors(env, monkeypatch, capsys):
    state = {"turn_seq": 2}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_run_companion_hooks", lambda *a: ([], []))
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"session_id": SID, "tool_name": "mcp__workflow-guardian__need_goal",
                                 "tool_input": {"action": "set", "goal": "G"}, "tool_response": {}},
                                {"docdrift": {"enabled": False}})
    ctx = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert "[NeedGoal] set 收下" in ctx and "T1" in ctx
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"session_id": SID, "tool_name": "mcp__workflow-guardian__need_goal",
                                 "tool_input": {"action": "add", "items": [{"text": "x"}]},
                                 "tool_response": {"isError": True, "content": [{"type": "text", "text": "拒收"}]}},
                                {"docdrift": {"enabled": False}})
    assert len(_tree()["nodes"]) == 1                                        # MCP 拒收的不套用


def test_post_tool_use_stamps_edits_and_receipts(env):
    _op("set", goal="G")
    proj = env["proj"]
    pt._need_goal_after_tool({"turn_seq": 2}, SID, "Write", {"file_path": str(proj / "a.py")}, {}, {})
    pt._need_goal_after_tool({"turn_seq": 2}, SID, "Bash", {"command": f'echo x > "{proj / "b.py"}"'},
                             {"cwd": str(proj)}, {})
    state = _receipt_state(_rcpt(11))
    pt._need_goal_after_tool(state | {"turn_seq": 2}, SID, "Bash", {"command": "pytest -q"}, {"cwd": str(proj)}, {})
    t = _tree()
    assert [Path(e["path"]).name for e in t["edits"]] == ["a.py", "b.py"] and len(_doc()["receipts"]) == 1


def test_hub_config_need_goal_section():
    c = hub_config.merge_hub_cfg({"overview_hub": {"need_goal": {"render_chars": 800}}}, None, None)
    assert c["need_goal"] == {"enabled": True, "scope_growth_dirs": 3, "render_chars": 800} and not c["_errors"]
    c = hub_config.merge_hub_cfg({"overview_hub": {"need_goal": {"enabled": "yes", "bogus": 1}}}, None, None)
    assert any("need_goal.enabled" in e for e in c["_errors"]) and any("bogus" in e for e in c["_errors"])


def test_unredirected_tests_never_write_data_root(monkeypatch):
    """跑真 hook 入口但沒把資料根導走的測試（例：verify_ups_overview_wiring）：目標檔落到系統暫存目錄，不進資料根。"""
    import tempfile
    assert ng.goal_dir() == Path(tempfile.gettempdir()) / "wg-test-need-goal"
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert ng.goal_dir() == Path(wg_core.WORKFLOW_DIR) / "need-goal"


def test_render_compact_respects_limit(env):
    _op("set", goal="G")
    _op("add", items=[{"text": "子目標" * 30} for _ in range(30)])
    text = ng.render(_tree(), "compact", chars=400)
    assert len(text) <= 520 and "其餘" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
