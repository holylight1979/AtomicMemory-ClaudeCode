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

APPB_TABLE = """
| 順序 | 路徑前綴 | 部位 | 導讀卡（atom 名） | 狀態 |
|---|---|---|---|---|
| 1 | `appb_server/WorldServer/Clan/` | Server／氏族域（子 Manager 群） | `server部位導讀-x` | 有（2026-10-08） |
| 2 | `appb_server/WorldServer/` | Server／主邏輯（Handler） | 同上 | 有 |
| 3 | `appb_server/ServerTools/Merge/` | 合服工具（多模式） | `合服部位導讀-y`（`shared/合服/`） | 有 |
| 4 | `Tools/` | 工具鏈（SVN） | `工具鏈導讀-z` | 有 |
| 5 | `_tools/` | 外部輕量腳本 | 同第 4 列 | 有 |
| 6 | `Vendor-Framework/` | 框架源碼 | 無；病灶見 Server 卡 | 無 |
"""

GAMEA_TABLE = """
| 路徑前綴 | 範疇 | 導讀卡（卡名） | 狀態 | 備註 |
|---|---|---|---|---|
| `Game\\ui\\Map\\`、`Game\\player\\map\\` | 大地圖（面板） | `大地圖知識導讀-hub索引` | 有 | 文件 `_AIDocs/x.md` |
| `Game\\ui\\`（上列以外） | UI 演出 | `ui演出知識導讀-hub索引` | 有（第二批） | 20 張 |
| `Assets\\Game\\config\\tables\\*.bytes` | 設計表 | `設計表知識導讀-hub索引` | 有（第三批） | 含 `BuildTables.ps1` |
| `rpc\\` | 網路登入 | `gamea-wire-protocols` | 部分 | 10 張 |
| `Assets\\Game\\scripts\\` | 主程式集 | `doc-index-client-scripts` | 索引 | CS-01 |
"""


# ─── 讀表 ──────────────────────────────────────────────────────────

def test_parse_appb_table_inherits_and_status():
    rows = oh.parse_map(APPB_TABLE)
    assert [r["part_short"] for r in rows] == ["Server", "Server", "合服工具", "工具鏈", "外部輕量腳本", "框架源碼"]
    assert rows[1]["card"] == "server部位導讀-x"          # 同上
    assert rows[4]["card"] == "工具鏈導讀-z"              # 同第 4 列
    assert rows[2]["card"] == "合服部位導讀-y"            # 路徑反引號不當卡名
    assert rows[5]["card"] is None and rows[5]["status"] == "無"
    assert rows[0]["status"] == "有"


def test_parse_gamea_table_backslash_glob_and_partial_status():
    rows = oh.parse_map(GAMEA_TABLE)
    assert rows[0]["prefixes"] == ["game/ui/map", "game/player/map"]
    assert rows[2]["prefixes"] == ["assets/game/config/tables/*.bytes"]
    assert rows[2]["card"] == "設計表知識導讀-hub索引"     # BuildTables.ps1 不是卡名
    assert [r["status"] for r in rows] == ["有", "有", "有", "部分", "索引"]


# ─── 命中 ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("path,part", [
    ("c:/Work/AppB/appb_server/WorldServer/Clan/ClanManager.cs", "Server"),
    ("c:/Work/AppB/appb_server/ServerTools/Merge/Step1.cs", "合服工具"),
    ("c:/Work/AppB/Tools/ExcelToData/a.cs", "工具鏈"),
    ("c:/Work/AppB/_tools/x.py", "外部輕量腳本"),
    ("c:/Work/AppB/_AIDocs/x.md", None),
])
def test_match_appb_longest_prefix(path, part):
    rows = oh.parse_map(APPB_TABLE)
    m = oh.match_row(path, Path("c:/Work/AppB"), rows)
    assert (m["part_short"] if m else None) == part


@pytest.mark.parametrize("path,part", [
    ("C:/Work/GameA/Client/GameA_Hotfix/Game/ui/Map/MapPanel.cs", "大地圖"),   # 比 Game\ui\ 長 → 大地圖
    ("C:/Work/GameA/Client/GameA_Hotfix/Game/ui/common/Btn.cs", "UI 演出"),
    ("C:/Work/GameA/Client/Assets/Game/config/tables/hero.bytes", "設計表"),     # glob
    ("C:/Work/GameA/Client/GameA_Hotfix/rpc/x.cs", "網路登入"),
])
def test_match_gamea_substring_prefix(path, part):
    rows = oh.parse_map(GAMEA_TABLE)
    assert oh.match_row(path, Path("C:/Work/GameA"), rows)["part_short"] == part


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
        "| `Vendor/` | 框架 | 無 | 無 |\n", encoding="utf-8")
    (root / ".claude" / "memory" / "shared" / "戰鬥" / "戰鬥知識導讀-hub索引.md").write_text("# 戰鬥導讀\n病灶：共用字典", encoding="utf-8")
    (root / "Game" / "Battle").mkdir(parents=True)
    (root / "Vendor").mkdir()
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

    warn, deny, changed = wo.on_edit(state, "sess", f1, tp, cfg)        # 沒交定位 → 警告、dry_run 不擋
    assert warn and "定位三行" in warn and "讀了 2 個檔" in warn and deny is None and changed

    with open(tp, "a", encoding="utf-8") as f:                           # 交了定位三行 → 放行，state 仍標 changed
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥——A.cs\n定位｜根因層：根因在邏輯層\n定位｜前例：共用字典"}]}}, ensure_ascii=False) + "\n")
    assert wo.on_edit(state, "sess", f1, tp, cfg) == (None, None, True)

    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert [e["event"] for e in log] == ["inject", "edit", "edit"]
    assert log[1]["located"] is False and log[2]["located"] is True


def test_edit_without_prior_read_injects_now_and_deny_when_not_dry_run(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    warn, deny, _ = wo.on_edit({}, "s", f1, tp, {"overview_hub": {"dry_run": True}})
    assert warn and "還沒看過" in warn and deny is None
    warn, deny, _ = wo.on_edit({}, "s", f1, tp, {"overview_hub": {"dry_run": False}})
    assert deny and "還沒看過" in deny and "戰鬥導讀" in deny      # B1：deny 理由要帶整張卡，模型才看得到


def test_no_card_row_still_asks_for_locate(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    state = {}
    txt = wo.on_read(state, "s", "Read", {"file_path": str(proj / "Vendor" / "x.cs")}, str(proj), "", {})
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
    assert wo.on_edit({}, "s", str(tmp_path / "lonely.cs"), "", {}) == (None, None, False)
    assert wo.on_read({}, "s", "Read", {"file_path": "x"}, "", "", {"overview_hub": {"enabled": False}}) is None


def test_project_override_file_wins(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".claude" / "overview-hub.json").write_text('{"dry_run": false}', encoding="utf-8")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    warn, deny, _ = wo.on_edit({}, "s", f1, tp, {"overview_hub": {"dry_run": True}})   # 根層 dry_run，專案覆蓋成擋
    assert deny
    (proj / ".claude" / "overview-hub.json").write_text('{"enabled": false}', encoding="utf-8")
    assert wo.on_edit({}, "s", f1, tp, {}) == (None, None, False)
    assert wo.on_read({}, "s", "Read", {"file_path": f1}, str(proj), tp, {}) is None


# ─── Codex 審查指出的五點（B1 在上面、B2／B5／W1／W2／B4 在這）────────────

def test_locate_two_parts_in_one_reply_both_count():                    # B2：兩部位各一組，不互相覆蓋
    text = ("定位｜部位：戰鬥——A\n定位｜根因層：邏輯層\n定位｜前例：共用字典\n"
            "定位｜部位：UI 演出——B\n定位｜根因層：展演層\n定位｜前例：事件沒解掛")
    assert oh.locate_present(text, "戰鬥") and oh.locate_present(text, "UI 演出")


def test_locate_rejects_copied_template():                                # W1：照抄注入範本的佔位句不算交
    text = "定位｜部位：戰鬥——這次改的是哪一塊\n定位｜根因層：修根因還是症狀；根因在哪層\n定位｜前例：這個部位以前摔過什麼"
    assert not oh.locate_present(text, "戰鬥")


def test_extended_profile_columns_do_not_steal_card_or_status():      # 擴欄（病灶清單、量尺、檢查器…）：骨架列導讀卡空就是空
    rows = oh.parse_map(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 病灶清單 | 量尺 | 檢查器清單 | 第四問 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| `Server/Map/` | 大地圖（world） | `大地圖知識導讀-hub索引`、`大地圖根因層` | 有 | `_AIDocs/d.md` | P90｜`dotnet run tick`｜25ms | `a.py`;`b.py` | 幾份存法？ |\n"
        "| `Server/Battle/` | 戰鬥 |  |  | `_AIDocs/d.md` | P90｜`dotnet run tick`｜25ms | `check.py` | 無 |\n"
    )
    assert rows[0]["cards"] == ["大地圖知識導讀-hub索引", "大地圖根因層"] and rows[0]["status"] == "有"
    assert rows[1]["cards"] == [] and rows[1]["status"] == ""


def test_glob_anchored_beats_shorter_prefix():                            # B5：錨在根的 glob 不被短前綴搶走
    rows = oh.parse_map("| `Assets\\` | 資產 | `a` | 有 |\n| `Assets\\Game\\config\\tables\\*.bytes` | 設計表 | `b` | 有 |\n")
    assert oh.match_row("C:/T/Assets/Game/config/tables/x.bytes", Path("C:/T"), rows)["part_short"] == "設計表"


def test_reads_after_counts_cross_part_and_untabled_files(proj, tmp_path, monkeypatch):   # W2
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    state, tp = {}, _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Vendor" / "o.cs")}, str(proj), tp, {})     # 另一部位
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "README.md")}, str(proj), tp, {})          # 表外檔
    rec = next(v for k, v in state["overview_hub"].items() if k.endswith("|戰鬥"))
    assert len(rec["reads_after"]) == 2


def test_bash_vcs_reads_count_as_reads():                                 # 專案覆蓋提案 #4
    got = oh.read_paths_from_tool("Bash", {"command": 'svn cat "c:/P/appb_server/A.cs" ; git show HEAD~1:hooks/x.py | head -5'}, "c:/P")
    assert got[0] == "c:/P/appb_server/A.cs" and got[1].replace("\\", "/") == "c:/P/hooks/x.py"


def test_project_locate_template_override(proj, tmp_path, monkeypatch):   # 專案覆蓋提案 #3
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".claude" / "overview-hub.json").write_text(
        '{"locate_template": ["改哪一塊", "根因在哪層", "對得上規格書哪個 R 編號或 §3 第幾列"]}', encoding="utf-8")
    state, tp = {}, _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    assert "定位｜前例：對得上規格書哪個 R 編號或 §3 第幾列" in txt
    with open(tp, "a", encoding="utf-8") as f:                              # 照抄專案自訂範本也不算交
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥——改哪一塊\n定位｜根因層：根因在哪層\n定位｜前例：對得上規格書哪個 R 編號或 §3 第幾列"}]}}, ensure_ascii=False) + "\n")
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})
    assert warn and "定位三行" in warn


def test_row_with_two_cards_injects_both_and_deny_parts(proj, tmp_path, monkeypatch):   # 另一專案提案 1、3、4
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".claude" / "memory" / "shared" / "戰鬥" / "戰鬥根因層.md").write_text("# 根因層\n共用字典", encoding="utf-8")
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
        "| `Game\\Battle\\` | 戰鬥 | `戰鬥知識導讀-hub索引`；根因層另有 `戰鬥根因層` | 有 |\n", encoding="utf-8")
    (proj / ".claude" / "overview-hub.json").write_text(
        '{"deny_parts": ["戰鬥"], "locate_extra": {"戰鬥": "跑的是哪份 DLL"}}', encoding="utf-8")
    state, tp = {}, _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    assert "戰鬥導讀" in txt and "共用字典" in txt and "定位｜加問：跑的是哪份 DLL" in txt
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {"overview_hub": {"dry_run": True}})   # 全域 dry_run，但戰鬥列開擋
    assert deny and "定位三行" in deny


def test_locate_accepted_from_tool_input_and_thinking(proj, tmp_path, monkeypatch):   # harness 掉字後的三管道
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = tmp_path / "t.jsonl"
    lines = "定位｜部位：戰鬥——A.cs\n定位｜根因層：邏輯層\n定位｜前例：共用字典"
    def entry(block):
        return json.dumps({"type": "assistant", "message": {"content": [block]}}, ensure_ascii=False) + "\n"
    tp.write_text(entry({"type": "text", "text": "x"}), encoding="utf-8")
    state = {}
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), str(tp), {})
    with open(tp, "a", encoding="utf-8") as f:                                    # 三行只在 Bash 參數裡
        f.write(entry({"type": "tool_use", "name": "Bash", "input": {"command": "# " + lines.replace("\n", "\n# ") + "\nsed -n 1,5p A.cs"}}))
    assert wo.on_edit(state, "s", f1, str(tp), {}) == (None, None, True)
    assert list(state["overview_hub"].values())[0]["located_via"] == "tool_input"
    assert oh.locate_channel(str(tp), 0, "戰鬥") == "tool_input"
    with open(tp, "a", encoding="utf-8") as f:                                    # 文字塊優先
        f.write(entry({"type": "text", "text": lines}))
    assert oh.locate_channel(str(tp), 0, "戰鬥") == "text"
    tp.write_text(entry({"type": "thinking", "thinking": lines}), encoding="utf-8")
    assert oh.locate_channel(str(tp), 0, "戰鬥") == "thinking"
    assert oh.locate_channel(str(tp), 0, "Server") is None


def test_missing_transcript_warns_instead_of_silent_allow(proj, tmp_path, monkeypatch):   # B4
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    state = {}
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), "", {})
    warn, deny, changed = wo.on_edit(state, "s", f1, str(tmp_path / "nope.jsonl"), {"overview_hub": {"dry_run": False}})
    assert deny is None and warn and "讀不到 transcript" in warn and changed
