"""verify_atom_io_audit_log.py：稽核帳 memory/_meta/atom_io_audit.jsonl 不再寫出壞位元組、讀取端遇壞行不炸、可修復。

背景：live 稽核帳出現一段非 UTF-8 位元組，用 utf-8 嚴格讀的工具會炸。實測根因：多個 session 的 hook 同時 append，
Windows 上 Python 的附加模式（含 os.open O_APPEND）是「先跳到檔尾、再寫」，兩支行程撞上時後寫的蓋掉前一行尾巴，
把中文字切成半個（8 行程×500 行：382 行非 UTF-8、掉約三成）。
正例：多行程同時寫，全部行都是合法 UTF-8 JSON、一行不少；含孤立代理字元（surrogateescape 解出的路徑）的條目寫得出、讀得回；
反例：讀取端（lib.atom_io.iter_audit_entries、回填工具）遇壞行不炸、stderr 有一行訊號；
修復：tools/atom-io-audit.py --repair 把壞行改寫成合法 JSON 行，原檔整份保留到旁檔，--check 修後轉綠。
全部在 tmp（monkeypatch AUDIT_LOG、子行程 WG_CLAUDE_DIR 指 tmp），不碰 live 稽核帳。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_atom_io_audit_log.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent  # lib/verify → lib → .claude
for p in (str(ROOT), str(ROOT / "hooks")):
    if p not in sys.path:
        sys.path.insert(0, p)

from lib import atom_io  # noqa: E402

TOOL = ROOT / "tools" / "atom-io-audit.py"
# source 不用 "test"：回填工具會把 test 來源的條目當測試殘留跳過
GOOD = {"audit_id": "1", "op": "write", "source": "mcp", "path": "memory/甲.md", "ts": "2026-10-01T00:00:00+00:00"}
GOOD2 = {"audit_id": "2", "op": "write", "source": "mcp", "path": "memory/乙.md", "ts": "2026-10-02T00:00:00+00:00"}
BAD_UTF8 = '{"audit_id": "3", "op": "write", "path": "memory/中'.encode("utf-8")[:-2] + b'"}'   # 中文字被切半
BAD_JSON = '{"audit_id": "4", "op": "wri'.encode("utf-8")                                    # 被別人蓋掉的半行


def _line(d: dict) -> bytes:
    return (json.dumps(d, ensure_ascii=False) + "\n").encode("utf-8")


def _corrupt_log(path: Path) -> bytes:
    raw = _line(GOOD) + BAD_UTF8 + b"\n" + BAD_JSON + b"\n" + _line(GOOD2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


_WRITER = r"""
import sys
sys.path.insert(0, sys.argv[1])
from lib import atom_io
me = sys.argv[2]
for i in range(int(sys.argv[3])):
    atom_io._audit_log({"audit_id": f"{me}-{i}", "op": "write", "source": "test",
                        "path": "memory/驗證與實證/很長的中文卡片名稱-放大多位元組字元比例-" + me + ".md",
                        "note": "中文" * (i % 37) + "x" * (i % 5)})
"""


def test_concurrent_appends_stay_valid_utf8_json(tmp_path):
    """修前：8×500 有 382 行非 UTF-8；這裡 6 行程×150 行，要求一行不壞、一行不少。"""
    data = tmp_path / "data"
    env = dict(os.environ, WG_CLAUDE_DIR=str(data))
    procs = [subprocess.Popen([sys.executable, "-X", "utf8", "-c", _WRITER, str(ROOT), f"w{k}", "150"], env=env,
                              stderr=subprocess.PIPE) for k in range(6)]
    errs = [p.communicate(timeout=180)[1].decode("utf-8", "replace") for p in procs]
    assert all(p.returncode == 0 for p in procs), errs
    log = data / "memory" / "_meta" / "atom_io_audit.jsonl"
    lines = [x for x in log.read_bytes().split(b"\n") if x]
    bad = []
    for n, x in enumerate(lines, 1):
        try:
            json.loads(x.decode("utf-8"))
        except ValueError:      # UnicodeDecodeError 也是 ValueError
            bad.append(n)
    assert bad == [] and len(lines) == 900, (len(lines), bad[:10])


def test_lone_surrogate_entry_is_written_and_read_back(tmp_path, monkeypatch):
    log = tmp_path / "_meta" / "atom_io_audit.jsonl"
    monkeypatch.setattr(atom_io, "AUDIT_LOG", log)
    atom_io._audit_log({"op": "write", "path": "memory/壞\udc80名.md"})   # 修前：UnicodeEncodeError 穿過 except OSError
    raw = log.read_bytes()
    entry = json.loads(raw.decode("utf-8"))                               # 檔內是合法 UTF-8
    assert entry["path"] == "memory/壞\udc80名.md"


def test_lock_unavailable_still_writes_and_says_so(tmp_path, monkeypatch, capsys):
    """鎖一直拿不到（別的行程卡住）→ 照寫並 stderr 告警：寧可冒一行被蓋，不讓稽核整筆消失。"""
    log = tmp_path / "_meta" / "atom_io_audit.jsonl"
    monkeypatch.setattr(atom_io, "AUDIT_LOG", log)
    monkeypatch.setattr(atom_io, "AUDIT_LOCK_WAIT_S", 0)

    def stuck(fh, *, unlock=False):
        if not unlock:
            raise OSError(36, "模擬別人一直拿著鎖")

    monkeypatch.setattr(atom_io, "_lock_byte", stuck)
    atom_io._audit_log({"op": "write", "path": "memory/甲.md"})
    assert json.loads(log.read_bytes().decode("utf-8"))["path"] == "memory/甲.md"
    assert "稽核帳鎖拿不到" in capsys.readouterr().err


def test_reader_skips_bad_lines_with_one_stderr_signal(tmp_path, capsys):
    log = tmp_path / "atom_io_audit.jsonl"
    _corrupt_log(log)
    got = atom_io.iter_audit_entries(log)
    assert [e["audit_id"] for e in got] == ["1", "2"]
    err = capsys.readouterr().err
    assert "2 行" in err and "第 2、3 行" in err and "--repair" in err, err


def test_backfill_reader_survives_bad_bytes_and_says_so(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("atom_provenance_backfill_audit_ut",
                                                  ROOT / "tools" / "atom-provenance-backfill.py")
    bf = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bf
    spec.loader.exec_module(bf)
    log = tmp_path / "atom_io_audit.jsonl"
    _corrupt_log(log)
    monkeypatch.setattr(bf, "AUDIT_LOG", log)
    got = bf._audit_earliest_by_basename()
    assert set(got) == {"甲.md", "乙.md"} or set(got) == {bf._norm("甲.md"), bf._norm("乙.md")}, got
    assert "--repair" in capsys.readouterr().err                           # 修前：壞行無聲略過


def _run_tool(*args, env_dir: Path):
    env = dict(os.environ, WG_CLAUDE_DIR=str(env_dir))
    return subprocess.run([sys.executable, "-X", "utf8", str(TOOL), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=60)


def test_repair_rewrites_bad_lines_and_keeps_raw_bytes(tmp_path):
    log = tmp_path / "atom_io_audit.jsonl"
    raw = _corrupt_log(log)
    chk = _run_tool("--check", "--path", str(log), env_dir=tmp_path / "data")
    assert chk.returncode == 1 and "ATOM_IO_AUDIT_CHECK FAIL" in chk.stdout, chk.stdout + chk.stderr
    rep = _run_tool("--repair", "--path", str(log), env_dir=tmp_path / "data")
    assert rep.returncode == 0, rep.stdout + rep.stderr
    lines = log.read_bytes().split(b"\n")
    entries = [json.loads(x.decode("utf-8")) for x in lines if x]          # 每行都合法
    assert len(entries) == 4 and entries[0]["audit_id"] == "1" and entries[3]["audit_id"] == "2"   # 好行原位不動
    fixed = [e for e in entries if e.get("op") == "audit_line_repaired"]
    assert [e["line"] for e in fixed] == [2, 3]
    assert bytes.fromhex(fixed[0]["raw_hex"]) == BAD_UTF8 and bytes.fromhex(fixed[1]["raw_hex"]) == BAD_JSON
    backups = [p for p in tmp_path.iterdir() if p.name.startswith("atom_io_audit.jsonl.pre-repair-")]
    assert len(backups) == 1 and backups[0].read_bytes() == raw              # 原始位元組整份留在旁檔
    assert all(e["backup"] == backups[0].name for e in fixed)
    again = _run_tool("--check", "--path", str(log), env_dir=tmp_path / "data")
    assert again.returncode == 0 and "ATOM_IO_AUDIT_CHECK PASS" in again.stdout, again.stdout
    noop = _run_tool("--repair", "--path", str(log), env_dir=tmp_path / "data")
    assert noop.returncode == 0 and len([p for p in tmp_path.iterdir() if ".pre-repair-" in p.name]) == 1
