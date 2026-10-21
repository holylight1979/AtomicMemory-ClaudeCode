"""wg_hook_timing.py — hook 分段計時與超時降級。

從這個行程建立起算，handler 每跑完一段就打一次點（lap）；累計耗時超過這個事件 hook 上限的 degrade_ratio（預設 80%）
→ 降級：寫一筆 guard log（guard-hook_timing.jsonl，kind=degraded：跑到哪一段、各段耗時）＋stderr 一行，lap 回 True，
呼叫端收到就寫回 state、放行，後面的段落這次不跑（只記不問）。不降級的話，Claude Code 時間一到直接取消 hook：
state 寫不回、閘一個也沒擋、記憶系統這邊什麼訊號都沒有。
每次 hook 結束（不論降級）寫一筆 kind=run，給 tools/hook-timing.py 算各段中位數。
打點只在段落之間；單一段落一路跑過上限時打不到點，所以起表時另排一個背景鬧鐘：到上限的 95% 還沒 finish，
先寫一筆 kind=overrun（卡在哪一段之後、各段耗時）＋stderr，就算接著被取消也留得下訊號。
handler 登記過代送輸出（set_fallback）而正常輸出還沒送（claim_output）時，鬧鐘接著代送那份 stdout 並結束行程——
Claude Code 取消 hook 時已印的輸出也不算數，搶在取消前送出、收掉，最重要的提示才到得了（SessionStart 的追蹤提示、
UserPromptSubmit 已備好的注入）。PreToolUse 不登記：逾時被取消本來就放行，代送放行只是少查。

上限：settings.json 裡這個事件掛 workflow-guardian.py 那支 hook 的 timeout 秒數（有 matcher 的組要對得上工具名）；
資料根（WG_CLAUDE_DIR）沒有 settings.json 時讀程式碼根那份（掛 hook 的就是它）；都讀不到退 config hook_timing.fallback_limit_s。
只計 fallback_limit_s 列到的事件（SessionStart、UserPromptSubmit、PreToolUse、PostToolUse、Stop）。
起點是這個行程的建立時間（Windows 用 GetProcessTimes）；pythonw 啟動器殼本身的時間算不到，所以實際比 Claude Code 的計時略少。
用法：dispatcher 開頭 start(event, input_data, config)、結尾 finish()；handler 在段落邊界 `if lap("段名"): <寫 state、放行>`，
或先 lap 再看 degraded() 決定下一段跑不跑。沒 start 過（單元測試直接呼叫 handler）lap 一律回 False、不記帳。
"""

import json
import os
import re
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from wg_core import CLAUDE_DIR, CODE_DIR, append_guard_log

GUARD = "hook_timing"
ALARM_RATIO = 0.95                                   # 背景鬧鐘：跑到上限的這個比例還沒結束就先留帳
_CUR: Optional["HookTimer"] = None
_OUT_LOCK = threading.Lock()                         # 正常輸出與鬧鐘代送互斥：同一份 stdout 不送兩次
_EXIT = os._exit                                     # 代送後直接結束（不等主執行緒）；測試換掉


class HookTimer:
    def __init__(self, event: str, session_id: str, limit_s: float, limit_src: str, ratio: float, t0: float):
        self.event, self.session_id = event, session_id
        self.limit_s, self.limit_src, self.ratio = limit_s, limit_src, ratio
        self.t0 = self.last = t0
        self.segments: List[List[Any]] = []          # [段名, 毫秒]
        self.degraded_at = ""
        self.alarm: Optional[threading.Timer] = None
        self.fallback: Optional[Callable[[], str]] = None    # 鬧鐘代送的 stdout（handler 登記）
        self.emitted = False                                  # 正常輸出或代送已占位

    def overrun(self) -> None:
        """背景鬧鐘：到上限 95% 還沒 finish（某一段一路跑過頭、打不到點）→ 先留一筆 kind=overrun＋stderr；
        有登記代送、正常輸出還沒送 → 先寫 stdout，寫成了才記 fallback=True、補一筆 run（ended_by=fallback）並結束行程；
        組不出來或寫不出去就不結束，留給主執行緒最後那 5%。"""
        done = self.segments[-1][0] if self.segments else "啟動"
        with _OUT_LOCK:
            sent = False
            if self.fallback and not self.emitted:
                try:
                    text = self.fallback()
                    self.emitted = True                  # 寫到一半失敗也可能已送出部分，不讓主執行緒再送一份
                    sys.stdout.write(text + "\n")
                    sys.stdout.flush()
                    sent = True
                except Exception as e:  # noqa: BLE001
                    print(f"[Guardian:HookTiming] 代送輸出失敗：{type(e).__name__}: {e}", file=sys.stderr)
            print(f"[Guardian:HookTiming] hook 快被取消：{self.event} 已跑 {time.time() - self.t0:.1f} 秒"
                  f"（上限 {self.limit_s:g} 秒的 {ALARM_RATIO:.0%}），卡在「{done}」之後那一段；各段耗時：{self.text()}"
                  + ("；已代送已備好的輸出並結束" if sent else ""), file=sys.stderr)
            rec = self.record("overrun")
            rec["stuck_after"], rec["fallback"] = done, sent
            append_guard_log(GUARD, rec)
            if not sent:
                return
            self.segments.append(["代送", int((time.time() - self.last) * 1000)])
            run = self.record("run")
            run["ended_by"] = "fallback"
            append_guard_log(GUARD, run)
            _EXIT(0)

    def lap(self, name: str) -> bool:
        now = time.time()
        self.segments.append([name, int((now - self.last) * 1000)])
        self.last = now
        if self.degraded_at:
            return True
        if now - self.t0 < self.limit_s * self.ratio:
            return False
        self.degraded_at = name
        print(f"[Guardian:HookTiming] hook 超時降級：{self.event} 跑完「{name}」已 {now - self.t0:.1f} 秒"
              f"（上限 {self.limit_s:g} 秒的 {self.ratio:.0%}），後面的段落這次不跑（只記不問）；各段耗時：{self.text()}",
              file=sys.stderr)
        append_guard_log(GUARD, self.record("degraded"))
        return True

    def text(self) -> str:
        return "、".join(f"{n} {ms}ms" for n, ms in self.segments)

    def record(self, kind: str) -> Dict[str, Any]:
        return {"kind": kind, "event": self.event, "session_id": self.session_id,
                "total_ms": int((time.time() - self.t0) * 1000), "limit_s": self.limit_s, "limit_src": self.limit_src,
                "ratio": self.ratio, "degraded_at": self.degraded_at, "segments": list(self.segments)}


def _process_started() -> float:
    """這個行程的建立時間（epoch 秒）；拿不到就用現在（啟動那段記 0）。"""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = wintypes.HANDLE          # 64 位元的 -1 假 handle，型別不設會被截成 32 位元
            k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
            created, ended, kern, user = (wintypes.FILETIME() for _ in range(4))
            if k32.GetProcessTimes(k32.GetCurrentProcess(), ctypes.byref(created), ctypes.byref(ended),
                                   ctypes.byref(kern), ctypes.byref(user)):
                return ((created.dwHighDateTime << 32) | created.dwLowDateTime) / 1e7 - 11644473600
        except Exception:  # noqa: BLE001
            pass
    return time.time()


def _matcher_hits(matcher: Any, tool_name: str) -> bool:
    """settings.json 的 matcher（工具名 regex，空＝全中）對不對得上；沒工具名（非工具事件）或 regex 壞了都當中。"""
    if not matcher or not tool_name:
        return True
    try:
        return re.fullmatch(str(matcher), tool_name) is not None
    except re.error:
        return True


def settings_limit(event: str, tool_name: str = "") -> Optional[float]:
    """settings.json 裡這個事件（matcher 對得上工具名的組）掛 workflow-guardian.py 的 hook timeout（秒）；
    沒掛、沒寫 timeout 或讀不到回 None。先讀資料根那份，沒檔再讀程式碼根那份。"""
    for path in (CLAUDE_DIR / "settings.json", CODE_DIR / "settings.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            break
        except OSError:
            continue
        except ValueError:
            return None
    else:
        return None
    for group in ((data.get("hooks") or {}).get(event) or []):
        if not _matcher_hits((group or {}).get("matcher"), tool_name):
            continue
        for h in (group or {}).get("hooks") or []:
            if "workflow-guardian.py" in str(h.get("command") or "") and isinstance(h.get("timeout"), (int, float)):
                return float(h["timeout"])
    return None


def start(event: str, input_data: Dict[str, Any], config: Dict[str, Any]) -> Optional[HookTimer]:
    """這個事件要計時就起表（第一段「啟動」＝行程建立到現在：直譯器、載入 wg_core、讀 stdin 與 config）。"""
    global _CUR
    cfg = config.get("hook_timing") or {}
    fallback = (cfg.get("fallback_limit_s") or {}).get(event)
    if not cfg.get("enabled", True) or not fallback:
        _CUR = None
        return None
    limit = settings_limit(event, str(input_data.get("tool_name") or ""))
    _CUR = HookTimer(event, str(input_data.get("session_id") or ""), limit or float(fallback),
                     "settings.json" if limit else "config", float(cfg.get("degrade_ratio", 0.8)), _process_started())
    _CUR.lap("啟動")
    _CUR.alarm = threading.Timer(max(0.0, _CUR.limit_s * ALARM_RATIO - (time.time() - _CUR.t0)), _CUR.overrun)
    _CUR.alarm.daemon = True                     # 不拖住行程結束
    _CUR.alarm.start()
    return _CUR


def lap(name: str) -> bool:
    """這一段跑完；回 True＝已過降級門檻，呼叫端寫回 state 後放行，後面的段落不跑。沒起表回 False。"""
    return _CUR.lap(name) if _CUR else False


def degraded() -> bool:
    """已過降級門檻（某次 lap 回過 True）；不打點。沒起表回 False。"""
    return bool(_CUR and _CUR.degraded_at)


def degrade_note() -> str:
    """降級時送給模型的一行：哪個事件跑完哪段超時、上限多少、帳在哪。沒降級回空字串。"""
    if not degraded():
        return ""
    t = _CUR
    return (f"[Guardian:HookTiming] 這次 {t.event} hook 超時降級（跑完「{t.degraded_at}」已 {time.time() - t.t0:.1f} 秒，"
            f"上限 {t.limit_s:g} 秒）：只送了前面已備好的，後面的段落這次沒跑；各段耗時記在 Logs/guard-hook_timing.jsonl。")


def set_fallback(fn: Callable[[], str]) -> None:
    """登記鬧鐘代送的 stdout（呼叫時才組，拿當下已備好的內容）；沒起表不做事。"""
    if _CUR:
        _CUR.fallback = fn


def claim_output() -> None:
    """正常路徑寫 stdout 前呼叫：占位之後鬧鐘只留帳、不代送（鬧鐘正在代送時這裡等它送完，行程隨即結束）。"""
    with _OUT_LOCK:
        if _CUR:
            _CUR.emitted = True


def finish() -> None:
    """hook 結束：最後一個點到現在記成「其餘」，寫一筆 kind=run。"""
    global _CUR
    timer, _CUR = _CUR, None
    if not timer:
        return
    if timer.alarm:
        timer.alarm.cancel()
    timer.segments.append(["其餘", int((time.time() - timer.last) * 1000)])
    append_guard_log(GUARD, timer.record("run"))
