"""verify_discover_memoize.py — discover_all_project_memory_dirs per-process memoize（A2）。

契約（wg_core）：
- 同簽章（registry 檔 + projects/ 目錄的 path+mtime）重複呼叫 → 底層只實掃一次
- registry 變動（登錄新專案）→ 簽章失效 → 重掃、結果反映新專案
- 回傳為淺拷貝：caller 變異不污染快取
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest  # noqa: F401

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_core  # noqa: E402

_INDEX_MD = """| Atom | Path | Trigger |
|------|------|---------|
| t-atom | t-atom.md | alpha |
"""


@pytest.fixture
def env(tmp_path, monkeypatch):
    claude = tmp_path / ".claude"
    mem = claude / "memory"
    mem.mkdir(parents=True)
    (claude / "projects").mkdir()
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", claude)
    monkeypatch.setattr(wg_core, "MEMORY_DIR", mem)
    monkeypatch.setattr(wg_core, "REGISTRY_PATH", mem / "project-registry.json")
    monkeypatch.setattr(wg_core, "_DISCOVER_CACHE", None)
    return tmp_path, claude, mem


def _register(tmp_path, mem, slug: str):
    root = tmp_path / slug
    (root / ".claude" / "memory").mkdir(parents=True)
    (root / ".claude" / "memory" / "MEMORY.md").write_text(_INDEX_MD, encoding="utf-8")
    reg_path = mem / "project-registry.json"
    reg = {"projects": {}}
    if reg_path.exists():
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    reg["projects"][slug] = {"root": str(root), "last_seen": "2026-01-01"}
    reg_path.write_text(json.dumps(reg), encoding="utf-8")
    # mtime 解析度保險：往前推 1 秒再壓回，確保簽章可見變化（mtime_ns 一般已足夠）
    st = reg_path.stat()
    os.utime(reg_path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))


def test_second_call_uses_cache(env, monkeypatch):
    tmp_path, _claude, mem = env
    _register(tmp_path, mem, "proj-a")
    scans = []
    real = wg_core._discover_all_project_memory_dirs_uncached

    def counted():
        scans.append(1)
        return real()

    monkeypatch.setattr(wg_core, "_discover_all_project_memory_dirs_uncached", counted)
    first = wg_core.discover_all_project_memory_dirs()
    second = wg_core.discover_all_project_memory_dirs()
    assert first == second
    assert {s for s, _ in first} == {"proj-a"}
    assert len(scans) == 1  # 第二次走快取，未重掃


def test_registry_change_invalidates(env):
    tmp_path, _claude, mem = env
    _register(tmp_path, mem, "proj-a")
    assert {s for s, _ in wg_core.discover_all_project_memory_dirs()} == {"proj-a"}
    time.sleep(0.01)
    _register(tmp_path, mem, "proj-b")  # registry mtime 變 → 簽章失效
    assert {s for s, _ in wg_core.discover_all_project_memory_dirs()} == {"proj-a", "proj-b"}


def test_returned_list_is_copy(env):
    tmp_path, _claude, mem = env
    _register(tmp_path, mem, "proj-a")
    first = wg_core.discover_all_project_memory_dirs()
    first.append(("bogus", Path(".")))
    second = wg_core.discover_all_project_memory_dirs()
    assert ("bogus", Path(".")) not in second
