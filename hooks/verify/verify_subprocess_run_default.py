"""verify_subprocess_run_default.py：跑子行程的函式不把 subprocess.run 綁成參數預設值（規則 SUBPROCESS_RUN_LOOKED_UP_AT_CALL）。

做什麼：`def f(run=subprocess.run)` 在定義那一刻就綁住真的 subprocess.run，測試的 git 錄製重播（換掉 subprocess.run）攔不到，
結果看匯入順序、錄製檔對不上（CassetteMismatch）。改成預設 None、呼叫當下才取 subprocess.run（同 wg_unknown_write.recover）。
正例：hooks（不含 verify）沒有任何參數預設值是 subprocess.run；note_git_launcher 沒給 run 時用的是呼叫當下的 subprocess.run。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_subprocess_run_default.py
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_verify_ledger as vl  # noqa: E402


def _is_subprocess_run(node) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "run" and isinstance(node.value, ast.Name)
            and node.value.id == "subprocess")


def test_no_parameter_defaults_to_subprocess_run():
    hits = []
    for p in sorted(HOOKS_DIR.rglob("*.py")):
        if "verify" in p.relative_to(HOOKS_DIR).parts:
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                defaults = [*n.args.defaults, *(d for d in n.args.kw_defaults if d is not None)]
                hits += [f"{p.relative_to(HOOKS_DIR).as_posix()}:{d.lineno}" for d in defaults if _is_subprocess_run(d)]
    assert not hits, hits


def test_note_git_launcher_uses_subprocess_run_patched_after_import(tmp_path, monkeypatch):
    """模組匯入之後才換掉 subprocess.run（錄製重播就是這樣）：沒給 run 的呼叫要用到換掉的那支。"""
    repo = tmp_path / "wt"
    (repo / ".git").mkdir(parents=True)
    launcher = repo / "_vc.py"
    launcher.write_text('import subprocess\nsubprocess.run(["git", "status"])\n', encoding="utf-8")
    assert vl.is_git_launcher_source(launcher.read_text(encoding="utf-8")), "前置：內容只跑 git"
    monkeypatch.setattr(vl, "LAUNCHER_DIR", tmp_path / "markers")
    calls = []

    def fake_run(args, *a, **k):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 1, b"", b"")       # ls-files --error-unmatch 非零＝沒追蹤
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert vl.note_git_launcher(str(launcher)) is True
    assert calls and calls[0][:2] == ["git", "-C"] and "ls-files" in calls[0]
