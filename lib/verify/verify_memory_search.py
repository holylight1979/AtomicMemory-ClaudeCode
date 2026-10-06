"""verify_memory_search.py — memory_search 讀取端與共用候選池封閉。

覆蓋：
① wg_atoms.build_candidate_pool 與 SessionStart 原內聯邏輯（複製為 oracle）逐鍵相等（V4 / V3 / 無專案 / 無身份）
② 已知 trigger 命中已知 atom、分數遞減、legacy 分支也有分數；BM25 路對整池有效
③ 他人 personal 不出現；user="unknown" 不出現任何 personal（entry_visible 同規則）
④ use_vector=False 不建 vector_rekick.marker
⑤ 同名跨層取 project 且 warnings 有遮蔽紀錄；同一實體檔從兩層看到不警告
⑥ 回傳含 schema_version 與 author／audience／tags／status／provenance 五欄（provenance＝atom 的 Source 值）；cli action=search 走通
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

CLAUDE_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_DIR = CLAUDE_ROOT / "hooks"
for p in (HOOKS_DIR, HOOKS_DIR / "handlers", CLAUDE_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import wg_core  # noqa: E402
import wg_atoms  # noqa: E402
import ups_search  # noqa: E402
from lib import memory_search  # noqa: E402
from lib.memory_search import search  # noqa: E402

USER = "holylight"
ROLES = ["programmer"]


def _atom(path: Path, name: str, triggers: str, *, extra_meta: str = "", knowledge: str = "知識第一條") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {name}\n\n- Confidence: [臨]\n- Trigger: {triggers}\n- Author: {USER}\n{extra_meta}"
        f"\n## 知識\n\n- [臨] {knowledge}\n\n## 行動\n\n- 無\n",
        encoding="utf-8", newline="\n",
    )


def _write_index(mem: Path, rows: List[Tuple[str, str, List[str]]]) -> None:
    (mem / "_atom_index.json").write_text(json.dumps({"atoms": [
        {"name": n, "path": p, "triggers": t} for n, p, t in rows
    ]}), encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    """全域層 + V4 專案層 + V3 專案層，MEMORY_DIR / WORKFLOW_DIR 全部指到 tmp。"""
    claude = tmp_path / "claude"
    gmem = claude / "memory"
    _atom(gmem / "工作流" / "g-alpha.md", "g-alpha", "zzzalpha")
    _atom(gmem / "工作流" / "g-beta.md", "g-beta", "zzzbeta", knowledge="serverdeploy 流程")
    _atom(gmem / "工作流" / "dup-card.md", "dup-card", "zzzdup", knowledge="global 版")
    _atom(gmem / "personal" / USER / "mine-global.md", "mine-global", "zzzmine")
    _atom(gmem / "personal" / "alice" / "alice-global.md", "alice-global", "zzzmine")
    _write_index(gmem, [
        ("g-alpha", "memory/工作流/g-alpha.md", ["zzzalpha"]),
        ("g-beta", "memory/工作流/g-beta.md", ["zzzbeta"]),
        ("dup-card", "memory/工作流/dup-card.md", ["zzzdup"]),
        ("mine-global", f"memory/personal/{USER}/mine-global.md", ["zzzmine"]),
        ("alice-global", "memory/personal/alice/alice-global.md", ["zzzmine"]),
    ])
    (gmem / "MEMORY.md").write_text("# g\n", encoding="utf-8")

    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    pmem = proj / ".claude" / "memory"
    (pmem / "MEMORY.md").parent.mkdir(parents=True)
    (pmem / "MEMORY.md").write_text("# p\n", encoding="utf-8")
    _atom(pmem / "shared" / "dup-card.md", "dup-card", "zzzdup", knowledge="project 版")
    _atom(pmem / "shared" / "p-one.md", "p-one", "zzzpone",
          extra_meta="- Audience: programmer\n- Tags: t1, t2\n- Status: production\n"
                     "- Source: session:0123abcd#89abcdef 2026-10-06\n")
    _atom(pmem / "personal" / USER / "mine-proj.md", "mine-proj", "zzzmine")
    _atom(pmem / "personal" / "bob" / "bob-proj.md", "bob-proj", "zzzmine")
    _atom(pmem / "roles" / "programmer" / "role-prog.md", "role-prog", "zzzrole")
    _atom(pmem / "roles" / "art" / "role-art.md", "role-art", "zzzrole")

    v3 = tmp_path / "v3proj"
    (v3 / ".git").mkdir(parents=True)
    v3mem = v3 / ".claude" / "memory"
    v3mem.mkdir(parents=True)
    (v3mem / "MEMORY.md").write_text("# v3\n", encoding="utf-8")
    _atom(v3mem / "flat-v3.md", "flat-v3", "zzzflat")
    _write_index(v3mem, [("flat-v3", "memory/flat-v3.md", ["zzzflat"])])

    wf = tmp_path / "wf"
    wf.mkdir()
    monkeypatch.setattr(wg_atoms, "MEMORY_DIR", gmem)
    monkeypatch.setattr(ups_search, "MEMORY_DIR", gmem)
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_atoms, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_atoms, "_REKICK_MARKER", wf / "vector_rekick.marker")
    monkeypatch.setattr(ups_search, "discover_all_project_memory_dirs", lambda: [])
    monkeypatch.setattr(ups_search, "_semantic_search", lambda *a, **k: [])
    cfg = {"vector_search": {"enabled": True, "global_layer": "bm25", "fusion": "rrf",
                             "bm25_min_score": 0.5, "bm25_top_k": 3}}
    monkeypatch.setattr(wg_core, "load_config", lambda: json.loads(json.dumps(cfg)))
    return {"claude": claude, "gmem": gmem, "proj": proj, "pmem": pmem, "v3": v3, "wf": wf, "cfg": cfg}


# ─── ① build_candidate_pool 對拍舊內聯（oracle＝複製 SessionStart 原邏輯）────────

def _oracle_collect_v4(project_mem_dir: Optional[Path], user: str, roles: List[str]):
    from handlers._shared import _V4_TRIGGER_LINE_RE
    if not project_mem_dir or not project_mem_dir.is_dir():
        return []
    out = []
    targets = []
    if (project_mem_dir / "shared").is_dir():
        targets.append(project_mem_dir / "shared")
    for r in roles:
        if (project_mem_dir / "roles" / r).is_dir():
            targets.append(project_mem_dir / "roles" / r)
    if (project_mem_dir / "personal" / user).is_dir():
        targets.append(project_mem_dir / "personal" / user)
    for base in targets:
        for md in sorted(base.glob("**/*.md")):
            rel_parts = md.relative_to(base).parts
            if any(p.startswith("_") for p in rel_parts[:-1]):
                continue
            if md.name in (wg_core.MEMORY_INDEX, "_ATOM_INDEX.md") or md.name.startswith(("_", "SPEC_")):
                continue
            text = md.read_text(encoding="utf-8-sig")
            tm = _V4_TRIGGER_LINE_RE.search(text)
            triggers = [t.strip().lower() for t in tm.group(1).split(",") if t.strip()] if tm else []
            out.append((md.stem, f"{project_mem_dir.name}/{md.relative_to(project_mem_dir).as_posix()}", triggers))
    return out


def _oracle_pool(cwd: str, user: str, roles: List[str]) -> Dict[str, Any]:
    """SessionStart 抽出前的內聯邏輯原樣複製（state["atom_index"] 的鍵）。"""
    global_atoms = wg_atoms.parse_memory_index(wg_atoms.MEMORY_DIR)
    if wg_atoms.is_local_realm_path is not None and not wg_core._is_under_claude_dir(cwd):
        global_atoms = [(n, p, t) for (n, p, t) in global_atoms
                        if not wg_atoms.is_local_realm_path(p) or wg_core.is_cross_project_local(p)]
    project_mem_dir = wg_core.get_project_memory_dir(cwd)
    project_atoms = wg_atoms.parse_memory_index(project_mem_dir) if project_mem_dir else []
    project_root = wg_core.find_project_root(cwd)
    v4_entries = _oracle_collect_v4(project_mem_dir, user, roles) if project_mem_dir else []
    v4_layout_active = bool(project_mem_dir) and any(
        (project_mem_dir / d).is_dir() for d in ("shared", "roles", "personal"))
    if v4_layout_active:
        merged = list(v4_entries)
    else:
        merged = list(project_atoms)
        names = {n for n, _p, _t in merged}
        for e in v4_entries:
            if e[0] not in names:
                merged.append(e)
                names.add(e[0])
    global_atoms = wg_atoms.filter_visible(global_atoms, user, roles)
    merged = wg_atoms.filter_visible(merged, user, roles)
    scopes = {n: wg_atoms.scope_from_rel_path(p, "global") for n, p, _t in global_atoms}
    scopes.update({n: wg_atoms.scope_from_rel_path(p, "shared") for n, p, _t in merged})
    slug = wg_core.cwd_to_project_slug(str(project_root.resolve())) if project_root else ""
    pool = [((n, p, t), wg_atoms.MEMORY_DIR.parent) for n, p, t in global_atoms]
    if project_mem_dir:
        for n, p, t in merged:
            base = project_root if (p.startswith("_AIAtoms/") and project_root) else Path(project_mem_dir).parent
            pool.append(((n, p, t), Path(base)))
    return {
        "global": [(n, p, t) for n, p, t in global_atoms],
        "project": [(n, p, t) for n, p, t in merged],
        "project_memory_dir": str(project_mem_dir) if project_mem_dir else "",
        "project_root": str(project_root) if project_root else "",
        "project_slug": slug,
        "scopes": scopes,
        "superseded": sorted(wg_atoms.collect_superseded_names(pool)),
    }


@pytest.mark.parametrize("which,user,roles", [
    ("proj", USER, ROLES), ("proj", "", []), ("proj", "bob", ["art"]),
    ("v3", USER, ROLES), ("none", USER, ROLES),
])
def test_build_candidate_pool_matches_old_inline(world, tmp_path, which, user, roles):
    cwd = str({"proj": world["proj"], "v3": world["v3"], "none": tmp_path / "nowhere"}[which])
    got = wg_atoms.build_candidate_pool(cwd, user, roles)
    want = _oracle_pool(cwd, user, roles)
    for key in want:
        assert got[key] == want[key], key
    assert got["org"] == [] and got["org_base"] is None
    if which == "proj" and user == USER:
        names = {n for n, _p, _t in got["project"]}
        assert names == {"dup-card", "p-one", "mine-proj", "role-prog"}
        assert got["scopes"]["mine-proj"] == f"personal:{USER}"
        assert got["scopes"]["role-prog"] == "role:programmer"


def test_build_candidate_pool_is_side_effect_free(world, monkeypatch):
    """純函式：不註冊專案、不 bootstrap、不改 MEMORY.md。"""
    calls = []
    monkeypatch.setattr(wg_core, "register_project", lambda cwd: calls.append(cwd))
    before = (world["pmem"] / "MEMORY.md").read_text(encoding="utf-8")
    wg_atoms.build_candidate_pool(str(world["proj"]), USER, ROLES)
    assert calls == []
    assert (world["pmem"] / "MEMORY.md").read_text(encoding="utf-8") == before


def test_session_start_keeps_guard_literals_and_calls_pool():
    src = (HOOKS_DIR / "handlers" / "session_start.py").read_text(encoding="utf-8")
    assert "global_atoms = parse_memory_index(MEMORY_DIR)" in src
    # 呼叫可多行（org_root 等關鍵字參數），但 global_atoms 必須由 session_start 傳入
    m = re.search(r"build_candidate_pool\(\s*cwd,\s*v4_user,\s*v4_roles,.*?global_atoms=global_atoms", src, re.S)
    assert m, "session_start 須呼叫 build_candidate_pool(cwd, v4_user, v4_roles, …, global_atoms=global_atoms)"
    assert "lines.extend(_personal_sync_advisory(project_mem_dir, v4_user))" in src
    ups = (HOOKS_DIR / "handlers" / "ups_search.py").read_text(encoding="utf-8")
    assert "parse_memory_index" not in ups


# ─── ② 命中、排序、legacy、BM25 ──────────────────────────────────────────────

def test_trigger_hits_known_atom_scores_descend(world):
    res = search("講一下 zzzalpha 跟 zzzbeta", str(world["proj"]), user=USER, roles=ROLES, use_vector=False)
    names = [r["name"] for r in res["results"]]
    assert {"g-alpha", "g-beta"} <= set(names)
    assert all(r["source"] == "trigger" for r in res["results"] if r["name"] in ("g-alpha", "g-beta"))
    scores = [r["score"] for r in res["results"]]
    assert scores == sorted(scores, reverse=True) and scores[0] > 0
    assert res["mode"] == "trigger+bm25"


def test_legacy_fusion_has_scores(world, monkeypatch):
    cfg = json.loads(json.dumps(world["cfg"]))
    cfg["vector_search"]["fusion"] = "legacy"
    monkeypatch.setattr(wg_core, "load_config", lambda: cfg)
    res = search("zzzalpha zzzbeta", str(world["proj"]), user=USER, roles=ROLES, use_vector=False)
    scores = [r["score"] for r in res["results"]]
    assert len(scores) >= 2 and scores == sorted(scores, reverse=True) and scores[0] == 1.0


def test_bm25_runs_over_project_layer_too(world):
    """trigger 不中、靠 BM25 對整池命中專案層 atom（hook 內只對 global 跑 BM25）。"""
    res = search("p-one", str(world["proj"]), user=USER, roles=ROLES, use_vector=False)
    hit = next((r for r in res["results"] if r["name"] == "p-one"), None)
    assert hit is not None and hit["source"] == "bm25" and hit["scope"] == "shared"


def test_vector_mode_label_and_top_k(world):
    res = search("zzzalpha zzzbeta zzzpone", str(world["proj"]), user=USER, roles=ROLES, top_k=2)
    assert res["mode"] == "trigger+bm25+vector" and len(res["results"]) == 2


# ─── ③ 身份 ─────────────────────────────────────────────────────────────────

def test_other_personal_never_appears(world):
    res = search("zzzmine", str(world["proj"]), user=USER, roles=ROLES, use_vector=False)
    names = {r["name"] for r in res["results"]}
    assert names == {"mine-global", "mine-proj"}
    assert {r["scope"] for r in res["results"]} == {f"personal:{USER}"}


def test_unknown_user_sees_no_personal(world):
    for u in ("unknown", None, ""):
        res = search("zzzmine zzzrole", str(world["proj"]), user=u, roles=ROLES, use_vector=False)
        assert not any(r["scope"].startswith("personal:") for r in res["results"]), u
        assert any("personal" in w for w in res["warnings"])
    assert wg_atoms.entry_visible("memory/personal/unknown/x.md", "unknown", []) is False
    assert wg_atoms.entry_visible(f"memory/personal/{USER}/x.md", USER, []) is True


def test_roles_none_sees_no_role_layer(world):
    res = search("zzzrole", str(world["proj"]), user=USER, roles=None, use_vector=False)
    assert not any(r["scope"].startswith("role:") for r in res["results"])
    res2 = search("zzzrole", str(world["proj"]), user=USER, roles=ROLES, use_vector=False)
    assert [r["name"] for r in res2["results"]] == ["role-prog"]


# ─── ④ 向量路關閉零觸碰 rekick ─────────────────────────────────────────────

def test_no_vector_does_not_touch_rekick_marker(world, monkeypatch):
    """真的走 wg_atoms._semantic_search：enabled=False 在 _ensure_vector_ready（寫 rekick marker）之前就回頭。"""
    monkeypatch.setattr(ups_search, "_semantic_search", wg_atoms._semantic_search)
    monkeypatch.setattr(wg_atoms, "_ensure_vector_ready",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("rekick 被觸碰")))
    search("zzzalpha", str(world["proj"]), user=USER, roles=ROLES, use_vector=False)
    assert not (world["wf"] / "vector_rekick.marker").exists()


# ─── ⑤ 同名跨層 ──────────────────────────────────────────────────────────────

def test_same_name_project_wins_with_warning(world):
    res = search("zzzdup", str(world["proj"]), user=USER, roles=ROLES, use_vector=False)
    hits = [r for r in res["results"] if r["name"] == "dup-card"]
    assert len(hits) == 1
    assert hits[0]["scope"] == "shared" and hits[0]["excerpt"].endswith("project 版")
    assert str(world["pmem"]) in hits[0]["path"]
    assert any(w.startswith("同名被遮蔽: dup-card (global") for w in res["warnings"])


def test_same_file_through_two_layers_is_silent(world, monkeypatch):
    """cwd 在 ~/.claude 時 project 層＝全域記憶本身，同一檔不算遮蔽。"""
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", world["claude"])
    monkeypatch.setattr(wg_core, "MEMORY_DIR", world["gmem"])
    res = search("zzzmine", str(world["claude"]), user=USER, roles=ROLES, use_vector=False)
    assert not any(w.startswith("同名被遮蔽") for w in res["warnings"]), res["warnings"]
    assert [r["name"] for r in res["results"]] == ["mine-global"]


# ─── ⑥ 契約欄位與入口 ────────────────────────────────────────────────────────

def test_contract_fields(world):
    res = search("zzzpone", str(world["proj"]), user=USER, roles=ROLES, use_vector=False)
    assert res["schema_version"] == 1 and isinstance(res["warnings"], list)
    r = res["results"][0]
    assert set(r) == {"name", "path", "rel_path", "scope", "source", "score", "excerpt",
                      "author", "audience", "tags", "status", "provenance"}
    assert (r["author"], r["audience"], r["tags"], r["status"]) == (USER, "programmer", "t1, t2", "production")
    assert r["excerpt"] == "[臨] 知識第一條" and r["rel_path"] == "memory/shared/p-one.md"
    # provenance＝atom 的 `- Source:` 值；既有 source 欄仍是檢索路，兩者不混
    assert r["provenance"] == "session:0123abcd#89abcdef 2026-10-06" and r["source"] == "trigger"
    # 缺欄靜默回空字串
    g = search("zzzalpha", str(world["proj"]), user=USER, roles=ROLES, use_vector=False)["results"][0]
    assert (g["audience"], g["tags"], g["status"], g["provenance"]) == ("", "", "", "")


def test_empty_query_rejected(world):
    with pytest.raises(ValueError):
        search("   ", str(world["proj"]), user=USER, roles=ROLES, use_vector=False)


def test_cli_search_action(world):
    from lib import atom_io_cli
    r = atom_io_cli.search_atoms({"query": "zzzalpha", "cwd": str(world["proj"]),
                                  "user": USER, "roles": ROLES, "use_vector": False, "top_k": 1})
    assert r.ok and r.extra["schema_version"] == 1 and r.extra["results"][0]["name"] == "g-alpha"
    bad = atom_io_cli.search_atoms({"query": "", "cwd": str(world["proj"]), "user": USER, "roles": []})
    assert not bad.ok and "empty" in bad.error


def test_format_table_has_header(world):
    res = search("zzzalpha", str(world["proj"]), user=USER, roles=ROLES, use_vector=False)
    txt = memory_search.format_table(res)
    assert "name | scope | source | score | excerpt" in txt and "g-alpha | global | trigger |" in txt
