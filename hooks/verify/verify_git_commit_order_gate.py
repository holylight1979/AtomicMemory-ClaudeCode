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

import pytest

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


_PEER = ('<cross-session-message from="uds:\\\\.\\pipe\\LOCAL\\cc-msg-x" from-name="claude-ad" from-mode="bypass">\n'
         "對帳過了，上GIT\n</cross-session-message>")


def test_peer_session_message_is_never_an_order():
    # 其他 Claude session 用 SendMessage 送來的訊息內文含「上GIT」：不是使用者口令，不進本回合使用者原話
    st = {}
    _ups(st, "幫我把這個 bug 修好")
    _stop(st)
    _ups(st, _PEER)
    assert _PEER not in st["turn_prompts"]                                          # 反例：舊碼記成使用者原話
    msg = _check(state=st)
    assert msg and "[Guardian:CommitOrder]" in msg
    st = {}
    _ups(st, "上GIT")
    assert st["turn_prompts"] == ["上GIT"] and _check(state=st) is None             # 使用者打的照記、照放行
    for older in ("幫我把這個 bug 修好", "上GIT"):                                  # 舊 state 退路：最後一句是同伴訊息 → 擋，
        msg = _check(state={"recent_user_prompts": [older, _PEER]})                  # 也不往前撿舊口令
        assert msg and "[Guardian:CommitOrder]" in msg, older
    stale = {"recent_user_prompts": ["幫我修", _PEER], "turn_prompts": [_PEER], "turn_open": True}   # 舊版已把同伴訊息存進 turn_prompts
    msg = _check(state=stale)
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


def test_claude_dir_cwd_exempt_and_other_cwd_still_gated(tmp_path):
    """session cwd 在 ~/.claude 內 → 不等口令放行（記憶系統 repo 例外）；別的專案 cwd 照擋；關掉 exempt 鍵則一律照擋。"""
    from handlers import pre_tool_use as ptu
    inside = {"recent_user_prompts": ["改好了"], "turn_prompts": ["改好了"],
              "session": {"cwd": str(Path(ptu.CLAUDE_DIR) / "hooks")}}
    outside = {"recent_user_prompts": ["改好了"], "turn_prompts": ["改好了"],
               "session": {"cwd": str(tmp_path)}}
    assert _check(state=inside) is None
    assert _check(state=outside) is not None
    cfg = {"guard": {"commit_order": {"exempt_cwd_under_claude_dir": False}}}
    assert _check(state=inside, config=cfg) is not None


def _wt(tmp_path, name, gitdir, with_map=True):
    """假 worktree：`.git` 檔的 gitdir 指到 gitdir；with_map 決定有沒有 .claude/overview-map.md（豁免不該靠它）。"""
    root = tmp_path / name
    (root / "hooks").mkdir(parents=True)
    if with_map:
        (root / ".claude").mkdir()
        (root / ".claude" / "overview-map.md").write_text("x", encoding="utf-8")
    (root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    return root


_PEER_COMMIT_WORD = '<cross-session-message from="uds:x" from-name="claude-x">分支先別再 commit</cross-session-message>'


def _peer_state(cwd):
    """本回合只有同伴訊息（user_typed_text 剔光，即使內文寫了 commit）：豁免只能照 commit 落在哪個 repo 判，不靠訊息字樣。"""
    return {"recent_user_prompts": [""], "turn_prompts": [_PEER_COMMIT_WORD], "session": {"cwd": str(cwd)}}


def test_claude_repo_worktree_exempt_other_repo_worktree_gated(tmp_path):
    """commit 落在 ~/.claude 這個 repo 的 git worktree（gitdir 在 <CLAUDE_DIR>/.git/worktrees/ 之下）→ 同屬記憶系統程式，放行；
    gitdir 指到別的 repo → 照擋；關掉 exempt 鍵 → 照擋；worktree 沒有 overview-map 也算（豁免看 git，不看部位表）。"""
    from handlers import pre_tool_use as ptu
    ours = _wt(tmp_path, "wt-ours", Path(ptu.CLAUDE_DIR) / ".git" / "worktrees" / "track-x")
    bare = _wt(tmp_path, "wt-nomap", Path(ptu.CLAUDE_DIR) / ".git" / "worktrees" / "track-y", with_map=False)
    other = _wt(tmp_path, "wt-other", tmp_path / "other-repo" / ".git" / "worktrees" / "track-x")
    assert _check(state=_peer_state(ours / "hooks")) is None
    assert _check(state=_peer_state(bare / "hooks")) is None
    assert _check(state=_peer_state(other / "hooks")) is not None
    cfg = {"guard": {"commit_order": {"exempt_cwd_under_claude_dir": False}}}
    assert _check(state=_peer_state(ours / "hooks"), config=cfg) is not None


def test_exemption_follows_commit_target_repo_not_session_cwd(tmp_path):
    """豁免看每段 commit 實際落在哪個 repo：session 在我們的 worktree，但 `git -C <別的專案> commit`、
    或 commit 落在 worktree 裡的內嵌 repo（自己的 .git 目錄）→ 照擋；`-C hooks`（相對、仍在 worktree）→ 放行；
    一段在我們、一段在別處 → 照擋。"""
    from handlers import pre_tool_use as ptu
    ours = _wt(tmp_path, "wt-ours", Path(ptu.CLAUDE_DIR) / ".git" / "worktrees" / "track-x")
    other_proj = tmp_path / "other-proj"
    (other_proj / ".git").mkdir(parents=True)
    nested = ours / "vendor" / "lib"
    (nested / ".git").mkdir(parents=True)
    st = _peer_state(ours)
    assert _check(command=f'git -C "{other_proj}" commit -m x', state=st) is not None
    assert _check(command="git commit -m x", state=_peer_state(nested)) is not None
    assert _check(command="git -C hooks commit -m x", state=st) is None
    assert _check(command=f'git commit -m a && git -C "{other_proj}" commit -m b', state=st) is not None


def test_undecidable_target_does_not_exempt_and_says_so(capsys):
    """判不了 commit 落在哪（沒有 cwd 可解相對路徑）→ 不套用豁免、繼續口令檢查，stderr 說明；不宣稱一定擋。"""
    st = {"recent_user_prompts": [""], "turn_prompts": [_PEER_COMMIT_WORD], "session": {}}
    assert _check(state=st) is not None
    assert "不套用豁免" in capsys.readouterr().err


def test_exemption_whitelist_rejects_repo_overrides_and_dir_juggling(tmp_path, monkeypatch):
    """豁免只給看得出落點的寫法：session 在我們的 worktree，下列寫法都可能落到別的 repo（或看不出），一律不豁免、照常要口令。
    誠實寫法（第一段 `cd <絕對路徑>`、單一獨立 `-C <絕對路徑>`、commit 訊息含括號）仍豁免。"""
    from handlers import pre_tool_use as ptu
    ours = _wt(tmp_path, "wt-ours", Path(ptu.CLAUDE_DIR) / ".git" / "worktrees" / "track-x")
    other = tmp_path / "other"
    (other / ".git").mkdir(parents=True)
    st = _peer_state(ours)
    o = str(other).replace("\\", "/")
    w = str(ours).replace("\\", "/")
    blocked = [
        f"git --git-dir={o}/.git --work-tree={o} commit -m x",
        f"git --git-dir {o}/.git --work-tree {o} commit -m x",
        f'$env:GIT_DIR="{o}/.git"; git commit -m x',
        f"GIT_DIR={o}/.git git commit -m x",
        f"cd {o}; git -C . commit -m x",
        f"cd {o}; cd .; git commit -m x",
        f"pushd {o}; git -C . commit -m x",
        f"Set-Location -Path {o}; git -C . commit -m x",
        f"git -C {o} -C . commit -m x",
        f"git -C{o} commit -m x",
        f"cd {o}; pushd {w}; popd; git commit -m x",
        f"(cd {o}; git commit -m x)",
        f'git "--git-dir={o}/.git" "--work-tree={o}" commit -m x',       # 引號裡的覆寫參數一樣算
        f'env "GIT_DIR={o}/.git" git commit -m x',
        f"builtin cd {o}; git commit -m x",
        f"builtin cd {o} && git commit -m x",
        f'git commit -m "$(git -C {o} commit -m y)"',                    # 雙引號裡的 $( ) 會被展開
        f"git commit -m \"'$(git -C {o} commit -m y)'\"",                # 雙引號裡的單引號不擋展開
        f"git commit -F - <<'EOF' && git -C {o} commit -m y\nx\nEOF",    # heredoc 起始行夾帶第二段
        f"git commit -F - <<EOF\n$(git -C {o} commit -m y)\nEOF",        # 沒加引號的 heredoc 內文會展開
        f'git commit -m "x\\$(git -C {o} commit -m y)"',                 # 跳脫
        'git commit -m "沒閉合',
        'git -C "$repo" commit -m x',                                     # 路徑變數會被展開成別處
        'git -C "${repo}" commit -m x',
        'git -C "$env:REPO" commit -m x',
        'git -C %REPO% commit -m x',
        "git -C ~/other commit -m x",
        f"cd {w} && git -C ../other commit -m x",                         # .. 消掉後落在 worktree 外
    ]
    for cmd in blocked:
        assert _check(command=cmd, state=st) is not None, cmd
    allowed = [
        "git commit -m x",
        "git commit -m 'fix(tools): 括號與 $(x) 在單引號裡不展開'",
        f'git commit -m "fix(tools): 雙引號裡的括號不算"',
        f"cd {w} && git add a.py && git commit -m x",
        f'git -C "{w}" commit -m x',
        f"cd {w} && git -C hooks commit -m x",                  # 相對 -C 接在唯一的 cd 後面
        "git commit -F - <<'EOF'\nfix: 訊息 (含括號) ; | 都在 heredoc 裡\nEOF",
    ]
    for cmd in allowed:
        assert _check(command=cmd, state=st) is None, cmd
    other_cwd = {"recent_user_prompts": [""], "turn_prompts": [_PEER_COMMIT_WORD], "session": {"cwd": str(other)}}
    assert _check(command=f"cd {w} | git commit -m x", state=other_cwd) is not None   # 管線左邊的 cd 不改右邊的目錄
    monkeypatch.setenv("GIT_DIR", f"{o}/.git")                 # hook 行程繼承的環境變數也算覆寫
    assert _check(command="git commit -m x", state=st) is not None


def test_tool_cwd_wins_over_session_cwd_and_unreadable_git_file_is_undecided(tmp_path, monkeypatch, capsys):
    """hook 的 tool cwd 優先於 session cwd（session 開在我們的 worktree、工具卻在別的專案跑 → 照擋）；
    worktree 的 `.git` 檔讀不到 → 判不了，不套用豁免並在 stderr 說明（不被吞成「不是」）。"""
    from handlers import pre_tool_use as ptu
    ours = _wt(tmp_path, "wt-ours", Path(ptu.CLAUDE_DIR) / ".git" / "worktrees" / "track-x")
    other = tmp_path / "other"
    (other / ".git").mkdir(parents=True)
    st = _peer_state(ours)
    assert check_git_commit_order("Bash", {"command": "git commit -m x"}, {}, st, str(other)) is not None
    assert check_git_commit_order("Bash", {"command": "git commit -m x"}, {}, st, str(ours)) is None
    real_read = Path.read_text

    def boom(self, *a, **k):
        if self.name == ".git":
            raise PermissionError("denied")
        return real_read(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", boom)
    capsys.readouterr()
    assert check_git_commit_order("Bash", {"command": "git commit -m x"}, {}, st, str(ours)) is not None
    assert "不套用豁免" in capsys.readouterr().err


def test_off_whitelist_shape_in_claude_repo_says_how_to_commit_without_order(tmp_path):
    """在記憶系統自己的 repo 裡、寫法不在白名單（尾巴接管線）→ 照常要口令，但擋訊息要說「單獨下 commit 就不用口令」；
    在別的 repo 不給這句（那裡本來就要口令）。"""
    from handlers import pre_tool_use as ptu
    ours = _wt(tmp_path, "wt-ours", Path(ptu.CLAUDE_DIR) / ".git" / "worktrees" / "track-x")
    other = tmp_path / "other"
    (other / ".git").mkdir(parents=True)
    msg = check_git_commit_order("Bash", {"command": "git commit -m x | tail -2"}, {}, _peer_state(ours), str(ours))
    assert msg and "單獨下 commit 指令就不用口令" in msg
    msg2 = check_git_commit_order("Bash", {"command": "git commit -m x | tail -2"}, {}, _peer_state(other), str(other))
    assert msg2 and "單獨下 commit 指令" not in msg2


def test_wrapped_commit_is_not_skipped_by_parser(tmp_path):
    """bash -c／子 shell 包住的 git commit 解析器拆不出段：不能當成「沒有 commit」放行，照常檢查口令（即使在記憶系統 repo）。"""
    st = {"recent_user_prompts": ["改好了"], "turn_prompts": ["改好了"], "session": {"cwd": str(tmp_path)}}
    assert _check(command='bash -c "git -C C:/other commit -m x"', state=st) is not None
    assert _check(command='bash -c "git log --oneline"', state=st) is None
    assert _check(command='git log --grep "commit (x)"', state=st) is None


# ─── 一般寫法不得漏擋（codex 檢核 A 四條）：每件一反例（無口令必擋、關豁免對照）＋誠實寫法照舊免口令 ────

_OFF = {"guard": {"commit_order": {"exempt_cwd_under_claude_dir": False}}}


def _no_order(cwd):
    """本回合使用者原話沒有口令，session cwd 在 cwd。"""
    return {"recent_user_prompts": ["改好了"], "turn_prompts": ["改好了"], "session": {"cwd": str(cwd)}}


def _other_repo(tmp_path):
    other = tmp_path / "other"
    (other / ".git").mkdir(parents=True)
    return other


def _ours(tmp_path):
    from handlers import pre_tool_use as ptu
    return _wt(tmp_path, "wt-ours", Path(ptu.CLAUDE_DIR) / ".git" / "worktrees" / "track-x")


def test_commit_on_heredoc_start_line_is_not_stripped_away(tmp_path):
    """`cat > msg <<'EOF' && git add … && git commit -F msg` 的 commit 在 heredoc 起始行 delimiter 後面：剝內文不得連它一起剝。
    別的 repo 無口令 → 擋；關豁免 → 擋；在記憶系統 worktree 這種起始行夾帶寫法本就不在白名單，也要口令；
    誠實寫法（`cd <絕對路徑> && git add … && git commit -F <檔>`、`git -C <絕對路徑> commit -F <檔>`）照舊免口令。"""
    from handlers import pre_tool_use as ptu
    cmd = "cat > message.txt <<'EOF' && git add a.py && git commit -F message.txt\nfix bug\nEOF"
    other, ours = _other_repo(tmp_path), _ours(tmp_path)
    assert _check(command=cmd, state=_no_order(other)) is not None
    assert _check(command=cmd, state=_no_order(other), config=_OFF) is not None
    assert _check(command=cmd, state=_no_order(ours)) is not None
    assert ptu._strip_heredoc_bodies(cmd) == "cat > message.txt <<HEREDOC_STRIPPED && git add a.py && git commit -F message.txt"
    assert _check(command="cat > m.txt <<'EOF'\nfix: git commit 字樣在內文\nEOF\ngrep -n x TECH.md", state=_no_order(other)) is None
    w = str(ours).replace("\\", "/")
    assert _check(command=f"cd {w} && git add a.py && git commit -F message.txt", state=_no_order(other)) is None
    assert _check(command=f"git -C {w} commit -F message.txt", state=_no_order(other)) is None


def test_shell_launch_options_do_not_hide_wrapped_commit(tmp_path):
    """shell 名與執行旗標之間夾一般啟動選項（bash -lc、bash -l -c、powershell -NoProfile -Command、pwsh -NoLogo …、cmd /d /c）：
    解析器拆不出段也不得當成「沒有 commit」，照常要口令；關豁免同樣擋；包的不是 commit 就不觸發。"""
    other = _other_repo(tmp_path)
    st = _no_order(other)
    wrapped = [
        "bash -lc 'git commit -m fix'",
        "bash -l -c 'git commit -m fix'",
        "sh -ec 'git commit -m fix'",
        'bash.exe -c "git commit -m fix"',
        'powershell -NoProfile -Command "git commit -m fix"',
        'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "git commit -m fix"',
        'pwsh -NoLogo -NoProfile -Command "git commit -m fix"',
        'pwsh -nop -c "git commit -m fix"',
        'cmd /d /c "git commit -m fix"',
        'cmd.exe /d /s /c "git commit -m fix"',
        'cmd /k "git commit -m fix"',
    ]
    for cmd in wrapped:
        assert _check(command=cmd, state=st) is not None, cmd
        assert _check(command=cmd, state=st, config=_OFF) is not None, cmd
    for cmd in ("bash -lc 'git log --oneline'", 'powershell -NoProfile -Command "git status"', 'cmd /d /c "git diff"'):
        assert _check(command=cmd, state=st) is None, cmd


def test_git_executable_case_matches_segment_parser(tmp_path):
    """Windows 執行檔不分大小寫：`Git commit`、`GIT.EXE commit`、`git.EXE` 快篩不得先放掉（_vcs_segments 本來就認得）。
    別的 repo 無口令 → 擋；關豁免 → 擋；在記憶系統 worktree 的誠實寫法照舊免口令。"""
    other, ours = _other_repo(tmp_path), _ours(tmp_path)
    for cmd in ("Git commit -m fix", "GIT.EXE commit -m fix", "git.EXE add a.py && git.EXE commit -m fix", "GIT COMMIT -m fix"):
        assert _check(command=cmd, state=_no_order(other)) is not None, cmd
        assert _check(command=cmd, state=_no_order(other), config=_OFF) is not None, cmd
    assert _check(command="Git commit -m fix", state=_no_order(ours)) is None


def _msys(p):
    """`C:\\x\\y` → Git Bash 的 `/c/x/y`。"""
    s = str(p).replace("\\", "/")
    return "/" + s[0].lower() + s[2:]


@pytest.mark.skipif(sys.platform != "win32", reason="Git Bash 磁碟機路徑只在 Windows 需要轉")
def test_git_bash_drive_path_resolves_to_windows_drive(tmp_path):
    """Git Bash 的 `cd /c/…`、`git -C /c/…` 在 Windows 轉成 `C:/…` 再找最近 `.git`：落在記憶系統 repo／worktree → 免口令（與 `C:/` 寫法同判）；
    落在別的 repo → 擋；關豁免 → 擋；`/cygdrive/c/…`、`//c/…` 不是已知寫法 → 不豁免。"""
    from handlers import pre_tool_use as ptu
    other, ours = _other_repo(tmp_path), _ours(tmp_path)
    live, w, o = _msys(ptu.CLAUDE_DIR), _msys(ours), _msys(other)
    assert _check(command=f"cd {live} && git add a.py && git commit -m fix", state=_no_order(other)) is None
    assert _check(command=f"cd {w} && git add a.py && git commit -m fix", state=_no_order(other)) is None
    assert _check(command=f"git -C {w} commit -F msg.txt", state=_no_order(other)) is None
    assert _check(command=f"cd {w} && git -C hooks commit -m fix", state=_no_order(other)) is None
    assert _check(command=f"cd {o} && git commit -m fix", state=_no_order(ours)) is not None
    assert _check(command=f"git -C {o} commit -m fix", state=_no_order(ours)) is not None
    assert _check(command=f"cd {w} && git commit -m fix", state=_no_order(other), config=_OFF) is not None
    for odd in (f"/cygdrive{w}", f"/{w}"):
        assert _check(command=f"cd {odd} && git commit -m fix", state=_no_order(other)) is not None, odd
    assert ptu._drive_path("/c/Users") == "C:/Users" and ptu._drive_path("/d") == "D:/" and ptu._drive_path("/cygdrive/c") == "/cygdrive/c"


# ─── codex 審 001 退件四條：帶引號的 shell 路徑、包裝裡的查詢不誤擋、/c/ 只對 Bash 工具、空 heredoc ────

def test_quoted_shell_path_is_still_a_wrapper(tmp_path):
    """Windows 安裝路徑含空白要加引號：`"C:/Program Files/Git/bin/bash.exe" -lc '…'`、PowerShell `& "…pwsh.exe" -NoProfile -Command "…"`。
    包裝辨識看斷詞後的執行檔 basename（保留引號內容），不先把引號內容抹掉。無口令擋、關豁免擋；包的是查詢不擋。"""
    other = _other_repo(tmp_path)
    st = _no_order(other)
    bash_path = '"C:/Program Files/Git/bin/bash.exe" -lc \'git commit -m fix\''
    pwsh_path = '& "C:/Program Files/PowerShell/7/pwsh.exe" -NoProfile -Command "git commit -m fix"'
    assert _check(command=bash_path, state=st) is not None
    assert _check(command=pwsh_path, state=st, tool="PowerShell") is not None
    assert _check(command=bash_path, state=st, config=_OFF) is not None
    assert _check(command=pwsh_path, state=st, config=_OFF, tool="PowerShell") is not None
    assert _check(command='"C:\\Program Files\\Git\\bin\\BASH.EXE" -c "git commit -m fix"', state=st) is not None
    assert _check(command='& "C:/Program Files/PowerShell/7/pwsh.exe" -NoProfile -Command "git log --grep=commit"', state=st, tool="PowerShell") is None
    assert _check(command='"C:/Program Files/Git/bin/bash.exe" -lc \'git log\'', state=st) is None


def test_wrapped_query_with_commit_word_is_not_gated(tmp_path):
    """包裝內容拆得出來就認真子命令：`bash -lc 'git log --grep=commit'` 是查詢，放行；內層真 commit、再包一層、eval／命令替換
    這類判不明的照口令檢查。"""
    other = _other_repo(tmp_path)
    st = _no_order(other)
    for cmd in ("bash -lc 'git log --grep=commit'", 'powershell -NoProfile -Command "git show HEAD -- commit.txt"',
                'cmd /d /c "git diff --stat commit.txt"', "bash -lc 'git log --grep=commit && git status'"):
        assert _check(command=cmd, state=st) is None, cmd
    for cmd in ("bash -lc 'git add commit.txt && git commit -m x'", "bash -lc 'git log && git commit -m x'",
                "bash -lc \"bash -c 'git commit -m x'\"", "bash -lc 'eval \"git commit -m x\"'",
                "bash -lc 'git $(echo commit) -m x'", 'pwsh -c "& git commit -m x"', "bash -lc 'git add commit.txt'"):
        assert _check(command=cmd, state=st) is not None, cmd
        assert _check(command=cmd, state=st, config=_OFF) is not None, cmd


@pytest.mark.skipif(sys.platform != "win32", reason="Git Bash 磁碟機路徑只在 Windows 需要轉")
def test_msys_drive_semantics_only_for_bash_tool(tmp_path):
    """同一條 `cd /c/… && git commit`：Bash 工具是 Git Bash 語意，轉成 `C:/…` 找落點、在我們的 worktree 免口令；
    PowerShell 工具的 `/c/…` 原生是 `C:\\c\\…`，不轉、不豁免、照常要口令。"""
    other, ours = _other_repo(tmp_path), _ours(tmp_path)
    cmd = f"cd {_msys(ours)} && git add a.py && git commit -m fix"
    assert _check(command=cmd, state=_no_order(other), tool="Bash") is None
    assert _check(command=cmd, state=_no_order(other), tool="PowerShell") is not None
    cmd_c = f"git -C {_msys(ours)} commit -m fix"
    assert _check(command=cmd_c, state=_no_order(other), tool="Bash") is None
    assert _check(command=cmd_c, state=_no_order(other), tool="PowerShell") is not None
    w = str(ours).replace("\\", "/")
    assert _check(command=f"cd {w} && git commit -m fix", state=_no_order(other), tool="PowerShell") is None


def test_empty_heredoc_then_commit_then_same_delimiter_is_gated(tmp_path):
    """空 heredoc（零行內文）後面接真 commit、再接同名 heredoc：只能剝到第一個結束行，中間的 commit 不得被吞掉。"""
    from handlers import pre_tool_use as ptu
    other = _other_repo(tmp_path)
    cmd = "cat <<'EOF'\nEOF\ngit commit -m fix\ncat <<'EOF'\nx\nEOF"
    assert _check(command=cmd, state=_no_order(other)) is not None
    assert _check(command=cmd, state=_no_order(other), config=_OFF) is not None
    assert ptu._strip_heredoc_bodies(cmd) == "cat <<HEREDOC_STRIPPED\ngit commit -m fix\ncat <<HEREDOC_STRIPPED"
    assert ptu._strip_heredoc_bodies("cat <<-E\n\tx\n\tE\ngit status") == "cat <<HEREDOC_STRIPPED\ngit status"
    assert ptu._strip_heredoc_bodies("cat <<'EOF'\ngit commit\nno end") == "cat <<'EOF'\ngit commit\nno end"


# ─── codex 審 003 退件三條：續行、雙引號裡的命令替換、包裝外片段的子 shell ────

def test_line_continuation_keeps_shell_and_flag_together(tmp_path):
    """續行不是兩條命令：Bash `\\`＋換行（裸 shell 名與帶引號完整路徑）、cmd `^`＋換行、PowerShell 反引號＋換行，
    shell 名與執行旗標分在兩行也要認成包裝。包的是 commit → 擋（含關豁免）；包的是查詢 → 放行。"""
    other = _other_repo(tmp_path)
    st = _no_order(other)
    gated = [
        ("bash \\\n  -lc 'git commit -m fix'", "Bash"),
        ('"C:/Program Files/Git/bin/bash.exe" \\\n  -lc \'git commit -m fix\'', "Bash"),
        ("bash -l \\\n  -c \\\n  'git commit -m fix'", "Bash"),
        ('cmd /d ^\n/c "git commit -m fix"', "Bash"),
        ('"C:/Windows/System32/cmd.exe" /d ^\n /c "git commit -m fix"', "PowerShell"),
        ('pwsh -NoProfile `\n  -Command "git commit -m fix"', "PowerShell"),
        ('& "C:/Program Files/PowerShell/7/pwsh.exe" -NoProfile `\n  -Command "git commit -m fix"', "PowerShell"),
        ("git \\\n  commit -m fix", "Bash"),
    ]
    for cmd, tool in gated:
        assert _check(command=cmd, state=st, tool=tool) is not None, cmd
        assert _check(command=cmd, state=st, tool=tool, config=_OFF) is not None, cmd
    allowed = [
        ("bash \\\n  -lc 'git log --grep=commit'", "Bash"),
        ('"C:/Program Files/Git/bin/bash.exe" \\\n  -lc \'git log --grep=commit\'', "Bash"),
        ('cmd /d ^\n/c "git log --grep=commit"', "Bash"),
        ('pwsh -NoProfile `\n  -Command "git log --grep=commit"', "PowerShell"),
    ]
    for cmd, tool in allowed:
        assert _check(command=cmd, state=st, tool=tool) is None, cmd


def test_command_substitution_inside_double_quotes_is_live(tmp_path):
    """只有單引號裡是字面：雙引號裡的 `$(…)`／反引號會展開執行，查詢白名單不得把它抹掉當成字面。
    單引號裡的 `$(…)` 是字面，照放行。"""
    other = _other_repo(tmp_path)
    st = _no_order(other)
    for cmd in ("bash -c 'git log --grep=\"$(git commit -m x)\"'",
                "bash -c 'git log --grep=\"`git commit -m x`\"'",
                'pwsh -NoProfile -Command "git log --grep=\\"$(git commit -m x)\\""',
                "bash -lc 'git status' \"$(git commit -m x)\"",
                'FOO="$(git commit -m x)" bash -lc \'git log\'',
                'echo "$(git commit -m x)"'):
        assert _check(command=cmd, state=st) is not None, cmd
        assert _check(command=cmd, state=st, config=_OFF) is not None, cmd
    assert _check(command="bash -c 'git log --grep=\\'$(commit)\\''", state=st) is not None   # 跳脫判不明
    assert _check(command="git log --grep='$(git commit -m x)'", state=st) is None            # 單引號字面、不是包裝


def test_other_segments_still_checked_when_query_wrapper_present(tmp_path):
    """有查詢包裝也不免除其他片段的檢查：同一條命令裡包裝外的子 shell 括號／eval／命令替換照查。"""
    other = _other_repo(tmp_path)
    st = _no_order(other)
    for cmd in ('bash -c "git log"; (git commit -m x)',
                'bash -c "git log"; eval "git commit -m x"',
                "bash -lc 'git log --grep=commit' && $(git commit -m x)",
                'bash -c "git log" | (git commit -m x)',
                'bash -c "git status"\n(git commit -m x)'):
        assert _check(command=cmd, state=st) is not None, cmd
        assert _check(command=cmd, state=st, config=_OFF) is not None, cmd
    assert _check(command="bash -c 'git log --oneline' && git status", state=st) is None


def test_deeply_nested_wrapped_commit_is_gated_past_parse_depth(tmp_path):
    """逐層合法 POSIX 引號包 1～6 層，最內層是 commit：超過遞迴上限也要擋（上限後只看 git…commit 字樣）；兩層包的查詢照放行。"""
    import shlex
    other = _other_repo(tmp_path)
    st = _no_order(other)
    cmd = "git commit -m fix"
    for layer in range(1, 7):
        cmd = "bash -c " + shlex.quote(cmd)
        assert _check(command=cmd, state=st) is not None, layer
        assert _check(command=cmd, state=st, config=_OFF) is not None, layer
    assert _check(command="bash -c " + shlex.quote("bash -c " + shlex.quote("git log --grep=commit")), state=st) is None


# ─── codex 審 005 退件四條：註解、外層雙引號的命令替換、續行重判、已知邊界的擋訊息 ────

def test_comment_apostrophe_does_not_swallow_next_line(tmp_path):
    """引號外、位在 token 起頭的 `#` 到行尾是註解：註解裡的撇號不是開引號，不得跨行吞掉下一行的包裝 commit。
    引號裡與 token 中間的 `#` 是字面：訊息含 `#12` 的誠實寫法在記憶系統 worktree 照舊免口令。"""
    other, ours = _other_repo(tmp_path), _ours(tmp_path)
    st = _no_order(other)
    for cmd in ("# Run the user's command\nbash -lc 'git commit -m fix'\n# That's all",
                "bash -lc 'git log --grep=commit' # user's query\nbash -lc 'git commit -m fix'",
                "# it's\n\"C:/Program Files/Git/bin/bash.exe\" -lc 'git commit -m fix'",
                "# don't\npwsh -NoProfile -Command \"git commit -m fix\"",
                "bash -lc 'git commit -m \"fix #12\"'"):
        assert _check(command=cmd, state=st) is not None, cmd
        assert _check(command=cmd, state=st, config=_OFF) is not None, cmd
    assert _check(command="# user's note\nbash -lc 'git log --grep=commit'", state=st) is None
    assert _check(command="bash -lc 'git log --grep=\"#12 commit\"'", state=st) is None
    w = str(ours).replace("\\", "/")
    assert _check(command=f'cd {w} && git add a.py && git commit -m "fix #12"', state=_no_order(other)) is None
    assert _check(command=f'git -C {w} commit -m "fix #12: 收尾"', state=_no_order(other)) is None


def test_outer_double_quotes_keep_substitution_live_before_recursion(tmp_path):
    """外層 shell 的雙引號裡，單引號只是普通字元，擋不住 `$()`：遞迴剝掉外層引號前，先用外層語意查整段原文。"""
    other = _other_repo(tmp_path)
    st = _no_order(other)
    for cmd in ("bash -c \"git log --grep='$(git commit -m x)'\"",
                "bash -lc \"git log --grep='`git commit -m x`'\"",
                "pwsh -NoProfile -Command \"git log --grep='$(git commit -m x)'\""):
        assert _check(command=cmd, state=st) is not None, cmd
        assert _check(command=cmd, state=st, config=_OFF) is not None, cmd
    assert _check(command="bash -c 'git log --grep=commit'", state=st) is None


def test_continuation_inside_git_token_is_rejoined_for_parsing(tmp_path):
    """續行接回後的文字才拿去判 git commit：`git\\⏎  commit`（反斜線緊貼 git、下一行縮排）也要擋；`$\\⏎(` 接回後是命令替換。
    `git\\⏎commit`（下一行不縮排）接回後是 `gitcommit` 一個字，不是 git commit，照 Bash 語意放行。"""
    other = _other_repo(tmp_path)
    st = _no_order(other)
    for cmd in ("git\\\n  commit -m fix", "Git\\\n commit -m fix",
                "bash -lc 'git log' \"$\\\n(git commit -m x)\""):
        assert _check(command=cmd, state=st) is not None, cmd
        assert _check(command=cmd, state=st, config=_OFF) is not None, cmd
    assert _check(command="git\\\ncommit -m fix", state=st) is None


def test_expansion_with_commit_word_is_known_boundary_and_says_so(tmp_path):
    """已知邊界（fail-closed）：命令裡有 `$()` 等展開又含 commit 字樣 → 一律要口令；擋訊息講清楚查詢怎麼寫才不擋。
    直接寫的 git commit 被擋時不附這句（它與包裝／展開無關）。"""
    other = _other_repo(tmp_path)
    st = _no_order(other)
    msg = _check(command='cd "$(git rev-parse --show-toplevel)" && git log --grep=commit', state=st)
    assert msg and "展開又含 commit 字樣時一律要口令" in msg and "改用單引號" in msg
    assert _check(command='cd "$(git rev-parse --show-toplevel)" && git status', state=st) is None
    plain = _check(command="git commit -m fix", state=st)
    assert plain and "展開又含 commit 字樣" not in plain
