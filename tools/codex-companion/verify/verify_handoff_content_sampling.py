"""verify_handoff_content_sampling.py — _read_handoff_content 頭尾採樣 + 截斷標記。

守門：發給 codex 的 handoff 內容若超長，必須 (1) 保留檔案結尾（授權/收尾段常在文末）
(2) 明確標記截斷（靜默截斷會讓 codex 把輸入切斷誤判成文件斷鏈——2026-08-05 實案：
limit=6000 靜默切斷 12778 字計畫檔，codex 連 4 輪 severity=high 誤報「文件截斷」）。
"""
from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[3] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from codex_companion import _read_handoff_content  # noqa: E402


def test_short_file_passthrough(tmp_path):
    f = tmp_path / "next-phase-x.md"
    f.write_text("# 短檔\n完整內容", encoding="utf-8")
    assert _read_handoff_content(str(f)) == "# 短檔\n完整內容"


def test_long_file_keeps_head_and_tail_with_marker(tmp_path):
    head_part = "H" * 5000
    tail_part = "T" * 3000
    f = tmp_path / "next-phase-x.md"
    f.write_text(head_part + tail_part, encoding="utf-8")
    out = _read_handoff_content(str(f), head=4500, tail=1500)
    assert out.startswith("H" * 4500), "開頭 4500 字必須保留"
    assert out.endswith("T" * 1500), "結尾 1500 字必須保留（授權段常在文末）"
    assert "中段省略" in out and "8000 字" in out, "截斷必須明確標記且附全文字數"


def test_missing_file_returns_empty(tmp_path):
    assert _read_handoff_content(str(tmp_path / "nope.md")) == ""


def test_bom_tolerated(tmp_path):
    f = tmp_path / "next-phase-x.md"
    f.write_bytes(b"\xef\xbb\xbfBOM body")
    assert _read_handoff_content(str(f)) == "BOM body"
