"""verify_modified_files_turn.py：B5：modified_files 記 MultiEdit、turn_seq／last_turn_seq／tool；Bash／PowerShell 改檔目標兩態。

怎麼跑：set WG_CLAUDE_DIR=<worktree> && python -X utf8 -m pytest -q hooks/verify/verify_modified_files_turn.py
兩態：wg_core.write_paths_from_tool 有（track-a1 合併後）→ Bash 目標進 modified_files；沒有（None）→ 只記 Edit／Write 目標。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

from handlers import post_tool_use as pt  # noqa: E402
import wg_verify_ledger as vl  # noqa: E402

_SID = "sid-mod"
_A = r"c:\proj\src\a.py"
_B = r"c:\proj\src\b.py"


@pytest.fixture()
def drive(monkeypatch, tmp_path):
    state = {"turn_seq": 3, "session": {"cwd": r"c:\proj"}}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)

    def run(tool_name, tool_input, turn=None, resp=None):
        if turn is not None:
            state["turn_seq"] = turn
        inp = {"session_id": _SID, "tool_name": tool_name, "tool_input": tool_input,
               "tool_response": resp if resp is not None else {"stdout": "", "stderr": ""}, "cwd": r"c:\proj"}
        with pytest.raises(SystemExit):
            pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}})
        return state

    return run


def test_edit_records_turn_seq_and_last_turn_seq(drive):
    state = drive("Edit", {"file_path": _A}, turn=3)
    m = state["modified_files"][0]
    assert m["path"] == _A and m["tool"] == "Edit" and m["turn_seq"] == 3 and m["last_turn_seq"] == 3 and m["count"] == 1
    state = drive("Write", {"file_path": _A}, turn=5)
    m = state["modified_files"][0]
    assert len(state["modified_files"]) == 1
    assert m["count"] == 2 and m["turn_seq"] == 3 and m["last_turn_seq"] == 5 and m["tool"] == "Write"
    assert vl.modified_this_turn(state["modified_files"], 5) == [_A]
    assert vl.modified_this_turn(state["modified_files"], 3) == []


def test_multiedit_recorded(drive):
    state = drive("MultiEdit", {"file_path": _B, "edits": [{"old_string": "a", "new_string": "b"}]}, turn=4)
    m = state["modified_files"][0]
    assert m["path"] == _B and m["tool"] == "MultiEdit" and m["turn_seq"] == 4


def test_bash_write_target_recorded_when_helper_available(drive, monkeypatch):
    monkeypatch.setattr(pt, "_write_paths_from_tool", lambda tool, ti, cwd: [_A] if ">" in ti.get("command", "") else [])
    state = drive("Bash", {"command": f"echo x > {_A}"}, turn=6)
    m = state["modified_files"][0]
    assert m["path"] == _A and m["tool"] == "Bash" and m["last_turn_seq"] == 6
    state = drive("PowerShell", {"command": f"Set-Content {_B} x"}, turn=6)
    assert len(state["modified_files"]) == 1   # helper 只對 `>` 回目標；PowerShell 無目標不記


def test_bash_without_helper_records_nothing(drive, monkeypatch):
    monkeypatch.setattr(pt, "_write_paths_from_tool", None)
    state = drive("Bash", {"command": f"echo x > {_A}"}, turn=6)
    assert "modified_files" not in state


def test_ephemeral_bash_target_filtered(drive, monkeypatch, tmp_path):
    tmp_target = str(tmp_path / "t.py")
    monkeypatch.setattr(pt, "_write_paths_from_tool", lambda tool, ti, cwd: [tmp_target])
    state = drive("Bash", {"command": f"echo x > {tmp_target}"}, turn=6)
    assert "modified_files" not in state


# ─── 004：指令非零結束（Claude Code 不送 PostToolUse、改送 PostToolUseFailure）前段寫的檔照樣記 ────────────
# 第二波題 A′ 實跑：`cat > pricing/api.py <<EOF … && python -m pytest`，pytest 紅讓整條 exit 1，改的產品檔沒進 modified_files，
# 閱讀路徑回「這次只改了測試檔」、G11 沒量到產品碼

HEREDOC = ("cat > pricing/api.py <<'EOF'\ndef quote(sku):\n    return 1\nEOF\n"
           "cat > pricing/never.py <<'EOF'\nx = 1\nEOF\n"
           "python -m pytest tests -q")


@pytest.fixture()
def failed(monkeypatch, tmp_path):
    """真的 write_paths_from_tool；專案在 tmp（暫存路徑過濾關掉，不然整個 tmp 專案都被濾掉）。
    transcript 裡放一筆 tool_use（時間＝一分鐘前），handler 拿它當指令開始時間：這之後才改過的檔才算這次寫的。"""
    import json
    import os
    import time
    from datetime import datetime, timezone
    from wg_core import write_paths_from_tool
    proj = tmp_path / "proj"
    (proj / "pricing").mkdir(parents=True)
    (proj / "tests").mkdir()
    (proj / "pricing" / "api.py").write_text("def quote(sku):\n    return 1\n", encoding="utf-8")   # 前段寫成功
    old = proj / "pricing" / "old.py"
    old.write_text("x = 1\n", encoding="utf-8")
    os.utime(old, (time.time() - 3600, time.time() - 3600))                                     # 指令開始前就是這樣
    started = datetime.fromtimestamp(time.time() - 60, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    tr = tmp_path / "t.jsonl"
    tr.write_text(json.dumps({"type": "assistant", "timestamp": started, "message": {"content": [
        {"type": "tool_use", "id": "tu-fail-1", "name": "Bash", "input": {}}]}}) + "\n", encoding="utf-8")
    state = {"turn_seq": 7, "session": {"cwd": str(proj)}}
    wrote = []
    monkeypatch.setattr(pt, "_write_paths_from_tool", write_paths_from_tool)
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda sid, st: wrote.append(sid))
    monkeypatch.setattr(pt, "_is_ephemeral_path", lambda p: False)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path / "wf")                    # 驗證帳本落 tmp
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    stamped = []                                                               # 目標樹蓋號：只記呼叫，不碰真的目標檔
    monkeypatch.setattr(pt, "_need_goal_stamp_failed", lambda st, sid, noted, aid, cwd, cfg: stamped.append(list(noted)) or [],
                        raising=False)                                         # 退回舊碼看紅時沒有這支，案例照跑到斷言

    def run(tool_name, command, transcript=True, error="Exit code 1\n1 failed, 9 passed"):
        inp = {"session_id": _SID, "hook_event_name": "PostToolUseFailure", "tool_name": tool_name,
               "tool_input": {"command": command}, "error": error, "cwd": str(proj),
               "tool_use_id": "tu-fail-1", "transcript_path": str(tr) if transcript else ""}
        try:
            pt.handle_post_tool_use_failure(inp, {})
        except SystemExit:
            pass
        return state, wrote

    def run_ok(command, stdout):
        """同一份 state 走成功事件（exit 0）。"""
        inp = {"session_id": _SID, "tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(proj),
               "tool_response": {"stdout": stdout, "stderr": "", "exit_code": 0}}
        with pytest.raises(SystemExit):
            pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}})
        return state

    run.ok = run_ok
    run.stamped = stamped
    return proj, run


def _case_globs():
    """閱讀路徑量尺判測試檔用的同一份樣式（reconcile_cfg 的 verify_case_globs）。"""
    return vl.reconcile_cfg({}).get("verify_case_globs") or []


def test_004_failed_bash_records_files_it_already_wrote(failed):
    from wg_reading_path import code_files
    from wg_verify_ledger import is_verify_case
    proj, run = failed
    state, wrote = run("Bash", HEREDOC)
    paths = [m["path"] for m in state.get("modified_files") or []]
    assert any(p.endswith("api.py") for p in paths), paths                      # 寫成功的產品檔有記
    assert not any(p.endswith("never.py") for p in paths), paths                # 沒寫出來的不記
    m = next(m for m in state["modified_files"] if m["path"].endswith("api.py"))
    assert m["tool"] == "Bash" and m["last_turn_seq"] == 7 and wrote == [_SID]
    product = [f for f in code_files(state["modified_files"], [".py"]) if not is_verify_case(f, _case_globs(), str(proj))]
    assert product and product[0].endswith("api.py")                            # 閱讀路徑量尺拿得到產品檔


def test_004_failed_bash_test_only_stays_test_only_and_nothing_written_writes_no_state(failed):
    from wg_reading_path import code_files
    from wg_verify_ledger import is_verify_case
    proj, run = failed
    (proj / "tests" / "test_cli.py").write_text("def test_x():\n    assert 1\n", encoding="utf-8")
    state, _ = run("Bash", "sed -i 's/1/2/' tests/test_cli.py && python -m pytest tests -q")
    files = code_files(state["modified_files"], [".py"])
    assert files and all(is_verify_case(f, _case_globs(), str(proj)) for f in files)   # 只改測試檔：照舊沒有產品入口
    state2, wrote = run("Bash", "ls missing.txt", error="Exit code 2\nls: missing.txt: No such file")   # 沒有寫入目標、不是測試
    assert len(state2["modified_files"]) == 1 and wrote == [_SID]               # 第二次沒寫 state


def test_004_failed_command_skips_targets_untouched_since_it_started(failed, capsys):
    """codex 審：失敗在寫之前、目標檔原本就在 → 不能算這次寫的（看 mtime 對指令開始時間）；找不到開始時間就照存在記、浮一行。"""
    proj, run = failed
    state, _ = run("Bash", "false && cat > pricing/old.py <<'EOF'\ny = 2\nEOF\ncat > pricing/api.py <<'EOF'\nz\nEOF")
    paths = [m["path"] for m in state.get("modified_files") or []]
    assert any(p.endswith("api.py") for p in paths) and not any(p.endswith("old.py") for p in paths), paths
    state2, _ = run("Bash", "cat > pricing/old.py <<'EOF'\ny = 2\nEOF\nfalse", transcript=False)
    assert any(m["path"].endswith("old.py") for m in state2["modified_files"])
    assert "找不到這次工具呼叫的開始時間" in capsys.readouterr().err


def test_004_failed_powershell_records_written_file(failed):
    proj, run = failed
    (proj / "pricing" / "ps.py").write_text("p = 1\n", encoding="utf-8")
    state, _ = run("PowerShell", "Set-Content -Path pricing/ps.py -Value 'p = 1'; throw 'boom'")
    m = next((m for m in state.get("modified_files") or [] if m["path"].endswith("ps.py")), None)
    assert m and m["tool"] == "PowerShell", state.get("modified_files")


PYTEST = "python -m pytest tests -q"
RED = "Exit code 1\nFAILED tests/test_cli.py::test_x - assert 1 == 2\n1 failed, 9 passed in 0.2s"


def _receipts(state):
    return (state.get("verify_receipts") or {}).get(_SID) or []


def test_004_failed_pytest_enters_failing_tests_and_receipt_green_does_not(failed):
    """exit 1 的 pytest（失敗事件）進 failing_tests、收據記 exit 1；同一份 state 再跑 exit 0（成功事件）→ 紅測清掉、不再新增。"""
    _, run = failed
    state, wrote = run("Bash", PYTEST, error=RED)
    reds = state.get("failing_tests") or []
    assert len(reds) == 1 and reds[0]["exit_code"] == 1 and reds[0]["session_id"] == _SID and reds[0]["pytest"], reds
    assert [r["exit_code"] for r in _receipts(state)] == [1] and wrote == [_SID]
    state = run.ok(PYTEST, "10 passed in 0.2s")
    assert not state.get("failing_tests"), state.get("failing_tests")
    assert [r["exit_code"] for r in _receipts(state)] == [1, 0]


def test_004_green_pytest_alone_never_enters_failing_tests(failed):
    _, run = failed
    state = run.ok(PYTEST, "10 passed in 0.2s")
    assert "failing_tests" not in state and [r["exit_code"] for r in _receipts(state)] == [0]


def test_004_blocked_or_interrupted_command_is_not_a_test_result(failed):
    """被 hook 擋下、逾時中斷：error 裡沒有結束碼，指令沒跑完，不記紅測也不落收據。
    前置：這段文字丟給紅測判讀本來會算紅（不記是因為沒結束碼，不是因為沒字樣）。"""
    _, run = failed
    blocked = "PreToolUse:Bash hook error: blocked\nFAILED tests/test_cli.py::test_x"
    assert pt.detect_test_failure(blocked, "", False)
    state, wrote = run("Bash", PYTEST, error=blocked)
    assert "failing_tests" not in state and not _receipts(state) and wrote == []


def test_004_failed_bash_writes_stamped_into_goal_tree(failed):
    """失敗指令真的寫到的檔才交目標樹蓋號（沒寫出來的不交）；沒寫到任何檔也照樣呼叫（收據蓋號）。"""
    _, run = failed
    run("Bash", HEREDOC)
    assert len(run.stamped) == 1 and [p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in run.stamped[0]] == ["api.py"]


def test_004_failed_powershell_pytest_enters_failing_tests(failed):
    _, run = failed
    state, _ = run("PowerShell", PYTEST, error=RED)
    reds = state.get("failing_tests") or []
    assert len(reds) == 1 and reds[0]["tool"] == "PowerShell" and [r["tool"] for r in _receipts(state)] == ["PowerShell"]


def test_004_stamp_wrapper_stamps_each_written_file_and_receipts(monkeypatch, capsys):
    """_need_goal_stamp_failed 本體（上面的案例替換掉它）：每個寫到的檔各蓋一次、收據蓋一次、提示行收回；目標樹關掉不蓋；蓋號出錯只 stderr 回空。"""
    import wg_need_goal as ng
    calls = []
    monkeypatch.setattr(ng, "cfg_for_cwd", lambda cfg, cwd: {"enabled": True})
    monkeypatch.setattr(ng, "stamp_edit", lambda sid, p, aid, turn, cfg: calls.append(("edit", sid, p, aid, turn))
                        or ("提示一行" if p.endswith("a.py") else None))
    monkeypatch.setattr(ng, "stamp_receipts", lambda sid, st, turn: calls.append(("receipts", sid, turn)))
    state = {"turn_seq": 9, "session": {"cwd": r"c:\proj"}}
    lines = pt._need_goal_stamp_failed(state, _SID, [_A, _B], "ag1", r"c:\proj", {})
    assert lines == ["提示一行"]
    assert calls == [("edit", _SID, _A, "ag1", 9), ("edit", _SID, _B, "ag1", 9), ("receipts", _SID, 9)]
    monkeypatch.setattr(ng, "cfg_for_cwd", lambda cfg, cwd: {"enabled": False})
    calls.clear()
    assert pt._need_goal_stamp_failed(state, _SID, [_A], "", r"c:\proj", {}) == [] and calls == []
    monkeypatch.setattr(ng, "cfg_for_cwd", lambda cfg, cwd: (_ for _ in ()).throw(RuntimeError("壞了")))
    assert pt._need_goal_stamp_failed(state, _SID, [_A], "", r"c:\proj", {}) == []
    assert "PostToolUseFailure 蓋號失敗" in capsys.readouterr().err


def test_004_judge_failure_records_receipt_but_not_failing_tests(failed, monkeypatch):
    """裁判子 session：失敗事件照記收據（寫碼查核閘要看），不記紅測、不蓋目標樹。"""
    import wg_core
    _, run = failed
    monkeypatch.setenv("CLAUDE_COMPANION_JUDGE", "1")
    judge_state = {"turn_seq": 2, "session": {"id": _SID, "cwd": ""}}
    monkeypatch.setattr(wg_core, "read_state", lambda sid: judge_state)
    run("Bash", PYTEST, error=RED)
    assert "failing_tests" not in judge_state and [r["exit_code"] for r in _receipts(judge_state)] == [1]
    assert run.stamped == []


def test_004_failure_event_wired_in_dispatcher():
    """dispatcher 一般與裁判兩張表都接 PostToolUseFailure。settings.json 的註冊由原設計者加（片段見交付信），這裡不驗。"""
    import dispatcher
    assert dispatcher.HANDLERS["PostToolUseFailure"] == ("handlers.post_tool_use", "handle_post_tool_use_failure")
    assert dispatcher.JUDGE_HANDLERS["PostToolUseFailure"] == ("handlers.post_tool_use", "handle_post_tool_use_failure")


def test_legacy_entry_without_turn_fields_not_this_turn_until_next_edit(drive):
    """升級前的 entry 沒 turn 欄 → 不當本 turn（對帳閘不拿它擋）；下一次 Edit 補上 turn 欄。"""
    state = drive("Edit", {"file_path": _A}, turn=3)
    state["modified_files"].append({"path": _B, "tool": "Edit", "session_id": _SID})
    assert vl.modified_this_turn(state["modified_files"], 9) == []
    state = drive("Edit", {"file_path": _B}, turn=9)
    legacy = next(m for m in state["modified_files"] if m["path"] == _B)
    assert legacy["turn_seq"] == 9 and legacy["last_turn_seq"] == 9 and legacy["count"] == 2
