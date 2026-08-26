"""verify_realm_llm_classify.py — LLM realm 分類器（Phase B）的 mock 測試。

不打真 Ollama：monkeypatch ollama_client.get_client 回 stub，驗各分支（含 fail-safe）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude/
for _p in (CLAUDE_DIR, CLAUDE_DIR / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import ollama_client  # noqa: E402
import realm_llm_classify as R  # noqa: E402


class _Stub:
    """假 OllamaClient：generate 回固定字串，或 raise（模擬基礎設施失敗）。"""
    def __init__(self, resp):
        self._resp = resp

    def generate(self, prompt, **kw):
        if isinstance(self._resp, Exception):
            raise self._resp
        return self._resp


@pytest.fixture
def mock_llm(monkeypatch):
    def _set(resp):
        monkeypatch.setattr(ollama_client, "get_client", lambda *a, **k: _Stub(resp))
    return _set


def test_local_with_canon_and_term_validation(mock_llm):
    """LLM 判 local：domain_path canon（OS/Win→OS/Windows）、terms 剔系統通用詞。"""
    mock_llm('{"realm":"local","domain_path":"OS/Win",'
             '"terms":["wsl2","vhdx","server.js","記憶系統"],"confidence":0.9,"reason":"WSL"}')
    r = R.llm_classify_realm("wsl2-x", ["vhdx"], "WSL2 vhdx 救援", ["OS/Windows/WSL", "Tools"])
    assert r["realm"] == "local"
    assert r["domain_path"] == "OS/Windows"          # Win→Windows snap
    assert r["confidence"] == 0.9
    assert "wsl2" in r["terms"] and "vhdx" in r["terms"]
    assert "server.js" not in r["terms"] and "記憶系統" not in r["terms"]  # 通用詞剔除


def test_infra_failure_returns_error(mock_llm):
    """連不到 backend（例外）→ realm='error'（caller defer，**不**誤降級）。"""
    mock_llm(RuntimeError("connection refused"))
    r = R.llm_classify_realm("some-atom", [], "", [])
    assert r["realm"] == "error" and r["domain_path"] is None


def test_empty_response_returns_error(mock_llm):
    """空回應 → error（defer）。"""
    mock_llm("")
    assert R.llm_classify_realm("some-atom", [], "", [])["realm"] == "error"


def test_bad_json_returns_unsure(mock_llm):
    """有回應但解析不出 → unsure（歸 Else，非 defer）。"""
    mock_llm("這不是 JSON 而是一段廢話")
    assert R.llm_classify_realm("some-atom", [], "", [])["realm"] == "unsure"


def test_core_judgment_no_domain(mock_llm):
    """LLM 確信 core → realm='core'、domain_path None（caller 留 core）。"""
    mock_llm('{"realm":"core","domain_path":null,"terms":[],"confidence":0.8,"reason":"跨專案"}')
    r = R.llm_classify_realm("decisions-x", [], "", [])
    assert r["realm"] == "core" and r["domain_path"] is None


def test_local_missing_domain_falls_back_to_else(mock_llm):
    """判 local 但沒給 domain_path → 落 catch-all（Else）。"""
    mock_llm('{"realm":"local","domain_path":null,"terms":["foo"],"confidence":0.7,"reason":"x"}')
    r = R.llm_classify_realm("misc-atom", [], "", ["Tools"])
    assert r["realm"] == "local" and r["domain_path"] == "Else"


def test_unknown_realm_value_coerced_to_unsure(mock_llm):
    """LLM 回非法 realm 值 → unsure（fail-safe）。"""
    mock_llm('{"realm":"banana","domain_path":"X","terms":[],"confidence":0.5}')
    assert R.llm_classify_realm("a", [], "", [])["realm"] == "unsure"


def test_extract_json_strips_fence():
    """_extract_json 剝 ```json``` 圍欄（本地 crack 模型常加）。"""
    assert R._extract_json('```json\n{"realm":"core"}\n```') == '{"realm":"core"}'


def test_validate_terms_drops_protected_and_short():
    """_validate_terms 剔過短 + 自身命中 protected 的詞（防 learned 反殺核心）。"""
    out = R._validate_terms(["a", "feedback-x", "decisions", "wsl2", "vhdx"])
    assert "wsl2" in out and "vhdx" in out
    assert "a" not in out                 # 過短
    assert "feedback-x" not in out and "decisions" not in out  # protected 前綴


# ─── 核心層範疇分類（閉合清單）llm_classify_category ─────────────────────────

_CATS = ["版控", "工作流", "驗證與實證"]


def test_category_hit_in_closed_list(mock_llm):
    """清單內（大小寫不分）→ hit + 正名；terms 剔系統通用詞。"""
    mock_llm('{"category":"驗證與實證","terms":["printwindow","server.js"],"confidence":0.85,"reason":"驗"}')
    r = R.llm_classify_category("x", ["y"], "內文", _CATS)
    assert r["status"] == "hit" and r["category"] == "驗證與實證"
    assert r["confidence"] == 0.85 and r["terms"] == ["printwindow"]


def test_category_outside_list_is_unsure(mock_llm):
    """清單外（含 LLM 自創／'unsure'）→ unsure，永不落 Else。"""
    mock_llm('{"category":"量子","terms":[],"confidence":0.95,"reason":"x"}')
    r = R.llm_classify_category("x", [], "", _CATS)
    assert r["status"] == "unsure" and r["category"] is None
    mock_llm('{"category":"unsure","terms":[],"confidence":0.1,"reason":"?"}')
    assert R.llm_classify_category("x", [], "", _CATS)["status"] == "unsure"


def test_category_infra_failure_and_bad_json(mock_llm):
    """連不到 → error（caller 標 error、可延後重試）；壞 JSON → unsure；空清單 → error。"""
    mock_llm(RuntimeError("connection refused"))
    assert R.llm_classify_category("x", [], "", _CATS)["status"] == "error"
    mock_llm("not json at all")
    assert R.llm_classify_category("x", [], "", _CATS)["status"] == "unsure"
    assert R.llm_classify_category("x", [], "", [])["status"] == "error"
