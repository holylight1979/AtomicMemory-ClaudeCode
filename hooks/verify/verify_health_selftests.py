"""verify_health_selftests.py：週健檢 H7（Q7）：工具自測三反例、Depends mtime、覆蓋率、--json 多 selftests 區、對帳 overflow 紅。

怎麼跑：set WG_CLAUDE_DIR=<worktree> && python -X utf8 -m pytest -q hooks/verify/verify_health_selftests.py
固定輸入：hooks/verify/fixtures/v6/q7/（預期 FAIL 的自測、壞依賴、壞接線、壞哨兵）。
反例：壞依賴（import 死）、壞接線（印別的名）、壞哨兵（小寫／PASSED 字尾）都要變紅；runtime_gate 未就緒只跳過不紅。
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
FIX = _ROOT / "hooks" / "verify" / "fixtures" / "v6" / "q7"
PY = sys.executable


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def hw(tmp_path, monkeypatch):
    mod = _load("health_weekly_selftests_ut", _ROOT / "tools" / "health-weekly.py")
    monkeypatch.setattr(mod, "MEMORY", tmp_path / "memory")
    monkeypatch.setattr(mod, "WORKFLOW", tmp_path / "workflow")
    monkeypatch.setattr(mod, "REPORT_DIR", tmp_path / "workflow" / "health-reports")
    monkeypatch.setattr(mod, "LAST_RUN", tmp_path / "workflow" / "health-last-run.json")
    (tmp_path / "workflow").mkdir()
    return mod


def _st(name, script, expected="PASS", gate=""):
    return {"name": name, "cmd": f'"{PY}" -X utf8 "{FIX / script}"', "expected": expected,
            "runtime_gate": gate, "timeout_s": 30}


# ─── Q7：登記的 selftest 綠；三反例紅 ─────────────────────────────────────

def test_expected_fail_selftest_is_green(hw, tmp_path):
    red, info, results = hw._selftests_block([_st("expect-fail", "selftest_expect_fail.py", "FAIL"),
                                              _st("plain", "selftest_pass.py", "PASS")], tmp_path)
    assert red == [] and len(results) == 2 and all(r["ok"] for r in results)
    assert results[0]["got"] == ["SELF_CHECK FAIL"] and results[0]["exit_code"] == 1


def test_bad_dependency_turns_red(hw, tmp_path):
    red, _, results = hw._selftests_block([_st("dep", "bad_dependency.py")], tmp_path)
    assert len(red) == 1 and "dep" in red[0] and "沒有任何哨兵" in red[0]
    assert results[0]["ok"] is False and "exit 1" in results[0]["detail"] and "ModuleNotFoundError" in results[0]["detail"]


def test_bad_wiring_turns_red(hw, tmp_path):
    red, _, results = hw._selftests_block([_st("wire", "bad_wiring.py")], tmp_path)
    assert len(red) == 1 and "預期 PASS" in red[0] and "SELF_CHECK FAIL" in red[0]
    assert results[0]["got"] == ["OTHER_TOOL_CHECK PASS", "SELF_CHECK FAIL"]


def test_bad_sentinel_format_turns_red(hw, tmp_path):
    red, _, results = hw._selftests_block([_st("fmt", "bad_sentinel.py")], tmp_path)
    assert len(red) == 1 and "沒有任何哨兵" in red[0] and results[0]["got"] == []


def test_runtime_gate_not_ready_is_skipped_not_red(hw, tmp_path):
    gate = f'"{PY}" -c "import sys; sys.exit(1)"'
    red, info, results = hw._selftests_block([_st("gated", "bad_dependency.py", gate=gate)], tmp_path)
    assert red == [] and results[0]["status"] == "skipped" and any("跳過" in x for x in info)


def test_timeout_turns_red(hw, tmp_path):
    st = {"name": "slow", "cmd": f'"{PY}" -c "import time; time.sleep(5)"', "expected": "PASS", "timeout_s": 0.5}
    red, _, results = hw._selftests_block([st], tmp_path)
    assert len(red) == 1 and results[0]["status"] == "timeout"


# ─── collect()：--json 多 selftests 區、last-run 多 selftests_failed ──────────

def _stub_collect_deps(hw, monkeypatch, selftests, hc=None):
    cfg = {"tool_selftests": selftests, "depends_coverage_min": 0, "provenance": {"enabled": False}}
    monkeypatch.setattr(hw, "_load_config", lambda: cfg)
    monkeypatch.setattr(hw, "_run_json", lambda args, timeout=300: (hc or {"stale_deps": [], "stale_mtime_deps": [],
                                                                     "depends_coverage": {"with_depends": 1, "total": 4, "ratio": 0.25}})
                        if "atom-health-check" in args[0] else {})
    monkeypatch.setattr(hw, "_run_check", lambda args, timeout=120: (True, ""))
    monkeypatch.setattr(hw, "_episodic_status", lambda cut: (None, {"counts": {"generated": 0, "skipped": 0, "failed": 0}, "reasons": {}}))
    monkeypatch.setattr(hw.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    (hw.MEMORY / "_vectordb").mkdir(parents=True)


def test_collect_has_selftests_section_and_last_run_counts_failed(hw, monkeypatch):
    _stub_collect_deps(hw, monkeypatch, [_st("ok", "selftest_pass.py"), _st("bad", "bad_sentinel.py")])
    result = hw.collect()
    assert [s["name"] for s in result["selftests"]] == ["ok", "bad"]
    assert any("selftest bad" in r for r in result["red"])
    assert any("Depends 覆蓋率 1/4" in i for i in result["info"])
    monkeypatch.setattr(sys, "argv", ["health-weekly.py", "--json"])
    rc = hw.main()
    assert rc == 1
    last = json.loads(hw.LAST_RUN.read_text(encoding="utf-8"))
    assert last["selftests_failed"] == 1 and last["red"] >= 1


def test_collect_reports_mtime_deps_and_low_coverage(hw, monkeypatch):
    hc = {"stale_deps": [{"atom": "a", "dep": "x"}],
          "stale_mtime_deps": [{"atom": "b", "dep": "C:/x/y.py", "dep_changed": "2026-10-01", "verified_at": "2026-09-01"}],
          "depends_coverage": {"with_depends": 0, "total": 3, "ratio": 0.0}}
    _stub_collect_deps(hw, monkeypatch, [], hc=hc)
    monkeypatch.setattr(hw, "_load_config", lambda: {"tool_selftests": [], "depends_coverage_min": 0.5,
                                                     "provenance": {"enabled": False}})
    result = hw.collect()
    y = "\n".join(result["yellow"])
    assert "stale_deps 1 筆" in y and "依賴比卡新 1 筆" in y and "b←y.py" in y and "低於 depends_coverage_min" in y


def test_reconcile_overflow_block_counts_recent(hw, monkeypatch, tmp_path):
    monkeypatch.setattr(hw, "CLAUDE_DIR", tmp_path)
    (tmp_path / "Logs").mkdir()
    now = datetime.now().astimezone()
    rows = [{"at": now.isoformat(timespec="seconds"), "session_id": "s"},
            {"at": (now - timedelta(days=40)).isoformat(timespec="seconds"), "session_id": "s"}]
    (tmp_path / "Logs" / "guard-reconcile_overflow.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8", newline="\n")
    out = hw._reconcile_overflow_block(14)
    assert len(out) == 1 and "放行 1 次" in out[0]
    assert hw._reconcile_overflow_block(14) == out
    monkeypatch.setattr(hw, "CLAUDE_DIR", tmp_path / "none")
    assert hw._reconcile_overflow_block(14) == []


def test_user_release_block_counts_recent_per_gate(hw, monkeypatch, tmp_path):
    """件一：擋滿後使用者放行（guard-<閘>.jsonl event=user_release）近 N 天要在健檢紅區看得到；其他事件與舊事件不算。"""
    monkeypatch.setattr(hw, "CLAUDE_DIR", tmp_path)
    (tmp_path / "Logs").mkdir()
    now = datetime.now().astimezone()
    old = (now - timedelta(days=40)).isoformat(timespec="seconds")
    rows = {"reconcile": [{"at": now.isoformat(timespec="seconds"), "event": "user_release"},
                          {"at": now.isoformat(timespec="seconds"), "event": "exhausted_block", "x": "user_release"},
                          {"at": old, "event": "user_release"}],
            "sync_block": [{"at": now.isoformat(timespec="seconds"), "event": "user_release"}] * 2}
    for gate, rs in rows.items():
        (tmp_path / "Logs" / f"guard-{gate}.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rs) + "\n", encoding="utf-8", newline="\n")
    out = hw._user_release_block(14)
    assert len(out) == 1 and "reconcile 1 次" in out[0] and "sync_block 2 次" in out[0]
    monkeypatch.setattr(hw, "CLAUDE_DIR", tmp_path / "none")
    assert hw._user_release_block(14) == []


# ─── atom-health-check：Depends mtime 與覆蓋率 ───────────────────────────────

HC = _load("atom_health_check_selftests_ut", _ROOT / "tools" / "atom-health-check.py")

ATOM = ("# {name}\n\n- Scope: global\n- Confidence: [觀]\n- Trigger: a, b\n{extra}\n## 知識\n\n- x\n\n## 行動\n\n- y\n")


def _atom(tmp_path, name, extra=""):
    p = tmp_path / f"{name}.md"
    p.write_text(ATOM.format(name=name, extra=extra), encoding="utf-8", newline="\n")
    return p


def test_depends_mtime_flags_dep_newer_than_verified_date(tmp_path):
    dep = tmp_path / "dep.py"
    dep.write_text("x", encoding="utf-8", newline="\n")       # mtime = 今天
    old = _atom(tmp_path, "old", f"- Verified-at: 2026-01-01\n- Depends: path:{dep}\n")
    fresh = _atom(tmp_path, "fresh", f"- Verified-at: {datetime.now():%Y-%m-%d}\n- Depends: path:{dep}\n")
    created = _atom(tmp_path, "created", f"- Created-at: 2026-01-01\n- Depends: path:{dep}\n")
    nodep = _atom(tmp_path, "nodep", "- Created-at: 2026-01-01\n")
    issues = HC.check_depends_mtime({"old": old, "fresh": fresh, "created": created, "nodep": nodep})
    assert sorted(i["atom"] for i in issues) == ["created", "old"]
    hit = next(i for i in issues if i["atom"] == "old")
    assert hit["verified_at"] == "2026-01-01" and hit["verified_source"] == "Verified-at"
    assert hit["dep_changed"] == f"{datetime.now():%Y-%m-%d}" and hit["dep_source"] == "mtime"   # 不在版控 → mtime
    # 同一天：依賴在卡片之後才改 → 報，並寫明是同日比出來的
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    os.utime(fresh, ((today + timedelta(hours=1)).timestamp(),) * 2)
    os.utime(dep, ((today + timedelta(hours=2)).timestamp(),) * 2)
    same = HC.check_depends_mtime({"fresh": fresh})
    assert len(same) == 1 and same[0]["same_day"].startswith("同日，依賴晚於卡片 mtime")


def test_depends_mtime_missing_path_left_to_stale_deps(tmp_path):
    a = _atom(tmp_path, "a", f"- Verified-at: 2026-01-01\n- Depends: path:{tmp_path / 'gone.py'}\n")
    assert HC.check_depends_mtime({"a": a}) == []
    assert len(HC.check_stale_deps({"a": a})) == 1


def test_depends_mtime_falls_back_to_atom_file_mtime(tmp_path):
    dep = tmp_path / "dep.py"
    dep.write_text("x", encoding="utf-8", newline="\n")
    a = _atom(tmp_path, "a", f"- Depends: path:{dep}\n")
    old_ts = time.time() - 5 * 86400
    os.utime(a, (old_ts, old_ts))
    issues = HC.check_depends_mtime({"a": a})
    assert len(issues) == 1 and issues[0]["verified_source"] == "mtime"


# ─── 依賴比卡新：依賴在版控裡看版控的最後變更，不看 update 時被刷新的 mtime ──────────

def _sh(*cmd, cwd=None, env=None):
    subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, check=True, capture_output=True)


def _svn_repo(tmp_path):
    if not (shutil.which("svn") and shutil.which("svnadmin")):
        pytest.skip("沒裝 svn／svnadmin")
    repo = tmp_path / "repo"
    _sh("svnadmin", "create", repo)
    _sh("svn", "checkout", "-q", repo.as_uri(), tmp_path / "wc")
    return repo, tmp_path / "wc"


def _svn_commit(wc, *names):
    _sh("svn", "add", "-q", *[wc / n for n in names])
    _sh("svn", "commit", "-q", "-m", "m", wc)


def _svn_set_date(repo, rev, when):
    """把第 rev 版的提交時間改成 when（本地時間）；svnadmin 直接改，不需要 pre-revprop-change hook。"""
    f = repo.parent / f"date-r{rev}.txt"
    f.write_text(when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z"), encoding="ascii", newline="")
    _sh("svnadmin", "setrevprop", repo, "-r", rev, "svn:date", f)


def _git_commit(root, name, when):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_AUTHOR_DATE": when.astimezone().isoformat(),
           "GIT_COMMITTER_DATE": when.astimezone().isoformat()}
    _sh("git", "-C", root, "add", name, env=env)
    _sh("git", "-C", root, "-c", "commit.gpgsign=false", "commit", "-q", "-m", name, env=env)


def test_depends_vcs_date_beats_fresh_mtime_svn(tmp_path):
    """svn：剛 checkout／update 的檔 mtime 是今天，但版控最後變更在卡片驗證日之前 → 不報；本機改了沒提交、沒進版控 → 回到 mtime。"""
    repo, wc = _svn_repo(tmp_path)
    (wc / "dep.py").write_text("x", encoding="utf-8", newline="\n")
    _svn_commit(wc, "dep.py")
    _svn_set_date(repo, 1, datetime(2026, 1, 1, 12))
    fresh = tmp_path / "fresh"                                   # 新 checkout＝「這台剛 update」
    _sh("svn", "checkout", "-q", repo.as_uri(), fresh)
    dep = fresh / "dep.py"
    card = _atom(tmp_path, "card", f"- Verified-at: 2026-03-01\n- Depends: path:{dep}\n")
    assert datetime.fromtimestamp(dep.stat().st_mtime).date() > datetime(2026, 3, 1).date()   # 只看 mtime 會報
    assert HC.check_depends_mtime({"card": card}) == []
    dep.write_text("y", encoding="utf-8", newline="\n")          # 本機改了沒提交：版控日期不代表現況
    (fresh / "new.py").write_text("z", encoding="utf-8", newline="\n")
    both = _atom(tmp_path, "both", f"- Verified-at: 2026-03-01\n- Depends: path:{dep}, path:{fresh / 'new.py'}\n")
    got = {Path(i["dep"]).name: i["dep_source"] for i in HC.check_depends_mtime({"both": both})}
    assert got == {"dep.py": "mtime（本機未提交修改）", "new.py": "mtime（未進版控）"}


def test_depends_vcs_date_beats_fresh_mtime_git(tmp_path):
    root = tmp_path / "g"
    root.mkdir()
    _sh("git", "init", "-q", root)
    dep = root / "dep.py"
    dep.write_text("x", encoding="utf-8", newline="\n")
    _git_commit(root, "dep.py", datetime(2026, 1, 1, 12))
    os.utime(dep, None)                                          # mtime＝現在（像 pull／checkout 後）
    card = _atom(tmp_path, "card", f"- Verified-at: 2026-03-01\n- Depends: path:{dep}\n")
    assert HC.check_depends_mtime({"card": card}) == []
    old = _atom(tmp_path, "old", f"- Verified-at: 2025-12-01\n- Depends: path:{dep}\n")
    hit = HC.check_depends_mtime({"old": old})
    assert len(hit) == 1 and hit[0]["dep_changed"] == "2026-01-01" and hit[0]["dep_source"].startswith("git ")


def test_depends_same_day_ordered_by_svn_revision(tmp_path):
    """同一天：比卡片當天第一次進版的版號與依賴的最後變更版號。三版提交時間設成同一刻，只剩版號分得出先後。"""
    repo, wc = _svn_repo(tmp_path)
    fresh = tmp_path / "fresh"
    dep_line = f"- Verified-at: 2026-05-05\n- Depends: path:{fresh / 'dep.py'}\n"
    for rev, name in enumerate(("before.md", "dep.py", "after.md"), start=1):   # r1 卡 → r2 依賴 → r3 卡
        (wc / name).write_text(ATOM.format(name=name, extra=dep_line) if name.endswith(".md") else "x",
                               encoding="utf-8", newline="\n")
        _svn_commit(wc, name)
        _svn_set_date(repo, rev, datetime(2026, 5, 5, 12))
    _sh("svn", "checkout", "-q", repo.as_uri(), fresh)
    issues = HC.check_depends_mtime({"before": fresh / "before.md", "after": fresh / "after.md"})
    assert [i["atom"] for i in issues] == ["before"]
    assert issues[0]["dep_source"] == "svn r2" and issues[0]["same_day"] == "同日，依賴晚於卡片 svn r1"


def test_depends_same_day_ordered_by_git_commit_time(tmp_path):
    root = tmp_path / "g"
    root.mkdir()
    _sh("git", "init", "-q", root)
    dep_line = f"- Verified-at: 2026-05-05\n- Depends: path:{root / 'dep.py'}\n"
    for hour, name in ((10, "before.md"), (11, "dep.py"), (12, "after.md")):
        (root / name).write_text(ATOM.format(name=name, extra=dep_line) if name.endswith(".md") else "x",
                                 encoding="utf-8", newline="\n")
        _git_commit(root, name, datetime(2026, 5, 5, hour))
    issues = HC.check_depends_mtime({"before": root / "before.md", "after": root / "after.md"})
    assert [i["atom"] for i in issues] == ["before"] and issues[0]["same_day"].startswith("同日，依賴晚於卡片 git ")


def test_depends_coverage_and_full_report_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(HC, "MEMORY_ROOT", tmp_path)
    dep = tmp_path / "dep.py"
    dep.write_text("x", encoding="utf-8", newline="\n")
    a = _atom(tmp_path, "a", f"- Depends: path:{dep}\n")
    b = _atom(tmp_path, "b", "- Depends: decision:xxx\n")
    c = _atom(tmp_path, "c")
    cov = HC.depends_coverage({"a": a, "b": b, "c": c})
    assert cov == {"with_depends": 1, "total": 3, "ratio": 0.3333}
    rep = HC.full_report({"a": a, "b": b, "c": c})
    assert "stale_mtime_deps" in rep and rep["depends_coverage"] == cov
    single = HC.single_atom_report("a", {"a": a})
    assert "stale_mtime_deps" in single

# ─── BLOCK 8：先 PASS 後崩潰／雜訊／DONE 後 FAIL 都紅（取最後非空行；exit 非零紅）────

def test_pass_then_crash_turns_red(hw, tmp_path):
    red, _, results = hw._selftests_block([_st("crash", "pass_then_crash.py")], tmp_path)
    assert len(red) == 1 and results[0]["exit_code"] == 1 and "exit 1" in results[0]["detail"]


def test_pass_then_noise_turns_red(hw, tmp_path):
    red, _, results = hw._selftests_block([_st("noise", "pass_then_noise.py")], tmp_path)
    assert len(red) == 1 and "cleanup" in results[0]["last_line"] and "不是 PASS 哨兵" in results[0]["detail"]


def test_done_then_fail_turns_red(hw, tmp_path):
    red, _, results = hw._selftests_block([_st("df", "done_then_fail.py", "DONE")], tmp_path)
    assert len(red) == 1 and results[0]["last_line"] == "SELF_CHECK FAIL"


def test_expected_fail_accepts_nonzero_exit(hw, tmp_path):
    """expected FAIL：exit 1 仍綠（selftest_expect_fail.py）。"""
    red, _, results = hw._selftests_block([_st("ef", "selftest_expect_fail.py", "FAIL")], tmp_path)
    assert red == [] and results[0]["ok"] is True and results[0]["exit_code"] == 1
