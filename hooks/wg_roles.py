"""
wg_roles.py — 身份、職能、裁決資格（多機共享、零宣告）

身份＝AD 帳號：get_current_user() 取 CLAUDE_USER → OS 登入帳號；取不到＝"unknown"
（哨兵值，wg_atoms.entry_visible 對它不開任何 personal，同事機器 getuser 失敗不得冒名）。

職能＝三層解析鏈，任一層失敗 fail-open 走下一層並 stderr 一行：
  1. role.md 人工覆寫：<proj>/.claude/memory/personal/<u>/role.md → ~/.claude/memory/personal/<u>/role.md，
     只看 `- Role: a, b` 一行（tools/init-roles.py --me 寫入；留空檔或刪檔即回到 AD）。
  2. AD 群組：whoami /groups（Windows 且有 USERDOMAIN 才跑，每個行程只 spawn 一次），群組名格式
     <網域>\\<專案代碼>_<序號>_<職能名>，依 config roles.ad_group_map 以「職能名子字串」對映
     （先比長鍵）；專案 MEMORY.md 有 `> Project-Code: PRJ001` 只取該專案的群組，沒宣告取聯集。
  3. 都沒有 → []：只看 shared／org／global，不預設 programmer（「不知道」不能被當成「是程式」擴大可見範圍）。

裁決資格＝config review.deciders（AD 帳號清單）；空＝人人可裁決。config 讀壞 → True 並 stderr。
"""

from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import wg_core

_DEFAULT_USER = "unknown"
_ROLE_LINE_RE = re.compile(r"^-\s*Role\s*:\s*(.*)$", re.IGNORECASE)
_PROJECT_CODE_RE = re.compile(r"^>\s*Project-Code:\s*(\S+)", re.MULTILINE)

# whoami 群組原始清單，行程內只查一次（None＝還沒查；失敗也存 [] 不重複 spawn）
_ad_groups_cache: Optional[List[str]] = None


def _warn(msg: str) -> None:
    print(f"[wg_roles] {msg}", file=sys.stderr)


def get_current_user() -> str:
    """env CLAUDE_USER → OS 登入帳號（AD 帳號去網域）→ "unknown"。"""
    u = os.environ.get("CLAUDE_USER")
    if u:
        return u
    try:
        import getpass
        u = getpass.getuser()
    except Exception:  # noqa: BLE001
        u = ""
    return u or _DEFAULT_USER


# ─── 裁決資格 ────────────────────────────────────────────────────────────────


def load_management_roster(cwd: str = "") -> List[str]:
    """config review.deciders；空＝人人可裁決。"""
    cfg = wg_core.load_config()
    if cfg.get("_config_parse_failed"):
        _warn("workflow/config.json 解析失敗，review.deciders 視為空（人人可裁決）")
        return []
    return [str(u) for u in (cfg.get("review", {}) or {}).get("deciders") or []]


def is_management(cwd: str = "", user: str = "") -> bool:
    """deciders 空 → True；非空 → 使用者在名單內。config 讀失敗 → True（fail-open，已 stderr）。"""
    try:
        deciders = load_management_roster(cwd)
    except Exception as e:  # noqa: BLE001
        _warn(f"讀 review.deciders 失敗，放行：{e}")
        return True
    if not deciders:
        return True
    return (user or get_current_user()) in deciders


# ─── 職能：第 1 層 role.md ───────────────────────────────────────────────────


def role_md_candidates(cwd: str, user: str) -> List[Path]:
    """人工覆寫檔的查找順序：專案 → 全域。"""
    if not user or user == _DEFAULT_USER:
        return []
    out: List[Path] = []
    proj_mem = wg_core.get_project_memory_dir(cwd) if cwd else None
    if proj_mem:
        out.append(Path(proj_mem) / "personal" / user / "role.md")
    gl = wg_core.MEMORY_DIR / "personal" / user / "role.md"
    if gl not in out:
        out.append(gl)
    return out


def parse_role_md(path: Path) -> Optional[List[str]]:
    """只解析 `- Role:`；檔不存在或沒有非空 Role 行 → None（視為沒覆寫）。"""
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        m = _ROLE_LINE_RE.match(line.strip())
        if not m:
            continue
        roles = [r.strip() for r in m.group(1).split(",") if r.strip()]
        return roles or None
    return None


# ─── 職能：第 2 層 AD 群組 ───────────────────────────────────────────────────


def ad_available() -> bool:
    return sys.platform == "win32" and bool(os.environ.get("USERDOMAIN"))


def _oem_encoding() -> str:
    """whoami 走主控台 OEM 碼頁（本機 cp950），不是 utf-8。"""
    try:
        import ctypes
        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    except Exception:  # noqa: BLE001
        return "mbcs"


def _whoami_groups() -> List[str]:
    """跑 `whoami /groups /fo csv`，回每列第一欄（群組名）。失敗 raise 由呼叫端轉 stderr。"""
    exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "whoami.exe")
    kwargs: Dict[str, Any] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    r = subprocess.run([exe, "/groups", "/fo", "csv"], capture_output=True, timeout=3, **kwargs)
    if r.returncode != 0:
        raise RuntimeError(f"whoami exit {r.returncode}")
    text = r.stdout.decode(_oem_encoding(), errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    return [row[0] for row in rows[1:] if row]


def ad_groups() -> List[str]:
    """AD 群組名清單（行程內快取）；非 AD 機器或 whoami 失敗 → []（失敗 stderr 一次）。"""
    global _ad_groups_cache
    if _ad_groups_cache is not None:
        return _ad_groups_cache
    if not ad_available():
        _ad_groups_cache = []
        return _ad_groups_cache
    try:
        _ad_groups_cache = _whoami_groups()
    except Exception as e:  # noqa: BLE001
        _warn(f"AD 群組查詢失敗（whoami），職能改走下一層：{e}")
        _ad_groups_cache = []
    return _ad_groups_cache


def project_code(cwd: str) -> str:
    """專案 MEMORY.md 的 `> Project-Code: XXX`；沒有回空字串。"""
    proj_mem = wg_core.get_project_memory_dir(cwd) if cwd else None
    if not proj_mem:
        return ""
    md = Path(proj_mem) / wg_core.MEMORY_INDEX
    if not md.is_file():
        return ""
    m = _PROJECT_CODE_RE.search(md.read_text(encoding="utf-8-sig"))
    return m.group(1).strip() if m else ""


def map_groups_to_roles(groups: List[str], group_map: Dict[str, str], code: str = "") -> List[str]:
    """群組名（去網域）依職能名子字串對映；code 非空只取 `<code>_` 開頭者。去重保序。"""
    keys = sorted((k for k in group_map if k), key=len, reverse=True)
    roles: List[str] = []
    for g in groups:
        if "\\" not in g:
            continue
        name = g.split("\\", 1)[1]
        if code and not name.startswith(code + "_"):
            continue
        hit = next((group_map[k] for k in keys if k in name), None)
        if hit and hit not in roles:
            roles.append(hit)
    return roles


# ─── 職能：解析鏈 ───────────────────────────────────────────────────────────


def resolve_roles_detail(cwd: str, user: str, full: bool = False) -> Dict[str, Any]:
    """三層各自看到什麼＋最終 roles／source。full=True（init-roles --status 對帳）即使 role.md 命中也照查 AD。"""
    detail: Dict[str, Any] = {
        "role_md": {"candidates": [], "path": None, "roles": None},
        "ad": {"available": ad_available(), "groups": [], "project_code": "", "roles": []},
        "roles": [],
        "source": "none",
    }
    try:
        cands = role_md_candidates(cwd, user)
        detail["role_md"]["candidates"] = [str(p) for p in cands]
        for p in cands:
            roles = parse_role_md(p)
            if roles is None:
                continue
            detail["role_md"].update({"path": str(p), "roles": roles})
            detail.update({"roles": roles, "source": "role.md"})
            break
    except Exception as e:  # noqa: BLE001
        _warn(f"role.md 解析失敗，改走 AD：{e}")
    if detail["source"] == "role.md" and not full:
        return detail

    try:
        groups = ad_groups()
        code = project_code(cwd)
        group_map = (wg_core.load_config().get("roles", {}) or {}).get("ad_group_map") or {}
        roles = map_groups_to_roles(groups, group_map, code)
        detail["ad"].update({"groups": groups, "project_code": code, "roles": roles})
        if roles and detail["source"] != "role.md":
            detail.update({"roles": roles, "source": "ad"})
    except Exception as e:  # noqa: BLE001
        _warn(f"AD 職能對映失敗，roles 視為空：{e}")
    return detail


def load_user_role(cwd: str, user: str) -> Dict[str, Any]:
    """回 {"roles": [...], "source": "role.md"|"ad"|"none", "management": bool}。"""
    d = resolve_roles_detail(cwd, user)
    return {"roles": list(d["roles"]), "source": d["source"], "management": is_management(cwd, user)}


def bootstrap_personal_dir(cwd: str, user: str) -> Optional[Path]:
    """相容殼：SessionStart 仍呼叫。不再自動建目錄（personal/<u>/ 由第一次寫入或 --me 建立），回 None。"""
    return None
