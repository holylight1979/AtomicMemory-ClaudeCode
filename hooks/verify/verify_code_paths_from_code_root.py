"""verify_code_paths_from_code_root.py：程式碼看檔案位置、資料看資料根（靜態守門，兩個方向）。

做什麼：以 ast 掃 hooks/、lib/、tools/ 的 .py（排除 verify/ 與 __pycache__），找出 `/` 串起來的路徑式（只看最外層、跨行也算）：
- 正方向（資料根接程式碼）：最左邊是資料根（`CLAUDE_DIR`、`_CLAUDE_DIR`、`xxx.CLAUDE_DIR`，或 `Path.home() / ".claude"`），
  後面任一段是 "tools"、"hooks"、"lib" 或以 .py 結尾的字串 → 違規。程式碼根用 wg_core.CODE_DIR 或 Path(__file__)。
- 反方向（檔案位置接資料）：最左邊是檔案位置根（式子裡直接含 `__file__`，或同檔裡由含 `__file__` 的式子賦值出來的名字，
  例如 CODE_DIR、ROOT），後面任一段是 "workflow"、"Logs"、"memory"、"projects"、"settings.json" → 違規。
  資料根用 lib.project_root.claude_data_dir()（hooks 端是 wg_core.CLAUDE_DIR）。
允許清單只放判不出或刻意保留的例外，每筆附理由；另有一案檢查允許清單沒有過期。
反例：兩個方向各一段合成原始碼，違規全抓到、合法寫法不誤報。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_code_paths_from_code_root.py
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Set, Tuple

TREE = Path(__file__).resolve().parents[2]
SCAN_DIRS = ("hooks", "lib", "tools")
CODE_SEGMENTS = {"tools", "hooks", "lib"}
DATA_SEGMENTS = {"workflow", "Logs", "memory", "projects", "settings.json"}
DATA_ROOT_NAMES = {"CLAUDE_DIR", "_CLAUDE_DIR"}
# 整支檔案不掃：路徑 → 理由
SKIP_FILES = {
    "tools/project-smells.py": "track-e 擁有，本輪不准動；是否同類寫在 014 交付信，由總控台合併時處理",
}
# (相對路徑, 違規那一行的原始碼片段) → 為什麼保留；目前沒有例外
ALLOWLIST: dict = {}


def _chain(node: ast.AST) -> List[ast.AST]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _chain(node.left) + [node.right]
    return [node]


def _is_str(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _is_code_seg(node: ast.AST) -> bool:
    return _is_str(node) and (node.value in CODE_SEGMENTS or node.value.endswith(".py"))


def _is_data_seg(node: ast.AST) -> bool:
    return _is_str(node) and node.value in DATA_SEGMENTS


def _mentions_file(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Name) and n.id == "__file__" for n in ast.walk(node))


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


def _file_root_names(tree: ast.AST) -> Set[str]:
    """同檔裡由檔案位置推出的名字：值含 `__file__`，或值的路徑式開頭是已知的檔案位置名字（反覆推到不再變）。"""
    assigns = [(n.targets[0].id, n.value) for n in ast.walk(tree)
               if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)]
    names: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, value in assigns:
            if name in names:
                continue
            head = _chain(value)[0]
            if _mentions_file(value) or (isinstance(head, ast.Name) and head.id in names):
                names.add(name)
                changed = True
    return names


def _is_sys_path_add(node: ast.AST) -> bool:
    f = node.func if isinstance(node, ast.Call) else None
    return (isinstance(f, ast.Attribute) and f.attr in ("insert", "append") and isinstance(f.value, ast.Attribute)
            and f.value.attr == "path" and isinstance(f.value.value, ast.Name) and f.value.value.id == "sys")


def _is_bare_data_root(node: ast.AST) -> bool:
    """`CLAUDE_DIR`、`str(CLAUDE_DIR)`、`Path.home() / ".claude"` 本身（插進 sys.path＝從資料根載程式碼）。"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str" and node.args:
        node = node.args[0]
    ops = _chain(node)
    n = _data_root_len(ops)
    return bool(n) and len(ops) == n


def _is_file_root(head: ast.AST, names: Set[str]) -> bool:
    if isinstance(head, ast.Name):
        return head.id in names
    return _mentions_file(head)


def violations(source: str, rel: str) -> List[Tuple[str, int, str, str]]:
    """→ [(相對路徑, 行號, 該行原始碼, 方向)]；方向是 "data-root→code" 或 "file-root→data"。"""
    tree = ast.parse(source)
    lines = source.splitlines()
    names = _file_root_names(tree)
    inner = set()
    out: List[Tuple[str, int, str, str]] = []
    for node in ast.walk(tree):
        if _is_sys_path_add(node) and any(_is_bare_data_root(a) for a in node.args):
            text = lines[node.lineno - 1].strip()
            if (rel, text) not in ALLOWLIST:
                out.append((rel, node.lineno, text, "data-root→code"))
            continue
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)) or id(node) in inner:
            continue
        sub = node.left
        while isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Div):   # 只看最外層，內層是同一條式子的前綴
            inner.add(id(sub))
            sub = sub.left
        ops = _chain(node)
        n = _data_root_len(ops)
        kind = ""
        if n and any(_is_code_seg(o) for o in ops[n:]):
            kind = "data-root→code"
        elif _is_file_root(ops[0], names) and any(_is_data_seg(o) for o in ops[1:]):
            kind = "file-root→data"
        if kind:
            text = lines[node.lineno - 1].strip()
            if (rel, text) not in ALLOWLIST:
                out.append((rel, node.lineno, text, kind))
    return out


def _scan() -> List[Tuple[str, int, str, str]]:
    found: List[Tuple[str, int, str, str]] = []
    for d in SCAN_DIRS:
        for p in sorted((TREE / d).rglob("*.py")):
            rel = p.relative_to(TREE).as_posix()
            parts = set(p.relative_to(TREE).parts)
            if "verify" in parts or "__pycache__" in parts or rel in SKIP_FILES:
                continue
            found += violations(p.read_text(encoding="utf-8"), rel)
    return found


def test_no_code_path_from_data_root_and_no_data_path_from_file_root():
    found = _scan()
    assert found == [], "程式碼／資料用錯根：\n" + "\n".join(
        f"{rel}:{ln}  [{kind}]  {text}" for rel, ln, text, kind in found)


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
        "sys.path.insert(0, str(CLAUDE_DIR))\n"
        "sys.path.insert(0, str(Path.home() / '.claude'))\n"
        "sys.path.insert(0, str(CODE_DIR))\n"
    )
    got = sorted((ln, kind) for _, ln, _, kind in violations(src, "synthetic.py"))
    assert got == [(2, "data-root→code"), (3, "data-root→code"), (6, "data-root→code"),
                   (7, "data-root→code"), (8, "data-root→code"),
                   (13, "data-root→code"), (14, "data-root→code")], got                # 多行式子回報在起頭那行


def test_guard_flags_file_root_data_paths():
    src = (
        "from pathlib import Path\n"
        "CODE_DIR = Path(__file__).resolve().parent.parent\n"
        "ROOT = CODE_DIR\n"
        "a = CODE_DIR / 'workflow' / 'config.json'\n"
        "b = Path(__file__).resolve().parents[1] / 'Logs' / 'x.log'\n"
        "c = (ROOT\n     / 'memory')\n"
        "d = CODE_DIR / 'settings.json'\n"
        "e = CODE_DIR / 'projects'\n"
        "ok1 = CODE_DIR / 'tools' / 'x.py'\n"
        "ok2 = claude_data_dir() / 'workflow'\n"
        "ok3 = CLAUDE_DIR / 'Logs'\n"
        "ok4 = OTHER / 'memory'\n"
    )
    got = [(ln, kind) for _, ln, _, kind in violations(src, "synthetic.py")]
    assert got == [(4, "file-root→data"), (5, "file-root→data"), (6, "file-root→data"),
                   (8, "file-root→data"), (9, "file-root→data")], got


def test_allowlist_and_skip_entries_still_exist_and_have_reasons():
    for (rel, text), reason in ALLOWLIST.items():
        assert str(reason).strip(), (rel, text)
        assert text in (TREE / rel).read_text(encoding="utf-8"), f"允許清單過期：{rel} 已沒有 {text!r}"
    for rel, reason in SKIP_FILES.items():
        assert str(reason).strip() and (TREE / rel).is_file(), rel
