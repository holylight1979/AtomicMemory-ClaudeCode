"""verify_skill_index.py — skills/ 計數單一真相（SoT）工具。

驗證 tools/skill-index.py：
  - scan_skills 數 == 實際 */SKILL.md 數；frontmatter name/description 解析；
    無 name → 退回目錄名；_skill_index.json 根檔不計入
  - build_index count 正確
  - check：_skill_index.json count / 文件 marker 與實檔不符 → drift；相符 → ok
  - write：產 _skill_index.json + 重寫 marker；冪等（第二次零變更）
  - 真庫防護：當前 repo skill 計數無 drift（防 commit 進 drift）

對應：tools/skill-index.py（消除人讀文件散落硬編 skill 數的 chronic drift）+
PostToolUse 自動同步 + SessionStart --check 防呆。控管規則見 atom
`skill-計數單一來源-skill-index`（local/MemDev）。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent  # tools/verify/ → tools/
_spec = importlib.util.spec_from_file_location(
    "skill_index", TOOLS_DIR / "skill-index.py")
si = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(si)


def _mk_skill(skills_dir: Path, name: str, desc: str = "d") -> None:
    d = skills_dir / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n# {name}\n", encoding="utf-8")


@pytest.fixture
def env(tmp_path):
    """tmp claude_dir + skills/ 含 3 個假 skill。"""
    skills = tmp_path / "skills"
    skills.mkdir()
    for n in ("alpha", "beta", "gamma"):
        _mk_skill(skills, n)
    return tmp_path, skills


# ─── scan / frontmatter ─────────────────────────────────────────────

def test_scan_counts_and_frontmatter(env):
    _, skills = env
    sk = si.scan_skills(skills)
    assert len(sk) == 3
    assert {s["name"] for s in sk} == {"alpha", "beta", "gamma"}
    assert all(s["description"] == "d" for s in sk)


def test_scan_falls_back_to_dirname(env):
    _, skills = env
    d = skills / "noname"
    d.mkdir()
    (d / "SKILL.md").write_text("# heading only, no frontmatter\n", encoding="utf-8")
    assert "noname" in {s["name"] for s in si.scan_skills(skills)}


def test_index_json_root_file_excluded(env):
    _, skills = env
    (skills / "_skill_index.json").write_text("{}", encoding="utf-8")  # 非 */SKILL.md
    assert len(si.scan_skills(skills)) == 3


def test_build_index_count(env):
    _, skills = env
    idx = si.build_index(si.scan_skills(skills))
    assert idx["count"] == 3
    assert len(idx["skills"]) == 3


# ─── check / write ──────────────────────────────────────────────────

def test_write_creates_json_and_rewrites_marker(env):
    claude, skills = env
    (claude / "TECH.md").write_text(
        "skills X <!-- skill-count -->99<!-- /skill-count --> 個\n", encoding="utf-8")
    n, changed = si.write(skills_dir=skills, claude_dir=claude)
    assert n == 3
    idx = json.loads((skills / "_skill_index.json").read_text(encoding="utf-8"))
    assert idx["count"] == 3
    txt = (claude / "TECH.md").read_text(encoding="utf-8")
    assert "<!-- skill-count -->3<!-- /skill-count -->" in txt
    assert "99" not in txt


def test_check_detects_and_clears_drift(env):
    claude, skills = env
    (claude / "TECH.md").write_text(
        "<!-- skill-count -->99<!-- /skill-count -->\n", encoding="utf-8")
    ok, problems = si.check(skills_dir=skills, claude_dir=claude)
    assert not ok and problems  # json 缺 + marker 99≠3
    si.write(skills_dir=skills, claude_dir=claude)
    ok2, problems2 = si.check(skills_dir=skills, claude_dir=claude)
    assert ok2 and not problems2


def test_write_idempotent(env):
    claude, skills = env
    (claude / "TECH.md").write_text(
        "<!-- skill-count -->3<!-- /skill-count -->\n", encoding="utf-8")
    si.write(skills_dir=skills, claude_dir=claude)          # 首跑：建 json
    n, changed = si.write(skills_dir=skills, claude_dir=claude)  # 二跑：應零變更
    assert n == 3 and changed == []


# ─── 真庫防護 ────────────────────────────────────────────────────────

def test_real_repo_in_sync():
    """當前 repo：_skill_index.json + 文件 marker 與實檔 skill 數一致（防 commit 進 drift）。"""
    ok, problems = si.check()
    assert ok, f"skill 計數 drift（跑 python tools/skill-index.py --write）：{problems}"
