"""hub_config.py：OverviewHub 設定（overview-hub.json 系）的四層合併與驗證，全系統只此一份。

做什麼：根層預設 HUB_DEFAULTS < workflow/config.json 的 overview_hub 段 < <公司根>/.claude/overview-hub.json
  < <專案根>/.claude/overview-hub.json，巢狀 dict 深合併、list 整個取覆蓋方；合併後驗證（未知鍵、型別、編碼、路徑基準）。
  各守門（hooks/wg_overview._cfg）、壞味道候選池 CLI（tools/project-smells.py）都走 merge_hub_cfg，
  兩邊看到的設定一致。
  純函式：不讀 config.json、不判公司根（呼叫端傳入），不碰 state；警告只回清單，由呼叫端決定怎麼浮出。
怎麼跑：hooks 以 sys.path 的 lib/ 頂層匯入；tools 以檔案相對路徑把 lib/ 放進 sys.path 後匯入。
  verify 在 hooks/verify/verify_overview_hub.py、tools/verify/verify_project_smells.py。
"""
from __future__ import annotations

import codecs
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


HUB_REL = Path(".claude") / "overview-hub.json"

# 十個 intent 鍵固定（介面凍結，與 wg_atoms.INTENT_PATTERNS＋general 對拍；verify_intent_goal_weights 驗）
INTENT_KEYS = ("debug", "feature", "refactor", "perf", "new_project", "build", "design", "recall", "handoff", "general")

# 變量預設（預計畫附錄 D）
HUB_DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "max_card_chars": 6000,
    "path_bases": [],
    "vcs_roots": [],
    "commit_encoding": "utf-8",
    "source_encodings": ["utf-8"],
    "eol_policy": "per-file-head",
    "PYTHONIOENCODING": "utf-8",
    "readonly_paths": [],
    "candidate_top_n": 5,
    # 壞味道報告：smells_report（相對專案根或絕對；json／jsonl／md 表）；報告 mtime 超過 smells_max_age_days 算過期
    "smells_report": "",
    "smells_max_age_days": 7,
    # 壞味道候選池 CLI（tools/project-smells.py）：沒報告就跑 smells_cmd（陣列或字串），逾時 smells_timeout_s 秒；
    # 報告的分類名不在七類內時用 smells_category_map 映射
    "smells_cmd": None,
    "smells_timeout_s": 20,
    "smells_category_map": {},
    # 權威地圖（A3.5）：{"<檔名樣式（fnmatch，對檔名或相對專案根路徑）>": "<地圖路徑（相對專案根或絕對）>"}；
    # 讀到文件／計畫檔命中樣式且非空 → 一 session 注入一次該地圖
    "authority_map": {},
    # verify_chains[部位]={runtime_gate,pre,run,collect,cleanup}：只驗形狀（dict），目前沒有程式讀；留著讓既有 overview-hub.json 不報未知鍵
    "verify_chains": {},
    # 等值與熱路徑收尾閘（hooks/handlers/stop.py Equivalence Gate）：enabled 整道閘的開關
    "equivalence": {"enabled": True},
    # svn 測試路徑閘（hooks/handlers/pre_tool_use.check_svn_test_block）：svn commit 的路徑含測試檔就擋；預設關，要的專案在
    # 專案層 overview-hub.json 開
    "svn_test_block": {"enabled": False},
}
KNOWN_KEYS = frozenset(HUB_DEFAULTS)
# 退役：沒有程式讀；出現只警告，不報錯（dry_run／deny_parts 明寫也不放行）
RETIRED_KEYS = ("dry_run", "deny_parts", "card_injection", "locate_template", "locate_extra", "min_overview_evidence",
                "root_cause_triggers", "idle_triggers", "post_compact_chars", "goal_weights", "min_map", "need_goal")
_EOL_POLICIES = ("lf", "crlf", "per-file-head")
_LIST_OF_STR_KEYS = ("vcs_roots", "readonly_paths", "source_encodings")
_DICT_KEYS = ("verify_chains", "authority_map", "smells_category_map")
_NONNEG_INT_KEYS = ("candidate_top_n", "smells_max_age_days")
_ENCODING_KEYS = ("commit_encoding", "PYTHONIOENCODING")


def deep_merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    """over 疊在 base 上：兩邊都是 dict 才往下併，其餘（含 list）整個取 over；不改 base。"""
    out = dict(base)
    for key, value in over.items():
        both_dict = isinstance(value, dict) and isinstance(out.get(key), dict)
        out[key] = deep_merge(out[key], value) if both_dict else value
    return out


def read_override(path: Path, label: str) -> Tuple[Dict[str, Any], List[str]]:
    """<層根>/.claude/overview-hub.json → (資料, 錯誤)。沒檔 ({}, [])；讀不到／壞 JSON／頂層不是物件 → ({}, [一條錯誤])，
    呼叫端把錯誤併進 `_errors`（設定壞了整層不可信，要擋，不是略過）。"""
    try:
        if not path.is_file():
            return {}, []
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {}, [f"{label}覆蓋檔讀取失敗：{path}：{e}"]
    if not isinstance(data, dict):
        return {}, [f"{label}覆蓋檔頂層不是物件：{path}"]
    return data, []


def same_dir(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except (OSError, ValueError):
        return False


def _is_list_of_str(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _is_nonneg_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def encoding_ok(name: Any) -> bool:
    if not isinstance(name, str) or not name:
        return False
    try:
        codecs.lookup(name)
        return True
    except (LookupError, ValueError, TypeError):   # 查不到、含 NUL（ValueError）、怪型別都算壞編碼，不往外拋
        return False


def validate_path_bases(bases: Any, root: Optional[Path]) -> List[str]:
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


def validate_smells(c: Dict[str, Any]) -> List[str]:
    """project-smells 的三個鍵：smells_cmd 是 null／字串／字串陣列；smells_timeout_s 是正數；category_map 的鍵值都是字串。"""
    errors: List[str] = []
    cmd = c.get("smells_cmd")
    if cmd is not None and not isinstance(cmd, str) and not _is_list_of_str(cmd):
        errors.append("smells_cmd 必須是 null、字串或字串陣列")
    t = c.get("smells_timeout_s")
    if isinstance(t, bool) or not isinstance(t, (int, float)) or t <= 0:
        errors.append("smells_timeout_s 必須是正數（秒）")
    cm = c.get("smells_category_map")
    if isinstance(cm, dict) and not all(isinstance(k, str) and isinstance(v, str) for k, v in cm.items()):
        errors.append("smells_category_map 的鍵與值都必須是字串（報告分類名 → 七類之一）")
    return errors


def validate_switch(name: str, sec: Any) -> List[str]:
    """只有 enabled 一鍵的開關段（equivalence、svn_test_block）：是物件、沒有別的鍵、enabled 是 true／false。"""
    if not isinstance(sec, dict):
        return [f"{name} 必須是物件"]
    errors = [f"{name} 有未知鍵「{k}」" for k in sorted(sec) if k != "enabled" and not k.startswith("_")]
    if not isinstance(sec.get("enabled"), bool):
        errors.append(f"{name}.enabled 必須是 true／false")
    return errors


def validate_equivalence(eq: Any) -> List[str]:
    """equivalence：只有 enabled 一鍵，是 true／false。"""
    return validate_switch("equivalence", eq)


def validate_hub_cfg(c: Dict[str, Any], root: Optional[Path]) -> Tuple[List[str], List[str]]:
    """合併後設定 → (錯誤清單, 出現的退役鍵)。未知鍵報錯；退役鍵不報錯只回報；底線開頭的鍵（_doc、_errors）不檢查。"""
    errors: List[str] = []
    retired: List[str] = []
    for key in sorted(c):
        if key.startswith("_") or key in KNOWN_KEYS:
            continue
        if key in RETIRED_KEYS:
            retired.append(key)
            continue
        errors.append(f"未知的設定鍵「{key}」")
    if not isinstance(c.get("enabled"), bool):
        errors.append("enabled 必須是 true／false")
    if not isinstance(c.get("max_card_chars"), int) or isinstance(c.get("max_card_chars"), bool) or c["max_card_chars"] <= 0:
        errors.append("max_card_chars 必須是正整數")
    for key in _NONNEG_INT_KEYS:
        if not _is_nonneg_int(c.get(key)):
            errors.append(f"{key} 必須是 0 以上的整數")
    if not isinstance(c.get("smells_report"), str):
        errors.append("smells_report 必須是字串（報告路徑；空字串＝沒有報告）")
    am = c.get("authority_map")
    if isinstance(am, dict) and not all(isinstance(k, str) and isinstance(v, str) and k and v for k, v in am.items()):
        errors.append("authority_map 的鍵與值都必須是非空字串（檔名樣式 → 地圖路徑）")
    for key in _LIST_OF_STR_KEYS:
        if not _is_list_of_str(c.get(key)):
            errors.append(f"{key} 必須是字串陣列")
    for key in _DICT_KEYS:
        if not isinstance(c.get(key), dict):
            errors.append(f"{key} 必須是物件")
    for key in _ENCODING_KEYS:
        if not encoding_ok(c.get(key)):
            errors.append(f"{key}「{c.get(key)}」不是 Python 認得的編碼")
    if _is_list_of_str(c.get("source_encodings")):
        errors.extend(f"source_encodings「{e}」不是 Python 認得的編碼" for e in c["source_encodings"] if not encoding_ok(e))
    if c.get("eol_policy") not in _EOL_POLICIES:
        errors.append(f"eol_policy 必須是 {'／'.join(_EOL_POLICIES)} 之一")
    errors.extend(validate_path_bases(c.get("path_bases"), root))
    errors.extend(validate_smells(c))
    errors.extend(validate_equivalence(c.get("equivalence")))
    errors.extend(validate_switch("svn_test_block", c.get("svn_test_block")))
    return errors, retired


def merge_hub_cfg(config: Dict[str, Any], org_root: Optional[Path], root: Optional[Path],
                  validate: Optional[Callable[[Dict[str, Any], Optional[Path]], Tuple[List[str], List[str]]]] = None,
                  ) -> Dict[str, Any]:
    """四層深合併：HUB_DEFAULTS < config["overview_hub"] < 公司層 overview-hub.json < 專案層 overview-hub.json。

    config＝整份 workflow/config.json（呼叫端讀）；org_root＝公司根或 None（呼叫端判）；root＝公司根時第四層跳過
    （同一檔不併兩次）。回傳必帶 `_errors`（驗證錯誤清單，非空＝設定不可信，呼叫端要擋）與 `_retired`（出現的退役鍵）；
    驗證器自己炸也不 fail-open：錯誤清單加一條「設定驗證內部錯誤」，例外物件放 `_internal_error` 給呼叫端記 log。
    validate 只給測試注入，預設 validate_hub_cfg。"""
    errors: List[str] = []
    section = (config or {}).get("overview_hub")
    if section is None:
        section = {}
    elif not isinstance(section, dict):
        errors.append(f"config.json 的 overview_hub 段必須是物件，現在是 {type(section).__name__}")
        section = {}
    c = deep_merge(HUB_DEFAULTS, section)
    if org_root is not None:
        over, errs = read_override(org_root / HUB_REL, "公司層")
        c, errors = deep_merge(c, over), errors + errs
    if root is not None and not (org_root is not None and same_dir(root, org_root)):
        over, errs = read_override(root / HUB_REL, "專案層")
        c, errors = deep_merge(c, over), errors + errs
    retired: List[str] = []
    internal: Optional[Exception] = None
    try:
        errs, retired = (validate or validate_hub_cfg)(c, root)
        errors += errs
    except Exception as e:  # noqa: BLE001  驗證器 bug 也要擋，不放行
        internal = e
        errors.append(f"設定驗證內部錯誤（不是設定寫錯，是驗證器 bug，traceback 在 atom-debug log）：{type(e).__name__}: {e}")
    c["_errors"] = errors
    c["_retired"] = retired
    c["_internal_error"] = internal
    return c
