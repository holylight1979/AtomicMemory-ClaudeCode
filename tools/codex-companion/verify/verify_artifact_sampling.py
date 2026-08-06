"""verify_artifact_sampling.py — artifact_io 頭尾採樣 + 截斷標記守門。

守門：發給 codex 的 artifact 內容若超長，必須 (1) 保留檔案結尾（授權/收尾段
常在文末）(2) 明確標記截斷（靜默截斷會讓 codex 把輸入切斷誤判成文件斷鏈——
handoff 實案：limit=6000 靜默切斷 12778 字檔，連 4 輪 severity=high 誤報
「文件截斷」；plan_review 同型案由 verify_prompt_input_integrity 把關）。
"""
from __future__ import annotations

import sys
from pathlib import Path

COMP_DIR = Path(__file__).resolve().parent.parent
if str(COMP_DIR) not in sys.path:
    sys.path.insert(0, str(COMP_DIR))

from artifact_io import read_artifact_sampled, sample_text  # noqa: E402


def test_short_file_passthrough(tmp_path):
    f = tmp_path / "next-phase-x.md"
    f.write_text("# 短檔\n完整內容", encoding="utf-8")
    assert read_artifact_sampled(str(f)) == "# 短檔\n完整內容"


def test_long_file_keeps_head_and_tail_with_marker(tmp_path):
    head_part = "H" * 5000
    tail_part = "T" * 3000
    f = tmp_path / "next-phase-x.md"
    f.write_text(head_part + tail_part, encoding="utf-8")
    out = read_artifact_sampled(str(f), head=4500, tail=1500)
    assert out.startswith("H" * 4500), "開頭 4500 字必須保留"
    assert out.endswith("T" * 1500), "結尾 1500 字必須保留（授權段常在文末）"
    assert "中段省略" in out and "8000 字" in out, "截斷必須明確標記且附全文字數"


def test_missing_file_returns_empty(tmp_path):
    assert read_artifact_sampled(str(tmp_path / "nope.md")) == ""


def test_bom_tolerated(tmp_path):
    f = tmp_path / "next-phase-x.md"
    f.write_bytes(b"\xef\xbb\xbfBOM body")
    assert read_artifact_sampled(str(f)) == "BOM body"


def test_parameterized_budget(tmp_path):
    """採樣預算參數化：plan_review 用大預算（8000+2000）同一函式服務。"""
    f = tmp_path / "plan.md"
    f.write_text("A" * 9000 + "Z" * 4000, encoding="utf-8")
    out = read_artifact_sampled(str(f), head=8000, tail=2000)
    assert out.startswith("A" * 8000)
    assert out.endswith("Z" * 2000)
    assert "13000 字" in out


def test_sample_text_inline():
    """inline 全文（如 tool_input.plan）同樣經採樣規則。"""
    text = "X" * 4000
    assert sample_text(text, head=4500, tail=1500) == text  # 未超長直通
    long_text = "X" * 5000 + "Y" * 2000
    out = sample_text(long_text, head=4500, tail=1500)
    assert out.startswith("X" * 4500) and out.endswith("Y" * 1500)
    assert "中段省略" in out
