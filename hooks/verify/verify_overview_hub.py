"""verify_overview_hub.py — OverviewHub 的部位表、設定合併與驗證、讀檔帳、寫入檢查（readonly_paths、設定錯誤）。

純函式：lib/overview_hub（讀表、最長前綴命中、Bash 讀檔擷取、導讀卡分片）；
state 層：wg_overview.record_reads / write_check（用 tmp_path 造一個假專案）。
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


_ROOT_NAMED_TABLE = ("| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
                     "| `tools/` | 工具 | 無 | 無 | code |\n| `.claude/` | 部位表 | 無 | 無 | knowledge |\n"
                     "| `tests/` | 測試 | 無 | 無 | code |\n")


@pytest.mark.parametrize("root,path,part", [
    # 根目錄本身叫 .claude（根層 repo）：表上沒列的根層檔不能因為根目錄名落到 `.claude/` 列
    ("C:/Users/u/.claude", "C:/Users/u/.claude/TECH.md", None),
    ("C:/Users/u/.claude", "C:/Users/u/.claude/workflow/config.json", None),
    ("C:/Users/u/.claude", "C:/Users/u/.claude/.claude/overview-map.md", "部位表"),     # 根下真的 .claude/ 照中
    ("C:/Users/u/.claude", "C:/Users/u/.claude/tools/x.py", "工具"),
    # 上層目錄名含 tests（CI 或 pytest 暫存目錄）：不影響專案裡的判定
    ("C:/ci/tests/proj", "C:/ci/tests/proj/lib/a.py", None),
    ("C:/ci/tests/proj", "C:/ci/tests/proj/sub/tests/a.py", "測試"),                  # 根以下的子字串照中
    # 一般專案：根以下的非錨定子字串命中不變
    ("C:/Work/proj", "C:/Work/proj/pkg/.claude/x.md", "部位表"),
])
def test_match_substring_only_below_root(root, path, part):
    """match_row 的子字串命中只看專案根以下的相對路徑：根目錄本身的名字、根以上的目錄名不參與。舊碼拿整條絕對路徑比，
    根層 repo（根目錄叫 .claude）每個表上沒列的檔都落到 `.claude/` 列、上層有 tests 的專案每個檔都落到 `tests/` 列。"""
    m = oh.match_row(path, Path(root), oh.parse_map(_ROOT_NAMED_TABLE))
    assert (m["part_short"] if m else None) == part, (root, path)


# ─── Bash 讀檔 ───────────────────────────────────────────


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


# ─── state 層：假專案 ───────────────────────────────

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


def test_outside_any_project_is_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    state = {}
    wo.record_reads(state, "Read", {"file_path": str(tmp_path / "lonely.cs")}, "", {})
    assert state == {}
    assert wo.write_check("s", str(tmp_path / "lonely.cs"), {}) == (None, None, None)
    wo.record_reads(state, "Read", {"file_path": "x"}, "", {"overview_hub": {"enabled": False}})
    assert state == {}


def test_project_override_file_wins(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    (proj / ".claude" / "overview-hub.json").write_text('{"max_card_chars": 5}', encoding="utf-8")
    assert wo._cfg({"overview_hub": {"max_card_chars": 6000}}, proj)["max_card_chars"] == 5   # 專案層蓋過 config.json
    (proj / ".claude" / "overview-hub.json").write_text('{"enabled": false}', encoding="utf-8")
    state = {}
    wo.record_reads(state, "Read", {"file_path": f1}, str(proj), {})                         # 專案層關掉：不記
    assert state == {}
    assert wo.write_check("s", f1, {}) == (None, None, None)


# ─── Codex 審查指出的五點（B1 在上面、B2／B5／W1／W2／B4 在這）────────────


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


def test_bash_vcs_reads_count_as_reads():                                 # 專案覆蓋提案 #4
    got = oh.read_paths_from_tool("Bash", {"command": 'svn cat "c:/P/appb_server/A.cs" ; git show HEAD~1:hooks/x.py | head -5'}, "c:/P")
    assert got[0] == "c:/P/appb_server/A.cs" and got[1].replace("\\", "/") == "c:/P/hooks/x.py"


# ─── 四層深合併 / find_map 界線 / 設定驗證 ─────────────────────────

def _org_world(tmp_path, monkeypatch, hub_json):
    org = tmp_path / "company"
    (org / ".claude").mkdir(parents=True)
    (org / ".claude" / "overview-hub.json").write_text(json.dumps(hub_json, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(wo, "org_memory_root", lambda: org)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    return org


def test_cfg_org_layer_overrides_config_and_project_wins(proj, tmp_path, monkeypatch):
    org = _org_world(tmp_path, monkeypatch, {"max_card_chars": 100, "authority_map": {"*.md": "公司圖", "*.txt": "公司文字圖"}})
    config = {"overview_hub": {"max_card_chars": 50, "readonly_paths": ["根層/**"]}}
    c = wo._cfg(config, proj)
    assert c["max_card_chars"] == 100                                   # 公司層蓋過 config.json
    assert c["authority_map"] == {"*.md": "公司圖", "*.txt": "公司文字圖"} and c["_errors"] == []
    (proj / ".claude" / "overview-hub.json").write_text(
        '{"max_card_chars": 20, "authority_map": {"*.md": "專案圖"}, "readonly_paths": ["專案/**"]}', encoding="utf-8")
    c = wo._cfg(config, proj)
    assert c["max_card_chars"] == 20                                    # 專案層勝
    assert c["authority_map"] == {"*.md": "專案圖", "*.txt": "公司文字圖"}   # 巢狀 dict 深合併
    assert c["readonly_paths"] == ["專案/**"]                             # list 整個取覆蓋方
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
    from hub_config import HUB_DEFAULTS, validate_hub_cfg

    def errors(c, root):
        return validate_hub_cfg(c, root)[0]
    assert errors(dict(HUB_DEFAULTS), None) == []
    assert errors(dict(HUB_DEFAULTS), tmp_path) == []
    (tmp_path / "src" / "sub").mkdir(parents=True)
    amb = errors(dict(HUB_DEFAULTS, path_bases=["src", "src/sub"]), tmp_path)
    assert len(amb) == 1 and "歧義" in amb[0]                            # 反例一：互相包含的基準
    missing = errors(dict(HUB_DEFAULTS, path_bases=["nope"]), tmp_path)
    assert len(missing) == 1 and "不是存在的目錄" in missing[0]
    bad_enc = errors(dict(HUB_DEFAULTS, commit_encoding="no-such-enc", source_encodings=["utf-8", "x-bogus"]), None)
    assert len(bad_enc) == 2 and all("編碼" in e for e in bad_enc)       # 反例二：壞編碼
    unknown = errors(dict(HUB_DEFAULTS, foo=1), None)
    assert unknown == ["未知的設定鍵「foo」"]                              # 反例三：未知鍵
    assert errors(dict(HUB_DEFAULTS, _doc="說明"), None) == []           # 底線鍵不算未知
    assert any("eol_policy" in e for e in errors(dict(HUB_DEFAULTS, eol_policy="mixed"), None))


def test_retired_keys_warn_once_not_error(proj, tmp_path, monkeypatch, capsys):
    from hub_config import RETIRED_KEYS
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    cfg = {"overview_hub": {k: True for k in RETIRED_KEYS}}
    c = wo._cfg(cfg)
    assert c["_errors"] == []                                           # 退役鍵不報錯
    err = capsys.readouterr().err
    assert err.count("已退役") == len(RETIRED_KEYS)
    wo._cfg(cfg)
    assert capsys.readouterr().err == ""                                # 第二次不再警告


def test_cfg_errors_make_write_check_deny(proj, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".claude" / "overview-hub.json").write_text('{"foo": 1, "eol_policy": "mixed"}', encoding="utf-8")
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    warn, deny, hit = wo.write_check("s", f1, {})
    assert deny and "設定有錯" in deny and "未知的設定鍵「foo」" in deny and "eol_policy" in deny and warn == deny
    assert hit["rule"] == "GATE_SELF_ERROR"
    assert "設定錯誤" in capsys.readouterr().err
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert log[-1]["event"] == "edit_cfg_error"
    state = {}
    wo.record_reads(state, "Read", {"file_path": f1}, str(proj), {})   # 讀仍照記（錯誤只擋改）
    assert next(iter(state["overview_hub"].values()))["part_files_read"] == [f1]


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
    warn, deny, _ = wo.write_check("s", str(proj / "Game" / "Battle" / "A.cs"), {})
    assert deny and "未知的設定鍵「foo」" in deny
    if "null" in hub_text:
        assert "enabled 必須是" in deny
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert log[-1]["event"] == "edit_cfg_error" and log[-1]["layer"] == "project_mapped"


def test_root_level_cfg_error_denies_file_outside_any_table(tmp_path, monkeypatch):   # BLOCK 1：沒命中表的檔也報
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    bad = {"overview_hub": {"enabled": False, "bogus": 1}}
    warn, deny, _ = wo.write_check("s", str(tmp_path / "lonely.cs"), bad)
    assert deny and "未知的設定鍵「bogus」" in deny and "none" in deny
    assert wo.write_check("s", "", bad) == (None, None, None)           # 沒 file_path 沒東西可擋


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
    from hub_config import HUB_DEFAULTS, encoding_ok, validate_hub_cfg
    for bad in ("utf\u0000-8", "", None, 5, ["utf-8"]):
        assert encoding_ok(bad) is False
    errs = validate_hub_cfg(dict(HUB_DEFAULTS, commit_encoding="utf\u0000-8", source_encodings=["utf\u0000-8"],
                                 PYTHONIOENCODING=["utf-8"]), None)[0]
    assert len(errs) == 3 and all("編碼" in e for e in errs)


def test_invalid_shapes_deny_on_write_instead_of_raising(proj, tmp_path, monkeypatch):   # BLOCK 2 端到端
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    warn, deny, _ = wo.write_check("s", f1, {"overview_hub": [1]})
    assert deny and "overview_hub 段必須是物件" in deny
    _hub(proj, '{"commit_encoding": "utf\\u0000-8"}')
    warn, deny, _ = wo.write_check("s", f1, {})
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
    root, row = wo._lookup(str(fake / "hooks" / "x.py"))
    assert wo._cards_for(root, row, {}) == [fake / "memory" / "CC" / "hooks導讀.md"]
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


def test_cards_for_root_worktree_live_and_project_same_name_counterexample(tmp_path, monkeypatch):
    live, wt, proj = _root_world(tmp_path, monkeypatch)
    row = oh.parse_map(ROOT_MAP)[0]
    assert wo._cfg({}, wt)["_layer"] == "project_mapped"                              # 層名判定不變
    assert wo._cards_for(wt, row, wo._cfg({}, wt)) == [live / "memory" / "CC" / "hooks導讀.md"]   # 同名卡內容不同，拿 live 那張
    assert wo._cards_for(live, row, wo._cfg({}, live)) == [live / "memory" / "CC" / "hooks導讀.md"]
    got = wo._cards_for(proj, row, wo._cfg({}, proj))                                  # 反例：兩處同名卡，只拿 .claude/memory
    assert got == [proj / ".claude" / "memory" / "shared" / "hooks導讀.md"]


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
    bad = {"overview_hub": {"enabled": False, "bogus": 1}}

    warn, deny, _ = wo.write_check("s", str(cfg_path), bad)                            # ① 根層 config.json：放行＋警告
    assert deny is None and warn and "放行以便修復" in warn and "未知的設定鍵「bogus」" in warn
    warn, deny, _ = wo.write_check("s", str(root_hub), bad)                            # ② 根層 .claude/overview-hub.json
    assert deny is None and warn and "bogus" in warn
    _hub(proj, '{"foo": 1}')
    warn, deny, _ = wo.write_check("s", str(proj / ".claude" / "overview-hub.json"), {})   # ③ 專案 hub.json
    assert deny is None and warn and "未知的設定鍵「foo」" in warn

    warn, deny, _ = wo.write_check("s", str(fake / "workflow" / "other.json"), bad)   # 同目錄他檔仍擋（比路徑不比檔名）
    assert deny and "bogus" in deny
    warn, deny, _ = wo.write_check("s", str(fake / "workflow" / "config.json.bak"), bad)
    assert deny
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    warn, deny, _ = wo.write_check("s", f1, {})                                          # 專案 hub 壞 → 部位檔仍擋
    assert deny and "foo" in deny

    _hub(proj, "{}")                                                                     # 修好 → 部位檔放行
    assert wo.write_check("s", f1, {}) == (None, None, None)
    assert wo.write_check("s", str(proj / ".claude" / "overview-hub.json"), {}) == (None, None, None)   # 設定沒錯：自家設定檔靜默放行
    events = [json.loads(l)["event"] for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert events.count("edit_own_config") == 3 and "edit_cfg_error" in events


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
    bad = {"overview_hub": {"enabled": False, "bogus": 1}}

    warn, deny, _ = wo.write_check("s", str(root_map), bad)                            # 根層表：放行＋警告
    assert deny is None and warn and "放行以便修復" in warn and "bogus" in warn
    _hub(proj, '{"foo": 1}')
    proj_map = proj / ".claude" / "overview-map.md"
    warn, deny, _ = wo.write_check("s", str(proj_map), {})                             # 專案表：放行＋警告列專案層錯誤
    assert deny is None and warn and "未知的設定鍵「foo」" in warn
    warn, deny, _ = wo.write_check("s", str(fake / ".claude" / "overview-map.md.bak"), bad)   # 同目錄他檔仍擋（比路徑不比檔名）
    assert deny and "bogus" in deny
    warn, deny, _ = wo.write_check("s", str(fake / ".claude" / "notes.md"), bad)
    assert deny and "bogus" in deny
    warn, deny, _ = wo.write_check("s", str(proj / "Game" / "Battle" / "A.cs"), {})          # 專案表壞設定下部位檔仍擋
    assert deny and "foo" in deny
    _hub(proj, "{}")
    assert wo.write_check("s", str(proj_map), {}) == (None, None, None)               # 設定沒錯：表靜默放行
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
    bad = {"overview_hub": {"enabled": False, "bogus": 1}}
    assert wo._strip_extended("\\\\?\\C:\\x\\y") == "C:\\x\\y"
    assert wo._strip_extended("\\\\?\\UNC\\srv\\share\\y") == "\\\\srv\\share\\y"
    assert wo._strip_extended("C:\\x") == "C:\\x"

    ext = "\\\\?\\" + str(cfg_path)
    assert wo._own_config_layer(ext) == (True, None)
    warn, deny, _ = wo.write_check("s", ext, bad)                                         # 前綴版 config.json：放行＋警告
    assert deny is None and warn and "bogus" in warn
    _hub(proj, '{"foo": 1}')
    ext_hub = "\\\\?\\" + str(proj / ".claude" / "overview-hub.json")
    assert wo._own_config_layer(ext_hub) == (True, proj)
    warn, deny, _ = wo.write_check("s", ext_hub, {})                                      # 前綴版專案 hub.json
    assert deny is None and warn and "foo" in warn
    warn, deny, _ = wo.write_check("s", "\\\\?\\" + str(fake / "workflow" / "other.json"), bad)   # 前綴版他檔仍擋
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
    hub_lower = str(root / ".claude" / "overview-hub.json")                              # 呼叫端給小寫
    assert Path(hub_lower).resolve().parent.name == ".CLAUDE"                            # 前提：resolve 還原磁碟實際大小寫
    assert wo._own_config_layer(hub_lower)[0] is True
    warn, deny, _ = wo.write_check("s", hub_lower, {})
    assert deny is None and warn and "未知的設定鍵「foo」" in warn
    warn, deny, _ = wo.write_check("s", str(root / ".CLAUDE" / "OVERVIEW-MAP.MD"), {})    # 表本身、全大寫寫法
    assert deny is None and warn and "foo" in warn
    warn, deny, _ = wo.write_check("s", str(root / ".CLAUDE" / "notes.md"), {})          # 同目錄他檔命中「設定」部位 → 仍擋
    assert deny and "foo" in deny
    warn, deny, _ = wo.write_check("s", str(root / "src" / "a.py"), {})
    assert deny and "foo" in deny


# ─── 導讀卡分片（defect_bullets 靠它取「已知病灶」段）───────────────────────

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
    assert set(p["slices"]) == {"what", "authority", "ask", "defects", "verify"}
    assert "子點跟著上一段" in p["slices"]["what"] and "| a | b |" in p["slices"]["defects"]    # 子 bullet／表格跟上一段
    assert any(k.startswith("2026-10-08 校正") for k in p["others"]) and "行動" in p["others"]
    assert "## 知識" not in FIVE_CARD.replace(p["head"], "") or "知識" not in p["others"]       # 結構標題不算段
    flat = oh.split_card_sections("# 只有標題\n\n一段散文，沒有任何 ## 或 bullet。")             # 無標題單 head 反例
    assert flat["slices"] == {} and flat["others"] == {} and "一段散文" in flat["head"]
    spine = oh.split_card_sections("# Spine\n\n## 知識\n\n- [臨] 閱讀序 ①②③\n- [臨] 一句話結論：走程式拆件\n")
    assert spine["slices"] == {} and len(spine["others"]) == 2


# ─── 無表專案的根（VCS 退路）─────────


def test_unmapped_deep_file_falls_back_to_vcs_root(tmp_path, monkeypatch):
    """缺口 4：只有 .git、無表；第 5 層的檔退 VCS 根，讀檔帳記到那個根的頂層目錄。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = tmp_path / "deep"
    (root / ".git").mkdir(parents=True)
    (root / "src" / "a" / "b" / "c").mkdir(parents=True)
    (root / "src" / "other.py").write_text("x", encoding="utf-8")
    deep = str(root / "src" / "a" / "b" / "c" / "widget.py")
    assert wo._project_root_of(deep) is None                                       # 前提：舊規則最多 4 層找不到
    assert _n(wo._unmapped_root_of(deep)) == _n(root)
    state = {}
    wo.record_reads(state, "PowerShell", {"command": "Get-Content src/other.py"}, str(root), {})
    assert _reads_in(state, "src") == {_n(root / "src" / "other.py")}


def test_unmapped_vcs_fallback_never_takes_home_or_drive_root(tmp_path, monkeypatch):
    import wg_verify_ledger as vl
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    home = tmp_path / "home"
    (home / ".git").mkdir(parents=True)
    deep = home / "a" / "b" / "c" / "d" / "e.py"
    deep.parent.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    assert wo._project_root_of(str(deep)) is None
    assert wo._unmapped_root_of(str(deep)) is None                                 # 家目錄不當根
    monkeypatch.setattr(vl, "find_vcs_root", lambda start: ("git", Path(Path(start).anchor)))
    other = tmp_path / "x" / "a" / "b" / "c" / "d" / "f.py"
    assert wo._unmapped_root_of(str(other)) is None                                # 磁碟根不當根


def test_unmapped_vcs_fallback_not_used_when_project_has_table(proj, tmp_path, monkeypatch):
    """有部位表的專案不走退路：表上沒列的深層檔不歸到 VCS 根。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".git").mkdir()
    deep = proj / "Other" / "a" / "b" / "c" / "x.py"
    deep.parent.mkdir(parents=True)
    assert wo._project_root_of(str(deep)) is None
    assert wo._unmapped_root_of(str(deep)) is None


# ─── 卡名欄、readonly_paths ───────────────────────


def test_009_7_extension_only_glob_is_file_pattern_not_card():
    """純副檔名樣式（`*.bytes`）與含路徑分隔字元的照舊不當卡；同列的真卡名照收。"""
    rows = oh.parse_map("| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
                     "| `Game\\Battle\\` | 戰鬥 | `*.bytes` `Data/*.json` `戰鬥*` | 有 |\n")
    assert rows[0]["cards"] == ["戰鬥*"]


def test_readonly_paths_deny_and_glob_misses_neighbors(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    (proj / ".claude" / "overview-hub.json").write_text(
        '{"readonly_paths": ["Game/Battle/Gen/**/*.cs", "Game/Battle/_INDEX.md"]}', encoding="utf-8")
    for ro in ("Game/Battle/Gen/A.cs", "Game/Battle/Gen/sub/B.cs", "Game/Battle/_INDEX.md"):
        warn, deny, hit = wo.write_check("s", str(proj / ro), {})
        assert deny and "readonly_paths（樣式「" in deny and hit["rule"] == "OVERVIEW_READONLY_PATHS"
    for nb in ("Game/Battle/Gen2/A.cs", "Game/Battle/_INDEX.md.bak", "Game/Battle/Gen.cs"):
        assert wo.write_check("s", str(proj / nb), {}) == (None, None, None)          # 鄰目錄不命中
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert [e["event"] for e in log] == ["edit_readonly"] * 3 and log[0]["deny_reason"] == "readonly"


# ─── 退回 001：BLOCK 1／2／3／7 ───────────────────────────────────────────────────


def test_unmapped_project_hub_json_is_own_config(tmp_path, monkeypatch):          # BLOCK 3：無表專案 hub.json 能自救
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = tmp_path / "bare"
    (root / ".git").mkdir(parents=True)
    (root / ".claude").mkdir()
    (root / "src").mkdir()
    hub = root / ".claude" / "overview-hub.json"
    hub.write_text('{"foo": 1}', encoding="utf-8")
    assert wo._own_config_layer(str(hub)) == (True, root)
    warn, deny, _ = wo.write_check("s", str(hub), {})
    assert deny is None and warn and "放行以便修復" in warn and "未知的設定鍵「foo」" in warn
    warn, deny, _ = wo.write_check("s", str(root / "src" / "a.py"), {})                     # 其他檔仍被設定錯誤擋
    assert deny and "foo" in deny
    hub.write_text("{}", encoding="utf-8")
    assert wo.write_check("s", str(hub), {}) == (None, None, None)
    assert wo._own_config_layer(str(tmp_path / "nowhere" / ".claude" / "overview-hub.json")) == (False, None)


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


def test_same_dir_norm_long_prefix_any_case():
    unc = Path("\\\\localhost\\nosuchshare_a3")                                             # localhost：不存在的分享也秒回
    assert oh._same_dir_norm(Path("\\\\?\\unc\\localhost\\nosuchshare_a3"), unc) is True   # 小寫 unc 不得剝成相對路徑
    assert oh._same_dir_norm(Path("\\\\?\\UNC\\localhost\\nosuchshare_a3"), unc) is True
    assert oh._same_dir_norm(Path("\\\\?\\c:\\x"), Path("C:\\x")) is True
    assert oh._same_dir_norm(Path("\\\\?\\unc\\localhost\\nosuchshare_a3"), Path("\\\\localhost\\other_a3")) is False


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


# ─── track-know：部位表類別 knowledge（lib/overview_hub.part_kind）─────────────────────────────────────────
# 舊碼不分類別：知識部位（派工信箱）改檔前也要讀部位檔、交定位三行；注入文字也叫人交定位三行。

_KNOW_MAP = (
    "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
    "| `tools/` | 工具 | `工具導讀` | 有 | code |\n"
    "| `scripts/` | 腳本 | `工具導讀` | 有 |  |\n"
    "| `workflow/inbox/` | 派工信箱 | `信箱導讀` | 有 | knowledge |\n"
)


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


# ─── B5 真測：Bash 唯讀讀檔（BASH_READONLY_COUNTS_AS_READ）記進讀檔帳 ──

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


def _bash_read(state, root, command, exit_code=None):
    wo.record_reads(state, "Bash", {"command": command}, str(root), {}, exit_code=exit_code)


def _n(p):
    return os.path.normcase(os.path.normpath(str(p)))


def _reads_in(state, top):
    """表外頂層目錄 top（<根>|(unmapped)<top>）記下的讀檔，正規化成集合。"""
    recs = [r for k, r in (state.get("overview_hub") or {}).items() if k.endswith(f"|(unmapped){top}")]
    return {_n(p) for r in recs for p in r.get("part_files_read") or []}


def test_b5_bash_cat_counts_as_read(tmp_path, monkeypatch):
    """派工單補充紅案例①：`cat ops/README.md` 跑成功 → 記成讀過 ops 的檔。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    state = {}
    _bash_read(state, root, "cat ops/README.md", exit_code=0)
    assert _reads_in(state, "ops") == {_n(root / "ops" / "README.md")}


def test_b5_bash_multi_file_cat_counts_every_file(tmp_path, monkeypatch):
    """B5 q3 兩組 `cat bookings/render.py … tests/test_render.py …` 一次讀多檔，舊 regex 只認第一個：每個檔都要記。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    state = {}
    _bash_read(state, root, "cat bookings/render.py tests/test_render.py && head -c 1500 ops/README.md")
    assert _reads_in(state, "bookings") == {_n(root / "bookings" / "render.py")}
    assert _reads_in(state, "tests") == {_n(root / "tests" / "test_render.py")}
    assert _reads_in(state, "ops") == {_n(root / "ops" / "README.md")}


@pytest.mark.parametrize("command, exit_code", [
    ("echo hi > /dev/null", 0),                         # ② echo 不是讀檔
    ("printf 'x' ; ls ops ; find ops -name '*.md'", 0), #   printf／ls／find 也不是
    ("cat $f", 0),                                      # ③ 變數路徑
    ('for f in $(ls ops); do cat "$f"; done', 0),       #   清單是命令代換的迴圈：讀了哪些檔不確定（字面清單的見 006 案）
    ("cat ops/$f", 0),                                  #   中段變數（改前當字面路徑算進去）
    ("cat ops/nothere.md", 1),                          # ④ 檔不存在（改前照算）
    ("cat ops/README.md", 1),                           #   指令失敗（exit≠0，改前照算）
    ("cat > ops/README.md <<'EOF'", 0),                 #   重導向目標是寫，不是讀
    ("cat ops/*.txt", 0),                               #   glob 展不出實檔（bash 原樣傳字面）
], ids=["echo", "printf-ls-find", "var", "loop-subst", "mid-var", "missing", "exit-1", "redirect", "glob-none"])
def test_b5_bash_non_reads_do_not_count(tmp_path, monkeypatch, command, exit_code):
    """派工單補充紅案例②③④：不算讀檔的指令跑完，ops 底下沒有記成讀過。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    state = {}
    _bash_read(state, root, command, exit_code=exit_code)
    assert _reads_in(state, "ops") == set()


# 第二波第五跑 B-1 原指令（transcript 22:00:37）：迴圈讀一批檔，之後改 sales/periods.py 被擋「讀過 0 個」
_B5W2_CMD = ('for f in sales/*.py tests/*.py defects.md .claude/overview-map.md .claude/overview-hub.json .gitignore; '
             'do echo "=== $f"; cat "$f"; done; echo "=== data head"; head -20 data/sales.csv; wc -l data/sales.csv')


def _b5w2_repo(tmp_path):
    root = tmp_path / "qb2"
    (root / ".git").mkdir(parents=True)
    for rel in ("sales/periods.py", "sales/cli.py", "tests/test_report.py", "data/sales.csv", "defects.md"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x\n", encoding="utf-8")
    return root


@pytest.mark.parametrize("command", [
    _B5W2_CMD,
    "for f in README.md sales/periods.py tests/test_report.py\ndo\n  cat \"$f\"\ndone",      # 第四跑 B-1 的字面清單、換行寫法
    "cat sales/*.py && head -5 tests/*.py",                                                   # glob 直接給讀檔指令
], ids=["w2-b5-loop", "w2-b4-literal-multiline", "glob-direct"])
def test_006_bash_loop_and_glob_reads_count(tmp_path, monkeypatch, command):
    """閘小修 006 件 3（規則 BASH_READONLY_COUNTS_AS_READ）：字面清單的 for 迴圈逐項展開、glob 照 cwd 展開成實檔，讀過的都記；
    前置：沒讀之前讀檔帳是空的。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5w2_repo(tmp_path)
    state = {}
    assert _reads_in(state, "sales") == set()
    _bash_read(state, root, command, exit_code=0)
    assert _n(root / "sales" / "periods.py") in _reads_in(state, "sales")
    assert _reads_in(state, "tests") == {_n(root / "tests" / "test_report.py")}


def test_006_loop_expansion_paths_are_exact(tmp_path):
    """展開只收清單真的列到的實檔：glob 對到的每個檔、字面項照收（不存在的 .claude/… 由 bash_read_counts 濾掉）；
    清單含命令代換整個迴圈不展開。"""
    root = _b5w2_repo(tmp_path)
    got = {Path(p).relative_to(root).as_posix() for p in oh.read_paths_from_tool("Bash", {"command": _B5W2_CMD}, str(root))
           if Path(p).is_file()}
    assert got == {"sales/periods.py", "sales/cli.py", "tests/test_report.py", "defects.md", "data/sales.csv"}, got
    assert oh.read_paths_from_tool("Bash", {"command": 'for f in $(ls sales); do cat "sales/$f"; done'}, str(root)) == []


@pytest.mark.parametrize("command", [
    'for f in sales/periods.py; do break; cat "$f"; done',          # 本體先跳出：cat 沒跑
    'for f in sales/*.py; do [ -s "$f" ] || continue; cat "$f"; done',
    "for f in 'sales/*.py'; do cat \"$f\"; done; true",               # 加引號的 glob：bash 傳字面星號
    "cat 'sales/*.py'; true",
], ids=["break", "continue", "quoted-loop-glob", "quoted-direct-glob"])
def test_006_loop_exit_and_quoted_glob_do_not_inflate_reads(tmp_path, command):
    """codex 006：讀檔指令不一定跑、glob 被引號擋住沒展開 → 不能多算讀過（之前會把 sales/ 底下的檔全算讀過）。"""
    root = _b5w2_repo(tmp_path)
    got = [p for p in oh.read_paths_from_tool("Bash", {"command": command}, str(root)) if Path(p).is_file()]
    assert got == [], got


@pytest.mark.parametrize("command", [
    "exit 0; cat sales/periods.py",
    "for f in x; do break; cat sales/periods.py; done",
    "test -f defects.md || cat sales/periods.py",
    "false && cat sales/periods.py; true",
    "[ -f defects.md ] && echo y && cat sales/periods.py; true",
    "grep -q x defects.md && cat sales/periods.py; echo done",
], ids=["exit-first", "break-then-cat", "or-tail", "false-and", "test-and-chain", "grep-q-and"])
def test_unreached_literal_read_does_not_count(tmp_path, command):
    """規則 BASH_UNREACHED_READ_NOT_COUNTED：字面出現、但執行不到（或不一定跑）的 cat 不算讀過——整條指令結束碼 0 看不出那段跑了沒。
    前置：同一個檔單獨 cat 會算（不是因為檔不在才沒算到）。"""
    root = _b5w2_repo(tmp_path)
    assert oh.read_paths_from_tool("Bash", {"command": "cat sales/periods.py"}, str(root))
    got = [p for p in oh.read_paths_from_tool("Bash", {"command": command}, str(root)) if Path(p).is_file()]
    assert got == [], got


@pytest.mark.parametrize("command, n", [
    ("cd . && cat sales/periods.py", 1),
    ("cat defects.md && cat sales/periods.py", 2),
    ("git ls-files && echo --- && cat defects.md", 1),
    ("cat sales/periods.py || true", 1),
    ("cat sales/periods.py; exit 0", 1),
    ("[ -f defects.md ] || exit 1; cat sales/periods.py", 1),
    ("for f in a; do break; done; cat sales/periods.py", 1),
    ("python - <<'PY'\ndef f():\n    return 1\nPY\ncat sales/periods.py", 1),
], ids=["cd-and", "cat-and-cat", "b5-ls-files-chain", "cat-or-true", "exit-after", "guard-exit", "after-done", "heredoc-return"])
def test_reached_reads_still_count(tmp_path, command, n):
    """反例：前段是一般指令的 && 後段（它失敗整條結束碼就非零，交結束碼篩）、|| 前段、exit 之前、守門式 `|| exit 1` 之後、
    迴圈 done 之後、heredoc 內文裡的 return（那是 python 的）都照算讀過。"""
    root = _b5w2_repo(tmp_path)
    got = [p for p in oh.read_paths_from_tool("Bash", {"command": command}, str(root)) if Path(p).is_file()]
    assert len(got) == n, got


def test_exit_reached_inside_chain_stops_later_reads(tmp_path):
    """codex 007：`true && exit 0; cat x` 在 exit 就結束，後面的 cat 沒跑；串內會跑到的 exit 之後都不算。
    反例：`|| exit 1` 守門式（exit 在 || 後段、不一定跑）之後的 cat 照算。"""
    root = _b5w2_repo(tmp_path)
    got = [p for p in oh.read_paths_from_tool("Bash", {"command": "true && exit 0; cat sales/periods.py"}, str(root))]
    assert got == [], got
    assert oh.read_paths_from_tool("Bash", {"command": "[ -f defects.md ] || exit 1; cat sales/periods.py"}, str(root))


def test_unreached_read_is_not_recorded(tmp_path, monkeypatch):
    """端到端：`test -f … || cat ops/README.md` 結束碼 0 → 沒記讀過；直接 cat 之後才記。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    state = {}
    _bash_read(state, root, "test -f ops/README.md || cat ops/README.md", exit_code=0)
    assert _reads_in(state, "ops") == set()
    _bash_read(state, root, "cat ops/README.md", exit_code=0)
    assert _reads_in(state, "ops") == {_n(root / "ops" / "README.md")}


def test_b5_bash_grep_n_and_more_count_as_read(tmp_path, monkeypatch):
    """grep -n（第一個參數是樣式，不算路徑）與 more 算讀檔（改前不認）；只印筆數的 grep -c 不算。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    root = _b5_repo(tmp_path)
    state = {}
    _bash_read(state, root, 'grep -c "x" ops/README.md')
    assert _reads_in(state, "ops") == set()
    _bash_read(state, root, 'grep -n "tests/test_render.py" ops/README.md')       # 樣式長得像路徑也不算
    assert _reads_in(state, "ops") == {_n(root / "ops" / "README.md")} and _reads_in(state, "tests") == set()
    _bash_read(state, root, "more tests/test_render.py")
    assert _reads_in(state, "tests") == {_n(root / "tests" / "test_render.py")}


def _battle(state):
    return next(v for k, v in state["overview_hub"].items() if k.endswith("|戰鬥"))


def _same_files(a, b):
    return {os.path.normcase(os.path.normpath(p)) for p in a} == {os.path.normcase(os.path.normpath(p)) for p in b}


def test_shell_read_counts_like_read(proj, tmp_path, monkeypatch):
    """規則 SHELL_READ_COUNTS_LIKE_READ：唯讀 Bash／PowerShell 讀檔跟 Read 同效。一條 cat 讀三個檔 → 三個都記（跟送三個 Read 一樣）；
    MSYS 寫法 /c/…、不帶 -n 的 grep、開頭 cd 之後的相對路徑、PowerShell Get-Content 都算；只印檔名、筆數或不印的 grep
    （-l、-c、--count、-q）不算，帶了 -n 也不算（-nl、-n -c 不能灌讀檔證據）。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    cfg = {"overview_hub": {"enabled": True}}
    battle = proj / "Game" / "Battle"
    f = {}
    for n in "ABCDEFGH":
        (battle / f"{n}.cs").write_text("foo = 1", encoding="utf-8")
        f[n] = (battle / f"{n}.cs").as_posix()
    by_read = {}
    for n in "ABC":
        wo.record_reads(by_read, "Read", {"file_path": f[n]}, str(proj), cfg)
    by_cat = {}
    wo.record_reads(by_cat, "Bash", {"command": f"cat {f['A']} {f['B']} {f['C']}"}, str(proj), cfg)
    rec = _battle(by_cat)
    assert len(rec["part_files_read"]) == 3 and _same_files(rec["part_files_read"], _battle(by_read)["part_files_read"])
    forms = [("Bash", f"grep foo {f['E']}"), ("PowerShell", f"Get-Content '{f['G']}' -TotalCount 5")]
    if os.name == "nt":
        msys = "/" + f["A"][0].lower() + f["A"][2:].rsplit("/Game/", 1)[0]          # C:/x/proj → /c/x/proj
        forms += [("Bash", f"cat {msys}/Game/Battle/D.cs"), ("Bash", f"cd {msys}/Game && head -5 Battle/F.cs")]
    for tool, cmd in forms:
        n = len(rec["part_files_read"])
        wo.record_reads(by_cat, tool, {"command": cmd}, str(proj), cfg)
        assert len(rec["part_files_read"]) == n + 1, cmd
    n = len(rec["part_files_read"])
    for cmd in (f"grep -l foo {f['H']}", f"grep -c foo {f['H']}", f"grep --count foo {f['H']}", f"grep -nl foo {f['H']}",
                f"grep -n -c foo {f['H']}", f"grep -rnq foo {f['H']}", f"grep --line-number --files-with-matches foo {f['H']}"):
        wo.record_reads(by_cat, "Bash", {"command": cmd}, str(proj), cfg)
        assert len(rec["part_files_read"]) == n, cmd


def test_shell_write_command_not_a_read(proj, tmp_path, monkeypatch):
    """規則 SHELL_WRITE_COMMAND_NOT_A_READ：有寫檔目標的指令不是唯讀，讀到的檔不算讀過——重導向 >、tee、sed -i、
    PowerShell Out-File／> 都不算（改前 `cat x > out`、`cat x | tee out` 算）；`2>&1` 只是併輸出，照算。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    cfg = {"overview_hub": {"enabled": True}}
    battle = proj / "Game" / "Battle"
    a, b, out = (battle / "A.cs").as_posix(), (battle / "B.cs").as_posix(), (proj / "out.txt").as_posix()
    for p in (a, b):
        Path(p).write_text("x", encoding="utf-8")
    fresh = {}
    wo.record_reads(fresh, "Bash", {"command": f"cat {a} > {out}"}, str(proj), cfg)
    assert not fresh.get("overview_hub")
    state = {}
    wo.record_reads(state, "Read", {"file_path": a}, str(proj), cfg)
    rec = _battle(state)
    for tool, cmd in (("Bash", f"cat {b} > {out}"), ("Bash", f"cat {b} | tee {out}"), ("Bash", f"sed -i 's/x/y/' {b}"),
                      ("PowerShell", f"Get-Content '{b}' | Out-File '{out}'"), ("PowerShell", f"Get-Content '{b}' > '{out}'")):
        wo.record_reads(state, tool, {"command": cmd}, str(proj), cfg)
        assert rec["part_files_read"] == [a], cmd                                # 只有那次 Read
    wo.record_reads(state, "Bash", {"command": f"cat {b} 2>&1"}, str(proj), cfg)
    assert len(rec["part_files_read"]) == 2


@pytest.fixture(autouse=True)
def _cassette(git_cassette):
    """git 子程序錄製重播（lib/git_cassette.py）：平常重播一次真實執行的紀錄、不開 git；git 互動改了 → 失敗要求
    pytest --git-record 重錄。"""
    git_cassette()
