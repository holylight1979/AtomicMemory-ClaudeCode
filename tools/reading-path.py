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
確定與否：確定只來自白名單（見 --help 末段），白名單外一律候選（有可列舉的目標）或未解（沒有）。
  每條邊要由白名單其中一條正向證明才確定（--json 每一步的 rule＝憑第幾條；null＝不確定），不是「沒標不確定就算確定」。
  所以全確定的數字是可信的下限，含候選的數字是上限參考。每個落點先找只走確定邊的路；走不到才用含候選的路，
  彙總、最差 N 條與比較都分開列。落點裡有專案內但解析不了的呼叫 → 標「未讀到底」（數字是下限），不算進刻度分布。
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
UNTYPED_ANNOTATIONS = {"Any", "object"}   # 標了等於沒標型別：照沒標註往下判，不當成「指到專案外的型別」
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

WHITELIST = """確定只來自這幾種寫法（白名單）；其他一律候選或未解，所以全確定的數字是可信的下限，含候選的數字是上限參考：
  1. 直接呼叫專案內唯一解析到、名字從未被重新指定的函式（含 import 進來的、模組.函式、類別.靜態方法、建構子、super()／base.）；
     模組層名字只要在任何地方被重新指定或被指定成算出來的值，就不在白名單；名字是哪一層的哪個綁定只查一次
     （由內往外，遵守 global／nonlocal；指定、import、except … as、match 擷取、def／class 都算綁定），
     連到的目標與被證明沒改指的必須是同一個綁定；同一層同名 import 好幾次，每次都解析到同一個專案內目標才算唯一
  2. 對剛 new 出來的物件呼叫方法（確定型別分派）：Foo().run()，或同一函式內建構一次、之後每一次出現都只是
     方法呼叫接收者（w.m(…)）的區域變數：當引數、被指定給別的目標、放進容器、回傳、yield、del、w.x = …、
     讀 w.x 不呼叫，任何一種都失去資格；任何一次出現在巢狀作用域（def、lambda、生成器、推導式、類別本體）裡
     就算被捕捉，同樣失去資格；建構者的名字（含 import 別名）也要從未被重新指定
  3. self.method()／this.Method()（含 C# 省略 this）在沒有子類覆寫時；型別已宣告的接收者（參數標註、區域變數標註、
     欄位宣告型別；self.x = Foo() 這種推導出來的不算）同樣只在沒有子類覆寫、也沒有多載時
     （照讀的人順著標註往下讀的方式；型別標註寫錯時，這條會跟著錯）。self／cls 要真的是方法的第一個參數（區域變數
     剛好叫 cls 的不算）；接收者（含 self）被重新指定過（任何一次，含內層函式用 nonlocal 改寫）就不算型別已宣告。
     標註在它被求值的作用域解析：參數標註在 def 的外層（方法是類別本體、巢狀函式是外層函式、模組層函式是模組層），
     函式本體裡的標註（含 self.x: Foo）在那個本體，類別本體的標註在類別本體；那個作用域裡這個名字還有別的綁定
     （區域 import、指定、同名參數、類別屬性）就不給
  4. 簡單區域別名：同一函式內指定一次、之後沒再指定、右邊是白名單內可確定的函式
  5. callback：有已知呼叫者、每處都傳同一個白名單內的函式（或都用同一個預設值）、參數沒被重新指定
  類別證據（1、2、3 條的建構者、標註、欄位型別、類別.方法 的類別）只認沿綁定鏈（本檔定義、import 鏈、re-export、
  模組.類別）解析到專案內的類別：全專案同名搜尋只給候選；綁定鏈指到專案外（標準庫、typing、第三方）就是外部，
  連候選都不連到同名的專案類別（父類也照這個找）
  方法目標（1～4 條）還要方法在類別上的綁定沒被改寫：專案任何地方（含類別本體、巢狀類別）寫過 類別.方法 = …、
  self.方法 = …、實例.方法 = …、setattr(X, "方法", …)（字串字面值）、del、類別本體再指定，就不給條號；
  改寫照類別身分（定義檔＋名字）記，實例的型別看不出時，同名的方法都不給；經由被重新指定過的參數或區域變數寫入的，
  它原本的標註不再算數，也照型別看不出處理
  目標（1～5 條）被裝飾過：函式的裝飾器，或查找經過的類別（呼叫點寫出的類別，即建構的類別、接收者型別、類別.方法 的
  類別、super() 用到的父類，沿繼承鏈到實際定義方法的類別，整條鏈上）的類別裝飾器，有任何一個不在「保留原函式身分」
  清單裡，就不給條號（呼叫先進的是裝飾器給的東西）。清單：staticmethod、classmethod、abstractmethod、property 與
  它的 .setter／.getter／.deleter、typing（含 typing_extensions）的 overload／override／final；類別只有 dataclass；
  名字要沿綁定鏈確認就是那個內建或標準庫名字（import 別名先還原原名；import 之後又被改綁、自己定義的同名裝飾器都不算；
  .setter／.getter／.deleter 要同類別裡同名的方法真的是 @property）。類別白名單只保證類別身分：dataclass（init 不是
  寫死 False）本體沒自己的 __init__ 時建構式是它產生的，其他它會產生的方法（__eq__、__repr__…）本體沒定義也一樣，
  經過它的這些查找不給條號
  方法查找照 Python C3 MRO（多重繼承）：MRO 證不出（多重繼承裡有外部、未解或算出來的父類，或合併不出來）時，
  只有查到的就是呼叫點寫出的類別自己時才給；第 3 條還要每個子孫類別的 MRO 都證得出（它們的實例也會跑進這個呼叫）
  模型沒建參數與綁定的 Python 作用域構件（lambda、生成器、推導式、類別本體）：呼叫點在 lambda／生成器／推導式裡的，
  1～5 條一律不給；被證明的名字（第 1 條的名字或接收者開頭、第 4 條的別名）在查找會走過的函式裡、這類構件中被綁定
  （lambda 參數、推導式／生成器的迴圈目標、構件裡的 :=、類別本體裡的 global／nonlocal；只讀不算），也不給第 1、4 條
  （證明只在模型涵蓋的範圍內成立，不是假設那個構件不存在）
  不在白名單（例）：模組層可變名字、工廠回傳、事件（不論有沒有 -=）、多載、分派表、反射、getattr、繼承分派、接收者型別不明的猜測、粗略模式"""

NOT_WHITELISTED = "候選：不在確定白名單（名字綁定、型別來源或唯一目標證明不了）"
DECORATED = "候選：目標被保留身分清單以外的裝飾器包過，呼叫先進的是裝飾器給的東西，不一定是它"
KEEP_IDENTITY = {   # 函式裝飾器：保留原函式身分（呼叫還是進原函式）→ 可以出現在哪些模組
    "staticmethod": ("builtins",), "classmethod": ("builtins",), "property": ("builtins",),
    "abstractmethod": ("abc",), "overload": ("typing", "typing_extensions"),
    "override": ("typing", "typing_extensions"), "final": ("typing", "typing_extensions")}
CLASS_KEEP_IDENTITY = {"dataclass": ("dataclasses",)}   # 類別裝飾器（可以寫成 dataclass(…)）
PROPERTY_PARTS = {"setter", "getter", "deleter"}       # @name.setter：同類別裡同名的 @property 自己加的
DATACLASS_METHODS = {"__init__", "__repr__", "__eq__", "__lt__", "__le__", "__gt__", "__ge__", "__hash__",
                     "__setattr__", "__delattr__", "__getstate__", "__setstate__", "__replace__"}   # dataclass 可能自己產生的
GENERATED = "候選：dataclass 產生的建構式（或其他它產生的方法），模型沒建；不把繼承鏈上的同名方法當成確定目標"
MRO_UNPROVEN = "候選：方法解析順序（Python C3 MRO）證不出（多重繼承裡有外部、未解或算出來的父類，或合併不出來）"
SCOPED = "候選：呼叫點在 lambda／生成器／推導式裡，模型沒建那一層的參數與綁定，不給條號"
METHOD_REBOUND = "候選：這個方法在類別上的綁定可能被改寫（類別.方法 = …、self／實例.方法 = …、setattr），不一定是它"

LIMITS = WHITELIST + """

抓不到／可能偏差（數字是尺，判斷交給人）：
  - 每個落點只取拐彎最少的一條路（G11「重找最短路」的口徑）；同一落點更繞的路不列
  - 專案內但解析不了的呼叫（區域變數裝的函式、同名方法多個、找不到的 self 方法、getattr）計入未解，
    落點標「未讀到底」；確知在專案外的（內建、外部模組、外部父類、專案沒有同名方法）不算
  - 外部函式庫、框架回呼（Unity 生命週期以外）、反射、eval、動態 import 看不到；getattr 只認分派表來的
  - 事件一律候選（看不出實例、也不追訂閱與取消訂閱的先後）；callback 多處各傳不同函式、沒有已知呼叫者也標候選
  - 繼承分派只有接收者是剛 new 出來的物件才算確定型別；多載不比對參數型別，同名多個一律標候選
  - 沒有任何確定路徑的入口標「無法評級」，不以 0 彎、順呈現
  - 區域變數被指定超過一次：不追別名、不算確定型別、不算同一實例（寧可算未解或候選）
  - callback 與函式別名只追一層傳遞：函式被當參數再往下轉傳一次就斷；工廠函式回傳的閉包看不到（計入未解）
  - 閉包呼叫外層函式的參數或區域變數：沿外層的呼叫者傳了什麼、或它在外層指定成什麼列候選；沒有來源就記未解，
    不拿同名的模組層函式補邊
  - 「只轉傳」靠句數判定（換區域變數名不算句）：塞進無關計算就會被當成有內容
  - 同檔多層有實質內容的呼叫：深度高但不算彎（刻度只看拐彎）
  - Python：裝飾器包裝、@property、模組頂層（__main__ 以外）程式碼不追；monkeypatch 不追換成什麼，
    但寫過 模組.名字 = …、self.方法名 = …、類別.方法名 = …、實例.方法名 = …、setattr(X, "名", …) 的名字一律不算確定
    （實例型別看不出時，專案裡同名的方法都不算；測試檔裡的寫入也算）
  - 防線邊界（下列寫法不追，照字面處理，落在候選或未解）：exec／eval 產生的綁定、setattr 帶變數名、globals()[…] = …、
    metaclass 與 __getattr__、import 時的副作用（別的模組在 import 時改寫本模組的名字；上一條列的字面寫法除外）、
    C# 反射與 dynamic；模型沒建的 Python 作用域構件（lambda、生成器、推導式、類別本體）裡，一律不給條號
  - Python 標註（參數、回傳、變數標註）不產生呼叫邊，確定或候選都不給：標註可能延後求值或根本不求值
    （from __future__ import annotations、3.14 以後、函式裡的變數標註），裡面的呼叫不算；標註只當型別證據。預設值與裝飾器照常算呼叫
  - 被裝飾的函式或類別：函式的裝飾器，或呼叫點寫出的類別沿繼承鏈到定義方法的類別之間（含被繼承的方法、建構時用到的
    父類 __init__、super() 經過的父類、多層繼承的中間層）任一個類別裝飾器，不在保留原函式身分的清單裡（見白名單末段；
    functools.lru_cache、cache、contextmanager、自訂裝飾器都不在），呼叫它只給候選，包裝層（wrapper）裡做了什麼不追；
    呼叫裝飾器工廠 @deco(…) 本身照常判；functools.cached_property 有快取（之後取值不再執行原函式），維持候選
  - 已知降級：typing.overload 的「多個 @overload 宣告＋唯一實作」被當成同名重複綁定，呼叫它只給候選（沒辨識宣告與實作）
  - C#（不用 Roslyn）：擴充方法、LINQ、var 由方法回傳推型別、跨 namespace 同名類合併、lambda 裡的呼叫算外層函式、
    #if 不分支、運算子多載與索引子不認、接收者型別不明的屬性不猜、三元運算與 LINQ 不算分支、插值字串 {} 裡再套字串會漏；
    類別證據沒有 import 鏈可走（專案裡同名的類別就當那個型別，分不出外部同名型別）；第 2 條的用途證明只數文字出現，
    lambda 裡的 w.M( 也算方法呼叫
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
    guess: str = ""      # 為什麼不確定（說明用）；確定與否只看 rule
    via: str = ""        # object：經由別的物件轉交（落點若只轉傳 → delegate）
    rule: int | None = None   # 給它確定的白名單條號 1～5；只有 Graph 的「確定白名單」那一段能填，其他一律 None＝不確定


@dataclass
class Binding:
    """callback 參數的來源。refs＝[(語境函式, 函式參照)]；blind＝有看不到的來源；mixed＝混了 lambda／常數；callers＝已知呼叫處數。"""
    refs: list
    blind: bool
    mixed: bool
    callers: int


@dataclass
class Step:
    func: str
    kind: str            # entry｜direct｜wrapper｜delegate｜callback｜event｜inherit｜dynamic
    jump: bool = False
    axis: str = ""       # 分檔有責任軸時的「責任→責任」
    guess: str = ""
    rule: int | None = None   # 這一步憑白名單第幾條確定；None＝不確定（入口那一步也是 None，不算進確定與否）

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
                "certain": all(s.rule is not None for s in moves), "incomplete": self.unresolved > 0,
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
    """有 BOM 照 BOM（UTF-8／UTF-16 LE／BE）；沒 BOM 先看前 4KB 的 NUL 分布：奇數位置大量 NUL → UTF-16 LE、
    偶數位置 → UTF-16 BE；否則嚴格 UTF-8。解不開、或有 NUL 卻判不出編碼 → 丟例外（列進解析失敗，不靜默替換）。"""
    data = path.read_bytes()
    boms = ((codecs.BOM_UTF8, "utf-8-sig"), (codecs.BOM_UTF16_LE, "utf-16"), (codecs.BOM_UTF16_BE, "utf-16"))
    encoding = next((enc for bom, enc in boms if data.startswith(bom)), "")
    head = data[:4096]
    odd, even = head[1::2].count(0), head[0::2].count(0)
    if not encoding and (odd or even):
        half = max(1, len(head) // 2)
        encoding = "utf-16-le" if odd > half * 0.3 > even else "utf-16-be" if even > half * 0.3 > odd else ""
        if not encoding:
            raise ValueError("檔裡有 NUL 位元組卻判不出編碼")
    return data.decode(encoding or "utf-8")


# ─── 偵測器：每一種轉手各一個（反證測試會一次拿掉一個） ─────────────────────


def override_targets(g: "Graph", cls: lang.Cls, name: str) -> list:
    """cls 的實例實際可能跑到、但不是 cls 自己查到的 name 實作：繼承／介面分派可能跑到的地方。
    Python：每個子孫類別照它自己的 C3 MRO 找到的第一個 name：子類覆寫，或多重繼承時排在前面的兄弟 mixin；
    單一繼承就是子孫自己的覆寫。C#：子孫自己的覆寫。"""
    if cls.lang != "py":
        return [fid for fid in flat(sub.methods.get(name, []) for sub in g.descendants(cls)) if not g.funcs[fid].abstract]
    own = set(g.lookup(cls, name))
    reached = [fid for sub in g.descendants(cls) for fid in g.lookup(sub, name) if fid not in own]
    return [fid for fid in dict.fromkeys(reached) if not g.funcs[fid].abstract]


def c3_merge(seqs: list):
    """Python C3 線性化的合併步驟（用物件身分比）：每次取第一個不出現在任何序列尾端的頭；合併不出來（順序衝突）→ None。"""
    seqs = [list(s) for s in seqs if s]
    out = []
    while seqs:
        tails = {id(x) for s in seqs for x in s[1:]}
        head = next((s[0] for s in seqs if id(s[0]) not in tails), None)
        if head is None:
            return None
        out.append(head)
        seqs = [s for s in (s[1:] if s[0] is head else s for s in seqs) if s]
    return out


def callback_targets(g: "Graph", bind_fid: str, param: str) -> list:
    """bind_fid 的參數 param 被當函式呼叫：找所有呼叫 bind_fid 的地方，那個位置傳進來的是哪個函式
    → [(func id, 那個參照在呼叫者語境的白名單條號或 None, 不確定原因)]；白名單 5 要每個來源都確定。"""
    out = []
    for caller, ref in g.bound_refs(bind_fid, param).refs:
        out += [(e.dst, e.rule, e.guess) for e in g.resolve(caller, ref, defer=False)]
    return out


def event_targets(g: "Graph", f: lang.Func, c: lang.Call) -> list:
    """訂閱了同名事件的處理函式 → [(func id, 處理函式本身的不確定原因)]。事件不在確定白名單：
    看不出是哪個實例發的、也不追訂閱、取消訂閱、觸發的先後，所以連線一律是候選。"""
    out = []
    for key, ref, owner, file, _recv in g.subs:
        if key == c.name and g.same_side(f, file):
            ctx = g.funcs.get(owner) or g.module_ctx(file)
            out += [(e.dst, e.guess) for e in g.resolve(ctx, ref, defer=False)]
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
        self._index_rebinds(modules)
        self._mro_memo = {}        # id(類別) → (C3 順序, 證得出否, 一路到頂都解析得到否)；綁定都建好之後才算
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
            for base in c.bases:                       # 子孫照父類名字最後一段收（同名都算：覆寫判斷寧可多）
                self.children[base.rpartition(".")[2]].append(c)
            for name, ids in c.methods.items():
                self.by_method[name].extend(ids)

    def _index_rebinds(self, modules: list) -> None:
        """在別處被改掉的綁定（綁定穩定的判斷要看）：
        rebound_elsewhere (檔, 名字)：別的程式碼用 模組.名字 = … 改掉的模組層名字；
        method_writes (類別身分或 "*", 屬性名)：會蓋掉同名方法的屬性寫入；類別身分＝(定義檔, 類別名)，
        "*"＝接收者型別看不出，專案裡同名的方法都算；
        nonlocal_rebound (檔, 外層作用域) → 名字：巢狀函式用 nonlocal 改掉的名字，只標在真正持有它的那一層
        （巢狀類別本體或它的方法裡的 nonlocal，從包住那個類別的函式自己這一層往外找）。"""
        self.rebound_elsewhere, self.method_writes, self.nonlocal_rebound = set(), set(), defaultdict(set)
        for f in [f for f in self.funcs.values() if f.nonlocal_writes]:
            for name in f.nonlocal_writes:
                owner = self._nonlocal_owner(f, name)
                if owner is not None:
                    self.nonlocal_rebound[(f.file, owner.qual)].add(name)
        for f in [f for f in self.funcs.values() if f.class_nonlocals]:
            for name in f.class_nonlocals:
                owner = self.lookup_binding(f, name)[1]
                if owner is not None:
                    self.nonlocal_rebound[(f.file, owner.qual)].add(name)
        contexts = [(f, f.attr_stores) for f in self.funcs.values()]
        contexts += [(self.module_ctx(m.file), m.attr_stores) for m in modules if m.lang == "py"]
        for f, stores in contexts:
            for recv, attr in stores:
                self._note_attr_store(f, recv, attr)

    def _nonlocal_owner(self, f: lang.Func, name: str):
        """f 裡 nonlocal name 改的是哪一層：從 f 的外層函式往外，第一個綁定它的作用域（lookup_binding 同一套規則）。"""
        scopes = self.scopes(f)
        parent = self.funcs.get(f"{f.file}::{scopes[-2]}") if len(scopes) > 1 else None
        return self.lookup_binding(parent, name)[1] if parent else None

    @staticmethod
    def cls_key(cls) -> tuple:
        """類別身分：(定義檔, 類別名)；不同模組的同名類別分得開。"""
        return cls.files[0], cls.name

    def _note_attr_store(self, f: lang.Func, recv: str, attr: str) -> None:
        """一筆 Python 屬性寫入（含 setattr 字面寫法、del、類別本體再指定）記到它會蓋掉的綁定：
        self／cls.名 → 這個類別；模組.名 → 那個模組的名字；類別.名、剛 new 的或有標註的實例.名 → 沿綁定鏈確知的那個類別；
        型別看不出（或類別只靠全專案同名搜尋）的接收者 → 用名字保守判定；接收者確知在專案外 → 不影響專案的方法。
        接收者（含 self）被重新指定過，型別證據就失效（總原則 4），照型別看不出的規則用名字判。"""
        if f.lang != "py":
            return
        own = self.cls_of(f) if recv in ("self", "cls") and self._own_receiver(f, recv) else None
        if own:
            self.method_writes.add((self.cls_key(own), attr))
            return
        head = recv.partition(".")[0]
        target = self.module_alias(f, recv) if recv != "?" and not self._shadowed(f, head) else None
        if target:
            self.rebound_elsewhere.add((target, attr))
            return
        if recv != "?" and self.recv_type(f, recv)[0] == "external":
            return
        cls = self._written_class(f, recv)
        self.method_writes.add((self.cls_key(cls) if cls else "*", attr))

    def _written_class(self, f: lang.Func, recv: str):
        """屬性寫入的接收者沿綁定鏈確知是哪個專案類別：類別名本身、剛 new 的區域變數、有標註的參數或區域變數；
        其他（欄位鏈、算出來的、指定好幾次、只靠同名搜尋）→ None。"""
        if "." in recv or recv == "?" or self.rebound_local(f, recv):
            return None
        if recv in f.constructed:
            ctx, typed = f, f.constructed[recv]
        elif recv in f.param_types:
            ctx, typed = self.outer_ctx(f), f.param_types[recv]   # 參數標註在 def 的外層解析
        elif recv in f.declared:
            ctx, typed = f, f.declared[recv]
        elif recv not in f.locals and recv not in f.params:
            ctx, typed = f, recv                       # 類別.名 = …
        else:
            return None
        cls, src = self.class_lookup(ctx, typed)
        return cls if src == "project" else None

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
        same.declared_fields.update(c.declared_fields)
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

    def class_lookup(self, f: lang.Func, name: str) -> tuple:
        """f 裡寫成 name 的類別（建構者、型別標註、欄位型別、類別.方法 的類別）沿綁定鏈解析 → (類別或 None, 來源)。
        來源：project＝沿本檔定義、import 鏈、re-export、模組.類別 解析到專案內的類別；external＝綁定鏈指到專案外
        （標準庫、第三方：import 的模組不在專案內）；unknown＝綁定鏈解不出（參數、區域變數、沒匯入的名字、不是類別）。
        C# 沒有 import 鏈（不用 Roslyn，namespace 也不分）：本檔或全專案同名的類別就算 project。"""
        if f.lang != "py":
            cls = next((c for c in self.classes.get(name, []) if f.file in c.files), None) or self.cls_named(name, f.file)
            return cls, "project" if cls else "unknown"
        if "." in name:                            # worker.Worker：模組.類別
            prefix, _, last = name.rpartition(".")
            if self._shadowed(f, prefix.partition(".")[0]):
                return None, "unknown"
            target = self.module_alias(f, prefix)
            if target:
                return self._class_at(target, last, 1)
            return None, "external" if self._external_import(f, prefix) else "unknown"
        kind, owner = self.lookup_binding(f, name)
        if kind == "import":
            return self._class_via_import(f.file, owner.imports, name, 0)
        return self._class_at(f.file, name, 0) if kind == "module" else (None, "unknown")

    def _class_at(self, file: str, name: str, hops: int) -> tuple:
        """模組 file 的模組層名字 name 是哪個類別：本檔定義的，或沿 from 匯入追 re-export。"""
        mod = self.modules.get(file)
        if mod is None or hops > MAX_REEXPORT:
            return None, "unknown"
        local = next((c for c in self.classes.get(name, []) if file in c.files), None)
        if local:
            return local, "project"
        return self._class_via_import(file, mod.imports, name, hops) if name in mod.imports else (None, "unknown")

    def _class_via_import(self, file: str, imports: dict, name: str, hops: int) -> tuple:
        modname, level, orig = imports.get(name, ("", 0, ""))
        if not orig:
            return None, "unknown"                 # import x：名字是模組，不是類別
        src = self.find_module(modname, level, file)
        if src is None:
            return None, "external" if self._outside(modname, level) else "unknown"
        return self._class_at(src, orig, hops + 1) if src != file else (None, "unknown")

    def _outside(self, modname: str, level: int) -> bool:
        """import 的模組確知不在專案內（絕對 import、專案裡沒有這個模組名）；同名模組多個、相對 import 解不到 → 不算確知。"""
        return level == 0 and not self.mod_index.get(modname)

    def _external_import(self, f: lang.Func, dotted: str) -> bool:
        """dotted（pathlib、os.path、typing）開頭的名字綁定到專案外模組的 import。"""
        imports = self.imports_for(f, dotted.partition(".")[0])
        key = dotted if dotted in imports else dotted.partition(".")[0]
        return key in imports and self._outside(imports[key][0], imports[key][1])

    def _type_external(self, f: lang.Func, name: str) -> bool:
        """型別寫法沿綁定鏈指到專案外（pathlib.Path、typing.Mapping、第三方）：不連到同名的專案類別。
        typing.Any 這種「沒有型別」的標註不算，照沒標註往下判。"""
        return name.rpartition(".")[2] not in UNTYPED_ANNOTATIONS and self.class_lookup(f, name)[1] == "external"

    def class_ref(self, f: lang.Func, name: str):
        """找目標用的類別：沿綁定鏈（class_lookup）；綁定鏈指到專案外 → None（不連到同名的專案類別）；
        Python 裸名的綁定鏈解不出來，才退回全專案同名的類別，那只是候選，確定要用 class_proof。"""
        cls, src = self.class_lookup(f, name)
        if cls or src == "external" or "." in name or f.lang != "py":
            return cls
        return self.cls_named(name, f.file)

    def class_proof(self, f: lang.Func, name: str):
        """確定白名單用的類別證據：沿綁定鏈解析到專案內的類別，而且沿途的名字都綁定穩定
        （Foo → stable(Foo)；worker.Foo → 模組名穩定、模組裡的 Foo 也穩定）；全專案同名搜尋、外部、不穩定 → None。"""
        cls, src = self.class_lookup(f, name)
        if src != "project":
            return None
        if "." not in name or f.lang != "py":
            return cls if self.stable(f, name) else None
        prefix, _, last = name.rpartition(".")
        target = self.module_alias(f, prefix)
        return cls if self.stable(f, prefix.partition(".")[0]) and self._stable_in(target, last, 0) else None

    def base_of(self, c, base: str):
        """類別 c 的父類 base：Python 在 c 所在的檔沿綁定鏈解析（含 collections.UserDict 這種模組前綴），而且名字穩定
        （class_proof）；全專案同名搜尋、外部、解析不了 → None（當成外部父類：繼承來的方法看不到）；C# 照名字找。
        找目標與白名單（lookup、super）都只走這條鏈。"""
        if c.lang == "py":
            return self.class_proof(self.module_ctx(c.files[0]), base)
        return self.cls_named(base, c.files[0])

    def ancestry(self, cls):
        """cls 自己與所有祖先（廣度優先，同一類只走一次）。"""
        seen, queue = set(), [cls]
        while queue:
            c = queue.pop(0)
            if c is None or id(c) in seen:
                continue
            seen.add(id(c))
            yield c
            queue.extend(self.base_of(c, b) for b in c.bases)

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
        """照方法解析順序（mro），第一個定義 name 的類別裡的那些方法。"""
        return next((c.methods[name] for c in self.mro(cls)[0] if name in c.methods), [])

    def mro(self, cls) -> tuple:
        """cls 的方法解析順序裡的專案類別 → (類別串列, 證得出否)。
        Python 照 C3：單一繼承一路往上，父類解析不到（外部、未解、算出來的運算式）就停在那裡，前面那段照樣證得出，
        後面不會再有專案類別；多重繼承要每個父類都是專案內類別、它們一路到頂都沒有解析不到的父類、C3 合併成功，
        才算證得出，否則照合併得出的順序（合併失敗就退回廣度優先）給找目標用、標證不出。明寫的 object 父類不算。
        C# 照父類鏈（廣度優先），不用 C3。"""
        if cls is None:
            return [], True
        if cls.lang != "py":
            return list(self.ancestry(cls)), True
        return self._linearize(cls)[:2]

    def _linearize(self, cls) -> tuple:
        """Python 類別的 (C3 順序, 證得出否, 一路到頂都解析得到否)；算過的記下來，繼承循環當證不出。"""
        key = id(cls)
        if key in self._mro_memo:
            return self._mro_memo[key]
        self._mro_memo[key] = ([cls], False, False)
        names = [b for b in cls.bases if b != "object"]
        bases = [self.base_of(cls, b) for b in names]
        if len(names) + cls.opaque_bases <= 1:          # 單一繼承
            if not bases or bases[0] is None:
                result = [cls], True, not names and not cls.opaque_bases
            else:
                order, proven, whole = self._linearize(bases[0])
                result = [cls] + order, proven, whole
        else:
            known = [b for b in bases if b is not None]
            lins = [self._linearize(b) for b in known]
            merged = c3_merge([order for order, _, _ in lins] + [known])
            proven = (merged is not None and len(known) == len(names) and not cls.opaque_bases
                      and all(p and w for _, p, w in lins))
            result = ([cls] + merged if merged is not None else list(self.ancestry(cls))), proven, proven
        self._mro_memo[key] = result
        return result

    def external_base(self, cls) -> bool:
        """類別（含祖先）有不在專案裡的父類：找不到的方法可能是從那裡繼承來的。沒有類別也當外部。"""
        if cls is None:
            return True
        for c in self.ancestry(cls):
            if any(self.base_of(c, b) is None for b in c.bases):
                return True
        return False

    def _field_decl(self, cls, attr: str, table: str = "fields"):
        """欄位寫的型別（沿繼承鏈找）→ (解析它的語境, 型別寫法) 或 None；table＝declared_fields 時只認宣告的。
        語境照型別證據寫在哪裡（總原則 3）：類別本體的標註在類別本體解析，方法裡的 self.x: Foo／self.x = Foo() 在那個方法的本體。"""
        owner = next((c for c in self.ancestry(cls) if attr in getattr(c, table)), None)
        if owner is None:
            return None
        scope = (owner.declared_scope if table == "declared_fields" else owner.field_scope).get(attr, "")
        return self.funcs.get(scope) or self.class_body_ctx(owner), getattr(owner, table)[attr]

    def outer_ctx(self, f: lang.Func) -> lang.Func:
        """f 的 def 在哪個作用域執行（參數標註與參數預設值在這裡求值，Python 語意）：巢狀函式 → 外層函式；
        方法 → 類別本體（本體綁定的名字遮住外面的，之後才是模組層）；模組層函式 → 模組層。C# 沒有這個分別，就是 f。"""
        if f.lang != "py":
            return f
        scopes = self.scopes(f)
        if len(scopes) > 1:
            return self.funcs.get(f"{f.file}::{scopes[-2]}") or self.module_ctx(f.file)
        cls = self.cls_of(f)
        return self.class_body_ctx(cls) if cls else self.module_ctx(f.file)

    def class_body_ctx(self, cls) -> lang.Func:
        """類別本體當解析語境：本體綁定的名字（方法、指定、import、巢狀類別…）是這一層的區域綁定（裝的是什麼不追），
        其他照模組層找。C# 沒有這個分別，就是類別所在檔的模組層。"""
        file = cls.files[0]
        if cls.lang != "py":
            return self.module_ctx(file)
        qual = f"<class {cls.name}>"
        return lang.Func(f"{file}::{qual}", file, qual, qual, "", "py", 0, locals=set(cls.body_names))

    def field_type(self, cls, attr: str):
        """找目標用：欄位的型別（宣告的與 self.x = Foo() 推導的都算；類別照 class_ref）。"""
        decl = self._field_decl(cls, attr)
        return self.class_ref(*decl) if decl else None

    def declared_field(self, cls, attr: str):
        """白名單 3 用：只認宣告的欄位型別，而且型別沿綁定鏈解析到專案內的類別（class_proof）。"""
        decl = self._field_decl(cls, attr, "declared_fields")
        return self.class_proof(*decl) if decl else None

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

    def lookup_binding(self, f: lang.Func, name: str) -> tuple:
        """Python 函式 f 裡寫成 name 的名字由哪個作用域的哪個綁定提供 → (種類, 綁定所在的函式；模組層為 None)。
        種類：param 參數｜nested 巢狀 def｜local 區域變數｜import 函式裡自己 import 的｜module 模組層（def、class、別名、import，或沒綁定）。
        由內往外找第一個綁定它的函式作用域（類別本體不算作用域）；某一層宣告 global name → 直接跳模組層，
        宣告 nonlocal name → 那一層不算、往外層找。找目標（_r_name、module_alias、類別證據）與證明穩定（stable）
        都只看這一次查找的結果，兩邊才不會各自找到不同的綁定。"""
        for scope in reversed(self.scopes(f)):
            owner = self.funcs.get(f"{f.file}::{scope}") or (f if scope == f.qual else None)   # 沒登記的語境（類別本體）看它自己
            if owner is None or name in owner.nonlocal_names:
                continue
            if name in owner.global_names:
                return "module", None
            kind = self._bound_in(owner, name)
            if kind:
                return kind, owner
        return "module", None

    def _bound_in(self, owner: lang.Func, name: str) -> str:
        """name 在 owner 這一層怎麼綁定；同一層綁了好幾種時取一種（那種情況 stable 會因 reassigned／import_rebinds 不穩定）。"""
        if name in owner.params:
            return "param"
        if f"{owner.id}.{name}" in self.funcs:
            return "nested"
        if name in owner.locals:
            return "local"
        if name in owner.imports or any(k.partition(".")[0] == name for k in owner.imports):
            return "import"
        return ""

    def imports_for(self, f: lang.Func, name: str) -> dict:
        """name 的綁定（lookup_binding）所在那一層的 import 表：函式自己的或模組層的；被參數、區域變數、巢狀 def 遮住 → {}。"""
        if f.lang != "py":
            return {}
        kind, owner = self.lookup_binding(f, name)
        if kind == "import":
            return owner.imports
        return self.modules[f.file].imports if kind == "module" and f.file in self.modules else {}

    def module_alias(self, f: lang.Func, dotted: str):
        """f 裡寫成 dotted 的接收者（w2、pkg.w2、a.b）是不是專案內的模組 → 模組檔或 None。
        看的是開頭那個名字的綁定（lookup_binding）所在那一層的 import。"""
        imports = self.imports_for(f, dotted.partition(".")[0])
        key = dotted if dotted in imports else dotted.partition(".")[0]
        if key not in imports:
            return None
        modname, level, orig = imports[key]
        full = ".".join(p for p in (modname, orig, dotted[len(key) + 1:]) if p)
        return self.find_module(full, level, f.file)

    def bound_refs(self, bind_fid: str, param: str) -> "Binding":
        """呼叫 bind_fid 的每個地方，param 那個位置傳進來的是什麼。
        具名函式 → 參照；lambda、常數 → 混了別種來源（內容在呼叫者裡）；算出來的值、被 *args／**kw 展開蓋到 → 看不到；
        沒傳 → 預設值（具名函式當參照，算出來的看不到；在定義所在的外層作用域解析）。
        Python 方法經由物件呼叫時第一個參數是 self，位置要扣掉。"""
        f = self.funcs[bind_fid]
        offset = 1 if f.lang == "py" and f.cls and f.params[:1] in (["self"], ["cls"]) else 0
        pos = f.params.index(param) - offset
        callers = [(caller, call) for caller, call in self.callers.get(bind_fid, []) if self.same_side(f, caller.file)]
        default = [(self.outer_ctx(f), f.defaults[param])] if param in f.defaults else []
        refs, unknown, mixed = [], not callers and param in f.blind_defaults, False
        for caller, call in callers:
            state = self._arg_at(call, pos, param)
            hit = [(caller, ref) for key, ref in call.refs if key in (pos, param)] if state == "given" else default
            unknown = unknown or state in ("blind", "spread") or (state == "absent" and param in f.blind_defaults)
            mixed = mixed or (state == "given" and not hit)
            refs += hit if state in ("given", "absent") else []
        return Binding(refs + (default if not callers else []), unknown, mixed, len(callers))

    @staticmethod
    def _arg_at(call: lang.Call, pos: int, param: str) -> str:
        """呼叫處在這個參數傳了什麼：given 有傳｜blind 傳算出來的值｜spread 被 *args／**kw 展開蓋到｜absent 沒傳（用預設值）。"""
        if pos in call.blind or param in call.blind:
            return "blind"
        limit = call.nargs if call.star < 0 else call.star
        if 0 <= pos < limit or param in call.kwargs:
            return "given"
        return "spread" if (0 <= call.star <= pos) or call.dstar else "absent"

    def same_side(self, f: lang.Func, other_file: str) -> bool:
        """非測試碼不採用測試檔傳進來的假函式、訂閱的處理函式（那只在跑測試時存在）。"""
        return is_test(f.file) or not is_test(other_file)

    def module_ctx(self, file: str) -> lang.Func:
        """模組層（函式外）的訂閱與分派表，用一個假函式當解析的語境。"""
        lang_name = self.modules[file].lang if file in self.modules else "py"
        return lang.Func(f"{file}::<module>", file, "<module>", "<module>", "", lang_name, 0)

    # 解析：一個呼叫點連到哪些函式 ─────────────────────────

    def resolve(self, f: lang.Func, c: lang.Call, defer: bool = True) -> list:
        """找目標（各解析路）→ 定確定與否（certify，唯一能給確定的地方）。"""
        c = self._plain_self(f, c)
        handler = {"name": self._r_name, "self": self._r_self, "super": self._r_super, "attr": self._r_attr,
                   "new": self._r_new, "emit": self._r_emit, "invoke": self._r_invoke, "table": self._r_table,
                   "getattr": self._r_getattr, "prop": self._r_prop, "opaque": lambda *_: []}
        return self.certify(f, c, handler[c.kind](f, c, defer))

    def _plain_self(self, f: lang.Func, c: lang.Call) -> lang.Call:
        """Python 寫成 self.m()／cls.m()，但接收者不是方法自己的第一個參數（區域變數剛好叫 cls、self 被重新指定過）→
        當成一般的屬性呼叫 recv.m()（照接收者的型別證據找，不連本類別的同名方法）；其他照原樣。"""
        if c.kind != "self" or f.lang != "py" or self._own_receiver(f, c.recv or "self"):
            return c
        return lang.Call("attr", c.name, recv=c.recv or "self", line=c.line, scoped=c.scoped)

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

    def _defer(self, src: lang.Func, bind: tuple, defer: bool, flag: str = "") -> list:
        """callback 等所有呼叫者都連好再解：記下 (呼叫的函式, 綁定的函式, 參數名, 旗標)。
        旗標：reassigned＝參數在函式裡被重新指定；stored＝經由欄位存下的 callback（欄位可能被換）；
        scoped＝呼叫點在 lambda／生成器／推導式裡；closure＝巢狀函式呼叫外層函式的參數；空＝直接呼叫參數。"""
        if defer:
            self.pending.append((src.id, *bind, flag))
        return []

    def _param_call(self, f, c, defer, caller=None) -> list:
        """呼叫 f 的參數 cb()：等 f 的呼叫者傳了什麼；參數被重新指定過（cb = alternate、import 改綁、內層 nonlocal 改寫）
        → 傳進來的和改指的都只是候選。caller＝呼叫點所在的函式，不是 f 時是閉包（巢狀函式呼叫外層 f 的參數，只列候選）。"""
        if f.cls and c.name == "cls" and f.params[:1] == ["cls"]:
            return self.dispatch(self.cls_of(f), "__init__")   # classmethod 的 cls(...)：子類呼叫時建構的是子類，有覆寫就是候選
        shaky = self.rebound_local(f, c.name)
        ref = f.aliases.get(c.name) if shaky else None
        reason = f"候選：參數 {c.name} 在函式 {f.qual} 裡被重新指定"
        edges = [Edge(e.dst, e.kind, guess=reason) for e in self.resolve(f, ref, defer=False)] if ref else []
        flag = "closure" if caller else "scoped" if c.scoped else "reassigned" if shaky else ""
        return edges + self._defer(caller or f, (f.id, c.name), defer, flag)

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
        if f.lang == "py":
            return self._r_py_name(f, c, defer)
        if c.name in f.params:
            return self._param_call(f, c, defer)
        if c.name in f.aliases:
            ref = self.alias_target(f, c.name)
            return self.resolve(f, ref, defer) if ref else []
        if c.name in f.locals or c.name in f.reassigned:
            return []                              # 區域變數裝的東西（遮住同名的方法）：看不到
        if f.lang == "coarse":
            return self._coarse(f, c.name)
        return self._r_self(f, c, defer) or self._static_using(f, c.name)   # C#：本類別的方法／事件／委派欄位，或 using static

    def _r_py_name(self, f, c, defer):
        """Python 裸名呼叫：先問 lookup_binding 是哪一層的哪個綁定，再照那個綁定找目標（證明穩定看的是同一個綁定）。
        名字是包住呼叫點的 lambda 參數或推導式迴圈變數（模型沒建那一層）→ 裝的東西看不到，不退回外層同名的名字。"""
        if c.shadowed:
            return []
        binding = self.lookup_binding(f, c.name)
        kind, owner = binding
        if owner is f and kind == "param":
            return self._param_call(f, c, defer)
        if (owner is f and kind == "local") or c.name in f.nonlocal_writes:
            return self._r_local(f, c, defer)      # 自己指定的（含 nonlocal 改寫外層的）：看自己指定了什麼
        if owner is f and c.name in f.reassigned:
            return []                              # 自己這一層綁了兩次（巢狀 def 寫兩次）：看不到是哪個
        if kind == "param":                        # 外層函式的參數（閉包）：沿外層的呼叫者傳了什麼（與外層改指的）列候選，沒有來源就記未解
            return self._param_call(owner, c, defer, caller=f)
        if kind == "local":                        # 外層函式的區域變數（閉包）：沿它在外層的指定（函式別名、分派表）列候選
            reason = f"候選：{c.name} 是外層函式 {owner.qual} 的區域變數（閉包），沿它在外層的指定列出，呼叫時可能已被改指"
            return [Edge(e.dst, e.kind, guess=e.guess or reason) for e in self._r_local(owner, c, False)]
        return self._binding_edges(f, c.name, binding)

    def _r_local(self, f, c, defer):
        """自己這一層的區域變數：函式別名 → 追到真正的函式；分派表變數 → 表裡的項目；其他裝的東西看不到。"""
        if c.name in f.aliases:
            ref = self.alias_target(f, c.name)
            return self.resolve(f, ref, defer) if ref else []
        if c.name in f.table_vars:
            return self._r_table(f, lang.Call("table", f.table_vars[c.name]), defer)
        return []

    def _binding_edges(self, f: lang.Func, name: str, binding: tuple) -> list:
        """綁定是巢狀 def、函式裡的 import、模組層名字時，它指到的函式（建構類別 → 建構子）；其他綁定 → []。"""
        kind, owner = binding
        if kind == "nested":
            return [Edge(f"{owner.id}.{name}", "direct")]
        if kind == "import":
            src, orig = self._imported_from(f.file, owner.imports, name)
            return self._py_name(src, orig, 1) if src else []
        return self._py_name(f.file, name) if kind == "module" else []

    def _static_using(self, f: lang.Func, name: str) -> list:
        """C# `using static 專案類別;` 之後的裸名呼叫：所有靜態匯入的類別裡同名的方法都算，多於一個就標候選。"""
        usings = self.modules[f.file].static_usings if f.file in self.modules else []
        classes = [c for c in (self.cls_named(t.split(".")[-1], f.file) for t in usings) if c]
        return self._overloads(list(flat(self.lookup(c, name) for c in classes)))

    def _r_self(self, f, c, defer):
        cls = self.cls_of(f)
        if cls is None:
            return []
        hits = self.dispatch(cls, c.name)
        if hits:
            return hits
        stored = self.stored_param(cls, c.name)
        if stored:
            return self._defer(f, stored, defer, "stored")
        return self._r_emit(f, c, defer) if any(c.name in x.events for x in self.ancestry(cls)) else []

    def _r_super(self, f, c, defer):
        """super()／base.：直接連父類的實作，不展開子類覆寫（那正是呼叫者自己）。Python 照所在類別的 C3 MRO、
        在它自己後面找第一個實作；C# 照父類順序。"""
        cls = self.cls_of(f)
        if f.lang == "py":
            order = self.mro(cls)[0][1:] if cls else []
            return self._overloads(next((k.methods[c.name] for k in order if c.name in k.methods), []))
        bases = [self.base_of(cls, b) for b in (cls.bases if cls else [])]
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
        reason = "候選：事件只按名字配對，看不出實例與訂閱是否還在"
        return [Edge(t, "event", guess=guess or reason) for t, guess in event_targets(self, f, c)]

    def _r_invoke(self, f, c, defer):
        """C# 的 X.Invoke()／X?.Invoke()：X 是參數、別名或建構時存下的委派 → callback；否則當事件。"""
        if c.name in f.params:
            return self._param_call(f, c, defer)
        if c.name in f.aliases:
            ref = self.alias_target(f, c.name)
            return self.resolve(f, ref, defer) if ref else []
        stored = self.stored_param(self.cls_of(f), c.name) if f.cls else None
        return self._defer(f, stored, defer, "stored") if stored else self._r_emit(f, c, defer)

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

    def _py_name(self, file: str, name: str, hops: int = 0) -> list:
        """Python 模組 file 的模組層名字 name：本檔函式、本檔類別（建構）、別名、from 匯入的函式或類別（追 re-export）。
        被重新指定過的名字不在確定白名單。"""
        mod = self.modules.get(file)
        if mod is None or hops > MAX_REEXPORT:
            return []
        return self._py_rebound(mod, name, hops) if self._rebound(mod, name) else self._py_bound_once(mod, name, hops)

    def _py_bound_once(self, mod: lang.Module, name: str, hops: int) -> list:
        """模組層只綁定一次的名字：本檔函式、本檔類別（建構）、別名、from 匯入的函式或類別。"""
        if name in mod.defs:
            return [Edge(mod.defs[name], "direct")]
        local_cls = next((c for c in self.classes.get(name, []) if mod.file in c.files), None)
        if local_cls:
            return self._ctor(local_cls)
        if name in mod.aliases:
            return list(flat(self._py_alias(mod.file, ref, hops + 1) for ref in mod.aliases[name]))
        src, orig = self._imported_from(mod.file, mod.imports, name)
        return self._py_name(src, orig, hops + 1) if src else []

    def _py_rebound(self, mod: lang.Module, name: str, hops: int) -> list:
        """模組層被重新指定的名字：被指定成算出來的值（或被 global 改寫）→ 看不到（未解）；
        都指向可列舉的函式（def、import、別名）→ 全部連上並標候選。"""
        if name in mod.opaque:
            return []
        reason = f"候選：模組層名字 {name} 被重新指定，不一定是這個"
        return [Edge(e.dst, e.kind, guess=reason) for e in self._py_bound_once(mod, name, hops)]

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
        """分派表的項目：呼叫時寫死了鍵且對得上 → 只連那一項；否則全連。分派表不在確定白名單（表可能被改），一律候選。"""
        picked = [ref for k, ref in entries if key and k == key] or [ref for _, ref in entries]
        reason = f"候選：分派表選出來的（{len(picked)} 項）"
        edges = []
        for ref in picked:
            edges += [Edge(e.dst, "dynamic", guess=e.guess or reason) for e in self.resolve(ctx, ref, defer=False)]
        return edges

    def _coarse(self, f, name: str) -> list:
        cands = self.coarse.get(name, [])
        pick = [i for i in cands if self.funcs[i].file == f.file] or cands
        return [Edge(pick[0], "direct", guess="候選：粗略模式只按同名配對")] if len(pick) == 1 else []

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
        """接收者是什麼 → (種類, 對象, 實際型別確定否)：module＋檔｜object／static＋類別｜external｜("", None) 不明。
        建構者、標註、欄位型別沿綁定鏈指到專案外 → external（不連到同名的專案類別）。"""
        if recv.startswith("new:"):
            if self._type_external(f, recv[4:]):
                return "external", None, False
            return "object", self.class_ref(f, recv[4:]), True
        if recv.startswith("mod:"):
            target = self.find_module(recv[4:], 0, f.file)
            return ("module", target, False) if target else ("external", None, False)
        head, *rest = recv.split(".")
        whole = self.module_alias(f, recv) if f.lang == "py" and recv and not self._shadowed(f, head) else None
        if whole:
            return "module", whole, False
        kind, cls = self._recv_head(f, head)
        for seg in rest:
            decl = self._field_decl(cls, seg) if cls else None
            if decl and self._type_external(*decl):
                return "external", None, False
            cls = self.class_ref(*decl) if decl else None
        constructed = head in f.constructed and not self.rebound_local(f, head) and head not in f.escaped
        exact = (kind == "static" or constructed) and not rest
        return (kind, cls, exact) if cls or kind == "external" else ("", None, False)

    def _shadowed(self, f: lang.Func, head: str) -> bool:
        """import 進來的模組名被參數、區域變數、巢狀 def 遮住（lookup_binding 找到的不是 import），
        或在模組層被重新指定（a = pick_backend()）：不能當那個模組。"""
        kind, _ = self.lookup_binding(f, head)
        mod = self.modules.get(f.file)
        return kind in ("param", "local", "nested") or (kind == "module" and bool(mod) and self._rebound(mod, head))

    def _recv_head(self, f: lang.Func, head: str):
        if head in ("self", "this") and self._own_receiver(f, head):
            return "object", self.cls_of(f)
        evidence = self._type_evidence(f, head)
        if evidence and self._type_external(*evidence):
            return "external", None                     # 標註或建構者指到專案外（pathlib.Path、typing 型別、第三方）
        typed_cls = self.class_ref(*evidence) if evidence else None
        if typed_cls:                                   # 解不到類別（工廠函式、沒匯入的名字）就照沒型別往下判
            return "object", typed_cls
        own = self.cls_of(f)
        if f.lang == "cs" and own and self.field_type(own, head):
            return "object", self.field_type(own, head)
        static = self.class_ref(f, head)
        if static:                                      # 類別.方法（含 import 別名的類別）
            return "static", static
        imp = self.imports_for(f, head).get(head)
        if imp and not self.find_module(imp[0], imp[1], f.file):
            return "external", None               # 匯入的外部模組或其成員（json、os.path…）
        return "", None

    def _type_evidence(self, f: lang.Func, head: str):
        """f 裡區域名字 head 的型別寫法與解析它的語境 → (語境, 型別寫法) 或 None（總原則 3：型別證據帶作用域）。
        區域變數的建構者與區域標註在本體（f）解析；參數標註在 def 的外層解析（outer_ctx）。
        Python 名字被重新指定過（任何一次，含內層 nonlocal 改寫）→ None：型別證據失效（總原則 4）；
        C# 的宣告型別是靜態型別，只有建構過又被重新指定（var x = new A(); x = new B();）才不定。"""
        unsettled = self.rebound_local(f, head) if f.lang == "py" else head in f.constructed and head in f.reassigned
        if unsettled:
            return None
        if head in f.local_types:
            return f, f.local_types[head]
        return (self.outer_ctx(f), f.param_types[head]) if head in f.param_types else None

    def _own_receiver(self, f: lang.Func, name: str) -> bool:
        """self.m()／cls.m() 的 self／cls 真的是方法自己的第一個參數：沿 lookup_binding 找到的是某個方法的第一個參數
        （巢狀函式裡用的是外層方法的），而且那一層沒重新指定過它（總原則 4）；區域變數剛好叫 self／cls 的不算。
        C# 的 this 不會被改。"""
        if f.lang != "py":
            return True
        kind, owner = self.lookup_binding(f, name)
        return kind == "param" and bool(owner.cls) and owner.params[:1] == [name] and not self.rebound_local(owner, name)

    def rebound_local(self, f: lang.Func, name: str) -> bool:
        """f 的參數或區域變數 name 被重新指定過：這一層綁了不只一次（含 import 又綁到同一個名字），
        或被內層函式（含巢狀類別本體）用 nonlocal 改掉。"""
        return (name in f.reassigned or name in f.import_rebinds
                or name in self.nonlocal_rebound.get((f.file, f.qual), ()))

    # 綁定穩定：白名單 1、2（建構者名稱）、4 共用的唯一判斷 ─────

    def stable(self, f: lang.Func, name: str) -> bool:
        """f 裡寫成 name 的名字只綁定一次、不是算出來的值（Python 看 lookup_binding 找到的那個綁定，見 _binding_stable）。
        C# 的方法與類別名不會被改指，只要不是同名的區域變數、參數或區域函式就算穩定。"""
        if f.lang == "cs":                         # C# 區域函式（f.inline）會遮住同名方法
            return name not in f.locals and name not in f.params and name not in f.inline
        return self._binding_stable(f, name, self.lookup_binding(f, name))

    def _binding_stable(self, f: lang.Func, name: str, binding: tuple) -> bool:
        """這個綁定只綁一次、不是算出來的值：參數或區域變數 → 不穩定（裝的東西看不到或會變）；巢狀 def 或函式裡的 import →
        那一層沒再綁定、沒被內層 nonlocal 改掉（import 還要沿匯入鏈到原模組也穩定）；模組層 → _stable_in。"""
        kind, owner = binding
        if kind == "module":
            return self._stable_in(f.file, name, 0)
        if kind not in ("nested", "import"):
            return False
        if name in owner.reassigned | owner.import_rebinds or name in self.nonlocal_rebound[(f.file, owner.qual)]:
            return False                           # 同一層綁了兩種（def＋指定、import＋指定），或被內層 nonlocal 改掉
        sources = owner.import_sources.get(name, []) if kind == "import" else []
        if len(sources) > 1:                       # 同一層 import 好幾次（try/except ImportError 兩種寫法）
            return self._imports_stable(f.file, sources, 0)
        if kind == "nested" or name not in owner.imports:
            return True                            # 巢狀 def，或 import a.b 綁的整個套件 a
        return self._stable_import(f.file, owner.imports[name], 0)

    def _stable_in(self, file: str, name: str, hops: int) -> bool:
        """模組層的 name 只綁定一次（或只被 import 好幾次、每次都指到同一個專案內目標）、不是算出來的值；
        它是別名或 from 匯入時，指到的名字也要穩定（逐跳）。"""
        mod = self.modules.get(file)
        if mod is None or hops > MAX_REEXPORT or name in mod.opaque:
            return False
        if (file, name) in self.rebound_elsewhere:     # 別處寫了 模組.name = …
            return False
        if mod.bindings[name] != 1:
            return self._only_agreeing_imports(mod, name, hops) and self._imports_stable(file, mod.import_sources[name], hops)
        if name in mod.aliases:
            return all(self._stable_ref(file, ref, hops + 1) for ref in mod.aliases[name])
        return self._stable_import(file, mod.imports[name], hops) if name in mod.imports else True

    def _only_agreeing_imports(self, mod: lang.Module, name: str, hops: int) -> bool:
        """模組層名字綁了好幾次，但每一次都是 import、而且全部指到同一個專案內目標。"""
        sources = mod.import_sources.get(name, [])
        return 1 < len(sources) == mod.bindings[name] and self._imports_agree(mod.file, sources, hops)

    def _imports_agree(self, file: str, sources: list, hops: int) -> bool:
        """同一層同名的 import 寫了好幾次（try/except ImportError 兩種寫法）：每一次沿綁定鏈都解析到同一個專案內目標
        （同一個函式、類別或模組）才算唯一解析到；有任何一次指到不同目標、外部、或解析不了 → 不是。
        函式層與模組層共用這一個判斷（找目標的 _rebound 只看這個；證明穩定再加 _imports_stable）。"""
        targets = {self._source_target(file, s, hops) for s in sources}
        return len(targets) == 1 and None not in targets

    def _imports_stable(self, file: str, sources: list, hops: int) -> bool:
        """同名 import 好幾次的綁定穩定：都指到同一個專案內目標，而且每一條匯入鏈都穩定。"""
        return self._imports_agree(file, sources, hops) and all(self._stable_import(file, s, hops) for s in sources)

    def _source_target(self, file: str, source: tuple, hops: int):
        """一筆 import 沿綁定鏈最後指到的專案內目標 → ("func", id)｜("class", 檔, 名)｜("module", 檔)；外部或解析不了 → None。"""
        modname, level, orig = source
        src = self.find_module(modname, level, file)
        if not orig or hops > MAX_REEXPORT:
            return ("module", src) if src and not orig else None
        mod = self.modules.get(src) if src and src != file else None
        if mod and mod.bindings[orig]:
            return self._name_target(mod, orig, hops + 1)
        sub = self.find_module(f"{modname}.{orig}" if modname else orig, level, file)
        return ("module", sub) if sub and sub != file else None

    def _name_target(self, mod: lang.Module, name: str, hops: int):
        """模組層名字 name 指到的專案內目標：本檔 def、本檔類別，或它的 import 都指到的同一個目標。"""
        if name in mod.defs:
            return "func", mod.defs[name]
        if any(mod.file in c.files for c in self.classes.get(name, [])):
            return "class", mod.file, name
        targets = {self._source_target(mod.file, s, hops) for s in mod.import_sources.get(name, [])}
        return targets.pop() if len(targets) == 1 else None

    def _rebound(self, mod: lang.Module, name: str) -> bool:
        """模組層名字被重新指定過（lang 的 rebound）；只被 import 好幾次、每次都指到同一個專案內目標的不算。"""
        return name in mod.rebound and (name in mod.opaque or not self._only_agreeing_imports(mod, name, 0))

    def _stable_import(self, file: str, source: tuple, hops: int) -> bool:
        """一筆 import：整個模組（import x）或子模組（from pkg import sub）就是那個模組；
        from X import name 要追到 X 裡的 name 也穩定。"""
        modname, level, orig = source
        if not orig:
            return True
        src = self.find_module(modname, level, file)
        mod = self.modules.get(src) if src and src != file else None
        if mod and mod.bindings[orig]:
            return self._stable_in(src, orig, hops + 1)
        sub = self.find_module(f"{modname}.{orig}" if modname else orig, level, file)
        return bool(sub) and sub != file

    def _stable_ref(self, file: str, ref: lang.Call, hops: int) -> bool:
        """模組層別名的右邊（同模組的名字，或 匯入的模組.成員）穩定。"""
        if ref.kind == "name":
            return self._stable_in(file, ref.name, hops)
        target = self.module_alias(self.module_ctx(file), ref.recv) if ref.kind == "attr" else None
        head = ref.recv.partition(".")[0]
        return bool(target) and self._stable_in(file, head, hops) and self._stable_in(target, ref.name, hops)

    # 確定白名單：rule 只在這一段填 ─────────────────────────
    # 每條白名單一個判斷式（_rule1～_rule5），各自正向檢查自己的寫法與條件。解析路只找目標、標不確定原因，
    # 不能給確定；所以新的解析路、或舊路漏了條件，產生的邊預設就是不確定。

    def certify(self, f: lang.Func, c: lang.Call, edges: list) -> list:
        """呼叫點 c 解析出來的邊：呼叫點在 lambda／生成器／推導式裡（c.scoped）、目標不只一個、不是直接呼叫、
        解析路已標了不確定原因的，一律不確定；
        目標是類別的方法而它在類別上的綁定可能被改寫（_method_rebound，1～4 條共用）→ 不確定；
        其餘依序對白名單 1～4 檢查，第一條成立的條號填進 rule。都不成立 → rule=None，補上原因。"""
        unique = len({e.dst for e in edges}) == 1
        for e in edges:
            e.rule = None
            if c.scoped and not e.guess:
                e.guess = SCOPED                   # 總原則 1：模型沒建的作用域構件裡，一律不給條號
            if unique and e.kind == "direct" and not e.guess and self._method_rebound(e.dst):
                e.guess = METHOD_REBOUND
            if unique and e.kind == "direct" and not e.guess:
                e.guess = self._lookup_veto(f, c, e.dst)   # 裝飾器、dataclass 產生的方法、MRO 證不出
            if unique and e.kind == "direct" and not e.guess:
                e.rule = next((n for n, check in self._call_rules() if check(f, c, e)), None)
            if e.rule is None and not e.guess:
                e.guess = NOT_WHITELISTED
        return edges

    def _method_rebound(self, dst: str) -> bool:
        """目標是 Python 類別的方法，而它在類別上的綁定可能被改寫：這個類別、祖先或子孫被寫過同名屬性
        （self.名 = …、類別.名 = …、型別看得出的實例.名 = …、setattr(X, "名", …)、del、類別本體再指定），
        或型別看不出的接收者寫過同名屬性（用名字保守判定）。C# 的方法不能被指定。"""
        fn = self.funcs[dst]
        if fn.lang != "py" or not fn.cls or fn.qual != f"{fn.cls}.{fn.name}":
            return False
        if ("*", fn.name) in self.method_writes:
            return True
        cls = self.cls_named(fn.cls, fn.file)
        family = list(self.ancestry(cls)) + self.descendants(cls)
        return any((self.cls_key(k), fn.name) in self.method_writes for k in family)

    def _lookup_veto(self, f: lang.Func, c: lang.Call, dst: str) -> str:
        """呼叫點 c 連到 dst 的路上有模型證不出的東西 → 不確定原因；沒有 → ""（白名單照常檢查）。C# 不適用。
        dst 自己的函式裝飾器、dst 所屬類別的類別裝飾器不在保留身分清單 → DECORATED；
        呼叫點經由的類別（_named_class；super() 則是所在類別 MRO 裡排在它後面的）照 C3 MRO 走到定義 dst 的類別：
        經過的類別帶清單外類別裝飾器 → DECORATED；經過的 dataclass 會自己產生這個方法 → GENERATED；MRO 證不出、而 dst
        不是呼叫點寫出的類別自己定義的 → MRO_UNPROVEN。super() 所在類別有用到多重繼承的子孫時，super 可能落到兄弟類別，
        也是 MRO_UNPROVEN。"""
        fn = self.funcs[dst]
        if fn.lang != "py":
            return ""
        ctx, own = self.outer_ctx(fn), self.cls_of(fn) if fn.cls and fn.qual == f"{fn.cls}.{fn.name}" else None
        if not all(self._keeps_identity(ctx, p, called, KEEP_IDENTITY, fn.name, own) for p, called, _ in fn.decorators):
            return DECORATED
        if own is not None and self._class_decorated(own):
            return DECORATED
        if c.kind == "super":
            here = self.cls_of(f)
            order, proven = self.mro(here) if here else ([], True)
            order, free = order[1:], 0
            proven = proven and not any(len(d.bases) + d.opaque_bases > 1 for d in (self.descendants(here) if here else []))
        else:
            order, proven = self.mro(self._named_class(f, c))
            free = 1                               # 呼叫點寫出的類別自己就定義 dst：MRO 後面怎麼排都不影響
        for i, k in enumerate(order):
            if self._class_decorated(k):
                return DECORATED
            if any(dst in ids for ids in k.methods.values()):
                return "" if proven or i < free else MRO_UNPROVEN
            if self._generates(k, fn.name):
                return GENERATED
        return ""

    def _class_decorated(self, cls) -> bool:
        """Python 類別帶保留身分清單（dataclass 系）以外的類別裝飾器。"""
        top = self.module_ctx(cls.files[0])
        return cls.lang == "py" and not all(self._keeps_identity(top, path, called, CLASS_KEEP_IDENTITY, cls.name)
                                            for path, called, _ in cls.decorators)

    def _generates(self, cls, name: str) -> bool:
        """cls 是 dataclass（沿綁定鏈確認的 dataclass 系裝飾器）、本體沒定義 name、而 name 是 dataclass 可能自己產生的方法：
        __init__ 只有寫死 init=False 時不產生；其他產生的方法不看旗標，一律當可能產生（模型沒建）。"""
        if cls.lang != "py" or name not in DATACLASS_METHODS or name in cls.methods or name in cls.body_names:
            return False
        top = self.module_ctx(cls.files[0])
        flags = [kw for p, _, kw in cls.decorators if self._canonical(top, p, CLASS_KEEP_IDENTITY) == "dataclass"]
        return any(not (name == "__init__" and kw.get("init") is False) for kw in flags)

    def _named_class(self, f: lang.Func, c: lang.Call):
        """呼叫點經由哪個類別查到目標（_lookup_veto 用，只會讓邊變不確定）：self／cls → 自己的類別；裸名 → 名字綁到的
        類別（建構）；接收者 → 它的型別（建構的、標註的、欄位宣告的）、類別.方法 的類別、模組.類別(…) 的類別；其他 → None。"""
        if c.kind == "self" or (c.kind == "name" and c.name == "cls" and f.params[:1] == ["cls"]):
            return self.cls_of(f)
        if c.kind == "name":
            return self.class_lookup(f, c.name)[0]
        if c.kind != "attr" or not c.recv:
            return None
        kind, target, _ = self.recv_type(f, c.recv)
        return self._class_at(target, c.name, 0)[0] if kind == "module" else target

    def _keeps_identity(self, ctx: lang.Func, path: str, called: bool, allowed: dict, own: str, cls=None) -> bool:
        """一個裝飾器保不保留被裝飾者的身分：寫法沿綁定鏈還原得出清單上的名字（_canonical）；函式裝飾器不能當場呼叫
        （@staticmethod() 不是那個寫法），類別的 dataclass(…) 可以。@name.setter／.getter／.deleter：name 就是被裝飾的方法名，
        而且同類別 cls 裡同名的方法真的掛了 @property。"""
        head, _, last = path.rpartition(".")
        if head and last in PROPERTY_PARTS and allowed is KEEP_IDENTITY:
            props = cls.def_decorators.get(own, []) if cls is not None and head == own else []
            return not called and any(not c2 and self._canonical(ctx, p2, KEEP_IDENTITY) == "property" for p2, c2, _ in props)
        return bool(self._canonical(ctx, path, allowed)) and (not called or allowed is CLASS_KEEP_IDENTITY)

    def _canonical(self, ctx: lang.Func, path: str, allowed: dict) -> str:
        """裝飾器寫法沿綁定鏈還原成清單上的名字（import 別名先還原原名：from abc import abstractmethod as abstract →
        abstractmethod）；import 進來的名字要綁定穩定（import 之後又被 def／指定改綁的不算）；內建的（staticmethod…）
        要在模組層從沒被綁定過。解析不到、不在清單 → ""。"""
        head, _, last = path.rpartition(".")
        key = head or last
        root = key.partition(".")[0]
        imports = self.imports_for(ctx, root)
        if key in imports:
            modname, level, orig = imports[key]
            name = last if head else orig
            ok = level == 0 and not (head and orig) and name in allowed and modname in allowed[name]
            return name if ok and self._bound_once(ctx, root) else ""
        if head or last not in allowed or "builtins" not in allowed[last]:
            return ""
        mod = self.modules.get(ctx.file)
        return last if self.lookup_binding(ctx, last)[0] == "module" and mod and mod.bindings[last] == 0 else ""

    def _bound_once(self, ctx: lang.Func, name: str) -> bool:
        """name 在綁定它的那一層只綁了這一次、之後沒被改綁（外部 import 也適用；stable() 會追到專案內的原模組，這裡不追）：
        模組層 → 只綁一次、不是算出來的值、沒被 模組.名字 = … 改掉；函式裡的 import → 那一層沒再綁、只 import 一次。"""
        kind, owner = self.lookup_binding(ctx, name)
        if kind == "module":
            mod = self.modules.get(ctx.file)
            return (bool(mod) and mod.bindings[name] == 1 and name not in mod.opaque
                    and (ctx.file, name) not in self.rebound_elsewhere)
        return (kind == "import" and name not in owner.reassigned | owner.import_rebinds
                and len(owner.import_sources.get(name, [])) == 1)

    def _call_rules(self) -> tuple:
        return (1, self._rule1), (2, self._rule2), (3, self._rule3), (4, self._rule4)

    def _rule1(self, f: lang.Func, c: lang.Call, e: Edge) -> bool:
        """白名單 1：直接呼叫唯一解析到、名字從未被重新指定的函式：裸名（含 import 進來的、巢狀函式、類別建構）、
        模組.函式、類別.靜態方法、建構子（C# new）、super()／base.。
        被證明的名字（裸名，或接收者開頭的模組名、類別名）在模型沒建的作用域構件裡被綁定 → 不成立（總原則 1）。"""
        if c.kind in ("super", "new"):
            return True
        head = c.name if c.kind == "name" else c.recv.partition(".")[0]
        if f.lang == "py" and self._in_construct(f, head):
            return False
        if c.kind == "name":
            if f.lang == "cs":                     # C# 裸名：本類別的方法歸第 3 條；這裡只收 using static 匯入的
                return self.stable(f, c.name) and not self._own_method(f, c.name, e)
            binding = self.lookup_binding(f, c.name)   # 被證明穩定的綁定，就要是 e.dst 的來源
            return (f.lang == "py" and self._binding_stable(f, c.name, binding)
                    and e.dst in {x.dst for x in self._binding_edges(f, c.name, binding)})
        if c.kind not in ("attr", "prop") or not c.recv:
            return False
        if c.recv.startswith("mod:"):
            target = self.find_module(c.recv[4:], 0, f.file)
            return bool(target) and self._stable_in(target, c.name, 0) and self._module_member(target, c.name, e)
        head = c.recv.partition(".")[0]
        if f.lang == "py" and not self._shadowed(f, head) and (target := self.module_alias(f, c.recv)):
            return self.stable(f, head) and self._stable_in(target, c.name, 0) and self._module_member(target, c.name, e)
        cls = self._static_class(f, c.recv)
        return bool(cls) and e.dst in self.lookup(cls, c.name)

    def _in_construct(self, f: lang.Func, name: str) -> bool:
        """總原則 1：名字在模型沒建的作用域構件裡被綁定（lambda 參數、推導式／生成器的迴圈目標、構件裡的 :=、
        巢狀類別本體裡的 global／nonlocal）；只讀不算，讀取不改變外層名字的綁定。
        看查找會走過的每一層函式：f 往外，到持有這個綁定的那一層為止（綁定在模組層就看到最外層函式）。"""
        owner = self.lookup_binding(f, name)[1]
        for scope in reversed(self.scopes(f)):
            fn = self.funcs.get(f"{f.file}::{scope}")
            if fn is not None and name in fn.scoped_binds:
                return True
            if fn is not None and fn is owner:
                return False
        return False

    def _module_member(self, target: str, name: str, e: Edge) -> bool:
        """被證明穩定的 模組.name，就是 e.dst 的來源。"""
        return e.dst in {x.dst for x in self._py_name(target, name)}

    def _static_class(self, f: lang.Func, recv: str):
        """類別.方法 的類別：接收者只有一段、就是類別名、而且不是同名的參數、區域變數或欄位；
        類別沿綁定鏈解析到專案內、名字也穩定（class_proof）。"""
        if "." in recv or recv in f.params or recv in f.locals or recv in f.local_types:
            return None
        own = self.cls_of(f) if f.lang == "cs" else None
        if own and self.field_type(own, recv):
            return None
        return self.class_proof(f, recv)

    def _own_method(self, f: lang.Func, name: str, e: Edge) -> bool:
        return bool(f.cls) and e.dst in self.lookup(self.cls_of(f), name)

    def _rule2(self, f: lang.Func, c: lang.Call, e: Edge) -> bool:
        """白名單 2：對剛 new 出來的物件呼叫方法（確定型別分派）：當場 new 的 Foo().run()，或同一函式內的區域變數
        建構之後每一次出現都只是方法呼叫的接收者（f.receiver_only 的正向證明，不是列舉「存走」的寫法）；
        建構者沿綁定鏈解析到專案內的類別、名字也綁定穩定（class_proof）。"""
        if c.kind not in ("attr", "prop") or "." in c.recv:
            return False
        if c.recv.startswith("new:"):
            ctor = c.recv[4:]
        elif c.recv in f.receiver_only:
            ctor = f.constructed[c.recv]
        else:
            return False
        cls = self.class_proof(f, ctor) if ctor else None
        return bool(cls) and e.dst in self.lookup(cls, c.name)

    def _rule3(self, f: lang.Func, c: lang.Call, e: Edge) -> bool:
        """白名單 3：self.method()／this.Method()（含 C# 省略 this、classmethod 的 cls()）沒有子類覆寫；
        型別已宣告的接收者（參數標註、區域變數標註、欄位宣告型別）沒有子類覆寫、也沒有多載（多載在 certify 已擋）。
        子類覆寫照各子孫自己的 C3 MRO 算（多重繼承排在前面的兄弟 mixin 也算）；子孫的 MRO 有任何一個證不出 → 不成立。"""
        cls, name = self._rule3_target(f, c, e)
        return (bool(cls) and e.dst in self.lookup(cls, name) and not override_targets(self, cls, name)
                and all(self.mro(d)[1] for d in self.descendants(cls)))

    def _rule3_target(self, f: lang.Func, c: lang.Call, e: Edge) -> tuple:
        """第 3 條看的類別與方法名：本物件 → 自己的類別；型別已宣告的接收者 → 宣告的型別；其他 → (None, "")。"""
        own = self.cls_of(f) if f.cls else None
        if c.kind == "self" or (c.kind == "prop" and c.recv in ("", "this")):
            return (own if self._own_receiver(f, c.recv or "self") else None), c.name
        if c.kind == "name" and f.lang == "cs" and self.stable(f, c.name) and self._own_method(f, c.name, e):
            return own, c.name
        if c.kind == "name" and c.name == "cls" and f.params[:1] == ["cls"]:
            return (own if self._own_receiver(f, "cls") else None), "__init__"
        if c.kind in ("attr", "prop") and c.recv:
            return self._declared_type(f, c.recv), c.name
        return None, ""

    def _declared_type(self, f: lang.Func, recv: str):
        """接收者的型別來自宣告：參數標註（在 def 的外層解析）、區域變數標註（在本體解析；C# 寫明型別的宣告）、
        欄位宣告型別（在寫它的地方解析）；沿 a.b.c 每一段都要是宣告的。
        建構推導的型別（x = Foo()、self.x = Foo()）不算，那是第 2 條的證據，失去第 2 條資格就不能改走這條。
        宣告的型別也要沿綁定鏈解析到專案內的類別（class_proof）：全專案同名搜尋、指到外部的都不算。"""
        head, *rest = recv.split(".")
        if head in ("self", "this") and self._own_receiver(f, head):
            cls = self.cls_of(f) if rest else None   # 方法自己的接收者；不是的話（一般函式的參數叫 self）照一般參數走
        elif f.lang == "py" and self.rebound_local(f, head):
            cls = None                             # 被重新指定過（含內層 nonlocal 改寫）：宣告的型別不再是證據（總原則 4）
        elif head in f.param_types and head not in f.reassigned:
            cls = self.class_proof(self.outer_ctx(f), f.param_types[head])   # 參數標註在 def 的外層解析
        elif head in f.declared and head not in f.reassigned:
            cls = self.class_proof(f, f.declared[head])
        elif f.lang == "cs" and head not in f.locals and head not in f.params and f.cls:
            cls = self.declared_field(self.cls_of(f), head)
        else:
            cls = None
        for seg in rest:
            cls = self.declared_field(cls, seg) if cls else None
        return cls

    def _rule4(self, f: lang.Func, c: lang.Call, e: Edge) -> bool:
        """白名單 4：簡單區域別名：同一函式內指定一次、之後沒再指定、右邊是白名單內可確定的函式（逐跳都不能被改指）。
        別名鏈上的名字宣告了 global／nonlocal、被內層函式用 nonlocal 改掉（別的作用域也能改它），
        或在模型沒建的作用域構件裡被綁定（總原則 1；只讀不算），都不算。"""
        if c.kind not in ("name", "invoke") or c.name not in f.aliases or c.name in f.params:
            return False
        names = [c.name]
        while (nxt := f.aliases.get(names[-1])) and nxt.kind == "name" and nxt.name in f.aliases and len(names) <= MAX_REEXPORT:
            names.append(nxt.name)
        outside = f.global_names | f.nonlocal_names | self.nonlocal_rebound[(f.file, f.qual)] | f.scoped_binds
        if outside & set(names):
            return False
        ref = self.alias_target(f, c.name)
        sure = [x.dst for x in self.resolve(f, ref, defer=False) if x.rule is not None] if ref else []
        return sure == [e.dst]

    def certify_callback(self, edges: list, sources: list, b: "Binding", flag: str, dead: bool, unknown: bool) -> list:
        """callback 邊（參數被當函式呼叫）：只有白名單 5 能給確定；不成立 → rule=None，補上原因。"""
        for e in edges:
            e.rule = 5 if len(edges) == 1 and not e.guess and self._rule5(e, sources, b, flag, dead, unknown) else None
            if e.rule is None and not e.guess:
                e.guess = NOT_WHITELISTED
        return edges

    def _rule5(self, e: Edge, sources: list, b: "Binding", flag: str, dead: bool, unknown: bool) -> bool:
        """白名單 5：callback：有已知呼叫者、每處都傳同一個白名單內的函式（或都用同一個預設值）、
        參數沒被重新指定、不是經由欄位存下的、沒有看不到或外部的來源。"""
        return (b.callers > 0 and not flag and not unknown and not b.mixed and not dead and bool(sources)
                and all(dst == e.dst and rule is not None for dst, rule, _ in sources))

    # 解析不到時：確知在專案外，還是專案內但看不到 ────────

    def is_external(self, f: lang.Func, c: lang.Call) -> bool:
        """確知在專案外（內建、外部模組、外部父類、專案裡沒有同名方法、沒人訂閱的事件、外部類別）→ True；
        專案內但看不到（區域變數裝的函式、同名方法多個、找不到的 self 方法、getattr、找不到的表、
        lambda 參數或推導式迴圈變數裝的東西）→ False，計入未解。"""
        if c.shadowed:
            return False
        c = self._plain_self(f, c)
        if c.kind in ("emit", "prop", "new", "super"):
            return True
        if c.kind in ("table", "getattr", "opaque"):
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
            return self._external_cs_name(f, name)
        if name in PY_BUILTINS or self.class_ref(f, name) or (name == "cls" and f.params[:1] == ["cls"]):
            return True                            # 建構沒有 __init__ 的類別（含 import 別名）：沒有要讀的建構子
        mod = self.modules.get(f.file)
        if mod and name in mod.opaque:
            return False                           # 模組層名字被指定成算出來的值：看不到
        aliases = mod.aliases.get(name, []) if mod else []
        if aliases:                                # 模組層別名指向外部模組的函式（flat = itertools.chain.from_iterable）
            ctx = self.module_ctx(f.file)
            return all(a.kind == "attr" and self.recv_type(ctx, a.recv)[0] == "external" for a in aliases)
        return self._py_external(f.file, self.imports_for(f, name), name)

    def _external_cs_name(self, f: lang.Func, name: str) -> bool:
        """C# 裸名呼叫解不到：沒人訂閱的事件 → 外部；本類別欄位裝的委派 → 看不到；
        有 using static 外部型別或外部父類 → 可能是從那裡來的，算外部。"""
        ancestry = list(self.ancestry(self.cls_of(f))) if f.cls else []
        if any(name in c.events for c in ancestry):
            return True
        if any(name in c.fields for c in ancestry):
            return False
        usings = self.modules[f.file].static_usings if f.file in self.modules else []
        outside = any(self.cls_named(t.split(".")[-1], f.file) is None for t in usings)
        return outside or self.external_base(self.cls_of(f))

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
                deferred = len(self.pending) > waiting      # callback：等下面解完才知道算連線還是未解
                self.hits[f.id] += bool(edges)
                self.unres[f.id] += not edges and not deferred and not self.is_external(f, c)
        for src, bind, param, flag in self.pending:
            sources = callback_targets(self, bind, param)
            found = {}
            for dst, _rule, guess in sources:
                found[dst] = guess if dst not in found else (found[dst] or guess)    # 任一處來源不確定就保留候選
            b = self.bound_refs(bind, param)
            dead = [(c, r) for c, r in b.refs if not self.resolve(c, r, defer=False)]   # 傳了具名函式卻連不到
            unknown = b.blind or any(not self.is_external(c, r) for c, r in dead)
            reason = self._callback_reason(param, len(found), flag, unknown, b.mixed or bool(dead), b.callers)
            edges = [Edge(t, "callback", guess=g or reason) for t, g in found.items()]
            self._add_edges(src, self.certify_callback(edges, sources, b, flag, bool(dead), unknown), None)
            self.hits[src] += bool(found)
            self.unres[src] += unknown or not (found or dead or b.mixed)   # 沒有任何來源證據（沒呼叫者也沒預設值）也算未解

    @staticmethod
    def _callback_reason(param: str, targets: int, flag: str, unknown: bool, mixed: bool, callers: int) -> str:
        """callback 邊的不確定原因：看不到的來源 > 經由欄位存下 > 參數被改指 > 沒有已知呼叫者 > 混了 lambda／外部函式
        > 多個目標；都沒有＝空字串（說明欄留空，確不確定由 _rule5 正向檢查）。"""
        if unknown:
            return f"候選：有呼叫處傳進看不到的函式給 {param}，這只是看得到的那些"
        if flag == "scoped":
            return f"候選：呼叫 {param} 的地方在 lambda／生成器／推導式裡，模型沒建那一層的綁定"
        if flag == "closure":
            return f"候選：{param} 是外層函式的參數（閉包），這些是外層的呼叫者傳進來的"
        if flag == "stored":
            return f"候選：經由欄位存下的 callback（建構時傳進 {param}），欄位可能被換"
        if flag == "reassigned":
            return f"候選：參數 {param} 在函式裡被重新指定"
        if not callers:
            return f"候選：{param} 沒有已知呼叫者，只看到預設值"
        if mixed:
            return f"候選：也有呼叫處傳 lambda 或外部函式進 {param}"
        return f"候選：{targets} 處呼叫各傳不同函式進 {param}，分不出這次是哪個" if targets > 1 else ""

    def _add_edges(self, src: str, edges: list, c) -> None:
        """加邊（同終點同種類只留一條；幾處呼叫裡有一處經白名單確定，就留確定的那條，不看呼叫點的先後）；
        直接／繼承呼叫每個呼叫點都記下呼叫者（就算邊重複），callback 要回頭查誰傳了什麼。
        沒經過確定白名單（rule 是 None）又沒寫原因的邊補上原因：確定只看 rule，原因只是說明。"""
        for e in edges:
            if e.rule is None and not e.guess:
                e.guess = NOT_WHITELISTED
            if c is not None and e.kind in ("direct", "inherit"):
                self.callers[e.dst].append((self.funcs[src], c))
            same = next((i for i, x in enumerate(self.edges[src]) if x.dst == e.dst and x.kind == e.kind), None)
            if same is None:
                self.edges[src].append(e)
            elif e.rule is not None and self.edges[src][same].rule is None:
                self.edges[src][same] = e

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
        return Step(b.id, kind, jump=a.file != b.file and not axis, axis=axis, guess=e.guess, rule=e.rule)

    def _shortest(self, entry: str, certain_only: bool):
        """從 entry 出發的最短路（拐彎、跳檔、深度依序比）；certain_only 時只走確定的邊。"""
        best, back = {entry: (0, 0, 0)}, {}
        heap = [((0, 0, 0), entry)]
        while heap:
            cost, u = heapq.heappop(heap)
            if cost > best[u]:
                continue
            for e in [e for e in self.edges.get(u, []) if not (certain_only and e.rule is None)]:
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
        if not mod.funcs and not is_test(rel) and DEF_HINT[mod.lang].search(text):
            scan["empty_files"].append(rel)       # 測試夾具常是只有頂層程式碼的腳本，不列
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
    return {"entry": eid, "sig": g.signature(eid), "landings": len(routes), "certain_routes": len(sure),
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
    """同一入口、同一落點比拐彎、跳檔、轉手；入口與落點都用「名稱＋完整簽章」對齊（C# 單一 ↔ 多載轉換也對得上）。
    全確定與含候選的路分開數。下列情況那一列標「不可判定」（可能是看不到了，不是變好）：
    入口可達範圍內的未解呼叫變多或冒出新的未解函式；路徑經過的檔在任一版解析失敗或從有函式變零函式。"""
    b_entries = {compare_key(e["entry"], e["sig"]): e for e in before["entries"]}
    a_entries = {compare_key(e["entry"], e["sig"]): e for e in after["entries"]}
    undecidable = {k for k, a in a_entries.items() if k in b_entries and _coverage_worse(b_entries[k], a)}
    sb, sa = before["stats"], after["stats"]
    broken = _broken_files(sb["file_funcs"], sa["file_funcs"])
    rows = []
    for key in sorted(set(b_entries) | set(a_entries)):
        eb, ea = b_entries.get(key, {}), a_entries.get(key, {})
        b = {compare_key(r["landing"], r["sig"]): r for r in eb.get("routes", [])}
        a = {compare_key(r["landing"], r["sig"]): r for r in ea.get("routes", [])}
        label = (ea or eb)["entry"]
        rows += [_diff_row(label, b.get(k), a.get(k), key in undecidable, broken) for k in sorted(set(b) | set(a))]
    rows.sort(key=lambda r: (not r["certain"], STATUS_ORDER.index(r["status"]), r["entry"], r["landing"]))
    sure = Counter(r["status"] for r in rows if r["certain"])
    maybe = Counter(r["status"] for r in rows if not r["certain"])
    coverage_drop = bool(len(sa["parse_errors"]) > len(sb["parse_errors"]) or broken or undecidable
                         or sa["unresolved_ratio"] > sb["unresolved_ratio"] + COVERAGE_DROP)
    return {"entries": len(set(b_entries) | set(a_entries)), "rows": rows,
            "counts": {k: sure.get(k, 0) for k in STATUS_ORDER},
            "counts_candidate": {k: maybe.get(k, 0) for k in STATUS_ORDER},
            "max_turns_before": max((e["max_turns"] for e in before["entries"]), default=0),
            "max_turns_after": max((e["max_turns"] for e in after["entries"]), default=0),
            "undecidable_entries": sorted((a_entries.get(k) or b_entries[k])["entry"] for k in undecidable),
            "emptied_files": sorted(broken), "stats_before": sb, "stats_after": sa, "coverage_drop": coverage_drop}


def _broken_files(before: dict, after: dict) -> set:
    """任一版解析失敗（-1），或一版有函式、另一版變零函式的檔：涉及它的比較列都不可判定。"""
    files = set(before) | set(after)
    failed = {f for f in files if -1 in (before.get(f), after.get(f))}
    emptied = {f for f in files if {before.get(f, 0) > 0, after.get(f, 0) > 0} == {True, False} and f in before and f in after}
    return failed | emptied


def _coverage_worse(b: dict, a: dict) -> bool:
    return a["unresolved_reach"] > b["unresolved_reach"] or bool(set(a["unresolved_funcs"]) - set(b["unresolved_funcs"]))


def compare_key(ident: str, sig: str | None) -> str:
    """入口或落點在前後比較時的對齊鍵：C# 用「檔::類.方法(完整參數型別)」，單一方法與多載互轉、重排都對得上同一個方法。"""
    return ident if sig is None else f"{ident.split('(')[0]}({sig})"


def _diff_row(entry: str, b: dict | None, a: dict | None, undecidable: bool, broken: set) -> dict:
    landing = (a or b)["landing"]
    key = ("turns", "file_jumps", "handoffs")
    if b is None or a is None:
        status = "new" if b is None else "gone"
    else:
        vb, va = tuple(b[k] for k in key), tuple(a[k] for k in key)
        status = "same" if va == vb else ("better" if va < vb else "worse")
    touched = {s["func"].split("::")[0] for s in flat(r["steps"] for r in (b, a) if r)}
    status = "undecidable" if undecidable or touched & broken else status   # 數字是下限：前後相同也不代表沒變
    certain = all(r["certain"] for r in (b, a) if r)
    return {"entry": entry, "landing": landing, "status": status, "certain": certain, "before": b, "after": a}


def run_compare(root: Path, before: str, after: str | None, entry: str | None, to: str | None) -> dict:
    with tempfile.TemporaryDirectory(prefix="reading-path-") as tmp:
        b_root = materialize(before, root, Path(tmp), "before")
        a_root = materialize(after, root, Path(tmp), "after") if after else root
        b_rep, a_rep = analyze(b_root, entry, to), analyze(a_root, entry, to)
    res = compare(b_rep, a_rep)
    res.update(before_label=before, after_label=after or "目前內容", root=str(root),
               caveats=list(dict.fromkeys(b_rep["caveats"] + a_rep["caveats"])))
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


def caveat_lines(caveats: list) -> list:
    return ["本次涉及的限制與可能誤報：", *(f"  - {c}" for c in caveats)] if caveats else []


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
    lines += caveat_lines(report["caveats"])
    entries = report["entries"]
    routes = sorted(flat(e["routes"] for e in entries), key=worst_first)
    lines.append(f"入口 {len(entries)} 個（最差在前）｜落點 {len(routes)} 條，其中全確定 {sum(r['certain'] for r in routes)}"
                 "：全確定的數字是可信下限，含候選的是上限參考；刻度分布只算全確定且讀到底的路")
    for e in entries[:ENTRY_LIST_LIMIT]:
        dist = "・".join(f"{label} {n}" for label, n in reversed(e["grades"].items()))
        rating = grade(e["max_turns"]) if e["certain_routes"] else "無法評級：沒有全確定的路"
        lines.append(f"  [{rating}] {e['entry']}  落點 {e['landings']}（全確定 {e['certain_routes']}）｜最多拐彎 {e['max_turns']}"
                     f"｜最多跳檔 {e['max_file_jumps']}｜最多轉手 {e['max_handoffs']}｜{dist}"
                     f"｜含候選 {e['candidate']}（最多拐彎 {e['max_turns_candidate']}）｜未讀到底 {e['incomplete']}"
                     f"｜可達範圍內未解 {e['unresolved_reach']}")
    if len(entries) > ENTRY_LIST_LIMIT:
        lines.append(f"  …另 {len(entries) - ENTRY_LIST_LIMIT} 個入口（--json 看全部）")
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
    lines += [f"  解析失敗或有函式↔零函式（經過它的列都不可判定）：{f}" for f in res["emptied_files"]]
    lines += caveat_lines(res["caveats"])
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
    return (f"READING_PATH DONE entries={len(entries)} landings={len(routes)} certain={sum(r['certain'] for r in routes)}"
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
