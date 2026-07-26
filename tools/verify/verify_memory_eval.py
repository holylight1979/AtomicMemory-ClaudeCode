"""verify_memory_eval.py — tools/memory-eval/ 檢索回歸評估工具契約。

驗證：
  - genqueries template 模式：3 顆假 atom 產出合法 queries（schema/條數/expect）、
    負例數量 = max(1, n//5)、冪等（重跑零變更、加新 atom 只補不動舊）
  - run.retrieve：trigger 優先、BM25 補位受 min_score 控制、合併去重
  - run.evaluate：假索引 + 手工 queries 算出手算可驗的 Recall@1/@3、MRR、
    負例誤注入率、per-atom miss、stale expect 跳過
  - genqueries × run 整合：template 查詢對自己的 atom 檢索 rank ≤ 3

不依賴 Ollama / vector service 在線（全走 template 模式與純函式）。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent  # tools/verify/ → tools/
EVAL_DIR = TOOLS_DIR / "memory-eval"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gq = _load("memory_eval_genqueries", EVAL_DIR / "genqueries.py")
run = _load("memory_eval_run", EVAL_DIR / "run.py")

FAKE_ATOMS = [
    {"name": "alpha", "path": "memory/alpha.md",
     "triggers": ["alpha滑軌", "軌道校準"], "scope": "global"},
    {"name": "beta", "path": "memory/beta.md",
     "triggers": ["beta閘門", "閘門逾時"], "scope": "global"},
    {"name": "gamma", "path": "memory/gamma.md",
     "triggers": ["gamma管線"], "scope": "global"},
]


def _write_index(mem_dir: Path, atoms) -> None:
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "_atom_index.json").write_text(
        json.dumps({"version": "1.0", "atoms": atoms}, ensure_ascii=False),
        encoding="utf-8")


@pytest.fixture
def env(tmp_path):
    """假 claude_dir：memory/_atom_index.json 含 3 顆假 atom。"""
    mem_dir = tmp_path / "memory"
    _write_index(mem_dir, FAKE_ATOMS)
    return tmp_path, mem_dir


def _entries(mem_dir: Path):
    return run.parse_memory_index(mem_dir)


# ─── genqueries：template 生成 ──────────────────────────────────────────────

def test_template_gen_produces_valid_queries(env, tmp_path):
    claude_dir, mem_dir = env
    atoms = gq.load_atoms(mem_dir)
    assert [a["name"] for a in atoms] == ["alpha", "beta", "gamma"]

    rows = gq.generate(atoms, [], "template", claude_dir)
    direct = [r for r in rows if r["cls"] == "direct"]
    neg = [r for r in rows if r["cls"] == "negative"]

    # schema
    for r in rows:
        assert set(r) == {"q", "expect", "cls", "gen"}
        assert isinstance(r["q"], str) and r["q"]
        assert r["gen"] == "template"
        if r["cls"] == "direct":
            assert r["expect"] in {"alpha", "beta", "gamma"}
        else:
            assert r["expect"] is None

    # 條數：≥2 triggers → 3 條；1 trigger → 2 條
    by_atom = {}
    for r in direct:
        by_atom.setdefault(r["expect"], []).append(r["q"])
    assert len(by_atom["alpha"]) == 3
    assert len(by_atom["beta"]) == 3
    assert len(by_atom["gamma"]) == 2
    # 負例：max(1, 3//5) = 1
    assert len(neg) == gq.negatives_needed(3) == 1


def test_gen_idempotent_and_incremental(env):
    claude_dir, mem_dir = env
    atoms = gq.load_atoms(mem_dir)
    rows1 = gq.generate(atoms, [], "template", claude_dir)
    # 冪等：已覆蓋 atom 不重生
    rows2 = gq.generate(atoms, rows1, "template", claude_dir)
    assert rows2 == rows1
    # 增量：加第 4 顆 atom → 舊 queries 原樣保留、只補新
    atoms4 = atoms + [{"name": "delta", "path": "memory/delta.md",
                       "triggers": ["delta快取"]}]
    rows3 = gq.generate(atoms4, rows1, "template", claude_dir)
    assert rows3[:len(rows1)] == rows1
    added = rows3[len(rows1):]
    assert added and all(r["expect"] == "delta" for r in added)


def test_negatives_needed_scaling():
    assert gq.negatives_needed(3) == 1   # 小集合保底 1 條
    assert gq.negatives_needed(10) == 2
    assert gq.negatives_needed(71) == 14


# ─── run.retrieve：合併順序 ─────────────────────────────────────────────────

def test_retrieve_trigger_first_bm25_backfill(env):
    _, mem_dir = env
    entries = _entries(mem_dir)
    # trigger 命中：beta 排最前
    ranked = run.retrieve("閘門逾時要怎麼處理", entries,
                          bm25_min_score=999, bm25_top_k=3)
    assert ranked[0] == "beta"
    # min_score=999 擋掉 BM25 → 無 trigger 命中的 query 全空
    assert run.retrieve("滑軌 校準", entries,
                        bm25_min_score=999, bm25_top_k=3) == []
    # 放行 BM25 → CJK bigram 命中 alpha 的 trigger doc
    ranked = run.retrieve("滑軌 校準", entries,
                          bm25_min_score=0.1, bm25_top_k=3)
    assert "alpha" in ranked


# ─── run.evaluate：手算可驗指標 ─────────────────────────────────────────────

HAND_QUERIES = [
    {"q": "幫我看 alpha滑軌 的問題", "expect": "alpha", "cls": "direct", "gen": "template"},
    {"q": "閘門逾時要怎麼處理", "expect": "beta", "cls": "direct", "gen": "template"},
    {"q": "完全無關的一句話而已", "expect": "gamma", "cls": "direct", "gen": "template"},
    {"q": "今天晚餐吃什麼好呢", "expect": None, "cls": "negative", "gen": "template"},
    {"q": "隨口提到 alpha滑軌 的閒聊", "expect": None, "cls": "negative", "gen": "template"},
]


def test_evaluate_hand_computed_metrics(env):
    _, mem_dir = env
    entries = _entries(mem_dir)
    m = run.evaluate(HAND_QUERIES, entries, bm25_min_score=999, bm25_top_k=3)
    # direct：alpha rank1、beta rank1、gamma miss → 手算
    assert m["n_direct"] == 3 and m["n_negative"] == 2
    assert m["recall_at_1"] == pytest.approx(2 / 3)
    assert m["recall_at_3"] == pytest.approx(2 / 3)
    assert m["mrr"] == pytest.approx(2 / 3)
    # 負例：1/2 誤注入（含 trigger 字串那條命中）
    assert m["neg_injection_rate"] == pytest.approx(0.5)
    # per-atom miss：只有 gamma
    assert set(m["per_atom_miss"]) == {"gamma"}
    assert len(m["per_atom_miss"]["gamma"]) == 1
    assert m["skipped"] == []


def test_evaluate_skips_stale_expect(env):
    _, mem_dir = env
    entries = _entries(mem_dir)
    stale = [{"q": "任何話", "expect": "ghost-atom", "cls": "direct", "gen": "template"}]
    m = run.evaluate(stale, entries, bm25_min_score=999, bm25_top_k=3)
    assert m["n_direct"] == 0
    assert len(m["skipped"]) == 1


# ─── 整合：template 查詢應被自己的 atom 接住 ────────────────────────────────

def test_template_queries_retrieve_own_atom(env):
    claude_dir, mem_dir = env
    atoms = gq.load_atoms(mem_dir)
    entries = _entries(mem_dir)
    rows = gq.generate(atoms, [], "template", claude_dir)
    for r in rows:
        if r["cls"] != "direct":
            continue
        ranked = run.retrieve(r["q"], entries, bm25_min_score=3.5, bm25_top_k=3)
        assert r["expect"] in ranked[:3], f"{r['expect']} 未接住: {r['q']} → {ranked}"


# ─── jsonl 落檔 round-trip ──────────────────────────────────────────────────

def test_save_load_roundtrip(env, tmp_path):
    claude_dir, mem_dir = env
    atoms = gq.load_atoms(mem_dir)
    rows = gq.generate(atoms, [], "template", claude_dir)
    out = tmp_path / "queries.jsonl"
    gq.save(rows, out)
    assert gq.load_existing(out) == rows
    assert run.load_queries(out) == rows


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
