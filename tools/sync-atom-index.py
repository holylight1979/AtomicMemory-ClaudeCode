"""
sync-atom-index.py — Atom frontmatter Trigger ↔ _atom_index.json 同步工具

索引模型：
- `_atom_index.json` 為機器真相源（schema v1.0；lib.atom_index_json）
- `_ATOM_INDEX.md` 為自動生成 mirror（lib.atom_index_json.regenerate_atom_index_md）
- frontmatter Trigger 為註記，drift 時以 JSON 為主對齊
- 配對 key 為 rel_path，避免短名 alias 與 atom 檔名不符的偽陽性

V4→V5 變更：原 parse_atom_index 讀 `_ATOM_INDEX.md` table；
V5 改讀 `_atom_index.json`，append 走 `lib.atom_index_json.upsert_atom`。

模式：
  (default)              dry-run，輸出 drift JSON 報告，drift 則 exit 1
  --fix                  以 _atom_index.json 內容覆蓋 atom 檔 frontmatter Trigger
  --add-from-frontmatter 把 frontmatter 有 Trigger 但 _atom_index.json 缺的 atom 補進索引
  --check                同 default，僅報 exit code（PreCommit 用，輸出最小化）

範圍判定（哪些檔算 atom）：
  - 路徑在 memory/ 下且為 .md
  - 有 frontmatter Trigger 欄位
  - 排除：_reference/, _archived/, _pending_review/, _staging/, templates/, wisdom/, _drafts/, episodic/
  - 排除：MEMORY.md, _ATOM_INDEX.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.atom_index_json import (  # noqa: E402
    dedup_triggers,
    delete_atom,
    load_atom_index_json,
    upsert_atom,
)
from lib.atom_locations import (  # noqa: E402  V5+ 多根掃描 + Failures filter
    atom_search_roots,
    iter_atom_files_multi,
    scope_from_index_path,
)
from lib.atom_spec import is_atom_file  # noqa: E402
from lib.atom_io import write_raw  # noqa: E402  走 funnel：EOL-preserving + audit（杜絕 bypass 裸寫）

MEMORY_DIR = Path.home() / ".claude" / "memory"
CLAUDE_ROOT = MEMORY_DIR.parent

EXCLUDED_DIR_PARTS = {"_reference", "_archived", "_pending_review", "_staging",
                      "templates", "wisdom", "_drafts", "episodic", "_distant", "_rejected"}
EXCLUDED_FILE_NAMES = {"MEMORY.md", "_ATOM_INDEX.md"}

TRIGGER_LINE_RE = re.compile(r"^- Trigger:\s*(.+)$", re.MULTILINE)
SCOPE_LINE_RE = re.compile(r"^- Scope:\s*(.+)$", re.MULTILINE)


@dataclass
class IndexRow:
    name: str
    path: str  # relative to ~/.claude
    triggers: List[str]
    scope: str = "global"


@dataclass
class AtomFile:
    name: str  # slug from filename
    path: Path  # absolute
    rel_path: str  # relative to ~/.claude (forward slash)
    triggers: List[str]
    scope: str


@dataclass
class DriftReport:
    missing_in_index: List[Dict] = field(default_factory=list)
    missing_frontmatter: List[str] = field(default_factory=list)
    trigger_drift: List[Dict] = field(default_factory=list)
    orphan_index: List[str] = field(default_factory=list)
    scope_drift: List[Dict] = field(default_factory=list)

    def has_drift(self) -> bool:
        return any([self.missing_in_index, self.missing_frontmatter,
                    self.trigger_drift, self.orphan_index, self.scope_drift])

    def to_dict(self) -> Dict:
        return {
            "missing_in_index": self.missing_in_index,
            "missing_frontmatter": self.missing_frontmatter,
            "trigger_drift": self.trigger_drift,
            "orphan_index": self.orphan_index,
            "scope_drift": self.scope_drift,
            "has_drift": self.has_drift(),
        }


def is_excluded(p: Path, memory_dir: Path) -> bool:
    if p.name in EXCLUDED_FILE_NAMES:
        return True
    rel = p.relative_to(memory_dir)
    for part in rel.parts:
        if part in EXCLUDED_DIR_PARTS:
            return True
    return False


def parse_frontmatter_triggers(text: str) -> Optional[List[str]]:
    m = TRIGGER_LINE_RE.search(text)
    if not m:
        return None
    # 與索引寫入側同一把去重（大小寫不敏感保序），否則 detect_drift 會永久報 drift
    return dedup_triggers(m.group(1).split(","))


def parse_frontmatter_scope(text: str) -> str:
    m = SCOPE_LINE_RE.search(text)
    return m.group(1).strip() if m else "global"


def scan_atom_files(memory_dir: Path, claude_root: Path) -> Dict[str, AtomFile]:
    """Return dict keyed by rel_path (forward-slash).

    V5+: 走 lib.atom_locations.iter_atom_files_multi() 含 memory/ + _AIDocs/Failures/，
    Failures 內套 failures_atom_stems() 過濾參考文件。
    """
    out: Dict[str, AtomFile] = {}
    # 若 caller 指定非預設 memory_dir（例如測試），仍走單根；否則走多根 default
    if memory_dir.resolve() == MEMORY_DIR.resolve():
        files_iter = iter_atom_files_multi()
    else:
        # 專案層與全域同一套 atom 判定（SKIP_DIRS：_rejected/_drafts/episodic…；
        # personal/<u>/ 是 atom、personal/auto/<u>/ 候選不是）
        files_iter = (p for p in memory_dir.rglob("*.md") if is_atom_file(p, memory_dir))
    for md in files_iter:
        # memory 樹下仍用既有 excluded dir/file 過濾；Failures root iter_atom_files_multi 已過濾
        try:
            md.relative_to(memory_dir)
            if is_excluded(md, memory_dir):
                continue
        except ValueError:
            pass  # 不在 memory_dir 樹下（Failures atom）— 已由 iter_atom_files_multi filter
        try:
            text = md.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        triggers = parse_frontmatter_triggers(text)
        if triggers is None:
            continue
        scope = parse_frontmatter_scope(text)
        slug = md.stem
        rel = str(md.relative_to(claude_root)).replace("\\", "/")
        out[rel] = AtomFile(name=slug, path=md, rel_path=rel,
                            triggers=triggers, scope=scope)
    return out


def load_index_rows(memory_dir: Path) -> List[IndexRow]:
    """V5: 讀 _atom_index.json，回傳 IndexRow list（取代舊 _ATOM_INDEX.md table parser）."""
    data = load_atom_index_json(memory_dir)
    rows: List[IndexRow] = []
    for a in data.get("atoms", []):
        rows.append(IndexRow(
            name=a.get("name", ""),
            path=a.get("path", "").replace("\\", "/"),
            triggers=dedup_triggers(a.get("triggers", [])),
            scope=a.get("scope", "global"),
        ))
    return rows


def detect_drift(atoms_by_path: Dict[str, AtomFile],
                 index_rows: List[IndexRow],
                 claude_root: Path) -> DriftReport:
    rep = DriftReport()
    index_paths = {r.path for r in index_rows}

    for rel_path, atom in atoms_by_path.items():
        if rel_path not in index_paths:
            rep.missing_in_index.append({
                "atom": atom.name,
                "path": rel_path,
                "triggers": atom.triggers,
                "scope": atom.scope,
            })

    for row in index_rows:
        target = (claude_root / row.path) if row.path else None
        if not target or not target.exists():
            rep.orphan_index.append(row.name)
            continue
        atom = atoms_by_path.get(row.path)
        if atom is None:
            rep.missing_frontmatter.append(row.name)
            continue
        if sorted(atom.triggers) != sorted(row.triggers):  # 順序不算漂移，只看集合
            rep.trigger_drift.append({
                "atom": row.name,
                "path": row.path,
                "frontmatter": atom.triggers,
                "index": row.triggers,
                "frontmatter_extra": [t for t in atom.triggers if t not in row.triggers],
                "index_extra": [t for t in row.triggers if t not in atom.triggers],
            })
        if atom.scope != row.scope:
            rep.scope_drift.append({
                "atom": row.name,
                "frontmatter": atom.scope,
                "index": row.scope,
            })

    return rep


def fix_frontmatter_from_index(atoms_by_path: Dict[str, AtomFile],
                               index_rows: List[IndexRow]) -> List[str]:
    changed: List[str] = []
    for row in index_rows:
        atom = atoms_by_path.get(row.path)
        if atom is None:
            continue
        if atom.triggers == row.triggers:
            continue
        new_line = f"- Trigger: {', '.join(row.triggers)}"
        text = atom.path.read_text(encoding="utf-8-sig")
        new_text, n = TRIGGER_LINE_RE.subn(new_line, text, count=1)
        if n == 1 and new_text != text:
            # 走 funnel：EOL-preserving _atomic_write + audit log
            # （舊版裸 write_text 會在 Windows 翻整檔 EOL，且寫入不留 audit）
            write_raw(atom.path, new_text, source="tool:sync-atom-index", op="trigger-align")
            changed.append(atom.rel_path)
    return changed


def add_to_index_from_frontmatter(atoms_by_path: Dict[str, AtomFile],
                                  index_rows: List[IndexRow],
                                  memory_dir: Path) -> List[str]:
    """V5: 走 upsert_atom（JSON SoT，自動回寫 MD mirror）."""
    indexed = {r.path for r in index_rows}
    added: List[str] = []
    for rel_path, atom in atoms_by_path.items():
        if rel_path in indexed:
            continue
        ok = upsert_atom(
            memory_dir,
            name=atom.name,
            path=rel_path,
            triggers=atom.triggers,
            scope=atom.scope,
        )
        if ok:
            added.append(atom.name)
    return added


_SCOPE_HEADER_RE = re.compile(r"^- Scope:\s*(.+?)\s*$", re.MULTILINE)


def fix_index_scope_from_path(memory_dir: Path, claude_root: Path,
                              index_rows: List[IndexRow]) -> Dict[str, List[str]]:
    """索引 scope 以 path 為準回寫（讀取端同一套 scope_from_index_path），並清懸空條目。

    - 條目 path 指向不存在的檔 → delete_atom（懸空）
    - scope 欄 ≠ path 推導（personal/<u>/、roles/<r>/、其餘依層 global|shared）→ upsert 回正
      並把 .md 檔頭 `- Scope:` 對齊（走 write_raw funnel）
    這是寫入端曾漏傳 scope（預設 global）留下的固定修法；write_index 缺省已改由 path 推導，
    本旗標處理存量與未來任何旁路寫入。回 {"dangling_removed": [...], "scope_fixed": [...]}。"""
    layer = "global" if memory_dir.resolve() == MEMORY_DIR.resolve() else "shared"
    out = {"dangling_removed": [], "scope_fixed": []}
    out["path_repaired"] = []
    for row in index_rows:
        md = claude_root / row.path
        path = row.path
        if path and not md.exists():
            # 先找「只是搬了位置」的同名檔（跳過 skip 目錄）：找到 → 修 path；真的沒有 → 才算懸空
            found = [p for p in memory_dir.rglob(f"{row.name}.md") if is_atom_file(p, memory_dir)]
            if len(found) == 1:
                path = str(found[0].relative_to(claude_root)).replace("\\", "/")
                md = found[0]
                out["path_repaired"].append(f"{row.name}: {row.path} -> {path}")
            else:
                if delete_atom(memory_dir, row.name):
                    out["dangling_removed"].append(row.name)
                continue
        expected = scope_from_index_path(path, layer)
        if row.scope == expected and path == row.path:
            continue
        upsert_atom(memory_dir, name=row.name, path=path, triggers=row.triggers, scope=expected)
        if row.scope == expected:
            continue
        try:
            text = md.read_text(encoding="utf-8-sig")
            m = _SCOPE_HEADER_RE.search(text)
            if m and m.group(1) != expected:
                wr = write_raw(md, text[:m.start()] + f"- Scope: {expected}" + text[m.end():],
                               source="tool:sync-atom-index", op="fix_scope_from_path")
                if not getattr(wr, "ok", False):
                    # write_raw 對未列舉 source／其他失敗回 ok=False 不 raise：浮出、不吞
                    print(f"[fix-scope] header not rewritten for {row.name}: {getattr(wr, 'error', '')}",
                          file=sys.stderr)
        except (OSError, UnicodeDecodeError):
            pass
        out["scope_fixed"].append(f"{row.name}: {row.scope} -> {expected}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="V5 atom index sync (JSON SoT).")
    parser.add_argument("--fix", action="store_true",
                        help="overwrite frontmatter Trigger from _atom_index.json")
    parser.add_argument("--add-from-frontmatter", action="store_true",
                        help="append atoms with frontmatter Trigger but missing from _atom_index.json")
    parser.add_argument("--fix-scope-from-path", action="store_true",
                        help="rewrite index scope from path (personal/roles/layer), drop dangling entries, align .md Scope header")
    parser.add_argument("--check", action="store_true",
                        help="quiet drift check (exit 1 if drift, for PreCommit)")
    parser.add_argument("--memory-dir", type=Path, default=MEMORY_DIR)
    parser.add_argument("--all-projects", action="store_true",
                        help="apply to every registered project memory dir (hooks/wg_core.discover_all_project_memory_dirs) instead of --memory-dir; exit 1 if any drift")
    args = parser.parse_args()

    if args.all_projects:
        return _run_all_projects(args)
    return _run_one(args.memory_dir, args)


def _project_memory_dirs() -> List[Tuple[str, Path]]:
    """與執行期同一套專案判定（hooks/wg_core.discover_all_project_memory_dirs）；只取有 JSON 索引者。"""
    hooks = CLAUDE_ROOT / "hooks"
    if str(hooks) not in sys.path:
        sys.path.insert(0, str(hooks))
    from wg_core import discover_all_project_memory_dirs  # noqa: E402
    return [(slug, mem) for slug, mem in discover_all_project_memory_dirs()
            if (mem / "_atom_index.json").exists()]


def _run_all_projects(args) -> int:
    """從 ~/.claude 一鍵掃全部登記專案：不必逐一開專案 session 叫 CC 整理。"""
    worst = 0
    summary: List[Dict] = []
    for slug, mem in _project_memory_dirs():
        rc = _run_one(mem, args, quiet=True, collector=summary, slug=slug)
        worst = max(worst, rc)
    if args.check:
        bad = [s for s in summary if s.get("has_drift")]
        if bad:
            print(json.dumps(bad, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1 if bad else 0
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return worst


def _run_one(memory_dir: Path, args, *, quiet: bool = False,
             collector: Optional[List[Dict]] = None, slug: str = "") -> int:
    claude_root = memory_dir.parent

    atoms_by_path = scan_atom_files(memory_dir, claude_root)
    index_rows = load_index_rows(memory_dir)

    actions_taken: List[str] = []

    if args.add_from_frontmatter:
        added = add_to_index_from_frontmatter(atoms_by_path, index_rows, memory_dir)
        if added:
            actions_taken.append(f"added to _atom_index.json: {added}")
            index_rows = load_index_rows(memory_dir)

    if args.fix_scope_from_path:
        res = fix_index_scope_from_path(memory_dir, claude_root, index_rows)
        if res["dangling_removed"] or res["scope_fixed"]:
            actions_taken.append(f"scope-from-path: {res}")
            index_rows = load_index_rows(memory_dir)
            atoms_by_path = scan_atom_files(memory_dir, claude_root)

    if args.fix:
        changed = fix_frontmatter_from_index(atoms_by_path, index_rows)
        if changed:
            actions_taken.append(f"frontmatter rewritten: {changed}")
            atoms_by_path = scan_atom_files(memory_dir, claude_root)

    rep = detect_drift(atoms_by_path, index_rows, claude_root)

    if collector is not None:
        entry = {"project": slug or memory_dir.parent.parent.name, "memory_dir": str(memory_dir),
                 "actions": actions_taken, "has_drift": rep.has_drift()}
        if rep.has_drift():
            entry["drift"] = rep.to_dict()
        collector.append(entry)
    if quiet:
        return 1 if rep.has_drift() else 0

    if args.check:
        if rep.has_drift():
            print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
            return 1
        return 0

    print(json.dumps({"actions": actions_taken, "drift": rep.to_dict()},
                     ensure_ascii=False, indent=2))
    return 1 if rep.has_drift() else 0


if __name__ == "__main__":
    sys.exit(main())
