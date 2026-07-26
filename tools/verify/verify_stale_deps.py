"""verify_stale_deps.py — 壞滅緣（validity conditions）檢查守門.

守住規則：
1. atom-health-check.check_stale_deps：path 型 Depends 指向不存在路徑 → 觸發；
   存在路徑 / free 型條目 / 無 Depends 欄 → 靜默（向後相容鐵則）。
2. memory-audit.check_stale_deps：同上；validate_format 對 Depends/Evidence
   格式錯誤只給 warning 級 Issue，缺欄零新增 Issue。
3. 報告層：memory-audit markdown 報告「壞滅緣」節有觸發才出現。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude/
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))
TOOLS_DIR = CLAUDE_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HC = _load("atom_health_check", "atom-health-check.py")
MA = _load("memory_audit", "memory-audit.py")


ATOM_TMPL = (
    "# {name}\n\n"
    "- Scope: global\n"
    "- Confidence: [觀]\n"
    "- Trigger: alpha, beta, gamma\n"
    "{extra}"
    "\n## 知識\n\n- 測試知識點內容\n\n"
    "## 行動\n\n- 測試行動\n"
)


def _write_atom(tmp_path: Path, name: str, extra: str = "") -> Path:
    p = tmp_path / f"{name}.md"
    p.write_text(ATOM_TMPL.format(name=name, extra=extra), encoding="utf-8")
    return p


# ─── atom-health-check.check_stale_deps ──────────────────────────────────────


def test_hc_missing_path_dep_triggers(tmp_path):
    missing = tmp_path / "gone" / "x.md"
    atom = _write_atom(tmp_path, "a", f"- Depends: path:{missing}\n")
    issues = HC.check_stale_deps({"a": atom})
    assert len(issues) == 1
    assert issues[0]["atom"] == "a"
    assert issues[0]["dep"] == str(missing)


def test_hc_existing_path_dep_silent(tmp_path):
    exists = tmp_path / "exists.md"
    exists.write_text("x", encoding="utf-8")
    atom = _write_atom(tmp_path, "a", f"- Depends: path:{exists}\n")
    assert HC.check_stale_deps({"a": atom}) == []


def test_hc_free_text_dep_never_triggers(tmp_path):
    atom = _write_atom(tmp_path, "a", "- Depends: decision:xxx, hooks v2 行為\n")
    assert HC.check_stale_deps({"a": atom}) == []


def test_hc_no_depends_field_silent(tmp_path):
    """向後相容鐵則：既有 atom（無 Depends 欄）一顆都不得觸發。"""
    atom = _write_atom(tmp_path, "a")
    assert HC.check_stale_deps({"a": atom}) == []


def test_hc_mixed_deps_only_missing_flagged(tmp_path):
    exists = tmp_path / "keep.md"
    exists.write_text("x", encoding="utf-8")
    missing = tmp_path / "gone.md"
    atom = _write_atom(
        tmp_path, "a",
        f"- Depends: path:{exists}, path:{missing}, decision:xxx\n",
    )
    issues = HC.check_stale_deps({"a": atom})
    assert [i["dep"] for i in issues] == [str(missing)]


def test_hc_full_report_contains_stale_deps_key(tmp_path, monkeypatch):
    monkeypatch.setattr(HC, "MEMORY_ROOT", tmp_path)  # per-atom rel-path 需以掃描根為基準
    atom = _write_atom(tmp_path, "a", f"- Depends: path:{tmp_path / 'gone.md'}\n")
    report = HC.full_report({"a": atom})
    assert len(report["stale_deps"]) == 1
    single = HC.single_atom_report("a", {"a": atom})
    assert len(single["stale_deps"]) == 1


# ─── memory-audit：check_stale_deps + validate_format warnings ──────────────


def test_ma_missing_path_dep_triggers(tmp_path):
    missing = tmp_path / "gone.md"
    p = _write_atom(tmp_path, "a", f"- Depends: path:{missing}\n")
    atom = MA.parse_atom_file(p, "global")
    out = MA.check_stale_deps(atom)
    assert len(out) == 1 and out[0]["dep"] == str(missing)


def test_ma_no_depends_silent_and_no_new_issues(tmp_path):
    """缺兩新欄的既有 atom：零壞滅緣、validate_format 零新增 Issue。"""
    p = _write_atom(tmp_path, "a")
    atom = MA.parse_atom_file(p, "global")
    assert MA.check_stale_deps(atom) == []
    msgs = [i.message for i in MA.validate_format(atom)]
    assert not any("Depends" in m or "Evidence" in m for m in msgs)


def test_ma_validate_format_warns_on_bad_evidence_and_empty_path(tmp_path):
    p = _write_atom(tmp_path, "a", "- Depends: path:\n- Evidence: 很確定\n")
    atom = MA.parse_atom_file(p, "global")
    issues = MA.validate_format(atom)
    dep_w = [i for i in issues if "Depends" in i.message]
    ev_w = [i for i in issues if "Evidence" in i.message]
    assert len(dep_w) == 1 and dep_w[0].level == "warning"
    assert len(ev_w) == 1 and ev_w[0].level == "warning"


def test_ma_valid_evidence_no_warning(tmp_path):
    p = _write_atom(tmp_path, "a", "- Evidence: 引述\n")
    atom = MA.parse_atom_file(p, "global")
    assert not any("Evidence" in i.message for i in MA.validate_format(atom))


def test_ma_markdown_report_section_only_when_triggered():
    report = MA.HealthReport()
    md = MA.generate_markdown_report(report)
    assert "壞滅緣" not in md
    report.stale_deps.append({"file": "memory/a.md", "dep": "memory/gone.md",
                              "resolved": "X"})
    md = MA.generate_markdown_report(report)
    assert "## 壞滅緣（Stale Depends）" in md
    assert "壞滅緣觸發：atom memory/a.md 依賴 memory/gone.md 已不存在" in md
