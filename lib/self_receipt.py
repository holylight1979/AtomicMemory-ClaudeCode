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
import posixpath
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, TextIO, Tuple, Union

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
# 尾端只准接留結尾的過濾：只會刪行、造不出成功行，又留得住印在最後一行的結論（head／-First 只會把結論行切掉）
_FILTER_PROGS = frozenset({"tail", "select-object", "select"})
_FILTER_ARG_RE = re.compile(r"^(?:[+-]?\d+|--?[A-Za-z][A-Za-z-]*=?\d*)$")  # tail 只准選項與數字（不帶檔名）
_LAST_ONLY_RE = re.compile(r"^-last$", re.IGNORECASE)                    # Select-Object 只准 -Last N
_ECHO_PROGS = frozenset({"echo", "printf", "write-output", "write-host", "write", "out-host"})   # 只會印字的指令
_CD_PROGS = frozenset({"cd", "pushd", "set-location", "sl", "chdir", "push-location"})
_CD_ALL = _CD_PROGS | {"popd", "pop-location"}
_WIN_SWITCH_RE = re.compile(r"^/[A-Za-z][\w-]*(?::[^/\\]*)?$")   # msbuild /p:Release、/nologo 這類選項，不是路徑
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
_PS_LITERAL_RE = re.compile(r"^(?:'[^']*'|\"[^\"$`]*\"|-?\d+(?:\.\d+)?|\$(?:true|false|null))$", re.IGNORECASE)
_ABS_DIR_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/[A-Za-z](?:/|$))")
_WHOLE_PY_OPTS = frozenset({"-X utf8", "-u", "-B"})              # 整體驗證准帶的直譯器選項（不改變跑什麼）
_PYTEST_WHOLE_OPT_RE = re.compile(r"^(?:-[qvsx]+|-r\w+|--tb=\w+|--color=\w+|--no-header|--disable-warnings"
                                  r"|--strict-markers)$")        # 整體驗證准帶的 pytest 選項（白名單；沒列的都不算；-p 另配值）
# 跑程式的指令（直譯器、測試與建置工具、腳本檔）：一般證據（對帳 (a) 提到改檔、(b) 量了）的輸出要是它們印的；
# 讀檔與印字的指令（cat、Get-Content、type、echo…）不在裡面，印出舊 log 的哨兵不算
_RUNNER_PROGS = frozenset({
    "python", "pytest", "py.test", "tox", "nox", "node", "deno", "bun", "npm", "npx", "pnpm", "yarn", "jest", "vitest",
    "mocha", "dotnet", "go", "cargo", "make", "cmake", "ctest", "msbuild", "ninja", "java", "mvn", "gradle", "gradlew",
    "ruby", "rspec", "rake", "bundle", "php", "phpunit", "composer", "perl", "lua", "rscript", "swift", "dart",
    "flutter", "julia", "sbt", "bash", "sh", "zsh", "pwsh", "powershell"})
_SCRIPT_EXTS = (".py", ".sh", ".ps1", ".bat", ".cmd", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl")

Argv = Union[str, List[str]]
# (程式, python 直譯器選項照順序, 程式之後的 token 照順序)：比對要整組相等（-W ignore -W error 換順序結果就不同）
Cmd = Tuple[str, Tuple[str, ...], Tuple[str, ...]]
_ENV_ONLY: Cmd = ("", (), ())                                    # 只有 bash 環境指定 `X=1` 的指令（保留下來，運算子才不會丟）


class Chunk(NamedTuple):
    """split_shell 斷出的一個指令（原字，還沒正規化）。"""
    op: Optional[str]           # 接在前一個指令後的運算子：&& || | ;（換行算 ;）；第一個是 None
    words: List[str]            # 去掉引號後的字（重導向與目標已丟掉）
    stdin: bool                 # 有 < 輸入重導向
    stdout: bool                # stdout 導到檔案或 $null（輸出看不到）
    raw: List[str]              # 每個字在原字串裡的樣子（含引號；判斷是字面值還是指令用）


class Step(NamedTuple):
    """指令鏈裡的一個指令。"""
    op: Optional[str]           # 接在前一個指令後的運算子：&& || | ;（換行算 ;）；第一個是 None
    cmd: Cmd                    # 正規化後的指令（只有環境指定的是 _ENV_ONLY）
    words: Tuple[str, ...]      # 去掉引號後的字（bash 已去開頭的 X=1）
    stdin: bool                 # 有 < 輸入重導向（尾端過濾改讀檔）
    stdout: bool                # stdout 導到檔案或 $null
    raw: Tuple[str, ...]        # 與 words 對齊的原字串樣子


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
    raws: List[str] = []
    cur: List[str] = []
    has = skip = stdin = stdout = False
    op: Optional[str] = None
    cont = "`" if ps else "\\"                                   # 行尾續行字元
    i, n, wstart = 0, len(s), 0

    def begin() -> None:
        """字從這裡開始（記原字串位置）。"""
        nonlocal wstart
        if not has:
            wstart = i

    def end_word() -> None:
        nonlocal has, skip
        if has and skip:
            skip = False                                          # 重導向目標，丟掉
        elif has:
            words.append("".join(cur))
            raws.append(s[wstart:i])
        cur.clear()
        has = False

    def end_cmd(nxt: str, hard: bool = False) -> None:
        """一個指令結束；nxt＝接下一個指令的運算子。hard＝字面的 ; 或輸入結尾（換行接在 && || | 後面是合法續接，不算）。"""
        nonlocal op, stdin, stdout
        end_word()
        if skip:
            raise _Unsupported("重導向沒有目標")
        if words:
            out.append(Chunk(op, list(words), stdin, stdout, list(raws)))
            words.clear()
            raws.clear()
            op = nxt
        elif nxt != ";" or (hard and out and op in ("&&", "||", "|")):
            raise _Unsupported("運算子前後缺指令")
        stdin = stdout = False

    def string_start() -> None:
        if ps and not has and not words:
            raise _Unsupported("PowerShell 以引號開頭的指令（字串運算式，不是執行的指令）")

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
        elif c in "'\"":                                          # PowerShell 引號裡連寫兩個（'' 或 ""）是一個字面引號
            string_start()
            begin()
            j, part = i + 1, []
            while True:
                if j >= n:
                    raise _Unsupported("引號沒閉合")
                if s[j] == c:
                    if ps and s[j + 1:j + 2] == c:
                        part.append(c)
                        j += 2
                        continue
                    break
                if c == '"' and s[j] == "`":
                    raise _Unsupported("反引號")
                if c == '"' and s.startswith("$(", j):
                    raise _Unsupported("命令替換 $( )")
                if c == '"' and s.startswith('\\"', j):
                    raise _Unsupported('雙引號裡的跳脫 \\"')
                part.append(s[j])
                j += 1
            cur.append("".join(part))
            has, i = True, j + 1
        elif c == "\\":
            begin()
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
            fd = "&" if c == "&" else ""
            if has and _FD_RE.match("".join(cur)):              # 2>、*> 的 fd 屬於重導向
                fd = "".join(cur)
                cur.clear()
                has = False
            else:
                end_word()
            if skip:
                raise _Unsupported("重導向沒有目標")              # `> > out`：前一個重導向還沒給目標
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
            stdout = stdout or (skip and c != "<" and fd in ("", "1", "*", "&"))   # stdout 導到檔案／$null
        elif c == "&":
            raise _Unsupported("單獨的 &（背景執行／PowerShell 呼叫運算子）")
        elif c in "|;\n":
            end_cmd("|" if c == "|" else ";", hard=c == ";")
            i += 1
        else:
            begin()
            cur.append(c)
            has, i = True, i + 1
    end_cmd(";", hard=True)
    for ch in out:                                                # 指令層：控制結構、把字串當指令跑、另起一層 shell
        w = ch.words if ps else _strip_env(ch.words)
        if not w:
            continue
        if not w[0]:
            raise _Unsupported("空的指令名")
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
    """白名單語法的斷詞 → ([Chunk(運算子, 原字, 有沒有 < 輸入, stdout 有沒有導走), …], None)；白名單外 → ([], 是哪一種)。
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


def _script_id(tok: str, root: str) -> str:
    """腳本是哪一支：有根（從哪裡跑）→ 照根解析成絕對路徑、消掉 . 與 ..（`archive/run_verify.py` 和根下的 `run_verify.py`
    不同支，從 archive/ 裡跑 `run_verify.py` 也不同支）；沒根 → 只看檔名。"""
    base = abs_path(root) if root else None
    if not base:
        return Path(tok.replace("\\", "/")).name
    return posixpath.normpath(abs_path(tok) or f"{base}/{tok.replace(chr(92), '/').lower()}")


def _canon(toks: List[str], root: str = "") -> List[str]:
    """一個指令的字 → 照原順序的正規化 token：程式名取檔名、去 .exe、小寫，python 家族（python3.13／pythonw）一律寫 python；
    程式本身寫成路徑（`./verify.sh`、`C:/live/verify.ps1`）的照 _script_id 認是哪一支；python 的選項 `-Xutf8` 寫成 `-X utf8`；
    python 跑的腳本照 _script_id。其餘參數原樣（大小寫、空字串都保留：`verify:Critical` 與 `verify:critical` 是不同的 task）。"""
    toks = [str(t) for t in toks]
    if not toks:
        return []
    w0, rest = toks[0], toks[1:]
    name = _prog(w0)
    if not _PY_HEAD_RE.match(name):
        return [_script_id(w0, root) if root and ("/" in w0 or "\\" in w0) else name, *rest]
    opts: List[str] = []
    while rest and rest[0].startswith("-") and rest[0] not in ("-", "-m", "-c"):
        tok = rest.pop(0)
        if tok in _PY_OPT_ARG and rest:
            tok = f"{tok} {rest.pop(0)}"
        elif tok[:2] in _PY_OPT_ARG and len(tok) > 2:
            tok = f"{tok[:2]} {tok[2:]}"
        opts.append(tok)
    if rest and rest[0] and not rest[0].startswith("-"):
        rest[0] = _script_id(rest[0], root)
    return ["python", *opts, *rest]


def _norm_cmd(words: List[str], root: str = "") -> Optional[Cmd]:
    """一個指令 → (程式, python 直譯器選項照順序, 程式之後的 token 照順序)。python 跑腳本時程式＝腳本、`python -m 模組` 時
    程式＝模組（`pytest -q x` 與 `python -m pytest -q x` 同一支）。選項與值照原順序保留（換順序可能選到別的測試、結果不同）。"""
    c = _canon(words, root)
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
    return head, tuple(py_opts), tuple(c[i:])


def parse_cmds(cmd: Argv, shell: str = "bash", root: str = "") -> List[Step]:
    """指令 → [Step]。字串走 split_shell（白名單外語法 → []）；argv 清單＝一個指令（自寫收據，不經 shell 解析）。
    只有 bash 環境指定的指令留成 _ENV_ONLY（`X=1 || 量尺` 的 || 要留著）。root：收據根，python 腳本照相對根的路徑認。"""
    argv = isinstance(cmd, (list, tuple))
    chunks = ([Chunk(None, [str(t) for t in cmd], False, False, [str(t) for t in cmd])] if argv
              else split_shell(str(cmd or ""), shell)[0])
    out: List[Step] = []
    for ch in chunks:
        ws = ch.words if argv or shell == "powershell" else _strip_env(ch.words)
        nc = _norm_cmd(ws, root) or (_ENV_ONLY if ch.words else None)
        if nc:
            out.append(Step(ch.op if out else None, nc, tuple(ws), ch.stdin, ch.stdout,
                            tuple(ch.raw[len(ch.words) - len(ws):])))
    return out


def exec_words(cmd: str, shell: str = "bash") -> List[str]:
    """真的會被執行的指令的字（split_shell 拆出；去掉開頭的 `X=1`；echo／printf／Write-Output／Write-Host 這類只會印字的
    指令整個不算）：引號裡被印出的字、註解、重導向目標都不在裡面；白名單外語法 → []。對帳 (a) 判「收據有沒有提到改的檔」用。"""
    out: List[str] = []
    for ch in split_shell(str(cmd or ""), shell)[0]:
        ws = [w for w in (ch.words if shell == "powershell" else _strip_env(ch.words)) if w]
        if ws and _prog(ws[0]) not in _ECHO_PROGS:
            out.extend(ws)
    return out


def _plain_filter(st: Step) -> bool:
    """尾端過濾：`| tail` 只帶選項與數字（`-n 20`、`-5`、`-n +3`）、`| Select-Object -Last N`；不帶檔名、沒有 < 輸入。"""
    if st.op != "|" or st.cmd[0] not in _FILTER_PROGS or st.stdin:
        return False
    args = st.words[1:]
    if st.cmd[0] == "tail":
        return all(_FILTER_ARG_RE.match(t) for t in args)
    return len(args) == 2 and bool(_LAST_ONLY_RE.match(args[0])) and args[1].isdigit()


def _first_filter(steps: List[Step]) -> int:
    """尾端那串過濾從第幾個指令開始（沒有就是 len）。"""
    k = len(steps)
    while k > 1 and _plain_filter(steps[k - 1]):
        k -= 1
    return k


def _is_setup(st: Step) -> bool:
    """量尺／整體驗證前面准接的指令：bash 環境指定 `X=1`、cd 類（根另判）、export／set／unset、PowerShell 變數指定。
    這些不印東西也不換別的程式跑；其他指令擺在前面，印出來的成功行分不出是誰印的，就不算。PowerShell 指定的右邊只准一個
    字面值（引號字串、數字、$true／$false／$null，看原字串）：`$x = Write-Host '…'` 會直接印到畫面、`$x = Set-Location`
    會換目錄，右邊是指令就不算。"""
    w, raw = st.words, st.raw
    if st.cmd == _ENV_ONLY or st.cmd[0] in _CD_PROGS:
        return True
    if st.cmd[0] in ("export", "set", "unset"):
        return len(w) > 1 and all(_SETUP_ARG_RE.match(t) for t in w[1:])
    if _PS_ASSIGN_RE.match(w[0]):
        rhs = [raw[0].split("=", 1)[1], *raw[1:]]
    elif _PS_VAR_RE.match(w[0]) and len(w) > 1 and w[1].startswith("="):
        rhs = [raw[1][1:], *raw[2:]]
    else:
        return False
    rhs = [t for t in rhs if t]
    return len(rhs) == 1 and bool(_PS_LITERAL_RE.match(rhs[0]))


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
    if not st or not set(st.cmd[1]) <= _WHOLE_PY_OPTS:
        return False
    if st.cmd[0] == "run_verify.py":
        return not st.cmd[2]
    if st.cmd[0] != "pytest":
        return False
    i, a = 0, st.cmd[2]
    while i < len(a):                                             # 照順序看：-p 後面一定要接 no:…，其餘只准白名單選項
        if a[i] == "-p" and i + 1 < len(a) and a[i + 1].startswith("no:"):
            i += 2
        elif _PYTEST_WHOLE_OPT_RE.match(a[i]):
            i += 1
        else:
            return False
    return True


def _runs_program(st: Step) -> bool:
    """這個指令是跑程式的（直譯器、測試與建置工具、腳本檔）。"""
    name = _prog(st.words[0]) if st.words else ""
    return name in _RUNNER_PROGS or bool(_PY_HEAD_RE.match(name)) or name.endswith(_SCRIPT_EXTS)


def evidence_steps(cmd: Argv, shell: str = "bash") -> Optional[List[Step]]:
    """一般證據（對帳 (a) 提到改檔、(b) 量了、根層 worktree 的 pytest DONE）的形狀 → 跑程式的那幾段；不是這種形狀 → None。
    形狀：前面只有 cd 與環境設定；之後全是跑程式的指令（直譯器、測試與建置工具、腳本檔），彼此只用 && 串（一段失敗後面就不跑、
    exit 會反映）、stdout 沒有導到檔案或 $null（失敗輸出藏不住）；最後只准留結尾的過濾，而且有過濾時只准一段（管線把最後一段的
    exit 蓋掉，前一段印的成功行會替後一段沒印 FAIL 的失敗背書）。夾了讀檔或印字的指令（cat、Get-Content、echo…）、
    用 ; 或 || 串、把輸出導走，印出來的成功行就分不出是誰印的、哪一段真的過了。"""
    steps = parse_cmds(cmd, shell)
    k = _first_filter(steps)
    i = 0
    while i < k and _is_setup(steps[i]):
        i += 1
    runs = steps[i:k]
    if not runs or not _reachable(steps, i) or any(s.op != "&&" for s in runs[1:]) or (k < len(steps) and len(runs) > 1):
        return None
    return runs if all(_runs_program(s) and not s.stdout for s in runs) else None


def cmd_matches(measure_cmd: Argv, cmd: Argv, shell: str = "bash", root: str = "", measure_root: str = "") -> bool:
    """執行的指令 cmd 是不是跑了表上的量尺 measure_cmd（量尺用 bash 規則解析，cmd 依 shell）：量尺的整條指令鏈
    （各指令與中間的 && || | ;）連續、運算子相同地出現在最後；之後只准乾淨的尾端過濾；之前只准 cd 與環境設定，接的運算子
    是開頭／;／換行／&&。各指令照順序完全相同：程式、python 直譯器選項、其他 token（`-h`、`-u`、`-k 某案`、多一個檔名、
    選項換順序、大小寫都不算；`-Xutf8`＝`-X utf8`）。腳本照路徑認：cmd 照 root（收據從哪裡跑）解析、量尺照 measure_root
    （表所在的根）解析，兩邊只給一個就共用；都沒給只比檔名。多段量尺後面再接過濾時，量尺最後一段要是 echo 類（管線會蓋掉
    最後一段的 exit：最後一段若是會失敗的程式，前段印的 DONE 會替它背書）。白名單外語法、`印假哨兵 || 量尺`、
    `量尺; echo 假的 DONE`、引號裡的量尺字樣都對不上。"""
    m = parse_cmds(measure_cmd, root=measure_root or root)
    e = parse_cmds(cmd, shell, root or measure_root)
    if not m:
        return False
    tail_ok = len(m) == 1 or _prog(m[-1].words[0] if m[-1].words else "") in _ECHO_PROGS
    for end in range(_first_filter(e), len(e) + 1):
        start = end - len(m)
        if start >= 0 and (end == len(e) or tail_ok) and _reachable(e, start) and _chain_at(m, e, start):
            return True
    return False


def _chain_at(m: List[Step], e: List[Step], start: int) -> bool:
    """量尺鏈 m 從 e[start] 起連續出現（各指令照順序相同、中間運算子相同）。"""
    seg = e[start:start + len(m)]
    return len(seg) == len(m) and all(ms.cmd == es.cmd and (k == 0 or ms.op == es.op)
                                      for k, (ms, es) in enumerate(zip(m, seg)))


def ruler_in(measure_cmd: Argv, cmd: Argv, shell: str = "bash", root: str = "") -> bool:
    """量尺鏈出現在 cmd 裡任何位置（不管前後接了什麼；兩邊照同一個根）：只給擋訊息說「量尺前後接了別的指令」，不是證據。"""
    m, e = parse_cmds(measure_cmd, root=root), parse_cmds(cmd, shell, root)
    return bool(m) and any(_chain_at(m, e, s) for s in range(len(e)))


def abs_path(word: str) -> Optional[str]:
    """字面絕對路徑 → 正規化（斜線、小寫，Git Bash 的 /c/x 寫成 c:/x）；不是絕對路徑 → None。"""
    if not _ABS_DIR_RE.match(word):
        return None
    m = re.match(r"^/([A-Za-z])(/.*)?$", word)
    p = f"{m.group(1)}:{m.group(2) or '/'}" if m else word
    return p.replace("\\", "/").rstrip("/").lower()


def _path_in(word: str, base: str, tree: str, literal: bool) -> bool:
    """一個參數字照 base（從哪裡跑）解析後在 tree（收據根）底下：絕對路徑直接比、相對路徑接在 base 後面，都先消掉 . 與 ..；
    `/p:Release` 這種 Windows 工具選項不是路徑；沒有單引號包住的 ~、$變數，以及其他 / 開頭、`C:x` 看不出在哪 → 不在。"""
    if _WIN_SWITCH_RE.match(word):
        return True
    if not literal and (word.startswith("~") or "$" in word):
        return False
    a = abs_path(word)
    if a is None and (word.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", word)):
        return False
    p = posixpath.normpath(a or f"{base}/{word.replace(chr(92), '/').lower()}")
    return p == tree or p.startswith(tree + "/")


def outside_paths(cmd: Argv, shell: str, root: str, cwd: str = "") -> List[str]:
    """跑程式的指令裡指到收據根 root 以外的字：程式本身寫成路徑的（`../live/verify.sh`；python 直譯器除外）、位置參數、
    選項 `=` 後面的值；相對路徑照 cwd（沒給就用 root）解析。cd 與環境設定另判。量尺比對只看腳本身分，`python ../live/run_verify.py`、
    `pytest C:/live/tests` 量的是別棵樹，要靠這裡擋。root 不是絕對路徑（沒根資訊）→ 不比，回 []。"""
    tree = abs_path(str(root or "")) or ""
    base = abs_path(str(cwd or "")) or tree
    out: List[str] = []
    for st in parse_cmds(cmd, shell) if tree else []:
        if _is_setup(st) or not st.words:
            continue
        cands = list(zip(st.words[1:], st.raw[1:]))
        w0 = st.words[0]
        if ("/" in w0 or "\\" in w0) and not _PY_HEAD_RE.match(_prog(w0)):
            cands.insert(0, (w0, st.raw[0]))
        for w, rw in cands:
            v = w.split("=", 1)[1] if w.startswith("-") and "=" in w else ("" if w.startswith("-") else w)
            literal = len(rw) >= 2 and rw[0] == "'" and rw[-1] == "'"          # 單引號裡不展開變數與 ~
            if v and not _path_in(v, base, tree, literal):
                out.append(w)
    return out


def _is_cd(words: List[str], shell: str) -> bool:
    """這個指令換目錄（cd／pushd／popd／Set-Location／sl／chdir，含 `builtin cd`、`command cd`）。"""
    w = words if shell == "powershell" else _strip_env(words)
    if w and _prog(w[0]) in ("builtin", "command"):
        w = w[1:]
    return bool(w) and _prog(w[0]) in _CD_ALL


def changes_dir(cmd: str, shell: str = "bash") -> bool:
    """指令裡有換目錄的指令；用同一套斷詞判，不靠原字串比對（`c"d"` 在 shell 裡就是 cd）。"""
    return any(_is_cd(ch.words, shell) for ch in split_shell(str(cmd or ""), shell)[0])


def leading_cd(cmd: str, shell: str = "bash") -> Optional[str]:
    """`cd <絕對路徑> && …`：第一個指令是 cd／pushd／Set-Location 帶單一字面絕對路徑、緊接 &&（`cd X | …` 的 cd 在管線的子行程，
    不換父 shell 的目錄），之後只用 && 與 | 串（cd 失敗後面就都不跑）、沒有別的 cd → 回該路徑（Git Bash 的 /c/x 寫成 C:/x），
    收據根就用它；其餘 → None（照舊當根不可信）。"""
    chunks = split_shell(str(cmd or ""), shell)[0]
    if (len(chunks) < 2 or chunks[1].op != "&&" or len(chunks[0].words) != 2
            or _prog(chunks[0].words[0]) not in _CD_PROGS):
        return None
    path = chunks[0].words[1]
    if not _ABS_DIR_RE.match(path) or any(ch in path for ch in "$~*?"):
        return None
    if any(ch.op not in ("&&", "|") or _is_cd(ch.words, shell) for ch in chunks[1:]):
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
