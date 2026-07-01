"""lang_guard.py — 英文回應漂移攔截 hook（standalone Stop hook）。

問題：AI 對話輸出應為繁體中文，但隨 session 內英文 context 累積（英文碼 /
tool output / 檔名術語），「用繁中回應」的 salience 逐輪衰減 → AI 不自覺漂移成
英文。純靠 instruction 不可靠，故程式化攔截。

機制：Stop hook 量測 assistant 終版訊息「英文語言字元佔比」，先剝除 code
fence / inline code / URL（政策 B：只管 user-facing 對話輸出，不管碼），超門檻
→ systemMessage 提醒繁中（可見、非阻斷；同時注入下一輪 → 模型自我修正）。

Design: plans/kind-marinating-lerdorf.md（P8b）。standalone，仿 codex_companion
模式，不 import 共用 state 邏輯。config: workflow/config.json → lang_guard。
Fast path: config disabled → exit(0)。stateless（無 flag，每輪自我校正）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

CLAUDE_DIR = Path.home() / ".claude"
CONFIG_PATH = CLAUDE_DIR / "workflow" / "config.json"


# ─── Config ──────────────────────────────────────────────────────────────────


def _load_config() -> Dict[str, Any]:
    try:
        full = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return full.get("lang_guard", {})
    except (json.JSONDecodeError, OSError):
        return {}


# ─── 純函式：剝除非對話內容 + 算英文佔比（政策 B 落地，可測）──────────────────

# fenced code block（```lang\n...```），非貪婪、跨行
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
# inline code（`...`），單行
_INLINE_RE = re.compile(r"`[^`\n]*`")
# markdown link 的 (url/path) 目標：緊接在 ](...) 內者（保留前面 link text）
_LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
# 裸 URL
_URL_RE = re.compile(r"https?://\S+")

# 語言字元計數：ASCII 英文字母 vs CJK（統一表意 + 擴充 A + 相容表意）
_EN_RE = re.compile(r"[A-Za-z]")
_CJK_RE = re.compile(r"[一-鿿㐀-䶿豈-﫿]")


def strip_noncontent(text: str) -> str:
    """剝除 code fence / inline code / URL / markdown link 目標。

    政策 (B)：只管 user-facing 對話散文，不管碼/路徑。先剝 fence（含內部
    inline backtick），再剝 inline code、link 目標、裸 URL。保留 link text。
    """
    if not text:
        return ""
    t = _FENCE_RE.sub(" ", text)
    t = _INLINE_RE.sub(" ", t)
    t = _LINK_TARGET_RE.sub(" ", t)
    t = _URL_RE.sub(" ", t)
    return t


def english_ratio(text: str) -> Tuple[float, int]:
    """回傳 (英文字母 / (英文字母 + CJK), 語言字元總數)。

    分母只計「語言字元」（英文字母 + CJK），忽略數字/標點/空白/emoji，
    使佔比不被非語言符號稀釋。分母為 0（空/純標點）→ (0.0, 0)。
    """
    en = len(_EN_RE.findall(text))
    cjk = len(_CJK_RE.findall(text))
    total = en + cjk
    if total == 0:
        return 0.0, 0
    return en / total, total


def should_remind(
    text: str, threshold: float, min_lang_chars: int
) -> Tuple[bool, float, int]:
    """判定是否需提醒繁中。

    先剝非對話內容 → 算佔比。語言字元數 < min_lang_chars → 太短不判（避免對
    "OK"/"Done." 等短訊誤報）。否則 ratio >= threshold → 提醒。
    回傳 (need_remind, ratio, lang_chars)。
    """
    stripped = strip_noncontent(text)
    ratio, lang_chars = english_ratio(stripped)
    if lang_chars < min_lang_chars:
        return False, ratio, lang_chars
    return ratio >= threshold, ratio, lang_chars


# ─── 取終版 assistant 訊息（兩層 fallback，自含不依賴 codex_companion）────────


def _get_last_assistant_text(input_data: Dict[str, Any]) -> str:
    """1. input_data["last_assistant_message"]（若 ClaudeCode 提供）
    2. 自寫 transcript jsonl tail parser：取最後一則 type==assistant 的 text block。
    """
    direct = input_data.get("last_assistant_message", "")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    transcript_path = input_data.get("transcript_path", "")
    if not transcript_path:
        return ""
    try:
        last = ""
        with open(transcript_path, "r", encoding="utf-8") as f:
            for raw in f:
                try:
                    obj = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    continue
                if obj.get("type") != "assistant":
                    continue
                content = obj.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        t = block.get("text", "")
                        if t:
                            last = t
        return last
    except (OSError, UnicodeDecodeError):
        return ""


# ─── Stop handler ────────────────────────────────────────────────────────────


def handle_stop(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    text = _get_last_assistant_text(input_data)
    if not text:
        sys.exit(0)

    threshold = float(config.get("english_ratio_threshold", 0.5))
    min_lang_chars = int(config.get("min_lang_chars", 40))

    need, ratio, _ = should_remind(text, threshold, min_lang_chars)
    if not need:
        sys.exit(0)

    pct = round(ratio * 100)
    th_pct = round(threshold * 100)
    msg = (
        f"[語言守衛] 本次回應英文佔比 {pct}%（門檻 {th_pct}%），"
        f"偏好繁中對話；請改用繁體中文回應（code/註解/路徑不受此限）。"
    )
    print(json.dumps({"systemMessage": msg}, ensure_ascii=False))
    sys.exit(0)


# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    # Force UTF-8 on Windows
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")

    # Fast path: config disabled → 直接退出
    config = _load_config()
    if not config.get("enabled", False):
        sys.exit(0)

    # Read stdin
    try:
        raw = sys.stdin.buffer.read()
        input_data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if input_data.get("hook_event_name", "") != "Stop":
        sys.exit(0)

    try:
        handle_stop(input_data, config)
    except SystemExit:
        raise
    except Exception as e:  # never crash — 降級靜默
        sys.stderr.write(f"[lang_guard] {type(e).__name__}: {e}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
