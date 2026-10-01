"""verify_selective_forget_index.py — selective forget 的索引刪除與 catalog 重產按「路徑」走。

守住 wg_atoms.apply_selective_forget 的逐檔契約（moved: atom/src_path/dst_path/ok/error/index）
與索引後處理：
- 同一 mem_dir 內 shared/dup.md 與 personal/u/dup.md 同名共存：各自的 `_atom_index.json` 條目
  只被自己的 forget 刪，不互相誤刪
- 搬移失敗的顆：索引條目保留（檔還在原處，索引不能先失真）
- 索引條目只按 path 定位：條目 name 與檔名 stem 不同仍刪得到
- 搬檔前嚴格讀索引：壞 JSON、或任一條目不是 {name: 非空 str, path: 非空 str} 的 dict →
  本輪一顆都不搬，moved 全標 error、index_errors 記「entry #i malformed」
- self_iterate 走真入口：各記憶根的 catalog_error 彙總進 forget.catalog_errors
- MD 搬成功、sidecar 搬失敗 → 索引照刪、error 記 sidecar
- catalog 重產同步跑、帶 `--memory-dir <該 mem_dir>`（專案層不再重產根層 catalog）；rc≠0 → catalog_error
- memory-audit.py enforce_decay 走 moved：同名跨層輸出列各自標 index 結果

受控 tmp，不動磁碟既有 atom。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
from wg_atoms import apply_selective_forget  # noqa: E402
from lib.atom_index_json import load_atom_index_json, save_atom_index_json  # noqa: E402
from lib.atom_spec import build_atom_content  # noqa: E402

CFG_ISOLATE = {"self_iteration": {"forget": {"enabled": True, "dry_run": False, "isolate_threshold": 0.3}}}


def _mk_atom(mem: Path, name: str, subdir: str, scope: str = "global", *, index: bool = True) -> Path:
    d = mem / subdir
    d.mkdir(parents=True, exist_ok=True)
    md = d / f"{name}.md"
    md.write_text(build_atom_content(
        title=name, scope=scope, confidence="[臨]", triggers=["a", "b", "c"],
        knowledge=["k"], actions=["act"], today="2026-01-01"), encoding="utf-8", newline="\n")
    last_used = (date.today() - timedelta(days=200)).isoformat()
    md.with_suffix(".access.json").write_text(json.dumps(
        {"last_used": last_used, "confirmations": 1, "read_hits": 1, "useful_hits": 1, "used_fail": 1}),
        encoding="utf-8")
    if index:
        _index_add(mem, name, f"memory/{subdir}/{name}.md", scope)
    return md


def _index_add(mem: Path, name: str, path: str, scope: str) -> None:
    """直接 append 條目：upsert_atom 按名字覆蓋，擺不出「同名跨層各一條」的索引。"""
    data = load_atom_index_json(mem) if (mem / "_atom_index.json").exists() else {"atoms": []}
    data.setdefault("atoms", []).append({"name": name, "path": path, "triggers": ["a", "b", "c"], "scope": scope})
    save_atom_index_json(mem, data)


def _cand(md: Path) -> dict:
    return {"atom": md.stem, "path": str(md), "score": 0.1, "last_used": "2026-01-01", "confirmations": 0}


def _index_paths(mem: Path, name: str) -> list:
    return sorted(a["path"] for a in load_atom_index_json(mem)["atoms"] if a["name"] == name)


@pytest.fixture
def mem(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_atoms, "_trigger_sync_memory_index", lambda *a, **k: None)
    m = tmp_path / "proj" / ".claude" / "memory"
    m.mkdir(parents=True)
    return m


# ─── apply_selective_forget：索引按路徑刪 ─────────────────────────────────────

def test_same_name_both_forgotten_each_index_entry_removed(mem):
    shared = _mk_atom(mem, "dup", "shared/Lv1", "shared")
    personal = _mk_atom(mem, "dup", "personal/u", "personal:u")
    assert len(_index_paths(mem, "dup")) == 2
    res = apply_selective_forget([_cand(shared), _cand(personal)], CFG_ISOLATE, atoms_dir=mem)
    assert res["forgotten"] == ["dup", "dup"] and res["index_errors"] == []
    assert [(m["ok"], m["index"]) for m in res["moved"]] == [(True, "removed"), (True, "removed")]
    assert [m["src_path"] for m in res["moved"]] == [str(shared), str(personal)]
    assert Path(res["moved"][0]["dst_path"]) == mem / "shared" / "Lv1" / "_distant" / "dup.md"
    assert _index_paths(mem, "dup") == []


def test_forget_shared_only_keeps_personal_index_entry(mem):
    shared = _mk_atom(mem, "dup", "shared/Lv1", "shared")
    personal = _mk_atom(mem, "dup", "personal/u", "personal:u")
    res = apply_selective_forget([_cand(shared)], CFG_ISOLATE, atoms_dir=mem)
    assert res["moved"][0]["index"] == "removed"
    assert not shared.exists() and personal.exists()
    assert _index_paths(mem, "dup") == ["memory/personal/u/dup.md"]  # 他層同名條目不動


def test_move_failure_keeps_index_entry(mem, monkeypatch):
    shared = _mk_atom(mem, "dup", "shared/Lv1", "shared")
    personal = _mk_atom(mem, "dup", "personal/u", "personal:u")
    import shutil
    real_move = shutil.move

    def _move(src, dst):
        if Path(src) == shared:
            raise OSError("locked")
        return real_move(src, dst)
    monkeypatch.setattr(shutil, "move", _move)
    res = apply_selective_forget([_cand(shared), _cand(personal)], CFG_ISOLATE, atoms_dir=mem)
    assert res["forgotten"] == ["dup"] and res["skipped"] == ["dup"]
    failed, done = res["moved"]
    assert failed["ok"] is False and "locked" in failed["error"] and "index" not in failed
    assert done["ok"] is True and done["index"] == "removed"
    assert shared.exists()
    assert _index_paths(mem, "dup") == ["memory/shared/Lv1/dup.md"]  # 搬失敗的顆條目保留


@pytest.mark.parametrize("atoms_json", [
    [None],                                             # 條目不是 dict
    [{"name": 1}],                                      # name 非字串、缺 path
    [{"name": "nopath", "triggers": ["a"], "scope": "shared"}],  # 缺 path
    [{"name": "", "path": "memory/shared/Lv1/stale.md"}],        # name 空字串
], ids=["null-entry", "name-int-no-path", "missing-path", "empty-name"])
def test_malformed_index_entry_blocks_all_moves(mem, atoms_json):
    md = _mk_atom(mem, "stale", "shared/Lv1", "shared", index=False)
    raw = json.dumps({"atoms": atoms_json})
    (mem / "_atom_index.json").write_text(raw, encoding="utf-8")
    res = apply_selective_forget([_cand(md)], CFG_ISOLATE, atoms_dir=mem)
    assert res["mode"] == "isolated" and res["forgotten"] == [] and res["skipped"] == ["stale"]
    m = res["moved"][0]
    assert m["ok"] is False and m["md_moved"] is False and m["index"] == "error"
    assert "index unreadable" in m["error"] and "entry #0 malformed" in m["error"]
    assert res["index_errors"] == [{"atom": "stale", "src_path": str(md), "error": m["error"]}]
    assert md.exists() and not (md.parent / "_distant" / "stale.md").exists()  # 檔沒動
    assert (mem / "_atom_index.json").read_text(encoding="utf-8") == raw  # 索引沒被覆寫


def test_strict_loader_accepts_well_formed_entries(mem):
    _mk_atom(mem, "ok", "shared/Lv1", "shared")
    entries, err = wg_atoms._forget_load_index_strict(mem)
    assert err is None and [a["name"] for a in entries] == ["ok"]


def test_index_entry_name_differs_from_stem_still_removed_by_path(mem):
    md = _mk_atom(mem, "renamed-file", "shared/Lv1", "shared", index=False)
    _index_add(mem, "old-name", "memory/shared/Lv1/renamed-file.md", "shared")
    res = apply_selective_forget([_cand(md)], CFG_ISOLATE, atoms_dir=mem)
    assert res["moved"][0]["index"] == "removed" and res["index_errors"] == []
    assert _index_paths(mem, "old-name") == []


def test_corrupt_index_blocks_all_moves(mem):
    md = _mk_atom(mem, "stale", "shared/Lv1", "shared")
    (mem / "_atom_index.json").write_text("{not json", encoding="utf-8")
    res = apply_selective_forget([_cand(md)], CFG_ISOLATE, atoms_dir=mem)
    assert res["forgotten"] == [] and res["skipped"] == ["stale"]
    m = res["moved"][0]
    assert m["ok"] is False and m["md_moved"] is False and "index unreadable" in m["error"]
    assert m["index"] == "error" and res["index_errors"][0]["atom"] == "stale"
    assert md.exists() and not (md.parent / "_distant" / "stale.md").exists()  # 檔沒動
    assert (mem / "_atom_index.json").read_text(encoding="utf-8") == "{not json"  # 索引沒被覆寫


def test_md_moved_but_sidecar_failed_still_drops_index(mem, monkeypatch):
    md = _mk_atom(mem, "half", "shared/Lv1", "shared")
    import shutil
    real_move = shutil.move

    def _move(src, dst):
        if str(src).endswith(".access.json"):
            raise OSError("sidecar locked")
        return real_move(src, dst)
    monkeypatch.setattr(shutil, "move", _move)
    res = apply_selective_forget([_cand(md)], CFG_ISOLATE, atoms_dir=mem)
    m = res["moved"][0]
    assert res["forgotten"] == ["half"]
    assert m["ok"] is True and m["md_moved"] is True and m["sidecar_moved"] is False
    assert m["error"].startswith("sidecar:") and "sidecar locked" in m["error"]
    assert m["index"] == "removed" and _index_paths(mem, "half") == []
    assert not md.exists() and md.with_suffix(".access.json").exists()  # sidecar 留原處


def test_not_indexed_atom_marks_none(mem):
    md = _mk_atom(mem, "lonely", "shared/Lv1", "shared", index=False)
    _mk_atom(mem, "other", "shared/Lv1", "shared")  # 讓索引檔存在
    res = apply_selective_forget([_cand(md)], CFG_ISOLATE, atoms_dir=mem)
    assert res["moved"][0]["index"] == "none" and res["index_errors"] == []


# ─── catalog 重產：同步跑、帶該記憶根、回收結果 ─────────────────────────────

class _Done:
    def __init__(self, rc=0, stderr=""):
        self.returncode, self.stderr, self.stdout = rc, stderr, ""


def _fake_run(calls, rc=0, stderr=""):
    def _run(cmd, **kw):
        calls.append((cmd, kw))
        return _Done(rc, stderr)
    return _run


def test_catalog_regen_targets_the_same_memory_root(tmp_path, monkeypatch):
    mem = tmp_path / "proj" / ".claude" / "memory"
    md = _mk_atom(mem, "stale", "shared/Lv1", "shared")
    calls = []
    monkeypatch.setattr(subprocess, "run", _fake_run(calls))
    res = apply_selective_forget([_cand(md)], CFG_ISOLATE, atoms_dir=mem)
    assert res["forgotten"] == ["stale"] and res["catalog_error"] is None
    assert len(calls) == 1
    cmd, kw = calls[0]
    assert cmd[1].endswith("sync-memory-index.py") and "--write" in cmd
    assert cmd[cmd.index("--memory-dir") + 1] == str(mem)  # 重產專案根，不是根層 memory/
    assert kw["timeout"] == 60 and kw["env"]["PYTHONIOENCODING"] == "utf-8" and "creationflags" in kw


def test_catalog_regen_failure_is_returned(tmp_path, monkeypatch):
    mem = tmp_path / "proj" / ".claude" / "memory"
    md = _mk_atom(mem, "stale", "shared/Lv1", "shared")
    monkeypatch.setattr(subprocess, "run", _fake_run([], rc=1, stderr="line1\nTraceback boom\n"))
    res = apply_selective_forget([_cand(md)], CFG_ISOLATE, atoms_dir=mem)
    assert res["forgotten"] == ["stale"]  # 檔與索引已處理，只有 catalog 沒重產
    assert "rc=1" in res["catalog_error"] and "Traceback boom" in res["catalog_error"]


def test_catalog_regen_timeout_is_returned(tmp_path, monkeypatch):
    mem = tmp_path / "proj" / ".claude" / "memory"
    md = _mk_atom(mem, "stale", "shared/Lv1", "shared")

    def _run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
    monkeypatch.setattr(subprocess, "run", _run)
    res = apply_selective_forget([_cand(md)], CFG_ISOLATE, atoms_dir=mem)
    assert "timeout" in res["catalog_error"]


def test_root_regen_has_no_memory_dir_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", _fake_run(calls))
    assert wg_atoms._trigger_sync_memory_index() is None
    assert "--memory-dir" not in calls[0][0]


def test_self_iterate_aggregates_catalog_errors(mem, monkeypatch):
    """SessionEnd 真入口 _self_iterate_atoms：各記憶根 apply_selective_forget 回的 catalog_error
    收進 forget.catalog_errors（帶記憶根前綴、不吞）。"""
    md = _mk_atom(mem, "stale", "shared/Lv1", "shared")  # 200 天前、低用 → 封存候選
    monkeypatch.setattr(wg_atoms, "iter_atom_files_multi", lambda: iter([md]))
    monkeypatch.setattr(wg_atoms, "log_promotion_heartbeat", lambda **k: None)
    calls = []

    def _fake_forget(cands, config, *, atoms_dir=None, staging_dir=None):
        calls.append((cands, atoms_dir, staging_dir))
        return {"mode": "isolated", "candidates": [c["atom"] for c in cands],
                "forgotten": [c["atom"] for c in cands], "skipped": [], "moved": [],
                "index_errors": [], "catalog_error": "sync-memory-index rc=2: boom"}
    monkeypatch.setattr(wg_atoms, "apply_selective_forget", _fake_forget)

    res = wg_atoms._self_iterate_atoms({"session": {"cwd": ""}}, CFG_ISOLATE)

    assert len(calls) == 1
    cands, atoms_dir, staging_dir = calls[0]
    assert [c["atom"] for c in cands] == ["stale"] and atoms_dir == mem and staging_dir == mem / "_staging"
    assert res["forget"]["mode"] == "isolated" and res["forget"]["forgotten"] == ["stale"]
    assert res["forget"]["catalog_errors"] == [f"{mem}: sync-memory-index rc=2: boom"]


# ─── memory-audit enforce_decay 走 moved ────────────────────────────────────

def _load_memory_audit():
    spec = importlib.util.spec_from_file_location(
        "memory_audit_forget_index_under_test", CLAUDE / "tools" / "memory-audit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MA = _load_memory_audit()  # 模組層載入：它會包 sys.stdout，測試內載入會繞過 capsys


def test_enforce_decay_same_name_across_sublayers(mem, tmp_path, monkeypatch, capsys):
    import argparse
    shared = _mk_atom(mem, "dup", "shared/Lv1", "shared")
    personal = _mk_atom(mem, "dup", "personal/u", "personal:u")
    keep = _mk_atom(mem, "fresh", "shared/Lv1", "shared")
    keep.with_suffix(".access.json").write_text(json.dumps(
        {"last_used": date.today().isoformat(), "confirmations": 3, "read_hits": 5, "useful_hits": 5}),
        encoding="utf-8")
    monkeypatch.setattr(MA, "discover_layers", lambda *a, **k: [("project", mem)])
    monkeypatch.setattr(MA, "CLAUDE_DIR", tmp_path)
    audit = []
    monkeypatch.setattr(MA, "_write_audit_entry", lambda e: audit.append(e))
    monkeypatch.setattr(MA, "_forget_config",
                        lambda: {"self_iteration": {"decay_half_life_days": 30,
                                                    "archive_score_threshold": 0.3,
                                                    "forget": {"enabled": False, "dry_run": True}}})
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no service")))
    MA.enforce_decay(argparse.Namespace(dry_run=False, global_only=False, project=None, project_dir=None))
    out = capsys.readouterr().out
    assert out.count("OK: 已隔離") == 2 and out.count("_atom_index.json entry removed: dup") == 2, out
    assert "fresh" not in out
    assert not shared.exists() and not personal.exists() and keep.exists()
    assert _index_paths(mem, "dup") == [] and _index_paths(mem, "fresh") == ["memory/shared/Lv1/fresh.md"]
    assert sorted(e["path"] for e in audit) == sorted(
        str(p.relative_to(tmp_path)) for p in (shared, personal))  # audit 記路徑身分，不只名字
