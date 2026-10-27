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


SID = "sidg9xxx-g9"                  # 前 8 碼（去掉非英數）＝JOB 裡的 session 段，同 run.py 組 job_id
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


RISKY = {"second_opinion": {"auto": {"risky_prefixes": ["hooks/wg_release_rules.py", "hooks/wg_second_opinion.py"]}}}


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
    own = reason.split("\n判準卡")[0]          # 切入點契約：判準卡接在擋訊息後面，入口在閘自己訊息的最末
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


def test_partial_done_then_final_in_progress_still_owed(drive, capsys, tmp_path):
    """規則 SECOND_OPINION_FACT_TRIGGER：最後一則說「整體仍進行中，等待測試結果」也是收尾（不是問使用者）——改了 5 支程式就欠，
    不看說法（舊判法照狀態詞算沒宣告完成、不判）。"""
    drive.tx.say("第一階段完成：資料表搬好了。")
    reason, _state, logs = drive("整體仍進行中，等待測試結果回來再整理。", capsys, files=_files(tmp_path, 5))
    assert "SECOND_OPINION_REQUIRED" in reason and [p["event"] for p in _so_logs(logs)] == ["block"]


def test_done_then_patch_mentioning_solution_still_blocks(drive, capsys, tmp_path):
    """Codex：說「全部做完了」→ 別的閘擋 → 補件只寫「拐彎判斷｜檢查解決方案的依賴｜合理」；「解決方案」不是完成與否的話，前面的宣告照算。"""
    drive.tx.say("全部做完了，測試都過。")
    drive.tx.add({"type": "user", "isMeta": True, "message": {"role": "user", "content": STOP_FEEDBACK}})
    reason, _state, logs = drive("拐彎判斷｜檢查解決方案的依賴｜不會：兩個彎｜各管一件事｜合理", capsys, files=_files(tmp_path, 5))
    assert "SECOND_OPINION_REQUIRED" in reason and [p["event"] for p in _so_logs(logs)] == ["block"]


def test_done_with_negated_first_sentence_then_patch_reply_still_blocks(drive, capsys, tmp_path):
    """規則 COMPLETION_CLAIM_PER_SENTENCE（codex 一輪 BLOCK 2）：宣告完成那則開頭寫「我還沒動git：完成的三件…」，下一句「全部做完了」；
    別的閘擋下、補件只寫拐彎判斷 → 往前看時那則照算宣告完成（舊判法整則套否定詞就清掉，第二意見漏擋）。"""
    drive.tx.say("我還沒動git：完成的三件列在下面。\n全部做完了，等你看 diff。")
    drive.tx.add({"type": "user", "isMeta": True, "message": {"role": "user", "content": STOP_FEEDBACK}})
    reason, _state, logs = drive(C2_PATCH, capsys, files=_files(tmp_path, 5))
    assert "SECOND_OPINION_REQUIRED" in reason and [p["event"] for p in _so_logs(logs)] == ["block"]


def test_done_then_later_not_done_reply_still_owed(drive, capsys, tmp_path):
    """SECOND_OPINION_FACT_TRIGGER：最後談到「還沒做完」也是收尾，改了 5 支程式照欠（舊判法照否定詞不判）。"""
    drive.tx.say(C2_DONE)
    reason, _state, logs = drive("還沒做完：ERP 合約測試照你說的留紅，另有 8 個檔等你說 commit。", capsys,
                                 files=_files(tmp_path, 5))
    assert "SECOND_OPINION_REQUIRED" in reason and [p["event"] for p in _so_logs(logs)] == ["block"]


def test_block_message_says_any_reply_this_turn_counts(drive, capsys, tmp_path):
    """擋訊息講明四行寫在本回合任一則回覆都算，補件那則不必重抄（SECOND_OPINION_REQUIRED）。"""
    reason, _state, _logs = drive(DONE, capsys, files=_files(tmp_path, 5))
    assert "本回合任一則回覆都算" in reason and "不必重抄" in reason
    assert reason.split("\n判準卡")[0].rstrip().endswith(HINT_TAIL)                 # 入口仍在閘自己訊息的最末


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
    reason, _, _ = drive(DONE, capsys, files=[root / rel], config=RISKY)
    assert "[Guardian:SecondOpinion]" in reason and f"改到高風險部位：{rel.rsplit('/', 1)[-1]}" in reason
    assert "[Guardian:SecondOpinion]" not in drive(DONE, capsys, files=[root / rel])[0], "risky_prefixes 預設空：沒設就不算高風險"


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


def test_once_per_claim_adopting_opinion_edits_not_owed_again(drive, capsys, tmp_path):
    """規則 SECOND_OPINION_ONCE_PER_CLAIM：審過之後為採納意見再改（改的是審過的檔、也沒過門檻）→ 不再欠第二次
    （舊碼：上次滿足之後又改了程式就再要一輪，採納 → 再改 → 再欠，連鎖不停 → 紅）。"""
    files = _files(tmp_path, 5)
    drive.tx.opinion("done")
    _, state, _ = drive(FOUR, capsys, files=files)
    assert state["second_opinion_ok"][SID] == 5
    drive.tx.user("照 codex 的意見改一行")
    state.update(turn_seq=6, turn_prompts_seq=6)
    state["modified_files"][0]["last_turn_seq"] = 6                     # 採納意見改了審過的其中一檔
    reason, _, _ = drive(DONE, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason


def test_once_per_claim_new_risky_part_or_new_files_over_threshold_owed(drive, capsys, tmp_path):
    """審過之後改到新的高風險檔 → 才再欠；再改審過的那個高風險檔不欠；之後新改的程式檔數再過門檻也再欠。"""
    root = _repo(tmp_path, {"hooks/wg_release_rules.py": _lines(3), "hooks/wg_second_opinion.py": _lines(3)})
    rr_file, so_file = root / "hooks/wg_release_rules.py", root / "hooks/wg_second_opinion.py"
    drive.tx.opinion("done")
    _, state, _ = drive(FOUR, capsys, files=[rr_file], config=RISKY)
    assert state["second_opinion_cover"][SID]["risky"]
    drive.tx.user("採納：再改 wg_release_rules")
    state.update(turn_seq=6, turn_prompts_seq=6)
    state["modified_files"][0]["last_turn_seq"] = 6
    assert "[Guardian:SecondOpinion]" not in drive(DONE, capsys, state=state, config=RISKY)[0]   # 審過的高風險檔：不欠
    drive.tx.user("另外改 wg_second_opinion")
    state.update(turn_seq=7, turn_prompts_seq=7)
    state["modified_files"].append(_mf(so_file, 7))
    assert "[Guardian:SecondOpinion]" in drive(DONE, capsys, state=state, config=RISKY)[0]       # 新的高風險檔：再欠
    files = _files(tmp_path, 5)
    drive.tx.opinion("done")
    _, st2, _ = drive(FOUR, capsys, files=files)
    drive.tx.user("又做一大批")
    st2.update(turn_seq=6, turn_prompts_seq=6)
    st2["modified_files"] += [_mf(p, 6) for p in _files(tmp_path, 4, sub="proj/other")]
    assert "[Guardian:SecondOpinion]" in drive(DONE, capsys, state=st2)[0]         # 之後新改的檔數再過門檻：再欠


def test_earlier_gate_block_previews_second_opinion(drive, capsys, tmp_path):
    state = {"phase": "working", "modified_files": [_mf(p) for p in _files(tmp_path, 5)], "stop_blocked_count": 0,
             "failing_tests": [{"cmd": "pytest a", "summary": "1 failed", "session_id": SID, "turn_seq": 5}],
             "recent_user_prompts": [], "turn_seq": 5, "turn_prompts_seq": 5, "muted": True}
    reason, _, _ = drive(DONE, capsys, state=state)
    assert "[Guardian:TestFailGate]" in reason and "[Guardian:AlsoOwed]" in reason and "第二意見：" in reason


# ─── 等結果、跨回合取結果、宣告收下（補題第二版第 4、5 回合）────────────────

WAIT_TEXT = f"第二意見還在跑，背景等它跑完，我會回來取結果、寫裁決。\n等第二意見｜{JOB}"
TASK_DONE = ("<task-notification>\n<task-id>b1</task-id>\n<status>completed</status>\n"
             "<summary>Background command completed (exit code 0)</summary>\n</task-notification>")


def _feedback(drive, reason):
    drive.tx.add({"type": "user", "isMeta": True, "message": {"role": "user", "content": "Stop hook feedback:\n" + reason}})


def _result(drive, status="done", job=JOB, mode="independent", notes=()):
    drive.tx.call(RESULT, {"job_id": job}, f"status: {status}\njob_id: {job}\nhash: h\nmodel: m\nmode: {mode}"
                  + "".join(f"\nnote: {n}" for n in notes) + "\n\n## 結論\n照判定")


def test_wait_in_flight_end_reply_naming_job_blocks_once(drive, capsys, tmp_path):
    """規則 SECOND_OPINION_WAITING_NOT_DONE（補題第二版第 4 回合）：宣告完成 → 擋 → start → 背景等 → 結束回覆寫明在等的 job。
    舊碼把這次結束回覆當宣告完成、照 start 了沒取結果再擋（同一回合第 2 次 → 斷路器警報）；改後只擋 1 次，等待那次留帳 waiting，
    背景通知回來取到 done、寫四行 → 放行。"""
    reason, state, logs = drive(DONE, capsys, files=_files(tmp_path, 5))
    assert "SECOND_OPINION_REQUIRED" in reason
    _feedback(drive, reason)
    drive.tx.opinion(status="")
    drive.tx.call("Bash", {"command": "until grep -q done status.json; do sleep 2; done", "run_in_background": True},
                  "Command running in background with ID: b1.")
    reason2, state, logs2 = drive(WAIT_TEXT, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason2, reason2
    assert [p["event"] for p in _so_logs(logs2)] == ["waiting"] and _so_logs(logs2)[0]["job"] == JOB
    assert SID not in (state.get("second_opinion_ok") or {}), "等待中不算滿足（不 mark_ok）"
    drive.tx.add({"type": "user", "message": {"role": "user", "content": TASK_DONE}})
    _result(drive, "done")
    reason3, state, logs3 = drive(FOUR, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason3 and state["second_opinion_ok"][SID] == 5
    assert [p["event"] for p in _so_logs(logs + logs2 + logs3)].count("block") == 1


def test_wait_in_flight_end_reply_without_job_id_still_blocks(drive, capsys, tmp_path):
    """收尾沒寫在等哪個 job（只說還在跑）→ 照擋，擋訊息教「直接呼叫 result 會等」與「收尾寫明 job_id」（start 完就宣告完成不能靠這條繞過）。"""
    drive.tx.opinion(status="")
    reason, _state, logs = drive("第二意見還在跑，全部完成後再說。", capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" in reason and "還沒取結果" in reason
    assert "直接呼叫 second_opinion_result" in reason and "等第二意見｜<job_id>" in reason
    assert [p["event"] for p in _so_logs(logs)] == ["block"]


def test_block_message_says_result_waits(drive, capsys, tmp_path):
    """開關 second_opinion.auto.background 關（舊送法）：第一次擋訊息寫明 start 後直接呼叫 result、它會等到有結果，不用另開背景等待
    （補題第二版第 4 回合 AI 照一般做法背景等）。開關開的寫法見 verify_closing_round.py。"""
    reason, _state, _logs = drive(DONE, capsys, files=_files(tmp_path, 5),
                                  config={"second_opinion": {"auto": {"background": False}}})
    assert "直接呼叫 second_opinion_result" in reason and "會等到有結果" in reason and "不用另開背景等待" in reason
    assert reason.split("\n判準卡")[0].rstrip().endswith(HINT_TAIL)


def test_result_across_turns_done_no_edits_passes(drive, capsys, tmp_path):
    """規則 SECOND_OPINION_RESULT_ACROSS_TURNS（補題第二版第 5 回合）：上一回合 start、這一回合 result 回 done、之後沒改程式、
    收尾有四行 → 不擋並記基準。舊碼只認本回合的 start，跨回合取回的 done 兩邊都不認，照擋「本回合沒有跑第二意見」。"""
    reason, state, _ = drive(DONE, capsys, files=_files(tmp_path, 5))
    _feedback(drive, reason)
    drive.tx.opinion(status="")
    drive.tx.user("照你的判斷做")
    state.update(turn_seq=6, turn_prompts_seq=6)
    _result(drive, "done")
    reason, state, logs = drive(FOUR, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason, reason
    assert state["second_opinion_ok"][SID] == 6 and state["second_opinion_ran"][SID]["job"] == JOB
    drive.tx.user("下一題：說明一下")
    state.update(turn_seq=7, turn_prompts_seq=7)
    reason, _, logs = drive(DONE, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs)


def test_result_across_turns_job_older_than_last_edit_not_counted(drive, capsys, tmp_path):
    """start 在前面回合的 job，開 job（job_id 開頭 2026-10-20 12:00:00）之後又改過程式 → 沒審到後來的改動，不算跑過（stale）；
    最後一次改程式在開 job 之前 → 照算。"""
    drive.tx.user("照你的判斷做")
    _result(drive, "done")
    files = _files(tmp_path, 5)
    state = {"phase": "working", "modified_files": [{**_mf(p), "last_at": "2026-10-22T09:00:00+00:00"} for p in files],
             "failing_tests": [], "recent_user_prompts": [], "stop_blocked_count": 0, "turn_seq": 5, "turn_prompts_seq": 5,
             "muted": True}
    reason, _, _ = drive(FOUR, capsys, state=state)
    assert "SECOND_OPINION_REQUIRED" in reason and "沒審到後來的改動" in reason
    for m in state["modified_files"]:
        m["last_at"] = "2026-10-19T09:00:00+00:00"
    state.pop("second_opinion_gate_turn", None)
    reason, state, _ = drive(FOUR, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason and state["second_opinion_ok"][SID] == 5


def test_result_across_turns_other_session_job_not_counted(drive, capsys, tmp_path):
    """job 目錄是同一個資料根共用的：別的 session 開的 job（job_id 裡的 session 段不是本 session），這一回合拿來取結果不算跑過（foreign）。"""
    other = "20261020-120000-aaaaaaaa-stage-review"
    drive.tx.user("照你的判斷做")
    _result(drive, "done", job=other)
    reason, _, _ = drive(FOUR, capsys, files=_files(tmp_path, 5))
    assert "SECOND_OPINION_REQUIRED" in reason and "不是這個 session 開的" in reason


def test_result_across_turns_still_needs_four_lines(drive, capsys, tmp_path):
    """跨回合取回 done 算本回合跑過：四行照要（結果是這一回合才拿到的，裁決寫在這一回合）。"""
    drive.tx.opinion(status="")
    drive.tx.user("照你的判斷做")
    _result(drive, "done")
    reason, _, _ = drive(DONE, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" in reason and "跑過第二意見，但收尾缺" in reason


@pytest.mark.parametrize("mode,notes,status", [("review", (), "done"), ("independent", (f"{rr.SO_NO_GOAL_NOTE}：沒帶 session_id",), "done"),
                                               ("", (), "failed")])
def test_result_across_turns_off_mode_no_goal_or_missing_job_not_counted(drive, capsys, tmp_path, monkeypatch,
                                                                         mode, notes, status):
    """start 不在本回合時照 result 自己帶的 mode、note 判：mode=review、session 有樹而材料沒帶到樹、找不到 job（沒有 mode 行）都不算跑過。"""
    monkeypatch.setattr(so, "has_goal_tree", lambda sid: True)
    drive.tx.user("照你的判斷做")
    if mode:
        _result(drive, status, mode=mode, notes=notes)
    else:
        drive.tx.call(RESULT, {"job_id": JOB}, f"status: failed\nreason: 找不到 job（{JOB}）")
    reason, _, _ = drive(FOUR, capsys, files=_files(tmp_path, 5))
    assert "SECOND_OPINION_REQUIRED" in reason and "跑過第二意見" not in reason


def test_refetch_reviewed_job_next_turn_not_owed_again(drive, capsys, tmp_path):
    """上一回合跑完並滿足的 job，這一回合再呼叫一次 result 重讀 → 仍是前面回合的基準（SECOND_OPINION_RAN_BEFORE），沒改程式就不再要四行。"""
    drive.tx.opinion("done")
    _, state, _ = drive(FOUR, capsys, files=_files(tmp_path, 5))
    drive.tx.user("再看一次結論")
    state.update(turn_seq=6, turn_prompts_seq=6)
    _result(drive, "done")
    reason, _, _ = drive(DONE, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason


DECLINE_LINE = "不需第二意見｜這份第二意見是在最後一次改程式之後才送出的，之後沒有再改任何程式檔"


def test_decline_accepted_not_blocked_even_if_earlier_reply_has_four_lines(drive, capsys, tmp_path):
    """規則 SECOND_OPINION_DECLINE_ACCEPTED（補題第二版第 5 回合帳：同一秒記 declined 又記 exhausted_block）：本回合較早那則有四行、
    被擋後收尾只寫「不需第二意見｜理由」→ 宣告被收下就不擋。舊碼判宣告行時拿的是較早那則四行齊的回覆（section_text），收尾那句
    宣告行看不到，照擋滿那條路再擋。"""
    reason, state, _ = drive(FOUR, capsys, files=_files(tmp_path, 5))
    assert "SECOND_OPINION_REQUIRED" in reason
    _feedback(drive, reason)
    reason, state, logs = drive(DECLINE_LINE, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason, reason
    assert [p["event"] for p in _so_logs(logs)] == ["declined"] and _so_logs(logs)[0]["needed"] is True
    assert state["second_opinion_ok"][SID] == 5


# ─── 事實與純判定 ─────────────────────────────────────────────────────────

def test_runs_result_only_jobs_across_turns():
    """SECOND_OPINION_RESULT_ACROSS_TURNS：本回合只有 result、沒有 start 的 job，照 result 的 mode、job_id 的類別、note 判。"""
    results = [{"job_id": "20261020-120000-aaaaaaaa-stage-review", "status": "running", "mode": "independent"},
               {"job_id": "20261020-120000-aaaaaaaa-stage-review", "status": "done", "mode": "independent"},
               {"job_id": "20261020-120000-bbbbbbbb-diagnose", "status": "done", "mode": "independent"},
               {"job_id": "20261020-120000-cccccccc-evaluate", "status": "failed", "mode": "", "reason": "找不到 job"},
               {"job_id": "20261020-120000-dddddddd-evaluate", "status": "done", "mode": "independent",
                "notes": [f"{rr.SO_NO_GOAL_NOTE}：沒帶 session_id"]},
               {"job_id": "20261020-120000-eeeeeeee-evaluate", "status": "running", "mode": "independent"}]
    assert rr.second_opinion_runs([], results, has_tree=True) == [
        ("20261020-120000-aaaaaaaa-stage-review", "done"), ("20261020-120000-bbbbbbbb-diagnose", "off-mode"),
        ("20261020-120000-dddddddd-evaluate", "no-goal"), ("20261020-120000-eeeeeeee-evaluate", "running")], \
        "找不到 job（沒有 mode 行）不列"


def test_verdict_waiting_and_decline_read_closing_text():
    """宣告行與「在等哪個 job」都看收尾最後一則（closing），四行可以在較早那則（text）。"""
    trig = ["程式檔 5 個 ≥ 4"]
    v = rr.second_opinion_verdict(True, trig, True, [(JOB, "running")], FOUR, closing=WAIT_TEXT)
    assert v.rule == "SECOND_OPINION_WAITING_NOT_DONE" and not v.owed
    v = rr.second_opinion_verdict(True, trig, True, [(JOB, "started")], FOUR, closing="還在跑。")
    assert v.owed and "等第二意見｜<job_id>" in v.why
    for prose in (f"全部完成，job_id：{JOB}", f"等第二意見｜{JOB}-other", f"```\n等第二意見｜{JOB}\n```"):
        v = rr.second_opinion_verdict(True, trig, True, [(JOB, "started")], FOUR, closing=prose)
        assert v.owed, f"散文裡提到 job_id、job_id 後面多接字、程式碼區塊裡的宣告行都不算：{prose!r}"
    v = rr.second_opinion_verdict(True, trig, True, [], FOUR, closing=DECLINE_LINE)
    assert v.rule == "SECOND_OPINION_DECLINED" and not v.owed


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


# ─── 005 件 4：「不需第二意見」每次宣告都留帳（規則 SECOND_OPINION_DECLARED_ALWAYS_LOGGED） ───

def test_005_decline_logged_when_gate_does_not_need_it(drive, capsys, tmp_path):
    """第四跑 C-1 第 3、4 回合：沒改程式、沒宣告完成，AI 照樣寫「不需第二意見｜…」→ 閘這回合不要，宣告也記一筆（needed=False）；
    舊碼只在閘要第二意見而且宣告成立那條路記，第 2～5 回合的宣告全沒帳。"""
    text = "不需第二意見｜這一輪沒有改任何程式，只是核對已經提交的內容"
    reason, state, logs = drive(text, capsys, files=_files(tmp_path, 5))
    declined = _so_logs(logs, "declined")
    assert "[Guardian:SecondOpinion]" not in reason and "second_opinion_ok" not in state, "前置：閘這回合沒要第二意見"
    assert len(declined) == 1 and declined[0]["needed"] is False and declined[0]["reason"].startswith("這一輪沒有改任何程式")


def test_005_decline_logged_even_when_an_earlier_gate_blocks(drive, capsys, tmp_path):
    """前面的閘（這裡用紅測閘）先擋下、收尾沒走到第二意見段，宣告照樣記，needed 記閘當下要不要（要：5 個程式檔、宣告完成）。"""
    red = {"cmd": "python -m pytest verify_a.py", "summary": "FAILED verify_a.py::test_x", "turn_seq": 5, "session_id": SID,
           "pytest": True}
    state = {"phase": "working", "modified_files": [_mf(p) for p in _files(tmp_path, 5)], "failing_tests": [red],
             "recent_user_prompts": [], "stop_blocked_count": 0, "turn_seq": 5, "turn_prompts_seq": 5, "muted": True}
    reason, _, logs = drive("全部完成。\n不需第二意見｜只重錄 cassettes", capsys, state=state)
    assert "[Guardian:TestFailGate]" in reason, "前置：紅測閘先擋"
    declined = _so_logs(logs, "declined")
    assert len(declined) == 1 and declined[0]["needed"] is True and declined[0]["code_files"] == 5


def test_005_same_decline_in_same_turn_logged_once(drive, capsys, tmp_path):
    """被擋後重寫同一句不重記；同一回合換一句理由再記一筆。"""
    state = {"phase": "working", "modified_files": [], "failing_tests": [], "recent_user_prompts": [], "stop_blocked_count": 0,
             "turn_seq": 5, "turn_prompts_seq": 5, "muted": True}
    text = "不需第二意見｜這一輪沒有改任何程式，只做搜尋和實測確認。"
    _, _, first = drive(text, capsys, state=state)
    _, _, again = drive(text, capsys, state=state)
    _, _, other = drive("不需第二意見｜只查狀態和整理回報", capsys, state=state)
    _, _, back = drive(text, capsys, state=state)
    assert len(_so_logs(first, "declined")) == 1 and not _so_logs(again, "declined") and len(_so_logs(other, "declined")) == 1
    assert not _so_logs(back, "declined"), "codex 005：A、B、A 第三次不重記（不是只記最後一句）"
    long_a, long_b = "只重錄 cassettes" + "，" * 200 + "甲", "只重錄 cassettes" + "，" * 200 + "乙"
    _, _, la = drive(f"不需第二意見｜{long_a}", capsys, state=state)
    _, _, lb = drive(f"不需第二意見｜{long_b}", capsys, state=state)
    assert len(_so_logs(la, "declined")) == 1 and len(_so_logs(lb, "declined")) == 1, "前 200 字相同、後面不同是兩句"


# ─── UNKNOWN_WRITE_RECOVERED：判不出目標的 Bash 寫入補進 modified_files 後，第二意見照數程式檔 ─────────────────

def test_unknown_write_recovered_files_count_for_second_opinion(drive, capsys, tmp_path, monkeypatch):
    """AI 只用 heredoc 餵給 python 改 3 支程式、新增 1 支程式與 1 支測試（寫入目標判不出），真的 PostToolUse 從 git status 補進
    modified_files → 宣告完成、本回合沒跑第二意見 → 照擋「程式檔 5 個」。舊碼：modified_files 空，第二意見不數（紅）。"""
    from verify_unknown_write_recover import NOTIFY, bash_unknown_write, heredoc, init_repo
    repo = init_repo(tmp_path / "qs3-notify", NOTIFY)
    code = ("def edit(p, old, new):\n"
            "    s = open(p, encoding='utf-8').read()\n"
            "    open(p, 'w', encoding='utf-8').write(s.replace(old, new))\n"
            "edit('notify/sender.py', 'MAX_RETRIES = 3', 'MAX_RETRIES = 6')\n"
            "edit('notify/format.py', 'text.strip()', 'text.strip().upper()')\n"
            "edit('notify/__init__.py', '', 'VERSION = 2\\n')\n"
            "for p in ('notify/log.py', 'tests/test_sender.py'):\n"
            "    open(p, 'w').write('x = 1\\n')\n")
    state = {"phase": "working", "modified_files": [], "failing_tests": [], "recent_user_prompts": [], "stop_blocked_count": 0,
             "turn_seq": 5, "turn_prompts_seq": 5, "muted": True, "session": {"cwd": str(repo)}}
    bash_unknown_write(monkeypatch, repo, state, f"cd {repo.as_posix()} && " + heredoc(code), code, sid=SID)
    reason, _, logs = drive(DONE, capsys, state=state)
    assert "[Guardian:SecondOpinion]" in reason and "程式檔 5 個" in reason, reason
    assert all(m["via"] == "vcs_status" for m in state["modified_files"])


# ─── 看事實觸發、出口指紋（減量三輪 A；改動前的 main f45be4ea 回放：標「紅」的那幾段在舊碼不成立）─────────────────

S1_DONE = ("兩件都改好了，測試也補了，全部 4 支測試都通過。\n\n**1. 寄送最後還是失敗時記一行**\n- 新檔 `notify/log.py`：記一行錯誤訊息。")
C1_DONE = "折扣碼功能已經寫好，但**我還沒 commit**：ERP 對接合約測試紅了，這要你決定。"
ASK = "改了 5 支檔。匯出格式要用 CSV 還是 JSON？"


@pytest.mark.parametrize("text", [S1_DONE, C1_DONE])
def test_fact_trigger_owed_without_completion_words(drive, capsys, tmp_path, text):
    """規則 SECOND_OPINION_FACT_TRIGGER（紅）：005 第 0 步兩筆漏擋——補題 S-1 第 4 回合收尾「兩件都改好了…全部 4 支測試都通過」、
    C-1 第 1 回合「已經寫好，但我還沒 commit」（還沒 commit 不是沒做完），都沒有完成詞表認得的說法；舊碼判成沒宣告完成，
    改了 5 支程式整個沒進第二意見閘。改後看事實：過門檻的收尾就欠，擋訊息照舊列規則、檔數與兩條出口。"""
    reason, _state, logs = drive(text, capsys, files=_files(tmp_path, 5))
    assert "SECOND_OPINION_REQUIRED" in reason and "程式檔 5 個" in reason
    assert reason.split("\n判準卡")[0].rstrip().endswith(HINT_TAIL) and "等第二意見｜<job_id>" in reason
    assert [p["event"] for p in _so_logs(logs)] == ["block"]


def test_fact_trigger_mid_question_not_owed_but_debt_kept(drive, capsys, tmp_path):
    """SECOND_OPINION_FACT_TRIGGER 唯一不判的：中途問使用者（最後一行是問句、沒宣告完成、這個使用者回合沒交收尾那批）→ 不欠、不留帳；
    欠帳不消：使用者回答後的收尾照欠。交過收尾那批（PRE_CLOSE 記了這個使用者回合）再用問句結尾 → 是收尾，照欠（紅：舊碼問句不判）。"""
    files = _files(tmp_path, 5)
    reason, state, logs = drive(ASK, capsys, files=files)
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs)
    drive.tx.user("用 CSV")
    state.update(turn_seq=6, turn_prompts_seq=6)
    reason, state, _ = drive(DONE, capsys, state=state)
    assert "SECOND_OPINION_REQUIRED" in reason, "問完回來收尾：先前改的 5 支照欠"
    st2 = {"phase": "working", "modified_files": [_mf(p) for p in files], "failing_tests": [], "recent_user_prompts": [],
           "stop_blocked_count": 0, "turn_seq": 5, "turn_prompts_seq": 5, "muted": True,
           so.PRE_CLOSE: {SID: {"uturn": 5, "owed": True}}}                     # 這個使用者回合交過收尾那批
    reason, _, logs = drive(ASK, capsys, state=st2)
    assert "SECOND_OPINION_REQUIRED" in reason and [p["event"] for p in _so_logs(logs)] == ["block"]


def test_exit_fingerprint_once_per_change_set(drive, capsys, tmp_path):
    """規則 SECOND_OPINION_EXIT_FINGERPRINT：「不需第二意見｜理由」放行並留帳；出口之後沒再改程式，下一次收尾（沒重寫出口行）不欠；
    出口之後又改了 1 支程式 → 再欠一次（紅：舊碼照 ONCE_PER_CLAIM，改 1 支沒過門檻就不再要）。"""
    files = _files(tmp_path, 5)
    reason, state, logs = drive(f"{S1_DONE}\n{DECLINE_LINE}", capsys, files=files)
    assert "[Guardian:SecondOpinion]" not in reason and [p["event"] for p in _so_logs(logs)] == ["declined"]
    assert state[so.EXIT][SID]["via"] == "declined" and state[so.EXIT][SID]["fp"]
    reason, state, logs = drive(S1_DONE, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs), "沒再改程式：這組改動交過了"
    drive.tx.user("cli 再補一個參數")
    state.update(turn_seq=6, turn_prompts_seq=6)
    state["modified_files"][0]["last_turn_seq"] = 6
    reason, state, logs = drive(S1_DONE, capsys, state=state)
    assert "SECOND_OPINION_REQUIRED" in reason and [p["event"] for p in _so_logs(logs)] == ["block"]
    reason, state, _ = drive(f"補好了。\n{DECLINE_LINE}", capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason, "再交一次出口就放行（不是修了又欠、修不停）"


def test_exit_fingerprint_waiting_exit_then_close_again_not_owed(drive, capsys, tmp_path):
    """SECOND_OPINION_EXIT_FINGERPRINT（紅）：收尾寫「等第二意見｜<job_id>」（job 還在跑）→ 留帳 waiting；同一回合沒再改程式、沒取結果又收尾
    → 不欠（舊碼照「start 了沒取結果」再擋一輪）。取回在等的結果那一回合照要四行（DONE_NOTICE），寫齊放行。"""
    drive.tx.opinion(status="")
    reason, state, logs = drive(WAIT_TEXT, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" not in reason and [p["event"] for p in _so_logs(logs)] == ["waiting"]
    assert state[so.EXIT][SID]["via"] == "waiting"
    reason, state, logs = drive(DONE, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs)
    _result(drive, "done")
    reason, state, _ = drive("看過結果了。", capsys, state=state)
    assert "[Guardian:SecondOpinion]" in reason and "第二意見與分歧裁決" in reason
    reason, state, _ = drive(FOUR, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason and state[so.EXIT][SID]["via"] == "ran"


def test_exit_fingerprint_recorded_even_when_earlier_gate_blocks(drive, capsys, tmp_path):
    """SECOND_OPINION_EXIT_FINGERPRINT：出口行在所有收尾閘前面就記——紅測閘先擋下、補件那則只寫不做行、沒重寫出口行，
    第二意見閘不再為同一組改動擋（舊碼宣告行只看收尾最後一則，補件那則沒寫就照擋）。"""
    state = {"phase": "working", "modified_files": [_mf(p) for p in _files(tmp_path, 5)], "stop_blocked_count": 0,
             "failing_tests": [{"cmd": "pytest a", "summary": "1 failed", "session_id": SID, "turn_seq": 5}],
             "recent_user_prompts": [], "turn_seq": 5, "turn_prompts_seq": 5, "muted": True}
    reason, state, _ = drive(f"{S1_DONE}\n{DECLINE_LINE}", capsys, state=state)
    assert "[Guardian:TestFailGate]" in reason and state[so.EXIT][SID]["via"] == "declined"
    state["failing_tests"] = []
    reason, _, logs = drive("紅測修好了，重跑全綠。", capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs, "block")


def test_fact_trigger_v6_off_unchanged(drive, capsys, tmp_path, monkeypatch):
    """總開關（v6）關：第二意見閘整段不跑，事實觸發與出口指紋都不動 state（同改動前）。"""
    monkeypatch.setenv("WG_V6", "0")
    reason, state, logs = drive(S1_DONE, capsys, files=_files(tmp_path, 5))
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs)
    assert so.EXIT not in state and "second_opinion_gate_turn" not in state


def test_mid_question_and_fingerprint_units():
    """mid_question：最後一行問句（? ？ 嗎 呢，可帶括號引號）才算；程式碼區塊裡的問句、宣告完成的那則、交過收尾那批的回合都不算。
    fingerprint：同一組改動相同、改了任一支（時間或回合）就變；沒有程式檔是空字串（不記出口）。"""
    assert so.mid_question({}, SID, ASK, 5) and so.mid_question({}, SID, "要不要順便清掉（會刪 3 個檔）嗎」", 5)
    assert not so.mid_question({}, SID, "全部完成了，要上GIT嗎？", 5), "宣告完成的那則是收尾"
    assert not so.mid_question({}, SID, "改好了。\n```\nok?\n```", 5)
    assert not so.mid_question({so.PRE_CLOSE: {SID: {"uturn": 5}}}, SID, ASK, 5)
    assert so.mid_question({so.PRE_CLOSE: {SID: {"uturn": 4}}}, SID, ASK, 5), "上一個使用者回合交的不算這回合"
    a = [{"path": "C:/p/a.py", "last_turn_seq": 5, "last_at": "t1"}, {"path": "C:/p/b.py", "last_turn_seq": 5}]
    assert so.fingerprint(a) == so.fingerprint(list(reversed(a))) == so.fingerprint(a + [{**a[0], "path": r"c:\p\A.py"}])
    assert so.fingerprint(a) != so.fingerprint([{**a[0], "last_at": "t2"}, a[1]]) and so.fingerprint([]) == ""


def test_exit_fingerprint_user_release_counts_as_exit(drive, capsys, tmp_path):
    """SECOND_OPINION_EXIT_FINGERPRINT：使用者放行也記成出口（不再欠的那類）——先前宣告不需、之後又改 1 支被擋到擋滿、使用者放行 →
    下一回合沒再改程式不欠（沒記的話，指紋跟那次宣告不同、出口又是不需 → 之後每次收尾都欠，修不停）。"""
    _, state, _ = drive(f"{DECLINE_LINE}\n{DONE}", capsys, files=_files(tmp_path, 5))
    drive.tx.user("再改一支")
    state.update(turn_seq=6, turn_prompts_seq=6)
    state["modified_files"][0]["last_turn_seq"] = 6
    assert "SECOND_OPINION_REQUIRED" in drive(DONE, capsys, state=state)[0]
    reason, state, _ = drive(DONE, capsys, state=state)
    assert RELEASE_TAG in reason
    q = f"{RELEASE_TAG} 第二意見要放行嗎？"
    drive.tx.call("AskUserQuestion", {"questions": [{"question": q, "options": []}]}, f'"{q}"="{OPT_RELEASE}"',
                  extra={"toolUseResult": {"answers": {q: OPT_RELEASE}}})
    reason, state, logs = drive(DONE, capsys, state=state)
    assert [p["event"] for p in _so_logs(logs)] == ["user_release"] and state[so.EXIT][SID]["via"] == "released"
    drive.tx.user("說明一下剛剛改了什麼")
    state.update(turn_seq=7, turn_prompts_seq=7)
    reason, _, logs = drive(DONE, capsys, state=state)
    assert "[Guardian:SecondOpinion]" not in reason and not _so_logs(logs)
