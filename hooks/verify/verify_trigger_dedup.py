"""verify_trigger_dedup.py — trigger 清單大小寫重複不得灌水命中數。

背景：索引 triggers 同時含 "linemate" 與 "LineMate" 時，讀取側 .lower() 後變成兩顆
相同 trigger，count_trigger_hits 對單一「LineMate」字回 2，越過跨專案 >=2 門檻。

覆蓋：
- 讀取側 to_atom_entries / _parse_trigger_table：lowercase + strip + 保序去重
- count_trigger_hits 對去重後 triggers 只算 1
- 寫入側 upsert_atom 落檔前 case-insensitive 保序去重（首見者勝）
- tools/sync-atom-index 的 frontmatter / index 兩側同一把去重（不互報 drift）
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_ROOT = HOOKS_DIR.parent
for p in (HOOKS_DIR, HOOKS_DIR / "handlers", CLAUDE_ROOT, CLAUDE_ROOT / "lib"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import wg_atoms  # noqa: E402
from lib import atom_index_json  # noqa: E402


# ─── 讀取側 ────────────────────────────────────────────────────────────────

def test_to_atom_entries_dedups_case_insensitively():
    data = {"version": "1.0", "atoms": [{
        "name": "linemate-architecture", "path": "memory/x.md",
        "triggers": ["linemate", "LineMate", " LineMate "], "scope": "project",
    }]}
    entries = atom_index_json.to_atom_entries(data)
    assert entries == [("linemate-architecture", "memory/x.md", ["linemate"])]


def test_to_atom_entries_preserves_order_and_drops_blank():
    data = {"atoms": [{"name": "a", "path": "p", "triggers": ["Zeta", "", "alpha", "ZETA", "  "]}]}
    assert atom_index_json.to_atom_entries(data)[0][2] == ["zeta", "alpha"]


def test_parse_trigger_table_dedups():
    md = (
        "| Atom | Path | Trigger | Scope |\n"
        "|------|------|---------|-------|\n"
        "| linemate-architecture | memory/x.md | linemate, LineMate,  LineMate  , 架構 | project |\n"
    )
    atoms = wg_atoms._parse_trigger_table(md)
    assert atoms == [("linemate-architecture", "memory/x.md", ["linemate", "架構"])]


def test_count_trigger_hits_single_word_counts_once():
    data = {"atoms": [{"name": "linemate-architecture", "path": "p",
                       "triggers": ["linemate", "LineMate", " LineMate "]}]}
    _, _, triggers = atom_index_json.to_atom_entries(data)[0]
    assert wg_atoms.count_trigger_hits(triggers, "看一下 linemate".lower()) == 1
    assert wg_atoms.count_trigger_hits(triggers, "看一下 LineMate".lower()) == 1


# ─── 寫入側 ────────────────────────────────────────────────────────────────

def test_upsert_atom_writes_deduped_triggers(tmp_path):
    mem = tmp_path / "memory"
    ok = atom_index_json.upsert_atom(
        mem, "linemate-architecture", "memory/x.md",
        ["linemate", "LineMate", " LineMate ", "架構", "架構"], scope="project",
    )
    assert ok
    saved = json.loads((mem / atom_index_json.ATOM_INDEX_JSON).read_text(encoding="utf-8"))
    triggers = saved["atoms"][0]["triggers"]
    assert triggers == ["linemate", "架構"], triggers
    lowered = [t.lower() for t in triggers]
    assert len(lowered) == len(set(lowered)), "索引檔 triggers 不得有大小寫重複"


def test_upsert_atom_keeps_first_seen_case(tmp_path):
    mem = tmp_path / "memory"
    atom_index_json.upsert_atom(mem, "a", "memory/a.md", ["LineMate", "linemate"])
    saved = json.loads((mem / atom_index_json.ATOM_INDEX_JSON).read_text(encoding="utf-8"))
    assert saved["atoms"][0]["triggers"] == ["LineMate"]


def test_parse_legacy_md_dedups(tmp_path):
    md = tmp_path / "_ATOM_INDEX.md"
    md.write_text(
        "| Atom | Path | Trigger | Scope |\n"
        "|------|------|---------|-------|\n"
        "| a | memory/a.md | linemate, LineMate | global |\n",
        encoding="utf-8",
    )
    atoms = atom_index_json.parse_legacy_atom_index_md(md)
    assert atoms[0]["triggers"] == ["linemate"]


# ─── sync-atom-index 兩側一致 ──────────────────────────────────────────────

def _load_sync_tool():
    path = CLAUDE_ROOT / "tools" / "sync-atom-index.py"
    spec = importlib.util.spec_from_file_location("sync_atom_index_mod", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclass + future annotations 需能從 sys.modules 找到模組
    spec.loader.exec_module(mod)
    return mod


def test_sync_tool_frontmatter_and_index_agree(tmp_path):
    mod = _load_sync_tool()
    fm = mod.parse_frontmatter_triggers("# t\n\n- Trigger: linemate, LineMate,  LineMate , 架構\n")
    assert fm == ["linemate", "架構"]
    mem = tmp_path / "memory"
    atom_index_json.upsert_atom(mem, "a", "memory/a.md", ["linemate", "LineMate", "架構"])
    rows = mod.load_index_rows(mem)
    assert rows[0].triggers == fm, "frontmatter 與 index 同一把去重，不得互報 drift"
