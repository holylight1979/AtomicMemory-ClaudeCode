"""verify_code_paths_from_code_root.py：程式碼看檔案位置、資料看資料根（靜態守門，兩個方向）。

做什麼：以 ast 掃 hooks/、lib/、tools/ 的 .py（排除 verify/ 與 __pycache__），找出 `/` 串起來的路徑式（只看最外層、跨行也算）：
- 正方向（資料根接程式碼）：最左邊是資料根（`CLAUDE_DIR`、`_CLAUDE_DIR`、`xxx.CLAUDE_DIR`，或 `Path.home() / ".claude"`），
  後面任一段是 "tools"、"hooks"、"lib"、"skills"、"prompts" 或以 .py 結尾的字串 → 違規。程式碼根用 wg_core.CODE_DIR 或 Path(__file__)。
  資料根的別名也算：`claude_data_dir()`；家目錄別名（`HOME = Path.home()`）/ ".claude"；記憶目錄（`MEMORY_DIR`、`memory_dir`、
  `mem_dir`、`xxx.MEMORY_DIR`、任一種資料根寫法 / "memory"）的 `.parent`／`.parents[0]`；以及經 `Path(x)`／`str(x)`、
  `.resolve()`／`.absolute()`／`.expanduser()`、條件式任一支推出來的名字（同檔單一名字賦值，反覆推到不再變；
  `from m import CLAUDE_DIR as X` 的 X 也算）。記憶目錄底下是記憶資料：資料根直接接 "memory" 或從記憶目錄別名往下接，
  後面出現 "tools" 都不算違規（兩種寫法同一套規則）。
  固定名字（CLAUDE_DIR、_CLAUDE_DIR、MEMORY_DIR、memory_dir、mem_dir）是命名約定，就算由 `__file__` 推出也照資料看
  （逼它改名成 CODE_DIR，例：skill-index.py）；同一個名字有混合來源（先檔案位置、後覆寫成資料根；條件式兩支來源不同）
  保守當資料根，不因含 `__file__` 就解除。家目錄的包裝（`Path.home().resolve()`、`Path(HOME)`）也認得。
  抓不到：跨檔或跨函式傳遞（參數、回傳值）、屬性賦值（`self.root = ...`）、`os.path.join`／f-string 字串拼接、tuple 解包、
  非 .py 檔（shell 腳本等）。名字不分作用域，同檔同名一律當別名（偏嚴）。
- 反方向（檔案位置接資料）：最左邊是檔案位置根（式子裡直接含 `__file__`，或同檔裡由含 `__file__` 的式子賦值出來的名字，
  例如 CODE_DIR、ROOT），後面任一段是 "workflow"、"Logs"、"memory"、"projects"、"settings.json" → 違規。
  資料根用 lib.project_root.claude_data_dir()（hooks 端是 wg_core.CLAUDE_DIR）。
允許清單只放判不出或刻意保留的例外，每筆附理由；另有一案檢查允許清單沒有過期。沒有整支跳過的檔（壞味道掃描工具也掃）。
反例：兩個方向各一段合成原始碼，違規全抓到、合法寫法不誤報。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_code_paths_from_code_root.py
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import List, NamedTuple, Set, Tuple

TREE = Path(__file__).resolve().parents[2]
SCAN_DIRS = ("hooks", "lib", "tools")
CODE_SEGMENTS = {"tools", "hooks", "lib", "skills", "prompts"}   # 核心程式層（wg_core._CORE_GUARDED_SUBDIRS）＋版控裡的 LLM 樣板
DATA_SEGMENTS = {"workflow", "Logs", "memory", "projects", "settings.json"}
DATA_ROOT_NAMES = {"CLAUDE_DIR", "_CLAUDE_DIR"}
MEMORY_DIR_NAMES = {"MEMORY_DIR", "memory_dir", "mem_dir"}   # 記憶目錄＝資料根 / "memory"，它的 .parent 就是資料根
WRAP_CALLS = {"Path", "str"}
WRAP_METHODS = {"resolve", "absolute", "expanduser"}
# (相對路徑, 違規那一行的原始碼片段) → 為什麼保留
ALLOWLIST: dict = {
    ("tools/install.py", 'init = run([bash, str(TARGET / "hooks" / "user-init.sh")], cwd=TARGET, check=False, env=env, timeout=60)'):
        "安裝器：TARGET（~/.claude）是安裝目的地，複製完跑目的地那份 user-init.sh 是安裝步驟本身",
    ("tools/install.py", 'hub_py = next(p for p in (TARGET / "lib" / "overview_hub.py", SOURCE / "lib" / "overview_hub.py") if p.is_file())'):
        "安裝器 --verify 驗的是「已安裝版本」：用 hook 實際會載的 ~/.claude/lib/overview_hub.py 解析部位表（函式 docstring 已寫明）",
    ("tools/usage-snapshot/usage_snapshot.py",
     'PROFILE_DIR = CLAUDE_DIR / "tools" / "usage-snapshot" / "browser-data"   # Chrome 登入 profile（使用者資料）'):
        "Chrome 登入 profile 是使用者資料、刻意看資料根（A2c 拍板 5）；放在資料根的 tools/usage-snapshot/ 底下，一般安裝兩根同一路徑，既有 profile 位置不變",
}


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


class _Names(NamedTuple):
    roots: Set[str]   # 資料根
    mems: Set[str]    # 記憶目錄（資料根 / "memory"）
    homes: Set[str]   # 家目錄（`Path.home()`）


def _is_wrapped(node: ast.AST, test) -> bool:
    """`Path(x)`／`str(x)`／`x.resolve()` 等包裝，或條件式任一支，裡面的 x 符合 test。"""
    if isinstance(node, ast.IfExp):
        return test(node.body) or test(node.orelse)
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    if isinstance(f, ast.Name) and f.id in WRAP_CALLS and node.args:
        return test(node.args[0])
    return isinstance(f, ast.Attribute) and f.attr in WRAP_METHODS and test(f.value)


def _is_home(node: ast.AST, nm: _Names) -> bool:
    """家目錄：`Path.home()`、家目錄別名，以及它們的包裝（`Path.home().resolve()`、`Path(HOME)`…）。"""
    if isinstance(node, ast.Name):
        return node.id in nm.homes
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "home":
        return True
    return _is_wrapped(node, lambda x: _is_home(x, nm))


def _data_root_len(ops: List[ast.AST], nm: _Names) -> int:
    """路徑式開頭是資料根（含別名）→ 資料根佔幾段（家目錄 / ".claude" 佔 2，其餘 1）；不是 → 0。"""
    if _is_home(ops[0], nm) and len(ops) > 1 and _is_str(ops[1]) and ops[1].value == ".claude":
        return 2
    return 1 if _is_data_root_expr(ops[0], nm) else 0


def _enters_memory(ops: List[ast.AST], n: int) -> bool:
    """資料根後面緊接 "memory"：後續各段是記憶資料，不是程式碼。"""
    return len(ops) > n and _is_str(ops[n]) and ops[n].value == "memory"


def _is_memory_dir_expr(node: ast.AST, nm: _Names) -> bool:
    """這個運算式的值是不是記憶目錄（資料根 / "memory"，資料根不論幾段寫法）。"""
    if isinstance(node, ast.Name):
        return node.id in nm.mems
    if isinstance(node, ast.Attribute):
        return node.attr == "MEMORY_DIR"
    ops = _chain(node)
    if len(ops) > 1:
        n = _data_root_len(ops, nm)
        return bool(n) and len(ops) == n + 1 and _enters_memory(ops, n)
    return _is_wrapped(node, lambda x: _is_memory_dir_expr(x, nm))


def _is_data_root_expr(node: ast.AST, nm: _Names) -> bool:
    """這個運算式的值是不是資料根本身（見模組說明）。"""
    if isinstance(node, ast.Name):
        return node.id in nm.roots
    if isinstance(node, ast.Attribute):
        if node.attr == "CLAUDE_DIR":
            return True
        return node.attr == "parent" and _is_memory_dir_expr(node.value, nm)
    if isinstance(node, ast.Subscript):
        v, i = node.value, node.slice
        return (isinstance(v, ast.Attribute) and v.attr == "parents" and isinstance(i, ast.Constant) and i.value == 0
                and _is_memory_dir_expr(v.value, nm))
    ops = _chain(node)
    if len(ops) > 1:
        return _data_root_len(ops, nm) == len(ops)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "claude_data_dir":
        return True
    return _is_wrapped(node, lambda x: _is_data_root_expr(x, nm))


def _data_root_names(tree: ast.AST) -> _Names:
    """同檔裡的資料根／記憶目錄／家目錄名字：固定名字＋`import ... as` 的別名＋賦值推出來的別名。
    同一個名字有混合來源（先由 `__file__` 推、後覆寫成資料根；條件式一支檔案位置一支資料根）時保守當資料根，
    不因含 `__file__` 就解除（它同時也留在檔案位置名單，兩個方向都會檢查）。"""
    assigns = [(n.targets[0].id, n.value) for n in ast.walk(tree)
               if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)]
    assigns += [(n.target.id, n.value) for n in ast.walk(tree)
                if isinstance(n, ast.AnnAssign) and n.value is not None and isinstance(n.target, ast.Name)]
    imported = [a for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names if a.asname]
    nm = _Names(set(DATA_ROOT_NAMES) | {a.asname for a in imported if a.name in DATA_ROOT_NAMES},
                set(MEMORY_DIR_NAMES) | {a.asname for a in imported if a.name in MEMORY_DIR_NAMES}, set())
    changed = True
    while changed:
        changed = False
        for name, value in assigns:
            if name in nm.roots or name in nm.mems or name in nm.homes:
                continue
            for group, test in ((nm.homes, _is_home), (nm.roots, _is_data_root_expr), (nm.mems, _is_memory_dir_expr)):
                if test(value, nm):
                    group.add(name)
                    changed = True
                    break
    return nm


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


def _is_bare_data_root(node: ast.AST, nm: _Names) -> bool:
    """`CLAUDE_DIR`、`str(CLAUDE_DIR)`、`Path.home() / ".claude"`、資料根別名本身（插進 sys.path＝從資料根載程式碼）。"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str" and node.args:
        node = node.args[0]
    ops = _chain(node)
    n = _data_root_len(ops, nm)
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
    nm = _data_root_names(tree)
    inner = set()
    out: List[Tuple[str, int, str, str]] = []
    for node in ast.walk(tree):
        if _is_sys_path_add(node) and any(_is_bare_data_root(a, nm) for a in node.args):
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
        n = _data_root_len(ops, nm)
        kind = ""
        if n and not _enters_memory(ops, n) and any(_is_code_seg(o) for o in ops[n:]):
            kind = "data-root→code"
        elif _is_file_root(ops[0], names) and any(_is_data_seg(o) for o in ops[1:]):
            kind = "file-root→data"
        if kind:
            text = lines[node.lineno - 1].strip()
            if (rel, text) not in ALLOWLIST:
                out.append((rel, node.lineno, text, kind))
    return out


def _scan_files() -> List[Tuple[str, Path]]:
    """要掃的檔：SCAN_DIRS 底下所有 .py，只排 verify/ 與 __pycache__。"""
    out: List[Tuple[str, Path]] = []
    for d in SCAN_DIRS:
        for p in sorted((TREE / d).rglob("*.py")):
            parts = set(p.relative_to(TREE).parts)
            if "verify" not in parts and "__pycache__" not in parts:
                out.append((p.relative_to(TREE).as_posix(), p))
    return out


def _scan() -> List[Tuple[str, int, str, str]]:
    found: List[Tuple[str, int, str, str]] = []
    for rel, p in _scan_files():
        found += violations(p.read_text(encoding="utf-8"), rel)
    return found


def test_scan_covers_smell_tool():
    """壞味道掃描工具也在守門範圍內（以前整支跳過）。"""
    assert "tools/project-smells.py" in {rel for rel, _ in _scan_files()}


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
        "g = CLAUDE_DIR / 'prompts' / 'user-decision-l1.md'\n"
        "ok6 = CODE_DIR / 'prompts'\n"
    )
    got = sorted((ln, kind) for _, ln, _, kind in violations(src, "synthetic.py"))
    assert got == [(2, "data-root→code"), (3, "data-root→code"), (6, "data-root→code"),
                   (7, "data-root→code"), (8, "data-root→code"),
                   (13, "data-root→code"), (14, "data-root→code"), (16, "data-root→code"),
                   (18, "data-root→code")], got   # 多行式子回報在起頭那行


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
        "ok6 = memory_dir / 'tools' / 'note.md'\n"
        "mem2 = claude_data_dir() / 'memory'\n"
        "f = mem2.parent / 'hooks' / 'w.py'\n"
    )
    got = [(ln, kind) for _, ln, _, kind in sorted(violations(src, "synthetic.py"), key=lambda v: v[1])]
    assert got == [(4, "data-root→code"), (5, "data-root→code"), (7, "data-root→code"), (8, "data-root→code"),
                   (9, "data-root→code"), (11, "data-root→code"), (20, "data-root→code")], got   # 反例：舊守門一條都抓不到


def test_guard_home_alias_and_memory_dir_same_rule_direct_or_aliased():
    src = (
        "from pathlib import Path\n"
        "HOME = Path.home()\n"
        "TARGET = HOME / '.claude'\n"
        "a = TARGET / 'tools' / 'x.py'\n"                              # 家目錄別名 / .claude → 資料根
        "m = Path.home() / '.claude' / 'memory'\n"
        "b = m.parent / 'tools' / 'x.py'\n"                            # 三段寫法的記憶目錄 .parent → 資料根
        "ok1 = CLAUDE_DIR / 'memory' / 'tools' / 'x.md'\n"             # 直接接 memory → 記憶資料
        "mem = CLAUDE_DIR / 'memory'\n"
        "ok2 = mem / 'tools' / 'x.md'\n"                               # 別名接同樣後綴 → 同一套規則
        "ok3 = HOME / 'Downloads' / 'tools'\n"                         # 家目錄本身不是資料根
    )
    got = [(ln, kind) for _, ln, _, kind in sorted(violations(src, "synthetic.py"), key=lambda v: v[1])]
    assert got == [(4, "data-root→code"), (6, "data-root→code")], got


def test_guard_mixed_source_names_and_fixed_names_stay_data_root():
    src = (
        "from pathlib import Path\n"
        "base = Path(__file__).resolve().parent\n"
        "base = claude_data_dir()\n"
        "bad1 = base / 'tools'\n"                                # 先檔案位置、後覆寫成資料根 → 保守當資料根
        "MEMORY_DIR = Path(__file__).resolve().parent\n"
        "bad2 = MEMORY_DIR.parent / 'lib'\n"                     # 固定名字是命名約定，照資料看（逼改名）
        "pick = Path(__file__).parent if fast else claude_data_dir()\n"
        "bad3 = pick / 'hooks'\n"                                # 條件式一支檔案位置一支資料根
        "H = Path.home().resolve()\n"
        "bad4 = H / '.claude' / 'skills'\n"                      # 家目錄包裝
        "ok = Path(__file__).resolve().parent / 'tools'\n"
    )
    got = [(ln, kind) for _, ln, _, kind in sorted(violations(src, "synthetic.py"), key=lambda v: v[1])]
    assert got == [(4, "data-root→code"), (6, "data-root→code"), (8, "data-root→code"), (10, "data-root→code")], got


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


def test_allowlist_entries_still_exist_and_have_reasons():
    for (rel, text), reason in ALLOWLIST.items():
        assert str(reason).strip(), (rel, text)
        assert text in (TREE / rel).read_text(encoding="utf-8"), f"允許清單過期：{rel} 已沒有 {text!r}"
