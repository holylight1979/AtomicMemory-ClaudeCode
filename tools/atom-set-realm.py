#!/usr/bin/env python3
"""atom-set-realm.py — 把 atom 在 core ⇄ local 範疇間搬移（V5+ Realm 維度）

local atom 物理落 `_AIDocs/_atoms/<domain>/`，但**索引仍 global、Scope 仍 global**
（realm 與 scope 正交；realm 由 index path 前綴推導、不存欄位、不寫 frontmatter）。

為何不用 atom-move.py：
  - atom-move（V5 SoT-correct 重寫後）走 JSON SoT、同根搬移保留 scope，但**刻意拒絕**
    `_AIDocs/_atoms/` 下的 local atom（守門導回本工具）——realm 維度的 path 由本工具獨佔，
    防兩個寫者競爭翻轉 realm。
  - 本工具只搬實體檔（含 `.access.json` sidecar）+ 改 index path，Scope 一律不動（local 維持 global）。
  - 本工具為 `_AIDocs/_atoms/` index path 的**唯一寫者**（防 realm 翻轉）。

為何不需 reconcile 修反向連結：
  - global→local 是**純 path 搬移**（scope 不變、slug 不變）。Related 反向連結用 **slug**
    引用（非 path），slug 不變 → 連結不斷裂。`_ATOM_INDEX.md` mirror 由 upsert 自動重生。

可逆（memory-undo.py 只處理自動萃取 atom，不適用本搬移）：
  set <slug> --domain <World|Tools|MemDev>   core → local（memory/ → _AIDocs/_atoms/D/）
  set <slug> --to-core [--category Lv1[/Lv2]] local → core（落 memory/<範疇>/；範疇經 core_write_target；
                                              `Failures/<主題>` 走失敗家族；寫入閘開後 --category 必填）
  set <slug> ... --dry-run                    只算路徑、不落檔

sidecar 隨 .md 原子性搬：先搬 .md，sidecar 搬失敗則 rollback .md，
避免 confirmations/usefulness 計數歸零、晉升歷史飄移。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

CLAUDE_DIR = Path.home() / ".claude"
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lib.atom_locations import (  # noqa: E402
    CLAUDE_DIR as _CLAUDE_ROOT, FAILURES_ROOT_NAME,
    GLOBAL_MEMORY_DIR, LOCAL_ATOMS_DIR, LOCAL_ATOMS_REL, LOCAL_REALM_DOMAINS,
    core_write_target, enumerate_local_paths, failures_write_target,
    is_local_realm_path, normalize_domain_path, unclassified_error,
)
try:
    from lib.atom_taxonomy import core_categories as _core_categories  # noqa: E402
    from lib.atom_taxonomy import gate_enabled as _gate_enabled  # noqa: E402
except Exception:  # taxonomy 缺 → 閘視為關（flat 落點仍可用）
    _core_categories = None
    _gate_enabled = None
from lib.atom_io import write_index, _audit_log, _gen_audit_id  # noqa: E402
from lib.atom_index_json import load_atom_index_json  # noqa: E402
from lib.atom_access import (  # noqa: E402
    access_sidecar_path, move_atom_pair, prune_empty_parents,
)

_SOURCE = "tool:atom-set-realm"


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _find_index_entry(slug: str) -> Optional[Dict[str, Any]]:
    data = load_atom_index_json(GLOBAL_MEMORY_DIR)
    for a in data.get("atoms", []):
        if a.get("name") == slug:
            return a
    return None


def _locate_md(slug: str, index_path: str) -> Optional[Path]:
    """以 index path（相對 CLAUDE_DIR）優先定位；落空則 rglob memory/ + _AIDocs/_atoms/。"""
    if index_path:
        p = CLAUDE_DIR / index_path
        if p.exists():
            return p
    for root in (GLOBAL_MEMORY_DIR, LOCAL_ATOMS_DIR):
        if root.is_dir():
            for hit in root.rglob(f"{slug}.md"):
                return hit
    return None


# sidecar-aware 原子搬移 helper 已上移到 lib.atom_access（atom-move / atom-set-realm 共用單一來源）：
#   access_sidecar_path / move_atom_pair / prune_empty_parents（行為不變，prune 的 stop 改顯式傳 LOCAL_ATOMS_DIR）


def _read_scope(md: Path) -> str:
    """讀 .md frontmatter 的 Scope（搬移不改它，僅供回報/驗證 scope 仍 global）。"""
    try:
        text = md.read_text(encoding="utf-8-sig")
    except OSError:
        return "?"
    import re
    m = re.search(r"^-\s*Scope:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else "?"


# ─── Core operation ───────────────────────────────────────────────────────────


def _core_landing(slug: str, category: Optional[str]) -> tuple:
    """--to-core 的落點：(dst_md, new_rel, error)。

    `category` 給了 → 經 core_write_target（Lv1 閉合清單、別名 snap、Lv2 自由）落
    memory/<Lv1>[/<Lv2>]/；`Failures/<主題>` 走 failures_write_target。沒給 → 寫入閘
    （taxonomy.gate_enabled）開時拒、關時落 memory/ 根（遷移期相容）。
    """
    raw = (category or "").strip().replace("\\", "/")
    if raw:
        head, _, rest = raw.partition("/")
        if head.casefold() == FAILURES_ROOT_NAME.casefold():
            t = failures_write_target(rest or None)
        else:
            t, err = core_write_target(raw, allow_new=False)
            if err:
                return (None, "", err)
        dst = Path(t["dir"]) / f"{slug}.md"
        return (dst, dst.relative_to(_CLAUDE_ROOT).as_posix(), None)
    gate_on = False
    if _gate_enabled is not None:
        try:
            gate_on = bool(_gate_enabled())
        except Exception:
            gate_on = False
    if gate_on:
        cats: List[str] = []
        if _core_categories is not None:
            try:
                cats = list(_core_categories())
            except Exception:
                cats = []
        return (None, "", unclassified_error(category, cats) + " (pass --category <Lv1[/Lv2]>)")
    dst = GLOBAL_MEMORY_DIR / f"{slug}.md"
    return (dst, f"memory/{slug}.md", None)


def set_realm(
    slug: str, *, domain: Optional[str] = None, to_core: bool = False,
    dry_run: bool = False, category: Optional[str] = None,
) -> Dict[str, Any]:
    """把 atom 搬到 local（--domain）或搬回 core（--to_core [--category]）。

    回 {ok, ...}；no-op（已在目標 realm）回 {ok:True, noop:True}。
    Scope 一律保持原值（必為 global），不修改 .md 的 Scope 行。
    --to-core 的範疇落點見 _core_landing。
    """
    entry = _find_index_entry(slug)
    if not entry:
        return {"ok": False, "error": f"atom not in index: {slug}"}
    cur_path = entry.get("path", "")
    triggers: List[str] = entry.get("triggers", [])
    scope = entry.get("scope", "global")

    src_md = _locate_md(slug, cur_path)
    if not src_md or not src_md.exists():
        return {"ok": False, "error": f"atom .md not found on disk: {slug} (index path={cur_path})"}

    cur_is_local = is_local_realm_path(cur_path)

    if to_core:
        if not cur_is_local:
            return {"ok": True, "noop": True, "msg": f"{slug} already core ({cur_path})"}
        dst_md, new_rel, err = _core_landing(slug, category)
        if err:
            return {"ok": False, "error": err}
        new_realm = "core"
    else:
        if not (domain or "").strip():
            return {"ok": False, "error": "empty domain (need --domain <path> or --to-core)"}
        # 多段階層路徑：canon（對既有樹 snap）取代舊 allow-list 驗證
        dom_path = normalize_domain_path(domain, enumerate_local_paths())
        if cur_is_local:
            return {"ok": True, "noop": True, "msg": f"{slug} already local ({cur_path})"}
        segs = [s for s in dom_path.split("/") if s]
        dst_md = LOCAL_ATOMS_DIR.joinpath(*segs, f"{slug}.md")
        new_rel = f"{LOCAL_ATOMS_REL}/{dom_path}/{slug}.md"
        new_realm = "local"

    if dst_md.resolve() == src_md.resolve():
        return {"ok": True, "noop": True, "msg": f"{slug} already at {new_rel}"}
    if dst_md.exists():
        return {"ok": False, "error": f"target already exists: {dst_md}"}

    cur_scope_field = _read_scope(src_md)

    if dry_run:
        if to_core:  # core_write_target 已 mkdir 落點：dry-run 不留空目錄鏈
            prune_empty_parents(dst_md.parent, GLOBAL_MEMORY_DIR)
            try:
                dst_md.parent.rmdir()
            except OSError:
                pass
        return {
            "ok": True, "dry_run": True, "slug": slug,
            "from": cur_path, "to": new_rel,
            "from_realm": "local" if cur_is_local else "core", "to_realm": new_realm,
            "scope": scope, "scope_field": cur_scope_field,
            "sidecar": access_sidecar_path(src_md).exists(),
        }

    # 1) 實體檔 + sidecar 原子搬
    try:
        sidecar_moved = move_atom_pair(src_md, dst_md)
    except OSError as e:
        return {"ok": False, "error": f"move failed: {e}"}

    # 2) 更新 index path（write_index → upsert，scope 強制 global、走 audit）
    res = write_index(GLOBAL_MEMORY_DIR, slug, new_rel, triggers, _SOURCE)
    if not res.ok:
        # rollback：.md + sidecar 搬回原處
        try:
            dst_md.rename(src_md)
            if sidecar_moved:
                access_sidecar_path(dst_md).rename(access_sidecar_path(src_md))
        except OSError:
            pass
        return {"ok": False, "error": f"index update failed: {res.error}"}

    # 3) 專屬 realm_move audit（可追溯 + 反向 undo 依據）
    _audit_log({
        "audit_id": _gen_audit_id(),
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "op": "realm_move", "source": _SOURCE, "slug": slug,
        "from_path": cur_path, "to_path": new_rel,
        "from_realm": "local" if cur_is_local else "core", "to_realm": new_realm,
        "sidecar_moved": sidecar_moved,
    })

    # 4) 搬離 local 子夾後清空的階層目錄（best-effort，止於 LOCAL_ATOMS_DIR）
    if cur_is_local:
        prune_empty_parents(src_md.parent, LOCAL_ATOMS_DIR)

    return {
        "ok": True, "slug": slug, "from": cur_path, "to": new_rel,
        "to_realm": new_realm, "scope": scope, "scope_field": cur_scope_field,
        "sidecar_moved": sidecar_moved, "md_path": str(dst_md),
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description="Move atom between core ⇄ local realm")
    sub = p.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("set", help="Set an atom's realm (core→local with --domain, or --to-core)")
    st.add_argument("atom", help="atom slug")
    st.add_argument("--domain", default=None, help=f"local domain: {sorted(LOCAL_REALM_DOMAINS)}")
    st.add_argument("--to-core", action="store_true", help="reverse: move local atom back to core (undo)")
    st.add_argument("--category", default=None,
                    help="with --to-core: core category 'Lv1[/Lv2]' (taxonomy Lv1 / slug / alias; "
                         "'Failures/<主題>' for the failures family). Required once taxonomy.gate_enabled")
    st.add_argument("--dry-run", action="store_true")
    st.set_defaults(func=lambda a: set_realm(
        a.atom, domain=a.domain, to_core=a.to_core, dry_run=a.dry_run, category=a.category,
    ))

    args = p.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
