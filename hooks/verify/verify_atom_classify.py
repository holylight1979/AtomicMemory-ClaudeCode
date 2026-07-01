"""verify_atom_classify.py — classify_realm 計分核心 byte-equal 重建對拍。

對 classify_realm（live import）+ 全核心 atom 對拍，證重構（退核心走 score_by_lexicon）前後零行為改變。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parent
CLAUDE = VERIFY_DIR.parent.parent
if str(CLAUDE) not in sys.path:
    sys.path.insert(0, str(CLAUDE))

from lib import atom_locations as AL  # noqa: E402
from lib.atom_locations import classify_realm  # noqa: E402


# ─── realm 重建（hand-rolled 獨立 oracle，**不**呼 score_by_lexicon）──────────
def reconstruct_realm(name, triggers):
    """重構前 classify_realm 的內聯計分逐行手寫複刻——刻意**不**依賴 lib.atom_classify。

    classify_realm 已重構為委派 score_by_lexicon；本獨立實作維持 byte-equal 對拍的真
    oracle：證『realm 計分鏈在「退核心」重構前後零行為改變』。任一端輸出漂移即被逮，
    避免 production 與 oracle 同走 score_by_lexicon 導致對拍退化為恆等式。
    """
    nm = (name or "").strip().lower()
    if nm in AL.LOCAL_REALM_CORE_PROTECTED_EXACT or nm.startswith(AL.LOCAL_REALM_CORE_PROTECTED_PREFIXES):
        return {"realm": "core", "domain": None, "protected": True}
    trig_blob = " ".join((t or "").lower() for t in (triggers or []))
    scores = {}
    for term, dom in AL.LOCAL_REALM_LEXICON.items():
        hit = 0
        if term in nm:
            hit += AL.LOCAL_REALM_NAME_WEIGHT
        if term in trig_blob:
            hit += AL.LOCAL_REALM_TRIGGER_WEIGHT
        if hit:
            scores[dom] = scores.get(dom, 0) + hit
    if not scores:
        return {"realm": "core", "domain": None, "protected": False}
    best = max(sorted(scores), key=lambda d: scores[d])
    if any(not AL._clean_segment(s) for s in best.split("/") if s.strip()):
        best = AL.LOCAL_REALM_DEFAULT_DOMAIN
    return {"realm": "local", "domain": best, "protected": False}


def _eq_realm(name, trig):
    e, g = classify_realm(name, trig), reconstruct_realm(name, trig)
    key = lambda r: (r["realm"], r["domain"], r["protected"])
    return key(e) == key(g), e, g


REALM_CASES = [
    ("guardian-dashboard 孤兒佔埠 修", ["eaddrinuse"]),   # → MemDev
    ("用 gdoc harvester 抓資料", ["harvester"]),           # → Tools
    ("腦內世界 world.html 生態", ["reconcile-render"]),     # → World
    ("feedback-something", ["x"]),                          # protected → core
    ("workflow-規則補充", []),                              # protected prefix → core
    ("完全無關條目", ["毫無命中詞彙"]),                       # 無命中 → core
]


def test_realm_byte_equal_cases():
    bad = [(n, e, g) for n, t in REALM_CASES for ok, e, g in [_eq_realm(n, t)] if not ok]
    assert not bad, bad


def test_realm_byte_equal_all_core_atoms():
    atoms = json.loads((CLAUDE / "memory" / "_atom_index.json").read_text(encoding="utf-8"))["atoms"]
    bad = [(a["name"], e, g) for a in atoms
           for ok, e, g in [_eq_realm(a["name"], a.get("triggers", []))] if not ok]
    assert not bad, f"{len(bad)} mism: {bad[:5]}"
