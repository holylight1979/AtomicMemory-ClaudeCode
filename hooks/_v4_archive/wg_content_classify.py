"""
wg_content_classify.py — 內容分類共用模組

統一判斷文字是否為「規劃型」(plan/draft/roadmap/TODO)：
- extract-worker: 萃取後過濾
- wg_episodic: episodic 生成前過濾 knowledge_lines
- workflow-guardian: _AIDocs 檔名 gate + atom 內容 gate
"""

import re

# ─── Plan-type content patterns ─────────────────────────────────────────────
# Unified regex: covers filenames AND content text.
# Matches: plan, todo, roadmap, draft, wip, scratch, 調查, 規劃, 暫存, phase-N,
#          設計方案, 待辦, 草稿, 下一步, next-step, action-item
PLAN_CONTENT_RE = re.compile(
    r"(?i)"
    r"(plan|todo|roadmap|draft|wip|scratch|調查|規劃|暫存)"
    r"|phase[- _]?\d"
    r"|設計方案|待辦|草稿|下一步|next[- _]?step|action[- _]?item"
)

# Stricter pattern for LLM-extracted content (matches the "content" field of extracted items)
# These indicate the extracted fact itself is about planning, not an operational fact.
PLAN_FACT_RE = re.compile(
    r"(?i)"
    r"(預計|計畫|規劃|打算|下一步|將要|準備|TODO|TBD|待確認|待實作|待處理)"
    r"|(Phase\s*\d+\s*.{0,5}(預計|計畫|目標|排程))"
    r"|(下個\s*(session|階段|sprint))"
    r"|(尚未|還沒|未來|之後再)"
)


def is_plan_filename(filename: str) -> bool:
    """Check if a filename looks like a temporary/plan document."""
    return bool(PLAN_CONTENT_RE.search(filename))


def is_plan_content(text: str) -> bool:
    """Check if extracted text content is plan/draft type (not operational knowledge).

    Returns True if the text describes future intent rather than established fact.
    Short texts (<10 chars) are not checked to avoid false positives on triggers.
    """
    if not text or len(text) < 10:
        return False
    return bool(PLAN_FACT_RE.search(text))


def classify_extracted_item(item: dict) -> str:
    """Classify an extracted item as 'knowledge' or 'plan'.

    Args:
        item: dict with at least 'content' key

    Returns:
        'plan' if the item describes future intent/planning
        'knowledge' otherwise
    """
    content = item.get("content", "")
    if is_plan_content(content):
        return "plan"
    return "knowledge"
