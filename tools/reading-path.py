#!/usr/bin/env python3
"""reading-path.py：量「人讀這段要跳幾個檔、經過幾層轉手、拐幾個彎」，從入口讀到功能落地的閱讀路徑。

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
確定與否：
  看不出實例的事件、看不出實際型別的繼承、沒比對參數的多載、執行時才選的分派表、多來源 callback → 邊標「候選」。
  每個落點先找只走確定邊的路；走不到才用含候選的路，那條路整條標成候選，彙總與比較都分開列。
  落點裡有專案內但解析不了的呼叫 → 標「未讀到底」（數字是下限），不算進刻度分布。
語言解析在同目錄 reading_path_lang.py（Python 用 ast；C# 不用 Roslyn；js/ts/go/java/kt/rs 粗略模式只數跳檔）。
"""
from __future__ import annotations

import argparse
import builtins
import codecs
import heapq
import io
import itertools
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
PY_BUILTINS = set(dir(builtins))
# 接收者型別不明時不拿來猜的方法名：內建型別本來就有的（d.get、s.strip…）與 .NET 常見方法
PY_BUILTIN_TYPES = (dict, list, str, set, bytes, tuple, int, float, io.TextIOWrapper, Path, re.Pattern, re.Match)
PY_BUILTIN_METHODS = set(itertools.chain.from_iterable(dir(t) for t in PY_BUILTIN_TYPES))
flat = itertools.chain.from_iterable
CS_COMMON_METHODS = {"Add", "AddRange", "Remove", "RemoveAt", "Contains", "ContainsKey", "TryGetValue", "Clear",
                     "ToString", "Equals", "GetHashCode", "Dispose", "Insert", "IndexOf", "Any", "All", "Where",
                     "Select", "First", "FirstOrDefault", "Last", "ToList", "ToArray", "Format", "Join", "Split",
                     "Trim", "Replace", "StartsWith", "EndsWith", "Substring", "Parse", "TryParse", "Sort", "Reverse",
                     "Push", "Pop", "Enqueue", "Dequeue", "Peek", "Append", "AppendLine", "GetComponent",
                     "SetActive", "Find", "Wait", "CompareTo", "CopyTo", "GetType", "Max", "Min", "Sum", "Count"}
# 檔裡看得到定義寫法、卻解析出零個函式 → 警示（可能是解析器沒認出來）
#   py：def，或頂層直接呼叫（頂層程式碼不追）；cs：方法寫法 `型別 名稱(...) {`，或頂層敘述 `X.Y(...);`
DEF_HINT = {"py": re.compile(r"^\s*(async\s+)?def\s|^[A-Za-z_][\w.]*\s*\(", re.M),
            "cs": re.compile(r"[\w>\]]\s+\w+\s*\([^;{)]*\)\s*(\{|=>)|^\s*[\w.]+\s*\([^;]*\)\s*;", re.M),
            "coarse": re.compile(r"\bfunction\b|\bfunc\s|\bfn\s|=>")}
# partial 檔名後綴看不出責任的（Part1、2、More、Misc…）不算責任軸
NON_AXIS_SUFFIX = re.compile(r"(?i)^(part|partial|file|section|piece|split)?\d+$|^(more|extra|misc|other|others|rest|temp|tmp|new|old|copy)$")
ROOT_LIMIT = 10           # 沒有天生入口時，最多拿幾個「沒人呼叫的公開函式」當入口
ENTRY_LIST_LIMIT = 20     # 表頭列幾個入口（--json 看全部）
UNRESOLVED_WARN = 0.3     # 解析不了的專案內呼叫超過這個比例 → 表頭警示數字偏低
COVERAGE_DROP = 0.05      # 前後比較時 after 的未解比例多出這麼多 → 警示可能是解析退化
MAX_REEXPORT = 5          # from a import x 追 re-export、追函式別名最多幾跳（防循環）
SHARED_FAN_IN = 5         # 落點被這麼多處呼叫 → 標「共用底層」：讀功能時通常不必沿這條路讀到它
DEEP_STRAIGHT = 6         # 深度到這麼多但拐彎 ≤1 → 提醒「同檔多層有實質內容的呼叫不算彎」
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

LIMITS = """抓不到／可能偏差（數字是尺，判斷交給人）：
  - 每個落點只取拐彎最少的一條路（G11「重找最短路」的口徑）；同一落點更繞的路不列
  - 專案內但解析不了的呼叫（區域變數裝的函式、同名方法多個、找不到的 self 方法、getattr）計入未解，
    落點標「未讀到底」；確知在專案外的（內建、外部模組、外部父類、專案沒有同名方法）不算
  - 外部函式庫、框架回呼（Unity 生命週期以外）、反射、eval、動態 import 看不到；getattr 只認分派表來的
  - 事件只在「同一函式對同一接收者訂閱又發出」時算確定，其餘看不出實例，標候選；callback 多處各傳不同函式也標候選
  - 繼承分派只有接收者是剛 new 出來的物件才算確定型別；多載不比對參數型別，同名多個一律標候選
  - 區域變數被指定超過一次：不追別名、不算確定型別、不算同一實例（寧可算未解或候選）
  - callback 與函式別名只追一層傳遞：函式被當參數再往下轉傳一次就斷；工廠函式回傳的閉包看不到（計入未解）
  - 「只轉傳」靠句數判定（換區域變數名不算句）：塞進無關計算就會被當成有內容
  - 同檔多層有實質內容的呼叫：深度高但不算彎（刻度只看拐彎）
  - Python：裝飾器包裝、@property、模組頂層（__main__ 以外）程式碼、monkeypatch 不追
  - C#（不用 Roslyn）：擴充方法、LINQ、var 由方法回傳推型別、跨 namespace 同名類合併、lambda 裡的呼叫算外層函式、
    #if 不分支、運算子多載與索引子不認、接收者型別不明的屬性不猜、三元運算與 LINQ 不算分支、插值字串 {} 裡再套字串會漏
  - partial 責任軸是依檔名推測：檔名沒寫成 `類.責任.cs` → 照算跳檔，有責任軸但沒標在檔名上的分檔數字會偏高；
    反過來，取了像樣後綴但其實沒分責任的也會被當成有軸（Part1、Misc 這類已排除），輸出都標「依檔名推測」
  - 分層架構（main→service→repo 各一檔）每層換檔都算彎：可能誤報，由讀的人判
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
    unresolved: int = 0      # 落點裡專案內但解析不了的呼叫數：>0 ＝ 未讀到底
    fan_in: int = 0          # 落點被幾個函式呼叫
    sig: str | None = None   # 落點的參數型別簽章（C#）；比較時對齊多載

    def summary(self) -> dict:
        moves = self.steps[1:]
        turns = sum(s.turn for s in moves)
        return {"entry": self.entry, "landing": self.landing, "sig": self.sig, "turns": turns, "grade": grade(turns),
                "file_jumps": sum(s.jump for s in moves), "axis_jumps": sum(bool(s.axis) for s in moves),
                "handoffs": sum(s.kind != "direct" for s in moves), "depth": len(moves),
                "certain": not any(s.guess for s in moves), "incomplete": self.unresolved > 0,
                "unresolved": self.unresolved, "fan_in": self.fan_in, "steps": [asdict(s) for s in self.steps]}


def grade(turns: int) -> str:
    return next(label for floor, label in GRADES if turns >= floor)


def worst_first(r: dict) -> tuple:
    return -r["turns"], -r["file_jumps"], -r["handoffs"], -r["depth"], r["landing"]


def is_test(rel: str) -> bool:
    """用相對專案根的路徑判斷（絕對路徑會比到專案外的上層目錄名）。"""
    parts = rel.split("/")
    return bool(TEST_DIRS & set(parts[:-1])) or bool(TEST_FILE_RE.match(parts[-1]))


def read_source(path: Path) -> str:
    """依 BOM 解碼 UTF-8／UTF-16 LE／BE；沒 BOM 就嚴格 UTF-8，解不開丟 UnicodeDecodeError（列進解析失敗，不靜默替換）。"""
    data = path.read_bytes()
    boms = ((codecs.BOM_UTF8, "utf-8-sig"), (codecs.BOM_UTF16_LE, "utf-16"), (codecs.BOM_UTF16_BE, "utf-16"))
    encoding = next((enc for bom, enc in boms if data.startswith(bom)), "utf-8")
    return data.decode(encoding)


# ─── 偵測器：每一種轉手各一個（反證測試會一次拿掉一個） ─────────────────────


def override_targets(g: "Graph", cls: lang.Cls, name: str) -> list:
    """cls 的子孫類別裡覆寫 name 的方法：繼承／介面分派可能跑到的地方。"""
    return [fid for fid in flat(sub.methods.get(name, []) for sub in g.descendants(cls)) if not g.funcs[fid].abstract]


def callback_targets(g: "Graph", bind_fid: str, param: str) -> list:
    """bind_fid 的參數 param 被當函式呼叫：找所有呼叫 bind_fid 的地方，那個位置傳進來的是哪個函式
    → [(func id, 不確定原因)]；傳進來的參照本身是猜的，原因跟著帶過來。"""
    out = []
    for caller, ref in g.bound_refs(bind_fid, param):
        out += [(e.dst, e.guess) for e in g.resolve(caller, ref, defer=False)]
    return out


def event_targets(g: "Graph", f: lang.Func, c: lang.Call) -> list:
    """訂閱了同名事件的處理函式 → [(func id, 同一實例否, 處理函式本身的不確定原因)]。
    同一函式裡對同一接收者訂閱又發出、且接收者沒被重新指定，才算同一實例。"""
    out = []
    for key, ref, owner, file, recv in g.subs:
        if key != c.name or not g.same_side(f, file):
            continue
        sure = bool(c.recv) and owner == f.id and recv == c.recv and c.recv not in f.reassigned
        ctx = g.funcs.get(owner) or g.module_ctx(file)
        out += [(e.dst, sure, e.guess) for e in g.resolve(ctx, ref, defer=False)]
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

    def __init__(self, root: Path, modules: list, scan: dict):
        self.root = root
        self.scan = scan           # parse_errors、empty_files、file_funcs（-1＝解析失敗）
        self.modules = {m.file: m for m in modules}
        self.known_py = set(self.modules) | {f for f, n in scan["file_funcs"].items() if n < 0 and f.endswith(".py")}
        self.funcs = {f.id: f for f in flat(m.funcs for m in modules)}
        self.subs = list(flat(m.subs for m in modules))
        self.classes = defaultdict(list)
        self.children = defaultdict(list)
        self.mod_index = defaultdict(list)
        self.coarse = defaultdict(list)
        self.edges = defaultdict(list)
        self.callers = defaultdict(list)
        self.pending = []          # (src, 綁定的 func id, 參數名)：callback 要等所有呼叫者都連好才解
        self.hits = Counter()      # 每個函式有幾個呼叫連到專案內
        self.unres = Counter()     # 每個函式有幾個呼叫在專案內但解析不了
        self._index(modules)
        self._resolve_all()
        self.fan_in = Counter()
        for es in self.edges.values():
            self.fan_in.update({e.dst for e in es})
        self.called = set(self.fan_in)
        self.axis = {c.name: partial_axis(c) for c in self.all_classes() if c.lang == "cs"}
        self.passthrough = {f.id: self._forward_style(f) for f in self.funcs.values() if self._is_passthrough(f)}

    def _index(self, modules: list) -> None:
        for m in modules:
            for c in m.classes:
                self._add_class(c)
        for f in [f for f in self.funcs.values() if f.lang == "coarse"]:
            self.coarse[f.name].append(f.id)
        for file in sorted(self.known_py):
            parts = file[:-3].split("/")
            parts = parts[:-1] if parts[-1] == "__init__" else parts
            for i in range(len(parts)):
                self.mod_index[".".join(parts[i:])].append(file)
        self.by_method = defaultdict(list)
        for c in self.all_classes():
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

    def all_classes(self) -> list:
        return list(flat(self.classes.values()))

    def signature(self, fid: str):
        """C# 方法的完整參數型別簽章（比較時用「名稱＋簽章」對齊多載）；其他語言沒有多載，回 None。"""
        f = self.funcs[fid]
        return f.sig if f.lang == "cs" else None

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

    def external_base(self, cls) -> bool:
        """類別（含祖先）有不在專案裡的父類：找不到的方法可能是從那裡繼承來的。沒有類別也當外部。"""
        if cls is None:
            return True
        for c in self.ancestry(cls):
            if any(self.cls_named(b, c.files[0]) is None for b in c.bases):
                return True
        return False

    def field_type(self, cls, attr: str):
        owner = next((c for c in self.ancestry(cls) if attr in c.fields), None)
        return self.cls_named(owner.fields[attr], owner.files[0]) if owner else None

    def stored_param(self, cls, attr: str):
        return next((c.stored[attr] for c in self.ancestry(cls) if attr in c.stored), None)

    def find_module(self, name: str, level: int, from_file: str):
        """Python import 名 → 專案內的檔（解析失敗的也算）；相對 import 照層級，絕對 import 比模組名尾段（同目錄優先，多個同名就不連）。"""
        if level:
            parents = PurePosixPath(from_file).parents
            if level > len(parents):
                return None
            base = parents[level - 1] / name.replace(".", "/") if name else parents[level - 1]
            cands = [base / "__init__.py"] if not name else [PurePosixPath(f"{base}.py"), base / "__init__.py"]
            hits = [p.as_posix() for p in cands if p.as_posix() in self.known_py]
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

    def bound_refs(self, bind_fid: str, param: str) -> list:
        """呼叫 bind_fid 的每個地方，在 param 那個位置傳進來的函式參照 → [(呼叫者, 參照)]。
        傳 lambda 的不算參照（內容就寫在呼叫者裡）。Python 方法經由物件呼叫時第一個參數是 self，位置要扣掉。"""
        f = self.funcs[bind_fid]
        offset = 1 if f.lang == "py" and f.cls and f.params[:1] in (["self"], ["cls"]) else 0
        pos = f.params.index(param) - offset
        callers = [(caller, call) for caller, call in self.callers.get(bind_fid, []) if self.same_side(f, caller.file)]
        out = []
        for caller, call in callers:
            out += [(caller, ref) for key, ref in call.refs if key in (pos, param)]
        return out

    def same_side(self, f: lang.Func, other_file: str) -> bool:
        """非測試碼不採用測試檔傳進來的假函式、訂閱的處理函式（那只在跑測試時存在）。"""
        return is_test(f.file) or not is_test(other_file)

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

    def dispatch(self, cls, name: str, via: str = "", exact: bool = False) -> list:
        """在 cls 上呼叫 name。實際型別確定（剛 new 出來）→ 只連它自己的實作；
        不確定且子類有覆寫（或本身抽象）→ inherit 連到所有實作並標候選；同名多載 → 全連並標候選。"""
        ids = list(dict.fromkeys(self.lookup(cls, name)))
        if not ids:
            return []
        over = [] if exact else override_targets(self, cls, name)
        if not over:
            return self._overloads(ids, via)
        concrete = [i for i in ids if not self.funcs[i].abstract]
        reason = "候選：實際型別不確定，基底實作與子類覆寫都可能"
        return [Edge(i, "inherit", guess=reason, via=via) for i in dict.fromkeys(concrete + over)]

    def _overloads(self, ids: list, via: str = "") -> list:
        """同一個名字有幾個實作就連幾條；多於一個（多載）時沒比對參數型別，全部標候選。dispatch、base.、建構子共用。"""
        reason = f"候選：{len(ids)} 個多載，沒比對參數型別" if len(ids) > 1 else ""
        return [Edge(i, "direct", guess=reason, via=via) for i in dict.fromkeys(ids)]

    def _defer(self, src: lang.Func, bind: tuple, defer: bool) -> list:
        if defer:
            self.pending.append((src.id, *bind))
        return []

    def alias_target(self, f: lang.Func, name: str):
        """fn = b; fn(n)：沿區域變數別名走到真正的函式參照（最多 MAX_REEXPORT 跳）；
        不是別名、循環、或中途被重新指定 → None（寧可算未解，也不挑一個當確定目標）。"""
        if name not in f.aliases or name in f.reassigned:
            return None
        ref, hops = f.aliases[name], 0
        while ref.kind == "name" and ref.name in f.aliases and ref.name not in f.reassigned and hops < MAX_REEXPORT:
            ref, hops = f.aliases[ref.name], hops + 1
        stuck = ref.kind == "name" and (ref.name in f.aliases or ref.name in f.reassigned)
        return None if stuck else ref

    def _r_name(self, f, c, defer):
        if c.name in f.params:
            return self._defer(f, (f.id, c.name), defer)
        if c.name in f.aliases:
            ref = self.alias_target(f, c.name)
            return self.resolve(f, ref, defer) if ref else []
        if c.name in f.table_vars:
            return self._r_table(f, lang.Call("table", f.table_vars[c.name]), defer)
        nested = next((n for s in reversed(self.scopes(f)) if (n := f"{f.file}::{s}.{c.name}") in self.funcs), None)
        if nested:
            return [Edge(nested, "direct")]       # 自己或外層函式裡定義的巢狀函式
        if f.lang == "coarse":
            return self._coarse(f, c.name)
        if f.lang == "py":
            return self._py_name(f.file, c.name, imports=self.imports_of(f))
        return self._r_self(f, c, defer) or self._static_using(f, c.name)   # C#：本類別的方法／事件／委派欄位，或 using static

    def _static_using(self, f: lang.Func, name: str) -> list:
        """C# `using static 專案類別;` 之後的裸名呼叫：到那些類別找靜態方法。"""
        for t in self.modules[f.file].static_usings if f.file in self.modules else []:
            cls = self.cls_named(t.split(".")[-1], f.file)
            edges = self.dispatch(cls, name, exact=True) if cls else []
            if edges:
                return edges
        return []

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
        return self._overloads(ids)

    def _r_attr(self, f, c, defer):
        kind, target, exact = self.recv_type(f, c.recv)
        if kind == "module":
            return self._py_name(target, c.name)
        if kind == "external":
            return []
        if target is not None:
            return self.dispatch(target, c.name, via="object" if kind == "object" else "", exact=exact)
        return self._guess(f, c.name)

    def _r_new(self, f, c, defer):
        cls = self.cls_named(c.name, f.file)
        return self._ctor(cls) if cls else []

    def _r_emit(self, f, c, defer):
        reason = "候選：事件只按名字配對，看不出是哪個實例"
        return [Edge(t, "event", guess=guess or ("" if sure else reason)) for t, sure, guess in event_targets(self, f, c)]

    def _r_invoke(self, f, c, defer):
        """C# 的 X.Invoke()／X?.Invoke()：X 是參數、別名或建構時存下的委派 → callback；否則當事件。"""
        if c.name in f.params:
            return self._defer(f, (f.id, c.name), defer)
        if c.name in f.aliases:
            ref = self.alias_target(f, c.name)
            return self.resolve(f, ref, defer) if ref else []
        stored = self.stored_param(self.cls_of(f), c.name) if f.cls else None
        return self._defer(f, stored, defer) if stored else self._r_emit(f, c, defer)

    def _r_table(self, f, c, defer):
        """分派表：函式內的表在函式語境解（self._r_x 要認得出類別），模組層的表在模組語境解。"""
        if c.name in f.tables:
            return self._dynamic(f, f.tables[c.name], c.key)
        return self._table(f.file, c.name, c.key)

    def _r_getattr(self, f, c, defer):
        """getattr(module, spec[1])(…)：用到的變數來自分派表 → 連到表裡全部；否則看不到目標（計入未解）。"""
        tables = [f.table_vars[n] for n in c.name.split(",") if n in f.table_vars]
        return self._r_table(f, lang.Call("table", tables[0]), defer) if tables else []

    def _r_prop(self, f, c, defer):
        """C# 讀寫屬性：只連到有 get/set 本體的屬性；接收者型別不明就不猜（屬性名太常見）。"""
        if c.recv and c.recv != "this":
            _, target, exact = self.recv_type(f, c.recv)
        else:
            target, exact = self.cls_of(f), False
        edges = self.dispatch(target, c.name, exact=exact) if target else []
        return [e for e in edges if self.funcs[e.dst].prop]

    def _ctor(self, cls) -> list:
        return self._overloads(self.lookup(cls, "__init__" if cls.lang == "py" else cls.name))

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
        if name in mod.aliases:
            return self._py_alias(file, mod.aliases[name], hops + 1)
        src, orig = self._imported_from(file, mod.imports if imports is None else imports, name)
        return self._py_name(src, orig, hops + 1) if src else []

    def _py_alias(self, file: str, ref: lang.Call, hops: int) -> list:
        """模組層別名 NAME = 別的函式：同模組的名字，或匯入的專案模組成員（追的跳數與 re-export 共用上限）。"""
        if ref.kind == "name":
            return self._py_name(file, ref.name, hops)
        target = self.module_alias(self.module_ctx(file), ref.recv) if ref.kind == "attr" else None
        return self._py_name(target, ref.name, hops) if target else []

    def _table(self, file: str, name: str, key: str = "", hops: int = 0) -> list:
        mod = self.modules.get(file)
        if mod is None or hops > MAX_REEXPORT:
            return []
        if name not in mod.tables:
            src, orig = self._imported_from(file, mod.imports, name)
            return self._table(src, orig, key, hops + 1) if src else []
        return self._dynamic(self.module_ctx(file), mod.tables[name], key)

    def _dynamic(self, ctx: lang.Func, entries: list, key: str) -> list:
        """分派表的項目：呼叫時寫死了鍵且對得上 → 只連那一項；否則執行時才選，多項就全連並標候選。"""
        picked = [ref for k, ref in entries if key and k == key] or [ref for _, ref in entries]
        reason = f"候選：分派表依執行時的鍵選一個（{len(picked)} 項）" if len(picked) > 1 else ""
        edges = []
        for ref in picked:
            edges += [Edge(e.dst, "dynamic", guess=e.guess or reason) for e in self.resolve(ctx, ref, defer=False)]
        return edges

    def _coarse(self, f, name: str) -> list:
        cands = self.coarse.get(name, [])
        pick = [i for i in cands if self.funcs[i].file == f.file] or cands
        return [Edge(pick[0], "direct")] if len(pick) == 1 else []

    def _guess_cands(self, f, name: str) -> list:
        """接收者型別不明時可能的同名方法；內建型別本來就有的方法名不算，非測試碼不算測試檔裡的。"""
        common = PY_BUILTIN_METHODS if f.lang == "py" else CS_COMMON_METHODS
        cands = [] if name in common else self.by_method.get(name, [])
        return [i for i in cands if self.same_side(f, self.funcs[i].file)]

    def _guess(self, f, name: str) -> list:
        """接收者型別不明：全專案只有一個同名方法才連（標為猜的），多個就不連（計入未解）。"""
        cands = self._guess_cands(f, name)
        reason = "猜的：接收者型別不明，全專案只有這個同名方法"
        return [Edge(cands[0], "direct", guess=reason, via="object")] if len(cands) == 1 else []

    def recv_type(self, f: lang.Func, recv: str):
        """接收者是什麼 → (種類, 對象, 實際型別確定否)：module＋檔｜object／static＋類別｜external｜("", None) 不明。"""
        if recv.startswith("new:"):
            return "object", self.cls_named(recv[4:], f.file), True
        if recv.startswith("mod:"):
            target = self.find_module(recv[4:], 0, f.file)
            return ("module", target, False) if target else ("external", None, False)
        whole = self.module_alias(f, recv) if f.lang == "py" and recv else None
        if whole:
            return "module", whole, False
        head, *rest = recv.split(".")
        kind, cls = self._recv_head(f, head)
        for seg in rest:
            cls = self.field_type(cls, seg) if cls else None
        exact = (kind == "static" or (head in f.exact and head not in f.reassigned)) and not rest
        return (kind, cls, exact) if cls or kind == "external" else ("", None, False)

    def _recv_head(self, f: lang.Func, head: str):
        if head in ("self", "this"):
            return "object", self.cls_of(f)
        changed = head in f.exact and head in f.reassigned      # x = Base() 之後又 x = Child()：型別不定
        typed = None if changed else f.local_types.get(head) or f.param_types.get(head)
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

    # 解析不到時：確知在專案外，還是專案內但看不到 ────────

    def is_external(self, f: lang.Func, c: lang.Call) -> bool:
        """確知在專案外（內建、外部模組、外部父類、專案裡沒有同名方法、沒人訂閱的事件、外部類別）→ True；
        專案內但看不到（區域變數裝的函式、同名方法多個、找不到的 self 方法、getattr、找不到的表）→ False，計入未解。"""
        if c.kind in ("emit", "prop", "new", "super"):
            return True
        if c.kind in ("table", "getattr"):
            return False
        if c.kind == "invoke":                     # 沒人訂閱的事件 → 外部；區域變數或不明欄位裝的委派 → 看不到
            return bool(f.cls) and any(c.name in x.events for x in self.ancestry(self.cls_of(f)))
        if c.kind == "self":
            return self.external_base(self.cls_of(f))
        if c.kind == "name":
            return self._external_name(f, c.name)
        return self._external_attr(f, c)

    def _external_name(self, f: lang.Func, name: str) -> bool:
        if name in f.inline:
            return True                            # 就地定義的 lambda／區域函式：內容就在這個函式裡
        ref = self.alias_target(f, name)
        if ref:
            return self.is_external(f, ref)        # parse = json.loads; parse(s)：看別名指到哪
        if name in f.locals:
            return False                           # 區域變數裝的函式（工廠回傳、條件指定）：看不到
        if f.lang == "coarse":
            return not self.coarse.get(name)
        if f.lang == "cs":
            usings = self.modules[f.file].static_usings if f.file in self.modules else []
            outside = any(self.cls_named(t.split(".")[-1], f.file) is None for t in usings)
            return outside or self.external_base(self.cls_of(f))
        if name in PY_BUILTINS or self.classes.get(name):
            return True
        alias = self.modules[f.file].aliases.get(name) if f.file in self.modules else None
        if alias:                                  # 模組層別名指向外部模組的函式（flat = itertools.chain.from_iterable）
            return alias.kind == "attr" and self.recv_type(self.module_ctx(f.file), alias.recv)[0] == "external"
        return self._py_external(f.file, self.imports_of(f), name)

    def _py_external(self, file: str, imports: dict, name: str, hops: int = 0) -> bool:
        """name 沿 import／re-export 追到底是外部模組的東西 → True；追到專案內、沒匯入或追不到 → False。"""
        imp = imports.get(name)
        if not imp or hops > MAX_REEXPORT:
            return False
        modname, level, orig = imp
        src = self.find_module(modname, level, file)
        if src is None:
            return True
        mod = self.modules.get(src)
        if mod is None or not orig or orig in mod.defs or self.classes.get(orig):
            return False
        return self._py_external(src, mod.imports, orig, hops + 1)

    def _external_attr(self, f: lang.Func, c: lang.Call) -> bool:
        kind, target, _ = self.recv_type(f, c.recv)
        if kind in ("external", "module"):
            return kind == "external" or bool(self.classes.get(c.name))
        if target is not None:
            return self.external_base(target)
        return not self._guess_cands(f, c.name)

    # 建邊 ───────────────────────────────────────────────

    def _resolve_all(self) -> None:
        for f in list(self.funcs.values()):
            for c in [c for c in f.calls if not c.noise]:
                waiting = len(self.pending)
                edges = self.resolve(f, c)
                self._add_edges(f.id, edges, c)
                linked = bool(edges) or len(self.pending) > waiting
                self.hits[f.id] += linked
                self.unres[f.id] += not linked and not self.is_external(f, c)
        for src, bind, param in self.pending:
            found = {}
            for dst, guess in callback_targets(self, bind, param):
                found[dst] = guess if dst not in found else (found[dst] and guess)   # 有一處確定就算確定
            reason = f"候選：{len(found)} 處呼叫各傳不同函式進 {param}，分不出這次是哪個" if len(found) > 1 else ""
            self._add_edges(src, [Edge(t, "callback", guess=g or reason) for t, g in found.items()], None)
            self.unres[src] += not found and bool(self.bound_refs(bind, param))   # 有人傳了具名函式卻解不出來

    def _add_edges(self, src: str, edges: list, c) -> None:
        """加邊（同終點同種類只留一條）；直接／繼承呼叫每個呼叫點都記下呼叫者（就算邊重複），callback 要回頭查誰傳了什麼。"""
        for e in edges:
            if c is not None and e.kind in ("direct", "inherit"):
                self.callers[e.dst].append((self.funcs[src], c))
            if not any(x.dst == e.dst and x.kind == e.kind for x in self.edges[src]):
                self.edges[src].append(e)

    def _is_passthrough(self, f: lang.Func) -> bool:
        """只把呼叫往下傳：≤2 句、無分支迴圈、恰好一個呼叫連到專案內、沒有解析不了的呼叫。"""
        return (f.simple and not f.entry and not f.abstract and f.lang != "coarse"
                and self.hits[f.id] == 1 and not self.unres[f.id])

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

    def _shortest(self, entry: str, certain_only: bool):
        """從 entry 出發的最短路（拐彎、跳檔、深度依序比）；certain_only 時只走確定的邊。"""
        best, back = {entry: (0, 0, 0)}, {}
        heap = [((0, 0, 0), entry)]
        while heap:
            cost, u = heapq.heappop(heap)
            if cost > best[u]:
                continue
            for e in [e for e in self.edges.get(u, []) if not (certain_only and e.guess)]:
                s = self.step(self.funcs[u], e)
                nxt = (cost[0] + s.turn, cost[1] + s.jump, cost[2] + 1)
                if nxt < best.get(e.dst, (float("inf"),)):
                    best[e.dst], back[e.dst] = nxt, (u, s)
                    heapq.heappush(heap, (nxt, e.dst))
        return best, back

    def routes(self, entry: str):
        """每個落點一條路：只走確定邊走得到就用那條；走不到才用含候選的路。另回入口可達範圍內有未解呼叫的函式。"""
        sure_best, sure_back = self._shortest(entry, True)
        any_best, any_back = self._shortest(entry, False)
        landings = [v for v in any_best if v != entry and v not in self.passthrough and not self.funcs[v].abstract]
        found = [self._route(sure_back if v in sure_best else any_back, entry, v) for v in landings]
        return found, sorted(v for v in any_best if self.unres[v])

    def _route(self, back: dict, entry: str, landing: str) -> Route:
        steps, node = [], landing
        while node != entry:
            node, s = back[node]
            steps.append(s)
        return Route(entry, landing, [Step(entry, "entry")] + steps[::-1], self.unres[landing], self.fan_in[landing],
                     self.signature(landing))


# ─── 掃描、入口、分析 ────────────────────────────────────────────────────────


def build_graph(root: Path) -> Graph:
    paths, modules = [], []
    scan = {"parse_errors": [], "empty_files": [], "file_funcs": {}}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        paths += [Path(dirpath) / name for name in sorted(filenames) if Path(name).suffix.lower() in PARSERS]
    for path in paths:
        rel = path.relative_to(root).as_posix()
        if lang.GENERATED_RE.search(rel):
            continue
        try:
            text = read_source(path)
            mod = PARSERS[path.suffix.lower()](rel, text)
        except (SyntaxError, ValueError, RecursionError) as e:
            scan["parse_errors"].append(f"{rel}（{type(e).__name__}）")
            scan["file_funcs"][rel] = -1
            continue
        modules.append(mod)
        scan["file_funcs"][rel] = len(mod.funcs)
        if not mod.funcs and DEF_HINT[mod.lang].search(text):
            scan["empty_files"].append(rel)
    return Graph(root, modules, scan)


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


def entry_summary(g: Graph, eid: str, routes: list, unresolved_funcs: list) -> dict:
    """一個入口的彙總：最多拐彎與刻度分布只算全確定、讀到底的路；含候選、未讀到底的另計。"""
    routes.sort(key=worst_first)
    sure = [r for r in routes if r["certain"]]
    grades = Counter(r["grade"] for r in sure if not r["incomplete"])
    return {"entry": eid, "landings": len(routes),
            "max_turns": max((r["turns"] for r in sure), default=0),
            "max_turns_candidate": max((r["turns"] for r in routes if not r["certain"]), default=0),
            "max_file_jumps": max((r["file_jumps"] for r in sure), default=0),
            "max_handoffs": max((r["handoffs"] for r in sure), default=0),
            "grades": {label: grades.get(label, 0) for _, label in GRADES},
            "candidate": len(routes) - len(sure), "incomplete": sum(r["incomplete"] for r in routes),
            "unresolved_reach": sum(g.unres[v] for v in unresolved_funcs), "unresolved_funcs": unresolved_funcs,
            "routes": routes}


def analyze(root: Path, entry: str | None = None, to: str | None = None) -> dict:
    g = build_graph(root)
    targets = {f.id for f in spec_hits(g, to)[0]} if to else None
    report = {"root": str(root), "stats": graph_stats(g), "entries": []}
    for eid in find_entries(g, entry):
        found, unresolved_funcs = g.routes(eid)
        routes = [r.summary() for r in found if targets is None or r.landing in targets]
        report["entries"].append(entry_summary(g, eid, routes, unresolved_funcs))
    report["entries"].sort(key=lambda e: (-e["max_turns"], -e["max_file_jumps"], e["entry"]))
    report["caveats"] = caveats(g, report)
    return report


def graph_stats(g: Graph) -> dict:
    files = Counter(m.lang for m in g.modules.values())
    linked, unresolved = sum(g.hits.values()), sum(g.unres.values())
    axis = {name: sorted(a.values()) for name, a in g.axis.items() if a}
    return {"files": {"py": files["py"], "cs": files["cs"], "coarse": files["coarse"]}, "funcs": len(g.funcs),
            "linked_calls": linked, "unresolved": unresolved, "axis_classes": axis,
            "unresolved_ratio": round(unresolved / (linked + unresolved), 3) if linked + unresolved else 0.0,
            "parse_errors": g.scan["parse_errors"], "empty_files": g.scan["empty_files"],
            "file_funcs": g.scan["file_funcs"]}


def caveats(g: Graph, report: dict) -> list:
    """這次輸出實際碰到的限制與可能誤報（只列有發生的），讓讀數字的人知道哪裡要打折。"""
    routes = list(flat(e["routes"] for e in report["entries"]))
    kinds = Counter(s["kind"] for s in flat(r["steps"][1:] for r in routes))
    unaxis = sorted(c.name for c in g.all_classes()
                    if c.lang == "cs" and c.partial and len(c.files) > 1 and not g.axis.get(c.name))
    candidate = sum(not r["certain"] for r in routes)
    incomplete = sum(r["incomplete"] for r in routes)
    checks = [
        (any(r["file_jumps"] >= 3 and r["handoffs"] <= 1 for r in routes),
         "分層換檔：有路徑的彎幾乎都來自換檔（跳檔≥3、轉手≤1），若是刻意的分層架構可能誤報"),
        (kinds["wrapper"] + kinds["delegate"],
         f"只轉傳的層 {kinds['wrapper'] + kinds['delegate']} 步：adapter／facade 若是刻意設計，彎數會偏高"),
        (kinds["event"] + kinds["callback"], "事件與 callback 管線：看不出實例或呼叫語境的已標候選"),
        (kinds["dynamic"], "分派表：執行時依鍵選一個，沒寫死鍵的已標候選"),
        (kinds["inherit"], "繼承／介面分派：實際型別不確定時基底與覆寫都連，已標候選"),
        (unaxis, f"無責任後綴的 partial：{'、'.join(unaxis)} 換檔照算，數字可能偏高"),
        (candidate, f"含候選的路徑 {candidate} 條：可能是實際走不到的捷徑，與全確定的分開列"),
        (incomplete, f"未讀到底的落點 {incomplete} 個：落點裡有專案內但解析不了的呼叫，數字是下限"),
        (g.scan["empty_files"], f"有定義卻解析出零函式 {len(g.scan['empty_files'])} 檔：可能是解析器沒認出來"),
        (report["stats"]["files"]["coarse"], "粗略模式的檔只數跳檔、不判轉手"),
        (any(r["depth"] >= DEEP_STRAIGHT and r["turns"] <= 1 for r in routes),
         "同檔多層有實質內容的呼叫：深度高但不算彎"),
        (any(r["fan_in"] >= SHARED_FAN_IN for r in routes), "共用底層落點：讀某個功能時通常不必讀到，路長不一定是問題"),
    ]
    return [msg for hit, msg in checks if hit]


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


STATUS_ORDER = ("worse", "undecidable", "new", "gone", "better", "same")
STATUS_LABEL = {"worse": "變差", "undecidable": "不可判定", "new": "新增", "gone": "消失", "better": "變好", "same": "不變"}


def compare(before: dict, after: dict) -> dict:
    """同一入口、同一落點（檔::函式）比拐彎、跳檔、轉手。全確定與含候選的路分開數；
    入口可達範圍內的未解呼叫變多、或冒出新的未解函式 → 那個入口的變化標「不可判定」（可能是看不到了，不是變好）。"""
    b_entries = {e["entry"]: e for e in before["entries"]}
    a_entries = {e["entry"]: e for e in after["entries"]}
    undecidable = {eid for eid, a in a_entries.items() if eid in b_entries and _coverage_worse(b_entries[eid], a)}
    rows = []
    for eid in sorted(set(b_entries) | set(a_entries)):
        b = {compare_key(r): r for r in b_entries.get(eid, {}).get("routes", [])}
        a = {compare_key(r): r for r in a_entries.get(eid, {}).get("routes", [])}
        rows += [_diff_row(eid, b.get(key), a.get(key), eid in undecidable) for key in sorted(set(b) | set(a))]
    rows.sort(key=lambda r: (not r["certain"], STATUS_ORDER.index(r["status"]), r["entry"], r["landing"]))
    sure = Counter(r["status"] for r in rows if r["certain"])
    maybe = Counter(r["status"] for r in rows if not r["certain"])
    sb, sa = before["stats"], after["stats"]
    emptied = sorted(f for f, n in sb["file_funcs"].items() if n > 0 and sa["file_funcs"].get(f, 1) <= 0)
    coverage_drop = bool(len(sa["parse_errors"]) > len(sb["parse_errors"]) or emptied or undecidable
                         or sa["unresolved_ratio"] > sb["unresolved_ratio"] + COVERAGE_DROP)
    return {"entries": len(set(b_entries) | set(a_entries)), "rows": rows,
            "counts": {k: sure.get(k, 0) for k in STATUS_ORDER},
            "counts_candidate": {k: maybe.get(k, 0) for k in STATUS_ORDER},
            "max_turns_before": max((e["max_turns"] for e in before["entries"]), default=0),
            "max_turns_after": max((e["max_turns"] for e in after["entries"]), default=0),
            "undecidable_entries": sorted(undecidable), "emptied_files": emptied,
            "stats_before": sb, "stats_after": sa, "coverage_drop": coverage_drop}


def _coverage_worse(b: dict, a: dict) -> bool:
    return a["unresolved_reach"] > b["unresolved_reach"] or bool(set(a["unresolved_funcs"]) - set(b["unresolved_funcs"]))


def compare_key(r: dict) -> str:
    """落點在前後比較時的對齊鍵：C# 用「檔::類.方法(參數型別)」，多載刪到剩一個（id 變回裸名）也對得上同一個方法。"""
    return r["landing"] if r["sig"] is None else f"{r['landing'].split('(')[0]}({r['sig']})"


def _diff_row(entry: str, b: dict | None, a: dict | None, undecidable: bool) -> dict:
    landing = (a or b)["landing"]
    key = ("turns", "file_jumps", "handoffs")
    if b is None or a is None:
        status = "new" if b is None else "gone"
    else:
        vb, va = tuple(b[k] for k in key), tuple(a[k] for k in key)
        status = "same" if va == vb else ("better" if va < vb else "worse")
    status = "undecidable" if undecidable and status != "same" else status
    certain = all(r["certain"] for r in (b, a) if r)
    return {"entry": entry, "landing": landing, "status": status, "certain": certain, "before": b, "after": a}


def run_compare(root: Path, before: str, after: str | None, entry: str | None, to: str | None) -> dict:
    with tempfile.TemporaryDirectory(prefix="reading-path-") as tmp:
        b_root = materialize(before, root, Path(tmp), "before")
        a_root = materialize(after, root, Path(tmp), "after") if after else root
        b_rep, a_rep = analyze(b_root, entry, to), analyze(a_root, entry, to)
    res = compare(b_rep, a_rep)
    res.update(before_label=before, after_label=after or "目前內容", root=str(root), caveats=a_rep["caveats"])
    return res


# ─── 輸出 ────────────────────────────────────────────────────────────────────


def route_lines(r: dict) -> list:
    flags = ""
    if r["fan_in"] >= SHARED_FAN_IN:
        flags += f"（共用底層：{r['fan_in']} 處呼叫）"
    if not r["certain"]:
        flags += "（含候選）"
    if r["incomplete"]:
        flags += f"（未讀到底：落點有 {r['unresolved']} 個解析不了的呼叫）"
    lines = [f"  [{r['grade']}] 拐彎 {r['turns']}｜跳檔 {r['file_jumps']}｜轉手 {r['handoffs']}｜深度 {r['depth']}"
             f"  {r['entry']} → {r['landing']}{flags}"]
    for s in r["steps"]:
        tags = " ↗換檔" if s["jump"] else ""
        tags += f" ≋分檔有責任軸（依檔名推測）{s['axis']}" if s["axis"] else ""
        tags += f" ?{s['guess']}" if s["guess"] else ""
        lines.append(f"      {s['kind']:<9} {s['func']}{tags}")
    return lines


def render(report: dict, top: int) -> str:
    st = report["stats"]
    lines = [f"閱讀路徑｜{report['root']}｜Python {st['files']['py']}・C# {st['files']['cs']}・粗略 {st['files']['coarse']} 檔"
             f"｜函式 {st['funcs']}｜呼叫連到專案內 {st['linked_calls']}｜專案內解析不了 {st['unresolved']}",
             "尺不是判決：拐彎 0-1 順｜2 注意｜3 警戒｜≥4 臭掉（G11）。每個落點取拐彎最少的一條；拐彎＝轉手或換檔，一步最多算 1"]
    if st["unresolved_ratio"] > UNRESOLVED_WARN:
        lines.append(f"⚠ 專案內解析不了的呼叫占 {st['unresolved_ratio']:.0%}：圖可能缺邊，數字偏低不可信")
    if st["parse_errors"]:
        lines.append(f"解析失敗 {len(st['parse_errors'])} 檔：" + "、".join(st["parse_errors"][:5]))
    if st["empty_files"]:
        lines.append(f"⚠ 有定義卻解析出零函式 {len(st['empty_files'])} 檔：" + "、".join(st["empty_files"][:5]))
    lines += [f"分檔有責任軸（依檔名推測）：{name}（{'・'.join(axes)}），這些檔之間換檔不算彎，另計 axis_jumps"
              for name, axes in st["axis_classes"].items()]
    if report["caveats"]:
        lines.append("本次涉及的限制與可能誤報：")
        lines += [f"  - {c}" for c in report["caveats"]]
    entries = report["entries"]
    lines.append(f"入口 {len(entries)} 個（最差在前；刻度分布只算全確定且讀到底的路）：")
    for e in entries[:ENTRY_LIST_LIMIT]:
        dist = "・".join(f"{label} {n}" for label, n in reversed(e["grades"].items()))
        lines.append(f"  [{grade(e['max_turns'])}] {e['entry']}  落點 {e['landings']}｜最多拐彎 {e['max_turns']}"
                     f"｜最多跳檔 {e['max_file_jumps']}｜最多轉手 {e['max_handoffs']}｜{dist}"
                     f"｜含候選 {e['candidate']}（最多拐彎 {e['max_turns_candidate']}）｜未讀到底 {e['incomplete']}")
    if len(entries) > ENTRY_LIST_LIMIT:
        lines.append(f"  …另 {len(entries) - ENTRY_LIST_LIMIT} 個入口（--json 看全部）")
    routes = sorted(flat(e["routes"] for e in entries), key=worst_first)
    for title, group in (("全確定", [r for r in routes if r["certain"]]), ("含候選", [r for r in routes if not r["certain"]])):
        lines.append(f"最差 {min(top, len(group))} 條路徑（{title}）：")
        lines += list(flat(route_lines(r) for r in group[:top]))
    return "\n".join(lines)


def render_compare(res: dict, top: int) -> str:
    c, cc, sb, sa = res["counts"], res["counts_candidate"], res["stats_before"], res["stats_after"]
    lines = [f"前後比較｜{res['root']}｜before={res['before_label']} → after={res['after_label']}｜入口 {res['entries']}",
             "全確定：" + "｜".join(f"{STATUS_LABEL[k]} {c[k]}" for k in STATUS_ORDER)
             + f"｜最多拐彎 {res['max_turns_before']} → {res['max_turns_after']}",
             "含候選：" + "｜".join(f"{STATUS_LABEL[k]} {cc[k]}" for k in STATUS_ORDER),
             f"解析：失敗 {len(sb['parse_errors'])} → {len(sa['parse_errors'])} 檔｜專案內解析不了 "
             f"{sb['unresolved_ratio']:.0%} → {sa['unresolved_ratio']:.0%}"]
    if res["coverage_drop"]:
        lines.append("⚠ after 的解析涵蓋變差：「消失」「變好」可能是看不到了，不是程式變好")
    lines += [f"  不可判定的入口（可達範圍內解析不了的呼叫變多或換了地方）：{e}" for e in res["undecidable_entries"]]
    lines += [f"  從有函式變成零函式或解析失敗：{f}" for f in res["emptied_files"]]
    shown = 0
    for row in [r for r in res["rows"] if r["status"] != "same"]:
        b, a = row["before"] or {}, row["after"] or {}
        nums = "｜".join(f"{name} {b.get(k, '-')}→{a.get(k, '-')}"
                        for name, k in (("拐彎", "turns"), ("跳檔", "file_jumps"), ("轉手", "handoffs")))
        mark = "" if row["certain"] else "（含候選）"
        lines.append(f"  [{STATUS_LABEL[row['status']]}]{mark} {row['entry']} → {row['landing']}｜{nums}")
        if row["status"] in ("worse", "new") and shown < top:
            lines += route_lines(a)
            shown += 1
    return "\n".join(lines)


def done_line(report: dict) -> str:
    entries = report["entries"]
    routes = list(flat(e["routes"] for e in entries))
    grades = Counter(r["grade"] for r in routes if r["certain"] and not r["incomplete"])
    return (f"READING_PATH DONE entries={len(entries)} landings={len(routes)}"
            f" max_turns={max((e['max_turns'] for e in entries), default=0)}"
            f" max_turns_candidate={max((e['max_turns_candidate'] for e in entries), default=0)}"
            f" max_file_jumps={max((e['max_file_jumps'] for e in entries), default=0)}"
            f" max_handoffs={max((e['max_handoffs'] for e in entries), default=0)}"
            f" smelly={grades['臭掉']} alert={grades['警戒']} notice={grades['注意']}"
            f" candidate={sum(not r['certain'] for r in routes)} incomplete={sum(r['incomplete'] for r in routes)}"
            f" unresolved={report['stats']['unresolved']}")


def compare_done_line(res: dict) -> str:
    c = res["counts"]
    changed_candidate = sum(n for k, n in res["counts_candidate"].items() if k != "same")
    return (f"READING_PATH DONE mode=compare entries={res['entries']} better={c['better']} worse={c['worse']}"
            f" new={c['new']} gone={c['gone']} same={c['same']} undecidable={c['undecidable']}"
            f" candidate_changed={changed_candidate}"
            f" max_turns_before={res['max_turns_before']} max_turns_after={res['max_turns_after']}"
            f" coverage_drop={int(res['coverage_drop'])}")


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, epilog=LIMITS, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="專案根（預設目前目錄）")
    ap.add_argument("--entry", help="入口：檔路徑｜檔::函式｜函式名（Class.method）；不給就自動找")
    ap.add_argument("--to", help="只看落在這些函式的路徑（寫法同 --entry）")
    ap.add_argument("--top", type=int, default=3, help="全確定與含候選各列幾條最差路徑（預設 3；比較模式是列幾條變差／新增的路徑）")
    ap.add_argument("--before", help="前後比較的舊版本：git rev（--root 所在 repo）或目錄")
    ap.add_argument("--after", help="前後比較的新版本：git rev 或目錄（預設 --root 目前內容）")
    ap.add_argument("--json", action="store_true", help="輸出 JSON（含 caveats；最後一行仍是哨兵）")
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
