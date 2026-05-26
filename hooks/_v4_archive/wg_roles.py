"""
wg_roles.py — V4 角色宣告 / 雙向認證 / personal dir bootstrap

對應 SPEC_ATOM_V4.md 第 6 節「角色機制」。

- get_current_user: Windows / Unix 跨平台 + CLAUDE_USER env 覆寫
- load_user_role: 讀 personal/{user}/role.md 解析自我宣告
- load_management_roster: 讀 shared _roles.md 的 Management 白名單
- is_management: 雙向認證（personal 宣告 + shared 白名單，缺一不可）
- bootstrap_personal_dir: 首次進專案建 personal/{user}/ + role.md 樣板 +
  冪等 append .claude/memory/personal/ 到 .gitignore
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from wg_paths import CLAUDE_DIR, MEMORY_INDEX, find_project_root


def _is_global_claude_root(root: Path) -> bool:
    """~/.claude 自身不視為 V4 專案（其 memory == global）。"""
    try:
        return root.resolve() == CLAUDE_DIR.resolve()
    except OSError:
        return False

# ─── User 身份 ────────────────────────────────────────────────────────────────


def get_current_user() -> str:
    """回傳當前使用者名稱。

    優先 CLAUDE_USER env（CI / 測試 / 多帳號切換用）；fallback os.getlogin()。
    os.getlogin() 在 Windows / Unix 行為不同但對 interactive session 都 OK。
    """
    return os.environ.get("CLAUDE_USER") or os.getlogin()


# ─── Role Declaration 解析 ────────────────────────────────────────────────────


_ROLE_LINE_RE = re.compile(r"^-\s*Role:\s*(.+)$", re.IGNORECASE)
_MGMT_LINE_RE = re.compile(r"^-\s*Management:\s*(true|false)\s*$", re.IGNORECASE)


def _project_memory_base(cwd: str) -> Optional[Path]:
    """找到 {proj}/.claude/memory/；無標記回 None。

    與 get_scope_dir 同一 guard 邏輯，但不 mkdir（純查詢）。
    """
    root = find_project_root(cwd)
    if not root or _is_global_claude_root(root):
        return None
    has_marker = (
        (root / ".claude" / "memory" / MEMORY_INDEX).exists()
        or (root / "_AIDocs").is_dir()
        or (root / ".git").exists()
        or (root / ".svn").exists()
    )
    if not has_marker:
        return None
    return root / ".claude" / "memory"


def load_user_role(cwd: str, user: str) -> Dict[str, Any]:
    """讀 personal/{user}/role.md 回傳 {"roles": [...], "management": bool}。

    雙重來源都識別：
      - `- Role: programmer, management`（逗號列表含 management）
      - `- Management: true` 獨立欄位
    任一為真即視為 personal 宣告為管理職。
    """
    empty = {"roles": [], "management": False}
    base = _project_memory_base(cwd)
    if not base:
        return empty
    role_file = base / "personal" / user / "role.md"
    if not role_file.exists():
        return empty

    roles: List[str] = []
    mgmt_flag = False
    for line in role_file.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        m = _ROLE_LINE_RE.match(s)
        if m:
            roles = [r.strip() for r in m.group(1).split(",") if r.strip()]
            continue
        m = _MGMT_LINE_RE.match(s)
        if m:
            mgmt_flag = m.group(1).lower() == "true"

    management = mgmt_flag or ("management" in [r.lower() for r in roles])
    return {"roles": roles, "management": management}


# ─── Management Roster ───────────────────────────────────────────────────────


def load_management_roster(cwd: str) -> List[str]:
    """讀 shared _roles.md 的 `## Management 白名單` 區塊。

    白名單格式（SPEC 6.3）：
      ## Management 白名單
      - holylight1979
      - alice

    回傳 user 列表；檔案不存在或無該區塊回空 list。
    """
    base = _project_memory_base(cwd)
    if not base:
        return []
    roster_file = base / "_roles.md"
    if not roster_file.exists():
        return []

    users: List[str] = []
    in_section = False
    for line in roster_file.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if re.match(r"^##\s+Management", s, re.IGNORECASE):
            in_section = True
            continue
        if in_section and s.startswith("##"):
            break
        if in_section:
            m = re.match(r"^-\s+(\S+)", s)
            if m:
                users.append(m.group(1).strip())
    return users


def is_management(cwd: str, user: str) -> bool:
    """雙向認證（SPEC 6.2）：personal 宣告 + shared 白名單，缺一不可。

    任何一端缺失 → False。目的是防止自封管理職而改動事實衝突仲裁。
    """
    info = load_user_role(cwd, user)
    if not info["management"]:
        return False
    return user in load_management_roster(cwd)


# ─── Bootstrap personal dir ──────────────────────────────────────────────────


_ROLE_TEMPLATE = """# Role Declaration

- User: {user}
- Role: programmer
- Management: false

> 請依實際職務修改 Role（programmer / art / planner / pm / qa / management，
> 逗號分隔多值）。Management 需另在 shared `_roles.md` 白名單登記才生效。
"""

_GITIGNORE_LINE = ".claude/memory/personal/"


def bootstrap_personal_dir(cwd: str, user: str) -> Optional[Path]:
    """首次進專案建立 personal/{user}/，冪等。

    步驟：
      1. 確保 {proj}/.claude/memory/personal/{user}/ 存在
      2. 若 role.md 不存在 → 寫樣板（存在則不動，避免覆寫使用者編輯）
      3. 冪等 append `.claude/memory/personal/` 到專案 .gitignore
    專案無標記 → 回 None。
    """
    root = find_project_root(cwd)
    if not root or _is_global_claude_root(root):
        return None
    has_marker = (
        (root / ".claude" / "memory" / MEMORY_INDEX).exists()
        or (root / "_AIDocs").is_dir()
        or (root / ".git").exists()
        or (root / ".svn").exists()
    )
    if not has_marker:
        return None

    personal_dir = root / ".claude" / "memory" / "personal" / user
    personal_dir.mkdir(parents=True, exist_ok=True)

    role_file = personal_dir / "role.md"
    if not role_file.exists():
        role_file.write_text(_ROLE_TEMPLATE.format(user=user), encoding="utf-8")

    _append_gitignore(root, _GITIGNORE_LINE)
    return personal_dir


def _append_gitignore(root: Path, line: str) -> None:
    """冪等 append 一行到 {root}/.gitignore。比對時忽略兩端空白與註解。"""
    gi = root / ".gitignore"
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    # 逐行比對去掉空白，避免因尾端換行差異重複寫入
    for existing_line in existing.splitlines():
        if existing_line.strip() == line.strip():
            return
    prefix = ""
    if existing and not existing.endswith("\n"):
        prefix = "\n"
    gi.write_text(existing + prefix + line + "\n", encoding="utf-8")
