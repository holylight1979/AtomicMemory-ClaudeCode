"""reading_path_cs — C# 改動的閱讀路徑：只量改到的 .cs 加一跳上下游，不掃整個專案（純計算，hooks/wg_reading_path 的背景量測用）。

做什麼：
  範圍  改到的檔 → 下游＝它們直接用到的專案型別所在的檔（繼承、欄位／參數／區域變數型別、new、靜態呼叫 X.M 的 X；「檔名＝型別名」
        的排前面，再搜型別定義）；上游＝提到改到的檔裡型別名的檔（只搜名字，不解析）。上下游各最多 NEIGHBOR_MAX 檔。
        只有範圍內的檔會被讀進來解析；範圍外的呼叫照外部算，所以路徑是一跳範圍裡看得到的那一段，不是整個專案的最短路。
  版控  git 工作區（_Git）：檔案清單＝git ls-files、搜名字＝git grep、before＝git cat-file 取 base 版、改動行＝git diff -U0。
        svn 工作副本（_Svn）：檔案清單＝目錄走訪、搜名字＝ripgrep（沒裝就逐檔讀），都不靠版控；before＝svn status --xml 挑出
        本地改過的檔才 svn cat -r BASE，沒改過的 before 就是工作樹內容；改動行＝difflib 比 before 與工作樹。
  建圖  範圍內的檔建 before 與 after（工作樹）兩張圖，用 tools/reading-path.py 的同一個 Graph 與 compare（找路、拐彎、狀態都跟
        Python 版同一套）。分析器：本機有 .NET SDK 附的 Roslyn 就用 lib/cs_roslyn，沒有或跑不動用輕量解析
        （reading_path_lang.parse_csharp），兩種都註明在 notes。
  量    入口＝改到的函式（改動行命中）加上範圍內直接呼叫它們的函式。另列改到的函式裡只把呼叫往下傳的（量尺的 passthrough；
        只呼叫上層同名方法的覆寫不列，算在類別空層裡），與改到的型別的繼承鏈每層（lib/turn_metrics_cs，查找池＝範圍）。
回傳只有數據；門檻、要不要問、附什麼字由 hooks/wg_reading_path 決定。
怎麼跑：import 後呼叫 measure(root, base, changed, run, deadline, kind)；不單獨跑。
"""
from __future__ import annotations

import difflib
import importlib.util
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Optional, Tuple

_TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.append(str(_TOOLS))
import reading_path_lang as lang  # noqa: E402
import cs_roslyn  # noqa: E402
import turn_metrics_cs as tmc  # noqa: E402
from turn_metrics import parse_diff_ranges  # noqa: E402

Run = Callable[..., Tuple[int, bytes]]   # (完整指令, stdin, cwd=None) → (結束碼, stdout)；預算由呼叫端管
NEIGHBOR_MAX = 40          # 上游、下游各最多幾檔（超過的照找到的順序截掉並註明）
SCOPE_POLICY = "一跳範圍"   # 報表上的範圍政策：前後兩版同一個，比較才不會判成母體不同
_DEF_KINDS = "class|struct|interface|record|enum"
_SVN_CHANGED = {"modified", "replaced", "conflicted", "missing", "obstructed", "incomplete"}   # 有 BASE、內容可能跟工作樹不同
_SVN_NEW = {"added", "unversioned"}                                                           # 沒有 BASE：before 沒這個檔


class MeasureError(Exception):
    """版控拿不到要的東西（檔案清單、改動行、before 版本、搜尋失敗）：這一批量不出來，呼叫端只附一句原因。"""


def measure(root: Path, base: str, changed: List[str], run: Run, deadline: float = float("inf"),
            kind: str = "git") -> Dict[str, Any]:
    """改到的 .cs（絕對路徑）→ {"scope": 解析過的相對路徑, "analyzer": "roslyn"｜"light", "notes": [說明],
    "rows": 量尺 compare 的每一列, "forwarders": 改到的只轉手函式, "classes": 改到的型別的繼承鏈}。
    kind：git（base＝git rev）或 svn（base 不用，一律對 BASE）。版控失敗丟 MeasureError；Roslyn 跑不動自動改用輕量解析重來一次
    並註明。deadline：Roslyn 子行程的期限（time.monotonic）。"""
    root = Path(root).resolve()
    src = _Git(root, run) if kind == "git" else _Svn(root, run)
    notes: List[str] = []
    rels = [r for r in (_rel(root, f) for f in changed) if r and (root / r).is_file()]   # 刪掉的檔沒有 after 可量
    tracked = src.files()
    use = "roslyn" if cs_roslyn.find_roslyn() else "light"
    if use == "light":
        notes.append("找不到 .NET SDK 附的 Roslyn，用輕量解析")
    try:
        return _measure(root, base, rels, src, tracked, use, notes, deadline)
    except cs_roslyn.RoslynError as e:
        notes.append(f"Roslyn 跑不動（{e}），改用輕量解析")
        return _measure(root, base, rels, src, tracked, "light", notes, deadline)


def _measure(root: Path, base: str, rels: List[str], src: Any, tracked: List[str], use: str, notes: List[str],
             deadline: float) -> Dict[str, Any]:
    rp = _ruler()
    parse = (lambda texts: cs_roslyn.parse_many(texts, deadline)) if use == "roslyn" else _light_many
    texts = {r: _text(rp, root / r) for r in rels}
    mine = parse({r: t for r, t in texts.items() if isinstance(t, str)})
    mods = [m for m in mine.values() if isinstance(m, lang.Module)]
    down, up, cut_down, cut_up = _neighbors(mods, tracked, rels, src)
    notes += [f"{side}有 {n} 檔超過上限 {NEIGHBOR_MAX} 沒讀" for side, n in (("下游", cut_down), ("上游", cut_up)) if n]
    scope = sorted(r for r in set(rels) | set(down) | set(up) if (root / r).is_file())   # 清單裡但工作樹已刪的鄰居不讀

    def parse_after(texts: Dict[str, str]) -> Dict[str, Any]:   # 改到的檔剛解析過，不再解析一次
        return {**parse({r: t for r, t in texts.items() if r not in mine}), **{r: mine[r] for r in texts if r in mine}}

    before_src = src.base(base, scope, rp, rels)
    after = rp.graph_of(root, {r: root / r for r in scope}, SCOPE_POLICY, parse_cs=parse_after)
    before = rp.graph_of(root, before_src, SCOPE_POLICY, parse_cs=parse)
    notes += [f"解析不了：{e}" for e in after.scan["parse_errors"]]
    ranges = src.ranges(base, rels, before_src, texts)
    hits = [f for f in after.funcs.values() if f.lang == "cs" and _touched(f, ranges.get(f.file))]
    eids = sorted({f.id for f in hits} | {c.id for f in hits for c, _ in after.callers.get(f.id, [])})
    res = rp.compare(rp.graph_report(before, [e for e in eids if e in before.funcs]), rp.graph_report(after, eids))
    forwarders = [{"func": f.id, "file": str(root / f.file), "line": f.line, "end": f.end, "style": after.passthrough[f.id],
                   "targets": [e.dst for e in after.edges[f.id]]} for f in hits if f.id in after.passthrough and not _base_echo(f)]
    abs_ranges = {str(root / r): v for r, v in ranges.items()}   # 查找池只有一跳範圍：實作數是下限，不據此算「只有一個實作」
    side = tmc.metrics_for_files([str(root / r) for r in rels], abs_ranges, [str(root / r) for r in scope], partial_pool=True)
    notes += [f"{_rel(root, r['file'])}：{'；'.join(r['unparsed']) if r['kind'] == 'unparsed' else r['error']}"
              for r in side if r["kind"] in ("unparsed", "error")]
    notes[:] = list(dict.fromkeys(notes + src.notes))   # 版控端的說明（查不到狀態、取不到 BASE）；Roslyn 退回重來時不重複
    return {"scope": scope, "analyzer": use, "notes": notes, "rows": res["rows"], "forwarders": forwarders,
            "classes": [r for r in side if r["kind"] == "class"]}


# ─── 範圍：一跳上下游 ─────────────────────────────────────────────────────────

def _type_refs(mod: lang.Module) -> List[str]:
    """一個檔直接用到的型別名，繼承的排前面：繼承、欄位、參數、區域變數、new、大寫開頭接收者的第一段（靜態呼叫）。"""
    bases = [b for c in mod.classes for b in c.bases]
    rest = [t for c in mod.classes for t in c.fields.values()]
    for f in mod.funcs:
        rest += [*f.param_types.values(), *f.local_types.values()]
        rest += [c.name if c.kind == "new" else c.recv.split(".")[0] for c in f.calls if c.kind == "new" or c.recv[:1].isupper()]
    names = [n.split("[")[0].rstrip("?") for n in bases + rest + [u.split(".")[-1] for u in mod.static_usings]]
    return list(dict.fromkeys(n for n in names if n[:1].isupper()))


def _neighbors(mods: List[lang.Module], tracked: List[str], changed: List[str], src: Any) -> Tuple[List[str], List[str], int, int]:
    """改到的檔的一跳上下游 → (下游, 上游, 下游截掉幾個, 上游截掉幾個)。
    下游：照檔名（Pool.cs、Pool.Fill.cs 都是 Pool）的排前面；檔名對上的不一定是定義所在（Store.cs 裡可能不是 Store），
    所以全部型別名再搜一次定義，接在後面。上游：整字搜改到的檔裡的型別名（含註解與字串；寧可多讀一檔）。"""
    defined = {c.name for m in mods for c in m.classes}
    want = [n for n in dict.fromkeys(n for m in mods for n in _type_refs(m)) if n not in defined]
    by_stem: Dict[str, List[str]] = {}
    for rel in tracked:
        by_stem.setdefault(PurePosixPath(rel).name.split(".")[0], []).append(rel)
    defs, mentions = src.grep(want, sorted(defined), tracked)
    down, cut_down = _cap([r for n in want for r in by_stem.get(n, [])] + defs, changed)
    up, cut_up = _cap(mentions, changed)
    return down, up, cut_down, cut_up


def _cap(found: List[str], changed: List[str]) -> Tuple[List[str], int]:
    """去重、去掉改到的檔，保留先找到的順序取前 NEIGHBOR_MAX 個 → (檔, 截掉幾個)。"""
    picked = [r for r in dict.fromkeys(found) if r not in set(changed)]
    return picked[:NEIGHBOR_MAX], max(0, len(picked) - NEIGHBOR_MAX)


def _source_files(rels: List[str]) -> List[str]:
    """清單裡量尺會掃的 .cs：去掉產生碼與量尺不掃的目錄（obj、bin、Library、點開頭…）。"""
    rp = _ruler()
    return [n for n in rels if n.lower().endswith(".cs") and not lang.GENERATED_RE.search(n) and not rp._skipped(n)]


# ─── 版控後端：git 工作區、svn 工作副本 ───────────────────────────────────────────

class _Git:
    """git 工作區：檔案清單＝ls-files（追蹤中的）、搜名字＝git grep、before＝cat-file --batch 取 base、改動行＝diff -U0。"""

    def __init__(self, root: Path, run: Run):
        self.root, self.run, self.notes = root, run, []

    def _git(self, args: List[str], data: Optional[bytes] = None) -> Tuple[int, bytes]:
        return self.run(["git", "-C", str(self.root), *args], data)

    def files(self) -> List[str]:
        rc, out = self._git(["ls-files", "-z", "--", "*.cs"])
        if rc != 0:
            raise MeasureError("git ls-files 失敗")
        return _source_files([n for n in out.decode("utf-8", "replace").split("\0") if n])

    def grep(self, defs: List[str], words: List[str], tracked: List[str]) -> Tuple[List[str], List[str]]:
        """(定義任一個 defs 型別的檔, 整字提到任一個 words 的檔)，都只收 tracked 裡的、照路徑排序。"""
        regex = rf"(^|[^A-Za-z0-9_])({_DEF_KINDS})[[:space:]]+({'|'.join(defs)})([^A-Za-z0-9_]|$)"
        return (self._grep(["-E", "-e", regex], tracked) if defs else [],
                self._grep(["-w", "-F", *[x for n in words for x in ("-e", n)]], tracked) if words else [])

    def _grep(self, pattern: List[str], tracked: List[str]) -> List[str]:
        rc, out = self._git(["grep", "-l", "-z", *pattern, "--", "*.cs"])
        if rc not in (0, 1):                     # 1＝沒命中
            raise MeasureError(f"git grep 失敗（結束碼 {rc}）")
        keep = set(tracked)
        return sorted(n for n in out.decode("utf-8", "replace").split("\0") if n in keep)

    def base(self, base: str, scope: List[str], rp: Any, changed: List[str]) -> Dict[str, Any]:
        """範圍內的檔在 base 的版本（cat-file --batch 一次取完）→ {相對路徑: 文字或解碼例外}；base 沒有的檔（新檔）不在裡面。
        changed 不用（git 照 base 取得到每個檔，沒有查不到狀態的情況）。"""
        if not scope:
            return {}
        rc, out = self._git(["cat-file", "--batch"], "".join(f"{base}:{r}\n" for r in scope).encode("utf-8"))
        if rc != 0:
            raise MeasureError(f"取不到 before（{base}）的檔")
        got, i = {}, 0
        for rel in scope:
            nl = out.index(b"\n", i)
            head, i = out[i:nl].split(), nl + 1
            if len(head) != 3 or head[1] != b"blob":    # "<名字> missing"：base 沒有這個檔
                continue
            size = int(head[2])
            got[rel] = _decode(rp, out[i:i + size])
            i += size + 1
        return got

    def ranges(self, base: str, rels: List[str], before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, List[Tuple[int, int]]]:
        """改到的檔對 base 的改動行區間（新版行號，鍵＝相對路徑）。"""
        rc, out = self._git(["diff", "-U0", base, "--", *rels]) if rels else (0, b"")
        if rc != 0:
            raise MeasureError(f"對 before（{base}）的 diff 拿不到")
        return parse_diff_ranges(out.decode("utf-8", "replace"))


class _Svn:
    """svn 工作副本：檔案清單＝目錄走訪、搜名字＝ripgrep（沒裝就逐檔讀），都不靠版控；before＝svn status --xml 挑出本地改過的才
    svn cat -r BASE（沒改過的 before＝工作樹內容，加的、沒納管的 before 沒這個檔）；改動行＝difflib 比 before 與工作樹。
    session 中途 svn commit 過的改動已經是 BASE，不算改動（同 git 收尾前 commit 過的照 base 規則）。"""

    def __init__(self, root: Path, run: Run):
        self.root, self.run, self.notes = root, run, []
        self.rg = shutil.which("rg")

    def files(self) -> List[str]:
        if self.rg:
            rc, out = self.run([self.rg, "--files", *self._globs(), "--", "."], None, self.root)
            if rc not in (0, 1):
                raise MeasureError(f"rg --files 失敗（結束碼 {rc}）")
            return _source_files(sorted(self._rels(out)))
        skip, found = _ruler().SKIP_DIRS, []
        for d, dirs, names in os.walk(self.root):
            pre = Path(d).relative_to(self.root).as_posix() + "/"
            dirs[:] = sorted(x for x in dirs if x not in skip and not x.startswith("."))   # 同量尺 _skipped 的目錄規則
            found += [(pre + n).removeprefix("./") for n in names if n.lower().endswith(".cs")]
        return _source_files(sorted(found))

    def _globs(self) -> List[str]:
        """rg 只看 .cs、不讀 .gitignore（svn 工作副本照目錄走訪的規則）、量尺不掃的目錄整個跳過（Unity 的 Library 動輒十萬檔）。
        rg 要在專案根當工作目錄搜 "."：給絕對路徑時 glob 會比到專案根以上的目錄名（專案放在 Temp、build 底下就整個被排掉）。"""
        return ["--no-ignore", "--no-messages", "-g", "*.cs", *[x for d in sorted(_ruler().SKIP_DIRS) for x in ("-g", f"!**/{d}/**")]]

    def grep(self, defs: List[str], words: List[str], tracked: List[str]) -> Tuple[List[str], List[str]]:
        regex = rf"(?:^|[^A-Za-z0-9_])(?:{_DEF_KINDS})\s+(?:{'|'.join(map(re.escape, defs))})(?:[^A-Za-z0-9_]|$)"
        if self.rg:
            return (self._rg(["-e", regex], tracked) if defs else [],
                    self._rg(["-w", "-F", *[x for n in words for x in ("-e", n)]], tracked) if words else [])
        def_rx = re.compile(regex) if defs else None
        word_rx = re.compile(rf"\b(?:{'|'.join(map(re.escape, words))})\b") if words else None
        hits: Tuple[List[str], List[str]] = ([], [])
        for rel in tracked:                      # 沒有 rg：逐檔讀一次，兩種都比
            try:
                text = (self.root / rel).read_bytes().decode("utf-8", "replace")
            except OSError:
                continue
            for out, rx in zip(hits, (def_rx, word_rx)):
                if rx and rx.search(text):
                    out.append(rel)
        return hits

    def _rg(self, pattern: List[str], tracked: List[str]) -> List[str]:
        rc, out = self.run([self.rg, "-l", *self._globs(), *pattern, "--", "."], None, self.root)
        if rc not in (0, 1):                     # 1＝沒命中
            raise MeasureError(f"rg 失敗（結束碼 {rc}）")
        keep = set(tracked)
        return sorted(r for r in self._rels(out) if r in keep)

    def _rels(self, out: bytes) -> List[str]:
        return [(self.root / ln).resolve().relative_to(self.root).as_posix() for ln in out.decode("utf-8", "replace").splitlines() if ln]

    def base(self, base: str, scope: List[str], rp: Any, changed: List[str]) -> Dict[str, Any]:
        """範圍內的檔在 BASE 的版本 → {相對路徑: 文字或例外}；加的、沒納管的檔不在裡面。一次查不到狀態（某個路徑 svn 不收）
        就逐檔查；逐檔也查不到的：這次改到的當新檔（整檔算改動，寧可多問不漏問），鄰居當沒改過（before＝工作樹）；
        取不到 BASE 的當新檔；都寫進 notes。"""
        if not scope:
            return {}
        status = self._status(scope)
        if status is None:
            status, lost = {}, []
            for rel in scope:
                one = self._status([rel])
                lost += [rel] if one is None else []
                status.update(one if one is not None else {rel: "unknown"})
            if lost:
                self.notes.append(f"svn 查不到狀態的 {len(lost)} 檔（例：{lost[0]}）：改到的當新檔、鄰居當沒改過")
        got: Dict[str, Any] = {}
        for rel in scope:
            item = status.get(rel, "normal")
            if item in _SVN_NEW or (item == "unknown" and rel in changed):
                continue
            if item not in _SVN_CHANGED:
                got[rel] = _text(rp, self.root / rel)
                continue
            rc, data = self.run(["svn", "cat", "-r", "BASE", "--non-interactive", self._arg(rel)], None)
            if rc == 0:
                got[rel] = _decode(rp, data)
            else:
                self.notes.append(f"svn 取不到 {rel} 的 BASE，當新檔")
        return got

    def _status(self, rels: List[str]) -> Optional[Dict[str, str]]:
        """svn status --xml → {相對路徑: wc-status 的 item}（沒列出來的＝normal）；svn 失敗或輸出讀不懂 → None。"""
        rc, out = self.run(["svn", "status", "--xml", "--non-interactive", *[self._arg(r) for r in rels]], None)
        if rc != 0:
            return None
        try:
            entries = list(ET.fromstring(out).iter("entry"))
        except ET.ParseError:
            return None
        status = {}
        for e in entries:
            ws = e.find("wc-status")
            rel = _rel(self.root, e.get("path", ""))
            if rel:
                status[rel] = ws.get("item", "") if ws is not None else ""
        return status

    def _arg(self, rel: str) -> str:
        """路徑尾端加 @：路徑裡的 @（Unity 套件目錄 com.x@1.2）svn 會當成指定版本，尾端多一個 @ 才當普通路徑。"""
        return f"{self.root / rel}@"

    def ranges(self, base: str, rels: List[str], before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, List[Tuple[int, int]]]:
        """改到的檔：difflib 比 before 與工作樹 → 新版的改動行區間（只刪不加記成 (起, 起)，同 git diff 的算法）；沒有 before ＝整檔。"""
        out: Dict[str, List[Tuple[int, int]]] = {}
        for rel in rels:
            new = after.get(rel)
            if not isinstance(new, str):
                continue
            old = before.get(rel)
            old_lines = old.splitlines() if isinstance(old, str) else []
            ops = difflib.SequenceMatcher(None, old_lines, new.splitlines(), autojunk=False).get_opcodes()
            out[rel] = [(j1 + 1, max(j1 + 1, j2)) for tag, _, _, j1, j2 in ops if tag != "equal"]
        return out


# ─── 建圖的材料 ─────────────────────────────────────────────────────────────

def _ruler():
    """tools/reading-path.py（檔名有連字號，照路徑載入一次；量尺本體與 Graph 都在這裡）。"""
    mod = sys.modules.get("reading_path_tool")
    if mod is None:
        spec = importlib.util.spec_from_file_location("reading_path_tool", _TOOLS / "reading-path.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["reading_path_tool"] = mod
        spec.loader.exec_module(mod)
    return mod


def _rel(root: Path, path: str) -> Optional[str]:
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def _text(rp, path: Path):
    """工作樹的檔 → 文字；讀不了或解不開回例外（graph_of 列進解析失敗）。"""
    try:
        return rp.read_source(path)
    except (OSError, ValueError) as e:
        return e


def _decode(rp, data: bytes):
    """版控取出的舊版位元組 → 文字；解不開回例外（graph_of 列進解析失敗）。"""
    try:
        return rp.decode_source(data)
    except ValueError as e:
        return e


def _light_many(texts: Dict[str, str]) -> Dict[str, Any]:
    """輕量解析一批（每次照模組屬性取 parse_csharp）；單檔解析丟的例外放在那個檔的位置。"""
    out: Dict[str, Any] = {}
    for rel, text in texts.items():
        try:
            out[rel] = lang.parse_csharp(rel, text)
        except (ValueError, RecursionError) as e:
            out[rel] = e
    return out


def _touched(f: lang.Func, ranges: Optional[List[Tuple[int, int]]]) -> bool:
    return any(not (b < f.line or a > (f.end or f.line)) for a, b in ranges or ())


def _base_echo(f: lang.Func) -> bool:
    """本體只呼叫上層同名方法（base.M(…)）：空殼覆寫，算在類別空層，不另列只轉手。"""
    calls = [c for c in f.calls if not c.noise and c.kind != "prop"]
    return len(calls) == 1 and calls[0].kind == "super" and calls[0].name == f.name
