"""wg_overview — OverviewHub 的 state 層：三個 hook 各呼叫一個函式。

做什麼：第一次碰到某部位（Read／Bash 讀檔、提示詞提到路徑、或直接 Edit）就依本回合意圖（state["turn_intent"]）
查 goal_weights 選片注入該部位導讀卡（沒片命中退整卡），一個 session 一個部位只注入一次；之後記「注入後讀了
哪些檔、其中幾個是部位檔」；改檔前三項證據缺一即 deny：導讀卡已注入（不可關）、讀過部位檔 ≥N、交了定位三行
（三行在 thinking 交的放行附提醒）。部位表類別 knowledge 的部位（文件、記憶、派工信箱）只要第一項。
readonly_paths 命中一律 deny 不注入；transcript 讀不到視為環境異常，deny。
沒有部位表的專案（或表上沒列的檔）改前只要求本 session 讀過同頂層目錄 ≥N 個檔。設定四層深合併（_cfg）、
設定錯誤時 Edit 一律擋。每個事件各落一行 jsonl 到 workflow/_overview-hub.log 當量測資料。

state["overview_hub"] = {
  "<root>|<part>": {"injected_turn", "injected_at", "transcript_offset", "intent", "slices", "card_paths",
                     "reads_after": [...], "part_files_read": [...], "depends_files_read": [...],
                     "located": bool, "located_via", "located_quality", "edits": n, "locate_template"},
  "<root>|(unmapped)<top_dir>": {"part_files_read": [...], "edits": n}
}
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (
    CLAUDE_DIR, CONFIG_PATH, _atom_debug_error, _layer_kind_for_root, _map_path_of,
    org_memory_root, resolve_project_root,
)
from wg_verify_ledger import vcs_root_of

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))   # 程式碼用本檔位置，CLAUDE_DIR 只定位資料
from hub_config import (  # noqa: E402
    HUB_DEFAULTS, HUB_REL, INTENT_KEYS, KNOWN_KEYS, RETIRED_KEYS, encoding_ok, merge_hub_cfg, validate_hub_cfg,
)
import overview_hub as _oh  # noqa: E402
from overview_hub import (  # noqa: E402
    DEFAULT_LOCATE_TEMPLATE, LOCATE_CHANNELS, MAP_REL, ROOT_CAUSE_SENTENCE, SLICE_NAMES, assistant_text_after,
    build_injection_ex, card_mem_dir, find_map, locate_quality, locate_values, match_row, parse_map, read_paths_from_tool, resolve_card,
    split_card_sections, top_dir, transcript_readable, transcript_size,
)

import wg_release_rules as _rr  # noqa: E402  放行／欠帳判定規則（GREP_CONTENT_IS_READ、BASH_COMMENT_LINES_STRIPPED、RUNTIME_DATA_NO_OVERVIEW、TEMP_COPY_NOT_PROJECT）

LOG_PATH = CLAUDE_DIR / "workflow" / "_overview-hub.log"   # _*.log 不進版控
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_TEMP_ROOTS: List[str] = []


def _long(p: str) -> str:
    """目標側也展成長路徑（與暫存根同一種表示；8.3 短路徑的 TEMP）。"""
    try:
        from handlers._shared import _comparable
        return _comparable(p)
    except Exception:  # noqa: BLE001
        return p


def _temp_roots() -> List[str]:
    """暫存根（規則 TEMP_COPY_NOT_PROJECT 的事實）；WG_TEMP_RULES=off 時每次都回關閉值（案例把假專案建在 tmp 下）。"""
    if str(os.environ.get("WG_TEMP_RULES", "")).lower() == "off":
        return list(_rr.TEMP_DISABLED)
    if not _TEMP_ROOTS:
        try:
            from handlers._shared import _comparable      # 8.3 短路徑展成長路徑，與目標側同一種表示
        except ImportError:
            _comparable = str
        _TEMP_ROOTS.extend(_rr.norm_temp_path(_comparable(r)) for r in _rr.temp_roots(tempdir=tempfile.gettempdir()))
    return _TEMP_ROOTS

# A5.1 前例行填空範本：只能填存在的卡名、「無」、或「待規格：<理由>」；照抄這句不算交（登進 overview_hub 的範本句表，
# locate_groups 對任何 template 都會剔除；overview_hub.py 是軌 A α 的檔，這裡以擴充 tuple 登記、不改原檔）
PRECEDENT_TEMPLATE = "<卡名>／無／待規格：<理由>"
if PRECEDENT_TEMPLATE not in _oh._TEMPLATE_PHRASES:
    _oh._TEMPLATE_PHRASES = tuple(_oh._TEMPLATE_PHRASES) + (PRECEDENT_TEMPLATE,)
IDLE_SCAN_LINE = ("[Guardian:OverviewHub] 沒有指定任務 → 主動掃視：跑 `project_smells(part)` 看候選前 N、看部位表還是「骨架」的列、"
                  "看健檢紅燈；挑一個說出來（部位＋為什麼）再動手。")
_CANDIDATE_QUESTIONS = ("① 這些候選裡哪一個是你這次要修的問題的根因所在？為什麼不是另一個？",
                        f"② {ROOT_CAUSE_SENTENCE}")

# 設定的預設、四層合併與驗證全在 lib/hub_config.py（導讀卡、量尺閘、project-smells 共用同一份）；這裡只留別名給既有呼叫端
_DEFAULT = HUB_DEFAULTS
_KNOWN_KEYS = KNOWN_KEYS
_RETIRED_KEYS = RETIRED_KEYS
_encoding_ok = encoding_ok
_LAYER_SPLIT_RE = re.compile(r"[／/、,，;；]")
_WARNED: set = set()                               # 行程內只警告一次的鍵
_ORG_ROOT_CACHE: List[Optional[Path]] = []         # 行程內快取公司根（[] 未查、[None] 未接上、[Path] 接上）


def _org_root() -> Optional[Path]:
    if not _ORG_ROOT_CACHE:
        _ORG_ROOT_CACHE.append(org_memory_root())
    return _ORG_ROOT_CACHE[0]


def _warn_once(key: str, msg: str) -> None:
    if key in _WARNED:
        return
    _WARNED.add(key)
    sys.stderr.write(f"[Guardian:OverviewHub] {msg}\n")


def _same_dir(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except (OSError, ValueError):
        return False


def _warn_retired(retired: List[str]) -> None:
    for key in retired:
        _warn_once(f"retired:{key}", f"設定鍵「{key}」已退役（閘一律擋，明寫也不放行），請從 overview-hub.json／config.json 移除")


def _validate_cfg(c: Dict[str, Any], root: Optional[Path]) -> List[str]:
    """合併後設定的錯誤清單（空＝通過；規則在 hub_config.validate_hub_cfg）；退役鍵只警告一次。"""
    errors, retired = validate_hub_cfg(c, root)
    _warn_retired(retired)
    return errors


def _cfg(config: Dict[str, Any], root: Optional[Path] = None) -> Dict[str, Any]:
    """四層深合併（hub_config.merge_hub_cfg）：預設 < config.json overview_hub < 公司層 < 專案層 overview-hub.json。

    這裡只補呼叫端的事：公司根（行程內快取）、錯誤與退役鍵各警告一次、驗證器內部錯誤進 atom-debug log、
    `_layer`（root／org／project_mapped／project_unmapped／none）。回傳必帶 `_errors`（非空時 on_edit deny）。
    """
    org = _org_root()
    c = merge_hub_cfg(config, org, root)
    internal = c.pop("_internal_error", None)
    if internal is not None:
        _atom_debug_error("overview_hub:validate", internal)
    _warn_retired(c.get("_retired") or [])
    for e in c["_errors"]:
        _warn_once(f"error:{root}:{e}", f"設定錯誤（{root or '根層'}）：{e}")
    c["_layer"] = "none" if root is None else _layer_kind_for_root(root, org)
    return c


def _log(event: str, session_id: str, **kw: Any) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "event": event,
                                "session": session_id[:8], **kw}, ensure_ascii=False) + "\n")
    except OSError as e:
        sys.stderr.write(f"[Guardian:OverviewHub] log 寫入失敗（不影響注入）：{e}\n")


def _lookup(path: str, stop_at: Optional[Path] = None) -> Optional[Tuple[Path, Dict[str, Any]]]:
    """路徑 → (專案根, 命中的表列)；找不到表或沒命中回 None；表存在卻讀不到拋 MapReadError（量尺閘不能把它當成沒有量尺）。
    stop_at：往上找表到這層就停（見 find_map）。"""
    found = find_map(path, stop_at)
    if not found:
        return None
    root, map_path = found
    try:
        rows = parse_map(map_path.read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        raise MapReadError(f"部位表 {map_path} 存在但讀不到（{type(e).__name__}: {e}）") from e
    row = match_row(path, root, rows)
    return (root, row) if row else None


class MapReadError(RuntimeError):
    """部位表找到了（find_map 確認檔案存在）卻讀不到：跟「沒有表／沒命中」是兩回事。量尺閘靠 _lookup 決定改檔屬於哪個部位，
    讀不到表就不知道該部位有沒有尺，不能當成「沒有量尺」靜默跳過；stop._verify_gates 接到這個例外走判定錯誤路徑（一律擋＋stderr
    ＋guard_log）。注入／讀檔記錄那幾條路（_lookup_quiet）照舊當沒命中，但在 stderr 說一聲。"""


def _lookup_quiet(path: str, stop_at: Optional[Path] = None) -> Optional[Tuple[Path, Dict[str, Any]]]:
    """_lookup 給注入與讀檔記錄用的版本：表讀不到 → stderr 一行、回 None（這幾條路不是閘，不為此中斷 hook）。"""
    try:
        return _lookup(path, stop_at)
    except MapReadError as e:
        sys.stderr.write(f"[Guardian:OverviewHub] {e}；這次當成沒命中部位表\n")
        return None


def _project_root_of(path: str) -> Optional[Path]:
    """沒命中任何表列時：檔案落在哪個專案根（宣告認領或四標記）；家目錄／磁碟根／無標記回 None。"""
    if not path or resolve_project_root is None:
        return None
    try:
        p = Path(path)
        if not p.is_absolute():
            return None
        return resolve_project_root(str(p if p.is_dir() else p.parent)).path
    except (OSError, ValueError):
        return None


def _unmapped_root_of(path: str) -> Optional[Path]:
    """無表那條路（改檔閘與讀檔記錄共用，兩邊根要一致）：_project_root_of 找不到、且往上沒有任何部位表時，
    退 VCS 根（.git／.svn，不設層數上限；家目錄與磁碟根不算）。有部位表的專案不走退路，行為不變。"""
    root = _project_root_of(path)
    if root is not None or not path or find_map(path):
        return root
    return vcs_root_of(path)


def _root_key(root: Path) -> str:
    return str(root).replace(chr(92), "/").lower()


def _key(root: Path, row: Dict[str, Any]) -> str:
    return f"{_root_key(root)}|{row['part_short']}"


def _unmapped_key(root: Path, path: str) -> str:
    return f"{_root_key(root)}|(unmapped){top_dir(path, root)}"


def _rel_to_root(path: str, root: Path) -> Optional[str]:
    p, r = path.replace("\\", "/").lower(), _root_key(root).rstrip("/")
    return p[len(r) + 1:] if p.startswith(r + "/") else None


def _migrate_rec(rec: Dict[str, Any]) -> Dict[str, Any]:
    """main 時代寫出的 rec 只有 reads_after／located／edits；升級後既有 session 的 state 直接用會 KeyError。入口補齊新欄。"""
    rec.setdefault("part_files_read", [])
    rec.setdefault("depends_files_read", [])
    rec.setdefault("slices", [])
    rec.setdefault("intent", "general")
    rec.setdefault("card_paths", [])
    rec.setdefault("reads_after", [])
    rec.setdefault("edits", 0)
    rec.setdefault("edited_files", {})
    rec.setdefault("reinjected_after_compact", False)
    rec.setdefault("root", "")
    rec.setdefault("layer", "")
    rec.setdefault("part", "")
    return rec


def _is_readonly(path: str, root: Path, cfg: Dict[str, Any]) -> Optional[str]:
    """readonly_paths（glob）命中 → 回命中的樣式；不命中回 None。`**/` 也配零層。
    基準 root＝這次命中的部位表所在根（無表專案＝resolve_project_root 的根），不是宣告那條 pattern 的設定檔所在層：
    根層 hub.json 的 pattern 經四層合併後，對專案檔也是以專案根相對路徑比對。"""
    rel = _rel_to_root(path, root)
    if rel is None:
        return None
    for pat in cfg.get("readonly_paths") or []:
        p = pat.replace("\\", "/").strip("/").lower()
        if fnmatch.fnmatchcase(rel, p) or ("**/" in p and fnmatch.fnmatchcase(rel, p.replace("**/", ""))):
            return pat
    return None


def _intent_of(state: Dict[str, Any]) -> str:
    v = state.get("turn_intent")
    return v if isinstance(v, str) and v in INTENT_KEYS else "general"


def _cards_for(root: Path, row: Dict[str, Any], cfg: Dict[str, Any]) -> List[Path]:
    """表列的導讀卡檔（找得到的）。卡片目錄由 card_mem_dir 決定：根層與根層 worktree 在 `<根>/memory`，其他專案在 `<根>/.claude/memory`。"""
    if row["status"] not in ("有", "部分", "索引"):
        return []
    mem_dir = card_mem_dir(root, CLAUDE_DIR)
    return [cp for cp in (resolve_card(root, c, mem_dir) for c in row["cards"]) if cp]


CARD_SEARCH_BUDGET_S = 1.5
_CARD_SEARCH_SKIP = (".git", "node_modules", "_distant")
_clock = time.monotonic


def _needs_card(row: Dict[str, Any]) -> bool:
    """表上狀態有／部分／索引、且寫了卡名的列：卡一定要找得到。"""
    return row["status"] in ("有", "部分", "索引") and bool(row["cards"])


def _card_name_matches(card: str, stem: str) -> bool:
    """表上卡名對檔名主幹（不分大小寫，底線換連字號的變體也算）；卡名含 `*` 時沿用 glob 語意（fnmatch）。"""
    stem = stem.lower()
    return any(fnmatch.fnmatchcase(stem, n.lower()) if "*" in n else stem == n.lower()
               for n in (card, card.replace("_", "-")))


def _search_cards(root: Path, cards: List[str], budget_s: float = CARD_SEARCH_BUDGET_S,
                  bases: Optional[Tuple[Path, ...]] = None) -> Dict[str, Any]:
    """_cards_for 回空時接著搜：bases 依序往下找 <卡名>.md（含底線換連字號；略過 .git、node_modules、_distant、.claude/worktrees；
    總時限 budget_s 秒）。bases 預設是 <根>/memory/、_AIDocs/_atoms/、.claude/memory/，再整個根。
    回 {"found": [卡檔], "missing": [找不到的卡名], "searched": [找過的位置], "timed_out": bool}。"""
    deadline = _clock() + budget_s
    found: Dict[str, Path] = {}
    searched: List[str] = []
    done: List[str] = []
    timed_out = False
    for base in bases or (root / "memory", root / "_AIDocs" / "_atoms", root / ".claude" / "memory", root):
        if timed_out or len(found) == len(cards):
            break
        if not base.is_dir():
            continue
        searched.append(str(base))
        for dirpath, dirnames, filenames in os.walk(base):
            if _clock() > deadline:
                timed_out = True
                break
            dp = Path(dirpath)
            dirnames[:] = [d for d in dirnames if d not in _CARD_SEARCH_SKIP and str(dp / d) not in done
                           and not (d == "worktrees" and dp.name == ".claude")]
            for fn in filenames:
                if not fn.lower().endswith(".md"):
                    continue
                for c in cards:
                    if c not in found and _card_name_matches(c, fn[:-3]):
                        found[c] = dp / fn
            if len(found) == len(cards):
                break
        done.append(str(base))
    return {"found": [found[c] for c in cards if c in found], "missing": [c for c in cards if c not in found],
            "searched": searched, "timed_out": timed_out}


def _resolve_row_cards(root: Path, row: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[List[Path], Optional[Dict[str, Any]]]:
    """表列的卡：先 _cards_for（預設目錄），表上卡名對不到找到的檔的那幾張再 _search_cards。卡片目錄（card_mem_dir）不在
    root 底下＝根層 worktree，卡是資料、權威在 live：補搜只找資料根的 memory/ 與 _AIDocs/_atoms/，不從 worktree 撿開分支時的
    舊副本；live 根層與一般專案照原本的位置補搜。回 (全部找到的卡檔, 搜尋結果或 None)；搜尋結果 missing 非空＝有卡找不到。"""
    paths = _cards_for(root, row, cfg)
    if not _needs_card(row):
        return paths, None
    stems = [p.stem.lower() for p in paths]
    absent = [c for c in row["cards"] if not any(_card_name_matches(c, s) for s in stems)]
    if not absent:
        return paths, None
    mem_dir = card_mem_dir(root, CLAUDE_DIR)
    inside = os.path.normcase(os.path.abspath(mem_dir)).startswith(os.path.normcase(os.path.abspath(root)) + os.sep)
    miss = _search_cards(root, absent, bases=None if inside else (mem_dir, mem_dir.parent / "_AIDocs" / "_atoms"))
    return paths + miss["found"], miss


def _missing_card_msg(row: Dict[str, Any], miss: Dict[str, Any]) -> str:
    cards = "、".join(f"`{c}`" for c in miss["missing"])
    where = "、".join(miss["searched"]) or "（沒有可搜的目錄）"
    state = f"；搜尋逾時（{CARD_SEARCH_BUDGET_S} 秒）沒搜完" if miss["timed_out"] else "；已搜完"
    return (f"[Guardian:OverviewHub] 部位【{row['part_short']}】表上寫的導讀卡 {cards} 在 repo 裡找不到（找過：{where}{state}）。"
            "不准繞過（不准改寫表、不准改用其他卡、不准用 Bash 寫檔）：停下來告訴使用者這張卡不見了，等使用者補卡或改表。")


def _locate_template(cfg: Dict[str, Any]) -> List[str]:
    """定位三行的範本句：專案 locate_template 給幾句用幾句，其餘補預設；第三句（前例）沒自訂時用填空範本（A5.1）。"""
    custom = cfg.get("locate_template") if isinstance(cfg.get("locate_template"), list) else []
    t = (list(custom) + DEFAULT_LOCATE_TEMPLATE[len(custom):])[:3]
    if len(custom) < 3:
        t[2] = PRECEDENT_TEMPLATE
    return t


def _tracking_for(root: Path, row: Dict[str, Any]) -> List[Dict[str, Any]]:
    """這個專案追蹤帳本裡、這個部位（part 或 part_short）仍 open 的項目；讀不到只 stderr，不擋注入。"""
    try:
        from wg_harvest import tracking_items_for_part, tracking_slug
        return tracking_items_for_part(tracking_slug(str(root)), [row.get("part"), row.get("part_short")])
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:Tracking] 讀追蹤項失敗（不擋注入）：{type(e).__name__}: {e}", file=sys.stderr)
        return []


def _inject(state: Dict[str, Any], session_id: str, root: Path, row: Dict[str, Any],
            hit_path: str, via: str, transcript_path: str, cfg: Dict[str, Any]) -> str:
    card_paths, miss = _resolve_row_cards(root, row, cfg)
    card_path = card_paths[0] if card_paths else None
    template = _locate_template(cfg)
    extra = (cfg.get("locate_extra") or {}).get(row["part_short"]) if isinstance(cfg.get("locate_extra"), dict) else None
    intent = _intent_of(state)
    gw = (cfg.get("goal_weights") or {}).get(intent) or {}
    kind = _oh.path_kind(hit_path, root) or _oh.KIND_CODE
    text, used = build_injection_ex(row, card_paths, hit_path, int(cfg["max_card_chars"]), template, extra,
                                    list(gw.get("slices") or []), str(gw.get("lens") or ""), str(gw.get("ask_first") or ""),
                                    knowledge=kind == _oh.KIND_KNOWLEDGE)
    if miss:
        text += "".join(f"\n表上的卡在 {p}，不在預設目錄；請更新表或搬卡" for p in miss["found"])
        if miss["missing"]:
            text += "\n" + _missing_card_msg(row, miss)
    tracked = _tracking_for(root, row)
    if tracked:
        from wg_harvest import tracking_block
        text = f"{text}\n{tracking_block(tracked, int(cfg['max_card_chars']))}"
    hub = state.setdefault("overview_hub", {})
    hub[_key(root, row)] = {
        "injected_turn": int(state.get("turn_seq", 0)),
        "injected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "transcript_offset": transcript_size(transcript_path),
        "intent": intent,
        "slices": used,
        "card_paths": [str(cp) for cp in card_paths],
        "reads_after": [],
        "part_files_read": [],
        "depends_files_read": [],
        "located": False,
        "edits": 0,
        "edited_files": {},
        "reinjected_after_compact": False,
        "root": str(root),
        "part": row["part"] or row["part_short"],
        "layer": row.get("layer") or "",
        "kind": kind,                     # knowledge 部位不要求定位三行；scorecard 的 S3 只算 code 部位
        "locate_template": template,
        "cards_missing": ({k: miss[k] for k in ("missing", "searched", "timed_out")}
                          if miss and miss["missing"] else None),
    }
    _log("inject", session_id, part=row["part_short"], status=row["status"], via=via, path=hit_path,
         card=str(card_path) if card_path else None, chars=len(text), intent=intent, slices=used, layer=cfg.get("_layer"))
    return text


# ─── 候選填空（A5.2～A5.4）────────────────────────────────────────────

def defects_top_n(card_paths: List[Any], n: int) -> List[str]:
    """導讀卡「已知病灶」片的前 n 條 bullet（跨多張卡依序取）；讀不到的卡略過。post_compact 重注也用這把。"""
    out: List[str] = []
    for cp in card_paths or []:
        try:
            body = Path(cp).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        sec = split_card_sections(body)["slices"].get("defects") or ""
        for line in sec.splitlines():
            s = line.strip()
            if s.startswith("- ") and len(out) < n:
                out.append(s)
        if len(out) >= n:
            break
    return out


_GENERATED_AT_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_LINE_CAP = 200   # 候選每列（reason／病灶）上限，與 max_card_chars // N 取小
_SMELLS_STR_FIELDS = ("part", "category", "kind", "reason")


def _smells_rows(path: Path) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[float]]:
    """smells 報告 → (列清單, 解析錯誤, generated_at 時間戳)。json（list 或 {rows|items|smells}，可帶 generated_at）／
    jsonl（一行一筆）／md 表（| 路徑 | 分類 | 理由 | 部位? |）。讀不到、壞 JSON、JSONL 壞行、頂層格式不收 → 錯誤字串（照舊回能解析的列）。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [], f"讀不到：{e}", None
    rows: List[Any] = []
    err: Optional[str] = None
    gen_ts: Optional[float] = None
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        bad = 0
        for i, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                bad += 1
                err = err or f"第 {i} 行不是 JSON"
        if bad:
            err = f"{bad} 行不是 JSON（{err}）"
    elif suffix == ".md":
        for line in text.splitlines():
            if not line.strip().startswith("|") or set(line.replace("|", "").strip()) <= set("-: "):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 3 or cells[0] in ("路徑", "path", "檔案"):
                continue
            rows.append({"path": cells[0].strip("`"), "category": cells[1], "reason": cells[2],
                         **({"part": cells[3]} if len(cells) > 3 else {})})
    else:
        try:
            data = json.loads(text)
        except ValueError as e:
            return [], f"不是合法 JSON：{e}", None
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict) and any(isinstance(data.get(k), list) for k in ("rows", "items", "smells")):
            rows = next(data[k] for k in ("rows", "items", "smells") if isinstance(data.get(k), list))
            raw_gen = data.get("generated_at")
            m = _GENERATED_AT_RE.match(str(raw_gen or ""))
            if m:
                try:   # 0000-01-01、13 月、9999 年這類值 mktime 會拋；退回 mtime 並記一筆
                    gen_ts = time.mktime((int(m.group(1)), int(m.group(2)), int(m.group(3)), 0, 0, 0, 0, 0, -1))
                except (OverflowError, ValueError, OSError):
                    gen_ts = None
                    err = f"generated_at 無法換算：{raw_gen}"
        else:
            err = "頂層要是陣列或含 rows／items／smells 陣列的物件"
    # 報告是外部輸入：path 必須是非空字串；part／category／kind／reason 有值就必須是字串，否則整列丟棄並計數
    good: List[Dict[str, Any]] = []
    bad_type = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        if not isinstance(r.get("path"), str) or not r["path"].strip():
            if r.get("path") not in (None, ""):
                bad_type += 1
            continue
        if any(r.get(k) is not None and not isinstance(r.get(k), str) for k in _SMELLS_STR_FIELDS):
            bad_type += 1
            continue
        good.append(r)
    if bad_type:
        msg = f"{bad_type} 列欄位型別不對（path／part／category／kind／reason 要字串）"
        err = f"{err}；{msg}" if err else msg
    return good, err, gen_ts


def _clip(s: str, k: int) -> str:
    s = str(s)
    return s if len(s) <= k else s[:k] + f"…（截 {len(s) - k} 字）"


def _smells_lines(root: Path, cfg: Dict[str, Any], parts: Optional[Tuple[str, ...]], n: int,
                  line_cap: int) -> Tuple[List[str], List[str], str]:
    """smells_report → (候選列, 附註列, 來源字樣)。parts=None＝全專案不濾部位。過期（generated_at 優先、否則 mtime）附一行仍送；
    解析失敗附一行「解析失敗」讓呼叫端退病灶段，不跟「真的沒候選」混在一起。"""
    report = str(cfg.get("smells_report") or "").strip()
    if not report:
        return [], [], ""
    rp = Path(report)
    if not rp.is_absolute():
        rp = root / rp
    if not rp.is_file():
        return [], [f"（smells_report 指到的報告不存在：{rp}）"], ""
    rows, err, gen_ts = _smells_rows(rp)
    notes = [f"（報告 {rp} 解析失敗：{err}）"] if err else []
    if parts is not None:
        rows = [r for r in rows if not r.get("part") or r["part"] in parts]
    rows.sort(key=lambda r: -float(r["score"]) if isinstance(r.get("score"), (int, float)) else 0)
    lines = [_clip(f"- {r['path']}｜{r.get('category') or r.get('kind') or '?'}｜"
                   f"{(('【' + r['part'] + '】') if parts is None and r.get('part') else '')}{r.get('reason') or '（沒寫理由）'}",
                   line_cap) for r in rows[:n]]
    if not lines:
        return [], notes, ""
    try:
        ts = gen_ts if gen_ts is not None else rp.stat().st_mtime
        age = max(0, int((time.time() - ts) // 86400))
    except OSError:
        age = 0
    max_age = int(cfg.get("smells_max_age_days") or 0)
    if age > max_age:
        notes.append(f"（報告已 {age} 天沒更新，超過 smells_max_age_days={max_age}；仍送，先重跑 smells_cmd 再信它）")
    return lines, notes, f"smells 報告 {rp}"


def _candidates_block(root: Path, rows: List[Dict[str, Any]], cfg: Dict[str, Any], max_chars: Optional[int] = None,
                      label: Optional[str] = None, compact_empty: bool = False) -> str:
    """候選前 N＋根因卡＋兩問。rows＝一列（該部位）或整張表（全專案，label 給「全專案」）。
    來源：smells_report（過期附一行仍送、壞格式附一行解析失敗）→ 沒有就退導讀卡病灶段前 N（全專案時各部位輪流取）→ 都沒有明說「無候選」。
    compact_empty（改檔路徑用）：都沒有時只回一行，不附根因卡與兩問；報告不存在／解析失敗的附註接在同一行。
    使用者問根因（on_prompt 觸發詞）不縮，仍送根因卡與兩問。
    字數：每列截 min(200, max_card_chars // N)；整塊截 max_chars（預設 max_card_chars），卡名與兩問一定保留。"""
    n = int(cfg.get("candidate_top_n") or 0)
    cap = int(max_chars if max_chars is not None else cfg.get("max_card_chars") or 6000)
    line_cap = min(_LINE_CAP, int(cfg.get("max_card_chars") or 6000) // max(n, 1))
    whole = label is not None
    parts = None if whole else tuple(x for x in (rows[0]["part"], rows[0]["part_short"]) if x)
    lines, notes, source = _smells_lines(root, cfg, parts, n, line_cap)
    card_paths: List[Path] = []
    per_part: List[List[str]] = []
    for r in rows:
        cps = _cards_for(root, r, cfg)
        card_paths.extend(cp for cp in cps if cp not in card_paths)
        if not lines:
            pref = f"【{r['part_short']}】" if whole else ""
            per_part.append([_clip(pref + d, line_cap) for d in defects_top_n(cps, n)])
    if not lines:
        merged: List[str] = []
        for i in range(n):   # 各部位輪流取第 i 條，避免全被表上第一個部位佔滿
            merged.extend(p[i] for p in per_part if i < len(p))
        lines = merged[:n]
        source = "導讀卡「已知病灶」段" if lines else ""
    if not lines and compact_empty:
        return (f"[Guardian:OverviewHub] 【{label or rows[0]['part_short']}】候選：無"
                f"（補導讀卡「已知病灶」段或設 smells_report）" + "".join(notes))
    if not lines:
        lines = ["候選：無（沒有可用的 smells 報告也沒有病灶段；先補導讀卡「已知病灶」段或在 overview-hub.json 設 smells_report）"]
        source = "無"
    head = f"[Guardian:OverviewHub] 【{label or rows[0]['part_short']}】候選前 {n}（來源：{source}）："
    cards = _clip("、".join(f"`{cp.stem}`（{cp}）" for cp in card_paths) or "無（表上沒卡）", max(line_cap, cap // 4))
    tail = [f"根因卡：{cards}", "先答兩問：" + "；".join(_CANDIDATE_QUESTIONS)]
    body = "\n".join([*notes, *lines])
    room = cap - len(head) - sum(len(t) + 1 for t in tail) - 1
    if len(body) > room:
        keep = max(room - 40, 0)   # 40＝截斷附註本身的長度預留，整塊仍 ≤ cap
        body = body[:keep] + f"\n…（候選區塊超過 {cap} 字，截 {len(body) - keep} 字）"
    return "\n".join([head, body, *tail])


def _row_for_key(root: Path, part_short: str) -> Optional[Dict[str, Any]]:
    mp = _map_path_of(root)
    if mp is None:
        return None
    try:
        rows = parse_map(mp.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return next((r for r in rows if r["part_short"] == part_short), None)


def _hit_trigger(prompt: str, triggers: Any) -> Optional[str]:
    low = (prompt or "").lower()
    return next((t for t in (triggers or []) if isinstance(t, str) and t and t.lower() in low), None)


def _mapped_recs(state: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """已注入的部位紀錄（排除無表 key），附 key；舊 rec 補欄。"""
    out = []
    for key, rec in (state.get("overview_hub") or {}).items():
        if "(unmapped)" in key:
            continue
        out.append((key, _migrate_rec(rec)))
    return out


def _table_rows(root: Path) -> List[Dict[str, Any]]:
    mp = _map_path_of(root)
    if mp is None:
        return []
    try:
        return parse_map(mp.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return []


def _candidates_error_line(session_id: str, e: Exception, **kw: Any) -> str:
    """候選產生失敗：回一行給模型（不影響閘的判定與同回合其他注入）並落 log candidates_error，traceback 進 atom-debug。"""
    _log("candidates_error", session_id, error=f"{type(e).__name__}: {e}", **kw)
    _atom_debug_error("overview_hub:candidates", e)
    return f"[Guardian:OverviewHub] 候選產生失敗：{type(e).__name__}: {e}（不影響本次放行）"


def _candidates_on_trigger(state: Dict[str, Any], session_id: str, prompt: str, config: Dict[str, Any]) -> List[str]:
    """提示詞命中 root_cause_triggers（用該專案根合併後的 cfg 判，專案層覆蓋有效）→ 送候選，每個 key 一 session 一次
    （state["candidates_sent"]）。已注入過部位 → 逐部位送（key＝部位 key）；本 session 還沒注入任何部位 → 用 cwd 的專案表
    送一次「全專案候選前 N」（key＝`<root>|(all)`）。多塊一起送時總量也受 max_card_chars 限制（平分給各塊）。"""
    sent = state.setdefault("candidates_sent", [])
    targets: List[Tuple[str, Path, List[Dict[str, Any]], Dict[str, Any], str, Optional[str]]] = []
    recs = _mapped_recs(state)
    if recs:
        for key, rec in recs:
            if key in sent or not rec.get("root"):
                continue
            root = Path(rec["root"])
            row = _row_for_key(root, key.split("|", 1)[1])
            if row is None:
                continue
            cfg = _cfg(config, root)
            word = _hit_trigger(prompt, cfg.get("root_cause_triggers"))
            if cfg["enabled"] and word:
                targets.append((key, root, [row], cfg, word, None))
    else:
        found = find_map(str((state.get("session") or {}).get("cwd") or ""))
        if found:
            root = found[0]
            key = f"{_root_key(root)}|(all)"
            cfg = _cfg(config, root)
            word = _hit_trigger(prompt, cfg.get("root_cause_triggers"))
            rows = _table_rows(root)
            if key not in sent and cfg["enabled"] and word and rows:
                targets.append((key, root, rows, cfg, word, "全專案"))
    if not targets:
        return []
    total = min(int(t[3].get("max_card_chars") or 6000) for t in targets)
    each = max(total // len(targets), 1)
    out: List[str] = []
    for key, root, rows, cfg, word, label in targets:
        out.append(_candidates_block(root, rows, cfg, each, label))
        sent.append(key)
        _log("candidates", session_id, part=label or rows[0]["part_short"], trigger=word, via="prompt", layer=cfg.get("_layer"))
    return out


def _card_texts(rec: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for cp in rec.get("card_paths") or []:
        try:
            out.append(Path(cp).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return out


def _record_read(state: Dict[str, Any], p: str, hit: Optional[Tuple[Path, Dict[str, Any]]]) -> None:
    """注入後讀的每個檔都記到所有已注入的部位（跨部位探索正是綜觀）；命中部位的檔另記 part_files_read；
    路徑字面出現在該部位卡片裡的檔記 depends_files_read；沒表列但在專案內的檔記到無表 key。"""
    hub = state.get("overview_hub") or {}
    for key, rec in hub.items():
        if "(unmapped)" in key:
            continue
        _migrate_rec(rec)
        if p not in rec["reads_after"]:
            rec["reads_after"].append(p)
    if hit:
        rec = hub.get(_key(*hit))
        if rec is not None:
            if p not in rec["part_files_read"]:
                rec["part_files_read"].append(p)
            norm = p.replace("\\", "/")
            if p not in rec["depends_files_read"] and any(norm in c.replace("\\", "/") for c in _card_texts(rec)):
                rec["depends_files_read"].append(p)
        return
    root = _unmapped_root_of(p)
    if root is None:
        return
    rec = state.setdefault("overview_hub", {}).setdefault(_unmapped_key(root, p), {"part_files_read": [], "edits": 0})
    if p not in rec["part_files_read"]:
        rec["part_files_read"].append(p)


def _read_paths(tool_name: str, tool_input: Dict[str, Any], cwd: str) -> List[str]:
    """讀檔辨識的入口：Grep（規則 GREP_CONTENT_IS_READ：output_mode=content 且 path 是檔）、Bash 先剝行首 # 註解行
    （規則 BASH_COMMENT_LINES_STRIPPED）再交 lib 的 regex；其他工具照 lib 原規則。"""
    if tool_name == "Grep":
        return _rr.grep_read_paths(tool_input)
    if tool_name == "Bash":
        tool_input = {**tool_input, "command": _rr.strip_comment_lines(str(tool_input.get("command") or ""))}
    return read_paths_from_tool(tool_name, tool_input, cwd)


def on_read(state: Dict[str, Any], session_id: str, tool_name: str, tool_input: Dict[str, Any],
            cwd: str, transcript_path: str, config: Dict[str, Any]) -> Optional[str]:
    """PostToolUse（Read／Bash／PowerShell／Grep）：第一次讀到某部位 → 回注入文字；已注入 → 記 reads_after／part_files_read。
    暫存目錄下的檔（規則 TEMP_COPY_NOT_PROJECT）不找表、不注入、不記。"""
    cfg = _cfg(config)
    if not cfg["enabled"]:
        return None
    for p in _read_paths(tool_name, tool_input, cwd):
        if _rr.is_temp_path(_long(p), _temp_roots()):
            continue
        hit = _lookup_quiet(p)
        _record_read(state, p, hit)
        if not hit:
            continue
        root, row = hit
        if (state.get("overview_hub") or {}).get(_key(root, row)) is None:
            cfg = _cfg(config, root)
            if not cfg["enabled"]:
                return None
            return _inject(state, session_id, root, row, p, tool_name.lower(), transcript_path, cfg)
    return None


def on_prompt(state: Dict[str, Any], session_id: str, prompt: str, transcript_path: str,
              config: Dict[str, Any], intent: Optional[str] = None) -> Optional[str]:
    """UserPromptSubmit：提示詞裡出現的絕對路徑命中某部位且未注入 → 依意圖選片注入。intent 給了就存進 state["turn_intent"]。"""
    if intent is not None:
        state["turn_intent"] = intent
    cfg = _cfg(config)
    if not cfg["enabled"]:
        return None
    parts: List[str] = []
    for m in re.finditer(r"[A-Za-z]:[\\/][^\s`'\"<>|]+", prompt):
        hit = _lookup_quiet(m.group(0))
        if not hit:
            continue
        root, row = hit
        if _key(root, row) not in (state.get("overview_hub") or {}):
            cfg_r = _cfg(config, root)
            if not cfg_r["enabled"]:
                return None
            parts.append(_inject(state, session_id, root, row, m.group(0), "prompt", transcript_path, cfg_r))
            break
    # A5.2：觸發詞 → 已注入部位各送一次候選前 N；A5.4：沒事做（general 意圖）→ 一 session 一行主動掃視
    try:   # 候選炸了不得吞掉同回合已組好的導讀卡注入（UPS 外層 except 會把整段 _hub_txt 丟掉）
        parts.extend(_candidates_on_trigger(state, session_id, prompt, config))
    except Exception as e:  # noqa: BLE001
        parts.append(_candidates_error_line(session_id, e, via="prompt"))
    if (_intent_of(state) == "general" and not state.get("idle_scan_sent")
            and _hit_trigger(prompt, cfg.get("idle_triggers"))):
        state["idle_scan_sent"] = True
        parts.append(IDLE_SCAN_LINE)
        _log("idle_scan", session_id, trigger=_hit_trigger(prompt, cfg.get("idle_triggers")))
    return "\n".join(parts) if parts else None


_EXT_UNC_PREFIX = "\\\\?\\UNC\\"
_EXT_PREFIX = "\\\\?\\"


def _strip_extended(path: str) -> str:
    """剝 Windows extended-length 前綴：`\\\\?\\C:\\x` → `C:\\x`、`\\\\?\\UNC\\srv\\share\\x` → `\\\\srv\\share\\x`。"""
    if path.startswith(_EXT_UNC_PREFIX):
        return "\\\\" + path[len(_EXT_UNC_PREFIX):]
    if path.startswith(_EXT_PREFIX):
        return path[len(_EXT_PREFIX):]
    return path


def _path_key(p: Path) -> Optional[str]:
    """路徑相等比對用的鍵：resolve（跟 symlink、還原磁碟實際大小寫）→ 剝 `\\\\?\\` → normpath → normcase（Windows 不分大小寫）。"""
    try:
        s = str(p.resolve())
    except (OSError, ValueError, RuntimeError):
        return None
    return os.path.normcase(os.path.normpath(_strip_extended(s)))


def _own_config_layer(file_path: str) -> Tuple[bool, Optional[Path]]:
    """file_path 是不是 OverviewHub 自己讀的設定檔或部位表；是 → 整個 on_edit 不走 OverviewHub 流程（有錯只回警告）。

    候選（精確比對 _path_key，不比檔名、不預篩）：根層 workflow/config.json；根層／公司根／該檔所屬專案根的
    .claude/overview-hub.json 與 .claude/overview-map.md。專案根＝find_map 從該檔往上找到的那個根：無表專案的
    hub.json 不算（那一層設定本來就不會被載入，沒有它造成的錯誤要修；若根層／公司層另有錯仍照一般檔被擋）。
    回 (是不是, 該檔所屬層的 root；config.json 回 None)。"""
    plain = _strip_extended(file_path)
    fk = _path_key(Path(plain))
    if fk is None:
        return (False, None)
    if fk == _path_key(CONFIG_PATH):
        return (True, None)
    own_rels = (HUB_REL, Path(MAP_REL))
    for layer_root in (CLAUDE_DIR, _org_root()):
        if layer_root is not None and any(fk == _path_key(layer_root / rel) for rel in own_rels):
            return (True, layer_root)
    found = find_map(plain)
    root = found[0] if found else _project_root_of(plain)      # 無表專案的 hub.json 也要能自救（新流程會載入它）
    if root is not None and any(fk == _path_key(root / rel) for rel in own_rels):
        return (True, root)
    return (False, None)


def _cfg_error_deny(cfg: Dict[str, Any], session_id: str, file_path: str,
                    row: Optional[Dict[str, Any]]) -> Optional[Tuple[str, str, bool]]:
    """`_errors` 非空 → (訊息, deny 理由, False)，訊息列全部錯誤；沒錯誤回 None。"""
    if not cfg["_errors"]:
        return None
    where = f"改【{row['part_short']}】部位的檔（{file_path}）" if row else f"改 {file_path}"
    msg = (f"[Guardian:OverviewHub] {where}前，這一層的 OverviewHub 設定有錯（{cfg['_layer']}），閘無法判定，先修設定："
           + "；".join(cfg["_errors"]))
    _log("edit_cfg_error", session_id, part=row["part_short"] if row else None, path=file_path,
         layer=cfg["_layer"], errors=cfg["_errors"])
    return (msg, msg, False)


def _layer_mismatch(row: Dict[str, Any], vals: Dict[str, str]) -> Optional[str]:
    """部位表有「層」欄（單層以外）時，根因層那行必須指明其中一層；都沒提到＝填錯層或沒填層。"""
    layers = [x.strip() for x in _LAYER_SPLIT_RE.split(row.get("layer") or "") if x.strip() and x.strip() != "單層"]
    if not layers or any(l in vals.get("根因", "") for l in layers):
        return None
    return f"定位｜根因層 沒有指明這個部位的層（部位表列的層：{'／'.join(layers)}），填錯層或沒填層一律擋"


def _gitignored(root: Path, file_path: str) -> Optional[bool]:
    """git check-ignore 事實（規則 RUNTIME_DATA_NO_OVERVIEW）：True 被忽略、False 沒有、None 查不到（不在 git／逾時）。"""
    if not (root / ".git").exists():
        return None
    try:
        r = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", file_path], capture_output=True,
                           timeout=2, creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    return True if r.returncode == 0 else (False if r.returncode == 1 else None)


def _unmapped_edit(state: Dict[str, Any], session_id: str, root: Path, file_path: str,
                   cfg: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], bool]:
    """沒有部位表的專案、或表上沒列的檔：只要求本 session 讀過同頂層目錄 ≥N 個檔。
    執行期資料（gitignored、workflow/state*、workflow/need-goal、Logs…；規則 RUNTIME_DATA_NO_OVERVIEW）免綜觀。"""
    key = _unmapped_key(root, file_path)
    top = top_dir(file_path, root)
    v = _rr.runtime_data_verdict(file_path, str(root), _gitignored(root, file_path))
    if not v.owed:
        _log("edit_unmapped", session_id, path=file_path, root=str(root), top=top, rule=v.rule, deny_reason=None)
        return (None, None, False)
    need = int(cfg["min_overview_evidence"]["part_files"])
    rec = (state.get("overview_hub") or {}).get(key)
    have = len(rec["part_files_read"]) if rec else 0
    if have < need:
        msg = (f"[Guardian:OverviewHub] 改 {file_path} 前：這個專案（{root}）沒有部位表列到這個檔，"
               f"閘只要求本 session 先讀過同頂層目錄「{top}」至少 {need} 個檔（目前 {have} 個）。先讀再改。")
        _log("edit_unmapped", session_id, path=file_path, root=str(root), top=top, part_files_read=have,
             need=need, deny_reason="part_files", layer=cfg.get("_layer"))
        return (msg, msg, False)
    rec["edits"] = int(rec.get("edits", 0)) + 1
    _log("edit_unmapped", session_id, path=file_path, root=str(root), top=top, part_files_read=have,
         need=need, edits=rec["edits"], deny_reason=None, layer=cfg.get("_layer"))
    return (None, None, True)


def on_edit(state: Dict[str, Any], session_id: str, file_path: str, transcript_path: str,
            config: Dict[str, Any], cwd: str = "") -> Tuple[Optional[str], Optional[str], bool]:
    """PreToolUse（Write／Edit／NotebookEdit／Bash／PowerShell 的每個寫入目標）：回 (警告文字, deny 理由, state 有沒有變)。

    deny 理由帶整張卡（模型只看得到 permissionDecisionReason）。三項證據缺一即 deny；transcript 讀不到 deny；
    readonly 命中 deny 不注入；定位三行只在 thinking 交的放行附提醒。cwd 目前只供記錄，判定全由檔案路徑決定。
    """
    if not file_path:
        return (None, None, False)
    if file_path.startswith("UNKNOWN:"):
        # write_paths_from_tool 解析不出寫入目標（變數路徑、eval、cd -、heredoc 以外的怪寫法）：不知道改哪個檔就不能判，一律擋
        msg = (f"[Guardian:OverviewHub] 無法判定這段指令的寫入目標（{file_path[8:]}…）：路徑含展不開的變數、eval、cd - 或"
               f"解析不出的重導向。改用 Edit／Write 工具，或把路徑寫成字面絕對路徑。")
        _interp = re.match(r"\s*(?:\S+=\S+\s+)*(node|nodejs|pwsh|powershell|python3?|py|pythonw)\b", file_path[8:], re.IGNORECASE)
        if _interp:
            msg += "\n" + _rr.inline_code_hint(_interp.group(1).lower())      # 規則 INLINE_PY_READONLY：判不了的內嵌碼指路
        _log("edit_unknown_target", session_id, path=file_path, deny_reason="unknown_target")
        return (msg, msg, False)
    if _rr.is_temp_path(_long(file_path), _temp_roots()):
        # 規則 TEMP_COPY_NOT_PROJECT：暫存目錄下的副本不當專案（git archive 解到 scratchpad 的樹含部位表也一樣），不找表、不注入、不擋
        _log("edit_temp_copy", session_id, path=file_path, rule="TEMP_COPY_NOT_PROJECT", deny_reason=None)
        return (None, None, False)
    # 改的是 OverviewHub 自己的設定檔／部位表 → 不走 OverviewHub 流程（否則設定寫錯一個鍵就再也改不回來）；有錯仍回警告列出來讓模型知道在修什麼
    own, own_root = _own_config_layer(file_path)
    if own:
        errors = _cfg(config, own_root)["_errors"]
        if not errors:
            return (None, None, False)
        msg = (f"[Guardian:OverviewHub] 正在改 OverviewHub 自己的設定檔（{file_path}），放行以便修復。目前的設定錯誤："
               + "；".join(errors))
        _log("edit_own_config", session_id, path=file_path, errors=errors)
        return (msg, None, False)
    # 設定錯誤先於 enabled／命中判定：設定壞了（含 enabled 不是 bool）整層都不可信，一律 deny，沒命中部位表的檔也擋
    cfg = _cfg(config)
    denied = _cfg_error_deny(cfg, session_id, file_path, None)
    if denied:
        return denied
    if not cfg["enabled"]:
        return (None, None, False)
    hit = _lookup_quiet(file_path)
    if hit:
        root, row = hit
    else:
        root, row = _unmapped_root_of(file_path), None
        if root is None:
            return (None, None, False)
    cfg = _cfg(config, root)
    denied = _cfg_error_deny(cfg, session_id, file_path, row)
    if denied:
        return denied
    if not cfg["enabled"]:
        return (None, None, False)
    ro = _is_readonly(file_path, root, cfg)
    if ro:
        msg = (f"[Guardian:OverviewHub] {file_path} 在這一層的 readonly_paths（樣式「{ro}」）：程式產物／索引不可手改，"
               f"改來源或跑產生器。")
        _log("edit_readonly", session_id, path=file_path, pattern=ro, part=row["part_short"] if row else None,
             deny_reason="readonly", layer=cfg.get("_layer"))
        return (msg, msg, False)
    if row is None:
        return _unmapped_edit(state, session_id, root, file_path, cfg)
    key = _key(root, row)
    rec = (state.get("overview_hub") or {}).get(key)
    knowledge = _oh.path_kind(file_path, root) == _oh.KIND_KNOWLEDGE
    if rec is not None and _needs_card(row) and (rec.get("cards_missing") or not rec.get("card_paths")):
        # 表上有卡但上次有缺（或升級前注入的舊紀錄沒有卡）：每次改檔都重找；任何一張仍找不到一律擋，讀過檔＋交三行也一樣
        paths, again = _resolve_row_cards(root, row, cfg)
        if again and again["missing"]:
            rec["cards_missing"] = {k: again[k] for k in ("missing", "searched", "timed_out")}
            msg = _missing_card_msg(row, again)
            _log("edit_card_missing", session_id, part=row["part_short"], path=file_path, deny_reason="card_missing",
                 cards=again["missing"], timed_out=again["timed_out"], layer=cfg.get("_layer"))
            return (msg, msg, True)
        if not rec.get("cards_missing") and again is None:
            rec["card_paths"] = [str(p) for p in paths]   # 升級前的舊紀錄：卡都在預設目錄，照常判定
        else:
            rec = None                              # 缺的卡出現了（或只在別處）：照第一次碰到這個部位重新注入
    if rec is None:
        text = _inject(state, session_id, root, row, file_path, "edit", transcript_path, cfg)
        cm = state["overview_hub"][key].get("cards_missing")
        if cm:
            mm = _missing_card_msg(row, cm)
            _log("edit_card_missing", session_id, part=row["part_short"], path=file_path, deny_reason="card_missing",
                 cards=cm["missing"], timed_out=cm["timed_out"], layer=cfg.get("_layer"))
            msg = f"{mm}\n{text.replace(chr(10) + mm, '')}"
            return (msg, msg, True)
        todo = "先讀完再改（知識類部位不要求讀部位檔與定位三行）。" if knowledge else "先讀完、讀過部位檔、在回覆交出定位三行，再改。"
        msg = (f"[Guardian:OverviewHub] 要改【{row['part_short']}】部位的檔但本 session 還沒看過這個部位的導讀卡；"
               f"卡片現在才注入（下面）。{todo}\n{text}")
        _log("edit_before_inject", session_id, part=row["part_short"], path=file_path, deny_reason="not_injected",
             intent=_intent_of(state), layer=cfg.get("_layer"), kind=_oh.KIND_KNOWLEDGE if knowledge else _oh.KIND_CODE)
        return (msg, msg, True)
    _migrate_rec(rec)
    rec["edits"] = int(rec.get("edits", 0)) + 1
    if not knowledge:
        rec["kind"] = _oh.KIND_CODE        # 同一列也有寫碼命中（例：只撞到子字串）：scorecard 的 S3 要算這個部位
    if knowledge:
        # 知識類部位：三項證據只要「卡已注入」（走到這裡就成立）；讀檔數照記（on_read），不查讀部位檔、定位三行、transcript
        _log("edit", session_id, part=row["part_short"], path=file_path, kind=_oh.KIND_KNOWLEDGE, located=bool(rec.get("located")),
             part_files_read=len(rec["part_files_read"]), depends_files_read=len(rec["depends_files_read"]),
             reads_after_inject=len(rec["reads_after"]), edits=rec["edits"], intent=rec.get("intent"),
             slices=rec.get("slices"), layer=cfg.get("_layer"), deny_reason=None)
        return (None, None, True)
    candidates: Optional[str] = None
    reads = rec["reads_after"]
    dirs = sorted({top_dir(p, root) for p in reads})
    part_files = rec["part_files_read"]
    depends_files = rec["depends_files_read"]
    ev = cfg["min_overview_evidence"]
    missing: List[str] = []
    deny_reason: Optional[str] = None
    warn: Optional[str] = None
    readable, why = transcript_readable(transcript_path)
    if not readable:
        # D4：讀不到 transcript 就驗不了定位三行（已 located 也一樣，環境異常先擋）；真開檔，不只 stat
        deny_reason = "transcript_missing"
        missing.append({
            "empty_path": "hook 沒收到 transcript_path（欄位為空）",
            "missing": f"transcript 檔不存在（{transcript_path}）",
            "unreadable": f"transcript 檔存在但開不了（{transcript_path}；鎖住或無權限）",
            "empty": f"transcript 檔存在但是空的（{transcript_path}）",
        }[why] + "：環境異常，閘無法驗定位三行，一律擋")
    if len(part_files) < int(ev["part_files"]):
        missing.append(f"注入導讀卡後還沒讀過這個部位的檔（要 ≥{ev['part_files']} 個，目前 {len(part_files)} 個；"
                       f"表外檔讀了 {len(reads) - len(part_files)} 個不算）")
    if len(depends_files) < int(ev["depends_files"]):
        missing.append(f"還沒讀過卡片指到的檔（要 ≥{ev['depends_files']} 個，目前 {len(depends_files)} 個）")
    if deny_reason is None and not rec.get("located"):
        # 三管道各取「最後一組」三行（被擋後補交的那組才是現行）；任一管道那組通過層檢查即 located
        found_ch, bad_layer, text = None, None, ""
        for ch in LOCATE_CHANNELS:
            text = assistant_text_after(transcript_path, int(rec.get("transcript_offset", 0)), ch)
            vals = locate_values(text, row["part_short"], rec.get("locate_template"))
            if not vals:
                continue
            bad = _layer_mismatch(row, vals)
            if bad:
                bad_layer = bad
                continue
            found_ch = ch
            break
        if found_ch is not None:
            rec["located"] = True
            rec["located_via"] = found_ch
            rec["located_quality"] = locate_quality(text, row["part_short"], _card_texts(rec), rec.get("locate_template"))
            if found_ch == "thinking":
                warn = (f"[Guardian:OverviewHub] 【{row['part_short']}】的定位三行只在 thinking 裡，模型下回合與人都看不到；"
                        f"這次放行，請改放回覆文字或下一個工具呼叫的參數（Bash 開頭的註解）。")
        elif bad_layer:
            missing.append(bad_layer + "；補交一組正確的三行即可（取最後一組）")
            deny_reason = "wrong_layer"
        else:
            missing.append(f"還沒交出定位三行（注入導讀卡後讀了 {len(reads)} 個檔、跨 {len(dirs)} 個目錄）。"
                           f"請先在回覆寫：定位｜部位：…／定位｜根因層：…／定位｜前例：…")
    if missing and deny_reason is None:
        deny_reason = "evidence"
    _log("edit", session_id, part=row["part_short"], path=file_path, located=bool(rec.get("located")),
         located_via=rec.get("located_via"), located_quality=rec.get("located_quality"),
         part_files_read=len(part_files), depends_files_read=len(depends_files),
         reads_after_inject=len(reads), dirs_after_inject=len(dirs), edits=rec["edits"],
         intent=rec.get("intent"), slices=rec.get("slices"), layer=cfg.get("_layer"), deny_reason=deny_reason)
    if not missing:
        # A5.3：放行的同檔第 2 次 Edit 附候選（被擋的不算改過；第 3 次起不送）；rec.edited_files {路徑: 放行次數}。
        # 一部位一 session 只送一次：與 on_prompt 觸發詞共用 candidates_sent（部位 key），同部位別的檔第 2 次 Edit 不再送；
        # 沒內容時只送一行，那一行也記進 candidates_sent。
        ef = rec["edited_files"]
        ef_key = _root_key(Path(file_path))   # 正斜線＋小寫：Windows 上 Game/A.cs 與 game/a.cs 是同一檔
        ef[ef_key] = int(ef.get(ef_key, 0)) + 1
        sent = state.setdefault("candidates_sent", [])
        if ef[ef_key] == 2 and key not in sent:
            # 放行已判定；候選是附加輸出，炸了只附一行說明，不得把放行變成擋（外層 pre_tool_use 的 except 會當環境異常 deny）
            try:
                candidates = _candidates_block(root, [row], cfg, compact_empty=True)
            except Exception as e:  # noqa: BLE001
                candidates = _candidates_error_line(session_id, e, via="second_edit", part=row["part_short"])
            sent.append(key)
            _log("second_edit", session_id, part=row["part_short"], path=file_path, edits_same_file=2, layer=cfg.get("_layer"))
            warn = f"{warn}\n{candidates}" if warn else candidates
        return (warn, None, True)
    msg = (f"[Guardian:OverviewHub] 改【{row['part_short']}】部位的檔（{file_path}）前的證據不足，一律擋：\n"
           + "\n".join(f"- {m}" for m in missing))
    return (msg, msg, True)
