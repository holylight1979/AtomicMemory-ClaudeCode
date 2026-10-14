"""verify_fix_escalation_plan_retry.py — FixEscalation 計畫迭代豁免 + error gate。

track_retry 對「計畫類檔」（plans/、_staging/、檔名命中 plan/draft/roadmap/wip）
的多次編輯不累計 retry_count，因此不會在下一輪 UserPromptSubmit 注入
[Guardian:FixEscalation]；計畫檔豁免先於 failure gate 早退（編計畫檔不是對程式
失敗的修復嘗試）。

retry 數的是「紅了、改了、再跑仍紅」的輪數（規則 RETRY_COUNTS_RERUN_CYCLES）：
紅測期間改檔只記 edits_since_run，重跑同一組仍紅才算一輪；測試全綠下反覆改同碼不誤觸
（edit 次數 ≠ 失敗）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from wisdom_engine import track_retry  # noqa: E402


# 真失敗訊號（detect_test_failure 偵到、未清）
_FAILING = [{"cmd": "pytest", "at": "t"}]


# ─── helper ──────────────────────────────────────────────────────────

def _state_with_edits(file_path: str, n: int, *, failing: bool = True) -> dict:
    """建構含 n 次同檔 edit 紀錄的 state（模擬 PostToolUse 已累積 N-1 次 +
    這一次馬上要呼 track_retry）。預設帶 failing_tests（真失敗未解）。"""
    return {
        "modified_files": [
            {"path": file_path, "tool": "Edit", "at": f"t{i}"} for i in range(n)
        ],
        "failing_tests": list(_FAILING) if failing else [],
    }


# ─── 計畫迭代豁免（先於 failure gate 早退）─────────────────────────────

def test_plan_dir_repeated_edits_not_counted_as_retry(tmp_path):
    """正向 1：plans/*.md 連續 5 次 edit（即使測試紅）→ retry 仍為 0（豁免早退）。"""
    plan_path = "C:/Users/x/.claude/plans/whimsical-zooming-sedgewick.md"
    state = {"modified_files": [], "failing_tests": list(_FAILING)}
    for _ in range(5):
        state["modified_files"].append({"path": plan_path, "tool": "Edit", "at": "t"})
        track_retry(state, plan_path)
    assert state.get("wisdom_retry_count", 0) == 0


def test_plan_filename_keyword_not_counted_as_retry():
    """正向 2：路徑不在 plans/ 但檔名含 'roadmap' / 'todo' / 'draft' 也豁免（測試紅亦然）。"""
    for fname in ["roadmap-2026.md", "todo-list.md", "draft-spec.md"]:
        path = f"/some/random/dir/{fname}"
        state = _state_with_edits(path, 3)  # failing=True
        track_retry(state, path)
        assert state.get("wisdom_retry_count", 0) == 0, fname


def test_staging_dir_not_counted_as_retry():
    """_staging/ 暫存區也豁免（自由格式區，本就不是 atom 也不是 fix target）。"""
    path = "/proj/.claude/memory/_staging/scratch.md"
    state = _state_with_edits(path, 4)  # failing=True
    track_retry(state, path)
    assert state.get("wisdom_retry_count", 0) == 0


# ─── error gate：測試綠 → 真碼反覆 edit 也不算 retry ──────────────────

def test_real_code_edits_without_failure_not_counted():
    """hooks/foo.py 反覆 edit 但 failing_tests 空 → retry 0（edit 次數 ≠ 失敗）。"""
    path = "/proj/hooks/foo.py"
    state = {"modified_files": []}  # 無 failing_tests
    for _ in range(5):
        state["modified_files"].append({"path": path, "tool": "Edit", "at": "t"})
        track_retry(state, path)
    assert state.get("wisdom_retry_count", 0) == 0


# ─── 測試仍紅 + 真碼反覆修 → 觸發（真正的反覆修不好）──────────────────

_SID = "sess-plan-retry"
_CMD = "python -m pytest -q tests/test_foo.py"


def _rerun_red(state):
    """走真的 PostToolUse 入口再跑一次同一組、仍紅（規則 RETRY_COUNTS_RERUN_CYCLES：重跑在這裡判輪）。"""
    from handlers import post_tool_use as ptu
    cmd = _CMD
    ev = {"session_id": _SID, "tool_name": "Bash", "tool_input": {"command": cmd},
          "tool_response": {"stdout": "FAILED tests/test_foo.py::t - assert 0\n1 failed in 0.1s\n", "stderr": "", "interrupted": False}}
    ptu._track_test_result(state, ev, cmd)


@pytest.mark.parametrize("path", ["/proj/hooks/foo.py", "/proj/tests/test_foo.py"])
def test_real_code_repeated_edits_during_failure_still_count(path):
    """反向：測試紅期間反覆改真碼（含測試檔，除錯場景）→ 改檔只記 edits_since_run；每次「改了再跑同一組仍紅」算一輪，
    兩輪到 FixEscalation 門檻。"""
    state = {"modified_files": [], "failing_tests": [{"cmd": _CMD, "at": "t", "session_id": _SID}]}
    for _ in range(3):
        state["modified_files"].append({"path": path, "tool": "Edit", "at": "t"})
        track_retry(state, path)
    assert state.get("wisdom_retry_count", 0) == 0 and state["failing_tests"][-1]["edits_since_run"] == {path: 3}
    _rerun_red(state)
    track_retry(state, path)
    _rerun_red(state)
    assert state.get("wisdom_retry_count", 0) == 2


def test_first_edit_no_retry_increment():
    """單次 edit 任何檔（含 .py，即使測試紅）→ 不算 retry（count=1 < threshold）。"""
    path = "/proj/foo.py"
    state = {
        "modified_files": [{"path": path, "tool": "Edit", "at": "t0"}],
        "failing_tests": list(_FAILING),
    }
    track_retry(state, path)
    assert state.get("wisdom_retry_count", 0) == 0


# ─── 整合：FixEscalation 注入流程 ─────────────────────────────────────
# 直接驗證 retry_count gate（>=2 觸發）的核心邏輯不被 plan 路徑誤觸。

def test_fix_escalation_threshold_not_reached_for_plan():
    """FixEscalation 閾值 retry_count >=2 對 plan 永不到達（即使測試紅）。"""
    plan_path = "/proj/plans/sprint-eval.md"
    state = {"modified_files": [], "failing_tests": list(_FAILING)}
    for _ in range(10):
        state["modified_files"].append({"path": plan_path, "tool": "Edit", "at": "t"})
        track_retry(state, plan_path)
    assert state.get("wisdom_retry_count", 0) < 2  # 永不觸發 FixEscalation
