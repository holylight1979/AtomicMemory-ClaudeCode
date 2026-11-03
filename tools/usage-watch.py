#!/usr/bin/env python3
"""usage-watch.py — Claude 用量異常偵測與紀錄：帳號級額度（所有機器／網頁合計）＋本機 transcript 追查是誰在燒。

做什麼：
  【帳號】用 Claude Code 自己的登入 token（~/.claude/.credentials.json）打 api.anthropic.com/api/oauth/usage，
    拿整個帳號的每週％、5 小時窗％與重置時間（只有百分比、沒有 token 數；非公開端點，格式變了會明確報錯）。
    token 過期不自己刷新（會輪替 refresh token、弄壞 Claude Code 登入），只報「開一次 Claude Code 即可」。
    異常定義：
      ① 突增：與最近一筆同週期、間隔 45 分～3h 的紀錄比，每小時漲 ≥ max(--rate-alert, 歷史漲速中位數×3)
      ② 會提早用完：用最近 24h 速度（不足 12h 退回本週平均）推算用完時間早於重置
      ③ 里程碑：每週到 50／75／90％ 各通知一次
      ④ 5 小時窗 ≥ --five-hour-alert％
      日：今日漲幅 ≥ max(--daily-budget, 過去日用量中位數×2)
      週：比上週同一時間點 ≥ --week-factor 倍且多 10 個百分點以上；另列近幾週結算
  【本機】掃 ~/.claude/projects/**/*.jsonl（含 subagents）的 assistant usage，以 (message.id, requestId) 去重，
    主指標「加權 token」＝ input + cache寫入×1.25(5m)/×2(1h) + cache讀取×0.1 + output×5（貼近計費）。
    每小時超過基線 P95 且 ≥ --hour-factor×中位數 → 異常並列專案／session；每日列最多的專案；每週滾動比前幾週。
  【紀錄】（workflow/usage-watch/，不進版控，供日後圖表）
    account.jsonl  每次查詢一行：at, weekly, weekly_reset, five_hour, five_hour_reset, limits{各額度 utilization}
    alerts.jsonl   每次判定出的異常：at, key, msg, notified
    hourly.json    本機每小時×專案：{小時: {專案: [加權, 原始]}}（同格取大，transcript 被清掉也留得住）
    last-run.json  最近一次執行結果（SessionStart 據此提醒排程沒跑、查詢或通知失敗）
    settings.json  {"discord_webhook": "..."}（網址等同發文權限，只放本機）
  【通知】--notify 時新異常跳 Windows 通知，settings.json 有 webhook 就同時發 Discord；
    同一種異常在各自冷卻時間內不重發（突增 3h、預估 6h、日／週 24h、里程碑每週一次）。--test-notify 發一則測試。
  【摘要】--report 把帳號段現況（含當下異常）發到 Discord，不論有沒有異常；手動跑，或用 report 排程每天固定時間發。

怎麼跑：
  python ~/.claude/tools/usage-watch.py                 帳號＋本機
  python ~/.claude/tools/usage-watch.py --account-only  只查帳號（約 1 秒）
  python ~/.claude/tools/usage-watch.py --account-only --report   查帳號並發摘要到 Discord
  python ~/.claude/tools/usage-watch.py --status        各排程的上次／下次執行與最近一次結果
  python ~/.claude/tools/usage-watch.py --register [watch]           註冊每小時監控（--account-only --notify）
  python ~/.claude/tools/usage-watch.py --register report --at HH:MM 註冊每日摘要（--account-only --report，預設 09:00）
  python ~/.claude/tools/usage-watch.py --unregister [watch|report]  移除對應排程（預設 watch）
  完整參數：--help
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import statistics
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# pythonw（Task Scheduler 靜默跑）下 sys.stdout/stderr 為 None → 導到 devnull。
for _name in ("stdout", "stderr"):
    _s = getattr(sys, _name)
    if _s is None:
        setattr(sys, _name, open(os.devnull, "w", encoding="utf-8", newline="\n"))
    elif hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS = CLAUDE_DIR / "projects"
OUT_DIR = CLAUDE_DIR / "workflow" / "usage-watch"
ACCOUNT_LOG = OUT_DIR / "account.jsonl"
ALERT_LOG = OUT_DIR / "alerts.jsonl"
LAST_RUN = OUT_DIR / "last-run.json"
LEDGER = OUT_DIR / "hourly.json"
SETTINGS = OUT_DIR / "settings.json"
USAGE_API = "https://api.anthropic.com/api/oauth/usage"
TASKS = {  # 排程種類 → (排程名, 執行參數)；排程名帶 Windows 帳號，每帳號一份
    "watch": (f"Claude-Usage-Watch-{getpass.getuser()}", "--account-only --notify"),
    "report": (f"Claude-Usage-Report-{getpass.getuser()}", "--account-only --report"),
}
MILESTONES = (50, 75, 90)

TOAST_PS = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$t = $x.GetElementsByTagName('text')
$t.Item(0).AppendChild($x.CreateTextNode($env:UW_TITLE)) | Out-Null
$t.Item(1).AppendChild($x.CreateTextNode($env:UW_BODY)) | Out-Null
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($x))
"""


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            print(f"[warn] {path.name} 有壞行已略過：{ln[:80]}", file=sys.stderr)
    return rows


def append_jsonl(path: Path, rows: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def at(s: dict) -> datetime:
    return datetime.fromisoformat(s["at"])


def alert(key: str, msg: str, window_h: float) -> dict:
    return {"key": key, "msg": msg, "window_h": window_h}


# ---------- 帳號 ----------

def fetch_account(now: datetime) -> dict:
    cred = json.loads((CLAUDE_DIR / ".credentials.json").read_text(encoding="utf-8"))["claudeAiOauth"]
    if cred.get("expiresAt", 0) / 1000 < now.timestamp():
        raise RuntimeError("Claude Code 登入 token 已過期（開一次 Claude Code 會自動刷新），本次略過帳號查詢")
    req = urllib.request.Request(USAGE_API, headers={
        "Authorization": "Bearer " + cred["accessToken"],
        "anthropic-beta": "oauth-2025-04-20",
        "User-Agent": "usage-watch",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode("utf-8"))
    week = d.get("seven_day")
    if not week or "utilization" not in week:
        raise RuntimeError(f"回應裡沒有 seven_day.utilization，端點格式可能變了：{str(d)[:200]}")
    five = d.get("five_hour") or {}
    return {
        "at": now.isoformat(timespec="seconds"),
        "plan": cred.get("rateLimitTier"),
        "weekly": week["utilization"], "weekly_reset": week.get("resets_at"),
        "five_hour": five.get("utilization"), "five_hour_reset": five.get("resets_at"),
        "limits": {k: v["utilization"] for k, v in d.items()
                   if isinstance(v, dict) and v.get("utilization") is not None},
    }


def period_key(s: dict) -> datetime:
    """週期以重置時間（四捨五入到整點）識別；API 每次回的秒數小數會飄。"""
    r = datetime.fromisoformat(s["weekly_reset"]) + timedelta(minutes=30)
    return r.replace(minute=0, second=0, microsecond=0)


def rate_between(prev: dict, cur: dict) -> float | None:
    """每小時漲幾％；跨週期或間隔不在 0.75～3h 回 None。

    API 的％只到整數，間隔太短時差 1％ 就被放大成假突增（23 分鐘 → 2.6%/h 誤差），所以下限 45 分鐘。
    """
    gap = (at(cur) - at(prev)).total_seconds() / 3600
    if period_key(prev) != period_key(cur) or not 0.75 <= gap <= 3:
        return None
    return (cur["weekly"] - prev["weekly"]) / gap


def deltas(samples: list[dict]) -> list[tuple[datetime, float]]:
    """相鄰兩筆之間用掉的％，記在後一筆的時間；跨重置時後一筆的值就是新週期已用量。"""
    out = []
    for p, c in zip(samples, samples[1:]):
        d = c["weekly"] - p["weekly"] if period_key(p) == period_key(c) else c["weekly"]
        out.append((at(c), max(0.0, d)))
    return out


def analyze_account(cur: dict, history: list[dict], now: datetime, a) -> tuple[list[str], list[dict]]:
    samples = history + [cur]
    reset = datetime.fromisoformat(cur["weekly_reset"]).astimezone()
    pk = period_key(cur)
    alerts = []
    lines = [f"  每週 {cur['weekly']:.0f}%（{reset:%m-%d %H:%M} 重置）  方案 {cur['plan']}"]

    # ① 突增
    past_rates = [r for p, c in zip(history, history[1:]) if (r := rate_between(p, c)) is not None and r > 0]
    threshold = max(a.rate_alert, statistics.median(past_rates) * 3) if len(past_rates) >= 10 else a.rate_alert
    # 手動跑會插進間隔很短的筆，往前找最近一筆間隔夠的當比較點
    ref = next((s for s in reversed(history) if rate_between(s, cur) is not None), None)
    rate = rate_between(ref, cur) if ref else None
    if rate is None:
        lines.append("  ① 突增：沒有 3 小時內同週期的上一筆，下次跑才有")
    else:
        flag = rate >= threshold
        lines.append(f"  ① 突增：{rate:+.1f}%/h（門檻 {threshold:.1f}%/h）" + ("  ⚠" if flag else ""))
        if flag:
            alerts.append(alert("rate", f"每週額度一小時漲 {rate:.1f}%", 3))

    # ② 會提早用完
    recent = [s for s in samples if period_key(s) == pk and at(s) >= now - timedelta(hours=24)]
    span_h = (now - at(recent[0])).total_seconds() / 3600
    elapsed_h = (now - (reset - timedelta(days=7))).total_seconds() / 3600
    if span_h >= 12:
        pace, basis = (cur["weekly"] - recent[0]["weekly"]) / span_h, f"最近 {span_h:.0f}h"
    elif elapsed_h >= 12:
        pace, basis = cur["weekly"] / elapsed_h, "本週平均"
    else:
        pace, basis = None, ""
    if pace is None:
        lines.append("  ② 預估：週開始未滿 12h，略過")
    elif pace <= 0:
        lines.append(f"  ② 預估：{basis}沒有增加")
    else:
        eta = now + timedelta(hours=(100 - cur["weekly"]) / pace)
        if eta < reset:
            lines.append(f"  ② 預估：照{basis}速度 {eta:%m-%d %H:%M} 用完，早於重置  ⚠")
            alerts.append(alert("pace", f"照{basis}速度 {eta:%m-%d %H:%M} 用完每週額度", 6))
        else:
            left_h = (reset - now).total_seconds() / 3600
            lines.append(f"  ② 預估：照{basis}速度到重置時約 {cur['weekly'] + pace * left_h:.0f}%")

    # ③ 里程碑（每週期只報最高的那一階，各一次）
    hit = [m for m in MILESTONES if cur["weekly"] >= m]
    if hit:
        alerts.append(alert(f"milestone{hit[-1]}@{pk:%Y%m%d%H}", f"每週額度已用到 {hit[-1]}%", 24 * 8))

    # ④ 5 小時窗
    if cur["five_hour"] is not None:
        fh_reset = datetime.fromisoformat(cur["five_hour_reset"]).astimezone()
        flag = cur["five_hour"] >= a.five_hour_alert
        lines.append(f"  ④ 5 小時窗 {cur['five_hour']:.0f}%（{fh_reset:%H:%M} 重置）" + ("  ⚠" if flag else ""))
        if flag:
            alerts.append(alert("five_hour", f"5 小時窗已 {cur['five_hour']:.0f}%", 3))
    else:
        lines.append("  ④ 5 小時窗：目前沒有啟用中的窗")

    # 日
    by_day = defaultdict(float)
    for t, d in deltas(samples):
        by_day[t.astimezone().date()] += d
    today = now.date()
    past = [v for day, v in by_day.items() if today - timedelta(days=28) <= day < today and v > 0]
    day_thr = max(a.daily_budget, statistics.median(past) * 2) if len(past) >= 5 else a.daily_budget
    flag = by_day[today] >= day_thr
    lines.append(f"  日：今日 {by_day[today]:.0f}%（門檻 {day_thr:.0f}%）、昨日 {by_day[today - timedelta(days=1)]:.0f}%"
                 + ("  ⚠" if flag else ""))
    if flag:
        alerts.append(alert(f"daily@{today}", f"今日已用每週額度 {by_day[today]:.0f}%", 24))

    # 週：上週同期＋結算
    target = now - timedelta(days=7)
    cands = [s for s in history if abs(at(s) - target) <= timedelta(hours=2)]
    if cands:
        lw = min(cands, key=lambda s: abs(at(s) - target))["weekly"]
        flag = lw > 0 and cur["weekly"] >= lw * a.week_factor and cur["weekly"] - lw >= 10
        lines.append(f"  週：上週同期 {lw:.0f}% → 本週 {cur['weekly']:.0f}%" + ("  ⚠" if flag else ""))
        if flag:
            alerts.append(alert("week_vs_last", f"每週額度 {cur['weekly']:.0f}%，上週同期只有 {lw:.0f}%", 24))
    else:
        lines.append("  週：還沒有上週同期紀錄（排程跑滿一週後才有）")
    last_by_period = {}
    for s in samples:
        last_by_period[period_key(s)] = s["weekly"]
    done = [(k, v) for k, v in sorted(last_by_period.items()) if k != pk][-4:]
    if done:
        lines.append("  近幾週結算：" + "  ".join(f"{k - timedelta(days=7):%m-%d} 起 {v:.0f}%" for k, v in done))
    return lines, alerts


def account_check(a, now: datetime) -> tuple[list[str], dict]:
    lines = ["== 帳號額度（所有機器／網頁合計）=="]
    try:
        cur = fetch_account(now)
    except (OSError, urllib.error.URLError, KeyError, ValueError, RuntimeError) as e:
        print(f"[warn] 帳號查詢失敗：{e}", file=sys.stderr)
        return lines + [f"  ✖ 查詢失敗：{e}"], {
            "ok": False, "error": str(e), "alerts": [alert("error", f"帳號用量查詢失敗：{e}", 12)]}
    history = read_jsonl(ACCOUNT_LOG)
    body, alerts = analyze_account(cur, history, now, a)
    append_jsonl(ACCOUNT_LOG, [cur])
    return lines + body, {"ok": True, **cur, "alerts": alerts}


# ---------- 本機 ----------

def merge_ledger(per_hour: dict) -> dict:
    """{hour_dt: {project: [weighted, raw]}} 併進帳本（同格取大），寫回並回傳全部。"""
    ledger = {}
    if LEDGER.exists():
        try:
            ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[warn] 帳本損毀、本次不採用：{LEDGER}（{e}）", file=sys.stderr)
    for h, projs in per_hour.items():
        slot = ledger.setdefault(h.isoformat(), {})
        for p, (w, r) in projs.items():
            old = slot.get(p, [0, 0])
            slot[p] = [max(old[0], w), max(old[1], r)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, sort_keys=True, ensure_ascii=False), encoding="utf-8", newline="\n")
    return {datetime.fromisoformat(k): v for k, v in ledger.items()}


def weighted(u: dict) -> float:
    cc = u.get("cache_creation") or {}
    cc_1h = cc.get("ephemeral_1h_input_tokens", 0) or 0
    cc_5m = (u.get("cache_creation_input_tokens", 0) or 0) - cc_1h
    return ((u.get("input_tokens", 0) or 0)
            + cc_5m * 1.25 + cc_1h * 2
            + (u.get("cache_read_input_tokens", 0) or 0) * 0.1
            + (u.get("output_tokens", 0) or 0) * 5)


def raw_total(u: dict) -> int:
    return sum((u.get(k, 0) or 0) for k in
               ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"))


def scan(since: datetime):
    """回傳 [(local_dt, weighted, raw, project, session)]，已去重。"""
    seen: set = set()
    rows = []
    bad_lines = 0
    since_ts = since.timestamp()
    for f in PROJECTS.rglob("*.jsonl"):
        if f.stat().st_mtime < since_ts:
            continue
        project = f.relative_to(PROJECTS).parts[0]
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"usage"' not in line or '"assistant"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    bad_lines += 1
                    continue
                m = d.get("message") or {}
                u = m.get("usage")
                ts = d.get("timestamp")
                if d.get("type") != "assistant" or not u or not ts:
                    continue
                key = (m.get("id"), d.get("requestId"))
                if key in seen:
                    continue
                seen.add(key)
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
                if dt < since:
                    continue
                rows.append((dt, weighted(u), raw_total(u), project, d.get("sessionId", f.stem)))
    if bad_lines:
        print(f"[warn] {bad_lines} 行 JSON 解析失敗已略過", file=sys.stderr)
    return rows


def percentile(vals: list[float], p: float) -> float:
    s = sorted(vals)
    return s[min(len(s) - 1, int(len(s) * p))]


def fmt(n: float) -> str:
    return f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.0f}K"


def local_check(a, now: datetime) -> tuple[list[str], dict]:
    this_hour = now.replace(minute=0, second=0, microsecond=0)
    since = this_hour - timedelta(days=a.days)
    rows = scan(since)

    per_hour = defaultdict(dict)
    culprits = defaultdict(Counter)
    for dt, w, r, proj, sess in rows:
        h = dt.replace(minute=0, second=0, microsecond=0)
        slot = per_hour[h].setdefault(proj, [0.0, 0])
        slot[0] += w
        slot[1] += r
        culprits[h][f"{proj} / {sess[:8]}"] += w
    merged = merge_ledger(per_hour)
    earliest = min(merged, default=now)
    merged = {h: v for h, v in merged.items() if h >= since}
    hourly = {h: sum(x[0] for x in v.values()) for h, v in merged.items()}
    hourly_raw = {h: sum(x[1] for x in v.values()) for h, v in merged.items()}

    alerts = []
    recent_start = this_hour - timedelta(hours=a.recent_hours - 1)
    baseline = [v for h, v in hourly.items() if h < recent_start and v > 0]
    lines = [f"== 本機每小時（基線 {a.days} 天、{len(baseline)} 個有用量小時；加權 token）=="]
    if len(baseline) < 10:
        lines.append("  基線資料不足（<10 小時），略過小時判定")
    else:
        med = statistics.median(baseline)
        threshold = max(percentile(baseline, 0.95), med * a.hour_factor)
        lines.append(f"  中位數 {fmt(med)}／門檻 {fmt(threshold)}")
        recent = [(h, hourly[h]) for h in sorted(hourly) if h >= recent_start]
        peak = max(recent, key=lambda x: x[1], default=None)
        if peak:
            lines.append(f"  最近 {a.recent_hours}h 最高：{peak[0]:%m-%d %H:00} {fmt(peak[1])}（{peak[1] / med:.1f}× 中位數）")
        for h, w in recent:
            if w <= threshold:
                continue
            alerts.append(alert(f"local-hour@{h:%Y%m%d%H}", f"本機 {h:%m-%d %H:00} 用量為平常 {w / med:.1f}×", 24))
            lines.append(f"  ⚠ {h:%m-%d %H:00}  {fmt(w)}（{w / med:.1f}× 中位數，原始 {fmt(hourly_raw[h])}）")
            for name, cw in culprits[h].most_common(3):
                lines.append(f"      {fmt(cw):>8}  {name}")
        if not any(x["key"].startswith("local-hour") for x in alerts):
            lines.append("  無異常小時")

    daily = defaultdict(Counter)
    for h, projs in merged.items():
        for p, (w, _) in projs.items():
            daily[h.date()][p] += w
    lines.append("== 本機每日（最近 7 天，加權 token）==")
    for i in range(6, -1, -1):
        day = now.date() - timedelta(days=i)
        c = daily.get(day)
        top = f"  最多：{c.most_common(1)[0][0]} {fmt(c.most_common(1)[0][1])}" if c else ""
        lines.append(f"  {day:%m-%d}  {fmt(sum(c.values()) if c else 0):>8}{top}")

    weeks = []
    for i in range(a.days // 7):
        end = this_hour + timedelta(hours=1) - timedelta(days=7 * i)
        start = end - timedelta(days=7)
        weeks.append((sum(v for h, v in hourly.items() if start <= h < end), start >= earliest))
    prev = [w for w, full in weeks[1:] if full and w > 0]
    week_ratio = weeks[0][0] / statistics.mean(prev) if prev else None
    lines.append(f"== 本機每週（滾動 7 天，由近到遠；* = 資料不完整，最早資料 {earliest:%m-%d %H:00}）==")
    lines.append("  " + "  ".join(fmt(w) + ("" if full else "*") for w, full in weeks))
    if week_ratio is None:
        lines.append("  尚無完整的前一週可比（帳本累積滿 14 天後才開始判定）")
    else:
        flag = week_ratio >= a.week_factor
        lines.append(f"  本週 / 前幾週平均 = {week_ratio:.2f}×  → " + ("⚠ 異常升高" if flag else "正常"))
        if flag:
            alerts.append(alert("local-week", f"本機本週用量為前幾週 {week_ratio:.1f}×", 24))
    return lines, {"msgs": len(rows), "weeks": [w for w, _ in weeks], "week_ratio": week_ratio, "alerts": alerts}


# ---------- 通知與排程 ----------

def fresh_alerts(alerts: list[dict], log: list[dict], now: datetime) -> list[dict]:
    """去掉冷卻時間內已通知過的同 key 異常。"""
    sent = {}
    for r in log:
        if r.get("notified"):
            sent[r["key"]] = max(sent.get(r["key"], at(r)), at(r))
    return [x for x in alerts if x["key"] not in sent or now - sent[x["key"]] >= timedelta(hours=x["window_h"])]


def toast(title: str, body: str) -> str | None:
    """跳 Windows 通知；失敗回錯誤字串。"""
    r = subprocess.run(["powershell", "-NoProfile", "-Command", TOAST_PS], capture_output=True, text=True,
                       env={**os.environ, "UW_TITLE": title, "UW_BODY": body},
                       creationflags=subprocess.CREATE_NO_WINDOW)
    return None if r.returncode == 0 else (r.stderr.strip()[:300] or f"exit {r.returncode}")


def discord_post(url: str, text: str) -> str | None:
    """POST 到 Discord webhook；失敗回錯誤字串（不含網址）。"""
    req = urllib.request.Request(url, data=json.dumps({"content": text[:2000]}).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": "usage-watch"})
    try:
        urllib.request.urlopen(req, timeout=15).close()
    except (OSError, urllib.error.URLError) as e:
        return f"Discord 發送失敗：{e}"
    return None


def load_webhook() -> tuple[str | None, str | None]:
    """回傳 (webhook 網址或 None, 錯誤或 None)；沒有 settings.json 不算錯。"""
    if not SETTINGS.exists():
        return None, None
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8")).get("discord_webhook"), None
    except json.JSONDecodeError as e:
        return None, f"settings.json 不可解析：{e}"


def notify(title: str, body: str) -> tuple[bool, dict]:
    """Windows 通知＋Discord（settings.json 有 webhook 才發）；回傳 (至少一個管道送達, {管道: 錯誤})。"""
    errors = {}
    if err := toast(title, body):
        errors["toast"] = err
    url, err = load_webhook()
    if err:
        errors["discord"] = err
    if url and (err := discord_post(url, f"**{title}**\n{body}")):
        errors["discord"] = err
    sent = "toast" not in errors or bool(url and "discord" not in errors)
    return sent, errors


def report_text(now: datetime, acc_lines: list[str], alerts: list[dict]) -> str:
    """--report 的 Discord 訊息：帳號段原樣放 code block，當下異常列在後面。"""
    body = "\n".join(ln.strip() for ln in acc_lines[1:])
    tail = "".join(f"\n⚠ {x['msg']}" for x in alerts)
    return f"📊 **Claude 用量**（{now:%m-%d %H:%M}）\n```\n{body}\n```{tail}"


def _powershell(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)


def schedule(kind: str, register: bool, at: str) -> int:
    """註冊或移除 TASKS[kind]；watch＝每小時（下個整點過 5 分起），report＝每天 at。"""
    name, args = TASKS[kind]
    if not register:
        r = _powershell(f"Unregister-ScheduledTask -TaskName '{name}' -Confirm:$false -ErrorAction Stop")
        if r.returncode != 0:
            print(f"移除 {name} 失敗：{r.stderr.strip()}", file=sys.stderr)
            return 1
        print(f"已移除 {name}")
        return 0
    if kind == "report" and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", at):
        print(f"--at 要是 HH:MM（00:00～23:59），收到 {at!r}", file=sys.stderr)
        return 1
    if kind == "watch":
        trigger, when = ("New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours((Get-Date).Hour + 1).AddMinutes(5) "
                         "-RepetitionInterval (New-TimeSpan -Hours 1)"), "每小時一次"
    else:
        trigger, when = f"New-ScheduledTaskTrigger -Daily -At {at}", f"每天 {at}"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    r = _powershell(f"""
$a = New-ScheduledTaskAction -Execute '{pythonw}' -Argument '"{Path(__file__).resolve()}" {args}'
$t = {trigger}
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName '{name}' -Action $a -Trigger $t -Settings $s -Force | Out-Null
(Get-ScheduledTaskInfo -TaskName '{name}').NextRunTime
""")
    if r.returncode != 0:
        print(f"註冊 {name} 失敗：{r.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"已註冊 {name}：{when}，下次執行 {r.stdout.strip()}")
    return 0


def status() -> int:
    """各排程的上次／下次執行與結果，加上 last-run.json 摘要；watch 沒註冊才算失敗（report 是選用）。"""
    watch_missing = False
    for kind, (name, _) in TASKS.items():
        # 267011 = SCHED_S_TASK_HAS_NOT_RUN（註冊後還沒跑過，LastRunTime 會是 1999 年）
        r = _powershell(f"$i = Get-ScheduledTaskInfo -TaskName '{name}' -ErrorAction Stop; "
                        "$last = if ($i.LastTaskResult -eq 267011) { '尚未執行' } else "
                        "{ '{0:MM-dd HH:mm}（結果 {1}）' -f $i.LastRunTime, $i.LastTaskResult }; "
                        "'上次 ' + $last + '／下次 {0:MM-dd HH:mm}' -f $i.NextRunTime")
        print(f"{name}：{r.stdout.strip() if r.returncode == 0 else f'未註冊（--register {kind}）'}")
        watch_missing |= kind == "watch" and r.returncode != 0
    if LAST_RUN.exists():
        d = json.loads(LAST_RUN.read_text(encoding="utf-8"))
        problems = ([d.get("error")] if not d.get("ok") else []) + list((d.get("notify_errors") or {}).values())
        print(f"最近一次執行 {d.get('at')}：{'；'.join(problems) if problems else '正常'}；"
              f"當下異常 {len(d.get('alerts') or [])} 項")
    else:
        print("還沒有執行紀錄")
    return int(watch_missing)


def main() -> int:
    ap = argparse.ArgumentParser(description="Claude 用量異常偵測：帳號級額度＋本機 transcript")
    ap.add_argument("--account-only", action="store_true", help="只查帳號額度，不掃本機 transcript")
    ap.add_argument("--notify", action="store_true", help="有新異常就跳 Windows 通知＋發 Discord（有設定時）")
    ap.add_argument("--test-notify", action="store_true", help="各通知管道發一則測試訊息後結束")
    ap.add_argument("--report", action="store_true", help="把帳號用量摘要發到 Discord（不論有無異常）")
    ap.add_argument("--status", action="store_true", help="看排程與最近一次執行結果")
    ap.add_argument("--register", nargs="?", const="watch", choices=list(TASKS),
                    help="註冊排程：watch＝每小時監控＋異常通知（預設）、report＝每天 --at 發摘要")
    ap.add_argument("--unregister", nargs="?", const="watch", choices=list(TASKS), help="移除排程（預設 watch）")
    ap.add_argument("--at", default="09:00", help="report 排程每天幾點（HH:MM，預設 09:00）")
    ap.add_argument("--rate-alert", type=float, default=4.0, help="① 突增門檻下限 %%/h（預設 4）")
    ap.add_argument("--five-hour-alert", type=float, default=80.0, help="④ 5 小時窗門檻 %%（預設 80）")
    ap.add_argument("--daily-budget", type=float, default=20.0, help="日用量門檻下限 %%（預設 20，約 5 個工作天用完一週）")
    ap.add_argument("--week-factor", type=float, default=1.5, help="週門檻：帳號比上週同期、本機比前幾週的倍數（預設 1.5）")
    ap.add_argument("--days", type=int, default=28, help="本機基線天數（預設 28）")
    ap.add_argument("--recent-hours", type=int, default=24, help="本機檢查最近幾小時（預設 24）")
    ap.add_argument("--hour-factor", type=float, default=3.0, help="本機小時門檻：≥ 中位數 × 此倍數（預設 3）")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    a = ap.parse_args()
    if a.register or a.unregister:
        return schedule(a.register or a.unregister, bool(a.register), a.at)
    if a.status:
        return status()
    if a.test_notify:
        sent, errors = notify("Claude 用量監控（測試）", "測試訊息：之後有用量異常會這樣通知")
        discord_state = errors.get("discord") or ("OK" if SETTINGS.exists() else "未設定")
        print(f"Windows 通知：{errors.get('toast') or 'OK'}\nDiscord：{discord_state}")
        return 0 if sent and not errors else 1

    now = datetime.now().astimezone()
    acc_lines, acc = account_check(a, now)
    loc_lines, loc = ([], None) if a.account_only else local_check(a, now)
    alerts = acc["alerts"] + (loc["alerts"] if loc else [])

    new = fresh_alerts(alerts, read_jsonl(ALERT_LOG), now)
    notified, notify_errors = False, {}
    if a.notify and new:
        body = "\n".join(f"• {x['msg']}" for x in new)
        if acc["ok"]:
            reset = datetime.fromisoformat(acc["weekly_reset"]).astimezone()
            body += f"\n（目前每週 {acc['weekly']:.0f}%，{reset:%m-%d %H:%M} 重置）"
        notified, notify_errors = notify("Claude 用量異常", body)
        for channel, err in notify_errors.items():
            print(f"[warn] {channel} 通知失敗：{err}", file=sys.stderr)
    if a.report:
        url, err = load_webhook()
        err = err or (discord_post(url, report_text(now, acc_lines, alerts)) if url else "settings.json 沒有 discord_webhook")
        if err:
            notify_errors["discord"] = err
            print(f"[warn] 摘要沒發出去：{err}", file=sys.stderr)
        else:
            print("摘要已發到 Discord")
    stamp = now.isoformat(timespec="seconds")
    append_jsonl(ALERT_LOG, [{"at": stamp, "key": x["key"], "msg": x["msg"], "notified": notified and x in new}
                             for x in alerts])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LAST_RUN.write_text(json.dumps({
        "at": stamp, "ok": acc["ok"], "error": acc.get("error"), "alerts": [x["msg"] for x in alerts],
        "notified": [x["msg"] for x in new] if notified else [], "notify_errors": notify_errors,
    }, ensure_ascii=False), encoding="utf-8", newline="\n")

    if a.json:
        print(json.dumps({"now": stamp, "account": acc, "local": loc}, ensure_ascii=False, default=str))
    else:
        print("\n".join(acc_lines + loc_lines))
        if alerts:
            print("== 異常 ==")
            for x in alerts:
                print(f"  ⚠ {x['msg']}" + ("" if x in new else "（冷卻中，不重複通知）"))

    print(f"USAGE_WATCH DONE account_ok={int(acc['ok'])} alerts={len(alerts)} new={len(new)} "
          f"notified={int(bool(notified and new))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
