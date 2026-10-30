"""wg_read_fast.py — Read 事件的快路徑（規則 READ_FAST_PATH）。

做什麼：settings.json 的 PostToolUse matcher 掛了 Read，AI 每讀一個檔就起一支 hook 行程；走完整 handler 要載 wg_core 等一整串
模組（約 0.3～0.5 秒）。dispatcher 一進門看到 PostToolUse＋Read 就只做這裡的事：把這次讀檔（session、路徑、cwd、時間、結果大小）
追加到 `workflow/read-log-<sid>.jsonl` 就結束，一個重模組都不載。原本靠 Read 的 PostToolUse 做的事（OverviewHub 讀檔帳、
動資料檔讀提示、需求目標讀入範圍、Depends 召回、工具結果體積、救援命中、讀到續接單匯入目標樹）
改在下一個非 Read 事件（任何工具的 PreToolUse、非 Read 的 PostToolUse、SessionEnd）先 drain 這份 log、逐筆交給既有函式補帳——
結果一樣、晚一個事件出現；提示隨那個事件的工具結果附上（PreToolUse 補出來的先存 state["read_replay_hints"]，下一個 PostToolUse 送）。
Bash／PowerShell／Grep 的唯讀照走原路徑。寫碼守門關、守門整個關：補帳端照 dispatcher 原本的判法丟掉（Read 本來就不進 handler）。
本檔只准 import 標準庫與 lib/project_root（資料根的唯一算法）；快路徑的門檻就是「不載 wg_core」。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from project_root import claude_data_dir  # noqa: E402

WORKFLOW_DIR = claude_data_dir() / "workflow"          # 與 wg_core.WORKFLOW_DIR 同一算法；測試各自換
FAST_TOOLS = ("Read",)
HINTS_KEY = "read_replay_hints"                         # PreToolUse 補帳補出來的提示，等下一個 PostToolUse 送
_ERR_HEAD = 200                                        # 讀失敗的回應只留開頭（補帳時只看有沒有錯）


def log_path(session_id: str) -> Path:
    return WORKFLOW_DIR / f"read-log-{session_id}.jsonl"


def is_fast_read(input_data: Dict[str, Any]) -> bool:
    """這個事件走不走快路徑：PostToolUse＋Read＋有 session。裁判子 session（CLAUDE_COMPANION_JUDGE）的 Read 本來就只做最小記帳、
    Read 沒東西可記 → 也走快路徑但不落 log（log_read 看環境變數）。"""
    return (input_data.get("hook_event_name") == "PostToolUse" and input_data.get("tool_name") in FAST_TOOLS
            and bool(input_data.get("session_id")))


def entry_of(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """一筆 log：補帳時 event_of 還原成 handler 吃的事件。tool_response 只留大小（工具結果體積量尺要）與錯誤開頭。"""
    resp = input_data.get("tool_response")
    e: Dict[str, Any] = {
        "t": round(time.time(), 3),
        "sid": str(input_data.get("session_id") or ""),
        "tool_input": input_data.get("tool_input") or {},
        "cwd": input_data.get("cwd", "") or "",
        "transcript_path": input_data.get("transcript_path", "") or "",
    }
    for k in ("agent_id", "tool_use_id"):
        if input_data.get(k):
            e[k] = str(input_data[k])
    if isinstance(resp, str):
        e["error"] = resp[:_ERR_HEAD]
    elif isinstance(resp, dict):
        file_part = resp.get("file")
        if isinstance(file_part, dict) and isinstance(file_part.get("content"), str):
            e["chars"] = len(file_part["content"])
        else:
            e["chars"] = len(json.dumps(resp, ensure_ascii=False))
    return e


def event_of(entry: Dict[str, Any]) -> Dict[str, Any]:
    """log 一筆 → PostToolUse 事件（跟 Claude Code 送來的形狀一樣，只有 tool_response 是等長的替身）。"""
    ev: Dict[str, Any] = {
        "hook_event_name": "PostToolUse", "session_id": entry.get("sid", ""), "tool_name": "Read",
        "tool_input": entry.get("tool_input") or {}, "cwd": entry.get("cwd", ""),
        "transcript_path": entry.get("transcript_path", ""),
    }
    for k in ("agent_id", "tool_use_id"):
        if entry.get(k):
            ev[k] = entry[k]
    if "error" in entry:
        ev["tool_response"] = entry["error"]
    else:
        ev["tool_response"] = {"file": {"content": " " * int(entry.get("chars") or 0)}}
    return ev


def log_read(input_data: Dict[str, Any]) -> None:
    """快路徑本體：追加一行就走。裁判子 session 不記。寫不進去只 stderr（可觀測性鐵律），不阻斷。"""
    if os.environ.get("CLAUDE_COMPANION_JUDGE"):
        return
    try:
        WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
        with open(log_path(str(input_data["session_id"])), "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry_of(input_data), ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[Guardian:ReadFastPath] read-log 寫不進去（這次讀檔不會被補帳）：{e}", file=sys.stderr)


def pending(session_id: str) -> bool:
    """有沒有還沒補帳的 Read（補帳端先問這個，沒有就不多讀 state）。"""
    try:
        return log_path(session_id).stat().st_size > 0
    except OSError:
        return False


def drain(session_id: str) -> List[Dict[str, Any]]:
    """取走並清掉這個 session 累積的 Read（照落檔順序）。先把檔改名再讀：改名之後才來的 Read 會寫進新檔、下次再補；
    平行的 Read 正握著檔在 append 時改名會失敗（Windows 不共享刪除），重試幾次，仍不行就讀完截斷（中間落進來的那幾筆會丟，stderr 說一聲）。"""
    src = log_path(session_id)
    if not pending(session_id):
        return []
    tmp = src.with_suffix(f".{os.getpid()}.replaying")
    moved = False
    for _ in range(5):
        try:
            os.replace(src, tmp)
            moved = True
            break
        except FileNotFoundError:
            return []
        except OSError:
            time.sleep(0.01)
    try:
        if moved:
            text = tmp.read_text(encoding="utf-8")
            tmp.unlink(missing_ok=True)
        else:
            text = src.read_text(encoding="utf-8")
            open(src, "w", encoding="utf-8").close()
            print("[Guardian:ReadFastPath] read-log 改名不了（平行 Read 握著），改成讀完截斷；這一瞬落進來的 Read 可能沒補到帳", file=sys.stderr)
    except OSError as e:
        print(f"[Guardian:ReadFastPath] read-log 讀不到（這批 Read 沒補帳）：{e}", file=sys.stderr)
        return []
    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            print(f"[Guardian:ReadFastPath] read-log 有一行壞掉（跳過）：{line[:80]}", file=sys.stderr)
    return out
