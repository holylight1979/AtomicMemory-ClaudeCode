"""verify_reading_path_hook.py：收尾檢核附「改動對閱讀路徑的影響」（hooks/wg_reading_path.py，背景量）。

正例：改碼回合收尾只交工作、不附；背景量完（這裡換成同行程直接跑）下一次收尾附尾行＋可評級與否＋變差／新增最差一條；
      同一批輸入只量一次、只附一次；session commit 過 → before 是第一筆的父提交；部位表「讀路徑樣本」給的入口優先；
      量測中又改的碼記著，量完再量最新的一批；真的起背景行程也照寫結果檔。
反例：沒改程式碼不附；不在 git、還沒 commit、量尺失敗、背景逾時、背景行程中斷、只改測試檔、還沒 git add 的新檔
      → 各附一句原因、都不附手動指令；逾時過的根之後不再量（不再起任何子行程）。子行程都帶 CREATE_NO_WINDOW。
逾時一律用假的 run 丟 TimeoutExpired，不真的睡到預算用完。
真 Stop 入口（改碼交工作、下次收尾附段落、沒改碼不附、逾時附原因）在 verify_stop_reconcile.py 的 driven 夾具。
本檔驗的是量測本身與量不出來的原因文字，所以把 reading_path.remind_only_over_threshold 關掉（LEGACY）；開著時沒有條目超線的
一批整段不送（只留帳），由 verify_turn_judgment_threshold.py 驗。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_reading_path_hook.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

import wg_reading_path as rph  # noqa: E402

REAL_SPAWN = rph._spawn_worker   # hooks/verify/conftest.py 每案把它換成不起行程；真起行程的案例換回來

_SID = "sid-rp"
LEGACY = {"reading_path": {"remind_only_over_threshold": False}}   # 沒超線也送（本檔要看原因文字）
_EXTS = [".py", ".cs", ".js"]
_BODY = "def {0}(n):\n    k = n + 1\n    k *= 2\n    return k\n"
APP = {"app.py": "from x import a\nfrom y import b\n\n\ndef main():\n    n = a(1)\n    n += b(2)\n    return n\n\n\n"
                 'if __name__ == "__main__":\n    main()\n',
       "x.py": _BODY.format("a"), "y.py": _BODY.format("b")}
WORSE = {"y.py": "from z import c\n\n\ndef b(n):\n    return c(n)\n", "z.py": _BODY.format("c")}


def _write(root: Path, files: dict) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return root


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _repo(root: Path, files: dict = APP) -> Path:
    _write(root, files)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _mf(path, turn=5):
    return {"path": str(path), "tool": "Edit", "session_id": _SID, "turn_seq": turn, "last_turn_seq": turn}


def _state(*mods, **extra) -> dict:
    return {"turn_seq": 5, "modified_files": list(mods), **extra}


def _inline(run=subprocess.run, seen=None):
    """背景量測換成同一個行程直接跑完、照寫結果檔（不用等背景行程）；seen 給了就記下每份工作檔。"""
    def spawn(path):
        job = json.loads(Path(path).read_text(encoding="utf-8"))
        if seen is not None:
            seen.append(job)
        rph.write_result(Path(job["out"]), rph.run_job(job, run=run))
    return spawn


def _note(state, run=subprocess.run, worker_run=None):
    """收尾兩次：第一次交給背景量（這次不附），第二次附上量完的結果。回第二次附的文字。"""
    first, changed = rph.reading_path_note(state, _SID, LEGACY, run=run, spawn=_inline(worker_run or run))
    assert first is None and changed and state["reading_path"][_SID].get("job"), "交工作的那次收尾不附結果、記下工作"
    second, _ = rph.reading_path_note(state, _SID, LEGACY, run=run, spawn=_inline(worker_run or run))
    assert not state["reading_path"][_SID].get("job"), "結果附過就清掉工作"
    return second


def _times_out_on(marker):
    """假的 run：指令含 marker 就當逾時（不真的等），其他照真的跑。"""
    real = subprocess.run

    def run(args, **kw):
        if any(marker in str(a) for a in args):
            raise subprocess.TimeoutExpired(args, kw.get("timeout"))
        return real(args, **kw)
    return run


@pytest.fixture(autouse=True)
def _jobs(tmp_path_factory, monkeypatch):
    """工作檔與結果檔放在受測目錄外（git 錄製重播只比對受測目錄）。"""
    monkeypatch.setattr(rph, "JOB_DIR", tmp_path_factory.mktemp("rp-jobs"))


# ─── 純函式 ──────────────────────────────────────────────────────────────────

def test_code_files_this_turn_only_counts_code():
    mods = [_mf("a.py"), _mf("b.md"), _mf("c.py", 3), {"path": "d.cs", "turn_seq": 5}]
    assert rph.code_files(mods, _EXTS, 5) == ["a.py", "d.cs"]
    assert rph.code_files(mods, _EXTS) == ["a.py", "c.py", "d.cs"]


def test_base_is_head_until_the_session_commits_then_the_first_commits_parent():
    assert rph.base_spec("k", {}) == "HEAD"
    assert rph.base_spec("k", {"k": {"shas": ["aaa", "bbb"]}}) == "aaa^"
    assert rph.base_spec("k", {"other": {"shas": ["aaa"]}}) == "HEAD"


def test_sample_entry_takes_the_first_code_token(tmp_path):
    _write(tmp_path, {"hooks/app.py": "", "hooks/handlers/stop.py": "", "tools/t.py": "", "lib/m.py": ""})
    hit = str(tmp_path / "hooks/handlers/stop.py")
    cell = "settings.json > hooks/app.py > handlers/<event>.py > wg_*.py（3 層）"
    assert rph.sample_entry(cell, tmp_path, ["hooks/handlers"], hit, _EXTS) == str(tmp_path / "hooks/app.py")
    tool = str(tmp_path / "tools/t.py")
    assert rph.sample_entry("tools/<腳本>.py --help > lib/<模組>.py（2 層）", tmp_path, ["tools"], tool, _EXTS) == tool
    other = str(tmp_path / "lib/m.py")
    assert rph.sample_entry("handlers/<event>.py > lib/<x>.py", tmp_path, ["hooks"], other, _EXTS) is None, \
        "第一個程式檔是樣式但對不上改過的檔 → 交給量尺自動找"
    assert rph.sample_entry("hooks/missing.py > lib/m.py", tmp_path, ["hooks"], other, _EXTS) is None
    assert rph.sample_entry("無", tmp_path, ["hooks"], other, _EXTS) is None


def test_summarize_ratable_unratable_and_worst_row():
    row = lambda st, cert, t, ent="a::m": {"status": st, "certain": cert, "entry": ent, "landing": f"z::{t}",
                                          "before": None if st == "new" else {"turns": 1, "file_jumps": 1, "handoffs": 0},
                                          "after": {"turns": t, "file_jumps": t, "handoffs": 0}}
    ok = {"ratable": True, "rows": [row("same", True, 1), row("worse", True, 2), row("new", False, 5), row("new", True, 3)]}
    lines = rph.summarize(ok, "READING_PATH DONE mode=compare ratable=1")
    assert lines[0].strip().startswith("READING_PATH DONE mode=compare") and "可評級：是" in lines[1]
    assert "[新增] a::m → z::3｜拐彎 -→3" in lines[2], "全確定優先，再比 after 拐彎"
    bad = {"ratable": False, "ratable_before": True, "ratable_after": False, "coverage_drop": True, "emptied_files": ["q.py"],
           "rows": [row("same", True, 1)], "entry_misses": ["pkg/gone.py"]}
    text = "\n".join(rph.summarize(bad, "READING_PATH DONE mode=compare ratable=0"))
    assert "可評級：否" in text and "after 有入口沒有全確定的路" in text and "解析失敗或有函式↔零函式 1 檔" in text
    assert "沒有變差或新增的路徑" in text and "找不到函式的入口 1 個" in text and "gone.py" not in text


# ─── 真量尺（真 git 夾具；背景量測換成同行程跑） ────────────────────────────────────

def test_code_change_turn_hands_off_then_attaches_tail_ratable_and_worst_once(tmp_path):
    root = _repo(tmp_path / "r")
    _write(root, WORSE)
    _git(root, "add", "z.py")
    state = _state(_mf(root / "y.py"), _mf(root / "z.py"))
    note = _note(state)
    assert note and note.startswith("[Guardian:ReadingPath] 第 5 回合改動對閱讀路徑的影響（背景量完"), note
    assert "READING_PATH DONE mode=compare" in note and "可評級：" in note
    assert "[新增]" in note and "z.py::c" in note, note
    head = _git(root, "rev-parse", "--short=12", "HEAD")
    assert f"before={head}" in note
    seen = []
    assert rph.reading_path_note(state, _SID, LEGACY, spawn=_inline(seen=seen)) == (None, False) and seen == [], \
        "同一批輸入只量一次、只附一次"
    _write(root, {"z.py": _BODY.format("c") + "\n"})
    assert _note(state), "又改了 → 再量再附"


def test_no_code_change_this_turn_attaches_nothing(tmp_path):
    root = _repo(tmp_path / "r")
    state = _state(_mf(root / "notes.md"))
    assert rph.reading_path_note(state, _SID, LEGACY) == (None, False) and "reading_path" not in state
    state = _state(_mf(root / "y.py", 3))
    assert rph.reading_path_note(state, _SID, LEGACY) == (None, False) and "reading_path" not in state, \
        "前幾回合改的不算這回合改碼"


def test_session_commit_moves_before_to_the_first_commits_parent(tmp_path):
    root = _repo(tmp_path / "r")
    base = _git(root, "rev-parse", "--short=12", "HEAD")
    _write(root, WORSE)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "session")
    first = _git(root, "rev-parse", "HEAD")
    key = rph._git_root_of(str(root / "y.py"))[0]
    note = _note(_state(_mf(root / "y.py"), committed_new_code={key: {"shas": [first]}}))
    assert f"before={base}" in note and "[新增]" in note, note


def test_overview_map_sample_gives_the_entry(tmp_path):
    root = _repo(tmp_path / "r", {**APP, "hooks/run.py": "from x import a\n\n\ndef go():\n    return a(1) + 1\n"})
    _write(root, {".claude/overview-map.md": "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 讀路徑樣本 |\n|---|---|---|---|---|\n"
                                             "| `hooks/` | 入口 | 無 | 無 | settings.json > hooks/run.py > x.py |\n"})
    seen = []
    real = subprocess.run

    def spy(args, **kw):
        seen.append((list(args), kw.get("creationflags")))
        return real(args, **kw)

    _write(root, {"x.py": _BODY.format("a") + "\n"})
    _note(_state(_mf(root / "x.py")), run=spy)
    tool = next(a for a, _ in seen if str(rph.TOOL) in a)
    entries = [tool[i + 1] for i, v in enumerate(tool) if v == "--entry"]
    assert entries == [], "x.py 在部位表上沒給入口 → 不給 --entry，量尺自動偵測"
    seen.clear()
    _write(root, {"hooks/run.py": "from x import a\n\n\ndef go():\n    return a(2) + 1\n"})
    _note(_state(_mf(root / "hooks/run.py")), run=spy)
    tool = next(a for a, _ in seen if str(rph.TOOL) in a)
    assert [tool[i + 1] for i, v in enumerate(tool) if v == "--entry"] == [str(root / "hooks" / "run.py")]
    assert "--layers" in tool and "--scope" not in tool, "部位表一起交給量尺；掃描母體用預設 git"
    assert all(flag == rph._NO_WINDOW for _, flag in seen), "每個子行程都帶 CREATE_NO_WINDOW"


# ─── 量不出來就附原因（不附手動指令） ──────────────────────────────────────────────

def test_outside_git_and_no_commit_say_why(tmp_path):
    loose = _write(tmp_path / "loose", APP)
    note = _note(_state(_mf(loose / "y.py")))
    assert "不在 git 工作區的改檔 1 個" in note and "y.py" not in note, "只報個數，不列檔名（避免和對帳閘的欠帳檔名混淆）"
    empty = tmp_path / "empty"
    _write(empty, APP)
    subprocess.run(["git", "init", "-q", str(empty)], check=True)
    _git(empty, "add", "-A")
    assert "解不出" in _note(_state(_mf(empty / "y.py")))


def test_tool_failure_and_only_tests_and_untracked_say_why(tmp_path):
    root = _repo(tmp_path / "r", {**APP, "tests/test_y.py": "def test_y():\n    assert 1\n"})
    _write(root, {"tests/test_y.py": "def test_y():\n    assert 2\n"})
    assert "只改了測試檔" in _note(_state(_mf(root / "tests/test_y.py")))
    _write(root, {"new.py": _BODY.format("n")})
    note = _note(_state(_mf(root / "new.py")))
    assert "還沒 git add 的新檔 1 個" in note and "new.py" not in note and "沒有產品入口可量" in note, \
        "只報個數不列檔名（檔名會跟對帳閘的欠帳檔名混淆）"
    real = subprocess.run

    def broken(args, **kw):
        if str(rph.TOOL) in args:
            return subprocess.CompletedProcess(args, 1, b"READING_PATH FAIL reason=git archive failed\n", b"")
        return real(args, **kw)

    _write(root, {"y.py": _BODY.format("b") + "\n"})
    note = _note(_state(_mf(root / "y.py")), worker_run=broken)
    assert "量尺失敗：READING_PATH FAIL reason=git archive failed" in note and "手動" not in note and "--before" not in note


def test_worker_timeout_says_why_without_a_manual_command_and_the_root_is_not_measured_again(tmp_path):
    """量尺在背景預算內量不完：只附原因（不附手動指令，模型會接單去跑）；這個根之後不再量、不再起任何子行程。"""
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": _BODY.format("b") + "\n"})
    state = _state(_mf(root / "y.py"))
    note = _note(state, worker_run=_times_out_on(str(rph.TOOL)))
    assert f"背景 {rph.WORKER_BUDGET_S:g} 秒內量不完" in note and "不再量" in note, note
    assert "手動" not in note and "--before" not in note, note
    assert state["reading_path"][_SID].get("slow"), "逾時的根記下來"
    calls = []
    real = subprocess.run

    def spy(args, **kw):
        calls.append(list(args))
        return real(args, **kw)

    _write(root, {"y.py": _BODY.format("b") + "\n\n"})
    again = _note(state, run=spy)
    assert "先前背景" in again and "不再量" in again and calls == [], "逾時過的根不再起任何子行程（收尾當下與背景都不起）"


def test_budget_spent_on_git_says_timeout_and_the_root_is_not_measured_again(tmp_path):
    """背景行程裡 git 就把預算用完：附「預算在呼叫 git 時就用完」、不附手動指令，這個根同樣不再量（codex 審 698a987 BLOCK 2）。"""
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": _BODY.format("b") + "\n"})
    state = _state(_mf(root / "y.py"))
    note = _note(state, worker_run=_times_out_on("rev-parse"))
    assert "呼叫 git 時就用完" in note and "手動" not in note and state["reading_path"][_SID].get("slow"), note


def test_git_add_alone_makes_a_new_batch_and_is_measured(tmp_path):
    """只 git add、不改檔也算新的一批：第一次提示「還沒 git add」，暫存之後再收尾要真的量（codex 審 698a987 BLOCK 1）。"""
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": "from z import c\n\n\ndef b(n):\n    return c(n)\n", "z.py": _BODY.format("c")})
    state = _state(_mf(root / "y.py"), _mf(root / "z.py"))
    first = _note(state)
    assert "還沒 git add 的新檔 1 個" in first, first
    _git(root, "add", "z.py")
    second = _note(state)
    assert second and "READING_PATH DONE mode=compare" in second and "還沒 git add" not in second, second


# ─── 收尾當下不等背景、一次一個背景量測 ────────────────────────────────────────────

def test_stop_does_not_wait_for_the_worker(tmp_path):
    """收尾當下只查 git ls-files 就交工作：量尺多慢都不等（這裡的背景行程永遠不交結果），交完立刻回、不附東西。"""
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": _BODY.format("b") + "\n"})
    state = _state(_mf(root / "y.py"))
    jobs = []
    started = time.monotonic()
    note, changed = rph.reading_path_note(state, _SID, LEGACY, spawn=jobs.append)
    assert note is None and changed and len(jobs) == 1 and time.monotonic() - started < rph.STOP_GIT_BUDGET_S + 1.0
    assert rph.reading_path_note(state, _SID, LEGACY, spawn=jobs.append) == (None, True) and len(jobs) == 1, \
        "還在量：這回合又收尾一次只記 pending、不再起第二個"
    assert state["reading_path"][_SID]["pending"] is True


def test_in_flight_job_defers_the_newer_batch_until_it_reports(tmp_path):
    """量測中又改了碼：先記著；舊的那批交結果的那次收尾附上它，同時把最新的一批交出去。"""
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": _BODY.format("b") + "\n"})
    state = _state(_mf(root / "y.py"))
    jobs = []
    rph.reading_path_note(state, _SID, LEGACY, spawn=jobs.append)
    state["turn_seq"] = 6
    state["modified_files"] = [_mf(root / "y.py", 6)]
    _write(root, {"y.py": _BODY.format("b") + "\n\n"})
    assert rph.reading_path_note(state, _SID, LEGACY, spawn=jobs.append) == (None, True) and len(jobs) == 1
    first = json.loads(Path(jobs[0]).read_text(encoding="utf-8"))
    rph.write_result(Path(first["out"]), {"text": "[Guardian:ReadingPath] 第 5 回合改動對閱讀路徑的影響：舊的一批"})
    state["turn_seq"] = 7                                     # 這回合沒改碼，但有記著的一批
    note, _ = rph.reading_path_note(state, _SID, LEGACY, spawn=jobs.append)
    assert "舊的一批" in note and len(jobs) == 2 and json.loads(Path(jobs[1]).read_text(encoding="utf-8"))["turn"] == 7
    assert not Path(first["out"]).exists() and not Path(jobs[0]).exists(), "收過的工作檔與結果檔刪掉"
    assert "pending" not in state["reading_path"][_SID]


def test_worker_that_never_reports_is_given_up_with_a_reason(tmp_path):
    """背景行程超過預算加寬限還沒交結果（被中斷）：附一句原因、清掉工作，不再等。"""
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": _BODY.format("b") + "\n"})
    state = _state(_mf(root / "y.py"))
    rph.reading_path_note(state, _SID, LEGACY, spawn=lambda p: None)
    job = state["reading_path"][_SID]["job"]
    state["turn_seq"] = 6
    assert rph.reading_path_note(state, _SID, LEGACY) == (None, False), "還在預算內：不附、不動"
    job["at"] = time.time() - (rph.WORKER_BUDGET_S + rph.GRACE_S + 1)
    note, changed = rph.reading_path_note(state, _SID, LEGACY)
    assert changed and "沒交結果" in note and "可能被中斷" in note and "手動" not in note, note
    assert "job" not in state["reading_path"][_SID]


def test_spawn_failure_says_why_once(tmp_path):
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": _BODY.format("b") + "\n"})
    state = _state(_mf(root / "y.py"))

    def boom(path):
        raise OSError("no python")

    note, changed = rph.reading_path_note(state, _SID, LEGACY, spawn=boom)
    assert changed and "起不來" in note and "no python" in note and "job" not in state["reading_path"][_SID]
    assert not list(rph.JOB_DIR.glob("*.job.json")), "起不來的工作檔不留"


def test_real_background_worker_writes_the_result(tmp_path, monkeypatch):
    """真的起背景行程（本檔 --job）：脫離收尾行程跑完，照工作檔寫結果檔，下一次收尾附上。"""
    monkeypatch.setattr(rph, "_spawn_worker", REAL_SPAWN)
    loose = _write(tmp_path / "loose", APP)                   # 不在 git：背景行程只寫一句原因，不跑量尺
    state = _state(_mf(loose / "y.py"))
    assert rph.reading_path_note(state, _SID, LEGACY) == (None, True)
    out = Path(state["reading_path"][_SID]["job"]["out"])
    deadline = time.monotonic() + 60
    while not out.exists() and time.monotonic() < deadline:   # 等的是真行程做完，不是等預算用完
        time.sleep(0.1)
    note, _ = rph.reading_path_note(state, _SID, LEGACY)
    assert note and "不在 git 工作區的改檔 1 個" in note, (note, (rph.JOB_DIR / "worker.log").read_text(encoding="utf-8")
                                                           if (rph.JOB_DIR / "worker.log").exists() else "")


@pytest.fixture(autouse=True)
def _cassette(git_cassette):
    """git 子程序錄製重播（lib/git_cassette.py）：平常重播一次真實執行的紀錄、不開 git；git 互動改了 → 失敗要求
    pytest --git-record 重錄。"""
    git_cassette()
