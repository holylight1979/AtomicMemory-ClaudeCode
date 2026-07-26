"""verify_ups_read_cache.py — UPS 管線 per-turn 讀取快取（A1）。

契約：
- read_atom_text / load_access_cached：cache 提供時同 path 只實讀一次
  （之後刪檔仍回快取值）；cache=None 自讀（各函式可獨測）
- assemble_injection 消費 search 段下傳的 content cache（不重讀磁碟）
- spread_related 接受 content_cache 且優先用快取
- 主迴圈 budget skip → continue（1-line 指標），連續 2 次 skip 才 break（A6）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
from handlers import ups_inject  # noqa: E402


# ─── read_atom_text / load_access_cached ────────────────────────────────────


def test_read_atom_text_cache_hit(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("# A\n內容", encoding="utf-8")
    cache: dict = {}
    assert wg_atoms.read_atom_text(p, cache) == "# A\n內容"
    p.unlink()
    assert wg_atoms.read_atom_text(p, cache) == "# A\n內容"  # 快取供值
    assert wg_atoms.read_atom_text(p) is None                 # 無快取 → 實讀失敗


def test_read_atom_text_caches_failure(tmp_path):
    p = tmp_path / "missing.md"
    cache: dict = {}
    assert wg_atoms.read_atom_text(p, cache) is None
    p.write_text("late", encoding="utf-8")
    assert wg_atoms.read_atom_text(p, cache) is None  # 失敗也快取（單次判定）
    assert wg_atoms.read_atom_text(p) == "late"


def test_load_access_cached_defaults_and_hit(tmp_path):
    md = tmp_path / "a.md"
    acc = tmp_path / "a.access.json"
    acc.write_text('{"read_hits": 7, "timestamps": [1.0]}', encoding="utf-8")
    cache: dict = {}
    data = wg_atoms.load_access_cached(md, cache)
    assert data["read_hits"] == 7
    acc.unlink()
    assert wg_atoms.load_access_cached(md, cache)["read_hits"] == 7  # 快取
    assert wg_atoms.load_access_cached(md).get("read_hits", 0) == 0  # 無快取重讀


# ─── assemble_injection 消費 caches ─────────────────────────────────────────


def _entry(name: str, base: Path, triggers=None):
    return ((name, f"memory/{name}.md", triggers or []), base)


def test_assemble_uses_content_cache(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    (mem / "a.md").write_text("# 磁碟版", encoding="utf-8")
    cached_text = "# 快取版\n\n- 內容"
    caches = {
        "content": {str(mem / "a.md"): cached_text},
        "access": {},
    }
    lines: list = []
    state: dict = {}
    newly, dirs = ups_inject.assemble_injection(
        "sid", state, {}, [_entry("a", tmp_path)], [], [],
        {"a": "trigger"}, {}, lines, caches=caches,
    )
    assert newly == ["a"]
    joined = "\n".join(lines)
    assert "快取版" in joined and "磁碟版" not in joined  # 證明吃快取、未重讀磁碟


def test_spread_related_uses_content_cache(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    a = mem / "a.md"
    b = mem / "b.md"
    a.write_text("# A\n- Related: b\n", encoding="utf-8")
    b.write_text("# B\n", encoding="utf-8")
    all_atoms = [_entry("a", tmp_path), _entry("b", tmp_path)]
    cache = {str(a): "# A\n- Related: b\n"}
    a.unlink()  # 實檔刪除後仍靠快取擴散……但 spread 前有 exists() 檢查
    # exists() 為 False → 不擴散；驗證快取路徑：檔在但內容以快取為準
    a.write_text("# A（磁碟已無 Related）\n", encoding="utf-8")
    related = wg_atoms.spread_related({"a"}, all_atoms, [], content_cache=cache)
    assert [e[0][0] for e in related] == ["b"]


# ─── A6：budget skip streak ─────────────────────────────────────────────────


def _huge_atom(mem: Path, name: str) -> None:
    # 單一超長標題行：impression fallback == full → 超 budget 時必 skip
    (mem / f"{name}.md").write_text("# " + "x" * 4000, encoding="utf-8")


def test_budget_skip_continues_then_breaks(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    _huge_atom(mem, "huge1")
    (mem / "small.md").write_text("# small\n\n- 短內容", encoding="utf-8")
    _huge_atom(mem, "huge2")
    _huge_atom(mem, "huge3")
    (mem / "never.md").write_text("# never\n\n- 不應到達", encoding="utf-8")
    matched = [
        _entry("huge1", tmp_path), _entry("small", tmp_path),
        _entry("huge2", tmp_path), _entry("huge3", tmp_path),
        _entry("never", tmp_path),
    ]
    src = {n: "trigger" for n in ("huge1", "small", "huge2", "huge3", "never")}
    lines: list = []
    newly, _dirs = ups_inject.assemble_injection(
        "sid", {}, {}, matched, [], [], src, {}, lines,
    )
    joined = "\n".join(lines)
    # 首顆超 budget 不再截斷全部：small 仍被完整注入
    assert "small" in newly and "[Atom:small]\n" in joined
    # huge1 以 1-line 指標出現（skip → continue）
    assert "[Atom:huge1]" in joined and "(full: Read" in joined
    # 連續 2 次 skip（huge2, huge3）後 break：never 不再處理
    assert "huge2" in newly and "huge3" in newly
    assert "never" not in newly
