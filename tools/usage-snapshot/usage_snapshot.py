#!/usr/bin/env python3
"""usage_snapshot.py — 每週用量刷新前把 claude.ai 用量頁截圖存檔（Windows 工作排程器驅動）。

做什麼：
  用本工具專屬的 Chrome profile（browser-data/，只登入 claude.ai；日常 Chrome 的 profile 被 Chrome 鎖住、
  且 Chrome 136+ 拒絕在預設 profile 上被自動化，所以不能直接借用）
  開有頭 Chrome 視窗（headless 會被 Cloudflare 人類驗證擋下）到 https://claude.ai/settings/usage，
  等用量條渲染完 → 截圖存到公司共享 SHARE_DIR（//192.168.100.100/暫存區/==公司人員==/holylight/CC-usage）
  的 usage-YYYYMMDD-<帳號>.png（帳號見 ACCOUNT 常數，每台機器一個帳號）；共享連不上就退存本機 workflow/usage-snapshots/ 並在結果標記。
  頁面上的 % / Resets 文字追記到本機 usage-log.jsonl，usage-last-run.json 記最近一次結果（成功／失敗原因）。
  失敗（未登入、逾時、被擋）也會留一張 usage-YYYYMMDD-<帳號>-FAILED.png 供診斷，不靜默。

怎麼跑：
  python tools/usage-snapshot/usage_snapshot.py --login     首次：開有頭視窗，手動登入 claude.ai，登入成功自動關閉
  python tools/usage-snapshot/usage_snapshot.py             截一張（會彈 Chrome 視窗約 30 秒）
  python tools/usage-snapshot/usage_snapshot.py --headless  不彈視窗（實測會被 Cloudflare 擋，留作再試）
  python tools/usage-snapshot/usage_snapshot.py --register  註冊排程：每週二 03:30（喚醒電腦、錯過補跑）
  完整參數：--help
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# pythonw（Task Scheduler 靜默跑）下 sys.stdout/stderr 為 None → 導到 devnull。
for _name in ("stdout", "stderr"):
    _s = getattr(sys, _name)
    if _s is None:
        setattr(sys, _name, open(os.devnull, "w", encoding="utf-8"))
    else:
        _s.reconfigure(encoding="utf-8", errors="replace")

TOOL_DIR = Path(__file__).resolve().parent
PROFILE_DIR = TOOL_DIR / "browser-data"
OUT_DIR = Path.home() / ".claude" / "workflow" / "usage-snapshots"  # 本機：log / last-run / 共享連不上時的截圖退路
SHARE_DIR = Path(r"\\192.168.100.100\暫存區\==公司人員==\holylight\CC-usage")  # 截圖正式落點
LAST_RUN = OUT_DIR / "usage-last-run.json"
LOG = OUT_DIR / "usage-log.jsonl"
USAGE_URL = "https://claude.ai/settings/usage"
TASK_NAME = "Claude-Usage-WeeklySnapshot"
ACCOUNT = "uj_claudeai_5"  # 這台機器登入 claude.ai 的帳號，進檔名
USAGE_TEXT = re.compile(r"\d+%\s*(used|已使用)", re.I)


def log(msg: str) -> None:
    print(f"[usage-snapshot] {msg}", flush=True)


def launch(headed: bool):
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        channel="chrome",
        headless=not headed,
        viewport={"width": 1280, "height": 1000},
        ignore_default_args=["--enable-automation"],
        args=["--disable-blink-features=AutomationControlled"],
    )
    return p, ctx


def usage_visible(page) -> bool:
    try:
        return USAGE_TEXT.search(page.locator("body").inner_text(timeout=3000)) is not None
    except Exception:
        return False


def do_login(timeout_min: int) -> int:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    p, ctx = launch(headed=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(USAGE_URL, wait_until="domcontentloaded")
    log(f"請在跳出的 Chrome 視窗登入 claude.ai（最多等 {timeout_min} 分鐘）；看到用量頁後會自動關閉。")
    deadline = datetime.now().timestamp() + timeout_min * 60
    ok = False
    try:
        while datetime.now().timestamp() < deadline:
            if page.is_closed():
                break
            if usage_visible(page):
                ok = True
                break
            page.wait_for_timeout(2000)
    finally:
        try:
            ctx.close()
        finally:
            p.stop()
    log("登入完成，profile 已保存" if ok else "未偵測到登入完成（視窗被關或逾時）")
    return 0 if ok else 1


def do_snapshot(headed: bool) -> int:  # headed=False 實測被 Cloudflare 擋
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    stamp = now.strftime("%Y%m%d") + "-" + ACCOUNT
    result = {"at": now.isoformat(timespec="seconds"), "ok": False, "file": None, "error": None}
    save_dir = _pick_save_dir(result)
    if not PROFILE_DIR.exists():
        result["error"] = "profile 不存在：先跑 --login"
        _finish(result)
        return 1

    p, ctx = launch(headed)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        page.goto(USAGE_URL, wait_until="domcontentloaded", timeout=60000)
        try:
            page.locator("body").filter(has_text=USAGE_TEXT).wait_for(timeout=45000)
            page.wait_for_timeout(2500)  # 用量條動畫跑完
        except Exception:
            url = page.url
            if "/login" in url or "/magic-link" in url:
                result["error"] = f"未登入（導到 {url}）：重跑 --login"
            else:
                result["error"] = f"45 秒內沒等到用量文字（url={url}, title={page.title()!r}）"
        suffix = "" if result["error"] is None else "-FAILED"
        out = save_dir / f"usage-{stamp}{suffix}.png"
        page.screenshot(path=str(out), full_page=True)
        result["file"] = str(out)
        if result["error"] is None:
            result["ok"] = True
            body = page.locator("body").inner_text()
            lines = [ln.strip() for ln in body.splitlines()
                     if "%" in ln or "Resets" in ln or "重設" in ln]
            result["lines"] = lines
    except Exception as e:  # 瀏覽器層失敗（啟動、導航）
        result["error"] = f"{type(e).__name__}: {e}"
    finally:
        try:
            ctx.close()
        finally:
            p.stop()
    _finish(result)
    return 0 if result["ok"] else 1


def _pick_save_dir(result: dict) -> Path:
    """共享可寫就用共享；不行退本機並把原因記進 result["share_error"]（不靜默）。"""
    try:
        SHARE_DIR.mkdir(parents=True, exist_ok=True)
        probe = SHARE_DIR / ".write-test"
        probe.touch()
        probe.unlink()
        return SHARE_DIR
    except OSError as e:
        result["share_error"] = f"共享寫不進（{e.strerror or e}），退存本機 {OUT_DIR}"
        return OUT_DIR


def _finish(result: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LAST_RUN.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
    if result["ok"]:
        log(f"OK → {result['file']}")
        if result.get("share_error"):
            log(f"WARN: {result['share_error']}")
        for ln in result.get("lines", []):
            log(f"  {ln}")
    else:
        log(f"FAILED: {result['error']}" + (f" → {result['file']}" if result["file"] else ""))


def do_register(at: str, day: str) -> int:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    script = str(Path(__file__).resolve())
    ps = f"""
$a = New-ScheduledTaskAction -Execute '{pythonw}' -Argument '"{script}"'
$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek {day} -At {at}
$s = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $a -Trigger $t -Settings $s -Force | Out-Null
(Get-ScheduledTaskInfo -TaskName '{TASK_NAME}').NextRunTime
"""
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    if r.returncode != 0:
        log(f"註冊失敗：{r.stderr.strip()}")
        return 1
    log(f"已註冊 {TASK_NAME}：每週 {day} {at}，下次執行 {r.stdout.strip()}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--login", action="store_true", help="開有頭視窗手動登入 claude.ai（一次性）")
    ap.add_argument("--login-timeout", type=int, default=60, metavar="MIN", help="--login 最多等幾分鐘（預設 60）")
    ap.add_argument("--headless", action="store_true", help="不彈視窗（實測會被 Cloudflare 擋）")
    ap.add_argument("--register", action="store_true", help="註冊 Windows 排程")
    ap.add_argument("--at", default="03:30", help="--register 的時間 HH:MM（預設 03:30）")
    ap.add_argument("--day", default="Tuesday", help="--register 的星期（預設 Tuesday）")
    a = ap.parse_args()
    if a.register:
        return do_register(a.at, a.day)
    if a.login:
        return do_login(a.login_timeout)
    return do_snapshot(headed=not a.headless)


if __name__ == "__main__":
    sys.exit(main())
