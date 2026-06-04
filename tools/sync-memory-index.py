"""
sync-memory-index.py — 從 _atom_index.json 自動生成 memory/MEMORY.md（V5 P6c）

設計依據：V5 Wave 3 P3b — `_atom_index.json` 為 SoT

V4→V5 變更：parse_atom_index 改讀 `_atom_index.json`（先前讀 `_ATOM_INDEX.md`，
該檔現為自動生成 mirror，drift 風險可避）。

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
    LOCAL_REALM_DEFAULT_DOMAIN,
    atom_index_row_kind,
    local_realm_domain,
)

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
    """分類 atom 列 → (individual, feedback_names, failures_other, local_by_domain)。

    - individual:    一般 global atom 主表行 [(name, caption, rel_path)]
    - feedback_names: feedback-* 名稱（聚合一行）
    - failures_other: _AIDocs/Failures/ 內非 feedback-*（獨立行）[(name, caption, rel_path)]
    - local_by_domain: path 落 _AIDocs/_atoms/ 的 local atom，依 domain 分組（保索引序）

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
    local_by_domain: dict = {}
    for name, rel_path, _scope in rows:
        kind = atom_index_row_kind(rel_path, name)
        if kind == "feedback_aggregate":
            feedback_names.append(name)
        elif kind == "failures_other":
            failures_other.append((name, extract_atom_caption(claude_root / rel_path) if rel_path else "", rel_path))
        elif kind == "local_realm":
            dom = local_realm_domain(rel_path) or LOCAL_REALM_DEFAULT_DOMAIN
            local_by_domain.setdefault(dom, []).append((name, _cap(name, rel_path), rel_path))
        else:  # individual
            individual.append((name, _cap(name, rel_path), rel_path))
    return individual, feedback_names, failures_other, local_by_domain


# 主表末尾指標（local atom 存在時）：人在任何環境讀 MEMORY.md 仍知本地範疇何在。
LOCAL_CATALOG_POINTER = (
    "> 本地範疇（World/Tools/MemDev，僅 ~/.claude 注入）索引見 `_local_catalog.md`。"
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
    individual, feedback_names, failures_other, local_by_domain = _classify_rows(
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
    if local_by_domain:
        lines += ["", LOCAL_CATALOG_POINTER]
    return "\n".join(lines)


def render_local_catalog(rows: List[Tuple[str, str, str]],
                         claude_root: Path,
                         existing_caps: dict | None = None) -> str:
    """Render 本地範疇 catalog（側檔 _local_catalog.md）— 僅核心環境由 SessionStart hook 注入。

    自含文件（H1 + 說明 + domain 子表）；無 local atom → 回 ""（caller 據此移除殘留側檔）。
    caption preserve 沿用一般規則（H1 裸名 → existing_caps 人工描述）。
    """
    _ind, _fb, _fo, local_by_domain = _classify_rows(rows, claude_root, existing_caps)
    if not local_by_domain:
        return ""
    lines = [
        f"# {LOCAL_CATALOG_TITLE}",
        "",
        "> 物理居 `_AIDocs/_atoms/<domain>/`，索引仍在 `_atom_index.json`（scope=global）；"
        "**只在 cwd∈~/.claude 時注入**，外部專案零負擔。機制見 [[realm-範疇分區機制-v5]]。",
    ]
    for dom in sorted(local_by_domain):
        lines += ["", f"### {dom}", "", "| Atom | 說明 |", "|------|------|"]
        for name, cap, _ in local_by_domain[dom]:
            lines.append(f"| {name} | {cap} |")
    return "\n".join(lines)


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

    # caption preserve 跨兩檔：local caption migration 首跑仍在舊 MEMORY.md，之後住側檔；
    # 合併兩檔人工策展描述（core/local 名稱不重疊，update 安全）。
    existing_caps = parse_existing_captions(memory_path)
    existing_caps.update(parse_existing_captions(local_catalog_path))

    core_section = render_core_section(rows, claude_root, existing_caps)
    _old_head, knowledge_tail = split_existing(memory_path)
    new_core = core_section + "\n\n" + knowledge_tail if knowledge_tail else core_section + "\n"

    local_catalog = render_local_catalog(rows, claude_root, existing_caps)
    new_local = (local_catalog + "\n") if local_catalog else ""

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
            print(f"[sync-memory-index] wrote {memory_path} + {local_catalog_path}")
        else:
            try:
                local_catalog_path.unlink()
            except FileNotFoundError:
                pass
            print(f"[sync-memory-index] wrote {memory_path} (no local atoms; removed side catalog)")
        return 0

    print(new_core)
    if new_local:
        print("\n# ── _local_catalog.md ──\n")
        print(new_local)
    return 0


if __name__ == "__main__":
    sys.exit(main())
