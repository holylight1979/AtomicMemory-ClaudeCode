"""verify_mcp_texts_avoid_evasion_words.py：MCP 伺服器（js）回給 AI 的字句不得命中退避偵測（規則 GATE_TEXT_AVOIDS_EVASION_WORDS 的 js 端）。

為什麼：工具說明與回覆訊息 AI 會照抄進自己的回覆，照抄的字句被退避偵測（hooks/wg_evasion.detect_evasion）判成 AI 退避
（實例：atom_move 回覆「索引既有問題…非本次造成」、need_goal 說明「add＝之後再長子目標」）。偵測面不開引用豁免，改說法。
做法：切出 tools/workflow-guardian-mcp/lib/*.js 與 server.js 原始碼裡的每個字串字面值（跳脫照 JS 還原、樣板字串整條、插值換成 X），
逐條跑 detect_evasion——詞表就是 wg_evasion 載入的那份，不另抄。不算（不會進 AI 眼前）：註解、正則（/…/ 字面值）、
物件的鍵（`"index_preexisting_issues":` 這類兩支程式之間的介面鍵）、最內層呼叫是 require／new RegExp／寫 stderr／crashLog 的參數、
給人看的儀表板與 HUD 頁模板（dashboard-html.js、aec-hud-html.js：瀏覽器頁，不經 MCP 回覆）。
切分器另有正向對照：幾句已知會回給 AI 的字串一定要切得到，切壞了不會空跑也綠。
怎麼跑：python -X utf8 -m pytest -q tools/workflow-guardian-mcp/verify/verify_mcp_texts_avoid_evasion_words.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

TREE = Path(__file__).resolve().parents[3]
HOOKS = TREE / "hooks"
for p in (str(TREE), str(HOOKS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from wg_evasion import detect_evasion  # noqa: E402

MCP = TREE / "tools" / "workflow-guardian-mcp"
HUMAN_PAGES = {"dashboard-html.js", "aec-hud-html.js"}
SKIP_CALLS = ("require", "RegExp", "process.stderr.write", "console.error", "console.warn", "crashLog")
_REGEX_PREV = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_KEYWORDS = {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void", "throw", "instanceof",
                   "yield", "await"}
_IDENT_TAIL_RE = re.compile(r"([A-Za-z_$][\w$.]*)\s*$")
_SIMPLE_ESC = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def js_strings(src: str) -> List[Tuple[int, str, bool]]:
    """JS 原始碼 → [(行號, 字串內容, 是否算數)]。跳脫照 JS 還原（\\n、\\uXXXX、\\u{…}、\\xHH）；樣板字串的 ${…} 換成 X
    （裡面的程式照樣往下切）；不算數＝物件的鍵、或最內層呼叫是 SKIP_CALLS 那幾種。註解與正則字面值整段跳過。"""
    out: List[Tuple[int, str, bool]] = []
    calls: List[str] = []           # 括號堆疊：每層記左括號前的呼叫名（不是呼叫記 ""）
    n = len(src)
    tok = {"last": "", "prev": "", "word": ""}   # 上一個、上上個有意義的字元，上一個識別字（判 / 是除號還是正則、字串是不是鍵）

    def line_of(pos: int) -> int:
        return src.count("\n", 0, pos) + 1

    def skipped() -> bool:
        c = calls[-1] if calls else ""
        return c in SKIP_CALLS or c.endswith(tuple("." + s for s in SKIP_CALLS))

    def mark(c: str, word: str = "") -> None:
        tok["prev"], tok["last"], tok["word"] = tok["last"], c, word

    def escape_at(j: int) -> Tuple[str, int]:
        """src[j] 是反斜線：回 (還原的字, 下一個位置)。"""
        e = src[j + 1] if j + 1 < n else ""
        if e == "u" and src.startswith("{", j + 2):
            k = src.find("}", j + 3)
            return chr(int(src[j + 3:k], 16)), k + 1
        if e == "u" and re.fullmatch(r"[0-9A-Fa-f]{4}", src[j + 2:j + 6]):
            return chr(int(src[j + 2:j + 6], 16)), j + 6
        if e == "x" and re.fullmatch(r"[0-9A-Fa-f]{2}", src[j + 2:j + 4]):
            return chr(int(src[j + 2:j + 4], 16)), j + 4
        if e == "\n":
            return "", j + 2   # 行接續
        return _SIMPLE_ESC.get(e, e), j + 2

    def read_quoted(q: str, start: int) -> Tuple[str, int]:
        buf, j = [], start
        while j < n and src[j] != q:
            if src[j] == "\\":
                ch, j = escape_at(j)
                buf.append(ch)
                continue
            buf.append(src[j])
            j += 1
        return "".join(buf), j + 1

    def read_template(start: int) -> Tuple[str, int]:
        """讀樣板字串到結尾反引號；遇 ${ 就切裡面的程式（字串照收），內容記 X。"""
        buf, j = [], start
        while j < n and src[j] != "`":
            if src[j] == "\\":
                ch, j = escape_at(j)
                buf.append(ch)
                continue
            if src.startswith("${", j):
                buf.append("X")
                j = skip_code(j + 2, until_brace=True)
                continue
            buf.append(src[j])
            j += 1
        return "".join(buf), j + 1

    def regex_here() -> bool:
        if tok["last"] in "+-" and tok["prev"] == tok["last"]:   # x++ / 2、x-- / 2：後置遞增遞減之後是除號
            return False
        return tok["last"] in _REGEX_PREV or tok["last"] == "" or tok["word"] in _REGEX_KEYWORDS

    def skip_code(j: int, until_brace: bool = False) -> int:
        """從 j 切程式到結尾（until_brace：到配對的 }）；途中的字串照樣收進 out。"""
        level = 0
        while j < n:
            c = src[j]
            if src.startswith("//", j):
                j = src.find("\n", j)
                j = n if j < 0 else j
                continue
            if src.startswith("/*", j):
                k = src.find("*/", j + 2)
                j = n if k < 0 else k + 2
                continue
            if c in "'\"":
                start = j
                s, j = read_quoted(c, j + 1)
                is_key = tok["last"] in ("{", ",") and re.match(r"\s*:", src[j:]) is not None
                out.append((line_of(start), s, not (is_key or skipped())))
                mark(c)
                continue
            if c == "`":
                start = j
                s, j = read_template(j + 1)
                out.append((line_of(start), s, not skipped()))
                mark("`")
                continue
            if c == "/" and regex_here():
                k, in_class = j + 1, False
                while k < n and src[k] != "\n":
                    if src[k] == "\\":
                        k += 2
                        continue
                    if src[k] == "[":
                        in_class = True
                    elif src[k] == "]":
                        in_class = False
                    elif src[k] == "/" and not in_class:
                        break
                    k += 1
                j = k + 1
                while j < n and src[j].isalpha():
                    j += 1
                mark("/")
                continue
            if c == "(":
                m = _IDENT_TAIL_RE.search(src[max(0, j - 80):j])
                calls.append(m.group(1) if m else "")
            elif c == ")" and calls:
                calls.pop()
            elif c == "{":
                level += 1
            elif c == "}":
                if until_brace and level == 0:
                    return j + 1
                level -= 1
            if c.isspace():
                j += 1
                continue
            if c.isalnum() or c in "_$":
                k = j
                while k < n and (src[k].isalnum() or src[k] in "_$"):
                    k += 1
                mark("w", src[j:k])
                j = k
                continue
            mark(c)
            j += 1
        return j

    skip_code(0)
    return out


def _mcp_files() -> List[Path]:
    files = sorted((MCP / "lib").glob("*.js")) + [MCP / "server.js"]
    return [p for p in files if p.name not in HUMAN_PAGES]


def _counted_texts() -> List[Tuple[str, int, str]]:
    return [(p.relative_to(TREE).as_posix(), line, text)
            for p in _mcp_files() for line, text, counted in js_strings(p.read_text(encoding="utf-8")) if counted]


def test_extractor_basics():
    src = ('const a = { "json_key": 1, description: "說明一" };\n'
           'require("./x"); process.stderr.write(`stderr ${a}`);\n'
           'const r = /之後再/; const d = 4 / 2; const t = `樣板 ${f("內層")} 尾`;\n'
           '// 註解之後再\n/* 區塊之後再 */ x = cond ? "甲" : "乙";\n'
           'i++ / 2; reply(id, "除號後的回覆");\n'
           'console.error(sendToolResult(id, "內層回覆"));\n'
           'const u = "\\u4e2d\\u{6587}\\n\\x41";\n')
    got = [(s, ok) for _l, s, ok in js_strings(src)]
    assert ("json_key", False) in got and ("說明一", True) in got
    assert ("./x", False) in got and ("stderr X", False) in got
    assert ("樣板 X 尾", True) in got and ("內層", True) in got
    assert ("甲", True) in got and ("乙", True) in got
    assert ("除號後的回覆", True) in got, "後置遞增之後的 / 是除號，不能把整行當正則跳過"
    assert ("內層回覆", True) in got, "只看最內層呼叫：stderr 呼叫裡另一個呼叫的回覆照算"
    assert ("中文\nA", True) in got, "跳脫照 JS 還原"
    assert not any("之後再" in s for s, _ in got), "註解與正則字面值不算字串"


def test_extractor_sees_known_ai_facing_texts():
    """正向對照：幾句一定會回給 AI 的字串（工具說明、回覆訊息）要切得到；切分器壞了這支會紅，不會空跑也綠。"""
    texts = _counted_texts()
    assert len(texts) > 1000, len(texts)
    joined = "\n".join(t for _r, _l, t in texts)
    for needle in ("取第二意見結果", "收尾檢核已提交", "項是搬移前就有的（這次搬移沒造成；",
                   "Atom not found: ", "不寫病灶文件"):
        assert needle in joined, f"切分器沒切到已知會回給 AI 的字串：{needle}"


def test_mcp_texts_do_not_trip_evasion_detector():
    hits = []
    for rel, line, text in _counted_texts():
        ev = detect_evasion(text, [])
        if ev:
            hits.append(f"{rel}:{line}：「{ev['phrase']}」← {text[:80]}")
    assert not hits, "MCP 回給 AI 的字句命中退避詞表（改說法，不加豁免）：\n" + "\n".join(hits)
