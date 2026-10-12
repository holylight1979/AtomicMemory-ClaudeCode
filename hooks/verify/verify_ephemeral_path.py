"""verify_ephemeral_path.py：暫存路徑判斷（handlers/_shared._is_ephemeral_path）要認得 Windows 8.3 短路徑。

背景：這台機器的暫存目錄同時以長路徑（C:\\Users\\holylight\\AppData\\Local\\Temp）與 8.3 短路徑（C:\\Users\\HOLYLI~1\\…）出現，
session scratchpad 就是短路徑寫法；只比字面前綴時兩種寫法對不上，scratchpad 裡的一次性腳本被當成改了程式碼，
寫碼查核 (d) 要求補案例。
正例：長／短 × 長／短（路徑寫法 × gettempdir 回傳寫法）四種組合都判成暫存，檔案還不存在也一樣。
反例：一般專案路徑、含 `~1` 但不在暫存目錄下的路徑判成非暫存。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_ephemeral_path.py
"""
from __future__ import annotations

import ctypes
import os
import sys
import tempfile
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
for p in (str(HOOKS_DIR), str(HOOKS_DIR.parent / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers import _shared  # noqa: E402

pytestmark = pytest.mark.skipif(os.name != "nt", reason="8.3 短路徑只在 Windows")


def _win_path(fn_name: str, p: str) -> str:
    buf = ctypes.create_unicode_buffer(32768)
    n = getattr(ctypes.windll.kernel32, fn_name)(p, buf, 32768)
    return buf.value if 0 < n < 32768 else p


def _tmp_forms():
    """(長路徑, 短路徑) 寫法的系統暫存目錄；這台機器 8.3 短名關閉（兩者相同）就跳過。"""
    long_ = _win_path("GetLongPathNameW", tempfile.gettempdir())
    short = _win_path("GetShortPathNameW", long_)
    if short.lower() == long_.lower():
        pytest.skip("這台機器的暫存目錄沒有 8.3 短名，四種組合無從構造")
    return long_, short


@pytest.mark.parametrize("path_form", ["long", "short"])
@pytest.mark.parametrize("tmp_form", ["long", "short"])
def test_temp_paths_in_either_form_are_ephemeral(monkeypatch, tmp_form, path_form):
    """路徑與 gettempdir 各自可能是長或短寫法；檔案還不存在（scratchpad 剛要寫）也要判成暫存。"""
    long_, short = _tmp_forms()
    monkeypatch.setattr(_shared.tempfile, "gettempdir", lambda: long_ if tmp_form == "long" else short)
    base = long_ if path_form == "long" else short
    for p in (base + r"\claude\sess\scratchpad\probe.py", base.replace("\\", "/") + "/claude/x/new_dir/a.py"):
        assert _shared._is_ephemeral_path(p) is True, (tmp_form, path_form, p)


def test_project_paths_and_tilde_outside_temp_are_not_ephemeral(monkeypatch):
    """一般專案路徑、含 `~1` 但不在暫存目錄下的路徑（例：C:\\PROGRA~1\\…）都不是暫存：不能把 `~1` 字樣當成暫存。"""
    long_, short = _tmp_forms()
    for tmp in (long_, short):
        monkeypatch.setattr(_shared.tempfile, "gettempdir", lambda t=tmp: t)
        for p in (r"C:\proj\src\a.py", r"C:\PROGRA~1\proj\src\a.py", r"C:\Users\HOLYLI~2\proj\a.py",
                  str(HOOKS_DIR / "handlers" / "_shared.py")):
            assert _shared._is_ephemeral_path(p) is False, (tmp, p)
