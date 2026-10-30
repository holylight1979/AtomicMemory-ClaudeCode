"""transcript_tokens.py — 從 Claude Code transcript 算一場 session 實際處理了多少 token（不換算美金）。

做什麼：
- 找 transcript：給存在的 .jsonl 路徑就用它；否則當 session id（完整或前綴）找
  `claude_config_dir()/projects/*/<前綴>*.jsonl` 與 `projects/_archive/*/<前綴>*.jsonl`，回傳全部命中（0 個或多個由呼叫端判）。
- 子代理：`<transcript 同名資料夾>/subagents/*.jsonl` 一起算。
- 去重：一則 assistant 回覆在 transcript 裡會拆成好幾行、每行帶同一份 usage，用 message.id 只算一次（沒 id 用該行 uuid）；
  逐行加總會重複計算。
- 合計：回覆數、輸入（未快取＋讀快取＋建快取）、輸出、合計；第一筆到最後一筆紀錄的時間 → 分鐘。
怎麼跑：程式 import（find_transcripts、subagent_files、iter_rows、new_usage、session_totals）；
  人用 skills/token/scripts/token_usage.py。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from .project_root import claude_config_dir

SESSION_ID_RE = re.compile(r"^[0-9A-Fa-f-]+$")


def projects_dir() -> Path:
    """Claude Code 存 transcript 的地方：設定目錄底下的 projects/。"""
    return claude_config_dir() / "projects"


def find_transcripts(target: str, root: Optional[Path] = None) -> list[Path]:
    """target 是存在的 .jsonl → [它]；是 session id 或前綴 → projects 底下所有命中（含 _archive）；都不是 → []。"""
    path = Path(target)
    if path.suffix == ".jsonl":
        return [path] if path.is_file() else []
    if not SESSION_ID_RE.match(target):
        return []
    root = root or projects_dir()
    if not root.is_dir():
        return []
    hits = set(root.glob(f"*/{target}*.jsonl")) | set(root.glob(f"_archive/*/{target}*.jsonl"))
    return sorted(hits)


def subagent_files(transcript: Path) -> list[Path]:
    sub = transcript.with_suffix("") / "subagents"
    return sorted(sub.glob("*.jsonl")) if sub.is_dir() else []


def iter_rows(path: Path) -> Iterator[dict]:
    """逐行讀 transcript；空行、壞行、不是物件的行跳過。"""
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def new_usage(row: dict, seen: set) -> Optional[dict]:
    """這行是 assistant 回覆、帶 usage、且這則回覆還沒算過 → 回 usage 並記進 seen；否則回 None。"""
    msg = row.get("message")
    if row.get("type") != "assistant" or not isinstance(msg, dict) or not msg.get("usage"):
        return None
    key = msg.get("id") or row.get("uuid")
    if key in seen:
        return None
    seen.add(key)
    return msg["usage"]


def _timestamp(row: dict) -> Optional[datetime]:
    raw = row.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def session_totals(transcript: Path) -> dict:
    """一場 session（主 transcript＋子代理）的 token 合計與首末時間。"""
    files = [transcript] + subagent_files(transcript)
    tot = {"replies": 0, "input_uncached": 0, "cache_read": 0, "cache_create": 0, "output": 0}
    seen: set = set()
    first = last = None
    for f in files:
        for row in iter_rows(f):
            ts = _timestamp(row)
            if ts is not None:
                first = ts if first is None or ts < first else first
                last = ts if last is None or ts > last else last
            usage = new_usage(row, seen)
            if usage is None:
                continue
            tot["replies"] += 1
            tot["input_uncached"] += usage.get("input_tokens") or 0
            tot["cache_read"] += usage.get("cache_read_input_tokens") or 0
            tot["cache_create"] += usage.get("cache_creation_input_tokens") or 0
            tot["output"] += usage.get("output_tokens") or 0
    tot["input"] = tot["input_uncached"] + tot["cache_read"] + tot["cache_create"]
    tot["total"] = tot["input"] + tot["output"]
    tot["subagent_files"] = len(files) - 1
    tot["first"] = first.isoformat() if first else None
    tot["last"] = last.isoformat() if last else None
    tot["minutes"] = round((last - first).total_seconds() / 60, 1) if first and last else None
    return tot
