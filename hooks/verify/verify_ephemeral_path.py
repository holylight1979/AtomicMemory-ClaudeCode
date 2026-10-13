"""verify_ephemeral_path.py：暫存路徑判斷（handlers/_shared._is_ephemeral_path）要認得 Windows 8.3 短路徑。

背景：這台機器的暫存目錄同時以長路徑（C:\\Users\\holylight\\AppData\\Local\\Temp）與 8.3 短路徑（C:\\Users\\HOLYLI~1\\…）出現，
session scratchpad 就是短路徑寫法；只比字面前綴時兩種寫法對不上，scratchpad 裡的一次性腳本被當成改了程式碼，
寫碼查核 (d) 要求補案例。
正例：長／短 × 長／短（路徑寫法 × gettempdir 回傳寫法）四種組合都判成暫存，檔案還不存在也一樣。
反例：一般專案路徑、含 `~1` 但不在暫存目錄下的路徑判成非暫存；`<暫存>\\..\\..\\專案\\x.py` 是專案原碼（經 post_tool_use 照常記改檔）。
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


def test_021_long_path_failure_is_reported(monkeypatch, capsys):
    """021（codex 審 020 的 WARN）：GetLongPathNameW 對短路徑與各層祖先都回 0（Win32 失敗不拋例外）→ 照原樣比對，並在 stderr
    說一聲，不靜默；不帶短檔名記號的路徑轉不了不出聲（轉不轉都不影響比對）。"""
    monkeypatch.setattr(ctypes.windll.kernel32, "GetLongPathNameW", lambda *a: 0)
    monkeypatch.setattr(_shared.tempfile, "gettempdir", lambda: r"C:\Users\holylight\AppData\Local\Temp")
    capsys.readouterr()
    assert _shared._is_ephemeral_path(r"C:\Users\HOLYLI~1\AppData\Local\Temp\new_dir\probe.py") is False   # 轉不了＝照一般檔記
    assert "短路徑轉長路徑失敗" in capsys.readouterr().err
    assert _shared._is_ephemeral_path(r"C:\proj\x.py") is False and capsys.readouterr().err == ""


def _noted_via_post_tool_use(monkeypatch, path: str) -> bool:
    """經 post_tool_use 入口（handle_post_tool_use 的 Edit）改這個檔，它有沒有進 modified_files（暫存檔不進）。"""
    from handlers import post_tool_use as pt
    state = {"turn_seq": 3, "session": {"cwd": str(HOOKS_DIR.parent)}}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"session_id": "sid-eph", "tool_name": "Edit", "tool_input": {"file_path": path},
                                 "tool_response": {}, "cwd": str(HOOKS_DIR.parent)}, {"docdrift": {"enabled": False}})
    return any(m.get("path") == path for m in state.get("modified_files") or [])


def _rel_to_shared(long_: str) -> str:
    """從暫存目錄用 `..` 走到本樹 hooks/handlers/_shared.py 的相對路徑；不在同一個磁碟就跳過。"""
    try:
        return os.path.relpath(str(HOOKS_DIR / "handlers" / "_shared.py"), long_)
    except ValueError:
        pytest.skip("暫存目錄與 worktree 不在同一個磁碟，接不出 `..` 路徑")


def test_028_dotdot_out_of_temp_is_project_code(monkeypatch):
    """028：暫存目錄後面接 `..` 跳回專案原碼（`<暫存>\\..\\..\\..\\.claude-wt\\…\\_shared.py`）不是暫存：轉長路徑後先 normpath
    再比包含；長短寫法交叉四組都測，每一組都經 post_tool_use 入口確認這個改檔照常進 modified_files。"""
    long_, short = _tmp_forms()
    rel = _rel_to_shared(long_)
    for tmp, base in ((long_, short), (long_, long_), (short, long_), (short, short)):
        monkeypatch.setattr(_shared.tempfile, "gettempdir", lambda t=tmp: t)
        p = base + "\\" + rel
        assert _shared._is_ephemeral_path(p) is False, (tmp, base)
        assert _noted_via_post_tool_use(monkeypatch, p), (tmp, base)


@pytest.mark.parametrize("tmp_form", ["long", "short"])
@pytest.mark.parametrize("path_form", ["long", "short"])
@pytest.mark.parametrize("path_pre, tmp_pre", [("\\\\?\\", ""), ("", "\\\\?\\"), ("\\\\?\\", "\\\\?\\")])
def test_030_long_path_prefix_on_either_side_is_still_temp(monkeypatch, path_pre, tmp_pre, path_form, tmp_form):
    """030／032：`\\\\?\\` 長路徑前綴只出現在路徑側、只出現在暫存側、兩側都有 × 路徑長／短 × 暫存長／短，共 12 組，scratchpad
    都判暫存（比對前兩側統一表示），經 post_tool_use 也不進 modified_files。純長路徑的 3 組不需要 8.3 短名，每台 Windows 都跑；
    用到短名的組在沒有 8.3 短名的機器跳過。"""
    long_ = _win_path("GetLongPathNameW", tempfile.gettempdir())       # 先算好：下面會替身 gettempdir
    short = _tmp_forms()[1] if "short" in (path_form, tmp_form) else long_
    monkeypatch.setattr(_shared.tempfile, "gettempdir", lambda: tmp_pre + (long_ if tmp_form == "long" else short))
    p = path_pre + (long_ if path_form == "long" else short) + r"\claude\sess\scratchpad\probe.py"
    assert _shared._is_ephemeral_path(p) is True, p
    assert not _noted_via_post_tool_use(monkeypatch, p), p


def _codex_regression_paths(long_: str):
    """codex 審 031 時實測判成非暫存的寫法（都是暫存目錄的同一串字，只換了前綴或磁碟機）：固化成回歸案。"""
    tail = long_[2:] + r"\claude\sess\scratchpad\probe.py"                 # 去掉「C:」的部分
    other = "E:" if long_[:1].upper() == "D" else "D:"
    return {
        "GLOBALROOT": r"\\?\GLOBALROOT\Device\HarddiskVolume3" + tail,
        "device": "\\\\.\\" + long_ + r"\claude\sess\scratchpad\probe.py",
        "volume": r"\\?\Volume{00000000-0000-0000-0000-000000000000}" + tail,
        "drive-relative": long_[:2] + tail.lstrip("\\"),
        "other-drive": other + tail,
    }


@pytest.mark.parametrize("kind", ["GLOBALROOT", "device", "volume", "drive-relative", "other-drive"])
def test_032_other_namespaces_and_drives_are_not_temp(monkeypatch, kind):
    """032：GLOBALROOT、`\\\\.\\` 裝置命名空間、`\\\\?\\Volume{…}\\`、`C:foo` 磁碟機相對路徑、別的磁碟機，即使後面接的是暫存目錄的
    同一串字，也判非暫存（不展開這些寫法；錯的方向是多要證據，不是漏記）。不需要 8.3 短名。"""
    long_ = _win_path("GetLongPathNameW", tempfile.gettempdir())
    monkeypatch.setattr(_shared.tempfile, "gettempdir", lambda: long_)
    p = _codex_regression_paths(long_)[kind]
    assert _shared._is_ephemeral_path(p) is False, p


def test_030_prefixed_dotdot_out_of_temp_is_project_code(monkeypatch):
    """030：方向不放寬：`\\\\?\\` 加 `..` 逃出暫存的仍是專案原碼，經 post_tool_use 照常記帳。"""
    long_, _ = _tmp_forms()
    monkeypatch.setattr(_shared.tempfile, "gettempdir", lambda: long_)
    p = "\\\\?\\" + long_ + "\\" + _rel_to_shared(long_)
    assert _shared._is_ephemeral_path(p) is False and _noted_via_post_tool_use(monkeypatch, p)


@pytest.mark.parametrize("path, tmp, is_temp", [
    (r"\\?\UNC\localhost\nosuchshare\tmp\claude\x.py", r"\\localhost\nosuchshare\tmp", True),
    (r"\\localhost\nosuchshare\tmp\claude\x.py", r"\\?\UNC\localhost\nosuchshare\tmp", True),
    (r"\\?\UNC\localhost\nosuchshare\other\x.py", r"\\localhost\nosuchshare\tmp", False),
    (r"\\?\UNC\localhost\nosuchshare\tmp\..\other\x.py", r"\\localhost\nosuchshare\tmp", False),
    (r"\\localhost\othershare\tmp\x.py", r"\\?\UNC\localhost\nosuchshare\tmp", False),
])
def test_030_unc_forms(monkeypatch, path, tmp, is_temp):
    """030：`\\\\?\\UNC\\server\\share\\…` 等同 `\\\\server\\share\\…`；暫存在 UNC 上時兩種寫法都判暫存，逃出暫存或別的分享仍判非暫存。"""
    monkeypatch.setattr(_shared.tempfile, "gettempdir", lambda: tmp)
    assert _shared._is_ephemeral_path(path) is is_temp
