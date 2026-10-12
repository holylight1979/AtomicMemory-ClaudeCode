"""verify_user_extract_session_directive.py：一次性 session 指示（派工開工句）不送萃取，萃取紀錄留 skip 原因。

正例：四張曾被誤寫成根層 atom 的開工句（卡片 Quote 原句）→ 程式前置判斷命中，不送 L1／L2，
      _merge_history.log 寫一行「action=user-extract-skip reason=session-directive(...)」，批次統計 skipped_directive。
反例：一般跨專案決策（「以後 commit message 一律繁體中文」等）→ 不命中，照常送 L1／L2。
另驗：worker 讀的判斷樣板來自程式碼樹，且 L1／L2 樣板都有「只在這個 session 有效的指示不算」準則。
退回舊碼：開工句也送 L1 → 管線案紅在斷言。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_user_extract_session_directive.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_ROOT = HOOKS_DIR.parent
for p in (HOOKS_DIR, CLAUDE_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# 被退役卡（memory/版控/_distant/2026_10/ 的四張）的 Quote 原句（寫入時截在 200 字）
KICKOFFS = [
    "你是 v6.0 的工作 session track-goal（需求目標核心流程設計單，只設計不寫程式），總控台是 claude-ad。第一步用 EnterWorktree 切進 "
    "worktree C:\\Users\\holylight\\.claude-wt\\track-goal（分支 v6/track-goal，已存在，不要新建）。派工 prompt 在 C:\\Users\\holylight\\.c…",
    "你是 v6.0 的工作 session track-g12（閱讀路徑掃描器），總控台是 claude-ad。第一步用 EnterWorktree 切進 worktree "
    "C:\\Users\\holylight\\.claude-wt\\track-g12（分支 v6/track-g12，已存在，不要新建）。派工 prompt 在 C:\\Users\\holylight\\.claude\\workflow\\…",
    "你是 v6.0 的工作 session track-verify（獨立實跑驗證），總控台是 claude-ad。第一步用 EnterWorktree 切進 worktree "
    "C:\\Users\\holylight\\.claude-wt\\track-verify（detached，已存在，不要新建）。派工 prompt 在 C:\\Users\\holylight\\.claude\\workflow\\v6…",
    "你是 v6.0 的工作 session track-b2，總控台是 claude-4b。派工 prompt 在 C:\\Users\\holylight\\.claude\\workflow\\v6-inbox\\"
    "to-track-b2\\000-prompt.md，用絕對路徑讀完全文照做。worktree C:\\Users\\holylight\\.claude-wt\\track-b2（分支 v6/track-…",
]
DECISIONS = [
    "以後 commit message 一律繁體中文",
    "記住：commit message 要寫中文",
    "禁止在 hook 裡跑 git push",
    "我偏好繁體中文回應",
    "你是不是忘了，以後一律用 pnpm",
    "以後每次改完都要跑 pytest 再交",
]


def _load_worker():
    spec = importlib.util.spec_from_file_location("uew_session_directive", HOOKS_DIR / "user-extract-worker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.mark.parametrize("text", KICKOFFS)
def test_kickoff_quotes_are_session_directives(text):
    assert _load_worker()._session_directive_reason(text) == "role"


@pytest.mark.parametrize("text", DECISIONS)
def test_cross_project_decisions_are_not_session_directives(text):
    assert _load_worker()._session_directive_reason(text) is None


def test_signals_without_role_need_two_kinds():
    m = _load_worker()
    assert m._session_directive_reason("第一步用 EnterWorktree 切進 worktree，派工單在 D:\\inbox\\7.md") == "first-step+session-op+dispatch-path"
    assert m._session_directive_reason("以後第一步都先跑測試") is None                     # 單一訊號不算


def test_prompt_templates_come_from_code_tree_and_carry_the_criterion(tmp_path, monkeypatch):
    import wg_core
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", tmp_path / "data-root")                  # 資料根與程式碼樹分開
    m = _load_worker()
    assert m._PROMPTS_DIR == CLAUDE_ROOT / "prompts"                                    # 反例：舊碼從資料根載樣板
    assert "只在這個 session 有效的指示不算" in m._load_l1_prompt("x")
    assert "只在這個 session 有效的指示不是決策" in m._load_l2_prompt("x", "")


def test_pipeline_skips_kickoff_before_llm_and_records_reason(tmp_path, monkeypatch):
    m = _load_worker()
    monkeypatch.setattr(m, "WORKFLOW_DIR", tmp_path)
    l1_seen, pending_seen = [], []
    monkeypatch.setattr(m, "_call_l1", lambda p: l1_seen.append(p) or True)
    monkeypatch.setattr(m, "_call_l2", lambda p: {"decision": True, "conf": 0.8, "scope": "shared",
                                                   "trigger": ["commit"], "statement": "commit message 一律繁體中文"})
    monkeypatch.setattr(m, "_write_pending_candidate",
                        lambda l2, cand, user, cwd, prefix="": pending_seen.append(cand["turn_id"]) or True)
    monkeypatch.setattr(m, "_get_assistant_last_600", lambda sid, cwd: "")
    monkeypatch.setattr(m, "evaluate_session", lambda *a, **k: {"scores": {"weighted_total": 0}})
    sid = "sd-test"
    state = {"pending_user_extract": [
        {"turn_id": f"{sid}-0", "prompt": KICKOFFS[0], "score": 1.0, "matched": ["一律"]},
        {"turn_id": f"{sid}-1", "prompt": DECISIONS[0], "score": 1.0, "matched": ["一律"]},
    ]}
    (tmp_path / f"state-{sid}.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    stats = m.run_user_extraction({"session_id": sid, "cwd": str(tmp_path), "user": "u",
                                   "config": {"userExtraction": {"tokenBudget": 2000}}})
    assert len(l1_seen) == 1 and DECISIONS[0] in l1_seen[0], l1_seen                  # 反例：舊碼開工句也送 L1
    assert pending_seen == [f"{sid}-1"] and stats["skipped_directive"] == 1
    log = (tmp_path / "_merge_history.log").read_text(encoding="utf-8")
    assert "action=user-extract-skip" in log and "reason=session-directive(role)" in log and f"turn={sid}-0" in log
    assert "skipped_directive=1" in log
    left = json.loads((tmp_path / f"state-{sid}.json").read_text(encoding="utf-8"))
    assert left.get("pending_user_extract") == []                                      # 兩筆都處理完、不留待重送
