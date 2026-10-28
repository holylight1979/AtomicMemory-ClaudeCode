"""verify_atom_spec_depends_evidence.py — Depends（壞滅緣）/ Evidence（證據等級）解析守門.

守住規則：
1. Depends 解析：`path:` 條目 → path 型（機器可驗）；其他 → free 型（僅展示）。
2. resolve_depends_path：~ 展開 / 絕對原樣 / 相對以 ~/.claude 為根。
3. 兩欄皆 optional：缺欄零警告、validate_atom_content 不因缺欄或有欄而 fail
   （向後相容鐵則：既有 atom 一顆都不得因缺欄位而報錯）。
4. Evidence 非法值 → warning 級（不 fail）；rank 實證3>引述2>推測1>未標0。
"""

from __future__ import annotations

import sys
from pathlib import Path

LIB_PARENT = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude/
if str(LIB_PARENT) not in sys.path:
    sys.path.insert(0, str(LIB_PARENT))

from lib.atom_spec import (  # noqa: E402
    OPTIONAL_METADATA, VALID_EVIDENCE,
    build_atom_content, classify_depends_path, depends_base_for_file, depends_warnings, evidence_rank, evidence_warning,
    parse_depends, parse_evidence, parse_frontmatter, portable_depends_path, resolve_depends_path,
    validate_atom_content,
)
from lib.project_root import claude_data_dir  # noqa: E402


# ─── Depends 存在性分級（跨機共享的卡：他機路徑不是壞滅緣）────────────────────

_FOREIGN_ROOT = "C:/zzq-no-such-root-9f3a" if sys.platform == "win32" else "/zzq-no-such-root-9f3a"


def test_classify_local_existing_is_ok(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("1", encoding="utf-8")
    assert classify_depends_path(str(f), claude_dir=tmp_path) == ("ok", f)


def test_classify_local_missing_under_existing_anchor_is_missing(tmp_path):
    """本機路徑、最上層錨點存在、檔不在 → missing（真的壞滅緣）。"""
    level, _ = classify_depends_path(str(tmp_path / "gone" / "x.py"), claude_dir=tmp_path)
    assert level == "missing"


def test_classify_other_home_claude_rebased_to_local_data_root(tmp_path):
    """別人 `<家目錄>/.claude/<rel>`：換成本機資料根再查——在就 ok、不在才 missing（作者機的 .claude 對應本機的 .claude）。"""
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "t.py").write_text("1", encoding="utf-8")
    for other in ("C:/Users/holylight/.claude/tools/t.py", "C:\\Users\\holylight\\.claude\\tools\\t.py", "/home/holylight/.claude/tools/t.py"):
        level, used = classify_depends_path(other, claude_dir=tmp_path)
        assert (level, used) == ("ok", tmp_path / "tools" / "t.py"), other
    level, used = classify_depends_path("C:/Users/holylight/.claude/tools/gone.py", claude_dir=tmp_path)
    assert level == "missing" and used == tmp_path / "tools" / "gone.py"


def test_classify_foreign_anchor_is_foreign_not_missing(tmp_path):
    """最上層錨點本機沒有（C:/Projects/…、C:/Users/<別人>/<非 .claude>）→ foreign：本機驗不到，不算壞滅緣。"""
    assert classify_depends_path(f"{_FOREIGN_ROOT}/Projects/SGI/tools/x.py", claude_dir=tmp_path)[0] == "foreign"
    assert classify_depends_path(f"{_FOREIGN_ROOT}/Users/holylight/other/x.py", claude_dir=tmp_path)[0] == "foreign"


def test_classify_relative_resolves_with_base(tmp_path):
    proj = tmp_path / "proj"
    (proj / "tools").mkdir(parents=True)
    (proj / "tools" / "t.py").write_text("1", encoding="utf-8")
    assert classify_depends_path("tools/t.py", claude_dir=tmp_path, base=proj)[0] == "ok"
    assert classify_depends_path("tools/t.py", claude_dir=tmp_path)[0] == "missing"


def test_depends_base_for_file_project_and_root(tmp_path):
    proj = tmp_path / "proj"
    card = proj / ".claude" / "memory" / "shared" / "x" / "c.md"
    card.parent.mkdir(parents=True)
    assert depends_base_for_file(card) == proj
    assert depends_base_for_file(tmp_path / "loose.md") is None


def test_portable_depends_path_project_then_data_root_then_absolute(tmp_path):
    proj = tmp_path / "proj"
    data = tmp_path / "claude"
    for p in (proj / ".claude" / "tools" / "t.py", data / "tools" / "u.py", tmp_path / "elsewhere" / "v.py"):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("1", encoding="utf-8")
    assert portable_depends_path(proj / ".claude" / "tools" / "t.py", project_root=proj, claude_dir=data) == ".claude/tools/t.py"
    assert portable_depends_path(data / "tools" / "u.py", project_root=proj, claude_dir=data) == "~/.claude/tools/u.py"
    assert portable_depends_path(tmp_path / "elsewhere" / "v.py", project_root=proj, claude_dir=data) == (tmp_path / "elsewhere" / "v.py").as_posix()


# ─── Depends 解析 ────────────────────────────────────────────────────────────


def test_parse_depends_path_and_free_mixed():
    entries = parse_depends("path:memory/foo.md, decision:xxx, hooks v2 行為")
    assert entries == [
        {"type": "path", "value": "memory/foo.md"},
        {"type": "free", "value": "decision:xxx"},
        {"type": "free", "value": "hooks v2 行為"},
    ]


def test_parse_depends_fullwidth_comma_and_whitespace():
    entries = parse_depends(" path:a.md ， path:b.md ")
    assert [e["value"] for e in entries] == ["a.md", "b.md"]
    assert all(e["type"] == "path" for e in entries)


def test_parse_depends_empty_and_none_silent():
    assert parse_depends("") == []
    assert parse_depends(None) == []
    assert parse_depends("  ,  ，  ") == []


def test_parse_depends_windows_abs_path_no_comma_split():
    entries = parse_depends(r"path:C:\Users\x\file.md")
    assert entries == [{"type": "path", "value": r"C:\Users\x\file.md"}]


def test_depends_warnings_empty_path_value():
    assert depends_warnings("path:") == ["Depends 條目 `path:` 缺路徑值"]
    assert depends_warnings("path:ok.md, decision:xxx") == []
    assert depends_warnings(None) == []
    assert depends_warnings("") == []


# ─── resolve_depends_path ────────────────────────────────────────────────────


def test_resolve_relative_rooted_at_claude_dir(tmp_path):
    p = resolve_depends_path("memory/foo.md", claude_dir=tmp_path)
    assert p == tmp_path / "memory" / "foo.md"


def test_resolve_default_root_is_data_root():
    p = resolve_depends_path("memory/foo.md")
    assert p == claude_data_dir() / "memory" / "foo.md"   # 資料根（WG_CLAUDE_DIR 或 ~/.claude）


def test_resolve_tilde_expands():
    p = resolve_depends_path("~/.claude/memory/foo.md")
    assert p == Path.home() / ".claude" / "memory" / "foo.md"


def test_resolve_absolute_untouched(tmp_path):
    abs_p = tmp_path / "x.md"
    assert resolve_depends_path(str(abs_p), claude_dir=tmp_path / "other") == abs_p


# ─── Evidence 解析 / rank ────────────────────────────────────────────────────


def test_parse_evidence_valid_values():
    for v in VALID_EVIDENCE:
        assert parse_evidence(v) == v
        assert parse_evidence(f"  {v}  ") == v


def test_parse_evidence_invalid_or_missing_is_none():
    assert parse_evidence(None) is None
    assert parse_evidence("") is None
    assert parse_evidence("proven") is None


def test_evidence_warning_only_on_illegal_value():
    assert evidence_warning(None) is None
    assert evidence_warning("") is None
    assert evidence_warning("實證") is None
    w = evidence_warning("很確定")
    assert w is not None and "很確定" in w


def test_evidence_rank_ordering():
    assert evidence_rank("實證") > evidence_rank("引述") > evidence_rank("推測") > evidence_rank(None)
    assert evidence_rank("非法值") == 0 == evidence_rank("")


# ─── 向後相容：optional 欄位不影響 validate / frontmatter ────────────────────


def _atom_with_meta(extra_meta: str = "") -> str:
    return (
        "# 測試 atom\n\n"
        "- Scope: global\n"
        "- Confidence: [臨]\n"
        "- Trigger: a, b, c\n"
        f"{extra_meta}"
        "\n## 知識\n\n- 內容\n\n"
        "## 行動\n\n- 行動項\n"
    )


def test_atom_without_new_fields_still_valid():
    assert validate_atom_content(_atom_with_meta()) is None


def test_atom_with_depends_and_evidence_still_valid():
    content = _atom_with_meta("- Depends: path:memory/foo.md, decision:xxx\n"
                              "- Evidence: 實證\n")
    assert validate_atom_content(content) is None
    fm = parse_frontmatter(content)
    assert fm["Depends"] == "path:memory/foo.md, decision:xxx"
    assert fm["Evidence"] == "實證"


def test_atom_with_illegal_evidence_does_not_fail_validate():
    """非法 Evidence 值只到 warning 級（evidence_warning），validate 不 fail。"""
    content = _atom_with_meta("- Evidence: 很確定\n")
    assert validate_atom_content(content) is None
    assert evidence_warning(parse_frontmatter(content).get("Evidence")) is not None


def test_optional_metadata_declares_new_fields():
    assert "Depends" in OPTIONAL_METADATA
    assert "Evidence" in OPTIONAL_METADATA


def test_build_atom_content_unchanged_and_valid():
    """build_atom_content 不產新欄（server.js byte-identical 契約不動）。"""
    content = build_atom_content(
        title="t", scope="global", confidence="[臨]",
        triggers=["a"], knowledge=["k"],
    )
    assert "Depends" not in content and "Evidence" not in content
    assert validate_atom_content(content) is None
