"""verify_index_scope_repair.py — 索引 scope 欄的單一真相是 path。

- lib.atom_locations.scope_from_index_path：personal/<u>/、personal/auto/<u>/、roles/<r>/、其餘依層
- lib.atom_io.write_index：新條目缺省 scope 由 path 推導（不再預設 global）
- tools/sync-atom-index.py --fix-scope-from-path：存量 scope 回寫 + 懸空條目刪除 + .md Scope 標頭對齊
- hooks/wg_atoms.scope_from_rel_path 委派同一把（讀取端／寫入端同規則）
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_ROOT = HOOKS_DIR.parent
for p in (HOOKS_DIR, CLAUDE_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from lib.atom_locations import scope_from_index_path  # noqa: E402
from lib.atom_index_json import load_atom_index_json, upsert_atom  # noqa: E402


def test_scope_from_index_path_single_source():
    from wg_atoms import scope_from_rel_path
    cases = {
        "memory/personal/holylight/x.md": "personal:holylight",
        "memory/personal/auto/holylight/x.md": "personal:holylight",
        "memory/roles/dev/x.md": "role:dev",
        "memory/shared/A/x.md": "shared",
        "memory/x.md": "shared",
    }
    for rel, exp in cases.items():
        assert scope_from_index_path(rel) == exp
        assert scope_from_rel_path(rel) == exp  # 讀取端委派同一把
    assert scope_from_index_path("工作流/x.md", "global") == "global"
    assert scope_from_index_path("memory/personal/holylight/x.md", "global") == "personal:holylight"


def test_write_index_defaults_scope_from_path(tmp_path):
    from lib import atom_io
    mem = tmp_path / "proj" / ".claude" / "memory"
    mem.mkdir(parents=True)
    (mem / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": []}), encoding="utf-8")
    r1 = atom_io.write_index(mem, "p1", "memory/personal/holylight/p1.md", ["a"], source="hook:user-extract")
    r2 = atom_io.write_index(mem, "s1", "memory/shared/X/s1.md", ["a"], source="hook:user-extract")
    r3 = atom_io.write_index(mem, "r1", "memory/roles/dev/r1.md", ["a"], source="hook:user-extract")
    assert r1.ok and r2.ok and r3.ok, (r1.error, r2.error, r3.error)
    scopes = {a["name"]: a["scope"] for a in load_atom_index_json(mem)["atoms"]}
    assert scopes == {"p1": "personal:holylight", "s1": "shared", "r1": "role:dev"}
    # 明給仍以明給為準；既有條目缺省沿用既有值
    atom_io.write_index(mem, "s1", "memory/shared/X/s1.md", ["b"], source="hook:user-extract", scope="shared")
    atom_io.write_index(mem, "p1", "memory/personal/holylight/p1.md", ["c"], source="hook:user-extract")
    scopes = {a["name"]: a["scope"] for a in load_atom_index_json(mem)["atoms"]}
    assert scopes["p1"] == "personal:holylight" and scopes["s1"] == "shared"


def _load_sync():
    path = CLAUDE_ROOT / "tools" / "sync-atom-index.py"
    spec = importlib.util.spec_from_file_location("sync_atom_index_ut", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclass 需要 sys.modules 能找到定義模組
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_fix_scope_from_path_repairs_and_prunes(tmp_path):
    sync = _load_sync()
    root = tmp_path / "proj" / ".claude"
    mem = root / "memory"
    (mem / "personal" / "holylight").mkdir(parents=True)
    (mem / "shared").mkdir()
    (mem / "personal" / "holylight" / "p.md").write_text(
        "# p\n\n- Scope: global\n- Trigger: a\n\n## 知識\n\n- x\n", encoding="utf-8")
    (mem / "shared" / "s.md").write_text(
        "# s\n\n- Scope: project\n- Trigger: a\n\n## 知識\n\n- x\n", encoding="utf-8")
    (mem / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": []}), encoding="utf-8")
    upsert_atom(mem, "p", "memory/personal/holylight/p.md", ["a"], scope="global")     # 錯標
    upsert_atom(mem, "s", "memory/shared/s.md", ["a"], scope="project")                # legacy
    upsert_atom(mem, "ghost", "memory/shared/ghost.md", ["a"], scope="shared")         # 懸空
    # 搬了位置但索引 path 沒跟上的：修 path、不當懸空刪
    (mem / "shared" / "Sub").mkdir()
    (mem / "shared" / "Sub" / "moved.md").write_text(
        "# moved\n\n- Scope: shared\n- Trigger: a\n\n## 知識\n\n- x\n", encoding="utf-8")
    upsert_atom(mem, "moved", "memory/shared/moved.md", ["a"], scope="shared")
    rows = sync.load_index_rows(mem)
    res = sync.fix_index_scope_from_path(mem, root, rows)
    assert res["dangling_removed"] == ["ghost"]
    assert res["path_repaired"] == ["moved: memory/shared/moved.md -> memory/shared/Sub/moved.md"]
    assert sorted(res["scope_fixed"]) == ["p: global -> personal:holylight", "s: project -> shared"]
    entries = {a["name"]: a for a in load_atom_index_json(mem)["atoms"]}
    assert {n: e["scope"] for n, e in entries.items()} == {"p": "personal:holylight", "s": "shared", "moved": "shared"}
    assert entries["moved"]["path"] == "memory/shared/Sub/moved.md"
    assert "- Scope: personal:holylight" in (mem / "personal" / "holylight" / "p.md").read_text(encoding="utf-8")
    assert "- Scope: shared" in (mem / "shared" / "s.md").read_text(encoding="utf-8")
    # 冪等
    res2 = sync.fix_index_scope_from_path(mem, root, sync.load_index_rows(mem))
    assert res2 == {"dangling_removed": [], "scope_fixed": [], "path_repaired": []}
    # 專案層掃描套 is_atom_file：_rejected/ 與 personal/auto/ 不算缺索引
    (mem / "_rejected").mkdir()
    (mem / "_rejected" / "old.md").write_text("# old\n\n- Trigger: a\n", encoding="utf-8")
    (mem / "personal" / "auto" / "holylight").mkdir(parents=True)
    (mem / "personal" / "auto" / "holylight" / "cand.md").write_text("# c\n\n- Trigger: a\n", encoding="utf-8")
    rep = sync.detect_drift(sync.scan_atom_files(mem, root), sync.load_index_rows(mem), root)
    assert not rep.missing_in_index


def test_all_projects_sweeps_every_registered_dir(tmp_path, monkeypatch):
    """--all-projects：從 ~/.claude 一鍵掃全部登記專案，不必逐專案開 session 叫 CC 整理。"""
    import argparse
    import wg_core
    sync = _load_sync()
    mems = []
    for name in ("pa", "pb"):
        root = tmp_path / name / ".claude"
        mem = root / "memory"
        (mem / "shared").mkdir(parents=True)
        (mem / "shared" / "s.md").write_text("# s\n\n- Scope: project\n- Trigger: a\n\n## 知識\n\n- x\n", encoding="utf-8")
        (mem / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": []}), encoding="utf-8")
        upsert_atom(mem, "s", "memory/shared/s.md", ["a"], scope="project")
        mems.append((name, mem))
    monkeypatch.setattr(wg_core, "discover_all_project_memory_dirs", lambda: list(mems))
    args = argparse.Namespace(check=False, fix=False, add_from_frontmatter=False, fix_scope_from_path=True)
    rc = sync._run_all_projects(args)
    assert rc == 0
    for _name, mem in mems:
        assert {a["scope"] for a in load_atom_index_json(mem)["atoms"]} == {"shared"}
    # check 模式：全乾淨 → 0
    args2 = argparse.Namespace(check=True, fix=False, add_from_frontmatter=False, fix_scope_from_path=False)
    assert sync._run_all_projects(args2) == 0
