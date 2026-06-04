"""verify_local_catalog_split.py — V5+ realm：本地範疇 catalog 跨錯界拆分（範疇閘）

acceptance（next-phase-alwaysload-token）：
  - render_core_section（= @import 的 MEMORY.md，外部專案所見 catalog）**不含**本地範疇
    8 顆 / `## 本地範疇` 標題，**仍含** core + feedback-* → 模擬外部專案候選不含本地範疇。
  - render_local_catalog（= 側檔 _local_catalog.md，僅核心環境 hook 注入）**含**本地 atom
    依 domain 分組。
  - main() 雙檔 round-trip：`--write` 後 `--check` exit 0（此處以 `--check` 對拍預渲染檔，
    不觸發 write_index_full → 零 audit log 污染；真實 repo 的 --write+--check 在驗收步驟跑）。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude/
SCRIPT = CLAUDE_DIR / "tools" / "sync-memory-index.py"
SPEC = importlib.util.spec_from_file_location("sync_memory_index", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

# (name, rel_path, scope) — rel_path 相對 claude_root（= memory_dir.parent）
ROWS = [
    ("core-note", "memory/core-note.md", "global"),
    ("decisions", "memory/decisions.md", "global"),
    ("feedback-foo", "_AIDocs/Failures/feedback-foo.md", "global"),
    ("gizmo-tool", "_AIDocs/_atoms/Tools/gizmo-tool.md", "global"),
    ("brain-x", "_AIDocs/_atoms/World/brain-x.md", "global"),
]
LOCAL_NAMES = ["gizmo-tool", "brain-x"]
H1 = {
    "core-note": "核心筆記", "decisions": "全域決策", "feedback-foo": "feedback-foo",
    "gizmo-tool": "Gizmo 工具踩坑", "brain-x": "腦內世界X",
}


def _build_memdir(tmp_path: Path) -> Path:
    """搭一個臨時 ~/.claude：memory/ + _AIDocs/{Failures,_atoms/<dom>}/ + _atom_index.json。"""
    mem = tmp_path / "memory"
    mem.mkdir()
    for name, rel, _ in ROWS:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {H1[name]}\n\n- Confidence: [臨]\n", encoding="utf-8")
    index = {"version": "1.0", "atoms": [
        {"name": n, "path": rel, "triggers": [f"t-{n}"], "scope": sc} for n, rel, sc in ROWS
    ]}
    (mem / "_atom_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return mem


# ─── 範疇閘：core catalog（外部專案所見）不含本地範疇 ───────────────────────────


def test_core_section_excludes_local_keeps_core_and_feedback(tmp_path: Path):
    _build_memdir(tmp_path)
    core = MOD.render_core_section(ROWS, tmp_path, {})
    # core：含核心 atom + feedback-* 聚合行
    assert "| core-note | 核心筆記 |" in core
    assert "| decisions | 全域決策 |" in core
    assert "feedback-*" in core
    # core：不含本地範疇 8 顆 / 標題（外部專案零本地負擔）
    assert "## 本地範疇" not in core
    for nm in LOCAL_NAMES:
        assert nm not in core, f"local atom {nm} 不該出現在 core catalog"
    # core：保留指標供 discoverability
    assert "_local_catalog.md" in core


def test_local_catalog_groups_local_by_domain(tmp_path: Path):
    _build_memdir(tmp_path)
    local = MOD.render_local_catalog(ROWS, tmp_path, {})
    assert local, "有 local atom 時側檔不該為空"
    assert "### Tools" in local and "### World" in local
    assert "| gizmo-tool | Gizmo 工具踩坑 |" in local
    assert "| brain-x | 腦內世界X |" in local
    # core / feedback 不進側檔
    assert "core-note" not in local
    assert "feedback-foo" not in local


# ─── 雙檔 round-trip：--check 對拍預渲染檔 → exit 0 / drift → exit 1 ──────────────


def _prerender(mem: Path, claude_root: Path) -> None:
    """以 MOD 渲染兩檔並落地（對拍 main() 的 new_core/new_local 組裝；無 knowledge_tail）。"""
    core = MOD.render_core_section(ROWS, claude_root, {}) + "\n"
    local = MOD.render_local_catalog(ROWS, claude_root, {}) + "\n"
    (mem / "MEMORY.md").write_text(core, encoding="utf-8")
    (mem / "_local_catalog.md").write_text(local, encoding="utf-8")


def _run_check(mem: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--memory-dir", str(mem)],
        capture_output=True, text=True,
    )


def test_check_roundtrip_no_drift(tmp_path: Path):
    mem = _build_memdir(tmp_path)
    _prerender(mem, tmp_path)
    r = _run_check(mem)
    assert r.returncode == 0, f"預期無 drift，stderr={r.stderr}"


def test_check_detects_core_drift(tmp_path: Path):
    mem = _build_memdir(tmp_path)
    _prerender(mem, tmp_path)
    (mem / "MEMORY.md").write_text("# 被竄改\n", encoding="utf-8")
    r = _run_check(mem)
    assert r.returncode == 1
    assert "MEMORY.md drift" in r.stderr


def test_check_detects_local_drift(tmp_path: Path):
    mem = _build_memdir(tmp_path)
    _prerender(mem, tmp_path)
    (mem / "_local_catalog.md").write_text("# 被竄改\n", encoding="utf-8")
    r = _run_check(mem)
    assert r.returncode == 1
    assert "_local_catalog.md drift" in r.stderr
