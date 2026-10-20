"""turn_metrics — 函式級與類別級側面數據（純函式，Python ast）：只算數據、不判臭。

做什麼：給一批 Python 檔（可附「這次改到的行區間」），回每個函式一筆、每個類別一筆 JSON 數據，交給 AI 判
「這一層／這個彎存在的理由是什麼、有沒有真正的作用、是不是抄舊架構長出來的」（G11）。程式不替 AI 判。
函式一筆：最大巢狀深度（nesting）、各自巢狀的條件區塊數（bumpy，Bumpy Road）、認知複雜度加分點總數（cognitive）、
  函式長度（length，只列）、只轉手（handoff：本體只有一句呼叫時是被呼叫的名字，否則 None）、連續轉手鏈長度
  （handoff_chain：從它起連續幾個只轉手的函式，呼叫對象在給的檔裡才接得下去）。
類別一筆：繼承鏈每一層新增／覆寫了哪些成員（layers），什麼都沒加的層標 empty（嫌疑：抄舊架構長出來的層）；
  鏈接到給的檔以外的基底（外部套件、內建）就停，記 unresolved_base。
非 Python 程式檔 → {"file", "lang": "不支援"}；解析失敗 → {"file", "error"}。
怎麼跑：python lib/turn_metrics.py <檔> … [--root 專案根] [--diff <unified diff 檔>]（--diff：只列 diff 命中的函式與類別）
  → 一行一筆 JSON，尾行 `TURN_METRICS DONE funcs=<n> classes=<n>`；或 import 後呼叫 metrics_for_files／parse_diff_ranges。
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_TRY = tuple(t for t in (getattr(ast, "Try", None), getattr(ast, "TryStar", None)) if t)
_MATCH = tuple(t for t in (getattr(ast, "Match", None),) if t)
_LOOPS = (ast.For, ast.AsyncFor, ast.While)
_WITHS = (ast.With, ast.AsyncWith)
COMPOUND = (ast.If,) + _LOOPS + _WITHS + _TRY + _MATCH      # 算巢狀深度的語句
_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)   # 巢狀定義各自算一筆，不算外層的深度
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")

Range = Tuple[int, int]


# ─── 巢狀、條件區塊、認知複雜度 ──────────────────────────────────────────────

def _is_elif(node: ast.If) -> bool:
    """orelse 只有一個 If → 是 elif：同一層，不加深度。"""
    return len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)


def _sub_bodies(s: ast.stmt) -> List[Tuple[List[ast.stmt], bool]]:
    """一個複合語句底下的各段語句 → [(語句清單, 算不算深一層)]。elif 的那段不算深一層。"""
    if isinstance(s, ast.If):
        return [(s.body, True), (s.orelse, not _is_elif(s))]
    if isinstance(s, _LOOPS):
        return [(s.body, True), (s.orelse, True)]
    if isinstance(s, _WITHS):
        return [(s.body, True)]
    if isinstance(s, _TRY):
        return [(s.body, True), *((h.body, True) for h in s.handlers), (s.orelse, True), (s.finalbody, True)]
    if isinstance(s, _MATCH):
        return [(c.body, True) for c in s.cases]
    return []


def _max_depth(stmts: Iterable[ast.stmt], depth: int) -> int:
    """這批語句（在 depth 層）底下最深到第幾層。"""
    worst = depth
    for s in stmts:
        if isinstance(s, _DEFS) or not isinstance(s, COMPOUND):
            continue
        for body, deeper in _sub_bodies(s):
            worst = max(worst, _max_depth(body, depth + 1 if deeper else depth))
    return worst


def _bumpy(body: List[ast.stmt]) -> int:
    """各自巢狀的條件區塊數（Bumpy Road）：函式第一層的複合語句裡，自己底下還有一層以上巢狀的有幾塊。"""
    return sum(1 for s in body if isinstance(s, COMPOUND) and _max_depth([s], 0) >= 2)


def _exprs(s: ast.stmt) -> Iterable[ast.expr]:
    """語句自己的運算式（不往底下的語句走）。"""
    for _, value in ast.iter_fields(s):
        if isinstance(value, ast.expr):
            yield value
        elif isinstance(value, list):
            for v in value:
                if isinstance(v, ast.expr):
                    yield v


def _expr_points(e: ast.expr, nesting: int, fname: str) -> int:
    """運算式裡的加分點：布林運算序列各 +1、三元 +1+巢狀、呼叫自己 +1。"""
    pts = 0
    for n in ast.walk(e):
        if isinstance(n, ast.BoolOp):
            pts += 1
        elif isinstance(n, ast.IfExp):
            pts += 1 + nesting
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == fname:
            pts += 1
    return pts


def _cognitive(stmts: Iterable[ast.stmt], nesting: int, fname: str) -> int:
    """認知複雜度加分點（照 SonarSource 的算法近似）：if／迴圈／except／match +1 再加目前巢狀數；elif／else +1；
    布林序列 +1；三元 +1 加巢狀；呼叫自己 +1；with 不加分；巢狀定義不算進外層。"""
    pts = 0
    for s in stmts:
        if isinstance(s, _DEFS):
            continue
        pts += sum(_expr_points(e, nesting, fname) for e in _exprs(s))
        if isinstance(s, ast.If):
            pts += 1 + nesting + _cognitive(s.body, nesting + 1, fname)
            if _is_elif(s):
                pts += _cognitive(s.orelse, nesting, fname) - nesting   # elif：+1、不吃巢狀加分
            elif s.orelse:
                pts += 1 + _cognitive(s.orelse, nesting + 1, fname)
        elif isinstance(s, _LOOPS):
            pts += 1 + nesting + _cognitive(s.body, nesting + 1, fname)
            if s.orelse:
                pts += 1 + _cognitive(s.orelse, nesting + 1, fname)
        elif isinstance(s, _WITHS):
            pts += _cognitive(s.body, nesting, fname)
        elif isinstance(s, _TRY):
            pts += _cognitive(s.body, nesting, fname) + _cognitive(s.orelse, nesting, fname) + _cognitive(s.finalbody, nesting, fname)
            for h in s.handlers:
                pts += 1 + nesting + _cognitive(h.body, nesting + 1, fname)
        elif isinstance(s, _MATCH):
            pts += 1 + nesting + sum(_cognitive(c.body, nesting + 1, fname) for c in s.cases)
    return pts


# ─── 只轉手 ────────────────────────────────────────────────────────────────

def _callee_name(e: ast.expr) -> Optional[str]:
    """呼叫對象的寫法：f、self.f、mod.f、a.b.c（點號鏈）。"""
    if isinstance(e, ast.Await):
        e = e.value
    if not isinstance(e, ast.Call):
        return None
    parts: List[str] = []
    f: ast.expr = e.func
    while isinstance(f, ast.Attribute):
        parts.append(f.attr)
        f = f.value
    if isinstance(f, ast.Name):
        parts.append(f.id)
    elif not parts:
        return None
    return ".".join(reversed(parts))


def _body_without_docstring(body: List[ast.stmt]) -> List[ast.stmt]:
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def _handoff(fn: ast.AST) -> Optional[str]:
    """本體只有一句呼叫（return f(...)、f(...)、await f(...)）→ 被呼叫的名字；否則 None。"""
    body = _body_without_docstring(list(fn.body))
    if len(body) != 1:
        return None
    s = body[0]
    if isinstance(s, ast.Return) and s.value is not None:
        return _callee_name(s.value)
    if isinstance(s, ast.Expr):
        return _callee_name(s.value)
    return None


# ─── 單檔：函式與類別 ───────────────────────────────────────────────────────

def _walk_defs(nodes: Iterable[ast.AST], prefix: str):
    """(限定名, 節點) 逐個產出：類別方法 Cls.m、巢狀函式 outer.inner。"""
    for n in nodes:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            q = f"{prefix}{n.name}"
            yield q, n
            yield from _walk_defs(n.body, q + ".")
        elif isinstance(n, ast.ClassDef):
            q = f"{prefix}{n.name}"
            yield q, n
            yield from _walk_defs(n.body, q + ".")
        elif isinstance(n, COMPOUND):
            for body, _ in _sub_bodies(n):
                yield from _walk_defs(body, prefix)


def _class_members(cls: ast.ClassDef) -> List[str]:
    """類別自己定義的成員：方法與類別層級的指派（含型別標注指派）。"""
    out: List[str] = []
    for s in cls.body:
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(s.name)
        elif isinstance(s, ast.Assign):
            out += [t.id for t in s.targets if isinstance(t, ast.Name)]
        elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
            out.append(s.target.id)
    return list(dict.fromkeys(out))


def _base_names(cls: ast.ClassDef) -> List[str]:
    out = []
    for b in cls.bases:
        if isinstance(b, ast.Name):
            out.append(b.id)
        elif isinstance(b, ast.Attribute):
            out.append(b.attr)         # mod.Base → 只拿 Base（同名碰撞時以同檔優先）
        elif isinstance(b, ast.Subscript) and isinstance(b.value, ast.Name):
            out.append(b.value.id)     # Generic[T] → Generic
    return out


def function_metrics(src: str, path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """一個 Python 檔的原始碼 → (每函式一筆, 每類別一筆)。類別那筆只有自己這層的成員與基底名，鏈要跨檔用 metrics_for_files 接。
    解析失敗丟 SyntaxError 給呼叫端決定。"""
    tree = ast.parse(src, filename=path)
    funcs: List[Dict[str, Any]] = []
    classes: List[Dict[str, Any]] = []
    for qual, node in _walk_defs(tree.body, ""):
        end = getattr(node, "end_lineno", None) or node.lineno
        if isinstance(node, ast.ClassDef):
            classes.append({"file": path, "name": qual, "lineno": node.lineno, "end_lineno": end,
                            "members": _class_members(node), "bases": _base_names(node)})
            continue
        body = list(node.body)
        funcs.append({"file": path, "name": qual, "lineno": node.lineno, "end_lineno": end,
                      "length": end - node.lineno + 1, "nesting": _max_depth(body, 0), "bumpy": _bumpy(body),
                      "cognitive": _cognitive(body, 0, node.name), "handoff": _handoff(node)})
    return funcs, classes


# ─── 多檔：diff 命中、轉手鏈、繼承鏈 ───────────────────────────────────────────

def parse_diff_ranges(diff_text: str) -> Dict[str, List[Range]]:
    """unified diff → {新版路徑: [(起, 迄) 行區間]}。只刪不加的 hunk 記成 (起, 起)（落在哪個函式就算改到它）。"""
    out: Dict[str, List[Range]] = {}
    cur: Optional[str] = None
    for line in str(diff_text or "").splitlines():
        m = _FILE_RE.match(line)
        if m:
            cur = m.group(1).strip()
            out.setdefault(cur, [])
            continue
        m = _HUNK_RE.match(line)
        if m and cur is not None:
            start, count = int(m.group(1)), int(m.group(2)) if m.group(2) is not None else 1
            out[cur].append((start, max(start, start + count - 1)))
    return out


def _norm(p: str) -> str:
    return os.path.normcase(os.path.realpath(p))   # realpath：Windows 8.3 短檔名（HOLYLI~1）與長檔名對得上


def _overlaps(row: Dict[str, Any], ranges: List[Range]) -> bool:
    return any(not (b < row["lineno"] or a > row["end_lineno"]) for a, b in ranges)


def _chain_len(name: str, edges: Dict[str, str]) -> int:
    """從 name 起連續幾個只轉手的函式（含自己）；對象不在清單裡就停；碰到環停。"""
    n, cur, seen = 0, name, set()
    while cur in edges and cur not in seen:
        seen.add(cur)
        n += 1
        cur = edges[cur]
    return n


def _resolve_handoffs(funcs: List[Dict[str, Any]]) -> None:
    """handoff_chain：對象用限定名的尾段對（f、Cls.f、self.f 都對 f；同名多個取第一個）。"""
    by_tail: Dict[str, str] = {}
    for f in funcs:
        by_tail.setdefault(f["name"].rsplit(".", 1)[-1], f["name"])
    edges = {f["name"]: by_tail.get(str(f["handoff"]).rsplit(".", 1)[-1], "") for f in funcs if f.get("handoff")}
    for f in funcs:
        f["handoff_chain"] = _chain_len(f["name"], edges) if f.get("handoff") else 0


def _inherit_layers(cls: Dict[str, Any], index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """沿第一個基底往上接：每層 added＝這層定義、上面所有層都沒有的成員；overridden＝上面有、這層又定義的；
    empty＝這層什麼都沒定義。接不到的基底記 unresolved_base 並停。"""
    chain: List[Dict[str, Any]] = []
    seen: set = set()
    cur: Optional[Dict[str, Any]] = cls
    unresolved: Optional[str] = None
    while cur is not None and cur["name"] not in seen:
        seen.add(cur["name"])
        chain.append(cur)
        bases = cur.get("bases") or []
        if not bases:
            break
        nxt = index.get(bases[0].rsplit(".", 1)[-1])
        if nxt is None:
            unresolved = bases[0]
            break
        cur = nxt
    layers: List[Dict[str, Any]] = []
    above: set = set()
    for c in reversed(chain):        # 從最上層往下算 added／overridden
        mem = list(c.get("members") or [])
        layers.append({"name": c["name"], "file": c["file"], "added": [m for m in mem if m not in above],
                       "overridden": [m for m in mem if m in above], "empty": not mem})
        above |= set(mem)
    layers.reverse()                  # 回到「自己在前、祖先在後」
    return {"file": cls["file"], "name": cls["name"], "lineno": cls["lineno"], "end_lineno": cls["end_lineno"],
            "depth": len(layers), "empty_layers": sum(1 for l in layers if l["empty"]),
            "unresolved_base": unresolved, "layers": layers}


def metrics_for_files(files: Iterable[str], ranges: Optional[Dict[str, List[Range]]] = None,
                      resolve_files: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """多檔 → 一筆一 dict（函式 kind=func、類別 kind=class、不支援 kind=unsupported、解析失敗 kind=error）。
    ranges 給了就只列落在區間裡的函式與類別（鍵是路徑，與 files 用 normcase＋abspath 對）。
    resolve_files：接轉手鏈與繼承鏈時可查的檔（預設＝files）；只拿來查對象，不列進結果。"""
    want = {_norm(k): v for k, v in (ranges or {}).items()}
    rows: List[Dict[str, Any]] = []
    all_funcs: List[Dict[str, Any]] = []
    index: Dict[str, Dict[str, Any]] = {}
    listed = [str(f) for f in files]
    pool = list(dict.fromkeys(listed + [str(f) for f in (resolve_files or [])]))
    parsed: Dict[str, Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]] = {}
    for f in pool:
        if not f.lower().endswith(".py"):
            continue
        try:
            parsed[f] = function_metrics(Path(f).read_text(encoding="utf-8", errors="replace"), f)
        except (OSError, SyntaxError, ValueError) as e:
            parsed[f] = ([], [])
            if f in listed:
                rows.append({"kind": "error", "file": f, "error": f"{type(e).__name__}: {e}"[:160]})
        funcs, classes = parsed[f]
        all_funcs += funcs
        for c in classes:
            index.setdefault(c["name"].rsplit(".", 1)[-1], c)
    _resolve_handoffs(all_funcs)
    for f in listed:
        if not f.lower().endswith(".py"):
            rows.append({"kind": "unsupported", "file": f, "lang": "不支援"})
            continue
        funcs, classes = parsed.get(f, ([], []))
        hit = want.get(_norm(f))
        rows += [{"kind": "func", **r} for r in funcs if ranges is None or (hit and _overlaps(r, hit))]
        rows += [{"kind": "class", **_inherit_layers(c, index)} for c in classes if ranges is None or (hit and _overlaps(c, hit))]
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="函式級與類別級側面數據（只算不判）：一行一筆 JSON，尾行 TURN_METRICS DONE。")
    ap.add_argument("files", nargs="+", help="要列的 Python 檔")
    ap.add_argument("--diff", help="unified diff 檔：只列命中的函式與類別（路徑相對 --root）")
    ap.add_argument("--root", default=".", help="diff 裡路徑的根")
    ap.add_argument("--resolve", nargs="*", default=[], help="接轉手鏈與繼承鏈時另外可查的 Python 檔")
    a = ap.parse_args(argv)
    ranges = None
    if a.diff:
        raw = parse_diff_ranges(Path(a.diff).read_text(encoding="utf-8", errors="replace"))
        ranges = {str(Path(a.root) / k): v for k, v in raw.items()}
    rows = metrics_for_files(a.files, ranges, a.resolve)
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    print(f"TURN_METRICS DONE funcs={sum(r['kind'] == 'func' for r in rows)} classes={sum(r['kind'] == 'class' for r in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
