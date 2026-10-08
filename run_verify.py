#!/usr/bin/env python
"""統一 verify 入口 — scan source 同層 verify/ + skills/{name}/verify/

用法:
  python run_verify.py           # 人讀輸出（pytest -v --tb=short）
  python run_verify.py --json    # 機讀輸出：stdout 純 JSON
                                 #   {exit_code, total, passed, failed, errors, skipped,
                                 #    duration_s, paths, cases:[{id, file, markers, phase,
                                 #    outcome, duration_s, message}]}
"""
import sys
import subprocess
from pathlib import Path

# 測試訊息含非 cp950 字元（如 ⚠）時 --json 會在 Windows 主控台炸掉，統一走 UTF-8
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
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

paths = [str(p) for p in fixed if p.exists()]
as_json = "--json" in sys.argv[1:]

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
import time
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
sys.exit(exit_code)
