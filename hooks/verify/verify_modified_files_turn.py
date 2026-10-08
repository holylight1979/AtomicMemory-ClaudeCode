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


def test_legacy_entry_without_turn_fields_not_this_turn_until_next_edit(drive):
    """升級前的 entry 沒 turn 欄 → 不當本 turn（對帳閘不拿它擋）；下一次 Edit 補上 turn 欄。"""
    state = drive("Edit", {"file_path": _A}, turn=3)
    state["modified_files"].append({"path": _B, "tool": "Edit", "session_id": _SID})
    assert vl.modified_this_turn(state["modified_files"], 9) == []
    state = drive("Edit", {"file_path": _B}, turn=9)
    legacy = next(m for m in state["modified_files"] if m["path"] == _B)
    assert legacy["turn_seq"] == 9 and legacy["last_turn_seq"] == 9 and legacy["count"] == 2
