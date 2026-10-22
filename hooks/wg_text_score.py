"""wg_text_score — 文字評分接到收尾（G15）：Stop 把交付「改了哪些程式」那則回覆與本回合改過的 .md 交背景評分、只留帳。

做什麼：
- Stop（on_stop）：只評本使用者回合改了程式、宣告完成的那一則（TEXT_SCORE_CODE_REPLY_ONLY；text_score.reply_scope=all 退回每則都評），
  去掉空白後不少於 text_score.min_chars（粗篩；精確字數與種類由 tools/text-score.py --auto-kind 判）→ 送評；本 session 這個回合
  改過、還在的 .md 也一起送，text-score 照 text_score.auto_targets.docs 的路徑樣式決定評不評。只寫一個工作檔、起一個背景行程
  （本檔 --job：沒有視窗、脫離 hook）就回，不等裁判、不擋；背景逐份跑 text-score，結果由它留帳 Logs/guard-text_score.jsonl
  （kind＝final_reply／docs、session＝這個 session）。
- UserPromptSubmit（tail_note）：上一回合送評那則評完了 → guard-text_score_tail 記 recorded；還沒評完記 pending。
  評分只記錄：不把「上則評分」送到眼前、不叫 AI 照抄；要看就叫 skill text-score 或查留帳、週彙總。
config 要有 text_score 段且 enabled=true 才做事；enabled=false → 都不做事。出錯只印 stderr，不影響 Stop 與 UserPromptSubmit 其他段。
怎麼跑：Stop／UserPromptSubmit 自動呼叫；背景入口 `python hooks/wg_text_score.py --job <工作檔>` 由 Stop 起，不手動跑。
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from wg_core import CLAUDE_DIR, WORKFLOW_DIR, append_guard_log, rotate_log_if_oversized

TOOL = Path(__file__).resolve().parents[1] / "tools" / "text-score.py"   # 程式碼根（本樹）的評分工具
LEDGER = CLAUDE_DIR / "Logs" / "guard-text_score.jsonl"                  # 與 tools/text-score.py 的 LOG_PATH 同一個檔
JOB_DIR = WORKFLOW_DIR / "text-score"
KEY = "text_score"            # state[KEY][session_id]
TAG = "[Guardian:TextScore]"
SENT_MAX = 50                 # 記得最近幾份送過的（同一份不重送）
LEDGER_TAIL_BYTES = 256_000   # 找評分結果只讀留帳尾段
STALE_S = 86400.0             # 背景中斷留下的工作檔留這麼久（下次送評時清）
_DETACHED = (subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS) if sys.platform == "win32" else 0


def _cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    return (config or {}).get("text_score") or {}


def _on(config: Dict[str, Any]) -> bool:
    return _cfg(config).get("enabled", False) is True


def text_sha(text: str) -> str:
    """跟 text-score 留帳的 text_sha 同算法（sha256 前 16 碼），拿來對回是哪一則。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _turn_docs(mods: List[Dict[str, Any]], session_id: str, turn: int) -> List[str]:
    """本 session 這個回合改過、還在的 .md（路徑樣式交給 text-score 判）。"""
    out = []
    for m in mods:
        m = m or {}
        path = str(m.get("path") or "")
        if m.get("session_id", session_id) != session_id or not path.lower().endswith(".md"):
            continue
        if int(m.get("last_turn_seq") or m.get("turn_seq") or 0) == turn and Path(path).is_file():
            out.append(path)
    return list(dict.fromkeys(out))


def _sweep() -> None:
    cutoff = time.time() - STALE_S
    for p in JOB_DIR.glob("*.json"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


def _spawn_worker(job_path: Path) -> None:
    """起背景行程、不等它：沒有視窗、脫離 hook 行程（hook 結束它照跑）；它的錯誤落 JOB_DIR/worker.log。"""
    kw: Dict[str, Any] = {"creationflags": _DETACHED} if sys.platform == "win32" else {"start_new_session": True}
    log_path = JOB_DIR / "worker.log"
    rotate_log_if_oversized(log_path, max_mb=1, keep=1)
    with open(log_path, "a", encoding="utf-8", newline="\n") as log:
        subprocess.Popen([sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--job", str(job_path)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log, close_fds=True, **kw)


def current_goal(state: Dict[str, Any], session_id: str) -> str:
    """評分要對的當下需求目標：目標樹樹根；沒有樹就用本回合使用者原話（ups_gates 記的 turn_prompts）；都沒有回空字串（不評）。"""
    try:
        import wg_need_goal as ng
        tree = ng.active_tree(ng.load(session_id))
        root = ((tree or {}).get("nodes") or {}).get((tree or {}).get("id")) or {}
        if str(root.get("text") or "").strip():
            return str(root["text"]).strip()
    except Exception as e:  # noqa: BLE001
        print(f"{TAG} 讀不到目標樹，改用本回合原話當目標：{type(e).__name__}: {e}", file=sys.stderr)
    said = [str(p).strip() for p in state.get("turn_prompts") or [] if str(p).strip()]
    return " ".join(said)[:300]


def _reply_in_scope(mine: Dict[str, Any], config: Dict[str, Any], code_reply: bool, user_turn: Optional[int]) -> bool:
    """規則 TEXT_SCORE_CODE_REPLY_ONLY：回覆預設只評交付「改了哪些程式」的那一則（呼叫端判 code_reply＝本使用者回合改了程式、
    這則宣告完成），一個使用者回合最多一則；其他回覆要評由使用者叫（skill text-score）。text_score.reply_scope="all" 退回每則夠長的都評。"""
    if _cfg(config).get("reply_scope", "code_change") == "all":
        return True
    return code_reply and (user_turn is None or mine.get("code_reply_turn") != user_turn)


def on_stop(state: Dict[str, Any], session_id: str, reply: str, mods: List[Dict[str, Any]], turn: int,
            config: Dict[str, Any], *, code_reply: bool = False, user_turn: Optional[int] = None) -> bool:
    """Stop 呼叫：更新「上一則」指標、送評。回 True＝state 改了（呼叫端要寫回）。
    回覆評不評照 _reply_in_scope；回覆與文件都要有當下的需求目標（current_goal：規格對它評；沒有就這次不評）；指標（mine["reply"]）
    指向最近一則送評的回覆（短的碎句不評、不換指標）；送評去重只看 sent，背景起成功才記進 sent，起不來下次 Stop 會再送。"""
    changed = False
    try:
        if not _on(config):
            return False
        mine = state.setdefault(KEY, {}).setdefault(session_id, {})
        changed = False
        sent = list(mine.get("sent") or [])
        tasks: List[Dict[str, str]] = []
        keys: List[str] = []
        floor = int(_cfg(config).get("min_chars") or 0)
        sha = text_sha(reply) if reply else ""
        if sha and len(re.sub(r"\s", "", reply)) >= floor and _reply_in_scope(mine, config, code_reply, user_turn):
            if (mine.get("reply") or {}).get("sha") != sha or mine["reply"].get("turn") != turn:
                mine["reply"] = {"sha": sha, "turn": turn}
                changed = True
            if f"reply:{sha}" not in sent:
                tasks.append({"kind": "final_reply", "text": reply})
                keys.append(f"reply:{sha}")
                mine["code_reply_turn"] = user_turn      # 這個使用者回合評過了（_reply_in_scope 一回合一則）
        for path in _turn_docs(mods, session_id, turn):
            key = f"doc:{path}:{Path(path).stat().st_mtime_ns}"
            if key not in sent:
                tasks.append({"kind": "docs", "path": path})
                keys.append(key)
        if not tasks:
            return changed
        goal = current_goal(state, session_id)
        if not goal:                     # 沒有當下的需求目標（沒樹、本回合也沒原話）可對：這次不評（規格用 {{goal}}）
            return changed
        for t in tasks:
            t["goal"] = goal
        JOB_DIR.mkdir(parents=True, exist_ok=True)
        _sweep()
        job = JOB_DIR / f"{session_id or 'nosession'}-{uuid.uuid4().hex[:8]}.json"
        try:
            job.write_text(json.dumps({"session": session_id, "tasks": tasks}, ensure_ascii=False), encoding="utf-8",
                           newline="\n")
            _spawn_worker(job)
        except Exception:
            job.unlink(missing_ok=True)
            raise
        mine["sent"] = (sent + keys)[-SENT_MAX:]
        return True
    except Exception as e:  # noqa: BLE001  評分只附不擋：出錯不影響收尾
        print(f"{TAG} 收尾送評失敗，這則沒評（下次收尾再送）：{type(e).__name__}: {e}", file=sys.stderr)
        return changed


def find_record(session_id: str, sha: str) -> Optional[Dict[str, Any]]:
    """留帳尾段裡同 session、同文字雜湊、kind=final_reply 的最新一筆。"""
    try:
        with open(LEDGER, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - LEDGER_TAIL_BYTES))
            lines = f.read().decode("utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    for raw in reversed(lines):
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if (isinstance(rec, dict) and rec.get("session") == session_id and rec.get("text_sha") == sha
                and rec.get("kind") == "final_reply"):
            return rec
    return None


def tail_note(state: Dict[str, Any], session_id: str, config: Dict[str, Any], cwd: str = "") -> str:
    """UserPromptSubmit 呼叫（turn_seq 還沒加一）：上一回合送評的回覆評完了 → 留帳 recorded（評分只記錄：
    不再把「上則評分」一行送到眼前、不再叫 AI 照抄），永遠回空字串。還沒評完記 pending。cwd 留著與呼叫端同簽名。"""
    try:
        if not _on(config):
            return ""
        mine = (state.get(KEY) or {}).get(session_id) or {}
        reply = mine.get("reply") or {}
        turn = int(state.get("turn_seq", 0) or 0)
        if not reply.get("sha") or reply.get("done") or reply.get("turn") != turn:
            return ""
        rec = find_record(session_id, reply["sha"])
        if rec is None:
            if not reply.get("pending_logged"):
                reply["pending_logged"] = True
                append_guard_log("text_score_tail", {"event": "pending", "session_id": session_id, "turn_seq": turn,
                                                     "text_sha": reply["sha"]})
            return ""
        reply["done"] = True
        append_guard_log("text_score_tail", {"event": "recorded", "session_id": session_id, "turn_seq": turn,
                                             "text_sha": reply["sha"], "summary": str(rec.get("summary") or "")[:120]})
        return ""
    except Exception as e:  # noqa: BLE001
        print(f"{TAG} 上則評分沒記到：{type(e).__name__}: {e}", file=sys.stderr)
        return ""


# ─── 背景行程：照工作檔逐份評 ─────────────────────────────────────────────────

def _load_tool():
    spec = importlib.util.spec_from_file_location("text_score", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["text_score"] = mod   # dataclass 解析型別註記要找得到模組
    spec.loader.exec_module(mod)
    return mod


def _run_task(tool: Any, task: Dict[str, Any], session: str) -> None:
    """評一份：final_reply 從 stdin 餵、docs 給路徑。出錯（含 argparse 的 SystemExit）只記這份。"""
    argv = ["--auto-kind", str(task.get("kind")), "--session", session, "--tail-line", "--goal", str(task.get("goal") or "")]
    try:
        if task.get("kind") == "final_reply":
            sys.stdin = io.TextIOWrapper(io.BytesIO(str(task.get("text") or "").encode("utf-8")), encoding="utf-8")
            tool.main(["-", *argv])
        else:
            tool.main([str(task.get("path")), *argv])
    except (Exception, SystemExit) as e:  # noqa: BLE001
        print(f"{TAG} {task.get('kind')} {task.get('path') or ''} 評分出錯：{type(e).__name__}: {e}", file=sys.stderr)


def run_job(job_path: Path) -> int:
    """逐份呼叫 text-score 的 main（同一行程，不再起子行程），一份出錯不影響其他份；
    不管成敗都刪工作檔（讀不到、載不到評分工具也刪：留著沒人會再跑它）。"""
    if sys.stderr is None:   # pythonw 沒接上 stderr 時，錯誤照樣落 worker.log
        sys.stderr = open(JOB_DIR / "worker.log", "a", encoding="utf-8", newline="\n")
    try:
        job = json.loads(job_path.read_text(encoding="utf-8"))
        tool = _load_tool()
        for task in job.get("tasks") or []:
            _run_task(tool, task, str(job.get("session") or ""))
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"{TAG} 工作檔 {job_path} 沒評成：{type(e).__name__}: {e}", file=sys.stderr)
        return 2
    finally:
        try:
            job_path.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--job":
        sys.exit(run_job(Path(sys.argv[2])))
    print(__doc__)
    sys.exit(2)
