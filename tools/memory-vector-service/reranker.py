"""
reranker.py — 本地 LLM 增強功能

透過 Ollama LLM API 提供：
A. 查詢改寫 (Query Rewriting)
B. Re-ranking
C. 知識萃取 (Auto-extract)

所有功能都是「離線路徑」，不在 3 秒 hook timeout 內使用。
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ollama_client import get_client


# ─── A. Query Rewriting ──────────────────────────────────────────────────────


def rewrite_query(
    query: str,
    config: Dict[str, Any],
) -> str:
    """Use LLM to expand/rewrite query for better semantic search.

    Example:
      "伺服器重啟後 client 斷線"
      → "伺服器重啟 client 連線中斷 socket disconnect reconnect 重連邏輯 斷線恢復"
    """
    client = get_client()
    if not client.is_available("llm"):
        return query  # fallback: return original

    system = (
        "你是一個搜尋查詢改寫助手。"
        "使用者會給你一個短查詢，你需要把它擴展成語意更豐富的搜尋文本。"
        "規則：\n"
        "1. 保留原始關鍵詞\n"
        "2. 加入同義詞（中英文都要）\n"
        "3. 加入相關技術術語\n"
        "4. 只輸出擴展後的文本，不要解釋\n"
        "5. 控制在 50 字以內"
    )

    try:
        result = client.chat(
            [{"role": "user", "content": query}],
            system=system, timeout=90,
        )
        return result.strip() if result.strip() else query
    except Exception:
        return query


# ─── B. Enhanced Search (Rewrite + Search) ───────────────────────────────────


def enhanced_search(
    query: str,
    config: Dict[str, Any],
    embedder=None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """LLM-enhanced search: rewrite query → vector search."""
    from searcher import search

    rewritten = rewrite_query(query, config)
    # Rewritten queries match with lower scores (more expanded/divergent), so lower threshold
    results = search(
        query=rewritten,
        config=config,
        top_k=top_k,
        min_score=min(config.get("search_min_score", 0.5), 0.4),
        embedder=embedder,
    )

    # Attach rewrite info
    for r in results:
        r["rewritten_query"] = rewritten

    return results


# ─── C. Re-ranking ───────────────────────────────────────────────────────────


def rerank(
    query: str,
    config: Dict[str, Any],
    embedder=None,
    candidates: Optional[List[Dict]] = None,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """Vector search top-N → LLM re-rank → top-K.

    If candidates not provided, does vector search first.
    """
    client = get_client()

    # Get candidates from vector search if not provided
    if candidates is None:
        from searcher import search_raw
        candidates = search_raw(query, config, top_k=10, min_score=0.4, embedder=embedder)

    if not candidates:
        return []

    if not client.is_available("llm"):
        # Fallback: return vector search results as-is
        return candidates[:top_k]

    # Ask LLM to score each candidate
    system = (
        "你是一個搜尋結果相關性評分助手。\n"
        "使用者會給你一個查詢和一個候選知識片段。\n"
        "請評估這個片段與查詢的相關性，給出 0-10 的分數。\n"
        "只輸出一個數字，不要任何解釋。"
    )

    scored = []
    for candidate in candidates:
        prompt = f"查詢: {query}\n\n知識片段: {candidate.get('text', '')}"
        try:
            score_text = client.chat(
                [{"role": "user", "content": prompt}],
                system=system, timeout=10,
            )
            # Extract number from response
            import re
            nums = re.findall(r"\d+(?:\.\d+)?", score_text)
            llm_score = float(nums[0]) / 10.0 if nums else 0.5
            llm_score = min(1.0, max(0.0, llm_score))
        except Exception:
            llm_score = candidate.get("score", 0.5)

        candidate_copy = dict(candidate)
        candidate_copy["llm_score"] = round(llm_score, 3)
        # Combined score: 40% vector + 60% LLM
        vec_score = candidate.get("score", 0.5)
        candidate_copy["combined_score"] = round(0.4 * vec_score + 0.6 * llm_score, 3)
        scored.append(candidate_copy)

    scored.sort(key=lambda x: x["combined_score"], reverse=True)
    return scored[:top_k]


# ─── D. Knowledge Extraction ────────────────────────────────────────────────


def extract_knowledge(
    text: str,
    config: Dict[str, Any],
    embedder=None,
) -> Dict[str, Any]:
    """Extract structured knowledge from text using LLM.

    Returns suggested atoms/facts for human review.
    """
    client = get_client()

    if not client.is_available("llm"):
        return {"error": "Ollama not available"}

    system = (
        "你是一個知識萃取助手。分析以下文本，萃取可以作為長期記憶保存的知識。\n\n"
        "輸出 JSON 格式：\n"
        "{\n"
        '  "facts": [\n'
        "    {\n"
        '      "text": "萃取的事實",\n'
        '      "confidence": "[固]|[觀]|[臨]",\n'
        '      "reason": "為什麼這個分類",\n'
        '      "suggested_atom": "建議歸入的 atom 名稱",\n'
        '      "triggers": ["建議的", "trigger", "keywords"]\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "分類規則：\n"
        "- [固]: 已確認的永久事實\n"
        "- [觀]: 已決策但可能演化\n"
        "- [臨]: 單次決策，需下次確認\n"
        "只輸出 JSON，不要其他文字。"
    )

    try:
        result = client.chat(
            [{"role": "user", "content": text}],
            system=system, timeout=30,
        )
        # Try to parse JSON from response
        # LLM might wrap it in ```json ... ```
        import re
        json_match = re.search(r"\{[\s\S]*\}", result)
        if json_match:
            return json.loads(json_match.group())
        return {"raw_response": result}
    except json.JSONDecodeError:
        return {"raw_response": result}
    except Exception as e:
        return {"error": str(e)}
