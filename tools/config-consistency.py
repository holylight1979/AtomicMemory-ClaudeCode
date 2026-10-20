#!/usr/bin/env python3
"""config-consistency.py：設定鍵一致性量測（G8）——每個設定鍵在每個執行端是否一致生效。只量不改。

做什麼：讀鍵的定義來源（workflow/config.json；lib/hub_config.HUB_DEFAULTS，掛在 overview_hub 底下；TECH.md §12 設定總表），
掃讀取端（hooks/、lib/、tools/ 的 .py 用 ast；.js 用 regex＋行號，標「近似」），列四類：
  (a) 程式讀了、三個定義來源都沒有的鍵（同一段整段沒定義時併成一列）
  (b) config.json 定義了、沒有任何讀取端讀的鍵（整段沒人讀只列最上層）
  (c) 同一個鍵在不同讀取處的預設值不同（.get 預設、`x or 預設`、程式內預設表、js `|| 預設`）
  (d) 自己算資料根：不經 lib/project_root.claude_data_dir／paths.js CLAUDE_DIR，自己拼 Path.home()/".claude"、
      expanduser("~/.claude")，或拿 __file__ 推出的路徑接 workflow／memory／Logs／projects
另列「判不了」（不猜、不進四類）：動態鍵（.get(變數)）、整段設定被傳給認不出的地方或逐鍵走訪、疑似同鍵不同寫法。
同一個鍵以點路徑正規化（Python a.get("b") 與 js a?.b 都是 a.b）；底線開頭的鍵（_doc、_errors）不算。
測試檔（verify/ 底下、verify_*、test_*、conftest.py）與本工具自己不算讀取端。

怎麼跑：
  python tools/config-consistency.py                         # Markdown 報告印到 stdout
  python tools/config-consistency.py --out memory/_staging/g8-config-consistency-report.md
  python tools/config-consistency.py --json                  # 機器讀
  python tools/config-consistency.py --root <樹> --config <config.json>   # 掃別的樹（案例用假目錄）
  python tools/config-consistency.py --notes <notes.json>    # 建議欄：{"a:<鍵>": "…", "d:<檔>": "…", "d:<檔>:<行>": "…", "c:*": "…"}
尾行：`CONFIG_CONSISTENCY DONE keys=<n> read_not_defined=<n> defined_not_read=<n> default_mismatch=<n> path_self_computed=<n>`
（數字是尺不是判決，不印 PASS）。exit：0 完成；2 config.json 讀不到或頂層不是物件。完整參數以 --help 為準。
"""
from __future__ import annotations

import argparse
import ast
import bisect
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

CODE_DIR = Path(__file__).resolve().parent.parent   # 程式碼根（本檔所在的樹）
sys.path.insert(0, str(CODE_DIR))
from lib.project_root import claude_data_dir  # noqa: E402

SCAN_DIRS = ("hooks", "lib", "tools")
SKIP_DIRS = {"verify", "node_modules", "__pycache__", ".git"}
SELF_REL = "tools/config-consistency.py"
CANONICAL = {"lib/project_root.py", "tools/workflow-guardian-mcp/lib/paths.js"}   # 資料根的唯一算法本身，(d) 不列
ROOT_NAMES = {"config", "_config", "full_config", "full_cfg", "wg_config"}       # 沒有更準的來源時，這些變數名當整份設定
ROOT_FUNCS = {"load_config", "_load_config", "load_cfg", "_load_cfg"}
CONFIG_PATH_NAMES = {"CONFIG_PATH", "_CONFIG_PATH", "config_path", "cfg_path", "CFG_PATH"}
SAFE_CALLS = {"isinstance", "bool", "len", "type", "id", "callable", "repr", "print", "int", "float", "str", "list", "tuple",
              "set", "frozenset", "sorted", "min", "max", "abs", "round", "any", "all", "enumerate", "zip", "Path",
              "hasattr", "getattr"}      # 拿值做轉型或判斷，不算整段外流
NO_ESCAPE_FUNC = re.compile(r"merge|validate")   # 合併器、驗證器裡逐鍵走訪是搬運或檢查，不算使用
DATA_CHILDREN = {"workflow", "memory", "Logs", "projects"}
HOME_ENV = {"HOME", "USERPROFILE"}
DOTTED_GETTER = re.compile(r"(?i)cfg|conf|setting")
DOTTED_KEY = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_][\w-]*)+$")

KeyPath = Tuple[str, ...]


# ─── 資料形狀 ─────────────────────────────────────────────────────────────

@dataclass
class Read:
    path: KeyPath
    file: str
    line: int
    side: str            # py｜js


@dataclass
class Dflt:
    path: KeyPath
    value: Any
    file: str
    line: int
    side: str
    src: str             # 寫法（顯示用）
    literal: bool = True


@dataclass
class Site:
    path: KeyPath
    file: str
    line: int
    how: str


@dataclass
class Collect:
    reads: List[Read] = field(default_factory=list)
    defaults: List[Dflt] = field(default_factory=list)
    dyn: List[Site] = field(default_factory=list)
    escapes: List[Site] = field(default_factory=list)
    tables: Dict[KeyPath, Set[str]] = field(default_factory=lambda: defaultdict(set))
    pcands: Dict[Tuple[str, int, str], Set[KeyPath]] = field(default_factory=lambda: defaultdict(set))
    rets: Dict[Tuple[str, int], Set[KeyPath]] = field(default_factory=lambda: defaultdict(set))
    trets: Dict[Tuple[str, int], Set[Tuple[Optional[KeyPath], ...]]] = field(default_factory=lambda: defaultdict(set))


class _Mark:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return self.name


CFG_PATH, CFG_FILE, CFG_TEXT = _Mark("<config 路徑>"), _Mark("<config 檔>"), _Mark("<config 文字>")
NOT_CFG = _Mark("<呼叫端傳現做的 dict>")   # 參數綁到它＝確定不是設定，變數名推定也不套
_UNHANDLED = _Mark("<不是認得的方法呼叫>")


@dataclass(frozen=True)
class Seed:
    """字面 dict（程式內預設表），等著和某段設定合併；值存在 PyIndex.dict_lits[(檔, 行, 欄)]。"""
    rel: str
    line: int
    col: int


@dataclass(frozen=True)
class KeyOf:
    """迴圈變數走訪某張預設表的鍵（`for k in DEFAULTS`）：拿它當鍵讀段＝讀那張表的每個鍵。"""
    seed: Seed


@dataclass(frozen=True)
class TupleVal:
    """函式回傳 tuple，各位置是哪段（`so, cc = load_config()`）。"""
    items: Tuple[Optional[KeyPath], ...]


def dotted(p: KeyPath) -> str:
    return ".".join(p) if p else "（整份）"


def _internal(p: KeyPath) -> bool:
    return any(s.startswith("_") for s in p)


# ─── 定義來源 ─────────────────────────────────────────────────────────────

def flatten_config(d: Dict[str, Any], prefix: KeyPath = ()) -> Dict[KeyPath, Any]:
    """config.json → {點路徑: 值}，中間段也收（值是 dict）；底線開頭的鍵連同子樹略過。"""
    out: Dict[KeyPath, Any] = {}
    for k, v in d.items():
        if not isinstance(k, str) or k.startswith("_"):
            continue
        p = prefix + (k,)
        out[p] = v
        if isinstance(v, dict):
            out.update(flatten_config(v, p))
    return out


def _lit(node: ast.AST, consts: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any]:
    """字面值 → (True, 值)；dict 逐鍵取，取不到的值放 _Mark；模組常數名照查。"""
    if isinstance(node, ast.Dict):
        out = {}
        for k, v in zip(node.keys, node.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            ok, val = _lit(v, consts)
            out[k.value] = val if ok else _Mark("<非字面>")
        return True, out
    try:
        return True, ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        pass
    if isinstance(node, ast.Name) and consts and node.id in consts:
        return True, consts[node.id]
    return False, None


def _single_target(st: ast.stmt) -> Optional[ast.expr]:
    """`X = …`／`X: T = …` 的單一指派目標；其他敘述（含多目標、沒有值）回 None。"""
    if isinstance(st, ast.AnnAssign) and st.value is not None:
        return st.target
    if isinstance(st, ast.Assign) and len(st.targets) == 1:
        return st.targets[0]
    return None


def hub_defaults(root: Path) -> Tuple[Dict[KeyPath, Any], Optional[str]]:
    """lib/hub_config.py 的 HUB_DEFAULTS（ast 取字面，不 import）→ {overview_hub.<鍵>: 值}。"""
    f = root / "lib" / "hub_config.py"
    if not f.is_file():
        return {}, None
    tree = ast.parse(f.read_text(encoding="utf-8"))
    for st in tree.body:
        target = _single_target(st)
        if isinstance(target, ast.Name) and target.id == "HUB_DEFAULTS":
            ok, d = _lit(st.value)
            if ok and isinstance(d, dict):
                return flatten_config(d, ("overview_hub",)), f"lib/hub_config.py:{st.lineno}"
    return {}, None


def _expand_braces(tok: str) -> List[str]:
    m = re.search(r"\{([^}]*)\}", tok)
    if not m:
        return [tok]
    return [x for part in m.group(1).split(",") for x in _expand_braces(tok[:m.start()] + part.strip() + tok[m.end():])]


def _cell_tokens(cell: str) -> List[str]:
    """表格一格裡的反引號鍵 → 展開 `{x,y}` 與 `a_min/max`（→ a_min、a_max）後的字串，順序保留。"""
    out: List[str] = []
    for raw in re.findall(r"`([^`]+)`", cell):
        head, *tails = raw.split("/")
        last = head.split(".")[-1]
        stem = head[:len(head) - len(last)] + last.rsplit("_", 1)[0] + "_" if "_" in last else ""
        out += _expand_braces(head.strip())
        for t in tails:
            out += _expand_braces((stem + t if stem and "." not in t else t).strip())
    return out


def tech_keys(text: str, top: Set[str]) -> Tuple[Set[KeyPath], Set[KeyPath]]:
    """TECH.md「## 12. 設定總表」與 12.1 兩張表第一欄的反引號鍵 → (精確鍵含各層上層, 萬用前綴)。
    同一格後續的鍵：第一段不是頂層鍵 → 掛在第一個鍵的上一層（`a.b` / `c` → a.c）；`a.*` 當前綴。"""
    exact: Set[KeyPath] = set()
    wild: Set[KeyPath] = set()
    m = re.search(r"^## 12\..*?$(.*?)(?=^## 13\.|\Z)", text, re.S | re.M)
    if not m:
        return exact, wild
    for line in m.group(1).splitlines():
        cells = line.split("|")
        if not line.startswith("|") or len(cells) < 3:
            continue
        first: Optional[List[str]] = None
        for tok in _cell_tokens(cells[1]):
            segs = tok.split(".")
            if first is None:
                first = segs
            elif segs[0] not in top:
                segs = first[:-1] + segs
            if segs[-1] == "*":
                wild.add(tuple(segs[:-1]))
            else:
                exact.add(tuple(segs))
    for p in list(exact) + list(wild):
        exact.update(p[:i] for i in range(1, len(p)))
    return exact, wild


# ─── Python 讀取端（ast） ─────────────────────────────────────────────────

class PyIndex:
    """全部 .py 的 ast、函式表、import 別名；跨檔解析呼叫（參數綁段、回傳值是哪段）用。"""

    def __init__(self, root: Path, rels: List[str], skipped: List[str]) -> None:
        self.trees: Dict[str, ast.Module] = {}
        self.sources: Dict[str, str] = {}
        for rel in rels:
            try:
                src = (root / rel).read_text(encoding="utf-8")
                self.trees[rel] = ast.parse(src)
                self.sources[rel] = src
            except (OSError, SyntaxError, UnicodeDecodeError, ValueError) as e:
                skipped.append(f"{rel}：解析失敗（{type(e).__name__}）")
        self.funcs: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
        self.methods: Set[Tuple[str, int]] = set()
        self.fnodes: Dict[Tuple[str, int], ast.AST] = {}
        self.aliases: Dict[str, Dict[str, str]] = {}               # 檔 → {別名: 模組短名}
        self.from_names: Dict[str, Dict[str, Tuple[str, str]]] = {}  # 檔 → {別名: (模組短名, 原名)}
        self.dict_lits: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
        self.consts: Dict[str, Dict[str, Any]] = {}
        self.own_config: Set[str] = set()
        self.param_paths: Dict[Tuple[str, int, str], KeyPath] = {}
        self.ret_paths: Dict[Tuple[str, int], KeyPath] = {}
        self.tret_paths: Dict[Tuple[str, int], Tuple[Optional[KeyPath], ...]] = {}
        self.file_root: Dict[str, KeyPath] = {}   # 檔內 load_config 類函式回傳哪段 → 該檔「config」變數名指的段
        for rel, tree in self.trees.items():
            self._index(rel, tree)

    def _index(self, rel: str, tree: ast.Module) -> None:
        al: Dict[str, str] = {}
        fr: Dict[str, Tuple[str, str]] = {}
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funcs[n.name].append((rel, n.lineno))
                self.fnodes[(rel, n.lineno)] = n
            elif isinstance(n, ast.ClassDef):
                self.methods.update((rel, b.lineno) for b in n.body if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)))
            elif isinstance(n, ast.Import):
                for a in n.names:
                    al[a.asname or a.name.split(".")[0]] = a.name.split(".")[-1 if a.asname else 0]
            elif isinstance(n, ast.ImportFrom):
                for a in n.names:
                    al[a.asname or a.name] = a.name                     # from lib import refix_churn as rc
                    fr[a.asname or a.name] = ((n.module or "").split(".")[-1], a.name)
        self.aliases[rel], self.from_names[rel] = al, fr
        consts: Dict[str, Any] = {}
        for st in tree.body:
            target = _single_target(st)
            if not isinstance(target, ast.Name):
                continue
            ok, val = _lit(st.value, consts)
            if ok:
                consts[target.id] = val
        self.consts[rel] = consts
        src = self.sources[rel]
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in ROOT_FUNCS:
                body = "\n".join(ast.get_source_segment(src, st) or "" for st in n.body)
                if not any(k in body for k in ("CONFIG_PATH", "config.json", "load_config(", "load_cfg(")):
                    self.own_config.add(rel)    # 自有設定檔（不是 workflow/config.json）：變數名推定關掉

    def resolve(self, rel: str, f: ast.AST) -> Optional[Tuple[str, int]]:
        """呼叫對象 → 函式鍵 (檔, 行)；同檔定義 > import 來源 > 全樹唯一；認不出回 None。"""
        if isinstance(f, ast.Name):
            mod, name = self.from_names[rel].get(f.id, (None, f.id))
        elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            name = f.attr
            mod = Path(rel).stem if f.value.id in ("self", "cls") else self.aliases[rel].get(f.value.id)
            if mod is None:
                return None
        else:
            return None
        cands = self.funcs.get(name, [])
        if isinstance(f, ast.Name):
            same = [c for c in cands if c[0] == rel]
            if same:
                return same[0]
        if mod:
            hit = [c for c in cands if Path(c[0]).stem == mod]
            return hit[0] if len(hit) == 1 else None
        return cands[0] if len(cands) == 1 else None


def _empty_literal(n: Optional[ast.AST]) -> bool:
    if isinstance(n, ast.Constant) and n.value is None:
        return True
    if isinstance(n, ast.Dict) and not n.keys or isinstance(n, (ast.List, ast.Tuple)) and not n.elts:
        return True
    return isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("dict", "list") and not n.args


class PyWalk:
    """單檔走一遍：變數 → 設定段（點路徑）的線性資料流，記讀取、預設、動態鍵、整段外流、呼叫端參數、回傳段。"""

    def __init__(self, ix: PyIndex, rel: str, out: Collect) -> None:
        self.ix, self.rel, self.out = ix, rel, out
        self.src = ix.sources[rel]
        self.own = rel in ix.own_config
        self.name_root: Optional[KeyPath] = None if self.own else ix.file_root.get(rel, ())
        self.menv: Dict[str, Any] = {}
        self.fstack: List[Tuple[str, int]] = []
        self.globals: List[Set[str]] = [set()]
        self.cond = 0                         # 在 if／迴圈／except 裡：重新指派不蓋掉原本的段
        self.readnodes: Dict[int, bool] = {}  # 讀取節點 id → 有沒有給預設
        self.deferred: Optional[List[ast.AST]] = None   # 走模組層時收集延後的函式與方法
        self.merging = 0                      # 在「預設表疊段」的迴圈裡：逐鍵搬運不算動態鍵或外流

    def run(self) -> None:
        """模組層先走完（函式與方法延後），再依原始順序走函式：`global` 指派過的模組變數後面的函式看得到。"""
        self.deferred = []
        self.block(self.ix.trees[self.rel].body, self.menv)
        deferred, self.deferred = self.deferred, None
        for fn in deferred:
            self.func(fn, dict(self.menv))

    def _by_name(self, name: str) -> Any:
        if name in CONFIG_PATH_NAMES:
            return CFG_PATH
        return self.name_root if name in ROOT_NAMES else None

    # 記錄
    def _src(self, n: ast.AST) -> str:
        s = (ast.get_source_segment(self.src, n) or "").replace("\n", " ")
        return s if len(s) <= 100 else s[:97] + "…"

    def read(self, p: KeyPath, n: ast.AST, has_default: bool = False) -> None:
        if p and not _internal(p):
            self.out.reads.append(Read(p, self.rel, n.lineno, "py"))
            self.readnodes[id(n)] = has_default

    def default(self, p: KeyPath, d: ast.AST) -> None:
        if _internal(p):
            return
        ok, val = _lit(d, self.ix.consts[self.rel])
        self.out.defaults.append(Dflt(p, val if ok else None, self.rel, d.lineno, "py", self._src(d), ok))

    def _merging(self) -> bool:
        return bool(self.merging) or bool(self.fstack) and bool(NO_ESCAPE_FUNC.search(self.ix.fnodes[self.fstack[-1]].name))

    def dyn(self, base: KeyPath, n: ast.AST) -> None:
        if not _internal(base) and not self._merging():
            self.out.dyn.append(Site(base, self.rel, n.lineno, self._src(n)))

    def escape(self, p: KeyPath, n: ast.AST, how: str) -> None:
        if p and not _internal(p) and not self._merging():
            self.out.escapes.append(Site(p, self.rel, n.lineno, how))

    def keyed_by(self, base: KeyPath, knode: ast.AST, n: ast.AST, env: Dict[str, Any], has_default: bool = False) -> None:
        """鍵是變數：綁到預設表的鍵 → 讀那張表的每個鍵；否則記動態鍵。"""
        k = env.get(knode.id) if isinstance(knode, ast.Name) else None
        d = self.ix.dict_lits.get((k.seed.rel, k.seed.line, k.seed.col)) if isinstance(k, KeyOf) else None
        if isinstance(d, dict):
            for key in d:
                self.read(base + (key,), n, has_default)
        else:
            self.dyn(base, n)

    def seed_defaults(self, seed: Seed, p: KeyPath) -> None:
        d = self.ix.dict_lits.get((seed.rel, seed.line, seed.col))
        if not isinstance(d, dict):
            return
        label = f"{seed.rel}:{seed.line}"

        def walk(prefix: KeyPath, dd: Dict[str, Any]) -> None:
            for k, v in dd.items():
                if k.startswith("_"):
                    continue
                q = prefix + (k,)
                self.out.tables[q].add(label)
                if isinstance(v, dict) and v:
                    walk(q, v)
                elif not isinstance(v, _Mark):
                    self.out.defaults.append(Dflt(q, v, seed.rel, seed.line, "py", f"預設表[{k!r}]"))
        walk(p, d)

    # 敘述
    def func(self, fn: ast.AST, env: Dict[str, Any]) -> None:
        a = fn.args
        pos = a.posonlyargs + a.args
        defaults = dict(zip([x.arg for x in pos[len(pos) - len(a.defaults):]], a.defaults))
        defaults.update({x.arg: d for x, d in zip(a.kwonlyargs, a.kw_defaults) if d is not None})
        dvals = {k: self.ev(d, env) for k, d in defaults.items()}
        names = [x.arg for x in pos + a.kwonlyargs] + [x.arg for x in (a.vararg, a.kwarg) if x]
        for p in names:
            bound = self.ix.param_paths.get((self.rel, fn.lineno, p))
            if bound is None and isinstance(dvals.get(p), tuple):
                bound = dvals[p]
            if bound is None:
                bound = self._by_name(p)
            env[p] = None if bound is NOT_CFG else bound
        globs: Set[str] = set()
        for st in ast.walk(fn):
            if isinstance(st, ast.Global):
                globs.update(st.names)
        self.fstack.append((self.rel, fn.lineno))
        self.globals.append(globs)
        cond, self.cond = self.cond, 0
        self.block(fn.body, env)
        self.cond = cond
        self.globals.pop()
        self.fstack.pop()

    def cblock(self, stmts: Iterable[ast.stmt], env: Dict[str, Any]) -> None:
        """有條件才跑的區塊。"""
        self.cond += 1
        self.block(stmts, env)
        self.cond -= 1

    def block(self, stmts: Iterable[ast.stmt], env: Dict[str, Any]) -> None:
        for st in stmts:
            self.stmt(st, env)

    def stmt(self, st: ast.stmt, env: Dict[str, Any]) -> None:
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if self.deferred is not None and env is self.menv:
                self.deferred.append(st)
            else:
                self.func(st, dict(env))
        elif isinstance(st, ast.ClassDef):
            cenv = dict(env)
            for b in st.body:
                if not isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.stmt(b, cenv)
                elif self.deferred is not None:
                    self.deferred.append(b)
                else:
                    self.func(b, dict(self.menv))
        elif isinstance(st, ast.Assign):
            self.assign(st.targets, st.value, env)
        elif isinstance(st, ast.AnnAssign):
            if st.value is not None:
                self.assign([st.target], st.value, env)
        elif isinstance(st, ast.AugAssign):
            self.ev(st.value, env)
        elif isinstance(st, ast.Return):
            if isinstance(st.value, ast.Tuple):
                vals = tuple(v if isinstance(v, tuple) else None for v in (self.ev(e, env) for e in st.value.elts))
                if self.fstack and any(v is not None for v in vals):
                    self.out.trets[self.fstack[-1]].add(vals)
                return
            v = self.ev(st.value, env)
            if self.fstack and isinstance(v, tuple):
                self.out.rets[self.fstack[-1]].add(v)
        elif isinstance(st, (ast.For, ast.AsyncFor)):
            self.for_(st, env)
        elif isinstance(st, (ast.With, ast.AsyncWith)):
            for it in st.items:
                v = self.ev(it.context_expr, env)
                if isinstance(it.optional_vars, ast.Name):
                    self.bind(it.optional_vars.id, v, it.context_expr, env)
            self.block(st.body, env)
        elif isinstance(st, (ast.If, ast.While)):
            self.ev(st.test, env)
            self.cblock(st.body, env)
            self.cblock(st.orelse, env)
        elif isinstance(st, ast.Try) or type(st).__name__ == "TryStar":
            self.block(st.body, env)
            for h in st.handlers:
                self.cblock(h.body, env)
            self.block(st.orelse, env)
            self.block(st.finalbody, env)
        elif isinstance(st, ast.Match):
            self.ev(st.subject, env)
            for c in st.cases:
                self.cblock(c.body, env)
        else:
            for child in ast.iter_child_nodes(st):
                if isinstance(child, ast.expr):
                    self.ev(child, env)

    def assign(self, targets: List[ast.expr], value: ast.expr, env: Dict[str, Any]) -> None:
        t0 = targets[0]
        if len(targets) == 1 and isinstance(t0, ast.Tuple) and isinstance(value, ast.Tuple) and len(t0.elts) == len(value.elts):
            for t, v in zip(t0.elts, value.elts):
                self.assign([t], v, env)
            return
        v = self.ev(value, env)
        for t in targets:
            self._assign_one(t, v, value, env)

    def _assign_one(self, t: ast.expr, v: Any, value: ast.expr, env: Dict[str, Any]) -> None:
        """指派到單一目標：名字綁段；屬性／容器收下整段算外流；`a, b = f()` 照 TupleVal 逐位綁。"""
        if isinstance(t, ast.Name):
            self.bind(t.id, v, value, env)
            return
        if isinstance(t, (ast.Attribute, ast.Subscript)):
            if isinstance(v, tuple):
                self.escape(v, t, "存進屬性或容器")
            return
        if not isinstance(t, (ast.Tuple, ast.List)):
            return
        items = v.items if isinstance(v, TupleVal) and len(v.items) == len(t.elts) else (None,) * len(t.elts)
        for e, item in zip(t.elts, items):
            if isinstance(e, ast.Name):
                self.bind(e.id, item, None, env)

    def bind(self, name: str, v: Any, value: Optional[ast.AST], env: Dict[str, Any]) -> None:
        old = env.get(name)
        if isinstance(v, tuple):
            env[name] = v
        elif old is not None and (self.cond and isinstance(old, tuple) or _empty_literal(value)):
            return    # 條件分支裡換成別的值、或 `x = {}` 退路：不蓋掉原本的段
        elif isinstance(v, (Seed, _Mark)):
            env[name] = v
        else:
            env[name] = self._by_name(name)
        if name in self.globals[-1]:
            self.menv[name] = env[name]

    def for_(self, st: ast.AST, env: Dict[str, Any]) -> None:
        it = st.iter
        keyed = isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr in ("items", "keys", "values")
        base = self.ev(it.func.value if keyed else it, env)
        loop_vars = {n.id for n in ast.walk(st.target) if isinstance(n, ast.Name)}
        seeded = self._seeded_target(st, env, loop_vars)
        src = base
        if seeded and not isinstance(src, tuple):
            src = self._section_in(st, env, loop_vars)
        merging = bool(seeded) and isinstance(src, tuple)
        if merging:
            self.seed_defaults(env[seeded], src)    # for k, v in 段.items(): out[k] = v／for k in out: out[k] = 段[k]
            env[seeded] = src
        elif isinstance(base, tuple):
            self.escape(base, it, "逐鍵走訪" if keyed else "逐項走訪")
        self._bind_loop(st.target, base, keyed and it.func.attr == "values", env)
        self.merging += merging
        self.cblock(st.body, env)
        self.merging -= merging
        self.cblock(st.orelse, env)

    @staticmethod
    def _bind_loop(target: ast.AST, base: Any, values_only: bool, env: Dict[str, Any]) -> None:
        """迴圈變數先清掉；走訪預設表的鍵（`for k in 表`／`for k, v in 表.items()`）時鍵變數綁 KeyOf。"""
        names = [n for n in ast.walk(target) if isinstance(n, ast.Name)]
        for n in names:
            env[n.id] = None
        if isinstance(base, Seed) and names and not values_only:
            env[names[0].id] = KeyOf(base)

    @staticmethod
    def _loop_key(n: ast.AST, loop_vars: Set[str]) -> bool:
        return isinstance(n, ast.Name) and n.id in loop_vars

    def _seeded_target(self, st: ast.AST, env: Dict[str, Any], loop_vars: Set[str]) -> Optional[str]:
        """迴圈裡 `out[<迴圈變數>] = …` 且 out 是程式內預設表的複本 → out 的名字。"""
        for n in ast.walk(st):
            for t in (n.targets if isinstance(n, ast.Assign) else ()):
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and self._loop_key(t.slice, loop_vars) \
                        and isinstance(env.get(t.value.id), Seed):
                    return t.value.id
        return None

    def _section_in(self, st: ast.AST, env: Dict[str, Any], loop_vars: Set[str]) -> Optional[KeyPath]:
        """`for k in out: out[k] = 段[k]`（或 段.get(k)）→ 那段。"""
        for n in ast.walk(st):
            if isinstance(n, ast.Subscript) and self._loop_key(n.slice, loop_vars):
                holder = n.value
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get" \
                    and n.args and self._loop_key(n.args[0], loop_vars):
                holder = n.func.value
            else:
                continue
            if isinstance(holder, ast.Name) and isinstance(env.get(holder.id), tuple) and env[holder.id]:
                return env[holder.id]
        return None

    # 運算式：回點路徑（tuple）／Seed／_Mark／None
    def ev(self, n: Optional[ast.AST], env: Dict[str, Any]) -> Any:
        if n is None:
            return None
        if isinstance(n, ast.Name):
            return env[n.id] if n.id in env else self._by_name(n.id)
        if isinstance(n, ast.Call):
            return self.call(n, env)
        if isinstance(n, ast.Subscript):
            base = self.ev(n.value, env)
            sl = n.slice
            if isinstance(base, tuple):
                if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                    p = base + (sl.value,)
                    self.read(p, n)
                    return p
                if not isinstance(sl, (ast.Constant, ast.Slice)):
                    self.keyed_by(base, sl, n, env)
            self.ev(sl, env)
            return None
        if isinstance(n, ast.Attribute):
            self.ev(n.value, env)
            return CFG_PATH if n.attr in CONFIG_PATH_NAMES else None
        if isinstance(n, ast.BoolOp):
            vals = [self.ev(v, env) for v in n.values]
            if isinstance(n.op, ast.Or) and self.readnodes.get(id(n.values[0])) is False and isinstance(vals[0], tuple):
                ok, val = _lit(n.values[1], self.ix.consts[self.rel])
                if ok and val:      # `x or 0`／`x or []` 是擋 None 的型別保險，不算預設
                    self.default(vals[0], n.values[1])
            return next((v for v in vals if isinstance(v, (tuple, Seed))), None)
        if isinstance(n, ast.IfExp):
            self.ev(n.test, env)
            a, b = self.ev(n.body, env), self.ev(n.orelse, env)
            return a if a is not None else b
        if isinstance(n, ast.Dict):
            spread = []
            for k, v in zip(n.keys, n.values):
                if k is None:
                    spread.append(self.ev(v, env))
                else:
                    self.ev(k, env)
                    self.ev(v, env)
            if spread:
                return self.merge(spread)
            if n.keys and all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in n.keys):
                self.ix.dict_lits[(self.rel, n.lineno, n.col_offset)] = _lit(n, self.ix.consts[self.rel])[1]
                return Seed(self.rel, n.lineno, n.col_offset)
            return None
        if isinstance(n, ast.Compare):
            return self._compare(n, env)
        if isinstance(n, ast.BinOp):
            self.ev(n.left, env)
            self.ev(n.right, env)
            return CFG_PATH if isinstance(n.op, ast.Div) and isinstance(n.right, ast.Constant) and n.right.value == "config.json" else None
        if isinstance(n, ast.Starred):
            return self.ev(n.value, env)
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            return self._comprehension(n, env)
        for child in ast.iter_child_nodes(n):
            if isinstance(child, ast.expr):
                self.ev(child, env)
        return None

    def _compare(self, n: ast.Compare, env: Dict[str, Any]) -> None:
        """`"k" in 段` 算讀 段.k；`變數 in 段` 交 keyed_by（預設表的鍵或動態鍵）。"""
        self.ev(n.left, env)
        for op, comp in zip(n.ops, n.comparators):
            cv = self.ev(comp, env)
            if not (isinstance(op, (ast.In, ast.NotIn)) and isinstance(cv, tuple)):
                continue
            if isinstance(n.left, ast.Constant) and isinstance(n.left.value, str):
                self.read(cv + (n.left.value,), n)
            elif cv:
                self.keyed_by(cv, n.left, n, env)
        return None

    def _comprehension(self, n: ast.AST, env: Dict[str, Any]) -> None:
        """推導式在自己的作用域裡走：走訪段算外流，走訪預設表的鍵時迴圈變數綁 KeyOf。"""
        cenv = dict(env)
        for gen in n.generators:
            it = gen.iter
            keyed = isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr in ("items", "keys", "values")
            base = self.ev(it.func.value if keyed else it, cenv)
            if isinstance(base, tuple):
                self.escape(base, it, "逐鍵走訪" if keyed else "逐項走訪")
            self._bind_loop(gen.target, base, keyed and it.func.attr == "values", cenv)
            for c in gen.ifs:
                self.ev(c, cenv)
        for part in ((n.key, n.value) if isinstance(n, ast.DictComp) else (n.elt,)):
            self.ev(part, cenv)
        return None

    def merge(self, vals: List[Any]) -> Any:
        """deep_merge(預設表, 段)／{**預設表, **段}：結果是那一段，預設表的值記成該段的預設。"""
        paths = [v for v in vals if isinstance(v, tuple)]
        seeds = [v for v in vals if isinstance(v, Seed)]
        if not paths:
            return seeds[0] if seeds else None
        for s in seeds:
            self.seed_defaults(s, paths[-1])
        return paths[-1]

    def items_base(self, n: ast.AST, env: Dict[str, Any]) -> Any:
        """`{k: v for k, v in 段.items() …}` → 段（合併用，不算外流）；`{k: 段[k] for k in 預設表 …}` → 段（讀表裡每個鍵）。"""
        if isinstance(n, (ast.DictComp, ast.GeneratorExp, ast.ListComp, ast.SetComp)) and n.generators:
            it = n.generators[0].iter
            if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr in ("items", "keys", "values"):
                return self.ev(it.func.value, env)
            self.ev(n, env)
            loop_vars = {x.id for g in n.generators for x in ast.walk(g.target) if isinstance(x, ast.Name)}
            return self._section_in(n, env, loop_vars)
        return self.ev(n, env)

    def keyed(self, base: KeyPath, n: ast.Call, env: Dict[str, Any]) -> Any:
        knode, rest = (n.args[0] if n.args else None), n.args[1:]
        for a in rest:
            self.ev(a, env)
        if isinstance(knode, ast.Constant) and isinstance(knode.value, str):
            p = base + (knode.value,)
            self.read(p, n, has_default=bool(rest))
            if rest:
                self.default(p, rest[0])
            return p
        if knode is not None:
            self.ev(knode, env)
            self.keyed_by(base, knode, n, env, has_default=bool(rest))
        return None

    def call(self, n: ast.Call, env: Dict[str, Any]) -> Any:
        f = n.func
        if isinstance(f, ast.Attribute):
            v = self._method(n, env)
            if v is not _UNHANDLED:
                return v
            self.ev(f.value, env)
            name: Optional[str] = f.attr
        elif isinstance(f, ast.Name):
            name = f.id
        else:
            self.ev(f, env)
            name = None
        args = [self.ev(a, env) for a in n.args]
        kws = {k.arg: self.ev(k.value, env) for k in n.keywords}
        if name == "open" and args and args[0] is CFG_PATH:
            return CFG_FILE
        if name == "join" and n.args and isinstance(n.args[-1], ast.Constant) and n.args[-1].value == "config.json":
            return CFG_PATH
        if name in ("dict", "deepcopy", "copy") and args and isinstance(args[0], (tuple, Seed)):
            return args[0]
        target = self.ix.resolve(self.rel, f)
        if target is not None:
            self.bind_params(target, n, args, kws)
            if target in self.ix.ret_paths:
                return self.ix.ret_paths[target]
            if target in self.ix.tret_paths:
                return TupleVal(self.ix.tret_paths[target])
        if name and DOTTED_GETTER.search(name):
            base = next((v for v in args if isinstance(v, tuple)), None)
            key = next((a.value for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)
                        and DOTTED_KEY.match(a.value)), None)
            if base is not None and key:
                p = base + tuple(key.split("."))
                self.read(p, n)
                return p
        if name and "merge" in name.lower() and len(args) + len(kws) >= 2:
            m = self.merge(args + list(kws.values()))
            if m is not None:
                return m
        if name in ROOT_FUNCS and not (target is not None and target[0] in self.ix.own_config):
            return ()
        if target is None and name not in SAFE_CALLS:
            for v in args + list(kws.values()):
                if isinstance(v, tuple):
                    self.escape(v, n, f"傳給 {name or '呼叫'}()")
        return None

    def _method(self, n: ast.Call, env: Dict[str, Any]) -> Any:
        """認得的方法呼叫：段.get(k)、段.items()、路徑.read_text()／open()、預設表.update(段)、json.load(f)；
        其他回 _UNHANDLED（這時還沒動過 n.func.value，呼叫端照一般呼叫走）。"""
        f, attr = n.func, n.func.attr
        if attr in ("get", "setdefault", "pop", "items", "keys", "values", "read_text", "read_bytes", "read", "open"):
            base = self.ev(f.value, env)
            if attr in ("get", "setdefault", "pop") and isinstance(base, tuple):
                return self.keyed(base, n, env)
            self._ev_args(n, env)
            if attr in ("items", "keys", "values") and isinstance(base, tuple):
                self.escape(base, n, "逐鍵走訪")
            if attr == "open":
                return CFG_FILE if base is CFG_PATH else None
            return CFG_TEXT if attr.startswith("read") and (base is CFG_PATH or base is CFG_FILE) else None
        if attr == "copy" and not n.args:
            return self.ev(f.value, env)
        if attr == "update" and n.args:
            base = self.ev(f.value, env)
            src = self.items_base(n.args[0], env)
            for a in n.args[1:]:
                self.ev(a, env)
            if isinstance(base, Seed) and isinstance(src, tuple):
                self.seed_defaults(base, src)
                if isinstance(f.value, ast.Name):
                    env[f.value.id] = src
            return None
        if attr in ("load", "loads") and isinstance(f.value, ast.Name) and f.value.id == "json":
            vals = [self.ev(a, env) for a in n.args]
            return () if vals and (vals[0] is CFG_FILE or vals[0] is CFG_TEXT) else None
        return _UNHANDLED

    def _ev_args(self, n: ast.Call, env: Dict[str, Any]) -> None:
        for a in n.args:
            self.ev(a, env)
        for k in n.keywords:
            self.ev(k.value, env)

    def bind_params(self, target: Tuple[str, int], n: ast.Call, args: List[Any], kws: Dict[Optional[str], Any]) -> None:
        fn = self.ix.fnodes[target]
        params = [x.arg for x in fn.args.posonlyargs + fn.args.args]
        if target in self.ix.methods and isinstance(n.func, ast.Attribute):
            params = params[1:]
        kwonly = {x.arg for x in fn.args.kwonlyargs}
        for i, (node, v) in enumerate(zip(n.args, args)):
            if isinstance(node, ast.Starred):
                break
            v = NOT_CFG if isinstance(v, Seed) else v
            if not isinstance(v, tuple) and v is not NOT_CFG:
                continue
            if i < len(params):
                self.out.pcands[(target[0], target[1], params[i])].add(v)
            elif v is not NOT_CFG:
                self.escape(v, n, f"傳進 *args（{fn.name}）")
        for k, v in kws.items():
            v = NOT_CFG if isinstance(v, Seed) else v
            if not isinstance(v, tuple) and v is not NOT_CFG or k is None:
                continue
            if k in params or k in kwonly:
                self.out.pcands[(target[0], target[1], k)].add(v)
            elif v is not NOT_CFG:
                self.escape(v, n, f"傳進 **kwargs（{fn.name}）")


def _pick(cands: Set[Any]) -> Any:
    """有呼叫端傳現做的 dict → NOT_CFG；候選段扣掉「整份」後剩唯一一段就取它（整份多半來自變數名推定，是弱證據）；
    只有整份就取整份；其餘判不了（None）。"""
    if NOT_CFG in cands:
        return NOT_CFG
    sections = cands - {()}
    if len(sections) == 1:
        return next(iter(sections))
    return () if cands == {()} else None


def analyze_python(ix: PyIndex, max_passes: int = 6) -> Collect:
    """固定點：每輪用上一輪的「參數綁哪段／函式回傳哪段」重走全部檔，兩者不再變就停；收最後一輪。"""
    out = Collect()
    for _ in range(max_passes):
        out = Collect()
        for rel in ix.trees:
            PyWalk(ix, rel, out).run()
        params = {k: p for k, v in out.pcands.items() if (p := _pick(v)) is not None}
        rets = {k: p for k, v in out.rets.items() if (p := _pick(v)) is not None}
        trets = {k: next(iter(v)) for k, v in out.trets.items() if len(v) == 1 and k not in rets}
        roots: Dict[str, Set[KeyPath]] = defaultdict(set)
        for (rel, line), p in rets.items():
            if ix.fnodes[(rel, line)].name in ROOT_FUNCS:
                roots[rel].add(p)
        file_root = {rel: next(iter(v)) for rel, v in roots.items() if len(v) == 1}
        if (params, rets, trets, file_root) == (ix.param_paths, ix.ret_paths, ix.tret_paths, ix.file_root):
            break
        ix.param_paths, ix.ret_paths, ix.tret_paths, ix.file_root = params, rets, trets, file_root
    return out


# ─── 自己算資料根（Python ast） ───────────────────────────────────────────

def _is_home(n: ast.AST, names: Set[str] = frozenset()) -> bool:
    """Path.home()、expanduser("~")、os.environ["HOME"/"USERPROFILE"]、os.getenv(...)、os.environ.get(...)，或指派過這些的變數名。"""
    if isinstance(n, ast.Name):
        return n.id in names
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
        if n.func.attr == "home" and not n.args:
            return True
        if n.func.attr == "expanduser":
            arg = n.args[0] if n.args else n.func.value
            if isinstance(arg, ast.Constant) and arg.value == "~":
                return True
            return isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == "Path" \
                and bool(arg.args) and isinstance(arg.args[0], ast.Constant) and arg.args[0].value == "~"
        if n.func.attr in ("getenv", "get") and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value in HOME_ENV:
            return True
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "Path" and len(n.args) == 1:
        return _is_home(n.args[0])
    return isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value in HOME_ENV


def _parts(n: ast.AST) -> Tuple[ast.AST, List[ast.AST]]:
    """a / "b" / "c"、os.path.join(a, "b", "c")、a.joinpath("b", "c") → (a, ["b", "c"])。"""
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
        base, rest = _parts(n.left)
        return base, rest + [n.right]
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.args:
        if n.func.attr == "join" and isinstance(n.func.value, ast.Attribute) and n.func.value.attr == "path":
            return n.args[0], list(n.args[1:])
        if n.func.attr == "joinpath":
            base, rest = _parts(n.func.value)
            return base, rest + list(n.args)
    return n, []


def _first_seg(parts: List[ast.AST]) -> Optional[str]:
    if parts and isinstance(parts[0], ast.Constant) and isinstance(parts[0].value, str):
        return re.split(r"[/\\]", parts[0].value)[0]
    return None


def _mentions(n: ast.AST, names: Set[str]) -> bool:
    return any(isinstance(x, ast.Name) and (x.id == "__file__" or x.id in names) for x in ast.walk(n))


def _tilde_claude_call(n: ast.AST) -> bool:
    """expanduser("~/.claude…")、Path("~/.claude…")、os.path.join("~/.claude", …)。"""
    if not isinstance(n, ast.Call):
        return False
    fname = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
    return fname in ("expanduser", "Path", "PurePath", "join") and any(
        isinstance(a, ast.Constant) and isinstance(a.value, str) and re.match(r"^~[/\\]\.claude([/\\]|$)", a.value)
        for a in n.args)


def _derived_names(tree: ast.Module) -> Tuple[Set[str], Set[str]]:
    """(模組層由 __file__ 推出的名字, 指派過家目錄的名字)。推三輪，涵蓋再推一兩層（CODE_DIR → HOOKS = CODE_DIR / "hooks"）。
    __file__ 只認模組層（函式內同名變數不算，免得跨作用域誤沾）；家目錄任何作用域都認（接 ".claude" 才算，夠窄）。"""
    module_level = {id(st) for st in tree.body}
    assigns = [n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None]
    file_names: Set[str] = set()
    home_names: Set[str] = set()
    for _ in range(3):
        for n in assigns:
            tgts = [t.id for t in (n.targets if isinstance(n, ast.Assign) else [n.target]) if isinstance(t, ast.Name)]
            if id(n) in module_level and _mentions(n.value, file_names):
                file_names.update(tgts)
            if _is_home(n.value, home_names):
                home_names.update(tgts)
    return file_names, home_names


def self_computed_py(rel: str, tree: ast.Module, src: str) -> List[Site]:
    if rel in CANONICAL:
        return []
    file_names, home_names = _derived_names(tree)
    hits: Dict[Tuple[int, str], Site] = {}

    def add(n: ast.AST, kind: str) -> None:
        s = (ast.get_source_segment(src, n) or "").replace("\n", " ")
        hits.setdefault((n.lineno, kind), Site((), rel, n.lineno, f"{kind}｜{s[:110]}"))

    for n in ast.walk(tree):
        if _tilde_claude_call(n):
            add(n, "expanduser ~/.claude")
            continue
        base, parts = _parts(n)
        if not parts:
            continue
        seg = _first_seg(parts)
        if seg == ".claude" and _is_home(base, home_names):
            add(n, "家目錄/.claude")
        elif seg in DATA_CHILDREN and _mentions(base, file_names):
            add(n, f"__file__ 推的路徑接 {seg}")
    return sorted(hits.values(), key=lambda s: s.line)


# ─── JS 讀取端（regex＋行號，近似） ───────────────────────────────────────

JS_ID = r"[A-Za-z_$][\w$]*"
JS_PARAMS = r"\(((?:[^()]|\([^()]*\))*)\)"      # 參數列，允許一層括號（cfg = loadConfig()）
JS_LIT = r"(?:true|false|null|-?\d+(?:\.\d+)?(?:\s*\*\s*\d+(?:\.\d+)?)*|\"[^\"\\\n]*\"|'[^'\\\n]*')"
_RE_DOT = re.compile(r"\s*(\?\.|\.)\s*(" + JS_ID + r")")
_RE_BRK = re.compile(r"\s*(?:\?\.)?\[\s*([\"'])")
_RE_DYN = re.compile(r"\s*(?:\?\.)?\[")
_RE_CALL = re.compile(r"\s*\(")
_RE_LOAD = re.compile(r"loadConfig\(\s*\)")
_RE_DEFAULT = re.compile(r"\s*(\|\||\?\?)\s*(" + JS_LIT + r")")


def _js_string_end(text: str, i: int, mk: List[str]) -> int:
    """從開引號 i 走到收尾引號，沿路把字串內容在 mk 換成 _（換行保留）；樣板字串的 ${…} 是程式碼，不遮。回收尾引號位置。"""
    q, j, n = text[i], i + 1, len(text)
    while j < n and text[j] != q and not (text[j] == "\n" and q != "`"):
        if q == "`" and text.startswith("${", j):
            depth, j = 1, j + 2
            while j < n and depth:
                depth += (text[j] == "{") - (text[j] == "}")
                j += 1
            continue
        step = 2 if text[j] == "\\" else 1
        mk[j:j + step] = ["_" if ch != "\n" else ch for ch in text[j:j + step]]
        j += step
    return j


def js_mask(text: str) -> Tuple[str, str]:
    """(去註解, 再把字串內容換成 _)；長度與換行都不變，位置可回原文取值。"""
    nc, mk = list(text), list(text)
    i, n = 0, len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
        elif text[i] in "\"'`":
            i = _js_string_end(text, i, mk) + 1
            continue
        else:
            i += 1
            continue
        nc[i:j] = mk[i:j] = [" " if ch != "\n" else ch for ch in text[i:j]]   # 註解換空白
        i = j
    return "".join(nc), "".join(mk)


class JsFile:
    def __init__(self, rel: str, text: str) -> None:
        self.rel = rel
        self.orig, self.mask = js_mask(text)
        self.lines = [0] + [m.end() for m in re.finditer(r"\n", text)]
        depth, self.depth = 0, []
        for ch in self.mask:
            self.depth.append(depth)
            depth += (ch == "{") - (ch == "}")
        self.binds: List[Tuple[str, KeyPath, int, int]] = []   # (名, 段, 起, 迄)
        self.fn_rets: Dict[str, KeyPath] = {}

    def line(self, pos: int) -> int:
        return bisect.bisect_right(self.lines, pos)

    def block_end(self, pos: int, depth: int) -> int:
        for j in range(pos, len(self.mask)):
            if self.mask[j] == "}" and self.depth[j] == depth:
                return j
        return len(self.mask)

    def bound(self, name: str, pos: int) -> Optional[KeyPath]:
        best = None
        for nm, p, s, e in self.binds:
            if nm == name and s <= pos < e and (best is None or s > best[0]):
                best = (s, p)
        return best[1] if best else None

    def chain(self, pos: int) -> Tuple[List[str], int, bool]:
        keys: List[str] = []
        while True:
            m = _RE_DOT.match(self.mask, pos)
            if m:
                if _RE_CALL.match(self.mask, m.end()):
                    break
                keys.append(m.group(2))
                pos = m.end()
                continue
            m = _RE_BRK.match(self.mask, pos)
            if m:
                e = self.mask.find(m.group(1), m.end())
                close = re.compile(r"\s*\]").match(self.mask, e + 1) if e >= 0 else None
                if not close:
                    break
                keys.append(self.orig[m.end():e])
                pos = close.end()
                continue
            return keys, pos, bool(_RE_DYN.match(self.mask, pos))
        return keys, pos, False

    def base(self, pos: int) -> Optional[Tuple[KeyPath, int]]:
        m = _RE_LOAD.match(self.mask, pos)
        if m:
            return (), m.end()
        m = re.compile(r"\(\s*").match(self.mask, pos)
        if m:
            inner = self.expr(m.end())
            if inner:
                end = re.compile(r"(?:\s*(?:\|\||\?\?)\s*\{\s*\})?\s*\)").match(self.mask, inner[1])
                if end:
                    return inner[0], end.end()
            return None
        m = re.compile(JS_ID).match(self.mask, pos)
        if not m:
            return None
        call = re.compile(r"\s*\(\s*\)").match(self.mask, m.end())
        if call and m.group(0) in self.fn_rets:
            return self.fn_rets[m.group(0)], call.end()
        if _RE_CALL.match(self.mask, m.end()):
            return None
        p = self.bound(m.group(0), pos)
        return (p, m.end()) if p is not None else None

    def expr(self, pos: int) -> Optional[Tuple[KeyPath, int, bool]]:
        b = self.base(pos)
        if not b:
            return None
        keys, end, dyn = self.chain(b[1])
        return b[0] + tuple(keys), end, dyn


def _js_value(lit: str) -> Any:
    if lit in ("true", "false", "null"):
        return {"true": True, "false": False, "null": None}[lit]
    if lit[0] in "\"'":
        return lit[1:-1]
    val: Any = 1
    for part in re.split(r"\s*\*\s*", lit):
        val *= float(part) if "." in part else int(part)
    return val


def analyze_js(jf: JsFile, out: Collect) -> None:
    for m in re.finditer(r"\bfunction\s+(" + JS_ID + r")\s*" + JS_PARAMS + r"\s*\{\s*return\s+", jf.mask):
        e = jf.expr(m.end())
        if e:
            jf.fn_rets[m.group(1)] = e[0]
    for m in re.finditer(r"\bfunction\b\s*[\w$]*\s*" + JS_PARAMS + r"\s*\{", jf.mask):
        brace = m.end() - 1
        for pm in re.finditer(r"(" + JS_ID + r")\s*=\s*loadConfig\(\s*\)", m.group(1)):
            jf.binds.append((pm.group(1), (), brace, jf.block_end(brace + 1, jf.depth[brace] + 1)))
    for m in re.finditer(r"\b(?:const|let|var)\s+(" + JS_ID + r")\s*=\s*", jf.mask):
        e = jf.expr(m.end())
        if e:
            jf.binds.append((m.group(1), e[0], m.end(), jf.block_end(m.end(), jf.depth[m.start()])))
    names = {b[0] for b in jf.binds} | set(jf.fn_rets)
    starts = [m.start() for m in _RE_LOAD.finditer(jf.mask)]
    starts += [m.start() for m in re.finditer(r"(?<![\w$.])(" + JS_ID + r")\b", jf.mask) if m.group(1) in names]
    alts = "|".join(["loadConfig\\("] + [re.escape(x) for x in names])
    starts += [m.start() for m in re.finditer(r"\((?=\s*(?:" + alts + r"))", jf.mask)]
    for pos in sorted(set(starts)):
        if pos > 0 and jf.mask[pos - 1] in ".$" or jf.mask[max(0, pos - 2):pos] == "?.":
            continue
        e = jf.expr(pos)
        if not e:
            continue
        path, end, dyn = e
        if dyn and not _internal(path):
            out.dyn.append(Site(path, jf.rel, jf.line(pos), "js 動態鍵（近似）"))
        if not path or _internal(path):
            continue
        out.reads.append(Read(path, jf.rel, jf.line(pos), "js"))
        d = _RE_DEFAULT.match(jf.orig, end)
        if d and (d.group(1) == "??" or _js_value(d.group(2))):    # `|| 0` 同 Python `or 0`，不算預設
            out.defaults.append(Dflt(path, _js_value(d.group(2)), jf.rel, jf.line(pos), "js", d.group(0).strip()))


def self_computed_js(jf: JsFile) -> List[Site]:
    if jf.rel in CANONICAL:
        return []
    pats = [
        (r"homedir\(\)\s*,\s*[\"']\.claude[\"'/\\]", "家目錄/.claude"),
        (r"homedir\(\)\s*\+\s*[\"'][/\\]\.claude", "家目錄/.claude"),
        (r"process\.env\.(?:USERPROFILE|HOME)\b[^;\n]*[\"'][/\\]?\.claude[\"'/\\]", "家目錄/.claude"),
        (r"__dirname\b[^;\n]*[\"'](?:workflow|memory|Logs|projects)[\"'/\\]", "__dirname 推的路徑接資料子目錄"),
    ]
    hits = []
    for i, line in enumerate(jf.orig.splitlines(), 1):
        for pat, kind in pats:
            if re.search(pat, line):
                hits.append(Site((), jf.rel, i, f"{kind}｜{line.strip()[:110]}"))
                break
    return hits


# ─── 比對 ─────────────────────────────────────────────────────────────────

def _norm_val(v: Any) -> Any:
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return (type(v).__name__, v)
    if isinstance(v, (int, float)):
        return ("num", float(v))
    if isinstance(v, (list, tuple)):
        return ("list", tuple(_norm_val(x) for x in v))
    if isinstance(v, dict):
        return ("dict", tuple(sorted((k, _norm_val(x)) for k, x in v.items())))
    return ("other", repr(v))


def _show(v: Any) -> str:
    s = repr(v) if isinstance(v, _Mark) else json.dumps(v, ensure_ascii=False, default=repr)
    return s if len(s) <= 60 else s[:57] + "…"


def _sites(items: Iterable[Any], limit: int = 3) -> str:
    seen: List[str] = []
    for it in items:
        tag = f"{it.file}:{it.line}" + ("（js）" if getattr(it, "side", "") == "js" else "")
        if tag not in seen:
            seen.append(tag)
    more = f" 等 {len(seen)} 處" if len(seen) > limit else ""
    return "、".join(seen[:limit]) + more


def compare(cfg_flat: Dict[KeyPath, Any], hub: Dict[KeyPath, Any], tech: Tuple[Set[KeyPath], Set[KeyPath]],
            out: Collect, selfcomp: List[Site]) -> Dict[str, Any]:
    tech_exact, tech_wild = tech
    defined: Set[KeyPath] = set(cfg_flat) | set(hub) | tech_exact
    defined.update(p[:i] for p in list(hub) for i in range(1, len(p)))

    def is_defined(p: KeyPath) -> bool:
        return p in defined or any(p[:len(w)] == w for w in tech_wild)

    reads_by: Dict[KeyPath, List[Read]] = defaultdict(list)
    for r in out.reads:
        reads_by[r.path].append(r)
    defaults_by: Dict[KeyPath, List[Dflt]] = defaultdict(list)
    for d in out.defaults:
        defaults_by[d.path].append(d)

    # (a) 讀了沒定義：同段整段沒定義時併到最上層沒定義、也被讀到的那段
    groups: Dict[KeyPath, List[KeyPath]] = {}
    for p in sorted(q for q in reads_by if not is_defined(q)):
        head = next((p[:i] for i in range(1, len(p)) if p[:i] in reads_by and not is_defined(p[:i])), p)
        groups.setdefault(head, []).append(p)
    a_rows = []
    for head, members in sorted(groups.items()):
        rs = [r for m in members for r in reads_by[m]]
        dfl = [d for m in members for d in defaults_by.get(m, []) if d.literal]
        a_rows.append({
            "key": dotted(head), "sub_keys": sorted({".".join(m[len(head):]) for m in members if m != head}),
            "sides": sorted({r.side for r in rs}), "where": _sites(rs),
            "reads": [f"{r.file}:{r.line}" + ("（js）" if r.side == "js" else "") for r in rs],
            "defaults": sorted({f"{'.'.join(d.path[len(head):]) or '本鍵'}={_show(d.value)}" for d in dfl}),
            "tables": sorted({t for m in members for t in out.tables.get(m, ())}),
        })

    # (b) 定義了沒人讀；上層（含本身）有整段外流或動態鍵 → 判不了
    opaque: Dict[KeyPath, List[Site]] = defaultdict(list)
    for s in out.escapes + out.dyn:
        opaque[s.path].append(s)
    b_rows, b_held, reported = [], [], []
    for p in sorted(cfg_flat):
        if any(r[:len(p)] == p for r in reads_by) or any(p[:len(q)] == q for q in reported):
            continue
        reported.append(p)
        hold = [s for i in range(1, len(p) + 1) for s in opaque.get(p[:i], [])]
        row = {"key": dotted(p), "value": _show(cfg_flat[p]), "in_tech": p in tech_exact,
               "children": sum(1 for q in cfg_flat if len(q) > len(p) and q[:len(p)] == p)}
        if hold:
            row["held_by"] = _sites(hold)
            b_held.append(row)
        else:
            b_rows.append(row)

    # (c) 同鍵預設不同（字面值；{} 與 None 是「沒給」不算）
    c_rows = []
    for p, ds in sorted(defaults_by.items()):
        lits = [d for d in ds if d.literal and d.value is not None and d.value != {}]
        if len({_norm_val(d.value) for d in lits}) < 2:
            continue
        c_rows.append({
            "key": dotted(p), "config": _show(cfg_flat[p]) if p in cfg_flat else "（未定義）",
            "defaults": [f"{_show(d.value)} @ {d.file}:{d.line}（{d.side}｜{d.src}）" for d in lits],
        })

    d_rows = [{"file": s.file, "line": s.line, "kind": s.how.split("｜")[0], "code": s.how.split("｜", 1)[1]} for s in selfcomp]

    sections = {q[:i] for q in cfg_flat for i in range(1, len(q))}   # 底下還有鍵的段；葉子被轉型或走訪不影響別的鍵
    esc_by: Dict[KeyPath, List[Site]] = defaultdict(list)
    for s in out.escapes:
        if s.path in sections:
            esc_by[s.path].append(s)
    norm: Dict[str, Set[str]] = defaultdict(set)
    for p in defined | set(reads_by):
        norm[".".join(s.lower().replace("_", "").replace("-", "") for s in p)].add(dotted(p))
    unknown = {
        "dynamic": [{"base": dotted(s.path), "where": f"{s.file}:{s.line}", "code": s.how} for s in out.dyn],
        "escape": [{"key": dotted(p), "where": _sites(v, 4), "how": sorted({s.how for s in v})[:3]} for p, v in sorted(esc_by.items())],
        "b_held": b_held,
        "alias": sorted(sorted(v) for v in norm.values() if len(v) > 1),
    }
    keys = {p for p in defined | set(reads_by) if not _internal(p)}
    return {"keys": len(keys), "defined": len(defined), "reads": len(out.reads),
            "a": a_rows, "b": b_rows, "c": c_rows, "d": d_rows, "unknown": unknown}


# ─── 掃描與輸出 ───────────────────────────────────────────────────────────

def scan_files(root: Path, ext: str) -> List[str]:
    out = []
    for d in SCAN_DIRS:
        if not (root / d).is_dir():
            continue
        for f in sorted((root / d).rglob(f"*{ext}")):
            rel = f.relative_to(root).as_posix()
            if SKIP_DIRS & set(rel.split("/")[:-1]) or rel == SELF_REL:
                continue
            if f.name.startswith(("verify_", "test_")) or f.name == "conftest.py":
                continue
            out.append(rel)
    return out


def run(root: Path, config_path: Path) -> Dict[str, Any]:
    cfg = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if not isinstance(cfg, dict):
        raise ValueError("config.json 頂層不是物件")
    cfg_flat = flatten_config(cfg)
    hub, hub_src = hub_defaults(root)
    tech_file = root / "TECH.md"
    top = set(cfg) | {p[0] for p in hub}
    tech = tech_keys(tech_file.read_text(encoding="utf-8"), top) if tech_file.is_file() else (set(), set())

    skipped: List[str] = []
    ix = PyIndex(root, scan_files(root, ".py"), skipped)
    out = analyze_python(ix)
    selfcomp: List[Site] = []
    for rel in ix.trees:
        selfcomp += self_computed_py(rel, ix.trees[rel], ix.sources[rel])
    js_rels = scan_files(root, ".js")
    for rel in js_rels:
        jf = JsFile(rel, (root / rel).read_text(encoding="utf-8", errors="replace"))
        analyze_js(jf, out)
        selfcomp += self_computed_js(jf)

    res = compare(cfg_flat, hub, tech, out, selfcomp)
    res["sources"] = {"config": str(config_path), "config_keys": len(cfg_flat), "hub": hub_src, "hub_keys": len(hub),
                      "tech": str(tech_file) if tech_file.is_file() else None, "tech_keys": len(tech[0]) + len(tech[1]),
                      "py_files": len(ix.trees), "js_files": len(js_rels)}
    res["skipped"] = skipped + [f"{r}：自有設定（不是 workflow/config.json），變數名推定不套用" for r in sorted(ix.own_config)]
    return res


def apply_notes(res: Dict[str, Any], notes: Dict[str, str]) -> None:
    for cat in ("a", "b", "c"):
        for row in res[cat]:
            row["note"] = notes.get(f"{cat}:{row['key']}", notes.get(f"{cat}:*", ""))
    for row in res["unknown"]["b_held"]:
        row["note"] = notes.get(f"b:{row['key']}", notes.get("u:*", ""))
    for row in res["d"]:
        row["note"] = notes.get(f"d:{row['file']}:{row['line']}", notes.get(f"d:{row['file']}", notes.get("d:*", "")))


def _cell(s: Any) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def _table(head: List[str], rows: List[List[Any]]) -> List[str]:
    if not rows:
        return ["（無）", ""]
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    return out + ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows] + [""]


def done_line(res: Dict[str, Any]) -> str:
    return (f"CONFIG_CONSISTENCY DONE keys={res['keys']} read_not_defined={len(res['a'])} "
            f"defined_not_read={len(res['b'])} default_mismatch={len(res['c'])} path_self_computed={len(res['d'])}")


def render_md(res: Dict[str, Any]) -> str:
    s, u = res["sources"], res["unknown"]
    kinds: Dict[str, int] = defaultdict(int)
    for r in res["d"]:
        kinds[r["kind"]] += 1
    L = ["# G8 設定鍵一致性報告（config-consistency）", "",
         "> 只量不改。四類各一表；「建議」欄是 AI 初判，總控台裁定。數字是尺不是判決。", "",
         "## 摘要", "",
         f"- 定義來源：config.json `{s['config']}`（{s['config_keys']} 鍵，含中間段）；HUB_DEFAULTS `{s['hub']}`"
         f"（{s['hub_keys']} 鍵，掛 overview_hub 下）；TECH.md §12（{s['tech_keys']} 鍵）",
         f"- 讀取端：Python {s['py_files']} 檔（ast）、JS {s['js_files']} 檔（regex，近似）；讀取點 {res['reads']} 處；鍵總數 {res['keys']}",
         f"- (a) 讀了沒定義 {len(res['a'])}｜(b) 定義了沒人讀 {len(res['b'])}｜(c) 預設值不同 {len(res['c'])}｜(d) 自己算資料根 {len(res['d'])}"
         + (f"（{'、'.join(f'{k} {v}' for k, v in sorted(kinds.items()))}）" if kinds else ""),
         f"- 判不了：動態鍵 {len(u['dynamic'])}｜整段外流 {len(u['escape'])} 段｜定義了沒直接讀但上層外流 {len(u['b_held'])}"
         f"｜疑似同鍵不同寫法 {len(u['alias'])} 組",
         "", "## (a) 程式讀了、config.json／HUB_DEFAULTS／TECH.md 都沒定義", ""]
    L += _table(["鍵", "子鍵", "哪裡讀", "各端預設", "程式內預設表", "建議"],
                [[f"`{r['key']}`", "、".join(r["sub_keys"]) or "—", r["where"], "；".join(r["defaults"]) or "—",
                  "、".join(r["tables"]) or "—", r.get("note", "")] for r in res["a"]])
    L += ["## (b) config.json 定義了、沒有讀取端讀（整段沒人讀只列最上層）", ""]
    L += _table(["鍵", "config.json 值", "子鍵數", "TECH.md 有", "建議"],
                [[f"`{r['key']}`", r["value"], r["children"], "有" if r["in_tech"] else "—", r.get("note", "")] for r in res["b"]])
    L += ["## (c) 同一個鍵在不同讀取處的預設值不同", ""]
    L += _table(["鍵", "config.json 值", "各處預設", "建議"],
                [[f"`{r['key']}`", r["config"], "<br>".join(r["defaults"]), r.get("note", "")] for r in res["c"]])
    L += ["## (d) 自己算資料根（不經 claude_data_dir／paths.js CLAUDE_DIR）", ""]
    L += _table(["檔:行", "類型", "寫法", "建議"],
                [[f"{r['file']}:{r['line']}", r["kind"], f"`{r['code']}`", r.get("note", "")] for r in res["d"]])
    L += ["## 判不了（不猜，交人看）", "", "### 動態鍵（鍵名是變數，ast 寫不出來）", ""]
    L += _table(["所在段", "檔:行", "寫法"], [[f"`{r['base']}`", r["where"], f"`{r['code']}`"] for r in u["dynamic"]])
    L += ["### 定義了、沒被直接讀，但上層整段被傳走或逐鍵走訪（可能在別處被讀）", ""]
    L += _table(["鍵", "config.json 值", "上層外流處", "建議"],
                [[f"`{r['key']}`", r["value"], r["held_by"], r.get("note", "")] for r in u["b_held"]])
    L += ["### 整段設定被傳給認不出的函式、存進屬性、或逐鍵走訪", ""]
    L += _table(["段", "哪裡", "方式"], [[f"`{r['key']}`", r["where"], "、".join(r["how"])] for r in u["escape"]])
    L += ["### 疑似同鍵不同寫法（大小寫／底線不同）", ""]
    L += _table(["寫法"], [["、".join(f"`{x}`" for x in g)] for g in u["alias"]])
    if res["skipped"]:
        L += ["## 略過", ""] + [f"- {x}" for x in res["skipped"]] + [""]
    L += ["## 已知限制", "",
          "- Python 是單檔線性資料流＋跨檔參數／回傳綁段（固定點），不跑程式：分支裡換段、物件屬性存設定、反射取鍵都追不到，追不到的列進「判不了」。",
          "- 沒有更準的來源時，名叫 config／_config／full_config／full_cfg／wg_config 的變數當整份設定（自有設定檔的工具不套用）；"
          "名字對但內容不是 config.json 的會誤列進 (a)。",
          "- JS 是 regex：只認 loadConfig() 起頭、或綁到它的變數與函式回傳；作用域用大括號深度近似。",
          "- TECH.md 的預設值欄不比對（格式不一，拆不準）；只用第一欄判「有沒有定義」。", "",
          done_line(res)]
    return "\n".join(L) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(CODE_DIR), help="要掃的程式碼樹（預設本檔所在的樹）")
    ap.add_argument("--config", default=str(claude_data_dir() / "workflow" / "config.json"),
                    help="鍵的定義來源 config.json（預設資料根的 workflow/config.json，只讀）")
    ap.add_argument("--out", help="Markdown 報告寫到這個路徑（不給就印到 stdout）")
    ap.add_argument("--json", action="store_true", help="改印 JSON（機器讀）")
    ap.add_argument("--notes", help="建議欄 JSON：{\"a:<鍵>\"|\"b:<鍵>\"|\"c:<鍵>\"|\"d:<檔>\"|\"d:<檔>:<行>\"|\"<類>:*\": 建議}")
    args = ap.parse_args(argv)

    try:
        res = run(Path(args.root).resolve(), Path(args.config))
    except (OSError, ValueError) as e:
        print(f"[config-consistency] 讀不到定義來源：{e}", file=sys.stderr)
        print("CONFIG_CONSISTENCY DONE keys=0 read_not_defined=0 defined_not_read=0 default_mismatch=0 path_self_computed=0")
        return 2
    apply_notes(res, json.loads(Path(args.notes).read_text(encoding="utf-8")) if args.notes else {})
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    elif args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(render_md(res), encoding="utf-8", newline="\n")
        print(f"報告：{args.out}")
    else:
        print(render_md(res), end="")
    print(done_line(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
