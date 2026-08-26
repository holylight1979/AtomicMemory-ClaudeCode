"""verify_realm_category_paths.py — 核心層範疇資料夾（memory/<範疇>/…）路徑規則回歸測試。

覆蓋 lib.atom_locations 的範疇 helper（realm_root_for / path_segments_under /
core_category_segments / is_flat_core_path / validate_category_segment /
validate_category_path / iter_realm_category_dirs / unclassified_error / core_write_target）
與 lib.atom_taxonomy（load_taxonomy fail-closed / core_categories / match_lv1 /
failure_type_fallback / category_term_pairs）。

core_write_target 以 monkeypatch 把 GLOBAL_MEMORY_DIR / CLAUDE_DIR 指到 tmp，
不碰現役 memory/ 樹；taxonomy 讀現役 memory/_meta/taxonomy.json（單一真相，測它本身）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude
if str(CLAUDE) not in sys.path:
    sys.path.insert(0, str(CLAUDE))

import lib.atom_locations as AL  # noqa: E402
import lib.atom_taxonomy as AT  # noqa: E402
from lib.atom_locations import (  # noqa: E402
    CATEGORY_RESERVED_SEGMENTS, CORE_ATOMS_REL, FAILURES_ROOT_NAME,
    LEGACY_FAILURES_REL, LOCAL_ATOMS_REL,
    core_category_segments, core_write_target, is_flat_core_path,
    iter_realm_category_dirs, path_segments_under, realm_root_for,
    unclassified_error, validate_category_path, validate_category_segment,
)
from lib.atom_taxonomy import (  # noqa: E402
    TAXONOMY_PATH, TaxonomyUnavailable, category_term_pairs, core_categories,
    failure_type_fallback, load_taxonomy, match_lv1,
)


# ─── 根與段 ──────────────────────────────────────────────────────────────────


def test_realm_root_for():
    assert realm_root_for("memory/decisions.md") == CORE_ATOMS_REL
    assert realm_root_for("memory/版控/Git/x.md") == CORE_ATOMS_REL
    assert realm_root_for("_AIDocs/_atoms/Tools/x.md") == LOCAL_ATOMS_REL
    assert realm_root_for("_AIDocs/Failures/feedback-x.md") == LEGACY_FAILURES_REL
    assert realm_root_for("_AIDocs/SPEC.md") is None
    assert realm_root_for("memoryx/a.md") is None
    assert realm_root_for("") is None


def test_path_segments_under():
    assert path_segments_under("memory/a/b/slug.md", "memory") == ["a", "b"]
    assert path_segments_under("memory/slug.md", "memory") == []
    assert path_segments_under("_AIDocs/_atoms/Tools/slug.md", "memory") == []
    assert path_segments_under("memory//a//slug.md", "memory") == ["a"]


def test_core_category_segments():
    assert core_category_segments("memory/版控/Git/slug.md") == ["版控", "Git"]
    assert core_category_segments("memory/Failures/驗證與實證/feedback-x.md") == ["Failures", "驗證與實證"]
    assert core_category_segments("memory/slug.md") == []
    assert core_category_segments("_AIDocs/Failures/feedback-x.md") == ["Failures"]
    assert core_category_segments("_AIDocs/Failures/topic/feedback-x.md") == ["Failures", "topic"]
    assert core_category_segments("_AIDocs/_atoms/Tools/x.md") == []


def test_is_flat_core_path():
    assert is_flat_core_path("memory/decisions.md") is True
    assert is_flat_core_path("memory/版控/x.md") is False
    assert is_flat_core_path("_AIDocs/Failures/feedback-x.md") is False
    assert is_flat_core_path("_AIDocs/_atoms/Tools/x.md") is False


# ─── 段驗證 ──────────────────────────────────────────────────────────────────


def test_validate_category_segment_rejects_every_reserved_member():
    assert CATEGORY_RESERVED_SEGMENTS, "reserved set must not be empty"
    for name in CATEGORY_RESERVED_SEGMENTS:
        assert validate_category_segment(name) == "", name
        # casefold 變體（Templates / SHARED…）一樣拒
        assert validate_category_segment(name.capitalize()) == "", name
        assert validate_category_segment(name.upper()) == "", name


def test_validate_category_segment_rejects_shapes():
    assert validate_category_segment("Templates") == ""
    assert validate_category_segment("_x") == ""
    assert validate_category_segment(".x") == ""
    assert validate_category_segment("_archive2026") == ""
    assert validate_category_segment("a/b") == ""
    assert validate_category_segment("a\\b") == ""
    assert validate_category_segment("자동화") == ""  # Hangul：非 CJK/ASCII
    assert validate_category_segment("") == ""
    assert validate_category_segment("   ") == ""


def test_validate_category_segment_accepts_and_allow():
    assert validate_category_segment("版控") == "版控"
    assert validate_category_segment("OS-Windows") == "OS-Windows"
    assert validate_category_segment("  版控  ") == "版控"
    # Failures 只在 allow 明列時放行；小寫 failures 永遠拒
    assert validate_category_segment(FAILURES_ROOT_NAME) == ""
    assert validate_category_segment(FAILURES_ROOT_NAME, allow=(FAILURES_ROOT_NAME,)) == FAILURES_ROOT_NAME
    assert validate_category_segment("failures", allow=(FAILURES_ROOT_NAME,)) == ""


def test_validate_category_path():
    assert validate_category_path("") == ([], None)
    assert validate_category_path(None) == ([], None)
    assert validate_category_path("版控/Git") == (["版控", "Git"], None)
    assert validate_category_path("版控\\Git") == (["版控", "Git"], None)
    # depth 截尾
    segs, err = validate_category_path("a/b/c/d", max_depth=2)
    assert (segs, err) == (["a", "b"], None)
    # 第一段 allow：Failures 預設放行、第二段不放行
    assert validate_category_path("Failures/驗證與實證") == (["Failures", "驗證與實證"], None)
    segs, err = validate_category_path("版控/Failures")
    assert segs == [] and err and "Failures" in err
    segs, err = validate_category_path("Failures/x", allow_first=())
    assert segs == [] and err
    segs, err = validate_category_path("版控/_meta")
    assert segs == [] and "_meta" in err


def test_iter_realm_category_dirs(tmp_path):
    for d in ("版控", "_meta", "templates", "Failures", ".hidden"):
        (tmp_path / d).mkdir()
    (tmp_path / "loose.md").write_text("x", encoding="utf-8")
    names = [p.name for p in iter_realm_category_dirs(tmp_path)]
    assert names == ["Failures", "版控"]
    assert iter_realm_category_dirs(tmp_path / "nope") == []


# ─── taxonomy ────────────────────────────────────────────────────────────────


def test_taxonomy_loads_and_matches():
    data = load_taxonomy(TAXONOMY_PATH, force=True)
    cats = core_categories()
    assert cats == list(data["core"].keys())
    assert cats
    assert match_lv1("vcs") == "版控"
    assert match_lv1("版控") == "版控"
    assert match_lv1("VisualStudio") == "dotnet"
    assert match_lv1("cc") == "CC與原子記憶契約"
    assert match_lv1("definitely-not-a-category") is None
    assert match_lv1("") is None
    assert match_lv1(None) is None
    assert failure_type_fallback("env") == "OS-Windows"
    assert failure_type_fallback("nope") is None
    pairs = category_term_pairs()
    assert pairs
    assert {c for _t, c in pairs} <= set(cats)
    # 每個 Lv1 正名都是合法範疇段，且不撞保留名
    for c in cats:
        assert validate_category_segment(c) == c, c
    assert not ({c.lower() for c in cats} & CATEGORY_RESERVED_SEGMENTS)


def test_taxonomy_unavailable_fail_closed(tmp_path):
    broken = tmp_path / "taxonomy.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(TaxonomyUnavailable):
        load_taxonomy(broken, force=True)
    with pytest.raises(TaxonomyUnavailable):
        core_categories(broken)
    missing = tmp_path / "missing.json"
    with pytest.raises(TaxonomyUnavailable):
        core_categories(missing)
    empty_core = tmp_path / "empty.json"
    empty_core.write_text(json.dumps({"core": {}}), encoding="utf-8")
    with pytest.raises(TaxonomyUnavailable):
        load_taxonomy(empty_core, force=True)


# ─── core_write_target（tmp 隔離）────────────────────────────────────────────


@pytest.fixture
def tmp_core(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()
    monkeypatch.setattr(AL, "GLOBAL_MEMORY_DIR", mem)
    monkeypatch.setattr(AL, "CLAUDE_DIR", tmp_path)
    return mem


def test_core_write_target_known_lv1_with_lv2(tmp_core):
    target, err = core_write_target("vcs/git", existing_paths=["版控/Git"])
    assert err is None
    assert target["category"] == "版控/Git"
    assert target["dir"] == tmp_core / "版控" / "Git"
    assert target["dir"].is_dir()
    assert target["index_dir"] == tmp_core
    assert target["index_root"] == tmp_core.parent


def test_core_write_target_unknown_lv1_rejected(tmp_core):
    target, err = core_write_target("nope", existing_paths=[])
    assert target is None
    for c in core_categories():
        assert c in err
    assert "allow_new_category" in err
    assert not (tmp_core / "nope").exists()


def test_core_write_target_allow_new(tmp_core):
    target, err = core_write_target("nope", allow_new=True, existing_paths=[])
    assert err is None
    assert target["category"] == "nope"
    assert (tmp_core / "nope").is_dir()
    target, err = core_write_target("templates", allow_new=True, existing_paths=[])
    assert target is None and err
    assert not (tmp_core / "templates").exists()


def test_core_write_target_failures_and_empty(tmp_core):
    # Failures 家族不走本函式：首段（大小寫不分）是 Failures 就直接導向 failures 路由提示，
    # 不論 allow_new；不建目錄。
    target, err = core_write_target("Failures/x", existing_paths=[])
    assert target is None and err
    assert "failures routing" in err
    target, err = core_write_target("failures/x", allow_new=True, existing_paths=[])
    assert target is None and "failures routing" in err
    assert not (tmp_core / "Failures").exists()
    target, err = core_write_target("", existing_paths=[])
    assert target is None
    assert "unclassified" in err
    target, err = core_write_target(None, existing_paths=[])
    assert target is None and "unclassified" in err


def test_unclassified_error_lists_categories():
    msg = unclassified_error("zzz", ["版控", "工作流"], layer="core")
    assert "版控" in msg and "工作流" in msg
    assert "zzz" in msg
    assert "allow_new_category" in msg
