"""verify_atom_index_depends.py：_atom_index.json 的 depends 欄（A3.1）。

三案：未傳鍵保留（4 參數的舊呼叫者不丟 depends）、`[]` 清空（鍵移除）、型別錯拒（ValueError，不落檔）；
另驗 _ATOM_INDEX.md mirror 多一欄、validate_index 對壞 depends 報錯。全在 tmp，不碰 live。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_atom_index_depends.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

CLAUDE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(CLAUDE_ROOT) not in sys.path:
    sys.path.insert(0, str(CLAUDE_ROOT))

from lib.atom_index_json import (  # noqa: E402
    load_atom_index_json, regenerate_atom_index_md, upsert_atom, validate_depends, validate_index,
)


@pytest.fixture
def mem(tmp_path):
    m = tmp_path / "memory"
    m.mkdir()
    return m


def _entry(mem, name):
    return next(a for a in load_atom_index_json(mem)["atoms"] if a["name"] == name)


def test_untouched_depends_is_preserved_by_four_arg_callers(mem):
    upsert_atom(mem, "a", "memory/a.md", ["t1"], "global", depends=["path:tools/x.py", "decision:abc"])
    assert _entry(mem, "a")["depends"] == ["path:tools/x.py", "decision:abc"]
    # 舊式 4／5 參數呼叫（trigger 改了、沒傳 depends）→ depends 原樣
    assert upsert_atom(mem, "a", "memory/a.md", ["t1", "t2"], "global") is True
    assert _entry(mem, "a")["depends"] == ["path:tools/x.py", "decision:abc"]
    assert _entry(mem, "a")["triggers"] == ["t1", "t2"]
    # 完全相同 → 回 False（含 depends 比對）
    assert upsert_atom(mem, "a", "memory/a.md", ["t1", "t2"], "global") is False
    # 新條目沒給 depends → 不長出空鍵
    upsert_atom(mem, "b", "memory/b.md", ["x"], "global")
    assert "depends" not in _entry(mem, "b")


def test_empty_list_clears_depends(mem):
    upsert_atom(mem, "a", "memory/a.md", ["t1"], "global", depends=["path:tools/x.py"])
    assert upsert_atom(mem, "a", "memory/a.md", ["t1"], "global", depends=[]) is True
    assert "depends" not in _entry(mem, "a")
    # 再清一次 → 沒變化
    assert upsert_atom(mem, "a", "memory/a.md", ["t1"], "global", depends=[]) is False
    # 非空取代
    upsert_atom(mem, "a", "memory/a.md", ["t1"], "global", depends=[" path:tools/y.py ", "path:tools/y.py", ""])
    assert _entry(mem, "a")["depends"] == ["path:tools/y.py"]      # strip、去空、去重


def test_wrong_type_is_rejected_before_writing(mem):
    upsert_atom(mem, "a", "memory/a.md", ["t1"], "global", depends=["path:tools/x.py"])
    before = (mem / "_atom_index.json").read_text(encoding="utf-8")
    for bad in ("path:tools/x.py", 3, {"path": "x"}, ["ok", 7], [None]):
        with pytest.raises(ValueError):
            upsert_atom(mem, "a", "memory/a.md", ["t1"], "global", depends=bad)
    assert (mem / "_atom_index.json").read_text(encoding="utf-8") == before   # 拒在寫入前，檔沒動
    assert validate_depends([]) == []
    # 索引檔被旁路寫壞 → validate_index 報
    data = load_atom_index_json(mem)
    data["atoms"][0]["depends"] = "not-a-list"
    (mem / "_atom_index.json").write_text(json.dumps(data), encoding="utf-8")
    errs = validate_index(mem)
    assert any("depends invalid" in e for e in errs), errs


def test_md_mirror_has_depends_column_only_when_used(mem):
    # 沒人用 depends → mirror 格式與以前 byte 相同（多機不因格式換版互相重生衝突）
    upsert_atom(mem, "b", "memory/b.md", ["t2"], "global")
    regenerate_atom_index_md(mem)
    md = (mem / "_ATOM_INDEX.md").read_text(encoding="utf-8")
    assert "| Atom | Path | Trigger | Scope |\n|------|------|---------|-------|\n| b | memory/b.md | t2 | global |\n" in md
    assert "Depends" not in md
    upsert_atom(mem, "a", "memory/a.md", ["t1"], "global", depends=["path:tools/x.py", "free text"])
    regenerate_atom_index_md(mem)
    md = (mem / "_ATOM_INDEX.md").read_text(encoding="utf-8")
    assert "| Atom | Path | Trigger | Scope | Depends |" in md
    assert "| a | memory/a.md | t1 | global | path:tools/x.py, free text |" in md
    assert "| b | memory/b.md | t2 | global |  |" in md
