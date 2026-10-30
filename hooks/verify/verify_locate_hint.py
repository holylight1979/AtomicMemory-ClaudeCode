"""verify_locate_hint.py：定位「讀到就先提示，沒照做才擋」（規則 LOCATE_HINT_ON_FIRST_READ）。

讀檔走真的 PostToolUse 處理器（handle_post_tool_use），改檔走真的 PreToolUse 處理器（handle_pre_tool_use）：提示要出現在
第一個 Edit 之前那則讀檔工具結果的 additionalContext 裡（讀檔只送這一行、不送卡，規則 READ_TOUCH_NO_CARD；卡隨第一次 Edit 那則的
工具結果到：提醒件 OVERVIEW_CARD_BEFORE_EDIT 進 remind_pending）；照提示交三行再改 → 不擋；沒照做 → 第一次改這個部位擋一次
（規則 LOCATE_FIRST_EDIT_BLOCKS_ONCE），之後不擋、不再提醒（規則 GATE_MODE_TABLE；判定與留帳不動）。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_locate_hint.py
  （直接跑 python -X utf8 hooks/verify/verify_locate_hint.py 也行：開子行程跑 pytest，尾行印哨兵）
共用 hub_world 的資料根隔離（env／hooked）與部位世界；不碰 live。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

VERIFY = Path(__file__).resolve().parent
sys.path.insert(0, str(VERIFY))

from hub_world import (  # noqa: E402,F401
    SID, THREE2, _deny_text, _mapped_world, _ptu_run, _say, _two_part_world, env, hooked, pt, wg_core, wo,
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
    if not p.exists():
        return []
    return [e for e in (json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()) if e["event"] == "locate_hint"]


def _coding(hooked):
    """把這個 session 標成寫碼回合（規則 NON_CODING_TURN_NO_NUDGE：定位提示只在寫碼回合送）：state 記一筆本回合改過的程式檔。"""
    st = wg_core.read_state(SID) or {}
    turn = max(int(st.get("turn_seq", 0) or 0), int(st.get("turn_prompts_seq", 0) or 0))
    st["modified_files"] = [{"path": str(hooked["proj"] / "tools" / "x.py"), "last_turn_seq": turn}]
    wg_core.write_state(SID, st)


def _rec_of(part):
    return next(v for k, v in wg_core.read_state(SID)["overview_hub"].items() if k.endswith(f"|{part}"))


def _next_user_turn():
    """下一個使用者回合（turn_prompts_seq 跟著進）：LOCATE_FIRST_EDIT_BLOCKS_ONCE 的那一輪只管第一次改檔的那個使用者回合。"""
    st = wg_core.read_state(SID) or {}
    st["turn_seq"] = int(st.get("turn_seq", 0) or 0) + 1
    st["turn_prompts_seq"] = st["turn_seq"]
    wg_core.write_state(SID, st)


def test_locate_hint_on_first_read_of_part_code_file_then_follow_it_no_block(hooked, post_read):
    """規則 LOCATE_HINT_ON_FIRST_READ：第一次讀到部位的程式檔 → 那則讀檔工具結果（PostToolUse，不是改檔的
    PreToolUse）附一行：交定位三行、寫在不寫檔指令的 # 註解、thinking 讀不到。AI 照做（回覆文字交三行）→ 第一個 Edit 不擋。
    改前讀檔結果只有導讀卡 → 紅。提示只在寫碼回合送（本回合已改過別的程式檔）。"""
    f1 = _mapped_world(hooked)
    _coding(hooked)
    ctx = post_read({"file_path": f1})
    hint = next(ln for ln in ctx.splitlines() if ln.startswith("[Guardian:OverviewHub] 改【戰鬥】的程式檔前"))
    assert "交定位三行" in hint
    assert "開頭的 `#` 註解" in hint and "（thinking 讀不到）" in hint and "照常用 Edit／Write" in hint
    assert "早一則" not in hint and "locate 欄" not in hint and "備援" not in hint   # 只教 # 註解一條路（DECL_HINT_KEEPS_EDIT_TOOLS）
    assert "戰鬥導讀" not in ctx                                                    # 讀檔結果只有提示、沒有卡（READ_TOUCH_NO_CARD）
    assert not [o for o in hooked["outputs"] if o]                                 # 還沒有任何 PreToolUse 輸出：提示在第一個 Edit 之前
    _say(hooked["tp"], THREE2)
    assert _edit(hooked, f1) is None                                                # 第一個 Edit：不擋，卡排進提醒、隨這次工具結果到
    pend = wg_core.read_state(SID)["remind_pending"]
    assert [h["rule"] for h in pend] == ["OVERVIEW_CARD_BEFORE_EDIT"]
    assert "戰鬥導讀" in pend[0]["extra"] and "導讀卡現在才送" in pend[0]["what"]
    assert _edit(hooked, f1) is None                                                # 卡到了、三行都有 → 不擋
    assert [e["first"] for e in _hint_events(hooked)] == [True]


def test_locate_hint_ignored_not_blocked_and_not_reminded_twice(hooked, post_read):
    """先讀、沒照做就改（規則 GATE_MODE_TABLE）：讀檔提示就是那一次提醒——沒交定位就改，第一輪過後不擋、
    不再提醒定位（提醒帳 remind_sent 已有這件；判定照舊留帳 edit_remind）。"""
    f1 = _mapped_world(hooked)
    _coding(hooked)
    assert "交定位三行" in post_read({"file_path": f1})
    assert _edit(hooked, f1)                                              # 第一次缺定位：擋這一輪（LOCATE_FIRST_EDIT_BLOCKS_ONCE）
    _next_user_turn()                                                     # 這一輪只管第一次改檔的那個使用者回合
    assert _edit(hooked, f1) is None                                      # 下一個使用者回合：不擋
    state = wg_core.read_state(SID)
    pending_rules = lambda st: [h["rule"] for h in st.get("remind_pending") or []]   # noqa: E731
    assert pending_rules(state) == ["OVERVIEW_CARD_BEFORE_EDIT"]                   # 等著送的只有卡，沒有定位的第二次提醒
    assert any(k.startswith("LOCATE_BEFORE_EDIT|") for k in state["remind_sent"])
    assert _edit(hooked, f1) is None
    assert pending_rules(wg_core.read_state(SID)) == ["OVERVIEW_CARD_BEFORE_EDIT"]
    assert len([o for o in hooked["outputs"] if o]) == 1                  # 只有第一次那一擋


def test_locate_hint_skips_non_code_second_read_located_and_short_for_next_part(hooked, post_read):
    """讀非程式檔（同部位的 .md）不送提示；同一部位第二次讀不重送；已交過定位的部位不送；本 session 第二個部位只點名、說格式同前；
    知識類部位（放 .py 也不算程式）不送。"""
    files = _two_part_world(hooked)
    notes = Path(files["Battle"]).with_name("notes.md")
    notes.write_text("# 筆記", encoding="utf-8")
    _coding(hooked)
    ctx = post_read({"file_path": str(notes)})
    assert "戰鬥導讀" not in ctx and "交定位" not in ctx                            # 非程式檔：只建紀錄，卡與提示都不送
    ctx = post_read({"file_path": files["Battle"]})
    assert "改【戰鬥】的程式檔前交定位三行" in ctx and "need_goal(action=set" not in ctx
    assert "交定位" not in post_read({"file_path": files["Battle"]})               # 同部位第二次讀
    assert "交定位" not in post_read({"command": f'cat "{files["Battle"]}"'}, tool="Bash")
    assert "交定位" not in post_read({"file_path": files["Docs"]})                 # 知識類部位
    ui = post_read({"file_path": files["UI"]})
    assert "[Guardian:OverviewHub] 改【介面】的程式檔前交定位三行（格式同前一則提示）。" in ui
    state = wg_core.read_state(SID)                                                 # 已交過定位的部位：不送
    rec = next(v for k, v in state["overview_hub"].items() if k.endswith("|介面"))
    rec.update(locate_hint="due", located=True)
    wg_core.write_state(SID, state)
    assert "交定位" not in post_read({"file_path": files["UI"]})
    assert [e["part"] for e in _hint_events(hooked)] == ["戰鬥", "介面"]


def test_locate_hint_not_sent_when_edit_injected_first(hooked, post_read):
    """改檔時才補注入的部位（第一次碰就是 Edit）：那則擋訊息已經講了要交什麼，之後再讀它的程式檔不另送提示。"""
    f1 = _mapped_world(hooked)
    _coding(hooked)
    assert _edit(hooked, f1)                                                        # 補注入導讀卡；第一次改缺定位擋一次，卡排進提醒隨下個工具結果送
    assert [h["rule"] for h in wg_core.read_state(SID)["remind_pending"]] == ["OVERVIEW_CARD_BEFORE_EDIT"]
    assert "交定位" not in post_read({"file_path": f1})
    assert not _hint_events(hooked)


def test_locate_hint_subagent_and_switches_off_unchanged(hooked, post_read, monkeypatch):
    """子代理讀的不送、也不吃掉主 session 那一次；v6 總開關關、OverviewHub 關 → 讀檔結果跟改前一樣（沒有提示）；
    開著 → 只要定位三行（同那時的擋訊息）。"""
    f1 = _mapped_world(hooked)
    _coding(hooked)
    assert "交定位" not in post_read({"file_path": f1}, agent_id="ag-1")
    monkeypatch.setenv("WG_V6", "0")
    off = post_read({"file_path": f1})
    assert "交定位" not in off
    monkeypatch.setenv("WG_V6", "1")
    assert "交定位" not in post_read({"file_path": f1}, config={"overview_hub": {"enabled": False}})
    three = post_read({"file_path": f1})
    hint = next(ln for ln in three.splitlines() if ln.startswith("[Guardian:OverviewHub] 改【戰鬥】的程式檔前"))
    assert "交定位三行：定位｜部位、定位｜根因層、定位｜前例" in hint and "need_goal" not in hint and "定位｜批判" not in hint
    assert len(_hint_events(hooked)) == 1


def test_locate_hint_not_sent_in_non_coding_turn_and_quota_kept(hooked, post_read):
    """規則 NON_CODING_TURN_NO_NUDGE：純問答回合——沒改過程式（只改文件）、這則 prompt 的關鍵字也不是寫碼類（turn_intent
    general）→ 讀部位的程式檔不送定位提示，一部位一次的額度不消耗（部位紀錄 locate_hint 留在 due、沒有 locate_hint 事件）；
    之後同回合改了碼再讀 → 提示照送、額度這時才用掉。走真的 PostToolUse。舊碼讀到就送 → 紅。"""
    f1 = _mapped_world(hooked)
    st = wg_core.read_state(SID) or {}
    st["modified_files"] = [{"path": str(hooked["proj"] / "README.md"), "last_turn_seq": 9}]   # 只改過文件
    st["turn_intent"] = "general"                                                            # 關鍵字也不是寫碼類
    wg_core.write_state(SID, st)
    ctx = post_read({"file_path": f1})
    assert "交定位" not in ctx and "戰鬥導讀" not in ctx
    assert _rec_of("戰鬥")["locate_hint"] == "due" and not _hint_events(hooked)
    assert "交定位" not in post_read({"file_path": f1})                               # 再讀還是不送、額度仍在
    _coding(hooked)
    hint = post_read({"file_path": f1})
    assert "交定位三行" in hint
    assert _rec_of("戰鬥")["locate_hint"] == "sent" and [e["first"] for e in _hint_events(hooked)] == [True]


def test_locate_hint_text_matches_what_gates_check():
    """提示跟擋講同一件事、同一個格式：點到擋訊息要的每一行（部位、根因層、前例），寫法管道用同一句
    DECL_VIA_COMMENT、宣告完照常用 Edit／Write（DECL_HINT_KEEPS_EDIT_TOOLS）；後續部位一行點名。"""
    three = wo.locate_read_hint("戰鬥", True)
    for piece in ("定位｜部位", "定位｜根因層", "定位｜前例", wo._rr.DECL_VIA_COMMENT, "thinking 讀不到", "照常用 Edit／Write"):
        assert piece in three, piece
    assert "\n" not in three and "定位三行" in three and "定位｜批判" not in three and "need_goal" not in three
    assert wo.locate_read_hint("介面", False) == "[Guardian:OverviewHub] 改【介面】的程式檔前交定位三行（格式同前一則提示）。"


if __name__ == "__main__":
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("LOCATE_HINT_CHECK PASS" if rc == 0 else "LOCATE_HINT_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
