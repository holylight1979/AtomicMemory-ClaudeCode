"""overview_scaffold：從零掃出 `<專案>/.claude/overview-map.md` 骨架表與每部位五段佔位卡（純函式）。

做什麼：任何專案第一次就有表。掃頂層目錄（扣掉 scaffold_ignore）當部位、用 lib/refix_churn 算 fix 熱點排前、
層由 layers 指定（預設全部「單層」）、Lv1 只映射既有清單絕不開新、每列一張 [臨] 骨架卡（五段各一行佔位句）。
產出的表必須過 `overview_hub.parse_map`；狀態欄一律「骨架」。

不落檔：這裡只算與渲染；寫表（write_text_lf）與寫卡（atom_io.write_atom）由 `write_scaffold` 做、CLI 預設 dry-run。
表存在時 `write_scaffold` 拒寫（ScaffoldError），`merge_missing=True` 只補表上沒有的前綴列。
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .overview_hub import MAP_REL, parse_map
    from .atom_spec import slugify
    from .atom_taxonomy import TaxonomyUnavailable, core_categories, match_lv1
    from .atom_locations import project_taxonomy_lv1
    from .atom_io import write_atom, write_text_lf
    from . import refix_churn as rc
except ImportError:  # 以 ~/.claude 為 sys.path 根時（tools／verify）：atom_io 只能以套件匯入
    from lib.overview_hub import MAP_REL, parse_map
    from lib.atom_spec import slugify
    from lib.atom_taxonomy import TaxonomyUnavailable, core_categories, match_lv1
    from lib.atom_locations import project_taxonomy_lv1
    from lib.atom_io import write_atom, write_text_lf
    from lib import refix_churn as rc

DEFAULT_IGNORE = [".git", ".svn", "node_modules", "obj", "bin", "Library", "Temp", "__pycache__", ".claude", "_AIDocs"]
DEFAULT_LAYER = "單層"
DEFAULT_LV1 = "設計通則"
STATUS_SKELETON = "骨架"
CARD_SUFFIX = "部位導讀"
SOURCE = "tool:overview-map-scaffold"
HEADER = ["路徑前綴", "部位", "導讀卡", "狀態", "病灶清單", "量尺（量法｜指令｜門檻）", "檢查器清單", "讀路徑樣本",
          "第四問", "層", "權威地圖", "上游", "下游"]
SECTIONS = ("做什麼", "部位與權威", "動手前必問", "已知病灶", "驗法")
PLACEHOLDER = "（待填）"
FILE_COUNT_CAP = 5000
SCAFFOLD_CMD = "python ~/.claude/tools/overview-map-scaffold.py --cwd <專案根> --write"
_PART_LINE_RE = re.compile(r"部位與權威：部位\s*`([^`]+)`")


class ScaffoldError(RuntimeError):
    """拒寫（表已存在）、Lv1 映射不到、根不存在、表讀不回。"""


def merge_cfg(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"scaffold_ignore": list(DEFAULT_IGNORE), "layers": {}, "scaffold_default_lv1": DEFAULT_LV1}
    for k in out:
        v = (cfg or {}).get(k)
        if v is not None:
            out[k] = v
    return out


# ─── 掃目錄 ──────────────────────────────────────────────────────────

def scan_top_dirs(root: Path, ignore: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """→ [{name, files}]（依名排序）。files＝該目錄下檔案數（扣 ignore 子目錄，數到 FILE_COUNT_CAP 就停）。"""
    root = Path(root)
    if not root.is_dir():
        raise ScaffoldError(f"專案根不存在或不是目錄：{root}")
    ig = {s.lower() for s in (DEFAULT_IGNORE if ignore is None else ignore)}
    out: List[Dict[str, Any]] = []
    for entry in sorted(os.scandir(root), key=lambda e: e.name.lower()):
        if not entry.is_dir(follow_symlinks=False) or entry.name.lower() in ig:
            continue
        out.append({"name": entry.name, "files": _count_files(Path(entry.path), ig)})
    return out


def _count_files(d: Path, ig: set) -> int:
    n = 0
    for _cur, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x.lower() not in ig]
        n += len(files)
        if n >= FILE_COUNT_CAP:
            return FILE_COUNT_CAP
    return n


def fix_hotspots_by_dir(root: Path, top_dirs: List[str], refix_cfg: Optional[Dict[str, Any]] = None,
                        since_days: Optional[int] = None) -> Tuple[Dict[str, int], Optional[str]]:
    """→ ({頂層目錄: fix 熱度}, 警告)。無 VCS → ({}, None)；VCS 讀失敗 → ({}, 原因)（降級但告知，不靜默）。"""
    cfg = rc.merge_cfg(refix_cfg)
    vcs = rc.detect_vcs(root)
    if vcs is None:
        return {}, None
    try:
        commits = rc.read_commits(root, vcs, int(since_days or cfg["refix_since_days"]))
    except rc.VcsError as e:
        return {}, f"{vcs} 歷史讀不到，熱點以零計：{e}"
    return rc.hotspots_by_dir(rc.rank_refixed(commits, cfg), top_dirs), None


def assign_layer(name: str, layers: Optional[Dict[str, List[str]]] = None) -> str:
    """layers＝{層名: [目錄名或 glob]}；對不上回「單層」。"""
    for layer, pats in (layers or {}).items():
        if any(fnmatch.fnmatchcase(name.lower(), str(p).lower()) for p in (pats or [])):
            return str(layer)
    return DEFAULT_LAYER


def card_name(part: str) -> str:
    return slugify(f"{part}{CARD_SUFFIX}")


def draft_rows(top_dirs: List[Dict[str, Any]], hotspots: Optional[Dict[str, int]] = None,
               layers: Optional[Dict[str, List[str]]] = None, top_n: Optional[int] = None) -> List[Dict[str, Any]]:
    """熱點（fix 熱度）高的排前、同熱度檔案多的排前、再依名；top_n 截前 N 列。卡名撞名時加 -2、-3。"""
    hot = hotspots or {}
    ordered = sorted(top_dirs, key=lambda d: (-int(hot.get(d["name"], 0)), -int(d.get("files", 0)), d["name"].lower()))
    if top_n:
        ordered = ordered[:int(top_n)]
    rows: List[Dict[str, Any]] = []
    used: Dict[str, int] = {}
    for d in ordered:
        base = card_name(d["name"])
        used[base] = used.get(base, 0) + 1
        card = base if used[base] == 1 else f"{base}-{used[base]}"
        rows.append({"prefix": f"{d['name']}/", "part": d["name"], "card": card, "status": STATUS_SKELETON,
                     "files": int(d.get("files", 0)), "hot": int(hot.get(d["name"], 0)),
                     "layer": assign_layer(d["name"], layers)})
    return rows


def render_table(rows: List[Dict[str, Any]], root_label: str = "") -> str:
    """十三欄表；只有前四欄與「層」有值，其餘填「無」或留空（parse_map 讀回時擴欄為空值）。"""
    lines = [f"# {root_label or '專案'} 部位表：骨架（從零掃出，待人補）", "",
             "> 列＝頂層目錄＝一個部位，依 fix 熱點排序；狀態「骨架」＝導讀卡只有五段佔位句，第一次改該部位前先補卡。",
             f"> 重掃只補缺列：`{SCAFFOLD_CMD} --merge-missing`；對帳表與卡：`python ~/.claude/tools/overview-map-scaffold.py check --cwd <專案根>`。",
             "", "| " + " | ".join(HEADER) + " |", "|" + "---|" * len(HEADER)]
    lines.extend(render_row(r) for r in rows)
    return "\n".join(lines) + "\n"


def render_row(r: Dict[str, Any]) -> str:
    cells = [f"`{r['prefix']}`", r["part"], f"`{r['card']}`", r.get("status", STATUS_SKELETON), "無", "無", "無",
             "", "", r.get("layer", DEFAULT_LAYER), "無", "無", "無"]
    return "| " + " | ".join(cells) + " |"


# ─── 骨架卡 ──────────────────────────────────────────────────────────

def skeleton_card(row: Dict[str, Any]) -> Dict[str, Any]:
    """write_atom 的參數（title／triggers／knowledge／actions）；五段各一行佔位句，第二段帶部位名供對帳。"""
    part, prefix = row["part"], row["prefix"]
    knowledge = [
        f"做什麼：{PLACEHOLDER}這個部位負責什麼、主要入口在哪",
        f"部位與權威：部位 `{part}`（前綴 `{prefix}`）；權威地圖{PLACEHOLDER}",
        f"動手前必問：{PLACEHOLDER}改這裡前必須先確認的一到三個問題",
        f"已知病灶：{PLACEHOLDER}這個部位以前怎麼摔過",
        f"驗法：{PLACEHOLDER}怎麼證明改對了（指令與哨兵）",
    ]
    return {
        "title": f"{part}{CARD_SUFFIX}",
        "triggers": [part, prefix.rstrip("/"), CARD_SUFFIX, "定位三行"],
        "knowledge": knowledge,
        "actions": [f"改 {prefix} 之前先把本卡五段填完，狀態欄從「骨架」改「有」"],
    }


def empty_sections(card_text: str) -> List[str]:
    """卡片裡還是佔位句的段名。"""
    return [s for s in SECTIONS
            if re.search(rf"^- (?:\[[^\]]+\] )?{re.escape(s)}：.*{re.escape(PLACEHOLDER)}", card_text, re.M)]


def map_lv1(root: Path, preferred: Optional[str] = None, core: Optional[List[str]] = None) -> str:
    """Lv1 只映射：專案 `shared/_taxonomy.json` domains → core_categories() → scaffold_default_lv1；絕不開新。"""
    want = (preferred or DEFAULT_LV1).strip()
    mem = Path(root) / ".claude" / "memory"
    project = project_taxonomy_lv1(mem)
    for x in project:
        if x.casefold() == want.casefold():
            return x
    if core is None:
        try:
            cats = core_categories()
        except TaxonomyUnavailable as e:
            raise ScaffoldError(f"taxonomy.json 讀不到，Lv1 無法映射：{e}") from e
        hit = match_lv1(want, cats)
    else:
        cats = list(core)
        hit = next((c for c in cats if c.casefold() == want.casefold()), None)
    if hit:
        return hit
    raise ScaffoldError(f"Lv1「{want}」不在專案 _taxonomy.json 也不在核心清單（{'、'.join(project + cats)}）；"
                        f"掃表不開新 Lv1，請用 --lv1 指定既有的一個")


def write_skeleton_cards(rows: List[Dict[str, Any]], root: Path, lv1: str, dry_run: bool = True) -> List[Dict[str, Any]]:
    """每列一張 [臨] 卡（scope=shared、source=tool:overview-map-scaffold）；回 [{card, ok, path|error}]。"""
    out: List[Dict[str, Any]] = []
    for r in rows:
        kw = skeleton_card(r)
        res = write_atom(scope="shared", confidence="[臨]", mode="create", source=SOURCE, domain=lv1,
                         project_cwd=str(root), dry_run=dry_run, **kw)
        out.append({"card": r["card"], "ok": res.ok, "path": str(res.path) if res.path else None, "error": res.error})
    return out


# ─── 落檔 ────────────────────────────────────────────────────────────

def merge_missing_rows(existing_text: str, rows: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """既有表 + 新列：只補表上沒有的前綴，接在最後一條表格列之後；回 (新文字, 補進去的列)。"""
    have = {p for r in parse_map(existing_text) for p in r["prefixes"]}
    added = [r for r in rows if r["prefix"].rstrip("/").lower() not in have]
    if not added:
        return existing_text, []
    lines = existing_text.splitlines()
    last = max((i for i, l in enumerate(lines) if l.lstrip().startswith("|")), default=len(lines) - 1)
    lines[last + 1:last + 1] = [render_row(r) for r in added]
    return "\n".join(lines) + "\n", added


def write_scaffold(root: Path, rows: List[Dict[str, Any]], lv1: str, *, write: bool = False,
                   merge_missing: bool = False, root_label: str = "") -> Dict[str, Any]:
    """write=False（預設）只算不落檔。表存在且非 merge_missing → ScaffoldError（永不覆寫）。"""
    root = Path(root)
    map_path = root / MAP_REL
    exists = map_path.is_file()
    if exists and not merge_missing:
        raise ScaffoldError(f"部位表已存在，不覆寫：{map_path}（只補缺列用 --merge-missing）")
    if exists:
        text, rows_to_write = merge_missing_rows(map_path.read_text(encoding="utf-8"), rows)
    else:
        text, rows_to_write = render_table(rows, root_label or root.name), rows
    parsed = parse_map(text)
    if len(parsed) < len(rows_to_write):
        raise ScaffoldError("渲染出的表讀不回（parse_map 列數少於草稿），不落檔")
    if write and rows_to_write:
        write_text_lf(map_path, text)
    cards = write_skeleton_cards(rows_to_write, root, lv1, dry_run=not write)
    return {"map": str(map_path), "written": bool(write and rows_to_write), "merged": exists,
            "rows": len(rows_to_write), "table": text, "cards": cards}


# ─── 對帳與首次提示 ──────────────────────────────────────────────────

def _card_files(mem_dir: Path) -> Dict[str, Path]:
    try:
        return {p.stem: p for p in sorted(mem_dir.rglob("*.md")) if p.stem.endswith(CARD_SUFFIX) or "部位" in p.stem}
    except OSError:
        return {}


def _find_card(mem: Path, card: str) -> List[Path]:
    try:
        for name in (card, card.replace("_", "-")):
            hits = sorted(mem.rglob(name + ".md"))
            if hits:
                return hits
    except OSError:
        pass
    return []


def check_consistency(root: Path, text: Optional[str] = None, mem_dir: Optional[Path] = None) -> List[str]:
    """三種不一致各一訊息：表卡名無檔、卡的部位與表的部位不符（Part 不符）、卡有表無。"""
    root = Path(root)
    mem = Path(mem_dir) if mem_dir else root / ".claude" / "memory"
    if text is None:
        try:
            text = (root / MAP_REL).read_text(encoding="utf-8")
        except OSError as e:
            return [f"表讀不到：{root / MAP_REL}（{e}）"]
    rows = parse_map(text)
    issues: List[str] = []
    parts = {r["part"] for r in rows} | {r["part_short"] for r in rows}
    table_cards: set = set()
    for r in rows:
        for card in r["cards"]:
            table_cards.add(card)
            hits = _find_card(mem, card)
            if not hits:
                where = r["prefixes"][0] if r["prefixes"] else "?"
                issues.append(f"表卡名無檔：列 `{where}` 的卡 `{card}` 在 {mem} 找不到")
                continue
            m = _PART_LINE_RE.search(hits[0].read_text(encoding="utf-8", errors="replace"))
            if m and m.group(1).strip() not in (r["part"], r["part_short"]):
                issues.append(f"Part 不符：卡 `{card}` 寫部位 `{m.group(1).strip()}`，表列是 `{r['part']}`")
    for stem, p in _card_files(mem).items():
        if stem in table_cards:
            continue
        m = _PART_LINE_RE.search(p.read_text(encoding="utf-8", errors="replace"))
        if m and m.group(1).strip() not in parts:
            issues.append(f"卡有表無：卡 `{stem}` 的部位 `{m.group(1).strip()}` 不在表上（{p}）")
    return issues


def first_session_hint(root: Path, mem_dir: Optional[Path] = None) -> str:
    """無表 → scaffold 指令段；骨架表 → 列出每張卡還空著的段；表都齊 → ""（SessionStart 掛接由軌 A 做）。"""
    root = Path(root)
    map_path = root / MAP_REL
    if not map_path.is_file():
        return (f"[Guardian:OverviewHub] 這個專案還沒有部位表（{map_path}）。先從零掃一張骨架（預設只預覽，不落檔）：\n"
                f"  python ~/.claude/tools/overview-map-scaffold.py --cwd {root}\n"
                f"  確認後加 --write 落表與五段骨架卡。")
    try:
        rows = parse_map(map_path.read_text(encoding="utf-8"))
    except OSError:
        return ""
    skeleton = [r for r in rows if r["status"] == STATUS_SKELETON]
    if not skeleton:
        return ""
    mem = Path(mem_dir) if mem_dir else root / ".claude" / "memory"
    lines = [f"[Guardian:OverviewHub] 部位表有 {len(skeleton)} 列還是「骨架」，改這些部位前先補卡的空段："]
    for r in skeleton:
        for card in r["cards"] or ["（表上沒卡）"]:
            hits = _find_card(mem, card)
            empties = empty_sections(hits[0].read_text(encoding="utf-8", errors="replace")) if hits else list(SECTIONS)
            where = "" if hits else "（卡檔不存在）"
            lines.append(f"- {r['part']}：`{card}`{where} 空段：{'、'.join(empties) if empties else '無'}")
    return "\n".join(lines)
