"""verify_atom_categorize.py — tools/atom-categorize.py plan/apply/undo 在 tmp 樹上的守門。

不變式：
1. index 是 SoT：對映的 slug 不在 index → error；index path 指向不存在的檔 → error。
2. 目標名走 taxonomy 閉合清單 + validate_category_path：未知 Lv1／保留名／未知 Failures 主題 → error；
   別名（vcs）snap 回正名（版控）。
3. 撞名（目標已存在、或兩顆 casefold 後同路徑）→ error；plan 有 error 則 apply 拒跑。
4. apply：.md 與 .access.json 原子同搬、index path 改寫、undo.json 落地、來源空目錄鏈清掉。
5. undo：逐字還原原路徑（含舊址 _AIDocs/Failures/）、index 還原、範疇空目錄清掉。
6. 專案層（--memory-dir）：根＝shared/、path 前綴 memory/shared/；local:／Failures/ 目標拒。
7. 未列入對映的根下散檔一律浮出（unmapped），不靜默略過。

全程 tmp 隔離：GLOBAL_MEMORY_DIR 指向 tmp、audit log 斷開；local: realm 的 apply 委派真實
atom-set-realm（動現役 index），故只測 plan 面。
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

SCRIPT = CLAUDE_DIR / "tools" / "atom-categorize.py"
SPEC = importlib.util.spec_from_file_location("atom_categorize", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

ATOM = "# {slug}\n\n- Scope: {scope}\n- Confidence: [臨]\n- Trigger: {slug}\n\n## 知識\n\n- [臨] x\n"


@pytest.fixture(autouse=True)
def _silence_audit(monkeypatch):
    import lib.atom_access as AAC
    import lib.atom_io as AIO
    monkeypatch.setattr(AIO, "_audit_log", lambda *a, **k: None)
    monkeypatch.setattr(AAC, "_audit_log", lambda *a, **k: None)
    monkeypatch.setattr(MOD, "_audit_log", lambda *a, **k: None)


def _mk(root: Path, rel: str, slug: str, scope: str = "global", sidecar: bool = True) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(ATOM.format(slug=slug, scope=scope), encoding="utf-8")
    if sidecar:
        p.with_suffix(".access.json").write_text(
            json.dumps({"schema": "atom-access-v3", "read_hits": 7}), encoding="utf-8")
    return p


def _index(mem: Path, rows):
    (mem / "_atom_index.json").write_text(json.dumps(
        {"version": "1.0", "atoms": [
            {"name": n, "path": p, "triggers": [n], "scope": sc} for n, p, sc in rows]},
        ensure_ascii=False, indent=2), encoding="utf-8")


def _entry(mem: Path, slug: str) -> dict:
    data = json.loads((mem / "_atom_index.json").read_text(encoding="utf-8"))
    return next(a for a in data["atoms"] if a["name"] == slug)


@pytest.fixture
def gtree(tmp_path, monkeypatch) -> Path:
    """假 ~/.claude：memory/{flat-a, flat-b, keep}.md + _AIDocs/Failures/feedback-f.md + local 一顆。"""
    root = tmp_path / "claude"
    mem = root / "memory"
    mem.mkdir(parents=True)
    (mem / "MEMORY.md").write_text("# idx\n", encoding="utf-8")
    _mk(root, "memory/flat-a.md", "flat-a")
    _mk(root, "memory/flat-b.md", "flat-b", sidecar=False)
    _mk(root, "memory/keep.md", "keep")
    _mk(root, "_AIDocs/Failures/feedback-f.md", "feedback-f")
    _mk(root, "_AIDocs/_atoms/MemDev/dev-note.md", "dev-note")
    _index(mem, [
        ("flat-a", "memory/flat-a.md", "global"),
        ("flat-b", "memory/flat-b.md", "global"),
        ("keep", "memory/keep.md", "global"),
        ("feedback-f", "_AIDocs/Failures/feedback-f.md", "global"),
        ("dev-note", "_AIDocs/_atoms/MemDev/dev-note.md", "global"),
    ])
    monkeypatch.setattr(MOD, "GLOBAL_MEMORY_DIR", mem)
    return root


@pytest.fixture
def ptree(tmp_path) -> Path:
    """假專案：<proj>/.claude/memory/shared/{pa,pb}.md（平鋪）+ shared/Done/pc.md（已歸類）。"""
    proj = tmp_path / "proj"
    mem = proj / ".claude" / "memory"
    (mem / "shared").mkdir(parents=True)
    (mem / "MEMORY.md").write_text("# idx\n", encoding="utf-8")
    _mk(proj / ".claude", "memory/shared/pa.md", "pa", scope="shared")
    _mk(proj / ".claude", "memory/shared/git-hunk.md", "git-hunk", scope="shared")
    _mk(proj / ".claude", "memory/shared/Done/pc.md", "pc", scope="shared")
    _index(mem, [
        ("pa", "memory/shared/pa.md", "shared"),
        ("git-hunk", "memory/shared/git-hunk.md", "shared"),
        ("pc", "memory/shared/Done/pc.md", "shared"),
    ])
    return proj


# ─── plan：全域版面 ───────────────────────────────────────────────────────────


def test_plan_global_resolves_core_failures_local_and_flags_unmapped(gtree):
    layout = MOD.Layout(gtree / "memory")
    assert layout.is_global
    plan = MOD.build_plan(layout, {
        "flat-a": "vcs/git",                  # 別名 → 版控；Lv2 對 taxonomy 宣告 sub snap → Git
        "flat-b": "Failures/驗證與實證",       # 舊址無關：來源在 memory/ 也可進失敗家族
        "feedback-f": "Failures/工作流",
        "dev-note": "local:MemDev",           # 已在 local 同 domain → noop
    }, {"_AIDocs/Failures/env-traps.md": "memory/Failures/_reference/env-traps.md"})
    assert plan["errors"] == []
    by = {i["slug"]: i for i in plan["items"]}
    assert by["flat-a"]["action"] == "move" and by["flat-a"]["to"] == "memory/版控/Git/flat-a.md"
    assert by["flat-a"]["sidecar"] is True and by["flat-b"]["sidecar"] is False
    assert by["flat-b"]["to"] == "memory/Failures/驗證與實證/flat-b.md"
    assert by["feedback-f"]["to"] == "memory/Failures/工作流/feedback-f.md"
    assert by["dev-note"]["action"] == "noop"
    assert plan["unmapped"] == ["keep"]                       # 根下散檔未列入 → 浮出
    assert plan["reference_git_mv"][0]["exists"] is False     # 參考文件只列清單、標存在性
    assert plan["counts"]["move"] == 3 and plan["counts"]["noop"] == 1


def test_plan_global_realm_target_for_core_atom(gtree):
    layout = MOD.Layout(gtree / "memory")
    plan = MOD.build_plan(layout, {"keep": "local:MemDev"}, {})
    assert plan["errors"] == []
    it = plan["items"][0]
    assert it["action"] == "realm" and it["domain"] == "MemDev" and it["from"] == "memory/keep.md"


@pytest.mark.parametrize("target,needle", [
    ("Nope/x", "unknown Lv1"),
    ("templates", "unknown Lv1"),               # 保留名不在 taxonomy → 閉合清單先擋
    ("版控/_archive", "reserved"),               # Lv2 保留名
    ("Failures", "needs a topic"),
    ("Failures/不存在主題", "unknown Failures topic"),
    ("", "empty target"),
])
def test_plan_rejects_bad_targets(gtree, target, needle):
    layout = MOD.Layout(gtree / "memory")
    plan = MOD.build_plan(layout, {"flat-a": target}, {})
    assert plan["items"] == []
    assert len(plan["errors"]) == 1 and needle in plan["errors"][0], plan["errors"]


def test_plan_rejects_missing_slug_and_missing_file(gtree):
    layout = MOD.Layout(gtree / "memory")
    (gtree / "memory" / "flat-b.md").unlink()
    plan = MOD.build_plan(layout, {"ghost": "版控", "flat-b": "版控"}, {})
    assert any("ghost: not in index" in e for e in plan["errors"])
    assert any("flat-b: index path missing on disk" in e for e in plan["errors"])


def test_plan_rejects_collisions(gtree):
    layout = MOD.Layout(gtree / "memory")
    _mk(gtree, "memory/版控/flat-a.md", "flat-a")  # 目標已被占
    plan = MOD.build_plan(layout, {"flat-a": "版控"}, {})
    assert any("target already exists" in e for e in plan["errors"])
    # 兩顆 casefold 後同路徑（Windows 不分大小寫）
    _mk(gtree, "memory/Flat-A.md", "Flat-A")
    _index(gtree / "memory", [("flat-a", "memory/flat-a.md", "global"),
                              ("Flat-A", "memory/Flat-A.md", "global")])
    plan = MOD.build_plan(layout, {"flat-a": "設計通則", "Flat-A": "設計通則"}, {})
    assert any("collides" in e for e in plan["errors"])


# ─── apply / undo ────────────────────────────────────────────────────────────


def test_apply_moves_md_sidecar_index_and_writes_undo_then_undo_restores(gtree, tmp_path):
    mem = gtree / "memory"
    layout = MOD.Layout(mem)
    amap = {"flat-a": "版控/Git", "flat-b": "工作流/節奏與收尾", "feedback-f": "Failures/工作流"}
    plan = MOD.build_plan(layout, amap, {})
    assert plan["errors"] == []
    undo_file = tmp_path / "undo.json"
    res = MOD.apply_plan(layout, plan, undo_file)
    assert res["failed"] == [] and res["validate_errors"] == [], res
    assert res["applied"] == 3 and undo_file.exists()
    # 實體 + sidecar
    assert (mem / "版控" / "Git" / "flat-a.md").exists()
    assert (mem / "版控" / "Git" / "flat-a.access.json").exists()
    assert not (mem / "flat-a.md").exists() and not (mem / "flat-a.access.json").exists()
    assert (mem / "Failures" / "工作流" / "feedback-f.md").exists()
    assert (mem / "Failures" / "工作流" / "feedback-f.access.json").exists()
    # index path 改寫、scope 不動、其他條目不受影響
    assert _entry(mem, "flat-a")["path"] == "memory/版控/Git/flat-a.md"
    assert _entry(mem, "flat-a")["scope"] == "global"
    assert _entry(mem, "feedback-f")["path"] == "memory/Failures/工作流/feedback-f.md"
    assert _entry(mem, "keep")["path"] == "memory/keep.md"
    # undo.json 內容可反向
    payload = json.loads(undo_file.read_text(encoding="utf-8"))
    assert {e["slug"] for e in payload["entries"]} == set(amap)
    assert all(e["from"] and e["to"] for e in payload["entries"])

    back = MOD.undo_apply(layout, payload, dry_run=False)
    assert back["failed"] == [] and back["reverted"] == 3, back
    assert (mem / "flat-a.md").exists() and (mem / "flat-a.access.json").exists()
    assert (gtree / "_AIDocs" / "Failures" / "feedback-f.md").exists()
    assert (gtree / "_AIDocs" / "Failures" / "feedback-f.access.json").exists()
    assert _entry(mem, "flat-a")["path"] == "memory/flat-a.md"
    assert _entry(mem, "feedback-f")["path"] == "_AIDocs/Failures/feedback-f.md"
    # 範疇空目錄鏈清掉（memory 根本身保留）
    assert not (mem / "版控").exists() and not (mem / "Failures").exists() and mem.is_dir()


def test_apply_refused_when_plan_has_errors(gtree, tmp_path):
    mem = gtree / "memory"
    mp = tmp_path / "bad.json"
    mp.write_text(json.dumps({"flat-a": "版控", "ghost": "版控"}), encoding="utf-8")
    rc = MOD.main(["apply", "--map", str(mp), "--memory-dir", str(mem)])
    assert rc == 1
    assert (mem / "flat-a.md").exists()          # 一顆都沒動
    assert not list(tmp_path.rglob("*.undo.json"))


def test_apply_dry_run_touches_nothing(gtree, tmp_path):
    mem = gtree / "memory"
    mp = tmp_path / "ok.json"
    mp.write_text(json.dumps({"atoms": {"flat-a": "版控"}}), encoding="utf-8")
    rc = MOD.main(["apply", "--map", str(mp), "--memory-dir", str(mem), "--dry-run"])
    assert rc == 0
    assert (mem / "flat-a.md").exists() and not (mem / "版控").exists()
    assert _entry(mem, "flat-a")["path"] == "memory/flat-a.md"


def test_undo_dry_run_and_occupied_original(gtree, tmp_path):
    mem = gtree / "memory"
    layout = MOD.Layout(mem)
    plan = MOD.build_plan(layout, {"flat-a": "版控"}, {})
    undo_file = tmp_path / "u.json"
    MOD.apply_plan(layout, plan, undo_file)
    payload = json.loads(undo_file.read_text(encoding="utf-8"))
    dry = MOD.undo_apply(layout, payload, dry_run=True)
    assert dry["reverted"] == 1 and (mem / "版控" / "flat-a.md").exists()
    _mk(gtree, "memory/flat-a.md", "flat-a")     # 原位被占 → 拒還原、不覆蓋
    res = MOD.undo_apply(layout, payload, dry_run=False)
    assert res["reverted"] == 0 and any("occupied" in f for f in res["failed"])


# ─── 專案層（--memory-dir） ──────────────────────────────────────────────────


def test_project_layer_plan_uses_shared_root_and_rejects_global_only_targets(ptree):
    mem = ptree / ".claude" / "memory"
    layout = MOD.Layout(mem)
    assert not layout.is_global and layout.core_root == mem / "shared"
    plan = MOD.build_plan(layout, {"pa": "驗證與實證", "git-hunk": "vcs"}, {})
    assert plan["errors"] == []
    by = {i["slug"]: i for i in plan["items"]}
    assert by["pa"]["to"] == "memory/shared/驗證與實證/pa.md"
    assert by["git-hunk"]["to"] == "memory/shared/版控/git-hunk.md"
    assert plan["unmapped"] == []                             # pc 已在 shared/Done/ → 非散檔
    bad = MOD.build_plan(layout, {"pa": "local:MemDev", "git-hunk": "Failures/工作流"}, {})
    assert len(bad["errors"]) == 2
    assert any("global layer" in e for e in bad["errors"])


def test_project_layer_apply_undo_keeps_shared_dir(ptree, tmp_path):
    mem = ptree / ".claude" / "memory"
    layout = MOD.Layout(mem)
    plan = MOD.build_plan(layout, {"pa": "驗證與實證"}, {})
    undo_file = tmp_path / "p.undo.json"
    res = MOD.apply_plan(layout, plan, undo_file)
    assert res["failed"] == [] and (mem / "shared" / "驗證與實證" / "pa.md").exists()
    assert _entry(mem, "pa")["path"] == "memory/shared/驗證與實證/pa.md"
    assert _entry(mem, "pa")["scope"] == "shared"
    back = MOD.undo_apply(layout, json.loads(undo_file.read_text(encoding="utf-8")), dry_run=False)
    assert back["failed"] == [] and (mem / "shared" / "pa.md").exists()
    assert (mem / "shared").is_dir() and not (mem / "shared" / "驗證與實證").exists()


def test_project_layer_plan_without_map_proposes_from_lexicon(ptree):
    layout = MOD.Layout(ptree / ".claude" / "memory")
    prop = MOD.propose_map(layout)
    assert prop.get("proposed") is True
    assert prop["atoms"].get("git-hunk") == "版控"          # name 命中詞庫 git/hunk
    assert "pa" in prop["undecided"]                         # 0 分不猜


def test_cli_plan_project_layer_exit0_no_traceback(ptree, tmp_path):
    mem = ptree / ".claude" / "memory"
    mp = tmp_path / "m.json"
    mp.write_text(json.dumps({"atoms": {"pa": "驗證與實證"}}, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT), "plan", "--map", str(mp), "--memory-dir", str(mem),
                        "--dry-run"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=120)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "Traceback" not in r.stderr
    out = json.loads(r.stdout)
    assert out["mode"] == "PLAN" and out["layer"] == "project" and out["errors"] == []
    assert (mem / "shared" / "pa.md").exists()   # plan 不落地
