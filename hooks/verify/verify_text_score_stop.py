"""verify_text_score_stop.py：文字評分接到收尾（hooks/wg_text_score.py＋stop.py／user_prompt_submit.py 的呼叫點＋週彙總新欄）。

做什麼：
- 收尾不阻塞：on_stop 只寫工作檔、起背景就回（假裁判每題慢 0.3 秒，on_stop 回來時留帳還是空的），背景跑完留帳一筆 final_reply、刪工作檔；
  背景行程沒有視窗、脫離 hook，腳本取自本樹。
- min_chars 門檻：去掉空白後不到 min_chars 不送；剛好到就送；同一則不重送。
- enabled=false：on_stop 不起背景、不動 state；tail_note 有評分也不送（同案 enabled=true 先證會送）。
- 下一回合只記錄：上一回合那則評完 → guard-text_score_tail 記 recorded 一次，不注入；沒評完 → 記 pending 一次；評的是更早回合 → 不記。
- 回覆與文件都對當下的需求目標評（任務帶 goal）。
- docs 類：本回合、本 session 改過的 .md 才送；背景照 auto_targets.docs 的路徑樣式評（checklist 有帳、TECH.md 沒帳）；改過再送、沒改不重送；不注入。
- 背景一份出錯不影響其他份；final_reply 從 stdin 餵、docs 給路徑。
- stop.py：各閘之前呼叫 on_stop（只給本 session 改的檔），state 有改就寫回。
- 週彙總：每份規格列實際回答的裁判與種類則數（舊紀錄記「沒記」、裁判不在記「沒回答」）。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_text_score_stop.py
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

HOOKS = Path(__file__).resolve().parent.parent
TREE = HOOKS.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(TREE))   # worktree 內跑：wg_core 的 lib／workflow 指本樹
sys.path.insert(0, str(HOOKS))
sys.path.insert(0, str(TREE / "lib"))

import wg_core  # noqa: E402
import wg_friction  # noqa: E402
import wg_need_goal  # noqa: E402
import wg_text_score as wts  # noqa: E402
from handlers import stop as st  # noqa: E402
from handlers import user_prompt_submit as ups  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


VTS = _load("verify_text_score_for_stop", TREE / "tools" / "verify" / "verify_text_score.py")   # 假 Ollama 與資料根工具
WEEKLY = _load("text_score_weekly_for_stop", TREE / "tools" / "text-score-weekly.py")

SID = "sess-ts"
REPLY = VTS.LONG
DOCS = {"final_reply": [], "docs": ["memory/_staging/*checklist*.md"]}   # 出廠沒列 docs（不評文件）；文件評分的案例自己給樣式
CFG = {"text_score": {"enabled": True, "min_chars": 300, "reply_scope": "all",
                      "auto_targets": DOCS}}   # 評分機制本身的案例：每則都評（預設只評交付改程式那則，見 verify_gate_slimming）
GOAL = "收尾回覆要讓設計者看懂改了什麼"


class _Stop(Exception):
    """在要驗的那一段之後停下 handle_stop。"""


@pytest.fixture
def world(tmp_path, monkeypatch):
    """資料根指 tmp（背景行程吃 WG_CLAUDE_DIR）；工作檔、留帳、guard log 都在 tmp；guard log 時鐘每筆加一秒。"""
    root = tmp_path / "data"
    (root / "workflow").mkdir(parents=True)
    monkeypatch.setenv("WG_CLAUDE_DIR", str(root))
    monkeypatch.setattr(wts, "JOB_DIR", root / "workflow" / "text-score")
    monkeypatch.setattr(wts, "LEDGER", root / "Logs" / "guard-text_score.jsonl")
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", root / "Logs")
    tick = itertools.count()
    base = datetime(2026, 10, 21, 9, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    monkeypatch.setattr(wg_core, "_now_iso", lambda: (base + timedelta(seconds=next(tick))).isoformat(timespec="seconds"))
    monkeypatch.setattr(wts, "current_goal", lambda state, sid: GOAL)   # 有當下目標才評回覆（沒目標不評的案在 verify_gate_trim）
    return root


@pytest.fixture
def spawned(monkeypatch):
    """Popen 換替身：記 argv 與參數，不真的起行程。"""
    seen: List[Any] = []

    def fake(argv, *a, **kw):
        seen.append((list(argv), kw))
        return object()
    monkeypatch.setattr(wts.subprocess, "Popen", fake)
    return seen


def _guard(root: Path, name: str) -> List[Dict[str, Any]]:
    p = root / "Logs" / f"guard-{name}.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def _ledger_rec(sha: str, summary: str = "評分 5/7｜沒過：R1、R4", kind: str = "final_reply", session: str = SID,
                spec: str = "reader-designer") -> str:
    return json.dumps({"ts": "2026-10-21T09:00:00", "session": session, "kind": kind, "spec": spec,
                       "text_sha": sha, "summary": summary, "items": []}, ensure_ascii=False)


def _write_ledger(root: Path, *lines: str) -> None:
    (root / "Logs").mkdir(parents=True, exist_ok=True)
    (root / "Logs" / "guard-text_score.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _wait(cond, secs: float = 90.0) -> bool:
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.2)
    return False


# ─── 收尾送評：不阻塞、背景留帳 ───────────────────────────────────────────────

def test_stop_returns_before_judge_and_worker_logs_final_reply(world, tmp_path):
    fake = VTS.Fake()
    handler = fake.server.RequestHandlerClass
    slow_post = handler.do_POST
    handler.do_POST = lambda self: (time.sleep(0.3), slow_post(self))[1]   # 每題慢 0.3 秒：8 題至少 2 秒
    try:
        VTS.data_root(tmp_path, {"a": VTS.backend(fake.url)}, {"min_chars": 300})
        state: Dict[str, Any] = {}
        t0 = time.monotonic()
        assert wts.on_stop(state, SID, REPLY, [], 3, CFG) is True
        took = time.monotonic() - t0
        assert not wts.LEDGER.exists() and took < 2.0, f"on_stop 等了 {took:.2f} 秒或留帳已先寫"   # 沒等裁判
        assert len(list(wts.JOB_DIR.glob("*.json"))) == 1
        assert _wait(lambda: wts.LEDGER.exists() and not list(wts.JOB_DIR.glob("*.json"))), \
            (wts.JOB_DIR / "worker.log").read_text(encoding="utf-8", errors="replace")
        [rec] = [json.loads(x) for x in wts.LEDGER.read_text(encoding="utf-8").splitlines()]
        assert (rec["kind"], rec["session"], rec["text_sha"], rec["source"]) == ("final_reply", SID, wts.text_sha(REPLY), "stdin")
        assert rec["summary"] == "評分 8/8｜全過" and len(fake.requests) == 8
        assert state["text_score"][SID]["reply"] == {"sha": wts.text_sha(REPLY), "turn": 3}
    finally:
        fake.close()


def test_spawn_is_detached_windowless_and_from_this_tree(world, spawned):
    assert wts.on_stop({}, SID, REPLY, [], 1, CFG) is True
    [(argv, kw)] = spawned
    assert argv[:3] == [sys.executable, "-X", "utf8"] and Path(argv[3]) == HOOKS / "wg_text_score.py" and argv[4] == "--job"
    assert Path(argv[5]).parent == wts.JOB_DIR and kw["stdin"] == subprocess.DEVNULL
    if sys.platform == "win32":
        assert kw["creationflags"] == subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    else:
        assert kw["start_new_session"] is True
    job = json.loads(Path(argv[5]).read_text(encoding="utf-8"))
    assert job == {"session": SID, "tasks": [{"kind": "final_reply", "text": REPLY, "goal": GOAL}]}


def test_ledger_path_is_the_tools_log_path():
    assert wts.LEDGER == VTS.TS.LOG_PATH and wts.TOOL == TREE / "tools" / "text-score.py"


# ─── 門檻、不重送、全關 ──────────────────────────────────────────────────────

def test_min_chars_counts_without_whitespace_and_same_reply_not_resent(world, spawned):
    short = "字" * 299 + " \n\t" * 50
    assert wts.on_stop({}, SID, short, [], 1, CFG) is False and spawned == []
    state: Dict[str, Any] = {}
    exact = "字" * 300
    assert wts.on_stop(state, SID, exact, [], 1, CFG) is True and len(spawned) == 1
    assert wts.on_stop(state, SID, exact, [], 1, CFG) is False and len(spawned) == 1        # 同一則被擋後再 Stop：不重送
    assert wts.on_stop(state, SID, exact + "補", [], 1, CFG) is True and len(spawned) == 2  # 換了一則就送


def test_enabled_false_sends_nothing_and_injects_nothing(world, spawned):
    sha = wts.text_sha(REPLY)
    _write_ledger(world, _ledger_rec(sha))
    on_state = {"turn_seq": 4, "text_score": {SID: {"reply": {"sha": sha, "turn": 4}}}}
    assert wts.on_stop({}, SID, REPLY, [], 4, CFG) is True and len(spawned) == 1            # 前置：開著會送
    wts.tail_note(on_state, SID, CFG)
    assert on_state["text_score"][SID]["reply"].get("done") is True                         # 前置：開著會記
    for off in ({"text_score": {"enabled": False, "min_chars": 300}}, {}, {"text_score": {"min_chars": 300}}):
        state: Dict[str, Any] = {}                                                           # 關掉、沒有這段、沒寫 enabled
        assert wts.on_stop(state, SID, REPLY + "別則", [], 4, off) is False and len(spawned) == 1 and state == {}
        off_state = {"turn_seq": 4, "text_score": {SID: {"reply": {"sha": sha, "turn": 4}}}}
        assert wts.tail_note(off_state, SID, off) == "" and "done" not in off_state["text_score"][SID]["reply"]


def test_pointer_follows_last_long_reply_in_turn_and_across_turns(world, spawned):
    """codex 第 1 點：「上一則」指標每次 Stop 都照最後一則夠長的回覆更新（送評去重另記）；短碎句不換指標。"""
    a, b = REPLY, REPLY + "另一則"
    state: Dict[str, Any] = {}
    for text in (a, b, a):                                                                   # 同回合被擋兩次：A → B → A
        wts.on_stop(state, SID, text, [], 5, CFG)
    assert state["text_score"][SID]["reply"] == {"sha": wts.text_sha(a), "turn": 5} and len(spawned) == 2
    assert wts.on_stop(state, SID, "短碎句。", [], 5, CFG) is False                          # 碎句不評、指標不動
    assert state["text_score"][SID]["reply"] == {"sha": wts.text_sha(a), "turn": 5}
    _write_ledger(world, _ledger_rec(wts.text_sha(a), "評分 6/7｜沒過：R2"), _ledger_rec(wts.text_sha(b)))
    state["turn_seq"] = 5
    assert wts.tail_note(state, SID, CFG) == ""
    assert [r["summary"] for r in _guard(world, "text_score_tail")] == ["評分 6/7｜沒過：R2"]   # 記的是指標那則（A）
    assert wts.on_stop(state, SID, a, [], 6, CFG) is True and len(spawned) == 2              # 下一回合同一段字：不重送
    state["turn_seq"] = 6
    wts.tail_note(state, SID, CFG)
    assert [r["summary"] for r in _guard(world, "text_score_tail")][-1] == "評分 6/7｜沒過：R2"   # 但這一則照樣記


def test_spawn_failure_leaves_no_job_and_retries_next_stop(world, monkeypatch, capsys):
    """codex 第 2 點：背景起不來 → 刪工作檔、不記成送過，下次 Stop 再送。"""
    calls: List[int] = []

    def flaky(argv, *a, **kw):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("起不來")
        return object()
    monkeypatch.setattr(wts.subprocess, "Popen", flaky)
    state: Dict[str, Any] = {}
    assert wts.on_stop(state, SID, REPLY, [], 2, CFG) is True                                 # 指標有更新，state 要寫回
    assert "收尾送評失敗" in capsys.readouterr().err and list(wts.JOB_DIR.glob("*.json")) == []
    assert "sent" not in state["text_score"][SID]
    assert wts.on_stop(state, SID, REPLY, [], 2, CFG) is True and len(calls) == 2
    assert state["text_score"][SID]["sent"] == [f"reply:{wts.text_sha(REPLY)}"]


# ─── 下一回合只記錄、不注入 ───────────────────────────────────────────────────

def test_tail_note_records_once_never_injects(world):
    sha = wts.text_sha(REPLY)
    _write_ledger(world, _ledger_rec("other"), _ledger_rec(sha, kind="docs"), _ledger_rec(sha, session="別的"),
                  _ledger_rec(sha))
    state = {"turn_seq": 5, "text_score": {SID: {"reply": {"sha": sha, "turn": 5}}}}
    assert wts.tail_note(state, SID, CFG) == "" and wts.tail_note(state, SID, CFG) == ""   # 不注入
    recs = _guard(world, "text_score_tail")
    assert [(r["event"], r["text_sha"], r["summary"]) for r in recs] == [("recorded", sha, "評分 5/7｜沒過：R1、R4")]   # 只記一次
    assert [r for r in _guard(world, "entry") if r.get("event") == "ask"] == []             # 不再問 AI 照抄


def test_tail_note_pending_logged_once_and_older_turn_not_sent(world):
    sha = wts.text_sha(REPLY)
    state = {"turn_seq": 5, "text_score": {SID: {"reply": {"sha": sha, "turn": 5}}}}
    assert wts.tail_note(state, SID, CFG) == "" and wts.tail_note(state, SID, CFG) == ""
    assert [(r["event"], r["text_sha"]) for r in _guard(world, "text_score_tail")] == [("pending", sha)]
    _write_ledger(world, _ledger_rec(sha))
    state["turn_seq"] = 6                                                                    # 評完時已是下一回合：不補送
    assert wts.tail_note(state, SID, CFG) == ""
    state["turn_seq"] = 5
    assert wts.tail_note(state, SID, CFG) == ""
    assert [r["event"] for r in _guard(world, "text_score_tail")] == ["pending", "recorded"]  # 對照：同回合就記


@pytest.fixture
def ups_wired(monkeypatch):
    """UPS handler 跑完整條路，其他依賴換空殼（照 verify_ups_overview_wiring）；回 outputs。"""
    outputs: List[Any] = []
    for name, fn in (("_ups_sentinel_check_and_arm", lambda *a: None), ("_ups_sentinel_clear", lambda sid: None),
                     ("run_pre_gates", lambda *a: None), ("build_context", lambda *a: None),
                     ("collect_matched_atoms", lambda *a: ([], {}, [], [], {}, [], "general", {})),
                     ("assemble_injection", lambda *a, **k: ([], {})), ("_maybe_spawn_failure_extraction", lambda *a: None),
                     ("_update_topic_tracker", lambda *a: None), ("_truncate_context_by_activation", lambda lines, *a: lines),
                     ("reconcile_injection_after_trim", lambda *a: []), ("write_state", lambda sid, s: None),
                     ("output_json", lambda d: outputs.append(d)), ("output_nothing", lambda: outputs.append(None))):
        monkeypatch.setattr(ups, name, fn)
    monkeypatch.setattr(wg_friction, "record_correction", lambda *a: None)
    monkeypatch.setattr(wg_need_goal, "on_prompt", lambda *a, **k: "")                    # 不寫目標樹檔
    return outputs


def test_ups_does_not_inject_score_line(world, ups_wired, monkeypatch):
    sha = wts.text_sha(REPLY)
    _write_ledger(world, _ledger_rec(sha))
    state = {"turn_seq": 2, "evasion_flag": {"phrase": "之後再", "context_excerpt": "x", "hint": "h"},
             "text_score": {SID: {"reply": {"sha": sha, "turn": 2}}}}
    monkeypatch.setattr(ups, "_ensure_state", lambda sid, inp, cfg: state)
    ups.handle_user_prompt_submit({"session_id": SID, "prompt": "繼續", "transcript_path": ""}, {"sync_keywords": [], **CFG})
    ctx = ups_wired[0]["hookSpecificOutput"]["additionalContext"]
    assert "上則評分" not in ctx and "TEXT_SCORE_TAIL" not in ctx and "[Guardian:Evasion]" in ctx and state["turn_seq"] == 3
    assert state["text_score"][SID]["reply"].get("done") is True                            # 照樣記


# ─── 文件類：本回合改過的 .md、路徑樣式由 text-score 判 ─────────────────────

def test_docs_this_turn_only_and_resent_after_change(world, tmp_path, spawned):
    doc = tmp_path / "proj" / "memory" / "_staging" / "g15-checklist.md"
    old = tmp_path / "proj" / "old.md"
    for p in (doc, old):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    mods = [{"path": str(doc), "session_id": SID, "last_turn_seq": 4},
            {"path": str(old), "session_id": SID, "last_turn_seq": 3},                       # 上一回合改的
            {"path": str(tmp_path / "proj" / "a.py"), "session_id": SID, "last_turn_seq": 4},  # 不是 .md
            {"path": str(tmp_path / "proj" / "gone.md"), "session_id": SID, "last_turn_seq": 4},  # 已不在
            {"path": str(doc).replace("g15", "peer"), "session_id": "別的", "last_turn_seq": 4}]
    state: Dict[str, Any] = {}
    assert wts.on_stop(state, SID, "短", mods, 4, CFG) is True
    job = json.loads(Path(spawned[0][0][5]).read_text(encoding="utf-8"))
    assert job["tasks"] == [{"kind": "docs", "path": str(doc), "goal": GOAL}] and "reply" not in state["text_score"][SID]
    assert wts.on_stop(state, SID, "短", mods, 4, CFG) is False and len(spawned) == 1        # 沒改不重送
    os.utime(doc, ns=(time.time_ns(), time.time_ns() + 10_000_000))
    assert wts.on_stop(state, SID, "短", mods, 4, CFG) is True and len(spawned) == 2          # 又改過就再送


def test_worker_scores_docs_by_path_pattern_and_never_injects(world, tmp_path):
    fake = VTS.Fake()
    try:
        VTS.data_root(tmp_path, {"a": VTS.backend(fake.url)}, {"min_chars": 300, "auto_targets": DOCS})
        hit = tmp_path / "proj" / "memory" / "_staging" / "g15-checklist.md"
        miss = tmp_path / "proj" / "TECH.md"
        for p in (hit, miss):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(VTS.LONG, encoding="utf-8")
        mods = [{"path": str(p), "session_id": SID, "last_turn_seq": 2} for p in (hit, miss)]
        state: Dict[str, Any] = {"turn_seq": 2}
        assert wts.on_stop(state, SID, "短", mods, 2, CFG) is True
        assert _wait(lambda: not list(wts.JOB_DIR.glob("*.json"))), \
            (wts.JOB_DIR / "worker.log").read_text(encoding="utf-8", errors="replace")
        assert wts.LEDGER.exists(), (wts.JOB_DIR / "worker.log").read_text(encoding="utf-8", errors="replace")
        recs = [json.loads(x) for x in wts.LEDGER.read_text(encoding="utf-8").splitlines()]
        assert [(r["kind"], Path(r["source"]).name) for r in recs] == [("docs", "g15-checklist.md")]
        assert "不評：來源" in (wts.JOB_DIR / "worker.log").read_text(encoding="utf-8")         # TECH.md 不評、原因留 log
        assert wts.tail_note(state, SID, CFG) == "" and _guard(world, "text_score_tail") == []   # docs 不注入、不記
    finally:
        fake.close()


def test_run_job_feeds_stdin_and_one_failure_does_not_stop_others(world, monkeypatch):
    calls: List[Any] = []

    class FakeTool:
        @staticmethod
        def main(argv):
            calls.append((argv, sys.stdin.buffer.read().decode("utf-8") if argv[0] == "-" else None))
            if argv[0].endswith("bad.md"):
                raise RuntimeError("壞了")
            if argv[0].endswith("exit.md"):
                raise SystemExit(2)                                                          # argparse 這類直接結束
            return 0
    monkeypatch.setattr(wts, "_load_tool", lambda: FakeTool)
    monkeypatch.setattr(sys, "stdin", sys.stdin)
    wts.JOB_DIR.mkdir(parents=True)
    job = wts.JOB_DIR / "j.json"
    job.write_text(json.dumps({"session": SID, "tasks": [{"kind": "docs", "path": "bad.md", "goal": GOAL},
                                                         {"kind": "docs", "path": "exit.md", "goal": GOAL},
                                                         {"kind": "final_reply", "text": "回覆全文", "goal": GOAL},
                                                         {"kind": "docs", "path": "ok.md", "goal": GOAL}]}, ensure_ascii=False),
                   encoding="utf-8")
    assert wts.run_job(job) == 0 and not job.exists()
    tail = ["--auto-kind", "docs", "--session", SID, "--tail-line", "--goal", GOAL]
    assert calls == [(["bad.md", *tail], None), (["exit.md", *tail], None),
                     (["-", "--auto-kind", "final_reply", "--session", SID, "--tail-line", "--goal", GOAL], "回覆全文"),
                     (["ok.md", *tail], None)]


def test_run_job_deletes_job_when_tool_cannot_load(world, monkeypatch, capsys):
    """codex 第 3 點：評分工具載不到 → 記原因、照樣刪工作檔（不留給沒人會再跑的殘檔）。"""
    def boom():
        raise ImportError("text-score 壞了")
    monkeypatch.setattr(wts, "_load_tool", boom)
    wts.JOB_DIR.mkdir(parents=True)
    job = wts.JOB_DIR / "j.json"
    job.write_text(json.dumps({"session": SID, "tasks": [{"kind": "docs", "path": "a.md"}]}), encoding="utf-8")
    assert wts.run_job(job) == 2 and not job.exists() and "沒評成" in capsys.readouterr().err


# ─── stop.py 呼叫點 ───────────────────────────────────────────────────────────

def test_stop_calls_on_stop_before_gates_with_own_files(world, tmp_path, monkeypatch):
    seen: List[Any] = []
    writes: List[Any] = []

    def fake_on_stop(state, sid, reply, mods, turn, config, *, code_reply, user_turn):
        seen.append((sid, reply, [m["path"] for m in mods], turn, config is cfg, code_reply))
        return True

    def lap(seg):
        if seg == "文字評分":
            raise _Stop
        return False
    cfg = {"text_score": {"enabled": True}}
    state = {"phase": "working", "turn_seq": 7, "failing_tests": [], "session": {"cwd": str(tmp_path)}, "need_goal_code_decl_turn": 7,
             "modified_files": [{"path": "mine.md", "session_id": SID, "last_turn_seq": 7},
                                {"path": "peer.md", "session_id": "別的", "last_turn_seq": 7}]}
    for name, fn in (("_ensure_state", lambda *a, **k: state), ("_find_session_transcript", lambda *a, **k: None),
                     ("_record_pick", lambda *a, **k: None), ("token_warn_payload", lambda *a, **k: ""),
                     ("reading_path_note", lambda *a, **k: ("", False)), ("_hook_lap", lap),
                     ("write_state", lambda sid, s: writes.append(sid)), ("_text_score_on_stop", fake_on_stop)):
        monkeypatch.setattr(st, name, fn)
    monkeypatch.setattr(st.aec_ledger, "collect_at_completion", lambda *a, **k: None)
    with pytest.raises(_Stop):
        st.handle_stop({"session_id": SID, "cwd": str(tmp_path), "last_assistant_message": "最終回覆全文"}, cfg)
    assert seen == [(SID, "最終回覆全文", ["mine.md"], 7, True, False)] and writes and writes[-1] == SID


# ─── 週彙總讀裁判與種類 ───────────────────────────────────────────────────────

def test_weekly_counts_judges_and_kinds(tmp_path):
    now = datetime.now().isoformat(timespec="seconds")
    base = {"ts": now, "spec": "reader-designer", "spec_sha": "a", "overall": "過",
            "items": [{"id": "R1", "status": "判定", "verdict": "是"}]}
    log = tmp_path / "log.jsonl"
    log.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in [
        {**base, "models_used": ["gemma4:e4b"], "judges": {"rdchat-direct": "gemma4:e4b"}, "kind": "final_reply"},
        {**base, "models_used": ["gemma4:e4b"], "kind": "final_reply"},
        {**base, "models_used": ["qwen3:4b-instruct-2507-q4_K_M"], "kind": "docs"},
        {**base, "models_used": [], "overall": "未評", "kind": "final_reply"},
        dict(base),                                                                           # 舊紀錄：沒這兩欄
    ]) + "\n", encoding="utf-8")
    weeks = WEEKLY.recent_weeks(1, datetime.now().date())
    s = WEEKLY.summarize(WEEKLY.load_records(log)[0], weeks)["reader-designer"]
    assert s["judges"] == {"gemma4:e4b": 2, "qwen3:4b-instruct-2507-q4_K_M": 1, "沒回答": 1, "沒記": 1}
    assert s["kinds"] == {"final_reply": 3, "docs": 1, "沒記": 1}
    md = WEEKLY.render({"reader-designer": s}, weeks)
    assert ("裁判（實際回答）：gemma4:e4b 2、qwen3:4b-instruct-2507-q4_K_M 1、沒回答 1、沒記 1｜"
            "種類：final_reply 3、docs 1、沒記 1") in md.splitlines()
