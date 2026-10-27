"""verify_data_file_via_need_goal.py：動資料檔宣告隨目標樹一起交（need_goal set／update 的 data_files，hooks/wg_data_file.declare_via_need_goal）。

為什麼：AI 改資料檔前本來就會呼叫 need_goal set 立樹；宣告另發一條只有註解的 Bash 多一個模型回合（006／007 實測）。
正例：set 帶 data_files=[{path, why}] → state data_file_declared 記 via=need_goal、留帳 declared_via_need_goal、回覆點名收下；
接著第一次 Edit 不擋（帳記 declared via=state）；why 空或只有佔位的那項不算（回覆點名沒收，改它照擋）；
讀檔提示與擋訊息提到「need_goal set 的 data_files」；v6 關：need_goal 分支整個不跑、state 不記、不留帳。
live 檔全 monkeypatch：WORKFLOW_DIR（state、目標檔落 tmp）、GUARD_LOG_DIR。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_data_file_via_need_goal.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_core  # noqa: E402
import wg_release_rules as rr  # noqa: E402
import wg_need_goal as ng  # noqa: E402
from handlers import post_tool_use as post  # noqa: E402
from handlers import pre_tool_use as ptu  # noqa: E402

SID = "sess-datafile-ng-0001"
NG_TOOL = "mcp__workflow-guardian__need_goal"
PROMPT = "report 的 cli 加一個 `--format csv`，小數位照設定檔。"
OLD = '{"decimals": 0,}'
NEW = '{"decimals": 0}'
WHY = "修掉多逗號讓 cli 讀得到；幣別會從預設 USD 變成檔內的 TWD"


@pytest.fixture
def world(tmp_path, monkeypatch):
    proj = tmp_path / "qb-report"
    proj.mkdir()
    (proj / "settings.json").write_text(OLD + "\n", encoding="utf-8")
    (proj / "app.py").write_text("x = 1\n", encoding="utf-8")
    wf = tmp_path / "wf"
    wf.mkdir()
    logs = tmp_path / "Logs"
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(post, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", logs)
    monkeypatch.setattr(wg_core, "_rebuild_min_atom_index", lambda cwd: {})
    monkeypatch.setattr(wg_core, "_find_active_sibling_state", lambda *a, **k: None)
    monkeypatch.setattr(wg_core, "_atom_debug_log", lambda *a, **k: None)
    outputs = []

    def _out(d):
        outputs.append(d)
        raise SystemExit(0)

    def _nothing():
        outputs.append(None)
        raise SystemExit(0)
    monkeypatch.setattr(ptu, "output_json", _out)
    monkeypatch.setattr(ptu, "output_nothing", _nothing)
    sent = []
    monkeypatch.setattr(post, "_emit_post_tool_output", lambda adv, msgs: sent.append("\n".join(adv)))
    wg_core.write_state(SID, {"session": {"id": SID, "cwd": str(proj)}, "turn_seq": 1,
                              "recent_user_prompts": [PROMPT], "turn_prompts": [PROMPT]})
    tp = tmp_path / "t.jsonl"
    tp.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": PROMPT}}, ensure_ascii=False) + "\n",
                  encoding="utf-8")
    return {"proj": proj, "tp": str(tp), "outputs": outputs, "logs": logs, "sent": sent}


def _post(w, tool, tool_input, config=None):
    w["sent"].clear()
    post.handle_post_tool_use({"session_id": SID, "cwd": str(w["proj"]), "tool_name": tool, "tool_input": tool_input,
                               "tool_response": {}, "transcript_path": w["tp"]}, config or {})
    return "\n".join(w["sent"])


def _need_goal(w, data_files, action="set", config=None):
    op = {"action": action, "goal": "cli 要讀得到設定檔", "kind": "code", "data_files": data_files}
    if action == "update":
        op = {"action": "update", "items": [{"id": "T1", "status": "doing"}], "data_files": data_files}
    return _post(w, NG_TOOL, op, config)


def _edit(w):
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": "Edit", "session_id": SID, "cwd": str(w["proj"]), "transcript_path": w["tp"],
                                 "tool_input": {"file_path": str(w["proj"] / "settings.json"), "old_string": OLD,
                                                "new_string": NEW}}, {})
    return w["outputs"][-1]


def _df_deny(out):
    hso = (out or {}).get("hookSpecificOutput") or {}
    return hso.get("permissionDecision") == "deny" and "[Guardian:DataFileAsk]" in hso.get("permissionDecisionReason", "")


def _log(w):
    p = w["logs"] / "guard-data_file.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def _declared(w):
    return (wg_core.read_state(SID).get("data_file_declared") or {})


def test_need_goal_set_with_data_files_marks_declared(world):
    ctx = _need_goal(world, [{"path": "settings.json", "why": WHY}])
    assert "[NeedGoal] set 收下" in ctx and "宣告收下" in ctx and "settings.json" in ctx
    key = rr.canon_path(str(world["proj"] / "settings.json"))
    entry = _declared(world)[key]
    assert entry["via"] == "need_goal" and entry["line"].startswith("動資料檔｜settings.json：") and "at" in entry
    assert [e["event"] for e in _log(world)] == ["declared_via_need_goal"]
    assert ng.active_tree(ng.load(SID))["id"] == "T1", "樹照立"


def test_update_with_data_files_marks_declared_too(world):
    _need_goal(world, None)
    assert not _declared(world)
    ctx = _need_goal(world, [{"path": str(world["proj"] / "settings.json"), "why": WHY}], action="update")
    assert "宣告收下" in ctx and rr.canon_path(str(world["proj"] / "settings.json")) in _declared(world)


def test_first_edit_after_declared_via_tree_not_denied(world):
    _need_goal(world, [{"path": "settings.json", "why": WHY}])
    assert not _df_deny(_edit(world))
    ev = _log(world)[-1]
    assert ev["event"] == "declared" and ev["via"] == "state"


def test_without_data_files_first_edit_still_denied(world):
    _need_goal(world, None)
    assert _df_deny(_edit(world))


@pytest.mark.parametrize("why", ["", "。。", "<為什麼要動它、動了使用者會看到什麼>"])
def test_missing_why_not_counted(world, why):
    ctx = _need_goal(world, [{"path": "settings.json", "why": why}])
    assert "[NeedGoal] set 收下" in ctx and "沒收" in ctx and "宣告收下" not in ctx
    assert not _declared(world)
    assert [e["event"] for e in _log(world)] == ["declared_skipped"]
    assert _df_deny(_edit(world))


def test_shape_errors_rejected_in_python_mirror():
    assert ng.validate_input({"action": "set", "goal": "G", "data_files": "settings.json"}) == \
        ["data_files 必須是陣列（[{path, why}]：要動的使用者資料檔與為什麼）"]
    errs = ng.validate_input({"action": "set", "goal": "G", "data_files": [{"why": "x"}, "s", {"path": "a.json", "why": 3}]})
    assert len(errs) == 3 and "data_files[0].path 必填" in errs[0] and "data_files[1] 必須是物件" in errs[1] \
        and "data_files[2].why 必須是字串" in errs[2]
    assert ng.validate_input({"action": "set", "goal": "G", "data_files": [{"path": "a.json", "why": "x"}]}) == []
    assert ng.validate_input({"action": "update", "items": [{"id": "T1", "status": "doing"}], "data_files": [{"path": "a.json"}]}) == []


def test_hint_mentions_need_goal_option(world):
    hint = _post(world, "Read", {"file_path": str(world["proj"] / "settings.json")})
    assert "[Guardian:DataFileAsk] 改 settings.json 前先宣告" in hint and "need_goal set 的 data_files" in hint
    out = _edit(world)
    assert _df_deny(out) and "need_goal set 的 data_files" in (out["hookSpecificOutput"]["permissionDecisionReason"])


def test_v6_off_unchanged(world, monkeypatch):
    monkeypatch.setenv("WG_V6", "0")
    ctx = _need_goal(world, [{"path": "settings.json", "why": WHY}])
    assert "宣告收下" not in ctx and not _declared(world) and not _log(world)
    assert not _df_deny(_edit(world)), "v6 關：動資料檔閘本來就不跑"
    assert not _log(world)
