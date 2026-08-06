"""verify_acceptance_spec.py — 驗收規格工件 hook 契約。

1. is_spec_file_path：規格檔路徑指紋（.claude/verify/acceptance-*.md、反斜線正規化）
2. count_session_modified_files：只數本 session、排除路徑片段、state 缺 fail-open=0
3. plan_looks_rejected：否決保守偵測
4. handle_post_tool_use 分級啟動：
   - ExitPlanMode → plan advisory（含格式指南 + session_id + frontmatter 欄位），每 session 一次
   - 多檔達門檻 → 一次性 multifile advisory；plan 已提醒 / 已有規格檔 → 抑制
   - 規格檔落盤 → sidecar 記路徑、不發 advisory
   - 小任務（檔數 < 門檻）→ 零輸出零打擾
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import acceptance_spec as asp  # noqa: E402


# ─── helpers ─────────────────────────────────────────────────────────────────

SID = "test-asp-session"


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """隔離 sidecar 與 guardian state 目錄到 tmp_path。"""
    workflow = tmp_path / "workflow"
    workflow.mkdir()
    monkeypatch.setattr(asp, "WORKFLOW_DIR", workflow)
    monkeypatch.setattr(asp, "SIDECAR_DIR", workflow / "acceptance-spec")
    return workflow


def _write_state(workflow: Path, paths, sid=SID):
    state = {
        "modified_files": [
            {"path": p, "session_id": sid, "tool": "Edit", "count": 1}
            for p in paths
        ]
    }
    (workflow / f"state-{sid}.json").write_text(
        json.dumps(state), encoding="utf-8"
    )


def _run(input_data, config=None, capsys=None):
    """跑 handler，回 (exit_code, parsed_stdout_or_None)。"""
    cfg = {"enabled": True, "min_files_trigger": 3,
           "count_exclude_substrings": ["/memory/", "/_staging/"]}
    if config:
        cfg.update(config)
    with pytest.raises(SystemExit) as ei:
        asp.handle_post_tool_use(input_data, cfg)
    out = capsys.readouterr().out if capsys else ""
    parsed = json.loads(out) if out.strip() else None
    return ei.value.code, parsed


def _ctx(parsed):
    return parsed["hookSpecificOutput"]["additionalContext"]


# ─── 1. is_spec_file_path ────────────────────────────────────────────────────

def test_spec_path_hit_forward_and_backslash():
    assert asp.is_spec_file_path("D:/proj/.claude/verify/acceptance-fix-login.md")
    assert asp.is_spec_file_path(r"D:\proj\.claude\verify\acceptance-fix-login.md")


def test_spec_path_miss():
    assert not asp.is_spec_file_path("D:/proj/.claude/verify/other.md")
    assert not asp.is_spec_file_path("D:/proj/hooks/verify/acceptance-x.md")  # 非 .claude/
    assert not asp.is_spec_file_path("D:/proj/.claude/verify/acceptance-x.py")
    assert not asp.is_spec_file_path("")


# ─── 2. count_session_modified_files ─────────────────────────────────────────

def test_count_distinct_and_excludes(sandbox):
    _write_state(sandbox, [
        "D:/p/a.py", "D:/p/b.py",
        "D:/p/memory/atom.md",      # excluded
        "D:/p/_staging/plan.md",    # excluded
    ])
    n = asp.count_session_modified_files(SID, ["/memory/", "/_staging/"])
    assert n == 2


def test_count_other_session_not_counted(sandbox):
    state = {"modified_files": [
        {"path": "D:/p/a.py", "session_id": "other"},
        {"path": "D:/p/b.py", "session_id": SID},
    ]}
    (sandbox / f"state-{SID}.json").write_text(json.dumps(state), encoding="utf-8")
    assert asp.count_session_modified_files(SID, []) == 1


def test_count_missing_state_failopen_zero(sandbox):
    assert asp.count_session_modified_files("no-such-session", []) == 0


# ─── 3. plan_looks_rejected ──────────────────────────────────────────────────

def test_rejected_detection():
    assert asp.plan_looks_rejected("User rejected the plan")
    assert asp.plan_looks_rejected({"result": "Plan REJECTED by user"})
    assert not asp.plan_looks_rejected({"result": "ok, plan approved"})
    assert not asp.plan_looks_rejected("")


# ─── 4. handler 分級啟動 ─────────────────────────────────────────────────────

def _exit_plan_event(sid=SID):
    return {"session_id": sid, "tool_name": "ExitPlanMode",
            "cwd": "D:/proj", "tool_input": {}, "tool_response": "approved"}


def test_exitplan_emits_advisory_once(sandbox, capsys):
    code, parsed = _run(_exit_plan_event(), capsys=capsys)
    assert code == 0 and parsed is not None
    ctx = _ctx(parsed)
    assert "AcceptanceSpec" in ctx
    assert ".claude/verify/acceptance-" in ctx
    for token in ("必須發生", "禁止發生", "驗證指令",
                  "task_slug", "status: open", SID):
        assert token in ctx
    # 第二次同 session → 靜默
    code2, parsed2 = _run(_exit_plan_event(), capsys=capsys)
    assert parsed2 is None


def test_exitplan_rejected_silent(sandbox, capsys):
    ev = _exit_plan_event()
    ev["tool_response"] = "User rejected the plan"
    _, parsed = _run(ev, capsys=capsys)
    assert parsed is None
    assert not asp.read_sidecar(SID).get("plan_prompted")


def test_multifile_advisory_at_threshold_once(sandbox, capsys):
    _write_state(sandbox, ["D:/p/a.py", "D:/p/b.py", "D:/p/c.py"])
    ev = {"session_id": SID, "tool_name": "Edit", "cwd": "D:/p",
          "tool_input": {"file_path": "D:/p/c.py"}}
    _, parsed = _run(ev, capsys=capsys)
    assert parsed is not None
    assert "3 個檔案" in _ctx(parsed)
    # 再編輯 → 不再提醒
    _, parsed2 = _run(ev, capsys=capsys)
    assert parsed2 is None


def test_small_task_below_threshold_silent(sandbox, capsys):
    _write_state(sandbox, ["D:/p/a.py", "D:/p/b.py"])
    ev = {"session_id": SID, "tool_name": "Edit", "cwd": "D:/p",
          "tool_input": {"file_path": "D:/p/b.py"}}
    _, parsed = _run(ev, capsys=capsys)
    assert parsed is None


def test_plan_prompted_suppresses_multifile(sandbox, capsys):
    _run(_exit_plan_event(), capsys=capsys)  # plan 提醒過
    _write_state(sandbox, ["D:/p/a.py", "D:/p/b.py", "D:/p/c.py"])
    ev = {"session_id": SID, "tool_name": "Edit", "cwd": "D:/p",
          "tool_input": {"file_path": "D:/p/c.py"}}
    _, parsed = _run(ev, capsys=capsys)
    assert parsed is None


def test_spec_write_records_and_suppresses(sandbox, capsys):
    spec = "D:/p/.claude/verify/acceptance-my-task.md"
    ev = {"session_id": SID, "tool_name": "Write", "cwd": "D:/p",
          "tool_input": {"file_path": spec}}
    _, parsed = _run(ev, capsys=capsys)
    assert parsed is None
    assert asp.read_sidecar(SID).get("spec_paths") == [spec]
    # 之後多檔達門檻也不提醒（已有規格檔）
    _write_state(sandbox, ["D:/p/a.py", "D:/p/b.py", "D:/p/c.py"])
    ev2 = {"session_id": SID, "tool_name": "Edit", "cwd": "D:/p",
           "tool_input": {"file_path": "D:/p/c.py"}}
    _, parsed2 = _run(ev2, capsys=capsys)
    assert parsed2 is None


def test_non_write_tool_silent(sandbox, capsys):
    ev = {"session_id": SID, "tool_name": "Bash", "cwd": "D:/p",
          "tool_input": {"command": "ls"}}
    _, parsed = _run(ev, capsys=capsys)
    assert parsed is None


def test_missing_session_id_silent(sandbox, capsys):
    ev = {"session_id": "", "tool_name": "ExitPlanMode",
          "tool_input": {}, "tool_response": ""}
    _, parsed = _run(ev, capsys=capsys)
    assert parsed is None
