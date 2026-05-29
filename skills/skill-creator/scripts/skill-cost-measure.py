#!/usr/bin/env python3
"""skill-cost-measure: 解析 Claude Code transcript JSONL，量測 token 與工具呼叫成本。

用法:
  python skill-cost-measure.py --latest                       # 最新 session
  python skill-cost-measure.py --session <jsonl 絕對路徑>     # 指定 session
  python skill-cost-measure.py --latest --skill analyze-spec  # 標記特定 skill 觸發點

輸出 JSON 到 stdout (UTF-8)，錯誤到 stderr。
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

# Windows Python 預設 cp950 stdout 中文會亂碼 → 強制 UTF-8
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECTS_DIR = Path.home() / ".claude" / "projects"


def find_latest_jsonl() -> Path:
    candidates = list(PROJECTS_DIR.rglob("*.jsonl"))
    if not candidates:
        raise FileNotFoundError(f"No transcript found under {PROJECTS_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def iter_messages(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def extract_usage(msg: dict) -> dict | None:
    if msg.get("type") != "assistant":
        return None
    return msg.get("message", {}).get("usage")


def extract_tool_uses(msg: dict) -> list[str]:
    if msg.get("type") != "assistant":
        return []
    content = msg.get("message", {}).get("content", [])
    if not isinstance(content, list):
        return []
    return [c.get("name", "?") for c in content if isinstance(c, dict) and c.get("type") == "tool_use"]


def msg_uses_skill_tool(msg: dict, skill_name: str) -> bool:
    """檢查此 assistant message 是否實際呼叫 Skill 工具且 input.skill == skill_name。
    比字串掃描更精準：避免被 system-reminder / atom 注入 / 歷史對話誤觸發。"""
    if not skill_name or msg.get("type") != "assistant":
        return False
    content = msg.get("message", {}).get("content", [])
    if not isinstance(content, list):
        return False
    for c in content:
        if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "Skill":
            if (c.get("input") or {}).get("skill") == skill_name:
                return True
    return False


def analyze(path: Path, skill_name: str | None) -> dict:
    total = dict(
        input_tokens=0,
        output_tokens=0,
        cache_creation=0,
        cache_read=0,
        assistant_turns=0,
        tool_uses=0,
    )
    tool_use_counter: dict[str, int] = {}
    skill_phase = {"before": dict(total), "after": dict(total)}
    skill_triggered = False
    timeline = []  # [(turn_idx, tokens_summary)]

    for i, msg in enumerate(iter_messages(path)):
        usage = extract_usage(msg)
        tools = extract_tool_uses(msg)

        if skill_name and not skill_triggered and msg_uses_skill_tool(msg, skill_name):
            skill_triggered = True

        if usage:
            total["assistant_turns"] += 1
            total["input_tokens"] += usage.get("input_tokens", 0)
            total["output_tokens"] += usage.get("output_tokens", 0)
            total["cache_creation"] += usage.get("cache_creation_input_tokens", 0)
            total["cache_read"] += usage.get("cache_read_input_tokens", 0)

            if skill_name:
                bucket = skill_phase["after" if skill_triggered else "before"]
                bucket["assistant_turns"] += 1
                bucket["input_tokens"] += usage.get("input_tokens", 0)
                bucket["output_tokens"] += usage.get("output_tokens", 0)
                bucket["cache_creation"] += usage.get("cache_creation_input_tokens", 0)
                bucket["cache_read"] += usage.get("cache_read_input_tokens", 0)

        for t in tools:
            total["tool_uses"] += 1
            tool_use_counter[t] = tool_use_counter.get(t, 0) + 1
            if skill_name:
                skill_phase["after" if skill_triggered else "before"]["tool_uses"] += 1

    result = {
        "session_file": str(path),
        "total": total,
        "tool_use_breakdown": dict(sorted(tool_use_counter.items(), key=lambda kv: -kv[1])),
    }
    if skill_name:
        result["skill_filter"] = skill_name
        result["skill_triggered"] = skill_triggered
        result["before_trigger"] = skill_phase["before"]
        result["after_trigger"] = skill_phase["after"]
    return result


def main():
    p = argparse.ArgumentParser(description="量測 Claude Code session 的 token 與工具成本")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--latest", action="store_true", help="自動找最新 session")
    g.add_argument("--session", type=str, help="指定 session jsonl 絕對路徑")
    p.add_argument("--skill", type=str, default=None, help="標記某個 skill 觸發點，計算 before/after delta")
    args = p.parse_args()

    try:
        path = find_latest_jsonl() if args.latest else Path(args.session)
        if not path.exists():
            print(json.dumps({"status": "error", "reason": f"file not found: {path}"}, ensure_ascii=False))
            sys.exit(1)
        result = analyze(path, args.skill)
        result["status"] = "ok"
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
