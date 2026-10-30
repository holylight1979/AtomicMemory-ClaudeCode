"""verify_g7_equivalence.py：G7 等值證法與熱路徑——注入帶出三問、Stop 收尾核對（規則 REFACTOR_NEEDS_EQUIVALENCE／PERF_HOT_PATH_NEEDS_MEASURE）、
意圖來源核實。

怎麼跑：set WG_CLAUDE_DIR=<worktree> && python -X utf8 -m pytest -q hooks/verify/verify_g7_equivalence.py
案例分四段：
  1. 意圖來源：只看使用者本人打的字（同伴訊息裡的「重構」不算），回合中途只有 UserPromptSubmit 會改 turn_intent，所以等值那條可以擋。
  2. 規則純函式：三類收據、不適用宣告、熱路徑三種答法。
  3. Stop 驅動：等值與熱路徑擋、擋滿問使用者、使用者放行、收據資格（自寫哨兵、改檔之前的不算）、留帳 guard-equivalence。
  4. 注入：refactor 的 head 含三類、熱路徑、間接層；perf 只有熱路徑；feature 都沒有。
規則函式在案例裡才取（getattr），退回舊碼時每個案例各自紅，不會整檔匯入失敗。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_overview as wo  # noqa: E402
import wg_release_rules as rr  # noqa: E402
import hub_config as hc  # noqa: E402
import overview_hub as oh  # noqa: E402
from harness_text import IDE_TAG_NAMES, strip_harness_blocks, user_typed_text  # noqa: E402
from wg_atoms import classify_intent  # noqa: E402
from wg_release import RELEASE_TAG  # noqa: E402
from handlers import stop as st  # noqa: E402

_SID = "sid-g7"
_CODE = r"c:\proj\hooks\x.py"
_PC = "python skills/behavior-preservation/scripts/preserve-check.py --expected-from old.py --actual-from hooks/x.py --func f"
_DONE_TEXT = "改完了，全部完成。"
_HOT_NO = "熱路徑｜否｜只跑一次的安裝腳本"


def _rule(name):
    return getattr(rr, name)


def _r(seq, cmd, name="PRESERVE_CHECK", verdict="PASS", exit_code=0, kv=None, sentinels=None):
    return {"seq": seq, "turn_seq": 5, "tool": "Bash", "cmd": cmd, "cmd_full": True, "env": {},
            "sentinels": sentinels or [{"name": name, "verdict": verdict, "kv": kv or {}}], "exit_code": exit_code,
            "cwd": r"c:\proj", "project_root": r"c:\proj"}


def _three(seq=20):
    return [_r(seq + i, f"{_PC} --mutation {m}") for i, m in enumerate(("order", "side_effect", "boundary"))]


def _mf(path=_CODE, turn=5, last_seq=10):
    return {"path": path, "tool": "Edit", "session_id": _SID, "turn_seq": turn, "last_turn_seq": turn, "last_seq": last_seq}


# ─── 1. 意圖來源 ─────────────────────────────────────────────────────────

def test_intent_source_is_user_typed_text_so_equivalence_blocks():
    """(a) 成立（派工 002 修）：UserPromptSubmit 只拿使用者本人打的字判意圖，同伴信裡寫「重構」不算；REFACTOR_NEEDS_EQUIVALENCE 因此擋。
    經入口的先紅後綠案例在 verify_ups_overview_wiring.py（test_g7_*）；這裡守原始碼與規則說明同步。"""
    src = (HOOKS_DIR / "handlers" / "user_prompt_submit.py").read_text(encoding="utf-8")
    assert "typed = user_typed_text(prompt)" in src and "classify_intent(typed)" in src
    assert "classify_intent(clean_prompt)" not in src
    prompt = '<cross-session-message from="claude-12">派工：把 wg_x 的分派重構成查表</cross-session-message>'
    assert classify_intent(strip_harness_blocks(prompt, only=IDE_TAG_NAMES).strip()) == "refactor"   # 舊判法會誤判的那一則
    assert classify_intent(user_typed_text(prompt)) == "general"
    rule = rr.RULES["REFACTOR_NEEDS_EQUIVALENCE"]
    assert "只提醒" not in rule and "擋滿問使用者" in rule and "user_typed_text" in rule


def test_user_own_words_set_refactor_intent():
    assert classify_intent("把 wg_x 的 if 鏈重構成查表") == "refactor"


def test_only_prompt_handlers_write_turn_intent():
    """(b) 成立：state["turn_intent"] 只在 UserPromptSubmit（與它呼叫的 wg_overview.on_prompt）寫；AI 回合中途說「我來重構」
    不經過這兩處，不改意圖。"""
    writers = set()
    for p in HOOKS_DIR.rglob("*.py"):
        if "verify" in p.parts:
            continue
        if re.search(r"\[\s*[\"']turn_intent[\"']\s*\]\s*=(?!=)", p.read_text(encoding="utf-8", errors="replace")):
            writers.add(p.relative_to(HOOKS_DIR).as_posix())
    assert writers == {"handlers/user_prompt_submit.py", "wg_overview.py"}, writers
    src = (HOOKS_DIR / "wg_overview.py").read_text(encoding="utf-8")
    on_prompt = src[src.index("def on_prompt("):src.index("def _strip_extended(")]
    assert 'state["turn_intent"] = intent' in on_prompt


# ─── 2. 規則純函式 ───────────────────────────────────────────────────────

def test_three_pass_receipts_prove_all_mutations():
    receipts = [(f"{_PC} --mutation {m}", ["PRESERVE_CHECK:PASS"], 0) for m in ("boundary", "order", "side_effect")]
    assert _rule("proved_mutations")(receipts) == ["order", "side_effect", "boundary"]


def test_failed_or_unmarked_receipt_proves_nothing():
    receipts = [(f"{_PC} --mutation order", ["PRESERVE_CHECK:FAIL"], 1), (f"{_PC} --mutation=side_effect", ["PRESERVE_CHECK:PASS"], 1),
                (_PC, ["PRESERVE_CHECK:PASS"], 0), (f"{_PC} --mutation boundary", ["X_CHECK:PASS"], 0)]
    assert _rule("proved_mutations")(receipts) == []


def test_repeated_mutation_args_prove_only_the_last():
    """codex BLOCK 1：preserve-check.py 的 --mutation 是單值參數，一條指令重複指定只跑最後一個 → 一筆收據只算最後那一類。"""
    cmd = f"{_PC} --mutation order --mutation side_effect --mutation boundary"
    assert _rule("proved_mutations")([(cmd, ["PRESERVE_CHECK:PASS"], 0)]) == ["boundary"]


def test_measure_needs_numbers():
    has = _rule("has_measure")
    assert has([("python bench.py", ["RENDER_BENCH:DONE"], 0, [{"ms": "12"}])])
    assert not has([("python -m pytest", ["PYTEST:PASS", "PYTEST_MEASURE:DONE"], 0, [{}])])
    assert not has([("python bench.py", ["RENDER_BENCH:DONE"], 1, [{"ms": "12"}])])


def test_only_order_lists_missing_two():
    v = _rule("equivalence_verdict")(["order"], [])
    assert v.owed and "side_effect、boundary" in v.why and "order" not in v.why
    assert any("preserve-check.py --mutation order|side_effect|boundary" in e for e in v.evidence)


def test_not_applicable_needs_reason():
    parse = _rule("parse_equivalence_lines")
    ok = _rule("equivalence_verdict")([], parse("`等值證法｜不適用｜改的是測試錄製檔`")["na"])
    assert not ok.owed and "測試錄製檔" in ok.why
    for text in ("等值證法｜不適用｜", "等值證法｜不適用", "等值證法｜不適用｜<理由>"):
        v = _rule("equivalence_verdict")([], parse(text)["na"])
        assert v.owed and "沒附理由" in v.why, text


def test_hot_path_answers():
    parse, verdict = _rule("parse_equivalence_lines"), _rule("hot_path_verdict")
    yes = parse("熱路徑｜是｜render 迴圈")
    assert verdict(yes["hot"], yes["skip"], False).owed
    assert not verdict(yes["hot"], yes["skip"], True).owed
    skip = parse("熱路徑｜是｜render 迴圈\n量測｜不做｜這台沒有 GPU，量了不準")
    assert not verdict(skip["hot"], skip["skip"], False).owed
    no = parse(_HOT_NO)
    assert not verdict(no["hot"], no["skip"], False).owed
    bare_no = parse("熱路徑｜否｜")
    assert verdict(bare_no["hot"], bare_no["skip"], False).owed
    none = verdict([], [], False)
    assert none.owed and "沒答" in none.why


def test_copied_entry_line_is_not_an_answer():
    """照抄擋訊息的入口寫法（角括號佔位）不算答了熱路徑。"""
    p = _rule("parse_equivalence_lines")("答 `熱路徑｜是｜<哪裡>`＋量測收據（`<NAME> DONE k=v`）")
    assert p["hot"] == []


# ─── 3. Stop 驅動 ────────────────────────────────────────────────────────

@pytest.fixture()
def drive(monkeypatch, capsys):
    """驅動 handle_stop 到 Equivalence Gate：對帳與驗證範圍關掉、其他副作用拿掉。回 run(text, …) → (stdout, state, equivalence 留帳)。"""
    logs: list = []
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [])
    monkeypatch.setattr(st, "_git_unpushed_roots", lambda mf: [])
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)
    monkeypatch.setattr(st, "_hud_alive", lambda *a, **k: (True, {}))
    monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: None)
    monkeypatch.setattr(st, "pending_gate_reason", lambda *a, **k: None)
    monkeypatch.setattr(st, "reading_path_note", lambda *a, **k: ("", False))
    monkeypatch.setattr(st, "_record_pick", lambda *a, **k: None)
    monkeypatch.setattr(st.aec_ledger, "collect_at_completion", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    monkeypatch.setattr(rr, "mode_of", lambda rule: rr.BLOCK)   # 規則 GATE_MODE_TABLE：送法只讀 wg_release_rules.RULE_MODE。這個檔的案例驗的是判定與擋訊息內容，把送法釘成 block 讓它們照驗；v6 預設的提醒送法（Stop 只留帳、提醒掛改檔那則工具結果）由 verify_gate_mode_stop.py 驗。
    results: list = []                                                  # 閘每次的回傳值：反例直接斷言是 None，不只看輸出字樣
    real_gate = st._equivalence_gate
    monkeypatch.setattr(st, "_equivalence_gate", lambda *a, **k: results.append(real_gate(*a, **k)) or results[-1])

    def run(text, intent="refactor", mods=None, receipts=None, state=None, config=None):
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: text)
        monkeypatch.setattr(st, "get_current_turn_visible_text", lambda *a, **k: ("", {"turn_tool_names_all": []}))
        if state is None:
            state = {"phase": "working", "failing_tests": [], "recent_user_prompts": [], "stop_blocked_count": 0, "turn_seq": 5,
                     "turn_intent": intent, "modified_files": [_mf()] if mods is None else mods,
                     "verify_receipts": {_SID: list(receipts or [])}}
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        logs.clear()
        results.clear()
        capsys.readouterr()
        cfg = {"reconcile_gate": {"enabled": False}, **(config or {})}
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, cfg)
        return capsys.readouterr().out, state, [p for g, p in logs if g == "equivalence"]

    run.results = results
    return run


def _json(out):
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {}


def _blocked(out):
    o = _json(out)
    return o.get("reason", "") if o.get("decision") == "block" else ""


def test_refactor_without_receipts_blocks_with_missing_three(drive):
    out, _, logs = drive(f"{_HOT_NO}\n{_DONE_TEXT}")
    reason = _blocked(out)
    assert "REFACTOR_NEEDS_EQUIVALENCE" in reason and "order、side_effect、boundary" in reason
    assert "preserve-check.py --mutation order|side_effect|boundary" in reason and "等值證法｜不適用｜<理由>" in reason
    assert any(l["event"] == "block" and "REFACTOR_NEEDS_EQUIVALENCE" in l["rules"] for l in logs)


def test_equivalence_blocks_up_to_budget_then_asks_user_and_release_passes(drive):
    text = f"{_HOT_NO}\n{_DONE_TEXT}"
    out, state, _ = drive(text)
    assert _blocked(out)
    drive(text, state=state)
    out3, _, logs = drive(text, state=state)
    assert RELEASE_TAG in _blocked(out3) and "REFACTOR_NEEDS_EQUIVALENCE" in out3
    assert any(l["event"] == "exhausted_block" for l in logs)
    state["turn_prompts"] = ["放行"]                                      # 使用者在最後一次擋之後打「放行」
    out4, _, logs = drive(text, state=state)
    assert drive.results == [None] and any(l["event"] == "user_release" for l in logs)
    drive(text, state=state)
    assert drive.results == [None]                                      # 放行一次＝這一回合不再擋


def test_three_pass_receipts_after_edit_pass(drive):
    out, _, _ = drive(f"{_HOT_NO}\n{_DONE_TEXT}", receipts=_three())
    assert "[Guardian:Equivalence]" not in out and drive.results == [None]


# 第三跑 A′ 原指令：三類寫在一條 for 迴圈裡跑，每輪 echo "exit=$?"（引號裡的 exit 不是跳出）；輸出三行 PRESERVE_CHECK PASS
_A3_LOOP = ("for m in order side_effect boundary; do echo \"=== $m\"; python ~/.claude/skills/behavior-preservation/scripts/"
            "preserve-check.py --expected-from C:/Users/x/AppData/Local/Temp/qa2-old/pricing/rates.py --actual-from "
            "C:/w4/qa2-pricing/pricing/rates.py --mutation $m --func tier_rate --order-func tiers --effect log; echo \"exit=$?\"; done")


def _loop(cmd=_A3_LOOP, n=3, extra=()):
    return [_r(20, cmd, sentinels=[{"name": "PRESERVE_CHECK", "verdict": "PASS", "kv": {}, "n": n}, *extra])]


def test_loop_running_three_mutations_passes(drive):
    """規則 EQUIVALENCE_LOOP_EXPANDED：A′ 那條迴圈一次跑完三類、印三行 PASS → 三類都算證到（之前擋「已證：無」、拆三條才過）。"""
    assert _rule("RULES")["EQUIVALENCE_LOOP_EXPANDED"]
    out, _, _ = drive(f"{_HOT_NO}\n{_DONE_TEXT}", receipts=_loop())
    assert "[Guardian:Equivalence]" not in out and drive.results == [None]


@pytest.mark.parametrize("receipts", [
    _loop(n=1),                                                                       # 只看到一行 PASS：有幾輪沒印哨兵
    _loop(extra=({"name": "PRESERVE_CHECK", "verdict": "FAIL", "kv": {}, "n": 1},)),  # 有一輪紅
    _loop(cmd=_A3_LOOP.replace("order side_effect boundary", "$(cat kinds.txt)")),     # 清單不是字面
    _loop(cmd=_A3_LOOP.replace("--effect log;", "--effect log; break;")),              # 本體真的有跳出
], ids=["one-pass-line", "has-fail", "list-not-literal", "real-break"])
def test_loop_without_full_evidence_still_blocks(drive, receipts):
    out, _, _ = drive(f"{_HOT_NO}\n{_DONE_TEXT}", receipts=receipts)
    assert "REFACTOR_NEEDS_EQUIVALENCE" in _blocked(out)


def test_only_order_receipt_blocks_missing_two(drive):
    out, _, _ = drive(f"{_HOT_NO}\n{_DONE_TEXT}", receipts=_three()[:1])
    assert "side_effect、boundary" in _blocked(out) and "已證：order" in _blocked(out)


def test_receipts_before_last_edit_do_not_count(drive):
    out, _, _ = drive(f"{_HOT_NO}\n{_DONE_TEXT}", receipts=_three(seq=1))
    assert "order、side_effect、boundary" in _blocked(out)


def test_not_applicable_with_reason_passes_and_logs(drive):
    out, _, logs = drive(f"等值證法｜不適用｜改的是測試錄製檔\n{_HOT_NO}\n{_DONE_TEXT}")
    assert "[Guardian:Equivalence]" not in out and drive.results == [None]
    na = [l for l in logs if l["event"] == "not_applicable"]
    assert len(na) == 1 and "測試錄製檔" in na[0]["line"]


def test_not_applicable_logged_when_gate_does_not_apply(drive):
    """規則 EQUIVALENCE_NA_DECLARED_ALWAYS_LOGGED：意圖不是重構（等值閘這回合不管）也照記，needed=False。"""
    out, _, logs = drive(f"等值證法｜不適用｜新檔，沒有舊行為要保持\n{_DONE_TEXT}", intent="feature")
    na = [l for l in logs if l["event"] == "not_applicable"]
    assert [(l["needed"], l["reason"]) for l in na] == [(False, "新檔，沒有舊行為要保持")]


def test_not_applicable_logged_even_when_an_earlier_gate_blocks(drive):
    """紅測閘先擋下（等值閘走不到），宣告照記，needed=True。"""
    state = {"phase": "working", "recent_user_prompts": [], "stop_blocked_count": 0, "turn_seq": 5, "turn_intent": "refactor",
             "modified_files": [_mf()], "verify_receipts": {_SID: []},
             "failing_tests": [{"session_id": _SID, "turn_seq": 5, "cmd": "pytest -q t.py", "summary": "FAILED t.py::a", "exit_code": 1}]}
    out, _, logs = drive(f"等值證法｜不適用｜改的是測試錄製檔\n{_HOT_NO}\n{_DONE_TEXT}", state=state)
    assert "TestFailGate" in _blocked(out) and drive.results == []        # 前置：等值閘沒走到
    assert [l["needed"] for l in logs if l["event"] == "not_applicable"] == [True]


def test_same_not_applicable_line_in_same_turn_logged_once(drive):
    a, b = "等值證法｜不適用｜改的是測試錄製檔", "等值證法｜不適用｜只動了註解"
    counts = []
    state = None
    for text in (a, a, b, a):
        out, state, logs = drive(f"{text}\n{_HOT_NO}\n{_DONE_TEXT}", state=state)
        counts.append(len([l for l in logs if l["event"] == "not_applicable"]))
    assert counts == [1, 0, 1, 0]


def test_not_applicable_without_reason_blocks(drive):
    out, _, _ = drive(f"等值證法｜不適用｜\n{_HOT_NO}\n{_DONE_TEXT}")
    assert "沒附理由" in _blocked(out)


def test_hot_path_yes_without_measure_blocks_then_done_receipt_passes(drive):
    text = f"等值證法｜不適用｜改的是測試錄製檔\n熱路徑｜是｜render 迴圈\n{_DONE_TEXT}"
    out, _, logs = drive(text)
    reason = _blocked(out)
    assert "PERF_HOT_PATH_NEEDS_MEASURE" in reason and "render 迴圈" in reason
    assert "熱路徑｜是｜<哪裡>" in reason and "量測｜不做｜<理由>" in reason and "熱路徑｜否｜<為什麼>" in reason
    assert any(l["event"] == "block" for l in logs)
    out2, _, _ = drive(text, receipts=[_r(30, "python bench/render_bench.py", name="RENDER_BENCH", verdict="DONE", kv={"ms": "12"})])
    assert "[Guardian:Equivalence]" not in out2 and drive.results == [None]


def test_plain_pytest_summary_is_not_a_measure(drive):
    """codex BLOCK 2：設定把 pytest 統計行轉成 PYTEST:PASS＋PYTEST_MEASURE:DONE（沒有 k=v）；跑一般測試不等於量了熱路徑，照擋。"""
    pytest_rcpt = _r(30, "python -m pytest -q hooks/verify/verify_x.py", sentinels=[
        {"name": "PYTEST", "verdict": "PASS", "kv": {}}, {"name": "PYTEST_MEASURE", "verdict": "DONE", "kv": {}}])
    out, _, _ = drive(f"熱路徑｜是｜render 迴圈\n{_DONE_TEXT}", intent="perf", receipts=[pytest_rcpt])
    assert "PERF_HOT_PATH_NEEDS_MEASURE" in _blocked(out)


def test_hot_path_no_with_reason_passes_and_logs(drive):
    out, _, logs = drive(f"{_HOT_NO}\n{_DONE_TEXT}", intent="perf")
    assert "[Guardian:Equivalence]" not in out and drive.results == [None]
    assert any(l["event"] == "hot_path" for l in logs)


def test_hot_path_unanswered_blocks_once_per_turn(drive):
    out, state, _ = drive(_DONE_TEXT, intent="perf")
    assert "沒答" in _blocked(out) and "REFACTOR_NEEDS_EQUIVALENCE" not in out
    out2, _, logs = drive(_DONE_TEXT, state=state)
    assert "[Guardian:Equivalence]" not in out2 and drive.results == [None]
    assert any(l["event"] == "hot_unanswered_passed" for l in logs)


def test_hot_path_answered_blocks_up_to_budget_then_asks_user(drive):
    text = f"熱路徑｜是｜render 迴圈\n{_DONE_TEXT}"
    out, state, _ = drive(text, intent="perf")
    assert _blocked(out)
    drive(text, state=state)
    out3, _, logs = drive(text, state=state)
    assert RELEASE_TAG in _blocked(out3) and "PERF_HOT_PATH_NEEDS_MEASURE" in out3
    assert any(l["event"] == "exhausted_block" for l in logs)


def test_refactor_blocks_both_rules_in_one_message(drive):
    """等值與熱路徑都缺：一則擋訊息列兩條（不各佔一次 Stop）。"""
    reason = _blocked(drive(_DONE_TEXT)[0])
    assert "PERF_HOT_PATH_NEEDS_MEASURE" in reason and "REFACTOR_NEEDS_EQUIVALENCE" in reason


@pytest.mark.parametrize("intent", ["feature", "debug", "general"])
def test_other_intents_not_gated(drive, intent):
    out, state, logs = drive(_DONE_TEXT, intent=intent)
    assert state["turn_intent"] == intent and state["modified_files"]                 # 前置：有改程式檔、有宣告完成，只差意圖
    assert "[Guardian:Equivalence]" not in out and not logs and drive.results == [None]


def test_no_code_change_or_no_completion_not_gated(drive):
    out, _, _ = drive(_DONE_TEXT, mods=[_mf(path=r"c:\proj\docs\x.md")])
    assert "[Guardian:Equivalence]" not in out and drive.results == [None]
    out2, _, _ = drive("這段改到一半，接著看下一段。")
    assert "[Guardian:Equivalence]" not in out2 and drive.results == [None]


def test_disabled_by_hub_config(drive):
    out, _, _ = drive(_DONE_TEXT, config={"overview_hub": {"equivalence": {"enabled": False}}})
    assert "[Guardian:Equivalence]" not in out and drive.results == [None]


# ─── 4. 注入 ─────────────────────────────────────────────────────────────

_ROW = {"part": "x 部位", "part_short": "x", "status": "無", "cards": [], "line": "| x |", "layer": ""}


def _head(intent):
    gw = hc.HUB_DEFAULTS["goal_weights"][intent]
    text, _ = oh.build_injection_ex(_ROW, [], r"c:\proj\x.py", 6000, None, None, list(gw.get("slices") or []),
                                    str(gw.get("lens") or ""), str(gw.get("ask_first") or ""), extra=str(gw.get("extra") or ""))
    return text


def test_inject_head_by_intent():
    ref, perf, feat = _head("refactor"), _head("perf"), _head("feature")
    assert all(w in ref for w in ("順序／副作用／邊界", "PRESERVE_CHECK PASS", "熱路徑或大量配置", "間接層"))
    assert "熱路徑或大量配置" in perf and "等值證法" not in perf and "間接層" not in perf
    assert "熱路徑" not in feat and "等值證法" not in feat


def test_overview_inject_passes_extra(monkeypatch, tmp_path):
    """wg_overview._inject 依 state 意圖把 goal_weights.<意圖>.extra 接進 head。"""
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "_resolve_row_cards", lambda *a, **k: ([], None))
    monkeypatch.setattr(wo, "_tracking_for", lambda *a, **k: [])
    monkeypatch.setattr(wo._oh, "path_kind", lambda *a, **k: None)
    cfg = hc.merge_hub_cfg({}, None, None)
    assert cfg["_errors"] == []
    text = wo._inject({"turn_intent": "refactor"}, "s", tmp_path, dict(_ROW), str(tmp_path / "x.py"), "read", "", cfg)
    assert "等值證法三類" in text and "間接層" in text
    text2 = wo._inject({"turn_intent": "feature"}, "s", tmp_path, dict(_ROW), str(tmp_path / "x.py"), "read", "", cfg)
    assert "等值證法" not in text2


def test_hub_config_validates_new_keys():
    bad = hc.merge_hub_cfg({"overview_hub": {"equivalence": {"enabled": "yes", "x": 1},
                                             "goal_weights": {"refactor": {"extra": 3}}}}, None, None)
    errs = "\n".join(bad["_errors"])
    assert "equivalence.enabled" in errs and "equivalence 有未知鍵「x」" in errs and "goal_weights.refactor.extra" in errs
    assert hc.HUB_DEFAULTS["equivalence"] == {"enabled": True}
