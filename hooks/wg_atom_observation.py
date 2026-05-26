"""
wg_atom_observation.py — V5 shim

REG-005 atom 注入觀察任務已於 2026-04 結束。本 shim 保留：
  1. main() entry — flag-gated no-op（若 settings 仍掛 hook 不會破壞）
  2. log_injection — re-export from wg_extraction（保留 6 處 UPS 硬呼叫的 API path）

完整原版見 hooks/_v4_archive/wg_atom_observation.py（P6 GA 後可刪除本檔）。
"""

from __future__ import annotations

import sys
from pathlib import Path

# Re-export — UPS handler (handlers/user_prompt_submit.py) 仍可 `from wg_atom_observation import log_injection`
from wg_extraction import log_injection  # noqa: F401


_FLAG_PATH = Path.home() / ".claude" / "memory" / "_staging" / "reg-005-observation-start.flag"


def main() -> None:
    """Flag-gated no-op. Old observation task ended — flag should not exist."""
    if not _FLAG_PATH.exists():
        sys.exit(0)
    # Flag still present (unlikely): drain stdin to keep hook contract, then exit.
    try:
        sys.stdin.buffer.read()
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
