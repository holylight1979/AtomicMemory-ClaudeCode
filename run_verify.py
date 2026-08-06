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

if not as_json:
    print("verify paths:")
    for p in paths:
        print(f"  {p}")
    # stdout 為 pipe 時 print 是 block-buffered，不 flush 會排到子行程 pytest 輸出之後
    sys.stdout.flush()
    result = subprocess.run([sys.executable, "-m", "pytest", *paths, "-v", "--tb=short"])
    sys.exit(result.returncode)

# --json：in-process pytest + 收集 plugin；pytest 的 terminal 輸出導入緩衝，stdout 只留 JSON
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
with redirect_stdout(io.StringIO()):
    exit_code = int(pytest.main([*paths, "-q", "--tb=short"], plugins=[collector]))
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

print(json.dumps({
    "exit_code": exit_code,
    "total": len(collector.cases),
    **counts,
    "duration_s": duration,
    "paths": paths,
    "cases": collector.cases,
}, ensure_ascii=False))
sys.exit(exit_code)
