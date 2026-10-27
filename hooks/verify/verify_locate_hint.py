"""verify_locate_hint.py：定位與立樹「讀到就先提示，沒照做才擋」（規則 LOCATE_HINT_ON_FIRST_READ）。

讀檔走真的 PostToolUse 處理器（handle_post_tool_use），改檔走真的 PreToolUse 處理器（handle_pre_tool_use）：提示要出現在
第一個 Edit 之前那則讀檔工具結果的 additionalContext 裡（讀檔只送這一行、不送卡，規則 READ_TOUCH_NO_CARD；卡隨第一次 Edit 那則的
工具結果到：提醒件 OVERVIEW_CARD_BEFORE_EDIT 進 remind_pending）；照提示立樹、交四行再改 → 不擋；沒照做 → 第一次改這個部位擋一次
（規則 LOCATE_FIRST_EDIT_BLOCKS_ONCE），之後不擋、不再提醒（規則 GATE_MODE_TABLE；判定與留帳不動）。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_locate_hint.py
  （直接跑 python -X utf8 hooks/verify/verify_locate_hint.py 也行：開子行程跑 pytest，尾行印哨兵）
共用 verify_need_goal 的資料根隔離（env／hooked）與部位世界；不碰 live。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

VERIFY = Path(__file__).resolve().parent
sys.path.insert(0, str(VERIFY))

from verify_need_goal import (  # noqa: E402,F401
    CRIT, SID, THREE2, _deny_text, _mapped_world, _op, _ptu_run, _say, _two_part_world, env, hooked, pt, wg_core, wo,
)


@pytest.fixture(autouse=True)
def _v6_on(monkeypatch):
    """提示只在 v6 總開關開時送；案例預設開，關的那案自己再關。"""
    monkeypatch.setenv("WG_V6", "1")
    from hub_config import HUB_DEFAULTS
    monkeypatch.setitem(HUB_DEFAULTS, "card_injection", "full")


@pytest.fixture
def post_read(hooked, monkeypatch):
    """跑一次真的 PostToolUse（讀檔），回這次工具結果附的 additionalContext；state 落到資料根複本，之後的 PreToolUse 讀得到。"""
    got = []
    monkeypatch.setattr(pt, "output_json", lambda d: (got.append(d), sys.exit(0)))
    monkeypatch.setattr(pt, "output_nothing", lambda: (got.append(None), sys.exit(0)))
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_run_companion_hooks", lambda *a: ([], []))

    def run(tool_input, tool="Read", config=None, agent_id=""):
        inp = {"session_id": SID, "hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": tool_input,
               "tool_response": {}, "cwd": str(hooked["proj"]), "transcript_path": hooked["tp"],
               **({"agent_id": agent_id} if agent_id else {})}
        with pytest.raises(SystemExit):
            pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}, **(config or {})})
        return ((got[-1] or {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""
    return run


def _edit(hooked, f, config=None):
    return _deny_text(_ptu_run("Edit", {"file_path": f, "old_string": "x", "new_string": "y"}, hooked["proj"], hooked["tp"],
                               hooked["outputs"], config=config))


def _hint_events(hooked):
    p = hooked["tmp"] / "hub.log"
    return [e for e in (json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()) if e["event"] == "locate_hint"]


FOUR = THREE2 + CRIT


def test_locate_hint_on_first_read_of_part_code_file_then_follow_it_no_block(hooked, post_read):
    """規則 LOCATE_HINT_ON_FIRST_READ：還沒有目標樹時第一次讀到部位的程式檔 → 那則讀檔工具結果（PostToolUse，不是改檔的
    PreToolUse）附一行：先 need_goal set 立樹、交定位四行（根因層兩候選、批判先下判斷）、寫在回覆文字或不寫檔指令的 # 註解、
    thinking 讀不到。AI 照做（立樹、回覆文字交四行）→ 第一個 Edit 兩道閘都不擋。改前讀檔結果只有導讀卡 → 紅。"""
    f1 = _mapped_world(hooked)
    ctx = post_read({"file_path": f1})
    hint = next(ln for ln in ctx.splitlines() if ln.startswith("[Guardian:OverviewHub] 改【戰鬥】的程式檔前"))
    assert "先用 need_goal(action=set, goal=…) 立需求目標樹" in hint and "交定位四行" in hint
    assert "候選 A …；候選 B …；選 A 因為 …" in hint and "合不合理、為什麼" in hint
    assert "回覆文字" in hint and "開頭的 `#` 註解" in hint and "（thinking 讀不到）" in hint and "照常用 Edit／Write" in hint
    assert "戰鬥導讀" not in ctx                                                    # 讀檔結果只有提示、沒有卡（READ_TOUCH_NO_CARD）
    assert not [o for o in hooked["outputs"] if o]                                 # 還沒有任何 PreToolUse 輸出：提示在第一個 Edit 之前
    _op("set", goal="戰鬥不卡", items=[{"text": "共用字典不再被兩邊改"}])
    _say(hooked["tp"], FOUR)
    assert _edit(hooked, f1) is None                                                # 第一個 Edit：不擋，卡排進提醒、隨這次工具結果到
    pend = wg_core.read_state(SID)["remind_pending"]
    assert [h["rule"] for h in pend] == ["OVERVIEW_CARD_BEFORE_EDIT"]
    assert "戰鬥導讀" in pend[0]["extra"] and "導讀卡現在才送" in pend[0]["what"]
    assert _edit(hooked, f1) is None                                                # 卡到了、樹與四行都有 → 不擋
    assert [(e["need_tree"], e["four"], e["first"]) for e in _hint_events(hooked)] == [(True, True, True)]


def test_locate_hint_ignored_not_blocked_and_not_reminded_twice(hooked, post_read):
    """先讀、沒照做就改（規則 GATE_MODE_TABLE）：讀檔提示就是那一次提醒——沒樹就改不擋、不再提醒立樹；立了樹沒交定位也不擋、
    不再提醒定位（提醒帳 remind_sent 已有這兩件；判定照舊留帳 edit_blocked／edit_remind）。"""
    f1 = _mapped_world(hooked)
    assert "立需求目標樹" in post_read({"file_path": f1})
    assert _edit(hooked, f1)                                              # 第一次缺定位：擋一次（LOCATE_FIRST_EDIT_BLOCKS_ONCE）
    assert _edit(hooked, f1) is None                                      # 第二次：不擋
    state = wg_core.read_state(SID)
    pending_rules = lambda st: [h["rule"] for h in st.get("remind_pending") or []]   # noqa: E731
    assert pending_rules(state) == ["OVERVIEW_CARD_BEFORE_EDIT"]                   # 等著送的只有卡，沒有立樹／定位的第二次提醒
    assert any(k.startswith("CODE_EDIT_NEEDS_GOAL_TREE|") for k in state["remind_sent"])
    assert any(k.startswith("LOCATE_BEFORE_EDIT|") for k in state["remind_sent"])
    assert [p["why"] for g, p in hooked["guard"] if g == "need_goal" and p["event"] == "edit_blocked"] == ["no_tree", "no_tree"]
    _op("set", goal="戰鬥不卡", items=[{"text": "共用字典不再被兩邊改"}])
    assert _edit(hooked, f1) is None
    assert pending_rules(wg_core.read_state(SID)) == ["OVERVIEW_CARD_BEFORE_EDIT"]
    assert len([o for o in hooked["outputs"] if o]) == 1                  # 只有第一次那一擋


def test_locate_hint_skips_non_code_second_read_located_and_short_for_next_part(hooked, post_read):
    """讀非程式檔（同部位的 .md）不送提示；同一部位第二次讀不重送；已交過定位的部位不送；本 session 第二個部位只點名、說格式同前；
    知識類部位（放 .py 也不算程式）不送；有樹時只講定位。"""
    files = _two_part_world(hooked)
    notes = Path(files["Battle"]).with_name("notes.md")
    notes.write_text("# 筆記", encoding="utf-8")
    _op("set", goal="戰鬥不卡", kind="code", items=[{"text": "共用字典不再被兩邊改"}])
    ctx = post_read({"file_path": str(notes)})
    assert "戰鬥導讀" not in ctx and "交定位" not in ctx                            # 非程式檔：只建紀錄，卡與提示都不送
    ctx = post_read({"file_path": files["Battle"]})
    assert "改【戰鬥】的程式檔前交定位四行" in ctx and "need_goal(action=set" not in ctx   # 有樹：只講定位
    assert "交定位" not in post_read({"file_path": files["Battle"]})               # 同部位第二次讀
    assert "交定位" not in post_read({"command": f'cat "{files["Battle"]}"'}, tool="Bash")
    assert "交定位" not in post_read({"file_path": files["Docs"]})                 # 知識類部位
    ui = post_read({"file_path": files["UI"]})
    assert "[Guardian:OverviewHub] 改【介面】的程式檔前交定位四行（格式同前一則提示）。" in ui
    state = wg_core.read_state(SID)                                                 # 已交過定位的部位：不送
    rec = next(v for k, v in state["overview_hub"].items() if k.endswith("|介面"))
    rec.update(locate_hint="due", located=True)
    wg_core.write_state(SID, state)
    assert "交定位" not in post_read({"file_path": files["UI"]})
    assert [e["part"] for e in _hint_events(hooked)] == ["戰鬥", "介面"]


def test_locate_hint_not_sent_when_edit_injected_first(hooked, post_read):
    """改檔時才補注入的部位（第一次碰就是 Edit）：那則擋訊息已經講了要交什麼，之後再讀它的程式檔不另送提示。"""
    f1 = _mapped_world(hooked)
    _op("set", goal="戰鬥不卡", items=[{"text": "共用字典不再被兩邊改"}])
    assert _edit(hooked, f1)                                                        # 補注入導讀卡；第一次改缺定位擋一次，卡排進提醒隨下個工具結果送
    assert [h["rule"] for h in wg_core.read_state(SID)["remind_pending"]] == ["OVERVIEW_CARD_BEFORE_EDIT"]
    assert "交定位" not in post_read({"file_path": f1})
    assert not _hint_events(hooked)


def test_locate_hint_subagent_and_switches_off_unchanged(hooked, post_read, monkeypatch):
    """子代理讀的不送、也不吃掉主 session 那一次；v6 總開關關、OverviewHub 關 → 讀檔結果跟改前一樣（沒有提示）；
    need_goal 關 → 只要定位三行、不提立樹（同那時的擋訊息）。"""
    f1 = _mapped_world(hooked)
    assert "交定位" not in post_read({"file_path": f1}, agent_id="ag-1")
    monkeypatch.setenv("WG_V6", "0")
    off = post_read({"file_path": f1})
    assert "交定位" not in off
    monkeypatch.setenv("WG_V6", "1")
    assert "交定位" not in post_read({"file_path": f1}, config={"overview_hub": {"enabled": False}})
    three = post_read({"file_path": f1}, config={"overview_hub": {"need_goal": {"enabled": False}}})
    hint = next(ln for ln in three.splitlines() if ln.startswith("[Guardian:OverviewHub] 改【戰鬥】的程式檔前"))
    assert "交定位三行：定位｜部位、定位｜根因層、定位｜前例" in hint and "need_goal" not in hint and "定位｜批判" not in hint
    assert [e["four"] for e in _hint_events(hooked)] == [False]


def test_locate_hint_text_matches_what_gates_check():
    """提示跟擋講同一件事、同一個格式：四行版點到擋訊息要的每一行（部位、根因層兩候選＋理由、前例、批判判斷），寫法管道用同一句
    DECL_VIA_COMMENT、宣告完照常用 Edit／Write（DECL_HINT_KEEPS_EDIT_TOOLS）；三行版只點三行；後續部位一行點名。"""
    four = wo.locate_read_hint("戰鬥", True, True, True)
    for piece in ("定位｜部位", "定位｜根因層", "候選 A", "候選 B", "選 A 因為", "第二個不存在因為", "定位｜前例", "定位｜批判",
                  "合不合理、為什麼", wo._rr.DECL_VIA_COMMENT, "thinking 讀不到", "照常用 Edit／Write"):
        assert piece in four, piece
    assert "\n" not in four and four.index("need_goal(action=set") < four.index("定位四行")   # 立樹與定位併成同一行、先立樹
    three = wo.locate_read_hint("戰鬥", False, False, True)
    assert "定位三行" in three and "定位｜批判" not in three and "need_goal" not in three
    assert wo.locate_read_hint("介面", False, True, False) == "[Guardian:OverviewHub] 改【介面】的程式檔前交定位四行（格式同前一則提示）。"


if __name__ == "__main__":
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("LOCATE_HINT_CHECK PASS" if rc == 0 else "LOCATE_HINT_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
