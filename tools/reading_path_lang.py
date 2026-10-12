"""reading_path_lang.py：tools/reading-path.py 的語言解析層——把原始碼變成語言中立的「函式＋呼叫點」清單。

只做抽取，不決定誰呼叫誰（連線、找路、計數都在 reading-path.py）。單獨跑沒有意義，入口是 tools/reading-path.py。
  Python  ast：函式／方法／巢狀函式／`if __name__ == "__main__"` 區塊、import、繼承與欄位型別、事件鍵、dict 分派表
  C#      不用 Roslyn：去註解與字串後，括號配對＋正規式抓 class/partial/interface/方法/欄位/event/+=/AddListener/Invoke/new
  粗略    js/ts/go/java/kt/rs：正規式抓定義與呼叫名，不判轉手（只數跳檔）
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field

EMIT_NAMES = {"emit", "publish", "fire", "trigger", "notify", "send_event", "dispatch_event"}
SUB_NAMES = {"on", "subscribe", "add_listener", "connect", "add_handler", "listen", "add_callback", "register"}
NOISE_CALLS = {"print"}
NOISE_RECV = {"log", "logger", "logging", "_log", "_logger", "Debug", "Console", "Log", "Trace"}
COARSE_EXT = {".js", ".mjs", ".jsx", ".ts", ".tsx", ".go", ".java", ".kt", ".rs"}
GENERATED_RE = re.compile(r"(\.Designer\.cs|\.g\.cs|\.g\.i\.cs|_pb2\.py|_pb2_grpc\.py)$")


@dataclass
class Call:
    """一個呼叫點，或一個被當值傳遞的函式參照。

    kind：name 裸名呼叫｜self 本物件方法｜super 父類方法｜attr 經由別的東西（recv；mod:X＝字串寫的模組）｜new 建構｜
          emit 發事件（name＝事件鍵）｜invoke C# 的 X.Invoke()（name＝X）｜table 分派表（name＝表名）｜
          getattr getattr(…)(…)（name＝引數裡出現的變數名，逗號分隔）
    """
    kind: str
    name: str
    recv: str = ""
    line: int = 0
    refs: list = field(default_factory=list)   # 引數裡的函式參照 [(位置 int｜關鍵字 str, Call)]
    noise: bool = False                        # log/print：不算句數、不算呼叫


@dataclass
class Func:
    id: str            # "相對路徑::限定名"
    file: str
    qual: str
    name: str
    cls: str           # 所屬類別名（模組層函式為空）
    lang: str          # py｜cs｜coarse
    line: int
    params: list = field(default_factory=list)
    param_types: dict = field(default_factory=dict)
    calls: list = field(default_factory=list)
    simple: bool = False      # 去掉 docstring 與 log 後 ≤2 句且無分支迴圈：轉手函式的候選
    abstract: bool = False    # 沒有本體（抽象、介面、NotImplementedError）
    entry: bool = False       # 天生入口：__main__ 區塊、無區塊時的 main、C# static Main、粗略模式 main
    local_types: dict = field(default_factory=dict)   # 區域變數 → 類別名（x = Foo()）
    table_vars: dict = field(default_factory=dict)    # 區域變數 → 分派表名（h = TABLE[k]）
    tables: dict = field(default_factory=dict)        # 函式內的分派表名 → [Call 參照]


@dataclass
class Cls:
    name: str
    lang: str
    files: list = field(default_factory=list)
    bases: list = field(default_factory=list)
    methods: dict = field(default_factory=dict)   # 方法名 → [func id]（C# 多載同名全收）
    fields: dict = field(default_factory=dict)    # 欄位 → 型別名
    stored: dict = field(default_factory=dict)    # 欄位 → (func id, 參數名)：把參數存成欄位的 callback
    events: set = field(default_factory=set)
    partial: bool = False


@dataclass
class Module:
    """一個檔解析出來的東西；reading-path.py 把所有檔合成整個專案的圖。"""
    file: str
    lang: str
    funcs: list = field(default_factory=list)
    classes: list = field(default_factory=list)
    defs: dict = field(default_factory=dict)      # 模組層函式名 → func id
    imports: dict = field(default_factory=dict)   # 本地名 → (模組名, 相對層級, from 匯入的原名或 "")
    tables: dict = field(default_factory=dict)    # 分派表名 → [Call 參照]
    subs: list = field(default_factory=list)      # (事件鍵, Call 參照, 訂閱所在 func id 或 "", 檔)


def _event_key(first_arg: str, recv: str) -> str:
    """事件鍵：第一個引數是字串就用它，否則用接收者最後一段（self.changed.emit() → changed）。"""
    return first_arg or recv.split(".")[-1]


def _is_noise(kind: str, name: str, recv: str) -> bool:
    segs = set(recv.split(".")) if recv else set()
    return (kind == "name" and name in NOISE_CALLS) or bool(segs & NOISE_RECV)


# ─── Python（ast） ────────────────────────────────────────────────────────────

_DEF_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_SIMPLE_STMTS = (ast.Return, ast.Expr, ast.Assign, ast.AnnAssign, ast.AugAssign)
_BRANCHY = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.IfExp)   # 一行裡的迴圈／分支也算內容


def parse_python(rel: str, text: str) -> Module:
    tree = ast.parse(text)
    mod = Module(rel, "py")
    for node in tree.body:
        if isinstance(node, _DEF_NODES):
            _py_func(mod, node, "", None)
        elif isinstance(node, ast.ClassDef):
            _py_class(mod, node)
        elif _is_main_guard(node):
            _py_main_block(mod, node)
        else:
            _py_module_stmt(mod, node)
    if not any(f.entry for f in mod.funcs) and "main" in mod.defs:
        next(f for f in mod.funcs if f.id == mod.defs["main"]).entry = True
    return mod


def _py_scan(mod: Module, stmts: list) -> list:
    """stmts 底下的節點走一次（不進巢狀 def/class），順手收 import（函式內的惰性 import 也算）。"""
    nodes = list(_own_nodes(stmts))
    for node in nodes:
        if isinstance(node, ast.Import):
            mod.imports.update({a.asname or a.name: (a.name, 0, "") for a in node.names})
        elif isinstance(node, ast.ImportFrom):
            mod.imports.update({a.asname or a.name: (node.module or "", node.level, a.name) for a in node.names})
    return nodes


def _is_main_guard(node: ast.AST) -> bool:
    test = getattr(node, "test", None)
    return (isinstance(node, ast.If) and isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name) and test.left.id == "__name__")


def _py_main_block(mod: Module, node: ast.If) -> None:
    fid = f"{mod.file}::<main>"
    f = Func(fid, mod.file, "<main>", "<main>", "", "py", node.lineno, entry=True)
    nodes = _py_scan(mod, node.body)
    _py_locals(f, None, nodes)
    f.calls = _py_calls(mod, nodes, fid)
    mod.funcs.append(f)


def _py_module_stmt(mod: Module, node: ast.stmt) -> None:
    """模組層其他敘述：收 import、分派表（NAME = {k: func}）與訂閱（bus.on("k", f)）。"""
    _py_calls(mod, _py_scan(mod, [node]), "")
    target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else getattr(node, "target", None)
    value = getattr(node, "value", None)
    refs = _py_table_refs(value)
    if isinstance(target, ast.Name) and refs:
        mod.tables[target.id] = refs


def _py_table_refs(value) -> list:
    """dict 字面值裡認得出是函式的值（f、self.f、mod.f、("pkg.mod", "func")）；其他值略過。"""
    values = value.values if isinstance(value, ast.Dict) else []
    return [r for v in values if (r := _py_ref(v) or _py_str_ref(v))]


def _py_str_ref(expr) -> Call | None:
    """惰性 import 表的值 ("pkg.mod", "func") → 指向那個模組裡的函式。"""
    elts = expr.elts if isinstance(expr, ast.Tuple) else []
    names = [e.value for e in elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return Call("attr", names[1], recv="mod:" + names[0]) if len(elts) == len(names) == 2 else None


def _py_class(mod: Module, node: ast.ClassDef) -> None:
    bases = [_py_recv(b).split(".")[-1] for b in node.bases if _py_recv(b)]
    cls = Cls(node.name, "py", [mod.file], bases)
    for item in node.body:
        if isinstance(item, _DEF_NODES):
            _py_func(mod, item, node.name + ".", cls)
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and _py_ann(item.annotation):
            cls.fields[item.target.id] = _py_ann(item.annotation)
    mod.classes.append(cls)


def _py_func(mod: Module, node, prefix: str, cls: Cls | None) -> None:
    qual = prefix + node.name
    fid = f"{mod.file}::{qual}"
    args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    f = Func(fid, mod.file, qual, node.name, cls.name if cls else "", "py", node.lineno,
             params=[a.arg for a in args],
             param_types={a.arg: _py_ann(a.annotation) for a in args if _py_ann(a.annotation)})
    body = _strip_doc(node.body)
    nodes = _py_scan(mod, body)
    real = [s for s in body if not isinstance(s, ast.Pass) and not _py_noise_stmt(s)]
    f.simple = (len(real) <= 2 and all(isinstance(s, _SIMPLE_STMTS) for s in real)
                and not any(isinstance(n, _BRANCHY) for n in nodes))
    f.abstract = _py_abstract(node, body)
    _py_locals(f, cls, nodes)
    f.calls = _py_calls(mod, nodes, fid)
    mod.funcs.append(f)
    if cls:
        cls.methods.setdefault(node.name, []).append(fid)
    elif not prefix:
        mod.defs[node.name] = fid
    for sub in [n for n in nodes if isinstance(n, _DEF_NODES)]:
        _py_func(mod, sub, qual + ".", cls)


def _own_nodes(stmts):
    """stmts 底下所有節點；巢狀 def/class 本身會給出，但不往裡走（那是別的函式）。"""
    stack = list(stmts)
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (*_DEF_NODES, ast.ClassDef)):
            stack.extend(ast.iter_child_nodes(node))


def _strip_doc(body: list) -> list:
    first = body[0] if body else None
    is_doc = isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)
    return body[1:] if is_doc else body


def _py_abstract(node, body: list) -> bool:
    decorated = any(_py_recv(d).split(".")[-1] == "abstractmethod" for d in node.decorator_list)
    if decorated or not body:
        return True
    only = body[0] if len(body) == 1 else None
    if isinstance(only, ast.Pass) or (isinstance(only, ast.Expr) and getattr(only.value, "value", None) is Ellipsis):
        return True
    exc = getattr(only, "exc", None) if isinstance(only, ast.Raise) else None
    return _py_recv(getattr(exc, "func", exc)) == "NotImplementedError" if exc else False


def _py_noise_stmt(stmt: ast.stmt) -> bool:
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
        return False
    c = _py_call(stmt.value)
    return bool(c and c.noise)


def _py_ann(ann) -> str:
    """型別標註取類別名：Repo、mod.Repo、Optional[Repo]、"Repo"。"""
    if isinstance(ann, ast.Subscript):
        return _py_ann(ann.slice)
    if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
        return ann.value.split(".")[-1]
    return _py_recv(ann).split(".")[-1] if ann is not None else ""


def _py_recv(expr) -> str:
    """接收者寫成字串：self、self.repo、mod.sub；Foo() → new:Foo；super() → super()；其他為空。"""
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        head = _py_recv(expr.value)
        return f"{head}.{expr.attr}" if head and not head.startswith(("new:", "super")) else ""
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name):
        return "super()" if expr.func.id == "super" else "new:" + expr.func.id
    return ""


def _py_table_name(expr) -> str:
    """TABLE[k] 或 TABLE.get(k) → "TABLE"。"""
    if isinstance(expr, ast.Subscript) and isinstance(expr.value, ast.Name):
        return expr.value.id
    fn = expr.func if isinstance(expr, ast.Call) else None
    if isinstance(fn, ast.Attribute) and fn.attr == "get" and isinstance(fn.value, ast.Name):
        return fn.value.id
    return ""


def _py_call(node: ast.Call) -> Call | None:
    fn, line = node.func, node.lineno
    table = _py_table_name(fn)
    if table:
        return Call("table", table, line=line)
    if isinstance(fn, ast.Name):
        return Call("name", fn.id, line=line, noise=fn.id in NOISE_CALLS)
    if isinstance(fn, ast.Call) and _py_recv(fn.func) == "getattr":
        names = sorted({n.id for a in fn.args for n in ast.walk(a) if isinstance(n, ast.Name)})
        return Call("getattr", ",".join(names), line=line)
    if not isinstance(fn, ast.Attribute):
        return None
    recv = _py_recv(fn.value)
    if recv in ("self", "cls"):
        return Call("self", fn.attr, line=line)
    if recv == "super()":
        return Call("super", fn.attr, line=line)
    return Call("attr", fn.attr, recv=recv, line=line, noise=_is_noise("attr", fn.attr, recv))


def _py_ref(expr) -> Call | None:
    """被當值傳遞的函式參照：f、self.f、mod.f。"""
    if isinstance(expr, ast.Name):
        return Call("name", expr.id)
    recv = _py_recv(expr.value) if isinstance(expr, ast.Attribute) else ""
    if recv in ("self", "cls"):
        return Call("self", expr.attr)
    return Call("attr", expr.attr, recv=recv) if recv and not recv.startswith("new:") else None


def _py_calls(mod: Module, nodes: list, owner: str) -> list:
    calls = []
    for node in nodes:
        c = _py_call(node) if isinstance(node, ast.Call) else None
        if c is None:
            continue
        c.refs = [(i, r) for i, a in enumerate(node.args) if (r := _py_ref(a))]
        c.refs += [(k.arg, r) for k in node.keywords if k.arg and (r := _py_ref(k.value))]
        calls.append(c)
        calls.extend(_py_events(mod, node, c, owner))
    return sorted(calls, key=lambda c: c.line)


def _py_events(mod: Module, node: ast.Call, c: Call, owner: str) -> list:
    """發事件 → 多一個 emit 呼叫；訂閱 → 記進 mod.subs（emit 端用同一把鍵找回處理函式）。"""
    if c.kind not in ("name", "attr", "self") or c.name not in EMIT_NAMES | SUB_NAMES:
        return []
    first = node.args[0] if node.args else None
    literal = first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else ""
    key = _event_key(literal, c.recv)
    if c.name in EMIT_NAMES:
        return [Call("emit", key, line=c.line)] if key else []
    if key and c.refs:
        mod.subs.append((key, c.refs[-1][1], owner, mod.file))
    return []


def _py_locals(f: Func, cls: Cls | None, nodes: list) -> None:
    """區域變數型別、分派表變數；方法裡的 self.x = Foo() 記欄位型別、self.x = 參數 記成 callback 欄位。"""
    for node in nodes:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and _py_ann(node.annotation):
            f.local_types[node.target.id] = _py_ann(node.annotation)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            _py_bind(f, cls, node.targets[0], node.value)


def _py_bind(f: Func, cls: Cls | None, target, value) -> None:
    ctor = _py_recv(value)[4:] if _py_recv(value).startswith("new:") else ""
    table, refs = _py_table_name(value), _py_table_refs(value)
    if isinstance(target, ast.Name):
        if ctor:
            f.local_types[target.id] = ctor
        if table:
            f.table_vars[target.id] = table
        if refs:
            f.tables[target.id] = refs
        return
    if not (cls and isinstance(target, ast.Attribute) and _py_recv(target.value) == "self"):
        return
    if ctor:
        cls.fields[target.attr] = ctor
    elif isinstance(value, ast.Name) and value.id in f.params:
        cls.stored[target.attr] = (f.id, value.id)


# ─── C#（括號配對＋正規式，不用 Roslyn） ─────────────────────────────────────

_C_BLANK = re.compile(r'//[^\n]*|/\*.*?\*/|@"(?:[^"]|"")*"|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])+\'', re.S)
_CS_CLASS = re.compile(
    r"(?P<mods>(?:(?:public|private|protected|internal|static|sealed|abstract|partial|readonly|unsafe|new|file)\s+)*)"
    r"\b(?P<kind>class|struct|interface|record)\s+(?P<name>\w+)(?:\s*<[^>{;]*>)?(?:\s*\([^)]*\))?"
    r"\s*(?::\s*(?P<bases>[^{;]+?))?\s*(?:where\s[^{;]*)?\{")
_CS_SIG = re.compile(r"(?P<name>\w+)\s*(?:<[^<>()]*>)?\s*\((?P<params>[^()]*(?:\([^()]*\)[^()]*)*)\)"
                     r"\s*(?::\s*(?:base|this)\s*\([^()]*\))?\s*(?:where\s.*)?$", re.S)
_CS_CALL = re.compile(r"(?P<new>\bnew\s+)?(?P<recv>(?:\w+\s*\??\.\s*)*)(?P<name>\w+)\s*(?:<[^<>();]*>)?\s*\(")
_CS_SUB = re.compile(r"(?P<lhs>[\w.]+)\s*\+=\s*(?P<rhs>[A-Za-z_][\w.]*)\s*;")
_CS_LISTEN = re.compile(r"(?P<lhs>[\w.]+)\s*\.\s*AddListener\s*\(\s*(?P<rhs>[A-Za-z_][\w.]*)\s*\)")
_CS_LOCAL = re.compile(r"\b(?:var|(?P<type>[A-Z]\w*)(?:<[^<>;=]*>)?)\s+(?P<var>[a-z_]\w*)\s*=\s*(?:new\s+(?P<new>\w+))?")
_CS_ASSIGN = re.compile(r"(?:this\.)?(?P<lhs>\w+)\s*=\s*(?:new\s+(?P<new>\w+)|(?P<rhs>\w+)\s*;)")
_CS_REF = re.compile(r"(?:(?P<key>\w+)\s*:\s*)?(?:(?P<recv>\w+)\.)?(?P<name>[A-Za-z_]\w*)")
_CS_ATTR = re.compile(r"\[[^\[\]]*\]")
_CS_TYPE_DECL = re.compile(r"\b(class|struct|interface|record|enum|namespace|delegate)\b")
_CS_COMPOUND = re.compile(r"\b(if|for|foreach|while|switch|try|do|lock)\b|\busing\s*\(")
CS_KEYWORDS = {"if", "for", "foreach", "while", "switch", "catch", "using", "lock", "return", "typeof", "nameof",
               "sizeof", "default", "checked", "unchecked", "fixed", "when", "base", "this", "new", "throw",
               "await", "get", "set", "in", "is", "as", "out", "ref", "var", "else", "do", "try", "yield", "stackalloc"}


def _blank(m: re.Match) -> str:
    """註解與字串換成等長空白（保留換行，行號不跑掉）。"""
    return re.sub(r"[^\n]", " ", m.group())


def _braces(src: str):
    """每個位置的大括號深度（{ 與 } 都算外層），以及每個 { 對應的 }。"""
    depth, pairs, stack = [], {}, []
    for i, ch in enumerate(src):
        if ch == "}" and stack:
            pairs[stack.pop()] = i
        depth.append(len(stack))
        if ch == "{":
            stack.append(i)
    return depth, pairs


def _strip_generics(text: str) -> str:
    for _ in range(3):
        text = re.sub(r"<[^<>]*>", "", text)
    return text


def _split_top(text: str, pairs: str = "()[]{}") -> list:
    """依頂層逗號切開（括號裡的逗號不算）。"""
    opens, closes = pairs[0::2], pairs[1::2]
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        depth += (ch in opens) - (ch in closes)
        if ch == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


def parse_csharp(rel: str, text: str) -> Module:
    src = _C_BLANK.sub(_blank, text)
    depth, pairs = _braces(src)
    mod = Module(rel, "cs")
    for m in _CS_CLASS.finditer(src):
        bases = [b.split(".")[-1] for b in _split_top(_strip_generics(m["bases"] or ""))]
        cls = Cls(m["name"], "cs", [rel], bases, partial="partial" in m["mods"].split())
        for member in _cs_members(src, depth, pairs, m.end() - 1):
            _cs_member(mod, cls, src, depth, member)
        mod.classes.append(cls)
    return mod


def _cs_members(src: str, depth: list, pairs: dict, open_i: int):
    """class 本體那一層的成員：yield (標頭, 標頭起點, 本體起, 本體迄, 是否 =>)。"""
    close_i = pairs.get(open_i, len(src))
    level = depth[open_i] + 1
    start = i = open_i + 1
    while i < close_i:
        ch = src[i]
        if ch == "{" and depth[i] == level:
            end = pairs.get(i, close_i)
            yield src[start:i], start, i + 1, end, False
            start = i = end + 1
            continue
        if ch == ";" and depth[i] == level:
            head, arrow, _ = src[start:i].partition("=>")
            yield (head, start, start + len(head) + 2, i, True) if arrow else (head, start, i, i, False)
            start = i + 1
        i += 1


def _cs_member(mod: Module, cls: Cls, src: str, depth: list, member: tuple) -> None:
    raw, start, b0, b1, arrow = member
    head = _CS_ATTR.sub(" ", raw).strip()
    if not head or _CS_TYPE_DECL.search(head):
        return
    sig = _CS_SIG.search(head)
    if not sig or "=" in head[:sig.start()] or sig["name"] in CS_KEYWORDS:
        _cs_field(cls, head)
        return
    name, mods = sig["name"], set(head[:sig.start()].split())
    params = [p for p in (_cs_param(t) for t in _split_top(sig["params"], "()[]{}<>")) if p]
    fid = f"{mod.file}::{cls.name}.{name}"
    fid = fid if all(f.id != fid for f in mod.funcs) else f"{fid}@{b0}"
    line = src.count("\n", 0, start + len(raw) - len(raw.lstrip())) + 1
    f = Func(fid, mod.file, f"{cls.name}.{name}", name, cls.name, "cs", line,
             params=[p for p, _ in params], param_types={p: t for p, t in params if t})
    f.abstract = "abstract" in mods or (b0 == b1 and not arrow)
    f.entry = name == "Main" and "static" in mods
    if b1 > b0:
        _cs_body(mod, cls, f, src, depth, b0, b1, arrow)
    cls.methods.setdefault(name, []).append(fid)
    mod.funcs.append(f)


def _cs_param(text: str):
    words = [w for w in _strip_generics(text.split("=")[0]).split() if w not in ("this", "ref", "out", "in", "params")]
    return (words[-1], words[-2].rstrip("?").replace("[]", "").split(".")[-1]) if len(words) >= 2 else None


def _cs_field(cls: Cls, head: str) -> None:
    words = _strip_generics(head.split("=")[0]).replace("[]", "").split()
    if len(words) < 2:
        return
    cls.fields[words[-1]] = words[-2].rstrip("?").split(".")[-1]
    if "event" in words:
        cls.events.add(words[-1])


def _cs_body(mod: Module, cls: Cls, f: Func, src: str, depth: list, b0: int, b1: int, arrow: bool) -> None:
    body = src[b0:b1]
    f.calls = [c for m in _CS_CALL.finditer(body) if (c := _cs_call(m, body, f.line))]
    stmts = 1 if arrow else sum(1 for j in range(b0, b1) if src[j] == ";" and depth[j] == depth[b0])
    noise = sum(1 for c in f.calls if c.noise)
    f.simple = stmts - noise <= 2 and not _CS_COMPOUND.search(body)
    for m in _CS_LOCAL.finditer(body):
        if m["new"] or m["type"]:
            f.local_types[m["var"]] = m["new"] or m["type"]
    for m in _CS_ASSIGN.finditer(body):
        if m["new"]:
            cls.fields.setdefault(m["lhs"], m["new"])
        elif m["rhs"] in f.params:
            cls.stored[m["lhs"]] = (f.id, m["rhs"])
    for m in [*_CS_SUB.finditer(body), *_CS_LISTEN.finditer(body)]:
        ref = _cs_ref(m["rhs"])
        if ref:
            mod.subs.append((m["lhs"].split(".")[-1], ref, f.id, mod.file))


def _cs_call(m: re.Match, body: str, line: int) -> Call | None:
    name, recv = m["name"], re.sub(r"[\s?]", "", m["recv"]).rstrip(".")
    if name in CS_KEYWORDS and not m["new"]:
        return None
    j = m.start() - 1
    while j >= 0 and body[j].isspace():
        j -= 1
    on_result = j >= 0 and body[j] in ".?"      # a.B().C( 的 C：接在運算結果上，接收者不明
    c = _cs_call_kind(bool(m["new"]), name, recv, on_result)
    c.line = line
    c.refs = _cs_args(body, m.end())
    return c


def _cs_call_kind(is_new: bool, name: str, recv: str, on_result: bool) -> Call:
    """C# 呼叫點的種類：new／X.Invoke()／接在運算結果上／本類別／base／經由別的東西。"""
    if is_new:
        return Call("new", name)
    if name == "Invoke" and recv:
        return Call("invoke", recv.split(".")[-1])
    if on_result:
        return Call("attr", name, recv="?")
    if recv in ("", "this"):
        return Call("self" if recv else "name", name)
    if recv == "base":
        return Call("super", name)
    return Call("attr", name, recv=recv, noise=_is_noise("attr", name, recv))


def _cs_args(body: str, i: int) -> list:
    """body[i] 是 ( 後一格：取到對應 ) 為止的引數裡、像函式參照的那些（方法群組 OnHit、this.OnHit）。"""
    depth = 0
    for j in range(i, len(body)):
        depth += (body[j] in "([{") - (body[j] in ")]}")
        if depth < 0:
            args = _split_top(body[i:j])
            return [(m["key"] or idx, _cs_ref(m["name"] if not m["recv"] else f"{m['recv']}.{m['name']}"))
                    for idx, a in enumerate(args) if (m := _CS_REF.fullmatch(a))]
    return []


def _cs_ref(text: str) -> Call | None:
    recv, _, name = text.rpartition(".")
    if not name or not (name[0].isalpha() or name[0] == "_"):
        return None
    if recv == "this":
        return Call("self", name)
    return Call("attr", name, recv=recv) if recv else Call("name", name)


# ─── 粗略模式（其他語言：只認定義與同名呼叫） ─────────────────────────────────

_COARSE_DEF = {
    ".go": re.compile(r"\bfunc\s+(?:\([^)]*\)\s*)?(\w+)\s*\("),
    ".rs": re.compile(r"\bfn\s+(\w+)\s*[<(]"),
}
_COARSE_DEF_DEFAULT = re.compile(
    r"\bfunction\s*\*?\s*(\w+)\s*\(|\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:function\b|\([^()]*\)\s*=>)"
    r"|^[ \t]*(?:(?:public|private|protected|static|async|export|override|final|fun|suspend)\s+)*"
    r"(?:[\w<>\[\],]+\s+)?(\w+)\s*\([^()]*\)\s*(?::\s*[^{;]+)?\{", re.M)
_COARSE_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
COARSE_SKIP = {"if", "for", "while", "switch", "catch", "return", "function", "typeof", "new", "sizeof",
               "fn", "func", "match", "await", "super", "constructor"}


def parse_coarse(rel: str, text: str) -> Module:
    src = _C_BLANK.sub(_blank, text)
    _, pairs = _braces(src)
    mod = Module(rel, "coarse")
    rx = _COARSE_DEF.get(os.path.splitext(rel)[1], _COARSE_DEF_DEFAULT)
    for m in rx.finditer(src):
        name = next(g for g in m.groups() if g)
        open_i = src.find("{", m.end() - 1)
        if name in COARSE_SKIP or open_i < 0:
            continue
        body = src[open_i + 1:pairs.get(open_i, len(src))]
        fid = f"{rel}::{name}"
        fid = fid if fid not in mod.defs.values() else f"{fid}@{open_i}"
        f = Func(fid, rel, name, name, "", "coarse", src.count("\n", 0, m.start()) + 1, entry=name == "main")
        f.calls = [Call("name", n, line=f.line) for n in _COARSE_CALL.findall(body) if n not in COARSE_SKIP]
        mod.defs.setdefault(name, fid)
        mod.funcs.append(f)
    return mod
