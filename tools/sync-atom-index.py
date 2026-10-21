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
  --add-from-frontmatter 把 frontmatter 有 Trigger 但 _atom_index.json 缺的 atom 補進索引（連 Depends 一起）
  --sync-depends         frontmatter 有 `- Depends:` 行的 atom，把條目寫進索引 depends（frontmatter 為真相；
                         沒有該行的存量不碰、--check 也不對它們報漂移）
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
from lib.atom_spec import find_aka_line, find_entry_line, find_related_line, split_related  # noqa: E402
from lib.atom_index_json import (  # noqa: E402
    SCHEMA_VERSION,
    apply_upsert,
    atom_index_md_stale,
    dedup_triggers,
    delete_atom,
    load_atom_index_json,
    save_index_with_mirror,
    upsert_atom,
)
from lib.atom_locations import (  # noqa: E402  V5+ 多根掃描 + Failures filter
    atom_search_roots,
    iter_atom_files_multi,
    scope_from_index_path,
)
from lib.atom_spec import is_atom_file  # noqa: E402
from lib.atom_io import write_raw  # noqa: E402  走 funnel：EOL-preserving + audit（杜絕 bypass 裸寫）

from lib.project_root import claude_data_dir  # noqa: E402

MEMORY_DIR = claude_data_dir() / "memory"   # 使用者資料根（WG_CLAUDE_DIR 或 ~/.claude），和 hooks 同一支算法

EXCLUDED_DIR_PARTS = {"_reference", "_archived", "_pending_review", "_staging",
                      "templates", "wisdom", "_drafts", "episodic", "_distant", "_rejected"}
EXCLUDED_FILE_NAMES = {"MEMORY.md", "_ATOM_INDEX.md"}

TRIGGER_LINE_RE = re.compile(r"^- Trigger:\s*(.+)$", re.MULTILINE)
SCOPE_LINE_RE = re.compile(r"^- Scope:\s*(.+)$", re.MULTILINE)
# [ \t]* 不跨行、(.*) 收空值：空的 `- Depends:` 行＝有行但清空（[]），不能把下一行吃成依賴
DEPENDS_LINE_RE = re.compile(r"^- Depends:[ \t]*(.*)$", re.MULTILINE)


@dataclass
class IndexRow:
    name: str
    path: str  # relative to ~/.claude
    triggers: List[str]
    scope: str = "global"
    depends: Optional[List[str]] = None   # None＝索引條目沒有 depends 鍵
    related: List[str] = field(default_factory=list)
    aka: List[str] = field(default_factory=list)
    entry: List[str] = field(default_factory=list)


@dataclass
class AtomFile:
    name: str  # slug from filename
    path: Path  # absolute
    rel_path: str  # relative to ~/.claude (forward slash)
    triggers: List[str]
    scope: str
    depends: Optional[List[str]] = None   # None＝frontmatter 沒有 Depends 行（存量）；[]／清單＝有行
    related: List[str] = field(default_factory=list)  # 作者寫的正向連結；反向由注入端反轉，不存檔
    aka: List[str] = field(default_factory=list)      # 用過的舊檔名；連結以檔名為鍵，改名靠它讓舊連結續存
    entry: List[str] = field(default_factory=list)    # 是哪幾個切入點的判準卡（workflow/entrypoints.json 的代號）


@dataclass
class DriftReport:
    missing_in_index: List[Dict] = field(default_factory=list)
    missing_frontmatter: List[str] = field(default_factory=list)
    trigger_drift: List[Dict] = field(default_factory=list)
    orphan_index: List[str] = field(default_factory=list)
    scope_drift: List[Dict] = field(default_factory=list)
    depends_drift: List[Dict] = field(default_factory=list)

    def has_drift(self) -> bool:
        return any([self.missing_in_index, self.missing_frontmatter,
                    self.trigger_drift, self.orphan_index, self.scope_drift, self.depends_drift])

    def to_dict(self) -> Dict:
        return {
            "missing_in_index": self.missing_in_index,
            "missing_frontmatter": self.missing_frontmatter,
            "trigger_drift": self.trigger_drift,
            "orphan_index": self.orphan_index,
            "scope_drift": self.scope_drift,
            "depends_drift": self.depends_drift,
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


def parse_frontmatter_depends(text: str) -> Optional[List[str]]:
    """`- Depends:` 行 → 條目清單（逗號／全形逗號切、strip、去空、保序去重）；沒有該行回 None（存量，不算漂移）；
    有行但值空 → []（清空：索引殘值算漂移，--sync-depends 會把索引鍵清掉）。"""
    m = DEPENDS_LINE_RE.search(text)
    if not m:
        return None
    out: List[str] = []
    for item in re.split(r"[,，]", m.group(1)):
        s = item.strip()
        if s and s not in out:
            out.append(s)
    return out


def depends_drift(atom: AtomFile, row: IndexRow) -> Optional[Dict]:
    """frontmatter 為真相：有 Depends 行而索引缺或不同 → 漂移；frontmatter 沒有行（存量）→ 不報，索引殘值由 --sync-depends 不動。
    回漂移記錄或 None。"""
    if atom.depends is None:
        return None
    index_deps = row.depends or []
    if sorted(atom.depends) == sorted(index_deps):
        return None
    return {
        "atom": row.name,
        "path": row.path,
        "frontmatter": atom.depends,
        "index": index_deps,
    }


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
        rm = find_related_line(text)
        related = split_related(rm.group(1)) if rm else []
        am = find_aka_line(text)
        aka = split_related(am.group(1)) if am else []
        em = find_entry_line(text)
        slug = md.stem
        rel = str(md.relative_to(claude_root)).replace("\\", "/")
        out[rel] = AtomFile(name=slug, path=md, rel_path=rel,
                            triggers=triggers, scope=scope, related=related, aka=aka,
                            entry=split_related(em.group(1)) if em else [],
                            depends=parse_frontmatter_depends(text))
    return out


def load_index_rows(memory_dir: Path) -> List[IndexRow]:
    """V5: 讀 _atom_index.json，回傳 IndexRow list（取代舊 _ATOM_INDEX.md table parser）."""
    data = load_atom_index_json(memory_dir)
    rows: List[IndexRow] = []
    for a in data.get("atoms", []):
        deps = a.get("depends")
        rows.append(IndexRow(
            name=a.get("name", ""),
            path=a.get("path", "").replace("\\", "/"),
            triggers=dedup_triggers(a.get("triggers", [])),
            scope=a.get("scope", "global"),
            depends=[d for d in deps if isinstance(d, str)] if isinstance(deps, list) else None,
            related=list(a.get("related", [])),
            aka=list(a.get("aka", [])),
            entry=list(a.get("entry", [])),
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
        dd = depends_drift(atom, row)
        if dd:
            rep.depends_drift.append(dd)

    return rep


def sync_depends_from_frontmatter(atoms_by_path: Dict[str, AtomFile],
                                  index_rows: List[IndexRow],
                                  memory_dir: Path) -> List[str]:
    """--sync-depends：frontmatter 有 Depends 行的 atom，把清單寫進索引 depends（走 upsert_atom，[] 也會清空索引殘值）；
    沒有行的存量不碰。回改到的 atom 名。"""
    changed: List[str] = []
    for row in index_rows:
        atom = atoms_by_path.get(row.path)
        if atom is None or depends_drift(atom, row) is None:
            continue
        upsert_atom(memory_dir, name=row.name, path=row.path, triggers=row.triggers,
                    scope=row.scope, depends=list(atom.depends or []))
        changed.append(row.name)
    return changed


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
            # 走 funnel：write_text_lf（一律 LF）+ audit log
            write_raw(atom.path, new_text, source="tool:sync-atom-index", op="trigger-align")
            changed.append(atom.rel_path)
    return changed


def add_to_index_from_frontmatter(atoms_by_path: Dict[str, AtomFile],
                                  index_rows: List[IndexRow],
                                  memory_dir: Path) -> List[str]:
    """frontmatter 有、索引缺的 atom 補進索引（與 upsert_atom 同一套語意：apply_upsert）。

    順帶把索引的 `related`（正向連結）對齊 atom 檔——反向連結不存檔、由注入端反轉，
    所以索引這份正向連結就是連結圖的唯一來源，必須跟著 atom 檔走。`entry`（切入點代號）同理跟著 atom 檔走。

    整批在記憶體改完、最後只落一次檔（JSON 先、md 鏡像後）。逐顆 upsert 每顆都整檔重寫兩份，N 顆換 2N 次檔，
    別的行程（每回合讀索引的 hook、索引器）任一次開著檔，Windows 就 WinError 5 整支中斷、補到哪算哪。
    索引檔在卻讀不到（被別的行程鎖著）就停手不寫：拿空索引寫回會把一份好好的索引抹掉；內容壞掉（衝突標記）照舊
    從 frontmatter 重生（多機合併三檔全壞的最後手段）。上次 md 鏡像沒換成時，這裡重生它。
    """
    data = load_atom_index_json(memory_dir, strict=True)
    by_path = {r.path: r for r in index_rows}
    added: List[str] = []
    changed = False
    for rel_path, atom in atoms_by_path.items():
        row = by_path.get(rel_path)
        if row is not None:
            if row.related == atom.related and row.aka == atom.aka and row.entry == atom.entry:
                continue
            changed |= apply_upsert(data, name=atom.name, path=rel_path,
                                    triggers=row.triggers, scope=row.scope,
                                    related=atom.related, aka=atom.aka, entry=atom.entry)
            continue
        ok = apply_upsert(
            data,
            name=atom.name,
            path=rel_path,
            triggers=atom.triggers,
            scope=atom.scope,
            depends=atom.depends,   # None＝frontmatter 無行＝不登；有行就連 depends 一起進索引
            related=atom.related,
            aka=atom.aka,
            entry=atom.entry,
        )
        if ok:
            changed = True
            added.append(atom.name)
    if changed or atom_index_md_stale(memory_dir, data):
        save_index_with_mirror(memory_dir, data)
    return added


_SCOPE_HEADER_RE = re.compile(r"^- Scope:\s*(.+?)\s*$", re.MULTILINE)


def scanned_root_prefixes(memory_dir: Path, claude_root: Path) -> List[str]:
    """`scan_atom_files` 這一趟真正走過的根，表示成 rel_path 前綴。

    全域索引不只 `memory/` 一個根（還有 `_AIDocs/_atoms/` 的 local realm、
    `_AIDocs/Failures/`），而多根只在 memory_dir 正好是本機 `~/.claude/memory` 時才啟用
    （與 scan_atom_files 同一判準）。副本、別台機器、測試樹都走單根，
    掃不到那些檔——重建索引時若對它們下刪除結論，那些 atom 會從索引消失且不再被注入。
    """
    multi = memory_dir.resolve() == MEMORY_DIR.resolve()
    roots = atom_search_roots() if multi else [memory_dir]
    out: List[str] = []
    for r in roots:
        try:
            out.append(str(Path(r).resolve().relative_to(claude_root.resolve())).replace("\\", "/"))
        except (OSError, ValueError):
            continue
    return out


def rebuild_index(memory_dir: Path, claude_root: Path,
                  atoms_by_path: Dict[str, AtomFile]) -> Dict[str, int]:
    """整份索引從磁碟重生，一次寫入（不逐顆 upsert，那是 O(n²) 重寫）。

    索引是衍生檔：磁碟上的 atom 才是原始資料。能隨時重生，索引就不必入版控，
    也就不會出現「兩個人各加一顆 atom ＝ 同一區塊各插一列 ＝ 衝突」，
    更不會因為索引登錄了尚未上傳的 atom 而綁死「只上傳一部分」。

    兩條界線：
    - **只對掃過的範圍下刪除結論**：path 落在本趟掃描根之外的條目原樣保留。
    - **不改 scope**：既有條目沿用原值，只有新條目由 path 推導。scope 回正是
      `--fix-scope-from-path` 的職責，兩件事混在一起會讓副本上的一次重建把全庫標錯層。

    last_used 不在 .md 裡，從舊索引沿用。回傳各段筆數。
    """
    layer = "global" if memory_dir.resolve() == MEMORY_DIR.resolve() else "shared"
    prev_index = load_atom_index_json(memory_dir)
    prev_list = prev_index.get("atoms", [])
    prev = {a.get("name"): a for a in prev_list}
    covered = scanned_root_prefixes(memory_dir, claude_root)

    def droppable(rel_path: str) -> bool:
        """只有「在本趟掃描根之下、而檔案真的不存在」才算懸空可刪。

        掃描器另有排除規則（_reference/_staging/templates…），那些目錄裡的既有條目
        掃不到卻檔案還在——那是排除規則與索引的分歧，不該由重建工具靜默裁決成刪除。
        """
        rel_path = (rel_path or "").replace("\\", "/")
        if not rel_path:
            return False
        inside = any(rel_path == c or rel_path.startswith(c + "/") for c in covered)
        return inside and not (claude_root / rel_path).exists()

    scanned_names = {af.name for af in atoms_by_path.values()}
    kept = [a for a in prev_list
            if a.get("name") not in scanned_names and not droppable(a.get("path", ""))]
    atoms: List[Dict] = list(kept)
    for rel_path, af in atoms_by_path.items():
        old_entry = prev.get(af.name) or {}
        entry: Dict = {
            "name": af.name,
            "path": rel_path,
            "triggers": dedup_triggers(af.triggers),
            "scope": old_entry.get("scope") or scope_from_index_path(rel_path, layer),
        }
        if af.related:
            entry["related"] = list(dict.fromkeys(af.related))
        if af.aka:
            entry["aka"] = list(dict.fromkeys(af.aka))
        if af.entry:
            entry["entry"] = list(dict.fromkeys(af.entry))
        if old_entry.get("last_used"):
            entry["last_used"] = old_entry["last_used"]
        atoms.append(entry)
    # 既有條目維持舊索引的順序，新條目接在尾端（新條目之間以 path 排序求可重現）。
    # 索引是入版控的檔：重排會讓整檔變成一次重寫（實測 8000 行 diff 有 57% 純粹是位移），
    # 人看不出真正改了什麼，三檔合併驅動也失去「同區塊各多一列」這個前提。
    order = {a.get("name"): i for i, a in enumerate(prev_list)}
    tail = len(order)
    atoms.sort(key=lambda a: (order.get(a.get("name"), tail), a.get("path", "")))
    # 重生只負責 version 與 atoms。其餘頂層鍵是別的工具寫的狀態（classify-project-scope
    # 的 layout="scope-v2" 判「這個專案的記憶已整理過」），這裡不認得、也不該吃掉——原樣帶過去。
    carried = {k: v for k, v in prev_index.items() if k not in ("version", "atoms")}
    save_index_with_mirror(
        memory_dir, {"version": SCHEMA_VERSION, "atoms": atoms, **carried})
    return {"scanned": len(atoms_by_path), "kept_outside_scan": len(kept), "total": len(atoms)}


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
    parser.add_argument("--sync-depends", action="store_true",
                        help="write frontmatter Depends into _atom_index.json depends (frontmatter is truth; atoms without a Depends line untouched)")
    parser.add_argument("--rebuild", action="store_true",
                        help="整份索引從磁碟重生（衍生檔，可隨時重建；不動任何 .md）")
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
    hooks = Path(__file__).resolve().parent.parent / "hooks"   # 程式碼：本檔所在的樹
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

    if getattr(args, "rebuild", False):   # 程式化呼叫端（測試/工具）自組 Namespace，不一定帶這旗標
        stat = rebuild_index(memory_dir, claude_root, atoms_by_path)
        actions_taken.append(f"index rebuilt from disk: {stat}")
        index_rows = load_index_rows(memory_dir)

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

    if getattr(args, "sync_depends", False):
        changed = sync_depends_from_frontmatter(atoms_by_path, index_rows, memory_dir)
        if changed:
            actions_taken.append(f"index depends synced from frontmatter: {changed}")
            index_rows = load_index_rows(memory_dir)

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
