"""verify_pull_stop_gates.py：收尾閘不再讓 AI 修不停或卡死、版控口令持續到這批 push 完的會紅案例（改前紅、改後綠）。

逐件（每件標它驗的是哪一條）：
  1 待放行只在同一個使用者回合有效；放行的那一件之後的回合原因還在不再問
  2 寫碼查核自己判定出錯：擋一次，同一個錯誤下一次收尾放行並留帳
  3 headless 主 session 比照子代理：擋滿放行留帳、擋訊息不說「不能放行」（等值閘同）
  4 「上GIT」持續到這批 push 完：背景通知與收尾閘逼出的補修 commit 不用重下；使用者新打字、push 完成就失效
  5 病形閘擋訊息教「# 不是繞閘｜」，照做一次就過（流程級）
  6 Reload 建議閘只在本 session 改過工具服務的檔才判
  7 退縮閘擋下的那一句不再記退避旗標（下一則使用者訊息不再追問）
  8 紅測閘吃寫碼查核那份每回合預算：擋滿問使用者（互動）／放行留帳（無頭）
  9 第二意見的待放行只在同一個使用者回合有效
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
    _SID, _CODE, _CASE, _RELATED_CMD, _T1, _T2, _aec, _ask_line, _git_budget_generous, _mf, _rcpt, _scope_ledger_isolated,
    _sub_state, _temp_rules_off, driven, exhausted, rl, st, sub_stop, track_turn_prompts,
)
import verify_g7_equivalence as g7  # noqa: E402
from verify_g7_equivalence import drive  # noqa: E402,F401
import verify_gate_bypass as gb  # noqa: E402
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
          "stop_blocked_count", "stop_blocked_turn", "second_opinion_gate_turn")


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

def test_5_smell_message_teaches_not_bypass_declaration():
    hit = {"name": "例外被吞掉", "why": "except 後直接 pass", "fix": "至少記 log", "path": "src/u.py", "line": 3, "text": "except: pass"}
    msg, _ = gb.ps.render_commit_report([{"new": [hit], "listed": [], "old": [], "allowed": [], "notes": []}], "<repo>")
    assert "# 不是繞閘｜" in msg and "git commit -- <你的檔>" in msg


def test_5_following_smell_message_passes_once(tmp_path, monkeypatch, git_cassette):
    """流程級：別人留在暫存區的帶病檔擋下 commit → 照擋訊息教的「# 不是繞閘｜…」＋只提交自己的檔送一次 → 過。"""
    monkeypatch.setitem(sys.modules, "project_smells", gb.ps)
    monkeypatch.setattr(gb.ps, "_hub_inputs", lambda: ({}, None))
    git_cassette(exclude=("Logs",))
    env = gb.Env(tmp_path, monkeypatch)
    repo = gb._qa_notify(tmp_path)
    deny = env.run(repo, 'git commit -m "x"')
    assert deny and "[Guardian:SmellGate]" in deny
    assert "# 不是繞閘｜" in deny                                                  # 擋訊息教的做法
    cmd = ("# 不是繞閘｜notify/retry.py 是別人留在暫存區的，不屬這次需求，病交原作者修\n"
           'git commit -m "x" -- notify/channels.py notify/dispatch.py tests/test_dispatch.py')
    assert env.run(repo, cmd) is None                                              # 照做一次就過


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
    out, state, logs = driven(_DEFER, capsys, need_goal_code_decl_turn=5)
    assert "[Guardian:DeferralGate]" in out, out[:300]
    assert not state.get("evasion_flag"), state.get("evasion_flag")               # 下一則使用者訊息不再注入「先處理這件」
    assert state.get("evasion_events")                                             # 事件照留（收尾檢核對照用）


def test_7_other_sentence_keeps_evasion_flag(driven, capsys, monkeypatch):
    """規則：DEFERRAL_COVERS_EVASION_SENTENCE。"""
    monkeypatch.setattr(st, "detect_evasion", wg_evasion.detect_evasion)
    text = "全部完成了。測試那段先跳過。另外 log 清理留到下個 session 做。"
    out, state, _ = driven(text, capsys, need_goal_code_decl_turn=5)
    assert "[Guardian:DeferralGate]" in out
    assert state.get("evasion_flag") and state["evasion_flag"]["phrase"] == "先跳過"   # 不是同一句：旗標照留


# ─── 8 紅測閘的擋次上限 ─────────────────────────────────────────────────────

def _three_red_stops(driven, capsys):
    out1, s1, _ = driven("全部完成了。", capsys, failing_tests=[dict(_RED)])
    out2, s2, _ = driven("全部完成了。", capsys, failing_tests=[dict(_RED)], **_carry(s1, *_BOOKS))
    out3, s3, logs = driven("全部完成了。", capsys, failing_tests=[dict(_RED)], **_carry(s2, *_BOOKS))
    return (out1, out2, out3), s3, logs


def test_8_testfail_third_stop_asks_user_interactive(driven, capsys):
    """規則：BLOCK_BUDGET_SHARED。"""
    (o1, o2, o3), _, _ = _three_red_stops(driven, capsys)
    assert "TestFailGate" in o1 and "TestFailGate" in o2 and rl.RELEASE_TAG not in o2
    assert "已擋滿" in o3 and rl.RELEASE_TAG in o3 and "verify_x.py::test_a" in o3, o3[:400]


def test_8_testfail_third_stop_releases_and_logs_headless(driven, capsys, monkeypatch):
    """規則：NONINTERACTIVE_RELEASE_AT_BUDGET。"""
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    (o1, o2, o3), _, logs = _three_red_stops(driven, capsys)
    assert "TestFailGate" in o1 and "TestFailGate" in o2
    assert "TestFailGate" not in o3, o3[:300]
    assert any(p.get("event") == "noninteractive_released" and p.get("kind") == "testfail" for g, p in logs), logs


def test_8_released_red_tests_do_not_cover_a_new_failure(driven, capsys):
    """規則：RELEASE_COVERS_SHOWN_ITEMS。放行的紅測鍵是指令＋全部失敗節點：放行 A、B、C、D 之後換成 A、B、C、E → 照擋（摘要都寫「A、B、C 等 4 支」也不混）。"""
    def red(*names):
        return {**_RED, "summary": "\n".join(f"FAILED hooks/verify/verify_x.py::{n} - x" for n in names)}
    out, s1, _ = driven("全部完成了。", capsys, failing_tests=[red("a", "b", "c", "d")])
    s1["last_block"][_SID]["testfail"]["offset"] = 0
    out, s2, _ = driven("全部完成了。", capsys, failing_tests=[red("a", "b", "c", "d")],
                        turn_prompts=list(s1["last_block"][_SID]["testfail"]["prompts"]) + ["放行"], **_carry(s1, *_BOOKS))
    assert "TestFailGate" not in out                                               # 使用者打「放行」
    out, _, _ = driven("全部完成了。", capsys, turn_seq=6, failing_tests=[red("a", "b", "c", "d")], **_carry(s2, *_BOOKS))
    assert "TestFailGate" not in out                                               # 下一回合同一批紅：不再擋
    out, _, _ = driven("全部完成了。", capsys, turn_seq=6, failing_tests=[red("a", "b", "c", "e")], **_carry(s2, *_BOOKS))
    assert "TestFailGate" in out                                                   # 換了一支紅：照擋


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
    import wg_need_goal
    monkeypatch.setattr(wg_need_goal, "goal_gate_reason", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("goal boom")))
    out, _, _ = driven(_CLAIM, capsys, turn_seq=6, user_released={_SID: {"reconcile": {"turn": 5, "items": key_a}}})
    assert "goal boom" in out and "GATE_SELF_ERROR" in out, out[:300]


# ─── 9 第二意見的待放行只在同一個使用者回合有效 ────────────────────────────────────

def test_9_second_opinion_pending_from_previous_turn_not_exhausted(driven, capsys, monkeypatch):
    """規則：PENDING_SAME_USER_TURN。"""
    from wg_release_rules import Verdict
    monkeypatch.setattr(st, "_so_facts", lambda *a, **k: (Verdict("SECOND_OPINION_REQUIRED", True, "大任務要第二意見"),
                                                         {"code_files": 6, "triggers": ["files"]}))
    monkeypatch.setattr(st, "_so_auto_cfg", lambda cfg: {"enabled": True, "max_blocks_per_turn": 1})
    pend = {_SID: {"second_opinion": {"turn": 4, "at": "x", "reason": "r", "claims": ["全部完成了。"]}}}
    out, _, _ = driven("全部完成了。", capsys, pending_release=pend, turn_prompts_seq=5,
                       last_block={_SID: {"second_opinion": {"offset": 0, "prompts": [], "turn": 4}}})
    assert "[Guardian:SecondOpinion] 收尾要處理第二意見" in out and "已擋滿" not in out, out[:300]


# ─── 共用擋次每個使用者回合歸零 ───────────────────────────────────────────────

def test_shared_budget_resets_per_user_turn(driven, capsys, monkeypatch):
    """規則：BLOCK_BUDGET_SHARED。"""
    monkeypatch.setattr(st, "deferral_gate_reason", lambda *a, **k: "[Guardian:DeferralGate] 把可做的事推給下個 session")
    out, _, _ = driven("好了。", capsys, stop_blocked_count=2, stop_blocked_turn=5, need_goal_code_decl_turn=5)
    assert "DeferralGate" not in out                                               # 同一回合擋滿 2 次 → 第 3 次放行（照舊）
    out, state, _ = driven("好了。", capsys, turn_seq=6, stop_blocked_count=2, stop_blocked_turn=5, need_goal_code_decl_turn=6)
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
    monkeypatch.setattr(st, "declared_cases", lambda state, sid, cfg: calls.append(sid) or marker)
    real = st.reconcile_gate_parts
    monkeypatch.setattr(st, "reconcile_gate_parts", lambda *a, **k: seen.append(k) or real(*a, **k))
    driven(_CLAIM, capsys)
    assert calls == [_SID] and seen and seen[-1].get("case_for") is marker


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
