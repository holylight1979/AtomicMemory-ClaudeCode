"""reading_path_lang.py：tools/reading-path.py 的語言解析層，把原始碼變成語言中立的「函式＋呼叫點」清單。

只做抽取，不決定誰呼叫誰（連線、找路、計數都在 reading-path.py）。單獨跑沒有意義，入口是 tools/reading-path.py。
  Python  ast：函式／方法／巢狀函式／`if __name__ == "__main__"` 區塊、import、繼承與欄位型別、事件鍵、dict 分派表
  C#      不用 Roslyn：去註解與字串後，括號配對＋正規式抓 class/partial/interface/方法/欄位/event/+=/AddListener/Invoke/new
  粗略    js/ts/go/java/kt/rs：正規式抓定義與呼叫名，不判轉手（只數跳檔）
"""
from __future__ import annotations

import ast
import itertools
import os
import re
from collections import Counter
from dataclasses import dataclass, field

EMIT_NAMES = {"emit", "publish", "fire", "trigger", "notify", "send_event", "dispatch_event"}
SUB_NAMES = {"on", "subscribe", "add_listener", "connect", "add_handler", "listen", "add_callback", "register"}
NOISE_CALLS = {"print"}
NOISE_RECV = {"log", "logger", "logging", "_log", "_logger", "Debug", "Console", "Log", "Trace"}
COARSE_EXT = {".js", ".mjs", ".jsx", ".ts", ".tsx", ".go", ".java", ".kt", ".rs"}
GENERIC_MARKERS = {"Generic", "Protocol"}   # class Foo(Generic[T])：型別參數標記，不是會進 MRO 的專案父類
GENERATED_RE = re.compile(r"(\.Designer\.cs|\.g\.cs|\.g\.i\.cs|_pb2\.py|_pb2_grpc\.py)$")


@dataclass
class Call:
    """一個呼叫點，或一個被當值傳遞的函式參照。

    kind：name 裸名呼叫｜self 本物件方法（Python 的 recv＝寫的是 self 還是 cls）｜super 父類方法｜attr 經由別的東西（recv；mod:X＝字串寫的模組）｜new 建構｜
          emit 發事件（name＝事件鍵，recv＝發事件的接收者）｜invoke C# 的 X.Invoke()（name＝X）｜
          table 分派表（name＝表名，key＝寫死的鍵）｜getattr getattr(…)(…)（name＝引數裡出現的變數名，逗號分隔）｜
          prop C# 讀寫屬性｜opaque 呼叫的對象是算出來的值（factory()(x)、self.handlers[k](x)），看不到
    """
    kind: str
    name: str
    recv: str = ""
    line: int = 0
    refs: list = field(default_factory=list)   # 引數裡的函式參照 [(位置 int｜關鍵字 str, Call)]
    noise: bool = False                        # log/print：不算句數、不算呼叫
    key: str = ""                              # 分派表呼叫時寫死的鍵（TABLE["x"]()）
    nargs: int = 0                             # 位置引數個數
    kwargs: set = field(default_factory=set)   # 有傳的關鍵字（具名）引數名
    blind: set = field(default_factory=set)    # 傳的是算出來的值（呼叫結果、下標…）的位置／關鍵字
    star: int = -1                             # 第一個 *args 展開的位置（之後的位置參數看不到）；-1＝沒有
    dstar: bool = False                        # 有 **kwargs 展開（沒明確傳的參數都可能被它蓋到）
    scoped: bool = False                       # 呼叫點在模型沒建的作用域構件（lambda、生成器、推導式）裡：一律不給條號
    shadowed: bool = False                     # 裸名呼叫的名字正是包住它的構件自己綁定的（lambda 參數、推導式迴圈變數）


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
    param_types: dict = field(default_factory=dict)   # 參數 → 型別的類別名（拿來解析接收者）
    defaults: dict = field(default_factory=dict)      # 參數 → 預設值是函式參照時的 Call（def run(cb=work)）
    blind_defaults: set = field(default_factory=set)  # 預設值是算出來的值的參數（def run(cb=choose())）
    sig: str = ""                                     # C# 完整參數型別（含泛型、陣列、ref/out），當多載簽章
    calls: list = field(default_factory=list)
    simple: bool = False      # 去掉 docstring 與 log 後 ≤2 句且無分支迴圈：轉手函式的候選
    abstract: bool = False    # 真正抽象：Python 方法本身掛 @abstractmethod（建圖時再要求類別確定是 ABCMeta）；C# abstract 或分號宣告（介面）
    hollow: bool = False      # 空實作：Python 只有 pass、...、raise NotImplementedError（或只有 docstring）、C# 空大括號本體。是覆寫，但不值得當落點
    conditional: bool = False                         # C# [Conditional("SYM")]：符號沒定義時編譯器會省略呼叫，呼叫它不給條號
    prop: bool = False        # C# 屬性的 get/set 本體（讀寫屬性就會跑進來）
    entry: bool = False       # 天生入口：__main__ 區塊、無區塊時的 main、C# static Main、粗略模式 main
    local_types: dict = field(default_factory=dict)   # 區域變數 → 類別名（x = Foo()、x: Foo）：找目標用，不分來源
    declared: dict = field(default_factory=dict)      # 區域變數 → 標註／宣告的型別名（x: Foo、C# Foo x = …）：白名單 3 只吃這個
    constructed: dict = field(default_factory=dict)   # 區域變數 → 建構者名稱（x = Foo()、var x = new Foo()）：白名單 2 只吃這個
    aliases: dict = field(default_factory=dict)       # 區域變數 → 函式參照（fn = b、fn = self.run）
    inline: set = field(default_factory=set)          # 就地定義的 lambda／C# 區域函式名：呼叫它不算未解（內容就在這裡）
    reassigned: set = field(default_factory=set)      # 被指定超過一次（參數再被指定也算）：別名、確定型別、確定實例都不算
    escaped: set = field(default_factory=set)         # 被存進欄位或容器的區域變數（self.x = obj、items = [obj]、lst.append(obj)）：找目標用
    receiver_only: set = field(default_factory=set)   # 建構後每一次出現都只是方法呼叫接收者（w.m(…)）的區域變數：白名單 2 只吃這個
    locals: set = field(default_factory=set)          # 本體裡被指定過的區域變數名：拿它當函式呼叫又追不到 → 未解
    attr_stores: set = field(default_factory=set)     # 本體裡寫過的屬性 (接收者, 屬性名)：self.run = f、w.run = f、mod.func = f
    nonlocal_writes: set = field(default_factory=set)  # 用 nonlocal 宣告後又指定的名字：改的是外層作用域的綁定
    global_names: set = field(default_factory=set)    # 宣告 global 的名字：查找直接跳模組層
    nonlocal_names: set = field(default_factory=set)  # 宣告 nonlocal 的名字：查找跳過這一層、往外層找
    import_rebinds: set = field(default_factory=set)  # 函式裡 import 的名字又被別種寫法綁定（import 又指定、又 def）：只影響確定，不影響找目標
    import_sources: dict = field(default_factory=dict)   # 綁定名 → 這一層全部的 import 來源 [(模組名, 相對層級, 原名或 "")]（import 好幾次都留）
    scoped_binds: set = field(default_factory=set)    # 在模型沒建的作用域構件裡被綁定的名字（lambda 參數、推導式迴圈目標、:=、類別本體的 global／nonlocal）
    class_nonlocals: set = field(default_factory=set)  # 巢狀類別本體（含它的方法）裡 nonlocal 宣告的名字：改的是這一層或外層函式的綁定
    decorators: list = field(default_factory=list)    # Python 裝飾器 [(寫法 staticmethod／functools.lru_cache…, 是否當場呼叫, 字面 keyword 引數)]，照原文順序
    table_vars: dict = field(default_factory=dict)    # 區域變數 → 分派表名（h = TABLE[k]）
    tables: dict = field(default_factory=dict)        # 函式內的分派表名 → [(鍵, Call 參照)]
    imports: dict = field(default_factory=dict)       # 函式內的 import（只在這個函式與它的巢狀函式裡有效）


@dataclass
class Cls:
    name: str
    lang: str
    files: list = field(default_factory=list)
    bases: list = field(default_factory=list)
    methods: dict = field(default_factory=dict)   # 方法名 → [func id]（C# 多載同名全收）
    fields: dict = field(default_factory=dict)    # 欄位 → 型別名（宣告的與 self.x = Foo() 推導的都有）：找目標用
    declared_fields: dict = field(default_factory=dict)   # 欄位 → 宣告的型別名（類別層標註、self.x: Foo = …、C# 欄位宣告）：白名單 3 只吃這個
    field_scope: dict = field(default_factory=dict)      # 欄位 → fields 那筆型別證據寫在哪個函式（func id；沒有或 ""＝類別本體）：在那裡解析
    declared_scope: dict = field(default_factory=dict)   # 欄位 → declared_fields 那筆寫在哪個函式（同上）
    body_names: set = field(default_factory=set)         # Python 類別本體綁定的名字（方法、指定、import、巢狀類別…）：方法的參數標註先在這裡找
    decorators: list = field(default_factory=list)       # Python 類別裝飾器 [(寫法, 是否當場呼叫, 字面 keyword 引數)]（見 Func.decorators）
    opaque_bases: int = 0                                # 寫不成名字的父類運算式個數（Base[int]、lambda…；Generic[…] 不算）：MRO 證不出
    metaclass: str = ""                                  # Python class 的 metaclass=… 寫法（abc.ABCMeta 才擋得住建立抽象類別的實例）
    def_decorators: dict = field(default_factory=dict)   # 方法名 → 同名各個 def 的裝飾器（property 與 setter 同名，函式 id 只留最後一個）
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
    import_sources: dict = field(default_factory=dict)   # 綁定名 → 模組層全部的 import 來源（import 好幾次都留，見 Func.import_sources）
    tables: dict = field(default_factory=dict)    # 分派表名 → [(鍵, Call 參照)]
    aliases: dict = field(default_factory=dict)   # 模組層函式別名 → [Call 參照]（flat = itertools.chain.from_iterable）
    bindings: Counter = field(default_factory=Counter)   # 模組層名字被綁定幾次（def、class、import、指定）
    opaque: set = field(default_factory=set)      # 模組層名字被指定成算出來的值，或被函式用 global 改寫：看不到是什麼
    attr_stores: set = field(default_factory=set)   # 不在任何解析出的函式裡寫過的屬性 (接收者, 屬性名)：模組層、類別本體、巢狀類別…
    scoped_nodes: set = field(default_factory=set, repr=False)   # 解析時用：已歸到某個函式的節點 id（其餘的屬性寫入歸模組層）
    static_usings: list = field(default_factory=list)   # C# using static 的型別名

    @property
    def rebound(self) -> set:
        """模組層被重新指定過的名字（綁定超過一次，或被函式 global 改寫）：不在確定白名單。"""
        return {name for name, k in self.bindings.items() if k > 1} | self.opaque
    subs: list = field(default_factory=list)      # (事件鍵, Call 參照, 訂閱所在 func id 或 "", 檔, 訂閱的接收者)


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
_SCOPE_EXPRS = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)   # 自成作用域、模型沒建參數與綁定的運算式


def parse_python(rel: str, text: str) -> Module:
    tree = ast.parse(text)
    mod = Module(rel, "py")
    for node in tree.body:
        if isinstance(node, (*_DEF_NODES, ast.ClassDef)):
            mod.bindings[node.name] += 1
            _py_def_time(mod, node)
        if isinstance(node, _DEF_NODES):
            _py_func(mod, node, "", None)
        elif isinstance(node, ast.ClassDef):
            _py_class(mod, node)
        elif _is_main_guard(node):
            _py_main_block(mod, node, tree)
        else:
            _py_module_stmt(mod, node)
    loose = [n for n in ast.walk(tree) if id(n) not in mod.scoped_nodes]
    mod.attr_stores |= _py_attr_stores(loose)   # 專案內任何地方的屬性寫入都要算（類別本體、巢狀類別、if 裡的 def…）
    mod.opaque |= set(itertools.chain.from_iterable(n.names for n in loose if isinstance(n, ast.Global)))   # 類別本體、
    # 沒解析的方法裡 global 改寫模組層名字（模型沒建那一層）：之後是什麼看不到
    mod.scoped_nodes = set()
    if not any(f.entry for f in mod.funcs) and "main" in mod.defs:
        next(f for f in mod.funcs if f.id == mod.defs["main"]).entry = True
    return mod


def _py_scan(owner, stmts: list) -> list:
    """stmts 底下的節點走一次（不進巢狀 def/class），順手把 import 收進 owner（Module 或 Func）的 imports 與 import_sources。
    import_sources 以實際綁定的名字為鍵、每一次 import 都留：import a.b 綁的是套件 a（來源記 a），import a.b as c 綁的是 a.b。"""
    nodes = list(_own_nodes(stmts))
    for node in nodes:
        if isinstance(node, ast.Import):
            owner.imports.update({a.asname or a.name: (a.name, 0, "") for a in node.names})
            bound = [(a.asname or a.name.split(".")[0], (a.name if a.asname else a.name.split(".")[0], 0, "")) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            owner.imports.update({a.asname or a.name: (node.module or "", node.level, a.name) for a in node.names})
            bound = [(a.asname or a.name, (node.module or "", node.level, a.name)) for a in node.names if a.name != "*"]
        else:
            continue
        for name, source in bound:
            owner.import_sources.setdefault(name, []).append(source)
    return nodes


def _py_def_time(mod: Module, node) -> None:
    """模組層 def／class 定義時在模組層求值的運算式（預設值、裝飾器、標註、父類…）：裡面的綁定（推導式裡的 :=）、
    import 與訂閱照模組層的敘述算。"""
    nodes = _py_scan(mod, _def_time_exprs(node))
    _py_count_bindings(mod, nodes)
    notes = {id(s) for r in _def_annotations(node) for s in ast.walk(r)}   # 標註只當型別證據，不算呼叫
    _py_calls(mod, [n for n in nodes if id(n) not in notes], "")


def _is_main_guard(node: ast.AST) -> bool:
    test = getattr(node, "test", None)
    return (isinstance(node, ast.If) and isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name) and test.left.id == "__name__")


def _py_main_block(mod: Module, node: ast.If, tree: ast.Module) -> None:
    fid = f"{mod.file}::<main>"
    f = Func(fid, mod.file, "<main>", "<main>", "", "py", node.lineno, entry=True)
    nodes = _py_scan(mod, node.body)
    mod.scoped_nodes |= {id(n) for n in nodes}
    _py_count_bindings(mod, nodes)
    _py_locals(f, None, nodes)
    f.calls = _py_calls(mod, nodes, fid)
    f.scoped_binds = _py_unmodeled(nodes)[0]
    elsewhere = itertools.chain.from_iterable(ast.walk(s) for s in tree.body if s is not node)
    outside = {n.id for n in elsewhere if isinstance(n, ast.Name)}
    f.receiver_only = _py_receiver_only(f, node.body) - outside   # 區塊裡的變數是模組層名字：別處寫到它就不算
    mod.funcs.append(f)


def _py_stores(nodes: list) -> Counter:
    """被指定的名字各幾次；只有型別宣告沒給值的（handler: Callable）不算指定。"""
    bare = {id(n.target) for n in nodes if isinstance(n, ast.AnnAssign) and n.value is None}
    return Counter(n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and id(n) not in bare)


_OTHER_BINDERS = (ast.ExceptHandler, ast.MatchAs, ast.MatchStar, ast.MatchMapping, ast.ClassDef)


def _bound_name(node) -> str:
    """Name 節點以外的綁定寫法綁了哪個名字：import 別名（import a.b 綁 a）、except … as、match 擷取（case x、*rest、
    **rest）、def／class 名；不是這些、或沒綁名字（case _、except E:）→ ""。"""
    if isinstance(node, ast.alias):
        return "" if node.name == "*" else node.asname or node.name.split(".")[0]
    if isinstance(node, ast.MatchMapping):
        return node.rest or ""
    return (node.name or "") if isinstance(node, (*_OTHER_BINDERS, *_DEF_NODES)) else ""


def _py_other_binds(nodes: list) -> Counter:
    """Name、import、def 以外的綁定各幾次：except … as、match 擷取、巢狀 class（與 Name 指定一樣當區域變數）。"""
    return Counter(n for n in (_bound_name(x) for x in nodes if isinstance(x, _OTHER_BINDERS)) if n)


def _py_count_bindings(mod: Module, nodes: list) -> None:
    """模組層程式碼裡的綁定都算一次：被指定的名字、import、except … as、match 擷取、if／try 裡的 def 與 class
    （__main__ 區塊裡的也是模組層）。"""
    mod.bindings.update(_py_stores(nodes))
    mod.bindings.update(n for n in map(_bound_name, nodes) if n)


def _py_module_stmt(mod: Module, node: ast.stmt) -> None:
    """模組層其他敘述：收 import、分派表（NAME = {k: func}）、函式別名（NAME = mod.func）與訂閱（bus.on("k", f)）。
    名字被指定成算出來的值（NAME = pick()）→ 記成看不到，之後呼叫它不能沿用先前的別名。"""
    nodes = _py_scan(mod, [node])
    _py_count_bindings(mod, nodes)
    _py_calls(mod, nodes, "")
    target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else getattr(node, "target", None)
    value = getattr(node, "value", None)
    if not isinstance(target, ast.Name) or value is None:
        return
    refs = _py_table_refs(value)
    alias = _py_ref(value) if isinstance(value, (ast.Name, ast.Attribute)) else None
    if refs:
        mod.tables[target.id] = refs
    if alias:
        mod.aliases.setdefault(target.id, []).append(alias)
    if not (refs or alias or isinstance(value, (ast.Constant, ast.Lambda))):
        mod.opaque.add(target.id)


def _py_table_refs(value) -> list:
    """dict 字面值裡認得出是函式的值（f、self.f、mod.f、("pkg.mod", "func")）→ [(鍵, 參照)]；其他值略過。"""
    pairs = zip(value.keys, value.values) if isinstance(value, ast.Dict) else []
    return [(_py_literal(k), r) for k, v in pairs if (r := _py_ref(v) or _py_str_ref(v))]


def _py_literal(node) -> str:
    return str(node.value) if isinstance(node, ast.Constant) and isinstance(node.value, (str, int)) else ""


def _py_str_ref(expr) -> Call | None:
    """惰性 import 表的值 ("pkg.mod", "func") → 指向那個模組裡的函式。"""
    elts = expr.elts if isinstance(expr, ast.Tuple) else []
    names = [e.value for e in elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return Call("attr", names[1], recv="mod:" + names[0]) if len(elts) == len(names) == 2 else None


def _py_class(mod: Module, node: ast.ClassDef) -> None:
    bases = [_py_recv(b) for b in node.bases if _py_recv(b)]      # 保留模組前綴（collections.UserDict），沿綁定鏈解析
    markers = [b for b in node.bases if isinstance(b, ast.Subscript) and _py_recv(b.value).split(".")[-1] in GENERIC_MARKERS]
    opaque = len(node.bases) - len(bases) - len(markers)           # Base[int]、make_base() 這類算出來的父類：MRO 證不出
    metaclass = next((_py_recv(k.value) for k in node.keywords if k.arg == "metaclass"), "")
    cls = Cls(node.name, "py", [mod.file], bases, decorators=_py_decorators(node), opaque_bases=opaque, metaclass=metaclass)
    for item in node.body:
        if isinstance(item, _DEF_NODES):
            _py_func(mod, item, node.name + ".", cls)
            cls.def_decorators.setdefault(item.name, []).extend(_py_decorators(item))
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and _py_ann(item.annotation):
            cls.fields[item.target.id] = cls.declared_fields[item.target.id] = _py_ann(item.annotation)
            cls.field_scope[item.target.id] = cls.declared_scope[item.target.id] = ""   # 類別本體的標註在類別本體解析
    defs = [item for item in node.body if isinstance(item, _DEF_NODES)]
    rest = [item for item in node.body if not isinstance(item, _DEF_NODES)]
    plain = list(_own_nodes(rest + [x for d in defs for x in _def_time_exprs(d)]))   # 方法的預設值、裝飾器、標註在類別本體求值
    names = set(_py_stores(plain)) | {n for n in map(_bound_name, plain) if n}
    mod.attr_stores |= {(node.name, name) for name in names}   # 類別本體 run = other、import run、巢狀 class run：蓋掉同名方法
    cls.body_names = names | {item.name for item in node.body if isinstance(item, _DEF_NODES)}
    mod.classes.append(cls)


def _py_func(mod: Module, node, prefix: str, cls: Cls | None) -> None:
    qual = prefix + node.name
    fid = f"{mod.file}::{qual}"
    positional = node.args.posonlyargs + node.args.args
    args = positional + node.args.kwonlyargs
    pairs = list(zip(positional[len(positional) - len(node.args.defaults):], node.args.defaults))
    pairs += [(a, d) for a, d in zip(node.args.kwonlyargs, node.args.kw_defaults) if d is not None]
    f = Func(fid, mod.file, qual, node.name, cls.name if cls else "", "py", node.lineno,
             params=[a.arg for a in args],
             param_types={a.arg: _py_ann(a.annotation) for a in args if _py_ann(a.annotation)},
             defaults={a.arg: r for a, d in pairs if (r := _py_ref(d))},
             blind_defaults={a.arg for a, d in pairs if _py_blind(d)}, decorators=_py_decorators(node))
    body = _strip_doc(node.body)
    nodes = _py_scan(f, body)
    mod.scoped_nodes |= {id(n) for n in nodes}
    real = [s for s in body if not isinstance(s, ast.Pass) and not _py_noise_stmt(s) and not _py_move(s)]
    f.simple = (len(real) <= 2 and all(isinstance(s, _SIMPLE_STMTS) for s in real)
                and not any(isinstance(n, _BRANCHY) for n in nodes))
    f.abstract = any(_py_recv(d).split(".")[-1] == "abstractmethod" for d in node.decorator_list)
    f.hollow = _py_hollow(body)
    _py_locals(f, cls, nodes)
    f.calls = _py_calls(mod, nodes, fid)
    f.scoped_binds, f.class_nonlocals = _py_unmodeled(nodes)
    f.global_names = set(itertools.chain.from_iterable(n.names for n in nodes if isinstance(n, ast.Global)))
    bound = f.locals | {n for n in map(_bound_name, nodes) if n}   # 這一層任何寫法綁定的名字（指定、import、def、class…）
    mod.opaque |= f.global_names & bound               # 函式用 global 改寫模組層名字：之後是什麼看不到
    f.nonlocal_names = set(itertools.chain.from_iterable(n.names for n in nodes if isinstance(n, ast.Nonlocal)))
    f.nonlocal_writes = f.nonlocal_names & bound       # 改的是外層函式的名字（reading-path 回頭標到真正持有它的那一層）
    f.receiver_only = _py_receiver_only(f, body)
    mod.funcs.append(f)
    if cls:
        cls.methods.setdefault(node.name, []).append(fid)
    elif not prefix:
        mod.defs[node.name] = fid
    for sub in [n for n in nodes if isinstance(n, _DEF_NODES)]:
        _py_func(mod, sub, qual + ".", cls)


def _py_unmodeled(nodes: list) -> tuple:
    """模型沒建參數與綁定的作用域構件裡「會改變綁定」的寫法 → (被綁定的名字, 巢狀類別本體裡 nonlocal 宣告的名字)。
    只算綁定、不算讀取（讀取不改變外層名字的綁定）：lambda／生成器／推導式整棵裡的 lambda 參數、迴圈目標與 :=
    （推導式裡的 := 綁在外層函式）；巢狀類別本體整棵（含它的方法）裡的 global／nonlocal 宣告。
    類別本體自己的指定、方法參數只綁在類別或方法裡，不改外層，不算。"""
    exprs = list(itertools.chain.from_iterable(ast.walk(n) for n in nodes if isinstance(n, _SCOPE_EXPRS)))
    bodies = [s for n in nodes if isinstance(n, ast.ClassDef) for s in n.body]
    in_class = list(itertools.chain.from_iterable(ast.walk(s) for s in bodies))
    binds = {n.arg for n in exprs if isinstance(n, ast.arg)}
    binds |= {n.id for n in exprs if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}
    declared = [n for n in in_class if isinstance(n, (ast.Global, ast.Nonlocal))]
    binds |= set(itertools.chain.from_iterable(n.names for n in declared))
    return binds, set(itertools.chain.from_iterable(n.names for n in declared if isinstance(n, ast.Nonlocal)))


def _scoped_spots(nodes: list) -> dict:
    """nodes 裡位在 lambda／生成器／推導式裡的節點 id → 包住它的那些構件自己綁定的名字（巢狀的取聯集）。
    構件整棵都算在裡面（含 lambda 預設值、推導式第一層的來源；寧可多算）。"""
    inside = {}
    for node in [n for n in nodes if isinstance(n, _SCOPE_EXPRS)]:
        binds = _construct_binds(node)
        for sub in itertools.islice(ast.walk(node), 1, None):
            inside.setdefault(id(sub), set()).update(binds)
    return inside


def _construct_binds(node) -> set:
    """lambda 的參數，或推導式各層 for 的目標名字。"""
    if isinstance(node, ast.Lambda):
        a = node.args
        return {x.arg for x in [*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg] if x}
    return {n.id for g in node.generators for n in ast.walk(g.target) if isinstance(n, ast.Name)}


def _own_nodes(stmts):
    """stmts 底下屬於這一層的節點：巢狀 def/class 本身會給出，它定義時在這一層求值的運算式（_def_time_exprs）也算這一層；
    def 本體與類別本體不往裡走（那是別的函式、別的作用域）。"""
    stack = list(stmts)
    while stack:
        node = stack.pop()
        yield node
        nested = isinstance(node, (*_DEF_NODES, ast.ClassDef))
        stack.extend(_def_time_exprs(node) if nested else ast.iter_child_nodes(node))


def _def_time_exprs(node) -> list:
    """def／class 敘述在定義當下、於外層作用域求值的運算式：def 的裝飾器、參數預設值（含只限關鍵字的）、參數與回傳標註；
    class 的裝飾器、父類、keywords（metaclass=…）。"""
    if isinstance(node, ast.ClassDef):
        return [*node.decorator_list, *node.bases, *node.keywords]
    a = node.args
    return [*node.decorator_list, *a.defaults, *[d for d in a.kw_defaults if d], *_def_annotations(node)]


def _def_annotations(node) -> list:
    """def 的參數標註與回傳標註（class 沒有，回空）。綁定（:=）照外層算，但裡面的呼叫不算呼叫（標註可能延後求值）。"""
    if isinstance(node, ast.ClassDef):
        return []
    a = node.args
    params = [p for p in [*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg] if p]
    return [p.annotation for p in params if p.annotation] + ([node.returns] if node.returns else [])


def _annotation_ids(nodes: list) -> set:
    """nodes 裡標註整棵的節點 id：巢狀 def 的參數與回傳標註、變數標註（x: T = …）。標註可能延後求值或根本不求值
    （from __future__ import annotations、Python 3.14 以後、函式裡的變數標註），裡面的呼叫不算呼叫，只當型別證據。"""
    roots = [n.annotation for n in nodes if isinstance(n, ast.AnnAssign)]
    roots += [r for n in nodes if isinstance(n, _DEF_NODES) for r in _def_annotations(n)]
    return {id(s) for r in roots for s in ast.walk(r)}


def _py_decorators(node) -> list:
    """裝飾器寫法 [(staticmethod／functools.lru_cache／name.setter…, 是否當場呼叫 @deco(…), 字面 keyword 引數 {名: 值})]；
    寫不成名字的（lambda、下標…）記 ""；keyword 只留寫死的字面值（dataclass(init=False) 判斷要用）。"""
    out = []
    for d in node.decorator_list:
        called = isinstance(d, ast.Call)
        kwargs = {k.arg: k.value.value for k in (d.keywords if called else []) if k.arg and isinstance(k.value, ast.Constant)}
        out.append((_py_recv(d.func if called else d), called, kwargs))
    return out


def _strip_doc(body: list) -> list:
    first = body[0] if body else None
    is_doc = isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)
    return body[1:] if is_doc else body


def _py_hollow(body: list) -> bool:
    """空實作：docstring 之外什麼都沒有、只有 pass、只有 ...、只有 raise NotImplementedError。是存在的覆寫（子類寫了就擋掉
    父類的方法，不論所在類別抽不抽象），只是不當落點；真抽象只看方法本身有沒有掛 @abstractmethod。"""
    only = body[0] if len(body) == 1 else None
    if not body or isinstance(only, ast.Pass):
        return True
    if isinstance(only, ast.Expr) and getattr(only.value, "value", None) is Ellipsis:
        return True
    exc = getattr(only, "exc", None) if isinstance(only, ast.Raise) else None
    return bool(exc) and _py_recv(getattr(exc, "func", exc)) == "NotImplementedError"


def _py_move(stmt: ast.stmt) -> bool:
    """只是把值換個區域變數名（y = x、y = self.x、y = 3）：沒有內容，不算進轉手判定的句數。存進 self.x 是改狀態，不算。"""
    targets = stmt.targets if isinstance(stmt, ast.Assign) else [getattr(stmt, "target", None)]
    value = getattr(stmt, "value", None) if isinstance(stmt, (ast.Assign, ast.AnnAssign)) else None
    return isinstance(value, (ast.Name, ast.Attribute, ast.Constant)) and all(isinstance(t, ast.Name) for t in targets)


def _py_noise_stmt(stmt: ast.stmt) -> bool:
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
        return False
    c = _py_call(stmt.value)
    return bool(c and c.noise)


def _py_ann(ann) -> str:
    """型別標註取類別的寫法：Repo、mod.Repo（保留模組前綴，reading-path 才能沿綁定鏈分出 pathlib.Path 與專案的 Path）、
    Optional[Repo]、Repo | None、"Repo"／"mod.Repo"（字串照運算式解析，前綴一樣保留）；容器（list[Repo]）回容器名，
    不是 Repo；聯集有兩個以上非 None 成員（Disk | Cloud）→ 空字串（型別不定，不挑一個）；字串解析不了 → 空字串。"""
    if isinstance(ann, ast.BinOp):
        members = [m for m in (ann.left, ann.right) if not _py_is_none(m)]
        return _py_ann(members[0]) if len(members) == 1 else ""
    if isinstance(ann, ast.Subscript):
        head = _py_recv(ann.value)
        elts = ann.slice.elts if isinstance(ann.slice, ast.Tuple) else [ann.slice]
        last = head.split(".")[-1]
        members = [e for e in elts if not _py_is_none(e)] if last == "Union" else elts[:1]
        if last not in ("Optional", "Union", "Annotated", "Final", "ClassVar"):
            return head
        return _py_ann(members[0]) if len(members) == 1 else ""
    if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
        try:
            return _py_ann(ast.parse(ann.value.strip(), mode="eval").body)
        except SyntaxError:
            return ""
    return _py_recv(ann) if ann is not None else ""


def _py_is_none(node) -> bool:
    return (isinstance(node, ast.Constant) and node.value is None) or (isinstance(node, ast.Name) and node.id == "None")


def _py_recv(expr) -> str:
    """接收者寫成字串：self、self.repo、mod.sub；Foo() → new:Foo；super() → super()；帶引數的 super(B, self) → super(…)；
    其他為空。"""
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        head = _py_recv(expr.value)
        return f"{head}.{expr.attr}" if head and not head.startswith(("new:", "super")) else ""
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name):
        if expr.func.id == "super":
            return "super(…)" if expr.args or expr.keywords else "super()"
        return "new:" + expr.func.id
    return ""


def _py_table(expr):
    """TABLE[k] 或 TABLE.get(k) → ("TABLE", k 若是寫死的字面值)；不是 → ("", "")。"""
    if isinstance(expr, ast.Subscript) and isinstance(expr.value, ast.Name):
        return expr.value.id, _py_literal(expr.slice)
    fn = expr.func if isinstance(expr, ast.Call) else None
    if isinstance(fn, ast.Attribute) and fn.attr == "get" and isinstance(fn.value, ast.Name):
        return fn.value.id, _py_literal(expr.args[0]) if expr.args else ""
    return "", ""


def _py_call(node: ast.Call) -> Call | None:
    fn, line = node.func, node.lineno
    table, key = _py_table(fn)
    if table:
        return Call("table", table, line=line, key=key)
    if isinstance(fn, ast.Name):
        return Call("name", fn.id, line=line, noise=fn.id in NOISE_CALLS)
    if isinstance(fn, ast.Call) and _py_recv(fn.func) == "getattr":
        names = sorted({n.id for n in itertools.chain.from_iterable(ast.walk(a) for a in fn.args) if isinstance(n, ast.Name)})
        return Call("getattr", ",".join(names), line=line)
    if not isinstance(fn, ast.Attribute):          # 就地呼叫 lambda：內容在這裡；其他算出來的對象：看不到
        return None if isinstance(fn, ast.Lambda) else Call("opaque", "", line=line)
    recv = _py_recv(fn.value)
    if recv in ("self", "cls"):
        return Call("self", fn.attr, recv=recv, line=line)
    if recv == "super()":
        return Call("super", fn.attr, line=line)
    if recv == "super(…)":                         # 顯式起點 super(B, self).m()：起點沒建模，recv 留記號給 reading-path 降級
        return Call("super", fn.attr, recv="explicit", line=line)
    return Call("attr", fn.attr, recv=recv, line=line, noise=_is_noise("attr", fn.attr, recv))


def _py_ref(expr) -> Call | None:
    """被當值傳遞的函式參照：f、self.f、mod.f。"""
    if isinstance(expr, ast.Name):
        return Call("name", expr.id)
    recv = _py_recv(expr.value) if isinstance(expr, ast.Attribute) else ""
    if recv in ("self", "cls"):
        return Call("self", expr.attr, recv=recv)
    return Call("attr", expr.attr, recv=recv) if recv and not recv.startswith("new:") else None


def _py_blind(expr) -> bool:
    """引數是算出來的值（呼叫結果、下標、條件運算…）：如果被當函式用，看不到是哪一個。"""
    return isinstance(expr, (ast.Call, ast.Subscript, ast.IfExp, ast.BoolOp, ast.Await))


def _py_calls(mod: Module, nodes: list, owner: str) -> list:
    """呼叫點；位在 lambda／生成器／推導式裡的（連同它引數裡的函式參照）標 scoped，名字被那個構件自己綁定的標 shadowed。"""
    calls, inside, notes = [], _scoped_spots(nodes), _annotation_ids(nodes)
    for node in nodes:
        c = _py_call(node) if isinstance(node, ast.Call) and id(node) not in notes else None   # 標註裡的不算呼叫
        if c is None:
            continue
        c.refs = [(i, r) for i, a in enumerate(node.args) if (r := _py_ref(a))]
        c.refs += [(k.arg, r) for k in node.keywords if k.arg and (r := _py_ref(k.value))]
        stars = [i for i, a in enumerate(node.args) if isinstance(a, ast.Starred)]
        c.nargs, c.kwargs = len(node.args), {k.arg for k in node.keywords if k.arg}
        c.star, c.dstar = (stars[0] if stars else -1), any(k.arg is None for k in node.keywords)
        c.blind = {i for i, a in enumerate(node.args) if _py_blind(a)} | {k.arg for k in node.keywords if k.arg and _py_blind(k.value)}
        events = _py_events(mod, node, c, owner)
        binds = inside.get(id(node))
        for x in [c, *events, *(r for _, r in c.refs)] if binds is not None else []:
            x.scoped, x.shadowed = True, x.kind == "name" and x.name in binds
        calls.append(c)
        calls.extend(events)
    return sorted(calls, key=lambda c: c.line)


def _py_events(mod: Module, node: ast.Call, c: Call, owner: str) -> list:
    """發事件 → 多一個 emit 呼叫；訂閱 → 記進 mod.subs（emit 端用同一把鍵找回處理函式）。"""
    if c.kind not in ("name", "attr", "self") or c.name not in EMIT_NAMES | SUB_NAMES:
        return []
    first = node.args[0] if node.args else None
    literal = first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else ""
    recv = "" if c.kind == "self" else c.recv          # self.emit(…)：接收者是物件自己，不拿來當事件鍵
    key = _event_key(literal, recv)
    if c.name in EMIT_NAMES:
        return [Call("emit", key, recv=recv, line=c.line)] if key else []
    if key and c.refs:
        mod.subs.append((key, c.refs[-1][1], owner, mod.file, recv))
    return []


CONTAINER_ADD = {"append", "appendleft", "extend", "insert", "add", "setdefault", "update", "put", "push"}


def _py_locals(f: Func, cls: Cls | None, nodes: list) -> None:
    """區域變數型別（標註與建構分開記）、分派表變數、被存進欄位或容器的區域變數；
    方法裡的 self.x = Foo() 記欄位型別（推導）、self.x: Foo = … 記欄位宣告型別、self.x = 參數 記成 callback 欄位。"""
    for node in nodes:
        ann = _py_ann(node.annotation) if isinstance(node, ast.AnnAssign) else ""
        if ann and isinstance(node.target, ast.Name):
            f.local_types[node.target.id] = f.declared[node.target.id] = ann
        if ann and cls and isinstance(node.target, ast.Attribute) and _py_recv(node.target.value) == "self":
            cls.fields[node.target.attr] = cls.declared_fields[node.target.attr] = ann
            cls.field_scope[node.target.attr] = cls.declared_scope[node.target.attr] = f.id   # 方法本體裡的標註在本體解析
        if isinstance(node, ast.AnnAssign) and node.value is not None:
            _py_bind(f, cls, node.target, node.value)      # w: Base = Child()：實際型別看建構的那個
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            _py_bind(f, cls, node.targets[0], node.value)
        f.escaped |= _py_contained(node)
    f.attr_stores = _py_attr_stores(nodes)
    for _ in range(len(f.aliases)):                    # v = w 之後 v 被存走，w 指的物件也被存走了
        f.escaped |= {ref.name for v, ref in f.aliases.items() if v in f.escaped and ref.kind == "name"}
    stores = _py_stores(nodes) + _py_other_binds(nodes)   # except … as、match 擷取、巢狀 class 也是區域綁定
    f.locals = set(stores)
    f.inline |= {n.name for n in nodes if isinstance(n, ast.ClassDef)}   # 就地定義的類別：建構它不算未解
    stores.update(f.params)
    stores.update(n.name for n in nodes if isinstance(n, _DEF_NODES))   # 巢狀 def 也是一次綁定
    f.reassigned = {name for name, k in stores.items() if k > 1}
    imported = Counter(_py_import_names(nodes))        # 函式裡的 import 也是一次綁定：import 又指定（或又 def）→ 不穩定；
    f.import_rebinds = {name for name in imported if stores[name] > 0}   # 只 import 好幾次的交給 reading-path 比對來源


def _py_import_names(nodes: list) -> list:
    imports = [n for n in nodes if isinstance(n, (ast.Import, ast.ImportFrom))]
    return [(a.asname or a.name).split(".")[0] for a in itertools.chain.from_iterable(n.names for n in imports)]


def _py_attr_stores(nodes: list) -> set:
    """被指定或 del 的屬性 (接收者, 屬性名)：self.run = f、w.run = f、worker.work = f、setattr(X, "run", f)（名字是字串字面值）；
    接收者寫不成字串的（get().run = f、items[0].run = f、setattr(get(), "run", f)）記成 "?"：型別看不出，用名字保守判定。"""
    stored = [n for n in nodes if isinstance(n, ast.Attribute) and isinstance(n.ctx, (ast.Store, ast.Del))]
    out = {(_py_recv(n.value) or "?", n.attr) for n in stored}
    calls = [n for n in nodes if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "setattr"]
    literal = [c for c in calls if len(c.args) >= 2 and isinstance(c.args[1], ast.Constant) and isinstance(c.args[1].value, str)]
    return out | {(_py_recv(c.args[0]) or "?", c.args[1].value) for c in literal}


_CONTAINERS = (ast.List, ast.Tuple, ast.Set, ast.Dict)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)


def _py_contained(node) -> set:
    """被放進容器的區域變數名：容器字面值或推導式裡直接寫的名字（巢狀的容器各自會被走到，所以 [[w]] 也算），
    或 lst.append(w) 這類加進容器的呼叫。拆包的指定目標（a, b = …）不算。"""
    if isinstance(node, _CONTAINERS) and not isinstance(getattr(node, "ctx", None), ast.Store):
        elts = [*node.keys, *node.values] if isinstance(node, ast.Dict) else node.elts
    elif isinstance(node, _COMPREHENSIONS):
        elts = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in CONTAINER_ADD:
        elts = node.args
    else:
        return set()
    names = [e.value if isinstance(e, ast.Starred) else e for e in elts]
    return {e.id for e in names if isinstance(e, ast.Name)}


def _py_receiver_only(f: Func, body: list) -> set:
    """白名單 2 的正向證明：建構之後每一次出現都只是方法呼叫的接收者（w.m(…)）的區域變數。
    只允許一次單一目標的建構指定（w = Foo(…)、w: T = Foo(…)）＋若干 w.m(…)；其他任何出現，像當引數（位置或具名）、
    被指定給別的目標（含鏈式、解構）、放進容器、return、yield、讀 w.x 不呼叫、w.x = …、del，都失去資格；
    任何一次出現位在巢狀作用域（def、lambda、生成器、推導式、類別本體）裡，就算被捕捉，就算是 w.m(…) 也失去資格。
    不列舉「存走」有哪些寫法：沒被允許的就是不行。Name 以外的綁定（import、except … as、match 擷取、
    def／class 名，巢狀作用域裡的也算）只要綁到同一個名字，就是又綁了一次，同樣失去資格。"""
    seen, rebound = {}, set()                          # 名字 → [(Name 節點, 父節點, 祖父節點, 是否在巢狀作用域裡)]
    stack = [(node, None, None, False) for node in body]
    while stack:
        node, parent, grand, inner = stack.pop()
        if isinstance(node, ast.Name):
            seen.setdefault(node.id, []).append((node, parent, grand, inner))
        rebound.add(_bound_name(node))
        nested = inner or isinstance(node, (*_DEF_NODES, ast.ClassDef, *_SCOPE_EXPRS))
        stack.extend((child, node, parent, nested) for child in ast.iter_child_nodes(node))
    skip = set(f.params) | f.global_names | f.nonlocal_names | rebound
    return {name for name in f.constructed if name not in skip and _only_receiver(seen.get(name, []))}


def _only_receiver(spots: list) -> bool:
    builds = sum(1 for s in spots if _is_build(*s))
    calls = sum(1 for s in spots if _is_receiver(*s))
    return builds == 1 and builds + calls == len(spots)


def _is_build(node, parent, _grand, inner) -> bool:
    """w = Foo(…)／w: T = Foo(…)：單一目標、右邊是建構寫法、不在巢狀作用域裡。"""
    if inner or not isinstance(node.ctx, ast.Store):
        return False
    if isinstance(parent, ast.Assign):
        return len(parent.targets) == 1 and parent.targets[0] is node and bool(_py_ctor(parent.value))
    return (isinstance(parent, ast.AnnAssign) and parent.target is node and parent.value is not None
            and bool(_py_ctor(parent.value)))


def _is_receiver(node, parent, grand, inner) -> bool:
    """w.m(…)：讀 w、它是屬性存取的對象、那個屬性正被呼叫；不在巢狀作用域裡。"""
    return (not inner and isinstance(node.ctx, ast.Load) and isinstance(parent, ast.Attribute) and parent.value is node
            and isinstance(grand, ast.Call) and grand.func is parent)


def _py_ctor(value) -> str:
    """指定的右邊是建構（Foo()、worker.Foo()）→ 建構者寫法（"Foo"、"worker.Foo"）；不是 → ""。
    worker.Foo() 也可能是普通的模組函式呼叫，是不是類別交給 reading-path 解析（解不到類別就不當型別證據）。"""
    fn = value.func if isinstance(value, ast.Call) else None
    if isinstance(fn, ast.Name):
        return "" if fn.id == "super" else fn.id
    return _py_recv(fn) if isinstance(fn, ast.Attribute) else ""


def _py_bind(f: Func, cls: Cls | None, target, value) -> None:
    ctor = _py_ctor(value)
    table, refs = _py_table(value)[0], _py_table_refs(value)
    alias = _py_ref(value) if isinstance(value, (ast.Name, ast.Attribute)) else None
    if isinstance(target, ast.Name):
        if ctor:
            f.local_types[target.id] = f.constructed[target.id] = ctor
        if table:
            f.table_vars[target.id] = table
        if refs:
            f.tables[target.id] = refs
        if alias:
            f.aliases[target.id] = alias
        if isinstance(value, ast.Lambda):
            f.inline.add(target.id)
        return
    if isinstance(target, (ast.Attribute, ast.Subscript)) and isinstance(value, ast.Name):
        f.escaped.add(value.id)                    # 區域變數被存進欄位或容器
    if not (cls and isinstance(target, ast.Attribute) and _py_recv(target.value) == "self"):
        return
    if ctor:
        cls.fields[target.attr] = ctor
        cls.field_scope[target.attr] = f.id
    elif isinstance(value, ast.Name) and value.id in f.params:
        cls.stored[target.attr] = (f.id, value.id)


# ─── C#（括號配對＋正規式，不用 Roslyn） ─────────────────────────────────────

_C_BLANK = re.compile(r'//[^\n]*|/\*.*?\*/|(?:\$@|@\$|@)"(?:[^"]|"")*"|\$?"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])+\'', re.S)
_HOLE = re.compile(r"\{\{|\}\}|\{([^{}]*)\}")
_CS_CLASS = re.compile(
    r"(?P<mods>(?:(?:public|private|protected|internal|static|sealed|abstract|partial|readonly|unsafe|new|file)\s+)*)"
    r"\b(?P<kind>class|struct|interface|record)\s+(?P<name>\w+)(?:\s*<[^>{;]*>)?(?:\s*\([^)]*\))?"
    r"\s*(?::\s*(?P<bases>[^{;]+?))?\s*(?:where\s[^{;]*)?\{")
_CS_SIG = re.compile(r"(?P<name>\w+)\s*(?:<[^<>()]*>)?\s*\((?P<params>[^()]*(?:\([^()]*\)[^()]*)*)\)"
                     r"\s*(?::\s*(?:base|this)\s*\([^()]*\))?\s*(?:where\s.*)?$", re.S)
_CS_CONDITIONAL = re.compile(r"\[\s*(?:System\.Diagnostics\.)?Conditional\s*\(")   # [Conditional("DEBUG")]：符號沒定義就不呼叫
_CS_OPAQUE_CALL = re.compile(r"\]\s*\(|\)\s*\(")   # handlers[0]()、Get()()：下標或運算結果上的呼叫，對象看不到
_CS_LAMBDA = re.compile(r"(?:\((?P<params>[^()]*)\)|(?P<one>\b[a-z_]\w*))\s*=>")   # (a, b) =>、x =>：lambda 的參數
_CS_CALL = re.compile(r"(?P<new>\bnew\s+)?(?P<recv>(?:\w+\s*\??\.\s*)*)(?P<name>\w+)\s*(?:<[^<>();]*>)?\s*\(")
_CS_SUB = re.compile(r"(?P<lhs>[\w.]+)\s*\+=\s*(?P<rhs>[A-Za-z_][\w.]*)\s*;")
_CS_LISTEN = re.compile(r"(?P<lhs>[\w.]+)\s*\.\s*AddListener\s*\(\s*(?P<rhs>[A-Za-z_][\w.]*)\s*\)")
_CS_LOCAL = re.compile(r"\b(?:var|(?P<type>[A-Z]\w*)(?:<[^<>;=]*>)?)\s+(?P<var>[a-z_]\w*)\s*=\s*(?:new\s+(?P<new>\w+))?")
_CS_ALIAS = re.compile(r"\b(?:var|[A-Z]\w*(?:<[^<>;=]*>)?)\s+(?P<var>[a-z_]\w*)\s*=\s*(?P<rhs>[A-Za-z_][\w.]*)\s*;")
_CS_STORE = re.compile(r"\b([a-z_]\w*)\s*=(?![=>])")   # 區域變數被指定（宣告或重新指定；不含 ==、=>、+=）
_CS_MODIFY = re.compile(r"\b([a-z_]\w*)\s*[+\-]=(?!=)")   # cb += B、cb -= A：委派被改（數值也算，只影響別名與確定型別）
_CS_INITIALIZER = re.compile(r"\bnew\b[^;{}]*\{([^{}]*)\}")   # 陣列／集合／物件初始化的大括號內容（寧可多算存走）
_CS_LOWER_NAME = re.compile(r"(?<![\w.])([a-z_]\w*)\b")
_CS_CONTAINER_ADD = re.compile(r"\.\s*(?:Add|Insert|Push|Enqueue|AddLast|AddFirst)\s*\(\s*(?:\w+\s*,\s*)?([a-z_]\w*)\s*\)")
_CS_BYREF = re.compile(r"\b(?:ref|out)\s+(?:var\s+|[\w<>\[\],.?]+\s+(?=[a-z_]\w*\s*[,)]))?([a-z_]\w*)")
_CS_INLINE = re.compile(r"(?:^|[;{}])\s*(?:(?:static|async)\s+)*(?P<type>[\w<>\[\],?.]+)\s+(?P<name>\w+)\s*"
                        r"(?:\([^()]*\)\s*(?:\{|=>)|=\s*(?:\([^()]*\)|\w+)\s*=>)", re.M)   # 區域函式、lambda 變數
_CS_ASSIGN = re.compile(r"(?:this\.)?(?P<lhs>\w+)\s*=\s*(?:new\s+(?P<new>\w+)|(?P<rhs>\w+)\s*;)")
_CS_REF = re.compile(r"(?:(?P<recv>\w+)\.)?(?P<name>[A-Za-z_]\w*)")
_CS_NAMED_ARG = re.compile(r"(\w+)\s*:(?!:)\s*(.*)", re.S)
_CS_INLINE_ARG = re.compile(r"|[\d.]+[a-zA-Z]*|true|false|null|default|(?:new|typeof|nameof|ref|out|in)\b.*", re.S)
_CS_ATTR = re.compile(r"\[\s*[A-Za-z_][^\[\]]*\]")   # attribute 以識別字開頭；陣列的 [] 與 [,] 不是 attribute，要留著
_CS_TYPE_DECL = re.compile(r"\b(class|struct|interface|record|enum|namespace|delegate)\b")
_CS_COMPOUND = re.compile(r"\b(if|for|foreach|while|switch|try|do|lock)\b|\busing\s*\(")
_CS_MOVE = re.compile(r"[\w<>\[\],.?]+\s+[a-z_]\w*\s*=\s*[\w.]+")   # var y = x;：宣告區域變數只換個名字
_CS_PROP_USE = re.compile(r"(?<![\w.?])(?P<recv>(?:\w+\s*\??\.\s*)*)(?P<name>[A-Z]\w*)\b(?!\s*[(<\w])")
_CS_ACCESSOR = re.compile(r"\b(get|set|init)\s*(\{|=>)")
_CS_RECV_CALL = re.compile(r"\s*\??\s*\.\s*\w+\s*(?:<[^<>();]*>)?\s*\(")   # 接在變數名後面的 .M( 或 ?.M(
CS_KEYWORDS = {"if", "for", "foreach", "while", "switch", "catch", "using", "lock", "return", "typeof", "nameof",
               "sizeof", "default", "checked", "unchecked", "fixed", "when", "base", "this", "new", "throw",
               "await", "get", "set", "in", "is", "as", "out", "ref", "var", "else", "do", "try", "yield", "stackalloc"}


def _blank(m: re.Match) -> str:
    """註解與字串換成等長空白（保留換行，行號不跑掉）；插值字串 $"…{運算式}…" 留下 {} 裡的運算式（大括號本身仍換掉）。"""
    text = m.group()
    out = list(re.sub(r"[^\n]", " ", text))
    holes = _HOLE.finditer(text) if text.startswith(("$", "@$")) else []
    for h in [h for h in holes if h.group(1)]:
        out[h.start(1):h.end(1)] = h.group(1)
    return "".join(out)


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
    """依頂層逗號切開（括號裡的逗號不算）。空白文字回 []；中間被抹成空白的字串引數保留成空字串，位置才不會錯。"""
    if not text.strip():
        return []
    opens, closes = pairs[0::2], pairs[1::2]
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        depth += (ch in opens) - (ch in closes)
        if ch == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p.strip() for p in parts]


def parse_csharp(rel: str, text: str) -> Module:
    src = _C_BLANK.sub(_blank, text)
    depth, pairs = _braces(src)
    mod = Module(rel, "cs")
    mod.static_usings = re.findall(r"\busing\s+static\s+([\w.]+)\s*;", src)
    for m in _CS_CLASS.finditer(src):
        bases = [b.split(".")[-1] for b in _split_top(_strip_generics(m["bases"] or ""))]
        cls = Cls(m["name"], "cs", [rel], bases, partial="partial" in m["mods"].split())
        first = len(mod.funcs)
        for member in _cs_members(src, depth, pairs, m.end() - 1):
            _cs_member(mod, cls, src, depth, member)
        _cs_sign_overloads(mod, cls, mod.funcs[first:])
        mod.classes.append(cls)
    return mod


def _cs_sign_overloads(mod: Module, cls: Cls, funcs: list) -> None:
    """同名多載每一個（含第一個）都改用「名稱(參數型別)」當 id，宣告順序、插入刪除都對得上；沒多載的維持裸名。"""
    counts = Counter(f.name for f in funcs)
    renames = {}
    for f in [f for f in funcs if counts[f.name] > 1]:
        sig = f"{f.file}::{f.qual}({f.sig})"
        renames[f.id] = sig if sig not in renames.values() else f"{sig}#{len(renames)}"
        f.id = renames[f.id]
    if not renames:
        return
    cls.methods = {name: [renames.get(i, i) for i in ids] for name, ids in cls.methods.items()}
    cls.stored = {attr: (renames.get(fid, fid), param) for attr, (fid, param) in cls.stored.items()}
    mod.subs = [(key, ref, renames.get(owner, owner), file, recv) for key, ref, owner, file, recv in mod.subs]


def _cs_members(src: str, depth: list, pairs: dict, open_i: int):
    """class 本體那一層的成員：yield (標頭, 標頭起點, 本體起, 本體迄, 是否 =>, 是否只有分號宣告)。
    空大括號 {} 的本體起迄相同，跟分號宣告（abstract、介面）要分得開：前者是空實作，後者才是沒有本體。"""
    close_i = pairs.get(open_i, len(src))
    level = depth[open_i] + 1
    start = i = open_i + 1
    while i < close_i:
        ch = src[i]
        if ch == "{" and depth[i] == level:
            end = pairs.get(i, close_i)
            yield src[start:i], start, i + 1, end, False, False
            start = i = end + 1
            continue
        if ch == ";" and depth[i] == level:
            head, arrow, _ = src[start:i].partition("=>")
            yield (head, start, start + len(head) + 2, i, True, False) if arrow else (head, start, i, i, False, True)
            start = i + 1
        i += 1


def _cs_member(mod: Module, cls: Cls, src: str, depth: list, member: tuple) -> None:
    raw, start, b0, b1, arrow, declared = member
    head = _CS_ATTR.sub(" ", raw).strip()
    if not head or _CS_TYPE_DECL.search(head):
        return
    sig = _CS_SIG.search(head)
    is_prop = not sig or "=" in head[:sig.start()] or sig["name"] in CS_KEYWORDS
    if is_prop:
        _cs_field(cls, head)
        if declared or "=" in head or not (arrow or _CS_ACCESSOR.search(src[b0:b1])):
            return
        name, mods, texts = head.split()[-1], set(), []     # 屬性的 get/set 本體：當成以屬性為名的節點
    else:
        name, mods, texts = sig["name"], set(head[:sig.start()].split()), _split_top(sig["params"], "()[]{}<>")
    params = [p for p in (_cs_param(t) for t in texts) if p]
    base = f"{mod.file}::{cls.name}.{name}"
    fid = base if all(f.id != base for f in mod.funcs) else f"{base}#{b0}"   # 暫用；多載在整個類別讀完後改成簽章 id
    line = src.count("\n", 0, start + len(raw) - len(raw.lstrip())) + 1
    f = Func(fid, mod.file, f"{cls.name}.{name}", name, cls.name, "cs", line,
             params=[p for p, _ in params], param_types={p: t for p, t in params if t}, prop=is_prop,
             sig=",".join(_cs_type_text(t) for t in texts))
    f.abstract = "abstract" in mods or declared
    f.hollow = not f.abstract and not arrow and not src[b0:b1].strip()   # 空大括號：是覆寫，不值得當落點
    f.conditional = bool(_CS_CONDITIONAL.search(raw))
    f.entry = name == "Main" and "static" in mods
    if b1 > b0:
        _cs_body(mod, cls, f, src, depth, b0, b1, arrow)
    cls.methods.setdefault(name, []).append(fid)
    mod.funcs.append(f)


def _cs_param(text: str):
    """(參數名, 型別名)：保留陣列形狀（Worker[] 不是 Worker，陣列的成員解析還沒支援，元素型別不當證據）。"""
    words = [w for w in _strip_generics(text.split("=")[0]).split() if w not in ("this", "ref", "out", "in", "params")]
    return (words[-1], words[-2].rstrip("?").split(".")[-1]) if len(words) >= 2 else None


def _cs_type_text(param: str) -> str:
    """參數的完整型別寫法（含泛型、陣列、ref/out/params，去掉參數名與預設值）：List<int> 與 List<string> 分得開。"""
    words = param.split("=")[0].split()
    return re.sub(r"\s*([<>,\[\]])\s*", r"\1", " ".join(words[:-1]))


def _cs_field(cls: Cls, head: str) -> None:
    words = _strip_generics(head.split("=")[0]).split()
    if len(words) < 2:
        return
    cls.fields[words[-1]] = cls.declared_fields[words[-1]] = words[-2].rstrip("?").split(".")[-1]   # 陣列形狀保留（Worker[]）
    if "event" in words:
        cls.events.add(words[-1])


def _cs_body(mod: Module, cls: Cls, f: Func, src: str, depth: list, b0: int, b1: int, arrow: bool) -> None:
    body = src[b0:b1]
    spots = [(m.start(), c) for m in _CS_CALL.finditer(body) if (c := _cs_call(m, body, f.line))]
    _cs_scope_calls(body, spots)                    # 區域函式／lambda 裡的呼叫：模型外（參數與綁定沒建）
    f.calls = [c for _, c in spots]
    f.calls += [Call("opaque", "", line=f.line) for m in _CS_OPAQUE_CALL.finditer(body) if _cs_opaque_call(body, m)]
    f.calls += [Call("prop", m["name"], recv=re.sub(r"[\s?]", "", m["recv"]).rstrip("."), line=f.line)
                for m in _CS_PROP_USE.finditer(body)]
    ends = [j for j in range(b0, b1) if src[j] == ";" and (depth[j] == depth[b0] or f.prop)]   # 屬性的句子在 get/set 裡面一層
    stmts = [body.strip()] if arrow else [src[a + 1:e].strip() for a, e in zip([b0 - 1] + ends, ends)]
    moves = sum(1 for s in stmts if _CS_MOVE.fullmatch(s))
    noise = sum(1 for c in f.calls if c.noise)
    f.simple = len(stmts) - moves - noise <= 2 and not _CS_COMPOUND.search(body)
    for m in _CS_LOCAL.finditer(body):
        if m["new"] or m["type"]:
            f.local_types[m["var"]] = m["new"] or m["type"]
        if m["type"]:
            f.declared[m["var"]] = m["type"]
        if m["new"]:
            f.constructed[m["var"]] = m["new"]
    f.aliases = {m["var"]: ref for m in _CS_ALIAS.finditer(body) if (ref := _cs_ref(m["rhs"]))}
    f.inline = {m["name"] for m in _CS_INLINE.finditer(body) if not {m["type"], m["name"]} & CS_KEYWORDS}
    stores = Counter(_CS_STORE.findall(body))
    f.locals = {m["var"] for m in _CS_LOCAL.finditer(body)} | set(f.aliases)   # 有宣告的才是區域變數；裸名指定可能是欄位
    stores.update(f.params)
    stores.update({name: 2 for name in _CS_BYREF.findall(body)})   # 傳 ref／out 出去：呼叫後值可能被換掉
    stores.update({name: 2 for name in _CS_MODIFY.findall(body)})
    f.reassigned = {name for name, k in stores.items() if k > 1}
    for m in _CS_ASSIGN.finditer(body):
        if m["new"]:
            cls.fields.setdefault(m["lhs"], m["new"])
        elif m["rhs"] in f.params:
            cls.stored[m["lhs"]] = (f.id, m["rhs"])
        if m["rhs"] in f.locals and m["lhs"] not in f.locals:
            f.escaped.add(m["rhs"])                # 區域變數被存進欄位
    f.escaped |= set(_CS_CONTAINER_ADD.findall(body))   # list.Add(x) 這類加進容器
    for init in _CS_INITIALIZER.findall(body):            # new[] { w }、new List<W> { w }、new Holder { W = w }
        f.escaped |= set(_CS_LOWER_NAME.findall(init))
    f.receiver_only = _cs_receiver_only(f, body)
    for m in [*_CS_SUB.finditer(body), *_CS_LISTEN.finditer(body)]:
        ref = _cs_ref(m["rhs"])   # 訂閱的是具名方法才收；+= lambda 的內容就寫在這裡
        recv, _, key = m["lhs"].rpartition(".")
        if ref:
            mod.subs.append((key, ref, f.id, mod.file, recv))


def _cs_receiver_only(f: Func, body: str) -> set:
    """C# 版的白名單 2 正向證明（本體已去註解與字串）：區域變數 w 的每一次出現（前面不是 `.` 的 \\bw\\b），
    只能是一次宣告 `var w = new X(…)`／`X w = new X(…)`，其餘都是 `w.M(`／`w?.M(`；當引數、ref/out、再指定、
    放進初始化子、return、讀屬性……都失去資格。"""
    out = set()
    for name in f.constructed:
        builds = {m.start("var") for m in _CS_LOCAL.finditer(body) if m["var"] == name and m["new"]}
        spots = [m.start() for m in re.finditer(rf"(?<![\w.]){re.escape(name)}\b", body)]
        calls = [p for p in spots if p not in builds and _CS_RECV_CALL.match(body, p + len(name))]
        if len(builds) == 1 and builds <= set(spots) and len(builds) + len(calls) == len(spots):
            out.add(name)
    return out


def _cs_opaque_call(body: str, m: re.Match) -> bool:
    """`](`：下標結果上的呼叫（handlers[0]()）→ 是一次看不到對象的呼叫。`)(`：前面那組括號裡還有括號（Get()(x)、
    (a.B())(x)）才算呼叫結果上的呼叫；(int)(x)、(Foo)(x) 這種轉型不算（委派變數加括號再呼叫也會被略過，列在抓不到清單）。"""
    if m.group().startswith("]"):
        return True
    depth, i = 0, m.start()
    while i >= 0:
        depth += (body[i] == ")") - (body[i] == "(")
        if depth == 0:
            return "(" in body[i + 1:m.start()]
        i -= 1
    return False


def _cs_scope_calls(body: str, spots: list) -> None:
    """位在區域函式或 lambda 本體裡的呼叫標 scoped（模型沒建那一層的參數與綁定，一律不給條號）；裸名呼叫的名字正是
    那個構件自己的參數（void Wrap(Action Run) { Run(); }）→ 再標 shadowed：裝的東西看不到，不退回外層同名的方法。"""
    ranges = []
    for m in _CS_INLINE.finditer(body):           # 區域函式、指定給變數的 lambda
        head = m.group()
        inner = re.search(r"\(([^()]*)\)", head)
        params = {_cs_param_name(p) for p in _split_top(inner.group(1) if inner else "")} - {""}
        if "=>" in head and not inner:
            params = {head.split("=")[-1].split("=>")[0].strip()}
        ranges.append((m.end(), _cs_construct_end(body, m.end(), head.endswith("{")), params))
    covered = [r for r in ranges]
    for m in _CS_LAMBDA.finditer(body):          # 當引數的 lambda：(x) => …、x => …
        if any(a <= m.start() < b for a, b, _ in covered):
            continue
        raw = m["params"] if m["params"] is not None else m["one"]
        params = {_cs_param_name(p) for p in _split_top(raw)} - {""}
        j = m.end()
        while j < len(body) and body[j].isspace():
            j += 1
        braced = j < len(body) and body[j] == "{"
        ranges.append((m.end(), _cs_construct_end(body, j + 1 if braced else m.end(), braced), params))
    for pos, c in spots:
        for a, b, params in ranges:
            if a <= pos < b:
                c.scoped = True
                c.shadowed = c.shadowed or (c.kind == "name" and c.name in params)


def _cs_param_name(text: str) -> str:
    """參數文字的名字：型別＋名字取最後一字；只有一個字（lambda 沒寫型別）就是它。"""
    words = [w for w in text.replace("=", " ").split() if w not in ("ref", "out", "in", "params", "this")]
    return words[-1] if words and (words[-1][0].isalpha() or words[-1][0] == "_") else ""


def _cs_construct_end(body: str, start: int, braced: bool) -> int:
    """構件本體到哪裡：大括號本體到對應的 }；運算式本體到深度 0 的 ; 或 ,、或包住它的 ) ] } 為止。"""
    depth = 0
    for j in range(start, len(body)):
        ch = body[j]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:                         # 關掉的是包住本體的那一個括號：本體到這裡（內層 if {…} 關掉時 depth 回 0，不是結束）
                return j
            depth -= 1
        elif not braced and depth == 0 and ch in ";,":
            return j
    return len(body)


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
    parsed = [_cs_arg(idx, a) for idx, a in enumerate(_cs_arg_texts(body, m.end()))]
    c.refs = [(key, ref) for key, ref, _, _ in parsed if ref]
    c.blind = {key for key, _, blind, _ in parsed if blind}
    c.nargs = sum(1 for *_, named in parsed if not named)
    c.kwargs = {key for key, *_, named in parsed if named}
    return c


def _cs_arg(idx: int, text: str):
    """一個 C# 引數 → (位置或具名參數名, 函式參照或 None, 是否算出來的值, 是否具名)。
    方法群組（Work、this.Work、Util.Work）→ 參照；lambda、字面值、new、ref/out → 內容在這裡或不是函式；其他 → 算出來的值。"""
    named = _CS_NAMED_ARG.fullmatch(text) if "?" not in text else None
    key, value = (named[1], named[2].strip()) if named else (idx, text)
    m = _CS_REF.fullmatch(value)
    ref = _cs_ref(value) if m else None
    inline = "=>" in value or bool(_CS_INLINE_ARG.fullmatch(value))
    return key, ref, not ref and not inline, bool(named)


def _cs_call_kind(is_new: bool, name: str, recv: str, on_result: bool) -> Call:
    """C# 呼叫點的種類：new／X.Invoke()／接在運算結果上／本類別／base／經由別的東西。"""
    if is_new:
        return Call("new", name)
    if name == "Invoke" and recv:
        owner, _, target = recv.rpartition(".")
        return Call("invoke", target, recv=owner)
    if on_result:
        return Call("attr", name, recv="?")
    if recv in ("", "this"):
        return Call("self" if recv else "name", name)
    if recv == "base":
        return Call("super", name)
    return Call("attr", name, recv=recv, noise=_is_noise("attr", name, recv))


def _cs_arg_texts(body: str, i: int) -> list:
    """body[i] 是 ( 後一格：取到對應 ) 為止，切成一個個引數文字。"""
    depth = 0
    for j in range(i, len(body)):
        depth += (body[j] in "([{") - (body[j] in ")]}")
        if depth < 0:
            return _split_top(body[i:j])
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
