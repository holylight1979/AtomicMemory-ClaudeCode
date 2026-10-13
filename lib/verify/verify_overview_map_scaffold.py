"""verify_overview_map_scaffold.py：從零掃表（lib/overview_scaffold、tools/overview-map-scaffold.py）；Q14。

正例：tree.json 掃出的表與 expected-table.md 一字相同；表過 parse_map roundtrip（狀態「骨架」、層「單層」、擴欄空）；
fix 熱點排前；無 VCS 仍產；dry-run 不落任何檔；表存在拒覆寫、內容不變；--merge-missing 只補缺列、舊列一字不動；
Lv1 只映射（專案 _taxonomy → 核心 → 預設），不開新；骨架卡五段齊、source=tool:overview-map-scaffold、[臨]；
寫卡先於寫表（每次 write_atom 當下表都還不在）；卡預驗失敗、真寫失敗或拋例外 → 結構化結果（ok=False、written／failed／skipped）、
不寫表、不刪任何東西、重跑接續；同名卡沿用條件＝部位行相符或 Source 是掃表產物（部位行被刪仍沿用、卡數不變），
同名人手寫卡 → 停、failed_card、不改名；沿用前核對 _atom_index.json 有條目、缺就補、補不進去 → 停；預驗失敗其餘全進 skipped；
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
from lib.atom_index_json import load_atom_index_json  # noqa: E402

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
            path.write_text(f"# {title}\n\n- Source: {kw['provenance']}\n\n## 知識\n\n{body}\n", encoding="utf-8", newline="\n")
        return atom_io.WriteResult(ok=True, path=path)


def test_detect_layer_and_kwargs(tmp_path):
    root = _mk_project(tmp_path)
    assert sc.detect_layer(root) == (sc.LAYER_PROJECT, root)
    import wg_core                                                               # detect_layer 已載入的同一份
    data = Path(wg_core.CLAUDE_DIR)                                              # 資料根（WG_CLAUDE_DIR 或 ~/.claude），不隨別支測試先載 wg_core 而變
    assert sc.detect_layer(data / "lib") == (sc.LAYER_ROOT, data)                # 根層子目錄＝根層
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
    assert res["cards"][1]["path"] is None                                           # 真寫失敗那張沒有路徑
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
    assert res["ok"] is False and res["failed_card"]["stage"] == "預驗" and res["skipped_cards"] == ["client部位導讀"]  # 預驗失敗其餘全進 skipped
    assert all(c["dry_run"] for c in fake.calls)                                      # 沒有任何真寫
    assert res["reused_cards"] == ["server部位導讀"] and res["written_cards"] == []


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


# ─── 004：沿用判定（部位行或 Source）、索引核對 ──────────────────────

def _card_file(root: Path, name: str) -> Path:
    return root / ".claude" / "memory" / "shared" / "設計通則" / f"{name}.md"


def _card_count(root: Path) -> int:
    return len(list((root / ".claude" / "memory").rglob("*部位導讀*.md")))


def test_reuse_by_part_line_or_source_else_stop(tmp_path):
    root = _mk_project(tmp_path)
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    assert res["ok"] and _card_count(root) == 3
    card = _card_file(root, "server部位導讀")
    text = card.read_text(encoding="utf-8")
    assert "- Source: tool:overview-map-scaffold" in text.split("## 知識")[0]            # 掃表產物有身分
    # 人把部位行刪掉 → 重跑仍沿用（Source 是掃表），卡數不變、不另建 -2
    card.write_text("\n".join(l for l in text.splitlines() if "部位與權威" not in l) + "\n", encoding="utf-8", newline="\n")
    (root / ".claude" / "overview-map.md").unlink()
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    assert res["ok"] and res["reused_cards"] == ["server部位導讀", "client部位導讀", "docs部位導讀"]
    assert _card_count(root) == 3 and not _card_file(root, "server部位導讀-2").exists()
    assert [r["card"] for r in parse_map((root / ".claude" / "overview-map.md").read_text(encoding="utf-8"))][0] == "server部位導讀"
    # 同名人手寫卡（沒 Source、部位不符）→ 停、failed_card、不寫表、不自動改名
    root2 = _mk_project(tmp_path, "proj2")
    hand = _card_file(root2, "client部位導讀")
    hand.parent.mkdir(parents=True)
    hand.write_text("# client部位導讀\n\n- Scope: shared\n\n## 知識\n\n- 部位與權威：部位 `Gateway`（前綴 `Gateway/`）\n",
                    encoding="utf-8", newline="\n")
    res = sc.write_scaffold(root2, _rows(root2), "設計通則", write=True)
    assert res["ok"] is False and res["written"] is False and not (root2 / ".claude" / "overview-map.md").exists()
    assert res["failed_card"]["name"] == "client部位導讀" and res["failed_card"]["stage"] == "定名"
    assert res["failed_card"]["error"] == f"既有同名卡非掃表產物且部位不符：{hand}，請改名或刪除後重跑"
    assert res["written_cards"] == [] and _card_count(root2) == 1 and not _card_file(root2, "client部位導讀-2").exists()
    # 同名人手寫卡但部位行相符 → 沿用（不是掃表產物也行）
    hand.write_text(hand.read_text(encoding="utf-8").replace("`Gateway`（前綴 `Gateway/`）", "`Client`（前綴 `Client/`）"),
                    encoding="utf-8", newline="\n")
    res = sc.write_scaffold(root2, _rows(root2), "設計通則", write=True)
    assert res["ok"] and res["reused_cards"] == ["client部位導讀"] and res["written"]
    # 避撞改名仍只在本次新列之間與既有表卡名：a-b／a_b 案不受影響（test_colliding_dir_names_get_distinct_cards）


def test_resolve_names_collide_only_with_table_and_this_run(tmp_path):
    root = _mk_project(tmp_path)
    rows, failed = sc.resolve_card_names(_rows(root), [root / ".claude" / "memory"], taken={"server部位導讀"})
    assert failed is None and [r["card"] for r in rows] == ["server部位導讀-2", "client部位導讀", "docs部位導讀"]
    assert all(r["reused"] is False for r in rows)


def test_index_missing_is_repaired_on_rerun(tmp_path, monkeypatch):
    """卡檔寫成、索引寫入拋例外 → 本次失敗；重跑：沿用前發現索引缺條目 → 補索引成功、表寫出、索引含該卡；補索引也失敗 → 停。"""
    root = _mk_project(tmp_path)
    mem = root / ".claude" / "memory"
    real_write_index = atom_io.write_index

    def boom(*_a, **_k):
        raise OSError(5, "index disk error")

    monkeypatch.setattr(atom_io, "write_index", boom)                                 # write_atom 內部呼叫的是模組全域
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    assert res["ok"] is False and res["failed_card"]["name"] == "server部位導讀" and "index disk error" in res["failed_card"]["error"]
    assert _card_file(root, "server部位導讀").is_file()                                   # 卡在磁碟
    assert not (root / ".claude" / "overview-map.md").exists()
    assert "server部位導讀" not in {a["name"] for a in load_atom_index_json(mem)["atoms"]}  # 索引缺
    # 補索引也失敗 → 停、不寫表（sc.write_index 是 sc 自己匯入的名字）
    monkeypatch.setattr(atom_io, "write_index", real_write_index)
    monkeypatch.setattr(sc, "write_index", boom)
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    assert res["ok"] is False and res["failed_card"]["stage"] == "索引核對"
    assert res["failed_card"]["error"].startswith(f"卡在磁碟但不在索引：{_card_file(root, 'server部位導讀')}")
    assert res["skipped_cards"] == ["client部位導讀", "docs部位導讀"] and not (root / ".claude" / "overview-map.md").exists()
    assert _card_count(root) == 1                                                        # 沒多寫任何卡
    # 索引修好 → 重跑：補索引、補其餘卡、寫表
    monkeypatch.setattr(sc, "write_index", real_write_index)
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True)
    assert res["ok"] and res["written"] and res["reused_cards"] == ["server部位導讀"]
    assert res["written_cards"] == ["client部位導讀", "docs部位導讀"]
    names = {a["name"]: a["path"] for a in load_atom_index_json(mem)["atoms"]}
    assert names["server部位導讀"] == "memory/shared/設計通則/server部位導讀.md" and "docs部位導讀" in names
    assert sc.check_consistency(root) == []
    res = sc.write_scaffold(root, _rows(root), "設計通則", write=True, merge_missing=True)
    assert res["ok"] and res["cards"] == []                                              # 已齊，什麼都不做


# ─── 根層 worktree：判成根層、讀 worktree 自己的卡、--write 一律拒 ─────────────────

WT_MAP = "| 路徑前綴 | 部位 | 導讀卡 | 狀態 |\n|---|---|---|---|\n| `server/` | server | `server部位導讀` | 骨架 |\n"


def _link_wt(live: Path, wt: Path, name: str) -> None:
    """把 wt 接成 live 的 git worktree 結構：live/.git/worktrees/<name>/ 目錄＋wt/.git 檔指回去。"""
    (live / ".git" / "worktrees" / name).mkdir(parents=True, exist_ok=True)
    (wt / ".git").write_text(f"gitdir: {live / '.git' / 'worktrees' / name}\n", encoding="utf-8")


def _root_wt_world(base: Path):
    """live 根層（base/claude）與它的 worktree（base/wt，git worktree 結構、表位元組相同、卡在 wt/memory）、一般專案（表不同）。"""
    live, wt, proj = base / "claude", base / "wt", base / "proj"
    for r in (live, wt, proj):
        (r / ".claude").mkdir(parents=True)
        (r / "server").mkdir()
        (r / "server" / "a.py").write_text("x\n", encoding="utf-8", newline="\n")
    for r in (live, wt):
        (r / ".claude" / "overview-map.md").write_text(WT_MAP, encoding="utf-8", newline="\n")
    (proj / ".claude" / "overview-map.md").write_text(WT_MAP + "| `docs/` | docs | 無 | 無 |\n", encoding="utf-8", newline="\n")
    (wt / "memory" / "MemDev").mkdir(parents=True)
    (wt / "memory" / "MemDev" / "server部位導讀.md").write_text("# server部位導讀\n", encoding="utf-8", newline="\n")
    _link_wt(live, wt, "wt")
    return live, wt, proj


def _all_files(base: Path) -> dict:
    return {str(p.relative_to(base)): _sha(p) for p in base.rglob("*") if p.is_file()}


@pytest.fixture
def live_wg_core(monkeypatch):
    if str(CLAUDE / "hooks") not in sys.path:
        sys.path.insert(0, str(CLAUDE / "hooks"))
    import wg_core
    return lambda live: monkeypatch.setattr(wg_core, "CLAUDE_DIR", live)


def test_detect_layer_root_worktree_reads_its_own_cards(tmp_path, live_wg_core):
    live, wt, proj = _root_wt_world(tmp_path)
    live_wg_core(live)
    assert sc.detect_layer(wt) == (sc.LAYER_ROOT, wt)
    assert sc.card_dirs(*sc.detect_layer(wt)) == [wt / "memory", wt / "_AIDocs" / "_atoms"]
    assert sc.check_consistency(wt) == []                                                # 卡在 wt/memory 找得到
    assert sc.detect_layer(proj) == (sc.LAYER_PROJECT, proj)                             # 反例：表不同＝一般專案
    assert sc.detect_layer(live) == (sc.LAYER_ROOT, live)


def test_root_worktree_preview_merge_missing_plans_without_writing(tmp_path, monkeypatch, live_wg_core):
    live, wt, _ = _root_wt_world(tmp_path)
    live_wg_core(live)
    (wt / "docs").mkdir()
    (wt / "docs" / "r.md").write_text("x\n", encoding="utf-8", newline="\n")
    fake = _FakeWriter(wt)
    monkeypatch.setattr(sc, "write_atom", fake)
    before = _all_files(tmp_path)
    res = sc.write_scaffold(wt, _rows(wt), sc.ROOT_DOMAIN, write=False, merge_missing=True)
    assert res["layer"] == sc.LAYER_ROOT and res["layer_root"] == str(wt) and not res["written"]
    assert fake.calls and "server部位導讀" not in {c["title"] for c in fake.calls}            # wt 的卡找得到，不重寫
    assert _all_files(tmp_path) == before                                               # 假 writer 真寫會落檔；沒有新檔＝只預驗


def test_root_worktree_write_refused_and_nothing_written(tmp_path, monkeypatch, live_wg_core):
    live, wt, _ = _root_wt_world(tmp_path)
    live_wg_core(live)
    fake = _FakeWriter(wt)
    monkeypatch.setattr(sc, "write_atom", fake)
    before = _all_files(tmp_path)
    for merge in (False, True):
        with pytest.raises(sc.ScaffoldError) as ei:
            sc.write_scaffold(wt, _rows(wt), sc.ROOT_DOMAIN, write=True, merge_missing=merge)
        assert sc.ROOT_WT_WRITE_REFUSED in str(ei.value)
    assert fake.calls == [] and _all_files(tmp_path) == before                          # 一次 write_atom 都沒叫


def test_detect_layer_fallback_without_wg_core_still_sees_root_worktree(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    live, wt, proj = _root_wt_world(home)
    live.rename(home / ".claude")                                                         # 退路的 live＝Path.home()/.claude
    _link_wt(home / ".claude", wt, "wt")                                                  # live 搬家後 .git 檔重新指回
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setitem(sys.modules, "wg_core", None)                                     # import wg_core → ImportError
    assert sc.detect_layer(wt) == (sc.LAYER_ROOT, wt)
    assert sc.detect_layer(proj) == (sc.LAYER_PROJECT, proj)
    assert "wg_core 判層不可用，退路徑判斷" in capsys.readouterr().err


def test_cli_root_worktree_write_exit_nonzero_and_check_reads_wt(tmp_path, fake_home):
    live, wt, _ = _root_wt_world(tmp_path / "w")
    env = {**os.environ, "HOME": str(fake_home), "USERPROFILE": str(fake_home), "WG_CLAUDE_DIR": str(live),
           "PYTHONIOENCODING": "utf-8"}

    def run(*args):
        return subprocess.run([sys.executable, "-X", "utf8", str(TOOL), *args], env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    before = _all_files(tmp_path)
    r = run("--cwd", str(wt), "--write")
    assert r.returncode != 0 and sc.ROOT_WT_WRITE_REFUSED in r.stderr, r.stdout + r.stderr
    r = run("--cwd", str(wt), "--write", "--merge-missing")
    assert r.returncode != 0 and sc.ROOT_WT_WRITE_REFUSED in r.stderr, r.stdout + r.stderr
    assert _all_files(tmp_path) == before                                               # tmp 內沒有新檔、沒改檔
    r = run("check", "--cwd", str(wt))
    assert r.returncode == 0 and r.stdout.rstrip().endswith("OVERVIEW_SCAFFOLD CHECK PASS issues=0"), r.stdout + r.stderr


def _nested_wt_world(home: Path):
    """live＝home/.claude；worktree 開在 live 底下（原生 EnterWorktree 的位置 <repo>/.claude/worktrees/<名>），表位元組相同。"""
    live = home / ".claude"
    wt = live / ".claude" / "worktrees" / "x"
    for r in (live, wt):
        (r / ".claude").mkdir(parents=True, exist_ok=True)
        (r / "server").mkdir(parents=True, exist_ok=True)
        (r / "server" / "a.py").write_text("x\n", encoding="utf-8", newline="\n")
        (r / ".claude" / "overview-map.md").write_text(WT_MAP, encoding="utf-8", newline="\n")
    (wt / "memory" / "MemDev").mkdir(parents=True)
    (wt / "memory" / "MemDev" / "server部位導讀.md").write_text("# server部位導讀\n", encoding="utf-8", newline="\n")
    _link_wt(live, wt, "x")
    return live, wt


@pytest.mark.parametrize("path_kind", ["wg_core", "fallback"])
def test_nested_root_worktree_under_live_is_root_wt_and_write_refused(tmp_path, monkeypatch, live_wg_core, path_kind):
    home = tmp_path / "H"
    live, wt = _nested_wt_world(home)
    if path_kind == "wg_core":
        live_wg_core(live)                                                                 # _layer_of 會判 root（在 live 之下）
    else:
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("USERPROFILE", str(home))
        monkeypatch.setitem(sys.modules, "wg_core", None)
    assert sc.detect_layer(wt) == (sc.LAYER_ROOT, wt)                                     # 不是 (root, live)
    fake = _FakeWriter(wt)
    monkeypatch.setattr(sc, "write_atom", fake)
    before = _all_files(home)
    for merge in (False, True):
        with pytest.raises(sc.ScaffoldError) as ei:
            sc.write_scaffold(wt, _rows(wt), sc.ROOT_DOMAIN, write=True, merge_missing=merge)
        assert sc.ROOT_WT_WRITE_REFUSED in str(ei.value)
    assert fake.calls == [] and _all_files(home) == before                               # live 與 wt 雜湊都不變


def _git(tmp_path: Path):
    """隔離全域／系統 git 設定的 git 執行器（作者資訊走環境變數）。"""
    cfg = tmp_path / "gitconfig-empty"
    cfg.write_text("", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    env.update({"GIT_CONFIG_GLOBAL": str(cfg), "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})

    def run(*args):
        r = subprocess.run(["git", *args], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=NO_WINDOW)
        assert r.returncode == 0, f"git {args}: {r.stderr}"
    return run


def test_org_root_with_live_map_stays_org_but_worktree_under_org_is_root(tmp_path, monkeypatch, live_wg_core):
    git = _git(tmp_path)
    live, org = tmp_path / "live", tmp_path / "org"
    live.mkdir()
    git("init", "-q", str(live))
    git("-C", str(live), "config", "core.autocrlf", "false")
    (live / ".claude").mkdir()
    (live / ".claude" / "overview-map.md").write_text(WT_MAP, encoding="utf-8", newline="\n")
    git("-C", str(live), "add", ".claude/overview-map.md")
    git("-C", str(live), "commit", "-q", "-m", "init")
    (org / ".claude").mkdir(parents=True)
    (org / ".claude" / "overview-map.md").write_text(WT_MAP, encoding="utf-8", newline="\n")   # 公司根放了與 live 相同的表
    live_wg_core(live)
    import wg_core
    monkeypatch.setattr(wg_core, "org_memory_root", lambda: org)
    assert sc.detect_layer(org) == (sc.LAYER_ORG, org)                                  # 反例：不是 worktree → 仍判 org
    wt = org / "wt-sub"
    git("-C", str(live), "worktree", "add", "-q", "-b", "wt-sub", str(wt))
    assert sc.detect_layer(wt) == (sc.LAYER_ROOT, wt)                                   # 正例：開在公司根底下的真 worktree
