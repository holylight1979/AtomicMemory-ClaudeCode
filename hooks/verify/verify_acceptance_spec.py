"""verify_acceptance_spec.py — 驗收規格檔登記契約。

1. is_spec_file_path：規格檔路徑指紋（.claude/verify/acceptance-*.md、反斜線正規化）
2. run：寫入規格檔 → sidecar spec_paths 記路徑（同一路徑只記一次）；enabled=false、非寫入工具、缺 session_id 不記
3. 不送字給 AI：寫碼守門開著、plan 被核可或同 session 改了很多檔，run 都不回任何東西、不寫提醒記號
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import acceptance_spec as asp  # noqa: E402

SID = "test-asp-session"
CFG = {"enabled": True}


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """隔離 sidecar 與 guardian state 目錄到 tmp_path；寫碼守門開著（conftest 預設 WG_V6=1，這裡明寫）。"""
    workflow = tmp_path / "workflow"
    workflow.mkdir()
    monkeypatch.setattr(asp, "WORKFLOW_DIR", workflow)
    monkeypatch.setattr(asp, "SIDECAR_DIR", workflow / "acceptance-spec")
    monkeypatch.setenv("WG_V6", "1")
    return workflow


def _write_ev(path, tool="Write", sid=SID):
    return {"session_id": sid, "tool_name": tool, "cwd": "D:/p", "tool_input": {"file_path": path}}


# ─── 1. is_spec_file_path ────────────────────────────────────────────────────

def test_spec_path_hit_forward_and_backslash():
    assert asp.is_spec_file_path("D:/proj/.claude/verify/acceptance-fix-login.md")
    assert asp.is_spec_file_path(r"D:\proj\.claude\verify\acceptance-fix-login.md")


def test_spec_path_miss():
    assert not asp.is_spec_file_path("D:/proj/.claude/verify/other.md")
    assert not asp.is_spec_file_path("D:/proj/hooks/verify/acceptance-x.md")  # 非 .claude/
    assert not asp.is_spec_file_path("D:/proj/.claude/verify/acceptance-x.py")
    assert not asp.is_spec_file_path("")


# ─── 2. 登記 ─────────────────────────────────────────────────────────────────

def test_spec_write_records_path_once_normalized(sandbox, capsys):
    spec = r"D:\p\.claude\verify\acceptance-my-task.md"
    assert asp.run(_write_ev(spec), CFG) is None
    asp.run(_write_ev(spec, tool="Edit"), CFG)                      # 同一路徑再改一次不重記
    assert asp.read_sidecar(SID).get("spec_paths") == ["D:/p/.claude/verify/acceptance-my-task.md"]
    assert capsys.readouterr().out == "", "run() 不得直接 print"


@pytest.mark.parametrize("ev, cfg", [
    (_write_ev("D:/p/.claude/verify/acceptance-x.md"), {"enabled": False}),
    ({"session_id": SID, "tool_name": "Bash", "tool_input": {"command": "echo > D:/p/.claude/verify/acceptance-x.md"}}, CFG),
    (_write_ev("D:/p/.claude/verify/acceptance-x.md", sid=""), CFG),
], ids=["disabled", "non_write_tool", "missing_sid"])
def test_not_recorded(sandbox, ev, cfg):
    asp.run(ev, cfg)
    assert not (sandbox / "acceptance-spec").exists()


# ─── 3. 不送字給 AI ──────────────────────────────────────────────────────────

def test_plan_approved_and_many_files_send_nothing(sandbox, capsys):
    """寫碼守門開、plan 被核可、同 session 改了 3 個檔：一個字都不回，也不寫提醒記號（舊碼這兩處各送一份約 550 字的規格提示）。"""
    state = {"modified_files": [{"path": f"D:/p/{n}.py", "session_id": SID} for n in "abc"]}
    (sandbox / f"state-{SID}.json").write_text(json.dumps(state), encoding="utf-8")
    plan = {"session_id": SID, "tool_name": "ExitPlanMode", "cwd": "D:/p", "tool_input": {}, "tool_response": "approved"}
    assert asp.run(plan, CFG) is None
    assert asp.run(_write_ev("D:/p/c.py", tool="Edit"), CFG) is None
    assert not (sandbox / "acceptance-spec").exists()
    assert capsys.readouterr().out == ""
