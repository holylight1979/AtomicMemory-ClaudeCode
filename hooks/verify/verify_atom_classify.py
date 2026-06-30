"""verify_atom_classify.py — Phase A：證明 score_by_lexicon 計分核心 byte-equal 重建兩範式。

realm：對 classify_realm（live import，my lib）+ 全核心 atom 對拍。
taxonomy：對 classify 的 verbatim 參考（= C:/Projects/.claude/tools/classify-project-atoms.py:76-123）
          + 全 SGI shared atom 對拍。
證「兩範式決策語意各走各的，但計分骨架真能統一」這個全架構地基假設。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

VERIFY_DIR = Path(__file__).resolve().parent
CLAUDE = VERIFY_DIR.parent.parent
if str(CLAUDE) not in sys.path:
    sys.path.insert(0, str(CLAUDE))

from lib.atom_classify import score_by_lexicon, taxonomy_term_pairs, classify_taxonomy  # noqa: E402
from lib import atom_locations as AL  # noqa: E402
from lib.atom_locations import classify_realm  # noqa: E402


# ─── realm 重建（決策語意複刻 classify_realm，計分走核心）──────────────────
def reconstruct_realm(name, triggers):
    nm = (name or "").strip().lower()
    if nm in AL.LOCAL_REALM_CORE_PROTECTED_EXACT or nm.startswith(AL.LOCAL_REALM_CORE_PROTECTED_PREFIXES):
        return {"realm": "core", "domain": None, "protected": True}
    scores, _ = score_by_lexicon(name, triggers, list(AL.LOCAL_REALM_LEXICON.items()),
                                 name_w=AL.LOCAL_REALM_NAME_WEIGHT, trig_w=AL.LOCAL_REALM_TRIGGER_WEIGHT)
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


# ─── taxonomy 重建（verbatim 參考 classify-project-atoms.py:76-123）────────
_NAME_W, _TRIG_W = 10, 1


def _ref_classify(name, triggers, taxonomy):
    """verbatim copy of classify-project-atoms.py::classify (76-123) 作 byte-equal oracle。"""
    overrides = taxonomy.get("overrides", {})
    if name in overrides:
        return overrides[name]
    nm = name.lower()
    trig_blob = " ".join(t.lower() for t in triggers)
    domains = taxonomy.get("domains", {})
    order = list(domains.keys())
    best_dom, best_score, best_priority, best_order = None, 0, -1, 1 << 30
    for dom, spec in domains.items():
        score = 0
        for term in spec.get("terms", []):
            tl = term.lower()
            hit = 0
            if tl in nm:
                hit += _NAME_W
            if tl in trig_blob:
                hit += _TRIG_W
            if hit:
                score += hit
        if score == 0:
            continue
        priority = int(spec.get("priority", 0))
        idx = order.index(dom)
        if (score > best_score or (score == best_score and priority > best_priority)
                or (score == best_score and priority == best_priority and idx < best_order)):
            best_dom, best_score, best_priority, best_order = dom, score, priority, idx
    if best_dom is None:
        return taxonomy.get("default_domain") or "_unclassified"
    return best_dom


SGI = Path("C:/Projects/.claude")


@pytest.mark.skipif(not (SGI / "memory/shared/_taxonomy.json").exists(), reason="SGI 不在本機")
def test_taxonomy_byte_equal_all_sgi_atoms():
    tax = json.loads((SGI / "memory/shared/_taxonomy.json").read_text(encoding="utf-8"))
    atoms = json.loads((SGI / "memory/_atom_index.json").read_text(encoding="utf-8"))["atoms"]
    checked, bad = 0, []
    for a in atoms:
        if "/shared/" not in (a.get("path") or "").replace("\\", "/"):
            continue
        name, trig = a["name"], a.get("triggers", [])
        e, g = _ref_classify(name, trig, tax), classify_taxonomy(name, trig, tax)[0]
        checked += 1
        if e != g:
            bad.append((name, e, g))
    assert checked >= 40, f"只查到 {checked} 顆 SGI atom，疑路徑錯"
    assert not bad, f"{len(bad)}/{checked} mism: {bad[:5]}"
