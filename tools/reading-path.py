#!/usr/bin/env python3
"""reading-path.py：量「人讀這段要跳幾個檔、經過幾層轉手、拐幾個彎」——從入口讀到功能落地的閱讀路徑。

做什麼：
  把專案的函式／方法畫成呼叫圖，從入口出發，替每個「落點」（有實質內容、不只是把呼叫往下傳的函式）
  找拐彎最少的那條路，列出經過的檔與函式、每一步是哪一種轉手、總跳檔數與拐彎數；也能比同一入口在兩個版本的差異。
  數字是尺不是判決：判斷交給讀的人與 LLM。

怎麼跑：
  python tools/reading-path.py [--root 專案根] [--entry 入口] [--to 落點] [--top N] [--json]
  python tools/reading-path.py --before <git rev|目錄> [--after <git rev|目錄>] [--entry 入口]
  完整參數見 --help。尾行：READING_PATH DONE k=v …（跑不動時 READING_PATH FAIL reason=…，exit 1）

每一步怎麼算（一步最多算一個彎）：
  轉手  這一步不是直接呼叫：wrapper／delegate（落到只轉傳的函式）、callback、event、inherit（繼承／介面分派）、dynamic（分派表）
  跳檔  換到別的檔；partial 類別各檔名是 `類.責任.cs` 且責任各不相同 → 標「分檔有責任軸」，不算跳檔、不算彎
  拐彎  這一步是轉手或跳檔。刻度（G11，參考）：0-1 順｜2 注意｜3 警戒｜≥4 臭掉
語言解析在同目錄 reading_path_lang.py（Python 用 ast；C# 不用 Roslyn；js/ts/go/java/kt/rs 粗略模式只數跳檔）。
"""
from __future__ import annotations

import argparse
import heapq
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reading_path_lang as lang  # noqa: E402

PARSERS = {".py": lang.parse_python, ".cs": lang.parse_csharp, **{e: lang.parse_coarse for e in lang.COARSE_EXT}}
SKIP_DIRS = {"node_modules", "__pycache__", "obj", "bin", "Library", "Temp", "Logs", "dist", "build",
             "venv", "site-packages", "_archive"}
TEST_DIRS = {"test", "tests", "verify", "__tests__", "spec", "specs"}
TEST_FILE_RE = re.compile(r"^(test_.*\.py|.*_test\.py|verify_.*\.py|conftest\.py|.*Tests?\.cs|.*\.(test|spec)\.[jt]sx?)$")
UNITY_ENTRY = {"Awake", "Start", "Update", "FixedUpdate", "LateUpdate", "OnEnable", "OnDisable", "OnDestroy"}
UNITY_BASES = {"MonoBehaviour", "NetworkBehaviour", "ScriptableObject", "StateMachineBehaviour"}
GRADES = ((4, "臭掉"), (3, "警戒"), (2, "注意"), (0, "順"))
# 接收者型別不明時不拿來猜的方法名：內建型別本來就有的（d.get、s.strip…）與 .NET 常見方法
PY_BUILTIN_TYPES = (dict, list, str, set, bytes, tuple, int, float, io.TextIOWrapper, Path, re.Pattern, re.Match)
PY_BUILTIN_METHODS = {n for t in PY_BUILTIN_TYPES for n in dir(t)}
CS_COMMON_METHODS = {"Add", "AddRange", "Remove", "RemoveAt", "Contains", "ContainsKey", "TryGetValue", "Clear",
                     "ToString", "Equals", "GetHashCode", "Dispose", "Insert", "IndexOf", "Any", "All", "Where",
                     "Select", "First", "FirstOrDefault", "Last", "ToList", "ToArray", "Format", "Join", "Split",
                     "Trim", "Replace", "StartsWith", "EndsWith", "Substring", "Parse", "TryParse", "Sort", "Reverse",
                     "Push", "Pop", "Enqueue", "Dequeue", "Peek", "Append", "AppendLine", "GetComponent",
                     "SetActive", "Find", "Wait", "CompareTo", "CopyTo", "GetType", "Max", "Min", "Sum", "Count"}
MAX_REEXPORT = 5          # from a import x 追 re-export 最多幾跳（防循環）
# partial 檔名後綴看不出責任的（Part1、2、More、Misc…）不算責任軸
NON_AXIS_SUFFIX = re.compile(r"(?i)^(part|partial|file|section|piece|split)?\d+$|^(more|extra|misc|other|others|rest|temp|tmp|new|old|copy)$")
COVERAGE_DROP = 0.05      # 前後比較時 after 的「對不到」比例多出這麼多 → 警示可能是解析退化
SHARED_FAN_IN = 5         # 落點被這麼多處呼叫 → 標「共用底層」：讀功能時通常不必沿這條路讀到它
ROOT_LIMIT = 10           # 沒有天生入口時，最多拿幾個「沒人呼叫的公開函式」當入口
ENTRY_LIST_LIMIT = 20     # 表頭列幾個入口（--json 看全部）
AMBIGUOUS_WARN = 0.3      # 對不到唯一目標的呼叫超過這個比例 → 表頭警示數字偏低
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

LIMITS = """抓不到／可能偏差（數字是尺，判斷交給人）：
  - 每個落點只取拐彎最少的一條路（G11「重找最短路」的口徑）；同一落點更繞的路不列
  - 名字對不到唯一目標（同名方法多個、接收者型別不明）不連線，只計 ambiguous → 路徑可能沒畫到、數字偏低
  - 外部函式庫、框架回呼（Unity 生命週期以外）、反射、eval、動態 import 看不到；getattr 只認分派表來的
  - callback 與事件不分呼叫語境：多處各傳不同函式、同名事件多處訂閱 → 全連並標「候選」，可能出現實際走不到的捷徑
  - callback 只追一層：函式被當參數再往下轉傳一次就斷
  - 「只轉傳」靠句數判定（換區域變數名不算句）：塞進無關計算就會被當成有內容
  - Python：裝飾器包裝、@property、模組頂層（__main__ 以外）程式碼、monkeypatch 不追
  - C#（不用 Roslyn）：多載同名全連、擴充方法、LINQ、var 由方法回傳推型別、跨 namespace 同名類合併、
    lambda 裡的呼叫算外層函式、#if 不分支、運算子多載與索引子不認、接收者型別不明的屬性不猜、
    三元運算與 LINQ 不算分支（一行 ?: 的方法可能被當成只轉傳）、插值字串 {} 裡再套字串會漏
  - partial 責任軸是依檔名推測：檔名沒寫成 `類.責任.cs` → 照算跳檔，有責任軸但沒標在檔名上的分檔數字會偏高；
    反過來，取了像樣後綴但其實沒分責任的也會被當成有軸（Part1、Misc 這類已排除）——輸出都標「依檔名推測」
  - 分層架構（main→service→repo 各一檔）每層換檔都算彎 → 可能誤報，由讀的人判
  - 落點被很多處呼叫（≥5）會標「共用底層」：讀某個功能時通常不必沿這條路讀到它，路長不一定是問題
  - 粗略模式（js/ts/go/java/kt/rs）只認定義與同名唯一呼叫：只數跳檔，不判轉手"""


class ReadingPathError(Exception):
    """跑不動（路徑不存在、git rev 解不出）；訊息要附使用者能做什麼。"""


@dataclass
class Edge:
    dst: str
    kind: str            # direct｜callback｜event｜inherit｜dynamic
    guess: str = ""      # 這條邊不確定的原因（猜的／候選）；空字串＝確定
    via: str = ""        # object：經由別的物件轉交（落點若只轉傳 → delegate）


@dataclass
class Step:
    func: str
    kind: str            # entry｜direct｜wrapper｜delegate｜callback｜event｜inherit｜dynamic
    jump: bool = False
    axis: str = ""       # 分檔有責任軸時的「責任→責任」
    guess: str = ""

    @property
    def turn(self) -> int:
        return int(self.kind != "direct" or self.jump)


@dataclass
class Route:
    entry: str
    landing: str
    steps: list = field(default_factory=list)
    open_end: bool = False   # 落點只轉傳、但下一站對不到：可能還沒讀到底
    fan_in: int = 0          # 落點被幾個函式呼叫

    def summary(self) -> dict:
        moves = self.steps[1:]
        turns = sum(s.turn for s in moves)
        return {"entry": self.entry, "landing": self.landing, "turns": turns, "grade": grade(turns),
                "file_jumps": sum(s.jump for s in moves), "axis_jumps": sum(bool(s.axis) for s in moves),
                "handoffs": sum(s.kind != "direct" for s in moves), "depth": len(moves),
                "open_end": self.open_end, "fan_in": self.fan_in, "steps": [asdict(s) for s in self.steps]}


def grade(turns: int) -> str:
    return next(label for floor, label in GRADES if turns >= floor)


def is_test(rel: str) -> bool:
    """用相對專案根的路徑判斷（絕對路徑會比到專案外的上層目錄名）。"""
    parts = rel.split("/")
    return bool(TEST_DIRS & set(parts[:-1])) or bool(TEST_FILE_RE.match(parts[-1]))


# ─── 偵測器：每一種轉手各一個（反證測試會一次拿掉一個） ─────────────────────


def override_targets(g: "Graph", cls: lang.Cls, name: str) -> list:
    """cls 的子孫類別裡覆寫 name 的方法：繼承／介面分派真正會跑到的地方。"""
    return [fid for sub in g.descendants(cls) for fid in sub.methods.get(name, []) if not g.funcs[fid].abstract]


def callback_targets(g: "Graph", bind_fid: str, param: str) -> list:
    """bind_fid 的參數 param 被當函式呼叫：找所有呼叫 bind_fid 的地方，那個位置傳進來的是哪個函式。"""
    f = g.funcs[bind_fid]
    offset = 1 if f.lang == "py" and f.cls and f.params[:1] in (["self"], ["cls"]) else 0
    pos = f.params.index(param) - offset
    out = []
    for caller, call in g.callers.get(bind_fid, []):
        refs = [ref for key, ref in call.refs if key in (pos, param)]
        for ref in refs:
            out.extend(e.dst for e in g.resolve(caller, ref, defer=False))
    return out


def event_targets(g: "Graph", key: str) -> list:
    """訂閱了事件鍵 key 的處理函式（on/subscribe/connect、C# 的 += 與 AddListener）。"""
    out = []
    for sub_key, ref, owner, file in g.subs:
        if sub_key == key:
            out.extend(e.dst for e in g.resolve(g.funcs.get(owner) or g.module_ctx(file), ref, defer=False))
    return out


def partial_axis(cls: lang.Cls) -> dict:
    """partial 類別的檔名是 `類.責任.cs`（可再加一個不帶後綴的主檔）、責任各不相同且看得出意思 → {檔: 責任}；
    否則 {}，照算跳檔。這是依檔名推測，輸出會標明；Part1、Misc 之類的後綴不算責任。"""
    if not cls.partial or len(cls.files) < 2:
        return {}
    axis = {}
    for file in cls.files:
        stem = PurePosixPath(file).name[:-3]
        suffix = stem[len(cls.name) + 1:] if stem.startswith(cls.name + ".") else ""
        if stem != cls.name and (not suffix or NON_AXIS_SUFFIX.match(suffix)):
            return {}
        axis[file] = suffix or "主檔"
    return axis if len(set(axis.values())) == len(axis) else {}


# ─── 呼叫圖 ──────────────────────────────────────────────────────────────────


class Graph:
    """全專案的函式與呼叫邊；建好後可從任一入口找各落點的最短閱讀路徑。"""

    def __init__(self, root: Path, modules: list, parse_errors: list):
        self.root = root
        self.modules = {m.file: m for m in modules}
        self.parse_errors = parse_errors
        self.funcs = {f.id: f for m in modules for f in m.funcs}
        self.subs = [s for m in modules for s in m.subs]
        self.classes = defaultdict(list)
        self.children = defaultdict(list)
        self.mod_index = defaultdict(list)
        self.coarse = defaultdict(list)
        self.edges = defaultdict(list)
        self.callers = defaultdict(list)
        self.pending = []          # (src, 綁定的 func id, 參數名)：callback 要等所有呼叫者都連好才解
        self.hits = Counter()      # 每個函式有幾個呼叫連到專案內
        self.amb = Counter()       # 每個函式有幾個呼叫對不到唯一目標
        self._index(modules)
        self._resolve_all()
        self.fan_in = Counter()
        for es in self.edges.values():
            self.fan_in.update({e.dst for e in es})
        self.called = set(self.fan_in)
        self.axis = {c.name: partial_axis(c) for cs in self.classes.values() for c in cs if c.lang == "cs"}
        self.passthrough = {f.id: self._forward_style(f) for f in self.funcs.values() if self._is_passthrough(f)}

    def _index(self, modules: list) -> None:
        for m in modules:
            for c in m.classes:
                self._add_class(c)
        for f in [f for f in self.funcs.values() if f.lang == "coarse"]:
            self.coarse[f.name].append(f.id)
        for m in [m for m in modules if m.lang == "py"]:
            parts = m.file[:-3].split("/")
            parts = parts[:-1] if parts[-1] == "__init__" else parts
            for i in range(len(parts)):
                self.mod_index[".".join(parts[i:])].append(m.file)
        self.by_method = defaultdict(list)
        for c in [c for cs in self.classes.values() for c in cs]:
            for base in c.bases:
                self.children[base].append(c)
            for name, ids in c.methods.items():
                self.by_method[name].extend(ids)

    def _add_class(self, c: lang.Cls) -> None:
        """C# partial（同名類）併成一個；Python 同名類各自保留，查找時優先同檔。"""
        same = next((x for x in self.classes[c.name] if x.lang == "cs" == c.lang), None)
        if same is None:
            self.classes[c.name].append(c)
            return
        same.files += [f for f in c.files if f not in same.files]
        same.bases += [b for b in c.bases if b not in same.bases]
        same.partial = same.partial or c.partial
        same.fields.update(c.fields)
        same.stored.update(c.stored)
        same.events |= c.events
        for name, ids in c.methods.items():
            same.methods.setdefault(name, []).extend(ids)

    # 查找 ───────────────────────────────────────────────

    def cls_named(self, name: str, from_file: str = ""):
        cands = self.classes.get(name, [])
        return next((c for c in cands if from_file in c.files), cands[0] if cands else None)

    def cls_of(self, f: lang.Func):
        return self.cls_named(f.cls, f.file) if f.cls else None

    def ancestry(self, cls):
        """cls 自己與所有祖先（廣度優先，同一類只走一次）。"""
        seen, queue = set(), [cls]
        while queue:
            c = queue.pop(0)
            if c is None or id(c) in seen:
                continue
            seen.add(id(c))
            yield c
            queue.extend(self.cls_named(b, c.files[0]) for b in c.bases)

    def descendants(self, cls):
        seen, queue, out = {id(cls)}, list(self.children.get(cls.name, [])), []
        while queue:
            c = queue.pop(0)
            if id(c) in seen:
                continue
            seen.add(id(c))
            out.append(c)
            queue.extend(self.children.get(c.name, []))
        return out

    def lookup(self, cls, name: str) -> list:
        """沿繼承鏈往上，第一個定義 name 的類別裡的那些方法。"""
        return next((c.methods[name] for c in self.ancestry(cls) if name in c.methods), [])

    def field_type(self, cls, attr: str):
        owner = next((c for c in self.ancestry(cls) if attr in c.fields), None)
        return self.cls_named(owner.fields[attr], owner.files[0]) if owner else None

    def stored_param(self, cls, attr: str):
        return next((c.stored[attr] for c in self.ancestry(cls) if attr in c.stored), None)

    def find_module(self, name: str, level: int, from_file: str):
        """Python import 名 → 專案內的檔；相對 import 照層級，絕對 import 比模組名尾段（同目錄優先，多個同名就不連）。"""
        if level:
            parents = PurePosixPath(from_file).parents
            if level > len(parents):
                return None
            base = parents[level - 1] / name.replace(".", "/") if name else parents[level - 1]
            cands = [base / "__init__.py"] if not name else [PurePosixPath(f"{base}.py"), base / "__init__.py"]
            hits = [p.as_posix() for p in cands if p.as_posix() in self.modules]
            return hits[0] if hits else None
        cands = self.mod_index.get(name, [])
        here = PurePosixPath(from_file).parent
        pick = [c for c in cands if PurePosixPath(c).parent == here] or cands
        return pick[0] if len(pick) == 1 else None

    def scopes(self, f: lang.Func) -> list:
        """f 所在的函式作用域，由外到內（Cls.method.inner → Cls.method、Cls.method.inner；類別本身不算作用域）。"""
        parts = f.qual.split(".")
        return [".".join(parts[:i]) for i in range(2 if f.cls else 1, len(parts) + 1)]

    def imports_of(self, f: lang.Func) -> dict:
        """f 看得到的 import：模組層＋外層函式＋自己的（內層蓋外層）。"""
        merged = dict(self.modules[f.file].imports) if f.file in self.modules else {}
        for scope in self.scopes(f):
            owner = self.funcs.get(f"{f.file}::{scope}")
            merged.update(owner.imports if owner else {})
        return merged

    def module_alias(self, f: lang.Func, dotted: str):
        """f 裡寫成 dotted 的接收者（w2、pkg.w2、a.b）是不是專案內的模組 → 模組檔或 None。"""
        imports = self.imports_of(f)
        key = dotted if dotted in imports else dotted.partition(".")[0]
        if key not in imports:
            return None
        modname, level, orig = imports[key]
        full = ".".join(p for p in (modname, orig, dotted[len(key) + 1:]) if p)
        return self.find_module(full, level, f.file)

    def module_ctx(self, file: str) -> lang.Func:
        """模組層（函式外）的訂閱與分派表，用一個假函式當解析的語境。"""
        lang_name = self.modules[file].lang if file in self.modules else "py"
        return lang.Func(f"{file}::<module>", file, "<module>", "<module>", "", lang_name, 0)

    # 解析：一個呼叫點連到哪些函式 ─────────────────────────

    def resolve(self, f: lang.Func, c: lang.Call, defer: bool = True) -> list:
        handler = {"name": self._r_name, "self": self._r_self, "super": self._r_super, "attr": self._r_attr,
                   "new": self._r_new, "emit": self._r_emit, "invoke": self._r_invoke, "table": self._r_table,
                   "getattr": self._r_getattr, "prop": self._r_prop}
        return handler[c.kind](f, c, defer)

    def dispatch(self, cls, name: str, via: str = "") -> list:
        """在 cls 上呼叫 name：子類有覆寫（或本身抽象）→ inherit 連到所有實作；否則 direct。"""
        owner_ids = self.lookup(cls, name)
        if not owner_ids:
            return []
        over = override_targets(self, cls, name)
        if not over:
            return [Edge(i, "direct", via=via) for i in owner_ids]
        concrete = [i for i in owner_ids if not self.funcs[i].abstract]
        return [Edge(i, "inherit", via=via) for i in dict.fromkeys(concrete + over)]

    def _defer(self, src: lang.Func, bind: tuple, defer: bool) -> list:
        if defer:
            self.pending.append((src.id, *bind))
        return []

    def _r_name(self, f, c, defer):
        if c.name in f.params:
            return self._defer(f, (f.id, c.name), defer)
        if c.name in f.table_vars:
            return self._r_table(f, lang.Call("table", f.table_vars[c.name]), defer)
        nested = next((n for s in reversed(self.scopes(f)) if (n := f"{f.file}::{s}.{c.name}") in self.funcs), None)
        if nested:
            return [Edge(nested, "direct")]       # 自己或外層函式裡定義的巢狀函式
        if f.lang == "coarse":
            return self._coarse(f, c.name)
        if f.lang == "py":
            return self._py_name(f.file, c.name, imports=self.imports_of(f))
        return self._r_self(f, c, defer)          # C#：裸名就是本類別的方法／事件／委派欄位

    def _r_self(self, f, c, defer):
        cls = self.cls_of(f)
        if cls is None:
            return []
        hits = self.dispatch(cls, c.name)
        if hits:
            return hits
        stored = self.stored_param(cls, c.name)
        if stored:
            return self._defer(f, stored, defer)
        return self._r_emit(f, c, defer) if any(c.name in x.events for x in self.ancestry(cls)) else []

    def _r_super(self, f, c, defer):
        """super()／base.：直接連父類的實作，不展開子類覆寫（那正是呼叫者自己）。"""
        cls = self.cls_of(f)
        bases = [self.cls_named(b, f.file) for b in (cls.bases if cls else [])]
        ids = next((hits for b in bases if b and (hits := self.lookup(b, c.name))), [])
        return [Edge(i, "direct") for i in ids]

    def _r_attr(self, f, c, defer):
        kind, target = self.recv_type(f, c.recv)
        if kind == "module":
            return self._py_name(target, c.name)
        if kind == "external":
            return []
        if target is not None:
            return self.dispatch(target, c.name, via="object" if kind == "object" else "")
        return self._guess(f, c.name)

    def _r_new(self, f, c, defer):
        cls = self.cls_named(c.name, f.file)
        return self._ctor(cls) if cls else []

    def _r_emit(self, f, c, defer):
        """事件只按名字配對（看不出是哪個實例發的）：同名事件有多個處理函式就標成候選。"""
        targets = list(dict.fromkeys(event_targets(self, c.name)))
        reason = f"候選：事件 {c.name} 有 {len(targets)} 個處理函式，只按名字配對" if len(targets) > 1 else ""
        return [Edge(t, "event", guess=reason) for t in targets]

    def _r_prop(self, f, c, defer):
        """C# 讀寫屬性：只連到有 get/set 本體的屬性；接收者型別不明就不猜（屬性名太常見）。"""
        target = self.recv_type(f, c.recv)[1] if c.recv and c.recv != "this" else self.cls_of(f)
        edges = self.dispatch(target, c.name) if target else []
        return [e for e in edges if self.funcs[e.dst].prop]

    def _r_invoke(self, f, c, defer):
        """C# 的 X.Invoke()／X?.Invoke()：X 是參數或建構時存下的委派 → callback；否則當事件。"""
        if c.name in f.params:
            return self._defer(f, (f.id, c.name), defer)
        stored = self.stored_param(self.cls_of(f), c.name) if f.cls else None
        return self._defer(f, stored, defer) if stored else self._r_emit(f, c, defer)

    def _r_table(self, f, c, defer):
        """分派表：函式內的表在函式語境解（self._r_x 要認得出類別），模組層的表在模組語境解。"""
        if c.name in f.tables:
            return self._dynamic(f, f.tables[c.name])
        return self._table(f.file, c.name)

    def _r_getattr(self, f, c, defer):
        """getattr(module, spec[1])(…)：用到的變數來自分派表 → 連到表裡全部；否則看不到目標，記 ambiguous。"""
        tables = [f.table_vars[n] for n in c.name.split(",") if n in f.table_vars]
        if tables:
            return self._r_table(f, lang.Call("table", tables[0]), defer)
        self.amb[f.id] += 1
        return []

    def _ctor(self, cls) -> list:
        return [Edge(i, "direct") for i in self.lookup(cls, "__init__" if cls.lang == "py" else cls.name)]

    def _imported_from(self, file: str, imports: dict, name: str):
        """from X import name → (X 在專案內的檔, 原名)；不是 from 匯入或 X 不在專案內 → (None, "")。"""
        modname, level, orig = imports.get(name, ("", 0, ""))
        src = self.find_module(modname, level, file) if orig else None
        return (src, orig) if src and src != file else (None, "")

    def _py_name(self, file: str, name: str, hops: int = 0, imports: dict | None = None) -> list:
        """Python 模組 file 裡的 name：本檔函式、本檔類別（建構）、from 匯入的函式或類別（追 re-export）。
        imports 給的是呼叫所在函式看得到的 import；沒給就用模組層的。"""
        mod = self.modules.get(file)
        if mod is None or hops > MAX_REEXPORT:
            return []
        if name in mod.defs:
            return [Edge(mod.defs[name], "direct")]
        local_cls = next((c for c in self.classes.get(name, []) if file in c.files), None)
        if local_cls:
            return self._ctor(local_cls)
        src, orig = self._imported_from(file, mod.imports if imports is None else imports, name)
        return self._py_name(src, orig, hops + 1) if src else []

    def _table(self, file: str, name: str, hops: int = 0) -> list:
        mod = self.modules.get(file)
        if mod is None or hops > MAX_REEXPORT:
            return []
        if name not in mod.tables:
            src, orig = self._imported_from(file, mod.imports, name)
            return self._table(src, orig, hops + 1) if src else []
        return self._dynamic(self.module_ctx(file), mod.tables[name])

    def _dynamic(self, ctx: lang.Func, refs: list) -> list:
        edges = []
        for ref in refs:
            edges += [Edge(e.dst, "dynamic") for e in self.resolve(ctx, ref, defer=False)]
        return edges

    def _coarse(self, f, name: str) -> list:
        cands = self.coarse.get(name, [])
        pick = [i for i in cands if self.funcs[i].file == f.file] or cands
        if len(pick) > 1:
            self.amb[f.id] += 1
        return [Edge(pick[0], "direct")] if len(pick) == 1 else []

    def _guess(self, f, name: str) -> list:
        """接收者型別不明：全專案只有一個同名方法才連（標為猜的），多個就記 ambiguous 不亂連。
        內建型別本來就有的方法名（d.get、s.strip、list.Add…）不猜，視為外部呼叫；非測試碼不猜進測試檔。"""
        common = PY_BUILTIN_METHODS if f.lang == "py" else CS_COMMON_METHODS
        cands = [] if name in common else self.by_method.get(name, [])
        cands = cands if is_test(f.file) else [i for i in cands if not is_test(self.funcs[i].file)]
        if len(cands) > 1:
            self.amb[f.id] += 1
        return [Edge(cands[0], "direct", guess="猜的：接收者型別不明，全專案只有這個同名方法", via="object")] if len(cands) == 1 else []

    def recv_type(self, f: lang.Func, recv: str):
        """接收者是什麼 → (種類, 對象)：module＋檔｜object＋類別（物件）｜static＋類別｜external｜("", None) 不明。"""
        if recv.startswith("new:"):
            return "object", self.cls_named(recv[4:], f.file)
        if recv.startswith("mod:"):
            target = self.find_module(recv[4:], 0, f.file)
            return ("module", target) if target else ("external", None)
        whole = self.module_alias(f, recv) if f.lang == "py" and recv else None
        if whole:
            return "module", whole
        head, *rest = recv.split(".")
        kind, cls = self._recv_head(f, head)
        for seg in rest:
            cls = self.field_type(cls, seg) if cls else None
        return (kind, cls) if cls or kind == "external" else ("", None)

    def _recv_head(self, f: lang.Func, head: str):
        if head in ("self", "this"):
            return "object", self.cls_of(f)
        typed = f.local_types.get(head) or f.param_types.get(head)
        if typed:
            return "object", self.cls_named(typed, f.file)
        own = self.cls_of(f)
        if f.lang == "cs" and own and self.field_type(own, head):
            return "object", self.field_type(own, head)
        if self.cls_named(head, f.file):
            return "static", self.cls_named(head, f.file)
        imp = self.imports_of(f).get(head) if f.lang == "py" else None
        if imp and not self.find_module(imp[0], imp[1], f.file):
            return "external", None               # 匯入的外部模組或其成員（json、os.path…）
        return "", None

    # 建邊 ───────────────────────────────────────────────

    def _resolve_all(self) -> None:
        for f in list(self.funcs.values()):
            for c in [c for c in f.calls if not c.noise]:
                waiting = len(self.pending)
                edges = self.resolve(f, c)
                self._add_edges(f.id, edges, c)
                self.hits[f.id] += bool(edges) or len(self.pending) > waiting
        for src, bind, param in self.pending:
            targets = list(dict.fromkeys(callback_targets(self, bind, param)))
            reason = f"候選：{len(targets)} 處呼叫各傳不同函式進 {param}，分不出這次是哪個" if len(targets) > 1 else ""
            self._add_edges(src, [Edge(t, "callback", guess=reason) for t in targets], None)

    def _add_edges(self, src: str, edges: list, c) -> None:
        """加邊（同終點同種類只留一條）；直接／繼承呼叫每個呼叫點都記下呼叫者（就算邊重複），callback 要回頭查誰傳了什麼。"""
        for e in edges:
            if c is not None and e.kind in ("direct", "inherit"):
                self.callers[e.dst].append((self.funcs[src], c))
            if not any(x.dst == e.dst and x.kind == e.kind for x in self.edges[src]):
                self.edges[src].append(e)

    def _is_passthrough(self, f: lang.Func) -> bool:
        """只把呼叫往下傳：≤2 句、無分支迴圈、恰好一個呼叫連到專案內。"""
        return f.simple and not f.entry and not f.abstract and f.lang != "coarse" and self.hits[f.id] == 1

    def _forward_style(self, f: lang.Func) -> str:
        return "delegate" if any(e.via == "object" for e in self.edges[f.id]) else "wrapper"

    def is_entry(self, f: lang.Func) -> bool:
        if f.entry:
            return True
        cls = self.cls_of(f) if f.lang == "cs" and f.name in UNITY_ENTRY else None
        return bool(cls) and any(c.name in UNITY_BASES or UNITY_BASES & set(c.bases) for c in self.ancestry(cls))

    # 找路 ───────────────────────────────────────────────

    def step(self, a: lang.Func, e: Edge) -> Step:
        b = self.funcs[e.dst]
        kind = e.kind if e.kind != "direct" else self.passthrough.get(b.id, "direct")
        axis_map = self.axis.get(a.cls, {}) if a.cls and a.cls == b.cls else {}
        axis = f"{axis_map[a.file]}→{axis_map[b.file]}" if a.file != b.file and a.file in axis_map and b.file in axis_map else ""
        return Step(b.id, kind, jump=a.file != b.file and not axis, axis=axis, guess=e.guess)

    def routes(self, entry: str) -> list:
        """從 entry 到每個落點、拐彎最少的那條路（平手比跳檔、再比深度）。"""
        best, back = {entry: (0, 0, 0)}, {}
        heap = [((0, 0, 0), entry)]
        while heap:
            cost, u = heapq.heappop(heap)
            if cost > best[u]:
                continue
            for e in self.edges.get(u, []):
                s = self.step(self.funcs[u], e)
                nxt = (cost[0] + s.turn, cost[1] + s.jump, cost[2] + 1)
                if nxt < best.get(e.dst, (float("inf"),)):
                    best[e.dst], back[e.dst] = nxt, (u, s)
                    heapq.heappush(heap, (nxt, e.dst))
        landings = [v for v in best if v != entry and v not in self.passthrough and not self.funcs[v].abstract]
        return [self._route(back, entry, v) for v in landings]

    def _route(self, back: dict, entry: str, landing: str) -> Route:
        steps, node = [], landing
        while node != entry:
            node, s = back[node]
            steps.append(s)
        f = self.funcs[landing]
        open_end = f.simple and self.hits[landing] == 0 and self.amb[landing] > 0
        return Route(entry, landing, [Step(entry, "entry")] + steps[::-1], open_end, self.fan_in[landing])


# ─── 掃描、入口、分析 ────────────────────────────────────────────────────────


def build_graph(root: Path) -> Graph:
    paths, modules, errors = [], [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        paths += [Path(dirpath) / name for name in sorted(filenames) if Path(name).suffix.lower() in PARSERS]
    for path in paths:
        rel = path.relative_to(root).as_posix()
        if lang.GENERATED_RE.search(rel):
            continue
        try:
            modules.append(PARSERS[path.suffix.lower()](rel, path.read_text(encoding="utf-8-sig", errors="replace")))
        except (SyntaxError, ValueError, RecursionError) as e:
            errors.append(f"{rel}（{type(e).__name__}）")
    return Graph(root, modules, errors)


def spec_hits(g: Graph, spec: str):
    """入口／落點寫法：檔路徑｜檔::限定名｜限定名或函式名（Class.method、main）→ (符合的函式, 是否只給了檔)。"""
    text = spec.replace("\\", "/")
    file_part, sep, qual = text.partition("::")
    if not sep:
        is_file = "/" in text or Path(text).suffix.lower() in PARSERS
        file_part, qual = (text, "") if is_file else ("", text)
    if file_part and Path(file_part).is_absolute():
        try:
            file_part = Path(file_part).resolve().relative_to(g.root.resolve()).as_posix()
        except ValueError:
            raise ReadingPathError(f"{file_part} 不在 --root {g.root} 底下") from None
    file_part = file_part.removeprefix("./")
    hits = [f for f in g.funcs.values()
            if (not file_part or f.file == file_part or f.file.endswith("/" + file_part))
            and (not qual or f.qual == qual or f.qual.endswith("." + qual) or f.name == qual)]
    return hits, not qual


def match_spec(g: Graph, spec: str) -> list:
    """入口：寫了函式就是那些函式；只給檔 → 檔裡的天生入口，沒有就用檔裡沒人呼叫的函式。"""
    hits, file_only = spec_hits(g, spec)
    if not file_only:
        return sorted(f.id for f in hits)
    entries = sorted(f.id for f in hits if g.is_entry(f))
    return entries or sorted(f.id for f in hits if f.id not in g.called)[:ROOT_LIMIT]


def find_entries(g: Graph, spec: str | None) -> list:
    """沒指定入口：天生入口（__main__、main、static Main、Unity 生命週期）；都沒有就用沒人呼叫的公開函式。測試檔不當入口。"""
    if spec:
        return match_spec(g, spec)
    mains = sorted(f.id for f in g.funcs.values() if g.is_entry(f) and not is_test(f.file))
    if mains:
        return mains
    roots = [f for f in g.funcs.values()
             if f.id not in g.called and not f.name.startswith("_") and not f.abstract and not is_test(f.file)]
    roots.sort(key=lambda f: (-len(g.edges.get(f.id, [])), f.id))
    return [f.id for f in roots[:ROOT_LIMIT]]


def analyze(root: Path, entry: str | None = None, to: str | None = None) -> dict:
    g = build_graph(root)
    targets = {f.id for f in spec_hits(g, to)[0]} if to else None
    report = {"root": str(root), "stats": graph_stats(g), "entries": []}
    for eid in find_entries(g, entry):
        routes = [r.summary() for r in g.routes(eid) if targets is None or r.landing in targets]
        routes.sort(key=lambda r: (-r["turns"], -r["file_jumps"], -r["handoffs"], -r["depth"], r["landing"]))
        grades = Counter(r["grade"] for r in routes)
        report["entries"].append({
            "entry": eid, "landings": len(routes),
            "max_turns": max((r["turns"] for r in routes), default=0),
            "max_file_jumps": max((r["file_jumps"] for r in routes), default=0),
            "max_handoffs": max((r["handoffs"] for r in routes), default=0),
            "grades": {label: grades.get(label, 0) for _, label in GRADES},
            "routes": routes})
    report["entries"].sort(key=lambda e: (-e["max_turns"], -e["max_file_jumps"], e["entry"]))
    return report


def graph_stats(g: Graph) -> dict:
    files = Counter(m.lang for m in g.modules.values())
    linked = sum(g.hits.values())
    ambiguous = sum(g.amb.values())
    axis = {name: sorted(a.values()) for name, a in g.axis.items() if a}
    return {"files": {"py": files["py"], "cs": files["cs"], "coarse": files["coarse"]}, "funcs": len(g.funcs),
            "linked_calls": linked, "ambiguous": ambiguous, "parse_errors": g.parse_errors, "axis_classes": axis,
            "ambiguous_ratio": round(ambiguous / (linked + ambiguous), 3) if linked + ambiguous else 0.0}


# ─── 前後比較 ────────────────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, creationflags=_NO_WINDOW)
    if proc.returncode != 0:
        msg = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise ReadingPathError(f"git {args[0]} 失敗：{msg[-1] if msg else proc.returncode}；"
                               "--before/--after 要給目錄，或 --root 所在 repo 的 commit")
    return proc.stdout


def materialize(spec: str, root: Path, tmp: Path, label: str) -> Path:
    """目錄就直接用；否則當 git rev，用 git archive 把 --root 這一層解到暫存夾（只取解析得了的檔）。"""
    if Path(spec).is_dir():
        return Path(spec).resolve()
    prefix = _git(root, "rev-parse", "--show-prefix").decode().strip()
    data = _git(root, "archive", "--format=tar", f"{spec}:{prefix}" if prefix else spec)
    dest = tmp / label
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        members = [m for m in tar.getmembers() if m.isfile() and Path(m.name).suffix.lower() in PARSERS
                   and not m.name.startswith("/") and ".." not in PurePosixPath(m.name).parts]
        for m in members:
            out = dest.joinpath(*PurePosixPath(m.name).parts)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(tar.extractfile(m).read())
    return dest


def compare(before: dict, after: dict) -> dict:
    """同一入口、同一落點（檔::函式）比拐彎、跳檔、轉手：better｜worse｜same｜new｜gone。"""
    b_entries = {e["entry"]: e for e in before["entries"]}
    a_entries = {e["entry"]: e for e in after["entries"]}
    rows = []
    for eid in sorted(set(b_entries) | set(a_entries)):
        b = {r["landing"]: r for r in b_entries.get(eid, {}).get("routes", [])}
        a = {r["landing"]: r for r in a_entries.get(eid, {}).get("routes", [])}
        rows += [_diff_row(eid, key, b.get(key), a.get(key)) for key in sorted(set(b) | set(a))]
    order = {"worse": 0, "new": 1, "gone": 2, "better": 3, "same": 4}
    rows.sort(key=lambda r: (order[r["status"]], r["entry"], r["landing"]))
    counts = Counter(r["status"] for r in rows)
    sb, sa = before["stats"], after["stats"]
    coverage_drop = (len(sa["parse_errors"]) > len(sb["parse_errors"])
                     or sa["ambiguous_ratio"] > sb["ambiguous_ratio"] + COVERAGE_DROP)
    return {"entries": len(set(b_entries) | set(a_entries)), "rows": rows,
            "counts": {k: counts.get(k, 0) for k in order},
            "max_turns_before": max((e["max_turns"] for e in before["entries"]), default=0),
            "max_turns_after": max((e["max_turns"] for e in after["entries"]), default=0),
            "stats_before": sb, "stats_after": sa, "coverage_drop": coverage_drop}


def _diff_row(entry: str, landing: str, b: dict | None, a: dict | None) -> dict:
    key = ("turns", "file_jumps", "handoffs")
    if b is None or a is None:
        status = "new" if b is None else "gone"
    else:
        vb, va = tuple(b[k] for k in key), tuple(a[k] for k in key)
        status = "same" if va == vb else ("better" if va < vb else "worse")
    return {"entry": entry, "landing": landing, "status": status, "before": b, "after": a}


def run_compare(root: Path, before: str, after: str | None, entry: str | None, to: str | None) -> dict:
    with tempfile.TemporaryDirectory(prefix="reading-path-") as tmp:
        b_root = materialize(before, root, Path(tmp), "before")
        a_root = materialize(after, root, Path(tmp), "after") if after else root
        b_rep, a_rep = analyze(b_root, entry, to), analyze(a_root, entry, to)
    res = compare(b_rep, a_rep)
    res.update(before_label=before, after_label=after or "目前內容", root=str(root))
    return res


# ─── 輸出 ────────────────────────────────────────────────────────────────────

STATUS_LABEL = {"worse": "變差", "new": "新增", "gone": "消失", "better": "變好", "same": "不變"}


def route_lines(r: dict) -> list:
    shared = f"（共用底層：{r['fan_in']} 處呼叫）" if r["fan_in"] >= SHARED_FAN_IN else ""
    lines = [f"  [{r['grade']}] 拐彎 {r['turns']}｜跳檔 {r['file_jumps']}｜轉手 {r['handoffs']}｜深度 {r['depth']}"
             f"  {r['entry']} → {r['landing']}{shared}"]
    for s in r["steps"]:
        tags = [" ↗換檔" * s["jump"], f" ≋分檔有責任軸（依檔名推測）{s['axis']}" * bool(s["axis"]),
                f" ?{s['guess']}" * bool(s["guess"])]
        lines.append(f"      {s['kind']:<9} {s['func']}{''.join(tags)}")
    if r["open_end"]:
        lines.append("      （落點只轉傳、下一站對不到唯一目標：可能還沒讀到底）")
    return lines


def render(report: dict, top: int) -> str:
    st = report["stats"]
    lines = [f"閱讀路徑｜{report['root']}｜Python {st['files']['py']}・C# {st['files']['cs']}・粗略 {st['files']['coarse']} 檔"
             f"｜函式 {st['funcs']}｜呼叫連到專案內 {st['linked_calls']}｜對不到唯一目標 {st['ambiguous']}",
             "尺不是判決：拐彎 0-1 順｜2 注意｜3 警戒｜≥4 臭掉（G11）。每個落點取拐彎最少的一條；拐彎＝轉手或換檔，一步最多算 1"]
    if st["ambiguous_ratio"] > AMBIGUOUS_WARN:
        lines.append(f"⚠ 對不到唯一目標的呼叫占 {st['ambiguous_ratio']:.0%}：圖可能缺邊，數字偏低不可信")
    if st["parse_errors"]:
        lines.append(f"解析失敗 {len(st['parse_errors'])} 檔：" + "、".join(st["parse_errors"][:5]))
    lines += [f"分檔有責任軸（依檔名推測）：{name}（{'・'.join(axes)}）——這些檔之間換檔不算彎，另計 axis_jumps"
              for name, axes in st["axis_classes"].items()]
    entries = report["entries"]
    lines.append(f"入口 {len(entries)} 個（最差在前）：")
    for e in entries[:ENTRY_LIST_LIMIT]:
        dist = "・".join(f"{label} {n}" for label, n in reversed(e["grades"].items()))
        lines.append(f"  [{grade(e['max_turns'])}] {e['entry']}  落點 {e['landings']}｜最多拐彎 {e['max_turns']}"
                     f"｜最多跳檔 {e['max_file_jumps']}｜最多轉手 {e['max_handoffs']}｜{dist}")
    if len(entries) > ENTRY_LIST_LIMIT:
        lines.append(f"  …另 {len(entries) - ENTRY_LIST_LIMIT} 個入口（--json 看全部）")
    worst = sorted((r for e in entries for r in e["routes"]),
                   key=lambda r: (-r["turns"], -r["file_jumps"], -r["handoffs"], -r["depth"], r["landing"]))
    lines.append(f"最差 {min(top, len(worst))} 條路徑：")
    for r in worst[:top]:
        lines += route_lines(r)
    return "\n".join(lines)


def render_compare(res: dict, top: int) -> str:
    c = res["counts"]
    sb, sa = res["stats_before"], res["stats_after"]
    lines = [f"前後比較｜{res['root']}｜before={res['before_label']} → after={res['after_label']}｜入口 {res['entries']}",
             "｜".join(f"{STATUS_LABEL[k]} {c[k]}" for k in c) + f"｜最多拐彎 {res['max_turns_before']} → {res['max_turns_after']}",
             f"解析：失敗 {len(sb['parse_errors'])} → {len(sa['parse_errors'])} 檔｜對不到唯一目標 "
             f"{sb['ambiguous_ratio']:.0%} → {sa['ambiguous_ratio']:.0%}"]
    if res["coverage_drop"]:
        lines.append("⚠ after 的解析涵蓋變差：「消失」「變好」可能是看不到了，不是程式變好——先看解析失敗清單 "
                     + "、".join(sa["parse_errors"][:5]))
    shown = 0
    for row in [r for r in res["rows"] if r["status"] != "same"]:
        b, a = row["before"] or {}, row["after"] or {}
        nums = "｜".join(f"{name} {b.get(k, '-')}→{a.get(k, '-')}"
                        for name, k in (("拐彎", "turns"), ("跳檔", "file_jumps"), ("轉手", "handoffs")))
        lines.append(f"  [{STATUS_LABEL[row['status']]}] {row['entry']} → {row['landing']}｜{nums}")
        if row["status"] in ("worse", "new") and shown < top:
            lines += route_lines(a)
            shown += 1
    return "\n".join(lines)


def done_line(report: dict) -> str:
    entries = report["entries"]
    routes = [r for e in entries for r in e["routes"]]
    grades = Counter(r["grade"] for r in routes)
    return (f"READING_PATH DONE entries={len(entries)} landings={len(routes)}"
            f" max_turns={max((e['max_turns'] for e in entries), default=0)}"
            f" max_file_jumps={max((e['max_file_jumps'] for e in entries), default=0)}"
            f" max_handoffs={max((e['max_handoffs'] for e in entries), default=0)}"
            f" smelly={grades['臭掉']} alert={grades['警戒']} notice={grades['注意']}"
            f" ambiguous={report['stats']['ambiguous']}")


def compare_done_line(res: dict) -> str:
    c = res["counts"]
    return (f"READING_PATH DONE mode=compare entries={res['entries']} better={c['better']} worse={c['worse']}"
            f" new={c['new']} gone={c['gone']} same={c['same']}"
            f" max_turns_before={res['max_turns_before']} max_turns_after={res['max_turns_after']}"
            f" coverage_drop={int(res['coverage_drop'])}")


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, epilog=LIMITS, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="專案根（預設目前目錄）")
    ap.add_argument("--entry", help="入口：檔路徑｜檔::函式｜函式名（Class.method）；不給就自動找")
    ap.add_argument("--to", help="只看落在這些函式的路徑（寫法同 --entry）")
    ap.add_argument("--top", type=int, default=3, help="列幾條最差路徑（預設 3；比較模式是列幾條變差／新增的路徑）")
    ap.add_argument("--before", help="前後比較的舊版本：git rev（--root 所在 repo）或目錄")
    ap.add_argument("--after", help="前後比較的新版本：git rev 或目錄（預設 --root 目前內容）")
    ap.add_argument("--json", action="store_true", help="輸出 JSON（最後一行仍是哨兵）")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if not root.is_dir():
            raise ReadingPathError(f"--root 不是目錄：{root}")
        if args.after and not args.before:
            raise ReadingPathError("--after 要搭配 --before")
        if args.before:
            res = run_compare(root, args.before, args.after, args.entry, args.to)
            missing = args.entry and res["entries"] == 0
            text, tail = render_compare(res, args.top), compare_done_line(res)
        else:
            res = analyze(root, args.entry, args.to)
            missing = args.entry and not res["entries"]
            text, tail = render(res, args.top), done_line(res)
        if missing:
            raise ReadingPathError(f"找不到入口 {args.entry}：用檔路徑、檔::函式 或 函式名（Class.method）")
    except ReadingPathError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False) if args.json else f"error: {e}")
        print(f"READING_PATH FAIL reason={str(e).splitlines()[0][:120]}")
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else text)
    print(tail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
