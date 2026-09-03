"""verify_aec_crosscheck.py — AEC (b) 欄 cross-check（hook 實測 vs 模型自評）。

驗證「不信模型自評」閉環：
  - crosscheck_aec_severity（wg_evasion 純函式）：hook 證據非空 + (b)=「無」→ 升
    real-evasion；(b) 已誠實填報 / 無證據 → 不動。
  - _collect_aec_evidence（post_tool_use）：evasion_events 依「上次 emit 之後」
    窗口過濾（>=，同 turn 內 Stop 在 emit 後）+ 現行 evasion_flag 合流不重複。
  - one-writer 整合：emit 時 report 落 severity_upgraded_by + hook_evidence。

對應：hooks/wg_evasion.py（crosscheck_aec_severity）、
     handlers/post_tool_use.py（_collect_aec_evidence + AEC emit branch）、
     handlers/stop.py（evasion_events 證據暫存）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from wg_evasion import crosscheck_aec_severity  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402

_SID = "sid-main"
_EV = [{"phrase": "留給未來", "turn_seq": 3, "at": "2026-07-08T00:00:00"}]


# ─── crosscheck_aec_severity（純函式）─────────────────────────────────────────


def test_evidence_and_blank_b_upgrades():
    """hook 證據非空 + (b)=「無」→ 升 real-evasion。"""
    sev, up = crosscheck_aec_severity("routine", "無", _EV)
    assert sev == "real-evasion" and up is True


def test_blank_b_with_punctuation_still_upgrades():
    """(b)=「無。」（模型慣寫尾標點）仍視為 blank → 升級。"""
    sev, up = crosscheck_aec_severity("notable", "無。", _EV)
    assert sev == "real-evasion" and up is True


def test_honest_b_not_double_upgraded():
    """(b) 誠實填報（非空敘述）→ 內容 severity 本就 real-evasion，不重複升級。"""
    sev, up = crosscheck_aec_severity("real-evasion", "有：偷埋了 X", _EV)
    assert sev == "real-evasion" and up is False


def test_no_evidence_no_upgrade():
    """無 hook 證據 → 不動（routine 維持）。"""
    sev, up = crosscheck_aec_severity("routine", "無", [])
    assert sev == "routine" and up is False


# ─── _collect_aec_evidence（窗口過濾 + flag 合流）─────────────────────────────


def test_evidence_window_after_prev_emit():
    """同 session 上份報告 turn=5 → 事件 turn<5 排除、>=5 保留（Stop 在 emit 後）。"""
    state = {
        "anti_evasion_report": {"session_id": _SID, "turn_seq": 5},
        "evasion_events": [
            {"phrase": "old", "turn_seq": 4, "at": "t4"},
            {"phrase": "same-turn", "turn_seq": 5, "at": "t5"},
            {"phrase": "new", "turn_seq": 6, "at": "t6"},
        ],
    }
    ev = pt._collect_aec_evidence(state, _SID)
    assert [e["phrase"] for e in ev] == ["same-turn", "new"]


def test_evidence_foreign_prev_report_includes_all():
    """上份報告屬他 session → 窗口不成立，全 session 事件都算證據。"""
    state = {
        "anti_evasion_report": {"session_id": "other", "turn_seq": 99},
        "evasion_events": [{"phrase": "x", "turn_seq": 1, "at": "t1"}],
    }
    ev = pt._collect_aec_evidence(state, _SID)
    assert len(ev) == 1


def test_evidence_merges_live_flag_without_dup():
    """現行未清 evasion_flag 合流；at 相同者不重複。"""
    state = {
        "turn_seq": 7,
        "evasion_events": [{"phrase": "a", "turn_seq": 7, "at": "tA"}],
        "evasion_flag": {"phrase": "b", "at": "tB", "context_excerpt": ""},
    }
    ev = pt._collect_aec_evidence(state, _SID)
    assert {e["phrase"] for e in ev} == {"a", "b"}
    # 同 at 不重複
    state["evasion_flag"] = {"phrase": "a", "at": "tA"}
    ev2 = pt._collect_aec_evidence(state, _SID)
    assert len(ev2) == 1


# ─── one-writer 整合：emit → report 落升級欄位 ───────────────────────────────


def test_emit_report_carries_upgrade(monkeypatch):
    """AEC emit branch：hook 證據 + (b)=無 → report severity=real-evasion +
    severity_upgraded_by + hook_evidence 落 state（一併進 per-turn 檔）。"""
    state = {
        "turn_seq": 4,
        "evasion_events": [{"phrase": "先跳過", "turn_seq": 3, "at": "t3"}],
    }
    written = {}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda sid, st: written.update(st))
    monkeypatch.setattr(pt, "_write_aec_report_file", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_maybe_spawn_hud", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use(
            {
                "session_id": _SID,
                "tool_name": "mcp__workflow-guardian__anti_evasion_report",
                "tool_input": {"a": "無", "b": "無", "c": "無", "d": "無"},
            },
            {},
        )
    rep = written.get("anti_evasion_report") or state.get("anti_evasion_report")
    assert rep["severity"] == "real-evasion"
    assert rep["severity_upgraded_by"] == "hook:evasion-crosscheck"
    assert rep["hook_evidence"][0]["phrase"] == "先跳過"


def test_emit_report_routine_when_clean(monkeypatch):
    """無證據 + (a)(b) 皆無 → routine、無升級欄位（不誤傷 routine 報告）。"""
    state = {"turn_seq": 4}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_write_aec_report_file", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_maybe_spawn_hud", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use(
            {
                "session_id": _SID,
                "tool_name": "mcp__workflow-guardian__anti_evasion_report",
                "tool_input": {"a": "無", "b": "無", "c": "無", "d": "無"},
            },
            {},
        )
    rep = state["anti_evasion_report"]
    assert rep["severity"] == "routine"
    assert "severity_upgraded_by" not in rep


def test_emit_report_upgrade_composes_b_content(monkeypatch):
    """升級時 (b) 欄改寫為含 hook 證據的內容（HUD 卡片只渲染 b；紅框不得指著空卡），
    模型原自評另存 b_model。"""
    state = {
        "turn_seq": 4,
        "evasion_events": [{"phrase": "先跳過", "turn_seq": 3, "at": "t3"}],
    }
    written = {}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda sid, st: written.update(st))
    monkeypatch.setattr(pt, "_write_aec_report_file", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_maybe_spawn_hud", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use(
            {
                "session_id": _SID,
                "tool_name": "mcp__workflow-guardian__anti_evasion_report",
                "tool_input": {"a": "無", "b": "無", "c": "無", "d": "無"},
            },
            {},
        )
    rep = written.get("anti_evasion_report") or state.get("anti_evasion_report")
    assert "先跳過" in rep["b"] and "turn 3" in rep["b"]
    assert rep["b_model"] == "無"
