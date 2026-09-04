#!/usr/bin/env python3
"""
conflict-review.py — backend for /conflict-review.

列 _pending_review/ 草稿與報告；依 is_management() 雙向認證核可 approve/reject。
所有動作寫 _merge_history.log，approve 後觸發 vector reindex。
approve 落點走範疇閘：`shared/<Lv1>[/<Lv2>]/`（`--domain` 或 classify_category 自動分類；
分不出 → 拒、草稿留 pending，不製造未分類 shared atom）＋ `_atom_index.json` upsert
＋ 背景刷新專案 MEMORY.md catalog 區塊。

JSON over stdout；非零 exit code 代表操作失敗（不是 missing pending）。
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

HOOKS_DIR = Path.home() / ".claude" / "hooks"
CLAUDE_DIR = Path.home() / ".claude"
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE_DIR))
from wg_core import find_project_root  # noqa: E402
from wg_roles import is_management, get_current_user  # noqa: E402
from lib.atom_io import _category_gate_enabled, write_index  # noqa: E402
from lib.atom_locations import classify_category, project_category_target  # noqa: E402

_INDEX_SOURCE = "tool:conflict-review"


# ─── Helpers ────────────────────────────────────────────────────────────────

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _proj_mem(proj_cwd: str) -> Optional[Path]:
    root = find_project_root(proj_cwd)
    if not root:
        return None
    mem = root / ".claude" / "memory"
    if not mem.is_dir():
        return None
    return mem


def _pending_dir(mem: Path) -> Path:
    return mem / "shared" / "_pending_review"


def _shared_dir(mem: Path) -> Path:
    return mem / "shared"


def _append_merge_history(mem: Path, action: str, atom: str, scope: str,
                          by: str, detail: str) -> None:
    log_path = mem / "_merge_history.log"
    safe = lambda s: str(s or "-").replace("\t", " ").replace("\n", " ").strip() or "-"
    line = "\t".join([_utcnow_iso(), safe(action), safe(atom), safe(scope),
                      safe(by), safe(detail)]) + "\n"
    try:
        with open(log_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(line)
    except OSError as e:
        print(f"[conflict-review] merge_history write failed: {e}", file=sys.stderr)


def _trigger_reindex() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:3849/index/incremental", method="POST")
        with urllib.request.urlopen(req, timeout=5) as _:
            return True
    except Exception:
        return False


def _preview_text(path: Path, max_len: int = 120) -> str:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return ""
    m = re.search(r"##\s*知識\s*\n+(.+?)(?=\n##\s|\Z)", text, re.DOTALL)
    body = (m.group(1) if m else text).strip()
    body = re.sub(r"\s+", " ", body)
    return body[:max_len]


def _parse_metadata(path: Path) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return meta
    for line in text.splitlines():
        m = re.match(r"^-\s*([\w-]+):\s*(.+)\s*$", line)
        if m:
            meta[m.group(1).lower()] = m.group(2).strip()
    return meta


# ─── Classify pending file kind ─────────────────────────────────────────────

def _classify_file(name: str) -> str:
    if name.endswith(".pull-conflict.md"):
        return "pull-conflict"
    if name.endswith(".conflict.md"):
        return "conflict"
    if name.endswith(".resolved.md"):
        return "resolved"
    if name.endswith(".md"):
        return "draft"
    return "unknown"


def _target_stem(name: str) -> str:
    """Strip .md / .conflict.md / .pull-conflict.md / .resolved.md suffix."""
    for suf in (".pull-conflict.md", ".conflict.md", ".resolved.md", ".md"):
        if name.endswith(suf):
            return name[: -len(suf)]
    return name


# ─── list action ────────────────────────────────────────────────────────────

def action_list(proj_cwd: str) -> Dict[str, Any]:
    mem = _proj_mem(proj_cwd)
    if not mem:
        return {"error": "no V4 project memory at cwd", "cwd": proj_cwd}

    pdir = _pending_dir(mem)
    if not pdir.is_dir():
        return {"pending": [], "total": 0, "project_root": str(mem.parent.parent)}

    items: List[Dict[str, Any]] = []
    for p in sorted(pdir.glob("*.md")):
        kind = _classify_file(p.name)
        if kind == "unknown":
            continue
        stem = _target_stem(p.name)
        meta = _parse_metadata(p)
        items.append({
            "kind": kind,
            "target": stem,
            "file": p.name,
            "path": str(p),
            "author": meta.get("author") or meta.get("incoming-author", ""),
            "detected_at": meta.get("detected-at", ""),
            "pending_review_by": meta.get("pending-review-by", ""),
            "preview": _preview_text(p),
        })
    return {"pending": items, "total": len(items),
            "project_root": str(mem.parent.parent)}


# ─── approve ────────────────────────────────────────────────────────────────

def _strip_pending_marker(text: str, user: str) -> str:
    """Remove `- Pending-review-by:` line, append `- Decided-by:` + bump Last-used.

    Idempotent: if Decided-by already present, replace it.
    """
    today = date.today().isoformat()
    # Remove Pending-review-by line(s)
    text = re.sub(r"^-\s*Pending-review-by:.*\n", "", text, flags=re.MULTILINE)
    # Update Last-used
    if re.search(r"^-\s*Last-used:", text, flags=re.MULTILINE):
        text = re.sub(r"^-\s*Last-used:.*$", f"- Last-used: {today}",
                      text, count=1, flags=re.MULTILINE)
    # Decided-by
    if re.search(r"^-\s*Decided-by:", text, flags=re.MULTILINE):
        text = re.sub(r"^-\s*Decided-by:.*$", f"- Decided-by: {user}",
                      text, count=1, flags=re.MULTILINE)
    else:
        # Insert after Confirmations line if present, else after first metadata block
        if re.search(r"^-\s*Confirmations:", text, flags=re.MULTILINE):
            text = re.sub(r"^(-\s*Confirmations:.*)$",
                          r"\1\n- Decided-by: " + user,
                          text, count=1, flags=re.MULTILINE)
        else:
            # Fallback: append to the end of the first `- Key:` metadata block
            # （插在標題下的空行前會把 metadata 區塊切成兩段，audit 解析器只讀到一欄）
            lines = text.splitlines(keepends=True)
            last_meta = None
            for i, ln in enumerate(lines):
                if re.match(r"^-\s*[\w-]+:", ln):
                    last_meta = i
                elif last_meta is not None and ln.strip():
                    break
            if last_meta is None:
                last_meta = 0
            lines.insert(last_meta + 1, f"- Decided-by: {user}\n")
            text = "".join(lines)
    return text


def _resolve_approve_target(mem: Path, stem: str, triggers: List[str],
                            domain: Optional[str]) -> Dict[str, Any]:
    """核可後的 shared 落點：範疇閘開 → `shared/<Lv1>[/<Lv2>]/`（同 atom_write create 規則）。

    domain 未給 → `classify_category`（詞庫→本地 LLM，閉合清單）；分不出 → 回 error、草稿留在
    `_pending_review/`（不落未分類 shared atom）。閘關 → 扁平 `shared/`（相容）。
    回 {"dir": Path, "category": str|None} 或 {"error": ...}。
    """
    if not _category_gate_enabled():
        return {"dir": _shared_dir(mem), "category": None}
    cat_domain = (domain or "").strip()
    classify: Optional[Dict[str, Any]] = None
    if not cat_domain:
        classify = classify_category(stem, triggers, layer="core")
        cat_domain = classify.get("category") or ""
        if not cat_domain:
            return {"error": "unclassified: approve needs a category — rerun with --domain <Lv1>[/<Lv2>]",
                    "classify": classify,
                    "hint": "Lv1 closed list = memory/_meta/taxonomy.json ∪ <mem>/shared/_taxonomy.json domains"}
    target, err = project_category_target(mem, cat_domain, allow_new=False)
    if err:
        return {"error": err, "classify": classify}
    return {"dir": target["dir"], "category": target["category"], "classify": classify}


def _parse_triggers(meta: Dict[str, Any]) -> List[str]:
    return [t.strip() for t in str(meta.get("trigger") or "").split(",") if t.strip()]


def action_approve(proj_cwd: str, target: str, user: str,
                   domain: Optional[str] = None) -> Dict[str, Any]:
    mem = _proj_mem(proj_cwd)
    if not mem:
        return {"error": "no V4 project memory at cwd"}

    if not is_management(proj_cwd, user):
        return {"error": "not authorized as management",
                "hint": "check personal role.md + shared _roles.md Management 白名單"}

    pdir = _pending_dir(mem)
    sdir = _shared_dir(mem)

    # Allow target with or without suffix
    candidates = [
        pdir / f"{target}.md",
        pdir / f"{target}.resolved.md",
        pdir / target,  # full filename with suffix
    ]
    src: Optional[Path] = next((c for c in candidates if c.is_file()), None)
    if not src:
        return {"error": f"pending target not found: {target}",
                "searched": [str(c) for c in candidates]}

    kind = _classify_file(src.name)
    if kind == "conflict" or kind == "pull-conflict":
        return {"error": "cannot approve a raw conflict report",
                "hint": "先編輯並另存為 {name}.resolved.md，再 approve {name}.resolved"}

    try:
        text = src.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        return {"error": f"read failed: {e}"}

    patched = _strip_pending_marker(text, user)

    # Destination filename: always the stripped stem；落點經範疇閘（shared/<Lv1>/）
    stem = _target_stem(src.name)
    triggers = _parse_triggers(_parse_metadata(src))
    resolved = _resolve_approve_target(mem, stem, triggers, domain)
    if resolved.get("error"):
        return {"error": resolved["error"], "classify": resolved.get("classify"),
                "hint": resolved.get("hint", "草稿仍在 _pending_review/，補 --domain 後重試")}
    dest_dir: Path = resolved["dir"]
    category = resolved.get("category")
    dest = dest_dir / f"{stem}.md"
    if dest.exists() or (sdir / f"{stem}.md").exists():
        return {"error": f"shared target already exists: {dest.name}",
                "hint": "先處理既有 atom（rename / merge / replace）再 approve"}

    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".md.tmp")
    tmp.write_text(patched.replace("\r\n", "\n").replace("\r", "\n"), encoding="utf-8", newline="\n")
    tmp.replace(dest)

    # Remove companion .conflict.md if exists (approval implies conflict was resolved)
    conflict_file = pdir / f"{stem}.conflict.md"
    extras_removed = []
    if conflict_file.is_file():
        try:
            conflict_file.unlink()
            extras_removed.append(conflict_file.name)
        except OSError:
            pass

    try:
        src.unlink()
    except OSError as e:
        return {"error": f"approve wrote {dest} but failed to remove pending src: {e}"}

    rel_path = f"memory/{dest.relative_to(mem).as_posix()}"
    _append_merge_history(mem, "approve", stem, "shared", user,
                          f"from={src.name} to={rel_path}")
    # index upsert（非致命）：核可的 atom 才會被 trigger 注入；MEMORY.md catalog 區塊隨後由
    # sync-memory-index --memory-dir 補（fire-and-forget，同 funnel.js syncMemoryIndex(memoryDir)）。
    ir = write_index(base_dir=mem, slug=stem, rel_path=rel_path, triggers=triggers,
                     source=_INDEX_SOURCE, scope="shared")
    _sync_project_catalog(mem)
    reindexed = _trigger_reindex()

    return {
        "ok": True,
        "target": stem,
        "dest": str(dest),
        "rel_path": rel_path,
        "category": category,
        "classify": resolved.get("classify"),
        "index_ok": ir.ok,
        "index_error": ir.error,
        "extras_removed": extras_removed,
        "reindex_triggered": reindexed,
        "decided_by": user,
    }


def _sync_project_catalog(mem: Path) -> None:
    """背景刷新專案 MEMORY.md 的 catalog 區塊（失敗只 stderr，不阻斷 approve）。"""
    import subprocess
    script = CLAUDE_DIR / "tools" / "sync-memory-index.py"
    if not script.exists():
        return
    try:
        kw: Dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                              "stderr": subprocess.DEVNULL}
        if sys.platform == "win32":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen([sys.executable, str(script), "--write", "--memory-dir", str(mem)], **kw)
    except OSError as e:
        print(f"[conflict-review] sync-memory-index spawn failed: {e}", file=sys.stderr)


# ─── reject ─────────────────────────────────────────────────────────────────

def action_reject(proj_cwd: str, target: str, user: str, reason: str) -> Dict[str, Any]:
    mem = _proj_mem(proj_cwd)
    if not mem:
        return {"error": "no V4 project memory at cwd"}

    if not is_management(proj_cwd, user):
        return {"error": "not authorized as management"}

    pdir = _pending_dir(mem)
    candidates = [
        pdir / f"{target}.md",
        pdir / f"{target}.conflict.md",
        pdir / f"{target}.pull-conflict.md",
        pdir / f"{target}.resolved.md",
        pdir / target,
    ]
    removed: List[str] = []
    for c in candidates:
        if c.is_file():
            try:
                c.unlink()
                removed.append(c.name)
            except OSError:
                pass

    if not removed:
        return {"error": f"pending target not found: {target}"}

    stem = _target_stem(removed[0])
    _append_merge_history(mem, "reject", stem, "shared", user,
                          f"files={','.join(removed)} reason={reason or '-'}")

    return {"ok": True, "target": stem, "removed": removed, "reason": reason}


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="pending-review backend")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--action", choices=["approve", "reject"])
    ap.add_argument("--target", type=str)
    ap.add_argument("--by", type=str, default=None,
                    help="user doing the action; defaults to CLAUDE_USER/os login")
    ap.add_argument("--project-cwd", type=str, required=True)
    ap.add_argument("--reason", type=str, default="")
    ap.add_argument("--domain", type=str, default=None,
                    help="approve 落點範疇 '<Lv1>[/<Lv2>]'（未給 → 自動分類；分不出 → 拒、草稿留 pending）")
    args = ap.parse_args()

    proj_cwd = args.project_cwd
    user = args.by or get_current_user()

    if args.list:
        print(json.dumps(action_list(proj_cwd), ensure_ascii=False, indent=2))
        return

    if args.action == "approve":
        if not args.target:
            print(json.dumps({"error": "--target required"}))
            sys.exit(2)
        result = action_approve(proj_cwd, args.target, user, domain=args.domain)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("ok") else 1)

    if args.action == "reject":
        if not args.target:
            print(json.dumps({"error": "--target required"}))
            sys.exit(2)
        result = action_reject(proj_cwd, args.target, user, args.reason)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("ok") else 1)

    print(json.dumps({"error": "no action specified (use --list or --action=approve/reject)"}))
    sys.exit(2)


if __name__ == "__main__":
    main()
