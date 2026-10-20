"""verify_related_line_and_conflict_guard.py — Related 行定位與衝突標記防護。

守住規則：
1. 衝突標記偵測：diff3/svn 形狀的區段算衝突；``` 範例裡的不算。
2. 寫入 funnel：內容含衝突標記 → 拒寫（ConflictMarkerError 為 OSError 子類，write_raw 回 ok=False），不落檔。
3. Related 行：只認第一個 `## ` 之前的第一行；空值不跨行吃到下一行。
4. 反向連結不寫檔：單向不算缺陷，`--fix-refs` 不動任何檔（改由索引在注入時反轉）。
   讀取只看 metadata 區，知識段裡長得像欄位的行不影響判斷。
5. edit_metadata：空值 Related 被替換時，下一行標題不被吃掉。
6. lib parse_frontmatter：空值欄位不會提前結束 metadata 區塊。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → repo root
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))
TOOLS_DIR = CLAUDE_DIR / "tools"

from lib import atom_io  # noqa: E402
from lib.atom_spec import (  # noqa: E402
    find_related_line, has_conflict_markers, parse_frontmatter, split_related,
)


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HC = _load("atom_health_check", "atom-health-check.py")

CONFLICT_BLOCK = (
    "<<<<<<< .mine\n"
    "- Related: x, y\n"
    "||||||| .r10\n"
    "- Related: x\n"
    "=======\n"
    "- Related: x, z\n"
    ">>>>>>> .r20\n"
)


def _atom(name: str, meta_tail: str, body: str = "- [臨] 知識點\n") -> str:
    return (
        f"# {name}\n\n"
        "- Scope: global\n"
        "- Confidence: [臨]\n"
        "- Trigger: alpha, beta\n"
        f"{meta_tail}"
        f"\n## 知識\n\n{body}\n## 行動\n\n- 行動\n"
    )


@pytest.fixture
def isolated_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(atom_io, "AUDIT_LOG", tmp_path / "_meta" / "atom_io_audit.jsonl")
    monkeypatch.setattr(HC, "MEMORY_ROOT", tmp_path)
    return tmp_path


# ─── 1. 衝突標記偵測 ──────────────────────────────────────────────────────────


def test_conflict_markers_detected():
    assert has_conflict_markers(_atom("a", CONFLICT_BLOCK))


def test_conflict_markers_inside_fence_ignored():
    body = "- [臨] 範例：\n\n```\n" + CONFLICT_BLOCK + "```\n"
    assert not has_conflict_markers(_atom("a", "- Related: b\n", body))


def test_plain_text_is_not_conflict():
    assert not has_conflict_markers("<<<<<<<< 八個不算\n一般內容\n>>>>>>>> 也不算\n")


# ─── 2. 寫入 funnel 拒寫 ──────────────────────────────────────────────────────


def test_write_text_lf_refuses_conflict_markers(tmp_path):
    target = tmp_path / "a.md"
    with pytest.raises(atom_io.ConflictMarkerError):
        atom_io.write_text_lf(target, _atom("a", CONFLICT_BLOCK))
    assert not target.exists()
    assert issubclass(atom_io.ConflictMarkerError, OSError)


def test_write_raw_reports_refusal(isolated_audit):
    target = isolated_audit / "a.md"
    res = atom_io.write_raw(target, _atom("a", CONFLICT_BLOCK), source="test")
    assert not res.ok
    assert "conflict" in (res.error or "")
    assert not target.exists()


def test_write_text_lf_allows_resolved_content(tmp_path):
    target = tmp_path / "a.md"
    atom_io.write_text_lf(target, _atom("a", "- Related: x, y, z\n"))
    assert target.exists()


# ─── 3. Related 行定位 ────────────────────────────────────────────────────────


def test_find_related_line_empty_value_does_not_cross_lines():
    text = _atom("a", "- Related:\n")
    m = find_related_line(text)
    assert m is not None
    assert m.group(1) == ""
    assert split_related(m.group(1)) == []


def test_find_related_line_ignores_knowledge_section():
    text = _atom("a", "", body="- Related: 知識段裡的不算\n")
    assert find_related_line(text) is None


def test_find_related_line_takes_first_in_conflict():
    m = find_related_line(_atom("a", CONFLICT_BLOCK))
    assert split_related(m.group(1)) == ["x", "y"]


def test_split_related_none_marker():
    assert split_related("(none)") == []
    assert split_related("a, b.md, ,c") == ["a", "b", "c"]


# ─── 4. 反向連結不寫檔 ───────────────────────────────────────────────────────


def test_one_way_link_is_not_a_defect(isolated_audit):
    """A → B 而 B 沒回指：不算缺陷，也不會有人去改 B 的檔。"""
    a = isolated_audit / "a.md"
    b = isolated_audit / "b.md"
    a.write_text(_atom("a", "- Related: b\n"), encoding="utf-8")
    b.write_text(_atom("b", "- Related:\n"), encoding="utf-8")
    before = b.read_text(encoding="utf-8")

    assert HC.check_reverse_refs({"a": a, "b": b}) == []
    assert not hasattr(HC, "fix_reverse_refs")  # 寫入器已退役，別再長回來
    assert b.read_text(encoding="utf-8") == before


def test_parse_frontmatter_stops_at_first_section(isolated_audit):
    p = isolated_audit / "a.md"
    p.write_text(_atom("a", "- Related: b\n", body="- Trigger: 知識段裡的不算\n"), encoding="utf-8")
    fm = HC.parse_frontmatter(p)
    assert fm["Trigger"] == "alpha, beta"
    assert HC.parse_related(fm) == ["b"]


# ─── 5. edit_metadata ────────────────────────────────────────────────────────


def test_edit_metadata_empty_related_keeps_next_heading(tmp_path, monkeypatch):
    fake_claude = tmp_path / ".claude"
    mem = fake_claude / "memory"
    mem.mkdir(parents=True)
    monkeypatch.setattr(atom_io, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(atom_io, "GLOBAL_MEMORY_DIR", mem)
    monkeypatch.setattr(atom_io, "AUDIT_LOG", mem / "_meta" / "atom_io_audit.jsonl")
    p = mem / "a.md"
    p.write_text(_atom("a", "- Related:\n"), encoding="utf-8")

    res = atom_io.edit_metadata(p, related=["b"], source="test")
    assert res.ok, res.error
    text = p.read_text(encoding="utf-8")
    assert "- Related: b\n" in text
    assert "\n## 知識\n" in text


def test_edit_metadata_refuses_conflicted_atom(tmp_path, monkeypatch):
    fake_claude = tmp_path / ".claude"
    mem = fake_claude / "memory"
    mem.mkdir(parents=True)
    monkeypatch.setattr(atom_io, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(atom_io, "GLOBAL_MEMORY_DIR", mem)
    monkeypatch.setattr(atom_io, "AUDIT_LOG", mem / "_meta" / "atom_io_audit.jsonl")
    p = mem / "a.md"
    original = _atom("a", CONFLICT_BLOCK)
    p.write_text(original, encoding="utf-8")

    res = atom_io.edit_metadata(p, related=["b"], source="test")
    assert not res.ok
    assert p.read_text(encoding="utf-8") == original


# ─── 6. lib parse_frontmatter ────────────────────────────────────────────────


def test_lib_parse_frontmatter_empty_value_keeps_block_open():
    text = "# a\n\n- Related:\n- Scope: shared\n\n## 知識\n"
    fm = parse_frontmatter(text)
    assert fm.get("Scope") == "shared"
    assert "Related" not in fm
