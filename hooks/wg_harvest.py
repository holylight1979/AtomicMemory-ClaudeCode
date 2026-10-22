"""wg_harvest.py — 階段完工知識收割（KnowledgeHarvest）、追蹤項帳本、交付時「順手看到最該修」的純函式。

誰用：
  - handlers/stop.py：harvest_gate_reason（該不該擋、擋什麼話）、pending_gate_reason、
    vcs_sync_lock_active（SyncReminder 遇 worker 活鎖跳過該 root）；record_pick／pick_due／mark_pick_asked／
    pick_material／pick_prompt（交付時那一問與記帳）。
  - handlers/post_tool_use.py（one-writer）：parse_receipt / record_atom_op（atom 工具收據入帳）、
    validate_items（收割回報逐項核對）、append_ledger；tracking_entries／append_tracking（AEC (k) 追蹤項）。
  - handlers/session_start.py：open_tracking_items／proposal_lines（開場列未結項與建議）。

state 分區（全部按 session_id 分區，防共用工作樹的隔壁 session 誤放行）：
  state["atom_ops"][sid]            = [{seq, turn_seq, op, atom, path, index_ok, ok, supersedes, old_path, new_path}]
  state["knowledge_harvest"][sid]   = {turn_seq, items, pending, validated, retired_paths, at, last_valid_harvest_turn, last_valid_op_seq}
  state["harvest_gate_turn"][sid]   = 本 session 已擋過 KnowledgeHarvest 的回合（使用者打字開的回合，stop._user_turn）
  state["harvest_pending_gate_turn"][sid] = 本 session 已擋過 Harvest-Pending 的回合（同上）
  state["pick_one"][sid]            = {asked_turn, covered_turn}（交付時那一問：上次問、上次答過的回合）
state 只讀寫傳入的 dict，write_state 由 handler 做；帳本檔（workflow/tracking、workflow/harvest-ledger）由本模組直接追加。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from wg_core import _now_iso, WORKFLOW_DIR, user_typed_prompts
from wg_evasion import claims_completion, _DISMISS_RE, _COMPLETION_EXCLUDE_RE
from wg_extraction import _is_pid_alive
from wg_release_rules import in_user_turn

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
    return bool(turn_seq) and in_user_turn(sec.get("turn_seq"), state, turn_seq) and bool(sec.get("validated"))


def reported_this_turn(state: Dict[str, Any], sid: str, turn_seq: int) -> bool:
    """本回合（同上）已經回報過收割。"""
    return bool(turn_seq) and in_user_turn(section(state, sid).get("turn_seq"), state, turn_seq)


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


# ─── AEC 追蹤項帳本（v6 G13：收尾誠實）─────────────────────────────────

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
    """追蹤帳本的檔名（寫入端 post_tool_use 與讀取端 wg_overview／session_start 共用）：
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


def read_tracking(slug: str, base_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """讀 workflow/tracking/<slug>.jsonl；沒有檔回 []；壞行（非 JSON、非物件或結構不對，見 _valid_tracking_row）
    跳過並 stderr 一行（列行號）；逐行嚴格 UTF-8 解碼，失敗的行改用 replace 解碼照收，另一行 stderr 列「第 N 行編碼損壞」；
    讀檔失敗 stderr 回 []。"""
    p = (base_dir or WORKFLOW_DIR) / "tracking" / f"{slug}.jsonl"
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
             "closes": {"id": old_id, "at": old.get("at"), "text_prefix": str(old.get("text") or "")},
             **({"source": new["source"]} if new.get("source") else {})}
    return [{**new, "supersedes": old_id}, close]


def _merge_same(existing: List[Dict[str, Any]], entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """規則 TRACKING_SAME_ITEM_NOT_REWRITTEN：open 列寫進帳本前，對「既有帳本＋本批較早的列」裡部位相容（相同或一邊沒寫）的未結項：
    ① 帶 same_as（AI 宣告「同追蹤項：<那筆裡至少 TRACK_CLOSE_MIN_CHARS 字>」，去標點空白後是那筆的一段）→ 恰好對到一筆就換成新說法
    （_supersede_rows）；對不到或對到不只一筆 → 不合併、照記新的、stderr 說原因（不悄悄關掉別件）；
    ② 沒宣告：跟某筆部位相同（嚴格相等，一邊沒寫不算）而且原文相同（不分 session，同 PickOne 的 repeat）→ 不重記、stderr。
    字面相近（只差括號註「密碼過期／帳號鎖定」、開頭相同）程式不併：可能是不同的事，併錯會悄悄吞掉一件，比多記一筆更糟；
    換句話說的同一件交 ①。已帶 supersedes 的列（PickOne 同回合換說法）照寫。"""
    out: List[Dict[str, Any]] = []
    for e in entries:
        if e.get("status") != "open" or e.get("supersedes"):
            out.append(e)
            continue
        part = str(e.get("part") or "").strip()
        opens = [o for o in open_tracking_items(existing + out)
                 if not part or not str(o.get("part") or "").strip() or _part_eq(o.get("part"), part)]
        snippet = _pick_summary(str(e.get("same_as") or ""))
        if e.get("same_as"):
            hits = [o for o in opens if len(snippet) >= TRACK_CLOSE_MIN_CHARS and snippet in _pick_summary(str(o.get("text") or ""))]
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


def tracking_items_for_part(slug: str, part_names: List[str], base_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """某部位（part 或 part_short，不分大小寫）仍 open 的追蹤項；part 空的不算任何部位。"""
    names = [n for n in part_names if str(n or "").strip()]
    return [e for e in open_tracking_items(read_tracking(slug, base_dir))
            if str(e.get("part") or "").strip() and any(_part_eq(e.get("part"), n) for n in names)]


TRACK_INJECT_MAX_ITEMS, TRACK_INJECT_ITEM_CHARS = 5, 200


def tracking_block(items: List[Dict[str, Any]], budget: int) -> str:
    """注入文字末段「【未結追蹤項】」：最多 5 筆、每筆截 200 字、整段不超過 budget 字；超過附「另有 N 筆」。沒有項目回空字串。"""
    if not items:
        return ""
    head = "【未結追蹤項】（這個部位以前記下、還沒結案的問題；處理完在 AEC (k) 寫「[部位] 結案：<原文開頭至少 8 字；原文不足 8 字就寫全文>」）"
    lines = [head]
    shown = 0
    for e in items[:TRACK_INJECT_MAX_ITEMS]:
        t = str(e.get("text") or "")
        t = t if len(t) <= TRACK_INJECT_ITEM_CHARS else t[:TRACK_INJECT_ITEM_CHARS - 1] + "…"
        line = f"- {t}（{str(e.get('at') or '')[:10]}）" + _proposal_tail(e)
        if len("\n".join(lines + [line])) > budget:
            break
        lines.append(line)
        shown += 1
    rest = len(items) - shown
    if rest > 0:
        lines.append(f"- 另有 {rest} 筆")
    return "\n".join(lines)


def _clip(s: Any, n: int) -> str:
    s = str(s or "").strip()
    return s if len(s) <= n else s[:n - 1] + "…"


def _proposal_tail(e: Dict[str, Any]) -> str:
    """追蹤項的提議欄接在行尾：「｜建議：…｜該誰解：…」；兩欄都沒寫回空字串。"""
    tail = f"｜建議：{_clip(e.get('proposal'), 120)}" if str(e.get("proposal") or "").strip() else ""
    return tail + (f"｜該誰解：{_clip(e.get('owner'), 40)}" if str(e.get("owner") or "").strip() else "")


def proposal_lines(items: List[Dict[str, Any]], limit: int = 3) -> List[str]:
    """SessionStart 開頭：仍未結、附了建議的追蹤項（交付時點出的最該修，或 (k) 行尾寫了「｜建議：」的），不分有沒有部位，
    最新 limit 筆＋要 AI 在第一則回覆告訴使用者；沒有回 []。"""
    picks = [e for e in items if str(e.get("proposal") or "").strip()]
    if not picks:
        return []
    newest = sorted(picks, key=lambda e: str(e.get("at") or ""), reverse=True)[:limit]
    lines = [f"[Guardian:Tracking] 之前交付時點出、還沒解的問題 {len(picks)} 件（附建議怎麼解；列最新 {len(newest)} 件）："]
    for e in newest:
        part = f"[{e['part']}] " if str(e.get("part") or "").strip() else ""
        lines.append(f"- {part}{_clip(e.get('text'), 160)}（{str(e.get('at') or '')[:10]}）")
        lines.append(f"  建議：{_clip(e.get('proposal'), 160)}"
                     + (f"｜該誰解：{_clip(e.get('owner'), 40)}" if str(e.get("owner") or "").strip() else ""))
    lines.append("第一則回覆開頭用一兩句白話告訴使用者這幾件還沒解、建議怎麼解（跟這次任務碰到同一塊的先說）；"
                 "解掉的在 AEC (k) 寫「[部位] 結案：<原文開頭至少 8 字>」（沒標部位就不帶部位）。")
    return lines


# ─── 交付時順手點出最該修的一件（v6 G4／G5／G13）────────────────────────────
# 程式只管時點與記帳，判斷交 AI：寫碼交付時 Stop 送一次「這次看到的鄰近問題裡哪一件最該修」（只提醒、不擋），材料依部位分組、
# 數字標參考；AI 回覆裡的「順手看到最該修」段記成追蹤項（附為什麼、為什麼不是數字最高的、建議怎麼解、該誰解），開場列出。
# state["pick_one"][sid] = {asked_turn：上次問的回合, covered_turn：上次答過（記進帳本、帳上已有、或答「無」）的回合}
# 「一批改動」以回合號分：問過之後同一回合裡的改動（順手修掉剛點出的那件、回應別道閘的修補）算同一次交付，不再問。

PICK_HEAD = "順手看到最該修"
_PICK_LABELS = (("why", "為什麼是它"), ("not_top", "為什麼不是數字最高"), ("proposal", "建議怎麼解"), ("owner", "該誰解"),
                ("same_as", "同追蹤項"))
_PICK_LINE_RE = re.compile(r"^[\s#*\-•]*(?:\d+[.、)]\s*)?(?P<label>[^：:\n]{2,24}?)\**\s*[：:]\s*(?P<value>.*?)\s*$")
_PICK_NONE_RE = re.compile(r"^無(?:$|[\s，,。；;（(：:、])")
PICK_MATERIAL_MAX_PARTS = 4


def parse_pick(text: str) -> Optional[Dict[str, Any]]:
    """回覆裡最後一段「順手看到最該修：…」＋其後的 為什麼是它／為什麼不是數字最高的那個／建議怎麼解／該誰解 → dict
    {none, part, text, why, not_top, proposal, owner}（none＝寫了「無，因為…」）。標頭要在行首（前面可有清單符號、粗體），
    引言（> 開頭）與 code block 裡的、句中順帶提到的都不算（解釋格式、引用舊回答不入帳）；照抄範本（含「哪一件」）不算；
    不是「無」的要至少有「為什麼是它」或「建議怎麼解」。沒有回 None。"""
    blocks: List[Dict[str, str]] = []
    cur: Optional[Dict[str, str]] = None
    fenced = False
    for raw in (text or "").splitlines():
        if raw.lstrip().startswith("```"):
            fenced = not fenced
            continue
        m = None if fenced or raw.lstrip().startswith(">") else _PICK_LINE_RE.match(raw)
        if not m:
            continue
        label = m.group("label").strip().strip("*").strip()
        value = m.group("value").strip().strip("*").strip()
        if label.startswith(PICK_HEAD):
            cur = {"head": value}
            blocks.append(cur)
            continue
        key = next((k for k, lb in _PICK_LABELS if label.startswith(lb)), None) if cur is not None else None
        if key and key not in cur:
            cur[key] = value
    for b in reversed(blocks):
        head = b.get("head", "")
        none = bool(_PICK_NONE_RE.match(head))
        if not head or "哪一件" in head or not (none or b.get("why") or b.get("proposal")):
            continue
        part, body = "", head
        pm = None if none else _TRACK_PART_RE.match(head)
        if pm:
            part, body = (pm.group("p1") or pm.group("p2") or "").strip(), pm.group("rest").strip()
        return {"none": none, "part": part, "text": body,
                **{k: b.get(k, "") for k, _ in _PICK_LABELS if k != "same_as" or b.get(k)}}   # 同追蹤項有寫才帶
    return None


_PICK_ASIDE_RE = re.compile(r"（[^（）]*）|\([^()]*\)")


def _pick_summary(text: str) -> str:
    """那一件的摘要：去掉括號旁註、空白與標點，大小寫不分。"""
    return re.sub(r"[\W_]+", "", _PICK_ASIDE_RE.sub("", text)).casefold()


def same_pick_target(a: str, b: str) -> bool:
    """兩句說的是不是同一件：摘要相同，或較短那句至少 TRACK_CLOSE_MIN_CHARS 字且是另一句的開頭。
    只看檔名與識別字、或字面相似度都不算：同一個函式的不同問題（「validate 未檢查上限」對「未檢查下限」）字面很像，
    併錯會把一件真的未結項悄悄關掉，比多記一筆重複更糟。"""
    short, long_ = sorted((_pick_summary(a), _pick_summary(b)), key=len)
    return bool(short) and (short == long_ or (len(short) >= TRACK_CLOSE_MIN_CHARS and long_.startswith(short)))


def _pick_sec(state: Dict[str, Any], sid: str) -> Dict[str, Any]:
    root = state.setdefault("pick_one", {})
    return root.setdefault(sid, {}) if isinstance(root, dict) else {}


def record_pick(state: Dict[str, Any], sid: str, turn_seq: int, text: str, cwd: str,
                at: Optional[str] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
    """text（交付的最後一則回覆）裡的「順手看到最該修」段 → (事件, parse_pick 的結果)；沒有那段回 None。事件：
    recorded＝寫進本專案追蹤帳本一筆 open（source＝pick，帶 why／not_top／proposal／owner）；repeat＝帳上已有同部位同文字的未結項，
    不重記（同一則回覆被看兩次、或下一批又點出同一件）；updated＝同 session 同回合同部位已記過同一件（same_pick_target：文字略異），
    改用第二次的內容：同一次追加兩列——先寫新的 open 列（標 supersedes）、再寫結案列關掉第一筆（closes 指它、標 superseded_by）；
    中途斷掉最多多一筆重複，不會只關掉舊的。帳本只追加、不改寫（多 session 同時追加沒有鎖），清理器照「結案＋開項」成對處理；
    update_failed＝那兩列寫不進去，第一筆照留、stderr；
    none＝答「無，因為…」，不進帳本；write_failed＝帳本寫不進去。
    write_failed 以外都記下這批改動答過了（covered_turn）；寫失敗不算答過，下次照問、照記。"""
    pick = parse_pick(text)
    if pick is None:
        return None
    event = "none"
    if not pick["none"]:
        slug = tracking_slug(cwd)
        existing = read_tracking(slug)
        opens = open_tracking_items(existing)
        same_turn = next((o for o in opens if o.get("source") == "pick" and o.get("session_id") == sid
                          and int(o.get("turn_seq") or 0) == int(turn_seq or 0) and _part_eq(o.get("part"), pick["part"])
                          and same_pick_target(str(o.get("text") or ""), pick["text"])), None)
        row = {"session_id": sid, "turn_seq": int(turn_seq or 0), "at": at or _now_iso(), "part": pick["part"],
               "text": pick["text"], "status": "open", "source": "pick"}
        extra = {k: pick[k] for k, _ in _PICK_LABELS if pick.get(k)}
        new = {"id": _sha16("|".join(str(row[k]) for k in ("session_id", "turn_seq", "at", "part", "text")) + "|pick"),
               **row, **extra}
        if (any(_part_eq(o.get("part"), pick["part"]) and str(o.get("text") or "").strip() == pick["text"] for o in opens)
                or (same_turn is None and not _merge_same(existing, [new]))):   # 別的入口（k 欄、followup）已記過同一句
            event = "repeat"
        elif same_turn is None:
            event = "recorded" if append_tracking(slug, [new]) else "write_failed"
        else:
            event = "updated" if append_tracking(slug, _supersede_rows(new, same_turn)) else "update_failed"
            if event == "update_failed":
                print(f"[Guardian:PickOne] 同一回合又點出同一件，追蹤帳本沒換成新的說法（寫不進去），帳上留第一次那筆："
                      f"{same_turn.get('text')}", file=sys.stderr)
    if event != "write_failed":
        _pick_sec(state, sid)["covered_turn"] = int(turn_seq or 0)
    return event, pick


def _mod_turn(m: Dict[str, Any]) -> int:
    return int((m or {}).get("last_turn_seq") or (m or {}).get("turn_seq") or 0)


def pick_due(state: Dict[str, Any], sid: str, code_mods: List[Dict[str, Any]], boundary: bool) -> bool:
    """該不該送「順手看到最該修」那一問：到了交付邊界（boundary），且本 session 在上次問過或記過之後又改了程式
    （code_mods＝本 session 改過的程式檔紀錄）。同一批改動只問一次；AI 自己先寫了那段（covered_turn）也不再問。
    改檔紀錄沒有回合號的不算新改動。"""
    if not boundary or not code_mods:
        return False
    sec = (state.get("pick_one") or {}).get(sid) or {}
    mark = max(int(sec.get("asked_turn") or 0), int(sec.get("covered_turn") or 0))
    return any(_mod_turn(m) > mark for m in code_mods)


def mark_pick_asked(state: Dict[str, Any], sid: str, turn_seq: int) -> None:
    _pick_sec(state, sid)["asked_turn"] = int(turn_seq or 0)


CALLSITE_BUDGET_S = 2.0          # 一次 pick_material 算呼叫點的總時間（每條壞味道一次 git grep）
_CALLSITE_LANG = {".py": "py", ".js": "js", ".mjs": "js", ".cjs": "js", ".jsx": "js", ".ts": "js", ".tsx": "js"}
_CALLSITE_GLOBS = {"py": ["*.py"], "js": ["*.js", "*.mjs", "*.cjs", "*.jsx", "*.ts", "*.tsx"]}
_JS_SPEC_RE = re.compile(r"""(?:\bfrom\s+|\brequire\(\s*|\bimport\(\s*|^\s*import\s+)['"]([^'"]+)['"]""")
_JS_COMMENT_PREFIX = ("//", "/*", "*")
_TEST_FILE_RE = re.compile(r"(^|/)(tests?|verify|__tests__|specs?)/|(^|/)(test_[^/]*|[^/]*_test\.py|verify_[^/]*\.py|conftest\.py"
                           r"|[^/]*\.(test|spec)\.[jt]sx?)$")


def _imports_stem(text: str, stem: str, lang: str) -> Optional[bool]:
    """這支檔有沒有 import 模組名 stem。Python 用 ast：`import a.stem`、`from a.stem import x`、`from a import stem`
    （看被匯入的名字，不看 as 後面的別名；分好幾行的括號匯入、註解都照語法算）；JS／TS 逐行比 import／require 的路徑檔名，
    註解行不算。Python 解析不了回 None（呼叫端算進「無法判」）。"""
    if lang == "js":
        return any(Path(spec).stem == stem or Path(spec).name == stem
                   for ln in text.splitlines() if not ln.lstrip().startswith(_JS_COMMENT_PREFIX)
                   for spec in _JS_SPEC_RE.findall(ln))
    import ast
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split(".")[-1] == stem for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and ((node.module or "").split(".")[-1] == stem
                                                  or any(a.name == stem for a in node.names)):
            return True
    return False


def _callsites(root: Path, rel: str, deadline: float) -> str:
    """壞味道那個檔的呼叫點：專案裡 git 追蹤的檔有誰 import 它、幾處 → 「呼叫點 0」「呼叫點 2（a.py、b.py）」，
    測試檔另計「另有測試 N 支」（測試會 import 沒人用的舊碼，混在一起會把死碼看成有人用）。以模組名（檔名去副檔名）比對，
    同名模組會一起算。只認 Python 與 JS／TS 的 import；其他語言、不在 git、git 失敗或逾時 → 「呼叫點 無法判（原因）」。"""
    import subprocess
    p = Path(rel)
    lang = _CALLSITE_LANG.get(p.suffix.lower())
    if not lang:
        return f"呼叫點 無法判（{p.suffix or '沒有副檔名'} 不以 import 檔案互相呼叫）"
    stem = p.parent.name if p.stem == "__init__" else p.stem
    if lang == "py" and not stem.isidentifier():
        return "呼叫點 無法判（檔名不是合法模組名，只能當腳本跑或用路徑載入）"
    left = deadline - time.monotonic()
    if not stem or left < 0.2:
        return "呼叫點 無法判（來不及算）"
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(root), "grep", "-I", "-l", "-w", "-F", "-e", stem,
                            "--", *_CALLSITE_GLOBS[lang]], capture_output=True, timeout=left,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as e:
        return f"呼叫點 無法判（git grep 失敗：{type(e).__name__}）"
    if r.returncode not in (0, 1):                     # 1＝沒有任何一行含這個字
        return "呼叫點 無法判（不在 git 版控或 git grep 失敗）"
    self_rel = p.as_posix().removeprefix("./")
    callers: List[str] = []
    unparsed = 0
    for f in r.stdout.decode("utf-8", "replace").splitlines():   # 含這個字的檔才讀、才解析
        if f == self_rel:
            continue
        if time.monotonic() > deadline:
            return "呼叫點 無法判（來不及算）"
        try:
            hit = _imports_stem((root / f).read_text(encoding="utf-8", errors="replace"), stem, lang)
        except OSError:
            hit = None
        if hit is None:
            unparsed += 1
        elif hit:
            callers.append(f)
    tests = [f for f in callers if _TEST_FILE_RE.search(f)]
    prod = [f for f in callers if f not in tests]
    names = "、".join(Path(f).name for f in prod[:3]) + ("…" if len(prod) > 3 else "")
    return (f"呼叫點 {len(prod)}" + (f"（{names}）" if prod else "")
            + (f"，另有測試 {len(tests)} 支" if tests else "") + (f"，{unparsed} 支解析不了沒算" if unparsed else "")
            + _runnable_note(root / p, lang))


def _runnable_note(path: Path, lang: str) -> str:
    """Python 檔自己有 `if __name__ == "__main__"` → 補一句「本身可直接執行」：腳本靠被執行不靠被 import，呼叫點 0 不等於沒人用。"""
    if lang != "py":
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "，本身可直接執行（呼叫點只算 import）" if re.search(r"__name__\s*==\s*['\"]__main__['\"]", text) else ""


def _pick_smells(wo: Any, root: Path, row: Dict[str, Any], cfg: Dict[str, Any],
                 deadline: Optional[float] = None) -> List[str]:
    """部位的壞味道報告（overview-hub 設了 smells_report 才有）前 2 名，附分數與呼叫點（_callsites）。"""
    report = str(cfg.get("smells_report") or "").strip()
    if not report:
        return []
    rp = Path(report) if Path(report).is_absolute() else root / report
    if not rp.is_file():
        return []
    rows, _, _ = wo._smells_rows(rp)
    mine = [r for r in rows if not r.get("part") or r["part"] in (row.get("part"), row.get("part_short"))]
    mine.sort(key=lambda r: -float(r["score"]) if isinstance(r.get("score"), (int, float)) else 0)
    deadline = deadline if deadline is not None else time.monotonic() + CALLSITE_BUDGET_S
    out = []
    for r in mine[:2]:
        rel = Path(str(r["path"]))
        if rel.is_absolute():
            try:
                rel = rel.relative_to(root)
            except ValueError:
                pass
        out.append(f"{rel.name}｜{r.get('category') or r.get('kind') or '?'}"
                   + (f"｜分數 {r['score']}" if isinstance(r.get("score"), (int, float)) else "")
                   + f"｜{_callsites(root, rel.as_posix(), deadline)}")
    return out


_LINE_COUNT_MAX_BYTES = 4 << 20


def _line_counts(paths: List[str]) -> str:
    """改到的檔各幾行（讀不到或超過 4MB 的略過），最多 3 個：「stop.py 1900 行、…」。"""
    out = []
    for p in paths[:3]:
        try:
            fp = Path(p)
            if fp.stat().st_size <= _LINE_COUNT_MAX_BYTES:
                n = fp.read_bytes().count(b"\n") + 1
                out.append(f"{fp.name} {n} 行")
        except OSError:
            continue
    return "、".join(out)


def _pick_part_line(wo: Any, root: Path, row: Dict[str, Any], paths: List[str], config: Dict[str, Any],
                    deadline: Optional[float] = None) -> str:
    cfg = wo._cfg(config, root)
    defects = [d.lstrip("- ").strip() for d in wo.defects_top_n(wo._cards_for(root, row, cfg), 2)]
    items = tracking_items_for_part(tracking_slug(str(root)), [row.get("part"), row.get("part_short")])
    smells = _pick_smells(wo, root, row, cfg, deadline)
    sizes = _line_counts(paths)
    bits = [f"影響到：{row.get('downstream') or '表上沒寫'}",
            "已知病灶：" + ("；".join(_clip(d, 80) for d in defects) if defects else "導讀卡沒寫")]
    if smells:
        bits.append("壞味道報告前 2 名（分數只當參考）：" + "；".join(smells))
    if sizes:
        bits.append(f"這次改到的檔（行數只當參考）：{sizes}")
    bits.append(f"未結追蹤項 {len(items)} 筆" + (f"，最新一筆：{_clip(items[-1].get('text'), 60)}" if items else ""))
    return _clip(f"- 【{row['part_short']}】" + "；".join(bits), 400)


def pick_material(code_paths: List[str], config: Dict[str, Any]) -> List[str]:
    """改過的程式檔 → 依部位分組的材料，一部位一行：影響到誰（表上「下游」）、導讀卡已知病灶前 2 條、壞味道報告前 2 名附分數
    與呼叫點（各部位共用 CALLSITE_BUDGET_S）、這次改到的檔行數、未結追蹤項筆數（數字都標參考）。不排名：部位照改檔先後；
    最多 PICK_MATERIAL_MAX_PARTS 個部位。部位表查不到的檔列一行檔名。某部位的材料讀失敗就寫一句原因，不中斷其他部位。"""
    deadline = time.monotonic() + CALLSITE_BUDGET_S
    try:
        import wg_overview as wo
    except ImportError as e:
        return [f"- （讀不到部位表模組：{e}）"]
    groups: Dict[Tuple[str, str], Tuple[Path, Dict[str, Any], List[str]]] = {}
    loose: List[str] = []
    for p in code_paths:
        hit = wo._lookup_quiet(p)
        if hit:
            groups.setdefault((str(hit[0]), hit[1]["part_short"]), (hit[0], hit[1], []))[2].append(p)
        else:
            loose.append(Path(p).name)
    lines: List[str] = []
    for (_, short), (root, row, paths) in list(groups.items())[:PICK_MATERIAL_MAX_PARTS]:
        try:
            lines.append(_pick_part_line(wo, root, row, paths, config, deadline))
        except Exception as e:  # noqa: BLE001
            lines.append(f"- 【{short}】（材料讀不到：{type(e).__name__}: {e}）")
    if len(groups) > PICK_MATERIAL_MAX_PARTS:
        lines.append(f"- 另有 {len(groups) - PICK_MATERIAL_MAX_PARTS} 個部位沒列")
    if loose:
        lines.append("- 部位表查不到的檔：" + _clip("、".join(dict.fromkeys(loose)), 200))
    return lines


PICK_OPENS_MAX = 5


def session_open_tracking(cwd: str, sid: str) -> List[str]:
    """本專案追蹤帳本裡本 session 記的、還沒結的項目「[部位] 原文」（帳本順序）。讀不到回空。"""
    return [f"[{o.get('part') or ''}] {o.get('text')}" for o in open_tracking_items(read_tracking(tracking_slug(cwd)))
            if o.get("session_id") == sid]


def pick_prompt(material: List[str], opens: Sequence[str] = ()) -> str:
    """交付時那一問的全文（Stop additionalContext）：材料＋要 AI 在回覆最後照格式寫的那一段。
    opens＝本 session 已記、還沒結的追蹤項（「[部位] 原文」）：列出來讓 AI 判斷要點的是不是其中一件（規則 TRACKING_SAME_ITEM_NOT_REWRITTEN）。"""
    same = ([f"本 session 已記、還沒結的追蹤項（最近 {PICK_OPENS_MAX} 筆）；要點的是其中同一件，就在五行後面加一行"
             "「同追蹤項：<那筆裡連續至少 8 個字>」，系統換成你這次的說法、不另記一筆：",
             *(f"- {o[:100]}" for o in list(opens)[-PICK_OPENS_MAX:])] if opens else [])
    return "\n".join([
        "[Guardian:PickOne] 這次交付改了程式。收尾前順手掃一眼（只提醒、不擋；這批改動只問這一次）："
        "這次讀到、改到的程式附近，哪一件最該修？",
        "材料依部位分組（只是材料、不是排名；裡面的數字只當參考，不是挑選理由）：",
        *(material or ["- （沒有材料：照你這次讀過、改過的程式判斷）"]),
        "在給使用者的回覆最後加這一段（白話、照這幾行開頭寫、不要放進引言或 code block；系統會照這段記成追蹤項，"
        "下次開 session 開頭會列出來）：",
        f"{PICK_HEAD}：[部位] <哪一件、在哪個檔哪一段>",
        "為什麼是它：<它影響誰、資料怎麼流、會不會反覆出事——用責任與影響說>",
        "為什麼不是數字最高的那個：<材料或你看過的數字（行數、分數、筆數）裡最高的是哪個、為什麼不是它；沒看過任何數字就寫「沒有數字可比」>",
        "建議怎麼解：<具體做法>",
        "該誰解：<這個 session／下一個寫碼 session／使用者決定／根層記憶系統／其他專案>",
        "跟這次同根、小、在範圍內的，直接修掉再交付，不用寫進來；真的沒看到值得修的，寫「順手看到最該修：無，因為…」。",
        "之後被別的閘擋下而補了一則，交付的最後一則要保留這五行（系統讀最後一則記帳），不要寫「見上一則」。",
        *same,
    ])


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
    return harvest_block_message()


def harvest_block_message(tracking_written: bool = False) -> str:
    """tracking_written：本 turn 的 AEC 追蹤項（k）已由 append_tracking 入帳（掛點在 post_tool_use，track-b 接）。"""
    tracking = ("追蹤項已入帳，有部位的同時寫進病灶文件。" if tracking_written
                else "追蹤項請填進收尾檢核 k 欄。")
    src = "\n".join(f"  {s}" for s in _HARVEST_SOURCES)
    return (
        "[Guardian:KnowledgeHarvest] 宣告完成＝階段完工，收尾前先盤點本場學到的東西，"
        "再呼叫 MCP tool knowledge_harvest_report（items=[] 也要呼叫）。\n"
        "掃六個來源：\n" + src + "\n"
        "判準：只寫「從程式碼/文件讀不出來、之後會重查或重犯」的；專案專屬 → scope=shared(+project_cwd)；"
        "記憶系統開發面 → realm=local/MemDev；一次性事實不寫。\n"
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
    詞表＝forbidden-phrases.json completion_claim.exclude_patterns（與 claims_completion 同源）。"""
    return bool(last_text) and bool(_COMPLETION_EXCLUDE_RE.search(last_text[-2000:]))


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