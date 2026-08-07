"""verify_atom_io_edit_metadata.py — lib.atom_io.edit_metadata 外科編輯單元測試。

edit_metadata 取代「直接 Write/Edit atom .md」（被 Guardian AtomFunnelBlock 擋）與
整檔 atom_write replace（重建知識區、風險高），只替換 frontmatter 的
Trigger/Related/Tags 行。本檔守住其不變式：

  1. byte-stable —— **只改目標那幾行**，其餘 byte 原樣（含非目標欄位、知識區、EOL、BOM）
  2. triggers 變更 → 先寫 _atom_index.json（SoT），成功才續寫 frontmatter（衍生）
  3. SoT 先行失敗 → 不續寫 frontmatter（避免不可復原 drift）
  4. 找不到欄位行 → 不靜默 no-op，回 error 且不落任何檔
  5. invalid source / read 失敗 / 檔不在 CLAUDE_DIR 下 → 各自 error

之前僅靠 dogfood + 對抗式審查，未進 run_verify baseline；本檔補入。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

LIB_PARENT = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude/
if str(LIB_PARENT) not in sys.path:
    sys.path.insert(0, str(LIB_PARENT))

from lib import atom_io  # noqa: E402
from lib.atom_io import edit_metadata, write_atom  # noqa: E402


FIXED_TODAY = "2026-05-04"


@pytest.fixture
def isolated_claude(tmp_path, monkeypatch):
    """把 atom_io 全域 root path 重指向 tmp_path，避免污染現役 ~/.claude/。

    edit_metadata 依賴 atom_io.CLAUDE_DIR（算 rel_path）與 GLOBAL_MEMORY_DIR
    （index base）兩個 module 全域，均 monkeypatch。
    """
    fake_claude = tmp_path / ".claude"
    fake_global_mem = fake_claude / "memory"
    fake_audit = fake_global_mem / "_meta" / "atom_io_audit.jsonl"
    fake_global_mem.mkdir(parents=True)
    monkeypatch.setattr(atom_io, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(atom_io, "GLOBAL_MEMORY_DIR", fake_global_mem)
    monkeypatch.setattr(atom_io, "AUDIT_LOG", fake_audit)
    return {"root": tmp_path, "claude": fake_claude, "memory": fake_global_mem}


def _make_atom(isolated_claude, *, title="Edit Target", triggers=("a", "b", "c"),
               related=None, knowledge=("fact1", "fact2")):
    """建一顆 global atom（含 index 條目）供編輯。回 file_path。"""
    res = write_atom(
        title=title, scope="global", confidence="[臨]",
        triggers=list(triggers), knowledge=list(knowledge),
        related=list(related) if related else None,
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert res.ok, res.error
    return res.path


def _index_triggers(isolated_claude, slug):
    """從 fake _atom_index.json 取某 atom 的 triggers list。"""
    idx = json.loads((isolated_claude["memory"] / "_atom_index.json").read_text(encoding="utf-8"))
    for a in idx["atoms"]:
        if a["name"] == slug:
            return a["triggers"]
    return None


# ─── 1. triggers 編輯：frontmatter + index 同步 ───────────────────────────────


def test_edit_triggers_updates_frontmatter_and_index(isolated_claude):
    fp = _make_atom(isolated_claude, triggers=["old1", "old2"])
    before = fp.read_text(encoding="utf-8")
    assert "- Trigger: old1, old2" in before
    assert _index_triggers(isolated_claude, fp.stem) == ["old1", "old2"]

    res = edit_metadata(fp, triggers=["new-x", "new-y", "new-z"], source="test")
    assert res.ok, res.error

    after = fp.read_text(encoding="utf-8")
    assert "- Trigger: new-x, new-y, new-z" in after
    assert "old1, old2" not in after
    # index (SoT) 同步更新
    assert _index_triggers(isolated_claude, fp.stem) == ["new-x", "new-y", "new-z"]
    # op=meta-edit 進 audit
    assert res.path == fp


# ─── 2. related-only 編輯：不碰 index ─────────────────────────────────────────


def test_edit_related_only_leaves_index_untouched(isolated_claude):
    fp = _make_atom(isolated_claude, triggers=["t1", "t2"], related=["r-old"])
    idx_path = isolated_claude["memory"] / "_atom_index.json"
    idx_before = idx_path.read_bytes()

    res = edit_metadata(fp, related=["r-new-1", "r-new-2"], source="test")
    assert res.ok, res.error

    after = fp.read_text(encoding="utf-8")
    assert "- Related: r-new-1, r-new-2" in after
    assert "r-old" not in after
    # related 編輯不寫 index → byte 原樣
    assert idx_path.read_bytes() == idx_before
    # triggers 不動
    assert "- Trigger: t1, t2" in after


# ─── 3. byte-stable：只有目標行變，其餘行 byte 原樣 ──────────────────────────


def test_byte_stable_only_target_line_changes(isolated_claude):
    fp = _make_atom(isolated_claude, triggers=["t1", "t2"], related=["r-old"],
                    knowledge=["keep-line-1", "keep-line-2"])
    before_lines = fp.read_text(encoding="utf-8").splitlines()

    res = edit_metadata(fp, related=["r-new"], source="test")
    assert res.ok, res.error
    after_lines = fp.read_text(encoding="utf-8").splitlines()

    assert len(before_lines) == len(after_lines), "行數不得變"
    diff = [(b, a) for b, a in zip(before_lines, after_lines) if b != a]
    assert len(diff) == 1, f"應只有 1 行變動，實得 {len(diff)}: {diff}"
    assert diff[0][0].startswith("- Related:")
    assert diff[0][1] == "- Related: r-new"


# ─── 4. tags 編輯（fixture 自備 Tags 行；build_atom_content 預設不出 Tags） ────


def test_edit_tags_line(isolated_claude):
    fp = isolated_claude["memory"] / "tagged.md"
    fp.write_text(
        "# Tagged\n\n- Scope: global\n- Confidence: [臨]\n"
        "- Trigger: a, b\n- Tags: old-tag-1, old-tag-2\n\n## 知識\n\n- k\n",
        encoding="utf-8",
    )
    res = edit_metadata(fp, tags=["new-tag"], source="test")
    assert res.ok, res.error
    after = fp.read_text(encoding="utf-8")
    assert "- Tags: new-tag" in after
    assert "old-tag" not in after


# ─── 5. 找不到欄位行 → 非靜默 no-op，且不落任何檔 ────────────────────────────


def test_field_not_found_errors_without_write(isolated_claude):
    # 標準 atom 無 Tags 行 → edit tags 應報 not found
    fp = _make_atom(isolated_claude, triggers=["t1", "t2"])
    before = fp.read_bytes()
    idx_before = (isolated_claude["memory"] / "_atom_index.json").read_bytes()

    res = edit_metadata(fp, tags=["whatever"], source="test")
    assert not res.ok
    assert "not found" in res.error and "Tags" in res.error
    # 檔與 index 皆 byte 原樣（not-found 在 SoT 寫入前）
    assert fp.read_bytes() == before
    assert (isolated_claude["memory"] / "_atom_index.json").read_bytes() == idx_before


# ─── 6. invalid source → error ───────────────────────────────────────────────


def test_invalid_source_errors(isolated_claude):
    fp = _make_atom(isolated_claude)
    before = fp.read_bytes()
    res = edit_metadata(fp, triggers=["x"], source="hacker:bypass")
    assert not res.ok and "invalid source" in res.error
    assert fp.read_bytes() == before  # 未動檔


# ─── 7. read 失敗（檔不存在）→ error ─────────────────────────────────────────


def test_read_failure_errors(isolated_claude):
    ghost = isolated_claude["memory"] / "does-not-exist.md"
    res = edit_metadata(ghost, related=["x"], source="test")
    assert not res.ok and "read failed" in res.error


# ─── 8. triggers 編輯但檔不在任何 memory root 下 → error，且不落檔 ────────────
# （專案層 atom 現為合法：index root 以上溯最近 _atom_index.json 定位；
#  上溯不到索引才拒絕——ClAUDE_DIR 外不再一律擋。）


def test_triggers_edit_without_index_root_errors(isolated_claude):
    # 在 tmp 但不在 fake_claude 下、上溯無 _atom_index.json；含 Trigger 行使
    # surgical replace 先成功，才驗 index root 定位階段攔下（尚未落檔）。
    outside = isolated_claude["root"] / "stray.md"
    outside.write_text(
        "# Stray\n\n- Scope: global\n- Confidence: [臨]\n- Trigger: a, b\n\n## 知識\n\n- k\n",
        encoding="utf-8",
    )
    before = outside.read_bytes()
    res = edit_metadata(outside, triggers=["z"], source="test")
    assert not res.ok and "no _atom_index.json found" in res.error
    assert outside.read_bytes() == before  # frontmatter 未落檔


# ─── 9. BOM 保留 ─────────────────────────────────────────────────────────────


def test_bom_preserved(isolated_claude):
    fp = _make_atom(isolated_claude, triggers=["t1", "t2"], related=["r-old"])
    # 模擬原檔帶 BOM
    raw = fp.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    fp.write_bytes(b"\xef\xbb\xbf" + raw)

    res = edit_metadata(fp, related=["r-new"], source="test")
    assert res.ok, res.error
    out = fp.read_bytes()
    assert out.startswith(b"\xef\xbb\xbf"), "BOM 須原樣保留"
    assert "- Related: r-new" in out.decode("utf-8-sig")


# ─── 10. SoT 先行：index 寫入失敗 → frontmatter 不續寫 ───────────────────────


def test_sot_index_failure_blocks_frontmatter(isolated_claude, monkeypatch):
    fp = _make_atom(isolated_claude, triggers=["keep-me"])
    before = fp.read_bytes()

    def _failing_write_index(*_a, **_k):
        return atom_io.WriteResult(ok=False, error="simulated index failure", audit_id="x")

    monkeypatch.setattr(atom_io, "write_index", _failing_write_index)
    res = edit_metadata(fp, triggers=["should-not-land"], source="test")
    assert not res.ok and "simulated index failure" in res.error
    # frontmatter Trigger 行未被改（index 領先失敗即中止）
    after = fp.read_bytes()
    assert after == before
    assert "- Trigger: keep-me" in after.decode("utf-8")
