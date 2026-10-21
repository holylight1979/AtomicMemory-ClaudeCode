"""turn_metrics_cs — C# 的函式級與類別級側面數據（純函式，不用 Roslyn）：與 turn_metrics 同一組指標、同欄位名，只算數據、不判臭。

做什麼：給一批 .cs 檔（可附「這次改到的行區間」），回每個方法一筆、每個型別一筆 JSON 數據，交給 AI 判「這一層／這個彎存在的理由是什麼、
  有沒有真正的作用」（G11）。切詞重用 tools/reading_path_lang.py（大括號配對、class／成員切分、參數切分），方法本體另用小型遞迴
  解析成 if／迴圈／switch／try／using 與區塊 lambda 的樹，再照 turn_metrics 的算法算。
函式一筆：nesting、bumpy、cognitive、length、handoff（本體只有一個呼叫時是被呼叫的寫法）、handoff_chain（從它起連續只轉手的個數；
  經過「只有一個實作的介面或抽象類別」那一手也算一個，記在 dispatch）。建構子叫 .ctor（同 Python 的 __init__），屬性的 get／set
  本體各一筆；沒有本體的宣告（介面、abstract）不列。
類別一筆：沿第一個基底（類別或介面）往上接，每層 added／overridden、空層 empty；這層的成員若只有「只呼叫 base 同名方法、引數照傳」
  「override 空本體」「建構子空本體」（記在 hollow），也算空層。另列 type_kind、interfaces（每個介面掃到的實作）、implementations
  （介面與抽象類別掃到的具體實作，經由父類別繼承到的也算；只數得到給的檔）。
解析不到：每筆多 unparsed（哪裡沒解析到）與 confidence（full／partial）；檔案層的問題（大括號不成對、不在任何型別裡的程式）另出
  一筆 kind=unparsed，其中大括號不成對會讓成員範圍錯位，同檔每筆信心都降為 partial。看不到不當成沒有：#else／#elif 兩支都算、本體某句解析斷掉就從下一行接著解析、轉手對象的型別卡在掃得到的檔裡
  就註明鏈可能更長。註解與字串自己遮（插值洞裡的字串、原始字串、@"" 跳脫都認得），不用量尺那支正規式。
怎麼跑：python lib/turn_metrics_cs.py <檔> … [--root 專案根] [--diff <unified diff 檔>] [--resolve <檔> …]
  → 一行一筆 JSON，尾行 `TURN_METRICS_CS DONE funcs=<n> classes=<n> partial=<n> unparsed_files=<n>`；或 import 後呼叫 metrics_for_files。
"""
from __future__ import annotations

import bisect
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_TOOLS = str(Path(__file__).resolve().parents[1] / "tools")
if _TOOLS not in sys.path:
    sys.path.append(_TOOLS)   # C# 切詞與閱讀路徑量尺共用一份
import reading_path_lang as lang  # noqa: E402
from turn_metrics import Range, _norm, _overlaps, hollow_text, parse_diff_ranges  # noqa: E402  空殼判準兩語言共用

_TYPE_WORDS = {"class", "struct", "interface", "enum", "record", "delegate"}
_ATTR_PREV = {"", ";", "{", "}", "]", "(", ","}   # attribute 區段 [X] 前面會是這些（陣列下標前面是識別字）
_PREPROC = re.compile(r"^[ \t]*#[^\n]*", re.M)
_PREPROC_BRANCH = re.compile(r"^[ \t]*#\s*(?:elif|else)\b", re.M)   # 兩支擇一的才會把兩支併進來；只有 #if 的是多算一段可選的碼
_STR_START = re.compile(r'(?:\$+@?|@\$*)?"')
_CHAR_LIT = re.compile(r"'(?:\\.[^'\n]*|[^'\\\n])'")
_CODE_STOP = re.compile(r"""//|/\*|['"$@]""")
_HOLE_STOP = re.compile(r"""//|/\*|['"$@(){}\[\]:]""")
_CTOR_INIT = re.compile(r"\)\s*:\s*(?:base|this)\s*\(.*$", re.S)
_CTOR_ARGS = re.compile(r":\s*(?:base|this)\s*\((.*)\)\s*$", re.S)
_OPERATOR = re.compile(r"\boperator\s*([^\s(]+)\s*\((?P<params>[^()]*)\)")
_ACCESSOR = re.compile(r"\b(get|set|init|add|remove)\s*(\{|=>)")
_LAMBDA_OPEN = re.compile(r"=>\s*\{|\bdelegate\s*(?:\([^()]*\))?\s*\{")
_TERNARY = re.compile(r"(?<=[\s)\]])\?(?=\s)")
_SWITCH_EXPR = re.compile(r"\bswitch\s*\{")
_LABEL = re.compile(r"[A-Za-z_]\w*\s*:(?!:)")
_LOCAL_FUNC = re.compile(
    r"(?:(?:static|async|unsafe|extern)\s+)*"
    r"(?!(?:return|await|new|throw|yield|else|case|goto|var|using|lock|fixed|if|for|foreach|while|switch|do|try|const|ref|out)\b)"
    r"[A-Za-z_][\w.]*(?:\s*<[^;{}()]*>)?(?:\s*\[[\s,]*\])*\??\s+[A-Za-z_]\w*\s*(?:<[^;{}()]*>)?\s*\(")
_IDENT = re.compile(r"[A-Za-z_]\w*")
_AWAIT = re.compile(r"await\s+")
_RETURN = re.compile(r"return\b\s*")
_NOT_A_CALL = re.compile(r"(?:throw|yield)\b")
_CTOR_PASS = re.compile(r":\s*(?:base|this)\s*\(")
_MODS = r"(?:(?:public|private|protected|internal|static|sealed|abstract|partial|readonly|unsafe|new|file)\s+)*"
_ENUM = re.compile(_MODS + r"\benum\s+\w+[^{;]*\{")
_NS_BLOCK = re.compile(r"\bnamespace\s+[\w.]+\s*\{")
_USING_NS = re.compile(r"^\s*using\s+(?:static\s+)?([A-Za-z_][\w.]*)\s*;", re.M)
_TOP_DECL = re.compile(r"\b(?:global\s+)?using\s+[^;{}()]*;|\bextern\s+alias\s+\w+\s*;|\bnamespace\s+[\w.]+\s*;|"
                       + _MODS + r"\bdelegate\b[^;{}]*;")
CTOR, CCTOR = ".ctor", ".cctor"


# ─── 字元層小工具 ──────────────────────────────────────────────────────────────

def _close(text: str, i: int, end: int, o: str, c: str) -> Optional[int]:
    """text[i] 是開括號 o → 對應的 c 的位置；不成對 → None。"""
    if i >= end or text[i] != o:
        return None
    d = 0
    for k in range(i, end):
        if text[k] == o:
            d += 1
        elif text[k] == c:
            d -= 1
            if d == 0:
                return k
    return None


def _semicolon(src: str, pairs: Dict[int, int], i: int, end: int) -> Optional[int]:
    """從 i 起、括號外第一個分號的位置（大括號整段跳過）；先碰到多出來的右括號或到底 → None。"""
    d = 0
    while i < end:
        c = src[i]
        if c == "{":
            close = pairs.get(i)
            if close is None or close >= end:
                return None
            i = close + 1
            continue
        if c in "([":
            d += 1
        elif c in ")]":
            d -= 1
            if d < 0:
                return None
        elif c == "}":
            return None
        elif c == ";" and d == 0:
            return i
        i += 1
    return None


def _blank_literals(text: str) -> Tuple[str, List[int]]:
    """註解換成等長空白；字串與字元常值也換成空白，但開頭留一個引號當記號：`return $"{F(x)}.png";` 才不會被看成單純呼叫 F。
    插值的 {運算式} 照留（洞裡的字串照樣遮，: 之後的格式字串遮掉）；認得 "…"、@"…"（"" 跳脫）、$"…"、$@"…"、
    原始字串 \"\"\"…\"\"\"（可帶 $）、'x'。換行一律留著，行號不跑。回 (遮好的原始碼, 原始插值字串的位置)：那種洞整段遮掉、沒算。"""
    out = list(text)
    n = len(text)
    raw_holes: List[int] = []

    def blank(a: int, b: int) -> None:
        out[a:b] = ["\n" if ch == "\n" else " " for ch in text[a:b]]

    def code(i: int, hole: bool) -> int:
        """掃程式碼；hole＝插值的 {運算式}：碰到同層的 } 停在它上面、碰到同層的 : 把格式字串遮到 }。"""
        depth, stop = 0, _HOLE_STOP if hole else _CODE_STOP
        while True:
            m = stop.search(text, i)
            if m is None:
                return n
            i, tok = m.start(), m.group()
            if tok == "//":
                j = text.find("\n", i)
                j = n if j < 0 else j
            elif tok == "/*":
                j = text.find("*/", i + 2)
                j = n if j < 0 else j + 2
            elif tok == "'" and _CHAR_LIT.match(text, i):
                j = _CHAR_LIT.match(text, i).end()
            elif tok in "\"$@" and _STR_START.match(text, i):
                i = string(i, _STR_START.match(text, i).end() - 1)
                continue
            else:
                if tok in "([{":
                    depth += 1
                elif tok in ")]}":
                    if tok == "}" and depth == 0:
                        return i
                    depth -= 1
                elif tok == ":" and depth == 0 and text[i + 1:i + 2] != ":" and text[i - 1:i] != ":":
                    j = text.find("}", i)
                    blank(i, n if j < 0 else j)
                    return n if j < 0 else j
                i += 1
                continue
            blank(i, j)
            if tok == "'":
                out[i] = "'"
            i = j

    def string(i: int, q: int) -> int:
        """字串從 i 起（前綴 $／@ 在 i..q，第一個引號在 q）→ 遮掉、回結尾之後的位置。"""
        pre, run = text[i:q], q
        while run < n and text[run] == '"':
            run += 1
        if run - q >= 3 and "@" not in pre:                 # 原始字串：結尾是同樣多的引號
            j = text.find('"' * (run - q), run)
            j = n if j < 0 else j + run - q
            if "$" in pre and "{" in text[run:j]:
                raw_holes.append(i)
            blank(i, j)
            out[i] = '"'
            return j
        blank(i, q + 1)
        out[i] = '"'
        k, verbatim, holes = q + 1, "@" in pre, "$" in pre
        while k < n:
            c = text[k]
            if c == '"' and verbatim and text.startswith('""', k):
                blank(k, k + 2)
                k += 2
            elif c == '"':
                blank(k, k + 1)
                return k + 1
            elif c == "\\" and not verbatim:
                blank(k, k + 2)
                k += 2
            elif c == "\n" and not verbatim:                 # 沒收尾的一般字串：停在行尾
                return k
            elif holes and text.startswith(("{{", "}}"), k):
                blank(k, k + 2)
                k += 2
            elif holes and c == "{":
                blank(k, k + 1)
                k = code(k + 1, True)
                blank(k, k + 1)
                k += 1
            else:
                blank(k, k + 1)
                k += 1
        return n

    code(0, False)
    return "".join(out), raw_holes


def _strip_generics(text: str) -> str:
    """拿掉所有層的 <…>（Dictionary<int, Dictionary<…>> 的逗號才不會被當成分隔）。"""
    while True:
        stripped = re.sub(r"<[^<>]*>", "", text)
        if stripped == text:
            return text
        text = stripped


def _blank_attributes(src: str) -> str:
    """attribute 區段 [X(…)] 換成等長空白（換行留著）：裡面的大括號不會被當成成員本體，標頭也乾淨。"""
    out = list(src)
    prev, i, n = "", 0, len(src)
    while i < n:
        ch = src[i]
        if ch == "[" and prev in _ATTR_PREV:
            k = i + 1
            while k < n and src[k].isspace():
                k += 1
            j = _close(src, i, n, "[", "]") if k < n and (src[k].isalpha() or src[k] == "_") else None
            if j is not None:
                out[i:j + 1] = ["\n" if c == "\n" else " " for c in src[i:j + 1]]
                prev, i = "]", j + 1
                continue
        if not ch.isspace():
            prev = ch
        i += 1
    return "".join(out)


def _code_only(src: str) -> str:
    """遮好字串的原始碼再遮掉前置處理行與 attribute 區段：class 標頭的基底清單裡夾 #if 行（protobuf 產生碼常見）也讀得對。"""
    return _blank_attributes(_PREPROC.sub(lambda m: " " * len(m.group()), src))


def _generic_end(e: str, i: int) -> Optional[int]:
    d = 0
    for k in range(i, len(e)):
        ch = e[k]
        if ch == "<":
            d += 1
        elif ch == ">":
            d -= 1
            if d == 0:
                return k
        elif not (ch.isalnum() or ch in "_ ,.[]?\t\n"):
            return None
    return None


def _call_of(expr: str) -> Optional[Tuple[str, str]]:
    """整個運算式就是一個呼叫 → (被呼叫的寫法, 最後那次呼叫的引數原文)；否則 None。寫法同 turn_metrics：點號鏈
    （a.b、this.f、base.f、x?.y）；呼叫結果上再呼叫只留最後一段（a().b() → b）；建構是 new T。"""
    e = expr.strip()
    m = _AWAIT.match(e)
    if m:
        e = e[m.end():]
    m = re.match(r"new\s+", e)
    is_new, i, n = bool(m), (m.end() if m else 0), len(e)
    m = _IDENT.match(e, i)
    if not m or (m.group() in lang.CS_KEYWORDS and m.group() not in ("this", "base")):
        return None
    segs, last, args, calls, i = [m.group()], "", "", 0, m.end()
    while i < n:
        ch = e[i]
        if ch.isspace():
            i += 1
        elif ch == "<":
            j = _generic_end(e, i)
            if j is None:
                return None
            i = j + 1
        elif ch == "(":
            j = _close(e, i, n, "(", ")")
            if j is None or not segs:
                return None
            last = ("new " if is_new and not calls else "") + ".".join(segs)
            args, calls, segs, i = e[i + 1:j], calls + 1, [], j + 1
        elif ch == "!" and not e.startswith("!=", i):
            i += 1                                      # null 寬容運算子 x!.F()
        elif ch == "." or e.startswith("?.", i):
            i += 2 if ch == "?" else 1
            while i < n and e[i].isspace():
                i += 1
            m = _IDENT.match(e, i)
            if not m:
                return None
            segs.append(m.group())
            i = m.end()
        else:
            return None
    return (last, args) if calls and not segs else None


def _same_args(args: str, params: List[str]) -> bool:
    return [re.sub(r"^(?:ref|out|in)\s+", "", a) for a in lang._split_top(args)] == params


# ─── 方法本體 → 流程結構樹 ──────────────────────────────────────────────────────

class _Body:
    """方法本體 → 只認流程結構的陳述式樹。節點 t：if／loop／switch／try／with（using、lock、fixed）／block／simple；
    每個節點的 lambdas＝它自己那段文字裡的區塊 lambda、匿名方法、區域函式本體（各自深一層）。解析斷掉記進 notes，從下一行接著解析。"""

    def __init__(self, src: str, pairs: Dict[int, int], line_of):
        self.src, self.pairs, self.line_of = src, pairs, line_of
        self.notes: List[str] = []

    def _ws(self, i: int, end: int) -> int:
        while i < end and self.src[i].isspace():
            i += 1
        return i

    def _word(self, i: int) -> str:
        m = _IDENT.match(self.src, i)
        return m.group() if m else ""

    def _after(self, i: int, word: str, end: int) -> int:
        return self._ws(i + len(word), end)

    def _next_line(self, i: int, end: int) -> int:
        nl = self.src.find("\n", i, end)
        return end if nl < 0 else nl + 1

    def stmts(self, i: int, end: int) -> List[dict]:
        out = []
        while True:
            i = self._ws(i, end)
            if i >= end:
                return out
            node, nxt = self.stmt(i, end)
            if node:
                out.append(node)
            i = max(nxt, i + 1)

    def stmt(self, i: int, end: int) -> Tuple[Optional[dict], int]:
        i = self._ws(i, end)
        if i >= end:
            return None, end
        s = self.src
        if s[i] == ";":
            return None, i + 1
        if s[i] == "{":
            close = self.pairs.get(i)
            if close is None or close >= end:
                return self._broken(i, end, "的大括號不成對")
            return {"t": "block", "body": self.stmts(i + 1, close)}, close + 1
        w = self._word(i)
        if w == "await" and self._word(self._after(i, w, end)) in ("foreach", "using"):
            i = self._after(i, w, end)
            w = self._word(i)
        k = self._after(i, w, end) if w else i
        nxt = s[k] if k < end else ""
        if w == "if" and nxt == "(":
            return self._if(i, end)
        if w in ("for", "foreach", "while") and nxt == "(":
            return self._headed(i, end, w, "loop")
        if w in ("using", "lock", "fixed") and nxt == "(":
            return self._headed(i, end, w, "with")
        if w == "switch" and nxt == "(":
            return self._switch(i, end)
        if w == "do":
            return self._do(i, end)
        if w == "try" and nxt == "{":
            return self._try(i, end)
        if w in ("checked", "unchecked", "unsafe") and nxt == "{":
            return self.stmt(k, end)
        if w == "else":
            self.notes.append(f"第 {self.line_of(i)} 行有接不上 if 的 else")
            return self.stmt(k, end)
        if w and w not in lang.CS_KEYWORDS:
            m = _LABEL.match(s, i)
            if m and m.end() < end:
                return self.stmt(m.end(), end)
            m = _LOCAL_FUNC.match(s, i)
            got = self._local_func(m, end) if m else None
            if got:
                return got
        return self._simple(i, end)

    def expr(self, i: int, j: int) -> Tuple[str, List[List[dict]]]:
        """一段運算式 → (拿掉區塊 lambda 本體後的文字, 各區塊 lambda 的陳述式)。"""
        parts, lams, pos = [], [], i
        for m in _LAMBDA_OPEN.finditer(self.src, i, j):
            k = m.end() - 1
            close = self.pairs.get(k)
            if m.start() < pos or close is None or close >= j:
                continue
            parts.append(self.src[pos:m.start()])
            lams.append(self.stmts(k + 1, close))
            pos = close + 1
        parts.append(self.src[pos:j])
        return " ".join(parts), lams

    def _broken(self, i: int, end: int, why: str) -> Tuple[dict, int]:
        self.notes.append(f"第 {self.line_of(i)} 行{why}，從下一行接著解析")
        nxt = self._next_line(i, end)
        text, lams = self.expr(i, nxt)
        return {"t": "simple", "text": text, "lambdas": lams}, nxt

    def _simple(self, i: int, end: int) -> Tuple[dict, int]:
        j = _semicolon(self.src, self.pairs, i, end)
        if j is None:
            return self._broken(i, end, "找不到陳述式結尾的分號")
        text, lams = self.expr(i, j)
        return {"t": "simple", "text": text, "lambdas": lams}, j + 1

    def _if(self, i: int, end: int) -> Tuple[dict, int]:
        k = self._after(i, "if", end)
        j = _close(self.src, k, end, "(", ")")
        if j is None:
            return self._broken(i, end, "的 if 條件括號不成對")
        cond, lams = self.expr(k + 1, j)
        body, nxt = self.stmt(j + 1, end)
        node = {"t": "if", "cond": cond, "lambdas": lams, "body": [body] if body else [], "orelse": []}
        k = self._ws(nxt, end)
        if self._word(k) == "else":
            other, nxt = self.stmt(k + 4, end)
            node["orelse"] = [other] if other else []
        return node, nxt

    def _headed(self, i: int, end: int, w: str, kind: str) -> Tuple[dict, int]:
        k = self._after(i, w, end)
        j = _close(self.src, k, end, "(", ")")
        if j is None:
            return self._broken(i, end, f"的 {w} 括號不成對")
        head, lams = self.expr(k + 1, j)
        body, nxt = self.stmt(j + 1, end)
        return {"t": kind, "head": head, "lambdas": lams, "body": [body] if body else []}, nxt

    def _do(self, i: int, end: int) -> Tuple[dict, int]:
        body, nxt = self.stmt(i + 2, end)
        node = {"t": "loop", "head": "", "lambdas": [], "body": [body] if body else []}
        k = self._ws(nxt, end)
        j = _close(self.src, self._after(k, "while", end), end, "(", ")") if self._word(k) == "while" else None
        if j is None:
            self.notes.append(f"第 {self.line_of(i)} 行的 do 找不到 while 條件")
            return node, nxt
        node["head"], node["lambdas"] = self.expr(self._after(k, "while", end) + 1, j)
        nxt = self._ws(j + 1, end)
        return node, nxt + 1 if nxt < end and self.src[nxt] == ";" else nxt

    def _switch(self, i: int, end: int) -> Tuple[dict, int]:
        k = self._after(i, "switch", end)
        j = _close(self.src, k, end, "(", ")")
        b = self._ws(j + 1, end) if j is not None else end
        close = self.pairs.get(b) if b < end and self.src[b] == "{" else None
        if j is None or close is None or close >= end:
            return self._broken(i, end, "的 switch 讀不出本體")
        head, lams = self.expr(k + 1, j)
        return {"t": "switch", "head": head, "lambdas": lams, "cases": self._cases(b + 1, close)}, close + 1

    def _label_end(self, i: int, end: int) -> Optional[int]:
        d, s = 0, self.src
        for k in range(i, end):
            c = s[k]
            if c in "([{":
                d += 1
            elif c in ")]}":
                d -= 1
            elif c == ";":
                return None
            elif c == ":" and d == 0 and s[k - 1] != ":" and (k + 1 >= end or s[k + 1] != ":"):
                return k + 1
        return None

    def _cases(self, i: int, end: int) -> List[List[dict]]:
        """switch 本體 → 每組標籤底下的陳述式（連續的標籤併成一組）。"""
        out: List[List[dict]] = []
        cur: Optional[List[dict]] = None
        while True:
            i = self._ws(i, end)
            if i >= end:
                return out
            w = self._word(i)
            is_label = w == "case" or (w == "default" and self.src.startswith(":", self._after(i, w, end)))
            label = self._label_end(i, end) if is_label else None
            if label is not None:
                if cur is None or cur:
                    cur = []
                    out.append(cur)
                i = label
                continue
            node, nxt = self._broken(i, end, "的 case 標籤找不到冒號") if is_label else self.stmt(i, end)
            if cur is None:
                cur = []
                out.append(cur)
            if node:
                cur.append(node)
            i = max(nxt, i + 1)

    def _try(self, i: int, end: int) -> Tuple[dict, int]:
        body, nxt = self.stmt(self._after(i, "try", end), end)
        node = {"t": "try", "body": [body] if body else [], "handlers": [], "final": [], "lambdas": []}
        while True:
            k = self._ws(nxt, end)
            w = self._word(k)
            if w == "finally":
                fin, nxt = self.stmt(self._after(k, w, end), end)
                node["final"] = [fin] if fin else []
                continue
            if w != "catch":
                return node, nxt
            k = self._after(k, w, end)
            if k < end and self.src[k] == "(":
                j = _close(self.src, k, end, "(", ")")
                if j is None:
                    self.notes.append(f"第 {self.line_of(k)} 行的 catch 括號不成對")
                    return node, self._next_line(k, end)
                k = self._ws(j + 1, end)
            head = ""
            if self._word(k) == "when":
                k2 = self._after(k, "when", end)
                j = _close(self.src, k2, end, "(", ")")
                if j is not None:
                    head, _ = self.expr(k2 + 1, j)
                    k = self._ws(j + 1, end)
            h, nxt = self.stmt(k, end)
            node["handlers"].append({"head": head, "body": [h] if h else []})

    def _local_func(self, m: re.Match, end: int) -> Optional[Tuple[dict, int]]:
        """區域函式 `T Name(…) { … }` → 本體當一層 lambda；運算式本體（=>）照一般陳述式讀到分號。"""
        j = _close(self.src, m.end() - 1, end, "(", ")")
        if j is None:
            return None
        b = self._ws(j + 1, end)
        if self._word(b) == "where":
            while b < end and self.src[b] not in "{;=":
                b += 1
        close = self.pairs.get(b) if b < end and self.src[b] == "{" else None
        if close is None or close >= end:
            return None
        return {"t": "simple", "text": "", "lambdas": [self.stmts(b + 1, close)]}, close + 1


# ─── 巢狀、條件區塊、認知複雜度（同 turn_metrics 的算法） ───────────────────────────

def _is_elif(n: dict) -> bool:
    return len(n["orelse"]) == 1 and n["orelse"][0]["t"] == "if"


def _subs(n: dict) -> List[Tuple[List[dict], bool]]:
    """節點底下的各段陳述式 → [(陳述式, 算不算深一層)]。else if 那段、裸大括號不算深一層；區塊 lambda 算。"""
    t = n["t"]
    out = [(lam, True) for lam in n.get("lambdas", ())]
    if t == "if":
        out += [(n["body"], True), (n["orelse"], not _is_elif(n))]
    elif t in ("loop", "with"):
        out.append((n["body"], True))
    elif t == "try":
        out += [(n["body"], True), *((h["body"], True) for h in n["handlers"]), (n["final"], True)]
    elif t == "switch":
        out += [(c, True) for c in n["cases"]]
    elif t == "block":
        out.append((n["body"], False))
    return out


def _max_depth(stmts: Iterable[dict], depth: int) -> int:
    worst = depth
    for s in stmts:
        for body, deeper in _subs(s):
            worst = max(worst, _max_depth(body, depth + 1 if deeper else depth))
    return worst


def _flatten(stmts: List[dict]) -> List[dict]:
    """裸大括號攤平：第一層陳述式。"""
    out: List[dict] = []
    for s in stmts:
        out += _flatten(s["body"]) if s["t"] == "block" else [s]
    return out


def _bool_sequences(text: str) -> int:
    """&&／|| 序列數（同 Python 一個 BoolOp 算一個）：同一層括號裡換運算子就是新的一串；逗號、三元的 ? 與 : 隔開。"""
    n, stack, i = 0, [None], 0
    while i < len(text):
        c = text[i]
        if c == "(":
            stack.append(None)
        elif c == ")" and len(stack) > 1:
            stack.pop()
        elif c == "," or (c == "?" and text[i + 1:i + 2].isspace()) or (c == ":" and text[i + 1:i + 2] != ":" and text[i - 1:i] != ":"):
            stack[-1] = None
        elif text.startswith(("&&", "||"), i):
            if stack[-1] != text[i:i + 2]:
                n += 1
                stack[-1] = text[i:i + 2]
            i += 2
            continue
        i += 1
    return n


def _self_call(text: str, i: int) -> bool:
    """text[i:] 是方法名接 (：前面沒東西、或是 this. → 呼叫自己；前面是別的接收者或 new → 不是。"""
    before = text[:i].rstrip()
    if before.endswith("."):
        return before[:-1].rstrip().endswith("this") and not before[:-1].rstrip()[:-4][-1:].isalnum()
    return not re.search(r"\bnew$", before)


def _points(text: str, nest: int, rec: Optional[re.Pattern]) -> int:
    """運算式的加分點：&&／|| 每串 +1、三元與 switch 運算式 +1+巢狀、呼叫自己 +1。"""
    pts = _bool_sequences(text) + (len(_TERNARY.findall(text)) + len(_SWITCH_EXPR.findall(text))) * (1 + nest)
    if rec is not None:
        pts += sum(1 for m in rec.finditer(text) if _self_call(text, m.start()))
    return pts


def _cognitive(stmts: Iterable[dict], nest: int, rec: Optional[re.Pattern]) -> int:
    """認知複雜度加分點（同 turn_metrics）：if／迴圈／catch／switch +1 再加巢狀數；else if／else +1；using／lock 不加分；
    區塊 lambda 裡的東西巢狀多一層。"""
    pts = 0
    for n in stmts:
        t = n["t"]
        pts += sum(_cognitive(lam, nest + 1, rec) for lam in n.get("lambdas", ()))
        if t == "simple":
            pts += _points(n["text"], nest, rec)
        elif t == "if":
            pts += _points(n["cond"], nest, rec) + 1 + nest + _cognitive(n["body"], nest + 1, rec)
            if _is_elif(n):
                pts += _cognitive(n["orelse"], nest, rec) - nest     # else if：+1、不吃巢狀加分
            elif n["orelse"]:
                pts += 1 + _cognitive(n["orelse"], nest + 1, rec)
        elif t == "loop":
            pts += _points(n["head"], nest, rec) + 1 + nest + _cognitive(n["body"], nest + 1, rec)
        elif t == "with":
            pts += _points(n["head"], nest, rec) + _cognitive(n["body"], nest, rec)
        elif t == "block":
            pts += _cognitive(n["body"], nest, rec)
        elif t == "try":
            pts += _cognitive(n["body"], nest, rec) + _cognitive(n["final"], nest, rec)
            for h in n["handlers"]:
                pts += _points(h["head"], nest, rec) + 1 + nest + _cognitive(h["body"], nest + 1, rec)
        elif t == "switch":
            pts += _points(n["head"], nest, rec) + 1 + nest + sum(_cognitive(c, nest + 1, rec) for c in n["cases"])
    return pts


def _body_metrics(p: _Body, b0: int, b1: int, arrow: bool, name: str) -> Dict[str, Any]:
    """一個本體 → 巢狀、條件塊、認知複雜度、只轉手（寫法與引數）、第一層陳述式數。"""
    if arrow:
        text, lams = p.expr(b0, b1)
        stmts = [{"t": "simple", "text": text, "lambdas": lams}]
    else:
        stmts = p.stmts(b0, b1)
    flat = _flatten(stmts)
    rec = re.compile(rf"\b{re.escape(name)}\s*(?:<[^<>()]*>)?\s*\(") if _IDENT.fullmatch(name) else None
    call = None
    if len(flat) == 1 and flat[0]["t"] == "simple" and not flat[0]["lambdas"]:
        e = flat[0]["text"].strip()
        m = _RETURN.match(e)
        e = e[m.end():] if m else e
        call = None if _NOT_A_CALL.match(e) else _call_of(e)
    return {"nesting": _max_depth(stmts, 0), "bumpy": sum(1 for s in flat if _max_depth([s], 0) >= 2),
            "cognitive": _cognitive(stmts, 0, rec), "handoff": call[0] if call else None,
            "handoff_args": call[1] if call else "", "stmts": 0 if arrow and stmts[0]["text"].strip() else len(flat)}


# ─── 單檔：型別、成員、方法本體 ───────────────────────────────────────────────────

def _declarators(head: str) -> Tuple[List[str], str]:
    """欄位／屬性／事件標頭 → (名字們, 型別名)：int a = 1, b; → ([a, b], int)。"""
    parts = lang._split_top(_strip_generics(head))
    words = parts[0].split("=")[0].split() if parts else []
    if len(words) < 2:
        return [], ""
    names = [words[-1]] + [p.split("=")[0].strip() for p in parts[1:]]
    tail = lambda s: s.split("::")[-1].split(".")[-1]   # pb::IMessage.Descriptor → Descriptor
    return [tail(n) for n in names if re.fullmatch(r"@?[\w.:]+", n)], tail(words[-2].rstrip("?"))


def _accessors(src: str, depth: List[int], pairs: Dict[int, int], b0: int, b1: int):
    """屬性本體裡有本體的 get／set／init／add／remove → (名字, 起點, 本體起, 本體迄, 是否 =>)。"""
    level = depth[b0] if b0 < len(depth) else 0
    for m in _ACCESSOR.finditer(src, b0, b1):
        if depth[m.start()] != level:
            continue
        if m.group(2) == "{":
            close = pairs.get(m.end() - 1)
            if close is not None and close <= b1:
                yield m.group(1), m.start(), m.end(), close, False
        else:
            close = _semicolon(src, pairs, m.end(), b1)
            if close is not None:
                yield m.group(1), m.start(), m.end(), close, True


def _parse(path: str, text: str) -> Dict[str, Any]:
    """一個 .cs 檔 → {classes, funcs, file_notes, last_line}。類別只有自己這層；鏈與實作跨檔用 _Ctx 接。"""
    src, raw_holes = _blank_literals(text)
    newlines = [m.start() for m in re.finditer("\n", src)]

    def line_of(pos: int) -> int:
        return bisect.bisect_right(newlines, pos - 1) + 1

    spots = [(m.start(), f"第 {line_of(m.start())} 行有 #if 的另一支（#else／#elif）：兩支都算進來（數字可能偏大，不會偏小）")
             for m in _PREPROC_BRANCH.finditer(src)]
    spots += [(p, f"第 {line_of(p)} 行有原始插值字串：{{運算式}} 裡的東西沒算進來（數字可能偏小）") for p in raw_holes]
    src = _code_only(src)
    depth, pairs = lang._braces(src)
    closes = set(pairs.values())
    bad = next((i for i, ch in enumerate(src) if (ch == "{" and i not in pairs) or (ch == "}" and i not in closes)), None)
    file_notes = [f"大括號不成對（第 {line_of(bad)} 行），之後的成員範圍可能錯位"] if bad is not None else []
    found = [(m, m.end() - 1, pairs.get(m.end() - 1, len(src) - 1)) for m in lang._CS_CLASS.finditer(src)]
    body = _Body(src, pairs, line_of)
    classes, funcs = [], []
    for m, o, c in found:
        outer = sorted((x for x in found if x[1] < m.start() and x[2] > o), key=lambda x: x[1])
        mods = set(m["mods"].split())
        bases = _base_list(m["bases"])
        info = {"name": m["name"], "qual": ".".join([x[0]["name"] for x in outer] + [m["name"]]), "file": path,
                "lineno": line_of(m.start()), "end_lineno": line_of(c), "span": (m.start(), c), "kind": m["kind"],
                "mods": mods, "bases": [b for b in bases if b], "partial": "partial" in mods, "members": [],
                "abstract": set(), "hollow": {}, "solid": set(), "fields": {}, "notes": [], "arity": {}, "overrides": set()}
        own: List[Dict[str, Any]] = []
        for member in lang._cs_members(src, depth, pairs, o):
            _read_member(info, own, member, src, depth, pairs, line_of, body)
        _sign_overloads(own)
        info["members"] = list(dict.fromkeys(info["members"]))
        info["hollow"] = {k: v for k, v in info["hollow"].items() if k not in info["solid"]}
        classes.append(info)
        funcs += own
    outside = _outside_types(src, pairs, [x[0].start() for x in found], [x[2] for x in found])
    if outside is not None:
        file_notes.append(f"第 {line_of(outside)} 行起有不在任何型別裡的程式（頂層陳述式或沒認出的宣告），沒算")
    for pos, note in spots:
        owner = _innermost(funcs, pos) or _innermost(classes, pos)
        (owner["notes"] if owner else file_notes).append(note)
    return {"classes": classes, "funcs": funcs, "file_notes": file_notes, "shaky": bad is not None,
            "last_line": len(newlines) + 1}


def _innermost(items: List[Dict[str, Any]], pos: int) -> Optional[Dict[str, Any]]:
    hits = [x for x in items if x["span"][0] <= pos <= x["span"][1]]
    return min(hits, key=lambda x: x["span"][1] - x["span"][0]) if hits else None


def _outside_types(src: str, pairs: Dict[int, int], starts: List[int], ends: List[int]) -> Optional[int]:
    """型別、enum、namespace、using 以外還有程式 → 第一個字的位置；沒有 → None。"""
    mask = list(src)

    def blank(a: int, b: int) -> None:
        mask[a:b] = ["\n" if ch == "\n" else " " for ch in mask[a:b]]

    for a, b in zip(starts, ends):
        blank(a, b + 1)
    for m in _ENUM.finditer("".join(mask)):
        blank(m.start(), pairs.get(m.end() - 1, len(src) - 1) + 1)
    for m in _TOP_DECL.finditer("".join(mask)):
        blank(m.start(), m.end())
    for m in _NS_BLOCK.finditer("".join(mask)):
        blank(m.start(), m.end())
        close = pairs.get(m.end() - 1)
        if close is not None:
            blank(close, close + 1)
    m = re.search(r"[^\s;{}]", "".join(mask))   # 多出來的大括號另報「不成對」
    return m.start() if m else None


def _read_member(info: Dict[str, Any], out: List[Dict[str, Any]], member: tuple, src: str, depth: List[int],
                 pairs: Dict[int, int], line_of, body: _Body) -> None:
    """類別本體的一個成員 → 記進 info（成員名、抽象、空覆寫、欄位型別），有本體的另產出函式筆。"""
    raw, start, b0, b1, arrow, declared = member
    head = raw.strip()
    if not head or head.startswith("=") or start <= info.get("consumed", -1):   # 屬性初始值的尾巴、前一個 => 本體的尾巴
        return
    lead = start + len(raw) - len(raw.lstrip())
    if not arrow and not declared and "=>" in head and "=" not in head.replace("=>", ""):
        cut = raw.index("=>")                       # `T F() => new X { … };`：本體裡的初始化子大括號被當成成員本體了
        end = _semicolon(src, pairs, start + cut + 2, info["span"][1])
        if end is not None:
            head, b0, b1, arrow = raw[:cut].strip(), start + cut + 2, end, True
            info["consumed"] = end
    op = _OPERATOR.search(head)
    sig = op or lang._CS_SIG.search(_CTOR_INIT.sub(")", head))   # 建構子串接 `: this(a, (float)b)` 裡的括號先拿掉
    is_method = bool(op) or (bool(sig) and "=" not in head[:sig.start()] and sig["name"] not in lang.CS_KEYWORDS)
    prefix = head[:sig.start()].split() if is_method else head.split()[:-1]
    if _TYPE_WORDS & set(prefix):                 # 巢狀型別：另外一筆
        return
    mods = set(prefix)
    if not is_method:
        _read_property(info, out, head, mods, lead, b0, b1, arrow, declared, src, depth, pairs, line_of, body)
        return
    name = f"operator{op.group(1)}" if op else sig["name"]
    if not op and name == info["name"]:
        name = "~" if head[:sig.start()].rstrip().endswith("~") else CCTOR if "static" in mods else CTOR
    texts = lang._split_top(sig["params"], "()[]{}<>")
    params = dict(p for p in (lang._cs_param(t) for t in texts) if p)
    info["members"].append(name)
    info["arity"].setdefault(name, set()).add(len(texts))
    if "override" in mods:
        info["overrides"].add(name)
    if declared or "abstract" in mods or "extern" in mods:
        info["abstract"].add(name)
        return
    fn = _func(info, name, f"{info['qual']}.{name}", lead, b0, b1, arrow, line_of, body, name)
    fn.update(params=params, method=True, sig=",".join(lang._cs_type_text(t) for t in texts))
    passed = _CTOR_ARGS.search(head)
    if "override" in mods and fn["stmts"] == 0 and not arrow:
        info["hollow"][name] = "empty"
    elif "override" in mods and fn["handoff"] == f"base.{name}" and _same_args(fn["handoff_args"], list(params)):
        info["hollow"][name] = "base"
    elif name in (CTOR, CCTOR) and fn["stmts"] == 0 and not arrow and (not passed or _same_args(passed.group(1), list(params))):
        info["hollow"][name] = "ctor-base" if passed else "ctor"     # 串接的引數有加工（: this(s * 1000)）就有作用
    else:
        info["solid"].add(name)
    out.append(fn)


def _read_property(info, out, head, mods, lead, b0, b1, arrow, declared, src, depth, pairs, line_of, body) -> None:
    names, ftype = (["this[]"], "") if "this[" in head.replace(" ", "") else _declarators(head)
    if not names:
        info["notes"].append(f"第 {line_of(lead)} 行的成員標頭讀不出：{' '.join(head.split())[:30]}")
        return
    for n in names:
        info["members"].append(n)
        info["fields"].setdefault(n, ftype)
    if "=" in head.replace("=>", "") or declared:   # 欄位（含初始值）、事件欄位
        if "abstract" in mods:
            info["abstract"].update(names)
        return
    if arrow:                                      # int X => …;
        out.append(_func(info, names[0], f"{info['qual']}.{names[0]}", lead, b0, b1, True, line_of, body, ""))
        return
    got = list(_accessors(src, depth, pairs, b0, b1))
    for acc, a_start, a0, a1, a_arrow in got:
        out.append(_func(info, f"{names[0]}.{acc}", f"{info['qual']}.{names[0]}.{acc}", a_start, a0, a1, a_arrow,
                         line_of, body, ""))
    if not got and (info["kind"] == "interface" or "abstract" in mods):
        info["abstract"].update(names)


def _func(info: Dict[str, Any], member: str, qual: str, lead: int, b0: int, b1: int, arrow: bool, line_of,
          body: _Body, rec_name: str) -> Dict[str, Any]:
    body.notes = []
    got = _body_metrics(body, b0, b1, arrow, rec_name)
    lineno, end = line_of(lead), line_of(b1)
    return {"name": qual, "member": member, "cls": info["name"], "file": info["file"], "lineno": lineno,
            "end_lineno": end, "length": end - lineno + 1, "span": (lead, b1), "params": {}, "method": False, "sig": "",
            "notes": list(body.notes), "handoff_nargs": len(lang._split_top(got["handoff_args"])), **got}


def _sign_overloads(funcs: List[Dict[str, Any]]) -> None:
    """同名多載的方法改用「名稱(參數型別)」當名字；沒多載的維持裸名。"""
    counts: Dict[str, int] = {}
    for f in funcs:
        if f["method"]:
            counts[f["member"]] = counts.get(f["member"], 0) + 1
    for f in funcs:
        if f["method"] and counts[f["member"]] > 1:
            f["name"] = f"{f['name']}({f['sig']})"


# ─── 多檔：型別索引、繼承鏈、轉手鏈與分派 ───────────────────────────────────────────

def _overrides(c: Dict[str, Any], m: str, above: set, above_arity: Dict[str, set]) -> bool:
    """m 是覆寫上層的成員嗎：欄位、屬性看名字；方法要有 override、或參數個數對得上（同名不同參數個數是新增的多載）。"""
    if m not in above:
        return False
    arity = c["arity"].get(m)
    return arity is None or m not in above_arity or m in c["overrides"] or bool(arity & above_arity[m])


def _inherit_layers(start: Dict[str, Any], index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """沿第一個基底往上接：每層 added／overridden／hollow，empty＝除了「沒加東西」的空殼成員什麼都沒加。接不到的基底記 unresolved_base 並停。"""
    chain, seen, cur, unresolved = [], set(), start, None
    while cur is not None and cur["name"] not in seen:
        seen.add(cur["name"])
        chain.append(cur)
        if not cur["bases"]:
            break
        nxt = index.get(cur["bases"][0])
        if nxt is None:
            unresolved = cur["bases"][0]
            break
        cur = nxt
    layers, above, above_abstract, above_arity = [], set(), set(), {}
    for c in reversed(chain):          # 從最上層往下算
        mem = c["members"]
        hollow = {m: hollow_text(k, m, above, above_abstract, unresolved is not None) for m, k in c["hollow"].items()}
        hollow = {m: v for m, v in hollow.items() if v}
        over = [m for m in mem if _overrides(c, m, above, above_arity)]
        layers.append({"name": c["qual"], "file": c["file"], "added": [m for m in mem if m not in over], "overridden": over,
                       "empty": not [m for m in mem if not hollow.get(m, ("", False))[1]],
                       "hollow": {m: text for m, (text, _) in hollow.items()}})
        above |= set(mem)
        above_abstract = (above_abstract - set(mem)) | c["abstract"]
        for m, arity in c["arity"].items():
            above_arity.setdefault(m, set()).update(arity)
    layers.reverse()
    return {"depth": len(layers), "empty_layers": sum(1 for l in layers if l["empty"]), "unresolved_base": unresolved,
            "layers": layers}


class _Ctx:
    """跨檔查表：型別索引（partial 併成一個；同名不同 namespace 先到先用）、每個型別的方法、介面與抽象類別的直接實作。"""

    def __init__(self, parsed: Iterable[Dict[str, Any]], partial_pool: bool = False):
        self.partial_pool = partial_pool   # 查找池截過：實作數只是下限，不據此說「只有一個實作」
        self.index: Dict[str, Dict[str, Any]] = {}
        self.funcs: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self.impls: Dict[str, List[str]] = {}
        for p in parsed:
            for c in p["classes"]:
                self._add(c)
            for fn in p["funcs"]:
                self.funcs.setdefault(fn["cls"], {}).setdefault(fn["member"], []).append(fn)
        for c in self.index.values():   # 實作＝具體型別（非介面、非 abstract），經由父類別或介面繼承到的也算
            if c["kind"] == "interface" or "abstract" in c["mods"]:
                continue
            for a in self._ancestors(c["name"]):
                self.impls.setdefault(a, []).append(c["name"])
        for names in self.impls.values():
            names.sort()

    def _ancestors(self, name: str) -> set:
        """所有基底（類別與介面，往上一路接；接不到的名字也收，停在那裡）。"""
        out: set = set()
        todo = list((self.index.get(name) or {}).get("bases") or [])
        while todo:
            b = todo.pop()
            if b in out or b == name:
                continue
            out.add(b)
            todo += (self.index.get(b) or {}).get("bases") or []
        return out

    def _add(self, c: Dict[str, Any]) -> None:
        have = self.index.get(c["name"])
        if have is None:
            self.index[c["name"]] = dict(c, members=list(c["members"]), abstract=set(c["abstract"]), hollow=dict(c["hollow"]),
                                         fields=dict(c["fields"]), overrides=set(c["overrides"]),
                                         arity={k: set(v) for k, v in c["arity"].items()}, parts=1)
        elif c["partial"] and have["partial"]:
            have["members"] = list(dict.fromkeys(have["members"] + c["members"]))
            have["abstract"] |= c["abstract"]
            have["overrides"] |= c["overrides"]
            for k, v in c["arity"].items():
                have["arity"].setdefault(k, set()).update(v)
            have["hollow"].update(c["hollow"])
            have["fields"] = {**c["fields"], **have["fields"]}
            have["bases"] = have["bases"] or c["bases"]
            have["parts"] += 1

    def _find(self, cls: Optional[str], member: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """沿繼承鏈找有本體的方法 → (同名的各個, 所在型別)；先碰到只有宣告的那層 → (None, 那層)；接不到 → (None, None)。"""
        seen: set = set()
        while cls and cls not in seen:
            seen.add(cls)
            fs = self.funcs.get(cls, {}).get(member)
            if fs:
                return fs, cls
            info = self.index.get(cls)
            if info is None:
                return None, None
            if member in info["members"]:
                return None, cls
            cls = info["bases"][0] if info["bases"] else None
        return None, None

    @staticmethod
    def _pick(fs: Optional[List[Dict[str, Any]]], nargs: int, caller: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not fs:
            return None
        others = [x for x in fs if x is not caller] or fs
        return next((x for x in others if len(x["params"]) == nargs), others[0])

    def _field(self, cls: Optional[str], name: str) -> Optional[str]:
        seen: set = set()
        while cls and cls not in seen:
            seen.add(cls)
            info = self.index.get(cls)
            if info is None:
                return None
            if name in info["fields"]:
                return info["fields"][name] or None
            cls = info["bases"][0] if info["bases"] else None
        return None

    def _external_base(self, cls: Optional[str]) -> bool:
        """繼承鏈上有接不到的基底（UnityEngine.MonoBehaviour 之類）：看不到的成員多半在那裡。"""
        seen: set = set()
        while cls and cls not in seen:
            seen.add(cls)
            info = self.index.get(cls)
            if info is None:
                return True
            cls = info["bases"][0] if info["bases"] else None
        return False

    def _recv_type(self, f: Dict[str, Any], recv: List[str]) -> Tuple[Optional[str], bool]:
        """接收者寫法 → (掃到的檔裡的型別, 卡在掃到的檔裡)。接到外部型別（Debug、transform、List…）是鏈的正常終點，不算卡住。"""
        t = f["params"].get(recv[0]) or self._field(f["cls"], recv[0])
        if t is None:
            if recv[0] in self.index:
                t = recv[0]
            elif recv[-1] in self.index:
                return recv[-1], False
            else:
                return None, not (recv[0][:1].isupper() or self._external_base(f["cls"]))
        for seg in recv[1:]:
            if t not in self.index:
                return None, False
            nxt = self._field(t, seg)
            if nxt is None:
                return None, not self._external_base(t)
            t = nxt
        return (t, False) if t in self.index else (None, False)

    def target(self, f: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, str]], Optional[str]]:
        """只轉手的對象 → (對象函式, 經過單一實作分派的那一手, 看不出對象時的說明)。"""
        callee, nargs = f["handoff"], f["handoff_nargs"]
        if callee.startswith("new "):
            return self._pick(self.funcs.get(callee[4:].split(".")[-1], {}).get(CTOR), nargs, f), None, None
        *recv, member = callee.split(".")
        recv = recv[1:] if recv[:1] == ["this"] else recv
        if not recv:
            return self._pick(self._find(f["cls"], member)[0], nargs, f), None, None
        if recv == ["base"]:
            bases = (self.index.get(f["cls"]) or {}).get("bases") or [None]
            return self._pick(self._find(bases[0], member)[0], nargs, f), None, None
        t, stuck = self._recv_type(f, recv)
        if t is None:
            same = stuck and any(member in fs for fs in self.funcs.values())
            return None, None, (f"轉手對象 {'.'.join(recv)} 的型別看不出來，鏈只算到這裡（掃到的檔裡有同名方法 {member}）"
                                if same else None)
        fs, _ = self._find(t, member)
        info = self.index[t]
        impls = self.impls.get(t, []) if info["kind"] == "interface" or "abstract" in info["mods"] else []
        got = self._pick(self._find(impls[0], member)[0], nargs, f) if len(impls) == 1 else None
        if got and not (fs and got in fs) and self.partial_pool:
            return (self._pick(fs, nargs, f), None,
                    f"經過 {t}.{member}：查找池超過上限只挑了一部分，實作看不全，沒算分派")
        if got and not (fs and got in fs):      # 經過介面或抽象型別、唯一的具體實作有自己的那一個：多繞一手
            return got, {"via": f"{t}.{member}", "impl": got["name"]}, None
        return self._pick(fs, nargs, f), None, None

    def func_row(self, fn: Dict[str, Any], shaky: bool) -> Dict[str, Any]:
        n, cur, seen, hops, notes = 0, fn, set(), [], list(fn["notes"])
        while cur is not None and cur["handoff"] and id(cur) not in seen:
            seen.add(id(cur))
            n += 1
            nxt, hop, why = self.target(cur)
            if hop:
                n += 1
                hops.append(hop)
            if why:
                notes.append(why if cur is fn else f"{cur['name']} 那一手：{why}")
            cur = nxt
        return {"kind": "func", "file": fn["file"], "name": fn["name"], "lineno": fn["lineno"], "end_lineno": fn["end_lineno"],
                "length": fn["length"], "nesting": fn["nesting"], "bumpy": fn["bumpy"], "cognitive": fn["cognitive"],
                "handoff": fn["handoff"], "handoff_chain": n, "dispatch": hops, "unparsed": notes,
                "confidence": "partial" if notes or shaky else "full"}

    def class_row(self, c: Dict[str, Any], shaky: bool) -> Dict[str, Any]:
        merged = self.index.get(c["name"])
        start = merged if c["partial"] and merged is not None and merged["partial"] else c
        notes = list(c["notes"])
        if c["partial"]:
            notes.append(f"partial：成員併了掃到的 {start.get('parts', 1)} 個分檔，沒掃到的分檔看不到")
        bases = start["bases"]
        first_is_interface = bool(bases) and (self.index.get(bases[0]) or {}).get("kind") == "interface"
        cands = bases[:1] * first_is_interface + bases[1:]
        abstract_like = c["kind"] == "interface" or "abstract" in c["mods"]
        if self.partial_pool and (abstract_like or cands):
            notes.append("實作數是查找池裡看得到的下限（池超過上限只挑了一部分）")
        return {"kind": "class", "file": c["file"], "name": c["qual"], "lineno": c["lineno"], "end_lineno": c["end_lineno"],
                **_inherit_layers(start, self.index), "type_kind": c["kind"],
                "interfaces": {b: (self.impls.get(b, []) if b in self.index else None) for b in cands},
                "implementations": self.impls.get(c["name"], []) if abstract_like else [],
                "unparsed": notes, "confidence": "partial" if notes or shaky else "full"}


def _base_list(text: Optional[str]) -> List[str]:
    """class 標頭冒號後面那串 → 基底型別名（拿掉泛型、命名空間、別名、record 的建構引數）。"""
    names = [re.sub(r"\(.*", "", b).split("::")[-1].split(".")[-1] for b in lang._split_top(_strip_generics(text or ""))]
    return [n for n in names if n]


def _refs(path: str) -> Tuple[set, set]:
    """一個 .cs 檔直接指到的 → (繼承與實作的型別名, using 的命名空間)；讀不了 → 兩個空集合。"""
    try:
        src = _code_only(_blank_literals(Path(path).read_text(encoding="utf-8-sig", errors="replace"))[0])
    except OSError:
        return set(), set()
    bases = {b for m in lang._CS_CLASS.finditer(src) for b in _base_list(m["bases"])}
    return bases, set(_USING_NS.findall(src))


def pick_lookup_files(changed: List[str], candidates: List[str], limit: int) -> List[str]:
    """查找池（接繼承鏈、轉手鏈、數實作用）超過上限時怎麼挑：改到的檔 → 它們繼承／實作直接指到的型別所在的檔（照「檔名＝型別名」找、
    找到的再往上接；量少又是鏈本身，放最前）→ 同目錄的檔 → using 指到的命名空間所在目錄的檔 → 其他檔照原順序補滿 limit。
    同目錄放在繼承之後：大目錄（產生碼）的同目錄檔會先把上限吃光，鏈反而接不到。沒超過上限就全給。"""
    if len(candidates) <= limit:
        return list(candidates)
    key = lambda p: os.path.normcase(os.path.abspath(p))
    picked: Dict[str, str] = {}

    def add(p: str) -> bool:
        if len(picked) >= limit or key(p) in picked:
            return False
        picked[key(p)] = p
        return True

    for p in changed:
        add(p)
    by_type: Dict[str, List[str]] = {}
    for p in candidates:
        by_type.setdefault(Path(p).name.split(".")[0], []).append(p)   # Pool.cs、Pool.Fill.cs 都是 Pool
    own = {key(p): _refs(p) for p in changed}
    todo, seen = list(changed), set()
    while todo and len(picked) < limit:
        p = todo.pop(0)
        bases = (own.get(key(p)) or _refs(p))[0]
        for t in sorted(bases - seen):   # 固定順序：上限不夠放時結果可重現
            seen.add(t)
            todo += [q for q in by_type.get(t, []) if add(q)]
    dirs = {key(str(Path(p).parent)) for p in changed}
    for p in candidates:
        if key(str(Path(p).parent)) in dirs:
            add(p)
    for ns in sorted(set().union(*(names for _, names in own.values()))):
        tail = "/" + ns.replace(".", "/").lower()
        for p in candidates:
            if Path(p).parent.as_posix().lower().endswith(tail):
                add(p)
    for p in candidates:
        add(p)
    return list(picked.values())


def metrics_for_files(files: Iterable[str], ranges: Optional[Dict[str, List[Range]]] = None,
                      resolve_files: Optional[Iterable[str]] = None, partial_pool: bool = False) -> List[Dict[str, Any]]:
    """多檔 → 一筆一 dict（方法 kind=func、型別 kind=class、檔案層解析不到 kind=unparsed、非 .cs kind=unsupported、讀不了 kind=error）。
    ranges 給了就只列落在區間裡的（鍵是路徑，與 files 用 realpath 對）。resolve_files：接繼承鏈、轉手鏈、數實作時另外可查的檔，不列進結果。
    partial_pool：resolve_files 是從更多檔裡挑出來的（pick_lookup_files）→ 實作數標成下限、不算「只有一個實作」的分派。"""
    want = {_norm(k): v for k, v in (ranges or {}).items()}
    listed = [str(f) for f in files]
    rows: List[Dict[str, Any]] = []
    parsed: Dict[str, Dict[str, Any]] = {}
    lost: List[str] = []                  # 查找用的檔讀不了：實作數與鏈可能少算
    for f in dict.fromkeys(listed + [str(f) for f in (resolve_files or [])]):
        if not f.lower().endswith(".cs"):
            continue
        try:
            parsed[f] = _parse(f, Path(f).read_text(encoding="utf-8-sig", errors="replace"))
        except (OSError, ValueError, RecursionError) as e:
            if f in listed:
                rows.append({"kind": "error", "file": f, "error": f"{type(e).__name__}: {e}"[:160]})
            else:
                lost.append(f"{Path(f).name}（{type(e).__name__}）")
    if lost:
        rows.append({"kind": "unparsed", "file": listed[0] if listed else "", "lineno": 1, "end_lineno": 1, "confidence": "partial",
                     "unparsed": [f"查找用的 {len(lost)} 個檔讀不了（{'、'.join(lost[:3])}），實作數與轉手鏈可能少算"]})
    ctx = _Ctx(parsed.values(), partial_pool)
    for f in listed:
        if not f.lower().endswith(".cs"):
            rows.append({"kind": "unsupported", "file": f, "lang": "不支援"})
            continue
        p = parsed.get(f)
        if p is None:
            continue
        hit = want.get(_norm(f))

        def keep(r: Dict[str, Any]) -> bool:
            return ranges is None or bool(hit and _overlaps(r, hit))

        rows += [ctx.func_row(fn, p["shaky"]) for fn in p["funcs"] if keep(fn)]
        rows += [ctx.class_row(c, p["shaky"]) for c in p["classes"] if keep(c)]
        whole = {"kind": "unparsed", "file": f, "lineno": 1, "end_lineno": p["last_line"], "unparsed": p["file_notes"],
                 "confidence": "partial"}
        if p["file_notes"] and keep(whole):
            rows.append(whole)
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="C# 的函式級與類別級側面數據（只算不判）：一行一筆 JSON，尾行 TURN_METRICS_CS DONE。")
    ap.add_argument("files", nargs="+", help="要列的 .cs 檔")
    ap.add_argument("--diff", help="unified diff 檔：只列命中的函式與類別（路徑相對 --root）")
    ap.add_argument("--root", default=".", help="diff 裡路徑的根")
    ap.add_argument("--resolve", nargs="*", default=[], help="接繼承鏈、轉手鏈、數實作時另外可查的 .cs 檔")
    a = ap.parse_args(argv)
    ranges = None
    if a.diff:
        raw = parse_diff_ranges(Path(a.diff).read_text(encoding="utf-8", errors="replace"))
        ranges = {str(Path(a.root) / k): v for k, v in raw.items()}
    rows = metrics_for_files(a.files, ranges, a.resolve)
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    partial = sum(r["kind"] in ("func", "class") and r["confidence"] == "partial" for r in rows)
    print(f"TURN_METRICS_CS DONE funcs={sum(r['kind'] == 'func' for r in rows)} classes={sum(r['kind'] == 'class' for r in rows)}"
          f" partial={partial} unparsed_files={sum(r['kind'] == 'unparsed' for r in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
