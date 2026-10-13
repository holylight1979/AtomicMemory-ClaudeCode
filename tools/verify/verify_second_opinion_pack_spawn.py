"""tools/second-opinion/pack.py 的子行程呼叫要帶壓窗參數：pythonw 父行程下 spawn git 若沒帶 CREATE_NO_WINDOW 會彈 console 宿主窗。
跑法：python -X utf8 -m pytest -q tools/verify/verify_second_opinion_pack_spawn.py
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_pack():
    path = ROOT / "tools" / "second-opinion" / "pack.py"
    spec = importlib.util.spec_from_file_location("second_opinion_pack", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["second_opinion_pack"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(sys.platform != "win32", reason="壓窗參數只在 Windows 有意義")
def test_run_passes_no_window_creationflags(monkeypatch):
    pack = _load_pack()
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)

        class R:
            returncode = 0
            stdout = "ok"
        return R()

    monkeypatch.setattr(pack.subprocess, "run", fake_run)
    assert pack._run(["git", "status"], str(ROOT), 5) == "ok"
    assert seen.get("creationflags") == subprocess.CREATE_NO_WINDOW, "pack._run 沒帶 CREATE_NO_WINDOW（會閃 console 窗）"
