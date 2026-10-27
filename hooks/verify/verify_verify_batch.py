"""verify_verify_batch.py — PreToolUse 驗證批次閘（hooks/wg_verify_batch.py）。

規則 VERIFY_FULL_RUN_NEEDS_USER_ORDER：會拖時間的整組驗證（run_verify.py 不帶參數、pytest 沒點名檔；且上次耗時 ≥ slow_run_s
  或測試檔 ≥ large_suite_files）要本回合使用者原話有口令；背景通知（task-notification）內文不算使用者原話。
  不拖時間（含耗時不知道、檔數沒到）的整組沒口令也放行、留帳 reason=small。
規則 VERIFY_SAME_BATCH_ALREADY_GREEN：同一組指令、上次收據綠、之後沒改檔 → 擋「這批改動已驗證過」；上次紅或之後有改檔 → 放行。
規則 VERIFY_BATCH_BLOCK_ONCE_PER_TURN：同一個使用者回合同一條規則最多擋 1 次，第 2 次放行、留帳 released。
解析不了的指令（heredoc／eval／bash -c）放行不留帳；guard.verify_batch.enabled=false 整閘不動。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_verify_batch.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import wg_core  # noqa: E402
import wg_verify_batch as vb  # noqa: E402

SID = "sid-vb"
FULL = "python -X utf8 -m pytest -q"
TARGETED = "python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_a.py"
CFG = {"guard": {"verify_batch": {"enabled": True}}}


@pytest.fixture
def log(tmp_path, monkeypatch):
    """guard log 與 state 寫入都落 tmp；回讀 guard-verify_batch.jsonl。"""
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path / "Logs")
    monkeypatch.setattr(wg_core, "write_state", lambda sid, state: None)

    def _read():
        p = tmp_path / "Logs" / "guard-verify_batch.jsonl"
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
    return _read


def _state(*prompts, turn=3, mods=(), receipts=()):
    return {
        "session": {"id": SID}, "turn_seq": turn, "turn_prompts_seq": turn,
        "recent_user_prompts": list(prompts), "turn_prompts": list(prompts),
        "modified_files": [{"path": p, "session_id": SID, "last_seq": s, "last_at": at, "turn_seq": turn, "last_turn_seq": turn}
                           for p, s, at in mods],
        "verify_receipts": {SID: list(receipts)},
    }


def _receipt(cmd, seq, at, green=True):
    return {"at": at, "seq": seq, "turn_seq": 2, "tool": "Bash", "cmd": cmd, "cmd_full": True,
            "sentinels": [{"name": "PYTEST", "verdict": "PASS" if green else "FAIL"}], "exit_code": 0 if green else 1}


def _slow_self_receipt(seconds, green=False):
    """整組指令（pytest -q）的自寫收據，跑了 seconds 秒；預設紅（只用它的耗時，不讓 SAME 規則先擋）。"""
    return {"source": "run_verify_self", "argv": ["python", "-m", "pytest", "-q"], "cmd": "python -m pytest -q",
            "exit_code": 0 if green else 1, "failed": 0 if green else 2,
            "started_at": "2026-10-27T01:00:00+00:00", "at": f"2026-10-27T01:{seconds // 60:02d}:{seconds % 60:02d}+00:00"}


SLOW_FULL = [_slow_self_receipt(180)]   # 整組規則只攔會拖時間的：上面的案例預設「上次跑了 180 秒」，小樹／不知道的案例在檔尾另給


def _check(cmd, state, config=CFG, call=None, self_receipts=None):
    return vb.check("Bash", {"command": cmd}, config, state, "", SID, "", call,
                    self_receipts=list(SLOW_FULL if self_receipts is None else self_receipts))


# ─── VERIFY_FULL_RUN_NEEDS_USER_ORDER ───────────────────────────────────────────

def test_full_run_without_keyword_blocked(log):
    msg = _check(FULL, _state("幫我修這個 bug"))
    assert msg and vb.RULE_FULL in msg and msg.startswith("[Guardian:VerifyBatch] ✗ (r) ")
    assert "｜證據：" in msg
    assert [(e["event"], e["rule"], e["allowed"]) for e in log()] == [("denied", vb.RULE_FULL, False)]


@pytest.mark.parametrize("cmd", [FULL, "python run_verify.py", "pytest hooks/verify"])
def test_full_run_with_user_keyword_allowed(log, cmd):
    assert _check(cmd, _state("改完後跑整組")) is None
    assert [(e["event"], e["allowed"]) for e in log()] == [("allowed", True)]


def test_task_notification_not_user_keyword(log):
    """背景通知開的回合：turn_prompts 空（口令沿用在 CommitOrder 另有規則；這裡只認使用者打的字），通知內文的「全量」不算。"""
    st = _state()
    st["recent_user_prompts"] = ["<task-notification>子代理回報：全量 run_verify 綠</task-notification>"]
    st["turn_prompts"] = []
    msg = _check(FULL, st)
    assert msg and vb.RULE_FULL in msg


def test_full_run_keyword_configurable(log):
    cfg = {"guard": {"verify_batch": {"enabled": True, "full_run_keywords": ["跑全"]}}}
    assert _check(FULL, _state("跑全"), cfg) is None
    assert _check(FULL, _state("整組"), cfg)       # 預設字被自訂表取代


# ─── VERIFY_SAME_BATCH_ALREADY_GREEN ────────────────────────────────────────────

def test_targeted_pytest_first_time_allowed(log):
    assert _check(TARGETED, _state("修 a", mods=(("hooks/a.py", 5, "2026-10-27T10:00:00+08:00"),))) is None
    assert log()[-1]["event"] == "allowed"


def test_same_batch_green_rerun_blocked(log):
    st = _state("修 a", mods=(("hooks/a.py", 5, "2026-10-27T10:00:00+08:00"),),
                receipts=(_receipt(TARGETED, 6, "2026-10-27T10:01:00+08:00"),))
    msg = _check(TARGETED, st)
    assert msg and vb.RULE_SAME in msg and "這批改動已驗證過" in msg
    assert "收據 2026-10-27T10:01:00+08:00" in msg and "verify_a.py" in msg and "結果 綠" in msg
    assert log()[-1]["event"] == "denied"


def test_same_batch_green_rerun_blocked_via_python_m_and_bare_pytest_equal(log):
    """`python -X utf8 -m pytest -q x` 與 `pytest -q x` 是同一組指令（self_receipt 正規化；直譯器選項不改測什麼、不進 key）。"""
    st = _state("修 a", receipts=(_receipt("pytest -q -p no:cacheprovider hooks/verify/verify_a.py", 6, "2026-10-27T10:01:00+08:00"),))
    assert _check(TARGETED, st)


def test_rerun_after_new_edit_allowed(log):
    st = _state("修 a", mods=(("hooks/a.py", 7, "2026-10-27T10:02:00+08:00"),),
                receipts=(_receipt(TARGETED, 6, "2026-10-27T10:01:00+08:00"),))
    assert _check(TARGETED, st) is None


def test_rerun_after_red_allowed(log):
    st = _state("修 a", mods=(("hooks/a.py", 5, "2026-10-27T10:00:00+08:00"),),
                receipts=(_receipt(TARGETED, 6, "2026-10-27T10:01:00+08:00", green=False),))
    assert _check(TARGETED, st) is None


def test_other_command_green_does_not_cover_this_one(log):
    st = _state("修 a", receipts=(_receipt("pytest -q hooks/verify/verify_b.py", 6, "2026-10-27T10:01:00+08:00"),))
    assert _check(TARGETED, st) is None


def test_full_run_green_self_receipt_then_full_again_blocked(log):
    """浪費③：背景 run_verify 自寫收據綠、之後沒改檔，再帶口令跑全量照擋（口令只開門，不洗掉已驗過）。"""
    st = _state("跑整組", mods=(("hooks/a.py", 5, "2026-10-27T02:00:00+00:00"),))
    self_rec = {"source": "run_verify_self", "argv": ["python", "run_verify.py"], "exit_code": 0, "failed": 0,
                "at": "2026-10-27T02:30:00+00:00", "cmd": "python run_verify.py"}
    msg = vb.check("Bash", {"command": "python run_verify.py"}, CFG, st, "", SID, "", None, self_receipts=[self_rec])
    assert msg and vb.RULE_SAME in msg


def test_edit_without_seq_or_time_counts_as_changed():
    """改檔少序號又少時間＝分不出先後，當有改（放行、不誤擋）。"""
    rec = _receipt(TARGETED, 6, "2026-10-27T10:01:00+08:00")
    assert vb.edits_after(rec, [{"path": "x.py"}]) == ["x.py"]
    assert vb.edits_after(rec, [{"path": "x.py", "last_seq": 6}]) == []


# ─── VERIFY_BATCH_BLOCK_ONCE_PER_TURN ───────────────────────────────────────────

def test_block_once_per_turn_then_release_logged(log, capsys):
    st = _state("幫我修這個 bug")
    assert _check(FULL, st, call={"tool_use_id": "t1", "session_id": SID})
    assert _check(FULL, st, call={"tool_use_id": "t2", "session_id": SID}) is None
    events = [(e["event"], e["allowed"]) for e in log()]
    assert events == [("denied", False), ("released", True)]
    assert log()[-1]["release_rule"] == vb.RULE_ONCE
    assert vb.RULE_ONCE in capsys.readouterr().err
    # 換使用者回合歸零：再擋
    st["turn_seq"] = st["turn_prompts_seq"] = 4
    assert _check(FULL, st, call={"tool_use_id": "t3", "session_id": SID})


def test_once_per_turn_is_per_rule(log):
    st = _state("幫我修這個 bug", receipts=(_receipt(TARGETED, 6, "2026-10-27T10:01:00+08:00"),))
    assert _check(FULL, st, call={"tool_use_id": "t1", "session_id": SID})          # FULL 擋 1 次
    assert _check(TARGETED, st, call={"tool_use_id": "t2", "session_id": SID})      # SAME 另一條，照擋


# ─── 開關、解析不了、非 shell 工具 ───────────────────────────────────────────────

def test_disabled_switch_passes_through(log):
    cfg = {"guard": {"verify_batch": {"enabled": False}}}
    assert _check(FULL, _state("幫我修這個 bug"), cfg) is None
    assert log() == []


@pytest.mark.parametrize("cmd", ["bash -c 'pytest'", "eval pytest", "cat <<EOF\nx\nEOF\npytest", "echo hi", "python tools/x.py"])
def test_unparsed_command_ignored(log, cmd):
    assert _check(cmd, _state("幫我修這個 bug")) is None
    assert log() == []


def test_non_shell_tool_ignored(log):
    assert vb.check("Edit", {"file_path": "a.py"}, CFG, _state("x"), "", SID) is None


def test_gate_error_fails_open_and_logs(log, monkeypatch):
    monkeypatch.setattr(vb, "decide", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert _check(FULL, _state("幫我修這個 bug")) is None
    assert log()[-1]["event"] == "error" and log()[-1]["rule"] == "GATE_SELF_ERROR"


# ─── 規則登記 ───────────────────────────────────────────────────────────────────

def test_rules_registered_out_of_scope_block():
    import wg_release_rules as rr
    for rule in (vb.RULE_FULL, vb.RULE_SAME, vb.RULE_ONCE):
        assert rule in rr.RULES and rr.RULE_CLASS[rule] == "不在範圍" and rr.gate_mode(rule, True) == rr.BLOCK


def test_config_has_verify_batch_section():
    cfg = json.loads((HOOKS_DIR.parent / "workflow" / "config.json").read_text(encoding="utf-8"))
    sec = cfg["guard"]["verify_batch"]
    assert sec["enabled"] is True and "_doc" in sec
    assert set(sec["full_run_keywords"]) >= set(vb.DEFAULT_FULL_RUN_KEYWORDS)


def test_pre_tool_use_wires_gate_after_commit_order():
    src = (HOOKS_DIR / "handlers" / "pre_tool_use.py").read_text(encoding="utf-8")
    assert src.index("check_git_commit_order(tool_name") < src.index("wg_verify_batch.check(tool_name, tool_input, config, _co_state")


# ─── 只攔會拖時間的：VERIFY_FULL_RUN_NEEDS_USER_ORDER 要「上次耗時 ≥ slow_run_s」或「測試檔 ≥ large_suite_files」才擋 ───

def _suite(tmp_path, n):
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    for i in range(n):
        (root / "tests" / f"test_{i}.py").write_text("def test_x(): pass\n", encoding="utf-8")
    return str(root)


def _check_in(cmd, state, cwd, self_receipts=(), config=CFG):
    return vb.check("Bash", {"command": cmd}, config, state, cwd, SID, "", None, self_receipts=list(self_receipts))


def test_small_suite_full_run_allowed_without_keyword(log, tmp_path):
    """006 的誤傷：小專案（qb2-sales 測試檔 3 支）跑 pytest 幾秒就完，沒口令也放行、留帳 reason=small。"""
    root = _suite(tmp_path, 3)
    assert _check_in(FULL, _state("幫我修這個 bug"), root) is None
    e = log()[-1]
    assert (e["event"], e["rule"], e["reason"]) == ("allowed", vb.RULE_FULL, "small")


def test_large_suite_full_run_blocked_without_keyword(log, tmp_path, monkeypatch):
    root = _suite(tmp_path, 50)
    st = _state("幫我修這個 bug")
    msg = _check_in(FULL, st, root)
    assert msg and vb.RULE_FULL in msg and log()[-1]["event"] == "denied"
    # 檔數只數一次：快取在 state 每根一筆，第二次不再走檔案系統
    assert st["verify_batch_suite_files"][vb._root_key(root)]["files"] >= 50
    monkeypatch.setattr(vb, "_count_case_files", lambda *a, **k: (_ for _ in ()).throw(AssertionError("recounted")))
    st["turn_seq"] = st["turn_prompts_seq"] = 4
    assert _check_in(FULL, st, root)


def test_slow_previous_run_blocks_without_keyword(log, tmp_path):
    root = _suite(tmp_path, 3)
    msg = _check_in(FULL, _state("幫我修這個 bug"), root, self_receipts=[_slow_self_receipt(180)])
    assert msg and vb.RULE_FULL in msg and log()[-1]["event"] == "denied"
    # 上次耗時 90 秒 < 120 → 不算拖時間
    assert _check_in(FULL, _state("幫我修這個 bug"), root, self_receipts=[_slow_self_receipt(90)]) is None


def test_unknown_duration_small_suite_allowed(log, tmp_path):
    """session 收據沒記開始時間 → 耗時不知道；檔數又沒到門檻 → 放行（偏放行不偏擋）。"""
    root = _suite(tmp_path, 3)
    st = _state("幫我修這個 bug", receipts=(_receipt(FULL, 6, "2026-10-27T10:01:00+08:00", green=False),))
    assert _check_in(FULL, st, root) is None
    assert log()[-1]["reason"] == "small"


def test_block_message_states_why_slow(log, tmp_path):
    big = _suite(tmp_path, 50)
    msg = _check_in(FULL, _state("幫我修這個 bug"), big)
    assert "測試檔" in msg and "50" in msg
    small = _suite(tmp_path / "b", 2)
    msg = _check_in(FULL, _state("幫我修這個 bug"), small, self_receipts=[_slow_self_receipt(180)])
    assert "上次耗時 180 秒" in msg


def test_slow_thresholds_configurable_and_in_config():
    cfg = json.loads((HOOKS_DIR.parent / "workflow" / "config.json").read_text(encoding="utf-8"))
    sec = cfg["guard"]["verify_batch"]
    assert sec["slow_run_s"] == 120 and sec["large_suite_files"] == 50
    assert vb.slow_reason(10.0, 3, 5, 50) and vb.slow_reason(None, 7, 120, 5) and vb.slow_reason(None, 3, 120, 50) is None
