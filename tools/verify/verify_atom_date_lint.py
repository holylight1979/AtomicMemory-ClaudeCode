"""verify_atom_date_lint — atom-date-lint 的剝日期規則，與「索引內 atom 知識行零敘事型日期」的活體守門。

跑法：python -m pytest -q tools/verify/verify_atom_date_lint.py
前半純函式；最後一案掃真實索引（episodic／_distant 不掃），背景收割寫進帶日期的 atom 會在這裡現形。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("atom_date_lint", CLAUDE_DIR / "tools" / "atom-date-lint.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["atom_date_lint"] = _mod
_spec.loader.exec_module(_mod)


def strip(line: str) -> str:
    new, _ = _mod._fix_line(line, False)
    return new


def test_paren_only_date_removed_with_parens():
    assert strip("- [臨] 實踩（2026-10-05）：新建的 repo") == "- [臨] 實踩：新建的 repo"


def test_date_at_paren_edges_leaves_rest():
    assert strip("- [臨]（2026-08-13 AppB T8d 實例）給契約加欄位") == "- [臨]（AppB T8d 實例）給契約加欄位"
    assert strip("- [觀] 同型再現（GameA 2026-08-25）：") == "- [觀] 同型再現（GameA）："
    assert strip("- [固] 覆轍實例（Realm S1–S3，2026-06）：") == "- [固] 覆轍實例（Realm S1–S3）："


def test_cjk_neighbours_do_not_keep_space():
    assert strip("- [臨] 使用者 2026-10-07 糾正：X") == "- [臨] 使用者糾正：X"
    assert strip("- [固] user 2026-07 明確拉高") == "- [固] user 明確拉高"


def test_reference_dates_and_fact_dates_kept():
    assert strip("- 日落檢視：約 2026-08-28 後再評估") == "- 日落檢視：約 2026-08-28 後再評估"
    assert strip("- [觀] 7.6 支援到 2028-11-14；7.5 於 2026-11-10 EOL") == "- [觀] 7.6 支援到 2028-11-14；7.5 於 2026-11-10 EOL"
    assert strip("- [臨] 2026-09-10 起交棒版本改為 codeMtime()") == "- [臨] 2026-09-10 起交棒版本改為 codeMtime()"


def test_code_spans_paths_and_metadata_untouched():
    assert strip("- [臨] 舊卡有 `- Last-used: 2026-04-23` 欄") == "- [臨] 舊卡有 `- Last-used: 2026-04-23` 欄"
    assert strip("- 見 plans/memory-cleanup-2026-04-27/plan.md") == "- 見 plans/memory-cleanup-2026-04-27/plan.md"
    assert strip("- Created-at: 2026-10-07") == "- Created-at: 2026-10-07"
    assert strip("- Source: session:04716181#80cc7e83 2026-10-07") == "- Source: session:04716181#80cc7e83 2026-10-07"


def test_legacy_created_lines_and_changelog_rows_dropped():
    assert strip("- Created: 2026-03-19") is None
    assert strip("| 2026-03-13 | 初始建立 | manual |") is None


def test_headings_and_date_fact_table_rows_kept():
    # Codex 審真實 commit 020be33 抓到：標題會被改、日期開頭的事實表格列會被整行刪
    assert strip("## 2026-05-14 升版紀錄") == "## 2026-05-14 升版紀錄"
    assert strip("| 2024-11-12 | .NET 6 EOL |") == "| 2024-11-12 | .NET 6 EOL |"
    assert strip("| 2028-11-14 | 7.6 支援到 |") == "| 2028-11-14 | 7.6 支援到 |"


def test_indexed_atoms_have_no_narrative_dates():
    """活體守門：索引內 atom 知識行零敘事型日期。失敗就跑 python tools/atom-date-lint.py 看是哪幾行，--fix 清掉。"""
    dirty = [(p, ch) for p in _mod.indexed_atoms() for ch, _ in [_mod.process(p)] if ch]
    assert not dirty, "帶敘事型日期的 atom：" + "、".join(p.name for p, _ in dirty[:5])
