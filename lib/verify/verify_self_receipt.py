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
