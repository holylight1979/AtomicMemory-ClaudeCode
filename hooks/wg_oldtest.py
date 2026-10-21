"""wg_oldtest.py — 改舊測試要先宣告（規則 OLD_TEST_CHANGE_NEEDS_DECLARATION）：收事實、留帳、組擋訊息。

抓五種「動既有測試」：消失、改名、同名測試的斷言被刪或改、新加跳過標記、說明（docstring）被改或刪；再到 transcript 三管道
（回覆文字／工具參數／thinking，與定位三行同一套 assistant_text_after）加上這次工具呼叫的參數找宣告行「改舊測試｜<函式名>：<理由>」。
判定在 wg_release_rules.old_test_change_verdict。兩條路：
- Edit／MultiEdit／Write：PreToolUse 比對改前（磁碟現檔）與改後（套用 old_string→new_string，或 Write 的新內容），沒宣告當場擋。
- Bash／PowerShell／NotebookEdit：寫之前看不到改後內容，PreToolUse 把寫入目標裡的測試檔拍快照（workflow/old-test-snap/），
  PostToolUse 拿快照比磁碟（after_tool），沒宣告的記 state `old_test_undeclared`，下一個任何工具呼叫在 PreToolUse 擋到補宣告為止；
  只讀或只寫這幾個欠帳檔（撤回）的呼叫不擋，撤回後的 PostToolUse 把已恢復的那筆清掉。

切本體：Python 照縮排（含單行 `def test_x(): assert …`；notebook 取所有程式格接起來），斷言以邏輯行比（括號或三引號沒合上、
行尾反斜線就併下一行），本體第一行是字串就是說明；JS／TS（it／test，describe 只看跳過；描述文字就是名字，改了算改名）、
C#（[Test]／[Fact]／[TestMethod]／[Theory]）、Java（@Test）從這支的開頭行到下一支開頭都算它的（尾端 helper 的斷言會算給最後一支，
只會多問一次宣告），斷言一行一筆、點開頭的續行併回上一行。比之前都去註解、空白壓成一個。
Bash 寫入目標靠 wg_core.write_paths_from_tool；python 腳本自己開檔寫的解析不到，改看 git：執行 python 前記下 repo 裡已經有改動的
測試檔與內容，執行後新出現改動的取 HEAD 當改前（執行前乾淨＝磁碟與 HEAD 相同）。node 等其他直譯器自己寫檔、不在 git repo 裡的抓不到。
怎麼驗：python -X utf8 -m pytest -q hooks/verify/verify_old_test_declare.py
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GUARD = "old_test"
# 共用的案例檔判式（wg_verify_ledger.is_case_file）沒涵蓋的 C#／Java 測試檔名慣例
EXTRA_CASE_NAMES = ("*tests.cs", "*test.cs", "*tests.java", "*test.java")
_PY_EXTS = (".py",)
_NB_EXTS = (".ipynb",)
_JS_EXTS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")
_ANNOT_EXTS = (".cs", ".java")
_ALL_EXTS = _PY_EXTS + _NB_EXTS + _JS_EXTS + _ANNOT_EXTS
EDIT_TOOLS = ("Edit", "MultiEdit", "Write")
AFTER_TOOLS = ("Bash", "PowerShell", "NotebookEdit")   # 寫之前看不到改後內容，事後比對
PENDING_KEY = "old_test_undeclared"
# 指令會執行 python（python／python3.12／py／pythonw，可帶路徑與 .exe）：腳本自己開檔寫的目標 write_paths_from_tool 解析不到
_PY_RUN_RE = re.compile(r"(?:^|[\s;&|(`'\"\\/])(?:python[\d.]*|pythonw|py)(?:\.exe)?(?=\s|$|[;&|)`'\"])", re.IGNORECASE | re.MULTILINE)

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
_PY_DOC_RE = re.compile(r"^[rRuUbB]?['\"]")
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
    """重用寫碼查核的案例檔判式（reconcile_gate 的 verify_case_globs＋code_exts），再補 C#／Java 的 FooTests.cs／FooTest.java；
    notebook 不算程式檔，只看 verify_case_globs。"""
    import wg_verify_ledger as vl
    cfg = vl.reconcile_cfg(config)
    if str(file_path).lower().endswith(_NB_EXTS):
        return vl.is_verify_case(file_path, cfg.get("verify_case_globs") or [], root)
    if vl.is_case_file(file_path, cfg, root):
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
        if depth > 0 or buf.endswith("\\") or buf.count('"""') % 2 or buf.count("'''") % 2:
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
        doc = body[0] if body and _PY_DOC_RE.match(body[0]) else ""
        _uniq(out, ".".join([n for _, n, _ in classes] + [m.group(2)]),
              {"body": body, "asserts": [b for b in body if _PY_ASSERT_RE.match(b)], "skip": skip, "suite": False, "doc": doc})
    return out


def _notebook_code(src: str) -> str:
    """notebook 的所有程式格接成一份 Python（格與格之間空兩行）。JSON 壞掉回空字串。"""
    try:
        cells = json.loads(src or "{}").get("cells") or []
    except (ValueError, AttributeError):
        return ""
    out = []
    for c in cells:
        if isinstance(c, dict) and c.get("cell_type") == "code":
            s = c.get("source", "")
            out.append("".join(s) if isinstance(s, list) else str(s))
    return "\n\n\n".join(out)


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
        _uniq(out, name, {"body": body, "asserts": [b for b in body if _OTHER_ASSERT_RE.search(b)], "skip": skip, "suite": suite,
                          "doc": ""})
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
    if ext in _NB_EXTS:
        return _py_tests(_notebook_code(src))
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
    """回 (動到的既有測試 [{key, kind, detail, new_key?}], 這次新加的測試 key)。kind ∈ gone／renamed／assert／skip／doc
    （doc＝原本有說明、說明被改或刪；原本沒說明、新加的不算）。
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
        if o["doc"] and n["doc"] != o["doc"]:
            changes.append({"key": k, "kind": "doc", "detail": o["doc"][:80]})
    return changes, added


def _strings(obj: Any) -> List[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in _strings(v)]
    return []


def _decl_text(input_data: Dict[str, Any]) -> str:
    """找宣告行的範圍：transcript 三管道（主檔與子代理檔都從頭，wg_core.assistant_texts_since）＋這次工具呼叫自己的參數
    （Bash 開頭的 `#` 註解不必等下一則訊息）。"""
    from overview_hub import LOCATE_CHANNELS
    from wg_core import assistant_texts_since
    tp = input_data.get("transcript_path", "") or ""
    agent_id = str(input_data.get("agent_id") or "")
    parts = [assistant_texts_since(tp, agent_id, ch) for ch in LOCATE_CHANNELS]
    return "\n".join(parts + _strings(input_data.get("tool_input") or {}))


def _log(event: str, sid: str, path: str, **kw: Any) -> None:
    from wg_core import append_guard_log
    append_guard_log(GUARD, {"event": event, "session": sid, "file": path, **kw})


def hint(first: str) -> str:
    return (f"真的要改這幾支舊測試 → 先寫一行「改舊測試｜{first}：<為什麼舊斷言不再對；使用者原話>」，多支用「、」分隔、每支都要列到"
            "（改名寫舊的名字）；放回覆文字或下一個 Bash 開頭 `#` 註解；使用者有說要改就引用原句；拿不準就 AskUserQuestion 問使用者。"
            "只加新測試不用宣告。")


def _changes(state: Optional[Dict[str, Any]], sid: str, fp: str, before: str, after: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """(要看宣告的動作, 這次新加的測試)：本 session 自己新加的、宣告過的那支記 exempt 放過。"""
    import wg_release_rules as rr
    changes, added = diff_tests(before, after, fp)
    cp = rr.canon_path(fp)
    seen_added = set((state or {}).get("old_test_added") or [])
    seen_decl = set((state or {}).get("old_test_declared") or [])
    live = []
    for c in changes:
        k = f"{cp}|{c['key']}"
        if k in seen_added or k in seen_decl:
            _log("exempt", sid, fp, test=c["key"], kind=c["kind"], why="session_added" if k in seen_added else "declared_before")
            continue
        live.append(c)
    return live, added


def _record(state: Optional[Dict[str, Any]], sid: str, fp: str, done: List[Dict[str, str]], added: List[str],
            decls: List[Dict[str, Any]], event: str = "declared") -> bool:
    """宣告對上的那幾支留帳並記進 old_test_declared（連同改名後的新名），新加的測試記進 old_test_added；就地改 state，回有沒有改。"""
    import wg_release_rules as rr
    cp = rr.canon_path(fp)
    for c in done:
        d = rr.old_test_declaration_for(c, decls, fp) or {}
        _log(event, sid, fp, test=c["key"], kind=c["kind"], new_key=c.get("new_key", ""), tool=c.get("tool", ""),
             reason=d.get("reason", "")[:200], line=d.get("line", ""))
    if state is None or not (done or added):
        return False
    decl = set(state.get("old_test_declared") or [])
    decl.update(f"{cp}|{x}" for c in done for x in (c["key"], c.get("new_key")) if x)
    state["old_test_declared"] = sorted(decl)
    state["old_test_added"] = sorted(set(state.get("old_test_added") or []) | {f"{cp}|{a}" for a in added})
    return True


def _test_targets(tool_name: str, tool_input: Dict[str, Any], config: Dict[str, Any], cwd: str) -> List[str]:
    """這次工具呼叫寫到的測試檔。Bash／PowerShell 的寫入目標由 wg_core.write_paths_from_tool 解析（目標不明的 UNKNOWN 略過，
    OverviewHub 會擋那種指令）。"""
    if tool_name == "NotebookEdit":
        paths = [str(tool_input.get("notebook_path", "") or "")]
    elif tool_name in EDIT_TOOLS:
        paths = [str(tool_input.get("file_path", "") or "")]
    else:
        from wg_core import write_paths_from_tool
        paths = [p for p in (write_paths_from_tool(tool_name, tool_input, cwd) or []) if p and not p.startswith("UNKNOWN:")]
    # 認得的語言才往下（每次寫檔都會經過這裡，先用副檔名擋掉，不載入判式）
    return [p for p in paths if p.lower().endswith(_ALL_EXTS) and is_test_file(p, config, _root(p, cwd))]


def _snap_file(sid: str, tool_name: str, tool_input: Dict[str, Any]) -> Path:
    """改前快照的檔：PreToolUse 與 PostToolUse 拿到的 tool_input 相同，用它的雜湊對上同一次呼叫。"""
    import wg_core
    key = hashlib.sha1(json.dumps([tool_name, tool_input], sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
    return Path(wg_core.WORKFLOW_DIR) / "old-test-snap" / f"{sid or 'nosid'}-{key.hexdigest()[:16]}.json"


def _git(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", root, *args], capture_output=True, timeout=10,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _dirty_tests(root: str, config: Dict[str, Any]) -> List[str]:
    """git repo 裡有改動（含未追蹤、刪除）的測試檔絕對路徑。查不到丟例外。"""
    r = _git(root, "status", "--porcelain", "-z", "--untracked-files=all")
    if r.returncode:
        raise RuntimeError(f"git status 失敗：{r.stderr.decode('utf-8', 'replace').strip()[:200]}")
    entries = r.stdout.decode("utf-8", "replace").split("\0")
    out: List[str] = []
    i = 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        if e[0] in "RC":
            i += 1   # -z 的改名／複製後面多一筆原路徑
        p = str(Path(root) / e[3:])
        if p.lower().endswith(_ALL_EXTS) and is_test_file(p, config, root):
            out.append(p)
    return out


def _head_text(root: str, path: str) -> str:
    """HEAD 裡這個檔的內容；HEAD 沒有（新檔）回空字串。"""
    r = _git(root, "show", f"HEAD:{Path(path).relative_to(root).as_posix()}")
    return r.stdout.decode("utf-8", "replace").replace("\r\n", "\n") if r.returncode == 0 else ""


def _py_baseline(tool_input: Dict[str, Any], config: Dict[str, Any], cwd: str, sid: str) -> Optional[Dict[str, Any]]:
    """指令會執行 python（腳本自己開檔寫的目標解析不到）：記下 repo 裡這時已經有改動的測試檔與內容。不是 git repo 回 None；
    git 查不到只能 stderr＋留帳（不擋所有 python 指令）。"""
    if not _PY_RUN_RE.search(str(tool_input.get("command", "") or "")):
        return None
    from wg_core import find_vcs_root
    hit = find_vcs_root(Path(cwd or "."))
    if not hit or hit[0] != "git":
        return None
    root = str(hit[1])
    try:
        return {"root": root, "dirty": {p: _read(p) for p in _dirty_tests(root, config)}}
    except Exception as e:
        print(f"[Guardian:OldTestDeclare] 執行 python 前查不到 git 狀態（這次 python 改測試檔沒核對到）：{e}", file=sys.stderr)
        _log("py_baseline_error", sid, root, error=f"{type(e).__name__}: {e}")
        return None


def snapshot(tool_name: str, tool_input: Dict[str, Any], input_data: Dict[str, Any], config: Dict[str, Any], cwd: str) -> None:
    """PreToolUse（Bash／PowerShell／NotebookEdit）：寫入目標裡的測試檔拍改前快照（檔還不存在記 None；讀不到讓例外往上丟＝擋）；
    指令會執行 python 再加記 repo 裡已經有改動的測試檔（_py_baseline）。"""
    sid = input_data.get("session_id", "") or ""
    files = {p: _read(p) for p in _test_targets(tool_name, tool_input, config, cwd)}
    py = _py_baseline(tool_input, config, cwd, sid) if tool_name in ("Bash", "PowerShell") else None
    if not files and py is None:
        return
    f = _snap_file(sid, tool_name, tool_input)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"files": files, "py": py}, ensure_ascii=False), encoding="utf-8", newline="\n")


def _snap_pairs(snap: Dict[str, Any], config: Dict[str, Any], sid: str) -> Dict[str, Optional[str]]:
    """要比對的 {測試檔: 改前內容}：寫入目標的快照，加上執行 python 後才出現改動的測試檔——執行前是乾淨的取 HEAD
    （乾淨＝磁碟與 HEAD 相同），執行前就有改動的取當時記下的內容。"""
    pairs = dict(snap.get("files") or {})
    py = snap.get("py")
    if not py:
        return pairs
    try:
        now = _dirty_tests(py["root"], config)
    except Exception as e:
        print(f"[Guardian:OldTestDeclare] 執行 python 後查不到 git 狀態（這次 python 改測試檔沒核對到）：{e}", file=sys.stderr)
        _log("py_after_error", sid, py["root"], error=f"{type(e).__name__}: {e}")
        return pairs
    dirty = py.get("dirty") or {}
    for p in now:
        if p not in pairs:
            pairs[p] = dirty[p] if p in dirty else _head_text(py["root"], p)
    return pairs


def _restored(e: Dict[str, Any]) -> bool:
    """欠帳的那一筆已經撤回：那支測試回來了，且被動的那一處（斷言、跳過、說明）回到原樣。"""
    cur = extract_tests(_read(e["file"]) or "", e["file"]).get(e["key"])
    if cur is None:
        return False
    kind = e["kind"]
    if kind == "assert":
        return not (Counter(e.get("old_asserts") or []) - Counter(cur["asserts"]))
    if kind == "skip":
        return not cur["skip"]
    if kind == "doc":
        return cur["doc"] == e.get("old_doc", "")
    return True   # gone／renamed：舊名字回來了


def after_tool(state: Optional[Dict[str, Any]], input_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """PostToolUse：Bash／PowerShell／NotebookEdit 拿改前快照比磁碟，動到既有測試又沒宣告的記進 state[PENDING_KEY]（下一個工具呼叫擋）；
    這次碰到的檔上還欠著的、已經撤回的清掉。state＝post_tool_use 那一份（就地改，由它尾端寫回）；回有沒有改。"""
    if state is None or not _cfg(config).get("enabled", True):
        return False
    import wg_release_rules as rr
    tool_name, tool_input = input_data.get("tool_name", ""), input_data.get("tool_input") or {}
    sid = input_data.get("session_id", "") or ""
    pending = list(state.get(PENDING_KEY) or [])
    before_n, changed, touched = len(pending), False, set()
    if tool_name in AFTER_TOOLS:
        f = _snap_file(sid, tool_name, tool_input)
        snap = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        f.unlink(missing_ok=True)
        text = None
        for path, before in _snap_pairs(snap, config, sid).items():
            touched.add(rr.canon_path(path))
            live, added = _changes(state, sid, path, before or "", _read(path) or "")
            if live and text is None:
                text = _decl_text(input_data)
            decls = rr.parse_old_test_declarations(text) if live else []
            old_t = extract_tests(before or "", path) if live else {}
            done = []
            for c in live:
                if rr.old_test_declaration_for(c, decls, path):
                    done.append({**c, "tool": tool_name})
                    continue
                o = old_t.get(c["key"]) or {}
                entry = {**c, "file": path, "tool": tool_name, "old_asserts": o.get("asserts", []), "old_doc": o.get("doc", "")}
                if not any(rr.same_file(e["file"], path) and e["key"] == c["key"] and e["kind"] == c["kind"] for e in pending):
                    pending.append(entry)
                    _log("undeclared", sid, path, tool=tool_name, test=c["key"], kind=c["kind"])
            changed = _record(state, sid, path, done, added, decls) or changed
    elif tool_name in EDIT_TOOLS and tool_input.get("file_path"):
        touched.add(rr.canon_path(tool_input["file_path"]))
    keep = []
    for e in pending:
        if rr.canon_path(e["file"]) in touched and _restored(e):
            _log("reverted", sid, e["file"], test=e["key"], kind=e["kind"], tool=tool_name)
            continue
        keep.append(e)
    if len(keep) != before_n or changed:
        state[PENDING_KEY] = keep
        return True
    return False


def _only_touches(tool_name: str, tool_input: Dict[str, Any], cwd: str, files: set) -> bool:
    """這次呼叫只讀或只寫欠帳的那幾個檔（撤回用）。"""
    import wg_release_rules as rr
    if tool_name == "Read" or tool_name in EDIT_TOOLS or tool_name == "NotebookEdit":
        p = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        return bool(p) and rr.canon_path(p) in files
    if tool_name in ("Bash", "PowerShell"):
        from wg_core import write_paths_from_tool
        ts = write_paths_from_tool(tool_name, tool_input, cwd) or []
        return bool(ts) and all(not t.startswith("UNKNOWN:") and rr.canon_path(t) in files for t in ts)
    return False


def _pending_deny(tool_name: str, tool_input: Dict[str, Any], input_data: Dict[str, Any], cwd: str) -> Optional[str]:
    """上一個 Bash／PowerShell／NotebookEdit 動了既有測試沒宣告：這次（任何工具）先找宣告，補了的清掉、留帳 declared_late；
    還欠著就擋，除非這次只讀或只寫那幾個檔（撤回）。"""
    sid = input_data.get("session_id", "") or ""
    if not sid:
        return None
    from wg_core import read_state, write_state
    state = read_state(sid)
    pending = list((state or {}).get(PENDING_KEY) or [])
    if not pending:
        return None
    import wg_release_rules as rr
    decls = rr.parse_old_test_declarations(_decl_text(input_data))
    left, done = [], {}
    for e in pending:
        (done.setdefault(e["file"], []) if rr.old_test_declaration_for(e, decls, e["file"]) else left).append(e)
    if done:
        for fp, es in done.items():
            _record(state, sid, fp, es, [], decls, "declared_late")
        state[PENDING_KEY] = left
        write_state(sid, state)
    if not left or _only_touches(tool_name, tool_input, cwd, {rr.canon_path(e["file"]) for e in left}):
        return None
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for e in left:
        by_file.setdefault(e["file"], []).append(e)
    _log("denied_late", sid, left[0]["file"], tool=tool_name, pending=[{k: e[k] for k in ("file", "key", "kind")} for e in left])
    tools = "／".join(sorted({e.get("tool", "") for e in left}))
    return ("\n".join(rr.format_hit("ot", rr.old_test_change_verdict(fp, es, decls)) for fp, es in by_file.items())
            + f"\n這是 {tools} 改的（已經寫進檔），請補宣告再繼續；要撤回就只讀、只改這幾個檔。\n" + hint(left[0]["key"]))


def gate(tool_name: str, tool_input: Dict[str, Any], input_data: Dict[str, Any], config: Dict[str, Any],
         cwd: str) -> Optional[str]:
    """PreToolUse：①上一個 Bash 類呼叫還欠宣告 → 擋（任何工具）；②Bash／PowerShell／NotebookEdit → 拍快照放行，事後由 after_tool 比；
    ③Edit／MultiEdit／Write 動到既有測試又找不到宣告行 → 擋。宣告過與本 session 自己新加的測試記 state，之後不再擋。"""
    if not _cfg(config).get("enabled", True):
        return None
    late = _pending_deny(tool_name, tool_input, input_data, cwd)
    if late:
        return late
    if tool_name in AFTER_TOOLS:
        snapshot(tool_name, tool_input, input_data, config, cwd)
        return None
    if tool_name not in EDIT_TOOLS or not _test_targets(tool_name, tool_input, config, cwd):
        return None
    fp = str(tool_input.get("file_path", "") or "")
    ba = before_after(tool_name, tool_input)
    if ba is None:
        return None
    sid = input_data.get("session_id", "") or ""
    import wg_release_rules as rr
    from wg_core import read_state, write_state
    state = read_state(sid) if sid else None
    live, added = _changes(state, sid, fp, ba[0], ba[1])
    # 已經欠著宣告的那幾支（上一個 Bash 改的）這次再動不另算：多半是撤回，撤回成不成由 after_tool 判、清帳
    owing = {(rr.canon_path(e["file"]), e["key"]) for e in (state or {}).get(PENDING_KEY) or []}
    live = [c for c in live if (rr.canon_path(fp), c["key"]) not in owing]
    decls = rr.parse_old_test_declarations(_decl_text(input_data)) if live else []
    v = rr.old_test_change_verdict(fp, live, decls)
    if v.owed:
        _log("denied", sid, fp, tool=tool_name, changes=live)
        return rr.format_hit("ot", v) + "\n" + hint(next(c["key"] for c in live if rr.old_test_declaration_for(c, decls, fp) is None))
    if _record(state, sid, fp, live, added, decls):
        write_state(sid, state)
    return None
