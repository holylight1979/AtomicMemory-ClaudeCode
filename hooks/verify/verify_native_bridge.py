"""verify_native_bridge.py — 原生記憶橋接（tools/native-memory-bridge.py）契約。

sync()：
  - 橋接檔含機器生成標記 + 每 core atom 一行指標（[[name]] + Read 路徑）
  - MEMORY.md 指標行冪等（重跑不重複）；既有內容保留
  - 目標目錄不存在 → 不寫、回 reason；目標 MEMORY.md 竟含 `| Atom` 表頭 → 拒寫
  - **guard 組合不變式**：寫入後的原生目錄仍不得被
    wg_core.discover_all_project_memory_dirs 當 atom 索引 dir 納入
    （橋接輸出必須是 harness 清單格式，不得引入 atom marker）
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_ROOT), str(_ROOT / "hooks")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_core  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "native_memory_bridge", _ROOT / "tools" / "native-memory-bridge.py")
nmb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nmb)

ATOMS = [
    {"name": "decisions", "path": "memory/decisions.md",
     "triggers": ["決策", "記憶系統"], "scope": "global"},
    {"name": "workflow-rules", "path": "memory/workflow-rules.md",
     "triggers": ["工作流"], "scope": "global"},
]


def test_bridge_file_and_index_line(tmp_path):
    r = nmb.sync(tmp_path, ATOMS)
    assert r["written"] and r["atom_count"] == 2
    bridge = (tmp_path / "atom-index-bridge.md").read_text(encoding="utf-8")
    assert "機器生成勿手編" in bridge
    assert "[[decisions]]" in bridge and "memory/decisions.md" in bridge
    assert "[[workflow-rules]]" in bridge
    mem = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert mem.count("atom-index-bridge.md") == 1


def test_idempotent_and_preserves_existing(tmp_path):
    (tmp_path / "MEMORY.md").write_text(
        "- [PowerShell BOM gotcha](ps-bom.md) — pwsh strips BOM\n", encoding="utf-8")
    nmb.sync(tmp_path, ATOMS)
    nmb.sync(tmp_path, ATOMS)
    mem = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert mem.count("atom-index-bridge.md") == 1
    assert "ps-bom.md" in mem  # 既有 harness 行保留


def test_missing_dir_refuses(tmp_path):
    r = nmb.sync(tmp_path / "nope", ATOMS)
    assert not r["written"] and "不存在" in r["reason"]


def test_atom_table_target_refused(tmp_path):
    (tmp_path / "MEMORY.md").write_text(
        "| Atom | 路徑 |\n|---|---|\n| x | x.md |\n", encoding="utf-8")
    r = nmb.sync(tmp_path, ATOMS)
    assert not r["written"] and "撞名" in r["reason"]
    assert not (tmp_path / "atom-index-bridge.md").exists()


def test_bridged_dir_not_misclassified_as_atom_dir(tmp_path):
    """組合不變式：橋接後的原生 memory dir 不得被 atom 掃描納入。"""
    claude_dir = tmp_path / ".claude"
    mem = claude_dir / "projects" / "c--proj-x" / "memory"
    mem.mkdir(parents=True)
    (mem / "MEMORY.md").write_text(
        "- [PowerShell BOM gotcha](ps-bom.md) — pwsh strips BOM\n", encoding="utf-8")
    nmb.sync(mem, ATOMS)

    saved = (wg_core.CLAUDE_DIR, wg_core.MEMORY_DIR, wg_core.REGISTRY_PATH)
    wg_core.CLAUDE_DIR = claude_dir
    wg_core.MEMORY_DIR = claude_dir / "memory"
    wg_core.MEMORY_DIR.mkdir(parents=True)
    wg_core.REGISTRY_PATH = wg_core.MEMORY_DIR / "project-registry.json"
    try:
        root = tmp_path / "proj-x"
        root.mkdir()
        wg_core.REGISTRY_PATH.write_text(
            json.dumps({"projects": {"c--proj-x": {"root": str(root)}}}),
            encoding="utf-8")
        slugs = {s for s, _ in wg_core.discover_all_project_memory_dirs()}
        assert "c--proj-x" not in slugs
    finally:
        wg_core.CLAUDE_DIR, wg_core.MEMORY_DIR, wg_core.REGISTRY_PATH = saved
