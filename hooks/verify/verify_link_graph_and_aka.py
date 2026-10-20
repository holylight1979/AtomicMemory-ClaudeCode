"""verify_link_graph_and_aka.py — 連結圖由索引計算，改名靠別名。

不變式：
1. 索引只存作者寫的正向連結；注入端在記憶體反轉出反向，擴散兩個方向都走得到。
2. `- Aka:` 舊檔名解析得到現名：改名者只動自己那一顆，連進來的舊連結不必改。
3. 舊索引（沒有 related 欄）退回讀檔解析 `- Related:`，行為與改動前相同。
4. 加法相容：索引 schema 不升版；sync 把 Related/Aka 寫進索引、內容一致就不重寫。
5. --rebuild 的刪除界線：只清「掃描根底下、檔案真的不存在」的條目；不改既有 scope；冪等。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parent.parent.parent  # hooks/verify/ → repo root
sys.path.insert(0, str(CLAUDE / "hooks"))
sys.path.insert(0, str(CLAUDE))

import wg_atoms  # noqa: E402
from lib.atom_index_json import (  # noqa: E402
    SCHEMA_VERSION, build_alias_map, upsert_atom, validate_index,
)

_spec = importlib.util.spec_from_file_location("sync_atom_index", CLAUDE / "tools" / "sync-atom-index.py")
SYNC = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = SYNC   # dataclass 解析註解要回查模組，未註冊會 AttributeError
_spec.loader.exec_module(SYNC)


def _atom(name: str, related: str = "", aka: str = "") -> str:
    lines = [f"# {name}", "", "- Scope: global", "- Confidence: [臨]", "- Trigger: alpha"]
    if related:
        lines.append(f"- Related: {related}")
    if aka:
        lines.append(f"- Aka: {aka}")
    return "\n".join(lines) + "\n\n## 知識\n\n- [臨] 知識點\n\n## 行動\n\n- 做事\n"


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    """<tmp>/.claude/memory/<name>.md ＋ 空索引；回傳 memory dir。"""
    mem = tmp_path / ".claude" / "memory"
    mem.mkdir(parents=True)
    for name, text in files.items():
        (mem / f"{name}.md").write_text(text, encoding="utf-8")
    (mem / "_atom_index.json").write_text(
        json.dumps({"version": SCHEMA_VERSION, "atoms": []}, ensure_ascii=False), encoding="utf-8")
    return mem


def _sync(mem: Path) -> dict:
    claude_root = mem.parent
    atoms = SYNC.scan_atom_files(mem, claude_root)
    SYNC.add_to_index_from_frontmatter(atoms, SYNC.load_index_rows(mem), mem)
    return json.loads((mem / "_atom_index.json").read_text(encoding="utf-8"))


def _pool(mem: Path, names) -> list:
    base = mem.parent
    return [((n, f"memory/{n}.md", ["alpha"]), base) for n in names]


def _fresh_graph():
    wg_atoms._LINK_GRAPH_CACHE.clear()


# ─── 1. 索引存正向，注入端反轉出反向 ─────────────────────────────────────────


def test_index_stores_forward_links_only(tmp_path):
    mem = _tree(tmp_path, {"a": _atom("a", related="hub"), "hub": _atom("hub")})
    data = _sync(mem)
    by_name = {x["name"]: x for x in data["atoms"]}
    assert by_name["a"]["related"] == ["hub"]
    assert "related" not in by_name["hub"]          # hub 的檔沒被別人寫進去
    assert data["version"] == SCHEMA_VERSION        # 加欄位不升版，舊工具照讀
    assert validate_index(mem) == []


def test_spread_walks_both_directions(tmp_path):
    mem = _tree(tmp_path, {"a": _atom("a", related="hub"), "hub": _atom("hub")})
    _sync(mem)
    _fresh_graph()
    pool = _pool(mem, ["a", "hub"])

    forward = wg_atoms.spread_related({"a"}, pool, [])
    assert [e[0][0] for e in forward] == ["hub"]

    _fresh_graph()
    backward = wg_atoms.spread_related({"hub"}, pool, [])
    assert [e[0][0] for e in backward] == ["a"]     # 反向只存在記憶體裡


def test_graph_dedups_and_skips_self(tmp_path):
    mem = _tree(tmp_path, {"a": _atom("a", related="b, b, a"), "b": _atom("b", related="a")})
    _sync(mem)
    _fresh_graph()
    adj, _alias, covered = wg_atoms.load_link_graph([mem])
    assert adj["a"] == ["b"] and adj["b"] == ["a"]
    assert covered == {"a", "b"}


# ─── 2. 改名：Aka 別名 ───────────────────────────────────────────────────────


def test_aka_resolves_old_name(tmp_path):
    """b 改名成 b-new，只有 b-new 自己加了一行 Aka；a 的舊連結照樣走得到。"""
    mem = _tree(tmp_path, {"a": _atom("a", related="b"), "b-new": _atom("b-new", aka="b")})
    data = _sync(mem)
    assert {x["name"]: x.get("aka") for x in data["atoms"]}["b-new"] == ["b"]
    assert build_alias_map(data) == {"b": "b-new"}

    _fresh_graph()
    pool = _pool(mem, ["a", "b-new"])
    assert [e[0][0] for e in wg_atoms.spread_related({"a"}, pool, [])] == ["b-new"]
    _fresh_graph()
    assert [e[0][0] for e in wg_atoms.spread_related({"b-new"}, pool, [])] == ["a"]


def test_alias_never_shadows_a_real_atom(tmp_path):
    """有人把別人還在用的檔名寫成自己的 Aka：真 atom 優先，且驗證報錯。"""
    mem = _tree(tmp_path, {"b": _atom("b"), "c": _atom("c", aka="b")})
    data = _sync(mem)
    assert build_alias_map(data) == {}
    assert any("aka collides" in e for e in validate_index(mem))


# ─── 3. 舊索引 fallback ──────────────────────────────────────────────────────


def test_falls_back_to_file_when_index_has_no_links(tmp_path):
    mem = _tree(tmp_path, {"a": _atom("a", related="b"), "b": _atom("b")})
    # 舊索引：只有 name/path/triggers/scope
    (mem / "_atom_index.json").write_text(json.dumps({"version": SCHEMA_VERSION, "atoms": [
        {"name": n, "path": f"memory/{n}.md", "triggers": ["alpha"], "scope": "global"}
        for n in ("a", "b")]}, ensure_ascii=False), encoding="utf-8")
    _fresh_graph()
    pool = _pool(mem, ["a", "b"])
    assert [e[0][0] for e in wg_atoms.spread_related({"a"}, pool, [])] == ["b"]


# ─── 4. 加法相容 ─────────────────────────────────────────────────────────────


def test_upsert_keeps_links_when_caller_omits_them(tmp_path):
    """只改 trigger 的呼叫端沒傳 related/aka → 不得把既有連結洗掉。"""
    mem = _tree(tmp_path, {})
    upsert_atom(mem, "a", "memory/a.md", ["alpha"], related=["b"], aka=["a-old"])
    assert upsert_atom(mem, "a", "memory/a.md", ["alpha", "beta"]) is True
    entry = json.loads((mem / "_atom_index.json").read_text(encoding="utf-8"))["atoms"][0]
    assert entry["related"] == ["b"] and entry["aka"] == ["a-old"]


def test_sync_is_idempotent(tmp_path):
    mem = _tree(tmp_path, {"a": _atom("a", related="b"), "b": _atom("b", aka="b-old")})
    first = _sync(mem)
    stamp = (mem / "_atom_index.json").read_text(encoding="utf-8")
    assert _sync(mem) == first
    assert (mem / "_atom_index.json").read_text(encoding="utf-8") == stamp


# ─── 5. --rebuild 的刪除界線 ─────────────────────────────────────────────────


def _rebuild(mem: Path) -> dict:
    claude_root = mem.parent
    atoms = SYNC.scan_atom_files(mem, claude_root)
    SYNC.rebuild_index(mem, claude_root, atoms)
    return json.loads((mem / "_atom_index.json").read_text(encoding="utf-8"))


def _write_index(mem: Path, atoms: list) -> None:
    (mem / "_atom_index.json").write_text(
        json.dumps({"version": SCHEMA_VERSION, "atoms": atoms}, ensure_ascii=False),
        encoding="utf-8")


def test_rebuild_keeps_entries_outside_the_scanned_roots(tmp_path):
    """全域索引另有 _AIDocs/_atoms/ 這個根；掃不到它的環境不得把那些條目清掉。"""
    mem = _tree(tmp_path, {"a": _atom("a")})
    local = tmp_path / ".claude" / "_AIDocs" / "_atoms" / "MemDev"
    local.mkdir(parents=True)
    (local / "tooling.md").write_text(_atom("tooling"), encoding="utf-8")
    _write_index(mem, [
        {"name": "a", "path": "memory/a.md", "triggers": ["alpha"], "scope": "global"},
        {"name": "tooling", "path": "_AIDocs/_atoms/MemDev/tooling.md",
         "triggers": ["alpha"], "scope": "global"},
    ])
    names = {x["name"] for x in _rebuild(mem)["atoms"]}
    assert names == {"a", "tooling"}


def test_rebuild_keeps_entries_the_scanner_excludes_but_file_still_there(tmp_path):
    """掃描器排除 _reference/ 等目錄；那裡的既有條目檔案還在，重建不該替它決定刪除。"""
    mem = _tree(tmp_path, {"a": _atom("a")})
    ref = mem / "_reference"
    ref.mkdir()
    (ref / "origin.md").write_text(_atom("origin"), encoding="utf-8")
    _write_index(mem, [
        {"name": "a", "path": "memory/a.md", "triggers": ["alpha"], "scope": "global"},
        {"name": "origin", "path": "memory/_reference/origin.md",
         "triggers": ["alpha"], "scope": "global"},
    ])
    names = {x["name"] for x in _rebuild(mem)["atoms"]}
    assert names == {"a", "origin"}


def test_rebuild_drops_only_entries_whose_file_is_gone(tmp_path):
    mem = _tree(tmp_path, {"a": _atom("a")})
    _write_index(mem, [
        {"name": "a", "path": "memory/a.md", "triggers": ["alpha"], "scope": "global"},
        {"name": "ghost", "path": "memory/ghost.md", "triggers": ["alpha"], "scope": "global"},
    ])
    names = {x["name"] for x in _rebuild(mem)["atoms"]}
    assert names == {"a"}


def test_rebuild_does_not_restamp_scope_and_is_idempotent(tmp_path):
    """scope 回正是 --fix-scope-from-path 的事；重建順手改，會讓副本上的一次重建標錯整庫。"""
    mem = _tree(tmp_path, {"a": _atom("a")})
    _write_index(mem, [{"name": "a", "path": "memory/a.md",
                        "triggers": ["alpha"], "scope": "global", "last_used": "2026-09-01"}])
    first = _rebuild(mem)
    entry = first["atoms"][0]
    assert entry["scope"] == "global"          # 未被重推成 shared
    assert entry["last_used"] == "2026-09-01"  # 不在 .md 裡的欄位沿用
    assert _rebuild(mem) == first              # 冪等


def test_rebuild_carries_unknown_top_level_keys(tmp_path):
    """頂層鍵不是只有 version/atoms：classify-project-scope 寫 layout="scope-v2"
    標記「這個專案的記憶已整理過」。重建若只組 version+atoms 就會把它靜默吃掉，
    而且沒有任何錯誤訊號——下次只表現成「這專案又被當成沒整理過」。"""
    mem = _tree(tmp_path, {"a": _atom("a")})
    (mem / "_atom_index.json").write_text(
        json.dumps({"version": SCHEMA_VERSION, "layout": "scope-v2", "atoms": [
            {"name": "a", "path": "memory/a.md", "triggers": ["alpha"], "scope": "global"},
        ]}, ensure_ascii=False), encoding="utf-8")
    out = _rebuild(mem)
    assert out.get("layout") == "scope-v2", sorted(out)
    assert {x["name"] for x in out["atoms"]} == {"a"}


def test_rebuild_keeps_existing_order_and_appends_new_at_the_end(tmp_path):
    """索引是入版控的檔：重排會讓整檔變成一次重寫，人看不出真正改了什麼，
    合併驅動也失去「同區塊各多一列」的前提。既有條目維持原序、新的接在尾端。"""
    mem = _tree(tmp_path, {"zeta": _atom("zeta"), "alpha": _atom("alpha")})
    _write_index(mem, [   # 刻意不是字母序，也不是 path 序
        {"name": "zeta", "path": "memory/zeta.md", "triggers": ["z"], "scope": "global"},
        {"name": "alpha", "path": "memory/alpha.md", "triggers": ["a"], "scope": "global"},
    ])
    assert [x["name"] for x in _rebuild(mem)["atoms"]] == ["zeta", "alpha"]

    (mem / "mid.md").write_text(_atom("mid"), encoding="utf-8")
    assert [x["name"] for x in _rebuild(mem)["atoms"]] == ["zeta", "alpha", "mid"]

    # 兩顆同時進來 → 彼此以 path 排序，結果可重現
    (mem / "b2.md").write_text(_atom("b2"), encoding="utf-8")
    (mem / "a2.md").write_text(_atom("a2"), encoding="utf-8")
    out = [x["name"] for x in _rebuild(mem)["atoms"]]
    assert out == ["zeta", "alpha", "mid", "a2", "b2"], out
