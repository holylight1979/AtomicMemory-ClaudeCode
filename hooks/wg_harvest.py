"""wg_harvest.py — 階段完工知識收割（KnowledgeHarvest）與追蹤項帳本的純函式。

誰用：
  - handlers/stop.py：harvest_gate_reason（該不該擋、擋什麼話）、pending_gate_reason、
    vcs_sync_lock_active（SyncReminder 遇 worker 活鎖跳過該 root）；tracking_entries／append_tracking（退縮閘那一問的「追蹤｜…」行）。
  - handlers/post_tool_use.py（one-writer）：parse_receipt / record_atom_op（atom 工具收據入帳）、
    validate_items（收割回報逐項核對）、append_ledger。

state 分區（全部按 session_id 分區，防共用工作樹的隔壁 session 誤放行）：
  state["atom_ops"][sid]            = [{seq, turn_seq, op, atom, path, index_ok, ok, supersedes, old_path, new_path}]
  state["knowledge_harvest"][sid]   = {turn_seq, items, pending, validated, retired_paths, at, last_valid_harvest_turn, last_valid_op_seq}
  state["harvest_gate_turn"][sid]   = 本 session 已擋過 KnowledgeHarvest 的回合（使用者打字開的回合，stop._user_turn）
  state["harvest_pending_gate_turn"][sid] = 本 session 已擋過 Harvest-Pending 的回合（同上）
state 只讀寫傳入的 dict，write_state 由 handler 做；帳本檔（workflow/tracking、workflow/harvest-ledger）由本模組直接追加。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import _is_under_claude_dir, _now_iso, WORKFLOW_DIR, user_typed_prompts
from wg_evasion import claims_completion, _DISMISS_RE, _COMPLETION_EXCLUDE_RE
from wg_extraction import _is_pid_alive
from wg_lazy_re import lazy_module

_rr = lazy_module("wg_release_rules")   # 「同一個使用者回合」的判法（in_user_turn）；收割帳沒有本回合紀錄時用不到，第一次用到才載

_ATOM_OPS_CAP = 200
_RECEIPT_OPS = ("create", "append", "replace", "retire")
_RECEIPT_LINE_RE = re.compile(r"^\s*receipt:\s*(\{.*\})\s*$")

_HARVEST_SOURCES = (
    "①使用者指正/退回/重申",
    "②重試≥2 次或查了才懂的機制/坑",
    "③外查事實（帶日期）",
    "④我做的取捨/契約/偏好",
    "⑤既有 atom 被證錯或要補（append 或新顆 Supersedes）",
    "⑥本場證實無用/錯誤且無人引用的 atom（atom_retire）",
)

# items 欄位契約（與 harvest.js validateItems 同一份規則；Python 端自驗，不信 Node 端已擋）
_ITEM_SOURCES = ("correction", "mechanism", "external_fact", "decision", "atom_fix", "atom_retire")
_ITEM_ACTIONS = ("created", "appended", "replaced", "superseded", "retired", "skip")
# 萃取路由（與 harvest.js ROUTES 同一份）：皆選填；part_doc 必帶 part；candidate_global 不得帶專案名（先 scrub）
_ITEM_ROUTES = ("part_doc", "global", "org", "local", "shared", "candidate_global")


# ─── config ──────────────────────────────────────────────────────


_DEFAULT_WORKFLOW_DIR = WORKFLOW_DIR

def harvest_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """config.harvest 區段；缺區段＝整個機制關（其他閘的測試用空 config 驅動 handle_stop，不能被連帶觸發）。"""
    cfg = (config or {}).get("harvest")
    if not isinstance(cfg, dict) or not cfg.get("enabled", False):
        return {}
    return cfg


# ─── state 分區存取 ───────────────────────────────────────────────


def section(state: Dict[str, Any], sid: str) -> Dict[str, Any]:
    kh = state.get("knowledge_harvest")
    if not isinstance(kh, dict):
        return {}
    sec = kh.get(sid)
    return sec if isinstance(sec, dict) else {}


def validated_this_turn(state: Dict[str, Any], sid: str, turn_seq: int) -> bool:
    """本回合（規則 TURN_SINCE_USER_PROMPT：使用者打字開的回合起，同伴訊息、背景通知不另開回合）收割回報已核過。"""
    sec = section(state, sid)
    return bool(turn_seq) and _rr.in_user_turn(sec.get("turn_seq"), state, turn_seq) and bool(sec.get("validated"))


def reported_this_turn(state: Dict[str, Any], sid: str, turn_seq: int) -> bool:
    """本回合（同上）已經回報過收割。"""
    return bool(turn_seq) and _rr.in_user_turn(section(state, sid).get("turn_seq"), state, turn_seq)


def atom_ops(state: Dict[str, Any], sid: str) -> List[Dict[str, Any]]:
    ops = state.get("atom_ops")
    if not isinstance(ops, dict):
        return []
    lst = ops.get(sid)
    return lst if isinstance(lst, list) else []


# ─── receipt ─────────────────────────────────────────────────────


def _response_text(tool_response: Any) -> str:
    """MCP 工具結果 → 純文字。hook 給的 tool_response 形狀不固定（{content:[{type,text}]} /
    content 直接是 list / 純字串），全部收。"""
    if tool_response is None:
        return ""
    if isinstance(tool_response, str):
        return tool_response
    if isinstance(tool_response, list):
        return "\n".join(_response_text(x) for x in tool_response)
    if isinstance(tool_response, dict):
        if isinstance(tool_response.get("text"), str) and tool_response.get("type", "text") == "text":
            return tool_response["text"]
        if "content" in tool_response:
            return _response_text(tool_response["content"])
        if "result" in tool_response:
            return _response_text(tool_response["result"])
        try:
            return json.dumps(tool_response, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(tool_response)
    return str(tool_response)


def parse_receipt(tool_response: Any) -> Optional[Dict[str, Any]]:
    """結果文字最後一行 `receipt: {json}` → dict；沒有（呼叫失敗）回 None。
    欄位：op(create|append|replace|retire)、atom、path、index_ok、ok、supersedes、old_path、new_path。"""
    text = _response_text(tool_response)
    if "receipt:" not in text:
        return None
    for line in reversed(text.splitlines()):
        m = _RECEIPT_LINE_RE.match(line)
        if not m:
            continue
        try:
            rec = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(rec, dict) or rec.get("op") not in _RECEIPT_OPS:
            return None
        return rec
    return None


def is_error_response(tool_response: Any) -> bool:
    """MCP 工具結果是否為錯誤：sendToolResult(…, isError=true) 的旗標（hook 可能轉成 is_error），
    沒旗標時看文字（harvest.js 拒收訊息含「拒收」；通用錯誤含 error）。錯誤結果不得當成回報。"""
    if isinstance(tool_response, dict):
        if tool_response.get("isError") is True or tool_response.get("is_error") is True:
            return True
    text = _response_text(tool_response)
    return "拒收" in text or "error" in text.lower()


def record_atom_op(state: Dict[str, Any], sid: str, turn_seq: int, receipt: Dict[str, Any]) -> Dict[str, Any]:
    """receipt 入帳 state["atom_ops"][sid]（含 ok:false 的失敗收據，供 ledger 與重試追蹤）；保留最近 200 筆。
    seq 單調遞增：收割核對只看「上次 validated 收割之後」的收據，用 seq 切比 turn_seq 準（同 turn 內可有多次收割）。"""
    ops_all = state.setdefault("atom_ops", {})
    if not isinstance(ops_all, dict):
        ops_all = state["atom_ops"] = {}
    lst = ops_all.setdefault(sid, [])
    seq_all = state.setdefault("atom_ops_seq", {})
    seq = int(seq_all.get(sid, 0)) + 1
    seq_all[sid] = seq
    entry = {
        "seq": seq,
        "turn_seq": int(turn_seq or 0),
        "op": receipt.get("op"),
        "atom": receipt.get("atom", ""),
        "path": receipt.get("path", ""),
        "index_ok": bool(receipt.get("index_ok", False)),
        "ok": receipt.get("ok", True) is not False,
        "supersedes": [s for s in (receipt.get("supersedes") or []) if isinstance(s, str)],
        "old_path": receipt.get("old_path", ""),
        "new_path": receipt.get("new_path", ""),
        "at": _now_iso(),
    }
    lst.append(entry)
    if len(lst) > _ATOM_OPS_CAP:
        ops_all[sid] = lst[-_ATOM_OPS_CAP:]
    return entry


# ─── 收割回報核對 ─────────────────────────────────────────────────


def _norm_path(p: Any) -> str:
    return str(p or "").replace("\\", "/").strip().rstrip("/").lower()


def receipts_since_last_validated(state: Dict[str, Any], sid: str) -> List[Dict[str, Any]]:
    """本 session 自上次 validated 收割以來的成功收據（ok:false 的失敗收據不算證據）。"""
    last_seq = int(section(state, sid).get("last_valid_op_seq", 0) or 0)
    return [
        r for r in atom_ops(state, sid)
        if int(r.get("seq", 0)) > last_seq and r.get("ok", True) is not False
    ]


def _item_fields_bad(item: Dict[str, Any]) -> Optional[str]:
    """必要欄位檢查；合格回 None，否則回原因。先於 receipt 核對——欄位不合格的 item 連核對都不做。"""
    action = str(item.get("action", "") or "")
    atom = str(item.get("atom", "") or "").strip()
    tag = atom or "?"
    if action not in _ITEM_ACTIONS:
        return f"{tag}: 欄位不合格——action={action!r} 不在 {'|'.join(_ITEM_ACTIONS)}"
    if str(item.get("source", "") or "") not in _ITEM_SOURCES:
        return f"{tag}: 欄位不合格——source={item.get('source')!r} 不在 {'|'.join(_ITEM_SOURCES)}"
    if not str(item.get("summary", "") or "").strip():
        return f"{tag}: 欄位不合格——summary 必填（與 harvest.js 同一套必填清單）"
    route_bad = _item_route_bad(item, tag)
    if route_bad:
        return route_bad
    if action == "skip":
        if not str(item.get("reason", "") or "").strip():
            return f"{tag}: 欄位不合格——action=skip 必填 reason"
        return None
    if not atom or not str(item.get("path", "") or "").strip():
        return f"{tag}: 欄位不合格——action={action} 必填 atom 與 path"
    return None


def _project_terms_in(text: str) -> List[str]:
    """文字裡的本機已登記專案名／專案根底下絕對路徑（lib/realm_gate 單源；import 失敗＝不擋但浮訊號）。"""
    try:
        from realm_gate import scan_known_projects  # wg_core 已把 ~/.claude/lib 放進 sys.path
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:Harvest] realm_gate unavailable, route scan skipped: {e}", file=sys.stderr)
        return []
    return [h["term"] for h in scan_known_projects({"knowledge": [text]})]


def _item_route_bad(item: Dict[str, Any], tag: str) -> Optional[str]:
    """route 欄（選填）：enum 內；part_doc 必帶 part；candidate_global／global 的 summary 不得帶專案名（先 scrub）。"""
    route = item.get("route")
    if route is None:
        return None
    route = str(route or "")
    if route not in _ITEM_ROUTES:
        return f"{tag}: 欄位不合格；route={route!r} 不在 {'|'.join(_ITEM_ROUTES)}"
    if route == "part_doc" and not str(item.get("part", "") or "").strip():
        return f"{tag}: 欄位不合格；route=part_doc 必填 part（部位名；有部位的知識寫進該部位病灶文件＋卡一行指標）"
    if route in ("candidate_global", "global"):
        terms = _project_terms_in(str(item.get("summary", "") or ""))
        if terms:
            return (f"{tag}: route={route} 但 summary 含專案名／路徑『{'、'.join(terms[:3])}』；"
                    "先 scrub（atom_io_cli action=scrub）去專案細節再報")
    return None


def _item_satisfied(item: Dict[str, Any], receipts: List[Dict[str, Any]]) -> Optional[str]:
    """單一 item 對 receipts 核對；通過回 None，不過回原因（白話）。欄位已由 _item_fields_bad 把關。"""
    action = str(item.get("action", "") or "")
    atom = str(item.get("atom", "") or "")
    path = _norm_path(item.get("path"))
    if action == "skip":
        return None
    op_by_action = {"created": "create", "appended": "append", "replaced": "replace"}
    if action in op_by_action:
        op = op_by_action[action]
        same = [r for r in receipts if r.get("op") == op and _norm_path(r.get("path")) == path]
        if not same:
            return f"{atom}: 無 {op} receipt（path={item.get('path')}）"
        if not any(r.get("index_ok") for r in same):
            return f"{atom}: {op} receipt index_ok=false（索引未更新）"
        return None
    if action == "superseded":
        hits = [
            r for r in receipts
            if r.get("op") in ("create", "replace") and atom in (r.get("supersedes") or [])
        ]
        if not hits:
            return f"{atom}: 無 create/replace receipt 的 supersedes 含它"
        if not any(r.get("index_ok") for r in hits):
            return f"{atom}: 取代它的 receipt index_ok=false（索引未更新）"
        return None
    if action == "retired":
        hits = [r for r in receipts if r.get("op") == "retire" and _norm_path(r.get("old_path")) == path]
        if not hits:
            return f"{atom}: 無 retire receipt（old_path={item.get('path')}）"
        return None
    return f"{atom}: 未知 action={action!r}"


def validate_items(items: Any, receipts: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """items（list 或 JSON 字串）先驗必要欄位、再逐項對 receipt → (正規化 items, pending 原因列)。
    pending 空＝validated；任一項欄位不合格即整份不 validated。"""
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except (json.JSONDecodeError, ValueError):
            return [], [f"items 不是合法 JSON：{items[:80]}"]
    if items is None:
        items = []
    if not isinstance(items, list):
        return [], ["items 必須是 list"]
    norm: List[Dict[str, Any]] = []
    pending: List[str] = []
    for raw in items:
        if not isinstance(raw, dict):
            pending.append(f"item 不是物件：{str(raw)[:60]}")
            continue
        norm.append(raw)
        why = _item_fields_bad(raw) or _item_satisfied(raw, receipts)
        if why:
            pending.append(why)
    return norm, pending


def validated_retired_paths(sec: Dict[str, Any], receipts: List[Dict[str, Any]]) -> List[str]:
    """validated 收割裡 action=retired 且有 ok:true retire receipt 的 old_path（receipt 的實際路徑，
    供 vcs-sync worker 把退役檔的刪除納入 commit）。未 validated 回空：核不過的不得上版控。"""
    if not sec.get("validated"):
        return []
    retired = {_norm_path(it.get("path")) for it in sec.get("items") or [] if it.get("action") == "retired"}
    if not retired:
        return []
    return [
        str(r.get("old_path"))
        for r in receipts
        if r.get("op") == "retire" and r.get("ok", True) is not False and _norm_path(r.get("old_path")) in retired
    ]


def apply_report(
    state: Dict[str, Any], sid: str, turn_seq: int, items: Any, note: str = "",
) -> Dict[str, Any]:
    """收割回報落本 session 分區；validated 才更新冷卻（last_valid_harvest_turn）與收據游標。回該分區。"""
    receipts = receipts_since_last_validated(state, sid)
    norm_items, pending = validate_items(items, receipts)
    retired_paths = validated_retired_paths({"validated": not pending, "items": norm_items}, receipts)
    kh = state.setdefault("knowledge_harvest", {})
    if not isinstance(kh, dict):
        kh = state["knowledge_harvest"] = {}
    prev = kh.get(sid) if isinstance(kh.get(sid), dict) else {}
    sec: Dict[str, Any] = {
        "turn_seq": int(turn_seq or 0),
        "items": norm_items,
        "pending": pending,
        "validated": not pending,
        "retired_paths": retired_paths,
        "note": str(note or "")[:300],
        "at": _now_iso(),
        "last_valid_harvest_turn": prev.get("last_valid_harvest_turn"),
        "last_valid_harvest_uturn": prev.get("last_valid_harvest_uturn"),
        "last_valid_op_seq": int(prev.get("last_valid_op_seq", 0) or 0),
    }
    if not pending:
        sec["last_valid_harvest_turn"] = int(turn_seq or 0)
        if state.get("user_turn_count") is not None:                       # 冷卻以使用者回合數算（規則 TURN_SINCE_USER_PROMPT）
            sec["last_valid_harvest_uturn"] = int(state.get("user_turn_count") or 0)
        ops = atom_ops(state, sid)
        sec["last_valid_op_seq"] = int(ops[-1].get("seq", 0)) if ops else sec["last_valid_op_seq"]
    kh[sid] = sec
    return sec


# ─── AEC 追蹤項帳本（G13：收尾誠實）─────────────────────────────────

_TRACK_PART_RE = re.compile(r"^(?:\[(?P<p1>[^\]]+)\]|(?P<p2>[^｜|：:]{1,20})[｜|])\s*(?P<rest>.+)$")


_TRACK_CLOSE_RE = re.compile(r"^結案\s*[：:]\s*(?P<prefix>.+)$")
TRACK_CLOSE_MIN_CHARS = 8
# 追蹤項行尾的提議欄（G13：記問題也記怎麼解、該誰解）：「…｜建議：<做法>｜該誰解：<誰>」，順序不拘、可只寫一欄；
# 「｜同追蹤項：<已記那筆裡至少 8 字>」＝AI 判斷這件跟帳上那筆是同一件（規則 TRACKING_SAME_ITEM_NOT_REWRITTEN）
_TRACK_FIELD_SPLIT_RE = re.compile(r"\s*[｜|]\s*(建議怎麼解|建議|該誰解|誰解|同追蹤項)\s*[：:]\s*")
_TRACK_FIELD_KEYS = {"建議怎麼解": "proposal", "建議": "proposal", "該誰解": "owner", "誰解": "owner", "同追蹤項": "same_as"}


def _split_track_fields(line: str) -> Tuple[str, Dict[str, str]]:
    """追蹤項一行 → (本文, {proposal, owner, same_as} 有寫的欄)。要在認部位之前切：不然「問題｜建議：…」的問題會被當成部位。"""
    parts = _TRACK_FIELD_SPLIT_RE.split(line)
    fields: Dict[str, str] = {}
    for label, value in zip(parts[1::2], parts[2::2]):
        fields[_TRACK_FIELD_KEYS[label]] = value.strip()
    return parts[0].strip(), {k: v for k, v in fields.items() if v}


def _sha16(raw: str) -> str:
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def tracking_entry_id(entry: Dict[str, Any]) -> str:
    """追蹤項的唯一 id：新寫入的列自帶 id；沒有 id 的舊列用 session_id、turn_seq、at、part、text 算出固定 id。"""
    if entry.get("id"):
        return str(entry["id"])
    return _sha16("|".join(str(entry.get(k, "")) for k in ("session_id", "turn_seq", "at", "part", "text")))


def tracking_entries(session_id: str, turn_seq: int, k_text: Any, at: Optional[str] = None) -> List[Dict[str, Any]]:
    """AEC 的 (k) 追蹤項文字 → 帳本列：一行一筆 {id, session_id, turn_seq, at, part, text, status}（行尾寫了
    「｜建議：…｜該誰解：…｜同追蹤項：…」另帶 proposal／owner／same_as，same_as 由 append_tracking 合併）。
    「無」／空白 → []。行首 `[部位]` 或 `部位｜` 當 part，沒有就空字串。id 含行序，同批同文字的兩筆也不同。
    一般行 status＝open；`[部位] 結案：<原項目開頭>` → status＝closed、text＝前綴（closes 由 append_tracking 對帳本補上）。"""
    text = str(k_text or "").strip()
    if not text or text in ("無", "none", "None", "N/A"):
        return []
    out: List[Dict[str, Any]] = []
    stamp = at or _now_iso()
    for idx, raw in enumerate(text.splitlines()):
        line, fields = _split_track_fields(raw.strip().lstrip("-•*").strip())
        if not line or line in ("無",):
            continue
        part, body = "", line
        m = _TRACK_PART_RE.match(line)
        if m:
            part = (m.group("p1") or m.group("p2") or "").strip()
            body = m.group("rest").strip()
        close = _TRACK_CLOSE_RE.match(body)
        row = {"session_id": session_id, "turn_seq": int(turn_seq or 0), "at": stamp, "part": part,
               "text": close.group("prefix").strip() if close else body, "status": "closed" if close else "open"}
        extra = {} if close else fields
        out.append({"id": _sha16("|".join(str(row[k]) for k in ("session_id", "turn_seq", "at", "part", "text")) + f"|{idx}"),
                    **row, **extra})
    return out


_TRACK_SLUG_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


def tracking_slug(cwd: str) -> str:
    """追蹤帳本的檔名（寫入端 stop._record_tracking_lines 用）：
    最近的部位表根 → 專案根 → cwd 本身（根是 live repo 的 git worktree 時換成 live 的 CLAUDE_DIR；其他 repo 的已登記
    git worktree 換成它的主工作樹：帳本是資料，跟主工作樹走，worktree 刪掉後未結項不會留在孤兒帳本；只看是不是
    worktree、不看部位表），經 cwd_to_project_slug。
    純 ASCII 且不超過 64 字 → 逐字使用；有字元被換成 `-`（有損）或超過 64 字 → 取前 55 字＋`-`＋「完整原始路徑
    （反斜線轉正、casefold）」的 8 碼雜湊，等長的中文路徑不會撞成同一本。cwd 空 → `_no-cwd` 並 stderr。
    已知邊界：ASCII 標點不同的路徑（`D:\\game.v1` 與 `D:\\game-v1`、`D:\\a\\b` 與 `D:\\a-b`）沿用 Claude Code 自己
    projects/<slug> 的規則，會落在同一本；中文與超長路徑才加雜湊。"""
    if not cwd:
        print("[Guardian:AEC] tracking slug: cwd 空，追蹤項寫進 _no-cwd 帳本（讀回時不會注入任何部位）", file=sys.stderr)
        return "_no-cwd"
    from wg_core import CLAUDE_DIR, cwd_to_project_slug, resolve_project_root
    root: Optional[Path] = None
    try:
        from overview_hub import find_map, is_root_git_worktree, main_worktree_of
        found = find_map(cwd)
        root = found[0] if found else None
        if root is None and resolve_project_root is not None:
            root = resolve_project_root(cwd).path
        if root is not None and is_root_git_worktree(Path(root), CLAUDE_DIR):
            root = CLAUDE_DIR                                  # 帳本是資料：根層 worktree 讀寫 live 的那本
        elif root is not None:
            root = main_worktree_of(Path(root)) or root       # 其他 repo 的 worktree 讀寫主工作樹那本
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:AEC] tracking slug: 尋根失敗，退用 cwd：{type(e).__name__}: {e}", file=sys.stderr)
    original = str(root or cwd)
    raw = cwd_to_project_slug(original)
    slug = re.sub(r"[^A-Za-z0-9_-]", "-", raw)
    if slug != raw or len(slug) > 64:
        digest = _sha16(original.replace("\\", "/").rstrip("/").casefold())[:8]
        slug = slug[:55] + "-" + digest
    return slug


def _part_eq(a: Any, b: Any) -> bool:
    return str(a or "").strip().casefold() == str(b or "").strip().casefold()


def _part_compat(a: Any, b: Any) -> bool:
    """部位相容（同追蹤項合併用）：相同、一邊沒寫、或一邊是另一邊的開頭——同一區塊後來寫細了（「合服」→「合服工具 DataHandler」）
    仍算同一件；「戰鬥」對「介面」不算。"""
    x, y = str(a or "").strip().casefold(), str(b or "").strip().casefold()
    return not x or not y or x.startswith(y) or y.startswith(x)


def open_tracking_items(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """帳本列 → 仍 open 的項目（依帳本順序）：被任一 closed 列的 closes.id 指到的那一筆不算 open（一筆結案只消除一筆）。"""
    closed_ids = {str((e.get("closes") or {}).get("id")) for e in entries
                  if e.get("status") == "closed" and isinstance(e.get("closes"), dict)}
    return [e for e in entries if e.get("status") == "open" and tracking_entry_id(e) not in closed_ids]


def _valid_tracking_row(row: Any) -> bool:
    """帳本列的結構：物件；status／text／at 都是字串、text 非空；status 只收 open／closed；
    closed 列的 closes 必須是物件且含字串型 id。"""
    if not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in ("status", "text", "at")):
        return False
    if not row["text"].strip() or row["status"] not in ("open", "closed"):
        return False
    closes = row.get("closes")
    return row["status"] == "open" or (isinstance(closes, dict) and isinstance(closes.get("id"), str))


def tracking_path(slug: str, base_dir: Optional[Path] = None) -> Path:
    """追蹤帳本的檔：workflow/tracking/<slug>.jsonl。"""
    return (base_dir or WORKFLOW_DIR) / "tracking" / f"{slug}.jsonl"


def read_tracking(slug: str, base_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """讀 workflow/tracking/<slug>.jsonl；沒有檔回 []；壞行（非 JSON、非物件或結構不對，見 _valid_tracking_row）
    跳過並 stderr 一行（列行號）；逐行嚴格 UTF-8 解碼，失敗的行改用 replace 解碼照收，另一行 stderr 列「第 N 行編碼損壞」；
    讀檔失敗 stderr 回 []。"""
    p = tracking_path(slug, base_dir)
    try:
        if not p.is_file():
            return []
        raw_lines = p.read_bytes().split(b"\n")
    except OSError as e:
        print(f"[Guardian:Tracking] 追蹤帳本讀不到（不擋注入）：{p}：{e}", file=sys.stderr)
        return []
    out: List[Dict[str, Any]] = []
    bad: List[int] = []
    broken: List[int] = []
    for i, raw in enumerate(raw_lines, 1):
        try:
            line = raw.decode("utf-8")
        except UnicodeDecodeError:
            line = raw.decode("utf-8", errors="replace")
            broken.append(i)
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            row = None
        if _valid_tracking_row(row):
            out.append(row)
        else:
            bad.append(i)
    if broken:
        print(f"[Guardian:Tracking] 追蹤帳本編碼損壞（已用替換字元照收）：{p} 第 {', '.join(map(str, broken[:10]))} 行編碼損壞",
              file=sys.stderr)
    if bad:
        print(f"[Guardian:Tracking] 追蹤帳本有 {len(bad)} 行壞掉已跳過：{p} 第 {', '.join(map(str, bad[:10]))} 行", file=sys.stderr)
    return out


def _resolve_closes(existing: List[Dict[str, Any]], entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """closed 列補 closes＝{id, at, text_prefix}：在「既有帳本＋本批較早的列」中找仍 open、部位相同的最舊一筆，
    對法是「前綴至少 TRACK_CLOSE_MIN_CHARS 字且原文字以它開頭」或「前綴就是原項目全文（strip 後相同）」。
    兩種都對不上 → stderr 並丟掉這筆（不寫成假的 open）。closes.id 只指那一筆，讀回時只消除它。"""
    out: List[Dict[str, Any]] = []
    for e in entries:
        if e.get("status") != "closed" or e.get("closes"):
            out.append(e)
            continue
        prefix = str(e.get("text") or "").strip()
        long_enough = len(prefix) >= TRACK_CLOSE_MIN_CHARS

        def matches(o: Dict[str, Any]) -> bool:
            text = str(o.get("text") or "").strip()
            return text == prefix or (long_enough and text.startswith(prefix))
        target = next((o for o in open_tracking_items(existing + out)
                       if _part_eq(o.get("part"), e.get("part")) and matches(o)), None)
        if target is None:
            why = "結案找不到對應的未結追蹤項" if long_enough else f"結案前綴不足 {TRACK_CLOSE_MIN_CHARS} 字、也不是原項目全文"
            print(f"[Guardian:AEC] {why}，沒有結案：[{e.get('part')}] {prefix}", file=sys.stderr)
            continue
        out.append({**e, "closes": {"id": tracking_entry_id(target), "at": target.get("at"), "text_prefix": prefix}})
    return out


def _supersede_rows(new: Dict[str, Any], old: Dict[str, Any]) -> List[Dict[str, Any]]:
    """新說法取代帳上那筆：同一次追加兩列——先寫新的 open 列（標 supersedes）、再寫結案列關掉舊的（closes 指它、標 superseded_by）；
    中途斷掉最多多一筆重複，不會只關掉舊的。"""
    old_id = tracking_entry_id(old)
    close = {"id": _sha16(f"{old_id}|{new['id']}|superseded"), "session_id": new.get("session_id"),
             "turn_seq": new.get("turn_seq"), "at": new.get("at"), "part": old.get("part") or "",
             "text": str(old.get("text") or ""), "status": "closed", "superseded_by": new["id"],
             "closes": {"id": old_id, "at": old.get("at"), "text_prefix": str(old.get("text") or "")}}
    return [{**new, "supersedes": old_id}, close]


_ASIDE_RE = re.compile(r"（[^（）]*）|\([^()]*\)")


def _summary_key(text: str) -> str:
    """一件追蹤項的比對鍵：去掉括號旁註、空白與標點，大小寫不分。"""
    return re.sub(r"[\W_]+", "", _ASIDE_RE.sub("", text)).casefold()


def _merge_same(existing: List[Dict[str, Any]], entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """規則 TRACKING_SAME_ITEM_NOT_REWRITTEN：open 列寫進帳本前，對「既有帳本＋本批較早的列」裡部位相容（相同、一邊沒寫、或一邊是
    另一邊的開頭，見 _part_compat）的未結項：
    ① 帶 same_as（AI 宣告「同追蹤項：<那筆裡至少 TRACK_CLOSE_MIN_CHARS 字>」，去標點空白後是那筆的一段）→ 恰好對到一筆就換成新說法
    （_supersede_rows）；對不到或對到不只一筆 → 不合併、照記新的、stderr 說原因（不悄悄關掉別件）；
    ② 沒宣告：跟某筆部位相同（嚴格相等，一邊沒寫不算）而且原文相同（不分 session）→ 不重記、stderr。
    字面相近（只差括號註「密碼過期／帳號鎖定」、開頭相同）程式不併：可能是不同的事，併錯會悄悄吞掉一件，比多記一筆更糟；
    換句話說的同一件交 ①。"""
    out: List[Dict[str, Any]] = []
    for e in entries:
        if e.get("status") != "open":
            out.append(e)
            continue
        part = str(e.get("part") or "").strip()
        opens = [o for o in open_tracking_items(existing + out) if _part_compat(o.get("part"), part)]
        snippet = _summary_key(str(e.get("same_as") or ""))
        if e.get("same_as"):
            hits = [o for o in opens if len(snippet) >= TRACK_CLOSE_MIN_CHARS and snippet in _summary_key(str(o.get("text") or ""))]
            if len(hits) == 1:
                out.extend(_supersede_rows({**e, "part": part or str(hits[0].get("part") or "")}, hits[0]))
                continue
            if len(snippet) < TRACK_CLOSE_MIN_CHARS:
                why = f"「同追蹤項」去標點後不足 {TRACK_CLOSE_MIN_CHARS} 字"
            elif not hits:
                why = "帳上找不到這段字的未結項"
            else:
                why = f"對到 {len(hits)} 筆、分不出是哪一筆"
            print(f"[Guardian:Tracking] {why}，沒有合併、照記新的：[{part}] {e.get('text')}｜同追蹤項：{e.get('same_as')}",
                  file=sys.stderr)
            out.append(e)
            continue
        mine = str(e.get("text") or "").strip()
        dup = next((o for o in opens if _part_eq(o.get("part"), part) and str(o.get("text") or "").strip() == mine), None)
        if dup is not None:
            print(f"[Guardian:Tracking] 帳上已有同一件未結項，不重記：[{part}] {e.get('text')}", file=sys.stderr)
            continue
        out.append(e)
    return out


def append_tracking(slug: str, entries: List[Dict[str, Any]], base_dir: Optional[Path] = None) -> Optional[Path]:
    """workflow/tracking/<slug>.jsonl 逐行追加（LF、一行一筆；執行期檔，.gitignore 收）。
    slug 必須 fullmatch [A-Za-z0-9_-]{1,64}（否則 ValueError：../、磁碟根、尾端換行都會指到 tracking 外或建怪檔）。
    open 列先過同一件合併（_merge_same），closed 列再對帳本補 closes（_resolve_closes）。
    entries 空、或結案列全對不上 → 不建檔、回 None；全是帳上已有的同一件 → 不寫、照回帳本路徑（記過了不算失敗）。
    寫入失敗浮 stderr（fail-open）。回帳本路徑。"""
    if not _TRACK_SLUG_RE.fullmatch(str(slug or "")):
        raise ValueError(f"tracking slug must match [A-Za-z0-9_-]+ (got {slug!r})")
    d = (base_dir or WORKFLOW_DIR) / "tracking"
    existing = read_tracking(slug, base_dir) if entries else []
    merged = _merge_same(existing, entries)
    if entries and not merged:
        return d / f"{slug}.jsonl"
    entries = merged
    if any(e.get("status") == "closed" and not e.get("closes") for e in entries):
        entries = _resolve_closes(existing, entries)
    if not entries:
        return None
    try:
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{slug}.jsonl"
        with open(p, "a", encoding="utf-8", newline="\n") as fh:
            for e in entries:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        return p
    except OSError as e:
        print(f"[Guardian:AEC] tracking ledger write failed (fail-open): {e}", file=sys.stderr)
        return None


def append_ledger(sid: str, record: Dict[str, Any], base_dir: Optional[Path] = None) -> None:
    """workflow/harvest-ledger/<sid>.jsonl 追加一筆（執行期檔，.gitignore 收）。失敗浮 stderr。
    items 原樣入帳（含選填的 route／candidate_global／part），不改寫、不補欄。"""
    try:
        d = (base_dir or WORKFLOW_DIR) / "harvest-ledger"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / f"{sid}.jsonl", "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[Guardian:Harvest] ledger write failed (fail-open): {e}", file=sys.stderr)


# ─── Stop 閘判定 ──────────────────────────────────────────────────


def _recent_typed(state: Dict[str, Any]) -> List[str]:
    return user_typed_prompts(state.get("recent_user_prompts", []) or [])[-3:]


def _dismissed(recent_prompts: List[str]) -> Optional[str]:
    """近 3 則使用者原話有 dismiss 詞（先這樣／跳過…）→ 那一則（收割閘、收割待補整批放行、留帳）；沒有回 None。"""
    return next((p for p in reversed(user_typed_prompts(recent_prompts)[-3:]) if _DISMISS_RE.search(p or "")), None)


def harvest_gate_reason(
    state: Dict[str, Any], sid: str, last_text: str, config: Dict[str, Any],
    own_mod_files: List[Dict[str, Any]], turn_seq: int, gate_turn: Optional[int] = None, claimed: Optional[bool] = None,
    waived: Optional[List[Dict[str, str]]] = None,
) -> Optional[str]:
    """該擋 KnowledgeHarvest 就回擋訊息，否則 None。純判定，不改 state。claimed＝呼叫端判好的「本回合宣告完成」（Stop 看整回合，
    補件那則不重說也算）；沒給就看 last_text。

    觸發＝宣告完成 ∧ 有實質活動（turn_seq ≥ min_turns ∨ 本 session
    有改檔 ∨ accessed_files ≥ min_accessed）∧ 冷卻已過（距上次 validated 收割 ≥ min_turns_between）
    ∧ 本 turn 未回報 ∧ 本回合未擋過 ∧ 無 pending（pending 由 Harvest-Pending 閘接手，不雙擋）
    ∧ 近 3 則使用者原話沒有 dismiss 詞（先這樣／跳過；有就整批放行，那則原話 append 進 waived 給呼叫端留帳）。
    「本回合未擋過」比 gate_turn（Stop 給使用者打字開的回合：同伴訊息、背景通知不算新回合）；沒給用 turn_seq。
    """
    cfg = harvest_config(config)
    if not cfg or not turn_seq:
        return None
    if not (bool(last_text) and claims_completion(last_text) if claimed is None else claimed):
        return None
    if reported_this_turn(state, sid, turn_seq):
        return None
    if (state.get("harvest_gate_turn") or {}).get(sid) == (turn_seq if gate_turn is None else gate_turn):
        return None
    sec = section(state, sid)
    if sec.get("pending"):
        return None
    min_turns = int(cfg.get("min_turns", 3))
    min_accessed = int(cfg.get("min_accessed", 5))
    min_between = int(cfg.get("min_turns_between", 3))
    accessed = [a for a in (state.get("accessed_files") or []) if isinstance(a, dict)]
    active = turn_seq >= min_turns or bool(own_mod_files) or len(accessed) >= min_accessed
    if not active:
        return None
    # 冷卻（規則 TURN_SINCE_USER_PROMPT）：兩邊都有使用者回合計數就算回合數差（同伴訊息、背景通知不算一回合）；
    # 舊 state 沒計數才退回 turn_seq 差
    last_valid, last_u, cur_u = sec.get("last_valid_harvest_turn"), sec.get("last_valid_harvest_uturn"), state.get("user_turn_count")
    if last_u is not None and cur_u is not None:
        if int(cur_u) - int(last_u) < min_between:
            return None
    elif last_valid is not None and turn_seq - int(last_valid) < min_between:
        return None
    said = _dismissed(_recent_typed(state))
    if said is not None:
        if waived is not None:
            waived.append({"item": "收割", "quote": said[:120], "line": ""})
        return None
    return harvest_block_message(cwd=str((state.get("session") or {}).get("cwd") or ""))


def harvest_block_message(cwd: str = "") -> str:
    """cwd：session 的工作目錄；在 ~/.claude 之下才附「記憶系統開發面 → realm=local」那句。
    追蹤項只說「填進收尾檢核 k 欄」：k 欄不寫追蹤帳本、也不另寫病灶文件。"""
    tracking = "追蹤項請填進收尾檢核 k 欄。"
    src = "\n".join(f"  {s}" for s in _HARVEST_SOURCES)
    return (
        "[Guardian:KnowledgeHarvest] 宣告完成＝階段完工，收尾前先盤點本場學到的東西，"
        "再呼叫 MCP tool knowledge_harvest_report（items=[] 也要呼叫）。\n"
        "掃六個來源：\n" + src + "\n"
        "判準：只寫「從程式碼/文件讀不出來、之後會重查或重犯」的；專案專屬 → scope=shared(+project_cwd)；"
        + ("記憶系統開發面 → realm=local/MemDev；" if _is_under_claude_dir(cwd) else "")   # 只在記憶系統自己的目錄裡有意義
        + "一次性事實不寫。\n"
        "atom_write／atom_retire 必在呼叫 knowledge_harvest_report **之前**做完——每個 item 用工具回的 receipt 核對："
        "created/appended/replaced 要同 path 同 op 且 index_ok；superseded 要 receipt.supersedes 含該 atom；"
        "retired 要 retire receipt 的 old_path 相符；對不上會被擋回補。"
        "items 欄位：source / summary / action(created|appended|replaced|superseded|retired|skip) / atom / path / scope / reason(skip 必填)"
        " / route(part_doc|global|org|local|shared|candidate_global，選填；part_doc 必帶 part；global／candidate_global 的 summary 不帶專案名) / candidate_global / part。"
        + tracking +
        "無東西 → items=[] 照樣呼叫。"
    )


def in_progress_text(last_text: str) -> bool:
    """收尾訊息是中途狀態句（仍在等 agent 回報／尚未開始／整合中途…）→ 不是收尾，閘不該在此刻擋。
    詞表＝forbidden-phrases.json completion_claim.exclude_patterns（與 claims_completion 同源）；另有一句宣告完成
    （claims_completion，逐句看）就不算中途：「三件都做完了。中途被擋了兩次」是收尾（規則 COMPLETION_CLAIM_PER_SENTENCE）。"""
    return (bool(last_text) and bool(_COMPLETION_EXCLUDE_RE.search(last_text[-2000:]))
            and not claims_completion(last_text))


def pending_gate_reason(state: Dict[str, Any], sid: str, turn_seq: int, last_text: str = "",
                        gate_turn: Optional[int] = None, waived: Optional[List[Dict[str, str]]] = None) -> Optional[str]:
    """本 session 收割回報有核不過的 item → 每回合擋一次要求補（回合＝gate_turn，Stop 給使用者打字開的回合；沒給用 turn_seq）；
    本則是中途狀態句（還在等別人回報）就不擋：擋了只會逼模型在半途補報。使用者說「先這樣／跳過」整批放行
    （待補 append 進 waived 給呼叫端留帳）。"""
    if not turn_seq:
        return None
    pending = section(state, sid).get("pending") or []
    if not pending:
        return None
    if in_progress_text(last_text):
        return None
    if (state.get("harvest_pending_gate_turn") or {}).get(sid) == (turn_seq if gate_turn is None else gate_turn):
        return None
    said = _dismissed(_recent_typed(state))
    if said is not None:
        if waived is not None:
            waived.extend({"item": str(p)[:160], "quote": said[:120], "line": ""} for p in pending)
        return None
    return (
        f"[Guardian:Harvest-Pending] 收割回報有 {len(pending)} 項核不過（宣稱寫了但沒有對應的 atom 工具 receipt）：\n"
        + "\n".join(f"  ✗ {x}" for x in pending[:6])
        + "\n先用 atom_write／atom_retire 真的做完（或把該 item 改成 action=skip 附 reason），"
        "再重新呼叫 knowledge_harvest_report。"
    )


# ─── vcs-sync worker 活鎖 ─────────────────────────────────────────


def vcs_sync_lock_path(root: Path, base_dir: Optional[Path] = None) -> Path:
    """與 wg_vcs_sync 同一條鎖檔規則：sha1(resolve 後 posix 小寫)[:12].lock，內容為 pid。"""
    key = Path(root).resolve().as_posix().lower()
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return (base_dir or WORKFLOW_DIR) / "vcs-sync" / f"{digest}.lock"


def vcs_sync_lock_active(root: Path, base_dir: Optional[Path] = None) -> bool:
    """worker 是否正持有該 root 的鎖（此刻 commit/push 中，unpushed 判定不準）。
    先看鎖檔 pid 是否活著（便宜、測試可注入 base_dir）；真實目錄下再問 wg_vcs_sync.lock_is_live
    （OS 互斥鎖試取，權威）。兩者任一為真即視為活鎖——誤判只是少提醒一次 unpushed。"""
    try:
        raw = vcs_sync_lock_path(root, base_dir).read_text(encoding="utf-8").strip()
        pid = int(raw)
        if pid > 0 and _is_pid_alive(pid):
            return True
    except (OSError, ValueError):
        pass
    if base_dir is None and WORKFLOW_DIR == _DEFAULT_WORKFLOW_DIR:
        try:
            from wg_vcs_sync import lock_is_live
            return bool(lock_is_live(Path(root)))
        except Exception:
            return False
    return False