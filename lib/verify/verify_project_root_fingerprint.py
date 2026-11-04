"""lib/project_root.py 的專案根指紋：只看生效根、認領方式、宣告檔，不吃 cwd 原字串。

為什麼：SessionStart 在 compact／resume 時拿指紋判「專案根有沒有變」，變了就重建 state、丟掉 PreCompact 快照；
cwd 的磁碟代號大小寫（c:\\ vs C:\\）或 shell 進了子目錄都不是換根，指紋必須相同。
跑法：python -X utf8 -m pytest -q lib/verify/verify_project_root_fingerprint.py
"""
import json
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import project_root as pr  # noqa: E402


def _tree(tmp_path: Path) -> Path:
    (tmp_path / "GameA" / ".claude").mkdir(parents=True)
    (tmp_path / "GameA" / "Server" / ".claude").mkdir(parents=True)
    (tmp_path / "GameA" / "Server" / ".claude" / "project-tree.json").write_text(
        json.dumps({"root": "..", "subs": ["scripts"]}), encoding="utf-8")
    (tmp_path / "GameA" / "Server" / "scripts" / "lua").mkdir(parents=True)
    return tmp_path / "GameA" / "Server" / "scripts"


def _fp(cwd: str) -> str:
    pr.clear_cache()
    return pr.resolve_project_root(cwd).fingerprint


def test_fingerprint_same_for_subdir(tmp_path):
    scripts = _tree(tmp_path)
    assert _fp(str(scripts)) == _fp(str(scripts / "lua"))


def test_fingerprint_same_for_drive_letter_case(tmp_path):
    scripts = _tree(tmp_path)
    s = str(scripts)
    swapped = (s[0].swapcase() + s[1:]) if s[0].isalpha() else s
    assert _fp(s) == _fp(swapped)


def test_fingerprint_changes_when_declaration_changes(tmp_path):
    scripts = _tree(tmp_path)
    before = _fp(str(scripts))
    decl = scripts.parent / ".claude" / "project-tree.json"
    decl.write_text(json.dumps({"root": "..", "subs": ["scripts", "tools"]}), encoding="utf-8")
    import os
    os.utime(decl, (decl.stat().st_atime + 5, decl.stat().st_mtime + 5))
    assert _fp(str(scripts)) != before
