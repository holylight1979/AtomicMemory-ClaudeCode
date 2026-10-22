"""wg_oldtest.py — 改舊測試要先宣告（規則 OLD_TEST_CHANGE_NEEDS_DECLARATION）：收事實、留帳、組擋訊息。

抓五種「動既有測試」：消失、改名、同名測試的斷言被刪或改、新加跳過標記、說明（docstring）被改或刪；再到 transcript 三管道
（回覆文字／工具參數／thinking，與定位三行同一套 assistant_text_after）加上這次工具呼叫的參數找宣告行「改舊測試｜<函式名>：<理由>」。
判定在 wg_release_rules.old_test_change_verdict。兩條路：
- Edit／MultiEdit／Write：PreToolUse 比對改前（磁碟現檔）與改後（套用 old_string→new_string，或 Write 的新內容），沒宣告當場擋。
- Bash／PowerShell／NotebookEdit：寫之前看不到改後內容，PreToolUse 把寫入目標裡的測試檔拍快照（workflow/old-test-snap/），
  PostToolUse 拿快照比磁碟（after_tool），沒宣告的記 state `old_test_undeclared`，下一個任何工具呼叫在 PreToolUse 擋到補宣告為止；
  兩條路的擋都有上限：同一個使用者回合同一件（檔＋測試＋動作）擋滿兩次就放行、留帳 cap_released（欠帳那筆一併拿掉）；
  只讀或只寫這幾個欠帳檔（撤回）的呼叫不擋，撤回後的 PostToolUse 把已恢復的那筆清掉。
本 session 新加的測試不算舊測試：記在 old_test_added（比對時看到新增），另有基線 old_test_baseline＝第一次拍快照時那個檔有哪些測試；
指令失敗時 Claude Code 不送 PostToolUse、old_test_added 記不到，基線沒有的那支照樣放過。

切本體：Python 照縮排（含單行 `def test_x(): assert …`；notebook 取所有程式格接起來），斷言以邏輯行比（括號或三引號沒合上、
行尾反斜線就併下一行），本體第一行是字串就是說明；JS／TS（it／test，describe 只看跳過；描述文字就是名字，改了算改名）、
C#（[Test]／[Fact]／[TestMethod]／[Theory]）、Java（@Test）從這支的開頭行到下一支開頭都算它的（尾端 helper 的斷言會算給最後一支，
只會多問一次宣告），斷言一行一筆、點開頭的續行併回上一行。比之前都去註解、空白壓成一個。
Bash 寫入目標靠 wg_core.write_paths_from_tool；python 腳本自己開檔寫的解析不到，改看 git：執行 python 前記下 HEAD、進行中的
合併類操作標記、logs/HEAD 長度、repo 裡已經有改動的測試檔與內容，執行後新出現改動的取執行前的 HEAD 當改前（執行前乾淨＝磁碟
與 HEAD 相同）；同一條指令自己 commit 掉、工作樹又乾淨的也算：logs/HEAD 裡這條指令自己 commit／revert 的每筆前後之間有變的
測試檔一併比對（OWN_COMMIT_CHANGES_STILL_COMPARED；合併提交不算）。git 自己產出的內容另外算（_git_after）：這條指令開始的 merge／squash／cherry-pick／rebase 停在半路 →
git merge-tree 從 commit 重算；HEAD 被 merge／pull／rebase／切分支移動（看這段期間 logs/HEAD 的每一筆，自己 commit、revert 不算）→ 新 HEAD。
有它就只算比 git 產出的也變了的動作（同一支腳本之後再改、再 add 的照算），git 帶進來的測試併入基線：別的分支帶進來的是舊測試，
不能當本 session 新加的放過；判不出就照執行前的內容比（寧可多擋）。node 等其他直譯器自己寫檔、不在 git repo 裡的抓不到。
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
from typing import Any, Dict, Iterable, List, Optional, Tuple

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
BASELINE_KEY = "old_test_baseline"   # {檔: 本 session 第一次碰它時有哪些測試}
# 指令會執行 python（python／python3.12／py／pythonw，可帶路徑與 .exe）：腳本自己開檔寫的目標 write_paths_from_tool 解析不到
_PY_RUN_RE = re.compile(r"(?:^|[\s;&|(`'\"\\/])(?:python[\d.]*|pythonw|py)(?:\.exe)?(?=\s|$|[;&|)`'\"])", re.IGNORECASE | re.MULTILINE)

# Bash 的 `cat > 檔 <<'TAG'`／`cat >> 檔 <<TAG`／`cat <<TAG > 檔`：heredoc 的內容就是要寫進去的，寫之前就能比對
_HEREDOC_PATH = r"(?P<{0}>'[^'\n]+'|\"[^\"\n]+\"|[^\s;&|<>'\"]+)"
_CAT_HEREDOC_RE = re.compile(
    r"(?:^|[;&|(]\s*)cat\s+(?:"
    r"(?P<op1>>>?)\s*" + _HEREDOC_PATH.format("p1") + r"\s*<<-?\s*['\"]?\w+"
    r"|<<-?\s*['\"]?\w+['\"]?\s*(?P<op2>>>?)\s*" + _HEREDOC_PATH.format("p2") + r")")
_HEREDOC_TAG_RE = re.compile(r"(?<!<)<<(?!<)(-?)\s*(['\"]?)(\w+)\2")
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
# git show HEAD:<路徑> 失敗時，這幾種是「HEAD 本來就沒有」（新檔、還沒有 commit），其他才是查詢失敗
_HEAD_MISSING_RE = re.compile(r"does not exist in|exists on disk, but not in|invalid object name 'HEAD'|"
                              r"bad revision 'HEAD'|unknown revision", re.IGNORECASE)
# git status --porcelain=v2 每種紀錄在路徑前面有幾個以空白分隔的欄位（1 一般改動、2 改名或複製、u 衝突、? 未追蹤）
_V2_FIELDS = {"1": 8, "2": 9, "u": 10, "?": 1}
# 把別人的內容合進來、停在半路時 git 目錄裡留的標記（merge --squash 不設 MERGE_HEAD、只留 SQUASH_MSG）。revert 不在內：
# 撤掉哪個 commit 是本 session 自己的決定，撤掉的測試照算本 session 改的
GIT_OP_MARKS = ("MERGE_HEAD", "SQUASH_MSG", "CHERRY_PICK_HEAD", "REBASE_HEAD", "rebase-merge", "rebase-apply")
_OWN_MOVES = ("commit", "revert")   # reflog 說明這樣開頭的是本 session 自己讓 HEAD 動的
_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")


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
    """檔不在回 None；檔在卻讀不到讓例外往上丟（閘判不了：PreToolUse 不擋、留帳 error），不能當成新檔放過。"""
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
    return ("宣告行要比這次工具呼叫早一則訊息送出（跟工具呼叫同一則送出的文字，這裡還看不到），或寫成下一個 Bash／PowerShell 指令開頭的 "
            f"`#` 註解。真的要改這幾支舊測試 → 先分是哪一種：使用者要的新行為讓舊斷言不再對（例：使用者要千分位、舊斷言沒有千分位）"
            f"→ 先寫一行「改舊測試｜{first}：<為什麼舊斷言不再對；使用者原話>」再改，多支用「、」分隔、每支都要列到（改名寫舊的名字）；"
            "使用者只說「跳過／先不管」某支紅測＝這件不做、不是讓它不紅 → 別加 skip、別改斷言，"
            "撤回這次修改讓它照紅，收尾寫「不做｜<那支測試>：使用者說「<原句>」」。兩種都對不上才 AskUserQuestion 問使用者。"
            "只加新測試不用宣告。")


def remember_baseline(state: Optional[Dict[str, Any]], pairs: Dict[str, Optional[str]], rev: str = "HEAD") -> bool:
    """{測試檔: 改前內容} 裡本 session 還沒記過的檔，把當時有哪些測試（磁碟上的加上 git rev 裡的）記進 state[BASELINE_KEY]
    （第一次碰到為準，之後不覆蓋）；就地改 state，回有沒有改。基線沒有的測試＝本 session 新加的：寫它的那次指令失敗時
    Claude Code 不送 PostToolUse，old_test_added 記不到，靠這份基線照樣認得。rev＝改前那一刻的 commit：事後補記的（after_tool）
    傳執行前的 HEAD，同一條指令新加又 commit 掉的測試才不會因為已進 HEAD 被當成舊測試。"""
    if state is None:
        return False
    import wg_release_rules as rr
    base = state.setdefault(BASELINE_KEY, {})
    fresh = {rr.canon_path(p): sorted(set(extract_tests(src or "", p)) | _head_tests(p, rev))
             for p, src in pairs.items() if rr.canon_path(p) not in base}
    base.update(fresh)
    return bool(fresh)


def _head_tests(path: str, rev: str = "HEAD") -> set:
    """git rev（預設 HEAD）裡這個檔有哪些測試（不在 git repo、rev 沒有這個檔 → 空）。基線要併進來：session 開始前就被刪掉（未提交）
    或被拿掉一支的舊測試，之後還原再改，仍算舊測試。查不到 git 只 stderr＋留帳，基線退回只看磁碟。"""
    from wg_core import find_vcs_root
    hit = find_vcs_root(Path(path).parent)
    if not hit or hit[0] != "git":
        return set()
    try:
        root = str(hit[1])
        r = _git(root, "show", f"{rev}:{Path(path).relative_to(root).as_posix()}",
                 env={**os.environ, "LC_ALL": "C", "LANGUAGE": "C"})   # 錯誤訊息固定英文，_HEAD_MISSING_RE 才對得上
        if r.returncode:
            err = r.stderr.decode("utf-8", "replace").strip()
            if _HEAD_MISSING_RE.search(err):
                return set()   # HEAD 沒有這個檔（本 session 新建）或 repo 還沒有 commit
            raise RuntimeError(f"git show 失敗：{err[:200]}")
        return set(extract_tests(r.stdout.decode("utf-8", "replace").replace("\r\n", "\n"), path))
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:OldTestDeclare] 基線查不到 git HEAD（只用磁碟上的測試當基線）：{path}：{e}", file=sys.stderr)
        _log("baseline_head_error", "", path, error=f"{type(e).__name__}: {e}")
        return set()


def _kind_key(c: Dict[str, str]) -> Tuple[str, str]:
    return c["key"], "gone" if c["kind"] in ("gone", "renamed") else c["kind"]


def _against_side(before: str, after: str, side: str, fp: str, prior: bool) -> Tuple[List[Dict[str, str]], List[str]]:
    """有 git 產出的內容（side）時這次的動作：比 git 產出的變了（改回執行前的值也算：撤掉別的分支帶進來的改動）；新加的以 git 產出的為準
    （git 帶進來的不是本 session 新加的）。prior＝執行前這個檔就有本 session 沒 commit 的改動（autostash 這類會把它放回來）：
    那支測試執行前就有的，比改前也要變了才算，執行前已經有的改動不重算。"""
    changes, added = diff_tests(side, after, fp)
    if not prior:
        return changes, added
    pre = {_kind_key(c) for c in diff_tests(before, after, fp)[0]}
    had = extract_tests(before, fp)
    return [c for c in changes if c["key"] not in had or _kind_key(c) in pre], added


def _changes(state: Optional[Dict[str, Any]], sid: str, fp: str, before: str, after: str,
             side: Optional[str] = None, prior: bool = False) -> Tuple[List[Dict[str, str]], List[str]]:
    """(要看宣告的動作, 這次新加的測試)：本 session 自己新加的（old_test_added 或基線沒有）、宣告過的那支記 exempt 放過。
    side＝git 自己產出的內容（_git_after），給了就照 _against_side 比。"""
    import wg_release_rules as rr
    changes, added = diff_tests(before, after, fp) if side is None else _against_side(before, after, side, fp, prior)
    cp = rr.canon_path(fp)
    seen_added = set((state or {}).get("old_test_added") or [])
    seen_decl = set((state or {}).get("old_test_declared") or [])
    base = ((state or {}).get(BASELINE_KEY) or {}).get(cp)
    base = set(base) if base is not None else None
    live = []
    for c in changes:
        k = f"{cp}|{c['key']}"
        why = ("session_added" if k in seen_added else "declared_before" if k in seen_decl
               else "not_in_baseline" if base is not None and c["key"] not in base else "")
        if why:
            _log("exempt", sid, fp, test=c["key"], kind=c["kind"], why=why)
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
    if state is None:
        return False
    base = set((state.get(BASELINE_KEY) or {}).get(cp) or [])
    added = [a for a in added if a not in base]   # 基線就有的（被刪又還原的舊測試）不算新加，之後改它照要宣告
    if not (done or added):
        return False
    decl = set(state.get("old_test_declared") or [])
    decl.update(f"{cp}|{x}" for c in done for x in (c["key"], c.get("new_key")) if x)
    state["old_test_declared"] = sorted(decl)
    state["old_test_added"] = sorted(set(state.get("old_test_added") or []) | {f"{cp}|{a}" for a in added})
    return True


def _test_targets(tool_name: str, tool_input: Dict[str, Any], config: Dict[str, Any], cwd: str) -> List[str]:
    """這次工具呼叫寫到的測試檔。Bash／PowerShell 的寫入目標由 wg_core.write_paths_from_tool 解析（目標不明的 UNKNOWN 略過，
    由 UNKNOWN_TARGET_LOGGED 放行留帳）。"""
    if tool_name == "NotebookEdit":
        paths = [str(tool_input.get("notebook_path", "") or "")]
    elif tool_name in EDIT_TOOLS:
        paths = [str(tool_input.get("file_path", "") or "")]
    else:
        from wg_core import write_paths_from_tool
        paths = [p for p in (write_paths_from_tool(tool_name, tool_input, cwd) or []) if p and not p.startswith("UNKNOWN:")]
    # 認得的語言才往下（每次寫檔都會經過這裡，先用副檔名擋掉，不載入判式）
    return [p for p in paths if p.lower().endswith(_ALL_EXTS) and is_test_file(p, config, _root(p, cwd))]


def _path_parts(p: str) -> List[str]:
    return [c.lower() for c in re.split(r"[/\\]+", p) if c not in ("", ".")]


def heredoc_writes(command: str, targets: List[str]) -> Dict[str, str]:
    """Bash 指令裡 heredoc 寫進測試檔的改後內容 {寫入目標: 改後全文}。targets＝_test_targets 解析出的寫入目標
    （wg_core.write_paths_from_tool，與改資料檔閘同一支）；heredoc 寫的路徑以尾段對上恰好一個目標才算（cd 之後的相對路徑也對得上）。
    `>` 覆寫＝內容、`>>` 追加＝原檔＋內容，同一檔多段依序套。逐行掃：每段 heredoc 的內文先跳過（內文裡的 `cat > 檔` 字樣不是指令）；
    `<<-` 的結束行只去掉前導 tab（同 Bash）。算不準的不算：一行掛兩個以上 heredoc、沒加引號的 heredoc 內文有 `$`／反引號（會展開）。
    同一指令其他寫法（sed、python）的改動不在這裡，照舊由 after_tool 事後比。"""
    out: Dict[str, str] = {}
    lines = str(command or "").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        tags = [] if line.lstrip().startswith("#") else list(_HEREDOC_TAG_RE.finditer(line))
        bodies: List[Tuple[str, List[str]]] = []
        for tm in tags:
            dash, quote, tag = tm.group(1) == "-", tm.group(2), tm.group(3)
            body: List[str] = []
            while i < len(lines):
                raw = lines[i].rstrip("\r")
                i += 1
                if (raw.lstrip("\t") if dash else raw) == tag:
                    break
                body.append(raw.lstrip("\t") if dash else raw)
            bodies.append((quote, body))
        m = _CAT_HEREDOC_RE.search(line) if len(bodies) == 1 else None
        if not m:
            continue
        quote, body = bodies[0]
        text = "".join(f"{ln}\n" for ln in body)
        if not quote and re.search(r"[$`]", text):
            continue
        tail = _path_parts((m.group("p1") or m.group("p2")).strip("'\""))[-3:]
        hits = [t for t in targets if tail and _path_parts(t)[-len(tail):] == tail]
        if len(hits) != 1:
            continue
        op = m.group("op1") or m.group("op2")
        out[hits[0]] = text if op == ">" else out.get(hits[0], _read(hits[0]) or "") + text
    return out


def _snap_file(sid: str, tool_name: str, tool_input: Dict[str, Any]) -> Path:
    """改前快照的檔：PreToolUse 與 PostToolUse 拿到的 tool_input 相同，用它的雜湊對上同一次呼叫。"""
    import wg_core
    key = hashlib.sha1(json.dumps([tool_name, tool_input], sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
    return Path(wg_core.WORKFLOW_DIR) / "old-test-snap" / f"{sid or 'nosid'}-{key.hexdigest()[:16]}.json"


def _git(root: str, *args: str, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", root, *args], capture_output=True, timeout=10, env=env,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _git_status(root: str, config: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
    """(HEAD 的 commit（還沒有 commit 是 "(initial)"）, {有改動（含未追蹤、刪除、衝突）的測試檔絕對路徑: 種類})。
    種類是 porcelain v2 的開頭字（_V2_FIELDS）。查不到丟例外。"""
    r = _git(root, "status", "--porcelain=v2", "-z", "--branch", "--untracked-files=all")
    if r.returncode:
        raise RuntimeError(f"git status 失敗：{r.stderr.decode('utf-8', 'replace').strip()[:200]}")
    entries = r.stdout.decode("utf-8", "replace").split("\0")
    head, out, i = "", {}, 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if e.startswith("# branch.oid "):
            head = e[len("# branch.oid "):]
            continue
        kind = e[:1]
        if kind not in _V2_FIELDS:
            continue
        if kind == "2":
            i += 1   # -z 的改名／複製後面多一筆原路徑
        p = str(Path(root) / e.split(" ", _V2_FIELDS[kind])[-1])
        if p.lower().endswith(_ALL_EXTS) and is_test_file(p, config, root):
            out[p] = kind
    return head, out


def _gitdir(root: str) -> Path:
    """git 目錄：worktree 的 .git 是檔、指向 gitdir。讀不到丟例外。"""
    dot = Path(root) / ".git"
    gd = dot if dot.is_dir() else Path(dot.read_text(encoding="utf-8", errors="replace").split("gitdir:", 1)[-1].strip())
    return gd if gd.is_absolute() else Path(root) / gd


def _git_marks(root: str) -> Dict[str, Any]:
    """執行前後要比的 git 目錄事實：ops＝進行中合併類操作的標記 {名稱: 內容雜湊}（目錄記空字串；同一種操作往下一步時內容會變）；
    reflog＝logs/HEAD 的位元組數（之後新增的就是這條指令讓 HEAD 動的紀錄；沒有這個檔記 -1）。讀不到丟例外。"""
    gd = _gitdir(root)
    ops: Dict[str, str] = {}
    for n in GIT_OP_MARKS:
        p = gd / n
        if p.is_dir():
            ops[n] = ""
        elif p.is_file():
            ops[n] = hashlib.sha1(p.read_bytes()).hexdigest()
    log = gd / "logs" / "HEAD"
    return {"ops": ops, "reflog": log.stat().st_size if log.is_file() else -1}


def _git_text(root: str, rev: str, path: str) -> str:
    """rev（commit、tree 或 HEAD）裡這個檔的內容；rev 裡沒有這個檔回空字串。"""
    r = _git(root, "show", f"{rev}:{Path(path).relative_to(root).as_posix()}")
    return r.stdout.decode("utf-8", "replace").replace("\r\n", "\n") if r.returncode == 0 else ""


def _under(root: str, path: str) -> bool:
    try:
        Path(path).relative_to(root)
        return True
    except ValueError:
        return False


def _op_tree(root: str, gd: Path) -> Tuple[str, str]:
    """(git 合出來的 tree, 判不出的原因)：合併類操作停在半路時，用 git merge-tree 從 commit 重算 git 自己的產出——不讀暫存區
    與工作樹，同一支腳本之後再寫、再 add 的都不會混進來。MERGE_HEAD（只合一個）→ HEAD 與它；CHERRY_PICK_HEAD／REBASE_HEAD X
    → 以 X^ 為共同祖先合 HEAD 與 X（X 是合併提交時主線不明 → 判不出）；SQUASH_MSG → HEAD 與訊息裡第一個 commit。
    界線：merge 時另給的策略或選項（-s、-X）從 commit 看不出來，重算結果不同的那幾處會照算本 session 改的（寧可多擋）。"""
    def shas(name: str, prefix: str = "") -> List[str]:
        p = gd / name
        text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
        return re.findall(rf"^{prefix}([0-9a-f]{{40,64}})\b", text, re.MULTILINE)
    merge, pick, squash = shas("MERGE_HEAD"), shas("CHERRY_PICK_HEAD") or shas("REBASE_HEAD"), shas("SQUASH_MSG", "commit ")
    if len(merge) > 1:
        return "", "MERGE_HEAD 有多個分支（octopus），merge-tree 重算不了"
    if merge:
        args = ["HEAD", merge[0]]
    elif pick:
        r = _git(root, "rev-list", "--parents", "-n", "1", pick[0])
        if len(r.stdout.decode("utf-8", "replace").split()) != 2:
            return "", "cherry-pick／rebase 套的是合併提交（主線不明）或查不到父代，merge-tree 重算不了"
        args = [f"--merge-base={pick[0]}^", "HEAD", pick[0]]
    elif squash:
        args = ["HEAD", squash[0]]
    else:
        return "", "合併類操作停下來了，但沒有可重算的 commit"
    r = _git(root, "merge-tree", "--write-tree", *args)
    tree = r.stdout.decode("utf-8", "replace").split("\n", 1)[0].strip()
    if r.returncode > 1 or not _SHA_RE.match(tree):
        return "", f"git merge-tree 失敗：{r.stderr.decode('utf-8', 'replace').strip()[:200]}"
    return tree, ""


def _diff_paths(root: str, old: str, new: str) -> List[str]:
    """commit old 到 new 之間有變的檔（絕對路徑）。查不到丟例外。"""
    r = _git(root, "diff", "--name-only", "-z", old, new)
    if r.returncode:
        raise RuntimeError(f"git diff 失敗：{r.stderr.decode('utf-8', 'replace').strip()[:200]}")
    return [str(Path(root) / rel) for rel in filter(None, r.stdout.decode("utf-8", "replace").split("\0"))]


def _head_moves(gd: Path, offset: int) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]], str]:
    """(這條指令期間 HEAD 被別人的內容移動的幾筆, 自己 commit 讓 HEAD 動的幾筆, 判不出的原因)，每筆是 (移動前, 移動後)：
    logs/HEAD 從 offset 起新增的紀錄，說明不是 _OWN_MOVES 開頭的（merge、pull、rebase、checkout、reset、cherry-pick）算別人的；
    自己 commit、amend、revert 算自己的；合併提交（commit (merge)：merge --no-commit 或解完衝突再 commit）兩邊都不算，
    它的內容大半來自別的分支、分不出哪幾處是自己改的。執行前沒有 reflog、檔被截短 → 判不出。"""
    log = gd / "logs" / "HEAD"
    data = log.read_bytes() if offset >= 0 and log.is_file() else b""
    if offset < 0 or len(data) < offset:
        return [], [], "HEAD 動了但讀不到這段期間的 reflog（logs/HEAD）"
    foreign, own = [], []
    for line in data[offset:].decode("utf-8", "replace").splitlines():
        head, _, msg = line.partition("\t")
        parts = head.split(" ")
        if len(parts) < 2 or not (_SHA_RE.match(parts[0]) and _SHA_RE.match(parts[1])):
            continue
        if not msg.startswith(_OWN_MOVES):
            foreign.append((parts[0], parts[1]))
        elif not msg.startswith("commit (merge)"):
            own.append((parts[0], parts[1]))
    return foreign, own, ""


def _own_commit_tests(root: str, py: Dict[str, Any], old: str, head: str, config: Dict[str, Any]) -> List[str]:
    """這條指令自己 commit 掉的測試檔（OWN_COMMIT_CHANGES_STILL_COMPARED）：_head_moves 的每筆自己移動前後之間有變的；
    讀不到 reflog 分不出誰動的 → 執行前到現在整段都算（寧可多比）。只看自己那幾筆：merge、pull 帶進來的大批檔不逐一取內容。
    查不到丟例外。"""
    _, own, why = _head_moves(_gitdir(root), int(py.get("reflog", -1)))
    out: List[str] = []
    for o, n in ([(old, head)] if why else own):
        out += [p for p in _diff_paths(root, o, n)
                if p not in out and p.lower().endswith(_ALL_EXTS) and is_test_file(p, config, root)]
    return out


def _git_after(root: str, py: Dict[str, Any], head: str, pairs: Dict[str, Optional[str]],
               known: set) -> Tuple[Dict[str, str], set, Dict[str, set], Dict[str, Any]]:
    """這條指令裡 git 自己做了什麼。回 (side, prior, brought, note)：
    side＝{要比對的測試檔: git 自己產出的內容}：合併類操作停在半路（標記新出現或內容變了）→ _op_tree 重算的結果；否則 HEAD 被
    別人的內容移動（_head_moves）→ 最後一筆外來移動的終點（之後自己 commit 的不算 git 產出）。prior＝side 裡執行前就有本 session
    沒 commit 改動的檔（改前內容不等於執行前的 HEAD）。brought＝{測試檔: git 帶進來的測試名}：side 比改前多出來的，加上每筆外來
    移動前後之間有變、已記基線（known）的檔移動後多出來的；HEAD 動了卻讀不到 reflog（分不出誰動的）→ 執行前到現在整段照外來算
    （併基線寧可多擋）。note＝留帳（ops、moves、判不出的原因）；判不出就不給 side：照舊拿執行前的內容比，寧可多擋不漏擋。查不到丟例外。"""
    import wg_release_rules as rr
    gd = _gitdir(root)
    old = str(py.get("head", head))
    before_ops = py.get("ops") or {}
    started = sorted(n for n, h in _git_marks(root)["ops"].items() if before_ops.get(n) != h)
    moves, _, why = _head_moves(gd, int(py.get("reflog", -1))) if head != old else ([], [], "")
    rev = ""
    if started:
        rev, op_why = _op_tree(root, gd)
        why = "；".join(x for x in (why, op_why) if x)
    elif moves:
        rev = moves[-1][1]
    side = {p: _git_text(root, rev, p) for p in pairs if _under(root, p)} if rev else {}
    old_text = (lambda p: _git_text(root, old, p)) if _SHA_RE.match(old) else (lambda p: "")
    prior = {p for p in side if (pairs[p] or "") != old_text(p)}
    brought: Dict[str, set] = {}
    for p, src in side.items():
        more = set(extract_tests(src, p)) - set(extract_tests(pairs[p] or "", p))
        if more:
            brought[p] = more
    if not moves and why and head != old and _SHA_RE.match(old) and _SHA_RE.match(head):
        moves = [(old, head)]
    for o, n in moves:
        for p in _diff_paths(root, o, n):
            if rr.canon_path(p) in known:
                more = set(extract_tests(_git_text(root, n, p), p)) - set(extract_tests(_git_text(root, o, p), p))
                brought.setdefault(p, set()).update(more)
    return side, prior, {p: s for p, s in brought.items() if s}, {"ops": started, "moves": len(moves), "why": why}


def absorb_git_tests(state: Optional[Dict[str, Any]], brought: Dict[str, Iterable[str]]) -> bool:
    """git 帶進來的測試是舊測試：{測試檔: 測試名} 併進已記過基線的那幾個檔（基線沒有的測試＝本 session 新加的，不併的話
    別的分支帶進來的新測試會被放過）。就地改 state，回有沒有改。"""
    import wg_release_rules as rr
    base = (state or {}).get(BASELINE_KEY) or {}
    changed = False
    for p, names in brought.items():
        cp = rr.canon_path(p)
        more = set(names) - set(base.get(cp) or []) if cp in base else set()
        if more:
            base[cp] = sorted(set(base[cp]) | more)
            changed = True
    return changed


def _py_baseline(tool_input: Dict[str, Any], config: Dict[str, Any], cwd: str, sid: str) -> Optional[Dict[str, Any]]:
    """指令會執行 python（腳本自己開檔寫的目標解析不到）：記下 HEAD、進行中的合併類操作、repo 裡這時已經有改動的測試檔與內容。
    不是 git repo 回 None；git 查不到只能 stderr＋留帳（不擋所有 python 指令）。"""
    if not _PY_RUN_RE.search(str(tool_input.get("command", "") or "")):
        return None
    from wg_core import find_vcs_root
    hit = find_vcs_root(Path(cwd or "."))
    if not hit or hit[0] != "git":
        return None
    root = str(hit[1])
    try:
        head, dirty = _git_status(root, config)
        return {"root": root, "head": head, **_git_marks(root), "dirty": {p: _read(p) for p in dirty}}
    except Exception as e:
        print(f"[Guardian:OldTestDeclare] 執行 python 前查不到 git 狀態（這次 python 改測試檔沒核對到）：{e}", file=sys.stderr)
        _log("py_baseline_error", sid, root, error=f"{type(e).__name__}: {e}")
        return None


def snapshot(tool_name: str, tool_input: Dict[str, Any], input_data: Dict[str, Any], config: Dict[str, Any], cwd: str,
             state: Optional[Dict[str, Any]]) -> None:
    """PreToolUse（Bash／PowerShell／NotebookEdit）：寫入目標裡的測試檔拍改前快照（檔還不存在記 None；讀不到讓例外往上丟＝判不了）；
    指令會執行 python 再加記 repo 裡已經有改動的測試檔（_py_baseline）。快照到的檔順便記基線（remember_baseline，記進 gate 拿到的
    那份 state）：這一步在 PreToolUse，指令之後失敗、PostToolUse 沒跑也記得到。"""
    sid = input_data.get("session_id", "") or ""
    files = {p: _read(p) for p in _test_targets(tool_name, tool_input, config, cwd)}
    py = _py_baseline(tool_input, config, cwd, sid) if tool_name in ("Bash", "PowerShell") else None
    if not files and py is None:
        return
    f = _snap_file(sid, tool_name, tool_input)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"files": files, "py": py}, ensure_ascii=False), encoding="utf-8", newline="\n")
    if sid and remember_baseline(state, {**((py or {}).get("dirty") or {}), **files}):
        from wg_core import write_state
        write_state(sid, state)


def _snap_pairs(snap: Dict[str, Any], config: Dict[str, Any], sid: str,
                known: set) -> Tuple[Dict[str, Optional[str]], Dict[str, str], set, Dict[str, set]]:
    """(要比對的 {測試檔: 改前內容}, git 產出的 {測試檔: 內容}, 執行前就有改動的檔, git 帶進來的 {測試檔: 測試名})。要比對的＝
    寫入目標的快照，加上執行 python 後才出現改動的測試檔：執行前就有改動的取當時記下的內容，執行前乾淨的取執行前的 HEAD。
    HEAD 前後不同時再加這條指令自己 commit 掉的測試檔（_own_commit_tests：同指令改了又 commit，工作樹乾淨也要比；
    同一段期間 merge 帶進來的仍由 _git_after 的 side 認出，不算自己改的）。
    後三項見 _git_after（known＝已記過基線的檔）；查不到 git 只 stderr＋留帳，照舊比。"""
    pairs = dict(snap.get("files") or {})
    py = snap.get("py")
    if not py:
        return pairs, {}, set(), {}
    root = py["root"]
    try:
        head, now = _git_status(root, config)
    except Exception as e:
        print(f"[Guardian:OldTestDeclare] 執行 python 後查不到 git 狀態（這次 python 改測試檔沒核對到）：{e}", file=sys.stderr)
        _log("py_after_error", sid, root, error=f"{type(e).__name__}: {e}")
        return pairs, {}, set(), {}
    old = str(py.get("head", head))
    dirty = py.get("dirty") or {}
    cands = list(now)
    if head != old and _SHA_RE.match(old) and _SHA_RE.match(head):
        try:
            cands += [p for p in _own_commit_tests(root, py, old, head, config) if p not in now]
        except Exception as e:
            print(f"[Guardian:OldTestDeclare] 查不到這條指令期間 HEAD 前後的差異（同指令 commit 掉的測試改動沒核對到）：{e}",
                  file=sys.stderr)
            _log("own_commit_diff_error", sid, root, error=f"{type(e).__name__}: {e}")
    for p in cands:
        if p not in pairs:
            pairs[p] = dirty[p] if p in dirty else (_git_text(root, old, p) if _SHA_RE.match(old) else "")
    try:
        side, prior, brought, note = _git_after(root, py, head, pairs, known)
    except Exception as e:
        print(f"[Guardian:OldTestDeclare] 查不到 git 這次做了什麼（照執行前的內容比，可能多擋）：{e}", file=sys.stderr)
        _log("git_op_error", sid, root, error=f"{type(e).__name__}: {e}")
        return pairs, {}, set(), {}
    if note["why"]:
        print(f"[Guardian:OldTestDeclare] {note['why']}：照執行前的內容比，可能多擋", file=sys.stderr)
    if side or brought or note["why"]:
        _log("git_op", sid, root, head=[old, head], files=sorted(set(side) | set(brought)), **note)
    return pairs, side, prior, brought


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
        pairs, side, prior, brought = _snap_pairs(snap, config, sid, set(state.get(BASELINE_KEY) or {}))
        changed = absorb_git_tests(state, brought)
        old_head = str((snap.get("py") or {}).get("head") or "")
        rev = old_head if _SHA_RE.match(old_head) else "HEAD"   # 執行前的 HEAD：同指令 commit 掉的新測試不併進基線
        for path, before in pairs.items():
            touched.add(rr.canon_path(path))
            changed = remember_baseline(state, {path: before}, rev) or changed   # python 腳本改的檔事前不知道是哪個，這裡補記
            changed = absorb_git_tests(state, {path: brought.get(path, ())}) or changed   # 剛記的基線也要有帶進來的
            live, added = _changes(state, sid, path, before or "", _read(path) or "", side.get(path), path in prior)
            if live and text is None:
                text = _decl_text(input_data)
            decls = rr.parse_old_test_declarations(text) if live else []
            old_t = extract_tests(side.get(path, before) or "", path) if live else {}
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


def _capped(state: Optional[Dict[str, Any]], sid: str, tool_name: str,
            owed: List[Tuple[str, Dict[str, Any]]]) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """擋次上限（wg_core.deny_cap）：沒宣告的 [(檔, 動作)] → ({檔: 這次照擋的動作}, 這次起放行的動作)。缺件＝檔＋測試＋動作種類；
    同一個使用者回合同一件擋滿兩次就放行、留帳 cap_released。state 就地改（計次），寫檔由呼叫端。"""
    import wg_release_rules as rr
    from wg_core import deny_cap
    keys = {f"{rr.canon_path(fp)}|{c['key']}|{c['kind']}": (fp, c) for fp, c in owed}
    denied, released = deny_cap(state, GUARD, list(keys))
    for k in released:
        fp, c = keys[k]
        _log("cap_released", sid, fp, tool=tool_name, test=c["key"], kind=c["kind"])
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for k in denied:
        fp, c = keys[k]
        by_file.setdefault(fp, []).append(c)
    return by_file, [keys[k][1] for k in released]


def _pending_deny(tool_name: str, tool_input: Dict[str, Any], input_data: Dict[str, Any], cwd: str,
                  state: Optional[Dict[str, Any]]) -> Optional[str]:
    """上一個 Bash／PowerShell／NotebookEdit 動了既有測試沒宣告：這次（任何工具）先找宣告，補了的清掉、留帳 declared_late；
    還欠著就擋，除非這次只讀或只寫那幾個檔（撤回）；同一件擋滿兩次放行（_capped），放行的那筆從欠帳拿掉、留帳 cap_released。"""
    sid = input_data.get("session_id", "") or ""
    if not sid:
        return None
    from wg_core import write_state
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
    by_file, released = _capped(state, sid, tool_name, [(e["file"], e) for e in left])
    if released:
        state[PENDING_KEY] = [e for e in left if not any(e is r for r in released)]
    write_state(sid, state)
    if not by_file:
        return None
    left = [e for es in by_file.values() for e in es]
    _log("denied_late", sid, left[0]["file"], tool=tool_name, pending=[{k: e[k] for k in ("file", "key", "kind")} for e in left])
    tools = "／".join(sorted({e.get("tool", "") for e in left}))
    return ("\n".join(rr.format_hit("ot", rr.old_test_change_verdict(fp, es, decls)) for fp, es in by_file.items())
            + f"\n這是 {tools} 改的（已經寫進檔），請補宣告再繼續；要撤回就只讀、只改這幾個檔。\n" + hint(left[0]["key"]))


def _heredoc_deny(tool_input: Dict[str, Any], input_data: Dict[str, Any], config: Dict[str, Any], cwd: str,
                  state: Optional[Dict[str, Any]]) -> Optional[str]:
    """Bash 用 heredoc 寫測試檔（heredoc_writes 算得出改後內容）→ 寫之前與 Edit／Write 同款判：動到既有測試又找不到宣告就擋
    （擋次上限同 _capped）；宣告對上的照 Edit 留帳。算不出改後內容的寫法回 None，交給快照＋after_tool 事後比。"""
    targets = _test_targets("Bash", tool_input, config, cwd)
    writes = heredoc_writes(str(tool_input.get("command", "") or ""), targets) if targets else {}
    if not writes:
        return None
    import wg_release_rules as rr
    from wg_core import write_state
    sid = input_data.get("session_id", "") or ""
    owing = {(rr.canon_path(e["file"]), e["key"]) for e in (state or {}).get(PENDING_KEY) or []}
    decls: Optional[List[Dict[str, Any]]] = None
    files: List[Tuple[str, List[Dict[str, str]], List[str]]] = []
    dirty = False
    for fp, after in writes.items():
        before = _read(fp)
        dirty = remember_baseline(state, {fp: before}) or dirty
        live, added = _changes(state, sid, fp, before or "", after)
        live = [c for c in live if (rr.canon_path(fp), c["key"]) not in owing]
        if live and decls is None:
            decls = rr.parse_old_test_declarations(_decl_text(input_data))
        files.append((fp, live, added))
    owed = [(fp, c) for fp, live, _ in files for c in live if rr.old_test_declaration_for(c, decls or [], fp) is None]
    by_file, _released = _capped(state, sid, "Bash", owed)
    dirty = dirty or bool(owed)
    if not by_file:   # 整條指令會執行才記宣告與新加的測試；有一個檔被擋就整條不跑，其他檔也不先記
        for fp, live, added in files:
            dirty = _record(state, sid, fp, [c for c in live if (fp, c) not in owed], added, decls or []) or dirty
    if dirty and state is not None and sid:
        write_state(sid, state)
    if not by_file:
        return None
    for fp, cs in by_file.items():
        _log("denied", sid, fp, tool="Bash", via="heredoc", changes=cs)
    hits = [rr.format_hit("ot", rr.old_test_change_verdict(fp, cs, decls or [])) for fp, cs in by_file.items()]
    return "\n".join(hits) + "\n這是 Bash heredoc 要寫進去的內容（寫之前就比對，還沒寫進檔）。\n" + hint(next(iter(by_file.values()))[0]["key"])


_READ = object()   # gate 沒拿到 state：自己讀一份（單獨呼叫時）


def gate(tool_name: str, tool_input: Dict[str, Any], input_data: Dict[str, Any], config: Dict[str, Any],
         cwd: str, state: Any = _READ) -> Optional[str]:
    """PreToolUse：①上一個 Bash 類呼叫還欠宣告 → 擋（任何工具）；②Bash／PowerShell／NotebookEdit → 拍快照放行，事後由 after_tool 比；
    ③Edit／MultiEdit／Write 動到既有測試又找不到宣告行 → 擋。宣告過與本 session 自己新加的測試記 state，之後不再擋。
    同一件缺宣告同一個使用者回合擋滿兩次就放行留帳（_capped）。state＝PreToolUse 已讀的那一份（None＝沒有 state 檔），
    就地改、本閘有改就寫回；沒給才自己讀。"""
    if not _cfg(config).get("enabled", True):
        return None
    sid = input_data.get("session_id", "") or ""
    if state is _READ:
        from wg_core import read_state
        state = read_state(sid) if sid else None
    late = _pending_deny(tool_name, tool_input, input_data, cwd, state)
    if late:
        return late
    if tool_name in AFTER_TOOLS:
        pre = _heredoc_deny(tool_input, input_data, config, cwd, state) if tool_name == "Bash" else None
        if pre:
            return pre
        snapshot(tool_name, tool_input, input_data, config, cwd, state)
        return None
    if tool_name not in EDIT_TOOLS or not _test_targets(tool_name, tool_input, config, cwd):
        return None
    fp = str(tool_input.get("file_path", "") or "")
    ba = before_after(tool_name, tool_input)
    if ba is None:
        return None
    import wg_release_rules as rr
    from wg_core import write_state
    based = remember_baseline(state, {fp: ba[0]})
    live, added = _changes(state, sid, fp, ba[0], ba[1])
    # 已經欠著宣告的那幾支（上一個 Bash 改的）這次再動不另算：多半是撤回，撤回成不成由 after_tool 判、清帳
    owing = {(rr.canon_path(e["file"]), e["key"]) for e in (state or {}).get(PENDING_KEY) or []}
    live = [c for c in live if (rr.canon_path(fp), c["key"]) not in owing]
    decls = rr.parse_old_test_declarations(_decl_text(input_data)) if live else []
    owed = [c for c in live if rr.old_test_declaration_for(c, decls, fp) is None]
    by_file, _released = _capped(state, sid, tool_name, [(fp, c) for c in owed])
    dirty = based or bool(owed)
    if by_file:
        if dirty and state is not None and sid:
            write_state(sid, state)
        _log("denied", sid, fp, tool=tool_name, changes=by_file[fp])
        return rr.format_hit("ot", rr.old_test_change_verdict(fp, by_file[fp], decls)) + "\n" + hint(by_file[fp][0]["key"])
    if (_record(state, sid, fp, [c for c in live if c not in owed], added, decls) or dirty) and state is not None and sid:
        write_state(sid, state)
    return None
