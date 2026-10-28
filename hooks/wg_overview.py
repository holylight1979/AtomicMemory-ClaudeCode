"""wg_overview — OverviewHub 的 state 層：三個 hook 各呼叫一個函式。

做什麼：第一次碰到某部位就建部位紀錄，一個 session 一個部位一次。唯讀碰到（Read／唯讀 Bash／PowerShell／Grep）只建紀錄、
讀檔結果最多多一行定位提示，卡不送（規則 READ_TOUCH_NO_CARD）；卡在第一次改這個部位的檔（on_edit）或提示詞點名路徑時才送。
卡怎麼送看 card_injection：pointer（預設）只送已知病灶一句＋卡路徑，改那塊之前要 Read 過卡；full 依本回合意圖
（state["turn_intent"]）查 goal_weights 選片整張注入（沒片命中退整卡）；v6 總開關開關都照這個值。卡尾的未結追蹤項只留筆數一行。
之後記「碰到後讀了哪些檔、其中幾個是部位檔」；改檔前三項證據缺一即 deny：導讀卡已注入（不可關；指標制的程式部位另要 Read 過卡）、
讀過部位檔 ≥N、交了定位三行（三行在 thinking 交的放行附提醒）。部位表類別 knowledge 的部位（文件、記憶、信件匣）只要第一項（指標制沒 Read 過卡只提醒、留帳）。
readonly_paths 命中一律 deny 不注入；transcript 讀不到視為環境異常，deny。
沒有部位表的專案（或表上沒列的檔）改前要求本 session 讀過同頂層目錄 ≥N 個檔；往上找不到任何部位表的專案，第一次改
某頂層目錄的程式檔前另要最小地圖三行（地圖｜讀了／上游／下游），擋訊息附掃表預覽。設定四層深合併（_cfg）、
設定錯誤時 Edit 一律擋。每個事件各落一行 jsonl 到 workflow/_overview-hub.log 當量測資料。

state["overview_hub"] = {
  "<root>|<part>": {"injected_turn", "injected_at", "transcript_offset", "transcript_offsets": {檔: byte}, "intent", "slices", "card_paths", "card_mode",
                     "reads_after": [...], "part_files_read": [...], "depends_files_read": [...],
                     "located": bool, "located_via", "located_quality", "edits": n, "locate_template"},
  "<root>|(unmapped)<top_dir>": {"part_files_read": [...], "edits": n, "min_map_done": bool, "min_map_via"}
}
state["min_map"] = {"<root>": {"preview", "preview_ok", "preview_ms", "offset"}}   # 掃表預覽快取、上次交地圖放行時的 transcript 位置
"""

from __future__ import annotations

import fnmatch
import hashlib
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
    CLAUDE_DIR, CONFIG_PATH, DECL_DENY_CAP, _atom_debug_error, _layer_kind_for_root, _map_path_of,
    CODE_INTENTS, append_guard_log, assistant_texts_since, coding_turn, deny_cap, org_memory_root, resolve_project_root, transcript_sizes,
    v6_enabled,
)
from wg_verify_ledger import vcs_root_of

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))   # 程式碼用本檔位置，CLAUDE_DIR 只定位資料
from hub_config import (  # noqa: E402
    HUB_DEFAULTS, HUB_REL, INTENT_KEYS, KNOWN_KEYS, RETIRED_KEYS, encoding_ok, merge_hub_cfg, validate_hub_cfg,
)
import overview_hub as _oh  # noqa: E402
from overview_hub import (  # noqa: E402
    DEFAULT_LOCATE_TEMPLATE, LAYER_AXIS_RE, LOCATE_CHANNELS, MAP_REL, ROOT_CAUSE_SENTENCE, SLICE_NAMES, assistant_text_after,
    build_injection_ex, card_mem_dir, find_map, locate_quality, locate_values, match_row, parse_map, read_paths_from_tool, resolve_card,
    top_dir, transcript_readable, transcript_size, unread_rows_note,
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
_CANDIDATE_QUESTIONS = ("① 這些候選裡哪一個是你這次要修的問題的根因所在？為什麼不是另一個（挑的不是分數最高的，就說為什麼不是它）？",
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
    `_layer`（root／org／project_mapped／project_unmapped／none）、`_card_mode`（這次實際用的導讀卡送法）。
    OverviewHub 整道（導讀卡注入、候選、讀檔記錄、定位）綁 v6 總開關：v6 關時 `enabled` 一律 False，什麼都不送、不記
    （規則 OVERVIEW_HUB_UNDER_V6）。回傳必帶 `_errors`（非空時 on_edit deny）。
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
    v6 = v6_enabled(config)
    c["enabled"] = bool(c.get("enabled")) and v6
    c["_card_mode"] = c.get("card_injection")
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


def write_target_root(path: str) -> Optional[Path]:
    """寫入目標（改檔閘逐目標判）落在哪個專案根，規則 DIR_TARGET_JUDGED_BY_CONTAINER：整個資料夾當目標（rm -rf、
    Remove-Item -Recurse、搬走）看它所在的上一層，不拿資料夾自己的專案標記（.git、_AIDocs、部位表）：刪掉整個專案資料夾
    不是在改那個專案的檔，拿它自己當根只會要求讀「(outside)」的檔，永遠讀不到。檔案照舊（_unmapped_root_of）。
    cwd 這類「我在哪」的目錄不走這裡（_project_root_of／_unmapped_root_of 照舊拿目錄自己）。"""
    try:
        p = Path(path)
        is_dir = p.is_absolute() and p.is_dir()
    except (OSError, ValueError):
        is_dir = False
    return _unmapped_root_of(str(p.parent) if is_dir else path)


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


# 第四行之後的第五行（規則 LOCATE_LINES_NEED_CRITIQUE）：批判與舉一反三
def _critique_cases() -> str:
    import wg_need_goal as _ng
    return _ng.CRITIQUE_CASES


CRITIQUE_LINE_HINT = f"定位三行的下面加一行「定位｜批判：{_oh.CRITIQUE_TEMPLATE}」；{_critique_cases()}"


def _critique_pointer() -> str:
    import wg_need_goal as _ng
    return _ng.CRITIQUE_CASES_POINTER


# 三種情況這個 session 送過全文之後（規則 CRITIQUE_CASES_ONCE_PER_SESSION）：定位第五行的格式照送，三種情況換成指回句
CRITIQUE_LINE_SHORT = f"定位三行的下面加一行「定位｜批判：{_oh.CRITIQUE_TEMPLATE}」；{_critique_pointer()}"


def _goal_block(session_id: str, cfg: Dict[str, Any], part_key: Optional[str] = None, turn: Optional[int] = None) -> str:
    """導讀卡開頭附的目標（有目前的樹才附）：brief_for（新送法只一行當前節點，這個部位掛了節點就是那個；樹根與整棵樹在 need_goal
    寫入的回覆送過），讓「目標」與「這一塊的說明」同時在眼前；同一個使用者回合已附過同一份就只留定位第五行的提醒（給了 turn 才去重）。
    定位第五行提示裡的三種情況每個 session 只送一次全文（wg_need_goal.critique_once）。全樹要看用 need_goal read。讀不到只 stderr。"""
    ng = cfg.get("need_goal") if isinstance(cfg.get("need_goal"), dict) else {}
    if not session_id or not ng.get("enabled", True):
        return ""
    try:
        import wg_need_goal as _ng
        tree = _ng.active_tree(_ng.load(session_id))
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:OverviewHub] 讀需求目標樹失敗（導讀卡不附樹）：{type(e).__name__}: {e}", file=sys.stderr)
        return ""
    if not tree:
        return ""
    b = _ng.brief_for(tree, part_key) if turn is None else _ng.brief_once(session_id, int(turn), part_key)
    hint = CRITIQUE_LINE_HINT if _ng.critique_once(session_id) else CRITIQUE_LINE_SHORT
    if not b:
        return f"[NeedGoal] 改這個部位的程式檔時，{hint}（目前的需求目標同本回合前面那則）"
    return f"[NeedGoal] 目前的需求目標（改這個部位的程式檔時，{hint}）：\n{b}"


def _goal_tree_for(session_id: str, file_path: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """這次改檔要交第四行時回目前的樹（need_goal 啟用、是程式檔、有樹）；目標檔壞了往外拋，由 pre_tool_use 一律擋。"""
    import wg_need_goal as _ng
    return _ng.goal_for_edit(session_id, file_path, config)


def _goal_linked(rec: Dict[str, Any], tree: Dict[str, Any]) -> bool:
    node = (tree.get("nodes") or {}).get(rec.get("goal_node") or "")
    return rec.get("goal_tree") == tree["id"] and bool(node) and node.get("status") != "dropped"


def _texts_after(rec: Dict[str, Any], transcript_path: str, agent_id: str, channel: str) -> str:
    """這個部位起點（注入或目標改的那刻）之後、主檔與子代理檔裡 AI 寫的內容（wg_core.assistant_texts_since）。"""
    return assistant_texts_since(transcript_path, agent_id, channel, rec.get("transcript_offsets"),
                                 int(rec.get("transcript_offset", 0)))


def relink_parts(state: Optional[Dict[str, Any]], session_id: str, transcript_path: str, config: Dict[str, Any],
                 parts: Dict[str, Dict[str, Any]]) -> List[str]:
    """收尾對照（規則 EDITED_PART_NEEDS_GOAL_NODE）前蒐集事實：沒掛目標的部位（parts＝{部位 key: {"files": […]}}），
    從 transcript 三管道找這個部位最後一組定位四行，照改檔時同一套判法（層、第四行節點、角色與兩個候選）通過就掛上。
    掃描起點＝state 裡這個部位的 transcript_offset（目標改過就從改的那刻起），沒紀錄從頭。回掛上的部位 key。"""
    import wg_need_goal as _ng
    tree = _ng.active_tree(_ng.load(session_id))
    if not tree or not transcript_path:
        return []
    hub = (state or {}).get("overview_hub") or {}
    linked: List[str] = []
    for key, info in parts.items():
        files = info.get("files") or []
        hit = _lookup_quiet(files[0]) if files else None
        if not hit or _key(*hit) != key:
            continue
        root, row = hit
        rec = hub.get(key) if isinstance(hub.get(key), dict) else {}
        template = rec.get("locate_template") or _locate_template(_cfg(config or {}, root))
        longer = _longer_parts(root, row)
        for ch in LOCATE_CHANNELS:
            vals = locate_values(_texts_after(rec, transcript_path, "", ch), row["part_short"], template, longer)
            if not vals or _layer_mismatch(row, vals):
                continue
            node, problem = _goal_line_check(tree, vals)
            if problem:
                continue
            _ng.link_part(session_id, key, node, int((state or {}).get("turn_seq", 0)))
            _log("relink", session_id, part=row["part_short"], node=node, via=ch)
            linked.append(key)
            break
    return linked


def on_goal_changed(state: Dict[str, Any], transcript_path: str, turn: int) -> int:
    """目標改了（開新樹、改寫樹根、改節點文字、匯入續接單的樹）：已交過定位的部位全部要重交，只認這之後交的那一組。
    加子節點不算（照讀入範圍提示長子目標，不該讓已交的定位作廢）。回清了幾個部位。"""
    size = transcript_size(transcript_path)
    sizes = transcript_sizes(transcript_path)
    n = 0
    for rec in (state.get("overview_hub") or {}).values():
        if not isinstance(rec, dict) or "located" not in rec:
            continue
        rec["located"] = False
        rec.pop("goal_node", None)
        rec.pop("goal_tree", None)
        rec["transcript_offset"] = size
        rec["transcript_offsets"] = dict(sizes)
        rec["goal_reset_turn"] = int(turn)
        n += 1
    return n


def _tracking_line(root: Path, row: Dict[str, Any], tracked: List[Dict[str, Any]]) -> str:
    """導讀卡尾的追蹤項只留一行（規則 TRACKING_COUNT_LINE_ONLY）：筆數＋帳本路徑＋結案寫法，不列內容——以前「最多 5 筆＋另有 N 筆」
    整段跟著卡進 context，查資料的 session 碰十個部位就吃掉幾千 token。沒有查詢工具，查法就是讀帳本。"""
    from wg_harvest import tracking_path, tracking_slug
    return (f"未結追蹤項 {len(tracked)} 筆（這個部位以前記下、還沒結案的問題；要看就讀帳本 {tracking_path(tracking_slug(str(root)))}，"
            f"處理完在 AEC (k) 寫「[{row['part_short']}] 結案：<原文開頭至少 8 字；原文不足 8 字就寫全文>」）")


def _card_text(state: Dict[str, Any], session_id: str, root: Path, row: Dict[str, Any], hit_path: str, cfg: Dict[str, Any],
               card_paths: List[Path], miss: Optional[Dict[str, Any]], kind: str) -> Tuple[str, List[str]]:
    """這個部位送到眼前的那段文字：目標一行（有樹才有）＋定位要求＋卡（照 _card_mode：pointer 兩行／full 整張選片）＋
    卡不在預設目錄的提醒＋追蹤項一行。回 (文字, 實際送出的片名)。注入當下（on_prompt／on_edit 補注入）與延後送（讀檔時只記、
    第一次改檔才送）都走這一支，兩邊字面相同。"""
    template = _locate_template(cfg)
    extra = (cfg.get("locate_extra") or {}).get(row["part_short"]) if isinstance(cfg.get("locate_extra"), dict) else None
    gw = (cfg.get("goal_weights") or {}).get(_intent_of(state)) or {}
    text, used = build_injection_ex(row, card_paths, hit_path, int(cfg["max_card_chars"]), template, extra,
                                    list(gw.get("slices") or []), str(gw.get("lens") or ""), str(gw.get("ask_first") or ""),
                                    knowledge=kind == _oh.KIND_KNOWLEDGE, extra=str(gw.get("extra") or ""),
                                    pointer=cfg.get("_card_mode") == "pointer")
    if miss:
        text += "".join(f"\n表上的卡在 {p}，不在預設目錄；請更新表或搬卡" for p in miss["found"])
        if miss["missing"]:
            text += "\n" + _missing_card_msg(row, miss)
    tracked = _tracking_for(root, row)
    if tracked:
        text = f"{text}\n{_tracking_line(root, row, tracked)}"
    goal = _goal_block(session_id, cfg, _key(root, row), int(state.get("turn_seq", 0) or 0))
    return (f"{goal}\n{text}" if goal else text), used


def _inject(state: Dict[str, Any], session_id: str, root: Path, row: Dict[str, Any],
            hit_path: str, via: str, transcript_path: str, cfg: Dict[str, Any], deliver: bool = True) -> str:
    """第一次碰到部位：建部位紀錄（證據從這一刻起算）。deliver＝True 連卡一起回（提示詞點名、改檔時補注入）；
    False＝唯讀碰到（規則 READ_TOUCH_NO_CARD）：只記紀錄、標 card_pending，回空字串，卡等第一次改這個部位的檔時由
    _deliver_card 送——AI 只查資料時不吃卡、候選、追蹤項。"""
    card_paths, miss = _resolve_row_cards(root, row, cfg)
    card_path = card_paths[0] if card_paths else None
    intent = _intent_of(state)
    kind = _oh.path_kind(hit_path, root) or _oh.KIND_CODE
    mode = cfg.get("_card_mode", "full")
    text, used = _card_text(state, session_id, root, row, hit_path, cfg, card_paths, miss, kind) if deliver else ("", [])
    hub = state.setdefault("overview_hub", {})
    hub[_key(root, row)] = {
        "card_pending": not deliver,      # 讀檔時只記、沒送卡：第一次改這個部位的檔時 on_edit 補送（_deliver_card）
        "injected_turn": int(state.get("turn_seq", 0)),
        "injected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "transcript_offset": transcript_size(transcript_path),
        "transcript_offsets": transcript_sizes(transcript_path),
        "intent": intent,
        "slices": used,
        "card_paths": [str(cp) for cp in card_paths],
        "card_mode": mode,                # pointer：卡沒整張送，改這塊之前要 Read 過卡（_unread_cards）
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
        "locate_template": _locate_template(cfg),
        "cards_missing": ({k: miss[k] for k in ("missing", "searched", "timed_out")}
                          if miss and miss["missing"] else None),
    }
    _log("inject", session_id, part=row["part_short"], status=row["status"], via=via, path=hit_path,
         card=str(card_path) if card_path else None, chars=len(text), intent=intent, slices=used, layer=cfg.get("_layer"),
         card_mode=mode, card_pending=not deliver)
    return text


def _deliver_card(state: Dict[str, Any], session_id: str, root: Path, row: Dict[str, Any], hit_path: str,
                  cfg: Dict[str, Any]) -> str:
    """讀檔時只記沒送的卡（rec.card_pending）在第一次改這個部位的檔時組出來：卡重新解析（中間可能補了卡）、送法照現在的 _card_mode、
    片照現在的意圖；紀錄的起點（transcript_offset、讀檔帳）不動——讀檔後交的定位行與讀過的部位檔照算。一個部位一 session 一次。
    文字由 edit_check 放進提醒件 OVERVIEW_CARD_BEFORE_EDIT 的 extra：v6 開時不擋，隨那次改檔的工具結果送到。"""
    key = _key(root, row)
    rec = state["overview_hub"][key]
    card_paths, miss = _resolve_row_cards(root, row, cfg)
    kind = _oh.path_kind(hit_path, root) or _oh.KIND_CODE
    text, used = _card_text(state, session_id, root, row, hit_path, cfg, card_paths, miss, kind)
    rec.update(card_pending=False, card_paths=[str(cp) for cp in card_paths], card_mode=cfg.get("_card_mode", "full"),
               slices=used, cards_missing=({k: miss[k] for k in ("missing", "searched", "timed_out")}
                                           if miss and miss["missing"] else None))
    _log("card", session_id, part=row["part_short"], via="edit", path=hit_path, chars=len(text), slices=used,
         card_mode=rec["card_mode"], layer=cfg.get("_layer"))
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
        out.extend(_oh.defect_bullets(body)[:n - len(out)])
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
        rows = [r for r in rows if not r.get("part") or r["part"] in parts][:n]
    else:
        rows = _parts_in_turn(rows, n)
    # 不按分數重排（數字只當參考、不替 AI 排優先）：照報告原順序；分數照列並標參考
    lines = [_clip(f"- {r['path']}｜{r.get('category') or r.get('kind') or '?'}｜"
                   f"{(('【' + r['part'] + '】') if parts is None and r.get('part') else '')}{r.get('reason') or '（沒寫理由）'}"
                   + (f"｜分數 {r['score']}（參考）" if isinstance(r.get("score"), (int, float)) else ""),
                   line_cap) for r in rows]
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
    return lines, notes, f"smells 報告 {rp}；照報告原順序、不是優先順序，分數只當參考"


def _parts_in_turn(rows: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    """全專案候選：各部位輪流取（每輪每個部位取下一筆，部位照報告裡第一次出現的順序），取滿 n 筆後依部位分組列出，
    避免一個部位（例如分數普遍高的）佔滿。"""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault(r.get("part") or "", []).append(r)
    picked: List[int] = []
    for i in range(max((len(g) for g in groups.values()), default=0)):
        picked += [id(g[i]) for g in groups.values() if i < len(g)]
    keep = set(picked[:n])
    out: List[Dict[str, Any]] = []
    for g in groups.values():
        out += [r for r in g if id(r) in keep]
    return out


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


def read_scope_keys(path: str, config: Dict[str, Any]) -> Tuple[Optional[Path], Optional[str], Optional[str]]:
    """需求目標 4.3 讀入範圍用：回（專案根, 部位鍵, 頂層目錄鍵 <根>|<頂層目錄>）。部位只在 OverviewHub 開著、表上有列時才有；
    專案根與頂層目錄不看 OverviewHub 開關（有部位表照表所在的根，沒有就照專案標記或 VCS 根）；不在任何專案裡全回 None。"""
    hit = _lookup_quiet(path) if _cfg(config)["enabled"] else None
    if hit and not _cfg(config, hit[0])["enabled"]:
        hit = None
    found = None if hit else find_map(path)
    root = hit[0] if hit else (found[0] if found else _unmapped_root_of(path))
    if root is None:
        return None, None, None
    return root, (_key(*hit) if hit else None), f"{_root_key(root)}|{top_dir(path, root)}"


def _goal_view(state: Dict[str, Any], session_id: str, root: Path, row: Dict[str, Any], rec: Dict[str, Any],
               hit_path: str, cfg: Dict[str, Any]) -> Optional[str]:
    """目標改變後（on_goal_changed 記了 goal_reset_turn，第一次 need_goal set 也算）已碰過的部位再讀到 → 用目標視角重看一次
    （goal_view_turn 記重看過的那次重置）。規則 GOAL_VIEW_ONE_LINE：只送一行——目標視角的提問＋當前節點
    （wg_need_goal_points.goal_view_text 兩段併成一行），不重貼導讀卡、定位要求與部位表原文（卡在第一次注入時已經送過）。
    不重建部位紀錄，讀過的部位檔照算。"""
    reset = rec.get("goal_reset_turn")
    rec["goal_view_turn"] = reset
    try:
        import wg_need_goal_points as _ngp
        head = _ngp.goal_view_text(session_id, row["part"] or row["part_short"],
                                   knowledge=_oh.path_kind(hit_path, root) == _oh.KIND_KNOWLEDGE, part_key=_key(root, row))
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[NeedGoal] 目標視角重送失敗（不影響讀檔）：{type(e).__name__}: {e}\n")
        return None
    if not head:
        return None
    line = " ".join(s.strip() for s in head.splitlines() if s.strip())
    _log("goal_view", session_id, part=row["part_short"], path=hit_path, reset_turn=reset, chars=len(line), slices=[])
    return line


_MSYS_DRIVE_RE = re.compile(r"(?<![^\s'\"=(])/([A-Za-z])(?=/)")
_LEAD_CD_RE = re.compile(r"""^\s*cd\s+(?:"([^"]+)"|'([^']+)'|([^\s;&|'"]+))\s*(?:&&|;|\n)""")
_GREP_CMD_RE = re.compile(r"((?:^|[;&|(])\s*grep)(?=\s)([^;&|)\n]*)", re.MULTILINE)
_GREP_NO_CONTENT = ("--count", "--files-with-matches", "--files-without-match", "--quiet", "--silent")


def _grep_prints_lines(args: str) -> bool:
    """SHELL_READ_COUNTS_LIKE_READ：這段 grep 會印出命中的行（不是只印檔名 -l／-L、只印筆數 -c、不印 -q）。"""
    for tok in args.split():
        if tok.startswith("--") and tok.split("=", 1)[0] in _GREP_NO_CONTENT:
            return False
        if tok.startswith("-") and not tok.startswith("--") and set(tok[1:]) & set("lLcq"):
            return False
    return True


_SHORT_FLAGS_RE = re.compile(r"(?<!\S)(-[A-Za-z]+|--line-number)(?!\S)")


def _drop_line_numbers(args: str) -> str:
    """不印內容的 grep 段拿掉 -n（含 -nl 這類合寫裡的 n）：lib 只認帶 -n 的 grep，留著就把只印檔名或筆數的 grep 算成讀過。"""
    def fix(m: "re.Match[str]") -> str:
        tok = m.group(1)
        if tok == "--line-number":
            return ""
        tok = tok.replace("n", "")
        return "" if tok == "-" else tok
    return _SHORT_FLAGS_RE.sub(fix, args)


def _shell_read_text(command: str) -> str:
    """SHELL_READ_COUNTS_LIKE_READ：Bash 讀檔指令交 lib 解析前的兩個改寫——MSYS 寫法 `/c/x` 換成 `C:/x`（跟寫檔判定
    wg_core._write_target_abs 同一個檔）；grep 照會不會印出命中行對齊 lib 只認帶 -n 的判法：會印的補上 -n（-n 不改印出多少內容），
    只印檔名、筆數或不印的（-l、-L、-c、-q）拿掉 -n，就算原本帶 -n 也不算讀過。"""
    command = _MSYS_DRIVE_RE.sub(lambda m: f"{m.group(1).upper()}:", command)
    return _GREP_CMD_RE.sub(lambda m: f"{m.group(1)} -n{m.group(2)}" if _grep_prints_lines(m.group(2))
                            else f"{m.group(1)}{_drop_line_numbers(m.group(2))}", command)


def _lead_cd(command: str, cwd: str) -> str:
    """SHELL_READ_COUNTS_LIKE_READ：指令開頭 `cd <目錄> &&`（或 ; 、換行）→ 後面的相對路徑照這個目錄補；沒有、或目錄含變數 → 原 cwd。
    只認開頭那一個 cd，中間的 cd 不追。"""
    m = _LEAD_CD_RE.match(command)
    d = next((g for g in m.groups() if g), "") if m else ""
    if not d or "$" in d or d.startswith("~"):
        return cwd
    return d if Path(d).is_absolute() or not cwd else str(Path(cwd) / d)


def _writes_files(tool_name: str, tool_input: Dict[str, Any], cwd: str) -> bool:
    """SHELL_WRITE_COMMAND_NOT_A_READ：這條 Bash／PowerShell 指令有寫檔目標（重導向 >、tee、sed -i、Out-File…；判不出目標的也算）。
    判寫檔目標的程式出錯 → 照寫檔算（不算讀過），stderr 說一聲。"""
    try:
        from wg_core import write_paths_from_tool
        return bool(write_paths_from_tool(tool_name, tool_input, cwd or None))
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[Guardian:OverviewHub] 判不出這條指令有沒有寫檔，讀到的檔這次不算讀過：{type(e).__name__}: {e}\n")
        return True


def _read_paths(tool_name: str, tool_input: Dict[str, Any], cwd: str, exit_code: Optional[int] = None) -> List[str]:
    """讀檔辨識的入口：Grep（規則 GREP_CONTENT_IS_READ：output_mode=content 且 path 是檔）、Bash 先剝行首 # 註解行
    （規則 BASH_COMMENT_LINES_STRIPPED）、換 MSYS 路徑、grep 補 -n、相對路徑照開頭的 cd 補（規則 SHELL_READ_COUNTS_LIKE_READ）再交 lib 解析；
    Bash／PowerShell 有寫檔目標整條不算讀（規則 SHELL_WRITE_COMMAND_NOT_A_READ），解析出的路徑照規則 BASH_READONLY_COUNTS_AS_READ
    篩（exit_code＝這次指令的結束碼，未知給 None）；其他工具照 lib 原規則。"""
    if tool_name == "Grep":
        return _rr.grep_read_paths(tool_input)
    if tool_name in ("Bash", "PowerShell") and _writes_files(tool_name, tool_input, cwd):
        return []
    if tool_name == "Bash":
        command = _shell_read_text(_rr.strip_comment_lines(str(tool_input.get("command") or "")))
        tool_input, cwd = {**tool_input, "command": command}, _lead_cd(command, cwd)
    paths = read_paths_from_tool(tool_name, tool_input, cwd)
    return _rr.bash_read_counts(paths, exit_code) if tool_name in ("Bash", "PowerShell") else paths


def read_targets(tool_name: str, tool_input: Dict[str, Any], cwd: str, exit_code: Optional[int] = None) -> List[str]:
    """這次工具呼叫讀到的專案檔：_read_paths 去掉暫存目錄下的檔（規則 TEMP_COPY_NOT_PROJECT）。on_read 與需求目標的
    讀入範圍（wg_need_goal_points.scope_on_read）共用這一支，兩邊對「讀了什麼」的認定一致。"""
    return [p for p in _read_paths(tool_name, tool_input, cwd, exit_code) if not _rr.is_temp_path(_long(p), _temp_roots())]


def on_read(state: Dict[str, Any], session_id: str, tool_name: str, tool_input: Dict[str, Any],
            cwd: str, transcript_path: str, config: Dict[str, Any], exit_code: Optional[int] = None,
            agent_id: str = "") -> Optional[str]:
    """PostToolUse（Read／Bash／PowerShell／Grep）：第一次讀到某部位 → 建部位紀錄、不送卡（規則 READ_TOUCH_NO_CARD，卡等第一次改檔
    由 on_edit 送），讀檔結果最多只多 LOCATE_HINT_ON_FIRST_READ 一行；已有紀錄 → 記 reads_after／part_files_read；
    目標改了以後又讀到已碰過的部位 → 回目標視角的導讀卡。暫存目錄下的檔（規則 TEMP_COPY_NOT_PROJECT）不找表、不注入、不記；
    Bash／PowerShell 指令失敗（exit_code≠0）讀到的不算（規則 BASH_READONLY_COUNTS_AS_READ）。
    agent_id＝子代理讀的：讀檔照記、第一次讀到照注入（子代理自己改檔時的定位閘要用），目標視角重看不送（那是問主 session 的樹）、
    也不消耗主 session 的那一次。（需求目標的讀入範圍由 post_tool_use 另外呼叫 wg_need_goal_points.scope_on_read 算，不看 OverviewHub 開關。）
    一條指令讀到好幾個檔（Bash cat a b c）：每個檔都照順序記，注入之後的檔照算讀過——跟一則回覆平行送出幾個 Read 一樣
    （規則 SHELL_READ_COUNTS_LIKE_READ）；觸發注入的那個檔本身也記進讀過（規則 INJECT_TRIGGER_READ_COUNTED，Read 也一樣：
    那次讀就是真讀，「看過全貌才改」靠之後的定位四行守）；這一次注入或重送的導讀卡都接起來回。"""
    cfg = _cfg(config)
    if not cfg["enabled"]:
        return None
    texts: List[str] = []
    for p in read_targets(tool_name, tool_input, cwd, exit_code):
        hit = _lookup_quiet(p)
        _record_read(state, p, hit)
        if not hit:
            line = _unmapped_read_hint(state, session_id, p, config, agent_id)
            if line:
                texts.append(line)
            continue
        root, row = hit
        rec = (state.get("overview_hub") or {}).get(_key(root, row))
        goal_view_due = (rec is not None and not agent_id
                         and rec.get("goal_reset_turn") not in (None, rec.get("goal_view_turn")))
        if rec is not None and not goal_view_due:
            hint = _locate_read_hint(state, session_id, root, row, p, config, agent_id)
            if hint:
                texts.append(hint)
            continue
        root_cfg = _cfg(config, root)
        if not root_cfg["enabled"]:
            continue
        if rec is None:
            # 規則 READ_TOUCH_NO_CARD：唯讀碰到部位只建紀錄、不送卡（卡等第一次改檔），讀檔結果只多 LOCATE_HINT_ON_FIRST_READ 那一行
            text = _inject(state, session_id, root, row, p, tool_name.lower(), transcript_path, root_cfg, deliver=False)
            _record_read(state, p, hit)          # INJECT_TRIGGER_READ_COUNTED：注入前那筆記不進還沒建的部位紀錄，注入後補記
            state["overview_hub"][_key(root, row)]["locate_hint"] = "due"   # LOCATE_HINT_ON_FIRST_READ：讀到這部位的程式檔時提示
        else:
            text = _goal_view(state, session_id, root, row, rec, p, root_cfg)
        if text:
            texts.append(text)
        hint = _locate_read_hint(state, session_id, root, row, p, config, agent_id)
        if hint:
            texts.append(hint)
    return "\n\n".join(texts) or None


_LOCATE_HINT_KEY = "overview_locate_hint_sent"     # 本 session 送過完整那一則提示沒（之後的部位只點名、說格式同前）


def _unmapped_read_hint(state: Dict[str, Any], session_id: str, path: str, config: Dict[str, Any], agent_id: str = "") -> Optional[str]:
    """沒有部位表（或表上沒列）的程式檔第一次被讀到：_unmapped_edit 改檔時會欠的那兩件（同頂層目錄讀夠檔、最小地圖三行）
    先各提醒一行，每頂層目錄每 session 一次（remind_once；改檔那邊同鍵，提醒過就不再提醒）。v6 關、子代理讀的、非程式檔、
    執行期資料不送。判定不動。"""
    if agent_id or not path or not v6_enabled(config):
        return None
    root = _unmapped_root_of(path)
    if root is None:
        return None
    cfg = _cfg(config, root)
    if not cfg["enabled"]:
        return None
    import wg_need_goal as _ng
    if not _ng.is_code_path(path, config) or not _rr.runtime_data_verdict(path, str(root), None).owed:   # 讀檔不多跑 git
        return None
    key, top = _unmapped_key(root, path), top_dir(path, root)
    rec = (state.get("overview_hub") or {}).get(key)
    have = len(rec["part_files_read"]) if rec else 0
    need = int(cfg["min_overview_evidence"]["part_files"])
    readable = _readable_existing(root, top, need) if have < need else need
    v = _rr.unmapped_edit_verdict(need, readable, have)
    lines = []
    if v.owed:
        lines.append(remind_once(state, v.rule, key, f"改「{top}」下的程式檔前要先讀過同頂層目錄的檔（{v.why}）", "先 Read 同目錄的既有檔再改"))
    if _min_map_due(rec, path, cfg, config):
        lines.append(remind_once(state, "UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP", key,
                                 f"這個專案沒有部位表，第一次改「{top}」的程式檔前要交最小地圖三行",
                                 f"在回覆文字或{_rr.DECL_VIA_COMMENT}寫 地圖｜讀了：<讀過的檔>／地圖｜上游：…／地圖｜下游：…"))
    return "\n".join(ln for ln in lines if ln) or None


def _locate_read_hint(state: Dict[str, Any], session_id: str, root: Path, row: Dict[str, Any], path: str,
                      config: Dict[str, Any], agent_id: str = "") -> Optional[str]:
    """規則 LOCATE_HINT_ON_FIRST_READ：讀檔時碰到的部位（READ_TOUCH_NO_CARD：讀檔只建紀錄不送卡，這一行就是讀檔結果多出來的全部），
    本 session 第一次讀到它的程式檔（可以就是建紀錄的那次）→ 讀檔結果後附一行，講改之前 on_edit 與 wg_need_goal.edit_gate 要的東西：沒目標樹就先 need_goal set（判式同 edit_gate：tree_owed_for_edit）、
    定位行幾行（有樹或要立樹＝四行，同擋訊息 LOCATE_ASK_ONCE；need_goal 關＝三行）、寫在哪（回覆文字或不寫檔指令開頭的 # 註解，
    thinking 讀不到）。一部位一 session 一次（rec.locate_hint：注入時 due、送了 sent）；改檔時才補注入的部位（擋訊息已講過）、
    已交過定位、非程式檔（含知識類部位）、子代理讀的不送（不消耗主 session 的那一次）；v6 總開關關著不送（注入本身是 v6 以前就有的，
    關時照舊）。沒有改程式的意圖（既不是寫碼回合 wg_core.coding_turn，這則 prompt 的關鍵字也沒判成寫碼類 CODE_INTENTS）也不送、額度不消耗（locate_hint 留在 due，
    之後成了寫碼回合再讀到照送）：純問答讀程式檔不該被催交定位行。判定不動：沒照做照擋。"""
    rec = (state.get("overview_hub") or {}).get(_key(root, row))
    if (agent_id or not rec or rec.get("locate_hint") != "due" or rec.get("located") or not v6_enabled(config)
            or not _cfg(config, root)["enabled"]):
        return None
    import wg_need_goal as _ng
    # 有改程式的意圖才送：本回合已是寫碼回合（coding_turn），或這則 prompt 的關鍵字判成寫碼類（state turn_intent）——
    # 提示要趕在第一次改檔前到，而寫碼回合多半要到第一次改檔才成立，所以關鍵字意圖在這裡算數（純問答判成 general 不送）
    if not _ng.is_code_path(path, config) or not (coding_turn(state, config) or state.get("turn_intent") in CODE_INTENTS):
        return None
    need_tree = _ng.tree_owed_for_edit(session_id, path, config)
    try:
        four = need_tree or _ng.goal_for_edit(session_id, path, config) is not None
    except _ng.NeedGoalCorrupt:
        four = True                                  # 改檔時照擋，修法是重寫樹；樹立好之後就是四行
    rec["locate_hint"] = "sent"
    first = not state.get(_LOCATE_HINT_KEY)
    state[_LOCATE_HINT_KEY] = True
    remind_mark(state, "LOCATE_BEFORE_EDIT", row["part_short"])      # 這一行就是定位的提醒：之後沒交不擋、也不再提醒
    if need_tree:
        remind_mark(state, "CODE_EDIT_NEEDS_GOAL_TREE", "")
    _log("locate_hint", session_id, part=row["part_short"], path=path, need_tree=need_tree, four=four, first=first)
    return locate_read_hint(row["part_short"], need_tree, four, first)


def locate_read_hint(part: str, need_tree: bool, four: bool, first: bool) -> str:
    """LOCATE_HINT_ON_FIRST_READ 那一行：立樹＋定位併成一行。first＝本 session 第一則，給格式與管道（同缺定位擋訊息的要求）；
    之後的部位只點名、說格式同前。"""
    tree = ("先立需求目標樹（回覆文字寫一行「目標｜<整個需求一句，用使用者的話，只寫目標不寫手段>」，子目標每件一行「子目標｜…」，"
            "hook 照它立樹；備援 need_goal(action=set, goal=…)），再" if need_tree else "")
    if not first:
        return f"[Guardian:OverviewHub] 改【{part}】的程式檔前{tree}交定位{'四' if four else '三'}行（格式同前一則提示）。"
    lines = ("交定位四行：定位｜部位、定位｜根因層（候選 A …；候選 B …；選 A 因為 …，只找到一個就寫「第二個不存在因為 …」）、定位｜前例、"
             "定位｜批判（這段寫法合不合理、為什麼；看得出更好的做法就寫，同類在哪也寫；只查有沒有內容）" if four
             else "交定位三行：定位｜部位、定位｜根因層、定位｜前例")
    via_tree = "，或在 need_goal set／update 的 locate 欄一起交（不必另發註解指令）" if four else ""   # 三行版＝need_goal 關，沒這條路
    return (f"[Guardian:OverviewHub] 改【{part}】的程式檔前{tree}{lines}；寫在比改檔早一則的回覆文字，或{_rr.DECL_VIA_COMMENT}"
            f"（thinking 讀不到）{via_tree}；宣告完照常用 Edit／Write 改，不要改用 Bash／PowerShell 寫檔。")


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


# ─── 提醒帳（規則 REMIND_ON_PRIOR_RESULT、REMIND_PENDING_IN_STATE）：工具前守門判成提醒的那一件先記 state，下一個工具結果取走 ───
REMIND_SENT_KEY = "remind_sent"          # state：這個 session 送過的提醒鍵（wg_release_rules.remind_key）
REMIND_PENDING_KEY = "remind_pending"    # state：工具前記下、等下一個工具結果送出的提醒
REMIND_PENDING_CAP = 20


def remind_hit(rule: str, obj: Any, what: str, fix: str, extra: str = "") -> Dict[str, Any]:
    """一件提醒：規則名、對象（部位／頂層目錄鍵／空＝整個 session）、現象、做法、順帶要送的全文（例：改檔時才注入的導讀卡）。"""
    return {"rule": str(rule), "obj": str(obj or ""), "what": str(what or ""), "fix": str(fix or ""), "extra": str(extra or "")}


def locate_first_deny_due(state: Dict[str, Any], session_id: str, part: Any) -> bool:
    """規則 LOCATE_FIRST_EDIT_BLOCKS_ONCE（使用者裁定「只擋第一次」）：同一 session 第一次改某部位的程式檔、定位還沒交 → 擋這一次
    （訊息就是定位四行的要求）；記了之後同部位再缺定位只提醒不擋。回 True＝這次要擋（並已記）。state 寫不進去就當記過（偏放行）。"""
    book = state.setdefault("locate_first_deny", {})
    sid = str(session_id or "")
    seen = book.setdefault(sid, [])
    key = str(part or "")
    if key in seen:
        return False
    seen.append(key)
    return True


def remind_sent_list(state: Dict[str, Any]) -> List[str]:
    """state 的提醒帳本：**一份清單**（元素 remind_key；state 一 session 一檔，不再按 session 分桶）。
    舊寫法殘留的 dict（{sid: [鍵]}）攤平成清單、其他形狀重置，寫回 state 後回傳同一個物件（呼叫端 append 直接生效）。"""
    sent = state.get(REMIND_SENT_KEY)
    if isinstance(sent, dict):
        sent = [str(k) for v in sent.values() if isinstance(v, list) for k in v]
    elif not isinstance(sent, list):
        sent = []
    state[REMIND_SENT_KEY] = sent
    return sent


def remind_mark(state: Dict[str, Any], rule: str, obj: Any = "") -> bool:
    """記「這件提醒送過了」；本來沒送過回 True（呼叫端這時才送），送過回 False。"""
    sent = remind_sent_list(state)
    if not _rr.remind_due(sent, rule, obj):
        return False
    sent.append(_rr.remind_key(rule, obj))
    return True


def remind_once(state: Dict[str, Any], rule: str, obj: Any, what: str, fix: str) -> Optional[str]:
    """該提醒就組一行（remind_line）並記送過；送過回 None。給讀檔結果這類當場就能送的用。"""
    return _rr.remind_line(rule, what, fix) if remind_mark(state, rule, obj) else None


def remind_queue(state: Dict[str, Any], hit: Dict[str, Any]) -> None:
    """工具前守門：這件判成提醒、不擋，先記進 state，等下一個工具結果（PostToolUse）送。"""
    pend = state.setdefault(REMIND_PENDING_KEY, [])
    pend.append(dict(hit))
    del pend[:-REMIND_PENDING_CAP]


def remind_flush(state: Dict[str, Any], session_id: str) -> List[str]:
    """PostToolUse：取走等著的提醒；該送的（同規則同對象本 session 第一次）組一行＋順帶全文，送過的只留帳不重送。回要併進
    additionalContext 的段落。"""
    pend = state.pop(REMIND_PENDING_KEY, None) or []
    out: List[str] = []
    for hit in pend:
        rule, obj = str(hit.get("rule") or ""), hit.get("obj") or ""
        if not remind_mark(state, rule, obj):
            _log("remind_skipped", session_id, rule=rule, obj=obj)
            continue
        out.append(_rr.remind_line(rule, str(hit.get("what") or ""), str(hit.get("fix") or "")))
        if hit.get("extra"):
            out.append(str(hit["extra"]))
        _log("remind_sent", session_id, rule=rule, obj=obj)
    return out


def _cfg_error_deny(cfg: Dict[str, Any], session_id: str, file_path: str,
                    row: Optional[Dict[str, Any]]) -> Optional[Tuple[str, str, bool, Dict[str, Any]]]:
    """`_errors` 非空 → (訊息, deny 理由, False, 提醒件 GATE_SELF_ERROR)，訊息列全部錯誤；沒錯誤回 None。"""
    if not cfg["_errors"]:
        return None
    where = f"改【{row['part_short']}】部位的檔（{file_path}）" if row else f"改 {file_path}"
    msg = (f"[Guardian:OverviewHub] {where}前，這一層的 OverviewHub 設定有錯（{cfg['_layer']}），閘無法判定，先修設定："
           + "；".join(cfg["_errors"]))
    _log("edit_cfg_error", session_id, part=row["part_short"] if row else None, path=file_path,
         layer=cfg["_layer"], errors=cfg["_errors"])
    return (msg, msg, False, remind_hit("GATE_SELF_ERROR", "overview_hub", f"OverviewHub 設定有錯（{cfg['_layer']}），閘判不了",
                                        "修這一層的 overview-hub.json：" + "；".join(cfg["_errors"])))


def _row_layers(row: Dict[str, Any]) -> List[str]:
    """部位表「層」欄要人在根因層那行指明的層；「單層」與閱讀路徑層號「第 N 層」（程式依路徑推）不算。"""
    return [x.strip() for x in _LAYER_SPLIT_RE.split(row.get("layer") or "")
            if x.strip() and x.strip() != "單層" and not LAYER_AXIS_RE.fullmatch(x.strip())]


def _layer_mismatch(row: Dict[str, Any], vals: Dict[str, str]) -> Optional[str]:
    """部位表有「層」欄（單層以外）時，根因層那行必須指明其中一層；都沒提到＝填錯層或沒填層。"""
    layers = _row_layers(row)
    if not layers or any(l in vals.get("根因", "") for l in layers):
        return None
    return f"定位｜根因層 沒有指明這個部位的層（部位表列的層：{'／'.join(layers)}），填錯層或沒填層一律擋"


def _longer_parts(root: Path, row: Dict[str, Any]) -> List[str]:
    """同一張表裡包含這個部位名的更長部位名（UI → UI 設定）：定位行提到它們的那組不算這個部位的（locate_values exclude）。"""
    me = str(row.get("part_short") or "").lower()
    return [r["part_short"] for r in _table_rows(root)
            if r.get("part_short") and r["part_short"].lower() != me and me in r["part_short"].lower()]


def _goal_line_check(tree: Dict[str, Any], vals: Dict[str, str], session_id: str = "",
                     state: Optional[Dict[str, Any]] = None,
                     call: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], Any]:
    """定位核對（有需求目標樹時）：回 (節點, None) 通過；(節點, [Verdict…]) 要擋：第五行批判沒寫或沒內容（LOCATE_LINES_NEED_CRITIQUE），
    或根因層沒寫兩個候選與選擇理由（LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES）——兩候選一個使用者回合只問一次
    （規則 TWO_CANDIDATES_ASK_ONCE：擋次上限 1 則回覆，wg_core.deny_cap；call＝這次的 hook 輸入，同一則回覆平行送出的改檔
    算同一次問、一起擋，DENY_CAP_PER_REPLY；沒給 state 照每次問），之後只留帳。
    第四行目標節點與範例佔位（LOCATE_LINES_NO_EXAMPLE_PLACEHOLDER）只記錄不擋：沒寫或指錯節點就掛樹根（收尾 (f3) 從 transcript
    補掛），缺的記進 guard-need_goal（locate_soft）。"""
    import wg_need_goal as _ng
    node = _ng.node_ref(tree, vals.get("目標"))
    soft = [] if node else [("LOCATE_GOAL_NODE", "沒交第四行或節點不在目前的樹")]
    node = node or tree["id"]
    role = _rr.locate_lines_verdict(vals.get("根因", ""), vals.get("目標", ""), node,
                                    str(((tree.get("nodes") or {}).get(node) or {}).get("text") or ""))
    two = _rr.locate_candidates_verdict(vals.get("根因", ""))
    if role.owed and not two.owed:
        soft.append((role.rule, role.why))           # 第四行的角色：只記錄
    owed = [v for v in (_rr.locate_critique_verdict(vals.get("批判", "")),) if v.owed]
    if two.owed:
        if state is None or deny_cap(state, "two_candidates", [session_id], cap=1, call=call)[0]:
            owed.append(two)
        else:
            soft.append((two.rule, two.why))
    place = _rr.locate_placeholder_verdict(vals)
    if place.owed:
        soft.append((place.rule, place.why))
    if soft and session_id:
        _ng._guard("locate_soft", session_id, tree=tree["id"], rules=[r for r, _ in soft], why=[w[:120] for _, w in soft])
    return node, (owed or None)


def _locate_example(row: Dict[str, Any], tree: Dict[str, Any], node: Optional[str]) -> str:
    """擋訊息附的範例五行：部位名、這一部位要指明的層、要指的節點都填好；角括號是要換成自己判斷的地方，照抄不換不算交
    （規則 LOCATE_LINES_NO_EXAMPLE_PLACEHOLDER）。"""
    layers = _row_layers(row)
    return "\n".join((
        f"  定位｜部位：{row['part_short']}——<這次改哪個檔、哪一段>",
        f"  定位｜根因層：候選 A <第一個根因>{f'（{layers[0]}）' if layers else ''}；候選 B <第二個根因>；選 A 因為 <為什麼不是 B>",
        "  定位｜前例：<卡名>／無",
        "  定位｜批判：<這段寫法合不合理、為什麼；看得出更好的做法就寫；同類還可能在哪>",
        "  （合理就明說合理與原因；只查有沒有寫、有沒有內容，不認固定字樣）",
    ))


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


def _gitignored_set(root: Path, paths: List[str]) -> set:
    """git check-ignore 一次查一批（規則 RUNTIME_DATA_NO_OVERVIEW 的事實）：回被忽略的那些路徑；不在 git／逾時／出錯回空集合（當不忽略）。"""
    if not paths or not (root / ".git").exists():
        return set()
    try:
        r = subprocess.run(["git", "-C", str(root), "check-ignore", "-z", "--stdin"], input="\0".join(paths) + "\0",
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=2,
                           creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return set()
    return {p for p in r.stdout.split("\0") if p}


_READABLE_SCAN_CAP = 500   # 數同頂層目錄可讀檔最多看幾個檔；看滿還數不到要讀數 → 當作夠（不放寬）


def _readable_existing(root: Path, top: str, need: int) -> int:
    """同頂層目錄「非執行期資料的既有檔」數（規則 UNMAPPED_EDIT_NEEDS_READABLE_FILES 的事實），最多數到 need。
    (root) 只看根目錄本身的檔；其他看該目錄整棵樹（.git、快取目錄不進去）。執行期資料照 runtime_data_verdict 判
    （gitignored 一次查一批）。讀目錄出錯、看滿 _READABLE_SCAN_CAP 個檔 → 回 need（不放寬）。"""
    if need <= 0:
        return 0
    if top == "(outside)":
        return need
    files: List[str] = []
    try:
        if top == "(root)":
            files = [str(p) for p in root.iterdir() if p.is_file() and p.name != ".git"]   # worktree 根的 .git 是檔
        else:
            for dirpath, dirnames, filenames in os.walk(root / top):
                dirnames[:] = [d for d in dirnames if d != ".git" and d not in _rr.RUNTIME_CACHE_DIR_NAMES]
                files.extend(os.path.join(dirpath, f) for f in filenames)
                if len(files) >= _READABLE_SCAN_CAP:
                    break
    except OSError:
        return need
    files = [f for f in files[:_READABLE_SCAN_CAP] if _rr.runtime_data_verdict(f, str(root), None).owed]
    ignored = _gitignored_set(root, files)
    count = sum(1 for f in files if f not in ignored)
    return need if count < need and len(files) >= _READABLE_SCAN_CAP else min(count, need)


# ─── G14 最小地圖（規則 UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP；判定在 wg_release_rules，這裡收事實與組擋訊息） ───
MIN_MAP_ENTRY = (
    "  地圖｜讀了：<檔清單，相對專案根，用「、」分隔，至少 1 個本 session 讀過的檔>",
    "  地圖｜上游：<誰餵這一塊（檔或模組）／無，因為…>",
    "  地圖｜下游：<誰吃這一塊／無，因為…>",
    f"放在回覆文字或{_rr.DECL_VIA_COMMENT}（要比這次改檔早一則訊息送出；角括號換成你的判斷；可和定位行同一則訊息交）；"
    f"{_rr.DECL_KEEP_EDIT}。",          # 規則 DECL_HINT_KEEPS_EDIT_TOOLS
)
# 掃表預覽跑在子程序（逾時砍得掉）：lib/overview_scaffold.preview_lines，參數＝程式碼根、專案根、overview_scaffold 段、refix_churn 段
_PREVIEW_CODE = ("import json, sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
                 "from lib import overview_scaffold as sc; "
                 "print(chr(10).join(sc.preview_lines(Path(sys.argv[2]), json.loads(sys.argv[3]), json.loads(sys.argv[4]))))")
_PREVIEW_MAX_LINES = 15


def _min_map_due(rec: Optional[Dict[str, Any]], file_path: str, cfg: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """規則 UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP 的適用範圍：開關開著、同鍵還沒交過地圖、往上找不到任何部位表（有表專案的表外檔
    與根層不查）、這次寫入算改程式（wg_need_goal.writes_code，與需求目標閘同一判式）。"""
    if not cfg["min_map"]["enabled"] or (rec or {}).get("min_map_done") or find_map(file_path):
        return False
    import wg_need_goal as _ng
    return _ng.writes_code(file_path, config)


def _session_reads(state: Dict[str, Any]) -> set:
    """本 session 讀過的檔（canon_path）：所有部位紀錄的 part_files_read 與 reads_after（on_read 記的，與讀檔證據同源）。"""
    out: set = set()
    for rec in (state.get("overview_hub") or {}).values():
        if not isinstance(rec, dict):
            continue
        for p in list(rec.get("part_files_read") or []) + list(rec.get("reads_after") or []):
            out.add(_rr.canon_path(p))
    return out


_TRANSCRIPT_WHY = {
    "empty_path": "hook 沒收到 transcript_path（欄位為空）",
    "missing": "transcript 檔不存在",
    "unreadable": "transcript 檔存在但開不了（鎖住或無權限）",
    "empty": "transcript 檔存在但是空的",
}


def _transcript_self_error(session_id: str, what: str, why: str, transcript_path: str, **kw: Any) -> None:
    """規則 GATE_SELF_ERROR：讀不到 transcript＝閘驗不了 AI 交的那幾行、判不了 → 呼叫端放行；這裡 stderr 一行＋守門紀錄 error（不計次）。"""
    msg = f"{_TRANSCRIPT_WHY.get(why, why)}（{transcript_path or '欄位為空'}），驗不了{what}，這次放行"
    sys.stderr.write(f"[Guardian:OverviewHub] {msg}\n")
    append_guard_log("overview_hub", {"event": "error", "rule": "GATE_SELF_ERROR", "session_id": session_id,
                                      "check": what, "why": why, **kw})


def _min_map_check(state: Dict[str, Any], root: Path, transcript_path: str) -> Tuple[_rr.Verdict, Optional[str]]:
    """三管道（LOCATE_CHANNELS，與定位三行同一套）各取最後一組地圖三行，任一管道那組通過就算交；回 (判定, 通過的管道)。
    同根已有頂層目錄交過地圖 → 只認那次放行之後的 transcript（state["min_map"][<根>]["offset"]）。呼叫端先確認 transcript 讀得到。"""
    offset = int(((state.get("min_map") or {}).get(_root_key(root)) or {}).get("offset", 0))
    read = _session_reads(state)
    first_bad: Optional[_rr.Verdict] = None
    for ch in LOCATE_CHANNELS:
        group = _rr.min_map_group(assistant_text_after(transcript_path, offset, ch))
        if group is None:
            continue
        v = _rr.min_map_verdict(group, str(root), read)
        if not v.owed:
            return v, ch
        first_bad = first_bad or v
    return first_bad or _rr.min_map_verdict(None, str(root), read), None


def _min_map_preview(state: Dict[str, Any], root: Path, config: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[str, bool]:
    """擋訊息附的掃表預覽（子程序跑 preview_lines，上限 min_map.preview_timeout_s 秒）；每個專案根只跑一次，結果（含失敗）
    快取在 state["min_map"][<根>]，同根之後的擋訊息直接用。失敗或逾時 → 「掃表預覽失敗：<原因>」（照擋、stderr 說一聲）。
    回 (文字, 這次有沒有跑)。"""
    slot = state.setdefault("min_map", {}).setdefault(_root_key(root), {})
    if "preview" in slot:
        return slot["preview"], False
    timeout = float(cfg["min_map"]["preview_timeout_s"])
    args = [sys.executable, "-X", "utf8", "-c", _PREVIEW_CODE, str(Path(__file__).resolve().parents[1]), str(root),
            json.dumps(config.get("overview_scaffold") or {}), json.dumps(config.get("refix_churn") or {})]
    t0 = time.monotonic()
    out, fail = "", None
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW)
        out = r.stdout.decode("utf-8", errors="replace").strip()
        if r.returncode != 0 or not out:
            last = (r.stderr.decode("utf-8", errors="replace").strip().splitlines() or ["沒有輸出"])[-1]
            fail = f"exit {r.returncode}：{last[:200]}"
    except subprocess.TimeoutExpired:
        fail = f"逾時（超過 {timeout:g} 秒）"
    except OSError as e:
        fail = f"{type(e).__name__}: {e}"
    text = f"掃表預覽失敗：{fail}" if fail else "\n".join(out.splitlines()[:_PREVIEW_MAX_LINES])
    slot.update({"preview": text, "preview_ok": fail is None, "preview_ms": int((time.monotonic() - t0) * 1000)})
    if fail:
        sys.stderr.write(f"[Guardian:OverviewHub] {text}（{root}；同根不再重跑）\n")
    return text, True


def _min_map_lines(top: str, v: _rr.Verdict, preview: str) -> List[str]:
    return [f"最小地圖：這是本 session 第一次改「{top}」的程式檔，先寫出跟這次需求相關的最小地圖（讀了哪些檔、上游誰餵、"
            f"下游誰吃；地圖有缺塊隨時補讀）。程式只核對三行在不在、列的檔讀過沒，內容由你判斷。",
            _rr.format_hit("o", v), preview, "入口（照這個格式交三行）：", *MIN_MAP_ENTRY]


def _unmapped_edit(state: Dict[str, Any], session_id: str, root: Path, file_path: str, cfg: Dict[str, Any],
                   config: Optional[Dict[str, Any]] = None, transcript_path: str = "",
                   call: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], Optional[str], bool, Optional[Dict[str, Any]]]:
    """沒有部位表的專案、或表上沒列的檔：要求本 session 讀過同頂層目錄的檔，數量照規則 UNMAPPED_EDIT_NEEDS_READABLE_FILES
    （設定的 N 與該目錄可讀既有檔數取小）。執行期資料（gitignored、workflow/state*、Logs、快取目錄…；規則 RUNTIME_DATA_NO_OVERVIEW）免綜觀。
    往上找不到任何部位表的專案，第一次改某頂層目錄的程式檔前另要最小地圖三行（規則 UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP），
    擋訊息附掃表預覽；兩條都欠就同一則訊息列。第四個回傳值＝欠的那件提醒（規則、頂層目錄鍵、現象、做法），放行時 None。"""
    key = _unmapped_key(root, file_path)
    top = top_dir(file_path, root)
    v = _rr.runtime_data_verdict(file_path, str(root), _gitignored(root, file_path))
    if not v.owed:
        _log("edit_unmapped", session_id, path=file_path, root=str(root), top=top, rule=v.rule, deny_reason=None)
        return (None, None, False, None)
    need = int(cfg["min_overview_evidence"]["part_files"])
    rec = (state.get("overview_hub") or {}).get(key)
    have = len(rec["part_files_read"]) if rec else 0
    readable = _readable_existing(root, top, need) if have < need else need    # 讀夠了就不必數
    v = _rr.unmapped_edit_verdict(need, readable, have)
    unread = unread_rows_note(root / MAP_REL)       # 表在、卻有資料列因寫法整列沒讀到：說出來，不靜默當成沒列
    due = _min_map_due(rec, file_path, cfg, config or {})
    if due:
        ok, why = transcript_readable(transcript_path)
        if not ok:                                  # 規則 GATE_SELF_ERROR：驗不了地圖三行＝判不了，這次不要求（也不記成交過）
            _transcript_self_error(session_id, "最小地圖三行", why, transcript_path, path=file_path, root=str(root))
            due = False
    mm, via = _min_map_check(state, root, transcript_path) if due else (None, None)
    mm_owed = mm is not None and mm.owed
    preview, ran = _min_map_preview(state, root, config or {}, cfg) if mm_owed else ("", False)
    log_kw = dict(path=file_path, root=str(root), top=top, part_files_read=have, need=need, readable=readable,
                  layer=cfg.get("_layer"), min_map=None if mm is None else mm.owed, min_map_via=via, preview_ran=ran)
    if v.owed or mm_owed:
        if v.owed:
            lines = [f"[Guardian:OverviewHub] 改 {file_path} 前：這個專案（{root}）沒有部位表列到這個檔，"
                     f"閘只要求本 session 先讀過同頂層目錄「{top}」{v.why}。先讀再改。", _rr.format_hit("o", v)]
        else:
            lines = [f"[Guardian:OverviewHub] 改 {file_path} 前：這個專案（{root}）沒有部位表。"]
        if unread:
            lines.append(f"注意：{unread}")
        msg = "\n".join(lines + (_min_map_lines(top, mm, preview) if mm_owed else []))
        rule, deny_reason = (v.rule, "part_files") if v.owed else (mm.rule, "min_map")
        hit = (remind_hit(rule, key, f"改「{top}」下的檔前還沒讀過同頂層目錄的檔（{v.why}）", "先 Read 同目錄的既有檔再改") if v.owed
               else remind_hit(rule, key, f"這個專案沒有部位表，第一次改「{top}」的程式檔前要交最小地圖三行",
                               f"在回覆文字或{_rr.DECL_VIA_COMMENT}寫 地圖｜讀了：<讀過的檔>／地圖｜上游：…／地圖｜下游：…"))
        # 規則 GATE_DENY_CAP（同定位閘）：同一個使用者回合、同一個頂層目錄、同樣的缺件擋滿 DECL_DENY_CAP 則回覆 → 之後放行，
        # 越過上限那一次留帳（地圖三行交了閘卻看不到、讀了檔卻沒認到時不無限擋）。同缺件＝缺哪幾條與理由一樣，數字不算；
        # 同一則回覆平行送出的幾個改檔算一次（DENY_CAP_PER_REPLY）
        gap = hashlib.sha1(re.sub(r"\d+", "#", "\n".join(
            [deny_reason, v.why if v.owed else "", mm.why if mm_owed else ""])).encode("utf-8")).hexdigest()[:16]
        denied, released = deny_cap(state, "overview_unmapped", [f"{key}|{gap}"], call=call)
        if denied:
            _log("edit_unmapped", session_id, rule=rule, deny_reason=deny_reason, **log_kw)
            return (msg, msg, True, hit)
        if released:
            _log("edit_unmapped_capped", session_id, rule=rule, deny_reason=deny_reason, blocks=DECL_DENY_CAP, **log_kw)
        capped = (f"[Guardian:OverviewHub] 改 {file_path}：同一回合同樣的缺件已擋過，這次放行並留帳（{rule}）。")
    else:
        capped = None
    # 放行（含擋滿放行）：地圖這次真的通過才記成交過，擋滿放行的不記
    rec = state.setdefault("overview_hub", {}).setdefault(key, {"part_files_read": [], "edits": 0})
    rec["edits"] = int(rec.get("edits", 0)) + 1
    notes = [capped] if capped else []
    if mm is not None and not mm.owed:
        rec["min_map_done"], rec["min_map_via"] = True, via
        state.setdefault("min_map", {}).setdefault(_root_key(root), {})["offset"] = transcript_size(transcript_path)
        if via == "thinking":
            notes.append("[Guardian:OverviewHub] 最小地圖三行只在 thinking 裡，模型下回合與人都看不到；這次放行，"
                         f"請改放回覆文字或{_rr.DECL_VIA_COMMENT}，改檔照常用 Edit／Write。")
    if unread:
        notes.append(f"[Guardian:OverviewHub] 注意：{unread}")
    _log("edit_unmapped", session_id, rule=v.rule, edits=rec["edits"], deny_reason=None, capped=bool(capped), **log_kw)
    return ("\n".join(notes) or None, None, True, None)


def _unread_cards(state: Dict[str, Any], rec: Dict[str, Any]) -> List[str]:
    """指標制注入（rec.card_mode＝pointer）的部位：卡檔裡本 session 還沒讀過的（讀檔帳＝_session_reads，與讀檔證據同源）。
    整張注入、升級前沒有 card_mode 的舊紀錄、沒有卡的部位回空（卡已經送到眼前或本來就沒有卡）。"""
    if rec.get("card_mode") != "pointer":
        return []
    read = _session_reads(state)
    return [cp for cp in rec.get("card_paths") or [] if _rr.canon_path(cp) not in read]


def _card_unread_line(unread: List[str]) -> str:
    return (f"還沒 Read 這個部位的導讀卡：{'、'.join(unread)}（第一次碰到時只送了已知病灶一句與卡路徑，整張沒有注入；"
            "改之前先 Read：下一則讀卡時順便讀要改的檔）")


def on_edit(state: Dict[str, Any], session_id: str, file_path: str, transcript_path: str,
            config: Dict[str, Any], cwd: str = "", agent_id: str = "",
            tool_use_id: str = "") -> Tuple[Optional[str], Optional[str], bool]:
    """同 edit_check，只回前三個（警告文字, deny 理由, state 有沒有變）；送法由 edit_check 的第四個值（提醒件）配 RULE_MODE 決定。"""
    return edit_check(state, session_id, file_path, transcript_path, config, cwd, agent_id, tool_use_id)[:3]


def edit_check(state: Dict[str, Any], session_id: str, file_path: str, transcript_path: str,
               config: Dict[str, Any], cwd: str = "", agent_id: str = "",
               tool_use_id: str = "") -> Tuple[Optional[str], Optional[str], bool, Optional[Dict[str, Any]]]:
    """PreToolUse（Write／Edit／NotebookEdit／Bash／PowerShell 的每個寫入目標）：回 (警告文字, deny 理由, state 有沒有變, 提醒件)。
    提醒件（remind_hit：規則名、對象、現象、做法、順帶全文）只在有 deny 理由時給，呼叫端拿規則名查 gate_mode 決定照擋還是改提醒
    （規則 GATE_MODE_TABLE）；這裡的判定與擋訊息不因送法而變。
    agent_id＝子代理的工具呼叫：定位三行連子代理自己的 transcript 一起找（wg_core.transcripts_of）。
    tool_use_id＝這次工具呼叫的 id：擋次上限照「同一則回覆算一次」數（規則 DENY_CAP_PER_REPLY）；沒給照每個呼叫算。

    deny 理由帶注入文字（模型只看得到 permissionDecisionReason；card_injection＝full 是整張卡，pointer 是病灶一句＋卡路徑）。
    三項證據缺一即 deny；指標制注入的程式部位另要本 session Read 過卡（知識類部位沒讀只提醒、留帳）；transcript 讀不到 deny；
    readonly 命中 deny 不注入；定位三行只在 thinking 交的放行附提醒。cwd 目前只供記錄，判定全由檔案路徑決定。
    """
    if not file_path:
        return (None, None, False, None)
    if file_path.startswith("UNKNOWN:"):
        # 規則 UNKNOWN_TARGET_LOGGED：write_paths_from_tool 解析不出寫入目標（變數路徑、eval、cd -、內嵌碼…）→ 放行並留帳，不擋；
        # 讀得懂的照常判。PostToolUse 照舊記一筆未知寫入
        _log("edit_unknown_target", session_id, path=file_path, deny_reason=None, allowed=True)
        return (None, None, False, None)
    if _rr.is_temp_path(_long(file_path), _temp_roots()):
        # 規則 TEMP_COPY_NOT_PROJECT：暫存目錄下的副本不當專案（git archive 解到 scratchpad 的樹含部位表也一樣），不找表、不注入、不擋
        _log("edit_temp_copy", session_id, path=file_path, rule="TEMP_COPY_NOT_PROJECT", deny_reason=None)
        return (None, None, False, None)
    # 改的是 OverviewHub 自己的設定檔／部位表 → 不走 OverviewHub 流程（否則設定寫錯一個鍵就再也改不回來）；有錯仍回警告列出來讓模型知道在修什麼
    own, own_root = _own_config_layer(file_path)
    if own:
        errors = _cfg(config, own_root)["_errors"]
        if not errors:
            return (None, None, False, None)
        msg = (f"[Guardian:OverviewHub] 正在改 OverviewHub 自己的設定檔（{file_path}），放行以便修復。目前的設定錯誤："
               + "；".join(errors))
        _log("edit_own_config", session_id, path=file_path, errors=errors)
        return (msg, None, False, None)
    # 設定錯誤先於 enabled／命中判定：設定壞了（含 enabled 不是 bool）整層都不可信，一律 deny，沒命中部位表的檔也擋
    cfg = _cfg(config)
    denied = _cfg_error_deny(cfg, session_id, file_path, None)
    if denied:
        return denied
    if not cfg["enabled"]:
        return (None, None, False, None)
    hit = _lookup_quiet(file_path)
    if hit:
        root, row = hit
    else:
        root, row = write_target_root(file_path), None
        if root is None:
            return (None, None, False, None)
    cfg = _cfg(config, root)
    denied = _cfg_error_deny(cfg, session_id, file_path, row)
    if denied:
        return denied
    if not cfg["enabled"]:
        return (None, None, False, None)
    ro = _is_readonly(file_path, root, cfg)
    if ro:
        msg = (f"[Guardian:OverviewHub] {file_path} 在這一層的 readonly_paths（樣式「{ro}」）：程式產物／索引不可手改，"
               f"改來源或跑產生器。")
        _log("edit_readonly", session_id, path=file_path, pattern=ro, part=row["part_short"] if row else None,
             deny_reason="readonly", layer=cfg.get("_layer"))
        return (msg, msg, False, remind_hit("OVERVIEW_READONLY_PATHS", file_path, f"{file_path} 命中 readonly_paths（{ro}）", "改來源或跑產生器"))
    call = ({"tool_use_id": tool_use_id, "transcript_path": transcript_path, "agent_id": agent_id, "session_id": session_id}
            if tool_use_id else None)
    if row is None:
        return _unmapped_edit(state, session_id, root, file_path, cfg, config, transcript_path, call)
    key = _key(root, row)
    part = row["part_short"]
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
            return (msg, msg, True, remind_hit("OVERVIEW_CARD_MISSING", part, f"【{part}】的導讀卡找不到：{'、'.join(again['missing'])}",
                                               "補卡檔或修部位表的導讀卡欄"))
        if not rec.get("cards_missing") and again is None:
            rec["card_paths"] = [str(p) for p in paths]   # 升級前的舊紀錄：卡都在預設目錄，照常判定
        else:
            rec = None                              # 缺的卡出現了（或只在別處）：照第一次碰到這個部位重新注入
    pending = rec is not None and bool(rec.get("card_pending"))
    if rec is None or pending:
        # 沒碰過就改：建紀錄＋送卡；讀過但卡還沒送（READ_TOUCH_NO_CARD）：這一刀送卡，證據起點不動。兩種都回判定文字＋提醒件
        # OVERVIEW_CARD_BEFORE_EDIT（extra＝卡）：呼叫端照 RULE_MODE 送——v6 開是提醒、不擋，卡隨這次改檔的工具結果到（remind_flush）；
        # 釘成 block 的呼叫端才真擋
        text = (_deliver_card(state, session_id, root, row, file_path, cfg) if pending
                else _inject(state, session_id, root, row, file_path, "edit", transcript_path, cfg))
        cm = state["overview_hub"][key].get("cards_missing")
        if cm:
            mm = _missing_card_msg(row, cm)
            _log("edit_card_missing", session_id, part=row["part_short"], path=file_path, deny_reason="card_missing",
                 cards=cm["missing"], timed_out=cm["timed_out"], layer=cfg.get("_layer"))
            msg = f"{mm}\n{text.replace(chr(10) + mm, '')}"
            return (msg, msg, True, remind_hit("OVERVIEW_CARD_MISSING", part, f"【{part}】的導讀卡找不到：{'、'.join(cm['missing'])}",
                                               "補卡檔或修部位表的導讀卡欄"))
        once = not knowledge and v6_enabled(config) and locate_first_deny_due(state, session_id, part)
        # 規則 LOCATE_FIRST_EDIT_BLOCKS_ONCE：程式部位這個 session 第一次改 → 卡照舊送，另外先驗一次定位行（_first_edit_once）：
        # 交了就放、沒交就擋這一次（讀檔提示送過、卡才要送這兩個「不擋」設計都讓位）
        first = "先 Read 導讀卡" if _unread_cards(state, state["overview_hub"][key]) else "先讀完"
        if pending:
            todo = f"{first}再改" + ("（知識類部位不要求讀部位檔與定位三行）。" if knowledge else "；讀過的部位檔與交過的定位行照算。")
            msg = (f"[Guardian:OverviewHub] 第一次改【{row['part_short']}】部位的檔；讀檔時只送了一行，導讀卡現在才送（下面）。"
                   f"{todo}\n{text}")
            _log("edit_card_delivered", session_id, part=row["part_short"], path=file_path, deny_reason="card_pending",
                 intent=_intent_of(state), layer=cfg.get("_layer"), kind=_oh.KIND_KNOWLEDGE if knowledge else _oh.KIND_CODE)
            hit = remind_hit("OVERVIEW_CARD_BEFORE_EDIT", part, f"第一次改【{part}】部位的檔；讀檔時只送了一行，導讀卡現在才送（下面）", todo,
                             extra=text)
            if once:
                return _first_edit_once(state, session_id, root, row, file_path, transcript_path, agent_id, call, config, cfg, msg, hit)
            return (msg, msg, True, hit)
        todo = (f"{first}再改（知識類部位不要求讀部位檔與定位三行）。" if knowledge
                else f"{first}、讀過部位檔、在回覆交出定位三行，再改。")
        msg = (f"[Guardian:OverviewHub] 要改【{row['part_short']}】部位的檔但本 session 還沒看過這個部位的導讀卡；"
               f"卡片現在才注入（下面）。{todo}\n{text}")
        _log("edit_before_inject", session_id, part=row["part_short"], path=file_path, deny_reason="not_injected",
             intent=_intent_of(state), layer=cfg.get("_layer"), kind=_oh.KIND_KNOWLEDGE if knowledge else _oh.KIND_CODE)
        _note_block(state, key)
        hit = remind_hit("OVERVIEW_CARD_BEFORE_EDIT", part, f"改【{part}】部位的檔前本 session 還沒看過它的導讀卡",
                         f"卡隨這次改檔結果送到（下面）；{todo}", extra=text)
        if once:
            return _first_edit_once(state, session_id, root, row, file_path, transcript_path, agent_id, call, config, cfg, msg, hit)
        return (msg, msg, True, hit)
    _migrate_rec(rec)
    rec["edits"] = int(rec.get("edits", 0)) + 1
    if not knowledge:
        rec["kind"] = _oh.KIND_CODE        # 同一列也有寫碼命中（例：只撞到子字串）：scorecard 的 S3 要算這個部位
    unread = _unread_cards(state, rec)          # 指標制：卡沒送到眼前，要 Read 過才算看過（讀了就記在讀檔帳，這裡核對並落 log）
    if knowledge:
        # 知識類部位：三項證據只要「卡已注入」（走到這裡就成立）；指標制沒 Read 過卡只附一行提醒並記帳（card_unread），不擋。
        # 讀檔數照記（on_read），不查讀部位檔、定位三行、transcript
        _log("edit", session_id, part=row["part_short"], path=file_path, kind=_oh.KIND_KNOWLEDGE, located=bool(rec.get("located")),
             part_files_read=len(rec["part_files_read"]), depends_files_read=len(rec["depends_files_read"]),
             reads_after_inject=len(rec["reads_after"]), edits=rec["edits"], intent=rec.get("intent"),
             slices=rec.get("slices"), layer=cfg.get("_layer"), deny_reason=None,
             card_mode=rec.get("card_mode"), card_unread=len(unread))
        if unread:
            return (f"[Guardian:OverviewHub] 改【{row['part_short']}】部位的檔（{file_path}）：{_card_unread_line(unread)}"
                    "；知識類部位這次照放行，已留帳。", None, True, None)
        return (None, None, True, None)
    candidates: Optional[str] = None
    reads = rec["reads_after"]
    dirs = sorted({top_dir(p, root) for p in reads})
    part_files = rec["part_files_read"]
    depends_files = rec["depends_files_read"]
    ev = cfg["min_overview_evidence"]
    missing: List[str] = [_card_unread_line(unread)] if unread else []
    example_item = short_item = None      # LOCATE_EXAMPLE_ONCE_PER_SESSION：完整範例那一條與第二則起換上的短句
    deny_reason: Optional[str] = None
    warn: Optional[str] = None
    readable, why = transcript_readable(transcript_path)
    if not readable:
        # 規則 GATE_SELF_ERROR：讀不到 transcript（真開檔，不只 stat）＝閘驗不了定位行、判不了 → 這次不要求定位行，
        # stderr＋守門紀錄 error、不計次；讀檔數不靠 transcript，照查
        _transcript_self_error(session_id, "定位行", why, transcript_path, part=row["part_short"], path=file_path)
    if len(part_files) < int(ev["part_files"]):
        missing.append(f"注入導讀卡後還沒讀過這個部位的檔（要 ≥{ev['part_files']} 個，目前 {len(part_files)} 個；"
                       f"表外檔讀了 {len(reads) - len(part_files)} 個不算）")
    if len(depends_files) < int(ev["depends_files"]):
        missing.append(f"還沒讀過卡片指到的檔（要 ≥{ev['depends_files']} 個，目前 {len(depends_files)} 個）")
    n_evidence = len(missing)             # 讀檔證據缺的條數；之後加的都是定位行的（LOCATE_BLOCK_ONCE_PER_USER_TURN 用）
    # 有需求目標樹而且改的是程式檔：定位三行之後要第四行「定位｜目標：<節點編號>」，編號要在目前的樹（換了樹或節點放棄就重交）
    goal_tree = _goal_tree_for(session_id, file_path, config) if readable else None
    locate_gap: Optional[Dict[str, Any]] = None   # 定位行交了但內容不過（規則 LOCATE_LINES_NEED_CRITIQUE 等）：擋或放行決定後才落帳
    if readable and (not rec.get("located") or (goal_tree is not None and not _goal_linked(rec, goal_tree))):
        found_ch, text, node, bad_layer, bad_content = _find_locate(state, session_id, root, row, rec, transcript_path, agent_id,
                                                                   goal_tree, call)
        if found_ch is not None:
            warn = _mark_located(state, session_id, key, row, rec, found_ch, text, node, goal_tree)
        elif bad_layer:
            missing.append(bad_layer + "；補交一組正確的三行即可（取最後一組）")
            deny_reason = "wrong_layer"
        elif bad_content:
            vs_, node = bad_content
            missing.append("\n  ".join(_rr.format_hit('定位', v) for v in vs_)
                           + "\n  建議寫法（只是範例：候選、理由、批判與同類寫到了就算，句子順序不限；"
                             "角括號換成你對這一塊的判斷）：\n" + _locate_example(row, goal_tree, node))
            deny_reason = "locate_content"
            locate_gap = {"part": row["part_short"], "path": file_path, "tree": goal_tree["id"],
                          "rule": "、".join(v.rule for v in vs_), "why": [v.why[:120] for v in vs_]}
        else:
            item, short_item = _locate_ask(row, goal_tree, len(reads), len(dirs))
            example_item = item if short_item else None
            missing.append(item)
    if missing and deny_reason is None:
        deny_reason = "evidence"
    # 提醒件（規則 GATE_MODE_TABLE 用）：缺讀檔證據 → OVERVIEW_PART_FILES_READ；只缺定位行 → LOCATE_BEFORE_EDIT（讀檔提示送過就算提醒過）
    hit = None
    if missing:
        hit = (remind_hit("OVERVIEW_PART_FILES_READ", part, f"改【{part}】前還沒讀夠這個部位的檔（{missing[0].splitlines()[0][:80]}）",
                          "先 Read 部位檔與卡指到的檔，再交定位行") if n_evidence
               else remind_hit("LOCATE_BEFORE_EDIT", part, f"改【{part}】的程式檔前還沒交定位{'四' if goal_tree is not None else '三'}行",
                               f"寫在回覆文字或{_rr.DECL_VIA_COMMENT}：定位｜部位、根因層（兩候選＋選擇理由）、前例"
                               + ("、批判" if goal_tree is not None else "")))
    _log("edit", session_id, part=row["part_short"], path=file_path, located=bool(rec.get("located")),
         located_via=rec.get("located_via"), located_quality=rec.get("located_quality"),
         part_files_read=len(part_files), depends_files_read=len(depends_files),
         reads_after_inject=len(reads), dirs_after_inject=len(dirs), edits=rec["edits"],
         intent=rec.get("intent"), slices=rec.get("slices"), layer=cfg.get("_layer"), deny_reason=deny_reason,
         card_mode=rec.get("card_mode"), card_unread=len(unread), **({} if readable else {"self_error": why}))
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
        return (warn, None, True, None)
    turn = int(state.get("turn_seq", 0) or 0)
    # 規則 LOCATE_BLOCK_ONCE_PER_USER_TURN：同一個使用者回合定位閘已經擋過別的部位 → 這個部位只缺定位行時改一行提醒、放行、留帳；
    # 缺讀檔證據照擋，擋過的那個部位再缺照擋（照下面的擋次上限），下一個使用者回合重來
    blocked = _blocked_parts(state, _rr.user_turn(state, turn))
    lack = missing[0].splitlines()[0][:60]
    if n_evidence == 0 and blocked and key not in blocked:
        _log("edit_locate_reminded", session_id, part=row["part_short"], path=file_path, rule="LOCATE_BLOCK_ONCE_PER_USER_TURN",
             deny_reason=deny_reason, blocked_parts=len(blocked))
        _locate_gap_guard("locate_soft", session_id, locate_gap, released="LOCATE_BLOCK_ONCE_PER_USER_TURN")
        return (f"[Guardian:OverviewHub] 【{row['part_short']}】定位缺 {lack}，這次放行並留帳"
                "（這個使用者回合定位閘擋別的部位時已擋過一次，同回合不再擋）。", None, True, None)
    # 規則 GATE_DENY_CAP：同一個使用者回合、同一部位、同樣的缺件已擋 DECL_DENY_CAP 則回覆 → 之後放行，越過上限那一次留帳
    # （定位行交了閘卻看不到、讀了檔卻沒認到時不無限擋）；換回合重給。同缺件＝擋的理由與缺的條目一樣，讀了幾個檔、節點編號這類數字不算。
    # 同一則回覆平行送出的幾個改檔算一次（DENY_CAP_PER_REPLY）：AI 那時還沒看到第一則擋訊息，第 3 個起不因此放行
    gap = hashlib.sha1(re.sub(r"\d+", "#", "\n".join([str(deny_reason), *missing])).encode("utf-8")).hexdigest()[:16]
    denied, released = deny_cap(state, "overview_locate", [f"{key}|{gap}"], call=call)
    if not denied:
        # 放行訊息不寫「已擋 N 則」：N 是閘的計次（state 合併、同批判定都會讓它與實際擋次對不上），帳在 _overview-hub.log
        if released:
            _log("edit_deny_capped", session_id, part=row["part_short"], path=file_path, deny_reason=deny_reason,
                 blocks=DECL_DENY_CAP, gap=gap)
        _locate_gap_guard("locate_soft", session_id, locate_gap, released="GATE_DENY_CAP")
        return (f"[Guardian:OverviewHub] 【{row['part_short']}】定位缺 {lack}，這次放行並留帳"
                "（這個使用者回合同樣的缺件已擋過，同回合不再擋；下一個使用者回合還會查）。", None, True, None)
    # 規則 DENY_SAME_BATCH_SHORT：同一個使用者回合、同一部位、缺的跟上一則擋訊息一樣（平行送出的幾個改檔一起被擋）→
    # 只回一行指回上一則，不重送整段要求與判準卡；缺的變了（補交了一部分）才送新的全文
    sig = hashlib.sha1("\n".join([str(deny_reason), *missing]).encode("utf-8")).hexdigest()[:16]
    last = rec.get("last_deny") or {}
    rec["last_deny"] = {"turn": turn, "sig": sig}
    if last.get("turn") == turn and last.get("sig") == sig:
        msg = (f"[Guardian:OverviewHub] 改【{row['part_short']}】部位的檔（{file_path}）同樣被擋：缺的跟上一則擋訊息一樣"
               f"（{missing[0].splitlines()[0][:60]}…），照上一則一次補齊後再改。")
        _log("edit_deny_repeat", session_id, part=row["part_short"], path=file_path, deny_reason=deny_reason)
        _locate_gap_guard("locate_blocked", session_id, locate_gap)
        _note_block(state, key)
        return (msg, msg, True, hit)
    # 規則 LOCATE_EXAMPLE_ONCE_PER_SESSION：擋訊息精簡（guard.deny_text_slim）開、本 session 已送過一則完整範例 → 這條換短句；
    # 缺件清單本身不換（擋次上限與同批短訊息照原文比，換了字不會重新計次）
    again = example_item is not None and _rr.deny_slim_enabled(config) and bool(state.get(_EXAMPLE_SENT_KEY))
    shown = [short_item if again and m is example_item else m for m in missing]
    if example_item is not None and not again:
        state[_EXAMPLE_SENT_KEY] = True
    msg = (f"[Guardian:OverviewHub] 改【{row['part_short']}】部位的檔（{file_path}）前的證據不足，一律擋：\n"
           + "\n".join(f"- {m}" for m in shown))
    _locate_gap_guard("locate_blocked", session_id, locate_gap)
    _note_block(state, key)
    return (msg, msg, True, hit)


def _locate_gap_guard(event: str, session_id: str, gap: Optional[Dict[str, Any]], **extra: Any) -> None:
    """定位行內容不過的那筆帳（guard-need_goal）：真的 deny 記 locate_blocked；放行（同回合擋過一次、擋次上限）記 locate_soft 並帶
    released=哪條規則放的。沒有內容不過的缺件（缺讀檔證據、完全沒交）不記。"""
    if not gap:
        return
    import wg_need_goal as _ng
    _ng._guard(event, session_id, **gap, **extra)


def _find_locate(state: Dict[str, Any], session_id: str, root: Path, row: Dict[str, Any], rec: Dict[str, Any],
                 transcript_path: str, agent_id: str, goal_tree: Optional[Dict[str, Any]],
                 call: Optional[Dict[str, Any]]) -> Tuple[Optional[str], str, Optional[str], Optional[str], Optional[Tuple[Any, Any]]]:
    """三管道（LOCATE_CHANNELS）各取「最後一組」定位行（被擋後補交的那組才是現行）；任一管道那組通過層檢查（有樹再與第四行核對）即命中。
    回 (命中的管道或 None, 那管道的文字, 節點, 層不對的說明, 內容不過的 (缺件, 節點))。不改 rec。"""
    found_ch, bad_layer, bad_content, text, node = None, None, None, "", None
    longer = _longer_parts(root, row)
    for ch in LOCATE_CHANNELS:
        text = _texts_after(rec, transcript_path, agent_id, ch)
        vals = locate_values(text, row["part_short"], rec.get("locate_template"), longer)
        if not vals:
            continue
        bad = _layer_mismatch(row, vals)
        if bad:
            bad_layer = bad
            continue
        if goal_tree is not None:
            node, why = _goal_line_check(goal_tree, vals, session_id, state, call)
            if why:
                bad_content = (why, node)
                continue
        found_ch = ch
        break
    return found_ch, text, node, bad_layer, bad_content


def _mark_located(state: Dict[str, Any], session_id: str, key: str, row: Dict[str, Any], rec: Dict[str, Any], found_ch: str,
                  text: str, node: Optional[str], goal_tree: Optional[Dict[str, Any]]) -> Optional[str]:
    """定位行命中：rec 標 located（管道、品質）、有樹就掛節點；只在 thinking 交的回一行放行附帶的提醒（規則 LOCATE_NOT_IN_THINKING）。"""
    rec["located"] = True
    rec["located_via"] = found_ch
    rec["located_quality"] = locate_quality(text, row["part_short"], _card_texts(rec), rec.get("locate_template"))
    if goal_tree is not None:
        import wg_need_goal as _ng
        rec["goal_tree"], rec["goal_node"] = goal_tree["id"], node
        _ng.link_part(session_id, key, node, int(state.get("turn_seq", 0)))
    if found_ch == "thinking":
        return (f"[Guardian:OverviewHub] 【{row['part_short']}】的定位三行只在 thinking 裡，模型下回合與人都看不到；"
                f"這次放行，請改放回覆文字或{_rr.DECL_VIA_COMMENT}，改檔照常用 Edit／Write。")
    return None


def _row_for_locate(part: str, cwd: str) -> Tuple[Optional[Tuple[Path, Dict[str, Any]]], str]:
    """locate 欄的 part：絕對／相對檔路徑 → 查表（_lookup_quiet）；部位名 → cwd 所在專案的表列（part_short 或 part 全名）。
    回 ((root, row) 或 None, 命中用的檔路徑或空字串)。"""
    p = str(part or "").strip()
    looks_path = os.path.isabs(p) or ("/" in p or "\\" in p)
    cand = p if os.path.isabs(p) else (os.path.join(cwd, p) if cwd and looks_path else "")
    hit = _lookup_quiet(cand) if cand else None
    if hit:
        return hit, cand
    found = find_map(cwd) if cwd else None
    if not found:
        return None, ""
    root = found[0]
    for row in _table_rows(root):
        if p.lower() in (str(row.get("part_short") or "").lower(), str(row.get("part") or "").lower()):
            return (root, row), ""
    return None, ""


def locate_from_goal(state: Dict[str, Any], session_id: str, cwd: str, transcript_path: str,
                     locate: Any, config: Dict[str, Any]) -> List[str]:
    """規則 LOCATE_VIA_NEED_GOAL：need_goal set／update 的 locate 欄 [{part, lines}]——改程式前的定位四行隨目標樹那一次呼叫
    一起交，不必另發一條只有 `#` 註解的指令（007 實測：每個部位多一個模型回合、一次約 10 萬 token 輸入）。每項：part（部位名或
    檔路徑）對到部位表列；lines 併成文字走改檔時同一套判定——locate_values 取組、_layer_mismatch 層、有樹時 _goal_line_check
    第四／五行內容（兩候選、批判；不計 two_candidates 擋次）；通過 → rec 標 located（_mark_located，via=need_goal）並掛節點，
    沒紀錄的部位先建紀錄（_inject deliver=False，卡等第一次改檔才送）；不過 → 不算交、回一行說缺什麼（改檔前照舊補交）。
    OverviewHub／v6 關：整道不動，回一行說沒套用。回要附在 need_goal 回覆之後的行；帳 located_via_need_goal／locate_via_need_goal_rejected。"""
    import wg_need_goal as _ng
    items = locate if isinstance(locate, list) else []
    if not items:
        return []
    if not _cfg(config)["enabled"]:
        return ["[Guardian:OverviewHub] locate 欄沒套用（OverviewHub／v6 關著），定位照舊在改檔前交"]
    try:
        tree = _ng.active_tree(_ng.load(session_id))
    except Exception:  # noqa: BLE001  目標檔壞了由 edit_gate 那一道報；這裡當沒樹（三行版）
        tree = None
    out: List[str] = []
    for it in items:
        part = str((it or {}).get("part") or "") if isinstance(it, dict) else ""
        lines = [str(x) for x in ((it or {}).get("lines") or [])] if isinstance(it, dict) else []
        hit, hit_path = _row_for_locate(part, cwd)
        if not hit:
            _log("locate_via_need_goal_rejected", session_id, part=part, why="no_part")
            out.append(f"[Guardian:OverviewHub] locate 的「{part}」對不到部位表（部位名或該部位的檔路徑；cwd={cwd or '?'}），這項沒收")
            continue
        root, row = hit
        key = _key(root, row)
        rec = (state.get("overview_hub") or {}).get(key)
        template = rec.get("locate_template") if isinstance(rec, dict) else _locate_template(_cfg(config, root))
        text = "\n".join(lines)
        vals = locate_values(text, row["part_short"], template, _longer_parts(root, row))
        if not vals:
            _log("locate_via_need_goal_rejected", session_id, part=row["part_short"], why="missing_lines")
            out.append(f"[Guardian:OverviewHub] 【{row['part_short']}】的 locate 沒收：缺定位三行（定位｜部位／根因層／前例各一行，"
                       f"部位行要提到「{row['part_short']}」）；改檔前照舊補交")
            continue
        bad = _layer_mismatch(row, vals)
        if bad:
            _log("locate_via_need_goal_rejected", session_id, part=row["part_short"], why="wrong_layer")
            out.append(f"[Guardian:OverviewHub] 【{row['part_short']}】的 locate 沒收：{bad}")
            continue
        knowledge = isinstance(rec, dict) and rec.get("kind") == _oh.KIND_KNOWLEDGE
        goal_tree = tree if (tree is not None and not knowledge) else None
        node = None
        if goal_tree is not None:
            node, owed = _goal_line_check(goal_tree, vals, session_id, None, None)
            if owed:
                _log("locate_via_need_goal_rejected", session_id, part=row["part_short"], why="content",
                     rules=[v.rule for v in owed])
                out.append(f"[Guardian:OverviewHub] 【{row['part_short']}】的 locate 沒收：\n  "
                           + "\n  ".join(_rr.format_hit("定位", v) for v in owed))
                continue
        if not isinstance(rec, dict):
            prefixes = row.get("prefixes") or []
            seed = hit_path or (str(root / prefixes[0]) if prefixes else str(root))
            _inject(state, session_id, root, row, seed, "need_goal", transcript_path, _cfg(config, root), deliver=False)
            rec = state["overview_hub"][key]
        _migrate_rec(rec)
        _mark_located(state, session_id, key, row, rec, "need_goal", text, node, goal_tree)
        rec["locate_hint"] = "sent"          # 已交，之後讀這部位的程式檔不再提示
        _log("located_via_need_goal", session_id, part=row["part_short"], node=node, tree=goal_tree["id"] if goal_tree else None,
             four=goal_tree is not None)
        out.append(f"[Guardian:OverviewHub] 【{row['part_short']}】定位已收（隨目標樹交）；改它的程式檔不再要求定位行")
    return out


def _first_edit_once(state: Dict[str, Any], session_id: str, root: Path, row: Dict[str, Any], file_path: str, transcript_path: str,
                     agent_id: str, call: Optional[Dict[str, Any]], config: Dict[str, Any], cfg: Dict[str, Any],
                     msg: str, hit: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], bool, Dict[str, Any]]:
    """規則 LOCATE_FIRST_EDIT_BLOCKS_ONCE（使用者裁「只擋第一次」）：卡剛送（msg／hit＝卡那一件，呼叫端已建好）、這個 session 第一次改這個部位
    的程式檔。先驗一次定位行：交了 → 標 located、放行，卡照舊當提醒件（hit）隨這次工具結果到；沒交 → 這一次擋，訊息＝卡＋定位要求
    （同一般缺件的 _locate_ask），提醒件標 block_once 給 pre_tool_use（擋、並把卡排進提醒）。定位的提醒記成送過（這則就是要求）；
    不動定位閘的擋次帳（deny_cap／last_deny／擋過的部位）——那些從下一次改檔起算。留帳 edit_blocked_once。"""
    key = _key(root, row)
    rec = state["overview_hub"][key]
    part = row["part_short"]
    try:
        goal_tree = _goal_tree_for(session_id, file_path, config)
    except Exception:  # noqa: BLE001  目標檔壞了由 wg_need_goal.edit_gate 那一道報；這裡只決定要求幾行
        goal_tree = None
    if rec.get("located") and (goal_tree is None or _goal_linked(rec, goal_tree)):
        # 規則 LOCATE_VIA_NEED_GOAL：定位已隨 need_goal set／update 的 locate 欄交過（locate_from_goal）→ 這一次不擋、不掃 transcript
        _log("edit_first_located", session_id, part=part, path=file_path, rule="LOCATE_FIRST_EDIT_BLOCKS_ONCE",
             located_via=rec.get("located_via"))
        return (None, None, True, hit)
    readable, _why = transcript_readable(transcript_path)
    if readable:
        found_ch, text, node, _bl, _bc = _find_locate(state, session_id, root, row, rec, transcript_path, agent_id, goal_tree, call)
        if found_ch is not None:
            warn = _mark_located(state, session_id, key, row, rec, found_ch, text, node, goal_tree)
            _log("edit_first_located", session_id, part=part, path=file_path, rule="LOCATE_FIRST_EDIT_BLOCKS_ONCE", located_via=found_ch)
            return (warn, None, True, hit)
    reads = rec.get("reads_after") or []
    ask, _short = _locate_ask(row, goal_tree, len(reads), len({top_dir(p, root) for p in reads}))
    remind_mark(state, "LOCATE_BEFORE_EDIT", part)                     # 這則就是定位的提醒：之後同部位缺定位不擋、也不再提醒
    _log("edit_blocked_once", session_id, part=part, path=file_path, rule="LOCATE_FIRST_EDIT_BLOCKS_ONCE",
         deny_reason="locate_first", four=goal_tree is not None, readable=readable, layer=cfg.get("_layer"))
    full = (f"{msg}\n[Guardian:OverviewHub] 本 session 第一次改【{part}】部位的程式檔（{file_path}）還沒交定位行，這一次擋；"
            f"交了就放，之後同部位再缺只提醒不擋：\n- {ask}")
    return (full, full, True, {**hit, "block_once": True})



def _locate_ask(row: Dict[str, Any], goal_tree: Optional[Dict[str, Any]], n_reads: int, n_dirs: int) -> Tuple[str, Optional[str]]:
    """擋訊息裡「還沒交定位行」那一條。規則 LOCATE_ASK_ONCE：第一次擋就把內容要求（兩個候選＋選擇理由、節點與角色、批判的判斷）
    與填好部位、節點的範例一起給，一次交齊；不先只給骨架、交了再擋一輪說格式不對。規則 LOCATE_NOT_IN_THINKING：thinking 那條路講死
    （受測設定 thinking 不落盤，AI 寫了還被擋第二次）。回 (完整那一條, 第二則起換上的短句)；沒有樹是三行版、沒有短句。"""
    where = (f"寫在回覆文字，或{_rr.DECL_VIA_COMMENT}，或在 need_goal(action=set／update) 的 locate 欄一起交"
             f"（[{{part, lines}}]，不必另發註解指令）；不要寫在 thinking：thinking 預設不寫進 transcript，"
             f"hook 讀不到，只寫在那裡照樣會再擋一次；"
             f"{_rr.DECL_KEEP_EDIT}")         # 規則 DECL_HINT_KEEPS_EDIT_TOOLS
    if goal_tree is None:
        return (f"還沒交出定位三行（注入導讀卡後讀了 {n_reads} 個檔、跨 {n_dirs} 個目錄）。{where}："
                "定位｜部位：…／定位｜根因層：…／定位｜前例：…", None)
    head = f"還沒交出定位行（注入導讀卡後讀了 {n_reads} 個檔、跨 {n_dirs} 個目錄）。"
    item = (f"{head}{where}。"
            "一次交齊四行：定位三行（根因層寫兩個候選與選擇理由：候選 A …；候選 B …；選 A 因為 …，只找到一個就寫"
            "「第二個不存在因為 …」），加一行批判——這段寫法合不合理、為什麼，看得出更好的做法就寫，同類在哪也寫（只查有沒有內容）。"
            "範例（角括號換成你的判斷，句子順序不限）：\n"
            + _locate_example(row, goal_tree, None))
    return (item, f"{head}{LOCATE_EXAMPLE_AGAIN}")


_BLOCKED_KEY = "overview_locate_blocked"
_EXAMPLE_SENT_KEY = "overview_locate_example_sent"
LOCATE_EXAMPLE_AGAIN = ("四行格式同本 session 第一則定位擋訊息；寫在回覆文字或不寫檔指令開頭的 `#` 註解（thinking 讀不到），"
                        "宣告完照常用 Edit／Write 改，不要改用 Bash／PowerShell 寫檔")


def _blocked_parts(state: Dict[str, Any], uturn: int) -> List[str]:
    """LOCATE_BLOCK_ONCE_PER_USER_TURN：這個使用者回合（wg_release_rules.user_turn）定位閘已經擋過的部位鍵；換回合是空的。"""
    rec = state.get(_BLOCKED_KEY)
    return [str(p) for p in rec.get("parts") or []] if isinstance(rec, dict) and rec.get("turn") == uturn else []


def _note_block(state: Dict[str, Any], key: str) -> None:
    """定位閘擋了這個部位：記進這個使用者回合擋過的部位（換回合從空的起）。"""
    uturn = _rr.user_turn(state, int(state.get("turn_seq", 0) or 0))
    state[_BLOCKED_KEY] = {"turn": uturn, "parts": list(dict.fromkeys([*_blocked_parts(state, uturn), key]))}
