"""series_run.py — 005 的 8 跑殼：清掉指揮 session 帶的環境變數、明設 CLAUDE_EFFORT=xhigh（調度 10-27 裁）與 WG_V6=1，
再在 kit/ 裡跑 004 的串跑器 fm_series.py（題組、跑法、加跑規則全照 004；卡用 004 快照）。
怎麼跑：python -X utf8 series_run.py [--only CC,NC] [--resume]
尾行照 fm_series：FM_SERIES DONE …／FM_SERIES FAIL …
"""
import os
import subprocess
import sys
from pathlib import Path

KIT_DIR = Path(__file__).resolve().parent / "kit"
SNAP = Path("C:/Users/holylight/.claude/workflow/inbox/wave2-kit/results/2026-10-23-FM-cards-snapshot")
DROP_ENV = ("CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_SESSION_ID",
            "CLAUDE_JOB_DIR", "CLAUDE_PID", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_EFFORT",
            "CLAUDE_COMPANION_JUDGE")
env = {k: v for k, v in os.environ.items() if k not in DROP_ENV}
env.update(CLAUDE_EFFORT="xhigh", WG_V6="1")
args = ["--day", "2026-10-27-005", "--cards", str(SNAP / "fm-cards.json"), "--snap", str(SNAP), *sys.argv[1:]]
sys.exit(subprocess.run([sys.executable, "-X", "utf8", "-u", "fm_series.py", *args], cwd=str(KIT_DIR), env=env).returncode)
