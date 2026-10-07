"""verify_conflict_complement.py — R6：衝突偵測對「互補卡」的誤判修法。

1. parse_label：整句一個標籤直接用；否則取回覆裡最早出現的標籤（舊版先找 CONTRADICT）。
2. match_full_text：舊卡有檔就給整段「## 知識」，沒檔退回命中片段。
3. 提示詞含四類定義，且明寫「各說一半＝EXTEND 不是 CONTRADICT」。
免 Ollama。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mcd", ROOT / "tools" / "memory-conflict-detector.py")
mcd = importlib.util.module_from_spec(spec)
sys.modules["mcd"] = mcd
spec.loader.exec_module(mcd)


def test_parse_label_exact_and_earliest():
    assert mcd.parse_label("EXTEND") == "EXTEND"
    assert mcd.parse_label(" extend\n") == "EXTEND"
    # 舊版：只要提到 CONTRADICT 就判矛盾；新版取最早出現者
    assert mcd.parse_label("EXTEND. They do not CONTRADICT each other.") == "EXTEND"
    assert mcd.parse_label("These CONTRADICT; not an EXTEND.") == "CONTRADICT"
    assert mcd.parse_label("I am not sure") == "UNRELATED"
    assert mcd.parse_label("") == "UNRELATED"


def test_match_full_text_reads_knowledge_section(tmp_path):
    f = tmp_path / "card.md"
    f.write_text("# 卡\n\n- Confidence: [臨]\n\n## 知識\n\n- [臨] 甲說一半\n- [臨] 乙說另一半\n\n## 行動\n\n- 做事\n", encoding="utf-8")
    txt = mcd.match_full_text({"file_path": str(f), "text": "只有片段"})
    assert txt.startswith("## 知識") and "乙說另一半" in txt and "做事" not in txt
    assert mcd.match_full_text({"file_path": str(tmp_path / "nope.md"), "text": "只有片段"}) == "只有片段"
    assert mcd.match_full_text({"text": "x" * 2000}, cap=100) == "x" * 100


def test_prompt_defines_extend_for_half_facts(monkeypatch):
    captured = {}

    class _C:
        def chat(self, msgs, system="", timeout=0):
            captured["prompt"] = msgs[0]["content"]
            return "EXTEND"

    monkeypatch.setattr(mcd, "get_client", lambda: _C())
    assert mcd.ollama_classify("A", "a", "[臨]", "B", "b", "[固]") == "EXTEND"
    p = captured["prompt"]
    assert "CONTRADICT: both cannot be true" in p and "each describing half" in p and "index/pointer" in p
