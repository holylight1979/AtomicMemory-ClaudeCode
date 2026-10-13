"""wg_release.py：Stop 閘擋滿次數後「不自行放行、改問使用者」的純函式。

做什麼：
  擋滿後送固定擋訊息，要模型用 AskUserQuestion 問使用者（題目含【收尾放行確認】、選項固定兩個）。
  放行只認兩種，且都要在「最後一次擋」之後出現：
    (a) transcript 裡 AskUserQuestion 的 tool_result，題目含【收尾放行確認】、答案是「放行這一回合」（同題多次以最後一次為準）；
    (b) 使用者本人新打的訊息整則符合放行句型（is_release_prompt；state.turn_prompts，背景通知等 harness 訊息不進這個清單）。
  (a) 只認 tool_use_id 對到 AskUserQuestion（題目含標記）的 tool_result；其他工具輸出、assistant 文字印出同樣的字都不算。
  「最後一次擋」的位置＝擋那一刻的 transcript 位元組長度＋當時的 turn_prompts 快照（mark_block 記）。
  擋滿記 pending_release，跨回合承接：換回合不重給預算，直到使用者放行或查核通過。
  無法互動（non_interactive_reason：裁判子 session、子代理、headless／SDK）→ 不叫它問，擋到底（non_interactive_message）。
  只用在寫程式碼的查核閘（ReconcileGate／MeasureGate）；其他閘照舊。
怎麼跑：被 handlers/stop.py 匯入；verify 在 hooks/verify/verify_stop_reconcile.py（件一段）。
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

RELEASE_TAG = "【收尾放行確認】"
OPT_RELEASE = "放行這一回合"
OPT_KEEP = "繼續擋，先修好"
# 使用者打字放行：整則訊息（NFKC 正規化全半形、去頭尾空白）必須完全符合；否定、疑問、引用、描述句一律不算
_PROMPT_RELEASE_RE = re.compile(r"^(好|好的|可以|行|OK|ok)?[，,、 ]*放行(這一回合|吧)?[。.!！]*$")


def is_release_prompt(text: str) -> bool:
    return bool(_PROMPT_RELEASE_RE.match(unicodedata.normalize("NFKC", str(text or "")).strip()))
_ANSWER_PAIR_RE = re.compile(r'"([^"]*)"="([^"]*)"')


def exhausted_message(gate: str, n: Optional[int], summary: str) -> str:
    """擋滿後的固定擋訊息。summary 取原因第一行；n＝None 表示承接先前回合的擋滿（pending_release），不報本回合次數。"""
    line = (summary or "").strip().splitlines()[0] if (summary or "").strip() else "（無原因摘要）"
    head = f"本回合已擋 {n} 次仍未解" if n is not None else "先前回合已擋滿、仍未放行也仍未解"
    return (f"[Guardian:{gate}] {head}：{line[:200]}。不准自行放行，也不准改寫宣稱來繞過。"
            f"用 AskUserQuestion 問使用者，題目必須含標記{RELEASE_TAG}，選項固定兩個：「{OPT_RELEASE}」「{OPT_KEEP}」；"
            "使用者選放行才收尾。")


_ENTRY_RE = re.compile(r'"entrypoint"\s*:\s*"([^"]*)"')
_ENTRY_TAIL_BYTES = 65536


def _transcript_entrypoint(transcript_path: Optional[str]) -> str:
    """transcript 尾段最後一筆紀錄的 entrypoint 欄（CC 每筆紀錄都寫）；讀不到回空字串。"""
    if not transcript_path:
        return ""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(max(0, os.path.getsize(transcript_path) - _ENTRY_TAIL_BYTES))
            hits = _ENTRY_RE.findall(f.read().decode("utf-8", errors="replace"))
    except OSError:
        return ""
    return hits[-1] if hits else ""


def non_interactive_reason(input_data: Dict[str, Any], transcript_path: Optional[str],
                           env: Optional[Dict[str, str]] = None) -> Optional[str]:
    """沒有人能回答 AskUserQuestion 的情境 → 回原因（給擋訊息）；有人在 → None。訊號依序：
    ① 環境變數 CLAUDE_COMPANION_JUDGE（裁判子 session；dispatcher 現已整組早退，這裡是第二道）；
    ② hook 輸入是 SubagentStop、或帶 agent_id（官方：子代理內才有）；
    ③ entrypoint 是 sdk-*（`claude -p`／SDK 呼叫）：環境變數 CLAUDE_CODE_ENTRYPOINT 優先（CC 設給子行程，hook 繼承），
       沒有再看 transcript 最後一筆紀錄的 entrypoint 欄。互動入口是 cli／claude-vscode 等，不算。"""
    env = os.environ if env is None else env
    if env.get("CLAUDE_COMPANION_JUDGE"):
        return "裁判子 session（CLAUDE_COMPANION_JUDGE=1）"
    if input_data.get("hook_event_name") == "SubagentStop" or input_data.get("agent_id"):
        return "子代理 Stop"
    ep = str(env.get("CLAUDE_CODE_ENTRYPOINT") or _transcript_entrypoint(transcript_path) or "")
    if ep.startswith("sdk"):
        return f"headless／SDK（entrypoint={ep}）"
    return None


def non_interactive_message(gate: str, n: Optional[int], summary: str, why: str) -> str:
    """無法互動時的固定擋訊息：不叫模型問使用者，一律擋到底。n＝本回合已擋次數（子代理不計預算，給 None 就不寫次數）。"""
    line = (summary or "").strip().splitlines()[0] if (summary or "").strip() else "（無原因摘要）"
    count = f"；本回合已擋 {n} 次" if n is not None else ""
    return (f"[Guardian:{gate}] 無法互動，不能放行：{line[:200]}（{why}{count}）。"
            "不准自行放行，也不准改寫宣稱來繞過：把它修好，或照實回報沒修好。")


def _size(transcript_path: Optional[str]) -> int:
    try:
        return os.path.getsize(transcript_path) if transcript_path else 0
    except OSError:
        return 0


def mark_block(state: Dict[str, Any], sid: str, gate: str, transcript_path: Optional[str], turn_seq: int) -> None:
    """記這個閘（reconcile＝對帳／量尺閘；shared＝吃 stop_gate_max_blocks 的閘）最後一次擋的位置：
    transcript 長度＋turn_prompts 快照＋回合。"""
    prompts = state.get("turn_prompts") if isinstance(state.get("turn_prompts"), list) else []
    state.setdefault("last_block", {}).setdefault(sid, {})[gate] = {
        "offset": _size(transcript_path), "prompts": list(prompts), "turn": int(turn_seq),
    }


def _blocks(o: Dict[str, Any]) -> List[Dict[str, Any]]:
    msg = o.get("message") if isinstance(o.get("message"), dict) else {}
    content = msg.get("content")
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _answers_after(transcript_path: Optional[str], offset: int) -> List[Tuple[str, str]]:
    """offset 之後真的來自 AskUserQuestion 的 (題目, 答案)，依出現順序。
    先從 assistant 的 tool_use 區塊建「tool_use_id → AskUserQuestion 題目」表（只收 input 題目含【收尾放行確認】的那次呼叫），
    再只採用 tool_use_id 對得上的 tool_result：優先讀同一筆紀錄的 toolUseResult.answers，沒有才解析 tool_result 文字。
    Bash／PowerShell／其他工具的輸出、assistant 文字一律不算（印出同樣的字也不算）。"""
    if not transcript_path:
        return []
    try:
        with open(transcript_path, "rb") as f:
            f.seek(max(0, int(offset)))
            raw = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    asked: Dict[str, List[str]] = {}
    out: List[Tuple[str, str]] = []
    for line in raw.splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if not isinstance(o, dict):
            continue
        for b in _blocks(o):
            if b.get("type") == "tool_use" and b.get("name") == "AskUserQuestion":
                qs = [str((q or {}).get("question", "")) for q in ((b.get("input") or {}).get("questions") or [])
                      if isinstance(q, dict)]
                if any(RELEASE_TAG in q for q in qs):
                    asked[str(b.get("id", ""))] = qs
        results = [b for b in _blocks(o) if b.get("type") == "tool_result" and str(b.get("tool_use_id", "")) in asked]
        if not results:
            continue
        qs = asked[str(results[0].get("tool_use_id"))]
        tur = o.get("toolUseResult")
        if isinstance(tur, dict) and isinstance(tur.get("answers"), dict):
            out.extend((str(q), str(a)) for q, a in tur["answers"].items() if str(q) in qs)
            continue
        for b in results:
            text = b.get("content") if isinstance(b.get("content"), str) else ""
            out.extend((q, a) for q, a in _ANSWER_PAIR_RE.findall(text) if q in qs)
    return out


def new_prompts(at_block: Iterable[str], now: Iterable[str]) -> List[str]:
    """turn_prompts 是最多 5 則的滑動窗（新回合會重開）：取 now 裡接在 at_block 之後新進來的那幾則。"""
    old, cur = list(at_block or []), list(now or [])
    for k in range(min(len(old), len(cur)), 0, -1):
        if old[len(old) - k:] == cur[:k]:
            return cur[k:]
    return cur


def user_released(state: Dict[str, Any], sid: str, gate: str, transcript_path: Optional[str]) -> Optional[str]:
    """這個閘最後一次擋之後使用者放行了嗎：回 "ask"（AskUserQuestion 選放行）／"prompt"（使用者打「放行」）／None。
    沒有擋的紀錄（還沒擋過）→ None。"""
    rec = ((state.get("last_block") or {}).get(sid) or {}).get(gate)
    if not isinstance(rec, dict):
        return None
    tagged = [a.strip() for q, a in _answers_after(transcript_path, int(rec.get("offset", 0))) if RELEASE_TAG in q]
    if tagged and tagged[-1] == OPT_RELEASE:
        return "ask"
    now = state.get("turn_prompts") if isinstance(state.get("turn_prompts"), list) else []
    if any(is_release_prompt(p) for p in new_prompts(rec.get("prompts") or [], now)):
        return "prompt"
    return None


def pending_of(state: Dict[str, Any], sid: str, gate: str) -> Optional[Dict[str, Any]]:
    """擋滿後待使用者放行的紀錄（跨回合承接：換了回合也不重給預算）；沒有回 None。"""
    rec = ((state.get("pending_release") or {}).get(sid) or {}).get(gate)
    return rec if isinstance(rec, dict) else None


def pending_any(state: Dict[str, Any], sid: str) -> bool:
    """這個 session 真的有一筆擋滿待放行：同一個閘的 last_block 與 pending_release 都在（光在題目加【收尾放行確認】不算）。"""
    blocks = (state.get("last_block") or {}).get(sid) or {}
    return any(pending_of(state, sid, g) is not None for g in blocks)


CLAIM_CHARS = 3000


def set_pending(state: Dict[str, Any], sid: str, gate: str, turn_seq: int, at: str, reason: str,
                claims: Iterable[str] = ()) -> None:
    """記擋滿待放行。claims＝pending 第一次建立時的「宣告完成」原話（每段尾 CLAIM_CHARS 字）：之後的 Stop 換一句話，
    對帳 (a)(b)(c) 仍拿原話重查；pending 已在時 claims 一律沿用原本那份，之後的文字不附加、不取代、不擠掉。
    舊版 pending（沒有 claims 欄）照舊沒有：無法重查原宣稱，只能由使用者放行清掉（stop.handle_stop 據此擋）。"""
    old = pending_of(state, sid, gate)
    rec: Dict[str, Any] = {"turn": int(turn_seq), "at": at, "reason": (reason or "")[:300]}
    if old is None:
        rec["claims"] = [str(c)[-CLAIM_CHARS:] for c in claims if c]
    elif "claims" in old:
        rec["claims"] = list(old["claims"])
    state.setdefault("pending_release", {}).setdefault(sid, {})[gate] = rec


def clear_pending(state: Dict[str, Any], sid: str, gate: str) -> None:
    sec = (state.get("pending_release") or {}).get(sid)
    if isinstance(sec, dict):
        sec.pop(gate, None)


def released_this_turn(state: Dict[str, Any], sid: str, gate: str, turn_seq: int) -> bool:
    """使用者已放行過這個閘的這一回合（放行一次＝這一回合不再擋）。"""
    return int(((state.get("user_released") or {}).get(sid) or {}).get(gate, -1)) == int(turn_seq)


def record_release(state: Dict[str, Any], sid: str, gate: str, turn_seq: int) -> None:
    state.setdefault("user_released", {}).setdefault(sid, {})[gate] = int(turn_seq)
