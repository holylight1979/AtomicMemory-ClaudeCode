#!/usr/bin/env python
"""統一 verify 入口 — scan source 同層 verify/ + skills/{name}/verify/

用法:
  python run_verify.py           # 人讀輸出（pytest -v --tb=short）
  python run_verify.py --json    # 機讀輸出：stdout 純 JSON
                                 #   {exit_code, total, passed, failed, errors, skipped,
                                 #    duration_s, paths, cases:[{id, file, markers, phase,
                                 #    outcome, duration_s, message}]}

印完量尺哨兵後自寫一份驗證收據到資料根（WG_CLAUDE_DIR 或 ~/.claude）的 workflow/verify-ledger/_runs/（lib/self_receipt.py）：全量常要背景跑，
PostToolUse 看不到結尾哨兵：對帳閘靠這份收據認「改完之後跑過、全綠、同根」；收據也記紅掉的測試名（failed_cases）。
--help 不寫。
"""
# 全量改增量待補：這支是全量，已從流程拔掉（部位表不再拿它當量尺；收尾、合併、發版都不跑），只留給手動排查。
import os
import sys
import subprocess
import time
from pathlib import Path

_STARTED = time.time()   # 整輪開始的時刻（自寫收據的 started_at：要晚於最後一次修改才算驗到這次改動）
_CWD = os.getcwd()       # 開跑時的 cwd（個別測試可能 chdir，結尾再取不可靠）

# 測試訊息含非 cp950 字元（如 ⚠）時 --json 會在 Windows 主控台炸掉，統一走 UTF-8
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent


def _load_by_path(name: str, rel: str):
    """用檔案路徑載入本樹 lib 的模組：不動 sys.path，也不受 sys.modules 裡別處的 `lib` 套件影響。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# 使用者資料根：自寫收據寫這裡，量尺閘（hooks/wg_verify_ledger）也從這裡讀；收據的 project_root 另記 ROOT（受測的樹）。
# 在 pytest.main 之前算：根 conftest.py 會在測試期間把 WG_CLAUDE_DIR 導到暫存目錄。
DATA_DIR = _load_by_path("_run_verify_project_root", "lib/project_root.py").claude_data_dir()
fixed = [
    ROOT / "hooks" / "verify",
    ROOT / "tools" / "verify",
    ROOT / "tools" / "codex-companion" / "verify",
    ROOT / "tools" / "auto-continue" / "verify",
    ROOT / "lib" / "verify",
]
skills = ROOT / "skills"
if skills.exists():
    fixed += [d / "verify" for d in skills.iterdir() if d.is_dir() and (d / "verify").exists()]

import argparse

# --help 只印用法不跑；其他未知參數照舊忽略（parse_known_args）
_ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
_ap.add_argument("--json", action="store_true", help="機讀輸出：stdout 純 JSON，量尺哨兵改印 stderr")
as_json = _ap.parse_known_args()[0].json

paths = [str(p) for p in fixed if p.exists()]

if not paths:
    if as_json:
        import json
        print(json.dumps({"exit_code": 0, "total": 0, "passed": 0, "failed": 0,
                          "errors": 0, "skipped": 0, "duration_s": 0.0,
                          "paths": [], "cases": []}))
    else:
        print("No verify/ directories found.")
    sys.exit(0)

# 兩種模式都 in-process 跑 pytest 收案數，結尾印量尺哨兵：全綠 `VERIFY_CHECK DONE cases=<n> failed=0`，
# 有紅／錯 `VERIFY_CHECK FAIL cases=<n> failed=<k>` 且 exit 1（根層部位表 hooks/ 的量尺指令；
# 人讀模式印 stdout，--json 模式印 stderr 讓 stdout 仍是純 JSON）
import io
import json
from contextlib import redirect_stdout

import pytest


class _Collector:
    def __init__(self):
        self.cases = []
        self._markers = {}

    def pytest_collection_modifyitems(self, session, config, items):
        for it in items:
            self._markers[it.nodeid] = sorted({m.name for m in it.iter_markers()})

    def pytest_runtest_logreport(self, report):
        # setup/teardown 正常通過不記；只記 call 結果與異常（error / skip 發生在 setup）
        if report.when != "call" and report.outcome == "passed":
            return
        self.cases.append({
            "id": report.nodeid,
            "file": report.nodeid.split("::", 1)[0],
            "markers": self._markers.get(report.nodeid, []),
            "phase": report.when,
            "outcome": report.outcome,
            "duration_s": round(report.duration, 4),
            "message": report.longreprtext or None,
        })


collector = _Collector()
started = time.time()
if as_json:
    with redirect_stdout(io.StringIO()):
        exit_code = int(pytest.main([*paths, "-q", "--tb=short"], plugins=[collector]))
else:
    print("verify paths:")
    for p in paths:
        print(f"  {p}")
    sys.stdout.flush()
    exit_code = int(pytest.main([*paths, "-v", "--tb=short"], plugins=[collector]))
duration = round(time.time() - started, 2)

counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
for c in collector.cases:
    if c["outcome"] == "passed":
        counts["passed"] += 1
    elif c["outcome"] == "skipped":
        counts["skipped"] += 1
    elif c["phase"] == "call":
        counts["failed"] += 1
    else:  # setup/teardown 失敗 = error
        counts["errors"] += 1

n_failed = counts["failed"] + counts["errors"]
verdict = "DONE" if exit_code == 0 and n_failed == 0 else "FAIL"
sentinel = f"VERIFY_CHECK {verdict} cases={len(collector.cases)} failed={n_failed}"
if verdict == "FAIL" and exit_code == 0:
    exit_code = 1
if as_json:
    print(json.dumps({
        "exit_code": exit_code,
        "total": len(collector.cases),
        **counts,
        "duration_s": duration,
        "paths": paths,
        "cases": collector.cases,
    }, ensure_ascii=False))
    print(sentinel, file=sys.stderr)
else:
    print(sentinel)
sys.stdout.flush()


def _write_self_receipt() -> None:
    """自寫驗證收據到資料根（DATA_DIR）；任何失敗只在 stderr 浮一行（self_receipt 內處理），不改 exit code。"""
    try:
        sys.path.insert(0, str(ROOT))          # self_receipt 寫檔時 import lib.atom_io
        sys.path.insert(0, str(ROOT / "lib"))
        # 用檔案路徑載入：pytest.main 跑過的測試可能已把別處的 `lib` 套件放進 sys.modules，按名字 import 會拿錯版本
        write_self_receipt = _load_by_path("_run_verify_self_receipt", "lib/self_receipt.py").write_self_receipt
        # project_root＝受測的那棵樹（本檔所在的 ROOT），不是呼叫時的 cwd：在 B 目錄跑 A 的 run_verify，驗的是 A
        argv = list(getattr(sys, "orig_argv", None) or [sys.executable, *sys.argv])
        failed_cases = [c["id"] for c in collector.cases if c["outcome"] not in ("passed", "skipped")]
        write_self_receipt(DATA_DIR, argv, sentinel, exit_code, len(collector.cases), n_failed,
                           _CWD, str(ROOT), _STARTED, time.time(), failed_cases=failed_cases)
    except Exception as e:  # noqa: BLE001
        print(f"[run_verify] 自寫驗證收據失敗：{type(e).__name__}: {e}", file=sys.stderr)


_write_self_receipt()
sys.exit(exit_code)
