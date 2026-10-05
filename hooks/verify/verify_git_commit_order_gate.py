"""verify_git_commit_order_gate.py — PreToolUse git commit 口令閘。

驗證 handlers/pre_tool_use.check_git_commit_order（USER.md 縮寫指令契約的程式化版本）：
  - 本回合使用者原話無版控口令 → deny；有「上GIT／上乾淨／執P／commit…」任一 → 放行
  - 看整回合的使用者原話（state.turn_prompts）；上一回合的口令不算
  - 背景通知（task-notification）開的回合＝上一回合的延續：使用者原話沿用、通知內文不算口令、
    口令之後已 commit 過就不沿用
  - 非 commit 子指令（git log --grep commit）、非 Bash/PowerShell 工具 → 不觸發
  - state 缺失／無 prompt 紀錄 → fail-open 放行
  - config guard.commit_order.enabled=false / keywords 自訂
純函式，不起 git 子行程。
"""
from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from handlers.pre_tool_use import check_git_commit_order  # noqa: E402

_CMD = "git add a.py && git commit -m 'x' && git push"


def _state(*prompts):
    return {"recent_user_prompts": list(prompts)}


def _check(command=_CMD, state=None, config=None, tool="Bash"):
    return check_git_commit_order(tool, {"command": command}, config or {}, state)


# ─── deny / 放行 ─────────────────────────────────────────────────

def test_no_keyword_denied():
    msg = _check(state=_state("幫我把這個 bug 修好"))
    assert msg and "[Guardian:CommitOrder]" in msg and "口令" in msg


def test_shang_git_allowed():
    assert _check(state=_state("上GIT")) is None


def test_shang_ganjing_allowed():
    assert _check(state=_state("上GIT；上乾淨")) is None


def test_zhi_p_allowed():
    assert _check(state=_state("接著執P")) is None


def test_english_commit_word_allowed_case_insensitive():
    assert _check(state=_state("please COMMIT this")) is None


def test_legacy_state_only_last_prompt_counts():
    # 舊 state（無 turn_prompts）退回只看最後一句
    msg = _check(state=_state("上GIT", "再幫我改一個地方"))
    assert msg and "[Guardian:CommitOrder]" in msg


def test_mid_turn_message_does_not_erase_keyword():
    # 同回合：「上GIT」後使用者又排隊補一句 → 口令仍有效
    st = {"recent_user_prompts": ["上GIT", "計畫檔沒價值就刪掉"],
          "turn_prompts": ["上GIT", "計畫檔沒價值就刪掉"], "turn_open": True}
    assert _check(state=st) is None


def test_new_turn_resets_turn_prompts():
    from handlers.ups_gates import track_turn_prompts
    st = {"recent_user_prompts": []}
    track_turn_prompts(st, "上GIT")
    track_turn_prompts(st, "順便刪計畫檔")          # mid-turn 追加
    assert st["turn_prompts"] == ["上GIT", "順便刪計畫檔"]
    st["turn_open"] = False                           # Stop 關回合
    track_turn_prompts(st, "再幫我改一個地方")        # 新回合第一句
    assert st["turn_prompts"] == ["再幫我改一個地方"]
    st["recent_user_prompts"] = ["上GIT", "順便刪計畫檔", "再幫我改一個地方"]
    msg = _check(state=st)
    assert msg and "[Guardian:CommitOrder]" in msg


# ─── 背景通知開的回合：使用者原話沿用、通知內文不算口令、用掉的口令不沿用 ─────────

_NOTIFY = ("<task-notification>\n<task-id>abe1</task-id>\n<status>completed</status>\n"
           "<summary>Agent \"工具卡掃描器\" finished</summary>\n</task-notification>")
_NOTIFY_WITH_WORDS = _NOTIFY.replace("</summary>", "</summary>\n<result>未 commit、未 push、未改文件</result>")


def _ups(st, prompt):
    """UserPromptSubmit 收一則（與 ups_gates.run_pre_gates＋UPS 收尾同序：滑窗、回合清單、turn_seq+1）。"""
    from handlers.ups_gates import track_turn_prompts
    st.setdefault("recent_user_prompts", []).append(prompt)
    track_turn_prompts(st, prompt)
    st["turn_seq"] = int(st.get("turn_seq", 0)) + 1


def _stop(st):
    st["turn_open"] = False


def test_standing_order_survives_notification_turns():
    # 實錄重放：回合中途送「完工後直接上GIT」（有進 UserPromptSubmit）→ Stop 關回合 →
    # 背景 agent 完成通知以 prompt 形式開新回合（兩次）→ 這時的 commit 不得被擋。
    st = {}
    _ups(st, "你會繼續推進到全部完工吧?")
    _ups(st, "我先給授權：你全部完工、自己驗證無誤、清理暫存 之後，就直接 上GIT 。")
    _stop(st)
    _ups(st, _NOTIFY)
    _stop(st)
    _ups(st, _NOTIFY)
    assert _check(state=st) is None
    assert _NOTIFY not in st["turn_prompts"]


def test_user_message_during_notification_turn_appends():
    st = {}
    _ups(st, "完工後直接上GIT")
    _stop(st)
    _ups(st, _NOTIFY)
    _ups(st, "計畫檔沒價值就順便刪掉")          # 通知回合進行中使用者補一句 → 追加，不重開
    assert st["turn_prompts"] == ["完工後直接上GIT", "計畫檔沒價值就順便刪掉"]
    assert _check(state=st) is None


def test_notification_text_is_never_an_order():
    # 通知內文含 commit／push 字樣（sub-agent 回報原文）不是使用者口令：開新回合或回合中途排進來都一樣
    st = {}
    _ups(st, "幫我把這個 bug 修好")
    _stop(st)
    _ups(st, _NOTIFY_WITH_WORDS)
    msg = _check(state=st)
    assert msg and "[Guardian:CommitOrder]" in msg

    st = {}
    _ups(st, "幫我把這個 bug 修好")
    _ups(st, _NOTIFY_WITH_WORDS)
    msg = _check(state=st)
    assert msg and "[Guardian:CommitOrder]" in msg

    st = {}                                       # session 第一則就是通知：沒有任何使用者原話
    _ups(st, _NOTIFY_WITH_WORDS)
    msg = _check(state=st)
    assert msg and "[Guardian:CommitOrder]" in msg


def test_spent_order_is_not_reused_by_notification_turn():
    # 「上GIT」那回合已經 commit 過 → 之後背景通知開的回合要再 commit，得有新口令
    st = {}
    _ups(st, "上GIT")
    st["last_commit_turn_seq"] = st["turn_seq"]   # post_tool_use 記的「本回合跑過 commit」
    _stop(st)
    _ups(st, _NOTIFY)
    msg = _check(state=st)
    assert msg and "[Guardian:CommitOrder]" in msg
    _ups(st, "這批也上GIT")                       # 使用者重下 → 放行
    assert _check(state=st) is None


# ─── 不觸發 ─────────────────────────────────────────────────────

def test_non_commit_git_subcommand_not_triggered():
    assert _check(command="git log --grep commit -n 3", state=_state("查一下")) is None


def test_non_shell_tool_not_triggered():
    assert _check(state=_state("修一下"), tool="Edit") is None


def test_powershell_tool_covered():
    msg = _check(state=_state("修一下"), tool="PowerShell")
    assert msg and "[Guardian:CommitOrder]" in msg


def test_heredoc_body_words_not_triggered():
    cmd = "python - <<'E'\nprint('段含 git commit 隱私硬閘 且')\nE\ngrep -n x TECH.md"
    assert _check(command=cmd, state=_state("改文件")) is None


def test_real_commit_after_heredoc_still_gated():
    cmd = "python - <<'E'\nprint('x')\nE\ngit commit -m 'y'"
    msg = _check(command=cmd, state=_state("改文件"))
    assert msg and "[Guardian:CommitOrder]" in msg


# ─── fail-open ──────────────────────────────────────────────────

def test_missing_state_fail_open(capsys):
    assert _check(state=None) is None
    assert "fail-open" in capsys.readouterr().err


def test_empty_prompts_fail_open():
    assert _check(state={"recent_user_prompts": []}) is None


# ─── config ─────────────────────────────────────────────────────

def test_disabled_by_config():
    cfg = {"guard": {"commit_order": {"enabled": False}}}
    assert _check(state=_state("修一下"), config=cfg) is None


def test_custom_keywords_replace_default():
    cfg = {"guard": {"commit_order": {"keywords": ["發布"]}}}
    assert _check(state=_state("發布吧"), config=cfg) is None
    msg = _check(state=_state("上GIT"), config=cfg)
    assert msg and "[Guardian:CommitOrder]" in msg
