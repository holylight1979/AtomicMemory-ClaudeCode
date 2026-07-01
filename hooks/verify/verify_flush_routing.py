"""verify_flush_routing.py — session_end auto-flush 落點路由。

驗證 extract-worker._flush_route：專案 session 的自動萃取知識 → 專案層 shared（只在該專案
注入），~/.claude session / 無 project root / 空 cwd → global。修「flush 一律 scope=global，
把專案專屬知識污染進 global core 並注入每個專案」缺口。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest  # noqa: F401

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

# 連字號檔名（extract-worker.py）無法 import，用 importlib 以路徑載入
_spec = importlib.util.spec_from_file_location(
    "extract_worker", HOOKS_DIR / "extract-worker.py")
ew = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ew)

CLAUDE_DIR = ew.CLAUDE_DIR
MEMORY_DIR = ew.MEMORY_DIR


def test_project_session_routes_to_shared():
    """有 project root 且非 ~/.claude → scope=shared、落專案 shared 層、project_cwd=cwd。"""
    proj = Path("C:/Projects/SomeGame") if sys.platform == "win32" else Path("/projects/somegame")
    scope, pcwd, dedup = ew._flush_route(str(proj / "src"), _find_root=lambda c: proj)
    assert scope == "shared"
    assert pcwd == str(proj / "src")
    assert dedup == proj / ".claude" / "memory" / "shared" / "_drafts" / "auto-capture"


def test_claude_dir_session_routes_to_global():
    """cwd 在 ~/.claude（finder 回 CLAUDE_DIR 自身）→ 不可進專案層、回 global。"""
    scope, pcwd, dedup = ew._flush_route(
        str(CLAUDE_DIR / "tools"), _find_root=lambda c: CLAUDE_DIR)
    assert (scope, pcwd, dedup) == ("global", None, MEMORY_DIR / "_drafts" / "auto-capture")


def test_no_project_root_routes_to_global():
    """找不到 project root → global（不會丟到不存在的專案層）。"""
    scope, pcwd, dedup = ew._flush_route("/tmp/whatever", _find_root=lambda c: None)
    assert (scope, pcwd, dedup) == ("global", None, MEMORY_DIR / "_drafts" / "auto-capture")


def test_empty_cwd_routes_to_global():
    """空 cwd → 直接 global、finder 不被呼叫。"""
    called = []

    def finder(c):
        called.append(c)
        return Path("X")

    scope, pcwd, dedup = ew._flush_route("", _find_root=finder)
    assert (scope, pcwd, dedup) == ("global", None, MEMORY_DIR / "_drafts" / "auto-capture")
    assert called == []
