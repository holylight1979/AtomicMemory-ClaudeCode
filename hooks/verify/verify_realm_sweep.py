"""verify_realm_sweep.py — SessionEnd realm auto-migrate sweep（Phase D）決策分支守門。

不打真 LLM / 不動真磁碟索引：monkeypatch wg_atoms 模組層的 classify_realm /
_load_tool_module / load_atom_index_json 等，驗 Fail-safe 表每條路徑。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402


class _FakeSetRealm:
    """假 atom-set-realm 模組：記錄被搬的 (slug, domain)。"""
    def __init__(self):
        self.calls = []

    def set_realm(self, name, domain=None, **kw):
        self.calls.append((name, domain))
        return {"ok": True, "from": f"memory/{name}.md",
                "to": f"_AIDocs/_atoms/{domain}/{name}.md"}


class _FakeLLM:
    """假 LLM 模組：依 slug 回固定判定。"""
    def __init__(self, table):
        self.table = table
        self.calls = []

    def llm_classify_realm(self, name, triggers, excerpt, existing_paths, config):
        self.calls.append(name)
        return self.table.get(name, {"realm": "unsure", "domain_path": None,
                                     "confidence": 0.0, "terms": [], "reason": "x"})


def _drive(monkeypatch, tmp_path, *, atoms, classify, llm_table=None,
           llm_enabled=True, max_llm=5, min_conf=0.7):
    """裝配 monkeypatch 並跑 sweep；回 (moved, fake_set, fake_llm, learned_captured)。"""
    fake_set = _FakeSetRealm()
    fake_llm = _FakeLLM(llm_table or {})

    def _load(filename, mod_name):
        return fake_set if "set-realm" in filename else (fake_llm if llm_enabled else None)

    learned_captured = {}
    monkeypatch.setattr(wg_atoms, "load_atom_index_json", lambda _d: {"atoms": atoms})
    monkeypatch.setattr(wg_atoms, "classify_realm",
                        lambda name, trig, extra_lexicon=None: classify[name])
    monkeypatch.setattr(wg_atoms, "is_local_realm_path",
                        lambda p: p.startswith("_AIDocs/_atoms/"))
    monkeypatch.setattr(wg_atoms, "_load_tool_module", _load)
    monkeypatch.setattr(wg_atoms, "_read_atom_excerpt", lambda p, limit=800: "excerpt")
    monkeypatch.setattr(wg_atoms, "enumerate_local_paths", lambda _d: ["Tools"])
    monkeypatch.setattr(wg_atoms, "load_learned_lexicon", lambda: {})
    monkeypatch.setattr(wg_atoms, "append_learned_terms",
                        lambda terms: learned_captured.update(terms))
    monkeypatch.setattr(wg_atoms, "_scan_doc_refs", lambda moved: {})
    monkeypatch.setattr(wg_atoms, "_trigger_sync_memory_index", lambda: None)
    monkeypatch.setattr(wg_atoms, "REALM_AUTOMOVE_MARKER", tmp_path / "marker.json")
    monkeypatch.setattr(wg_atoms, "MEMORY_DIR", tmp_path)

    cfg = {"realm": {"auto_migrate": True, "llm_fallback": {
        "enabled": llm_enabled, "max_per_session": max_llm, "min_confidence": min_conf}}}
    moved = wg_atoms._sweep_realm_auto_migrate(cfg)
    return moved, fake_set, fake_llm, learned_captured


def _atom(name, path="memory/x.md"):
    return {"name": name, "path": path.replace("x.md", f"{name}.md"), "triggers": []}


def test_lexicon_hit_moves_via_lex(monkeypatch, tmp_path):
    moved, fs, fl, _ = _drive(
        monkeypatch, tmp_path,
        atoms=[_atom("gdoc-harvester")],
        classify={"gdoc-harvester": {"realm": "local", "domain": "Tools", "protected": False}},
    )
    assert [m["slug"] for m in moved] == ["gdoc-harvester"]
    assert moved[0]["via"] == "lex" and fs.calls == [("gdoc-harvester", "Tools")]
    assert fl.calls == []  # 詞庫命中 → 不喚 LLM


def test_protected_never_calls_llm_never_moves(monkeypatch, tmp_path):
    moved, fs, fl, _ = _drive(
        monkeypatch, tmp_path,
        atoms=[_atom("feedback-x")],
        classify={"feedback-x": {"realm": "core", "domain": None, "protected": True}},
        llm_table={"feedback-x": {"realm": "local", "domain_path": "Tools", "confidence": 0.99}},
    )
    assert moved == [] and fs.calls == [] and fl.calls == []  # 硬擋先於 LLM


def test_llm_error_defers_no_move(monkeypatch, tmp_path):
    moved, fs, fl, _ = _drive(
        monkeypatch, tmp_path,
        atoms=[_atom("mystery")],
        classify={"mystery": {"realm": "core", "domain": None, "protected": False}},
        llm_table={"mystery": {"realm": "error", "domain_path": None, "confidence": 0.0}},
    )
    assert moved == [] and fs.calls == []        # 基礎設施失敗 → defer 留原地
    assert fl.calls == ["mystery"]


def test_llm_core_keeps(monkeypatch, tmp_path):
    moved, fs, _, _ = _drive(
        monkeypatch, tmp_path,
        atoms=[_atom("mechanism-doc")],
        classify={"mechanism-doc": {"realm": "core", "domain": None, "protected": False}},
        llm_table={"mechanism-doc": {"realm": "core", "domain_path": None, "confidence": 0.9}},
    )
    assert moved == [] and fs.calls == []


def test_llm_local_high_conf_moves_and_learns(monkeypatch, tmp_path):
    moved, fs, _, learned = _drive(
        monkeypatch, tmp_path,
        atoms=[_atom("wsl2-rescue")],
        classify={"wsl2-rescue": {"realm": "core", "domain": None, "protected": False}},
        llm_table={"wsl2-rescue": {"realm": "local", "domain_path": "OS/Windows/WSL",
                                   "confidence": 0.9, "terms": ["wsl2", "vhdx"]}},
    )
    assert [m["slug"] for m in moved] == ["wsl2-rescue"]
    assert moved[0]["via"] == "LLM" and fs.calls == [("wsl2-rescue", "OS/Windows/WSL")]
    assert learned == {"wsl2": "OS/Windows/WSL", "vhdx": "OS/Windows/WSL"}  # 學詞回寫


def test_llm_unsure_goes_to_else(monkeypatch, tmp_path):
    moved, fs, _, _ = _drive(
        monkeypatch, tmp_path,
        atoms=[_atom("vague")],
        classify={"vague": {"realm": "core", "domain": None, "protected": False}},
        llm_table={"vague": {"realm": "unsure", "domain_path": None, "confidence": 0.0}},
    )
    assert moved[0]["via"] == "Else" and fs.calls == [("vague", "Else")]


def test_llm_low_conf_local_goes_to_else(monkeypatch, tmp_path):
    moved, fs, _, _ = _drive(
        monkeypatch, tmp_path,
        atoms=[_atom("weak")],
        classify={"weak": {"realm": "core", "domain": None, "protected": False}},
        llm_table={"weak": {"realm": "local", "domain_path": "OS/X", "confidence": 0.3}},
        min_conf=0.7,
    )
    assert moved[0]["via"] == "Else" and fs.calls == [("weak", "Else")]  # 低信心→Else


def test_max_per_session_caps_llm_calls(monkeypatch, tmp_path):
    atoms = [_atom(f"u{i}") for i in range(4)]
    classify = {f"u{i}": {"realm": "core", "domain": None, "protected": False} for i in range(4)}
    llm_table = {f"u{i}": {"realm": "core", "domain_path": None, "confidence": 0.9} for i in range(4)}
    _, _, fl, _ = _drive(monkeypatch, tmp_path, atoms=atoms, classify=classify,
                         llm_table=llm_table, max_llm=2)
    assert len(fl.calls) == 2  # 額度上限


def test_llm_disabled_keeps_unknown_core(monkeypatch, tmp_path):
    moved, fs, fl, _ = _drive(
        monkeypatch, tmp_path,
        atoms=[_atom("mystery")],
        classify={"mystery": {"realm": "core", "domain": None, "protected": False}},
        llm_enabled=False,
    )
    assert moved == [] and fs.calls == []  # LLM 關 → unknown core 留原地


def test_already_local_skipped(monkeypatch, tmp_path):
    moved, fs, fl, _ = _drive(
        monkeypatch, tmp_path,
        atoms=[{"name": "brain-x", "path": "_AIDocs/_atoms/World/brain-x.md", "triggers": []}],
        classify={"brain-x": {"realm": "local", "domain": "World", "protected": False}},
    )
    assert moved == [] and fs.calls == [] and fl.calls == []  # idempotent
