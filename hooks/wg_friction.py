"""wg_friction.py — session 摩擦量測：工具結果體積（浪費）＋使用者糾正訊號

兩個純本地計數，無 LLM、fail-open，補「零 token 浪費」與「測試全綠但一路被糾正」
這兩種原本量不到的東西。

1. 工具結果體積（PostToolUse → SessionEnd）
   - 每筆 tool_response 量字元數，append 到 `workflow/tool-results/<sid>.jsonl`
     （append-only，不進 state，避免每個工具呼叫都 R-M-W state）。
   - 單筆 ≥ `oversized_chars` → 回一行 advisory 給模型（每 session 至多
     `max_advisories_per_session` 次，計數存 state）+ `Logs/guard-tool-result-size.jsonl`。
   - SessionEnd 把整場 per-tool 次數／總量／最大值聚合成一筆
     `Logs/guard-tool-result-stats.jsonl`，然後刪 per-session 檔。

2. 使用者糾正（UserPromptSubmit → Stop）
   - 比對糾正／改口關鍵字（是「你做錯方向」的話，不是 bug／測試失敗的話——那組在
     response_capture.failure_extraction）。命中 → state["user_correction_count"] +1、
     明細 cap 10、`Logs/guard-friction.jsonl`。
   - 達 `min_hits` → Stop 的 Deep Post-Mortem 視為 effort 與真失敗同時成立。

config：workflow/config.json `tool_result_waste` / `friction`。
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import wg_core
from wg_core import _now_iso, append_guard_log

_TOOL_RESULT_GC_DAYS = 7
_HITS_CAP = 10
_BRIEF_LEN = 100

# 「對不對？」「不對嗎？」是提問不是糾正，比對前先拿掉。
_QUESTION_FORMS_RE = re.compile(r"對不對|不對嗎|不對\s*[?？]|是不是")

_DEFAULT_CORRECTION_KEYWORDS = [
    "不對", "不是這樣", "不是這個意思", "不是我要的", "我說過", "我已經說", "我剛說",
    "我沒叫你", "我沒要你", "誰叫你", "重來", "改回來", "回復原本", "還原回去", "退回去",
    "不要這樣", "你又", "又來了", "搞錯", "弄錯", "理解錯", "會錯意", "答非所問",
    "not what i asked", "that's not what", "i said", "i already said", "i told you",
    "revert that", "undo that", "start over", "wrong file", "wrong direction",
]


# ─── 1. 工具結果體積 ─────────────────────────────────────────────────────────


# 這些工具的 tool_response 帶整份檔案內容，但模型只看到一行「已更新」——量了會誤報。
_ACK_ONLY_TOOLS = {"Edit", "Write", "NotebookEdit"}


def tool_result_size(tool_response: Any, tool_name: str = "") -> int:
    """模型實際看到的結果字元數（近似）。
    Edit/Write 只看到一行 ack → 0；Bash 看 stdout+stderr；Read 看 file.content；
    其餘 str 直接量、dict/list 以 JSON 序列化長度近似。"""
    if tool_response is None or tool_name in _ACK_ONLY_TOOLS:
        return 0
    if isinstance(tool_response, str):
        return len(tool_response)
    if isinstance(tool_response, dict):
        if tool_name == "Bash":  # 模型只看到 stdout+stderr；兩者都沒有＝什麼都沒看到
            return len(tool_response.get("stdout") or "") + len(tool_response.get("stderr") or "")
        file_part = tool_response.get("file")
        if tool_name == "Read" and isinstance(file_part, dict) and "content" in file_part:
            return len(file_part.get("content") or "")
    try:
        return len(json.dumps(tool_response, ensure_ascii=False))
    except (TypeError, ValueError):
        return len(str(tool_response))


def _brief(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """一眼看出這筆結果是什麼：檔案路徑／指令頭／搜尋樣式。"""
    if not isinstance(tool_input, dict):
        return ""
    for key in ("file_path", "notebook_path", "command", "pattern", "query", "url", "path"):
        v = tool_input.get(key)
        if v:
            return str(v).replace("\n", " ")[:_BRIEF_LEN]
    return ""


def _tool_result_dir(base_dir: Optional[Path] = None) -> Path:
    """caller（PostToolUse／SessionEnd handler）把自己的 WORKFLOW_DIR 傳進來——那是各 verify
    monkeypatch 隔離的對象；沒傳才退回 wg_core.WORKFLOW_DIR。在 import 時固定路徑會讓
    跑測試時在真的 workflow/tool-results/ 留殘檔。"""
    return (base_dir or wg_core.WORKFLOW_DIR) / "tool-results"


def _tool_result_path(session_id: str, base_dir: Optional[Path] = None) -> Path:
    return _tool_result_dir(base_dir) / f"{session_id}.jsonl"


def record_tool_result(
    state: Dict[str, Any], session_id: str, tool_name: str,
    tool_input: Dict[str, Any], tool_response: Any, config: Dict[str, Any],
    base_dir: Optional[Path] = None,
) -> Optional[str]:
    """PostToolUse：量一筆、落 per-session 檔；超門檻回 advisory 字串（否則 None）。
    只有回 advisory 時才動 state（advisory 計數）。"""
    cfg = (config or {}).get("tool_result_waste", {}) or {}
    if not cfg.get("enabled", True) or not session_id:
        return None
    size = tool_result_size(tool_response, tool_name)
    if size == 0:
        return None
    threshold = int(cfg.get("oversized_chars", 20000))
    turn = int(state.get("turn_seq", 0) or 0)
    oversized = size >= threshold
    entry: Dict[str, Any] = {"t": int(time.time()), "tool": tool_name, "chars": size, "turn": turn}
    if oversized:
        entry["brief"] = _brief(tool_name, tool_input)
    try:
        _tool_result_dir(base_dir).mkdir(parents=True, exist_ok=True)
        with open(_tool_result_path(session_id, base_dir), "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[tool-result] append error: {e}", file=sys.stderr)
    if not oversized:
        return None

    append_guard_log("tool-result-size", {
        "session_id": session_id, "turn_seq": turn, "tool": tool_name,
        "chars": size, "threshold": threshold, "brief": entry.get("brief", ""),
    })
    max_adv = int(cfg.get("max_advisories_per_session", 3))
    shown = int(state.get("tool_result_advisories", 0) or 0)
    if shown >= max_adv:
        return None
    state["tool_result_advisories"] = shown + 1
    kb = size // 1000
    return (
        f"{tool_name} 這筆回傳約 {kb}K 字元（門檻 {threshold // 1000}K）："
        f"{entry.get('brief') or '(無目標)'}。整份都用得到才值得進 context；"
        "只需一段就改 offset/limit、grep 定位，或交 Explore agent 回摘要。"
        f"（本 session 此提醒剩 {max_adv - shown - 1} 次）"
    )


def summarize_tool_results(session_id: str, base_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """讀 per-session 檔 → per-tool {n, chars, max} + oversized 明細（最大 10 筆）。無檔回 None。"""
    path = _tool_result_path(session_id, base_dir)
    if not path.exists():
        return None
    per_tool: Dict[str, Dict[str, Any]] = {}
    oversized: List[Dict[str, Any]] = []
    total = 0
    n = 0
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tool = str(e.get("tool", "?"))
                chars = int(e.get("chars", 0) or 0)
                slot = per_tool.setdefault(tool, {"n": 0, "chars": 0, "max": 0})
                slot["n"] += 1
                slot["chars"] += chars
                if chars > slot["max"]:
                    slot["max"] = chars
                total += chars
                n += 1
                if "brief" in e:
                    oversized.append({"tool": tool, "chars": chars, "turn": e.get("turn", 0), "brief": e["brief"]})
    except OSError:
        return None
    oversized.sort(key=lambda x: -x["chars"])
    return {
        "calls": n, "total_chars": total, "per_tool": per_tool,
        "oversized_n": len(oversized), "oversized_chars": sum(o["chars"] for o in oversized),
        "oversized_top": oversized[:10],
    }


def flush_tool_result_stats(
    session_id: str, state: Dict[str, Any], base_dir: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """SessionEnd：聚合 → 一筆 Logs/guard-tool-result-stats.jsonl → 刪 per-session 檔；
    順手 GC 逾 7 天的孤兒檔（session 沒走到 SessionEnd 就留下的）。回聚合結果供 stderr 摘要。"""
    summary = summarize_tool_results(session_id, base_dir)
    if summary:
        summary["session_id"] = session_id
        summary["cwd"] = (state.get("session", {}) or {}).get("cwd", "")
        append_guard_log("tool-result-stats", summary)
        try:
            _tool_result_path(session_id, base_dir).unlink()
        except OSError:
            pass
    try:
        cutoff = time.time() - _TOOL_RESULT_GC_DAYS * 86400
        for old in _tool_result_dir(base_dir).glob("*.jsonl"):
            if old.stat().st_mtime < cutoff:
                old.unlink()
    except OSError:
        pass
    return summary


# ─── 2. 使用者糾正訊號 ───────────────────────────────────────────────────────


def detect_correction(prompt: str, config: Dict[str, Any]) -> List[str]:
    """回命中的糾正關鍵字（空 list＝沒命中）。ASCII 整詞、CJK 子字串，沿用 wg_atoms._kw_match。"""
    cfg = (config or {}).get("friction", {}) or {}
    if not cfg.get("enabled", True) or not prompt:
        return []
    from wg_atoms import _kw_match
    text = _QUESTION_FORMS_RE.sub("", prompt).lower()
    keywords = cfg.get("keywords") or _DEFAULT_CORRECTION_KEYWORDS
    return [kw for kw in keywords if _kw_match(kw.lower(), text)]


def record_correction(
    state: Dict[str, Any], session_id: str, prompt: str, config: Dict[str, Any],
) -> List[str]:
    """UserPromptSubmit：命中 → 計數 +1、明細 cap 10、guard log。回命中清單。"""
    matched = detect_correction(prompt, config)
    if not matched:
        return []
    turn = int(state.get("turn_seq", 0) or 0)
    state["user_correction_count"] = int(state.get("user_correction_count", 0) or 0) + 1
    hits = state.setdefault("user_correction_hits", [])
    hits.append({"turn": turn, "kw": matched[:3], "excerpt": prompt.strip().replace("\n", " ")[:80], "at": _now_iso()})
    if len(hits) > _HITS_CAP:
        state["user_correction_hits"] = hits[-_HITS_CAP:]
    append_guard_log("friction", {
        "session_id": session_id, "turn_seq": turn, "kw": matched[:3],
        "count": state["user_correction_count"], "excerpt": prompt.strip()[:120],
    })
    return matched


def friction_triggered(state: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """糾正次數達門檻＝「測試全綠但一路被糾正」也算真失敗。"""
    cfg = (config or {}).get("friction", {}) or {}
    if not cfg.get("enabled", True):
        return False
    return int(state.get("user_correction_count", 0) or 0) >= int(cfg.get("min_hits", 2))


def friction_summary(state: Dict[str, Any]) -> str:
    """給 Deep Post-Mortem 指令用的一句話：糾正幾次、命中哪些詞。"""
    count = int(state.get("user_correction_count", 0) or 0)
    kws: List[str] = []
    for h in state.get("user_correction_hits", []) or []:
        for k in h.get("kw", []):
            if k not in kws:
                kws.append(k)
    return f"使用者已糾正 {count} 次（{'、'.join(kws[:5]) or '關鍵字命中'}）"
