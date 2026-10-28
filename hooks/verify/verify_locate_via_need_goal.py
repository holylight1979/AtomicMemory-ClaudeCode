"""verify_locate_via_need_goal.py：定位四行隨目標樹一起交（規則 LOCATE_VIA_NEED_GOAL）。

007 實測：AI 改檔前要交定位四行，只能寫在回覆文字或下一條 Bash 的 `#` 註解，做法變成「先發一條只有註解的 Bash、再重送 Edit」，
每個部位多一個模型回合。改造：need_goal set／update 加選填 locate=[{part, lines}]，PostToolUse 收到就交給 wg_overview 既有的
定位判定（locate_from_goal：取組、層、兩候選、批判同一套），通過標 located（via=need_goal）、掛節點；第一次改該部位不擋、不提醒；
行不齊或內容不過 → 不算交，回一行說缺什麼，改檔照舊第一次擋一次。讀檔提示與擋訊息都提這條路。v6 關：整道不動。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_locate_via_need_goal.py
共用 verify_need_goal 的資料根隔離（env／hooked）與部位世界、verify_gate_mode_pre 的真 PreToolUse／PostToolUse 入口；不碰 live。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

VERIFY = Path(__file__).resolve().parent
sys.path.insert(0, str(VERIFY))

from verify_gate_mode_pre import (  # noqa: E402,F401
    NG_TOOL, REMIND, _code_intent, _edit_input, _hub_events, _lines, _pre, _state_seed, _v6_on_full_card, post,
)
from verify_need_goal import (  # noqa: E402,F401
    CRIT, SID, THREE, THREE2, _mapped_world, _two_part_world, env, hooked, ng, wg_core, wo,
)

OK_RESP = {"content": [{"type": "text", "text": "ok"}]}
FOUR = THREE2.split("\n") + [CRIT.strip()]              # 戰鬥：部位／根因層（兩候選）／前例／批判
UI_FOUR = [ln.replace("戰鬥：A.cs", "介面：B.cs") for ln in FOUR]


def _set(post, locate, **kw):
    return post(NG_TOOL, {"action": "set", "goal": "戰鬥不卡", "kind": "code", "items": [{"text": "共用字典不再被兩邊改"}],
                          "locate": locate, **kw}, tool_response=OK_RESP)


def _rec(part):
    st = wg_core.read_state(SID)
    return next((v for k, v in (st.get("overview_hub") or {}).items() if k.endswith(f"|{part}")), None)


def test_need_goal_set_with_locate_marks_part_located(hooked, post):
    """set 帶 locate（部位名、檔路徑各一）：兩個部位都標 located、via=need_goal、掛到樹上（goal_tree／goal_node、目標檔 links.parts）；
    回覆附一行「定位已收」；帳 located_via_need_goal。還沒讀過的部位也先建紀錄（卡等第一次改檔才送，card_pending）。"""
    files = _two_part_world(hooked)
    ctx = _set(post, [{"part": "戰鬥", "lines": FOUR}, {"part": files["UI"], "lines": UI_FOUR}])
    assert "[NeedGoal] set 收下" in ctx
    assert ctx.count("定位已收（隨目標樹交）") == 2, ctx
    for part in ("戰鬥", "介面"):
        rec = _rec(part)
        assert rec and rec["located"] is True and rec["located_via"] == "need_goal" and rec["card_pending"] is True, (part, rec)
        assert rec["goal_tree"] == "T1" and rec["goal_node"] == "T1"      # 沒交第四行節點 → 掛樹根（LOCATE_GOAL_NODE 只記錄）
    tree = ng.active_tree(ng.load(SID))
    assert sorted(k.split("|")[-1] for k in tree["links"]["parts"]) == ["介面", "戰鬥"]
    assert sorted(e["part"] for e in _hub_events(hooked, "located_via_need_goal")) == ["介面", "戰鬥"]
    assert not _hub_events(hooked, "locate_via_need_goal_rejected")


def test_first_edit_after_locate_via_tree_not_denied_not_reminded(hooked, post):
    """交過就放：set 帶 locate 之後（a）沒讀就改——第一個 Edit 不擋，卡隨工具結果到，沒有定位提醒、沒有 edit_blocked_once；
    （b）先讀再改——讀檔結果不再提示交定位，Edit 一樣不擋。帳 edit_first_located（via=need_goal）。"""
    files = _two_part_world(hooked)
    _set(post, [{"part": "戰鬥", "lines": FOUR}, {"part": "介面", "lines": UI_FOUR}])
    deny, _ = _pre(hooked, "Edit", _edit_input(files["Battle"]))                 # (a) 沒讀就改
    assert deny is None, deny
    ctx = post("Edit", _edit_input(files["Battle"]))
    assert _lines(ctx, "OVERVIEW_CARD_BEFORE_EDIT") and "戰鬥導讀" in ctx and not _lines(ctx, "LOCATE_BEFORE_EDIT"), ctx
    assert "交定位" not in post("Read", {"file_path": files["UI"]})              # (b) 讀：已交過，不提示
    deny, _ = _pre(hooked, "Edit", _edit_input(files["UI"]))
    assert deny is None, deny
    assert not _lines(post("Edit", _edit_input(files["UI"])), "LOCATE_BEFORE_EDIT")
    assert not _hub_events(hooked, "edit_blocked_once") and not _hub_events(hooked, "locate_hint")
    assert [(e["part"], e["located_via"]) for e in _hub_events(hooked, "edit_first_located")] == [("戰鬥", "need_goal"), ("介面", "need_goal")]
    assert not [o for o in hooked["outputs"] if (o or {}).get("hookSpecificOutput", {}).get("permissionDecision") == "deny"]
    assert not any(k.startswith("LOCATE_BEFORE_EDIT|") for k in wg_core.read_state(SID).get("remind_sent") or [])


def test_locate_via_tree_missing_lines_not_counted(hooked, post):
    """行不齊（缺前例）、內容不過（根因層只有一個候選）、部位對不到：都不算交——回覆說缺什麼、帳 locate_via_need_goal_rejected、
    不建紀錄不標 located；之後第一次改照舊擋一次（LOCATE_FIRST_EDIT_BLOCKS_ONCE）。update 帶合格的 locate 補交 → 放。"""
    f1 = _mapped_world(hooked)
    short = [ln for ln in FOUR if not ln.startswith("定位｜前例")]
    one_candidate = THREE.split("\n") + [CRIT.strip()]
    ctx = _set(post, [{"part": "戰鬥", "lines": short}, {"part": "不存在的部位", "lines": FOUR}])
    assert "【戰鬥】的 locate 沒收：缺定位三行" in ctx and "「不存在的部位」對不到部位表" in ctx, ctx
    assert _rec("戰鬥") is None
    ctx = post(NG_TOOL, {"action": "update", "items": [{"id": "T1", "text": "戰鬥不卡頓"}], "locate": [{"part": "戰鬥", "lines": one_candidate}]},
               tool_response=OK_RESP)
    assert "【戰鬥】的 locate 沒收" in ctx and "LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES" in ctx, ctx
    assert [e["why"] for e in _hub_events(hooked, "locate_via_need_goal_rejected")] == ["missing_lines", "no_part", "content"]
    deny, _ = _pre(hooked, "Edit", _edit_input(f1))
    assert deny and "還沒交定位行，這一輪擋" in deny, deny                      # 沒交到就跟以前一樣：第一次擋
    ctx = post(NG_TOOL, {"action": "update", "items": [{"id": "T1", "text": "戰鬥不卡"}], "locate": [{"part": "戰鬥", "lines": FOUR}]},
               tool_response=OK_RESP)
    assert "定位已收" in ctx and _rec("戰鬥")["located"] is True
    assert _pre(hooked, "Edit", _edit_input(f1))[0] is None


def test_read_hint_mentions_need_goal_option(hooked, post):
    """讀檔提示那一行與缺定位的擋訊息都補了「可在 need_goal set／update 的 locate 欄一起交」；提示仍是一行。"""
    f1 = _mapped_world(hooked)
    _code_intent(hooked)                                                              # 使用者要改程式：讀檔才附定位提示
    hint = next(ln for ln in post("Read", {"file_path": f1}).splitlines() if ln.startswith("[Guardian:OverviewHub] 改【戰鬥】的程式檔前"))
    assert "need_goal set／update 的 locate 欄一起交" in hint and "不必另發註解指令" in hint
    assert wo.locate_read_hint("戰鬥", True, True, True).count("\n") == 0
    _set(post, [])
    deny, _ = _pre(hooked, "Edit", _edit_input(f1))
    assert deny and "need_goal(action=set／update) 的 locate 欄一起交" in deny, deny
    mcp_js = Path(__file__).resolve().parents[2].joinpath("tools", "workflow-guardian-mcp", "lib", "mcp.js").read_text(encoding="utf-8")
    assert "locate: {" in mcp_js and "不必另發註解指令" in mcp_js                   # schema 有 locate 欄（形狀由 js 案例驗）


def test_v6_off_unchanged(hooked, post, monkeypatch):
    """v6 關：帶 locate 的 set 跟不帶的一樣（回文整道不送）、不建紀錄不標 located、不留 located_via_need_goal 帳；讀檔與改檔結果都沒有提醒行。"""
    monkeypatch.setenv("WG_V6", "0")
    _state_seed(hooked)
    f1 = _mapped_world(hooked)
    ctx = _set(post, [{"part": "戰鬥", "lines": FOUR}])
    assert ctx == "" and _set(post, []) == ""                                     # v6 關：need_goal 的回文整道不送（既有），帶不帶 locate 一樣
    assert _rec("戰鬥") is None and not _hub_events(hooked, "located_via_need_goal")
    assert REMIND not in post("Read", {"file_path": f1})
    assert _pre(hooked, "Edit", _edit_input(f1))[0] is None
    assert REMIND not in post("Edit", _edit_input(f1))
    assert not wg_core.read_state(SID).get("remind_pending") and not wg_core.read_state(SID).get("remind_sent")


if __name__ == "__main__":
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("LOCATE_VIA_NEED_GOAL_CHECK PASS" if rc == 0 else "LOCATE_VIA_NEED_GOAL_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
