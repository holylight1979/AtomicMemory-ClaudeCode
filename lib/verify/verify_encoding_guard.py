"""verify_encoding_guard.py — 亂碼名稱的寫入端守門 + svn add 提醒閘。

已知亂碼案例：TSLG 的 `shared/UIºt¥X`＝`UI演出` 的 Big5 位元組被當 cp1252 解碼。鎖住既有行為：
  - `slugify("UIºt¥X")` 結果不含 U+0080–U+00FF（亂碼字元被剝掉，不會成為 atom 檔名）
  - `_clean_segment("UIºt¥X")` 拒收（回空字串，不會成為範疇資料夾名）
  - 正常中文／ASCII 名稱不受影響（不是把所有 Latin-1 都當亂碼——只鎖這個案例）
  - pre_tool_use.check_svn_encoding：`svn add` 帶非 ASCII 路徑 → `[Guardian:SvnEncoding]` 一行、零子行程；
    ASCII 路徑／非 add 子指令／非 Bash 工具 → None。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude/
for _p in (CLAUDE, CLAUDE / "hooks"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lib.atom_locations import _clean_segment  # noqa: E402
from lib.atom_spec import slugify  # noqa: E402
from handlers.pre_tool_use import check_svn_encoding  # noqa: E402

MOJIBAKE = "UIºt¥X"
LATIN1_RE = re.compile(r"[\u0080-\u00ff]")


def test_known_mojibake_case_slugify_strips_latin1():
    out = slugify(MOJIBAKE)
    assert not LATIN1_RE.search(out), out
    assert out == "uitx"


def test_known_mojibake_case_clean_segment_rejects():
    assert _clean_segment(MOJIBAKE) == ""


def test_cjk_and_ascii_names_still_pass():
    assert slugify("UI演出") == "ui演出"
    assert _clean_segment("UI演出") == "UI演出"
    assert _clean_segment("Tools") == "Tools"


def test_svn_add_non_ascii_path_warns_without_subprocess(monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("子行程")))
    msg = check_svn_encoding("Bash", {"command": 'svn add "memory/shared/UI演出"'})
    assert msg and msg.startswith("[Guardian:SvnEncoding]"), msg
    assert check_svn_encoding("PowerShell", {"command": "cd C:\\TSLG; svn add .claude/memory/shared/UI演出"}) == msg
    assert check_svn_encoding("Bash", {"command": "svn add --parents memory/x/UI演出/a.md"}) == msg


def test_svn_add_ascii_or_other_commands_silent():
    assert check_svn_encoding("Bash", {"command": "svn add memory/shared/ui-show"}) is None
    assert check_svn_encoding("Bash", {"command": "svn status memory/shared/UI演出"}) is None
    assert check_svn_encoding("Bash", {"command": "svn commit -m 'UI演出' memory"}) is None
    assert check_svn_encoding("Bash", {"command": "echo UI演出"}) is None
    assert check_svn_encoding("Write", {"file_path": "svn add UI演出"}) is None
