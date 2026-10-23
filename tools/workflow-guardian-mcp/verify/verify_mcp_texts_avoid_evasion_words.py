"""verify_mcp_texts_avoid_evasion_words.py：MCP 伺服器（js）回給 AI 的字句不得命中退避偵測（規則 GATE_TEXT_AVOIDS_EVASION_WORDS 的 js 端）。

為什麼：工具說明與回覆訊息 AI 會照抄進自己的回覆，照抄的字句被退避偵測（hooks/wg_evasion.detect_evasion）判成 AI 退避
（實例：atom_move 回覆「索引既有問題…非本次造成」、need_goal 說明「add＝之後再長子目標」）。偵測面不開引用豁免，改說法。
做法：切出 tools/workflow-guardian-mcp/lib/*.js 與 server.js 原始碼裡的每個字串字面值（樣板字串整條、插值換成 X），逐條跑
detect_evasion——詞表就是 wg_evasion 載入的那份，不另抄。不算（不會進 AI 眼前）：註解、正則（/…/ 字面值與 new RegExp 的參數）、
require 路徑、物件的鍵（`"index_preexisting_issues":` 這類兩支程式之間的介面鍵）、寫 stderr／crashLog 的參數、
給人看的儀表板與 HUD 頁模板（dashboard-html.js、aec-hud-html.js：瀏覽器頁，不經 MCP 回覆）。
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


def js_strings(src: str) -> List[Tuple[int, str, bool]]:
    """JS 原始碼 → [(行號, 字串內容, 是否算數)]。樣板字串的 ${…} 換成 X（裡面的程式照樣往下切）；
    不算數＝物件的鍵、或在 SKIP_CALLS 那幾種呼叫的括號裡。註解與正則字面值整段跳過。"""
    out: List[Tuple[int, str, bool]] = []
    calls: List[str] = []           # 括號堆疊：每層記左括號前的呼叫名（不是呼叫記 ""）
    tmpl: List[int] = []            # 樣板字串 ${ 的大括號深度堆疊
    depth = 0
    last = ""                       # 上一個有意義的字元（判斷 / 是除號還是正則、字串是不是鍵）
    last_word = ""
    i, n = 0, len(src)

    def line_of(pos: int) -> int:
        return src.count("\n", 0, pos) + 1

    def skipped() -> bool:
        return any(c in SKIP_CALLS or c.endswith(tuple("." + s for s in SKIP_CALLS)) for c in calls)

    def read_quoted(q: str, start: int) -> Tuple[str, int]:
        buf, j = [], start
        while j < n and src[j] != q:
            if src[j] == "\\" and j + 1 < n:
                buf.append(src[j + 1])
                j += 2
                continue
            buf.append(src[j])
            j += 1
        return "".join(buf), j + 1

    def read_template(start: int) -> Tuple[str, int]:
        """讀樣板字串到結尾反引號；遇 ${ 就遞迴切裡面的程式（只為跳過它），內容記 X。"""
        nonlocal_out = []
        j = start
        while j < n and src[j] != "`":
            if src[j] == "\\" and j + 1 < n:
                nonlocal_out.append(src[j + 1])
                j += 2
                continue
            if src.startswith("${", j):
                nonlocal_out.append("X")
                j = skip_code(j + 2, until_brace=True)
                continue
            nonlocal_out.append(src[j])
            j += 1
        return "".join(nonlocal_out), j + 1

    def skip_code(j: int, until_brace: bool = False) -> int:
        """從 j 切程式到結尾（until_brace：到配對的 }）；途中的字串照樣收進 out。"""
        nonlocal last, last_word
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
                is_key = last in ("{", ",") and re.match(r"\s*:", src[j:]) is not None
                out.append((line_of(start), s, not (is_key or skipped())))
                last, last_word = c, ""
                continue
            if c == "`":
                start = j
                s, j = read_template(j + 1)
                out.append((line_of(start), s, not skipped()))
                last, last_word = "`", ""
                continue
            if c == "/" and (last in _REGEX_PREV or last == "" or last_word in _REGEX_KEYWORDS):
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
                last, last_word = "/", ""
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
                last_word, last = src[j:k], "w"
                j = k
                continue
            last, last_word = c, ""
            j += 1
        return j

    skip_code(0)
    return out


def _mcp_files() -> List[Path]:
    files = sorted((MCP / "lib").glob("*.js")) + [MCP / "server.js"]
    return [p for p in files if p.name not in HUMAN_PAGES]


def test_extractor_basics():
    src = ('const a = { "json_key": 1, description: "說明一" };\n'
           'require("./x"); process.stderr.write(`stderr ${a}`);\n'
           'const r = /之後再/; const d = 4 / 2; const t = `樣板 ${f("內層")} 尾`;\n'
           '// 註解之後再\n/* 區塊之後再 */ x = cond ? "甲" : "乙";\n')
    got = [(s, ok) for _l, s, ok in js_strings(src)]
    assert ("json_key", False) in got and ("說明一", True) in got
    assert ("./x", False) in got and ("stderr X", False) in got
    assert ("樣板 X 尾", True) in got and ("內層", True) in got
    assert ("甲", True) in got and ("乙", True) in got
    assert not any("之後再" in s for s, _ in got), "註解與正則字面值不算字串"


def test_mcp_texts_do_not_trip_evasion_detector():
    hits = []
    for p in _mcp_files():
        for line, text, counted in js_strings(p.read_text(encoding="utf-8")):
            if not counted:
                continue
            ev = detect_evasion(text, [])
            if ev:
                hits.append(f"{p.relative_to(TREE).as_posix()}:{line}：「{ev['phrase']}」← {text[:80]}")
    assert not hits, "MCP 回給 AI 的字句命中退避詞表（改說法，不加豁免）：\n" + "\n".join(hits)
