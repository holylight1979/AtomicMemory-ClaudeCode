"""verify_pick_one.py：寫碼交付時順手點出最該修的一件（v6 G4／G5／G13）。

做什麼：本 session 改了程式、到交付邊界 → Stop 用 additionalContext 送一次「哪一件最該修、為什麼、為什麼不是數字最高的那個」
（只提醒、不擋；同一批改動只問一次）；AI 回覆裡的「順手看到最該修」段記成追蹤項（另存建議怎麼解、該誰解）；
下個 session 開場先列附了建議的未結項；(k) 行尾的「｜建議：…｜該誰解：…」也進同兩欄。
正例：交付邊界＋新改的程式 → 送一次（不是 block）；回覆裡的那段 → 帳本一筆 open 附四欄、同段不重記；開場列建議與該誰解（有部位的也列）；
      材料依部位分組、壞味道分數與行數標「只當參考」。
反例：同一批改動第二次不送；沒到交付邊界、只改文件、設定沒開、AI 自己先寫了那段 → 不送；句中提到、code block 裡、照抄範本、
      只有標頭 → 不記；「無，因為…」不進帳本；(k) 的「問題｜建議：…」不把問題當部位。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_pick_one.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_harvest as wh  # noqa: E402
import wg_overview as wo  # noqa: E402
from handlers import stop as st  # noqa: E402

_SID = "sid-pick"
MAP = ("| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 病灶清單 | 量尺 | 檢查器 | 讀路徑 | 第四問 | 層 | 權威 | 上游 | 下游 | 類別 |\n"
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
       "| `Game/Battle/` | 戰鬥 | `戰鬥知識導讀` | 有 | 無 | 無 | 無 | 無 | 無 | 單層 | 無 | 無 | 傷害結算、存檔 | code |\n"
       "| `Game/UI/` | 介面 | 無 | 無 | 無 | 無 | 無 | 無 | 無 | 單層 | 無 | 無 | 玩家畫面 | code |\n"
       "| `docs/` | 文件 | 無 | 無 | 無 | 無 | 無 | 無 | 無 | 單層 | 無 | 無 | 無 | knowledge |\n")
CARD = "# 戰鬥導讀\n\n## 已知病灶\n- 傷害公式的共用字典被三處各自改\n- 技能冷卻表讀錯欄位\n- 第三條不會列\n"
PICK = """改好了，全部完成。

**順手看到最該修**：[戰鬥] Game/Battle/Damage.cs 的暴擊分支把共用字典當暫存
- 為什麼是它：傷害結算與存檔都讀這份字典，改一處另兩處跟著錯，已經修過兩次
- 為什麼不是數字最高的那個：Skill.cs 2000 行最長，但結構清楚、沒人改它出事
- 建議怎麼解：暴擊分支改用區域變數，字典只讀
- 該誰解：下一個寫碼 session
"""


@pytest.fixture
def world(tmp_path, monkeypatch):
    """tmp 專案（部位表＋戰鬥卡＋壞味道報告）＋ tmp 的 workflow（帳本落這裡，不碰 live）。"""
    proj = tmp_path / "proj"
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text(MAP, encoding="utf-8", newline="\n")
    (proj / ".claude" / "overview-hub.json").write_text(json.dumps({"smells_report": "smells.json"}), encoding="utf-8")
    (proj / ".claude" / "memory" / "shared" / "戰鬥知識導讀.md").write_text(CARD, encoding="utf-8")
    (proj / "smells.json").write_text(json.dumps({"rows": [
        {"path": "Game/Battle/Skill.cs", "category": "長函式", "reason": "2000 行", "score": 95, "part": "戰鬥"},
        {"path": "Game/Battle/Damage.cs", "category": "共用可變狀態", "reason": "字典", "score": 12, "part": "戰鬥"},
        {"path": "Game/UI/Btn.cs", "category": "長函式", "reason": "x", "score": 99, "part": "介面"}]}), encoding="utf-8")
    for d in ("Game/Battle", "Game/UI", "docs"):
        (proj / d).mkdir(parents=True)
    (proj / "Game" / "Battle" / "Damage.cs").write_text("a\nb\nc\n", encoding="utf-8")
    (proj / "Game" / "Battle" / "Skill.cs").write_text("x\n" * 9, encoding="utf-8")
    (proj / "Game" / "UI" / "Btn.cs").write_text("y\n", encoding="utf-8")
    wf = tmp_path / "workflow"
    monkeypatch.setattr(wh, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    return proj, wf


def _rows(proj):
    return wh.read_tracking(wh.tracking_slug(str(proj)))


# ─── (k) 行尾的提議欄 ─────────────────────────────────────────────────────────

def test_k_line_proposal_and_owner_split_before_part():
    rows = wh.tracking_entries("s", 1, "gitlab 鏡像 push 憑證失效｜建議：換 token 後重推｜該誰解：使用者\n"
                                       "[hooks] 寫入失敗待查｜該誰解：根層｜建議：加重試\n"
                                       "hooks｜舊格式部位行\n[hooks] 結案：寫入失敗待查", at="2026-10-20T00:00:00")
    assert (rows[0]["part"], rows[0]["text"]) == ("", "gitlab 鏡像 push 憑證失效")   # 反例：舊碼把問題當成部位、本文剩「建議：…」
    assert (rows[0]["proposal"], rows[0]["owner"]) == ("換 token 後重推", "使用者")
    assert (rows[1]["part"], rows[1]["text"], rows[1]["proposal"], rows[1]["owner"]) == ("hooks", "寫入失敗待查", "加重試", "根層")
    assert (rows[2]["part"], rows[2]["text"]) == ("hooks", "舊格式部位行") and "proposal" not in rows[2]   # 沒寫提議照舊
    assert rows[3]["status"] == "closed" and "proposal" not in rows[3]


# ─── 解析回覆裡的那一段 ───────────────────────────────────────────────────────

def test_parse_pick_reads_all_fields_and_last_block_wins():
    p = wh.parse_pick("順手看到最該修：[介面] 舊的那件\n為什麼是它：舊理由\n\n" + PICK)
    assert p == {"none": False, "part": "戰鬥", "text": "Game/Battle/Damage.cs 的暴擊分支把共用字典當暫存",
                 "why": "傷害結算與存檔都讀這份字典，改一處另兩處跟著錯，已經修過兩次",
                 "not_top": "Skill.cs 2000 行最長，但結構清楚、沒人改它出事",
                 "proposal": "暴擊分支改用區域變數，字典只讀", "owner": "下一個寫碼 session"}
    none = wh.parse_pick("全部完成。\n順手看到最該修：無，因為這次只改了一行設定")
    assert none["none"] is True and none["text"].startswith("無")


@pytest.mark.parametrize("text", [
    "交付末尾會多一段「順手看到最該修：X，因為…」這樣。",                                  # 句中順帶提到
    "```\n順手看到最該修：[戰鬥] 範例\n為什麼是它：範例\n```",                               # code block 裡
    "格式範例如下：\n> 順手看到最該修：[戰鬥] Damage.cs 共用字典被覆寫\n> 為什麼是它：會影響存檔\n> 建議怎麼解：改區域變數",   # 引言裡（Codex BLOCK 1）
    "順手看到最該修：[部位] <哪一件、在哪個檔哪一段>\n為什麼是它：<它影響誰>",                # 照抄範本
    "順手看到最該修：[戰鬥] 只有標頭沒有理由",                                              # 只有標頭
    "全部完成。",
])
def test_parse_pick_counter_cases(text):
    assert wh.parse_pick(text) is None


# ─── 記進帳本 ────────────────────────────────────────────────────────────────

def test_record_pick_writes_one_open_item_with_proposal_and_owner(world):
    proj, _ = world
    state: dict = {}
    ev, p = wh.record_pick(state, _SID, 5, PICK, str(proj), at="2026-10-20T01:00:00")
    assert ev == "recorded" and p["part"] == "戰鬥"
    rows = _rows(proj)
    assert len(rows) == 1
    r = rows[0]
    assert (r["status"], r["source"], r["part"]) == ("open", "pick", "戰鬥")
    assert r["proposal"] == "暴擊分支改用區域變數，字典只讀" and r["owner"] == "下一個寫碼 session"
    assert r["why"].startswith("傷害結算") and r["not_top"].startswith("Skill.cs")
    assert state["pick_one"][_SID]["covered_turn"] == 5
    ev2, _ = wh.record_pick({}, "other-sid", 9, PICK, str(proj))                         # 下一批、甚至別的 session 又點出同一件
    assert ev2 == "repeat" and len(_rows(proj)) == 1                                     # 帳上已有未結的同一件 → 不重記
    wh.append_tracking(wh.tracking_slug(str(proj)), wh.tracking_entries("s2", 7, "[戰鬥] 結案：Game/Battle/Damage.cs 的暴擊"))
    assert wh.open_tracking_items(_rows(proj)) == []                                     # 照一般追蹤項結案
    assert wh.record_pick({}, _SID, 10, PICK, str(proj))[0] == "recorded"                # 結案後又出現 → 重新記


def test_record_pick_none_and_repeats_still_count_as_answered_for_new_batch(world):
    """Codex BLOCK 3：下一批改動又答出同一句（「無」或同一件）也要算這批答過，不能因為去重而再被問。"""
    proj, _ = world
    state: dict = {}
    assert wh.record_pick(state, _SID, 5, "順手看到最該修：無，因為只改了一行", str(proj))[0] == "none"
    assert _rows(proj) == [] and state["pick_one"][_SID]["covered_turn"] == 5
    assert wh.record_pick(state, _SID, 6, "順手看到最該修：無，因為只改了一行", str(proj))[0] == "none"
    assert not wh.pick_due(state, _SID, [{"path": "a.py", "last_turn_seq": 6}], boundary=True)
    wh.record_pick(state, _SID, 7, PICK, str(proj))
    assert wh.record_pick(state, _SID, 8, PICK, str(proj))[0] == "repeat"
    assert not wh.pick_due(state, _SID, [{"path": "a.py", "last_turn_seq": 8}], boundary=True)


# 第二波 A′ 實跑（tracking:1–2、guard-pick_one:2–3）：同 session 同回合對同一件以略異文字答兩次 → 記成兩筆 open
A1_PICK_1 = """改完了。

順手看到最該修：[pricing] catalog.py 的 PRICES 價格表寫死在程式裡（defects.md 剩下的唯一一項）
- 為什麼是它：價格是業務天天會改的資料，現在改價等於改程式、發版、重跑測試
- 建議怎麼解：把 PRICES 搬成 pricing 目錄下的 prices.json，catalog.unit_price 啟動時讀一次並快取
- 該誰解：使用者決定改價流程
"""
A1_PICK_2 = """補上那段。

順手看到最該修：[pricing] catalog.py 的 PRICES 價格表寫死在程式裡
- 為什麼是它：價格是業務常改的資料，改價等於改程式發版
- 建議怎麼解：PRICES 搬成 pricing/prices.json，catalog.unit_price 啟動讀一次快取，KeyError 行為保留
- 該誰解：使用者決定改價流程後，下一個寫碼 session 做
"""


def _open(proj):
    return wh.open_tracking_items(_rows(proj))


def test_record_pick_same_turn_reworded_supersedes_first_row(world):
    proj, _ = world
    state: dict = {}
    assert wh.record_pick(state, _SID, 1, A1_PICK_1, str(proj), at="2026-10-21T15:35:43+08:00")[0] == "recorded"
    first_id = _rows(proj)[0]["id"]
    ev, _ = wh.record_pick(state, _SID, 1, A1_PICK_2, str(proj), at="2026-10-21T15:35:56+08:00")
    assert ev == "updated" and state["pick_one"][_SID]["covered_turn"] == 1
    (row,) = _open(proj)                                                                 # 未結的只一筆，是第二次的說法
    assert row["text"] == "catalog.py 的 PRICES 價格表寫死在程式裡" and row["proposal"].endswith("KeyError 行為保留")
    assert row["owner"].startswith("使用者決定改價流程後") and row["supersedes"] == first_id
    rows = _rows(proj)                                                                   # 帳本只追加：原列逐字還在
    assert len(rows) == 3 and rows[0]["id"] == first_id and rows[0]["text"].endswith("（defects.md 剩下的唯一一項）")
    assert rows[1]["id"] == row["id"]                                                    # 新列先寫、結案列後寫
    assert rows[2]["status"] == "closed" and rows[2]["closes"]["id"] == first_id and rows[2]["superseded_by"] == row["id"]


def test_record_pick_supersede_half_written_never_loses_the_item(world, monkeypatch):
    """Codex：兩列只寫進第一列就斷了（磁碟滿、程序被砍）→ 最多多一筆重複，舊的那件不會被關掉卻沒有新的。"""
    proj, _ = world
    wh.record_pick({}, _SID, 1, A1_PICK_1, str(proj))
    real = wh.append_tracking
    monkeypatch.setattr(wh, "append_tracking", lambda slug, entries, *a, **k: real(slug, entries[:1], *a, **k))
    wh.record_pick({}, _SID, 1, A1_PICK_2, str(proj))
    assert len(_open(proj)) == 2


def test_record_pick_superseded_row_stays_closed_after_ledger_pruning(world):
    """清理器（handlers/_shared._prune_tracking_pairs）把結案超過 90 天的「結案列＋開項」成對拿掉；被取代的那筆不會因此又變回未結。"""
    from datetime import datetime
    from handlers import _shared
    proj, wf = world
    wh.record_pick({}, _SID, 1, A1_PICK_1, str(proj), at="2026-01-01T00:00:00+08:00")
    wh.record_pick({}, _SID, 1, A1_PICK_2, str(proj), at="2026-01-01T00:00:10+08:00")
    res = {"deleted": [], "compacted": {}, "failed": []}
    _shared._prune_tracking_pairs(wf / "tracking", 90, datetime(2026, 10, 21).timestamp(), False, res)
    assert res["compacted"], "前置：清理器真的拿掉了那一對"
    assert [r["text"] for r in _rows(proj)] == ["catalog.py 的 PRICES 價格表寫死在程式裡"]
    assert [r["text"] for r in _open(proj)] == ["catalog.py 的 PRICES 價格表寫死在程式裡"]


def test_record_pick_different_target_or_other_session_keeps_separate_rows(world):
    proj, _ = world
    wh.record_pick({}, _SID, 1, A1_PICK_1, str(proj))
    other = A1_PICK_2.replace("catalog.py 的 PRICES 價格表寫死在程式裡", "cli.py 的 main 參數手切")
    assert wh.record_pick({}, _SID, 1, other, str(proj))[0] == "recorded"               # 同回合不同標的 → 兩筆
    same_fn = A1_PICK_2.replace("價格表寫死在程式裡", "缺少負數檢查")
    assert wh.record_pick({}, _SID, 1, same_fn, str(proj))[0] == "recorded"             # 同一個檔與識別字、不同問題（Codex）→ 不併
    upper = A1_PICK_2.replace("catalog.py 的 PRICES 價格表寫死在程式裡", "validator.py 的 validate 未檢查上限")
    assert wh.record_pick({}, _SID, 1, upper, str(proj))[0] == "recorded"
    lower = upper.replace("未檢查上限", "未檢查下限")
    assert wh.record_pick({}, _SID, 1, lower, str(proj))[0] == "recorded"               # 字面很像的不同問題（Codex 複審）→ 不併
    assert wh.record_pick({}, "other-sid", 1, A1_PICK_2, str(proj))[0] == "recorded"   # 別的 session 不併（不是同一次交付）
    assert len(_open(proj)) == 6


def test_record_pick_supersede_write_failure_keeps_first_row_and_says_so(world, monkeypatch, capsys):
    """換成新說法的那兩列寫不進去 → 第一筆照留、stderr 說沒換；第一筆已在帳上，仍算答過。"""
    proj, _ = world
    state: dict = {}
    wh.record_pick(state, _SID, 1, A1_PICK_1, str(proj))
    monkeypatch.setattr(wh, "append_tracking", lambda *a, **k: None)
    assert wh.record_pick(state, _SID, 1, A1_PICK_2, str(proj))[0] == "update_failed"
    (row,) = _open(proj)
    assert row["text"].endswith("（defects.md 剩下的唯一一項）")
    assert "沒換成新的說法" in capsys.readouterr().err and state["pick_one"][_SID]["covered_turn"] == 1


def test_record_pick_write_failure_is_not_answered_and_retries(world, monkeypatch):
    """Codex BLOCK 2：帳本寫不進去 → 不算答過（下次照問）、同一段下次照記。"""
    proj, _ = world
    state: dict = {}
    real, broken = wh.append_tracking, [True]
    monkeypatch.setattr(wh, "append_tracking", lambda *a, **k: None if broken[0] else real(*a, **k))
    assert wh.record_pick(state, _SID, 5, PICK, str(proj))[0] == "write_failed"
    assert "covered_turn" not in state.get("pick_one", {}).get(_SID, {})
    assert wh.pick_due(state, _SID, [{"path": "a.py", "last_turn_seq": 5}], boundary=True)
    broken[0] = False                                                                    # 帳本恢復可寫
    assert wh.record_pick(state, _SID, 5, PICK, str(proj))[0] == "recorded" and len(_rows(proj)) == 1


# ─── 該不該問 ────────────────────────────────────────────────────────────────

def test_pick_due_only_for_new_code_changes_at_boundary():
    state: dict = {}
    mods = [{"path": "a.py", "last_turn_seq": 5}]
    assert wh.pick_due(state, _SID, mods, boundary=True)
    assert not wh.pick_due(state, _SID, mods, boundary=False)                           # 沒到交付邊界
    assert not wh.pick_due(state, _SID, [], boundary=True)                              # 沒改程式
    wh.mark_pick_asked(state, _SID, 5)
    assert not wh.pick_due(state, _SID, mods, boundary=True)                            # 同一批只問一次
    mods.append({"path": "b.py", "last_turn_seq": 6})
    assert wh.pick_due(state, _SID, mods, boundary=True)                                # 下一批又改了 → 再問
    state["pick_one"][_SID]["covered_turn"] = 6
    assert not wh.pick_due(state, _SID, mods, boundary=True)                            # AI 自己先寫了那段
    assert not wh.pick_due({}, _SID, [{"path": "c.py"}], boundary=True)                 # 沒有回合號的不算新改動


# ─── 材料：依部位分組、數字標參考 ─────────────────────────────────────────────

def test_material_groups_by_part_with_numbers_marked_reference(world):
    proj, _ = world
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, wh.tracking_entries("s", 1, "[戰鬥] 舊的未結項\n[戰鬥] 最新的未結項"))
    paths = [str(proj / "Game" / "Battle" / "Damage.cs"), str(proj / "Game" / "UI" / "Btn.cs"),
             str(proj / "Game" / "Battle" / "Skill.cs"), str(proj / "tools" / "x.py")]
    lines = wh.pick_material(paths, {})
    assert lines[0].startswith("- 【戰鬥】") and lines[1].startswith("- 【介面】")       # 照改檔先後、不按分數排
    battle = lines[0]
    assert "影響到：傷害結算、存檔" in battle
    assert "傷害公式的共用字典被三處各自改" in battle and "第三條不會列" not in battle
    assert "分數只當參考" in battle and battle.index("Skill.cs｜長函式｜分數 95") < battle.index("Damage.cs｜共用可變狀態｜分數 12")
    assert "Btn.cs" not in battle                                                        # 別部位的壞味道不混進來
    assert "行數只當參考" in battle and "Damage.cs 4 行" in battle and "Skill.cs 10 行" in battle
    assert "未結追蹤項 2 筆，最新一筆：最新的未結項" in battle
    assert lines[-1] == "- 部位表查不到的檔：x.py"
    prompt = wh.pick_prompt(lines)
    assert "只提醒、不擋" in prompt and "為什麼不是數字最高的那個：" in prompt and "該誰解：" in prompt
    assert "Skill.cs｜長函式｜分數 95｜呼叫點 無法判（.cs 不以 import 檔案互相呼叫）" in battle   # 算不出就說算不出


# ─── 材料：每條壞味道附呼叫點（003，切入點自評 E04c／E04d）────────────────────────────
# 真任務原樣：沒人呼叫的 90 行舊函式分數 48、被兩支 import 的吞錯 loader 分數 12；材料沒有呼叫點時 AI 挑分數高的死碼

E04_MAP = ("| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 病灶清單 | 量尺 | 檢查器 | 讀路徑 | 第四問 | 層 | 權威 | 上游 | 下游 | 類別 |\n"
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
           "| `report/` | 匯出 | 無 | 無 | 無 | 無 | 無 | 無 | 無 | 單層 | 無 | 無 | 日報 CSV、月結 summary | code |\n")
E04_FILES = {
    "report/__init__.py": "",
    "report/legacy_export.py": "def format_legacy_rows(rows):\n    return rows\n",
    "report/loader.py": "def load_rows(f):\n    rows = []\n    for line in f:\n        try:\n            rows.append(line)\n"
                        "        except Exception:\n            continue\n    return rows\n",
    "report/csv_export.py": "from report.loader import load_rows\n\n\ndef export(f):\n    return load_rows(f)\n",
    "report/summary.py": "from report import (\n    loader,  # 月結\n)\n\n\ndef total(f):\n    return len(loader.load_rows(f))\n",
    "report/alias.py": "from report.fmtlib import parse as loader  # 別名叫 loader，不是 import loader\n",
    "report/broken.py": "def oops(:\n    from report import loader\n",
    "report/notes.py": "# loader 的說明：別在這裡 import\nLOADER_DOC = 'loader legacy_export'\n",
    "tests/test_legacy.py": "from report import legacy_export\n",
    "web/app.js": "const fmt = require('../report/fmt');\nimport { a } from './util/fmt.js';\n",
    "report/fmt.js": "module.exports = {};\n",
    ".claude/hooks/gate.py": "import gate  # 自己的 import 行不算呼叫者\n\n\ndef check():\n    return True\n",
    "tools/run_report.py": "def main():\n    pass\n\n\nif __name__ == \"__main__\":\n    main()\n",
    "tools/move-dir-check.py": "print('x')\n",
    "app/use_gate.py": "from hooks.gate import check\n",
}


@pytest.fixture
def git_world(tmp_path, monkeypatch):
    import subprocess
    proj = tmp_path / "e04"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text(E04_MAP, encoding="utf-8", newline="\n")
    (proj / ".claude" / "overview-hub.json").write_text(json.dumps({"smells_report": "smells.json"}), encoding="utf-8")
    (proj / "smells.json").write_text(json.dumps({"rows": [
        {"path": "report/legacy_export.py", "category": "long_function", "reason": "90 行、巢狀 5 層", "score": 48, "part": "匯出"},
        {"path": "report/loader.py", "category": "swallowed_exception", "reason": "except: continue", "score": 12, "part": "匯出"},
    ]}), encoding="utf-8")
    for rel, text in E04_FILES.items():
        (proj / rel).parent.mkdir(parents=True, exist_ok=True)
        (proj / rel).write_text(text, encoding="utf-8", newline="\n")
    flags = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    subprocess.run(["git", "init", "-q", str(proj)], check=True, capture_output=True, **flags)
    subprocess.run(["git", "-C", str(proj), "add", "-A"], check=True, capture_output=True, **flags)
    monkeypatch.setattr(wh, "WORKFLOW_DIR", tmp_path / "workflow")
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    return proj


def test_003_material_smells_carry_callsites(git_world):
    lines = wh.pick_material([str(git_world / "report" / "csv_export.py")], {})
    line = lines[0]
    # 死碼：只有測試 import，正式程式 0 處；吞錯的 loader 有兩支正式程式 import（單行 from … import 與分好幾行的括號匯入都算）
    assert "legacy_export.py｜long_function｜分數 48｜呼叫點 0，另有測試 1 支" in line, line
    assert "loader.py｜swallowed_exception｜分數 12｜呼叫點 2（csv_export.py、summary.py），1 支解析不了沒算" in line, line
    assert "notes.py" not in line and "alias.py" not in line         # 只提到字樣、別名叫 loader 的都不算呼叫點


def test_003_callsites_cannot_judge_says_so(git_world, tmp_path):
    import time as _t
    far = _t.monotonic() + 5
    assert wh._callsites(git_world, "report/fmt.js", far) == "呼叫點 1（app.js）"          # JS require 路徑的檔名
    assert wh._callsites(git_world, "Game/Skill.cs", far).startswith("呼叫點 無法判（.cs")
    assert wh._callsites(git_world, "report/loader.py", _t.monotonic() - 1) == "呼叫點 無法判（來不及算）"
    outside = tmp_path / "not_git"
    outside.mkdir()
    assert wh._callsites(outside, "a.py", far) == "呼叫點 無法判（不在 git 版控或 git grep 失敗）"
    # 腳本靠被執行不靠被 import：呼叫點 0 要補一句，不然看起來像死碼；檔名不能 import 的直接說算不出
    assert wh._callsites(git_world, "tools/run_report.py", far) == "呼叫點 0，本身可直接執行（呼叫點只算 import）"
    assert wh._callsites(git_world, "tools/move-dir-check.py", far).startswith("呼叫點 無法判（檔名不是合法模組名")
    # 點開頭目錄底下的檔：自己那一行不能被當成呼叫者，別人的 import 照算
    assert wh._callsites(git_world, ".claude/hooks/gate.py", far) == "呼叫點 1（use_gate.py）"
    assert wh._callsites(git_world, "./report/loader.py", far).startswith("呼叫點 2（csv_export.py、summary.py）")
    assert wh._callsites(git_world, "report/fmt.js", _t.monotonic() + 0.3).startswith("呼叫點")     # 預算很緊也回一句，不丟例外


@pytest.mark.parametrize("text,stem,lang,hit", [
    ("from report.loader import load_rows", "loader", "py", True),
    ("from report import loader, summary", "loader", "py", True),
    ("from . import loader", "loader", "py", True),
    ("from .loader import x  # 註解", "loader", "py", True),
    ("import report.loader as ld", "loader", "py", True),
    ("import os, report.loader", "loader", "py", True),
    ("from report import (\n    summary,\n    loader,\n)\n", "loader", "py", True),     # 分好幾行的括號匯入（codex 審）
    ("def f():\n    from report import loader\n", "loader", "py", True),           # 函式裡的匯入
    ("from report.tools import parse as loader", "loader", "py", False),          # 別名叫 loader 不算（codex 審）
    ("x = loader.load_rows(f)", "loader", "py", False),                           # 用到但不是 import
    ("from report.loader_v2 import y", "loader", "py", False),
    ("# from report.loader import y\ns = 'import loader'", "loader", "py", False),  # 註解與字串
    ("def broken(:\n    import loader", "loader", "py", None),                     # 解析不了：不猜
    ("import { a } from './util/fmt.js';", "fmt", "js", True),
    ("const x = require(\"../fmt\")", "fmt", "js", True),
    ("const x = require('../fmtx')", "fmt", "js", False),
    ("// const x = require('../fmt')\n/* import y from './fmt' */\n * require('./fmt')", "fmt", "js", False),   # 註解行（codex 審）
])
def test_003_imports_stem(text, stem, lang, hit):
    assert wh._imports_stem(text, stem, lang) is hit


# ─── Stop 真流程：送一次、不是 block；記帳 ─────────────────────────────────────

_PASS_CFG = {"reconcile_gate": {"enabled": False}, "verify_scope": {"enabled": False}, "sync_reminder": {"enabled": False},
             "atom_audit": {"enabled": False}, "aec": {"scan_report_gate": False}, "pick_one": {"enabled": True}}


@pytest.fixture
def stop_run(world, monkeypatch, capsys):
    """驅動 handle_stop：其他閘都關或換掉，只看這一段。回 run(last_message, mods, config, state) → (stdout, state, guard 事件)。"""
    proj, _ = world
    logs: list = []
    for name, fn in (("_find_session_transcript", lambda *a, **k: None), ("token_warn_payload", lambda *a, **k: ""),
                     ("detect_evasion", lambda *a, **k: None), ("write_state", lambda *a, **k: None),
                     ("_attribute_usefulness", lambda *a, **k: None), ("_detect_uncommitted_files", lambda mf: []),
                     ("_maybe_spawn_user_extract_worker", lambda *a, **k: None), ("_hud_alive", lambda *a, **k: (True, {})),
                     ("_should_deep_postmortem", lambda *a, **k: False), ("reading_path_note", lambda *a, **k: ("", False)),
                     ("append_guard_log", lambda guard, payload: logs.append((guard, payload)))):
        monkeypatch.setattr(st, name, fn)

    def run(message, mods, config=None, **extra):
        state = {"phase": "working", "modified_files": mods, "failing_tests": [], "recent_user_prompts": [],
                 "stop_blocked_count": 0, "turn_seq": 5, "session": {"cwd": str(proj)}, **extra}
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        logs.clear()
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": str(proj), "last_assistant_message": message},
                           _PASS_CFG if config is None else config)
        cap = capsys.readouterr()
        run.err = cap.err                    # 斷言失敗時印出來看是哪道閘先走了
        return cap.out, state, [p for g, p in logs if g == "pick_one"]
    return proj, run


def _mod(path, turn=5):
    return {"path": str(path), "session_id": _SID, "turn_seq": turn, "last_turn_seq": turn}


def test_stop_sends_pick_once_as_context_not_block(stop_run):
    proj, run = stop_run
    mods = [_mod(proj / "Game" / "Battle" / "Damage.cs")]
    out, state, ev = run("改好了，全部完成。", mods)
    assert out.strip(), run.err
    payload = json.loads(out.strip().splitlines()[-1])
    assert "decision" not in payload                                                     # 不是擋
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert ctx.startswith("[Guardian:PickOne]") and "【戰鬥】" in ctx and "為什麼不是數字最高的那個：" in ctx
    assert state["pick_one"][_SID]["asked_turn"] == 5 and ev[-1]["event"] == "asked"
    out2, _, _ = run("改好了，全部完成。", mods, pick_one=state["pick_one"])                 # 同一批改動第二次
    assert "PickOne" not in out2


@pytest.mark.parametrize("message,mods_kind,config", [
    ("我先看一下這段在做什麼，接著改。", "code", None),                                    # 沒到交付邊界
    ("改好了，全部完成。", "doc", None),                                                  # 只改文件
    ("改好了，全部完成。", "code", {k: v for k, v in _PASS_CFG.items() if k != "pick_one"}),   # 設定沒開
])
def test_stop_does_not_send_pick(stop_run, message, mods_kind, config):
    proj, run = stop_run
    path = proj / ("Game/Battle/Damage.cs" if mods_kind == "code" else "docs/readme.md")
    out, state, _ = run(message, [_mod(path)], config)
    assert "PickOne" not in out and not (state.get("pick_one") or {}).get(_SID, {}).get("asked_turn")


def test_stop_records_pick_from_delivery_and_does_not_ask_again(stop_run):
    proj, run = stop_run
    out, state, ev = run(PICK, [_mod(proj / "Game" / "Battle" / "Damage.cs")])
    assert "PickOne" not in out                                                          # AI 自己先寫了 → 不再問
    rows = _rows(proj)
    assert len(rows) == 1 and rows[0]["source"] == "pick" and rows[0]["proposal"] and rows[0]["owner"]
    assert [e["event"] for e in ev] == ["recorded"]


# ─── 開場列出附了建議的未結項 ─────────────────────────────────────────────────

def test_session_start_lists_proposals_first_including_parted_items(world, monkeypatch):
    proj, wf = world
    from handlers import session_start as ss
    monkeypatch.setattr(ss, "WORKFLOW_DIR", wf)
    slug = wh.tracking_slug(str(proj))
    wh.record_pick({}, _SID, 5, PICK, str(proj), at="2026-10-19T00:00:00")
    wh.append_tracking(slug, wh.tracking_entries("s", 1, "沒部位沒建議的雜項追蹤一則\n"
                                                       "沒部位但有建議的一則｜建議：補一支測試", at="2026-10-20T00:00:00"))
    adv = ss._tracking_advisory(str(proj), {})
    assert len(adv) == 2
    head = adv[0]
    assert "之前交付時點出、還沒解的問題 2 件" in head                                     # 反例：舊碼不列有部位的項目
    assert head.index("沒部位但有建議的一則") < head.index("[戰鬥] Game/Battle/Damage.cs")   # 最新的先列
    assert "建議：暴擊分支改用區域變數，字典只讀｜該誰解：下一個寫碼 session" in head
    assert "第一則回覆開頭用一兩句白話告訴使用者" in head
    assert "本專案未結追蹤項 1 筆" in adv[1] and "沒部位沒建議的雜項追蹤一則" in adv[1]
    assert "沒部位但有建議的一則" not in adv[1]                                           # 不重複列
    assert ss._tracking_advisory(str(proj), {"tracking_advisory_sent": True}) == []


def test_part_injection_block_shows_proposal(world):
    block = wh.tracking_block([{"text": "暴擊分支把共用字典當暫存", "at": "2026-10-20T00:00:00", "part": "戰鬥",
                                "proposal": "改用區域變數", "owner": "下一個寫碼 session"}], 2000)
    assert "- 暴擊分支把共用字典當暫存（2026-10-20）｜建議：改用區域變數｜該誰解：下一個寫碼 session" in block
