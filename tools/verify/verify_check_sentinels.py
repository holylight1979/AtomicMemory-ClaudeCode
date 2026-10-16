"""verify_check_sentinels.py：部位表量尺用的三支 --check 工具自己印完成字樣（<NAME>_CHECK PASS／FAIL），量尺不必再接 echo。

做什麼：在本樹跑 sync_doc_counts.py、skill-index.py、sync-memory-index.py 的 --check，斷言最後一行是該工具的哨兵，
而且 PASS／FAIL 跟 exit code 一致（exit 0 才 PASS）。只讀不寫。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_check_sentinels.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("tool, name", [
    ("sync_doc_counts.py", "DOC_COUNTS_CHECK"),
    ("skill-index.py", "SKILL_INDEX_CHECK"),
    ("sync-memory-index.py", "MEMORY_INDEX_CHECK"),
])
def test_check_mode_prints_its_own_sentinel(tool, name):
    r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / tool), "--check"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    assert last == f"{name} {'PASS' if r.returncode == 0 else 'FAIL'}", (tool, r.returncode, last, r.stderr[-300:])
