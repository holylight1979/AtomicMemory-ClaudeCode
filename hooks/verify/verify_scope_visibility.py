"""verify_scope_visibility.py — atom scope 可見性（SPEC §8.1）讀取端封閉。

規則：session 在專案 P、使用者 U 的候選池 = global + P/shared(+failures) + P/roles/{U 持有}
+ P/personal/U。他專案 atom 從不進池；他人 personal / 他人 role 不進池。六條檢索路
（trigger / BM25 / vector / related / alias / AtomAudit 資料面）全靠這個池，不各自過濾。

覆蓋：
- scope_from_rel_path / filter_visible：personal 只給本人、role 只給持有者、V3 佈局同規則
- collect_matched_atoms：他專案 atom trigger 命中 ≥2 也不進 all_atoms / matched
- alias 命中只帶入 MEMORY.md 目錄，且不含 personal/ roles/ 行
- 向量路永遠帶 layers 白名單（management 不豁免）；池外的向量命中被丟
- related 擴散只在候選池內
- injection_log 每筆帶 scope
- 守衛：ups_search 不得再讀他專案 atom 索引
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_ROOT = HOOKS_DIR.parent
for p in (HOOKS_DIR, HOOKS_DIR / "handlers", CLAUDE_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import wg_core  # noqa: E402
import ups_search  # noqa: E402
from wg_atoms import (  # noqa: E402
    scope_from_rel_path, entry_visible, filter_visible, visible_vector_layers, spread_related,
)


# ─── 純函式：path → scope、可見性 ────────────────────────────────────────────

def test_scope_from_rel_path():
    assert scope_from_rel_path("memory/personal/holylight/x.md") == "personal:holylight"
    assert scope_from_rel_path("memory/roles/dev/x.md") == "role:dev"
    assert scope_from_rel_path("memory/shared/Server/x.md") == "shared"
    assert scope_from_rel_path("memory/failures/思考/x.md") == "shared"
    assert scope_from_rel_path("memory/x.md") == "shared"  # flat-legacy = shared
    assert scope_from_rel_path("工作流/x.md", "global") == "global"
    # 全域根的 personal/<user>/（本人跨專案偏好，Phase 2 寫入端）同一規則
    assert scope_from_rel_path("personal/holylight/x.md", "global") == "personal:holylight"
    # 檔名含 personal 字樣不算目錄段
    assert scope_from_rel_path("memory/shared/personal-notes.md") == "shared"
    assert scope_from_rel_path("memory\\personal\\alice\\x.md") == "personal:alice"
    # 自動萃取候選夾 personal/auto/<user>/ 仍屬該使用者
    assert scope_from_rel_path("memory/personal/auto/holylight/x.md") == "personal:holylight"


def test_entry_visible_rules():
    assert entry_visible("memory/personal/holylight/x.md", "holylight", [])
    assert not entry_visible("memory/personal/wellstseng/x.md", "holylight", [])
    assert not entry_visible("memory/personal/holylight/x.md", "", [])
    assert entry_visible("memory/roles/programmer/x.md", "anyone", ["programmer"])
    assert not entry_visible("memory/roles/planner/x.md", "anyone", ["programmer"])
    assert entry_visible("memory/shared/x.md", "", None)
    assert entry_visible("工作流/x.md", "", None)


def test_filter_visible_v3_layout_same_rule():
    """V3 佈局（parse_memory_index 全量）也要按人過濾——他人 personal 不得進池。"""
    entries = [
        ("mine", "memory/personal/holylight/mine.md", ["a"]),
        ("theirs", "memory/personal/wellstseng/theirs.md", ["a"]),
        ("shared1", "memory/shared/s.md", ["a"]),
        ("legacy", "memory/legacy.md", ["a"]),
        ("roleok", "memory/roles/programmer/r.md", ["a"]),
        ("roleno", "memory/roles/planner/r.md", ["a"]),
    ]
    names = [e[0] for e in filter_visible(entries, "holylight", ["programmer"])]
    assert names == ["mine", "shared1", "legacy", "roleok"]


def test_visible_vector_layers():
    assert visible_vector_layers("", "u", ["programmer"]) == ["global"]
    assert visible_vector_layers("c--proj", "u", ["programmer"]) == [
        "global", "shared:c--proj", "role:c--proj:programmer", "personal:c--proj:u",
    ]
    assert visible_vector_layers("c--proj", None, None, include_local=True) == [
        "global", "extra:local-atoms", "shared:c--proj",
    ]


# ─── collect_matched_atoms：他專案 atom 永不進池 ─────────────────────────────

def _mk_other_project(root: Path, alias: str = "") -> Path:
    mem = root / ".claude" / "memory"
    (mem / "personal" / "holylight").mkdir(parents=True)
    (mem / "shared").mkdir()
    body = "# x\n\n- Trigger: server, client\n\n## 知識\n\n- [臨] 洩漏\n"
    (mem / "personal" / "holylight" / "leak-personal.md").write_text(body, encoding="utf-8")
    (mem / "shared" / "leak-shared.md").write_text(body, encoding="utf-8")
    (mem / "_atom_index.json").write_text(json.dumps({"atoms": [
        {"name": "leak-personal", "path": "memory/personal/holylight/leak-personal.md",
         "triggers": ["server", "client"], "scope": "personal:holylight"},
        {"name": "leak-shared", "path": "memory/shared/leak-shared.md",
         "triggers": ["server", "client"], "scope": "shared"},
    ]}), encoding="utf-8")
    (mem / "MEMORY.md").write_text(
        (f"> Project-Aliases: {alias}\n" if alias else "")
        + "# Other — Atom Index\n"
        + "- 共用 atom: shared/leak-shared.md\n"
        + "- 個人狀態: personal/holylight/ 與 roles/dev/\n"
        + "| Atom | Path |\n| leak-shared | memory/shared/leak-shared.md |\n",
        encoding="utf-8")
    return mem


def _base_state(mem_dir: Path):
    (mem_dir / "own.md").write_text("# own\n\n- 內容\n", encoding="utf-8")
    return {
        "atom_index": {
            "global": [["own", "memory/own.md", ["zzzownword"]]],
            "project": [], "project_memory_dir": "", "project_root": "",
            "project_slug": "", "scopes": {"own": "global"},
        },
        "injected_atoms": [],
        "session": {"cwd": "C:/Projects"},
        "user_identity": {"user": "holylight", "roles": ["programmer"], "management": True},
    }


def _collect(tmp_path, monkeypatch, prompt, state=None, cross=None, sem=None):
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path / "wf")
    monkeypatch.setattr(ups_search, "discover_all_project_memory_dirs", lambda: list(cross or []))
    monkeypatch.setattr(ups_search, "_semantic_search", sem or (lambda *a, **k: []))
    monkeypatch.setattr(ups_search, "MEMORY_DIR", mem_dir)
    config = {"vector_search": {"enabled": True, "global_layer": "bm25",
                                "bm25_min_score": 99.0, "bm25_top_k": 3}}
    state = state or _base_state(mem_dir)
    lines: list = []
    matched, _source, all_atoms, _sem, _hints, alias_projs, _intent, _caches = (
        ups_search.collect_matched_atoms("sid", state, config, prompt, prompt.lower(), lines))
    return matched, all_atoms, lines, alias_projs


def test_other_project_atoms_never_enter_pool(tmp_path, monkeypatch):
    other = _mk_other_project(tmp_path / "LineMate")
    prompt = "討論 client 與 server 端的協定送收"  # 兩顆洩漏 atom 各命中 2 個 trigger
    matched, all_atoms, lines, _ = _collect(
        tmp_path, monkeypatch, prompt, cross=[("c--linemate", other)])
    pool = {e[0][0] for e in all_atoms}
    assert "leak-personal" not in pool and "leak-shared" not in pool
    assert not any(e[0][0].startswith("leak-") for e in matched)
    assert not any("[ProjectMemory:" in l for l in lines)  # 沒提到別名 → 連目錄都不帶


def test_alias_brings_memory_md_directory_only(tmp_path, monkeypatch):
    other = _mk_other_project(tmp_path / "LineMate", alias="linemate")
    prompt = "LineMate 的 server 跟 client 怎麼發布"
    _matched, all_atoms, lines, alias_projs = _collect(
        tmp_path, monkeypatch, prompt, cross=[("c--linemate", other)])
    assert alias_projs == {"c--linemate"}
    block = next(l for l in lines if l.startswith("[ProjectMemory:c--linemate]"))
    assert "shared/leak-shared.md" in block
    assert "personal/" not in block and "roles/" not in block
    assert "| leak-shared |" not in block  # 表格列去掉
    # alias 只帶目錄，atom 本身仍不進池
    assert not any(e[0][0].startswith("leak-") for e in all_atoms)


def test_vector_layers_whitelist_even_for_management(tmp_path, monkeypatch):
    seen = {}

    def fake_sem(prompt, config, intent="general", user=None, roles=None,
                 session_id=None, layers=None):
        seen.update(user=user, roles=roles, layers=layers)
        return []

    mem_dir = tmp_path / "memory"
    mem_dir.mkdir(exist_ok=True)
    state = _base_state(mem_dir)
    state["atom_index"]["project_slug"] = "c--projects"
    _collect(tmp_path, monkeypatch, "完全無關的句子 nothing", state=state, sem=fake_sem)
    assert seen["user"] == "holylight" and seen["roles"] == ["programmer"]
    assert seen["layers"] == [
        "global", "shared:c--projects", "role:c--projects:programmer",
        "personal:c--projects:holylight",
    ]


def test_vector_hits_outside_pool_are_dropped(tmp_path, monkeypatch):
    """舊服務不認 layers 時仍安全：服務回了池外名字 → _merge_hit 找不到就丟。"""
    def fake_sem(*a, **k):
        return [("leak-shared", "c:/LineMate/.claude/memory/shared/leak-shared.md", [], [])]
    matched, _all, _lines, _ = _collect(tmp_path, monkeypatch, "完全無關 nothing", sem=fake_sem)
    assert not any(e[0][0] == "leak-shared" for e in matched)


def test_related_spread_confined_to_pool(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    (mem / "a.md").write_text("# a\n\n- Related: b, outsider\n\n## 知識\n- x\n", encoding="utf-8")
    (mem / "b.md").write_text("# b\n\n## 知識\n- y\n", encoding="utf-8")
    pool = [(("a", "memory/a.md", []), tmp_path), (("b", "memory/b.md", []), tmp_path)]
    got = spread_related({"a"}, pool, [], max_depth=2)
    assert [e[0][0] for e in got] == ["b"]  # outsider 不在池 → 不擴散、不解析檔案


def test_injection_log_records_scope(tmp_path):
    from handlers.ups_inject import assemble_injection

    mem = tmp_path / "memory" / "personal" / "holylight"
    mem.mkdir(parents=True)
    (mem / "mine.md").write_text(
        "# mine\n\n- Confidence: [臨]\n\n## 知識\n\n- 內容\n", encoding="utf-8")
    state = {"turn_seq": 1, "atom_index": {"scopes": {"mine": "personal:holylight"}}}
    lines: list = []
    newly, _dirs = assemble_injection(
        "sid", state, {},
        [(("mine", "memory/personal/holylight/mine.md", ["x"]), tmp_path)],
        [], [], {"mine": "trigger"}, {}, lines,
    )
    assert newly == ["mine"]
    assert state["injection_log"][0]["scope"] == "personal:holylight"


# ─── 守衛：跨專案 atom 迴圈不得回來 ───────────────────────────────────────────

def test_ups_search_has_no_cross_project_atom_scan():
    src = (HOOKS_DIR / "handlers" / "ups_search.py").read_text(encoding="utf-8")
    assert "parse_memory_index" not in src, "ups_search 不得再讀他專案的 atom 索引"
    assert "count_trigger_hits(triggers, prompt_lower) >= 2" not in src
