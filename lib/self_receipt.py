"""self_receipt.py：長跑的驗證程式（run_verify.py）自己寫的驗證收據；寫與讀在同一處定格式。

做什麼：CC 單次工具呼叫上限 10 分鐘，全量 run_verify 要跑 18～25 分鐘只能背景跑，PostToolUse 只看得到「已啟動」、
  看不到結尾的量尺哨兵 → session 帳本永遠沒有這把尺的 DONE。所以 run_verify 印完哨兵後自己寫一份收據到
  <CLAUDE_DIR>/workflow/verify-ledger/_runs/<UTC 時間戳>-<pid>.json，MeasureGate 再讀它（hooks/wg_verify_ledger）。
  這個目錄由 PreToolUse 禁止手寫（hooks/handlers/pre_tool_use.check_verify_ledger_write）。
怎麼跑：run_verify.py 呼叫 write_self_receipt；hooks 呼叫 load_self_receipts、cmd_matches、is_whole_run、unsupported_syntax。
  verify 在 lib/verify/verify_self_receipt.py、hooks/verify/verify_stop_reconcile.py（自寫收據段）。
指令解析只有一套（split_shell → parse_cmds）：量尺閘、自寫收據比對、對帳閘的「整體驗證」與「提到改檔」都經過它。
  只認白名單語法；白名單外的語法整條指令不算證據（fail-closed），不逐一追 shell 技巧。
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, NamedTuple, Optional, TextIO, Tuple, Union

RUNS_REL = Path("workflow") / "verify-ledger" / "_runs"
SOURCE = "run_verify_self"
LOAD_LIMIT = 50


def utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


# ─── 指令解析與比對（量尺閘、自寫收據、對帳閘共用這一套） ─────────────────────────────
_PY_HEAD_RE = re.compile(r"^python(?:\d+(?:\.\d+)*)?w?$", re.IGNORECASE)   # py 啟動器（py -3）不算：照表上字串跑
_PY_OPT_ARG = ("-X", "-W")                       # 帶一個參數的直譯器選項（`-X utf8` 與 `-Xutf8` 同義）
_PY_OPT_PAIR_RE = re.compile(r"^-[XW] \S+$")
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_FD_RE = re.compile(r"^(?:\d|\*)$")
_SHELL_SPECIAL_RE = re.compile(r"[\s;&|<>()'\"#`$]")
_ESCAPED_RE = re.compile(r"[\s;&|<>()'\"#`${}*?\[\]!~]")    # 反斜線後接這些＝shell 跳脫（白名單外）
_FILTER_PROGS = frozenset({"tail", "head", "select-object", "select"})   # 尾端只准接這幾支：只會刪行，造不出成功行
_FILTER_ARG_RE = re.compile(r"^(?:[+-]?\d+|--?[A-Za-z][A-Za-z-]*=?\d*)$")  # 尾端過濾只准選項與數字（不帶檔名）
_ECHO_PROGS = frozenset({"echo", "printf", "write-output", "write-host", "write", "out-host"})   # 只會印字的指令
_CD_PROGS = frozenset({"cd", "pushd", "set-location", "sl", "chdir", "push-location"})
_CTRL_WORDS = frozenset({"if", "then", "elif", "else", "fi", "for", "foreach", "while", "until", "do", "done",
                         "function", "switch", "case", "esac", "try", "catch", "finally", "trap", "!"})
_EVAL_PROGS = frozenset({"iex", "invoke-expression", "eval", "source", ".", "start-process", "saps", "start"})
_PS_SHELLS = frozenset({"pwsh", "powershell"})
_POSIX_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
_INLINE_FLAG_RE = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")        # bash -c／-lc：把字串當指令跑
_PS_INLINE_RE = re.compile(r"^-(?:c|e$|ec$|en|cwa$)", re.IGNORECASE)   # pwsh -Command／-EncodedCommand（含縮寫）
_SETUP_ARG_RE = re.compile(r"^(?:[A-Za-z_]\w*(?:=.*)?|[-+][A-Za-z]+)$", re.DOTALL)
_PS_VAR_RE = re.compile(r"^\$[A-Za-z_][\w:]*$")
_PS_ASSIGN_RE = re.compile(r"^\$[A-Za-z_][\w:]*=")
_ABS_DIR_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/[A-Za-z](?:/|$))")
_WHOLE_PY_OPTS = frozenset({"-X utf8", "-u", "-B"})              # 整體驗證准帶的直譯器選項（不改變跑什麼）
_PYTEST_WHOLE_OPT_RE = re.compile(r"^(?:-[qvsx]+|-p|-r\w+|--tb=\w+|--color=\w+|--no-header|--disable-warnings"
                                  r"|--strict-markers)$")        # 整體驗證准帶的 pytest 選項（白名單；沒列的都不算）

Argv = Union[str, List[str]]
Cmd = Tuple[str, FrozenSet[str], FrozenSet[str], Tuple[str, ...]]      # (程式, python 直譯器選項, 其他選項, 位置參數)
Chunk = Tuple[Optional[str], List[str], bool]                           # (接在前一個指令後的運算子, 原字, 有 < 輸入重導向)


class Step(NamedTuple):
    """指令鏈裡的一個指令。"""
    op: Optional[str]           # 接在前一個指令後的運算子：&& || | ;（換行算 ;）；第一個是 None
    cmd: Cmd                    # 正規化後的指令
    words: Tuple[str, ...]      # 原字（bash 已去開頭的 X=1）
    stdin: bool                 # 有 < 輸入重導向（尾端過濾改讀檔）


class _Unsupported(Exception):
    """白名單外的語法；訊息＝是哪一種（擋訊息直接引用）。"""


def _prog(word: str) -> str:
    """程式名：取檔名、小寫、去 .exe（`.` 就是 `.`）。"""
    head = (Path(str(word).replace("\\", "/")).name or str(word)).lower()
    return head[:-4] if head.endswith(".exe") else head


def _strip_env(words: List[str]) -> List[str]:
    """去掉開頭的 bash 環境指定 `X=1`（PowerShell 沒有這種寫法，不去）。"""
    i = 0
    while i < len(words) and _ENV_ASSIGN_RE.match(words[i]):
        i += 1
    return words[i:]


def _scan(s: str, ps: bool) -> List[Chunk]:
    """白名單斷詞；碰到白名單外的語法拋 _Unsupported。白名單見 split_shell。"""
    out: List[Chunk] = []
    words: List[str] = []
    cur: List[str] = []
    has = skip = stdin = False
    op: Optional[str] = None
    cont = "`" if ps else "\\"                                   # 行尾續行字元

    def end_word() -> None:
        nonlocal has, skip
        if has and skip:
            skip = False                                          # 重導向目標，丟掉
        elif has:
            words.append("".join(cur))
        cur.clear()
        has = False

    def end_cmd(nxt: str) -> None:
        nonlocal op, skip, stdin
        end_word()
        skip = False
        if words:
            out.append((op, list(words), stdin))
            words.clear()
            op = nxt
        elif nxt != ";":
            op = nxt
        stdin = False

    def string_start() -> None:
        if ps and not has and not words:
            raise _Unsupported("PowerShell 以引號開頭的指令（字串運算式，不是執行的指令）")

    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r":
            end_word()
            i += 1
        elif c == cont and s.startswith(("\n", "\r\n"), i + 1):    # 續行（LF／CRLF）
            i += 2 if s[i + 1] == "\n" else 3
        elif c == "#" and not has:
            j = s.find("\n", i)
            i = n if j < 0 else j
        elif c == "'":
            string_start()
            j = s.find("'", i + 1)
            if j < 0:
                raise _Unsupported("引號沒閉合")
            cur.append(s[i + 1:j])
            has, i = True, j + 1
        elif c == '"':
            string_start()
            j = i + 1
            while j < n and s[j] != '"':
                if s[j] == "`":
                    raise _Unsupported("反引號")
                if s.startswith("$(", j):
                    raise _Unsupported("命令替換 $( )")
                if s.startswith('\\"', j):
                    raise _Unsupported('雙引號裡的跳脫 \\"')
                j += 1
            if j >= n:
                raise _Unsupported("引號沒閉合")
            cur.append(s[i + 1:j])
            has, i = True, j + 1
        elif c == "\\":
            if s.startswith("\\\\", i):                          # `\\`：bash 是一個反斜線，PowerShell 照留
                cur.append("\\" if not ps else "\\\\")
                has, i = True, i + 2
            elif i + 1 < n and _ESCAPED_RE.match(s[i + 1]):
                raise _Unsupported("反斜線跳脫（含空白或 shell 符號的參數請改用引號）")
            else:                                                 # Windows 路徑的 \x 照留
                cur.append(c)
                has, i = True, i + 1
        elif c == "$" and s[i + 1:i + 2] in ("(", "'", '"'):
            raise _Unsupported("命令替換 $( )" if s[i + 1] == "(" else "$'…' 引號")
        elif c == "@" and s[i + 1:i + 2] in ("'", '"'):
            raise _Unsupported("PowerShell here-string @'…'@")
        elif c == "`":
            raise _Unsupported("反引號")
        elif c in "()":
            raise _Unsupported("子 shell ( )")
        elif c in "{}":
            raise _Unsupported("script block／大括號 { }")
        elif s.startswith("<<", i):
            raise _Unsupported("heredoc／here-string（<<、<<<）")
        elif s.startswith("<#", i):
            raise _Unsupported("PowerShell 區塊註解 <# #>")
        elif s.startswith(("&&", "||"), i):
            end_cmd(s[i:i + 2])
            i += 2
        elif c in "<>" or s.startswith("&>", i):
            if has and _FD_RE.match("".join(cur)):              # 2>、*> 的 fd 屬於重導向
                cur.clear()
                has = False
            else:
                end_word()
            stdin = stdin or c == "<"
            i += 1 if c == "&" else 0
            while i < n and s[i] in "<>":
                i += 1
            if s[i:i + 1] == "|":
                raise _Unsupported("重導向 >|")
            if s[i:i + 1] == "&":                                # 2>&1：沒有目標檔；`>& 檔名` 的目標是下一個字
                j = i + 1
                while j < n and (s[j].isdigit() or s[j] == "-"):
                    j += 1
                skip, i = j == i + 1, j
            else:
                skip = True                                       # 下一個字是重導向目標，丟掉
        elif c == "&":
            raise _Unsupported("單獨的 &（背景執行／PowerShell 呼叫運算子）")
        elif c in "|;\n":
            end_cmd("|" if c == "|" else ";")
            i += 1
        else:
            cur.append(c)
            has, i = True, i + 1
    end_cmd(";")
    for _, ws, _ in out:                                          # 指令層：控制結構、把字串當指令跑、另起一層 shell
        w = ws if ps else _strip_env(ws)
        if not w:
            continue
        head = _prog(w[0])
        if head in _CTRL_WORDS:
            raise _Unsupported(f"控制結構 {w[0]}")
        if head in _EVAL_PROGS:
            raise _Unsupported(f"{w[0]}（把字串或腳本當指令執行）")
        if (head == "cmd" or (head in _POSIX_SHELLS and any(_INLINE_FLAG_RE.match(t) for t in w[1:]))
                or (head in _PS_SHELLS and (not any(t.lower() in ("-file", "-f") for t in w[1:])
                                            or any(_PS_INLINE_RE.match(t) for t in w[1:])))):
            raise _Unsupported(f"另起一層 shell 跑字串指令（{w[0]}）")    # 跑腳本檔（bash x.sh、pwsh -File x.ps1）照算
    return out


def split_shell(s: str, shell: str = "bash") -> Tuple[List[Chunk], Optional[str]]:
    """白名單語法的斷詞 → ([(運算子, 原字, 有沒有 < 輸入), …], None)；白名單外 → ([], 是哪一種)。
    白名單：單一指令與 && || | ; 換行串起的指令鏈；'…'、"…"；重導向 > >> 2>&1 *> &> < > $null（連同目標丟掉）；
    字首 # 註解；行首環境指定（bash `X=1 cmd`、PowerShell `$env:X="1";`）；續行（bash 反斜線、PowerShell 反引號，LF／CRLF）。
    其餘一律不支援：引號沒閉合、here-string、heredoc、$( )、反引號、( )、{ }、單獨的 &、反斜線跳脫、<# #>、
    if／for／function 等控制結構、iex／eval／source／.／Start-Process、bash -c、pwsh -Command（pwsh 只准 -File）、cmd。
    shell="powershell"：以引號開頭的指令是字串運算式（只是輸出那串字）→ 不支援。"""
    try:
        return _scan(str(s or ""), shell == "powershell"), None
    except _Unsupported as e:
        return [], str(e)


def unsupported_syntax(cmd: str, shell: str = "bash") -> Optional[str]:
    """指令含白名單外的語法 → 是哪一種（給擋訊息）；可解析 → None。"""
    return split_shell(cmd, shell)[1]


def _low(t: str) -> str:
    """選項保留大小寫（python -V 與 -v 不同）；其餘參數斜線統一、小寫。"""
    return t if t.startswith("-") else t.replace("\\", "/").lower()


def _canon(toks: List[str]) -> List[str]:
    """一個指令的字 → 照原順序的正規化 token：程式取檔名、去 .exe、小寫，python 家族（python3.13／pythonw）一律寫 python；
    python 的選項 `-Xutf8` 寫成 `-X utf8`；python 跑的腳本取檔名（`C:\\中文專案\\run_verify.py` → run_verify.py）；
    其餘參數斜線統一、小寫，選項保留大小寫。"""
    toks = [str(t) for t in toks if str(t) != ""]
    if not toks:
        return []
    head, rest = _prog(toks[0]), toks[1:]
    if not _PY_HEAD_RE.match(head):
        return [head, *(_low(t) for t in rest)]
    opts: List[str] = []
    while rest and rest[0].startswith("-") and rest[0] not in ("-", "-m", "-c"):
        tok = rest.pop(0)
        if tok in _PY_OPT_ARG and rest:
            tok = f"{tok} {rest.pop(0)}"
        elif tok[:2] in _PY_OPT_ARG and len(tok) > 2:
            tok = f"{tok[:2]} {tok[2:]}"
        opts.append(tok)
    if rest and not rest[0].startswith("-"):
        rest[0] = Path(rest[0].replace("\\", "/")).name
    return ["python", *opts, *(_low(t) for t in rest)]


def _norm_cmd(words: List[str]) -> Optional[Cmd]:
    """一個指令 → (程式, python 直譯器選項, 其他選項, 位置參數)。python 跑腳本時程式＝腳本檔名、`python -m 模組` 時程式＝模組
    （`pytest -q x` 與 `python -m pytest -q x` 同一支）；`-` 開頭的是選項（收成集合，順序不計），其餘是位置參數（照順序）。"""
    c = _canon(words)
    if not c:
        return None
    head, i, py_opts = c[0], 1, []
    if head == "python":
        while i < len(c) and c[i].startswith("-") and c[i] not in ("-", "-m", "-c"):
            py_opts.append(c[i])
            i += 1
        if c[i:i + 1] == ["-m"] and i + 1 < len(c):
            head, i = c[i + 1], i + 2
        elif i < len(c) and not c[i].startswith("-"):
            head, i = c[i], i + 1
    rest = c[i:]
    return (head, frozenset(py_opts), frozenset(t for t in rest if t.startswith("-")),
            tuple(t for t in rest if not t.startswith("-")))


def parse_cmds(cmd: Argv, shell: str = "bash") -> List[Step]:
    """指令 → [Step]。字串走 split_shell（白名單外語法 → []）；argv 清單＝一個指令（自寫收據，不經 shell 解析）。"""
    argv = isinstance(cmd, (list, tuple))
    chunks = [(None, [str(t) for t in cmd], False)] if argv else split_shell(str(cmd or ""), shell)[0]
    out: List[Step] = []
    for op, words, stdin in chunks:
        ws = words if argv or shell == "powershell" else _strip_env(words)
        nc = _norm_cmd(ws)
        if nc:
            out.append(Step(op if out else None, nc, tuple(ws), stdin))
    return out


def exec_words(cmd: str, shell: str = "bash") -> List[str]:
    """真的會被執行的指令的字（split_shell 拆出；去掉開頭的 `X=1`；echo／printf／Write-Output／Write-Host 這類只會印字的
    指令整個不算）：引號裡被印出的字、註解、重導向目標都不在裡面；白名單外語法 → []。對帳 (a) 判「收據有沒有提到改的檔」用。"""
    out: List[str] = []
    for _, words, _ in split_shell(str(cmd or ""), shell)[0]:
        ws = [w for w in (words if shell == "powershell" else _strip_env(words)) if w]
        if ws and _prog(ws[0]) not in _ECHO_PROGS:
            out.extend(ws)
    return out


def _plain_filter(st: Step) -> bool:
    """尾端過濾：`| tail`／`| head`／`| Select-Object` 只帶選項與數字（`-n 20`、`-5`、`-Last 5`），不帶檔名、沒有 < 輸入。"""
    return (st.op == "|" and st.cmd[0] in _FILTER_PROGS and not st.stdin
            and all(_FILTER_ARG_RE.match(t) for t in st.words[1:]))


def _first_filter(steps: List[Step]) -> int:
    """尾端那串過濾從第幾個指令開始（沒有就是 len）。"""
    k = len(steps)
    while k > 1 and _plain_filter(steps[k - 1]):
        k -= 1
    return k


def _is_setup(st: Step) -> bool:
    """量尺／整體驗證前面准接的指令：cd 類（根另判）、export／set／unset、PowerShell 變數指定（`$env:X="1"`、`$x = …`）。
    這些不印哨兵；其他指令擺在前面，印出來的成功行分不出是誰印的，就不算。"""
    w = st.words
    if st.cmd[0] in _CD_PROGS:
        return True
    if st.cmd[0] in ("export", "set", "unset"):
        return len(w) > 1 and all(_SETUP_ARG_RE.match(t) for t in w[1:])
    return bool(_PS_ASSIGN_RE.match(w[0]) or (_PS_VAR_RE.match(w[0]) and len(w) > 1 and w[1].startswith("=")))


def _reachable(steps: List[Step], start: int) -> bool:
    """steps[start] 一定會執行、輸出就是它的：接在開頭／;／換行／&& 之後（|| 可能沒跑、| 是把輸入給它），前面只有 cd 與環境設定。"""
    return start == 0 or (steps[start].op in (";", "&&") and all(_is_setup(s) for s in steps[:start]))


def final_step(cmd: Argv, shell: str = "bash") -> Optional[Step]:
    """輸出就是收據的那個指令：前面只准 cd 與環境設定、後面只准乾淨的尾端過濾；不是這種形狀（或白名單外語法）→ None。"""
    steps = parse_cmds(cmd, shell)
    k = _first_filter(steps)
    return steps[k - 1] if k and _reachable(steps, k - 1) else None


def is_whole_run(cmd: Argv, shell: str = "bash") -> bool:
    """整體驗證（對所有改檔都算對得上）：final_step 是不帶任何參數的 run_verify.py，或不帶位置參數、只帶不縮範圍選項
    （-q -v -s -x、-p no:…、--tb=…）的 pytest；直譯器選項只准 -X utf8、-u、-B。-k、-m、--lf、--collect-only、--deselect、
    --ignore、目錄或檔名參數…都不算（白名單：沒列的選項一律不算）。"""
    st = final_step(cmd, shell)
    if not st:
        return False
    head, py, opts, pos = st.cmd
    if not py <= _WHOLE_PY_OPTS:
        return False
    if head == "run_verify.py":
        return not opts and not pos
    return head == "pytest" and all(_PYTEST_WHOLE_OPT_RE.match(o) for o in opts) and all(p.startswith("no:") for p in pos)


def cmd_matches(measure_cmd: Argv, cmd: Argv, shell: str = "bash") -> bool:
    """執行的指令 cmd 是不是跑了表上的量尺 measure_cmd（量尺用 bash 規則解析，cmd 依 shell）：量尺的整條指令鏈
    （各指令與中間的 && || | ;）連續、運算子相同地出現在最後；之後只准乾淨的尾端過濾；之前只准 cd 與環境設定，接的運算子
    是開頭／;／換行／&&。各指令要完全相同：程式、python 直譯器選項集合、其他選項集合、位置參數順序（`-h`、`-u`、`-k 某案`、
    多一個檔名都不算）。白名單外語法、`印假哨兵 || 量尺`、`量尺; echo 假的 DONE`、引號裡的量尺字樣都對不上。"""
    m, e = parse_cmds(measure_cmd), parse_cmds(cmd, shell)
    if not m:
        return False
    for end in range(_first_filter(e), len(e) + 1):
        start = end - len(m)
        if start >= 0 and _reachable(e, start) and all(
                ms.cmd == es.cmd and (k == 0 or ms.op == es.op) for k, (ms, es) in enumerate(zip(m, e[start:end]))):
            return True
    return False


def leading_cd(cmd: str, shell: str = "bash") -> Optional[str]:
    """`cd <絕對路徑> && …`：第一個指令是 cd／pushd／Set-Location 帶單一字面絕對路徑，之後只用 && 與 | 串（cd 失敗後面就都不跑）、
    沒有別的 cd → 回該路徑（Git Bash 的 /c/x 寫成 C:/x），收據根就用它；其餘 → None（照舊當根不可信）。"""
    chunks = split_shell(str(cmd or ""), shell)[0]
    if len(chunks) < 2 or len(chunks[0][1]) != 2 or _prog(chunks[0][1][0]) not in _CD_PROGS:
        return None
    path = chunks[0][1][1]
    if not _ABS_DIR_RE.match(path) or any(ch in path for ch in "$~*?"):
        return None
    if any(op not in ("&&", "|") or (ws and _prog(ws[0]) in _CD_PROGS | {"popd", "pop-location"})
           for op, ws, _ in chunks[1:]):
        return None
    m = re.match(r"^/([A-Za-z])(/.*)?$", path)
    return f"{m.group(1).upper()}:{m.group(2) or '/'}" if m else path


def _quote(t: str) -> str:
    if not t or not _SHELL_SPECIAL_RE.search(t):
        return t or "''"
    return f"'{t}'" if "'" not in t else f'"{t}"'


def cmd_of(argv: List[str]) -> str:
    """收據上的指令字串（顯示用；比對用收據的 argv）：_canon 的結果接回一行（`python -X utf8 "C:\\中文專案\\run_verify.py"` →
    `python -X utf8 run_verify.py`）；含空白或 shell 符號的參數加引號。python 選項 `-X utf8` 本來就是兩個字，原樣接。"""
    return " ".join(t if _PY_OPT_PAIR_RE.match(t) else _quote(t) for t in _canon(list(argv or [])))


def write_self_receipt(claude_dir: Path, argv: List[str], sentinel: str, exit_code: int, cases: int, failed: int,
                       cwd: str, project_root: str, started: float, ended: float,
                       err: Optional[TextIO] = None) -> Optional[Path]:
    """寫一份自寫收據，回寫入的路徑；寫不進去 → err（預設 stderr）印一行、回 None，不拋例外（不改呼叫端的 exit code）。
    project_root＝受測的那棵樹（run_verify 傳自己的 ROOT），cwd 另存（呼叫時的工作目錄，只供追查）。"""
    path = Path(claude_dir) / RUNS_REL / f"{datetime.fromtimestamp(ended, timezone.utc):%Y%m%dT%H%M%SZ}-{os.getpid()}.json"
    rec = {
        "cmd": cmd_of(argv), "argv": list(argv), "sentinel": sentinel, "exit_code": int(exit_code),
        "cases": int(cases), "failed": int(failed), "cwd": cwd, "project_root": project_root,
        "started_at": utc_iso(started), "at": utc_iso(ended), "source": SOURCE,
    }
    try:
        from lib.atom_io import write_text_lf
        write_text_lf(path, json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        return path
    except Exception as e:  # noqa: BLE001  任何寫入失敗都只浮一行訊號，不影響驗證結果
        print(f"[run_verify] 自寫驗證收據失敗（{path}）：{type(e).__name__}: {e}", file=err or sys.stderr)
        return None


GC_KEEP = 200
GC_MAX_AGE_DAYS = 30


def prune_self_runs(claude_dir: Path, keep: int = GC_KEEP, max_age_days: int = GC_MAX_AGE_DAYS,
                    now: Optional[float] = None, err: Optional[TextIO] = None) -> int:
    """_runs/ 清理（SessionEnd 呼叫）：只留最新 keep 份（依檔名時間戳），其餘刪；留下的超過 max_age_days 天（看 mtime）也刪。
    回刪掉的份數；任何一份刪不掉 → err（預設 stderr）一行，繼續下一份。"""
    d = Path(claude_dir) / RUNS_REL
    try:
        files = sorted(d.glob("*.json"), reverse=True)
    except OSError as e:
        print(f"[self_receipt] 清理 {d} 失敗：{type(e).__name__}: {e}", file=err or sys.stderr)
        return 0
    cutoff = (now if now is not None else datetime.now(timezone.utc).timestamp()) - max_age_days * 86400
    removed = 0
    for i, f in enumerate(files):
        try:
            if i >= keep or f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError as e:
            print(f"[self_receipt] 刪不掉舊收據 {f}：{type(e).__name__}: {e}", file=err or sys.stderr)
    return removed


def load_self_receipts(claude_dir: Path, limit: int = LOAD_LIMIT, err: Optional[TextIO] = None) -> List[Dict[str, Any]]:
    """讀 _runs/ 最新的 limit 份自寫收據（檔名以 UTC 時間戳開頭，排序即新舊）；非自寫來源略過。
    目錄列不出來、單份讀不動或壞 JSON → err（預設 stderr）一行（路徑＋錯誤種類），那份不採用（量尺閘照擋，不靜默）。"""
    d = Path(claude_dir) / RUNS_REL
    try:
        files = sorted(d.glob("*.json"), reverse=True)[:limit] if d.is_dir() else []
    except OSError as e:
        print(f"[self_receipt] 列不出自寫收據目錄 {d}：{type(e).__name__}: {e}（量尺閘看不到自寫收據）", file=err or sys.stderr)
        return []
    out: List[Dict[str, Any]] = []
    for f in files:
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"[self_receipt] 自寫收據讀不動 {f}：{type(e).__name__}: {e}（這份不採用）", file=err or sys.stderr)
            continue
        if isinstance(rec, dict) and rec.get("source") == SOURCE:
            out.append(rec)
    return out
