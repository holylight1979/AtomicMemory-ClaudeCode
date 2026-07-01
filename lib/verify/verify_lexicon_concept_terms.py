"""verify_lexicon_concept_terms.py — realm lexicon 概念詞拒收（systemic realm fix）。

守住 atom_locations._LEXICON_GENERIC_TOKENS 擴充後不變式：context-engineering /
memory-governance 通用概念詞（context rot / selective forgetting / context poisoning /
context engineering …）一律判泛用 → learned 詞庫讀寫兩端拒收，根治「sweep 學概念詞 →
污染未來同詞 atom 誤降 local」的自我強化迴圈。
含實例詞的 local 詞仍照收（需全 token 泛用才拒）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

CLAUDE = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → lib → ~/.claude
for p in (str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

from lib import atom_locations as A  # noqa: E402


def test_context_engineering_concepts_rejected():
    for t in ("context rot", "context engineering", "selective forgetting",
              "context poisoning", "context distraction", "context confusion",
              "context clash", "relevance gate", "memory governance"):
        assert A.is_generic_lexicon_term(t), f"{t} 應判泛用被拒收"


def test_chinese_concept_tokens_rejected():
    for t in ("萃取", "上下文", "汙染", "分心", "遺忘", "上下文工程"):
        assert A.is_generic_lexicon_term(t), f"{t} 應判泛用被拒收"


def test_instance_terms_still_accepted():
    # 含非泛用實例 token → 仍可學（不誤殺真 local 知識）
    for t in ("auto-handoff", "eaddrinuse", "guardian-dashboard", "logs_2.sqlite",
              "wsl2", "gdoc-harvester"):
        assert not A.is_generic_lexicon_term(t), f"{t} 不應被拒收（含實例 token）"


def test_append_rejects_concept_terms(tmp_path, monkeypatch):
    # 寫入端 belt-and-suspenders：append_learned_terms 對概念詞 no-op、實例詞照收
    fake = tmp_path / "_meta" / "realm-lexicon-learned.json"
    monkeypatch.setattr(A, "LEARNED_LEXICON_PATH", fake)
    merged = A.append_learned_terms({
        "context rot": "MemDev/MemoryIndex",
        "selective forgetting": "MemDev/MemoryIndex",
        "wsl2": "OS/Windows/WSL",
    })
    assert "context rot" not in merged
    assert "selective forgetting" not in merged
    assert merged.get("wsl2") == "OS/Windows/WSL"
