"""self_receipt.py：長跑的驗證程式（run_verify.py）自己寫的驗證收據；寫與讀在同一處定格式。

做什麼：CC 單次工具呼叫上限 10 分鐘，全量 run_verify 要跑 18～25 分鐘只能背景跑，PostToolUse 只看得到「已啟動」、
  看不到結尾的量尺哨兵 → session 帳本永遠沒有這把尺的 DONE。所以 run_verify 印完哨兵後自己寫一份收據到
  <CLAUDE_DIR>/workflow/verify-ledger/_runs/<UTC 時間戳>-<pid>.json，MeasureGate 再讀它（hooks/wg_verify_ledger）。
  這個目錄由 PreToolUse 禁止手寫（hooks/handlers/pre_tool_use.check_verify_ledger_write）。
怎麼跑：run_verify.py 呼叫 write_self_receipt；hooks 呼叫 load_self_receipts 與 cmd_matches。
  verify 在 lib/verify/verify_self_receipt.py、hooks/verify/verify_stop_reconcile.py（自寫收據段）。
指令比對只有一套（split_shell → parse_cmds → cmd_matches）：收據的 cmd（cmd_of）、量尺閘、對帳閘拿表上量尺去比收據都經過它。
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, TextIO, Tuple, Union

RUNS_REL = Path("workflow") / "verify-ledger" / "_runs"
SOURCE = "run_verify_self"
LOAD_LIMIT = 50


def utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


# ─── 指令解析與比對（收據端、量尺閘、對帳閘共用這一套） ─────────────────────────────
_PY_HEAD_RE = re.compile(r"^(?:python(?:\d+(?:\.\d+)*)?w?|py)$", re.IGNORECASE)
_PY_OPT_ARG = ("-X", "-W")                       # 帶一個參數的直譯器選項（`-X utf8` 與 `-Xutf8` 同義）
_PY_OPT_PAIR_RE = re.compile(r"^-[XW] \S+$")
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_FD_RE = re.compile(r"^(?:\d|\*)$")
_SHELL_SPECIAL_RE = re.compile(r"[\s;&|<>()'\"#`$]")
_FILTER_PROGS = frozenset({"tail", "head", "select-object", "select"})   # 尾端只准接這幾支：只會刪行，造不出成功行
_ECHO_PROGS = frozenset({"echo", "printf", "write-output", "write-host", "write", "out-host"})   # 只會印字的指令
_HEREDOC_RE = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

Argv = Union[str, List[str]]
Cmd = Tuple[str, FrozenSet[str], FrozenSet[str], Tuple[str, ...]]      # (程式, python 直譯器選項, 其他選項, 位置參數)


def split_shell(s: str) -> List[Tuple[Optional[str], List[str]]]:
    """bash／PowerShell 共通的保守斷詞 → [(接在前一個指令後的運算子, 這個指令的字)]；運算子只有 &&、||、|、;
    （換行、單獨的 &、( ) 都當 ;）。'…' 原樣；"…" 只認 \\" `" \\$ 這類跳脫，其餘反斜線照留（Windows 路徑）；
    引號裡的 ; | && 不切，所以 echo 的參數不會變成指令。字首的 # 到行尾是註解；>、>>、2>&1、*>、&>、< 連同目標丟掉；
    heredoc（`<<EOF`、`<<-'EOF'`）的內容行整段跳過，不當指令。"""
    out: List[Tuple[Optional[str], List[str]]] = []
    words: List[str] = []
    cur: List[str] = []
    heredocs: List[str] = []
    has = skip = False
    op: Optional[str] = None

    def end_word() -> None:
        nonlocal has, skip
        if has and skip:
            skip = False
        elif has:
            words.append("".join(cur))
        cur.clear()
        has = False

    def end_cmd(nxt: str) -> None:
        nonlocal op, skip
        end_word()
        skip = False
        if words:
            out.append((op, list(words)))
            words.clear()
            op = nxt
        elif nxt != ";":
            op = nxt

    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r":
            end_word()
            i += 1
        elif c == "#" and not has:
            j = s.find("\n", i)
            i = n if j < 0 else j
        elif c == "'":
            j = s.find("'", i + 1)
            j = n if j < 0 else j
            cur.append(s[i + 1:j])
            has, i = True, j + 1
        elif c == '"':
            i += 1
            while i < n and s[i] != '"':
                if s[i] in "\\`" and s[i + 1:i + 2] in ('"', "`", "$"):
                    i += 1
                cur.append(s[i])
                i += 1
            has, i = True, i + 1
        elif c in "\\`" and s[i + 1:i + 2] == "\n":           # 續行
            i += 2
        elif s.startswith(("&&", "||"), i):
            end_cmd(s[i:i + 2])
            i += 2
        elif s.startswith("<<", i) and not s.startswith("<<<", i) and _HEREDOC_RE.match(s, i):
            m = _HEREDOC_RE.match(s, i)
            end_word()
            heredocs.append(m.group(2))
            i = m.end()
        elif c == "\n" and heredocs:                          # heredoc 內容到結束標記那一行為止，整段跳過
            end_cmd(";")
            pos = i + 1
            for d in heredocs:
                while pos < n:
                    e = s.find("\n", pos)
                    line, pos = s[pos:n if e < 0 else e], (n if e < 0 else e + 1)
                    if line.strip() == d:
                        break
            heredocs.clear()
            i = pos
        elif c in "<>" or s.startswith("&>", i):
            if has and _FD_RE.match("".join(cur)):          # 2>、*> 的 fd 屬於重導向
                cur.clear()
                has = False
            else:
                end_word()
            i += 1 if c == "&" else 0
            while i < n and s[i] in "<>":
                i += 1
            if s[i:i + 1] == "&":                            # 2>&1：沒有目標檔
                i += 1
                while i < n and (s[i].isdigit() or s[i] == "-"):
                    i += 1
            else:
                skip = True                                   # 下一個字是重導向目標，丟掉
        elif c in "|;\n&()":
            end_cmd("|" if c == "|" else ";")
            i += 1
        else:
            cur.append(c)
            has, i = True, i + 1
    end_cmd(";")
    return out


def _canon(toks: List[str]) -> List[str]:
    """一個指令的字 → 照原順序的正規化 token：去掉開頭的 `X=1` 環境指定；程式取檔名、去 .exe、小寫，python 家族
    （python3.13／pythonw／py）一律寫 python；python 的選項 `-Xutf8` 寫成 `-X utf8`（收據上保留原大小寫）；python 跑的
    腳本取檔名（`C:\\中文專案\\run_verify.py` → run_verify.py）；其餘參數斜線統一、小寫。"""
    toks = [str(t) for t in toks if str(t) != ""]
    while toks and _ENV_ASSIGN_RE.match(toks[0]):
        toks = toks[1:]
    if not toks:
        return []
    head = Path(toks[0].replace("\\", "/")).name.lower()
    head = head[:-4] if head.endswith(".exe") else head
    rest = toks[1:]
    if not _PY_HEAD_RE.match(head):
        return [head, *(t.replace("\\", "/").lower() for t in rest)]
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
    return ["python", *opts, *(t.replace("\\", "/").lower() for t in rest)]


def _norm_cmd(words: List[str]) -> Optional[Cmd]:
    """一個指令 → (程式, python 直譯器選項, 其他選項, 位置參數)。python 跑腳本時程式＝腳本檔名、`python -m 模組` 時程式＝模組
    （`pytest -q x` 與 `python -m pytest -q x` 同一支）；`-` 開頭的是選項（收成集合，順序不計），其餘是位置參數（照順序）。"""
    c = _canon(words)
    if not c:
        return None
    head, i, py_opts = c[0], 1, []
    if head == "python":
        while i < len(c) and c[i].startswith("-") and c[i] not in ("-", "-m", "-c"):
            py_opts.append(c[i].lower())
            i += 1
        if c[i:i + 1] == ["-m"] and i + 1 < len(c):
            head, i = c[i + 1], i + 2
        elif i < len(c) and not c[i].startswith("-"):
            head, i = c[i], i + 1
    rest = c[i:]
    return (head, frozenset(py_opts), frozenset(t for t in rest if t.startswith("-")),
            tuple(t for t in rest if not t.startswith("-")))


def exec_words(cmd: str) -> List[str]:
    """真的會被執行的指令的字（split_shell 拆出；去掉開頭的 `X=1`；echo／printf／Write-Output／Write-Host 這類只會印字的
    指令整個不算）：引號裡被印出的字、註解、重導向目標、heredoc 內容都不在裡面。對帳 (a) 判「收據有沒有提到改的檔」用。"""
    out: List[str] = []
    for _, words in split_shell(str(cmd or "")):
        ws = [w for w in words if w]
        while ws and _ENV_ASSIGN_RE.match(ws[0]):
            ws = ws[1:]
        head = Path(ws[0].replace("\\", "/")).name.lower() if ws else ""
        if ws and (head[:-4] if head.endswith(".exe") else head) not in _ECHO_PROGS:
            out.extend(ws)
    return out


def parse_cmds(cmd: Argv) -> List[Tuple[Optional[str], Cmd]]:
    """指令（字串走 split_shell；argv 清單＝一個指令）→ [(接在前一個指令後的運算子, 正規化後的指令)]。"""
    chunks = [(None, [str(t) for t in cmd])] if isinstance(cmd, (list, tuple)) else split_shell(str(cmd or ""))
    out: List[Tuple[Optional[str], Cmd]] = []
    for op, words in chunks:
        nc = _norm_cmd(words)
        if nc:
            out.append((op if out else None, nc))
    return out


def _first_filter(cmds: List[Tuple[Optional[str], Cmd]]) -> int:
    """尾端那串 `| tail …`／`| head …`／`| Select-Object …` 從第幾個指令開始（沒有就是 len）。"""
    k = len(cmds)
    while k > 1 and cmds[k - 1][0] == "|" and cmds[k - 1][1][0] in _FILTER_PROGS:
        k -= 1
    return k


def final_cmd(cmd: Argv) -> Optional[Cmd]:
    """最後被執行的那個指令（尾端的 tail／head／Select-Object 不算）；沒有回 None。"""
    cmds = parse_cmds(cmd)
    k = _first_filter(cmds)
    return cmds[k - 1][1] if k else None


def _same_cmd(m: Cmd, e: Cmd) -> bool:
    """程式相同；量尺有的 python 直譯器選項它都要有；其他選項集合相等；位置參數照順序相等（不准多帶，`-k 某案`、多一個檔名都不算）。"""
    return m[0] == e[0] and m[1] <= e[1] and m[2] == e[2] and m[3] == e[3]


def cmd_matches(measure_cmd: Argv, cmd: Argv) -> bool:
    """執行的指令 cmd 是不是跑了表上的量尺 measure_cmd：量尺的整條指令鏈（各指令與中間的 && || | ;）連續、運算子相同地出現，
    而且就在最後；之後只准接 `| tail`、`| head`、`| Select-Object`。`量尺; echo 假的 DONE`、`量尺 && echo …`（量尺本身沒有那段）、
    引號裡的量尺字樣、子集或多帶參數都對不上。"""
    m, e = parse_cmds(measure_cmd), parse_cmds(cmd)
    if not m:
        return False
    for end in range(_first_filter(e), len(e) + 1):
        start = end - len(m)
        if start >= 0 and all(_same_cmd(mc, ec) and (k == 0 or mo == eo)
                              for k, ((mo, mc), (eo, ec)) in enumerate(zip(m, e[start:end]))):
            return True
    return False


def _quote(t: str) -> str:
    if not t or not _SHELL_SPECIAL_RE.search(t):
        return t or "''"
    return f"'{t}'" if "'" not in t else '"' + t.replace("\\", "\\\\").replace('"', '\\"') + '"'


def cmd_of(argv: List[str]) -> str:
    """收據上的指令字串：_canon 的結果接回一行（`python -X utf8 "C:\\中文專案\\run_verify.py"` → `python -X utf8 run_verify.py`）；
    含空白或 shell 符號的參數加引號，split_shell 讀回來是同一串字。python 選項 `-X utf8` 本來就是兩個字，原樣接。"""
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
