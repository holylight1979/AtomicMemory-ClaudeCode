"""verify_aec_emission_gate.py — Anti-Evasion HUD 收尾檢核閘（emit 滿足 + sibling 隔離）。

驗證 A/B（Anti-Evasion HUD）核心閉環的閘門正確性，比照 verify_scan_report_session_filter.py：
  - ScanReport 閘滿足方式從 prose 標記 → 本回合 emit anti_evasion_report（turn_seq+session_id 雙鍵）。
  - ★sibling 隔離：隔壁 session 的 emit（session_id 不符）不得放行本 session（本 initiative 核心防護）。
  - 純 commit turn 豁免、own 過濾等既有紀律不回歸。
  - severity 模型（Python/Node single source）+ HUD 不可達 fallback（可觀測性鐵律）。
  - one-writer：post_tool_use 收 MCP emit 事件 → 獨佔寫 state + 落 per-turn 報告檔。

對應：handlers/stop.py（emit 閘 + fallback）、handlers/post_tool_use.py（one-writer 落 state/檔）、
     wg_evasion.py（detect_missing_aec_emission / aec_severity）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from handlers import stop as st  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
from wg_evasion import detect_missing_aec_emission, aec_severity, _aec_blank  # noqa: E402

_SID = "sid"
_CORE = r"c:\a\.claude\hooks\x.py"
_DOC = r"c:\a\.claude\_AIDocs\note.md"
_DONE = "全部完成了"  # claims_completion=True


@pytest.fixture
def driven(monkeypatch):
    """驅動 handle_stop，只保留 gate 控制流；回 drive(modified_files, capsys, **extra) → stdout。

    比照 verify_scan_report_session_filter.py 的 driven fixture（同攔截面）。"""
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: _DONE)
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [])
    monkeypatch.setattr(st, "_maybe_spawn_per_turn_extraction", lambda *a, **k: None)
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)

    def drive(modified_files, capsys, **extra):
        state = {
            "phase": "working",
            "modified_files": modified_files,
            "failing_tests": [],
            "recent_user_prompts": [],
            "stop_blocked_count": 0,
        }
        state.update(extra)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, {})
        return capsys.readouterr().out

    return drive


def _mf(path, session_id=_SID):
    return {"path": path, "tool": "Edit", "session_id": session_id}


def _emit(turn_seq, session_id=_SID, severity="routine", a="無", b="無", c="無", d="無"):
    return {
        "turn_seq": turn_seq, "session_id": session_id,
        "a": a, "b": b, "c": c, "d": d, "severity": severity, "at": "now",
    }


# ─── emit 閘：滿足 / 未滿足 ───────────────────────────────────────

def test_own_core_no_emit_blocks(driven, capsys):
    """本 session own core + 宣告完成 + 未 emit → block，訊息要求呼叫 anti_evasion_report。"""
    out = driven([_mf(_CORE)], capsys, turn_seq=5)
    assert "[Guardian:ScanReport]" in out
    assert "anti_evasion_report" in out


def test_emit_this_turn_passes(driven, capsys):
    """本回合 emit（turn_seq+session_id 雙鍵皆符）→ 放行，不 block。"""
    out = driven([_mf(_CORE)], capsys, turn_seq=5, anti_evasion_report=_emit(5))
    assert "ScanReport" not in out


def test_sibling_emit_still_blocks(driven, capsys):
    """★核心 sibling 隔離：隔壁 session emit（session_id="other" 不符）→ 本 session 仍 block。

    模擬共用工作樹 / merged state 下，B 讀到的 state 含 A 戳的 emit；雙鍵防誤放行。"""
    out = driven([_mf(_CORE)], capsys, turn_seq=5,
                 anti_evasion_report=_emit(5, session_id="other"))
    assert "[Guardian:ScanReport]" in out


def test_prior_turn_emit_not_satisfied(driven, capsys):
    """emit 發生在別 turn（turn_seq 不符）→ 不滿足，照 block（不因歷史 emit 永久放行）。"""
    out = driven([_mf(_CORE)], capsys, turn_seq=5, anti_evasion_report=_emit(4))
    assert "[Guardian:ScanReport]" in out


def test_turn_seq_zero_guard(driven, capsys):
    """turn_seq==0 的 fallback state：bool(turn_seq)=False → emit 不以 0==0 假滿足 → block。"""
    out = driven([_mf(_CORE)], capsys, turn_seq=0, anti_evasion_report=_emit(0))
    assert "[Guardian:ScanReport]" in out


# ─── 既有紀律不回歸 ──────────────────────────────────────────────

def test_pure_commit_turn_exempt(driven, capsys):
    """純 commit turn 豁免不回歸：committed_this_turn → 不要求 emit（即使動 core）。"""
    out = driven([_mf(_CORE)], capsys, turn_seq=5, last_commit_turn_seq=5)
    assert "ScanReport" not in out


def test_foreign_core_not_triggered(driven, capsys):
    """own 過濾不回歸：他 session 改 core（session_id≠本）→ own 空 → 不觸發。"""
    out = driven([_mf(_CORE, session_id="other")], capsys, turn_seq=5)
    assert "ScanReport" not in out


def test_coordinator_docs_only_not_triggered(driven, capsys):
    """協調 session 只改單一 docs + 隔壁改 core → own 僅單一非 core → 不觸發。"""
    out = driven([_mf(_DOC), _mf(_CORE, session_id="other")], capsys, turn_seq=5)
    assert "ScanReport" not in out


# ─── HUD 不可達 fallback（可觀測性鐵律：push 不到窗不得 fail-silent）──────

def test_hud_fallback_surfaces_notable(driven, capsys):
    """emit 為 notable + HUD 不可達（aec_hud_fallback）→ Stop 大聲補 (a) 回 chat。"""
    out = driven(
        [_mf(_CORE)], capsys, turn_seq=5,
        anti_evasion_report=_emit(5, severity="notable", a="- x.py:10 — 修了 y"),
        aec_hud_fallback=True,
    )
    assert "[Guardian:AEC]" in out
    assert "缺失修補" in out


# ─── severity 模型（Python/Node single source of truth）──────────

@pytest.mark.parametrize("a,b,expected", [
    ("無", "無", "routine"),
    ("", "", "routine"),
    ("- x.py:1 — fix", "無", "notable"),
    ("無", "偷埋了 X", "real-evasion"),
    ("- x — y", "偷埋", "real-evasion"),  # (b) 優先於 (a)
])
def test_aec_severity(a, b, expected):
    assert aec_severity(a, b, "無", "無") == expected


def test_aec_severity_cd_informational():
    """(c)/(d) 非空不升級 severity（severity 只衡量退避訊號 (a)/(b)）。"""
    assert aec_severity("無", "無", "token 警示!", "temp/foo") == "routine"


@pytest.mark.parametrize("v,blank", [
    ("", True), ("無", True), ("  無  ", True), ("x", False), ("- a — b", False),
])
def test_aec_blank(v, blank):
    assert _aec_blank(v) is blank


# ─── detect_missing_aec_emission 前置門檻（鏡像 scan_report）─────

def _mfs(*paths):
    return [{"path": p, "tool": "Edit"} for p in paths]


def test_detect_no_completion_not_blocked():
    assert detect_missing_aec_emission("還在做", _mfs(_CORE), [], 2, False) is False


def test_detect_single_noncore_not_blocked():
    assert detect_missing_aec_emission(
        _DONE, _mfs(r"c:\a\.claude\memory\f.md"), [], 2, False
    ) is False


def test_detect_core_missing_emit_blocks():
    assert detect_missing_aec_emission(_DONE, _mfs(_CORE), [], 2, False) is True


def test_detect_core_emitted_not_blocked():
    assert detect_missing_aec_emission(_DONE, _mfs(_CORE), [], 2, True) is False


def test_detect_dismiss_prompt_not_blocked():
    assert detect_missing_aec_emission(_DONE, _mfs(_CORE), ["先這樣"], 2, False) is False


# ─── one-writer：post_tool_use 收 MCP emit → 獨佔寫 state + 落報告檔 ──────

def _drive_ptu(monkeypatch, tmp_path, tool_input, turn_seq=7, session_id=_SID):
    state = {"turn_seq": turn_seq}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "read_hot_cache", None)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(pt, "_hud_beat_fresh", lambda *a, **k: False)  # HUD 死
    monkeypatch.setattr(pt, "_spawn_hud_edge", lambda *a, **k: None)
    inp = {
        "session_id": session_id,
        "tool_name": "mcp__workflow-guardian__anti_evasion_report",
        "tool_input": tool_input,
        "tool_response": {},
    }
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}, "aec": {}})
    return state


def test_ptu_emit_writes_state_and_file(monkeypatch, tmp_path):
    """emit notable → state["anti_evasion_report"] 帶原始 session_id+turn_seq + 落 per-turn 檔
    + notable+HUD死 → aec_hud_fallback。"""
    state = _drive_ptu(
        monkeypatch, tmp_path,
        {"a": "- x.py:10 — fix", "b": "無", "c": "無", "d": "無"},
    )
    aec = state.get("anti_evasion_report")
    assert aec and aec["turn_seq"] == 7 and aec["session_id"] == _SID
    assert aec["severity"] == "notable"
    p = tmp_path / f"aec-report-{_SID}-t7.json"
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["a"].startswith("- x.py:10")
    assert data["session_id"] == _SID and data["turn_seq"] == 7
    assert state.get("aec_hud_fallback") is True


def test_ptu_routine_no_fallback(monkeypatch, tmp_path):
    """routine emit → 落檔但窗死不 fallback（無退避訊號、可事後由歷史格瀏覽）。"""
    state = _drive_ptu(
        monkeypatch, tmp_path,
        {"a": "無", "b": "無", "c": "無", "d": "無"},
    )
    assert state["anti_evasion_report"]["severity"] == "routine"
    assert (tmp_path / f"aec-report-{_SID}-t7.json").exists()
    assert not state.get("aec_hud_fallback")
