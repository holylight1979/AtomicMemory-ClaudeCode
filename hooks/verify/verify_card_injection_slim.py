"""verify_card_injection_slim.py — 導讀卡注入瘦身（改造包 E）。

三件事：
1. 唯讀碰到部位（Read／唯讀 Bash／Grep）不送卡（規則 READ_TOUCH_NO_CARD）：只建紀錄、讀檔結果最多多 LOCATE_HINT_ON_FIRST_READ 一行；
   卡（含候選、追蹤項）等第一次改這個部位的檔（on_edit）才送、一個部位一次。
2. v6 總開關關時也用 card_injection 的值（預設 pointer），不再退回整張。
3. 卡尾的未結追蹤項只留「未結追蹤項 N 筆：帳本路徑」一行（規則 TRACKING_COUNT_LINE_ONLY），不列內容。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_card_injection_slim.py
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

import wg_harvest as wh  # noqa: E402
import wg_overview as wo  # noqa: E402

CARD = """# 戰鬥導讀

## 做什麼與上下游
- 結算傷害，上游技能表、下游戰報

## 已知病灶
- 共用字典跨場次沒清，第二場數值帶前一場
- 浮點比較直接用 ==

## 驗法
- pytest tests/battle
"""
LOCATE = "定位｜部位：戰鬥——A.cs\n定位｜根因層：根因在邏輯層，第二個不存在因為只有一層\n定位｜前例：無"
CARD_WORDS = ("結算傷害", "浮點比較", "pytest tests/battle", "已知病灶：", "導讀卡")   # 卡的任何一段出現就算送了卡


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("WG_TEMP_RULES", "off")                   # 假專案在 pytest tmp 下
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wh, "WORKFLOW_DIR", tmp_path / "workflow")   # 追蹤帳本落 tmp，不碰 live


@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "proj"
    mem = root / ".claude" / "memory" / "shared"
    mem.mkdir(parents=True)
    (root / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
        "| `Game/Battle/` | 戰鬥 | `戰鬥導讀` | 有 | code |\n", encoding="utf-8")
    (mem / "戰鬥導讀.md").write_text(CARD, encoding="utf-8")
    (root / "Game" / "Battle").mkdir(parents=True)
    for f in ("A.cs", "B.cs"):
        (root / "Game" / "Battle" / f).write_text("foo = 1", encoding="utf-8")
    return root


def _card(proj):
    return str(proj / ".claude" / "memory" / "shared" / "戰鬥導讀.md")


def _transcript(tmp_path, *texts):
    tp = tmp_path / "t.jsonl"
    with open(tp, "a", encoding="utf-8") as f:
        for t in texts:
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}},
                               ensure_ascii=False) + "\n")
    return str(tp)


def _log(tmp_path):
    return [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]


def _rec(state):
    return next(v for k, v in state["overview_hub"].items() if k.endswith("|戰鬥"))


def _assert_one_hint_line_only(txt):
    """讀檔結果多出來的只有 LOCATE_HINT_ON_FIRST_READ 那一行：沒有卡、沒有候選、沒有追蹤項。"""
    assert txt and "\n" not in txt and txt.startswith("[Guardian:OverviewHub] 改【戰鬥】的程式檔前"), txt
    for w in CARD_WORDS + ("候選", "根因卡", "先答", "未結追蹤項", "定位｜部位：戰鬥——"):
        assert w not in txt, w


def test_readonly_bash_first_touch_sends_one_line_no_card(proj, tmp_path):
    """唯讀 Bash（grep -n／sed -n／head／cat）第一次碰到部位：只多一行定位提示；部位紀錄建了、標 card_pending；
    inject 事件 chars＝0。同部位之後的唯讀指令什麼都不送、讀檔照記。"""
    tp = _transcript(tmp_path, "先看看。")
    f1, f2 = (proj / "Game/Battle/A.cs").as_posix(), (proj / "Game/Battle/B.cs").as_posix()
    state: dict = {}
    txt = wo.on_read(state, "s", "Bash", {"command": f"grep -n foo {f1}"}, str(proj), tp, {})
    _assert_one_hint_line_only(txt)
    rec = _rec(state)
    assert rec["card_pending"] is True and rec["card_mode"] == "pointer" and rec["part_files_read"] == [f1]
    inj = next(e for e in _log(tmp_path) if e["event"] == "inject")
    assert inj["chars"] == 0 and inj["card_pending"] is True and inj["via"] == "bash"
    for cmd in (f"sed -n 1,5p {f2}", f"head -3 {f1}", f"cat {f1} {f2}"):
        assert wo.on_read(state, "s", "Bash", {"command": cmd}, str(proj), tp, {}) is None, cmd
    assert rec["part_files_read"] == [f1, f2]


def test_read_tool_first_touch_sends_one_line_no_card(proj, tmp_path):
    """Read 工具第一次碰到部位：同樣只一行；對照改前（卡隨讀檔結果到）：那一行不到 300 字，卡（pointer 兩行＋定位要求）要 500 字以上。"""
    tp = _transcript(tmp_path, "先看看。")
    f1 = str(proj / "Game/Battle/A.cs")
    state: dict = {}
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    _assert_one_hint_line_only(txt)
    assert len(txt) < 300
    assert wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {}) is None      # 第二次讀：什麼都不送
    card = wo.on_edit(state, "s", f1, tp, {})[1]
    assert card and len(card) > 500 and _card(proj) in card
    print(f"\nSLIM_SIZE read_line={len(txt)} first_edit_card={len(card)}")


def test_first_edit_sends_card_once(proj, tmp_path):
    """卡在第一次改這個部位的檔時送（on_edit 回的訊息帶卡）、只送一次：第二次改不再帶卡；讀檔時讀過的部位檔與交過的定位行照算
    （pointer 送法：第二次只缺 Read 卡，Read 了就放行）。log：inject（讀檔、chars 0）→ card（改檔、有字數）→ edit。"""
    tp = _transcript(tmp_path, "先看看。")
    f1, f2 = str(proj / "Game/Battle/A.cs"), str(proj / "Game/Battle/B.cs")
    state: dict = {}
    wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    wo.on_read(state, "s", "Read", {"file_path": f2}, str(proj), tp, {})
    _transcript(tmp_path, LOCATE)
    warn, deny, changed, hit = wo.edit_check(state, "s", f1, tp, {})            # 定位已交 → 不擋；卡當提醒件（extra）隨這次改檔結果到
    assert deny is None and warn is None and changed and hit["rule"] == "OVERVIEW_CARD_BEFORE_EDIT"
    assert "第一次改【戰鬥】部位的檔；讀檔時只送了一行，導讀卡現在才送" in hit["what"] and "讀過的部位檔與交過的定位行照算" in hit["fix"]
    card = hit["extra"]
    assert "已知病灶：共用字典跨場次沒清" in card and _card(proj) in card and "定位｜部位：戰鬥——" in card
    assert "結算傷害" not in card                                                   # pointer：卡其他段不送
    assert _rec(state)["card_pending"] is False
    warn, deny2, _ = wo.on_edit(state, "s", f1, tp, {})
    assert deny2 and "還沒 Read 這個部位的導讀卡" in deny2 and "導讀卡現在才送" not in deny2 and "已知病灶：" not in deny2
    assert "還沒交出定位" not in deny2 and "還沒讀過這個部位的檔" not in deny2      # 讀檔時的證據照算
    wo.on_read(state, "s", "Read", {"file_path": _card(proj)}, str(proj), tp, {})
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)
    events = [e["event"] for e in _log(tmp_path)]
    assert events == ["inject", "locate_hint", "card", "edit_card_delivered", "edit_first_located", "edit", "edit"]
    card_ev = next(e for e in _log(tmp_path) if e["event"] == "card")
    assert card_ev["chars"] > 0 and card_ev["card_mode"] == "pointer" and card_ev["via"] == "edit"


def test_first_edit_full_mode_sends_whole_card_then_passes(proj, tmp_path):
    """full 送法：第一次改檔那則帶整張卡，證據齊了第二次就放行（不要求 Read 卡）。"""
    (proj / ".claude" / "overview-hub.json").write_text('{"card_injection": "full"}', encoding="utf-8")
    tp = _transcript(tmp_path, "先看看。")
    f1, f2 = str(proj / "Game/Battle/A.cs"), str(proj / "Game/Battle/B.cs")
    state: dict = {}
    _assert_one_hint_line_only(wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {}))
    wo.on_read(state, "s", "Read", {"file_path": f2}, str(proj), tp, {})
    _transcript(tmp_path, LOCATE)
    _, deny, _, hit = wo.edit_check(state, "s", f1, tp, {})                      # 定位已交 → 不擋；整張卡在提醒件裡
    card = hit["extra"]
    assert deny is None and "結算傷害" in card and "浮點比較" in card and "pytest tests/battle" in card and "先讀完再改" in hit["fix"]
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)


def test_v6_off_uses_pointer_mode_not_full(proj, tmp_path, monkeypatch):
    """v6 總開關關（規則 OVERVIEW_HUB_UNDER_V6）：OverviewHub 整道不動——讀檔零增量、不建紀錄，改檔不送卡也不擋；
    _card_mode 仍照 card_injection 算（出廠 pointer，專案明寫 full 才 full），只是沒有人用它。"""
    monkeypatch.setenv("WG_V6", "0")
    assert wo._cfg({})["_card_mode"] == "pointer" and wo._cfg({}, proj)["_card_mode"] == "pointer"
    assert wo._cfg({}, proj)["enabled"] is False
    tp = _transcript(tmp_path, "x")
    f1 = str(proj / "Game/Battle/A.cs")
    state: dict = {}
    assert wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {}) is None    # 關態：定位提示也不送，讀檔結果零增量
    assert "overview_hub" not in state                                                      # 連紀錄都不建
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, False)                       # 不送卡、不擋
    assert not (tmp_path / "hub.log").exists()
    (proj / ".claude" / "overview-hub.json").write_text('{"card_injection": "full"}', encoding="utf-8")
    assert wo._cfg({}, proj)["_card_mode"] == "full" and wo._cfg({}, proj)["enabled"] is False
    assert wo.on_edit({}, "s", f1, tp, {}) == (None, None, False)


def test_tracking_items_not_appended_only_count_line(proj, tmp_path):
    """卡尾的未結追蹤項：只一行「未結追蹤項 N 筆」＋帳本路徑＋結案寫法，不列項目內容、沒有「另有 N 筆」；讀檔那則連這一行也沒有。"""
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, wh.tracking_entries("s1", 1, "\n".join(f"[戰鬥] 第{i}項追蹤" + "長" * 100 for i in range(7)),
                                                 at="2026-10-01T00:00:00"))
    tp = _transcript(tmp_path, "x")
    f1 = str(proj / "Game/Battle/A.cs")
    state: dict = {}
    _assert_one_hint_line_only(wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {}))
    deny = wo.on_edit(state, "s", f1, tp, {})[1]
    line = next(l for l in deny.splitlines() if l.startswith("未結追蹤項"))
    assert line.startswith("未結追蹤項 7 筆") and str(wh.tracking_path(slug)) in line and "[戰鬥] 結案：" in line
    assert "【未結追蹤項】" not in deny and "第0項追蹤" not in deny and "另有" not in deny and "長長長" not in deny
    assert deny.count("未結追蹤項") == 1
    # 沒有追蹤項的部位連這一行都沒有
    (tmp_path / "workflow" / "tracking" / f"{slug}.jsonl").unlink()
    assert "未結追蹤項" not in wo.on_edit({}, "s", f1, tp, {})[1]


def test_candidates_block_not_sent_on_read(proj, tmp_path):
    """讀檔結果不帶候選（候選前 N／根因卡／先答兩問）：debug 意圖、卡有病灶段，讀到部位檔還是只有那一行；候選只在觸發詞與第 2 次 Edit。"""
    tp = _transcript(tmp_path, "先看看。")
    f1 = str(proj / "Game/Battle/A.cs")
    state: dict = {"turn_intent": "debug", "turn_seq": 2}
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    _assert_one_hint_line_only(txt)
    assert "候選前" not in txt and "根因卡" not in txt and "先問" not in txt and "視角" not in txt and "分數" not in txt
    assert not state.get("candidates_sent")
    assert _rec(state)["slices"] == []                                            # 片在送卡那刻才選


if __name__ == "__main__":
    import subprocess
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("CARD_INJECTION_SLIM_CHECK PASS" if rc == 0 else "CARD_INJECTION_SLIM_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
