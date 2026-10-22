"""verify_g6_rules_to_llm.py — G6 階段 5：五處固定規則改交 AI 判（字詞表與門檻只篩候選，AI 宣告附理由、程式核對並留帳）。

做什麼：每件一條有名規則（hooks/wg_release_rules.RULES）＋會紅的案例（舊碼照固定規則處置）＋反例（AI 判「不是」不計數、不自動處置）。
1. CORRECTION_WORDS_ARE_HINTS（wg_friction、user_prompt_submit、stop._record_prompt_judgments）
2. EXTRACT_VETO_NEEDS_JUDGMENT（wg_extraction、handlers/ups_gates）
3. HARVEST_WAIVER_ITEMIZED（wg_harvest 收割閘與收割待補、wg_evasion 收尾檢核）
4. CONFLICT_DECLARED_BY_AI（tools/memory-conflict-detector write-check 與拉取稽核）
5. PROJECT_LITERAL_IS_HINT（lib/realm_gate global／org）
不碰 live：guard log 全收進 list、向量與本地模型 stub、registry monkeypatch、state 不落檔。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_g6_rules_to_llm.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CODE_ROOT = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CODE_ROOT))

import wg_core  # noqa: E402
import wg_entrypoint as ep  # noqa: E402
import wg_evasion as wev  # noqa: E402
import wg_extraction as wex  # noqa: E402
import wg_friction as wf  # noqa: E402
import wg_harvest as wh  # noqa: E402
import wg_release_rules as rr  # noqa: E402
from handlers import stop as st  # noqa: E402
from handlers import ups_gates as ug  # noqa: E402
from lib import realm_gate as rg  # noqa: E402

_spec = importlib.util.spec_from_file_location("memory_conflict_detector_g6", CODE_ROOT / "tools" / "memory-conflict-detector.py")
det = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(det)

SID = "s-g6"
CORE = r"c:\a\.claude\hooks\x.py"
DONE = "全部完成了"


@pytest.fixture
def logs(monkeypatch):
    """guard log 收進 list：[(guard, payload)]。wg_core 那支給 import 時才取的呼叫端（entry_note、否決、realm、偵測器）。"""
    got = []

    def _log(guard, payload):
        got.append((guard, dict(payload)))
    monkeypatch.setattr(wg_core, "append_guard_log", _log)
    monkeypatch.setattr(wf, "append_guard_log", _log)
    monkeypatch.setattr(st, "append_guard_log", _log)
    return got


def _events(logs, guard):
    return [p for g, p in logs if g == guard]


# ─── 1. CORRECTION_WORDS_ARE_HINTS ───────────────────────────────────────────

def test_correction_hit_is_pending_not_counted(logs):
    """會紅：舊碼命中「不對」就計數。現在記待判、不計，留帳 candidate。"""
    state = {"turn_seq": 3}
    assert wf.record_correction(state, SID, "這樣不對嗎？我是說另一個檔不對", {})
    assert "user_correction_count" not in state
    assert state["user_correction_pending"]["kw"] == ["不對"]
    assert _events(logs, "friction")[-1]["event"] == "candidate"


def test_correction_declared_not_is_not_counted(logs):
    """反例：AI 判「不是」→ 不計數、帳上留 AI 的理由。"""
    state = {"turn_seq": 3}
    wf.record_correction(state, SID, "不對，順便看一下 log", {})
    assert wf.resolve_correction(state, SID, "前文\n糾正｜不是：他在說 log 裡那行輸出不對，不是說我做錯") is False
    assert "user_correction_pending" not in state and not state.get("user_correction_count")
    last = _events(logs, "friction")[-1]
    assert last["event"] == "judged" and last["correction"] is False and "log 裡那行" in last["reason"]
    assert not wf.friction_triggered(state, {"friction": {"min_hits": 1}})


def test_correction_declared_yes_counts(logs):
    state = {"turn_seq": 3}
    wf.record_correction(state, SID, "我說過不要動 config", {})
    assert wf.resolve_correction(state, SID, "糾正｜是：他之前說過不要動 config，我動了") is True
    assert state["user_correction_count"] == 1 and state["user_correction_hits"][-1]["by"] == "judged"


def test_correction_placeholder_or_silence_is_not_counted(logs):
    """理由只有佔位不算回；一直沒回 → 下一則使用者本人打的訊息結帳：沒人判過不計（詞表不替 AI 判），留帳 undeclared。
    背景通知不算使用者開新回合，不結帳。"""
    state = {"turn_seq": 3}
    wf.record_correction(state, SID, "重來", {})
    assert wf.resolve_correction(state, SID, "糾正｜不是：<理由>") is None
    assert state.get("user_correction_pending")
    wf.record_correction(state, SID, "<task-notification>agent done 不對</task-notification>", {})
    assert state.get("user_correction_pending")
    wf.record_correction(state, SID, "好，繼續下一步", {})
    assert not state.get("user_correction_count") and "user_correction_pending" not in state
    assert _events(logs, "friction")[-1]["event"] == "undeclared"


def test_quoted_declaration_in_prose_is_not_an_answer(logs):
    """codex 獨立審：句中引用的宣告字樣是說明不是答覆；只認行首，好幾條以最後一條為準。"""
    state = {"turn_seq": 3}
    assert wf.record_correction(state, SID, "log 那行不對，進度到哪了", {})          # 前置：真的記了待判
    text ="說明：不要寫成『糾正｜是：使用者在糾正方向』那樣。\n- 糾正｜是：先記一下\n- 糾正｜不是：他只是在問進度"
    assert wf.resolve_correction(state, SID, text) is False
    assert not state.get("user_correction_count")
    assert rr.yes_no_declaration("他說「糾正｜是：x」", "糾正") is None


def test_question_moment_logs_guard_entry_for_each_new_entry(logs):
    """問的那一刻（entry_note）認得出切入點、記 guard-entry ask：E38、E39、E40、E41。"""
    asks = {
        "user_prompt": [wf.correction_question(["不對"]), wex.extract_veto_question(["否"], [{"statement": "s"}])],
        "stop_piggyback": [wh.harvest_block_message()],
        "mcp_reply": ["衝突待宣告（這次不寫檔）：x", "atom_write: realm gate …\n" + rg.LITERAL_HINT],
    }
    for path, texts in asks.items():
        for t in texts:
            ep.entry_note(t, path, session_id=SID, state={}, pool=[])
    got = {p["entry"] for g, p in logs if g == "entry" and p.get("event") == "ask"}
    assert {"E38", "E39", "E40", "E41"} <= got


def test_correction_question_is_entrypoint_e38():
    q = wf.correction_question(["不對"])
    assert "糾正｜是：" in q and "糾正｜不是：" in q
    assert [r["id"] for r in ep.match_entries(q, "user_prompt")] == ["E38"]


def _transcript(user: str, assistant: str) -> str:
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in (
        {"type": "user", "message": {"role": "user", "content": user}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": assistant}]}},
    ))


def test_stop_collects_declaration_from_turn_text(logs, monkeypatch):
    """Stop 在所有閘之前收本回合可見文字的宣告行：糾正與否決兩種待判一起結。"""
    writes = []
    monkeypatch.setattr(st, "write_state", lambda sid, s: writes.append(sid))
    state = {"turn_seq": 4, "user_correction_pending": {"turn": 4, "kw": ["不對"], "excerpt": "不對"},
             "extract_veto_pending": {"turn": 4, "hints": ["否"], "statements": ["一律 UTF-8"]}}
    text = _transcript("這樣不對嗎？是否要改", "看過了。\n糾正｜不是：他在問問題\n否決記憶｜不是：「是否」是在問我能不能改")
    st._record_prompt_judgments(state, SID, None, text)
    assert "user_correction_pending" not in state and "extract_veto_pending" not in state
    assert not state.get("user_correction_count") and writes == [SID]
    assert _events(logs, "extract_veto")[-1]["veto"] is False


# ─── 2. EXTRACT_VETO_NEEDS_JUDGMENT ──────────────────────────────────────────

def _pre_gates(monkeypatch, prompt, confirmed):
    monkeypatch.setattr(ug, "check_long_die_status", lambda: {"backend": "ollama"})
    monkeypatch.setattr(ug, "disable_backend", lambda name: True)
    monkeypatch.setattr(ug, "OllamaClient", None)
    state, lines = {"turn_seq": 7, "confirmed_extractions": confirmed}, []
    ug.run_pre_gates(SID, state, {}, prompt, prompt.lower(), lines)
    return state, lines


def test_veto_word_inside_question_keeps_notice_and_asks(logs, monkeypatch):
    """會紅：舊碼這則有「否」就整批丟掉通知（卡也沒撤）。現在通知照送、附卡路徑，另問 AI 是不是在否決。"""
    ext = [{"statement": "表格一律用 UTF-8", "write_result": "wrote", "atom_path": "/m/utf8.md"}]
    state, lines = _pre_gates(monkeypatch, "這樣改是否會影響舊報表？", ext)
    assert any("已記為 atom（/m/utf8.md）" in ln for ln in lines)
    q = [ln for ln in lines if wex.EXTRACT_VETO_MARKER in ln]
    assert q and "否決記憶｜是：" in q[0] and "atom_retire" in q[0]
    assert state["extract_veto_pending"]["statements"] == ["表格一律用 UTF-8"]
    assert state["extract_veto_pending"]["atoms"] == ["/m/utf8.md"]
    assert state["confirmed_extractions"] == []
    assert [r["id"] for r in ep.match_entries(q[0], "user_prompt")] == ["E39"]


def test_veto_pending_keeps_every_written_card(logs, monkeypatch):
    """codex 獨立審 WARN：剛寫成的卡有四張，待判與帳要四張都在（問句只列前三、附「另 N 條」）。"""
    ext = [{"statement": f"決策{i}", "write_result": "wrote", "atom_path": f"/m/d{i}.md"} for i in range(4)]
    state, lines = _pre_gates(monkeypatch, "這四條是否都要？", ext)
    assert state["extract_veto_pending"]["atoms"] == [f"/m/d{i}.md" for i in range(4)]
    assert any("另 1 條" in ln for ln in lines if wex.EXTRACT_VETO_MARKER in ln)


def test_worker_records_card_path_for_notice(tmp_path, monkeypatch):
    """萃取寫卡成功 → 卡的落點記回那筆（通知與否決問句才指得出要撤哪張）；寫入結果沒有 path 欄也不炸、記空字串。"""
    spec = importlib.util.spec_from_file_location("uew_g6", HOOKS_DIR / "user-extract-worker.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    monkeypatch.setattr(m, "_write_pending_candidate", lambda *a, **k: None)
    l2 = {"statement": "專案版本控制必須使用 GIT，禁止使用 SVN", "scope": "personal", "audience": "programmer", "trigger": ["git"]}

    class WithPath:
        ok, error, path = True, "", proj / ".claude" / "memory" / "shared" / "x.md"

    class NoPath:
        ok, error = True, ""
    for result, want in ((WithPath(), str(WithPath.path)), (NoPath(), "")):
        monkeypatch.setattr(m, "write_atom", lambda **kw: result)
        ext = {"turn_id": "t-1", "cwd": str(proj)}
        assert m._write_atom_via_mcp(l2, ext, "sid", "u", {}) == "wrote"
        assert ext["atom_path"] == want


def test_no_veto_hint_no_question(logs, monkeypatch):
    """反例：這則沒有否決字樣 → 只送通知、不問、不記待判。"""
    ext = [{"statement": "表格一律用 UTF-8", "write_result": "wrote"}]
    state, lines = _pre_gates(monkeypatch, "好，繼續做下一件", ext)
    assert any("已記為 atom" in ln for ln in lines)
    assert not any(wex.EXTRACT_VETO_MARKER in ln for ln in lines) and "extract_veto_pending" not in state


def test_veto_declarations_and_undeclared_ledger(logs):
    state = {"extract_veto_pending": {"turn": 7, "hints": ["不要記"], "statements": ["s"], "atoms": ["/m/s.md"]}}
    assert wex.resolve_extract_veto(state, SID, "否決記憶｜是：他說這條不要記，已 atom_retire") is True
    last = _events(logs, "extract_veto")[-1]
    assert last["event"] == "judged" and last["atoms"] == ["/m/s.md"]
    state = {"extract_veto_pending": {"turn": 8, "hints": ["否"], "statements": ["s"]}}
    assert wex.resolve_extract_veto(state, SID, "沒有宣告") is None
    wex.settle_pending_veto(state, SID)
    assert "extract_veto_pending" not in state and _events(logs, "extract_veto")[-1]["event"] == "undeclared"


# ─── 3. 收割與收尾檢核的使用者豁免：dismiss 詞整批放行、留帳 ────────────────────

_HCFG = {"harvest": {"enabled": True, "min_turns": 3, "min_accessed": 5, "min_turns_between": 3,
                     "background": False}}   # 測擋下與豁免這條路（背景收割關掉或送不出去時走它）


def _hstate(**kw):
    s = {"modified_files": [{"path": CORE, "session_id": SID}], "recent_user_prompts": ["測試那支先這樣，其他照做"], "turn_seq": 5,
         "turn_intent": "feature"}
    s.update(kw)
    return s


def test_dismiss_word_waives_harvest_and_reports(logs):
    """近 3 則有 dismiss 詞（先這樣）：收割整批放行，回報那一則原話給呼叫端留帳；不用寫不做行引用。"""
    s = _hstate(recent_user_prompts=["收割先這樣，下班了"])
    waived = []
    assert wh.harvest_gate_reason(s, SID, DONE, _HCFG, s["modified_files"], 5, waived=waived) is None
    assert waived and waived[0]["item"] == "收割" and waived[0]["quote"] == "收割先這樣，下班了"


def test_waiver_quote_not_in_user_words_still_blocks(logs):
    """反例：近 3 則沒有 dismiss 詞 → 照擋（AI 自己寫的不做行不算豁免）。"""
    s = _hstate(recent_user_prompts=["繼續"])
    assert wh.harvest_gate_reason(s, SID, DONE + "\n不做｜收割：使用者說「先這樣」", _HCFG, s["modified_files"], 5)


def test_pending_waiver_dismiss_releases_whole_batch(logs):
    """收割待補：近 3 則有 dismiss 詞整批放行，每一筆都回報留帳；沒有 dismiss 詞照擋、列出每一筆。"""
    kh = {SID: {"pending": ["card-a: 無 create receipt（path=x）", "card-ab: 無 append receipt（path=y）"]}}
    s = _hstate(knowledge_harvest=kh, recent_user_prompts=["card-a 先這樣"])
    waived = []
    assert wh.pending_gate_reason(s, SID, 5, "", waived=waived) is None
    assert [w["item"][:7] for w in waived] == ["card-a:", "card-ab"]
    msg = wh.pending_gate_reason(_hstate(knowledge_harvest=kh, recent_user_prompts=["繼續"]), SID, 5, "")
    assert msg and "card-a:" in msg and "card-ab" in msg


def test_stop_waivers_release_and_ledger_each_gate(logs, monkeypatch, capsys):
    """端到端（Stop）：使用者說收割與收尾檢核都先這樣 → 兩閘都放行，guard-harvest_waived 各一筆；同一個使用者回合不重記；
    沒有 dismiss 詞的對照照擋。"""
    for name, val in (("_find_session_transcript", lambda *a, **k: None), ("token_warn_payload", lambda *a, **k: ""),
                      ("detect_evasion", lambda *a, **k: None), ("write_state", lambda *a, **k: None),
                      ("_attribute_usefulness", lambda *a, **k: None), ("_detect_uncommitted_files", lambda mf: []),
                      ("_git_unpushed_roots", lambda mf: []), ("_should_deep_postmortem", lambda *a, **k: False),
                      ("_maybe_spawn_user_extract_worker", lambda *a, **k: None), ("_hud_alive", lambda *a, **k: (True, {}))):
        monkeypatch.setattr(st, name, val)

    def drive(said, state=None):
        state = state or _hstate(recent_user_prompts=[said], phase="working", failing_tests=[], stop_blocked_count=0)
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: DONE)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": SID, "cwd": ""}, _HCFG)
        return capsys.readouterr().out

    assert "KnowledgeHarvest" in drive("繼續")
    del logs[:]
    said = "收割和收尾檢核都先這樣"
    same = _hstate(recent_user_prompts=[said], phase="working", failing_tests=[], stop_blocked_count=0)
    out = drive(said, same)
    assert "KnowledgeHarvest" not in out and "ScanReport" not in out
    assert sorted(p["gate"] for p in _events(logs, "harvest_waived")) == ["closing_check", "harvest"]
    drive(said, same)                                    # 同一個使用者回合再 Stop 一次：不重記
    assert len(_events(logs, "harvest_waived")) == 2


def test_waiver_ledger_dedupes_within_one_batch(logs, monkeypatch):
    """同一批豁免裡重複的那件也只記一筆（codex 兩輪 WARN）。"""
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    w = {"item": "card-a: 無 create receipt", "quote": "先這樣", "line": "不做｜card-a：使用者說「先這樣」"}
    state = {}
    st._log_waivers(state, SID, 5, 2, "harvest_pending", [w, dict(w)])
    st._log_waivers(state, SID, 6, 2, "harvest_pending", [w])
    assert len(_events(logs, "harvest_waived")) == 1
    st._log_waivers(state, SID, 9, 3, "harvest_pending", [w])        # 換使用者回合重新計
    assert len(_events(logs, "harvest_waived")) == 2


def test_closing_check_dismiss_word_waives(logs):
    """收尾檢核：近 3 則有 dismiss 詞（先這樣）就不要求；沒有照要求。"""
    mfs = [{"path": CORE}]
    assert wev.detect_missing_aec_emission(DONE, mfs, ["先這樣"], 2, False) is False
    assert wev.detect_missing_aec_emission(DONE, mfs, ["繼續"], 2, False) is True


# ─── 4. CONFLICT_DECLARED_BY_AI ──────────────────────────────────────────────

def _hit(atom, sim):
    return {"atom_name": atom, "score": sim, "text": f"fact of {atom}", "file_path": f"/p/.claude/memory/shared/{atom}.md",
            "confidence": "[觀]", "layer": "shared"}


def _write_check(monkeypatch, hits, labels, declared=None):
    seq = iter(labels)
    monkeypatch.setattr(det, "vector_search", lambda *a, **k: hits)
    monkeypatch.setattr(det, "_classify_match", lambda *a, **k: next(seq))
    return det.run_write_check("incoming fact", None, "shared", declared=declared, title="new-card")


def test_threshold_candidates_need_declaration(logs, monkeypatch):
    """會紅：舊碼複驗一致的 CONTRADICT 直接擋、EXTEND≥0.85 自動改道待審。現在都回 need_declaration 列候選。"""
    out = _write_check(monkeypatch, [_hit("a", 0.9)], ["CONTRADICT", "CONTRADICT"])
    assert out["verdict"] == "need_declaration" and out["detector_verdict"] == "contradict"
    assert [c["atom_name"] for c in out["candidates"]] == ["a"]
    out = _write_check(monkeypatch, [_hit("b", 0.9)], ["EXTEND"])
    assert out["verdict"] == "need_declaration" and out["detector_verdict"] == "extend_overlap"


def test_declared_not_conflict_writes_and_ledgers(logs, monkeypatch):
    """反例：AI 判「不是衝突」→ 照寫（verdict ok），帳上留理由。"""
    decl = [{"of": "a", "verdict": "not_conflict", "why": "舊卡講 A 專案的設定，新卡講工具預設，範圍不同"}]
    out = _write_check(monkeypatch, [_hit("a", 0.9)], ["CONTRADICT", "CONTRADICT"], declared=decl)
    assert out["verdict"] == "ok" and out["declared"][0]["verdict"] == "not_conflict"
    led = _events(logs, "conflict_declared")
    assert led and led[-1]["event"] == "not_conflict" and led[-1]["incoming"] == "new-card"


def test_declared_conflict_blocks_with_primary(logs, monkeypatch):
    decl = {"of": "a", "verdict": "conflict", "why": "同一設定鍵，一張說開一張說關"}
    out = _write_check(monkeypatch, [_hit("a", 0.9)], ["EXTEND"], declared=decl)
    assert out["verdict"] == "contradict" and out["primary"] == "a"


def test_bad_declaration_is_refused(logs, monkeypatch):
    out = _write_check(monkeypatch, [_hit("a", 0.9)], ["EXTEND"],
                       declared=[{"of": "a", "verdict": "not_conflict", "why": "<一句理由>"}, {"of": "zzz", "verdict": "conflict", "why": "x 理由"}])
    assert out["verdict"] == "need_declaration"
    assert "a：why 要寫一句理由" in out["declaration_problem"] and "zzz：不在候選" in out["declaration_problem"]
    assert not _events(logs, "conflict_declared")


def test_contradictory_declarations_for_one_candidate_refused(logs, monkeypatch):
    """反例（codex 一輪）：同一張候選同時宣告 conflict 與 not_conflict → 退回，不取第一條。"""
    decl = [{"of": "a", "verdict": "not_conflict", "why": "範圍不同"}, {"of": "a", "verdict": "conflict", "why": "同鍵相反"}]
    out = _write_check(monkeypatch, [_hit("a", 0.9)], ["EXTEND"], declared=decl)
    assert out["verdict"] == "need_declaration" and "兩種判法" in out["declaration_problem"]


def test_rules_unavailable_still_follows_ai_declaration(logs, monkeypatch):
    """判式載不起來（codex 兩輪）：不退回門檻舊判、也不把沒人判的候選放行——照 AI 的宣告決定，只是不核理由。"""
    real = det._hooks_module

    def broken(name):
        if name == "wg_release_rules":
            raise ImportError("gone")
        return real(name)
    monkeypatch.setattr(det, "_hooks_module", broken)
    hits, labels = [_hit("a", 0.9)], ["CONTRADICT", "CONTRADICT"]
    out = _write_check(monkeypatch, hits, labels)
    assert out["verdict"] == "need_declaration" and out["declaration_unavailable"]
    assert any("without validating" in w for w in out["warnings"])
    out = _write_check(monkeypatch, hits, labels, declared=[{"of": "a", "verdict": "conflict", "why": "同鍵相反"}])
    assert out["verdict"] == "contradict" and out["primary"] == "a"
    out = _write_check(monkeypatch, hits, labels, declared=[{"of": "a", "verdict": "not_conflict", "why": "範圍不同"}])
    assert out["verdict"] == "ok"


def test_below_threshold_extend_is_not_a_candidate(logs, monkeypatch):
    """反例：EXTEND 但相似度 < 0.85 → 不是候選、照寫；帶了宣告也忽略。"""
    out = _write_check(monkeypatch, [_hit("a", 0.7)], ["EXTEND"], declared=[{"of": "a", "verdict": "conflict", "why": "x"}])
    assert out["verdict"] == "ok" and out.get("declaration_ignored") and "candidates" not in out


def test_pull_audit_llm_error_is_candidate_not_contradict(logs, monkeypatch, tmp_path):
    """會紅：舊碼本地模型 ERROR、相似度 ≥0.85 就把報告標 contradict。現在標 candidate 並說明要先判。"""
    (tmp_path / ".git").mkdir()
    atom = {"atom_name": "inc", "content": "# inc\n\n## 知識\n\n- [臨] 某個事實的敘述夠長\n", "path": str(tmp_path / "inc.md"),
            "rel_path": "shared/inc.md", "commit": "abcdef12"}
    monkeypatch.setattr(det, "_collect_changed_atoms", lambda *a, **k: [atom])
    monkeypatch.setattr(det, "_get_last_audit_ts", lambda *a, **k: "2026-10-01T00:00:00Z")
    monkeypatch.setattr(det, "_set_last_audit_ts", lambda *a, **k: None)
    monkeypatch.setattr(det, "_append_merge_history", lambda *a, **k: None)
    monkeypatch.setattr(det, "vector_search", lambda *a, **k: [_hit("old", 0.9)])
    monkeypatch.setattr(det, "_classify_match", lambda *a, **k: "ERROR")
    out = det.run_pull_audit(str(tmp_path))
    assert out["flagged"][0]["verdict"] == "candidate"
    report = Path(out["flagged"][0]["report"]).read_text(encoding="utf-8")
    assert "- Verdict: candidate" in report and "只是相似度候選" in report


def test_conflict_rule_registered_as_entrypoint():
    assert "CONFLICT_DECLARED_BY_AI" in rr.RULES
    assert [r["id"] for r in ep.match_entries("衝突待宣告（這次不寫檔）：x", "mcp_reply")] == ["E40"]


# ─── 5. PROJECT_LITERAL_IS_HINT ──────────────────────────────────────────────

@pytest.fixture
def no_registry(monkeypatch):
    monkeypatch.setattr(rg, "_load_registry", lambda: {"projects": {"a": {"root": r"D:\Work\FooProj"}}})
    monkeypatch.setattr(rg, "_org_root_names", lambda: set())


LITERAL = "提到「此專案」這個詞的規則屬於專案規則，該寫 shared"


def test_org_literal_only_rejects_with_hint_then_declared_passes(logs, no_registry):
    """會紅：舊碼字面「此專案」一律擋、沒有宣告入口。現在擋訊息附寫法，帶 scope_reason 就照寫並留帳。"""
    errs = rg.check_org_write({"title": "scope-分界", "knowledge": [LITERAL]})
    assert errs and "PROJECT_LITERAL_IS_HINT" in "\n".join(errs)
    assert [r["id"] for r in ep.match_entries("\n".join(errs), "mcp_reply")] == ["E41"]
    assert rg.check_org_write({"title": "scope-分界", "knowledge": [LITERAL]},
                              scope_reason="在講「此專案」這個詞本身怎麼判 scope，任何專案都適用") == []
    led = _events(logs, "realm_declared")
    assert led and led[-1]["gate"] == "org" and led[-1]["terms"] == ["此專案"]


def test_project_name_still_rejected_even_with_reason(logs, no_registry):
    """反例：專案名、專案路徑是查得到的事實 → 帶 scope_reason 也照擋、不留宣告帳。"""
    errs = rg.check_org_write({"knowledge": [LITERAL + r"，正本在 D:\Work\FooProj\a.md"]}, scope_reason="跨專案通則")
    assert errs and not _events(logs, "realm_declared")


def test_placeholder_reason_does_not_pass(logs, no_registry):
    assert rg.check_org_write({"knowledge": [LITERAL]}, scope_reason="<一句：為什麼是跨專案的>")
    assert rg.check_org_write({"knowledge": [LITERAL]}, scope_reason="  ")


def test_global_gate_from_project_cwd(logs, no_registry, tmp_path):
    root = tmp_path / "Proj"
    (root / ".git").mkdir(parents=True)
    (root / ".claude" / "memory").mkdir(parents=True)
    err = rg.check_global_write(str(root), title="scope-分界", knowledge=[LITERAL])
    assert err and rg.LITERAL_HINT in err
    assert rg.check_global_write(str(root), title="scope-分界", knowledge=[LITERAL],
                                 scope_reason="在講這個詞本身，跨專案都適用") is None
    assert _events(logs, "realm_declared")[-1]["gate"] == "global"


# ─── 規則表與登錄表 ─────────────────────────────────────────────────────────

def test_four_rules_registered_and_named():
    names = ("CORRECTION_WORDS_ARE_HINTS", "EXTRACT_VETO_NEEDS_JUDGMENT", "CONFLICT_DECLARED_BY_AI", "PROJECT_LITERAL_IS_HINT")
    reg = ep.load_registry()
    registered = {s for r in reg["entrypoints"] for s in r.get("rules") or []}
    assert all(n in rr.RULES and n in registered for n in names)


def test_conflict_declaration_verdict_pure():
    v, got = rr.conflict_declaration_verdict(["a", "b"], [{"of": "a", "verdict": "conflict", "why": "同鍵相反"}])
    assert v.owed and "b：沒宣告" in v.why and got == []
    v, got = rr.conflict_declaration_verdict(["a"], {"of": "a", "verdict": "not_conflict", "why": "範圍不同"})
    assert not v.owed and got[0]["verdict"] == "not_conflict"
