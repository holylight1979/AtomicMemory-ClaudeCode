"""verify_self_receipt.py：run_verify 自寫驗證收據（lib/self_receipt.py）的寫與讀。

正例：欄位齊、路徑在 workflow/verify-ledger/_runs/、cmd 正規化成表上的量尺寫法；讀端只收自寫來源、新的在前。
反例：寫不進去 → stderr 一行、回 None、不拋；--help 不寫收據（真的跑 run_verify.py --help）。
接線：run_verify.py 印完量尺哨兵之後才寫收據；收據寫資料根（WG_CLAUDE_DIR 或 ~/.claude），不寫程式碼樹，
  量尺閘（hooks/wg_verify_ledger.load_self_runs）從同一個資料根讀得到、project_root 對得上受測樹。
  部位量尺是整組 pytest 的（`pytest -q tools/verify`、`pytest -q lib/verify`）由根 conftest 跑完自寫收據（同機制），
  量尺閘 self_run_ok 認帳；只跑一支不寫。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_self_receipt.py
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("_ut_self_receipt", ROOT / "lib" / "self_receipt.py")   # 按檔案載入（同 run_verify）
sr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sr)
_ohspec = importlib.util.spec_from_file_location("_ut_overview_hub", ROOT / "lib" / "overview_hub.py")
_overview_hub = importlib.util.module_from_spec(_ohspec)
_ohspec.loader.exec_module(_overview_hub)

ARGV = [r"C:\Py\python.exe", "-X", "utf8", str(ROOT / "run_verify.py"), "--json"]


def test_write_self_receipt_fields_and_location(tmp_path):
    p = sr.write_self_receipt(tmp_path, ARGV, "VERIFY_CHECK DONE cases=9 failed=0", 0, 9, 0,
                              r"C:\proj", r"C:\proj", 1760234400.0, 1760235600.0)
    assert p is not None and p.parent == tmp_path / "workflow" / "verify-ledger" / "_runs"
    assert p.name.startswith("20251012T") and p.name.endswith(".json")
    rec = json.loads(p.read_text(encoding="utf-8"))
    assert rec["cmd"] == "python -X utf8 run_verify.py --json" and rec["argv"] == ARGV
    assert {k: rec[k] for k in ("exit_code", "cases", "failed", "cwd", "project_root", "source")} == {
        "exit_code": 0, "cases": 9, "failed": 0, "cwd": r"C:\proj", "project_root": r"C:\proj", "source": "run_verify_self"}
    assert rec["started_at"] == "2025-10-12T02:00:00+00:00" and rec["at"] == "2025-10-12T02:20:00+00:00"
    assert rec["sentinel"] == "VERIFY_CHECK DONE cases=9 failed=0"
    assert b"\r\n" not in p.read_bytes()                                       # LF


def test_024_2_write_self_receipt_records_scope_env(tmp_path, monkeypatch):
    """024 規則 2：自寫收據記下本行程環境裡影響驗證範圍的變數（空值也記；讀的一方照值判斷）。"""
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k x")
    monkeypatch.setenv("PYTHONOPTIMIZE", "")
    p = sr.write_self_receipt(tmp_path, ARGV, "VERIFY_CHECK DONE cases=1 failed=0", 0, 1, 0, r"C:\proj", r"C:\proj", 0.0, 1.0)
    rec = json.loads(p.read_text(encoding="utf-8"))
    assert {k.upper(): v for k, v in (rec.get("env") or {}).items()} == {"PYTEST_ADDOPTS": "-k x", "PYTHONOPTIMIZE": ""}


def test_write_failure_is_one_stderr_line_not_exception(tmp_path):
    (tmp_path / "workflow").write_text("我是檔案不是目錄", encoding="utf-8")       # mkdir 必失敗
    err = io.StringIO()
    assert sr.write_self_receipt(tmp_path, ARGV, "s", 1, 1, 1, "c", "", 0.0, 1.0, err=err) is None
    lines = err.getvalue().strip().splitlines()
    assert len(lines) == 1 and lines[0].startswith("[run_verify] 自寫驗證收據失敗")


def test_load_self_receipts_newest_first_and_only_self_source(tmp_path):
    d = tmp_path / "workflow" / "verify-ledger" / "_runs"
    d.mkdir(parents=True)
    (d / "20261012T010000Z-1.json").write_text(json.dumps({"source": "run_verify_self", "n": 1}), encoding="utf-8")
    (d / "20261012T020000Z-2.json").write_text(json.dumps({"source": "run_verify_self", "n": 2}), encoding="utf-8")
    (d / "20261012T030000Z-3.json").write_text(json.dumps({"source": "hand", "n": 3}), encoding="utf-8")
    (d / "20261012T040000Z-4.json").write_text("{壞", encoding="utf-8")
    assert [r["n"] for r in sr.load_self_receipts(tmp_path)] == [2, 1]
    assert sr.load_self_receipts(tmp_path / "none") == []


def _runs_dir(tmp_path, n, now, old_idx=()):
    d = tmp_path / "workflow" / "verify-ledger" / "_runs"
    d.mkdir(parents=True)
    import os
    for i in range(n):
        f = d / f"2026{i:08d}T000000Z-1.json"
        f.write_text("{}", encoding="utf-8")
        t = now - (31 * 86400 if i in old_idx else 60)
        os.utime(f, (t, t))
    return d


def test_prune_keeps_newest_200_and_drops_older_than_30_days(tmp_path):
    now = 1_800_000_000.0
    d = _runs_dir(tmp_path, 205, now, old_idx={204})                              # 最新那份（檔名最大）mtime 卻超過 30 天
    removed = sr.prune_self_runs(tmp_path, now=now)
    left = sorted(p.name for p in d.glob("*.json"))
    assert removed == 6 and len(left) == 199                                       # 超過 200 份的 5 份＋30 天以上的 1 份
    assert left[-1] == "202600000203T000000Z-1.json" and left[0] == "202600000005T000000Z-1.json"
    assert sr.prune_self_runs(tmp_path / "none", now=now) == 0                     # 沒有目錄不炸


def test_prune_failure_is_stderr_line_and_continues(tmp_path, monkeypatch):
    now = 1_800_000_000.0
    _runs_dir(tmp_path, 3, now, old_idx={0, 1})
    real_unlink = Path.unlink

    def flaky(self, *a, **k):
        if self.name.startswith("202600000001"):
            raise PermissionError("locked")
        return real_unlink(self, *a, **k)
    monkeypatch.setattr(Path, "unlink", flaky)
    err = io.StringIO()
    assert sr.prune_self_runs(tmp_path, now=now, err=err) == 1                     # 反例：一份刪不掉，另一份照刪
    assert err.getvalue().count("\n") == 1 and "刪不掉舊收據" in err.getvalue()


def test_session_end_calls_prune():
    src = (ROOT / "hooks" / "handlers" / "session_end.py").read_text(encoding="utf-8")
    assert "prune_self_runs(" in src and src.index("_cleanup_old_states()") < src.index("prune_self_runs(")


GATE_PROBE = ("import json, sys; sys.path.insert(0, sys.argv[1]); import wg_verify_ledger as L; runs = L.load_self_runs(); "
              "print('GATE_JSON ' + json.dumps({'roots': [r.get('project_root') for r in runs], "
              "'root_ok': [L._root_ok(r, sys.argv[2]) for r in runs]}))")


@pytest.mark.parametrize("data_mode", ["tmp", "unset"])
def test_006_real_run_verify_writes_receipt_to_data_root_with_tree_root(tmp_path, data_mode):
    """真實接線：tmp 樹 A（當成 worktree）放 run_verify.py＋conftest.py＋lib/＋一個會過的 verify 檔，在 B 目錄當 cwd 子行程實跑；
    資料根是 tmp（WG_CLAUDE_DIR）或沒設（落 tmp 家/.claude，等同 live）。收據落地在資料根的 workflow/verify-ledger/_runs/、
    不落 A；project_root＝A（受測樹，006-5）、cwd＝B；A 裡的測試跑在 conftest 隔離的資料根（不是外層資料根）；
    量尺閘用同一組環境 load_self_runs 讀得到這份收據，_root_ok 對 A 成立。"""
    import shutil
    a, b, home = tmp_path / "A", tmp_path / "B", tmp_path / "home"
    b.mkdir()
    home.mkdir()
    shutil.copytree(ROOT / "lib", a / "lib", ignore=shutil.ignore_patterns("verify", "__pycache__"))
    for name in ("run_verify.py", "pytest.ini", "conftest.py"):                    # pytest.ini：python_files 要收 verify_*.py
        shutil.copyfile(ROOT / name, a / name)
    (a / "hooks" / "verify").mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if k not in ("WG_CLAUDE_DIR", "PYTEST_CURRENT_TEST")}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "PYTHONIOENCODING": "utf-8"})
    data = tmp_path / "data" if data_mode == "tmp" else home / ".claude"
    if data_mode == "tmp":
        env["WG_CLAUDE_DIR"] = str(data)
    (a / "hooks" / "verify" / "verify_ok.py").write_text(
        "import os\n\ndef test_ok():\n    assert os.path.realpath(os.environ['WG_CLAUDE_DIR']) != "
        f"os.path.realpath({str(data)!r})\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", str(a / "run_verify.py")], capture_output=True, text=True,
                       encoding="utf-8", timeout=300, cwd=str(b), env=env)
    assert r.returncode == 0 and "VERIFY_CHECK DONE cases=1 failed=0" in r.stdout, r.stdout[-500:] + r.stderr[-500:]
    assert not (a / "workflow").exists()                                              # 反例：收據不寫程式碼樹
    runs = list((data / "workflow" / "verify-ledger" / "_runs").glob("*.json"))
    assert len(runs) == 1
    rec = json.loads(runs[0].read_text(encoding="utf-8"))
    assert rec["project_root"] == str(a) and rec["cwd"] == str(b)                     # 受測樹不是 cwd
    assert rec["cmd"] == "python -X utf8 run_verify.py" and rec["source"] == "run_verify_self"
    assert rec["exit_code"] == 0 and rec["cases"] == 1 and rec["failed"] == 0
    assert rec["sentinel"] == "VERIFY_CHECK DONE cases=1 failed=0" and rec["started_at"] <= rec["at"]
    g = subprocess.run([sys.executable, "-X", "utf8", "-c", GATE_PROBE, str(ROOT / "hooks"), str(a)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120, cwd=str(b), env=env)
    line = next((l for l in g.stdout.splitlines() if l.startswith("GATE_JSON ")), None)
    assert line, g.stderr[-2000:]
    assert json.loads(line[len("GATE_JSON "):]) == {"roots": [str(a)], "root_ok": [True]}


# argv：hooks 目錄、受測樹、量尺；部位最後修改給一個早於開跑的時間
SUITE_GATE_PROBE = ("import json, sys; sys.path.insert(0, sys.argv[1]); import wg_verify_ledger as L; runs = L.load_self_runs(); "
                    "print('GATE_JSON ' + json.dumps({'n': len(runs), 'sentinels': [r.get('sentinel') for r in runs], "
                    "'ok': L.self_run_ok(runs, sys.argv[3], sys.argv[2], '2000-01-01T00:00:00+00:00', 0)}))")


@pytest.mark.parametrize("suite,data_mode", [("tools/verify", "tmp"), ("tools/verify", "unset"), ("lib/verify", "tmp")])
def test_whole_pytest_suite_writes_receipt_gate_accepts(tmp_path, suite, data_mode):
    """部位量尺是整組 pytest（`python -X utf8 -m pytest -q tools/verify`、`… lib/verify`；背景跑看不到結尾）：根 conftest
    在整組跑完後寫收據到 pytest 啟動時的資料根（tmp，或沒設 → tmp 家/.claude）、不落受測樹；量尺閘 load_self_runs 讀得到，
    self_run_ok 對這把量尺與受測樹成立。只跑其中一支、篩過、只收集、-o 覆寫收集設定、-c 換 ini 都不寫收據。"""
    import shutil
    a, home = tmp_path / "A", tmp_path / "home"
    home.mkdir()
    shutil.copytree(ROOT / "lib", a / "lib", ignore=shutil.ignore_patterns("verify", "__pycache__"))
    for name in ("pytest.ini", "conftest.py"):
        shutil.copyfile(ROOT / name, a / name)
    shutil.copyfile(ROOT / "pytest.ini", a / "alt.ini")                                # 內容相同、但不是本樹那支 ini
    (a / suite).mkdir(parents=True)
    (a / suite / "verify_ok.py").write_text("def test_ok():\n    assert True\n\n\ndef test_other():\n    assert True\n",
                                            encoding="utf-8")
    ruler = f"python -X utf8 -m pytest -q {suite}"
    env = {k: v for k, v in os.environ.items() if k not in ("WG_CLAUDE_DIR", "PYTEST_CURRENT_TEST")}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "PYTHONIOENCODING": "utf-8"})
    data = tmp_path / "data" if data_mode == "tmp" else home / ".claude"
    if data_mode == "tmp":
        env["WG_CLAUDE_DIR"] = str(data)
    runs_dir = data / "workflow" / "verify-ledger" / "_runs"

    def pytest_run(*args):
        r = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", "-q", *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300, cwd=str(a), env=env)
        assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]

    for narrowed in ([f"{suite}/verify_ok.py"], [suite, "-k", "test_other"], [suite, "--collect-only"],
                     [suite, "--deselect", f"{suite}/verify_ok.py::test_other"],
                     [suite, "-o", "python_files=verify_ok.py"], [suite, "-c", "alt.ini"]):
        pytest_run(*narrowed)                                                         # 子集／篩過／只收集／改收集設定：不寫收據
        assert not runs_dir.exists(), narrowed
    pytest_run(suite)                                                                 # 整組：寫收據
    runs = list(runs_dir.glob("*.json"))
    assert len(runs) == 1 and not (a / "workflow").exists()
    rec = json.loads(runs[0].read_text(encoding="utf-8"))
    assert rec["project_root"] == str(a) and rec["cmd"] == ruler
    assert rec["exit_code"] == 0 and rec["cases"] == 2 and rec["failed"] == 0 and rec["source"] == "run_verify_self"
    g = subprocess.run([sys.executable, "-X", "utf8", "-c", SUITE_GATE_PROBE, str(ROOT / "hooks"), str(a), ruler],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=env)
    line = next((l for l in g.stdout.splitlines() if l.startswith("GATE_JSON ")), None)
    assert line, g.stderr[-2000:]
    sentinel = f"{suite.replace('/', '_').upper()}_CHECK DONE cases=2 failed=0"
    assert json.loads(line[len("GATE_JSON "):]) == {"n": 1, "sentinels": [sentinel], "ok": True}


def test_cmd_of_normalizes_interpreter_and_script_path():
    """python 家族一律寫 python（表上的量尺寫 python）；腳本取檔名；`-Xutf8` 寫成 `-X utf8`。"""
    assert sr.cmd_of(["/usr/bin/python3", "run_verify.py"]) == "python run_verify.py"
    assert sr.cmd_of([r"C:\x\pythonw.exe", "-X", "utf8", r"C:\a\b\run_verify.py"]) == "python -X utf8 run_verify.py"
    assert sr.cmd_of(["python3.13", "-Xutf8", r"C:\中文專案\run_verify.py"]) == "python -X utf8 run_verify.py"
    assert sr.cmd_of([]) == ""


_MEASURE = "python -X utf8 run_verify.py"


def test_009_3_cmd_matches_same_normalization_both_ends():
    """009-4.3：收據端 cmd_of 與量尺比對同一套：絕對腳本路徑、引號、`-Xutf8` 寫法、python 家族、前面的環境設定都對得上。
    017b 規則 7：直譯器選項集合相等（`-u` 多帶、`py -3` 啟動器都不算）。"""
    ok = ['python -X utf8 "C:\\中文專案\\run_verify.py"', "python -Xutf8 run_verify.py",
          "C:/Py/python.exe -X utf8 run_verify.py", "export X=1; WG=1 python -X utf8 run_verify.py 2>&1 | tail -5",
          sr.cmd_of(["C:\\Py\\python.exe", "-X", "utf8", "C:\\中文專案\\run_verify.py"])]
    for cmd in ok:
        assert sr.cmd_matches(_MEASURE, cmd), cmd
    bad = ["python run_verify.py", "python -X utf8 other.py", "echo python -X utf8 run_verify.py",
           "python -X utf8 -m pytest -q hooks/verify", "bash fullrun.sh", "python -u -X utf8 run_verify.py",
           "py -3 -Xutf8 run_verify.py"]
    for cmd in bad:
        assert not sr.cmd_matches(_MEASURE, cmd), cmd
    assert not sr.cmd_matches("pytest -q lib/verify", "python -X utf8 -m pytest -q lib/verify")      # 多帶直譯器選項
    assert not sr.cmd_matches("python -X utf8 -m pytest -q lib/verify", "pytest -q lib/verify")          # 量尺要的選項沒帶
    assert not sr.cmd_matches("python -m pytest -q lib/verify", "python -m pytest -q lib/verify/verify_x.py")  # 子集不算整把尺


_ROOT_ROWS = {r["part_short"]: r for r in _overview_hub.parse_map((ROOT / ".claude" / "overview-map.md").read_text(encoding="utf-8"))}


@pytest.mark.parametrize("part", ["記憶資料層", "專案文件層"])
def test_013_3_compound_rulers_from_root_table(part):
    """013 BLOCK 3：根層部位表 memory/、_AIDocs/ 兩列的量尺（`… && echo X DONE` 串接式）原樣執行 → 對上；
    後面接 `; echo X DONE`、`&& echo …`、`| sed …` → 不對；`| tail -5` → 對。直接讀表上字串當輸入。"""
    m = _ROOT_ROWS[part]["measure"]["cmd"]
    assert "&&" in m
    assert sr.cmd_matches(m, m) and sr.cmd_matches(m, f"WG=1 {m} 2>&1 | tail -5")
    for bad in (f"{m}; echo X_CHECK DONE", f"{m} && echo X_CHECK DONE", f"{m} | sed s/a/b/", m.split(" && ")[0]):
        assert not sr.cmd_matches(m, bad), bad


def test_013_2_quotes_echo_and_subsets_do_not_count():
    """013 BLOCK 2：引號裡的字（含分號）不切、echo 的參數不是指令、子集與多帶參數不是那把尺；選項順序、PowerShell 管線過濾照算。"""
    fake = "echo 'dummy;py -3 -Xutf8 run_verify.py;'; echo VERIFY_CHECK PASS"
    assert not sr.cmd_matches(_MEASURE, fake)
    assert not sr.cmd_matches(_MEASURE, 'Write-Output "python -X utf8 run_verify.py"')
    assert not sr.cmd_matches(_MEASURE, f"{_MEASURE}; echo VERIFY_CHECK DONE cases=1 failed=0")
    assert not sr.cmd_matches("pytest -q lib/verify", "pytest -q lib/verify -k test_cmd_of")
    assert not sr.cmd_matches("pytest -q lib/verify", "pytest -q lib/verify lib/verify/verify_self_receipt.py")
    assert not sr.cmd_matches(_MEASURE, f"{_MEASURE} --json")                                 # 其他選項集合要相等
    assert not sr.cmd_matches("pytest -q lib/verify", "pytest lib/verify -q")                # 017：照順序比（換順序可能換意思）
    assert sr.cmd_matches(_MEASURE, 'python -X utf8 "C:\\中文專案\\run_verify.py" 2>&1 | tail -5')
    assert sr.cmd_matches(_MEASURE, "python -X utf8 run_verify.py | Select-Object -Last 5")
    assert sr.cmd_matches(_MEASURE, "# 定位｜部位：x && y\npython -X utf8 run_verify.py")       # 註解行不算指令
    assert sr.split_shell(fake)[0][0][1] == ["echo", "dummy;py -3 -Xutf8 run_verify.py;"]   # 引號內含分號 → 不切
    assert sr.final_step(fake) is None and sr.final_step(f"{_MEASURE} | tail -3").cmd[0] == "run_verify.py"   # 017：前面只准 cd／環境設定


def test_009_8_load_failures_are_reported_not_silent(tmp_path):
    """009-4.8：讀收據失敗（壞 JSON）→ stderr 一行帶路徑與錯誤種類，那份不採用；好的照收。"""
    runs = tmp_path / "workflow" / "verify-ledger" / "_runs"
    runs.mkdir(parents=True)
    (runs / "20261012T020000Z-1.json").write_text("{broken", encoding="utf-8")
    (runs / "20261012T020100Z-2.json").write_text(json.dumps({"source": sr.SOURCE, "cmd": _MEASURE}), encoding="utf-8")
    err = io.StringIO()
    got = sr.load_self_receipts(tmp_path, err=err)
    assert [r["cmd"] for r in got] == [_MEASURE]
    assert "20261012T020000Z-1.json" in err.getvalue() and "JSONDecodeError" in err.getvalue()


def test_run_verify_writes_receipt_after_sentinel_and_help_writes_nothing(tmp_path):
    src = (ROOT / "run_verify.py").read_text(encoding="utf-8")
    assert src.index("print(sentinel)") < src.index("_write_self_receipt()") < src.index("sys.exit(exit_code)", src.index("_write_self_receipt()"))
    runs = ROOT / "workflow" / "verify-ledger" / "_runs"
    before = set(runs.glob("*.json")) if runs.exists() else set()
    r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "run_verify.py"), "--help"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=str(tmp_path))
    assert r.returncode == 0 and "--json" in r.stdout
    after = set(runs.glob("*.json")) if runs.exists() else set()
    assert after == before                                                         # --help 不寫


def test_015_heredoc_body_and_echo_are_not_executed_words():
    """015：echo 印的字不算執行的字（022 規則 3：「提到改檔」只看實際驗證段的參數，夾了 echo 整條就不是證據形狀）。
    017b 規則 13／14：heredoc 改成 fail-closed：整條指令三種用途都不算
    （heredoc 之後真的跑也不算；要跑尺就單獨跑）。"""
    hd = "cat <<'EOF' > note.txt\npython -X utf8 run_verify.py\nEOF\necho VERIFY_CHECK DONE cases=1 failed=0"
    assert not sr.cmd_matches(_MEASURE, hd)
    assert not sr.cmd_matches(_MEASURE, "cat <<-EOF\n  x\n  EOF\npython -X utf8 run_verify.py")
    assert sr.evidence_words("echo tests/test_a.py; pytest -q tests/test_b.py") == []
    assert sr.evidence_words("pytest -q tests/test_b.py") == ["-q", "tests/test_b.py"]
    assert sr.evidence_words(hd) == [] and "heredoc" in sr.unsupported_syntax(hd)


# ─── 017／017b：白名單語法、解析不了就不算 ─────────────────────────────────────────────

@pytest.mark.parametrize("cmd, kind", [
    ('iex "python -X utf8 run_verify.py"', "iex"),
    ("eval python -X utf8 run_verify.py", "eval"),
    ("source x.sh && python -X utf8 run_verify.py", "source"),
    (". ./x.ps1; python -X utf8 run_verify.py", "."),
    ("Start-Process python -X utf8 run_verify.py", "Start-Process"),
    ("echo $(python -X utf8 run_verify.py)", "$( )"),
    ('echo "$(false && python -X utf8 run_verify.py)"', "$( )"),
    ("echo `python -X utf8 run_verify.py`", "反引號"),
    ("{ python -X utf8 run_verify.py; }", "{ }"),
    ("(python -X utf8 run_verify.py)", "( )"),
    ("& python -X utf8 run_verify.py", "單獨的 &"),
    ("python -X utf8 run_verify.py & wait", "單獨的 &"),
    ('bash -c "python -X utf8 run_verify.py"', "另起一層 shell"),
    ('bash -lc "python -X utf8 run_verify.py"', "另起一層 shell"),
    ("pwsh -Command python -X utf8 run_verify.py", "另起一層 shell"),
    ("powershell python -X utf8 run_verify.py", "另起一層 shell"),          # Windows PowerShell 的位置參數預設是 -Command
    ("pwsh -NoProfile -EncodedCommand cABhAHMAcwA=", "另起一層 shell"),
    ("cmd /c python -X utf8 run_verify.py", "另起一層 shell"),
    ("if (1) { python -X utf8 run_verify.py }", "( )"),
    ("for f in a; do python -X utf8 run_verify.py; done", "控制結構"),
    ('python -X utf8 run_verify.py "', "引號沒閉合"),
    ("python -X utf8 run_verify.py '", "引號沒閉合"),
    ("Write-Output @'\nx\n'@\npython -X utf8 run_verify.py", "here-string"),
    ("cat <<EOF\nx\nEOF\npython -X utf8 run_verify.py", "heredoc"),
    ("python -X utf8 run_verify.py | tail <<< 'VERIFY_CHECK PASS'", "heredoc"),
    ("Write-Output 'VERIFY_CHECK PASS'\n<#\npython -X utf8 run_verify.py\n#>", "<# #>"),
    ("python -X utf8 my\\ dir/run_verify.py", "反斜線跳脫"),
    ("echo VERIFY_CHECK PASS \\; python -X utf8 run_verify.py", "反斜線跳脫"),
    ("echo $'VERIFY_CHECK\\x20PASS'; python -X utf8 run_verify.py", "$'…'"),
    ("python -X utf8 run_verify.py >", "重導向沒有目標"),                 # shell 語法錯誤：整條都沒跑
    ("python -X utf8 run_verify.py > > out", "重導向沒有目標"),           # codex 二審 WARN
    ("python -X utf8 run_verify.py ||| tail -5", "運算子前後缺指令"),
    ("| python -X utf8 run_verify.py", "運算子前後缺指令"),
    ("echo x && ; python -X utf8 run_verify.py", "運算子前後缺指令"),
    ("python -X utf8 run_verify.py &&", "運算子前後缺指令"),
])
def test_017_outside_whitelist_is_not_evidence_anywhere(cmd, kind):
    """017 規則 2、017b 規則 13／14：白名單外語法 → 兩種 shell 都說得出是哪一種，量尺比對、整體驗證、「提到改檔」三種用途都不算。"""
    for shell in ("bash", "powershell"):
        why = sr.unsupported_syntax(cmd, shell)
        assert why and kind in why, (cmd, shell, why)
        assert not sr.cmd_matches(_MEASURE, cmd, shell) and not sr.is_whole_run(cmd, shell) and sr.evidence_words(cmd, shell) == []


@pytest.mark.parametrize("cmd, shell", [
    (_MEASURE, "bash"), (_MEASURE, "powershell"),
    ('python -X utf8 "C:\\中文 專案\\run_verify.py" 2>&1 | tail -n 20', "bash"),
    ('$env:WG_CLAUDE_DIR="C:\\x"; python -X utf8 run_verify.py 2>&1 | Select-Object -Last 5', "powershell"),
    ("$ErrorActionPreference = 'Stop'; python -X utf8 run_verify.py", "powershell"),
    ("export X=1; WG=1 python -X utf8 run_verify.py", "bash"),
    ("python -X utf8 `\nrun_verify.py", "powershell"),                 # 017b 規則 12：PowerShell 反引號續行（LF）
    ("python -X utf8 `\r\nrun_verify.py", "powershell"),               # CRLF 續行
    ("python -X utf8 \\\nrun_verify.py", "bash"),
    ("python -X utf8 \\\r\nrun_verify.py", "bash"),
    ("# 定位｜部位：x && y\r\npython -X utf8 run_verify.py\r\n", "bash"),  # CRLF 換行、註解行
    ("cd C:\\proj && python -X utf8 run_verify.py", "powershell"),
    ("python -X utf8 C:\\\\proj\\\\run_verify.py", "bash"),               # bash 的 \\ 是一個反斜線
    ("python -X utf8 run_verify.py < /dev/null > $null 2>&1", "bash"),
    ("cd C:\\proj &&\npython -X utf8 run_verify.py", "bash"),            # && 之後換行是合法續接
])
def test_017_honest_forms_match(cmd, shell):
    """017 規則 1：白名單內的誠實寫法（引號、重導向、環境設定、cd <根>、續行、CRLF）照表上原字串跑 → 對得上。"""
    assert sr.unsupported_syntax(cmd, shell) is None and sr.cmd_matches(_MEASURE, cmd, shell), cmd


def test_017_evidence_steps_shape_for_general_evidence():
    """一般證據（對帳 (a)(b)、根層 worktree pytest）的形狀：cd／環境設定之後全是跑程式的指令、只用 && 串、stdout 沒導走、
    後面只准留結尾的過濾；讀檔與印字的指令、; 或 || 串（codex 二審 BLOCK 1）、把輸出導走都不算。"""
    for ok in ("pytest -q tests/test_a.py", "python tools/x.py --check", "cd C:\\p && npm test", "./gradlew test",
               ".\\verify.ps1", "WG=1 python -m pytest -q x.py 2>&1 | tail -3", "pytest a.py && pytest b.py",
               "pytest -q x.py 2>/dev/null"):
        assert sr.evidence_steps(ok, "powershell" if ok.startswith(".\\") else "bash"), ok
    for bad in ("cat old.log", "Get-Content x.txt", "type x.txt", "pytest -q x.py; cat old.log", "echo hi",
                "pytest -q x.py | grep passed", "pytest -q x.py | head -5", "iex x", "",
                "python verify_good.py || python verify_widget.py",
                "python verify_widget.py > /dev/null 2>&1; python verify_good.py",
                "python verify_widget.py > /dev/null && python verify_good.py", "pytest a.py; pytest b.py",
                "python verify_good.py && python verify_widget.py > $null | tail -3",
                "python -m pytest a.py && python -m pytest missing.py | tail -5"):     # 管線蓋掉最後一段的 exit
        assert sr.evidence_steps(bad) is None, bad
    assert [s.cmd[0] for s in sr.evidence_steps("cd C:\\p && pytest a.py && python -m pytest b.py")] == ["pytest", "pytest"]


def test_017_changes_dir_and_outside_paths():
    """codex 二審 BLOCK 2／3：換目錄用同一套斷詞判（`c"d"`、`builtin cd`）；指到收據根以外的路徑（../、含 .. 的絕對路徑、
    別棵樹、~、$變數、/tmp）都抓得到，根底下的與 Windows 工具選項 `/p:x` 不算。"""
    for cmd in ('c"d" C:/live; python -X utf8 run_verify.py', "builtin cd /c/live; x", "Set-Location C:\\x; y", "popd; x"):
        assert sr.changes_dir(cmd, "powershell" if "Set-Location" in cmd else "bash"), cmd
    assert not sr.changes_dir("python cdx.py --cd") and not sr.changes_dir(_MEASURE)
    root = "C:\\proj"
    for out in ("python -X utf8 ../live/run_verify.py", "python -X utf8 C:/proj/../live/run_verify.py",
                "python -m pytest -q C:/live/tests/test_x.py", "pytest -q --rootdir=C:/live", "python ~/x.py",
                "python $LIVE/run_verify.py", "python /tmp/run_verify.py", "pytest -q .."):
        assert sr.outside_paths(out, "bash", root), out
    for inside in (_MEASURE, "python -X utf8 c:\\proj\\run_verify.py", "python -m pytest -q -p no:cacheprovider lib/verify",
                   "python -X utf8 /c/proj/sub/../run_verify.py", "msbuild /p:Configuration=Release /nologo"):
        assert sr.outside_paths(inside, "bash", root) == [], inside
    assert sr.outside_paths("python ../x.py", "bash", "") == []                         # 沒根資訊 → 不比


def test_017_script_file_shells_are_whitelisted():
    """跑腳本檔不是「把字串當指令」：`bash x.sh`、`pwsh -File x.ps1`（含 -ExecutionPolicy）可解析、原樣對得上。"""
    for m in ("bash scripts/verify.sh", "pwsh -NoProfile -ExecutionPolicy Bypass -File ./verify.ps1"):
        assert sr.unsupported_syntax(m) is None and sr.cmd_matches(m, m, "powershell"), m


def test_017_short_circuit_and_prefix_rules():
    """017 規則 3：量尺前的運算子只准開頭／;／換行／&&；前面的指令只准 cd 與環境設定（其他指令印的成功行分不出是誰印的）。"""
    for bad in (f"Write-Output 'VERIFY_CHECK DONE cases=1 failed=0' || {_MEASURE}", f"printf x || {_MEASURE}",
                f"echo x | {_MEASURE}", f"cat old.log; {_MEASURE}", f"cat old.log && {_MEASURE}", f"{_MEASURE} || true"):
        assert not sr.cmd_matches(_MEASURE, bad), bad
    for ok in (f"cd C:\\proj && {_MEASURE}", f"export X=1; {_MEASURE}", f"X=1; {_MEASURE}"):
        assert sr.cmd_matches(_MEASURE, ok), ok
    for ps_bad in (f"$x = Write-Host 'VERIFY_CHECK DONE cases=1 failed=0'; {_MEASURE} | Select-Object -Last 0",
                   f"$x=Write-Host VERIFY_CHECK DONE; {_MEASURE}", f"$env:S = python fake.py x; {_MEASURE}"):
        assert not sr.cmd_matches(_MEASURE, ps_bad, "powershell"), ps_bad                # 指定右邊是會印字的指令
    for ps_ok in (f"$ErrorActionPreference = 'Stop'; {_MEASURE}", f'$env:X="1"; {_MEASURE}', f"$x =1; {_MEASURE}"):
        assert sr.cmd_matches(_MEASURE, ps_ok, "powershell"), ps_ok


def test_017_codex_r3_control_flow_identity_and_order():
    """codex 三審：只有環境指定的指令留著（`X=1 || 量尺` 的 || 不能丟）；PowerShell 指定右邊是指令（Set-Location）不是設定；
    管線裡的 cd 不換父 shell 的目錄；腳本照相對根的路徑認（archive/ 裡的同名腳本不算）；選項照順序比。"""
    mem = _ROOT_ROWS["記憶資料層"]["measure"]["cmd"]
    assert not sr.cmd_matches(mem, f"X=1 || {mem}") and not sr.cmd_matches(_MEASURE, f"X=1 || {_MEASURE}")
    assert sr.cmd_matches(_MEASURE, f"X=1; {_MEASURE}") and sr.cmd_matches(_MEASURE, f"X=1 && {_MEASURE}")
    assert not sr.cmd_matches(_MEASURE, f"$x = Set-Location; {_MEASURE}", "powershell")
    assert not sr.cmd_matches(_MEASURE, f"$x = $y; {_MEASURE}", "powershell")
    assert sr.leading_cd(f"cd C:\\proj | export X=1 && {_MEASURE}") is None
    root = "C:\\proj"
    assert not sr.cmd_matches(_MEASURE, "python -X utf8 archive/run_verify.py", root=root)
    assert sr.cmd_matches(_MEASURE, "python -X utf8 archive/run_verify.py")                 # 沒根資訊只比檔名
    assert sr.cmd_matches(_MEASURE, "python -X utf8 C:\\proj\\run_verify.py", root=root)
    assert sr.cmd_matches(_MEASURE, 'python -X utf8 "C:\\中文 專案\\run_verify.py"', root="C:\\中文 專案")
    assert sr.cmd_matches(_MEASURE, ["C:\\Py\\python.exe", "-X", "utf8", "C:\\proj\\run_verify.py"], root=root)
    assert not sr.cmd_matches("pytest -k smoke -m slow", "pytest -m smoke -k slow")
    assert not sr.cmd_matches("python -W ignore -W error verify.py", "python -W error -W ignore verify.py")
    assert sr.cmd_matches("python -W ignore -W error verify.py", "python -W ignore -Werror verify.py")


def test_017_codex_r4_identity_tail_and_literals():
    """codex 四審：多段量尺接過濾時最後一段要是 echo；直接執行的腳本照路徑認；收據照 cwd、量尺照表的根解析；參數大小寫、
    空字串、PowerShell 的 '' 跳脫都照原樣；單引號裡的 $ 是字面值。"""
    two = "python -X utf8 run_verify.py && python missing.py"
    assert not sr.cmd_matches(two, f"{two} | tail -n 5") and sr.cmd_matches(two, two)
    mem = _ROOT_ROWS["記憶資料層"]["measure"]["cmd"]
    assert sr.cmd_matches(mem, f"{mem} 2>&1 | tail -5")                                     # 最後一段是 echo → 照算
    root = "C:\\proj"
    assert not sr.cmd_matches("./verify.sh", "../live/verify.sh", root=root) and sr.cmd_matches("./verify.sh", "./verify.sh", root=root)
    assert not sr.cmd_matches("./verify.ps1", "C:/live/verify.ps1", "powershell", root=root)
    assert sr.outside_paths("../live/verify.sh", "bash", root) == ["../live/verify.sh"]
    assert not sr.cmd_matches("python run_verify.py", "python run_verify.py", root="C:\\proj\\archive", measure_root=root)
    assert sr.cmd_matches("python run_verify.py", "python run_verify.py", root=root, measure_root=root)
    assert not sr.cmd_matches("npm run verify:Critical", "npm run verify:critical")
    assert not sr.cmd_matches('python check.py --mode ""', "python check.py --mode")
    # 量尺照 bash 規則讀（'a''b' 是 ab）；PowerShell 跑同一串時傳的是 a'b → 不是同一個參數
    assert not sr.cmd_matches("python check.py --pattern 'a''b'", "python check.py --pattern 'a''b'", "powershell")
    assert sr.cmd_matches("python check.py --pattern ab", "python check.py --pattern 'a''b'")          # bash 相鄰引號就是接起來
    assert sr.split_shell("echo 'it''s'", "powershell")[0][0].words == ["echo", "it's"]
    assert sr.outside_paths("rg --count '$'", "powershell", root) == [] and sr.outside_paths('rg --count "$x"', "bash", root)
    assert "空的指令名" in sr.unsupported_syntax("'' run_verify.py")


def test_017b_6_powershell_string_expression_is_not_a_command():
    """017b 規則 6：PowerShell 以引號開頭的那段是字串運算式（只輸出字串）→ 不算；bash 同字串（無引號）→ 算
    （bash 整串加引號是一個字＝找不到的程式名，也不算）。"""
    s = "'python -X utf8 run_verify.py'"
    assert "字串運算式" in sr.unsupported_syntax(s, "powershell") and not sr.cmd_matches(_MEASURE, s, "powershell")
    assert sr.cmd_matches(_MEASURE, _MEASURE, "bash") and sr.cmd_matches(_MEASURE, _MEASURE, "powershell")
    assert not sr.cmd_matches(_MEASURE, s, "bash")
    assert not sr.is_whole_run("Write-Output 'VERIFY_CHECK PASS'\n'run_verify.py'", "powershell")


def test_017b_7_python_options_must_be_equal():
    """017b 規則 7：直譯器選項集合相等（`-Xutf8`＝`-X utf8`）；-h／-V／--version／-i／-c／不同 -m／py -3 都對不上。"""
    for bad in ("python -h -X utf8 run_verify.py", "python -V -X utf8 run_verify.py", "python --version -X utf8 run_verify.py",
                "python -i -X utf8 run_verify.py", "python -X utf8 -c run_verify.py", "python -X utf8 -m run_verify",
                "py -3 -X utf8 run_verify.py", "python -u -X utf8 run_verify.py", "python -x -X utf8 run_verify.py"):
        assert not sr.cmd_matches(_MEASURE, bad), bad
    assert sr.cmd_matches(_MEASURE, "python -Xutf8 run_verify.py")
    mem = _ROOT_ROWS["記憶資料層"]["measure"]["cmd"]
    assert not sr.cmd_matches(mem, "python -h " + mem[len("python "):])


def test_017b_8_tail_filters_take_only_numbers_and_options():
    """017b 規則 8：尾端過濾只准選項與數字；帶檔名、< 輸入、<<< 都不算。再收窄成只准留結尾的過濾（tail、Select-Object -Last N）：
    量尺的結論印在最後一行，head／-First 只會把結論切掉、留下前面輸出裡長得像哨兵的行。"""
    for ok in (f"{_MEASURE} | tail -n 20", f"{_MEASURE} 2>&1 | tail -n +3", f"{_MEASURE} | tail -5",
               f"{_MEASURE} | Select-Object -Last 5", f"{_MEASURE} | tail --lines=20"):
        assert sr.cmd_matches(_MEASURE, ok), ok
    for bad in (f"{_MEASURE} | tail -n 20 old.log", f"{_MEASURE} | tail -n 20 < old.log",
                f"{_MEASURE} | tail <<< 'VERIFY_CHECK PASS'", f"{_MEASURE} | Select-Object -ExpandProperty x",
                f"{_MEASURE} | sed s/a/b/", f"{_MEASURE} | head -5", f"{_MEASURE} | Select-Object -First 5",
                f"{_MEASURE} | Select-Object -SkipLast 1"):
        assert not sr.cmd_matches(_MEASURE, bad), bad


@pytest.mark.parametrize("cmd, whole", [
    ("pytest -q", True), ("python -X utf8 -m pytest -q -p no:cacheprovider", True), ("pytest -x -q --tb=short", True),
    (_MEASURE, True), (f"{_MEASURE} 2>&1 | tail -5", True), (f"cd C:\\proj && {_MEASURE}", True),
    ("pytest -q -k x", False), ("pytest --collect-only", False), ("pytest --co -q", False), ("pytest -q tests", False),
    ("pytest -q --lf", False), ("pytest -q --ff", False), ("pytest -q -m slow", False), ("pytest -q --deselect a::b", False),
    ("pytest -q --ignore=x", False), ("pytest -q --maxfail=1", False), ("pytest -q -o testpaths=x", False),
    ("pytest -q -p xdist", False), (f"{_MEASURE} --json", False), ("python -O -m pytest -q", False),
    ("python -h -X utf8 run_verify.py", False), ("echo VERIFY_CHECK PASS; pytest -q", False), (f"printf x || {_MEASURE}", False),
    ("pytest no:fake", False), ("pytest -p", False), ("pytest -q -p no:x no:y", False),        # codex 初審 WARN 4：-p 要配值
    ("python -X utf8 ./run_verify.py", True), ("python -X utf8 archive/run_verify.py", False),  # 022 規則 4：沒根就照寫法認
    ("python -X utf8 C:\\proj\\run_verify.py", False), ("python -X utf8 ../run_verify.py", False),
])
def test_017b_9_whole_run_is_a_whitelist(cmd, whole):
    """017b 規則 9：整體驗證只有不帶參數的 run_verify.py、不帶位置參數也不帶縮範圍選項的 pytest。"""
    assert sr.is_whole_run(cmd) is whole, cmd


def test_022_codex_pre_tokenizer_targets_assignments_and_cd_root():
    """022 codex 預審：重導向目標另記（查哨兵字樣用，不進 words），只有重導向、沒有程式的指令段不支援；bash 環境指定的值要
    字面值（單引號包住的 $ 是字面值）；PowerShell 變數不分大小寫、任何 scope 前綴都認，bash 變數名分大小寫；
    cd 根消掉 . 與 ..，消完不是絕對路徑就不認。"""
    chunks, why = sr.split_shell('python x.py 2>"VERIFY_CHECK DONE" > out.log')
    assert why is None and chunks[0].words == ["python", "x.py"] and chunks[0].targets == ["VERIFY_CHECK DONE", "out.log"]
    assert "只有重導向" in (sr.unsupported_syntax('python x.py; > "VERIFY_CHECK DONE"') or "")
    for cmd in ("$global:PS4='x'; python x.py", "$script:ENV='x'; python x.py", "$ENV:ps4 = 'x'; python x.py"):
        assert sr.unsupported_syntax(cmd, "powershell"), cmd
    assert sr.cmd_matches(_MEASURE, f"$note='it''s'; {_MEASURE}", "powershell")              # PowerShell '' 是字面引號
    for cmd in ("X=$HOME python x.py", 'X="$HOME"; python x.py', "export X=$HOME; python x.py", "declare -x X=$HOME; python x.py"):
        assert "不是字面值" in (sr.unsupported_syntax(cmd) or ""), cmd
    assert sr.unsupported_syntax("X='$HOME' python x.py") is None
    assert "PS4" in (sr.unsupported_syntax('$ENV:PS4="x"; python x.py', "powershell") or "")
    assert sr.unsupported_syntax("env=x; ifs=y; python x.py") is None
    assert sr.leading_cd("cd C:/proj/tests/.. && pytest -q") == "C:/proj"
    assert sr.leading_cd("cd /c/proj/. && pytest -q") == "C:/proj"
    assert sr.leading_cd("cd C:\\proj && pytest -q") == "C:\\proj"
    assert sr.leading_cd("cd C:/.. && pytest -q") is None


def test_022_4_whole_run_identity_with_root():
    """022 規則 4：有根就照完整路徑身分，絕對路徑寫法是根自己那支才算。"""
    root = "C:\\proj"
    assert sr.is_whole_run("python -X utf8 C:\\proj\\run_verify.py", "bash", root)
    assert sr.is_whole_run("python -X utf8 run_verify.py", "bash", root)
    assert not sr.is_whole_run("python -X utf8 archive/run_verify.py", "bash", root)
    assert not sr.is_whole_run("python -X utf8 C:\\other\\run_verify.py", "bash", root)


def test_017b_12_backslash_escape_fails_closed_quotes_work():
    """017b 規則 12（總控台裁定改採 fail-closed）：反斜線跳脫空白／符號 → 不支援（訊息叫人用引號），加引號 → 算；
    `\\;` 不會被拆成兩條指令讓前面的 echo 冒充。"""
    esc = "python -X utf8 my\\ dir/run_verify.py"
    assert "請改用引號" in sr.unsupported_syntax(esc) and not sr.cmd_matches(_MEASURE, esc)
    assert sr.cmd_matches(_MEASURE, 'python -X utf8 "my dir/run_verify.py"')
    assert not sr.cmd_matches(_MEASURE, "echo VERIFY_CHECK PASS \\; python -X utf8 run_verify.py")


def test_017b_14_self_receipt_argv_is_not_shell_parsed():
    """017b 規則 6／14：自寫收據用 argv 比，不經 shell 解析（路徑含空白與符號照樣是一個字）；同一個 cmd_matches。"""
    argv = ["C:\\Py\\python.exe", "-X", "utf8", "C:\\a b (1)\\run_verify.py"]
    assert sr.cmd_matches(_MEASURE, argv)
    assert not sr.cmd_matches(_MEASURE, [*argv, "--json"]) and not sr.cmd_matches(_MEASURE, ["python", "-h", *argv[1:]])


def test_017_leading_cd_root_only_for_single_absolute_cd():
    """`cd <絕對路徑> && …` 認得出根（Git Bash /c/x → C:/x）；相對路徑、`;`、`||`、第二個 cd、~ → 認不出（照舊當含 cd）。"""
    assert sr.leading_cd(f"cd C:\\proj && {_MEASURE}") == "C:\\proj"
    assert sr.leading_cd(f"cd /c/proj && {_MEASURE} | tail -5") == "C:/proj"
    assert sr.leading_cd(f'Set-Location "C:\\中文 專案" && {_MEASURE}', "powershell") == "C:\\中文 專案"
    for bad in (f"cd proj && {_MEASURE}", f"cd C:\\proj; {_MEASURE}", f"cd C:\\proj && cd sub && {_MEASURE}",
                f"cd C:\\proj || {_MEASURE}", f"cd ~/p && {_MEASURE}", f"{_MEASURE} && cd C:\\p", "cd C:\\proj"):
        assert sr.leading_cd(bad) is None, bad


def test_017_all_root_table_rulers_parse_and_match_themselves():
    """G6 (b)：根層部位表 10 列（7 把尺）原字串在兩種 shell 都可解析、原樣跑對得上，尾接 `2>&1 | tail -5` 也對得上。"""
    rows = [r for r in _ROOT_ROWS.values() if (r.get("measure") or {}).get("cmd")]
    assert len(_ROOT_ROWS) == 10 and len(rows) == 7
    for r in rows:
        m = r["measure"]["cmd"]
        for shell in ("bash", "powershell"):
            assert sr.unsupported_syntax(m, shell) is None and sr.cmd_matches(m, m, shell), (m, shell)
            assert sr.cmd_matches(m, f"{m} 2>&1 | tail -5", shell), (m, shell)


def test_029b_env_case_fold_follows_platform():
    """029b（track-verify 008 WARN）：環境變數名的比對照受執行平台，Windows 不分大小寫。旗標的真實預設要有測試守，
    不經 monkeypatch（其他案都自設旗標，寫死成 False 也照綠）。"""
    assert sr._ENV_CASE_FOLD == (os.name == "nt")


@pytest.mark.skipif(os.name != "nt", reason="Windows 上環境變數名不分大小寫才有這個情況")
def test_029b_windows_bash_lowercase_pytest_addopts_is_not_the_ruler():
    """029b：Windows 上 bash 的 `pytest_addopts=` 在 Python 裡就是 PYTEST_ADDOPTS：接量尺不被採認、也不算整體驗證（不經 monkeypatch）。"""
    cmd = "pytest_addopts='-k x' python -m pytest -q"
    assert not sr.cmd_matches("python -m pytest -q", cmd) and not sr.is_whole_run(cmd)
    assert sr.cmd_matches("python -m pytest -q", "python -m pytest -q")                    # 對照：沒帶就對得上
