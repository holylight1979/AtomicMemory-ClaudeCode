"""verify_rules_sentinel.py: rules/coding-style.md 寫的哨兵格式 ↔ hooks/wg_verify_ledger.parse_sentinels 的判決一致（Q7 的 R1）。

守住：
- 規則文件兩條格式（`<NAME>_CHECK PASS|FAIL`、量測 `<NAME> DONE k=v`）從檔案原文抽出，抽不到就紅（規則被改掉時不靜默）。
- 同一組正例：規則格式命中、帳本也收成同名同結論的收據。
- 同一組反例：缺字尾 `X_CHECK`、小寫、`PASSED`、散文「測試通過」→ 規則格式不命中、帳本也不收。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parents[2]
RULES = CLAUDE / "rules" / "coding-style.md"
sys.path.insert(0, str(CLAUDE / "hooks"))
import wg_verify_ledger as vl  # noqa: E402


def _rule_patterns() -> dict:
    text = RULES.read_text(encoding="utf-8")
    check = re.search(r"`(\^\[A-Z\][^`]*_CHECK[^`]*)`", text)
    done = re.search(r"`(\^\[A-Z\][^`]* DONE[^`]*)`", text)
    assert check and done, "rules/coding-style.md 自檢段找不到兩條哨兵格式"
    return {"check": re.compile(check.group(1)), "done": re.compile(done.group(1))}


def test_rules_document_both_formats():
    pats = _rule_patterns()
    assert pats["check"].pattern.endswith("(PASS|FAIL)$") and "DONE" in pats["done"].pattern


@pytest.mark.parametrize("line, name, verdict, kind", [
    ("FOO_CHECK PASS", "FOO_CHECK", "PASS", "check"),
    ("FOO_CHECK FAIL", "FOO_CHECK", "FAIL", "check"),
    ("MEMORY_INDEX DONE", "MEMORY_INDEX", "DONE", "done"),
    ("REFIX DONE files=3 pairs=1", "REFIX", "DONE", "done"),
])
def test_rule_format_and_ledger_agree_on_valid_lines(line, name, verdict, kind):
    assert _rule_patterns()[kind].match(line)
    got = [(r["name"], r["verdict"]) for r in vl.parse_sentinels(f"some output\n{line}\n")]
    assert (name, verdict) in got


@pytest.mark.parametrize("line", [
    "FOO_CHECK",              # 缺字尾不算 PASS
    "foo_check pass",         # 小寫
    "FOO_CHECK PASSED",       # 字尾黏字
    "測試通過",                # 散文
    "_CHECK PASS",            # 沒有名字
])
def test_rule_format_and_ledger_agree_on_invalid_lines(line):
    pats = _rule_patterns()
    assert not pats["check"].match(line) and not pats["done"].match(line)
    assert vl.parse_sentinels(f"x\n{line}\n") == []
