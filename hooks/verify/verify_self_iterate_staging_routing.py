"""verify_self_iterate_staging_routing.py — self-iteration 候選報告落「atom 所屬記憶庫」。

守住：
- _staging_dir_for_atom：全域 atom（memory/、_AIDocs/_atoms/、_AIDocs/Failures/）→ 全域
  memory/_staging；專案 atom（<root>/.claude/memory/、舊址 projects/<slug>/memory/）→ 該庫 _staging。
- _self_iterate_atoms：全域候選不因 cwd 在專案而寫進專案 _staging；全域＋專案候選並存時各寫一份，
  results["reports"] 列出實際路徑、results["forget"] 合併各庫結果。
- apply_selective_forget：候選帶 path 時按 path 定位（atom 散在子目錄，MEMORY_DIR/<slug>.md 找不到）。

跑法：python -m pytest hooks/verify/verify_self_iterate_staging_routing.py -q
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "hooks"))
sys.path.insert(0, str(_ROOT / "lib"))

import wg_atoms  # noqa: E402
import wg_core  # noqa: E402

CFG = {"self_iteration": {"archive_score_threshold": 0.3, "forget": {"enabled": False}}}


def _fake_claude(tmp_path, monkeypatch):
    claude = tmp_path / ".claude"
    mem = claude / "memory"
    mem.mkdir(parents=True)
    for mod in (wg_atoms, wg_core):
        monkeypatch.setattr(mod, "CLAUDE_DIR", claude)
        monkeypatch.setattr(mod, "MEMORY_DIR", mem)
    return claude, mem


def _stale_atom(d: Path, slug: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    md = d / f"{slug}.md"
    md.write_text(f"# {slug}\n\n- Confidence: [臨]\n- Trigger: x\n\n## 知識\n\n- [臨] y\n",
                  encoding="utf-8", newline="\n")
    # 200 天前用過、只有曝光 → score 遠低於 0.3 → 封存候選
    (d / f"{slug}.access.json").write_text(json.dumps({
        "last_used": "2026-01-01", "read_hits": 1, "confirmations": 0}), encoding="utf-8")
    return md


# ─── _staging_dir_for_atom ───────────────────────────────────────────────────

def test_global_roots_route_to_global_staging(tmp_path, monkeypatch):
    claude, mem = _fake_claude(tmp_path, monkeypatch)
    for md in (mem / "OS-Windows" / "a.md",
               claude / "_AIDocs" / "_atoms" / "MemDev" / "b.md",
               claude / "_AIDocs" / "Failures" / "c.md"):
        assert wg_atoms._staging_dir_for_atom(md) == mem / "_staging"


def test_project_roots_route_to_project_staging(tmp_path, monkeypatch):
    claude, mem = _fake_claude(tmp_path, monkeypatch)
    proj_mem = tmp_path / "proj" / ".claude" / "memory"
    assert wg_atoms._staging_dir_for_atom(proj_mem / "shared" / "a.md") == proj_mem / "_staging"
    legacy = claude / "projects" / "d--proj" / "memory"
    assert wg_atoms._staging_dir_for_atom(legacy / "a.md") == legacy / "_staging"


# ─── _self_iterate_atoms 整合 ────────────────────────────────────────────────

def test_global_candidate_ignores_project_cwd(tmp_path, monkeypatch):
    claude, mem = _fake_claude(tmp_path, monkeypatch)
    g = _stale_atom(mem / "OS-Windows", "stale-global")
    proj_mem = tmp_path / "proj" / ".claude" / "memory"
    proj_mem.mkdir(parents=True)
    monkeypatch.setattr(wg_atoms, "iter_atom_files_multi", lambda: iter([g]))
    monkeypatch.setattr(wg_atoms, "log_promotion_heartbeat", lambda **k: None)

    res = wg_atoms._self_iterate_atoms(
        {"session": {"cwd": str(tmp_path / "proj")}}, CFG)

    assert [c["atom"] for c in res["archive_candidates"]] == ["stale-global"]
    assert res["reports"] == [str(mem / "_staging" / "archive-candidates.md")]
    assert (mem / "_staging" / "forget-candidates.md").exists()
    assert not (proj_mem / "_staging").exists()  # 專案庫零污染
    assert res["forget"]["mode"] == "dry_run" and res["forget"]["candidates"] == ["stale-global"]


def test_mixed_candidates_write_one_report_per_library(tmp_path, monkeypatch):
    claude, mem = _fake_claude(tmp_path, monkeypatch)
    g = _stale_atom(mem / "OS-Windows", "stale-global")
    proj_mem = tmp_path / "proj" / ".claude" / "memory"
    p = _stale_atom(proj_mem / "shared", "stale-proj")
    monkeypatch.setattr(wg_atoms, "iter_atom_files_multi", lambda: iter([g, p]))
    monkeypatch.setattr(wg_atoms, "log_promotion_heartbeat", lambda **k: None)

    res = wg_atoms._self_iterate_atoms({"session": {"cwd": ""}}, CFG)

    assert set(res["reports"]) == {
        str(mem / "_staging" / "archive-candidates.md"),
        str(proj_mem / "_staging" / "archive-candidates.md"),
    }
    g_txt = (mem / "_staging" / "archive-candidates.md").read_text(encoding="utf-8")
    p_txt = (proj_mem / "_staging" / "archive-candidates.md").read_text(encoding="utf-8")
    assert "stale-global" in g_txt and "stale-proj" not in g_txt
    assert "stale-proj" in p_txt and "stale-global" not in p_txt
    assert str(date.today()) in g_txt
    assert sorted(res["forget"]["candidates"]) == ["stale-global", "stale-proj"]


# ─── apply_selective_forget 按 path 定位 ─────────────────────────────────────

def test_forget_isolates_by_candidate_path(tmp_path, monkeypatch):
    claude, mem = _fake_claude(tmp_path, monkeypatch)
    monkeypatch.setattr(wg_atoms, "_trigger_sync_memory_index", lambda: None)
    md = _stale_atom(mem / "OS-Windows", "deep")
    cfg = {"self_iteration": {"forget": {"enabled": True, "dry_run": False, "isolate_threshold": 0.3}}}
    res = wg_atoms.apply_selective_forget(
        [{"atom": "deep", "path": str(md), "score": 0.1}], cfg, atoms_dir=mem)
    assert res["forgotten"] == ["deep"]
    assert (mem / "_distant" / "deep.md").exists()
    assert (mem / "_distant" / "deep.access.json").exists()
    assert not md.exists()
