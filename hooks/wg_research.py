"""wg_research.py — Research Fan-out detector.

UPS handler 偵測「知識檢索型」請求（幫我查 / 搜索 / 我想知道 / 研究一下），
注入兩階段 fan-out SOP 提示。

為什麼獨立於 wg_parallel（實測依據，勿憑印象合併）：
  - wg_parallel 的計分維度只有連接詞 / 批量詞 / 跨目標動詞 / 多檔提及 —— 檢索意圖
    不在其中任何一維。實測「幫我搜索 X 的差別」「我想知道 A 跟 B 選型」score 皆為
    **0**，永遠過不了 min_score 門檻。這是它對檢索型全啞的真正原因。
  - （次要）`_is_pure_question` 另會濾掉「什麼是 X」「為什麼 Y」**開頭**的無動詞
    純問句；那類本模組也不接管（無檢索動詞），故非本模組的存在理由。
  - 根本差異：wg_parallel 的並行價值定義是「多個目標」，檢索型的價值是「同一問題
    的多個檢索角度」——單一目標也值得 fan-out。兩者判準互斥，故分模組而非放寬門檻
    （放寬會讓所有單目標 prompt 誤觸發並行建議）。

輸出兩種模式（互斥）：
  - knowledge：外部知識/技術問題 → 兩階段（關鍵字擴充 → 記憶庫+網路併搜）
  - codebase：本地程式碼/檔案定位 → 單階段 Explore fan-out，不需 WebSearch

三層協作（同 wg_parallel 慣例）：
  - rules/core.md              → 原則
  - atom workflow-research-fanout → 手冊（trigger 注入）
  - this module                → 即時 pattern 推播

Config (workflow/config.json `research_fanout`):
  - enabled: bool
  - cooldown_turns: int (default 2)
  - min_prompt_chars: int (default 5) —— 中文密度高，「幫我查最佳實踐」僅 7 字元即
    是完整請求；檢索動詞已是必要條件，長度門檻只需擋住「查」這類單詞殘句。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# ── 檢索意圖動詞（必要條件：無命中直接不推播）────────────────
_RESEARCH_VERBS = [
    "幫我查", "幫我搜", "幫我找", "幫忙查", "幫忙找",
    "搜尋", "搜索", "查詢", "查一下", "查查", "找一下", "找找",
    "我想知道", "想知道", "想了解", "了解一下", "瞭解一下",
    "研究一下", "調查一下", "調研", "打聽",
    "有沒有相關", "有哪些", "有什麼方法", "怎麼做到", "如何實作", "如何做到",
    "最佳實踐", "best practice", "有沒有辦法",
    "search for", "look up", "look into", "find out",
    "research ", "i want to know", "how do i", "how to ",
    "what are the", "is there a way",
]

# ── 外部知識域訊號 → 傾向 knowledge 模式 ──────────────────
_KNOWLEDGE_SIGNALS = [
    "原理", "機制", "是什麼", "什麼是", "差別", "差異", "比較", "選型",
    "方案", "業界", "社群", "官方", "文件說", "規格", "標準", "生態",
    "新版", "版本", "更新", "roadmap", "changelog",
    "教學", "範例", "case study", "benchmark", "trade-off", "tradeoff",
    "怎麼用", "用法", "限制", "踩坑", "坑", "已知問題",
]

# ── 本地 codebase 定位訊號 → 傾向 codebase 模式 ────────────
_CODEBASE_SIGNALS = [
    "在哪", "哪個檔", "哪支檔", "哪一行", "哪裡定義", "定義在",
    "這個函式", "這支函式", "這個變數", "這段", "這個檔",
    "我們的", "本專案", "專案裡", "repo 裡", "codebase",
    "誰呼叫", "誰用到", "被誰", "引用", "reference",
    "where is", "which file", "who calls",
]

# ── 明示檔案路徑 → codebase 側證據 ─────────────────────
_PATH_RE = re.compile(
    r"(?:[a-zA-Z_][\w\-]*/)+[\w\-]+\.\w+"          # foo/bar.py
    r"|\b[\w\-]+\.(?:py|js|ts|tsx|json|md|toml|yaml|yml|cs|java|go|rs)\b"
)

# ── 略過條件 ───────────────────────────────────────
_SKIP_PATTERNS = [
    re.compile(r"^\s*/\w+"),                                  # 純 slash command
    re.compile(r"^\s*(?:好|是|對|否|不|yes|no|ok|確認|繼續)\s*[。!\.]?\s*$"),
]

# ── 反例：已在流程中／要我直接動手，不是要檢索 ──────────────
_ALREADY_ACTING = [
    "繼續做", "接著做", "照上面", "就這樣做", "開始實作", "直接改",
]


def _hit(text: str, needles: List[str]) -> int:
    return sum(1 for n in needles if n in text)


def _is_skip(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return any(p.match(stripped) for p in _SKIP_PATTERNS)


def classify(prompt: str) -> Tuple[Optional[str], List[str]]:
    """回傳 (mode, hints)。mode ∈ {"knowledge", "codebase", None}。

    必要條件：檢索動詞命中。之後比較 knowledge / codebase 兩側證據強度：
      - codebase 側：定位訊號 ×1 + 明示檔名/路徑 ×1
      - knowledge 側：知識域訊號 ×1 + 預設偏移 +1（無本地證據時外求）
    """
    low = prompt.lower()

    verb_hits = _hit(low, _RESEARCH_VERBS)
    if verb_hits == 0:
        return None, []
    if _hit(low, _ALREADY_ACTING) > 0:
        return None, []

    hints: List[str] = [f"檢索動詞×{verb_hits}"]

    code_score = 0
    cb_hits = _hit(low, _CODEBASE_SIGNALS)
    if cb_hits:
        code_score += cb_hits
        hints.append(f"本地定位×{cb_hits}")
    path_n = len(set(_PATH_RE.findall(prompt)))
    if path_n:
        code_score += path_n
        hints.append(f"明示檔×{path_n}")

    know_score = 1  # 預設偏 knowledge：沒有本地錨點就是外求知識
    kw_hits = _hit(low, _KNOWLEDGE_SIGNALS)
    if kw_hits:
        know_score += kw_hits
        hints.append(f"知識域×{kw_hits}")

    return ("codebase" if code_score > know_score else "knowledge"), hints


_KNOWLEDGE_LINE = (
    "[Research:Fanout] 偵測知識檢索型請求 ({hints})。走兩階段 fan-out，不要單線直答：\n"
    "  Stage A 關鍵字擴充（1-2 agent，回報限純關鍵字清單）："
    "術語同義詞 + 中文↔英文對應 + 上下位概念 + 常見誤稱；"
    "一路查網路確認業界實際用語。\n"
    "  Stage B 併搜（用 Stage A 全部關鍵字，同 message dispatch ≥2 agent）："
    "一路掃原子記憶庫/_AIDocs（既有結論優先，命中就別重查），"
    "一路 WebSearch/WebFetch 補外部最新知識。\n"
    "  Stage A→B 是真序列依賴（B 要 A 的關鍵字），故 A 必須輕；B 內部才是並行主力。"
    "完整判準見 [[workflow-research-fanout]]。不適合 fan-out 請說明原因。"
)

_CODEBASE_LINE = (
    "[Research:Fanout] 偵測本地程式碼檢索請求 ({hints})。"
    "同 message dispatch ≥2 個 `Explore` agent 分頭找（各給不同命名慣例/目錄切面），"
    "不需 WebSearch，不需關鍵字擴充階段。判準見 [[workflow-research-fanout]]。"
)


def detect_research_fanout(
    prompt: str, state: Dict[str, Any], config: Dict[str, Any]
) -> Optional[str]:
    """回傳要注入的 line，或 None。

    cooldown 以 topic_tracker.prompt_count 為基準（同 wg_parallel，
    state["turn_count"] 不可信）。
    """
    cfg = config.get("research_fanout", {})
    if not cfg.get("enabled", True):
        return None

    if len(prompt.strip()) < cfg.get("min_prompt_chars", 5):
        return None
    if _is_skip(prompt):
        return None

    mode, hints = classify(prompt)
    if mode is None:
        return None

    cooldown = cfg.get("cooldown_turns", 2)
    cur_turn = state.get("topic_tracker", {}).get("prompt_count", 0)
    last_inject = state.get("research_last_inject_turn", -10)
    if cur_turn - last_inject < cooldown:
        return None
    state["research_last_inject_turn"] = cur_turn

    hint_str = ", ".join(hints)
    tmpl = _KNOWLEDGE_LINE if mode == "knowledge" else _CODEBASE_LINE
    return tmpl.format(hints=hint_str)
