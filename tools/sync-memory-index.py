"""
sync-memory-index.py — 從 _atom_index.json 自動生成 memory/MEMORY.md

`_atom_index.json` 為機器真相源（SoT）；parse_atom_index 以它為來源，
`_ATOM_INDEX.md` 為自動生成 mirror，不作解析來源以避 drift。

行為：
- 讀 `_atom_index.json` 取得所有 atom（按 name 排序、計數）
- 從每 atom 檔的 H1 第一行抽取「說明」欄
- **保留人工策展描述**：funnel 建立的 atom H1=裸 kebab-name，H1 caption 會退化成裸名；
  此時沿用現有 MEMORY.md 較豐富的描述，regen 永不把人寫的描述降級成裸名
  （精準度：描述性 H1 > 現有人工描述 > 裸名）。僅作用於一般 atom 列。
- 重組「Atom Index」區，feedback-* 自動歸納並計數
- 保留現有「知識庫查閱」段落（自動偵測 `> **知識庫查閱**：` 標記後內容）
- **V5+ realm 雙輸出（跨錯界修復）**：core atom → `MEMORY.md`（@import，全專案）；
  本地範疇 atom（path 落 `_AIDocs/_atoms/`）→ 側檔 `_local_catalog.md`，僅核心環境由
  SessionStart hook 注入。MEMORY.md 主表末尾僅留一行指標，外部專案零本地負擔。
  caption preserve 跨兩檔合併（migration 首跑本地描述仍在舊 MEMORY.md → 自動保留進側檔）。

模式（皆作用於 MEMORY.md + _local_catalog.md 兩檔）：
  --check  drift 偵測，stderr 列出差異，任一檔 drift → exit 1
  --write  覆寫兩檔（無 local atom → 移除殘留側檔）
  (default) dry-run，stdout 顯示兩段新內容
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.atom_io import write_index_full  # noqa: E402
from lib.atom_index_json import load_atom_index_json  # noqa: E402
from lib.atom_locations import (  # noqa: E402
    FAILURES_REL,
    LOCAL_ATOMS_REL,
    LOCAL_REALM_DEFAULT_DOMAIN,
    atom_index_row_kind,
    local_realm_path_segments,
)

# 人讀文件 atom 計數同步（SoT=_atom_index.json）：piggyback 本工具的 atom_write 觸發鏈，
# 每次 atom 增刪/搬移後靜默把 TECH/_INDEX/DocIndex 的計數標記跟上（見 sync_doc_counts.py）。
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/ for sibling import
try:
    import sync_doc_counts  # noqa: E402
except Exception:
    sync_doc_counts = None

MEMORY_DIR = Path.home() / ".claude" / "memory"
MEMORY_INDEX_NAME = "MEMORY.md"
LOCAL_CATALOG_NAME = "_local_catalog.md"  # V5+ realm：本地範疇側檔（hook 僅核心環境注入）


def parse_atom_index(memory_dir: Path) -> List[Tuple[str, str, str]]:
    """V5: 讀 _atom_index.json，回傳 (atom_name, rel_path, scope) list."""
    data = load_atom_index_json(memory_dir)
    rows: List[Tuple[str, str, str]] = []
    for a in data.get("atoms", []):
        rows.append((
            a.get("name", ""),
            a.get("path", ""),
            a.get("scope", "global"),
        ))
    return rows


def extract_atom_caption(atom_path: Path) -> str:
    """Read first H1 line as caption."""
    if not atom_path.exists():
        return ""
    try:
        for line in atom_path.read_text(encoding="utf-8-sig").splitlines()[:5]:
            if line.startswith("# "):
                return line[2:].strip()
    except (OSError, UnicodeDecodeError):
        pass
    return ""


def parse_existing_captions(memory_path: Path) -> dict:
    """解析現有 MEMORY.md atom 表 → {name: caption}。

    用於 regen 時保留人工策展的描述：funnel 建立的 atom H1=裸 kebab-name，
    extract_atom_caption 會退化成裸名；此處讓 regen 沿用現有較豐富的描述。
    （feedback-* 聚合列 / failures_other 列也會被收進來，但 render 只對一般 atom 查詢，無副作用。）
    """
    caps: dict = {}
    if not memory_path.exists():
        return caps
    try:
        text = memory_path.read_text(encoding="utf-8-sig")
    except OSError:
        return caps
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) != 2:
            continue
        name, cap = cells
        if not name or name == "Atom" or set(name) <= {"-"}:
            continue  # 跳過表頭 / 分隔列
        caps[name] = cap
    return caps


def _classify_rows(rows: List[Tuple[str, str, str]],
                   claude_root: Path,
                   existing_caps: dict | None = None):
    """分類 atom 列 → (individual, feedback_names, failures_other, local_atoms)。

    - individual:    一般 global atom 主表行 [(name, caption, rel_path)]
    - feedback_names: feedback-* 名稱（聚合一行）
    - failures_other: _AIDocs/Failures/ 內非 feedback-*（獨立行）[(name, caption, rel_path)]
    - local_atoms:   path 落 _AIDocs/_atoms/ 的 local atom [(name, caption, rel_path, segments)]
                     （segments=Lv1..Lvn 階層路徑；缺段→[Else]）

    保留策展：一般/local atom 的 H1 caption 退化成裸名/空時，沿用 existing_caps 較豐富的描述
    （精準度：描述性 H1 > 現有人工描述 > 裸名）。
    """
    existing_caps = existing_caps or {}

    def _cap(name: str, rel_path: str) -> str:
        """H1 caption；退化成裸名/空 → 沿用 existing_caps 中較豐富的人工描述。"""
        cap = extract_atom_caption(claude_root / rel_path) if rel_path else ""
        if not cap or cap == name:
            prev = existing_caps.get(name, "")
            if prev and prev != name:
                cap = prev
        return cap

    individual: List[Tuple[str, str, str]] = []
    feedback_names: List[str] = []
    failures_other: List[Tuple[str, str, str]] = []
    local_atoms: List[Tuple[str, str, str, List[str]]] = []
    for name, rel_path, _scope in rows:
        kind = atom_index_row_kind(rel_path, name)
        if kind == "feedback_aggregate":
            feedback_names.append(name)
        elif kind == "failures_other":
            failures_other.append((name, extract_atom_caption(claude_root / rel_path) if rel_path else "", rel_path))
        elif kind == "local_realm":
            segs = local_realm_path_segments(rel_path) or [LOCAL_REALM_DEFAULT_DOMAIN]
            local_atoms.append((name, _cap(name, rel_path), rel_path, segs))
        else:  # individual
            individual.append((name, _cap(name, rel_path), rel_path))
    return individual, feedback_names, failures_other, local_atoms


# ─── 階層樹（local 範疇關聯式分級）─────────────────────────────────────────────


class _Node:
    """階層樹節點：該層 atom + 直屬子層。"""
    __slots__ = ("atoms", "children")

    def __init__(self):
        self.atoms: List[Tuple[str, str, str]] = []   # (name, cap, rel_path)
        self.children: dict = {}                       # segname -> _Node


def _build_tree(local_atoms) -> _Node:
    root = _Node()
    for name, cap, rel_path, segs in local_atoms:
        node = root
        for s in segs:
            node = node.children.setdefault(s, _Node())
        node.atoms.append((name, cap, rel_path))
    return root


def _subtree_count(node: _Node) -> int:
    return len(node.atoms) + sum(_subtree_count(c) for c in node.children.values())


def _needs_index(node: _Node) -> bool:
    """該層是否值得生 _INDEX.md（除雞肋：葉層單 atom 無子層→不生廢檔）。"""
    return bool(node.children) or len(node.atoms) >= 2


def _drill_target(node: _Node, rel_dir: str) -> str:
    """catalog/子層的「深入」指標：有 _INDEX → 指 _INDEX.md；單 atom 葉 → 直指該 atom。"""
    if _needs_index(node):
        return f"`{rel_dir}/_INDEX.md`"
    name, cap, rel_path = node.atoms[0]
    return f"`{rel_path}`"


# 主表末尾指標（local atom 存在時）：人在任何環境讀 MEMORY.md 仍知本地範疇何在。
LOCAL_CATALOG_POINTER = (
    "> 本地範疇（僅 ~/.claude 注入）Lv1 根索引見 `_local_catalog.md`，深層 drill 各層 `_INDEX.md`。"
)
LOCAL_CATALOG_TITLE = "本地範疇 Catalog（~/.claude only）"


def render_core_section(rows: List[Tuple[str, str, str]],
                        claude_root: Path,
                        existing_caps: dict | None = None) -> str:
    """Render 核心 atom 索引（主表）— 即 @import 的 MEMORY.md 內容，**不含**本地範疇明細。

    feedback-* 聚合一行 + `→ _AIDocs/Failures/` 指標；其他 Failures atom（cognitive-patterns 等）
    獨立一行標位置。V5+ realm：local atom 抽出主表，僅末尾留一行指標（明細在側檔，
    由 render_local_catalog 產出、hook 在核心環境注入）→ 外部專案零本地負擔。
    """
    individual, feedback_names, failures_other, local_atoms = _classify_rows(
        rows, claude_root, existing_caps)

    lines = [
        "# Atom Index — Global",
        "",
        "> Hook 自動匹配 trigger 注入相關 atom（完整觸發表見 `_atom_index.json` / `_ATOM_INDEX.md` mirror）。",
        "",
        "| Atom | 說明 |",
        "|------|------|",
    ]
    for name, cap, _ in individual:
        lines.append(f"| {name} | {cap} |")
    if feedback_names:
        lines.append(
            f"| feedback-* | 行為校正（{len(feedback_names)} atoms）"
            f" → [`{FAILURES_REL}/`](../{FAILURES_REL}/) |"
        )
    for name, cap, rel_path in failures_other:
        lines.append(f"| {name} | {cap} → [`{rel_path}`](../{rel_path}) |")
    if local_atoms:
        lines += ["", LOCAL_CATALOG_POINTER]
    return "\n".join(lines)


def render_local_catalog(rows: List[Tuple[str, str, str]],
                         claude_root: Path,
                         existing_caps: dict | None = None) -> str:
    """Render 本地範疇 catalog（側檔 _local_catalog.md）— 僅核心環境由 SessionStart hook 注入。

    **只輸出 Lv1 根 + 遞迴計數 + drill 指標**（OPEN 1：always-load 維持 O(根數)、不隨 atom 量膨脹；
    深層由各層 `_INDEX.md` 按需 drill-down）。無 local atom → 回 ""（caller 移除殘留側檔）。
    """
    _ind, _fb, _fo, local_atoms = _classify_rows(rows, claude_root, existing_caps)
    if not local_atoms:
        return ""
    tree = _build_tree(local_atoms)
    lines = [
        f"# {LOCAL_CATALOG_TITLE}",
        "",
        "> 物理居 `_AIDocs/_atoms/<階層路徑>/`，索引仍在 `_atom_index.json`（scope=global）；"
        "**只在 cwd∈~/.claude 時注入**，外部專案零負擔。深層進各層 `_INDEX.md`。"
        "機制見 [[realm-範疇分區機制-v5]]。",
        "",
        "| 範疇根 | atom 數 | 深入 |",
        "|--------|---------|------|",
    ]
    for root_name in sorted(tree.children):
        node = tree.children[root_name]
        rel_dir = f"{LOCAL_ATOMS_REL}/{root_name}"
        lines.append(f"| {root_name} | {_subtree_count(node)} | {_drill_target(node, rel_dir)} |")
    return "\n".join(lines)


def render_level_index(node: _Node, rel_dir: str) -> str:
    """Render 單層 `_INDEX.md`：本層 atom（名+說明）＋直屬子層（名+遞迴計數 drill）。"""
    lines = [
        f"# {rel_dir} — 範疇索引",
        "",
        "> 階層 local 範疇索引（自動生成，`_` 前綴非 atom）。機制見 [[realm-範疇分區機制-v5]]。",
    ]
    if node.atoms:
        lines += ["", "## 本層 atom", "", "| Atom | 說明 |", "|------|------|"]
        for name, cap, _ in sorted(node.atoms):
            lines.append(f"| {name} | {cap} |")
    if node.children:
        lines += ["", "## 子層", "", "| 子層 | atom 數 | 深入 |", "|------|---------|------|"]
        for cn in sorted(node.children):
            child = node.children[cn]
            lines.append(f"| {cn} | {_subtree_count(child)} | {_drill_target(child, f'{rel_dir}/{cn}')} |")
    return "\n".join(lines)


def collect_per_level_files(rows: List[Tuple[str, str, str]],
                            claude_root: Path,
                            existing_caps: dict | None = None) -> dict:
    """走階層樹 → {abs _INDEX.md path: content}（僅 _needs_index 的層；按需，除雞肋）。"""
    _ind, _fb, _fo, local_atoms = _classify_rows(rows, claude_root, existing_caps)
    tree = _build_tree(local_atoms)
    out: dict = {}

    def walk(node: _Node, segs: List[str]) -> None:
        if segs and _needs_index(node):
            rel_dir = "/".join([LOCAL_ATOMS_REL] + segs)
            out[claude_root / rel_dir / "_INDEX.md"] = render_level_index(node, rel_dir)
        for cn in sorted(node.children):
            walk(node.children[cn], segs + [cn])

    walk(tree, [])
    return out


KNOWLEDGE_BLOCK_MARKER = "> **知識庫查閱**："


def split_existing(memory_path: Path) -> Tuple[str, str]:
    """Split existing MEMORY.md into (atom_section, knowledge_block).
    knowledge_block 從 marker 那行開始（含），到檔尾。
    """
    if not memory_path.exists():
        return "", ""
    text = memory_path.read_text(encoding="utf-8-sig")
    idx = text.find(KNOWLEDGE_BLOCK_MARKER)
    if idx < 0:
        return text, ""
    head = text[:idx].rstrip() + "\n"
    tail = text[idx:]
    return head, tail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--memory-dir", type=Path, default=MEMORY_DIR)
    args = parser.parse_args()

    memory_dir: Path = args.memory_dir
    claude_root = memory_dir.parent
    memory_path = memory_dir / MEMORY_INDEX_NAME
    local_catalog_path = memory_dir / LOCAL_CATALOG_NAME

    rows = parse_atom_index(memory_dir)
    if not rows:
        print("[sync-memory-index] _atom_index.json empty or missing", file=sys.stderr)
        return 1

    # caption preserve 跨多檔：MEMORY.md + 側檔 + 各層 _INDEX.md（人工策展描述名稱不重疊）。
    existing_caps = parse_existing_captions(memory_path)
    existing_caps.update(parse_existing_captions(local_catalog_path))
    local_atoms_dir = claude_root / LOCAL_ATOMS_REL
    if local_atoms_dir.is_dir():
        for idx in local_atoms_dir.rglob("_INDEX.md"):
            existing_caps.update(parse_existing_captions(idx))

    core_section = render_core_section(rows, claude_root, existing_caps)
    _old_head, knowledge_tail = split_existing(memory_path)
    new_core = core_section + "\n\n" + knowledge_tail if knowledge_tail else core_section + "\n"

    local_catalog = render_local_catalog(rows, claude_root, existing_caps)
    new_local = (local_catalog + "\n") if local_catalog else ""

    # per-level _INDEX.md：新生成集 vs 磁碟現存（差集＝stale，須移除/標 drift）。
    new_index_files = collect_per_level_files(rows, claude_root, existing_caps)
    cur_index_files = (set(local_atoms_dir.rglob("_INDEX.md")) if local_atoms_dir.is_dir() else set())
    stale_index_files = cur_index_files - set(new_index_files)

    if args.check:
        drift = False
        cur_core = memory_path.read_text(encoding="utf-8-sig") if memory_path.exists() else ""
        if cur_core.strip() != new_core.strip():
            print("[sync-memory-index] MEMORY.md drift detected", file=sys.stderr)
            drift = True
        cur_local = local_catalog_path.read_text(encoding="utf-8-sig") if local_catalog_path.exists() else ""
        if cur_local.strip() != new_local.strip():
            print("[sync-memory-index] _local_catalog.md drift detected", file=sys.stderr)
            drift = True
        for abs_path, content in new_index_files.items():
            cur = abs_path.read_text(encoding="utf-8-sig") if abs_path.exists() else ""
            if cur.strip() != content.strip():
                print(f"[sync-memory-index] _INDEX.md drift: {abs_path}", file=sys.stderr)
                drift = True
        for abs_path in stale_index_files:
            print(f"[sync-memory-index] stale _INDEX.md: {abs_path}", file=sys.stderr)
            drift = True
        if sync_doc_counts is not None:
            dc_drift, dc_msgs = sync_doc_counts.sync(claude_root, write=False)
            for m in dc_msgs:
                print(m, file=sys.stderr)
            drift = drift or dc_drift
        return 1 if drift else 0

    if args.write:
        r1 = write_index_full(memory_path, new_core, source="tool:sync-memory-index")
        if not r1.ok:
            print(f"[sync-memory-index] write failed (MEMORY.md): {r1.error}", file=sys.stderr)
            return 1
        if new_local:
            r2 = write_index_full(local_catalog_path, new_local, source="tool:sync-memory-index")
            if not r2.ok:
                print(f"[sync-memory-index] write failed (_local_catalog.md): {r2.error}", file=sys.stderr)
                return 1
        else:
            try:
                local_catalog_path.unlink()
            except FileNotFoundError:
                pass
        for abs_path, content in new_index_files.items():
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            r = write_index_full(abs_path, content + "\n", source="tool:sync-memory-index")
            if not r.ok:
                print(f"[sync-memory-index] write failed ({abs_path}): {r.error}", file=sys.stderr)
                return 1
        for abs_path in stale_index_files:
            try:
                abs_path.unlink()
            except FileNotFoundError:
                pass
        print(f"[sync-memory-index] wrote {memory_path}"
              f"{' + ' + str(local_catalog_path) if new_local else ' (no local; removed side catalog)'}"
              f"{f' + {len(new_index_files)} _INDEX.md' if new_index_files else ''}"
              f"{f' (-{len(stale_index_files)} stale)' if stale_index_files else ''}")
        if sync_doc_counts is not None:
            _dc_drift, dc_msgs = sync_doc_counts.sync(claude_root, write=True)
            for m in dc_msgs:
                print(m, file=sys.stderr)
        return 0

    print(new_core)
    if new_local:
        print("\n# ── _local_catalog.md ──\n")
        print(new_local)
    for abs_path, content in new_index_files.items():
        print(f"\n# ── {abs_path} ──\n")
        print(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
