"""verify_spawned_tools_from_code_root.py：hook 要執行／載入的 tools、hooks 腳本取自程式碼根（本樹），給腳本的資料參數仍是資料根。

做什麼：把 subprocess.run／Popen 換成替身（不真的 spawn），呼叫各 hook 的起腳本函式，斷言 argv 裡的腳本在本樹，
cwd／--memory-dir 這類資料參數仍是 CLAUDE_DIR（資料根）。資料根在測試裡指到 tmp，所以「腳本在本樹、資料在 tmp」兩者能分開驗。
涵蓋：wg_atoms._trigger_sync_memory_index、wg_atoms._load_tool_module、wg_extraction._spawn_extract_worker、
handlers.session_start._followup_advisory、wg_vcs_sync._run_index_tools。其餘位置由 verify_code_paths_from_code_root 靜態守門。
反例：腳本路徑不得來自 live ~/.claude（在 live 底下、不在本樹的才算，本樹放在 ~/.claude/.claude/worktrees/ 也照判；
判法自己的反例見 test_not_live_*）；資料參數不得落在本樹。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_spawned_tools_from_code_root.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
TREE = HOOKS_DIR.parent
LIVE = Path.home() / ".claude"
os.environ.setdefault("WG_CLAUDE_DIR", str(TREE))
sys.path.insert(0, str(HOOKS_DIR))

import wg_atoms  # noqa: E402
import wg_core  # noqa: E402
import wg_extraction  # noqa: E402
import wg_vcs_sync  # noqa: E402
from handlers import session_start  # noqa: E402


def _n(p) -> str:
    return os.path.normcase(os.path.realpath(str(p)))


def _in_tree(p) -> bool:
    return _n(p).startswith(_n(TREE) + os.sep)


def _not_live(p, tree: Path = TREE, live: Path = LIVE) -> bool:
    """不是從正式安裝載入：不在 live ~/.claude 底下，或在本樹裡（本樹放在 ~/.claude/.claude/worktrees/ 時本樹的檔不算 live，
    live 那份與別棵工作樹照算；本樹就是 live 時恆真）。"""
    n = _n(p)
    return n.startswith(_n(tree) + os.sep) or not n.startswith(_n(live) + os.sep)


class _Proc:
    pid = 4242
    returncode = 0
    stdout = ""
    stderr = ""

    class stdin:                                                                        # noqa: N801
        @staticmethod
        def write(_b):
            return None

        @staticmethod
        def close():
            return None


@pytest.fixture
def calls(monkeypatch):
    seen = []

    def fake(argv, *a, **kw):
        seen.append((list(argv), kw.get("cwd")))
        return _Proc()
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr(subprocess, "Popen", fake)
    return seen


def test_trigger_sync_memory_index_script_in_tree_cwd_is_data_root(tmp_path, monkeypatch, calls):
    monkeypatch.setattr(wg_atoms, "CLAUDE_DIR", tmp_path / "data")
    assert wg_atoms._trigger_sync_memory_index(tmp_path / "mem") is None
    argv, cwd = calls[0]
    assert _n(argv[1]) == _n(TREE / "tools" / "sync-memory-index.py") and _not_live(argv[1])
    assert _n(cwd) == _n(tmp_path / "data") and argv[-1] == str(tmp_path / "mem")         # 資料參數不動


def test_load_tool_module_loads_this_trees_file(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_atoms, "CLAUDE_DIR", tmp_path / "data")                       # 資料根沒有 tools/：從那裡載就會失敗
    mod = wg_atoms._load_tool_module("realm_llm_classify.py", "realm_llm_classify_a3probe")
    assert mod is not None and _in_tree(mod.__file__) and _not_live(mod.__file__)


def test_spawn_extract_worker_runs_this_trees_worker(tmp_path, monkeypatch, calls):
    (tmp_path / "data" / "workflow").mkdir(parents=True)
    monkeypatch.setattr(wg_extraction, "CLAUDE_DIR", tmp_path / "data")                  # worker log 落 tmp（資料）
    monkeypatch.setattr(wg_core, "append_guard_log", lambda *a, **kw: None)
    assert wg_extraction._spawn_extract_worker({"session_id": "s"}) == 4242
    argv, _ = calls[0]
    assert _n(argv[1]) == _n(TREE / "hooks" / "extract-worker.py") and _not_live(argv[1])
    assert (tmp_path / "data" / "workflow" / "extract-worker.log").exists()


def test_followup_advisory_runs_this_trees_checker(tmp_path, monkeypatch, calls):
    (tmp_path / "followups.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(session_start, "WORKFLOW_DIR", tmp_path)
    session_start._followup_advisory()
    argv, _ = calls[0]
    assert _n(argv[1]) == _n(TREE / "tools" / "followup-check.py") and _not_live(argv[1])


def test_run_index_tools_script_in_tree_memory_dir_and_cwd_are_data(tmp_path, monkeypatch):
    mem = tmp_path / "data" / "memory"
    mem.mkdir(parents=True)
    (mem / "_atom_index.json").write_text("{}", encoding="utf-8")
    seen = []
    monkeypatch.setattr(wg_vcs_sync, "CLAUDE_DIR", tmp_path / "data")
    monkeypatch.setattr(wg_vcs_sync, "_run", lambda argv, cwd, timeout, env: seen.append((argv, cwd)) or _Proc())
    wg_vcs_sync._run_index_tools(SimpleNamespace(mem_dirs=[mem]), 5, {}, lambda m: None, [["sync-memory-index.py", "--check"]])
    argv, cwd = seen[0]
    assert _n(argv[1]) == _n(TREE / "tools" / "sync-memory-index.py") and _not_live(argv[1])
    assert argv[-2:] == ["--memory-dir", str(mem)] and _n(cwd) == _n(tmp_path / "data")
    assert not _in_tree(cwd)                                                            # 反例：cwd（資料）不得變成本樹


def test_not_live_catches_live_copy_but_not_this_nested_tree(tmp_path):
    """反例：本樹放在 live 底下（~/.claude/.claude/worktrees/wt）→ 本樹的腳本不算 live，live 那份、名字前綴相同的別棵工作樹照算；
    本樹在 live 外、本樹就是 live，判法照舊。"""
    live = tmp_path / "home" / ".claude"
    wt = live / ".claude" / "worktrees" / "wt"
    script = Path("tools") / "sync-memory-index.py"
    assert _not_live(wt / script, wt, live)
    assert not _not_live(live / script, wt, live)                                       # 工作樹的程式起了 live 那份 → 抓到
    assert not _not_live(live / ".claude" / "worktrees" / "wt2" / script, wt, live)
    outside = tmp_path / "wt"
    assert _not_live(outside / script, outside, live) and not _not_live(live / script, outside, live)
    assert _not_live(live / script, live, live)


def test_code_dir_equals_home_claude_in_live_layout():
    """live 下新舊路徑相同：hooks 由 ~/.claude/hooks 起時 CODE_DIR＝~/.claude（本樹是 live 時直接比；否則比算法）。"""
    live_core = LIVE / "hooks" / "wg_core.py"
    if live_core.is_file():
        assert _n(live_core.resolve().parents[1]) == _n(LIVE)
    assert _n(wg_core.CODE_DIR) == _n(TREE)
