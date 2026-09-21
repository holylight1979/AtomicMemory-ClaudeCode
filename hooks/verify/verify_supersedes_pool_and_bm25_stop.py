"""verify_supersedes_pool_and_bm25_stop.py — Supersedes 全路徑有效性 + BM25 請求框架停用詞 + 排序旋鈕（Phase 2）。

守住：
1. collect_superseded_names：掃池內 `- Supersedes:` 行，鏈式（A 取代 B、B 取代 C）都進集合。
2. UPS 候選池先去掉被取代者：新卡 Related 指回舊卡時 spread_related 不會把舊卡帶回；
   只有舊卡命中、新卡沒命中時舊卡也不出現。歷史查詢（「以前」「被取代」）放行。
3. build_injection_blob（子代理注入）同一規則。
4. _bm25_tokenize 剔除「幫我／我想／請你」等請求框架 bigram；主題 bigram 保留。
5. vector_search.rrf_activation_gain / bm25_gate_max_trigger_hits 旋鈕會被 collect_matched_atoms 讀到。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
from handlers import ups_search  # noqa: E402


def _atom(mem: Path, name: str, triggers: str, extra_meta: str = "", body: str = "- [臨] 內容") -> None:
    (mem / f"{name}.md").write_text(
        f"# {name}\n\n- Scope: global\n- Confidence: [臨]\n- Trigger: {triggers}\n{extra_meta}\n\n## 知識\n\n{body}\n",
        encoding="utf-8")


@pytest.fixture
def pool(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    _atom(mem, "old-way", "部署流程", body="- [臨] 舊做法 deploy-old-token")
    _atom(mem, "new-way", "部署流程", "- Supersedes: old-way\n- Related: old-way", body="- [臨] 新做法 deploy-new-token")
    _atom(mem, "older-way", "舊部署", body="- [臨] 更舊 deploy-older-token")
    _atom(mem, "mid-way", "中間版", "- Supersedes: older-way", body="- [臨] 中間 deploy-mid-token")
    entries = [("old-way", "memory/old-way.md", ["部署流程"]),
               ("new-way", "memory/new-way.md", ["部署流程"]),
               ("older-way", "memory/older-way.md", ["舊部署"]),
               ("mid-way", "memory/mid-way.md", ["中間版"])]
    return tmp_path, [((n, p, t), tmp_path) for n, p, t in entries]


def _state(entries, superseded=None):
    idx = {"global": [(n, p, list(t)) for (n, p, t), _b in entries], "project": [],
           "project_memory_dir": "", "project_root": "", "project_slug": "", "scopes": {}}
    if superseded is not None:
        idx["superseded"] = superseded
    return {"atom_index": idx, "injected_atoms": [], "turn_seq": 0, "session": {"cwd": "", "id": "t"}}


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    # 池以 MEMORY_DIR.parent 為 base：把它指到 tmp，避免掃真實 memory/
    monkeypatch.setattr(ups_search, "MEMORY_DIR", tmp_path / "memory")
    monkeypatch.setattr(ups_search, "_semantic_search", lambda *a, **k: [])
    monkeypatch.setattr(ups_search, "discover_all_project_memory_dirs", lambda: [])


# ─── 1. 集合建構 ──────────────────────────────────────────────────────────────


def test_collect_superseded_names_chain(pool):
    _root, entries = pool
    assert wg_atoms.collect_superseded_names(entries) == {"old-way", "older-way"}


# ─── 2. UPS 池過濾 ─────────────────────────────────────────────────────────────


def test_superseded_not_in_candidates_even_when_only_old_matches(pool):
    root, entries = pool
    state = _state(entries)  # 舊 state 沒有 superseded 欄 → UPS 自己補算
    matched, *_ = ups_search.collect_matched_atoms("t", state, {}, "舊部署 怎麼做", "舊部署 怎麼做", [])
    names = [e[0][0] for e in matched]
    assert "older-way" not in names           # 只有舊卡的 trigger 命中，仍被池過濾
    assert sorted(state["atom_index"]["superseded"]) == ["old-way", "older-way"]


def test_related_spread_does_not_bring_back_superseded(pool):
    root, entries = pool
    state = _state(entries, superseded=["old-way", "older-way"])
    matched, _src, all_atoms, *_ = ups_search.collect_matched_atoms(
        "t", state, {}, "部署流程", "部署流程", [])
    names = [e[0][0] for e in matched]
    assert "new-way" in names and "old-way" not in names
    # Related 擴散從同一個（已過濾的）池取 → new-way.Related=old-way 帶不回來
    related = wg_atoms.spread_related({"new-way"}, all_atoms, [], max_depth=1)
    assert [e[0][0] for e in related] == []


def test_history_query_keeps_superseded(pool):
    root, entries = pool
    state = _state(entries, superseded=["old-way", "older-way"])
    q = "以前的部署流程是怎麼做的"
    matched, *_ = ups_search.collect_matched_atoms("t", state, {}, q, q, [])
    names = [e[0][0] for e in matched]
    assert "old-way" in names and "new-way" in names


# ─── 3. 子代理注入池 ───────────────────────────────────────────────────────────


def test_subagent_blob_excludes_superseded(pool, monkeypatch):
    root, entries = pool
    mem = root / "memory"
    # 讓 build_injection_blob 用 tmp 池：parse_memory_index 走 MEMORY_DIR；superseded 快取以 memory_dir 為 key
    monkeypatch.setattr(wg_atoms, "MEMORY_DIR", mem)
    monkeypatch.setattr(wg_atoms, "parse_memory_index",
                        lambda _d: [e[0] for e in entries])
    wg_atoms._SUPERSEDED_CACHE.clear()
    blob, injected = wg_atoms.build_injection_blob("部署流程", budget=2000)
    assert "new-way" in injected and "old-way" not in injected


# ─── 4. BM25 停用詞 ───────────────────────────────────────────────────────────


def test_bm25_tokenize_drops_request_frame_bigrams():
    toks = wg_atoms._bm25_tokenize("請你幫我查一下部署流程")
    assert "幫我" not in toks and "請你" not in toks and "一下" not in toks
    assert "部署" in toks and "流程" in toks


def test_bm25_request_phrasing_alone_scores_nothing(pool):
    _root, entries = pool
    hits = wg_atoms.bm25_match("幫我想三個晚餐菜色", [e[0] for e in entries], min_score=7.0, top_k=3)
    assert hits == []


# ─── 5. 旋鈕 ──────────────────────────────────────────────────────────────────


def test_ranking_knobs_are_read_from_config(pool, monkeypatch):
    root, entries = pool
    calls = {"gain": None}
    real_exp = ups_search.math.exp

    def _spy_exp(x):
        calls["gain"] = x
        return real_exp(x)

    monkeypatch.setattr(ups_search.math, "exp", _spy_exp)
    state = _state(entries, superseded=[])
    cfg = {"vector_search": {"fusion": "rrf", "rrf_activation_gain": 0, "bm25_gate_max_trigger_hits": 999}}
    ups_search.collect_matched_atoms("t", state, cfg, "部署流程", "部署流程", [])
    assert calls["gain"] == 0  # gain=0 → exp(0*rank)=exp(0)


# ─── Codex #8 反例：否定舊版不是歷史查詢 ─────────────────────────────────────


def test_negating_old_version_is_not_history_query():
    assert not ups_search._is_history_query("不要用以前的部署流程，請照最新版部署")
    assert not ups_search._is_history_query("舊版已被取代，請只提供目前可用的方法")
    assert ups_search._is_history_query("以前的部署流程是怎麼做的")
    assert ups_search._is_history_query("幫我比較舊版和現在的差異")
    assert not ups_search._is_history_query("部署流程")
