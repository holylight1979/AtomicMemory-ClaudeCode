"""verify_verify_ledger.py：驗證帳本（H6 B1～B4）：哨兵解析、exit code 三來源、VCS 快照、帳本落檔、收據 cap、子代理不入主帳。

怎麼跑：set WG_CLAUDE_DIR=<worktree> && python -X utf8 -m pytest -q hooks/verify/verify_verify_ledger.py
固定輸入：hooks/verify/fixtures/v6/q6/（四種 Bash 輸出＋fixture 詞表）。
反例：小寫 `x_check pass`／散文「測試通過」／`PASSED` 字尾不命中；exit≠0 的 PASS 落帳 verdict=PASS exit=1（對帳閘不認）；
      agent_id 非空只落 <sid>.agents.jsonl、不進 state 收據；非 VCS 目錄快照回空。
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
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_verify_ledger as vl  # noqa: E402
import wg_evasion as ev  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402

FIX = HOOKS_DIR / "verify" / "fixtures" / "v6" / "q6"
_SID = "sid-ledger"


def _fx(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


# ─── B1 哨兵：三種 verdict、自訂 regex、反例 ─────────────────────────────

def test_default_regex_matches_existing_replay_guard_output():
    """REPLAY_GUARD_CHECK 既有輸出直接命中（B1 完成條件）。"""
    got = vl.parse_sentinels(_fx("pass_exit0.txt"))
    assert got == [{"name": "REPLAY_GUARD_CHECK", "verdict": "PASS", "line": "REPLAY_GUARD_CHECK PASS", "kv": {}}]


def test_three_verdicts_and_measure_done_kv():
    text = "A_CHECK PASS\nB_CHECK FAIL\nC_CHECK DONE\n" + _fx("done_measure.txt")
    got = vl.parse_sentinels(text)
    assert [(s["name"], s["verdict"]) for s in got] == [
        ("A_CHECK", "PASS"), ("B_CHECK", "FAIL"), ("C_CHECK", "DONE"), ("REFIX_CHURN", "DONE")]
    assert got[3]["kv"] == {"vcs": "git", "commits": "40", "fix": "7", "files_refixed": "2"}


def test_custom_regex_maps_pytest_summary():
    rules = vl.compile_sentinel_rules([
        {"regex": r"^(?P<verdict>\d+ (?:passed|failed))", "name": "PYTEST",
         "verdict_map": {"passed": "PASS", "failed": "FAIL"}},
        {"regex": "([unclosed", "name": "BAD"},   # 壞 regex 跳過不炸
    ])
    assert len(rules) == 1
    assert [(s["name"], s["verdict"]) for s in vl.parse_sentinels("3 passed in 0.12s\n", rules)] == [("PYTEST", "PASS")]
    assert [(s["name"], s["verdict"]) for s in vl.parse_sentinels("2 failed, 1 passed in 0.5s\n", rules)] == [("PYTEST", "FAIL")]


def test_counterexamples_lowercase_prose_passed_suffix_do_not_match():
    """反例：小寫、散文、`PASSED` 字尾、句中出現都不算哨兵。"""
    assert vl.parse_sentinels(_fx("no_sentinel.txt")) == []
    assert vl.parse_sentinels("note: FOO_CHECK PASS mid-line\n") == []
    assert vl.parse_sentinels("") == []


def test_same_line_only_once():
    assert len(vl.parse_sentinels("X_CHECK PASS\nX_CHECK PASS\n")) == 1


# ─── exit code 三來源 ──────────────────────────────────────────────────

@pytest.mark.parametrize("resp,expected", [
    ({"stdout": "ok", "exit_code": 2}, 2),
    ({"stdout": "ok", "returncode": "3"}, 3),
    ("Error: Exit code 1\nFOO_CHECK PASS\n", 1),            # 實機非零 exit：整包字串
    ({"stdout": "ok", "stderr": "", "interrupted": False}, None),  # 實機成功：dict 無 exit 欄 → None（不當零）
    ({"stdout": "Exit code 127\n", "stderr": ""}, 127),
    (None, None),
])
def test_exit_code_three_sources(resp, expected):
    assert vl.exit_code_of(resp) == expected


def test_response_text_handles_dict_and_str():
    assert "FOO_CHECK PASS" in vl.response_text(_fx("pass_exit1.txt"))
    assert vl.response_text({"stdout": "a", "stderr": "b"}) == "a\nb"


# ─── B2 VCS 快照 ────────────────────────────────────────────────────────

def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / "a.py").write_text("x=1\n", encoding="utf-8", newline="\n")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    return root


def test_snapshot_rev_matches_git_and_dirty_hash_tracks_stat(repo):
    """rev 對得上 git、dirty 雜湊跟著 stat 變；時限給寬（機器忙時 git 會超過預設 1 秒，那是 024a 那案測的行為）。"""
    state: dict = {}
    f = str(repo / "a.py")
    snap = vl.vcs_snapshot(str(repo), [f], state, budget_s=10.0, subprocess_s=5.0)
    assert len(snap) == 1 and snap[0]["kind"] == "git" and snap[0]["truncated"] is False
    assert snap[0]["rev"] == _git(repo, "rev-parse", "--short", "HEAD")
    h1 = snap[0]["dirty"]
    assert h1 and h1 == vl.dirty_hash(repo, [f])[0]
    time.sleep(0.02)
    (repo / "a.py").write_text("x=22\n", encoding="utf-8", newline="\n")
    assert vl.dirty_hash(repo, [f])[0] != h1
    assert vl.dirty_hash(repo, []) == ("", False)


def test_024a_rev_timeout_marks_truncated_with_reason(repo, monkeypatch):
    """024a：取 rev 的子行程逾時（整體預算還沒到）→ 該筆 truncated=True、why 說取不到 rev，dirty 照算；
    替身：rev 指令換成睡 3 秒的 python，子行程上限 0.3 秒，走真的 _run_rev 逾時路徑。配對：取得到時照舊 False。"""
    monkeypatch.setattr(vl, "_rev_cmd", lambda kind, root: [sys.executable, "-c", "import time; time.sleep(3)"])
    f = str(repo / "a.py")
    snap = vl.vcs_snapshot(str(repo), [f], {}, budget_s=10.0, subprocess_s=0.3)
    assert snap and snap[0]["rev"] == "" and snap[0]["truncated"] is True
    assert "取不到 git rev" in snap[0].get("why", "") and snap[0]["dirty"]
    snap = vl.vcs_snapshot(str(repo), [f], {}, budget_s=10.0, _rev=lambda k, r, t: "abc1234")
    assert snap and snap[0]["rev"] == "abc1234" and snap[0]["truncated"] is False


def test_026_budget_exhausted_before_rev_says_why(repo):
    """026（WARN）：取 rev 之前整體預算就已耗盡 → truncated=True 而且 why 說原因（時鐘替身：起點 0、進入取 rev 前 2 秒、預算 1.5 秒）。"""
    ticks = iter([0.0] + [2.0] * 50)
    snap = vl.vcs_snapshot(str(repo), [str(repo / "a.py")], {}, budget_s=1.5, _rev=lambda k, r, t: "abc1234",
                           _clock=lambda: next(ticks))
    assert snap and snap[0]["truncated"] is True and "還沒取 rev 就已耗盡預算" in snap[0].get("why", "")


def test_snapshot_uses_rev_cache_within_60s(repo):
    state: dict = {}
    calls = []

    def fake_rev(kind, root, timeout):
        calls.append(kind)
        return "abc1234"

    vl.vcs_snapshot(str(repo), [], state, _rev=fake_rev)
    vl.vcs_snapshot(str(repo), [], state, _rev=fake_rev)
    assert calls == ["git"]
    assert state["vcs_rev_cache"][str(repo).replace("\\", "/")]["rev"] == "abc1234"


def test_snapshot_marks_truncated_when_rev_sleeps_past_budget(repo):
    clock = [0.0]

    def fake_rev(kind, root, timeout):
        clock[0] += 2.0            # 模擬子行程睡 2 s（超過 1.5 s 預算）
        return "deadbee"

    snap = vl.vcs_snapshot(str(repo), [], {}, budget_s=1.5, _rev=fake_rev, _clock=lambda: clock[0])
    assert snap[0]["truncated"] is True and snap[0]["rev"] == "deadbee"


def test_snapshot_non_vcs_dir_is_empty(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert vl.vcs_snapshot(str(plain), [str(plain / "x.txt")], {}) == []


# ─── B3 帳本與收據 ───────────────────────────────────────────────────────

def test_append_ledger_writes_lf_jsonl(tmp_path):
    p = vl.append_verify_ledger(_SID, {"a": 1, "中": "文"}, base_dir=tmp_path)
    assert p == tmp_path / "verify-ledger" / f"{_SID}.jsonl"
    raw = p.read_bytes()
    assert b"\r\n" not in raw and json.loads(raw.decode("utf-8")) == {"a": 1, "中": "文"}


def test_receipt_cap_50_and_turn_filter():
    state: dict = {}
    for i in range(60):
        vl.record_receipt(state, _SID, {"turn_seq": i % 7, "sentinels": [], "exit_code": None})
    assert len(state["verify_receipts"][_SID]) == 50
    assert state["verify_receipts"][_SID][0]["turn_seq"] == 10 % 7
    this = vl.ledger_entries_this_turn(state, _SID, 3)
    assert this and all(r["turn_seq"] == 3 for r in this)
    assert vl.ledger_entries_this_turn(state, "other", 3) == []
    state["turn_prompts_seq"] = 2                     # 044：使用者在 turn 2 打字、同伴訊息到 turn 3 → turn 2、3 都是本回合
    assert {r["turn_seq"] for r in vl.ledger_entries_this_turn(state, _SID, 3)} == {2, 3}


# ─── B4 post_tool_use：Bash／PowerShell 落帳、PASS 且 exit≠0、子代理不入主帳 ──

def _drive(monkeypatch, tmp_path, tool_name, command, resp, agent_id="", turn_seq=4):
    state = {"turn_seq": turn_seq, "session": {"cwd": str(tmp_path)}}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    inp = {"session_id": _SID, "tool_name": tool_name, "tool_input": {"command": command},
           "tool_response": resp, "cwd": str(tmp_path)}
    if agent_id:
        inp["agent_id"] = agent_id
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}})
    return state


def test_powershell_sentinel_lands_in_ledger_and_state(monkeypatch, tmp_path):
    state = _drive(monkeypatch, tmp_path, "PowerShell", "python x.py", _fx("pass_exit0.txt"))
    rec = state["verify_receipts"][_SID][0]
    assert rec["tool"] == "PowerShell" and rec["turn_seq"] == 4
    assert rec["sentinels"] == [{"name": "REPLAY_GUARD_CHECK", "verdict": "PASS", "kv": {}}] and rec["exit_code"] is None
    assert rec["seq"] == 1 and rec["project_root"] == ""
    line = json.loads((tmp_path / "verify-ledger" / f"{_SID}.jsonl").read_text(encoding="utf-8"))
    for key in ("at", "session_id", "agent_id", "turn_seq", "tool", "cmd", "cwd", "project_root",
                "sentinels", "exit_code", "vcs", "modified_files_turn", "spec"):
        assert key in line
    assert line["vcs"] == [] and line["agent_id"] == ""


def test_pass_with_nonzero_exit_recorded_as_pass_exit1(monkeypatch, tmp_path):
    """B4 完成條件：PASS 且 exit≠0 落帳 verdict=PASS exit=1（對帳閘那邊不認）。"""
    state = _drive(monkeypatch, tmp_path, "Bash", "python x.py", _fx("pass_exit1.txt"))
    rec = state["verify_receipts"][_SID][0]
    assert rec["exit_code"] == 1 and rec["sentinels"][0]["verdict"] == "PASS"
    assert vl.pass_receipts([rec]) == []


def test_bash_without_sentinel_and_not_test_cmd_writes_nothing(monkeypatch, tmp_path):
    state = _drive(monkeypatch, tmp_path, "Bash", "ls -la", {"stdout": "a.py\n", "stderr": ""})
    assert "verify_receipts" not in state
    assert not (tmp_path / "verify-ledger").exists()


def test_subagent_receipt_not_in_main_ledger(monkeypatch, tmp_path):
    state = _drive(monkeypatch, tmp_path, "Bash", "python x.py", _fx("pass_exit0.txt"), agent_id="agent-1")
    assert vl.receipts_of(state, _SID) == []                                        # 主 session 的收據不混入子代理的
    assert len(vl.receipts_of(state, vl.agent_receipt_key(_SID, "agent-1"))) == 1     # 005：子代理自己的另放（SubagentStop 對帳用）
    assert not (tmp_path / "verify-ledger" / f"{_SID}.jsonl").exists()
    side = tmp_path / "verify-ledger" / f"{_SID}.agents.jsonl"
    assert side.exists() and json.loads(side.read_text(encoding="utf-8"))["agent_id"] == "agent-1"


def test_ledger_disabled_by_config(monkeypatch, tmp_path):
    state = {"turn_seq": 1}
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    assert pt._track_sentinels(state, {"tool_response": _fx("pass_exit0.txt")}, "python x.py", "Bash",
                               {"verify_ledger": {"enabled": False}}, _SID) is False


# ─── 宣稱詞表（fixture 詞表）────────────────────────────────────────────

@pytest.fixture()
def phrases():
    return ev.compile_claim_phrases(FIX / "phrases.json")


@pytest.mark.parametrize("text,fixed,measured,tried", [
    ("閘的問題修好了，三案綠。", True, False, False),
    ("使用者說已修正，我沒驗。", False, False, False),        # BLOCK 2：第三方主語（轉述）不算
    ("it is not fixed yet", False, False, False),            # BLOCK 2：英文否定
    ("量過了嗎？", False, False, False),                     # BLOCK 2：疑問
    ("A 已修好，B 尚未修好。", True, False, False),            # BLOCK 2：否定只取消同子句
    ("codex 顯示已修復，但我覺得還沒。", False, False, False),  # BLOCK 2：轉述＋否定
    ("這條我修好了；那條 not fixed", True, False, False),      # BLOCK 2：子句各自判
    ("還沒修好但 B 已修好", True, False, False),                # 003-1：轉折詞後另起子句
    ("我請 codex 跑了測試後已修正", True, False, True),         # 003-1：有「我」→ 自己的宣稱（修好＋試過都算）
    ("codex 跑了測試", False, False, False),                   # 003-1：第三方開頭、無我／本／已 → 轉述
    ("使用者說已修正", False, False, False),                   # 003-1：仍 False
    ("還沒修好，先記下。", False, False, False),
    ("要怎麼修好這個？", False, False, False),
    ("我量了三次，平均 120 ms。", False, True, False),
    ("還沒量，下一步再量。", False, False, False),
    ("我跑了 pytest，全綠。", False, False, True),
    ("請你跑一次看看。", False, False, False),
    ("hook 回「修好」這個詞時要擋", False, False, False),   # 引號內不算宣稱
])
def test_claim_detection_with_fixture_phrases(phrases, text, fixed, measured, tried):
    assert vl.claims_fixed(text, phrases) is fixed
    assert vl.claims_measured(text, phrases) is measured
    assert vl.claims_tried(text, phrases) is tried


def test_default_claim_phrases_fallback_present():
    assert set(ev.CLAIM_RES) >= {"fixed", "fixed_exclude", "measured", "measured_exclude", "tried", "tried_exclude"}
    assert vl.claims_fixed("已修復")


def test_tried_claim_without_exec_accepts_tool_names_or_receipts(phrases):
    txt = "我跑了測試"
    assert vl.tried_claim_without_exec(txt, [], ["Bash", "PowerShell"], (), phrases) is True
    assert vl.tried_claim_without_exec(txt, ["Read", "Bash"], ["Bash", "PowerShell"], (), phrases) is False
    assert vl.tried_claim_without_exec(txt, [], ["Bash"], [{"turn_seq": 1}], phrases) is False
    assert vl.tried_claim_without_exec("還沒跑", [], ["Bash"], (), phrases) is False

# ─── BLOCK 7：vcs_snapshot 整體 deadline（找 root、子行程、stat 迴圈都受管；檔數上限 200）────

def test_snapshot_deadline_covers_slow_stat(repo):
    """注入 55 ms stat 延遲×100 檔：truncated，且總耗時不超過「預算＋一次檢查間隔」（每 10 檔才查 deadline，最多多跑 10 次
    stat；再留 0.3 s 給排程抖動）。沒停的話 100 檔要 5.5 s。"""
    files = []
    for i in range(100):
        p = repo / f"f{i}.py"
        p.write_text("x\n", encoding="utf-8", newline="\n")
        files.append(str(p))

    def slow_stat(path):
        time.sleep(0.055)
        return __import__("os").stat(path)

    t0 = time.monotonic()
    snap = vl.vcs_snapshot(str(repo), files, {}, budget_s=1.5, _rev=lambda k, r, t: "abc1234", _stat=slow_stat)
    elapsed = time.monotonic() - t0
    assert elapsed < 2.35, elapsed                 # 1.5 s 預算＋10 檔×55 ms 檢查間隔＋0.3 s 排程餘量（固定數字：間隔被調大要紅）
    assert snap and snap[0]["truncated"] is True


def test_snapshot_file_cap_200(repo):
    files = [str(repo / f"g{i}.py") for i in range(250)]
    h, trunc = vl.dirty_hash(repo, files)
    assert trunc is True and h


def test_snapshot_subprocess_timeout_is_remaining_budget(repo):
    seen = []

    def fake_rev(kind, root, timeout):
        seen.append(timeout)
        return "abc"

    clock = [0.0]
    vl.vcs_snapshot(str(repo), [], {}, budget_s=1.5, _rev=fake_rev, _clock=lambda: clock[0])
    assert seen == [1.0]
    clock = [0.0]

    def tick():
        clock[0] += 0.6       # 每次看錶走 0.6 s：deadline 起於第一次看錶，子行程前剩 0.9 → timeout 要 ≤ 剩餘
        return clock[0]

    seen.clear()
    vl.vcs_snapshot(str(repo), [], {}, budget_s=1.5, _rev=fake_rev, _clock=tick)
    assert seen and seen[0] < 1.0


# ─── BLOCK 5：run_verify.py 失敗印 FAIL 且 exit 1；量尺閘看 exit 與 failed= ─────────────

def test_run_verify_source_prints_fail_and_exit_1():
    src = (HOOKS_DIR.parent / "run_verify.py").read_text(encoding="utf-8")
    assert 'verdict = "DONE" if exit_code == 0 and n_failed == 0 else "FAIL"' in src
    assert 'if verdict == "FAIL" and exit_code == 0:\n    exit_code = 1' in src
    assert ev.is_test_command("python -X utf8 run_verify.py") and ev.is_test_command("python run_verify.py --json")


def test_run_verify_help_prints_usage_without_running():
    r = subprocess.run([sys.executable, "-X", "utf8", str(HOOKS_DIR.parent / "run_verify.py"), "--help"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    assert r.returncode == 0 and "usage:" in r.stdout and "--json" in r.stdout
    assert "VERIFY_CHECK" not in r.stdout + r.stderr   # 沒有跑測試


def test_done_receipt_with_failed_count_or_nonzero_exit_not_ok():
    good = {"turn_seq": 5, "cmd": "python -X utf8 run_verify.py", "exit_code": 0, "env": {},
            "sentinels": [{"name": "VERIFY_CHECK", "verdict": "DONE", "kv": {"cases": "10", "failed": "0"}}]}
    bad_kv = {**good, "sentinels": [{"name": "VERIFY_CHECK", "verdict": "DONE", "kv": {"cases": "10", "failed": "2"}}]}
    bad_exit = {**good, "exit_code": 1}
    fail_verdict = {**good, "sentinels": [{"name": "VERIFY_CHECK", "verdict": "FAIL", "kv": {"failed": "2"}}]}
    assert vl.done_receipts([good]) == [good]
    assert vl.done_receipts([bad_kv]) == [] and vl.done_receipts([bad_exit]) == [] and vl.done_receipts([fail_verdict]) == []
    assert vl.done_receipts([bad_kv], require_ok=False) == [bad_kv]


def test_run_verify_fail_output_creates_failing_entry(monkeypatch, tmp_path):
    """run_verify 失敗輸出（哨兵 FAIL、dict 無 exit 欄）→ TestFailGate 建紅測。"""
    state = _drive(monkeypatch, tmp_path, "Bash", "python -X utf8 run_verify.py",
                   {"stdout": "....F\nVERIFY_CHECK FAIL cases=10 failed=1\n", "stderr": "", "interrupted": False})
    assert state["failing_tests"] and state["failing_tests"][0]["session_id"] == _SID
    assert state["verify_receipts"][_SID][0]["sentinels"][0]["kv"] == {"cases": "10", "failed": "1"}


# ─── BLOCK 3：PASS 收據要對得上改的檔／verify glob／量尺指令 ─────────────────────────

def test_receipt_relates_rules_fixed_in_002_returned():
    """003-2「對得上」定死：stem 整詞／test_<stem>／整體驗證／量尺／verify 目錄算；verify glob 單獨、子字串、含 cd 不算。"""
    globs = vl.RECONCILE_DEFAULTS["verify_case_globs"]
    a = [r"c:\proj\src\a.py"]
    assert vl.receipt_relates({"env": {}, "cmd": "pytest tests/test_a.py"}, a, globs) is True              # (b) test_<stem>
    assert vl.receipt_relates({"env": {}, "cmd": "pytest tests/test_b.py"}, a, globs) is False             # verify glob 單獨不算
    assert vl.receipt_relates({"env": {}, "cmd": "python check_beta.py"}, a, globs) is False               # 子字串不算
    assert vl.receipt_relates({"env": {}, "cmd": "pytest -q"}, a, globs) is True                           # (c) 無檔名 pytest
    assert vl.receipt_relates({"env": {}, "cmd": "python -m pytest -q -p no:cacheprovider"}, a, globs) is True
    assert vl.receipt_relates({"env": {}, "cmd": "python -X utf8 run_verify.py"}, a, globs) is True        # (c) run_verify
    assert vl.receipt_relates({"env": {}, "cmd": "python -X utf8 run_verify.py --json"}, a, globs) is False  # 017b 規則 9：帶參數不算整體
    assert vl.receipt_relates({"env": {}, "cmd": "python measure.py"}, a, globs, ["python measure.py"]) is True   # (c) 量尺
    assert vl.receipt_relates({"env": {}, "cmd": "python tools/replay-guard.py pre"}, a, globs) is False
    assert vl.receipt_relates({"env": {}, "cmd": "cd other; python -m pytest -q"}, a, globs) is False      # 003-4 含 cd 不算
    assert vl.receipt_relates({"env": {}, "cmd": "cd x && pytest -q", "root_uncertain": True}, a, globs) is False
    # 017：可解析的指令看斷詞判換目錄，PostToolUse 用原字串標的 root_uncertain 不推翻它（cd 只在註解裡）
    assert vl.receipt_relates({"env": {}, "cmd": "pytest -q # cd x", "root_uncertain": True}, a, globs) is True
    mods = [r"c:\proj\hooks\wg_x.py"]
    assert vl.receipt_relates({"env": {}, "cmd": "python -m pytest hooks/verify/verify_wg_x.py"}, mods, globs) is True   # (b) verify_<stem>
    assert vl.receipt_relates({"env": {}, "cmd": "python -m pytest hooks/verify/verify_other.py"}, mods, globs) is True  # (d) 改檔所在的 verify 目錄
    assert vl.receipt_relates({"env": {}, "cmd": "python -m pytest lib/verify/verify_other.py"}, mods, globs) is False
    assert vl.receipt_relates({"env": {}, "cmd": "python tools/wg_x.py --check"}, mods, globs) is True        # (a) stem 整詞
    assert vl.receipt_relates({"env": {}, "cmd": "python tools/wg_xy.py --check"}, mods, globs) is False      # 整詞邊界
    assert vl.has_cd("cd /c && pytest") and vl.has_cd("pushd x; pytest") and vl.has_cd("Set-Location x; pytest")
    assert not vl.has_cd("python cdx.py") and not vl.has_cd("pytest --cd-flag")


def test_receipt_relates_root_must_match():
    """缺口 3：root 參數真的用上，收據根（project_root，沒有就 cwd）要等於改檔根或在它之下。"""
    mods = ["C:/Demo/src/widget.py"]
    r = {"cmd": "python tests/test_widget.py", "project_root": "C:/Other", "cwd": "C:/Other", "env": {}}
    assert vl.receipt_relates(r, mods, (), (), "C:/Demo") is False                                     # 別的根
    demo = {**r, "project_root": "C:/Demo", "cwd": "C:/Demo"}
    assert vl.receipt_relates(demo, mods, (), (), "C:/Demo") is True
    # 017：相對路徑照 cwd 解析，從 C:/Other 跑 `python tests/test_widget.py` 跑的是 C:/Other 的檔，project_root 寫什麼都不算
    assert vl.receipt_relates({**r, "project_root": "C:/Demo"}, mods, (), (), "C:/Demo") is False
    assert vl.receipt_relates({**r, "project_root": "", "cwd": "C:/Demo/sub"}, mods, (), (), "C:/Demo") is True   # 沒 project_root 用 cwd
    assert vl.receipt_relates({**r, "project_root": "C:/Demo2"}, mods, (), (), "C:/Demo") is False     # 字首相同不等於同一棵樹
    assert vl.receipt_relates({**r, "project_root": "C:/"}, mods, (), (), "C:/Demo") is True           # 未解 1：收據根在上層也算
    assert vl.receipt_relates(demo, mods, (), (), "C:/Demo/sub") is True
    assert vl.receipt_relates({**r, "project_root": "C:/Demo/sub2"}, mods, (), (), "C:/Demo/sub") is False   # 互不包含才擋
    assert vl.receipt_relates({"env": {}, "cmd": r["cmd"]}, mods, (), (), "C:/Demo") is True                      # 收據沒根資訊 → 照舊
    assert vl.receipt_relates(r, mods, (), (), lambda p: None) is True                                 # 改檔根不可判定 → 照舊
    assert vl.receipt_relates({**r, "cmd": "python -m pytest -q"}, mods, (), (), "C:/Demo") is False   # 整體驗證也要同根
    assert vl.receipt_relates({"env": {}, "cmd": "python -m pytest -q", "project_root": "C:/Other"}, [], (), (), "C:/Demo") is True   # 沒改檔不比根


def test_file_root_of_uses_project_root_then_vcs_fallback(tmp_path):
    root = tmp_path / "p"
    (root / ".git").mkdir(parents=True)
    deep = root / "a" / "b" / "c" / "d" / "x.py"
    deep.parent.mkdir(parents=True)
    assert vl.file_root_of(str(root / "x.py")) == str(root)                  # project_root 判得到
    assert vl.file_root_of(str(deep)) == str(root)                           # 第 5 層：project_root 舊規則找不到，退 VCS 根
    lone = tmp_path / "lone" / "x.py"
    lone.parent.mkdir()
    assert vl.file_root_of(str(lone)) is None                                # 沒任何根 → 不可判定


def test_vcs_root_of_never_returns_home_or_drive_root(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".git").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    assert vl.vcs_root_of(str(home / "a" / "x.py")) is None
    proj = home / "proj"
    (proj / ".git").mkdir(parents=True)
    assert vl.vcs_root_of(str(proj / "a" / "x.py")) == proj                  # 家目錄下的專案照常
    monkeypatch.setattr(vl, "find_vcs_root", lambda start: ("git", Path(Path(start).anchor)))
    assert vl.vcs_root_of(str(tmp_path / "x" / "y.py")) is None              # 磁碟根不算
    assert vl.vcs_root_of("rel/x.py") is None


def test_related_pass_receipts_marks_order_and_root_reasons():
    mods = ["C:/Demo/src/widget.py"]
    rec = {"cmd": "python tests/test_widget.py", "sentinels": [{"verdict": "PASS"}], "exit_code": 0,
           "turn_seq": 5, "seq": 3, "project_root": "C:/Demo", "env": {}}
    edits = {mods[0]: {"path": mods[0], "last_seq": 5, "last_turn_seq": 5}}
    related, unrelated = vl.related_pass_receipts([rec], 5, mods, (), (), "C:/Demo", edits)
    assert related == [] and unrelated[0]["before_edit"] == mods
    related, unrelated = vl.related_pass_receipts([{**rec, "seq": 6}], 5, mods, (), (), "C:/Demo", edits)
    assert len(related) == 1 and unrelated == []
    related, unrelated = vl.related_pass_receipts([{**rec, "seq": 6, "project_root": "C:/Other"}], 5, mods, (), (), "C:/Demo", edits)
    assert related == [] and unrelated[0]["other_root"] is True

# ─── 003-3：at 同秒比 seq；不同時區 offset 先轉 UTC ─────────────────────────────

def test_receipt_after_same_second_uses_seq_and_normalizes_tz():
    edit_at = "2026-10-08T10:00:05+08:00"
    assert vl._receipt_after({"at": edit_at, "seq": 7}, edit_at, 6, 5) is True
    assert vl._receipt_after({"at": edit_at, "seq": 5}, edit_at, 6, 5) is False
    assert vl._receipt_after({"at": edit_at}, edit_at, 6, 5) is False                       # 同秒無 seq → 不算晚於
    assert vl._receipt_after({"at": "2026-10-08T02:00:06+00:00"}, edit_at, None, 5) is True   # UTC 02:00:06 ＝ +08 10:00:06
    assert vl._receipt_after({"at": "2026-10-08T02:00:04Z"}, edit_at, None, 5) is False


def test_ledger_marks_root_uncertain_when_cmd_has_cd(monkeypatch, tmp_path):
    state = _drive(monkeypatch, tmp_path, "Bash", "cd /c && python -X utf8 run_verify.py", _fx("done_measure.txt"))
    rec = state["verify_receipts"][_SID][0]
    assert rec["root_uncertain"] is True
    line = json.loads((tmp_path / "verify-ledger" / f"{_SID}.jsonl").read_text(encoding="utf-8"))
    assert line["root_uncertain"] is True


# ─── 017 規則 4：收據存完整指令（截斷後接在尾段的假哨兵也看得到） ─────────────────────────────

_RUN_ROW = {"part_short": "hook 共用模組層", "measure": {"method": "全量 verify", "cmd": "python -X utf8 run_verify.py",
                                                     "threshold": "全綠"}}
_DONE_OUT = {"stdout": "VERIFY_CHECK DONE cases=1 failed=0\n", "stderr": ""}


def _measure_gate_on(receipts, tmp_path):
    mod = {"path": str(tmp_path / "hooks" / "x.py"), "session_id": _SID, "turn_seq": 4, "last_turn_seq": 4,
           "last_at": "2020-01-01T00:00:00+00:00", "last_seq": 0}
    return vl.measure_gate_reason([mod], receipts, 4, lambda p: (tmp_path, _RUN_ROW), vl.MEASURE_DEFAULTS,
                                  chains_of=lambda r: {}, self_runs=lambda: [])[0]


def test_017_long_command_through_track_sentinels(monkeypatch, tmp_path):
    """前段 `量尺 > $null 2>&1` 補空白到 200 字、尾段 `; Write-Output "VERIFY_CHECK DONE …"`，經 PostToolUse 落帳 → 量尺閘不認；
    誠實的長指令（超過 200 字、量尺在最後）經同一條路 → 認得。舊碼收據只存前 200 字，假的變成只剩量尺而被認。"""
    head = "python -X utf8 run_verify.py > $null 2>&1"
    fake = head + " " * (200 - len(head)) + '; Write-Output "VERIFY_CHECK DONE cases=1 failed=0"'
    honest = '$env:WG_CLAUDE_DIR="C:\\' + "x" * 190 + '"; python -X utf8 run_verify.py'
    for cmd, blocked in ((fake, True), (honest, False)):
        state = _drive(monkeypatch, tmp_path, "PowerShell", cmd, _DONE_OUT)
        reason = _measure_gate_on(state["verify_receipts"][_SID], tmp_path)
        assert (reason is not None) is blocked, (cmd[:40], reason)
        rec = state["verify_receipts"][_SID][-1]
        assert len(cmd) > 200 and rec["cmd"] == cmd and rec["cmd_full"] is True
    assert "參數裡寫了哨兵字樣" in _measure_gate_on(_drive(monkeypatch, tmp_path, "PowerShell", fake, _DONE_OUT)
                                             ["verify_receipts"][_SID], tmp_path)


def test_017_legacy_truncated_receipt_is_not_evidence(tmp_path):
    """升級前的收據（沒有 cmd_full）滿 200 字 → 不知道後面還接了什麼 → 不算，訊息叫人重跑；不滿 200 字的舊收據照算。"""
    base = {"turn_seq": 4, "tool": "Bash", "exit_code": 0, "at": "2026-10-12T02:00:00+00:00", "cwd": str(tmp_path), "env": {},
            "sentinels": [{"name": "VERIFY_CHECK", "verdict": "DONE", "kv": {"cases": "1", "failed": "0"}}]}
    full = ("python -X utf8 run_verify.py" + " " * 200)[:200]
    reason = _measure_gate_on([{**base, "cmd": full}], tmp_path)
    assert reason and "只存前 200 字" in reason
    assert _measure_gate_on([{**base, "cmd": full[:199]}], tmp_path) is None
    assert _measure_gate_on([{**base, "cmd": full, "cmd_full": True}], tmp_path) is None
