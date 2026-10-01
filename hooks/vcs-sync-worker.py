#!/usr/bin/env python3
"""vcs-sync-worker.py — 記憶庫背景上版控的 detached worker。

由 wg_vcs_sync.spawn_vcs_sync 起（pythonw、stderr → Logs/vcs-sync.log）。
stdin JSON：{session_id, cwd, reason, retired_paths, config, targets?, enqueued?}
  - targets 缺省時依 cwd 重算（collect_sync_targets）
  - retired_paths 由 spawn 端合併 ledger（只採 validated 紀錄）後帶入，請求檔也已帶同一份
  - enqueued=true 表示 spawn 端已把請求落 `.req/`，這裡不再重複落檔；缺省（手動跑）則由主邏輯落檔
主邏輯全在 wg_vcs_sync.sync_targets_inline（測試直接呼叫同一函式）；本檔只負責 I/O 與起訖帳。
"""

import json
import os
import sys
from pathlib import Path

_HOOKS_DIR = str(Path.home() / ".claude" / "hooks")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")

from wg_core import append_guard_log, _now_iso  # noqa: E402
from wg_vcs_sync import (  # noqa: E402
    SyncTarget, collect_sync_targets, read_retired_paths, sync_targets_inline,
)


def _log(msg: str) -> None:
    print(f"[{_now_iso()}] [pid {os.getpid()}] {msg}", file=sys.stderr, flush=True)


def _account(event: str, ctx: dict, **extra) -> None:
    try:
        payload = {"event": event, "pid": os.getpid(),
                   "mode": f"vcs-sync:{ctx.get('reason', '')}",
                   "session_id": ctx.get("session_id", "")}
        payload.update(extra)
        append_guard_log("worker-runs", payload)
    except Exception:
        pass


def main() -> int:
    ctx = {}
    try:
        ctx = json.loads(sys.stdin.read() or "{}")
        session_id = ctx.get("session_id", "")
        cwd = ctx.get("cwd", "")
        reason = ctx.get("reason", "") or "worker"
        config = ctx.get("config") or {}
        raw_targets = ctx.get("targets")
        targets = ([SyncTarget.from_dict(d) for d in raw_targets] if raw_targets
                   else collect_sync_targets(cwd, config))
        retired = list(ctx.get("retired_paths") or [])
        if not ctx.get("enqueued"):
            for p in read_retired_paths(session_id):
                if p not in retired:
                    retired.append(p)
        _log(f"start reason={reason} sid={session_id[:8]} roots={[t.root.as_posix() for t in targets]}")
        results = sync_targets_inline(targets, config, retired_paths=retired, log=_log, pre_sync=True,
                                      reason=reason, session_id=session_id,
                                      enqueue=not ctx.get("enqueued"))
        summary = {r["root"]: r.get("status") for r in results}
        _log(f"finish {summary}")
        _account("finish", ctx, results=results)
        return 0
    except Exception as e:  # 永不無聲：crash 也留一筆帳與一行 log
        _log(f"crash {type(e).__name__}: {e}")
        _account("crash", ctx, error=f"{type(e).__name__}: {e}"[:200])
        return 1


if __name__ == "__main__":
    sys.exit(main())
