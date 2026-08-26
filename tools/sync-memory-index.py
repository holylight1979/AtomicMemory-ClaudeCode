"""
sync-memory-index.py — 從 _atom_index.json 自動生成 memory/MEMORY.md

`_atom_index.json` 為機器真相源（SoT）；parse_atom_index 以它為來源，
`_ATOM_INDEX.md` 為自動生成 mirror，不作解析來源以避 drift。

行為：
- 讀 `_atom_index.json` 取得所有 atom（按 name 排序、計數）
- 從每 atom 檔的 H1 第一行抽取「說明」欄
- **保留人工策展描述**：funnel 建立的 atom H1=裸 kebab-name，H1 caption 會退化成裸名；
  此時沿用現有 MEMORY.md / 各層 _INDEX.md 較豐富的描述，regen 永不把人寫的描述降級成裸名
  （精準度：描述性 H1 > 現有人工描述 > 裸名）。僅作用於一般 atom 列。
- 保留現有「知識庫查閱」段落（自動偵測 `> **知識庫查閱**：` 標記後內容）
- **realm 雙輸出**：core atom → `MEMORY.md`（@import，全專案）；
  本地範疇 atom（path 落 `_AIDocs/_atoms/`）→ 側檔 `_local_catalog.md`，僅核心環境由
  SessionStart hook 注入。MEMORY.md 主表末尾僅留一行指標，外部專案零本地負擔。

核心區兩種渲染（`hierarchical` 參數；None → workflow/config.json `taxonomy.gate_enabled`）：
- 平鋪（gate 關，遷移前）：一 atom 一列 `| Atom | 說明 |`，feedback-* 聚合一列指向 Failures 資料夾。
- 階層（gate 開）：`| 範疇 | atom 數 | 深入 |`，memory/ 下每個 Lv1 一列（Failures 亦為其一），
  深入指各層 `_INDEX.md`（單葉直指 atom）。**硬規則：memory/ 根下不容平鋪 atom**——
  `--check` 逐顆印 `flat atom under memory/: <slug>` 並 exit 1、`--write` 拒寫。不設「未分類」表。

per-level `_INDEX.md`：兩根都走（`_AIDocs/_atoms/<階層>/`、`memory/<範疇>/…`），只在
有子層或 atom≥2 的層生成；memory/ 根層（depth-0）永不生成（根索引就是 MEMORY.md）。

模式（皆作用於 MEMORY.md + _local_catalog.md + 各層 _INDEX.md）：
  --check  drift 偵測，stderr 列出差異，任一檔 drift → exit 1
  --write  覆寫（無 local atom → 移除殘留側檔；stale _INDEX.md 移除）
  (default) dry-run，stdout 顯示新內容
  --hierarchical / --legacy  強制核心區渲染模式（預設讀 config）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.atom_io import write_index_full  # noqa: E402
from lib.atom_index_json import load_atom_index_json  # noqa: E402
from lib.atom_locations import (  # noqa: E402
    CORE_ATOMS_REL,
    FAILURES_REL,
    FAILURES_ROOT_NAME,
    LEGACY_FAILURES_REL,
    LOCAL_ATOMS_REL,
    LOCAL_REALM_DEFAULT_DOMAIN,
    atom_index_row_kind,
    core_category_segments,
    is_legacy_failures_path,
    iter_realm_category_dirs,
    local_realm_path_segments,
)

try:
    from lib.atom_taxonomy import core_categories as _taxonomy_core_categories  # noqa: E402
    from lib.atom_taxonomy import gate_enabled as _taxonomy_gate_enabled  # noqa: E402
except Exception:  # taxonomy 模組缺 → 平鋪模式、範疇純字母序
    _taxonomy_core_categories = None
    _taxonomy_gate_enabled = None

# 人讀文件 atom 計數同步（SoT=_atom_index.json）：piggyback 本工具的 atom_write 觸發鏈，
# 每次 atom 增刪/搬移後靜默把 TECH/_INDEX/DocIndex 的計數標記跟上（見 sync_doc_counts.py）。
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/ for sibling import
try:
    import sync_doc_counts  # noqa: E402
except Exception:
    sync_doc_counts = None

MEMORY_DIR = Path.home() / ".claude" / "memory"
MEMORY_INDEX_NAME = "MEMORY.md"
LOCAL_CATALOG_NAME = "_local_catalog.md"  # 本地範疇側檔（hook 僅核心環境注入）
FLAT_ATOM_MSG = "[sync-memory-index] flat atom under memory/: {slug}"


def resolve_hierarchical(hierarchical: Optional[bool]) -> bool:
    """None → config `taxonomy.gate_enabled`（缺/壞 → False）；bool → 照給。"""
    if hierarchical is not None:
        return bool(hierarchical)
    if _taxonomy_gate_enabled is None:
        return False
    try:
        return bool(_taxonomy_gate_enabled())
    except Exception:
        return False


def _taxonomy_order() -> List[str]:
    """Lv1 宣告序（taxonomy.json）；不可用 → []（純字母序）。"""
    if _taxonomy_core_categories is None:
        return []
    try:
        return list(_taxonomy_core_categories())
    except Exception:
        return []


def parse_atom_index(memory_dir: Path) -> List[Tuple[str, str, str]]:
    """讀 _atom_index.json，回傳 (atom_name, rel_path, scope) list."""
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
    """解析現有索引檔（MEMORY.md / _local_catalog.md / 各層 _INDEX.md）的兩欄 atom 表 → {name: caption}。

    用於 regen 時保留人工策展的描述：funnel 建立的 atom H1=裸 kebab-name，
    extract_atom_caption 會退化成裸名；此處讓 regen 沿用現有較豐富的描述。
    三欄的範疇表（| 範疇 | atom 數 | 深入 |）自然被跳過；feedback-* 聚合列會被收進來但 render 不查它。
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


def _make_cap(claude_root: Path, existing_caps: dict):
    def _cap(name: str, rel_path: str) -> str:
        """H1 caption；退化成裸名/空 → 沿用 existing_caps 中較豐富的人工描述。"""
        cap = extract_atom_caption(claude_root / rel_path) if rel_path else ""
        if not cap or cap == name:
            prev = existing_caps.get(name, "")
            if prev and prev != name:
                cap = prev
        return cap
    return _cap


def _classify_rows(rows: List[Tuple[str, str, str]],
                   claude_root: Path,
                   existing_caps: dict | None = None):
    """分類 atom 列 → (individual, feedback_rows, failures_other, local_atoms)。

    - individual:    一般 global atom 主表行 [(name, caption, rel_path)]
    - feedback_rows: feedback-* [(name, rel_path)]（平鋪模式聚合一行）
    - failures_other: Failures 家族內非 feedback-*（獨立行）[(name, caption, rel_path)]
    - local_atoms:   path 落 _AIDocs/_atoms/ 的 local atom [(name, caption, rel_path, segments)]
                     （segments=Lv1..Lvn 階層路徑；缺段→[Else]）

    保留策展：一般/local atom 的 H1 caption 退化成裸名/空時，沿用 existing_caps 較豐富的描述
    （精準度：描述性 H1 > 現有人工描述 > 裸名）。
    """
    _cap = _make_cap(claude_root, existing_caps or {})
    individual: List[Tuple[str, str, str]] = []
    feedback_rows: List[Tuple[str, str]] = []
    failures_other: List[Tuple[str, str, str]] = []
    local_atoms: List[Tuple[str, str, str, List[str]]] = []
    for name, rel_path, _scope in rows:
        kind = atom_index_row_kind(rel_path, name)
        if kind == "feedback_aggregate":
            feedback_rows.append((name, rel_path))
        elif kind == "failures_other":
            failures_other.append((name, extract_atom_caption(claude_root / rel_path) if rel_path else "", rel_path))
        elif kind == "local_realm":
            segs = local_realm_path_segments(rel_path) or [LOCAL_REALM_DEFAULT_DOMAIN]
            local_atoms.append((name, _cap(name, rel_path), rel_path, segs))
        else:  # individual
            individual.append((name, _cap(name, rel_path), rel_path))
    return individual, feedback_rows, failures_other, local_atoms


def _core_category_atoms(rows: List[Tuple[str, str, str]],
                         claude_root: Path,
                         existing_caps: dict | None = None):
    """核心層（非 local）atom 依範疇段建樹用 → (categorized, flat_names)。

    categorized: [(name, cap, rel_path, segs)]，segs 由 core_category_segments 推
      （memory/<Lv1>/<Lv2>/x.md → ['Lv1','Lv2']；舊址 _AIDocs/Failures/x.md → ['Failures']）。
    flat_names: 無範疇段的核心 atom（memory/<slug>.md 等）——硬規則違規者，不進樹。
    """
    _cap = _make_cap(claude_root, existing_caps or {})
    categorized: List[Tuple[str, str, str, List[str]]] = []
    flat: List[str] = []
    for name, rel_path, _scope in rows:
        if atom_index_row_kind(rel_path, name) == "local_realm":
            continue
        segs = core_category_segments(rel_path)
        if not segs:
            flat.append(name)
            continue
        categorized.append((name, _cap(name, rel_path), rel_path, segs))
    return categorized, flat


def flat_core_atoms(rows: List[Tuple[str, str, str]]) -> List[str]:
    """memory/ 根下平鋪（無範疇資料夾）的核心 atom 名（硬規則檢查用）。"""
    return [name for name, rel_path, _ in rows
            if atom_index_row_kind(rel_path, name) != "local_realm"
            and not core_category_segments(rel_path)]


# ─── 階層樹（兩根共用：memory/<範疇>、_AIDocs/_atoms/<階層>）────────────────────


class _Node:
    """階層樹節點：該層 atom + 直屬子層。"""
    __slots__ = ("atoms", "children")

    def __init__(self):
        self.atoms: List[Tuple[str, str, str]] = []   # (name, cap, rel_path)
        self.children: dict = {}                       # segname -> _Node


def _build_tree(atoms_with_segs) -> _Node:
    root = _Node()
    for name, cap, rel_path, segs in atoms_with_segs:
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


def _subtree_all_legacy(node: _Node) -> bool:
    """子樹所有 atom 仍在舊址 _AIDocs/Failures/（遷移前）。"""
    if any(not is_legacy_failures_path(rp) for _n, _c, rp in node.atoms):
        return False
    return all(_subtree_all_legacy(c) for c in node.children.values())


# 主表末尾指標（local atom 存在時）：人在任何環境讀 MEMORY.md 仍知本地範疇何在。
LOCAL_CATALOG_POINTER = (
    "> 本地範疇（僅 ~/.claude 注入）Lv1 根索引見 `_local_catalog.md`，深層 drill 各層 `_INDEX.md`。"
)
LOCAL_CATALOG_TITLE = "本地範疇 Catalog（~/.claude only）"
CORE_INDEX_TITLE = "# Atom Index — Global"
HIERARCHICAL_NOTE = (
    "> Hook 依 trigger 自動注入 atom；範疇資料夾 `memory/<範疇>/`，深入各層 `_INDEX.md`；"
    "機器索引 `_atom_index.json`"
)


def _render_core_flat(individual, feedback_rows, failures_other, local_atoms) -> str:
    """平鋪版主表：一 atom 一列；feedback-* 聚合一列 → Failures 資料夾（全在舊址則指舊址）。"""
    lines = [
        CORE_INDEX_TITLE,
        "",
        "> Hook 自動匹配 trigger 注入相關 atom（完整觸發表見 `_atom_index.json` / `_ATOM_INDEX.md` mirror）。",
        "",
        "| Atom | 說明 |",
        "|------|------|",
    ]
    for name, cap, _ in individual:
        lines.append(f"| {name} | {cap} |")
    if feedback_rows:
        fb_dir = (LEGACY_FAILURES_REL
                  if all(is_legacy_failures_path(rp) for _n, rp in feedback_rows)
                  else FAILURES_REL)
        lines.append(
            f"| feedback-* | 行為校正（{len(feedback_rows)} atoms）"
            f" → [`{fb_dir}/`](../{fb_dir}/) |"
        )
    for name, cap, rel_path in failures_other:
        lines.append(f"| {name} | {cap} → [`{rel_path}`](../{rel_path}) |")
    if local_atoms:
        lines += ["", LOCAL_CATALOG_POINTER]
    return "\n".join(lines)


def _ordered_lv1(names) -> List[str]:
    """Lv1 列序：taxonomy 宣告序在前（有出現者），其餘字母序接後。"""
    declared = [c for c in _taxonomy_order() if c in names]
    rest = sorted(n for n in names if n not in declared)
    return declared + rest


def _render_core_hierarchical(rows, claude_root, existing_caps, local_atoms) -> str:
    """階層版主表：memory/ 下每個 Lv1 一列（含 Failures）+ 遞迴計數 + 深入指標。平鋪 atom 不進表。"""
    categorized, _flat = _core_category_atoms(rows, claude_root, existing_caps)
    tree = _build_tree(categorized)
    lines = [
        CORE_INDEX_TITLE,
        "",
        HIERARCHICAL_NOTE,
        "",
        "| 範疇 | atom 數 | 深入 |",
        "|------|---------|------|",
    ]
    for lv1 in _ordered_lv1(tree.children):
        node = tree.children[lv1]
        if lv1 == FAILURES_ROOT_NAME and _subtree_all_legacy(node):
            drill = f"`{LEGACY_FAILURES_REL}/_INDEX.md`"  # 遷移前：手寫舊址索引
        else:
            drill = _drill_target(node, f"{CORE_ATOMS_REL}/{lv1}")
        lines.append(f"| {lv1} | {_subtree_count(node)} | {drill} |")
    if local_atoms:
        lines += ["", LOCAL_CATALOG_POINTER]
    return "\n".join(lines)


def render_core_section(rows: List[Tuple[str, str, str]],
                        claude_root: Path,
                        existing_caps: dict | None = None,
                        hierarchical: Optional[bool] = None) -> str:
    """Render 核心 atom 索引（主表）— 即 @import 的 MEMORY.md 內容，**不含**本地範疇明細。

    local atom 抽出主表，僅末尾留一行指標（明細在側檔，由 render_local_catalog 產出、
    hook 在核心環境注入）→ 外部專案零本地負擔。
    hierarchical=None → 讀 config gate；False 平鋪表；True 範疇表（見模組說明）。
    """
    individual, feedback_rows, failures_other, local_atoms = _classify_rows(
        rows, claude_root, existing_caps)
    if resolve_hierarchical(hierarchical):
        return _render_core_hierarchical(rows, claude_root, existing_caps, local_atoms)
    return _render_core_flat(individual, feedback_rows, failures_other, local_atoms)


def render_local_catalog(rows: List[Tuple[str, str, str]],
                         claude_root: Path,
                         existing_caps: dict | None = None) -> str:
    """Render 本地範疇 catalog（側檔 _local_catalog.md）— 僅核心環境由 SessionStart hook 注入。

    **只輸出 Lv1 根 + 遞迴計數 + drill 指標**（always-load 維持 O(根數)、不隨 atom 量膨脹；
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


def render_level_index(node: _Node, rel_dir: str, hierarchical: Optional[bool] = None) -> str:
    """Render 單層 `_INDEX.md`：本層 atom（名+說明）＋直屬子層（名+遞迴計數 drill）。"""
    note = ("> 階層範疇索引（自動生成，`_` 前綴非 atom）。機制見 [[realm-範疇分區機制-v5]]。"
            if resolve_hierarchical(hierarchical) else
            "> 階層 local 範疇索引（自動生成，`_` 前綴非 atom）。機制見 [[realm-範疇分區機制-v5]]。")
    lines = [f"# {rel_dir} — 範疇索引", "", note]
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
                            existing_caps: dict | None = None,
                            hierarchical: Optional[bool] = None) -> dict:
    """走兩根的階層樹 → {abs _INDEX.md path: content}（僅 _needs_index 的層；按需，除雞肋）。

    memory/ 根層（depth-0）不生成——根索引就是 MEMORY.md；舊址 _AIDocs/Failures/ 的 atom
    不在 memory/ 之下，跳過（其 _INDEX.md 為手寫）。
    """
    mode = resolve_hierarchical(hierarchical)
    _ind, _fb, _fo, local_atoms = _classify_rows(rows, claude_root, existing_caps)
    categorized, _flat = _core_category_atoms(rows, claude_root, existing_caps)
    core_atoms = [a for a in categorized if not is_legacy_failures_path(a[2])]
    out: dict = {}

    def walk(node: _Node, root_rel: str, segs: List[str]) -> None:
        if segs and _needs_index(node):
            rel_dir = "/".join([root_rel] + segs)
            out[claude_root / rel_dir / "_INDEX.md"] = render_level_index(node, rel_dir, mode)
        for cn in sorted(node.children):
            walk(node.children[cn], root_rel, segs + [cn])

    walk(_build_tree(local_atoms), LOCAL_ATOMS_REL, [])
    walk(_build_tree(core_atoms), CORE_ATOMS_REL, [])
    return out


def existing_index_files(claude_root: Path, memory_dir: Path) -> Set[Path]:
    """磁碟現存、由本工具管轄的 _INDEX.md：_AIDocs/_atoms/** ∪ memory/<範疇>/**。

    只掃 iter_realm_category_dirs 認可的範疇資料夾——`memory/_reference/**`、手寫的
    `_AIDocs/Failures/_INDEX.md` 等永不被視為 stale。
    """
    def _managed(root: Path) -> Set[Path]:
        # rglob 會鑽進 `_reference/`、`_distant/` 等 `_` 前綴子夾——那些不是範疇層、
        # 其 _INDEX.md 是手寫參考索引，不歸本工具管（否則 --write 會把它當 stale 刪掉）
        return {
            p for p in root.rglob("_INDEX.md")
            if not any(part.startswith("_") for part in p.relative_to(root).parts[:-1])
        }

    found: Set[Path] = set()
    local_atoms_dir = claude_root / LOCAL_ATOMS_REL
    if local_atoms_dir.is_dir():
        found |= _managed(local_atoms_dir)
    for cat_dir in iter_realm_category_dirs(memory_dir):
        found |= _managed(cat_dir)
    return found


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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--hierarchical", dest="hierarchical", action="store_true", default=None,
                      help="強制範疇表渲染（預設讀 config taxonomy.gate_enabled）")
    mode.add_argument("--legacy", dest="hierarchical", action="store_false",
                      help="強制平鋪表渲染")
    args = parser.parse_args()

    memory_dir: Path = args.memory_dir
    claude_root = memory_dir.parent
    memory_path = memory_dir / MEMORY_INDEX_NAME
    local_catalog_path = memory_dir / LOCAL_CATALOG_NAME
    hierarchical = resolve_hierarchical(args.hierarchical)

    rows = parse_atom_index(memory_dir)
    if not rows:
        print("[sync-memory-index] _atom_index.json empty or missing", file=sys.stderr)
        return 1

    # caption preserve 跨多檔：MEMORY.md + 側檔 + 兩根各層 _INDEX.md（人工策展描述名稱不重疊）。
    existing_caps = parse_existing_captions(memory_path)
    existing_caps.update(parse_existing_captions(local_catalog_path))
    cur_index_files = existing_index_files(claude_root, memory_dir)
    for idx in sorted(cur_index_files):
        existing_caps.update(parse_existing_captions(idx))

    # 硬規則：階層模式下 memory/ 根不容平鋪 atom（平鋪模式不查——遷移前 49 顆本來就在根下）。
    flat = flat_core_atoms(rows) if hierarchical else []
    for slug in flat:
        print(FLAT_ATOM_MSG.format(slug=slug), file=sys.stderr)

    core_section = render_core_section(rows, claude_root, existing_caps, hierarchical)
    _old_head, knowledge_tail = split_existing(memory_path)
    new_core = core_section + "\n\n" + knowledge_tail if knowledge_tail else core_section + "\n"

    local_catalog = render_local_catalog(rows, claude_root, existing_caps)
    new_local = (local_catalog + "\n") if local_catalog else ""

    # per-level _INDEX.md：新生成集 vs 磁碟現存（差集＝stale，須移除/標 drift）。
    new_index_files = collect_per_level_files(rows, claude_root, existing_caps, hierarchical)
    stale_index_files = cur_index_files - set(new_index_files)

    if args.check:
        drift = bool(flat)
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
        if flat:
            print(f"[sync-memory-index] refuse to write: {len(flat)} flat atom(s) under memory/ "
                  "(move them into memory/<範疇>/ first)", file=sys.stderr)
            return 1
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
