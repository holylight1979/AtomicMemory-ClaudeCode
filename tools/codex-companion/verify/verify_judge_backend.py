"""verify_judge_backend.py — 裁判後端解析／備援切換單元測試。

涵蓋：
  1. resolve_codex_bin：config 絕對路徑存在→用它；不存在→退 PATH（不再靜默關閉）
  2. is_entitlement_failure：授權/額度類 stderr 命中；一般逾時不命中
  3. select_backend：codex 可用→codex；codex 缺→claude 備援；抑制中→備援；
     抑制過期→重探 codex；備援關閉且無 codex→NONE
  4. 抑制標記讀寫與 TTL
  5. run_claude_judge 組裝：唯讀工具限制 + JUDGE_ENV 子 session 標記 + stdin 傳材料
  6. _judge_may_block：備援預設無 block 權，allow_block=true 才有

不實際呼叫 codex / claude；subprocess.run 以 monkeypatch 攔截。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

CLAUDE_DIR = Path.home() / ".claude"
COMPANION_DIR = CLAUDE_DIR / "tools" / "codex-companion"
sys.path.insert(0, str(COMPANION_DIR))
sys.path.insert(0, str(CLAUDE_DIR / "hooks"))

import judge_backend as jb  # noqa: E402


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """把抑制標記檔導到 tmp，避免污染真實 workflow/companion-backend.json。"""
    monkeypatch.setattr(jb, "STATE_PATH", tmp_path / "companion-backend.json")
    return tmp_path


# ─── 1. codex binary 解析 ────────────────────────────────────────────────────


def test_resolve_codex_prefers_existing_absolute_path(tmp_path):
    fake = tmp_path / "codex.cmd"
    fake.write_text("", encoding="utf-8")
    assert jb.resolve_codex_bin({"codex_binary": str(fake)}) == str(fake)


def test_resolve_codex_falls_back_to_path_when_absolute_missing(monkeypatch):
    """別台機器沒有這個絕對路徑 → 退 PATH 找 codex，不得回 None。"""
    monkeypatch.setattr(jb.shutil, "which",
                        lambda name: "/usr/bin/codex" if name == "codex" else None)
    got = jb.resolve_codex_bin({"codex_binary": "C:/somebody-else/npm/codex.cmd"})
    assert got == "/usr/bin/codex"


def test_resolve_codex_none_when_nowhere(monkeypatch):
    monkeypatch.setattr(jb.shutil, "which", lambda name: None)
    assert jb.resolve_codex_bin({"codex_binary": "C:/nope/codex.cmd"}) is None


# ─── 2. 授權失敗辨識 ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("stderr", [
    "Error: Not logged in. Please run codex login",
    "request failed with status 401 Unauthorized",
    "HTTP 429 rate limit exceeded",
    "usage limit reached for your plan",
    "no active subscription found",
])
def test_entitlement_failures_detected(stderr):
    assert jb.is_entitlement_failure(stderr) is True


@pytest.mark.parametrize("stderr", [
    "[assessor] timeout after 60s",
    "CreateProcessWithLogon failed",
    "",
])
def test_non_entitlement_failures_not_detected(stderr):
    assert jb.is_entitlement_failure(stderr) is False


# ─── 3~4. 後端選擇與抑制 TTL ─────────────────────────────────────────────────


def _cfg(**fallback):
    base = {"enabled": True, "model": "sonnet"}
    base.update(fallback)
    return {"codex_binary": "codex", "fallback": base}


def test_select_prefers_codex(monkeypatch, isolated_state):
    monkeypatch.setattr(jb, "resolve_codex_bin", lambda c: "/bin/codex")
    monkeypatch.setattr(jb, "resolve_claude_bin", lambda c: "/bin/claude")
    assert jb.select_backend(_cfg()) == (jb.BACKEND_CODEX, "/bin/codex")


def test_select_falls_back_to_claude_when_no_codex(monkeypatch, isolated_state):
    monkeypatch.setattr(jb, "resolve_codex_bin", lambda c: None)
    monkeypatch.setattr(jb, "resolve_claude_bin", lambda c: "/bin/claude")
    assert jb.select_backend(_cfg()) == (jb.BACKEND_CLAUDE, "/bin/claude")


def test_select_falls_back_while_codex_suppressed(monkeypatch, isolated_state):
    monkeypatch.setattr(jb, "resolve_codex_bin", lambda c: "/bin/codex")
    monkeypatch.setattr(jb, "resolve_claude_bin", lambda c: "/bin/claude")
    jb.mark_codex_unavailable("401 unauthorized")
    assert jb.select_backend(_cfg()) == (jb.BACKEND_CLAUDE, "/bin/claude")


def test_suppression_expires_and_reprobes_codex(monkeypatch, isolated_state):
    monkeypatch.setattr(jb, "resolve_codex_bin", lambda c: "/bin/codex")
    monkeypatch.setattr(jb, "resolve_claude_bin", lambda c: "/bin/claude")
    jb.mark_codex_unavailable("401")
    stale = jb.read_backend_state()
    stale["codex_unavailable"]["ts"] = time.time() - 25 * 3600
    jb._write_backend_state(stale)
    assert jb.select_backend(_cfg(reprobe_hours=24))[0] == jb.BACKEND_CODEX


def test_codex_success_clears_suppression(isolated_state):
    jb.mark_codex_unavailable("401")
    assert jb.codex_suppressed(_cfg()) is not None
    jb.clear_codex_unavailable()
    assert jb.codex_suppressed(_cfg()) is None


def test_select_none_when_fallback_disabled_and_no_codex(monkeypatch, isolated_state):
    monkeypatch.setattr(jb, "resolve_codex_bin", lambda c: None)
    monkeypatch.setattr(jb, "resolve_claude_bin", lambda c: "/bin/claude")
    assert jb.select_backend(_cfg(enabled=False)) == (jb.BACKEND_NONE, "")


def test_describe_unavailable_mentions_reason(isolated_state):
    text = jb.describe_unavailable({"codex_binary": "C:/nope/codex.cmd",
                                    "fallback": {"enabled": True}})
    assert "codex" in text and "claude" in text


# ─── 5. claude 備援執行組裝 ──────────────────────────────────────────────────


class _FakeCompleted:
    returncode = 0
    stdout = '{"verdict":"pass","summary":"ok"}'
    stderr = ""


def test_run_claude_judge_command_and_env(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env", {})
        captured["stdin_text"] = kwargs["stdin"].read()
        return _FakeCompleted()

    monkeypatch.setattr(jb.subprocess, "run", fake_run)
    out, err = jb.run_claude_judge(
        "案卷材料 XYZ", str(tmp_path), _cfg(model="sonnet"), "/bin/claude")

    assert out.startswith("{") and err == ""
    cmd = captured["cmd"]
    assert cmd[0] == "/bin/claude" and "-p" in cmd
    assert cmd[cmd.index("--model") + 1] == "sonnet"
    # 裁判不得改動受審對象
    disallowed = cmd[cmd.index("--disallowed-tools") + 1]
    for tool in ("Bash", "Write", "Edit"):
        assert tool in disallowed
    # 子 session 標記必須存在（hooks 端據此早退，防遞迴）
    assert captured["env"].get(jb.JUDGE_ENV) == "1"
    # 材料走 stdin，不塞 argv
    assert "案卷材料 XYZ" in captured["stdin_text"]
    assert not any("案卷材料" in str(a) for a in cmd)


def test_run_claude_judge_timeout_returns_reason(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        raise jb.subprocess.TimeoutExpired(cmd, 90)

    monkeypatch.setattr(jb.subprocess, "run", fake_run)
    out, err = jb.run_claude_judge("x", str(tmp_path), _cfg(), "/bin/claude")
    assert out == "" and "timeout" in err


# ─── 5b. assessor._run_judge 切換路徑 ───────────────────────────────────────


def test_run_judge_switches_to_fallback_on_entitlement_failure(monkeypatch, isolated_state):
    """codex 因未登入失敗 → 落抑制標記 + **當輪**改用 claude 出判定。"""
    import assessor

    monkeypatch.setattr(jb, "resolve_codex_bin", lambda c: "/bin/codex")
    monkeypatch.setattr(jb, "resolve_claude_bin", lambda c: "/bin/claude")
    monkeypatch.setattr(
        assessor, "_run_codex_with_retry",
        lambda p, cwd, cfg: ("", "Error: Not logged in. Please run codex login", 2))
    monkeypatch.setattr(
        jb, "run_claude_judge",
        lambda p, cwd, cfg, b, timeout=None: ('{"verdict":"pass"}', ""))

    raw, stderr, attempts, backend = assessor._run_judge("材料", "", _cfg())
    assert backend == jb.BACKEND_CLAUDE
    assert '"verdict":"pass"' in raw
    assert jb.codex_suppressed(_cfg()) is not None  # 下次直接走備援，不再燒兩次逾時


def test_run_judge_keeps_codex_and_clears_suppression_on_success(monkeypatch, isolated_state):
    import assessor

    monkeypatch.setattr(jb, "resolve_codex_bin", lambda c: "/bin/codex")
    monkeypatch.setattr(jb, "resolve_claude_bin", lambda c: "/bin/claude")
    monkeypatch.setattr(
        assessor, "_run_codex_with_retry",
        lambda p, cwd, cfg: ('{"status":"ok","summary":"fine"}', "", 1))
    # 抑制標記已過 reprobe_hours → 本輪重探 codex（抑制期內不重探是設計）
    jb.mark_codex_unavailable("stale 401")
    stale = jb.read_backend_state()
    stale["codex_unavailable"]["ts"] = time.time() - 25 * 3600
    jb._write_backend_state(stale)

    raw, stderr, attempts, backend = assessor._run_judge("材料", "", _cfg())
    assert backend == jb.BACKEND_CODEX
    assert jb.codex_suppressed(_cfg()) is None  # codex 復活 → 抑制標記清掉


def test_run_judge_does_not_fallback_on_plain_timeout(monkeypatch, isolated_state):
    """一般逾時不是授權問題 → 維持既有 codex 失敗語意，不亂切備援也不抑制。"""
    import assessor

    monkeypatch.setattr(jb, "resolve_codex_bin", lambda c: "/bin/codex")
    monkeypatch.setattr(jb, "resolve_claude_bin", lambda c: "/bin/claude")
    monkeypatch.setattr(
        assessor, "_run_codex_with_retry",
        lambda p, cwd, cfg: ("", "[assessor] timeout after 60s", 2))

    raw, stderr, attempts, backend = assessor._run_judge("材料", "", _cfg())
    assert backend == jb.BACKEND_CODEX and raw == ""
    assert jb.codex_suppressed(_cfg()) is None


# ─── 6. block 權 ────────────────────────────────────────────────────────────


def test_fallback_has_no_block_power_by_default():
    import codex_companion as cc
    result = {"_judge_backend": jb.BACKEND_CLAUDE}
    assert cc._judge_may_block(result, _cfg()) is False


def test_fallback_can_block_when_explicitly_allowed():
    import codex_companion as cc
    result = {"_judge_backend": jb.BACKEND_CLAUDE}
    assert cc._judge_may_block(result, _cfg(allow_block=True)) is True


def test_codex_always_has_block_power():
    import codex_companion as cc
    result = {"_judge_backend": jb.BACKEND_CODEX}
    assert cc._judge_may_block(result, _cfg()) is True


# ─── 7. 無後端揭露（可觀測性鐵律：不得無聲降級） ─────────────────────────────


def test_no_judge_disclosed_once_only(isolated_state, capsys):
    import codex_companion as cc
    cfg = {"codex_binary": "C:/nope/codex.cmd", "fallback": {"enabled": True}}

    with pytest.raises(SystemExit):  # _output_context 以 exit(0) 收尾
        cc._disclose_no_judge_once(cfg, jb)
    first = capsys.readouterr().out
    assert "Codex Companion" in first and "heuristics" in first

    cc._disclose_no_judge_once(cfg, jb)  # 第二次靜默：不 exit、不輸出
    assert capsys.readouterr().out == ""
