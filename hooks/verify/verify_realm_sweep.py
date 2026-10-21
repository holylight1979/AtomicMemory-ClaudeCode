"""verify_realm_sweep.py — SessionEnd realm auto-migrate sweep（Phase D）決策分支守門。

不打真 LLM / 不動真磁碟索引：monkeypatch wg_atoms 模組層的 classify_realm /
_load_tool_module / load_atom_index_json 等，驗 Fail-safe 表每條路徑。
"""

from __future__ import annotations

import json
import os
import subprocess
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
    monkeypatch.setattr(wg_atoms, "CLAUDE_DIR", tmp_path)  # Entry 判定讀檔頭的根：指 tmp，不讀資料根

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


E16_CARD = "第二意見分歧裁決-codex的block"
LEX_TOOLS = {"realm": "local", "domain": "Tools", "matched": ["codex"], "protected": False}


def _holds(monkeypatch, tmp_path):
    """稽核帳改指 tmp（不碰資料根的 atom_io_audit.jsonl）；回讀 realm_hold 行的函式。"""
    import lib.atom_io as atom_io
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(atom_io, "AUDIT_LOG", audit)

    def read():
        if not audit.exists():
            return []
        rows = [json.loads(ln) for ln in audit.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return [r for r in rows if r.get("op") == "realm_hold"]
    return read


def test_entry_bound_card_stays_core_and_is_ledgered(monkeypatch, tmp_path):
    holds = _holds(monkeypatch, tmp_path)
    # 前置：同一張卡不綁 Entry 時詞庫判 local 照搬（證明下面的「不搬」是規則擋的，不是本來就不會搬）
    moved, fs, _, _ = _drive(monkeypatch, tmp_path, atoms=[_atom(E16_CARD)],
                             classify={E16_CARD: LEX_TOOLS})
    assert fs.calls == [(E16_CARD, "Tools")] and moved[0]["via"] == "lex"
    assert holds() == []

    bound = {**_atom(E16_CARD), "entry": ["E16"]}
    moved, fs, fl, _ = _drive(monkeypatch, tmp_path, atoms=[bound], classify={E16_CARD: LEX_TOOLS})
    assert moved == [] and fs.calls == [] and fl.calls == []
    assert [(h["rule"], h["slug"], h["entry"], h["would"]) for h in holds()] == [
        ("ENTRY_BOUND_STAYS_CORE", E16_CARD, ["E16"], "lex:Tools")]


def test_entry_header_is_truth_over_index(monkeypatch, tmp_path):
    """檔頭是真相：索引沒 entry、檔頭有 `- Entry:` → 照擋；索引殘留 entry、檔頭已拿掉 → 照原判法搬。"""
    holds = _holds(monkeypatch, tmp_path)
    md = tmp_path / "memory" / f"{E16_CARD}.md"
    md.parent.mkdir(parents=True)
    md.write_text(f"# {E16_CARD}\n\n- Scope: global\n- Entry: E16\n\n## 知識\n\n- x\n", encoding="utf-8")
    moved, fs, _, _ = _drive(monkeypatch, tmp_path, atoms=[_atom(E16_CARD)],
                             classify={E16_CARD: LEX_TOOLS})
    assert moved == [] and fs.calls == []
    assert [(h["slug"], h["entry"]) for h in holds()] == [(E16_CARD, ["E16"])]

    md.write_text(f"# {E16_CARD}\n\n- Scope: global\n\n## 知識\n\n- Entry: E99 寫在知識段不算\n", encoding="utf-8")
    moved, fs, _, _ = _drive(monkeypatch, tmp_path, atoms=[{**_atom(E16_CARD), "entry": ["E16"]}],
                             classify={E16_CARD: LEX_TOOLS})
    assert fs.calls == [(E16_CARD, "Tools")] and len(holds()) == 1


def test_entry_bound_card_never_calls_llm(monkeypatch, tmp_path):
    holds = _holds(monkeypatch, tmp_path)
    miss = {"realm": "core", "domain": None, "protected": False}
    llm_local = {"bound-x": {"realm": "local", "domain_path": "Tools", "confidence": 0.99, "terms": ["t"]}}
    # 前置：同一張卡不綁 Entry 時會喚 LLM 並搬（證明下面的「不喚」是規則擋的）
    moved, fs, fl, _ = _drive(monkeypatch, tmp_path, atoms=[_atom("bound-x")],
                              classify={"bound-x": miss}, llm_table=llm_local)
    assert fl.calls == ["bound-x"] and fs.calls == [("bound-x", "Tools")]

    moved, fs, fl, learned = _drive(monkeypatch, tmp_path,
                                    atoms=[{**_atom("bound-x"), "entry": ["E04"]}],
                                    classify={"bound-x": miss}, llm_table=llm_local)
    assert moved == [] and fs.calls == [] and fl.calls == [] and learned == {}
    assert [(h["slug"], h["would"]) for h in holds()] == [("bound-x", "LLM")]
    # 本來就不會搬的不留帳（帳只記規則真的擋下的）：LLM 關且詞庫沒命中、protected
    _drive(monkeypatch, tmp_path, atoms=[{**_atom("bound-y"), "entry": ["E04"]}],
           classify={"bound-y": miss}, llm_enabled=False)
    _drive(monkeypatch, tmp_path, atoms=[{**_atom("feedback-z"), "entry": ["E04"]}],
           classify={"feedback-z": {"realm": "core", "domain": None, "protected": True}}, llm_table=llm_local)
    assert [h["slug"] for h in holds()] == ["bound-x"]


def _tmp_data_root(tmp_path, cards):
    """暫存資料根（子行程用 WG_CLAUDE_DIR 指過去）：cards=[(slug, Entry 代號或 None)] → (root, env)。"""
    root = tmp_path / "claude"
    mem = root / "memory"
    mem.mkdir(parents=True)
    rows = []
    for slug, eid in cards:
        entry_line = f"- Entry: {eid}\n" if eid else ""
        (mem / f"{slug}.md").write_text(
            f"# {slug}\n\n- Scope: global\n{entry_line}\n## 知識\n\n- [臨] x\n", encoding="utf-8")
        rows.append({"name": slug, "path": f"memory/{slug}.md", "triggers": [slug], "scope": "global",
                     **({"entry": [eid]} if eid else {})})
    (mem / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": rows}), encoding="utf-8")
    return root, {**os.environ, "WG_CLAUDE_DIR": str(root), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def _run_tool(env, *args):
    r = subprocess.run([sys.executable, str(CLAUDE / "tools" / args[0]), *args[1:]],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout), r.stderr


def test_manual_move_of_entry_bound_card_warns_but_moves(tmp_path):
    """同一規則的反向出口：手動 atom-set-realm 搬綁 Entry 的卡到 local → stderr 一行警告、照搬（判斷留給人）。"""
    root, env = _tmp_data_root(tmp_path, [("bound-x", "E16"), ("plain-y", None)])
    for slug, expect_warn in (("bound-x", True), ("plain-y", False)):
        out, err = _run_tool(env, "atom-set-realm.py", "set", slug, "--domain", "Tools")
        assert out["ok"] and out["to_realm"] == "local"
        assert (root / "_AIDocs" / "_atoms" / "Tools" / f"{slug}.md").exists()
        warn = [ln for ln in err.splitlines() if "ENTRY_BOUND_STAYS_CORE" in ln]
        if expect_warn:
            assert len(warn) == 1 and "bound-x" in warn[0] and "E16" in warn[0] and "E16" in out["warning"]
        else:
            assert warn == [] and "warning" not in out  # 沒綁 Entry → 不警告
    assert (root / "memory" / "_meta" / "atom_io_audit.jsonl").exists()  # 搬移帳落在 WG_CLAUDE_DIR 的資料根


def test_categorize_apply_passes_entry_warning_through(tmp_path):
    """atom-categorize 的 local: 對映委派 set_realm：照搬，set_realm 的警告出現在 apply 結果的 warnings。"""
    root, env = _tmp_data_root(tmp_path, [("bound-x", "E16"), ("plain-y", None)])
    plan_map = tmp_path / "map.json"
    plan_map.write_text(json.dumps({"atoms": {"bound-x": "local:Tools", "plain-y": "local:Tools"}}), encoding="utf-8")
    out, _ = _run_tool(env, "atom-categorize.py", "apply", "--map", str(plan_map),
                       "--undo-file", str(tmp_path / "undo.json"))
    assert out["applied"] == 2 and out["failed"] == []
    assert len(out["warnings"]) == 1 and "ENTRY_BOUND_STAYS_CORE" in out["warnings"][0] and "bound-x" in out["warnings"][0]


def test_already_local_skipped(monkeypatch, tmp_path):
    moved, fs, fl, _ = _drive(
        monkeypatch, tmp_path,
        atoms=[{"name": "brain-x", "path": "_AIDocs/_atoms/World/brain-x.md", "triggers": []}],
        classify={"brain-x": {"realm": "local", "domain": "World", "protected": False}},
    )
    assert moved == [] and fs.calls == [] and fl.calls == []  # idempotent
