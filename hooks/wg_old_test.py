"""wg_old_test.py — 改舊測試要先宣告（規則 OLD_TEST_CHANGE_NEEDS_DECLARATION）：收事實、留帳、組擋訊息。

PreToolUse 的 Edit／MultiEdit／Write 寫到測試檔時，比對改前（磁碟現檔）與改後（套用 old_string→new_string，或 Write 的新內容），
抓四種「動既有測試」：消失、改名、同名測試的斷言被刪或改、新加跳過標記；再到 transcript 三管道（回覆文字／工具參數／thinking，
與定位三行同一套 assistant_text_after）找宣告行「改舊測試｜<函式名>：<理由>」。判定在 wg_release_rules.old_test_change_verdict。

切本體：Python 照縮排（含單行 `def test_x(): assert …`），斷言以邏輯行比（括號沒合上、行尾反斜線就併下一行）；
JS／TS（it／test，describe 只看跳過）、C#（[Test]／[Fact]／[TestMethod]／[Theory]）、Java（@Test）從這支的開頭行到下一支開頭都算它的
（尾端 helper 的斷言會算給最後一支，只會多問一次宣告），斷言一行一筆、點開頭的續行併回上一行。比之前都去註解、空白壓成一個。
NotebookEdit、Bash 的 sed -i／重導改測試檔不經過這裡。
怎麼驗：python -X utf8 -m pytest -q hooks/verify/verify_old_test_declare.py
"""
from __future__ import annotations

import fnmatch
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GUARD = "old_test"
# 共用的案例檔判式（wg_verify_ledger.is_case_file）沒涵蓋的 C#／Java 測試檔名慣例
EXTRA_CASE_NAMES = ("*tests.cs", "*test.cs", "*tests.java", "*test.java")
_PY_EXTS = (".py",)
_JS_EXTS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")
_ANNOT_EXTS = (".cs", ".java")

_PY_DEF_RE = re.compile(r"^(\s*)(?:async\s+)?def\s+(test\w*)\s*\(")
_PY_INLINE_BODY_RE = re.compile(r"\)\s*(?:->[^:]+)?:\s*(\S.*)$")
_PY_CLASS_RE = re.compile(r"^(\s*)class\s+(\w+)")
_PY_ASSERT_RE = re.compile(r"^(?:assert\b|self\.assert|with (?:pytest\.raises|self\.assert)|pytest\.raises\()")
_PY_SKIP_RE = re.compile(r"pytest\.mark\.(?:skip|skipif|xfail)\b|\bpytest\.(?:skip|xfail)\s*\(|unittest\.skip|"
                         r"unittest\.expectedFailure|\bself\.skipTest\s*\(")
_PY_MODULE_MARK_RE = re.compile(r"^pytestmark\s*=")
_JS_TEST_RE = re.compile(r"(?<![\w.$])(x?)(it|test|describe|context)((?:\.\w+)*)\s*\(\s*(['\"`])((?:\\.|(?!\4).)*?)\4")
_OTHER_ASSERT_RE = re.compile(r"\bexpect\s*\(|\bassert\w*\s*\(|\b\w*Assert\.|\bAssertions\.")
_ANNOT_LINE_RE = re.compile(r"^\s*(?:\[.*\]|@\w[\w.]*(?:\(.*\))?)\s*$")
_TEST_ANNOT_RE = re.compile(r"[\[,]\s*(?:Test|TestMethod|Fact|Theory|TestCase)\b|@(?:Test|ParameterizedTest|RepeatedTest)\b")
_SKIP_ANNOT_RE = re.compile(r"[\[,]\s*Ignore\b|\bSkip\s*=|@Disabled\b|@Ignore\b")
_METHOD_RE = re.compile(r"\b(\w+)\s*\(")
_WS_RE = re.compile(r"\s+")
RENAME_MIN_SIMILARITY = 0.6


def _cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    return ((config or {}).get("guard") or {}).get("old_test_declare") or {}


def _root(file_path: str, cwd: str) -> Optional[str]:
    try:
        from wg_core import find_vcs_root
        hit = find_vcs_root(Path(file_path).parent)
        if hit:
            return str(hit[1])
    except Exception:
        pass
    return cwd or None


def is_test_file(file_path: str, config: Dict[str, Any], root: Optional[str]) -> bool:
    """重用寫碼查核的案例檔判式（reconcile_gate 的 verify_case_globs＋code_exts），再補 C#／Java 的 FooTests.cs／FooTest.java。"""
    import wg_verify_ledger as vl
    if vl.is_case_file(file_path, vl.reconcile_cfg(config), root):
        return True
    name = os.path.basename(str(file_path)).lower()
    return any(fnmatch.fnmatch(name, pat) for pat in EXTRA_CASE_NAMES)


def _read(path: str) -> Optional[str]:
    """檔不在回 None；檔在卻讀不到讓例外往上丟（閘判不了＝擋），不能當成新檔放過。"""
    p = Path(path)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def before_after(tool_name: str, tool_input: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """(改前, 改後) 全檔內容。Write 新檔＝改前空字串；Edit／MultiEdit 套不上磁碟現檔（檔不在、old_string 對不到；這時工具本身
    多半也會失敗）就退回只比 old_string／new_string 片段。拿不到要比的東西回 None。"""
    fp = tool_input.get("file_path", "") or ""
    disk = _read(fp)
    if tool_name == "Write":
        return (disk or "", str(tool_input.get("content", "") or ""))
    edits = tool_input.get("edits") if tool_name == "MultiEdit" else [tool_input]
    if not isinstance(edits, list) or not edits:
        return None
    pairs = [(str(e.get("old_string", "") or ""), str(e.get("new_string", "") or ""), bool(e.get("replace_all")))
             for e in edits if isinstance(e, dict)]
    cur = disk
    for old_s, new_s, every in pairs:
        if cur is None or not old_s or old_s not in cur:
            cur = None
            break
        cur = cur.replace(old_s, new_s) if every else cur.replace(old_s, new_s, 1)
    if cur is not None:
        return (disk or "", cur)
    return ("\n".join(p[0] for p in pairs), "\n".join(p[1] for p in pairs))


def _scan(line: str, marker: str) -> Tuple[str, int]:
    """(去掉註解的程式部分, 括號淨開數)。引號裡的 # 或 // 與括號不算。"""
    q, depth, i = None, 0, 0
    while i < len(line):
        ch = line[i]
        if q:
            if ch == "\\":
                i += 2
                continue
            if ch == q:
                q = None
        elif ch in "'\"`":
            q = ch
        elif line.startswith(marker, i):
            return line[:i], depth
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        i += 1
    return line, depth


def _logical(lines: List[str], marker: str) -> List[str]:
    """邏輯行：括號沒合上或行尾反斜線就併下一行；去註解、空白壓成一個；空行與純註解行不算。"""
    out: List[str] = []
    buf, depth = "", 0
    for raw in lines:
        code, d = _scan(raw, marker)
        code = code.strip()
        if not code and not buf:
            continue
        buf = f"{buf} {code}" if buf else code
        depth += d
        if depth > 0 or buf.endswith("\\"):
            continue
        out.append(_WS_RE.sub(" ", buf).strip())
        buf, depth = "", 0
    if buf:
        out.append(_WS_RE.sub(" ", buf).strip())
    return out


def _uniq(out: Dict[str, Dict[str, Any]], key: str, rec: Dict[str, Any]) -> None:
    k, n = key, 2
    while k in out:
        k, n = f"{key}#{n}", n + 1
    out[k] = rec


def _py_decorators(lines: List[str], i: int, ind: int) -> List[str]:
    """第 i 行（def／class）上方緊接的裝飾器；多行裝飾器的續行（縮排較深、或同縮排的收尾括號）一起收。"""
    deco: List[str] = []
    pending: List[str] = []
    for j in range(i - 1, -1, -1):
        s = lines[j]
        if not s.strip():
            break
        sind = len(s) - len(s.lstrip())
        if sind == ind and s.lstrip().startswith("@"):
            deco = [s, *pending, *deco]
            pending = []
        elif sind > ind or (sind == ind and s.lstrip()[0] in ")]}"):
            pending.insert(0, s)
        else:
            break
    return deco


def _py_tests(src: str) -> Dict[str, Dict[str, Any]]:
    lines = src.splitlines()
    out: Dict[str, Dict[str, Any]] = {}
    module_skip = any(_PY_MODULE_MARK_RE.match(ln) and _PY_SKIP_RE.search(ln) for ln in lines)
    classes: List[Tuple[int, str, bool]] = []
    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        ind = len(ln) - len(ln.lstrip())
        while classes and classes[-1][0] >= ind and not ln.lstrip().startswith(("@", ")", "]", "}")):
            classes.pop()
        c = _PY_CLASS_RE.match(ln)
        if c:
            classes.append((ind, c.group(2), bool(_PY_SKIP_RE.search("\n".join(_py_decorators(lines, i, ind))))))
            continue
        m = _PY_DEF_RE.match(ln)
        if not m:
            continue
        raw_body: List[str] = []
        inline = _PY_INLINE_BODY_RE.search(_scan(ln, "#")[0])
        if inline:
            raw_body.append(inline.group(1))
        for s in lines[i + 1:]:
            if s.strip() and len(s) - len(s.lstrip()) <= ind:
                break
            raw_body.append(s)
        body = _logical(raw_body, "#")
        deco = "\n".join(_py_decorators(lines, i, ind))
        skip = module_skip or any(cs for _, _, cs in classes) or bool(_PY_SKIP_RE.search(deco + "\n" + "\n".join(body)))
        _uniq(out, ".".join([n for _, n, _ in classes] + [m.group(2)]),
              {"body": body, "asserts": [b for b in body if _PY_ASSERT_RE.match(b)], "skip": skip, "suite": False})
    return out


def _chained(lines: List[str], marker: str) -> List[str]:
    """大括號語言的比對行：一行一筆（整支測試包在 it(…) 的括號裡，不能照括號併），去註解、空白壓成一個；
    `.toBe(1)` 這類以點開頭的續行併回上一行。"""
    out: List[str] = []
    for raw in lines:
        code = _WS_RE.sub(" ", _scan(raw, marker)[0]).strip()
        if not code:
            continue
        if code.startswith(".") and out:
            out[-1] += code
            continue
        out.append(code)
    return out


def _span_tests(lines: List[str], heads: List[Tuple[int, str, bool, bool]], marker: str) -> Dict[str, Dict[str, Any]]:
    """heads＝[(開頭行號, 名字, 跳過, 是不是 describe 這類分組)]；本體＝開頭那一行到下一個開頭之前（單行 it(…) 的斷言在開頭行上）。"""
    out: Dict[str, Dict[str, Any]] = {}
    for n, (at, name, skip, suite) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        body = _chained(lines[at:end], marker)
        _uniq(out, name, {"body": body, "asserts": [b for b in body if _OTHER_ASSERT_RE.search(b)], "skip": skip, "suite": suite})
    return out


def _js_tests(src: str) -> Dict[str, Dict[str, Any]]:
    heads = []
    for m in _JS_TEST_RE.finditer(src):
        mods, suite = m.group(3), m.group(2) in ("describe", "context")
        heads.append((src.count("\n", 0, m.start()), f"{m.group(2)}:{m.group(5)}" if suite else m.group(5),
                      bool(m.group(1)) or ".skip" in mods or ".todo" in mods, suite))
    return _span_tests(src.splitlines(), heads, "//")


def _annot_tests(src: str) -> Dict[str, Dict[str, Any]]:
    lines = src.splitlines()
    heads = []
    pending: List[str] = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s or s.startswith("//"):
            continue
        if _ANNOT_LINE_RE.match(ln):
            pending.append(s)
            continue
        ann = "\n".join(pending)
        pending = []
        m = _METHOD_RE.search(s)
        if m and _TEST_ANNOT_RE.search(ann):
            heads.append((i, m.group(1), bool(_SKIP_ANNOT_RE.search(ann)), False))
    return _span_tests(lines, heads, "//")


def extract_tests(src: str, path: str) -> Dict[str, Dict[str, Any]]:
    """測試 key（Python 帶外層類別：TestX.test_y；JS 分組：describe:<名>；同名第二支起加 #2）→ {body, asserts, skip, suite}。
    不認得的語言回空。"""
    ext = os.path.splitext(str(path))[1].lower()
    if ext in _PY_EXTS:
        return _py_tests(src)
    if ext in _JS_EXTS:
        return _js_tests(src)
    if ext in _ANNOT_EXTS:
        return _annot_tests(src)
    return {}


def body_similarity(a: List[str], b: List[str]) -> float:
    """改名的標記法（替身）：兩支本體邏輯行共同的行數 ÷ 較長那支的行數。只決定證據寫「改名」還是「消失」；
    放不放行仍要宣告行點名舊的那支。"""
    longest = max(len(a), len(b))
    return sum((Counter(a) & Counter(b)).values()) / longest if longest else 0.0


def diff_tests(old_src: str, new_src: str, path: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """回 (動到的既有測試 [{key, kind, detail, new_key?}], 這次新加的測試 key)。kind ∈ gone／renamed／assert／skip。
    改名＝舊的一支消失、新出現的一支本體相似度 ≥ RENAME_MIN_SIMILARITY；配不上的照消失。describe 這類分組只看加跳過。"""
    old_t, new_t = extract_tests(old_src, path), extract_tests(new_src, path)
    added = [k for k in new_t if k not in old_t and not new_t[k]["suite"]]
    changes: List[Dict[str, str]] = []
    for k, o in old_t.items():
        n = new_t.get(k)
        if o["suite"]:
            if n is not None and n["skip"] and not o["skip"]:
                changes.append({"key": k, "kind": "skip", "detail": ""})
            continue
        if n is None:
            mate = next((a for a in added if body_similarity(o["body"], new_t[a]["body"]) >= RENAME_MIN_SIMILARITY), None)
            if mate:
                added.remove(mate)
                changes.append({"key": k, "kind": "renamed", "detail": "", "new_key": mate})
            else:
                changes.append({"key": k, "kind": "gone", "detail": ""})
            continue
        lost = list((Counter(o["asserts"]) - Counter(n["asserts"])).elements())
        if lost:
            changes.append({"key": k, "kind": "assert", "detail": lost[0][:80]})
        if n["skip"] and not o["skip"]:
            changes.append({"key": k, "kind": "skip", "detail": ""})
    return changes, added


def _declaration_text(transcript_path: str) -> str:
    from overview_hub import LOCATE_CHANNELS, assistant_text_after
    return "\n".join(assistant_text_after(transcript_path, 0, ch) for ch in LOCATE_CHANNELS)


def _log(event: str, sid: str, path: str, **kw: Any) -> None:
    from wg_core import append_guard_log
    append_guard_log(GUARD, {"event": event, "session": sid, "file": path, **kw})


def hint(first: str) -> str:
    return (f"真的要改這幾支舊測試 → 先寫一行「改舊測試｜{first}：<為什麼舊斷言不再對；使用者原話>」，多支用「、」分隔、每支都要列到"
            "（改名寫舊的名字）；放回覆文字或下一個 Bash 開頭 `#` 註解；使用者有說要改就引用原句；拿不準就 AskUserQuestion 問使用者。"
            "只加新測試不用宣告。")


def gate(tool_name: str, tool_input: Dict[str, Any], input_data: Dict[str, Any], config: Dict[str, Any],
         cwd: str) -> Optional[str]:
    """PreToolUse：動到既有測試又找不到宣告行 → 回擋訊息；其餘回 None。宣告過與本 session 自己新加的測試記 state，之後不再擋。"""
    if tool_name not in ("Edit", "MultiEdit", "Write") or not _cfg(config).get("enabled", True):
        return None
    fp = str(tool_input.get("file_path", "") or "")
    # 認得的語言才往下（每次 Edit／Write 都會經過這裡，先用副檔名擋掉，不載入判式）
    if not fp.lower().endswith(_PY_EXTS + _JS_EXTS + _ANNOT_EXTS) or not is_test_file(fp, config, _root(fp, cwd)):
        return None
    ba = before_after(tool_name, tool_input)
    if ba is None:
        return None
    changes, added = diff_tests(ba[0], ba[1], fp)
    sid = input_data.get("session_id", "") or ""
    import wg_release_rules as rr
    from wg_core import read_state, write_state
    state = read_state(sid) if sid else None
    cp = rr.canon_path(fp)
    seen_added = set((state or {}).get("old_test_added") or [])
    seen_decl = set((state or {}).get("old_test_declared") or [])
    live = []
    for c in changes:
        k = f"{cp}|{c['key']}"
        if k in seen_added or k in seen_decl:
            _log("exempt", sid, fp, test=c["key"], kind=c["kind"],
                 why="session_added" if k in seen_added else "declared_before")
            continue
        live.append(c)
    decls = rr.parse_old_test_declarations(_declaration_text(input_data.get("transcript_path", "") or "")) if live else []
    v = rr.old_test_change_verdict(fp, live, decls)
    if v.owed:
        _log("denied", sid, fp, tool=tool_name, changes=live)
        return rr.format_hit("ot", v) + "\n" + hint(next(c["key"] for c in live if rr.old_test_declaration_for(c, decls, fp) is None))
    for c in live:
        d = rr.old_test_declaration_for(c, decls, fp) or {}
        _log("declared", sid, fp, test=c["key"], kind=c["kind"], new_key=c.get("new_key", ""),
             reason=d.get("reason", "")[:200], line=d.get("line", ""))
        seen_decl.update(f"{cp}|{x}" for x in (c["key"], c.get("new_key")) if x)
    seen_added.update(f"{cp}|{a}" for a in added)
    if state is not None and (live or added):
        state["old_test_declared"] = sorted(seen_decl)
        state["old_test_added"] = sorted(seen_added)
        write_state(sid, state)
    return None
