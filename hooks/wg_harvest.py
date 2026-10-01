"""wg_harvest.py — 階段完工知識收割（KnowledgeHarvest）的純函式。

誰用：
  - handlers/stop.py：harvest_gate_reason（該不該擋、擋什麼話）、pending_gate_reason、
    vcs_sync_lock_active（SyncReminder 遇 worker 活鎖跳過該 root）。
  - handlers/post_tool_use.py（one-writer）：parse_receipt / record_atom_op（atom 工具收據入帳）、
    validate_items（收割回報逐項核對）、append_ledger。

state 分區（全部按 session_id 分區，防共用工作樹的隔壁 session 誤放行）：
  state["atom_ops"][sid]            = [{seq, turn_seq, op, atom, path, index_ok, ok, supersedes, old_path, new_path}]
  state["knowledge_harvest"][sid]   = {turn_seq, items, pending, validated, retired_paths, at, last_valid_harvest_turn, last_valid_op_seq}
  state["harvest_gate_turn"][sid]   = 本 session 已擋過 KnowledgeHarvest 的 turn
  state["harvest_pending_gate_turn"][sid] = 本 session 已擋過 Harvest-Pending 的 turn
本模組只讀寫傳入的 state dict，不落盤；write_state 由 handler 做。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import _now_iso, WORKFLOW_DIR
from wg_evasion import claims_completion, _DISMISS_RE, _COMPLETION_EXCLUDE_RE
from wg_extraction import _is_pid_alive

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
    sec = section(state, sid)
    return bool(turn_seq) and sec.get("turn_seq") == turn_seq and bool(sec.get("validated"))


def reported_this_turn(state: Dict[str, Any], sid: str, turn_seq: int) -> bool:
    return bool(turn_seq) and section(state, sid).get("turn_seq") == turn_seq


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
    if action == "skip":
        if not str(item.get("reason", "") or "").strip():
            return f"{tag}: 欄位不合格——action=skip 必填 reason"
        return None
    if not atom or not str(item.get("path", "") or "").strip():
        return f"{tag}: 欄位不合格——action={action} 必填 atom 與 path"
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
        "last_valid_op_seq": int(prev.get("last_valid_op_seq", 0) or 0),
    }
    if not pending:
        sec["last_valid_harvest_turn"] = int(turn_seq or 0)
        ops = atom_ops(state, sid)
        sec["last_valid_op_seq"] = int(ops[-1].get("seq", 0)) if ops else sec["last_valid_op_seq"]
    kh[sid] = sec
    return sec


def append_ledger(sid: str, record: Dict[str, Any], base_dir: Optional[Path] = None) -> None:
    """workflow/harvest-ledger/<sid>.jsonl 追加一筆（執行期檔，.gitignore 收）。失敗浮 stderr。"""
    try:
        d = (base_dir or WORKFLOW_DIR) / "harvest-ledger"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / f"{sid}.jsonl", "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[Guardian:Harvest] ledger write failed (fail-open): {e}", file=sys.stderr)


# ─── Stop 閘判定 ──────────────────────────────────────────────────


def _dismissed(recent_prompts: List[str]) -> bool:
    return any(_DISMISS_RE.search(p or "") for p in (recent_prompts or [])[-3:])


def harvest_gate_reason(
    state: Dict[str, Any], sid: str, last_text: str, config: Dict[str, Any],
    own_mod_files: List[Dict[str, Any]], turn_seq: int,
) -> Optional[str]:
    """該擋 KnowledgeHarvest 就回擋訊息，否則 None。純判定，不改 state。

    觸發＝宣告完成 ∧ 近 3 則 prompt 無 dismiss 詞 ∧ 有實質活動（turn_seq ≥ min_turns ∨ 本 session
    有改檔 ∨ accessed_files ≥ min_accessed）∧ 冷卻已過（距上次 validated 收割 ≥ min_turns_between）
    ∧ 本 turn 未回報、未擋過 ∧ 無 pending（pending 由 Harvest-Pending 閘接手，不雙擋）。
    """
    cfg = harvest_config(config)
    if not cfg or not turn_seq:
        return None
    if not last_text or not claims_completion(last_text):
        return None
    if _dismissed(state.get("recent_user_prompts", []) or []):
        return None
    if reported_this_turn(state, sid, turn_seq):
        return None
    if (state.get("harvest_gate_turn") or {}).get(sid) == turn_seq:
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
    last_valid = sec.get("last_valid_harvest_turn")
    if last_valid is not None and turn_seq - int(last_valid) < min_between:
        return None
    return harvest_block_message()


def harvest_block_message() -> str:
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
        "items 欄位：source / summary / action(created|appended|replaced|superseded|retired|skip) / atom / path / scope / reason(skip 必填)。"
        "無東西 → items=[] 照樣呼叫。"
    )


def in_progress_text(last_text: str) -> bool:
    """收尾訊息是中途狀態句（仍在等 agent 回報／尚未開始／整合中途…）→ 不是收尾，閘不該在此刻擋。
    詞表＝forbidden-phrases.json completion_claim.exclude_patterns（與 claims_completion 同源）。"""
    return bool(last_text) and bool(_COMPLETION_EXCLUDE_RE.search(last_text[-2000:]))


def pending_gate_reason(state: Dict[str, Any], sid: str, turn_seq: int, last_text: str = "") -> Optional[str]:
    """本 session 收割回報有核不過的 item → 每 turn 擋一次要求補；使用者說「先這樣／跳過」或
    本則是中途狀態句（還在等別人回報）就不擋——擋了只會逼模型在半途補報。"""
    if not turn_seq:
        return None
    pending = section(state, sid).get("pending") or []
    if not pending:
        return None
    if in_progress_text(last_text):
        return None
    if (state.get("harvest_pending_gate_turn") or {}).get(sid) == turn_seq:
        return None
    if _dismissed(state.get("recent_user_prompts", []) or []):
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