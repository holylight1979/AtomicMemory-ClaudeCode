"""verify_ups_overview_wiring.py：UPS handler 對 OverviewHub 的接線：fail-open 真的 fail-open。

修的 bug：user_prompt_submit.py 呼叫 _atom_debug_error 但沒 import，on_prompt 一丟例外就 NameError，
整個 UPS 掛掉。正例：handler 有 _atom_debug_error 且就是 wg_core 的那個；on_prompt raise 時 handler
不拋、錯誤進 _atom_debug_error、turn_seq 照常推進。對照：on_prompt 回文字時文字進 additionalContext。
其他依賴全 monkeypatch，不讀寫 live 的 workflow/。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_ups_overview_wiring.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))   # worktree 內跑：wg_core 的 lib／workflow 指本樹
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_core  # noqa: E402
import wg_friction  # noqa: E402
import wg_overview  # noqa: E402
from handlers import user_prompt_submit as ups  # noqa: E402


def test_handler_has_atom_debug_error_bound():
    assert hasattr(ups, "_atom_debug_error")
    assert ups._atom_debug_error is wg_core._atom_debug_error


@pytest.fixture
def wired(monkeypatch):
    """handler 跑完整條路，但所有會碰檔案／模型／state 的依賴都換成空殼；回 (state, debug_calls, outputs)。"""
    state = {"turn_seq": 0}
    debug_calls, outputs = [], []
    monkeypatch.setattr(ups, "_ensure_state", lambda sid, inp, cfg: state)
    monkeypatch.setattr(ups, "_ups_sentinel_check_and_arm", lambda *a: None)
    monkeypatch.setattr(ups, "_ups_sentinel_clear", lambda sid: None)
    monkeypatch.setattr(ups, "run_pre_gates", lambda *a: None)
    monkeypatch.setattr(ups, "build_context", lambda *a: None)
    monkeypatch.setattr(ups, "collect_matched_atoms", lambda *a: ([], {}, [], [], {}, [], "general", {}))
    monkeypatch.setattr(ups, "assemble_injection", lambda *a, **k: ([], {}))
    monkeypatch.setattr(ups, "_maybe_spawn_failure_extraction", lambda *a: None)
    monkeypatch.setattr(ups, "_update_topic_tracker", lambda *a: None)
    monkeypatch.setattr(ups, "_truncate_context_by_activation", lambda lines, *a: lines)
    monkeypatch.setattr(ups, "reconcile_injection_after_trim", lambda *a: [])
    monkeypatch.setattr(ups, "write_state", lambda sid, st: None)
    monkeypatch.setattr(ups, "_atom_debug_error", lambda src, exc: debug_calls.append((src, repr(exc))))
    monkeypatch.setattr(ups, "output_json", lambda d: outputs.append(d))
    monkeypatch.setattr(ups, "output_nothing", lambda: outputs.append(None))
    monkeypatch.setattr(wg_friction, "record_correction", lambda *a: None)
    return state, debug_calls, outputs


INPUT = {"session_id": "sess-wiring", "prompt": "幫我看 C:/Work/Proj/src/A.cs", "transcript_path": ""}


def test_on_prompt_exception_does_not_break_handler(wired, monkeypatch):
    state, debug_calls, outputs = wired

    def _boom(*a, **k):
        raise RuntimeError("hub boom")
    monkeypatch.setattr(wg_overview, "on_prompt", _boom)
    ups.handle_user_prompt_submit(dict(INPUT), {"sync_keywords": []})
    assert debug_calls == [("ups:overview_hub", "RuntimeError('hub boom')")]
    assert state["turn_seq"] == 1 and len(outputs) == 1              # 走到尾、turn_seq 推進、有輸出


def test_p7_evasion_injection_carries_not_doing_hint(wired, monkeypatch):
    """G6 P7：上輪退避旗標注入舉證要求時，附上 Stop 給的不做行寫法（hint），AI 才知道「真的不做」要怎麼回；旗標注入後清空。"""
    state, debug_calls, outputs = wired
    state["evasion_flag"] = {"phrase": "既有的問題", "context_excerpt": "x", "category": "precedent-drift",
                             "hint": "真的不做 → 寫一行「不做｜<哪一件>：<理由：檢測時點 + 不修的實際風險>」"}
    monkeypatch.setattr(wg_overview, "on_prompt", lambda *a, **k: "")
    ups.handle_user_prompt_submit(dict(INPUT), {"sync_keywords": []})
    assert debug_calls == []
    text = outputs[0]["hookSpecificOutput"]["additionalContext"]
    assert "[Guardian:Evasion]" in text and "不做｜<哪一件>" in text and state["evasion_flag"] is None


def test_on_prompt_text_reaches_additional_context(wired, monkeypatch):
    state, debug_calls, outputs = wired
    monkeypatch.setattr(wg_overview, "on_prompt", lambda *a, **k: "[Guardian:OverviewHub] HUB-TEXT")
    ups.handle_user_prompt_submit(dict(INPUT), {"sync_keywords": []})
    assert debug_calls == []
    assert "HUB-TEXT" in outputs[0]["hookSpecificOutput"]["additionalContext"]


# ─── G7 意圖只認使用者原話：同伴訊息、背景通知不改 turn_intent（REFACTOR_NEEDS_EQUIVALENCE 據此擋） ───

_PEER_REFACTOR = '<cross-session-message from="claude-12">派工：把 wg_x 的分派重構成查表</cross-session-message>'


def _intent_after(wired, monkeypatch, prompt, prev=None):
    state, debug_calls, _ = wired
    if prev is not None:
        state["turn_intent"] = prev
    seen = {}
    monkeypatch.setattr(wg_overview, "on_prompt", lambda st, sid, p, tp, cfg, intent=None: seen.update(intent=intent) or "")
    ups.handle_user_prompt_submit({**INPUT, "prompt": prompt}, {"sync_keywords": []})
    assert debug_calls == []
    assert seen["intent"] == state["turn_intent"]                     # OverviewHub 拿到的就是 state 存的那一個
    return state["turn_intent"]


def test_g7_peer_message_does_not_set_refactor_intent(wired, monkeypatch):
    assert _intent_after(wired, monkeypatch, _PEER_REFACTOR) == "general"


def test_g7_user_typed_refactor_sets_intent(wired, monkeypatch):
    assert _intent_after(wired, monkeypatch, "派工：把 wg_x 的分派重構成查表") == "refactor"


def test_g7_user_words_win_over_peer_block_in_same_prompt(wired, monkeypatch):
    """同伴區塊命中 refactor 兩個詞、使用者自己打的只命中 perf 一個詞 → 照使用者的（舊碼兩邊加總會判成 refactor）。"""
    peer = '<cross-session-message from="claude-12">重構並整理 wg_x</cross-session-message>'
    assert _intent_after(wired, monkeypatch, f"{peer}\n這頁太慢了") == "perf"


@pytest.mark.parametrize("prompt", [_PEER_REFACTOR, "<task-notification>背景 agent 回報：重構完成</task-notification>"])
def test_g7_message_without_user_text_keeps_previous_intent(wired, monkeypatch, prompt):
    """整則沒有使用者打的字（同伴訊息、背景通知）→ 沿用上一則使用者訊息判的意圖，不改成 general 也不被正文改成 refactor。"""
    assert _intent_after(wired, monkeypatch, prompt, prev="perf") == "perf"
