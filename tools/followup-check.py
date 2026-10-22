#!/usr/bin/env python3
"""followup-check.py — 回訪檢查器：到期後由 SessionStart 自動跑，把「改了東西一週後看數據」變成程式判定。

登記表 workflow/followups.json：
  {"followups": [{"id", "title", "due": "YYYY-MM-DD", "since": "YYYY-MM-DD",
                  "check": "<檢查名>", "criteria": {...}, "context": "<一句：改了什麼、為何回訪>",
                  "done": false, "owner": "<帳號>", "host": "<電腦代號>"}]}
  owner／host 選填：有填就要對上這個帳號（getpass.getuser，不分大小寫）／這台電腦才跑、才在開場顯示；沒填＝每個人每台都看。
  host 存電腦代號（電腦名小寫後 sha256 的前 12 碼，`--host-id` 印這台的），登記表不存電腦名原文。
  只對某台機器有意義的回訪（量測腳本只在那台）標 host。
執行期紀錄（last_shown／result、--auto-close 的 done／done_at）寫登記表旁的 followups.local.json（這台機器的、不進版控），
讀的時候疊在登記表上；登記表只在 --add、--done（人刻意改登記）時寫。

用法：
  python tools/followup-check.py --list                 列出全部（含未到期）
  python tools/followup-check.py --run [--force]        跑所有到期未結案、屬於這個人這台機器的項（--force 忽略到期日）
  python tools/followup-check.py --run --auto-close     PASS 者自動標 done
  python tools/followup-check.py --run --brief --mark-shown   SessionStart 用：精簡輸出 + 記錄今日已提醒
  python tools/followup-check.py --done <id>            手動結案
  python tools/followup-check.py --add <json>           登記一筆（JSON 物件字串）
  python tools/followup-check.py --host-id              印這台電腦的代號（登記 host 欄用）

檢查名（check）現有：
  injection-budget — 讀 Logs/injection-turns.jsonl（since 起）算 全文/回合、熱 atom 全文率；
                     讀 Logs/atom-debug-*.log 算 final-trim dropped/回合；
                     讀 memory-effect-report.collect 的 exposure_tax 顆數。
狀態：PASS（全過）/ FAIL（有未過）/ INSUFFICIENT（樣本回合數 < criteria.min_turns）。
"""
from __future__ import annotations

import argparse
import getpass
import glob
import hashlib
import json
import platform
import re
import sys
from datetime import date, datetime
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent   # 程式碼根（本檔所在的樹）
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
from lib.project_root import claude_data_dir  # noqa: E402
CLAUDE_DIR = claude_data_dir()   # 使用者資料根（WG_CLAUDE_DIR 或 ~/.claude），和 hooks 同一支算法
FOLLOWUPS = CLAUDE_DIR / "workflow" / "followups.json"
INJECTION_TURNS_LOG = CLAUDE_DIR / "Logs" / "injection-turns.jsonl"
ATOM_DEBUG_GLOB = str(CLAUDE_DIR / "Logs" / "atom-debug-*.log")


# ─── 登記表 IO ───────────────────────────────────────────────────────────────

def load() -> dict:
    if not FOLLOWUPS.exists():
        return {"followups": []}
    try:
        return json.loads(FOLLOWUPS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"followups": []}


def save(data: dict) -> None:
    FOLLOWUPS.parent.mkdir(parents=True, exist_ok=True)
    FOLLOWUPS.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


RUNTIME_KEYS = ("last_shown", "result", "done", "done_at")


def _runtime_path() -> Path:
    return FOLLOWUPS.with_name("followups.local.json")   # 跟著登記表走：測試把登記表換到暫存目錄，本機紀錄也跟著換


def load_runtime() -> dict:
    """這台機器的執行期紀錄 {id: {last_shown, result, done, done_at}}；沒有回 {}，讀壞了 stderr 一行、當成沒有。"""
    p = _runtime_path()
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        print(f"[followup] {p} 讀不了，當成沒有本機紀錄：{e}", file=sys.stderr)
        return {}
    return d if isinstance(d, dict) else {}


def save_runtime(rt: dict) -> None:
    p = _runtime_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rt, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def merged(item: dict, rt: dict) -> dict:
    """登記項疊上這台機器的執行期紀錄。"""
    rec = rt.get(item.get("id")) or {}
    return {**item, **{k: v for k, v in rec.items() if k in RUNTIME_KEYS}}


def _d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def is_due(item: dict, today: date | None = None) -> bool:
    today = today or date.today()
    try:
        return not item.get("done") and _d(item["due"]) <= today
    except (KeyError, ValueError):
        return False


def host_id(name: str) -> str:
    """電腦代號：電腦名小寫後 sha256 的前 12 碼（登記表的 host 欄存這個，不存電腦名原文）。"""
    return hashlib.sha256(name.lower().encode("utf-8")).hexdigest()[:12]


def _me() -> dict:
    return {"owner": getpass.getuser(), "host": host_id(platform.node())}


def for_me(item: dict, me: dict | None = None) -> bool:
    """owner／host 有填的要對上目前的帳號／電腦代號才算這個人這台機器的回訪；沒填＝人人都看。"""
    me = me or _me()
    return all(not item.get(k) or str(item[k]).casefold() == str(v).casefold() for k, v in me.items())


# ─── 檢查：injection-budget ─────────────────────────────────────────────────

def _load_turns(since: date) -> list[dict]:
    out: list[dict] = []
    if not INJECTION_TURNS_LOG.exists():
        return out
    for line in INJECTION_TURNS_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if datetime.fromisoformat(rec["at"]).date() >= since:
                out.append(rec)
        except (ValueError, KeyError, TypeError):
            continue
    return out


def _count_dropped_since(since: date) -> int:
    """atom-debug log 中 final-trim form=dropped 行數（since 起，依檔名日期粗篩）。"""
    n = 0
    for p in glob.glob(ATOM_DEBUG_GLOB):
        m = re.search(r"atom-debug-(\d{4}-\d{2}-\d{2})", p)
        if not m or _d(m.group(1)) < since:
            continue
        try:
            for line in Path(p).read_text(encoding="utf-8", errors="replace").splitlines():
                if "final-trim" in line and "form=dropped" in line:
                    n += 1
        except OSError:
            continue
    return n


def check_injection_budget(item: dict) -> dict:
    c = item.get("criteria", {})
    since = _d(item["since"])
    turns = _load_turns(since)
    n = len(turns)
    min_turns = int(c.get("min_turns", 10))
    rows: list[dict] = []
    if n < min_turns:
        return {"status": "INSUFFICIENT", "turns": n, "min_turns": min_turns, "rows": rows}

    full = sum(int(t.get("ok", 0)) for t in turns)
    hot = full + sum(int(t.get("fallback", 0)) + int(t.get("skip", 0)) for t in turns)
    fpt = full / n
    fr = (full / hot) if hot else 0.0
    dropped_pt = _count_dropped_since(since) / n

    def row(name, value, op, thr, fmt="{:.2f}"):
        ok = (value >= thr) if op == ">=" else (value <= thr)
        rows.append({"name": name, "value": fmt.format(value), "threshold": f"{op} {fmt.format(thr)}", "ok": ok})

    row("全文/回合", fpt, ">=", float(c.get("full_per_turn_min", 2.5)))
    row("熱 atom 全文率", fr, ">=", float(c.get("full_rate_min", 0.55)))
    row("final-trim dropped/回合", dropped_pt, "<=", float(c.get("dropped_per_turn_max", 1.0)))

    tax = None
    try:
        sys.path.insert(0, str(CODE_DIR / "tools"))
        import importlib.util
        spec = importlib.util.spec_from_file_location("mer", CODE_DIR / "tools" / "memory-effect-report.py")
        mer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mer)  # type: ignore[union-attr]
        days = max(1, (date.today() - since).days)
        tax = len(mer.collect(days=days).get("exposure_tax", []))
        row("高曝光零使用 atom 數", float(tax), "<=", float(c.get("exposure_tax_max", 0)), fmt="{:.0f}")
    except Exception as e:  # noqa: BLE001 — 報表壞掉不擋回訪，標示即可
        rows.append({"name": "高曝光零使用 atom 數", "value": f"n/a ({e.__class__.__name__})",
                     "threshold": f"<= {c.get('exposure_tax_max', 0)}", "ok": True})

    status = "PASS" if all(r["ok"] for r in rows) else "FAIL"
    return {"status": status, "turns": n, "min_turns": min_turns, "rows": rows}


# ─── 檢查：closing-gates ────────────────────────────────────────────────────
# 收尾被擋幾次、擋下後重跑幾次測試（讀 Claude Code 的對話紀錄 projects/<資料夾>/*.jsonl，只算根層專案的資料夾）

PROJECTS_DIR = CLAUDE_DIR / "projects"
ROOT_PROJECT_PREFIX = re.sub(r"[:\\/.]", "-", str(CLAUDE_DIR)).lower()   # C:\Users\x\.claude → c--users-x--claude
_GATE_TAG = re.compile(r"\[(Guardian:[A-Za-z-]+|Workflow Guardian)\]")
_TEST_CMD = re.compile(r"pytest|run_verify")
_HARNESS_BLOCK = re.compile(r"<(system-reminder|task-notification|cross-session-message|ide_[a-z_]+)[^>]*>.*?</\1>", re.S)


def _user_text(msg: dict) -> str:
    """真的使用者訊息才回字：不是 tool_result、不是 Stop hook feedback、剝掉系統標籤後還有字。"""
    c = msg.get("content")
    if isinstance(c, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
            return ""
        c = "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(c, str) or c.lstrip().startswith("Stop hook feedback"):
        return ""
    return _HARNESS_BLOCK.sub("", c).strip()


def _closing_counts(since_utc: str) -> dict:
    """since_utc 之後根層專案的使用者回合數、收尾擋下數（同時間同內容只算一次）、擋下後到下一回合之間跑的測試數、各閘擋下數。"""
    turns = blocks = reruns = 0
    gates: dict = {}
    since_ts = datetime.fromisoformat(since_utc).timestamp()
    for p in glob.glob(str(PROJECTS_DIR / "*" / "*.jsonl")):
        if not Path(p).parent.name.lower().startswith(ROOT_PROJECT_PREFIX) or Path(p).stat().st_mtime < since_ts:
            continue
        seen: set = set()
        after_block = False
        for line in Path(p).read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            ts = str(d.get("timestamp") or "")[:19]
            if not isinstance(d, dict) or d.get("isSidechain") or ts < since_utc:
                continue
            a = d.get("attachment")
            if d.get("type") == "attachment" and isinstance(a, dict) and a.get("type") == "hook_blocking_error" \
                    and a.get("hookEvent") == "Stop":
                be = a.get("blockingError")
                text = be.get("blockingError", "") if isinstance(be, dict) else str(be)
                if (ts, text) in seen:
                    continue
                seen.add((ts, text))
                blocks += 1
                m = _GATE_TAG.search(text)
                gate = m.group(1) if m else "(無標籤)"
                gates[gate] = gates.get(gate, 0) + 1
                after_block = True
            elif d.get("type") == "user" and isinstance(d.get("message"), dict) and _user_text(d["message"]):
                turns += 1
                after_block = False
            elif d.get("type") == "assistant" and after_block and isinstance(d.get("message"), dict):
                for b in d["message"].get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Bash", "PowerShell") \
                            and _TEST_CMD.search(str((b.get("input") or {}).get("command", ""))):
                        reruns += 1
    return {"turns": turns, "blocks": blocks, "reruns": reruns, "gates": gates}


def check_closing_gates(item: dict) -> dict:
    c = item.get("criteria", {})
    k = _closing_counts(str(c.get("since_utc") or f"{item['since']}T00:00:00"))
    n, min_turns = k["turns"], int(c.get("min_turns", 30))
    out = {"status": "INSUFFICIENT", "turns": n, "min_turns": min_turns, "rows": [],
           "blocks": k["blocks"], "reruns": k["reruns"]}
    if n < min_turns:
        return out
    rows = out["rows"]
    for name, value, thr in (("收尾被擋次數／回合", k["blocks"] / n, float(c.get("blocks_per_turn_max", 0.4))),
                             ("擋下後重跑測試次數／回合", k["reruns"] / n, float(c.get("reruns_per_turn_max", 0.5)))):
        rows.append({"name": name, "value": f"{value:.2f}", "threshold": f"<= {thr:.2f}", "ok": value <= thr})
    top = sorted(k["gates"].items(), key=lambda kv: -kv[1])[:4]
    rows.append({"name": "還在擋的關卡（參考）", "value": "、".join(f"{g} {v}" for g, v in top) or "無",
                 "threshold": "不判", "ok": True})
    out["status"] = "PASS" if all(r["ok"] for r in rows) else "FAIL"
    return out


CHECKS = {"injection-budget": check_injection_budget, "closing-gates": check_closing_gates}


# ─── 輸出 ──────────────────────────────────────────────────────────────────

def render(item: dict, res: dict, brief: bool = False, first_show: bool = False) -> str:
    """交接前提：接手的 session 什麼都不記得。首次推送（或非 brief）整份 handoff 進 context，
    之後每日精簡版只給結果與結案指令。"""
    L = []
    head = f"[Guardian:Followup] ⏰ 回訪到期：{item.get('title', item['id'])}（登記 {item.get('since')} → 到期 {item.get('due')}）"
    L.append(head)
    if res["status"] == "INSUFFICIENT":
        L.append(f"  樣本不足：since 起僅 {res['turns']} 個回合（需 ≥{res['min_turns']}）——多用幾次 CC 後會自動再檢，無需動作。")
        return "\n".join(L)
    if (first_show or not brief) and item.get("handoff"):
        L.append("  ── 交接（假設接手者對本題零記憶）──")
        for k, v in item["handoff"].items():
            if isinstance(v, list):
                L.append(f"  【{k}】")
                L.extend(f"    - {x}" for x in v)
            else:
                L.append(f"  【{k}】{v}")
        L.append("  ── 檢查結果 ──")
    elif not brief and item.get("context"):
        L.append(f"  背景：{item['context']}")
    for r in res["rows"]:
        L.append(f"  {'✅' if r['ok'] else '❌'} {r['name']}：{r['value']}（通過線 {r['threshold']}）")
    if res["status"] == "PASS":
        L.append(f"  結論：全過，{'已自動結案' if item.get('done') else '可結案：python tools/followup-check.py --done ' + item['id']}。")
    else:
        why = item.get("on_fail") or "本 session 先看 `python tools/memory-effect-report.py` 找原因"
        L.append(f"  結論：未全過 → {why}；處理完 `python tools/followup-check.py --done {item['id']}`。")
    return "\n".join(L)


def run_all(force: bool = False, auto_close: bool = False, brief: bool = False, mark_shown: bool = False,
            only_id: str | None = None) -> tuple[list[str], int]:
    data = load()
    out: list[str] = []
    today = date.today().isoformat()
    changed = False
    fails = 0
    me = _me()
    rt = load_runtime()
    for raw in data.get("followups", []):
        item = merged(raw, rt)
        if only_id and item.get("id") != only_id:
            continue
        if item.get("done"):
            continue
        if not only_id and not for_me(item, me):
            continue  # 別人／別台機器的回訪：不跑、不顯示（--id 指名照跑）
        if not force and not is_due(item):
            continue
        if mark_shown and item.get("last_shown") == today:
            continue  # 今日已提醒
        fn = CHECKS.get(item.get("check", ""))
        if fn is None:
            out.append(f"[Guardian:Followup] ⚠ {item.get('id')}：未知檢查名 {item.get('check')!r}")
            continue
        res = fn(item)
        first_show = not item.get("last_shown")
        rec = rt.setdefault(item["id"], {})   # 執行期紀錄只寫本機，登記表不動
        rec["result"] = f"{today} {res['status']}"
        if res["status"] == "PASS" and auto_close:
            rec["done"] = True
            rec["done_at"] = today
        if res["status"] == "FAIL":
            fails += 1
        if mark_shown and res["status"] != "INSUFFICIENT":
            rec["last_shown"] = today  # 樣本不足不算「已提醒」，補足後仍要整份推
        changed = True
        out.append(render({**item, **rec}, res, brief=brief, first_show=first_show))
    if changed:
        save_runtime(rt)
    return out, fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--id", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--auto-close", action="store_true")
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--mark-shown", action="store_true")
    ap.add_argument("--done", default=None)
    ap.add_argument("--add", default=None, help="JSON 物件字串")
    ap.add_argument("--host-id", action="store_true", help="印這台電腦的代號（登記 host 欄用）")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if args.add:
        data = load()
        item = json.loads(args.add)
        for k in ("id", "title", "due", "since", "check"):
            if k not in item:
                print(f"缺欄位 {k}", file=sys.stderr)
                return 2
        item.setdefault("done", False)
        item.setdefault("criteria", {})
        data.setdefault("followups", []).append(item)
        save(data)
        print(f"added {item['id']} (due {item['due']})")
        return 0
    if args.done:
        data = load()
        for item in data.get("followups", []):
            if item.get("id") == args.done:
                item["done"] = True
                item["done_at"] = date.today().isoformat()
                save(data)
                print(f"done {args.done}")
                return 0
        print(f"not found: {args.done}", file=sys.stderr)
        return 1
    if args.host_id:
        print(host_id(platform.node()))
        return 0
    if args.list:
        rt = load_runtime()
        for item in (merged(raw, rt) for raw in load().get("followups", [])):
            flag = "done" if item.get("done") else ("DUE" if is_due(item) else "pending")
            mine = "" if for_me(item) else "  （別人／別台機器的）"
            print(f"{flag:8} {item['id']}  due={item.get('due')}  last={item.get('result', '')}{mine}")
        return 0
    if args.run:
        lines, fails = run_all(force=args.force, auto_close=args.auto_close, brief=args.brief,
                               mark_shown=args.mark_shown, only_id=args.id)
        if lines:
            print("\n".join(lines))
        return 1 if fails else 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
