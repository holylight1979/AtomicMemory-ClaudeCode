"""verify_quote_cleanup.py：tools/quote-cleanup.py 只刪「Quote 整個等於 --value」那一行、預設 dry-run 不改檔、走 atom_io 留稽核帳。

造假：子行程跑工具，WG_CLAUDE_DIR 指到 tmp 資料根（memory/、_AIDocs/_atoms/、稽核帳都落 tmp），專案層用 --memory-dir 給。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_quote_cleanup.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parents[2]
TOOL = TREE / "tools" / "quote-cleanup.py"

CARD = """# {title}

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: a, b
- Created-at: 2026-10-21
- Source: session:aaaaaaaa 2026-10-21
{quote}
## 知識

- [臨] 內容
- Quote: 「A」 這行在知識段，不是中繼資料

## 行動

- （依知識內容判斷）
"""


def _card(path: Path, quote: str, bom: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = CARD.format(title=path.stem, quote=quote)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    return path


@pytest.fixture
def world(tmp_path):
    data = tmp_path / "data"
    proj_mem = tmp_path / "proj" / ".claude" / "memory"
    cards = {
        "a": _card(data / "memory" / "設計通則" / "卡A.md", "- Quote: 「A」\n"),
        "bom": _card(data / "_AIDocs" / "_atoms" / "卡BOM.md", "- Quote: 「A」 \n", bom=True),
        "proj": _card(proj_mem / "shared" / "卡專案.md", "- Quote: 「A」\n"),
        "longer": _card(data / "memory" / "設計通則" / "卡長.md", "- Quote: 「A 計畫先做」\n"),
        "other": _card(data / "memory" / "設計通則" / "卡好.md", "- Quote: 「好」\n"),
        "none": _card(data / "memory" / "設計通則" / "卡無.md", ""),
    }
    return {"data": data, "proj_mem": proj_mem, "cards": cards, "tmp": tmp_path}


def _run(world, *args: str):
    env = {**os.environ, "WG_CLAUDE_DIR": str(world["data"]), "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "--memory-dir", str(world["proj_mem"]), *args],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(world["tmp"]))
    return p


def _snap(world):
    return {k: p.read_bytes() for k, p in world["cards"].items()}


def test_dry_run_lists_matches_and_changes_nothing(world):
    before = _snap(world)
    p = _run(world)
    assert p.returncode == 0, p.stderr
    tail = p.stdout.strip().splitlines()[-1]
    assert tail == "QUOTE_CLEANUP DONE matched=3 changed=0 failed=0 dry_run=1", p.stdout
    for k in ("a", "bom", "proj"):
        assert str(world["cards"][k]) in p.stdout
    for k in ("longer", "other", "none"):
        assert str(world["cards"][k]) not in p.stdout
    assert _snap(world) == before                                            # dry-run 一個位元組都不動
    assert not (world["data"] / "memory" / "_meta" / "atom_io_audit.jsonl").exists()


def test_apply_removes_only_that_line_and_is_idempotent(world):
    before = _snap(world)
    p = _run(world, "--apply", "--json")
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip().splitlines()[-1] == "QUOTE_CLEANUP DONE matched=3 changed=3 failed=0 dry_run=0"
    rep = json.loads(p.stdout[:p.stdout.rindex("QUOTE_CLEANUP")])
    assert sorted(Path(m["path"]).name for m in rep["matched"]) == ["卡A.md", "卡BOM.md", "卡專案.md"]
    for k in ("a", "bom", "proj"):
        raw = world["cards"][k].read_bytes()
        old = before[k]
        line = b"- Quote: \xe3\x80\x8cA\xe3\x80\x8d \n" if k == "bom" else b"- Quote: \xe3\x80\x8cA\xe3\x80\x8d\n"
        assert raw == old.replace(line, b"", 1), k                           # 只少那一行
        assert "- Quote: 「A」 這行在知識段" in raw.decode("utf-8-sig")        # 知識段同字樣不動
    assert world["cards"]["bom"].read_bytes().startswith(b"\xef\xbb\xbf")   # BOM 照留
    for k in ("longer", "other", "none"):
        assert world["cards"][k].read_bytes() == before[k]
    audit = (world["data"] / "memory" / "_meta" / "atom_io_audit.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(l) for l in audit]
    assert len(rows) == 3 and {r["source"] for r in rows} == {"tool:quote-cleanup"} and {r["op"] for r in rows} == {"quote-cleanup"}
    again = _run(world, "--apply")
    assert again.stdout.strip().splitlines()[-1] == "QUOTE_CLEANUP DONE matched=0 changed=0 failed=0 dry_run=0"


def test_value_option_and_only_given(world):
    p = _run(world, "--value", "好")
    assert p.stdout.strip().splitlines()[-1] == "QUOTE_CLEANUP DONE matched=1 changed=0 failed=0 dry_run=1"
    assert str(world["cards"]["other"]) in p.stdout
    only = _run(world, "--only-given")                                        # 只掃專案層
    assert only.stdout.strip().splitlines()[-1] == "QUOTE_CLEANUP DONE matched=1 changed=0 failed=0 dry_run=1"
    assert str(world["cards"]["proj"]) in only.stdout


def test_004_empty_entry_mode_removes_only_empty_entry_lines(world):
    """--empty-entry：清 edit_metadata(entry=[]) 以前留下的「- Entry: 」空行；有代號的 Entry 行、Quote 行都不動。"""
    data = world["data"]
    blank = _card(data / "memory" / "設計通則" / "卡空Entry.md", "- Entry: \n")
    bound = _card(data / "memory" / "設計通則" / "卡有Entry.md", "- Entry: E04\n")
    before_blank, before_bound, before_a = blank.read_bytes(), bound.read_bytes(), world["cards"]["a"].read_bytes()
    dry = _run(world, "--empty-entry")
    assert dry.stdout.strip().splitlines()[-1] == "QUOTE_CLEANUP DONE matched=1 changed=0 failed=0 dry_run=1", dry.stdout
    assert str(blank) in dry.stdout and str(bound) not in dry.stdout and blank.read_bytes() == before_blank
    p = _run(world, "--empty-entry", "--apply")
    assert p.stdout.strip().splitlines()[-1] == "QUOTE_CLEANUP DONE matched=1 changed=1 failed=0 dry_run=0", p.stdout
    assert blank.read_bytes() == before_blank.replace(b"- Entry: \n", b"", 1)
    assert bound.read_bytes() == before_bound and world["cards"]["a"].read_bytes() == before_a   # Quote 「A」這次不碰


def test_source_is_registered_in_atom_io():
    sys.path.insert(0, str(TREE))
    from lib.atom_io import VALID_SOURCES
    assert "tool:quote-cleanup" in VALID_SOURCES                             # 反例：沒登記 → write_raw 拒寫、每張都 failed
