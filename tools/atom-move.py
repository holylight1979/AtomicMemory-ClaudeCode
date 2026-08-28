#!/usr/bin/env python3
"""atom-move.py — 原子搬遷工具（V5 SoT-correct：動 _atom_index.json + 搬 sidecar）

子命令：
  move      — 把 atom 搬到目標資料夾（同 index-root 改分類 / 跨 root 換層級），完整同步 JSON SoT
  reconcile — atom 已被手動搬到 --at，掃描修正 JSON 索引與跨層反向連結

契約：
  - 唯一機器索引源是各 memory-root 的 `_atom_index.json`（非 per-folder `_ATOM_INDEX.md`）。
    改 path 一律走 lib.atom_index_json.upsert_atom/delete_atom（自動重生 `_ATOM_INDEX.md` 鏡像）。
  - `.md` 與 `.access.json` sidecar 原子性同搬（lib.atom_access.move_atom_pair；計數不歸零）。
  - 子資料夾不再被誤當 memory root：以 find_index_dir 上溯到擁有 `_atom_index.json` 的根，
    JSON path 一律相對 index_dir.parent（對拍 atom_io 的 index_root=base.parent）。
  - 落 `_AIDocs/_atoms/`（local realm）/ 舊址 `_AIDocs/Failures/`（feedback，title 路由）的 atom
    由專屬路由器管，本工具拒絕搬移、導引到 atom-set-realm.py / title 前綴路由。
    `memory/Failures/<主題>/` 與 `memory/<範疇>/` 在 memory 樹內，是合法的搬移目標；
    全域 memory/ 下的目標資料夾經 core_target_gate（taxonomy Lv1 閉合清單、別名 snap；
    `memory/` 根平鋪只在 taxonomy.gate_enabled=false 時放行）。
  - 搬移後跑 validate_index 自驗；有 error → exit 2。

層序規則（跨 root inbound ref）：
  global (最高) > project (子層)
  - up-ref  (project → global): 合法保留
  - down-ref (global  → project): 違規移除
  - sibling  (projectA → projectB): 警告回報，不自動處理
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

CLAUDE_DIR = Path.home() / ".claude"
GLOBAL_MEMORY = CLAUDE_DIR / "memory"
REGISTRY_PATH = GLOBAL_MEMORY / "project-registry.json"
ATOM_INDEX_JSON = "_atom_index.json"
SKIP_PREFIXES = ("_",)

if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lib.atom_index_json import (  # noqa: E402
    load_atom_index_json, upsert_atom, delete_atom, validate_index,
    find_index_dir as _lib_find_index_dir,
)
from lib.atom_access import (  # noqa: E402
    move_atom_pair, access_sidecar_path, prune_empty_parents,
)
from lib.atom_io import write_raw, _audit_log, _gen_audit_id  # noqa: E402
from lib.atom_locations import (  # noqa: E402
    FAILURES_ROOT_NAME, core_write_target, unclassified_error, validate_category_path,
)
try:
    from lib.atom_taxonomy import core_categories, gate_enabled  # noqa: E402
except Exception:  # taxonomy 缺 → 閘視為關
    def gate_enabled() -> bool:  # type: ignore[misc]
        return False

    def core_categories():  # type: ignore[misc]
        return []

_SOURCE = "tool:atom-move"


def _fail(msg: str):
    print(f"ERROR {msg}", file=sys.stderr)
    sys.exit(1)


def _audit(op: str, **extra: Any) -> None:
    entry = {
        "audit_id": _gen_audit_id(),
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "op": op, "source": _SOURCE,
    }
    entry.update(extra)
    _audit_log(entry)


# ─── frontmatter / Related 解析（跨 root reconcile 用） ───────────────────────


def parse_frontmatter(path: Path) -> Dict[str, str]:
    text = path.read_text(encoding="utf-8")
    fm: Dict[str, str] = {}
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            for line in text[4:end].splitlines():
                m = re.match(r"([A-Za-z_-]+):\s*(.*)", line)
                if m:
                    fm[m.group(1)] = m.group(2).strip()
            return fm
    for line in text.splitlines():
        m = re.match(r"^- ([A-Za-z_-]+):\s*(.*)", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
        elif line.startswith("## "):
            break
    return fm


def get_related(fm: Dict[str, str]) -> List[str]:
    raw = fm.get("Related", "") or fm.get("related", "")
    if not raw or raw.strip() in ("(none)", "—", ""):
        return []
    return [r.strip() for r in raw.split(",") if r.strip()]


def triggers_from_md(md: Path) -> List[str]:
    fm = parse_frontmatter(md)
    raw = fm.get("Trigger", "") or fm.get("trigger", "")
    return [t.strip() for t in raw.split(",") if t.strip()]


def iter_atoms(root: Path):
    if not root.is_dir():
        return
    for p in root.rglob("*.md"):
        if p.name.startswith(SKIP_PREFIXES) or p.name in ("MEMORY.md",):
            continue
        yield p


# ─── index-root / path 解析（修「子夾誤當 root」） ────────────────────────────


def find_index_dir(path: Path) -> Optional[Path]:
    """上溯最近含 `_atom_index.json` 的祖先 = index_dir（單一實作在 lib.atom_index_json）。

    子夾沒有自己的索引，須上溯到擁有 `_atom_index.json` 的 memory-root
    （global=~/.claude/memory；project=專案/.claude/memory）。
    """
    return _lib_find_index_dir(path)


def rel_path_for(moved_md: Path, index_dir: Path) -> str:
    """JSON path 欄位 = 檔案相對 index_dir.parent（global→相對 ~/.claude；project→相對 專案/.claude）。

    對拍 lib.atom_io._resolve_target 的 index_root=base.parent 慣例（純路徑運算，不需檔已存在）。
    """
    return Path(moved_md).resolve(strict=False).relative_to(
        Path(index_dir).parent.resolve()
    ).as_posix()


def is_global_index(index_dir: Path) -> bool:
    try:
        return Path(index_dir).resolve() == GLOBAL_MEMORY.resolve()
    except OSError:
        return False


# 只擋 memory 樹外的受管區；memory/Failures/<主題>/ 在樹內、由本工具正常搬（改分類）。
_SPECIAL_REALM_MARKERS = (
    ("_AIDocs/_atoms", "local realm（_AIDocs/_atoms/）— 改用 tools/atom-set-realm.py 搬 core⇄local"),
    ("_AIDocs/Failures", "feedback/failures 舊址（_AIDocs/Failures/）— 由 title 前綴自動路由，勿手搬"),
)


def special_realm_reason(p: Path) -> Optional[str]:
    """p 落在 local-realm / failures 受管目錄 → 回拒絕原因字串，否則 None。"""
    s = Path(p).resolve(strict=False).as_posix() + "/"
    for marker, reason in _SPECIAL_REALM_MARKERS:
        if f"/{marker}/" in s:
            return reason
    return None


def core_target_gate(to_dir: Path, dst_index: Path, *, dry_run: bool) -> tuple:
    """全域 memory/ 樹內的目標資料夾必須是合法範疇：回 (canon_to_dir, note)。

    - `memory/Failures[/<主題>]`：失敗家族 Lv1，名稱經 validate_category_path 放行。
    - `memory/<Lv1>[/<Lv2>]`：經 core_write_target（taxonomy Lv1 閉合清單、別名／大小寫 snap
      回正名、Lv2 對既有兄弟 snap）；snap 後的資料夾可能與輸入不同，以回傳值為準。
    - `memory/` 根（無範疇段）：寫入閘（taxonomy.gate_enabled）開 → 拒；關 → 放行（遷移期）。
    專案層 index（非全域）不在本閘範圍，原樣回傳。
    """
    if not is_global_index(dst_index):
        return to_dir, None
    try:
        rel = Path(to_dir).resolve(strict=False).relative_to(GLOBAL_MEMORY.resolve())
    except ValueError:
        return to_dir, None
    segs = [s for s in rel.as_posix().split("/") if s and s != "."]
    if not segs:
        if gate_enabled():
            try:
                cats = core_categories()
            except Exception:
                cats = []
            _fail(unclassified_error(None, cats) + " (--to memory/<範疇>/…)")
        return to_dir, "memory/ 根（平鋪）目前放行：taxonomy.gate_enabled=false"
    if segs[0].casefold() == FAILURES_ROOT_NAME.casefold():
        ok_segs, err = validate_category_path("/".join(segs))
        if err or not ok_segs or ok_segs[0] != FAILURES_ROOT_NAME:
            _fail(f"failures target invalid: {err or rel.as_posix()!r} (use memory/{FAILURES_ROOT_NAME}/<主題>)")
        return GLOBAL_MEMORY.joinpath(*ok_segs), None
    target, err = core_write_target("/".join(segs), allow_new=False)
    if err:
        _fail(f"target category rejected: {err}")
    canon_dir = Path(target["dir"])
    if dry_run:
        # core_write_target 會 mkdir 落點：dry-run 不留副作用（空目錄鏈往上清、非空自然停）
        prune_empty_parents(canon_dir, GLOBAL_MEMORY)
        try:
            canon_dir.rmdir()
        except OSError:
            pass
    note = None
    if canon_dir.resolve(strict=False) != Path(to_dir).resolve(strict=False):
        note = f"target snapped to canonical category dir: {canon_dir}"
    return canon_dir, note


# ─── 搬移後的同步：檔頭 Scope / 目錄重生 / 既有錯誤分離 ───────────────────────

_SCOPE_LINE_RE = re.compile(r"^- Scope:\s*(.+?)\s*$", re.MULTILINE)


def sync_scope_header(md: Path, scope: str) -> bool:
    """atom 檔頭 `- Scope:` 與索引 scope 對齊（走 write_raw funnel）。回是否實際改動。"""
    try:
        text = md.read_text(encoding="utf-8-sig")
    except OSError:
        return False
    m = _SCOPE_LINE_RE.search(text)
    if not m or m.group(1) == scope:
        return False
    new_text = text[:m.start()] + f"- Scope: {scope}" + text[m.end():]
    res = write_raw(md, new_text, source=_SOURCE, op="atom_move_scope")
    return bool(getattr(res, "ok", False))


def catalog_sync(index_dir: Path) -> Dict[str, Any]:
    """重生成該 memory root 的目錄：全域 → MEMORY.md + 各層 _INDEX.md；專案 → MEMORY.md
    的 atom-catalog 區塊（tools/sync-memory-index.py --write）。回 {ok, error?}。"""
    script = CLAUDE_DIR / "tools" / "sync-memory-index.py"
    if not script.exists():
        return {"ok": False, "error": f"missing {script}"}
    argv = [sys.executable, str(script), "--write"]
    if not is_global_index(index_dir):
        argv += ["--memory-dir", str(index_dir)]
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", cwd=str(CLAUDE_DIR), timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": str(e)}
    if cp.returncode != 0:
        return {"ok": False, "error": (cp.stderr or cp.stdout).strip()[-300:]}
    return {"ok": True}


def split_validate(baseline: List[str], after: List[str]) -> tuple:
    """(本次新增的錯誤, 搬移前就存在的錯誤)。exit code 只看前者。"""
    base = set(baseline)
    return [e for e in after if e not in base], [e for e in after if e in base]


def find_entry(index_dir: Path, slug: str) -> Optional[Dict[str, Any]]:
    for a in load_atom_index_json(index_dir).get("atoms", []):
        if a.get("name") == slug:
            return a
    return None


def locate_md(index_dir: Path, slug: str, entry: Optional[Dict[str, Any]]) -> Optional[Path]:
    """以 JSON path（相對 index_dir.parent）優先定位；落空則 rglob index_dir。"""
    if entry and entry.get("path"):
        p = Path(index_dir).parent / entry["path"]
        if p.exists():
            return p
    for hit in Path(index_dir).rglob(f"{slug}.md"):
        return hit
    return None


def discover_project_roots() -> List[Path]:
    roots: set = set()
    if REGISTRY_PATH.exists():
        try:
            reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            for _, info in reg.get("projects", {}).items():
                pr = Path(info.get("root", ""))
                mem = pr / ".claude" / "memory"
                if mem.is_dir():
                    roots.add(mem.resolve())
        except (json.JSONDecodeError, OSError):
            pass
    legacy = CLAUDE_DIR / "projects"
    if legacy.is_dir():
        for pd in legacy.iterdir():
            mem = pd / "memory"
            if mem.is_dir():
                try:
                    roots.add(mem.resolve())
                except OSError:
                    pass
    return [Path(r) for r in roots]


def all_index_dirs() -> List[Path]:
    out, seen = [], set()
    for d in [GLOBAL_MEMORY, *discover_project_roots()]:
        try:
            key = d.resolve()
        except OSError:
            key = d
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


# ─── 跨 root 反向連結層序 ─────────────────────────────────────────────────────


def remove_inbound_ref(atom_path: Path, slug: str) -> bool:
    """從 atom_path 的 `- Related:` 移除 slug（走 write_raw funnel）。回是否實際改動。"""
    text = atom_path.read_text(encoding="utf-8")
    m = re.search(r"^- Related:\s*(.+)$", text, re.MULTILINE)
    if not m:
        return False
    items = [i.strip() for i in m.group(1).split(",") if i.strip()]
    new_items = [i for i in items if i != slug]
    if len(new_items) == len(items):
        return False
    new_line = f"- Related: {', '.join(new_items) if new_items else '(none)'}"
    text = text.replace(m.group(0), new_line, 1)
    res = write_raw(atom_path, text, source=_SOURCE, op="atom_move_related")
    return bool(getattr(res, "ok", False))


def reconcile_inbound_refs(slug: str, target_index: Path, dry_run: bool) -> List[str]:
    """跨 root 搬移後：清其他 root 的 stale JSON 條目 + 套 Related 反向連結層序規則。

    V5 single-index：atom 只該住一處索引；其他 root 若有同 slug 條目即 stale，清除。
    Related 用 slug 引用（非 path）→ slug 不變、連結不斷；只需處理 down-ref 違規與 sibling 警告。
    """
    warnings: List[str] = []
    target_is_global = is_global_index(target_index)
    try:
        target_resolved = Path(target_index).resolve()
    except OSError:
        target_resolved = Path(target_index)
    for root in all_index_dirs():
        try:
            if root.resolve() == target_resolved:
                continue
        except OSError:
            continue
        if not root.is_dir():
            continue
        if find_entry(root, slug):
            if not dry_run:
                delete_atom(root, slug)
            warnings.append(f"stale index entry {'would be ' if dry_run else ''}removed: {root / ATOM_INDEX_JSON}")
        root_is_global = is_global_index(root)
        for hit in iter_atoms(root):
            if slug not in get_related(parse_frontmatter(hit)):
                continue
            if root_is_global and not target_is_global:
                if dry_run:
                    warnings.append(f"down-ref would remove: {hit}")
                elif remove_inbound_ref(hit, slug):
                    warnings.append(f"down-ref removed: {hit}")
            elif not root_is_global and not target_is_global:
                warnings.append(f"sibling ref (manual review): {hit} → {slug}")
            # up-ref / same-layer：合法保留，不回報
    return warnings


# ─── 子命令 ───────────────────────────────────────────────────────────────────


def cmd_move(args):
    slug = args.atom
    from_dir = Path(args.src)
    to_dir = Path(args.to)

    src_index = find_index_dir(from_dir)
    if not src_index:
        _fail(f"no {ATOM_INDEX_JSON} at/above --from: {from_dir}")
    dst_index = find_index_dir(to_dir)
    if not dst_index:
        _fail(f"no {ATOM_INDEX_JSON} at/above --to: {to_dir}")

    entry = find_entry(src_index, slug)
    src_md = locate_md(src_index, slug, entry)
    if not src_md or not src_md.exists():
        _fail(f"atom '{slug}' not found under {src_index}")

    for p, lbl in ((src_md, "source"), (to_dir, "target")):
        reason = special_realm_reason(p)
        if reason:
            _fail(f"{lbl} 落在受管目錄：{reason}")

    to_dir, gate_note = core_target_gate(to_dir, dst_index, dry_run=args.dry_run)

    dst_md = to_dir / src_md.name
    if dst_md.resolve(strict=False) == src_md.resolve():
        print(json.dumps({"ok": True, "noop": True, "msg": f"{slug} 已在 {to_dir}"}, ensure_ascii=False))
        return
    if dst_md.exists():
        _fail(f"target already exists: {dst_md}")

    triggers = (entry or {}).get("triggers") or triggers_from_md(src_md)
    cur_scope = (entry or {}).get("scope", "global")
    same_root = src_index.resolve() == dst_index.resolve()
    # scope 一律沿用索引既有值（含 cross-root）；變更須呼叫端以 --scope 明確指定。
    new_scope = args.scope or cur_scope
    new_rel = rel_path_for(dst_md, dst_index)
    # 搬移前的索引錯誤基線：搬完只對「新增的錯誤」exit 2，既有的另欄回報（不混談）。
    baseline_errs = validate_index(dst_index) + ([] if same_root else validate_index(src_index))

    if args.dry_run:
        report = {
            "mode": "DRY-RUN", "slug": slug, "same_root": same_root,
            "from": str(src_md), "to": str(dst_md), "new_rel": new_rel,
            "scope": new_scope, "scope_changed": new_scope != cur_scope,
            "sidecar": access_sidecar_path(src_md).exists(),
        }
        if not same_root and not args.scope:
            report["warn_scope"] = f"跨 root 搬移沿用既有 scope '{cur_scope}'；層級語意若已改變，用 --scope 明確指定"
        if gate_note:
            report["note"] = gate_note
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    # 1) 實體搬（.md + sidecar 原子）
    try:
        sidecar_moved = move_atom_pair(src_md, dst_md)
    except OSError as e:
        _fail(f"move failed: {e}")

    # 2) JSON SoT（失敗 → rollback 實體檔）
    try:
        if same_root:
            upsert_atom(dst_index, slug, new_rel, triggers, scope=new_scope)
        else:
            delete_atom(src_index, slug)
            upsert_atom(dst_index, slug, new_rel, triggers, scope=new_scope)
    except Exception as e:  # noqa: BLE001 — 任何索引失敗都要 rollback 實體
        try:
            dst_md.rename(src_md)
            if sidecar_moved:
                access_sidecar_path(dst_md).rename(access_sidecar_path(src_md))
        except OSError:
            pass
        _fail(f"index update failed (實體已 rollback): {e}")

    _audit("atom_move", slug=slug, from_path=str(src_md), to_path=new_rel,
           same_root=same_root, scope=new_scope, sidecar_moved=sidecar_moved)

    warnings = reconcile_inbound_refs(slug, dst_index, dry_run=False) if not same_root else []

    prune_empty_parents(src_md.parent, src_index)

    # 檔頭 `- Scope:` 跟索引 scope 對齊（跨 root 換層時檔頭常還是舊層）
    header_synced = sync_scope_header(dst_md, new_scope)

    # 目錄重生：目的 root 一定跑；跨 root 時來源 root 也跑（計數 / _INDEX.md 都變了）
    sync: Dict[str, Any] = {"dst": catalog_sync(dst_index)}
    if not same_root:
        sync["src"] = catalog_sync(src_index)

    after = validate_index(dst_index) + ([] if same_root else validate_index(src_index))
    new_errs, preexisting = split_validate(baseline_errs, after)

    report = {
        "mode": "APPLIED", "slug": slug, "same_root": same_root,
        "from": str(src_md), "to_rel": new_rel, "scope": new_scope,
        "scope_changed": new_scope != cur_scope,
        "scope_header_synced": header_synced,
        "sidecar_moved": sidecar_moved, "warnings": warnings,
        "catalog_sync": sync,
        "validate_errors": new_errs,                 # 本次搬移造成的（exit 2）
        "index_preexisting_issues": preexisting,     # 搬移前就有的（只回報）
    }
    if gate_note:
        report["note"] = gate_note
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if new_errs:
        sys.exit(2)


def cmd_reconcile(args):
    slug = args.atom
    at_dir = Path(args.at)
    index_dir = find_index_dir(at_dir)
    if not index_dir:
        _fail(f"no {ATOM_INDEX_JSON} at/above --at: {at_dir}")

    md = None
    if at_dir.is_dir():
        for hit in at_dir.rglob(f"{slug}.md"):
            md = hit
            break
    if md is None:
        md = locate_md(index_dir, slug, find_entry(index_dir, slug))
    if not md or not md.exists():
        _fail(f"atom '{slug}' not found at {at_dir}")

    reason = special_realm_reason(md)
    if reason:
        _fail(f"atom 落在受管目錄：{reason}")

    entry = find_entry(index_dir, slug)
    triggers = (entry or {}).get("triggers") or triggers_from_md(md)
    scope = (entry or {}).get("scope") or ("global" if is_global_index(index_dir) else "shared")
    new_rel = rel_path_for(md, index_dir)
    baseline_errs = validate_index(index_dir)

    header_synced = False
    sync: Dict[str, Any] = {}
    if not args.dry_run:
        upsert_atom(index_dir, slug, new_rel, triggers, scope=scope)
        _audit("atom_reconcile", slug=slug, to_path=new_rel, scope=scope)
        header_synced = sync_scope_header(md, scope)
        sync = {"dst": catalog_sync(index_dir)}

    warnings = reconcile_inbound_refs(slug, index_dir, dry_run=args.dry_run)
    new_errs, preexisting = ([], []) if args.dry_run else split_validate(
        baseline_errs, validate_index(index_dir))

    report = {
        "mode": "DRY-RUN" if args.dry_run else "APPLIED", "slug": slug,
        "index": str(index_dir / ATOM_INDEX_JSON), "rel": new_rel, "scope": scope,
        "scope_header_synced": header_synced, "catalog_sync": sync,
        "warnings": warnings, "validate_errors": new_errs,
        "index_preexisting_issues": preexisting,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if new_errs:
        sys.exit(2)


def main():
    p = argparse.ArgumentParser(description="V5 SoT-correct atom move (JSON index + sidecar)")
    sub = p.add_subparsers(dest="cmd", required=True)

    mv = sub.add_parser("move", help="Move atom to target folder and sync _atom_index.json + sidecar")
    mv.add_argument("atom")
    mv.add_argument("--from", dest="src", required=True, help="source dir (atom located via index/slug)")
    mv.add_argument("--to", required=True, help="target folder (subfolder under a memory-root is OK)")
    mv.add_argument("--scope", default=None,
                    help="explicitly set index scope (default: preserve existing)")
    mv.add_argument("--dry-run", action="store_true")
    mv.set_defaults(func=cmd_move)

    rc = sub.add_parser("reconcile", help="Atom already moved to --at; fix JSON index + inbound refs")
    rc.add_argument("atom")
    rc.add_argument("--at", required=True)
    rc.add_argument("--dry-run", action="store_true")
    rc.set_defaults(func=cmd_reconcile)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
