"""verify_code_paths_from_code_root.py：hooks/、lib/ 找「程式碼」不得從使用者資料根組路徑（靜態守門）。

做什麼：以 ast 掃 hooks/、lib/ 的 .py（排除 verify/ 與 __pycache__），找出 `/` 串起來的路徑式；最左邊是資料根
（`CLAUDE_DIR`、`_CLAUDE_DIR`、`xxx.CLAUDE_DIR`，或 `Path.home() / ".claude"`），後面任一段是 "tools"、"hooks"、"lib"
或以 .py 結尾的字串 → 違規。程式碼根一律用 wg_core.CODE_DIR 或 Path(__file__).resolve().parents[N]；
WG_CLAUDE_DIR／家目錄只定位使用者資料（memory、workflow、config、Logs）。
允許清單只放真的是資料的例外，每筆附理由；目前是空的。
反例：test_guard_flags_data_root_code_paths 對一段合成原始碼（含多行、屬性、家目錄三種寫法）必須抓到。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_code_paths_from_code_root.py
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Tuple

TREE = Path(__file__).resolve().parents[2]
SCAN_DIRS = ("hooks", "lib")
CODE_SEGMENTS = {"tools", "hooks", "lib"}
DATA_ROOT_NAMES = {"CLAUDE_DIR", "_CLAUDE_DIR"}
# (相對路徑, 違規那一行的原始碼片段) → 為什麼它其實是資料
ALLOWLIST: dict = {}


def _chain(node: ast.AST) -> List[ast.AST]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _chain(node.left) + [node.right]
    return [node]


def _is_str(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _is_code_seg(node: ast.AST) -> bool:
    return _is_str(node) and (node.value in CODE_SEGMENTS or node.value.endswith(".py"))


def _data_root_len(ops: List[ast.AST]) -> int:
    """路徑式開頭是資料根 → 資料根佔幾段（1 或 2）；不是 → 0。"""
    head = ops[0]
    if isinstance(head, ast.Name) and head.id in DATA_ROOT_NAMES:
        return 1
    if isinstance(head, ast.Attribute) and head.attr == "CLAUDE_DIR":
        return 1
    is_home = (isinstance(head, ast.Call) and isinstance(head.func, ast.Attribute) and head.func.attr == "home")
    if is_home and len(ops) > 1 and _is_str(ops[1]) and ops[1].value == ".claude":
        return 2
    return 0


def violations(source: str, rel: str) -> List[Tuple[str, int, str]]:
    tree = ast.parse(source)
    lines = source.splitlines()
    inner = set()
    out: List[Tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)) or id(node) in inner:
            continue
        sub = node.left
        while isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Div):   # 只看最外層，內層是同一條式子的前綴
            inner.add(id(sub))
            sub = sub.left
        ops = _chain(node)
        n = _data_root_len(ops)
        if n and any(_is_code_seg(o) for o in ops[n:]):
            text = lines[node.lineno - 1].strip()
            if (rel, text) not in ALLOWLIST:
                out.append((rel, node.lineno, text))
    return out


def _scan() -> List[Tuple[str, int, str]]:
    found: List[Tuple[str, int, str]] = []
    for d in SCAN_DIRS:
        for p in sorted((TREE / d).rglob("*.py")):
            parts = set(p.relative_to(TREE).parts)
            if "verify" in parts or "__pycache__" in parts:
                continue
            found += violations(p.read_text(encoding="utf-8"), p.relative_to(TREE).as_posix())
    return found


def test_no_code_path_built_from_data_root():
    found = _scan()
    assert found == [], "程式碼位置從資料根組（改用 CODE_DIR／Path(__file__)）：\n" + "\n".join(
        f"{rel}:{ln}  {text}" for rel, ln, text in found)


def test_guard_flags_data_root_code_paths():
    src = (
        "from pathlib import Path\n"
        "a = CLAUDE_DIR / 'tools' / 'x.py'\n"
        "b = (CLAUDE_DIR\n     / 'hooks'\n     / 'w.py')\n"
        "c = wg_core.CLAUDE_DIR / 'lib'\n"
        "d = Path.home() / '.claude' / 'tools'\n"
        "e = _CLAUDE_DIR / 'tools'\n"
        "ok1 = CLAUDE_DIR / 'memory' / 'MEMORY.md'\n"
        "ok2 = CODE_DIR / 'tools' / 'x.py'\n"
        "ok3 = Path(__file__).resolve().parents[1] / 'lib'\n"
        "ok4 = Path.home() / '.claude' / 'workflow'\n"
    )
    got = [ln for _, ln, _ in violations(src, "synthetic.py")]
    assert got == [2, 3, 6, 7, 8], got                                                  # 多行式子回報在起頭那行
    assert sorted(set(got)) == got                                                      # 同一條式子只報一次


def test_allowlist_entries_still_exist_and_have_reasons():
    for (rel, text), reason in ALLOWLIST.items():
        assert str(reason).strip(), (rel, text)
        assert text in (TREE / rel).read_text(encoding="utf-8"), f"允許清單過期：{rel} 已沒有 {text!r}"
