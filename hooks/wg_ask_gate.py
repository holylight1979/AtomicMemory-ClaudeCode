"""wg_ask_gate：問使用者之前（AskUserQuestion／ExitPlanMode）的提問閘。

做什麼：蒐集事實（題目、OverviewHub 各部位讀過幾個檔、題目點名的部位）交 wg_release_rules 的兩條規則判——
  ASK_NEEDS_RECOMMENDATION 每一題要附推薦，沒有就欠；ASK_OVERVIEW_BEFORE_DECISION 問改法而還沒讀過部位檔，多一句（不單獨擋）。
  送法照 RULE_MODE：這道閘只在寫碼守門開時跑，開時兩條都是提醒——提問照放行，下一個工具結果附一行（列缺的題目與照抄可過的寫法）。題目全是【收尾放行確認】而且真有待放行紀錄整次豁免。
兩條路：PreToolUse（handlers/pre_tool_use._ask_gate 呼叫 on_ask_full）事前判，處理過的提問記進 state["ask_handled"]；
  PreToolUse 沒處理到的，PostToolBatch（batch_lines）照同一套判斷事後提醒、不擋，並對這批每次提問記一筆審計（擋過幾次）。
開關跟寫碼守門總開關：守門關時 dispatcher 不把這兩個工具送進 PreToolUse（PRE_V6_TOOLS），PostToolBatch 也不跑這段。
帳：Logs/guard-ask.jsonl（ask_no_recommendation、ask_audit、ask_error、remind）。
怎麼驗：python -X utf8 -m pytest -q hooks/verify/verify_ask_gate.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import wg_core
import wg_release
import wg_release_rules as rr

ASK_TOOLS = ("AskUserQuestion", "ExitPlanMode")
RELEASE_LABELS = (wg_release.OPT_RELEASE, wg_release.OPT_KEEP)
ASK_IDS_MAX = 20
GUARD = "ask"
TAG = "[Guardian:Ask]"


def _guard(event: str, sid: Any, turn: Optional[int], **kw: Any) -> None:
    wg_core.append_guard_log(GUARD, {"event": event, "session_id": str(sid or "").split("#agent:")[0],
                                     "turn_seq": turn, **kw})


def _part_reads(state: Dict[str, Any]) -> int:
    """OverviewHub 各部位（含表外目錄）記下的 part_files_read 總數：規則 ASK_OVERVIEW_BEFORE_DECISION 退回判定的事實。"""
    hub = state.get("overview_hub") if isinstance(state, dict) else None
    return sum(len(r.get("part_files_read") or []) for r in (hub or {}).values() if isinstance(r, dict))


def _named_parts(tool_name: str, tool_input: Any, state: Dict[str, Any]) -> List[Tuple[str, str, int]]:
    """題目提到的路徑（rr.ask_paths；相對路徑照 session cwd 解，沒記就用行程 cwd）經 wg_overview.read_scope_keys 對到部位（跟讀檔紀錄同一套鍵），
    每個部位一筆 (題目裡的寫法, 部位名, 該部位 part_files_read 檔數)：規則 ASK_OVERVIEW_BEFORE_DECISION 的事實。
    只看 AskUserQuestion；對不到部位的路徑不列（規則退回總數判定）。"""
    if tool_name != "AskUserQuestion":
        return []
    import wg_overview
    cwd = str((state.get("session") or {}).get("cwd") or "") or os.getcwd()   # state 沒記 session cwd：hook 行程就開在 session 的 cwd
    hub = state.get("overview_hub") if isinstance(state.get("overview_hub"), dict) else {}
    try:
        config = wg_core.load_config()
    except Exception as e:  # noqa: BLE001
        print(f"{TAG} 讀設定失敗，部位對映照預設開關：{type(e).__name__}: {e}", file=sys.stderr)
        config = {}
    out: List[Tuple[str, str, int]] = []
    seen: List[str] = []
    for raw in rr.ask_paths(tool_input):
        p = raw if os.path.isabs(raw) else (os.path.join(cwd, raw) if cwd else "")
        try:   # 這條只是提醒：對映炸了不能讓整個提問被 PreToolUse 外層一律擋，這個路徑當沒對到（規則退回總數判定）
            key = wg_overview.read_scope_keys(os.path.normpath(p), config)[1] if p else None
        except Exception as e:  # noqa: BLE001
            print(f"{TAG} 題目路徑對部位失敗（{raw}，當沒對到）：{type(e).__name__}: {e}", file=sys.stderr)
            key = None
        if not key or key in seen:
            continue
        seen.append(key)
        rec = hub.get(key) if isinstance(hub.get(key), dict) else {}
        out.append((raw, str(rec.get("part") or key.rpartition("|")[2]), len(rec.get("part_files_read") or [])))
    return out


def note_ask_blocked(state: Dict[str, Any], deny: Optional[str]) -> None:
    """PreToolUse 擋了一次提問：累計次數（PostToolBatch 的審計看這個，過得了提問閘之後歸零）。"""
    if deny:
        state["ask_blocks"] = int(state.get("ask_blocks") or 0) + 1


def _audit(sid: Any, state: Dict[str, Any], tool_calls: Any, turn: int) -> None:
    """PostToolBatch：這批每一次提問記一筆審計（擋過幾次）；這題過得了提問閘（附了推薦）就把擋的次數歸零。"""
    for c in tool_calls if isinstance(tool_calls, list) else []:
        name, inp, tid = _call_parts(c)
        if name not in ASK_TOOLS:
            continue
        _guard("ask_audit", sid, turn, tool=name, tool_use_id=tid, blocked=int(state.get("ask_blocks") or 0))
        if name != "AskUserQuestion" or not rr.ask_recommendation_verdict(inp, wg_release.RELEASE_TAG, RELEASE_LABELS).owed:
            state["ask_blocks"] = 0


def _judge_ask(sid: Any, tool_name: str, tool_input: Any, state: Dict[str, Any], after: bool
               ) -> Tuple[Optional[str], Optional[str], List[Dict[str, Any]]]:
    """蒐集事實交 wg_release_rules 的兩條提問規則判，組成擋訊息或提示。有要擋的（事前模式）→ 所有句子併成一則擋訊息；
    否則併成一則提示。事後模式只提示。第三個回傳值＝提醒件清單（規則名、現象、做法、block＝這條本來是擋）：PreToolUse
    拿規則名查 gate_mode 決定照擋還是改提醒（規則 GATE_MODE_TABLE）；判定與文字不因送法而變。"""
    turn = int(state.get("turn_seq", 0) or 0)
    mode = "after" if after else "pre"
    pending = wg_release.pending_any(state, str(sid))
    if (tool_name == "AskUserQuestion" and pending
            and rr.ask_release_only(tool_input, wg_release.RELEASE_TAG, RELEASE_LABELS)):
        return None, None, []
    blocks: List[str] = []
    hints: List[str] = []
    hits: List[Dict[str, Any]] = []
    if tool_name == "AskUserQuestion":
        rec = rr.ask_recommendation_verdict(tool_input, wg_release.RELEASE_TAG, RELEASE_LABELS)
        if rec.owed:
            fix = rr.ask_recommendation_fix(tool_input, wg_release.RELEASE_TAG, RELEASE_LABELS)
            blocks.append(f"{TAG} {rr.format_hit('提問', rec)}\n" + fix)
            hits.append({"rule": rec.rule, "what": rec.why, "fix": fix, "block": True})
            _guard("ask_no_recommendation", sid, turn, tool=tool_name, missing=len(rec.evidence), mode=mode)
    view = rr.ask_overview_verdict(tool_name, tool_input, _part_reads(state), _named_parts(tool_name, tool_input, state))
    if view.owed:
        hints.append(f"{TAG} {rr.format_hit('提問', view)}")
        hits.append({"rule": view.rule, "what": view.why, "fix": "先 Read 題目點名的部位的檔再問改法", "block": False})
    if blocks and not after:
        return "\n\n".join(blocks + hints), None, hits
    return None, "\n\n".join(blocks + hints) or None, hits


def on_ask_full(sid: Any, tool_name: str, tool_input: Any, state: Dict[str, Any]
                ) -> Tuple[Optional[str], Optional[str], List[Dict[str, Any]]]:
    """PreToolUse：回（擋的理由或 None、提示或 None、提醒件清單）。"""
    return _judge_ask(sid, tool_name, tool_input, state, after=False)


def on_ask(sid: Any, tool_name: str, tool_input: Any, state: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """on_ask_full 的前兩個值（擋的理由或 None、提示或 None）。"""
    return _judge_ask(sid, tool_name, tool_input, state, after=False)[:2]


def ask_key(tool_input: Any) -> str:
    """沒有 tool_use_id 時用工具輸入的雜湊對應同一次提問（PreToolUse 與 PostToolBatch 兩邊都算得出來）。"""
    raw = json.dumps(tool_input, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "h:" + hashlib.sha1(raw).hexdigest()[:12]


def mark_asked(state: Dict[str, Any], tool_use_id: str, tool_input: Any) -> None:
    """記下這次提問已處理過（tool_use_id 與輸入雜湊），PreToolUse 處理過的 PostToolBatch 不再事後處理。"""
    seen = [k for k in state.get("ask_handled") or [] if isinstance(k, str)]
    seen += [k for k in (tool_use_id, ask_key(tool_input)) if k and k not in seen]
    state["ask_handled"] = seen[-ASK_IDS_MAX:]


def _call_parts(c: Any) -> Tuple[str, Any, str]:
    c = c if isinstance(c, dict) else {}
    return (str(c.get("tool_name") or c.get("name") or ""), c.get("tool_input", c.get("input")) or {},
            str(c.get("tool_use_id") or c.get("id") or ""))


def has_ask_calls(tool_calls: Any) -> bool:
    return any(_call_parts(c)[0] in ASK_TOOLS for c in (tool_calls if isinstance(tool_calls, list) else []))


def asks_after(sid: Any, state: Dict[str, Any], tool_calls: Any) -> List[str]:
    """事後記錄＋提醒（PostToolBatch）：這批裡 PreToolUse 沒處理過的提問，照 on_ask 同一套判斷，只提醒不擋。"""
    out: List[str] = []
    for c in tool_calls if isinstance(tool_calls, list) else []:
        name, inp, tid = _call_parts(c)
        seen = set(state.get("ask_handled") or [])
        if name not in ASK_TOOLS or (tid and tid in seen) or ask_key(inp) in seen:
            continue
        mark_asked(state, tid, inp)
        _deny, hint, _hits = _judge_ask(sid, name, inp, state, after=True)
        if hint:
            out.append(hint)
    return out


def batch_lines(sid: Any, state: Dict[str, Any], tool_calls: Any) -> List[str]:
    """PostToolBatch：這批有提問 → 沒處理過的事後提醒，每次提問記一筆審計。"""
    if not has_ask_calls(tool_calls):
        return []
    lines = asks_after(sid, state, tool_calls)
    _audit(sid, state, tool_calls, int(state.get("turn_seq", 0) or 0))
    return lines
