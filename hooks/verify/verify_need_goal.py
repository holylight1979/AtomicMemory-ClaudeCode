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
import re
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
    assert not any("why" in x for x in _op("update", items=[{"id": "T1", "status": "done"}])["rejected"])  # why 選填（WHY_OPTIONAL）
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


def test_set_rewrite_without_why_new_task_opens_new_tree(env):
    """WHY_OPTIONAL（派工 003 第 13 刀）：改寫樹根不附 why 也收；有附的照樣記進 history。"""
    _op("set", goal="A")
    r = _op("set", goal="B")
    assert r["ok"] and _tree()["nodes"]["T1"]["text"] == "B" and _tree()["goal_rev"] == 2, r
    r = _op("set", goal="B2", why="使用者改口要 B2")
    assert r["ok"] and _tree()["nodes"]["T1"]["history"][-1]["why"] == "使用者改口要 B2"
    r = _op("set", goal="C", new_task=True, why="使用者換成另一件事 C", turn=3)
    assert r["tree"] == "T2" and _doc()["active"] == "T2" and _doc()["trees"]["T1"]["status"] == "doing"


def test_t13_new_task_while_doing_without_why_lists_old_nodes(env):
    """B5 q3 改成提醒（WHY_OPTIONAL）：目前的樹還在進行中時換題不附 why 也收；收下時列出舊樹沒結束的節點，
    並提醒「是糾正或補充就改回舊樹」。update 不附 why 也收。"""
    _op("set", goal="A")
    _op("add", items=[{"text": "a1"}, {"text": "a2"}])
    r = _op("set", goal="B", new_task=True, turn=2)
    assert r["ok"] and r["tree"] == "T2" and "舊樹 T1 還有 3 個沒結束的節點" in r["text"] and "T1.1" in r["text"], r["text"]
    assert "改回 T1" in r["text"], r["text"]
    assert _doc()["trees"]["T1"]["status"] == "doing"                        # 舊樹不自動收
    u = _op("update", turn=2, items=[{"id": "T1.1", "status": "dropped"}])
    assert u["ok"] and _doc()["trees"]["T1"]["nodes"]["T1.1"]["status"] == "dropped", u
    _op("reconcile", turn=3, items=[{"id": "T2", "status": "none", "followup": "下次做"}])
    assert _tree()["status"] == "reconciled"
    r = _op("set", goal="C", new_task=True, turn=4)                         # 對照完再換題：不列舊樹
    assert r["ok"] and r["tree"] == "T3" and "舊樹" not in r["text"]


def test_t13_new_tree_note_asks_for_subgoals_and_whole_need(env):
    """B5 缺口①：AI 懂了子目標，樹上卻只有樹根；q5：一句話兩件事只寫進「這回合先做的」那件。開樹收下時送一次：樹根寫整個需求、
    看得出的子目標現在就 add。第一則提示也寫明寫整個需求。"""
    r = _op("set", goal="登入要能用")
    assert r["ok"] and ng.SUBGOAL_LINE in r["text"] and "不只這回合先做的那段" in ng.SUBGOAL_LINE
    assert "不只這回合先做的那段" in ng.HINT_LINE
    assert ng.SUBGOAL_LINE not in _op("set", goal="登入與註冊都要能用", why="使用者補充註冊")["text"]   # 改寫樹根不重送


def test_t13_on_prompt_offers_amend_and_correct_paths_not_only_new_task(env):
    """每則訊息附的樹根那一行：原本只寫「這則若換題用 new_task」，等於只指開新樹那條路。改成補充 → add、糾正 → 改這棵樹不開新樹、
    換成另一件事才 new_task 附 why，三條路並列。"""
    _op("set", goal="登入要能用", turn=1)
    line = ng.on_prompt(SID, "不對，是要記住登入狀態", 2, {})
    assert ng.TREE_PATHS in line and "不開新樹" in line and "add" in line and "new_task=true" in line, line


def test_t110_handout_check_user_words_before_plan(env):
    """T1.10（原設計者 10-20）：交出前一問只對最新計畫，計畫偏了會跟著一起偏。改成先對使用者原話（樹最上面那句）、再對計畫，
    對不上以原話為準並說出落差；眼前沒有樹的兩處（改計畫類文件、收尾檢核收下）把樹最上面那句附上。"""
    hc = ng.HANDOUT_CHECK
    assert "先對使用者原話" in hc and hc.index("原話") < hc.index("最新的計畫") and "以原話為準" in hc and "落差" in hc
    assert ng.handout_check_text(SID) == hc                                  # 沒有樹：只有那一問
    ng.on_prompt(SID, "設定改了要馬上生效，順便把舊設定檔相容", 1, {})
    _op("set", goal="設定改完不用重開就生效")                                # 樹根（AI 解讀）漏了「舊設定檔相容」
    ng.on_prompt(SID, "記得舊檔", 2, {})
    text = ng.handout_check_text(SID)
    assert text.startswith(hc) and "目標樹最上面那句（T1，AI 照原話寫的解讀）：「設定改完不用重開就生效」" in text, text
    assert "使用者原話（第 1 回合）：「設定改了要馬上生效，順便把舊設定檔相容」" in text            # 原話與解讀分開附，落差看得到
    assert "使用者原話（第 2 回合）：「記得舊檔」" in text


def test_t110_handout_check_text_survives_broken_tree(env, capsys):
    """目標檔是合法 JSON 但樹結構壞了（缺 id）：照送那一問、寫 stderr，不丟例外讓 PostToolUse 漏送（Codex WARN）。"""
    _op("set", goal="G")
    ng.update_locked(SID, lambda d: d["trees"]["T1"].pop("id"))
    assert ng.handout_check_text(SID) == ng.HANDOUT_CHECK
    assert "交出前一問附不了原話" in capsys.readouterr().err


def test_t13_correction_after_closed_tree_kept_when_old_tree_reopened(env):
    """Codex BLOCK：樹已結束後使用者糾正 → 那句沒進任何樹（目前的樹已結束）；照新提示改舊樹（set 改寫樹根、或 update 退回非終點）
    → 樹重新打開時要把那句掛回來，續接單才帶得走；同一則不重複掛。"""
    proj = env["proj"]
    (proj / "c.md").write_text("C\n", encoding="utf-8")
    _op("set", goal="C", cwd=str(proj))
    assert _op("reconcile", turn=1, cwd=str(proj), items=[
        {"id": "T1", "status": "done", "evidence": [{"kind": "file", "ref": "c.md", "level": "read"}]}])["ok"]
    assert _tree()["status"] == "closed"
    ng.on_prompt(SID, "不對，C 還要包含 D", 2, {})
    assert "不對，C 還要包含 D" not in [s["text"] for s in _tree()["user_said"]]      # 前置：結束的樹不收
    assert _op("set", goal="C 和 D", why="使用者糾正：還要包含 D", turn=2)["ok"]
    said = [s["text"] for s in _tree()["user_said"]]
    assert _tree()["status"] == "doing" and said.count("不對，C 還要包含 D") == 1, said
    assert "不對，C 還要包含 D" in ng.handoff_block(SID)
    ng.update_locked(SID, lambda d: d["trees"]["T1"].update(status="closed"))         # 再結束、再糾正，改走 update 退回
    ng.on_prompt(SID, "D 要先做", 3, {})
    assert _op("update", items=[{"id": "T1", "status": "doing", "why": "使用者要 D 先做"}], turn=3)["ok"]
    said = [s["text"] for s in _tree()["user_said"]]
    assert said.count("D 要先做") == 1 and said.count("不對，C 還要包含 D") == 1, said


def test_t13_imported_receipt_evidence_not_resolved_against_this_sessions_receipts(env):
    """匯入的收據證據（prior）編號是前一個 session 的：顯示時不能拿本 session 同號收據的指令去配（本 session 實遇：樹根的
    「R157（前一個 session）」顯示成本 session 剛跑的另一條指令）。本 session 自己的收據證據照舊附指令。"""
    _op("set", goal="匯出變快")
    ng.update_locked(SID, lambda d: d["trees"]["T1"]["nodes"]["T1"]["evidence"].append(
        {"kind": "receipt", "ref": "R1", "level": "measured", "covers": ["T1"], "seq": 1}))
    block = ng.handoff_block(SID)
    ng.import_handoff("sess-next", block, str(env["proj"] / "next-phase-x.md"), 1)
    ng.update_locked("sess-next", lambda d: d.setdefault("receipts", []).append(
        {"seq": 1, "turn": 1, "cmd": "python other_session_cmd.py", "verdicts": [], "exit": 0}))
    d = ng.load("sess-next")
    nodes_part = ng.render(ng.active_tree(d), "full", doc=d).split("最近收據", 1)[0]      # 收據清單本身照列，只看節點的證據
    assert "R1" in nodes_part and "（前一個 session）" in nodes_part, nodes_part         # 前置：舊證據有印出來
    assert "other_session_cmd" not in nodes_part, nodes_part
    ng.update_locked("sess-next", lambda d: d["trees"][d["active"]]["nodes"][d["active"]]["evidence"].append(
        {"kind": "receipt", "ref": "R1", "level": "measured", "covers": [d["active"]], "seq": 2}))
    d = ng.load("sess-next")
    assert "other_session_cmd" in ng.render(ng.active_tree(d), "full", doc=d).split("最近收據", 1)[0]   # 本 session 的收據照舊附指令


def test_t13_import_attaches_this_sessions_words_before_import(env):
    """換 session 接續：開工句（本 session 第一則）在匯入前送到、當時沒有樹，匯入後要接在前一個 session 的原話後面；
    不接的話接手 session 的樹只有舊原話，交出前一問對不到這一輪的要求（本 session 開頭實測 said_log 第 1 回合 attached=False）。"""
    ng.on_prompt(SID, "讓匯出變快", 1, {})
    _op("set", goal="匯出變快")
    block = ng.handoff_block(SID)
    assert ng.on_prompt("sess-next", "你是推進 session，這輪做匯出快取", 1, {}) == ng.HINT_LINE
    assert ng.load("sess-next")["said_log"][0]["attached"] is False
    res = ng.import_handoff("sess-next", block, str(env["proj"] / "next-phase-x.md"), 1)
    d = ng.load("sess-next")
    said = d["trees"][d["active"]]["user_said"]
    assert res["imported"] and [s["text"] for s in said] == ["讓匯出變快", "你是推進 session，這輪做匯出快取"], said
    assert said[0].get("prior") and not said[1].get("prior")
    assert d["said_log"][0]["attached"] is True


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


def test_reconcile_done_node_can_carry_same_class(env):
    """收尾完整對照：達成的節點可附 same_class（同類別處：找到的位置，或為什麼沒有）；存進節點、完整顯示看得到。
    沒附的達成節點只提醒一句、不擋；same_class 不是字串 → 拒收。舊碼不收這個欄位（紅）。"""
    proj = env["proj"]
    (proj / "x.md").write_text("x\n", encoding="utf-8")
    _op("set", goal="A", cwd=str(proj))
    _op("add", items=[{"text": "b"}])
    r = _op("reconcile", turn=2, cwd=str(proj), items=[
        {"id": "T1", "status": "done", "evidence": [{"kind": "file", "ref": "x.md", "level": "read"}],
         "same_class": "wg_harvest 的收據判定也用檔名對應"},
        {"id": "T1.1", "status": "done", "evidence": [{"kind": "file", "ref": "x.md", "level": "read"}]}])
    assert r["ok"], r["rejected"]
    assert _tree()["nodes"]["T1"]["same_class"] == "wg_harvest 的收據判定也用檔名對應"
    assert "同類別處：wg_harvest" in ng.render(_tree(), "full")
    assert "T1.1" in r["text"] and "same_class" in r["text"], r["text"]                 # 沒附的達成節點：提醒一句
    bad = _op("reconcile", turn=3, cwd=str(proj), items=[{"id": "T1", "status": "done", "same_class": ["x"]}])
    assert not bad["ok"] and any("same_class" in x for x in bad["rejected"]), bad


def test_reconcile_reply_asks_handout_check_before_giving_plans(env):
    """完整對照收下的回應是交出計畫、開工句、清單之前的最後一個點：附「還對得上最新計畫嗎、剛改的影響哪些已給出的內容」。"""
    proj = env["proj"]
    _op("set", goal="A", cwd=str(proj))
    r = _op("reconcile", turn=2, cwd=str(proj), items=[{"id": "T1", "status": "none", "followup": "下次補"}])
    assert r["ok"] and ng.HANDOUT_CHECK in r["text"], r["text"]


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
    _op("set", goal="B", new_task=True, why="換題", turn=3)                 # 換題：T2 成為目前的樹
    assert ng.goal_gate_reason(SID, False, {}) is None                       # T1 欠的由程式記進度（PROGRESS_LINE_BY_PROGRAM）
    assert _doc()["trees"]["T1"]["nodes"]["T1"]["history"][-1]["by"] == "program"
    r = _op("update", items=[{"id": "T1", "status": "doing", "why": "a.py 的改動讓 A 更接近"}], turn=3)
    assert r["ok"] and r["tree"] == "T1"                                     # AI 自己交舊樹的進度照收
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
    assert ng.HANDOUT_CHECK in line                                         # 純問答回合交開工句、清單前也收得到
    assert "寫或整併文件" in ng.HINT_LINE                                     # 第一則提醒寫明文件類也算要動手
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
    after = "若這則是新的要動手的需求"                                     # 對照完那句；每則都帶的三條路也提開新樹，不能拿「開新樹」當判別字
    assert after in first
    assert after not in ng.on_prompt(SID, "再一件", 4, {})


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
                      ("_update_topic_tracker", lambda *a: None),
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
# 有目標樹時的四行：根因層要兩個候選＋選擇理由（LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES）
THREE2 = "定位｜部位：戰鬥：A.cs\n定位｜根因層：候選 A 邏輯層；候選 B 存檔時序；選 A 因為字典只在邏輯層被寫\n定位｜前例：共用字典"
# 有目標樹時四行之後的第五行：批判與舉一反三（LOCATE_LINES_NEED_CRITIQUE）
CRIT = "\n定位｜批判：不合理，因為字典兩邊都寫，更好的做法是只留邏輯層一個寫入點；同類還可能在哪：存檔流程也兩邊寫"


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
    _say(tp, THREE2 + "\n定位｜目標：T1.1（共用字典就是這一塊）" + CRIT)
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
    _say(tp, THREE2 + "\n定位｜目標：T1.2（新長出的那條）" + CRIT)
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)) is None


def test_three_lines_enough_without_tree_for_non_code(hooked):
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    _mapped_world(hooked)
    doc = proj / "Game" / "Battle" / "notes.md"
    doc.write_text("x", encoding="utf-8")
    _op("set", goal="G")
    _say(tp, "動資料檔｜Game/Battle/notes.md：需求要補戰鬥筆記；可見影響：筆記多一段")   # 既有 .md 先過改資料檔閘，這支只驗 OverviewHub
    _ptu_run("Edit", {"file_path": str(doc)}, proj, tp, outputs)
    _read_part(str(doc), proj, tp)
    _say(tp, THREE)
    assert _deny_text(_ptu_run("Edit", {"file_path": str(doc)}, proj, tp, outputs)) is None   # 非程式檔不要第四行


def test_locate_groups_parse_goal_key():
    g = overview_hub.locate_groups(THREE + "\n定位｜目標：T2.1（角色）")
    assert g[-1]["目標"].startswith("T2.1")
    g = overview_hub.locate_groups(THREE + "\n# 定位｜目標：<節點編號>（這一塊在目標裡的角色）")
    assert "目標" not in g[-1]


# ─── C-G0：定位四行要說角色與兩個根因候選；收尾查改到的部位都掛到目標 ─────────────

def test_004_locate_example_is_a_suggestion_and_chained_nodes_pass(hooked):
    """第三跑 B-1：擋訊息附的範例標成「建議寫法」（內容到了就算、句子順序不限）；第四行「T1.1/T1.2（角色）」、第五行把哪裡不合理
    寫在前面，端到端放行。"""
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    f1 = _mapped_world(hooked)
    _op("set", goal="戰鬥不卡")
    _op("add", items=[{"text": "共用字典不再被兩邊改"}, {"text": "存檔不壞"}])
    _ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)                  # 第一次碰部位：注入導讀卡
    _read_part(f1, proj, tp)
    _say(tp, THREE + "\n定位｜目標：T1.1")
    deny = _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert deny and "建議寫法（只是範例" in deny and "照這個樣子" not in deny, deny
    _say(tp, THREE2 + "\n定位｜目標：T1.1/T1.2（共用字典的唯一寫入點、順帶顧存檔）"
         "\n定位｜批判：字典兩邊都寫不合理，更好的做法是只留邏輯層寫；同類還可能在哪：存檔快取也有同樣的雙寫")
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)) is None


def test_cg0_locate_four_lines_need_role_and_two_candidates(hooked):
    """LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES：第四行沒角色 → 擋；根因層只一個候選 → 擋；擋訊息印規則名、缺哪一項、
    範例四行照抄就過；放行後部位掛到節點。"""
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    f1 = _mapped_world(hooked)
    _op("set", goal="戰鬥不卡")
    _op("add", items=[{"text": "共用字典不再被兩邊改"}])
    _ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)                  # 第一次碰部位：注入導讀卡
    _read_part(f1, proj, tp)
    _say(tp, THREE2 + "\n定位｜目標：T1.1")
    deny = _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert deny and "LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES" in deny and "角色" in deny
    _say(tp, THREE + "\n定位｜目標：T1.1（共用字典的唯一寫入點）")
    deny = _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert deny and "LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES" in deny and "只辨識出 0 個" in deny
    assert "還沒" not in deny.split("\n判準卡（")[0]                          # 只擋內容，不是說沒交（後面接的判準卡內文不算）
    example = [ln.strip() for ln in deny.splitlines() if ln.strip().startswith("定位｜")]
    assert len(example) == 5 and example[3].startswith("定位｜目標：T1.1（") and example[4].startswith("定位｜批判："), example
    _say(tp, "\n".join(example))                                            # 範例照抄（角括號佔位沒換）不算交（codex BLOCK）
    deny = _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert deny and "LOCATE_LINES_NO_EXAMPLE_PLACEHOLDER" in deny, deny
    _say(tp, "\n".join(re.sub(r"<[^<>]*>", "共用字典只在邏輯層寫", ln) for ln in example))   # 佔位換成自己的判斷就過
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)) is None
    assert list(_tree()["links"]["parts"].values())[0]["node"] == "T1.1"


def test_cg1_locate_needs_critique_line(hooked):
    """LOCATE_LINES_NEED_CRITIQUE：有目標樹改寫碼部位，定位四行之後要第五行「批判」；沒交 → 擋（規則名、缺哪一項）；
    照抄範本 → 當沒交；判合理沒理由 → 擋；結構對 → 放行並掛節點。舊碼不認「批判」這個鍵，四行就放（紅）。"""
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    f1 = _mapped_world(hooked)
    _op("set", goal="戰鬥不卡")
    _op("add", items=[{"text": "共用字典不再被兩邊改"}])
    _ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)
    _read_part(f1, proj, tp)
    four = THREE2 + "\n定位｜目標：T1.1（共用字典的唯一寫入點）"
    _say(tp, four)
    deny = _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert deny and "LOCATE_LINES_NEED_CRITIQUE" in deny and "沒交第五行" in deny, deny
    _say(tp, four + "\n定位｜批判：" + overview_hub.CRITIQUE_TEMPLATE)
    deny = _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert deny and "沒交第五行" in deny                                     # 照抄範本不算交
    _say(tp, four + "\n定位｜批判：合理；同類還可能在哪：存檔流程")
    deny = _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert deny and "LOCATE_LINES_NEED_CRITIQUE" in deny and "沒寫理由" in deny
    _say(tp, four + CRIT)
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)) is None
    assert list(_tree()["links"]["parts"].values())[0]["node"] == "T1.1"


def test_cg0_one_candidate_with_second_absent_reason_passes(hooked):
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    f1 = _mapped_world(hooked)
    _op("set", goal="戰鬥不卡")
    _ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)
    _read_part(f1, proj, tp)
    _say(tp, "定位｜部位：戰鬥：A.cs\n定位｜根因層：根因在邏輯層；第二個不存在，因為字典只有這一處寫入\n定位｜前例：共用字典\n"
             "定位｜目標：T1（戰鬥邏輯是卡頓的源頭）" + CRIT)
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)) is None


def _two_part_world(env):
    """兩個寫碼部位（戰鬥、介面）＋一個知識類部位（文件，放 .py 也不算程式）。回 {子目錄: 檔路徑}。"""
    proj = env["proj"]
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
        "| `Game\\Battle\\` | 戰鬥 | `戰鬥導讀` | 有 | code |\n"
        "| `Game\\UI\\` | 介面 | `介面導讀` | 有 | code |\n"
        "| `Game\\Docs\\` | 文件 | 無 | 無 | knowledge |\n", encoding="utf-8")
    for name in ("戰鬥導讀", "介面導讀"):
        (proj / ".claude" / "memory" / "shared" / f"{name}.md").write_text(
            f"# {name}\n\n## 知識\n\n- [臨] **已知病灶**：x\n", encoding="utf-8")
    files = {}
    for sub, fn in (("Battle", "A.cs"), ("UI", "B.cs"), ("Docs", "gen.py")):
        (proj / "Game" / sub).mkdir(parents=True, exist_ok=True)
        files[sub] = str(proj / "Game" / sub / fn)
        Path(files[sub]).write_text("x", encoding="utf-8")
    return files


FOUR_UI = ("定位｜部位：介面：B.cs\n定位｜根因層：候選 A 刷新時機；候選 B 事件沒解掛；選 A 因為只在戰鬥結束時刷\n"
           "定位｜前例：無\n定位｜目標：T1.2（介面刷新跟著字典變）" + CRIT)


def test_cg0_reconcile_edited_part_needs_goal_node(hooked):
    """EDITED_PART_NEEDS_GOAL_NODE：改了兩個部位、只有一個交過定位第四行 → 交付邊界與 commit 前擋，列沒掛的部位與檔、指路；
    知識類部位不列；補交四行後收尾時補掛、放行。"""
    import wg_release_rules as rr
    proj, tp = hooked["proj"], hooked["tp"]
    files = _two_part_world(hooked)
    _op("set", goal="戰鬥不卡", cwd=str(proj))
    _op("add", items=[{"text": "共用字典不再被兩邊改"}, {"text": "介面跟著刷新"}])
    ng.link_part(SID, ng._hub_key_of(files["Battle"]), "T1.1", 2)          # 戰鬥交過定位第四行
    for k in ("Battle", "UI", "Docs"):
        ng.stamp_edit(SID, files[k], "", 2, {})
    r = ng.goal_gate_reason(SID, True, {})
    f3 = r.split("(f3)", 1)[1] if r and "(f3)" in r else ""
    assert "EDITED_PART_NEEDS_GOAL_NODE" in f3 and "介面：" in f3 and "B.cs" in f3 and "沒掛目標" in f3, r
    assert "戰鬥：" not in f3 and "gen.py" not in r                          # 掛過的、知識類部位不列
    assert "need_goal" in f3 and "定位四行" in f3                             # 指路
    assert "f3" in rr.parse_hits(r)                                          # 擋次預算單獨計次
    assert "(f3)" not in (ng.goal_gate_reason(SID, False, {}) or "")         # 只在交付邊界
    assert "(f3)" in ng.commit_gate(SID, {})
    _say(tp, FOUR_UI)                                                        # 補交介面的定位四行
    r = ng.goal_gate_reason(SID, True, {}, state={}, transcript_path=tp)
    assert "(f3)" not in (r or "")
    assert _tree()["links"]["parts"][ng._hub_key_of(files["UI"])]["node"] == "T1.2"
    assert "(f3)" not in (ng.commit_gate(SID, {}) or "")


def test_cg0_relink_needs_valid_four_lines(hooked):
    """補掛也照定位四行的判法：沒角色、指到不存在的節點都不算掛上。"""
    proj, tp = hooked["proj"], hooked["tp"]
    files = _two_part_world(hooked)
    _op("set", goal="G", cwd=str(proj))
    _op("add", items=[{"text": "a"}, {"text": "介面跟著刷新"}])
    ng.stamp_edit(SID, files["UI"], "", 2, {})
    _say(tp, FOUR_UI.replace("T1.2（介面刷新跟著字典變）", "T1.2"))
    assert "(f3)" in ng.goal_gate_reason(SID, True, {}, state={}, transcript_path=tp)
    _say(tp, FOUR_UI.replace("T1.2", "T9"))
    assert "(f3)" in ng.goal_gate_reason(SID, True, {}, state={}, transcript_path=tp)


def test_cg0_relink_overlapping_part_names_only_links_the_named_one(hooked):
    """部位名互相包含（UI、UI 設定）：補交「UI 設定」的四行只掛 UI 設定，UI 照擋（codex BLOCK）。"""
    proj, tp = hooked["proj"], hooked["tp"]
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
        "| `Game\\UI\\Settings\\` | UI 設定 | 無 | 無 |\n| `Game\\UI\\` | UI | 無 | 無 |\n", encoding="utf-8")
    (proj / "Game" / "UI" / "Settings").mkdir(parents=True)
    ui, st_ = proj / "Game" / "UI" / "View.cs", proj / "Game" / "UI" / "Settings" / "S.cs"
    for p in (ui, st_):
        p.write_text("x", encoding="utf-8")
    _op("set", goal="G", cwd=str(proj))
    _op("add", items=[{"text": "設定頁存得進去"}])
    ng.stamp_edit(SID, str(ui), "", 2, {})
    ng.stamp_edit(SID, str(st_), "", 2, {})
    _say(tp, "定位｜部位：UI 設定——S.cs\n定位｜根因層：候選 A 存檔時機；候選 B 欄位對應；選 A 因為按了沒反應\n"
             "定位｜前例：無\n定位｜目標：T1.1（設定頁的存檔入口）" + CRIT)
    r = ng.goal_gate_reason(SID, True, {}, state={}, transcript_path=tp)
    f3 = r.split("(f3)", 1)[1] if r and "(f3)" in r else ""
    assert "UI：" in f3 and "View.cs" in f3 and "S.cs" not in f3, r
    assert overview_hub.locate_values("定位｜部位：UI 設定\n定位｜根因層：x\n定位｜前例：無", "UI", exclude=["UI 設定"]) is None


def test_cg0_dropped_node_unlinks_part(hooked):
    """部位掛的節點後來放棄 → 這個部位的改動等於沒掛目標，列出放棄的節點。"""
    proj = hooked["proj"]
    files = _two_part_world(hooked)
    _op("set", goal="G", cwd=str(proj))
    _op("add", items=[{"text": "a"}, {"text": "b"}])
    ng.link_part(SID, ng._hub_key_of(files["UI"]), "T1.2", 2)
    ng.stamp_edit(SID, files["UI"], "", 2, {})
    assert "(f3)" not in (ng.goal_gate_reason(SID, True, {}) or "")
    _op("update", items=[{"id": "T1.2", "status": "dropped", "why": "不做了"}], turn=3)
    r = ng.goal_gate_reason(SID, True, {})
    assert "(f3)" in r and "T1.2 已放棄" in r


def test_cg0_overview_off_layer_records_no_part(hooked):
    """OverviewHub 在那一層關掉：不要求定位，也不記改到的部位（不在收尾補要）。"""
    proj = hooked["proj"]
    files = _two_part_world(hooked)
    _op("set", goal="G", cwd=str(proj))
    ng.stamp_edit(SID, files["UI"], "", 2, {"overview_hub": {"enabled": False}})
    assert not _tree().get("parts_edited")
    assert "(f3)" not in (ng.goal_gate_reason(SID, True, {"overview_hub": {"enabled": False}}) or "")


def test_cg0_stop_verify_gates_passes_transcript_for_relink(hooked):
    proj, tp = hooked["proj"], hooked["tp"]
    files = _two_part_world(hooked)
    _op("set", goal="G", cwd=str(proj))
    _op("add", items=[{"text": "a"}, {"text": "介面跟著刷新"}])
    ng.stamp_edit(SID, files["UI"], "", 2, {})
    off = {"enabled": False}
    reason, *_ = st._verify_gates({"turn_seq": 3}, SID, 3, "全部完成。", None, "", [], off, off, {}, False,
                                  goal=True, goal_cfg={})
    assert "(f3)" in reason
    _say(tp, FOUR_UI)
    reason, *_ = st._verify_gates({"turn_seq": 3}, SID, 3, "全部完成。", Path(tp), "", [], off, off, {}, False,
                                  goal=True, goal_cfg={})
    assert "(f3)" not in (reason or "")


# ─── 4.5 (f1)(f2)、Stop、commit ─────────────────────────────────────────────

def test_goal_gate_f1_every_time_f2_only_on_boundary(env):
    proj = _code_tree(env)
    assert ng.goal_gate_reason(SID, False, {}) is None                      # (f1) 不再擋：程式記進度、清待對照
    assert not ng._owed(_tree()) and _tree()["nodes"]["T1"]["history"][-1]["by"] == "program"
    assert "還沒交完整對照" in ng.goal_gate_reason(SID, True, {})              # (f2) 交付邊界照擋
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
    assert reason is None                                                   # 不在交付邊界：待對照由程式記進度、不擋
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
        st.handle_stop({"session_id": SID, "last_assistant_message": "全部完成。"}, {"reconcile_gate": {}, "verify_scope": {}})
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out.get("decision") == "block" and "(f2)" in out.get("reason", "") and "(f1)" not in out.get("reason", "")
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
            st.handle_stop({"session_id": SID, "last_assistant_message": "全部完成。"}, {})
        reasons.append(json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason"])
    assert all("(f2)" in r for r in reasons)
    assert pending_of(state, SID, "reconcile") is not None                  # 擋滿：記 pending、改問使用者
    assert RELEASE_TAG in reasons[-1] or "沒有人能回答" in reasons[-1] or "無法互動" in reasons[-1]
    _op("reconcile", turn=3, cwd=str(env["proj"]), items=[{"id": n, "status": "none", "followup": "f"}
                                                          for n in ("T1", "T1.1", "T1.2")])
    try:
        st.handle_stop({"session_id": SID, "last_assistant_message": "全部完成。"}, {})
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


# ─── 記憶知識類的輕樹 (f4)：沒樹時改知識類檔要寫樹、交付前要對照（屬記憶與報告類，不問使用者） ─────────────

def _kfile(proj, name):
    """寫出一個（記憶知識類的）檔、回路徑：沒樹時只認寫完還在的檔案。"""
    p = proj / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x", encoding="utf-8")
    return str(p)


def test_untreed_knowledge_write_hints_once_per_turn_and_is_adopted_by_new_tree(env):
    proj = env["proj"]
    assert ng.stamp_edit(SID, _kfile(proj, "a.py"), "", 2, {}) is None     # 程式檔沒樹：不記（改之前 edit_gate 已擋）
    _kfile(proj, "pkg/b.py")
    assert ng.stamp_edit(SID, str(proj / "pkg"), "", 2, {}) is None        # 搬過去的目錄裡有程式（git mv src pkg）：不算
    assert ng.stamp_edit(SID, str(proj / "src"), "", 2, {}) is None        # 搬走的目錄（沒副檔名又不在）分不出：不算
    assert ng.stamp_edit(SID, str(proj / "gone.py"), "", 2, {}) is None    # 刪掉的程式檔：不算
    (proj / "_AIDocs").mkdir()                                             # 專案根標記：執行期資料目錄相對專案根判
    assert ng.stamp_edit(SID, _kfile(proj, "Logs/run.jsonl"), "", 2, {}) is None   # 執行期資料（RUNTIME_DATA_NO_OVERVIEW）
    assert not ng.goal_path(SID).exists()
    line = ng.stamp_edit(SID, _kfile(proj, "notes.md"), "", 2, {})
    assert line and "notes.md" in line and "need_goal(action=set" in line and "不擋寫檔" in line
    assert ng.stamp_edit(SID, _kfile(proj, "plan.md"), "", 2, {}) is None  # 同一回合只送一次
    assert ng.stamp_edit(SID, _kfile(proj, "notes.md"), "", 3, {})         # 下一回合還沒寫樹：再送
    assert [Path(e["path"]).name for e in _doc()["untreed"]] == ["notes.md", "plan.md"]   # 同一檔一筆
    assert _doc()["untreed"][0]["turn"] == 3                                # 同一檔再改：回合更新
    assert ng.stamp_edit(SID, _kfile(proj, "x.md"), "", 3, {"overview_hub": {"need_goal": {"enabled": False}}}) is None
    _op("set", goal="整併兩份說明、必要步驟都保留", turn=3)
    t = _tree()
    assert [Path(e["path"]).name for e in t["edits"]] == ["notes.md", "plan.md"] and "untreed" not in _doc()
    assert all(e["node"] == "T1" and not e["owed"] and not e["code"] for e in t["edits"]) and t["kind"] == "knowledge"
    assert ng.stamp_edit(SID, _kfile(proj, "more.md"), "", 3, {}) is None  # 有樹：照常記進樹、不再送


def test_untreed_counts_deleted_docs_and_moved_doc_dirs(env):
    """沒樹時刪掉文件、搬文件目錄也是知識類的工作（Codex BLOCK 2）：已不在但副檔名不是程式的檔、裡面沒有程式的目錄都算。"""
    proj = env["proj"]
    assert ng.stamp_edit(SID, str(proj / "old.md"), "", 2, {})              # rm old.md 之後
    _kfile(proj, "old-docs/a.md")
    assert ng.stamp_edit(SID, str(proj / "old-docs"), "", 2, {}) is None    # mv docs old-docs（同回合不重送）
    assert [Path(e["path"]).name for e in _doc()["untreed"]] == ["old.md", "old-docs"]


def test_untreed_overflow_drops_oldest_with_signal(env, monkeypatch):
    """超過上限丟最舊的要留訊號（Codex BLOCK 3）：計數進目標檔、守門紀錄有一筆、session 結束的帳把丟的也算進去。"""
    import wg_need_goal_points as ngp
    monkeypatch.setattr(ng, "UNTREED_MAX", 2)
    proj = env["proj"]
    for name in ("a.md", "b.md", "c.md"):
        ng.stamp_edit(SID, _kfile(proj, name), "", 2, {})
    d = _doc()
    assert [Path(e["path"]).name for e in d["untreed"]] == ["b.md", "c.md"] and d["untreed_dropped"] == 1
    assert any(p.get("event") == "untreed_dropped" for g, p in env["guard"] if g == "need_goal")
    assert ngp.silent_unreconciled(SID, 3)[-1]["files"] == 3


def test_import_adopts_untreed_knowledge_writes(env):
    proj = _code_tree(env)
    block = ng.handoff_block(SID)
    assert ng.stamp_edit("sess-k", _kfile(proj, "notes.md"), "", 1, {})    # 讀續接單之前先改了文件
    ng.import_handoff("sess-k", block, str(proj / "next-phase-k.md"), 1)
    t = ng.active_tree(ng.load("sess-k"))
    assert [Path(e["path"]).name for e in t["edits"]] == ["notes.md"] and "untreed" not in ng.load("sess-k")


def test_multi_tree_import_adopts_untreed_into_the_continued_tree(env):
    """續接單有兩棵、接續的是第二棵：沒樹時改的檔掛到接續的那一棵，不看匯入順序（Codex BLOCK 1）。"""
    proj = env["proj"]
    _op("set", goal="A")
    _op("set", goal="B", new_task=True, why="換題", turn=2)
    block = ng.handoff_block(SID)
    assert ng.stamp_edit("sess-m", _kfile(proj, "notes.md"), "", 1, {})
    res = ng.import_handoff("sess-m", block, str(proj / "next-phase-m.md"), 1)
    d = ng.load("sess-m")
    active = d["trees"][d["active"]]
    assert res["map"]["T2"] == d["active"] and [Path(e["path"]).name for e in active["edits"]] == ["notes.md"]
    assert all(not t["edits"] for tid, t in d["trees"].items() if tid != d["active"])


def test_knowledge_edit_after_closed_reconcile_reopens_and_old_tree_still_owes(env):
    """知識類樹全部達成（結束）之後又改文件 → 退回進行中；換題開新樹後，舊樹對照後的改動交付時照樣要對照、session 結束照樣記帳
    （Codex BLOCK 4）。"""
    import wg_need_goal_points as ngp
    proj = env["proj"]
    _op("set", goal="整併說明", turn=2)
    ng.stamp_edit(SID, _kfile(proj, "notes.md"), "", 2, {})
    assert _op("reconcile", turn=2, cwd=str(proj), items=[
        {"id": "T1", "status": "done", "evidence": [{"kind": "file", "ref": "notes.md", "level": "read"}]}])["ok"]
    assert _tree()["status"] == "closed"
    ng.stamp_edit(SID, _kfile(proj, "notes.md"), "", 3, {})
    assert _tree()["status"] == "doing"
    _op("set", goal="別的事", new_task=True, why="換題", turn=3)
    r = ng.knowledge_gate_reason(SID, True, {}, 3, 3)
    assert r and "KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY" in r and "T1" in r and "notes.md" in r
    assert "T1" in [x["tree"] for x in ngp.silent_unreconciled(SID, 3)]


def test_knowledge_gate_f4_light_tree_and_reconcile_at_delivery(env):
    proj = env["proj"]
    ng.stamp_edit(SID, _kfile(proj, "old.md"), "", 1, {})                  # 上一個使用者回合改的
    assert ng.knowledge_gate_reason(SID, False, {}, 3, 3) is None           # 不在本回合：不要求（session 結束另記帳）
    ng.stamp_edit(SID, _kfile(proj, "notes.md"), "", 3, {})
    r = ng.knowledge_gate_reason(SID, False, {}, 3, 3)
    assert r and "(f4)" in r and "KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE" in r and "notes.md" in r and "old.md" not in r
    assert "need_goal(action=set" in r                                      # 不看措辭：沒宣告完成也要
    assert ng.knowledge_gate_reason(SID, False, {"overview_hub": {"need_goal": {"enabled": False}}}, 3, 3) is None
    _op("set", goal="整併說明", turn=3)
    assert ng.knowledge_gate_reason(SID, False, {}, 3, 3) is None           # 寫了樹；不在交付邊界不要對照
    r = ng.knowledge_gate_reason(SID, True, {}, 3, 3)
    assert r and "KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY" in r and "KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE" not in r
    res = _op("reconcile", turn=3, cwd=str(proj), items=[
        {"id": "T1", "status": "done", "evidence": [{"kind": "file", "ref": "notes.md", "level": "read"}]}])
    assert res["ok"], res                                                   # 知識類達成不要求案例或收據
    assert ng.knowledge_gate_reason(SID, True, {}, 3, 3) is None
    ng.stamp_edit(SID, _kfile(proj, "notes.md"), "", 4, {})                # 對照之後又改
    assert "KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY" in ng.knowledge_gate_reason(SID, True, {}, 4, 4)


def test_knowledge_gate_f4_skips_code_and_pure_qa_trees(env):
    _code_tree(env)
    assert ng.knowledge_gate_reason(SID, True, {}, 3, 3) is None            # 寫碼類歸 (f2)
    _op("set", goal="只是問答", sid="sess-qa")
    assert _tree("sess-qa")["kind"] == "knowledge"
    assert ng.knowledge_gate_reason("sess-qa", True, {}, 3, 3) is None      # 純問答（樹上沒改檔）不要求對照


def test_stop_verify_gates_puts_f4_in_report_not_code_check(env):
    ng.stamp_edit(SID, _kfile(env["proj"], "notes.md"), "", 3, {})
    off = {"enabled": False}
    state = {"turn_seq": 3, "turn_prompts_seq": 3}
    reason, report, kind, _ = st._verify_gates(state, SID, 3, "好了", None, "", [], off, off, {}, False,
                                               goal=True, goal_cfg={})
    assert reason is None and report and "(f4)" in report and kind == "reconcile"   # 記憶與報告類：不進寫碼查核
    reason, report, _, _ = st._verify_gates(state, f"{SID}#agent:x", 3, "好了", None, "", [], off, off, {}, False)
    assert reason is None and report is None                                # 子代理不跑


def test_stop_f4_blocks_twice_then_releases_with_overflow_not_asking(env, monkeypatch, capsys):
    from wg_release import pending_of
    ng.stamp_edit(SID, _kfile(env["proj"], "notes.md"), "", 3, {})
    state = {"turn_seq": 3, "turn_prompts_seq": 3, "session": {"id": SID, "cwd": str(env["proj"])}, "modified_files": []}
    _stop_env(env, monkeypatch, state)
    outs = []
    for _ in range(3):
        try:
            st.handle_stop({"session_id": SID, "last_assistant_message": "這輪先到這。"}, {})
        except SystemExit:
            pass
        outs.append(capsys.readouterr().out)
    assert all("(f4)" in o and "KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE" in o for o in outs[:2])
    assert "(f4)" not in outs[2] and state["reconcile_overflow"][SID]["kind"] == "report"   # 第 3 次放行並記帳
    assert pending_of(state, SID, "reconcile") is None                      # 不走擋滿問使用者


def test_stop_report_budget_not_eaten_by_code_rule_counts(env, monkeypatch, capsys):
    """同一使用者回合寫碼規則 (f1) 先擋過兩次，之後只剩收尾報告那一份 (f4) → 照擋，不因 (f1) 的次數直接放行
    （Codex WARN：BLOCK_BUDGET_PER_RULE 每條規則各自計次）。"""
    ng.stamp_edit(SID, _kfile(env["proj"], "notes.md"), "", 3, {})
    state = {"turn_seq": 3, "turn_prompts_seq": 3, "session": {"id": SID, "cwd": str(env["proj"])}, "modified_files": [],
             "reconcile_gate_turn": {SID: {"turn": 3, "counts": {"f1": 2}, "count": 2}}}
    _stop_env(env, monkeypatch, state)
    try:
        st.handle_stop({"session_id": SID, "last_assistant_message": "這輪先到這。"}, {})
    except SystemExit:
        pass
    out = capsys.readouterr().out
    assert "(f4)" in out and not state.get("reconcile_overflow")


def test_commit_gate_and_pretool_commit_denied(hooked, monkeypatch):
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    _code_tree(hooked)
    assert "(f2)" in ng.commit_gate(SID, {}) and "(f1)" not in ng.commit_gate(SID, {})
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
    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert ng.HANDOUT_CHECK in json.loads(out)["hookSpecificOutput"]["additionalContext"]   # 收尾報告之前送交出前一問
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
    _op("set", goal="另一件", new_task=True, why="換題", turn=2)
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


def test_post_tool_use_untreed_knowledge_write_sends_light_tree_line(env):
    proj = env["proj"]
    ctx, _ = pt._need_goal_after_tool({"turn_seq": 2}, "sess-k2", "Write", {"file_path": _kfile(proj, "notes.md")}, {}, {})
    assert ctx and "notes.md" in ctx and "need_goal(action=set" in ctx
    staging = _kfile(proj, ".claude/memory/_staging/next-phase-k.md")
    ctx, changed = pt._need_goal_after_tool({"turn_seq": 3}, "sess-k2", "Write", {"file_path": staging}, {}, {})
    assert "need_goal(action=set" in ctx and ng.HANDOUT_CHECK in ctx and changed   # 兩句併送、交出前一問改了 state
    ctx, _ = pt._need_goal_after_tool({"turn_seq": 3}, "sess-k2", "Write", {"file_path": _kfile(proj, "eph/x.md")}, {}, {})
    assert ctx is None                                                      # 暫存檔不管


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


def test_goal_gate_switch_off_skips_delivery_and_commit_checks(env):
    """收尾瘦身：reconcile_gate.goal_gate=false → 收尾的需求目標對照 (f1)(f2)(f3)、知識類輕樹 (f4)、commit 前的目標對照都不擋；
    目標樹照記，改檔前要有樹、提問要掛節點不歸這個開關。前置：同一棵樹預設照擋。舊碼不認這個鍵 → 紅。"""
    _code_tree(env)
    assert "(f2)" in ng.commit_gate(SID, {}) and ng.goal_gate_reason(SID, True, {})     # 前置：預設照擋
    off = {"reconcile_gate": {"goal_gate": False}}
    assert ng.commit_gate(SID, off) is None
    assert ng.goal_gate_reason(SID, True, off) is None
    assert ng.knowledge_gate_reason(SID, True, off, 5) is None
