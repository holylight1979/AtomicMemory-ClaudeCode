"""verify_candidates_trigger.py：Q5 候選填空（A5.1～A5.4）。

四案：觸發詞＋有表送一次、第二次不送；smells_report 過期仍送附一行；無報告退導讀卡 defects 片前 N；無觸發詞不送。
A5.3：同檔第 2 次放行的 Edit 附候選、第 3 次不送（被擋的不算）。A5.4：general 意圖命中 idle_triggers 一 session 一行。
A5.1：前例行是填空範本；照抄範本不算交；「無」→ locate_quality none、「待規格：…」→ free。
fixture hooks/verify/fixtures/v6/q5/（smells.json 七列：五列戰鬥、一列第六名、一列別部位；card.md 五段）。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_candidates_trigger.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import overview_hub as oh  # noqa: E402
import wg_overview as wo  # noqa: E402


@pytest.fixture(autouse=True)
def _whole_card(monkeypatch):
    """這支照整張注入（card_injection=full）寫的；指標制（預設）的案例在 verify_overview_card_pointer.py。"""
    from hub_config import HUB_DEFAULTS
    monkeypatch.setitem(HUB_DEFAULTS, "card_injection", "full")

FIX = HOOKS_DIR / "verify" / "fixtures" / "v6" / "q5"


@pytest.fixture(autouse=True)
def _temp_rules_off(monkeypatch):
    """假專案建在 pytest tmp 下：關掉規則 TEMP_COPY_NOT_PROJECT（否則暫存目錄下的專案不注入導讀卡、不擋）。"""
    monkeypatch.setenv("WG_TEMP_RULES", "off")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    monkeypatch.setattr(wo, "_atom_debug_error", lambda src, exc: None)   # 不寫真 atom-debug log


@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "proj"
    (root / ".claude" / "memory" / "shared" / "戰鬥").mkdir(parents=True)
    (root / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n| `Game\\Battle\\` | 戰鬥 | `戰鬥導讀` | 有 |\n", encoding="utf-8")
    shutil.copy(FIX / "card.md", root / ".claude" / "memory" / "shared" / "戰鬥" / "戰鬥導讀.md")
    (root / "Game" / "Battle").mkdir(parents=True)
    (root / "Game" / "Battle" / "A.cs").write_text("x", encoding="utf-8")
    return root


def _with_report(root, stale_days=0):
    rp = root / ".claude" / "smells.json"
    shutil.copy(FIX / "smells.json", rp)
    if stale_days:
        old = time.time() - stale_days * 86400
        os.utime(rp, (old, old))
    (root / ".claude" / "overview-hub.json").write_text(json.dumps({"smells_report": ".claude/smells.json"}), encoding="utf-8")
    return rp


def _transcript(tmp_path, texts):
    tp = tmp_path / "t.jsonl"
    with open(tp, "w", encoding="utf-8") as f:
        for t in texts:
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}}, ensure_ascii=False) + "\n")
    return str(tp)


def _inject(root, state, tp):
    f1 = str(root / "Game" / "Battle" / "A.cs")
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(root), tp, {})
    assert txt
    return f1, txt


def _log_events(tmp_path):
    return [json.loads(l)["event"] for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]


# ─── Q5 四案 ────────────────────────────────────────────────────────

def test_trigger_with_table_sends_once_top_n_filtered_in_report_order(proj, tmp_path):
    _with_report(proj)
    state, tp = {}, _transcript(tmp_path, ["x"])
    _inject(proj, state, tp)
    txt = wo.on_prompt(state, "s", "為什麼又壞了？找根因", tp, {}, intent="debug")
    assert txt and "【戰鬥】候選前 5" in txt and "smells 報告" in txt
    rows = [l for l in txt.splitlines() if l.startswith("- ")]
    assert len(rows) == 5 and rows[0].startswith("- Game/Battle/DamageSystem.cs｜hotspot") and rows[-1].startswith("- Game/Battle/Util.cs")
    assert "Io.cs" not in txt and "Panel.cs" not in txt            # 第六名與別部位不進
    assert "根因卡：`戰鬥導讀`" in txt and "先答兩問" in txt and oh.ROOT_CAUSE_SENTENCE in txt
    assert "沒更新" not in txt
    assert len(state["candidates_sent"]) == 1
    assert wo.on_prompt(state, "s", "再問一次根因在哪", tp, {}, intent="debug") is None     # 第二次不送
    assert _log_events(tmp_path).count("candidates") == 1


def test_stale_report_still_sent_with_one_line(proj, tmp_path):
    _with_report(proj, stale_days=30)
    state, tp = {}, _transcript(tmp_path, ["x"])
    _inject(proj, state, tp)
    txt = wo.on_prompt(state, "s", "這個老問題治本", tp, {}, intent="debug")
    assert txt and "天沒更新" in txt and "smells_max_age_days=7" in txt and "仍送" in txt
    assert "DamageSystem.cs" in txt                                 # 資料照回


def test_no_report_falls_back_to_card_defects(proj, tmp_path):
    state, tp = {}, _transcript(tmp_path, ["x"])
    _inject(proj, state, tp)
    txt = wo.on_prompt(state, "s", "root cause?", tp, {}, intent="debug")
    assert txt and "導讀卡「已知病灶」段" in txt and "最後一擊無訊號" in txt and "結算生命期" in txt
    # 沒病灶段也沒報告 → 明說無候選，仍送根因卡與兩問
    (proj / ".claude" / "memory" / "shared" / "戰鬥" / "戰鬥導讀.md").write_text("# 戰鬥導讀\n\n## 知識\n\n- [臨] 沒分段\n", encoding="utf-8")
    state2 = {}
    _inject(proj, state2, tp)
    txt = wo.on_prompt(state2, "s", "又壞了", tp, {}, intent="debug")
    assert txt and "候選：無" in txt and "先答兩問" in txt


def test_no_trigger_word_or_no_table_sends_nothing(proj, tmp_path):
    _with_report(proj)
    state, tp = {}, _transcript(tmp_path, ["x"])
    _inject(proj, state, tp)
    assert wo.on_prompt(state, "s", "幫我加一個按鈕", tp, {}, intent="feature") is None
    assert "candidates_sent" not in state or state["candidates_sent"] == []
    # 有觸發詞但本 session 沒碰過任何部位（無表可對）→ 不送
    assert wo.on_prompt({}, "s", "為什麼又壞了", tp, {}, intent="debug") is None


# ─── A5.3 同檔第二次 Edit ─────────────────────────────────────────────

def test_second_edit_same_file_attaches_candidates_once(proj, tmp_path):
    _with_report(proj)
    state, tp = {}, _transcript(tmp_path, ["x"])
    f1, _ = _inject(proj, state, tp)
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})
    assert deny                                                             # 沒交三行：被擋，不算一次 Edit
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥：A.cs\n定位｜根因層：根因在邏輯層\n定位｜前例：無"}]}}, ensure_ascii=False) + "\n")
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)         # 第 1 次放行：不附
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})                      # 第 2 次：附候選
    assert deny is None and warn and "【戰鬥】候選前 5" in warn and "DamageSystem.cs" in warn
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)         # 第 3 次：不送
    rec = next(v for k, v in state["overview_hub"].items() if k.endswith("|戰鬥"))
    assert rec["edited_files"] == {f1.replace("\\", "/").lower(): 3} and rec["edits"] == 4
    f2 = str(proj / "Game" / "Battle" / "B.cs")
    assert wo.on_edit(state, "s", f2, tp, {}) == (None, None, True)         # 另一檔第 1 次：不附
    assert _log_events(tmp_path).count("second_edit") == 1


def test_second_edit_key_is_case_insensitive(proj, tmp_path):          # 退件 BLOCK 6
    state, tp = {}, _transcript(tmp_path, ["x"])
    f1, _ = _inject(proj, state, tp)
    with open(tp, "a", encoding="utf-8") as f:                              # 注入後才交三行（offset 之後）
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥：A.cs\n定位｜根因層：根因在邏輯層\n定位｜前例：無"}]}}, ensure_ascii=False) + "\n")
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)
    other_case = str(proj / "game" / "battle" / "a.cs")                    # 同一檔、大小寫不同
    warn, deny, _ = wo.on_edit(state, "s", other_case, tp, {})
    assert deny is None and warn and "候選前" in warn                      # 第二次就送
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)          # 第三次不送
    rec = next(v for k, v in state["overview_hub"].items() if k.endswith("|戰鬥"))
    assert list(rec["edited_files"].values()) == [3]


# ─── 004 候選噪音：沒內容一行、一部位一 session 一次 ─────────────────────

_LOCATED = "定位｜部位：戰鬥：A.cs\n定位｜根因層：根因在邏輯層\n定位｜前例：無"


def _located_session(proj, tmp_path):
    """注入戰鬥部位、讀過部位檔、交過定位三行：之後的 Edit 都會放行。"""
    state, tp = {}, _transcript(tmp_path, ["x"])
    _inject(proj, state, tp)
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": _LOCATED}]}},
                           ensure_ascii=False) + "\n")
    return state, tp


def _edit_twice(state, f, tp):
    assert wo.on_edit(state, "s", f, tp, {}) == (None, None, True)
    warn, deny, _ = wo.on_edit(state, "s", f, tp, {})
    assert deny is None
    return warn


def test_second_edit_without_candidates_is_one_line_once_per_part(proj, tmp_path):
    """沒 smells 報告、導讀卡沒病灶段：第 2 次 Edit 只得一行（不附根因卡與兩問）；同部位別的檔第 2 次 Edit 不再送。"""
    (proj / ".claude" / "memory" / "shared" / "戰鬥" / "戰鬥導讀.md").write_text("# 戰鬥導讀\n\n## 知識\n\n- [臨] 沒分段\n", encoding="utf-8")
    state, tp = _located_session(proj, tmp_path)
    warn = _edit_twice(state, str(proj / "Game" / "Battle" / "A.cs"), tp)
    assert warn and "候選：無" in warn and "先答兩問" not in warn and "根因卡" not in warn and "\n" not in warn
    assert warn.startswith("[Guardian:OverviewHub] 【戰鬥】候選：無")
    assert _edit_twice(state, str(proj / "Game" / "Battle" / "B.cs"), tp) is None
    assert len(state["candidates_sent"]) == 1 and state["candidates_sent"][0].endswith("|戰鬥")
    assert _log_events(tmp_path).count("second_edit") == 1


def test_second_edit_with_candidates_full_block_once_per_part(proj, tmp_path):
    """導讀卡有病灶段：第 2 次 Edit 送完整塊（候選＋根因卡＋兩問）；同部位別的檔第 2 次 Edit 不再送；
    on_prompt 觸發詞送過的部位，改檔也不再送（共用 candidates_sent）。"""
    state, tp = _located_session(proj, tmp_path)
    warn = _edit_twice(state, str(proj / "Game" / "Battle" / "A.cs"), tp)
    assert warn and "【戰鬥】候選前 5" in warn and "最後一擊無訊號" in warn and "先答兩問" in warn
    assert _edit_twice(state, str(proj / "Game" / "Battle" / "B.cs"), tp) is None
    assert wo.on_prompt(state, "s", "為什麼又壞了，找根因", tp, {}, intent="debug") is None
    state2, tp2 = _located_session(proj, tmp_path)
    assert wo.on_prompt(state2, "s", "為什麼又壞了，找根因", tp2, {}, intent="debug")
    assert _edit_twice(state2, str(proj / "Game" / "Battle" / "A.cs"), tp2) is None


def test_compact_empty_line_carries_report_notes(proj, tmp_path):
    """smells_report 指到不存在的檔、導讀卡也沒病灶段：一行版仍帶「報告不存在」附註（降級要看得到）。"""
    (proj / ".claude" / "memory" / "shared" / "戰鬥" / "戰鬥導讀.md").write_text("# 戰鬥導讀\n\n## 知識\n\n- [臨] 沒分段\n", encoding="utf-8")
    (proj / ".claude" / "overview-hub.json").write_text(json.dumps({"smells_report": ".claude/missing.json"}), encoding="utf-8")
    state, tp = _located_session(proj, tmp_path)
    warn = _edit_twice(state, str(proj / "Game" / "Battle" / "A.cs"), tp)
    assert warn and "候選：無" in warn and "報告不存在" in warn and "\n" not in warn


# ─── 退件 BLOCK 4／5／7 與 WARN ───────────────────────────────────────

def test_table_but_no_injected_part_sends_whole_project_once(proj, tmp_path):   # BLOCK 4
    _with_report(proj)
    state = {"session": {"cwd": str(proj)}}
    txt = wo.on_prompt(state, "s", "為什麼又壞了", "", {}, intent="debug")
    assert txt and "【全專案】候選前 5" in txt and "DamageSystem.cs" in txt and "【戰鬥】" in txt
    assert "Panel.cs" in txt                                                # 全專案不濾部位（Panel 分數最高）
    assert state["candidates_sent"] == [str(proj).replace("\\", "/").lower() + "|(all)"]
    assert wo.on_prompt(state, "s", "根因到底在哪", "", {}, intent="debug") is None   # 第二次不送
    # 沒報告 → 各部位病灶段合併
    state2 = {"session": {"cwd": str(proj)}}
    (proj / ".claude" / "overview-hub.json").unlink()
    txt = wo.on_prompt(state2, "s", "又壞了", "", {}, intent="debug")
    assert txt and "導讀卡「已知病灶」段" in txt and "【戰鬥】" in txt and "最後一擊無訊號" in txt
    # cwd 不在任何有表專案 → 不送
    assert wo.on_prompt({"session": {"cwd": str(tmp_path)}}, "s", "又壞了", "", {}, intent="debug") is None


def test_project_layer_root_cause_triggers_override(proj, tmp_path):      # BLOCK 5
    (proj / ".claude" / "overview-hub.json").write_text(json.dumps({"root_cause_triggers": ["專案暗號"]}), encoding="utf-8")
    state, tp = {}, _transcript(tmp_path, ["x"])
    _inject(proj, state, tp)
    assert wo.on_prompt(state, "s", "為什麼又壞了，找根因", tp, {}, intent="debug") is None   # 根層預設詞被專案覆蓋掉
    txt = wo.on_prompt(state, "s", "專案暗號", tp, {}, intent="debug")
    assert txt and "【戰鬥】候選前" in txt
    state2 = {"session": {"cwd": str(proj)}}                                # 全專案路徑也用專案層 cfg
    assert wo.on_prompt(state2, "s", "根因", "", {}, intent="debug") is None
    assert wo.on_prompt(state2, "s", "專案暗號", "", {}, intent="debug")


def test_candidates_block_is_capped(proj, tmp_path):                       # BLOCK 7
    rp = proj / ".claude" / "smells.json"
    rp.write_text(json.dumps({"rows": [{"path": "Game/Battle/X.cs", "category": "hotspot", "reason": "長" * 100000,
                                        "score": 9, "part": "戰鬥"}] * 5}, ensure_ascii=False), encoding="utf-8")
    (proj / ".claude" / "overview-hub.json").write_text(json.dumps({"smells_report": ".claude/smells.json", "max_card_chars": 1200}),
                                                        encoding="utf-8")
    state, tp = {}, _transcript(tmp_path, ["x"])
    _inject(proj, state, tp)
    txt = wo.on_prompt(state, "s", "根因", tp, {}, intent="debug")
    assert txt and len(txt) <= 1200 + 20
    assert "根因卡：`戰鬥導讀`" in txt and "先答兩問" in txt and "截" in txt
    rows = [l for l in txt.splitlines() if l.startswith("- Game/")]
    assert rows and all(len(l) <= 200 + 20 for l in rows)                  # 每列 min(200, 1200//5)=200


def test_bad_report_says_parse_failed_then_falls_back(proj, tmp_path):     # WARN 1
    (proj / ".claude" / "smells.json").write_text("{not json", encoding="utf-8")
    (proj / ".claude" / "overview-hub.json").write_text(json.dumps({"smells_report": ".claude/smells.json"}), encoding="utf-8")
    state, tp = {}, _transcript(tmp_path, ["x"])
    _inject(proj, state, tp)
    txt = wo.on_prompt(state, "s", "根因", tp, {}, intent="debug")
    assert "解析失敗" in txt and "不是合法 JSON" in txt and "最後一擊無訊號" in txt and "候選：無" not in txt
    rows, err, _ = wo._smells_rows(proj / ".claude" / "smells.json")
    assert rows == [] and err
    jl = proj / ".claude" / "s.jsonl"
    jl.write_text('{"path": "a.cs", "reason": "r"}\nbroken\n', encoding="utf-8")
    rows, err, _ = wo._smells_rows(jl)
    assert len(rows) == 1 and "1 行不是 JSON" in err
    top = proj / ".claude" / "t.json"
    top.write_text('{"foo": 1}', encoding="utf-8")
    assert "頂層" in wo._smells_rows(top)[1]


def test_generated_at_wins_over_mtime(proj, tmp_path):                      # WARN 2
    data = json.loads((FIX / "smells.json").read_text(encoding="utf-8"))
    data["generated_at"] = "2020-01-01"
    rp = proj / ".claude" / "smells.json"
    rp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")   # mtime＝現在，但 generated_at 很舊
    (proj / ".claude" / "overview-hub.json").write_text(json.dumps({"smells_report": ".claude/smells.json"}), encoding="utf-8")
    state, tp = {}, _transcript(tmp_path, ["x"])
    _inject(proj, state, tp)
    assert "天沒更新" in wo.on_prompt(state, "s", "根因", tp, {}, intent="debug")


# ─── 退件 002：壞報告不拋、候選炸了不改變閘的判定 ───────────────────────

@pytest.mark.parametrize("report,bad_hint", [
    ({"generated_at": "0000-01-01", "rows": [{"path": "Game/Battle/Ok.cs", "category": "hotspot", "reason": "合法列", "part": "戰鬥"}]},
     "generated_at 無法換算：0000-01-01"),
    ({"rows": [{"path": "Game/Battle/Bad.cs", "reason": "part 型別錯", "part": 7},
               {"path": "Game/Battle/Ok.cs", "category": "hotspot", "reason": "合法列", "part": "戰鬥"}]},
     "1 列欄位型別不對"),
    ({"rows": [{"path": "Game/Battle/Bad.cs", "reason": {"x": 1}, "part": "戰鬥"},
               {"path": "Game/Battle/Ok.cs", "category": "hotspot", "reason": "合法列", "part": "戰鬥"}]},
     "1 列欄位型別不對"),
])
def test_bad_report_fields_do_not_raise_and_good_rows_still_sent(proj, report, bad_hint):
    rp = proj / ".claude" / "smells.json"
    rp.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    cfg = wo._cfg({"overview_hub": {"smells_report": str(rp)}}, proj)
    for parts in (None, ("戰鬥",)):                                         # 全專案（part 串接那條）與單部位兩條路都走
        lines, notes, source = wo._smells_lines(proj, cfg, parts, 5, 200)
        assert any("解析失敗" in n and bad_hint in n for n in notes), notes
        assert len(lines) == 1 and "Ok.cs" in lines[0] and "合法列" in lines[0]
        assert "Bad.cs" not in "\n".join(lines)
    state = {"session": {"cwd": str(proj)}}                                  # 端到端：全專案候選不拋
    txt = wo.on_prompt(state, "s", "根因", "", {"overview_hub": {"smells_report": str(rp)}}, intent="debug")
    assert txt and "Ok.cs" in txt and "解析失敗" in txt


def test_candidates_crash_on_second_edit_still_allows(proj, tmp_path, monkeypatch):
    state, tp = {}, _transcript(tmp_path, ["x"])
    f1, _ = _inject(proj, state, tp)
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥：A.cs\n定位｜根因層：根因在邏輯層\n定位｜前例：無"}]}}, ensure_ascii=False) + "\n")
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)

    def _boom(*a, **k):
        raise RuntimeError("候選爆了")
    monkeypatch.setattr(wo, "_candidates_block", _boom)
    warn, deny, changed = wo.on_edit(state, "s", f1, tp, {})
    assert deny is None and changed and warn and "候選產生失敗：RuntimeError: 候選爆了" in warn and "不影響本次放行" in warn
    rec = next(v for k, v in state["overview_hub"].items() if k.endswith("|戰鬥"))
    assert rec["edited_files"][wo._root_key(Path(f1))] == 2
    assert "candidates_error" in _log_events(tmp_path)


def test_candidates_crash_on_prompt_keeps_card_injection(proj, tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("候選爆了")
    monkeypatch.setattr(wo, "_candidates_on_trigger", _boom)
    state = {}
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    txt = wo.on_prompt(state, "s", f"為什麼又壞了 {f1}", "", {}, intent="debug")   # 同時命中部位檔與觸發詞
    assert txt and "本 session 第一次碰到【戰鬥】部位" in txt and "戰鬥導讀" in txt   # 導讀卡照送
    assert "候選產生失敗：RuntimeError: 候選爆了" in txt
    assert any(k.endswith("|戰鬥") for k in state["overview_hub"])


# ─── A5.4 沒事做提示 ─────────────────────────────────────────────────

def test_idle_trigger_general_intent_once_per_session(proj, tmp_path):
    state, tp = {}, _transcript(tmp_path, ["x"])
    assert wo.on_prompt(state, "s", "接下來做什麼？", tp, {}, intent="general") == wo.IDLE_SCAN_LINE
    assert state["idle_scan_sent"] is True
    assert wo.on_prompt(state, "s", "還有什麼要做", tp, {}, intent="general") is None        # 一 session 一次
    assert wo.on_prompt({}, "s", "下一步修 bug", tp, {}, intent="debug") is None             # 非 general 不送
    assert wo.on_prompt({}, "s", "今天天氣", tp, {}, intent="general") is None                # 沒命中
    assert _log_events(tmp_path) == ["idle_scan"]


# ─── A5.1 前例填空範本 ───────────────────────────────────────────────

def test_precedent_fill_in_template_and_copy_does_not_count(proj, tmp_path):
    state, tp = {}, _transcript(tmp_path, ["x"])
    f1, txt = _inject(proj, state, tp)
    assert f"定位｜前例：{wo.PRECEDENT_TEMPLATE}" in txt                       # 注入的第三行就是填空範本
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), tp, {})
    with open(tp, "a", encoding="utf-8") as f:                                # 照抄範本 → 不算交
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": f"定位｜部位：戰鬥：A.cs\n定位｜根因層：根因在邏輯層\n定位｜前例：{wo.PRECEDENT_TEMPLATE}"}]}}, ensure_ascii=False) + "\n")
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})
    assert deny and "定位三行" in deny
    assert not oh.locate_present(f"定位｜部位：戰鬥：A\n定位｜根因層：x\n定位｜前例：{wo.PRECEDENT_TEMPLATE}", "戰鬥")   # 無 template 參數也擋
    with open(tp, "a", encoding="utf-8") as f:                                # 待規格：<理由> 真填 → 交了，quality free
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥：A.cs\n定位｜根因層：根因在邏輯層\n定位｜前例：待規格：規格 §3 沒寫結算順序"}]}}, ensure_ascii=False) + "\n")
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)
    rec = next(v for k, v in state["overview_hub"].items() if k.endswith("|戰鬥"))
    assert rec["located_quality"] == "free" and rec["locate_template"][2] == wo.PRECEDENT_TEMPLATE
    assert oh.locate_quality("定位｜部位：戰鬥：A\n定位｜根因層：x\n定位｜前例：無", "戰鬥", []) == "none"
    # 專案自訂第三句 → 沿用專案的，不換成填空範本
    (proj / ".claude" / "overview-hub.json").write_text('{"locate_template": ["a", "b", "對得上規格哪一節"]}', encoding="utf-8")
    state2 = {}
    _, txt2 = _inject(proj, state2, tp)
    assert "定位｜前例：對得上規格哪一節" in txt2


# ─── G5：分數只當參考，不暗中按分數重排、不讓一個部位佔滿 ─────────────────────

def test_candidates_keep_report_order_show_score_as_reference_and_take_parts_in_turn(proj):
    """候選照報告原順序（不按分數重排）、每列照列分數並標「參考」、來源說明不是優先順序；全專案時各部位輪流取、依部位分組列。
    舊碼：按分數重排（低分的真問題排到後面、被截掉）、不顯示分數、全專案被分數高的部位佔滿。"""
    rows = [{"path": "Game/Battle/Fix.cs", "category": "hotspot", "reason": "同一處修了三次", "score": 2, "part": "戰鬥"}]
    rows += [{"path": f"Game/UI/Big{i}.cs", "category": "size", "reason": "大但清楚", "score": 90 - i, "part": "介面"}
             for i in range(6)]
    rows.append({"path": "Game/Battle/Two.cs", "category": "coupling", "reason": "分數高但不是真問題", "score": 50, "part": "戰鬥"})
    rp = proj / ".claude" / "smells.json"
    rp.write_text(json.dumps({"rows": rows}, ensure_ascii=False), encoding="utf-8")
    cfg = wo._cfg({"overview_hub": {"smells_report": str(rp)}}, proj)
    lines, _, source = wo._smells_lines(proj, cfg, None, 4, 200)
    assert [l.split("｜")[0] for l in lines] == ["- Game/Battle/Fix.cs", "- Game/Battle/Two.cs",   # 依部位分組、各部位輪流取
                                                  "- Game/UI/Big0.cs", "- Game/UI/Big1.cs"]
    assert lines[0].endswith("｜分數 2（參考）") and "不是優先順序" in source and "分數只當參考" in source
    one, _, _ = wo._smells_lines(proj, cfg, ("戰鬥",), 1, 200)
    assert [l.split("｜")[0] for l in one] == ["- Game/Battle/Fix.cs"]                      # 單部位只取 1 筆：照報告順序，不是分數高的 Two.cs
    assert any("分數最高" in q for q in wo._CANDIDATE_QUESTIONS)                           # 根因那一問要說為什麼不是分數最高的
