"""verify_personal_index.py — 根層私人卡的登記不進共用索引（lib/atom_index_json 的分流與疊回）。

做什麼：
- 寫入：根層 save 把 memory/personal/ 的列放進本機私人索引，共用索引與 _ATOM_INDEX.md 找不到卡名、觸發詞；專案層不分流。
- 讀取：load 看到完整一份；共用索引壞掉照舊回空（呼叫端靠它退回鏡像）；舊版機器推回來的列不重複。
- 搬移：這台剛升級（列還在共用索引）、別台 pull 掉舊列（卡在磁碟、沒有登記）都由 --split-personal 收斂，開場自動跑。
- 直接讀 JSON 的工具與 Node 儀表板看得到私人卡；本 repo 進版控的索引沒有私人列。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_personal_index.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "lib", ROOT / "hooks"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lib.atom_index_json import (  # noqa: E402
    delete_atom, find_index_dir, load_atom_index_json, load_personal_rows, personal_split_pending,
    regenerate_atom_index_md, upsert_atom,
)
from lib.sensitive_gate import is_secret_path  # noqa: E402

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
PUBLIC_PATH = "memory/x/pub.md"
SECRET = "secret-card"
SECRET_PATH = f"memory/personal/u/{SECRET}.md"
SECRET_TRIGGER = "秘密詞"
CARD_TEXT = (f"# {SECRET}\n\n- Scope: personal:u\n- Confidence: [臨]\n- Trigger: {SECRET_TRIGGER}, second\n\n"
             "## 知識\n\n- [臨] x\n\n## 行動\n\n- y\n")


@pytest.fixture
def mem(tmp_path, monkeypatch):
    """資料根指到 tmp 的根層 memory/。"""
    monkeypatch.setenv("WG_CLAUDE_DIR", str(tmp_path))
    d = tmp_path / "memory"
    d.mkdir()
    return d


def _shared_text(mem_dir: Path) -> str:
    return (mem_dir / "_atom_index.json").read_text(encoding="utf-8")


def _mirror_text(mem_dir: Path) -> str:
    return (mem_dir / "_ATOM_INDEX.md").read_text(encoding="utf-8")


def _personal_file(mem_dir: Path) -> Path:
    return mem_dir / "personal" / "_personal_index.json"


def _write_card(mem_dir: Path) -> Path:
    card = mem_dir / "personal" / "u" / f"{SECRET}.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text(CARD_TEXT, encoding="utf-8")
    return card


def _write_old_shared_index(mem_dir: Path, *paths: str) -> None:
    """照舊版的樣子落一份共用索引（私人列混在裡面、繞過 save）。"""
    atoms = [{"name": Path(p).stem, "path": p, "triggers": [Path(p).stem], "scope": "global"} for p in paths]
    (mem_dir / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": atoms}, ensure_ascii=False, indent=2),
                                              encoding="utf-8")


def _with_two_rows(mem_dir: Path) -> None:
    upsert_atom(mem_dir, "pub", PUBLIC_PATH, ["公開詞"], "global")
    upsert_atom(mem_dir, SECRET, SECRET_PATH, [SECRET_TRIGGER], "personal:u")


def _names(mem_dir: Path) -> list:
    return [a["name"] for a in load_atom_index_json(mem_dir)["atoms"]]


def test_personal_row_stays_out_of_shared_index_and_mirror(mem):
    _with_two_rows(mem)
    for text in (_shared_text(mem), _mirror_text(mem)):
        assert "pub" in text and SECRET not in text and SECRET_TRIGGER not in text
    assert SECRET_TRIGGER in _personal_file(mem).read_text(encoding="utf-8")
    assert _names(mem) == ["pub", SECRET]                      # 呼叫端看到的仍是完整一份
    regenerate_atom_index_md(mem)
    assert SECRET not in _mirror_text(mem)


def test_update_and_delete_personal_row_leave_shared_index_bytes_alone(mem):
    _with_two_rows(mem)
    before = _shared_text(mem), _mirror_text(mem)
    upsert_atom(mem, SECRET, SECRET_PATH, ["改過的詞"], "personal:u")
    assert load_personal_rows(mem)[0]["triggers"] == ["改過的詞"]
    assert delete_atom(mem, SECRET) is True
    assert (_shared_text(mem), _mirror_text(mem)) == before
    assert load_personal_rows(mem) == [] and _names(mem) == ["pub"]   # 刪到一筆不剩要寫空表，不然會被疊回來


def test_machine_without_personal_cards_gets_no_personal_file(mem):
    upsert_atom(mem, "pub", PUBLIC_PATH, ["公開詞"], "global")
    assert not (mem / "personal").exists()


def test_project_layer_keeps_personal_rows_inline(tmp_path, monkeypatch):
    """專案層的 personal 跟著專案 repo 走，不分流。"""
    monkeypatch.setenv("WG_CLAUDE_DIR", str(tmp_path / "data-root"))
    proj = tmp_path / "proj" / ".claude" / "memory"
    proj.mkdir(parents=True)
    _with_two_rows(proj)
    assert SECRET in _shared_text(proj) and SECRET in _mirror_text(proj)
    assert not _personal_file(proj).exists()
    assert personal_split_pending(proj) is False


def test_index_root_from_personal_card_is_still_memory(mem):
    """私人索引的檔名不能讓 find_index_dir 往上找時停在 personal/。"""
    _with_two_rows(mem)
    assert find_index_dir(_write_card(mem)).resolve() == mem.resolve()


def test_broken_shared_index_still_loads_empty_for_fallback(mem):
    """共用索引壞掉不疊私人列：parse_memory_index 靠條目為空退回 _ATOM_INDEX.md。"""
    _with_two_rows(mem)
    (mem / "_atom_index.json").write_text("<<<<<<< conflict", encoding="utf-8")
    assert load_atom_index_json(mem)["atoms"] == []


def test_row_pushed_back_by_old_machine_is_not_duplicated_and_gets_split(mem):
    _with_two_rows(mem)
    _write_old_shared_index(mem, PUBLIC_PATH, SECRET_PATH)
    assert _names(mem).count(SECRET) == 1
    assert personal_split_pending(mem) is True
    upsert_atom(mem, "another", "memory/x/another.md", ["別的"], "global")   # 任何一次寫入都會收乾淨
    assert SECRET not in _shared_text(mem) and personal_split_pending(mem) is False


@pytest.mark.parametrize("shared_has_row,card_on_disk,personal_file,want", [
    (True, True, False, True),     # 這台剛升級
    (False, True, False, True),    # pull 掉了舊列
    (False, True, True, False),    # 已分流
    (False, False, False, False),  # 沒有私人卡的機器
])
def test_split_pending_cases(mem, shared_has_row, card_on_disk, personal_file, want):
    _write_old_shared_index(mem, PUBLIC_PATH, *([SECRET_PATH] if shared_has_row else []))
    if card_on_disk:
        _write_card(mem)
    if personal_file:
        _personal_file(mem).parent.mkdir(parents=True, exist_ok=True)
        _personal_file(mem).write_text(json.dumps({"atoms": [{"name": SECRET, "path": SECRET_PATH}]}), encoding="utf-8")
    assert personal_split_pending(mem) is want


def test_split_pending_for_card_pulled_after_rows_exist(mem):
    """pull 來的新卡（含 secret/ 底下的）沒有登記要補；role.md、沒有 Trigger 的檔補不出來，不算。"""
    _with_two_rows(mem)
    assert personal_split_pending(mem) is False
    owner = mem / "personal" / "u"
    owner.mkdir(parents=True, exist_ok=True)
    (owner / "role.md").write_text("- Trigger: x\n", encoding="utf-8")
    (owner / "no-trigger.md").write_text("# 沒有觸發詞\n", encoding="utf-8")
    assert personal_split_pending(mem) is False
    (owner / "pulled-card.md").write_text(CARD_TEXT, encoding="utf-8")
    assert personal_split_pending(mem) is True
    (owner / "pulled-card.md").unlink()
    (owner / "secret").mkdir()
    (owner / "secret" / "pulled-key.md").write_text(CARD_TEXT, encoding="utf-8")
    assert personal_split_pending(mem) is True


def _run_split_tool(mem_dir: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "WG_CLAUDE_DIR": str(mem_dir.parent), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / "sync-atom-index.py"),
                           "--memory-dir", str(mem_dir), "--split-personal"], env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, creationflags=NO_WINDOW)


def test_split_tool_moves_rows_on_just_upgraded_machine(mem):
    _write_card(mem)
    _write_old_shared_index(mem, PUBLIC_PATH, SECRET_PATH)
    r = _run_split_tool(mem)
    assert SECRET not in _shared_text(mem) and SECRET not in _mirror_text(mem), r.stdout + r.stderr
    assert [a["name"] for a in load_personal_rows(mem)] == [SECRET]
    assert personal_split_pending(mem) is False


def test_split_tool_rebuilds_rows_from_card_after_pull_removed_them(mem):
    _write_card(mem)
    _write_old_shared_index(mem, PUBLIC_PATH)
    r = _run_split_tool(mem)
    rows = load_personal_rows(mem)
    assert [a["name"] for a in rows] == [SECRET], r.stdout + r.stderr
    assert rows[0]["path"] == SECRET_PATH and rows[0]["triggers"] == [SECRET_TRIGGER, "second"]
    assert rows[0]["scope"] == "personal:u"
    assert SECRET not in _shared_text(mem)


def test_session_start_splits_once_then_stays_quiet(mem, monkeypatch):
    from handlers import session_start as ss
    monkeypatch.setattr(ss, "_under_claude_dir", lambda p: True)
    _write_card(mem)
    _write_old_shared_index(mem, PUBLIC_PATH, SECRET_PATH)
    regenerate_atom_index_md(mem)
    assert "已更新到本機索引" in ss._rebuild_index_if_missing(mem)
    assert SECRET not in _shared_text(mem)
    assert ss._rebuild_index_if_missing(mem) == ""


def test_session_start_warns_when_split_did_not_happen(mem, monkeypatch, tmp_path):
    """工具不在、沒搬成 → 要出聲，不能靜默留著外流風險。"""
    from handlers import session_start as ss
    monkeypatch.setattr(ss, "CODE_DIR", tmp_path / "no-code-here")
    _write_card(mem)
    _write_old_shared_index(mem, PUBLIC_PATH, SECRET_PATH)
    assert "沒搬成" in ss._split_personal_if_pending(mem)


READER_PROBE = r"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("probe_tool_mod", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
sys.modules["probe_tool_mod"] = mod
spec.loader.exec_module(mod)
print("PROBE_JSON " + json.dumps([str(x) for x in getattr(mod, sys.argv[2])()], ensure_ascii=False))
"""


@pytest.mark.parametrize("tool,func", [("atom-date-lint.py", "indexed_atoms"), ("memory-effect-report.py", "_load_atoms")])
def test_tools_reading_json_directly_still_see_personal_cards(mem, tool, func):
    _with_two_rows(mem)
    _write_card(mem)
    (mem / "x").mkdir()
    (mem / "x" / "pub.md").write_text("# pub\n", encoding="utf-8")
    env = {**os.environ, "WG_CLAUDE_DIR": str(mem.parent), "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", READER_PROBE, str(ROOT / "tools" / tool), func], env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=NO_WINDOW)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("PROBE_JSON ")), "")
    assert SECRET in line and "pub" in line, r.stdout + r.stderr[-1500:]


def test_source_lookup_and_forget_find_personal_cards(mem):
    from lib.provenance import _locate_by_index
    import wg_atoms
    _with_two_rows(mem)
    card = _write_card(mem)
    assert _locate_by_index(SECRET, mem) == card
    entries, error = wg_atoms._forget_load_index_strict(mem)
    assert error is None and any(a["name"] == SECRET for a in entries)


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_dashboard_lists_personal_cards(mem):
    _with_two_rows(mem)
    _write_card(mem)
    script = ("const h = require(process.argv[1]);"
              "h.apiAtoms({}, {writeHead() {}, end(s) { console.log('PROBE_JSON ' + s); }});")
    env = {**os.environ, "WG_CLAUDE_DIR": str(mem.parent), "HOME": str(mem.parent), "USERPROFILE": str(mem.parent)}
    r = subprocess.run(["node", "-e", script, str(ROOT / "tools" / "workflow-guardian-mcp" / "lib" / "http-api.js")], env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=NO_WINDOW)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("PROBE_JSON ")), "")
    assert line and SECRET in line, r.stdout[-500:] + r.stderr[-1500:]


HEAL_PROBE = r"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("probe_atom_heal", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
sys.modules["probe_atom_heal"] = mod
spec.loader.exec_module(mod)
seen = {}
def record_candidates(name, content, bad_ref, candidates, backend):
    seen[name] = candidates
    return {"action": "needs_human", "target": None, "reason": ""}
mod._propose = record_candidates
atoms = mod.ahc.find_atoms(mod.ahc.MEMORY_ROOT)
for name in sys.argv[2:]:
    mod.heal_L2(name, {"broken_refs": [{"missing_ref": "gone"}]}, atoms, {}, False, "none")
print("PROBE_JSON " + json.dumps(seen, ensure_ascii=False))
"""


def test_atom_heal_never_offers_secret_card_to_other_cards(mem):
    """修一般卡的斷連結不提議接到 secret 卡（卡名會隨 repo 外流），一般個人卡照常能接；修 secret 卡時什麼都能接。"""
    _write_card(mem)
    key = mem / "personal" / "u" / "secret" / "key-card.md"
    key.parent.mkdir(parents=True)
    key.write_text(CARD_TEXT.replace(SECRET, "key-card"), encoding="utf-8")
    public = mem / "x" / "pub.md"
    public.parent.mkdir()
    public.write_text(CARD_TEXT.replace(SECRET, "pub").replace("personal:u", "global"), encoding="utf-8")
    env = {**os.environ, "WG_CLAUDE_DIR": str(mem.parent), "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", HEAL_PROBE, str(ROOT / "tools" / "atom-heal.py"), "pub", "key-card"],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                       creationflags=NO_WINDOW)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("PROBE_JSON ")), "")
    assert line, r.stdout + r.stderr[-1500:]
    seen = json.loads(line[len("PROBE_JSON "):])
    assert "pub" in seen["pub"] and SECRET in seen["pub"] and "key-card" not in seen["pub"]
    assert {"pub", SECRET, "key-card"} <= set(seen["key-card"])


def test_repo_shared_index_has_no_personal_rows():
    """本 repo 進版控的索引與鏡像不得有個人卡的列；也不得提到 secret 卡名：
    連結要寫在 secret 卡那邊，反向連結在記憶體算，本機效果一樣。"""
    shared = (ROOT / "memory" / "_atom_index.json").read_text(encoding="utf-8")
    mirror = (ROOT / "memory" / "_ATOM_INDEX.md").read_text(encoding="utf-8")
    assert '"path": "memory/personal/' not in shared and "| memory/personal/" not in mirror
    rows = [a for a in load_personal_rows(ROOT / "memory") if is_secret_path(a["path"])]
    named = [a["name"] for a in rows if a["name"] in shared or a["name"] in mirror]
    assert not named, named
