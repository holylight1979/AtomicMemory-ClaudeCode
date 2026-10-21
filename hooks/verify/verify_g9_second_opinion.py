"""verify_g9_second_opinion.py：G9 自動第二意見（規則 SECOND_OPINION_REQUIRED／SECOND_OPINION_DECLINED）。

紅案例（改前紅、改後綠）：改 5 個程式檔宣告完成、本回合沒跑 → 擋（訊息列規則名、檔數、缺什麼，末尾是「要跑：…；或宣告
`不需第二意見｜<理由>`」）；同情境 start→result done＋收尾四行 → 放行；只改 1 檔但在 hooks/wg_release_rules.py → 擋；2 檔不在
risky、改 40 行 → 不擋（200 行 → 擋）；「不需第二意見｜只重錄 cassettes」→ 放行並留一筆 declined；「不需第二意見｜不需要」→ 擋；
result failed＋四行 → 放行；result running → 擋（說等 result）；子代理、headless → 不觸發；pack 有目標樹時 manifest 多 goal.md、
hash 和沒樹時不同；question 不含樹根那句 → prepare 回 blocked 附原因；收尾缺「裁決與理由」行 → 擋並點名。
另守：部位表類別 gate、擋滿改問使用者與放行、滿足後沒再改程式不再要求、question 被擋那次不算跑過、PreToolUse 補 session_id、
週健檢列 declined、前面的閘擋下時預覽列出第二意見、本回合窗口之前的 start／result 不算；codex 審查後補的：只認 result 回的狀態
（沒開出 job 的 failed 不算）、session 有樹而材料沒帶到樹不算、散文或程式碼區塊裡的宣告行與四行不算、判定出錯不擋但留帳。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_g9_second_opinion.py
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
CODE_DIR = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CODE_DIR / "lib"))

import wg_release_rules as rr  # noqa: E402
import wg_second_opinion as so  # noqa: E402
import wg_need_goal as ng  # noqa: E402
from wg_release import RELEASE_TAG, OPT_RELEASE  # noqa: E402
from handlers import stop as st  # noqa: E402
from handlers import pre_tool_use as pt  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


SID = "sid-g9"
START = "mcp__workflow-guardian__second_opinion_start"
RESULT = "mcp__workflow-guardian__second_opinion_result"
JOB = "20261020-120000-sidg9xxx-stage-review"
HINT_TAIL = "或宣告 `不需第二意見｜<理由>`"
DONE = "全部完成。"
FOUR = ("## 第二意見與分歧裁決\n- Codex 結論：閘的判定正確\n- 我方結論：同意\n- 分歧點：門檻數字要不要調\n"
        "- 裁決與理由：照總控台定的門檻，因為那是事實核對\n全部完成。")


class Tx:
    """假 transcript（jsonl）：使用者打字、工具呼叫與回傳、assistant 文字，依序追加。"""

    def __init__(self, path: Path):
        self.path, self.n = path, 0
        path.write_text("", encoding="utf-8")

    def add(self, obj):
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def user(self, text):
        self.add({"type": "user", "message": {"role": "user", "content": text}})

    def say(self, text):
        self.add({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})

    def call(self, name, inp, result_text, extra=None):
        self.n += 1
        tid = f"t{self.n}"
        self.add({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
        self.add({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid,
                                                           "content": [{"type": "text", "text": result_text}]}]},
                  **(extra or {})})

    def opinion(self, status="done", job=JOB, mode="independent", kind="stage-review", start_status="started", reason="",
                notes=()):
        tail = f"\nreason: {reason}" if reason else ""
        self.call(START, {"mode": mode, "kind": kind, "part": "p", "cwd": "c", "question": "q"},
                  f"job_id: {job}\nhash: h\nstatus: {start_status}{tail}" + "".join(f"\nnote: {n}" for n in notes))
        if status:
            self.call(RESULT, {"job_id": job}, f"status: {status}\njob_id: {job}{tail}")


def _mf(path, turn=5):
    return {"path": str(path), "tool": "Edit", "session_id": SID, "turn_seq": turn, "last_turn_seq": turn}


def _files(tmp_path, n, sub="proj/src"):
    return [tmp_path / sub / f"m{i}.py" for i in range(n)]


def _reason(out: str) -> str:
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]
    return json.loads(lines[-1]).get("reason", "") if lines else ""


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _repo(tmp_path, files):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "core.autocrlf", "false")
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _lines(n, tag="x"):
    return "".join(f"{tag}{i} = {i}\n" for i in range(n))


@pytest.fixture(autouse=True)
def _temp_rules_off(monkeypatch):
    """假專案落在 pytest tmp：關掉暫存規則（同 verify_stop_reconcile）。"""
    monkeypatch.setenv("WG_TEMP_RULES", "off")


@pytest.fixture()
def drive(monkeypatch, tmp_path):
    """驅動 handle_stop：別的閘關掉或換成不擋，只留 SecondOpinion 段與它前面的 TestFail；回 run(text, capsys, …) → (reason, state, logs)。"""
    logs: list = []
    stubs = {
        "_find_session_transcript": lambda *a, **k: None, "token_warn_payload": lambda *a, **k: "",
        "detect_evasion": lambda *a, **k: None, "write_state": lambda *a, **k: None,
        "_attribute_usefulness": lambda *a, **k: None, "_detect_uncommitted_files": lambda mf: [],
        "_maybe_spawn_user_extract_worker": lambda *a, **k: None, "_hud_alive": lambda *a, **k: (True, {}),
        "harvest_gate_reason": lambda *a, **k: None, "pending_gate_reason": lambda *a, **k: None,
        "deferral_gate_reason": lambda *a, **k: None, "_record_pick": lambda *a, **k: None,
        "_acceptance_regression_hint": lambda *a, **k: "", "reading_path_note": lambda *a, **k: ("", False),
        "_should_deep_postmortem": lambda *a, **k: False, "_pick_one_prompt": lambda *a, **k: None,
        "detect_missing_aec_emission": lambda *a, **k: False,
        "leftover_cleanup_verdict": lambda *a, **k: rr.Verdict("LEFTOVER_NEEDS_CLEANUP", False, "測試關掉"),
        "claims_completion": lambda t: "完成" in str(t or ""),
        "append_guard_log": lambda guard, payload: logs.append((guard, payload)),
    }
    for name, fn in stubs.items():
        monkeypatch.setattr(st, name, fn)
    monkeypatch.setattr(st.aec_ledger, "collect_at_completion", lambda *a, **k: None)
    monkeypatch.delenv("CLAUDE_COMPANION_JUDGE", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    tx = Tx(tmp_path / "transcript.jsonl")
    tx.user("做 G9")

    def run(text, capsys, files=(), state=None, hook_input=None, config=None):
        if state is None:
            state = {"phase": "working", "modified_files": [_mf(p) for p in files], "failing_tests": [],
                     "recent_user_prompts": [], "stop_blocked_count": 0, "turn_seq": 5, "turn_prompts_seq": 5, "muted": True}
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        tx.say(text)
        logs.clear()
        cfg = {"reconcile_gate": {"enabled": False}, "verify_scope": {"enabled": False}, "aec": {"scan_report_gate": False},
               "atom_audit": {"enabled": False}, "sync_reminder": {"enabled": False}, **(config or {})}
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": SID, "cwd": "", "transcript_path": str(tx.path), "last_assistant_message": text,
                            **(hook_input or {})}, cfg)
        return _reason(capsys.readouterr().out), state, list(logs)

    run.tx = tx
    return run


def _so_logs(logs, event=None):
    return [p for g, p in logs if g == "second_opinion" and (event is None or p.get("event") == event)]


# ─── 紅案例：Stop 端 ─────────────────────────────────────────────────────

def test_five_files_no_run_blocks_with_rule_count_and_entry(drive, capsys, tmp_path):
    reason, state, logs = drive(DONE, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" in reason and "SECOND_OPINION_REQUIRED" in reason
    assert "程式檔 5 個" in reason and "本回合沒有跑第二意見" in reason
    own = reason.split("\n判準卡（")[0]          # 切入點契約：判準卡接在擋訊息後面，入口在閘自己訊息的最末
    assert own.rstrip().endswith(HINT_TAIL), own[-200:]
    assert "second_opinion_start(mode=independent, kind=stage-review, question=<含樹根那句>)→second_opinion_result" in reason
    assert [p["event"] for p in _so_logs(logs)] == ["block"]


def test_five_files_done_and_four_lines_passes(drive, capsys, tmp_path):
    drive.tx.opinion("done")
    reason, state, logs = drive(FOUR, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" not in reason
    assert state["second_opinion_ok"][SID] == 5, "閘有跑到、判定滿足（不是因為沒跑到才沒擋）"


STOP_FEEDBACK = ("Stop hook feedback:\n[Guardian:ReadingPath] ✗ (t) TURN_JUDGMENT_REQUIRED：側面數據到門檻的 1 條裡 1 條"
                 "沒有五欄齊的「拐彎判斷｜」行（程式只核對五欄，不評內容）")


def test_job_done_then_other_gate_stop_feedback_still_counts(drive, capsys, tmp_path):
    """第二波 C′（C-1 transcript:254～384）：同一則使用者訊息內 job 已 done，之後別的閘擋了一次，Claude Code 把擋訊息寫成一筆
    user 紀錄「Stop hook feedback:…」（isMeta）；那不是使用者打字，不能當回合起點把 job 切掉（舊碼連擋兩次，AI 只好自放行）。"""
    drive.tx.opinion("done")
    drive.tx.add({"type": "user", "isMeta": True, "message": {"role": "user", "content": STOP_FEEDBACK}})
    reason, state, logs = drive(FOUR, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" not in reason
    assert state["second_opinion_ok"][SID] == 5, "閘有跑到、判定滿足（不是因為沒跑到才沒擋）"


C2_DONE = "折扣碼功能做完了：15 個測試全過，已 commit（59298ec），沒有 push。"
C2_PATCH = "拐彎判斷｜orders/cli.py::<main> → orders/pricing.py::discount｜不會：只拐兩個彎｜checkout 規定計算順序｜合理"


def test_c2_done_then_other_gate_patch_reply_still_blocks_once(drive, capsys, tmp_path):
    """第二波 C′ 第二跑（C2 transcript:304→315→321）：改了 5 支程式、收尾說「做完了…已 commit」→ ReadingPath 先擋 → 補件那則
    只補拐彎判斷、不再重說完成。舊碼只看最後一則（又認不得「做完了」），判成沒宣告完成，第二意見閘一次都沒擋。
    改後：本回合最後一則談到完成與否的回覆說做完了 → 宣告完成且過門檻，必擋一次（不是只算沒 commit 的檔：own_mod_files 不看 commit）。"""
    drive.tx.say(C2_DONE)
    drive.tx.add({"type": "user", "isMeta": True, "message": {"role": "user", "content": STOP_FEEDBACK}})
    reason, _state, logs = drive(C2_PATCH, capsys, files=_files(tmp_path, 5))
    assert "SECOND_OPINION_REQUIRED" in reason and "程式檔 5 個" in reason
    assert [p["event"] for p in _so_logs(logs)] == ["block"]


def test_partial_done_then_final_in_progress_not_required(drive, capsys, tmp_path):
    """Codex：同回合先說「第一階段完成」、最後一則說「整體仍進行中，等待測試結果」→ 最後一則有狀態詞，照它（不算宣告完成）。"""
    drive.tx.say("第一階段完成：資料表搬好了。")
    reason, _state, logs = drive("整體仍進行中，等待測試結果回來再整理。", capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs)


def test_done_then_patch_mentioning_solution_still_blocks(drive, capsys, tmp_path):
    """Codex：說「全部做完了」→ 別的閘擋 → 補件只寫「拐彎判斷｜檢查解決方案的依賴｜合理」；「解決方案」不是完成與否的話，前面的宣告照算。"""
    drive.tx.say("全部做完了，測試都過。")
    drive.tx.add({"type": "user", "isMeta": True, "message": {"role": "user", "content": STOP_FEEDBACK}})
    reason, _state, logs = drive("拐彎判斷｜檢查解決方案的依賴｜不會：兩個彎｜各管一件事｜合理", capsys, files=_files(tmp_path, 5))
    assert "SECOND_OPINION_REQUIRED" in reason and [p["event"] for p in _so_logs(logs)] == ["block"]


def test_done_then_later_not_done_reply_not_required(drive, capsys, tmp_path):
    drive.tx.say(C2_DONE)
    reason, _state, logs = drive("還沒做完：ERP 合約測試照你說的留紅，另有 8 個檔等你說 commit。", capsys,
                                 files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs)            # 最後談到的是「還沒完成」→ 照舊不算宣告


def test_block_message_says_last_reply_keeps_four_lines(drive, capsys, tmp_path):
    """第二波 B′／C′（B1、C3）：被別的閘擋後補的最後一則只寫「見上一則」，四行裁決沒留在交付末尾。擋訊息要講明最後一則要保留。"""
    reason, _state, _logs = drive(DONE, capsys, files=_files(tmp_path, 5))
    assert "交付的最後一則也要保留這四行" in reason and "不要寫「見上一則」" in reason
    assert reason.split("\n判準卡（")[0].rstrip().endswith(HINT_TAIL)                 # 入口仍在閘自己訊息的最末


def test_job_from_previous_user_prompt_still_blocks(drive, capsys, tmp_path):
    drive.tx.opinion("done")
    drive.tx.user("再加一個匯出功能")                                                   # 換了一則使用者訊息：上一則跑的不算
    reason, _state, _logs = drive(FOUR, capsys, files=_files(tmp_path, 5))
    assert "SECOND_OPINION_REQUIRED" in reason and "本回合沒有跑第二意見" in reason


def test_failed_result_with_four_lines_passes(drive, capsys, tmp_path):
    drive.tx.opinion("failed", reason="探針逾時")
    text = FOUR.replace("閘的判定正確", "failed（探針逾時），沒有結論")
    reason, state, _ = drive(text, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" not in reason and state["second_opinion_ok"][SID] == 5


def test_running_blocks_and_says_wait(drive, capsys, tmp_path):
    drive.tx.opinion("running")
    reason, _, _ = drive(FOUR, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" in reason and "還在跑" in reason and "second_opinion_result" in reason


def test_missing_verdict_line_blocks_and_names_it(drive, capsys, tmp_path):
    drive.tx.opinion("done")
    text = FOUR.replace("- 裁決與理由：照總控台定的門檻，因為那是事實核對\n", "")
    reason, _, _ = drive(text, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" in reason and "「裁決與理由：」行" in reason
    assert "「Codex 結論：」行" not in reason, "只點名缺的那一行"


@pytest.mark.parametrize("rel", ["hooks/wg_release_rules.py", "hooks/wg_second_opinion.py"])
def test_one_file_in_risky_prefix_blocks(drive, capsys, tmp_path, rel):
    root = _repo(tmp_path, {rel: _lines(3)})
    reason, _, _ = drive(DONE, capsys, files=[root / rel])
    assert "[Guardian:SecondOpinion]" in reason and f"改到高風險部位：{rel.rsplit('/', 1)[-1]}" in reason


def test_two_files_40_lines_not_risky_passes_but_200_lines_blocks(drive, capsys, tmp_path):
    root = _repo(tmp_path, {"src/a.py": _lines(50, "a"), "src/b.py": _lines(50, "b")})
    paths = [root / "src" / "a.py", root / "src" / "b.py"]
    for p in paths:
        p.write_text(p.read_text(encoding="utf-8") + _lines(20, "n"), encoding="utf-8", newline="\n")
    v, facts = so.check({}, SID, [_mf(p) for p in paths], DONE, "", {}, so.auto_cfg({}), True)
    assert facts["changed_lines"] == 40 and facts["triggers"] == [] and not v.owed, "前置：40 行、沒觸發"
    reason, state, logs = drive(DONE, capsys, files=paths)
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs) and "second_opinion_ok" not in state
    paths[0].write_text(paths[0].read_text(encoding="utf-8") + _lines(180, "m"), encoding="utf-8", newline="\n")
    reason, _, _ = drive(DONE, capsys, files=paths)
    assert "[Guardian:SecondOpinion]" in reason and "對 HEAD 的程式改動 220 行" in reason


def test_session_scratch_scripts_not_counted_but_same_shape_in_repo_is(tmp_path, monkeypatch):
    """規則 SESSION_SCRATCH_NOT_CODE：背景工作暫存區 jobs/<id>/tmp/ 底下的量測腳本不算改了程式檔（選型軌實遇：12 支量測腳本
    被算成改碼、要第二意見）；同樣形狀的路徑放在 repo 裡照算、照觸發門檻。"""
    cc = tmp_path / "cc"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cc))
    for base, n_code in ((cc, 0), (tmp_path / "proj", 5)):
        paths = [base / "jobs" / "8bd2fa36" / "tmp" / f"probe_{i}.py" for i in range(5)]
        for p in paths:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x = 1\n", encoding="utf-8")
        v, facts = so.check({}, SID, [_mf(p) for p in paths], DONE, "", {}, so.auto_cfg({}), True)
        assert facts["code_files"] == n_code, (base, facts)
        assert bool(facts["triggers"]) == bool(n_code) and v.owed == bool(n_code), (base, facts)


def test_decline_with_reason_passes_and_logs(drive, capsys, tmp_path):
    reason, state, logs = drive("不需第二意見｜只重錄 cassettes\n全部完成。", capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" not in reason and state["second_opinion_ok"][SID] == 5
    declined = _so_logs(logs, "declined")
    assert len(declined) == 1 and declined[0]["reason"] == "只重錄 cassettes" and declined[0]["code_files"] == 5


@pytest.mark.parametrize("why", ["不需要", "", "<理由>", "不需要。"])
def test_decline_without_real_reason_blocks(drive, capsys, tmp_path, why):
    reason, _, logs = drive(f"不需第二意見｜{why}\n全部完成。", capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" in reason and "SECOND_OPINION_DECLINED" in reason and not _so_logs(logs, "declined")


def test_subagent_and_headless_not_triggered(drive, capsys, tmp_path, monkeypatch):
    reason, state, logs = drive(DONE, capsys, files=_files(tmp_path, 5), hook_input={"agent_id": "a1"})
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs) and "second_opinion_gate_turn" not in state
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    reason, state, logs = drive(DONE, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    reason, _, _ = drive(DONE, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" in reason, "同一份事實換回互動入口就擋（前置成立）"


def test_question_root_blocked_run_does_not_count(drive, capsys, tmp_path):
    why = f"{rr.SO_QUESTION_ROOT_MISSING}：「讓交付自動要第二意見」（整句照抄進 question 再重跑）"
    drive.tx.opinion("", start_status="blocked", reason=why)
    reason, _, _ = drive(FOUR, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" in reason and "照 reason 把那句抄進 question 重跑" in reason


def test_material_without_goal_tree_does_not_count(drive, capsys, tmp_path, monkeypatch):
    """session 有需求目標樹，但那次 start 的材料沒帶到（note 以 SO_NO_GOAL_NOTE 開頭）→ 不算跑過；材料帶到樹（沒有那條 note）→ 放行。"""
    monkeypatch.setattr(so, "has_goal_tree", lambda sid: True)
    drive.tx.opinion("done", notes=[f"{rr.SO_NO_GOAL_NOTE}：沒帶 session_id，找不到這個 session 的樹"])
    reason, _, _ = drive(FOUR, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" in reason and "材料沒有需求目標樹" in reason
    drive.tx.opinion("done", job="20261020-120500-sidg9xxx-stage-review")
    reason, state, _ = drive(FOUR, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" not in reason and state["second_opinion_ok"][SID] == 5


def test_decline_quoted_in_prose_does_not_bypass(drive, capsys, tmp_path):
    """散文裡引用的範例（不在行首）、程式碼區塊裡的宣告行都不算 AI 宣告不需。"""
    text = "說明：AI 可以寫 `不需第二意見｜只重錄 cassettes` 來免跑。\n```\n不需第二意見｜只重錄 cassettes\n```\n全部完成。"
    reason, _, logs = drive(text, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" in reason and "SECOND_OPINION_REQUIRED" in reason and not _so_logs(logs, "declined")


def test_check_error_does_not_block_but_logs(drive, capsys, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("壞了")
    monkeypatch.setattr(st, "_so_facts", boom)
    reason, _, logs = drive(DONE, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" not in reason and [p["event"] for p in _so_logs(logs)] == ["error"]


def test_exhausted_asks_user_then_release(drive, capsys, tmp_path):
    files = _files(tmp_path, 5)
    _, state, _ = drive(DONE, capsys, files=files)
    reason, state, logs = drive(DONE, capsys, state=state)
    assert RELEASE_TAG in reason and "原擋訊息" in reason and state["pending_release"][SID]["second_opinion"]
    assert [p["event"] for p in _so_logs(logs)] == ["exhausted_block"]
    q = f"{RELEASE_TAG} 第二意見要放行嗎？"
    drive.tx.call("AskUserQuestion", {"questions": [{"question": q, "options": []}]}, f'"{q}"="{OPT_RELEASE}"',
                  extra={"toolUseResult": {"answers": {q: OPT_RELEASE}}})
    reason, state, logs = drive(DONE, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason and [p["event"] for p in _so_logs(logs)] == ["user_release"]
    assert state["second_opinion_ok"][SID] == 5 and "second_opinion" not in state["pending_release"][SID]


def test_satisfied_then_next_turn_without_edits_not_required(drive, capsys, tmp_path):
    files = _files(tmp_path, 5)
    drive.tx.opinion("done")
    _, state, _ = drive(FOUR, capsys, files=files)
    assert state["second_opinion_ok"][SID] == 5
    drive.tx.user("下一題：說明一下")
    state.update(turn_seq=6, turn_prompts_seq=6)
    reason, _, logs = drive(DONE, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs)
    state["modified_files"][0]["last_turn_seq"] = 6
    reason, _, _ = drive(DONE, capsys, state=state)
    assert "[Guardian:SecondOpinion]" in reason, "上次滿足之後又改了程式 → 再要求（本回合窗口裡沒有新的 run）"


def test_earlier_gate_block_previews_second_opinion(drive, capsys, tmp_path):
    state = {"phase": "working", "modified_files": [_mf(p) for p in _files(tmp_path, 5)], "stop_blocked_count": 0,
             "failing_tests": [{"cmd": "pytest a", "summary": "1 failed", "session_id": SID, "turn_seq": 5}],
             "recent_user_prompts": [], "turn_seq": 5, "turn_prompts_seq": 5, "muted": True}
    reason, _, _ = drive(DONE, capsys, state=state)
    assert "[Guardian:TestFailGate]" in reason and "[Guardian:AlsoOwed]" in reason and "第二意見：" in reason


# ─── 事實與純判定 ─────────────────────────────────────────────────────────

def test_turn_events_only_current_turn(tmp_path):
    tx = Tx(tmp_path / "t.jsonl")
    tx.user("上一題")
    tx.opinion("done", job="20261020-110000-aaaaaaaa-stage-review")
    tx.user("這一題")
    tx.opinion("running")
    starts, results = so.turn_events(tx.path.read_text(encoding="utf-8"))
    assert [s["job_id"] for s in starts] == [JOB] and [r["status"] for r in results] == ["running"]
    assert rr.second_opinion_runs(starts, results) == [(JOB, "running")]


def test_runs_status_mapping():
    starts = [{"mode": "independent", "kind": "stage-review", "job_id": "j1", "status": "started"},
              {"mode": "review", "kind": "stage-review", "job_id": "j2", "status": "started"},
              {"mode": "independent", "kind": "evaluate", "job_id": "-", "status": "failed", "reason": "models_cache 沒有"},
              {"mode": "independent", "kind": "evaluate", "job_id": "-", "status": "", "reason": ""},
              {"mode": "independent", "kind": "diagnose", "job_id": "j5", "status": "started"},
              {"mode": "independent", "kind": "evaluate", "job_id": "j6", "status": "blocked"},
              {"mode": "independent", "kind": "evaluate", "job_id": "j7", "status": "started",
               "notes": [f"{rr.SO_NO_GOAL_NOTE}：沒帶 session_id"]}]
    results = [{"job_id": "j1", "status": "running"}, {"job_id": "j1", "status": "blocked", "reason": "replay-guard pre FAIL"},
               {"job_id": "j7", "status": "done"}]
    assert rr.second_opinion_runs(starts, results, has_tree=True) == [
        ("j1", "blocked"), ("j2", "off-mode"), ("-", "invalid"), ("-", "invalid"), ("j5", "off-mode"), ("j6", "started"),
        ("j7", "no-goal")], "只認 result 回的狀態：沒開出 job 的 failed、start 自己回的 blocked 都不算跑過"
    assert rr.second_opinion_runs(starts[-1:], results, has_tree=False) == [("j7", "done")], "session 沒有樹 → 不要求材料帶樹"


def test_changed_lines_counts_untracked_new_file(tmp_path):
    root = _repo(tmp_path, {"src/a.py": _lines(10)})
    (root / "src" / "a.py").write_text(_lines(10) + _lines(5, "y"), encoding="utf-8", newline="\n")
    (root / "src" / "new.py").write_text(_lines(200, "z"), encoding="utf-8", newline="\n")
    assert so.changed_lines([str(root / "src" / "a.py"), str(root / "src" / "new.py")]) == 5 + 201
    assert so.changed_lines([str(tmp_path / "nogit" / "x.py")]) is None, "不在 git 根 → 只看檔數"


def test_gate_kind_in_part_table_is_risky(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
        "| `src/gate/` | 閘本體 | 無 | 部分 | gate |\n| `src/` | 一般 | 無 | 部分 | code |\n", encoding="utf-8")
    gate, plain = str(proj / "src" / "gate" / "x.py"), str(proj / "src" / "y.py")
    assert so.risky_paths([gate, plain], []) == [gate]


def test_triggers_and_decline_units():
    assert rr.second_opinion_triggers(3, None, [], 4, 150) == []
    assert rr.second_opinion_triggers(4, None, [], 4, 150) == ["程式檔 4 個 ≥ 4"]
    assert rr.second_opinion_triggers(1, 150, [], 4, 150) == ["對 HEAD 的程式改動 150 行 ≥ 150"]
    assert rr.second_opinion_decline("前文\n不需第二意見｜只改訊息字串\n") == "只改訊息字串"
    assert rr.second_opinion_decline("沒有宣告") is None
    assert rr.second_opinion_decline_ok("只重錄 cassettes") and not rr.second_opinion_decline_ok("不需要")
    assert rr.second_opinion_decline("- **不需第二意見**｜只改訊息字串") == "只改訊息字串"
    assert rr.second_opinion_decline("可以寫 `不需第二意見｜只改訊息字串` 免跑") is None, "散文裡引用不算"
    assert rr.second_opinion_decline("> 不需第二意見｜只改訊息字串") is None, "引用區塊不算"
    assert rr.second_opinion_decline("```\n不需第二意見｜只改訊息字串\n```") is None, "程式碼區塊不算"
    assert rr.second_opinion_section_missing(FOUR) == []
    assert rr.second_opinion_section_missing("Codex 結論：\n") == [
        "段標題「第二意見與分歧裁決」", "「Codex 結論：」行", "「我方結論：」行", "「分歧點：」行", "「裁決與理由：」行"]
    assert len(rr.second_opinion_section_missing(f"```\n{FOUR}\n```")) == 5, "整段放在程式碼區塊（範本）不算"


# ─── 材料：goal.md 與 question 樹根 ──────────────────────────────────────────

@pytest.fixture()
def so_run(tmp_path, monkeypatch):
    monkeypatch.setenv("WG_CLAUDE_DIR", str(tmp_path / "data-root"))
    run = _load("g9_so_run", CODE_DIR / "tools" / "second-opinion" / "run.py")
    monkeypatch.setattr(ng, "goal_dir", lambda: tmp_path / "need-goal")
    monkeypatch.setattr(run, "resolve_model", lambda cfg: ("gpt-test", ""))
    monkeypatch.setattr(run, "run_guard", lambda args, timeout_s=60: ("PASS", [], "REPLAY_GUARD_CHECK PASS\n"))
    return run


ROOT_GOAL = r"讓 C:\Users\x\proj 的大任務交付自動要第二意見"


def test_pack_goal_md_in_manifest_and_hash(so_run, tmp_path):
    pack = so_run.pack
    assert ng.apply_op(SID, 1, {"action": "set", "goal": ROOT_GOAL})["ok"]
    req = {"cwd": "", "part": "", "mode": "independent", "materials": {"diff": {"text": "d\n"}}}
    with_tree, notes = pack.gather_items({**req, "session_id": SID}, {})
    no_tree, notes2 = pack.gather_items({**req, "session_id": "nobody"}, {})
    goal = dict(with_tree)["goal.md"]
    assert goal.startswith("樹根（T1）：讓 …/proj 的大任務交付自動要第二意見") and "C:\\Users" not in goal
    assert "【使用者原話（權威）】" in goal and dict(no_tree)["goal.md"] == "無目標樹\n"
    assert any(n.startswith(rr.SO_NO_GOAL_NOTE) for n in notes2) and not any("目標樹" in n for n in notes)
    m1 = pack.pack_materials(tmp_path / "a", with_tree, "independent", "m")
    m2 = pack.pack_materials(tmp_path / "b", no_tree, "independent", "m")
    assert "goal.md" in [f["rel"] for f in m1["files"]] and "goal.md" in [f["rel"] for f in m2["files"]]
    assert m1["hash"] != m2["hash"]


def test_prepare_blocks_question_without_root(so_run, tmp_path):
    assert ng.apply_op(SID, 1, {"action": "set", "goal": ROOT_GOAL})["ok"]
    so_cfg, _ = so_run.load_config()
    req = {"kind": "stage-review", "part": "p", "cwd": str(tmp_path), "mode": "independent", "session_id": SID,
           "question": "這樣改對嗎？", "materials": {"diff": {"text": "d\n"}}}
    res = so_run.prepare(req, so_cfg, tmp_path / "jobs")
    assert res["status"] == "blocked" and rr.SO_QUESTION_ROOT_MISSING in res["reason"]
    assert "讓 …/proj 的大任務交付自動要第二意見" in res["reason"]
    ok = so_run.prepare({**req, "question": "目標：讓 …/proj 的大任務交付自動要第二意見。這樣改對嗎？"}, so_cfg, tmp_path / "jobs")
    assert ok["status"] == "started", ok
    prompt = (Path(ok["job_dir"]) / "prompt.md").read_text(encoding="utf-8")
    assert "materials/goal.md" in prompt and "C:\\Users\\x" not in prompt
    free = so_run.prepare({**req, "session_id": "nobody"}, so_cfg, tmp_path / "jobs")
    assert free["status"] == "started", "沒有樹時 question 免核對"


# ─── 入口與對帳 ─────────────────────────────────────────────────────────

def test_pre_tool_use_adds_session_id(capsys):
    inp = {"kind": "stage-review", "mode": "independent", "question": "q"}
    with pytest.raises(SystemExit):
        pt.handle_pre_tool_use({"tool_name": START, "tool_input": inp, "session_id": SID}, {})
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["updatedInput"] == {**inp, "session_id": SID}
    with pytest.raises(SystemExit):
        pt.handle_pre_tool_use({"tool_name": START, "tool_input": {**inp, "session_id": SID}, "session_id": SID}, {})
    assert capsys.readouterr().out == "", "已經是自己的 session_id 就不改"


def test_health_weekly_lists_declined(tmp_path, monkeypatch):
    hw = _load("g9_health_weekly", CODE_DIR / "tools" / "health-weekly.py")
    monkeypatch.setattr(hw, "CLAUDE_DIR", tmp_path)
    (tmp_path / "Logs").mkdir()
    now = hw.datetime.now().astimezone()
    rows = [{"at": now.isoformat(), "event": "declined", "reason": "只重錄 cassettes", "code_files": 5},
            {"at": now.isoformat(), "event": "block", "reason": "x"},
            {"at": (now - hw.timedelta(days=30)).isoformat(), "event": "declined", "reason": "太舊"}]
    (tmp_path / "Logs" / "guard-second_opinion.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    got = hw._second_opinion_declined_block(14)
    assert len(got) == 1 and "1 筆" in got[0] and "只重錄 cassettes" in got[0] and "太舊" not in got[0]
    assert hw._second_opinion_declined_block(14) and not hw._user_release_block(14)
