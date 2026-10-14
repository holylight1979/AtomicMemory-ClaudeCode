"""verify_language_view.py — 依程式語言篩選的跨範疇視圖（memory/_by_language/_INDEX.md）

做什麼：驗 sync-memory-index 的語言視圖。詞的比對邊界、範疇資料夾綁定、一卡多語言、
沒有詞庫就不產檔也不放指標、--check 抓得到視圖漂移、--write 的落地與清除、
多機合併驅動對這份檔兩側各加一列不衝突。
怎麼跑：python -m pytest -q tools/verify/verify_language_view.py
（--write 不在子行程實跑：會寫 live 稽核紀錄並觸發原生記憶橋接；落地邏輯改測 sync_language_view_file。）
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude/
SCRIPT = CLAUDE_DIR / "tools" / "sync-memory-index.py"
SPEC = importlib.util.spec_from_file_location("sync_memory_index_lang", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

MERGE_SPEC = importlib.util.spec_from_file_location("merge_atom_index_lang", CLAUDE_DIR / "tools" / "merge-atom-index.py")
MERGE = importlib.util.module_from_spec(MERGE_SPEC)
MERGE_SPEC.loader.exec_module(MERGE)

LANGUAGES = {
    "_doc": "測試用詞庫",
    "Python": {"terms": ["python*", "pytest*", "pip"]},
    "C#／.NET": {"dirs": ["dotnet"], "terms": ["c#", ".net"]},
    "JavaScript／Node": {"terms": ["js", "node.js"]},
    "Bash／Shell": {"terms": ["git bash", "heredoc"]},
}

# (name, rel_path, triggers)
ATOMS = [
    ("utf8-subprocess", "memory/OS-Windows/utf8-subprocess.md", ["PYTHONUTF8", "子行程"]),
    ("pipeline-order", "memory/工作流/pipeline-order.md", ["pipeline", "json 檔"]),
    ("winforms-focus", "memory/dotnet/WinForms/winforms-focus.md", ["焦點"]),
    ("mcp-server-js", "memory/設計通則/mcp-server-js.md", ["server.js", "pytest 收案"]),
    ("hook走git-bash", "memory/CC與原子記憶契約/hook走git-bash.md", ["statusline"]),
    ("用c#寫工具", "memory/設計通則/用c#寫工具.md", ["工具"]),
    ("json-only", "memory/文字與格式/json-only.md", ["jsonl", "JSONPath"]),
]


def _build(tmp_path: Path, languages=LANGUAGES) -> Path:
    mem = tmp_path / "memory"
    (mem / "_meta").mkdir(parents=True)
    for name, rel, _t in ATOMS:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {name}\n\n- Confidence: [臨]\n", encoding="utf-8")
    index = {"version": "1.0", "atoms": [
        {"name": n, "path": rel, "triggers": t, "scope": "global"} for n, rel, t in ATOMS]}
    (mem / "_atom_index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    tax = {"core": {"X": {}}}
    if languages is not None:
        tax["languages"] = languages
    (mem / "_meta" / "taxonomy.json").write_text(json.dumps(tax, ensure_ascii=False), encoding="utf-8")
    return mem


def _groups(mem: Path) -> dict:
    rows = MOD.parse_atom_index(mem)
    cat, _ = MOD._core_category_atoms(rows, mem.parent, {})
    return MOD.collect_language_view(cat, MOD.load_language_rules(mem), MOD._triggers_by_path(mem))


def _names(groups: dict, lang: str) -> set:
    return {Path(p).stem for p, _c in groups.get(lang, [])}


def test_term_boundaries_prefix_and_whole_word(tmp_path):
    g = _groups(_build(tmp_path))
    # python* 是前綴：PYTHONUTF8 命中；pip 整詞：pipeline 不命中；js 整詞：json／jsonl 不命中、server.js 命中
    assert _names(g, "Python") == {"utf8-subprocess", "mcp-server-js"}
    assert "pipeline-order" not in _names(g, "Python")
    assert _names(g, "JavaScript／Node") == {"mcp-server-js"}
    assert "json-only" not in {n for lang in g for n in _names(g, lang)}


def test_dir_binding_cjk_boundary_and_hyphen_as_space(tmp_path):
    g = _groups(_build(tmp_path))
    # dotnet 資料夾綁 C#（卡名與 Trigger 都沒有 C# 詞）；「用c#寫工具」中文緊貼也算邊界
    assert _names(g, "C#／.NET") == {"winforms-focus", "用c#寫工具"}
    # 卡名的 - 視為空白：git-bash 命中 "git bash"
    assert _names(g, "Bash／Shell") == {"hook走git-bash"}


def test_one_atom_in_several_languages_and_view_lists_paths(tmp_path):
    mem = _build(tmp_path)
    g = _groups(mem)
    assert "mcp-server-js" in _names(g, "Python") and "mcp-server-js" in _names(g, "JavaScript／Node")
    view = MOD.render_language_view(g)
    assert "`memory/設計通則/mcp-server-js.md`" in view
    assert view.count("| Python | 說明 |") == 1 and view.count("| JavaScript／Node | 說明 |") == 1
    assert "| Python | 2 |" in view


def test_no_rules_no_view_no_pointer(tmp_path):
    mem = _build(tmp_path, languages=None)
    assert MOD.load_language_rules(mem) == []
    assert MOD.render_language_view({}) == ""
    rows = MOD.parse_atom_index(mem)
    plain = MOD.render_core_section(rows, mem.parent, {}, hierarchical=True)
    assert MOD.LANGUAGE_VIEW_POINTER not in plain
    with_ptr = MOD.render_core_section(rows, mem.parent, {}, hierarchical=True, language_view=True)
    assert with_ptr == plain + "\n\n" + MOD.LANGUAGE_VIEW_POINTER


def test_broken_languages_section_warns_and_skips(tmp_path, capsys):
    mem = _build(tmp_path, languages=["not", "a", "dict"])
    assert MOD.load_language_rules(mem) == []
    assert "languages 段讀不到" in capsys.readouterr().err


def _prerender(mem: Path) -> None:
    root = mem.parent
    rows = MOD.parse_atom_index(mem)
    view = MOD.render_language_view(_groups(mem))
    (mem / "MEMORY.md").write_text(
        MOD.render_core_section(rows, root, {}, hierarchical=True, language_view=bool(view)) + "\n", encoding="utf-8")
    for abs_path, content in MOD.collect_per_level_files(rows, root, {}, hierarchical=True).items():
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content + "\n", encoding="utf-8")
    if view:
        (mem / "_by_language").mkdir(exist_ok=True)
        (mem / "_by_language" / "_INDEX.md").write_text(view + "\n", encoding="utf-8")


def _check(mem: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--hierarchical", "--memory-dir", str(mem)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    )


def test_check_roundtrip_and_detects_view_drift(tmp_path):
    mem = _build(tmp_path)
    _prerender(mem)
    r = _check(mem)
    assert r.returncode == 0, r.stderr
    (mem / "_by_language" / "_INDEX.md").unlink()
    r = _check(mem)
    assert r.returncode == 1 and "語言視圖 drift" in r.stderr, r.stderr


def test_write_lands_and_empty_view_cleans_up(tmp_path, monkeypatch):
    class _Ok:
        ok, error = True, None

    def fake_write(path, content, *, source):
        Path(path).write_text(content, encoding="utf-8")
        return _Ok()

    monkeypatch.setattr(MOD, "write_index_full", fake_write)
    lang_path = tmp_path / "memory" / "_by_language" / "_INDEX.md"
    assert MOD.sync_language_view_file(lang_path, "# view") is None
    assert lang_path.read_text(encoding="utf-8") == "# view\n"
    assert MOD.sync_language_view_file(lang_path, "") is None
    assert not lang_path.exists() and not lang_path.parent.exists()
    assert MOD.sync_language_view_file(lang_path, "") is None   # 已經不在也不算錯


def test_merge_driver_both_sides_add_rows_no_conflict(tmp_path):
    mem = _build(tmp_path)
    g = _groups(mem)
    base = MOD.render_language_view(g)
    ours_g = {**g, "Python": sorted(g["Python"] + [("memory/A/ours-py.md", "ours")])}
    theirs_g = {**g, "Python": sorted(g["Python"] + [("memory/B/theirs-py.md", "theirs")])}
    merged, conflicts, _msg = MERGE.merge_table_doc(
        base, MOD.render_language_view(ours_g), MOD.render_language_view(theirs_g))
    assert conflicts == 0, merged
    assert "`memory/A/ours-py.md`" in merged and "`memory/B/theirs-py.md`" in merged
    assert "| Python | 4 |" in merged          # 計數表 o+t−b：3+3−2＝4
    assert "<<<<<<<" not in merged
