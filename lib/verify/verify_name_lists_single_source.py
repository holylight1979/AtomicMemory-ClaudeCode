"""verify_name_lists_single_source.py — 索引檔名、記憶資料夾名的清單只在 lib/atom_spec.py 寫字面。

別處要一組這些名字（跳過名單、索引檔清單），用 atom_spec 的常數組，不再用字串各寫一份：
過去出事的都是「同一組名字在多處各寫一份、其中一份漏了一項」（_archived、_rejected、templates）。

只擋清單：一個 set／tuple／list 字面裡出現兩個以上受管名字才算。單獨一個字面、拼路徑不擋。
放行：`except ImportError` 區塊內的備援清單（lib 載不進來時本來就拿不到常數）。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_name_lists_single_source.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lib import atom_spec  # noqa: E402

MANAGED = frozenset(
    [*atom_spec.ALL_INDEX_FILES]
    + [v for k, v in vars(atom_spec).items() if k.endswith("_DIR_NAME") and isinstance(v, str)]
)
SCAN_DIRS = ("hooks", "lib", "tools")
SPEC_FILE = ROOT / "lib" / "atom_spec.py"


def _import_error_handler_nodes(tree: ast.AST) -> set:
    """`except ImportError` 區塊內所有節點的 id。"""
    inside = set()
    for h in ast.walk(tree):
        if isinstance(h, ast.ExceptHandler) and isinstance(h.type, ast.Name) and h.type.id == "ImportError":
            for stmt in h.body:
                inside.update(id(n) for n in ast.walk(stmt))
    return inside


def find_name_lists(source: str) -> list:
    """回傳 [(行號, 命中的受管名字)]：兩個以上受管名字寫在同一個清單字面裡。"""
    tree = ast.parse(source)
    exempt = _import_error_handler_nodes(tree)
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.Set, ast.Tuple, ast.List)) and id(n) not in exempt:
            names = [e.value for e in n.elts if isinstance(e, ast.Constant) and e.value in MANAGED]
            if len(names) >= 2:
                hits.append((n.lineno, names))
    return hits


def test_checker_catches_a_copied_list():
    # 對照組：檢查器本身要抓得到，否則「什麼都沒抓到」也算通過
    assert find_name_lists('SKIP = {"_staging", "episodic", "node_modules"}\n')
    assert find_name_lists('IDX = ("MEMORY.md", "_INDEX.md")\n')
    assert not find_name_lists('p = root / "_staging" / "x.md"\nSKIP = {"_staging", "node_modules"}\n')
    assert not find_name_lists('try:\n    from atom_spec import X\nexcept ImportError:\n    X = ("_staging", "episodic")\n')


def test_no_copied_name_lists_outside_atom_spec():
    found = []
    for d in SCAN_DIRS:
        for p in (ROOT / d).rglob("*.py"):
            if p == SPEC_FILE or "verify" in p.parts or "__pycache__" in p.parts:
                continue
            for line, names in find_name_lists(p.read_text(encoding="utf-8")):
                found.append(f"{p.relative_to(ROOT).as_posix()}:{line} {names}")
    assert not found, "改用 lib/atom_spec.py 的常數組這份清單：\n" + "\n".join(found)
