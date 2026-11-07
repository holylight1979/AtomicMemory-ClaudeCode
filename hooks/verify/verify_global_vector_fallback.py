"""verify_global_vector_fallback.py — 全域層走向量時，向量這次沒結果要退回 BM25，不讓全域層只剩 trigger。

做什麼：釘住 ups_search.collect_matched_atoms 的三條路（global_layer=vector 有結果、沒結果、global_layer=bm25）；
  服務連不上時拿掉就緒旗標、只是逾時就留著。
怎麼跑：python -m pytest hooks/verify/verify_global_vector_fallback.py -q
"""
from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
ROOT = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(ROOT), str(ROOT / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
from handlers import ups_search  # noqa: E402

CARD = "alpha-card"
ENTRY = (CARD, f"memory/{CARD}.md", ["不會命中的觸發詞"])


@pytest.fixture
def state(tmp_path, monkeypatch):
    memory = tmp_path / "memory"
    memory.mkdir()
    (memory / f"{CARD}.md").write_text(
        f"# {CARD}\n\n- Scope: global\n- Confidence: [臨]\n- Trigger: 不會命中的觸發詞\n\n## 知識\n\n- [臨] 內容\n",
        encoding="utf-8")
    monkeypatch.setattr(ups_search, "MEMORY_DIR", memory)
    monkeypatch.setattr(ups_search, "discover_all_project_memory_dirs", lambda: [])
    index = {"global": [ENTRY], "project": [], "project_memory_dir": "", "project_root": "", "project_slug": "", "scopes": {}}
    return {"atom_index": index, "injected_atoms": [], "turn_seq": 0, "session": {"cwd": "", "id": "t"}}


def run(state, monkeypatch, global_layer, vector_hits):
    calls = []

    def fake_bm25(prompt, entries, **kwargs):
        calls.append("bm25")
        return [e for e in entries if e[0] == CARD]

    monkeypatch.setattr(ups_search, "bm25_match", fake_bm25)
    monkeypatch.setattr(ups_search, "_semantic_search", lambda *a, **k: (calls.append("vector"), vector_hits)[1])
    config = {"vector_search": {"global_layer": global_layer, "bm25_gate_max_trigger_hits": 2}}
    matched, sources, *_ = ups_search.collect_matched_atoms("t", state, config, "換句話問的問題", "換句話問的問題", [])
    return [e[0][0] for e in matched], sources, calls


def test_vector_empty_falls_back_to_bm25(state, monkeypatch):
    names, sources, calls = run(state, monkeypatch, "vector", [])
    assert calls == ["vector", "bm25"]        # 先問向量，沒結果才退回
    assert CARD in names and sources[CARD] == "bm25"


def test_vector_hit_does_not_run_bm25(state, monkeypatch):
    names, sources, calls = run(state, monkeypatch, "vector", [(CARD, 0.9, "global", [])])
    assert calls == ["vector"]
    assert CARD in names and sources[CARD] == "vector"


def test_bm25_mode_keeps_running_bm25_first(state, monkeypatch):
    names, sources, calls = run(state, monkeypatch, "bm25", [])
    assert calls[0] == "bm25"
    assert CARD in names and sources[CARD] == "bm25"


@pytest.mark.parametrize("error, flag_kept", [
    (urllib.error.URLError(ConnectionRefusedError(10061, "refused")), False),   # 服務掛了：拿掉旗標，下一句走自癒
    (urllib.error.URLError(TimeoutError("timed out")), True),                    # 只是忙：旗標留著，下一句照問
])
def test_refused_connection_drops_ready_flag(tmp_path, monkeypatch, error, flag_kept):
    search_module = sys.modules[wg_atoms._semantic_search.__module__]
    monkeypatch.setattr(search_module, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(search_module, "_log_vector_obs", lambda *a, **k: None)
    flag = tmp_path / "vector_ready.flag"
    flag.write_text("ready", encoding="utf-8")

    def refuse(*_a, **_k):
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert wg_atoms._semantic_search("q", {"vector_search": {"service_port": 1}}, session_id="t") == []
    assert flag.exists() is flag_kept
