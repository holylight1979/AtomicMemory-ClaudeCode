"""verify_console_skill.py：/console skill 的結構守門（來源指得回去、三種用法在、給人讀的說明含四處修正）。

正例：SKILL.md ≤150 行且三種用法都在；每個 [[卡名]] 在 memory/ 或 _AIDocs/_atoms/ 找得到檔；
SKILL.md 連到的 references 檔都存在；guide-for-humans 有兩個例外、Reload 改名、模型依工作分、寫交接備忘。
反例：卡片改名或退役後 SKILL.md 還指舊名 → 紅（提醒同步改 skill）。
怎麼跑：python -X utf8 -m pytest -q skills/console/verify/verify_console_skill.py
"""
from __future__ import annotations

import re
from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[3]
SKILL_DIR = CLAUDE / "skills" / "console"
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def test_skill_md_size_and_three_usages():
    assert len(SKILL.splitlines()) <= 150
    for usage in ("/console 對人", "/console 調度", "/console 開工句 <軌名>"):
        assert usage in SKILL


def test_every_card_link_resolves():
    names = {p.stem for d in ("memory", "_AIDocs/_atoms") for p in (CLAUDE / d).rglob("*.md")}
    slugs = re.findall(r"\[\[([^\]]+)\]\]", SKILL)
    assert slugs
    assert [s for s in slugs if s not in names] == []


def test_linked_references_exist():
    links = set(re.findall(r"\]\((references/[^)]+)\)", SKILL))
    assert links
    assert [p for p in links if not (SKILL_DIR / p).is_file()] == []


def test_guide_for_humans_has_four_fixes():
    guide = (SKILL_DIR / "references" / "guide-for-humans.md").read_text(encoding="utf-8")
    assert "放行這一回合" in guide and "Reload Window" in guide   # 兩個叫人去工作分頁的例外
    assert "名字全部重編" in guide                                  # Reload 改名
    assert "調度用 Opus" in guide and "Fable" in guide             # 模型依工作分
    assert "寫交接備忘" in guide                                    # 口令
