"""verify_ask_gate.py — 提問閘（hooks/wg_ask_gate.py 與 PreToolUse／PostToolBatch 的呼叫點）。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_ask_gate.py

守住：
  ASK_NEEDS_RECOMMENDATION：每一題要附推薦，沒有就擋（v6 開照 GATE_MODE_TABLE 改提醒），擋訊息列缺的題目與照抄可過的寫法；
      【收尾放行確認】固定兩選項的放行題豁免，真有待放行紀錄時只豁免放行題本身。
  ASK_OVERVIEW_BEFORE_DECISION：問改法而題目點名的部位（或任一部位）還沒讀過檔，擋訊息或提示多一句，不單獨擋。
  PreToolUse 處理過的提問 PostToolBatch 不再處理；沒處理過的事後提醒（不擋），每次提問記一筆審計（擋過幾次）。
  閘自己壞了：v6 開改提醒、v6 關照擋；只放過真有待放行紀錄的純放行題。
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

import wg_ask_gate as ag  # noqa: E402
import wg_core  # noqa: E402
import wg_overview as wo  # noqa: E402
import wg_release  # noqa: E402
from handlers import post_tool_batch as ptb  # noqa: E402
from handlers import pre_tool_use as ptu  # noqa: E402

SID = "sid-ask-0001"
READ = {"overview_hub": {"c:/p|部位": {"part_files_read": ["c:/p/a.py"]}}}       # 讀過部位檔（不附全貌提醒）
ASK = {"questions": [{"question": "要用哪個做法？", "header": "做法", "multiSelect": False,
                      "options": [{"label": "A (Recommended)", "description": "甲"}, {"label": "B", "description": "乙"}]}]}


def coding(turn):
    """本使用者回合已改過程式檔（coding_turn 第①層）：PostToolBatch 的事後提醒只在寫碼回合跑（規則 CODING_TURN_ONLY）。"""
    return {"modified_files": [{"path": "c:/p/a.py", "last_turn_seq": turn}]}


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    """資料根與守門紀錄都進 tmp。假專案建在 pytest tmp 下，關掉 TEMP_COPY_NOT_PROJECT（暫存目錄下的檔不算專案檔）。"""
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path / "workflow")
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path / "Logs")
    (tmp_path / "workflow").mkdir()
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    return tmp_path


def guard(tmp_path):
    p = tmp_path / "Logs" / "guard-ask.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def run_handler(fn, *args):
    """hook 入口會 sys.exit；抓 stdout 的 JSON（沒輸出回 None）。"""
    import io
    buf, old = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        fn(*args)
    except SystemExit:
        pass
    finally:
        sys.stdout = old
    out = buf.getvalue().strip()
    return json.loads(out) if out else None


def ask_opts(question, labels):
    return {"questions": [{"question": question, "header": "選擇", "multiSelect": False,
                           "options": [{"label": l, "description": f"{l} 的說明"} for l in labels]}]}


def _release_q():
    """真的放行題：題目含標記、選項正好是 wg_release 固定的兩個（豁免看結構，不只看標記）。"""
    return {"questions": [{"question": f"{wg_release.RELEASE_TAG} 要放行這一回合嗎？", "header": "放行", "multiSelect": False,
                           "options": [{"label": wg_release.OPT_RELEASE, "description": "放"},
                                       {"label": wg_release.OPT_KEEP, "description": "擋"}]}]}


def _pending_state():
    state = {"turn_seq": 2, **READ}
    wg_release.mark_block(state, SID, "reconcile", None, 2)
    wg_release.set_pending(state, SID, "reconcile", 2, "now", "擋滿")
    return state


def _pre_input(tool_input, tid="tu1", tool="AskUserQuestion"):
    return {"session_id": SID, "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
            "tool_use_id": tid, "cwd": str(HOOKS_DIR.parent)}


def _pending_rules():
    return [h["rule"] for h in wg_core.read_state(SID).get("remind_pending") or []]


def _broken_gate(monkeypatch):
    """提問前檢查壞掉：wg_ask_gate 載不進來（import 時丟 ImportError）。"""
    monkeypatch.setitem(sys.modules, "wg_ask_gate", None)


# ─── 判定 ─────────────────────────────────────────────────────────────────

def test_release_pending_any_needs_same_gate_block_and_pending():
    """wg_release.pending_any：同一個閘 last_block 與 pending_release 都在才算（on_ask 與壞掉時的放行題共用這一支）。"""
    s = {}
    wg_release.mark_block(s, SID, "reconcile", None, 1)
    assert wg_release.pending_any(s, SID) is False                              # 只擋過、沒擋滿
    s2 = {}
    wg_release.set_pending(s2, SID, "reconcile", 1, "now", "擋滿")
    assert wg_release.pending_any(s2, SID) is False                             # 只有待放行、沒有擋的位置
    wg_release.mark_block(s2, SID, "shared", None, 1)
    assert wg_release.pending_any(s2, SID) is False                             # 不同閘不算
    wg_release.mark_block(s2, SID, "reconcile", None, 1)
    assert wg_release.pending_any(s2, SID) is True and wg_release.pending_any(s2, "別的 session") is False


def test_ask_without_recommendation_blocked_then_recommended_passes(world):
    """沒推薦 → 擋，訊息有規則名、缺哪一題、照抄可過的寫法；照抄加 (Recommended) 或「建議：」就放行。"""
    deny, hint = ag.on_ask(SID, "AskUserQuestion", ask_opts("卡在這：要用哪個？", ["A", "B"]), {"turn_seq": 3, **READ})
    assert deny and "ASK_NEEDS_RECOMMENDATION" in deny and "第 1 題" in deny and hint is None
    assert '"label": "A (Recommended)"' in deny and "建議：選 A" in deny
    assert [g for g in guard(world) if g["event"] == "ask_no_recommendation"]
    ok = ask_opts("卡在這：要用哪個？", ["A (Recommended)", "B"])
    assert ag.on_ask(SID, "AskUserQuestion", ok, {"turn_seq": 3, **READ}) == (None, None)
    ok2 = ask_opts("卡在這：要用哪個？建議：選 B，因為只動一個檔。", ["A", "B"])
    assert ag.on_ask(SID, "AskUserQuestion", ok2, {"turn_seq": 3, **READ}) == (None, None)


def test_release_question_exempt_from_recommendation(world):
    """【收尾放行確認】固定兩選項的放行題不是決策題：不要求推薦；真有待放行紀錄時整題豁免。"""
    q = ask_opts(f"{wg_release.RELEASE_TAG} 要放行這一回合嗎？", [wg_release.OPT_RELEASE, wg_release.OPT_KEEP])
    assert ag.on_ask(SID, "AskUserQuestion", q, {"turn_seq": 2, **READ}) == (None, None)
    state = {"turn_seq": 2, **READ}
    wg_release.mark_block(state, SID, "reconcile", None, 2)
    wg_release.set_pending(state, SID, "reconcile", 2, "now", "擋滿")
    assert ag.on_ask(SID, "AskUserQuestion", q, state) == (None, None)


def test_release_exemption_does_not_cover_other_questions(world):
    """真有待放行紀錄時，放行題豁免只管放行題本身；同批的一般題照查推薦，標記塞進一般題也不豁免。"""
    mixed = _release_q()
    mixed["questions"].append({"question": "要哪種格式？", "header": "h", "multiSelect": False,
                               "options": [{"label": "CSV", "description": "x"}, {"label": "JSON", "description": "y"}]})
    deny, _ = ag.on_ask(SID, "AskUserQuestion", mixed, _pending_state())
    assert deny and "ASK_NEEDS_RECOMMENDATION" in deny and "第 2 題" in deny and "第 1 題「" not in deny
    smuggled = ask_opts(f"{wg_release.RELEASE_TAG} 要哪種格式？", ["CSV", "JSON"])
    deny, _ = ag.on_ask(SID, "AskUserQuestion", smuggled, _pending_state())
    assert deny and "ASK_NEEDS_RECOMMENDATION" in deny
    assert ag.on_ask(SID, "AskUserQuestion", _release_q(), _pending_state()) == (None, None)


def test_overview_reminder_rides_on_message_not_own_block(world):
    """問改法而本 session 還沒讀過任何部位檔：擋訊息或提示多一句「先讀過部位檔再問」；只提醒，不單獨擋。"""
    q = ask_opts("要用哪個改法？", ["A (Recommended)", "B"])
    deny, hint = ag.on_ask(SID, "AskUserQuestion", q, {"turn_seq": 2})
    assert deny is None and hint and "先讀過部位檔再問" in hint and "ASK_OVERVIEW_BEFORE_DECISION" in hint
    assert ag.on_ask(SID, "AskUserQuestion", q, {"turn_seq": 2, **READ}) == (None, None)
    deny, hint = ag.on_ask(SID, "AskUserQuestion", ask_opts("要用哪個改法？", ["A"]), {"turn_seq": 2})
    assert deny and "ASK_NEEDS_RECOMMENDATION" in deny and "先讀過部位檔再問" in deny and hint is None
    deny, hint = ag.on_ask(SID, "AskUserQuestion", ask_opts("今天先做哪一軌？", ["A (Recommended)"]), {"turn_seq": 2})
    assert (deny, hint) == (None, None)                                          # 不是改法選擇


# ─── 題目點名的部位（ASK_OVERVIEW_BEFORE_DECISION） ───────────────────────────

@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "proj"
    (root / ".claude" / "memory" / "shared" / "戰鬥").mkdir(parents=True)
    (root / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
        "| `Game/Battle/` | 戰鬥 | `戰鬥知識導讀-hub索引` | 有 |\n"
        "| `Game/Net/` | 網路 | 無 | 無 |\n", encoding="utf-8")
    (root / ".claude" / "memory" / "shared" / "戰鬥" / "戰鬥知識導讀-hub索引.md").write_text("# 戰鬥導讀\n病灶：共用字典", encoding="utf-8")
    for d in ("Game/Battle", "Game/Net", "Tools", "Docs"):
        (root / d).mkdir(parents=True, exist_ok=True)
    return root


def _hub(proj, **reads):
    """state 的 OverviewHub 紀錄：部位資料夾 → 讀過的檔數（鍵照 wg_overview.read_scope_keys 算，跟真的讀檔紀錄同一套）。"""
    hub = {}
    for d, n in reads.items():
        key = wo.read_scope_keys(str(proj / "Game" / d / "x.py"), {})[1]
        hub[key] = {"part_files_read": [str(proj / "Game" / d / f"f{i}.py") for i in range(n)]}
    return {"overview_hub": hub, "session": {"id": SID, "cwd": str(proj)}, "turn_seq": 2}


def test_named_part_unread_reminds_even_if_other_part_read(world, proj):
    """讀了 A 部位（戰鬥）的檔、題目問 B 部位（網路）某檔的改法 → 提醒，證據點名 B 讀過 0 檔。"""
    q = ask_opts(f"{proj / 'Game' / 'Net' / 'conn.py'} 要用哪個改法？", ["A (Recommended)", "B"])
    deny, hint = ag.on_ask(SID, "AskUserQuestion", q, _hub(proj, Battle=2))
    assert deny is None and hint and "先讀過部位檔再問" in hint
    assert "→部位 網路，本回合該部位讀過 0 檔" in hint
    rel = ask_opts("Game/Net/conn.py 要用哪個改法？", ["A (Recommended)", "B"])       # 相對路徑照 session cwd 解
    assert "→部位 網路，本回合該部位讀過 0 檔" in (ag.on_ask(SID, "AskUserQuestion", rel, _hub(proj, Battle=2))[1] or "")


def test_named_part_read_no_reminder(world, proj):
    """讀了 B 部位的檔、問 B 部位改法 → 不提醒（讀的是別的部位才算沒看全貌）。"""
    q = ask_opts(f"{proj / 'Game' / 'Net' / 'conn.py'} 要用哪個改法？", ["A (Recommended)", "B"])
    assert ag.on_ask(SID, "AskUserQuestion", q, _hub(proj, Net=1)) == (None, None)


def test_no_path_falls_back_to_any_part_read(world, proj):
    """題目沒提路徑 → 讀過任一部位檔不提醒；一檔都沒讀 → 提醒，證據寫「題目沒提到部位表上的路徑」。"""
    q = ask_opts("要用哪個改法？", ["A (Recommended)", "B"])
    assert ag.on_ask(SID, "AskUserQuestion", q, _hub(proj, Battle=1)) == (None, None)
    deny, hint = ag.on_ask(SID, "AskUserQuestion", q, _hub(proj))
    assert deny is None and "題目沒提到部位表上的路徑" in (hint or "")


def test_unmapped_path_falls_back(world, proj):
    """題目提的路徑不在部位表（Tools/ 沒列）→ 退回總數判定。"""
    q = ask_opts(f"{proj / 'Tools' / 'gen.py'} 要用哪個改法？", ["A (Recommended)", "B"])
    assert ag.on_ask(SID, "AskUserQuestion", q, _hub(proj, Battle=1)) == (None, None)
    deny, hint = ag.on_ask(SID, "AskUserQuestion", q, _hub(proj))
    assert deny is None and "題目沒提到部位表上的路徑" in (hint or "")


def test_cjk_part_and_root_file_and_cwd_fallback(world, tmp_path, monkeypatch):
    """中文資料夾的部位、根目錄檔名的部位都對得到；state 沒記 session cwd 時，相對路徑照 hook 行程的 cwd 解。"""
    root = tmp_path / "cjk"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
        "| `Game/網路/` | 網路 | 無 | 無 |\n| `Game/戰鬥/` | 戰鬥 | 無 | 無 |\n| `./TECH.md` | 技術文件 | 無 | 無 |\n",   # 表上根目錄檔要含斜線
        encoding="utf-8")
    key = wo.read_scope_keys(str(root / "Game" / "戰鬥" / "a.py"), {})[1]
    state = {"overview_hub": {key: {"part_files_read": [str(root / "Game" / "戰鬥" / "a.py")]}}, "turn_seq": 2}
    monkeypatch.chdir(root)
    for q, part in (("要改Game/網路/conn.py嗎，用哪個改法？", "網路"), ("TECH.md 要用哪個改法？", "技術文件")):
        deny, hint = ag.on_ask(SID, "AskUserQuestion", ask_opts(q, ["A (Recommended)", "B"]), state)
        assert deny is None and f"→部位 {part}，本回合該部位讀過 0 檔" in (hint or ""), (q, hint)


def test_part_lookup_error_falls_back_not_blocks(world, proj, monkeypatch, capsys):
    """部位對映丟例外：這條只是提醒，不能讓整個提問被打斷（PreToolUse 外層會一律擋）；stderr 說一聲、退回總數判定。"""
    state = _hub(proj, Battle=1)

    def boom(*a, **k):
        raise OSError("網路磁碟斷線")
    monkeypatch.setattr(wo, "read_scope_keys", boom)
    q = ask_opts(f"{proj / 'Game' / 'Net' / 'conn.py'} 要用哪個改法？", ["A (Recommended)", "B"])
    assert ag.on_ask(SID, "AskUserQuestion", q, state) == (None, None)
    assert "網路磁碟斷線" in capsys.readouterr().err


# ─── 事後模式與審計（PostToolBatch） ──────────────────────────────────────

def test_asks_after_skips_handled_and_hints_unhandled(world):
    state = {"turn_seq": 6, **READ}
    nr = ask_opts("另一題", ["A", "B"])
    ag.mark_asked(state, "tu1", nr)
    calls = [{"tool_name": "AskUserQuestion", "tool_input": nr, "tool_use_id": "tu1"}]
    assert ag.batch_lines(SID, state, calls) == []                              # PreToolUse 處理過
    calls2 = [{"tool_name": "AskUserQuestion", "tool_input": ask_opts("再一題", ["A", "B"]), "tool_use_id": "tu2"}]
    lines = ag.batch_lines(SID, state, calls2)
    assert len(lines) == 1 and "ASK_NEEDS_RECOMMENDATION" in lines[0]          # 沒攔到 → 事後提醒、不擋
    assert [g for g in guard(world) if g["event"] == "ask_no_recommendation"][-1]["mode"] == "after"
    assert ag.batch_lines(SID, state, calls2) == []                             # 同一題不重複提醒


def test_after_mode_hints_missing_recommendation(world):
    """PreToolUse 沒攔到的提問（事後模式）：沒推薦只提醒、不擋。"""
    state = {"turn_seq": 6, **READ}
    q = ask_opts("要用哪個？", ["A", "B"])
    lines = ag.batch_lines(SID, state, [{"tool_name": "AskUserQuestion", "tool_input": q, "tool_use_id": "z1"}])
    assert len(lines) == 1 and "ASK_NEEDS_RECOMMENDATION" in lines[0]


def test_block_count_resets_when_ask_passes(world):
    """沒推薦被擋一次，補上推薦那題過了：審計記擋過 1 次、計數歸零（否則一直累加到下一題）。"""
    state = {"turn_seq": 2, **READ}
    bad = ask_opts("要先查哪一份？", ["A", "B"])
    deny, _ = ag.on_ask(SID, "AskUserQuestion", bad, state)
    ag.note_ask_blocked(state, deny)
    ok = ask_opts("要先查哪一份？", ["A (Recommended)", "B"])
    ag.mark_asked(state, "c1", ok)
    ag.batch_lines(SID, state, [{"tool_name": "AskUserQuestion", "tool_input": ok, "tool_use_id": "c1"}])
    assert [g["blocked"] for g in guard(world) if g["event"] == "ask_audit"] == [1]
    assert state.get("ask_blocks", 0) == 0


# ─── hook 入口：PreToolUse／PostToolBatch ────────────────────────────────

def test_pre_tool_use_handler_reminds_then_passes_and_marks(world):
    """沒推薦的提問不擋（規則 GATE_MODE_TABLE）：記一件待提醒 ASK_NEEDS_RECOMMENDATION、PreToolUse 不送東西；附了推薦照放。"""
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 3, **READ})
    out = run_handler(ptu.handle_pre_tool_use, _pre_input(ask_opts("要用哪個？", ["A", "B"]), "tu1"), {})
    assert out is None and "ASK_NEEDS_RECOMMENDATION" in _pending_rules()
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(ASK, "tu2"), {}) is None
    assert {"tu1", "tu2"} <= set(wg_core.read_state(SID)["ask_handled"])


def test_ask_block_count_flows_from_pre_tool_use_to_batch_audit(world):
    """真 hook 入口串起來：PreToolUse 判該擋（改提醒、不 deny）一次 state 計數 1；補上推薦那題在 PostToolBatch 審計記「擋過 1 次」並歸零。"""
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 3, **coding(3), **READ})
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(ask_opts("要用哪個？", ["A", "B"]), "tu1"), {}) is None
    assert wg_core.read_state(SID).get("ask_blocks") == 1
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(ASK, "tu2"), {}) is None
    inp = {"session_id": SID, "hook_event_name": "PostToolBatch",
           "tool_calls": [{"tool_name": "AskUserQuestion", "tool_input": ASK, "tool_use_id": "tu2"}]}
    run_handler(ptb.handle_post_tool_batch, inp, {})
    assert [g["blocked"] for g in guard(world) if g["event"] == "ask_audit"] == [1]
    assert wg_core.read_state(SID).get("ask_blocks") == 0


def test_pre_tool_use_handler_reminds_and_subagent_skip(world):
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 1})
    bad = ask_opts("要先查哪一份？", ["A", "B"])
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(bad), {}) is None       # 不擋：記待提醒
    assert "ASK_NEEDS_RECOMMENDATION" in _pending_rules()
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 1})
    assert run_handler(ptu.handle_pre_tool_use, {**_pre_input(bad), "agent_id": "a1"}, {}) is None   # 子代理不查
    assert not _pending_rules()


def test_pre_tool_use_entry_reminds_missing_recommendation_blocks_when_v6_off(world, monkeypatch):
    """真 hook 入口：沒推薦 → v6 開記待提醒不 deny（規則 GATE_MODE_TABLE）、v6 關照 deny（規則名在擋訊息裡）；加了 (Recommended) → 放行。"""
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 3, **READ})
    bad = ask_opts("要用哪個？", ["A", "B"])
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(bad, "r1"), {}) is None
    assert _pending_rules() == ["ASK_NEEDS_RECOMMENDATION"]
    monkeypatch.setenv("WG_V6", "0")
    out = run_handler(ptu.handle_pre_tool_use, _pre_input(bad, "r0"), {})
    assert out and out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "ASK_NEEDS_RECOMMENDATION" in out["hookSpecificOutput"]["permissionDecisionReason"]
    monkeypatch.setenv("WG_V6", "1")
    ok = ask_opts("要用哪個？", ["A (Recommended)", "B"])
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(ok, "r2"), {}) is None


def test_pre_tool_use_broken_gate_reminds_normal_question(world, monkeypatch, capsys):
    """提問前檢查自己壞了（規則 GATE_SELF_ERROR，v6 開）→ 不擋：stderr 照實說照問＋守門紀錄 ask_error、記一件待提醒；
    v6 關照契約擋（fail-closed），stderr 說擋。"""
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 2})
    _broken_gate(monkeypatch)
    capsys.readouterr()
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(ASK), {}) is None
    err_on = capsys.readouterr().err
    assert "提問前檢查失敗（不擋，這題照問" in err_on and "（擋）" not in err_on, err_on
    assert [(g["event"], g["rule"]) for g in guard(world) if g["event"] == "ask_error"] == [("ask_error", "GATE_SELF_ERROR")]
    assert _pending_rules() == ["GATE_SELF_ERROR"]
    monkeypatch.setenv("WG_V6", "0")
    out = run_handler(ptu.handle_pre_tool_use, _pre_input(ASK), {})
    assert out and out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "提問前檢查壞了" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert "提問前檢查失敗（擋）" in capsys.readouterr().err


def test_pre_tool_use_broken_gate_still_lets_real_release_question_through(world, monkeypatch):
    """壞了也要放過【收尾放行確認】：本 session 真有擋滿待放行紀錄時才放，否則收尾會死鎖；光加標記照擋。"""
    q = _release_q()
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 2})
    _broken_gate(monkeypatch)
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(q), {}) is None      # 沒有待放行紀錄：當一般題，v6 開改提醒
    assert _pending_rules() == ["GATE_SELF_ERROR"]
    state = {"session": {"id": SID}, "turn_seq": 2}
    wg_release.mark_block(state, SID, "reconcile", None, 2)
    wg_release.set_pending(state, SID, "reconcile", 2, "now", "擋滿")
    wg_core.write_state(SID, state)
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(q, "tu5"), {}) is None


def test_broken_gate_lets_only_pure_release_ask_through(world, monkeypatch):
    """pre_tool_use 例外分支：閘壞了只放「整次全是放行題」且真有待放行紀錄；夾一般題照擋。"""
    st = _pending_state()
    st["session"] = {"id": SID}
    wg_core.write_state(SID, st)
    _broken_gate(monkeypatch)
    mixed = _release_q()
    mixed["questions"].append(ask_opts("要哪種格式？", ["CSV", "JSON"])["questions"][0])
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(mixed, "m1"), {}) is None   # 夾一般題：當一般題（v6 開改提醒）
    assert _pending_rules() == ["GATE_SELF_ERROR"]
    st = wg_core.read_state(SID)
    st.pop("remind_pending", None)
    wg_core.write_state(SID, st)
    assert run_handler(ptu.handle_pre_tool_use, _pre_input(_release_q(), "m2"), {}) is None
    assert not _pending_rules()                                                    # 純放行題：照放、不提醒


def test_post_tool_batch_handler_emits_after_ask(world):
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 2, **coding(2), **READ})
    inp = {"session_id": SID, "hook_event_name": "PostToolBatch",
           "tool_calls": [{"tool_name": "AskUserQuestion", "tool_input": ask_opts("要哪個？", ["A", "B"]),
                           "tool_use_id": "tu9"}]}
    out = run_handler(ptb.handle_post_tool_batch, inp, {})
    assert out, "PostToolBatch 沒送提問提醒"
    assert "ASK_NEEDS_RECOMMENDATION" in out["hookSpecificOutput"]["additionalContext"]


def test_post_tool_batch_plain_qa_turn_skips_ask_lines(world):
    """規則 CODING_TURN_ONLY：不是寫碼回合（還沒改程式），PostToolBatch 不送事後的提問提醒。"""
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 2, **READ})
    inp = {"session_id": SID, "hook_event_name": "PostToolBatch",
           "tool_calls": [{"tool_name": "AskUserQuestion", "tool_input": ask_opts("要哪個？", ["A", "B"]),
                           "tool_use_id": "tu8"}]}
    assert run_handler(ptb.handle_post_tool_batch, inp, {}) is None


def test_post_tool_batch_idle_without_anything(world):
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 2})
    inp = {"session_id": SID, "hook_event_name": "PostToolBatch", "tool_calls": [{"tool_name": "Read", "tool_input": {}}]}
    assert run_handler(ptb.handle_post_tool_batch, inp, {}) is None


def test_settings_pre_tool_use_matcher_has_ask_tools():
    data = json.loads((HOOKS_DIR.parent / "settings.json").read_text(encoding="utf-8"))
    matchers = [e.get("matcher", "") for e in data["hooks"]["PreToolUse"]
                if any("workflow-guardian.py" in h.get("command", "") for h in e.get("hooks") or [])]
    assert any({"AskUserQuestion", "ExitPlanMode"} <= set(m.split("|")) for m in matchers)


def test_hook_files_call_ask_gate():
    """hook 檔真的呼叫到提問閘：PreToolUse 的 on_ask_full、PostToolBatch 的 batch_lines。"""
    import ast

    def calls(rel, name):
        tree = ast.parse((HOOKS_DIR / rel).read_text(encoding="utf-8"))
        return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and getattr(n.func, "id", getattr(n.func, "attr", None)) == name]
    assert calls("handlers/pre_tool_use.py", "on_ask_full")
    assert calls("handlers/post_tool_batch.py", "batch_lines")
