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
def _temp_rules_off(monkeypatch):
    """假專案都建在 pytest tmp 下：關掉暫存規則（TEMP_COPY_NOT_PROJECT），B14 的案自己再開。"""
    monkeypatch.setenv("WG_TEMP_RULES", "off")


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


def test_045_bash_comment_lines_stripped_head_on_next_line_is_a_read():
    """規則 BASH_COMMENT_LINES_STRIPPED：定位三行放 # 註解、下一行 head 讀檔 → 認得到（舊 regex 只認字串開頭）。"""
    cmd = "# 定位｜部位：x\n# 定位｜根因層：y\n# 定位｜前例：z\nhead -20 C:/a/b.py"
    assert oh.read_paths_from_tool("Bash", {"command": cmd}, "C:/w") == ["C:/a/b.py"]
    assert oh.read_paths_from_tool("Bash", {"command": "echo a\nsed -n 1,5p C:/a/c.py"}, "C:/w") == ["C:/a/c.py"]


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
    Path(f1).write_text("x", encoding="utf-8")                                     # Bash cat 讀的要是實檔才算（BASH_READONLY_COUNTS_AS_READ）

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


# ─── 卡片目錄單源 card_mem_dir：根層／根層 worktree／一般專案 ─────────────────────

ROOT_MAP = "| `hooks/` | hook 層 | `hooks導讀` | 部分 |\n"


def _link_wt(live: Path, wt: Path, name: str = "wt") -> None:
    """把 wt 接成 live 的 git worktree 結構，與 `git worktree add` 寫的同一組檔：管理目錄 live/.git/worktrees/<name>/ 裡的
    gitdir（反向指回 wt/.git）與 commondir（../..），wt/.git 檔指到管理目錄。is_root_worktree 的定義案用真 worktree，見下。"""
    adm = live / ".git" / "worktrees" / name
    adm.mkdir(parents=True, exist_ok=True)
    (adm / "gitdir").write_text(f"{wt / '.git'}\n", encoding="utf-8")
    (adm / "commondir").write_text("../..\n", encoding="utf-8")
    (wt / ".git").write_text(f"gitdir: {adm}\n", encoding="utf-8")


def _root_world(tmp_path, monkeypatch):
    """tmp 造 live 根層（fake claude）、它的 worktree（卡在 <wt>/memory）、一般專案（不是 live 的 worktree、表不同）。"""
    live, wt, proj = tmp_path / "claude", tmp_path / "claude-wt" / "track-x", tmp_path / "proj"
    for r, body in ((live, "live 卡：pythonw 無 stdio"), (wt, "worktree 卡：HOME 覆寫指錯")):
        (r / ".claude").mkdir(parents=True)
        (r / "hooks").mkdir()
        (r / "memory" / "CC").mkdir(parents=True)
        (r / ".claude" / "overview-map.md").write_text(ROOT_MAP, encoding="utf-8", newline="\n")
        (r / "memory" / "CC" / "hooks導讀.md").write_text(f"# hooks 導讀\n病灶：{body}", encoding="utf-8")
    _link_wt(live, wt, "track-x")
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    (proj / "memory" / "CC").mkdir(parents=True)
    (proj / "hooks").mkdir()
    (proj / ".claude" / "overview-map.md").write_text(ROOT_MAP + "| `src/` | 主程式 | 無 | 無 |\n", encoding="utf-8", newline="\n")
    (proj / ".claude" / "memory" / "shared" / "hooks導讀.md").write_text("# 專案卡\n病灶：專案 .claude/memory 這張", encoding="utf-8")
    (proj / "memory" / "CC" / "hooks導讀.md").write_text("# 誤撈\n病灶：專案根 memory 同名卡", encoding="utf-8")
    import wg_core
    monkeypatch.setattr(wo, "CLAUDE_DIR", live)
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", live)
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    return live, wt, proj


def test_024_root_worktree_card_search_uses_data_root_not_worktree_copy(tmp_path, monkeypatch):
    """024 修正：根層 worktree 的導讀卡補搜也以資料根（card_mem_dir）為準。資料根（live）已沒有這張卡、worktree 的 memory/
    還留著開分支時的舊副本 → 不撿舊副本、列為 missing，也沒搜 worktree；一般專案在非預設目錄的卡照舊補搜得到。"""
    live, wt, proj = _root_world(tmp_path, monkeypatch)
    row = {"status": "部分", "cards": ["hooks導讀"], "part_short": "hook 層", "part": "hooks/"}
    (live / "memory" / "CC" / "hooks導讀.md").unlink()
    paths, miss = wo._resolve_row_cards(wt, row, {})
    assert paths == [] and miss and miss["missing"] == ["hooks導讀"]
    assert not any(Path(s) == wt or str(wt) in s for s in miss["searched"])
    (proj / ".claude" / "memory" / "shared" / "hooks導讀.md").unlink()
    paths, miss = wo._resolve_row_cards(proj, row, {})
    assert [p.parent.name for p in paths] == ["CC"] and miss and miss["missing"] == []      # 專案根 memory/CC 那張照撿


def test_card_mem_dir_root_worktree_project_and_no_map(tmp_path, monkeypatch):
    live, wt, proj = _root_world(tmp_path, monkeypatch)
    assert oh.card_mem_dir(live, live) == live / "memory"
    assert oh.card_mem_dir(Path(str(live).upper()), live) == Path(str(live).upper()) / "memory"   # 正規化後相同也算根層
    assert oh.card_mem_dir(wt, live) == live / "memory"                                # 根層 worktree：卡是資料，讀 live 那批
    assert oh.card_mem_dir(proj, live) == proj / ".claude" / "memory"                  # 反例：不是 live 的 worktree＝一般專案
    nomap = tmp_path / "bare"
    nomap.mkdir()
    assert oh.card_mem_dir(nomap, live) == nomap / ".claude" / "memory"                # 反例：沒有表＝一般專案
    nolive = tmp_path / "no-live-map"
    nolive.mkdir()
    assert oh.card_mem_dir(wt, nolive) == wt / ".claude" / "memory"                    # 反例：wt 不是 nolive 的 worktree
    assert oh.is_root_worktree(wt, live) is True and oh.is_root_worktree(wt, nolive) is False
    import wg_verify_ledger as vl
    assert vl.is_root_worktree(wt, live) is True and vl.is_root_worktree(proj, live) is False   # 舊名委派 lib 本體


def test_cards_for_root_worktree_live_and_project_same_name_counterexample(tmp_path, monkeypatch):
    live, wt, proj = _root_world(tmp_path, monkeypatch)
    row = oh.parse_map(ROOT_MAP)[0]
    assert wo._cfg({}, wt)["_layer"] == "project_mapped"                              # 層名判定不變
    assert wo._cards_for(wt, row, wo._cfg({}, wt)) == [live / "memory" / "CC" / "hooks導讀.md"]   # 同名卡內容不同，拿 live 那張
    assert wo._cards_for(live, row, wo._cfg({}, live)) == [live / "memory" / "CC" / "hooks導讀.md"]
    got = wo._cards_for(proj, row, wo._cfg({}, proj))                                  # 反例：兩處同名卡，只拿 .claude/memory
    assert got == [proj / ".claude" / "memory" / "shared" / "hooks導讀.md"]


def test_inject_end_to_end_in_root_worktree_has_card_text(tmp_path, monkeypatch):
    live, wt, _ = _root_world(tmp_path, monkeypatch)
    tp = _transcript(tmp_path, ["x"])
    target = str(wt / "hooks" / "wg_x.py")
    warn, deny, changed = wo.on_edit({}, "s", target, tp, {})                          # 改檔觸發注入（沒先讀 → 擋，理由帶整張卡）
    assert deny and "pythonw 無 stdio" in deny and "沒有可注入的導讀卡" not in deny and changed   # live 那張
    txt = wo.on_read({}, "s", "Read", {"file_path": target}, str(wt), tp, {})
    assert txt and "pythonw 無 stdio" in txt and "HOME 覆寫指錯" not in txt and "沒有可注入的導讀卡" not in txt   # 反例：不是 worktree 的舊副本


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
    import hub_config
    monkeypatch.setattr(hub_config, "validate_path_bases", _bug)                  # 005：驗證本體搬到 lib/hub_config
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
    (root / "src" / "b.py").write_text("x", encoding="utf-8")                     # src 有可讀的既有檔，閘才要求讀（B5：沒檔可讀不要求）
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


# ─── 件二：表上有卡、預設目錄找不到 → 搜 repo；確定找不到一律擋 ───────────────────────

_CARD = "戰鬥知識導讀-hub索引"


def _move_card(proj, dest_dir):
    src = proj / ".claude" / "memory" / "shared" / "戰鬥" / f"{_CARD}.md"
    if dest_dir is None:
        src.unlink()
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    return src.replace(dest_dir / src.name)


def test_card_in_default_dir_unchanged(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    txt = wo.on_read({}, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "A.cs")}, str(proj), tp, {})
    assert "戰鬥導讀" in txt and "不在預設目錄" not in txt and "在 repo 裡找不到" not in txt


def test_card_only_in_aidocs_atoms_is_found_and_flagged(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    moved = _move_card(proj, proj / "_AIDocs" / "_atoms" / "x")
    tp = _transcript(tmp_path, ["x"])
    state = {}
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    assert "戰鬥導讀" in txt and f"表上的卡在 {moved}，不在預設目錄；請更新表或搬卡" in txt
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    _locate(tp)
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)                 # 找到 → 照正常判定放行


def test_card_missing_everywhere_denies_even_after_reads_and_locate(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    _move_card(proj, None)
    tp = _transcript(tmp_path, ["x"])
    state = {}
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    assert f"`{_CARD}` 在 repo 裡找不到" in txt
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    _locate(tp)
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})                             # 反例：讀過檔＋交三行也擋
    assert deny and f"部位【戰鬥】表上寫的導讀卡 `{_CARD}` 在 repo 裡找不到" in deny
    assert str(proj / ".claude" / "memory") in deny and str(proj) in deny and "已搜完" in deny
    assert "不准繞過（不准改寫表、不准改用其他卡、不准用 Bash 寫檔）" in deny and "等使用者補卡或改表" in deny
    warn, deny2, _ = wo.on_edit({}, "s", f1, tp, {})                               # 沒讀過就改：同樣是找不到卡的擋
    assert deny2.startswith(f"[Guardian:OverviewHub] 部位【戰鬥】表上寫的導讀卡 `{_CARD}`")
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert [e["deny_reason"] for e in log if e["event"] == "edit_card_missing"] == ["card_missing", "card_missing"]
    _move_card_back = proj / "Game" / f"{_CARD}.md"                               # 卡出現後恢復正常判定
    _move_card_back.write_text("# 戰鬥導讀\n病灶：共用字典", encoding="utf-8")
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})
    assert deny and "還沒看過這個部位的導讀卡" in deny and "戰鬥導讀" in deny and "不在預設目錄" in deny


def test_status_none_row_unchanged(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tp = _transcript(tmp_path, ["x"])
    state = {}
    v1 = str(proj / "Vendor" / "a.cs")
    wo.on_read(state, "s", "Read", {"file_path": v1}, str(proj), tp, {})
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Vendor" / "b.cs")}, str(proj), tp, {})
    _locate(tp, part="框架")
    assert wo.on_edit(state, "s", v1, tp, {}) == (None, None, True)                 # 狀態「無」不要求卡


def test_card_search_timeout_denies_and_says_so(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    _move_card(proj, proj / "deep" / "x")                                           # 卡在 repo 裡，但搜不到那裡就逾時
    ticks = iter(range(0, 1000, 1))
    monkeypatch.setattr(wo, "_clock", lambda: next(ticks))                          # 每問一次時間過 1 秒
    tp = _transcript(tmp_path, ["x"])
    warn, deny, _ = wo.on_edit({}, "s", str(proj / "Game" / "Battle" / "A.cs"), tp, {})
    assert deny and f"`{_CARD}` 在 repo 裡找不到" in deny and "搜尋逾時（1.5 秒）沒搜完" in deny


def _two_card_table(proj):
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
        f"| `Game\\Battle\\` | 戰鬥 | `{_CARD}`；根因層另有 `戰鬥根因層` | 有 |\n", encoding="utf-8")


def test_two_cards_both_present_unchanged(proj, tmp_path, monkeypatch):
    """003-4 正例：表上兩張卡都在預設目錄 → 照舊（注入兩張、交三行讀檔後放行）。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    _two_card_table(proj)
    (proj / ".claude" / "memory" / "shared" / "戰鬥" / "戰鬥根因層.md").write_text("# 根因層\n共用字典", encoding="utf-8")
    state, tp = {}, _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    assert "在 repo 裡找不到" not in txt and "不在預設目錄" not in txt
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    _locate(tp)
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)


def test_two_cards_one_missing_denies_listing_only_that_one(proj, tmp_path, monkeypatch):
    """003-4 反例：一張在、一張哪裡都找不到 → 對該部位 deny，訊息只列缺的那張；讀檔＋交三行也照擋。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    _two_card_table(proj)
    state, tp = {}, _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    assert "戰鬥導讀" in txt and "表上寫的導讀卡 `戰鬥根因層` 在 repo 裡找不到" in txt
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    _locate(tp)
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})
    assert deny and "表上寫的導讀卡 `戰鬥根因層` 在 repo 裡找不到" in deny and f"`{_CARD}`" not in deny
    warn, deny, _ = wo.on_edit({}, "s", f1, tp, {})                                # 沒讀過就改：同一種擋
    assert deny.startswith("[Guardian:OverviewHub] 部位【戰鬥】表上寫的導讀卡 `戰鬥根因層`")


def _wild_table(proj, card):
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
        f"| `Game\\Battle\\` | 戰鬥 | `{card}` | 有 |\n", encoding="utf-8")


def test_006_8_wildcard_card_found_by_glob(proj, tmp_path, monkeypatch):
    """表上卡名 `戰鬥*`：預設目錄有 `戰鬥知識導讀-hub索引.md` → 不報缺卡（沿用 glob 語意）。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    _wild_table(proj, "戰鬥*")
    state, tp = {}, _transcript(tmp_path, ["x"])
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    assert "戰鬥導讀" in txt and "在 repo 裡找不到" not in txt
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    _locate(tp)
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)


def test_006_8_wildcard_card_matching_nothing_denies(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    _wild_table(proj, "不存在的卡*")
    warn, deny, _ = wo.on_edit({}, "s", str(proj / "Game" / "Battle" / "A.cs"), _transcript(tmp_path, ["x"]), {})
    assert deny and "`不存在的卡*` 在 repo 裡找不到" in deny
    (proj / "docs").mkdir()
    (proj / "docs" / "不存在的卡-其實在這.md").write_text("# x", encoding="utf-8")       # repo 搜尋對含 * 的卡名用 fnmatch
    assert wo._search_cards(proj, ["不存在的卡*"])["found"] == [proj / "docs" / "不存在的卡-其實在這.md"]


@pytest.mark.parametrize("card", ["*Missing", "Missing.v2*"])
def test_009_7_wildcard_card_leading_star_or_dot_is_still_a_card(proj, tmp_path, monkeypatch, card):
    """009-4.7：`*Missing`、`Missing.v2*` 是卡名 glob，不在解析時消失：找不到 → 擋；repo 有對得上的卡 → 搜得到。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    _wild_table(proj, card)
    assert oh.parse_map((proj / ".claude" / "overview-map.md").read_text(encoding="utf-8"))[0]["cards"] == [card]
    warn, deny, _ = wo.on_edit({}, "s", str(proj / "Game" / "Battle" / "A.cs"), _transcript(tmp_path, ["x"]), {})
    assert deny and f"`{card}` 在 repo 裡找不到" in deny
    (proj / "docs").mkdir()
    hit = proj / "docs" / (card.replace("*", "X") + ".md")
    hit.write_text("# x", encoding="utf-8")
    assert wo._search_cards(proj, [card])["found"] == [hit]


def test_009_7_extension_only_glob_is_file_pattern_not_card():
    """純副檔名樣式（`*.bytes`）與含路徑分隔字元的照舊不當卡；同列的真卡名照收。"""
    rows = oh.parse_map("| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
                     "| `Game\\Battle\\` | 戰鬥 | `*.bytes` `Data/*.json` `戰鬥*` | 有 |\n")
    assert rows[0]["cards"] == ["戰鬥*"]


def test_search_cards_skips_git_node_modules_distant_and_worktrees(tmp_path):
    for d in (".git", "node_modules", "_distant", ".claude/worktrees/wt"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
        (tmp_path / d / "c-x.md").write_text("x", encoding="utf-8")
    r = wo._search_cards(tmp_path, ["c_x"])
    assert r["found"] == [] and r["missing"] == ["c_x"] and not r["timed_out"]
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "c-x.md").write_text("x", encoding="utf-8")                # 底線換連字號的變體
    assert wo._search_cards(tmp_path, ["c_x"])["found"] == [tmp_path / "docs" / "c-x.md"]


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
    assert "【戰鬥】候選" in warn2                                               # A5.3：同檔第 2 次放行的 Edit 附候選（沒內容是一行版；verify_candidates_trigger 驗細節）


# ─── 退回 001：BLOCK 1／2／3／7 ───────────────────────────────────────────────────

LAYER_TABLE = ("| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 層 |\n|---|---|---|---|---|\n"
               "| `Game\\Battle\\` | 戰鬥 | `戰鬥知識導讀-hub索引` | 有 | 主程式集／熱修 |\n")


def test_reading_path_layer_number_is_not_a_layer_the_root_cause_line_must_name():
    """層欄的「第 N 層」是閱讀路徑層次軸，由程式依路徑推：根因層那行不用寫它（只有它或配「單層」都不擋）；
    和要人填的層混寫時，只要求寫出要人填的那幾個。"""
    vals = {"根因": "邏輯層：判斷式寫反"}
    assert wo._layer_mismatch({"layer": "第2層"}, vals) is None
    assert wo._layer_mismatch({"layer": "第 3 層"}, vals) is None
    mixed = wo._layer_mismatch({"layer": "主程式集／第2層"}, vals)
    assert mixed and "主程式集" in mixed and "第2層" not in mixed
    assert wo._layer_mismatch({"layer": "主程式集／第2層"}, {"根因": "主程式集：判斷式寫反"}) is None
    assert wo._layer_mismatch({"layer": "主程式集／熱修"}, vals), "要人填的層照擋"


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


# ─── codex 補件：_same_dir 不撞名、長路徑前綴、委派失敗不放行 ─────────────────────

def _base_overview_hub():
    """基底 9ab945f 的 lib/overview_hub.py（版控讀出、載成獨立模組），當 find_map／_same_dir 的預期值來源。"""
    import subprocess
    import types
    src = subprocess.run(["git", "-C", str(HOOKS_DIR.parent), "show", "9ab945f:lib/overview_hub.py"],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    mod = types.ModuleType("overview_hub_base_9ab945f")
    exec(compile(src, "overview_hub@9ab945f", "exec"), mod.__dict__)
    return mod, src


def test_find_map_same_dir_unchanged_from_base_with_case_variant_stop_at(tmp_path, monkeypatch):
    import inspect
    base, src = _base_overview_hub()
    assert inspect.getsource(oh._same_dir) in src and inspect.getsource(oh.find_map) in src   # 原版兩支一字不動
    assert oh._same_dir is not oh._same_dir_norm
    proj = tmp_path / "Proj"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text("| `a/` | 甲 | 無 | 無 |\n", encoding="utf-8")
    deep = proj / "Sub" / "Deep"
    deep.mkdir(parents=True)
    monkeypatch.setattr(oh, "_home", lambda: tmp_path / "nohome")
    monkeypatch.setattr(base, "_home", lambda: tmp_path / "nohome")
    for stop in (None, proj / "Sub", Path(str(proj / "Sub").upper()), Path(str(proj / "Sub").lower()),
                 Path(str(proj).upper()), tmp_path / "unrelated"):
        assert oh.find_map(str(deep / "x.py"), stop) == base.find_map(str(deep / "x.py"), stop), stop


def test_is_root_worktree_long_path_prefix_is_same_dir(tmp_path):
    live = tmp_path / "claude"
    (live / ".claude").mkdir(parents=True)
    (live / ".claude" / "overview-map.md").write_text(ROOT_MAP, encoding="utf-8", newline="\n")
    prefixed = Path("\\\\?\\" + str(live))
    assert oh.is_root_worktree(prefixed, live) is False                    # 同一目錄加長路徑前綴不是 worktree
    assert oh.card_mem_dir(prefixed, live) == live / "memory"


def test_verify_ledger_delegation_failure_returns_false_and_gate_still_blocks(tmp_path, monkeypatch, capsys):
    import types
    import wg_verify_ledger as vl
    q6 = HOOKS_DIR / "verify" / "fixtures" / "v6" / "q6" / "overview-map.md"
    rows = oh.parse_map(q6.read_text(encoding="utf-8"))
    live, wt = tmp_path / "live", tmp_path / "wt"
    for d in (live, wt):
        (d / ".claude").mkdir(parents=True)
        (d / ".claude" / "overview-map.md").write_bytes(q6.read_bytes())
    _link_wt(live, wt)
    monkeypatch.setattr(vl, "CLAUDE_DIR", live)
    mod = str(wt / "hooks" / "x.py")
    mf = [{"path": mod, "tool": "Edit", "session_id": "s", "turn_seq": 5, "last_turn_seq": 5}]
    done = {"turn_seq": 5, "tool": "Bash", "cmd": "python -X utf8 -m pytest -q hooks/verify/verify_x.py", "exit_code": 0,
            "at": "", "project_root": str(wt), "cwd": str(wt), "env": {},
            "sentinels": [{"name": "PYTEST", "verdict": "PASS", "kv": {}}, {"name": "PYTEST_MEASURE", "verdict": "DONE", "kv": {}}]}

    def lookup(path):
        row = oh.match_row(path, wt, rows)
        return (wt, row) if row else None
    assert vl.measure_gate_reason(mf, [done], 5, lookup, vl.MEASURE_DEFAULTS)[0] is None   # 正常委派：worktree 認目標 verify
    monkeypatch.setitem(sys.modules, "overview_hub", types.ModuleType("overview_hub"))     # 混載：舊版模組沒有這支
    assert vl.is_root_worktree(wt, live) is False
    assert "[verify_ledger] is_root_worktree 委派失敗" in capsys.readouterr().err
    reason, _ = vl.measure_gate_reason(mf, [done], 5, lookup, vl.MEASURE_DEFAULTS)
    assert reason and "[Guardian:MeasureGate]" in reason                                 # 反例：委派失敗不得放行


def test_verify_ledger_delegation_raising_attribute_error_returns_false(tmp_path, monkeypatch, capsys):
    import types
    import wg_verify_ledger as vl
    fake = types.ModuleType("overview_hub")

    def boom(root, claude_dir):
        raise AttributeError("'NoneType' object has no attribute 'read_bytes'")
    fake.is_root_worktree = boom
    monkeypatch.setitem(sys.modules, "overview_hub", fake)
    assert vl.is_root_worktree(tmp_path / "wt", tmp_path / "live") is False
    err = capsys.readouterr().err
    assert "[verify_ledger] is_root_worktree 委派失敗：AttributeError" in err


def test_same_dir_norm_long_prefix_any_case():
    unc = Path("\\\\localhost\\nosuchshare_a3")                                             # localhost：不存在的分享也秒回
    assert oh._same_dir_norm(Path("\\\\?\\unc\\localhost\\nosuchshare_a3"), unc) is True   # 小寫 unc 不得剝成相對路徑
    assert oh._same_dir_norm(Path("\\\\?\\UNC\\localhost\\nosuchshare_a3"), unc) is True
    assert oh._same_dir_norm(Path("\\\\?\\c:\\x"), Path("C:\\x")) is True
    assert oh._same_dir_norm(Path("\\\\?\\unc\\localhost\\nosuchshare_a3"), Path("\\\\localhost\\other_a3")) is False


def test_verify_ledger_delegation_multiline_error_is_one_stderr_line(tmp_path, monkeypatch, capsys):
    import types
    import wg_verify_ledger as vl
    fake = types.ModuleType("overview_hub")

    def boom(root, claude_dir):
        raise AttributeError("first\nsecond")
    fake.is_root_worktree = boom
    monkeypatch.setitem(sys.modules, "overview_hub", fake)
    assert vl.is_root_worktree(tmp_path / "wt", tmp_path / "live") is False
    lines = [l for l in capsys.readouterr().err.splitlines() if l.strip()]
    assert len(lines) == 1 and "AttributeError: first second" in lines[0]


# ─── is_root_worktree 定義：真 git worktree（.git 檔指回 <live>/.git/worktrees/），不看部位表 ─────────

@pytest.fixture
def git(tmp_path):
    """隔離全域／系統 git 設定的 git 執行器（作者資訊走環境變數）。"""
    import subprocess
    cfg = tmp_path / "gitconfig-empty"
    cfg.write_text("", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    env.update({"GIT_CONFIG_GLOBAL": str(cfg), "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})

    def run(*args):
        r = subprocess.run(["git", *args], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert r.returncode == 0, f"git {args}: {r.stderr}"
        return r.stdout
    return run


def _git_live(git, live: Path, map_bytes: bytes) -> None:
    live.mkdir(parents=True)
    git("init", "-q", str(live))
    git("-C", str(live), "config", "core.autocrlf", "false")
    (live / ".claude").mkdir()
    (live / ".claude" / "overview-map.md").write_bytes(map_bytes)
    git("-C", str(live), "add", ".claude/overview-map.md")
    git("-C", str(live), "commit", "-q", "-m", "init")


def _copy_map(live: Path, d: Path) -> Path:
    (d / ".claude").mkdir(parents=True)
    (d / ".claude" / "overview-map.md").write_bytes((live / ".claude" / "overview-map.md").read_bytes())
    return d


def test_is_root_worktree_real_git_worktrees_inside_and_outside_live(tmp_path, git):
    live = tmp_path / "live"
    _git_live(git, live, ROOT_MAP.encode("utf-8"))
    outside, inside = tmp_path / "wt-out", live / ".claude" / "worktrees" / "x"
    git("-C", str(live), "worktree", "add", "-q", "-b", "wt-out", str(outside))
    git("-C", str(live), "worktree", "add", "-q", "-b", "wt-in", str(inside))
    assert oh.is_root_worktree(outside, live) is True                                  # live 之外
    assert oh.is_root_worktree(inside, live) is True                                   # live 之下（原生 EnterWorktree 的位置）
    assert oh.card_mem_dir(inside, live) == live / "memory"                            # 根層 worktree 讀 live 的卡
    (outside / ".claude" / "overview-map.md").write_bytes(b"| `x/` | other | none | none |\n")
    assert oh.is_root_worktree(outside, live) is True                                  # 改了部位表仍是根層 worktree（身分只看 git）
    assert oh.card_mem_dir(outside, live) == live / "memory"                           # 卡照讀 live 那批


def test_is_root_worktree_rejects_lookalike_folders(tmp_path, git):
    live = tmp_path / "live"
    _git_live(git, live, ROOT_MAP.encode("utf-8"))
    plain = _copy_map(live, live / "fixture")
    assert oh.is_root_worktree(plain, live) is False                                   # 反例：相同表、沒有 .git
    assert oh.card_mem_dir(plain, live) == plain / ".claude" / "memory"
    with_dir = _copy_map(live, live / "fixture-dotgit-dir")
    (with_dir / ".git").mkdir()
    assert oh.is_root_worktree(with_dir, live) is False                                # 反例：.git 是目錄
    other = tmp_path / "other"
    _git_live(git, other, ROOT_MAP.encode("utf-8"))
    (other / ".git" / "worktrees" / "z").mkdir(parents=True)
    foreign = _copy_map(live, tmp_path / "foreign")
    (foreign / ".git").write_text(f"gitdir: {other / '.git' / 'worktrees' / 'z'}\n", encoding="utf-8")
    assert oh.is_root_worktree(foreign, live) is False                                 # 反例：指到別的 repo 的 worktrees/
    bad = _copy_map(live, tmp_path / "bad-format")
    (bad / ".git").write_text("not a gitdir line\n", encoding="utf-8")
    assert oh.is_root_worktree(bad, live) is False                                     # 反例：格式不對
    git("-C", str(live), "worktree", "add", "-q", "-b", "real", str(tmp_path / "real"))
    assert oh.is_root_worktree(tmp_path / "real", live) is True                        # 正例對照


def test_is_root_worktree_rejects_forged_dot_git(tmp_path, git):
    """一個普通目錄只寫一行 `.git` 指到 live 的 worktrees/ 底下，不算根層 worktree：管理目錄要真的登記這棵樹
    （gitdir 反向指回它的 .git、commondir 指到 live 的 .git）。舊碼只看 .git 指向就認，可拿到量尺免全量。console codex 審 ec4f9e9 WARN 2。"""
    live = tmp_path / "live"
    _git_live(git, live, ROOT_MAP.encode("utf-8"))
    real = tmp_path / "real"
    git("-C", str(live), "worktree", "add", "-q", "-b", "real", str(real))
    adm = live / ".git" / "worktrees" / "real"
    assert oh.is_root_worktree(real, live) is True                                     # 對照：真 worktree
    nowhere = _copy_map(live, tmp_path / "nowhere")
    (nowhere / ".git").write_text(f"gitdir: {live / '.git' / 'worktrees' / 'nonexistent'}\n", encoding="utf-8")
    assert oh.is_root_worktree(nowhere, live) is False                                 # 反例：指到不存在的管理目錄
    empty_adm = live / ".git" / "worktrees" / "empty"
    empty_adm.mkdir()
    hollow = _copy_map(live, tmp_path / "hollow")
    (hollow / ".git").write_text(f"gitdir: {empty_adm}\n", encoding="utf-8")
    assert oh.is_root_worktree(hollow, live) is False                                  # 反例：管理目錄是空的（沒有 gitdir／commondir）
    thief = _copy_map(live, tmp_path / "thief")
    (thief / ".git").write_text(f"gitdir: {adm}\n", encoding="utf-8")
    assert oh.is_root_worktree(thief, live) is False                                   # 反例：借用別棵樹的管理目錄（反向指回 real）
    assert oh.card_mem_dir(thief, live) == thief / ".claude" / "memory"


def test_is_root_worktree_relative_gitdir_resolved_against_root(tmp_path, git):
    live = tmp_path / "live"
    _git_live(git, live, ROOT_MAP.encode("utf-8"))
    rel = tmp_path / "rel"
    git("-C", str(live), "worktree", "add", "-q", "-b", "rel", str(rel))              # 真 worktree，再把 .git 改寫成相對路徑
    (rel / ".git").unlink()                                                            # Windows 的 git 把 .git 設成隱藏檔，不能直接覆寫
    (rel / ".git").write_text("gitdir: ../live/.git/worktrees/rel\n", encoding="utf-8")
    assert oh.is_root_worktree(rel, live) is True                                      # 相對路徑以 <root> 為基準
    other = tmp_path / "other"
    (other / ".git" / "worktrees" / "rel").mkdir(parents=True)
    rel2 = _copy_map(live, tmp_path / "rel2")
    (rel2 / ".git").write_text("gitdir: ../other/.git/worktrees/rel\n", encoding="utf-8")
    assert oh.is_root_worktree(rel2, live) is False                                    # 反例：相對路徑解析到別處


def test_unreadable_dot_git_says_so_on_one_stderr_line_and_is_not_root_git_worktree(tmp_path, monkeypatch, capsys, git):
    live = tmp_path / "live"
    _git_live(git, live, ROOT_MAP.encode("utf-8"))
    root = tmp_path / "wt"
    git("-C", str(live), "worktree", "add", "-q", "-b", "x", str(root))
    assert oh.is_root_git_worktree(root, live) is True                                 # 對照：讀得到就是
    capsys.readouterr()
    real_read_text = Path.read_text

    def deny(self, *a, **kw):
        if self.name == ".git":
            raise PermissionError("拒絕存取\n第二行")                                      # 換行要壓成空白
        return real_read_text(self, *a, **kw)
    monkeypatch.setattr(Path, "read_text", deny)
    assert oh.is_root_git_worktree(root, live) is False
    err_lines = capsys.readouterr().err.splitlines()
    assert len(err_lines) == 1, err_lines                                              # 反例：舊碼靜默回 False
    assert err_lines[0].startswith("[overview_hub] 讀不到 ") and str(root / ".git") in err_lines[0]
    assert "PermissionError: 拒絕存取 第二行" in err_lines[0] and err_lines[0].endswith("當成非根層 worktree")


def test_measure_gate_fixture_with_same_map_is_not_root_worktree(tmp_path, monkeypatch, git):
    import wg_verify_ledger as vl
    q6 = HOOKS_DIR / "verify" / "fixtures" / "v6" / "q6" / "overview-map.md"
    rows = oh.parse_map(q6.read_text(encoding="utf-8"))
    live = tmp_path / "live"
    _git_live(git, live, q6.read_bytes())
    wt = tmp_path / "wt"
    git("-C", str(live), "worktree", "add", "-q", "-b", "wt", str(wt))
    fixture = _copy_map(live, live / "fixture")
    monkeypatch.setattr(vl, "CLAUDE_DIR", live)

    def gate(root):
        mf = [{"path": str(root / "hooks" / "x.py"), "tool": "Edit", "session_id": "s", "turn_seq": 5, "last_turn_seq": 5}]
        done = {"turn_seq": 5, "tool": "Bash", "cmd": "python -X utf8 -m pytest -q hooks/verify/verify_x.py", "exit_code": 0,
                "at": "", "project_root": str(root), "cwd": str(root), "env": {},
                "sentinels": [{"name": "PYTEST", "verdict": "PASS", "kv": {}},
                              {"name": "PYTEST_MEASURE", "verdict": "DONE", "kv": {}}]}

        def lookup(path):
            row = oh.match_row(path, root, rows)
            return (root, row) if row else None
        return vl.measure_gate_reason(mf, [done], 5, lookup, vl.MEASURE_DEFAULTS)[0]
    assert gate(wt) is None                                                            # 真 worktree：認目標 verify 的 pytest DONE
    reason = gate(fixture)
    assert reason and "[Guardian:MeasureGate]" in reason and "PYTEST_MEASURE" not in reason   # 反例：fixture 不走 worktree 規則


# ─── 網路路徑（UNC）：不呼叫 realpath，直接不是根層 worktree ─────────────────────────

@pytest.fixture
def unc_realpath_guard(monkeypatch):
    """realpath 遇到網路路徑就記下並拋例外（真環境會卡數秒）；本機路徑照常算。"""
    real = os.path.realpath
    hits = []

    def guarded(p, *a, **kw):
        s = str(p).replace("\\", "/").lower()
        if s.startswith("//?/unc/") or (s.startswith("//") and not s.startswith(("//?/", "//./"))):
            hits.append(str(p))
            raise AssertionError(f"realpath called on UNC: {p}")
        return real(p, *a, **kw)
    monkeypatch.setattr(oh.os.path, "realpath", guarded)
    return hits


def test_unc_paths_skip_realpath_and_are_never_root_worktree(tmp_path, unc_realpath_guard):
    live = tmp_path / "claude"
    (live / ".claude").mkdir(parents=True)
    (live / ".claude" / "overview-map.md").write_text(ROOT_MAP, encoding="utf-8", newline="\n")
    for unc in (Path("\\\\server\\share\\wt"), Path("\\\\?\\UNC\\server\\share\\wt"), Path("\\\\?\\unc\\server\\share\\wt")):
        assert oh.is_root_worktree(unc, live) is False
        assert oh.card_mem_dir(unc, live) == unc / ".claude" / "memory"
        assert oh.is_root_worktree(live, unc) is False                                  # claude_dir 是網路路徑也直接不是
    assert oh._same_dir_norm(Path("\\\\?\\UNC\\server\\share"), Path("\\\\server\\share")) is True
    assert oh._same_dir_norm(Path("\\\\server\\share\\a"), Path("\\\\server\\share\\b")) is False
    assert unc_realpath_guard == []                                                     # 一次都沒對網路路徑呼叫 realpath


def test_local_paths_still_resolve_with_unc_guard_active(tmp_path, unc_realpath_guard, git):
    live, wt = tmp_path / "claude", tmp_path / "wt"
    _git_live(git, live, ROOT_MAP.encode("utf-8"))
    git("-C", str(live), "worktree", "add", "-q", "-b", "wt", str(wt))                # 真 worktree
    assert oh.is_root_worktree(wt, live) is True                                        # 正例：本機路徑照常走完三條
    assert oh.card_mem_dir(wt, live) == live / "memory"                                # 根層 worktree 讀 live 的卡
    assert oh.card_mem_dir(live, live) == live / "memory"
    assert unc_realpath_guard == []


# ─── track-know：部位表類別 knowledge 的部位只要卡已注入 ─────────────────────────────────────────
# 舊碼不分類別：知識部位（派工信箱）改檔前也要讀部位檔、交定位三行；注入文字也叫人交定位三行。

_KNOW_MAP = (
    "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
    "| `tools/` | 工具 | `工具導讀` | 有 | code |\n"
    "| `scripts/` | 腳本 | `工具導讀` | 有 |  |\n"
    "| `workflow/inbox/` | 派工信箱 | `信箱導讀` | 有 | knowledge |\n"
)


@pytest.fixture
def kproj(tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = tmp_path / "kproj"
    cards = root / ".claude" / "memory" / "shared" / "導讀"
    cards.mkdir(parents=True)
    (root / ".claude" / "overview-map.md").write_text(_KNOW_MAP, encoding="utf-8")
    (cards / "工具導讀.md").write_text("# 工具導讀\n病灶：參數名寫錯", encoding="utf-8")
    (cards / "信箱導讀.md").write_text("# 信箱導讀\n派工單一律 .md", encoding="utf-8")
    for d in ("tools", "scripts", "workflow/inbox/to-x", "sub/workflow/inbox"):
        (root / d).mkdir(parents=True)
    return root


def _know_log(tmp_path):
    return [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("rel,knowledge", [
    ("workflow/inbox/to-x/a.py", True),
    ("tools/a.py", False),
    ("scripts/a.py", False),                      # 沒標類別的列＝code
    ("sub/workflow/inbox/a.py", False),        # 只有子字串撞到信箱列＝code
])
def test_know_edit_evidence_depends_on_part_kind(kproj, tmp_path, rel, knowledge):
    """同一份檔：在知識部位，注入過卡就放行（沒讀部位檔、沒交定位三行也放）；在寫碼部位照擋。"""
    tp = _transcript(tmp_path, ["先看看。"])
    f = str(kproj / rel)
    state: dict = {}
    assert wo.on_prompt(state, "s", f"看一下 {f}", tp, {})                      # 提到路徑 → 注入，沒讀任何部位檔
    warn, deny, changed = wo.on_edit(state, "s", f, tp, {})
    if knowledge:
        assert (warn, deny, changed) == (None, None, True), rel
        last = _know_log(tmp_path)[-1]
        assert last["event"] == "edit" and last["kind"] == "knowledge" and last["deny_reason"] is None
    else:
        assert deny and "定位三行" in deny, rel


def test_know_edit_before_inject_still_denies_once_without_locate_demand(kproj, tmp_path):
    """知識部位保留「卡已注入」這一項：沒注入過就先注入並擋一次（理由不叫人交定位三行），下一次放行。"""
    tp = _transcript(tmp_path, ["x"])
    f = str(kproj / "workflow" / "inbox" / "to-x" / "001-x.md")
    state: dict = {}
    warn, deny, changed = wo.on_edit(state, "s", f, tp, {})
    assert deny and "信箱導讀" in deny and "知識類部位" in deny and "定位｜部位" not in deny and changed
    assert _know_log(tmp_path)[-1]["deny_reason"] == "not_injected"
    assert wo.on_edit(state, "s", f, tp, {}) == (None, None, True)


def test_know_injection_text_asks_locate_only_for_code_parts(kproj, tmp_path):
    """注入文字：知識部位不要求定位三行（卡照注）；寫碼部位照舊要。"""
    state: dict = {}
    k = wo.on_read(state, "s", "Read", {"file_path": str(kproj / "workflow" / "inbox" / "to-x" / "a.md")}, str(kproj), "", {})
    c = wo.on_read(state, "s", "Read", {"file_path": str(kproj / "tools" / "a.py")}, str(kproj), "", {})
    assert "信箱導讀" in k and "知識類部位" in k and "定位｜部位" not in k
    assert "工具導讀" in c and "定位｜部位：工具" in c
    assert {key.rsplit("|", 1)[1]: rec.get("kind") for key, rec in state["overview_hub"].items()} == {
        "派工信箱": "knowledge", "工具": "code"}                                  # scorecard 的 S3 靠這欄排除知識部位


def test_know_part_kind_table(tmp_path):
    """lib 判法：錨在專案根的最長前綴列的類別；沒欄、沒標、拼錯、只有子字串命中、沒命中都算 code；沒部位表回 None。"""
    rows = oh.parse_map(_KNOW_MAP + "| `tools/notes/` | 工具筆記 | 無 | 無 | knowlege |\n")
    root = Path("c:/p")
    kind_of = getattr(oh, "part_kind", None)
    assert kind_of is not None, "lib/overview_hub 沒有 part_kind"
    kinds = {rel: kind_of(f"c:/p/{rel}", root, rows) for rel in
             ("workflow/inbox/a.py", "tools/a.py", "scripts/a.py", "tools/notes/a.md", "x/workflow/inbox/a.py", "a.py")}
    assert kinds == {"workflow/inbox/a.py": "knowledge", "tools/a.py": "code", "scripts/a.py": "code",
                     "tools/notes/a.md": "code", "x/workflow/inbox/a.py": "code", "a.py": "code"}
    assert all(r.get("kind") == "code" for r in oh.parse_map(APPB_TABLE))       # 沒有類別欄的舊表全是 code
    proj = tmp_path / "p"
    (proj / ".claude").mkdir(parents=True)
    assert oh.path_kind(str(proj / "workflow" / "inbox" / "a.py"), proj) is None
    (proj / ".claude" / "overview-map.md").write_text(_KNOW_MAP, encoding="utf-8")
    assert oh.path_kind(str(proj / "workflow" / "inbox" / "a.py"), proj) == "knowledge"
    assert oh.path_kind(str(proj / "tools" / "a.py"), proj) == "code"


def test_know_nested_rows_and_path_forms():
    """knowledge 父列底下的 code 子列（與反向）照最長前綴；反斜線、大小寫照認；`..` 先消掉再比；根以下帶 8.3 短名
    （長名寫的子部位比不到、會落到外層 knowledge）一律算 code。codex 審 a6323cb B1。"""
    rows = oh.parse_map(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
        "| `docs/` | 文件 | 無 | 無 | knowledge |\n| `docs/example-build/` | 範例建置 | 無 | 無 | code |\n"
        "| `lib/` | 程式庫 | 無 | 無 | code |\n| `lib/notes/` | 程式庫筆記 | 無 | 無 | knowledge |\n")
    kind_of = getattr(oh, "part_kind", None)
    assert kind_of is not None, "lib/overview_hub 沒有 part_kind"
    root = Path("C:/p")
    cases = {
        "C:/p/docs/a.md": "knowledge", "C:/p/docs/example-build/build.py": "code",
        "C:\\P\\DOCS\\Example-Build\\build.py": "code", "C:/p/docs/x/../example-build/build.py": "code",
        "C:/p/docs/../lib/a.py": "code", "C:/p/docs/EXAMPL~1/build.py": "code",
        "C:/p/lib/a.py": "code", "C:/p/lib/notes/a.md": "knowledge", "C:/p/lib/../docs/a.md": "knowledge",
    }
    assert {p: kind_of(p, root, rows) for p in cases} == cases
    assert kind_of("C:/HOLYLI~1/p/docs/a.md", Path("C:/HOLYLI~1/p"), rows) == "knowledge"   # 根本身的短名不影響


@pytest.mark.parametrize("child", ["./docs/build/", "docs/x/../build/", ".\\docs\\build\\", "./DOCS/Build"])
def test_know_table_prefix_forms_normalized_like_paths(child):
    """表列前綴與輸入路徑同一套根相對正規化：code 子列寫成 `./docs/build/`、`docs/x/../build/`、反斜線、大小寫，都蓋得住
    knowledge 父列 `docs/` 底下的 build/。舊碼只正規化輸入路徑，子列比不到、落回 knowledge 父列，真程式免 (d)。
    console codex 審 ec4f9e9 BLOCK 1。"""
    rows = oh.parse_map("| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
                        "| `docs/` | 文件 | 無 | 無 | knowledge |\n"
                        f"| `{child}` | 建置 | 無 | 無 | code |\n")
    assert rows[1]["prefixes"] == ["docs/build"]
    kind_of = getattr(oh, "part_kind", None)
    assert kind_of is not None, "lib/overview_hub 沒有 part_kind"
    assert kind_of("C:/p/docs/build/a.py", Path("C:/p"), rows) == "code"
    assert kind_of("C:/p/docs/a.md", Path("C:/p"), rows) == "knowledge"


@pytest.mark.parametrize("child", ["../build/", "./", "/abs/build/", "C:/abs/build/"])
def test_know_unplaceable_code_row_keeps_knowledge_parents_as_code(child):
    """放不進根相對位置的 code 列（往上跳出根、整個根、絕對路徑、磁碟代號）：判不出它管不管這條路徑，knowledge 列一律不豁免；
    沒有這種列時 knowledge 照常。"""
    head = ("| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
            "| `docs/` | 文件 | 無 | 無 | knowledge |\n| `tools/` | 工具 | 無 | 無 | code |\n")
    rows = oh.parse_map(head + f"| `{child}` | 怪列 | 無 | 無 | code |\n")
    assert rows[2].get("unsafe_prefix") is True
    kind_of = getattr(oh, "part_kind", None)
    assert kind_of is not None, "lib/overview_hub 沒有 part_kind"
    assert kind_of("C:/p/docs/a.md", Path("C:/p"), rows) == "code"
    assert kind_of("C:/p/docs/a.md", Path("C:/p"), oh.parse_map(head)) == "knowledge"
    assert kind_of("C:/p/docs/a.md", Path("C:/p"), oh.parse_map(head + f"| `{child}` | 怪列 | 無 | 無 | knowledge |\n")) == "knowledge"


def test_know_existing_denies_still_apply_to_knowledge_parts(kproj, tmp_path):
    """知識部位只省掉讀部位檔與定位三行：表上的卡找不到照擋、readonly_paths 照擋。"""
    (kproj / ".claude" / "overview-map.md").write_text(
        _KNOW_MAP + "| `docs/` | 文件 | `不存在的卡` | 有 | knowledge |\n", encoding="utf-8")
    (kproj / ".claude" / "overview-hub.json").write_text('{"readonly_paths": ["workflow/inbox/gen/**"]}', encoding="utf-8")
    tp = _transcript(tmp_path, ["x"])
    warn, deny, _ = wo.on_edit({}, "s", str(kproj / "docs" / "a.md"), tp, {})
    assert deny and "`不存在的卡` 在 repo 裡找不到" in deny
    warn, deny, changed = wo.on_edit({}, "s", str(kproj / "workflow" / "inbox" / "gen" / "x.md"), tp, {})
    assert deny and "readonly_paths（樣式「" in deny and not changed


def test_know_substring_code_hit_marks_part_as_code_for_scorecard(kproj, tmp_path):
    """同一列先被知識路徑注入（kind=knowledge），之後只撞到子字串的寫碼檔來改 → 照寫碼部位擋，紀錄改成 code（S3 要算）。
    codex 審 a6323cb W1。"""
    tp = _transcript(tmp_path, ["x"])
    state: dict = {}
    wo.on_prompt(state, "s", f"看 {kproj / 'workflow' / 'inbox' / 'to-x' / 'a.md'}", tp, {})
    rec = next(v for k, v in state["overview_hub"].items() if k.endswith("|派工信箱"))
    assert rec.get("kind") == "knowledge"
    warn, deny, _ = wo.on_edit(state, "s", str(kproj / "sub" / "workflow" / "inbox" / "a.py"), tp, {})
    assert deny and "定位三行" in deny and rec.get("kind") == "code"


# ─── B5 真測：表外檔綜觀（UNMAPPED_EDIT_NEEDS_READABLE_FILES）、快取目錄、Bash 唯讀讀檔（BASH_READONLY_COUNTS_AS_READ）──

def _b5_repo(tmp_path, git_init=False):
    """B5 q3 的形狀：專案根只有子目錄（沒有可讀的根層檔），沒有部位表。"""
    root = tmp_path / "b5"
    root.mkdir()
    if git_init:
        import subprocess
        subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    else:
        (root / ".git").mkdir()
    for d, f in (("bookings", "render.py"), ("tests", "test_render.py"), ("ops", "README.md")):
        (root / d).mkdir()
        (root / d / f).write_text("x\n", encoding="utf-8")
    return root


def test_b5_new_gitignore_in_root_without_readable_files_is_allowed(tmp_path, monkeypatch):
    """B5 q3 兩組 `printf … > .gitignore` 各被擋 2～3 次：根目錄沒有可讀的既有檔 → 不要求先讀（改前擋「目前 0 個」）。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    state = {}
    assert wo.on_edit(state, "s", str(root / ".gitignore"), "", {}) == (None, None, True)
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert log[-1]["rule"] == "UNMAPPED_EDIT_NEEDS_READABLE_FILES" and log[-1]["readable"] == 0


def test_b5_handoff_into_missing_claude_dir_is_allowed(tmp_path, monkeypatch):
    """B5 q5 兩組 /handoff 寫 `<專案>/.claude/memory/_staging/next-phase-*.md` 被擋「先讀 .claude 1 檔，目前 0」，
    專案根本沒有 .claude/：目標頂層目錄不存在 → 不要求先讀（改前擋）；目錄在但空的也一樣。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    target = str(root / ".claude" / "memory" / "_staging" / "next-phase-x.md")
    assert wo.on_edit({}, "s", target, "", {}) == (None, None, True)
    (root / "empty").mkdir()
    assert wo.on_edit({}, "s", str(root / "empty" / "a.md"), "", {}) == (None, None, True)


def test_b5_root_with_unread_readme_still_blocks(tmp_path, monkeypatch):
    """根目錄有 1 個 README 沒讀 → 照擋（不放寬），擋訊息帶規則名與「該目錄既有可讀檔」；讀了就放。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    (root / "README.md").write_text("# r\n", encoding="utf-8")
    state = {}
    warn, deny, _ = wo.on_edit(state, "s", str(root / ".gitignore"), "", {})
    assert deny and "「(root)」至少 1 個檔（目前 0 個）" in deny
    assert "UNMAPPED_EDIT_NEEDS_READABLE_FILES" in deny and "該目錄既有可讀檔 至少 1 個" in deny
    wo.on_read(state, "s", "Read", {"file_path": str(root / "README.md")}, str(root), "", {})
    assert wo.on_edit(state, "s", str(root / ".gitignore"), "", {}) == (None, None, True)


def test_b5_rm_pycache_is_runtime_data(tmp_path, monkeypatch):
    """B5 對照組 `rm -rf tests/__pycache__` 被擋（tests 有 test_render.py 沒讀）：快取目錄免綜觀（改前擋）。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    (root / "tests" / "__pycache__").mkdir()
    assert wo.on_edit({}, "s", str(root / "tests" / "__pycache__"), "", {}) == (None, None, False)
    assert wo.on_edit({}, "s", str(root / ".pytest_cache" / "v" / "x"), "", {}) == (None, None, False)
    warn, deny, _ = wo.on_edit({}, "s", str(root / "tests" / "test_new.py"), "", {})
    assert deny and "「tests」至少 1 個檔（目前 0 個）" in deny                       # 同目錄一般檔照要求


def test_b5_gitignored_and_cache_files_are_not_readable(tmp_path, monkeypatch):
    """可讀檔不數 gitignored 產物與快取目錄：build/ 只有被忽略的 log 與 __pycache__ → 新建 build/notes.md 不要求先讀。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path, git_init=True)
    (root / ".gitignore").write_text("build/*.log\n", encoding="utf-8")
    (root / "build" / "__pycache__").mkdir(parents=True)
    (root / "build" / "run.log").write_text("x", encoding="utf-8")
    (root / "build" / "__pycache__" / "a.pyc").write_text("x", encoding="utf-8")
    assert wo.on_edit({}, "s", str(root / "build" / "notes.md"), "", {}) == (None, None, True)
    (root / "build" / "keep.md").write_text("x", encoding="utf-8")                  # 有一個沒被忽略的檔 → 照要求
    warn, deny, _ = wo.on_edit({}, "s", str(root / "build" / "notes.md"), "", {})
    assert deny and "「build」至少 1 個檔（目前 0 個）" in deny


def _bash_read(state, root, command, exit_code=None):
    return wo.on_read(state, "s", "Bash", {"command": command}, str(root), "", {}, exit_code=exit_code)


def test_b5_bash_cat_counts_as_read(tmp_path, monkeypatch):
    """派工單補充紅案例①：`cat ops/README.md` 之後寫 ops/docs/x.md → 不擋。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    state = {}
    _bash_read(state, root, "cat ops/README.md", exit_code=0)
    assert wo.on_edit(state, "s", str(root / "ops" / "docs" / "x.md"), "", {}) == (None, None, True)


def test_b5_bash_multi_file_cat_counts_every_file(tmp_path, monkeypatch):
    """B5 q3 兩組 `cat bookings/render.py … tests/test_render.py …` 一次讀多檔，舊 regex 只認第一個 → 寫 tests/ 被擋（改前擋）。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    state = {}
    _bash_read(state, root, "cat bookings/render.py tests/test_render.py && head -c 1500 ops/README.md")
    assert wo.on_edit(state, "s", str(root / "tests" / "test_render.py"), "", {}) == (None, None, True)
    assert wo.on_edit(state, "s", str(root / "ops" / "new.md"), "", {}) == (None, None, True)


@pytest.mark.parametrize("command, exit_code", [
    ("echo hi > /dev/null", 0),                         # ② echo 不是讀檔
    ("printf 'x' ; ls ops ; find ops -name '*.md'", 0), #   printf／ls／find 也不是
    ("cat $f", 0),                                      # ③ 變數路徑
    ('for f in ops/*.md; do cat "$f"; done', 0),        #   B5 q4 的迴圈寫法：照規則不算
    ("cat ops/$f", 0),                                  #   中段變數（改前當字面路徑算進去）
    ("cat ops/nothere.md", 1),                          # ④ 檔不存在（改前照算）
    ("cat ops/README.md", 1),                           #   指令失敗（exit≠0，改前照算）
    ("cat > ops/README.md <<'EOF'", 0),                 #   重導向目標是寫，不是讀
], ids=["echo", "printf-ls-find", "var", "q4-loop", "mid-var", "missing", "exit-1", "redirect"])
def test_b5_bash_non_reads_do_not_count(tmp_path, monkeypatch, command, exit_code):
    """派工單補充紅案例②③④：不算讀檔的指令讀完，寫 ops/ 下的檔仍擋。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    state = {}
    _bash_read(state, root, command, exit_code=exit_code)
    warn, deny, _ = wo.on_edit(state, "s", str(root / "ops" / "docs" / "x.md"), "", {})
    assert deny and "「ops」至少 1 個檔（目前 0 個）" in deny


def test_b5_bash_grep_n_and_more_count_as_read(tmp_path, monkeypatch):
    """grep -n（第一個參數是樣式，不算路徑）與 more 算讀檔（改前不認）；grep 沒帶 -n 不算。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    state = {}
    _bash_read(state, root, 'grep -c "x" ops/README.md')
    warn, deny, _ = wo.on_edit(state, "s", str(root / "ops" / "a.md"), "", {})
    assert deny
    _bash_read(state, root, 'grep -n "tests/test_render.py" ops/README.md')       # 樣式長得像路徑也不算
    assert wo.on_edit(state, "s", str(root / "ops" / "a.md"), "", {}) == (None, None, True)
    warn, deny, _ = wo.on_edit(state, "s", str(root / "tests" / "t2.py"), "", {})
    assert deny
    _bash_read(state, root, "more tests/test_render.py")
    assert wo.on_edit(state, "s", str(root / "tests" / "t2.py"), "", {}) == (None, None, True)
