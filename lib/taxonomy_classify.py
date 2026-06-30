"""taxonomy_classify.py — 單後端 batch 分類器（jury 的可組合單元）。

Phase 1：把 ≤8 條 draft 包成一題，丟一個後端（generate_fn 注入），回每條
{id, slug, is_real, sensitive, reason}。generate_fn 注入 → mock 可單測、接
lib.ollama_extract_core._call_ollama 可實跑。**dry-run：只算建議、不搬檔、不碰索引/詞庫。**

slug 走 closed-list（render_seed_for_prompt 奠基）：回值不在 seed → 強制 _Unsorted
（防 LLM 幻覺指向不存在分類，對映 INV 防飄移）。本檔不 import 索引/詞庫/搬移符號。
"""
from __future__ import annotations

import json
import re
from typing import Callable, Dict, List

from lib.game_taxonomy import (
    TAXONOMY_CATCHALL, render_seed_for_prompt, seed_slugs,
)

GenerateFn = Callable[[str], str]


def build_classify_prompt(drafts: List[Dict]) -> str:
    """drafts: [{"id": str, "title": str, "excerpt": str}, ...]（≤8）。"""
    seed = render_seed_for_prompt()
    items = "\n".join(
        f'[{d["id"]}] {d.get("title", "")}：{d.get("excerpt", "")}' for d in drafts
    )
    return (
        "你是遊戲開發團隊的知識分類器。把每條碎片歸入下列分類之一。\n\n"
        f"{seed}\n\n"
        "規則：\n"
        f"- slug 只能回上面出現過的；全都不合才回 \"{TAXONOMY_CATCHALL}\"。\n"
        "- is_real：0.0–1.0，這條是否為值得長期保留的真知識"
        "（低分=贅字/噪音/運作過程瑣事/重複；高分=決策/根因/踩坑/架構/可重用規則）。\n"
        "- sensitive：true 若含個資/金額/商業機密/帳密/合約。\n"
        "- 嚴格只輸出 JSON array，每條一物件，欄位：id, slug, is_real, sensitive, reason(≤20字)。\n\n"
        f"碎片（共 {len(drafts)} 條）：\n{items}\n\n"
        "只輸出 JSON array："
    )


def _coerce_item(obj: Dict, valid: frozenset) -> Dict:
    """正規化單條 LLM 輸出：slug closed-list、is_real clamp、型別補正。"""
    slug = str(obj.get("slug", "") or "").strip()
    coerced = slug not in valid and slug != TAXONOMY_CATCHALL
    if coerced:
        slug = TAXONOMY_CATCHALL
    try:
        is_real = float(obj.get("is_real", 0.0))
    except (TypeError, ValueError):
        is_real = 0.0
    is_real = max(0.0, min(1.0, is_real))
    return {
        "id": str(obj.get("id", "")).strip(),
        "slug": slug,
        "is_real": is_real,
        "sensitive": bool(obj.get("sensitive", False)),
        "reason": str(obj.get("reason", "") or "")[:40],
        "slug_coerced": coerced,  # True = LLM 回了非法 slug 被打回 _Unsorted
    }


def parse_classify_response(raw: str, valid_slugs: frozenset) -> List[Dict]:
    """從 LLM raw 輸出抽 JSON array，逐條正規化。解析不出 → []。"""
    if not raw:
        return []
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    return [_coerce_item(x, valid_slugs) for x in arr if isinstance(x, dict)]


def classify_batch(drafts: List[Dict], generate_fn: GenerateFn) -> List[Dict]:
    """跑一個後端分類 ≤8 條 draft，回正規化結果（順序對齊輸入 id；缺項補 unsure）。"""
    if not drafts:
        return []
    valid = seed_slugs()
    parsed = parse_classify_response(generate_fn(build_classify_prompt(drafts)), valid)
    by_id = {p["id"]: p for p in parsed}
    out = []
    for d in drafts:
        did = str(d["id"])
        if did in by_id:
            out.append(by_id[did])
        else:  # LLM 漏這條 → 保守標 _Unsorted + is_real=0（不可信、待人工）
            out.append({"id": did, "slug": TAXONOMY_CATCHALL, "is_real": 0.0,
                        "sensitive": False, "reason": "LLM 未回此 id", "slug_coerced": True,
                        "missing": True})
    return out
