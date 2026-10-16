"""verify_git_cassette.py：測試用 git／svn 子程序錄製重播（lib/git_cassette.py）。

主案：錄一次再換一個受測目錄重播 → 輸出一字不差、檔案變化原樣寫回、重播期間不開 git。
反例：指令不同、呼叫前目錄內容不同、少呼叫、多呼叫 → 都失敗並說要重錄；git 的 index 不同 → 不算差異；
會被 git 叫起來的程式改了 → 自動重錄；逾時與 check=True 的非零結束照錄照播；不是 git／svn 的指令照常執行。
大部分案用假的 git（只寫檔、回輸出）驗錄製重播本身；最後一案用真 git 走一次 init／add／commit。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_git_cassette.py
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("_ut_git_cassette", ROOT / "lib" / "git_cassette.py")
gc = importlib.util.module_from_spec(_spec)
sys.modules["_ut_git_cassette"] = gc
_spec.loader.exec_module(gc)

REAL_RUN = subprocess.run


def fake_git(root_holder):
    """假的 git：init 寫 .git/HEAD 與 index；commit 寫一個物件檔、輸出含受測目錄的絕對路徑；timeout 指令丟逾時。"""
    def run(cmd, *args, **kw):
        if not gc.is_vcs_call(cmd):
            return REAL_RUN(cmd, *args, **kw)
        cwd = Path(kw.get("cwd") or root_holder["root"])
        sub = cmd[1]
        if sub == "init":
            (cwd / ".git").mkdir(exist_ok=True)
            (cwd / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (cwd / ".git" / "index").write_bytes(b"stamp-" + str(id(kw)).encode())   # 每次內容不同（像時間戳）
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if sub == "commit":
            (cwd / ".git" / "obj").write_bytes(b"\x00\x01binary")
            return subprocess.CompletedProcess(cmd, 0, f"committed in {cwd}\n", "")
        if sub == "timeout":
            raise subprocess.TimeoutExpired(cmd, 5)
        if sub == "fail":
            return subprocess.CompletedProcess(cmd, 3, "", "boom\n")
        if sub == "echo-paths":                     # 像 check-ignore 照原樣回聲＋rev-parse 給長檔名正斜線
            return subprocess.CompletedProcess(cmd, 0, f"{cmd[2]}|{Path(cwd).resolve().as_posix()}\n", "")
        return subprocess.CompletedProcess(cmd, 0, "ok\n", "")
    return run


def _record(tmp_path, monkeypatch, scenario, name="c.json.gz", **kw):
    root = tmp_path / "rec"
    root.mkdir()
    holder = {"root": root}
    cas_path = tmp_path / name
    c = gc.Cassette(cas_path, root, "record", **kw)
    c._orig = fake_git(holder)
    c.install(monkeypatch)
    out = scenario(root)
    c.finish(True)
    monkeypatch.undo()
    return cas_path, out


def _replay(tmp_path, monkeypatch, cas_path, scenario, sub="play", finish=True, **kw):
    root = tmp_path / sub
    root.mkdir()
    c = gc.Cassette(cas_path, root, "replay", **kw)

    def no_git(cmd, *args, **k):
        assert not gc.is_vcs_call(cmd), f"重播期間不該開 git：{cmd}"
        return REAL_RUN(cmd, *args, **k)
    c._orig = no_git
    c.install(monkeypatch)
    try:
        out = scenario(root)
        if finish:
            c.finish(True)
    finally:
        monkeypatch.undo()
    return root, out


def _git(root, *args, **kw):
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, encoding="utf-8", **kw)


def basic(root):
    _git(root, "init")
    (root / "a.md").write_text("hello\n", encoding="utf-8")
    r = _git(root, "commit", "-m", "harvest 2026-10-15")
    return r.stdout


def test_round_trip_reproduces_output_and_files_without_git(tmp_path, monkeypatch):
    cas, rec_out = _record(tmp_path, monkeypatch, basic)
    play, out = _replay(tmp_path, monkeypatch, cas, basic)
    assert rec_out == f"committed in {tmp_path / 'rec'}\n"
    assert out.replace("\\", "/").lower() == f"committed in {play.resolve()}\n".replace("\\", "/").lower()   # 路徑換成這次的目錄
    assert (play / ".git" / "HEAD").read_text(encoding="utf-8") == "ref: refs/heads/main\n"
    assert (play / ".git" / "obj").read_bytes() == b"\x00\x01binary"                                      # 二進位檔原樣寫回


def test_each_path_spelling_replays_in_the_same_spelling(tmp_path, monkeypatch):
    """git 照原樣回聲的路徑要還原成這次同一種寫法（反斜線原樣），git 自己給的長檔名正斜線也還原成同一種；
    舊碼一律還原成長檔名正斜線，受測程式拿自己給 git 的字串去比就對不上。"""
    def scenario(root):
        return _git(root, "echo-paths", str(root / "build" / "run.log")).stdout
    _, rec = _record(tmp_path, monkeypatch, scenario)
    play, out = _replay(tmp_path, monkeypatch, tmp_path / "c.json.gz", scenario)
    assert out == f"{play / 'build' / 'run.log'}|{play.resolve().as_posix()}\n", (rec, out)


def test_date_in_argv_does_not_break_replay(tmp_path, monkeypatch):
    cas, _ = _record(tmp_path, monkeypatch, basic)

    def other_day(root):
        _git(root, "init")
        (root / "a.md").write_text("hello\n", encoding="utf-8")
        return _git(root, "commit", "-m", "harvest 2026-11-02").stdout
    _replay(tmp_path, monkeypatch, cas, other_day)


def test_different_argv_fails_with_rerecord_hint(tmp_path, monkeypatch):
    cas, _ = _record(tmp_path, monkeypatch, basic)

    def changed(root):
        _git(root, "init")
        (root / "a.md").write_text("hello\n", encoding="utf-8")
        _git(root, "commit", "--amend", "-m", "x")
    with pytest.raises(gc.CassetteMismatch, match="(?s)第 2 筆呼叫和錄製不同.*--amend.*--git-record"):
        _replay(tmp_path, monkeypatch, cas, changed)


def test_different_tree_before_call_fails_and_names_the_file(tmp_path, monkeypatch):
    cas, _ = _record(tmp_path, monkeypatch, basic)

    def other_content(root):
        _git(root, "init")
        (root / "a.md").write_text("changed\n", encoding="utf-8")
        _git(root, "commit", "-m", "harvest 2026-10-15")
    with pytest.raises(gc.CassetteMismatch, match="內容不同 a.md"):
        _replay(tmp_path, monkeypatch, cas, other_content)


def test_volatile_git_index_difference_is_ignored(tmp_path, monkeypatch):
    cas, _ = _record(tmp_path, monkeypatch, basic)

    def touch_index(root):
        _git(root, "init")
        (root / ".git" / "index").write_bytes(b"different stamp")   # 像子程序裡的 git add 改了 index 時間戳
        (root / "a.md").write_text("hello\n", encoding="utf-8")
        _git(root, "commit", "-m", "harvest 2026-10-15")
    _replay(tmp_path, monkeypatch, cas, touch_index)


def test_log_file_with_timestamps_is_ignored(tmp_path, monkeypatch):
    def scenario(root, stamp):
        (root / "hub.log").write_text(f"{stamp} edit\n", encoding="utf-8")   # 受測程式自己的日誌，每次時間不同
        (root / "wf").mkdir(exist_ok=True)
        (root / "wf" / "ledger.jsonl").write_text(f'{{"at": "{stamp}"}}\n', encoding="utf-8")   # 帳本同理
        return basic(root)
    cas, _ = _record(tmp_path, monkeypatch, lambda r: scenario(r, "12:00:01"))
    _replay(tmp_path, monkeypatch, cas, lambda r: scenario(r, "12:09:59"))


def test_fewer_calls_fail_at_finish_and_extra_calls_fail_immediately(tmp_path, monkeypatch):
    cas, _ = _record(tmp_path, monkeypatch, basic)
    with pytest.raises(gc.CassetteMismatch, match="只用了 1 筆"):
        _replay(tmp_path, monkeypatch, cas, lambda root: _git(root, "init"), sub="fewer")

    def extra(root):
        basic(root)
        _git(root, "status")
    with pytest.raises(gc.CassetteMismatch, match="第 3 筆.*錄製裡沒有"):
        _replay(tmp_path, monkeypatch, cas, extra, sub="extra")


def test_timeout_and_check_failures_replay_as_recorded(tmp_path, monkeypatch):
    def scenario(root):
        got = []
        try:
            _git(root, "timeout", timeout=5)
        except subprocess.TimeoutExpired:
            got.append("timeout")
        try:
            _git(root, "fail", check=True)
        except subprocess.CalledProcessError as e:
            got.append((e.returncode, e.stderr))
        return got
    cas, rec = _record(tmp_path, monkeypatch, scenario)
    _, out = _replay(tmp_path, monkeypatch, cas, scenario)
    assert rec == out == ["timeout", (3, "boom\n")]


def test_excluded_dir_is_not_compared(tmp_path, monkeypatch):
    def scenario(root, stamp):
        (root / "_sync").mkdir(exist_ok=True)
        (root / "_sync" / "roots.json").write_text(stamp, encoding="utf-8")   # 時間戳類，每次不同
        return basic(root)
    cas, _ = _record(tmp_path, monkeypatch, lambda r: scenario(r, "t1"), exclude=["_sync"])
    _replay(tmp_path, monkeypatch, cas, lambda r: scenario(r, "t2"), exclude=["_sync"])


def test_conftest_excludes_every_hook_runtime_fallback_dir():
    """根 conftest 的 git_cassette 預設不比對 hook 在測試沒導走資料根時寫的暫存去處（守門紀錄、需求目標檔：帶時間戳與這次的
    暫存路徑，git 不讀）。清單是字面名字：hooks 裡的暫存去處改名或多一個，這裡會紅。"""
    import re
    spec = importlib.util.spec_from_file_location("_ut_root_conftest", ROOT / "conftest.py")
    conftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conftest)
    used = set()
    for f in (ROOT / "hooks").glob("*.py"):
        used |= set(re.findall(r'"(wg-test-[\w-]+)"', f.read_text(encoding="utf-8")))
    assert "wg-test-need-goal" in used and "wg-test-logs" in used, used       # 前置：真的掃到 hooks 的去處
    assert {e.rsplit("/", 1)[-1] for e in conftest.RUNTIME_EXCLUDE} == used
    assert all(e.startswith("_tmp/") for e in conftest.RUNTIME_EXCLUDE)       # 暫存目錄已改到 tmp_path/_tmp


def test_non_vcs_commands_still_run(tmp_path, monkeypatch):
    def scenario(root):
        _git(root, "init")
        return subprocess.run([sys.executable, "-c", "print(42)"], capture_output=True, text=True).stdout
    cas, rec = _record(tmp_path, monkeypatch, scenario)
    _, out = _replay(tmp_path, monkeypatch, cas, scenario)
    assert rec == out == "42\n"


def test_no_vcs_call_writes_no_file(tmp_path, monkeypatch):
    cas, _ = _record(tmp_path, monkeypatch, lambda root: (root / "a.md").write_text("x", encoding="utf-8"))
    assert not cas.exists()


def test_record_writes_tool_versions(tmp_path, monkeypatch):
    """錄製時記下用到的工具與版本（用錄製時那支執行檔問；假 git 對 --version 回 ok）。"""
    monkeypatch.setattr(gc, "_VERSIONS", {})
    cas, _ = _record(tmp_path, monkeypatch, basic)
    data = gc.load(cas)
    assert data["versions"] == {"git": "ok"} and data["exe"] == {"git": "git"}


def test_tool_version_query_leaves_no_trace_in_test_home(tmp_path, monkeypatch):
    """問版本不能在測試的家目錄留檔（svn 一啟動就建設定目錄）：舊碼沿用測試環境，受測目錄憑空多出 AppData/Subversion。"""
    home = tmp_path / "_home"
    home.mkdir()
    for k in ("HOME", "USERPROFILE", "APPDATA", "XDG_CONFIG_HOME"):
        monkeypatch.setenv(k, str(home))
    monkeypatch.setattr(gc, "_VERSIONS", {})
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(cwd=kw.get("cwd"), home=kw.get("env", {}).get("APPDATA"))
        Path(kw["env"]["APPDATA"], "Subversion").mkdir()          # 模擬 svn 啟動時建設定目錄
        return subprocess.CompletedProcess(cmd, 0, "1.14.5\n", "")
    assert gc.tool_version("svn", run=fake_run) == "1.14.5"
    assert seen["home"] != str(home) and seen["cwd"] == seen["home"]
    assert list(home.iterdir()) == []


def test_tool_version_does_not_consume_test_temp_names(tmp_path, monkeypatch):
    """claude-0b 回報：錄製時 fixture 已把暫存檔名換成序號，舊碼問版本用 TemporaryDirectory 吃掉一個序號（還建在
    受測目錄的 _tmp），受測程式之後的暫存名全錯一位；重播時在換序號前問、不吃號 → 單獨錄的檔整檔重播對不上。"""
    names = iter(f"t{n:06d}" for n in range(1, 100))
    monkeypatch.setattr(tempfile, "_get_candidate_names", lambda: names)
    (tmp_path / "_tmp").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "_tmp"))
    monkeypatch.setattr(gc, "_VERSIONS", {})
    assert gc.tool_version("git", run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "git version 9\n", "")) \
        == "git version 9"
    assert next(names) == "t000001"                                   # 受測程式拿到的第一個暫存名沒被吃掉
    assert list((tmp_path / "_tmp").iterdir()) == []                  # 也沒在受測目錄留東西


def test_tool_version_change_triggers_rerecord(tmp_path, monkeypatch):
    """git 換版（或同事機器版本不同）→ 自動重錄，理由寫出兩個版本；版本相同才重播；舊錄製檔沒記版本 → 重錄。"""
    p = tmp_path / "v.json.gz"
    gc.save(p, {"format": gc.FORMAT, "code": {}, "versions": {"git": "git version 2.50.1"}, "exe": {"git": "git"},
                "start": {}, "calls": []})
    monkeypatch.setattr(gc, "_VERSIONS", {"git": "git version 2.51.0"})
    mode, why = gc.choose_mode(p, "auto", {})
    assert mode == "record" and "2.50.1" in why and "2.51.0" in why, why
    monkeypatch.setattr(gc, "_VERSIONS", {"git": "git version 2.50.1"})
    assert gc.choose_mode(p, "auto", {}) == ("replay", "重播")
    gc.save(p, {"format": gc.FORMAT, "code": {}, "start": {}, "calls": []})
    assert gc.choose_mode(p, "auto", {}) == ("record", "錄製檔沒記 git／svn 版本")


def test_choose_mode(tmp_path):
    p = tmp_path / "x.json.gz"
    assert gc.choose_mode(p, "auto", {}) == ("record", "沒有錄製檔")
    gc.save(p, {"format": gc.FORMAT, "code": {"tools/a.py": "h1"}, "versions": {}, "start": {}, "calls": []})
    assert gc.choose_mode(p, "auto", {"tools/a.py": "h1"}) == ("replay", "重播")
    mode, why = gc.choose_mode(p, "auto", {"tools/a.py": "h2"})
    assert mode == "record" and "tools/a.py" in why                     # 被 git 叫起來的程式改了 → 自動重錄
    assert gc.choose_mode(p, "record", {"tools/a.py": "h1"})[0] == "record"
    assert gc.choose_mode(p, "off", {})[0] == "off"


def test_save_is_byte_stable(tmp_path):
    data = {"format": gc.FORMAT, "code": {}, "start": {"a": "1"}, "calls": []}
    gc.save(tmp_path / "a.json.gz", data)
    gc.save(tmp_path / "b.json.gz", data)
    assert (tmp_path / "a.json.gz").read_bytes() == (tmp_path / "b.json.gz").read_bytes()


def test_real_git_round_trip(tmp_path, monkeypatch):
    """真 git：init／add／commit／log 錄一次，換目錄重播 → log 輸出相同、.git 內容重建、重播期間不開 git。"""
    def scenario(root):
        _git(root, "init", "-q", "-b", "main")
        (root / "a.md").write_text("hello\n", encoding="utf-8")
        _git(root, "add", "a.md")
        _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed")
        return _git(root, "log", "--format=%H %s").stdout
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))   # 不吃使用者的全域設定（簽章、hooksPath）
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "rec"
    root.mkdir()
    c = gc.Cassette(tmp_path / "real.json.gz", root, "record")
    c.install(monkeypatch)
    rec = scenario(root)
    c.finish(True)
    monkeypatch.undo()
    _, out = _replay(tmp_path, monkeypatch, tmp_path / "real.json.gz", scenario)
    assert rec == out and rec.endswith(" seed\n")
