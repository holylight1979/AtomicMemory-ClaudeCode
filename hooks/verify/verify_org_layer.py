#!/usr/bin/env python3
"""verify_org_layer.py — 公司層（org）記憶：候選池、可見性、同步目標、--init、config 單一來源、向量層。

做什麼：tmp 建 org 根（git init）＋專案根，驗 build_candidate_pool 的 org 組、personal 不洩漏、
collect_sync_targets 含 org 根、org-memory.py --init 後 sync-memory-index --check exit 0、
org_memory_root() 對多根拒絕、visible_vector_layers(extra_layers)、ups_search 消費 org 組、js 語法糖鏡像。
怎麼跑：python -m pytest hooks/verify/verify_org_layer.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_ROOT = HOOKS_DIR.parent
for p in (HOOKS_DIR, HOOKS_DIR / "handlers", CLAUDE_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import wg_core  # noqa: E402
import wg_atoms  # noqa: E402
import wg_vcs_sync as vs  # noqa: E402
import ups_search  # noqa: E402
from wg_atoms import build_candidate_pool, visible_vector_layers  # noqa: E402

USER = "holylight"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def _atom(path: Path, name: str, triggers: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {name}\n\n- Confidence: [臨]\n- Trigger: {triggers}\n- Author: {USER}\n"
        f"\n## 知識\n\n- [臨] 知識第一條\n\n## 行動\n\n- 無\n",
        encoding="utf-8", newline="\n",
    )


def _write_index(mem: Path, rows: List[Tuple[str, str, List[str]]]) -> None:
    mem.mkdir(parents=True, exist_ok=True)
    (mem / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": [
        {"name": n, "path": p, "triggers": t} for n, p, t in rows
    ]}, ensure_ascii=False), encoding="utf-8")


def _git_init(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True, capture_output=True)
    return path


def _org_cfg(roots: List[Path]) -> dict:
    return {
        "vector_search": {"enabled": True, "global_layer": "bm25", "fusion": "rrf",
                          "bm25_min_score": 0.5, "bm25_top_k": 3},
        "org_memory": {"enabled": True, "roots": [{"id": f"org{i}", "root": str(r)} for i, r in enumerate(roots)]},
    }


@pytest.fixture
def world(tmp_path, monkeypatch):
    """全域層 + 專案層 + org 層全在 tmp；config 的 org_memory 指到 tmp org 根。"""
    claude = tmp_path / "claude"
    gmem = claude / "memory"
    _atom(gmem / "工作流" / "g-alpha.md", "g-alpha", "zzzalpha")
    _write_index(gmem, [("g-alpha", "memory/工作流/g-alpha.md", ["zzzalpha"])])
    (gmem / "MEMORY.md").write_text("# g\n", encoding="utf-8")

    proj = _git_init(tmp_path / "proj")
    pmem = proj / ".claude" / "memory"
    _atom(pmem / "shared" / "p-one.md", "p-one", "zzzpone")
    (pmem / "MEMORY.md").write_text("# p\n", encoding="utf-8")

    org = _git_init(tmp_path / "org")
    (org / ".claude" / "project-tree.json").parent.mkdir(parents=True)
    (org / ".claude" / "project-tree.json").write_text('{"standalone": true}\n', encoding="utf-8")
    omem = org / ".claude" / "memory"
    _atom(omem / "shared" / "工具" / "tool-a.md", "tool-a", "zzzorgtool")
    _atom(omem / "personal" / "alice" / "alice-org.md", "alice-org", "zzzorgpersonal")
    _atom(omem / "personal" / USER / "mine-org.md", "mine-org", "zzzorgpersonal")
    _write_index(omem, [
        ("tool-a", "memory/shared/工具/tool-a.md", ["zzzorgtool"]),
        ("alice-org", "memory/personal/alice/alice-org.md", ["zzzorgpersonal"]),
        ("mine-org", f"memory/personal/{USER}/mine-org.md", ["zzzorgpersonal"]),
    ])
    (omem / "MEMORY.md").write_text("# org\n", encoding="utf-8")

    wf = tmp_path / "wf"
    wf.mkdir()
    monkeypatch.setattr(wg_atoms, "MEMORY_DIR", gmem)
    monkeypatch.setattr(ups_search, "MEMORY_DIR", gmem)
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_atoms, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_atoms, "_REKICK_MARKER", wf / "vector_rekick.marker")
    monkeypatch.setattr(ups_search, "discover_all_project_memory_dirs", lambda: [])
    cfg = _org_cfg([org])
    monkeypatch.setattr(wg_core, "load_config", lambda: json.loads(json.dumps(cfg)))
    return {"claude": claude, "gmem": gmem, "proj": proj, "org": org, "omem": omem, "wf": wf, "cfg": cfg}


# ─── ① 任意 cwd 池含 org atom；cwd＝org 根不重複 ─────────────────────────────

def test_pool_has_org_group_and_no_duplicate_when_cwd_is_org(world):
    got = build_candidate_pool(str(world["proj"]), USER, [], org_root=str(world["org"]))
    org_names = [n for n, _p, _t in got["org"]]
    assert "tool-a" in org_names
    assert got["org_base"] == str((world["org"] / ".claude").resolve())
    assert got["scopes"]["tool-a"] == "org"
    assert [n for n, _p, _t in got["project"]] == ["p-one"]

    at_org = build_candidate_pool(str(world["org"]), USER, [], org_root=str(world["org"]))
    assert at_org["org"] == [] and at_org["org_base"] is None
    proj_names = [n for n, _p, _t in at_org["project"]]
    assert proj_names.count("tool-a") == 1  # 從專案層看到一次，org 組不再重複


def test_pool_without_org_root_is_unchanged(world):
    got = build_candidate_pool(str(world["proj"]), USER, [])
    assert got["org"] == [] and got["org_base"] is None


# ─── ② org 的 personal 只給本人；unknown 一顆 personal 都看不到 ───────────────

def test_org_personal_not_leaked(world):
    got = build_candidate_pool(str(world["proj"]), USER, [], org_root=str(world["org"]))
    names = {n for n, _p, _t in got["org"]}
    assert "mine-org" in names and "alice-org" not in names
    assert got["scopes"]["mine-org"] == f"personal:{USER}"

    unknown = build_candidate_pool(str(world["proj"]), "unknown", [], org_root=str(world["org"]))
    assert {n for n, _p, _t in unknown["org"]} == {"tool-a"}


# ─── ③ collect_sync_targets 含 org 根 ────────────────────────────────────────

def test_collect_sync_targets_includes_org_root(world, monkeypatch):
    monkeypatch.setattr(wg_core, "resolve_project_root", None)
    cfg = {"vcs_sync": {"enabled": True, "push": True}}
    targets = vs.collect_sync_targets(str(world["proj"]), cfg, claude_dir=world["claude"])
    by_root = {t.root: t for t in targets}
    assert by_root[world["org"].resolve()].pathspecs == [".claude/memory"]
    assert by_root[world["proj"].resolve()].pathspecs == [".claude/memory"]

    # cwd 就是 org 根：同一根只出現一次
    targets = vs.collect_sync_targets(str(world["org"]), cfg, claude_dir=world["claude"])
    assert [t.root for t in targets].count(world["org"].resolve()) == 1
    assert by_root[world["org"].resolve()].pathspecs == [".claude/memory"]


# ─── ④ --init 後 sync-memory-index --check exit 0；config／registry 條目 ───────

def _load_org_memory_module():
    spec = importlib.util.spec_from_file_location("org_memory", CLAUDE_ROOT / "tools" / "org-memory.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_init_tree_then_sync_check_passes(tmp_path):
    om = _load_org_memory_module()
    root = _git_init(tmp_path / "company")
    msgs = om.init_tree(root, "tester")
    mem = root / ".claude" / "memory"
    assert (root / ".claude" / "project-tree.json").read_text(encoding="utf-8").strip() == '{\n  "standalone": true\n}'
    tax = json.loads((mem / "shared" / "_taxonomy.json").read_text(encoding="utf-8"))
    assert "工具" in tax["domains"]
    assert (mem / "shared" / "工具" / "org-memory.md").is_file()
    idx = json.loads((mem / "_atom_index.json").read_text(encoding="utf-8"))
    assert [a["name"] for a in idx["atoms"]] == ["org-memory"]
    text = (mem / "MEMORY.md").read_text(encoding="utf-8")
    assert "<!-- atom-catalog -->" in text and "| 工具 | 1 |" in text
    assert any("工具卡" in m for m in msgs)

    r = subprocess.run(
        [sys.executable, str(CLAUDE_ROOT / "tools" / "sync-memory-index.py"), "--check", "--memory-dir", str(mem)],
        capture_output=True, text=True, encoding="utf-8", env=ENV,
    )
    assert r.returncode == 0, r.stderr

    # 冪等：再跑一次不新增、不改
    before = {p: p.read_bytes() for p in mem.rglob("*") if p.is_file()}
    om.init_tree(root, "tester")
    assert {p: p.read_bytes() for p in mem.rglob("*") if p.is_file()} == before


def test_init_registers_local_state_and_registry(tmp_path, monkeypatch):
    """接上只寫本機狀態檔；進版控的共用 config 一個位元組都不動。"""
    om = _load_org_memory_module()
    root = _git_init(tmp_path / "company")
    wf = tmp_path / "wf"
    wf.mkdir()
    cfg_path = wf / "config.json"
    cfg_path.write_text(json.dumps({"enabled": True, "org_memory": {"_doc": "d", "repo_url": "u", "enabled": False,
                                                                    "roots": []},
                                    "zz": 1}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shared_before = cfg_path.read_bytes()
    reg_path = tmp_path / "project-registry.json"
    monkeypatch.setattr(om, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(wg_core, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_core, "REGISTRY_PATH", reg_path)
    wg_core.save_org_local(advised=True)

    om.register_local(root)
    om.register_in_registry(root)

    assert cfg_path.read_bytes() == shared_before
    local = json.loads((wf / "org-memory.local.json").read_text(encoding="utf-8"))
    assert local == {"advised": True, "enabled": True, "roots": [{"id": "org", "root": str(root)}]}  # 既有鍵保留
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    slug = wg_core.cwd_to_project_slug(str(root))
    assert reg["projects"][slug]["root"] == str(root)
    # 單一來源函式：共用 config 關著，本機檔蓋過後回這個根
    assert wg_core.org_memory_root() == root


def test_local_state_overrides_shared_and_bad_file_is_loud(world, monkeypatch, capsys):
    """本機檔同名鍵蓋過共用 config；沒檔＝照共用；壞檔＝當沒接上且 stderr 有訊息。"""
    monkeypatch.setattr(wg_core, "load_config", lambda: {"org_memory": {"repo_url": "u", "enabled": False, "roots": []}})
    assert wg_core.org_memory_root() is None and capsys.readouterr().err == ""

    wg_core.save_org_local(enabled=True, roots=[{"id": "org", "root": str(world["org"])}])
    assert wg_core.org_memory_root() == world["org"]

    wg_core.save_org_local(enabled=False)   # 本機明確關掉，就算共用 config 開著也不接
    monkeypatch.setattr(wg_core, "load_config", lambda: _org_cfg([world["proj"]]))
    assert wg_core.org_memory_root() is None

    (world["wf"] / "org-memory.local.json").write_text("{壞", encoding="utf-8")
    monkeypatch.setattr(wg_core, "load_config", lambda: {"org_memory": {"enabled": False, "roots": []}})
    capsys.readouterr()
    assert wg_core.org_memory_root() is None
    assert "讀取失敗" in capsys.readouterr().err


# ─── ④b SessionStart：沒接上的機器只邀請一次；沒 repo_url 不出聲；已接上照舊報顆數 ──────────

def test_unjoined_machine_is_invited_exactly_once(world, monkeypatch):
    import session_start as ss
    shared = {"org_memory": {"repo_url": "https://example.invalid/x.git", "enabled": False, "roots": []}}
    monkeypatch.setattr(ss, "load_config", lambda: shared)
    first = ss._org_advisory(None, {})
    assert len(first) == 1 and "接上公司記憶" in first[0] and "只出現這一次" in first[0]
    assert json.loads((world["wf"] / "org-memory.local.json").read_text(encoding="utf-8")) == {"advised": True}
    assert ss._org_advisory(None, {}) == []
    assert ss._org_advisory(None, {}) == []


def test_no_invite_without_repo_url_and_joined_machine_unchanged(world, monkeypatch):
    import session_start as ss
    monkeypatch.setattr(ss, "load_config", lambda: {"org_memory": {"enabled": False, "roots": []}})
    assert ss._org_advisory(None, {}) == []
    assert not (world["wf"] / "org-memory.local.json").exists()   # 沒提示就不留標記

    pool = build_candidate_pool(str(world["proj"]), USER, [], org_root=str(world["org"]))
    assert ss._org_advisory(world["org"], pool) == [f"[Org] 公司層 {len(pool['org'])} 顆（{world['org']}）"]
    assert "尚未接上" in ss._org_advisory(world["wf"] / "nowhere", pool)[0]   # 接過但 checkout 不見 → 每次都警告


# ─── ⑤ org_memory_root：關閉不出聲；多根／缺鍵拒絕且 stderr 有訊息 ─────────────

def test_org_memory_root_rejects_multiple_roots(world, monkeypatch, capsys):
    cfg = _org_cfg([world["org"], world["proj"]])
    monkeypatch.setattr(wg_core, "load_config", lambda: cfg)
    assert wg_core.org_memory_root() is None
    assert "只支援 1 個" in capsys.readouterr().err

    monkeypatch.setattr(wg_core, "load_config", lambda: {"org_memory": {"enabled": False, "roots": []}})
    assert wg_core.org_memory_root() is None
    assert capsys.readouterr().err == ""

    monkeypatch.setattr(wg_core, "load_config", lambda: {})
    assert wg_core.org_memory_root() is None
    assert "缺 org_memory" in capsys.readouterr().err

    monkeypatch.setattr(wg_core, "load_config", lambda: {"org_memory": {"enabled": True, "roots": []}})
    assert wg_core.org_memory_root() is None
    assert "roots 為空" in capsys.readouterr().err


# ─── ⑥ visible_vector_layers(extra_layers) ───────────────────────────────────

def test_visible_vector_layers_extra_layers():
    base = visible_vector_layers("c--proj", "u", ["programmer"])
    assert visible_vector_layers("c--proj", "u", ["programmer"], extra_layers=None) == base
    assert visible_vector_layers("c--proj", "u", ["programmer"], extra_layers=["shared:x"]) == base + ["shared:x"]
    assert visible_vector_layers("c--proj", "u", ["programmer"], extra_layers=["global"]) == base  # 不重複


# ─── ⑦ ups_search 消費 org 組：trigger 命中 org atom、向量層加 shared:<org slug> ──

def test_ups_search_consumes_org_group(world, monkeypatch):
    seen = {}

    def _fake_sem(prompt, config, **kw):
        seen["layers"] = kw.get("layers")
        return []
    monkeypatch.setattr(ups_search, "_semantic_search", _fake_sem)

    pool = build_candidate_pool(str(world["proj"]), USER, [], org_root=str(world["org"]))
    state = {"atom_index": pool, "user_identity": {"user": USER, "roles": [], "management": False},
             "session": {"cwd": str(world["proj"])}, "injected_atoms": []}
    prompt = "請看 zzzorgtool"
    matched, atom_source, _all, _sem, _h, _a, _i, _c = ups_search.collect_matched_atoms(
        "t", state, world["cfg"], prompt, prompt.lower(), [])
    hit = {e[0][0]: e[1] for e in matched}
    assert atom_source.get("tool-a") == "trigger"
    assert hit["tool-a"] == (world["org"] / ".claude").resolve()
    org_slug = wg_core.cwd_to_project_slug(str(world["org"].resolve()))
    assert f"shared:{org_slug}" in seen["layers"]


# ─── ⑧ js 鏡像：orgMemoryRoot 同規則；dedupLayersFor(org)＝global＋shared:<org slug> ──

def test_js_org_sugar_mirrors_python(world):
    lib = str(CLAUDE_ROOT / "tools" / "workflow-guardian-mcp" / "lib" / "realm.js")
    script = (
        "const r=require(process.argv[1]);"
        "console.log(JSON.stringify(["
        "r.orgMemoryRoot({org_memory:{enabled:true,roots:[{id:'a',root:'C:/A'},{id:'b',root:'C:/B'}]}},{}),"
        "r.orgMemoryRoot({org_memory:{enabled:false,roots:[{id:'a',root:'C:/A'}]}},{}),"
        "r.orgMemoryRoot({org_memory:{enabled:true,roots:[{id:'a',root:'c:/Company/Mem'}]}},{}),"
        "r.dedupLayersFor('org','c:/Company/Mem/.claude/memory'),"
        # 本機狀態（第二參數）同名鍵蓋過共用 config：共用關、本機開 → 本機根；共用開、本機關 → null
        "r.orgMemoryRoot({org_memory:{repo_url:'u',enabled:false,roots:[]}},{enabled:true,roots:[{id:'org',root:'D:/Mine'}]}),"
        "r.orgMemoryRoot({org_memory:{enabled:true,roots:[{id:'a',root:'C:/A'}]}},{enabled:false}),"
        "r.orgMemoryRoot({org_memory:{repo_url:'u',enabled:false,roots:[]}},{advised:true}),"
        "]))"
    )
    r = subprocess.run(["node", "-e", script, lib], capture_output=True, text=True, encoding="utf-8", check=True)
    two, off, one, layers, local_on, local_off, advised_only = json.loads(r.stdout)
    assert two is None and "只支援 1 個" in r.stderr
    assert off is None
    assert one == "c:/Company/Mem"
    assert local_on == "D:/Mine" and local_off is None and advised_only is None
    assert layers == ["global", f"shared:{wg_core.cwd_to_project_slug('c:/Company/Mem')}"]


def test_init_tree_ignores_access_sidecars(tmp_path):
    """公司 repo 不追蹤 *.access.json（各機遙測）；既有 .gitignore 內容保留、重跑不重複加。"""
    om = _load_org_memory_module()
    root = tmp_path / "company"
    root.mkdir()
    (root / ".gitignore").write_text("node_modules/\n", encoding="utf-8", newline="\n")
    om.init_tree(root, "tester")
    om.init_tree(root, "tester")
    lines = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert lines == ["node_modules/", "**/*.access.json"]
