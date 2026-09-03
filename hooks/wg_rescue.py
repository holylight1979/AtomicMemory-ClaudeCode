"""wg_rescue.py — 救援日誌（rescue log）：注入 atom 是否真被用上的直接證據。

原理：UPS 注入 atom 時，從實際注入的知識內容**確定性**抽取高特異 token
（檔案路徑 / inline-code 指令 / ALL_CAPS 常數 / snake_case 識別字；泛詞與短詞
一律不取，寧缺勿濫）記入 session state 的 watch 表；本 session 後續工具呼叫的
tool_input 命中 watch token → 落 Logs/rescue-log.jsonl 一筆
{atom, token, evidence, turn_seq, tool}。純字串比對，零模型判斷。

精度守則（只認高置信證據）：
- 同 token 出現在多個 atom → 歸因模糊，整個丟棄
- Agent/Task 的 prompt 欄不掃（[WG:SubagentMemory] 自動注入會自我命中）
- 寫入 memory/ 或 _atoms/ 的 .md 不掃（編輯記憶本身不算「救援」）
- 每 (atom, token) 每 session 只記一次
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import CLAUDE_DIR, _atom_debug_error

RESCUE_LOG = CLAUDE_DIR / "Logs" / "rescue-log.jsonl"

_MIN_TOKEN_LEN = 6
_MAX_TOKEN_LEN = 80
_MAX_TOKENS_PER_ATOM = 20
_MAX_WATCH_TOKENS = 200
_SCAN_TEXT_CAP = 20000
_EVIDENCE_WINDOW = 40

# 泛詞黑名單：在本環境語料中高頻出現、無鑑別力的詞（小寫比對）
_GENERIC = frozenset({
    "python", "pytest", "session", "memory", "config", "claude", "atom",
    "atoms", "workflow", "guardian", "markdown", "string", "import",
    "default", "enabled", "disabled", "content", "message", "prompt",
    "hooks", "skills", "verify", "global", "project", "trigger", "commit",
    "session_id", "settings", "readme", "claude.md", "memory.md",
})

# 路徑型：含目錄分隔且以已知副檔名結尾，或已知根目錄開頭的相對路徑
_PATH_RE = re.compile(
    r"[A-Za-z0-9_\-.~]+(?:[/\\][A-Za-z0-9_\-.]+)+\.(?:py|md|json|jsonl|js|ts|yaml|yml|toml|ini|sh|ps1|txt)"
)
# inline code span（單反引號，不跨行）
_CODE_SPAN_RE = re.compile(r"`([^`\n]{3,80})`")
# ALL_CAPS 常數（≥6 字元）
_CONST_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
# snake_case 識別字（≥8 字元、至少一底線）
_SNAKE_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")


def _acceptable(tok: str) -> bool:
    tok = tok.strip()
    if not (_MIN_TOKEN_LEN <= len(tok) <= _MAX_TOKEN_LEN):
        return False
    if tok.lower() in _GENERIC:
        return False
    if re.fullmatch(r"[\d\W]+", tok):  # 純數字/符號
        return False
    return True


def extract_specific_tokens(content: str) -> List[str]:
    """從注入內容確定性抽取高特異 token。順序穩定、去重、上限 _MAX_TOKENS_PER_ATOM。"""
    found: List[str] = []
    seen = set()

    def _add(tok: str) -> None:
        tok = tok.strip().strip("\"'()[]{}<>,;:")
        key = tok.lower()
        if key in seen or not _acceptable(tok):
            return
        seen.add(key)
        found.append(tok)

    for m in _PATH_RE.finditer(content):
        _add(m.group(0))
    for m in _CODE_SPAN_RE.finditer(content):
        span = m.group(1).strip()
        # code span 若整段是路徑已被上面抓過；泛詞單字 span 由 _acceptable 擋
        _add(span)
    for m in _CONST_RE.finditer(content):
        _add(m.group(0))
    for m in _SNAKE_RE.finditer(content):
        if len(m.group(0)) >= 8:
            _add(m.group(0))
    # 子字串抑制：token 是另一 token 的子字串 → 冗餘（如路徑內的 snake 識別字），丟短留長
    lowers = [t.lower() for t in found]
    kept = [
        t for i, t in enumerate(found)
        if not any(i != j and lowers[i] in lowers[j] for j in range(len(found)))
    ]
    return kept[:_MAX_TOKENS_PER_ATOM]


def record_rescue_watch(
    state: Dict[str, Any], injected: List[Tuple[str, str]]
) -> None:
    """把 (atom_name, injected_content) 的特異 token 併入 state['rescue_watch']。

    同 token 已屬他 atom → 歸因模糊，標記剔除（寧缺勿濫）。總量硬頂防膨脹。
    """
    watch: Dict[str, str] = state.setdefault("rescue_watch", {})
    ambiguous: set = set(state.get("rescue_ambiguous", []))
    for atom_name, content in injected:
        for tok in extract_specific_tokens(content):
            key = tok.lower()
            if key in ambiguous:
                continue
            owner = watch.get(key)
            if owner is None:
                if len(watch) < _MAX_WATCH_TOKENS:
                    watch[key] = f"{atom_name}\t{tok}"
            elif not owner.startswith(f"{atom_name}\t"):
                watch.pop(key, None)
                ambiguous.add(key)
    state["rescue_ambiguous"] = sorted(ambiguous)


def _scan_text_for_tool(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """序列化 tool_input 為待掃文字。精度排除見模組 docstring。"""
    if not isinstance(tool_input, dict):
        return ""
    fp = str(tool_input.get("file_path", "")).replace("\\", "/")
    if fp.endswith(".md") and ("/memory/" in fp or "/_atoms/" in fp):
        return ""
    parts: List[str] = []
    for k, v in tool_input.items():
        if tool_name in ("Agent", "Task") and k == "prompt":
            continue  # 自動注入的 memory header 會自我命中
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (list, dict)):
            try:
                parts.append(json.dumps(v, ensure_ascii=False))
            except Exception:
                pass
    return "\n".join(parts)[:_SCAN_TEXT_CAP]


def check_rescue_hits(
    state: Dict[str, Any],
    session_id: str,
    tool_name: str,
    tool_input: Dict[str, Any],
    *,
    log_path: Optional[Path] = None,
) -> int:
    """掃描一次工具呼叫。命中即落 rescue-log.jsonl，回寫入筆數（0 = state 未變）。"""
    watch: Dict[str, str] = state.get("rescue_watch") or {}
    if not watch:
        return 0
    text = _scan_text_for_tool(tool_name, tool_input)
    if not text:
        return 0
    text_l = text.lower()
    hit_keys: List[str] = state.setdefault("rescue_hits", [])
    written = 0
    for key, owner in watch.items():
        atom_name, _, tok = owner.partition("\t")
        dedupe = f"{atom_name}|{key}"
        if dedupe in hit_keys:
            continue
        pos = text_l.find(key)
        if pos < 0:
            continue
        evidence = text[max(0, pos - _EVIDENCE_WINDOW): pos + len(tok) + _EVIDENCE_WINDOW]
        rec = {
            "ts": time.time(),
            "session_id": session_id,
            "atom": atom_name,
            "token": tok,
            "evidence": evidence.replace("\n", " ").strip(),
            "turn_seq": int(state.get("turn_seq", 0)),
            "tool": tool_name,
        }
        try:
            lp = log_path or RESCUE_LOG
            lp.parent.mkdir(parents=True, exist_ok=True)
            with open(lp, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            hit_keys.append(dedupe)
            written += 1
        except Exception as e:
            _atom_debug_error("rescue:write", e)
    return written
