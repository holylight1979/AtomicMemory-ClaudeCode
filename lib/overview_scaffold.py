"""overview_scaffold：從零掃出 `<專案>/.claude/overview-map.md` 骨架表與每部位五段佔位卡（純函式）。

做什麼：任何專案第一次就有表。掃頂層目錄（扣掉 scaffold_ignore）當部位、用 lib/refix_churn 算 fix 熱點排前、
層由 layers 指定（預設全部「單層」）、Lv1 只映射既有清單絕不開新、每列一張 [臨] 骨架卡（五段各一行佔位句）。
產出的表必須過 `overview_hub.parse_map`；狀態欄一律「骨架」。

落檔順序（不撤回、可重入；表是最後一步）：
1. 先定卡名：列的卡名撞到既有卡檔時，卡內「部位與權威」行的部位等於列部位 → 沿用（reused）；不等 → 改名避撞（-2、-3…，
   避開既有表全部卡名、既有卡檔名、本次已用名）。
2. 逐張寫卡：先全部 dry-run 預驗，再逐張真寫；任一張失敗或拋例外 → 立刻停、不寫表、不刪任何東西，結果結構化回
   written_cards／failed_card／skipped_cards，呼叫端 exit 1。重跑同一指令：已寫的卡部位一致就沿用，只補缺的卡，最後寫表。
3. 全部卡都在了才寫表。
表存在時拒寫（ScaffoldError）；`merge_missing=True` 以既有表的「前綴→卡名」配對為準（既有列一字不動），只補表上沒有的前綴列
（卡名避開既有表全部卡名）與「表有列但卡檔不在」的卡。

卡落哪一層由 `detect_layer(root)` 決定（hooks/wg_core._layer_of 單源；lib 不硬依賴 hooks，載不到就退路徑判斷）：
根層（~/.claude）→ scope=global、realm=local、domain=MemDev（_AIDocs/_atoms/MemDev/）；公司根 → shared＋project_cwd=公司根
（與 atom-tools.js 的 org 對映相同；py 端沒有 org scope）；專案 → shared＋project_cwd=專案根。
"""

from __future__ import annotations

import fnmatch
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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

CLAUDE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_IGNORE = [".git", ".svn", "node_modules", "obj", "bin", "Library", "Temp", "__pycache__", ".claude", "_AIDocs"]
DEFAULT_LAYER = "單層"
DEFAULT_LV1 = "設計通則"
ROOT_DOMAIN = "MemDev"
LAYER_ROOT, LAYER_ORG, LAYER_PROJECT = "root", "org", "project"
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
    """拒寫（表已存在）、Lv1 映射不到、根不存在、表讀不回。卡寫失敗不是例外，是結構化結果（result["ok"] False）。"""


def merge_cfg(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"scaffold_ignore": list(DEFAULT_IGNORE), "layers": {}, "scaffold_default_lv1": DEFAULT_LV1}
    for k in out:
        v = (cfg or {}).get(k)
        if v is not None:
            out[k] = v
    return out


# ─── 判層 ────────────────────────────────────────────────────────────

def detect_layer(root: Path) -> Tuple[str, Path]:
    """→ (層, 該層的根)。走 hooks/wg_core._layer_of（根層／公司層／專案層單源）；wg_core 載不到時退「在 ~/.claude 之下＝根層，
    否則＝專案層」。專案層與解析不到專案根（none）都當專案，根＝使用者給的 --cwd。"""
    root = Path(root)
    try:
        if str(CLAUDE_DIR / "hooks") not in sys.path:
            sys.path.insert(0, str(CLAUDE_DIR / "hooks"))
        import wg_core  # noqa: WPS433
        info = wg_core._layer_of(str(root))
        if info.kind == "root":
            return LAYER_ROOT, Path(info.root)
        if info.kind == "org":
            return LAYER_ORG, Path(info.root)
        return LAYER_PROJECT, root
    except Exception as e:  # lib 不硬依賴 hooks；退路徑判斷但要說一聲
        print(f"[overview_scaffold] wg_core 判層不可用，退路徑判斷：{e}", file=sys.stderr)
    home_claude = Path.home() / ".claude"
    try:
        if root.resolve() == home_claude.resolve() or home_claude.resolve() in root.resolve().parents:
            return LAYER_ROOT, home_claude
    except OSError:
        pass
    return LAYER_PROJECT, root


def card_write_kwargs(layer: str, layer_root: Path, lv1: Optional[str]) -> Dict[str, Any]:
    """各層寫卡的 write_atom 參數（scope／realm／domain／project_cwd）。"""
    if layer == LAYER_ROOT:
        return {"scope": "global", "realm": "local", "domain": ROOT_DOMAIN}
    return {"scope": "shared", "project_cwd": str(layer_root), "domain": lv1}


def card_dirs(layer: str, layer_root: Path) -> List[Path]:
    """各層找卡檔的目錄。"""
    if layer == LAYER_ROOT:
        return [layer_root / "memory", layer_root / "_AIDocs" / "_atoms"]
    return [layer_root / ".claude" / "memory"]


# ─── 掃目錄 ──────────────────────────────────────────────────────────

def scan_top_dirs(root: Path, ignore: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """→ [{name, files}]（依名排序）。files＝該目錄下檔案數（扣 ignore 子目錄，數到 FILE_COUNT_CAP 就停）。
    根目錄讀不到（權限）→ stderr 一句、回 []（結果是零列、不落檔）。symlink 目錄不跟進；junction 未測。"""
    root = Path(root)
    if not root.is_dir():
        raise ScaffoldError(f"專案根不存在或不是目錄：{root}")
    ig = {s.lower() for s in (DEFAULT_IGNORE if ignore is None else ignore)}
    try:
        entries = sorted(os.scandir(root), key=lambda e: e.name.lower())
    except OSError as e:
        print(f"[overview_scaffold] 專案根讀不到，零列：{root}（{e}）", file=sys.stderr)
        return []
    out: List[Dict[str, Any]] = []
    for entry in entries:
        try:
            if not entry.is_dir(follow_symlinks=False) or entry.name.lower() in ig:
                continue
        except OSError:
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
    """熱點（fix 熱度）高的排前、同熱度檔案多的排前、再依名；top_n 截前 N 列。卡名撞名（a-b／a_b）時加 -2、-3
    （只看本次列；落檔前 `resolve_card_names` 會再對既有卡檔與既有表重定）。"""
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
    """write_atom 的參數（title／triggers／knowledge／actions）；title＝row["card"]（避撞後的名字，與表引用一致），
    五段各一行佔位句，第二段帶部位名供對帳與重跑沿用判定。"""
    part, prefix = row["part"], row["prefix"]
    knowledge = [
        f"做什麼：{PLACEHOLDER}這個部位負責什麼、主要入口在哪",
        f"部位與權威：部位 `{part}`（前綴 `{prefix}`）；權威地圖{PLACEHOLDER}",
        f"動手前必問：{PLACEHOLDER}改這裡前必須先確認的一到三個問題",
        f"已知病灶：{PLACEHOLDER}這個部位以前怎麼摔過",
        f"驗法：{PLACEHOLDER}怎麼證明改對了（指令與哨兵）",
    ]
    return {
        "title": row["card"],
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


# ─── 卡名定案（可重入） ──────────────────────────────────────────────

def card_part(path: Path) -> Optional[str]:
    """卡檔的「部位與權威」行寫的部位；沒有這行回 None。"""
    try:
        m = _PART_LINE_RE.search(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return m.group(1).strip() if m else None


def resolve_card_names(rows: List[Dict[str, Any]], dirs: List[Path], taken: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    """每列定最終卡名（就地改 row["card"]、加 reused／path）：
    候選從 base（slugify(部位＋部位導讀)）起，-2、-3… 往後找；候選在 taken（既有表全部卡名）或本次已用 → 跳過；
    候選已有卡檔：卡內部位行等於列部位 → 沿用（reused=True，不重寫）；不等（含沒有部位行）→ 跳過改名；候選沒檔 → 用它新寫。"""
    used: Set[str] = set(taken or ())
    for r in rows:
        base = card_name(r["part"])
        n = 1
        while True:
            cand = base if n == 1 else f"{base}-{n}"
            n += 1
            if cand in used:
                continue
            hits = _find_card(dirs, cand)
            if hits and card_part(hits[0]) != r["part"]:
                continue
            r["card"], r["reused"], r["path"] = cand, bool(hits), (str(hits[0]) if hits else None)
            break
        used.add(r["card"])
    return rows


def _try_write(kwargs: Dict[str, Any], row: Dict[str, Any], dry_run: bool) -> Tuple[bool, Optional[str], Optional[str]]:
    """一張卡 → (ok, path, error)；write_atom 拋例外也收成失敗，不往外冒。"""
    try:
        res = write_atom(confidence="[臨]", mode="create", source=SOURCE, dry_run=dry_run, **kwargs, **skeleton_card(row))
    except Exception as e:  # noqa: BLE001  寫卡端任何例外都要變成結構化失敗
        return False, None, f"{type(e).__name__}: {e}"
    return bool(res.ok), (str(res.path) if res.path else None), (None if res.ok else (res.error or "write_atom 回 ok=False 無訊息"))


def write_cards(rows: List[Dict[str, Any]], kwargs: Dict[str, Any], write: bool) -> Dict[str, Any]:
    """逐張寫卡（不撤回、可重入）：reused 的跳過不寫；先全部 dry-run 預驗，再逐張真寫；任一張失敗或拋例外 → 立刻停。
    回 {ok, cards:[{card, ok, path, error, reused}], written_cards, reused_cards, failed_card, skipped_cards, error}。"""
    out: Dict[str, Any] = {"ok": True, "cards": [], "written_cards": [], "reused_cards": [], "failed_card": None,
                           "skipped_cards": [], "error": None}
    todo = [r for r in rows if not r.get("reused")]
    out["reused_cards"] = [r["card"] for r in rows if r.get("reused")]
    out["cards"] = [{"card": r["card"], "ok": True, "path": r.get("path"), "error": None, "reused": True}
                    for r in rows if r.get("reused")]

    def _fail(idx: int, row: Dict[str, Any], err: str, stage: str) -> Dict[str, Any]:
        out["ok"] = False
        out["failed_card"] = {"name": row["card"], "error": err, "stage": stage}
        out["skipped_cards"] = [r["card"] for r in todo[idx + 1:]]
        out["cards"].append({"card": row["card"], "ok": False, "path": None, "error": err, "reused": False})
        out["cards"] += [{"card": r["card"], "ok": False, "path": None, "error": "未寫（前一張失敗即停）", "reused": False}
                         for r in todo[idx + 1:]]
        out["error"] = (f"已寫 {len(out['written_cards'])} 張、第 {idx + 1} 張（`{row['card']}`）{stage}失敗：{err}；"
                        f"表未寫；重跑同一指令會接續補完")
        return out

    for i, r in enumerate(todo):                      # 預驗：全部 dry-run
        ok, _p, err = _try_write(kwargs, r, dry_run=True)
        if not ok:
            return _fail(i, r, err or "預驗失敗", "預驗")
    if not write:
        out["cards"] += [{"card": r["card"], "ok": True, "path": None, "error": None, "reused": False} for r in todo]
        return out
    for i, r in enumerate(todo):                      # 真寫：逐張，失敗即停、不刪已寫的
        ok, p, err = _try_write(kwargs, r, dry_run=False)
        if not ok:
            return _fail(i, r, err or "真寫失敗", "真寫")
        out["written_cards"].append(r["card"])
        out["cards"].append({"card": r["card"], "ok": True, "path": p, "error": None, "reused": False})
    return out


# ─── 落檔 ────────────────────────────────────────────────────────────

def merge_missing_rows(existing_text: str, rows: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """既有表 + 新列：只補表上沒有的前綴，接在最後一條表格列之後（既有列一字不動）；回 (新文字, 補進去的列)。"""
    have = {p for r in parse_map(existing_text) for p in r["prefixes"]}
    added = [r for r in rows if r["prefix"].rstrip("/").lower() not in have]
    if not added:
        return existing_text, []
    lines = existing_text.splitlines()
    last = max((i for i, l in enumerate(lines) if l.lstrip().startswith("|")), default=len(lines) - 1)
    lines[last + 1:last + 1] = [render_row(r) for r in added]
    return "\n".join(lines) + "\n", added


def rows_missing_cards(existing_text: str, dirs: List[Path]) -> List[Dict[str, Any]]:
    """既有表上「有卡名但卡檔不在」的列 → 可寫卡的 row dict（部位、前綴、卡名照表，不改名）。"""
    out: List[Dict[str, Any]] = []
    for r in parse_map(existing_text):
        for card in r["cards"]:
            if _find_card(dirs, card):
                continue
            prefix = (r["prefixes"][0] + "/") if r["prefixes"] else ""
            out.append({"prefix": prefix, "part": r["part"], "card": card, "status": r["status"] or STATUS_SKELETON,
                        "files": 0, "hot": 0, "layer": r["layer"] or DEFAULT_LAYER, "reused": False, "path": None})
    return out


def write_scaffold(root: Path, rows: List[Dict[str, Any]], lv1: Optional[str], *, write: bool = False,
                   merge_missing: bool = False, root_label: str = "",
                   layer: Optional[Tuple[str, Path]] = None) -> Dict[str, Any]:
    """write=False（預設）只定名＋預驗不落檔。表存在且非 merge_missing → ScaffoldError（永不覆寫）。
    順序：定卡名（沿用／避撞）→ 逐張寫卡（失敗即停、不撤回、result["ok"]=False）→ 全部卡在了才寫表。"""
    root = Path(root)
    map_path = root / MAP_REL
    kind, layer_root = layer or detect_layer(root)
    kwargs, dirs = card_write_kwargs(kind, layer_root, lv1), card_dirs(kind, layer_root)
    exists = map_path.is_file()
    if exists and not merge_missing:
        raise ScaffoldError(f"部位表已存在，不覆寫：{map_path}（只補缺列用 --merge-missing）")
    if exists:
        old = map_path.read_text(encoding="utf-8")
        taken = {c for r in parse_map(old) for c in r["cards"]}
        have = {p for r in parse_map(old) for p in r["prefixes"]}
        added = resolve_card_names([r for r in rows if r["prefix"].rstrip("/").lower() not in have], dirs, taken)
        text, added = merge_missing_rows(old, added)
        missing = rows_missing_cards(old, dirs)
        card_rows = added + [m for m in missing if m["card"] not in {a["card"] for a in added}]
        old_rows = len(parse_map(old))
    else:
        added = resolve_card_names(list(rows), dirs)
        text, card_rows, old_rows = render_table(added, root_label or root.name), added, 0
    if len(parse_map(text)) < old_rows + len(added):
        raise ScaffoldError("渲染出的表讀不回（parse_map 列數少於草稿），不落檔")
    cards = write_cards(card_rows, kwargs, write)
    result = {"map": str(map_path), "layer": kind, "layer_root": str(layer_root), "merged": exists,
              "rows": len(added), "cards_planned": len(card_rows), "table": text, "written": False, **cards}
    if not cards["ok"] or not write:
        return result
    if added:
        write_text_lf(map_path, text)
        result["written"] = True
    return result


# ─── 對帳與首次提示 ──────────────────────────────────────────────────

def _card_files(dirs: List[Path]) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    for d in dirs:
        try:
            for p in sorted(d.rglob("*.md")):
                if (p.stem.endswith(CARD_SUFFIX) or "部位" in p.stem) and p.stem not in out:
                    out[p.stem] = p
        except OSError:
            continue
    return out


def _find_card(dirs: List[Path], card: str) -> List[Path]:
    for d in dirs:
        try:
            for name in (card, card.replace("_", "-")):
                hits = sorted(d.rglob(name + ".md"))
                if hits:
                    return hits
        except OSError:
            continue
    return []


def _dirs_for(root: Path, mem_dir: Optional[Path]) -> List[Path]:
    if mem_dir is not None:
        return [Path(mem_dir)]
    return card_dirs(*detect_layer(root))


def check_consistency(root: Path, text: Optional[str] = None, mem_dir: Optional[Path] = None) -> List[str]:
    """三種不一致各一訊息：表卡名無檔、卡的部位與表的部位不符（Part 不符）、卡有表無。"""
    root = Path(root)
    dirs = _dirs_for(root, mem_dir)
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
            hits = _find_card(dirs, card)
            if not hits:
                where = r["prefixes"][0] if r["prefixes"] else "?"
                issues.append(f"表卡名無檔：列 `{where}` 的卡 `{card}` 在 {'、'.join(map(str, dirs))} 找不到")
                continue
            part = card_part(hits[0])
            if part and part not in (r["part"], r["part_short"]):
                issues.append(f"Part 不符：卡 `{card}` 寫部位 `{part}`，表列是 `{r['part']}`")
    for stem, p in _card_files(dirs).items():
        if stem in table_cards:
            continue
        part = card_part(p)
        if part and part not in parts:
            issues.append(f"卡有表無：卡 `{stem}` 的部位 `{part}` 不在表上（{p}）")
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
    dirs = _dirs_for(root, mem_dir)
    lines = [f"[Guardian:OverviewHub] 部位表有 {len(skeleton)} 列還是「骨架」，改這些部位前先補卡的空段："]
    for r in skeleton:
        for card in r["cards"] or ["（表上沒卡）"]:
            hits = _find_card(dirs, card)
            empties = empty_sections(hits[0].read_text(encoding="utf-8", errors="replace")) if hits else list(SECTIONS)
            where = "" if hits else "（卡檔不存在）"
            lines.append(f"- {r['part']}：`{card}`{where} 空段：{'、'.join(empties) if empties else '無'}")
    return "\n".join(lines)
