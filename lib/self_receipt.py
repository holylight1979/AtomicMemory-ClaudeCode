"""self_receipt.py：長跑的驗證程式（run_verify.py）自己寫的驗證收據；寫與讀在同一處定格式。

做什麼：CC 單次工具呼叫上限 10 分鐘，全量 run_verify 要跑 18～25 分鐘只能背景跑，PostToolUse 只看得到「已啟動」、
  看不到結尾的量尺哨兵 → session 帳本永遠沒有這把尺的 DONE。所以 run_verify 印完哨兵後自己寫一份收據到
  <CLAUDE_DIR>/workflow/verify-ledger/_runs/<UTC 時間戳>-<pid>.json，MeasureGate 再讀它（hooks/wg_verify_ledger）。
  這個目錄由 PreToolUse 禁止手寫（hooks/handlers/pre_tool_use.check_verify_ledger_write）。
怎麼跑：run_verify.py 呼叫 write_self_receipt；hooks 呼叫 load_self_receipts。
  verify 在 hooks/verify/verify_stop_reconcile.py（自寫收據段）。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

RUNS_REL = Path("workflow") / "verify-ledger" / "_runs"
SOURCE = "run_verify_self"
LOAD_LIMIT = 50


def utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def cmd_of(argv: List[str]) -> str:
    """實際 argv 組成的指令字串：直譯器取檔名主幹（python／python3／pythonw，不帶路徑與 .exe），
    run_verify.py 那個參數取檔名（用絕對路徑呼叫也對得上表上的量尺 `python -X utf8 run_verify.py`）。"""
    if not argv:
        return ""
    head = Path(argv[0]).stem
    rest = [Path(a).name if a.replace("\\", "/").endswith("/run_verify.py") else a for a in argv[1:]]
    return " ".join([head, *rest])


def write_self_receipt(claude_dir: Path, argv: List[str], sentinel: str, exit_code: int, cases: int, failed: int,
                       cwd: str, project_root: str, started: float, ended: float,
                       err: Optional[TextIO] = None) -> Optional[Path]:
    """寫一份自寫收據，回寫入的路徑；寫不進去 → err（預設 stderr）印一行、回 None，不拋例外（不改呼叫端的 exit code）。"""
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


def load_self_receipts(claude_dir: Path, limit: int = LOAD_LIMIT) -> List[Dict[str, Any]]:
    """讀 _runs/ 最新的 limit 份自寫收據（檔名以 UTC 時間戳開頭，排序即新舊）；壞檔與非自寫來源略過。"""
    d = Path(claude_dir) / RUNS_REL
    try:
        files = sorted(d.glob("*.json"), reverse=True)[:limit]
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for f in files:
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict) and rec.get("source") == SOURCE:
            out.append(rec)
    return out
