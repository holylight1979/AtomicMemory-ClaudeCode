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
