"""verify_reading_path_hook.py：收尾檢核附「這次對閱讀路徑的影響」（hooks/wg_reading_path.py）。

正例：改碼回合在真 git 夾具上跑真量尺，附尾行＋可評級與否＋變差／新增最差一條；同一批輸入只附一次；session commit 過
      → before 是第一筆的父提交；部位表「讀路徑樣本」給的入口優先。
反例：沒改程式碼不附；不在 git、還沒 commit、量尺失敗、逾時、只改測試檔、還沒 git add 的新檔 → 各附一句原因；
      逾時過的根之後不再自動量（不再起量尺子行程）。子行程都帶 CREATE_NO_WINDOW。
真 Stop 入口（改碼附段落、沒改碼不附、逾時附原因）在 verify_stop_reconcile.py 的 driven 夾具。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_reading_path_hook.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

import wg_reading_path as rph  # noqa: E402

OFFICIAL_BUDGET = rph.BUDGET_S   # 夾具把預算放寬之前的正式值

_SID = "sid-rp"
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


@pytest.fixture(autouse=True)
def _roomy(monkeypatch):
    monkeypatch.setattr(rph, "BUDGET_S", 120.0)   # 真量尺在忙碌的機器上也量得完；逾時案自己縮


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


# ─── 真量尺（真 git 夾具） ─────────────────────────────────────────────────────

def test_code_change_turn_attaches_tail_ratable_and_worst_once(tmp_path):
    root = _repo(tmp_path / "r")
    _write(root, WORSE)
    _git(root, "add", "z.py")
    state = _state(_mf(root / "y.py"), _mf(root / "z.py"))
    note = rph.reading_path_note(state, _SID, {})
    assert note and note.startswith("[Guardian:ReadingPath]"), note
    assert "READING_PATH DONE mode=compare" in note and "可評級：" in note
    assert "[新增]" in note and "z.py::c" in note, note
    head = _git(root, "rev-parse", "--short=12", "HEAD")
    assert f"before={head}" in note
    assert rph.reading_path_note(state, _SID, {}) is None, "同一批輸入只附一次"
    _write(root, {"z.py": _BODY.format("c") + "\n"})
    assert rph.reading_path_note(state, _SID, {}), "又改了 → 再量再附"


def test_no_code_change_this_turn_attaches_nothing(tmp_path):
    root = _repo(tmp_path / "r")
    assert rph.reading_path_note(_state(_mf(root / "notes.md")), _SID, {}) is None
    assert rph.reading_path_note(_state(_mf(root / "y.py", 3)), _SID, {}) is None, "前幾回合改的不算這回合改碼"


def test_session_commit_moves_before_to_the_first_commits_parent(tmp_path):
    root = _repo(tmp_path / "r")
    base = _git(root, "rev-parse", "--short=12", "HEAD")
    _write(root, WORSE)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "session")
    first = _git(root, "rev-parse", "HEAD")
    key = rph._git_root_of(str(root / "y.py"))[0]
    note = rph.reading_path_note(_state(_mf(root / "y.py"), committed_new_code={key: {"shas": [first]}}), _SID, {})
    assert f"before={base}" in note and "[新增]" in note, note


def test_overview_map_sample_gives_the_entry(tmp_path, monkeypatch):
    root = _repo(tmp_path / "r", {**APP, "hooks/run.py": "from x import a\n\n\ndef go():\n    return a(1) + 1\n"})
    _write(root, {".claude/overview-map.md": "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 讀路徑樣本 |\n|---|---|---|---|---|\n"
                                             "| `hooks/` | 入口 | 無 | 無 | settings.json > hooks/run.py > x.py |\n"})
    seen = []
    real = subprocess.run
    monkeypatch.setattr(rph, "_python_exe", lambda: sys.executable)

    def spy(args, **kw):
        seen.append((list(args), kw.get("creationflags")))
        return real(args, **kw)

    _write(root, {"x.py": _BODY.format("a") + "\n"})
    rph.reading_path_note(_state(_mf(root / "x.py")), _SID, {}, run=spy)
    tool = next(a for a, _ in seen if str(rph.TOOL) in a)
    entries = [tool[i + 1] for i, v in enumerate(tool) if v == "--entry"]
    assert entries == [], "x.py 在部位表上沒給入口 → 不給 --entry，量尺自動偵測"
    seen.clear()
    _write(root, {"hooks/run.py": "from x import a\n\n\ndef go():\n    return a(2) + 1\n"})
    rph.reading_path_note(_state(_mf(root / "hooks/run.py")), _SID, {}, run=spy)
    tool = next(a for a, _ in seen if str(rph.TOOL) in a)
    assert [tool[i + 1] for i, v in enumerate(tool) if v == "--entry"] == [str(root / "hooks" / "run.py")]
    assert "--layers" in tool and "--scope" not in tool, "部位表一起交給量尺；掃描母體用預設 git"
    assert all(flag == rph._NO_WINDOW for _, flag in seen), "每個子行程都帶 CREATE_NO_WINDOW"


# ─── 量不出來就附原因 ──────────────────────────────────────────────────────────

def test_outside_git_and_no_commit_say_why(tmp_path):
    loose = _write(tmp_path / "loose", APP)
    note = rph.reading_path_note(_state(_mf(loose / "y.py")), _SID, {})
    assert "不在 git 工作區的改檔 1 個" in note and "y.py" not in note, "只報個數，不列檔名（避免和對帳閘的欠帳檔名混淆）"
    empty = tmp_path / "empty"
    _write(empty, APP)
    subprocess.run(["git", "init", "-q", str(empty)], check=True)
    _git(empty, "add", "-A")
    assert "解不出" in rph.reading_path_note(_state(_mf(empty / "y.py")), _SID, {})


def test_tool_failure_and_only_tests_and_untracked_say_why(tmp_path, monkeypatch):
    root = _repo(tmp_path / "r", {**APP, "tests/test_y.py": "def test_y():\n    assert 1\n"})
    _write(root, {"tests/test_y.py": "def test_y():\n    assert 2\n"})
    assert "只改了測試檔" in rph.reading_path_note(_state(_mf(root / "tests/test_y.py")), _SID, {})
    _write(root, {"new.py": _BODY.format("n")})
    note = rph.reading_path_note(_state(_mf(root / "new.py")), _SID, {})
    assert "還沒 git add 的新檔 1 個" in note and "new.py" not in note and "沒有產品入口可量" in note, \
        "只報個數不列檔名（檔名會跟對帳閘的欠帳檔名混淆）"
    real = subprocess.run

    def broken(args, **kw):
        if str(rph.TOOL) in args:
            return subprocess.CompletedProcess(args, 1, b"READING_PATH FAIL reason=git archive failed\n", b"")
        return real(args, **kw)

    _write(root, {"y.py": _BODY.format("b") + "\n"})
    note = rph.reading_path_note(_state(_mf(root / "y.py")), _SID, {}, run=broken)
    assert "量尺失敗：READING_PATH FAIL reason=git archive failed" in note and "手動：python" in note


def test_timeout_says_so_and_the_root_is_not_measured_again(tmp_path, monkeypatch):
    root = _repo(tmp_path / "r")
    slow = _write(tmp_path / "slowtool", {"reading-path.py": "import time\ntime.sleep(60)\n"}) / "reading-path.py"
    monkeypatch.setattr(rph, "TOOL", slow)
    monkeypatch.setattr(rph, "BUDGET_S", 8.0)   # 忙碌機器上的 git 先跑完，卡住的是假量尺
    _write(root, {"y.py": _BODY.format("b") + "\n"})
    state = _state(_mf(root / "y.py"))
    note = rph.reading_path_note(state, _SID, {})
    assert "逾時（8 秒內量不完" in note and "不再自動量" in note and "手動：python" in note, note
    calls = []
    real = subprocess.run

    def spy(args, **kw):
        calls.append(list(args))
        return real(args, **kw)

    _write(root, {"y.py": _BODY.format("b") + "\n\n"})
    again = rph.reading_path_note(state, _SID, {}, run=spy)
    assert "先前 8 秒內量不完，不再自動量" in again and not any(str(slow) in " ".join(c) for c in calls)


def test_budget_spent_on_git_says_timeout_and_the_root_is_not_measured_again(tmp_path):
    """git 本身就把預算用完（忙碌的機器）：附「逾時」與手動指令（before 用還沒解開的寫法），這個根同樣不再自動量：
    之後再改檔，連 git 子行程都不起（codex 審 698a987 BLOCK 2）。"""
    root = _repo(tmp_path / "r")
    real = subprocess.run
    calls = []

    def slow_git(args, **kw):
        calls.append(list(args))
        if "rev-parse" in args:
            raise subprocess.TimeoutExpired(args, kw.get("timeout"))
        return real(args, **kw)

    _write(root, {"y.py": _BODY.format("b") + "\n"})
    state = _state(_mf(root / "y.py"))
    note = rph.reading_path_note(state, _SID, {}, run=slow_git)
    assert "呼叫 git 時就用完" in note and "--before HEAD" in note and state["reading_path"][_SID].get("slow"), note
    calls.clear()
    _write(root, {"y.py": _BODY.format("b") + "\n\n"})
    again = rph.reading_path_note(state, _SID, {}, run=slow_git)
    assert "不再自動量" in again and "手動：python" in again and calls == [], "逾時過的根不再起任何子行程"


def test_git_add_alone_makes_a_new_batch_and_is_measured(tmp_path):
    """只 git add、不改檔也算新的一批：第一次提示「還沒 git add」，暫存之後再 Stop 要真的量（codex 審 698a987 BLOCK 1）。"""
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": "from z import c\n\n\ndef b(n):\n    return c(n)\n", "z.py": _BODY.format("c")})
    state = _state(_mf(root / "y.py"), _mf(root / "z.py"))
    first = rph.reading_path_note(state, _SID, {})
    assert "還沒 git add 的新檔 1 個" in first, first
    _git(root, "add", "z.py")
    second = rph.reading_path_note(state, _SID, {})
    assert second and "READING_PATH DONE mode=compare" in second and "還沒 git add" not in second, second


def test_the_official_budget_bounds_the_whole_call(tmp_path, monkeypatch):
    """正式預算（模組常數 3 秒）下，量尺卡住時整支在預算內收手（加啟動與收尾的餘裕 2 秒），附「逾時」。"""
    monkeypatch.setattr(rph, "BUDGET_S", OFFICIAL_BUDGET)
    root = _repo(tmp_path / "r")
    slow = _write(tmp_path / "slowtool", {"reading-path.py": "import time\ntime.sleep(60)\n"}) / "reading-path.py"
    monkeypatch.setattr(rph, "TOOL", slow)
    _write(root, {"y.py": _BODY.format("b") + "\n"})
    started = time.monotonic()
    note = rph.reading_path_note(_state(_mf(root / "y.py")), _SID, {})
    assert OFFICIAL_BUDGET == 3.0 and time.monotonic() - started < OFFICIAL_BUDGET + 2.0
    assert "逾時" in note and "手動：python" in note, note
