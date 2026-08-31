"""verify_locate_single_authority.py — lib/atom_io.locate_atom 是 atom 落點的唯一裁決者。

原本 js（atom-tools.js / realm.js）自算落點、只在 create 採 py 結果；現全部改問 py。
本檔守「從 js 搬進 py 的控管」每一條都還在：
- cwd-scope 防護（enforce_cwd_scope）：專案 cwd 禁寫 global；~/.claude 子樹禁寫 shared
- 分隔符變體撞名：create 擋、非 create 只提示（extra.separator_variant）
- 敏感 audience → _pending_review（routed_to_pending）
- 回傳欄位齊全（js 只採用不重算）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

LIB_PARENT = Path(__file__).resolve().parents[2]
if str(LIB_PARENT) not in sys.path:
    sys.path.insert(0, str(LIB_PARENT))

from lib import atom_io  # noqa: E402
from lib.atom_io import locate_atom  # noqa: E402
from lib.atom_locations import find_separator_variant  # noqa: E402


@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "proj"
    (root / ".git").mkdir(parents=True)
    (root / ".claude" / "memory" / "shared").mkdir(parents=True)
    (root / ".claude" / "memory" / "MEMORY.md").write_text("# m\n", encoding="utf-8")
    return root


def test_global_from_project_cwd_rejected_only_when_enforced(proj):
    r = locate_atom("x-y", "global", project_cwd=str(proj), domain="版控/Git",
                    mode="create", enforce_cwd_scope=True)
    assert not r.ok and "inside project root" in (r.error or "")
    # 程式寫手（hooks）不開閘 → 照舊放行
    r2 = locate_atom("x-y", "global", project_cwd=str(proj), domain="版控/Git", mode="create")
    assert r2.ok


def test_global_from_claude_dir_allowed():
    r = locate_atom("x-y", "global", project_cwd=str(atom_io.CLAUDE_DIR / "hooks"),
                    domain="版控/Git", mode="create", enforce_cwd_scope=True)
    assert r.ok, r.error
    assert r.extra["index_root"].replace("\\", "/").rstrip("/").endswith(".claude")


def test_shared_under_claude_dir_rejected():
    r = locate_atom("x-y", "shared", project_cwd=str(atom_io.CLAUDE_DIR / "tools"),
                    domain="版控/Git", mode="create")
    assert not r.ok and "under ~/.claude" in (r.error or "")


def test_return_fields_complete(proj, monkeypatch):
    monkeypatch.setattr(atom_io, "_category_gate_enabled", lambda: True)
    r = locate_atom("brand-new-atom", "shared", project_cwd=str(proj), domain="版控/Git",
                    mode="create", enforce_cwd_scope=True)
    assert r.ok and r.path is None, r.error
    x = r.extra
    for k in ("target_dir", "base_dir", "index_dir", "index_root", "scope_label", "slug",
              "create_rel_path", "routed_to_failures", "routed_to_pending", "routed_to_local",
              "category"):
        assert k in x, f"missing {k}"
    assert x["slug"] == "brand-new-atom" and x["scope_label"] == "shared"
    assert x["create_rel_path"] == "memory/shared/版控/Git/brand-new-atom.md"
    assert Path(x["index_dir"]) == proj / ".claude" / "memory"


def test_sensitive_audience_routes_pending(proj):
    r = locate_atom("arch-note", "shared", project_cwd=str(proj), audience=["architecture"],
                    mode="create", enforce_cwd_scope=True)
    assert r.ok and r.extra["routed_to_pending"] is True
    assert r.extra["target_dir"].replace("\\", "/").endswith("shared/_pending_review")


def test_separator_variant_blocks_create_but_only_hints_otherwise(proj):
    (proj / ".claude" / "memory" / "shared" / "client_il.md").write_text("# x\n", encoding="utf-8")
    roots = [proj / ".claude" / "memory"]
    assert find_separator_variant(roots, "client-il") == "shared/client_il.md"
    r = locate_atom("client-il", "shared", project_cwd=str(proj), domain="版控/Git", mode="create")
    assert not r.ok and "Slug collision" in (r.error or "")
    r2 = locate_atom("client-il", "shared", project_cwd=str(proj), mode="replace")
    assert r2.ok and r2.path is None and r2.extra["separator_variant"] == "shared/client_il.md"


def test_existing_atom_found_in_subfolder_with_rel_path(proj):
    sub = proj / ".claude" / "memory" / "shared" / "Tools"
    sub.mkdir(parents=True)
    (sub / "deep-atom.md").write_text("# deep\n", encoding="utf-8")
    r = locate_atom("deep-atom", "shared", project_cwd=str(proj), mode="append")
    assert r.ok and r.path == sub / "deep-atom.md"
    assert r.extra["rel_path"] == "memory/shared/Tools/deep-atom.md"
