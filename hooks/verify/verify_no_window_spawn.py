#!/usr/bin/env python3
"""verify_no_window_spawn — hooks/lib 內 subprocess 呼叫必須帶壓窗參數。

背景：hook 行程是 GUI pythonw（無 console）。它 spawn 任何 console 程式（git/svn/python…）
若不帶 creationflags=CREATE_NO_WINDOW（或 startupinfo），Windows 會彈可見 console 宿主窗（閃窗）。
本掃描把「漏帶旗標」變成 verify 失敗，防止新增程式碼再引入閃窗。

規則：掃 hooks/*.py、hooks/handlers/*.py、lib/*.py（排除 verify/ 測試碼）中所有
subprocess.run/Popen/check_output/check_call/call 呼叫（含 import 別名），
呼叫必須滿足其一：
  - keyword 帶 creationflags= 或 startupinfo=
  - keyword 帶 **kwargs 展開（旗標由呼叫端組裝，如 _shared 的 spawn helper）
  - 呼叫行上方或同行有 `# no-window-exempt: <理由>` 註記（POSIX-only 分支等）
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[2]
SCAN_DIRS = [CLAUDE / "hooks", CLAUDE / "hooks" / "handlers", CLAUDE / "lib"]
SPAWN_FUNCS = {"run", "Popen", "check_output", "check_call", "call"}
EXEMPT_MARK = "no-window-exempt:"


def subprocess_aliases(tree: ast.AST) -> set:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "subprocess":
                    names.add(a.asname or a.name)
    return names


def check_file(path: Path) -> list:
    src = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"{path.name}: SyntaxError {e}"]
    aliases = subprocess_aliases(tree)
    if not aliases:
        return []
    lines = src.splitlines()
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                and f.value.id in aliases and f.attr in SPAWN_FUNCS):
            continue
        kw_names = {k.arg for k in node.keywords}  # **kwargs 展開 → arg=None
        if "creationflags" in kw_names or "startupinfo" in kw_names or None in kw_names:
            continue
        ctx = "\n".join(lines[max(0, node.lineno - 2): node.lineno])
        if EXEMPT_MARK in ctx:
            continue
        problems.append(f"{path.relative_to(CLAUDE)}:{node.lineno} subprocess.{f.attr} 未帶 creationflags/startupinfo")
    return problems


def main() -> int:
    seen, problems = set(), []
    for d in SCAN_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.py")):
            if p in seen or "verify" in p.parts:
                continue
            seen.add(p)
            problems += check_file(p)
    if problems:
        print(f"FAIL verify_no_window_spawn: {len(problems)} 個 spawn 點漏帶壓窗參數（會閃 console 窗）")
        for x in problems:
            print(f"  - {x}")
        return 1
    print(f"PASS verify_no_window_spawn: {len(seen)} 檔掃描，所有 subprocess 呼叫皆帶壓窗參數或豁免註記")
    return 0


if __name__ == "__main__":
    sys.exit(main())
