"""verify_aec_ledger.py — per-session 殘檔帳本（handlers/aec_ledger.py）行為驗證。

契約：帳本只記「進過帳」的路徑，「還在不在」由讀端 exists() 判定；(d) 一行一路徑只收此刻存在者；
scratchpad 掃描依 cwd slug 定位；append 去重（scan 不覆寫既有 note）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from handlers import aec_ledger as L  # noqa: E402

_SID = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def wdir(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "WORKFLOW_DIR", tmp_path / "workflow")
    return tmp_path


def test_cwd_slug_matches_claude_code_convention():
    assert L._cwd_slug(r"c:\Users\x\.claude") == "c--Users-x--claude"
    assert L._cwd_slug(r"d:\AI-PLAY\AI-gen-projs\MudClient-withAI") == "d--AI-PLAY-AI-gen-projs-MudClient-withAI"


def test_scan_scratchpad_lists_top_level_only(wdir, monkeypatch):
    tmp = wdir / "tmp"
    sp = tmp / "claude" / "c--proj" / _SID / "scratchpad"
    (sp / "build-c").mkdir(parents=True)
    (sp / "build-c" / "nested.exe").write_text("x")
    (sp / "a.py").write_text("x")
    monkeypatch.setattr(L, "_tempdir", lambda: str(tmp))
    got = L.scan_scratchpad(r"c:\proj", _SID)
    names = sorted(Path(e["path"]).name for e in got)
    assert names == ["a.py", "build-c"]
    assert all(e["source"] == "scan" for e in got)


def test_scan_scratchpad_drive_letter_case_fallback(wdir, monkeypatch):
    tmp = wdir / "tmp"
    sp = tmp / "claude" / "C--proj" / _SID / "scratchpad"   # 大寫磁碟機
    sp.mkdir(parents=True)
    (sp / "z.txt").write_text("x")
    monkeypatch.setattr(L, "_tempdir", lambda: str(tmp))
    got = L.scan_scratchpad(r"c:\proj", _SID)                # cwd 小寫
    assert [Path(e["path"]).name for e in got] == ["z.txt"]


def test_parse_d_paths_only_existing_and_skips_prose(wdir):
    cwd = wdir / "proj"
    (cwd / "scratch").mkdir(parents=True)
    (cwd / "scratch" / "a.log").write_text("x")
    (cwd / "scratch" / "b.log").write_text("x")
    (cwd / "keep.bak").write_text("x")
    d = "\n".join([
        "- scratch/*.log — 一次性驅動輸出",
        "keep.bak：保留，使用者要回滾可用",
        "scratch/gone.tmp — 已刪",
        "純 prose 說明行沒有路徑",
        "無",
    ])
    got = L.parse_d_paths(d, str(cwd))
    names = sorted(Path(e["path"]).name for e in got)
    assert names == ["a.log", "b.log", "keep.bak"]
    by = {Path(e["path"]).name: e for e in got}
    assert by["keep.bak"]["note"].startswith("保留")
    assert by["a.log"]["note"] == "一次性驅動輸出"
    assert all(e["source"] == "aec-d" for e in got)


def test_parse_d_paths_expands_env_and_home(wdir, monkeypatch):
    target = wdir / "envdir" / "t.txt"
    target.parent.mkdir()
    target.write_text("x")
    monkeypatch.setenv("WG_TEST_ENV", str(wdir / "envdir"))
    got = L.parse_d_paths("%WG_TEST_ENV%/t.txt — 備份" if sys.platform == "win32" else "$WG_TEST_ENV/t.txt — 備份", "")
    assert [Path(e["path"]).name for e in got] == ["t.txt"]


def test_ledger_append_dedupes_and_read_last_wins(wdir):
    p1 = wdir / "x.tmp"; p1.write_text("x")
    n = L.ledger_append(_SID, [{"path": str(p1), "note": "", "source": "write"}], 3)
    assert n == 1
    # 同路徑 scan 再進 → 不追加
    assert L.ledger_append(_SID, [{"path": str(p1), "note": "scratchpad", "source": "scan"}]) == 0
    # 同路徑 aec-d 帶新 note → 追加一筆覆寫 note
    assert L.ledger_append(_SID, [{"path": str(p1), "note": "回滾用", "source": "aec-d"}]) == 1
    recs = L.ledger_read(_SID)
    assert len(recs) == 1 and recs[0]["note"] == "回滾用" and recs[0]["source"] == "aec-d"
    # 大小寫不同視為同路徑（Windows）
    if sys.platform == "win32":
        assert L.ledger_append(_SID, [{"path": str(p1).upper(), "note": "回滾用", "source": "aec-d"}]) == 0
    raw = L.ledger_path(_SID).read_text(encoding="utf-8").strip().splitlines()
    assert len(raw) == 2 and json.loads(raw[0])["turn_seq"] == 3


def test_record_temp_write_only_under_tempdir(wdir, monkeypatch):
    tmp = wdir / "tmp"; tmp.mkdir()
    monkeypatch.setattr(L, "_tempdir", lambda: str(tmp))
    L.record_temp_write(_SID, str(tmp / "s" / "a.py"))
    L.record_temp_write(_SID, str(wdir / "proj" / "real.py"))
    recs = L.ledger_read(_SID)
    assert [Path(r["path"]).name for r in recs] == ["a.py"]
    assert recs[0]["source"] == "write"


def test_collect_at_completion_merges_d_and_scan(wdir, monkeypatch):
    tmp = wdir / "tmp"
    cwd = wdir / "proj"; cwd.mkdir()
    (cwd / "maps.bak").write_text("x")
    sp = tmp / "claude" / L._cwd_slug(str(cwd)) / _SID / "scratchpad"   # 真 cwd 推 slug
    sp.mkdir(parents=True)
    (sp / "run.ps1").write_text("x")
    monkeypatch.setattr(L, "_tempdir", lambda: str(tmp))
    n = L.collect_at_completion(_SID, str(cwd), "maps.bak — 實機前備份", 7)
    assert n == 2
    names = sorted(Path(r["path"]).name for r in L.ledger_read(_SID))
    assert names == ["maps.bak", "run.ps1"]


def test_ledger_read_missing_or_corrupt_fail_open(wdir):
    assert L.ledger_read(_SID) == []
    p = L.ledger_path(_SID); p.parent.mkdir(parents=True)
    p.write_text('{"path": "a"}\nnot json\n{"nopath": 1}\n', encoding="utf-8")
    assert [r["path"] for r in L.ledger_read(_SID)] == ["a"]
