"""wg_overview — OverviewHub 的 state 層：三個 hook 各呼叫一個函式。

做什麼：第一次碰到某部位（Read／Bash 讀檔、提示詞提到路徑、或直接 Edit）就依本回合意圖（state["turn_intent"]）
查 goal_weights 選片注入該部位導讀卡（沒片命中退整卡），一個 session 一個部位只注入一次；之後記「注入後讀了
哪些檔、其中幾個是部位檔」；改檔前三項證據缺一即 deny：導讀卡已注入（不可關）、讀過部位檔 ≥N、交了定位三行
（三行在 thinking 交的放行附提醒）。readonly_paths 命中一律 deny 不注入；transcript 讀不到視為環境異常，deny。
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

import codecs
import fnmatch
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (
    CLAUDE_DIR, CONFIG_PATH, _atom_debug_error, _deep_merge, _layer_kind_for_root, _map_path_of,
    org_memory_root, resolve_project_root,
)

sys.path.insert(0, str(CLAUDE_DIR / "lib"))
from overview_hub import (  # noqa: E402
    MAP_REL, SLICE_NAMES, assistant_text_after, build_injection_ex, find_map, locate_channel, locate_quality,
    locate_values, match_row, parse_map, read_paths_from_tool, resolve_card, top_dir, transcript_size,
)

LOG_PATH = CLAUDE_DIR / "workflow" / "_overview-hub.log"   # _*.log 不進版控
HUB_REL = Path(".claude") / "overview-hub.json"

# 十個 intent 鍵固定（介面凍結，與 wg_atoms.INTENT_PATTERNS＋general 對拍；verify_intent_goal_weights 驗）
INTENT_KEYS = ("debug", "feature", "refactor", "perf", "new_project", "build", "design", "recall", "handoff", "general")
_GOAL_WEIGHT_KEYS = ("slices", "lens", "ask_first")
_EVIDENCE_KEYS = ("card", "part_files", "depends_files")

# 變量預設（預計畫附錄 D）；合併順序 _DEFAULT < config.json overview_hub < <公司根>/.claude/overview-hub.json
# < <專案根>/.claude/overview-hub.json，巢狀 dict 深合併、list 整個取覆蓋方。
_DEFAULT: Dict[str, Any] = {
    "enabled": True,
    "max_card_chars": 6000,
    "locate_template": [],
    "locate_extra": {},
    "path_bases": [],
    "vcs_roots": [],
    "commit_encoding": "utf-8",
    "source_encodings": ["utf-8"],
    "eol_policy": "per-file-head",
    "PYTHONIOENCODING": "utf-8",
    "readonly_paths": [],
    "min_overview_evidence": {"card": True, "part_files": 1, "depends_files": 0},
    "candidate_top_n": 5,
    "root_cause_triggers": ["根因", "治本", "為什麼又", "又壞", "重複發生", "老問題", "root cause", "again"],
    # 目的加權（預計畫第二節）：意圖 → 先送哪幾片、用哪個視角、先問哪題；空 slices＝整卡原序
    "goal_weights": {
        "debug": {"slices": ["defects", "verify", "authority"], "lens": "目標視角", "ask_first": "幾份存法、有無訊號"},
        "new_project": {"slices": ["authority", "what", "ask"], "lens": "目標視角", "ask_first": "資料到底存哪"},
        "feature": {"slices": ["what", "authority", "verify"], "lens": "理解視角", "ask_first": "上游誰餵下游誰吃"},
        "refactor": {"slices": ["what", "verify", "defects"], "lens": "數彎視角", "ask_first": "這條路拐幾個彎"},
        "perf": {"slices": ["verify", "defects", "what"], "lens": "目標視角", "ask_first": "量尺在哪門檻多少"},
        "build": {"slices": ["authority", "verify"], "lens": "目標視角", "ask_first": ""},
        "design": {"slices": ["authority", "what"], "lens": "理解視角", "ask_first": ""},
        "recall": {"slices": [], "lens": "", "ask_first": ""},
        "handoff": {"slices": [], "lens": "", "ask_first": ""},
        "general": {"slices": [], "lens": "", "ask_first": ""},
    },
}
_KNOWN_KEYS = frozenset(_DEFAULT)
_RETIRED_KEYS = ("dry_run", "deny_parts")          # 退役：閘一律擋；出現只警告一次，不報錯
_EOL_POLICIES = ("lf", "crlf", "per-file-head")
_LIST_OF_STR_KEYS = ("vcs_roots", "readonly_paths", "root_cause_triggers", "locate_template", "source_encodings")
_DICT_KEYS = ("locate_extra", "min_overview_evidence", "goal_weights")
_ENCODING_KEYS = ("commit_encoding", "PYTHONIOENCODING")
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


def _read_override(path: Path, label: str) -> Tuple[Dict[str, Any], List[str]]:
    """<層根>/.claude/overview-hub.json → (資料, 錯誤)。沒檔 ({}, [])；讀不到／壞 JSON／頂層不是物件 → ({}, [一條錯誤])，
    呼叫端把錯誤併進 `_errors`（設定壞了整層不可信，Edit 要擋，不是略過）。"""
    try:
        if not path.is_file():
            return {}, []
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {}, [f"{label}覆蓋檔讀取失敗：{path}：{e}"]
    if not isinstance(data, dict):
        return {}, [f"{label}覆蓋檔頂層不是物件：{path}"]
    return data, []


def _same_dir(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except (OSError, ValueError):
        return False


def _is_list_of_str(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _is_nonneg_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _encoding_ok(name: Any) -> bool:
    if not isinstance(name, str) or not name:
        return False
    try:
        codecs.lookup(name)
        return True
    except (LookupError, ValueError, TypeError):   # 查不到、含 NUL（ValueError）、怪型別都算壞編碼，不往外拋
        return False


def _validate_path_bases(bases: Any, root: Optional[Path]) -> List[str]:
    """每項要是存在的目錄（相對路徑以 root 為基準），且彼此不重複、不互相包含（否則同一相對路徑兩基準都命中＝歧義）。"""
    if not _is_list_of_str(bases):
        return ["path_bases 必須是字串陣列"]
    errors: List[str] = []
    resolved: List[Tuple[str, Path]] = []
    for b in bases:
        p = Path(b)
        if not p.is_absolute():
            if root is None:
                errors.append(f"path_bases「{b}」是相對路徑但沒有專案根可解析")
                continue
            p = root / p
        try:
            if not p.is_dir():
                errors.append(f"path_bases「{b}」不是存在的目錄")
                continue
            resolved.append((b, p.resolve()))
        except (OSError, ValueError) as e:
            errors.append(f"path_bases「{b}」無法解析：{e}")
    for i, (bi, pi) in enumerate(resolved):
        for bj, pj in resolved[i + 1:]:
            if pi == pj or pi in pj.parents or pj in pi.parents:
                errors.append(f"path_bases「{bi}」與「{bj}」重疊，同一相對路徑會兩邊都命中（歧義）")
    return errors


def _validate_goal_weights(gw: Any) -> List[str]:
    """goal_weights：鍵 ⊆ 十個 intent；值 {slices ⊆ SLICE_NAMES, lens: str, ask_first: str}。"""
    if not isinstance(gw, dict):
        return ["goal_weights 必須是物件"]
    errors: List[str] = []
    for intent, spec in sorted(gw.items()):
        if intent not in INTENT_KEYS:
            errors.append(f"goal_weights 的意圖「{intent}」不在十鍵內（{'／'.join(INTENT_KEYS)}）")
            continue
        if not isinstance(spec, dict):
            errors.append(f"goal_weights.{intent} 必須是物件")
            continue
        for k in sorted(spec):
            if k not in _GOAL_WEIGHT_KEYS:
                errors.append(f"goal_weights.{intent} 有未知鍵「{k}」")
        slices = spec.get("slices", [])
        if not _is_list_of_str(slices):
            errors.append(f"goal_weights.{intent}.slices 必須是字串陣列")
        else:
            errors.extend(f"goal_weights.{intent}.slices 有未知的片「{s}」（可用：{'／'.join(SLICE_NAMES)}）"
                          for s in slices if s not in SLICE_NAMES)
        for k in ("lens", "ask_first"):
            if not isinstance(spec.get(k, ""), str):
                errors.append(f"goal_weights.{intent}.{k} 必須是字串")
    return errors


def _validate_evidence(ev: Any) -> List[str]:
    """min_overview_evidence：card 必為 true（讀卡不可關）；part_files／depends_files 為 0 以上整數；無其他鍵。"""
    if not isinstance(ev, dict):
        return ["min_overview_evidence 必須是物件"]
    errors = [f"min_overview_evidence 有未知鍵「{k}」" for k in sorted(ev) if k not in _EVIDENCE_KEYS]
    if ev.get("card") is not True:
        errors.append("min_overview_evidence.card 必須是 true：讀導讀卡不可關")
    for k in ("part_files", "depends_files"):
        if not _is_nonneg_int(ev.get(k)):
            errors.append(f"min_overview_evidence.{k} 必須是 0 以上的整數")
    return errors


def _validate_cfg(c: Dict[str, Any], root: Optional[Path]) -> List[str]:
    """合併後設定的錯誤清單（空＝通過）。未知鍵報錯；退役鍵只警告一次；底線開頭的鍵（_doc、_errors）不檢查。"""
    errors: List[str] = []
    for key in sorted(c):
        if key.startswith("_") or key in _KNOWN_KEYS:
            continue
        if key in _RETIRED_KEYS:
            _warn_once(f"retired:{key}", f"設定鍵「{key}」已退役（閘一律擋，明寫也不放行），請從 overview-hub.json／config.json 移除")
            continue
        errors.append(f"未知的設定鍵「{key}」")
    if not isinstance(c.get("enabled"), bool):
        errors.append("enabled 必須是 true／false")
    if not isinstance(c.get("max_card_chars"), int) or isinstance(c.get("max_card_chars"), bool) or c["max_card_chars"] <= 0:
        errors.append("max_card_chars 必須是正整數")
    if not _is_nonneg_int(c.get("candidate_top_n")):
        errors.append("candidate_top_n 必須是 0 以上的整數")
    for key in _LIST_OF_STR_KEYS:
        if not _is_list_of_str(c.get(key)):
            errors.append(f"{key} 必須是字串陣列")
    for key in _DICT_KEYS:
        if not isinstance(c.get(key), dict):
            errors.append(f"{key} 必須是物件")
    for key in _ENCODING_KEYS:
        if not _encoding_ok(c.get(key)):
            errors.append(f"{key}「{c.get(key)}」不是 Python 認得的編碼")
    if _is_list_of_str(c.get("source_encodings")):
        errors.extend(f"source_encodings「{e}」不是 Python 認得的編碼" for e in c["source_encodings"] if not _encoding_ok(e))
    if c.get("eol_policy") not in _EOL_POLICIES:
        errors.append(f"eol_policy 必須是 {'／'.join(_EOL_POLICIES)} 之一")
    errors.extend(_validate_path_bases(c.get("path_bases"), root))
    errors.extend(_validate_goal_weights(c.get("goal_weights")))
    errors.extend(_validate_evidence(c.get("min_overview_evidence")))
    return errors


def _cfg(config: Dict[str, Any], root: Optional[Path] = None) -> Dict[str, Any]:
    """四層深合併：_DEFAULT < config.json overview_hub < 公司層 overview-hub.json < 專案層 overview-hub.json。

    root＝公司根時第四層跳過（同一檔不併兩次）。回傳必帶 `_errors`（驗證錯誤清單，非空時 on_edit deny）
    與 `_layer`（root／org／project_mapped／project_unmapped／none）。
    """
    errors: List[str] = []
    section = config.get("overview_hub")
    if section is None:
        section = {}
    elif not isinstance(section, dict):
        errors.append(f"config.json 的 overview_hub 段必須是物件，現在是 {type(section).__name__}")
        section = {}
    c = _deep_merge(_DEFAULT, section)
    org = _org_root()
    if org is not None:
        over, errs = _read_override(org / HUB_REL, "公司層")
        c, errors = _deep_merge(c, over), errors + errs
    if root is not None and not (org is not None and _same_dir(root, org)):
        over, errs = _read_override(root / HUB_REL, "專案層")
        c, errors = _deep_merge(c, over), errors + errs
    try:
        errors += _validate_cfg(c, root)
    except Exception as e:   # 驗證器自己炸也不能 fail-open：仍擋，但標成內部錯誤、traceback 進 atom-debug log
        _atom_debug_error("overview_hub:validate", e)
        errors.append(f"設定驗證內部錯誤（不是設定寫錯，是驗證器 bug，traceback 在 atom-debug log）：{type(e).__name__}: {e}")
    for e in errors:
        _warn_once(f"error:{root}:{e}", f"設定錯誤（{root or '根層'}）：{e}")
    c["_errors"] = errors
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
    """路徑 → (專案根, 命中的表列)；找不到表或沒命中回 None。stop_at：往上找表到這層就停（見 find_map）。"""
    found = find_map(path, stop_at)
    if not found:
        return None
    root, map_path = found
    try:
        rows = parse_map(map_path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    row = match_row(path, root, rows)
    return (root, row) if row else None


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


def _root_key(root: Path) -> str:
    return str(root).replace(chr(92), "/").lower()


def _key(root: Path, row: Dict[str, Any]) -> str:
    return f"{_root_key(root)}|{row['part_short']}"


def _unmapped_key(root: Path, path: str) -> str:
    return f"{_root_key(root)}|(unmapped){top_dir(path, root)}"


def _rel_to_root(path: str, root: Path) -> Optional[str]:
    p, r = path.replace("\\", "/").lower(), _root_key(root).rstrip("/")
    return p[len(r) + 1:] if p.startswith(r + "/") else None


def _is_readonly(path: str, root: Path, cfg: Dict[str, Any]) -> Optional[str]:
    """readonly_paths（相對專案根的 glob）命中 → 回命中的樣式；不命中回 None。`**/` 也配零層。"""
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


def _inject(state: Dict[str, Any], session_id: str, root: Path, row: Dict[str, Any],
            hit_path: str, via: str, transcript_path: str, cfg: Dict[str, Any]) -> str:
    card_paths: List[Path] = []
    if row["status"] in ("有", "部分", "索引"):
        # 根層自己的表（~/.claude/.claude/overview-map.md）卡片在 ~/.claude/memory，不在 ~/.claude/.claude/memory
        mem_dir = CLAUDE_DIR / "memory" if cfg.get("_layer") == "root" else None
        card_paths = [cp for cp in (resolve_card(root, c, mem_dir) for c in row["cards"]) if cp]
    card_path = card_paths[0] if card_paths else None
    template = cfg.get("locate_template") if isinstance(cfg.get("locate_template"), list) else None
    extra = (cfg.get("locate_extra") or {}).get(row["part_short"]) if isinstance(cfg.get("locate_extra"), dict) else None
    intent = _intent_of(state)
    gw = (cfg.get("goal_weights") or {}).get(intent) or {}
    text, used = build_injection_ex(row, card_paths, hit_path, int(cfg["max_card_chars"]), template, extra,
                                    list(gw.get("slices") or []), str(gw.get("lens") or ""), str(gw.get("ask_first") or ""))
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
        "locate_template": template or [],
    }
    _log("inject", session_id, part=row["part_short"], status=row["status"], via=via, path=hit_path,
         card=str(card_path) if card_path else None, chars=len(text), intent=intent, slices=used, layer=cfg.get("_layer"))
    return text


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
    for rec in hub.values():
        if "reads_after" in rec and p not in rec["reads_after"]:
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
    root = _project_root_of(p)
    if root is None:
        return
    rec = state.setdefault("overview_hub", {}).setdefault(_unmapped_key(root, p), {"part_files_read": [], "edits": 0})
    if p not in rec["part_files_read"]:
        rec["part_files_read"].append(p)


def on_read(state: Dict[str, Any], session_id: str, tool_name: str, tool_input: Dict[str, Any],
            cwd: str, transcript_path: str, config: Dict[str, Any]) -> Optional[str]:
    """PostToolUse（Read／Bash）：第一次讀到某部位 → 回注入文字；已注入 → 記 reads_after／part_files_read。"""
    cfg = _cfg(config)
    if not cfg["enabled"]:
        return None
    for p in read_paths_from_tool(tool_name, tool_input, cwd):
        hit = _lookup(p)
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
    for m in re.finditer(r"[A-Za-z]:[\\/][^\s`'\"<>|]+", prompt):
        hit = _lookup(m.group(0))
        if not hit:
            continue
        root, row = hit
        if _key(root, row) not in (state.get("overview_hub") or {}):
            cfg = _cfg(config, root)
            if not cfg["enabled"]:
                return None
            return _inject(state, session_id, root, row, m.group(0), "prompt", transcript_path, cfg)
    return None


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
    if found and any(fk == _path_key(found[0] / rel) for rel in own_rels):
        return (True, found[0])
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


def _unmapped_edit(state: Dict[str, Any], session_id: str, root: Path, file_path: str,
                   cfg: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], bool]:
    """沒有部位表的專案、或表上沒列的檔：只要求本 session 讀過同頂層目錄 ≥N 個檔。"""
    key = _unmapped_key(root, file_path)
    top = top_dir(file_path, root)
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
    hit = _lookup(file_path)
    if hit:
        root, row = hit
    else:
        root, row = _project_root_of(file_path), None
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
    if rec is None:
        text = _inject(state, session_id, root, row, file_path, "edit", transcript_path, cfg)
        msg = (f"[Guardian:OverviewHub] 要改【{row['part_short']}】部位的檔但本 session 還沒看過這個部位的導讀卡；"
               f"卡片現在才注入（下面）。先讀完、讀過部位檔、在回覆交出定位三行，再改。\n{text}")
        _log("edit_before_inject", session_id, part=row["part_short"], path=file_path, deny_reason="not_injected",
             intent=_intent_of(state), layer=cfg.get("_layer"))
        return (msg, msg, True)
    rec["edits"] = int(rec.get("edits", 0)) + 1
    reads = rec.get("reads_after", [])
    dirs = sorted({top_dir(p, root) for p in reads})
    part_files = rec.get("part_files_read", [])
    depends_files = rec.get("depends_files_read", [])
    ev = cfg["min_overview_evidence"]
    missing: List[str] = []
    deny_reason: Optional[str] = None
    warn: Optional[str] = None
    if transcript_size(transcript_path) <= 0:
        # D4：讀不到 transcript 就驗不了定位三行；環境異常也擋（fail-closed）
        deny_reason = "transcript_missing"
        missing.append(f"讀不到 transcript（{transcript_path or '路徑為空'}），環境異常，閘無法驗定位三行；"
                       f"請確認 hook 收到的 transcript_path 存在且非空")
    if len(part_files) < int(ev["part_files"]):
        missing.append(f"注入導讀卡後還沒讀過這個部位的檔（要 ≥{ev['part_files']} 個，目前 {len(part_files)} 個；"
                       f"表外檔讀了 {len(reads) - len(part_files)} 個不算）")
    if len(depends_files) < int(ev["depends_files"]):
        missing.append(f"還沒讀過卡片指到的檔（要 ≥{ev['depends_files']} 個，目前 {len(depends_files)} 個）")
    if deny_reason is None and not rec.get("located"):
        ch = locate_channel(transcript_path, int(rec.get("transcript_offset", 0)), row["part_short"], rec.get("locate_template"))
        if ch is not None:
            vals = locate_values(assistant_text_after(transcript_path, int(rec.get("transcript_offset", 0)), ch),
                                 row["part_short"], rec.get("locate_template")) or {}
            bad_layer = _layer_mismatch(row, vals)
            if bad_layer:
                missing.append(bad_layer)
                deny_reason = "wrong_layer"
            else:
                rec["located"] = True
                rec["located_via"] = ch
                rec["located_quality"] = locate_quality(
                    assistant_text_after(transcript_path, int(rec.get("transcript_offset", 0)), ch),
                    row["part_short"], _card_texts(rec), rec.get("locate_template"))
                if ch == "thinking":
                    warn = (f"[Guardian:OverviewHub] 【{row['part_short']}】的定位三行只在 thinking 裡，模型下回合與人都看不到；"
                            f"這次放行，請改放回覆文字或下一個工具呼叫的參數（Bash 開頭的註解）。")
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
        return (warn, None, True)
    msg = (f"[Guardian:OverviewHub] 改【{row['part_short']}】部位的檔（{file_path}）前的證據不足，一律擋：\n"
           + "\n".join(f"- {m}" for m in missing))
    return (msg, msg, True)
