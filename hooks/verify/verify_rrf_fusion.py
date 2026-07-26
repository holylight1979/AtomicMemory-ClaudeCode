"""verify_rrf_fusion.py — 多路檢索 RRF rank 融合（config vector_search.fusion）。

契約：
- rrf_fuse 純函式：score = Σ_routes 1/(k+rank)，多路命中相加、rank 1-based
- collect_matched_atoms fusion="rrf"（預設）：trigger+bm25 雙路命中者排序高於
  單路命中者（相關性融合決定排序）；fusion="legacy" 回退純 ACT-R rank 排序
- 各路 min_score 入場過濾不因融合放寬（BM25 高門檻 → 不進候選）

monkeypatch _semantic_search / discover_all_project_memory_dirs，不打真實服務。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
from handlers import ups_search  # noqa: E402


# ─── rrf_fuse 純函式 ────────────────────────────────────────────────────────


def test_rrf_multi_route_beats_single_route():
    scores = wg_atoms.rrf_fuse({
        "trigger": ["both", "only-trigger"],
        "bm25": ["both"],
    })
    assert scores["both"] > scores["only-trigger"]
    assert scores["both"] == pytest.approx(1 / 61 + 1 / 61)
    assert scores["only-trigger"] == pytest.approx(1 / 62)


def test_rrf_rank_order_within_route():
    scores = wg_atoms.rrf_fuse({"bm25": ["first", "second", "third"]})
    assert scores["first"] > scores["second"] > scores["third"]


def test_rrf_empty_routes():
    assert wg_atoms.rrf_fuse({}) == {}
    assert wg_atoms.rrf_fuse({"trigger": []}) == {}


# ─── collect_matched_atoms 融合排序 ─────────────────────────────────────────


def _mk_state(mem_dir: Path):
    # 兩顆 atom 都被 trigger 命中（trigger 命中 2 ≤2 → BM25 仍會跑）；
    # bm25boost 的 trigger 詞同時是 BM25 語料（trigger+name）強訊號 → 雙路命中。
    atom_index = {
        "global": [
            ["plainatom", "memory/plainatom.md", ["sharedword"]],
            ["bm25boost", "memory/bm25boost.md", ["sharedword", "zebrafusion"]],
        ],
        "project": [],
        "project_memory_dir": "",
        "project_root": "",
    }
    for name in ("plainatom", "bm25boost"):
        (mem_dir / f"{name}.md").write_text(f"# {name}\n\n- 內容\n", encoding="utf-8")
    return {"atom_index": atom_index, "injected_atoms": []}


def _run(tmp_path, monkeypatch, fusion: str, prompt: str):
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ups_search, "discover_all_project_memory_dirs", lambda: [])
    monkeypatch.setattr(ups_search, "_semantic_search",
                        lambda *a, **k: [])
    monkeypatch.setattr(ups_search, "MEMORY_DIR", mem_dir)
    config = {"vector_search": {
        "enabled": True, "global_layer": "bm25",
        "bm25_min_score": 0.1, "bm25_top_k": 3, "fusion": fusion,
    }}
    state = _mk_state(mem_dir)
    (matched, atom_source, _all, _sem, _hints, _alias, _intent, caches
     ) = ups_search.collect_matched_atoms(
        "sid", state, config, prompt, prompt.lower(), [])
    return [e[0][0] for e in matched], atom_source, caches


def test_rrf_multi_route_ranks_first(tmp_path, monkeypatch):
    # 兩顆同為 trigger 命中；bm25boost 因 zebrafusion 再吃 BM25 路 → RRF 排前
    names, source, _ = _run(
        tmp_path, monkeypatch, "rrf", "sharedword zebrafusion please")
    assert source["plainatom"] == "trigger" and source["bm25boost"] == "trigger"
    assert names[0] == "bm25boost"


def test_legacy_fusion_keeps_actr_order(tmp_path, monkeypatch):
    # legacy：無 access sidecar → activation 全 0.0 → stable sort 保持收集順序
    names, _source, _ = _run(
        tmp_path, monkeypatch, "legacy", "sharedword zebrafusion please")
    assert names == ["plainatom", "bm25boost"]


def test_min_score_entry_filter_preserved(tmp_path, monkeypatch):
    # BM25 門檻拉高 → bm25 路無入場者；融合只重排既有候選、不放寬入場
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ups_search, "discover_all_project_memory_dirs", lambda: [])
    monkeypatch.setattr(ups_search, "_semantic_search", lambda *a, **k: [])
    monkeypatch.setattr(ups_search, "MEMORY_DIR", mem_dir)
    config = {"vector_search": {
        "enabled": True, "global_layer": "bm25",
        "bm25_min_score": 99.0, "bm25_top_k": 3, "fusion": "rrf",
    }}
    state = _mk_state(mem_dir)
    (matched, atom_source, *_rest) = ups_search.collect_matched_atoms(
        "sid", state, config, "zebrafusion only", "zebrafusion only", [])
    # 只有 trigger 命中者入場（bm25boost 有 zebrafusion trigger）
    assert [e[0][0] for e in matched] == ["bm25boost"]
    assert atom_source == {"bm25boost": "trigger"}


def test_caches_returned_and_populated(tmp_path, monkeypatch):
    # A1：supersedes 掃描讀過的內文須進 content cache（assemble 段免重讀）
    names, _source, caches = _run(
        tmp_path, monkeypatch, "rrf", "sharedword please")
    assert set(caches.keys()) == {"content", "access"}
    assert any(k.endswith("plainatom.md") for k in caches["content"])
