"""verify_atom_locate_scope.py — 索引 SoT 定位 + scope 沿用 + subdir 落點守門。

不變式（對應多專案共用庫實案：memory/projects/<專案名>/ 分區）：
1. 已歸位到 memory root 下任意兄弟子夾（projects/<X>/…）的 shared atom，
   append/replace 必須定位得到（索引 path 優先；索引缺條目時 rglob 補位）。
2. 索引 scope 永不被寫入路徑蹍掉：create 寫 scope_label、replace/edit_metadata 沿用
   既有值；atom-move 預設沿用（含 cross-root），變更須 --scope 明確指定且
   scope_changed 據實回報。
3. subdir（相對 memory root，僅 scope=shared）一次寫到位；逐段沙盒化，
   traversal / `_` 前綴 / 受保護段（personal/roles/…）拒絕。
4. trigger 長度在寫入當下即驗（create/replace）；append 不動既有 triggers 不受牽連。
5. edit_metadata 支援專案層 atom（index root 上溯定位，不硬編 ~/.claude）。
6. 跨 scope 保護不因定位放寬而失守（personal/roles 段層級排除）。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude
sys.path.insert(0, str(CLAUDE))

from lib.atom_io import write_atom, write_index, edit_metadata, locate_atom  # noqa: E402
from lib.atom_index_json import load_atom_index_json  # noqa: E402

ATOM_BODY = """# {slug}

- Scope: shared
- Author: tester
- Confidence: [臨]
- Trigger: probe
- Created-at: 2026-07-28

## 知識

- [臨] seed

## 行動

- probe
"""


def _mkproject(tmp_path: Path, files: dict, index: list | None = None) -> Path:
    mem = tmp_path / ".claude" / "memory"
    mem.mkdir(parents=True)
    (mem / "MEMORY.md").write_text("# idx\n", encoding="utf-8")
    for rel, slug in files.items():
        p = mem / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(ATOM_BODY.format(slug=slug), encoding="utf-8")
    (mem / "_atom_index.json").write_text(
        json.dumps({"version": "1.0", "atoms": index or []}, ensure_ascii=False),
        encoding="utf-8")
    return tmp_path


def _index_entry(root: Path, name: str) -> dict:
    data = load_atom_index_json(root / ".claude" / "memory")
    return next(a for a in data["atoms"] if a["name"] == name)


def _run_atom_move(*argv: str) -> dict:
    cp = subprocess.run(
        [sys.executable, str(CLAUDE / "tools" / "atom-move.py"), *argv],
        capture_output=True, text=True, encoding="utf-8", cwd=str(CLAUDE))
    assert cp.returncode == 0, f"atom-move exit {cp.returncode}\n{cp.stdout}\n{cp.stderr}"
    return json.loads(cp.stdout)


# ─── 1. projects/<X>/ 分區定位（使用者實案重現） ─────────────────────────────


def test_replace_finds_atom_in_projects_partition_via_index(tmp_path):
    root = _mkproject(
        tmp_path, {"projects/testp/gamma.md": "gamma"},
        index=[{"name": "gamma", "path": "memory/projects/testp/gamma.md",
                "triggers": ["probe"], "scope": "shared"}])
    r = write_atom(title="gamma", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] replaced"],
                   mode="replace", source="mcp", project_cwd=str(root))
    assert r.ok, r.error
    assert r.path == root / ".claude/memory/projects/testp/gamma.md"
    assert _index_entry(root, "gamma")["path"] == "memory/projects/testp/gamma.md"


def test_append_finds_atom_in_projects_partition_via_rglob(tmp_path):
    root = _mkproject(tmp_path, {"projects/testp/delta.md": "delta"})  # 索引無條目
    r = write_atom(title="delta", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] appended"],
                   mode="append", source="mcp", project_cwd=str(root))
    assert r.ok, r.error
    assert r.path == root / ".claude/memory/projects/testp/delta.md"


def test_create_dup_guard_when_slug_lives_in_partition(tmp_path):
    root = _mkproject(
        tmp_path, {"projects/testp/gamma.md": "gamma"},
        index=[{"name": "gamma", "path": "memory/projects/testp/gamma.md",
                "triggers": ["probe"], "scope": "shared"}])
    r = write_atom(title="gamma", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] fork"], actions=["x"],
                   mode="create", source="mcp", project_cwd=str(root), domain="工作流")
    assert not r.ok and "already exists" in (r.error or ""), r


# ─── 2. scope 沿用 ────────────────────────────────────────────────────────────


def test_create_writes_scope_label_to_index(tmp_path):
    root = _mkproject(tmp_path, {})
    r = write_atom(title="epsilon", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] fresh"], actions=["x"],
                   mode="create", source="mcp", project_cwd=str(root), domain="工作流")
    assert r.ok, r.error
    assert _index_entry(root, "epsilon")["scope"] == "shared"


def test_replace_preserves_index_scope(tmp_path):
    """使用者實案的髒污鏈：replace 曾把 scope 蹍回 global。"""
    root = _mkproject(
        tmp_path, {"shared/zeta.md": "zeta"},
        index=[{"name": "zeta", "path": "memory/shared/zeta.md",
                "triggers": ["probe"], "scope": "shared"}])
    r = write_atom(title="zeta", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] replaced"],
                   mode="replace", source="mcp", project_cwd=str(root))
    assert r.ok, r.error
    assert _index_entry(root, "zeta")["scope"] == "shared"


def test_write_index_new_entry_defaults_global(tmp_path):
    root = _mkproject(tmp_path, {})
    mem = root / ".claude" / "memory"
    res = write_index(mem, "fresh", "memory/shared/fresh.md", ["probe"], "test")
    assert res.ok, res.error
    assert _index_entry(root, "fresh")["scope"] == "global"


def test_write_index_explicit_scope_wins(tmp_path):
    root = _mkproject(
        tmp_path, {}, index=[{"name": "eta", "path": "memory/shared/eta.md",
                              "triggers": ["probe"], "scope": "shared"}])
    mem = root / ".claude" / "memory"
    res = write_index(mem, "eta", "memory/shared/eta.md", ["probe"], "test",
                      scope="role:art")
    assert res.ok, res.error
    assert _index_entry(root, "eta")["scope"] == "role:art"


def test_atom_move_roundtrip_preserves_scope_with_replace_in_between(tmp_path):
    """完整髒污鏈重放：shared→projects → replace → projects→shared，scope 全程 shared。"""
    root = _mkproject(
        tmp_path, {"shared/theta.md": "theta"},
        index=[{"name": "theta", "path": "memory/shared/theta.md",
                "triggers": ["probe"], "scope": "shared"}])
    mem = root / ".claude" / "memory"
    (mem / "projects" / "testp").mkdir(parents=True)

    rep1 = _run_atom_move("move", "theta", "--from", str(mem / "shared"),
                          "--to", str(mem / "projects" / "testp"))
    assert rep1["scope"] == "shared" and rep1["scope_changed"] is False, rep1

    r = write_atom(title="theta", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] replaced in partition"],
                   mode="replace", source="mcp", project_cwd=str(root))
    assert r.ok, r.error
    assert _index_entry(root, "theta")["scope"] == "shared"

    rep2 = _run_atom_move("move", "theta", "--from", str(mem / "projects" / "testp"),
                          "--to", str(mem / "shared"))
    assert rep2["scope"] == "shared" and rep2["scope_changed"] is False, rep2


def test_atom_move_explicit_scope_override_reports_change(tmp_path):
    root = _mkproject(
        tmp_path, {"shared/iota.md": "iota"},
        index=[{"name": "iota", "path": "memory/shared/iota.md",
                "triggers": ["probe"], "scope": "shared"}])
    mem = root / ".claude" / "memory"
    (mem / "projects" / "testp").mkdir(parents=True)
    rep = _run_atom_move("move", "iota", "--from", str(mem / "shared"),
                         "--to", str(mem / "projects" / "testp"),
                         "--scope", "project")
    assert rep["scope"] == "project" and rep["scope_changed"] is True, rep
    assert _index_entry(root, "iota")["scope"] == "project"


# ─── 3. subdir 落點 ───────────────────────────────────────────────────────────


def test_subdir_create_lands_in_partition(tmp_path):
    """subdir 是分區根、domain 是範疇：落 <subdir>/<Lv1>[/<Lv2>]/（範疇閘對專案層同規則）。"""
    root = _mkproject(tmp_path, {})
    r = write_atom(title="kappa", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] fresh"], actions=["x"],
                   mode="create", source="mcp", project_cwd=str(root),
                   subdir="projects/testp", domain="vcs/git")
    assert r.ok, r.error
    assert r.path == root / ".claude/memory/projects/testp/版控/Git/kappa.md"
    entry = _index_entry(root, "kappa")
    assert entry["path"] == "memory/projects/testp/版控/Git/kappa.md"
    assert entry["scope"] == "shared"
    # subdir 給了、domain 沒給 → 仍拒（分區不是分類）
    bad = write_atom(title="kappa2", scope="shared", confidence="[臨]",
                     triggers=["probe"], knowledge=["[臨] fresh"], actions=["x"],
                     mode="create", source="mcp", project_cwd=str(root),
                     subdir="projects/testp")
    assert not bad.ok and "unclassified shared atom" in (bad.error or ""), bad


def test_subdir_rejects_traversal_protected_and_wrong_scope(tmp_path):
    root = _mkproject(tmp_path, {})
    for bad_subdir, expect in [
        ("../escape", "invalid subdir"),
        ("_meta", "invalid subdir"),
        ("personal/holylight", "protected"),
        ("roles/art", "protected"),
    ]:
        r = write_atom(title="lam", scope="shared", confidence="[臨]",
                       triggers=["probe"], knowledge=["[臨] x"], actions=["x"],
                       mode="create", source="mcp", project_cwd=str(root),
                       subdir=bad_subdir)
        assert not r.ok and expect in (r.error or ""), (bad_subdir, r.error)
    g = write_atom(title="lam", scope="global", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] x"], actions=["x"],
                   mode="create", source="mcp", subdir="projects/testp",
                   dry_run=True)
    assert not g.ok and "only supported for scope=shared" in (g.error or ""), g


def test_sensitive_audience_overrides_subdir(tmp_path):
    """敏感 audience → _pending_review 路由優先於 subdir（安全優先，不得被繞過）。"""
    root = _mkproject(tmp_path, {})
    r = write_atom(title="sens", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] x"], actions=["x"],
                   audience=["architecture"],
                   mode="create", source="mcp", project_cwd=str(root),
                   subdir="projects/testp")
    assert r.ok, r.error
    assert r.routed_to_pending, r
    assert r.path == root / ".claude/memory/shared/_pending_review/sens.md"


def test_no_subdir_lands_under_shared_category(tmp_path):
    """無 subdir → 層根 shared/<Lv1>/（別名 snap 回正名）；無 domain → 拒並列全部 Lv1。"""
    root = _mkproject(tmp_path, {})
    r = write_atom(title="mu", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] flat"], actions=["x"],
                   mode="create", source="mcp", project_cwd=str(root), domain="workflow")
    assert r.ok, r.error
    assert r.path == root / ".claude/memory/shared/工作流/mu.md"
    bad = write_atom(title="mu2", scope="shared", confidence="[臨]",
                     triggers=["probe"], knowledge=["[臨] flat"], actions=["x"],
                     mode="create", source="mcp", project_cwd=str(root))
    assert not bad.ok and "Valid Lv1" in (bad.error or ""), bad


# ─── 4. trigger 長度寫入時驗證 ────────────────────────────────────────────────


def test_trigger_too_long_rejected_at_write_time(tmp_path):
    root = _mkproject(tmp_path, {})
    long_trigger = "AuthoritativeUserMessageHandler"  # 31 chars（使用者實案）
    assert len(long_trigger) == 31
    r = write_atom(title="nu", scope="shared", confidence="[臨]",
                   triggers=[long_trigger], knowledge=["[臨] x"], actions=["x"],
                   mode="create", source="mcp", project_cwd=str(root))
    assert not r.ok and "trigger too long" in (r.error or ""), r


def test_append_unaffected_by_legacy_long_trigger(tmp_path):
    """append 不動索引 triggers——legacy 超長 trigger 的 atom 仍可 append。"""
    root = _mkproject(
        tmp_path, {"shared/xi.md": "xi"},
        index=[{"name": "xi", "path": "memory/shared/xi.md",
                "triggers": ["AuthoritativeUserMessageHandler"], "scope": "shared"}])
    r = write_atom(title="xi", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] appended"],
                   mode="append", source="mcp", project_cwd=str(root))
    assert r.ok, r.error


# ─── 5. edit_metadata 專案層支援 ──────────────────────────────────────────────


def test_edit_metadata_project_layer_atom(tmp_path):
    root = _mkproject(
        tmp_path, {"projects/testp/omicron.md": "omicron"},
        index=[{"name": "omicron", "path": "memory/projects/testp/omicron.md",
                "triggers": ["probe"], "scope": "shared"}])
    fp = root / ".claude/memory/projects/testp/omicron.md"
    res = edit_metadata(fp, triggers=["newtrig"], source="mcp")
    assert res.ok, res.error
    entry = _index_entry(root, "omicron")
    assert entry["triggers"] == ["newtrig"]
    assert entry["scope"] == "shared"  # 沿用，不被蹍回 global
    assert "- Trigger: newtrig" in fp.read_text(encoding="utf-8")


# ─── 6. 跨 scope 保護不失守 ───────────────────────────────────────────────────


def test_widened_shared_roots_still_skip_personal_and_roles(tmp_path):
    root = _mkproject(
        tmp_path, {
            "personal/holylight/secret.md": "secret",
            "roles/art/rolesecret.md": "rolesecret",
        },
        index=[{"name": "secret", "path": "memory/personal/holylight/secret.md",
                "triggers": ["probe"], "scope": "personal:holylight"},
               {"name": "rolesecret", "path": "memory/roles/art/rolesecret.md",
                "triggers": ["probe"], "scope": "role:art"}])
    for slug in ("secret", "rolesecret"):
        r = locate_atom(slug, "shared", project_cwd=str(root))
        assert r.ok and r.path is None, (slug, r)
