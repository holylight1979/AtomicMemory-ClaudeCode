"""verify_gate_mode_pre.py：工具前守門「擋改提醒」（規則 GATE_MODE_TABLE、REMIND_ON_PRIOR_RESULT）。

v6 總開關開時，提問閘、改程式前要有目標樹、commit 前目標對照、定位閘、導讀卡、無表專案、閘自己壞（P2～P10d）都不再 deny：
第一次讀到那塊程式檔的讀檔結果（既有 LOCATE_HINT_ON_FIRST_READ）或下一個工具結果（PostToolUse 的 additionalContext）附一行提醒，
同一條規則同一個對象一個 session 只提醒一次，沒照做不擋、也不送第二次。照擋三類（動資料檔、改舊測試、病形閘、繞閘）不動；
v6 關時每條路都跟改前一樣。都走真的 PreToolUse／PostToolUse 入口。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_gate_mode_pre.py
共用 verify_need_goal 的資料根隔離（env／hooked）與部位世界；照擋三類借 verify_pull_tool_gates 的假專案。不碰 live。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

VERIFY = Path(__file__).resolve().parent
sys.path.insert(0, str(VERIFY))

from verify_need_goal import (  # noqa: E402,F401
    CRIT, ON, SID, THREE2, _code_tree, _deny_text, _mapped_world, _op, _ptu_run, _say, _two_part_world, env, hooked, ng, pt,
    ptu, wg_core, wo,
)
from verify_pull_tool_gates import (  # noqa: E402,F401
    DATA_EDIT, OT_HIT, TEST_EDIT, _pre as _pull_pre, world as pull_world,
)
import wg_release_rules as _rr  # noqa: E402

REMIND = "[Guardian:提醒]"
NG_TOOL = "mcp__workflow-guardian__need_goal"


@pytest.fixture(autouse=True)
def _v6_on_full_card(monkeypatch):
    monkeypatch.setenv("WG_V6", "1")
    from hub_config import HUB_DEFAULTS
    monkeypatch.setitem(HUB_DEFAULTS, "card_injection", "full")


@pytest.fixture
def post(hooked, monkeypatch):
    """跑一次真的 PostToolUse，回那次工具結果附的 additionalContext（沒有回空字串）。"""
    got = []
    monkeypatch.setattr(pt, "output_json", lambda d: (got.append(d), sys.exit(0)))
    monkeypatch.setattr(pt, "output_nothing", lambda: (got.append(None), sys.exit(0)))
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_run_companion_hooks", lambda *a: ([], []))
    monkeypatch.setattr(pt, "_note_commit", lambda *a, **k: None)

    def run(tool, tool_input, config=None, tool_response=None, tid="tu-post"):
        inp = {"session_id": SID, "hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": tool_input,
               "tool_response": tool_response if tool_response is not None else {}, "cwd": str(hooked["proj"]),
               "transcript_path": hooked["tp"], "tool_use_id": tid}
        with pytest.raises(SystemExit):
            pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}, **(config or {})})
        return ((got[-1] or {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""
    return run


def _pre(hooked, tool, tool_input, config=None):
    """跑一次真的 PreToolUse；回 (deny 文字或 None, 整個輸出)。"""
    out = _ptu_run(tool, tool_input, hooked["proj"], hooked["tp"], hooked["outputs"], config=config)
    return _deny_text(out), out


def _edit_input(f):
    return {"file_path": f, "old_string": "x", "new_string": "y"}


def _ask(labels, question="要用哪個做法？"):
    return {"questions": [{"question": question, "header": "做法", "multiSelect": False,
                           "options": [{"label": l, "description": f"{l} 的說明"} for l in labels]}]}


def _state_seed(hooked):
    wg_core.write_state(SID, {"session": {"id": SID, "cwd": str(hooked["proj"])}, "turn_seq": 1})


def _hub_events(hooked, event):
    p = hooked["tmp"] / "hub.log"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
    return [e for e in rows if e["event"] == event]


def _lines(ctx, rule):
    return [ln for ln in ctx.splitlines() if ln.startswith(REMIND) and rule in ln]


# ─── P2／P2c 提問閘 ─────────────────────────────────────────────────────────

def test_ask_no_recommendation_reminded_not_denied(hooked, post):
    """P2：沒附推薦的提問不擋；AskUserQuestion 的工具結果附一行（規則名＋做法）；同 session 第二題沒推薦不再提醒、也不擋。"""
    _state_seed(hooked)
    bad = _ask(["A", "B"])
    deny, out = _pre(hooked, "AskUserQuestion", bad)
    assert deny is None and out is None, out                       # 不擋、PreToolUse 不送 additionalContext
    ctx = post("AskUserQuestion", bad)
    line = _lines(ctx, "ASK_NEEDS_RECOMMENDATION")
    assert len(line) == 1 and "做法：" in line[0] and "(Recommended)" in line[0], ctx
    assert [p["rule"] for g, p in hooked["guard"] if g == "need_goal" and p["event"] == "remind"
            and p["rule"] == "ASK_NEEDS_RECOMMENDATION"] == ["ASK_NEEDS_RECOMMENDATION"]
    deny, _ = _pre(hooked, "AskUserQuestion", _ask(["C", "D"], "再問一題？"))
    assert deny is None
    assert not _lines(post("AskUserQuestion", bad), "ASK_NEEDS_RECOMMENDATION")


def test_ask_gate_error_not_denied(hooked, post, monkeypatch):
    """P2c：提問前檢查自己壞了 → 不擋、stderr＋留帳 ask_error（GATE_SELF_ERROR），下一個工具結果附一行提醒。"""
    _state_seed(hooked)
    monkeypatch.setitem(sys.modules, "wg_need_goal_points", None)
    deny, out = _pre(hooked, "AskUserQuestion", _ask(["A", "B"]))
    assert deny is None and out is None, out
    assert [(p["event"], p.get("rule")) for g, p in hooked["guard"] if g == "need_goal" and p["event"] == "ask_error"] \
        == [("ask_error", "GATE_SELF_ERROR")]
    monkeypatch.delitem(sys.modules, "wg_need_goal_points")
    ctx = post("AskUserQuestion", _ask(["A", "B"]))
    assert _lines(ctx, "GATE_SELF_ERROR") and "提問前檢查" in _lines(ctx, "GATE_SELF_ERROR")[0], ctx


# ─── P8 commit 前目標對照 ──────────────────────────────────────────────────

def test_commit_goal_reminded_not_denied(hooked, post, monkeypatch):
    """P8：commit 前目標對照沒過 → 不擋；commit 那則 Bash 的工具結果附一行（每棵樹一次）。"""
    _state_seed(hooked)
    _code_tree(hooked)
    assert "(f2)" in ng.commit_gate(SID, ON)
    monkeypatch.setattr(ptu, "check_git_commit_order", lambda *a, **k: None)
    monkeypatch.setattr(ptu, "check_git_privacy", lambda *a, **k: None)
    cmd = {"command": 'git commit -m "x"'}
    deny, out = _pre(hooked, "Bash", cmd, config=ON)
    assert deny is None, deny
    ctx = post("Bash", cmd, config=ON)
    assert len(_lines(ctx, "COMMIT_GOAL_RECONCILED")) == 1 and "(f2)" in _lines(ctx, "COMMIT_GOAL_RECONCILED")[0], ctx
    assert _pre(hooked, "Bash", cmd, config=ON)[0] is None
    assert not _lines(post("Bash", cmd, config=ON), "COMMIT_GOAL_RECONCILED")


# ─── P9 改程式前要有目標樹 ────────────────────────────────────────────────

def test_first_edit_without_tree_not_denied(hooked, post):
    """P9：沒讀就先改、還沒有目標樹 → 不擋；那次 Edit 的工具結果附一行立樹提醒（還順帶注入導讀卡：P10b）。"""
    f1 = _mapped_world(hooked)
    deny, out = _pre(hooked, "Edit", _edit_input(f1))
    assert deny is None and out is None, out
    ctx = post("Edit", _edit_input(f1))
    assert len(_lines(ctx, "CODE_EDIT_NEEDS_GOAL_TREE")) == 1 and "need_goal(action=set" in ctx
    assert "戰鬥導讀" in ctx and _lines(ctx, "OVERVIEW_CARD_BEFORE_EDIT")
    assert ctx.index(REMIND) < ctx.index("戰鬥導讀")                # 提醒一行在前、卡在後
    assert _pre(hooked, "Edit", _edit_input(f1))[0] is None
    again = post("Edit", _edit_input(f1))
    assert not _lines(again, "CODE_EDIT_NEEDS_GOAL_TREE") and "戰鬥導讀" not in again


def test_tree_hint_once_per_session(hooked, post):
    """P9：讀檔結果已經講過「先 need_goal set」（LOCATE_HINT_ON_FIRST_READ）→ 之後沒樹就改，不擋也不再提醒立樹。"""
    f1 = _mapped_world(hooked)
    assert "立需求目標樹" in post("Read", {"file_path": f1})
    assert _pre(hooked, "Edit", _edit_input(f1))[0] is None
    ctx = post("Edit", _edit_input(f1))
    assert not _lines(ctx, "CODE_EDIT_NEEDS_GOAL_TREE") and "need_goal(action=set" not in ctx, ctx


# ─── P10 定位閘 ─────────────────────────────────────────────────────────

def test_locate_reminded_on_read_not_denied_on_edit(hooked, post):
    """P10：第一次讀到部位程式檔的讀檔結果已提醒交定位 → 立了樹沒交定位就改：不擋、留帳 edit_remind、不送第二次。"""
    f1 = _mapped_world(hooked)
    assert "交定位四行" in post("Read", {"file_path": f1})
    _op("set", goal="戰鬥不卡", items=[{"text": "共用字典不再被兩邊改"}])
    deny, out = _pre(hooked, "Edit", _edit_input(f1))
    assert deny is None, deny
    assert [e["rule"] for e in _hub_events(hooked, "edit_remind")] == ["LOCATE_BEFORE_EDIT"]
    assert REMIND not in post("Edit", _edit_input(f1))
    assert not [o for o in hooked["outputs"] if o]                  # PreToolUse 全程沒輸出（沒擋、沒提醒）


def test_locate_remind_once_per_part(hooked, post):
    """P10：每部位每 session 一次：戰鬥提醒過再改兩次不提醒；介面第一次讀時點名一次，之後改介面也不提醒。"""
    files = _two_part_world(hooked)
    _op("set", goal="戰鬥不卡", kind="code", items=[{"text": "共用字典不再被兩邊改"}])
    assert "改【戰鬥】的程式檔前交定位四行" in post("Read", {"file_path": files["Battle"]})
    for _ in range(2):
        assert _pre(hooked, "Edit", _edit_input(files["Battle"]))[0] is None
        assert REMIND not in post("Edit", _edit_input(files["Battle"]))
    ui = post("Read", {"file_path": files["UI"]})
    assert "改【介面】的程式檔前交定位四行（格式同前一則提示）" in ui
    assert _pre(hooked, "Edit", _edit_input(files["UI"]))[0] is None
    assert REMIND not in post("Edit", _edit_input(files["UI"]))
    assert [e["part"] for e in _hub_events(hooked, "edit_remind")][:2] == ["戰鬥", "戰鬥"]
    assert not [o for o in hooked["outputs"] if _deny_text(o)]


def test_card_injected_after_edit_not_denied(hooked, post):
    """P10b：沒讀就先改、導讀卡還沒注入 → 不擋；那次 Edit 的工具結果附一行提醒並把卡注入；第二次改不重送卡。"""
    f1 = _mapped_world(hooked)
    _op("set", goal="戰鬥不卡", items=[{"text": "共用字典不再被兩邊改"}])
    deny, out = _pre(hooked, "Edit", _edit_input(f1))
    assert deny is None and out is None, out
    ctx = post("Edit", _edit_input(f1))
    assert _lines(ctx, "OVERVIEW_CARD_BEFORE_EDIT") and "戰鬥導讀" in ctx and "已知病灶" in ctx
    assert [e["deny_reason"] for e in _hub_events(hooked, "edit_before_inject")] == ["not_injected"]
    assert _pre(hooked, "Edit", _edit_input(f1))[0] is None
    again = post("Edit", _edit_input(f1))
    assert "戰鬥導讀" not in again and not _lines(again, "OVERVIEW_CARD_BEFORE_EDIT")


# ─── P10c 沒部位表 ─────────────────────────────────────────────────────

def test_unmapped_reminded_once_per_top(hooked, post):
    """P10c：沒有部位表的專案，第一次讀某頂層目錄的程式檔 → 讀檔結果附一行最小地圖提醒；同目錄再讀不送；沒交地圖就改不擋、不再提醒。"""
    proj = hooked["proj"]
    (proj / ".git").mkdir()
    (proj / "src").mkdir()
    for n in ("a.py", "b.py"):
        (proj / "src" / n).write_text("x = 1\n", encoding="utf-8")
    _op("set", goal="G")
    ctx = post("Read", {"file_path": str(proj / "src" / "a.py")})
    assert len(_lines(ctx, "UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP")) == 1 and "地圖｜讀了" in ctx, ctx
    assert REMIND not in post("Read", {"file_path": str(proj / "src" / "b.py")})
    deny, out = _pre(hooked, "Edit", _edit_input(str(proj / "src" / "a.py")))
    assert deny is None, deny
    assert REMIND not in post("Edit", _edit_input(str(proj / "src" / "a.py")))


# ─── P10d 閘自己炸 ────────────────────────────────────────────────────

def test_hub_self_error_not_denied(hooked, post, monkeypatch):
    """P10d：OverviewHub 閘自己炸 → 不擋、stderr＋留帳 gate_error（GATE_SELF_ERROR）、下一個工具結果附一行。"""
    f1 = _mapped_world(hooked)
    _op("set", goal="戰鬥不卡", items=[{"text": "共用字典不再被兩邊改"}])

    def boom(*a, **k):
        raise RuntimeError("模擬閘內部錯誤")
    real = wo.edit_check
    monkeypatch.setattr(wo, "edit_check", boom)
    deny, out = _pre(hooked, "Edit", _edit_input(f1))
    assert deny is None and out is None, out
    assert [(e.get("rule"), e.get("allowed")) for e in _hub_events(hooked, "gate_error")] == [("GATE_SELF_ERROR", True)]
    monkeypatch.setattr(wo, "edit_check", real)
    ctx = post("Edit", _edit_input(f1))
    assert _lines(ctx, "GATE_SELF_ERROR") and "模擬閘內部錯誤" in _lines(ctx, "GATE_SELF_ERROR")[0], ctx


# ─── 照擋三類不動 ───────────────────────────────────────────────────────

def test_block_data_file_has_rule_and_fix(pull_world):
    r = _pull_pre(pull_world, "Edit", {"file_path": str(pull_world["proj"] / "settings.json"), **DATA_EDIT})
    assert "USER_DATA_FILE_NEEDS_DECLARATION" in r and "修法" in r and "動資料檔｜" in r, r
    assert _rr.gate_mode("USER_DATA_FILE_NEEDS_DECLARATION", True) == _rr.BLOCK


def test_block_old_test_has_rule_and_fix(pull_world):
    r = _pull_pre(pull_world, "Edit", {"file_path": str(pull_world["proj"] / "tests" / "test_calc.py"), **TEST_EDIT})
    assert OT_HIT in r and "改舊測試｜" in r, r
    assert _rr.gate_mode("OLD_TEST_CHANGE_NEEDS_DECLARATION", True) == _rr.BLOCK


def test_block_smell_has_rule_and_fix(pull_world, monkeypatch):
    """病形閘的擋訊息原樣送出（規則名＋修法）；這裡換掉病形判定本體，只驗 pre_tool_use 這條路照擋。"""
    for name in ("check_git_commit_order", "check_git_privacy", "check_merge_driver"):
        monkeypatch.setattr(ptu, name, lambda *a, **k: None)
    text = "[Guardian:SmellGate] 修法：拆掉這次提交新寫進的巢狀\n✗ (s) COMMIT_SMELL_NEW_BLOCKS：a.py 巢狀 4 層"
    monkeypatch.setattr(ptu, "check_smell_gate", lambda *a, **k: (text, None))
    monkeypatch.setattr(ptu.wg_gate_bypass, "note_smell_deny", lambda *a, **k: None)
    r = _pull_pre(pull_world, "Bash", {"command": 'git commit -m "x"'})
    assert r.startswith(text), r
    assert _rr.gate_mode("COMMIT_SMELL_NEW_BLOCKS", True) == _rr.BLOCK


def test_block_gate_bypass(pull_world, monkeypatch):
    for name in ("check_git_commit_order", "check_git_privacy", "check_merge_driver"):
        monkeypatch.setattr(ptu, name, lambda *a, **k: None)
    monkeypatch.setattr(ptu, "check_smell_gate", lambda *a, **k: (None, None))
    text = "[Guardian:GateBypass] 修法：寫「不是繞閘｜理由」\n✗ (b) GATE_BYPASS_NEEDS_DECLARATION：retry.py 被排除"
    monkeypatch.setattr(ptu.wg_gate_bypass, "check", lambda *a, **k: text)
    r = _pull_pre(pull_world, "Bash", {"command": "git restore --staged notify/retry.py"})
    assert r.startswith(text), r
    assert _rr.gate_mode("GATE_BYPASS_NEEDS_DECLARATION", True) == _rr.BLOCK


# ─── v6 關：一字不變 ────────────────────────────────────────────────────

def test_v6_off_pre_gates_unchanged(hooked, post, monkeypatch):
    """總開關關：提問閘照擋（不讀本表）、改程式沒樹不查（9e476fd0 就沒有）、讀檔與改檔結果都沒有提醒行。"""
    monkeypatch.setenv("WG_V6", "0")
    _state_seed(hooked)
    f1 = _mapped_world(hooked)
    deny, _ = _pre(hooked, "AskUserQuestion", _ask(["A", "B"]))
    assert deny and "ASK_NEEDS_RECOMMENDATION" in deny
    assert REMIND not in post("Read", {"file_path": f1})
    deny, out = _pre(hooked, "Edit", _edit_input(f1))
    assert deny is None
    assert REMIND not in post("Edit", _edit_input(f1))
    assert not wg_core.read_state(SID).get("remind_pending") and not wg_core.read_state(SID).get("remind_sent")


# ─── 順手：加子節點不算目標改了 ───────────────────────────────────────────

def test_add_child_node_keeps_located(hooked, post):
    """目標樹 add 子節點不清掉已交的定位（只有 set 改寫樹根、update 改節點文字才算目標改了）。"""
    f1 = _mapped_world(hooked)
    _op("set", goal="戰鬥不卡", items=[{"text": "共用字典不再被兩邊改"}])
    post("Read", {"file_path": f1})
    st = wg_core.read_state(SID)
    key = next(k for k in st["overview_hub"] if k.endswith("|戰鬥"))
    st["overview_hub"][key]["located"] = True
    wg_core.write_state(SID, st)
    post(NG_TOOL, {"action": "add", "items": [{"text": "介面刷新跟著字典變"}]}, tool_response={"content": [{"type": "text", "text": "ok"}]})
    assert wg_core.read_state(SID)["overview_hub"][key]["located"] is True
    post(NG_TOOL, {"action": "update", "items": [{"id": "T1.1", "text": "共用字典只在邏輯層寫"}]},
         tool_response={"content": [{"type": "text", "text": "ok"}]})
    assert wg_core.read_state(SID)["overview_hub"][key]["located"] is False


if __name__ == "__main__":
    import subprocess
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("GATE_MODE_PRE_CHECK PASS" if rc == 0 else "GATE_MODE_PRE_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)


# ─── OverviewHub 綁 v6 總開關：關時整道不送（OVERVIEW_HUB_UNDER_V6） ───
def test_v6_off_overview_hub_disabled_no_card_injection(monkeypatch):
    import wg_overview as ovh
    import wg_release_rules as _rr
    assert "OVERVIEW_HUB_UNDER_V6" in _rr.RULES
    monkeypatch.setattr(ovh, "v6_enabled", lambda config: False)
    cfg = ovh._cfg({"overview_hub": {"enabled": True}})
    assert cfg["enabled"] is False
    monkeypatch.setattr(ovh, "v6_enabled", lambda config: True)
    cfg_on = ovh._cfg({"overview_hub": {"enabled": True}})
    assert cfg_on["enabled"] is True
