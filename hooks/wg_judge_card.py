"""wg_judge_card.py — 改判準卡要先宣告（規則 JUDGE_CARD_CHANGE_NEEDS_DECLARATION，裁定 #53）：收事實、找宣告行、留帳、組擋訊息。

綁了 Entry 的判準卡是判 AI 做得對不對的量尺；誰改了、為什麼改，裁決時要看得到。這裡只收事實，判定在
wg_release_rules.judge_card_verdict。四條出口都在 PreToolUse 判：
- Edit／MultiEdit／Write、Bash／PowerShell：寫入目標由 wg_core.write_paths_from_tool 算（算不出的 UNKNOWN 交 OverviewHub）。
- MCP atom_write（append／replace）、atom_edit_meta、atom_retire：要 settings.json PreToolUse matcher 掛這三個工具名才經過這裡
  （matcher 由原設計者套用，沒套之前 MCP 出口不經過本閘）；
  卡在哪個檔照 MCP 自己用的 lib/atom_io.locate_atom 定位（MCP 行程沒有 session 與 transcript，宣告只能在這裡核對）。
目標是 memory／_atoms 目錄底下的 .md、磁碟上已經存在、檔頭 `- Entry:` 非空（lib/atom_locations.entry_bound_ids）才管；
宣告行三管道（回覆文字／工具參數裡 `#` 開頭的註解行／thinking），主檔與子代理檔都找，Bash／PowerShell 另認這次指令的 `#` 註解行。
每次改動都留帳 Logs/guard-judge_card.jsonl（denied／declared／error）。閘自己炸＝判不了 → 擋。
開關：workflow/config.json 的 guard.judge_card_declare.enabled（預設開）。
怎麼驗：python -X utf8 -m pytest -q hooks/verify/verify_judge_card_declare.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import CODE_DIR, append_guard_log, transcripts_of, write_paths_from_tool
import wg_release_rules as _rr

GUARD = "judge_card"
FILE_TOOLS = ("Edit", "MultiEdit", "Write", "Bash", "PowerShell")
SHELL_TOOLS = ("Bash", "PowerShell")
MCP_TOOLS = ("__atom_write", "__atom_edit_meta", "__atom_retire")
ATOM_DIRS = ("memory", "_atoms")


def _enabled(config: Optional[Dict[str, Any]]) -> bool:
    return (((config or {}).get("guard") or {}).get("judge_card_declare") or {}).get("enabled", True) is not False


def _atom_md(path: str) -> bool:
    p = Path(path)
    return (p.suffix.lower() == ".md" and not p.name.startswith("_")
            and any(d in ATOM_DIRS for d in (s.lower() for s in p.parts[:-1])))


def _locate(title: str, scope: str, tool_input: Dict[str, Any], **kw: Any) -> str:
    """MCP 那邊會寫哪個檔：同一份 locate_atom、同樣的參數；定位不到或定位出錯（MCP 自己也會失敗）回空。"""
    if str(CODE_DIR) not in sys.path:
        sys.path.insert(0, str(CODE_DIR))
    from lib.atom_io import locate_atom
    r = locate_atom(title, scope, project_cwd=tool_input.get("project_cwd"), role=tool_input.get("role"),
                    user=tool_input.get("user"), **kw)
    return str(r.path) if r.ok and r.path else ""


def _mcp_target(tool_name: str, tool_input: Dict[str, Any]) -> str:
    name = str(tool_input.get("title") or tool_input.get("atom_name") or "").strip()
    scope = str(tool_input.get("scope") or "").strip()
    if not name or not scope:
        return ""
    if tool_name.endswith("__atom_write"):
        mode = str(tool_input.get("mode") or "")
        if mode not in ("append", "replace"):
            return ""
        entry = tool_input.get("entry")
        return _locate(name, scope, tool_input, mode=mode, realm=tool_input.get("realm"), domain=tool_input.get("domain"),
                       subdir=tool_input.get("subdir"), triggers=tool_input.get("triggers"),
                       cross_project=bool(tool_input.get("cross_project")),
                       entry=[str(e).strip() for e in entry] if isinstance(entry, list) else None)
    if tool_name.endswith("__atom_retire") and scope == "local":
        return _locate(name, "global", tool_input, realm="local", mode="append")
    if scope == "project":   # atom_edit_meta 的 project：照 MCP locateByName 的順序找 shared → personal → role
        for sc in ("shared", "personal") + (("role",) if tool_input.get("role") else ()):
            hit = _locate(name, sc, tool_input, mode="append")
            if hit:
                return hit
        return ""
    return _locate(name, scope, tool_input, mode="append")


def _targets(tool_name: str, tool_input: Dict[str, Any], cwd: str) -> List[str]:
    if tool_name.endswith(MCP_TOOLS):
        hit = _mcp_target(tool_name, tool_input)
        return [hit] if hit else []
    if tool_name not in FILE_TOOLS:
        return []
    return [p for p in write_paths_from_tool(tool_name, tool_input, cwd or None) if not p.startswith("UNKNOWN:")]


def bound_cards(tool_name: str, tool_input: Dict[str, Any], cwd: str) -> List[Tuple[str, List[str]]]:
    """這次呼叫要改的判準卡 [(路徑, 綁的 Entry)]：memory／_atoms 底下、磁碟上已存在、檔頭 Entry 非空。"""
    from atom_locations import entry_bound_ids
    out: List[Tuple[str, List[str]]] = []
    for p in dict.fromkeys(_targets(tool_name, tool_input, cwd)):
        if _atom_md(p) and Path(p).is_file():
            entry = entry_bound_ids(None, Path(p))
            if entry:
                out.append((p, entry))
    return out


def declarations(input_data: Dict[str, Any], tool_name: str) -> List[Tuple[Dict[str, Any], str]]:
    """整個 session 的宣告行 [(宣告, 管道)]：三管道、主檔與子代理檔；工具參數只認 `#` 開頭的行（寫進卡片內容裡的字樣不算宣告）；
    Bash／PowerShell 另認這次指令自己的 `#` 註解行（PreToolUse 當下這則呼叫不一定已進 transcript）。"""
    from overview_hub import LOCATE_CHANNELS, assistant_text_after
    _, tps = transcripts_of(str(input_data.get("transcript_path") or ""), str(input_data.get("agent_id") or ""))
    out: List[Tuple[Dict[str, Any], str]] = []
    for tp in tps:
        for ch in LOCATE_CHANNELS:
            text = assistant_text_after(tp, 0, ch)
            if ch == "tool_input":
                text = "\n".join(ln for ln in text.splitlines() if ln.lstrip().startswith("#"))
            out.extend((d, ch) for d in _rr.parse_judge_card_decls(text))
    if tool_name in SHELL_TOOLS:
        cmd = str((input_data.get("tool_input") or {}).get("command") or "")
        text = "\n".join(ln for ln in cmd.splitlines() if ln.lstrip().startswith("#"))
        out.extend((d, "tool_input") for d in _rr.parse_judge_card_decls(text))
    return out


def gate(tool_name: str, tool_input: Dict[str, Any], input_data: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Optional[str]:
    """PreToolUse：回擋訊息或 None。一次改好幾張判準卡，每張都要各自點到宣告，沒點到的全列出來。"""
    if not _enabled(config) or not (tool_name in FILE_TOOLS or tool_name.endswith(MCP_TOOLS)):
        return None
    sid = str(input_data.get("session_id") or "")
    try:
        cards = bound_cards(tool_name, tool_input, str(input_data.get("cwd") or ""))
        return _judge(tool_name, cards, sid, input_data) if cards else None
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        sys.stderr.write(f"[Guardian:JudgeCardDeclare] 閘內部錯誤（已擋）：{err}\n")
        append_guard_log(GUARD, {"event": "error", "session_id": sid, "tool": tool_name, "error": err})
        return (f"[Guardian:JudgeCardDeclare] 這次可能要改綁了 Entry 的判準卡，但閘判不了（{err}），一律擋。"
                "先用 Read 查原因；只是要記新知識就另開一張新卡（atom_write mode=create）。")


def _judge(tool_name: str, cards: List[Tuple[str, List[str]]], sid: str, input_data: Dict[str, Any]) -> Optional[str]:
    decls = declarations(input_data, tool_name)
    owed: List[Tuple[str, _rr.Verdict]] = []
    for path, entry in cards:
        stem = Path(path).stem
        v = _rr.judge_card_verdict(stem, entry, [d for d, _ in decls])
        line = v.evidence[0] if not v.owed and v.evidence else ""
        via = next((ch for d, ch in decls if d["line"] == line), "") if line else ""
        append_guard_log(GUARD, {"event": "denied" if v.owed else "declared", "session_id": sid, "tool": tool_name,
                                 "card": stem, "entry": entry, "path": path, "allowed": not v.owed,
                                 **({"line": line, "via": via} if line else {})})
        if v.owed:
            owed.append((stem, v))
    if not owed:
        return None
    return ("[Guardian:JudgeCardDeclare] 要改的是綁了 Entry 的判準卡（判 AI 做得對不對用的量尺）：先宣告一行再改，"
            "帳上留下誰、為什麼改過，裁決時才分得出量尺被改過。一次改好幾張，每張都要各自宣告。\n"
            + "\n".join(_rr.format_hit("jc", v) for _, v in owed) + "\n"
            + "\n".join(_rr.judge_card_hint(stem) for stem, _ in owed))
