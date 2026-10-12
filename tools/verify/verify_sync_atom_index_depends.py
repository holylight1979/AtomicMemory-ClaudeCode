"""verify_sync_atom_index_depends.py：sync-atom-index 的 Depends 欄同步（A3.3）。

正例：frontmatter 有 `- Depends:` 而索引沒有 → depends_drift；`--sync-depends` 後零漂移；
反例：存量（frontmatter 沒有 Depends 行）不報漂移，索引殘值也不被 --sync-depends 動；--add-from-frontmatter 連 depends 一起登。
CLI 以 subprocess 跑 `--memory-dir <tmp>`，不碰 live 索引。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_sync_atom_index_depends.py
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(CLAUDE_ROOT) not in sys.path:
    sys.path.insert(0, str(CLAUDE_ROOT))

from lib.atom_index_json import load_atom_index_json, upsert_atom  # noqa: E402

SYNC = CLAUDE_ROOT / "tools" / "sync-atom-index.py"


def _load_sync():
    spec = importlib.util.spec_from_file_location("sync_atom_index_deps_ut", SYNC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod  # dataclass 需要 sys.modules 能找到定義模組
    spec.loader.exec_module(mod)
    return mod


def _card(title: str, depends: str = "") -> str:
    dep_line = f"- Depends: {depends}\n" if depends else ""
    return (f"# {title}\n\n- Scope: shared\n- Confidence: [臨]\n- Trigger: {title}, t2, t3\n"
            f"- Created-at: 2026-10-01\n{dep_line}\n## 知識\n\n- [臨] k\n\n## 行動\n\n- a\n")


@pytest.fixture
def world(tmp_path):
    """專案記憶層：<root>/.claude/memory/shared/排程/*.md；索引在 <root>/.claude/memory/_atom_index.json。"""
    root = tmp_path / "proj"
    mem = root / ".claude" / "memory"
    cat = mem / "shared" / "排程"
    cat.mkdir(parents=True)
    (cat / "有依賴卡.md").write_text(_card("有依賴卡", "path:src/sched/queue.py, decision:abc"), encoding="utf-8")
    (cat / "存量卡.md").write_text(_card("存量卡"), encoding="utf-8")
    upsert_atom(mem, "有依賴卡", "memory/shared/排程/有依賴卡.md", ["有依賴卡", "t2", "t3"], "shared")   # 索引沒有 depends
    upsert_atom(mem, "存量卡", "memory/shared/排程/存量卡.md", ["存量卡", "t2", "t3"], "shared")
    return root, mem


def test_frontmatter_depends_missing_in_index_is_drift_and_sync_fixes_it(world):
    root, mem = world
    sync = _load_sync()
    atoms = sync.scan_atom_files(mem, mem.parent)
    rows = sync.load_index_rows(mem)
    rep = sync.detect_drift(atoms, rows, mem.parent)
    assert [d["atom"] for d in rep.depends_drift] == ["有依賴卡"]
    assert rep.depends_drift[0]["frontmatter"] == ["path:src/sched/queue.py", "decision:abc"] and rep.depends_drift[0]["index"] == []
    assert rep.has_drift() and rep.to_dict()["depends_drift"]
    changed = sync.sync_depends_from_frontmatter(atoms, rows, mem)
    assert changed == ["有依賴卡"]
    rows = sync.load_index_rows(mem)
    rep = sync.detect_drift(atoms, rows, mem.parent)
    assert rep.depends_drift == [] and not rep.has_drift()
    entry = next(a for a in load_atom_index_json(mem)["atoms"] if a["name"] == "有依賴卡")
    assert entry["depends"] == ["path:src/sched/queue.py", "decision:abc"]
    # 再同步一次 → 無事
    assert sync.sync_depends_from_frontmatter(atoms, rows, mem) == []


def test_stock_atoms_without_depends_line_never_reported(world):
    root, mem = world
    sync = _load_sync()
    # 存量卡沒有 Depends 行；就算索引被旁路塞了殘值，也不算漂移、--sync-depends 不碰
    upsert_atom(mem, "存量卡", "memory/shared/排程/存量卡.md", ["存量卡", "t2", "t3"], "shared", depends=["path:old.py"])
    atoms = sync.scan_atom_files(mem, mem.parent)
    assert atoms["memory/shared/排程/存量卡.md"].depends is None
    rows = sync.load_index_rows(mem)
    rep = sync.detect_drift(atoms, rows, mem.parent)
    assert [d["atom"] for d in rep.depends_drift] == ["有依賴卡"]          # 只有真的有行的那張
    sync.sync_depends_from_frontmatter(atoms, rows, mem)
    entry = next(a for a in load_atom_index_json(mem)["atoms"] if a["name"] == "存量卡")
    assert entry["depends"] == ["path:old.py"]


def test_cli_check_then_sync_depends_then_check_clean(world):
    root, mem = world
    env_cmd = [sys.executable, "-X", "utf8", str(SYNC), "--memory-dir", str(mem)]
    r = subprocess.run(env_cmd + ["--check"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1 and "depends_drift" in r.stderr and "有依賴卡" in r.stderr
    r = subprocess.run(env_cmd + ["--sync-depends"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert any("depends synced" in a for a in out["actions"]) and out["drift"]["depends_drift"] == []
    r = subprocess.run(env_cmd + ["--check"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr


def test_add_from_frontmatter_carries_depends(world):
    root, mem = world
    sync = _load_sync()
    cat = mem / "shared" / "排程"
    (cat / "新卡.md").write_text(_card("新卡", "path:src/sched/legacy"), encoding="utf-8")
    atoms = sync.scan_atom_files(mem, mem.parent)
    rows = sync.load_index_rows(mem)
    assert sync.add_to_index_from_frontmatter(atoms, rows, mem) == ["新卡"]
    entry = next(a for a in load_atom_index_json(mem)["atoms"] if a["name"] == "新卡")
    assert entry["depends"] == ["path:src/sched/legacy"]
    assert sync.parse_frontmatter_depends("- Depends: a， b, a\n") == ["a", "b"]
    assert sync.parse_frontmatter_depends("# x\n- Trigger: t\n") is None
