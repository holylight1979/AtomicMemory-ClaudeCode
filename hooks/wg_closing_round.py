"""wg_closing_round — 收尾只跑一輪：收尾要問的東西在收尾前最後一個工具回應就送到，AI 第一次寫收尾就一起寫，不再被 Stop 叫回去重寫。

做什麼（每批工具跑完，hooks/handlers/post_tool_batch.py 呼叫 on_batch；判斷交 AI，程式只管時點）：
  這批有收尾檢核（anti_evasion_report；收尾檢核放最後，交了就是交付邊界，一次交齊時知識收割也在裡面）或分開交的
  知識收割回報（knowledge_harvest_report）＝收尾前最後一個工具回應（closing_call），附上
  「順手看到最該修」：該問就附材料、記問過（PICK_ONE_PRE_CLOSE，開關 pick_one.pre_close）；Stop 的 pick_due 看到問過就不再送、
  不再讓對話續跑一輪。交付邊界還有一種：本 session 改過程式之後測試跑綠的那批（pick_on_test_green，post_tool_batch.closing_reminders
  判綠後呼叫、與其他收尾提醒同一條路）——收尾檢核提醒關著（aec.scan_report_gate=false）時 AI 多半不交收尾檢核，那一問就靠這條路送到。
沒走到附著點（沒交收尾檢核、開關關）→ Stop 照舊送（舊送法原處不動）。寫碼守門總開關關、子代理的批次 → 呼叫端不呼叫。
怎麼驗：python -X utf8 -m pytest -q hooks/verify/verify_closing_round.py
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional, Tuple

from wg_core import coding_turn

CLOSING_TOOL_SUFFIX = "__anti_evasion_report"
HARVEST_SUFFIX = "__knowledge_harvest_report"


def pick_pre_close_on(config: Dict[str, Any]) -> bool:
    """開關 pick_one.pre_close（缺＝開；pick_one.enabled 本身要是 true）。"""
    pick = (config or {}).get("pick_one") or {}
    return pick.get("enabled") is True and pick.get("pre_close", True) is not False


def _calls(tool_calls: Any) -> List[Tuple[str, Dict[str, Any]]]:
    out = []
    for c in tool_calls if isinstance(tool_calls, list) else []:
        c = c if isinstance(c, dict) else {}
        inp = c.get("tool_input", c.get("input"))
        out.append((str(c.get("tool_name") or c.get("name") or ""), inp if isinstance(inp, dict) else {}))
    return out


def closing_call(name: str) -> bool:
    """收尾前最後一個工具回應的認法（規則 CLOSING_CALL_ALL_THREE）：收尾檢核（anti_evasion_report，harvest_items 欄帶著知識收割），
    或分開交的知識收割回報（knowledge_harvest_report）。"""
    return name.endswith(CLOSING_TOOL_SUFFIX) or name.endswith(HARVEST_SUFFIX)


def _own(state: Dict[str, Any], sid: str) -> List[Dict[str, Any]]:
    return [m for m in state.get("modified_files") or [] if (m or {}).get("session_id", sid) == sid]


# ─── 收尾前附著：最該修 ─────────────────────────────────────────

def pick_pre_close(state: Dict[str, Any], sid: str, config: Dict[str, Any], input_data: Dict[str, Any],
                   via: str = "pre_close") -> Optional[str]:
    """規則 PICK_ONE_PRE_CLOSE：到了交付邊界那批（via=pre_close：交收尾檢核或完整對照；via=test_green：改過程式之後測試跑綠），
    「順手看到最該修」該問（wg_harvest.pick_due：上次問過或記過之後又改了程式、這個使用者回合還沒問過）就回那一問並記問過
    （wg_harvest.pick_ask，與 Stop 同一段）；不該問、靜音、連鎖警報後只記錄 → None。判斷出錯只 stderr、不送（Stop 照舊會問）。"""
    if not pick_pre_close_on(config) or state.get("muted"):
        return None
    try:
        import chain_store
        from wg_harvest import pick_ask, pick_code_mods, pick_due
        from wg_release_rules import user_turn
        code = pick_code_mods(_own(state, sid), config)
        if not pick_due(state, sid, code, True):
            return None
        if chain_store.record_only(sid, user_turn(state, int(state.get("turn_seq", 0) or 0)), input_data, config):
            print("[Guardian:ChainBreaker] 連鎖中止中：交付邊界不送「順手看到最該修」", file=sys.stderr)
            return None
        cwd = str((state.get("session") or {}).get("cwd") or input_data.get("cwd") or "")
        return pick_ask(state, sid, code, config, cwd, via)
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:PickOne] 交付邊界「最該修」那一問判斷出錯（這次不送，收尾照舊問）：{type(e).__name__}: {e}", file=sys.stderr)
        return None


def pick_on_test_green(state: Dict[str, Any], sid: str, config: Dict[str, Any], input_data: Dict[str, Any]) -> Optional[str]:
    """規則 PICK_ONE_PRE_CLOSE 的另一個交付邊界：本 session 改過程式之後測試跑綠那批（post_tool_batch.closing_reminders 判綠）
    → 同一問。該不該問、記問過都在 pick_pre_close。"""
    text = pick_pre_close(state, sid, config, input_data, via="test_green")
    if text:
        print(text.splitlines()[0], file=sys.stderr)
        return text
    return None


# ─── 入口 ───────────────────────────────────────────────────────────────────────

def on_batch(state: Dict[str, Any], sid: str, input_data: Dict[str, Any], config: Dict[str, Any]) -> Tuple[List[str], bool]:
    """PostToolBatch 每批呼叫 → (要附的段落, state 有沒有改)。判斷出錯只少那一段、浮 stderr（pick_pre_close 自己接住）。"""
    calls = _calls(input_data.get("tool_calls"))
    parts: List[str] = []
    changed = False
    if coding_turn(state, config) and any(closing_call(n) for n, _inp in calls):
        pick = pick_pre_close(state, sid, config, input_data)
        changed = True          # 收尾那批一律寫回：pick_pre_close 記問過會改 state
        if pick:
            print(pick.splitlines()[0], file=sys.stderr)
            parts.append(pick)
    return parts, changed
