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

FIX = HOOKS_DIR / "verify" / "fixtures" / "v6" / "q5"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())


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

def test_trigger_with_table_sends_once_top_n_filtered_and_sorted(proj, tmp_path):
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
    assert rec["edited_files"] == {f1.replace("\\", "/"): 3} and rec["edits"] == 4
    f2 = str(proj / "Game" / "Battle" / "B.cs")
    assert wo.on_edit(state, "s", f2, tp, {}) == (None, None, True)         # 另一檔第 1 次：不附
    assert _log_events(tmp_path).count("second_edit") == 1


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
