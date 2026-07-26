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


def _write_text_preserving_eol(path: Path, content: str) -> None:
    """tmp + rename 落檔，byte-stable EOL（對拍 atom_io._atomic_write）。

    索引檔（_atom_index.json / _ATOM_INDEX.md）每次 upsert 都整檔 regen；若用
    Path.write_text 預設 newline=None，Windows 會把 \\n 全翻成 os.linesep，使既有
    CRLF 索引每次都整檔翻行尾（reformat blast 同源）。偵測既有檔行尾原樣套回，
    newline="" 關平台轉譯——既有行 byte-stable、僅真正變動的列進 diff。
    """
    try:
        raw = path.read_bytes()
        eol = "\r\n" if b"\r\n" in raw else ("\n" if b"\n" in raw else os.linesep)
    except OSError:
        eol = os.linesep
    body = content.replace("\r\n", "\n").replace("\r", "\n")
    if eol != "\n":
        body = body.replace("\n", eol)
    # tmp 後綴帶 PID+TID 唯一化（仿 atom_access._write_raw）：索引檔為全系統共用，
    # 固定 ".tmp" 在併發 session upsert 時互踩（truncate 競態 → 半空索引）。
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
    _write_text_preserving_eol(
        p, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)
    )


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
    triggers = [t.strip() for t in triggers if t and t.strip()]
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
    _write_text_preserving_eol(md, "\n".join(lines))


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
        triggers = [t.strip() for t in cells[2].split(",") if t.strip()]
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
                if len(t) > 30:
                    errors.append(f"trigger too long (>30): {name}: {t!r}")
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
        triggers = [t.lower() for t in a.get("triggers", [])]
        entries.append((name, path, triggers))
    return entries
