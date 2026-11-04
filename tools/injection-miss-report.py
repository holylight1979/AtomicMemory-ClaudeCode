#!/usr/bin/env python3
"""injection-miss-report.py — 量「hook 沒注入卡片時，Claude 有沒有自己補搜記憶」（唯讀）。

做什麼：掃 ~/.claude/projects/**/*.jsonl 最近 N 場（依檔案修改時間，略過 subagents 子目錄），
逐個使用者回合判：UserPromptSubmit hook 注入了幾張卡（注入文字裡行首 `[Atom:` 的數量）、
Claude 同回合有沒有呼叫 memory_search、搜了什麼。印注入 0 張的回合裡有補搜的比例、
注入 ≥1 張仍搜的比例、最常見搜尋詞前 30。
怎麼跑：python ~/.claude/tools/injection-miss-report.py [--sessions 150]

回合怎麼切（照檔案順序走主線紀錄，isSidechain 的略過）：
  - 回合起點＝送進來的一則提示：不含 tool_result 的 user 紀錄，或 queued_command 附件
    （Claude 忙時排隊送進來的提示）。isMeta（技能內文等）與壓縮摘要不切回合。
  - 背景任務完成通知（task-notification）與其他 session 傳來的訊息（peer）也會觸發 hook、也切回合，
    但不算使用者回合；它們回合裡的搜尋另列一行。
  - 回合內：UserPromptSubmit 的 hook_additional_context 附件（同回合多個就加總）、主線 assistant 的 tool_use。
  - Claude 沒回覆的回合（本地指令如 /model、中斷訊息）不可能搜尋，不進比例，另列筆數。
搜尋詞：query 以空白與標點切開、轉小寫、同一個 query 內去重、單字元略過。
search-terms-to-triggers.py 匯入本檔的 scan／split_terms 取搜尋句與切詞。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
SEARCH_TOOL = "mcp__workflow-guardian__memory_search"
OTHER_ORIGINS = frozenset({"task-notification", "peer"})  # 會觸發 hook 但不是使用者打的
HEADLESS_ENTRY = "sdk-cli"  # claude -p 無頭跑的 entrypoint
ATOM_LINE_RE = re.compile(r"^\[Atom:", re.MULTILINE)
TERM_SPLIT_RE = re.compile(r"[\s,，、。;；:：|/\\()（）\[\]{}「」『』\"'`]+")
TOP_TERMS = 30


def _origin(rec: dict):
    org = rec.get("origin")
    return org.get("kind") if isinstance(org, dict) else org


def turn_start_kind(rec: dict):
    """這筆紀錄是回合起點就回 "user"／"other"，不是回 None。"""
    t = rec.get("type")
    if t == "user":
        content = (rec.get("message") or {}).get("content")
        if isinstance(content, list) and any(isinstance(x, dict) and x.get("type") == "tool_result" for x in content):
            return None
        if _origin(rec) in OTHER_ORIGINS:
            return "other"
        if rec.get("isMeta") or rec.get("isCompactSummary"):
            return None
        return "user"
    if t == "attachment":
        att = rec.get("attachment") or {}
        if att.get("type") != "queued_command":
            return None
        if _origin(att) in OTHER_ORIGINS or att.get("commandMode") == "task-notification":
            return "other"
        return "user"
    return None


def _ups_card_count(rec: dict):
    """UserPromptSubmit 注入附件 → 卡片數；不是這種附件回 None。"""
    att = rec.get("attachment") or {}
    if rec.get("type") != "attachment" or att.get("type") != "hook_additional_context" \
            or att.get("hookEvent") != "UserPromptSubmit":
        return None
    content = att.get("content")
    text = "\n".join(str(x) for x in content) if isinstance(content, list) else str(content or "")
    return len(ATOM_LINE_RE.findall(text))


def _search_queries(rec: dict):
    if rec.get("type") != "assistant":
        return []
    out = []
    for block in (rec.get("message") or {}).get("content") or []:
        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == SEARCH_TOOL:
            out.append(str((block.get("input") or {}).get("query") or ""))
    return out


def scan_file(path: Path):
    """一場 transcript → 回合清單 [{kind, entry, cards, queries, answered}]。壞行略過並計數。"""
    turns, bad = [], 0
    cur = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if not isinstance(rec, dict) or rec.get("isSidechain"):
                continue
            kind = turn_start_kind(rec)
            if kind:
                cur = {"kind": kind, "entry": rec.get("entrypoint") or "", "cards": 0, "queries": [], "answered": False}
                turns.append(cur)
                continue
            if cur is None:
                continue
            n = _ups_card_count(rec)
            if n is not None:
                cur["cards"] += n
            if rec.get("type") == "assistant":
                cur["answered"] = True
                cur["queries"].extend(_search_queries(rec))
    return turns, bad


def recent_sessions(projects_dir: Path, sessions: int):
    files = [p for p in projects_dir.rglob("*.jsonl") if "subagents" not in p.relative_to(projects_dir).parts]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:sessions]


def scan(projects_dir: Path = PROJECTS_DIR, sessions: int = 150):
    """最近 N 場 → (掃到的檔, 全部回合, 壞行數)。"""
    files = recent_sessions(projects_dir, sessions)
    turns, bad = [], 0
    for p in files:
        t, b = scan_file(p)
        turns.extend(t)
        bad += b
    return files, turns, bad


def split_terms(query: str):
    seen = []
    for tok in TERM_SPLIT_RE.split((query or "").lower()):
        if len(tok) >= 2 and tok not in seen:
            seen.append(tok)
    return seen


def search_terms(turns) -> Counter:
    """全部回合（含非使用者回合）的搜尋詞 → {詞: 出現在幾個 query}。"""
    c = Counter()
    for t in turns:
        for q in t["queries"]:
            c.update(split_terms(q))
    return c


def summarize(turns) -> dict:
    user = [t for t in turns if t["kind"] == "user" and t["answered"]]
    zero = [t for t in user if t["cards"] == 0]
    inj = [t for t in user if t["cards"] > 0]
    by_entry = {}
    for label, pick in (("interactive", lambda t: t["entry"] != HEADLESS_ENTRY), ("headless", lambda t: t["entry"] == HEADLESS_ENTRY)):
        sub = [t for t in user if pick(t)]
        z = [t for t in sub if t["cards"] == 0]
        i = [t for t in sub if t["cards"] > 0]
        by_entry[label] = {"turns": len(sub), "zero": len(z), "zero_search": sum(1 for t in z if t["queries"]),
                           "inj": len(i), "inj_search": sum(1 for t in i if t["queries"])}
    return {
        "turns": len(user),
        "unanswered": sum(1 for t in turns if t["kind"] == "user" and not t["answered"]),
        "zero_inject": len(zero),
        "zero_then_search": sum(1 for t in zero if t["queries"]),
        "injected": len(inj),
        "inject_then_search": sum(1 for t in inj if t["queries"]),
        "cards_total": sum(t["cards"] for t in user),
        "search_calls_user": sum(len(t["queries"]) for t in user),
        "other_turns": sum(1 for t in turns if t["kind"] == "other"),
        "search_calls_other": sum(len(t["queries"]) for t in turns if t["kind"] == "other"),
        "by_entry": by_entry,
    }


def _pct(a: int, b: int) -> str:
    return f"{a / b * 100:.1f}%" if b else "n/a"


def render(files, bad: int, s: dict, terms: Counter) -> str:
    lines = [
        f"掃 {len(files)} 場（略過 subagents）；使用者回合 {s['turns']}，注入卡片共 {s['cards_total']} 張"
        f"（另有 Claude 沒回覆的回合 {s['unanswered']} 個不計）",
        f"注入 0 張的回合：{s['zero_inject']}（{_pct(s['zero_inject'], s['turns'])}），其中同回合自己 memory_search 補位："
        f"{s['zero_then_search']}（{_pct(s['zero_then_search'], s['zero_inject'])}）",
        f"注入 ≥1 張的回合：{s['injected']}，其中仍 memory_search：{s['inject_then_search']}（{_pct(s['inject_then_search'], s['injected'])}）",
    ]
    for label, name in (("interactive", "互動"), ("headless", "無頭 claude -p")):
        e = s["by_entry"][label]
        lines.append(f"  {name}：回合 {e['turns']}｜0 張 {e['zero']} 補搜 {e['zero_search']}（{_pct(e['zero_search'], e['zero'])}）"
                     f"｜≥1 張 {e['inj']} 仍搜 {e['inj_search']}（{_pct(e['inj_search'], e['inj'])}）")
    lines.append(f"memory_search 呼叫：使用者回合內 {s['search_calls_user']} 次；背景通知／跨 session 訊息回合"
                 f"（{s['other_turns']} 個，不計入上面比例）內 {s['search_calls_other']} 次")
    if bad:
        print(f"[injection-miss-report] 略過無法解析的 JSON 行 {bad} 行", file=sys.stderr)
    lines.append(f"最常見搜尋詞前 {TOP_TERMS}（詞：出現在幾個 query）：")
    lines.extend(f"  {term}：{n}" for term, n in terms.most_common(TOP_TERMS))
    lines.append(f"INJECTION_MISS DONE turns={s['turns']} zero_inject={s['zero_inject']} "
                 f"zero_then_search={s['zero_then_search']} inject_then_search={s['inject_then_search']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="量注入 0 張時 Claude 有沒有自己補搜記憶（唯讀）")
    ap.add_argument("--sessions", type=int, default=150, help="掃最近幾場（預設 150）")
    args = ap.parse_args()
    files, turns, bad = scan(PROJECTS_DIR, args.sessions)
    print(render(files, bad, summarize(turns), search_terms(turns)))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
