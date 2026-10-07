"""verify_rule_atom_style_gate — 規則型 atom（行為契約／工作流）的知識行不得帶日期戳或 config 鍵名。

跑法：python -m pytest -q lib/verify/verify_rule_atom_style_gate.py
純函式測 lib.atom_io.rule_atom_style_violation；不碰真實記憶庫。
"""
from __future__ import annotations

import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lib.atom_io import rule_atom_style_violation as viol  # noqa: E402

RULE = Path(r"C:\x\.claude\memory\行為契約\某規則.md")
WF = Path(r"C:\x\.claude\memory\工作流\節奏與收尾\preferences.md")
FAIL = Path(r"C:\x\.claude\memory\Failures\行為契約\feedback-x.md")
OTHER = Path(r"C:\x\.claude\memory\dotnet\x.md")


def test_date_stamp_rejected_in_rule_dirs():
    assert viol(RULE, ["[臨] 2026-10-07 使用者定：直上版控"]) is not None
    assert viol(WF, ["[固] 口令例外（2026-10-07）"]) is not None


def test_dotted_config_key_rejected():
    err = viol(RULE, ["[臨] 閘門放行見 guard.commit_order.exempt_cwd_under_claude_dir"])
    assert err and "guard.commit_order.exempt_cwd_under_claude_dir" in err


def test_plain_rule_line_passes():
    assert viol(WF, ["[固] 原子記憶系統相關的不用問、直上版控；其他專案程式碼等口令。規則見 rules/core.md「版控」段"]) is None


def test_urls_paths_and_versions_not_false_positive():
    assert viol(RULE, ["見 https://docs.example.com/a.b.c 與 tools/x.py，版本 v5.1.0"]) is None
    assert viol(RULE, ["檔案 lib/atom_io.py 的 write_atom"]) is None


def test_feedback_atoms_reject_dates_but_allow_config_keys():
    assert viol(FAIL, ["[臨] 使用者指正（2026-10-06）：亂碼直接修"]) is not None
    assert viol(FAIL, ["[臨] 使用者指正：亂碼直接修；閘見 guard.commit_order.keywords"]) is None


def test_failure_story_and_other_domains_exempt():
    story = Path(r"C:\x\.claude\memory\Failures\版控\某踩坑.md")
    assert viol(story, ["[臨] 始末（2026-10-06）：…guard.commit_order.keywords"]) is None
    assert viol(OTHER, ["[固] 2026-09-21 實測 R@1 81%"]) is None


def test_non_string_and_empty_knowledge_ignored():
    assert viol(RULE, None) is None
    assert viol(RULE, [123, ""]) is None  # type: ignore[list-item]
