#!/usr/bin/env python3
"""verify_lf_writes — hooks/lib/tools/skills 內文字模式寫檔必須帶 newline= 控制。

背景：本 repo 只收 LF（.gitattributes `* text=auto eol=lf`）。
Windows 上 Python 文字模式寫檔，沒給 newline= 就會把 `\\n` 翻成 `\\r\\n`。
行尾翻掉的檔進 git 會整檔 diff，索引三檔多機合併必衝突。
本掃描把「文字模式寫檔漏帶 newline=」變成 verify 失敗，防止新增程式碼再引入平台換行翻譯。
本守門只保證「不做平台換行翻譯」；內容本身是 LF 由 lib.atom_io.write_text_lf / normalize_lf 保證，
結果由 `python tools/normalize-eol.py --root --check` 掃。

規則：遞迴掃 hooks/、lib/、tools/、skills/ 下 *.py（排除路徑含 verify、__pycache__、node_modules、
_archived、_archive、v4-archive），以下呼叫若為文字模式且沒帶合格 newline= 即列為問題：
  - open(...) / io.open(...) / <任何>.open(...)：mode（第 2 個位置引數或 mode=）為常數字串且
    含 w/a/x/+ 之一、不含 b → 文字寫入；mode 省略視為 "r" 不算；mode 非常數 → 無法證明安全，算問題
    （os.open 是 fd 層、沒有文字模式，不在此列）
  - <任何>.write_text(...)：一律要帶 newline=
  - tempfile.NamedTemporaryFile / TemporaryFile / SpooledTemporaryFile：mode（mode= 或第 1 個位置
    引數）為常數且含 w/a/+ 之一、不含 b → 文字模式；mode 省略為 "w+b" 二進位不算
newline= 只接受常數 "" 或 "\\n"；newline=None、非常數值、**kwargs 展開都不算控制。
豁免：呼叫行或其上一行有 `# lf-exempt: <理由>` 註記（stdio、二進位包裝等）。
檔案 SyntaxError 不跳過，直接列為問題。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[2]
SCAN_DIRS = [CLAUDE / "hooks", CLAUDE / "lib", CLAUDE / "tools", CLAUDE / "skills"]
EXCLUDE_PARTS = {"verify", "__pycache__", "node_modules", "_archived", "_archive", "v4-archive"}
TEMPFILE_FUNCS = {"NamedTemporaryFile", "TemporaryFile", "SpooledTemporaryFile"}
OPEN_TEXT_WRITE_CHARS = set("wax+")
TEMPFILE_TEXT_CHARS = set("wa+")
NEWLINE_OK = {"", "\n"}
EXEMPT_MARK = "lf-exempt:"


def _classify(node: ast.Call) -> tuple:
    """回 (種類, 顯示名)：種類為 open / write_text / tempfile；不相干回 (None, '')。"""
    f = node.func
    if isinstance(f, ast.Name):
        if f.id == "open":
            return "open", "open"
        if f.id in TEMPFILE_FUNCS:
            return "tempfile", f.id
        return None, ""
    if isinstance(f, ast.Attribute):
        if f.attr == "open":
            if isinstance(f.value, ast.Name) and f.value.id == "os":
                return None, ""
            return "open", "open"
        if f.attr == "write_text":
            return "write_text", "write_text"
        if f.attr in TEMPFILE_FUNCS:
            return "tempfile", f.attr
    return None, ""


def _mode_arg(node: ast.Call, pos: int):
    for k in node.keywords:
        if k.arg == "mode":
            return k.value
    if len(node.args) > pos:
        return node.args[pos]
    return None


def _is_text_write(mode_node, chars: set) -> tuple:
    """回 (是否文字寫入, mode 描述)。mode 省略 → 不是；mode 非常數 → 視為是（無法證明安全）。"""
    if mode_node is None:
        return False, ""
    if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
        m = mode_node.value
        return ("b" not in m and any(c in m for c in chars)), f"mode={m!r}"
    return True, "mode=<非常數>"


def _newline_verdict(node: ast.Call):
    """None = 有合格 newline= 控制；否則回傳問題描述。"""
    for k in node.keywords:
        if k.arg == "newline":
            v = k.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str) and v.value in NEWLINE_OK:
                return None
            if isinstance(v, ast.Constant) and v.value is None:
                return "newline=None 等於沒控（平台換行）"
            return "newline=<非常數> 無法證明"
    return "缺 newline="


def check_source(src: str, label: str) -> list:
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"{label}: SyntaxError {e}"]
    lines = src.splitlines()
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kind, name = _classify(node)
        if kind is None:
            continue
        if kind == "open":
            hit, desc = _is_text_write(_mode_arg(node, 1), OPEN_TEXT_WRITE_CHARS)
        elif kind == "tempfile":
            hit, desc = _is_text_write(_mode_arg(node, 0), TEMPFILE_TEXT_CHARS)
        else:
            hit, desc = True, ""
        if not hit:
            continue
        verdict = _newline_verdict(node)
        if verdict is None:
            continue
        ctx = "\n".join(lines[max(0, node.lineno - 2): node.lineno])
        if EXEMPT_MARK in ctx:
            continue
        problems.append(f"{label}:{node.lineno} {name}({desc}) {verdict}")
    return problems


def check_file(path: Path) -> list:
    try:
        label = path.relative_to(CLAUDE).as_posix()
    except ValueError:
        label = path.name
    src = path.read_text(encoding="utf-8", errors="replace")
    return check_source(src, label)


def main() -> int:
    seen, problems = set(), []
    for d in SCAN_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            if p in seen or EXCLUDE_PARTS & set(p.relative_to(CLAUDE).parts):
                continue
            seen.add(p)
            problems += check_file(p)
    if problems:
        print(f"FAIL verify_lf_writes: {len(problems)} 個文字模式寫檔點缺 newline= 控制（Windows 會寫成 CRLF）")
        for x in problems:
            print(f"  - {x}")
        return 1
    print(f"PASS verify_lf_writes: {len(seen)} 檔掃描，所有文字模式寫檔皆帶 newline= 控制或豁免註記")
    return 0


def test_rules_on_snippets(tmp_path):
    cases = [
        ('open(p, "w")', True),
        ('open(p, "w", newline="\\n")', False),
        ('open(p, "w", newline="")', False),
        ('open(p, "wb")', False),
        ("Path(p).write_text(s)", True),
        ('open(p, "w", **kw)', True),
        ('open(p, "w")  # lf-exempt: stdio', False),
        ('NamedTemporaryFile(mode="w")', True),
        ("NamedTemporaryFile()", False),
    ]
    for i, (snippet, flagged) in enumerate(cases):
        f = tmp_path / f"s{i}.py"
        f.write_text(snippet + "\n", encoding="utf-8", newline="\n")
        got = check_file(f)
        assert bool(got) == flagged, f"{snippet!r} -> {got}"


def test_main_passes():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
