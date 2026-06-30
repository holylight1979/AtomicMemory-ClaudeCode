"""verify_dedup_stage.py — _drafts 去蕪 DedupStage 安全證成（§3 + 不變式）。

釘死：截斷三訊號**全中**才判（真/假陽性 fixtures，含**真實 draft** 內容防 26% 假陽性覆轍）、
soft-delete **可逆** + 牢籠 cage_assert fail-closed、14 天時間閘、SessionEnd file-lock 拿不到即 skip、
per-env 策略（project 叢集去重 / core 不去重）、零知識損失 subsumption、CI grep 禁索引/詞庫符號。

對映 memory/_staging/next-phase-draft-taxonomy-engine.md §4 不變式：
  INV-DRAFT-STAYS-CAGED / INV-DELETE-IS-SOFT-AND-REVERSIBLE / INV-NO-INDEX-FOR-DRAFT /
  INV-NO-LEXICON-WRITE。全 tmp_path，不碰真磁碟 memory、不喚 LLM、不打真索引。pytest。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

VERIFY_DIR = Path(__file__).resolve().parent     # hooks/verify/
CLAUDE = VERIFY_DIR.parent.parent                # → ~/.claude
if str(CLAUDE) not in sys.path:
    sys.path.insert(0, str(CLAUDE))

import lib.dedup_stage as ds  # noqa: E402
from lib.dedup_stage import (  # noqa: E402
    DedupPolicy, draft_env_for, find_redundant, is_truncated_fragment,
    purge_expired_trash, resolve_dedup_policy, restore_from_trash, soft_delete,
    sweep_drafts,
)
from lib.taxonomy_jury import CAGE_SEGMENT, CageEscapeError  # noqa: E402

_DAY = 86400.0
T0 = 1_750_000_000.0  # 固定時戳基準（不依 wall clock，測試可重現）


def _draft(text: str) -> str:
    """補上 auto-capture 標準骨架外殼（is_truncated 只讀 ## 知識/## 行動，外殼僅為真實感）。"""
    return ("# t\n\n- Scope: global\n- Author: auto-captured\n"
            "- Confidence: [臨]\n- Trigger: auto-capture\n\n" + text)


def _know(body: str, action: str = "- （依知識內容判斷）") -> str:
    return _draft(f"## 知識\n\n{body}\n\n## 行動\n\n{action}\n")


def _write(mem: Path, name: str, text: str, sub: str = "auto-capture") -> Path:
    d = mem / "_drafts" / sub
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text(text, encoding="utf-8")
    return f


# ── 真實 draft 內容（grounded fixtures，防憑採樣斷言）─────────────────────────
REAL_TRUNCATED = _draft(  # 三訊號全中：未閉反引號 + `/` 收尾 + 佔位行動
    "## 知識\n\n- [臨] 【跨層引用缺陷】系統在處理 cross-layer up-refs 時，其 fallback 搜尋範圍"
    "僅限於 `~/.claude/memory` (via rglob)，無法掃描到全局原子儲存的關鍵目錄結構，"
    "如 `~/.claude/_AIDocs/Failures/` 和 `~/.claude/\n\n## 行動\n\n- （依知識內容判斷）\n")
REAL_SIGNAL1_ONLY = _draft(  # 未閉反引號(訊號①) 但 `K` 收尾非連接符(訊號②✗) → 全三不中 → 不判截斷
    "## 知識\n\n- [臨] 【Task 2/3 Pitfall】在 `atom_io.py` 中，第 45 行的註解誤寫為 \"raise "
    "ValueError\"。真正的陷阱是「虛假註解 + 未檢查呼叫方」。修復必須是修正註解，"
    "因為 `atom_io_cli.py` 只捕獲 `TypeError`/`K\n\n## 行動\n\n- （依知識內容判斷）\n")
REAL_COMPLETE = _draft(  # 完整近重複（句尾。、括號平衡、佔位行動）→ 僅訊號③ → 不判截斷
    "## 知識\n\n- [臨] `atom-move.py` 的核心缺陷：它僅使用 `lib.atom_io` 寫入 `.md` 文件，"
    "從頭到尾沒有呼叫任何更新中央 SoT (`_atom_index.json`) 的函數（如 `upsert_atom`），"
    "導致索引資訊無法同步。\n\n## 行動\n\n- （依知識內容判斷）\n")


# ═══ 截斷三訊號：真陽性 ════════════════════════════════════════════════════
def test_truncated_real_positive():
    assert is_truncated_fragment(REAL_TRUNCATED) is True


def test_truncated_synthetic_positive():
    # 未閉 `code + ， 連接符收尾 + 佔位行動
    assert is_truncated_fragment(_know("- [臨] 修法是在 `lib/foo 補上，")) is True


def test_truncated_unclosed_fence_positive():
    body = "- [臨] 範例：\n```python\ndef f(:"        # 未閉 fence + : 收尾
    assert is_truncated_fragment(_know(body)) is True


# ═══ 截斷三訊號：假陽性防線（須回 False）═══════════════════════════════════
def test_real_signal1_only_not_truncated():
    """真實 draft：未閉反引號但非連接符收尾 → 三訊號不全中 → 不判（高精度設計）。"""
    assert is_truncated_fragment(REAL_SIGNAL1_ONLY) is False


def test_real_complete_near_dup_not_truncated():
    """真實完整近重複：僅佔位行動(訊號③)命中 → 不判截斷（交由叢集去重，非截斷清除）。"""
    assert is_truncated_fragment(REAL_COMPLETE) is False


def test_real_action_items_override():
    """有真實行動項（訊號③ False）→ 即使未閉+連接符收尾亦不判（保護 curated atom）。"""
    txt = _know("- [臨] 某知識，", action="- 先寫重現測試\n- 再讓它過")
    assert ds._has_action_placeholder(txt) is False
    assert is_truncated_fragment(txt) is False


def test_complete_sentence_not_truncated():
    assert is_truncated_fragment(_know("- [臨] 這是一條完整且收尾正常的知識。")) is False


def test_placeholder_alone_insufficient():
    """訊號③ 單獨（80/80 draft 皆有）不足以判截斷。"""
    assert ds._has_action_placeholder(_know("- [臨] 完整知識。")) is True
    assert is_truncated_fragment(_know("- [臨] 完整知識。")) is False


# ═══ per-env 策略（§3）════════════════════════════════════════════════════
def test_policy_project_full():
    p = resolve_dedup_policy("project")
    assert p == DedupPolicy(remove_truncated=True, cluster_dedup=True)


def test_policy_core_no_cluster():
    """core 主記憶『近重複=0、碎片吸收』→ 不叢集去重；truncated 仍清（可逆）。"""
    p = resolve_dedup_policy("core")
    assert p.cluster_dedup is False and p.remove_truncated is True


def test_draft_env_detection(tmp_path):
    claude = tmp_path / ".claude"
    assert draft_env_for(claude / "memory", claude) == "core"
    assert draft_env_for(tmp_path / "proj" / ".claude" / "memory" / "shared", claude) == "project"


# ═══ 零知識損失 subsumption 叢集 ══════════════════════════════════════════
def test_find_redundant_subsumption(tmp_path):
    mem = tmp_path / "memory"
    full = _write(mem, "a.md", _know("- [臨] alpha beta gamma delta epsilon 這是完整知識內容收尾。"))
    sub = _write(mem, "b.md", _know("- [臨] alpha beta gamma delta epsilon"))   # 內容字元序列 ⊆ full
    other = _write(mem, "c.md", _know("- [臨] 完全無關的另一主題 zeta eta omega。"))
    drops = dict(find_redundant([full, sub, other]))
    assert sub in drops and drops[sub] == full     # 被涵蓋者 drop、指向 host
    assert full not in drops and other not in drops  # 最完整者 + 無關者 留


def test_find_redundant_exact_dup_keeps_one(tmp_path):
    mem = tmp_path / "memory"
    a = _write(mem, "a.md", _know("- [臨] 一模一樣的內容 xyz。"))
    b = _write(mem, "b.md", _know("- [臨] 一模一樣的內容 xyz。"))
    drops = dict(find_redundant([a, b]))
    assert len(drops) == 1                          # 完全相等只留一份、不全刪


def test_find_redundant_skips_truncated(tmp_path):
    mem = tmp_path / "memory"
    trunc = _write(mem, "t.md", _know("- [臨] alpha beta `lib/foo，"))  # 截斷
    full = _write(mem, "f.md", _know("- [臨] alpha beta gamma 完整。"))
    drops = dict(find_redundant([trunc, full]))
    assert trunc not in drops                        # 截斷者不作叢集錨/不被當冗餘 drop


# ═══ soft-delete 可逆 + 牢籠（INV-DELETE-IS-SOFT / INV-DRAFT-STAYS-CAGED）═══
def test_soft_delete_stays_caged(tmp_path):
    mem = tmp_path / "memory"
    d = _write(mem, "x.md", _know("- [臨] 待刪。"))
    trash = soft_delete(d, mem, reason="truncated", now_ts=T0)
    rel = trash.relative_to(mem)
    assert CAGE_SEGMENT in rel.parts and ds.TRASH in rel.parts
    assert trash.exists() and not d.exists()


def test_soft_delete_reversible(tmp_path):
    mem = tmp_path / "memory"
    orig = _know("- [臨] 可被救回的內容。")
    d = _write(mem, "x.md", orig)
    trash = soft_delete(d, mem, now_ts=T0)
    restored = restore_from_trash(trash, mem)
    assert restored.read_text(encoding="utf-8") == orig    # byte-identical
    assert restored.resolve() == d.resolve()               # 回原位
    assert not trash.exists()                              # trash 物件已移走
    assert not trash.with_name(trash.name + ds.TRASHMETA_SUFFIX).exists()  # sidecar 清


def test_soft_delete_cage_fail_closed(tmp_path, monkeypatch):
    """即使 _drafts_root 被改成指向牢籠外，cage_assert 仍硬擋、原檔不動（fail-closed）。"""
    mem = tmp_path / "memory"
    d = _write(mem, "x.md", _know("- [臨] 內容。"))
    monkeypatch.setattr(ds, "_drafts_root", lambda p: mem / "_AIDocs")  # 無 _drafts 段
    with pytest.raises(CageEscapeError):
        soft_delete(d, mem, now_ts=T0)
    assert d.exists()                                # 未越獄前原檔保留


# ═══ 14 天時間閘（唯一硬刪路徑）════════════════════════════════════════════
def test_purge_respects_ttl(tmp_path):
    mem = tmp_path / "memory"
    old = _write(mem, "old.md", _know("- [臨] 逾期。"))
    young = _write(mem, "young.md", _know("- [臨] 未逾期。"))
    t_old = soft_delete(old, mem, now_ts=T0 - 15 * _DAY)   # 15 天前刪
    t_young = soft_delete(young, mem, now_ts=T0 - 13 * _DAY)  # 13 天前刪
    drafts_root = mem / "_drafts"
    purged = purge_expired_trash(drafts_root, now_ts=T0)
    assert t_old in purged and not t_old.exists()          # 逾 14 天 → 硬刪
    assert t_young.exists()                                # 未逾期 → 保留（可 /refile）
    assert t_young not in purged


def test_purge_empty_trash_noop(tmp_path):
    assert purge_expired_trash(tmp_path / "memory" / "_drafts", now_ts=T0) == []


# ═══ SessionEnd sweep：file-lock 拿不到即 skip ════════════════════════════
def test_sweep_skips_when_locked(tmp_path):
    mem = tmp_path / "memory"
    d = _write(mem, "x.md", REAL_TRUNCATED)
    drafts_root = mem / "_drafts"
    held = ds._try_acquire(drafts_root / ds.SWEEP_LOCK)     # 模擬另一 session 持鎖
    assert held is not None
    try:
        rep = sweep_drafts(drafts_root, mem, env="core", now_ts=T0)
        assert rep["status"] == "skipped-locked"
        assert d.exists()                                  # 拿不到鎖 → 零搬動
    finally:
        ds._release(drafts_root / ds.SWEEP_LOCK, held)


def test_sweep_removes_truncated_both_envs(tmp_path):
    for env in ("core", "project"):
        mem = tmp_path / env / "memory"
        d = _write(mem, "x.md", REAL_TRUNCATED)
        keep = _write(mem, "ok.md", _know("- [臨] 完整知識。"))
        rep = sweep_drafts(mem / "_drafts", mem, env=env, now_ts=T0)
        assert rep["status"] == "ok"
        assert "x.md" in rep["truncated"] and not d.exists()  # 截斷清除（兩 env 皆）
        assert keep.exists()


def test_sweep_cluster_dedup_project_only(tmp_path):
    """project 啟動叢集去重；core 不去重（碎片吸收）。"""
    full = _know("- [臨] alpha beta gamma delta 完整知識主題收尾內容。")
    sub = _know("- [臨] alpha beta gamma delta")              # 內容字元序列 ⊆ full
    # project：被涵蓋者 soft-delete
    pmem = tmp_path / "proj" / "memory"
    pf = _write(pmem, "f.md", full)
    ps = _write(pmem, "s.md", sub)
    prep = sweep_drafts(pmem / "_drafts", pmem, env="project", now_ts=T0)
    assert any(r["drop"] == "s.md" for r in prep["redundant"])
    assert pf.exists() and not ps.exists()
    # core：同樣輸入但不去重
    cmem = tmp_path / "core" / "memory"
    cf = _write(cmem, "f.md", full)
    cs = _write(cmem, "s.md", sub)
    crep = sweep_drafts(cmem / "_drafts", cmem, env="core", now_ts=T0)
    assert crep["redundant"] == []
    assert cf.exists() and cs.exists()                      # core 近重複留原地


def test_sweep_dry_run_moves_nothing(tmp_path):
    mem = tmp_path / "memory"
    d = _write(mem, "x.md", REAL_TRUNCATED)
    rep = sweep_drafts(mem / "_drafts", mem, env="core", now_ts=T0, dry_run=True)
    assert "x.md" in rep["truncated"] and rep["dry_run"] is True
    assert d.exists()                                      # 只算不搬


def test_sweep_no_drafts_dir(tmp_path):
    rep = sweep_drafts(tmp_path / "memory" / "_drafts", tmp_path / "memory",
                       env="core", now_ts=T0)
    assert rep["status"] == "no-drafts-dir"


# ═══ 軸隔離：sweep 不碰索引/詞庫（INV-NO-INDEX-FOR-DRAFT / INV-NO-LEXICON-WRITE）═
def test_sweep_untouches_index_and_lexicon(tmp_path):
    mem = tmp_path / "memory"
    _write(mem, "x.md", REAL_TRUNCATED)
    idx = mem / "_atom_index.json"
    idx.write_text('{"atoms":[]}', encoding="utf-8")
    lex = mem / "_meta" / "realm-lexicon-learned.json"
    lex.parent.mkdir(parents=True, exist_ok=True)
    lex.write_text('{"terms":{}}', encoding="utf-8")
    before = (idx.read_text(), idx.stat().st_mtime_ns,
              lex.read_text(), lex.stat().st_mtime_ns)
    sweep_drafts(mem / "_drafts", mem, env="project", now_ts=T0)
    after = (idx.read_text(), idx.stat().st_mtime_ns,
             lex.read_text(), lex.stat().st_mtime_ns)
    assert before == after                                 # 索引/詞庫 byte+mtime 不變


# ═══ CI grep：禁索引寫入 / 詞庫學習符號（物理零相關 import）═══════════════
def test_no_forbidden_symbols():
    """INV-DRAFT-STAYS-CAGED：dedup_stage.py 不得引用索引寫入/詞庫學習/realm 搬移符號。"""
    src = (CLAUDE / "lib" / "dedup_stage.py").read_text(encoding="utf-8")
    for sym in ("append_learned_terms", "write_atom", "upsert_atom", "set_realm"):
        assert sym not in src, f"dedup_stage.py 不得出現 {sym!r}（違反四軸分離/牢籠）"
