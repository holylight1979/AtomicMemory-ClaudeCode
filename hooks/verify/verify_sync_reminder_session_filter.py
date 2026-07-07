"""verify_sync_reminder_session_filter.py — SyncReminder + 底部 block 的 per-session 過濾。

驗證 handlers/stop.py 的「同步提醒」閘與底部一般 block 只認「本 session 自己
Edit/Write 的檔」（own_mod_files）：共用工作樹 / merged state 下，state.modified_files
可能混入他 session 改的檔（session_id 不符）；此時本協調 session（無自身改動）不得
被他 session 未提交的檔誤觸發同步提醒 / 一般 block。

  SyncReminder：
  - 只有 own uncommitted → 觸發，列 own 路徑
  - 只有 foreign（session_id≠本）→ own 空 → 不觸發
  - 混合 → 只列 own 路徑、不列 foreign
  底部 block（_detect_uncommitted_files→[] 使 SyncReminder 不觸發後兜底）：
  - foreign-only → own 空 → mod_count 0 → 早退、不觸發
  - own ≥ min_files → 觸發

對應修補：handlers/stop.py SyncReminder 閘（own_mod_files 過濾）
        + 底部 block（mod_count / unique_files 由 own_mod_files 推導）。
配套：post_tool_use.py 為 modified_files 標 session_id（見 verify_scan_report_session_filter）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from handlers import stop as st  # noqa: E402

_SID = "sid"
# 正斜線路徑：程式視為不透明字串，且避免 JSON 輸出跳脫反斜線干擾子字串斷言。
_CORE = "c:/a/.claude/hooks/x.py"
_CORE2 = "c:/a/.claude/lib/y.py"
_DOC = "c:/a/.claude/_AIDocs/note.md"


@pytest.fixture
def driven(monkeypatch):
    """驅動 handle_stop 至 SyncReminder / 底部 block；回 drive(modified_files, capsys) → stdout。

    預設繞過前置閘：Scan-Report 靠 scan_report_warned=True 跳過、DPM monkeypatch 關掉，
    使控制流抵達 SyncReminder 與底部 block。_detect_uncommitted_files 由 drive 的
    uncommitted 參數決定：'echo'（回顯 own 路徑，測 SyncReminder）/ 'none'（回 []，讓
    SyncReminder 不觸發、測底部 block）。"""
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: "全部完成了")
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_should_deep_postmortem", lambda *a, **k: False)
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)

    def drive(modified_files, capsys, uncommitted="echo", **extra):
        if uncommitted == "echo":
            monkeypatch.setattr(
                st, "_detect_uncommitted_files",
                lambda mf: [m["path"] for m in mf],
            )
        else:
            monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [])
        state = {
            "phase": "working",
            "modified_files": modified_files,
            "failing_tests": [],
            "recent_user_prompts": [],
            "stop_blocked_count": 0,
            "scan_report_warned": True,  # 跳過 Scan-Report 閘 → 控制流抵達 SyncReminder
        }
        state.update(extra)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, {})
        return capsys.readouterr().out

    return drive


def _mf(path, session_id=_SID):
    d = {"path": path, "tool": "Edit"}
    if session_id is not None:
        d["session_id"] = session_id
    return d


# ─── SyncReminder 閘 session-filter ─────────────────────────────────

def test_sync_own_uncommitted_triggers(driven, capsys):
    """只有 own uncommitted → 觸發同步提醒，列 own 路徑。"""
    out = driven([_mf(_CORE, session_id=_SID)], capsys)
    assert "[Guardian:SyncReminder]" in out
    assert _CORE in out


def test_sync_foreign_only_not_triggered(driven, capsys):
    """只有他 session 改的檔（session_id≠本）→ own 空 → 不觸發同步提醒。"""
    out = driven([_mf(_CORE, session_id="other")], capsys)
    assert "[Guardian:SyncReminder]" not in out


def test_sync_mixed_lists_own_only(driven, capsys):
    """混合：本 session 改 doc + 他 session 改 core → 只列 own(doc)、不列 foreign(core)。"""
    out = driven(
        [_mf(_DOC, session_id=_SID), _mf(_CORE, session_id="other")],
        capsys,
    )
    assert "[Guardian:SyncReminder]" in out
    assert _DOC in out
    assert _CORE not in out


def test_sync_legacy_no_session_id_fail_open(driven, capsys):
    """無 session_id 的 legacy entry → 保守視為本 session（fail-open）→ 觸發。"""
    out = driven([_mf(_CORE, session_id=None)], capsys)
    assert "[Guardian:SyncReminder]" in out


# ─── 底部一般 block session-filter（_detect_uncommitted_files→[] 兜底）───

def test_block_foreign_only_not_triggered(driven, capsys):
    """foreign-only：own 空 → mod_count 0 → 早退、不觸發 [Workflow Guardian]。"""
    out = driven(
        [_mf(_CORE, session_id="other"), _mf(_CORE2, session_id="other")],
        capsys, uncommitted="none",
    )
    assert "[Workflow Guardian]" not in out


def test_block_own_meets_threshold_triggers(driven, capsys):
    """own ≥ min_files(2) → 觸發 [Workflow Guardian] 一般 block。"""
    out = driven(
        [_mf(_CORE, session_id=_SID), _mf(_CORE2, session_id=_SID)],
        capsys, uncommitted="none",
    )
    assert "[Workflow Guardian]" in out
