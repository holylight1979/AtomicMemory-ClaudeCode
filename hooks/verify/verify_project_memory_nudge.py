"""verify_project_memory_nudge.py：開場「專案還沒有記憶層」一行提示（_project_memory_nudge）。

做什麼：有版控且是專案根、根下沒有 .claude/memory → 一行指向 init-project-memory.py；
已有記憶層／沒版控／repo 子目錄／CLAUDE_DIR → 空；原始碼結構守門（有被呼叫、有 once-per-session 旗標）。
怎麼跑：python -X utf8 hooks/verify/verify_project_memory_nudge.py（印 PROJECT_MEMORY_NUDGE_CHECK PASS／FAIL）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
CLAUDE = HOOKS_DIR.parent
for _p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from handlers import session_start as ss  # noqa: E402

SRC = HOOKS_DIR / "handlers" / "session_start.py"


@pytest.fixture(autouse=True)
def _not_transient(monkeypatch):
    monkeypatch.setattr(ss, "is_transient_project_root", lambda root: False)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_vcs_root_without_memory_nudges(tmp_path):
    root = _repo(tmp_path)
    out = ss._project_memory_nudge(str(root), root, root / ".claude" / "memory")
    assert len(out) == 1
    assert "init-project-memory.py" in out[0] and str(root) in out[0]


def test_existing_memory_silent(tmp_path):
    root = _repo(tmp_path)
    mem = root / ".claude" / "memory"
    mem.mkdir(parents=True)
    assert ss._project_memory_nudge(str(root), root, mem) == []


def test_no_vcs_silent(tmp_path):
    assert ss._project_memory_nudge(str(tmp_path), tmp_path, tmp_path / ".claude" / "memory") == []


def test_repo_subdir_silent(tmp_path):
    root = _repo(tmp_path)
    sub = root / "sub"
    sub.mkdir()
    assert ss._project_memory_nudge(str(sub), sub, sub / ".claude" / "memory") == []


def test_claude_dir_silent():
    assert ss._project_memory_nudge(str(ss.CLAUDE_DIR), ss.CLAUDE_DIR, None) == []


def test_source_structure():
    src = SRC.read_text(encoding="utf-8")
    calls = [m.start() for m in re.finditer(r"_project_memory_nudge\(", src)]
    defn = src.index("def _project_memory_nudge(")
    outside = [c for c in calls if c != defn + len("def ")]
    assert outside, "_project_memory_nudge 沒被呼叫"
    fn_start = src.rindex("\ndef ", 0, outside[0])
    fn_end = src.find("\ndef ", outside[0])
    assert "project_memory_nudged" in src[fn_start:fn_end if fn_end != -1 else len(src)]


if __name__ == "__main__":
    rc = pytest.main(["-q", "-p", "no:cacheprovider", __file__])
    print("PROJECT_MEMORY_NUDGE_CHECK " + ("PASS" if rc == 0 else "FAIL"))
    sys.exit(0 if rc == 0 else 1)
