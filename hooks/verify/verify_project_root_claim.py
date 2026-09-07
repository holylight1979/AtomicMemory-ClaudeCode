"""verify_project_root_claim.py — 子專案 cwd 認領核心根層（lib/project_root + wg_core 委派 + SessionStart 宣告 + CLI）。

怎麼跑：python -m pytest hooks/verify/verify_project_root_claim.py -q
佈局：tmp 下建 TSLG 型樹（根層 .claude/memory + 宣告；Server 子層有自己的宣告；Client 只有 .git）。
狀況總表 A～T 見 plans/resilient-orbiting-lark.md §2b；本檔每列一個 case。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent
for _p in (CLAUDE_DIR / "hooks", CLAUDE_DIR / "lib", CLAUDE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import project_root as pr  # noqa: E402
import wg_core  # noqa: E402
from lib import atom_io  # noqa: E402
from handlers.session_start import _project_root_notice, _root_fingerprint_matches  # noqa: E402

CLI = CLAUDE_DIR / "tools" / "project-tree.py"


def _decl(layer: Path, **fields) -> Path:
    p = layer / ".claude" / pr.DECL_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")
    return p


def _memory(layer: Path, atoms: int = 0) -> None:
    mem = layer / ".claude" / "memory"
    mem.mkdir(parents=True, exist_ok=True)
    (mem / "MEMORY.md").write_text("# idx\n", encoding="utf-8")
    if atoms:
        (mem / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": [
            {"name": f"a{i}", "path": f"memory/shared/a{i}.md", "triggers": [f"a{i}"]} for i in range(atoms)]}),
            encoding="utf-8")


@pytest.fixture(autouse=True)
def _fresh_cache():
    pr.clear_cache()
    yield
    pr.clear_cache()


@pytest.fixture
def tree(tmp_path) -> Path:
    """T/TSLG（根，subs=[Server]）；T/TSLG/Server（root=..）；T/TSLG/Client（.git）；深層 scripts/lua/quest/npc。"""
    t = tmp_path / "T"
    _memory(t / "TSLG")
    _decl(t / "TSLG", subs=["Server"])
    _decl(t / "TSLG" / "Server", root="..", subs=["scripts"])
    (t / "TSLG" / "Server" / "scripts" / "lua" / "quest" / "npc").mkdir(parents=True)
    (t / "TSLG" / "Client" / ".git").mkdir(parents=True)
    (t / "TSLG" / "Server2" / "x").mkdir(parents=True)
    return t


def R(p: Path) -> pr.Resolution:
    return pr.resolve_project_root(str(p))


def same(a, b) -> bool:
    return a is not None and b is not None and Path(a).resolve() == Path(b).resolve()


# ─── 狀況總表 ─────────────────────────────────────────────────────────────────


def test_A_claude_dir_subtree_stays_core():
    r = R(CLAUDE_DIR / "hooks")
    assert same(r.path, CLAUDE_DIR) and r.claimed_by == "nearest" and not r.candidates
    assert wg_core.get_project_memory_dir(str(CLAUDE_DIR / "hooks")) == wg_core.MEMORY_DIR


def test_B_home_never_becomes_project_root(tmp_path, monkeypatch):
    home = tmp_path / "home"
    _memory(home)                       # 家目錄的 ~/.claude/memory/MEMORY.md
    monkeypatch.setattr(pr, "HOME", home)
    monkeypatch.setattr(pr, "CLAUDE_DIR", home / ".claude")
    plain = home / "Downloads" / "x"
    plain.mkdir(parents=True)
    r = R(plain)
    assert r.path is None and r.claimed_by == "none" and not r.candidates
    # {"root": "../.."} 指到家目錄也被拒
    sub = home / "proj" / "sub"
    sub.mkdir(parents=True)
    _decl(sub, root="../..")
    r = R(sub)
    assert not same(r.path, home) and any("家目錄" in w for w in r.warnings)


def test_C_D_no_declaration_no_candidate(tmp_path):
    bare = tmp_path / "bare" / "deep"
    bare.mkdir(parents=True)
    assert R(bare).claimed_by == "none"
    proj = tmp_path / "proj"
    _memory(proj)
    r = R(proj)
    assert same(r.path, proj) and r.claimed_by == "nearest" and not r.candidates


def test_E_H_candidate_without_declaration_asks(tree):
    r = R(tree / "TSLG" / "Client")
    assert same(r.path, tree / "TSLG" / "Client") and r.claimed_by == "nearest"
    assert [c.resolve() for c in r.candidates] == [(tree / "TSLG").resolve()]
    lines = _project_root_notice(r, str(tree / "TSLG" / "Client"))
    ask = [l for l in lines if l.startswith("❓ [Guardian:ProjectRoot]")]
    assert len(ask) == 1
    assert str(tree / "TSLG") in ask[0] and "claim --root" in ask[0] and "standalone on" in ask[0] \
        and "pick" in ask[0] and "這次先不決定" in ask[0]


def test_F_multiple_candidates_lists_all(tmp_path):
    outer, inner = tmp_path / "O", tmp_path / "O" / "I"
    _memory(outer)
    _memory(inner)
    leaf = inner / "leaf"
    (leaf / ".git").mkdir(parents=True)
    r = R(leaf)
    assert r.claimed_by == "nearest" and same(r.path, leaf)
    assert [c.resolve() for c in r.candidates] == [inner.resolve(), outer.resolve()]


def test_G_ancestor_subs_claims_deep_cwd(tree):
    cwd = tree / "TSLG" / "Server" / "scripts" / "lua" / "quest" / "npc"
    r = R(cwd)
    assert same(r.path, tree / "TSLG") and r.claimed_by == "ancestor-root"   # Server 層的 root 先命中
    assert same(wg_core.find_project_root(str(cwd)), tree / "TSLG")
    assert same(atom_io._find_project_root(str(cwd)), tree / "TSLG")
    (tree / "TSLG" / "Server" / ".claude" / pr.DECL_NAME).unlink()
    pr.clear_cache()
    r = R(cwd)
    assert same(r.path, tree / "TSLG") and r.claimed_by == "ancestor-subs"   # 只剩根層 subs 也認得到
    line = _project_root_notice(r, str(cwd))[0]
    assert line.startswith("📍 [Guardian:ProjectRoot]")
    assert f"{cwd} 屬 {tree / 'TSLG'} 的子專案（宣告：根層 subs @ {tree / 'TSLG'}）" in line
    assert f"記憶歸 {tree / 'TSLG' / '.claude' / 'memory'}" in line


def test_H_subs_not_listing_cwd_prefix_exact(tree):
    r = R(tree / "TSLG" / "Server2" / "x")            # Server ≠ Server2
    assert r.claimed_by == "nearest" and same(r.path, tree / "TSLG")   # 4 層內舊規則本來就到 TSLG
    assert not r.candidates                            # 生效根＝候選 → 沒什麼可問
    lines = _project_root_notice(r, str(tree / "TSLG" / "Server2" / "x"))
    assert not any(l.startswith("❓") for l in lines)


def test_I_Iprime_own_root_wins_over_self(tree):
    r = R(tree / "TSLG" / "Server")
    assert same(r.path, tree / "TSLG") and r.claimed_by == "own-root"
    assert not r.warnings                              # 根層 subs 有列 Server
    _decl(tree / "TSLG", subs=["Client"])              # 根層改成沒列 Server → ⚠️ 提示 add-sub
    pr.clear_cache()
    r = R(tree / "TSLG" / "Server")
    assert same(r.path, tree / "TSLG") and any("未列本層" in w and "add-sub" in w for w in r.warnings)


def test_J_root_parent_without_claude_dir_is_info(tmp_path):
    only = tmp_path / "Only" / "Server"
    _decl(only, root="..")
    leaf = only / "x"
    leaf.mkdir()
    r = R(leaf)
    assert same(r.path, only) and r.claimed_by == "nearest"     # 有效宣告檔本身是標記
    assert any("未 checkout" in i for i in r.infos) and not r.warnings
    lines = _project_root_notice(r, str(leaf))
    assert lines and lines[0].startswith("📍 [Guardian:ProjectRoot] 上層") and not any(l.startswith("❓") for l in lines)


def test_K_root_target_has_claude_but_nothing_valid(tmp_path):
    root = tmp_path / "R"
    (root / ".claude").mkdir(parents=True)
    sub = root / "S"
    _decl(sub, root="..")
    r = R(sub)
    assert same(r.path, sub) and r.claimed_by == "nearest"
    assert any("不採用" in w for w in r.warnings)


def test_L_standalone_stops_and_silences(tmp_path):
    outer = tmp_path / "O"
    _memory(outer)
    sub = outer / "Sub"
    _decl(sub, standalone=True)
    leaf = sub / "y"
    leaf.mkdir()
    r = R(leaf)
    assert r.standalone and same(r.path, sub) and not r.candidates
    assert _project_root_notice(r, str(leaf)) == []


def test_M_invalid_json_is_warning_not_marker(tmp_path):
    outer = tmp_path / "O"
    _memory(outer)
    app = outer / "App"
    p = _decl(app)
    p.write_text('{"root": ', encoding="utf-8")
    r = R(app)
    assert same(r.path, outer) and r.claimed_by == "nearest"            # 壞檔不當標記 → 舊規則走到 outer
    assert any(str(p) in w and "JSON" in w for w in r.warnings)
    assert pr.has_project_marker(app) is False


def test_N_fork_detected_with_count(tree):
    _memory(tree / "TSLG" / "Server", atoms=2)
    r = R(tree / "TSLG" / "Server" / "scripts")
    assert same(r.path, tree / "TSLG") and r.fork_atoms == 2
    assert any("2 顆分叉 atom" in w and "atom_move" in w for w in r.warnings)


def test_O_root_chain_cycle_and_hop_limit(tmp_path):
    a = tmp_path / "A"
    b = a / "B"
    _decl(a, root="B")           # 不是祖先 → R 列拒絕
    _decl(b, root="..")
    r = R(b)
    assert any("不是本層的祖先" in w for w in r.warnings)
    # 4 層純轉發鏈超過 3 跳
    l4 = tmp_path / "L1" / "L2" / "L3" / "L4" / "L5"
    l4.mkdir(parents=True)
    for layer in (tmp_path / "L1" / "L2", tmp_path / "L1" / "L2" / "L3", tmp_path / "L1" / "L2" / "L3" / "L4", l4):
        _decl(layer, root="..")
    _decl(tmp_path / "L1", subs=["*"])   # 終點但要 4 跳才到
    r = R(l4)
    assert any("超過" in w for w in r.warnings)


def test_P_root_itself_is_self(tree):
    r = R(tree / "TSLG")
    assert same(r.path, tree / "TSLG") and r.claimed_by == "self"
    assert _project_root_notice(r, str(tree / "TSLG")) == []


def test_Q_declared_root_without_memory_yet(tmp_path):
    root = tmp_path / "Root"
    _decl(root, subs=["Sub"])
    sub = root / "Sub" / "deep"
    sub.mkdir(parents=True)
    r = R(sub)
    assert same(r.path, root) and r.claimed_by == "ancestor-subs"
    assert any("尚未同步" in i for i in r.infos)
    mem = root / ".claude" / "memory"
    assert wg_core.get_project_memory_dir(str(sub)) == mem and not mem.exists()
    assert wg_core.resolve_failures_dir(str(sub)) == mem / "failures"
    assert wg_core.resolve_staging_dir(str(sub)) == mem / "_staging"
    from wg_atoms import parse_memory_index
    assert parse_memory_index(mem) == []


def test_R_S_root_abs_rules(tree, tmp_path):
    server = tree / "TSLG" / "Server"
    # root_abs 目錄不存在 → 忽略、用 root
    _decl(server, root="..", root_abs=str(tmp_path / "nope"))
    r = R(server)
    assert same(r.path, tree / "TSLG") and not r.warnings
    # root_abs 存在且與 root 不同 → 採 root_abs 並警告
    other = tmp_path / "Other"
    _memory(other)
    _decl(server, root="..", root_abs=str(other))
    pr.clear_cache()
    r = R(server)
    assert same(r.path, other) and any("採 root_abs" in w for w in r.warnings)


def test_T_no_declaration_equals_legacy(tmp_path):
    """無宣告時逐案與舊規則等值：最近四標記、最多 4 層、找不到回 None。"""
    def legacy(cwd: Path):
        p = cwd
        for _ in range(4):
            if (p / ".claude" / "memory" / "MEMORY.md").exists() or (p / "_AIDocs").is_dir() \
                    or (p / ".git").exists() or (p / ".svn").exists():
                return p
            if p.parent == p:
                break
            p = p.parent
        return None
    cases = []
    g = tmp_path / "g" / "a" / "b"
    (tmp_path / "g" / ".git").mkdir(parents=True); g.mkdir(parents=True); cases.append(g)
    d = tmp_path / "d" / "x" / "y" / "z" / "w"
    (tmp_path / "d" / "_AIDocs").mkdir(parents=True); d.mkdir(parents=True); cases.append(d)   # 5 層外 → None
    m = tmp_path / "m" / "k"
    _memory(tmp_path / "m"); m.mkdir(); cases.append(m)
    n = tmp_path / "n" / "o"
    n.mkdir(parents=True); cases.append(n)
    for c in cases:
        r = R(c)
        exp = legacy(c)
        assert (r.path is None) == (exp is None) and (exp is None or same(r.path, exp)), c
        assert r.claimed_by in ("nearest", "none") and not r.warnings and not r.infos
        assert wg_core.find_project_root(str(c)) == (exp or c)


# ─── 指紋 / resume ────────────────────────────────────────────────────────────


def test_fingerprint_changes_with_declaration_and_matches_state(tree):
    cwd = tree / "TSLG" / "Server" / "scripts"
    fp1 = R(cwd).fingerprint
    assert _root_fingerprint_matches({"atom_index": {"project_root_fingerprint": fp1}}, R(cwd))
    assert not _root_fingerprint_matches({"atom_index": {}}, R(cwd))       # 舊 state 無指紋 → 重建
    _decl(tree / "TSLG", subs=["Server", "Client"])
    pr.clear_cache()
    assert R(cwd).fingerprint != fp1


def test_cache_invalidates_on_declaration_mtime(tree):
    cwd = tree / "TSLG" / "Client"
    assert R(cwd).claimed_by == "nearest"
    p = _decl(tree / "TSLG", subs=["Server", "Client"])
    os.utime(p, (p.stat().st_atime, p.stat().st_mtime + 5))
    assert R(cwd).claimed_by == "ancestor-subs"       # 沒 clear_cache 也要看到新宣告


# ─── 鐵律：hook 只讀不寫 ───────────────────────────────────────────────────────


def test_hooks_never_write_declaration(tree):
    cwd = tree / "TSLG" / "Server" / "scripts"
    decls = [tree / "TSLG" / ".claude" / pr.DECL_NAME, tree / "TSLG" / "Server" / ".claude" / pr.DECL_NAME]
    before = [(p.read_bytes(), p.stat().st_mtime) for p in decls]
    guardian = CLAUDE_DIR / "hooks" / "workflow-guardian.py"
    sid = "ptclaim-" + os.urandom(4).hex()
    env = dict(os.environ, PYTEST_CURRENT_TEST=os.environ.get("PYTEST_CURRENT_TEST", "x"), PYTHONIOENCODING="utf-8")
    try:
        for ev, extra in (("SessionStart", {"source": "startup"}), ("UserPromptSubmit", {"prompt": "hi"}),
                          ("Stop", {"stop_hook_active": False})):
            data = {"hook_event_name": ev, "cwd": str(cwd), "session_id": sid, **extra}
            r = subprocess.run([sys.executable, str(guardian)], input=json.dumps(data), capture_output=True,
                               text=True, encoding="utf-8", errors="replace", cwd=str(cwd), env=env, timeout=180)
            assert "Traceback" not in r.stderr, r.stderr
    finally:
        try:
            wg_core.state_path(sid).unlink()
        except FileNotFoundError:
            pass
    assert [(p.read_bytes(), p.stat().st_mtime) for p in decls] == before


# ─── CLI ──────────────────────────────────────────────────────────────────────


def _cli(*args, cwd: Path | None = None, expect_fail: bool = False) -> str:
    argv = [sys.executable, str(CLI)]
    if cwd is not None:
        argv += ["--cwd", str(cwd)]
    argv += list(args)
    r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=60)
    if expect_fail:
        assert r.returncode != 0, r.stdout + r.stderr
    else:
        assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout + r.stderr


def _raw(layer: Path) -> dict:
    return json.loads((layer / ".claude" / pr.DECL_NAME).read_text(encoding="utf-8"))


def test_cli_claim_is_idempotent_and_skips_sub_without_claude(tree):
    client = tree / "TSLG" / "Client"
    out = _cli("claim", "--root", str(tree / "TSLG"), cwd=client)
    assert "沒有 .claude/" in out and not (client / ".claude").exists()
    assert _raw(tree / "TSLG")["subs"] == ["Server", "Client"]
    _cli("claim", "--root", str(tree / "TSLG"), cwd=client)
    assert _raw(tree / "TSLG")["subs"] == ["Server", "Client"]          # 冪等
    _cli("claim", "--root", str(tree / "TSLG"), "--both", cwd=client)
    assert _raw(client) == {"root": ".."}
    assert R(client).claimed_by == "own-root"


def test_cli_dry_run_and_unknown_keys_preserved(tree):
    p = _decl(tree / "TSLG", subs=["Server"], note="keep me")
    before = p.read_text(encoding="utf-8")
    _cli("--dry-run", "add-sub", "Client", cwd=tree / "TSLG")
    assert p.read_text(encoding="utf-8") == before
    _cli("add-sub", "Client", "Client", cwd=tree / "TSLG")
    raw = _raw(tree / "TSLG")
    assert raw["subs"] == ["Server", "Client"] and raw["note"] == "keep me"
    _cli("remove-sub", "Server", cwd=tree / "TSLG")
    assert _raw(tree / "TSLG")["subs"] == ["Client"]


def test_cli_set_root_unset_root_standalone(tree, tmp_path):
    server = tree / "TSLG" / "Server"
    _cli("set-root", str(tree / "TSLG"), "--abs", cwd=server)
    raw = _raw(server)
    assert raw["root"] == ".." and Path(raw["root_abs"]).resolve() == (tree / "TSLG").resolve()
    other = tmp_path / "Other"
    other.mkdir()
    out = _cli("set-root", str(other), cwd=server, expect_fail=True)
    assert "只准指祖先" in out
    _cli("unset-root", cwd=server)
    raw = _raw(server)
    assert "root" not in raw and "root_abs" not in raw and raw["subs"] == ["scripts"]
    _cli("standalone", "on", cwd=server)
    assert _raw(server)["standalone"] is True and R(server / "scripts").standalone
    _cli("standalone", "off", cwd=server)
    assert "standalone" not in _raw(server)


def test_cli_explain_json_and_show(tree):
    out = _cli("explain", str(tree / "TSLG" / "Server" / "scripts"), "--json")
    data = json.loads(out)
    assert Path(data["root"]).resolve() == (tree / "TSLG").resolve() and data["claimed_by"] == "ancestor-root"
    out = _cli("show", cwd=tree / "TSLG" / "Server" / "scripts")
    assert "WhoAmI" in out and "[有效]" in out and "目前生效" in out


def test_cli_pick_without_display_gives_alternative(tree, monkeypatch):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PROJECT_TREE_NO_GUI="1")
    r = subprocess.run([sys.executable, str(CLI), "--cwd", str(tree / "TSLG" / "Client"), "pick"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert r.returncode != 0 and "claim --root" in (r.stdout + r.stderr)
