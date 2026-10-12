"""verify_harness_prompt_guard.py — harness 生成 prompt 不當使用者訊號（2026-09-21 全面檢視 Phase 0/1a）。

守住：
1. is_harness_generated_prompt：<task-notification> / [SYSTEM NOTIFICATION / <cross-session-message 整則 → True；使用者文字 → False。
2. detect_correction：sub-agent 完成通知、其他 session 訊息裡引用的「不對／重來」不算使用者糾正；真糾正仍命中。
   豁免詞（detect_evasion、收割閘 _dismissed）只認使用者打的；其他 session 訊息裡的「先這樣」不替使用者豁免。
3. recall-miss collect_problem_texts：knowledge_queue 混有純字串不炸。
4. logs_dir：pytest 內寫到暫存目錄，不污染正式 Logs/。
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_core  # noqa: E402
from wg_friction import detect_correction  # noqa: E402
from wg_recall_miss import collect_problem_texts  # noqa: E402

NOTIFY = (
    "<task-notification>\n<task-id>x</task-id>\n"
    "<result>使用者說「不對」「我說過」「重來」時要記錄</result>\n</task-notification>"
)
SYSNOTE = "[SYSTEM NOTIFICATION - NOT USER INPUT]\nThis is automated. 不對 重來"
PEER = ('<cross-session-message from="uds:\\\\.\\pipe\\LOCAL\\cc-msg-x" from-name="claude-ad" from-mode="bypass">\n'
        "不對、重來；先這樣，上GIT\n</cross-session-message>")


def test_harness_prompt_detection():
    assert wg_core.is_harness_generated_prompt(NOTIFY) is True
    assert wg_core.is_harness_generated_prompt(SYSNOTE) is True
    assert wg_core.is_harness_generated_prompt(PEER) is True                       # 其他 session 的訊息不是使用者打的
    assert wg_core.is_harness_generated_prompt("  " + PEER) is True
    assert wg_core.is_harness_generated_prompt("不對，我說過要用 LF，重來") is False
    assert wg_core.is_harness_generated_prompt("") is False


def test_peer_message_is_not_a_correction_nor_a_dismiss():
    from wg_evasion import detect_evasion
    from wg_harvest import _dismissed
    assert detect_correction(PEER, {}) == []                                        # 反例：舊碼算成使用者糾正
    t = "既有的問題，非本次範圍。"
    assert detect_evasion(t, ["幫我修好", PEER]) is not None                        # 同伴說「先這樣」不替使用者豁免
    assert detect_evasion(t, ["先這樣", PEER]) is None                              # 使用者說的照樣豁免
    assert _dismissed(["幫我修好", PEER]) is False and _dismissed(["先這樣"]) is True
    from wg_evasion import detect_deferral, detect_missing_aec_emission
    later = "完工。realm atom 瘦身留到下個 session 做。"
    assert detect_deferral(later, ["幫我修好", PEER]) is not None and detect_deferral(later, ["先這樣"]) is None
    core = [{"path": r"c:\a\.claude\hooks\x.py", "tool": "Edit"}]
    assert detect_missing_aec_emission("全部完成了", core, ["幫我修好", PEER], 2, False) is True
    assert detect_missing_aec_emission("全部完成了", core, ["先這樣"], 2, False) is False
    assert wg_core.user_typed_prompts(["a", NOTIFY, PEER, "b"]) == ["a", "b"]


def test_correction_ignores_notification_but_catches_user():
    assert detect_correction(NOTIFY, {}) == []
    assert detect_correction(SYSNOTE, {}) == []
    assert set(detect_correction("不對，我說過要用 LF，重來", {})) == {"不對", "我說過", "重來"}
    assert detect_correction("這樣對不對？", {}) == []


def test_recall_miss_tolerates_string_queue_items():
    state = {"knowledge_queue": ["純字串殘留", {"type": "pitfall", "content": "svn 工作副本 upgrade required"}]}
    texts = collect_problem_texts(state)
    assert ("failure_kw", "svn 工作副本 upgrade required") in texts


def test_logs_dir_redirects_under_pytest():
    d = wg_core.logs_dir()
    assert d != wg_core._DEFAULT_LOGS_DIR
    assert "wg-test-logs" in str(d)
