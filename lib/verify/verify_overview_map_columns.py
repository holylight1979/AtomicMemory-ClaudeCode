"""verify_overview_map_columns.py — overview-map.md 擴欄解析（lib/overview_hub.parse_map）。

正例：十三欄表（前綴｜部位｜導讀卡｜狀態｜病灶清單｜量尺｜檢查器清單｜讀路徑樣本｜第四問｜層｜權威地圖｜上游｜下游）
解析齊；狀態「骨架」可讀；表頭多一欄「順序」時擴欄仍照表頭定位。
反例：舊四欄表（照 verify_overview_hub.py 的 APPB_TABLE／GAMEA_TABLE 原文）既有鍵與擴欄前（main 2af6b64 的
parse_map 跑出的快照）完全相同、擴欄全空；量尺欄的反引號指令不被當卡名；沒表頭時擴欄全空；「根因層」表頭不是「層」。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_overview_map_columns.py
"""
from __future__ import annotations

import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LIB_DIR))

import overview_hub as oh  # noqa: E402

OLD_KEYS = ("prefixes", "part", "part_short", "card", "cards", "status", "line")
EMPTY_EXTRA = {"defects_doc": "", "measure": {}, "checkers": [], "sample_paths": "", "extra_q": "",
               "layer": "", "authority": "", "upstream": "", "downstream": ""}

# ─── 舊四欄表原文（與 hooks/verify/verify_overview_hub.py 一字相同）與擴欄前的解析快照 ──────────

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

APPB_SNAPSHOT = [
    {"prefixes": ["appb_server/worldserver/clan"], "part": "Server／氏族域", "part_short": "Server",
     "card": "server部位導讀-x", "cards": ["server部位導讀-x"], "status": "有",
     "line": "| 1 | `appb_server/WorldServer/Clan/` | Server／氏族域（子 Manager 群） | `server部位導讀-x` | 有（2026-10-08） |"},
    {"prefixes": ["appb_server/worldserver"], "part": "Server／主邏輯", "part_short": "Server",
     "card": "server部位導讀-x", "cards": ["server部位導讀-x"], "status": "有",
     "line": "| 2 | `appb_server/WorldServer/` | Server／主邏輯（Handler） | 同上 | 有 |"},
    {"prefixes": ["appb_server/servertools/merge"], "part": "合服工具", "part_short": "合服工具",
     "card": "合服部位導讀-y", "cards": ["合服部位導讀-y"], "status": "有",
     "line": "| 3 | `appb_server/ServerTools/Merge/` | 合服工具（多模式） | `合服部位導讀-y`（`shared/合服/`） | 有 |"},
    {"prefixes": ["tools"], "part": "工具鏈", "part_short": "工具鏈",
     "card": "工具鏈導讀-z", "cards": ["工具鏈導讀-z"], "status": "有",
     "line": "| 4 | `Tools/` | 工具鏈（SVN） | `工具鏈導讀-z` | 有 |"},
    {"prefixes": ["_tools"], "part": "外部輕量腳本", "part_short": "外部輕量腳本",
     "card": "工具鏈導讀-z", "cards": ["工具鏈導讀-z"], "status": "有",
     "line": "| 5 | `_tools/` | 外部輕量腳本 | 同第 4 列 | 有 |"},
    {"prefixes": ["vendor-framework"], "part": "框架源碼", "part_short": "框架源碼",
     "card": None, "cards": [], "status": "無",
     "line": "| 6 | `Vendor-Framework/` | 框架源碼 | 無；病灶見 Server 卡 | 無 |"},
]

GAMEA_SNAPSHOT = [
    {"prefixes": ["game/ui/map", "game/player/map"], "part": "大地圖", "part_short": "大地圖",
     "card": "大地圖知識導讀-hub索引", "cards": ["大地圖知識導讀-hub索引"], "status": "有",
     "line": "| `Game\\ui\\Map\\`、`Game\\player\\map\\` | 大地圖（面板） | `大地圖知識導讀-hub索引` | 有 | 文件 `_AIDocs/x.md` |"},
    {"prefixes": ["game/ui"], "part": "UI 演出", "part_short": "UI 演出",
     "card": "ui演出知識導讀-hub索引", "cards": ["ui演出知識導讀-hub索引"], "status": "有",
     "line": "| `Game\\ui\\`（上列以外） | UI 演出 | `ui演出知識導讀-hub索引` | 有（第二批） | 20 張 |"},
    {"prefixes": ["assets/game/config/tables/*.bytes"], "part": "設計表", "part_short": "設計表",
     "card": "設計表知識導讀-hub索引", "cards": ["設計表知識導讀-hub索引"], "status": "有",
     "line": "| `Assets\\Game\\config\\tables\\*.bytes` | 設計表 | `設計表知識導讀-hub索引` | 有（第三批） | 含 `BuildTables.ps1` |"},
    {"prefixes": ["rpc"], "part": "網路登入", "part_short": "網路登入",
     "card": "gamea-wire-protocols", "cards": ["gamea-wire-protocols"], "status": "部分",
     "line": "| `rpc\\` | 網路登入 | `gamea-wire-protocols` | 部分 | 10 張 |"},
    {"prefixes": ["assets/game/scripts"], "part": "主程式集", "part_short": "主程式集",
     "card": "doc-index-client-scripts", "cards": ["doc-index-client-scripts"], "status": "索引",
     "line": "| `Assets\\Game\\scripts\\` | 主程式集 | `doc-index-client-scripts` | 索引 | CS-01 |"},
]

# ─── 十三欄表 ───────────────────────────────────────────────────────────────────

THIRTEEN = """
| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 病灶清單 | 量尺（量法｜指令｜門檻） | 檢查器清單 | 讀路徑樣本 | 第四問 | 層 | 權威地圖 | 上游 | 下游 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `Server/Map/` | 大地圖（world） | `大地圖知識導讀-hub索引`、`大地圖根因層` | 有 | `_AIDocs/defects/map.md` | P90｜`dotnet run tick`｜25ms | `a.py`;`b.py` | MapPanel > MapCtrl > MapData（3 層） | 幾份存法？ | 熱修 | `_AIDocs/authority.md` | 設計表 | UI 演出 |
| `Server/Battle/` | 戰鬥 |  | 骨架 | 無 | 無 | 無 |  |  | 主程式集 |  |  |  |
"""


def _old(rows):
    return [{k: r[k] for k in OLD_KEYS} for r in rows]


def _extra(row):
    return {k: row[k] for k in EMPTY_EXTRA}


# ─── 正例 ──────────────────────────────────────────────────────────────────────

def test_thirteen_columns_all_parsed():
    rows = oh.parse_map(THIRTEEN)
    assert len(rows) == 2
    r = rows[0]
    assert r["prefixes"] == ["server/map"] and r["part_short"] == "大地圖"
    assert r["cards"] == ["大地圖知識導讀-hub索引", "大地圖根因層"] and r["status"] == "有"
    assert r["defects_doc"] == "_AIDocs/defects/map.md"
    assert r["measure"] == {"method": "P90", "cmd": "dotnet run tick", "threshold": "25ms"}
    assert r["checkers"] == ["a.py", "b.py"]
    assert r["sample_paths"] == "MapPanel > MapCtrl > MapData（3 層）"
    assert r["extra_q"] == "幾份存法？"
    assert r["layer"] == "熱修"
    assert r["authority"] == "_AIDocs/authority.md"
    assert r["upstream"] == "設計表" and r["downstream"] == "UI 演出"


def test_skeleton_status_and_empty_extra_cells():
    r = oh.parse_map(THIRTEEN)[1]
    assert r["status"] == "骨架" and r["cards"] == [] and r["card"] is None
    assert _extra(r) == dict(EMPTY_EXTRA, layer="主程式集")           # 「無」與空格都是空值


def test_header_with_leading_order_column_still_locates_extra_columns():
    text = (
        "| 順序 | 路徑前綴 | 部位 | 導讀卡 | 狀態 | 檢查器清單 | 量尺 |\n|---|---|---|---|---|---|---|\n"
        "| 1 | `Tools/` | 工具鏈 | `工具鏈導讀-z` | 有 | `check.py` | 行數｜`wc -l`｜500 |\n"
    )
    r = oh.parse_map(text)[0]
    assert r["card"] == "工具鏈導讀-z" and r["checkers"] == ["check.py"]
    assert r["measure"] == {"method": "行數", "cmd": "wc -l", "threshold": "500"}


def test_checkers_without_backticks_split_on_separators():
    text = "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 檢查器清單 |\n|---|---|---|---|---|\n| `x/` | 甲 | `卡` | 有 | a.py; b.py、c.py |\n"
    assert oh.parse_map(text)[0]["checkers"] == ["a.py", "b.py", "c.py"]


# ─── 反例 ──────────────────────────────────────────────────────────────────────

def test_old_four_column_tables_identical_to_pre_extension_snapshot():
    appb, gamea = oh.parse_map(APPB_TABLE), oh.parse_map(GAMEA_TABLE)
    assert _old(appb) == APPB_SNAPSHOT
    assert _old(gamea) == GAMEA_SNAPSHOT
    for r in appb + gamea:
        assert _extra(r) == EMPTY_EXTRA


def test_measure_backtick_command_is_not_a_card():
    text = (
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 量尺 |\n|---|---|---|---|---|\n"
        "| `Server/Battle/` | 戰鬥 |  | 骨架 | P90｜`dotnet run tick`｜25ms |\n"
        "| `Server/Map/` | 大地圖 | `大地圖導讀` | 有 | 延遲｜`python bench.py`｜10ms |\n"
    )
    rows = oh.parse_map(text)
    assert rows[0]["cards"] == [] and rows[0]["measure"]["cmd"] == "dotnet run tick"
    assert rows[1]["cards"] == ["大地圖導讀"] and rows[1]["measure"]["cmd"] == "python bench.py"


def test_no_header_extended_cells_stay_empty():
    text = "| `Server/Map/` | 大地圖 | `大地圖導讀` | 有 | `_AIDocs/d.md` | P90｜`dotnet run tick`｜25ms |\n"
    r = oh.parse_map(text)[0]
    assert r["cards"] == ["大地圖導讀"] and _extra(r) == EMPTY_EXTRA


def test_root_cause_layer_header_is_not_layer_column():
    text = "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 根因層 |\n|---|---|---|---|---|\n| `x/` | 甲 | `卡` | 有 | 邏輯層 |\n"
    assert oh.parse_map(text)[0]["layer"] == ""
