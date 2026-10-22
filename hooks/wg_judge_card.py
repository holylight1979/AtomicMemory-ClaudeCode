"""wg_judge_card.py — 改判準卡要先宣告（規則 JUDGE_CARD_CHANGE_NEEDS_DECLARATION）：收事實、找宣告行、留帳。只記錄不擋。

綁了 Entry 的判準卡是判 AI 做得對不對的量尺；誰改了、為什麼改，裁決時要看得到。這裡只收事實，判定在
wg_release_rules.judge_card_verdict。四條出口在 PreToolUse 判，直譯器出口事後比對：
- Edit／MultiEdit／Write、Bash／PowerShell：寫入目標由 wg_core.write_paths_from_tool 算（算不出的 UNKNOWN 交 OverviewHub）。
- MCP atom_write（append／replace）、atom_edit_meta、atom_retire：要 settings.json PreToolUse matcher 掛這三個工具名才經過這裡
  （matcher 由原設計者套用，沒套之前 MCP 出口不經過本閘）；
  卡在哪個檔照 MCP 自己用的 lib/atom_io.locate_atom 定位（MCP 行程沒有 session 與 transcript，宣告只能在這裡核對）。
- 直譯器自己開檔寫（JUDGE_CARD_HASH_CATCHES_INTERPRETER）：Bash／PowerShell 指令會跑直譯器、或指令字面含某張判準卡的檔名 →
  PreToolUse 把資料根索引裡綁 Entry 的卡記雜湊（snapshot，上一條路已判過的卡不重記）；PostToolUse（失敗的指令走
  PostToolUseFailure）比對（after_tool），變了又沒宣告 → 留帳（channel=interpreter）。卡清單取索引的 entry 欄（sync-atom-index 由檔頭同步），沒同步進索引的不在內。
目標是 memory／_atoms 目錄底下的 .md、磁碟上已經存在、檔頭 `- Entry:` 非空（lib/atom_locations.entry_bound_ids）才管；
宣告行三管道（回覆文字／工具參數裡 `#` 開頭的註解行／thinking），主檔與子代理檔都找，Bash／PowerShell 另認這次指令的 `#` 註解行。
每次改動都留帳 Logs/guard-judge_card.jsonl（undeclared／declared／error，直譯器出口 channel=interpreter）。
出錯只 stderr＋留帳。
開關：workflow/config.json 的 guard.judge_card_declare.enabled（預設開）。
怎麼驗：python -X utf8 -m pytest -q hooks/verify/verify_judge_card_declare.py
"""
from __future__ import annotations

import hashlib
import json
import re
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
SNAP_DIR = "judge-card-snap"
# 指令會跑直譯器（可帶路徑、版本號與 .exe），或在指令位置直接跑腳本檔（`./fix.py`、`uv run fix.py`）：
# 腳本自己開檔寫的目標 write_paths_from_tool 解析不到
_INTERP_RE = re.compile(r"(?:^|[\s;&|(`'\"\\/])(?:python[\d.]*|pythonw|py|pypy[\d.]*|node|deno|bun|perl|ruby|php|pwsh|powershell)"
                        r"(?:\.exe)?(?=\s|$|[;&|)`'\"])"
                        r"|(?:^|[;&|(]\s*|\brun\s+)[\w./\\:-]*\.(?:py|pyw|js|mjs|cjs|ts|pl|rb|php|ps1|sh)(?=\s|$|[;&|)])",
                        re.IGNORECASE | re.MULTILINE)


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


def data_root_cards() -> Dict[str, List[str]]:
    """資料根索引裡綁了 Entry 的卡 {絕對路徑: Entry 代號}（索引 entry 欄，sync-atom-index 由檔頭同步）。"""
    from atom_index_json import load_atom_index_json
    from wg_core import CLAUDE_DIR, MEMORY_DIR
    out: Dict[str, List[str]] = {}
    for a in load_atom_index_json(MEMORY_DIR).get("atoms") or []:
        entry = [str(e).strip() for e in a.get("entry") or [] if str(e).strip()]
        if entry and a.get("path"):
            out[str(CLAUDE_DIR / str(a["path"]))] = entry
    return out


def _sha(path: str) -> str:
    """檔案內容雜湊；檔不在回空字串（被刪也算變了）。"""
    p = Path(path)
    return hashlib.sha1(p.read_bytes()).hexdigest() if p.is_file() else ""


def _snap_path(input_data: Dict[str, Any]) -> Path:
    """這次工具呼叫的雜湊快照檔：PreToolUse 與 PostToolUse 拿到同一個 tool_use_id（沒有就用工具名＋參數的雜湊）。"""
    from wg_core import WORKFLOW_DIR
    key = str(input_data.get("tool_use_id") or "") or hashlib.sha1(json.dumps(
        [input_data.get("tool_name"), input_data.get("tool_input")], sort_keys=True, ensure_ascii=False, default=str
    ).encode("utf-8")).hexdigest()[:16]
    sid = str(input_data.get("session_id") or "") or "nosid"
    return Path(WORKFLOW_DIR) / SNAP_DIR / f"{sid}-{re.sub(r'[^0-9A-Za-z_-]', '_', key)}.json"


def snapshot(tool_name: str, tool_input: Dict[str, Any], input_data: Dict[str, Any], judged: List[str]) -> None:
    """PreToolUse（Bash／PowerShell，閘放行之後）：指令會跑直譯器、或字面含某張判準卡的檔名 → 記資料根裡綁 Entry 的卡的雜湊；
    judged＝這次已由寫入目標判過的卡（不重記）。出錯只 stderr＋留帳：記不到就漏這一次，不能因此擋所有直譯器指令。"""
    if tool_name not in SHELL_TOOLS:
        return
    sid = str(input_data.get("session_id") or "")
    try:
        cmd = str(tool_input.get("command") or "")
        cards = data_root_cards()
        low = cmd.replace("\\", "/").lower()
        if not cards or not (_INTERP_RE.search(cmd) or any(Path(p).name.lower() in low for p in cards)):
            return
        skip = {_rr.canon_path(p) for p in judged}
        snap = {p: {"sha": _sha(p), "entry": e} for p, e in cards.items() if _rr.canon_path(p) not in skip}
        f = _snap_path(input_data)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8", newline="\n")
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:JudgeCardDeclare] 記判準卡雜湊失敗（這次直譯器改卡沒核對到）：{type(e).__name__}: {e}", file=sys.stderr)
        append_guard_log(GUARD, {"event": "snap_error", "session_id": sid, "tool": tool_name, "error": f"{type(e).__name__}: {e}"})


def after_tool(state: Optional[Dict[str, Any]], input_data: Dict[str, Any], config: Optional[Dict[str, Any]]) -> bool:
    """PostToolUse／PostToolUseFailure（Bash／PowerShell）：拿 PreToolUse 記的雜湊比磁碟，變了的卡逐張核對宣告：有宣告留帳 declared，
    沒有留帳 undeclared（不擋）。回有沒有比對到變動。"""
    tool_name = str(input_data.get("tool_name") or "")
    if state is None or not _enabled(config) or tool_name not in SHELL_TOOLS:
        return False
    f = _snap_path(input_data)
    if not f.is_file():
        return False
    snap = json.loads(f.read_text(encoding="utf-8"))
    f.unlink(missing_ok=True)
    moved = [(p, v["entry"], v["sha"]) for p, v in snap.items() if _sha(p) != v["sha"]]
    if not moved:
        return False
    sid = str(input_data.get("session_id") or "")
    decls = declarations(input_data, tool_name)
    for path, entry, _before in moved:
        stem = Path(path).stem
        v = _rr.judge_card_verdict(stem, entry, [d for d, _ in decls])
        line = v.evidence[0] if not v.owed and v.evidence else ""
        append_guard_log(GUARD, {"event": "undeclared" if v.owed else "declared", "channel": "interpreter", "session_id": sid,
                                 "tool": tool_name, "card": stem, "entry": entry, "path": path, "allowed": True,
                                 **({"line": line, "via": next((ch for d, ch in decls if d["line"] == line), "")} if line else {})})
    return True


def gate(tool_name: str, tool_input: Dict[str, Any], input_data: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Optional[str]:
    """PreToolUse：只留帳不擋（量尺被改的問題在沒人知道，留帳即解），永遠回 None。改綁 Entry 的判準卡，
    每張記一筆 declared／undeclared；Bash／PowerShell 記雜湊給事後比對。閘內部錯誤只浮 stderr 並留帳。"""
    if not _enabled(config):
        return None
    sid = str(input_data.get("session_id") or "")
    try:
        if not (tool_name in FILE_TOOLS or tool_name.endswith(MCP_TOOLS)):
            return None
        cards = bound_cards(tool_name, tool_input, str(input_data.get("cwd") or ""))
        if cards:
            _judge(tool_name, cards, sid, input_data)
        snapshot(tool_name, tool_input, input_data, [p for p, _ in cards])
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        sys.stderr.write(f"[Guardian:JudgeCardDeclare] 留帳失敗（不擋）：{err}\n")
        append_guard_log(GUARD, {"event": "error", "session_id": sid, "tool": tool_name, "error": err})
    return None


def _judge(tool_name: str, cards: List[Tuple[str, List[str]]], sid: str, input_data: Dict[str, Any]) -> None:
    """每張要改的判準卡核對宣告、留帳（undeclared／declared）；不擋。"""
    decls = declarations(input_data, tool_name)
    for path, entry in cards:
        stem = Path(path).stem
        v = _rr.judge_card_verdict(stem, entry, [d for d, _ in decls])
        line = v.evidence[0] if not v.owed and v.evidence else ""
        via = next((ch for d, ch in decls if d["line"] == line), "") if line else ""
        append_guard_log(GUARD, {"event": "undeclared" if v.owed else "declared", "session_id": sid, "tool": tool_name,
                                 "card": stem, "entry": entry, "path": path, "allowed": True,
                                 **({"line": line, "via": via} if line else {})})
