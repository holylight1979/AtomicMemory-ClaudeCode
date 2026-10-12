"""self_receipt.py：長跑的驗證程式（run_verify.py）自己寫的驗證收據；寫與讀在同一處定格式。

做什麼：CC 單次工具呼叫上限 10 分鐘，全量 run_verify 要跑 18～25 分鐘只能背景跑，PostToolUse 只看得到「已啟動」、
  看不到結尾的量尺哨兵 → session 帳本永遠沒有這把尺的 DONE。所以 run_verify 印完哨兵後自己寫一份收據到
  <CLAUDE_DIR>/workflow/verify-ledger/_runs/<UTC 時間戳>-<pid>.json，MeasureGate 再讀它（hooks/wg_verify_ledger）。
  這個目錄由 PreToolUse 禁止手寫（hooks/handlers/pre_tool_use.check_verify_ledger_write）。
怎麼跑：run_verify.py 呼叫 write_self_receipt；hooks 呼叫 load_self_receipts 與 cmd_matches。
  verify 在 lib/verify/verify_self_receipt.py、hooks/verify/verify_stop_reconcile.py（自寫收據段）。
指令比對只有一套（norm_argv）：收據的 cmd（cmd_of）與量尺閘、對帳閘拿表上量尺去比收據，都經過它。
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, TextIO, Tuple, Union

RUNS_REL = Path("workflow") / "verify-ledger" / "_runs"
SOURCE = "run_verify_self"
LOAD_LIMIT = 50


def utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


# ─── 指令正規化（兩端共用） ───────────────────────────────────────────────
_PY_HEAD_RE = re.compile(r"^(?:python(?:\d+(?:\.\d+)*)?w?|py)$", re.IGNORECASE)
_PY_OPT_ARG = ("-X", "-W")                       # 帶一個參數的直譯器選項（`-X utf8` 與 `-Xutf8` 同義）
_SEG_SPLIT_RE = re.compile(r"&&|\|\||[;|\n]")
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

Argv = Union[str, List[str]]


def _tokens(cmd: Argv) -> List[str]:
    if isinstance(cmd, (list, tuple)):
        return [str(t) for t in cmd]
    s = str(cmd or "").replace("\\", "/")
    try:
        return shlex.split(s)
    except ValueError:
        return s.split()


def _canon(cmd: Argv) -> List[str]:
    """照原順序的正規化 token：去掉開頭的 `X=1` 環境指定；程式取檔名、去 .exe、小寫，python 家族（python3.13／pythonw／py）
    一律寫 python；python 的選項 `-Xutf8` 寫成 `-X utf8`（收據上保留原大小寫）；python 跑的腳本取檔名
    （`"C:\\中文專案\\run_verify.py"` → run_verify.py）；其餘參數斜線統一、小寫；引號由切 token 時去掉。"""
    toks = [t for t in _tokens(cmd) if t != ""]
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


def norm_argv(cmd: Argv) -> Tuple[str, FrozenSet[str], List[str]]:
    """指令 → (程式, 直譯器選項集合, 其餘參數)，建在 _canon 上：python 的選項收成小寫集合（`-X utf8` 前後位置不同也一樣；
    舊比對本來就不分大小寫），`python -m 模組` 的程式就是那個模組（`pytest -q x` 與 `python -m pytest -q x` 同一支）。"""
    c = _canon(cmd)
    if not c:
        return "", frozenset(), []
    if c[0] != "python":
        return c[0], frozenset(), c[1:]
    i = 1
    while i < len(c) and c[i].startswith("-") and c[i] not in ("-", "-m", "-c"):
        i += 1
    opts, rest = frozenset(o.lower() for o in c[1:i]), c[i:]
    if rest[:1] == ["-m"] and len(rest) > 1:
        return rest[1], opts, rest[2:]
    return "python", opts, rest


def cmd_of(argv: Argv) -> str:
    """收據上的指令字串（_canon 接回一行）：`python -X utf8 "C:\\中文專案\\run_verify.py"` → `python -X utf8 run_verify.py`。"""
    return " ".join(_canon(argv))


def cmd_matches(measure_cmd: Argv, cmd: Argv) -> bool:
    """收據指令 cmd 是不是跑了表上的量尺 measure_cmd：cmd 以 && || ; | 換行切段，任一段正規化後
    程式相同、量尺的直譯器選項它都有、量尺的參數是它參數的開頭（後面多帶 --json 之類照算）。"""
    m_head, m_opts, m_rest = norm_argv(measure_cmd)
    if not m_head:
        return False
    segs = [cmd] if isinstance(cmd, (list, tuple)) else _SEG_SPLIT_RE.split(str(cmd or ""))
    for seg in segs:
        head, opts, rest = norm_argv(seg)
        if head == m_head and m_opts <= opts and rest[:len(m_rest)] == m_rest:
            return True
    return False


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
