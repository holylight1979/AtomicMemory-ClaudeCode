"""reading_path_cs — C# 改動的閱讀路徑：只量改到的 .cs 加一跳上下游，不掃整個專案（純計算，hooks/wg_reading_path 的背景量測用）。

做什麼：
  範圍  改到的檔 → 下游＝它們直接用到的專案型別所在的檔（繼承、欄位／參數／區域變數型別、new、靜態呼叫 X.M 的 X；「檔名＝型別名」
        的排前面，再用 git grep 找定義）；上游＝提到改到的檔裡型別名的檔（git grep 名字，不解析）。上下游各最多 NEIGHBOR_MAX 檔。
        只有範圍內的檔會被讀進來解析；範圍外的呼叫照外部算，所以路徑是一跳範圍裡看得到的那一段，不是整個專案的最短路。
  建圖  範圍內的檔建 before（git 取 base 版）與 after（工作樹）兩張圖，用 tools/reading-path.py 的同一個 Graph 與 compare（找路、
        拐彎、狀態都跟 Python 版同一套）。分析器：本機有 .NET SDK 附的 Roslyn 就用 lib/cs_roslyn，沒有或跑不動用輕量解析
        （reading_path_lang.parse_csharp），兩種都註明在 notes。
  量    入口＝改到的函式（diff 命中）加上範圍內直接呼叫它們的函式。另列改到的函式裡只把呼叫往下傳的（量尺的 passthrough；
        只呼叫上層同名方法的覆寫不列，算在類別空層裡），與改到的型別的繼承鏈每層（lib/turn_metrics_cs，查找池＝範圍）。
回傳只有數據；門檻、要不要問、附什麼字由 hooks/wg_reading_path 決定。
怎麼跑：import 後呼叫 measure(root, base, changed, git)；不單獨跑。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Optional, Tuple

_TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.append(str(_TOOLS))
import reading_path_lang as lang  # noqa: E402
import cs_roslyn  # noqa: E402
import turn_metrics_cs as tmc  # noqa: E402
from turn_metrics import parse_diff_ranges  # noqa: E402

Git = Callable[[List[str], Optional[bytes]], Tuple[int, bytes]]   # (git 參數, stdin) → (結束碼, stdout)
NEIGHBOR_MAX = 40          # 上游、下游各最多幾檔（超過的照路徑排序截掉並註明）
SCOPE_POLICY = "一跳範圍"   # 報表上的範圍政策：前後兩版同一個，比較才不會判成母體不同
_DEF_RE = r"(^|[^A-Za-z0-9_])(class|struct|interface|record|enum)[[:space:]]+({})([^A-Za-z0-9_]|$)"


class MeasureError(Exception):
    """git 拿不到要的東西（追蹤清單、diff、before 版本）：這一批量不出來，呼叫端只附一句原因。"""


def measure(root: Path, base: str, changed: List[str], git: Git, deadline: float = float("inf")) -> Dict[str, Any]:
    """改到的 .cs（絕對路徑）→ {"scope": 解析過的相對路徑, "analyzer": "roslyn"｜"light", "notes": [說明],
    "rows": 量尺 compare 的每一列, "forwarders": 改到的只轉手函式, "classes": 改到的型別的繼承鏈}。
    git 失敗丟 MeasureError；Roslyn 跑不動自動改用輕量解析重來一次並註明。deadline：Roslyn 子行程的期限（time.monotonic）。"""
    root = Path(root).resolve()
    notes: List[str] = []
    rels = [r for r in (_rel(root, f) for f in changed) if r and (root / r).is_file()]   # 刪掉的檔沒有 after 可量
    tracked = _tracked(git)
    use = "roslyn" if cs_roslyn.find_roslyn() else "light"
    if use == "light":
        notes.append("找不到 .NET SDK 附的 Roslyn，用輕量解析")
    try:
        return _measure(root, base, rels, git, tracked, use, notes, deadline)
    except cs_roslyn.RoslynError as e:
        notes.append(f"Roslyn 跑不動（{e}），改用輕量解析")
        return _measure(root, base, rels, git, tracked, "light", notes, deadline)


def _measure(root: Path, base: str, rels: List[str], git: Git, tracked: List[str], use: str, notes: List[str],
             deadline: float) -> Dict[str, Any]:
    rp = _ruler()
    parse = (lambda texts: cs_roslyn.parse_many(texts, deadline)) if use == "roslyn" else _light_many
    texts = {r: _text(rp, root / r) for r in rels}
    mine = parse({r: t for r, t in texts.items() if isinstance(t, str)})
    mods = [m for m in mine.values() if isinstance(m, lang.Module)]
    down, cut_down = _downstream(mods, tracked, rels, git)
    up, cut_up = _upstream(mods, tracked, rels, git)
    notes += [f"{side}有 {n} 檔超過上限 {NEIGHBOR_MAX} 沒讀" for side, n in (("下游", cut_down), ("上游", cut_up)) if n]
    scope = sorted(r for r in set(rels) | set(down) | set(up) if (root / r).is_file())   # 追蹤中但工作樹已刪的鄰居不讀

    def parse_after(texts: Dict[str, str]) -> Dict[str, Any]:   # 改到的檔剛解析過，不再解析一次
        return {**parse({r: t for r, t in texts.items() if r not in mine}), **{r: mine[r] for r in texts if r in mine}}

    after = rp.graph_of(root, {r: root / r for r in scope}, SCOPE_POLICY, parse_cs=parse_after)
    before = rp.graph_of(root, _base_sources(rp, git, base, scope), SCOPE_POLICY, parse_cs=parse)
    notes += [f"解析不了：{e}" for e in after.scan["parse_errors"]]
    ranges = _ranges(git, base, rels)
    hits = [f for f in after.funcs.values() if f.lang == "cs" and _touched(f, ranges.get(f.file))]
    eids = sorted({f.id for f in hits} | {c.id for f in hits for c, _ in after.callers.get(f.id, [])})
    res = rp.compare(rp.graph_report(before, [e for e in eids if e in before.funcs]), rp.graph_report(after, eids))
    forwarders = [{"func": f.id, "file": str(root / f.file), "line": f.line, "end": f.end, "style": after.passthrough[f.id],
                   "targets": [e.dst for e in after.edges[f.id]]} for f in hits if f.id in after.passthrough and not _base_echo(f)]
    abs_ranges = {str(root / r): v for r, v in ranges.items()}   # 查找池只有一跳範圍：實作數是下限，不據此算「只有一個實作」
    side = tmc.metrics_for_files([str(root / r) for r in rels], abs_ranges, [str(root / r) for r in scope], partial_pool=True)
    notes += [f"{_rel(root, r['file'])}：{'；'.join(r['unparsed']) if r['kind'] == 'unparsed' else r['error']}"
              for r in side if r["kind"] in ("unparsed", "error")]
    return {"scope": scope, "analyzer": use, "notes": notes, "rows": res["rows"], "forwarders": forwarders,
            "classes": [r for r in side if r["kind"] == "class"]}


# ─── 範圍：一跳上下游 ─────────────────────────────────────────────────────────

def _tracked(git: Git) -> List[str]:
    """git 追蹤中的 .cs（相對路徑），去掉產生碼與量尺不掃的目錄（obj、bin、Library…）。"""
    rc, out = git(["ls-files", "-z", "--", "*.cs"], None)
    if rc != 0:
        raise MeasureError("git ls-files 失敗")
    rp = _ruler()
    return [n for n in out.decode("utf-8", "replace").split("\0") if n and not lang.GENERATED_RE.search(n) and not rp._skipped(n)]


def _type_refs(mod: lang.Module) -> List[str]:
    """一個檔直接用到的型別名，繼承的排前面：繼承、欄位、參數、區域變數、new、大寫開頭接收者的第一段（靜態呼叫）。"""
    bases = [b for c in mod.classes for b in c.bases]
    rest = [t for c in mod.classes for t in c.fields.values()]
    for f in mod.funcs:
        rest += [*f.param_types.values(), *f.local_types.values()]
        rest += [c.name if c.kind == "new" else c.recv.split(".")[0] for c in f.calls if c.kind == "new" or c.recv[:1].isupper()]
    names = [n.split("[")[0].rstrip("?") for n in bases + rest + [u.split(".")[-1] for u in mod.static_usings]]
    return list(dict.fromkeys(n for n in names if n[:1].isupper()))


def _downstream(mods: List[lang.Module], tracked: List[str], changed: List[str], git: Git) -> Tuple[List[str], int]:
    """改到的檔用到的型別所在的檔 → (檔, 截掉幾個)。照檔名（Pool.cs、Pool.Fill.cs 都是 Pool）的排前面；檔名對上的不一定是
    定義所在（Store.cs 裡可能不是 Store），所以全部型別名再一次 git grep 找定義，接在後面。"""
    defined = {c.name for m in mods for c in m.classes}
    want = [n for n in dict.fromkeys(n for m in mods for n in _type_refs(m)) if n not in defined]
    by_stem: Dict[str, List[str]] = {}
    for rel in tracked:
        by_stem.setdefault(PurePosixPath(rel).name.split(".")[0], []).append(rel)
    found = [r for n in want for r in by_stem.get(n, [])]
    if want:
        found += _grep(git, ["-E", "-e", _DEF_RE.format("|".join(want))], tracked)
    return _cap(found, changed)


def _upstream(mods: List[lang.Module], tracked: List[str], changed: List[str], git: Git) -> Tuple[List[str], int]:
    """提到改到的檔裡型別名的檔（整字比對，含註解與字串；寧可多讀一檔）→ (檔, 截掉幾個)。"""
    names = sorted({c.name for m in mods for c in m.classes})
    return _cap(_grep(git, ["-w", "-F", *[x for n in names for x in ("-e", n)]], tracked) if names else [], changed)


def _grep(git: Git, pattern: List[str], tracked: List[str]) -> List[str]:
    """git grep -l（工作樹的追蹤檔）→ 命中的 .cs，照路徑排序；沒命中（結束碼 1）→ 空。"""
    rc, out = git(["grep", "-l", "-z", *pattern, "--", "*.cs"], None)
    if rc not in (0, 1):
        raise MeasureError(f"git grep 失敗（結束碼 {rc}）")
    keep = set(tracked)
    return sorted(n for n in out.decode("utf-8", "replace").split("\0") if n in keep)


def _cap(found: List[str], changed: List[str]) -> Tuple[List[str], int]:
    """去重、去掉改到的檔，保留先找到的順序取前 NEIGHBOR_MAX 個 → (檔, 截掉幾個)。"""
    picked = [r for r in dict.fromkeys(found) if r not in set(changed)]
    return picked[:NEIGHBOR_MAX], max(0, len(picked) - NEIGHBOR_MAX)


# ─── 建圖的材料：工作樹與 before 版本、diff 區間 ───────────────────────────────────

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


def _light_many(texts: Dict[str, str]) -> Dict[str, Any]:
    """輕量解析一批（每次照模組屬性取 parse_csharp）；單檔解析丟的例外放在那個檔的位置。"""
    out: Dict[str, Any] = {}
    for rel, text in texts.items():
        try:
            out[rel] = lang.parse_csharp(rel, text)
        except (ValueError, RecursionError) as e:
            out[rel] = e
    return out


def _base_sources(rp, git: Git, base: str, scope: List[str]) -> Dict[str, Any]:
    """範圍內的檔在 base 的版本（git cat-file --batch 一次取完）→ {相對路徑: 文字或解碼例外}；base 沒有的檔（新檔）不在裡面。"""
    if not scope:
        return {}
    rc, out = git(["cat-file", "--batch"], "".join(f"{base}:{r}\n" for r in scope).encode("utf-8"))
    if rc != 0:
        raise MeasureError(f"取不到 before（{base}）的檔")
    got, i = {}, 0
    for rel in scope:
        nl = out.index(b"\n", i)
        head, i = out[i:nl].split(), nl + 1
        if len(head) != 3 or head[1] != b"blob":    # "<名字> missing"：base 沒有這個檔
            continue
        size = int(head[2])
        try:
            got[rel] = rp.decode_source(out[i:i + size])
        except ValueError as e:
            got[rel] = e
        i += size + 1
    return got


def _ranges(git: Git, base: str, rels: List[str]) -> Dict[str, List[Tuple[int, int]]]:
    """改到的檔對 base 的 diff 命中的行區間（新版行號，鍵＝相對路徑）。"""
    rc, out = git(["diff", "-U0", base, "--", *rels], None) if rels else (0, b"")
    if rc != 0:
        raise MeasureError(f"對 before（{base}）的 diff 拿不到")
    return parse_diff_ranges(out.decode("utf-8", "replace"))


def _touched(f: lang.Func, ranges: Optional[List[Tuple[int, int]]]) -> bool:
    return any(not (b < f.line or a > (f.end or f.line)) for a, b in ranges or ())


def _base_echo(f: lang.Func) -> bool:
    """本體只呼叫上層同名方法（base.M(…)）：空殼覆寫，算在類別空層，不另列只轉手。"""
    calls = [c for c in f.calls if not c.noise and c.kind != "prop"]
    return len(calls) == 1 and calls[0].kind == "super" and calls[0].name == f.name
