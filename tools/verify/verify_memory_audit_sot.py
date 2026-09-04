"""verify_memory_audit_sot.py — memory-audit delete/restore/move 的 SoT 與 sidecar 守門.

守住規則：
1. move_to_distant：.md 與 .access.json sidecar 原子同搬（lib.atom_access.move_atom_pair）。
2. delete_atom：_atom_index.json（唯一機器源）同步移除條目（含 mirror regen）。
3. restore_from_distant：拉回後 upsert 回 _atom_index.json、Confidence 重置 [臨]、
   _distant 側殘留 sidecar 清除。

全程 tmp 樹隔離；LanceDB / vector service / audit log 皆以 monkeypatch 斷開。
"""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude/
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

SPEC = importlib.util.spec_from_file_location(
    "memory_audit", CLAUDE_DIR / "tools" / "memory-audit.py"
)
MA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MA)


@pytest.fixture(autouse=True)
def _silence_funnel_audit(monkeypatch):
    """避免單元測試往現役 atom_io_audit.jsonl 落檔（沿 lib/verify 慣例）。"""
    import lib.atom_access as AAC
    import lib.atom_io as AIO
    monkeypatch.setattr(AIO, "_audit_log", lambda *a, **k: None)
    monkeypatch.setattr(AAC, "_audit_log", lambda *a, **k: None)

ATOM_BODY = (
    "# {name}\n\n"
    "- Scope: global\n"
    "- Confidence: [觀]\n"
    "- Trigger: alpha, beta, gamma\n\n"
    "## 知識\n\n- 內容一則\n\n"
    "## 行動\n\n- 行動一則\n"
)


def _mk_atom(mem_dir: Path, name: str, *, with_sidecar: bool = True,
             indexed: bool = True) -> Path:
    mem_dir.mkdir(parents=True, exist_ok=True)
    md = mem_dir / f"{name}.md"
    md.write_text(ATOM_BODY.format(name=name), encoding="utf-8")
    if with_sidecar:
        md.with_suffix(".access.json").write_text(
            json.dumps({"schema": "atom-access-v3", "read_hits": 3,
                        "confirmations": 2, "useful_hits": 1, "used_fail": 1,
                        "last_used": "2026-07-01", "first_seen": "2026-06-01",
                        "last_promoted_at": None, "timestamps": [],
                        "confirmation_events": []}),
            encoding="utf-8")
    if indexed:
        from lib.atom_index_json import upsert_atom
        upsert_atom(mem_dir, name, f"memory/{name}.md",
                    ["alpha", "beta", "gamma"], scope="global")
    return md


# ─── 1. move_to_distant 帶 sidecar ───────────────────────────────────────────


def test_move_to_distant_moves_sidecar(tmp_path):
    mem = tmp_path / "memory"
    md = _mk_atom(mem, "foo", indexed=False)
    ok, msg = MA.move_to_distant(md)
    assert ok, msg
    dests = list((mem / "_distant").rglob("foo.md"))
    assert len(dests) == 1
    assert dests[0].with_suffix(".access.json").exists()  # sidecar 同搬
    assert not md.exists() and not md.with_suffix(".access.json").exists()


def test_move_to_distant_without_sidecar_still_ok(tmp_path):
    mem = tmp_path / "memory"
    md = _mk_atom(mem, "bare", with_sidecar=False, indexed=False)
    ok, msg = MA.move_to_distant(md)
    assert ok, msg
    assert list((mem / "_distant").rglob("bare.md"))


# ─── 2. delete_atom 同步 _atom_index.json ────────────────────────────────────


@pytest.fixture
def isolated_delete_env(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    _mk_atom(mem, "bar")
    monkeypatch.setattr(MA, "discover_layers", lambda *a, **k: [("global", mem)])
    monkeypatch.setattr(MA, "CLAUDE_DIR", tmp_path)  # _vectordb 不存在 → LanceDB skip
    monkeypatch.setattr(MA, "AUDIT_LOG_PATH", tmp_path / "audit.log")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no service")))
    return mem


def test_delete_atom_removes_index_entry(isolated_delete_env):
    mem = isolated_delete_env
    from lib.atom_index_json import load_atom_index_json
    assert any(a["name"] == "bar" for a in load_atom_index_json(mem)["atoms"])
    ok, msg = MA.delete_atom("bar", layer="global")
    assert ok, msg
    assert "_atom_index.json entry removed" in msg
    assert not any(a["name"] == "bar"
                   for a in load_atom_index_json(mem)["atoms"])
    assert not (mem / "bar.md").exists()
    assert list((mem / "_distant").rglob("bar.md"))  # 移入 _distant 而非蒸發


def test_delete_atom_dry_run_keeps_index(isolated_delete_env):
    mem = isolated_delete_env
    from lib.atom_index_json import load_atom_index_json
    ok, msg = MA.delete_atom("bar", layer="global", dry_run=True)
    assert ok
    assert any(a["name"] == "bar" for a in load_atom_index_json(mem)["atoms"])
    assert (mem / "bar.md").exists()


# ─── 3. restore_from_distant 回填 index + 清 sidecar ─────────────────────────


def test_restore_from_distant_upserts_index(tmp_path):
    mem = tmp_path / "memory"
    distant = mem / "_distant" / "2026_01"
    distant.mkdir(parents=True)
    src = distant / "baz.md"
    src.write_text(ATOM_BODY.format(name="baz"), encoding="utf-8")
    src.with_suffix(".access.json").write_text('{"schema":"atom-access-v3"}',
                                               encoding="utf-8")
    ok, msg = MA.restore_from_distant(src)
    assert ok, msg
    dest = mem / "baz.md"
    assert dest.exists()
    assert "- Confidence: [臨]" in dest.read_text(encoding="utf-8")
    assert not src.exists()
    assert not src.with_suffix(".access.json").exists()  # 殘留 sidecar 清除
    from lib.atom_index_json import load_atom_index_json
    entries = {a["name"]: a for a in load_atom_index_json(mem)["atoms"]}
    assert "baz" in entries, msg
    assert entries["baz"]["path"] == "memory/baz.md"
    assert entries["baz"]["triggers"] == ["alpha", "beta", "gamma"]


# ─── 4. parse_memory_index：範疇聚合表不產 entry ──────────────────────────────


@pytest.mark.parametrize("header", ["| Atom | atom 數 | 深入 |", "| 範疇 | atom 數 | 深入 |"])
def test_parse_memory_index_category_table_yields_no_entries(tmp_path, header):
    idx = tmp_path / "MEMORY.md"
    idx.write_text(
        "# Atom Index\n\n"
        f"{header}\n"
        "|------|------|------|\n"
        "| 版控 | 4 | `memory/版控/_INDEX.md` |\n"
        "| 設計通則 | 2 | `memory/設計通則/_INDEX.md` |\n",
        encoding="utf-8",
    )
    entries, lines = MA.parse_memory_index(idx)
    assert entries == []
    assert lines == 6


def test_parse_memory_index_flat_two_col_still_yields_entries(tmp_path):
    idx = tmp_path / "MEMORY.md"
    idx.write_text(
        "| Atom | 說明 |\n|------|------|\n| decisions | 全域決策 |\n| feedback-* | 行為校正 |\n",
        encoding="utf-8",
    )
    entries, _ = MA.parse_memory_index(idx)
    assert [e.path for e in entries] == ["decisions.md", "feedback-*.md"]


# ─── 5. validate_index：子目錄 atom 遞迴（index→file 與 file→index 雙向）──────


def test_validate_index_subdir_atoms_recursive(tmp_path):
    mem = tmp_path / "memory"
    _mk_atom(mem / "版控" / "Git", "foo", indexed=False)
    _mk_atom(mem / "設計通則", "bar", indexed=False)
    idx = mem / "MEMORY.md"
    idx.write_text("| Atom | 說明 |\n|---|---|\n", encoding="utf-8")
    entries = [MA.IndexEntry("foo", "memory/版控/Git/foo.md", "alpha")]
    issues = MA.validate_index(idx, mem, entries)
    assert not [i for i in issues if "索引指向不存在" in i.message]
    assert [i for i in issues if i.level == "warning" and "bar.md 未在索引中列出" in i.message]


# ─── 6. validate_index：layout gate（memory/ 根下散檔）─────────────────────────


def _bind_tmp_global(monkeypatch, mem: Path):
    """把 memory-audit 的全域 memory 綁到 tmp；多根掃描也收斂到 tmp 根，不碰現役 memory/。"""
    real_multi = MA.iter_atom_files_multi
    monkeypatch.setattr(MA, "GLOBAL_MEMORY_DIR", mem)
    monkeypatch.setattr(
        MA, "iter_atom_files_multi",
        lambda roots=None, **k: real_multi(roots if roots is not None else [mem], **k),
    )


@pytest.mark.parametrize("gate,expected", [(True, 1), (False, 0)])
def test_validate_index_layout_gate(tmp_path, monkeypatch, gate, expected):
    mem = tmp_path / "memory"
    _mk_atom(mem, "flat", indexed=False)
    idx = mem / "MEMORY.md"
    idx.write_text("| Atom | 說明 |\n|---|---|\n", encoding="utf-8")
    _bind_tmp_global(monkeypatch, mem)
    monkeypatch.setattr(MA, "gate_enabled", lambda: gate)
    issues = MA.validate_index(idx, mem, [MA.IndexEntry("flat", "memory/flat.md", "alpha")])
    layout = [i for i in issues if i.category == "layout"]
    assert len(layout) == expected
    if gate:
        assert layout[0].level == "error" and "memory/flat.md" in layout[0].message
    assert not [i for i in issues if i.level == "error" and i.category == "index"]


# ─── 7. run_audit：有 _atom_index.json 時 entries 來自 json，非 MEMORY.md ──────


def test_run_audit_entries_from_atom_index_json(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    _mk_atom(mem, "one")
    _mk_atom(mem, "two")
    (mem / "MEMORY.md").write_text("| Atom | 說明 |\n|---|---|\n", encoding="utf-8")
    from lib.atom_index_json import load_atom_index_json
    assert len(load_atom_index_json(mem)["atoms"]) == 2
    _bind_tmp_global(monkeypatch, mem)
    monkeypatch.setattr(MA, "discover_layers", lambda *a, **k: [("global", mem)])
    monkeypatch.setattr(MA, "CLAUDE_DIR", tmp_path)
    monkeypatch.setattr(MA, "AUDIT_LOG_PATH", tmp_path / "audit.log")
    import argparse
    report = MA.run_audit(argparse.Namespace(
        global_only=True, project=None, project_dir=None, verbose=False))
    index_issues = [i for i in report.issues if i.category == "index"]
    assert not [i for i in index_issues if i.level == "error"], index_issues
    assert not [i for i in index_issues if "未在索引中列出" in i.message], index_issues
    assert report.total_atoms == 2


# ─── 8. 專案層 MEMORY.md 行數：index 仍含平鋪 shared atom → info，遷移後 → warning ──────


def _mk_project_layer(tmp_path: Path, shared_rel: str) -> Path:
    """<tmp>/proj/.claude/memory：MEMORY.md 超過專案層上限 + 一顆 shared atom（shared_rel 決定平鋪/歸類）。"""
    mem = tmp_path / "proj" / ".claude" / "memory"
    md = mem / Path(shared_rel).relative_to("memory")
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(ATOM_BODY.format(name=md.stem).replace("Scope: global", "Scope: shared"),
                  encoding="utf-8")
    from lib.atom_spec import PROJECT_INDEX_MAX_LINES
    n_lines = PROJECT_INDEX_MAX_LINES + 20
    (mem / "MEMORY.md").write_text("# Atom Index — Project\n" + "\n".join(f"- 手寫分區規則第 {i} 行" for i in range(n_lines)) + "\n",
                                   encoding="utf-8")
    from lib.atom_index_json import upsert_atom
    upsert_atom(mem, md.stem, shared_rel, ["alpha", "beta", "gamma"], scope="shared")
    return mem


@pytest.mark.parametrize("shared_rel,expected_level", [
    ("memory/shared/flat-one.md", "info"),          # 平鋪 shared 尚在 → 過渡，只 info
    ("memory/shared/驗證與實證/cat-one.md", "warning"),  # 已歸類 → 套專案層 150 行上限
])
def test_run_audit_project_index_lines_info_until_migrated(tmp_path, monkeypatch,
                                                           shared_rel, expected_level):
    mem = _mk_project_layer(tmp_path, shared_rel)
    monkeypatch.setattr(MA, "discover_layers", lambda *a, **k: [("project", mem)])
    monkeypatch.setattr(MA, "parse_audit_log", lambda: {})
    monkeypatch.setattr(MA, "AUDIT_LOG_PATH", tmp_path / "audit.log")
    import argparse
    report = MA.run_audit(argparse.Namespace(
        global_only=False, project=None, project_dir=str(mem), verbose=False))
    size = [i for i in report.issues if i.category == "size" and "MEMORY.md" in i.message]
    assert len(size) == 1, report.issues
    assert size[0].level == expected_level, size[0]
    assert not [i for i in report.issues if i.level == "error"], report.issues


def test_has_flat_shared_entries_predicate():
    E = MA.IndexEntry
    assert MA._has_flat_shared_entries([E("a", "memory/shared/a.md", "")]) is True
    assert MA._has_flat_shared_entries([E("a", "memory/shared/版控/a.md", "")]) is False
    assert MA._has_flat_shared_entries([E("a", "memory/projects/X/a.md", "")]) is False
    assert MA._has_flat_shared_entries([]) is False


# ─── --enforce 委派 selective forget（唯一遺忘機制） ─────────────────────────────

def _mk_stale_layer(tmp_path, days_old: int, confirmations: int = 1):
    """<tmp>/memory 層：一顆歸類 atom（OS-Windows/stale-x.md）+ sidecar last_used=days_old 天前 + 索引。"""
    from datetime import timedelta
    mem = tmp_path / "memory"
    md = mem / "OS-Windows" / "stale-x.md"
    md.parent.mkdir(parents=True)
    md.write_text(ATOM_BODY.format(name="stale-x"), encoding="utf-8")
    last_used = (MA.date.today() - timedelta(days=days_old)).isoformat()
    (mem / "OS-Windows" / "stale-x.access.json").write_text(json.dumps(
        {"last_used": last_used, "confirmations": confirmations, "read_hits": 1,
         "useful_hits": 1, "used_fail": 1}), encoding="utf-8")
    from lib.atom_index_json import upsert_atom, load_atom_index_json
    upsert_atom(mem, "stale-x", "memory/OS-Windows/stale-x.md", ["alpha", "beta", "gamma"], scope="global")
    assert any(a["name"] == "stale-x" for a in load_atom_index_json(mem)["atoms"])
    return mem, md


def _enforce(mem, monkeypatch, dry_run: bool, capsys):
    import argparse
    import wg_atoms
    monkeypatch.setattr(MA, "discover_layers", lambda *a, **k: [("global", mem)])
    monkeypatch.setattr(MA, "_write_audit_entry", lambda *a, **k: None)
    monkeypatch.setattr(MA, "_forget_config",
                        lambda: {"self_iteration": {"decay_half_life_days": 30,
                                                    "archive_score_threshold": 0.3,
                                                    "forget": {"enabled": False, "dry_run": True}}})
    monkeypatch.setattr(wg_atoms, "_trigger_sync_memory_index", lambda: None)
    MA.enforce_decay(argparse.Namespace(dry_run=dry_run, global_only=True, project=None, project_dir=None))
    return capsys.readouterr().out


def test_enforce_dry_run_lists_forget_candidate_without_moving(tmp_path, monkeypatch, capsys):
    mem, md = _mk_stale_layer(tmp_path, days_old=200)
    out = _enforce(mem, monkeypatch, dry_run=True, capsys=capsys)
    assert "[DRY-RUN] Would isolate" in out and "stale-x" in out, out
    assert md.exists()


def test_enforce_isolates_into_category_distant_and_drops_index_row(tmp_path, monkeypatch, capsys):
    mem, md = _mk_stale_layer(tmp_path, days_old=200)
    out = _enforce(mem, monkeypatch, dry_run=False, capsys=capsys)
    assert "OK: 已隔離" in out, out
    assert not md.exists()
    assert (mem / "OS-Windows" / "_distant" / "stale-x.md").exists()
    assert (mem / "OS-Windows" / "_distant" / "stale-x.access.json").exists()
    from lib.atom_index_json import load_atom_index_json
    assert not any(a["name"] == "stale-x" for a in load_atom_index_json(mem)["atoms"])
    assert MA._count_distant(mem) == 1


def test_enforce_recent_atom_is_not_a_candidate(tmp_path, monkeypatch, capsys):
    mem, md = _mk_stale_layer(tmp_path, days_old=3, confirmations=5)
    out = _enforce(mem, monkeypatch, dry_run=False, capsys=capsys)
    assert "No archive candidates" in out, out
    assert md.exists()
