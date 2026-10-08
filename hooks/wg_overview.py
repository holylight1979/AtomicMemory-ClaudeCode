"""wg_overview — OverviewHub 的 state 層：三個 hook 各呼叫一個函式。

做什麼：第一次碰到某部位（Read／Bash 讀檔、提示詞提到路徑、或直接 Edit）就整張注入該部位導讀卡，
一個 session 一個部位只注入一次；之後記「注入後讀了幾個檔、跨幾個頂層目錄」；Edit 前查 AI 有沒有交
定位三行。設定四層深合併（_cfg）、設定錯誤時 Edit 一律擋。每個事件各落一行 jsonl 到 workflow/_overview-hub.log 當量測資料。

state["overview_hub"] = {
  "<root>|<part>": {"injected_turn", "injected_at", "transcript_offset", "reads_after": [...], "located": bool, "edits": n}
}
"""

from __future__ import annotations

import codecs
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import CLAUDE_DIR, _deep_merge, _layer_kind_for_root, org_memory_root

sys.path.insert(0, str(CLAUDE_DIR / "lib"))
from overview_hub import (  # noqa: E402
    build_injection, find_map, locate_channel, match_row,
    parse_map, read_paths_from_tool, resolve_card, top_dir, transcript_size,
)

LOG_PATH = CLAUDE_DIR / "workflow" / "_overview-hub.log"   # _*.log 不進版控
HUB_REL = Path(".claude") / "overview-hub.json"

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
    "goal_weights": {},
}
_KNOWN_KEYS = frozenset(_DEFAULT)
_RETIRED_KEYS = ("dry_run", "deny_parts")          # 退役：閘一律擋；出現只警告一次，不報錯
_EOL_POLICIES = ("lf", "crlf", "per-file-head")
_LIST_OF_STR_KEYS = ("vcs_roots", "readonly_paths", "root_cause_triggers", "locate_template", "source_encodings")
_DICT_KEYS = ("locate_extra", "min_overview_evidence", "goal_weights")
_ENCODING_KEYS = ("commit_encoding", "PYTHONIOENCODING")
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


def _read_override(path: Path, label: str) -> Dict[str, Any]:
    """<層根>/.claude/overview-hub.json；沒檔回 {}；壞檔回 {} 且 stderr 一行（fail-open 必浮訊號）。"""
    try:
        if not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.stderr.write(f"[Guardian:OverviewHub] {label}覆蓋檔讀取失敗（略過此層）：{path}：{e}\n")
        return {}
    if not isinstance(data, dict):
        sys.stderr.write(f"[Guardian:OverviewHub] {label}覆蓋檔頂層不是物件（略過此層）：{path}\n")
        return {}
    return data


def _same_dir(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except (OSError, ValueError):
        return False


def _is_list_of_str(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _encoding_ok(name: Any) -> bool:
    if not isinstance(name, str) or not name:
        return False
    try:
        codecs.lookup(name)
        return True
    except LookupError:
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


def _validate_cfg(c: Dict[str, Any], root: Optional[Path]) -> List[str]:
    """合併後設定的錯誤清單（空＝通過）。未知鍵報錯；退役鍵只警告一次；底線開頭的鍵（_doc、_errors）不檢查。"""
    errors: List[str] = []
    for key in sorted(c):
        if key.startswith("_") or key in _KNOWN_KEYS:
            continue
        if key in _RETIRED_KEYS:
            _warn_once(f"retired:{key}", f"設定鍵「{key}」已退役（閘一律擋），請從 overview-hub.json／config.json 移除")
            continue
        errors.append(f"未知的設定鍵「{key}」")
    if not isinstance(c.get("enabled"), bool):
        errors.append("enabled 必須是 true／false")
    if not isinstance(c.get("max_card_chars"), int) or isinstance(c.get("max_card_chars"), bool) or c["max_card_chars"] <= 0:
        errors.append("max_card_chars 必須是正整數")
    if not isinstance(c.get("candidate_top_n"), int) or isinstance(c.get("candidate_top_n"), bool) or c["candidate_top_n"] < 0:
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
    return errors


def _cfg(config: Dict[str, Any], root: Optional[Path] = None) -> Dict[str, Any]:
    """四層深合併：_DEFAULT < config.json overview_hub < 公司層 overview-hub.json < 專案層 overview-hub.json。

    root＝公司根時第四層跳過（同一檔不併兩次）。回傳必帶 `_errors`（驗證錯誤清單，非空時 on_edit deny）
    與 `_layer`（root／org／project_mapped／project_unmapped／none）。
    """
    c = _deep_merge(_DEFAULT, config.get("overview_hub") or {})
    org = _org_root()
    if org is not None:
        c = _deep_merge(c, _read_override(org / HUB_REL, "公司層"))
    if root is not None and not (org is not None and _same_dir(root, org)):
        c = _deep_merge(c, _read_override(root / HUB_REL, "專案層"))
    errors = _validate_cfg(c, root)
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


def _key(root: Path, row: Dict[str, Any]) -> str:
    return f"{str(root).replace(chr(92), '/').lower()}|{row['part_short']}"


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
    text = build_injection(row, card_paths, hit_path, int(cfg["max_card_chars"]), template, extra)
    hub = state.setdefault("overview_hub", {})
    hub[_key(root, row)] = {
        "injected_turn": int(state.get("turn_seq", 0)),
        "injected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "transcript_offset": transcript_size(transcript_path),
        "reads_after": [],
        "located": False,
        "edits": 0,
        "locate_template": template or [],
    }
    _log("inject", session_id, part=row["part_short"], status=row["status"], via=via,
         path=hit_path, card=str(card_path) if card_path else None, chars=len(text))
    return text


def on_read(state: Dict[str, Any], session_id: str, tool_name: str, tool_input: Dict[str, Any],
            cwd: str, transcript_path: str, config: Dict[str, Any]) -> Optional[str]:
    """PostToolUse（Read／Bash）：第一次讀到某部位 → 回注入文字；已注入 → 記 reads_after。"""
    cfg = _cfg(config)
    if not cfg["enabled"]:
        return None
    for p in read_paths_from_tool(tool_name, tool_input, cwd):
        # 注入後讀的每個檔都記到所有已注入的部位（跨部位探索正是綜觀，不能只記命中的那一個）
        for rec in (state.get("overview_hub") or {}).values():
            if p not in rec["reads_after"]:
                rec["reads_after"].append(p)
        hit = _lookup(p)
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
              config: Dict[str, Any]) -> Optional[str]:
    """UserPromptSubmit：提示詞裡出現的絕對路徑命中某部位且未注入 → 注入。"""
    import re
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


def on_edit(state: Dict[str, Any], session_id: str, file_path: str, transcript_path: str,
            config: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], bool]:
    """PreToolUse（Edit／Write）：回 (警告文字, deny 理由, state 有沒有變)。dry_run 時 deny 恆 None。

    deny 理由帶整張卡（模型只看得到 permissionDecisionReason）；transcript 讀不到時不擋但要提醒。
    """
    cfg = _cfg(config)
    if not cfg["enabled"] or not file_path:
        return (None, None, False)
    hit = _lookup(file_path)
    if not hit:
        return (None, None, False)
    root, row = hit
    cfg = _cfg(config, root)
    if not cfg["enabled"]:
        return (None, None, False)
    if cfg["_errors"]:
        msg = (f"[Guardian:OverviewHub] 改【{row['part_short']}】部位的檔（{file_path}）前，這一層的 overview-hub.json 設定有錯，"
               f"閘無法判定，先修設定：" + "；".join(cfg["_errors"]))
        _log("edit_cfg_error", session_id, part=row["part_short"], path=file_path, errors=cfg["_errors"])
        return (msg, msg, False)
    key = _key(root, row)
    rec = (state.get("overview_hub") or {}).get(key)
    # 專案可只對某幾個部位開擋（deny_parts），其他部位維持 dry_run
    dry = bool(cfg.get("dry_run", False)) and row["part_short"] not in (cfg.get("deny_parts") or [])
    cfg = dict(cfg, dry_run=dry)
    if rec is None:
        text = _inject(state, session_id, root, row, file_path, "edit", transcript_path, cfg)
        msg = (f"[Guardian:OverviewHub] 要改【{row['part_short']}】部位的檔但本 session 還沒看過這個部位的導讀卡——"
               f"卡片現在才注入（下面）。先讀完、在回覆交出定位三行，再改。\n{text}")
        _log("edit_before_inject", session_id, part=row["part_short"], path=file_path)
        return (msg, None if cfg["dry_run"] else msg, True)
    rec["edits"] = int(rec.get("edits", 0)) + 1
    reads = rec.get("reads_after", [])
    dirs = sorted({top_dir(p, root) for p in reads})
    verifiable = transcript_size(transcript_path) > 0   # transcript 讀得到就可驗；讀得到但沒內容＝沒交
    if not rec.get("located") and verifiable:
        ch = locate_channel(transcript_path, int(rec.get("transcript_offset", 0)),
                            row["part_short"], rec.get("locate_template"))
        rec["located"] = ch is not None
        rec["located_via"] = ch
    _log("edit", session_id, part=row["part_short"], path=file_path, located=rec["located"],
         located_via=rec.get("located_via"), verifiable=verifiable, reads_after_inject=len(reads),
         dirs_after_inject=len(dirs), edits=rec["edits"], dry_run=cfg["dry_run"])
    if rec["located"]:
        return (None, None, True)
    if not verifiable:
        return (f"[Guardian:OverviewHub] 改【{row['part_short']}】部位的檔（{file_path}）：讀不到 transcript，"
                f"查不了有沒有交定位三行，這次放行；請確認回覆裡有寫。", None, True)
    msg = (f"[Guardian:OverviewHub] 改【{row['part_short']}】部位的檔（{file_path}）前還沒交出定位三行"
           f"（注入導讀卡後讀了 {len(reads)} 個檔、跨 {len(dirs)} 個目錄）。"
           f"請先在回覆寫：定位｜部位：…／定位｜根因層：…／定位｜前例：…"
           + ("（目前 dry-run，只提醒不擋）" if cfg["dry_run"] else ""))
    return (msg, None if cfg["dry_run"] else msg, True)
