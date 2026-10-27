"""verify_closing_round.py：收尾只跑一輪、第二意見背景跑（hooks/wg_closing_round.py 與它接到的 PostToolBatch、Stop 段）。

做什麼：
  READING_PATH_EARLY_START     改了程式檔的那批跑完就交背景量；同一批不重量、量測中又改先記 pending；開關關不起跑。
  TURN_JUDGMENT_PRE_CLOSE      量好的拐彎判斷結果在交收尾檢核那批附上，Stop 不再送；還有一批在量就不附。
  PICK_ONE_PRE_CLOSE           交收尾檢核那批附「順手看到最該修」並記問過，Stop 不再送（不再續跑一輪）；開關關照舊由 Stop 送。
  PICK_ONE_WITH_TURN_JUDGMENT  Stop 的拐彎判斷擋下時，最該修同一則一起問；下一次收尾不再另送。
  SECOND_OPINION_BACKGROUND    第二意見閘的擋訊息寫 start 後不用等；MCP 端 start 的下一步與 result 的說明同一個說法。
  SECOND_OPINION_DONE_NOTICE   開了的 job 跑完、AI 還沒取回 → 下一批工具回應或收尾提醒一次；取過、開始看守前就跑完的不提醒。
每一案拿派工時的 main（5ccf44d2／e39061a0）回放都是紅：舊碼 PostToolBatch 不做這些事、Stop 照舊兩輪、擋訊息寫直接呼叫 result 等結果。
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
from verify_g9_second_opinion import DONE, JOB, SID as SO_SID, WAIT_TEXT, _feedback, _files, drive  # noqa: E402,F401

AEC = {"tool_name": "mcp__workflow-guardian__anti_evasion_report", "tool_input": {"a": "無"}}
TJ_NOTE = ("[Guardian:ReadingPath] 第 5 回合改動對閱讀路徑的影響（背景量完；尺不是判決，只量不擋）：\n"
           "  要人看的 1 條（門檻：拐彎 ≥2）：\n    函式 cli.py::by_product｜拐彎 3\n    拐彎判斷｜cli.py::by_product｜…")


def _batch(state, calls, config, capsys, sid=_SID):
    """跑一次 PostToolBatch（state 就地改）→ 送出的 additionalContext（沒送回空字串）。"""
    ptb._ensure_state = lambda *a, **k: state
    with pytest.raises(SystemExit):
        ptb.handle_post_tool_batch({"session_id": sid, "tool_calls": calls}, config)
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
    """背景交了結果、還沒到收尾 → 收下存著（EARLY_NOTE），Stop 的 reading_path_note 送一次；Stop 收到新的一批就只送新的。"""
    code = tmp_path / "proj" / "cli.py"
    code.parent.mkdir(parents=True)
    code.write_text("x = 1\n", encoding="utf-8")
    state = _code_state(code)
    _batch(state, [{"tool_name": "Write", "tool_input": {"file_path": str(code)}}], _PASS_CFG, capsys)
    job = state["reading_path"][_SID]["job"]
    rph.write_result(Path(job["out"]), {"text": TJ_NOTE, "judgment": []})
    _batch(state, [{"tool_name": "Bash", "tool_input": {"command": "pytest"}}], _PASS_CFG, capsys)
    rec = state["reading_path"][_SID]
    assert rec.get(rph.EARLY_NOTE) == TJ_NOTE and not rec.get("job")
    note, _ = rph.reading_path_note(state, _SID, _PASS_CFG, spawn=lambda p: None)
    assert note == TJ_NOTE and rph.EARLY_NOTE not in rec
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


def test_pick_one_not_on_ordinary_batch(batch_env, stop_run, capsys):
    """沒交收尾檢核的批次不附（還在工作中，交付邊界還沒到）。"""
    proj, _ = stop_run
    state = {"modified_files": [_mod(proj / "Game" / "Battle" / "Damage.cs")], "turn_seq": 5, "session": {"cwd": str(proj)}}
    assert "PickOne" not in _batch(state, [{"tool_name": "Bash", "tool_input": {"command": "pytest"}}], _PASS_CFG, capsys)
    assert not (state.get("pick_one") or {}).get(_SID, {}).get("asked_uturn")


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


# ─── SECOND_OPINION_BACKGROUND ──────────────────────────────────────────────────

def test_second_opinion_background_hint_and_mcp_agree(drive, capsys, tmp_path):
    """規則 SECOND_OPINION_BACKGROUND：擋訊息寫 start 後不用等、收尾還在跑寫等第二意見｜<job_id>（舊碼寫直接呼叫 result 等結果，
    收尾卡在 Codex 跑完，live 帳中位數 115 秒）；MCP 端 start 的下一步、result 的說明同一個說法，兩邊不打架。"""
    reason, _state, _logs = drive(DONE, capsys, files=_files(tmp_path, 5))
    assert "start 後不用等結果" in reason and "等第二意見｜<job_id>" in reason and "不算宣告完成" in reason
    assert "直接呼叫 second_opinion_result，它會等到有結果" not in reason
    js = HOOKS_DIR.parent / "tools" / "workflow-guardian-mcp" / "lib"
    start_js = (js / "second-opinion.js").read_text(encoding="utf-8")
    desc_js = (js / "mcp.js").read_text(encoding="utf-8")
    assert "不用守著等" in start_js and "等第二意見｜" in start_js and "那次不算宣告完成" in start_js
    assert "下一步：直接呼叫 second_opinion_result" not in start_js
    assert "跑完了馬上回" in desc_js and "要結果時再呼叫" in desc_js


# ─── SECOND_OPINION_DONE_NOTICE ─────────────────────────────────────────────────

def _job_dir(root, job, status):
    d = root / job
    d.mkdir(parents=True, exist_ok=True)
    (d / "status.json").write_text(json.dumps({"job_id": job, "status": status}), encoding="utf-8")


def test_second_opinion_done_notice_once_per_job(batch_env, monkeypatch, tmp_path, capsys):
    """規則 SECOND_OPINION_DONE_NOTICE：這批開了第二意見 → 看守；跑完、還沒取回 → 下一批提醒一次（舊碼沒有這條，AI 只能守著 result 等）；
    同一個 job 不再提醒；這批自己取過的不提醒；開始看守前就跑完的不提醒。"""
    import wg_closing_round as cr
    root = tmp_path / "so-jobs"
    monkeypatch.setattr(cr, "SO_JOB_ROOT", root)
    sid = "abcd1234-x"
    old, job, got = (f"20261027-10000{i}-abcd1234-stage-review" for i in range(3))
    _job_dir(root, old, "done")
    state = {"turn_seq": 5}
    start = [{"tool_name": "mcp__workflow-guardian__second_opinion_start", "tool_input": {"kind": "stage-review"}}]
    _job_dir(root, job, "running")
    assert _batch(state, start, _PASS_CFG, capsys, sid=sid) == ""
    assert state["second_opinion_watch"][sid]["running"] == [job], "跑完的舊 job 不看守"
    _job_dir(root, job, "done")
    ctx = _batch(state, [{"tool_name": "Bash", "tool_input": {}}], _PASS_CFG, capsys, sid=sid)
    assert f"第二意見 {job} 跑完了（done）" in ctx and "second_opinion_result" in ctx and old not in ctx
    assert _batch(state, [{"tool_name": "Bash", "tool_input": {}}], _PASS_CFG, capsys, sid=sid) == "", "同一個 job 只提醒一次"
    _job_dir(root, got, "running")
    _batch(state, start, _PASS_CFG, capsys, sid=sid)
    _job_dir(root, got, "done")
    fetch = [{"tool_name": "mcp__workflow-guardian__second_opinion_result", "tool_input": {"job_id": got}}]
    assert _batch(state, fetch, _PASS_CFG, capsys, sid=sid) == "", "這批自己取過：不提醒"
    assert not state["second_opinion_watch"][sid]["on"]
    off = {"turn_seq": 5}
    _batch(off, start, {**_PASS_CFG, "second_opinion": {"auto": {"background": False}}}, capsys, sid=sid)
    assert "second_opinion_watch" not in off, "開關關：不看守"


def test_second_opinion_waiting_close_then_stop_notices(drive, capsys, tmp_path, monkeypatch):
    """收尾寫了等第二意見｜<job_id> → Stop 把它記進看守；之後的收尾發現它跑完、本回合沒取回 → 同一則 additionalContext 提醒取回。"""
    import wg_closing_round as cr
    root = tmp_path / "so-jobs"
    monkeypatch.setattr(cr, "SO_JOB_ROOT", root)
    reason, state, _ = drive(DONE, capsys, files=_files(tmp_path, 5))
    _feedback(drive, reason)
    drive.tx.opinion(status="")
    _job_dir(root, JOB, "running")
    drive(WAIT_TEXT, capsys, state=state)
    assert JOB in state["second_opinion_watch"][SO_SID]["running"]
    _job_dir(root, JOB, "done")
    drive.tx.user("先看一下其他的")
    with pytest.raises(SystemExit):
        st.handle_stop({"session_id": SO_SID, "cwd": "", "transcript_path": str(drive.tx.path),
                        "last_assistant_message": "看過了。"}, {"reconcile_gate": {"enabled": False},
                                                              "verify_scope": {"enabled": False}, "sync_reminder": {"enabled": False},
                                                              "atom_audit": {"enabled": False}, "aec": {"scan_report_gate": False}})
    out = capsys.readouterr().out.strip()
    ctx = json.loads(out.splitlines()[-1])["hookSpecificOutput"]["additionalContext"]
    assert f"第二意見 {JOB} 跑完了（done）" in ctx
