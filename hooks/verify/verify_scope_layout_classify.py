"""verify_scope_layout_classify.py — 「專案記憶已依 scope 分層整理」的判定、SessionStart 提示、整理工具。

- lib.atom_locations.scope_layout_classified：_atom_index.json.layout=="scope-v2" 或 shared/_taxonomy.json → 已整理；無索引 → 視為已整理
- session_start._scope_layout_advisory：未整理才提示一行；已整理／無專案 → []
- tools/classify-project-scope.py：plan 給 personal 存量建議＋索引計數；apply 依決定搬檔、回寫索引、打標記；mark 只打標記
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_ROOT = HOOKS_DIR.parent
for p in (HOOKS_DIR, HOOKS_DIR / "handlers", CLAUDE_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from lib.atom_index_json import load_atom_index_json, upsert_atom  # noqa: E402
from lib.atom_locations import scope_layout_classified, SCOPE_LAYOUT_MARK  # noqa: E402


def _mk_project(tmp_path: Path, *, personal=True) -> Path:
    root = tmp_path / "proj" / ".claude"
    mem = root / "memory"
    (mem / "shared").mkdir(parents=True)
    (mem / "shared" / "s.md").write_text("# s\n\n- Scope: shared\n- Trigger: a\n\n## 知識\n\n- [臨] x\n", encoding="utf-8")
    (mem / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": []}), encoding="utf-8")
    upsert_atom(mem, "s", "memory/shared/s.md", ["a"], scope="shared")
    if personal:
        (mem / "personal" / "holylight").mkdir(parents=True)
        (mem / "personal" / "holylight" / "rule.md").write_text(
            "# rule\n\n- Scope: personal:holylight\n- Author: auto-extracted-v4.1\n- Trigger: svn\n\n## 知識\n\n"
            "- [臨] 此專案上 SVN 前必須再次向使用者確認\n", encoding="utf-8")
        upsert_atom(mem, "rule", "memory/personal/holylight/rule.md", ["svn"], scope="global")  # 錯標
        (mem / "personal" / "holylight" / "pref.md").write_text(
            "# pref\n\n- Scope: personal:holylight\n- Author: holylight\n- Trigger: 白話\n\n## 知識\n\n"
            "- [臨] 要求 AI 助手以白話條列方式溝通\n", encoding="utf-8")
        upsert_atom(mem, "pref", "memory/personal/holylight/pref.md", ["白話"], scope="personal:holylight")
    return mem


def _load_tool():
    path = CLAUDE_ROOT / "tools" / "classify-project-scope.py"
    spec = importlib.util.spec_from_file_location("classify_project_scope_ut", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_classified_detection(tmp_path):
    mem = _mk_project(tmp_path, personal=False)
    assert scope_layout_classified(mem) is None
    (mem / "shared" / "_taxonomy.json").write_text("{}", encoding="utf-8")
    assert scope_layout_classified(mem) == "taxonomy"
    (mem / "shared" / "_taxonomy.json").unlink()
    data = load_atom_index_json(mem)
    data["layout"] = SCOPE_LAYOUT_MARK
    (mem / "_atom_index.json").write_text(json.dumps(data), encoding="utf-8")
    assert scope_layout_classified(mem) == "marker"
    # 標記在 upsert 後仍在（save 保留頂層鍵）
    upsert_atom(mem, "t", "memory/shared/t.md", ["a"], scope="shared")
    assert scope_layout_classified(mem) == "marker"
    # 無索引 → 沒東西可整理
    assert scope_layout_classified(tmp_path / "nothing") == "marker"


def test_session_start_advisory_only_when_unclassified(tmp_path):
    from handlers.session_start import _scope_layout_advisory
    mem = _mk_project(tmp_path)
    out = _scope_layout_advisory(mem)
    assert len(out) == 1 and out[0].startswith("[Guardian:ScopeLayout]")
    assert "/memory classify" in out[0]
    (mem / "shared" / "_taxonomy.json").write_text("{}", encoding="utf-8")
    assert _scope_layout_advisory(mem) == []
    assert _scope_layout_advisory(None) == []
    assert _scope_layout_advisory(tmp_path / "missing") == []


def test_plan_suggests_and_counts(tmp_path, monkeypatch):
    tool = _load_tool()
    mem = _mk_project(tmp_path)
    monkeypatch.setenv("CLAUDE_USER", "holylight")
    plan = tool.build_plan(mem)
    by = {p["slug"]: p for p in plan["personal"]}
    assert by["rule"]["suggest"] == "shared" and by["rule"]["mine"] is True
    assert by["pref"]["suggest"] == "personal"
    assert plan["index"]["scope_mismatch"] == 1  # rule 錯標 global
    assert plan["shared_flat"] == 1 and plan["classified"] is None


def test_apply_moves_and_marks(tmp_path, monkeypatch):
    tool = _load_tool()
    mem = _mk_project(tmp_path)
    monkeypatch.setenv("CLAUDE_USER", "holylight")
    # 不觸發真的目錄重生子程序
    monkeypatch.setattr(tool, "_load_module", _patched_loader(tool))
    dec = tmp_path / "dec.json"
    dec.write_text(json.dumps({"rule": "shared", "pref": "personal"}), encoding="utf-8")
    rc = tool.cmd_apply(mem, dec, dry_run=False)
    assert rc == 0
    entries = {a["name"]: a for a in load_atom_index_json(mem)["atoms"]}
    assert entries["rule"]["path"] == "memory/shared/rule.md" and entries["rule"]["scope"] == "shared"
    assert entries["pref"]["scope"] == "personal:holylight"
    text = (mem / "shared" / "rule.md").read_text(encoding="utf-8")
    assert "- Scope: shared" in text and "- Author: holylight" in text
    assert scope_layout_classified(mem) == "marker"


def _patched_loader(tool):
    real = tool._load_module

    def loader(name, path):
        mod = real(name, path)
        if name.startswith("atom_move"):
            mod.catalog_sync = lambda index_dir: {"ok": True, "skipped": "test"}
        return mod
    return loader
