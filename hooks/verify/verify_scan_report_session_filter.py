"""verify_scan_report_session_filter.py — ScanReport 閘 per-session 過濾。

驗證 handlers/stop.py 的 Scan-Report Gate 只認「本 session 自己 Edit/Write 的檔」：
  共用工作樹 / merged state 下，state.modified_files 可能混入他 session 改的 core 檔
  （session_id 不符）；此時本協調 session（只改 docs）的收尾檢核不得被誤觸發。

  - 他 session 改 core 檔（session_id≠本）→ own 為空 → 不觸發
  - 本 session 改 core 檔（session_id==本）→ 觸發
  - legacy entry（無 session_id）→ 保守視為本 session（fail-open）→ 觸發
  - 混合：本 session 單一 docs + 他 session core → own 僅單一非 core → 不觸發
    （正是「只改 docs 的協調 session vs 隔壁 session 改 server.js」實例）

對應修補：handlers/post_tool_use.py（modified_files 標 session_id）
        + handlers/stop.py Scan-Report Gate（own_mod_files 過濾）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from handlers import stop as st  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
from handlers.post_tool_use import _VCS_COMMIT_RE  # noqa: E402

_SID = "sid"
_CORE = r"c:\a\.claude\hooks\x.py"
_DOC = r"c:\a\.claude\_AIDocs\note.md"
_DONE = "全部完成了"  # claims_completion=True, has_scan_report=False


@pytest.fixture
def driven(monkeypatch):
    """驅動 handle_stop，只保留 gate 控制流；回 drive(modified_files) → stdout。

    last_text 固定為完成宣告（滿足 ScanReport 前置），modified_files 由測試給，
    其餘外部依賴全攔掉。session_id 固定 _SID。"""
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
    d = {"path": path, "tool": "Edit"}
    if session_id is not None:
        d["session_id"] = session_id
    return d


def test_foreign_core_not_triggered(driven, capsys):
    """他 session 改的 core 檔（session_id≠本）→ own 為空 → 不觸發收尾檢核。"""
    out = driven([_mf(_CORE, session_id="other")], capsys)
    assert "ScanReport" not in out


def test_own_core_triggered(driven, capsys):
    """本 session 改的 core 檔 → 觸發。"""
    out = driven([_mf(_CORE, session_id=_SID)], capsys)
    assert "[Guardian:ScanReport]" in out


def test_legacy_no_session_id_fail_open(driven, capsys):
    """無 session_id 的 legacy entry → 保守視為本 session（fail-open）→ 觸發。"""
    out = driven([_mf(_CORE, session_id=None)], capsys)
    assert "[Guardian:ScanReport]" in out


def test_coordinator_docs_only_not_triggered(driven, capsys):
    """實例：本協調 session 只改單一 docs（非 core），他 session 改 core server.js。
    own 僅單一非 core → 低於門檻且未觸 core → 不觸發。"""
    out = driven(
        [_mf(_DOC, session_id=_SID), _mf(_CORE, session_id="other")],
        capsys,
    )
    assert "ScanReport" not in out


# ─── 純 VCS commit turn 豁免收尾檢核 ─────────────────────────────────

def test_commit_this_turn_exempts(driven, capsys):
    """本 turn 有 commit（last_commit_turn_seq==turn_seq）→ 豁免，即使動 core 亦不觸發。"""
    out = driven([_mf(_CORE, session_id=_SID)], capsys,
                 turn_seq=5, last_commit_turn_seq=5)
    assert "ScanReport" not in out


def test_commit_prior_turn_not_exempt(driven, capsys):
    """commit 發生在別 turn（≠本 turn）→ 不豁免，照觸發（不因歷史 commit 永久放行）。"""
    out = driven([_mf(_CORE, session_id=_SID)], capsys,
                 turn_seq=5, last_commit_turn_seq=4)
    assert "[Guardian:ScanReport]" in out


def test_no_commit_flag_not_exempt(driven, capsys):
    """本 turn 未 commit（無 last_commit_turn_seq）→ 不豁免，照觸發。"""
    out = driven([_mf(_CORE, session_id=_SID)], capsys, turn_seq=5)
    assert "[Guardian:ScanReport]" in out


# ─── _VCS_COMMIT_RE：commit 指令偵測 ─────────────────────────────────

@pytest.mark.parametrize("cmd, matches", [
    ('git commit -m "x"', True),
    ('git -C "C:/p" commit -m "x"', True),
    ('svn commit -m "x"', True),
    ('git add . && git commit -m "x"', True),   # 串接第二段命中
    ('git log --oneline | grep commit', False),  # commit 在管線後、非 git 子命令
    ('git push', False),
    ('git status', False),
    ('git show HEAD', False),
])
def test_vcs_commit_regex(cmd, matches):
    assert bool(_VCS_COMMIT_RE.search(cmd)) is matches


# ─── 端到端：post_tool_use 對 git commit 記 last_commit_turn_seq ───────

def _drive_ptu(monkeypatch, command):
    state = {"turn_seq": 7}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "read_hot_cache", None)
    inp = {
        "session_id": _SID,
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {},
    }
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}})
    return state


def test_ptu_git_commit_sets_flag(monkeypatch):
    """跑 git commit → last_commit_turn_seq = 當前 turn_seq。"""
    state = _drive_ptu(monkeypatch, 'git commit -m "fix: x"')
    assert state.get("last_commit_turn_seq") == 7


def test_ptu_non_commit_no_flag(monkeypatch):
    """非 commit 指令（git status）→ 不設旗標。"""
    state = _drive_ptu(monkeypatch, "git status")
    assert "last_commit_turn_seq" not in state
