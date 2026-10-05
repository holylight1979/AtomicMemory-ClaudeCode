#!/usr/bin/env python3
"""
init-roles.py — /init-roles backend

職能預設自動來自 AD 群組（hooks/wg_roles.py 三層解析鏈：role.md 人工覆寫 → AD 群組 → 空）；
本工具只做例外覆寫與對帳。裁決名單在 workflow/config.json review.deciders（空＝人人可裁決）。

動作（依參數執行，單次 call 可組合）：
  --me ROLES                人工覆寫職能：寫 <專案或 ~/.claude>/memory/personal/{user}/role.md（逗號分隔，例 art 或 programmer,art）
  --bootstrap-personal      ＝ --me programmer（舊名相容）
  --scaffold-roles          在 memory/_roles.md 建成員表樣板（純登記，程式不讀）
  --add-member USER:ROLES   增/改一筆成員（ROLES 逗號分隔）
  --install-hook            將 ~/.claude/hooks/post-git-pull.sh 複製到 .git/hooks/post-merge 並 chmod +x
  --status                  對帳（JSON）：role.md／AD 群組對映／最終 roles 三層各自解析到什麼＋deciders，不做變動

所有動作均冪等。對每項動作回 JSON：
  {"action": "...", "ok": bool, "changed": bool, "path": "...", ...}

典型呼叫：
  python init-roles.py --project-cwd PATH --status
  python init-roles.py --project-cwd PATH --me art
  python init-roles.py --project-cwd PATH --add-member alice:art
  python init-roles.py --project-cwd PATH --install-hook
"""

import argparse
import json
import re
import stat
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

HOOKS_DIR = Path.home() / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))
from wg_core import find_project_root, get_project_memory_dir  # noqa: E402
from wg_roles import (  # noqa: E402
    get_current_user,
    is_management,
    load_management_roster,
    resolve_roles_detail,
)

HOOK_SOURCE = HOOKS_DIR / "post-git-pull.sh"

ROLES_TEMPLATE = """# Project Role Registry

> 專案成員與角色登記（純登記供人看，程式不讀；職能實際來自 AD 群組或 personal/<user>/role.md）。

## 成員

| User | Roles |
|---|---|

## 角色說明

- programmer: 服務於程式人員工作場景的一切知識
- art: 服務於美術工作場景 — asset、shader、素材處理、圖像工作流
- planner: 服務於企劃工作場景 — 設計規格、流程、需求、平衡
- pm: 專案管理（預設未啟用，依 team 需要開通）
- qa: 測試（預設未啟用）
"""

def _resolve_root(proj_cwd: str) -> Optional[Path]:
    r = find_project_root(proj_cwd)
    if not r:
        return None
    return r


def _proj_memory_base(root: Path) -> Path:
    """專案記憶目錄；root 是 ~/.claude 本身時就是全域 memory/。"""
    return get_project_memory_dir(str(root)) or (root / ".claude" / "memory")


def _roster_path(root: Path) -> Path:
    """成員表在 memory/_roles.md（純登記）。"""
    return _proj_memory_base(root) / "_roles.md"


# ─── Actions ────────────────────────────────────────────────────────────────


def action_status(root: Path, user: str) -> Dict[str, Any]:
    mem = _proj_memory_base(root)
    personal = mem / "personal" / user
    roster_md = _roster_path(root)
    gi = root / ".gitignore"
    hook_dst = root / ".git" / "hooks" / "post-merge"

    detail = resolve_roles_detail(str(root), user, full=True)
    role_md = detail["role_md"]
    ad = detail["ad"]
    return {
        "project_root": str(root),
        "user": user,
        "mem_dir": str(mem),
        "personal_dir_exists": personal.is_dir(),
        "layer1_role_md": {
            "candidates": role_md["candidates"],
            "hit_path": role_md["path"],
            "roles": role_md["roles"],
        },
        "layer2_ad": {
            "available": ad["available"],
            "project_code": ad["project_code"],
            "groups": [g for g in ad["groups"] if "\\" in g],
            "roles": ad["roles"],
        },
        "roles": detail["roles"],
        "roles_source": detail["source"],
        "deciders": load_management_roster(str(root)),
        "can_decide": is_management(str(root), user),
        "roster_md_exists": roster_md.is_file(),
        "roster_md_path": str(roster_md),
        "gitignore_has_personal": (
            gi.is_file() and
            any(ln.strip() == ".claude/memory/personal/"
                for ln in gi.read_text(encoding="utf-8").splitlines())
        ),
        "post_merge_hook_installed": hook_dst.is_file(),
    }


def action_me(root: Path, user: str, roles: List[str]) -> Dict[str, Any]:
    """寫 personal/<user>/role.md 人工覆寫職能（冪等）。"""
    personal = _proj_memory_base(root) / "personal" / user
    personal.mkdir(parents=True, exist_ok=True)
    f = personal / "role.md"
    text = (
        f"- User: {user}\n"
        f"- Role: {', '.join(roles)}\n"
        "<!-- 人工覆寫；留空檔或刪檔即回到 AD 群組解析 -->\n"
    )
    changed = not (f.is_file() and f.read_text(encoding="utf-8") == text)
    if changed:
        f.write_text(text, encoding="utf-8", newline="\n")
    return {"action": "me", "ok": True, "changed": changed, "path": str(f), "roles": roles}


def action_scaffold_roles(root: Path) -> Dict[str, Any]:
    """SPEC §3: roster 檔在 memory/_roles.md（與 wg_roles 讀取位置一致）。"""
    mem = _proj_memory_base(root)
    mem.mkdir(parents=True, exist_ok=True)
    f = _roster_path(root)
    if f.is_file():
        return {"action": "scaffold-roles", "ok": True,
                "changed": False, "path": str(f), "note": "already exists"}
    f.write_text(ROLES_TEMPLATE, encoding="utf-8", newline="\n")
    return {"action": "scaffold-roles", "ok": True,
            "changed": True, "path": str(f)}


def _edit_roles_md(path: Path, update_fn) -> Dict[str, Any]:
    if not path.is_file():
        return {"ok": False, "error": f"_roles.md not found: {path}"}
    text = path.read_text(encoding="utf-8")
    new_text = update_fn(text)
    if new_text == text:
        return {"ok": True, "changed": False, "path": str(path)}
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(new_text, encoding="utf-8", newline="\n")
    tmp.replace(path)
    return {"ok": True, "changed": True, "path": str(path)}


def _update_member_row(text: str, user: str, roles: List[str]) -> str:
    """在「## 成員」下的 table 插入或更新 user 行。"""
    lines = text.splitlines()
    out: List[str] = []
    in_members = False
    in_table = False
    table_end = -1
    inserted = False

    roles_str = ", ".join(roles)
    new_row = f"| {user} | {roles_str} |"

    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"^##\s+成員", stripped):
            in_members = True
            out.append(line)
            continue
        if in_members and stripped.startswith("## "):
            # 結束 table：若未插入過 user 行，在前一個非空行後插入
            if not inserted:
                # 回找 table 末尾（out 的 tail）
                tail_idx = len(out) - 1
                while tail_idx >= 0 and out[tail_idx].strip() == "":
                    tail_idx -= 1
                out.insert(tail_idx + 1, new_row)
                inserted = True
            in_members = False
            in_table = False
            out.append(line)
            continue
        if in_members:
            if stripped.startswith("|---") or stripped.startswith("| ---"):
                in_table = True
                out.append(line)
                continue
            if in_table and stripped.startswith("|"):
                m = re.match(r"^\|\s*([^\s|]+)\s*\|", stripped)
                if m and m.group(1) == user:
                    out.append(new_row)
                    inserted = True
                    continue
            out.append(line)
            continue
        out.append(line)

    if not inserted:
        # 沒成員區 / 沒 table — 附在檔末
        out.append("")
        out.append("## 成員")
        out.append("")
        out.append("| User | Roles |")
        out.append("|---|---|")
        out.append(new_row)
    text_out = "\n".join(out)
    if not text_out.endswith("\n"):
        text_out += "\n"
    return text_out


def action_add_member(root: Path, user: str, roles: List[str]) -> Dict[str, Any]:
    path = _roster_path(root)
    if not path.is_file():
        action_scaffold_roles(root)
    result = _edit_roles_md(path, lambda t: _update_member_row(t, user, roles))
    result["action"] = "add-member"
    result["user"] = user
    result["roles"] = roles
    return result


# ─── Privacy check ────────────────────────────────────────────


_CLOUD_SYNC_PATTERNS = [
    # (label, path fragments to check)
    ("Dropbox", ["Dropbox"]),
    ("iCloud", ["iCloud", "iCloudDrive", "com~apple~CloudDocs"]),
    ("OneDrive", ["OneDrive"]),
    ("Google Drive", ["Google Drive", "My Drive", "GoogleDrive"]),
]


def action_privacy_check(root: Path, user: str) -> Dict[str, Any]:
    """Scan if personal/ dir sits under a cloud-sync path. Warn only."""
    mem = _proj_memory_base(root)
    personal_dir = mem / "personal"
    auto_dir = mem / "personal" / "auto" / user

    warnings: List[str] = []
    personal_abs = str(personal_dir.resolve()).replace("\\", "/")

    # Check cloud sync paths
    for label, fragments in _CLOUD_SYNC_PATTERNS:
        for frag in fragments:
            if frag.lower() in personal_abs.lower():
                warnings.append(
                    f"personal/ 位於 {label} 同步路徑下，自動萃取的個人決策可能被雲端同步。"
                    f"建議將 personal/ 加入 {label} 排除清單。"
                )
                break

    # 專案層 personal/ 的契約是「進版控、僅本人可搜」（SPEC_ATOM_V5 §2；session_start._personal_sync_advisory
    # 同一方向）：索引三檔跟著 repo 走，personal 檔被 ignore 會讓他機索引懸空。這裡只警告「被排除」。
    gitignore = root / ".gitignore"
    gitignore_ignores_personal = False
    if gitignore.is_file():
        try:
            gi_text = gitignore.read_text(encoding="utf-8")
            for line in gi_text.splitlines():
                stripped = line.strip()
                if stripped in (
                    ".claude/memory/personal/",
                    ".claude/memory/personal",
                    "personal/",
                ):
                    gitignore_ignores_personal = True
                    break
        except (OSError, UnicodeDecodeError):
            pass
    if gitignore_ignores_personal:
        warnings.append(
            ".gitignore 排除了 .claude/memory/personal/，"
            "個人 atom 不會跟著 repo 同步到其他機器（索引會懸空）。建議移除該行；"
            "注入過濾只決定模型搜不搜得到、不是保密，敏感內容不要放 personal。"
        )

    # Check SVN svn:ignore (if SVN repo)
    svn_dir = root / ".svn"
    if svn_dir.is_dir():
        try:
            import subprocess
            result = subprocess.run(
                ["svn", "propget", "svn:ignore", str(mem), "--non-interactive"],
                capture_output=True, text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                svn_ignores = result.stdout.strip().splitlines()
                if any("personal" in line for line in svn_ignores):
                    warnings.append(
                        "SVN svn:ignore 排除了 personal/，個人 atom 不會跟著 repo 同步到其他機器。建議移除。"
                    )
        except Exception:
            pass  # svn not available or timeout

    return {
        "action": "privacy-check",
        "ok": True,
        "personal_path": str(personal_dir),
        "warnings": warnings,
        "warning_count": len(warnings),
        "gitignore_has_personal": gitignore_ignores_personal,
    }


def action_install_hook(root: Path) -> Dict[str, Any]:
    if not HOOK_SOURCE.is_file():
        return {"action": "install-hook", "ok": False,
                "error": f"source hook missing: {HOOK_SOURCE}"}
    git_dir = root / ".git"
    if not git_dir.is_dir():
        return {"action": "install-hook", "ok": False,
                "error": f"not a git repo: {root}"}
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    dst = hooks_dir / "post-merge"
    src_text = HOOK_SOURCE.read_text(encoding="utf-8")
    changed = True
    if dst.is_file():
        try:
            if dst.read_text(encoding="utf-8") == src_text:
                changed = False
        except (OSError, UnicodeDecodeError):
            pass
    if changed:
        dst.write_text(src_text, encoding="utf-8", newline="\n")
    try:
        st = dst.stat().st_mode
        dst.chmod(st | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError as e:
        return {"action": "install-hook", "ok": False,
                "error": f"chmod failed: {e}", "path": str(dst)}
    return {"action": "install-hook", "ok": True,
            "changed": changed, "path": str(dst)}


# ─── CLI ────────────────────────────────────────────────────────────────────


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="職能覆寫與對帳（職能預設自動來自 AD 群組）")
    ap.add_argument("--project-cwd", required=True)
    ap.add_argument("--user", default=None,
                    help="Override current user (defaults to CLAUDE_USER/os login)")
    ap.add_argument("--me", metavar="ROLES", default=None,
                    help="人工覆寫職能，寫 personal/<user>/role.md；逗號分隔，例 art 或 programmer,art")
    ap.add_argument("--bootstrap-personal", action="store_true",
                    help="= --me programmer（舊名相容）")
    ap.add_argument("--scaffold-roles", action="store_true",
                    help="Create memory/_roles.md member table template")
    ap.add_argument("--add-member", metavar="USER:ROLES", default=None,
                    help="逗號分隔 roles，例 alice:art 或 bob:programmer,art")
    ap.add_argument("--install-hook", action="store_true")
    ap.add_argument("--privacy-check", action="store_true",
                    help="Scan cloud-sync paths, .gitignore, SVN ignore for personal/")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    root = _resolve_root(args.project_cwd)
    if not root:
        print(json.dumps({"error": "no project root at cwd",
                          "cwd": args.project_cwd}))
        sys.exit(2)

    user = args.user or get_current_user()
    results: List[Dict[str, Any]] = []

    if args.status:
        print(json.dumps(action_status(root, user), ensure_ascii=False, indent=2))
        return

    me_roles = args.me if args.me is not None else ("programmer" if args.bootstrap_personal else None)
    if me_roles is not None:
        roles = [r.strip() for r in me_roles.split(",") if r.strip()]
        if not roles:
            results.append({"action": "me", "ok": False, "error": "ROLES 不得為空"})
        else:
            results.append(action_me(root, user, roles))
    if args.scaffold_roles:
        results.append(action_scaffold_roles(root))
    if args.add_member:
        if ":" not in args.add_member:
            results.append({"action": "add-member", "ok": False,
                            "error": "format must be USER:ROLES"})
        else:
            u, roles_str = args.add_member.split(":", 1)
            roles = [r.strip() for r in roles_str.split(",") if r.strip()]
            results.append(action_add_member(root, u.strip(), roles))
    if args.install_hook:
        results.append(action_install_hook(root))
    if args.privacy_check:
        results.append(action_privacy_check(root, user))

    # auto-run privacy check when bootstrapping (last step of init flow)
    if me_roles is not None and not args.privacy_check:
        results.append(action_privacy_check(root, user))

    if not results:
        results.append({"error": "no action specified; try --status or --help"})

    print(json.dumps({"user": user, "project_root": str(root),
                      "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
