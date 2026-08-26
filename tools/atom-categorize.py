#!/usr/bin/env python3
"""atom-categorize.py — 核心層批次歸類搬遷（plan | apply | undo）

把 index 裡的 atom 依對映表搬進範疇資料夾：
  memory/<slug>.md            → memory/<Lv1>[/<Lv2>]/<slug>.md      （"版控/Git"）
  _AIDocs/Failures/<slug>.md  → memory/Failures/<主題>/<slug>.md     （"Failures/驗證與實證"）
  memory/… 或 _AIDocs/…       → _AIDocs/_atoms/<domain>/<slug>.md    （"local:MemDev"，委派 atom-set-realm）
  <proj>/.claude/memory/shared/<slug>.md → shared/<Lv1>[/<Lv2>]/     （--memory-dir，專案層；根＝shared/）

契約：
  - `_atom_index.json` 是唯一真相：atom 以 index path 定位，搬完 path 也只改 index（write_index，
    source=tool:atom-categorize，_ATOM_INDEX.md mirror 自動重生）。不在 index 的檔不搬。
  - 分類名走 taxonomy 閉合清單（Lv1 正名／slug／別名皆可，snap 回正名；Lv2 自由）+ validate_category_path
    沙盒（保留名／字元集）。分不出、撞名、sidecar 落單一律列 error，plan 有任何 error 則 apply 拒跑。
  - `.md` 與 `.access.json` 用 lib.atom_access.move_atom_pair 原子同搬；apply 落 undo.json
    （sidecar 在 .gitignore，git 救不回，undo.json 是唯一反向依據）。
  - 跨 realm（local:）委派 tools/atom-set-realm.py（_AIDocs/_atoms/ path 的唯一寫者）；undo 時為了
    逐字還原原路徑，改走本工具的 move_atom_pair + write_index（不經 set_realm 的落點推導）。
  - 對映表格式（plans/core-categories.json）：
      {"atoms": {slug: "版控/Git" | "Failures/驗證與實證" | "local:MemDev"},
       "reference_git_mv": {src_rel: dst_rel}}      ← 非 atom 參考文件，只列清單、不搬（S3 用 git mv）
    也接受扁平 {slug: target}（`_` 開頭鍵視為註解）。
  - `plan` 不給 --map 時，對根下未歸類 atom 用 taxonomy 詞庫（score_by_lexicon）出草案（proposed=true），
    只是提案，不落地。

用法：
  atom-categorize.py plan  --map plans/core-categories.json [--memory-dir <mem>] [--dry-run]
  atom-categorize.py apply --map plans/core-categories.json [--dry-run] [--undo-file <json>]
  atom-categorize.py undo  --undo-file plans/categorize-<ts>.undo.json [--dry-run]
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

CLAUDE_DIR = Path.home() / ".claude"
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lib.atom_access import access_sidecar_path, move_atom_pair, prune_empty_parents  # noqa: E402
from lib.atom_classify import score_by_lexicon  # noqa: E402
from lib.atom_index_json import load_atom_index_json, validate_index  # noqa: E402
from lib.atom_io import _audit_log, _gen_audit_id, write_index  # noqa: E402
from lib.atom_locations import (  # noqa: E402
    FAILURES_ROOT_NAME, GLOBAL_MEMORY_DIR, LEGACY_FAILURES_DIR, LOCAL_ATOMS_DIR,
    is_flat_core_path, is_in_failures_path, is_legacy_failures_path, is_local_realm_path,
    known_category_paths, local_realm_path_segments, normalize_domain_path, validate_category_path,
)
from lib.atom_taxonomy import (  # noqa: E402
    TaxonomyUnavailable, category_term_pairs, core_categories, failures_topics, match_lv1,
)

_SOURCE = "tool:atom-categorize"
_SET_REALM_FILE = CLAUDE_DIR / "tools" / "atom-set-realm.py"
DEFAULT_UNDO_DIR = CLAUDE_DIR / "plans"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ts_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ─── 版面：全域 vs 專案層 ────────────────────────────────────────────────────


class Layout:
    """memory_dir 決定根與相對路徑前綴：全域 memory/（含 Failures、local）；專案 memory/shared/。"""

    def __init__(self, memory_dir: Path):
        self.memory_dir = Path(memory_dir).resolve()
        self.claude_root = self.memory_dir.parent           # index path 的相對根
        try:
            self.is_global = self.memory_dir == GLOBAL_MEMORY_DIR.resolve()
        except OSError:
            self.is_global = False
        self.core_root = self.memory_dir if self.is_global else self.memory_dir / "shared"
        self.core_rel_prefix = "memory" if self.is_global else "memory/shared"

    def rel(self, p: Path) -> str:
        return Path(p).resolve(strict=False).relative_to(self.claude_root).as_posix()

    def is_flat(self, rel_path: str) -> bool:
        """根下散檔（尚未歸類）：全域 memory/<slug>.md；專案 memory/shared/<slug>.md。"""
        if self.is_global:
            return is_flat_core_path(rel_path)
        prefix = self.core_rel_prefix + "/"
        return rel_path.startswith(prefix) and "/" not in rel_path[len(prefix):]

    def prune_stop(self, src: Path) -> Path:
        """搬離後清空目錄鏈的止點（不含）：local 樹止於 _atoms、舊址止於 _AIDocs/Failures、其餘止於範疇根。"""
        s = src.resolve(strict=False)
        for stop in (LOCAL_ATOMS_DIR, LEGACY_FAILURES_DIR):
            try:
                if stop.resolve() in s.parents:
                    return stop
            except OSError:
                continue
        return self.core_root


# ─── 對映表 ──────────────────────────────────────────────────────────────────


def load_map(path: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("map must be a JSON object")
    if "atoms" in data:
        atoms = data.get("atoms") or {}
        refs = data.get("reference_git_mv") or {}
    else:
        atoms = {k: v for k, v in data.items() if not str(k).startswith("_")}
        refs = {}
    if not isinstance(atoms, dict) or not all(isinstance(v, str) for v in atoms.values()):
        raise ValueError("atoms map must be {slug: target-string}")
    return dict(atoms), dict(refs or {})


# ─── 目標解析 ────────────────────────────────────────────────────────────────


def resolve_target(target: str, layout: Layout) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """對映值 → {kind, segs|domain, dst_dir, canon}；錯 → (None, error)。"""
    raw = (target or "").strip().replace("\\", "/")
    if not raw:
        return None, "empty target"
    if raw.startswith("local:"):
        if not layout.is_global:
            return None, "local: realm targets exist only in the global layer"
        dom = raw[len("local:"):].strip("/ ")
        if not dom:
            return None, "local: needs a domain path (e.g. local:MemDev)"
        return {"kind": "local", "domain": dom, "canon": f"local:{dom}"}, None
    head, _, rest = raw.partition("/")
    if head.casefold() == FAILURES_ROOT_NAME.casefold():
        if not layout.is_global:
            return None, "Failures family lives in the global layer only"
        segs, err = validate_category_path(f"{FAILURES_ROOT_NAME}/{rest}" if rest else FAILURES_ROOT_NAME)
        if err:
            return None, err
        if len(segs) < 2:
            return None, f"Failures target needs a topic: {FAILURES_ROOT_NAME}/<主題>"
        try:
            topics = failures_topics()
        except TaxonomyUnavailable as e:
            return None, f"taxonomy.json unavailable: {e}"
        if segs[1] not in topics:
            return None, f"unknown Failures topic {segs[1]!r}; valid: {', '.join(topics)}"
        return {"kind": "failures", "segs": segs, "dst_dir": layout.core_root.joinpath(*segs),
                "canon": "/".join(segs)}, None
    try:
        lv1 = match_lv1(head)
        cats = core_categories()
    except TaxonomyUnavailable as e:
        return None, f"taxonomy.json unavailable: {e}"
    if lv1 is None:
        return None, f"unknown Lv1 {head!r}; valid: {', '.join(cats)} (slug/alias accepted)"
    full = lv1 if not rest else f"{lv1}/{rest}"
    # 先沙盒（保留名／字元集任一段不合就拒，不靜默截斷），再把 Lv2 對既有兄弟／taxonomy 宣告的
    # sub snap（'vcs/git' → '版控/Git'），snap 結果再驗一次。
    segs, err = validate_category_path(full, allow_first=())
    if err or not segs:
        return None, err or f"category path invalid: {full!r}"
    if rest:
        full = normalize_domain_path("/".join(segs), known_category_paths(layout.memory_dir))
    segs, err = validate_category_path(full, allow_first=())
    if err or not segs or segs[0] != lv1:
        return None, err or f"category path invalid: {full!r}"
    return {"kind": "core", "segs": segs, "dst_dir": layout.core_root.joinpath(*segs),
            "canon": "/".join(segs)}, None


# ─── 計畫 ────────────────────────────────────────────────────────────────────


def build_plan(layout: Layout, atoms_map: Dict[str, str], refs: Dict[str, str]) -> Dict[str, Any]:
    data = load_atom_index_json(layout.memory_dir)
    by_name = {a.get("name"): a for a in data.get("atoms", [])}
    items: List[Dict[str, Any]] = []
    errors: List[str] = []
    dst_seen: Dict[str, str] = {}

    for slug, target in atoms_map.items():
        entry = by_name.get(slug)
        if not entry:
            errors.append(f"{slug}: not in index")
            continue
        cur_rel = entry.get("path") or ""
        src = layout.claude_root / cur_rel
        if not cur_rel or not src.exists():
            errors.append(f"{slug}: index path missing on disk: {cur_rel!r}")
            continue
        resolved, err = resolve_target(target, layout)
        if err:
            errors.append(f"{slug}: {err}")
            continue
        sidecar = access_sidecar_path(src).exists()
        if resolved["kind"] == "local":
            dom = resolved["domain"]
            if is_local_realm_path(cur_rel):
                cur_dom = "/".join(local_realm_path_segments(cur_rel))
                if cur_dom.casefold() == dom.casefold():
                    items.append({"action": "noop", "slug": slug, "from": cur_rel, "to": cur_rel,
                                  "target": resolved["canon"]})
                else:
                    errors.append(f"{slug}: already local at {cur_dom!r}, target {dom!r} "
                                  "(re-home with tools/atom-set-realm.py)")
                continue
            items.append({"action": "realm", "slug": slug, "from": cur_rel, "domain": dom,
                          "target": resolved["canon"], "sidecar": sidecar})
            continue
        dst = Path(resolved["dst_dir"]) / f"{slug}.md"
        new_rel = layout.rel(dst)
        if new_rel == cur_rel:
            items.append({"action": "noop", "slug": slug, "from": cur_rel, "to": new_rel,
                          "target": resolved["canon"]})
            continue
        key = new_rel.casefold()
        if key in dst_seen:
            errors.append(f"{slug}: target collides (case-insensitive) with {dst_seen[key]}: {new_rel}")
            continue
        dst_seen[key] = slug
        if dst.exists():
            errors.append(f"{slug}: target already exists: {new_rel}")
            continue
        items.append({"action": "move", "slug": slug, "from": cur_rel, "to": new_rel,
                      "target": resolved["canon"], "sidecar": sidecar,
                      "scope": entry.get("scope", "global")})

    # 未列入對映的根下散檔／舊址失敗家族：不搬，但要浮出（遷移完成的定義＝這裡是空的）
    unmapped: List[str] = []
    for name, a in by_name.items():
        if name in atoms_map:
            continue
        p = a.get("path") or ""
        if layout.is_flat(p) or (layout.is_global and is_legacy_failures_path(p)):
            unmapped.append(name)

    ref_items: List[Dict[str, Any]] = []
    for src_rel, dst_rel in refs.items():
        ref_items.append({"from": src_rel, "to": dst_rel,
                          "exists": (layout.claude_root / src_rel).exists(),
                          "cmd": f'git mv "{src_rel}" "{dst_rel}"'})

    counts = {"move": 0, "realm": 0, "noop": 0}
    for it in items:
        counts[it["action"]] = counts.get(it["action"], 0) + 1
    return {
        "memory_dir": str(layout.memory_dir), "layer": "global" if layout.is_global else "project",
        "counts": {**counts, "error": len(errors), "unmapped": len(unmapped),
                   "reference_git_mv": len(ref_items)},
        "items": items, "unmapped": sorted(unmapped), "reference_git_mv": ref_items,
        "errors": errors,
    }


def propose_map(layout: Layout) -> Dict[str, Any]:
    """無 --map 時的草案：taxonomy 詞庫計分（name 權重高、trigger 低）；0 分不猜（留 unmapped）。"""
    data = load_atom_index_json(layout.memory_dir)
    proposals: Dict[str, str] = {}
    undecided: List[str] = []
    try:
        core_pairs = category_term_pairs("core")
        fail_pairs = category_term_pairs("failures")
    except TaxonomyUnavailable as e:
        return {"error": f"taxonomy.json unavailable: {e}"}
    for a in data.get("atoms", []):
        name, p = a.get("name") or "", a.get("path") or ""
        if not (layout.is_flat(p) or (layout.is_global and is_legacy_failures_path(p))):
            continue
        in_failures = layout.is_global and (is_in_failures_path(p) or name.startswith("feedback-"))
        scores, _matched = score_by_lexicon(name, a.get("triggers") or [],
                                            fail_pairs if in_failures else core_pairs)
        if not scores:
            undecided.append(name)
            continue
        best = max(scores.items(), key=lambda kv: kv[1])[0]
        proposals[name] = f"{FAILURES_ROOT_NAME}/{best}" if in_failures else best
    return {"proposed": True, "atoms": proposals, "undecided": sorted(undecided)}


# ─── 執行 ────────────────────────────────────────────────────────────────────


def _load_set_realm():
    spec = importlib.util.spec_from_file_location("atom_set_realm", _SET_REALM_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_SET_REALM_FILE}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _entry(layout: Layout, slug: str) -> Dict[str, Any]:
    for a in load_atom_index_json(layout.memory_dir).get("atoms", []):
        if a.get("name") == slug:
            return a
    raise RuntimeError(f"{slug}: vanished from index")


def _move_and_reindex(layout: Layout, slug: str, from_rel: str, to_rel: str, op: str) -> bool:
    """實體搬（.md + sidecar 原子）→ index path 改寫（失敗 rollback 實體）→ audit → 清空目錄。回 sidecar 是否搬了。"""
    entry = _entry(layout, slug)
    src = layout.claude_root / from_rel
    dst = layout.claude_root / to_rel
    sidecar_moved = move_atom_pair(src, dst)
    res = write_index(layout.memory_dir, slug, to_rel, entry.get("triggers") or [], _SOURCE,
                      scope=entry.get("scope"))
    if not res.ok:
        try:
            dst.rename(src)
            if sidecar_moved:
                access_sidecar_path(dst).rename(access_sidecar_path(src))
        except OSError:
            pass
        raise RuntimeError(f"{slug}: index update failed ({res.error}); physical move rolled back")
    _audit_log({"audit_id": _gen_audit_id(), "ts": _now(), "op": op, "source": _SOURCE,
                "slug": slug, "from_path": from_rel, "to_path": to_rel,
                "sidecar_moved": sidecar_moved, "index_dir": str(layout.memory_dir)})
    prune_empty_parents(src.parent, layout.prune_stop(src))
    return sidecar_moved


def _write_undo(path: Path, layout: Layout, entries: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"created": _now(), "source": _SOURCE, "memory_dir": str(layout.memory_dir),
               "entries": entries}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_plan(layout: Layout, plan: Dict[str, Any], undo_file: Path) -> Dict[str, Any]:
    done: List[Dict[str, Any]] = []
    failures: List[str] = []
    set_realm_mod = None
    for it in plan["items"]:
        if it["action"] == "noop":
            continue
        try:
            if it["action"] == "move":
                moved = _move_and_reindex(layout, it["slug"], it["from"], it["to"], "categorize_move")
                done.append({"action": "move", "slug": it["slug"], "from": it["from"], "to": it["to"],
                             "sidecar_moved": moved})
            else:  # realm → atom-set-realm（_AIDocs/_atoms/ path 唯一寫者）
                if set_realm_mod is None:
                    set_realm_mod = _load_set_realm()
                res = set_realm_mod.set_realm(it["slug"], domain=it["domain"])
                if not res.get("ok"):
                    raise RuntimeError(f"{it['slug']}: atom-set-realm failed: {res.get('error')}")
                if res.get("noop"):
                    continue
                _audit_log({"audit_id": _gen_audit_id(), "ts": _now(), "op": "categorize_move",
                            "source": _SOURCE, "slug": it["slug"], "from_path": res["from"],
                            "to_path": res["to"], "sidecar_moved": res.get("sidecar_moved"),
                            "via": "tool:atom-set-realm"})
                done.append({"action": "realm", "slug": it["slug"], "from": res["from"], "to": res["to"],
                             "sidecar_moved": res.get("sidecar_moved")})
        except (OSError, RuntimeError) as e:
            failures.append(str(e))
            break  # 半途失敗：停、落 undo（已做的可反向）、回報
    if done:
        _write_undo(undo_file, layout, done)
    return {"applied": len(done), "failed": failures,
            "undo_file": str(undo_file) if done else None,
            "validate_errors": validate_index(layout.memory_dir)}


def undo_apply(layout: Layout, undo_payload: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    entries = list(undo_payload.get("entries") or [])
    reverted: List[Dict[str, Any]] = []
    failures: List[str] = []
    for e in reversed(entries):
        slug, cur_rel, back_rel = e["slug"], e["to"], e["from"]
        src = layout.claude_root / cur_rel
        if not src.exists():
            failures.append(f"{slug}: expected at {cur_rel} (not found; already reverted?)")
            continue
        if (layout.claude_root / back_rel).exists():
            failures.append(f"{slug}: original path occupied: {back_rel}")
            continue
        if dry_run:
            reverted.append({"slug": slug, "from": cur_rel, "to": back_rel, "dry_run": True})
            continue
        try:
            moved = _move_and_reindex(layout, slug, cur_rel, back_rel, "categorize_undo")
            reverted.append({"slug": slug, "from": cur_rel, "to": back_rel, "sidecar_moved": moved})
        except (OSError, RuntimeError) as ex:
            failures.append(str(ex))
            break
    return {"reverted": len(reverted), "items": reverted, "failed": failures,
            "validate_errors": [] if dry_run else validate_index(layout.memory_dir)}


# ─── CLI ──────────────────────────────────────────────────────────────────────


def _emit(obj: Dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_plan(args) -> int:
    layout = Layout(args.memory_dir)
    if not args.map:
        _emit({"mode": "PLAN(proposal)", **propose_map(layout)})
        return 0
    atoms_map, refs = load_map(Path(args.map))
    plan = build_plan(layout, atoms_map, refs)
    _emit({"mode": "PLAN", "map": str(args.map), **plan})
    return 1 if plan["errors"] else 0


def cmd_apply(args) -> int:
    layout = Layout(args.memory_dir)
    atoms_map, refs = load_map(Path(args.map))
    plan = build_plan(layout, atoms_map, refs)
    if plan["errors"]:
        _emit({"mode": "APPLY-REFUSED", "reason": "plan has errors", **plan})
        return 1
    if args.dry_run:
        _emit({"mode": "APPLY-DRY-RUN", **plan})
        return 0
    undo_file = Path(args.undo_file) if args.undo_file else (
        (DEFAULT_UNDO_DIR if layout.is_global else layout.memory_dir / "_staging")
        / f"categorize-{_ts_slug()}.undo.json")
    result = apply_plan(layout, plan, undo_file)
    _emit({"mode": "APPLIED", "counts": plan["counts"], **result,
           "reference_git_mv": plan["reference_git_mv"]})
    return 2 if (result["failed"] or result["validate_errors"]) else 0


def cmd_undo(args) -> int:
    payload = json.loads(Path(args.undo_file).read_text(encoding="utf-8-sig"))
    layout = Layout(Path(args.memory_dir) if args.memory_dir_given else Path(payload["memory_dir"]))
    result = undo_apply(layout, payload, args.dry_run)
    _emit({"mode": "UNDO-DRY-RUN" if args.dry_run else "UNDONE", "undo_file": str(args.undo_file), **result})
    return 2 if (result["failed"] or result["validate_errors"]) else 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Batch-categorize atoms into memory/<範疇>/ (index = SoT)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def _common(sp, need_map: bool):
        sp.add_argument("--map", required=need_map, default=None, help="plans/core-categories.json")
        sp.add_argument("--memory-dir", type=Path, default=GLOBAL_MEMORY_DIR,
                        help="memory root holding _atom_index.json (project: <proj>/.claude/memory)")
        sp.add_argument("--dry-run", action="store_true")

    sp = sub.add_parser("plan", help="validate the map against the index; no changes")
    _common(sp, need_map=False)
    sp.set_defaults(func=cmd_plan)

    sp = sub.add_parser("apply", help="move atoms per map (+ .access.json), rewrite index, write undo.json")
    _common(sp, need_map=True)
    sp.add_argument("--undo-file", default=None)
    sp.set_defaults(func=cmd_apply)

    sp = sub.add_parser("undo", help="revert an apply from its undo.json")
    sp.add_argument("--undo-file", required=True)
    sp.add_argument("--memory-dir", type=Path, default=None)
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_undo)

    args = p.parse_args(argv)
    if args.cmd == "undo":
        args.memory_dir_given = args.memory_dir is not None
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
