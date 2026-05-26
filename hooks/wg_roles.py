"""
wg_roles.py — V5 shim（單人環境 hardcode）

原 V4 雙向認證 / personal dir bootstrap / management roster 在 single-user 環境
無實質意義。本 shim 保留 4 個函式 API（其他模組仍 import），內容簡化為 hardcode。

未來若回多人協作模式，從 hooks/_v4_archive/wg_roles.py 還原即可。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


_DEFAULT_USER = "holylight"
_DEFAULT_ROLES = ["programmer"]
_DEFAULT_MANAGEMENT = True


def get_current_user() -> str:
    """Return current user — env CLAUDE_USER override else hardcoded default."""
    return os.environ.get("CLAUDE_USER") or _DEFAULT_USER


def load_user_role(cwd: str, user: str) -> Dict[str, Any]:
    """Return fixed role declaration. Single-user env: always programmer+management."""
    return {"roles": list(_DEFAULT_ROLES), "management": _DEFAULT_MANAGEMENT}


def load_management_roster(cwd: str) -> List[str]:
    """Return single-user roster."""
    return [_DEFAULT_USER]


def is_management(cwd: str, user: str) -> bool:
    """Single-user env: current user is always management."""
    return user == _DEFAULT_USER or user == os.environ.get("CLAUDE_USER", "")


def bootstrap_personal_dir(cwd: str, user: str) -> Optional[Path]:
    """Single-user env: no-op. Returns None (caller treats as already-bootstrapped)."""
    return None
