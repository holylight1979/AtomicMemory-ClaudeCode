"""verify_overview_card_pointer.py — 導讀卡指標制（overview_hub.card_injection）。

第一次碰到部位只送「已知病灶一句＋卡路徑」兩行，定位要求照送；改程式部位之前要本 session Read 過卡，沒讀照定位閘的方式擋
（擋訊息附卡路徑），知識類部位沒讀只提醒、留帳；card_injection=full 回到整張注入、不要求讀卡；v6 總開關關時一律整張；
沒有卡的部位兩種送法逐字相同。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_overview_card_pointer.py
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


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("WG_TEMP_RULES", "off")                   # 假專案在 pytest tmp 下
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")


@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "proj"
    mem = root / ".claude" / "memory" / "shared"
    mem.mkdir(parents=True)
    (root / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
        "| `Game/Battle/` | 戰鬥 | `戰鬥導讀` | 有 | code |\n"
        "| `Docs/` | 文件 | `文件導讀` | 有 | knowledge |\n"
        "| `Vendor/` | 框架 | 無 | 無 | code |\n", encoding="utf-8")
    (mem / "戰鬥導讀.md").write_text(CARD, encoding="utf-8")
    (mem / "文件導讀.md").write_text("# 文件導讀\n\n## 已知病灶\n- README 跑法段常漏新子命令\n", encoding="utf-8")
    for d, files in (("Game/Battle", ("A.cs", "B.cs")), ("Docs", ("a.md",)), ("Vendor", ("v.cs",))):
        (root / d).mkdir(parents=True)
        for f in files:
            (root / d / f).write_text("x", encoding="utf-8")
    return root


def _card(proj, name="戰鬥導讀"):
    return str(proj / ".claude" / "memory" / "shared" / f"{name}.md")


def _transcript(tmp_path, *texts):
    tp = tmp_path / "t.jsonl"
    with open(tp, "a", encoding="utf-8") as f:
        for t in texts:
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}},
                               ensure_ascii=False) + "\n")
    return str(tp)


def _log(tmp_path):
    return [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]


def _rec(state, part):
    return next(v for k, v in state["overview_hub"].items() if k.endswith(f"|{part}"))


def test_pointer_first_touch_sends_defect_line_and_card_path(proj, tmp_path):
    """第一刀：第一次碰到部位只送病灶一句＋卡路徑，卡的其他段不進 context；定位要求照送。"""
    state: dict = {}
    txt = wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game/Battle/A.cs")}, str(proj), _transcript(tmp_path, "x"), {})
    assert "已知病灶：共用字典跨場次沒清，第二場數值帶前一場" in txt
    assert _card(proj) in txt and "先 Read" in txt
    assert "結算傷害" not in txt and "浮點比較" not in txt and "pytest tests/battle" not in txt
    assert "定位｜部位：戰鬥" in txt
    assert _rec(state, "戰鬥")["card_mode"] == "pointer"
    assert _log(tmp_path)[-1]["card_mode"] == "pointer" and _log(tmp_path)[-1]["chars"] == len(txt)


def test_pointer_edit_denied_until_card_read_then_passes(proj, tmp_path):
    """第二刀：讀了部位檔、交了定位三行，卡沒 Read 過照擋（訊息附卡路徑）；Read 了卡就放行，讀卡有帳。"""
    state: dict = {}
    tp = _transcript(tmp_path, "先看看。")
    f1, f2 = str(proj / "Game/Battle/A.cs"), str(proj / "Game/Battle/B.cs")
    wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    wo.on_read(state, "s", "Read", {"file_path": f2}, str(proj), tp, {})
    _transcript(tmp_path, LOCATE)
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})
    assert deny and "還沒 Read 這個部位的導讀卡" in deny and _card(proj) in deny
    assert "還沒交出定位" not in deny and "還沒讀過這個部位的檔" not in deny        # 缺的只有讀卡
    assert wo.on_read(state, "s", "Read", {"file_path": _card(proj)}, str(proj), tp, {}) is None
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)
    edits = [e for e in _log(tmp_path) if e["event"] == "edit"]
    assert [e["card_unread"] for e in edits] == [1, 0] and edits[0]["deny_reason"] == "evidence"


def test_pointer_card_read_in_same_bash_command_counts(proj, tmp_path):
    """指標行說「可跟讀部位檔同一則送」：一條 cat 同時讀部位檔與卡，改檔就不缺讀卡。"""
    state: dict = {}
    tp = _transcript(tmp_path, "x")
    f1, f2 = str(proj / "Game/Battle/A.cs"), str(proj / "Game/Battle/B.cs")
    assert wo.on_read(state, "s", "Bash", {"command": f'cat "{f1}" "{f2}" "{_card(proj)}"'}, str(proj), tp, {})
    _transcript(tmp_path, LOCATE)
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)


def test_pointer_failed_card_read_does_not_count(proj, tmp_path):
    """讀卡跟讀部位檔同一套認定：指令失敗（exit≠0）讀到的卡不算讀過，改檔照擋。"""
    state: dict = {}
    tp = _transcript(tmp_path, "x")
    f1, f2 = str(proj / "Game/Battle/A.cs"), str(proj / "Game/Battle/B.cs")
    wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    wo.on_read(state, "s", "Read", {"file_path": f2}, str(proj), tp, {})
    wo.on_read(state, "s", "Bash", {"command": f'cat "{_card(proj)}"'}, str(proj), tp, {}, exit_code=1)
    _transcript(tmp_path, LOCATE)
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})
    assert deny and "還沒 Read 這個部位的導讀卡" in deny


def test_pointer_two_cards_one_unread_still_denied(proj, tmp_path):
    """表上兩張卡只讀一張：照擋，訊息只列沒讀的那張。"""
    second = proj / ".claude" / "memory" / "shared" / "戰鬥根因層.md"
    second.write_text("# 根因層\n\n## 已知病灶\n- 結算順序跟技能表不同步\n", encoding="utf-8")
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
        "| `Game/Battle/` | 戰鬥 | `戰鬥導讀`、`戰鬥根因層` | 有 | code |\n", encoding="utf-8")
    state: dict = {}
    tp = _transcript(tmp_path, "x")
    f1, f2 = str(proj / "Game/Battle/A.cs"), str(proj / "Game/Battle/B.cs")
    wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    wo.on_read(state, "s", "Read", {"file_path": f2}, str(proj), tp, {})
    wo.on_read(state, "s", "Read", {"file_path": _card(proj)}, str(proj), tp, {})
    _transcript(tmp_path, LOCATE)
    warn, deny, _ = wo.on_edit(state, "s", f1, tp, {})
    unread_line = next(l for l in deny.splitlines() if "還沒 Read 這個部位的導讀卡" in l)
    assert str(second) in unread_line and _card(proj) not in unread_line
    wo.on_read(state, "s", "Read", {"file_path": str(second)}, str(proj), tp, {})
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)


def test_pointer_knowledge_part_unread_card_warns_not_blocks(proj, tmp_path):
    """知識類部位照舊只要「卡已注入」就放行：指標制卡沒 Read 過只附一行提醒（附卡路徑）、帳上記 card_unread，不擋；
    讀了之後不再提醒。"""
    state: dict = {}
    tp = _transcript(tmp_path, "x")
    f = str(proj / "Docs/a.md")
    assert "README 跑法段常漏新子命令" in wo.on_prompt(state, "s", f"看一下 {f}", tp, {})
    warn, deny, changed = wo.on_edit(state, "s", f, tp, {})
    assert deny is None and changed and warn and "還沒 Read 這個部位的導讀卡" in warn and _card(proj, "文件導讀") in warn
    assert "定位三行" not in warn
    last = _log(tmp_path)[-1]
    assert last["event"] == "edit" and last["deny_reason"] is None and last["card_unread"] == 1
    wo.on_read(state, "s", "Read", {"file_path": _card(proj, "文件導讀")}, str(proj), tp, {})
    assert wo.on_edit(state, "s", f, tp, {}) == (None, None, True)
    assert _log(tmp_path)[-1]["card_unread"] == 0


def test_pointer_edit_before_inject_tells_to_read_card(proj, tmp_path):
    """還沒碰過部位就改：照舊先注入並擋一次，擋訊息是指標兩行、叫人先 Read 卡。"""
    warn, deny, _ = wo.on_edit({}, "s", str(proj / "Game/Battle/A.cs"), _transcript(tmp_path, "x"), {})
    assert deny and "先 Read 導讀卡" in deny and _card(proj) in deny and "結算傷害" not in deny


def test_pre_tool_use_entry_denies_with_pointer_lines(proj, tmp_path, monkeypatch):
    """走真 PreToolUse 入口：第一次改部位檔被擋，擋訊息是指標兩行（病灶一句＋卡路徑），不是整張卡。"""
    import wg_core
    from handlers import pre_tool_use as ptu
    wf = tmp_path / "wf"
    wf.mkdir()
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_core, "_rebuild_min_atom_index", lambda cwd: {})
    monkeypatch.setattr(wg_core, "_find_active_sibling_state", lambda *a, **k: None)
    monkeypatch.setattr(wg_core, "_atom_debug_log", lambda *a, **k: None)
    outputs = []

    def _out(d=None):
        outputs.append(d)
        raise SystemExit(0)
    monkeypatch.setattr(ptu, "output_json", _out)
    monkeypatch.setattr(ptu, "output_nothing", _out)
    f1 = str(proj / "Game/Battle/A.cs")
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": "Edit", "tool_input": {"file_path": f1, "old_string": "x", "new_string": "y"},
                                 "session_id": "sess-ptr-0001", "cwd": str(proj), "transcript_path": _transcript(tmp_path, "x")}, {})
    out = (outputs[-1] or {}).get("hookSpecificOutput", {})
    reason = out.get("permissionDecisionReason", "")
    assert out.get("permissionDecision") == "deny" and "已知病灶：共用字典跨場次沒清" in reason and _card(proj) in reason
    assert "結算傷害" not in reason


def test_full_switch_restores_whole_card_without_read_requirement(proj, tmp_path):
    """第三刀接縫：card_injection=full 走原本整張注入的程式，改檔不要求 Read 卡。"""
    (proj / ".claude" / "overview-hub.json").write_text('{"card_injection": "full"}', encoding="utf-8")
    state: dict = {}
    tp = _transcript(tmp_path, "x")
    f1, f2 = str(proj / "Game/Battle/A.cs"), str(proj / "Game/Battle/B.cs")
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    assert "結算傷害" in txt and "浮點比較" in txt and "先把下面的導讀卡讀完" in txt
    assert _rec(state, "戰鬥")["card_mode"] == "full"
    wo.on_read(state, "s", "Read", {"file_path": f2}, str(proj), tp, {})
    _transcript(tmp_path, LOCATE)
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)


def test_v6_off_keeps_whole_card(proj, tmp_path, monkeypatch):
    """總開關關時行為不變：預設 pointer 也照整張注入，改檔不要求 Read 卡。"""
    monkeypatch.setenv("WG_V6", "0")
    state: dict = {}
    tp = _transcript(tmp_path, "x")
    f1, f2 = str(proj / "Game/Battle/A.cs"), str(proj / "Game/Battle/B.cs")
    txt = wo.on_read(state, "s", "Read", {"file_path": f1}, str(proj), tp, {})
    assert "結算傷害" in txt and "已知病灶：" not in txt
    wo.on_read(state, "s", "Read", {"file_path": f2}, str(proj), tp, {})
    _transcript(tmp_path, LOCATE)
    assert wo.on_edit(state, "s", f1, tp, {}) == (None, None, True)


def test_no_card_part_identical_in_both_modes(proj, tmp_path):
    """沒有卡的部位（表上「無」）：兩種送法逐字相同，也不多一道讀卡要求。"""
    f = str(proj / "Vendor/v.cs")
    texts = {}
    for mode in ("pointer", "full"):
        (proj / ".claude" / "overview-hub.json").write_text(json.dumps({"card_injection": mode}), encoding="utf-8")
        state: dict = {}
        texts[mode] = wo.on_read(state, "s", "Read", {"file_path": f}, str(proj), _transcript(tmp_path, "x"), {})
        assert _rec(state, "框架")["card_paths"] == []
    assert texts["pointer"] == texts["full"] and "沒有可注入的導讀卡" in texts["pointer"]


def test_goal_view_resend_is_pointer_too(proj, tmp_path, monkeypatch):
    """目標改了之後重送導讀卡（目標視角那次）也照指標制，不整張重送。"""
    import wg_need_goal_points as ngp
    monkeypatch.setattr(ngp, "goal_view_text", lambda *a, **k: "[NeedGoal] 目標視角：測試")
    state: dict = {}
    tp = _transcript(tmp_path, "x")
    f = str(proj / "Game/Battle/A.cs")
    wo.on_read(state, "s", "Read", {"file_path": f}, str(proj), tp, {})
    _rec(state, "戰鬥")["goal_reset_turn"] = 4
    view = wo.on_read(state, "s", "Read", {"file_path": f}, str(proj), tp, {})
    assert view and "目標視角：測試" in view and "已知病灶：共用字典" in view and "結算傷害" not in view


def test_card_injection_value_validated(proj, tmp_path):
    """開關只收 pointer／full，寫錯值是設定錯誤（改檔一律擋，訊息點名這個鍵）。"""
    (proj / ".claude" / "overview-hub.json").write_text('{"card_injection": "half"}', encoding="utf-8")
    warn, deny, _ = wo.on_edit({}, "s", str(proj / "Game/Battle/A.cs"), _transcript(tmp_path, "x"), {})
    assert deny and "card_injection 必須是 pointer／full 之一" in deny


def test_pointer_body_clips_defect_and_lists_every_card(tmp_path):
    """病灶一句截在上限；多張卡都列路徑，病灶取第一張有病灶段的卡。"""
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("# a\n\n## 做什麼\n- x\n", encoding="utf-8")
    b.write_text("# b\n\n## 已知病灶\n- " + "長" * 300 + "\n", encoding="utf-8")
    row = {"part": "戰鬥", "part_short": "戰鬥", "status": "有", "cards": ["a", "b"], "line": ""}
    txt, used = oh.build_injection_ex(row, [a, b], "C:/x/A.cs", 6000, pointer=True)
    line = next(l for l in txt.splitlines() if l.startswith("已知病灶："))
    assert used == [] and len(line) == len("已知病灶：") + oh.POINTER_DEFECT_CAP + 1 and str(a) in txt and str(b) in txt
