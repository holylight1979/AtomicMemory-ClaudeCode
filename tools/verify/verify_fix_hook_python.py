"""verify_fix_hook_python.py — settings.json 直譯器路徑校正工具測試。

情境即「別台機器 git clone 後，settings.json 寫的是原作者的絕對路徑」：
  1. 掃得出所有帶指令的欄位（statusLine + 各 event 的 hooks）
  2. 改寫換掉開頭直譯器、指令其餘部分（-c "..." 全串）一字不動
  3. pythonw（不彈 console）維持 w 版，不會被換成會彈視窗的 python
  4. 已經正確就不動（本機不該被無謂改寫）
  5. 候選直譯器實跑驗證，不合格拒絕寫入
  6. 單獨執行時改的是 Claude Code 讀的那份 settings.json（CLAUDE_CONFIG_DIR，沒設就 ~/.claude），不是資料根那份
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]   # 本樹的 tools/（驗本樹的程式，不是家目錄裝的那份）
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# 檔名帶連字號無法 import，以 spec 載入
_spec = importlib.util.spec_from_file_location(
    "fix_hook_python", TOOLS_DIR / "fix-hook-python.py")
fhp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fhp)


FOREIGN = "C:/Users/someone-else/AppData/Local/Python/bin"


def _settings():
    return {
        "statusLine": {
            "type": "command",
            "command": f"{FOREIGN}/python.exe C:/Users/x/.claude/tools/statusline.py",
        },
        "hooks": {
            "SessionStart": [{"hooks": [
                {"type": "command",
                 "command": f'{FOREIGN}/pythonw.exe -c "import runpy;runpy.run_path(\'a.py\')"',
                 "timeout": 5},
                {"type": "command",
                 "command": f'{FOREIGN}/pythonw.exe -c "print(1)"'},
            ]}],
            "Stop": [{"hooks": [
                {"type": "command", "command": f'{FOREIGN}/pythonw.exe -c "pass"'},
            ]}],
        },
    }


def test_detects_every_command_slot():
    found = fhp.current_interpreters(_settings())
    descs = [d for d, _ in found]
    assert "statusLine" in descs
    assert "hooks.SessionStart[0][0]" in descs
    assert "hooks.Stop[0][0]" in descs
    assert len(found) == 4


def test_rewrite_replaces_only_the_interpreter(tmp_path):
    fake = tmp_path / "python.exe"
    fake.write_text("", encoding="utf-8")
    s = _settings()
    changes = fhp.rewrite(s, str(fake))

    assert len(changes) == 4
    # 指令主體（-c 的整串）必須原封不動
    cmd = s["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "runpy.run_path" in cmd and FOREIGN not in cmd
    # rewrite 一律寫成可攜形式（$LOCALAPPDATA/…）並加引號
    assert cmd.startswith(f'"{fhp.portable(str(fake))}"')
    # statusLine 的腳本參數也要保留
    assert "statusline.py" in s["statusLine"]["command"]


def test_pythonw_stays_windowless(tmp_path):
    """原本用 pythonw 的 hook 不得被換成會彈 console 的 python。"""
    (tmp_path / "python.exe").write_text("", encoding="utf-8")
    (tmp_path / "pythonw.exe").write_text("", encoding="utf-8")
    s = _settings()
    fhp.rewrite(s, str(tmp_path / "python.exe"))

    assert s["hooks"]["Stop"][0]["hooks"][0]["command"].startswith(
        f'"{fhp.portable(str(tmp_path / "pythonw.exe"))}"')
    # statusLine 原本就是 python（需要 stdout）→ 維持非 w 版
    assert s["statusLine"]["command"].startswith(
        f'"{fhp.portable(str(tmp_path / "python.exe"))}"')


def test_no_change_when_already_correct(tmp_path):
    fake = tmp_path / "pythonw.exe"
    fake.write_text("", encoding="utf-8")
    # 已是可攜形式（rewrite 的輸出格式）→ 不得再被改寫
    s = {"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": f'"{fhp.portable(str(fake))}" -c "pass"'}]}]}}
    assert fhp.rewrite(s, str(fake)) == []


def test_verify_interpreter_accepts_running_python():
    ok, info = fhp.verify_interpreter(sys.executable)
    assert ok and info


def test_verify_interpreter_rejects_missing_binary(tmp_path):
    ok, info = fhp.verify_interpreter(str(tmp_path / "nope.exe"))
    assert ok is False and info


def test_rewrite_quotes_paths_with_spaces(tmp_path):
    d = tmp_path / "Program Files"
    d.mkdir()
    fake = d / "python.exe"
    fake.write_text("", encoding="utf-8")
    s = _settings()
    fhp.rewrite(s, str(fake))
    assert s["statusLine"]["command"].startswith('"')


def test_settings_stays_valid_json_after_rewrite(tmp_path):
    fake = tmp_path / "python.exe"
    fake.write_text("", encoding="utf-8")
    s = _settings()
    fhp.rewrite(s, str(fake))
    json.loads(json.dumps(s))  # 不得產生無法序列化的內容


MISSING = "C:/no/such/python.exe"


def _write_broken(path: Path) -> bytes:
    """寫一份直譯器不存在的 settings.json，回寫入的位元組。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    s = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": f'"{MISSING}" -c "pass"'}]}]}}
    path.write_text(json.dumps(s), encoding="utf-8", newline="\n")
    return path.read_bytes()


def _run_standalone(home: Path, data: Path, config=None) -> subprocess.CompletedProcess:
    """單獨跑 fix-hook-python --write：HOME 指假家、WG_CLAUDE_DIR 指資料根、CLAUDE_CONFIG_DIR 有給才設。"""
    env = {k: v for k, v in os.environ.items() if k not in ("WG_CLAUDE_DIR", "CLAUDE_CONFIG_DIR")}
    env.update(HOME=str(home), USERPROFILE=str(home), WG_CLAUDE_DIR=str(data), PYTHONIOENCODING="utf-8")
    if config is not None:
        env["CLAUDE_CONFIG_DIR"] = str(config)
    return subprocess.run([sys.executable, str(TOOLS_DIR / "fix-hook-python.py"), "--write"], env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                          creationflags=NO_WINDOW)


def _assert_rewrote_only(target: Path, before: bytes, data: Path, decoy: bytes) -> None:
    assert MISSING not in target.read_text(encoding="utf-8")                 # 改到了 Claude Code 讀的那份
    assert target.with_suffix(".json.bak").read_bytes() == before
    assert (data / "settings.json").read_bytes() == decoy                     # 資料根的誘餌一個位元都沒動
    assert sorted(p.name for p in data.iterdir()) == ["settings.json"]


def test_standalone_rewrites_claude_config_dir_not_data_root(tmp_path):
    """資料根放誘餌、CLAUDE_CONFIG_DIR 指假設定目錄：改寫設定目錄那份。"""
    home, data, config = tmp_path / "home", tmp_path / "data", tmp_path / "cc-config"
    home.mkdir()
    decoy = _write_broken(data / "settings.json")
    before = _write_broken(config / "settings.json")
    r = _run_standalone(home, data, config)
    assert r.returncode == 0 and str(config / "settings.json") in r.stdout, r.stdout + r.stderr
    _assert_rewrote_only(config / "settings.json", before, data, decoy)


def test_standalone_without_config_dir_uses_home_claude(tmp_path):
    """沒設 CLAUDE_CONFIG_DIR：改寫家目錄 .claude 那份；資料根另指別處也不去動它。"""
    home, data = tmp_path / "home", tmp_path / "data"
    decoy = _write_broken(data / "settings.json")
    before = _write_broken(home / ".claude" / "settings.json")
    r = _run_standalone(home, data)
    assert r.returncode == 0 and str(home / ".claude" / "settings.json") in r.stdout, r.stdout + r.stderr
    _assert_rewrote_only(home / ".claude" / "settings.json", before, data, decoy)
