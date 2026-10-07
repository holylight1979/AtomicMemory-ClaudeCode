"""verify_write_gate_pointer.py — R6：去重閘對「指標卡」（導讀／hub 索引／知識地圖）用較高門檻。

指標卡只列位置與必問，詞彙跟內容卡天生重疊；一般卡 0.80 擋「相似」，指標卡只擋 >0.95 的真重複。
title 由 MCP atom-tools → funnel stdin JSON 傳入。免向量服務。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mwg", ROOT / "tools" / "memory-write-gate.py")
mwg = importlib.util.module_from_spec(spec)
sys.modules["mwg"] = mwg
spec.loader.exec_module(mwg)


def test_pointer_title_detection_default_and_config():
    cfg = {}
    assert mwg.is_pointer_title("設計表知識導讀-hub索引", cfg)
    assert mwg.is_pointer_title("spine區導讀-知識地圖與閱讀序", cfg)
    assert not mwg.is_pointer_title("設計表產出優先正式bytes管線", cfg)
    assert mwg.is_pointer_title("foo-overview", {"pointer_markers": ["overview"]})
    assert not mwg.is_pointer_title("設計表知識導讀", {"pointer_markers": ["overview"]})


def test_threshold_pointer_vs_normal():
    cfg = {"dedup_score": 0.8}
    assert mwg.dedup_threshold_for(cfg, "設計表產出優先正式bytes管線") == 0.8
    assert mwg.dedup_threshold_for(cfg, "設計表知識導讀-hub索引") == 0.95
    assert mwg.dedup_threshold_for({"dedup_score": 0.8, "dedup_pointer_score": 0.9}, "x導讀") == 0.9


def test_check_dedup_uses_pointer_threshold(monkeypatch):
    """0.816 的命中：內容卡要擋（similar），指標卡放行。"""
    import json

    class _Resp:
        def __init__(self, data):
            self._d = json.dumps(data).encode("utf-8")

        def read(self):
            return self._d

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    seen = {}

    def fake_urlopen(req, timeout=3):
        seen["url"] = req.full_url
        return _Resp([{"atom_name": "設計表產出優先正式bytes管線", "score": 0.816, "text": "..."}])

    monkeypatch.setattr(mwg.urllib.request, "urlopen", fake_urlopen)
    cfg = {"dedup_score": 0.8}
    hit = mwg.check_dedup("knowledge", cfg, None, "設計表產出-補充")
    assert hit and hit["verdict"] == "similar"
    assert mwg.check_dedup("knowledge", cfg, None, "設計表知識導讀-hub索引") is None
    assert "min_score=0.95" in seen["url"]
