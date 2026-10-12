"""verify_user_extract_session_directive.py：一次性 session 指示（派工開工句）不送萃取，萃取紀錄留 skip 原因。

正例：四張曾被誤寫成根層 atom 的開工句（卡片 Quote 原句）、開工句模板整段 → 每個子句都整句對上派工樣板，不送 L1／L2，
      _merge_history.log 寫一行「action=user-extract-skip reason=session-directive(...)」，批次統計 skipped_directive。
反例：開工句裡夾任何一個對不上樣板的子句（跨專案決策、操作限制…）、一般跨專案決策 → 交 L1／L2。
另驗：正式啟動端（_shared）把 worker 的 stderr 落到資料根 Logs/，紀錄寫不進時錯誤看得到、候選留在佇列。
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
    "你是我的長期 coding agent，記住所有專案一律先查證再修改。",                      # 角色開頭但帶長期用語 → 交 LLM
    "以後所有專案一律遵守：第一步用 EnterWorktree 隔離修改。",                         # 訊號兩種但是長期規則
    "你是工作 session track-x。這次修 UI。另外記住：以後所有專案 commit message 一律繁體中文。",   # 混合：交 LLM 抽長期段
    "你是工作 session track-x。第一步修 UI。另外，我偏好繁體中文回應。",                # 角色開頭但沒有派工操作或路徑
    "你是工作 session track-x。第一步修 UI。另外 commit message 用繁體中文。",          # 同上，且沒有任何決策用語
    "你是工作 session track-x，第一步用 EnterWorktree 切進 C:\\wt\\x。另外禁止在 hook 裡跑 git push。",   # 帶決策用語
]
# 開工句後面夾一句真正的決策：那一句沒有派工訊號 → 整則交 LLM（逐句判斷，不靠用語清單；換行也算句界）
MIXED_DECIDE = "你是工作 session track-x。第一步用 EnterWorktree 切進 C:\\wt\\x。另外，我決定 commit message 一律使用繁體中文。"
MIXED_DECIDE_NEWLINE = "你是工作 session track-x。第一步用 EnterWorktree 切進 C:\\wt\\x\n另外，我決定 commit message 一律使用繁體中文。"
DECISIONS += [MIXED_DECIDE, MIXED_DECIDE_NEWLINE,
              "你是\n工作 session track-x，本次一律只讀 C:\\wt\\x。",   # 角色被換行拆開：認不出就交 LLM（不誤丟優先）
              "你是工作 session track-x。第一步用 EnterWorktree 切進 C:\\wt\\x\n我決定備份目錄統一使用 D:\\backup。",
              "你是工作 session track-x。第一步用 EnterWorktree 切進 C:\\wt\\x\n備份目錄統一使用 D:\\backup。"]   # 有路徑但沒有派工語境的句子不算派工句
# 退件 026 的重現：開工句後面接跨專案決策或操作限制，那個子句對不上任何樣板 → 交 LLM
B1A = "你是工作 session，第一步用 EnterWorktree 切進 C:\\wt\\x，所有 repo 的 commit message 一律繁體中文。"
B1B = "你是工作 session。第一步用 EnterWorktree 切進 C:\\wt\\x。所有 repo 的 worktree 備份目錄統一用 D:\\backup。"
LIMITS = "你是工作 session track-x，第一步用 EnterWorktree 切進 C:\\wt\\x，只准處理 UI，一律先跑測試。"
NEWLINE_MIXED = "你是工作 session track-x\n第一步用 EnterWorktree 切進 C:\\wt\\x\n所有 repo 的 commit message 用繁體中文"
DECISIONS += [B1A, B1B, LIMITS, NEWLINE_MIXED]
# 欄位不能吞掉決策：頓號或直接接在路徑、名稱、分支、開工回覆後面的另一段話，整句要對不上樣板
PATH_SWALLOW = "你是工作 session track-x，本次一律只讀 C:\\wt\\x、所有專案一律禁止刪除備份。"
DECISIONS += [
    PATH_SWALLOW,
    "你是工作 session track-x，派工 prompt 在 C:\\inbox\\7.md、所有專案一律禁止刪除備份。",
    "你是工作 session track-x，本次一律只讀 C:\\wt\\x所有專案一律禁止刪除備份。",
    "你是工作 session track-x，總控台是 claude-ad所有專案一律禁止刪除備份。",
    "你是工作 session track-x，第一步用 EnterWorktree 切進 C:\\wt\\x（分支 v6/x、所有專案一律用 tab）。",
    "你是工作 session track-x，開工前先 SendMessage claude-ad 一句「所有專案一律禁止刪除備份」。",
]
# 開工句模板（workflow/v6-inbox/_console/開工句模板.md）填好的整段，與只用換行分句的純開工句
TEMPLATE_FILLED = (
    "你是 v6.0 的工作 session track-a3，總控台是 claude-ad。第一步用 EnterWorktree 切進 worktree "
    "C:\\Users\\holylight\\.claude-wt\\track-a3（分支 v6/track-a3，已存在，不要新建）。派工 prompt 在 "
    "C:\\Users\\holylight\\.claude\\workflow\\v6-inbox\\to-track-a3\\019-continue-017.md，用絕對路徑讀完全文照做。"
    "切進去之後所有讀寫一律用 worktree 絕對路徑、不碰 live C:\\Users\\holylight\\.claude；交付信附 live 未動證明。"
    "只跑目標 verify（直接在 worktree 根跑 pytest，不加 cd）、不跑全量、不重掛 Monitor、不輪詢。"
    "開工前先 SendMessage claude-ad 一句「track-a3 收到開工」。")
NEWLINE_KICKOFF = "你是工作 session track-x\n第一步用 EnterWorktree 切進 C:\\wt\\x"
# 開工句的常見改寫（不是「你是」開頭、英文、外層引號）
REWORDED_KICKOFFS = [
    "For this session, act as track-x. You must work only in C:\\wt\\x; read the task at C:\\inbox\\022.md.",
    "請接手本次工作 session track-x，一律只讀 C:\\wt\\x；派工單在 C:\\inbox\\022.md。",
    "「你是工作 session track-x，本次一律只讀 C:\\wt\\x。」",
]


def _load_worker():
    spec = importlib.util.spec_from_file_location("uew_session_directive", HOOKS_DIR / "user-extract-worker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _user_part(l1_prompt: str) -> str:
    """L1 樣板裡填進使用者那段（樣板的範例句不算）。"""
    return l1_prompt.rsplit("使用者的話：", 1)[1].split("\n\nJSON", 1)[0].strip()


@pytest.mark.parametrize("text", KICKOFFS)
def test_kickoff_quotes_are_session_directives(text):
    assert (_load_worker()._session_directive_reason(text) or "").startswith("role+")


@pytest.mark.parametrize("text", REWORDED_KICKOFFS)
def test_reworded_kickoffs_are_session_directives(text):
    assert _load_worker()._session_directive_reason(text)


@pytest.mark.parametrize("text", DECISIONS)
def test_cross_project_decisions_are_not_session_directives(text):
    assert _load_worker()._session_directive_reason(text) is None


def test_template_and_newline_kickoffs_match_clause_by_clause():
    m = _load_worker()
    assert m._session_directive_reason(TEMPLATE_FILLED) == "role+controller+step+dispatch+scope+deliver+verify+ack"
    assert m._session_directive_reason(NEWLINE_KICKOFF) == "role+step"                  # 反例：換行不切句就對不上樣板
    assert m._session_directive_reason(TEMPLATE_FILLED + "另外，所有 repo 都用 tab") is None   # 多一個子句對不上 → 交 LLM


def test_prompt_templates_come_from_code_tree_and_carry_the_criterion(tmp_path, monkeypatch):
    import wg_core
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", tmp_path / "data-root")                  # 資料根與程式碼樹分開
    m = _load_worker()
    assert m._PROMPTS_DIR == CLAUDE_ROOT / "prompts"                                    # 反例：舊碼從資料根載樣板
    assert "只在這個 session 有效的指示不算" in m._load_l1_prompt("x")
    assert "只在這個 session 有效的指示不是決策" in m._load_l2_prompt("x", "")


def _run_pipeline(tmp_path, monkeypatch, prompts):
    """替身 L1／L2（L2 回 conf 0.8 → 進候選）跑 run_user_extraction；回 (stats, L1 收到的, 進候選的 (turn, prompt), 萃取紀錄, 剩下的佇列)。"""
    m = _load_worker()
    monkeypatch.setattr(m, "WORKFLOW_DIR", tmp_path)
    l1_seen, pending_seen = [], []
    monkeypatch.setattr(m, "_call_l1", lambda p: l1_seen.append(p) or True)
    monkeypatch.setattr(m, "_call_l2", lambda p: {"decision": True, "conf": 0.8, "scope": "shared",
                                                   "trigger": ["commit"], "statement": "commit message 一律繁體中文"})
    monkeypatch.setattr(m, "_write_pending_candidate",
                        lambda l2, cand, user, cwd, prefix="": pending_seen.append((cand["turn_id"], cand["prompt"])) or True)
    monkeypatch.setattr(m, "_get_assistant_last_600", lambda sid, cwd: "")
    monkeypatch.setattr(m, "evaluate_session", lambda *a, **k: {"scores": {"weighted_total": 0}})
    sid = "sd-test"
    state = {"pending_user_extract": [{"turn_id": f"{sid}-{i}", "prompt": p, "score": 1.0, "matched": ["一律"]}
                                      for i, p in enumerate(prompts)]}
    (tmp_path / f"state-{sid}.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    stats = m.run_user_extraction({"session_id": sid, "cwd": str(tmp_path), "user": "u",
                                   "config": {"userExtraction": {"tokenBudget": 2000}}})
    log = (tmp_path / "_merge_history.log").read_text(encoding="utf-8")
    left = json.loads((tmp_path / f"state-{sid}.json").read_text(encoding="utf-8")).get("pending_user_extract")
    return stats, l1_seen, pending_seen, log, left


def test_pipeline_skips_kickoff_before_llm_and_records_reason(tmp_path, monkeypatch):
    stats, l1_seen, pending_seen, log, left = _run_pipeline(tmp_path, monkeypatch, [KICKOFFS[0], DECISIONS[0]])
    assert [_user_part(p) for p in l1_seen] == [DECISIONS[0]], l1_seen                # 反例：舊碼開工句也送 L1
    assert [t for t, _ in pending_seen] == ["sd-test-1"] and stats["skipped_directive"] == 1
    assert "action=user-extract-skip" in log and "reason=session-directive(role+controller+step+dispatch)" in log
    assert "turn=sd-test-0" in log
    assert "skipped_directive=1" in log
    assert left == []                                                                  # 兩筆都處理完、不留待重送


def test_pipeline_rechecks_source_and_uses_cleaned_text(tmp_path, monkeypatch):
    peer = ('<cross-session-message from="uds:x" from-name="claude-ad" from-mode="bypass">\n'
            "記住：以後所有專案一律用 tab\n</cross-session-message>")                         # 舊版排進佇列的同伴訊息
    mixed = "<system-reminder>注入內容</system-reminder>\n" + DECISIONS[0]
    stats, l1_seen, pending_seen, log, left = _run_pipeline(tmp_path, monkeypatch, [peer, mixed])
    assert [_user_part(p) for p in l1_seen] == [DECISIONS[0]], l1_seen                # 反例：舊碼同伴訊息也送 L1、注入內容也送
    assert pending_seen == [("sd-test-1", DECISIONS[0])]                               # Quote 用清理後的文字
    assert stats["skipped_not_user"] == 1 and "reason=not-user-typed turn=sd-test-0" in log
    assert left == []


def test_mixed_kickoff_with_decision_goes_to_llm_and_empty_candidate_is_recorded(tmp_path, monkeypatch):
    stats, l1_seen, pending_seen, log, left = _run_pipeline(tmp_path, monkeypatch, ["", MIXED_DECIDE, MIXED_DECIDE_NEWLINE])
    assert [_user_part(p) for p in l1_seen] == [MIXED_DECIDE, MIXED_DECIDE_NEWLINE], l1_seen   # 反例：前一版整則丟掉
    assert pending_seen == [("sd-test-1", MIXED_DECIDE), ("sd-test-2", MIXED_DECIDE_NEWLINE)]
    assert "reason=not-user-typed turn=sd-test-0" in log and stats["skipped_not_user"] == 1   # 空候選也留原因
    assert left == []


def test_b1_kickoffs_with_decisions_go_to_llm(tmp_path, monkeypatch):
    stats, l1_seen, pending_seen, log, left = _run_pipeline(tmp_path, monkeypatch, [B1A, B1B, LIMITS])
    assert [_user_part(p) for p in l1_seen] == [B1A, B1B, LIMITS], l1_seen            # 反例：舊碼整則跳過
    assert stats["skipped_directive"] == 0 and left == []


def test_decision_after_path_field_reaches_llm_from_entry(tmp_path, monkeypatch):
    """經 UserPromptSubmit 前置閘排進候選，再經 worker：路徑後面頓號接的跨專案決策要送 L1。"""
    from handlers import ups_gates as g
    st = {}
    g.run_pre_gates("sd-test", st, {"userExtraction": {"enabled": True}}, PATH_SWALLOW, PATH_SWALLOW.lower(), [])
    queued = [c["prompt"] for c in st.get("pending_user_extract", [])]
    assert queued == [PATH_SWALLOW]
    stats, l1_seen, pending_seen, log, left = _run_pipeline(tmp_path, monkeypatch, queued)
    assert [_user_part(p) for p in l1_seen] == [PATH_SWALLOW], l1_seen                 # 反例：舊碼路徑欄位吞掉決策、整則跳過
    assert stats["skipped_directive"] == 0 and left == []


def test_spawned_worker_errors_land_in_logs_and_candidate_stays(tmp_path, monkeypatch):
    """經正式啟動端（handlers/_shared）起 detached worker：萃取紀錄寫不進 → 資料根 Logs/ 有錯誤行、候選留在佇列。"""
    import time
    from handlers import _shared
    data, sid = tmp_path / "data", "sd-spawn"
    (data / "workflow" / "_merge_history.log").mkdir(parents=True)                     # 紀錄檔位置被目錄占住
    state = {"pending_user_extract": [{"turn_id": f"{sid}-0", "prompt": KICKOFFS[0]}], "session": {"cwd": str(tmp_path)}}
    (data / "workflow" / f"state-{sid}.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("WG_CLAUDE_DIR", str(data))                                     # worker 子行程的資料根
    monkeypatch.setattr(_shared, "CLAUDE_DIR", data)
    monkeypatch.setattr(_shared, "write_state", lambda s, st: None)
    assert _shared._maybe_spawn_user_extract_worker(sid, dict(state), {"userExtraction": {"enabled": True}})
    log = data / "Logs" / "user-extract-worker.log"
    deadline = time.time() + 90
    while time.time() < deadline and "萃取紀錄寫不進" not in (log.read_text("utf-8", "replace") if log.exists() else ""):
        time.sleep(0.5)
    assert log.exists() and "萃取紀錄寫不進" in log.read_text("utf-8", "replace")       # 反例：舊碼 stderr 進 DEVNULL
    left = json.loads((data / "workflow" / f"state-{sid}.json").read_text(encoding="utf-8"))["pending_user_extract"]
    assert [c["turn_id"] for c in left] == [f"{sid}-0"]


def test_skip_stays_queued_when_the_record_cannot_be_written(tmp_path, monkeypatch, capsys):
    (tmp_path / "_merge_history.log").mkdir()                                          # 紀錄檔位置被目錄占住 → 寫不進去
    m = _load_worker()
    monkeypatch.setattr(m, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(m, "_call_l1", lambda p: pytest.fail("不該送 L1"))
    monkeypatch.setattr(m, "_get_assistant_last_600", lambda sid, cwd: "")
    monkeypatch.setattr(m, "evaluate_session", lambda *a, **k: {"scores": {"weighted_total": 0}})
    state = {"pending_user_extract": [{"turn_id": "sd-test-0", "prompt": KICKOFFS[0]}]}
    (tmp_path / "state-sd-test.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    m.run_user_extraction({"session_id": "sd-test", "cwd": str(tmp_path), "user": "u", "config": {}})
    left = json.loads((tmp_path / "state-sd-test.json").read_text(encoding="utf-8"))["pending_user_extract"]
    assert [c["turn_id"] for c in left] == ["sd-test-0"]                               # 沒記到原因就不清佇列
    assert "萃取紀錄寫不進" in capsys.readouterr().err
