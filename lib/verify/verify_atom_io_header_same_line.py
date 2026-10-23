"""verify_atom_io_header_same_line.py：檔頭欄位讀寫只吃同一行；append 帶的 provenance／quote 照寫進檔頭。

1. replace 讀舊卡的 Source／Quote：空的 `- Quote:`／`- Source:` 行不得把下一行（`## 知識`、`- Confidence:`）讀成值再寫回。
   舊讀法 `^- Quote:\\s*(.+)$` 的 `\\s*` 吃掉換行，卡片 Quote 空的時 replace 會寫出 `- Quote: ## 知識`、知識標題消失。
2. append 帶 provenance／quote：以前兩條 append 路（py write_atom、MCP 走的 atom_io_cli append）只收知識行，
   呼叫者明給的來源被靜默丟掉。現在三態同 replace：沒給＝不動；非空＝換掉該行（沒有就補）；""＝刪掉該行。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_atom_io_header_same_line.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

LIB_PARENT = Path(__file__).resolve().parents[2]
if str(LIB_PARENT) not in sys.path:
    sys.path.insert(0, str(LIB_PARENT))

from lib import atom_io  # noqa: E402
from lib.atom_io import write_atom  # noqa: E402

TODAY = "2026-10-23"
COMMON = dict(scope="global", confidence="[臨]", triggers=["表頭", "同行", "來源"], source="test", skip_gate=True, today=TODAY)


@pytest.fixture
def isolated_claude(tmp_path, monkeypatch):
    """atom_io 與落點函式的全域根改指 tmp，不碰現役 ~/.claude。"""
    fake_claude = tmp_path / ".claude"
    mem = fake_claude / "memory"
    mem.mkdir(parents=True)
    monkeypatch.setattr(atom_io, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(atom_io, "GLOBAL_MEMORY_DIR", mem)
    monkeypatch.setattr(atom_io, "AUDIT_LOG", mem / "_meta" / "atom_io_audit.jsonl")
    from lib import atom_locations as aloc
    monkeypatch.setattr(aloc, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(aloc, "GLOBAL_MEMORY_DIR", mem)
    monkeypatch.setattr(aloc, "FAILURES_DIR", mem / "Failures")
    monkeypatch.setattr(aloc, "LOCAL_ATOMS_DIR", fake_claude / "_AIDocs" / "_atoms")
    monkeypatch.setattr(aloc, "TAXONOMY_LEARNED_PATH", mem / "_meta" / "taxonomy-lexicon-learned.json")
    return mem


def _card(provenance="session:abcdef12#11223344 2026-10-20", quote="「原句一號」") -> Path:
    r = write_atom(title="header-card", domain="CC與原子記憶契約", mode="create", knowledge=["[臨] 舊知識"],
                   provenance=provenance, quote=quote, **COMMON)
    assert r.ok, r.error
    return r.path


def _blank_header_fields(fp: Path) -> str:
    """把 Source／Quote 改成空欄位行（edit_metadata 給空字串就會留下這種行）。"""
    text = fp.read_text(encoding="utf-8")
    lines = ["- Source:" if l.startswith("- Source:") else "- Quote:" if l.startswith("- Quote:") else l
             for l in text.split("\n")]
    fp.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return fp.read_text(encoding="utf-8")


def test_008_replace_keeps_knowledge_heading_when_quote_line_is_empty(isolated_claude):
    fp = _card()
    before = _blank_header_fields(fp)
    assert "\n- Quote:\n- Confidence:" in before and "\n- Source:\n- Quote:" in before
    r = write_atom(title="header-card", mode="replace", knowledge=["[臨] 新知識"], **COMMON)
    assert r.ok, r.error
    text = fp.read_text(encoding="utf-8")
    assert "\n## 知識\n" in text, f"知識標題被吃成 Quote：\n{text}"
    assert "- Quote: ## 知識" not in text and "- Source: - Quote" not in text, text
    assert "- Quote:" not in text and "- Source:" not in text, "空欄位 replace 後不輸出（同 build 給空字串）"
    assert "- [臨] 新知識" in text


def test_008_edit_metadata_empty_then_replace_round_trip(isolated_claude):
    """實際中過的路：edit_metadata(quote="") 留空行 → 之後沒給 quote 的 replace 不能把下一行吃進 Quote。"""
    fp = _card()
    res = atom_io.edit_metadata(fp, quote="", source="test")
    assert res.ok, res.error
    assert "\n- Quote: \n" in fp.read_text(encoding="utf-8") or "\n- Quote:\n" in fp.read_text(encoding="utf-8")
    r = write_atom(title="header-card", mode="replace", knowledge=["[臨] 又一版"], **COMMON)
    assert r.ok, r.error
    text = fp.read_text(encoding="utf-8")
    assert "\n## 知識\n" in text and "- Quote: ## 知識" not in text, text
    assert "- Quote: - " not in text and text.count("- Confidence:") == 1, f"空 Quote 行把下一行的欄位讀成值寫回：\n{text}"
    assert "- Source: session:abcdef12#11223344 2026-10-20\n" in text, "沒給 provenance 的 replace 照舊保留 Source"


def test_008_supersedes_empty_line_does_not_read_next_line():
    assert atom_io.read_supersedes("# t\n\n- Supersedes:\n- Confidence: [臨]\n") == []
    assert atom_io.read_supersedes("# t\n\n- Supersedes: a, b\n") == ["a", "b"]


def test_008_append_writes_caller_provenance_and_quote(isolated_claude):
    fp = _card()
    new_src = "session:abcdef12#11223344 2026-10-20；commit:1234567 2026-10-23"
    r = write_atom(title="header-card", mode="append", knowledge=["[臨] 併入的知識"], provenance=new_src,
                   quote="「併入時的原句」", **COMMON)
    assert r.ok, r.error
    text = fp.read_text(encoding="utf-8")
    assert f"- Source: {new_src}\n" in text and text.count("- Source:") == 1, f"append 帶的 provenance 沒寫進 Source：\n{text}"
    assert "- Quote: 「併入時的原句」\n" in text and text.count("- Quote:") == 1
    assert "- [臨] 舊知識" in text and "- [臨] 併入的知識" in text


def test_008_append_without_provenance_keeps_header(isolated_claude):
    fp = _card()
    r = write_atom(title="header-card", mode="append", knowledge=["[臨] 只加知識"], **COMMON)
    assert r.ok, r.error
    text = fp.read_text(encoding="utf-8")
    assert "- Source: session:abcdef12#11223344 2026-10-20\n" in text and "- Quote: 「原句一號」\n" in text


def test_008_append_empty_string_clears_and_missing_line_is_inserted(isolated_claude):
    fp = _card(provenance=None, quote=None)
    assert "- Source:" not in fp.read_text(encoding="utf-8")
    r = write_atom(title="header-card", mode="append", knowledge=["[臨] 補來源"], provenance="commit:abcdef1 2026-10-23",
                   **COMMON)
    assert r.ok, r.error
    assert "- Source: commit:abcdef1 2026-10-23\n" in fp.read_text(encoding="utf-8"), "卡上沒有 Source 行：append 要補一行"
    r = write_atom(title="header-card", mode="append", knowledge=["[臨] 清來源"], provenance="", **COMMON)
    assert r.ok, r.error
    assert "- Source:" not in fp.read_text(encoding="utf-8"), '""＝清掉 Source 行（同 replace）'


def test_008_cli_append_used_by_mcp_writes_provenance(isolated_claude):
    """MCP js 的 append spawn `atom_io_cli append`：payload 帶 provenance 也要寫進檔頭。"""
    fp = _card()
    payload = {"action": "append", "file_path": str(fp), "knowledge": ["[臨] 經 cli 併入"], "source": "mcp",
               "provenance": "commit:7654321 2026-10-23"}
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "WG_CLAUDE_DIR": str(isolated_claude.parent)}
    proc = subprocess.run([sys.executable, "-m", "lib.atom_io_cli"], input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True, encoding="utf-8", cwd=str(LIB_PARENT), env=env, timeout=30)
    res = json.loads(proc.stdout)
    assert res["ok"], res.get("error")
    text = fp.read_text(encoding="utf-8")
    assert "- Source: commit:7654321 2026-10-23\n" in text and "- [臨] 經 cli 併入" in text, text
