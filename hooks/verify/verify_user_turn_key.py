"""verify_user_turn_key.py：使用者回合鍵（turn_prompts_seq）不掉（規則 USER_TURN_KEY_KEPT）。

做什麼：state 重建時回合編號與回合鍵照搬（session_start._CARRY_ON_REBUILD）；鍵還是不在（從零建）時，UserPromptSubmit 第一則進來的
訊息就算是同伴訊息也把鍵錨在這一則（ups_gates.track_turn_prompts）。鍵不在時 user_turn 退回逐則前進的 turn_seq，只進同伴訊息的
那段每則都被當成新使用者回合：實測長 session compact 重建 state 後，PickOne 每則同伴訊息都再問一次（turn 14／15／17／19／49…）。
正例：重建後連三則同伴訊息，每則都改了程式、到交付邊界 → PickOne 只問一次；重建前的回合鍵、回合編號照舊；從零建的 state 第一則
      同伴訊息就錨定，之後同伴訊息不前進、使用者打字照舊開新回合。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_user_turn_key.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_core  # noqa: E402
import wg_overview as wo  # noqa: E402
from handlers import session_start as ss  # noqa: E402
from handlers import stop as st  # noqa: E402
from handlers.ups_gates import track_turn_prompts  # noqa: E402
from wg_release_rules import user_turn  # noqa: E402

_SID = "sid-turn-key"
PEER = ('<cross-session-message from="uds:\\\\.\\pipe\\LOCAL\\cc-msg-x" from-name="console" from-mode="bypass">\n'
        "交付收到，下一項照做。\n</cross-session-message>")
_CFG = {"pick_one": {"enabled": True}}


def _ups(monkeypatch, state, prompt):
    """真的走 handle_user_prompt_submit（推進 turn_seq、turn_prompts 走真的 track_turn_prompts）；碰檔案與模型的依賴換空殼。"""
    from handlers import user_prompt_submit as ups
    import wg_friction
    monkeypatch.setattr(ups, "_ensure_state", lambda sid, inp, cfg: state)
    for name, fn in (("_ups_sentinel_check_and_arm", lambda *a: None), ("_ups_sentinel_clear", lambda sid: None),
                     ("build_context", lambda *a: None), ("_maybe_spawn_failure_extraction", lambda *a: None),
                     ("_update_topic_tracker", lambda *a: None),
                     ("reconcile_injection_after_trim", lambda *a: []), ("write_state", lambda sid, s: None),
                     ("output_json", lambda d: None), ("output_nothing", lambda: None)):
        monkeypatch.setattr(ups, name, fn)
    monkeypatch.setattr(ups, "run_pre_gates", lambda sid, s, cfg, clean, low, lines: track_turn_prompts(s, clean))
    monkeypatch.setattr(ups, "collect_matched_atoms", lambda *a: ([], {}, [], [], {}, [], "general", {}))
    monkeypatch.setattr(ups, "assemble_injection", lambda *a, **k: ([], {}))
    monkeypatch.setattr(ups, "_truncate_context_by_activation", lambda lines, *a: lines)
    monkeypatch.setattr(wo, "on_prompt", lambda *a, **k: None)
    monkeypatch.setattr(wg_friction, "record_correction", lambda *a: None)
    ups.handle_user_prompt_submit({"session_id": _SID, "prompt": prompt, "transcript_path": ""}, {"sync_keywords": []})


def _rebuilt(existing):
    """照 session_start 專案根指紋變了的重建分支（compact／resume）做一份新 state：new_state 後走真的 carry_on_rebuild。"""
    new = wg_core.new_state(_SID, existing["session"]["cwd"], "compact")
    ss.carry_on_rebuild(existing, new)
    return new


def _before_rebuild(cwd):
    """重建前：使用者第 37 回合打字開工，之後同伴訊息讓 turn_seq 走到 40；PickOne 上次是第 30 個使用者回合問的
    （帳本現在會照搬：第 37 回合還沒問過，重建後才該問一次）。"""
    return {"session": {"id": _SID, "cwd": str(cwd)}, "phase": "working", "turn_seq": 40, "turn_prompts_seq": 37,
            "user_turn_count": 5, "turn_open": False, "turn_typed": False, "turn_prompts": [],
            "pick_one": {_SID: {"asked_turn": 30, "asked_uturn": 30}}}


@pytest.fixture
def code_file(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "append_guard_log", lambda *a, **k: None)
    f = tmp_path / "proj" / "src" / "pricing.py"
    f.parent.mkdir(parents=True)
    f.write_text("def price(x):\n    return x\n", encoding="utf-8")
    return f


def test_rebuilt_state_three_peer_messages_pick_one_asks_once(monkeypatch, code_file):
    """規則 USER_TURN_KEY_KEPT：compact 重建 state 後連三則同伴訊息、每則都改了程式又交付 → 同一個使用者回合，PickOne 只問一次。
    舊碼重建時回合鍵沒帶過去、turn_seq 歸零，user_turn 跟著每則同伴訊息前進，三則各問一次。"""
    state = _rebuilt(_before_rebuild(code_file.parent.parent))
    asked = []
    for _ in range(3):
        _ups(monkeypatch, state, PEER)
        mods = [{"path": str(code_file), "session_id": _SID, "turn_seq": state["turn_seq"], "last_turn_seq": state["turn_seq"]}]
        if st._pick_one_prompt(state, _SID, mods, True, _CFG):
            asked.append(state["turn_seq"])
    assert len(asked) == 1, (asked, state.get("turn_prompts_seq"), state.get("turn_seq"))
    assert user_turn(state, state["turn_seq"]) == 37


def test_rebuild_keeps_turn_key_and_numbering():
    """重建前已有回合鍵 → 重建後鍵值、回合編號、回合開關照舊（舊碼：turn_seq 歸零、回合鍵不見）。"""
    old = _before_rebuild(Path("c:/proj"))
    new = _rebuilt(old)
    assert {k: new.get(k) for k in ("turn_seq", "turn_prompts_seq", "user_turn_count", "turn_open", "turn_typed")} == \
           {"turn_seq": 40, "turn_prompts_seq": 37, "user_turn_count": 5, "turn_open": False, "turn_typed": False}
    assert user_turn(new, new["turn_seq"]) == 37


def test_rebuild_floors_turn_seq_to_modified_files_turns():
    """重建前的 state 沒有 turn_seq（更舊版本沒搬），modified_files 的 last_turn_seq 到 11 → 重建後 turn_seq 墊到 11
    （舊碼：0，各閘的問過／放行全記第 0 回合，PickOne 同一批改動連問）。有 turn_seq 且比改檔回合大 → 照舊不動。"""
    mods = [{"path": "c:/proj/a.py", "last_turn_seq": 2}, {"path": "c:/proj/b.py", "last_turn_seq": 11, "turn_seq": 11},
            {"path": "c:/proj/c.py", "last_turn_seq": "junk"}]
    old = {"session": {"id": _SID, "cwd": "c:/proj"}, "phase": "working", "modified_files": mods}
    assert _rebuilt(old)["turn_seq"] == 11
    reuse = {"turn_seq": 1, "modified_files": mods}
    ss.floor_turn_seq(reuse)
    assert reuse["turn_seq"] == 11
    bigger = {"turn_seq": 40, "modified_files": mods}
    ss.floor_turn_seq(bigger)
    assert bigger["turn_seq"] == 40


def test_rebuild_carries_event_seq_and_gate_ledgers():
    """重建後收據序號接著走（event_seq），各閘的問過／放行／擋過帳本照搬：使用者剛選的「放行這一回合」與收據
    不因壓縮重建消失（舊碼：只搬回合鍵，這些全部重來）。"""
    old = _before_rebuild(Path("c:/proj"))
    ledgers = {"event_seq": 95,
               "user_released": {_SID: {"reconcile": 37}}, "pending_release": {_SID: {"reconcile": {"turn": 37}}},
               "verify_receipts": {_SID: [{"seq": 90, "cmd": "pytest -q"}]},
               "reconcile_gate_turn": {_SID: {"turn": 37, "count": 1}}, "cleanup_gate_turn": {_SID: 37}}
    new = _rebuilt({**old, **ledgers})
    assert {k: new.get(k) for k in ledgers} == ledgers
    assert new["pick_one"] == old["pick_one"]


def test_missing_key_anchored_at_first_peer_message_then_typing_opens_new_turn(monkeypatch):
    """鍵不在（state 從零建）、第一則是同伴訊息 → 鍵錨在這一則；之後同伴訊息不前進；使用者打字才開新回合（舊碼：鍵一直不在）。"""
    state = wg_core.new_state(_SID, "c:/proj", "startup")
    _ups(monkeypatch, state, PEER)
    assert state["turn_seq"] == 1 and state.get("turn_prompts_seq") == 1 and "user_turn_count" not in state
    _ups(monkeypatch, state, PEER)
    _ups(monkeypatch, state, "<task-notification>背景任務完成</task-notification>")
    assert state["turn_seq"] == 3 and user_turn(state, state["turn_seq"]) == 1
    _ups(monkeypatch, state, "好，接著改報表")
    assert state["turn_seq"] == 4 and user_turn(state, state["turn_seq"]) == 4 and state["turn_prompts"] == ["好，接著改報表"]


def test_v6_off_does_not_anchor_missing_key():
    """守門總開關關（照 9e476fd0）：鍵不在也不錨，同伴訊息照舊只開續跑回合。"""
    state = wg_core.new_state(_SID, "c:/proj", "startup")
    track_turn_prompts(state, PEER, v6=False)
    assert "turn_prompts_seq" not in state and state["turn_typed"] is False
    track_turn_prompts(state, PEER, v6=True)
    assert state["turn_prompts_seq"] == 1
