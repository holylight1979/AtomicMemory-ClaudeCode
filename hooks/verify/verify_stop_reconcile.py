"""verify_stop_reconcile.py：Stop 對帳閘（Q6）、收尾欄 j／k（Q13）、量尺閘（Q8）、獨立預算與 overflow。

怎麼跑：set WG_CLAUDE_DIR=<worktree> && python -X utf8 -m pytest -q hooks/verify/verify_stop_reconcile.py
固定輸入：hooks/verify/fixtures/v6/q6/（Bash 輸出、詞表、含量尺欄的表）、q13/（AEC 五檔）。
Q6 反例：無關 PASS（隔壁 session）、舊 turn PASS、非零 exit 的 PASS、標試過沒跑 → 各擋；正例各放。
Q13：缺 j 擋、j 路徑不存在擋、k 空字串擋、k「無」放。
Q8：有量尺沒跑擋、runtime_gate 未就緒擋、跑過 DONE 放、無量尺只提醒。
預算：同 turn 第 3 次放行並寫 guard_log reconcile_overflow＋state reconcile_overflow[sid]。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_verify_ledger as vl  # noqa: E402
import wg_evasion as ev  # noqa: E402
import wg_overview as wo  # noqa: E402
from overview_hub import parse_map, match_row  # noqa: E402
from handlers import stop as st  # noqa: E402

FIX = HOOKS_DIR / "verify" / "fixtures" / "v6"
_SID = "sid-rec"
_CODE = r"c:\proj\hooks\x.py"
_CASE = r"c:\proj\hooks\verify\verify_x.py"
PHRASES = ev.compile_claim_phrases(FIX / "q6" / "phrases.json")


ROOT = Path(r"c:\proj")
_RELATED_CMD = "python -m pytest hooks/verify/verify_x.py"


def _rcpt(turn, verdict="PASS", exit_code=None, cmd=_RELATED_CMD, at="", seq=None, kv=None):
    r = {"turn_seq": turn, "tool": "Bash", "cmd": cmd, "sentinels": [{"name": "X_CHECK", "verdict": verdict, "kv": kv or {}}],
         "exit_code": exit_code, "at": at, "project_root": str(ROOT), "cwd": str(ROOT)}
    if seq is not None:
        r["seq"] = seq
    return r


def _mf(path, turn, session_id=_SID, last_at="", last_seq=None):
    m = {"path": path, "tool": "Edit", "session_id": session_id, "turn_seq": turn, "last_turn_seq": turn}
    if last_at:
        m["last_at"] = last_at
    if last_seq is not None:
        m["last_seq"] = last_seq
    return m


@pytest.fixture()
def driven(monkeypatch):
    """驅動 handle_stop：只留閘控制流；回 drive(text, capsys, state 欄位…) → (stdout, state, guard_log 事件)。"""
    logs: list = []
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [])
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)
    monkeypatch.setattr(st, "_hud_alive", lambda *a, **k: (True, {}))
    monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: None)
    monkeypatch.setattr(st, "pending_gate_reason", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    monkeypatch.setattr(vl, "CLAIM_RES", PHRASES)

    def drive(text, capsys, tool_names=(), **extra):
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: text)
        monkeypatch.setattr(st, "get_current_turn_visible_text",
                            lambda *a, **k: ("", {"turn_tool_names_all": list(tool_names)}))
        state = {"phase": "working", "modified_files": [], "failing_tests": [], "recent_user_prompts": [],
                 "stop_blocked_count": 0, "turn_seq": 5}
        state.update(extra)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        logs.clear()
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, {})
        return capsys.readouterr().out, state, list(logs)

    return drive


# ─── Q6 (a) 說修好 ───────────────────────────────────────────────────────

def test_fixed_claim_with_pass_this_turn_passes(driven, capsys):
    out, _, _ = driven("閘修好了，完成。", capsys, verify_receipts={_SID: [_rcpt(5, cmd="python -X utf8 run_verify.py")]})
    assert "ReconcileGate" not in out


def test_fixed_claim_without_completion_not_gated(driven, capsys):
    """BLOCK 2 ④：沒宣告完成的回覆（純審查／中途）不進閘。"""
    out, _, _ = driven("閘修好了，接著看下一段。", capsys)
    assert "ReconcileGate" not in out


def test_fixed_claim_without_any_pass_blocks(driven, capsys):
    out, state, logs = driven("閘修好了，完成。", capsys)
    assert "[Guardian:ReconcileGate]" in out and "(a)" in out and "沒有任何 PASS" in out
    assert state["reconcile_gate_turn"][_SID] == {"turn": 5, "count": 1}
    assert logs and logs[-1][0] == "reconcile"


def test_unrelated_pass_from_sibling_session_blocks(driven, capsys):
    """反例一：無關 PASS：隔壁 session 的收據不放行本 session。"""
    out, _, _ = driven("閘修好了，完成。", capsys, verify_receipts={"other": [_rcpt(5)]})
    assert "ReconcileGate" in out and "(a)" in out


def test_unrelated_pass_in_same_session_does_not_count(driven, capsys):
    """BLOCK 3：同回合有 PASS 但驗的是別的東西（cmd 沒提到改的檔、不是 verify 路徑、不是量尺）→ 不能背書。"""
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_CODE, 5)],
                       verify_receipts={_SID: [_rcpt(5, cmd="python tools/replay-guard.py pre --prompt p.md --sandbox s")]})
    assert "ReconcileGate" in out and "驗的是" in out and "改的是 x.py" in out
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_CODE, 5), _mf(_CASE, 5)],
                       verify_receipts={_SID: [_rcpt(5, cmd="python -m pytest hooks/verify/verify_x_gate.py")]},
                       anti_evasion_report=_aec(5, j=__file__, k="無"))
    assert "ReconcileGate" not in out


def test_stale_turn_pass_blocks(driven, capsys):
    """反例二：改完後的舊 PASS（turn 3）不算本回合證據。"""
    out, _, _ = driven("閘修好了，完成。", capsys, verify_receipts={_SID: [_rcpt(3)]})
    assert "ReconcileGate" in out and "舊回合的 PASS" in out


def test_pass_with_nonzero_exit_blocks(driven, capsys):
    """反例三：PASS 但 exit≠0。"""
    out, _, _ = driven("閘修好了，完成。", capsys, verify_receipts={_SID: [_rcpt(5, exit_code=1)]})
    assert "ReconcileGate" in out and "exit≠0" in out


def test_pass_with_unknown_exit_passes_with_note(driven, capsys):
    """BLOCK 6：exit=None 的 PASS 放行，但擋訊息（若有其他命中）附註 exit 未知；純放行時不出訊息。"""
    out, _, _ = driven("閘修好了，我量了，完成。", capsys, verify_receipts={_SID: [_rcpt(5)]})
    assert "ReconcileGate" in out and "(b)" in out and "exit 未知" in out


def test_fixed_claim_negated_not_blocked(driven, capsys):
    out, _, _ = driven("還沒修好，先記下原因，完成。", capsys)
    assert "ReconcileGate" not in out


@pytest.mark.parametrize("text", [
    "使用者說已修正，完成。",
    "log 顯示 not fixed，完成。",
    "量過了嗎？完成。",
    "codex 說它修好了，完成。",
])
def test_claim_sentences_from_return_letter_not_blocked(driven, capsys, text):
    """BLOCK 2：轉述／英文否定／疑問不擋。"""
    out, _, _ = driven(text, capsys)
    assert "ReconcileGate" not in out


def test_mixed_sentence_still_claims(driven, capsys):
    """BLOCK 2：「A 已修好，B 尚未修好」否定只取消同子句，A 的宣稱仍要對收據。"""
    out, _, _ = driven("A 已修好，B 尚未修好，完成。", capsys)
    assert "ReconcileGate" in out and "(a)" in out


@pytest.mark.parametrize("text", ["還沒修好但 B 已修好，完成。", "我請 codex 跑了測試後已修正，完成。"])
def test_turn_word_and_own_mark_sentences_still_claim(driven, capsys, text):
    """003-1：轉折詞後另起子句；有「我」的句子即使提到 codex 也是自己的宣稱 → 沒收據就擋。"""
    out, _, _ = driven(text, capsys, tool_names=["Bash"])
    assert "ReconcileGate" in out and "(a)" in out


def test_unrelated_test_file_cannot_vouch(driven, capsys):
    """003-2：改 a.py，PASS 來自 tests/test_b.py 或 check_beta.py → 不算；tests/test_a.py 或 pytest -q 算。"""
    a = r"c:\proj\src\a.py"
    for bad in ("pytest tests/test_b.py", "python check_beta.py"):
        out, _, _ = driven("a 修好了，完成。", capsys, modified_files=[_mf(a, 5), _mf(_CASE, 5)],
                           verify_receipts={_SID: [_rcpt(5, cmd=bad)]}, anti_evasion_report=_aec(5, j=__file__, k="無"))
        assert "ReconcileGate" in out and "對不上" in out, bad
    for good in ("pytest tests/test_a.py", "pytest -q", MEASURE_CMD):
        out, _, _ = driven("a 修好了，完成。", capsys, modified_files=[_mf(a, 5), _mf(_CASE, 5)],
                           verify_receipts={_SID: [_rcpt(5, cmd=good)]}, anti_evasion_report=_aec(5, j=__file__, k="無"))
        assert "ReconcileGate" not in out, good


# ─── Q6 (b) 說量了 ───────────────────────────────────────────────────────

def test_measured_claim_without_done_blocks(driven, capsys):
    out, _, _ = driven("我量了，平均 120 ms，完成。", capsys, verify_receipts={_SID: [_rcpt(5, "PASS")]})
    assert "ReconcileGate" in out and "(b)" in out


def test_measured_claim_with_done_passes(driven, capsys):
    out, _, _ = driven("我量了，平均 120 ms，完成。", capsys, verify_receipts={_SID: [_rcpt(5, "DONE")]})
    assert "ReconcileGate" not in out


# ─── Q6 (c) 標試過沒跑 ────────────────────────────────────────────────────

def test_tried_claim_without_exec_tool_blocks(driven, capsys):
    """反例四：標試過但本回合只有 Read／Edit。"""
    out, _, _ = driven("我跑了測試，完成。", capsys, tool_names=["Read", "Edit"])
    assert "ReconcileGate" in out and "(c)" in out


def test_tried_claim_with_bash_in_turn_passes(driven, capsys):
    out, _, _ = driven("我跑了測試，完成。", capsys, tool_names=["Read", "Bash", "Edit"])
    assert "ReconcileGate" not in out


def test_tried_claim_with_receipt_but_tool_names_lost_passes(driven, capsys):
    """transcript 掉段時工具名為空，但帳本有本回合收據 → 不擋（收據是更強的證據）。"""
    out, _, _ = driven("我跑了測試，完成。", capsys, tool_names=[], verify_receipts={_SID: [_rcpt(5, "FAIL", 1)]})
    assert "ReconcileGate" not in out


# ─── Q6 (d) 改了碼沒驗證 case ────────────────────────────────────────────

def test_completion_with_code_change_and_no_case_no_pass_blocks(driven, capsys):
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CODE, 5)])
    assert "ReconcileGate" in out and "(d)" in out and "沒驗證 case" in out


def test_completion_with_verify_case_modified_passes(driven, capsys):
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CODE, 5), _mf(_CASE, 5)],
                       anti_evasion_report=_aec(5, j="無", k="無"))
    assert "ReconcileGate" not in out


def test_completion_with_pass_but_no_case_now_blocks(driven, capsys):
    """件三反例：改了程式＋有對得上的 PASS、但本回合沒改任何驗證 case → (d) 擋（舊行為以 PASS 代替會放行）。"""
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(r"c:\proj\src\a.py", 5)],
                       verify_receipts={_SID: [_rcpt(5, cmd="pytest tests/test_a.py")]},
                       anti_evasion_report=_aec(5, j=__file__, k="無"))
    assert "ReconcileGate" in out and "(d)" in out and "PASS 不能代替" in out
    assert "或說明為何不需要" not in out and "照【收尾放行確認】問使用者" in out


def test_completion_with_code_and_test_case_modified_passes(driven, capsys):
    """件三正例：改 src/a.py＋改 tests/test_a.py → (d) 不擋；只改 .md → 不擋（見 test_markdown_change_is_not_code_change）。"""
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(r"c:\proj\src\a.py", 5), _mf(r"c:\proj\tests\test_a.py", 5)],
                       anti_evasion_report=_aec(5, j="無", k="無"))
    assert "ReconcileGate" not in out


def test_fixed_claim_still_needs_pass_even_with_case_modified(driven, capsys):
    """件三：(a) 與 (d) 各自判；改了 case 讓 (d) 過，說修好仍要 PASS。"""
    out, _, _ = driven("a 修好了，完成。", capsys, modified_files=[_mf(r"c:\proj\src\a.py", 5), _mf(r"c:\proj\tests\test_a.py", 5)])
    assert "ReconcileGate" in out and "(a)" in out and "(d)" not in out


def test_code_changed_in_older_turn_not_counted(driven, capsys):
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CODE, 2)],
                       anti_evasion_report=_aec(5, j="無", k="無"))
    assert "ReconcileGate" not in out


@pytest.mark.parametrize("name", ["widget.cpp", "Main.java", "main.go", "lib.rs"])
def test_more_languages_count_as_code_change(driven, capsys, name):
    """缺口 7 反例：C++／Java／Go／Rust 改了沒驗證就宣告完成 → (d) 擋（不再只認 .py .js .cs .ts .lua）。"""
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(r"c:\proj\src" + "\\" + name, 5)])
    assert "ReconcileGate" in out and "(d)" in out and name in out


def test_markdown_change_is_not_code_change(driven, capsys):
    """缺口 7 正例：改 .md 不算程式碼，不擋。"""
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(r"c:\proj\docs\readme.md", 5)])
    assert "ReconcileGate" not in out


# ─── 缺口 2：同回合先測後改，舊 PASS 不算修好 ──────────────────────────────────

_W = r"c:\demo\src\widget.py"
_W_CMD = "python -m pytest tests/test_widget.py"
_WC = r"c:\demo\tests\test_widget.py"          # 同回合也改了驗證 case（件三：(d) 只認 case，正例都要帶）


def test_pass_before_last_edit_in_same_turn_blocks(driven, capsys):
    """反例：PASS（seq 3）→ 改 widget.py（seq 5）→ 宣告修好 → 擋，(a) 與 (d) 都指出改完沒重跑。"""
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_W, 5, last_seq=5)],
                       verify_receipts={_SID: [_rcpt(5, cmd=_W_CMD, seq=3)]})
    assert "ReconcileGate" in out and "(a)" in out and "(d)" in out and "widget.py 最後一次修改之前" in out


def test_pass_after_last_edit_in_same_turn_passes(driven, capsys):
    """正例：改（seq 3）→ PASS（seq 5）→ 放行。"""
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_W, 5, last_seq=3), _mf(_WC, 5)],
                       verify_receipts={_SID: [_rcpt(5, cmd=_W_CMD, seq=5)]})
    assert "ReconcileGate" not in out


def test_same_second_edit_and_pass_compares_seq(driven, capsys):
    at = "2026-10-12T10:00:00+08:00"
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_W, 5, last_at=at, last_seq=5)],
                       verify_receipts={_SID: [_rcpt(5, cmd=_W_CMD, at=at, seq=3)]})
    assert "ReconcileGate" in out and "最後一次修改之前" in out
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_W, 5, last_at=at, last_seq=3), _mf(_WC, 5)],
                       verify_receipts={_SID: [_rcpt(5, cmd=_W_CMD, at=at, seq=5)]})
    assert "ReconcileGate" not in out


def test_whole_verification_must_be_after_every_claimed_file(driven, capsys):
    """同一張收據對上多個檔：每個它聲稱對上的檔都要在它之前改完；有一個在它之後改 → 不算。"""
    g = r"c:\demo\src\gadget.py"
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_W, 5, last_seq=2), _mf(g, 5, last_seq=6)],
                       verify_receipts={_SID: [_rcpt(5, cmd="python -X utf8 run_verify.py", seq=4)]})
    assert "ReconcileGate" in out and "gadget.py 最後一次修改之前" in out
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_W, 5, last_seq=2), _mf(g, 5, last_seq=3), _mf(_WC, 5)],
                       verify_receipts={_SID: [_rcpt(5, cmd="python -X utf8 run_verify.py", seq=4)]})
    assert "ReconcileGate" not in out


def test_legacy_edit_record_without_at_or_seq_keeps_old_behavior(driven, capsys):
    """修改紀錄沒有 at／seq（升級前）→ 不比先後，照舊放行。"""
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_W, 5), _mf(_WC, 5)],
                       verify_receipts={_SID: [_rcpt(5, cmd=_W_CMD, seq=3)]})
    assert "ReconcileGate" not in out


# ─── 缺口 3：別專案同名測試的 PASS 不算 ────────────────────────────────────────

def test_pass_from_other_project_root_blocks(driven, capsys, monkeypatch):
    monkeypatch.setattr(vl, "file_root_of", lambda p: "C:/Demo")
    mf = [_mf("C:/Demo/src/widget.py", 5), _mf("C:/Demo/tests/test_widget.py", 5)]
    other = {**_rcpt(5, cmd="python tests/test_widget.py"), "project_root": "C:/Other", "cwd": "C:/Other"}
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=mf, verify_receipts={_SID: [other]})
    assert "ReconcileGate" in out and "C:/Other 跑的，不是改檔所屬的專案根" in out           # 反例
    same = {**other, "project_root": "C:/Demo", "cwd": "C:/Demo"}
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=mf, verify_receipts={_SID: [same]})
    assert "ReconcileGate" not in out                                                       # 正例
    rootless = {**other, "project_root": "", "cwd": ""}
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=mf, verify_receipts={_SID: [rootless]})
    assert "ReconcileGate" not in out                                                       # 收據沒根資訊 → 照舊
    whole = {**other, "cmd": "python -m pytest -q"}
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=mf, verify_receipts={_SID: [whole]})
    assert "ReconcileGate" in out                                                           # 整體驗證也要同根


def test_receipt_root_above_file_root_counts(driven, capsys, monkeypatch):
    """未解 1 裁決：收據根是改檔根的上層（同一棵樹內從上層跑測試）也算；兩根互不包含才擋。"""
    monkeypatch.setattr(vl, "file_root_of", lambda p: "C:/Demo/sub")
    mf = [_mf("C:/Demo/sub/src/widget.py", 5), _mf("C:/Demo/sub/tests/test_widget.py", 5)]
    above = {**_rcpt(5, cmd="python -m pytest sub/tests/test_widget.py"), "project_root": "C:/Demo", "cwd": "C:/Demo"}
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=mf, verify_receipts={_SID: [above]})
    assert "ReconcileGate" not in out                                                       # 正例：上層
    apart = {**above, "project_root": "C:/Other", "cwd": "C:/Other"}
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=mf, verify_receipts={_SID: [apart]})
    assert "ReconcileGate" in out and "不是改檔所屬的專案根" in out                         # 反例：互不包含


# ─── 缺口 1：判定器出例外一律擋，仍吃預算 ──────────────────────────────────────

def _boom(*a, **k):
    raise RuntimeError("boom")


def test_reconcile_judge_exception_blocks(driven, capsys, monkeypatch):
    out, _, _ = driven("閘修好了，完成。", capsys, verify_receipts={_SID: [_rcpt(5, cmd="python -X utf8 run_verify.py")]})
    assert "ReconcileGate" not in out                                                       # 正例：判定器正常 → 放行
    monkeypatch.setattr(st, "reconcile_gate_reason", _boom)
    out, state, logs = driven("閘修好了，完成。", capsys, verify_receipts={_SID: [_rcpt(5, cmd="python -X utf8 run_verify.py")]})
    assert "[Guardian:ReconcileGate] 判定錯誤，一律擋：RuntimeError: boom" in out and "先別宣告完成" in out
    assert state["reconcile_gate_turn"][_SID] == {"turn": 5, "count": 1}
    assert any(g == "reconcile" and "boom" in p.get("error", "") for g, p in logs)


def test_measure_judge_exception_blocks(driven, capsys, monkeypatch):
    kw = dict(modified_files=[_mf(_CODE, 5), _mf(_CASE, 5)], verify_receipts={_SID: [_rcpt(5)]},
              anti_evasion_report=_aec(5, j=__file__, k="無"))
    out, _, _ = driven("全部完成了。", capsys, **kw)
    assert "ReconcileGate" not in out and "MeasureGate" not in out                          # 正例
    monkeypatch.setattr(st, "measure_gate_reason", _boom)
    out, state, _ = driven("全部完成了。", capsys, **kw)
    assert "[Guardian:MeasureGate] 判定錯誤，一律擋：RuntimeError: boom" in out
    assert state["reconcile_gate_turn"][_SID] == {"turn": 5, "count": 1}


def test_judge_exception_third_block_asks_user(driven, capsys, monkeypatch):
    """判定錯誤也吃預算；擋滿後照件一改問使用者（不再 overflow 放行）。"""
    monkeypatch.setattr(st, "reconcile_gate_reason", _boom)
    out, state, logs = driven("閘修好了，完成。", capsys, reconcile_gate_turn={_SID: {"turn": 5, "count": 2}})
    assert "本回合已擋 2 次仍未解：[Guardian:ReconcileGate] 判定錯誤，一律擋" in out and "【收尾放行確認】" in out
    assert "reconcile_overflow" not in state


# ─── Q13 收尾欄 j／k ──────────────────────────────────────────────────────

def _aec(turn, j, k, session_id=_SID):
    rec = json.loads((FIX / "q13" / "aec_full.json").read_text(encoding="utf-8"))
    rec.update({"turn_seq": turn, "session_id": session_id, "severity": "routine", "at": "now",
                "j_evidence_path": j, "k_followups": k})
    return rec


def _q13(name, ledger):
    rec = json.loads((FIX / "q13" / name).read_text(encoding="utf-8"))
    rec["j_evidence_path"] = rec["j_evidence_path"].replace("__LEDGER__", ledger)
    return rec


def test_q13_missing_j_with_receipts_blocks(driven, capsys, tmp_path):
    rec = _aec(5, **{"j": _q13("aec_missing_j.json", "")["j_evidence_path"], "k": "無"})
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5)],
                       verify_receipts={_SID: [_rcpt(5)]}, anti_evasion_report=rec)
    assert "ReconcileGate" in out and "(j)" in out


def test_q13_j_path_not_exists_blocks(driven, capsys):
    rec = _aec(5, j=_q13("aec_bad_j.json", "")["j_evidence_path"], k="無")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5)],
                       verify_receipts={_SID: [_rcpt(5)]}, anti_evasion_report=rec)
    assert "ReconcileGate" in out and "(j)" in out


def test_q13_full_report_with_existing_ledger_passes(driven, capsys, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("{}\n", encoding="utf-8", newline="\n")
    q = _q13("aec_full.json", str(ledger))
    rec = _aec(5, j=q["j_evidence_path"], k=q["k_followups"])
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5)],
                       verify_receipts={_SID: [_rcpt(5)]}, anti_evasion_report=rec)
    assert "ReconcileGate" not in out


def test_q13_empty_k_blocks_even_without_receipts(driven, capsys):
    q = _q13("aec_empty_k.json", "")
    rec = _aec(5, j="無", k=q["k_followups"])
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5)], anti_evasion_report=rec)
    assert "ReconcileGate" in out and "(k)" in out and "空字串" in out


def test_q13_k_with_items_passes(driven, capsys, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("{}\n", encoding="utf-8", newline="\n")
    q = _q13("aec_with_k.json", str(ledger))
    rec = _aec(5, j=q["j_evidence_path"], k=q["k_followups"])
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5)],
                       verify_receipts={_SID: [_rcpt(5)]}, anti_evasion_report=rec)
    assert "ReconcileGate" not in out


def test_legacy_aec_report_without_jk_keys_not_checked(driven, capsys):
    """升級前 emit 的報告沒有 j／k 鍵 → 不拿它擋（post_tool_use 新報告一定有兩鍵）。"""
    rec = _aec(5, j="無", k="")
    rec.pop("j_evidence_path")
    rec.pop("k_followups")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5)],
                       verify_receipts={_SID: [_rcpt(5)]}, anti_evasion_report=rec)
    assert "ReconcileGate" not in out


def test_legacy_modified_entry_without_turn_not_counted_for_rule_d(driven, capsys):
    """升級前的 modified_files entry（無 turn 欄）不觸發 (d)。"""
    out, _, _ = driven("全部完成了。", capsys, modified_files=[{"path": _CODE, "tool": "Edit", "session_id": _SID}])
    assert "ReconcileGate" not in out


def test_q13_sibling_aec_not_checked(driven, capsys):
    """隔壁 session 的報告（session_id 不符）不算本回合 emit：j／k 不檢（ScanReport 閘另擋 emit 本身）。"""
    rec = _aec(5, j="無", k="", session_id="other")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5)],
                       verify_receipts={_SID: [_rcpt(5)]}, anti_evasion_report=rec)
    assert "ReconcileGate" not in out


def test_aec_evidence_missing_pure_function(tmp_path):
    assert vl.aec_evidence_missing("無", False) is False
    assert vl.aec_evidence_missing("無", True) is True
    assert vl.aec_evidence_missing("", True) is True
    f = tmp_path / "e.txt"
    f.write_text("x", encoding="utf-8", newline="\n")
    assert vl.aec_evidence_missing(f"{f} \u2014 帳本", True) is False
    assert vl.aec_evidence_missing(f"{f}\n{tmp_path / 'nope'}", True) is True
    assert vl.aec_followups_missing("") is True and vl.aec_followups_missing("  ") is True
    assert vl.aec_followups_missing("無") is False and vl.aec_followups_missing("x \u2014 y") is False


# ─── 預算：同 turn 擋滿後不放行，改問使用者（件一） ─────────────────────────

def test_third_block_in_same_turn_still_blocks_and_asks_user(driven, capsys):
    """件一反例：舊行為第 3 次放行記 overflow；現在照擋、要 AskUserQuestion【收尾放行確認】，不寫 overflow。"""
    out, state, logs = driven("閘修好了，完成。", capsys, reconcile_gate_turn={_SID: {"turn": 5, "count": 2}})
    assert "[Guardian:ReconcileGate] 本回合已擋 2 次仍未解" in out and "【收尾放行確認】" in out
    assert "「放行這一回合」「繼續擋，先修好」" in out and "原擋訊息" in out and "(a)" in out
    assert "reconcile_overflow" not in state and state["reconcile_gate_turn"][_SID] == {"turn": 5, "count": 3}
    assert [p.get("event") for g, p in logs if g == "reconcile"] == ["exhausted_block"]


def test_budget_resets_on_new_turn(driven, capsys):
    out, state, _ = driven("閘修好了，完成。", capsys, reconcile_gate_turn={_SID: {"turn": 4, "count": 2}})
    assert "ReconcileGate" in out and state["reconcile_gate_turn"][_SID] == {"turn": 5, "count": 1}


def test_gate_not_consuming_shared_stop_budget(driven, capsys):
    _, state, _ = driven("閘修好了，完成。", capsys)
    assert state["stop_blocked_count"] == 0


def test_gate_disabled_by_config(monkeypatch, driven, capsys):
    monkeypatch.setattr(st, "reconcile_cfg", lambda c: {**vl.RECONCILE_DEFAULTS, "enabled": False})
    out, _, _ = driven("閘修好了，完成。", capsys)
    assert "ReconcileGate" not in out


# ─── BLOCK 1：TestFailGate 只認本 session 的 failing_tests ───────────────────────────

def test_failing_tests_isolated_between_sibling_sessions(driven, capsys):
    """A 的紅測（session_id=A）不擋 B 的 Stop；B 自己的紅測才擋；沒蓋 sid 的舊條目不擋。"""
    red_a = {"cmd": "python -m pytest x.py", "summary": "1 failed", "turn_seq": 5, "session_id": "A", "pytest": True}
    legacy = {"cmd": "python -m pytest y.py", "summary": "1 failed", "turn_seq": 5}
    out, _, _ = driven("全部完成了。", capsys, failing_tests=[red_a, legacy], modified_files=[_mf(_CASE, 5)],
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "TestFailGate" not in out
    red_b = {**red_a, "session_id": _SID}
    out, _, _ = driven("全部完成了。", capsys, failing_tests=[red_a, red_b], modified_files=[_mf(_CASE, 5)])
    assert "TestFailGate" in out and "1 項失敗" in out


# ─── Q8 量尺閘 ────────────────────────────────────────────────────────────

ROWS = parse_map((FIX / "q6" / "overview-map.md").read_text(encoding="utf-8"))
MEASURE_CMD = "python -X utf8 run_verify.py"


def _lookup(path):
    row = match_row(path, ROOT, ROWS)
    return (ROOT, row) if row else None


def test_fixture_table_has_measure_column():
    assert ROWS[0]["measure"] == {"method": "全量 verify", "cmd": MEASURE_CMD, "threshold": "全綠"}
    assert ROWS[1]["measure"] == {}


def test_measure_present_not_run_blocks(driven, capsys, monkeypatch):
    monkeypatch.setattr(wo, "_lookup", _lookup)
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5)], anti_evasion_report=_aec(5, "無", "無"))
    assert "[Guardian:MeasureGate]" in out and "hook 共用模組層" in out and MEASURE_CMD in out


def test_measure_done_after_last_edit_passes(driven, capsys, monkeypatch):
    monkeypatch.setattr(wo, "_lookup", _lookup)
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 3)],
                       verify_receipts={_SID: [_rcpt(4, "DONE", 0, cmd=MEASURE_CMD + " --json")]},
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "MeasureGate" not in out


def test_measure_done_before_last_edit_blocks(driven, capsys, monkeypatch):
    """反例：量過但之後又改了部位的檔（DONE 在 turn 2、改在 turn 4）→ 擋。"""
    monkeypatch.setattr(wo, "_lookup", _lookup)
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 4)],
                       verify_receipts={_SID: [_rcpt(2, "DONE", 0, cmd=MEASURE_CMD)]},
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "MeasureGate" in out and "先量後改" in out


def test_measure_before_edit_in_same_turn_blocks(driven, capsys, monkeypatch):
    """BLOCK 4：同回合先量後改：收據 at 早於部位最後修改 at → 擋；at 缺時比 session 內序號；順序對了才放。"""
    monkeypatch.setattr(wo, "_lookup", _lookup)
    early, late = "2026-10-08T10:00:00+08:00", "2026-10-08T10:00:05+08:00"
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5, last_at=late)],
                       verify_receipts={_SID: [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, at=early)]},
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "MeasureGate" in out and "先量後改" in out
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5, last_seq=2)],
                       verify_receipts={_SID: [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, seq=1)]},
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "MeasureGate" in out
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5, last_at=early)],
                       verify_receipts={_SID: [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, at=late)]},
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "MeasureGate" not in out


def test_measure_same_second_receipt_uses_seq(driven, capsys, monkeypatch):
    """003-3：at 同秒：收據 seq 大於修改 seq → 放；小於 → 擋。"""
    monkeypatch.setattr(wo, "_lookup", _lookup)
    same = "2026-10-08T10:00:05+08:00"
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5, last_at=same, last_seq=3)],
                       verify_receipts={_SID: [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, at=same, seq=4)]},
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "MeasureGate" not in out
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5, last_at=same, last_seq=4)],
                       verify_receipts={_SID: [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, at=same, seq=3)]},
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "MeasureGate" in out and "先量後改" in out


def test_measure_receipt_with_cd_not_used(driven, capsys, monkeypatch):
    """003-4：cmd 含 cd 的 DONE 不算，訊息說含 cd；不含的算。"""
    monkeypatch.setattr(wo, "_lookup", _lookup)
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 3)],
                       verify_receipts={_SID: [_rcpt(5, "DONE", 0, cmd="cd c:/other && " + MEASURE_CMD)]},
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "MeasureGate" in out and "含 cd" in out and "專案根直接跑尺" in out
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 3)],
                       verify_receipts={_SID: [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD)]},
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "MeasureGate" not in out


def test_measure_receipt_from_other_root_blocks(driven, capsys, monkeypatch):
    """BLOCK 4：收據的 cwd／project_root 不是該部位的 root → 不算。"""
    monkeypatch.setattr(wo, "_lookup", _lookup)
    r = _rcpt(5, "DONE", 0, cmd=MEASURE_CMD)
    r["project_root"], r["cwd"] = r"c:\other", r"c:\other"
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 3)], verify_receipts={_SID: [r]},
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "MeasureGate" in out and "不是這個部位的 root" in out


def test_measure_failed_run_blocks(driven, capsys, monkeypatch):
    """BLOCK 5：run_verify 失敗輸出（FAIL 或 DONE failed=2 或 exit 1）不能過量尺閘。"""
    monkeypatch.setattr(wo, "_lookup", _lookup)
    for r in (_rcpt(5, "FAIL", 1, cmd=MEASURE_CMD, kv={"cases": "10", "failed": "2"}),
              _rcpt(5, "DONE", 0, cmd=MEASURE_CMD, kv={"cases": "10", "failed": "2"}),
              _rcpt(5, "DONE", 1, cmd=MEASURE_CMD, kv={"cases": "10", "failed": "0"})):
        out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 3)], verify_receipts={_SID: [r]},
                           anti_evasion_report=_aec(5, "無", "無"))
        assert "MeasureGate" in out, r
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 3)],
                       verify_receipts={_SID: [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, kv={"cases": "10", "failed": "0"})]},
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "MeasureGate" not in out


def test_no_measure_part_only_advises(driven, capsys, monkeypatch):
    monkeypatch.setattr(wo, "_lookup", _lookup)
    out, state, logs = driven("全部完成了。", capsys, modified_files=[_mf(r"c:\proj\docs\a.md", 5)],
                              anti_evasion_report=_aec(5, "無", "無"))
    err = capsys.readouterr().err
    assert "MeasureGate" not in out and "ReconcileGate" not in out
    assert state["measure_advised"][_SID] == ["文件層"]
    assert any(g == "measure" and "沒有量尺" in p.get("advisory", "") for g, p in logs)


def test_measure_gate_only_when_claiming_completion(driven, capsys, monkeypatch):
    monkeypatch.setattr(wo, "_lookup", _lookup)
    out, _, _ = driven("繼續看下一段。", capsys, modified_files=[_mf(_CASE, 5)])
    assert "MeasureGate" not in out


def test_runtime_gate_not_ready_blocks_with_reason():
    chains = {"hook 共用模組層": {"runtime_gate": "unity-is-playing --check"}}
    reason, no_measure = vl.measure_gate_reason(
        [_mf(_CASE, 5)], [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD)], 5, _lookup, vl.MEASURE_DEFAULTS,
        chains_of=lambda root: chains, runner=lambda cmd, t, cwd: (False, "runtime_gate exit 1：Editor 不在 Play Mode"))
    assert reason and "未就緒" in reason and "Play Mode" in reason and no_measure == []


def test_runtime_gate_ready_then_done_passes():
    chains = {"hook 共用模組層": {"runtime_gate": "echo ok"}}
    reason, _ = vl.measure_gate_reason(
        [_mf(_CASE, 5)], [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD)], 5, _lookup, vl.MEASURE_DEFAULTS,
        chains_of=lambda root: chains, runner=lambda cmd, t, cwd: (True, ""))
    assert reason is None


def test_run_runtime_gate_real_timeout_and_exit():
    ok, why = vl.run_runtime_gate(f'"{sys.executable}" -c "import sys; sys.exit(3)"', 5)
    assert ok is False and "exit 3" in why
    ok, _ = vl.run_runtime_gate(f'"{sys.executable}" -c "print(1)"', 5)
    assert ok is True
    ok, why = vl.run_runtime_gate(f'"{sys.executable}" -c "import time; time.sleep(3)"', 0.5)
    assert ok is False and "逾時" in why


def test_load_verify_chains_reads_hub_json(tmp_path):
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "overview-hub.json").write_text(json.dumps({"verify_chains": {"p": {"runtime_gate": "x", "run": "y"}}}),
                                         encoding="utf-8", newline="\n")
    assert vl.load_verify_chains(tmp_path) == {"p": {"runtime_gate": "x", "run": "y"}}
    assert vl.load_verify_chains(tmp_path / "nope") == {}


@pytest.fixture()
def hub_layers(tmp_path, monkeypatch):
    """005：verify_chains 走四層合併；回 (公司根, 專案根, 設定 config.json 段的函式)。不吃本機 config 與公司根。"""
    import wg_core
    org, proj = tmp_path / "org", tmp_path / "proj"
    for d in (org, proj):
        (d / ".claude").mkdir(parents=True)
    cfg = {}
    monkeypatch.setattr(wg_core, "load_config", lambda: cfg)
    monkeypatch.setattr(wo, "org_memory_root", lambda: org)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    return org, proj, cfg


def _hub_json(root, data):
    (root / ".claude" / "overview-hub.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_verify_chains_from_company_root_used_by_measure_gate(hub_layers):
    org, proj, _ = hub_layers
    _hub_json(org, {"verify_chains": {"hook 共用模組層": {"runtime_gate": "python org-gate.py"}}})
    assert vl.load_verify_chains(proj) == {"hook 共用模組層": {"runtime_gate": "python org-gate.py"}}   # 專案沒設 → 公司的
    ran = []
    reason, _ = vl.measure_gate_reason([_mf(str(proj / "hooks" / "x.py"), 5)], [], 5, _lookup_at(proj), vl.MEASURE_DEFAULTS,
                                       runner=lambda g, t, c: (ran.append(g), (False, "未就緒"))[1])
    assert ran == ["python org-gate.py"] and "執行環境未就緒：未就緒" in reason                          # MeasureGate 用公司的
    _hub_json(proj, {"verify_chains": {"hook 共用模組層": {"runtime_gate": "python proj-gate.py"}}})
    assert vl.load_verify_chains(proj)["hook 共用模組層"]["runtime_gate"] == "python proj-gate.py"     # 專案覆蓋


def test_verify_chains_config_root_value_and_errors(hub_layers):
    org, proj, cfg = hub_layers
    cfg["overview_hub"] = {"verify_chains": {"p": {"runtime_gate": "cfg-gate"}}}
    assert vl.load_verify_chains(proj) == {"p": {"runtime_gate": "cfg-gate"}}                     # config.json 根層值生效
    _hub_json(proj, {"verify_chain": {}})                                                          # 打錯鍵
    with pytest.raises(ValueError, match="未知的設定鍵「verify_chain」"):
        vl.load_verify_chains(proj)                                                                # 反例：與導讀卡端同樣報錯


# ─── Q8 根層 worktree：認目標 verify 的 pytest DONE，不要求全量 ──────────────

_MAP_BYTES = (FIX / "q6" / "overview-map.md").read_bytes()
_PYTEST_CMD = "python -X utf8 -m pytest -q hooks/verify/verify_x.py"


def _pytest_done(turn, root, exit_code=0, cmd=_PYTEST_CMD):
    """pytest 摘要行 `N passed` 經 sentinel_regex 映射後的收據：PYTEST PASS ＋ PYTEST_MEASURE DONE 兩個哨兵。"""
    return {"turn_seq": turn, "tool": "Bash", "cmd": cmd, "exit_code": exit_code, "at": "",
            "project_root": str(root), "cwd": str(root),
            "sentinels": [{"name": "PYTEST", "verdict": "PASS", "kv": {}},
                          {"name": "PYTEST_MEASURE", "verdict": "DONE", "kv": {}}]}


def _two_roots(tmp_path, same_map=True):
    """live 根（當 CLAUDE_DIR）與 worktree 根各放一張表；same_map=False 時 worktree 的表內容不同（＝一般專案）。"""
    live, wt = tmp_path / "live", tmp_path / "wt"
    for d in (live, wt):
        (d / ".claude").mkdir(parents=True)
    (live / ".claude" / "overview-map.md").write_bytes(_MAP_BYTES)
    extra = "\n| `x/` | 其他 | 無 | 無 | 無 | 無 | 無 |\n".encode("utf-8")
    (wt / ".claude" / "overview-map.md").write_bytes(_MAP_BYTES if same_map else _MAP_BYTES + extra)
    return live, wt


def _lookup_at(root):
    def lookup(path):
        row = match_row(path, root, ROWS)
        return (root, row) if row else None
    return lookup


def test_is_root_worktree_pure_checks(tmp_path):
    live, wt = _two_roots(tmp_path)
    assert vl.is_root_worktree(wt, live) is True
    assert vl.is_root_worktree(live, live) is False                 # 同一目錄不是 worktree
    assert vl.is_root_worktree(tmp_path / "nope", live) is False    # 表不存在
    assert vl.is_root_worktree(wt, tmp_path / "nope") is False
    _, wt2 = _two_roots(tmp_path / "b", same_map=False)
    assert vl.is_root_worktree(wt2, live) is False                  # 表內容不同＝一般專案


_HEAD = "[Guardian:MeasureGate] 改到有量尺的部位，收尾前要跑過那把尺：\n  ✗ "
# 基底 2b15257 hooks/wg_verify_ledger.py 第 800～805 行的兩句原文（非根層 worktree 分支逐字不變）
_BASE_STALE = ("部位【hook 共用模組層】有量尺「全量 verify｜`python -X utf8 run_verify.py`｜全綠」，"
               "最近一次跑尺在這個部位最後一次修改之前（先量後改不算）。"
               "改完再跑一次 `python -X utf8 run_verify.py`（尾行 `<NAME> DONE` 或 `<NAME>_CHECK DONE`，exit 0、failed=0）再收尾。")
_BASE_NONE = ("部位【hook 共用模組層】有量尺「全量 verify｜`python -X utf8 run_verify.py`｜全綠」，"
              "改了 1 個檔（最後在 turn 5）但之後沒有這把尺的 DONE 收據。"
              "跑 `python -X utf8 run_verify.py`（尾行要印 `<NAME> DONE` 或 `<NAME>_CHECK DONE`）再收尾。")
# 004：尺是 run_verify 時，原文兩句之後另起一行提示背景跑的自寫收據（原文本身逐字不變）
_RUNS_HINT = ("\n  run_verify 跑超過 10 分鐘就背景跑：它跑完會自寫收據到 workflow/verify-ledger/_runs/，"
              "改完之後才開始跑、exit 0、failed=0、同一棵樹就認得到（收據不准手寫）。")


def test_non_root_worktree_block_messages_verbatim_as_base(tmp_path, monkeypatch):
    """非根層 worktree 的兩句擋訊息與基底原文逐字相同：一般專案（表不在 CLAUDE_DIR）與 live 根層（root == CLAUDE_DIR）各比一次。"""
    live, _ = _two_roots(tmp_path)
    for root, lookup, claude_dir in ((ROOT, _lookup, live), (live, _lookup_at(live), live)):
        monkeypatch.setattr(vl, "CLAUDE_DIR", claude_dir)
        mod = str(Path(root) / "hooks" / "x.py")
        stale = {**_rcpt(2, "DONE", 0, cmd=MEASURE_CMD), "project_root": str(root), "cwd": str(root)}
        reason, _ = vl.measure_gate_reason([_mf(mod, 5)], [stale], 5, lookup, vl.MEASURE_DEFAULTS)
        assert reason == _HEAD + _BASE_STALE + _RUNS_HINT, reason
        reason, _ = vl.measure_gate_reason([_mf(mod, 5)], [], 5, lookup, vl.MEASURE_DEFAULTS)
        assert reason == _HEAD + _BASE_NONE + _RUNS_HINT, reason


def test_done_receipts_sentinel_name_filter():
    pt = _pytest_done(5, ROOT)
    plain = _rcpt(5, "DONE", 0, cmd=MEASURE_CMD)
    assert vl.done_receipts([pt, plain], sentinel_name="PYTEST_MEASURE") == [pt]
    assert vl.done_receipts([pt, plain]) == [pt, plain]             # 預設＝舊行為


def test_root_worktree_pytest_done_after_edit_passes(tmp_path, monkeypatch):
    live, wt = _two_roots(tmp_path)
    monkeypatch.setattr(vl, "CLAUDE_DIR", live)
    mod = str(wt / "hooks" / "x.py")
    reason, _ = vl.measure_gate_reason([_mf(mod, 5)], [_pytest_done(5, wt)], 5, _lookup_at(wt), vl.MEASURE_DEFAULTS)
    assert reason is None


def test_root_worktree_pytest_done_from_live_root_blocks(tmp_path, monkeypatch):
    live, wt = _two_roots(tmp_path)
    monkeypatch.setattr(vl, "CLAUDE_DIR", live)
    mod = str(wt / "hooks" / "x.py")
    reason, _ = vl.measure_gate_reason([_mf(mod, 5)], [_pytest_done(5, live)], 5, _lookup_at(wt), vl.MEASURE_DEFAULTS)
    assert reason and "根層 worktree" in reason and "不是這個部位的 root" in reason and "不要求全量" in reason


def test_root_worktree_pytest_done_before_edit_blocks(tmp_path, monkeypatch):
    live, wt = _two_roots(tmp_path)
    monkeypatch.setattr(vl, "CLAUDE_DIR", live)
    mod = str(wt / "hooks" / "x.py")
    reason, _ = vl.measure_gate_reason([_mf(mod, 5)], [_pytest_done(2, wt)], 5, _lookup_at(wt), vl.MEASURE_DEFAULTS)
    assert reason and "根層 worktree" in reason and "修改之前" in reason
    reason, _ = vl.measure_gate_reason([_mf(mod, 5)], [_pytest_done(5, wt, exit_code=1)], 5, _lookup_at(wt), vl.MEASURE_DEFAULTS)
    assert reason and "尺沒過" in reason
    reason, _ = vl.measure_gate_reason([_mf(mod, 5)], [], 5, _lookup_at(wt), vl.MEASURE_DEFAULTS)
    assert reason and "沒有這把尺的 DONE 收據" in reason and "PYTEST_MEASURE" in reason


def test_live_root_still_requires_full_measure(tmp_path, monkeypatch):
    """live 根層（root == CLAUDE_DIR）行為一字不變：只有 pytest DONE 不夠，要 run_verify.py 的 DONE。"""
    live, _ = _two_roots(tmp_path)
    monkeypatch.setattr(vl, "CLAUDE_DIR", live)
    mod = str(live / "hooks" / "x.py")
    reason, _ = vl.measure_gate_reason([_mf(mod, 5)], [_pytest_done(5, live)], 5, _lookup_at(live), vl.MEASURE_DEFAULTS)
    assert reason and MEASURE_CMD in reason and "根層 worktree" not in reason
    full = {**_rcpt(5, "DONE", 0, cmd=MEASURE_CMD), "project_root": str(live), "cwd": str(live)}
    reason, _ = vl.measure_gate_reason([_mf(mod, 5)], [full], 5, _lookup_at(live), vl.MEASURE_DEFAULTS)
    assert reason is None


def test_project_worktree_with_different_map_keeps_project_logic(tmp_path, monkeypatch):
    live, wt = _two_roots(tmp_path, same_map=False)
    monkeypatch.setattr(vl, "CLAUDE_DIR", live)
    mod = str(wt / "hooks" / "x.py")
    reason, _ = vl.measure_gate_reason([_mf(mod, 5)], [_pytest_done(5, wt)], 5, _lookup_at(wt), vl.MEASURE_DEFAULTS)
    assert reason and MEASURE_CMD in reason and "根層 worktree" not in reason
    full = {**_rcpt(5, "DONE", 0, cmd=MEASURE_CMD), "project_root": str(wt), "cwd": str(wt)}
    reason, _ = vl.measure_gate_reason([_mf(mod, 5)], [full], 5, _lookup_at(wt), vl.MEASURE_DEFAULTS)
    assert reason is None


# ─── 件一：擋滿後只認使用者放行（AskUserQuestion【收尾放行確認】或使用者打「放行」，都要在最後一次擋之後） ───

import wg_release as rl  # noqa: E402
from handlers.ups_gates import track_turn_prompts  # noqa: E402


def _ask_line(answer, question=f"收尾宣稱對不上，要放行嗎？{rl.RELEASE_TAG}"):
    return json.dumps({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": f'Your questions have been answered: "{question}"="{answer}".'}]},
        "toolUseResult": {"questions": [{"question": question}], "answers": {question: answer}}}, ensure_ascii=False) + "\n"


@pytest.fixture()
def exhausted(driven, tmp_path, monkeypatch):
    """對帳閘已擋滿（count=2）且最後一次擋記在 transcript 的 offset；回 run(after=[行], before=[行], **state) → (out, state, logs)。"""
    tp = tmp_path / "t.jsonl"
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: tp)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")                             # 預設互動；無法互動的案自己改
    monkeypatch.delenv("CLAUDE_COMPANION_JUDGE", raising=False)

    def run(capsys, before=(), after=(), **extra):
        tp.write_text("".join(before), encoding="utf-8")
        offset = tp.stat().st_size
        with open(tp, "a", encoding="utf-8") as f:
            f.write("".join(after))
        base = {"reconcile_gate_turn": {_SID: {"turn": 5, "count": 2}},
                "last_block": {_SID: {"reconcile": {"offset": offset, "prompts": ["原本那句"], "turn": 5}}},
                "turn_prompts": ["原本那句"], "session": {"cwd": str(tmp_path)}}       # 有 cwd 才會去找 transcript
        base.update(extra)
        return driven("閘修好了，完成。", capsys, **base)

    return run


def test_release_answer_after_last_block_releases_once_and_logs(exhausted, capsys, driven):
    out, state, logs = exhausted(capsys, after=[_ask_line(rl.OPT_RELEASE)])
    assert "ReconcileGate" not in out                                                       # 正例：放行一次
    rel = [p for g, p in logs if g == "reconcile" and p.get("event") == "user_release"]
    assert rel and rel[0]["via"] == "ask" and "(a)" in rel[0]["reason"]
    assert state["reconcile_gate_turn"][_SID]["count"] == 0 and state["user_released"][_SID]["reconcile"] == 5
    out, _, _ = driven("閘修好了，完成。", capsys, **{k: state[k] for k in ("reconcile_gate_turn", "user_released", "session")})
    assert "ReconcileGate" not in out                                                       # 這一回合不再擋
    out, _, _ = driven("閘修好了，完成。", capsys, turn_seq=6, user_released=state["user_released"])
    assert "ReconcileGate" in out                                                           # 下一回合照擋


def test_keep_blocking_answer_still_blocks(exhausted, capsys):
    out, _, _ = exhausted(capsys, after=[_ask_line(rl.OPT_KEEP)])
    assert "本回合已擋 2 次仍未解" in out and "【收尾放行確認】" in out


def test_release_answer_before_last_block_does_not_count(exhausted, capsys):
    out, _, _ = exhausted(capsys, before=[_ask_line(rl.OPT_RELEASE)])
    assert "本回合已擋 2 次仍未解" in out


def test_release_answer_without_tag_does_not_count(exhausted, capsys):
    out, _, _ = exhausted(capsys, after=[_ask_line(rl.OPT_RELEASE, question="要放行嗎？")])
    assert "本回合已擋 2 次仍未解" in out


def test_last_tagged_answer_wins(exhausted, capsys):
    out, _, _ = exhausted(capsys, after=[_ask_line(rl.OPT_RELEASE), _ask_line(rl.OPT_KEEP)])
    assert "本回合已擋 2 次仍未解" in out


def test_user_typed_release_after_block_releases(exhausted, capsys):
    out, _, logs = exhausted(capsys, turn_prompts=["原本那句", "好，放行"])
    assert "ReconcileGate" not in out
    assert [p["via"] for g, p in logs if p.get("event") == "user_release"] == ["prompt"]


def test_user_typed_release_before_block_or_negated_does_not_count(exhausted, capsys):
    out, _, _ = exhausted(capsys, turn_prompts=["原本那句"],
                          last_block={_SID: {"reconcile": {"offset": 0, "prompts": ["放行", "原本那句"], "turn": 5}}})
    assert "本回合已擋 2 次仍未解" in out                                                   # 「放行」在擋之前就說了
    out, _, _ = exhausted(capsys, turn_prompts=["原本那句", "不要放行"])
    assert "本回合已擋 2 次仍未解" in out                                                   # 否定句不算


def test_task_notification_with_release_word_does_not_count(exhausted, capsys):
    st_ = {"turn_prompts": ["原本那句"], "turn_open": True}
    track_turn_prompts(st_, "<task-notification>背景任務說：放行</task-notification>")
    out, _, _ = exhausted(capsys, turn_prompts=st_["turn_prompts"])
    assert "本回合已擋 2 次仍未解" in out


def test_new_prompts_alignment_over_sliding_window():
    assert rl.new_prompts(["a", "b"], ["a", "b"]) == []
    assert rl.new_prompts(["a", "b", "c", "d", "e"], ["b", "c", "d", "e", "f"]) == ["f"]
    assert rl.new_prompts(["a"], ["x"]) == ["x"]                                            # 新回合重開
    assert rl.new_prompts([], ["x"]) == ["x"]


def test_shared_budget_sync_block_keeps_force_release(driven, capsys, monkeypatch):
    """003 裁決：共用預算 stop_gate_max_blocks 的閘照舊：一般 sync block 第 3 次強制放行（phase=done），不問使用者。"""
    monkeypatch.setattr(st, "_git_unpushed_roots", lambda mf: [])
    mf = [_mf(r"c:\proj\docs\a.md", 5), _mf(r"c:\proj\docs\b.md", 5)]
    out, state, _ = driven("好了。", capsys, modified_files=mf, stop_blocked_count=0)
    assert "[Workflow Guardian] 2 file(s) modified" in out and state["stop_blocked_count"] == 1     # 沒擋滿：照擋
    out, state, logs = driven("好了。", capsys, modified_files=mf, stop_blocked_count=2)
    assert "Guardian" not in out and "【收尾放行確認】" not in out and state["phase"] == "done"     # 擋滿：照舊放行
    assert not [g for g, _ in logs if g == "sync_block"]


def test_shared_budget_deferral_gate_keeps_skipping_when_exhausted(driven, capsys, monkeypatch):
    monkeypatch.setattr(st, "deferral_gate_reason", lambda *a, **k: "[Guardian:DeferralGate] 把可做的事推給下個 session")
    out, _, _ = driven("好了。", capsys, stop_blocked_count=2)
    assert "DeferralGate" not in out and "【收尾放行確認】" not in out                         # 擋滿：照舊跳過
    out, _, _ = driven("好了。", capsys, stop_blocked_count=0)
    assert "DeferralGate" in out and "本回合已擋" not in out                                # 沒擋滿：照原本的擋


# ─── 003：無法互動情境一律擋到底（不叫它問使用者） ──────────────────────────────

def test_non_interactive_reason_signals(tmp_path):
    tp = tmp_path / "t.jsonl"
    tp.write_text('{"type":"user","entrypoint":"cli"}\n{"type":"assistant","entrypoint":"sdk-cli"}\n', encoding="utf-8")
    assert rl.non_interactive_reason({}, str(tp), env={}) == "headless／SDK（entrypoint=sdk-cli）"           # transcript 欄
    assert rl.non_interactive_reason({}, str(tp), env={"CLAUDE_CODE_ENTRYPOINT": "claude-vscode"}) is None  # 環境變數優先
    assert rl.non_interactive_reason({}, None, env={"CLAUDE_CODE_ENTRYPOINT": "sdk-py"}).startswith("headless")
    assert rl.non_interactive_reason({"agent_id": "a1"}, None, env={"CLAUDE_CODE_ENTRYPOINT": "cli"}) == "子代理 Stop"
    assert rl.non_interactive_reason({"hook_event_name": "SubagentStop"}, None, env={}) == "子代理 Stop"
    assert rl.non_interactive_reason({}, None, env={"CLAUDE_COMPANION_JUDGE": "1"}).startswith("裁判子 session")
    assert rl.non_interactive_reason({}, None, env={"CLAUDE_CODE_ENTRYPOINT": "cli"}) is None              # 互動
    tp.write_text('{"type":"user","entrypoint":"claude-vscode"}\n', encoding="utf-8")
    assert rl.non_interactive_reason({}, str(tp), env={}) is None


def test_headless_exhausted_blocks_without_asking_even_with_release_answer(exhausted, capsys, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    out, _, logs = exhausted(capsys, after=[_ask_line(rl.OPT_RELEASE)], turn_prompts=["原本那句", "放行"])
    assert "[Guardian:ReconcileGate] 無法互動，不能放行：✗ (a)" in out and "headless／SDK（entrypoint=sdk-cli）" in out
    assert "AskUserQuestion" not in out.split("原擋訊息")[0] and "【收尾放行確認】" not in out           # 不叫它問
    assert [p.get("event") for g, p in logs if g == "reconcile"] == ["noninteractive_block"]


def test_headless_before_exhausted_is_ordinary_block(driven, capsys, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    out, _, _ = driven("閘修好了，完成。", capsys)
    assert "收尾宣稱對不上" in out and "無法互動" not in out                                 # 還沒擋滿：照一般擋訊息


# ─── 004：MeasureGate 認 run_verify 自寫收據（_runs/） ───────────────────────────────

_EDIT_AT = "2026-10-12T10:00:00+08:00"          # ＝UTC 02:00:00


def _self_run(started="2026-10-12T02:00:01+00:00", exit_code=0, failed=0, root=str(ROOT), cmd=MEASURE_CMD):
    return {"cmd": cmd, "sentinel": f"VERIFY_CHECK {'DONE' if not failed else 'FAIL'} cases=9 failed={failed}",
            "exit_code": exit_code, "cases": 9, "failed": failed, "cwd": root, "project_root": root,
            "started_at": started, "at": "2026-10-12T02:20:00+00:00", "source": "run_verify_self"}


def _mg(runs, mods=None):
    reason, _ = vl.measure_gate_reason(mods or [_mf(_CASE, 5, last_at=_EDIT_AT, last_seq=7)], [], 5, _lookup,
                                       vl.MEASURE_DEFAULTS, self_runs=lambda: runs)
    return reason


def test_self_run_started_after_edit_passes():
    assert _mg([_self_run()]) is None                                                        # 正例


@pytest.mark.parametrize("run, why", [
    (_self_run(started="2026-10-12T01:59:59+00:00"), "改之前就開始跑"),
    (_self_run(started="2026-10-12T02:00:00+00:00"), "同一秒開始跑：證明不了在修改之後"),
    (_self_run(failed=3), "failed=3"),
    (_self_run(exit_code=1), "exit 1"),
    (_self_run(root="c:/other"), "別的根"),
    (_self_run(cmd="python -m pytest -q hooks/verify"), "不是這把尺"),
])
def test_self_run_counterexamples_block(run, why):
    reason = _mg([run])
    assert reason and "MeasureGate" in reason and "workflow/verify-ledger/_runs/" in reason, why


def test_no_self_run_blocks_with_hint():
    reason = _mg([])
    assert reason and "沒有這把尺的 DONE 收據" in reason and "背景跑" in reason and "收據不准手寫" in reason


def test_self_run_from_sibling_session_counts_and_wraps_through_stop(driven, capsys, monkeypatch):
    """不綁 session：收據沒有 session 欄也算；Stop 端到端走 _load_self_runs。"""
    monkeypatch.setattr(wo, "_lookup", _lookup)
    monkeypatch.setattr(vl, "_load_self_runs", lambda: [_self_run()])
    kw = dict(modified_files=[_mf(_CASE, 5, last_at=_EDIT_AT, last_seq=7)], anti_evasion_report=_aec(5, "無", "無"))
    out, _, _ = driven("全部完成了。", capsys, **kw)
    assert "MeasureGate" not in out
    monkeypatch.setattr(vl, "_load_self_runs", lambda: [])
    out, _, _ = driven("全部完成了。", capsys, **kw)
    assert "MeasureGate" in out                                                              # 反例：沒收據


def test_root_worktree_rule_unchanged_by_self_runs(tmp_path, monkeypatch):
    """根層 worktree 照舊只認 PYTEST_MEASURE；自寫收據不改變它。"""
    live, wt = _two_roots(tmp_path)
    monkeypatch.setattr(vl, "CLAUDE_DIR", live)
    mod = _mf(str(wt / "hooks" / "x.py"), 5, last_at=_EDIT_AT, last_seq=7)
    reason, _ = vl.measure_gate_reason([mod], [], 5, _lookup_at(wt), vl.MEASURE_DEFAULTS,
                                       self_runs=lambda: [_self_run(root=str(wt))])
    assert reason and "根層 worktree" in reason


# ─── 005：SubagentStop 只跑寫碼查核閘、擋到底 ───────────────────────────────────────

@pytest.fixture()
def sub_stop(monkeypatch):
    """驅動 handle_subagent_stop：state 由參數給；回 run(state, last_text, agent_id) → (stdout, guard_log 事件)。"""
    logs: list = []
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    monkeypatch.setattr(vl, "CLAIM_RES", PHRASES)

    def run(capsys, state, last="全部完成了。", agent_id="ag1"):
        monkeypatch.setattr(st, "read_state", lambda sid: state)
        logs.clear()
        with pytest.raises(SystemExit):
            st.handle_subagent_stop({"session_id": _SID, "agent_id": agent_id, "hook_event_name": "SubagentStop",
                                     "last_assistant_message": last}, {})
        return capsys.readouterr().out, list(logs)

    return run


def _sub_state(**extra):
    s = {"turn_seq": 5, "modified_files": [], "verify_receipts": {}}
    s.update(extra)
    return s


def test_subagent_code_change_without_case_blocks_non_interactive(sub_stop, capsys):
    out, logs = sub_stop(capsys, _sub_state(agent_modified_files={"ag1": [_mf(_CODE, 5)]}))
    assert "[Guardian:ReconcileGate] 無法互動，不能放行：✗ (d)" in out and "子代理 Stop" in out
    assert "AskUserQuestion" not in out.split("原擋訊息")[0] and "本回合已擋" not in out          # 不問、不計次
    assert [p["event"] for g, p in logs if g == "reconcile"] == ["subagent_block"]


def test_subagent_read_only_not_gated(sub_stop, capsys):
    out, _ = sub_stop(capsys, _sub_state(agent_modified_files={"other": [_mf(_CODE, 5)]}))
    assert "Guardian" not in out                                                            # 只讀檔（自己沒改檔）→ 不擋


def test_subagent_uses_own_receipts_and_case(sub_stop, capsys):
    key = vl.agent_receipt_key(_SID, "ag1")
    st_ = _sub_state(agent_modified_files={"ag1": [_mf(_CODE, 5), _mf(_CASE, 5)]},
                     verify_receipts={key: [_rcpt(5)], _SID: []})
    out, _ = sub_stop(capsys, st_, last="x 修好了，完成。")
    assert "Guardian" not in out                                                            # 正例：自己的收據＋改了 case
    st_ = _sub_state(agent_modified_files={"ag1": [_mf(_CODE, 5), _mf(_CASE, 5)]},
                     verify_receipts={_SID: [_rcpt(5)]})
    out, _ = sub_stop(capsys, st_, last="x 修好了，完成。")
    assert "(a)" in out                                                                     # 反例：主 session 的收據不替子代理背書


def test_main_session_ignores_agent_bookkeeping(driven, capsys):
    """主 session 行為不變：agent_modified_files／子代理收據鍵不影響主 Stop。"""
    out, _, _ = driven("全部完成了。", capsys, agent_modified_files={"ag1": [_mf(_CODE, 5)]},
                       verify_receipts={vl.agent_receipt_key(_SID, "ag1"): [_rcpt(5)]})
    assert "ReconcileGate" not in out


def test_dispatcher_routes_subagent_stop_and_post_tool_use_tags_agent_edits():
    import dispatcher
    assert dispatcher.HANDLERS["SubagentStop"] == ("handlers.stop", "handle_subagent_stop")
    from handlers import post_tool_use as pt
    s = {"turn_seq": 3}
    pt._note_modified(s, _SID, "c:/p/a.py", "Edit", "ag1")
    pt._note_modified(s, _SID, "c:/p/b.py", "Edit")
    assert [m["path"] for m in s["modified_files"]] == ["c:/p/a.py", "c:/p/b.py"]           # 主帳照舊全記
    assert [m["path"] for m in s["agent_modified_files"]["ag1"]] == ["c:/p/a.py"]            # 子代理另記自己的
    assert s["agent_modified_files"]["ag1"][0]["last_turn_seq"] == 3
