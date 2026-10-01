"""verify_knowledge_harvest_gate.py — 階段完工知識收割：Stop 閘 + receipt 核對 + AEC 互動 + SyncReminder 活鎖。

對應：handlers/stop.py（KnowledgeHarvest / Harvest-Pending 閘、_git_unpushed_roots 活鎖跳過）、
     handlers/post_tool_use.py（atom_write/atom_retire receipt 入帳、knowledge_harvest_report 核對）、
     wg_harvest.py（純函式）。
驅動方式比照 verify_aec_emission_gate.py 的 driven fixture（只留 gate 控制流）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from handlers import stop as st  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
import wg_harvest as wh  # noqa: E402

_SID = "sid"
_DONE = "全部完成了"
_CORE = r"c:\a\.claude\hooks\x.py"
_ATOM_PATH = r"C:\Users\u\.claude\memory\dotnet\foo-bar.md"
_CFG = {"harvest": {"enabled": True, "min_turns": 3, "min_accessed": 5, "min_turns_between": 3}}
_PTU_CFG = {"docdrift": {"enabled": False}, "aec": {}, **_CFG}


def _mf(path, session_id=_SID):
    return {"path": path, "tool": "Edit", "session_id": session_id}


def _state(**extra):
    s = {
        "phase": "working", "modified_files": [], "failing_tests": [],
        "recent_user_prompts": [], "stop_blocked_count": 0, "turn_seq": 5,
    }
    s.update(extra)
    return s


@pytest.fixture
def driven(monkeypatch):
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [])
    monkeypatch.setattr(st, "_git_unpushed_roots", lambda mf: [])
    monkeypatch.setattr(st, "_should_deep_postmortem", lambda *a, **k: False)
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)
    monkeypatch.setattr(st, "_hud_alive", lambda *a, **k: (True, {}))

    def drive(capsys, state, config=_CFG, last_text=_DONE):
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: last_text)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, config)
        return capsys.readouterr().out

    return drive


@pytest.fixture
def ptu(monkeypatch, tmp_path, capsys):
    """驅動 handle_post_tool_use；回 run(state, tool_name, tool_input, tool_response) → (stdout, spawned)。"""
    spawned = []
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(pt, "_hud_alive", lambda *a, **k: (True, {}))
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_write_aec_report_file", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_run_companion_hooks", lambda *a, **k: ([], []))
    monkeypatch.setattr(pt.aec_ledger, "collect_at_completion", lambda *a, **k: 0)
    monkeypatch.setattr(
        pt, "spawn_vcs_sync",
        lambda sid, cwd, reason, retired_paths=None: spawned.append((sid, cwd, reason, list(retired_paths or []))),
    )

    def run(state, tool_name, tool_input, tool_response=None, session_id=_SID):
        monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
        inp = {
            "session_id": session_id, "cwd": "c:/proj",
            "tool_name": f"mcp__workflow-guardian__{tool_name}",
            "tool_input": tool_input, "tool_response": tool_response or {},
        }
        with pytest.raises(SystemExit):
            pt.handle_post_tool_use(inp, _PTU_CFG)
        return capsys.readouterr().out, spawned

    run.ledger = tmp_path / "harvest-ledger" / f"{_SID}.jsonl"
    return run


def _receipt_resp(op, path=_ATOM_PATH, atom="foo-bar", index_ok=True, **extra):
    rec = {"op": op, "atom": atom, "path": path, "index_ok": index_ok, "supersedes": [],
           "old_path": "", "new_path": "", **extra}
    return {"content": [{"type": "text", "text": "✓ 寫入 atom\nreceipt: " + json.dumps(rec, ensure_ascii=False)}]}


def _item(action, atom="foo-bar", path=_ATOM_PATH, **extra):
    return {"source": "mechanism", "summary": "x", "action": action, "atom": atom, "path": path,
            "scope": "global", **extra}


# ─── KnowledgeHarvest 閘觸發條件 ──────────────────────────────────

def test_gate_triggers_and_does_not_eat_shared_budget(driven, capsys):
    state = _state(modified_files=[_mf(_CORE)])
    out = driven(capsys, state)
    assert "[Guardian:KnowledgeHarvest]" in out and "knowledge_harvest_report" in out
    assert "items=[]" in out and "⑥" in out  # 六個來源與 items=[] 也要呼叫
    assert state["stop_blocked_count"] == 0
    assert state["harvest_gate_turn"][_SID] == 5


def test_gate_once_per_turn(driven, capsys):
    state = _state(modified_files=[_mf(_CORE)], harvest_gate_turn={_SID: 5})
    assert "KnowledgeHarvest" not in driven(capsys, state)


def test_zero_turn_no_trigger(driven, capsys):
    state = _state(turn_seq=0, modified_files=[_mf(_CORE)])
    assert "KnowledgeHarvest" not in driven(capsys, state)


def test_no_activity_no_trigger_but_accessed_threshold_counts(driven, capsys):
    assert "KnowledgeHarvest" not in driven(capsys, _state(turn_seq=2))
    accessed = [{"path": f"c:/a/{i}.py", "at": "now"} for i in range(5)]
    assert "KnowledgeHarvest" in driven(capsys, _state(turn_seq=2, accessed_files=accessed))


def test_no_completion_claim_no_trigger(driven, capsys):
    out = driven(capsys, _state(modified_files=[_mf(_CORE)]), last_text="還在查原因")
    assert "KnowledgeHarvest" not in out


def test_dismiss_prompt_skips(driven, capsys):
    state = _state(modified_files=[_mf(_CORE)], recent_user_prompts=["先這樣"])
    assert "KnowledgeHarvest" not in driven(capsys, state)


def test_config_section_absent_is_off(driven, capsys):
    out = driven(capsys, _state(modified_files=[_mf(_CORE)]), config={})
    assert "KnowledgeHarvest" not in out


def test_cooldown_only_counts_validated(driven, capsys):
    validated_t4 = {_SID: {"turn_seq": 4, "validated": True, "pending": [], "items": [],
                           "last_valid_harvest_turn": 4}}
    assert "KnowledgeHarvest" not in driven(capsys, _state(knowledge_harvest=validated_t4))
    assert "KnowledgeHarvest" in driven(capsys, _state(turn_seq=7, knowledge_harvest=validated_t4))


def test_sibling_session_harvest_does_not_release(driven, capsys):
    other = {"other": {"turn_seq": 5, "validated": True, "pending": [], "items": [],
                       "last_valid_harvest_turn": 5}}
    assert "[Guardian:KnowledgeHarvest]" in driven(capsys, _state(knowledge_harvest=other))


# ─── receipt 入帳與收割核對（post_tool_use one-writer）────────────

def test_empty_items_validates_and_releases(driven, ptu, capsys):
    state = _state(modified_files=[_mf(_CORE)])
    out, spawned = ptu(state, "knowledge_harvest_report", {"items": []})
    sec = state["knowledge_harvest"][_SID]
    assert sec["validated"] is True and sec["pending"] == [] and sec["last_valid_harvest_turn"] == 5
    assert spawned == [(_SID, "c:/proj", "harvest", [])]
    assert ptu.ledger.exists() and json.loads(ptu.ledger.read_text(encoding="utf-8").splitlines()[-1])["validated"]
    assert "Harvest-Pending" not in out
    out = driven(capsys, state)
    assert "KnowledgeHarvest" not in out and "Harvest-Pending" not in out


def test_item_without_receipt_pending_then_fixed(driven, ptu, capsys):
    state = _state(modified_files=[_mf(_CORE)])
    out, spawned = ptu(state, "knowledge_harvest_report", {"items": [_item("created")]})
    sec = state["knowledge_harvest"][_SID]
    assert sec["validated"] is False and "無 create receipt" in sec["pending"][0]
    assert "[Guardian:Harvest-Pending]" in out and not spawned
    # Stop：Harvest-Pending 擋一次、不吃預算；同 turn 再 Stop 不再擋
    out = driven(capsys, state)
    assert "[Guardian:Harvest-Pending]" in out and "foo-bar" in out
    assert state["stop_blocked_count"] == 0 and state["harvest_pending_gate_turn"][_SID] == 5
    assert "Harvest-Pending" not in driven(capsys, state)
    # 補 receipt → 重報 → validated → 放行
    ptu(state, "atom_write", {"name": "foo-bar"}, _receipt_resp("create"))
    assert state["atom_ops"][_SID][0]["op"] == "create" and state["atom_ops"][_SID][0]["ok"] is True
    out, spawned = ptu(state, "knowledge_harvest_report", {"items": [_item("created")]})
    assert state["knowledge_harvest"][_SID]["validated"] is True and spawned
    out = driven(capsys, state)
    assert "KnowledgeHarvest" not in out and "Harvest-Pending" not in out


def test_failed_receipt_recorded_but_not_evidence(ptu):
    state = _state()
    ptu(state, "atom_retire", {"atom_name": "foo-bar"},
        _receipt_resp("retire", ok=False, old_path=_ATOM_PATH, steps_failed=["index"]))
    assert state["atom_ops"][_SID][0]["ok"] is False
    ptu(state, "knowledge_harvest_report", {"items": [_item("retired")]})
    assert state["knowledge_harvest"][_SID]["validated"] is False


def test_index_not_ok_is_pending(ptu):
    state = _state()
    ptu(state, "atom_write", {}, _receipt_resp("append", index_ok=False))
    ptu(state, "knowledge_harvest_report", {"items": [_item("appended")]})
    assert "index_ok=false" in state["knowledge_harvest"][_SID]["pending"][0]


def test_superseded_and_retired_match(ptu):
    state = _state()
    ptu(state, "atom_write", {}, _receipt_resp("create", path=r"c:\m\new.md", atom="new", supersedes=["old-atom"]))
    ptu(state, "atom_retire", {}, _receipt_resp("retire", atom="dead", path="", old_path=r"c:\m\dead.md",
                                                new_path=r"c:\m\_distant\dead.md"))
    items = [_item("superseded", atom="old-atom", path=r"c:/m/old.md"),
             _item("retired", atom="dead", path="C:/M/DEAD.MD"),
             _item("skip", atom="", path="", reason="一次性事實")]
    ptu(state, "knowledge_harvest_report", {"items": items})
    assert state["knowledge_harvest"][_SID]["validated"] is True


def test_receipts_before_last_validated_not_reused(ptu):
    state = _state()
    ptu(state, "atom_write", {}, _receipt_resp("create"))
    ptu(state, "knowledge_harvest_report", {"items": [_item("created")]})
    assert state["knowledge_harvest"][_SID]["validated"] is True
    ptu(state, "knowledge_harvest_report", {"items": [_item("created")]})
    assert state["knowledge_harvest"][_SID]["validated"] is False


def test_receipt_only_from_same_session(ptu):
    state = _state()
    ptu(state, "atom_write", {}, _receipt_resp("create"), session_id="other")
    ptu(state, "knowledge_harvest_report", {"items": [_item("created")]})
    assert state["knowledge_harvest"][_SID]["validated"] is False


def test_no_receipt_line_not_recorded(ptu):
    state = _state()
    ptu(state, "atom_write", {}, {"content": [{"type": "text", "text": "✗ 拒寫：重複"}]})
    assert _SID not in (state.get("atom_ops") or {})


# ─── items 欄位自驗（不信 Node 端已擋）與 MCP 拒收不當回報 ────────

@pytest.mark.parametrize("bad, why", [
    (_item("deleted"), "action='deleted'"),
    (_item("created", path=""), "必填 atom 與 path"),
    (_item("created", atom=""), "必填 atom 與 path"),
    (_item("skip", atom="", path=""), "必填 reason"),
    (_item("created", source="gossip"), "source='gossip'"),
])
def test_bad_item_fields_are_pending(ptu, bad, why):
    state = _state()
    ptu(state, "atom_write", {}, _receipt_resp("create"))
    out, spawned = ptu(state, "knowledge_harvest_report", {"items": [bad, _item("created")]})
    sec = state["knowledge_harvest"][_SID]
    assert sec["validated"] is False and not spawned
    assert len(sec["pending"]) == 1 and "欄位不合格" in sec["pending"][0] and why in sec["pending"][0]
    assert "[Guardian:Harvest-Pending]" in out


def test_items_not_list_is_pending(ptu):
    state = _state()
    ptu(state, "knowledge_harvest_report", {"items": {"action": "created"}})
    assert state["knowledge_harvest"][_SID]["validated"] is False


@pytest.mark.parametrize("resp", [
    {"content": [{"type": "text", "text": "knowledge_harvest_report 拒收：\n  ✗ items[0].action 無效"}], "isError": True},
    {"content": [{"type": "text", "text": "knowledge_harvest_report: items 必須是陣列"}], "is_error": True},
    {"content": [{"type": "text", "text": "Error: tool crashed"}]},
])
def test_mcp_error_response_is_not_a_report(ptu, resp):
    state = _state()
    out, spawned = ptu(state, "knowledge_harvest_report", {"items": [_item("created")]}, resp)
    assert "knowledge_harvest" not in state and not spawned and not ptu.ledger.exists()
    assert "Harvest-Pending" not in out


# ─── validated 收割才把退役檔交給 vcs-sync；ledger 記 validated ────

def test_spawn_carries_only_validated_retired_paths(ptu):
    state = _state()
    ptu(state, "atom_retire", {}, _receipt_resp("retire", atom="dead", path="", old_path=r"c:\m\dead.md",
                                                new_path=r"c:\m\_distant\dead.md"))
    ptu(state, "atom_write", {}, _receipt_resp("create"))
    items = [_item("retired", atom="dead", path="C:/M/DEAD.MD"), _item("created")]
    _, spawned = ptu(state, "knowledge_harvest_report", {"items": items})
    assert spawned == [(_SID, "c:/proj", "harvest", [r"c:\m\dead.md"])]
    rec = json.loads(ptu.ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["validated"] is True and rec["retired_paths"] == [r"c:\m\dead.md"]


def test_failed_retire_receipt_not_in_spawn_and_ledger_marks_invalid(ptu):
    state = _state()
    ptu(state, "atom_retire", {}, _receipt_resp("retire", ok=False, atom="dead", path="", old_path=r"c:\m\dead.md"))
    _, spawned = ptu(state, "knowledge_harvest_report", {"items": [_item("retired", atom="dead", path=r"c:\m\dead.md")]})
    assert not spawned
    rec = json.loads(ptu.ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["validated"] is False and rec["retired_paths"] == []


# ─── AEC 與收割兩種呼叫順序皆不互擋 ──────────────────────────────

_AEC_INPUT = {k: "無" for k in "abcefgi"} | {"d": "- 坑 → 尚未寫", "h": "可關閉"}


def test_aec_then_harvest_clears_d_pending(driven, ptu, capsys):
    state = _state(modified_files=[_mf(_CORE)])
    ptu(state, "anti_evasion_report", _AEC_INPUT)
    assert state["anti_evasion_report"]["d_pending"]
    ptu(state, "knowledge_harvest_report", {"items": []})
    assert "d_pending" not in state["anti_evasion_report"]
    out = driven(capsys, state)
    assert "AEC-Pending" not in out and "KnowledgeHarvest" not in out and "ScanReport" not in out


def test_harvest_then_aec_skips_d_pending(driven, ptu, capsys):
    state = _state(modified_files=[_mf(_CORE)])
    ptu(state, "knowledge_harvest_report", {"items": []})
    out, _ = ptu(state, "anti_evasion_report", _AEC_INPUT)
    assert "d_pending" not in state["anti_evasion_report"] and "AEC-Pending" not in out
    out = driven(capsys, state)
    assert "AEC-Pending" not in out and "KnowledgeHarvest" not in out and "ScanReport" not in out


def test_harvest_validated_still_requires_h_pending(ptu):
    state = _state()
    ptu(state, "knowledge_harvest_report", {"items": []})
    ptu(state, "anti_evasion_report", {**_AEC_INPUT, "d": "無", "h": "下一動＝寫 atom"})
    assert state["anti_evasion_report"]["d_pending"]


def test_aec_h_pending_survives_later_harvest(driven, ptu, capsys):
    """(d)/(h) 共用 d_pending：收割只替 (d) 背書，(h)「下一動＝寫 atom」要留著讓 AEC-Pending 擋。"""
    state = _state(modified_files=[_mf(_CORE)])
    ptu(state, "anti_evasion_report", {**_AEC_INPUT, "h": "下一動＝寫 atom"})
    assert len(state["anti_evasion_report"]["d_pending"]) == 2  # (d) 尚未寫 + (h)
    ptu(state, "knowledge_harvest_report", {"items": []})
    pend = state["anti_evasion_report"]["d_pending"]
    assert len(pend) == 1 and pend[0].startswith("(h) ")
    out = driven(capsys, state)
    assert "[Guardian:AEC-Pending]" in out and "KnowledgeHarvest" not in out


# ─── 中途狀態句不是收尾：三閘都不擋 ──────────────────────────────

_MIDWAY = [
    "A2 已完成，仍在等 A1 回報。",
    "兩支 agent 都完成了，等待 A3 回報後再整合。",
    "A1 完成；整合尚未開始。",
    "搞定前半，目前中途，先回報進度。",
]


@pytest.mark.parametrize("text", _MIDWAY)
def test_midway_text_does_not_trigger_harvest_gate(driven, capsys, text):
    assert "KnowledgeHarvest" not in driven(capsys, _state(modified_files=[_mf(_CORE)]), last_text=text)


@pytest.mark.parametrize("text", _MIDWAY)
def test_midway_text_does_not_trigger_pending_gate(driven, capsys, text):
    pending = {_SID: {"turn_seq": 4, "validated": False, "pending": ["foo-bar: 無 create receipt"], "items": []}}
    state = _state(knowledge_harvest=pending)
    assert "Harvest-Pending" not in driven(capsys, state, last_text=text)
    assert _SID not in (state.get("harvest_pending_gate_turn") or {})
    assert "[Guardian:Harvest-Pending]" in driven(capsys, state)  # 真收尾句才擋


# ─── SyncReminder：vcs-sync worker 活鎖中的 root 跳過 unpushed 判定 ──

def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd)] + list(args), check=True,
                   capture_output=True, text=True, timeout=15)


@pytest.fixture
def ahead_clone(tmp_path):
    bare = tmp_path / "up.git"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(bare), str(work))
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    (work / "a.py").write_text("x", encoding="utf-8")
    _git(work, "add", "a.py")
    _git(work, "commit", "-q", "-m", "init")
    _git(work, "push", "-q", "-u", "origin", "HEAD")
    (work / "a.py").write_text("y", encoding="utf-8")
    _git(work, "commit", "-q", "-am", "more")
    return work


def test_sync_reminder_skips_root_with_live_lock(ahead_clone, tmp_path, monkeypatch):
    monkeypatch.setattr(wh, "WORKFLOW_DIR", tmp_path / "wf")
    mf = [{"path": str(ahead_clone / "a.py")}]
    assert st._git_unpushed_roots(mf)  # 無鎖：領先 → 列出
    lock = wh.vcs_sync_lock_path(ahead_clone)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(str(os.getpid()), encoding="utf-8")  # 活 pid
    assert st._git_unpushed_roots(mf) == []
    monkeypatch.setattr(wh, "_is_pid_alive", lambda pid: False)  # 殘鎖（pid 死）→ 照常判定
    assert st._git_unpushed_roots(mf)
    lock.write_text("not-a-pid", encoding="utf-8")
    assert st._git_unpushed_roots(mf)


def test_lock_path_is_sha1_of_lowercase_posix_root(tmp_path):
    import hashlib
    key = tmp_path.resolve().as_posix().lower()
    expect = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12] + ".lock"
    assert wh.vcs_sync_lock_path(tmp_path, tmp_path).name == expect


def test_item_missing_summary_is_bad_field():
    bad = wh._item_fields_bad({"source": "mechanism", "action": "skip", "atom": "x", "reason": "r"})
    assert bad and "summary" in bad
    ok = wh._item_fields_bad({"source": "mechanism", "summary": "s", "action": "skip", "atom": "x", "reason": "r"})
    assert ok is None
