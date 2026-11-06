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


@pytest.mark.parametrize("tail", ["\n- Trigger: x\n", "\n\n## 知識\n\n- k\n", ""])
def test_empty_depends_line_is_clear_not_next_line(world, tail):          # 退件 BLOCK 2
    root, mem = world
    sync = _load_sync()
    assert sync.parse_frontmatter_depends("# t\n- Depends:" + tail) == []
    assert sync.parse_frontmatter_depends("# t\n- Depends:   " + tail) == []
    # 索引有殘值、frontmatter 改成空行 → 漂移；--sync-depends 後索引鍵消失
    card = mem / "shared" / "排程" / "有依賴卡.md"
    text = card.read_text(encoding="utf-8").replace("- Depends: path:src/sched/queue.py, decision:abc\n", "- Depends:" + tail)
    if not tail:   # 檔尾情境：把 Depends 行搬到最後一行
        text = card.read_text(encoding="utf-8").replace("- Depends: path:src/sched/queue.py, decision:abc\n", "") + "- Depends:"
    card.write_text(text, encoding="utf-8")
    upsert_atom(mem, "有依賴卡", "memory/shared/排程/有依賴卡.md", ["有依賴卡", "t2", "t3"], "shared", depends=["path:old.py"])
    atoms = sync.scan_atom_files(mem, mem.parent)
    assert atoms["memory/shared/排程/有依賴卡.md"].depends == []
    rows = sync.load_index_rows(mem)
    rep = sync.detect_drift(atoms, rows, mem.parent)
    assert [d["atom"] for d in rep.depends_drift] == ["有依賴卡"]
    assert sync.sync_depends_from_frontmatter(atoms, rows, mem) == ["有依賴卡"]
    entry = next(a for a in load_atom_index_json(mem)["atoms"] if a["name"] == "有依賴卡")
    assert "depends" not in entry
    assert sync.detect_drift(atoms, sync.load_index_rows(mem), mem.parent).depends_drift == []


def test_atom_io_replace_reads_empty_depends_line_as_clear():              # 同一個 \s* 跨行坑在 atom_io／atom_io_cli
    import re
    src_io = (CLAUDE_ROOT / "lib" / "atom_io.py").read_text(encoding="utf-8")
    src_cli = (CLAUDE_ROOT / "lib" / "atom_io_cli.py").read_text(encoding="utf-8")
    assert r'^- Depends:\s*(.+)$' not in src_io and r'^- Depends:\s*(.+)$' not in src_cli
    from lib.atom_io_cli import _depends_of
    assert _depends_of("# t\n- Depends:\n- Related: r\n") == []
    assert _depends_of("# t\n- Depends: path:a.py， path:b.py\n") == ["path:a.py", "path:b.py"]
    assert re.search(r"^- Depends:[ \t]*(.*)$", "- Depends:\n- Trigger: x", re.MULTILINE).group(1) == ""


def _rebuild_entries(sync, mem) -> dict:
    atoms = sync.scan_atom_files(mem, mem.parent)
    sync.rebuild_index(mem, mem.parent, atoms)
    return {a["name"]: a for a in load_atom_index_json(mem)["atoms"]}


def test_rebuild_writes_depends_from_frontmatter(world):
    """卡片有 Depends 行：重建後索引照卡片寫，而且零漂移（開 session 的過期重建不能讓索引忽有忽無）。"""
    root, mem = world
    sync = _load_sync()
    entries = _rebuild_entries(sync, mem)
    assert entries["有依賴卡"]["depends"] == ["path:src/sched/queue.py", "decision:abc"]
    assert "depends" not in entries["存量卡"]                                # 兩邊都沒有：不憑空多一個鍵
    assert sync.detect_drift(sync.scan_atom_files(mem, mem.parent), sync.load_index_rows(mem), mem.parent).depends_drift == []
    assert _rebuild_entries(sync, mem) == entries                            # 再重建一次不變


def test_rebuild_frontmatter_beats_stale_index_value(world):
    root, mem = world
    sync = _load_sync()
    upsert_atom(mem, "有依賴卡", "memory/shared/排程/有依賴卡.md", ["有依賴卡", "t2", "t3"], "shared", depends=["path:old.py"])
    assert _rebuild_entries(sync, mem)["有依賴卡"]["depends"] == ["path:src/sched/queue.py", "decision:abc"]


def test_rebuild_keeps_index_depends_when_card_has_no_line(world):
    """沒有 Depends 行＝存量：卡片沒表態，舊索引的值留著（與 --sync-depends「不碰」同語意；重建不是刪除的理由）。"""
    root, mem = world
    sync = _load_sync()
    upsert_atom(mem, "存量卡", "memory/shared/排程/存量卡.md", ["存量卡", "t2", "t3"], "shared", depends=["path:old.py"])
    entries = _rebuild_entries(sync, mem)
    assert entries["存量卡"]["depends"] == ["path:old.py"]
    assert _rebuild_entries(sync, mem) == entries


def test_rebuild_empty_depends_line_clears_index_value(world):
    """空的 Depends 行＝明講清空：重建後索引鍵消失（與 --sync-depends 同語意）。"""
    root, mem = world
    sync = _load_sync()
    card = mem / "shared" / "排程" / "存量卡.md"
    card.write_text(card.read_text(encoding="utf-8").replace("- Created-at", "- Depends:\n- Created-at"), encoding="utf-8")
    upsert_atom(mem, "存量卡", "memory/shared/排程/存量卡.md", ["存量卡", "t2", "t3"], "shared", depends=["path:old.py"])
    assert "depends" not in _rebuild_entries(sync, mem)["存量卡"]


def test_rebuild_via_cli_keeps_depends(world):
    """開 session 的過期重建實際走的路：CLI --rebuild（session_start._rebuild_index_if_missing）。"""
    root, mem = world
    upsert_atom(mem, "存量卡", "memory/shared/排程/存量卡.md", ["存量卡", "t2", "t3"], "shared", depends=["path:old.py"])
    r = subprocess.run([sys.executable, "-X", "utf8", str(SYNC), "--memory-dir", str(mem), "--rebuild"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    entries = {a["name"]: a for a in load_atom_index_json(mem)["atoms"]}
    assert entries["有依賴卡"]["depends"] == ["path:src/sched/queue.py", "decision:abc"]
    assert entries["存量卡"]["depends"] == ["path:old.py"]
