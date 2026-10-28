"""verify_goal_tree_once.py：目標樹只立一次（改造包 J）——改程式前 need_goal set 一次保留；之後沒有任何提醒促使 AI 再呼叫
need_goal reconcile／verify_scope（實測 006：這兩步各一個模型回合＋工具定義載入，佔第一回合 72% 的 token）。

做什麼：
  改程式檔那批的提醒（handlers/post_tool_batch.closing_reminders）只剩不點名 reconcile／verify_scope 的條目；
  PostToolUse 改程式檔不再問驗證範圍（SCOPE_ASK_ONCE_PER_CODE_TURN 拿掉）；
  Stop 的 (f2)／SCOPE_* 判定照跑、只留帳（event=remind），不送 additionalContext、不擋；
  need_goal set 的回覆、沒樹改知識類檔的提示、MCP 工具說明都不寫「接著 reconcile／verify_scope」；
  v6 關：Stop 照舊擋 (f2)、批次一行都不送（行為不動）。
會紅：拿改動前的 main（4bc9243e）回放，前五案紅（舊碼提醒 SCOPE_*、GOAL_RECONCILE_AT_DELIVERY、問驗證範圍、提示寫 reconcile）；
  v6 關那案守舊行為、舊碼本來就綠。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_goal_tree_once.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wg_need_goal as ng  # noqa: E402
import wg_verify_ledger as vl  # noqa: E402
import wg_verify_scope as vs  # noqa: E402
from handlers import post_tool_batch as ptb  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
from handlers import stop as st  # noqa: E402
from verify_gate_mode_stop import CODE, DONE, OFF, SID, _batch, _mf, _reminds, drive  # noqa: E402,F401
from verify_need_goal import _op, env  # noqa: E402,F401

MCP_DIR = HOOKS_DIR.parent / "tools" / "workflow-guardian-mcp" / "lib"
PROMPT_RE = re.compile(r"need_goal\(action=(\w+)")
F2_TEXT = "[Guardian:ReconcileGate] (f2) 交付前的目標對照（T1）缺：\n  - 還沒交完整對照"
SCOPE_TEXT = "✗ (s) SCOPE_DECLARED_FOR_CHANGE：改了 x.py，還沒有驗證範圍宣告"


def _follow_up_calls(text: str) -> set:
    """文字裡點名要 AI 去叫的 need_goal 動作；只准出現 set。"""
    return set(PROMPT_RE.findall(text)) | {w for w in ("reconcile", "verify_scope") if w in text}


@pytest.fixture
def goal_on(monkeypatch):
    """改程式那批：v6 開、目標對照閘與驗證範圍閘都開、有一棵寫碼類樹、驗證範圍判成欠宣告——舊碼在這個情境會提醒 (f2) 與 SCOPE_*。"""
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "file_root_of", lambda p: r"c:\proj", raising=False)
    monkeypatch.setattr(ng, "load", lambda sid: {"trees": {"T1": {"id": "T1", "kind": "code", "status": "doing", "nodes": {}}}})
    monkeypatch.setattr(ng, "active_tree", lambda doc: (doc or {}).get("trees", {}).get("T1"))
    monkeypatch.setattr(ng, "knowledge_gate_reason", lambda *a, **k: None)
    monkeypatch.setattr(vs, "gate_reason", lambda *a, **k: (SCOPE_TEXT, None))
    monkeypatch.setattr(vs, "case_check", lambda *a, **k: None)
    return {"reconcile_gate": {"enabled": True, "goal_gate": True}, "verify_scope": {"enabled": True}}


def _code_batch(monkeypatch, capsys, config, seq=3):
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [_mf(seq=seq)]}
    calls = [{"tool_name": "Edit", "tool_input": {"file_path": CODE}}]
    return _batch(monkeypatch, capsys, state, calls, config)


def test_coding_turn_reminds_set_once_only(goal_on, monkeypatch, capsys):
    """改程式檔那批的提醒：點名的 need_goal 動作只准是 set（立樹那一次），沒有任何一行叫 AI 去 reconcile／verify_scope。"""
    ctx = _code_batch(monkeypatch, capsys, goal_on)
    assert "[Guardian:提醒]" in ctx, ctx
    assert _follow_up_calls(ctx) <= {"set"}, ctx


def test_no_reconcile_reminder_after_edit(goal_on, monkeypatch, capsys):
    """有寫碼類樹、目標對照閘開著：改程式那批不送 GOAL_RECONCILE_AT_DELIVERY／(f3)(f4)；收尾檢核那行也不寫「目標對照放 reconcile」。"""
    ctx = _code_batch(monkeypatch, capsys, goal_on)
    for rule in ("GOAL_RECONCILE_AT_DELIVERY", "EDITED_PART_NEEDS_GOAL_NODE", "KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE",
                 "KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY"):
        assert rule not in ctx, (rule, ctx)
    assert "reconcile" not in ctx and "對照" not in ctx, ctx
    assert not hasattr(ptb, "_goal_reminders") and not hasattr(ptb, "FIX_GOAL")


def test_no_verify_scope_reminder_after_edit(goal_on, monkeypatch, capsys):
    """驗證範圍閘開著、判成欠宣告：改程式那批不送 SCOPE_*；PostToolUse 改程式檔也不再問一次驗證範圍（_scope_ask_once 拿掉）。"""
    ctx = _code_batch(monkeypatch, capsys, goal_on)
    assert "SCOPE_" not in ctx and "verify_scope" not in ctx and "驗證範圍" not in ctx, ctx
    assert not hasattr(pt, "_scope_ask_once") and not hasattr(pt, "SCOPE_ASK")
    assert "verify_scope" not in ptb.FIX_CASE


def test_stop_logs_reconcile_but_sends_nothing(drive, monkeypatch):
    """Stop：(f2) 與 SCOPE_* 的判定照跑、只留帳 event=remind；不擋、不送 additionalContext 續跑（續跑一回合就是一次模型回合）。"""
    monkeypatch.setattr(ng, "goal_gate_reason", lambda *a, **k: F2_TEXT)
    monkeypatch.setattr(ng, "knowledge_gate_reason", lambda *a, **k: None)
    monkeypatch.setattr(vs, "gate_reason", lambda *a, **k: (SCOPE_TEXT, None))
    monkeypatch.setattr(vs, "case_check", lambda *a, **k: None)
    out, state, logs = drive(DONE, config={"reconcile_gate": {"enabled": True, "goal_gate": True},
                                           "verify_scope": {"enabled": True}}, modified_files=[_mf()])
    assert out == {}, out
    rules = {p["rule"] for p in _reminds(logs, "reconcile")}
    assert {"GOAL_RECONCILE_AT_DELIVERY", "SCOPE_DECLARED_FOR_CHANGE"} <= rules, rules
    assert state["stop_blocked_count"] == 0


def test_need_goal_set_reply_has_no_follow_up_call_prompt(env):
    """need_goal set 的回覆、沒樹改知識類檔的提示、第一則訊息的立樹提示、MCP 工具說明：都不寫「接著 reconcile／verify_scope」。"""
    text = _op("set", goal="讓目標樹只立一次", cwd=str(env["proj"]))["text"]
    assert text.startswith("[NeedGoal] set 收下") and _follow_up_calls(text) <= {"set", "add"}, text
    for line in (ng.KNOWLEDGE_TREE_LINE, ng.HINT_LINE, ng.CODE_TREE_HINT):
        assert _follow_up_calls(line) <= {"set", "add"}, line
    mcp = (MCP_DIR / "mcp.js").read_text(encoding="utf-8")
    assert "會問一次" not in mcp and "目標對照放 reconcile" not in mcp
    assert "reconcile" not in st.CLOSING_CHECK_FIX and "reconcile" not in ptb.FIX_CLOSING


def test_v6_off_unchanged(drive, monkeypatch, capsys):
    """總開關關：整道不動——寫碼查核閘本來就只在 v6 跑（Stop 不留 remind 帳、不擋），改程式那批一行提醒都不送；
    送法表照舊（這幾條 v6 關是 block）。"""
    monkeypatch.setenv("WG_V6", "0")
    monkeypatch.setattr(ng, "goal_gate_reason", lambda *a, **k: F2_TEXT)
    monkeypatch.setattr(ng, "knowledge_gate_reason", lambda *a, **k: None)
    out, state, logs = drive(DONE, config={"reconcile_gate": {"enabled": True, "goal_gate": True}, "verify_scope": OFF},
                             modified_files=[_mf()])
    assert "decision" not in out and not _reminds(logs, "reconcile") and state["stop_blocked_count"] == 0, out
    import wg_release_rules as rr
    for rule in ("GOAL_RECONCILE_AT_DELIVERY", "SCOPE_DECLARED_FOR_CHANGE", "CODE_EDIT_NEEDS_GOAL_TREE", "GOAL_TREE_SET_ONCE"):
        assert rr.gate_mode(rule, False) == rr.BLOCK and rr.gate_mode(rule, True) == rr.REMIND, rule
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)
    assert _code_batch(monkeypatch, capsys, {"reconcile_gate": OFF, "verify_scope": OFF}) == ""
