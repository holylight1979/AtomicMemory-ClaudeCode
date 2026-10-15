"""verify_reload_advice.py：收尾時 AI 叫使用者 Reload Window，程式先查工具服務是不是已經跑最新程式（規則 RELOAD_ADVICE_ALREADY_LOADED）。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_reload_advice.py
事實來源：每個 MCP 服務程序啟動時寫 workflow/mcp-boot/<pid>.json（code_mtime＝啟動時載入的程式版本、heartbeat_at 每分鐘更新）；
磁碟版本＝server.js 與 lib/*.js 最新的修改時間（與服務端 codeMtime 同算法）。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

VERIFY = Path(__file__).resolve().parent
sys.path.insert(0, str(VERIFY))

from verify_stop_reconcile import (  # noqa: E402,F401
    _git_budget_generous, _scope_ledger_isolated, _temp_rules_off, driven, st,
)


def _code_tree(tmp_path: Path, mtime: float) -> Path:
    """假的 MCP 程式目錄：server.js 與 lib/a.js，修改時間都設成 mtime。"""
    d = tmp_path / "mcp"
    (d / "lib").mkdir(parents=True)
    for f in (d / "server.js", d / "lib" / "a.js"):
        f.write_text("//\n", encoding="utf-8")
        os.utime(f, (mtime, mtime))
    return d


def _boot(dir_: Path, pid: int, code_mtime_ms: float, heartbeat_s: float) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / f"{pid}.json").write_text(json.dumps({"pid": pid, "code_mtime": code_mtime_ms, "booted_at": heartbeat_s * 1000,
                                                  "heartbeat_at": heartbeat_s * 1000}), encoding="utf-8")


def test_load_facts_reads_records_and_disk_version(tmp_path, capsys, monkeypatch):
    """事實讀取以「正在跑的服務程序」為準：有紀錄的給 (載入版本, 心跳秒)；在跑卻沒紀錄的（加這功能之前啟動的舊版服務，
    別的視窗還沒重載）給 (None, 現在)，規則就判不出、放行；有紀錄但程序已不在的（被殺掉的測試服務）不算；
    壞檔跳過並 stderr 說一聲；磁碟版本是程式目錄最新的修改時間（毫秒）。"""
    now = time.time()
    code = _code_tree(tmp_path, now - 100)
    boots = tmp_path / "mcp-boot"
    _boot(boots, 11, (now - 100) * 1000, now - 20)
    _boot(boots, 13, (now - 100) * 1000, now - 10)                       # 程序已結束（被殺掉的測試服務）
    (boots / "12.json").write_text("{壞", encoding="utf-8")
    monkeypatch.setattr(st, "_running_mcp_pids", lambda *a, **k: {11, 12, 14})
    records, disk = st._mcp_load_facts(boots, code)
    assert ((now - 100) * 1000, now - 20) in records and len(records) == 3
    assert sum(1 for m, _ in records if m is None) == 2                    # 12（紀錄壞了）與 14（沒紀錄）都判不出
    assert disk is not None and abs(disk - (now - 100) * 1000) < 2
    assert "12.json" in capsys.readouterr().err


def test_load_facts_unknown_when_processes_cannot_be_listed(tmp_path, monkeypatch):
    """列不出在跑的服務程序 → 不回任何紀錄（判不出、放行），不拿檔案猜。"""
    now = time.time()
    code = _code_tree(tmp_path, now - 100)
    _boot(tmp_path / "mcp-boot", 11, (now - 100) * 1000, now - 20)
    monkeypatch.setattr(st, "_running_mcp_pids", lambda *a, **k: None)
    assert st._mcp_load_facts(tmp_path / "mcp-boot", code)[0] == []


_MCP_CMD = r"node C:\Users\u\.claude\tools\workflow-guardian-mcp\server.js"
_ROWS = [  # (pid, ppid, 程式名, 指令列)：照實測的程序樹（每個 session 一個 claude.exe，服務經 pythonw 外殼掛在它底下）
    (52236, 1, "Code.exe", ""), (99724, 52236, "Code.exe", ""),
    (103168, 99724, "claude.exe", ""), (99736, 103168, "pythonw.exe", "run-hidden.py " + _MCP_CMD),   # 外殼的指令列也帶 server.js
    (86916, 99736, "node.exe", _MCP_CMD),
    (136028, 99724, "claude.exe", ""), (77004, 136028, "pythonw.exe", "run-hidden.py " + _MCP_CMD),
    (89192, 77004, "node.exe", _MCP_CMD),
    (139148, 136028, "cmd.exe", ""), (139200, 139148, "pythonw.exe", "workflow-guardian.py"),
]


@pytest.mark.parametrize("self_pid, expected", [
    (139200, {89192}),            # 收尾閘屬於 claude.exe 136028 → 只看它底下的服務 89192，不看別的 session 的 86916
    (999, {86916, 89192}),        # 找不到所屬的 claude.exe → 退回全機所有服務（保守）
])
def test_session_mcp_pids_follow_process_tree(self_pid, expected):
    """實證（10-15）：每個 session（claude.exe）各有自己的工具服務程序，不是整個視窗共用一個。收尾閘只看自己這個 session 的服務；
    別的 session 的舊服務不影響這個 session 的判斷（codex WARN：舊服務在別的 session 時會漏擋）。"""
    assert st._session_mcp_pids(_ROWS, self_pid) == expected


@pytest.mark.parametrize("stale, text, blocked", [
    (False, "全部完成了。新工具要生效，請 Reload Window。", True),
    (True, "全部完成了。新工具要生效，請 Reload Window。", False),
    (False, "全部完成了。改了 MCP 啟動參數，請 Reload Window。重載原因：啟動參數改了", False),   # codex BLOCK：程式更新以外的理由
])
def test_stop_blocks_redundant_reload_advice(driven, capsys, monkeypatch, stale, text, blocked):
    """收尾文字叫使用者 Reload Window：在跑的服務都已載入最新 → 擋一次，告訴它不必叫使用者重載、有別的理由就寫「重載原因：…」；
    有舊的 → 照常放行；AI 已寫明重載原因 → 照它的判斷放行。"""
    disk = 1_792_045_981_215.0
    loaded = disk - 60_000 if stale else disk
    monkeypatch.setattr(st, "_mcp_load_facts", lambda *a, **k: ([(loaded, time.time() - 30)], disk))
    out, _, _ = driven(text, capsys)
    assert ("RELOAD_ADVICE_ALREADY_LOADED" in out) is blocked, out
    if blocked:
        assert "重載原因：" in out
