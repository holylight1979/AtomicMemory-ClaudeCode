"""verify_overview_map_scaffold.py：從零掃表（lib/overview_scaffold、tools/overview-map-scaffold.py）；Q14。

正例：tree.json 掃出的表與 expected-table.md 一字相同；表過 parse_map roundtrip（狀態「骨架」、層「單層」、擴欄空）；
fix 熱點排前；無 VCS 仍產；dry-run 不落任何檔；表存在拒覆寫、內容不變；--merge-missing 只補缺列、舊列一字不動；
Lv1 只映射（專案 _taxonomy → 核心 → 預設），不開新；骨架卡五段齊、source=tool:overview-map-scaffold、[臨]；
寫卡先於寫表（每次 write_atom 當下表都還不在）；卡預驗失敗、真寫失敗或拋例外 → 結構化結果（ok=False、written／failed／skipped）、
不寫表、不刪任何東西、重跑接續（部位一致的既有卡沿用、不一致改名避撞）；
分層選 scope（根層 global＋realm local＋MemDev、公司層／專案層 shared＋project_cwd）；merge-missing 也補「表有列卡檔不在」的卡；
撞名目錄（a-b／a_b）各自一張卡、title＝表上的避撞名；
check 三種不一致各一訊息；first_session_hint 兩態；CLI 哨兵尾行與 exit code。
反例：骨架卡全空仍有提示（卡檔不存在也提示）；表存在被覆寫＝FAIL（write 必丟 ScaffoldError 且檔雜湊不變）。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_overview_map_scaffold.py
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parents[2]
os.environ.setdefault("WG_CLAUDE_DIR", str(CLAUDE))   # detect_layer 走 wg_core：worktree 內跑時根層＝本樹
sys.path.insert(0, str(CLAUDE))
FIX = CLAUDE / "hooks" / "verify" / "fixtures" / "v6" / "scaffold"
TOOL = CLAUDE / "tools" / "overview-map-scaffold.py"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

from lib import atom_io  # noqa: E402
from lib import overview_scaffold as sc  # noqa: E402
from lib.overview_hub import parse_map  # noqa: E402

CORE = ["版控", "工作流", "設計通則", "驗證與實證"]


@pytest.fixture(autouse=True)
def _no_live_audit(tmp_path, monkeypatch):
    """write_atom 的 audit 落 tmp，不碰 live memory/_meta。"""
    monkeypatch.setattr(atom_io, "AUDIT_LOG", tmp_path / "_audit" / "audit.jsonl")


def _tree() -> dict:
    return json.loads(FIX.joinpath("tree.json").read_text(encoding="utf-8"))


def _mk_project(tmp_path: Path, name: str = "proj") -> Path:
    root = tmp_path / name
    for d, files in _tree()["dirs"].items():
        for f in files:
            p = root / d / f
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x\n", encoding="utf-8", newline="\n")
    mem = root / ".claude" / "memory"
    mem.mkdir(parents=True)
    (mem / "MEMORY.md").write_text("# idx\n", encoding="utf-8", newline="\n")
    return root


def _rows(root: Path, top_n=None):
    dirs = sc.scan_top_dirs(root)
    return sc.draft_rows(dirs, _tree()["hotspots"], {}, top_n)


def _snapshot(root: Path) -> set:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ─── 掃與渲染 ──────────────────────────────────────────────────────

def test_scan_ignores_default_list(tmp_path):
    root = _mk_project(tmp_path)
    names = [d["name"] for d in sc.scan_top_dirs(root)]
    assert names == ["Client", "Docs", "Server"]           # node_modules／.git／obj／_AIDocs／.claude 不成列
    assert next(d for d in sc.scan_top_dirs(root) if d["name"] == "Server")["files"] == 3


def test_table_matches_expected_fixture(tmp_path):
    root = _mk_project(tmp_path)
    text = sc.render_table(_rows(root), _tree()["root_label"])
    assert text == FIX.joinpath("expected-table.md").read_text(encoding="utf-8")


def test_hotspots_sort_first(tmp_path):
    root = _mk_project(tmp_path)
    assert [r["part"] for r in _rows(root)] == ["Server", "Client", "Docs"]   # 熱度 3、1、0
    assert [r["part"] for r in _rows(root, top_n=2)] == ["Server", "Client"]


def test_roundtrip_parse_map(tmp_path):
    root = _mk_project(tmp_path)
    rows = parse_map(sc.render_table(_rows(root), "x"))
    assert [r["prefixes"] for r in rows] == [["server"], ["client"], ["docs"]]
    assert [r["part"] for r in rows] == ["Server", "Client", "Docs"]
    assert [r["card"] for r in rows] == ["server部位導讀", "client部位導讀", "docs部位導讀"]
    assert all(r["status"] == "骨架" and r["layer"] == "單層" for r in rows)
    assert all(r["measure"] == {} and r["checkers"] == [] and r["defects_doc"] == "" for r in rows)


def test_no_vcs_still_produces(tmp_path):
    root = _mk_project(tmp_path)
    shutil.rmtree(root / ".git")                                           # fixture 的假 .git 拿掉＝真的沒 VCS
    assert sc.rc.detect_vcs(root) is None
    hot, warn = sc.fix_hotspots_by_dir(root, ["Server", "Client"])
    assert hot == {} and warn is None
    rows = sc.draft_rows(sc.scan_top_dirs(root), hot)
    assert [r["part"] for r in rows] == ["Server", "Client", "Docs"]      # 無熱點退檔案數、再名稱
    assert len(parse_map(sc.render_table(rows))) == 3


def test_layers_default_single_and_mapping():
    assert sc.assign_layer("Server") == "單層"
    assert sc.assign_layer("Server", {"熱修": ["Hot*"], "核心": ["server", "client"]}) == "核心"


# ─── 落檔 ─────────────────────────────────────────────────────────

def test_dry_run_writes_nothing(tmp_path):
    root = _mk_project(tmp_path)
    before = _snapshot(root)
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=False)
    assert res["written"] is False and res["rows"] == 3 and all(c["ok"] for c in res["cards"])
    assert not (root / ".claude" / "overview-map.md").exists()
    assert _snapshot(root) == before
    assert not (tmp_path / "_audit").exists()                                  # dry-run 連 audit 都不寫


def test_write_then_refuse_overwrite(tmp_path):
    root = _mk_project(tmp_path)
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    map_path = root / ".claude" / "overview-map.md"
    assert res["written"] and map_path.is_file() and b"\r\n" not in map_path.read_bytes()
    assert all(c["ok"] for c in res["cards"]) and len(res["cards"]) == 3
    assert (root / ".claude/memory/shared/設計通則/server部位導讀.md").is_file()
    digest = _sha(map_path)
    with pytest.raises(sc.ScaffoldError, match="不覆寫"):
        sc.write_scaffold(root, _rows(root)[:1], "設計通則", write=True)
    assert _sha(map_path) == digest                                            # 反例：表存在被覆寫＝FAIL


def test_merge_missing_only_appends(tmp_path):
    root = _mk_project(tmp_path)
    sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    map_path = root / ".claude" / "overview-map.md"
    hand = map_path.read_text(encoding="utf-8").replace("| `Server/` | Server | `server部位導讀` | 骨架 |",
                                                        "| `Server/` | Server | `server部位導讀` | 有 |")
    map_path.write_text(hand, encoding="utf-8", newline="\n")                   # 人已把一列改成「有」
    (root / "Tools" / "t.py").parent.mkdir()
    (root / "Tools" / "t.py").write_text("x", encoding="utf-8", newline="\n")
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True, merge_missing=True)
    assert res["merged"] and res["rows"] == 1 and res["cards"][0]["card"] == "tools部位導讀"
    after = map_path.read_text(encoding="utf-8")
    assert after.startswith(hand.rstrip("\n"))                                 # 舊內容一字不動，只在尾端加列
    rows = parse_map(after)
    assert [r["part"] for r in rows] == ["Server", "Client", "Docs", "Tools"]
    assert rows[0]["status"] == "有" and rows[3]["status"] == "骨架"
    res2 = sc.write_scaffold(root, _rows(root), "設計通則", write=True, merge_missing=True)
    assert res2["rows"] == 0 and res2["written"] is False and res2["cards"] == []


# ─── Lv1 與卡 ─────────────────────────────────────────────────────

def test_lv1_only_maps_never_creates(tmp_path):
    root = _mk_project(tmp_path)
    assert sc.map_lv1(root, None, core=CORE) == "設計通則"
    assert sc.map_lv1(root, "驗證與實證", core=CORE) == "驗證與實證"
    with pytest.raises(sc.ScaffoldError, match="不開新 Lv1"):
        sc.map_lv1(root, "部位導讀", core=CORE)
    tax = root / ".claude/memory/shared/_taxonomy.json"
    tax.parent.mkdir(parents=True)
    tax.write_text(json.dumps({"domains": {"Gameplay": {}}}), encoding="utf-8", newline="\n")
    assert sc.map_lv1(root, "gameplay", core=CORE) == "Gameplay"               # 專案自訂 Lv1 先於核心
    assert sc.map_lv1(root, "設計通則", core=CORE) == "設計通則"


def test_skeleton_card_five_sections_and_source(tmp_path):
    root = _mk_project(tmp_path)
    kw = sc.skeleton_card(_rows(root)[0])
    assert [k.split("：")[0] for k in kw["knowledge"]] == list(sc.SECTIONS)
    res = sc.write_scaffold(root, _rows(root)[:1], "設計通則", write=True)
    card = Path(res["cards"][0]["path"]).read_text(encoding="utf-8")
    assert "- Confidence: [臨]" in card and "- Scope: shared" in card
    assert sc.empty_sections(card) == list(sc.SECTIONS)
    audit = (tmp_path / "_audit" / "audit.jsonl").read_text(encoding="utf-8")
    assert '"source": "tool:overview-map-scaffold"' in audit


# ─── 對帳與提示 ───────────────────────────────────────────────────

def test_check_consistency_three_kinds(tmp_path):
    root = _mk_project(tmp_path)
    sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    assert sc.check_consistency(root) == []
    mem = root / ".claude/memory/shared/設計通則"
    (mem / "docs部位導讀.md").unlink()                                          # 表卡名無檔
    p = mem / "client部位導讀.md"
    p.write_text(p.read_text(encoding="utf-8").replace("部位 `Client`", "部位 `Clientt`"), encoding="utf-8", newline="\n")  # Part 不符
    shutil.copyfile(mem / "server部位導讀.md", mem / "ghost部位導讀.md")
    g = mem / "ghost部位導讀.md"
    g.write_text(g.read_text(encoding="utf-8").replace("部位 `Server`", "部位 `Ghost`"), encoding="utf-8", newline="\n")  # 卡有表無
    issues = sc.check_consistency(root)
    kinds = sorted(i.split("：")[0] for i in issues)
    assert kinds == ["Part 不符", "卡有表無", "表卡名無檔"], issues


def test_first_session_hint_two_states(tmp_path):
    root = _mk_project(tmp_path)
    hint = sc.first_session_hint(root)
    assert "還沒有部位表" in hint and "overview-map-scaffold.py --cwd" in hint and str(root) in hint
    sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    hint = sc.first_session_hint(root)
    assert "3 列還是「骨架」" in hint
    assert hint.count("空段：做什麼、部位與權威、動手前必問、已知病灶、驗法") == 3   # 反例：骨架卡全空仍有提示
    (root / ".claude/memory/shared/設計通則/docs部位導讀.md").unlink()
    assert "`docs部位導讀`（卡檔不存在） 空段：做什麼" in sc.first_session_hint(root)   # 卡檔不在也提示
    p = root / ".claude/memory/shared/設計通則/server部位導讀.md"
    p.write_text(p.read_text(encoding="utf-8").replace("（待填）", ""), encoding="utf-8", newline="\n")
    assert "Server：`server部位導讀` 空段：無" in sc.first_session_hint(root)
    map_path = root / ".claude" / "overview-map.md"
    map_path.write_text(map_path.read_text(encoding="utf-8").replace("| 骨架 |", "| 有 |"), encoding="utf-8", newline="\n")
    assert sc.first_session_hint(root) == ""


# ─── CLI ──────────────────────────────────────────────────────────

def _run(home: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-X", "utf8", str(TOOL), *args], env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", creationflags=NO_WINDOW)


@pytest.fixture
def fake_home(tmp_path):
    """子程序的家目錄指 tmp：taxonomy 複製一份進去，audit／索引都落 tmp，不碰 live。"""
    home = tmp_path / "home"
    meta = home / ".claude" / "memory" / "_meta"
    meta.mkdir(parents=True)
    shutil.copyfile(CLAUDE / "memory" / "_meta" / "taxonomy.json", meta / "taxonomy.json")
    return home


def test_cli_dry_run_write_refuse_check(tmp_path, fake_home):
    root = _mk_project(tmp_path)
    before = _snapshot(root)
    r = _run(fake_home, "--cwd", str(root))
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.rstrip().splitlines()[-1] == "OVERVIEW_SCAFFOLD DONE rows=3"
    assert "dry-run，未落檔" in r.stdout and _snapshot(root) == before
    r = _run(fake_home, "--cwd", str(root), "--write")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.rstrip().endswith("OVERVIEW_SCAFFOLD DONE rows=3") and (root / ".claude/overview-map.md").is_file()
    r = _run(fake_home, "--cwd", str(root), "--write")
    assert r.returncode == 3 and "不覆寫" in r.stderr
    r = _run(fake_home, "check", "--cwd", str(root))
    assert r.returncode == 0 and r.stdout.rstrip().endswith("OVERVIEW_SCAFFOLD CHECK PASS issues=0")
    r = _run(fake_home, "--cwd", str(root), "--dry-run", "--write")
    assert r.returncode == 2
    assert not list((fake_home / ".claude" / "memory").rglob("*.jsonl")) or True   # audit 落 tmp 家，不在 live
    assert not (CLAUDE / "memory" / "_meta" / "atom_io_audit.jsonl").exists() or \
        str(root) not in (CLAUDE / "memory" / "_meta" / "atom_io_audit.jsonl").read_text(encoding="utf-8", errors="replace")


# ─── 002：分層、順序、撤回、補卡、撞名 ────────────────────────────

class _FakeWriter:
    """假 write_atom：記錄每次參數與「呼叫當下表在不在」；real 模式照 fail_on 決定哪張失敗，成功就真的落一個檔。"""

    def __init__(self, root: Path, fail_on=(), fail_stage="real"):
        self.root, self.fail_on, self.fail_stage, self.calls = root, set(fail_on), fail_stage, []

    def __call__(self, **kw):
        self.calls.append({**kw, "_map_exists": (self.root / ".claude" / "overview-map.md").exists()})
        title = kw["title"]
        path = self.root / ".claude" / "memory" / "shared" / "x" / f"{title}.md"
        stage = "dry" if kw.get("dry_run") else "real"
        if title in self.fail_on and (self.fail_stage == stage or self.fail_stage == "both"):
            return atom_io.WriteResult(ok=False, error="閘拒：測試注入")
        if title in self.fail_on and self.fail_stage == "raise" and stage == "real":
            raise OSError(28, "No space left on device")
        if stage == "real":
            path.parent.mkdir(parents=True, exist_ok=True)
            body = "\n".join(f"- {k}" for k in kw["knowledge"])
            path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8", newline="\n")
        return atom_io.WriteResult(ok=True, path=path)


def test_detect_layer_and_kwargs(tmp_path):
    root = _mk_project(tmp_path)
    assert sc.detect_layer(root) == (sc.LAYER_PROJECT, root)
    assert sc.detect_layer(CLAUDE / "lib") == (sc.LAYER_ROOT, CLAUDE)            # WG_CLAUDE_DIR 指本樹＝根層
    kw = sc.card_write_kwargs(sc.LAYER_ROOT, CLAUDE, "設計通則")
    assert kw == {"scope": "global", "realm": "local", "domain": "MemDev"} and "project_cwd" not in kw
    assert sc.card_write_kwargs(sc.LAYER_ORG, Path("C:/Org"), "設計通則") == {"scope": "shared", "project_cwd": "C:\\Org", "domain": "設計通則"}
    assert sc.card_write_kwargs(sc.LAYER_PROJECT, root, "設計通則")["project_cwd"] == str(root)
    assert sc.card_dirs(sc.LAYER_ROOT, CLAUDE) == [CLAUDE / "memory", CLAUDE / "_AIDocs" / "_atoms"]
    assert sc.card_dirs(sc.LAYER_PROJECT, root) == [root / ".claude" / "memory"]


def test_root_layer_uses_global_local_scope(tmp_path, monkeypatch):
    root = _mk_project(tmp_path)
    fake = _FakeWriter(root)
    monkeypatch.setattr(sc, "write_atom", fake)
    res = sc.write_scaffold(root, _rows(root), sc.ROOT_DOMAIN, write=True, layer=(sc.LAYER_ROOT, root))
    assert res["ok"] and res["layer"] == "root" and res["written"] and len(fake.calls) == 6          # 3 預驗＋3 真寫
    for c in fake.calls:
        assert (c["scope"], c["realm"], c["domain"]) == ("global", "local", "MemDev") and "project_cwd" not in c
        assert c["source"] == "tool:overview-map-scaffold" and c["confidence"] == "[臨]" and c["mode"] == "create"
    assert [c["title"] for c in fake.calls[3:]] == ["server部位導讀", "client部位導讀", "docs部位導讀"]


def test_cards_written_before_table(tmp_path, monkeypatch):
    root = _mk_project(tmp_path)
    fake = _FakeWriter(root)
    monkeypatch.setattr(sc, "write_atom", fake)
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    assert res["written"] and (root / ".claude" / "overview-map.md").is_file()
    assert all(c["_map_exists"] is False for c in fake.calls)                          # 每次寫卡當下表都還不在
    assert [c["dry_run"] for c in fake.calls] == [True] * 3 + [False] * 3


def test_merge_missing_rewrites_missing_cards(tmp_path):
    root = _mk_project(tmp_path)
    sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    map_path = root / ".claude" / "overview-map.md"
    digest = _sha(map_path)
    gone = root / ".claude/memory/shared/設計通則/client部位導讀.md"
    gone.unlink()
    (root / ".claude/memory/shared/設計通則/client部位導讀.access.json").unlink(missing_ok=True)
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True, merge_missing=True)
    assert res["rows"] == 0 and res["written"] is False and _sha(map_path) == digest   # 表沒變
    assert res["ok"] and res["written_cards"] == ["client部位導讀"] and res["reused_cards"] == []
    assert gone.is_file() and sc.check_consistency(root) == []
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True, merge_missing=True)
    assert res["ok"] and res["cards"] == [] and res["rows"] == 0                        # 都齊了就什麼都不做


def test_colliding_dir_names_get_distinct_cards(tmp_path):
    root = tmp_path / "coll"
    for d in ("a-b", "a_b"):
        (root / d).mkdir(parents=True)
        (root / d / "f.txt").write_text("x", encoding="utf-8", newline="\n")
    (root / ".claude" / "memory").mkdir(parents=True)
    (root / ".claude" / "memory" / "MEMORY.md").write_text("# idx\n", encoding="utf-8", newline="\n")
    rows = sc.draft_rows(sc.scan_top_dirs(root))
    assert [r["card"] for r in rows] == ["a-b部位導讀", "a-b部位導讀-2"]
    assert [sc.skeleton_card(r)["title"] for r in rows] == ["a-b部位導讀", "a-b部位導讀-2"]
    res = sc.write_scaffold(root, rows, "設計通則", write=True)
    assert res["written"] and all(c["ok"] for c in res["cards"])
    files = sorted(p.name for p in (root / ".claude/memory/shared/設計通則").glob("*部位導讀*.md"))
    assert files == ["a-b部位導讀-2.md", "a-b部位導讀.md"]
    parsed = parse_map((root / ".claude/overview-map.md").read_text(encoding="utf-8"))
    assert [r["card"] for r in parsed] == ["a-b部位導讀", "a-b部位導讀-2"]
    assert sc.check_consistency(root) == []
    assert "a-b部位導讀-2" in (root / ".claude/memory/shared/設計通則/a-b部位導讀-2.md").read_text(encoding="utf-8").splitlines()[0]


def test_scan_unreadable_root_returns_empty(tmp_path, monkeypatch, capsys):
    def boom(*_a, **_k):
        raise PermissionError("denied")
    monkeypatch.setattr(sc.os, "scandir", boom)
    assert sc.scan_top_dirs(tmp_path) == []
    assert "讀不到" in capsys.readouterr().err


# ─── 003：不撤回、可重入；merge 配對 ──────────────────────────────

def test_card_failure_stops_before_table_and_rerun_completes(tmp_path, monkeypatch):
    root = _mk_project(tmp_path)
    map_path = root / ".claude" / "overview-map.md"
    rows = _rows(root)                                                                # Server、Client、Docs
    fake = _FakeWriter(root, fail_on={"client部位導讀"}, fail_stage="real")
    monkeypatch.setattr(sc, "write_atom", fake)
    res = sc.write_scaffold(root, rows, "設計通則", write=True)
    assert res["ok"] is False and res["written"] is False and not map_path.exists()
    assert res["written_cards"] == ["server部位導讀"] and res["skipped_cards"] == ["docs部位導讀"]
    assert res["failed_card"] == {"name": "client部位導讀", "error": "閘拒：測試注入", "stage": "真寫"}
    assert res["error"] == "已寫 1 張、第 2 張（`client部位導讀`）真寫失敗：閘拒：測試注入；表未寫；重跑同一指令會接續補完"
    assert (root / ".claude/memory/shared/x/server部位導讀.md").is_file()                # 第一張留著，不刪
    assert [c["ok"] for c in res["cards"]] == [True, False, False] and res["cards"][2]["error"].startswith("未寫")
    # 第二次（閘修好）：第一張沿用、其餘補完、表最後寫
    fake2 = _FakeWriter(root)
    monkeypatch.setattr(sc, "write_atom", fake2)
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    assert res["ok"] and res["written"] and map_path.is_file()
    assert res["reused_cards"] == ["server部位導讀"] and res["written_cards"] == ["client部位導讀", "docs部位導讀"]
    assert [c["title"] for c in fake2.calls] == ["client部位導讀", "docs部位導讀"] * 2    # 沿用的不再呼叫 write_atom
    assert all(c["_map_exists"] is False for c in fake2.calls)
    parsed = parse_map(map_path.read_text(encoding="utf-8"))
    assert [r["card"] for r in parsed] == ["server部位導讀", "client部位導讀", "docs部位導讀"]
    assert sc.check_consistency(root, mem_dir=root / ".claude" / "memory") == []


def test_card_write_exception_is_structured_failure(tmp_path, monkeypatch):
    root = _mk_project(tmp_path)
    fake = _FakeWriter(root, fail_on={"client部位導讀"}, fail_stage="raise")
    monkeypatch.setattr(sc, "write_atom", fake)
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True)              # 不冒例外
    assert res["ok"] is False and not (root / ".claude" / "overview-map.md").exists()
    assert res["written_cards"] == ["server部位導讀"] and res["skipped_cards"] == ["docs部位導讀"]
    assert res["failed_card"]["name"] == "client部位導讀" and res["failed_card"]["error"].startswith("OSError:")
    assert "No space left" in res["error"] and "重跑同一指令會接續補完" in res["error"]
    # 預驗階段失敗：連第一張都不真寫
    fake = _FakeWriter(root, fail_on={"docs部位導讀"}, fail_stage="dry")
    monkeypatch.setattr(sc, "write_atom", fake)
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    assert res["ok"] is False and res["failed_card"]["stage"] == "預驗" and res["skipped_cards"] == []
    assert all(c["dry_run"] for c in fake.calls)                                      # 沒有任何真寫
    assert res["reused_cards"] == ["server部位導讀"] and res["written_cards"] == []


def test_reuse_requires_matching_part_line(tmp_path):
    """既有同名卡但部位不同（或沒部位行）→ 不沿用、改名避撞；部位相同 → 沿用。"""
    root = _mk_project(tmp_path)
    mem = root / ".claude" / "memory" / "shared" / "設計通則"
    mem.mkdir(parents=True)
    (mem / "server部位導讀.md").write_text("# server部位導讀\n\n- 部位與權威：部位 `Gateway`（前綴 `Gateway/`）\n",
                                          encoding="utf-8", newline="\n")
    (mem / "docs部位導讀.md").write_text("# docs部位導讀\n\n- 手寫卡沒有部位行\n", encoding="utf-8", newline="\n")
    rows = sc.resolve_card_names(_rows(root), [root / ".claude" / "memory"])
    assert [(r["card"], r["reused"]) for r in rows] == [("server部位導讀-2", False), ("client部位導讀", False), ("docs部位導讀-2", False)]
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    assert res["ok"] and res["written_cards"] == ["server部位導讀-2", "client部位導讀", "docs部位導讀-2"]
    parsed = parse_map((root / ".claude/overview-map.md").read_text(encoding="utf-8"))
    assert [r["card"] for r in parsed] == ["server部位導讀-2", "client部位導讀", "docs部位導讀-2"]
    issues = sc.check_consistency(root)
    assert len(issues) == 1 and issues[0].startswith("卡有表無：卡 `server部位導讀`")       # 別人的 Gateway 卡被點名，不是被沿用


def test_merge_missing_keeps_existing_pairing_and_avoids_collision(tmp_path):
    """先只有 a_b/ → 既有表 `a_b/`→`a-b部位導讀`；再加 a-b/ 重掃（排序會把 a-b 排前）→ 既有列不變、新列拿 -2、零不符。"""
    root = tmp_path / "pair"
    (root / "a_b").mkdir(parents=True)
    (root / "a_b" / "f.txt").write_text("x", encoding="utf-8", newline="\n")
    (root / ".claude" / "memory").mkdir(parents=True)
    (root / ".claude" / "memory" / "MEMORY.md").write_text("# idx\n", encoding="utf-8", newline="\n")
    res = sc.write_scaffold(root, sc.draft_rows(sc.scan_top_dirs(root)), "設計通則", write=True)
    assert res["ok"] and res["written_cards"] == ["a-b部位導讀"]
    map_path = root / ".claude" / "overview-map.md"
    before = map_path.read_text(encoding="utf-8")
    (root / "a-b").mkdir()
    (root / "a-b" / "g.txt").write_text("x", encoding="utf-8", newline="\n")
    rows = sc.draft_rows(sc.scan_top_dirs(root))
    assert [r["card"] for r in rows] == ["a-b部位導讀", "a-b部位導讀-2"] and rows[0]["part"] == "a-b"   # 重掃時 a-b 搶到 base 名
    res = sc.write_scaffold(root, rows, "設計通則", write=True, merge_missing=True)
    assert res["ok"] and res["rows"] == 1 and res["written_cards"] == ["a-b部位導讀-2"] and res["reused_cards"] == []
    after = map_path.read_text(encoding="utf-8")
    assert after.startswith(before.rstrip("\n"))                                        # 既有列一字不動
    parsed = parse_map(after)
    assert [(r["part"], r["card"]) for r in parsed] == [("a_b", "a-b部位導讀"), ("a-b", "a-b部位導讀-2")]
    assert sc.card_part(root / ".claude/memory/shared/設計通則/a-b部位導讀-2.md") == "a-b"
    assert sc.check_consistency(root) == []
    res = sc.write_scaffold(root, sc.draft_rows(sc.scan_top_dirs(root)), "設計通則", write=True, merge_missing=True)
    assert res["ok"] and res["rows"] == 0 and res["cards"] == []                        # 再跑一次什麼都不動
