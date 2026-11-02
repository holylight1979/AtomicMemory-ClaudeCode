"""verify_entry_wording.py：切入點自評實測出會把 AI 帶錯的擋訊息字句，改成先分辨情況再給處置；只改字句，擋的條件不變。

逐處對自評文件（_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-2026-10-21.md）那一節：
  E05 提問前先讀部位（hooks/wg_release_rules.ask_overview_verdict）、E11 退避舉證（hooks/handlers/user_prompt_submit.evasion_ask）、
  SmellGate 處置句（tools/project-smells.render_commit_report）。
每處兩件事：新字句在、舊的誤導句不在。
gemma4:e4b 改前／改後實測紀錄在同目錄的 LLM切入點自評-實測/cases_003.json、results_003.jsonl。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_entry_wording.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
TREE = HOOKS_DIR.parent
for p in (str(TREE), str(HOOKS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_release_rules as rr  # noqa: E402
from handlers.user_prompt_submit import evasion_ask  # noqa: E402

_spec = importlib.util.spec_from_file_location("project_smells_wording", TREE / "tools" / "project-smells.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)


# ─── E05：提問前先讀部位 ───────────────────────────────────────────────────────

ASK = {"questions": [{"question": "TWD 換算要用哪個做法？", "header": "做法",
                      "options": [{"label": "A. 在 report/csv_export.py 輸出時換算"}, {"label": "B. 在 report/loader.py 讀入時換算"}]}]}


def test_ask_overview_says_read_before_regrouping_not_only_reminder():
    v = rr.ask_overview_verdict("AskUserQuestion", ASK, 0, named=(("report/loader.py", "讀入", 0),))
    hit = rr.format_hit("提問", v)
    assert v.owed and "先讀過部位檔再問（這條不單獨擋；但這題被別條擋下要重組時，先讀題目提到、還沒讀的部位檔" in hit
    assert "讀完再定推薦，或判斷根本不必問" in hit
    assert "只提醒，不因這條擋" not in hit                          # 反例：舊括號等於叫模型略過
    v2 = rr.ask_overview_verdict("AskUserQuestion", ASK, 0)
    assert v2.owed and "這條不單獨擋" in v2.why


def test_ask_overview_condition_unchanged():
    assert not rr.ask_overview_verdict("AskUserQuestion", ASK, 0, named=(("report/loader.py", "讀入", 2),)).owed
    assert not rr.ask_overview_verdict("AskUserQuestion", ASK, 3).owed
    plain = {"questions": [{"question": "今天要先看哪份報表？", "header": "報表", "options": [{"label": "日報"}]}]}
    assert not rr.ask_overview_verdict("AskUserQuestion", plain, 0).owed


# ─── E11：退避舉證 ─────────────────────────────────────────────────────────────

def test_evasion_ask_says_handle_first_and_writes_the_rule_not_card_names():
    t = evasion_ask({"phrase": "之後再", "context_excerpt": "x" * 300, "hint": "真的不做 → 寫一行「不做｜<哪一件>：<理由>」"})
    assert t.startswith("[Guardian:Evasion] 你上輪用了退避語『之後再』")
    assert "先處理這件，再做使用者這回合的新請求（只回新請求、不理這段，不算處理）" in t
    assert "成本小（幾行、一支測試）就這一回合先做掉" in t and "使用者換了話題不等於放行" in t
    assert "…" + "x" * 200 + "…" in t and "x" * 201 not in t
    assert t.rstrip().endswith("真的不做 → 寫一行「不做｜<哪一件>：<理由>」")
    assert "feedback-rigor-standards" not in t and "feedback atom" not in t


# ─── SmellGate 處置句 ──────────────────────────────────────────────────────────

HIT = {"name": "例外被吞掉", "why": "except 後直接 pass", "fix": "至少記 log", "path": "src/legacy_util.py", "line": 10,
       "text": "except Exception: pass"}


def test_smellgate_disposal_asks_whose_file_first():
    msg, hint = ps.render_commit_report([{"new": [HIT], "listed": [], "old": [], "allowed": [], "notes": []}], "<repo>")
    assert hint is None and msg.startswith("[Guardian:SmellGate]")                       # 照樣擋
    last = msg.splitlines()[-1]
    assert last.startswith("處置先分清被點名的段落是不是你這次任務寫的：是 → 把 ✗ 那幾行改掉再 commit")
    assert "`smell-ok: <為什麼>`" in last and "不是你這次寫的 → 不修，修它就偏離了使用者這次要的事" in last
    assert "只提交你自己的檔" in last and "舊碼原樣搬動或改名、合併進來的別人分支，原樣再送一次" in last
    assert "繞閘" not in last and last.endswith("--commit-check --cwd <repo>")   # 繞閘宣告已拔，沒有閘讀那行
    assert "處置：把 ✗" not in msg                                 # 反例：舊句不分是不是你的檔，帶 AI 去代刀
    ok, only = ps.render_commit_report([{"new": [], "listed": [HIT], "old": [], "allowed": [], "notes": []}], "<repo>")
    assert ok is None and "處置" not in only                        # 沒有新寫進的病：不擋、不印處置
