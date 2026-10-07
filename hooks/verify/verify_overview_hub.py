"""verify_overview_hub.py — OverviewHub（第一次改某部位前整張注入導讀卡、Edit 前查定位三行）。

純函式：lib/overview_hub（讀表、最長前綴命中、定位三行、Bash 讀檔擷取）；
state 層：wg_overview.on_read / on_prompt / on_edit（用 tmp_path 造一個假專案與假 transcript）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import overview_hub as oh  # noqa: E402
import wg_overview as wo  # noqa: E402

SGI_TABLE = """
| 順序 | 路徑前綴 | 部位 | 導讀卡（atom 名） | 狀態 |
|---|---|---|---|---|
| 1 | `sgi_server/MapServer/Guild/` | Server／軍團域（六子 Manager） | `server部位導讀-x` | 有（2026-10-08） |
| 2 | `sgi_server/MapServer/` | Server／主邏輯（Handler） | 同上 | 有 |
| 3 | `sgi_server/ServerTools/Merge/` | 合服工具（四模式） | `合服部位導讀-y`（`shared/合服/`） | 有 |
| 4 | `Tools/` | 工具鏈（SVN） | `工具鏈導讀-z` | 有 |
| 5 | `_tools/` | 外部輕量腳本 | 同第 4 列 | 有 |
| 6 | `Orbit-Serverbase/` | 框架源碼 | 無；病灶見 Server 卡 | 無 |
"""

TSLG_TABLE = """
| 路徑前綴 | 範疇 | 導讀卡（卡名） | 狀態 | 備註 |
|---|---|---|---|---|
| `Game\\ui\\Map\\`、`Game\\player\\map\\` | 大地圖（面板） | `大地圖知識導讀-hub索引` | 有 | 文件 `_AIDocs/x.md` |
| `Game\\ui\\`（上列以外） | UI 演出 | `ui演出知識導讀-hub索引` | 有（T8） | 25 張 |
| `Assets\\Game\\design\\dat\\*.bytes` | 設計表 | `設計表知識導讀-hub索引` | 有（T9） | 含 `GoldenMaster.ps1` |
| `rpc\\` | 網路登入 | `tslg-wire-protocols` | 部分 | 12 張 |
| `Assets\\Game\\scripts\\` | 主程式集 | `doc-index-client-scripts` | 索引 | CS-58 |
"""


# ─── 讀表 ──────────────────────────────────────────────────────────

def test_parse_sgi_table_inherits_and_status():
    rows = oh.parse_map(SGI_TABLE)
    assert [r["part_short"] for r in rows] == ["Server", "Server", "合服工具", "工具鏈", "外部輕量腳本", "框架源碼"]
    assert rows[1]["card"] == "server部位導讀-x"          # 同上
    assert rows[4]["card"] == "工具鏈導讀-z"              # 同第 4 列
    assert rows[2]["card"] == "合服部位導讀-y"            # 路徑反引號不當卡名
    assert rows[5]["card"] is None and rows[5]["status"] == "無"
    assert rows[0]["status"] == "有"


def test_parse_tslg_table_backslash_glob_and_partial_status():
    rows = oh.parse_map(TSLG_TABLE)
    assert rows[0]["prefixes"] == ["game/ui/map", "game/player/map"]
    assert rows[2]["prefixes"] == ["assets/game/design/dat/*.bytes"]
    assert rows[2]["card"] == "設計表知識導讀-hub索引"     # GoldenMaster.ps1 不是卡名
    assert [r["status"] for r in rows] == ["有", "有", "有", "部分", "索引"]


# ─── 命中 ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("path,part", [
    ("c:/Projects/sgi_server/MapServer/Guild/GuildManager.cs", "Server"),
    ("c:/Projects/sgi_server/ServerTools/Merge/Step1.cs", "合服工具"),
    ("c:/Projects/Tools/ExcelToData/a.cs", "工具鏈"),
    ("c:/Projects/_tools/x.py", "外部輕量腳本"),
    ("c:/Projects/_AIDocs/x.md", None),
])
def test_match_sgi_longest_prefix(path, part):
    rows = oh.parse_map(SGI_TABLE)
    m = oh.match_row(path, Path("c:/Projects"), rows)
    assert (m["part_short"] if m else None) == part


@pytest.mark.parametrize("path,part", [
    ("C:/TSLG/Client/TSLG_Hotfix/Game/ui/Map/MapPanel.cs", "大地圖"),   # 比 Game\ui\ 長 → 大地圖
    ("C:/TSLG/Client/TSLG_Hotfix/Game/ui/common/Btn.cs", "UI 演出"),
    ("C:/TSLG/Client/Assets/Game/design/dat/hero.bytes", "設計表"),     # glob
    ("C:/TSLG/Client/TSLG_Hotfix/rpc/x.cs", "網路登入"),
])
def test_match_tslg_substring_prefix(path, part):
    rows = oh.parse_map(TSLG_TABLE)
    assert oh.match_row(path, Path("C:/TSLG"), rows)["part_short"] == part


# ─── 定位三行 / Bash 讀檔 ───────────────────────────────────────────

def test_locate_present_requires_three_lines_and_part():
    ok = "定位｜部位：戰鬥——改 BattleView\n定位｜根因層：症狀，根因在邏輯層\n定位｜前例：共用字典"
    assert oh.locate_present(ok, "戰鬥")
    assert not oh.locate_present(ok, "Server")                 # 部位對不上
    assert not oh.locate_present(ok.rsplit("\n", 1)[0], "戰鬥")  # 少一行
    assert oh.locate_present(ok.replace("｜", "|").replace("：", ":"), "戰鬥")  # 半形也收


def test_read_paths_from_bash_and_read():
    got = oh.read_paths_from_tool("Bash", {"command": 'cd x && cat "C:/a/b.cs" | head; sed -n 1,5p lib/z.py; echo $P/x'}, "C:/w")
    assert got[0] == "C:/a/b.cs" and got[1].replace("\\", "/") == "C:/w/lib/z.py" and len(got) == 2
    assert oh.read_paths_from_tool("Read", {"file_path": "C:/q.cs"}, "") == ["C:/q.cs"]
    assert oh.read_paths_from_tool("Grep", {"pattern": "x"}, "") == []


# ─── state 層：假專案 + 假 transcript ───────────────────────────────

@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "proj"
    (root / ".claude" / "memory" / "shared" / "戰鬥").mkdir(parents=True)
    (root / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
        "| `Game\\Battle\\` | 戰鬥 | `戰鬥知識導讀-hub索引` | 有 |\n"
        "| `Orbit/` | 框架 | 無 | 無 |\n", encoding="utf-8")
    (root / ".claude" / "memory" / "shared" / "戰鬥" / "戰鬥知識導讀-hub索引.md").write_text("# 戰鬥導讀\n病灶：共用字典", encoding="utf-8")
    (root / "Game" / "Battle").mkdir(parents=True)
    (root / "Orbit").mkdir()
    return root


def _transcript(tmp_path, texts):
    tp = tmp_path / "t.jsonl"
    with open(tp, "w", encoding="utf-8") as f:
        for t in texts:
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}}, ensure_ascii=False) + "\n")
    return str(tp)


def test_state_flow_inject_once_then_warn_then_locate(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    cfg = {"overview_hub": {"enabled": True, "dry_run": True}}
    state = {"turn_seq": 3}
    tp = _transcript(tmp_path, ["先看看。"])
    f1, f2 = str(proj / "Game" / "Battle" / "A.cs"), str(proj / "Game" / "Battle" / "B.cs")

    txt = wo.on_read(state, "sess", "Read", {"file_path": f1}, str(proj), tp, cfg)
    assert txt and "整張" not in txt and "戰鬥導讀" in txt and "定位｜部位：戰鬥" in txt   # 第一次讀 → 注入整張
    assert wo.on_read(state, "sess", "Read", {"file_path": f2}, str(proj), tp, cfg) is None  # 第二次不再注入
    assert wo.on_read(state, "sess", "Bash", {"command": f'cat "{f1}"'}, str(proj), tp, cfg) is None

    warn, deny = wo.on_edit(state, "sess", f1, tp, cfg)                 # 沒交定位 → 警告、dry_run 不擋
    assert warn and "定位三行" in warn and "讀了 2 個檔" in warn and deny is None

    with open(tp, "a", encoding="utf-8") as f:                           # 交了定位三行 → 放行
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥——A.cs\n定位｜根因層：根因在邏輯層\n定位｜前例：共用字典"}]}}, ensure_ascii=False) + "\n")
    assert wo.on_edit(state, "sess", f1, tp, cfg) == (None, None)

    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert [e["event"] for e in log] == ["inject", "edit", "edit"]
    assert log[1]["located"] is False and log[2]["located"] is True


def test_edit_without_prior_read_injects_now_and_deny_when_not_dry_run(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    warn, deny = wo.on_edit({}, "s", f1, tp, {"overview_hub": {"dry_run": True}})
    assert warn and "還沒看過" in warn and deny is None
    warn, deny = wo.on_edit({}, "s", f1, tp, {"overview_hub": {"dry_run": False}})
    assert deny and "還沒看過" in deny


def test_no_card_row_still_asks_for_locate(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    state = {}
    txt = wo.on_read(state, "s", "Read", {"file_path": str(proj / "Orbit" / "x.cs")}, str(proj), "", {})
    assert txt and "沒有可注入的導讀卡" in txt and "定位｜前例" in txt


def test_prompt_mention_injects(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    state = {}
    p = str(proj / "Game" / "Battle" / "A.cs")
    assert wo.on_prompt(state, "s", f"幫我看 {p} 為什麼不掉血", "", {})
    assert wo.on_prompt(state, "s", f"再看 {p}", "", {}) is None


def test_outside_any_project_is_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    assert wo.on_read({}, "s", "Read", {"file_path": str(tmp_path / "lonely.cs")}, "", "", {}) is None
    assert wo.on_edit({}, "s", str(tmp_path / "lonely.cs"), "", {}) == (None, None)
    assert wo.on_read({}, "s", "Read", {"file_path": "x"}, "", "", {"overview_hub": {"enabled": False}}) is None


def test_project_override_file_wins(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".claude" / "overview-hub.json").write_text('{"dry_run": false}', encoding="utf-8")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    warn, deny = wo.on_edit({}, "s", f1, tp, {"overview_hub": {"dry_run": True}})   # 根層 dry_run，專案覆蓋成擋
    assert deny
    (proj / ".claude" / "overview-hub.json").write_text('{"enabled": false}', encoding="utf-8")
    assert wo.on_edit({}, "s", f1, tp, {}) == (None, None)
    assert wo.on_read({}, "s", "Read", {"file_path": f1}, str(proj), tp, {}) is None
