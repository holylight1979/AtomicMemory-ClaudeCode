"""verify_project_layer_smoke.py — 專案層（<proj>/.claude/memory/）不受核心層範疇資料夾規則波及的 smoke。

核心層改用 memory/<範疇>/… 與 memory/Failures/<主題>/ 後，專案層記憶樹（shared/ 扁平或
shared/<domain>/）必須照舊：路徑判定、failures 落點、注入閘門、索引同步四條純函式通道
在 tmp 假專案上實跑，不碰現役 memory/。

計畫案例對照：
  - 案例 1（專案層路徑判定與 failures 落點）：本檔 test_case1_*
  - 案例 5（sync-memory-index --check 對專案層索引不炸）：本檔 test_case5_*
  - 案例 2（專案層 atom_write 走 shared/ 不被核心閘拒寫）、案例 3（專案層 catalog 渲染）、
    案例 4（跨層 up-ref 解析）：待閘門啟用（taxonomy.gate_enabled=true）後補。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest  # noqa: F401

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude
for _p in (CLAUDE_DIR / "hooks", CLAUDE_DIR / "lib", CLAUDE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from wg_core import (  # noqa: E402
    _is_under_claude_dir, get_project_memory_dir, resolve_failures_dir,
    is_local_realm_path as _wg_is_local_realm_path, is_cross_project_local,
)
from lib.atom_locations import (  # noqa: E402
    FAILURES_DIR, is_in_failures_path, is_local_realm_path,
)

SYNC_MEMORY_INDEX = CLAUDE_DIR / "tools" / "sync-memory-index.py"


@pytest.fixture
def proj(tmp_path) -> Path:
    """<tmp>/proj/.claude/memory/{MEMORY.md,_atom_index.json,shared/}：最小專案層記憶樹。"""
    root = tmp_path / "proj"
    mem = root / ".claude" / "memory"
    (mem / "shared").mkdir(parents=True)
    (mem / "MEMORY.md").write_text("# Atom Index — Project\n\n| Atom | 說明 |\n|------|------|\n",
                                   encoding="utf-8")
    atoms = []
    for slug, sub in (("proj-rule-a", ""), ("proj-rule-b", "Domain")):
        d = mem / "shared" / sub if sub else mem / "shared"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{slug}.md").write_text(
            f"# {slug}\n\n- Confidence: [臨]\n- Trigger: {slug}\n\n## 知識\n\n- [臨] x\n",
            encoding="utf-8")
        rel = f"memory/shared/{sub + '/' if sub else ''}{slug}.md"
        atoms.append({"name": slug, "path": rel, "triggers": [slug], "scope": "shared"})
    (mem / "_atom_index.json").write_text(
        json.dumps({"version": "1.0", "atoms": atoms}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return root


# ─── 案例 1：專案層路徑判定與 failures 落點 ──────────────────────────────────


def test_case1_under_claude_dir_predicate(proj):
    assert _is_under_claude_dir(str(proj)) is False
    assert _is_under_claude_dir(str(CLAUDE_DIR)) is True


def test_case1_project_memory_dir_and_failures_dir(proj, tmp_path):
    mem = proj / ".claude" / "memory"
    assert get_project_memory_dir(str(proj)) == mem
    # 專案層 failures 落 <proj>/.claude/memory/failures（小寫，wg_core 現行行為；mkdir 副作用在 tmp）
    fd = resolve_failures_dir(str(proj))
    assert fd == mem / "failures"
    assert fd.is_dir()
    # 非專案 cwd → 全域 memory/Failures
    outside = tmp_path / "outside"
    outside.mkdir()
    assert resolve_failures_dir(str(outside)) == FAILURES_DIR
    assert resolve_failures_dir(r"C:\Windows\Temp") == FAILURES_DIR
    assert FAILURES_DIR == CLAUDE_DIR / "memory" / "Failures"
    # cwd 在 ~/.claude 本身（get_project_memory_dir 回根層 memory/）→ 也必須落全域家族目錄，
    # 不得走專案佈局長出小寫 memory/failures/（本 session 背景失敗萃取曾因此重生舊址）。
    assert resolve_failures_dir(str(CLAUDE_DIR)) == FAILURES_DIR
    assert resolve_failures_dir(str(CLAUDE_DIR / "tools")) == FAILURES_DIR
    assert not (CLAUDE_DIR / "memory" / "failures").exists() or \
        (CLAUDE_DIR / "memory" / "failures").resolve().name == "Failures"


# ─── 案例 1（續）：路徑前綴判定 + 注入閘門純函式 ──────────────────────────────


def _apply_gate(atoms, cwd):
    """對拍 lib/verify/verify_realm_injection_gate.py 的 _apply_gate（session_start 過濾邏輯）。"""
    if _wg_is_local_realm_path is not None and not _is_under_claude_dir(cwd):
        return [(n, p, t) for (n, p, t) in atoms
                if not _wg_is_local_realm_path(p) or is_cross_project_local(p)]
    return list(atoms)


def test_case1_path_predicates():
    assert is_local_realm_path("_AIDocs/_atoms/MemDev/x.md") is True
    assert is_in_failures_path("memory/Failures/驗證與實證/feedback-x.md") is True
    assert is_in_failures_path("_AIDocs/Failures/feedback-x.md") is True
    assert is_in_failures_path("memory/版控/Git/x.md") is False
    assert is_local_realm_path("memory/Failures/x/feedback-x.md") is False


def test_case1_injection_gate_from_project_keeps_core_category_atoms(proj):
    atoms = [
        ("decisions", "memory/decisions.md", ["決策"]),
        ("feedback-x", "memory/Failures/驗證與實證/feedback-x.md", ["驗證"]),
        ("feedback-legacy", "_AIDocs/Failures/feedback-legacy.md", ["舊址"]),
        ("git-hunk", "memory/版控/Git/git-hunk.md", ["hunk"]),
        ("brain", "_AIDocs/_atoms/MemDev/brain.md", ["腦內世界"]),
        ("handoff-q", "_AIDocs/_atoms/Continuity/handoff-q.md", ["handoff"]),
    ]
    names = {n for n, _, _ in _apply_gate(atoms, str(proj))}
    assert names == {"decisions", "feedback-x", "feedback-legacy", "git-hunk", "handoff-q"}
    # 核心環境不濾
    assert {n for n, _, _ in _apply_gate(atoms, str(CLAUDE_DIR))} == {n for n, _, _ in atoms}


# ─── 案例 5：sync-memory-index --check 對專案層索引 ───────────────────────────


def test_case5_sync_memory_index_check_no_traceback(proj):
    mem = proj / ".claude" / "memory"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(
        [sys.executable, str(SYNC_MEMORY_INDEX), "--check", "--memory-dir", str(mem)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=120,
    )
    assert r.returncode in (0, 1), (r.returncode, r.stdout, r.stderr)
    assert "Traceback" not in r.stderr, r.stderr
    assert "Traceback" not in r.stdout, r.stdout
    # --check 不得寫檔：MEMORY.md 原樣
    assert (mem / "MEMORY.md").read_text(encoding="utf-8").startswith("# Atom Index — Project")
