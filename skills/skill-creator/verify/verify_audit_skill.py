"""verify_audit_skill.py — audit-skill.py 契約：官方格式錯誤才 fail，本機建議只 warning.

守住規則：
- frontmatter 用 YAML 解析：多行 description（`>` 折行）、list 型 triggers 都吃得到。
- 缺 description → fail；缺 triggers / pattern / name → warning，不 fail。
- 500 行是官方 Tip → warning（skill-md-over-500），不 fail。
- `userInvocable` 非官方拼法 → warning；`user-invocable` 正常。
- 每筆 fails/warnings 帶 src ∈ {official, local}。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent  # skills/skill-creator/
SPEC = importlib.util.spec_from_file_location("audit_skill", SKILL_DIR / "scripts" / "audit-skill.py")
AS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AS)


def _mk(tmp_path: Path, frontmatter: str, body_lines: int = 20, name: str = "demo") -> Path:
    d = tmp_path / name
    d.mkdir()
    body = "\n".join(f"line {i} 內容足夠長避免被當瑣碎行" for i in range(body_lines))
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n# Demo\n\n{body}\n", encoding="utf-8")
    return d


def _ids(entries):
    return {e["id"] for e in entries}


def test_multiline_description_parsed():
    fm, _, err = AS.parse_frontmatter(
        "---\nname: demo\ndescription: >\n  第一行很長的描述文字\n  第二行接著描述\ntriggers:\n  - a\n  - b\n  - c\n---\nbody\n"
    )
    assert err is None
    assert "第一行" in fm["description"] and "第二行" in fm["description"]
    assert fm["triggers"] == "a, b, c"


def test_missing_description_is_fail_missing_triggers_is_warning(tmp_path):
    d = _mk(tmp_path, "name: demo")
    res = AS.audit(d, "project")
    assert "frontmatter-missing-description" in _ids(res["fails"])
    assert "triggers-missing" in _ids(res["warnings"])
    assert "triggers-missing" not in _ids(res["fails"])


def test_official_only_frontmatter_has_zero_fails(tmp_path):
    d = _mk(tmp_path, "name: demo\ndescription: 這是一段超過三十個字的描述，用來確認官方欄位齊全時不會被判 fail 的情境。\nuser-invocable: true")
    res = AS.audit(d, "project")
    assert res["fail_count"] == 0
    assert {"triggers-missing", "pattern-missing"} <= _ids(res["warnings"])
    assert all(w["src"] in ("official", "local") for w in res["warnings"])


def test_legacy_spelling_is_warning_not_fail(tmp_path):
    d = _mk(tmp_path, "name: demo\ndescription: 這是一段超過三十個字的描述，用來確認舊拼法只警告不擋下的情境測試。\nuserInvocable: true")
    res = AS.audit(d, "project")
    assert res["fail_count"] == 0
    legacy = [w for w in res["warnings"] if w["id"] == "frontmatter-legacy-spelling"]
    assert legacy and legacy[0]["src"] == "official" and "user-invocable" in legacy[0]["msg"]


def test_over_500_lines_is_warning_not_fail(tmp_path):
    d = _mk(tmp_path, "name: demo\ndescription: 這是一段超過三十個字的描述，用來確認長度超過五百行只是官方建議不是紅線。", body_lines=520)
    res = AS.audit(d, "project")
    assert res["fail_count"] == 0
    over = [w for w in res["warnings"] if w["id"] == "skill-md-over-500"]
    assert over and over[0]["src"] == "official"


def test_unparseable_yaml_is_fail(tmp_path):
    d = _mk(tmp_path, "name: demo\ndescription: [unclosed\n  bad: : :")
    res = AS.audit(d, "project")
    assert "frontmatter-unparseable" in _ids(res["fails"])


def test_repo_skills_have_no_fails():
    """21 個真 skill 目錄（有 SKILL.md）在新契約下不該有 fail；有 fail 就是真格式問題。"""
    skills_root = SKILL_DIR.parent
    bad = {}
    for d in skills_root.iterdir():
        if not d.is_dir() or not (d / "SKILL.md").exists():
            continue
        res = AS.audit(d, "global")
        if res["fail_count"]:
            bad[d.name] = [f["id"] for f in res["fails"]]
    assert not bad, bad
