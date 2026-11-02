"""verify_pull_stop_gates.py：收尾閘不再讓 AI 修不停或卡死、版控口令持續到這批 push 完的會紅案例（改前紅、改後綠）。

逐件（每件標它驗的是哪一條）：
  1 待放行只在同一個使用者回合有效；放行的那一件之後的回合原因還在不再問
  2 寫碼查核自己判定出錯：擋一次，同一個錯誤下一次收尾放行並留帳
  3 headless 主 session 比照子代理：擋滿放行留帳、擋訊息不說「不能放行」（等值閘同）
  4 「上GIT」持續到這批 push 完：背景通知與收尾閘逼出的補修 commit 不用重下；使用者新打字、push 完成就失效
  5 病形閘擋訊息教「# 不是繞閘｜」，照做一次就過（流程級）
  6 Reload 建議閘只在本 session 改過工具服務的檔才判
  7 退縮閘擋下的那一句不再記退避旗標（下一則使用者訊息不再追問）
  8 紅測閘寫碼守門開或關同一套：不看擋次預算、不開放行題，每次宣告完成都照擋（互動、無頭都一樣）
  共用擋次（stop_gate_max_blocks）每個使用者回合歸零；閱讀路徑尾段在拐彎判斷擋下時不重複那一題
  流程級：紅測擋 → 改碼、跑綠 → 再收尾，除「改完之後跑綠一次」外沒有別的收尾閘重欠
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_pull_stop_gates.py（或直接 python 跑，尾行印 PULL_STOP_GATES_CHECK PASS／FAIL）
退回舊碼看紅：把 hooks/、tools/ 換成舊版再跑同一支（案例只走 handler 入口與 state 字面值，不依賴新函式簽名）。
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

VERIFY = Path(__file__).resolve().parent
sys.path.insert(0, str(VERIFY))

from verify_stop_reconcile import (  # noqa: E402,F401
    _SID, _CODE, _CASE, _RELATED_CMD, _T1, _T2, _aec, _ask_line, _git_budget_generous, _mf, _rcpt,
    _sub_state, _temp_rules_off, driven, exhausted, rl, st, sub_stop, track_turn_prompts,
)
import verify_g7_equivalence as g7  # noqa: E402
from verify_g7_equivalence import drive  # noqa: E402,F401
import wg_evasion  # noqa: E402
import wg_reading_path as rp  # noqa: E402
from handlers.pre_tool_use import check_git_commit_order  # noqa: E402

_CLAIM = "閘修好了，完成。"
_RED = {"session_id": _SID, "cmd": _RELATED_CMD, "turn_seq": 5,
        "summary": "FAILED hooks/verify/verify_x.py::test_a - assert 1 == 2\n1 failed in 0.1s"}


@pytest.fixture(autouse=True)
def _interactive(monkeypatch):
    """預設互動入口（測試行程繼承的環境變數不算數）；無頭的案自己改成 sdk-cli。"""
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    monkeypatch.delenv("CLAUDE_COMPANION_JUDGE", raising=False)


def _carry(state, *keys):
    return {k: copy.deepcopy(state[k]) for k in keys if k in state}


_BOOKS = ("reconcile_gate_turn", "pending_release", "last_block", "user_released", "judge_error_blocked",
          "stop_blocked_count", "stop_blocked_turn")


# ─── 1 待放行只在同一個使用者回合有效 ────────────────────────────────────────────

def test_1_pending_from_previous_user_turn_gives_fresh_budget(driven, capsys):
    """規則：PENDING_SAME_USER_TURN。回合 1 擋滿留 pending → 回合 2（使用者新打字）同一個原因 → 預算重給、照一般擋，不直接送擋滿訊息。舊碼 pending 跨回合承接。"""
    pend = {_SID: {"reconcile": {"turn": 4, "at": "x", "reason": "r", "claims": [_CLAIM]}}}
    out, state, _ = driven(_CLAIM, capsys, pending_release=pend, turn_prompts_seq=5,
                           reconcile_gate_turn={_SID: {"turn": 4, "count": 2}})
    assert "收尾宣稱對不上" in out and "已擋滿" not in out and rl.RELEASE_TAG not in out.split("原擋訊息")[0], out[:400]
    assert {k: state["reconcile_gate_turn"][_SID][k] for k in ("turn", "count")} == {"turn": 5, "count": 1}


def test_1_released_item_not_asked_again_next_turn_until_cause_gone(exhausted, driven, capsys):
    """規則：RELEASE_COVERS_SHOWN_ITEMS。放行某一件後，原因沒消失前下一回合不再要求放行；原因消失後再出現就照擋。舊碼放行只算那一回合。"""
    out, state, _ = exhausted(capsys, after=[_ask_line(rl.OPT_RELEASE)])
    assert "ReconcileGate" not in out
    out, s6, _ = driven(_CLAIM, capsys, turn_seq=6, **_carry(state, "user_released"))
    assert "ReconcileGate" not in out                                              # 下一回合同一件：不擋、不問
    out, s7, _ = driven("全部完成了。", capsys, turn_seq=7, **_carry(s6, "user_released"))
    assert "ReconcileGate" not in out                                              # 這回合沒說修好：原因消失
    out, _, _ = driven(_CLAIM, capsys, turn_seq=8, **_carry(s7, "user_released"))
    assert "(a)" in out                                                            # 原因消失後再出現：照擋


# ─── 2 判定出錯擋一次 ──────────────────────────────────────────────────────

def _boom(*a, **k):
    raise RuntimeError("boom")


def test_2_judge_error_blocks_once_then_releases_and_logs(driven, capsys, monkeypatch):
    """規則：GATE_SELF_ERROR。"""
    monkeypatch.setattr(st, "reconcile_gate_parts", _boom)
    out, state, _ = driven(_CLAIM, capsys)
    assert "判定錯誤" in out and "boom" in out                                    # 擋 1 次
    out, _, logs = driven(_CLAIM, capsys, **_carry(state, *_BOOKS))
    assert "ReconcileGate" not in out, out[:300]                                   # 同一錯誤下一次收尾：放行
    assert any(g == "reconcile" and p.get("event") == "error" and p.get("released") is True
               and p.get("rule") == "GATE_SELF_ERROR" for g, p in logs), logs


# ─── 3 headless 主 session 比照子代理 ──────────────────────────────────────────

def test_3_headless_main_session_releases_on_third_and_never_says_cannot_release(driven, capsys, monkeypatch):
    """規則：NONINTERACTIVE_RELEASE_AT_BUDGET。"""
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    out1, s1, _ = driven(_CLAIM, capsys)
    out2, s2, _ = driven(_CLAIM, capsys, **_carry(s1, *_BOOKS))
    assert "(a)" in out1 and "(a)" in out2                                         # 擋 2 次
    out3, _, logs = driven(_CLAIM, capsys, **_carry(s2, *_BOOKS))
    assert "ReconcileGate" not in out3, out3[:300]                                 # 第 3 次放行
    assert any(p.get("event") == "noninteractive_released" for g, p in logs if g == "reconcile"), logs
    assert all("不能放行" not in o for o in (out1, out2, out3))


def test_3_subagent_block_message_does_not_say_cannot_release(sub_stop, capsys):
    """規則：NONINTERACTIVE_RELEASE_AT_BUDGET。"""
    out, _ = sub_stop(capsys, _sub_state(agent_modified_files={"ag1": [_mf(_CODE, 5)]}))
    assert "(d)" in out and "不能放行" not in out


def test_3_headless_equivalence_exhausted_releases_and_logs(drive, monkeypatch):
    """規則：NONINTERACTIVE_RELEASE_AT_BUDGET。"""
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    text = f"{g7._HOT_NO}\n{g7._DONE_TEXT}"
    out, state, _ = drive(text)
    drive(text, state=state)
    assert "REFACTOR_NEEDS_EQUIVALENCE" in out
    out3, _, logs = drive(text, state=state)
    assert drive.results == [None] and "Equivalence" not in out3                  # 擋滿：放行
    assert any(l["event"] == "noninteractive_released" for l in logs), logs


# ─── 4 版控口令持續到這批 push 完 ──────────────────────────────────────────────

_NOTIFY = "<task-notification>\n<task-id>b1</task-id>\n<status>completed</status>\n<summary>done</summary>\n</task-notification>"


def _ups(s, prompt):
    s.setdefault("recent_user_prompts", []).append(prompt)
    track_turn_prompts(s, prompt)
    s["turn_seq"] = int(s.get("turn_seq", 0)) + 1


def _commit(s):
    return check_git_commit_order("Bash", {"command": 'git commit -m "x"'}, {}, s)


def test_4_order_survives_commit_and_notification_for_gate_forced_fix():
    """規則：ORDER_UNTIL_PUSH。上GIT → commit → Stop → 背景通知開續跑回合 → 收尾閘逼出的補修 commit 不被口令閘擋。舊碼 commit 過就把口令清掉。"""
    s = {}
    _ups(s, "上GIT")
    assert _commit(s) is None
    s["last_commit_turn_seq"] = s["turn_seq"]
    s["turn_open"] = False                                                        # Stop 關回合
    _ups(s, _NOTIFY)
    assert _commit(s) is None


def test_4_user_new_message_in_continuation_needs_new_order():
    """規則：ORDER_UNTIL_PUSH。續跑回合裡使用者新打一則字 → 先前的口令失效。舊碼清單照舊追加，口令還在。"""
    s = {}
    _ups(s, "上GIT")
    s["turn_open"] = False
    _ups(s, _NOTIFY)
    _ups(s, "README 也順便看一下")
    assert _commit(s)
    s["turn_open"] = False
    _ups(s, "好，這批上GIT")
    assert _commit(s) is None


def _push_transcript(tmp_path, ok=True, cmd="git push origin pull-stop-gates"):
    tp = tmp_path / "t.jsonl"
    use = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": cmd}}]}}
    res = {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tu1", "content": "ok", "is_error": not ok}]}}
    tp.write_text(json.dumps(use) + "\n" + json.dumps(res) + "\n", encoding="utf-8")
    return tp


def test_4_push_done_spends_order_even_within_same_turn(driven, capsys, tmp_path):
    """規則：ORDER_UNTIL_PUSH。上GIT → commit → push → 收尾（Stop 從 transcript 記到 push）→ 再 commit 要新口令（同一回合、不經過背景通知也一樣）。"""
    tp = _push_transcript(tmp_path)
    s = {}
    _ups(s, "上GIT")
    _, after, _ = driven("全部完成了。", capsys, hook_input={"transcript_path": str(tp)}, **s)
    msg = _commit(after)
    assert msg and "[Guardian:CommitOrder]" in msg, msg
    s2 = {}
    _ups(s2, "上GIT")
    _, after2, _ = driven("全部完成了。", capsys, hook_input={"transcript_path": str(_push_transcript(tmp_path, ok=False))}, **s2)
    assert _commit(after2) is None                                                # push 失敗：這批還沒做完
    s3 = {}
    _ups(s3, "上GIT")
    tp3 = _push_transcript(tmp_path, cmd='git commit -m "push 前補註解"')
    _, after3, _ = driven("全部完成了。", capsys, hook_input={"transcript_path": str(tp3)}, **s3)
    assert _commit(after3) is None                                                # commit 訊息裡的 push 字樣不算推送


def test_4_echo_or_dry_run_is_not_a_push(driven, capsys, tmp_path):
    """規則：ORDER_UNTIL_PUSH。指令裡出現 push 字樣不等於推送：echo、--dry-run 都不算，口令照撐。"""
    for cmd in ("echo git push", "git push --dry-run origin x"):
        s = {}
        _ups(s, "上GIT")
        _, after, _ = driven("全部完成了。", capsys, hook_input={"transcript_path": str(_push_transcript(tmp_path, cmd=cmd))}, **s)
        assert _commit(after) is None, cmd


def test_4_push_then_commit_before_any_stop_needs_new_order(tmp_path):
    """規則：ORDER_UNTIL_PUSH。push 成功之後、還沒收尾就再 commit：口令閘自己補掃 transcript，認得這批已 push 完。"""
    s = {}
    _ups(s, "上GIT")
    s["order_transcript"] = str(_push_transcript(tmp_path))       # UserPromptSubmit 記下的 transcript 路徑
    msg = _commit(s)
    assert msg and "這批已 push 完" in msg


def test_4_push_result_written_after_scan_is_still_paired(tmp_path):
    """規則：ORDER_UNTIL_PUSH。掃的時候只看到 push 指令、結果還沒寫進來 → 下次掃到結果照樣配對成「推送完成」。"""
    from handlers.ups_gates import note_order_push
    tp = _push_transcript(tmp_path)
    use_line, res_line = tp.read_text(encoding="utf-8").splitlines(keepends=True)
    tp.write_text(use_line, encoding="utf-8")
    s = {"turn_seq": 3}
    assert note_order_push(s, str(tp)) is False and s.get("order_push_waiting") == ["tu1"]
    with open(tp, "a", encoding="utf-8") as f:
        f.write(res_line)
    assert note_order_push(s, str(tp)) is True and s["order_push_seq"] == 3


# ─── 5 病形閘擋訊息 ────────────────────────────────────────────────────────

def _load_tool(name, rel):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, VERIFY.parent.parent / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ps = _load_tool("project_smells", "tools/project-smells.py")
_SMELL_SID = "sess-gate-bypass-0001"
RETRY_PY = ("from notify import dispatch\n\nRETRY = {\n"
            '    "once": lambda k, p: (lambda r: r or dispatch.dispatch(k, p))(dispatch.dispatch(k, p)),\n'
            '    "twice": lambda k, p: (lambda r: r or dispatch.dispatch(k, p) or dispatch.dispatch(k, p))(dispatch.dispatch(k, p)),\n'
            "}\n\n\ndef retry(policy, kind, payload):\n    try:\n        return RETRY[policy](kind, payload)\n"
            "    except:\n        return False\n")


def _git(repo: Path, *args: str):
    import subprocess
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false", *args],
                          cwd=str(repo), capture_output=True, text=True, encoding="utf-8", check=True)


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def _qa_notify(tmp_path: Path, name: str = "qa-notify") -> Path:
    """題 A 的形狀：init 之後別人留了帶病的 notify/retry.py 在暫存區；這次任務改了 channels／dispatch／測試（沒暫存）。"""
    repo = tmp_path / name
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    base = {"notify/__init__.py": "", "notify/dispatch.py": "HANDLERS = {}\n\n\ndef dispatch(kind, payload):\n    return HANDLERS[kind](payload)\n",
            "notify/channels.py": "def send_mail(p):\n    return True\n", "tests/test_dispatch.py": "def test_x():\n    assert True\n"}
    for rel, text in base.items():
        _write(repo, rel, text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    _write(repo, "notify/retry.py", RETRY_PY)
    _git(repo, "add", "notify/retry.py")
    _write(repo, "notify/channels.py", "def send_mail(p):\n    return True\n\n\ndef send_webhook(p):\n    return True\n")
    _write(repo, "notify/dispatch.py", "HANDLERS = {}\n\n\ndef dispatch(kind, payload):\n    return HANDLERS[kind](payload) is not None\n")
    _write(repo, "tests/test_dispatch.py", "def test_x():\n    assert True\n\n\ndef test_y():\n    assert 1\n")
    return repo


class _SmellEnv:
    """走真實 PreToolUse 入口跑 commit：口令、隱私、合併驅動、svn 編碼換成放行，只看病形閘。"""
    def __init__(self, tmp_path: Path, monkeypatch):
        import wg_core
        from handlers import pre_tool_use as ptu
        self.ptu = ptu
        self.state = {"session": {"id": _SMELL_SID}, "turn_seq": 1}
        self.transcript = tmp_path / "transcript.jsonl"
        self.transcript.write_text("", encoding="utf-8")
        self.out = []
        monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path / "Logs")
        monkeypatch.setattr(wg_core, "write_state", lambda sid, st: None)
        monkeypatch.setattr(ptu, "read_state_status", lambda sid: (self.state, "ok"))
        for name in ("check_merge_driver", "check_git_commit_order", "check_git_privacy", "check_svn_encoding"):
            monkeypatch.setattr(ptu, name, lambda *a, **k: None)
        monkeypatch.setattr(ptu, "output_json", self.out.append)
        monkeypatch.setattr(ptu, "output_nothing", lambda: self.out.append(None))

    def run(self, repo: Path, command: str, tool: str = "Bash"):
        """走一次 PreToolUse；回 deny 的理由（沒擋回 None）。"""
        self.out.clear()
        self.ptu.handle_pre_tool_use({"tool_name": tool, "tool_input": {"command": command}, "cwd": str(repo),
                                      "session_id": _SMELL_SID, "transcript_path": str(self.transcript)}, {})
        for o in self.out:
            hso = (o or {}).get("hookSpecificOutput") or {}
            if hso.get("permissionDecision") == "deny":
                return hso.get("permissionDecisionReason")
        return None


def test_5_smell_message_teaches_commit_own_files_only():
    hit = {"name": "例外被吞掉", "why": "except 後直接 pass", "fix": "至少記 log", "path": "src/u.py", "line": 3, "text": "except: pass"}
    msg, _ = ps.render_commit_report([{"new": [hit], "listed": [], "old": [], "allowed": [], "notes": []}], "<repo>")
    assert "不是你這次寫的 → 不修" in msg and "git commit -- <你的檔>" in msg
    assert "繞閘" not in msg                                                       # 繞閘宣告已拔，沒有閘讀那行


def test_5_following_smell_message_passes_once(tmp_path, monkeypatch, git_cassette):
    """流程級：別人留在暫存區的帶病檔擋下 commit → 照擋訊息教的只提交自己的檔 → 過；而且是病形檢查本身判乾淨，
    不是靠「同一回合只擋一次」放行。"""
    monkeypatch.setitem(sys.modules, "project_smells", ps)
    monkeypatch.setattr(ps, "_hub_inputs", lambda: ({}, None))
    git_cassette(exclude=("Logs",))
    env = _SmellEnv(tmp_path, monkeypatch)
    repo = _qa_notify(tmp_path)
    deny = env.run(repo, 'git commit -m "x"')
    assert deny and "[Guardian:SmellGate]" in deny
    assert "只提交你自己的檔" in deny                                              # 擋訊息教的做法
    cmd = 'git commit -m "x" -- notify/channels.py notify/dispatch.py tests/test_dispatch.py'
    assert env.ptu.check_smell_gate("Bash", {"command": cmd}, str(repo), {})[0] is None   # 只提交自己的檔：本身就乾淨
    assert env.run(repo, cmd) is None                                              # 照做一次就過


def test_5_unstage_or_partial_commit_after_smell_deny_is_not_blocked(tmp_path, monkeypatch, git_cassette):
    """病形閘擋下之後，沒寫任何宣告就把被點名的帶病檔移出暫存、或只提交自己的檔，都不擋：病形閘只看這次要提交的內容，
    擋過之後的指令序列沒有另一道閘在看。"""
    monkeypatch.setitem(sys.modules, "project_smells", ps)
    monkeypatch.setattr(ps, "_hub_inputs", lambda: ({}, None))
    git_cassette(exclude=("Logs",))
    env = _SmellEnv(tmp_path, monkeypatch)
    repo = _qa_notify(tmp_path)
    assert "[Guardian:SmellGate]" in (env.run(repo, 'git commit -m "x"') or "")
    assert env.run(repo, "git restore --staged notify/retry.py") is None
    assert env.run(repo, 'git commit -m "x" -- notify/channels.py notify/dispatch.py tests/test_dispatch.py') is None
    assert env.run(repo, 'git commit --no-verify -m "x" -- notify/channels.py') is None
    assert "smell_deny_last" not in env.state


# ─── 6 Reload 建議閘 ───────────────────────────────────────────────────────

def test_6_reload_advice_not_judged_without_mcp_edits(driven, capsys, monkeypatch):
    """規則：RELOAD_ADVICE_MCP_EDITS_ONLY。"""
    calls = []
    monkeypatch.setattr(st, "_mcp_load_facts", lambda *a, **k: calls.append(1) or ([(1.0, 1e12)], 1.0))
    text = "全部完成了。新工具要生效，請 Reload Window。"
    out, _, _ = driven(text, capsys)
    assert "ReloadAdvice" not in out and not calls                                  # 沒改工具服務的檔：不判、不列程序表
    out, _, _ = driven(text, capsys, agent_modified_files={"ag1": [{"path": r"c:\w\tools\workflow-guardian-mcp\server.js"}]})
    assert "RELOAD_ADVICE_ALREADY_LOADED" in out and calls                         # 改過：照判


# ─── 7 退縮閘擋下的那一句不記退避旗標 ────────────────────────────────────────────

_DEFER = "全部完成了。log 清理下次再處理，留到下個 session 做。"


def test_7_deferral_block_clears_evasion_flag_for_same_sentence(driven, capsys, monkeypatch):
    """規則：DEFERRAL_COVERS_EVASION_SENTENCE。"""
    monkeypatch.setattr(st, "detect_evasion", wg_evasion.detect_evasion)
    out, state, logs = driven(_DEFER, capsys, unknown_writes=[{"cmd": "python gen.py > $OUT", "target": "UNKNOWN:redirect", "turn_seq": 5}])   # 本回合有判不出目標的寫入＝寫碼回合
    assert "[Guardian:DeferralGate]" in out, out[:300]
    assert not state.get("evasion_flag"), state.get("evasion_flag")               # 下一則使用者訊息不再注入「先處理這件」
    assert state.get("evasion_events")                                             # 事件照留（收尾檢核對照用）


def test_7_other_sentence_keeps_evasion_flag(driven, capsys, monkeypatch):
    """規則：DEFERRAL_COVERS_EVASION_SENTENCE。"""
    monkeypatch.setattr(st, "detect_evasion", wg_evasion.detect_evasion)
    text = "全部完成了。測試那段先跳過。另外 log 清理留到下個 session 做。"
    out, state, _ = driven(text, capsys, unknown_writes=[{"cmd": "python gen.py > $OUT", "target": "UNKNOWN:redirect", "turn_seq": 5}])
    assert "[Guardian:DeferralGate]" in out
    assert state.get("evasion_flag") and state["evasion_flag"]["phrase"] == "先跳過"   # 不是同一句：旗標照留


# ─── 8 紅測閘不看擋次預算、不開放行題 ─────────────────────────────────────────

def _three_red_stops(driven, capsys):
    out1, s1, _ = driven("全部完成了。", capsys, failing_tests=[dict(_RED)])
    out2, s2, _ = driven("全部完成了。", capsys, failing_tests=[dict(_RED)], **_carry(s1, *_BOOKS))
    out3, s3, logs = driven("全部完成了。", capsys, failing_tests=[dict(_RED)], **_carry(s2, *_BOOKS))
    return (out1, out2, out3), s3, logs


def test_8_testfail_blocks_every_stop_without_release_question_interactive(driven, capsys):
    """規則：RED_TEST_BLOCKS_COMPLETION。紅測還在、每次宣告完成都擋，第三次也不改問【收尾放行確認】、擋訊息每次一樣。"""
    (o1, o2, o3), _, _ = _three_red_stops(driven, capsys)
    assert all("[Guardian:TestFailGate]" in o and "verify_x.py::test_a" in o for o in (o1, o2, o3)), o3[:400]
    assert not any(rl.RELEASE_TAG in o or "已擋滿" in o for o in (o1, o2, o3)), o3[:400]
    reasons = [json.loads(o)["reason"].split("\n[Guardian:AlsoOwed]")[0] for o in (o1, o2, o3)]
    assert reasons[0] == reasons[1] == reasons[2]


def test_8_testfail_blocks_every_stop_headless_too(driven, capsys, monkeypatch):
    """規則：RED_TEST_BLOCKS_COMPLETION。沒人能回答放行詢問時一樣每次擋，不擋滿放行、不留 noninteractive_released。"""
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    (o1, o2, o3), _, logs = _three_red_stops(driven, capsys)
    assert all("[Guardian:TestFailGate]" in o for o in (o1, o2, o3)), o3[:300]
    assert not any(p.get("kind") == "testfail" for g, p in logs), logs


# ─── 8b 紅測閘前後一致：判過不算的不再擋、同一條指令的紅以最後一次看得出範圍的結果為準、真紅照擋 ─────────────────
# 實跑 2026-10-28-009-CCon-1：一條 Bash 先跑整組 pytest tests（5 passed），尾段 heredoc python 把切月函式換回 UTC 再跑兩支（刻意紅，FF）。
# 第 1 回合收尾沒宣告完成 → 紅測閘根本沒判、紅留著；第 2 回合「交材料」宣告完成 → 擋「還有 2 支沒跑綠（0 支已綠）」，多兩個模型回合。

_MIX_CMD = ("export PYTHONDONTWRITEBYTECODE=1 && python -m pytest tests -q -p no:cacheprovider; echo \"--- 實跑 by-product 2026-10\"; "
            "python -m sales.cli by-product 2026-10; echo \"exit=$?\"; echo \"--- 反證：切月換回 UTC，邊界測試應該紅\"; python - <<'EOF'\n"
            "import sys, pytest\nfrom sales import periods\nperiods.taipei_month_of = periods.month_of\n"
            "rc = pytest.main([\"-q\", \"-p\", \"no:cacheprovider\", \"tests/test_report.py::test_product_totals_uses_taipei_month_boundary\", "
            "\"tests/test_cli.py::test_by_product_cli_output\"])\nprint(\"MUTANT_CHECK PASS\" if rc != 0 else \"MUTANT_CHECK FAIL\")\nEOF")
_MIX_UNITS = ["tests/test_report.py::test_product_totals_uses_taipei_month_boundary", "tests/test_cli.py::test_by_product_cli_output"]
_MIX_OUT = (".....                                                                    [100%]\n5 passed in 0.03s\n--- 實跑 by-product 2026-10\n"
            "product=cake qty=2 amount=180.00\nexit=0\n--- 反證：切月換回 UTC，邊界測試應該紅\nFF                                       [100%]\n"
            "================================== FAILURES ===================================\n"
            "_______________ test_product_totals_uses_taipei_month_boundary ________________\n"
            ">       assert report.product_totals(rows, \"2026-10\") == {\"cake\": (1, 90.0), \"tea\": (3, 180.5)}\nE       AssertionError\n"
            "=========================== short test summary info ===========================\n"
            f"FAILED {_MIX_UNITS[0]}\nFAILED {_MIX_UNITS[1]} - AssertionError: assert...\n2 failed in 0.12s\nMUTANT_CHECK PASS\n")
_A, _B = "tests/test_a.py::test_a", "tests/test_b.py::test_b"


def _track(state, cmd, out, ok=False):
    """跑一次測試指令的 PostToolUse 記帳／清帳（輸出照 Bash 工具的 dict 回應）；回 state。"""
    from handlers import post_tool_use as ptu
    state.setdefault("session", {"id": _SID})
    ptu._track_test_result(state, {"session_id": _SID, "cwd": "", "tool_response": {"stdout": out, "stderr": "", "interrupted": False,
                                                                                    **({} if ok else {"exit_code": 1})}}, cmd, "Bash", {})
    return state


def _own_reds(state):
    import wg_release_rules as rr
    return [rr.red_units(f) for f in state.get("failing_tests") or [] if f.get("session_id") == _SID]


@pytest.fixture(autouse=True)
def _ptu_quiet(monkeypatch):
    """8b 的記帳走真的 PostToolUse 函式：守門帳不寫進本機 Logs。"""
    from handlers import post_tool_use as ptu
    monkeypatch.setattr(ptu, "append_guard_log", lambda *a, **k: None)


def test_8b_1_red_not_judged_until_completion_and_closing_declaration_does_not_move_it(driven, capsys):
    """規則：RED_TEST_BLOCKS_COMPLETION。同一筆紅：第 5 回合收尾（沒宣告完成）不判、紅照留；收尾回覆寫「負向對照｜…」也不搬走那筆紅
    （負向對照只在記紅那一刻、寫在那條指令的 `#` 註解或之前的回覆才算，NEGATIVE_CONTROL_DECLARED）。第 6 回合宣告完成照擋、擋訊息不寫「0 支已綠」。"""
    decl = "反證結果如上。\n負向對照｜verify_x.py：拿舊碼跑新測試，預期這支紅，證明新測試抓得到舊行為"
    out, s5, logs = driven(decl, capsys, turn_seq=5, failing_tests=[dict(_RED)])
    assert "TestFailGate" not in out
    assert len(s5["failing_tests"]) == 1 and "deliberate_reds" not in s5
    assert not any(g == "testfail_scope" and p.get("event") == "negative_control_declared" for g, p in logs), logs
    out, s5b, _ = driven("反證結果如上。", capsys, turn_seq=5, failing_tests=[dict(_RED)])
    assert "TestFailGate" not in out and len(s5b["failing_tests"]) == 1 and "deliberate_reds" not in s5b   # 沒宣告完成：不判、不算判過
    out, _, _ = driven("全部完成了。", capsys, turn_seq=6, failing_tests=copy.deepcopy(s5b["failing_tests"]))
    assert "TestFailGate" in out and "還有 1 支沒跑綠，不得宣告完成" in out and "支已綠" not in out, out[:300]


def test_8b_2_same_command_later_or_scoped_green_outweighs_red_so_nothing_is_owed(driven, capsys):
    """規則：RED_LAST_RESULT_IN_COMMAND。(1) 實跑那條：看得出範圍的 `pytest tests` 綠在前、heredoc 裡看不出範圍的兩支紅在後 → 不記紅
    （記 deliberate_reds），下一回合宣告完成不擋；同條指令裡看得出範圍的綠照常清舊紅。(2) 同一條指令先紅後綠（都看得出範圍）→ 不記。
    (3) 部分：紅 a、b 之後只重跑 a 綠 → 記那筆紅時 a 已在 cleared_units，只剩 b。"""
    import wg_release_rules as rr
    segs, runs = rr.test_segments(_MIX_CMD), rr.command_test_runs(_MIX_OUT)
    assert [v for _, v in segs] == [True, False] and [(len(u), g) for u, g in runs] == [(0, True), (2, False)]
    assert rr.red_units_last_result(segs, runs) == ([], _MIX_UNITS, rr.red_units_last_result(segs, runs)[2])
    old = {**_RED, "cmd": "python -m pytest tests/test_report.py -q", "summary": f"FAILED {_MIX_UNITS[0]} - x\n1 failed in 0.1s"}
    state = _track({"turn_seq": 5, "failing_tests": [dict(old)]}, _MIX_CMD, _MIX_OUT)
    assert _own_reds(state) == [] and [d["rule"] for d in state["deliberate_reds"]] == ["RED_LAST_RESULT_IN_COMMAND"]   # 舊紅也被綠那段清掉
    out, _, _ = driven("全部完成了。", capsys, turn_seq=6,
                       failing_tests=copy.deepcopy(state["failing_tests"]), deliberate_reds=copy.deepcopy(state["deliberate_reds"]))
    assert "TestFailGate" not in out, out[:300]
    state = _track({"turn_seq": 5}, "python -m pytest tests/test_a.py -q; python -m pytest tests/test_a.py -q",
                   f"FAILED {_A} - x\n1 failed in 0.1s\n1 passed in 0.1s")
    assert _own_reds(state) == [] and state["deliberate_reds"][0]["rule"] == "RED_LAST_RESULT_IN_COMMAND"
    state = _track({"turn_seq": 5}, "python -m pytest tests -q; python -m pytest tests/test_a.py -q",
                   f"FAILED {_A} - x\nFAILED {_B} - y\n2 failed, 3 passed in 1s\n1 passed in 0.1s")
    assert _own_reds(state) == [[_B]] and state["failing_tests"][0]["cleared_units"] == [_A] and "deliberate_reds" not in state


def test_8b_3_true_red_still_blocks(driven, capsys):
    """規則：RED_TEST_BLOCKS_COMPLETION 不放寬。(1) heredoc 裡單跑一次紅 → 照記；(2) 同一條指令先綠後紅（都看得出範圍）→ 最後一次是紅，照記；
    (3) 紅 a 之後只跑 b 綠 → a 照記；(4) 看得出範圍的紅之後只有看不出範圍的綠 → 照記。都記了、下一回合宣告完成 → 照擋。"""
    heredoc = "python - <<'EOF'\nimport pytest\nraise SystemExit(pytest.main([\"-q\", \"tests/test_a.py\"]))\nEOF"
    cases = [
        (heredoc, f"FAILED {_A} - x\n1 failed in 0.1s"),
        ("python -m pytest tests/test_a.py -q; python -m pytest tests/test_a.py -q", f"1 passed in 0.1s\nFAILED {_A} - x\n1 failed in 0.1s"),
        ("python -m pytest tests/test_a.py -q; python -m pytest tests/test_b.py -q", f"FAILED {_A} - x\n1 failed in 0.1s\n1 passed in 0.1s"),
        ("python -m pytest tests/test_a.py -q; " + heredoc, f"FAILED {_A} - x\n1 failed in 0.1s\n1 passed in 0.1s"),
    ]
    for cmd, out_text in cases:
        state = _track({"turn_seq": 5}, cmd, out_text)
        assert _own_reds(state) == [[_A]] and "deliberate_reds" not in state, (cmd, state.get("failing_tests"))
        out, _, _ = driven("全部完成了。", capsys, turn_seq=6, failing_tests=copy.deepcopy(state["failing_tests"]))
        assert "TestFailGate" in out and _A in out and "支已綠" not in out, (cmd, out[:300])


# ─── 放行只放使用者看過的、沒有 ✗ 條目的新原因不被吞 ─────────────────────────────────────

_TWO = "閘修好了，我量了，完成。"


def test_release_binds_to_items_the_user_was_shown(driven, capsys, tmp_path):
    """規則：RELEASE_COVERS_SHOWN_ITEMS。擋訊息只列了 (a)，使用者放行時當下又多了 (b) → 只記 (a)；下一回合 (b) 照擋。"""
    out, s1, _ = driven(_CLAIM, capsys)
    shown = s1["last_block"][_SID]["reconcile"]["items"]
    assert any("(a)" in k for k in shown) and not any("(b)" in k for k in shown)
    tp = tmp_path / "t.jsonl"
    tp.write_text(_ask_line(rl.OPT_RELEASE), encoding="utf-8")
    s1["last_block"][_SID]["reconcile"]["offset"] = 0
    out, s2, _ = driven(_TWO, capsys, tool_names=["Read"], hook_input={"transcript_path": str(tp)}, **_carry(s1, *_BOOKS))
    assert "ReconcileGate" not in out                                              # 這一回合放行
    out, _, _ = driven(_TWO, capsys, turn_seq=6, tool_names=["Read"], **_carry(s2, "user_released"))
    assert "(b)" in out and "(a) CLAIM_FIXED" not in out                           # 沒看過的 (b) 不算放行過


def test_unformatted_new_reason_is_not_swallowed_by_released_item(driven, capsys, monkeypatch):
    """規則：RELEASE_COVERS_SHOWN_ITEMS。先前放行了 (a)；這次 (a) 還在、另多一段沒有 ✗ 條目的判定錯誤 → 照擋那段錯誤，不因 (a) 已放行就整份清空。"""
    out, _, _ = driven(_CLAIM, capsys)
    key_a = [k for k in rl.release_items(json.loads(out)["reason"]) if "(a)" in k]
    monkeypatch.setattr(st, "reconcile_gate_parts", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("judge boom")))
    out, _, _ = driven(_CLAIM, capsys, turn_seq=6, user_released={_SID: {"reconcile": {"turn": 5, "items": key_a}}})
    assert "judge boom" in out and "GATE_SELF_ERROR" in out, out[:300]


# ─── 共用擋次每個使用者回合歸零 ───────────────────────────────────────────────

def test_shared_budget_resets_per_user_turn(driven, capsys, monkeypatch):
    """規則：BLOCK_BUDGET_SHARED。"""
    monkeypatch.setattr(st, "deferral_gate_reason", lambda *a, **k: "[Guardian:DeferralGate] 把可做的事推給下個 session")
    out, _, _ = driven("好了。", capsys, stop_blocked_count=2, stop_blocked_turn=5, unknown_writes=[{"cmd": "python gen.py > $OUT", "target": "UNKNOWN:redirect", "turn_seq": 5}])
    assert "DeferralGate" not in out                                               # 同一回合擋滿 2 次 → 第 3 次放行（照舊）
    out, state, _ = driven("好了。", capsys, turn_seq=6, stop_blocked_count=2, stop_blocked_turn=5, unknown_writes=[{"cmd": "python gen.py > $OUT", "target": "UNKNOWN:redirect", "turn_seq": 6}])
    assert "DeferralGate" in out and state["stop_blocked_count"] == 1              # 新的使用者回合：退縮閘照樣擋一次


# ─── 「順手看到最該修」同一個使用者回合只問一次 ──────────────────────────────────────

def test_pick_one_not_re_asked_in_continuation_of_same_user_turn():
    """問過一次 → 這一問讓對話續跑（turn_seq 往前、使用者回合不變），續跑時又改了碼 → 不再問；使用者新打一則、又改了碼 → 照常問。
    舊碼照 turn_seq 比，續跑回合被當成新的一批重問。"""
    import wg_harvest as wh
    s = {"turn_seq": 5, "turn_prompts_seq": 5}
    mods = [{"path": "c:/p/x.py", "turn_seq": 5, "last_turn_seq": 5}]
    assert wh.pick_due(s, _SID, mods, True)
    wh.mark_pick_asked(s, _SID, 5)
    s["turn_seq"] = 6
    mods = [{"path": "c:/p/x.py", "turn_seq": 5, "last_turn_seq": 6}]
    assert not wh.pick_due(s, _SID, mods, True)
    s["turn_seq"] = s["turn_prompts_seq"] = 7
    mods.append({"path": "c:/p/y.py", "turn_seq": 7, "last_turn_seq": 7})
    assert wh.pick_due(s, _SID, mods, True)


def test_pick_one_still_sent_when_stop_hook_active(driven, capsys, monkeypatch):
    """規則 PICK_ONCE_PER_USER_TURN：這次收尾是 Stop hook 讓對話續跑出來的（stop_hook_active）不當條件，照樣問（同一個使用者回合只問一次
    由 pick_due 管，案例在 verify_pick_one）；續跑旗標只交給 _pick_one_prompt 處理沒有使用者回合鍵的舊 state。
    原本這案斷言續跑不送：第一次收尾先被紅測閘擋，整回合就一次都不問（004 改 code 題現況3）。"""
    calls = []
    monkeypatch.setattr(st, "_pick_one_prompt", lambda *a, **k: calls.append(k.get("continuation")) or "[Guardian:PickOne] 順手看到最該修？")
    out, _, _ = driven("全部完成了。", capsys, hook_input={"stop_hook_active": True})
    assert "PickOne" in out and calls == [True]
    out, _, _ = driven("全部完成了。", capsys)
    assert "PickOne" in out and calls == [True, False]


# ─── 案例宣告接線：對帳帶 case_for＝wg_verify_ledger.declared_cases(...) ─────────────────────────────

def test_declared_cases_wired_into_reconcile(driven, capsys, monkeypatch):
    seen, marker = [], (lambda path: ["verify_x.py"])
    calls = []
    monkeypatch.setattr(st, "declared_cases", lambda cfg, tp="": calls.append(tp) or marker)   # 第 2 個參數＝transcript 路徑（case_for｜ 行從它讀）
    real = st.reconcile_gate_parts
    monkeypatch.setattr(st, "reconcile_gate_parts", lambda *a, **k: seen.append(k) or real(*a, **k))
    driven(_CLAIM, capsys)
    assert len(calls) == 1 and seen and seen[-1].get("case_for") is marker


# ─── v6 守門總開關關時照 9e476fd0：共用擋次整個 session 累計、口令 commit 過就用掉 ─────────────────

@pytest.fixture()
def v6_off(monkeypatch):
    monkeypatch.setenv("WG_V6", "0")


def test_v6_off_shared_budget_stays_session_wide(driven, capsys, monkeypatch, v6_off):
    """規則：BLOCK_BUDGET_SHARED。"""
    monkeypatch.setattr(st, "deferral_gate_reason", lambda *a, **k: "[Guardian:DeferralGate] 把可做的事推給下個 session")
    out, state, _ = driven("好了。", capsys, turn_seq=6, stop_blocked_count=2, stop_blocked_turn=5)
    assert "DeferralGate" not in out and state["stop_blocked_count"] == 2          # 換了使用者回合也不歸零
    out, state, _ = driven("好了。", capsys, turn_seq=6, stop_blocked_count=0)
    assert "DeferralGate" in out                                                   # 前置：沒擋滿照擋


def test_v6_off_order_spent_by_commit_and_kept_on_continuation_typing(v6_off):
    """規則：ORDER_UNTIL_PUSH。"""
    s = {}
    _ups(s, "上GIT")
    s["last_commit_turn_seq"] = s["turn_seq"]
    s["turn_open"] = False
    _ups(s, _NOTIFY)
    assert _commit(s)                                                              # commit 過就用掉
    s2 = {}
    _ups(s2, "上GIT")
    s2["turn_open"] = False
    _ups(s2, _NOTIFY)
    _ups(s2, "README 也順便看一下")
    assert s2["turn_prompts"] == ["上GIT", "README 也順便看一下"] and _commit(s2) is None   # 續跑回合補一句：照舊追加


def test_v6_off_stop_does_not_scan_push_and_commit_gate_ignores_it(driven, capsys, tmp_path, v6_off):
    """規則：ORDER_UNTIL_PUSH。"""
    s = {}
    _ups(s, "上GIT")
    _, after, _ = driven("全部完成了。", capsys, hook_input={"transcript_path": str(_push_transcript(tmp_path))}, **s)
    assert "order_push_seq" not in after and "order_transcript" not in after
    assert _commit({**after, "order_push_seq": after["turn_seq"]}) is None          # 口令閘不看 push


def test_v6_off_deferral_block_keeps_evasion_flag(driven, capsys, monkeypatch, v6_off):
    """規則：DEFERRAL_COVERS_EVASION_SENTENCE。"""
    monkeypatch.setattr(st, "detect_evasion", wg_evasion.detect_evasion)
    out, state, _ = driven(_DEFER, capsys)
    assert "[Guardian:DeferralGate]" in out and state.get("evasion_flag")          # 照舊記旗標


# ─── 閱讀路徑尾段不重複那一題 ─────────────────────────────────────────────────

_ITEM = {"kind": "函式", "name": "y.py::b", "keys": ["y.py::b", "b"], "nums": "巢狀 4｜條件塊 2"}
_RP_TEXT = "\n".join([f"{rp.TAG} 閱讀路徑量完：", "  函式數據 1 筆", *rp.PROMPT_LINES,
                      "    " + rp.JUDGMENT_EXAMPLE.format(name="y.py::b")])


def test_reading_path_question_once_when_turn_judgment_blocks(driven, capsys, monkeypatch):
    monkeypatch.setattr(st, "coding_turn", lambda *a, **k: True)
    monkeypatch.setattr(st, "reading_path_note", lambda *a, **k: (_RP_TEXT, False))
    owed = {_SID: {"owed": {"turn": 5, "items": [dict(_ITEM)]}}}
    out, _, _ = driven("全部完成了。", capsys, reading_path=owed)
    reason = json.loads(out)["reason"]
    assert "TURN_JUDGMENT_REQUIRED" in reason and reason.count(rp.JUDGMENT_QUESTION) == 1, reason[-600:]
    assert "函式數據 1 筆" in reason                                               # 數據行照留
    out, _, _ = driven(_CLAIM, capsys, reading_path=copy.deepcopy(owed))
    reason = json.loads(out)["reason"]
    assert "(a)" in reason and reason.count(rp.JUDGMENT_QUESTION) == 1            # 別的閘擋：尾段照附原文（唯一一處）


# ─── 流程級：擋 → 照做 → 再收尾，只欠「改完之後跑綠一次」 ───────────────────────────────

def test_flow_red_then_fix_and_green_owes_nothing_else(driven, capsys):
    code = _mf(_CODE, 5, last_at=_T1, last_seq=3)
    case = _mf(_CASE, 5, last_at=_T1, last_seq=4)
    out, s1, _ = driven("全部完成了。", capsys, modified_files=[code, case], failing_tests=[dict(_RED)])
    assert "TestFailGate" in out                                                   # 擋
    fixed = _mf(_CODE, 5, last_at=_T2, last_seq=7)                                 # 照做：改碼
    green = _rcpt(5, cmd=_RELATED_CMD, at=_T2, seq=8)                              # 改完之後跑綠
    out, s2, _ = driven("修好了，全部完成了。", capsys, modified_files=[fixed, case], failing_tests=[],
                        verify_receipts={_SID: [green]}, anti_evasion_report=_aec(5, j=__file__, k="無"),
                        **_carry(s1, *_BOOKS))
    assert "[Guardian:" not in out and "[Workflow Guardian]" not in out, out[:400]   # 沒有別的收尾閘因這次改動重欠
    out, _, _ = driven("修好了，全部完成了。", capsys, modified_files=[fixed, case], failing_tests=[],
                       verify_receipts={_SID: []}, anti_evasion_report=_aec(5, j=__file__, k="無"),
                       **_carry(s2, *_BOOKS))
    assert "(a)" in out                                                            # 配對：沒跑綠就欠那一張收據


if __name__ == "__main__":
    rc = pytest.main([__file__, "-q", "-p", "no:cacheprovider"])
    print("PULL_STOP_GATES_CHECK PASS" if rc == 0 else "PULL_STOP_GATES_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)


@pytest.fixture(autouse=True)
def _block_mode(monkeypatch):
    """規則 GATE_MODE_TABLE：送法只讀 wg_release_rules.RULE_MODE。這個檔的案例驗的是判定與擋訊息內容，把送法釘成 block 讓它們照驗；
    v6 預設的提醒送法（Stop 只留帳、提醒掛改檔那則工具結果）由 verify_gate_mode_stop.py 驗。"""
    import wg_release_rules as _rr
    monkeypatch.setattr(_rr, "mode_of", lambda rule: _rr.BLOCK)
