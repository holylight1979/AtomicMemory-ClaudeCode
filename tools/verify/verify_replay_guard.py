"""verify_replay_guard.py — tools/replay-guard.py 的沙箱外路徑偵測（paths_outside／pre）。

做什麼：網址（http://、https://）不能被當成磁碟絕對路徑擋下；真的沙箱外路徑（含 file:///C:/…）照擋。
起因：第二意見材料的 diff 含 `curl -s http://127.0.0.1:3849/...`，舊正則把「p://」當 P 槽路徑 → pre FAIL、Codex 起不來。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_replay_guard.py
"""
import argparse
import importlib.util
import re
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "replay_guard", Path(__file__).resolve().parents[1] / "replay-guard.py")
rg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rg)

_URLS = ("curl -s http://127.0.0.1:3849/index/full\n"
         "見 https://example.com/a/b 與 HTTP://HOST:8080/x\n")


def test_urls_are_not_disk_paths(tmp_path):
    # 前置：舊規則（磁碟代號前不限字元）確實會在這段命中，案例才不是「什麼都沒發生」而通過
    assert re.search(r"[A-Za-z]:[/\\][^\s\"'`)\]]+", _URLS)
    assert rg.paths_outside(_URLS, tmp_path) == []


def test_real_outside_paths_still_caught(tmp_path):
    text = 'type "C:\\outside\\secret.txt" 再讀 file:///D:/repo/notes.md'
    got = rg.paths_outside(text, tmp_path)
    assert any("outside" in p for p in got), got
    assert any(p.startswith("D:/repo") for p in got), got


def test_pre_passes_url_but_fails_outside_path(tmp_path, capsys):
    sandbox = tmp_path / "job"
    sandbox.mkdir()
    ok = sandbox / "ok.md"
    ok.write_text("diff 片段：" + _URLS, encoding="utf-8")
    assert rg.cmd_pre(argparse.Namespace(prompt=str(ok), sandbox=str(sandbox), sealed=None)) == 0
    assert capsys.readouterr().out.strip().endswith("REPLAY_GUARD_CHECK PASS")

    bad = sandbox / "bad.md"
    bad.write_text("請讀 C:/outside/answer.md\n", encoding="utf-8")
    assert rg.cmd_pre(argparse.Namespace(prompt=str(bad), sandbox=str(sandbox), sealed=None)) == 1
    out = capsys.readouterr().out
    assert "C:/outside/answer.md" in out and out.strip().endswith("REPLAY_GUARD_CHECK FAIL")
