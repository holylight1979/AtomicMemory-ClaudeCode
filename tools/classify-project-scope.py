#!/usr/bin/env python3
"""classify-project-scope.py — 把一個專案的記憶整理到 scope 分層規則上。

規則（SPEC_ATOM_V5 §2）：personal 只給本人；「針對專案的規則」不是個人偏好，要進 shared 並以
Author 記提出者；索引 scope 由 path 推導；他專案 atom 不注入。整理分兩半：
  腳本能判的（索引 scope 回寫、懸空條目、Scope/Author 標頭、搬檔、目錄重生）→ 本工具做；
  要人判的（每顆 personal 存量該去 shared / 留 personal / 轉本人跨專案 / 刪）→ 本工具先給建議表，
  CC 拿去問使用者，拿到決定後 `apply`。

用法（專案根下執行，或 --memory-dir <proj>/.claude/memory）：
  status                         已整理？（_atom_index.json.layout=="scope-v2" 或 shared/_taxonomy.json）
  plan                           JSON：personal 存量逐顆建議 + 索引問題計數 + shared 平鋪數
  apply --decisions <file.json>  {slug: "shared"|"personal"|"cross_project"|"reject"}；未列者不動；完成後 mark
  mark                           只打「已整理」標記
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CLAUDE_DIR = Path(__file__).resolve().parent.parent
for p in (CLAUDE_DIR, CLAUDE_DIR / "hooks", CLAUDE_DIR / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from lib.atom_index_json import load_atom_index_json, save_atom_index_json, upsert_atom, delete_atom  # noqa: E402
from lib.atom_locations import (  # noqa: E402
    GLOBAL_MEMORY_DIR, scope_from_index_path, scope_layout_classified, SCOPE_LAYOUT_MARK,
)
from lib.atom_spec import is_atom_file  # noqa: E402

_KNOWLEDGE_LINE_RE = re.compile(r"^- \[[固觀臨]\]\s*(.+)$", re.MULTILINE)
_AUTHOR_RE = re.compile(r"^- Author:\s*(.+?)\s*$", re.MULTILINE)
_SCOPE_RE = re.compile(r"^- Scope:\s*(.+?)\s*$", re.MULTILINE)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _resolve_memory_dir(arg: Optional[str]) -> Path:
    if arg:
        return Path(arg).resolve()
    from wg_core import find_project_root
    root = find_project_root(os.getcwd())
    if not root:
        sys.exit("no project root found from cwd; pass --memory-dir")
    return (Path(root) / ".claude" / "memory").resolve()


def _first_statement(text: str) -> str:
    m = _KNOWLEDGE_LINE_RE.search(text)
    return (m.group(1) if m else text.strip().splitlines()[0] if text.strip() else "").strip()


def _read(md: Path) -> str:
    try:
        return md.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return ""


# ─── status / mark ──────────────────────────────────────────────────────────

def cmd_status(mem: Path) -> int:
    how = scope_layout_classified(mem)
    print(json.dumps({"memory_dir": str(mem), "classified": bool(how), "by": how}, ensure_ascii=False))
    return 0 if how else 1


def cmd_mark(mem: Path) -> int:
    data = load_atom_index_json(mem)
    data["layout"] = SCOPE_LAYOUT_MARK
    save_atom_index_json(mem, data)
    print(json.dumps({"memory_dir": str(mem), "marked": SCOPE_LAYOUT_MARK}, ensure_ascii=False))
    return 0


# ─── plan ───────────────────────────────────────────────────────────────────

def build_plan(mem: Path) -> Dict[str, Any]:
    from wg_roles import get_current_user
    worker = _load_module("uew_for_classify", CLAUDE_DIR / "hooks" / "user-extract-worker.py")
    sync = _load_module("sync_atom_index_for_classify", CLAUDE_DIR / "tools" / "sync-atom-index.py")

    root = mem.parent  # <proj>/.claude
    me = get_current_user()
    data = load_atom_index_json(mem)
    personal: List[Dict[str, Any]] = []
    for a in data.get("atoms", []):
        label = scope_from_index_path(a.get("path", ""), "shared")
        if not label.startswith("personal:"):
            continue
        owner = label.split(":", 1)[1]
        md = root / a["path"]
        text = _read(md)
        stmt = _first_statement(text)
        am = _AUTHOR_RE.search(text)
        author = am.group(1) if am else ""
        is_rule = worker._is_project_rule(stmt, a["name"], a.get("triggers", []), str(root.parent), "")
        personal.append({
            "slug": a["name"], "path": a["path"], "owner": owner, "author": author,
            "statement": stmt[:120],
            "suggest": "shared" if is_rule else "personal",
            "reason": "專案規則（專名/此專案/上傳/發布/必須/禁止）" if is_rule else "個人偏好或未見專案規則訊號",
            "mine": owner == me,
        })

    rows = sync.load_index_rows(mem)
    layer = "shared"
    scope_mismatch = sum(1 for r in rows if r.scope != scope_from_index_path(r.path, layer))
    dangling = sum(1 for r in rows if r.path and not (root / r.path).exists())
    rep = sync.detect_drift(sync.scan_atom_files(mem, root), rows, root)
    shared_dir = mem / "shared"
    shared_flat = len([p for p in shared_dir.glob("*.md") if is_atom_file(p, mem)]) if shared_dir.is_dir() else 0
    return {
        "memory_dir": str(mem), "user": me,
        "classified": scope_layout_classified(mem),
        "personal": personal,
        "index": {"scope_mismatch": scope_mismatch, "dangling": dangling,
                  "trigger_drift": len(rep.trigger_drift), "missing_in_index": len(rep.missing_in_index)},
        "shared_flat": shared_flat,
        "has_taxonomy": (shared_dir / "_taxonomy.json").exists(),
    }


def cmd_plan(mem: Path) -> int:
    print(json.dumps(build_plan(mem), ensure_ascii=False, indent=2))
    return 0


# ─── apply ──────────────────────────────────────────────────────────────────

def _set_header(md: Path, key_re: re.Pattern, line: str, insert_after: str = "- Scope:") -> None:
    text = _read(md)
    if not text:
        return
    m = key_re.search(text)
    if m:
        new = text[:m.start()] + line + text[m.end():]
    else:
        new = re.sub(rf"^({re.escape(insert_after)}.*\n)", rf"\1{line}\n", text, count=1, flags=re.MULTILINE)
    if new != text:
        md.write_text(new, encoding="utf-8")


def _move_pair(am, src_md: Path, dst_md: Path) -> None:
    dst_md.parent.mkdir(parents=True, exist_ok=True)
    try:
        am.move_atom_pair(src_md, dst_md)
    except OSError:  # 跨磁碟機 rename 不行 → copy+delete（.md 與 .access.json 一起）
        shutil.move(str(src_md), str(dst_md))
        sc = am.access_sidecar_path(src_md)
        if sc.exists():
            shutil.move(str(sc), str(am.access_sidecar_path(dst_md)))


def _shared_target_dir(mem: Path, slug: str, triggers: List[str]) -> Path:
    """shared 落點：feedback-* → failures/<主題>/；有對應範疇夾才進夾，否則與兄弟一致平鋪 shared/。"""
    from lib.atom_locations import classify_category
    if slug.startswith("feedback-"):
        try:
            cls = classify_category(slug, triggers, layer="failures")
            cat = cls.get("category") if cls.get("status") in ("lex", "llm") else None
        except Exception:  # noqa: BLE001
            cat = None
        return mem / "failures" / (cat or "工作流")
    try:
        cls = classify_category(slug, triggers, layer="shared")
        cat = cls.get("category") if cls.get("status") in ("lex", "llm") else None
    except Exception:  # noqa: BLE001
        cat = None
    if cat and (mem / "shared" / cat.split("/")[0]).is_dir():
        return mem / "shared" / cat
    return mem / "shared"


def cmd_apply(mem: Path, decisions_path: Path, dry_run: bool) -> int:
    am = _load_module("atom_move_for_classify", CLAUDE_DIR / "tools" / "atom-move.py")
    sync = _load_module("sync_atom_index_for_classify", CLAUDE_DIR / "tools" / "sync-atom-index.py")
    decisions: Dict[str, str] = json.loads(decisions_path.read_text(encoding="utf-8"))
    root = mem.parent
    data = load_atom_index_json(mem)
    by_name = {a["name"]: a for a in data.get("atoms", [])}
    report: List[Dict[str, Any]] = []
    touched: set = set()

    for slug, decision in decisions.items():
        a = by_name.get(slug)
        if not a:
            report.append({"slug": slug, "error": "not in index"}); continue
        src_md = root / a["path"]
        if not src_md.exists():
            report.append({"slug": slug, "error": "file missing"}); continue
        owner = scope_from_index_path(a["path"], "shared").split(":", 1)[-1]
        triggers = a.get("triggers", [])
        entry: Dict[str, Any] = {"slug": slug, "decision": decision, "from": a["path"]}

        if decision == "personal":
            entry["to"] = a["path"]
            if not dry_run:
                _set_header(src_md, _AUTHOR_RE, f"- Author: {owner}")
        elif decision == "reject":
            dst = mem / "_rejected" / src_md.name
            entry["to"] = str(dst.relative_to(root)).replace("\\", "/")
            if not dry_run:
                _move_pair(am, src_md, dst)
                delete_atom(mem, slug)
                touched.add(mem)
        elif decision in ("shared", "cross_project"):
            if decision == "shared":
                dst_dir, dst_index, scope = _shared_target_dir(mem, slug, triggers), mem, "shared"
            else:
                dst_dir, dst_index, scope = GLOBAL_MEMORY_DIR / "personal" / owner, GLOBAL_MEMORY_DIR, f"personal:{owner}"
            dst_md = dst_dir / src_md.name
            entry["to"] = str(dst_md)
            entry["scope"] = scope
            if not dry_run:
                if dst_md.exists():
                    entry["error"] = "target exists"; report.append(entry); continue
                _move_pair(am, src_md, dst_md)
                new_rel = am.rel_path_for(dst_md, dst_index)
                if dst_index.resolve() != mem.resolve():
                    delete_atom(mem, slug)
                upsert_atom(dst_index, slug, new_rel, triggers, scope=scope)
                _set_header(dst_md, _SCOPE_RE, f"- Scope: {scope}")
                _set_header(dst_md, _AUTHOR_RE, f"- Author: {owner}")
                if dst_index.resolve() != mem.resolve():
                    am.reconcile_inbound_refs(slug, dst_index, dry_run=False)
                am.prune_empty_parents(src_md.parent, mem)
                touched.add(mem); touched.add(dst_index)
        else:
            entry["error"] = f"unknown decision {decision!r}"
        report.append(entry)

    fix = None
    if not dry_run:
        fix = sync.fix_index_scope_from_path(mem, root, sync.load_index_rows(mem))
        touched.add(mem)
        syncs = {str(r): am.catalog_sync(r) for r in touched}
        cmd_mark(mem)
    else:
        syncs = {}
    print(json.dumps({"mode": "DRY-RUN" if dry_run else "APPLY", "memory_dir": str(mem),
                      "report": report, "index_fix": fix, "catalog_sync": syncs},
                     ensure_ascii=False, indent=2))
    return 1 if any("error" in r for r in report) else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["status", "plan", "apply", "mark"])
    ap.add_argument("--memory-dir", default=None)
    ap.add_argument("--decisions", default=None, help="apply: JSON {slug: shared|personal|cross_project|reject}")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    mem = _resolve_memory_dir(args.memory_dir)
    if args.cmd == "status":
        return cmd_status(mem)
    if args.cmd == "plan":
        return cmd_plan(mem)
    if args.cmd == "mark":
        return cmd_mark(mem)
    if not args.decisions:
        sys.exit("apply requires --decisions <file.json>")
    return cmd_apply(mem, Path(args.decisions), args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
