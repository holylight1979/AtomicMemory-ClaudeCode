"""verify_closing_round.py：收尾只跑一輪（hooks/wg_closing_round.py 與它接到的 PostToolBatch、Stop 段）。

做什麼：
  READING_PATH_EARLY_START     改了程式檔的那批跑完就交背景量；同一批不重量、量測中又改先記 pending；開關關不起跑。
  TURN_JUDGMENT_PRE_CLOSE      量好的拐彎判斷結果在交收尾檢核那批附上，Stop 不再送；還有一批在量就不附。
  PICK_ONE_PRE_CLOSE           交收尾檢核那批、或改過程式之後測試跑綠那批附「順手看到最該修」並記問過，Stop 不再送（不再續跑一輪）；
                               同回合第二批綠不重問、沒改程式只跑測試不問；開關關照舊由 Stop 送。
  PICK_ONE_WITH_TURN_JUDGMENT  Stop 的拐彎判斷擋下時，最該修同一則一起問；下一次收尾不再另送。
每一案拿改動前的 main（5ccf44d2／e39061a0）回放都是紅：舊碼 PostToolBatch 不做這些事、Stop 照舊兩輪。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_closing_round.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wg_reading_path as rph  # noqa: E402
from handlers import post_tool_batch as ptb  # noqa: E402
from handlers import stop as st  # noqa: E402
from verify_pick_one import _PASS_CFG, _SID, _mod, stop_run, world  # noqa: E402,F401  共用的假專案與 Stop 驅動

AEC = {"tool_name": "mcp__workflow-guardian__anti_evasion_report", "tool_input": {"a": "無"}}


@pytest.fixture(autouse=True)
def _block_mode(monkeypatch):
    """規則 GATE_MODE_TABLE：送法只讀 wg_release_rules.RULE_MODE。這個檔的案例驗的是判定與擋訊息內容，把送法釘成 block 讓它們照驗；v6 預設的提醒送法（Stop 只留帳、提醒掛改檔那則工具結果）由 verify_gate_mode_stop.py 驗。"""
    import wg_release_rules as _rr
    monkeypatch.setattr(_rr, "mode_of", lambda rule: _rr.BLOCK)
TJ_NOTE = ("[Guardian:ReadingPath] 第 5 回合改動對閱讀路徑的影響（背景量完；尺不是判決，只量不擋）：\n"
           "  要人看的 1 條（門檻：拐彎 ≥2）：\n    函式 cli.py::by_product｜拐彎 3\n    拐彎判斷｜cli.py::by_product｜…")


def _batch(state, calls, config, capsys, sid=_SID, **extra):
    """跑一次 PostToolBatch（state 就地改；extra 蓋進 hook 輸入，例 transcript_path）→ 送出的 additionalContext（沒送回空字串）。"""
    ptb._ensure_state = lambda *a, **k: state
    with pytest.raises(SystemExit):
        ptb.handle_post_tool_batch({"session_id": sid, "tool_calls": calls, **extra}, config)
    out = capsys.readouterr().out.strip()
    return json.loads(out.splitlines()[-1])["hookSpecificOutput"]["additionalContext"] if out else ""


@pytest.fixture
def batch_env(monkeypatch, tmp_path):
    """PostToolBatch 驅動：不寫 state 檔、背景量測不起行程（記下起了幾次）、工作檔落 tmp。"""
    spawned: list = []
    monkeypatch.setattr(ptb, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(ptb, "_ensure_state", ptb._ensure_state)          # 測完還原
    monkeypatch.setattr(rph, "JOB_DIR", tmp_path / "rp-jobs")
    monkeypatch.setattr(rph, "_spawn_worker", lambda path: spawned.append(path))
    return spawned


def _code_state(path, sid=_SID, **extra):
    return {"modified_files": [{"path": str(path), "session_id": sid, "turn_seq": 5, "last_turn_seq": 5}],
            "turn_seq": 5, "turn_prompts_seq": 5, **extra}


# ─── READING_PATH_EARLY_START ───────────────────────────────────────────────────

def test_reading_path_early_start_on_code_batch(batch_env, tmp_path, capsys):
    """規則 READING_PATH_EARLY_START：改了程式檔那批跑完就交背景量（舊碼要等第一次收尾才起跑，第一次收尾沒數據、多擋一輪）；
    同一批再跑一批不重量；量測中又改了先記 pending、不另起；開關關不起跑。"""
    code = tmp_path / "proj" / "cli.py"
    code.parent.mkdir(parents=True)
    code.write_text("x = 1\n", encoding="utf-8")
    state = _code_state(code)
    write = [{"tool_name": "Write", "tool_input": {"file_path": str(code)}}]
    _batch(state, write, _PASS_CFG, capsys)
    rec = state["reading_path"][_SID]
    assert len(batch_env) == 1 and rec.get("job"), "改完程式那批就該交背景量"
    _batch(state, [{"tool_name": "Read", "tool_input": {}}], _PASS_CFG, capsys)
    assert len(batch_env) == 1, "同一批不重量"
    code.write_text("x = 1\ny = 2\n", encoding="utf-8")
    _batch(state, write, _PASS_CFG, capsys)
    assert len(batch_env) == 1 and rec.get("pending") is True, "量測中又改：先記著、量完再量最新的"
    off = _code_state(code)
    _batch(off, write, {**_PASS_CFG, "reading_path": {"early_start": False}}, capsys)
    assert len(batch_env) == 1 and not (off.get("reading_path") or {}).get(_SID, {}).get("job"), "開關關：照舊等收尾"


def test_reading_path_early_result_kept_for_stop(batch_env, tmp_path, capsys):
    """背景交了結果（有一條超線）、還沒到收尾 → 收下存著（EARLY_NOTE），Stop 的 reading_path_note 送一次；Stop 收到新的一批就只送新的。"""
    code = tmp_path / "proj" / "cli.py"
    code.parent.mkdir(parents=True)
    code.write_text("x = 1\n", encoding="utf-8")
    state = _code_state(code)
    _batch(state, [{"tool_name": "Write", "tool_input": {"file_path": str(code)}}], _PASS_CFG, capsys)
    job = state["reading_path"][_SID]["job"]
    item = {"kind": "函式", "name": "cli.py::by_product", "keys": ["cli.py::by_product"], "nums": "拐彎 3", "fp": "f"}
    rph.write_result(Path(job["out"]), {"text": TJ_NOTE, "judgment": [item]})
    _batch(state, [{"tool_name": "Bash", "tool_input": {"command": "pytest"}}], _PASS_CFG, capsys)
    rec = state["reading_path"][_SID]
    early = rec.get(rph.EARLY_NOTE) or ""
    assert early.startswith(TJ_NOTE) and rph.JUDGMENT_QUESTION in early and not rec.get("job"), early
    note, _ = rph.reading_path_note(state, _SID, _PASS_CFG, spawn=lambda p: None)
    assert note == early and rph.EARLY_NOTE not in rec
    rec[rph.EARLY_NOTE] = "舊的一批"
    rec["job"] = {"path": str(tmp_path / "j.job.json"), "out": str(tmp_path / "j.result.json"), "at": 0, "budget": 300, "turn": 5}
    rph.write_result(tmp_path / "j.result.json", {"text": None, "judgment": []})          # 新的一批沒超線
    note, _ = rph.reading_path_note(state, _SID, _PASS_CFG, spawn=lambda p: None)
    assert note is None, "收到新的一批就算沒超線，舊的那份也不送"


# ─── TURN_JUDGMENT_PRE_CLOSE ────────────────────────────────────────────────────

def _measured(state, path):
    """當成改完那批已經量完、結果先存著：指紋對上、沒有在量。"""
    rec = state.setdefault("reading_path", {}).setdefault(_SID, {})
    rec.update({rph.EARLY_NOTE: TJ_NOTE, "early_fp": json.dumps(rph._fingerprint([str(path)]), ensure_ascii=False),
                "owed": {"items": [{"kind": "函式", "name": "cli.py::by_product", "nums": "拐彎 3", "fp": "f"}], "turn": 5}})
    return rec


def test_turn_judgment_pre_close_attached_once(batch_env, tmp_path, capsys):
    """規則 TURN_JUDGMENT_PRE_CLOSE：交收尾檢核那批附上量好的結果（舊碼這批什麼都不送，拐彎判斷要等 Stop 擋下才問）；
    取走後 Stop 不再送；欠項留著給 Stop 核對。還有一批在量 → 不附。"""
    code = tmp_path / "proj" / "cli.py"
    code.parent.mkdir(parents=True)
    code.write_text("x = 1\n", encoding="utf-8")
    state = _code_state(code)
    rec = _measured(state, code)
    ctx = _batch(state, [AEC], _PASS_CFG, capsys)
    assert TJ_NOTE.splitlines()[0] in ctx and "拐彎判斷｜" in ctx
    assert rph.EARLY_NOTE not in rec and rec["owed"]["items"], "取走結果、欠項照留"
    note, _ = rph.reading_path_note(state, _SID, _PASS_CFG, spawn=lambda p: None)
    assert not note, "附過就不由 Stop 再送"
    busy = _code_state(code)
    _measured(busy, code)["job"] = {"path": "j", "out": str(tmp_path / "none.json"), "at": 9e12, "budget": 300, "turn": 5}
    assert "拐彎判斷｜" not in _batch(busy, [AEC], _PASS_CFG, capsys), "還有一批在量：留給 Stop"


# ─── PICK_ONE_PRE_CLOSE ─────────────────────────────────────────────────────────

def test_pick_one_pre_close_then_stop_does_not_resend(batch_env, stop_run, monkeypatch, capsys):
    """規則 PICK_ONE_PRE_CLOSE：交收尾檢核那批附「順手看到最該修」、記問過（舊碼要等第一次收尾用 additionalContext 讓對話續跑一輪、
    AI 重寫整則收尾）；之後 Stop 不再送。開關關：這批不附，Stop 照舊送。"""
    proj, run = stop_run
    damage = proj / "Game" / "Battle" / "Damage.cs"
    state = {"modified_files": [_mod(damage)], "turn_seq": 5, "session": {"cwd": str(proj)}}
    ctx = _batch(state, [AEC], _PASS_CFG, capsys)
    assert "[Guardian:PickOne]" in ctx and "【戰鬥】" in ctx and "為什麼不是數字最高的那個：" in ctx
    assert state["pick_one"][_SID]["asked_uturn"] == 5
    out, _, _ = run("改好了，全部完成。", [_mod(damage)], pick_one=state["pick_one"])
    assert "PickOne" not in out, "收尾前問過：Stop 不再續跑一輪"
    off_cfg = {**_PASS_CFG, "pick_one": {"enabled": True, "pre_close": False}}
    off = {"modified_files": [_mod(damage)], "turn_seq": 5, "session": {"cwd": str(proj)}}
    assert "PickOne" not in _batch(off, [AEC], off_cfg, capsys)
    out, _, ev = run("改好了，全部完成。", [_mod(damage)], config=off_cfg)
    assert "[Guardian:PickOne]" in out and ev[-1]["event"] == "asked", "開關關：舊送法照舊"


def test_reconcile_batch_is_pre_close_too(batch_env, stop_run, tmp_path, capsys):
    """PICK_ONE_PRE_CLOSE／TURN_JUDGMENT_PRE_CLOSE：完整對照（need_goal action=reconcile）那批也是收尾前的附著點（無頭實跑兩跑 AI 都沒交
    收尾檢核，最後一個收尾類工具是 reconcile）；need_goal 其他動作（set、add）不是。"""
    proj, _ = stop_run
    damage = proj / "Game" / "Battle" / "Damage.cs"
    state = {"modified_files": [_mod(damage)], "turn_seq": 5, "session": {"cwd": str(proj)}}
    _measured(state, damage)
    for action in ("set", "add"):
        ctx = _batch(state, [{"tool_name": "mcp__workflow-guardian__need_goal", "tool_input": {"action": action}}], _PASS_CFG, capsys)
        # 不是收尾那批：不附最該修、不附量好的結果本文；背景量完的欠項一行提醒（TURN_JUDGMENT_REQUIRED，REMIND_ON_PRIOR_RESULT）照送
        assert "PickOne" not in ctx and TJ_NOTE.splitlines()[0] not in ctx, action
    ctx = _batch(state, [{"tool_name": "mcp__workflow-guardian__need_goal", "tool_input": {"action": "reconcile"}}], _PASS_CFG, capsys)
    assert "[Guardian:PickOne]" in ctx and "拐彎判斷｜" in ctx


def test_pick_one_not_on_ordinary_batch(batch_env, stop_run, capsys):
    """沒交收尾檢核、也沒有跑綠收據的批次不附（還在工作中，交付邊界還沒到）。"""
    proj, _ = stop_run
    state = {"modified_files": [_mod(proj / "Game" / "Battle" / "Damage.cs")], "turn_seq": 5, "session": {"cwd": str(proj)}}
    assert "PickOne" not in _batch(state, [{"tool_name": "Bash", "tool_input": {"command": "pytest"}}], _PASS_CFG, capsys)
    assert not (state.get("pick_one") or {}).get(_SID, {}).get("asked_uturn")


PYTEST_CALL = [{"tool_name": "Bash", "tool_input": {"command": "python -m pytest -q tests"}}]


def _receipt(seq, verdict="PASS", exit_code=0, cmd="python -m pytest -q tests"):
    """post_tool_use 記進 state verify_receipts 的一筆（seq＝session 內事件序號）。"""
    return {"seq": seq, "turn_seq": 5, "tool": "Bash", "cmd": cmd, "exit_code": exit_code,
            "sentinels": [{"name": "PYTEST", "verdict": verdict, "kv": {}}]}


def test_pick_one_on_test_green_batch_then_stop_ledger_silent(batch_env, stop_run, monkeypatch, capsys):
    """規則 PICK_ONE_PRE_CLOSE 的另一個交付邊界（實測 010：收尾檢核提醒關著、AI 從不交收尾檢核，那一問結構上送不到）：
    改了程式之後測試跑綠那批 → 附「順手看到最該修」、記問過（via=test_green）；同一個使用者回合再來一批綠不重問；
    之後 Stop 看到問過，不送也不留帳第二次。紅的那批不問。"""
    proj, run = stop_run
    damage = proj / "Game" / "Battle" / "Damage.cs"
    logs: list = []
    import wg_harvest as wh
    monkeypatch.setattr(wh, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    state = {"modified_files": [_mod(damage)], "turn_seq": 5, "turn_prompts_seq": 5, "session": {"cwd": str(proj)},
             "verify_receipts": {_SID: [_receipt(1, "FAIL", 1)]}}
    assert "PickOne" not in _batch(state, PYTEST_CALL, _PASS_CFG, capsys), "紅的那批：還沒到交付邊界"
    state["verify_receipts"][_SID].append(_receipt(2))
    ctx = _batch(state, PYTEST_CALL, _PASS_CFG, capsys)
    assert "[Guardian:PickOne]" in ctx and "【戰鬥】" in ctx and "為什麼不是數字最高的那個：" in ctx
    assert state["pick_one"][_SID]["asked_uturn"] == 5 and state["remind_receipt_seq"][_SID] == 2
    asked = [p for g, p in logs if g == "pick_one" and p.get("event") == "asked"]
    assert len(asked) == 1 and asked[0]["via"] == "test_green"
    state["verify_receipts"][_SID].append(_receipt(3))
    assert "PickOne" not in _batch(state, PYTEST_CALL, _PASS_CFG, capsys), "同一回合第二批綠：不重問"
    assert len([p for g, p in logs if g == "pick_one" and p.get("event") == "asked"]) == 1
    out, _, ev = run("改好了，全部完成。", [_mod(damage)], pick_one=state["pick_one"], turn_prompts_seq=5)
    assert "PickOne" not in out and not [p for p in ev if p.get("event") in ("asked", "remind")], (out, run.err)


def test_pick_one_not_on_green_without_code_change(batch_env, stop_run, capsys):
    """沒改程式只跑測試（或改的是文件）→ 跑綠那批不問；收據序號照記，下次不重判同一批。"""
    proj, _ = stop_run
    state = {"modified_files": [_mod(proj / "docs" / "readme.md")], "turn_seq": 5, "session": {"cwd": str(proj)},
             "verify_receipts": {_SID: [_receipt(1)]}}
    assert "PickOne" not in _batch(state, PYTEST_CALL, _PASS_CFG, capsys)
    assert not (state.get("pick_one") or {}).get(_SID, {}).get("asked_uturn") and state["remind_receipt_seq"][_SID] == 1


# ─── PICK_ONE_WITH_TURN_JUDGMENT ────────────────────────────────────────────────

def test_pick_one_rides_turn_judgment_block(stop_run, monkeypatch):
    """規則 PICK_ONE_WITH_TURN_JUDGMENT：沒走到收尾前附著（例：沒交收尾檢核），第一次收尾拐彎判斷擋下 → 最該修同一則一起問、記問過；
    下一次收尾不再另送（舊碼擋完之後還要再續跑一輪問最該修，共兩輪）。"""
    proj, run = stop_run
    damage = proj / "Game" / "Battle" / "Damage.cs"
    block = "[Guardian:ReadingPath] TURN_JUDGMENT_REQUIRED：缺 1 條\n  拐彎判斷｜<名稱>｜…"
    monkeypatch.setattr(st, "turn_judgment_note", lambda *a, **k: (block, True))
    out, state, ev = run("改好了，全部完成。", [_mod(damage)])
    reason = json.loads(out.strip().splitlines()[-1]).get("reason", "")
    assert "TURN_JUDGMENT_REQUIRED" in reason and "[Guardian:PickOne]" in reason, run.err
    assert ev and ev[-1]["event"] == "asked"
    monkeypatch.setattr(st, "turn_judgment_note", lambda *a, **k: (None, False))
    out2, _, _ = run("改好了，全部完成。\n拐彎判斷｜…", [_mod(damage)], pick_one=state["pick_one"])
    assert "PickOne" not in out2

