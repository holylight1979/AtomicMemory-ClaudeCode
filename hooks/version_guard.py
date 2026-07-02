"""version_guard.py — 版本操作脈絡殘留 warn hook（standalone PostToolUse hook）。

問題：live 檔（.py/.js/config）與 atom 應只寫 timeless 現況，但開發中易埋入版本
操作脈絡（V5 P3 里程碑 / [vN] stderr 前綴 / [Fxx] spec 錨 / 方案代號…）＝浪費
token 又把歷史搬進 live。一次性人工掃除後無常設把關，易再漂移。

機制：PostToolUse（Write/Edit 後）掃描剛寫入的檔案內容，命中高精度版本 pattern →
warn-only advisory（systemMessage + stderr，可觀測不阻斷）。**寧漏報不誤報**：只收
高精度 pattern，模糊者（裸 Phase N / 日期 / v2.x）不納入，避免噪音。

範圍：只掃 ~/.claude 內的檔（政策針對本系統自身）；正位/歸檔檔（DevHistory /
_CHANGELOG / TECH / Architecture / SPEC / plans / verify / _staging）豁免。

規則：rules/core.md「版本與文件治理」；pattern/KEEP 邊界 single source＝atom
[[feedback-live-檔與記憶不留版本操作脈絡歷史歸專門檔]]。config: workflow/config.json
→ version_guard。standalone，仿 hooks/lang_guard.py。never-crash 降級靜默。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

CLAUDE_DIR = Path.home() / ".claude"
CONFIG_PATH = CLAUDE_DIR / "workflow" / "config.json"


# ─── Config ──────────────────────────────────────────────────────────────────


def _load_config() -> Dict[str, Any]:
    try:
        full = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return full.get("version_guard", {})
    except (json.JSONDecodeError, OSError):
        return {}


# ─── Pattern taxonomy（高精度子集，鏡射 atom ①–⑥；寧漏報不誤報）──────────────

# 只收「幾乎不會誤傷」的 pattern。模糊者刻意不收：
#   裸 `Phase N`（功能識別如 Phase 2 效用 / 檔名耦合 verify_*_phase2.py）
#   裸 `v2.11`（schema / migrated-v2.21 功能 literal）
#   日期戳（Created-at / fixture 合法）、「原X改Y」變更敘事（散文誤傷高）
_PATTERNS = [
    re.compile(r"V\d+\s*P\d+"),            # ① V5 P3 里程碑
    re.compile(r"\bSprint\s*\d+\b", re.I),  # ① Sprint N
    re.compile(r"\bWave\s*\d+\b", re.I),    # ① Wave N
    re.compile(r"方案[甲乙丙丁戊]"),         # ⑤ 方案代號
    re.compile(r"\[v\d+(?:\.\d+)?\]"),      # ② [v2] / [v2.1] stderr 前綴
    re.compile(r"\[phase\d+\]", re.I),      # ② [phase2] 前綴
    re.compile(r"\[F\d+\]"),                # ③ [F12] spec 錨
]

# 行內含這些 token → 該行整行豁免（KEEP 邊界：功能識別非版本脈絡）
_WHITELIST_TOKENS = (
    "_migrate_v", "SCHEMA_VERSION", "schema_version",
    "protocolVersion", "migrated-v", "protocol_version",
)

# 路徑含這些片段 → 整檔豁免（版本正位 / 歸檔 / 測試 fixture / 規劃）
_WHITELIST_PATH_PARTS = (
    "_aidocs/devhistory/", "_changelog", "/tech.md", "tech.md",
    "architecture.md", "readme.md", "spec_atom", "/plans/",
    "/verify/", "_staging/", "/.git/", "__pycache__",
    # atom 本身列舉 pattern 作範例 → 豁免自身與本 hook/測試
    "feedback-live-", "version_guard",
)

_TEXT_SUFFIXES = (".py", ".js", ".md", ".json", ".sh", ".txt", ".ts", ".mjs")


def is_scannable_path(file_path: str) -> bool:
    """只掃 ~/.claude 內、非正位/歸檔、文字副檔名的檔。"""
    if not file_path:
        return False
    norm = file_path.replace("\\", "/").lower()
    claude_norm = str(CLAUDE_DIR).replace("\\", "/").lower()
    if claude_norm not in norm:  # 政策只針對本系統自身
        return False
    if not norm.endswith(_TEXT_SUFFIXES):
        return False
    return not any(part in norm for part in _WHITELIST_PATH_PARTS)


def find_version_remnants(text: str) -> List[str]:
    """回傳命中的版本殘留片段（去重、限量）；行內含 whitelist token 的行整行跳過。"""
    if not text:
        return []
    found: List[str] = []
    seen = set()
    for line in text.splitlines():
        if any(tok in line for tok in _WHITELIST_TOKENS):
            continue
        for pat in _PATTERNS:
            for m in pat.findall(line):
                frag = m if isinstance(m, str) else m[0]
                if frag and frag not in seen:
                    seen.add(frag)
                    found.append(frag)
    return found


# ─── 取剛寫入的內容 ────────────────────────────────────────────────────────────


def extract_written_text(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """Write=content / Edit=new_string / MultiEdit=edits[].new_string。"""
    if not isinstance(tool_input, dict):
        return ""
    if tool_name == "Write":
        return str(tool_input.get("content", ""))
    if tool_name == "Edit":
        return str(tool_input.get("new_string", ""))
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits", [])
        if isinstance(edits, list):
            return "\n".join(
                str(e.get("new_string", "")) for e in edits if isinstance(e, dict)
            )
    return ""


# ─── PostToolUse handler ───────────────────────────────────────────────────────


def handle_post_tool_use(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
    if not is_scannable_path(file_path):
        sys.exit(0)

    text = extract_written_text(tool_name, tool_input)
    remnants = find_version_remnants(text)
    min_matches = int(config.get("min_matches", 1))
    if len(remnants) < min_matches:
        sys.exit(0)

    shown = ", ".join(remnants[:5])
    name = Path(file_path.replace("\\", "/")).name
    msg = (
        f"[版本守衛] `{name}` 疑含版本操作脈絡殘留：{shown}。"
        f"live 檔/atom 只寫 timeless 現況——版本演進歸 _CHANGELOG，非埋進碼。"
        f"（規則 rules/core.md「版本與文件治理」；誤判可調 config.version_guard）"
    )
    # 可觀測性：systemMessage（可見+注入下輪）+ stderr（保底信號，不阻斷）
    sys.stderr.write(msg + "\n")
    print(json.dumps({"systemMessage": msg}, ensure_ascii=False))
    sys.exit(0)


# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")

    config = _load_config()
    if not config.get("enabled", False):  # fast path: disabled → 退出
        sys.exit(0)
    if config.get("mode", "warn") == "off":
        sys.exit(0)

    try:
        raw = sys.stdin.buffer.read()
        input_data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if input_data.get("hook_event_name", "") != "PostToolUse":
        sys.exit(0)

    try:
        handle_post_tool_use(input_data, config)
    except SystemExit:
        raise
    except Exception as e:  # never crash — 降級靜默
        sys.stderr.write(f"[version_guard] {type(e).__name__}: {e}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
