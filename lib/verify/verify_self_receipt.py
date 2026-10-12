"""verify_self_receipt.py：run_verify 自寫驗證收據（lib/self_receipt.py）的寫與讀。

正例：欄位齊、路徑在 workflow/verify-ledger/_runs/、cmd 正規化成表上的量尺寫法；讀端只收自寫來源、新的在前。
反例：寫不進去 → stderr 一行、回 None、不拋；--help 不寫收據（真的跑 run_verify.py --help）。
接線：run_verify.py 印完量尺哨兵之後才寫收據。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_self_receipt.py
"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("_ut_self_receipt", ROOT / "lib" / "self_receipt.py")   # 按檔案載入（同 run_verify）
sr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sr)

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


def test_006_real_run_verify_writes_receipt_with_tree_root(tmp_path):
    """真實接線：tmp 樹 A 放 run_verify.py＋lib/＋一個會過的 verify 檔，在 B 目錄當 cwd 子行程實跑；
    收據真的落地在 A/workflow/verify-ledger/_runs/，project_root＝A（受測樹，006-5）、cwd＝B。"""
    import shutil
    a, b = tmp_path / "A", tmp_path / "B"
    b.mkdir()
    shutil.copytree(ROOT / "lib", a / "lib", ignore=shutil.ignore_patterns("verify", "__pycache__"))
    shutil.copyfile(ROOT / "run_verify.py", a / "run_verify.py")
    shutil.copyfile(ROOT / "pytest.ini", a / "pytest.ini")                         # python_files 要收 verify_*.py
    (a / "hooks" / "verify").mkdir(parents=True)
    (a / "hooks" / "verify" / "verify_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", str(a / "run_verify.py")], capture_output=True, text=True,
                       encoding="utf-8", timeout=300, cwd=str(b))
    assert r.returncode == 0 and "VERIFY_CHECK DONE cases=1 failed=0" in r.stdout, r.stdout[-500:] + r.stderr[-500:]
    runs = list((a / "workflow" / "verify-ledger" / "_runs").glob("*.json"))
    assert len(runs) == 1
    rec = json.loads(runs[0].read_text(encoding="utf-8"))
    assert rec["project_root"] == str(a) and rec["cwd"] == str(b)                     # 受測樹不是 cwd
    assert rec["cmd"] == "python -X utf8 run_verify.py" and rec["source"] == "run_verify_self"
    assert rec["exit_code"] == 0 and rec["cases"] == 1 and rec["failed"] == 0
    assert rec["sentinel"] == "VERIFY_CHECK DONE cases=1 failed=0" and rec["started_at"] <= rec["at"]


def test_cmd_of_normalizes_interpreter_and_script_path():
    assert sr.cmd_of(["/usr/bin/python3", "run_verify.py"]) == "python3 run_verify.py"
    assert sr.cmd_of([r"C:\x\pythonw.exe", "-X", "utf8", r"C:\a\b\run_verify.py"]) == "pythonw -X utf8 run_verify.py"
    assert sr.cmd_of([]) == ""


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
