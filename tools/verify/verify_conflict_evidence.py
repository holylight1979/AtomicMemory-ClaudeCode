"""verify_conflict_evidence.py — 證據等級裁決（了義）+ 快速否證通道守門.

守住規則（memory-conflict-detector）：
1. arbitrate 優先序：證據等級（實證>引述>推測>未標）→ recency → 現行規則
   （project>global → confidence）；兩側同級才落到 recency。
2. fast_refute_check：CONTRADICT 且新側（Last-used 較新）Evidence=實證、
   舊側 [固]/[觀] → 回傳新側代號；只浮出置頂，不自動降級。
3. run_write_check：incoming 為新側；Evidence=實證 且矛盾對象 [固]/[觀]
   → fast_refute=True + 說明；無 Evidence → False。
4. parse_atom_meta：Evidence 合法值入 meta；非法值視同未標。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude/
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))
TOOLS_DIR = CLAUDE_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

SPEC = importlib.util.spec_from_file_location(
    "memory_conflict_detector", TOOLS_DIR / "memory-conflict-detector.py"
)
MCD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MCD)


def _meta(confidence="[觀]", last_used="", scope="global", evidence=""):
    return {"scope": scope, "confidence": confidence,
            "last_used": last_used, "evidence": evidence}


# ─── arbitrate：證據等級優先 ─────────────────────────────────────────────────


def test_evidence_beats_recency_and_confidence():
    """實證側縱使較舊、confidence 較低，仍勝未標側。"""
    a = _meta(confidence="[臨]", last_used="2026-01-01", evidence="實證")
    b = _meta(confidence="[固]", last_used="2026-07-01", evidence="")
    arb = MCD.arbitrate(a, b)
    assert arb["winner"] == "a"
    assert "evidence" in arb["reason"]


def test_evidence_rank_full_order():
    for lo, hi in [("", "推測"), ("推測", "引述"), ("引述", "實證")]:
        arb = MCD.arbitrate(_meta(evidence=hi), _meta(evidence=lo))
        assert arb["winner"] == "a", (hi, lo)
        arb = MCD.arbitrate(_meta(evidence=lo), _meta(evidence=hi))
        assert arb["winner"] == "b", (lo, hi)


def test_same_evidence_falls_back_to_recency():
    a = _meta(evidence="引述", last_used="2026-01-01")
    b = _meta(evidence="引述", last_used="2026-06-01")
    arb = MCD.arbitrate(a, b)
    assert arb["winner"] == "b"
    assert "recent" in arb["reason"]


def test_same_evidence_same_date_falls_to_scope_then_confidence():
    # scope 規則
    a = _meta(scope="project", last_used="2026-01-01")
    b = _meta(scope="global", last_used="2026-01-01")
    arb = MCD.arbitrate(a, b)
    assert arb["winner"] == "a" and "project" in arb["reason"]
    # confidence 規則
    a = _meta(confidence="[固]", last_used="2026-01-01")
    b = _meta(confidence="[臨]", last_used="2026-01-01")
    arb = MCD.arbitrate(a, b)
    assert arb["winner"] == "a" and "confidence" in arb["reason"]


def test_full_tie_manual_review():
    arb = MCD.arbitrate(_meta(), _meta())
    assert "manual review" in arb["reason"]


# ─── fast_refute_check ───────────────────────────────────────────────────────


def test_fast_refute_new_empirical_vs_old_solid():
    new = _meta(confidence="[臨]", last_used="2026-07-01", evidence="實證")
    old = _meta(confidence="[固]", last_used="2026-01-01")
    assert MCD.fast_refute_check(new, old) == "a"
    assert MCD.fast_refute_check(old, new) == "b"  # 側序無關


def test_fast_refute_old_side_observed_also_triggers():
    new = _meta(last_used="2026-07-01", evidence="實證")
    old = _meta(confidence="[觀]", last_used="2026-01-01")
    assert MCD.fast_refute_check(new, old) == "a"


def test_fast_refute_not_triggered_cases():
    # 舊側 [臨] → 不觸發（無需快速通道）
    new = _meta(last_used="2026-07-01", evidence="實證")
    assert MCD.fast_refute_check(new, _meta(confidence="[臨]", last_used="2026-01-01")) is None
    # 新側非實證 → 不觸發
    cited = _meta(last_used="2026-07-01", evidence="引述")
    assert MCD.fast_refute_check(cited, _meta(confidence="[固]", last_used="2026-01-01")) is None
    # 實證在舊側 → 不觸發
    old_emp = _meta(confidence="[固]", last_used="2026-01-01", evidence="實證")
    assert MCD.fast_refute_check(_meta(last_used="2026-07-01"), old_emp) is None
    # 無法分辨新舊（同日/皆缺）→ 不觸發
    assert MCD.fast_refute_check(_meta(evidence="實證"), _meta(confidence="[固]")) is None


# ─── parse_atom_meta：Evidence 讀取 ──────────────────────────────────────────


def test_parse_atom_meta_evidence(tmp_path):
    p = tmp_path / "a.md"
    p.write_text(
        "# a\n\n- Scope: global\n- Confidence: [觀]\n- Trigger: x, y, z\n"
        "- Evidence: 實證\n\n## 知識\n\n- k\n",
        encoding="utf-8",
    )
    assert MCD.parse_atom_meta(p)["evidence"] == "實證"
    p.write_text(p.read_text(encoding="utf-8").replace("實證", "很確定"), encoding="utf-8")
    assert MCD.parse_atom_meta(p)["evidence"] == ""  # 非法值視同未標


def test_parse_atom_meta_without_evidence_compat(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("# a\n\n- Scope: global\n- Confidence: [觀]\n\n## 知識\n\n- k\n",
                 encoding="utf-8")
    assert MCD.parse_atom_meta(p)["evidence"] == ""


# ─── run_write_check：incoming fast-refute ───────────────────────────────────


def _patched_write_check(monkeypatch, content, hit_confidence="[固]",
                         classification="CONTRADICT"):
    hit = {"score": 0.88, "atom_name": "old-atom", "layer": "global",
           "text": "舊知識內容", "file_path": "", "confidence": hit_confidence}
    monkeypatch.setattr(MCD, "vector_search", lambda *a, **k: [hit])
    monkeypatch.setattr(MCD, "_classify_match", lambda *a, **k: classification)
    return MCD.run_write_check(content, None, "global")


def test_write_check_fast_refute_on_empirical_incoming(monkeypatch):
    out = _patched_write_check(
        monkeypatch, "# n\n\n- Evidence: 實證\n\n## 知識\n\n- 新事實內容夠長",
    )
    assert out["verdict"] == "contradict"
    assert out["fast_refute"] is True
    assert "不自動降級" in out["fast_refute_note"]


def test_write_check_no_fast_refute_without_evidence(monkeypatch):
    out = _patched_write_check(monkeypatch, "## 知識\n\n- 新事實內容夠長")
    assert out["verdict"] == "contradict"
    assert out["fast_refute"] is False


def test_write_check_no_fast_refute_vs_provisional_atom(monkeypatch):
    out = _patched_write_check(
        monkeypatch, "- Evidence: 實證\n\n- 新事實內容夠長", hit_confidence="[臨]",
    )
    assert out["verdict"] == "contradict"
    assert out["fast_refute"] is False


def test_write_check_agree_never_fast_refute(monkeypatch):
    out = _patched_write_check(
        monkeypatch, "- Evidence: 實證\n\n- 新事實內容夠長",
        classification="AGREE",
    )
    assert out["verdict"] != "contradict"
    assert out["fast_refute"] is False
