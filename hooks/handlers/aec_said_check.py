"""aec_said_check.py — 收尾報告「你說」核對：AI 在 goal[].said 抄的原話，拿主對話紀錄裡使用者本人打的字比。

只加記號、不擋、不退回、不改嚴重度；守門開關都跑。PostToolUse 收 anti_evasion_report 時呼叫 annotate(report, input_data)：
  - 每個 goal[i] 加 said_check（值只有這六種）：
      本回合        在本回合使用者打的字裡找得到
      第 N 回合前   在更早的使用者訊息裡找得到（N＝往前幾個使用者回合）
      派工          只在派工說明裡找得到（子代理紀錄第一則＝交給它的任務；同伴 session 傳來的訊息）
      對不到        都找不到
      太短不判      正規化後少於 6 字
      判不了        沒有 transcript、讀紀錄失敗（stderr 留一行）
    said 開頭的「派工：」只是 AI 標的來源，比之前拿掉；不管有沒有標，都先找使用者的話、再找派工說明。
  - report["user_said_this_turn"]：本回合使用者打的原話（每則一個字串，全文、剔系統區塊、保留換行），給 HUD 對照
    AI 有沒有漏列使用者要的事。讀不到紀錄就不寫這個欄位。

使用者打的字（只認主檔；子代理檔裡的 user 訊息是 AI 寫給它的任務）：
  - 真人訊息（lib/provenance.is_human_record）＝開一個使用者回合；
  - AI 做事中途使用者插話＝queued_command 附件、origin.kind=human，算進當下那個回合（實查：這種不會另存成真人訊息）；
  - 兩種都只取 user_typed_text（剔 harness 區塊）。
本回合：主 session＝最後一個使用者回合；子代理＝派它的那一回合（子代理檔第一則的 promptId 對到主檔的那則紀錄；
  對不到就當最後一個），之後的回合子代理看不到，不拿來比。

比對：兩邊同一套 normalize——全形半形統一（NFKC）、去清單符號與引號、空白換行折一格，再去掉不夾在兩個英數字中間的空格
  （中文換行改成空格或拿掉都對得上）。said 有「…」或「...」就切段，每段都要在同一則訊息裡找得到（順序不拘）；
  只抄一則訊息的其中一段算找得到。
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from typing import Any, Dict, List, Tuple

from wg_core import CODE_DIR, transcripts_of, user_typed_text

MIN_CHARS = 6

_CIRCLED_NUM_RE = re.compile(r"[①-⑳⑴-⒇⒈-⒛]")   # ①～⑳、⑴～⒇、⒈～⒛（NFKC 會變成裸數字，先拿掉）
_LIST_MARK_RE = re.compile(r"(?m)(?:^|(?<=\s))(?:[-*+•·‧▪◦●○■□>]+(?=\s)|\d{1,3}[.)、](?!\d)|\(\d{1,3}\))")
_QUOTES_RE = re.compile(r"[「」『』“”‘’\"'〝〞`]")
_SPACE_RE = re.compile(r"\s+")
_LONE_SPACE_RE = re.compile(r" (?![A-Za-z0-9])|(?<![A-Za-z0-9]) ")
_ELLIPSIS_RE = re.compile(r"[\[(【]?(?:\.{3,}|⋯+)[\])】]?")   # NFKC 之後「…」已是「...」；「[…]」「（…）」整個當省略
_DISPATCH_PREFIX_RE = re.compile(r"^\s*派工\s*[:：]\s*")


def normalize(text: str) -> str:
    s = unicodedata.normalize("NFKC", _CIRCLED_NUM_RE.sub(" ", text or ""))
    s = _QUOTES_RE.sub("", _LIST_MARK_RE.sub(" ", s))
    return _LONE_SPACE_RE.sub("", _SPACE_RE.sub(" ", s)).strip()


def said_segments(said: str) -> List[str]:
    """said 拿掉「派工：」，依省略號切段、各段 normalize，丟掉空段。"""
    body = unicodedata.normalize("NFKC", _CIRCLED_NUM_RE.sub(" ", _DISPATCH_PREFIX_RE.sub("", said or "")))
    return [seg for seg in (normalize(p) for p in _ELLIPSIS_RE.split(body)) if seg]


def _blocks_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def read_sources(transcript_path: str, agent_id: str) -> Tuple[List[List[str]], int, List[str]]:
    """→ (使用者回合清單（舊→新，每回合是使用者打的字的清單）, 本回合在清單裡的位置（沒有回合 -1）, 派工說明清單)。
    主檔不存在或讀不了 → OSError（呼叫端標「判不了」）。"""
    if str(CODE_DIR) not in sys.path:
        sys.path.insert(0, str(CODE_DIR))
    from lib.provenance import is_human_record, record_text

    main, files = transcripts_of(transcript_path, agent_id)
    if not main:
        raise OSError("hook 輸入沒有 transcript_path")
    dispatch: List[str] = []
    prompt_id = None
    if len(files) > 1:   # 子代理：第一則是交給它的任務，promptId 指回主檔派它的那一回合
        with open(files[1], encoding="utf-8", errors="replace") as fh:
            first = json.loads(fh.readline() or "null")
        if isinstance(first, dict):
            dispatch.append(_blocks_text((first.get("message") or {}).get("content")))
            prompt_id = first.get("promptId") or None
    turns: List[List[str]] = []
    current = None
    with open(main, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"user"' not in line and "queued_command" not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            att = rec.get("attachment") if rec.get("type") == "attachment" else None
            if isinstance(att, dict) and att.get("type") == "queued_command":
                kind = (att.get("origin") or {}).get("kind")
                text = _blocks_text(att.get("prompt"))
            elif rec.get("type") == "user" and not rec.get("isSidechain"):
                kind = "human" if is_human_record(rec) else (rec.get("origin") or {}).get("kind")
                text = record_text(rec) if kind == "human" else _blocks_text((rec.get("message") or {}).get("content"))
            else:
                continue
            if kind == "peer":
                dispatch.append(text)
            elif kind == "human":
                typed = user_typed_text(text, keep_lines=True)
                if typed and (att is None or not turns):   # 真人訊息開新回合；中途插話接在當下那回合
                    turns.append([typed])
                elif typed:
                    turns[-1].append(typed)
            if prompt_id and current is None and rec.get("type") == "user" and rec.get("promptId") == prompt_id:
                current = len(turns) - 1
    return turns, (len(turns) - 1 if current is None else current), [d for d in dispatch if d.strip()]


def check_said(said: str, turns_norm: List[List[str]], current: int, dispatch_norm: List[str]) -> str:
    segs = said_segments(said)
    if len("".join(segs)) < MIN_CHARS:
        return "太短不判"

    def hit(texts: List[str]) -> bool:
        return any(all(seg in t for seg in segs) for t in texts)

    for back in range(current + 1):
        if hit(turns_norm[current - back]):
            return "本回合" if back == 0 else f"第 {back} 回合前"
    return "派工" if hit(dispatch_norm) else "對不到"


def annotate(report: Dict[str, Any], input_data: Dict[str, Any]) -> None:
    """就地替 report["goal"] 每項加 said_check，並寫 report["user_said_this_turn"]。任何失敗只標「判不了」＋ stderr，不丟例外。"""
    goals = [g for g in report.get("goal") or [] if isinstance(g, dict)]
    try:
        turns, current, dispatch = read_sources(str(input_data.get("transcript_path") or ""),
                                                str(input_data.get("agent_id") or ""))
    except Exception as e:   # 讀不到紀錄：太短的照標太短，其餘判不了；hook 照跑
        print(f"[Guardian:AEC-Said] 讀不到對話紀錄，「你說」標判不了：{type(e).__name__}: {e}", file=sys.stderr)
        for g in goals:
            g["said_check"] = "太短不判" if len("".join(said_segments(g.get("said", "")))) < MIN_CHARS else "判不了"
        return
    turns_norm = [[normalize(t) for t in turn] for turn in turns[:current + 1]]
    dispatch_norm = [normalize(d) for d in dispatch]
    for g in goals:
        g["said_check"] = check_said(g.get("said", ""), turns_norm, current, dispatch_norm)
    report["user_said_this_turn"] = turns[current] if current >= 0 else []
