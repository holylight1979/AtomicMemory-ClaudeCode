"""verify_atom_subdir_locate.py — append/replace 對「子夾內既有 atom」的定位。

不變式：
1. atom 的寫入預設落點是**扁平**的（scope=shared → memory/shared/），但實體檔常被
   事後歸位到主題子夾（專案 classifier sweep / local realm）。append/replace 必須
   仍定位得到；只看扁平落點 = 死路（修補前 100% 失效於子夾化的專案 memory）。
2. 定位順序：_atom_index.json 的 path 優先 → 落空 rglob search_roots。
3. 撞名（多檔同 slug 且索引無條目）→ 明確報錯，**不靜默取第一個**。
4. 跨 scope 保護：scope=shared 不得定位到 personal/ 的檔；草稿牢籠（_drafts、
   personal/auto/）不得成為 append/replace 目標。
5. create 的落點由寫入閘決定（taxonomy.gate_enabled 關閉時落層根：shared/、memory/），
   append/replace 一律依 index 定位、不看落點規則。
6. scope=global 的 append/replace 依 index path 定位（根下散檔、memory/<範疇>/、_AIDocs/_atoms/
   皆同一條路），與 create 落點無關。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude
sys.path.insert(0, str(CLAUDE))

from lib.atom_io import locate_atom, write_atom  # noqa: E402
from lib.atom_locations import locate_existing_atom  # noqa: E402

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
    """建合成專案樹。files: {相對 memory/ 的 posix 路徑: slug}。"""
    mem = tmp_path / ".claude" / "memory"
    mem.mkdir(parents=True)
    (mem / "MEMORY.md").write_text("# idx\n", encoding="utf-8")
    for rel, slug in files.items():
        p = mem / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(ATOM_BODY.format(slug=slug), encoding="utf-8")
    (mem / "_atom_index.json").write_text(
        json.dumps({"atoms": index or []}, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_locate_subdir_atom_via_index(tmp_path):
    root = _mkproject(
        tmp_path, {"shared/Tools/alpha.md": "alpha"},
        index=[{"name": "alpha", "path": "memory/shared/Tools/alpha.md",
                "triggers": ["probe"], "scope": "shared"}])
    r = locate_atom("alpha", "shared", project_cwd=str(root))
    assert r.ok, r.error
    assert r.path == root / ".claude/memory/shared/Tools/alpha.md"
    assert r.extra["rel_path"] == "memory/shared/Tools/alpha.md"


def test_locate_subdir_atom_via_rglob_when_index_missing(tmp_path):
    root = _mkproject(tmp_path, {"shared/Gameplay/beta.md": "beta"})
    r = locate_atom("beta", "shared", project_cwd=str(root))
    assert r.ok, r.error
    assert r.path == root / ".claude/memory/shared/Gameplay/beta.md"


def test_append_writes_into_subdir_and_index_path_is_real(tmp_path):
    root = _mkproject(tmp_path, {"shared/Tools/alpha.md": "alpha"})
    target = root / ".claude/memory/shared/Tools/alpha.md"
    before = target.read_text(encoding="utf-8")
    r = write_atom(title="alpha", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] appended"],
                   mode="append", source="mcp", project_cwd=str(root))
    assert r.ok, r.error
    assert r.path == target
    after = target.read_text(encoding="utf-8")
    assert "appended" in after
    # 只新增，不重寫既有內容
    assert before.splitlines()[0] == after.splitlines()[0]
    assert len(after.splitlines()) == len(before.splitlines()) + 1


def test_replace_locates_subdir_and_index_path_points_there(tmp_path):
    root = _mkproject(tmp_path, {"shared/Tools/alpha.md": "alpha"})
    r = write_atom(title="alpha", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] replaced"],
                   mode="replace", source="mcp", project_cwd=str(root))
    assert r.ok, r.error
    assert r.path == root / ".claude/memory/shared/Tools/alpha.md"
    idx = json.loads((root / ".claude/memory/_atom_index.json").read_text(encoding="utf-8"))
    entry = next(a for a in idx["atoms"] if a["name"] == "alpha")
    assert entry["path"] == "memory/shared/Tools/alpha.md"
    assert (root / ".claude" / entry["path"]).exists()


def test_ambiguous_slug_errors_not_silent_first_hit(tmp_path):
    root = _mkproject(tmp_path, {
        "shared/Tools/dup.md": "dup",
        "shared/Server/dup.md": "dup",
    })
    r = locate_atom("dup", "shared", project_cwd=str(root))
    assert not r.ok
    assert "Ambiguous" in (r.error or "")
    # append 同樣被擋（不得任選一個寫入）
    w = write_atom(title="dup", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] x"],
                   mode="append", source="mcp", project_cwd=str(root))
    assert not w.ok and "Ambiguous" in (w.error or "")


def test_index_disambiguates_duplicate_slugs(tmp_path):
    root = _mkproject(tmp_path, {
        "shared/Tools/dup.md": "dup",
        "shared/Server/dup.md": "dup",
    }, index=[{"name": "dup", "path": "memory/shared/Server/dup.md",
               "triggers": ["probe"], "scope": "shared"}])
    r = locate_atom("dup", "shared", project_cwd=str(root))
    assert r.ok, r.error
    assert r.path.parent.name == "Server"


def test_shared_scope_does_not_reach_personal(tmp_path):
    root = _mkproject(tmp_path, {"personal/holylight/secret.md": "secret"})
    r = locate_atom("secret", "shared", project_cwd=str(root))
    assert r.ok and r.path is None, r


def test_index_entry_outside_scope_is_ignored(tmp_path):
    """索引 path 指向他 scope → 不採用（跨 scope 保護優先於索引）。"""
    root = _mkproject(
        tmp_path, {"personal/holylight/secret.md": "secret"},
        index=[{"name": "secret", "path": "memory/personal/holylight/secret.md",
                "triggers": ["probe"], "scope": "personal:holylight"}])
    r = locate_atom("secret", "shared", project_cwd=str(root))
    assert r.ok and r.path is None, r


def test_auto_capture_drafts_are_not_append_targets(tmp_path):
    root = _mkproject(tmp_path, {"shared/_drafts/auto-capture/draft.md": "draft"})
    r = locate_atom("draft", "shared", project_cwd=str(root))
    assert r.ok and r.path is None, r


def test_personal_scope_locates_own_user_subtree_only(tmp_path):
    root = _mkproject(tmp_path, {
        "personal/holylight/mine.md": "mine",
        "personal/auto/holylight/autodraft.md": "autodraft",
    })
    ok = locate_atom("mine", "personal", project_cwd=str(root), user="holylight")
    assert ok.ok and ok.path == root / ".claude/memory/personal/holylight/mine.md"
    # personal/auto/<user>/ 是 extract-worker 草稿夾，不在 scope 樹內
    draft = locate_atom("autodraft", "personal", project_cwd=str(root), user="holylight")
    assert draft.ok and draft.path is None, draft


def test_create_lands_by_write_gate_default(tmp_path):
    """create 落點由範疇寫入閘決定：domain 必填 → shared/<Lv1>/；不從既有子夾猜（Tools/ 不會被
    當落點）；無 domain → 拒。"""
    root = _mkproject(tmp_path, {"shared/Tools/alpha.md": "alpha"})
    r = write_atom(title="brandnew", scope="shared", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] fresh"], actions=["do"],
                   mode="create", source="mcp", project_cwd=str(root),
                   skip_gate=True, domain="design")
    assert r.ok, r.error
    assert r.path == root / ".claude/memory/shared/設計通則/brandnew.md"
    bad = write_atom(title="brandnew2", scope="shared", confidence="[臨]",
                     triggers=["probe"], knowledge=["[臨] fresh"], actions=["do"],
                     mode="create", source="mcp", project_cwd=str(root), skip_gate=True)
    assert not bad.ok and "unclassified shared atom" in (bad.error or ""), bad


def test_global_append_locates_by_index_path(tmp_path):
    """scope=global 的 append 依 index path 定位（範疇子夾 memory/<Lv1>/…），不繞定位器。"""
    from lib.atom_index_json import load_atom_index_json
    from lib.atom_locations import GLOBAL_MEMORY_DIR
    indexed = next(a["path"] for a in load_atom_index_json(GLOBAL_MEMORY_DIR)["atoms"]
                   if a.get("name") == "decisions")
    assert indexed.startswith("memory/") and "/" in indexed[len("memory/"):], indexed  # 已歸類、非根平鋪
    r = write_atom(title="decisions", scope="global", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] probe"],
                   mode="append", source="mcp", dry_run=True)
    assert r.ok, r.error
    assert r.extra["rel_path"] == indexed


def test_global_local_realm_atom_found_without_domain_hint(tmp_path):
    """realm/domain 沒給（或給錯）時，global append 仍定位得到 _atoms/ 下的實體檔。"""
    r = write_atom(title="realm-範疇分區機制-v5", scope="global", confidence="[臨]",
                   triggers=["probe"], knowledge=["[臨] probe"],
                   mode="append", source="mcp", dry_run=True)
    assert r.ok, r.error
    assert r.extra["rel_path"].startswith("_AIDocs/_atoms/"), r.extra


def test_locate_existing_atom_empty_roots_is_noop(tmp_path):
    p, err = locate_existing_atom("whatever", index_dir=tmp_path,
                                  index_root=tmp_path, search_roots=[])
    assert p is None and err is None
