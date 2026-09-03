"""atom_index_json.py — _atom_index.json single source of truth.

Schema:
    {
      "version": "1.0",
      "atoms": [
        {"name": str, "path": str, "triggers": [str], "scope": str, "last_used": str?}
      ]
    }

責任：
- load_atom_index_json(mem_dir) -> {atoms: [...]}
- upsert_atom(mem_dir, name, path, triggers, scope) -> bool
- delete_atom(mem_dir, name) -> bool
- regenerate_atom_index_md(mem_dir) -> 同步重生 _ATOM_INDEX.md 作為人類可讀 deprecated view

舊 _ATOM_INDEX.md 仍由本模組生成（保留人類可讀視圖過渡期），
但唯一機器源是 JSON；hooks/MCP/lib 統一走本模組。

讀取容錯：JSON 不存在或損毀 → 回 {"atoms": []}（caller 自行 fallback _ATOM_INDEX.md）。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


ATOM_INDEX_JSON = "_atom_index.json"
ATOM_INDEX_MD = "_ATOM_INDEX.md"
SCHEMA_VERSION = "1.0"
TRIGGER_MAX_LEN = 30  # validate_index 與 write funnel 共用（寫入當下即驗，不留到後續操作才爆）


def find_index_dir(path: Path) -> Optional[Path]:
    """從 path 往上找最近含 _atom_index.json 的祖先 = index root（memory root）。

    單一來源：edit_metadata（專案層 atom 的索引歸屬）與 tools/atom-move.py 共用，
    取代各處硬編 ~/.claude 或自刻上溯。找不到回 None。
    """
    try:
        cur = Path(path).resolve(strict=False)
    except OSError:
        cur = Path(path)
    while True:
        if (cur / ATOM_INDEX_JSON).exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def _write_text_lf(path: Path, content: str) -> None:
    """tmp + rename 落檔，內容一律 LF（與 atom_io.write_text_lf 同規則；本模組只依賴 stdlib 故自帶一份）。

    索引檔每次 upsert 都整檔 regen；newline="" 關掉平台轉譯，Windows 才不會把 \\n 翻成 \\r\\n。
    tmp 後綴帶 PID+TID：索引檔全系統共用，併發 session upsert 不互踩。
    """
    body = content.replace("\r\n", "\n").replace("\r", "\n")
    import threading as _threading
    tmp = path.with_suffix(
        f"{path.suffix}.tmp.{os.getpid()}.{_threading.get_ident()}"
    )
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(body)
        tmp.replace(path)
    except OSError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def _empty_index() -> Dict[str, Any]:
    return {"version": SCHEMA_VERSION, "atoms": []}


def load_atom_index_json(mem_dir: Path) -> Dict[str, Any]:
    """Load _atom_index.json; on missing/corrupt return empty."""
    p = mem_dir / ATOM_INDEX_JSON
    if not p.exists():
        return _empty_index()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("atoms"), list):
            return _empty_index()
        return data
    except (OSError, json.JSONDecodeError):
        return _empty_index()


def save_atom_index_json(mem_dir: Path, data: Dict[str, Any]) -> None:
    p = mem_dir / ATOM_INDEX_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    _write_text_lf(
        p, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)
    )


def dedup_triggers(triggers, *, lower: bool = False) -> List[str]:
    """strip + 去空 + 大小寫不敏感保序去重（首見者勝）；lower=True 時輸出一律小寫。

    讀寫兩側共用：索引若同時含 "linemate" 與 "LineMate"，讀取側 .lower() 後會變成
    兩顆相同 trigger，count_trigger_hits 對單字回 2 而灌水越過跨專案 >=2 門檻。
    """
    out: List[str] = []
    seen = set()
    for t in triggers or []:
        if not isinstance(t, str):
            continue
        t = t.strip()
        if not t:
            continue
        key = t.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(t.lower() if lower else t)
    return out


def upsert_atom(
    mem_dir: Path,
    name: str,
    path: str,
    triggers: List[str],
    scope: str = "global",
    last_used: Optional[str] = None,
) -> bool:
    """Insert or update an atom entry. Returns True if changed."""
    data = load_atom_index_json(mem_dir)
    atoms = data["atoms"]
    triggers = dedup_triggers(triggers)
    new_entry: Dict[str, Any] = {
        "name": name,
        "path": path,
        "triggers": triggers,
        "scope": scope,
    }
    if last_used:
        new_entry["last_used"] = last_used

    for i, a in enumerate(atoms):
        if a.get("name") == name:
            if a == new_entry:
                return False
            atoms[i] = new_entry
            save_atom_index_json(mem_dir, data)
            regenerate_atom_index_md(mem_dir)
            return True

    atoms.append(new_entry)
    save_atom_index_json(mem_dir, data)
    regenerate_atom_index_md(mem_dir)
    return True


def delete_atom(mem_dir: Path, name: str) -> bool:
    data = load_atom_index_json(mem_dir)
    atoms = data["atoms"]
    before = len(atoms)
    data["atoms"] = [a for a in atoms if a.get("name") != name]
    if len(data["atoms"]) == before:
        return False
    save_atom_index_json(mem_dir, data)
    regenerate_atom_index_md(mem_dir)
    return True


def regenerate_atom_index_md(mem_dir: Path) -> None:
    """Regenerate _ATOM_INDEX.md from JSON (human-readable mirror, deprecated)."""
    data = load_atom_index_json(mem_dir)
    lines = [
        "# Atom Trigger Index — Global",
        "",
        "> **Deprecated mirror.** Machine source: `_atom_index.json`.",
        "> 本檔由 lib/atom_index_json.py 自動生成；勿手改。",
        "",
        "| Atom | Path | Trigger | Scope |",
        "|------|------|---------|-------|",
    ]
    for a in data["atoms"]:
        name = a.get("name", "")
        path = a.get("path", "")
        triggers = ", ".join(a.get("triggers", []))
        scope = a.get("scope", "global")
        lines.append(f"| {name} | {path} | {triggers} | {scope} |")
    lines.append("")

    md = mem_dir / ATOM_INDEX_MD
    _write_text_lf(md, "\n".join(lines))


# ─── Migration: parse legacy _ATOM_INDEX.md → JSON ──────────────────────────


_TABLE_HEADER_RE = re.compile(r"^\|\s*Atom\s*\|", re.IGNORECASE)


def parse_legacy_atom_index_md(md_path: Path) -> List[Dict[str, Any]]:
    """One-shot migration helper: parse _ATOM_INDEX.md table → atom dicts."""
    if not md_path.exists():
        return []
    try:
        text = md_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []

    atoms: List[Dict[str, Any]] = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if not in_table:
            if _TABLE_HEADER_RE.match(stripped):
                in_table = True
            continue
        if stripped.startswith("|---") or stripped.startswith("| ---"):
            continue
        if not stripped.startswith("|"):
            if not stripped:
                continue
            break
        cells = [c.strip() for c in stripped.split("|") if c.strip()]
        if len(cells) < 3:
            continue
        name = cells[0]
        path = cells[1]
        triggers = dedup_triggers(cells[2].split(","))
        scope = cells[3] if len(cells) >= 4 else "global"
        atoms.append({
            "name": name,
            "path": path,
            "triggers": triggers,
            "scope": scope,
        })
    return atoms


def migrate_md_to_json(mem_dir: Path, *, overwrite: bool = False) -> Dict[str, Any]:
    """Build _atom_index.json from existing _ATOM_INDEX.md. Idempotent."""
    json_path = mem_dir / ATOM_INDEX_JSON
    if json_path.exists() and not overwrite:
        return load_atom_index_json(mem_dir)
    md_path = mem_dir / ATOM_INDEX_MD
    atoms = parse_legacy_atom_index_md(md_path)
    data = {"version": SCHEMA_VERSION, "atoms": atoms}
    save_atom_index_json(mem_dir, data)
    return data


def validate_index(mem_dir: Path) -> List[str]:
    """Return list of validation errors (empty = ok). Used by pre-commit hook."""
    errors: List[str] = []
    json_path = mem_dir / ATOM_INDEX_JSON
    if not json_path.exists():
        errors.append(f"missing: {json_path}")
        return errors
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        errors.append(f"json parse error: {e}")
        return errors

    if not isinstance(data, dict):
        errors.append("root is not object")
        return errors
    if data.get("version") != SCHEMA_VERSION:
        errors.append(f"version mismatch: expected {SCHEMA_VERSION}, got {data.get('version')!r}")
    atoms = data.get("atoms")
    if not isinstance(atoms, list):
        errors.append("atoms is not a list")
        return errors

    seen_names = set()
    seen_paths = set()
    for i, a in enumerate(atoms):
        if not isinstance(a, dict):
            errors.append(f"atoms[{i}] is not object")
            continue
        for k in ("name", "path", "triggers", "scope"):
            if k not in a:
                errors.append(f"atoms[{i}] missing key: {k}")
        name = a.get("name")
        if name in seen_names:
            errors.append(f"duplicate name: {name}")
        seen_names.add(name)
        path = a.get("path")
        if path in seen_paths:
            errors.append(f"duplicate path: {path}")
        seen_paths.add(path)
        if not isinstance(a.get("triggers"), list):
            errors.append(f"atoms[{i}] triggers not list")
        else:
            for t in a["triggers"]:
                if len(t) > TRIGGER_MAX_LEN:
                    errors.append(f"trigger too long (>{TRIGGER_MAX_LEN}): {name}: {t!r}")
    return errors


# ─── For wg_atoms compatibility (AtomEntry tuple format) ────────────────────


def to_atom_entries(data: Dict[str, Any]) -> List[tuple]:
    """Convert JSON atoms → list of (name, path, triggers_lowercase) tuples.

    Matches wg_atoms.AtomEntry contract.
    """
    entries = []
    for a in data.get("atoms", []):
        name = a.get("name", "")
        path = a.get("path", "")
        triggers = dedup_triggers(a.get("triggers", []), lower=True)
        entries.append((name, path, triggers))
    return entries
