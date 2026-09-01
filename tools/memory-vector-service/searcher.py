"""
searcher.py — 語意搜尋引擎

使用 LanceDB 進行向量搜尋。
ranked_search() 以 intent-aware 多因子排序。
V4: user/roles 參數 → 組 layer SQL clause 過濾可見性（SPEC §8.1）。
"""

import json
import re
from datetime import date
from typing import Any, Dict, List, Optional

from indexer import create_embedder, search_vectors


# ─── V4 Layer Filter ─────────────────────────────────────────────────────────

_SANE_ID = re.compile(r"^[\w\-]+$")


def _build_v4_layer_clause(
    user: Optional[str],
    roles: Optional[List[str]],
) -> Optional[str]:
    """V4: 依 user + roles 組 LanceDB WHERE clause（SPEC §8.1）。

    回傳：
      - None：user/roles 皆空 → 不過濾（保留給管理職 / indexer 等全量場景）
      - SQL 字串：限定 global + shared:* + role:*:{r}... + personal:*:{user}

    安全：user/roles 只允許 [\\w-]+，不合就丟（防 SQL 注入）。
    """
    user_clean = user if user and _SANE_ID.match(user) else None
    role_clean: List[str] = []
    if roles:
        for r in roles:
            r = (r or "").strip()
            if r and _SANE_ID.match(r):
                role_clean.append(r)

    if not user_clean and not role_clean:
        return None

    clauses = ["layer = 'global'", "layer LIKE 'shared:%'"]
    for r in role_clean:
        clauses.append(f"layer LIKE 'role:%:{r}'")
    if user_clean:
        clauses.append(f"layer LIKE 'personal:%:{user_clean}'")
    return "(" + " OR ".join(clauses) + ")"


_SANE_LAYER = re.compile(r"^[\w\-:]+$")


def _build_layers_clause(layers: Optional[List[str]]) -> Optional[str]:
    """把明確的 layer 標籤清單組成 `layer IN (...)`。

    給呼叫端「只看這幾層」用（例：write-gate 去重只比 global + 當前專案自己的層）。
    標籤只允許 [\\w\\-:]（layer 標籤形如 shared:c--proj / personal:c--proj:user），
    不合的丟掉；全丟光回 None（= 不過濾，呼叫端自行決定是否接受）。
    """
    if not layers:
        return None
    clean = [l.strip() for l in layers if l and _SANE_LAYER.match(l.strip())]
    if not clean:
        return None
    quoted = ", ".join(f"'{l}'" for l in dict.fromkeys(clean))
    return f"layer IN ({quoted})"


# ─── Ranking Constants ───────────────────────────────────────────────────────

CONFIDENCE_SCORE_MAP = {"[固]": 1.0, "[觀]": 0.7, "[臨]": 0.4}

# (atom_category, intent) → boost multiplier (0.5-1.5)
INTENT_WEIGHT = {
    ("pitfall", "debug"): 1.5, ("pitfall", "build"): 1.0,
    ("pitfall", "design"): 0.8, ("pitfall", "recall"): 1.0,
    ("decision", "debug"): 0.8, ("decision", "build"): 1.0,
    ("decision", "design"): 1.3, ("decision", "recall"): 1.5,
    ("procedural", "debug"): 0.8, ("procedural", "build"): 1.5,
    ("procedural", "design"): 0.8, ("procedural", "recall"): 0.8,
    ("architecture", "debug"): 0.7, ("architecture", "build"): 1.0,
    ("architecture", "design"): 1.5, ("architecture", "recall"): 1.0,
    ("preference", "debug"): 0.5, ("preference", "build"): 0.8,
    ("preference", "design"): 1.0, ("preference", "recall"): 1.0,
}

# atom_type-level intent bonus (additive)
TYPE_INTENT_BONUS = {
    ("procedural", "build"): 0.05, ("procedural", "recall"): 0.03,
    ("episodic", "recall"): 0.05, ("episodic", "debug"): 0.03,
}


def _classify_atom_category(hit: Dict[str, Any]) -> str:
    """Classify atom into a category for intent boosting (rule-based)."""
    tags = hit.get("tags", "").lower()
    atom_type = hit.get("atom_type", "")
    name = hit.get("atom_name", "").lower()

    if any(k in tags for k in ("pitfall", "陷阱", "坑")):
        return "pitfall"
    if any(k in tags for k in ("architecture", "架構")):
        return "architecture"
    if atom_type == "procedural" or any(k in tags for k in ("操作", "recipe", "procedural")):
        return "procedural"
    if any(k in tags for k in ("decision", "決策")) or "decision" in name:
        return "decision"
    if any(k in tags for k in ("preference", "偏好")) or "preference" in name:
        return "preference"
    return "general"


def _compute_final_score(hit: Dict[str, Any], intent: str) -> Dict[str, Any]:
    """Compute weighted final score. Returns breakdown dict."""
    semantic = hit.get("score", 0.0)

    # Recency
    last_used = hit.get("last_used", "")
    if last_used:
        try:
            days = (date.today() - date.fromisoformat(last_used)).days
            recency = max(0.0, 1.0 - days / 90)
        except ValueError:
            recency = 0.5
    else:
        recency = 0.5

    # Intent boost
    cat = _classify_atom_category(hit)
    intent_boost = INTENT_WEIGHT.get((cat, intent), 1.0)

    # Type-level bonus
    atom_type = hit.get("atom_type", "semantic")
    type_bonus = TYPE_INTENT_BONUS.get((atom_type, intent), 0.0)

    # Confidence
    conf = CONFIDENCE_SCORE_MAP.get(hit.get("confidence", ""), 0.5)

    # Confirmations
    confirms = hit.get("confirmations", 0)
    if isinstance(confirms, str):
        try:
            confirms = int(confirms)
        except ValueError:
            confirms = 0
    confirm_score = min(0.2, confirms * 0.05)

    final = (0.45 * semantic
             + 0.15 * recency
             + 0.20 * intent_boost
             + 0.10 * conf
             + 0.10 * (confirm_score + type_bonus))

    return {
        "final_score": round(final, 4),
        "semantic": round(semantic, 4),
        "recency": round(recency, 4),
        "intent_boost": round(intent_boost, 2),
        "type_bonus": round(type_bonus, 4),
        "confidence_score": round(conf, 2),
        "confirm_score": round(confirm_score, 4),
        "category": cat,
        "atom_type": atom_type,
    }


def search(
    query: str,
    config: Dict[str, Any],
    top_k: int = 5,
    min_score: float = 0.65,
    layer_filter: Optional[str] = None,
    include_distant: bool = False,
    embedder=None,
    user: Optional[str] = None,
    roles: Optional[List[str]] = None,
    layers: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Semantic search across indexed atoms.

    Returns list of results sorted by score (descending):
    [{"atom_name", "title", "section", "text", "score", "confidence", "file_path", "layer", "line_number"}, ...]

    V4: 若傳 user/roles → 組 role-filter clause 過濾可見性。
    layers：明確的 layer 標籤清單，只搜這幾層（優先於 user/roles 與 layer_filter）。
    """
    if not query.strip():
        return []

    if embedder is None:
        embedder = create_embedder(config)

    # Embed query
    query_vec = embedder.embed([query])
    if not query_vec or not query_vec[0]:
        return []

    # 明確 layers 清單 > V4 role-based clause > layer_filter
    layer_clause = _build_layers_clause(layers) or _build_v4_layer_clause(user, roles)

    # Search LanceDB
    # LanceDB cosine metric: _distance = 1 - cosine_similarity
    raw_results = search_vectors(
        query_vec[0],
        top_k=top_k * 3,  # Fetch more for dedup
        layer_filter=layer_filter,
        layer_clause=layer_clause,
    )

    if not raw_results:
        return []

    # Process and dedup by atom
    hits: List[Dict[str, Any]] = []
    seen_atoms: Dict[str, float] = {}

    for row in raw_results:
        distance = row.get("_distance", 1.0)
        score = 1.0 - distance  # cosine similarity

        if score < min_score:
            continue

        atom_key = f"{row.get('layer', '')}:{row.get('atom_name', '')}"

        # Post-filter for "project" layer
        if layer_filter == "project" and not row.get("layer", "").startswith("project:"):
            continue

        # Dedup: keep highest scoring chunk per atom
        if atom_key in seen_atoms:
            if score <= seen_atoms[atom_key]:
                continue
        seen_atoms[atom_key] = score
        hits = [h for h in hits if f"{h['layer']}:{h['atom_name']}" != atom_key]

        hits.append({
            "atom_name": row.get("atom_name", ""),
            "title": row.get("title", ""),
            "section": row.get("section", ""),
            "text": row.get("text", ""),
            "score": round(score, 4),
            "confidence": row.get("confidence", ""),
            "file_path": row.get("file_path", ""),
            "layer": row.get("layer", ""),
            "line_number": int(row.get("line_number", 0)),
        })

    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits[:top_k]


def ranked_search(
    query: str,
    config: Dict[str, Any],
    intent: str = "general",
    top_k: int = 5,
    min_score: float = 0.50,
    layer_filter: Optional[str] = None,
    embedder=None,
    user: Optional[str] = None,
    roles: Optional[List[str]] = None,
    layers: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Intent-aware ranked search.

    Uses multi-factor scoring: 0.45*Semantic + 0.15*Recency + 0.20*IntentBoost
    + 0.10*Confidence + 0.10*Confirmation.

    V4: 若傳 user/roles → 組 role-filter clause 過濾可見性（SPEC §8.1）。
    """
    if not query.strip():
        return []

    if embedder is None:
        embedder = create_embedder(config)

    query_vec = embedder.embed([query])
    if not query_vec or not query_vec[0]:
        return []

    # 明確 layers 白名單（呼叫端可見性）> V4 role clause
    layer_clause = _build_layers_clause(layers) or _build_v4_layer_clause(user, roles)

    raw_results = search_vectors(
        query_vec[0],
        top_k=top_k * 4,  # Fetch extra for dedup + re-ranking
        layer_filter=layer_filter,
        layer_clause=layer_clause,
    )
    if not raw_results:
        return []

    # Dedup by atom (keep best semantic chunk per atom)
    hits: List[Dict[str, Any]] = []
    seen_atoms: Dict[str, float] = {}

    for row in raw_results:
        distance = row.get("_distance", 1.0)
        score = 1.0 - distance

        if score < min_score:
            continue

        atom_key = f"{row.get('layer', '')}:{row.get('atom_name', '')}"

        if layer_filter == "project" and not row.get("layer", "").startswith("project:"):
            continue

        if atom_key in seen_atoms:
            if score <= seen_atoms[atom_key]:
                continue
        seen_atoms[atom_key] = score
        hits = [h for h in hits if f"{h['layer']}:{h['atom_name']}" != atom_key]

        hits.append({
            "atom_name": row.get("atom_name", ""),
            "title": row.get("title", ""),
            "section": row.get("section", ""),
            "text": row.get("text", ""),
            "score": round(score, 4),
            "confidence": row.get("confidence", ""),
            "file_path": row.get("file_path", ""),
            "layer": row.get("layer", ""),
            "line_number": int(row.get("line_number", 0)),
            "last_used": row.get("last_used", ""),
            "confirmations": row.get("confirmations", 0),
            "atom_type": row.get("atom_type", "semantic"),
            "tags": row.get("tags", ""),
        })

    # Apply multi-factor ranking
    for hit in hits:
        breakdown = _compute_final_score(hit, intent)
        hit["final_score"] = breakdown["final_score"]
        hit["score_breakdown"] = breakdown

    hits.sort(key=lambda x: x["final_score"], reverse=True)
    return hits[:top_k]


def ranked_search_sections(
    query: str,
    config: Dict[str, Any],
    intent: str = "general",
    top_k: int = 5,
    max_sections: int = 3,
    min_score: float = 0.50,
    layer_filter: Optional[str] = None,
    embedder=None,
    user: Optional[str] = None,
    roles: Optional[List[str]] = None,
    layers: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Intent-aware ranked search preserving section-level detail.

    Same scoring as ranked_search(), but dedup groups by atom and keeps
    top-N chunks per atom instead of collapsing to 1.

    Returns: [{atom_name, file_path, final_score, layer,
               sections: [{section, text, score, line_number}]}]

    V4: 若傳 user/roles → 組 role-filter clause 過濾可見性（SPEC §8.1）。
    """
    if not query.strip():
        return []

    if embedder is None:
        embedder = create_embedder(config)

    query_vec = embedder.embed([query])
    if not query_vec or not query_vec[0]:
        return []

    layer_clause = _build_layers_clause(layers) or _build_v4_layer_clause(user, roles)

    raw_results = search_vectors(
        query_vec[0],
        top_k=top_k * 4,
        layer_filter=layer_filter,
        layer_clause=layer_clause,
    )
    if not raw_results:
        return []

    # Group chunks by atom, compute per-chunk score
    from collections import defaultdict
    atom_chunks: Dict[str, Dict[str, Any]] = {}   # atom_key → atom meta
    chunk_map: Dict[str, List[Dict]] = defaultdict(list)  # atom_key → chunks

    for row in raw_results:
        distance = row.get("_distance", 1.0)
        score = 1.0 - distance
        if score < min_score:
            continue

        atom_key = f"{row.get('layer', '')}:{row.get('atom_name', '')}"

        if layer_filter == "project" and not row.get("layer", "").startswith("project:"):
            continue

        if atom_key not in atom_chunks:
            atom_chunks[atom_key] = {
                "atom_name": row.get("atom_name", ""),
                "file_path": row.get("file_path", ""),
                "layer": row.get("layer", ""),
                "score": score,
                "last_used": row.get("last_used", ""),
                "confirmations": row.get("confirmations", 0),
                "atom_type": row.get("atom_type", "semantic"),
                "tags": row.get("tags", ""),
                "confidence": row.get("confidence", ""),
            }
        else:
            # Track best semantic score for the atom (used in final_score)
            if score > atom_chunks[atom_key]["score"]:
                atom_chunks[atom_key]["score"] = score

        chunk_map[atom_key].append({
            "section": row.get("section", ""),
            "text": row.get("text", ""),
            "score": round(score, 4),
            "line_number": int(row.get("line_number", 0)),
        })

    # Sort chunks per atom by score desc, keep top max_sections
    results: List[Dict[str, Any]] = []
    for atom_key, meta in atom_chunks.items():
        chunks = sorted(chunk_map[atom_key], key=lambda c: c["score"], reverse=True)
        chunks = chunks[:max_sections]

        # Compute final_score using best chunk score
        breakdown = _compute_final_score(meta, intent)
        results.append({
            "atom_name": meta["atom_name"],
            "file_path": meta["file_path"],
            "layer": meta["layer"],
            "final_score": breakdown["final_score"],
            "score_breakdown": breakdown,
            "sections": chunks,
        })

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results[:top_k]


def episodic_search(
    query: str,
    config: Dict[str, Any],
    top_k: int = 3,
    min_score: float = 0.35,
    embedder=None,
) -> List[Dict[str, Any]]:
    """Search only episodic atoms. Lower threshold for session context injection.

    Returns list of results filtered to atom_type=episodic, sorted by score:
    [{"atom_name", "score", "file_path", "layer", "last_used", "created", "atom_type"}, ...]
    """
    if not query.strip():
        return []

    if embedder is None:
        embedder = create_embedder(config)

    query_vec = embedder.embed([query])
    if not query_vec or not query_vec[0]:
        return []

    # Fetch more to compensate for type filtering
    raw_results = search_vectors(query_vec[0], top_k=top_k * 8)
    if not raw_results:
        return []

    # Filter: episodic only + dedup by atom
    hits: List[Dict[str, Any]] = []
    seen_atoms: Dict[str, float] = {}

    for row in raw_results:
        if row.get("atom_type", "semantic") != "episodic":
            continue

        distance = row.get("_distance", 1.0)
        score = 1.0 - distance
        if score < min_score:
            continue

        atom_name = row.get("atom_name", "")
        if atom_name in seen_atoms:
            if score <= seen_atoms[atom_name]:
                continue
        seen_atoms[atom_name] = score
        hits = [h for h in hits if h["atom_name"] != atom_name]

        hits.append({
            "atom_name": atom_name,
            "score": round(score, 4),
            "file_path": row.get("file_path", ""),
            "layer": row.get("layer", ""),
            "last_used": row.get("last_used", ""),
            "confidence": row.get("confidence", ""),
            "atom_type": "episodic",
        })

    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits[:top_k]


def search_raw(
    query: str,
    config: Dict[str, Any],
    top_k: int = 10,
    min_score: float = 0.5,
    embedder=None,
) -> List[Dict[str, Any]]:
    """Raw search without atom-level dedup. Used by reranker."""
    if not query.strip():
        return []

    if embedder is None:
        embedder = create_embedder(config)

    query_vec = embedder.embed([query])
    if not query_vec or not query_vec[0]:
        return []

    raw_results = search_vectors(query_vec[0], top_k=top_k)

    hits = []
    for row in raw_results:
        distance = row.get("_distance", 1.0)
        score = 1.0 - distance
        if score < min_score:
            continue
        hits.append({
            "atom_name": row.get("atom_name", ""),
            "title": row.get("title", ""),
            "section": row.get("section", ""),
            "text": row.get("text", ""),
            "score": round(score, 4),
            "confidence": row.get("confidence", ""),
            "file_path": row.get("file_path", ""),
            "layer": row.get("layer", ""),
            "line_number": int(row.get("line_number", 0)),
        })

    return hits


if __name__ == "__main__":
    import sys
    from config import load_config

    query_text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "測試搜尋"
    cfg = load_config()
    results = search(query_text, cfg, top_k=5, min_score=0.5)
    print(json.dumps(results, indent=2, ensure_ascii=False))
