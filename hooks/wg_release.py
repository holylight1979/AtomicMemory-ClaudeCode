"""wg_release.py：Stop 閘擋滿次數後「不自行放行、改問使用者」的純函式。

做什麼：
  擋滿後送固定擋訊息，要模型用 AskUserQuestion 問使用者（題目含【收尾放行確認】、選項固定兩個）。
  放行只認兩種，且都要在「最後一次擋」之後出現：
    (a) transcript 裡 AskUserQuestion 的 tool_result，題目含【收尾放行確認】、答案是「放行這一回合」（同題多次以最後一次為準）；
    (b) 使用者本人新打的訊息含「放行」（state.turn_prompts；背景通知等 harness 訊息本來就不進這個清單；「不放行」類否定不算）。
  「最後一次擋」的位置＝擋那一刻的 transcript 位元組長度＋當時的 turn_prompts 快照（mark_block 記）。
怎麼跑：被 handlers/stop.py 匯入；verify 在 hooks/verify/verify_stop_reconcile.py（件一段）。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

RELEASE_TAG = "【收尾放行確認】"
OPT_RELEASE = "放行這一回合"
OPT_KEEP = "繼續擋，先修好"
_PROMPT_RELEASE_RE = re.compile(r"(?<![不別勿])(?<!不要)(?<!不准)(?<!不能)放行")
_ANSWER_PAIR_RE = re.compile(r'"([^"]*)"="([^"]*)"')


def exhausted_message(gate: str, n: int, summary: str) -> str:
    """擋滿後的固定擋訊息。summary 取原因第一行。"""
    line = (summary or "").strip().splitlines()[0] if (summary or "").strip() else "（無原因摘要）"
    return (f"[Guardian:{gate}] 本回合已擋 {n} 次仍未解：{line[:200]}。不准自行放行，也不准改寫宣稱來繞過。"
            f"用 AskUserQuestion 問使用者，題目必須含標記{RELEASE_TAG}，選項固定兩個：「{OPT_RELEASE}」「{OPT_KEEP}」；"
            "使用者選放行才收尾。")


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


def _answers_after(transcript_path: Optional[str], offset: int) -> List[Tuple[str, str]]:
    """offset 之後 AskUserQuestion 的 (題目, 答案)，依出現順序。優先讀 toolUseResult.answers，沒有就解析 tool_result 文字。"""
    if not transcript_path:
        return []
    try:
        with open(transcript_path, "rb") as f:
            f.seek(max(0, int(offset)))
            raw = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    out: List[Tuple[str, str]] = []
    for line in raw.splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if not isinstance(o, dict):
            continue
        tur = o.get("toolUseResult")
        if isinstance(tur, dict) and isinstance(tur.get("answers"), dict):
            out.extend((str(q), str(a)) for q, a in tur["answers"].items())
            continue
        content = (o.get("message") or {}).get("content") if isinstance(o.get("message"), dict) else None
        for b in content if isinstance(content, list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                text = b.get("content") if isinstance(b.get("content"), str) else ""
                out.extend(_ANSWER_PAIR_RE.findall(text))
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
    if any(_PROMPT_RELEASE_RE.search(str(p)) for p in new_prompts(rec.get("prompts") or [], now)):
        return "prompt"
    return None


def released_this_turn(state: Dict[str, Any], sid: str, gate: str, turn_seq: int) -> bool:
    """使用者已放行過這個閘的這一回合（放行一次＝這一回合不再擋）。"""
    return int(((state.get("user_released") or {}).get(sid) or {}).get(gate, -1)) == int(turn_seq)


def record_release(state: Dict[str, Any], sid: str, gate: str, turn_seq: int) -> None:
    state.setdefault("user_released", {}).setdefault(sid, {})[gate] = int(turn_seq)
