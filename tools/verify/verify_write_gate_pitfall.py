"""verify_write_gate_pitfall.py — write-gate pitfall 捷徑 × dedup 順序守門.

守住規則：pitfall/坑 關鍵詞捷徑**只豁免品質評分**，不豁免去重——
dedup 先跑：>0.95 duplicate 仍 skip、0.80~0.95 similar 仍建議 update；
無 dedup 命中時 pitfall 才以 quality=0.7 直接 add（[觀]）。
另守 check_dedup fail-open 訊號：vector service 掛掉時 audit 記
dedup_skipped_service_down（可觀測性鐵律）。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude/
SPEC = importlib.util.spec_from_file_location(
    "memory_write_gate", CLAUDE_DIR / "tools" / "memory-write-gate.py"
)
WG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WG)

CONFIG = {
    "enabled": True,
    "auto_threshold": 0.5,
    "ask_threshold": 0.3,
    "dedup_score": 0.80,
    "skip_on_explicit_user": True,
}

PITFALL_CONTENT = "這是一個坑：Windows 下 Path.write_text 會翻整檔行尾"


def _dedup_stub(verdict: str, score: float):
    def stub(content, config, layers=None):
        return {
            "atom_name": "existing-atom", "score": score,
            "text_preview": "preview", "verdict": verdict,
        }
    return stub


def test_pitfall_duplicate_still_skipped(monkeypatch):
    monkeypatch.setattr(WG, "check_dedup", _dedup_stub("duplicate", 0.97))
    monkeypatch.setattr(WG, "write_audit_log", lambda *a, **k: None)
    r = WG.evaluate(PITFALL_CONTENT, config=CONFIG)
    assert r["action"] == "skip"
    assert r["dedup_match"]["atom_name"] == "existing-atom"


def test_pitfall_similar_still_suggests_update(monkeypatch):
    monkeypatch.setattr(WG, "check_dedup", _dedup_stub("similar", 0.88))
    monkeypatch.setattr(WG, "write_audit_log", lambda *a, **k: None)
    r = WG.evaluate(PITFALL_CONTENT, config=CONFIG)
    assert r["action"] == "update"


def test_pitfall_without_dedup_hit_auto_adds(monkeypatch):
    monkeypatch.setattr(WG, "check_dedup", lambda content, config, layers=None: None)
    monkeypatch.setattr(WG, "write_audit_log", lambda *a, **k: None)
    r = WG.evaluate(PITFALL_CONTENT, config=CONFIG)
    assert r["action"] == "add"
    assert r["quality_score"] == 0.7
    assert "pitfall" in r["reason"]


def test_explicit_user_fast_path_precedes_dedup(monkeypatch):
    called = []
    monkeypatch.setattr(WG, "check_dedup",
                        lambda content, config, layers=None: called.append(1) or None)
    monkeypatch.setattr(WG, "write_audit_log", lambda *a, **k: None)
    r = WG.evaluate("記住這個", explicit_user=True, config=CONFIG)
    assert r["action"] == "add" and not called


def test_check_dedup_service_down_writes_audit_signal(monkeypatch):
    """fail-open 必留訊號：service 掛 → audit 記 dedup_skipped_service_down。"""
    audits = []
    monkeypatch.setattr(WG, "write_audit_log",
                        lambda action, *a, **k: audits.append(action))

    def boom(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(WG.urllib.request, "urlopen", boom)
    assert WG.check_dedup("任意內容", CONFIG) is None
    assert "dedup_skipped_service_down" in audits


def test_check_dedup_layers_go_into_query(monkeypatch):
    """layers 給了就進 /search 的 layers= 參數（去重只比那幾層）；沒給就不帶（全庫）。"""
    import io
    seen = []

    class _Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=0):
        seen.append(req.full_url)
        return _Resp(b"[]")

    monkeypatch.setattr(WG.urllib.request, "urlopen", fake_urlopen)
    WG.check_dedup("任意內容", CONFIG, layers=["global", "shared:c--proj", "personal:c--proj:me"])
    WG.check_dedup("任意內容", CONFIG)
    assert "layers=global%2Cshared%3Ac--proj%2Cpersonal%3Ac--proj%3Ame" in seen[0]
    assert "layers=" not in seen[1]
