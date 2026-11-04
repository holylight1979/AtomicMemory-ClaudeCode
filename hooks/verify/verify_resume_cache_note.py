"""verify_resume_cache_note.py — 重開舊 session 告知要重寫多少快取（規則 RESUME_CACHE_REWRITE_NOTE）。

資料是官方 SessionStart(resume／fork) 輸入的 context_tokens、prompt_cache_likely_expired、seconds_since_last_response
（Docs/06-reference/hooks.md「SessionStart 輸入」）。守住：
1. 快取多半失效、重送量到門檻 → 一行（不超過 100 字），含閒置時間與「約 N 萬 token」。
2. 快取還在、量不到門檻、欄位沒給（舊版、逐字稿還沒有回應）、不是 resume／fork → 不送。
3. 端到端：handle_session_start(source=resume) 輸出 systemMessage（給使用者）＝這一行，additionalContext 也有；
   沒有欄位時輸出沒有 systemMessage。

怎麼跑：python -X utf8 hooks/verify/verify_resume_cache_note.py（尾行 RESUME_CACHE_NOTE_CHECK PASS／FAIL）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE / "lib"))

from handlers import session_start as ss  # noqa: E402

EXPIRED = {"seconds_since_last_response": 5400, "context_tokens": 182340,
           "prompt_cache_likely_expired": True, "estimated_cache_write_usd": 1.1396}   # 官方文件的範例輸入


# ─── 不變式 1、2：判斷與文字 ─────────────────────────────────────────────────


def test_expired_large_context_gives_one_short_line():
    line = ss._resume_cache_note(EXPIRED, "resume")
    assert line.startswith("[Guardian:ResumeCache] ")
    assert "1.5 小時" in line and "約 18 萬 token" in line
    assert len(line) <= 100 and "\n" not in line
    assert ss._resume_cache_note(EXPIRED, "fork") == line, "fork 也拿得到同樣欄位，照樣提"


def test_minutes_and_unknown_idle():
    assert "約 45 分鐘" in ss._resume_cache_note({**EXPIRED, "seconds_since_last_response": 2700}, "resume")
    no_idle = ss._resume_cache_note({**EXPIRED, "seconds_since_last_response": None}, "resume")
    assert no_idle and "距上次回應" not in no_idle


def test_no_note_when_warm_small_missing_or_other_source():
    assert ss._resume_cache_note({**EXPIRED, "prompt_cache_likely_expired": False}, "resume") == ""
    assert ss._resume_cache_note({**EXPIRED, "context_tokens": 99_999}, "resume") == ""
    assert ss._resume_cache_note({}, "resume") == "", "欄位沒給＝估不出，不送"
    assert ss._resume_cache_note({**EXPIRED, "context_tokens": "abc"}, "resume") == ""
    for src in ("startup", "compact", "clear"):
        assert ss._resume_cache_note(EXPIRED, src) == ""


# ─── 不變式 3：端到端 ────────────────────────────────────────────────────────


def _run_session_start_resume(tmp_path, monkeypatch, capsys, extra):
    """跑 handle_session_start(source=resume) 沿用舊 state 那條路；碰真實環境的段落全換成不做事
    （同 verify_post_compact_reinjection_phase4._run_session_start_compact）。回解析後的輸出 JSON。"""
    import wg_core
    env = tmp_path / "env"
    holder = {"state": {"session": {"id": "test-sid", "cwd": str(tmp_path)}, "phase": "working",
                        "modified_files": [], "knowledge_queue": [], "injected_atoms": []}}
    monkeypatch.setenv("WG_CODING_GUARD", "0")
    monkeypatch.setattr(wg_core, "rotate_log_if_oversized", lambda *a, **k: None)
    monkeypatch.setattr(ss, "resolve_project_root", None)        # 不算專案根指紋 → 走沿用舊 state 那條
    monkeypatch.setattr(ss, "_find_active_sibling_state", lambda *a, **k: None)
    monkeypatch.setattr(ss, "read_state", lambda sid: holder["state"])
    monkeypatch.setattr(ss, "write_state", lambda sid, st: holder.__setitem__("state", st))
    for name in ("MEMORY_DIR", "WORKFLOW_DIR", "CLAUDE_DIR"):
        monkeypatch.setattr(ss, name, env)
    monkeypatch.setattr(ss, "REALM_AUTOMOVE_MARKER", env / "realm-automove.json")
    monkeypatch.setattr(ss, "WISDOM_AVAILABLE", False)
    stubs = (("_check_se_sentinel_residual", None), ("_check_periodic_review_due", None),
             ("_load_oscillation_warnings", None), ("check_long_die_status", None), ("_check_mcp_servers", []),
             ("check_always_load_contracts", []), ("_cleanup_old_states", None), ("_refresh_vector_flag", None))
    for name, value in stubs:
        monkeypatch.setattr(ss, name, lambda *a, _v=value, **k: _v)
    capsys.readouterr()
    with pytest.raises(SystemExit):
        ss.handle_session_start({"session_id": "test-sid", "cwd": str(tmp_path), "source": "resume", **extra},
                                {"vector_search": {"auto_start_service": False}})
    return json.loads(capsys.readouterr().out.strip())


def test_session_start_resume_shows_note_to_user_and_claude(tmp_path, monkeypatch, capsys):
    out = _run_session_start_resume(tmp_path, monkeypatch, capsys, EXPIRED)
    line = ss._resume_cache_note(EXPIRED, "resume")
    assert out.get("systemMessage") == line, "給使用者的 systemMessage 要是這一行"
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "Session resumed (resume)" in ctx and line in ctx


def test_session_start_resume_without_fields_no_system_message(tmp_path, monkeypatch, capsys):
    out = _run_session_start_resume(tmp_path, monkeypatch, capsys, {})
    assert "systemMessage" not in out
    assert "[Guardian:ResumeCache]" not in out["hookSpecificOutput"]["additionalContext"]


if __name__ == "__main__":
    import subprocess   # 新行程跑 pytest：本檔頂端已載入的模組不帶進測試（conftest 的資料根隔離才完整）
    code = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("RESUME_CACHE_NOTE_CHECK " + ("PASS" if code == 0 else "FAIL"))
    sys.exit(0 if code == 0 else 1)
