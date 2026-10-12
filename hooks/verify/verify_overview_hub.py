"""verify_overview_hub.py — OverviewHub（第一次改某部位前整張注入導讀卡、Edit 前查定位三行）。

純函式：lib/overview_hub（讀表、最長前綴命中、定位三行、Bash 讀檔擷取）；
state 層：wg_overview.on_read / on_prompt / on_edit（用 tmp_path 造一個假專案與假 transcript）。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))   # worktree 內跑：wg_core 的 lib／workflow 指本樹
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import overview_hub as oh  # noqa: E402
import wg_overview as wo  # noqa: E402


@pytest.fixture(autouse=True)
def _no_org(monkeypatch):
    """預設不接公司層：不讀本機真設定（org-memory.local.json）；要公司層的案自己再 setattr。"""
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())

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


def test_read_paths_bash_bare_name_only_when_file_exists_in_cwd(tmp_path):
    """缺口 5①：沒斜線的 token 只有 cwd 下真有這個檔才收（旗標、指令名不算）。"""
    (tmp_path / "main.py").write_text("x", encoding="utf-8")
    assert oh.read_paths_from_tool("Bash", {"command": "cat main.py"}, str(tmp_path)) == [str(tmp_path / "main.py")]
    assert oh.read_paths_from_tool("Bash", {"command": "cat -n"}, str(tmp_path)) == []
    assert oh.read_paths_from_tool("Bash", {"command": "echo hi"}, str(tmp_path)) == []
    assert oh.read_paths_from_tool("Bash", {"command": "cat nothere.py"}, str(tmp_path)) == []


def test_read_paths_from_powershell():
    """缺口 5②：Get-Content／gc／cat／type／Select-String -Path／Import-Csv；-Path／-LiteralPath 具名或第一個位置參數。"""
    def ps(c):
        return [p.replace("\\", "/") for p in oh.read_paths_from_tool("PowerShell", {"command": c}, "C:/w")]
    assert ps("Get-Content src/widget.py") == ["C:/w/src/widget.py"]
    assert ps('gc -Path "C:/x/a.cs"') == ["C:/x/a.cs"]
    assert ps("Select-String -Path a.txt foo") == ["C:/w/a.txt"]
    assert ps("Get-Content $p") == []                                            # 反例：含變數跳過
    assert ps("Select-String foo") == []                                         # 反例：Select-String 第一個位置參數是 Pattern
    assert ps("Write-Output hi") == []                                           # 反例：不是讀檔 cmdlet
    assert ps("Get-Content -Raw -Encoding utf8 x.py") == ["C:/w/x.py"]           # 帶值參數的值不當路徑
    assert ps("Get-Content -LiteralPath:'C:/y b/z.txt' -TotalCount 3") == ["C:/y b/z.txt"]
    assert ps("$rows = Import-Csv data/a.csv; type b.txt") == ["C:/w/data/a.csv", "C:/w/b.txt"]
    assert ps("gc a.cs,b.cs | Select-String x") == ["C:/w/a.cs", "C:/w/b.cs"]
    assert oh.read_paths_from_tool("Read", {"file_path": "C:/q.cs"}, "C:/w") == ["C:/q.cs"]   # Read 行為不變


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


def test_state_flow_inject_once_then_deny_then_locate(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    cfg = {"overview_hub": {"enabled": True}}
    state = {"turn_seq": 3}
    tp = _transcript(tmp_path, ["先看看。"])
    f1, f2 = str(proj / "Game" / "Battle" / "A.cs"), str(proj / "Game" / "Battle" / "B.cs")

    txt = wo.on_read(state, "sess", "Read", {"file_path": f1}, str(proj), tp, cfg)
    assert txt and "整張" not in txt and "戰鬥導讀" in txt and "定位｜部位：戰鬥" in txt   # 第一次讀 → 注入整張
    assert wo.on_read(state, "sess", "Read", {"file_path": f2}, str(proj), tp, cfg) is None  # 第二次不再注入
    assert wo.on_read(state, "sess", "Bash", {"command": f'cat "{f1}"'}, str(proj), tp, cfg) is None
    rec = next(v for k, v in state["overview_hub"].items() if k.endswith("|戰鬥"))
    assert rec["part_files_read"] == [f2, f1] and rec["reads_after"] == [f2, f1]

    warn, deny, changed = wo.on_edit(state, "sess", f1, tp, cfg)        # 沒交定位 → 一律擋（A4.1 沒有不擋的模式）
    assert deny and "定位三行" in deny and "讀了 2 個檔" in deny and warn == deny and changed

    with open(tp, "a", encoding="utf-8") as f:                           # 交了定位三行 → 放行，state 仍標 changed
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥：A.cs\n定位｜根因層：根因在邏輯層\n定位｜前例：共用字典"}]}}, ensure_ascii=False) + "\n")
    assert wo.on_edit(state, "sess", f1, tp, cfg) == (None, None, True)
    assert rec["located_via"] == "text" and rec["located_quality"] == "card"

    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert [e["event"] for e in log] == ["inject", "edit", "edit"]
    assert log[1]["located"] is False and log[1]["deny_reason"] == "evidence"
    assert log[2]["located"] is True and log[2]["deny_reason"] is None and log[2]["located_quality"] == "card"


def test_edit_without_prior_read_injects_now_and_denies(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    for cfg in ({}, {"overview_hub": {"enabled": True}}):
        warn, deny, changed = wo.on_edit({}, "s", f1, tp, cfg)
        assert deny and "還沒看過" in deny and "戰鬥導讀" in deny and warn == deny and changed   # B1：deny 理由要帶整張卡，模型才看得到
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert log[-1]["event"] == "edit_before_inject" and log[-1]["deny_reason"] == "not_injected"


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
    (proj / ".claude" / "overview-hub.json").write_text('{"max_card_chars": 5}', encoding="utf-8")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    warn, deny, _ = wo.on_edit({}, "s", f1, tp, {"overview_hub": {"max_card_chars": 6000}})   # 專案層蓋過 config.json
    assert deny and "超過 5 字截斷" in deny
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


@pytest.mark.parametrize("precedent, ok", [
    ("待規格：擊破任務計分時點沒人拍板", True),     # 帶理由＝誠實交出「沒有規格」
    ("待規格", False),                              # 光禿沒理由＝沒填
    ("待規格：", False),
    ("待規格:  ", False),
])
def test_locate_accepts_pending_spec(precedent, ok):
    text = f"定位｜部位：戰鬥\n定位｜根因層：根因層，計分時點與建築生命週期分家\n定位｜前例：{precedent}"
    assert oh.locate_present(text, "戰鬥") is ok


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


def test_row_with_two_cards_injects_both_and_locate_extra(proj, tmp_path, monkeypatch):   # 另一專案提案 1、3、4
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".claude" / "memory" / "shared" / "戰鬥" / "戰鬥根因層.md").write_text("# 根因層\n共用字典", encoding="utf-8")
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
        "| `Game\\Battle\\` | 戰鬥 | `戰鬥知識導讀-hub索引`；根因層另有 `戰鬥根因層` | 有 |\n", encoding="utf-8")
    (proj / ".claude" / "overview-hub.json").write_text(
        '{"locate_extra": {"戰鬥": "跑的是哪份 DLL"}}', encoding="utf-8")
    state, tp = {}, _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    assert "戰鬥導讀" in txt and "共用字典" in txt and "定位｜加問：跑的是哪份 DLL" in txt
    rec = next(iter(state["overview_hub"].values()))
    assert len(rec["card_paths"]) == 2
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})
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
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), str(tp), {})   # 部位檔 ≥1
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


def test_missing_transcript_denies_as_environment_error(proj, tmp_path, monkeypatch):   # B4 改 D4：fail-closed
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    state = {}
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), "", {})
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), "", {})
    for tp in (str(tmp_path / "nope.jsonl"), ""):
        warn, deny, changed = wo.on_edit(state, "s", f1, tp, {})
        assert deny and "transcript" in deny and "環境異常" in deny and changed
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert log[-1]["event"] == "edit" and log[-1]["deny_reason"] == "transcript_missing"


# ─── 軌 0：四層深合併 / find_map 界線 / _validate_cfg ─────────────────────────

def _org_world(tmp_path, monkeypatch, hub_json):
    org = tmp_path / "company"
    (org / ".claude").mkdir(parents=True)
    (org / ".claude" / "overview-hub.json").write_text(json.dumps(hub_json, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(wo, "org_memory_root", lambda: org)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    return org


def test_cfg_org_layer_overrides_config_and_project_wins(proj, tmp_path, monkeypatch):
    org = _org_world(tmp_path, monkeypatch, {"max_card_chars": 100, "locate_extra": {"戰鬥": "公司問", "UI": "公司UI問"}})
    config = {"overview_hub": {"max_card_chars": 50, "root_cause_triggers": ["根層詞"]}}
    c = wo._cfg(config, proj)
    assert c["max_card_chars"] == 100                                   # 公司層蓋過 config.json
    assert c["locate_extra"] == {"戰鬥": "公司問", "UI": "公司UI問"} and c["_errors"] == []
    (proj / ".claude" / "overview-hub.json").write_text(
        '{"max_card_chars": 20, "locate_extra": {"戰鬥": "專案問"}, "root_cause_triggers": ["專案詞"]}', encoding="utf-8")
    c = wo._cfg(config, proj)
    assert c["max_card_chars"] == 20                                    # 專案層勝
    assert c["locate_extra"] == {"戰鬥": "專案問", "UI": "公司UI問"}      # 巢狀 dict 深合併
    assert c["root_cause_triggers"] == ["專案詞"]                         # list 整個取覆蓋方
    assert c["_layer"] == "project_mapped"
    at_org = wo._cfg(config, org)                                       # root＝公司根 → 第四層跳過，只併一次
    assert at_org["max_card_chars"] == 100 and at_org["_layer"] == "org"


def test_cfg_without_org_ignores_company_file(proj, tmp_path):
    c = wo._cfg({}, proj)
    assert c["max_card_chars"] == 6000 and c["_errors"] == [] and c["_layer"] == "project_mapped"
    assert wo._cfg({}, None)["_layer"] == "none"


def test_deep_merge_nested_dict_list_replaced_base_untouched():
    from wg_core import _deep_merge
    base = {"a": {"x": 1, "y": 2}, "l": [1, 2], "k": 1}
    over = {"a": {"y": 3, "z": 4}, "l": [9], "n": {"m": 1}}
    out = _deep_merge(base, over)
    assert out == {"a": {"x": 1, "y": 3, "z": 4}, "l": [9], "k": 1, "n": {"m": 1}}
    assert base == {"a": {"x": 1, "y": 2}, "l": [1, 2], "k": 1}


def test_find_map_stops_at_stop_at_and_nested_tables(tmp_path):
    outer = tmp_path / "outer"
    inner = outer / "inner"
    for d in (outer, inner):
        (d / ".claude").mkdir(parents=True)
        (d / ".claude" / "overview-map.md").write_text("| `src/` | 部位 | `卡` | 有 |\n", encoding="utf-8")
    src = inner / "src"
    src.mkdir()
    f = str(src / "x.cs")
    assert oh.find_map(f)[0] == inner                                   # 最近的表
    assert oh.find_map(f, stop_at=inner)[0] == inner                    # stop_at 那層仍檢查
    assert oh.find_map(f, stop_at=src) is None                          # 到 stop_at 停，不再往上
    (inner / ".claude" / "overview-map.md").unlink()
    assert oh.find_map(f)[0] == outer
    assert oh.find_map(f, stop_at=inner) is None


def test_find_map_never_checks_home_or_drive_root(tmp_path, monkeypatch):
    assert oh.find_map(str(tmp_path / "lonely.cs")) is None             # tmp 在家目錄下，往上到家目錄就停
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "overview-map.md").write_text("| `a/` | 部位 | `卡` | 有 |\n", encoding="utf-8")
    (tmp_path / "a").mkdir()
    assert oh.find_map(str(tmp_path / "a" / "x.cs"))[0] == tmp_path
    monkeypatch.setattr(oh, "_home", lambda: tmp_path)                 # 把 tmp 當家目錄：那層不檢查
    assert oh.find_map(str(tmp_path / "a" / "x.cs")) is None
    assert oh.find_map(str(Path(tmp_path.anchor) / "nope.cs")) is None  # 磁碟根


def test_validate_cfg_default_passes_and_three_counterexamples(tmp_path):
    assert wo._validate_cfg(dict(wo._DEFAULT), None) == []
    assert wo._validate_cfg(dict(wo._DEFAULT), tmp_path) == []
    (tmp_path / "src" / "sub").mkdir(parents=True)
    amb = wo._validate_cfg(dict(wo._DEFAULT, path_bases=["src", "src/sub"]), tmp_path)
    assert len(amb) == 1 and "歧義" in amb[0]                            # 反例一：互相包含的基準
    missing = wo._validate_cfg(dict(wo._DEFAULT, path_bases=["nope"]), tmp_path)
    assert len(missing) == 1 and "不是存在的目錄" in missing[0]
    bad_enc = wo._validate_cfg(dict(wo._DEFAULT, commit_encoding="no-such-enc", source_encodings=["utf-8", "x-bogus"]), None)
    assert len(bad_enc) == 2 and all("編碼" in e for e in bad_enc)       # 反例二：壞編碼
    unknown = wo._validate_cfg(dict(wo._DEFAULT, foo=1), None)
    assert unknown == ["未知的設定鍵「foo」"]                              # 反例三：未知鍵
    assert wo._validate_cfg(dict(wo._DEFAULT, _doc="說明"), None) == []  # 底線鍵不算未知
    assert any("eol_policy" in e for e in wo._validate_cfg(dict(wo._DEFAULT, eol_policy="mixed"), None))


def test_retired_keys_warn_once_not_error_and_never_relax(proj, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    cfg = {"overview_hub": {k: True for k in wo._RETIRED_KEYS}}
    c = wo._cfg(cfg)
    assert c["_errors"] == []                                           # 退役鍵不報錯
    err = capsys.readouterr().err
    assert err.count("已退役") == len(wo._RETIRED_KEYS)
    wo._cfg(cfg)
    assert capsys.readouterr().err == ""                                # 第二次不再警告
    tp = _transcript(tmp_path, ["x"])
    warn, deny, _ = wo.on_edit({}, "s", str(proj / "Game" / "Battle" / "A.cs"), tp, cfg)   # 明寫退役鍵也不放行
    assert deny and "還沒看過" in deny


def test_cfg_errors_make_on_edit_deny(proj, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".claude" / "overview-hub.json").write_text('{"foo": 1, "eol_policy": "mixed"}', encoding="utf-8")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    warn, deny, changed = wo.on_edit({}, "s", f1, tp, {})
    assert deny and "設定有錯" in deny and "未知的設定鍵「foo」" in deny and "eol_policy" in deny and not changed
    assert "設定錯誤" in capsys.readouterr().err
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert log[-1]["event"] == "edit_cfg_error"
    assert wo.on_read({}, "s", "Read", {"file_path": f1}, str(proj), tp, {})   # 讀仍注入（錯誤只擋改）


def test_bad_company_file_is_loud_and_skipped(proj, tmp_path, monkeypatch, capsys):
    org = tmp_path / "company"
    (org / ".claude").mkdir(parents=True)
    (org / ".claude" / "overview-hub.json").write_text("{壞", encoding="utf-8")
    monkeypatch.setattr(wo, "org_memory_root", lambda: org)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    c = wo._cfg({}, proj)
    assert c["max_card_chars"] == 6000 and c["_layer"] == "project_mapped"
    assert len(c["_errors"]) == 1 and "公司層覆蓋檔讀取失敗" in c["_errors"][0]   # 壞檔＝設定錯誤，不是略過
    assert "公司層覆蓋檔讀取失敗" in capsys.readouterr().err


# ─── 退回 001 的兩條 BLOCK：設定錯誤必擋（順序）、無效設定不拋例外 ─────────────────

def _hub(proj, text):
    (proj / ".claude" / "overview-hub.json").write_text(text, encoding="utf-8")


@pytest.mark.parametrize("hub_text", ['{"enabled": false, "foo": 1}', '{"enabled": null, "foo": 1}'])
def test_cfg_errors_deny_even_when_disabled_or_enabled_not_bool(proj, tmp_path, monkeypatch, hub_text):   # BLOCK 1
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    _hub(proj, hub_text)
    tp = _transcript(tmp_path, ["x"])
    warn, deny, changed = wo.on_edit({}, "s", str(proj / "Game" / "Battle" / "A.cs"), tp, {})
    assert deny and "未知的設定鍵「foo」" in deny and not changed
    if "null" in hub_text:
        assert "enabled 必須是" in deny
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert log[-1]["event"] == "edit_cfg_error" and log[-1]["layer"] == "project_mapped"


def test_root_level_cfg_error_denies_file_outside_any_table(tmp_path, monkeypatch):   # BLOCK 1：沒命中表的檔也擋
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    bad = {"overview_hub": {"enabled": False, "bogus": 1}}
    warn, deny, changed = wo.on_edit({}, "s", str(tmp_path / "lonely.cs"), "", bad)
    assert deny and "未知的設定鍵「bogus」" in deny and "none" in deny and not changed
    assert wo.on_edit({}, "s", "", "", bad) == (None, None, False)      # 沒 file_path 沒東西可擋


def test_invalid_config_shapes_become_errors_not_exceptions(proj):   # BLOCK 2
    for section in (True, [1], "x", 3):
        c = wo._cfg({"overview_hub": section}, proj)
        assert c["_layer"] == "project_mapped" and c["max_card_chars"] == 6000
        assert any("overview_hub 段必須是物件" in e for e in c["_errors"]), section
    assert wo._cfg({"overview_hub": None}, proj)["_errors"] == []       # null 當沒設
    _hub(proj, "[1, 2]")
    c = wo._cfg({}, proj)
    assert len(c["_errors"]) == 1 and "頂層不是物件" in c["_errors"][0]
    _hub(proj, "{壞")
    assert "專案層覆蓋檔讀取失敗" in wo._cfg({}, proj)["_errors"][0]


def test_encoding_with_nul_is_error_not_valueerror():   # BLOCK 2
    for bad in ("utf\u0000-8", "", None, 5, ["utf-8"]):
        assert wo._encoding_ok(bad) is False
    errs = wo._validate_cfg(dict(wo._DEFAULT, commit_encoding="utf\u0000-8", source_encodings=["utf\u0000-8"],
                                PYTHONIOENCODING=["utf-8"]), None)
    assert len(errs) == 3 and all("編碼" in e for e in errs)


def test_invalid_shapes_deny_on_edit_instead_of_raising(proj, tmp_path, monkeypatch):   # BLOCK 2 端到端
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    warn, deny, _ = wo.on_edit({}, "s", f1, tp, {"overview_hub": [1]})
    assert deny and "overview_hub 段必須是物件" in deny
    _hub(proj, '{"commit_encoding": "utf\\u0000-8"}')
    warn, deny, _ = wo.on_edit({}, "s", f1, tp, {})
    assert deny and "commit_encoding" in deny and "編碼" in deny


def test_root_layer_cards_resolve_from_claude_memory(tmp_path, monkeypatch):
    """根層自己的表放 <CLAUDE_DIR>/.claude/overview-map.md，卡在 <CLAUDE_DIR>/memory（不是 .claude/memory）。"""
    fake = tmp_path / "claude"
    (fake / ".claude").mkdir(parents=True)
    (fake / "hooks").mkdir()
    (fake / "memory" / "CC").mkdir(parents=True)
    (fake / "memory" / "CC" / "hooks導讀.md").write_text("# hooks 導讀\n病灶：pythonw 無 stdio", encoding="utf-8")
    (fake / ".claude" / "overview-map.md").write_text("| `hooks/` | hook 層 | `hooks導讀` | 部分 |\n", encoding="utf-8")
    monkeypatch.setattr(wo, "CLAUDE_DIR", fake)
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    import wg_core
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", fake)
    assert wo._cfg({}, fake)["_layer"] == "root"
    txt = wo.on_read({}, "s", "Read", {"file_path": str(fake / "hooks" / "x.py")}, str(fake), "", {})
    assert txt and "pythonw 無 stdio" in txt
    assert oh.resolve_card(fake, "hooks導讀") is None                   # 預設位置找不到
    assert oh.resolve_card(fake, "hooks導讀", fake / "memory").name == "hooks導讀.md"


# ─── 退回 002 的 BLOCK：設定錯誤不得封鎖設定檔自身的修復 ───────────────────────

def test_cfg_error_still_allows_editing_the_config_files_themselves(proj, tmp_path, monkeypatch):
    import wg_core
    fake = tmp_path / "claude"
    (fake / ".claude").mkdir(parents=True)
    (fake / "workflow").mkdir()
    cfg_path = fake / "workflow" / "config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    root_hub = fake / ".claude" / "overview-hub.json"
    root_hub.write_text('{"bogus": 1}', encoding="utf-8")
    monkeypatch.setattr(wo, "CLAUDE_DIR", fake)
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", fake)
    monkeypatch.setattr(wo, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    bad = {"overview_hub": {"enabled": False, "bogus": 1}}

    warn, deny, changed = wo.on_edit({}, "s", str(cfg_path), tp, bad)                  # ① 根層 config.json：放行＋警告
    assert deny is None and not changed and warn and "放行以便修復" in warn and "未知的設定鍵「bogus」" in warn
    warn, deny, _ = wo.on_edit({}, "s", str(root_hub), tp, bad)                        # ② 根層 .claude/overview-hub.json
    assert deny is None and warn and "bogus" in warn
    _hub(proj, '{"foo": 1}')
    warn, deny, _ = wo.on_edit({}, "s", str(proj / ".claude" / "overview-hub.json"), tp, {})   # ③ 專案 hub.json
    assert deny is None and warn and "未知的設定鍵「foo」" in warn

    warn, deny, _ = wo.on_edit({}, "s", str(fake / "workflow" / "other.json"), tp, bad)   # 同目錄他檔仍擋（比路徑不比檔名）
    assert deny and "bogus" in deny
    warn, deny, _ = wo.on_edit({}, "s", str(fake / "workflow" / "config.json.bak"), tp, bad)
    assert deny
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    warn, deny, _ = wo.on_edit({}, "s", f1, tp, {})                                      # 專案 hub 壞 → 部位檔仍擋
    assert deny and "foo" in deny

    _hub(proj, "{}")                                                                     # 修好 → 下一次 Edit 走正常注入分支
    warn, deny, changed = wo.on_edit({}, "s", f1, tp, {})
    assert changed and deny and "還沒看過" in deny and "戰鬥導讀" in deny
    assert wo.on_edit({}, "s", str(proj / ".claude" / "overview-hub.json"), tp, {}) == (None, None, False)   # 設定沒錯：自家設定檔靜默放行
    events = [json.loads(l)["event"] for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert events.count("edit_own_config") == 3 and "edit_cfg_error" in events and events[-1] == "edit_before_inject"


def test_validator_internal_error_still_denies_and_logs_traceback(proj, monkeypatch, capsys):   # 退回 002 的 WARN
    seen = []
    monkeypatch.setattr(wo, "_atom_debug_error", lambda src, exc: seen.append((src, type(exc).__name__)))

    def _bug(bases, root):
        raise RuntimeError("validator-bug")
    monkeypatch.setattr(wo, "_validate_path_bases", _bug)
    c = wo._cfg({}, proj)
    assert len(c["_errors"]) == 1 and "內部錯誤" in c["_errors"][0] and "validator-bug" in c["_errors"][0]
    assert seen == [("overview_hub:validate", "RuntimeError")]
    assert "內部錯誤" in capsys.readouterr().err


def test_cfg_error_still_allows_editing_the_map_itself(proj, tmp_path, monkeypatch):   # 003 複審裁定：表本身也能自救
    import wg_core
    fake = tmp_path / "claude"
    (fake / ".claude").mkdir(parents=True)
    root_map = fake / ".claude" / "overview-map.md"
    root_map.write_text("| `hooks/` | hook 層 | `打錯的卡名` | 有 |\n", encoding="utf-8")
    monkeypatch.setattr(wo, "CLAUDE_DIR", fake)
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", fake)
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    bad = {"overview_hub": {"enabled": False, "bogus": 1}}

    warn, deny, changed = wo.on_edit({}, "s", str(root_map), tp, bad)                  # 根層表：放行＋警告
    assert deny is None and not changed and warn and "放行以便修復" in warn and "bogus" in warn
    _hub(proj, '{"foo": 1}')
    proj_map = proj / ".claude" / "overview-map.md"
    warn, deny, _ = wo.on_edit({}, "s", str(proj_map), tp, {})                         # 專案表：放行＋警告列專案層錯誤
    assert deny is None and warn and "未知的設定鍵「foo」" in warn
    warn, deny, _ = wo.on_edit({}, "s", str(fake / ".claude" / "overview-map.md.bak"), tp, bad)   # 同目錄他檔仍擋（比路徑不比檔名）
    assert deny and "bogus" in deny
    warn, deny, _ = wo.on_edit({}, "s", str(fake / ".claude" / "notes.md"), tp, bad)
    assert deny and "bogus" in deny
    warn, deny, _ = wo.on_edit({}, "s", str(proj / "Game" / "Battle" / "A.cs"), tp, {})          # 專案表壞設定下部位檔仍擋
    assert deny and "foo" in deny
    _hub(proj, "{}")
    assert wo.on_edit({}, "s", str(proj_map), tp, {}) == (None, None, False)          # 設定沒錯：表靜默放行
    events = [json.loads(l)["event"] for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert events.count("edit_own_config") == 2 and events.count("edit_cfg_error") == 3


# ─── 退回 003 的兩條 BLOCK：extended-length 前綴、磁碟目錄實際大小寫／symlink 不得漏判自家檔 ───────

def test_own_config_matches_with_extended_prefix(proj, tmp_path, monkeypatch):
    import wg_core
    fake = tmp_path / "claude"
    (fake / "workflow").mkdir(parents=True)
    cfg_path = fake / "workflow" / "config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(wo, "CLAUDE_DIR", fake)
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", fake)
    monkeypatch.setattr(wo, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    bad = {"overview_hub": {"enabled": False, "bogus": 1}}
    assert wo._strip_extended("\\\\?\\C:\\x\\y") == "C:\\x\\y"
    assert wo._strip_extended("\\\\?\\UNC\\srv\\share\\y") == "\\\\srv\\share\\y"
    assert wo._strip_extended("C:\\x") == "C:\\x"

    ext = "\\\\?\\" + str(cfg_path)
    assert wo._own_config_layer(ext) == (True, None)
    warn, deny, _ = wo.on_edit({}, "s", ext, tp, bad)                                    # 前綴版 config.json：放行＋警告
    assert deny is None and warn and "bogus" in warn
    _hub(proj, '{"foo": 1}')
    ext_hub = "\\\\?\\" + str(proj / ".claude" / "overview-hub.json")
    assert wo._own_config_layer(ext_hub) == (True, proj)
    warn, deny, _ = wo.on_edit({}, "s", ext_hub, tp, {})                                 # 前綴版專案 hub.json
    assert deny is None and warn and "foo" in warn
    warn, deny, _ = wo.on_edit({}, "s", "\\\\?\\" + str(fake / "workflow" / "other.json"), tp, bad)   # 前綴版他檔仍擋
    assert deny and "bogus" in deny


def test_own_config_matches_when_dir_case_differs(tmp_path, monkeypatch):
    """磁碟目錄實際是 .CLAUDE（resolve 回大寫）、表把 .claude/ 列成部位、hub 有錯 → 仍是自家檔，放行＋警告。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = tmp_path / "proj2"
    (root / ".CLAUDE").mkdir(parents=True)
    (root / ".CLAUDE" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
        "| `.claude/` | 設定 | 無 | 無 |\n| `src/` | 主程式 | 無 | 無 |\n", encoding="utf-8")
    (root / ".CLAUDE" / "overview-hub.json").write_text('{"foo": 1}', encoding="utf-8")
    (root / "src").mkdir()
    tp = _transcript(tmp_path, ["x"])
    hub_lower = str(root / ".claude" / "overview-hub.json")                              # 呼叫端給小寫
    assert Path(hub_lower).resolve().parent.name == ".CLAUDE"                            # 前提：resolve 還原磁碟實際大小寫
    assert wo._own_config_layer(hub_lower)[0] is True
    warn, deny, _ = wo.on_edit({}, "s", hub_lower, tp, {})
    assert deny is None and warn and "未知的設定鍵「foo」" in warn
    warn, deny, _ = wo.on_edit({}, "s", str(root / ".CLAUDE" / "OVERVIEW-MAP.MD"), tp, {})   # 表本身、全大寫寫法
    assert deny is None and warn and "foo" in warn
    warn, deny, _ = wo.on_edit({}, "s", str(root / ".CLAUDE" / "notes.md"), tp, {})      # 同目錄他檔命中「設定」部位 → 仍擋
    assert deny and "foo" in deny
    warn, deny, _ = wo.on_edit({}, "s", str(root / "src" / "a.py"), tp, {})
    assert deny and "foo" in deny


# ─── 軌 A：分片（A0.4）、選片注入（A0.5）、固定句（A1.1）───────────────────────

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "v6"
FIVE_CARD = (
    "# 戰鬥導讀\n\n- Scope: shared\n- Trigger: 戰鬥\n\n## 知識\n\n"
    "- [臨] **做什麼與上下游**：單人戰鬥。\n  - 子點跟著上一段\n"
    "- [臨] **部位與權威**：DamageSystem 為真相。\n"
    "- [臨] **動手前必問**：幾份存法？\n"
    "- [臨] **已知病灶**：①最後一擊無訊號 ②結算生命期。\n\n| 分支 | 卡 |\n|---|---|\n| a | b |\n"
    "- [臨] **驗法**：F2 實跑。\n"
    "- [臨] 2026-10-08 校正：一行雜訊。\n\n## 行動\n\n- 動戰鬥前先讀本卡\n"
)


def test_split_card_sections_twelve_real_card_label_variants():
    data = json.loads((FIXTURES / "hub_card_labels.json").read_text(encoding="utf-8"))["cards"]
    assert len(data) >= 12
    for card, labels in data.items():
        body = "# " + card + "\n\n## 知識\n\n" + "".join(f"- [臨] **{lab}**：內容 {i}\n" for i, lab in enumerate(labels))
        parsed = oh.split_card_sections(body)
        for i, (lab, want) in enumerate(labels.items()):
            got = oh.slice_of_label(lab)
            assert got == want, (card, lab, got)
            where = parsed["slices"].get(want, "") if want else parsed["others"].get(lab, "")
            assert f"內容 {i}" in where, (card, lab)


def test_split_card_sections_full_card_shape_and_no_heading_counterexample():
    p = oh.split_card_sections(FIVE_CARD)
    assert p["head"].startswith("# 戰鬥導讀") and "- Trigger: 戰鬥" in p["head"]
    assert set(p["slices"]) == set(oh.SLICE_NAMES)
    assert "子點跟著上一段" in p["slices"]["what"] and "| a | b |" in p["slices"]["defects"]    # 子 bullet／表格跟上一段
    assert any(k.startswith("2026-10-08 校正") for k in p["others"]) and "行動" in p["others"]
    assert "## 知識" not in FIVE_CARD.replace(p["head"], "") or "知識" not in p["others"]       # 結構標題不算段
    flat = oh.split_card_sections("# 只有標題\n\n一段散文，沒有任何 ## 或 bullet。")             # 無標題單 head 反例
    assert flat["slices"] == {} and flat["others"] == {} and "一段散文" in flat["head"]
    spine = oh.split_card_sections("# Spine\n\n## 知識\n\n- [臨] 閱讀序 ①②③\n- [臨] 一句話結論：走程式拆件\n")
    assert spine["slices"] == {} and len(spine["others"]) == 2


@pytest.fixture
def five_card(tmp_path):
    cp = tmp_path / "戰鬥導讀.md"
    cp.write_text(FIVE_CARD, encoding="utf-8")
    return cp


ROW = {"part": "戰鬥", "part_short": "戰鬥", "cards": ["戰鬥導讀"], "status": "有", "line": "| x |", "layer": ""}


def test_build_injection_debug_picks_defects_first_and_lists_rest(five_card):
    txt, used = oh.build_injection_ex(ROW, [five_card], "C:/p/A.cs", 6000, None, None,
                                      ["defects", "verify", "authority"], "目標視角", "幾份存法、有無訊號")
    assert used == ["defects", "verify", "authority"]
    i_d, i_v, i_a = txt.index("[已知病灶]"), txt.index("[驗法]"), txt.index("[權威在哪]")
    assert i_d < i_v < i_a and txt.index("①最後一擊無訊號") < txt.index("F2 實跑")
    assert "視角：目標視角" in txt and "先問：幾份存法、有無訊號" in txt and oh.ROOT_CAUSE_SENTENCE in txt   # A1.1 固定句
    rest = txt.split("其餘段落只列標題")[1]
    assert "做什麼與上下游" in rest and "動手前必問" in rest and "行動" in rest
    assert "單人戰鬥。" not in txt                                                 # 沒選的片只列標題，不送全文
    assert "依意圖先送：已知病灶、驗法、權威在哪" in txt


def test_build_injection_falls_back_to_whole_card_and_general_keeps_order(tmp_path, five_card):
    plain = tmp_path / "平鋪.md"
    plain.write_text("# 平鋪\n\n沒有標籤的散文卡，病灶與驗法都寫在一起。", encoding="utf-8")
    txt, used = oh.build_injection_ex(ROW, [plain], "C:/p/A.cs", 6000, None, None, ["defects", "verify"])
    assert used == [] and "沒有標籤的散文卡" in txt and "其餘段落" not in txt            # 無片命中退整卡，不得注得更少
    txt, used = oh.build_injection_ex(ROW, [five_card], "C:/p/A.cs", 6000, None, None, [], "", "")
    assert used == [] and txt.index("單人戰鬥") < txt.index("最後一擊無訊號") < txt.index("F2 實跑")   # general：原序整卡
    assert "視角：" not in txt and "先問：" not in txt
    txt, used = oh.build_injection_ex(ROW, [five_card], "C:/p/A.cs", 80, None, None, ["defects"])
    assert used == ["defects"] and "超過 80 字截斷" in txt                            # max_card_chars 仍上限
    assert oh.build_injection(ROW, [five_card], "C:/p/A.cs", 6000) == oh.build_injection_ex(ROW, [five_card], "C:/p/A.cs", 6000)[0]


def test_locate_present_rejects_copied_root_cause_sentence():
    text = f"定位｜部位：戰鬥：A\n定位｜根因層：{oh.ROOT_CAUSE_SENTENCE}\n定位｜前例：共用字典"
    assert not oh.locate_present(text, "戰鬥")
    assert oh.locate_present(text.replace(oh.ROOT_CAUSE_SENTENCE, "邏輯層"), "戰鬥")


def test_locate_quality_three_values():
    card = ["## 知識\n- **已知病灶**：最後一擊無訊號；結算資料生命期"]
    base = "定位｜部位：戰鬥：A\n定位｜根因層：邏輯層\n定位｜前例："
    assert oh.locate_quality(base + "最後一擊無訊號（病灶①）", "戰鬥", card) == "card"
    assert oh.locate_quality(base + "無", "戰鬥", card) == "none"
    assert oh.locate_quality(base + "無；這張卡沒寫前例", "戰鬥", card) == "none"
    assert oh.locate_quality(base + "上次改壞過但卡沒記", "戰鬥", card) == "free"
    assert oh.locate_quality("沒交", "戰鬥", card) == "free"


# ─── 軌 A：三項證據（A4.2）、無表（A4.2）、readonly（A4.3）、thinking 提醒（A4.6）─────────

def _locate(tp, part="戰鬥", block="text", precedent="共用字典"):
    lines = f"定位｜部位：{part}：A.cs\n定位｜根因層：邏輯層\n定位｜前例：{precedent}"
    content = {"type": "thinking", "thinking": lines} if block == "thinking" else {"type": "text", "text": lines}
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [content]}}, ensure_ascii=False) + "\n")


def test_three_evidence_stages_card_cannot_be_disabled_part_files_then_locate(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    bad = {"overview_hub": {"min_overview_evidence": {"card": False}}}            # ① 讀卡不可關：關了是設定錯誤 → 擋
    warn, deny, _ = wo.on_edit({}, "s", f1, tp, bad)
    assert deny and "不可關" in deny
    state = {}
    wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})          # 注入
    for i in range(20):                                                            # ② 讀 20 個表外檔不算部位檔
        wo.on_read(state, "s", "Read", {"file_path": str(proj / f"note{i}.md")}, str(proj), tp, {})
    _locate(tp)
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})
    assert deny and "目前 0 個" in deny and "表外檔讀了 20 個不算" in deny and "定位三行" not in deny
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)              # ③ 部位檔 1 ＋ 已交三行 → 放行
    (proj / ".claude" / "overview-hub.json").write_text('{"min_overview_evidence": {"part_files": 3}}', encoding="utf-8")
    state2 = {}
    wo.on_read(state2, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    wo.on_read(state2, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    warn, deny, _ = wo.on_edit(state2, "s", f1, tp, {})
    assert deny and "要 ≥3 個，目前 1 個" in deny                                   # 專案可調數字


def test_unmapped_project_requires_a_read_in_same_top_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = tmp_path / "bare"
    (root / ".git").mkdir(parents=True)                                            # 有四標記、沒部位表
    (root / "src").mkdir()
    (root / "docs").mkdir()
    f1 = str(root / "src" / "a.py")
    state = {}
    warn, deny, changed = wo.on_edit(state, "s", f1, "", {})
    assert deny and "沒有部位表" in deny and "「src」至少 1 個檔（目前 0 個）" in deny and not changed
    wo.on_read(state, "s", "Read", {"file_path": str(root / "docs" / "x.md")}, str(root), "", {})   # 別的頂層目錄不算
    warn, deny, _ = wo.on_edit(state, "s", f1, "", {})
    assert deny and "目前 0 個" in deny
    wo.on_read(state, "s", "Read", {"file_path": str(root / "src" / "b.py")}, str(root), "", {})
    assert wo.on_edit(state, "s", f1, "", {}) == (None, None, True)
    key = next(k for k in state["overview_hub"] if "(unmapped)src" in k)
    assert state["overview_hub"][key]["edits"] == 1
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert [e["event"] for e in log] == ["edit_unmapped"] * 3 and log[-1]["deny_reason"] is None
    assert wo.on_edit({}, "s", str(tmp_path / "lonely.py"), "", {}) == (None, None, False)   # 無標記目錄不管


def test_unmapped_deep_file_falls_back_to_vcs_root(tmp_path, monkeypatch):
    """缺口 4：只有 .git、無表；第 5 層的檔以前放行，現在退 VCS 根照無表規則（讀過同頂層一檔才放）。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = tmp_path / "deep"
    (root / ".git").mkdir(parents=True)
    (root / "src" / "a" / "b" / "c").mkdir(parents=True)
    (root / "src" / "other.py").write_text("x", encoding="utf-8")
    deep = str(root / "src" / "a" / "b" / "c" / "widget.py")
    assert wo._project_root_of(deep) is None                                       # 前提：舊規則最多 4 層找不到
    state = {}
    warn, deny, changed = wo.on_edit(state, "s", deep, "", {})
    assert deny and "沒有部位表" in deny and str(root) in deny and "「src」至少 1 個檔（目前 0 個）" in deny
    wo.on_read(state, "s", "PowerShell", {"command": "Get-Content src/other.py"}, str(root), "", {})
    assert wo.on_edit(state, "s", deep, "", {}) == (None, None, True)


def test_unmapped_vcs_fallback_never_takes_home_or_drive_root(tmp_path, monkeypatch):
    import wg_verify_ledger as vl
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    home = tmp_path / "home"
    (home / ".git").mkdir(parents=True)
    deep = home / "a" / "b" / "c" / "d" / "e.py"
    deep.parent.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    assert wo._project_root_of(str(deep)) is None
    assert wo.on_edit({}, "s", str(deep), "", {}) == (None, None, False)          # 家目錄不當根
    monkeypatch.setattr(vl, "find_vcs_root", lambda start: ("git", Path(Path(start).anchor)))
    other = tmp_path / "x" / "a" / "b" / "c" / "d" / "f.py"
    assert wo.on_edit({}, "s", str(other), "", {}) == (None, None, False)         # 磁碟根不當根


def test_unmapped_vcs_fallback_not_used_when_project_has_table(proj, tmp_path, monkeypatch):
    """有部位表的專案不走退路：表上沒列的深層檔行為不變（照舊放行）。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".git").mkdir()
    deep = proj / "Other" / "a" / "b" / "c" / "x.py"
    deep.parent.mkdir(parents=True)
    assert wo._project_root_of(str(deep)) is None
    assert wo.on_edit({}, "s", str(deep), "", {}) == (None, None, False)


def test_readonly_paths_deny_without_inject_and_glob_misses_neighbors(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".claude" / "overview-hub.json").write_text(
        '{"readonly_paths": ["Game/Battle/Gen/**/*.cs", "Game/Battle/_INDEX.md"]}', encoding="utf-8")
    tp = _transcript(tmp_path, ["x"])
    state = {}
    for ro in ("Game/Battle/Gen/A.cs", "Game/Battle/Gen/sub/B.cs", "Game/Battle/_INDEX.md"):
        warn, deny, changed = wo.on_edit(state, "s", str(proj / ro), tp, {})
        assert deny and "readonly_paths（樣式「" in deny and not changed and state == {}      # 命中 deny、不注入
    for nb in ("Game/Battle/Gen2/A.cs", "Game/Battle/_INDEX.md.bak", "Game/Battle/Gen.cs"):
        warn, deny, _ = wo.on_edit({}, "s", str(proj / nb), tp, {})
        assert deny and "樣式「" not in deny and "還沒看過" in deny                      # 鄰目錄走一般流程（注入＋擋）
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert [e["event"] for e in log][:3] == ["edit_readonly"] * 3 and log[0]["deny_reason"] == "readonly"


def test_thinking_channel_allows_with_reminder(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    state = {}
    wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    _locate(tp, block="thinking", precedent="無")
    warn, deny, changed = wo.on_edit(state, "s", f1, tp, {})
    assert deny is None and changed and warn and "thinking" in warn and "放行" in warn
    rec = next(iter(state["overview_hub"].values()))
    assert rec["located_via"] == "thinking" and rec["located_quality"] == "none"
    warn2, deny2, changed2 = wo.on_edit(state, "s", f1, tp, {})                 # 已 located，第二次不再提醒 thinking
    assert deny2 is None and changed2 and "只在 thinking 裡" not in (warn2 or "")
    assert "候選前" in warn2                                                     # A5.3：同檔第 2 次放行的 Edit 附候選（verify_candidates_trigger 驗細節）


# ─── 退回 001：BLOCK 1／2／3／7 ───────────────────────────────────────────────────

LAYER_TABLE = ("| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 層 |\n|---|---|---|---|---|\n"
               "| `Game\\Battle\\` | 戰鬥 | `戰鬥知識導讀-hub索引` | 有 | 主程式集／熱修 |\n")


def test_wrong_layer_then_corrected_passes(proj, tmp_path, monkeypatch):       # BLOCK 1：補正取最後一組
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".claude" / "overview-map.md").write_text(LAYER_TABLE, encoding="utf-8")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    state = {}
    wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥：A.cs\n定位｜根因層：Demo 區\n定位｜前例：共用字典"}]}}, ensure_ascii=False) + "\n")
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})
    assert deny and "填錯層" in deny and "取最後一組" in deny
    _locate(tp)                                                                  # 同管道補交：根因層「邏輯層」沒指層 → 仍擋
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})
    assert deny and "填錯層" in deny
    with open(tp, "a", encoding="utf-8") as f:                                   # 再補一組正確的（熱修）→ 放行
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥：A.cs\n定位｜根因層：熱修層\n定位｜前例：共用字典"}]}}, ensure_ascii=False) + "\n")
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)
    rec = next(iter(state["overview_hub"].values()))
    assert rec["located"] and rec["located_quality"] == "card" and rec["edits"] == 3
    with open(tp, "a", encoding="utf-8") as f:                                   # 錯的在 text、對的在 tool_input 也算
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash",
                "input": {"command": "# 定位｜部位：戰鬥：A.cs\n# 定位｜根因層：主程式集\n# 定位｜前例：共用字典\ntrue"}}]}}, ensure_ascii=False) + "\n")
    state2 = {}
    wo.on_read(state2, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    wo.on_read(state2, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    off = next(iter(state2["overview_hub"].values()))["transcript_offset"]
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥：A.cs\n定位｜根因層：Demo 區\n定位｜前例：共用字典"}]}}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash",
                "input": {"command": "# 定位｜部位：戰鬥：A.cs\n# 定位｜根因層：主程式集\n# 定位｜前例：共用字典\ntrue"}}]}}, ensure_ascii=False) + "\n")
    assert off > 0 and wo.on_edit(state2, "s", f1, tp, {}) == (None, None, True)
    assert next(iter(state2["overview_hub"].values()))["located_via"] == "tool_input"


def test_main_format_rec_is_migrated_not_keyerror(proj, tmp_path, monkeypatch):   # BLOCK 2：舊 state 升級
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    key = f"{str(proj).replace(chr(92), '/').lower()}|戰鬥"
    state = {"overview_hub": {key: {"injected_turn": 1, "injected_at": "t", "transcript_offset": 0,
                                    "reads_after": [], "located": False, "edits": 0, "locate_template": []}}}
    assert wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {}) is None       # 不 KeyError、不重注
    rec = state["overview_hub"][key]
    assert rec["part_files_read"] == [f1] and rec["slices"] == [] and rec["intent"] == "general"
    _locate(tp)
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)
    old = {"overview_hub": {key: {"reads_after": [], "located": False, "edits": 0, "transcript_offset": 0}}}
    warn, deny, _ = wo.on_edit(old, "s", f1, tp, {})                                          # 直接 on_edit 也不炸
    assert deny and "目前 0 個" in deny


def test_unmapped_project_hub_json_is_own_config(tmp_path, monkeypatch):          # BLOCK 3：無表專案 hub.json 能自救
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = tmp_path / "bare"
    (root / ".git").mkdir(parents=True)
    (root / ".claude").mkdir()
    (root / "src").mkdir()
    hub = root / ".claude" / "overview-hub.json"
    hub.write_text('{"foo": 1}', encoding="utf-8")
    tp = _transcript(tmp_path, ["x"])
    assert wo._own_config_layer(str(hub)) == (True, root)
    warn, deny, changed = wo.on_edit({}, "s", str(hub), tp, {})
    assert deny is None and not changed and warn and "放行以便修復" in warn and "未知的設定鍵「foo」" in warn
    warn, deny, _ = wo.on_edit({}, "s", str(root / "src" / "a.py"), tp, {})                    # 其他檔仍被設定錯誤擋
    assert deny and "foo" in deny
    hub.write_text("{}", encoding="utf-8")
    assert wo.on_edit({}, "s", str(hub), tp, {}) == (None, None, False)
    assert wo._own_config_layer(str(tmp_path / "nowhere" / ".claude" / "overview-hub.json")) == (False, None)


def test_transcript_unreadable_denies_even_if_located(proj, tmp_path, monkeypatch):   # BLOCK 7：真開檔
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    state = {}
    wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    _locate(tp)
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)
    rec = next(iter(state["overview_hub"].values()))
    assert rec["located"] is True
    locked = tmp_path / "dir_as_transcript"                                       # 存在但開不了（目錄）
    locked.mkdir()
    assert oh.transcript_readable(str(locked)) == (False, "unreadable")
    assert oh.transcript_readable("") == (False, "empty_path")
    assert oh.transcript_readable(str(tmp_path / "nope.jsonl")) == (False, "missing")
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert oh.transcript_readable(str(empty)) == (False, "empty")
    assert oh.transcript_readable(tp) == (True, "")
    for bad, word in ((str(locked), "開不了"), ("", "欄位為空"), (str(tmp_path / "nope.jsonl"), "不存在")):
        warn, deny, _ = wo.on_edit(state, "s", f1, bad, {})
        assert deny and word in deny and "環境異常" in deny
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert [e["deny_reason"] for e in log[-3:]] == ["transcript_missing"] * 3


def test_inject_record_and_log_carry_intent_slices_layer(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".claude" / "memory" / "shared" / "戰鬥" / "戰鬥知識導讀-hub索引.md").write_text(FIVE_CARD, encoding="utf-8")
    state = {"turn_intent": "debug"}
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), "", {})
    assert txt.index("[已知病灶]") < txt.index("[驗法]")
    rec = next(iter(state["overview_hub"].values()))
    assert rec["intent"] == "debug" and rec["slices"] == ["defects", "verify", "authority"]
    log = json.loads((tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()[0])
    assert log["intent"] == "debug" and log["slices"] == ["defects", "verify", "authority"] and log["layer"] == "project_mapped"
    state2 = {}
    assert wo.on_prompt(state2, "s", f"看 {f1}", "", {}, intent="perf")
    assert state2["turn_intent"] == "perf" and next(iter(state2["overview_hub"].values()))["slices"] == ["verify", "defects", "what"]
    state3 = {"turn_intent": "bogus"}                                              # 不在十鍵 → 當 general
    wo.on_read(state3, "s", "Read", {"file_path": f1}, str(proj), "", {})
    assert next(iter(state3["overview_hub"].values()))["intent"] == "general"
