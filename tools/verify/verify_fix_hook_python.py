"""verify_fix_hook_python.py — settings.json 直譯器路徑校正工具測試。

情境即「別台機器 git clone 後，settings.json 寫的是原作者的絕對路徑」：
  1. 掃得出所有帶指令的欄位（statusLine + 各 event 的 hooks）
  2. 改寫換掉開頭直譯器、指令其餘部分（-c "..." 全串）一字不動
  3. pythonw（不彈 console）維持 w 版，不會被換成會彈視窗的 python
  4. 已經正確就不動（本機不該被無謂改寫）
  5. 候選直譯器實跑驗證，不合格拒絕寫入
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TOOLS_DIR = Path.home() / ".claude" / "tools"

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
    assert cmd.startswith(str(fake).replace("python.exe", "python"))
    # statusLine 的腳本參數也要保留
    assert "statusline.py" in s["statusLine"]["command"]


def test_pythonw_stays_windowless(tmp_path):
    """原本用 pythonw 的 hook 不得被換成會彈 console 的 python。"""
    (tmp_path / "python.exe").write_text("", encoding="utf-8")
    (tmp_path / "pythonw.exe").write_text("", encoding="utf-8")
    s = _settings()
    fhp.rewrite(s, str(tmp_path / "python.exe"))

    assert s["hooks"]["Stop"][0]["hooks"][0]["command"].startswith(
        str(tmp_path / "pythonw.exe"))
    # statusLine 原本就是 python（需要 stdout）→ 維持非 w 版
    assert s["statusLine"]["command"].startswith(str(tmp_path / "python.exe"))


def test_no_change_when_already_correct(tmp_path):
    fake = tmp_path / "pythonw.exe"
    fake.write_text("", encoding="utf-8")
    s = {"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": f'{fake} -c "pass"'}]}]}}
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
