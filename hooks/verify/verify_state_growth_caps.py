"""verify_state_growth_caps.py — state 無上限累積修補（A3）。

契約：
- post_tool_use：modified_files 以 (path, session_id) 去重——重複編輯累加
  count + 刷 at，不重複 append entry
- wisdom_engine.track_retry：改讀 count 欄計同檔編輯次數（legacy 無 count
  的重複 entry 各計 1，語意不變）
- stop._harvest_accessed_files：accessed_files cap 500（裁最舊）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_core  # noqa: E402
import wisdom_engine  # noqa: E402
from handlers import post_tool_use as ptu  # noqa: E402
from handlers import stop as st  # noqa: E402


# ─── modified_files 去重 ────────────────────────────────────────────────────


@pytest.fixture
def env(tmp_path, monkeypatch):
    wdir = tmp_path / "workflow"
    wdir.mkdir()
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wdir)
    state = wg_core.new_state("sid-dedupe", str(tmp_path), "test")
    state["phase"] = "working"
    wg_core.write_state("sid-dedupe", state)
    return tmp_path, wdir


def _drive_edit(tmp_path, file_path: str):
    input_data = {
        "session_id": "sid-dedupe",
        "cwd": str(tmp_path),
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path},
    }
    config = {"docdrift": {"enabled": False}}
    with pytest.raises(SystemExit):
        ptu.handle_post_tool_use(input_data, config)


def test_repeat_edits_dedupe_with_count(env):
    tmp_path, _wdir = env
    # 路徑不可落系統 temp（_is_ephemeral_path 會濾掉）；檔案毋須實存
    fp = "C:/fakeproj/src/a.py"
    for _ in range(3):
        _drive_edit(tmp_path, fp)
    _drive_edit(tmp_path, "C:/fakeproj/src/b.py")
    state = wg_core.read_state("sid-dedupe")
    mods = state["modified_files"]
    assert len(mods) == 2  # 4 次事件 → 2 entry
    entry_a = next(m for m in mods if m["path"] == fp)
    assert entry_a["count"] == 3
    assert entry_a["session_id"] == "sid-dedupe"
    # edit_counts 舊軌不受影響
    assert state["edit_counts"][fp] == 3


def test_track_retry_reads_count_field():
    state = {
        "failing_tests": [{"cmd": "pytest", "summary": "F"}],
        "modified_files": [{"path": "src/a.py", "count": 3}],
        "wisdom_approach": "direct",
    }
    wisdom_engine.track_retry(state, "src/a.py")
    assert state.get("wisdom_retry_count", 0) == 1  # count=3 ≥ threshold 2


def test_track_retry_legacy_duplicate_entries():
    state = {
        "failing_tests": [{"cmd": "pytest", "summary": "F"}],
        "modified_files": [{"path": "src/a.py"}, {"path": "src/a.py"}],
        "wisdom_approach": "direct",
    }
    wisdom_engine.track_retry(state, "src/a.py")
    assert state.get("wisdom_retry_count", 0) == 1  # 各計 1 → 2 ≥ 2


# ─── accessed_files cap ─────────────────────────────────────────────────────


def _read_line(path: str) -> str:
    return json.dumps({
        "type": "assistant",
        "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": path}},
        ]},
    })


def test_accessed_files_capped_at_500():
    state = {"accessed_files": [
        {"path": f"C:/x/old{i}.md", "at": "t"} for i in range(498)
    ]}
    text = "\n".join(_read_line(f"C:/x/new{i}.md") for i in range(10))
    assert st._harvest_accessed_files(state, text) is True
    accessed = state["accessed_files"]
    assert len(accessed) == 500
    # 裁最舊、保最新
    assert accessed[-1]["path"] == "C:/x/new9.md"
    assert not any(a["path"] == "C:/x/old0.md" for a in accessed)
