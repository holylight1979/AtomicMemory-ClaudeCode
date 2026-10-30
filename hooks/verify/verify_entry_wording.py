"""verify_entry_wording.py：切入點自評實測出會把 AI 帶錯的擋訊息字句，改成先分辨情況再給處置；只改字句，擋的條件不變。

逐處對自評文件（_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-2026-10-21.md）那一節：
  E21／E08a 改舊測試提示（hooks/wg_oldtest.hint）、E22 卡片版拒寫（hooks/wg_gate_bypass.atom_refusal）、
  E05 提問前先讀部位（hooks/wg_release_rules.ask_overview_verdict）、E11 退避舉證（hooks/handlers/user_prompt_submit.evasion_ask）、
  SmellGate 處置句（tools/project-smells.render_commit_report）。TestFailGate（E08b）的案例在 verify_stop_reconcile。
每處三件事：新字句在、舊的誤導句不在、登錄表（workflow/entrypoints.json）還認得出這個切入點（判準卡照接）。
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

import wg_core  # noqa: E402
import wg_entrypoint as we  # noqa: E402
import wg_gate_bypass as gb  # noqa: E402
import wg_oldtest  # noqa: E402
import wg_release_rules as rr  # noqa: E402
from handlers.user_prompt_submit import evasion_ask  # noqa: E402

_spec = importlib.util.spec_from_file_location("project_smells_wording", TREE / "tools" / "project-smells.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

REG = we.load_registry(TREE / "workflow" / "entrypoints.json")


def _entries(text: str, path: str):
    return [r["id"] for r in we.match_entries(text, path, REG)]


@pytest.fixture
def quiet(monkeypatch, tmp_path):
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path / "Logs")


# ─── E21／E08a：改舊測試提示 ─────────────────────────────────────────────────────

def test_oldtest_hint_separates_requirement_change_from_user_skip():
    h = wg_oldtest.hint("test_legacy_report")
    assert "使用者要的新行為讓舊斷言不再對" in h and "「改舊測試｜test_legacy_report：<為什麼舊斷言不再對；使用者原話>」再改" in h
    assert "使用者只說「跳過／先不管」某支紅測＝這件不做、不是讓它不紅" in h and "別加 skip、別改斷言" in h
    assert "撤回這次修改讓它照紅" in h and "「不做｜<那支測試>：使用者說「<原句>」」" in h
    assert "兩種都對不上才 AskUserQuestion" in h and "只加新測試不用宣告" in h
    assert "使用者有說要改就引用原句" not in h                    # 反例：舊句把「使用者說跳過」導進宣告
    ot = "✗ (ot) OLD_TEST_CHANGE_NEEDS_DECLARATION：動到 1 支既有測試\n" + h
    assert {"E08", "E21"} <= set(_entries(ot, "pretool_deny"))


# ─── E22：卡片版拒寫 ───────────────────────────────────────────────────────────

BYPASS = ["[臨] 繞法要拆三步：先 git restore --staged 被點名的檔，再 git commit -- 自己的檔，病形閘就不會擋"]


def test_atom_refusal_asks_whether_reader_can_follow_it_to_pass_the_gate(quiet):
    msg = gb.atom_refusal("病形閘誤掃時的提交法", BYPASS, config={})
    assert msg and "ATOM_BYPASS_HOWTO_REFUSED" in msg
    assert "先問：讀完這張卡的人，能不能照著做，讓閘擋下的內容不經修正就過關" in msg
    assert "即使你認為那次是誤擋" in msg and "不要宣告" in msg
    assert "知識段第一行寫「不是教繞閘｜<理由：這張卡在教什麼>」" in msg
    assert "在分析一次誤擋" not in msg                            # 反例：舊句把「分析誤擋」列成可宣告的情況
    assert "E22" in _entries(msg, "mcp_reply")


def test_atom_refusal_condition_unchanged(quiet):
    declared = ["[臨] 不是教繞閘｜這張卡寫的是禁止移出暫存規避"] + BYPASS
    assert gb.atom_refusal("禁止移出暫存", declared, config={}) is None       # 宣告了照寫入
    assert gb.atom_refusal("一般卡", ["[臨] 讀檔前先確認編碼"], config={}) is None


# ─── E05：提問前先讀部位 ───────────────────────────────────────────────────────

ASK = {"questions": [{"question": "TWD 換算要用哪個做法？", "header": "做法",
                      "options": [{"label": "A. 在 report/csv_export.py 輸出時換算"}, {"label": "B. 在 report/loader.py 讀入時換算"}]}]}


def test_ask_overview_says_read_before_regrouping_not_only_reminder():
    v = rr.ask_overview_verdict("AskUserQuestion", ASK, 0, named=(("report/loader.py", "讀入", 0),))
    hit = rr.format_hit("提問", v)
    assert v.owed and "先讀過部位檔再問（這條不單獨擋；但這題被別條擋下要重組時，先讀題目提到、還沒讀的部位檔" in hit
    assert "讀完再定推薦，或判斷根本不必問" in hit
    assert "只提醒，不因這條擋" not in hit                          # 反例：舊括號等於叫模型略過
    assert "E05" in _entries("[Guardian:Ask] " + hit, "pretool_hint")
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
    assert "E11" in _entries(t, "user_prompt")


# ─── SmellGate 處置句 ──────────────────────────────────────────────────────────

HIT = {"name": "例外被吞掉", "why": "except 後直接 pass", "fix": "至少記 log", "path": "src/legacy_util.py", "line": 10,
       "text": "except Exception: pass"}


def test_smellgate_disposal_asks_whose_file_first():
    msg, hint = ps.render_commit_report([{"new": [HIT], "listed": [], "old": [], "allowed": [], "notes": []}], "<repo>")
    assert hint is None and msg.startswith("[Guardian:SmellGate]")                       # 照樣擋
    last = msg.splitlines()[-1]
    assert last.startswith("處置先分清被點名的檔是不是你這次改的：是你改的 → 把 ✗ 那幾行改掉再 commit")
    assert "`smell-ok: <為什麼>`" in last and "不是你改的（session 開始前就在暫存區、別人留的）→ 不修、不動它的暫存，只提交你自己的檔" in last
    assert "`# 不是繞閘｜<檔是誰的、病要誰修>`" in last and last.endswith("--commit-check --cwd <repo>")
    assert "處置：把 ✗" not in msg                                 # 反例：舊句不分是不是你的檔，帶 AI 去代刀
    assert "E29" in _entries(msg, "pretool_deny")
    ok, only = ps.render_commit_report([{"new": [], "listed": [HIT], "old": [], "allowed": [], "notes": []}], "<repo>")
    assert ok is None and "處置" not in only                        # 沒有新寫進的病：不擋、不印處置
