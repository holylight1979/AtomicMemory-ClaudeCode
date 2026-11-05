"""verify_init_project_memory.py：tools/init-project-memory.py 的實跑驗證。

做什麼：在 tmp 建 git init 的假專案，子行程實跑 CLI，驗
(a) 首跑建齊檔與目錄、MEMORY.md 含 catalog 標記、.gitignore 五行、索引空；
(b) 既有自訂 MEMORY.md 逐 byte 不變且不計入 created；(c) 重跑 created=0；
(d) --dry-run 不落檔；(e) --cwd 指向 ~/.claude → exit 2。
怎麼跑：python -X utf8 hooks/verify/verify_init_project_memory.py（印 INIT_PROJECT_MEMORY_CHECK PASS／FAIL）
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parents[2]
SCRIPT = CLAUDE / "tools" / "init-project-memory.py"
DIRS = ("shared", "failures", "personal", "_staging", "episodic")


def _run(cwd: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "--cwd", str(cwd), *extra],
                          capture_output=True, text=True, encoding="utf-8")


def _created(out: str) -> int:
    return int(re.search(r"created=(\d+)", out).group(1))


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    p = tmp_path / "demo proj"
    p.mkdir()
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    return p


def test_first_run_builds_everything(proj: Path):
    r = _run(proj, "--allow-transient")
    assert r.returncode == 0, r.stderr
    mem = proj / ".claude" / "memory"
    for d in DIRS:
        assert (mem / d).is_dir(), d
    for f in ("MEMORY.md", ".gitignore", "README.md", "shared/.gitkeep", "failures/.gitkeep"):
        assert (mem / f).is_file(), f
    md = (mem / "MEMORY.md").read_text(encoding="utf-8")
    assert "<!-- atom-catalog -->" in md and "<!-- /atom-catalog -->" in md
    assert (mem / ".gitignore").read_text(encoding="utf-8").split() == [
        "_atom_index.json", "_ATOM_INDEX.md", "_staging/", "episodic/", "vector-db/"]
    assert json.loads((mem / "_atom_index.json").read_text(encoding="utf-8"))["atoms"] == []
    assert "INIT_PROJECT_MEMORY DONE" in r.stdout


def test_custom_memory_md_untouched_and_rerun_creates_nothing(proj: Path):
    mem = proj / ".claude" / "memory"
    mem.mkdir(parents=True)
    custom = "# 我自己寫的\n\n分區規則\n".encode("utf-8")
    (mem / "MEMORY.md").write_bytes(custom)
    r1 = _run(proj, "--allow-transient")
    assert r1.returncode == 0, r1.stderr
    assert (mem / "MEMORY.md").read_bytes() == custom
    assert "existed  .claude/memory/MEMORY.md" in r1.stdout
    r2 = _run(proj, "--allow-transient")
    assert _created(r2.stdout) == 0


def test_dry_run_writes_nothing(proj: Path):
    r = _run(proj, "--allow-transient", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert not (proj / ".claude").exists()
    assert "dry_run=1" in r.stdout and _created(r.stdout) > 0


def test_refuses_claude_dir():
    r = _run(CLAUDE, "--allow-transient")
    assert r.returncode == 2


if __name__ == "__main__":
    rc = pytest.main([__file__, "-q", "-p", "no:cacheprovider"])
    print("INIT_PROJECT_MEMORY_CHECK PASS" if rc == 0 else "INIT_PROJECT_MEMORY_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
