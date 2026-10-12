"""verify_code_paths_from_code_root.py：程式碼看檔案位置、資料看資料根（靜態守門，兩個方向）。

做什麼：以 ast 掃 hooks/、lib/、tools/ 的 .py（排除 verify/ 與 __pycache__），找出 `/` 串起來的路徑式（只看最外層、跨行也算）：
- 正方向（資料根接程式碼）：最左邊是資料根（`CLAUDE_DIR`、`_CLAUDE_DIR`、`xxx.CLAUDE_DIR`，或 `Path.home() / ".claude"`），
  後面任一段是 "tools"、"hooks"、"lib"、"skills" 或以 .py 結尾的字串 → 違規。程式碼根用 wg_core.CODE_DIR 或 Path(__file__)。
  資料根的別名也算：記憶目錄（`MEMORY_DIR`、`memory_dir`、`mem_dir`、`xxx.MEMORY_DIR`）、`claude_data_dir()`，以及由它們
  經 `.parent`／`.parents[i]`、`Path(x)`／`str(x)`、`.resolve()`／`.absolute()`／`.expanduser()`、條件式任一支、
  不含程式碼段的 `/` 串推出來的名字（同檔單一名字賦值，反覆推到不再變；`from m import CLAUDE_DIR as X` 的 X 也算）。
  抓不到：跨檔或跨函式傳遞（參數、回傳值）、屬性賦值（`self.root = ...`）、`os.path.join`／f-string 字串拼接、tuple 解包。
  名字不分作用域，同檔同名一律當別名（偏嚴）；同一個名字也由 `__file__` 推出時以檔案位置為準，不當別名。
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
CODE_SEGMENTS = {"tools", "hooks", "lib", "skills"}   # skills 與 tools／hooks／lib 並列為核心程式層（wg_core._CORE_GUARDED_SUBDIRS）
DATA_SEGMENTS = {"workflow", "Logs", "memory", "projects", "settings.json"}
DATA_ROOT_NAMES = {"CLAUDE_DIR", "_CLAUDE_DIR"}
MEMORY_DIR_NAMES = {"MEMORY_DIR", "memory_dir", "mem_dir"}   # 記憶目錄在資料根之下，它的 .parent 就是資料根
WRAP_CALLS = {"Path", "str"}
WRAP_METHODS = {"resolve", "absolute", "expanduser"}
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


def _is_data_root_expr(node: ast.AST, aliases: Set[str]) -> bool:
    """這個運算式的值是不是資料根（或資料根之下、不含程式碼段的位置）。單段的判斷；`/` 串交給 _data_root_len。"""
    if isinstance(node, ast.Name):
        return node.id in DATA_ROOT_NAMES or node.id in MEMORY_DIR_NAMES or node.id in aliases
    if isinstance(node, ast.Attribute):
        if node.attr in ("CLAUDE_DIR", "MEMORY_DIR"):
            return True
        return node.attr == "parent" and _is_data_root_expr(node.value, aliases)
    if isinstance(node, ast.Subscript):
        v = node.value
        return isinstance(v, ast.Attribute) and v.attr == "parents" and _is_data_root_expr(v.value, aliases)
    if isinstance(node, ast.IfExp):
        return _is_data_root_expr(node.body, aliases) or _is_data_root_expr(node.orelse, aliases)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        ops = _chain(node)
        n = _data_root_len(ops, aliases)
        return bool(n) and not any(_is_code_seg(o) for o in ops[n:])
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    if isinstance(f, ast.Name) and f.id == "claude_data_dir":
        return True
    if isinstance(f, ast.Name) and f.id in WRAP_CALLS and node.args:
        return _is_data_root_expr(node.args[0], aliases)
    return isinstance(f, ast.Attribute) and f.attr in WRAP_METHODS and _is_data_root_expr(f.value, aliases)


def _data_root_len(ops: List[ast.AST], aliases: Set[str]) -> int:
    """路徑式開頭是資料根（含別名）→ 資料根佔幾段（1 或 2）；不是 → 0。"""
    head = ops[0]
    is_home = (isinstance(head, ast.Call) and isinstance(head.func, ast.Attribute) and head.func.attr == "home")
    if is_home and len(ops) > 1 and _is_str(ops[1]) and ops[1].value == ".claude":
        return 2
    return 1 if _is_data_root_expr(head, aliases) else 0


def _data_root_aliases(tree: ast.AST, file_roots: Set[str]) -> Set[str]:
    """同檔裡由資料根推出的名字（見模組說明）；也由 `__file__` 推出的名字不算。"""
    assigns = [(n.targets[0].id, n.value) for n in ast.walk(tree)
               if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)]
    assigns += [(n.target.id, n.value) for n in ast.walk(tree)
                if isinstance(n, ast.AnnAssign) and n.value is not None and isinstance(n.target, ast.Name)]
    names = {a.asname for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names
             if a.asname and (a.name in DATA_ROOT_NAMES or a.name in MEMORY_DIR_NAMES)}
    changed = True
    while changed:
        changed = False
        for name, value in assigns:
            if name not in names and name not in file_roots and _is_data_root_expr(value, names):
                names.add(name)
                changed = True
    return names - file_roots


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


def _is_bare_data_root(node: ast.AST, aliases: Set[str]) -> bool:
    """`CLAUDE_DIR`、`str(CLAUDE_DIR)`、`Path.home() / ".claude"`、資料根別名本身（插進 sys.path＝從資料根載程式碼）。"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str" and node.args:
        node = node.args[0]
    ops = _chain(node)
    n = _data_root_len(ops, aliases)
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
    aliases = _data_root_aliases(tree, names)
    inner = set()
    out: List[Tuple[str, int, str, str]] = []
    for node in ast.walk(tree):
        if _is_sys_path_add(node) and any(_is_bare_data_root(a, aliases) for a in node.args):
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
        n = _data_root_len(ops, aliases)
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
        "f = CLAUDE_DIR / 'skills' / '_skill_index.json'\n"
        "ok5 = CODE_DIR / 'skills'\n"
    )
    got = sorted((ln, kind) for _, ln, _, kind in violations(src, "synthetic.py"))
    assert got == [(2, "data-root→code"), (3, "data-root→code"), (6, "data-root→code"),
                   (7, "data-root→code"), (8, "data-root→code"),
                   (13, "data-root→code"), (14, "data-root→code"), (16, "data-root→code")], got   # 多行式子回報在起頭那行


def test_guard_follows_data_root_aliases():
    src = (
        "from pathlib import Path\n"
        "memory_dir = Path(args.memory_dir) if args.memory_dir else MEMORY_DIR\n"
        "claude_root = memory_dir.parent\n"
        "a = Path(claude_root) / 'tools' / 'native-memory-bridge.py'\n"
        "b = memory_dir.parent / 'hooks'\n"
        "root2 = Path(claude_data_dir()).resolve()\n"
        "c = root2 / 'lib'\n"
        "d = MEMORY_DIR.parents[0] / 'x.py'\n"
        "sys.path.insert(0, str(claude_root))\n"
        "from lib.atom_locations import CLAUDE_DIR as DATA\n"
        "e = DATA / 'skills'\n"
        "ok1 = claude_root / 'projects' / 'x'\n"
        "ok2 = Path(__file__).resolve().parent / 'native-memory-bridge.py'\n"
        "ok3 = Path(other_root) / 'tools'\n"
        "here = Path(__file__).resolve().parent\n"
        "ok4 = here.parent / 'lib'\n"
        "ok5 = Path(claude_root).relative_to(base) / 'tools'\n"
    )
    got = [(ln, kind) for _, ln, _, kind in sorted(violations(src, "synthetic.py"), key=lambda v: v[1])]
    assert got == [(4, "data-root→code"), (5, "data-root→code"), (7, "data-root→code"), (8, "data-root→code"),
                   (9, "data-root→code"), (11, "data-root→code")], got     # 反例：舊守門一條都抓不到


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
