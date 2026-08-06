"""verify_prompt_input_integrity.py — 送 codex 的輸入完整性守門。

守門原則（artifact_io module docstring 的統一原則）：
  * 引用檔案類 artifact 必附實體內容——plan_review 的計畫正文必須真的在
    送出的 prompt 內，動作紀錄不得替代內容本體（歷史實案：plan_content
    從未被組裝、100% fallback 成 tool trace，codex 恆回「未收到正文」）。
  * 所有截斷 in-band 標記；集合截斷附計數標頭。
全部離線：對 assessor.build_prompt / build_prompt_budgeted 純函式斷言，不打 codex。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

CLAUDE_DIR = Path(__file__).resolve().parents[3]
COMP_DIR = Path(__file__).resolve().parent.parent
if str(COMP_DIR) not in sys.path:
    sys.path.insert(0, str(COMP_DIR))
if str(CLAUDE_DIR / "hooks") not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR / "hooks"))

import assessor  # noqa: E402
import prompts  # noqa: E402
import codex_companion as cc  # noqa: E402


def _plan_trace(plan_path: str) -> list:
    return [
        {"tool": "Bash", "input": "git status", "output_summary": "stdout: clean", "path": ""},
        {"tool": "Write", "input": plan_path, "output_summary": "", "path": plan_path},
        {"tool": "ExitPlanMode", "input": "{}", "output_summary": "", "path": ""},
    ]


# ─── plan_review：正文實體必須在 prompt 內 ───────────────────────────────────


def test_plan_review_contains_file_body(tmp_path):
    plan = tmp_path / "plans" / "big-plan.md"
    plan.parent.mkdir()
    body = "PLANHEAD_" + "A" * 12000 + "_PLANTAIL"  # > 8000+2000 → 觸發採樣
    plan.write_text(body, encoding="utf-8")

    p = assessor.build_prompt(
        "plan_review", _plan_trace(str(plan)), str(tmp_path),
        {"turn_index": 1, "artifact_path": str(plan)},
    )
    assert "PLANHEAD_" in p, "計畫開頭必須在 prompt 內"
    assert "_PLANTAIL" in p, "計畫結尾必須在 prompt 內（頭尾採樣保尾段）"
    assert "中段省略" in p and f"{len(body)} 字" in p, "採樣截斷必須附標記+全文字數"
    assert "(no plan content available)" not in p
    assert "未解析到計畫 artifact" not in p


def test_plan_review_inline_fallback(tmp_path):
    p = assessor.build_prompt(
        "plan_review", [], str(tmp_path),
        {"turn_index": 1, "plan_inline": "INLINE_PLAN_BODY step1 step2"},
    )
    assert "INLINE_PLAN_BODY step1 step2" in p


def test_plan_review_never_substitutes_trace_for_body(tmp_path):
    """無 artifact 時 prompt 必須明說「無正文」，而非拿 trace 冒充。"""
    trace = _plan_trace("not-a-plan-location.md")
    p = assessor.build_prompt("plan_review", trace, str(tmp_path), {"turn_index": 1})
    assert "未解析到計畫 artifact" in p and "missing_evidence" in p


def test_plan_review_read_failure_marked(tmp_path):
    p = assessor.build_prompt(
        "plan_review", [], str(tmp_path),
        {"turn_index": 1, "artifact_path": str(tmp_path / "gone.md")},
    )
    assert "讀取失敗" in p and "missing_evidence" in p


# ─── hook 端：artifact 解析與 EnterPlanMode 防呆 ─────────────────────────────


def test_resolve_plan_artifact_finds_latest_plans_write():
    trace = [
        {"tool": "Write", "path": "C:\\x\\.claude\\plans\\old.md"},
        {"tool": "Bash", "path": ""},
        {"tool": "Write", "path": "C:\\x\\.claude\\plans\\latest.md"},
        {"tool": "Edit", "path": "C:\\x\\.claude\\hooks\\foo.py"},
    ]
    path, inline = cc._resolve_plan_artifact({}, trace)
    assert path.endswith("latest.md")
    assert inline == ""


def test_resolve_plan_artifact_inline_from_tool_input():
    path, inline = cc._resolve_plan_artifact({"plan": "# inline plan"}, [])
    assert path == "" and inline == "# inline plan"


def test_resolve_plan_artifact_empty_means_skip():
    """兩層 fallback 皆空 = handle_post_tool_use 的 skip 條件（不空審）。"""
    assert cc._resolve_plan_artifact({}, [{"tool": "Bash", "path": ""}]) == ("", "")


def test_enter_plan_mode_does_not_trigger():
    """EnterPlanMode 當下計畫不存在，不得觸發 plan_review（歷史 100% 空審）。"""
    cfg = {"soft_gate": {"handoff_review": True}}
    assert cc._detect_checkpoint("EnterPlanMode", "", cfg) is None
    assert cc._detect_checkpoint("ExitPlanMode", "", cfg) == "plan_review"


# ─── handoff_review：遷移後不退化 ────────────────────────────────────────────


def test_handoff_review_contains_file_body(tmp_path):
    f = tmp_path / "next-phase-x.md"
    f.write_text("HANDOFF_BODY_TOKEN 授權條件…", encoding="utf-8")
    p = assessor.build_prompt(
        "handoff_review", [], str(tmp_path),
        {"turn_index": 2, "artifact_path": str(f)},
    )
    assert "HANDOFF_BODY_TOKEN" in p


# ─── turn_audit：背景 + 集合截斷計數標頭 ─────────────────────────────────────


def test_turn_audit_has_user_goal_and_trace_header(tmp_path):
    trace = [
        {"tool": "Bash", "input": f"cmd {i}", "output_summary": "", "path": ""}
        for i in range(40)
    ]
    p = assessor.build_prompt(
        "turn_audit", trace, str(tmp_path),
        {"turn_index": 3, "user_goal": "USER_GOAL_TOKEN 修輸入組成",
         "last_assistant_tail": "done", "trace_dropped": 10},
    )
    assert "USER_GOAL_TOKEN" in p, "user_goal 必須進 prompt（brief 背景要件）"
    assert "showing last 30 of 50 tool events" in p, \
        "集合截斷必附計數標頭（40 條 in-trace + 10 條 state 端已丟）"


# ─── 總量預算：超額縮 trace 一次、artifact 永不砍、有標記 ────────────────────


def test_budget_reduces_trace_not_artifact(tmp_path):
    plan = tmp_path / "plans" / "p.md"
    plan.parent.mkdir()
    plan.write_text("PLANHEAD_" + "B" * 12000 + "_PLANTAIL", encoding="utf-8")
    trace = [
        {"tool": "Bash", "input": "x" * 200, "output_summary": "y" * 150, "path": ""}
        for _ in range(200)
    ]
    ctx = {"turn_index": 1, "artifact_path": str(plan)}
    cfg = {"max_prompt_chars": 12000}  # 預算可 config 調整；測試用低值觸發縮減路徑
    budgeted = assessor.build_prompt_budgeted(
        "plan_review", trace, str(tmp_path), ctx, cfg,
    )
    # 用 turn_audit（trace 全量入 prompt）驗縮減路徑
    t_full = assessor.build_prompt("turn_audit", trace, str(tmp_path), ctx)
    assert len(t_full) > 12000, "前置條件：30 條長 trace 的 turn_audit 必須超過測試預算"
    t_budgeted = assessor.build_prompt_budgeted(
        "turn_audit", trace, str(tmp_path), ctx, cfg,
    )
    assert len(t_budgeted) < len(t_full), "超額必須縮減重組"
    assert "因 prompt 總量預算" in t_budgeted, "縮減必須 in-band 標記"
    assert "showing last 8 of" in t_budgeted, "縮減後 trace 上限 8 條"
    # artifact 正文在預算縮減下完好
    assert "PLANHEAD_" in budgeted and "_PLANTAIL" in budgeted


# ─── 模板誠實化：不再宣稱含未監測工具 ────────────────────────────────────────


def test_templates_honest_about_monitoring_scope():
    for tpl in (prompts.PLAN_REVIEW, prompts.TURN_AUDIT):
        assert "do NOT infer" in tpl, "模板必須明示監測範圍限制，防「未讀檔」誤報"
        assert "includes both direct Read/Glob/Grep" not in tpl, \
            "不得再宣稱 Files Examined 含 Read/Glob/Grep（matcher 收不到）"
