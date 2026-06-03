#!/usr/bin/env python3
"""atom-set-realm.py — 把 atom 在 core ⇄ local 範疇間搬移（V5+ Realm 維度）

local atom 物理落 `_AIDocs/_atoms/<domain>/`，但**索引仍 global、Scope 仍 global**
（realm 與 scope 正交；realm 由 index path 前綴推導、不存欄位、不寫 frontmatter）。

為何不用 atom-move.py 的 --from/--to：
  - atom-move 的 reconcile() 會 `is_global(target_root)==False` → 把 Scope 誤設成
    "project"、且往 `target_root/_ATOM_INDEX.md` 寫列（但 local 的索引在
    `memory/_atom_index.json`）。兩者皆破壞 local 的「scope=global、索引在 global」契約。
  - 故本工具自成一格：**只搬實體檔（含 `.access.json` sidecar）+ 改 index path，Scope 不動**。
  - 本工具為 `_AIDocs/_atoms/` index path 的**唯一寫者**（防 reconcile 誤重算翻轉 realm；計畫 R3）。

為何不需 reconcile 修反向連結：
  - global→local 是**純 path 搬移**（scope 不變、slug 不變）。Related 反向連結用 **slug**
    引用（非 path），slug 不變 → 連結不斷裂。`_ATOM_INDEX.md` mirror 由 upsert 自動重生。

可逆（計畫驗收 B#4「undo 演練」；memory-undo.py 只處理 V4.1 自動萃取，不適用本搬移）：
  set <slug> --domain <World|Tools|MemDev>   core → local（memory/ → _AIDocs/_atoms/D/）
  set <slug> --to-core                        local → core（反向搬回，即 undo）
  set <slug> ... --dry-run                    只算路徑、不落檔

sidecar 隨 .md 原子性搬（計畫必驗 #8）：先搬 .md，sidecar 搬失敗則 rollback .md，
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
    GLOBAL_MEMORY_DIR, LOCAL_ATOMS_DIR, LOCAL_ATOMS_REL, LOCAL_REALM_DOMAINS,
    is_local_realm_path,
)
from lib.atom_io import write_index, _audit_log, _gen_audit_id  # noqa: E402
from lib.atom_index_json import load_atom_index_json  # noqa: E402

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


def _access_path(md: Path) -> Path:
    """<atom>.md → <atom>.access.json（對拍 lib.atom_access._access_path）。"""
    return md.with_suffix(".access.json")


def _move_pair(src_md: Path, dst_md: Path) -> bool:
    """原子性搬 .md + .access.json sidecar。sidecar 搬失敗 → rollback .md 後 raise。

    回傳 sidecar 是否實際搬移（src 無 sidecar → False，非錯誤）。
    """
    dst_md.parent.mkdir(parents=True, exist_ok=True)
    src_access = _access_path(src_md)
    dst_access = _access_path(dst_md)
    src_md.rename(dst_md)
    if src_access.exists():
        try:
            src_access.rename(dst_access)
        except OSError:
            dst_md.rename(src_md)  # rollback：.md 先搬回，維持 .md+sidecar 同層
            raise
        return True
    return False


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


def set_realm(
    slug: str, *, domain: Optional[str] = None, to_core: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """把 atom 搬到 local（--domain）或搬回 core（--to_core）。

    回 {ok, ...}；no-op（已在目標 realm）回 {ok:True, noop:True}。
    Scope 一律保持原值（必為 global），不修改 .md 的 Scope 行。
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
        dst_md = GLOBAL_MEMORY_DIR / f"{slug}.md"
        new_rel = f"memory/{slug}.md"
        new_realm = "core"
    else:
        if domain not in LOCAL_REALM_DOMAINS:
            return {"ok": False,
                    "error": f"unknown domain {domain!r} (known: {sorted(LOCAL_REALM_DOMAINS)})"}
        if cur_is_local:
            return {"ok": True, "noop": True, "msg": f"{slug} already local ({cur_path})"}
        dst_md = LOCAL_ATOMS_DIR / domain / f"{slug}.md"
        new_rel = f"{LOCAL_ATOMS_REL}/{domain}/{slug}.md"
        new_realm = "local"

    if dst_md.resolve() == src_md.resolve():
        return {"ok": True, "noop": True, "msg": f"{slug} already at {new_rel}"}
    if dst_md.exists():
        return {"ok": False, "error": f"target already exists: {dst_md}"}

    cur_scope_field = _read_scope(src_md)

    if dry_run:
        return {
            "ok": True, "dry_run": True, "slug": slug,
            "from": cur_path, "to": new_rel,
            "from_realm": "local" if cur_is_local else "core", "to_realm": new_realm,
            "scope": scope, "scope_field": cur_scope_field,
            "sidecar": _access_path(src_md).exists(),
        }

    # 1) 實體檔 + sidecar 原子搬
    try:
        sidecar_moved = _move_pair(src_md, dst_md)
    except OSError as e:
        return {"ok": False, "error": f"move failed: {e}"}

    # 2) 更新 index path（write_index → upsert，scope 強制 global、走 audit）
    res = write_index(GLOBAL_MEMORY_DIR, slug, new_rel, triggers, _SOURCE)
    if not res.ok:
        # rollback：.md + sidecar 搬回原處
        try:
            dst_md.rename(src_md)
            if sidecar_moved:
                _access_path(dst_md).rename(_access_path(src_md))
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
    st.add_argument("--dry-run", action="store_true")
    st.set_defaults(func=lambda a: set_realm(
        a.atom, domain=a.domain, to_core=a.to_core, dry_run=a.dry_run,
    ))

    args = p.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
