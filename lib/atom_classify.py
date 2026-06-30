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


def classify_taxonomy(name, triggers, taxonomy: Dict) -> Tuple[str, List[str]]:
    """project taxonomy 分類（drop-in 取代 classify-project-atoms.py::classify）。

    回 (domain, matched_terms)。決策語意（override 優先 / 無命中落 default_domain /
    priority+宣告序 tiebreak）為 TaxonomyStrategy；計分走共用 score_by_lexicon。
    byte-equal verified 對 SGI 全 atom（verify_atom_classify.py）。
    """
    overrides: Dict[str, str] = taxonomy.get("overrides", {})
    if name in overrides:
        return overrides[name], ["<override>"]
    domains: Dict[str, Dict] = taxonomy.get("domains", {})
    scores, matched_by = score_by_lexicon(name, triggers, taxonomy_term_pairs(domains))
    if not scores:
        return (taxonomy.get("default_domain") or "_unclassified"), []
    order = list(domains.keys())
    best = max(scores, key=lambda d: (scores[d], int(domains[d].get("priority", 0)), -order.index(d)))
    return best, matched_by.get(best, [])


def classify_project_atom(name, triggers, taxonomy: Dict, *, escape_protected=None):
    """專案 atom 分類入口 = 跨 realm 逃逸閘（前置）+ classify_taxonomy（後置 pure）。

    escape_protected: 可選 callable(name)->bool，**注入**核心保護判定
    （lib.atom_locations.is_core_protected_name）。以注入而非 import 取得——atom_locations 已單向
    import 本模組的 score_by_lexicon，反向 import 會成 cycle，故由 caller 注入。

    命中逃逸閘（核心跨專案規則 atom 逃進專案）→ 回 ('_refile', ['<cross-realm-escapee>']):
    caller 送人工 /refile、**不**歸專案業務夾（INV-CROSS-REALM-ESCAPE-HATCH）。未命中（或未注入）
    → classify_taxonomy（taxonomy 維持 pure、protection 永 null，INV-STRATEGY-ISOLATION：逃逸閘是
    分類『前』的正交邊界守，非 TaxonomyStrategy 內部）。回 (domain, matched_terms)。
    """
    if escape_protected is not None and escape_protected(name):
        return "_refile", ["<cross-realm-escapee>"]
    return classify_taxonomy(name, triggers, taxonomy)
