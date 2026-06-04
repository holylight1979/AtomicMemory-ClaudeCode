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


def _build_memdir(tmp_path: Path, rows=ROWS) -> Path:
    """搭一個臨時 ~/.claude：memory/ + _AIDocs/{Failures,_atoms/<dom>}/ + _atom_index.json。"""
    mem = tmp_path / "memory"
    mem.mkdir()
    for name, rel, _ in rows:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {H1.get(name, name)}\n\n- Confidence: [臨]\n", encoding="utf-8")
    index = {"version": "1.0", "atoms": [
        {"name": n, "path": rel, "triggers": [f"t-{n}"], "scope": sc} for n, rel, sc in rows
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


def test_local_catalog_shows_lv1_roots_only(tmp_path: Path):
    """OPEN 1：側檔只列 Lv1 根 + 遞迴計數 + drill 指標（不攤每顆 atom caption）。"""
    _build_memdir(tmp_path)
    local = MOD.render_local_catalog(ROWS, tmp_path, {})
    assert local, "有 local atom 時側檔不該為空"
    # Lv1 根表（Tools/World 各 1 顆）
    assert "| Tools | 1 |" in local and "| World | 1 |" in local
    # 單 atom 葉無子層 → 不生 _INDEX，drill 直指該 atom 檔
    assert "_AIDocs/_atoms/Tools/gizmo-tool.md" in local
    # always-load 不攤每顆 caption（移至 drill 目標）
    assert "Gizmo 工具踩坑" not in local and "腦內世界X" not in local
    # core / feedback 不進側檔
    assert "core-note" not in local and "feedback-foo" not in local


# ─── 雙檔 round-trip：--check 對拍預渲染檔 → exit 0 / drift → exit 1 ──────────────


def _prerender(mem: Path, claude_root: Path, rows=ROWS) -> None:
    """以 MOD 渲染所有檔並落地（core + 側檔 + per-level _INDEX.md；對拍 main() 組裝）。"""
    core = MOD.render_core_section(rows, claude_root, {}) + "\n"
    local = MOD.render_local_catalog(rows, claude_root, {})
    (mem / "MEMORY.md").write_text(core, encoding="utf-8")
    if local:
        (mem / "_local_catalog.md").write_text(local + "\n", encoding="utf-8")
    for abs_path, content in MOD.collect_per_level_files(rows, claude_root, {}).items():
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content + "\n", encoding="utf-8")


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


# ─── 階層樹：per-level _INDEX.md 按需生成 + drill + round-trip + stale ────────────

DEEP_ROWS = [
    ("core-note", "memory/core-note.md", "global"),
    ("wsl-a", "_AIDocs/_atoms/OS/Windows/WSL/wsl-a.md", "global"),
    ("wsl-b", "_AIDocs/_atoms/OS/Windows/WSL/wsl-b.md", "global"),
    ("tool-1", "_AIDocs/_atoms/Tools/tool-1.md", "global"),
    ("tool-2", "_AIDocs/_atoms/Tools/tool-2.md", "global"),
    ("lone", "_AIDocs/_atoms/Loner/lone.md", "global"),
]


def test_catalog_deep_tree_lv1_counts_and_drill(tmp_path: Path):
    _build_memdir(tmp_path, DEEP_ROWS)
    local = MOD.render_local_catalog(DEEP_ROWS, tmp_path, {})
    assert "| OS | 2 | `_AIDocs/_atoms/OS/_INDEX.md` |" in local      # 有子層 → _INDEX
    assert "| Tools | 2 | `_AIDocs/_atoms/Tools/_INDEX.md` |" in local  # ≥2 → _INDEX
    assert "| Loner | 1 | `_AIDocs/_atoms/Loner/lone.md` |" in local    # 單葉 → 直指 atom


def test_per_level_index_generation_on_demand(tmp_path: Path):
    _build_memdir(tmp_path, DEEP_ROWS)
    files = MOD.collect_per_level_files(DEEP_ROWS, tmp_path, {})
    rels = {p.relative_to(tmp_path).as_posix() for p in files}
    # 生成：OS、OS/Windows、OS/Windows/WSL、Tools；不生：Loner（單葉雞肋）
    assert rels == {
        "_AIDocs/_atoms/OS/_INDEX.md",
        "_AIDocs/_atoms/OS/Windows/_INDEX.md",
        "_AIDocs/_atoms/OS/Windows/WSL/_INDEX.md",
        "_AIDocs/_atoms/Tools/_INDEX.md",
    }
    wsl_idx = next(c for p, c in files.items() if p.as_posix().endswith("WSL/_INDEX.md"))
    assert "| wsl-a |" in wsl_idx and "| wsl-b |" in wsl_idx        # 本層 atom
    os_idx = next(c for p, c in files.items() if p.as_posix().endswith("OS/_INDEX.md"))
    assert "## 子層" in os_idx and "| Windows | 2 |" in os_idx       # 直屬子層 + 遞迴計數


def test_deep_tree_roundtrip_no_drift(tmp_path: Path):
    mem = _build_memdir(tmp_path, DEEP_ROWS)
    _prerender(mem, tmp_path, DEEP_ROWS)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--memory-dir", str(mem)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"預期無 drift，stderr={r.stderr}"


def test_check_detects_stale_index(tmp_path: Path):
    mem = _build_memdir(tmp_path, DEEP_ROWS)
    _prerender(mem, tmp_path, DEEP_ROWS)
    # 製造 stale：多一個不該存在的 _INDEX.md
    bogus = tmp_path / "_AIDocs" / "_atoms" / "Ghost" / "_INDEX.md"
    bogus.parent.mkdir(parents=True, exist_ok=True)
    bogus.write_text("# 殘留\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--memory-dir", str(mem)],
        capture_output=True, text=True,
    )
    assert r.returncode == 1 and "stale _INDEX.md" in r.stderr
