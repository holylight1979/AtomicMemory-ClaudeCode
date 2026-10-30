"""verify_codex_call.py：tools/codex-call.py（叫 Codex 的單一入口）與驗收裁判改走它之後的等值。

做什麼：
  1. 等值：驗收裁判 assessor._run_codex 改走 codex-call 之後，同一份設定組出的 codex 指令、旗標、逾時、環境、工作目錄、stdin 內容、
     log、暫存檔清理與回傳值，跟 55c748cc 的舊 assessor 相同。預期值＝`git show 55c748cc:tools/codex-companion/assessor.py`
     載成模組實跑；實際值＝本樹的 assessor 實跑；兩邊都只把 subprocess.run 換成同一個記錄器。
     設定（預設、帶 extra args、指定執行檔、模型名）× 子行程結果（-o 有答案、只有 stdout、exit 非 0、逾時、找不到執行檔、例外）全組合。
  2. 失敗路徑：執行檔不在 → exit 1、stderr 印原因、stdout 沒有答案；exit 非 0／沒回答／模型名不對 → 不報成功。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider tools/verify/verify_codex_call.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parents[2]
COMPANION_DIR = TREE / "tools" / "codex-companion"
CODEX_CALL = TREE / "tools" / "codex-call.py"
OLD_REV = "55c748cc"
if str(COMPANION_DIR) not in sys.path:
    sys.path.insert(0, str(COMPANION_DIR))

import assessor  # noqa: E402

codex_call = assessor.codex_call
_REAL_RUN = subprocess.run


def _old_assessor() -> types.ModuleType:
    """55c748cc 的 assessor.py 原文載成模組（__file__ 指本樹同一路徑，它 import 的 artifact_io／judge_backend／prompts 同一份）。"""
    r = _REAL_RUN(["git", "-C", str(TREE), "show", f"{OLD_REV}:tools/codex-companion/assessor.py"],
                  capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        pytest.skip(f"取不到 {OLD_REV} 的舊 assessor（淺 clone？）：{r.stderr.strip()[:200]}")
    mod = types.ModuleType("assessor_old")
    mod.__file__ = str(COMPANION_DIR / "assessor.py")
    exec(compile(r.stdout, f"assessor@{OLD_REV}", "exec"), mod.__dict__)
    return mod


OLD = None


@pytest.fixture(scope="module")
def old_mod():
    global OLD
    if OLD is None:
        OLD = _old_assessor()
    return OLD


class _Recorder:
    """假的 subprocess.run：記下引數與 stdin 內容，照 outcome 回結果或丟例外；-o 檔照 outcome 寫。"""

    def __init__(self, outcome: str, prompt: str):
        self.outcome, self.prompt, self.calls = outcome, prompt, []

    def __call__(self, cmd, **kw):
        stdin = kw.pop("stdin")
        out_path = cmd[cmd.index("-o") + 1]
        self.calls.append({"cmd": [("<OUT>" if c == out_path else c) for c in cmd], "kw": kw,
                           "stdin": stdin.read(), "out_is_prompt_plus_out": out_path == stdin.name + ".out",
                           "temp": (stdin.name, out_path)})
        o = self.outcome
        if o == "timeout":
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        if o == "notfound":
            raise FileNotFoundError(cmd[0])
        if o == "oserror":
            raise OSError("spawn 壞了")
        if o == "o_file":
            Path(out_path).write_text("  {\"score\": 9}\n", encoding="utf-8")
        if o == "o_blank":
            Path(out_path).write_text("   \n", encoding="utf-8")
        rc = 1 if o == "exit1" else 0
        stderr = "codex\nuser\n" + self.prompt.strip() + "\nERROR: quota exceeded\n" if o == "exit1" else "tokens used\n12\n"
        return subprocess.CompletedProcess(cmd, rc, stdout="  stdout 回答  \n", stderr=stderr)


CONFIGS = {
    "empty": {},
    "default": {"model": "gpt-6-astra", "assessment_timeout": 120, "codex_extra_args": []},
    "extra_args": {"assessment_timeout": 7, "codex_extra_args": ["-c", "mcp_servers.x.enabled=false", 3]},
    "explicit_bin": "EXPLICIT",                     # 換成 tmp 裡真的存在的檔
    "missing_bin": {"codex_binary": "C:/nope-codex-call/codex.cmd", "model": "gpt-5.6-sol"},
    "model_blank": {"model": "", "assessment_timeout": 30.5},
}
OUTCOMES = ["o_file", "stdout_only", "o_blank", "exit1", "timeout", "notfound", "oserror"]


def _run(mod, fn_owner, monkeypatch, config, outcome, prompt, cwd):
    rec, logs = _Recorder(outcome, prompt), []
    monkeypatch.setattr(subprocess, "run", rec)
    monkeypatch.setattr(fn_owner, "_log", logs.append)
    ret = mod._run_codex(prompt, cwd, config)
    monkeypatch.setattr(subprocess, "run", _REAL_RUN)
    leftover = [p for c in rec.calls for p in c.pop("temp") if os.path.exists(p)]
    return {"ret": ret, "calls": rec.calls, "logs": logs, "leftover": leftover}


@pytest.mark.parametrize("cfg_name", list(CONFIGS))
@pytest.mark.parametrize("outcome", OUTCOMES)
@pytest.mark.parametrize("cwd_kind", ["dir", "blank", "missing"])
def test_assessor_codex_call_matches_55c748cc(old_mod, monkeypatch, tmp_path, cfg_name, outcome, cwd_kind):
    cfg = CONFIGS[cfg_name]
    if cfg == "EXPLICIT":
        fake = tmp_path / "codex-explicit.cmd"
        fake.write_text("@echo off\n", encoding="utf-8")
        cfg = {"codex_binary": str(fake), "model": "gpt-6-astra"}
    cwd = {"dir": str(tmp_path), "blank": "", "missing": str(tmp_path / "nope")}[cwd_kind]
    prompt = "工具軌跡：#3 [FAILED] → CreateProcessWithLogonW failed: 1385\n請判斷完成度\n"
    expected = _run(old_mod, old_mod, monkeypatch, dict(cfg), outcome, prompt, cwd)
    actual = _run(assessor, assessor, monkeypatch, dict(cfg), outcome, prompt, cwd)
    assert len(expected["calls"]) == 1, "前置：舊碼真的組了一次 codex 指令"
    assert expected["calls"][0]["out_is_prompt_plus_out"] and expected["calls"][0]["stdin"] == prompt, "前置：舊碼 stdin 是提示詞檔"
    assert actual == expected


def test_assessor_empty_prompt_matches_55c748cc(old_mod, monkeypatch):
    """邊界：空提示詞不剝回聲（strip 後是空字串，replace 不能把整段 stderr 的空字串位置換掉）。"""
    for outcome in ("exit1", "stdout_only"):
        expected = _run(old_mod, old_mod, monkeypatch, {}, outcome, "", "")
        actual = _run(assessor, assessor, monkeypatch, {}, outcome, "", "")
        assert actual == expected


# ─── 失敗路徑：沒跑成就不報成功 ─────────────────────────────────────────


def test_cli_missing_binary_exits_nonzero_with_reason(tmp_path):
    root = tmp_path / "data"
    (root / "workflow").mkdir(parents=True)
    missing = tmp_path / "no-such-dir" / "codex.cmd"
    (root / "workflow" / "config.json").write_text(
        json.dumps({"codex_companion": {"codex_binary": str(missing)}}), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k.upper() not in ("PATH", "WG_CLAUDE_DIR")}
    env.update(WG_CLAUDE_DIR=str(root), PATH=str(tmp_path / "empty-path"))   # PATH 上也沒有 codex
    r = _REAL_RUN([sys.executable, "-X", "utf8", str(CODEX_CALL), "--prompt", "回一個字"], capture_output=True,
                  text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert "失敗" in r.stderr and "codex binary not found" in r.stderr and str(missing) in r.stderr, r.stderr
    assert r.stdout.strip() == "", r.stdout


def _fake_run(rc, stdout="", out_text=None):
    def run(cmd, **kw):
        if out_text is not None:
            Path(cmd[cmd.index("-o") + 1]).write_text(out_text, encoding="utf-8")
        return subprocess.CompletedProcess(cmd, rc, stdout=stdout, stderr="err\n")
    return run


def test_nonzero_exit_is_not_success_even_with_text(monkeypatch):
    monkeypatch.setattr(codex_call.judge_backend, "resolve_codex_bin", lambda c: "codex-stub")
    monkeypatch.setattr(subprocess, "run", _fake_run(2, stdout="半個答案"))
    res = codex_call.run_codex("問", validate_model=False, log=lambda m: None)
    assert (res.ok, res.returncode, res.text) == (False, 2, "半個答案") and "exit=2" in res.reason


def test_zero_exit_without_answer_is_not_success(monkeypatch):
    monkeypatch.setattr(codex_call.judge_backend, "resolve_codex_bin", lambda c: "codex-stub")
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout="  ", out_text=""))
    res = codex_call.run_codex("問", log=lambda m: None)
    assert not res.ok and res.returncode == 0 and "沒有回答" in res.reason


def test_unknown_model_never_spawns(monkeypatch, tmp_path):
    import lib.codex_models as cm
    cache = tmp_path / "models_cache.json"
    cache.write_text(json.dumps({"models": [{"slug": "gpt-6-astra"}]}), encoding="utf-8")
    monkeypatch.setattr(cm, "DEFAULT_CACHE_PATH", cache)

    def boom(*a, **k):
        raise AssertionError("模型名不對還叫了 codex")
    monkeypatch.setattr(subprocess, "run", boom)
    res = codex_call.run_codex("問", model="gpt-6-astra-900K", log=lambda m: None)
    assert not res.ok and res.returncode is None and "不在 models_cache" in res.reason


def test_cli_success_prints_answer_and_flags(monkeypatch, capsys, tmp_path):
    """成功路徑：答案印 stdout、exit 0；必帶 --ephemeral 與 --skip-git-repo-check；指定沙箱時 Windows 帶 unelevated。"""
    seen = {}
    monkeypatch.setattr(codex_call.judge_backend, "resolve_codex_bin", lambda c: "codex-stub")
    monkeypatch.setattr(codex_call, "load_config", lambda: {"codex_extra_args": ["--x"]})

    def run(cmd, **kw):
        seen["cmd"], seen["stdin"] = cmd, kw["stdin"].read()
        Path(cmd[cmd.index("-o") + 1]).write_text("答案\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", run)
    rc = codex_call.main(["--prompt", "問題", "--sandbox", "read-only", "--cwd", str(tmp_path)])
    assert rc == 0 and capsys.readouterr().out.strip() == "答案"
    cmd = seen["cmd"]
    assert cmd[:2] == ["codex-stub", "exec"] and "--ephemeral" in cmd and "--skip-git-repo-check" in cmd
    assert cmd[cmd.index("-s") + 1] == "read-only" and cmd[-1] == "--x" and seen["stdin"] == "問題"
    assert ('windows.sandbox="unelevated"' in cmd) == (sys.platform == "win32")
    assert codex_call.sandbox_args(None) == []
