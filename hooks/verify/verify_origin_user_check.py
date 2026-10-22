"""verify_origin_user_check.py：目標樹節點標「使用者說的」要對得到原話（規則 ORIGIN_USER_NEEDS_QUOTE，T2.18）。

覆蓋：add／update 標 origin=user 時 quote 或節點文字是原話字面子串 → 保持 user（history 記引用回合、存 quote 與 said_seq）；
對不到、quote 太短、只出現在同伴轉述 → 強制 inferred、回傳 note 提醒、下一則訊息的樹提示帶一次就清、守門紀錄留帳；
樹根 origin 不動、顯示一律「AI 的解讀」，set／改寫樹根／匯入時切句列出原話裡沒有的句子提醒一次；
匯入的子節點不核；guard.origin_user_check.enabled=false 不核；驗收題 C 第二段的真實輸入。
不碰 live：目標檔、守門紀錄、OverviewHub log 全落 tmp；設定用 monkeypatch 給。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_origin_user_check.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_core  # noqa: E402
import wg_need_goal as ng  # noqa: E402
import wg_overview as wo  # noqa: E402

SID = "sess-origin-0001"


@pytest.fixture
def env(tmp_path, monkeypatch):
    wf = tmp_path / "wf"
    wf.mkdir()
    guard = []
    cfg = {"guard": {}}
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_core, "append_guard_log", lambda g, p: guard.append((g, p)))
    monkeypatch.setattr(wg_core, "load_config", lambda: cfg)
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    return {"guard": guard, "cfg": cfg, "tmp": tmp_path}


def _op(action, turn=1, sid=SID, **kw):
    return ng.apply_op(sid, turn, {"action": action, **kw}, "")


def _node(nid, sid=SID):
    doc = ng.load(sid)
    return ng.tree_of(doc, nid)["nodes"][nid]


def _events(env, name):
    return [p for g, p in env["guard"] if g == "need_goal" and p.get("event") == name]


def _tree_with(said, goal="把稽核紀錄留下來"):
    ng.on_prompt(SID, said, 1, {})
    assert _op("set", goal=goal)["ok"]
    assert ng.active_tree(ng.load(SID))["user_said"][0]["text"] == said   # 前置：原話真的掛在樹上


def test_quote_in_user_words_keeps_user_and_records_turn(env):
    _tree_with("把 audit 寫進 log 檔，格式自己定")
    r = _op("add", items=[{"text": "audit 要寫進 log 檔", "origin": "user", "quote": "audit 寫進 log 檔"}])
    n = _node("T1.1")
    assert r["ok"] and n["origin"] == "user", n
    assert n["quote"] == "audit 寫進 log 檔" and n["said_seq"] == ng.active_tree(ng.load(SID))["user_said"][0]["seq"]
    assert n["history"][-1]["what"] == "origin" and "引用第 1 回合" in n["history"][-1]["why"]
    assert "對不到原話" not in r["text"]
    assert _events(env, "origin_quoted") and not _events(env, "origin_downgraded")


def test_unquoted_inference_downgraded_and_reminded_once(env):
    _tree_with("adjust_stock 要支援負數（退貨），扣到低於 0 要擋下來並說明")
    r = _op("add", items=[{"text": "舊報表不被弄壞", "origin": "user"}])
    n = _node("T1.1")
    assert r["ok"] and n["origin"] == "inferred", n
    assert "對不到原話" in r["text"] and "quote" in r["text"]
    assert ng.load(SID).get("origin_downgraded"), "state 要記一筆 origin_downgraded"
    ev = _events(env, "origin_downgraded")
    assert ev and ev[0]["node"] == "T1.1" and ev[0]["text"] == "舊報表不被弄壞"
    first = ng.on_prompt(SID, "繼續", 2, {})
    assert "T1.1" in first and "對不到原話" in first, first
    second = ng.on_prompt(SID, "再繼續", 3, {})
    assert "對不到原話" not in second, second


def test_quote_only_in_peer_message_downgraded_as_peer(env):
    _tree_with("幫我整理退貨流程")
    ng.on_prompt(SID, '<cross-session-message from-name="claude-aa">舊報表的輸出格式不能變</cross-session-message>', 2, {})
    assert ng.active_tree(ng.load(SID))["peer_said"], "前置：同伴轉述要在 peer_said"
    r = _op("add", turn=2, items=[{"text": "報表格式不變", "origin": "user", "quote": "舊報表的輸出格式不能變"}])
    assert _node("T1.1")["origin"] == "inferred"
    assert "同伴 claude-aa 說的，不是使用者" in r["text"], r["text"]


def test_text_itself_is_user_words_without_quote(env):
    _tree_with("扣到低於 0 要擋下來並說明，其他照舊")
    _op("add", items=[{"text": "扣到低於 0 要擋下來並說明", "origin": "user"}])
    assert _node("T1.1")["origin"] == "user"


def test_short_quote_downgraded(env):
    _tree_with("把 audit 寫進 log 檔")
    r = _op("add", items=[{"text": "要有稽核", "origin": "user", "quote": "audit"}])
    assert _node("T1.1")["origin"] == "inferred" and "至少要 6 字" in r["text"]


@pytest.mark.parametrize("quote, ok", [
    ("要有測試。", True),        # 第三跑 B-1 T1.3：原話整句（前後都是句號），5 字
    ("要有測試", True),          # 不帶句末標點也算整句
    ("有測試。", False),         # 句子中段：左邊是「要」不是句界
    ("好。", False),             # 整句但只有 1 個字
])
def test_short_whole_sentence_quote_counts(env, quote, ok):
    said = "好。月報改用台北時間歸月，不要動到它。要有測試。"
    _tree_with(said)
    assert quote.rstrip("。") in said, "前置：引用的字真的在原話裡"
    r = _op("add", items=[{"text": "有測試", "origin": "user", "quote": quote}])
    assert (_node("T1.1")["origin"] == "user") is ok, r["text"]


def test_whole_sentence_quote_punctuation_must_match(env):
    """codex 004：短句引用自帶的句末標點要跟原話一樣：原話是問句「要有測試？」，引成「要有測試。」不是逐字引用；照原標點引、或不帶標點都算。"""
    _tree_with("要有測試？")
    _op("add", items=[{"text": "有測試", "origin": "user", "quote": "要有測試。"},
                      {"text": "有測試二", "origin": "user", "quote": "要有測試？"},
                      {"text": "有測試三", "origin": "user", "quote": "要有測試"}])
    assert [_node(f"T1.{i}")["origin"] for i in (1, 2, 3)] == ["inferred", "user", "user"]


def test_mcp_quote_description_matches_rule():
    """MCP need_goal 的 quote 說明是 LLM 讀的契約：要說得出「不到 6 字的整句也算」，不然 AI 不會去引短句（規則 ORIGIN_USER_NEEDS_QUOTE）。"""
    js = (HOOKS_DIR.parent / "tools" / "workflow-guardian-mcp" / "lib" / "mcp.js").read_text(encoding="utf-8")
    line = next(ln for ln in js.splitlines() if "quote:" in ln and "origin=user" in ln)
    assert "整句" in line, line


def test_update_to_user_checked_both_ways(env):
    _tree_with("把 audit 寫進 log 檔，格式自己定")
    _op("add", items=[{"text": "稽核紀錄落地", "origin": "inferred"}, {"text": "格式要固定", "origin": "inferred"}])
    ok = _op("update", turn=2, items=[{"id": "T1.1", "origin": "user", "quote": "把 audit 寫進 log 檔", "why": "原話有"}])
    assert ok["ok"] and _node("T1.1")["origin"] == "user" and "對不到原話" not in ok["text"]
    bad = _op("update", turn=2, items=[{"id": "T1.2", "origin": "user", "quote": "格式要固定", "why": "我覺得是"}])
    assert bad["ok"] and _node("T1.2")["origin"] == "inferred" and "對不到原話" in bad["text"]


def test_update_without_why_still_checks_origin(env):
    """WHY_OPTIONAL 反例：why 拔掉後，標使用者說的、卻對不到原話，照樣降級；對得到的照樣收成使用者說的。"""
    _tree_with("把 audit 寫進 log 檔，格式自己定")
    _op("add", items=[{"text": "稽核紀錄落地", "origin": "inferred"}, {"text": "格式要固定", "origin": "inferred"}])
    bad = _op("update", turn=2, items=[{"id": "T1.2", "origin": "user", "quote": "格式要固定"}])
    assert bad["ok"] and _node("T1.2")["origin"] == "inferred" and "對不到原話" in bad["text"], bad["text"]
    ok = _op("update", turn=2, items=[{"id": "T1.1", "origin": "user", "quote": "把 audit 寫進 log 檔"}])
    assert ok["ok"] and _node("T1.1")["origin"] == "user" and "對不到原話" not in ok["text"], ok["text"]


def test_text_update_on_user_node_rechecked(env):
    """codex BLOCK：只改文字、沒帶 origin，使用者說的節點也要重核（沒 quote 的舊節點改成使用者沒說過的話 → 降級）。"""
    _tree_with("請把稽核結果寫入日誌，其他照舊")
    env["cfg"]["guard"]["origin_user_check"] = {"enabled": False}
    _op("add", items=[{"text": "請把稽核結果寫入日誌", "origin": "user"}, {"text": "稽核要寫日誌", "origin": "user"}])
    env["cfg"]["guard"]["origin_user_check"] = {"enabled": True}
    assert "quote" not in _node("T1.1") and _node("T1.2")["origin"] == "user"   # 前置：沒核過、沒 quote 的 user 節點
    r = _op("update", turn=2, items=[{"id": "T1.1", "text": "刪除所有歷史報表資料", "why": "改寫"}])
    assert _node("T1.1")["origin"] == "inferred" and "對不到原話" in r["text"], r["text"]
    ok = _op("update", turn=2, items=[{"id": "T1.2", "text": "稽核結果進日誌", "quote": "請把稽核結果寫入日誌", "why": "附引用"}])
    assert _node("T1.2")["origin"] == "user" and "⚠" not in ok["text"], ok["text"]


def test_early_and_long_user_words_still_quotable(env):
    """005：顯示用的 user_said 只留 20 則、單則截 1000 字；核對要用完整原話，早期與長訊息後段的話照樣引得到。"""
    _tree_with("先開樹")
    ng.on_prompt(SID, "記得把稽核結果寫入日誌", 2, {})
    for i in range(25):
        ng.on_prompt(SID, f"第 {i} 則閒聊", 3 + i, {})
    ng.on_prompt(SID, "字" * 1200 + "舊報表的欄位順序不能變", 40, {})
    shown = [s["text"] for s in ng.active_tree(ng.load(SID))["user_said"]]
    assert not any("稽核結果寫入日誌" in t for t in shown)               # 前置：早期那則已不在顯示清單
    assert not any("欄位順序不能變" in t for t in shown)                 # 前置：長訊息後段被截掉
    r = _op("add", turn=41, items=[{"text": "稽核要進日誌", "origin": "user", "quote": "把稽核結果寫入日誌"},
                                   {"text": "報表欄位順序不變", "origin": "user", "quote": "舊報表的欄位順序不能變"}])
    assert [_node("T1.1")["origin"], _node("T1.2")["origin"]] == ["user", "user"], r["text"]
    assert "said_all" not in ng.handoff_block(SID)                       # 完整原話不進續接單


def test_text_matched_node_rewrite_does_not_reuse_old_text(env):
    """005：靠節點文字本身對上的節點，改寫文字後不能拿舊文字當 quote 重核（舊文字一定對得上）；AI 明確引的 quote 照樣拿來核。"""
    _tree_with("扣到低於 0 要擋下來並說明，其他照舊")
    _op("add", items=[{"text": "扣到低於 0 要擋下來並說明", "origin": "user"},
                      {"text": "負數要擋", "origin": "user", "quote": "扣到低於 0 要擋下來"}])
    assert _node("T1.1")["quote_by"] == "text" and _node("T1.2")["quote_by"] == "quote"   # 前置：兩種對上方式
    _op("update", turn=2, items=[{"id": "T1.1", "text": "順便重寫整個庫存模組", "why": "改寫"},
                                 {"id": "T1.2", "text": "低於 0 擋下並回說明", "why": "改寫"}])
    assert _node("T1.1")["origin"] == "inferred" and _node("T1.2")["origin"] == "user"


def test_imported_user_node_without_quote_kept(env, monkeypatch):
    _tree_with("讓匯出變快")
    env["cfg"]["guard"]["origin_user_check"] = {"enabled": False}
    _op("add", items=[{"text": "上一個 session 記的節點", "origin": "user"}])
    assert _node("T1.1")["origin"] == "user"            # 前置：續接單裡真有一個沒引用的 origin=user 節點
    block = ng.handoff_block(SID)
    env["cfg"]["guard"]["origin_user_check"] = {"enabled": True}
    res = ng.import_handoff("sess-origin-next", block, str(env["tmp"] / "next-phase-x.md"), 1)
    assert res["imported"]
    assert _node("T1.1", sid="sess-origin-next")["origin"] == "user"


def test_set_root_origin_unchanged_label_is_ai_reading_and_lists_missing_sentence(env):
    """002 ①：樹根兩句、一句在原話一句不在 → 只列不在的那句；origin 欄位仍 user、顯示一律「AI 的解讀」；提醒當下＋下一則各一次。"""
    ng.on_prompt(SID, "adjust_stock 要支援負數退貨，其他照舊", 1, {})
    r = _op("set", goal="adjust_stock 要支援負數退貨；舊報表不被這次改動弄壞")
    root = _node("T1")
    assert root["origin"] == "user" and "history" in root
    assert "[進行中｜明確｜AI 的解讀]" in r["text"] and "｜使用者說的]" not in r["text"]
    line = next(ln for ln in r["text"].splitlines() if ln.startswith("[NeedGoal] 樹根這幾句原話裡沒有"))
    assert "「舊報表不被這次改動弄壞」" in line and "adjust_stock 要支援負數退貨" not in line, line
    assert _events(env, "root_unquoted")[0]["sentences"] == ["舊報表不被這次改動弄壞"]
    assert "樹根這幾句原話裡沒有" in ng.on_prompt(SID, "繼續", 2, {})
    assert "樹根這幾句原話裡沒有" not in ng.on_prompt(SID, "再繼續", 3, {})
    assert "AI 的解讀" in ng.handoff_block(SID)   # 續接單用同一個 render


def test_set_root_all_in_user_words_no_reminder(env):
    """002 ②：樹根每句都是原話子串 → 不提醒、不留帳。"""
    ng.on_prompt(SID, "adjust_stock 要支援負數退貨，扣到低於 0 要擋下來", 1, {})
    r = _op("set", goal="adjust_stock 要支援負數退貨，扣到低於 0 要擋下來")
    assert "樹根這幾句原話裡沒有" not in r["text"] and not _events(env, "root_unquoted")
    assert not ng.load(SID).get("origin_downgraded")


def test_set_root_rewrite_rechecked(env):
    """002：set 改寫樹根（why 那條路）同樣重核。"""
    ng.on_prompt(SID, "adjust_stock 要支援負數退貨", 1, {})
    assert "樹根這幾句" not in _op("set", goal="adjust_stock 要支援負數退貨")["text"]
    r = _op("set", turn=2, goal="adjust_stock 要支援負數退貨，順便重寫整個報表模組", why="AI 自己擴範圍")
    assert "「順便重寫整個報表模組」" in r["text"], r["text"]


def test_import_root_checked(env):
    """002 ④：從續接單匯入的樹根同樣切句核對（對前一個 session 的原話）。"""
    ng.on_prompt(SID, "讓匯出變快，其他不動", 1, {})
    env["cfg"]["guard"]["origin_user_check"] = {"enabled": False}
    _op("set", goal="讓匯出變快；而且順便換掉資料庫")
    block = ng.handoff_block(SID)
    env["cfg"]["guard"]["origin_user_check"] = {"enabled": True}
    res = ng.import_handoff("sess-origin-next", block, str(env["tmp"] / "next-phase-x.md"), 1)
    assert res["imported"] and "「而且順便換掉資料庫」" in res["text"] and "讓匯出變快」" not in res["text"], res["text"]
    assert ng.tree_of(ng.load("sess-origin-next"), res["imported"][0])["nodes"][res["imported"][0]]["origin"] == "user"


def test_switch_off_keeps_old_behavior(env):
    env["cfg"]["guard"]["origin_user_check"] = {"enabled": False}
    _tree_with("adjust_stock 要支援負數")
    r = _op("add", items=[{"text": "舊報表不被弄壞", "origin": "user"}])
    assert _node("T1.1")["origin"] == "user" and "對不到原話" not in r["text"]
    assert not _events(env, "origin_downgraded") and not _events(env, "origin_quoted")


# 驗收題 C 第二段真實輸入（workflow/inbox/wave1-kit/results/2026-10-20/C-2/：need-goal/812c83d6-….json 的 user_said
# 與 transcript/812c83d6-….jsonl 裡新 session 的 set／add 原樣）。新 session 只看了 git diff 就把推論標成使用者說的。
C2_SAID = "接手 qc-stock 的退貨調整需求，先告訴我目前做到哪、中途改過什麼要求，再繼續。"
C2_GOAL = "退貨要能正確扣庫存、不會扣成負的，而且舊報表不被這次改動弄壞"
C2_ITEMS = [
    {"text": "負數 qty 當退貨扣庫存，扣到剛好 0 可以、低於 0 要擋且庫存不變", "clarity": "clear", "origin": "user"},
    {"text": "每筆調整要回傳可記錄的事件字串（中途追加的要求）", "clarity": "clear", "origin": "user"},
    {"text": "舊報表把回傳值當 int 印，介面改 tuple 後要有解法（目前靠 skip 蓋住）", "clarity": "open", "origin": "user"},
    {"text": "庫存正本目前是模組級 LEVELS dict，要不要落地持久化", "clarity": "open", "origin": "inferred"},
]


def test_c2_real_input_inferred_nodes_downgraded(env):
    _tree_with(C2_SAID, goal=C2_GOAL)
    r = _op("add", items=[dict(it) for it in C2_ITEMS])
    assert [_node(f"T1.{i}")["origin"] for i in range(1, 5)] == ["inferred"] * 4, r["text"]
    assert sum("⚠" in ln and "對不到原話" in ln for ln in r["text"].splitlines()) == 3, r["text"]
    assert {e["node"] for e in _events(env, "origin_downgraded")} == {"T1.1", "T1.2", "T1.3"}
    # 「舊報表不被這次改動弄壞」實際寫在樹根：origin 不動（樹根列句見下一案）
    assert _node("T1")["origin"] == "user"


def test_c2_real_root_listed_at_set(env):
    """002 ③：C-2 真實樹根在 set 當下就被列出（舊碼什麼都不說）。"""
    ng.on_prompt(SID, C2_SAID, 1, {})
    r = _op("set", goal=C2_GOAL)
    line = next(ln for ln in r["text"].splitlines() if ln.startswith("[NeedGoal] 樹根這幾句原話裡沒有"))
    assert "舊報表不被這次改動弄壞」" in line and "｜AI 的解讀]" in r["text"], r["text"]   # 切出來的句子帶「而且」


def test_005_quote_from_words_said_while_tree_closed(env):
    """第四跑 C-1 T1.7（規則 ORIGIN_SAID_INCLUDES_UNATTACHED）：第 4 回合完整對照全達成、樹結束；第 5 回合使用者糾正，原話先記進
    said_log、還沒掛上樹（樹結束了）；同一次 update 把節點改回進行中、逐字引用那則原話 → 要認得。舊碼先核再重開樹，判「不在任何一則
    使用者原話裡」降成推出來的。"""
    _tree_with("補一個：折扣碼不要寫死在程式裡，放進 config/shop.json，之後要加新碼改設定檔就好。")
    assert _op("add", items=[{"text": "折扣碼放 config/shop.json", "origin": "user", "quote": "之後要加新碼改設定檔就好"}])["ok"]
    ng.update_locked(SID, lambda doc: doc["trees"]["T1"].update(status="closed"))
    said = "不對，折扣碼不要放 shop.json，改成另外開一個新檔 config/promos.json 放；shop.json 只留門檻那一個改動。"
    ng.on_prompt(SID, said, 5, {})
    doc = ng.load(SID)
    assert doc["trees"]["T1"]["status"] == "closed" and doc["said_log"][-1]["attached"] is False, "前置：原話還沒掛上樹"
    r = _op("update", turn=5, items=[{"id": "T1.1", "text": "折扣碼放新檔 config/promos.json，shop.json 只留門檻改動",
                                      "origin": "user", "quote": "改成另外開一個新檔 config/promos.json 放；shop.json 只留門檻那一個改動",
                                      "status": "doing", "why": "使用者糾正"}])
    n = _node("T1.1")
    assert r["ok"] and n["origin"] == "user" and "對不到原話" not in r["text"], r["text"]
    assert n["said_seq"] == doc["said_log"][-1]["seq"] and not _events(env, "origin_downgraded")
    # 反例：引用不在任何一則原話（含沒掛上的）照降級
    r = _op("update", turn=5, items=[{"id": "T1.1", "origin": "user", "quote": "另外開一個新檔 config/discount.json", "why": "x"}])
    assert _node("T1.1")["origin"] == "inferred" and "對不到原話" in r["text"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
