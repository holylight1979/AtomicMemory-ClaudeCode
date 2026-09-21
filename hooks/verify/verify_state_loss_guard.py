"""verify_state_loss_guard.py — 活躍 session 的 state 不得因暫時讀不到或 30 分鐘沒動就被換掉／刪掉。

2026-09-21 實證：主持 session 在 turn 15 時 state 被 fallback 覆蓋（turn_seq 歸 1、歷史全失）。
兩個獨立成因都要守：
1. read_state 把「檔在但讀失敗（另一支 hook 正 tmp+replace／鎖住、或 JSON 半寫）」與「檔不存在」混為 None，
   _ensure_state 就建 fallback 覆蓋 → 現在讀失敗重試三次、仍失敗就本次 hook 跳過（回 None），不覆蓋。
2. _cleanup_old_states 對「有 prompt 的 working state」30 分鐘沒寫就刪 → 放寬到 6 小時。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_core  # noqa: E402
from handlers import _shared  # noqa: E402


def _active_state(sid: str, turn: int = 15) -> dict:
    return {"session": {"id": sid, "cwd": "C:/x", "started_at": "2026-09-21T10:00:00+08:00", "source": "startup"},
            "phase": "working", "turn_seq": turn, "topic_tracker": {"prompt_count": turn},
            "atom_index": {"global": [], "project": []}, "injected_atoms": ["a"]}


def test_read_state_status_distinguishes_missing_and_error(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path)
    assert wg_core.read_state_status("nope") == (None, "missing")
    p = wg_core.state_path("bad")
    p.write_text("{not json", encoding="utf-8")
    assert wg_core.read_state_status("bad") == (None, "error")
    p.write_text(json.dumps(_active_state("bad")), encoding="utf-8")
    st, status = wg_core.read_state_status("bad")
    assert status == "ok" and st["turn_seq"] == 15


def test_ensure_state_does_not_overwrite_on_transient_read_error(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path)
    sid = "s-guard"
    p = wg_core.state_path(sid)
    p.write_text("{half-written", encoding="utf-8")  # 模擬另一支 hook 正在寫／JSON 半寫
    before = p.read_text(encoding="utf-8")
    out = wg_core._ensure_state(sid, {"session_id": sid, "cwd": "C:/x"}, {})
    assert out is None                      # 本次 hook 放棄
    assert p.read_text(encoding="utf-8") == before  # 沒被 fallback 覆蓋


def test_ensure_state_recovers_when_read_succeeds_on_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path)
    sid = "s-retry"
    p = wg_core.state_path(sid)
    p.write_text("{half", encoding="utf-8")
    calls = {"n": 0}
    real = wg_core.read_state_status

    def flaky(session_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return None, "error"
        p.write_text(json.dumps(_active_state(sid)), encoding="utf-8")
        return real(session_id)

    monkeypatch.setattr(wg_core, "read_state_status", flaky)
    out = wg_core._ensure_state(sid, {"session_id": sid, "cwd": "C:/x"}, {})
    assert out and out["turn_seq"] == 15


def test_cleanup_keeps_active_working_state_under_6h(tmp_path, monkeypatch):
    monkeypatch.setattr(_shared, "WORKFLOW_DIR", tmp_path)
    p = tmp_path / "state-active.json"
    p.write_text(json.dumps(_active_state("active")), encoding="utf-8")
    old = time.time() - 2 * 3600  # 2 小時沒動：以前（30 分鐘）會被刪
    os.utime(p, (old, old))
    _shared._cleanup_old_states()
    assert p.exists()
    older = time.time() - 7 * 3600  # 超過 6 小時才視為孤兒
    os.utime(p, (older, older))
    _shared._cleanup_old_states()
    assert not p.exists()
