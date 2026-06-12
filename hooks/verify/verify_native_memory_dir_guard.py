"""verify_native_memory_dir_guard.py — CC harness 原生 memory dir 誤納防護 (2026-06-12).

守住的不變式：
1. 新版 CC harness file-based memory（projects/<slug>/memory/）會自建 MEMORY.md
   （`- [Title](file.md) — hook` 清單格式），與 atom 索引撞名。
   `discover_all_project_memory_dirs()` 不得把它納入 cross-project 掃描——
   否則 harness 自寫記憶檔會被 discover_v4_sublayers 的 flat-legacy 路徑當 atom 注入。
   兩個分支都要守：registry old-path fallback（無 marker 檢查的歷史漏洞，
   2026-06-12 c--users-holylight--claude 實例）與 Phase-0 目錄掃描。
2. 合法 atom 索引照常納入：_atom_index.json / _ATOM_INDEX.md /
   MEMORY.md 含「| Atom」trigger 表頭 / migrated-v2.21 slug-pointer stub。
3. cbf7c15 的 _is_global_mem 護欄不得回退（全域 memory dir 不得當專案回傳）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[2]  # hooks/verify/ → ~/.claude
HOOKS = CLAUDE / "hooks"
for p in (str(CLAUDE), str(HOOKS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_core  # noqa: E402

HARNESS_INDEX = "# Memory Index\n\n- [PowerShell BOM gotcha](ps-bom.md) — pwsh strips BOM\n"
ATOM_TABLE_INDEX = "# Atom Index\n\n| Atom | 路徑 | Trigger |\n|---|---|---|\n| foo | foo.md | bar, baz |\n"
MIGRATED_STUB = "Status: migrated-v2.21\n- Root: C:\\somewhere\n"


def _make_env(tmp_path: Path):
    """建假 ~/.claude 結構並 patch wg_core 全域，回傳 restore callback。"""
    claude_dir = tmp_path / ".claude"
    mem_dir = claude_dir / "memory"
    mem_dir.mkdir(parents=True)
    (claude_dir / "projects").mkdir()
    saved = (wg_core.CLAUDE_DIR, wg_core.MEMORY_DIR, wg_core.REGISTRY_PATH)
    wg_core.CLAUDE_DIR = claude_dir
    wg_core.MEMORY_DIR = mem_dir
    wg_core.REGISTRY_PATH = mem_dir / "project-registry.json"

    def restore():
        wg_core.CLAUDE_DIR, wg_core.MEMORY_DIR, wg_core.REGISTRY_PATH = saved

    return claude_dir, restore


def _proj_mem(claude_dir: Path, slug: str) -> Path:
    d = claude_dir / "projects" / slug / "memory"
    d.mkdir(parents=True)
    return d


def _write_registry(claude_dir: Path, slugs_roots: dict):
    payload = {"projects": {s: {"root": r} for s, r in slugs_roots.items()}}
    wg_core.REGISTRY_PATH.write_text(json.dumps(payload), encoding="utf-8")


def _slugs(results):
    return {s for s, _ in results}


def test_harness_native_dir_excluded_via_registry_old_path(tmp_path):
    """registry old-path 分支：harness MEMORY.md（清單格式）不得納入。"""
    claude_dir, restore = _make_env(tmp_path)
    try:
        mem = _proj_mem(claude_dir, "c--proj-a")
        (mem / "MEMORY.md").write_text(HARNESS_INDEX, encoding="utf-8")
        (mem / "ps-bom.md").write_text("---\nname: ps-bom\n---\nfact", encoding="utf-8")
        # root 指向不存在 .claude/memory 的地方 → 走 old_mem 分支
        root = tmp_path / "proj-a"
        root.mkdir()
        _write_registry(claude_dir, {"c--proj-a": str(root)})
        assert "c--proj-a" not in _slugs(wg_core.discover_all_project_memory_dirs())
    finally:
        restore()


def test_harness_native_dir_excluded_via_phase0_scan(tmp_path):
    """Phase-0 目錄掃描分支：registry 沒登錄、只有 harness MEMORY.md → 不納入。"""
    claude_dir, restore = _make_env(tmp_path)
    try:
        mem = _proj_mem(claude_dir, "c--proj-b")
        (mem / "MEMORY.md").write_text(HARNESS_INDEX, encoding="utf-8")
        assert "c--proj-b" not in _slugs(wg_core.discover_all_project_memory_dirs())
    finally:
        restore()


def test_empty_dir_excluded(tmp_path):
    """harness 預建的空 memory dir（2026-06-12 實例）不得納入。"""
    claude_dir, restore = _make_env(tmp_path)
    try:
        _proj_mem(claude_dir, "c--proj-empty")
        _write_registry(claude_dir, {"c--proj-empty": str(tmp_path / "nowhere")})
        assert "c--proj-empty" not in _slugs(wg_core.discover_all_project_memory_dirs())
    finally:
        restore()


def test_atom_markers_still_included(tmp_path):
    """合法 atom 索引三型態（trigger 表 / json / migrated stub）照常納入。"""
    claude_dir, restore = _make_env(tmp_path)
    try:
        m1 = _proj_mem(claude_dir, "c--atom-table")
        (m1 / "MEMORY.md").write_text(ATOM_TABLE_INDEX, encoding="utf-8")
        m2 = _proj_mem(claude_dir, "c--atom-json")
        (m2 / "_atom_index.json").write_text("{}", encoding="utf-8")
        m3 = _proj_mem(claude_dir, "c--migrated-stub")
        (m3 / "MEMORY.md").write_text(MIGRATED_STUB, encoding="utf-8")
        got = _slugs(wg_core.discover_all_project_memory_dirs())
        assert {"c--atom-table", "c--atom-json", "c--migrated-stub"} <= got
    finally:
        restore()


def test_global_mem_guard_not_regressed(tmp_path):
    """cbf7c15 護欄：registry root=家目錄 → 全域 memory dir 不得當專案回傳。"""
    claude_dir, restore = _make_env(tmp_path)
    try:
        # 全域 memory dir 放上合法 atom 索引，仍不得被回傳
        (claude_dir / "memory" / "_atom_index.json").write_text("{}", encoding="utf-8")
        _write_registry(claude_dir, {"c--home": str(tmp_path)})  # root/.claude/memory == 全域
        paths = {m.resolve() for _, m in wg_core.discover_all_project_memory_dirs()}
        assert (claude_dir / "memory").resolve() not in paths
    finally:
        restore()


def test_source_has_marker_helper():
    """靜態守門：兩分支都必須過 _has_atom_index_marker，_is_global_mem 不得移除。"""
    src = (HOOKS / "wg_core.py").read_text(encoding="utf-8")
    assert src.count("_has_atom_index_marker(") >= 3, "helper 定義 + 兩分支呼叫缺一"
    assert "_is_global_mem" in src, "cbf7c15 全域 memory 護欄被移除"
