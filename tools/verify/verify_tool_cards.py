#!/usr/bin/env python3
"""verify_tool_cards.py — org-memory.py --scan-tools 工具卡封閉驗證。

做什麼：tmp org 根（--init 骨架）＋stub 來源（skills 索引、MCP 樣板、專案 .claude/tools/x.py），驗
① scan 兩次 atom 數與每張卡位元組不變；② 人工改過的卡不被覆寫；③ 進入點刪掉後再 scan → 該卡
Status: deprecated、其餘不變、health-check 標 stale_deps；④ --dry-run 不寫檔；⑤ memory_search 以工具名
命中且 status／author／scope 正確；⑥ skills 有 memory → 產出 skill-memory（專案 memory.py 才撞索引檔、略過有訊號）；
⑦ 沒 org 也沒 --project → exit 2。
怎麼跑：python -m pytest tools/verify/verify_tool_cards.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict

import pytest

CLAUDE_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_DIR = CLAUDE_ROOT / "hooks"
for p in (HOOKS_DIR, HOOKS_DIR / "handlers", CLAUDE_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import wg_core  # noqa: E402
import wg_atoms  # noqa: E402
import ups_search  # noqa: E402
from lib.memory_search import search  # noqa: E402

OWNER = "tester"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def _load_om():
    spec = importlib.util.spec_from_file_location("org_memory", CLAUDE_ROOT / "tools" / "org-memory.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git_init(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True, capture_output=True)
    return path


def _lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _snapshot(*roots: Path) -> Dict[str, bytes]:
    """所有 atom .md 與 _atom_index.json 的位元組快照。"""
    out: Dict[str, bytes] = {}
    for r in roots:
        for f in list(r.rglob("*.md")) + list(r.rglob("_atom_index.json")):
            out[str(f)] = f.read_bytes()
    return out


@pytest.fixture
def world(tmp_path, monkeypatch):
    om = _load_om()
    gmem = tmp_path / "claude" / "memory"
    _lf(gmem / "MEMORY.md", "# g\n")
    _lf(gmem / "_atom_index.json", json.dumps({"version": "1.0", "atoms": []}))

    org = _git_init(tmp_path / "org")
    om.init_tree(org, OWNER)
    omem = org / ".claude" / "memory"

    skills = tmp_path / "skills"
    _lf(skills / "zzqskill" / "SKILL.md", "# zzqskill\n")
    _lf(skills / "_skill_index.json", json.dumps({"skills": [
        {"name": "zzqskill", "dir": "zzqskill", "description": "測試技能：批次整理圖片縮圖（拼貼）"},
    ]}, ensure_ascii=False))
    srv = tmp_path / "srv.js"
    _lf(srv, "// stub\n")
    template = tmp_path / "mcp-servers.template.json"
    _lf(template, json.dumps({"servers": {
        "zzqmcp": {"npm_package": "zzq-mcp-pkg", "description": "測試 MCP：瀏覽器自動化"},
        "zzqlocal": {"npm_package": None, "entry_absolute": str(srv), "description": "本機 stub 伺服器"},
    }}, ensure_ascii=False))

    proj = _git_init(tmp_path / "proj")
    pmem = proj / ".claude" / "memory"
    _lf(pmem / "MEMORY.md", "# p\n")
    tool = proj / ".claude" / "tools" / "zzqtool.py"
    _lf(tool, '"""zzqtool.py — 測試工具：把 A 轉成 B。\n\n怎麼跑：python zzqtool.py\n"""\nprint(1)\n')

    wf = tmp_path / "wf"
    wf.mkdir()
    cfg = {
        "vector_search": {"enabled": True, "global_layer": "bm25", "fusion": "rrf",
                          "bm25_min_score": 0.5, "bm25_top_k": 3},
        "org_memory": {"enabled": True, "roots": [{"id": "org", "root": str(org)}]},
    }
    monkeypatch.setattr(om, "SKILL_INDEX", skills / "_skill_index.json")
    monkeypatch.setattr(om, "SKILLS_DIR", skills)
    monkeypatch.setattr(om, "MCP_TEMPLATE", template)
    monkeypatch.setattr(wg_core, "load_config", lambda: json.loads(json.dumps(cfg)))
    monkeypatch.setattr(wg_atoms, "MEMORY_DIR", gmem)
    monkeypatch.setattr(ups_search, "MEMORY_DIR", gmem)
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_atoms, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_atoms, "_REKICK_MARKER", wf / "vector_rekick.marker")
    monkeypatch.setattr(ups_search, "discover_all_project_memory_dirs", lambda: [])
    monkeypatch.setattr(ups_search, "_semantic_search", lambda *a, **k: [])
    return {"om": om, "org": org, "omem": omem, "proj": proj, "pmem": pmem, "srv": srv, "tool": tool}


def _scan(w, *, dry_run=False, project=True) -> int:
    return w["om"].cmd_scan_tools(str(w["proj"]) if project else None, OWNER, dry_run)


def _cards(w) -> Dict[str, Path]:
    return {
        "zzqskill": w["omem"] / "shared" / "工具" / "skill-zzqskill.md",
        "zzqmcp": w["omem"] / "shared" / "工具" / "mcp-zzqmcp.md",
        "zzqlocal": w["omem"] / "shared" / "工具" / "mcp-zzqlocal.md",
        "zzqtool": w["pmem"] / "shared" / "工具" / "zzqtool.md",
    }


def _status(path: Path) -> str:
    return re.search(r"^- Status:\s*(.+)$", path.read_text(encoding="utf-8"), re.MULTILINE).group(1).strip()


# ─── ① 兩次 scan：atom 數與每張卡位元組不變；四欄正確 ────────────────────────

def test_scan_twice_is_idempotent(world, capsys):
    assert _scan(world) == 0
    cards = _cards(world)
    for name, path in cards.items():
        assert path.is_file(), name
        text = path.read_text(encoding="utf-8")
        assert f"- Author: {OWNER}" in text
        assert "- Status: production" in text
        assert (path.with_suffix(".access.json")).is_file(), f"{name} 無 access.json"
    assert f"- Depends: path:{world['srv'].as_posix()}" in cards["zzqlocal"].read_text(encoding="utf-8")
    assert "- Source: zzq-mcp-pkg" in cards["zzqmcp"].read_text(encoding="utf-8")
    assert "- Depends:" not in cards["zzqmcp"].read_text(encoding="utf-8")
    assert "- [臨] zzqtool.py — 測試工具：把 A 轉成 B。" in cards["zzqtool"].read_text(encoding="utf-8")
    org_idx = json.loads((world["omem"] / "_atom_index.json").read_text(encoding="utf-8"))
    assert sorted(a["name"] for a in org_idx["atoms"]) == ["mcp-zzqlocal", "mcp-zzqmcp", "org-memory", "skill-zzqskill"]
    assert "- Trigger: skill-zzqskill, zzqskill, skill, " in cards["zzqskill"].read_text(encoding="utf-8")

    before = _snapshot(world["omem"], world["pmem"])
    capsys.readouterr()
    assert _scan(world) == 0
    out = capsys.readouterr().out
    assert out.count("已存在：") == 4  # org 3 ＋ project 1（--init 種的 org-memory 不是掃描來源）
    assert "建立：" not in out
    assert _snapshot(world["omem"], world["pmem"]) == before


# ─── ② 人工改過的卡再 scan 不被覆寫 ──────────────────────────────────────────

def test_manual_edit_survives_rescan(world):
    assert _scan(world) == 0
    card = _cards(world)["zzqskill"]
    edited = card.read_text(encoding="utf-8") + "- 人工補充：這行不能被掃描洗掉\n"
    _lf(card, edited)
    assert _scan(world) == 0
    assert card.read_text(encoding="utf-8") == edited


# ─── ③ 進入點消失 → 該卡 deprecated、其餘不變；health-check 標 stale_deps ──────

def test_missing_entry_marks_deprecated_only_that_card(world, capsys):
    assert _scan(world) == 0
    cards = _cards(world)
    before = _snapshot(world["omem"], world["pmem"])
    world["srv"].unlink()
    world["tool"].unlink()
    capsys.readouterr()
    assert _scan(world) == 0
    out = capsys.readouterr().out
    assert "退役：mcp-zzqlocal" in out and "退役：zzqtool" in out
    assert _status(cards["zzqlocal"]) == "deprecated"
    assert _status(cards["zzqtool"]) == "deprecated"
    after = _snapshot(world["omem"], world["pmem"])
    changed = {k for k in before if before[k] != after.get(k)}
    assert changed == {str(cards["zzqlocal"]), str(cards["zzqtool"])}
    # 只改 Status 那一行
    old_lines = before[str(cards["zzqlocal"])].decode("utf-8").splitlines()
    new_lines = after[str(cards["zzqlocal"])].decode("utf-8").splitlines()
    assert [l for l in old_lines if not l.startswith("- Status:")] == [l for l in new_lines if not l.startswith("- Status:")]

    # 再 scan：已 deprecated 不重寫、不重建（進入點沒了也不會再建一張）
    assert _scan(world) == 0
    assert _snapshot(world["omem"], world["pmem"]) == after

    r = subprocess.run(
        [sys.executable, str(CLAUDE_ROOT / "tools" / "atom-health-check.py"), "--report", "--json",
         "--memory-root", str(world["omem"])],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV,
    )
    assert r.returncode == 0, r.stderr
    report = json.loads(r.stdout)
    assert {d["atom"] for d in report["stale_deps"]} == {"mcp-zzqlocal"}


# ─── ④ --dry-run 不寫檔 ────────────────────────────────────────────────────────

def test_dry_run_writes_nothing(world, capsys):
    before = _snapshot(world["omem"], world["pmem"])
    assert _scan(world, dry_run=True) == 0
    out = capsys.readouterr().out
    assert out.count("[dry-run] 將建立：") == 4
    assert _snapshot(world["omem"], world["pmem"]) == before
    assert not any(_cards(world)[n].exists() for n in _cards(world))

    # 退役也只預告
    assert _scan(world) == 0
    world["srv"].unlink()
    capsys.readouterr()
    assert _scan(world, dry_run=True) == 0
    assert "[dry-run] 將退役：mcp-zzqlocal" in capsys.readouterr().out
    assert _status(_cards(world)["zzqlocal"]) == "production"


# ─── ⑤ memory_search 以工具名命中；status／author／scope 正確 ─────────────────

def test_memory_search_finds_cards(world):
    assert _scan(world) == 0
    res = search("zzqskill", cwd=str(world["proj"]), user=OWNER, use_vector=False)
    hit = next(r for r in res["results"] if r["name"] == "skill-zzqskill")
    assert hit["scope"] == "org"
    assert hit["status"] == "production"
    assert hit["author"] == OWNER

    res = search("zzqtool", cwd=str(world["proj"]), user=OWNER, use_vector=False)
    hit = next(r for r in res["results"] if r["name"] == "zzqtool")
    assert hit["scope"] == "shared"
    assert hit["status"] == "production"
    assert hit["author"] == OWNER


# ─── ⑥ skills 有 memory → 建 skill-memory（前綴避開 MEMORY.md）；專案 tools/memory.py 無前綴才撞 → 略過有訊號 ──

def test_memory_skill_gets_prefix_and_bare_project_tool_is_skipped(world, capsys):
    om = world["om"]
    _lf(om.SKILLS_DIR / "memory" / "SKILL.md", "# memory\n")
    _lf(om.SKILL_INDEX, json.dumps({"skills": [
        {"name": "memory", "dir": "memory", "description": "原子記憶系統綜合工具"},
    ]}, ensure_ascii=False))
    _lf(world["proj"] / ".claude" / "tools" / "memory.py", '"""memory.py — 撞名用。"""\n')
    assert _scan(world) == 0
    captured = capsys.readouterr()
    card = world["omem"] / "shared" / "工具" / "skill-memory.md"
    assert card.is_file()
    assert "- Trigger: skill-memory, memory, skill, " in card.read_text(encoding="utf-8")
    assert "略過 memory：" in captured.out and "略過 memory：" in captured.err
    assert not (world["pmem"] / "shared" / "工具" / "memory.md").exists()


# ─── ⑦ 沒 org 也沒 --project → exit 2 且 stderr 有訊息 ───────────────────────

def test_no_target_exits_2(world, monkeypatch, capsys):
    monkeypatch.setattr(wg_core, "load_config", lambda: {"org_memory": {"enabled": False, "roots": []}})
    assert _scan(world, project=False) == 2
    assert "沒有可掃的落點" in capsys.readouterr().err
