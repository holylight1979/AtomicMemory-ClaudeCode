"""verify_depends_recall.py：Q3 路徑→卡片召回（A3.4／A3.5）：recall 1.0、誤報 0。

fixture hooks/verify/fixtures/v6/q3/：三張卡（path 指檔、path 指目錄、無 Depends）＋ expected.json 四案
（讀到 path: 指的檔 → 一行指標；目錄前綴命中；`src/x` 不中 `src/xy.cs`；無關檔零注入）。
另驗：同卡一 session 只提一次（depends_hints）、authority_map 對文件檔一次性注入、
atoms_depending_on 的專案相對解析（base＝專案根）與根層解析（base＝~/.claude）、post_tool_use 接線在 hub 呼叫之後。
live 檔全 monkeypatch（MEMORY_DIR／CLAUDE_DIR／LOG_PATH／公司根）。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_depends_recall.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_depends as wd  # noqa: E402
import wg_overview as wo  # noqa: E402
from atom_index_json import upsert_atom  # noqa: E402
from atom_spec import atoms_depending_on, depends_base_for, resolve_depends_path  # noqa: E402

FIX = HOOKS_DIR / "verify" / "fixtures" / "v6" / "q3"
EXPECTED = json.loads((FIX / "expected.json").read_text(encoding="utf-8"))


def _depends_of(text: str):
    for line in text.splitlines():
        if line.startswith("- Depends:"):
            return [t.strip() for t in line.split(":", 1)[1].split(",") if t.strip()]
    return None


@pytest.fixture
def world(tmp_path, monkeypatch):
    """假專案：<root>/.claude/memory/shared/排程/<卡>.md 進索引（depends 從 frontmatter 來）；全域索引指到空的 tmp。"""
    root = tmp_path / "proj"
    mem = root / ".claude" / "memory"
    cat = mem / "shared" / "排程"
    cat.mkdir(parents=True)
    for card in (FIX / "cards").glob("*.md"):
        text = card.read_text(encoding="utf-8")
        (cat / card.name).write_text(text, encoding="utf-8")
        upsert_atom(mem, card.stem, f"memory/shared/排程/{card.name}", ["t1"], "shared", depends=_depends_of(text))
    for rel in ("src/sched/queue.py", "src/sched/legacy/old.py", "src/sched/legacyx.py", "README.md", "docs/計畫.md"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    (root / "_AIDocs").mkdir()
    shutil.copy(FIX / "MAP.md", root / "_AIDocs" / "MAP.md")
    (root / ".git").mkdir()
    fake_claude = tmp_path / "claude"
    (fake_claude / "memory").mkdir(parents=True)
    monkeypatch.setattr(wd, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(wd, "MEMORY_DIR", fake_claude / "memory")
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    state = {"atom_index": {"project_memory_dir": str(mem), "project_root": str(root)}}
    return root, mem, state


def _cards_in(text):
    return [seg.split("`")[1] for seg in (text or "").split("\n") if seg.startswith("[Guardian:Depends]")]


def test_q3_four_cases_recall_one_false_positive_zero(world):
    root, mem, state = world
    expected_total = hit = fp = 0
    for case in EXPECTED["cases"]:
        st = dict(state)                      # 每案獨立 state，不受去重影響
        txt = wd.on_read_depends(st, "s", "Read", {"file_path": str(root / case["read"])}, str(root), {})
        got = _cards_in(txt)
        expected_total += len(case["expect"])
        hit += len(set(got) & set(case["expect"]))
        fp += len(set(got) - set(case["expect"]))
        if not case["expect"]:
            assert txt is None, (case["name"], txt)
        else:
            assert len(got) == len(case["expect"]) and all(l.count("[Guardian:Depends]") == 1 for l in txt.split("\n")), (case["name"], txt)
            assert str(mem / "shared" / "排程" / f"{case['expect'][0]}.md") in txt   # 一行一卡：卡名＋路徑
    assert expected_total and hit / expected_total == 1.0, (hit, expected_total)
    assert fp == 0


def test_same_card_hinted_once_per_session_and_log(world, tmp_path):
    root, mem, state = world
    f = str(root / "src" / "sched" / "queue.py")
    assert _cards_in(wd.on_read_depends(state, "s", "Read", {"file_path": f}, str(root), {})) == ["排程佇列卡"]
    assert wd.on_read_depends(state, "s", "Read", {"file_path": f}, str(root), {}) is None
    assert wd.on_read_depends(state, "s", "Bash", {"command": f'cat "{f}"'}, str(root), {}) is None
    assert state["depends_hints"] == ["排程佇列卡"]
    # 另一張卡的檔仍會提
    assert _cards_in(wd.on_read_depends(state, "s", "Read", {"file_path": str(root / "src/sched/legacy/old.py")}, str(root), {})) == ["舊排程卡"]
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert [e["event"] for e in log] == ["depends_hint", "depends_hint"] and log[0]["card"] == "排程佇列卡"


def test_authority_map_injected_once_for_doc_files_only(world):
    root, mem, state = world
    (root / ".claude" / "overview-hub.json").write_text(json.dumps({"authority_map": EXPECTED["authority_map"]}), encoding="utf-8")
    # 非文件檔不注入地圖
    txt = wd.on_read_depends(state, "s", "Read", {"file_path": str(root / "src/sched/queue.py")}, str(root), {})
    assert "[Guardian:AuthorityMap]" not in (txt or "")
    txt = wd.on_read_depends(state, "s", "Read", {"file_path": str(root / EXPECTED["doc_read"])}, str(root), {})
    assert txt and "[Guardian:AuthorityMap]" in txt and "權威地圖（fixture）" in txt and state["authority_map_injected"] is True
    assert wd.on_read_depends(state, "s", "Read", {"file_path": str(root / "README.md")}, str(root), {}) is None   # 一次性
    # authority_map 空 → 不注入
    (root / ".claude" / "overview-hub.json").write_text("{}", encoding="utf-8")
    st = dict(state)
    st.pop("authority_map_injected")
    assert wd.on_read_depends(st, "s", "Read", {"file_path": str(root / EXPECTED["doc_read"])}, str(root), {}) is None


def test_authority_map_dotdot_does_not_escape_pattern(world):            # 退件 BLOCK 3
    root, mem, state = world
    (root / ".claude" / "overview-hub.json").write_text(json.dumps({"authority_map": {"docs/*.md": "_AIDocs/MAP.md"}}), encoding="utf-8")
    (root / "src" / "a.md").write_text("x", encoding="utf-8")
    cfg = wo._cfg({}, root)
    assert wd._authority_map_for(str(root / "docs" / ".." / "src" / "a.md"), cfg, root) is None
    assert wd._authority_map_for(str(root / "docs" / "計畫.md"), cfg, root) is not None
    assert wd._authority_map_for(str(root / "src" / ".." / "docs" / "計畫.md"), cfg, root) is not None
    st = dict(state)
    assert wd.on_read_depends(st, "s", "Read", {"file_path": str(root / "docs" / ".." / "src" / "a.md")}, str(root), {}) is None


def test_norm_fs_path_strips_extended_prefix(tmp_path):                  # 退件 WARN（\\?\ 前綴）
    from atom_spec import _norm_fs_path
    plain = _norm_fs_path(tmp_path / "x.py")
    assert _norm_fs_path(Path("\\\\?\\" + str(tmp_path / "x.py"))) == plain
    assert "?" not in plain


def test_atoms_depending_on_bases_project_vs_root(tmp_path):
    root = tmp_path / "p"
    mem = root / ".claude" / "memory"
    mem.mkdir(parents=True)
    upsert_atom(mem, "c", "memory/shared/x/c.md", ["t"], "shared", depends=["path:src/x", "decision:q", "path:"])
    assert depends_base_for(mem) == root
    assert resolve_depends_path("src/x", base=root) == root / "src" / "x"
    assert resolve_depends_path("src/x", claude_dir=tmp_path / "c") == tmp_path / "c" / "src" / "x"   # 舊簽名不變
    hits = atoms_depending_on(root / "src" / "x" / "a.cs", [mem])
    assert [h["name"] for h in hits] == ["c"] and hits[0]["dep"] == "path:src/x"
    assert atoms_depending_on(root / "src" / "xy.cs", [mem]) == []
    assert atoms_depending_on(root / "src" / "x", [(mem, root)])[0]["name"] == "c"
    # 明給根（根層卡以 ~/.claude 解析）：同一相對路徑換根就不中
    assert atoms_depending_on(root / "src" / "x" / "a.cs", [(mem, tmp_path / "elsewhere")]) == []
    # 索引不存在 → 空、不炸
    assert atoms_depending_on(root / "src" / "x" / "a.cs", [tmp_path / "nope"]) == []


def test_post_tool_use_calls_depends_after_hub():
    src = (HOOKS_DIR / "handlers" / "post_tool_use.py").read_text(encoding="utf-8")
    assert src.index("_hub_on_read(") < src.index("on_read_depends(") < src.index("advisories.append(dep_ctx)")
    assert src.index("advisories.append(hub_ctx)") < src.index("advisories.append(dep_ctx)")   # hub 文字先、召回後
    # 缺口 5：所有讀檔分支（條件含 "Read" 的 `if tool_name in (...)`：導讀卡、需求目標讀入範圍、Depends 召回…）都收 Bash 與
    # PowerShell；不數分支個數（新增讀檔分支不該讓這條紅），只驗每一支的行為。有的另收 Grep（045 規則 GREP_CONTENT_IS_READ），
    # 所以比的是條件裡有哪些工具，不比整行字面
    import re
    read_branches = [m.group(1) for m in re.finditer(r'if tool_name in \(([^)]*)\):', src) if '"Read"' in m.group(1)]
    assert read_branches, "post_tool_use.py 找不到讀檔分支"
    missing = [b for b in read_branches if not all(f'"{t}"' in b for t in ("Bash", "PowerShell"))]
    assert not missing, f"這些讀檔分支沒收 Bash／PowerShell：{missing}"


def test_powershell_and_bare_bash_reads_trigger_recall(world):
    """缺口 5：PowerShell 讀檔、Bash 無斜線相對路徑也觸發 Depends 召回；含變數的路徑不收。"""
    root, mem, state = world
    txt = wd.on_read_depends(dict(state), "s", "PowerShell", {"command": "Get-Content src/sched/queue.py -TotalCount 5"}, str(root), {})
    assert _cards_in(txt) == ["排程佇列卡"] and txt.count("\n") == 0                         # 一行指標
    txt = wd.on_read_depends(dict(state), "s", "Bash", {"command": "cat queue.py"}, str(root / "src" / "sched"), {})
    assert _cards_in(txt) == ["排程佇列卡"]
    assert wd.on_read_depends(dict(state), "s", "PowerShell", {"command": "Get-Content $p"}, str(root), {}) is None
    assert wd.on_read_depends(dict(state), "s", "Bash", {"command": "cat nothere.py"}, str(root / "src" / "sched"), {}) is None
