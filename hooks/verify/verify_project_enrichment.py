"""verify_project_enrichment.py — 專案層 vector enrichment 放行契約（ups_search）。

collect_matched_atoms 的 vector 呼叫決策：
- trigger 命中 >0 且有專案層 atom → 仍跑 vector（enrichment），但結果只取
  專案層命中（全域層交給 trigger/BM25），source 標 "vector"
- trigger 命中 >0 且無專案層 atom → 不跑 vector（省 round-trip，維持舊行為）
- 命中 =0 → 全層 fallback（全域 vector 命中照收，與現況一致）

monkeypatch _semantic_search / discover_all_project_memory_dirs，不打真實服務。
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers import ups_search  # noqa: E402

CONFIG = {
    "vector_search": {
        "enabled": True, "global_layer": "bm25",
        "bm25_min_score": 99.0,  # 測試中 BM25 不產生命中，隔離 trigger/vector 兩訊號
    },
}


def _mk_state(tmp_path, with_project: bool):
    proj = tmp_path / "proj"
    (proj / "memory").mkdir(parents=True, exist_ok=True)
    atom_index = {
        "global": [
            ["glob-hit", "memory/glob-hit.md", ["magicword"]],
            ["glob-vec", "memory/glob-vec.md", ["不會匹配的詞"]],
        ],
        "project": (
            [["proj-vec", "memory/proj-vec.md", ["另一個不匹配詞"]]]
            if with_project else []
        ),
        "project_memory_dir": str(proj / "memory") if with_project else "",
        "project_root": str(proj) if with_project else "",
    }
    return {"atom_index": atom_index, "injected_atoms": []}


def _run(tmp_path, monkeypatch, prompt, with_project, sem_results):
    calls = []

    def _fake_sem(p, config, intent="general", user=None, roles=None, session_id=None, layers=None):
        calls.append(p)
        return sem_results

    monkeypatch.setattr(ups_search, "_semantic_search", _fake_sem)
    monkeypatch.setattr(ups_search, "discover_all_project_memory_dirs", lambda: [])
    state = _mk_state(tmp_path, with_project)
    matched, atom_source, *_ = ups_search.collect_matched_atoms(
        "sid", state, CONFIG, prompt, prompt.lower(), [],
    )
    return matched, atom_source, calls


def test_trigger_hit_with_project_runs_enrichment(tmp_path, monkeypatch):
    sem = [("proj-vec", "內容", [], []), ("glob-vec", "內容", [], [])]
    matched, source, calls = _run(
        tmp_path, monkeypatch, "please magicword now", True, sem)
    assert len(calls) == 1  # vector 有跑（enrichment）
    assert source.get("glob-hit") == "trigger"
    assert source.get("proj-vec") == "vector"      # 專案層命中收進來
    assert "glob-vec" not in source                # 全域層 vector 命中被濾掉


def test_trigger_hit_without_project_skips_vector(tmp_path, monkeypatch):
    sem = [("glob-vec", "內容", [], [])]
    matched, source, calls = _run(
        tmp_path, monkeypatch, "please magicword now", False, sem)
    assert calls == []  # 無專案層 → 不跑 vector，省 round-trip
    assert source.get("glob-hit") == "trigger"
    assert "glob-vec" not in source


def test_zero_hits_full_fallback_keeps_global(tmp_path, monkeypatch):
    sem = [("glob-vec", "內容", [], []), ("proj-vec", "內容", [], [])]
    matched, source, calls = _run(
        tmp_path, monkeypatch, "完全無關的話", True, sem)
    assert len(calls) == 1
    assert source.get("glob-vec") == "vector"  # fallback 模式全域照收
    assert source.get("proj-vec") == "vector"
    assert "glob-hit" not in source
