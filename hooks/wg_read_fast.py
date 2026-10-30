"""wg_read_fast.py — Read 事件的快路徑（規則 READ_FAST_PATH）。

做什麼：settings.json 的 PostToolUse matcher 掛了 Read，AI 每讀一個檔就起一支 hook 行程；走完整 handler 要載 wg_core 等一整串
模組（約 0.3～0.5 秒）。dispatcher 一進門看到 PostToolUse＋Read 就只做這裡的事：把這次讀檔（session、路徑、cwd、時間、結果大小）
追加到 `workflow/read-log-<sid>.jsonl` 就結束，一個重模組都不載。原本靠 Read 的 PostToolUse 做的事（OverviewHub 讀檔帳、
動資料檔讀提示、Depends 召回、工具結果體積、救援命中）
改在下一個非 Read 事件（任何工具的 PreToolUse、非 Read 的 PostToolUse、SessionEnd）先 drain 這份 log、逐筆交給既有函式補帳——
結果一樣、晚一個事件出現；提示隨那個事件的工具結果附上（PreToolUse 補出來的先存 state["read_replay_hints"]，下一個 PostToolUse 送）。
Bash／PowerShell／Grep 的唯讀照走原路徑。寫碼守門關、守門整個關：補帳端照 dispatcher 原本的判法丟掉（Read 本來就不進 handler）。
平行的 Read 同時追加、drain 同時取走：兩邊都握 read-log 的鎖（`read-log-<sid>.lock`），一筆都不互蓋、不漏補。
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
_LOCK_POLL_S = 0.002                                   # read-log 鎖拿不到每 2 ms 再試（握鎖只有追加一行、讀完清檔那一下）
_LOCK_WAIT_S = 2.0                                     # 最多等幾秒


def log_path(session_id: str) -> Path:
    return WORKFLOW_DIR / f"read-log-{session_id}.jsonl"


def _lock(session_id: str):
    """read-log 的鎖（Windows msvcrt 鎖 1 byte、其他平台 fcntl.flock，同 wg_core 的 state 鎖；行程結束系統自動放）。
    要鎖的原因：Windows 的 append 是「移到檔尾、再寫」兩步，平行的 Read 會寫到同一個位置互蓋（8 支行程各追加 300 筆掉三成）；
    drain 改名或清檔時有人正開著檔在寫，那幾筆也會丟。拿不到每 2 ms 再試到 _LOCK_WAIT_S，仍拿不到回 None。"""
    path = log_path(session_id).with_suffix(".lock")
    deadline = time.time() + _LOCK_WAIT_S
    while True:
        fh = None
        try:
            fh = open(path, "ab")
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except OSError:
            if fh is not None:
                fh.close()
        if time.time() >= deadline:
            return None
        time.sleep(_LOCK_POLL_S)


def _unlock(fh, session_id: str) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    fh.close()
    if sys.platform == "win32":    # 同 state 鎖：有人開著就刪不掉＝有人在等；其他平台刪了會讓等的人鎖到另一個檔，留著
        try:
            log_path(session_id).with_suffix(".lock").unlink()
        except OSError:
            pass


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
    """快路徑本體：握 read-log 的鎖追加一行就走。裁判子 session 不記。鎖等不到照樣追加、寫不進去，都只 stderr（可觀測性鐵律），不阻斷。"""
    if os.environ.get("CLAUDE_COMPANION_JUDGE"):
        return
    sid = str(input_data["session_id"])
    line = json.dumps(entry_of(input_data), ensure_ascii=False) + "\n"
    try:
        WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
        fh = _lock(sid)
        if fh is None:
            print("[Guardian:ReadFastPath] read-log 的鎖等不到，這筆照樣追加（同時落檔的 Read 可能互蓋）", file=sys.stderr)
        try:
            with open(log_path(sid), "a", encoding="utf-8", newline="\n") as f:
                f.write(line)
        finally:
            if fh is not None:
                _unlock(fh, sid)
    except OSError as e:
        print(f"[Guardian:ReadFastPath] read-log 寫不進去（這次讀檔不會被補帳）：{e}", file=sys.stderr)


def pending(session_id: str) -> bool:
    """有沒有還沒補帳的 Read（補帳端先問這個，沒有就不多讀 state）。"""
    try:
        return log_path(session_id).stat().st_size > 0
    except OSError:
        return False


def drain(session_id: str) -> List[Dict[str, Any]]:
    """取走並清掉這個 session 累積的 Read（照落檔順序）。握著 read-log 的鎖讀完再刪檔：追加也握同一把鎖，讀到刪之間沒人寫得進來，
    之後才來的 Read 寫進新檔、下次再補；刪不掉（別的程式開著）就截斷。鎖等不到、讀不到或清不掉 → 這次回空、stderr 說一聲，
    帳整份留在檔裡給下一個事件補（不丟、也不重補）。"""
    src = log_path(session_id)
    if not pending(session_id):
        return []
    fh = _lock(session_id)
    if fh is None:
        print("[Guardian:ReadFastPath] read-log 的鎖等不到，這批 Read 留到下一個事件再補帳", file=sys.stderr)
        return []
    try:
        text = src.read_text(encoding="utf-8")
        try:
            src.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            open(src, "w", encoding="utf-8").close()
    except FileNotFoundError:
        return []
    except OSError as e:
        print(f"[Guardian:ReadFastPath] read-log 讀不到或清不掉（這批 Read 留到下一個事件再補帳）：{e}", file=sys.stderr)
        return []
    finally:
        _unlock(fh, session_id)
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
