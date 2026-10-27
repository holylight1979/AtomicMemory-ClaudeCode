"""verify_injection_slim.py — 開場與每則提示的注入瘦身（只動「印不印、印多長」，判斷與寫入照舊）。

開場（handlers/session_start）：
  - [Guardian:覆轍] 不再開場印（same_file_3x 只留 episodic 卡寫入）
  - [AIDocs] 文件清單 → 一行指 _AIDocs/_INDEX.md
  - 本地範疇 Catalog 整表 → 一行指 memory/_local_catalog.md
  - [Guardian:ScopeLayout] 長段 → 一行
每則（handlers/ups_context、wg_parallel、wg_research、wg_atoms）：
  - [Parallel:Suggest]／[Research:Fanout] 只在強訊號出（config 門檻），每 session 最多 2 次
  - [Proactive] 每 session 最多 1 次
  - [Session:Context] 只在第一則出；每筆截 80 字、最多 2 筆
  - [Guardian:AIDocs] 最多 1 條，命中 ≥ aidocs.min_prompt_hits 才出，同一份文件一 session 只指一次

怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_injection_slim.py
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_ROOT = HOOKS_DIR.parent
for p in (HOOKS_DIR, HOOKS_DIR / "handlers", CLAUDE_ROOT, CLAUDE_ROOT / "lib"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import wg_atoms  # noqa: E402
import wg_parallel  # noqa: E402
import wg_research  # noqa: E402
from handlers import session_start as ss  # noqa: E402
from handlers import ups_context  # noqa: E402

CONFIG = json.loads((CLAUDE_ROOT / "workflow" / "config.json").read_text(encoding="utf-8"))

# 今天實況等級的一般請求：parallel score 2～5、research 只有檢索動詞＋一兩個知識詞
WEAK_PARALLEL = "幫我盤點 hooks/a.py、hooks/b.py 兩個檔的錯誤處理，順便整理測試"       # 連接詞×2+跨目標+複數+多檔 = 5
STRONG_PARALLEL = "全部的 hooks/a.py、hooks/b.py 都要重構，同時三個模組的測試也要補齊"  # +批量 → 7
WEAK_RESEARCH = "幫我查一下 LanceDB 的用法"                                            # 檢索動詞×1 + 知識域×1
STRONG_RESEARCH = "幫我查、研究一下 LanceDB 跟 Qdrant 的差別與選型比較，官方文件怎麼說"  # 動詞×2 + 知識域×5


# ─── 開場 ──────────────────────────────────────────────────────────────────

def test_session_start_no_rut_signal_block():
    """覆轍訊號是開發期訊號，開場不再印；wg_evasion 的偵測函式留給 episodic／測試用。"""
    src = inspect.getsource(ss.handle_session_start)
    assert "_detect_rut_patterns" not in src
    assert "覆轍" not in src


def test_session_start_aidocs_one_line():
    entries = [(f"Doc{i}.md", f"說明 {i}", ["kw"]) for i in range(18)]
    out = ss._aidocs_opening_lines(entries, "C:/proj")
    assert len(out) == 1
    assert "Read _AIDocs/_INDEX.md" in out[0]
    assert "Doc0.md" not in out[0] and "Doc17.md" not in out[0]
    assert ss._aidocs_opening_lines([], "C:/proj") == ["[Guardian] No _AIDocs found. Run /init-project to create."] \
        or ss._aidocs_opening_lines([], "C:/proj") == []


def test_session_start_local_catalog_one_line(tmp_path, monkeypatch):
    lc = tmp_path / "_local_catalog.md"
    lc.write_text("# 本地範疇 Catalog\n\n| 範疇 | atom 數 |\n|---|---|\n" + "\n".join(f"| Lv{i} | {i} |" for i in range(40)),
                  encoding="utf-8")
    monkeypatch.setattr(ss, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(ss, "_is_under_claude_dir", lambda cwd: True)
    out = ss._local_catalog_lines("C:/u/.claude")
    assert len(out) == 1 and "\n" not in out[0]
    assert "_local_catalog.md" in out[0]
    assert "| Lv3 |" not in out[0]
    monkeypatch.setattr(ss, "_is_under_claude_dir", lambda cwd: False)
    assert ss._local_catalog_lines("D:/proj") == []


def test_scope_layout_one_line(tmp_path):
    mem = tmp_path / "proj" / ".claude" / "memory"
    (mem / "shared").mkdir(parents=True)
    (mem / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": []}), encoding="utf-8")
    out = ss._scope_layout_advisory(mem)
    assert len(out) == 1 and out[0].startswith("[Guardian:ScopeLayout]")
    assert len(out[0]) <= 60, out[0]
    assert "整理記憶分類" in out[0]


# ─── 每則：並行／研究建議 ──────────────────────────────────────────────────────

def _st(turn: int = 5) -> dict:
    return {"topic_tracker": {"prompt_count": turn}}


def test_parallel_suggest_silent_on_weak_signal():
    cfg = {"parallel_agents": CONFIG["parallel_agents"]}
    score, _ = wg_parallel.score_prompt(WEAK_PARALLEL)
    assert 2 <= score <= 5, score
    assert wg_parallel.detect_parallel_opportunity(WEAK_PARALLEL, _st(), cfg) is None
    assert wg_parallel.detect_parallel_opportunity(STRONG_PARALLEL, _st(), cfg) is not None
    assert CONFIG["parallel_agents"]["min_score"] >= 6 and "_doc" in CONFIG["parallel_agents"]


def test_parallel_suggest_max_twice_per_session(monkeypatch):
    monkeypatch.setenv("WG_V6", "0")      # 關掉 v6_once，單測 max_per_session
    cfg = {"parallel_agents": {"min_score": 1, "cooldown_turns": 0}}
    st = _st(0)
    fired = []
    for turn in range(6):
        st["topic_tracker"]["prompt_count"] = turn
        fired.append(wg_parallel.detect_parallel_opportunity(STRONG_PARALLEL, st, cfg) is not None)
    assert fired.count(True) == 2 and fired[:2] == [True, True], fired


def test_research_fanout_silent_on_weak_signal():
    cfg = {"research_fanout": CONFIG["research_fanout"]}
    assert wg_research.classify(WEAK_RESEARCH)[0] is not None       # 判斷邏輯照舊：仍會判成檢索型
    assert wg_research.detect_research_fanout(WEAK_RESEARCH, _st(), cfg) is None
    assert wg_research.detect_research_fanout(STRONG_RESEARCH, _st(), cfg) is not None
    assert "min_signal_hits" in CONFIG["research_fanout"] and "_doc" in CONFIG["research_fanout"]


def test_research_fanout_max_twice_per_session():
    cfg = {"research_fanout": {"min_signal_hits": 1, "cooldown_turns": 0}}
    st = _st(0)
    fired = []
    for turn in range(6):
        st["topic_tracker"]["prompt_count"] = turn
        fired.append(wg_research.detect_research_fanout(STRONG_RESEARCH, st, cfg) is not None)
    assert fired.count(True) == 2 and fired[:2] == [True, True], fired


# ─── 每則：Proactive／Session:Context／AIDocs ──────────────────────────────────

def _episodics(n: int = 4) -> list:
    return [{"atom_name": f"episodic-2026-10-2{i}-s{i}", "created": f"2026-10-2{i}",
             "summary": ("向量服務 " * 60).strip(), "confirmations": 0} for i in range(n)]


def test_proactive_once_per_session(monkeypatch):
    monkeypatch.setattr(wg_atoms, "_detect_cross_session_patterns", lambda eps, prompt: ["向量服務"])
    state = {"atom_index": {"global": [], "project": []}}
    first = wg_atoms._proactive_classify(state, _episodics(), "向量服務", {})
    assert any("[Proactive]" in ln for ln in first)
    second = wg_atoms._proactive_classify(state, _episodics(), "向量服務", {})
    assert not any("[Proactive]" in ln for ln in second)


def test_session_context_first_prompt_only(monkeypatch):
    monkeypatch.setattr(ups_context, "_search_episodic_context", lambda *a, **k: _episodics())
    monkeypatch.setattr(ups_context, "_proactive_classify", lambda *a, **k: [])
    monkeypatch.setattr(ups_context, "_record_episodic_exposure", lambda *a, **k: None)
    state = {"session": {"cwd": "D:/x"}, "topic_tracker": {"prompt_count": 1}}

    def run(prompt: str) -> list:
        lines: list = []
        ups_context.build_context("sid", state, {}, prompt, prompt, prompt.lower(), 3000, lines)
        return lines

    first = run("向量服務怎麼起")
    ctx = [ln for ln in first if ln.startswith("[Session:Context]")]
    assert len(ctx) == 1
    rows = [ln for ln in first if ln.startswith("- [")]
    assert len(rows) <= 2 and rows
    for row in rows:
        summary = row.split(": ", 1)[1]
        assert len(summary) <= 80, row
    second = run("向量服務怎麼起")
    assert not any("[Session:Context]" in ln for ln in second)
    assert not any(ln.startswith("- [") for ln in second)


def test_aidocs_pointer_at_most_one(monkeypatch):
    monkeypatch.setenv("WG_V6", "0")
    state = {
        "session_context_injected": True, "session": {"cwd": "D:/x"}, "topic_tracker": {"prompt_count": 1},
        "aidocs": {"project_root": "C:/p",
                   "entries": [("Routing.md", "路由表怎麼排"), ("Cache.md", "快取層"), ("Vec.md", "向量")],
                   "keywords": {"Routing.md": ["routing", "路由"], "Cache.md": ["cache", "快取"], "Vec.md": ["vector"]}},
    }

    def run(prompt: str) -> str:
        lines: list = []
        ups_context.build_context("sid", state, {}, prompt, prompt, prompt.lower(), 3000, lines)
        return "\n".join(lines)

    # 單一關鍵字命中（分數不明顯）→ 不出
    assert "[Guardian:AIDocs]" not in run("routing 表少一列")
    # 兩份都兩個關鍵字命中 → 只給 1 條
    out = run("routing 路由 跟 cache 快取 一起看")
    assert out.count("→ Read") == 1 and "[Guardian:AIDocs]" in out
    # 同一份不重指：再問一次不出
    assert "[Guardian:AIDocs]" not in run("routing 路由 再看一次")
