"""verify_local_catalog_split.py — realm 拆分 catalog + 核心區兩種渲染（平鋪／範疇表）

acceptance：
  - render_core_section（= @import 的 MEMORY.md，外部專案所見 catalog）**不含**本地範疇
    atom / `## 本地範疇` 標題，**仍含** core + feedback-* → 模擬外部專案候選不含本地範疇。
  - render_local_catalog（= 側檔 _local_catalog.md，僅核心環境 hook 注入）**含**本地 atom
    依 domain 分組。
  - main() 多檔 round-trip：`--check` 對拍預渲染檔 exit 0（不觸發 write_index_full → 零 audit
    log 污染；真實 repo 的 --write+--check 在驗收步驟跑）。
  - 階層模式（`--hierarchical`）：memory/<Lv1> 一列一範疇、Failures 亦為一列、無 atom caption；
    per-level _INDEX.md 走兩根；memory/ 根下平鋪 atom → `--check` exit 1、`--write` 拒。

模式一律顯式指定（`hierarchical=False` / `--legacy`、`hierarchical=True` / `--hierarchical`），
不依賴 live config 的 gate 值。
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
    mem.mkdir(exist_ok=True)
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
    core = MOD.render_core_section(ROWS, tmp_path, {}, hierarchical=False)
    # core：含核心 atom + feedback-* 聚合行（atom 仍在舊址 → 指標指舊址）
    assert "| core-note | 核心筆記 |" in core
    assert "| decisions | 全域決策 |" in core
    assert "| feedback-* | 行為校正（1 atoms） → [`_AIDocs/Failures/`](../_AIDocs/Failures/) |" in core
    # core：不含本地範疇 atom / 標題（外部專案零本地負擔）
    assert "## 本地範疇" not in core
    for nm in LOCAL_NAMES:
        assert nm not in core, f"local atom {nm} 不該出現在 core catalog"
    # core：保留指標供 discoverability
    assert "_local_catalog.md" in core


def test_flat_feedback_pointer_follows_new_home_after_migration(tmp_path: Path):
    """feedback-* 一旦有任何一顆搬進 memory/Failures/，平鋪聚合列指標改指新址。"""
    rows = ROWS + [("feedback-bar", "memory/Failures/工作流/feedback-bar.md", "global")]
    _build_memdir(tmp_path, rows)
    core = MOD.render_core_section(rows, tmp_path, {}, hierarchical=False)
    assert "| feedback-* | 行為校正（2 atoms） → [`memory/Failures/`](../memory/Failures/) |" in core


def test_local_catalog_shows_lv1_roots_only(tmp_path: Path):
    """側檔只列 Lv1 根 + 遞迴計數 + drill 指標（不攤每顆 atom caption）。"""
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


# ─── 多檔 round-trip：--check 對拍預渲染檔 → exit 0 / drift → exit 1 ──────────────


def _prerender(mem: Path, claude_root: Path, rows=ROWS, hierarchical: bool = False) -> None:
    """以 MOD 渲染所有檔並落地（core + 側檔 + per-level _INDEX.md；對拍 main() 組裝）。"""
    core = MOD.render_core_section(rows, claude_root, {}, hierarchical=hierarchical) + "\n"
    local = MOD.render_local_catalog(rows, claude_root, {})
    (mem / "MEMORY.md").write_text(core, encoding="utf-8")
    if local:
        (mem / "_local_catalog.md").write_text(local + "\n", encoding="utf-8")
    files = MOD.collect_per_level_files(rows, claude_root, {}, hierarchical=hierarchical)
    for abs_path, content in files.items():
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content + "\n", encoding="utf-8")


def _run(mem: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *flags, "--memory-dir", str(mem)],
        capture_output=True, text=True, encoding="utf-8",
    )


def _run_check(mem: Path, mode: str = "--legacy") -> subprocess.CompletedProcess:
    return _run(mem, "--check", mode)


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
    files = MOD.collect_per_level_files(DEEP_ROWS, tmp_path, {}, hierarchical=False)
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
    assert "階層 local 範疇索引" in os_idx                            # 平鋪期文案不變（live 不 drift）


def test_deep_tree_roundtrip_no_drift(tmp_path: Path):
    mem = _build_memdir(tmp_path, DEEP_ROWS)
    _prerender(mem, tmp_path, DEEP_ROWS)
    r = _run_check(mem)
    assert r.returncode == 0, f"預期無 drift，stderr={r.stderr}"


def test_check_detects_stale_index(tmp_path: Path):
    mem = _build_memdir(tmp_path, DEEP_ROWS)
    _prerender(mem, tmp_path, DEEP_ROWS)
    # 製造 stale：多一個不該存在的 _INDEX.md
    bogus = tmp_path / "_AIDocs" / "_atoms" / "Ghost" / "_INDEX.md"
    bogus.parent.mkdir(parents=True, exist_ok=True)
    bogus.write_text("# 殘留\n", encoding="utf-8")
    r = _run_check(mem)
    assert r.returncode == 1 and "stale _INDEX.md" in r.stderr


# ─── 階層模式：核心區範疇表 + 兩根 _INDEX.md + 平鋪硬規則 ──────────────────────────

HIER_ROWS = [
    ("a", "memory/版控/Git/a.md", "global"),
    ("b", "memory/版控/SVN/b.md", "global"),
    ("c", "memory/工作流/c.md", "global"),
    ("feedback-d", "memory/Failures/驗證與實證/feedback-d.md", "global"),
    ("t", "_AIDocs/_atoms/Tools/t.md", "global"),
]


def test_hierarchical_core_section_lv1_rows(tmp_path: Path):
    _build_memdir(tmp_path, HIER_ROWS)
    core = MOD.render_core_section(HIER_ROWS, tmp_path, {}, hierarchical=True)
    assert core.startswith("# Atom Index — Global\n")
    assert "| 範疇 | atom 數 | 深入 |" in core
    assert "| 版控 | 2 | `memory/版控/_INDEX.md` |" in core          # 有子層 → _INDEX
    assert "| 工作流 | 1 | `memory/工作流/c.md` |" in core            # 單葉 → 直指 atom
    assert "| Failures | 1 | `memory/Failures/_INDEX.md` |" in core  # 有主題子層 → _INDEX
    # taxonomy 宣告序在前：版控 → 工作流；Failures（非核心 Lv1）接後
    assert core.index("| 版控 |") < core.index("| 工作流 |") < core.index("| Failures |")
    # 無 atom caption 列、無未分類表、local 指標仍在
    assert "| a |" not in core and "| c |" not in core and "feedback-d" not in core
    assert "未分類" not in core
    assert MOD.LOCAL_CATALOG_POINTER in core
    assert len(core.splitlines()) <= 25


def test_hierarchical_failures_all_legacy_drills_old_index(tmp_path: Path):
    """feedback 全在舊址 → Failures 列仍出現，深入指手寫的 _AIDocs/Failures/_INDEX.md。"""
    _build_memdir(tmp_path)  # ROWS：feedback-foo 在 _AIDocs/Failures/；core-note/decisions 平鋪
    core = MOD.render_core_section(ROWS, tmp_path, {}, hierarchical=True)
    assert "| Failures | 1 | `_AIDocs/Failures/_INDEX.md` |" in core
    assert "core-note" not in core  # 平鋪 atom 不進表（由硬規則另行報錯）


def test_hierarchical_per_level_index_both_roots(tmp_path: Path):
    _build_memdir(tmp_path, HIER_ROWS)
    files = MOD.collect_per_level_files(HIER_ROWS, tmp_path, {}, hierarchical=True)
    rels = {p.relative_to(tmp_path).as_posix() for p in files}
    assert rels == {"memory/版控/_INDEX.md", "memory/Failures/_INDEX.md"}
    vcs = files[tmp_path / "memory" / "版控" / "_INDEX.md"]
    assert "# memory/版控 — 範疇索引" in vcs
    assert "| Git | 1 | `memory/版控/Git/a.md` |" in vcs and "| SVN | 1 | `memory/版控/SVN/b.md` |" in vcs
    assert "local" not in vcs                                          # 文案去 local 化
    fail = files[tmp_path / "memory" / "Failures" / "_INDEX.md"]
    assert "| 驗證與實證 | 1 | `memory/Failures/驗證與實證/feedback-d.md` |" in fail


def test_hierarchical_never_generates_memory_root_index(tmp_path: Path):
    _build_memdir(tmp_path, HIER_ROWS)
    files = MOD.collect_per_level_files(HIER_ROWS, tmp_path, {}, hierarchical=True)
    assert (tmp_path / "memory" / "_INDEX.md") not in files


def test_hierarchical_roundtrip_no_drift(tmp_path: Path):
    mem = _build_memdir(tmp_path, HIER_ROWS)
    _prerender(mem, tmp_path, HIER_ROWS, hierarchical=True)
    # 非範疇資料夾裡的 _INDEX.md（_reference/）不歸本工具管 → 不算 stale；
    # 範疇資料夾底下的 `_` 前綴子夾（Failures/_reference/ 參考文件索引）同樣豁免
    for ref in (mem / "_reference" / "_INDEX.md", mem / "Failures" / "_reference" / "_INDEX.md"):
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_text("# 手寫參考\n", encoding="utf-8")
    r = _run_check(mem, "--hierarchical")
    assert r.returncode == 0, f"預期無 drift，stderr={r.stderr}"
    assert len((mem / "MEMORY.md").read_text(encoding="utf-8").splitlines()) <= 25


def test_hierarchical_check_detects_stale_core_index(tmp_path: Path):
    mem = _build_memdir(tmp_path, HIER_ROWS)
    _prerender(mem, tmp_path, HIER_ROWS, hierarchical=True)
    bogus = mem / "工作流" / "_INDEX.md"  # 單葉層不該有 _INDEX
    bogus.write_text("# 殘留\n", encoding="utf-8")
    r = _run_check(mem, "--hierarchical")
    assert r.returncode == 1 and "stale _INDEX.md" in r.stderr


def test_hierarchical_flat_atom_hard_rule(tmp_path: Path):
    rows = HIER_ROWS + [("loose", "memory/loose.md", "global")]
    mem = _build_memdir(tmp_path, rows)
    _prerender(mem, tmp_path, rows, hierarchical=True)
    # --check：逐顆印出並 exit 1
    r = _run_check(mem, "--hierarchical")
    assert r.returncode == 1
    assert "[sync-memory-index] flat atom under memory/: loose" in r.stderr
    # --write：拒寫（MEMORY.md 原樣）
    before = (mem / "MEMORY.md").read_text(encoding="utf-8")
    w = _run(mem, "--write", "--hierarchical")
    assert w.returncode == 1 and "refuse to write" in w.stderr
    assert (mem / "MEMORY.md").read_text(encoding="utf-8") == before
    # dry-run：警告但不 crash，主表照印
    d = _run(mem, "--hierarchical")
    assert d.returncode == 0 and "flat atom under memory/: loose" in d.stderr
    assert "| 範疇 | atom 數 | 深入 |" in d.stdout


def test_legacy_mode_ignores_flat_rule(tmp_path: Path):
    """平鋪期（--legacy）memory/ 根下 atom 是常態，不報硬規則。"""
    mem = _build_memdir(tmp_path)
    _prerender(mem, tmp_path)
    r = _run_check(mem, "--legacy")
    assert r.returncode == 0 and "flat atom" not in r.stderr
