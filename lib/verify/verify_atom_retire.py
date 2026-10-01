"""verify_atom_retire.py — atom 退役（memory-audit.delete_atom）與 Supersedes 寫前檢查

退役契約：護欄全部在任何異動之前（[固] 拒、Confidence 讀不到拒、核心保護名拒、核心清單退
fallback 拒、被 Related/Supersedes 引用拒、引用掃描有讀不到的檔拒、找不到拒）；caller 給
atom_path 時直接用（須在該層根下且 stem 相符），不再遍歷整層找同名；執行順序 向量 → Related
清理 → 索引 → 搬檔（不可逆最後）；向量只刪定位路徑所屬那一個 layer；①–④ 冪等，任一步失敗
即停、不搬檔、回 (False, msg, info)；重跑同一退役可從頭成功（檔案仍在原位）。
check_supersedes：目標可解析／非自指／無循環／非核心保護名／鏈上檔讀不到拒／清單 fallback 拒。
"""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

import pytest

LIB_PARENT = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude/
if str(LIB_PARENT) not in sys.path:
    sys.path.insert(0, str(LIB_PARENT))

from lib import atom_io  # noqa: E402
from lib.atom_io import check_supersedes, read_supersedes  # noqa: E402
from lib.atom_index_json import load_atom_index_json, upsert_atom  # noqa: E402
from lib.atom_spec import build_atom_content  # noqa: E402

FIXED_TODAY = "2026-10-01"


def _load_memory_audit():
    spec = importlib.util.spec_from_file_location(
        "memory_audit_under_test", LIB_PARENT / "tools" / "memory-audit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MA = _load_memory_audit()


def _mk_atom(mem: Path, name: str, *, confidence="[臨]", related=None, supersedes=None,
             subdir: str = "", scope="global") -> Path:
    d = mem / subdir if subdir else mem
    d.mkdir(parents=True, exist_ok=True)
    md = d / f"{name}.md"
    md.write_text(build_atom_content(
        title=name, scope=scope, confidence=confidence, triggers=["a", "b", "c"],
        knowledge=["k"], actions=["act"], related=related, supersedes=supersedes,
        today=FIXED_TODAY), encoding="utf-8", newline="\n")
    md.with_suffix(".access.json").write_text(json.dumps({"schema": "atom-access-v3"}),
                                              encoding="utf-8")
    rel = f"{subdir}/{name}.md" if subdir else f"{name}.md"
    upsert_atom(mem, name, f"memory/{rel}", ["a", "b", "c"], scope=scope)
    return md


@pytest.fixture
def env(tmp_path, monkeypatch):
    """tmp 全域層 + tmp personal 層；向量庫不存在、重索引服務不可達、audit.log 落 tmp。"""
    mem = tmp_path / "memory"
    personal = tmp_path / "personal_layer"
    for m in (mem, personal):
        m.mkdir(parents=True)
        (m / "MEMORY.md").write_text("# idx\n\n| atom | path |\n|---|---|\n", encoding="utf-8")
    monkeypatch.setattr(MA, "discover_layers",
                        lambda *a, **k: [("global", mem), ("personal", personal)])
    monkeypatch.setattr(MA, "CLAUDE_DIR", tmp_path)
    monkeypatch.setattr(MA, "AUDIT_LOG_PATH", tmp_path / "audit.log")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no service")))
    return {"mem": mem, "personal": personal, "root": tmp_path}


def _index_has(mem: Path, name: str) -> bool:
    return any(a["name"] == name for a in load_atom_index_json(mem)["atoms"])


def _add_memory_row(mem: Path, name: str) -> None:
    p = mem / "MEMORY.md"
    p.write_text(p.read_text(encoding="utf-8") + f"| {name} | {name}.md |\n", encoding="utf-8")


# ─── 護欄 ──────────────────────────────────────────────────────────────────────


def test_guard_fixed_confidence_rejected(env):
    mem = env["mem"]
    md = _mk_atom(mem, "solid-one", confidence="[固]")
    ok, msg, info = MA.delete_atom("solid-one", "global", reason="test")
    assert not ok and "Supersedes" in msg
    assert md.exists() and _index_has(mem, "solid-one")
    assert info["steps_done"] == [] and info["steps_failed"] and info["old_path"] == str(md)


def test_guard_referenced_rejected_lists_referrers(env):
    mem, personal = env["mem"], env["personal"]
    md = _mk_atom(mem, "target-x")
    _mk_atom(mem, "friend", related=["target-x"])
    _mk_atom(personal, "sup-user", supersedes=["target-x"], subdir="personal/holy",
             scope="personal:holy")
    ok, msg, info = MA.delete_atom("target-x", "global", reason="test")
    assert not ok and "referenced by" in msg
    assert "global/friend (Related)" in msg and "personal/sup-user (Supersedes)" in msg
    assert sorted(info["references"]) == ["global/friend (Related)", "personal/sup-user (Supersedes)"]
    assert md.exists() and _index_has(mem, "target-x")


def test_guard_core_protected_rejected(env):
    mem = env["mem"]
    md = _mk_atom(mem, "preferences")  # LOCAL_REALM_CORE_PROTECTED_EXACT
    ok, msg, _ = MA.delete_atom("preferences", "global", reason="test")
    assert not ok and "core-protected" in msg
    assert md.exists() and _index_has(mem, "preferences")


def test_guard_core_protected_list_unavailable_rejects(env, monkeypatch):
    mem = env["mem"]
    md = _mk_atom(mem, "plain-atom")
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "lib.atom_locations":
            raise ImportError("boom")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    ok, msg, _ = MA.delete_atom("plain-atom", "global", reason="test")
    assert not ok and "core-protected list unavailable" in msg
    assert md.exists()


def test_guard_confidence_unreadable_rejects(env, monkeypatch):
    """檔讀不到 → _atom_confidence 回 None → 拒（不能當「非 [固]」放行）。"""
    mem = env["mem"]
    md = _mk_atom(mem, "unreadable-conf")
    assert MA._atom_confidence(md) == "[臨]"
    assert MA._atom_confidence(mem / "nope.md") is None
    monkeypatch.setattr(MA, "_atom_confidence", lambda _p: None)
    ok, msg, info = MA.delete_atom("unreadable-conf", "global", reason="t")
    assert not ok and "cannot read" in msg and "Confidence" in msg
    assert md.exists() and info["steps_done"] == []


def test_guard_reference_scan_unreadable_rejects(env, monkeypatch):
    """引用掃描任一檔讀不到 → 拒並列出該檔（它可能正引用著目標）。"""
    mem = env["mem"]
    md = _mk_atom(mem, "scan-target")
    _mk_atom(mem, "broken-ref")
    real_read = Path.read_text

    def flaky_read(self, *a, **k):
        if self.name == "broken-ref.md":
            raise OSError("EACCES")
        return real_read(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", flaky_read)
    refs, unreadable = MA._scan_references("scan-target", [("global", mem)], md)
    assert refs == [] and unreadable and unreadable[0].startswith("global/broken-ref")
    ok, msg, _ = MA.delete_atom("scan-target", "global", reason="t")
    assert not ok and "unreadable" in msg and "global/broken-ref" in msg
    assert md.exists() and _index_has(mem, "scan-target")


def test_guard_core_protected_fallback_rejects(env, monkeypatch):
    """realm-lexicon.json 載入失敗退 fallback 子集 → 「非核心」判定不可信 → 退役一律拒。"""
    from lib import atom_locations as AL
    assert AL.core_protected_source() == "json"
    mem = env["mem"]
    md = _mk_atom(mem, "plain-two")
    monkeypatch.setattr(AL, "_CORE_PROTECTED_SOURCE", "fallback")
    assert AL.core_protected_source() == "fallback"
    ok, msg, _ = MA.delete_atom("plain-two", "global", reason="t")
    assert not ok and "not loaded" in msg and "fallback" in msg
    assert md.exists() and _index_has(mem, "plain-two")


def test_not_found_is_error(env):
    ok, msg, info = MA.delete_atom("ghost", "global", reason="test")
    assert not ok and "not found" in msg and info["old_path"] is None
    ok, msg, _ = MA.delete_atom("ghost", "project", reason="test")
    assert not ok and "requires project_dir" in msg


# ─── 正常退役 ──────────────────────────────────────────────────────────────────


def test_retire_moves_to_distant_and_clears_index(env):
    mem = env["mem"]
    md = _mk_atom(mem, "bye-atom", subdir="設計通則")
    _add_memory_row(mem, "bye-atom")
    ok, msg, info = MA.delete_atom("bye-atom", "global", reason="證實無用")
    assert ok, msg
    assert not md.exists() and not md.with_suffix(".access.json").exists()
    new_path = Path(info["new_path"])
    assert new_path.exists() and new_path.parent.parent.name == "_distant"
    assert new_path.with_suffix(".access.json").exists()
    assert not _index_has(mem, "bye-atom")
    assert "| bye-atom " not in (mem / "MEMORY.md").read_text(encoding="utf-8")
    assert info["index_ok"] is True and info["steps_failed"] == []
    assert info["steps_done"] == ["guards", "vector", "related", "index", "move"]
    assert info["old_path"] == str(md)
    assert "證實無用" in new_path.read_text(encoding="utf-8")  # 演化日誌寫 reason
    audit = (env["root"] / "audit.log").read_text(encoding="utf-8")
    assert '"action": "retire"' in audit and "證實無用" in audit


def test_dry_run_changes_nothing(env):
    mem = env["mem"]
    md = _mk_atom(mem, "dry-atom")
    before = md.read_bytes()
    ok, msg, info = MA.delete_atom("dry-atom", "global", dry_run=True, reason="t")
    assert ok and "DRY-RUN" in msg
    assert md.read_bytes() == before and _index_has(mem, "dry-atom")
    assert info["steps_done"] == ["guards"] and info["new_path"] is None


def test_project_layer_via_project_dir(tmp_path, monkeypatch):
    """layer=project 以 project_dir 定位（discover_layers 真實路徑：須有 MEMORY.md）。"""
    proj_mem = tmp_path / "proj" / ".claude" / "memory"
    proj_mem.mkdir(parents=True)
    (proj_mem / "MEMORY.md").write_text("# p\n", encoding="utf-8")
    md = _mk_atom(proj_mem, "proj-atom", subdir="shared", scope="shared")
    real = MA.discover_layers
    monkeypatch.setattr(MA, "discover_layers",
                        lambda *a, **k: [ly for ly in real(*a, **k) if ly[0] == "project"])
    monkeypatch.setattr(MA, "CLAUDE_DIR", tmp_path)
    monkeypatch.setattr(MA, "AUDIT_LOG_PATH", tmp_path / "audit.log")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no service")))
    ok, msg, info = MA.delete_atom("proj-atom", "project", reason="t")
    assert not ok and "requires project_dir" in msg  # 沒給 project_dir → 明確錯
    ok, msg, info = MA.delete_atom("proj-atom", "project", project_dir=proj_mem, reason="t")
    assert ok, msg
    assert not md.exists() and not _index_has(proj_mem, "proj-atom")


# ─── atom_path：定位路徑直接用（同名跨層不重找） ─────────────────────────────


def _project_env(tmp_path, monkeypatch):
    proj_mem = tmp_path / "proj" / ".claude" / "memory"
    proj_mem.mkdir(parents=True)
    (proj_mem / "MEMORY.md").write_text("# p\n", encoding="utf-8")
    real = MA.discover_layers
    monkeypatch.setattr(MA, "discover_layers",
                        lambda *a, **k: [ly for ly in real(*a, **k) if ly[0] == "project"])
    monkeypatch.setattr(MA, "CLAUDE_DIR", tmp_path)
    monkeypatch.setattr(MA, "AUDIT_LOG_PATH", tmp_path / "audit.log")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no service")))
    return proj_mem


def test_atom_path_same_name_across_sublayers_retires_only_that_one(tmp_path, monkeypatch):
    """shared/dup 與 personal/u/dup 同名：給 atom_path=shared 那顆 → 只退役它，personal 那顆不動。
    （舊碼遍歷整層取第一個同名檔，會退役錯顆。）"""
    proj_mem = _project_env(tmp_path, monkeypatch)
    personal_md = _mk_atom(proj_mem, "dup", subdir="personal/u", scope="personal:u")
    shared_md = _mk_atom(proj_mem, "dup", subdir="shared/Lv1", scope="shared")
    ok, msg, info = MA.delete_atom("dup", "project", project_dir=proj_mem, reason="t",
                                   atom_path=shared_md)
    assert ok, msg
    assert not shared_md.exists() and personal_md.exists()
    assert info["old_path"] == str(shared_md)
    # 反向：指定 personal 那顆
    ok, msg, info = MA.delete_atom("dup", "project", project_dir=proj_mem, reason="t",
                                   atom_path=personal_md)
    assert ok, msg
    assert not personal_md.exists() and info["old_path"] == str(personal_md)


def test_atom_path_outside_layer_or_wrong_stem_rejected(tmp_path, monkeypatch):
    proj_mem = _project_env(tmp_path, monkeypatch)
    md = _mk_atom(proj_mem, "inside", subdir="shared", scope="shared")
    other = tmp_path / "elsewhere" / "inside.md"
    other.parent.mkdir()
    other.write_text(md.read_text(encoding="utf-8"), encoding="utf-8")
    ok, msg, info = MA.delete_atom("inside", "project", project_dir=proj_mem, reason="t",
                                   atom_path=other)
    assert not ok and "not under layer" in msg and info["steps_done"] == []
    assert md.exists() and other.exists()
    ok, msg, _ = MA.delete_atom("inside", "project", project_dir=proj_mem, reason="t",
                                atom_path=proj_mem / "shared" / "other-name.md")
    assert not ok and "stem" in msg
    ok, msg, _ = MA.delete_atom("inside", "project", project_dir=proj_mem, reason="t",
                                atom_path=proj_mem / "shared" / "sub" / "inside.md")
    assert not ok and "does not exist" in msg
    assert md.exists()


def test_cli_retire_passes_located_path(tmp_path, monkeypatch):
    """atom_io_cli retire 把 locate 到的 loc.path 傳進 delete_atom(atom_path=…)。"""
    from lib import atom_io_cli
    proj = tmp_path / "myproj"
    (proj / ".git").mkdir(parents=True)
    proj_mem = proj / ".claude" / "memory"
    proj_mem.mkdir(parents=True)
    (proj_mem / "MEMORY.md").write_text("# p\n", encoding="utf-8")
    md = _mk_atom(proj_mem, "located", subdir="shared/Lv1", scope="shared")
    seen = {}

    def fake_delete(name, layer, **kw):
        seen.update(kw, name=name, layer=layer)
        return True, "ok", {"old_path": str(kw["atom_path"])}
    monkeypatch.setattr(atom_io_cli, "_load_memory_audit",
                        lambda: type("M", (), {"delete_atom": staticmethod(fake_delete)}))
    r = atom_io_cli.retire_atom({"atom_name": "located", "scope": "shared",
                                 "project_cwd": str(proj), "reason": "t"})
    assert r.ok, r.error
    assert seen["atom_path"] == md and seen["project_dir"] == proj_mem and seen["layer"] == "project"


# ─── 向量：layer 標籤由定位路徑推導，predicate 只打一個 layer ──────────────────


def test_vector_layer_label_from_path(tmp_path, monkeypatch):
    claude = tmp_path / ".claude"
    gmem = claude / "memory"
    monkeypatch.setattr(MA, "GLOBAL_MEMORY_DIR", gmem)
    monkeypatch.setattr(MA, "FAILURES_DIR", gmem / "Failures")
    monkeypatch.setattr(MA, "LEGACY_FAILURES_DIR", claude / "_AIDocs" / "Failures")
    monkeypatch.setattr(MA, "LOCAL_ATOMS_DIR", claude / "_AIDocs" / "_atoms")
    lab = MA._vector_layer_label
    assert lab(claude / "_AIDocs" / "_atoms" / "Tools" / "x.md", "global", gmem) == "extra:local-atoms"
    assert lab(gmem / "Failures" / "工作流" / "f.md", "global", gmem) == "extra:failures"
    assert lab(claude / "_AIDocs" / "Failures" / "f.md", "global", gmem) == "extra:failures"
    assert lab(gmem / "personal" / "holy" / "p.md", "global", gmem) == "personal:global:holy"
    assert lab(gmem / "設計通則" / "g.md", "global", gmem) == "global"
    assert lab(tmp_path / "out" / "g.md", "global", gmem) is None
    pmem = tmp_path / "proj" / ".claude" / "memory"
    monkeypatch.setattr(MA, "_project_slug_for", lambda d: "myproj" if d == pmem else None)
    assert lab(pmem / "shared" / "Lv1" / "a.md", "project", pmem) == "shared:myproj"
    assert lab(pmem / "failures" / "t" / "a.md", "project", pmem) == "shared:myproj"
    assert lab(pmem / "flat.md", "project", pmem) == "shared:myproj"
    assert lab(pmem / "roles" / "dev" / "a.md", "project", pmem) == "role:myproj:dev"
    assert lab(pmem / "personal" / "u" / "a.md", "project", pmem) == "personal:myproj:u"
    assert lab(pmem / "shared" / "a.md", "project", tmp_path / "other") is None
    monkeypatch.setattr(MA, "_project_slug_for", lambda d: None)
    assert lab(pmem / "shared" / "a.md", "project", pmem) is None  # 未登記專案 → 推不出


def test_vector_delete_predicate_targets_single_layer(env, monkeypatch):
    (env["root"] / "memory" / "_vectordb").mkdir(parents=True, exist_ok=True)
    preds = []

    class _Table:
        def delete(self, pred):
            preds.append(pred)

    class _DB:
        def open_table(self, _name):
            return _Table()

    import types
    fake = types.ModuleType("lancedb")
    fake.connect = lambda _p: _DB()
    monkeypatch.setitem(sys.modules, "lancedb", fake)
    ok, msg = MA._vector_delete_chunks("x", "extra:local-atoms")
    assert ok and preds == ["atom_name = 'x' AND layer = 'extra:local-atoms'"]
    ok, msg = MA._vector_delete_chunks("it's", "shared:p")
    assert ok and preds[-1] == "atom_name = 'it''s' AND layer = 'shared:p'"
    ok, msg = MA._vector_delete_chunks("x", None)
    assert not ok and "cannot derive layer label" in msg and len(preds) == 2


def test_vector_permission_error_blocks_move(env, monkeypatch):
    """connect／open_table 拋 PermissionError（非「表不存在」）→ False → 退役停在向量步、不搬檔。"""
    mem = env["mem"]
    md = _mk_atom(mem, "vec-perm", subdir="設計通則")
    (env["root"] / "memory" / "_vectordb").mkdir(parents=True, exist_ok=True)
    import types
    fake = types.ModuleType("lancedb")
    fake.connect = lambda _p: (_ for _ in ()).throw(PermissionError("locked"))
    monkeypatch.setitem(sys.modules, "lancedb", fake)
    monkeypatch.setattr(MA, "_vector_layer_label", lambda *a: "global")
    ok, msg = MA._vector_delete_chunks("vec-perm", "global")
    assert not ok and "connect failed" in msg and "locked" in msg
    ok, msg, info = MA.delete_atom("vec-perm", "global", reason="t")
    assert not ok and "locked" in msg
    assert md.exists() and _index_has(mem, "vec-perm")
    assert info["steps_done"] == ["guards"] and info["steps_failed"][0].startswith("vector:")

    class _DB:
        def open_table(self, _name):
            raise PermissionError("table locked")
    fake.connect = lambda _p: _DB()
    ok, msg = MA._vector_delete_chunks("vec-perm", "global")
    assert not ok and "open_table failed" in msg


# ─── 故障注入：失敗即停、檔案仍在原位、重跑成功 ────────────────────────────────


def test_index_failure_stops_before_move_and_rerun_succeeds(env):
    mem = env["mem"]
    md = _mk_atom(mem, "idx-fail")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(MA, "index_delete_atom",
                   lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
        ok, msg, info = MA.delete_atom("idx-fail", "global", reason="t")
    assert not ok and "disk full" in msg
    assert md.exists() and md.with_suffix(".access.json").exists()
    assert info["index_ok"] is False and info["new_path"] is None
    assert info["steps_done"] == ["guards", "vector", "related"]
    assert info["steps_failed"] and info["steps_failed"][0].startswith("index:")
    assert _index_has(mem, "idx-fail")
    ok, msg, info = MA.delete_atom("idx-fail", "global", reason="t")  # 重跑：從頭成功
    assert ok, msg
    assert not md.exists() and not _index_has(mem, "idx-fail")


def test_vector_unreachable_stops_and_rerun_succeeds(env):
    mem = env["mem"]
    md = _mk_atom(mem, "vec-fail")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(MA, "_vector_delete_chunks",
                   lambda *a, **k: (False, "LanceDB delete failed: connection refused"))
        ok, msg, info = MA.delete_atom("vec-fail", "global", reason="t")
    assert not ok and "connection refused" in msg
    assert md.exists() and _index_has(mem, "vec-fail")
    assert info["steps_done"] == ["guards"] and info["steps_failed"][0].startswith("vector:")
    assert info["index_ok"] is None
    ok, msg, _ = MA.delete_atom("vec-fail", "global", reason="t")  # 重跑：從頭成功
    assert ok, msg
    assert not md.exists()


def test_vector_delete_exception_is_failure(env, monkeypatch):
    """lancedb 存在但 delete 拋例外 → (False, …)；無庫／無表 → 冪等視為完成。"""
    (env["root"] / "memory" / "_vectordb").mkdir(parents=True, exist_ok=True)

    class _Table:
        def delete(self, _pred):
            raise RuntimeError("io error")

    class _DB:
        def open_table(self, _name):
            return _Table()

    import types
    fake = types.ModuleType("lancedb")
    fake.connect = lambda _p: _DB()
    monkeypatch.setitem(sys.modules, "lancedb", fake)
    ok, msg = MA._vector_delete_chunks("x", "global")
    assert not ok and "io error" in msg

    class _DB2:
        def open_table(self, _name):
            raise FileNotFoundError("no table")
    fake.connect = lambda _p: _DB2()
    ok, msg = MA._vector_delete_chunks("x", "global")  # 泛用 FileNotFoundError ≠ 表不存在
    assert not ok and "open_table failed" in msg

    for exc in (ValueError("Table 'atom_chunks' was not found"),
                FileNotFoundError("Table atom_chunks does not exist. Please first call db.create_table")):
        class _DB3:
            def open_table(self, _name, _exc=exc):
                raise _exc
        fake.connect = lambda _p: _DB3()
        ok, msg = MA._vector_delete_chunks("x", "global")
        assert ok and "skipped" in msg


def test_vector_import_failure_with_vectordb_blocks_move(env, monkeypatch):
    """向量庫目錄存在但 import lancedb 失敗 → False（庫裡可能真有 chunks）→ 退役停在向量步、不搬檔。"""
    mem = env["mem"]
    md = _mk_atom(mem, "vec-noimport", subdir="設計通則")
    (env["root"] / "memory" / "_vectordb").mkdir(parents=True, exist_ok=True)
    monkeypatch.setitem(sys.modules, "lancedb", None)  # import 時拋 ImportError
    ok, msg = MA._vector_delete_chunks("vec-noimport", "global")
    assert not ok and "import failed" in msg
    ok, msg, info = MA.delete_atom("vec-noimport", "global", reason="t")
    assert not ok and "import failed" in msg
    assert md.exists() and _index_has(mem, "vec-noimport")
    assert info["steps_done"] == ["guards"] and info["steps_failed"][0].startswith("vector:")


# ─── 索引清理帶實體 path：同名跨層只清這顆的條目 ─────────────────────────────


def test_retire_shared_keeps_personal_index_entry_of_same_name(tmp_path, monkeypatch):
    """shared/dup.md 與 personal/u/dup.md 同名共存、索引指向 personal：退役 shared 後
    personal 的索引條目仍在（舊碼按名刪會把它一起抹掉）。"""
    from lib.atom_index_json import load_atom_index_json
    proj_mem = _project_env(tmp_path, monkeypatch)
    shared_md = _mk_atom(proj_mem, "dup", subdir="shared/Lv1", scope="shared")
    personal_md = _mk_atom(proj_mem, "dup", subdir="personal/u", scope="personal:u")  # 索引 → personal
    ok, msg, info = MA.delete_atom("dup", "project", project_dir=proj_mem, reason="t",
                                   atom_path=shared_md)
    assert ok, msg
    assert not shared_md.exists() and personal_md.exists()
    entries = [a for a in load_atom_index_json(proj_mem)["atoms"] if a["name"] == "dup"]
    assert [a["path"] for a in entries] == ["memory/personal/u/dup.md"]
    assert info["index_ok"] is True and "same-name entry" in msg and "kept" in msg


def test_retire_index_entry_without_path_refuses_before_move(env):
    """索引條目沒有 path 欄位可比對 → index_ok=False、不搬檔（不猜）。"""
    mem = env["mem"]
    md = _mk_atom(mem, "nopath", subdir="設計通則")
    idx = mem / "_atom_index.json"
    data = json.loads(idx.read_text(encoding="utf-8"))
    for a in data["atoms"]:
        if a["name"] == "nopath":
            del a["path"]
    idx.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    ok, msg, info = MA.delete_atom("nopath", "global", reason="t")
    assert not ok and "no path to compare" in msg
    assert info["index_ok"] is False and info["new_path"] is None
    assert md.exists() and _index_has(mem, "nopath")
    assert info["steps_failed"][0].startswith("index:")


def test_memory_md_row_of_other_same_name_atom_is_kept(tmp_path, monkeypatch):
    """MEMORY.md 列帶 path 指到另一顆同名 atom → 該列不動；指到這顆的列才刪。"""
    proj_mem = _project_env(tmp_path, monkeypatch)
    shared_md = _mk_atom(proj_mem, "dup", subdir="shared/Lv1", scope="shared")
    personal_md = _mk_atom(proj_mem, "dup", subdir="personal/u", scope="personal:u")
    (proj_mem / "MEMORY.md").write_text(
        "# p\n\n| atom | path |\n|---|---|\n"
        "| dup | x → [`memory/personal/u/dup.md`](../memory/personal/u/dup.md) |\n"
        "| dup | y → [`memory/shared/Lv1/dup.md`](../memory/shared/Lv1/dup.md) |\n",
        encoding="utf-8")
    ok, msg, _ = MA.delete_atom("dup", "project", project_dir=proj_mem, reason="t",
                                atom_path=shared_md)
    assert ok, msg
    text = (proj_mem / "MEMORY.md").read_text(encoding="utf-8")
    assert "memory/personal/u/dup.md" in text and "memory/shared/Lv1/dup.md" not in text
    assert personal_md.exists()
    # 列沒 path、又有同名他顆 → 不猜，拒
    (proj_mem / "MEMORY.md").write_text("# p\n\n| atom | 說明 |\n|---|---|\n| dup | 說明 |\n",
                                        encoding="utf-8")
    other_md = _mk_atom(proj_mem, "dup", subdir="shared/Lv2", scope="shared")
    ok, msg, info = MA.delete_atom("dup", "project", project_dir=proj_mem, reason="t",
                                   atom_path=other_md)
    assert not ok and "cannot tell" in msg and info["index_ok"] is False
    assert other_md.exists()


# ─── atom_io_cli action=retire（locate → delete_atom(project_dir)） ──────────


def test_cli_retire_project_scope(tmp_path, monkeypatch):
    from lib import atom_io_cli
    proj = tmp_path / "myproj"
    (proj / ".git").mkdir(parents=True)
    proj_mem = proj / ".claude" / "memory"
    proj_mem.mkdir(parents=True)
    (proj_mem / "MEMORY.md").write_text("# p\n", encoding="utf-8")
    md = _mk_atom(proj_mem, "proj-retire", subdir="shared/Lv1", scope="shared")

    real = MA.discover_layers
    monkeypatch.setattr(MA, "discover_layers",
                        lambda *a, **k: [ly for ly in real(*a, **k) if ly[0] == "project"])
    monkeypatch.setattr(MA, "CLAUDE_DIR", tmp_path)
    monkeypatch.setattr(MA, "AUDIT_LOG_PATH", tmp_path / "audit.log")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no service")))
    monkeypatch.setattr(atom_io_cli, "_load_memory_audit", lambda: MA)

    base = {"atom_name": "proj-retire", "scope": "shared", "project_cwd": str(proj), "reason": "t"}
    r = atom_io_cli.retire_atom({**base, "dry_run": True})
    assert r.ok, r.error
    assert r.extra["op"] == "retire" and r.extra["old_path"] == str(md) and md.exists()
    assert r.extra["index_root"] == str(proj / ".claude")

    r = atom_io_cli.retire_atom(base)
    assert r.ok, r.error
    ex = r.extra
    assert ex["op"] == "retire" and ex["atom"] == "proj-retire"
    assert ex["old_path"] == str(md) and Path(ex["new_path"]).exists()
    assert ex["index_ok"] is True and ex["steps_failed"] == []
    assert ex["steps_done"] == ["guards", "vector", "related", "index", "move"]
    assert not _index_has(proj_mem, "proj-retire")
    assert json.loads(json.dumps(r.to_dict(), ensure_ascii=False))["ok"] is True  # stdout 可序列化

    r = atom_io_cli.retire_atom(base)  # 已退役 → 明確 not found，非成功
    assert not r.ok and "not found" in r.error
    r = atom_io_cli.retire_atom({**base, "reason": ""})
    assert not r.ok and "reason" in r.error


# ─── check_supersedes：自指／循環／核心保護／可解析 ───────────────────────────


@pytest.fixture
def sup_env(tmp_path, monkeypatch):
    mem = tmp_path / ".claude" / "memory"
    mem.mkdir(parents=True)
    monkeypatch.setattr(atom_io, "CLAUDE_DIR", tmp_path / ".claude")
    monkeypatch.setattr(atom_io, "GLOBAL_MEMORY_DIR", mem)
    return mem


def _chk(mem: Path, targets, self_slug: str):
    return check_supersedes(targets, self_slug=self_slug, index_dir=mem,
                            index_root=mem.parent, search_roots=[mem])


def _run_cli(monkeypatch, capsys, payload: dict) -> dict:
    import io
    from lib import atom_io_cli
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    atom_io_cli.main()
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _build_params(title: str, supersedes) -> dict:
    return {"title": title, "scope": "global", "confidence": "[臨]", "triggers": ["a", "b", "c"],
            "knowledge": ["k"], "actions": ["act"], "supersedes": supersedes, "today": FIXED_TODAY}


def test_cli_build_and_create_canonicalize_supersedes(sup_env, monkeypatch, capsys):
    """MCP 走 cli build／create_atom：supersedes 傳 "Old Atom" → 檔頭與 receipt 都是 old-atom
    （驗證、落檔、receipt 同一份 slug 清單；原字串落檔會讓注入端對不上 old-atom.md）。"""
    mem = sup_env
    monkeypatch.setattr(atom_io, "atom_search_roots", lambda *a, **k: [mem])  # 全域層搜尋根指 tmp
    _mk_atom(mem, "old-atom", subdir="設計通則")
    r = _run_cli(monkeypatch, capsys, {"action": "build", **_build_params("New One", ["Old Atom"])})
    assert r["ok"], r["error"]
    assert "- Supersedes: old-atom\n" in r["extra"]["content"]
    assert r["extra"]["supersedes"] == ["old-atom"]
    r = _run_cli(monkeypatch, capsys, {"action": "build", **_build_params("New One", ["Old Atom", ""])})
    assert not r["ok"] and "empty target" in r["error"]

    fp = mem / "設計通則" / "new-one.md"
    r = _run_cli(monkeypatch, capsys, {
        "action": "create_atom", "build": _build_params("New One", ["Old Atom"]),
        "file_path": str(fp), "today": FIXED_TODAY,
        "index": {"base_dir": str(mem), "slug": "new-one",
                  "rel_path": "memory/設計通則/new-one.md", "triggers": ["a", "b", "c"]},
    })
    assert r["ok"], r["error"]
    assert r["extra"]["supersedes"] == ["old-atom"]
    assert read_supersedes(fp.read_text(encoding="utf-8")) == ["old-atom"]
    assert "- Supersedes: old-atom\n" in fp.read_text(encoding="utf-8")


def test_check_supersedes_self_reference(sup_env):
    mem = sup_env
    _mk_atom(mem, "me", subdir="設計通則")
    err = _chk(mem, ["me"], "me")
    assert err and "self-reference" in err


def test_check_supersedes_cycle(sup_env):
    mem = sup_env
    _mk_atom(mem, "a-atom", subdir="設計通則")
    _mk_atom(mem, "b-atom", subdir="設計通則", supersedes=["a-atom"])
    _mk_atom(mem, "c-atom", subdir="設計通則", supersedes=["b-atom"])
    # a 想取代 c：c → b → a 回到自身 = 循環
    err = _chk(mem, ["c-atom"], "a-atom")
    assert err and "cycle" in err and "c-atom → b-atom → a-atom" in err
    # 不成環的鏈可通過
    assert _chk(mem, ["c-atom"], "d-atom") is None


def test_check_supersedes_core_protected(sup_env):
    mem = sup_env
    _mk_atom(mem, "preferences", subdir="設計通則")
    err = _chk(mem, ["preferences"], "newcomer")
    assert err and "core-protected" in err
    err = _chk(mem, ["decisions"], "newcomer")  # 前綴保護：不需存在即拒
    assert err and "core-protected" in err


def test_check_supersedes_resolution(sup_env):
    mem = sup_env
    _mk_atom(mem, "exists-one", subdir="設計通則")
    assert _chk(mem, ["exists-one"], "newcomer") is None
    assert _chk(mem, [], "newcomer") is None
    err = _chk(mem, ["exists-one", "ghost"], "newcomer")
    assert err and "ghost" in err and "not found" in err
    assert read_supersedes("- Related: x\n- Supersedes: p, q\n") == ["p", "q"]
    assert read_supersedes("- Related: x\n") == []
    assert _chk(mem, [""], "newcomer") == "supersedes: empty target name"


def test_check_supersedes_chain_unreadable_rejects(sup_env, monkeypatch):
    """沿鏈讀不到檔 → 無法證明不成環 → 回錯誤（不 continue 放行）。"""
    mem = sup_env
    _mk_atom(mem, "root-a", subdir="設計通則")
    _mk_atom(mem, "mid-b", subdir="設計通則", supersedes=["root-a"])
    assert _chk(mem, ["mid-b"], "newcomer") is None
    real_read = Path.read_text

    def flaky_read(self, *a, **k):
        if self.name == "mid-b.md":
            raise OSError("EIO")
        return real_read(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", flaky_read)
    err = _chk(mem, ["mid-b"], "newcomer")
    assert err and "cannot read" in err and "mid-b" in err


def test_check_supersedes_core_list_fallback_rejects(sup_env, monkeypatch):
    from lib import atom_locations as AL
    mem = sup_env
    _mk_atom(mem, "exists-two", subdir="設計通則")
    assert _chk(mem, ["exists-two"], "newcomer") is None
    monkeypatch.setattr(AL, "_CORE_PROTECTED_SOURCE", "fallback")
    err = _chk(mem, ["exists-two"], "newcomer")
    assert err and "not loaded" in err and "fallback" in err


def test_memory_row_with_parent_relative_link_to_other_file_is_kept(tmp_path):
    """catalog 列的 ../../memory/shared/dup.md 指到另一實體檔 → 是別顆的列，不可因剝掉 ../ 誤判成自己的。"""
    proj = tmp_path / "proj"
    mem_dir = proj / ".claude" / "memory"
    mine = mem_dir / "shared" / "dup.md"
    other = proj / "memory" / "shared" / "dup.md"
    for f in (mine, other):
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# dup\n", encoding="utf-8")
    line = "| dup | [dup](../../memory/shared/dup.md) | x |"
    assert MA._memory_row_removable(line, "dup", mine, mem_dir, name_unique=False) is None
    assert MA._memory_row_removable(line, "dup", mine, mem_dir, name_unique=True) is None
    own = "| dup | [dup](shared/dup.md) | x |"
    assert MA._memory_row_removable(own, "dup", mine, mem_dir, name_unique=False) is True


def test_remove_index_entries_refuses_on_corrupt_index_json(tmp_path):
    """_atom_index.json 存在但壞 JSON → 不是「沒有條目」，必須回 False 讓 caller 拒搬檔。"""
    mem_dir = tmp_path / "memory"
    (mem_dir / "shared").mkdir(parents=True)
    atom = mem_dir / "shared" / "x.md"
    atom.write_text("# x\n", encoding="utf-8")
    (mem_dir / "MEMORY.md").write_text("# m\n", encoding="utf-8")
    (mem_dir / "_atom_index.json").write_text("{not json", encoding="utf-8")
    ok, msg = MA._remove_index_entries(mem_dir, "x", atom, name_unique=True)
    assert ok is False and "unreadable" in msg
