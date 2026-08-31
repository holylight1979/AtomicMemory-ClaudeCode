"""verify_layer_discovery_unify.py — 專案層判定單一來源與相關防呆。

覆蓋：
- register_project 不登記 ~/.claude 本身與家目錄；8.3 短檔名展開後同 slug
- ups_search 跨專案索引快取：鍵隨 MEMORY.md / _atom_index.json mtime 變動；命中免重讀
- tools/memory-audit.discover_layers 與 memory-conflict-detector.discover_layers 走 wg_core 判定
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_ROOT = HOOKS_DIR.parent
for p in (HOOKS_DIR, HOOKS_DIR / "handlers", CLAUDE_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import wg_core  # noqa: E402
import ups_search  # noqa: E402


# ─── register_project 防呆 ─────────────────────────────────────────────────

def test_register_project_skips_claude_dir_and_home(tmp_path, monkeypatch):
    saved = {}
    monkeypatch.setattr(wg_core, "_save_registry", lambda reg: saved.update(reg))
    monkeypatch.setattr(wg_core, "_load_registry", lambda: {"projects": {}})
    monkeypatch.setattr(wg_core, "is_transient_project_root", lambda r: False)
    wg_core.register_project(str(wg_core.CLAUDE_DIR))
    wg_core.register_project(str(wg_core.CLAUDE_DIR.parent))
    assert saved == {}, "~/.claude 與家目錄不得登記為專案"


def test_register_project_registers_real_project(tmp_path, monkeypatch):
    saved = {}
    monkeypatch.setattr(wg_core, "_save_registry", lambda reg: saved.update(reg))
    monkeypatch.setattr(wg_core, "_load_registry", lambda: {"projects": {}})
    monkeypatch.setattr(wg_core, "is_transient_project_root", lambda r: False)
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    wg_core.register_project(str(proj))
    assert len(saved.get("projects", {})) == 1
    root = next(iter(saved["projects"].values()))["root"]
    assert "~" not in root  # resolve() 展開短檔名


# ─── 跨專案索引快取 ───────────────────────────────────────────────────────

def _mk_project(mem: Path, name: str, triggers, alias: str = "") -> None:
    mem.mkdir(parents=True, exist_ok=True)
    (mem / "MEMORY.md").write_text(
        (f"> Project-Aliases: {alias}\n" if alias else "") + "| Atom | x |\n", encoding="utf-8")
    (mem / "_atom_index.json").write_text(json.dumps({"atoms": [
        {"name": name, "path": f"memory/{name}.md", "triggers": list(triggers), "scope": "shared"}
    ]}), encoding="utf-8")


def test_cross_cache_roundtrip_and_invalidation(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path / "wf")
    mem = tmp_path / "p1" / ".claude" / "memory"
    _mk_project(mem, "a1", ["alpha", "beta"], alias="p1")
    cross = [("p1", mem)]
    first = ups_search._load_cross_project_cache(cross)
    assert first[str(mem)]["aliases"] == ["p1"]
    assert first[str(mem)]["atoms"][0][0] == "a1"
    cache_file = tmp_path / "wf" / ups_search._CROSS_CACHE_NAME
    assert cache_file.exists()
    # 命中：不重讀（把索引檔改壞但 mtime 不變 → 仍回快取內容）
    idx = mem / "_atom_index.json"
    st = idx.stat()
    idx.write_text("{broken", encoding="utf-8")
    os.utime(idx, ns=(st.st_atime_ns, st.st_mtime_ns))
    hit = ups_search._load_cross_project_cache(cross)
    assert hit[str(mem)]["atoms"][0][0] == "a1"
    # 失效：mtime 前進 → 重讀（壞 JSON 時 parse_memory_index 走 fallback 索引源，
    # 不炸；重點是不再回舊快取的 a1）
    os.utime(idx, ns=(st.st_atime_ns + 10**9, st.st_mtime_ns + 10**9))
    miss = ups_search._load_cross_project_cache(cross)
    assert all(a[0] != "a1" for a in miss.get(str(mem), {}).get("atoms", []))
    # 修好後再讀回
    _mk_project(mem, "a2", ["gamma"])
    time.sleep(0.01)
    back = ups_search._load_cross_project_cache(cross)
    assert back[str(mem)]["atoms"][0][0] == "a2"


# ─── 工具端判定走 wg_core ─────────────────────────────────────────────────

def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_tools_discovery_follows_wg_core(monkeypatch):
    fake = [("fake-proj", Path("Z:/nonexistent/.claude/memory"))]
    monkeypatch.setattr(wg_core, "discover_all_project_memory_dirs", lambda: list(fake))
    audit = _load(CLAUDE_ROOT / "tools" / "memory-audit.py")
    layers = audit.discover_layers()
    assert any(name == "fake-proj" for name, _ in layers)
    assert not any("Temp" in name or "grok" in name.lower() for name, _ in layers)
    det = _load(CLAUDE_ROOT / "tools" / "memory-conflict-detector.py")
    layers2 = det.discover_layers()
    assert any(name == "project:fake-proj" for name, _ in layers2)
