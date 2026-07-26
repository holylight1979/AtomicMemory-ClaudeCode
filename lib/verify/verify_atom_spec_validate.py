"""verify_atom_spec_validate.py — atom_spec.validate_atom_content 知識/印象二選一守門.

守住規則（與 KNOWLEDGE_SECTIONS / memory-audit validate_format 對齊）：
- ## 知識 或 ## 印象 擇一即過（指標型 atom 用 ## 印象 取代 ## 知識）
- 兩者皆缺 → 違規
- ## 行動 / # 標題 / Confidence 檢查不變
"""

from __future__ import annotations

import sys
from pathlib import Path

LIB_PARENT = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude/
if str(LIB_PARENT) not in sys.path:
    sys.path.insert(0, str(LIB_PARENT))

from lib.atom_spec import (  # noqa: E402
    KNOWLEDGE_SECTIONS, build_atom_content, validate_atom_content,
)


def _atom(section: str) -> str:
    return (
        "# 測試 atom\n\n"
        "- Scope: global\n"
        "- Confidence: [臨]\n"
        "- Trigger: a, b, c\n\n"
        f"## {section}\n\n- 內容\n\n"
        "## 行動\n\n- 行動項\n"
    )


def test_knowledge_sections_constant_covers_both():
    assert KNOWLEDGE_SECTIONS == frozenset({"知識", "印象"})


def test_knowledge_section_passes():
    assert validate_atom_content(_atom("知識")) is None


def test_impression_section_passes():
    """指標型 atom：## 印象 取代 ## 知識，validate 不得再硬 require ## 知識。"""
    assert validate_atom_content(_atom("印象")) is None


def test_missing_both_knowledge_and_impression_fails():
    err = validate_atom_content(_atom("其他段"))
    assert err is not None and "知識" in err and "印象" in err


def test_missing_action_still_fails():
    content = _atom("印象").replace("## 行動", "## 其他")
    assert validate_atom_content(content) == "Missing ## 行動 section"


def test_build_atom_content_output_still_valid():
    content = build_atom_content(
        title="t", scope="global", confidence="[臨]",
        triggers=["a"], knowledge=["k"],
    )
    assert validate_atom_content(content) is None
