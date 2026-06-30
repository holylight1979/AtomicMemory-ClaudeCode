"""atom_classify.py — 統一分類核心（realm + project taxonomy 共用 L1 計分骨架）。

半統一架構 L1（見 memory/_staging/next-phase-draft-taxonomy-engine.md §1-2）：
realm 軸與 taxonomy 軸的「決策語意」不同（tiebreak/無命中/保護清單 → adapter 並存），
但「計分機械骨架」實證 ~100% 同構：子字串掃 name+trigger、name 權重 > trigger 權重、累分。
本檔只抽該共用純函式；tiebreak / 無命中語意 / 保護清單 / segment guard 由各 strategy 詮釋。

MIRROR 注意（INV-LOGIC-SINGLE-PY-SOURCE-JS-MIRROR）：core 端 classify_realm 仍有 server.js
mirror（parity test）。本核心是 **py 單一來源**，js 對拍仍需同步——勿宣稱跨語言單源。
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Tuple


def score_by_lexicon(name, triggers, lexicon_pairs, *, name_w: int = 10, trig_w: int = 1):
    """純計分核心（realm classify_realm 與 project classify 共用）。

    lexicon_pairs: iterable of (term, bucket)。用 pair list 而非 dict，
      以容 taxonomy 同 term 跨多 domain（realm 的 term→domain 天然唯一亦相容）。
    回 (scores: {bucket: int}, matched_by_bucket: {bucket: [term]})。
    term 一律 lower 後子字串比對（realm 詞庫本即 lower、idempotent；taxonomy 原碼亦 term.lower()）。
    """
    nm = (name or "").strip().lower()
    trig_blob = " ".join((t or "").lower() for t in (triggers or []))
    scores: Dict[str, int] = {}
    matched: Dict[str, List[str]] = {}
    for term, bucket in lexicon_pairs:
        tl = str(term).lower()
        hit = (name_w if tl in nm else 0) + (trig_w if tl in trig_blob else 0)
        if hit:
            scores[bucket] = scores.get(bucket, 0) + hit
            matched.setdefault(bucket, []).append(term)
    return scores, matched


def taxonomy_term_pairs(domains: Dict[str, Dict]) -> List[Tuple[str, str]]:
    """project taxonomy domains{dom:{terms:[...]}} → [(term, dom), ...]
    保 domain 宣告序、保 term 序、允許 term 跨 domain 重複。"""
    return [(term, dom)
            for dom, spec in domains.items()
            for term in spec.get("terms", [])]
