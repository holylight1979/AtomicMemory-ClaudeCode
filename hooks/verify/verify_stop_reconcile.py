"""verify_stop_reconcile.py：Stop 對帳閘（Q6）、收尾欄 j／k（Q13）、驗證範圍閘裡「收據對不對得上宣告的指令」（Q8，原量尺閘案例）、
獨立預算與 overflow。

怎麼跑：set WG_CLAUDE_DIR=<worktree> && python -X utf8 -m pytest -q hooks/verify/verify_stop_reconcile.py
固定輸入：hooks/verify/fixtures/v6/q6/（Bash 輸出、詞表、含量尺欄的表）、q13/（AEC 五檔）。
Q6 反例：無關 PASS（隔壁 session）、舊 turn PASS、非零 exit 的 PASS、標試過沒跑 → 各擋；正例各放。
Q13：缺 j 擋、j 路徑不存在擋、k 空字串擋、k「無」放。
Q8：宣告的範圍項目是一條指令（原本表上的量尺）→ 收據要照原字串、改完之後、同根、跑綠；白名單語法、假哨兵、環境縮範圍、
自寫收據、runtime_gate 未就緒的案例都在這裡（驗證範圍其餘案例在 verify_verify_scope.py）。driven 預設關掉驗證範圍閘
（對帳閘的案例不受它影響），要測它的案帶 scope=True。
預算：同 turn 第 3 次放行並寫 guard_log reconcile_overflow＋state reconcile_overflow[sid]。
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_verify_ledger as vl  # noqa: E402
import wg_verify_scope as vs  # noqa: E402
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


@pytest.fixture(autouse=True)
def _scope_ledger_isolated(monkeypatch, tmp_path):
    """驗證範圍的帳本（結案、漏判）每案各用一份，不讓前一案記的漏判擋到下一案的宣告。"""
    monkeypatch.setattr(vs, "SCOPE_DIR", tmp_path / "verify-scope")


@pytest.fixture(autouse=True)
def _temp_rules_off(monkeypatch):
    """假專案與收據可能落在 pytest tmp：關掉暫存規則（B14 的案自己再開）。"""
    monkeypatch.setenv("WG_TEMP_RULES", "off")


@pytest.fixture(autouse=True)
def _git_budget_generous(monkeypatch):
    """真 git 案例（037／042／043／044／045）在全檔連跑的負載下每次 git 可達 0.7 秒，時間預算不該變成判定：
    一律放寬到 20 秒；要測「預算用完照算改了」的案自己再壓回 0。已刪改檔查去向的預算（VANISH_BUDGET_S，2 秒）同理：
    別的 session 同時跑測試時，0a 的「刪除不欠」案在全檔連跑時紅過一次、單跑綠，時間預算不該變成判定。"""
    monkeypatch.setattr(vl, "GIT_BUDGET_S", 20.0, raising=False)
    monkeypatch.setattr(vl, "REF_BUDGET_S", 20.0, raising=False)
    monkeypatch.setattr(vl, "VANISH_BUDGET_S", 20.0, raising=False)
_REAL_CASE_EXISTS = getattr(vl, "case_exists", None)   # fixture 會把它換成「一律存在」，009-4.5 要用真的


def _rcpt(turn, verdict="PASS", exit_code=None, cmd=_RELATED_CMD, at="", seq=None, kv=None):
    r = {"turn_seq": turn, "tool": "Bash", "cmd": cmd, "sentinels": [{"name": "X_CHECK", "verdict": verdict, "kv": kv or {}}],
         "exit_code": exit_code, "at": at, "project_root": str(ROOT), "cwd": str(ROOT), "env": {}}
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


def _declared(cmd, root=ROOT, key=_SID, lookup=None):
    """宣告驗證範圍＝這一條指令（原量尺閘案例改成「範圍項目是表上那把尺」：收據要照原字串跑），回 state 的 verify_scope 欄。"""
    s = {"turn_seq": 5, "modified_files": []}
    text = vs.declare(s, key, {"action": "verify_scope", "items": [{"target": cmd, "why": "原量尺閘案例：範圍就是這條指令"}]},
                      str(root), {}, lookup=lookup or (lambda p: None))
    assert "收下" in text, text
    return s["verify_scope"]


def _with_case_for(decls, *codes, key=_SID):
    """在最新那份宣告的第一項掛 case_for（(d) 由哪個案例驗的宣告）：fixture 路徑是虛構的，不走收件的存在檢查。"""
    decls[key][-1]["items"][0]["case_for"] = list(codes)
    return decls


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
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)   # 案例路徑是虛構的；存在與否由 009 段用真檔測
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)   # 程式檔路徑也是虛構的；已刪除的程式檔由 040 段用真檔測

    def drive(text, capsys, tool_names=(), hook_input=None, config=None, scope=False, **extra):
        """text=None：用真的 get_last_assistant_text 讀 transcript（017c）；hook_input：hook 輸入另帶的欄位；config：handle_stop 的設定；
        scope：開驗證範圍閘（預設關，對帳閘的案例不受它影響）。"""
        config = {"verify_scope": {"enabled": bool(scope)}, **(config or {})}
        monkeypatch.setattr(st, "get_last_assistant_text",
                            ev.get_last_assistant_text if text is None else (lambda *a, **k: text))
        monkeypatch.setattr(st, "get_current_turn_visible_text",
                            lambda *a, **k: ("", {"turn_tool_names_all": list(tool_names)}))
        state = {"phase": "working", "modified_files": [], "failing_tests": [], "recent_user_prompts": [],
                 "stop_blocked_count": 0, "turn_seq": 5}
        state.update(extra)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        logs.clear()
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": "", **(hook_input or {})}, config)
        cap = capsys.readouterr()
        state["_err"] = cap.err          # 只剩「改了 N 個檔」時底部那行改走 stderr（SYNC_BLOCK_NOT_REPEATED）
        return cap.out, state, list(logs)

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
    assert {k: state["reconcile_gate_turn"][_SID][k] for k in ("turn", "count")} == {"turn": 5, "count": 1}
    assert logs and logs[-1][0] == "reconcile"


def test_fixed_claim_block_does_not_suggest_full_run(driven, capsys):
    """全量已從流程拔掉：(a) 擋訊息講可接受的自寫收據時，不再把「背景全量」當修好的建議做法。舊碼括號寫背景全量 → 紅。"""
    out, _, _ = driven("閘修好了，完成。", capsys)
    assert "(a)" in out and "自寫收據" in out, out                      # 前置：走到列可接受證據的那段訊息
    assert "背景全量" not in out, out


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
        out, _, _ = driven("a 修好了，完成。", capsys, modified_files=[_mf(a, 5), _mf(r"c:\proj\tests\test_a.py", 5)],
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
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_W, 5, last_seq=3), _mf(_WC, 5, last_seq=4)],
                       verify_receipts={_SID: [_rcpt(5, cmd=_W_CMD, seq=5)]})
    assert "ReconcileGate" not in out


def test_same_second_edit_and_pass_compares_seq(driven, capsys):
    at = "2026-10-12T10:00:00+08:00"
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_W, 5, last_at=at, last_seq=5)],
                       verify_receipts={_SID: [_rcpt(5, cmd=_W_CMD, at=at, seq=3)]})
    assert "ReconcileGate" in out and "最後一次修改之前" in out
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_W, 5, last_at=at, last_seq=3),
                                                                _mf(_WC, 5, last_at=at, last_seq=4)],
                       verify_receipts={_SID: [_rcpt(5, cmd=_W_CMD, at=at, seq=5)]})
    assert "ReconcileGate" not in out


def test_whole_verification_must_be_after_every_claimed_file(driven, capsys):
    """同一張收據對上多個檔：每個它聲稱對上的檔都要在它之前改完；有一個在它之後改 → 不算。
    （022 規則 4：整體驗證只涵蓋執行根之下，收據要在 c:\\demo 跑才涵蓋 c:\\demo 的改檔。）"""
    g = r"c:\demo\src\gadget.py"
    whole = lambda seq: {**_rcpt(5, cmd="python -X utf8 run_verify.py", seq=seq),          # noqa: E731
                         "cwd": r"c:\demo", "project_root": r"c:\demo"}
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_W, 5, last_seq=2), _mf(g, 5, last_seq=6)],
                       verify_receipts={_SID: [whole(4)]})
    assert "ReconcileGate" in out and "gadget.py 最後一次修改之前" in out
    out, _, _ = driven("閘修好了，完成。", capsys, modified_files=[_mf(_W, 5, last_seq=2), _mf(g, 5, last_seq=3),
                                                                _mf(_WC, 5, last_seq=4), _mf(r"c:\demo\tests\test_gadget.py", 5, last_seq=4)],
                       verify_receipts={_SID: [whole(5)]})
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
    monkeypatch.setattr(st, "reconcile_gate_parts", _boom)
    out, state, logs = driven("閘修好了，完成。", capsys, verify_receipts={_SID: [_rcpt(5, cmd="python -X utf8 run_verify.py")]})
    assert "[Guardian:ReconcileGate] 判定錯誤，一律擋：RuntimeError: boom" in out and "先別宣告完成" in out
    assert {k: state["reconcile_gate_turn"][_SID][k] for k in ("turn", "count")} == {"turn": 5, "count": 1}
    assert any(g == "reconcile" and "boom" in p.get("error", "") for g, p in logs)


def test_scope_judge_exception_blocks(driven, capsys, monkeypatch):
    kw = dict(modified_files=[_mf(_CODE, 5), _mf(_CASE, 5)], verify_receipts={_SID: [_rcpt(5)]},
              anti_evasion_report=_aec(5, j=__file__, k="無"), verify_scope=_with_case_for(_declared(_RELATED_CMD), _CODE),
              scope=True)
    out, _, _ = driven("全部完成了。", capsys, **kw)
    assert "ReconcileGate" not in out and "VerifyScope" not in out                          # 正例
    monkeypatch.setattr(vs, "gate_reason", _boom)
    out, state, _ = driven("全部完成了。", capsys, **kw)
    assert "[Guardian:VerifyScope] 判定錯誤，一律擋：RuntimeError: boom" in out
    assert {k: state["reconcile_gate_turn"][_SID][k] for k in ("turn", "count")} == {"turn": 5, "count": 1}


def test_judge_exception_third_block_asks_user(driven, capsys, monkeypatch):
    """判定錯誤也吃預算；擋滿後照件一改問使用者（不再 overflow 放行）。"""
    monkeypatch.setattr(st, "reconcile_gate_parts", _boom)
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
    assert "reconcile_overflow" not in state and {k: state["reconcile_gate_turn"][_SID][k] for k in ("turn", "count")} == {"turn": 5, "count": 3}
    assert [p.get("event") for g, p in logs if g == "reconcile"] == ["exhausted_block"]


def test_budget_resets_on_new_turn(driven, capsys):
    out, state, _ = driven("閘修好了，完成。", capsys, reconcile_gate_turn={_SID: {"turn": 4, "count": 2}})
    assert "ReconcileGate" in out and {k: state["reconcile_gate_turn"][_SID][k] for k in ("turn", "count")} == {"turn": 5, "count": 1}


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


def test_003_testfail_message_asks_user_skip_first_and_never_offers_xfail(driven, capsys):
    """003（切入點自評 E08）：TestFailGate 三條出路先問使用者有沒有叫跳過（程式只收引原話的不做行），
    不再寫「標記為已知 regression」——那句會把 AI 帶去加 xfail／skip 讓紅消失。擋的條件不變：有紅測又宣告完成就擋。"""
    red = {"cmd": "python -m pytest tests -q", "summary": "FAILED tests/test_report.py::test_legacy_report", "turn_seq": 5,
           "session_id": _SID, "pytest": True}
    out, _, _ = driven("全部完成了。", capsys, failing_tests=[red], modified_files=[_mf(_CASE, 5)])
    assert "[Guardian:TestFailGate] 測試未綠（1 項失敗），不得宣告完成。" in out
    assert "先看使用者有沒有叫你跳過或先不管這支" in out and "「不做｜<紅的那支測試名>：使用者說「<原句片段>」」" in out
    assert "不准加 skip／xfail、不准只為了變綠改斷言" in out and "收尾別說完成" in out
    # 需求變了、舊斷言不再對是正常情況：指去改舊測試的宣告，不一律禁改斷言（codex 審：跟改舊測試提示矛盾）
    assert "是使用者要的新行為讓舊斷言不再對，先寫「改舊測試｜<測試名>：<為什麼；使用者原話>」再改斷言" in out
    assert "已知 regression" not in out and "降級任務定義" not in out                 # 反例：舊字句
    # 改舊測試｜test_003_testfail_message_asks_user_skip_first_and_never_offers_xfail：派工單件 1 要擋訊息「只認 FAILED／ERROR 開頭的節點行，其他行不得當失敗項」
    msg = st.testfail_message([{"cmd": f"c{i}", "summary": f"第一行\nFAILED t.py::case{i} - x"} for i in range(5)])
    assert "  - t.py::case2（指令：c2）" in msg and "  - t.py::case4（指令：c4）" in msg and "case1" not in msg   # 最後 3 筆
    assert "第一行" not in msg                                     # 失敗項是 FAILED 節點，不是摘要第一行


# ─── Q8 驗證範圍：宣告的項目是一條指令（原量尺閘案例） ───────────────────────────────────

ROWS = parse_map((FIX / "q6" / "overview-map.md").read_text(encoding="utf-8"))
MEASURE_CMD = "python -X utf8 run_verify.py"


def _lookup(path):
    row = match_row(path, ROOT, ROWS)
    return (ROOT, row) if row else None


def test_fixture_table_has_measure_column():
    assert ROWS[0]["measure"] == {"method": "全量 verify", "cmd": MEASURE_CMD, "threshold": "全綠"}
    assert ROWS[1]["measure"] == {}


@pytest.fixture()
def scoped(driven, monkeypatch):
    """改到有量尺的部位（hook 共用模組層）、宣告範圍＝表上那把尺，經 handle_stop 端到端。"""
    monkeypatch.setattr(wo, "_lookup", _lookup)

    def run(capsys, mods, receipts=(), text="全部完成了。", declared=True, **extra):
        kw = dict(modified_files=mods, verify_receipts={_SID: list(receipts)}, anti_evasion_report=_aec(5, "無", "無"),
                  scope=True, **extra)
        if declared:
            kw["verify_scope"] = _declared(MEASURE_CMD, lookup=_lookup)
        return driven(text, capsys, **kw)[0]

    return run


def test_ruler_part_change_without_declaration_offers_ruler_as_reference(scoped, capsys):
    """改到有量尺的部位、沒宣告 → 擋；表上的尺只當參考出現在訊息裡，不是門檻。"""
    out = scoped(capsys, [_mf(_CASE, 5)], declared=False)
    assert "[Guardian:VerifyScope]" in out and "SCOPE_DECLARED_FOR_CHANGE" in out
    assert "參考（不必全跑）" in out and MEASURE_CMD in out and "hook 共用模組層" in out


def test_declared_command_run_verbatim_after_edit_passes(scoped, capsys):
    """013：宣告的指令要原樣跑（多帶 --json 不算）。"""
    assert "VerifyScope" not in scoped(capsys, [_mf(_CASE, 3)], [_rcpt(4, "DONE", 0, cmd=MEASURE_CMD)])
    out = scoped(capsys, [_mf(_CASE, 3)], [_rcpt(4, "DONE", 0, cmd=MEASURE_CMD + " --json")])
    assert "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in out and "沒有跑這一項的收據" in out


def test_declared_command_run_before_last_edit_blocks(scoped, capsys):
    """反例：跑過但之後又改了（收據 turn 2、改在 turn 4）→ 擋。"""
    out = scoped(capsys, [_mf(_CASE, 4)], [_rcpt(2, "DONE", 0, cmd=MEASURE_CMD)])
    assert "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in out and "之前" in out


def test_declared_command_before_edit_in_same_turn_blocks(scoped, capsys):
    """BLOCK 4：同回合先跑後改：收據 at 早於最後修改 at → 擋；at 缺時比 session 內序號；順序對了才放。"""
    early, late = "2026-10-08T10:00:00+08:00", "2026-10-08T10:00:05+08:00"
    out = scoped(capsys, [_mf(_CASE, 5, last_at=late)], [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, at=early)])
    assert "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in out and "之前" in out
    assert "VerifyScope" in scoped(capsys, [_mf(_CASE, 5, last_seq=2)], [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, seq=1)])
    assert "VerifyScope" not in scoped(capsys, [_mf(_CASE, 5, last_at=early)],
                                       [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, at=late)])


def test_declared_command_same_second_receipt_uses_seq(scoped, capsys):
    """003-3：at 同秒：收據 seq 大於修改 seq → 放；小於 → 擋。"""
    same = "2026-10-08T10:00:05+08:00"
    assert "VerifyScope" not in scoped(capsys, [_mf(_CASE, 5, last_at=same, last_seq=3)],
                                       [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, at=same, seq=4)])
    out = scoped(capsys, [_mf(_CASE, 5, last_at=same, last_seq=4)], [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, at=same, seq=3)])
    assert "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in out and "之前" in out


def test_declared_command_receipt_with_cd(scoped, capsys):
    """開頭單一絕對路徑的 `cd <根> && 指令` 認得出根：是宣告的根就算、別的根不算。`;` 串的絕對路徑 cd
    也算（RECEIPT_NO_FORGERY_CHECK）；真的換到別的目錄跑（相對路徑 cd、cd 在後面）就不是宣告那一項。"""
    mods = [_mf(_CASE, 3)]
    assert "VerifyScope" not in scoped(capsys, mods, [_rcpt(5, "DONE", 0, cmd="cd c:/proj; " + MEASURE_CMD)])
    for moved in ("cd sub && " + MEASURE_CMD, "cd c:/proj && cd sub && " + MEASURE_CMD):    # 真的換到別處跑：不是宣告那一項
        assert "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in scoped(capsys, mods, [_rcpt(5, "DONE", 0, cmd=moved)]), moved
    assert "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in scoped(capsys, mods, [_rcpt(5, "DONE", 0, cmd="cd c:/other && " + MEASURE_CMD)])
    for ok in (MEASURE_CMD, "cd c:\\proj && " + MEASURE_CMD, "cd /c/proj && " + MEASURE_CMD + " 2>&1 | tail -5"):
        assert "VerifyScope" not in scoped(capsys, mods, [_rcpt(5, "DONE", 0, cmd=ok)]), ok


def test_declared_command_receipt_from_other_root_blocks(scoped, capsys):
    """BLOCK 4：收據的 cwd／project_root 不是宣告那棵樹 → 不算。"""
    r = _rcpt(5, "DONE", 0, cmd=MEASURE_CMD)
    r["project_root"], r["cwd"] = r"c:\other", r"c:\other"
    assert "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in scoped(capsys, [_mf(_CASE, 3)], [r])


def test_declared_command_failed_run_blocks(scoped, capsys):
    """BLOCK 5：失敗輸出（FAIL、DONE failed=2、exit 1）不算。"""
    for r in (_rcpt(5, "FAIL", 1, cmd=MEASURE_CMD, kv={"cases": "10", "failed": "2"}),
              _rcpt(5, "DONE", 0, cmd=MEASURE_CMD, kv={"cases": "10", "failed": "2"}),
              _rcpt(5, "DONE", 1, cmd=MEASURE_CMD, kv={"cases": "10", "failed": "0"})):
        out = scoped(capsys, [_mf(_CASE, 3)], [r])
        assert "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in out and "紅" in out, r
    assert "VerifyScope" not in scoped(capsys, [_mf(_CASE, 3)],
                                       [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, kv={"cases": "10", "failed": "0"})])


def test_scope_gate_judged_without_completion_claim(scoped, capsys):
    """009-4.1：驗證範圍不看措辭：改了沒跑，回覆不宣告完成也擋。"""
    out = scoped(capsys, [_mf(_CASE, 5)], text="繼續看下一段。")
    assert "VerifyScope" in out and st.ASK_HINT in out
    assert "VerifyScope" not in scoped(capsys, [_mf(_CASE, 3)], [_rcpt(4, "DONE", 0, cmd=MEASURE_CMD)], text="繼續看下一段。")


def _scope_gate(mods, receipts=(), cmd=MEASURE_CMD, lookup=_lookup, self_runs=(), **kw):
    """直接呼叫驗證範圍閘（宣告＝cmd 這條指令）；回擋訊息或 None。"""
    state = {"turn_seq": 5, "modified_files": [], "verify_scope": _declared(cmd, lookup=lookup)}
    reason, _ = vs.gate_reason(state, _SID, list(mods), list(receipts), vl.reconcile_cfg({}), lookup, vs.DEFAULTS,
                               self_runs=self_runs, **kw)
    return reason


def test_runtime_gate_not_ready_blocks_with_reason():
    """還欠收據時才探環境（已有合格收據就不跑 runtime_gate，見 test_013_w2）；量不了 → 擋並說原因。"""
    chains = {"hook 共用模組層": {"runtime_gate": "unity-is-playing --check"}}
    reason = _scope_gate([_mf(_CASE, 5)], chains_of=lambda root: chains,
                         runner=lambda cmd, t, cwd: (False, "runtime_gate exit 1：Editor 不在 Play Mode"))
    assert reason and "未就緒" in reason and "Play Mode" in reason


def test_runtime_gate_ready_then_done_passes():
    chains = {"hook 共用模組層": {"runtime_gate": "echo ok"}}
    assert _scope_gate([_mf(_CASE, 5)], [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD)], chains_of=lambda root: chains,
                       runner=lambda cmd, t, cwd: (True, "")) is None


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


def test_verify_chains_from_company_root_used_by_scope_gate(hub_layers):
    org, proj, _ = hub_layers
    _hub_json(org, {"verify_chains": {"hook 共用模組層": {"runtime_gate": "python org-gate.py"}}})
    assert vl.load_verify_chains(proj) == {"hook 共用模組層": {"runtime_gate": "python org-gate.py"}}   # 專案沒設 → 公司的
    ran = []
    reason = _scope_gate([_mf(str(proj / "hooks" / "x.py"), 5)], lookup=_lookup_at(proj),
                         runner=lambda g, t, c: (ran.append(g), (False, "未就緒"))[1])
    assert ran == ["python org-gate.py"] and "驗證環境未就緒：未就緒" in reason                          # 驗證範圍閘用公司的
    _hub_json(proj, {"verify_chains": {"hook 共用模組層": {"runtime_gate": "python proj-gate.py"}}})
    assert vl.load_verify_chains(proj)["hook 共用模組層"]["runtime_gate"] == "python proj-gate.py"     # 專案覆蓋


def test_verify_chains_config_root_value_and_errors(hub_layers):
    org, proj, cfg = hub_layers
    cfg["overview_hub"] = {"verify_chains": {"p": {"runtime_gate": "cfg-gate"}}}
    assert vl.load_verify_chains(proj) == {"p": {"runtime_gate": "cfg-gate"}}                     # config.json 根層值生效
    _hub_json(proj, {"verify_chain": {}})                                                          # 打錯鍵
    with pytest.raises(ValueError, match="未知的設定鍵「verify_chain」"):
        vl.load_verify_chains(proj)                                                                # 反例：與導讀卡端同樣報錯


# ─── Q8 檔案項目：pytest 收據要真的跑過那支、在它那棵樹（原根層 worktree 量尺案例） ──────────────

_MAP_BYTES = (FIX / "q6" / "overview-map.md").read_bytes()
_PYTEST_CMD = "python -X utf8 -m pytest -q hooks/verify/verify_x.py"


def _pytest_done(turn, root, exit_code=0, cmd=_PYTEST_CMD):
    """pytest 摘要行 `N passed` 經 sentinel_regex 映射後的收據：PYTEST PASS ＋ PYTEST_MEASURE DONE 兩個哨兵。"""
    return {"turn_seq": turn, "tool": "Bash", "cmd": cmd, "exit_code": exit_code, "at": "", "env": {},
            "project_root": str(root), "cwd": str(root),
            "sentinels": [{"name": "PYTEST", "verdict": "PASS", "kv": {}},
                          {"name": "PYTEST_MEASURE", "verdict": "DONE", "kv": {}}]}


def _two_roots(tmp_path, same_map=True):
    """live 根（當 CLAUDE_DIR）與 worktree 根各放一張表；same_map=False 時 worktree 的表內容不同（工作 session 改了部位表）。"""
    live, wt = tmp_path / "live", tmp_path / "wt"
    for d in (live, wt):
        (d / ".claude").mkdir(parents=True)
    (live / ".claude" / "overview-map.md").write_bytes(_MAP_BYTES)
    extra = "\n| `x/` | 其他 | 無 | 無 | 無 | 無 | 無 |\n".encode("utf-8")
    (wt / ".claude" / "overview-map.md").write_bytes(_MAP_BYTES if same_map else _MAP_BYTES + extra)
    adm = live / ".git" / "worktrees" / "wt"                                       # 結構同真 worktree（git worktree add 寫的同一組檔）
    adm.mkdir(parents=True)
    (adm / "gitdir").write_text(f"{wt / '.git'}\n", encoding="utf-8")
    (adm / "commondir").write_text("../..\n", encoding="utf-8")
    (wt / ".git").write_text(f"gitdir: {adm}\n", encoding="utf-8")
    return live, wt


def _lookup_at(root):
    def lookup(path):
        row = match_row(path, root, ROWS)
        return (root, row) if row else None
    return lookup


def _path_scope_gate(tree):
    """tree 底下放 hooks/x.py 與 hooks/verify/verify_x.py，宣告範圍＝hooks/verify/verify_x.py（檔案項目），改了 hooks/x.py；
    回 gate(收據們) → 驗證範圍閘的擋訊息或 None（原「根層 worktree 認 pytest DONE」案例改成檔案項目要真的跑過那支）。"""
    (tree / "hooks" / "verify").mkdir(parents=True, exist_ok=True)
    (tree / "hooks" / "x.py").write_text("X = 1\n", encoding="utf-8")
    (tree / "hooks" / "verify" / "verify_x.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    s = {"turn_seq": 5, "modified_files": []}
    text = vs.declare(s, _SID, {"action": "verify_scope", "items": [{"target": "hooks/verify/verify_x.py", "why": "直接測 x.py"}]},
                      str(tree), {}, lookup=_lookup_at(tree))
    assert "收下" in text, text
    mods = [_mf(str(tree / "hooks" / "x.py"), 5)]
    return lambda receipts: vs.gate_reason(s, _SID, mods, list(receipts), vl.reconcile_cfg({}), _lookup_at(tree),
                                           vs.DEFAULTS)[0]


def test_done_receipts_sentinel_name_filter():
    pt = _pytest_done(5, ROOT)
    plain = _rcpt(5, "DONE", 0, cmd=MEASURE_CMD)
    assert vl.done_receipts([pt, plain], sentinel_name="PYTEST_MEASURE") == [pt]
    assert vl.done_receipts([pt, plain]) == [pt, plain]             # 預設＝舊行為


def test_file_item_takes_pytest_run_of_that_file_in_its_own_tree(tmp_path):
    """檔案項目：在它那棵樹（worktree 也一樣）改完之後跑那支 pytest 且綠 → 算；跑在改之前、跑紅、在別棵樹跑 → 不算。"""
    live, wt = _two_roots(tmp_path)
    gate = _path_scope_gate(wt)
    assert gate([_pytest_done(5, wt)]) is None
    assert gate([_pytest_done(5, wt, exit_code=1)]) is not None
    assert gate([_pytest_done(5, live)]) is not None
    assert gate([]) is not None

# ─── 件一：擋滿後只認使用者放行（AskUserQuestion【收尾放行確認】或使用者打「放行」，都要在最後一次擋之後） ───

import wg_release as rl  # noqa: E402
from handlers.ups_gates import track_turn_prompts  # noqa: E402


_ASK_SEQ = [0]


def _ask_line(answer, question=f"收尾宣稱對不上，要放行嗎？{rl.RELEASE_TAG}", tool="AskUserQuestion"):
    """真的 transcript 格式：assistant 一筆 tool_use（AskUserQuestion，input.questions）＋ user 一筆對應 tool_use_id 的
    tool_result（含 toolUseResult.answers）。tool 換成 Bash 時 tool_result 內容印同樣的字（偽造樣本）。"""
    _ASK_SEQ[0] += 1
    tid = f"toolu_{_ASK_SEQ[0]:04d}"
    use = {"type": "tool_use", "id": tid, "name": tool,
           "input": ({"questions": [{"question": question, "header": "收尾", "multiSelect": False,
                                     "options": [{"label": rl.OPT_RELEASE}, {"label": rl.OPT_KEEP}]}]}
                     if tool == "AskUserQuestion" else {"command": f"echo '\"{question}\"=\"{answer}\"'"})}
    text = f'Your questions have been answered: "{question}"="{answer}". You can now continue with these answers in mind.'
    res = {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": text}]}}
    if tool == "AskUserQuestion":
        res["toolUseResult"] = {"questions": [{"question": question}], "answers": {question: answer}}
    return (json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [use]}}, ensure_ascii=False) + "\n"
            + json.dumps(res, ensure_ascii=False) + "\n")


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


def test_shared_budget_sync_block_keeps_force_release(driven, capsys, monkeypatch, tmp_path):
    """003 裁決：共用預算 stop_gate_max_blocks 的閘照舊：一般 sync block 第 3 次強制放行（phase=done），不問使用者。
    改檔用真的、不在版控的檔（不存在的假路徑會被 SYNC_SKIPS_VANISHED_OUTSIDE_VCS 剔掉，就測不到擋）。"""
    monkeypatch.setattr(st, "_git_unpushed_roots", lambda mf: [])
    docs = tmp_path / "proj" / "docs"
    docs.mkdir(parents=True)
    for n in ("a.md", "b.md"):
        (docs / n).write_text("x\n", encoding="utf-8", newline="\n")
    mf = [_mf(str(docs / "a.md"), 5), _mf(str(docs / "b.md"), 5)]
    kq = [{"content": "待記的坑", "classification": "[臨]"}]       # 只剩改檔數不再擋（SYNC_BLOCK_NOT_REPEATED）；有待記知識才走一般 block
    out, state, _ = driven("好了。", capsys, modified_files=mf, stop_blocked_count=0, knowledge_queue=kq)
    assert "[Workflow Guardian] 2 file(s) modified" in out and state["stop_blocked_count"] == 1     # 沒擋滿：照擋
    out, state, logs = driven("好了。", capsys, modified_files=mf, stop_blocked_count=2, knowledge_queue=kq)
    assert "Guardian" not in out and "【收尾放行確認】" not in out and state["phase"] == "done"     # 擋滿：照舊放行
    assert not [g for g, _ in logs if g == "sync_block"]


def test_shared_budget_deferral_gate_keeps_skipping_when_exhausted(driven, capsys, monkeypatch):
    monkeypatch.setattr(st, "deferral_gate_reason", lambda *a, **k: "[Guardian:DeferralGate] 把可做的事推給下個 session")
    out, _, _ = driven("好了。", capsys, stop_blocked_count=2, need_goal_code_decl_turn=5)   # 本回合宣告了寫碼樹
    assert "DeferralGate" not in out and "【收尾放行確認】" not in out                         # 擋滿：照舊跳過
    out, _, _ = driven("好了。", capsys, stop_blocked_count=0, need_goal_code_decl_turn=5)
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


# ─── 004：驗證範圍認 run_verify 自寫收據（_runs/；範圍大到要背景跑時） ───────────────────────────────

_EDIT_AT = "2026-10-12T10:00:00+08:00"          # ＝UTC 02:00:00


def _self_run(started="2026-10-12T02:00:01+00:00", exit_code=0, failed=0, root=str(ROOT), cmd=MEASURE_CMD, env=None):
    return {"cmd": cmd, "sentinel": f"VERIFY_CHECK {'DONE' if not failed else 'FAIL'} cases=9 failed={failed}",
            "exit_code": exit_code, "cases": 9, "failed": failed, "cwd": root, "project_root": root,
            "started_at": started, "at": "2026-10-12T02:20:00+00:00", "source": "run_verify_self",
            "env": {} if env is None else env}


def _mg(runs, mods=None):
    """宣告範圍＝run_verify 整體（指令項目），只有背景跑的自寫收據。"""
    return _scope_gate(mods or [_mf(_CASE, 5, last_at=_EDIT_AT, last_seq=7)], self_runs=runs)


def test_self_run_started_after_edit_passes():
    assert _mg([_self_run()]) is None                                                        # 正例


@pytest.mark.parametrize("run, why", [
    (_self_run(started="2026-10-12T01:59:59+00:00"), "改之前就開始跑"),
    (_self_run(started="2026-10-12T02:00:00+00:00"), "同一秒開始跑：證明不了在修改之後"),
    (_self_run(failed=3), "failed=3"),
    (_self_run(exit_code=1), "exit 1"),
    (_self_run(root="c:/other"), "別的根"),
    (_self_run(cmd="python -m pytest -q hooks/verify"), "不是宣告的那條指令"),
])
def test_self_run_counterexamples_block(run, why):
    reason = _mg([run])
    assert reason and "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in reason and "背景跑的要等它寫完自寫收據" in reason, why


def test_self_run_covers_file_items_under_its_tree(tmp_path):
    """路徑項目：run_verify 整體的自寫收據涵蓋受測樹全部；只跑某一組（argv 點名 tools/verify）只涵蓋那一組。"""
    _, wt = _two_roots(tmp_path)
    (wt / "tools" / "verify").mkdir(parents=True)
    gate = _path_scope_gate(wt)                                                             # 宣告 hooks/verify/verify_x.py
    later = "2099-01-01T00:00:00+00:00"                                                     # 晚於任何修改
    whole = {**_self_run(root=str(wt), started=later), "argv": ["python", "-X", "utf8", "run_verify.py"]}
    tools_only = {**_self_run(root=str(wt), started=later), "argv": ["python", "-m", "pytest", "-q", "tools/verify"]}
    mods = [_mf(str(wt / "hooks" / "x.py"), 5, last_at=_EDIT_AT, last_seq=7)]
    item = {"kind": "file", "abs": vl._abs_target("", str(wt / "hooks" / "verify" / "verify_x.py")), "root": str(wt)}
    assert vl.scope_item_status(item, [], mods, [whole])[0] is True
    assert vl.scope_item_status(item, [], mods, [tools_only])[0] is False
    assert gate([]) is not None                                                             # 沒有 session 收據 → 擋


def test_self_run_from_sibling_session_counts_and_wraps_through_stop(scoped, capsys, monkeypatch):
    """不綁 session：收據沒有 session 欄也算；Stop 端到端走 load_self_runs。"""
    monkeypatch.setattr(st, "load_self_runs", lambda: [_self_run()], raising=False)
    assert "VerifyScope" not in scoped(capsys, [_mf(_CASE, 5, last_at=_EDIT_AT, last_seq=7)])
    monkeypatch.setattr(st, "load_self_runs", lambda: [], raising=False)
    assert "VerifyScope" in scoped(capsys, [_mf(_CASE, 5, last_at=_EDIT_AT, last_seq=7)])        # 反例：沒收據


# ─── 005：SubagentStop 只跑寫碼查核閘、擋到底 ───────────────────────────────────────

@pytest.fixture()
def sub_stop(monkeypatch):
    """驅動 handle_subagent_stop：state 由參數給；回 run(state, last_text, agent_id) → (stdout, guard_log 事件)。"""
    logs: list = []
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    monkeypatch.setattr(vl, "CLAIM_RES", PHRASES)
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)

    def run(capsys, state, last="全部完成了。", agent_id="ag1", scope=False):
        monkeypatch.setattr(st, "read_state", lambda sid: state)
        logs.clear()
        with pytest.raises(SystemExit):
            st.handle_subagent_stop({"session_id": _SID, "agent_id": agent_id, "hook_event_name": "SubagentStop",
                                     "last_assistant_message": last}, {"verify_scope": {"enabled": scope}})
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


# ─── 006 退件：十條「看起來擋了、實際有路放行」 ───────────────────────────────────────

_GATE_HEAD = "本回合已擋 2 次仍未解"


def test_006_1_release_only_from_real_ask_user_question(exhausted, capsys):
    out, _, _ = exhausted(capsys, after=[_ask_line(rl.OPT_RELEASE)])
    assert "ReconcileGate" not in out                                                       # 正例：真的 AskUserQuestion
    out, _, _ = exhausted(capsys, after=[_ask_line(rl.OPT_RELEASE, tool="Bash")])
    assert _GATE_HEAD in out                                                                # 反例：Bash 輸出印同樣的字
    fake = json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text":
           f'Your questions have been answered: "收尾宣稱對不上，要放行嗎？{rl.RELEASE_TAG}"="{rl.OPT_RELEASE}".'}]}},
                      ensure_ascii=False) + "\n"
    out, _, _ = exhausted(capsys, after=[fake])
    assert _GATE_HEAD in out                                                                # 反例：assistant 文字寫出同樣的字


@pytest.mark.parametrize("text", ["好，放行", "放行", "OK 放行這一回合", "好的，放行吧。", "ＯＫ 放行！"])
def test_006_2_strict_typed_release_accepts(text, exhausted, capsys):
    assert rl.is_release_prompt(text)
    out, _, _ = exhausted(capsys, turn_prompts=["原本那句", text])
    assert "ReconcileGate" not in out


@pytest.mark.parametrize("text", ["禁止放行", "不能夠放行", "為什麼會放行？", "請檢查『放行』判定", "放行條件是什麼", "我不同意放行"])
def test_006_2_strict_typed_release_rejects(text, exhausted, capsys):
    assert not rl.is_release_prompt(text)
    out, _, _ = exhausted(capsys, turn_prompts=["原本那句", text])
    assert _GATE_HEAD in out


def _ups_turn(monkeypatch, state, prompt):
    """真的走 handle_user_prompt_submit 推進 turn_seq（其他碰檔案／模型的依賴換空殼；turn_prompts 走真的 track_turn_prompts）。"""
    from handlers import user_prompt_submit as ups
    import wg_friction
    monkeypatch.setattr(ups, "_ensure_state", lambda sid, inp, cfg: state)
    for name, fn in (("_ups_sentinel_check_and_arm", lambda *a: None), ("_ups_sentinel_clear", lambda sid: None),
                     ("build_context", lambda *a: None), ("_maybe_spawn_failure_extraction", lambda *a: None),
                     ("_update_topic_tracker", lambda *a: None),
                     ("reconcile_injection_after_trim", lambda *a: []), ("write_state", lambda sid, st: None),
                     ("output_json", lambda d: None), ("output_nothing", lambda: None)):
        monkeypatch.setattr(ups, name, fn)
    monkeypatch.setattr(ups, "run_pre_gates", lambda sid, st, cfg, clean, low, lines: track_turn_prompts(st, clean))
    monkeypatch.setattr(ups, "collect_matched_atoms", lambda *a: ([], {}, [], [], {}, [], "general", {}))
    monkeypatch.setattr(ups, "assemble_injection", lambda *a, **k: ([], {}))
    monkeypatch.setattr(ups, "_truncate_context_by_activation", lambda lines, *a: lines)
    monkeypatch.setattr(wo, "on_prompt", lambda *a, **k: None)
    monkeypatch.setattr(wg_friction, "record_correction", lambda *a: None)
    ups.handle_user_prompt_submit({"session_id": _SID, "prompt": prompt, "transcript_path": ""}, {"sync_keywords": []})


def test_006_3_pending_release_carries_over_turns(exhausted, capsys, monkeypatch):
    out, state, _ = exhausted(capsys)                                                       # turn 5 擋滿
    assert _GATE_HEAD in out and state["pending_release"][_SID]["reconcile"]["turn"] == 5
    s6 = copy.deepcopy(state)
    _ups_turn(monkeypatch, s6, "好，放行")                                                   # 使用者另送一則 → UPS 推進到 turn 6
    assert s6["turn_seq"] == 6 and s6["turn_prompts"] == ["好，放行"]
    out, after, logs = exhausted(capsys, **s6)
    assert "ReconcileGate" not in out and "reconcile" not in (after.get("pending_release") or {}).get(_SID, {})
    assert [p["via"] for g, p in logs if p.get("event") == "user_release"] == ["prompt"]   # 正例：跨回合放行
    s6b = copy.deepcopy(state)
    _ups_turn(monkeypatch, s6b, "繼續修")
    out, after, _ = exhausted(capsys, **s6b)
    assert "先前回合已擋滿、仍未放行也仍未解" in out and "【收尾放行確認】" in out              # 反例：不重給新回合預算
    assert {k: after["reconcile_gate_turn"][_SID][k] for k in ("turn", "count")} == {"turn": 6, "count": 1}


def test_006_3_pending_cleared_when_check_passes(driven, capsys):
    """查核通過才清 pending（pending 帶原宣稱 claims；舊版沒帶 claims 的照擋，見 test_013_1_legacy_pending_blocks_until_user_release）。"""
    pend = {_SID: {"reconcile": {"turn": 4, "at": "x", "reason": "r", "claims": ["閘修好了，完成。"]}}}
    out, state, _ = driven("閘修好了，完成。", capsys, verify_receipts={_SID: [_rcpt(5, cmd="python -X utf8 run_verify.py")]},
                           pending_release=pend)
    assert "ReconcileGate" not in out and state["pending_release"][_SID] == {}


def test_006_6_judge_stop_blocks_to_the_end(capsys, monkeypatch):
    import dispatcher
    # UPS 等照舊早退；PreToolUse 只擋判不出的寫入；PostToolUseFailure 補記失敗指令寫下的檔（同 PostToolUse 的最小記帳）
    assert set(dispatcher.JUDGE_HANDLERS) == {"PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop"}
    assert dispatcher.JUDGE_HANDLERS["Stop"] == ("handlers.stop", "handle_judge_stop")
    state = {"turn_seq": 0, "modified_files": [_mf(_CODE, 0)]}
    monkeypatch.setattr(st, "read_state", lambda sid: state)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(vl, "CLAIM_RES", PHRASES)
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)              # _CODE 是虛構路徑
    with pytest.raises(SystemExit):
        st.handle_judge_stop({"session_id": _SID, "last_assistant_message": "全部完成了。"}, {})
    out = capsys.readouterr().out
    assert "無法互動，不能放行" in out and "裁判子 session" in out and "(d)" in out
    state["modified_files"] = []
    with pytest.raises(SystemExit):
        st.handle_judge_stop({"session_id": _SID, "last_assistant_message": "全部完成了。"}, {})
    assert "Guardian" not in capsys.readouterr().out                                       # 沒改檔不擋


def test_006_6_judge_post_tool_use_bookkeeping(tmp_path, monkeypatch):
    from handlers import post_tool_use as pt
    import wg_core
    saved = {}
    monkeypatch.setattr(wg_core, "read_state", lambda sid: None)
    monkeypatch.setattr(pt, "write_state", lambda sid, s: saved.update(s))
    with pytest.raises(SystemExit):
        pt.handle_judge_post_tool_use({"session_id": _SID, "tool_name": "Edit", "tool_input": {"file_path": _CODE},
                                       "cwd": str(tmp_path)}, {})
    assert [m["path"] for m in saved["modified_files"]] == [_CODE]


def test_006_7_report_only_keeps_old_overflow(driven, capsys):
    kw = dict(anti_evasion_report=_aec(5, j=__file__, k=""), verify_receipts={_SID: [_rcpt(5, cmd="python -X utf8 run_verify.py")]})
    out, _, _ = driven("全部完成了。", capsys, **kw)
    assert "(e)" in out and "【收尾放行確認】" not in out                                   # 沒擋滿：照擋
    out, state, logs = driven("全部完成了。", capsys, reconcile_gate_turn={_SID: {"turn": 5, "count": 2}}, **kw)
    assert "ReconcileGate" not in out and state["reconcile_overflow"][_SID]["kind"] == "report"   # 擋滿：照 97128e5 放行記 red
    assert [g for g, _ in logs] == ["reconcile_overflow"]


def test_006_7_code_and_report_split_when_exhausted(driven, capsys):
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CODE, 5)], anti_evasion_report=_aec(5, j=__file__, k=""),
                       verify_receipts={_SID: [_rcpt(5)]}, reconcile_gate_turn={_SID: {"turn": 5, "count": 2}})
    head, _, rest = out.partition("另外（記憶與報告類，不走放行詢問，照原規則處理）")
    assert "【收尾放行確認】" in head and "(d)" in head and "(e)" not in head and "(e)" in rest


def test_006_9_case_must_be_code_file(driven, capsys):
    w = r"c:\proj\src\widget.py"
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(w, 5), _mf(r"c:\proj\tests\README.md", 5)])
    assert "ReconcileGate" in out and "改了程式碼（widget.py）" in out   # 反例：文件冒充案例
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(w, 5), _mf(r"c:\proj\tests\test_widget.py", 5)])
    assert "ReconcileGate" not in out


def test_windows_batch_files_count_as_code(driven, capsys):
    """原設計者 10-20 定：Windows 批次檔（.bat／.cmd）算程式——改了要補測試，和 .ps1、.sh 同樣判。反例：同目錄的文件不算。"""
    exts = vl.reconcile_cfg({})["code_exts"]
    assert vl.is_code_file(r"c:\proj\tools\build.bat", exts) and vl.is_code_file(r"c:\proj\tools\deploy.CMD", exts)
    assert not vl.is_code_file(r"c:\proj\tools\README.md", exts)
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(r"c:\proj\tools\build.bat", 5)])
    assert "ReconcileGate" in out and "改了程式碼（build.bat）" in out, out          # 改批次檔沒補案例照欠


def test_006_10_case_debt_carries_over_turns(driven, capsys):
    w = _mf(r"c:\proj\src\widget.py", 5, last_at="2026-10-12T10:00:00+08:00", last_seq=3)
    out, _, _ = driven("全部完成了。", capsys, turn_seq=6, modified_files=[w])
    assert "改了程式碼（widget.py）" in out                    # 反例：turn 5 改的碼，turn 6 只說完成
    case = _mf(r"c:\proj\tests\test_widget.py", 6, last_at="2026-10-12T10:05:00+08:00", last_seq=9)
    out, _, _ = driven("全部完成了。", capsys, turn_seq=6, modified_files=[w, case])
    assert "ReconcileGate" not in out                                                       # 正例：turn 6 補了案例
    later = _mf(r"c:\proj\src\gadget.py", 6, last_at="2026-10-12T10:06:00+08:00", last_seq=10)
    out, _, _ = driven("全部完成了。", capsys, turn_seq=6, modified_files=[w, case, later])
    assert "改了程式碼（gadget.py）" in out                    # 案例之後又改的碼才欠


# ─── 009 退件：換句話避查核、未知寫入、正常啟動的真收據、背景收據接對帳、刪案例清帳 ─────────────────

_T1, _T2 = "2026-10-12T10:00:00+08:00", "2026-10-12T10:05:00+08:00"


def _pend_state(claims):
    """擋滿時 set_pending 寫下的 pending（含 claims）；直接寫字面值，退回舊碼反證時不依賴新簽名。"""
    return {_SID: {"reconcile": {"turn": 4, "at": "x", "reason": "r", "claims": list(claims)}}}


def test_009_1_rephrase_keeps_case_debt_and_pending(driven, capsys):
    """4.1 重現：有改碼、沒補案例、已有 pending，回「變更內容如上。」→ 擋（含 AskUserQuestion 提示）且 pending 留著；
    補了案例後同一句 → 不擋、pending 清。"""
    code = _mf(r"c:\proj\src\a.py", 5, last_at=_T1, last_seq=3)
    out, state, _ = driven("變更內容如上。", capsys, modified_files=[code], pending_release=_pend_state([]))
    assert "改了程式碼（a.py）" in out and st.ASK_HINT in out
    assert state["pending_release"][_SID]["reconcile"]["turn"] == 5                        # pending 承接、沒被清
    case = _mf(r"c:\proj\tests\test_a.py", 5, last_at=_T2, last_seq=4)
    out, state, _ = driven("變更內容如上。", capsys, modified_files=[code, case], pending_release=_pend_state([]))
    assert "ReconcileGate" not in out and "reconcile" not in state["pending_release"][_SID]


def test_009_1_pending_claim_rechecked_after_rephrase(driven, capsys):
    """4.1 規則 2：擋滿時的宣稱（修好）跟著 pending 走；換句話不清，補到對得上的 PASS 才清。"""
    pend = _pend_state(["閘修好了，完成。"])
    out, state, _ = driven("變更內容如上。", capsys, pending_release=copy.deepcopy(pend))
    assert "(a) CLAIM_FIXED_NEEDS_PASS：說「修好」" in out and state["pending_release"][_SID]["reconcile"]["claims"] == ["閘修好了，完成。"]
    out, state, _ = driven("變更內容如上。", capsys, pending_release=copy.deepcopy(pend),
                           verify_receipts={_SID: [_rcpt(5, cmd="python -X utf8 run_verify.py")]})
    assert "ReconcileGate" not in out and "reconcile" not in state["pending_release"][_SID]


def test_013_1_legacy_pending_blocks_until_user_release(driven, capsys):
    """013 BLOCK 1 規則 2：舊版 pending（沒帶 claims）原宣稱無從重查 → 照擋（不再當成可收尾），pending 留著且不被補上 claims；
    說完成也一樣擋；只有使用者放行能清（放行流程見 test_006_3_pending_release_carries_over_turns）。"""
    legacy = {_SID: {"reconcile": {"turn": 4, "at": "x", "reason": "r"}}}
    for text in ("變更內容如上。", "全部完成了。"):
        out, state, _ = driven(text, capsys, pending_release=copy.deepcopy(legacy))
        assert "舊格式，沒有原宣稱可以重查" in out and "【收尾放行確認】" in out, text
        assert "claims" not in state["pending_release"][_SID]["reconcile"], text


def test_013_1_original_claim_survives_repeated_rephrase(driven, capsys):
    """013 BLOCK 1 重現：pending 的原宣稱是「修好了，全部完成了。」，之後連說五次「全部完成了。」→ 每次都擋、原宣稱不被擠掉；
    補了對得上的 PASS → 清。訊息不再叫人改寫宣稱（WARN 1）。"""
    pend, budget = _pend_state(["修好了，全部完成了。"]), None
    for k in range(5):
        extra = {"reconcile_gate_turn": budget} if budget else {}
        out, state, _ = driven("全部完成了。", capsys, pending_release=copy.deepcopy(pend), **extra)
        assert "(a) CLAIM_FIXED_NEEDS_PASS：說「修好」" in out and "改成事實句" not in out, k
        pend, budget = state["pending_release"], state["reconcile_gate_turn"]
        assert pend[_SID]["reconcile"]["claims"] == ["修好了，全部完成了。"], k
    out, state, _ = driven("全部完成了。", capsys, pending_release=copy.deepcopy(pend),
                           verify_receipts={_SID: [_rcpt(5, cmd="python -X utf8 run_verify.py")]})
    assert "ReconcileGate" not in out and "reconcile" not in state["pending_release"][_SID]


def test_009_1_subagent_and_judge_judge_case_debt_regardless_of_wording(sub_stop, capsys, monkeypatch):
    out, _ = sub_stop(capsys, _sub_state(agent_modified_files={"ag1": [_mf(_CODE, 5)]}), last="變更內容如上。")
    assert "無法互動，不能放行" in out and "改了程式碼（x.py）" in out
    out, _ = sub_stop(capsys, _sub_state(agent_modified_files={"ag1": [_mf(_CODE, 5)]}), last="")
    assert "無法互動，不能放行" in out                                                       # 讀不到收尾文字也照判
    state = {"turn_seq": 0, "modified_files": [_mf(_CODE, 0)]}
    monkeypatch.setattr(st, "read_state", lambda sid: state)
    with pytest.raises(SystemExit):
        st.handle_judge_stop({"session_id": _SID, "last_assistant_message": "變更內容如上。"}, {})
    out = capsys.readouterr().out
    assert "裁判子 session" in out and "改了程式碼（x.py）" in out


def _judge_post(monkeypatch, tmp_path, command):
    from handlers import post_tool_use as pt
    import wg_core
    saved: dict = {}
    monkeypatch.setattr(wg_core, "read_state", lambda sid: None)
    monkeypatch.setattr(pt, "write_state", lambda sid, s: saved.update(s))
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path / "wf")
    with pytest.raises(SystemExit):
        pt.handle_judge_post_tool_use({"session_id": _SID, "tool_name": "Bash", "tool_input": {"command": command},
                                       "cwd": str(tmp_path), "tool_response": {"stdout": "", "exit_code": 0}}, {})
    return saved


def _judge_stop(monkeypatch, capsys, state, real_files=False):
    if not real_files:
        monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)          # 虛構路徑；真檔的案傳 real_files=True
    monkeypatch.setattr(st, "read_state", lambda sid: state)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(vl, "CLAIM_RES", PHRASES)
    with pytest.raises(SystemExit):
        st.handle_judge_stop({"session_id": _SID, "last_assistant_message": "全部完成了。"}, {})
    return capsys.readouterr().out


def test_009_2_judge_unknown_write_logged_not_blocked(tmp_path, monkeypatch, capsys):
    """裁判跑 python -c 寫檔（目標算不出來）→ 記未知寫入（不當成沒改檔）；裁判 Stop 不為它擋（UNKNOWN_TARGET_LOGGED：只留帳）。"""
    saved = _judge_post(monkeypatch, tmp_path, "python -c \"from pathlib import Path; Path('src/a.py').write_text('x')\"")
    assert not saved.get("modified_files") and saved["unknown_writes"][0]["cmd"].startswith("python -c")
    out = _judge_stop(monkeypatch, capsys, saved)
    assert "寫入目標不明" not in out


def test_009_2_judge_read_only_not_blocked(tmp_path, monkeypatch, capsys):
    saved = _judge_post(monkeypatch, tmp_path, "git log --oneline -3")
    assert not saved.get("unknown_writes") and not saved.get("modified_files")
    assert "Guardian" not in _judge_stop(monkeypatch, capsys, saved)


def test_009_2_subagent_unknown_write_logged_not_blocked(sub_stop, capsys, monkeypatch, tmp_path):
    """經主 PostToolUse 入口（帶 agent_id）記帳，再經 SubagentStop 入口判：子代理的未知寫入記帳（agent_unknown_writes）、不擋，
    Stop 留一筆 unknown_writes_logged。"""
    from handlers import post_tool_use as pt
    s = _sub_state(session={"cwd": str(tmp_path)})
    for name, fn in (("_ensure_state", lambda *a, **k: s), ("write_state", lambda *a, **k: None),
                     ("append_guard_log", lambda *a, **k: None), ("_check_output_quality", lambda *a, **k: None)):
        monkeypatch.setattr(pt, name, fn)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"session_id": _SID, "agent_id": "ag1", "tool_name": "Bash", "cwd": str(tmp_path),
                                 "tool_input": {"command": "python -c \"open('a.py','w').write('x')\""},
                                 "tool_response": {"stdout": "", "stderr": ""}}, {"docdrift": {"enabled": False}})
    assert (s.get("agent_unknown_writes") or {}).get("ag1")
    out, logs = sub_stop(capsys, s)
    assert "寫入目標不明" not in out and "unknown_writes_logged" in [p.get("event") for g, p in logs]


_ABS_CMD = 'python -X utf8 "C:\\中文專案\\run_verify.py"'
_ABS_IN_ROOT = 'python -X utf8 "C:\\proj\\run_verify.py"'      # 真的自寫收據：腳本就在 project_root（run_verify 自己的 ROOT）


@pytest.mark.parametrize("run, blocked", [
    (_self_run(cmd=_ABS_IN_ROOT), False),                                   # 絕對路徑、同根、改完才開始、全綠
    (_self_run(cmd=_ABS_IN_ROOT, started="2026-10-12T01:59:59+00:00"), True),  # 改檔之前就開始
    (_self_run(cmd=_ABS_IN_ROOT, root="c:/other"), True),                   # 別的根
    (_self_run(cmd=_ABS_IN_ROOT, failed=3), True),                          # failed=3
    (_self_run(cmd=_ABS_CMD), True),                                        # 017：腳本是別棵樹的 run_verify
])
def test_009_3_real_receipt_with_abs_script_path(run, blocked):
    """4.3：拿掉啟動關聯後，收據採用條件回到 004；收據 cmd 與量尺經同一套正規化比對（python 腳本照相對收據根的路徑比）。"""
    assert (_mg([run]) is not None) is blocked


def test_009_3_session_receipt_uses_same_normalization(scoped, capsys):
    """前景跑的 session 收據也走同一套比對：絕對腳本路徑、`-Xutf8` 寫法都對得上宣告的指令；017b 規則 7：多帶 `-u` 不算。
    017：只比腳本檔名，所以絕對路徑的腳本要在收據根底下；別棵樹的 run_verify（例：從 worktree 跑 live 的）量的不是這裡。"""
    for cmd, blocked in (('python -X utf8 "c:\\proj\\run_verify.py"', False), ("python -Xutf8 run_verify.py", False),
                         ("python -u -X utf8 run_verify.py", True), (_ABS_CMD, True),
                         ("python -X utf8 C:\\Users\\holylight\\.claude\\run_verify.py", True)):
        out = scoped(capsys, [_mf(_CASE, 3)], [_rcpt(4, "DONE", 0, cmd=cmd)])
        assert ("VerifyScope" in out) is blocked, cmd


def test_009_4_background_self_receipt_satisfies_fixed_claim(driven, capsys, monkeypatch):
    """4.4 重現：改碼、改案例、背景全量成功、自寫收據合格，回「修好了，全部完成了。」→ 對帳 (a) 也認自寫收據，不擋。"""
    monkeypatch.setattr(wo, "_lookup", _lookup)
    mods = [_mf(_CODE, 5, last_at=_EDIT_AT, last_seq=7), _mf(_CASE, 5, last_at=_EDIT_AT, last_seq=8)]
    monkeypatch.setattr(st, "load_self_runs", lambda: [_self_run()], raising=False)
    out, _, _ = driven("修好了，全部完成了。", capsys, modified_files=mods)
    assert "ReconcileGate" not in out
    monkeypatch.setattr(st, "load_self_runs", lambda: [_self_run(started="2026-10-12T01:59:00+00:00")], raising=False)
    out, _, _ = driven("修好了，全部完成了。", capsys, modified_files=mods)
    assert "(a) CLAIM_FIXED_NEEDS_PASS：說「修好」" in out                                                         # 自寫收據在改檔之前開始 → 擋


def test_009_5_deleted_case_does_not_clear_debt(driven, capsys, monkeypatch, tmp_path):
    """4.5：改 src/a.py 後刪 tests/test_a.py（PostToolUse 對刪除也記一筆）→ 擋；改 src/a.py 後新增 tests/test_a.py → 不擋。
    案例路徑用虛構的 c:\\proj（pytest 的 tmp 目錄名含 test，會被 `**/*test*` 當成案例），存在與否交給真的 case_exists 查 tmp 真檔。"""
    real = tmp_path / "test_a.py"
    case_path = r"c:\proj\tests\test_a.py"
    monkeypatch.setattr(vl, "case_exists", lambda p: bool(_REAL_CASE_EXISTS) and _REAL_CASE_EXISTS(str(real) if p == case_path else p),
                        raising=False)
    mods = [_mf(r"c:\proj\src\a.py", 5, last_at=_T1, last_seq=3), _mf(case_path, 5, last_at=_T2, last_seq=4)]
    out, _, _ = driven("全部完成了。", capsys, modified_files=mods)
    assert "改了程式碼（a.py）" in out                       # 案例檔已不存在（刪掉了）
    real.write_text("def test_a():\n    assert True\n", encoding="utf-8")
    out, _, _ = driven("全部完成了。", capsys, modified_files=mods)
    assert "ReconcileGate" not in out                                                       # 案例檔在 → 補了案例


# ─── 011：案例判定用相對專案根的路徑比 glob ─────────────────────────────────────────

_LATEST = r"C:\latest\proj"


def test_011_project_under_test_named_dir_judges_relative_path(driven, capsys, monkeypatch):
    """根在 C:\\latest\\proj（虛構路徑走樣式判定；存在與否由 fixture 視為存在）：改 src/a.py → 不是案例、(d) 擋；
    再改 tests/test_a.py → 是案例、(d) 不擋。舊碼比絕對路徑，`**/*test*` 吃到 latest，src/a.py 也算案例 → 不擋。"""
    monkeypatch.setattr(vl, "file_root_of", lambda p: _LATEST if p.lower().startswith(_LATEST.lower()) else None)
    src = _mf(_LATEST + r"\src\a.py", 5, last_at=_T1, last_seq=3)
    out, _, _ = driven("全部完成了。", capsys, modified_files=[src])
    assert "改了程式碼（a.py）" in out
    case = _mf(_LATEST + r"\tests\test_a.py", 5, last_at=_T2, last_seq=4)
    out, _, _ = driven("全部完成了。", capsys, modified_files=[src, case])
    assert "ReconcileGate" not in out


def test_011_ordinary_root_behaves_as_before(monkeypatch):
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)              # 虛構路徑：只驗樣式判定
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)
    cfg = vl.reconcile_cfg({})
    src, case = _mf(r"c:\proj\src\a.py", 5, last_at=_T1, last_seq=3), _mf(r"c:\proj\tests\test_a.py", 5, last_at=_T2, last_seq=4)
    root_of = lambda p: str(ROOT)                                                       # noqa: E731
    assert vl.case_debt([src], 5, cfg, root_of) == [src["path"]]
    assert vl.case_debt([src, case], 5, cfg, root_of) == []
    assert vl.is_verify_case(r"c:\proj\test_root.py", cfg["verify_case_globs"], str(ROOT))   # 根目錄下的 test_x.py 也算
    assert vl.is_verify_case(r"c:\proj\hooks\verify\x.py", cfg["verify_case_globs"], str(ROOT))


def test_011_no_root_falls_back_to_absolute_path_with_one_stderr_line(capsys):
    """拿不到根 → 用絕對路徑判定，stderr 每個程式檔恰一行。舊樣式 `*test*` 會把上層目錄名 latest 吃成案例、沒欠帳；
    案例樣式改成測試目錄與檔名慣例（檔名樣式只比檔名）之後，目錄名不再算數 → 照欠。"""
    cfg = vl.reconcile_cfg({})
    src, doc = _mf(_LATEST + r"\src\a.py", 5, last_at=_T1, last_seq=3), _mf(_LATEST + r"\docs\a.md", 5)
    assert vl.case_debt([src, doc], 5, cfg, lambda p: None) == [src["path"]]
    err = [ln for ln in capsys.readouterr().err.splitlines() if "[verify_ledger] 找不到" in ln]
    assert err == [f"[verify_ledger] 找不到 {src['path']} 的專案根，案例判定改用絕對路徑"]


# ─── 013 退件：串接式量尺、引號與子集冒充、裁判 PreToolUse、訊息與 runtime_gate 成本 ─────────────────

_ROOT_ROWS = parse_map((HOOKS_DIR.parent / ".claude" / "overview-map.md").read_text(encoding="utf-8"))


def _root_row(part):
    return next(r for r in _ROOT_ROWS if r["part_short"] == part)


@pytest.mark.parametrize("part", ["記憶資料層", "專案文件層"])
def test_013_3_compound_ruler_from_root_table_is_satisfiable(part):
    """013 BLOCK 3（最優先）：根層部位表這兩列的量尺由程式自己印完成字樣、不再接 echo（文件層是兩支程式 && 串）；表上字串原樣跑出的
    收據要認得到，後面再接 `; echo 假的 DONE` 就不算。舊碼（7b80327）收據端按 && 切段、量尺端整串比，原樣跑也永遠對不上。"""
    row = _root_row(part)
    cmd = row["measure"]["cmd"]
    assert "echo" not in cmd                                                               # 直接讀表上字串當輸入
    mod = _mf(r"c:\proj\x.md", 5, last_at=_T1, last_seq=3)
    assert _gate(cmd, row=row, mod=mod) is None
    assert _gate(cmd + "; echo FAKE_CHECK DONE", row=row, mod=mod) is not None


def test_013_2_quoted_ruler_text_is_not_a_run(scoped, capsys, monkeypatch):
    """013 BLOCK 2：指令字樣在 echo 的引號裡、成功行是另一個 echo 印的 → 驗證範圍不認、對帳 (a) 不認 PASS。"""
    monkeypatch.setattr(st, "load_self_runs", lambda: [], raising=False)
    fake = "echo 'dummy;py -3 -Xutf8 run_verify.py;'; echo VERIFY_CHECK PASS; echo VERIFY_CHECK DONE cases=1 failed=0"
    r = _rcpt(5, "PASS", 0, cmd=fake, at=_T2)
    r["sentinels"].append({"name": "VERIFY_CHECK", "verdict": "DONE", "kv": {"cases": "1", "failed": "0"}})
    mods = [_mf(_CODE, 5, last_at=_T1, last_seq=3), _mf(_CASE, 5, last_at=_T1, last_seq=4)]
    out = scoped(capsys, mods, [r], text="修好了，全部完成了。")
    assert "(a) CLAIM_FIXED_NEEDS_PASS：說「修好」" in out and "[Guardian:VerifyScope]" in out


# ─── 盤點 P5：(a)「說修好」有宣告就認宣告範圍的收據，沒宣告才退回檔名對應 ─────────────────

_P5_MODS = [_mf(_CODE, 3, last_at="2026-10-12T10:00:00+08:00", last_seq=3),
            _mf(_CASE, 3, last_at="2026-10-12T10:00:00+08:00", last_seq=4)]


def test_p5_fixed_claim_accepts_declared_scope_receipt_from_earlier_turn(scoped, capsys):
    """宣告範圍＝表上那把尺；改完之後（上一回合）跑綠、指令沒提到改的檔 → (a) 認（同一個判斷只有一份答案）。
    舊碼只認本回合、檔名對得上的 PASS → 擋（紅）。"""
    r = _rcpt(4, "PASS", 0, cmd=MEASURE_CMD, at="2026-10-12T10:05:00+08:00", seq=5)
    out = scoped(capsys, _P5_MODS, [r], text="閘修好了，全部完成了。")
    assert "(a) CLAIM_FIXED_NEEDS_PASS" not in out and "VerifyScope" not in out, out


def test_p5_fixed_claim_with_declaration_ignores_file_name_match(scoped, capsys):
    """有宣告時檔名對應不再算數：本回合跑了提到 x.py 的測試，但它不在宣告範圍 → (a) 擋，證據列宣告的項目為什麼沒收據。
    舊碼檔名對上就放 (a)（紅）。"""
    r = _rcpt(5, "PASS", 0, cmd=_RELATED_CMD, at="2026-10-12T10:05:00+08:00", seq=5)
    out = scoped(capsys, _P5_MODS, [r], text="閘修好了，全部完成了。")
    assert "(a) CLAIM_FIXED_NEEDS_PASS：說「修好」但驗證範圍" in out and MEASURE_CMD in out, out


def test_p5_fixed_claim_without_declaration_falls_back_to_file_names(scoped, capsys):
    """沒宣告：退回檔名對應（本回合提到 x.py 的 PASS 就算），(a) 不擋；驗證範圍閘另外要宣告。"""
    r = _rcpt(5, "PASS", 0, cmd=_RELATED_CMD, at="2026-10-12T10:05:00+08:00", seq=5)
    out = scoped(capsys, _P5_MODS, [r], text="閘修好了，全部完成了。", declared=False)
    assert "(a) CLAIM_FIXED_NEEDS_PASS" not in out and "SCOPE_DECLARED_FOR_CHANGE" in out, out


def test_013_2_subset_run_is_not_the_ruler():
    """013 BLOCK 2：宣告 `pytest -q lib/verify`，實跑多帶 `-k 某案` 或多一個檔名 → 不是宣告的那條指令。"""
    row = {"part_short": "純函式與資料層", "measure": {"method": "lib verify", "cmd": "pytest -q lib/verify", "threshold": "全綠"}}
    mod = _mf(r"c:\proj\lib\x.py", 5, last_at=_T1, last_seq=3)
    assert _gate("pytest -q lib/verify", row=row, mod=mod) is None
    assert _gate("pytest lib/verify -q", row=row, mod=mod) is not None                       # 017：照順序比，換位置不算
    assert _gate("pytest -q lib/verify -k test_cmd_of", row=row, mod=mod) is not None
    assert _gate("pytest -q lib/verify lib/verify/verify_self_receipt.py", row=row, mod=mod) is not None


def test_013_w2_runtime_gate_skipped_when_part_already_measured():
    """013 WARN 2：範圍已有合格收據 → 不跑 runtime_gate；還欠收據才跑，量不了的訊息不叫人寫原因來解帳。"""
    calls: list = []
    runner = lambda g, t, c: (calls.append(g), (False, "未就緒"))[1]                          # noqa: E731
    chains = lambda r: {"hook 共用模組層": {"runtime_gate": "probe --check"}}                 # noqa: E731
    mod = _mf(_CASE, 5, last_at=_T1, last_seq=3)
    assert _scope_gate([mod], [_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, at=_T2)], chains_of=chains, runner=runner) is None
    assert calls == []
    reason = _scope_gate([mod], [], chains_of=chains, runner=runner)
    assert calls == ["probe --check"] and "驗證環境未就緒" in reason and "【收尾放行確認】" in reason
    assert "寫明量不了的原因與何時能量，或讓環境就緒後跑尺" not in reason


def test_013_w1_messages_list_evidence_not_rewording(driven, scoped, capsys):
    """013 WARN 1：沒 pending 的 (a) 第一次擋照舊可說「沒跑就說沒跑」；欠補案例 (d) 或驗證範圍欠帳時只列證據與放行問法。"""
    out, _, _ = driven("閘修好了，完成。", capsys)
    assert "沒跑就說沒跑" in out
    out, _, _ = driven("變更內容如上。", capsys, modified_files=[_mf(r"c:\proj\src\a.py", 5, last_at=_T1, last_seq=3)])
    assert "(d)" in out and "改成事實句" not in out and "改寫收尾文字不會解帳" in out
    out = scoped(capsys, [_mf(_CASE, 5)], text="變更內容如上。")
    assert "[Guardian:VerifyScope]" in out and "改寫收尾文字不會解帳" in out


def _judge_dispatch(tool_name, tool_input, cwd):
    """真的跑 dispatcher（CLAUDE_COMPANION_JUDGE=1），回 stdout；經入口驗可觀察結果。"""
    import os
    import subprocess
    env = dict(os.environ, CLAUDE_COMPANION_JUDGE="1", WG_CLAUDE_DIR=str(HOOKS_DIR.parent))
    payload = json.dumps({"hook_event_name": "PreToolUse", "session_id": _SID, "tool_name": tool_name,
                          "tool_input": tool_input, "cwd": str(cwd)}, ensure_ascii=False).encode("utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", str(HOOKS_DIR / "dispatcher.py")], input=payload,
                       capture_output=True, env=env, timeout=120)
    return r.stdout.decode("utf-8", "replace")


def test_013_4_judge_pre_tool_use_allows_unknown_write_target(tmp_path):
    """裁判跑寫檔的 `python -c "open('x','w')…"` → 判不出目標，放行並留帳（UNKNOWN_TARGET_LOGGED）；
    純讀取的 `python -c "print(1)"`（規則 INLINE_PY_READONLY）、git log、Read 放行。"""
    out = _judge_dispatch("Bash", {"command": "python -c \"open('x','w').write('1')\""}, tmp_path)
    assert '"permissionDecision": "deny"' not in out
    assert _judge_dispatch("Bash", {"command": 'python -c "print(1)"'}, tmp_path).strip() == ""
    assert _judge_dispatch("Bash", {"command": "git log --oneline -3"}, tmp_path).strip() == ""
    assert _judge_dispatch("Read", {"file_path": str(tmp_path / "a.py")}, tmp_path).strip() == ""


# ─── 015：對帳 (a) 判「收據有沒有提到改的檔」只看真的會被執行的指令 ─────────────────────────────

_WIDGET = r"c:\proj\src\widget.py"


# ─── 017／017b：白名單語法、解析不了就不算（宣告的指令項目照原字串比；經驗證範圍閘或 handle_stop 入口） ──────────────

def _gate(cmd, tool="Bash", row=None, mod=None):
    """驗證範圍閘入口：宣告範圍＝表上那把尺（row 給了用它的，否則 MEASURE_CMD）；一筆同根、改完之後、exit 0、failed=0 的
    DONE 收據，指令是 cmd（tool 決定依哪種 shell 解析）。回擋訊息或 None。"""
    ruler = ((row or {}).get("measure") or {}).get("cmd") or MEASURE_CMD
    r = {**_rcpt(5, "DONE", 0, cmd=cmd, at=_T2, kv={"cases": "1", "failed": "0"}), "tool": tool}
    return _scope_gate([mod or _mf(_CASE, 5, last_at=_T1, last_seq=3)], [r], cmd=ruler,
                       lookup=(lambda p: (ROOT, row)) if row else _lookup, chains_of=lambda r: {})


_HERE_STRING = "Write-Output @'\nVERIFY_CHECK DONE cases=1 failed=0\n';\npython -X utf8 run_verify.py\nX='\n'@"


def test_017_root_table_rulers_still_runnable_as_declared_commands():
    """G6 (b)：根層部位表 10 列（4 把尺；行為規則層、派工信箱、部位表與專案層設定無尺；hook 兩層與 skill 層的全量 run_verify
    已拔掉，全量改增量待補）的量尺是候選材料：宣告成指令項目後原字串原樣跑，Bash 與 PowerShell 都對得上；直接讀表上字串。"""
    rows = [r for r in _ROOT_ROWS if (r.get("measure") or {}).get("cmd")]
    assert len(_ROOT_ROWS) == 10 and len(rows) == 4
    assert not [r["part_short"] for r in rows if "run_verify.py" in r["measure"]["cmd"]]   # 表上不再有全量當量尺
    for row in rows:
        single = "&&" not in row["measure"]["cmd"]          # 多段量尺後接過濾會蓋掉最後一段的 exit，只有單段量尺准接
        for tool in ("Bash", "PowerShell"):
            assert _gate(row["measure"]["cmd"], tool, row) is None, (row["part_short"], tool)
            assert (_gate(row["measure"]["cmd"] + " 2>&1 | tail -5", tool, row) is None) is single, (row["part_short"], tool)
            assert _gate("python -h " + row["measure"]["cmd"][len("python "):], tool, row) is not None   # 規則 7


def test_017_declared_command_itself_unparseable_is_rejected():
    """G6 (b)：宣告的指令本身含白名單外語法，任何收據都對不上 → 收件就退回並說是哪一種；跑腳本檔的 `pwsh -File` 是白名單內
    → 收下、原樣跑會過。"""
    s = {"turn_seq": 5}
    text = vs.declare(s, _SID, {"action": "verify_scope", "items": [{"target": "pwsh -Command ./verify.ps1", "why": "w"}]},
                      str(ROOT), {}, lookup=lambda p: None)
    assert "SCOPE_ITEM_WELL_FORMED" in text and "解析不了的語法（另起一層 shell" in text and not s.get("verify_scope")
    ok = {"part_short": "工具層", "measure": {"method": "verify", "cmd": "pwsh -NoProfile -File ./verify.ps1", "threshold": "全綠"}}
    assert _gate(ok["measure"]["cmd"], "PowerShell", ok) is None


def test_017_warn_pending_b_c_ask_for_evidence_not_rewording(driven, capsys):
    """017 WARN：沒 pending 的第一次宣稱查核照舊（可說「沒量就寫沒量」）；有 pending 時 (b)(c) 只叫人補證據或問放行。"""
    for claim, hit, phrase in (("我量了，全部完成了。", "(b) CLAIM_MEASURED_NEEDS_DONE：說「量了」", "沒量就寫沒量"),
                               ("我跑了測試，全部完成了。", "(c) CLAIM_TRIED_NEEDS_EXEC：說「試過／跑了」", "沒跑就寫沒跑")):
        out, _, _ = driven(claim, capsys, tool_names=["Read"])
        assert hit in out and phrase in out, claim
        out, _, _ = driven("全部完成了。", capsys, tool_names=["Read"], pending_release=_pend_state([claim]))
        assert hit in out and phrase not in out and "【收尾放行確認】" in out, claim


@pytest.mark.parametrize("cmd, related", [
    ("pytest -q", True), ("python -X utf8 run_verify.py", True),
    ("pytest -q -k x", False), ("pytest --collect-only -q", False), ("pytest -q tests", False),
    ("python -X utf8 run_verify.py --json", False), ("pytest -q -o testpaths=src", False),
])
def test_017b_9_only_unnarrowed_runs_are_whole_verification(driven, capsys, cmd, related):
    """017b 規則 9：說「修好」時，整體驗證只認不帶參數的 run_verify.py 與不縮範圍的 pytest；選案、只收集、指定目錄都不算。"""
    mods = [_mf(_WIDGET, 5, last_at=_T1, last_seq=3), _mf(r"c:\proj\tests\test_widget.py", 5, last_at=_T1, last_seq=4)]
    out, _, _ = driven("widget 修好了，完成。", capsys, modified_files=mods, verify_receipts={_SID: [_rcpt(5, cmd=cmd, at=_T2)]})
    assert ("(a) CLAIM_FIXED_NEEDS_PASS：說「修好」" not in out) is related, cmd


def test_017b_10_measured_claim_accepts_qualified_self_receipt(driven, capsys, monkeypatch):
    """017b 規則 10：說「量了」、本回合沒有 DONE，但改檔部位有合格自寫收據（量尺閘同條件）→ (b) 不擋；收據在改檔之前開始 → 擋。"""
    monkeypatch.setattr(wo, "_lookup", _lookup)
    mods = [_mf(_CODE, 5, last_at=_EDIT_AT, last_seq=7), _mf(_CASE, 5, last_at=_EDIT_AT, last_seq=8)]
    monkeypatch.setattr(st, "load_self_runs", lambda: [_self_run()], raising=False)
    out, _, _ = driven("我量了，全部完成了。", capsys, modified_files=mods)
    assert "(b) CLAIM_MEASURED_NEEDS_DONE：說「量了」" not in out and "ReconcileGate" not in out
    monkeypatch.setattr(st, "load_self_runs", lambda: [_self_run(started="2026-10-12T01:59:00+00:00")], raising=False)
    out, _, _ = driven("我量了，全部完成了。", capsys, modified_files=mods)
    assert "(b) CLAIM_MEASURED_NEEDS_DONE：說「量了」" in out


def test_017b_11_ruler_own_echo_still_counts():
    """017b 規則 11 例外：表上記憶資料層量尺的 echo 是指令本身 → 宣告成指令項目認得；前面再加一個印哨兵的 echo → 不認。"""
    row = _root_row("記憶資料層")
    m = row["measure"]["cmd"]
    assert _gate(m, row=row) is None
    assert _gate("echo MEMORY_INDEX_CHECK DONE; " + m, row=row) is not None


def test_017_file_item_pytest_done_must_come_from_pytest(tmp_path):
    """檔案項目認 pytest 摘要行映射的收據：輸出要是 pytest 印的（最後執行的指令是 pytest、前面只准 cd 與環境設定、
    參數沒寫哨兵字樣）；echo／cat 舊 log 印的 `5 passed` 不算。"""
    _, wt = _two_roots(tmp_path)
    path_gate = _path_scope_gate(wt)
    gate = lambda cmd: path_gate([_pytest_done(5, wt, cmd=cmd)])                                 # noqa: E731
    assert gate(_PYTEST_CMD) is None and gate(f"WG=1 {_PYTEST_CMD} 2>&1 | tail -3") is None
    for fake in ('echo "=== 5 passed in 0.1s ==="', "cat old-pytest.log", f"cat old-pytest.log; {_PYTEST_CMD} | tail -3",
                 f"{_PYTEST_CMD}; echo '5 passed'"):
        assert gate(fake) is not None, fake


# ─── 017 codex 初審：指定式藏假哨兵、讀舊輸出檔冒充、done_receipts 預設也 fail-closed ─────────────────────

_PYTEST_RULE = {"regex": "^(?:=+ )?(?P<verdict>\\d+ (?:passed|failed))", "name": "PYTEST_MEASURE",
                "verdict_map": {"failed": "FAIL", "passed": "DONE"}}


def test_017_codex1_powershell_assignment_cannot_print_fake_pytest_summary(tmp_path, monkeypatch):
    """codex 初審 BLOCK 1：`$env:S="5 passed"; $x=Write-Host $env:S; python -m pytest --version`（PowerShell 實跑會印出假摘要）
    經 PostToolUse 落帳 → 驗證範圍的檔案項目不認；真的跑 pytest 印的摘要 → 認。"""
    from handlers import post_tool_use as pt
    _, wt = _two_roots(tmp_path)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path / "wf")
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    path_gate = _path_scope_gate(wt)

    def gate(cmd, stdout):
        state = {"turn_seq": 5, "session": {"cwd": str(wt)}}
        assert pt._track_sentinels(state, {"tool_response": {"stdout": stdout}, "cwd": str(wt)}, cmd, "PowerShell",
                                   {"verify_ledger": {"sentinel_regex": [_PYTEST_RULE]}}, _SID)
        return path_gate(state["verify_receipts"][_SID])

    fake = '$env:S="5 passed"; $x=Write-Host $env:S; python -m pytest --version'
    assert gate(fake, "5 passed\npytest 8.3.0\n") is not None
    assert gate("$x = Write-Host '=== 5 passed ==='; python -m pytest --version", "=== 5 passed ===\npytest 8.3.0\n") is not None
    assert gate(_PYTEST_CMD, "1 passed in 0.10s\n") is None


def test_017_codex_r2_3_other_tree_paths_do_not_count(tmp_path, monkeypatch):
    """codex 二審 BLOCK 3：`../live/run_verify.py`、`C:/proj/../live/run_verify.py` 量的是別棵樹 → 指令項目不認；worktree 的
    檔案項目拿 pytest 跑別棵樹的同名測試也不認。codex 二審 BLOCK 4：`pytest x && pytest b` 誠實串接 → 認。"""
    for bad in ("python -X utf8 ../live/run_verify.py", "python -X utf8 C:/proj/../live/run_verify.py"):
        reason = _gate(bad)
        assert reason and "收據根以外" in reason, bad
    assert _gate("python -X utf8 c:/proj/sub/../run_verify.py") is None
    live, wt = _two_roots(tmp_path)
    path_gate = _path_scope_gate(wt)
    gate = lambda cmd: path_gate([_pytest_done(5, wt, cmd=cmd)])                                 # noqa: E731
    assert gate(f"python -m pytest -q {live}/hooks/verify/verify_x.py") is not None
    assert gate("python -m pytest -q ../live/hooks/verify/verify_x.py") is not None
    assert gate("python -m pytest -q hooks/verify/verify_x.py && python -m pytest -q hooks/verify/verify_b.py") is None
    # codex 三審探針：後一段失敗沒印 failed、又被 | tail 蓋掉 exit，前一段的 passed 不能替它背書
    assert gate("python -m pytest hooks/verify/verify_x.py && python -m pytest missing.py | tail -5") is not None


@pytest.mark.parametrize("cmd", [f"git status; {MEASURE_CMD}", f"{MEASURE_CMD} | head -5", f"cd sub; {MEASURE_CMD} | tail -n 20 old.log"])
def test_017_block_message_explains_allowed_prefix(cmd):
    """總控台裁定：量尺前面只准 `cd <絕對路徑> &&` 與環境設定；量尺前後接了別的指令時，擋訊息要說明允許的寫法。"""
    reason = _gate(cmd)
    assert reason and "裡有量尺，但前後接了別的指令" in reason and "前面只准 `cd <絕對路徑> &&` 與環境設定" in reason, cmd
    assert "| Select-Object -Last N" in reason
    assert "前後接了別的指令" not in (_gate("python -X utf8 tools/other.py") or "")          # 沒有量尺的指令不加這句


def test_017_codex_r4_scope_gate_identity_and_tail():
    """codex 四審（經驗證範圍閘的指令項目）：從 archive/ 跑 `python -X utf8 run_verify.py`（cwd 不是宣告時的目錄）跑的是另一支
    → 不認；`../live/verify.sh` 不是宣告的 `./verify.sh` → 不認；多段指令最後一段會失敗又接 `| tail` → 不認。"""
    archive = {**_rcpt(5, "DONE", 0, cmd=MEASURE_CMD, at=_T2, kv={"cases": "1", "failed": "0"}), "cwd": r"c:\proj\archive"}
    assert _scope_gate([_mf(_CASE, 5, last_at=_T1, last_seq=3)], [archive], chains_of=lambda r: {}) is not None
    sh_row = {"part_short": "腳本層", "measure": {"method": "verify", "cmd": "./verify.sh --all", "threshold": "全綠"}}
    assert _gate("../live/verify.sh --all", row=sh_row) is not None and _gate("./verify.sh --all", row=sh_row) is None
    two = {"part_short": "兩段", "measure": {"method": "v", "cmd": "python -X utf8 run_verify.py && python check.py", "threshold": "全綠"}}
    assert _gate(two["measure"]["cmd"] + " | tail -n 5", row=two) is not None
    assert _gate(two["measure"]["cmd"], row=two) is None


def test_017_codex_r3_scope_gate_follows_real_execution():
    """codex 三審：判定要跟 shell 實際執行一致。`X=1 || 指令`（指令被短路）、`$x = Set-Location; 指令`（換到家目錄）、
    `cd C:/repo | … && 指令`（管線裡的 cd 不換目錄）、`archive/run_verify.py`（另一支同名腳本）→ 指令項目不認；
    `指令 # cd C:/repo`（cd 只在註解裡，PostToolUse 用原字串標了 root_uncertain）→ 認。"""
    row = _root_row("記憶資料層")
    mem = row["measure"]["cmd"]
    assert _gate(f"X=1 || {mem}", row=row) is not None and _gate(mem, row=row) is None
    assert _gate(f"$x = Set-Location; {MEASURE_CMD}", "PowerShell") is not None
    assert _gate(f"$ErrorActionPreference = 'Stop'; {MEASURE_CMD}", "PowerShell") is None
    assert _gate(f"cd {ROOT} | export X=1 && {MEASURE_CMD}") is not None
    assert _gate("python -X utf8 archive/run_verify.py") is not None
    r = {**_rcpt(5, "DONE", 0, cmd=f"{MEASURE_CMD} # cd C:/repo", at=_T2, kv={"cases": "1", "failed": "0"}),
         "root_uncertain": True}
    assert _scope_gate([_mf(_CASE, 5, last_at=_T1, last_seq=3)], [r], chains_of=lambda r: {}) is None


def test_017d_rescue_map_error_is_logged_not_swallowed_by_name_error(monkeypatch, capsys):
    """017d：stop.py 的 rescue_map 例外路徑呼叫 _atom_debug_error 卻沒 import → 一跑就 NameError，被外層吞成
    「usefulness attribution error」、整段歸因中斷。修好：錯誤記進 _atom_debug_error（wg_core 那支），歸因照常跑完。"""
    import wg_core
    import wg_rescue
    assert getattr(st, "_atom_debug_error", None) is wg_core._atom_debug_error
    seen: list = []
    monkeypatch.setattr(st, "_atom_debug_error", lambda src, exc: seen.append((src, type(exc).__name__)))

    def boom(*a, **k):
        raise RuntimeError("rescue broke")

    monkeypatch.setattr(wg_rescue, "rescue_hits_for_turn_from_state", boom)
    state = {"turn_seq": 3}
    st._attribute_usefulness(state, {"usefulness": {"attribution_policy": "v2"}}, _SID, None, "完成", transcript_text="")
    assert seen == [("usefulness:rescue_map", "RuntimeError")]
    assert state.get("usefulness_attributed_seq") == 3 and "usefulness attribution error" not in capsys.readouterr().err


# ─── 021：不做執行程式擴充；不在白名單的程式在擋訊息裡指路到量尺欄 ─────────────────────────────

def test_028_tool_on_path_in_ruler_counts_full_out_of_tree_path_says_why():
    """028：照提示把自製工具寫成 PATH 上的程式名放進量尺欄，照跑可採認；量尺欄寫樹外完整路徑，照跑仍拒收（採認規則不放寬），
    訊息講是哪個樹外路徑與改法，不說成「前後接了別的指令」。"""
    on_path = "Unity.exe -batchmode -runTests -testFilter widget"
    assert _gate(on_path, row={**ROWS[0], "measure": {**ROWS[0]["measure"], "cmd": on_path}}) is None
    full = '"C:/Program Files/Unity/Hub/Editor/2022.3.1f1/Editor/Unity.exe" -batchmode -runTests -testFilter widget'
    reason = _gate(full, row={**ROWS[0], "measure": {**ROWS[0]["measure"], "cmd": full}})
    assert reason and "C:/Program Files/Unity/Hub/Editor/2022.3.1f1/Editor/Unity.exe" in reason
    assert "收據根以外" in reason and "PATH 上的程式名" in reason and "前後接了別的指令" not in reason


# ─── 022：量尺比對定死四條家族規則 ────────────────────────────────────────────────────────────

_PS4_FAKE = ("PS4='VERIFY_CHECK DONE cases=1 failed=0 '\nset +o pipefail\nset -x\n"
             "C:/missing/python.exe -X utf8 run_verify.py 2>&1 | tail -20")


def test_022_codex_pre_honest_forms_still_count():
    """配對正例：行內字面值環境指定、單引號包住的 $、bash 小寫 env／ifs（bash 變數名分大小寫，不是 ENV／IFS）、2>&1 | tail 照算。"""
    for cmd in ("X=1 " + MEASURE_CMD, "X='$HOME' " + MEASURE_CMD, "env=x; ifs=y; " + MEASURE_CMD,
                MEASURE_CMD + " 2>&1 | tail -5", "WG_CLAUDE_DIR='C:/x' " + MEASURE_CMD):
        assert _gate(cmd) is None, cmd
    assert _gate(f"$note='it''s'; {MEASURE_CMD}", "PowerShell") is None                       # PowerShell '' 是字面引號


def test_022_codex_pre_declared_command_runs_in_its_own_dir():
    """022 規則 4（驗證範圍的指令項目）：宣告 `python -m pytest -q` 時，`cd 根/tests && 同一條指令` 跑的是 tests 之下那一組，
    不算；擋訊息說執行根在哪；在宣告時的目錄跑、或開頭 cd 到那個目錄照算。"""
    row = {**ROWS[0], "measure": {**ROWS[0]["measure"], "cmd": "python -m pytest -q"}}
    reason = _gate("cd c:/proj/tests && python -m pytest -q", row=row)
    assert reason and "執行根是 c:/proj/tests" in reason
    assert _gate("python -m pytest -q", row=row) is None
    assert _gate("cd c:/proj && python -m pytest -q", row=row) is None


def test_022_codex_pre_drop_anchors_keeps_classes_and_escapes():
    """_drop_anchors 只拿錨點：字元類裡的 ^ $、跳脫的 \\$、類別開頭的 ] 都照留。"""
    assert vl._drop_anchors("(?i)^CUSTOM_OK$") == "(?i)CUSTOM_OK"
    assert vl._drop_anchors("^(?:CUSTOM_OK$)") == "(?:CUSTOM_OK)"
    assert vl._drop_anchors(r"\AX_OK\Z") == "X_OK"
    assert vl._drop_anchors("[^$]X$") == "[^$]X"
    assert vl._drop_anchors(r"^\$5 passed$") == r"\$5 passed"
    assert vl._drop_anchors("[]^]X") == "[]^]X"


@pytest.mark.parametrize("cmd, tool", [
    ("PYTEST_ADDOPTS='-k test_x' python -m pytest -q", "Bash"),                 # 從環境塞 -k：跑的是子集
    ("export PYTEST_ADDOPTS='tests/test_other.py'; python -m pytest -q", "Bash"),
    ("PYTHONOPTIMIZE=1 python -m pytest -q", "Bash"),                            # 等於 -O
    ('$env:pytest_addopts="-k test_x"; python -m pytest -q', "PowerShell"),      # PowerShell 不分大小寫
])
def test_022_codex_pre_env_injected_options_are_not_whole_runs(cmd, tool):
    """022 規則 4：PYTEST_ADDOPTS／PYTHONOPTIMIZE 從環境替程式加選項，等於命令列多帶了選項：不算整體驗證，
    也對不上沒指定它的量尺 `python -m pytest -q`。配對正例：其他環境指定照算。"""
    widget = r"c:\proj\src\widget.py"
    r = {**_rcpt(5, cmd=cmd), "tool": tool}
    assert vl.claimed_paths(r, [widget]) == [] and vl.claimed_paths(r, [widget], ["python -m pytest -q"]) == []
    row = {**ROWS[0], "measure": {**ROWS[0]["measure"], "cmd": "python -m pytest -q"}}
    assert _gate(cmd, tool, row) is not None
    ok = {**_rcpt(5, cmd="X=1 python -m pytest -q"), "tool": "Bash"}
    assert vl.claimed_paths(ok, [widget]) == [widget] and _gate("X=1 python -m pytest -q", row=row) is None


def test_022_codex_pre_ruler_covers_only_its_exec_root():
    """022 規則 4：對帳閘的量尺分支也只涵蓋執行根之下的改檔；`cd 子專案 && 量尺` 對上的是子專案自己那支，不涵蓋父專案改檔。"""
    widget = r"c:\proj\src\widget.py"
    sub = _rcpt(5, cmd="cd c:/proj/subproject && " + MEASURE_CMD)
    assert vl.claimed_paths(sub, [widget], [MEASURE_CMD]) == []
    assert not vl.receipt_relates(sub, [widget], measure_cmds=[MEASURE_CMD])
    top = _rcpt(5, cmd=MEASURE_CMD)
    assert vl.claimed_paths(top, [widget], [MEASURE_CMD]) == [widget]
    assert vl.receipt_relates(top, [widget], measure_cmds=[MEASURE_CMD])


# ─── 024：影響範圍的環境選項只看真的進子程式環境、值非空的設定；自寫收據共用同一個判斷；去錨點懂註解 ────────────

def _pytest_row():
    return {**ROWS[0], "measure": {**ROWS[0]["measure"], "cmd": "python -m pytest -q"}}


@pytest.mark.parametrize("cmd, tool, fold, counts", [
    ("pytest_addopts='-k x' python -m pytest -q", "Bash", True, False),         # Windows：bash 小寫在 Python 裡就是 PYTEST_ADDOPTS
    ("pytest_addopts='-k x' python -m pytest -q", "Bash", False, True),         # 非 Windows：小寫是另一個變數
    ('$PYTEST_ADDOPTS="工作備註"; python -m pytest -q', "PowerShell", True, True),  # PowerShell 變數不進子程式環境
    ('$global:PYTEST_ADDOPTS="-k x"; python -m pytest -q', "PowerShell", True, True),
    ("PYTEST_ADDOPTS='' python -m pytest -q", "Bash", True, True),              # 清空不算縮小範圍
    ('$env:PYTEST_ADDOPTS=""; python -m pytest -q', "PowerShell", True, True),
    ("$env:PYTEST_ADDOPTS=$null; python -m pytest -q", "PowerShell", True, True),
    ('$env:pytest_addopts="-k x"; python -m pytest -q', "PowerShell", True, False),
    ("export PYTEST_ADDOPTS='-k x'; python -m pytest -q", "Bash", True, False),
    ("PYTEST_ADDOPTS='-k x'; python -m pytest -q", "Bash", True, False),        # 單獨一段：變數若本來就在環境裡會傳下去，照算
    ("PYTHONOPTIMIZE=1 python -m pytest -q", "Bash", True, False),
    ("$env:PYTHONOPTIMIZE='$null'; python -m pytest -q", "PowerShell", True, False),  # 加引號的 '$null' 是字串，非空
    ("$env:PYTHONOPTIMIZE=' '; python -m pytest -q", "PowerShell", True, False),      # 空白也是值，不修剪
    ("$env:PYTEST_ADDOPTS='-k x'; $env:PYTEST_ADDOPTS=''; python -m pytest -q", "PowerShell", True, True),  # 照順序：啟動時已清空
    ("export PYTEST_ADDOPTS='-k x'; PYTEST_ADDOPTS='' python -m pytest -q", "Bash", True, True),
    ("export PYTEST_ADDOPTS='-k x' && PYTEST_ADDOPTS='' && python -m pytest -q", "Bash", True, True),
    ("export PYTEST_ADDOPTS='-k x' || PYTEST_ADDOPTS=''; python -m pytest -q", "Bash", True, False),  # || 右邊不會跑
    ("export PYTEST_ADDOPTS='-k x'; PYTEST_ADDOPTS='' | X=1; python -m pytest -q", "Bash", True, False),  # 管線子 shell
    ("declare -x PYTEST_ADDOPTS=''; python -m pytest -q", "Bash", True, False),  # declare 不在 022 規則 2 的前置設定白名單
])
def test_024_1_scope_env_counts_only_child_env_with_value(monkeypatch, cmd, tool, fold, counts):
    """024 規則 1：只有真的進到子程式環境（bash 行內前綴／export、PowerShell 只有 $env:）而且值非空的 PYTEST_ADDOPTS／
    PYTHONOPTIMIZE 才算縮小驗證範圍；名稱照受執行平台比（fold＝Windows 不分大小寫）。counts＝這條仍算整體驗證、也對得上量尺。"""
    monkeypatch.setattr(vl._self_receipt, "_ENV_CASE_FOLD", fold, raising=False)
    widget = r"c:\proj\src\widget.py"
    r = {**_rcpt(5, cmd=cmd), "tool": tool}
    assert (vl.claimed_paths(r, [widget]) == [widget]) is counts, cmd
    assert (_gate(cmd, tool, _pytest_row()) is None) is counts, cmd


def test_024_1_ruler_with_scope_env_compares_values():
    """024 規則 1：表上量尺本身帶影響範圍的環境設定時，收據要同名同值才對得上；換成縮小範圍的值、或少了它都對不上。"""
    row = {**ROWS[0], "measure": {**ROWS[0]["measure"], "cmd": "PYTEST_ADDOPTS='--tb=short' python -m pytest -q"}}
    assert _gate("PYTEST_ADDOPTS='--tb=short' python -m pytest -q", row=row) is None
    assert _gate("PYTEST_ADDOPTS='-k x' python -m pytest -q", row=row) is not None
    assert _gate("python -m pytest -q", row=row) is not None


def test_024_1_scope_env_block_message_names_variable_and_fix():
    """024 規則 1：被環境選項擋下時，訊息說是哪個環境設定、怎麼改，不是「量尺前後接了別的指令」；多段量尺的第一段帶了也一樣。"""
    reason = _gate("PYTEST_ADDOPTS='-k x' python -m pytest -q", row=_pytest_row())
    assert reason and "PYTEST_ADDOPTS" in reason and "拿掉多加的設定" in reason and "前後接了別的指令" not in reason
    row = {**ROWS[0], "measure": {**ROWS[0]["measure"], "cmd": "python -m pytest -q && python check.py"}}
    reason = _gate("PYTEST_ADDOPTS='-k x' python -m pytest -q && python check.py", row=row)
    assert reason and "PYTEST_ADDOPTS" in reason and "前後接了別的指令" not in reason
    row = {**ROWS[0], "measure": {**ROWS[0]["measure"], "cmd": "PYTEST_ADDOPTS='--tb=short' python -m pytest -q"}}
    reason = _gate("python -m pytest -q", row=row)                                      # 少了表上要的值：不叫人拿掉
    assert reason and "表上是 '--tb=short'" in reason and "拿掉多加的設定" not in reason
    row = {**ROWS[0], "measure": {**ROWS[0]["measure"], "cmd": "python -m pytest -q && echo VERIFY_CHECK DONE"}}
    reason = _gate("PYTEST_ADDOPTS='-k x' python -m pytest -q && echo VERIFY_CHECK DONE", row=row)
    assert reason and "PYTEST_ADDOPTS" in reason and "寫了哨兵字樣" not in reason        # 量尺自帶的 DONE 不是這次的原因


@pytest.mark.parametrize("cmd, tool, related", [
    ("PYTEST_ADDOPTS='-k other' python -m pytest -q tests/test_widget.py", "Bash", False),
    ("PYTHONOPTIMIZE=1 python -m pytest -q tests/test_widget.py", "Bash", False),
    ('$env:PYTEST_ADDOPTS="-k other"; python -m pytest -q tests/test_widget.py', "PowerShell", False),
    ("PYTEST_ADDOPTS='-k other' python -m pytest -q tests/test_widget.py && python -m pytest -q tests/test_other.py",
     "Bash", False),                                                                       # 只有第一段帶縮限
    ("PYTEST_ADDOPTS='' python -m pytest -q tests/test_widget.py", "Bash", True),          # 清空照算
    ('$PYTEST_ADDOPTS="工作備註"; python -m pytest -q tests/test_widget.py', "PowerShell", True),   # PowerShell 普通變數
])
def test_026_general_evidence_checks_scope_env_at_every_program_step(driven, capsys, cmd, tool, related):
    """026：規則 1 的環境檢查也接到一般證據（_clean／claimed_paths）：每一段跑程式的指令啟動時，有效環境帶非空縮限設定就不採認，
    擋訊息講變數名與改法；清空與 PowerShell 普通變數照常採認。"""
    widget = r"c:\proj\src\widget.py"
    r = {**_rcpt(5, cmd=cmd, at=_T2), "tool": tool}
    assert (vl.claimed_paths(r, [widget]) == [widget]) is related, cmd
    mods = [_mf(widget, 5, last_at=_T1, last_seq=3), _mf(r"c:\proj\tests\test_widget.py", 5, last_at=_T1, last_seq=4)]
    out, _, _ = driven("widget 修好了，完成。", capsys, modified_files=mods, verify_receipts={_SID: [r]})
    assert ("(a) CLAIM_FIXED_NEEDS_PASS：說「修好」" not in out) is related, cmd
    if not related:
        assert "改了驗證選項" in out and ("PYTEST_ADDOPTS" in out or "PYTHONOPTIMIZE" in out), cmd


def test_026_file_item_pytest_run_checks_scope_env(tmp_path):
    """026：檔案項目認 pytest 收據也查環境：縮限設定跑出來的不算，訊息講變數；清空照算。"""
    _, wt = _two_roots(tmp_path)
    gate = _path_scope_gate(wt)
    narrowed = _pytest_done(5, wt, cmd="PYTEST_ADDOPTS='-k other' python -X utf8 -m pytest -q hooks/verify/verify_x.py")
    reason = gate([narrowed])
    assert reason and "PYTEST_ADDOPTS" in reason
    cleared = _pytest_done(5, wt, cmd="PYTEST_ADDOPTS='' python -X utf8 -m pytest -q hooks/verify/verify_x.py")
    assert gate([cleared]) is None


def test_024_2_self_receipt_with_scope_env_does_not_settle_part(tmp_path, monkeypatch):
    """024 規則 2：`PYTEST_ADDOPTS='-k x' python -X utf8 run_verify.py` 的自寫收據（用真的 write_self_receipt 序列化）不能替部位
    解帳，擋訊息說是哪個環境設定；配對正例：環境裡沒有或是空值時，同樣寫出的收據照算。"""
    from datetime import datetime, timezone
    started = datetime(2026, 10, 12, 2, 0, 1, tzinfo=timezone.utc).timestamp()

    def written(name, value):
        monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
        monkeypatch.delenv("PYTHONOPTIMIZE", raising=False)
        if value is not None:
            monkeypatch.setenv("PYTEST_ADDOPTS", value)
        p = vl._self_receipt.write_self_receipt(tmp_path / name, ["python", "-X", "utf8", "run_verify.py"],
                                                "VERIFY_CHECK DONE cases=1 failed=0", 0, 1, 0, str(ROOT), str(ROOT),
                                                started, started + 60)
        return json.loads(p.read_text(encoding="utf-8"))
    reason = _mg([written("subset", "-k test_x")])
    assert reason and "PYTEST_ADDOPTS" in reason and "自寫收據" in reason
    assert _mg([written("clean", None)]) is None and _mg([written("empty", "")]) is None
    legacy = {k: v for k, v in _self_run().items() if k != "env"}
    assert _mg([legacy]) is not None                                                      # 沒記 env 的舊收據看不出來，不算


# ─── 017c：寫碼查核看真正的最後一句（短收尾句不被 30 字下限跳過） ─────────────────────────────────

_LONG_NOTE = "這一段是很長的說明，交代改動的來龍去脈與每一個檔案的用途，只是說明而已沒有別的。"


def _transcript(path, *texts):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": t}]}}, ensure_ascii=False) + "\n" for t in texts), encoding="utf-8")
    return path


def test_017c_short_final_claim_after_long_text_is_judged(driven, capsys, monkeypatch, tmp_path):
    """長說明（>30 字、沒宣稱）之後只回「修好了，全部完成。」、沒跑 PASS → (a) 擋；補跑對得上的 PASS → 不擋。
    有紅測時 TestFailGate 也看這一句。舊碼只收 >30 字的段落，拿前一段說明判，不擋。"""
    assert len(_LONG_NOTE) > 30 and len("修好了，全部完成。") <= 30
    tp = _transcript(tmp_path / "t.jsonl", _LONG_NOTE, "修好了，全部完成。")
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: tp)
    kw = dict(session={"cwd": str(tmp_path)})
    out, _, _ = driven(None, capsys, **kw)
    assert "(a) CLAIM_FIXED_NEEDS_PASS：說「修好」" in out
    out, _, _ = driven(None, capsys, verify_receipts={_SID: [_rcpt(5, cmd=MEASURE_CMD)]}, **kw)
    assert "ReconcileGate" not in out
    red = {"cmd": "python -m pytest x.py", "summary": "1 failed", "turn_seq": 5, "session_id": _SID, "pytest": True}
    out, _, _ = driven(None, capsys, failing_tests=[red], **kw)
    assert "TestFailGate" in out


def test_017c_hook_last_assistant_message_wins_over_transcript(driven, capsys, monkeypatch, tmp_path):
    """hook 輸入帶 last_assistant_message、transcript 還沒寫入最後一則 → 照 last_assistant_message 判；
    擋滿時 pending 記下的原宣稱也是這一句（017c 規則 3）。"""
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    tp = _transcript(tmp_path / "t.jsonl", _LONG_NOTE)
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: tp)
    kw = dict(session={"cwd": str(tmp_path)})
    out, _, _ = driven(None, capsys, **kw)
    assert "ReconcileGate" not in out                                                       # 只有說明 → 沒宣稱
    out, state, _ = driven(None, capsys, hook_input={"last_assistant_message": "修好了，全部完成。"},
                           reconcile_gate_turn={_SID: {"turn": 5, "count": 2}}, **kw)
    assert "(a) CLAIM_FIXED_NEEDS_PASS：說「修好」" in out
    assert state["pending_release"][_SID]["reconcile"]["claims"] == ["修好了，全部完成。"]


# ─── 035／033：繼承環境進判定、pytest error 是 FAIL、部位表讀不到要擋、暫存子目錄不是改碼、還原反例 ──────────

import os  # noqa: E402
import subprocess  # noqa: E402

_LIVE_CFG = json.loads((HOOKS_DIR.parent / "workflow" / "config.json").read_text(encoding="utf-8"))
_PTU_CFG = {"verify_ledger": _LIVE_CFG["verify_ledger"], "docdrift": {"enabled": False}}
_WIDGET, _WIDGET_CASE = r"c:\proj\src\widget.py", r"c:\proj\tests\test_widget.py"


def _post(monkeypatch, tmp_path, cmd, out, tool="Bash", resp=None, turn=5):
    """經 post_tool_use 入口落一筆收據（用這棵樹 config.json 的 sentinel_regex）；resp 給了就當 tool_response 原樣送（字串＝沒有 exit 欄）。
    回 state（verify_receipts、failing_tests）。"""
    from handlers import post_tool_use as pt
    state = {"turn_seq": turn, "session": {"cwd": str(ROOT)}}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    tr = resp if resp is not None else {"stdout": out, "stderr": "", "exit_code": 0}
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"session_id": _SID, "tool_name": tool, "tool_input": {"command": cmd},
                                 "tool_response": tr, "cwd": str(ROOT)}, _PTU_CFG)
    return state


def _edit_via_post_tool_use(monkeypatch, tmp_path, path):
    """經 post_tool_use 入口（Edit）改這個檔；回 state。"""
    from handlers import post_tool_use as pt
    state = {"turn_seq": 5, "session": {"cwd": str(HOOKS_DIR.parent)}}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"session_id": _SID, "tool_name": "Edit", "tool_input": {"file_path": path},
                                 "tool_response": {}, "cwd": str(HOOKS_DIR.parent)}, {"docdrift": {"enabled": False}})
    return state


_WIDGET_MODS = [_mf(_WIDGET, 5, last_at=_T1, last_seq=3), _mf(_WIDGET_CASE, 5, last_at=_T1, last_seq=4)]


@pytest.mark.parametrize("inherited, cmd, tool, ok", [
    ("-k smoke", "python -X utf8 -m pytest -q", "Bash", False),                           # 繼承：指令內沒提，程式照樣只跑子集
    ("-k smoke", "python -X utf8 -m pytest -q", "PowerShell", False),
    ("-k smoke", "PYTEST_ADDOPTS='-k x' python -X utf8 -m pytest -q", "Bash", False),     # 行內覆蓋成另一個縮限值
    ("-k smoke", "PYTEST_ADDOPTS='' python -X utf8 -m pytest -q", "Bash", True),           # 行內清空繼承值
    ("-k smoke", "$env:PYTEST_ADDOPTS=''; python -X utf8 -m pytest -q", "PowerShell", True),
    ("-k smoke", "$env:PYTEST_ADDOPTS=$null; python -X utf8 -m pytest -q", "PowerShell", True),
    ("", "python -X utf8 -m pytest -q", "Bash", True),                                      # 繼承的是空值
    (None, "python -X utf8 -m pytest -q", "Bash", True),                                    # 父行程沒設
])
def test_035_1_inherited_scope_env_is_part_of_effective_env(driven, capsys, monkeypatch, tmp_path, inherited, cmd, tool, ok):
    """035 ①：PostToolUse 落帳記下啟動當下的 PYTEST_ADDOPTS／PYTHONOPTIMIZE（空值也記），Stop 採認時與指令內的指定合併算有效值：
    父行程已設 `-k smoke` 時原樣跑 pytest 只跑子集，不算整體驗證、(a) 擋且訊息講是繼承來的；行內清空才算；沒設或空值照常。"""
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("PYTHONOPTIMIZE", raising=False)
    if inherited is not None:
        monkeypatch.setenv("PYTEST_ADDOPTS", inherited)
    state = _post(monkeypatch, tmp_path, cmd, "1 passed, 40 deselected in 0.10s\n", tool)
    rec = state["verify_receipts"][_SID][0]
    assert {k.upper(): v for k, v in rec["env"].items()} == ({"PYTEST_ADDOPTS": inherited} if inherited is not None else {})
    assert [s["verdict"] for s in rec["sentinels"]] == ["PASS", "DONE"]
    out, _, _ = driven("widget 修好了，完成。", capsys, modified_files=copy.deepcopy(_WIDGET_MODS),
                       verify_receipts=state["verify_receipts"])
    assert ("(a) CLAIM_FIXED_NEEDS_PASS：說「修好」" not in out) is ok, (inherited, cmd, tool)
    if not ok:
        assert "PYTEST_ADDOPTS" in out and "改了驗證選項" in out
        if "PYTEST_ADDOPTS=" not in cmd:
            assert "父行程繼承" in out and "在指令內清空繼承值" in out


def test_035_1_inherited_env_also_gates_file_items_and_declared_commands(tmp_path):
    """035 ①：檔案項目認 pytest 收據與指令項目照原字串比，都從收據 env 起算：繼承 `-k smoke` 的收據不算，訊息講變數；
    行內清空的照算；宣告的指令自帶 PYTEST_ADDOPTS 值時，繼承來的同值也算對上。"""
    _, wt = _two_roots(tmp_path)
    gate = _path_scope_gate(wt)
    inherited = {**_pytest_done(5, wt), "env": {"PYTEST_ADDOPTS": "-k smoke"}}
    reason = gate([inherited])
    assert reason and "PYTEST_ADDOPTS" in reason and "父行程繼承" in reason
    cleared = {**_pytest_done(5, wt, cmd="PYTEST_ADDOPTS='' " + _PYTEST_CMD), "env": {"PYTEST_ADDOPTS": "-k smoke"}}
    assert gate([cleared]) is None
    mod = _mf(_CASE, 5, last_at=_T1, last_seq=3)
    r = {**_rcpt(5, "DONE", 0, cmd="python -m pytest -q", at=_T2), "env": {"PYTEST_ADDOPTS": "-k smoke"}}
    reason = _scope_gate([mod], [r], cmd="python -m pytest -q", chains_of=lambda r: {})
    assert reason and "PYTEST_ADDOPTS" in reason
    r2 = {**_rcpt(5, "DONE", 0, cmd="python -m pytest -q", at=_T2), "env": {"PYTEST_ADDOPTS": "--tb=short"}}
    assert _scope_gate([mod], [r2], cmd="PYTEST_ADDOPTS='--tb=short' python -m pytest -q", chains_of=lambda r: {}) is None


def test_035_1_receipt_without_env_is_not_evidence(driven, capsys):
    """035 ①（照 025 規則 2）：升級前沒記 env 欄的收據看不出範圍有沒有被縮小，(a) 與驗證範圍都不採認，訊息說是沒記啟動環境、
    請重跑；配對：同一筆加上 env={} 就認。"""
    legacy = {k: v for k, v in _rcpt(5, at=_T2).items() if k != "env"}
    out, _, _ = driven("x 修好了，完成。", capsys, modified_files=[_mf(_CODE, 5, last_at=_T1, last_seq=3), _mf(_CASE, 5, last_at=_T1, last_seq=4)],
                       verify_receipts={_SID: [legacy]})
    assert "(a) CLAIM_FIXED_NEEDS_PASS：說「修好」" in out and "沒記啟動環境" in out
    out, _, _ = driven("x 修好了，完成。", capsys, modified_files=[_mf(_CODE, 5, last_at=_T1, last_seq=3), _mf(_CASE, 5, last_at=_T1, last_seq=4)],
                       verify_receipts={_SID: [{**legacy, "env": {}}]})
    assert "ReconcileGate" not in out
    done = {k: v for k, v in _rcpt(5, "DONE", 0, cmd=MEASURE_CMD, at=_T2, kv={"failed": "0"}).items() if k != "env"}
    reason = _scope_gate([_mf(_CASE, 5, last_at=_T1, last_seq=3)], [done], chains_of=lambda r: {})
    assert reason and "沒記啟動環境" in reason
    assert _scope_gate([_mf(_CASE, 5, last_at=_T1, last_seq=3)], [{**done, "env": {}}], chains_of=lambda r: {}) is None


@pytest.mark.parametrize("line, verdicts", [
    ("1 passed, 1 error in 0.12s", ("FAIL", "FAIL")),                 # teardown error：整段看，error 優先
    ("1 error in 0.05s", ("FAIL", "FAIL")),                           # 純 error 也是 FAIL，不是沒哨兵
    ("2 errors in 0.05s", ("FAIL", "FAIL")),
    ("1 failed, 2 passed in 0.5s", ("FAIL", "FAIL")),
    ("1 passed, 1 failed, 1 error in 0.5s", ("FAIL", "FAIL")),
    ("=========== 1 passed, 1 error in 0.1s ===========", ("FAIL", "FAIL")),
    ("3 passed in 0.12s", ("PASS", "DONE")),
    ("5 passed, 1 skipped, 2 deselected, 3 warnings in 1.00s", ("PASS", "DONE")),
    ("3 passed in 65.00s (0:01:05)", ("PASS", "DONE")),
    ("=========== 3 passed in 0.1s ===========", ("PASS", "DONE")),
    ("== 5 passed, 2 skipped, 1 xfailed in 3.2s ==", ("PASS", "DONE")),     # 036 codex：xfailed 不是 failed（預期失敗的正常測試集）
    ("1 failed, 1 xfailed in 0.2s", ("FAIL", "FAIL")),
    ("1 xpassed in 0.1s", ("PASS", "DONE")),
    ("2 passed, 1 xpassed, 1 xfailed in 0.4s", ("PASS", "DONE")),
    ("1 failed, 1 passed, 1 xpassed in 0.3s", ("FAIL", "FAIL")),            # 036b codex 額外驗證的變體固定下來
    ("1 xfailed, 1 error in 0.2s", ("FAIL", "FAIL")),
    ("2 passed, 1 warning in 0.2s", ("PASS", "DONE")),
    ("3 passed, 0 failed in 0.1s", ("PASS", "DONE")),                        # 只跟著 0 不算命中
])
def test_035_2_pytest_summary_mapping_reads_whole_line(line, verdicts):
    """035 ②／036b：config 的兩條 pytest 規則抓整段統計到 ` in `，按完整狀態詞逐組解析：只有非零 failed／error(s) 才 FAIL，
    xfailed／xpassed／skipped／warnings／deselected 不算失敗，PYTEST 與 PYTEST_MEASURE 同一行同結果。"""
    rules = vl.compile_sentinel_rules(_LIVE_CFG["verify_ledger"]["sentinel_regex"])
    got = vl.parse_sentinels(line + "\n", rules)
    assert [(s["name"], s["verdict"]) for s in got] == [("PYTEST", verdicts[0]), ("PYTEST_MEASURE", verdicts[1])], line


def test_036c_pytest_summary_rules_ignore_non_summaries():
    """036c（原 035 ② 共用斷言獨立出來）：內建 pytest 規則只認完整摘要行；什麼都沒跑、只有 deselected、`-rA` 的逐案狀態行都不產生
    成功哨兵，多行輸出只認最後的摘要。"""
    rules = vl.compile_sentinel_rules(_LIVE_CFG["verify_ledger"]["sentinel_regex"])
    for text in ("1 passed\n", "2 skipped in 0.1s\n", "3 deselected in 0.1s\n", "no tests ran in 0.01s\n"):
        assert vl.parse_sentinels(text, rules) == [], text
    multi = "PASSED tests/test_x.py::test_ok\nFAILED tests/test_x.py::test_bad\n1 failed, 1 passed in 0.1s\n"
    assert [(s["name"], s["verdict"]) for s in vl.parse_sentinels(multi, rules)] == [("PYTEST", "FAIL"), ("PYTEST_MEASURE", "FAIL")]


@pytest.mark.parametrize("line, verdict", [
    ("CUSTOM_FAIL 1 item", "FAIL"),
    ("CUSTOM_OK 1 item", "PASS"),
    ("CUSTOM_OK", "PASS"),
    ("CUSTOM_OK 0 fail", "FAIL"),                  # 自訂規則照子字串、FAIL 優先：fail 出現就 FAIL，不套 pytest 的零計數
])
def test_036c_custom_rule_keeps_substring_mapping(line, verdict):
    """036c（036b codex WARN 1）：pytest 統計逐組解析只套用在標了 pytest_summary 的內建兩條規則；自訂規則照子字串映射，
    `CUSTOM_FAIL 1 item` 的 `1 item` 不是統計，照 fail 判 FAIL、`CUSTOM_OK 1 item` 照 ok 判 PASS。"""
    rules = vl.compile_sentinel_rules([{"regex": "^CUSTOM_.*$", "name": "CUSTOM", "verdict_map": {"ok": "PASS", "fail": "FAIL"}}])
    got = vl.parse_sentinels(line + "\n", rules)
    assert [(s["name"], s["verdict"]) for s in got] == [("CUSTOM", verdict)], line


def test_036c_only_builtin_pytest_rules_are_marked_pytest_summary():
    """036c：config 裡兩條內建 pytest 規則都標了 pytest_summary（照統計逐組解析）；沒標的規則編譯後是 False（照子字串）。"""
    compiled = vl.compile_sentinel_rules(_LIVE_CFG["verify_ledger"]["sentinel_regex"])
    assert [(r["name"], r.get("pytest_summary")) for r in compiled] == [("PYTEST", True), ("PYTEST_MEASURE", True)]
    assert vl.compile_sentinel_rules([{"regex": "^X$", "name": "X", "verdict_map": {}}])[0].get("pytest_summary") is False


# 歷來內建 pytest 規則（config 還沒有 pytest_summary 鍵的三個版本），照當時 config.json 原字抄
_OLD_PYTEST_RULES = {
    "d59ee37": ("^(?:=+ )?(?P<verdict>\\d+ (?:passed|failed))", {"failed": "FAIL", "passed": "{ok}"}),
    "1c6a902": ("^(?:=+ )?(?P<verdict>\\d+ (?:passed|failed|errors?)(?:, \\d+ [a-z]+)*) in \\d",
                {"failed": "FAIL", "error": "FAIL", "passed": "{ok}"}),
    "ec80a66": ("^(?:=+ )?(?P<verdict>\\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|warnings?|deselected|rerun)"
                "(?:, \\d+ [a-z]+)*) in \\d", {"failed": "FAIL", "error": "FAIL", "passed": "{ok}", "xpassed": "{ok}"}),
}


def _old_rules(ver):
    regex, vm = _OLD_PYTEST_RULES[ver]
    return [{"regex": regex, "name": n, "verdict_map": {k: v.format(ok=ok) for k, v in vm.items()}}
            for n, ok in (("PYTEST", "PASS"), ("PYTEST_MEASURE", "DONE"))]


@pytest.mark.parametrize("ver, line, verdicts", [
    ("ec80a66", "== 5 passed, 2 skipped, 1 xfailed in 3.2s ==", ("PASS", "DONE")),
    ("ec80a66", "3 passed, 0 failed in 0.1s", ("PASS", "DONE")),
    ("ec80a66", "1 passed, 1 error in 0.1s", ("FAIL", "FAIL")),
    ("1c6a902", "5 passed, 2 skipped, 1 xfailed in 3.2s", ("PASS", "DONE")),
    ("1c6a902", "1 passed, 1 error in 0.1s", ("FAIL", "FAIL")),
    ("d59ee37", "3 passed in 0.1s", ("PASS", "DONE")),
])
def test_036d_new_parser_with_old_config_still_reads_pytest_summary(ver, line, verdicts):
    """036d（036c codex WARN）：保留舊全域 config（內建兩條 pytest 規則沒有 pytest_summary 鍵）、只更新 hooks 時，load_config 只做頂層
    合併補不到旗標；編譯規則時認出歷來內建的 名稱＋regex＋verdict_map，照樣按統計逐組解析，xfailed 不被當 failed。"""
    got = vl.parse_sentinels(line + "\n", vl.compile_sentinel_rules(_old_rules(ver)))
    assert [(s["name"], s["verdict"]) for s in got] == [("PYTEST", verdicts[0]), ("PYTEST_MEASURE", verdicts[1])], (ver, line)


def test_036d_only_exact_builtin_forms_are_upgraded():
    """036d 配對：只同名的自訂規則（regex 或 verdict_map 不同）、明寫 pytest_summary:false 的內建形狀，都照子字串（不升級）。"""
    builtin = _old_rules("ec80a66")[0]
    for rule in ({**builtin, "regex": "^(?P<verdict>\\d+ passed.*)$"},
                 {**builtin, "verdict_map": {"failed": "FAIL", "passed": "PASS", "ok": "PASS"}},
                 {**builtin, "name": "MY_PYTEST"},
                 {**builtin, "pytest_summary": False}):
        assert vl.compile_sentinel_rules([rule])[0]["pytest_summary"] is False, rule
    assert vl.compile_sentinel_rules([builtin])[0]["pytest_summary"] is True


@pytest.mark.parametrize("cmd, tool", [
    ("unset PYTEST_ADDOPTS; python -X utf8 -m pytest -q", "Bash"),
    ("unset PYTEST_ADDOPTS && python -X utf8 -m pytest -q", "Bash"),
    ("env -u PYTEST_ADDOPTS python -X utf8 -m pytest -q", "Bash"),
    ("Remove-Item env:PYTEST_ADDOPTS; python -X utf8 -m pytest -q", "PowerShell"),
])
def test_036b_unsupported_env_clearing_syntax_is_not_accepted(driven, capsys, monkeypatch, tmp_path, cmd, tool):
    """036 codex 建議固定邊界：繼承了 `-k smoke` 時，白名單外的清空寫法（unset、env -u、Remove-Item env:）不算清空，
    收據不採認（它們不是前置設定也不是跑程式的指令）；要清空只認 `PYTEST_ADDOPTS='' …` 與 `$env:PYTEST_ADDOPTS=''`。"""
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k smoke")
    state = _post(monkeypatch, tmp_path, cmd, "1 passed, 40 deselected in 0.10s\n", tool)
    out, _, _ = driven("widget 修好了，完成。", capsys, modified_files=copy.deepcopy(_WIDGET_MODS),
                       verify_receipts=state["verify_receipts"])
    assert "(a) CLAIM_FIXED_NEEDS_PASS：說「修好」" in out, cmd


@pytest.mark.parametrize("out, resp_kind", [
    ("1 passed, 1 error in 0.12s\n", "exit0"),            # teardown error；`| tail -n 1` 讓工具 exit 0
    ("1 error in 0.05s\n", "exit0"),                       # 純 error
    ("2 passed, 1 error in 0.30s\n", "noexit"),            # 字串回應，沒有 exit code
])
def test_035_2_pytest_error_is_fail_through_post_tool_use_and_stop(driven, capsys, monkeypatch, tmp_path, out, resp_kind):
    """035 ②：經 PostToolUse 落帳的 pytest error 摘要是 FAIL 收據（兩個哨兵都 FAIL），也進 failing_tests；
    Stop：(a) 不採認、TestFailGate 擋、驗證範圍的檔案項目也不認。配對：同形狀全綠照常 PASS／DONE。"""
    cmd = "python -X utf8 -m pytest -q lib/verify | tail -n 1"
    state = _post(monkeypatch, tmp_path, cmd, out, resp=(out if resp_kind == "noexit" else None))
    rec = state["verify_receipts"][_SID][0]
    assert [(s["name"], s["verdict"]) for s in rec["sentinels"]] == [("PYTEST", "FAIL"), ("PYTEST_MEASURE", "FAIL")]
    assert rec["exit_code"] == (None if resp_kind == "noexit" else 0)
    assert state["failing_tests"] and state["failing_tests"][0]["pytest"] is True
    o, _, _ = driven("widget 修好了，完成。", capsys, modified_files=copy.deepcopy(_WIDGET_MODS),
                     verify_receipts=state["verify_receipts"], failing_tests=state["failing_tests"])
    assert "TestFailGate" in o
    o, _, _ = driven("widget 修好了，完成。", capsys, modified_files=copy.deepcopy(_WIDGET_MODS), verify_receipts=state["verify_receipts"])
    assert "(a) CLAIM_FIXED_NEEDS_PASS：說「修好」" in o and "沒有任何 PASS 收據" in o
    _, wt = _two_roots(tmp_path)
    red = {**rec, "project_root": str(wt), "cwd": str(wt), "cmd": _PYTEST_CMD}
    assert _path_scope_gate(wt)([red])
    green = _post(monkeypatch, tmp_path, cmd, "3 passed in 0.10s\n")["verify_receipts"][_SID][0]
    assert [s["verdict"] for s in green["sentinels"]] == ["PASS", "DONE"]


def test_receipt_keeps_red_cases_and_whether_the_list_is_complete(monkeypatch, tmp_path):
    """規則 SCOPE_RED_ONLY_ITS_CASES：PostToolUse 落的收據記下紅掉的案例與清單完不完整（紅案數對得上結算行）；綠的不加欄位。
    輸出被 tail 截掉結算行 → red_known=False（Stop 照整條算紅）。"""
    cmd = "python -X utf8 -m pytest -q hooks/verify/verify_a.py hooks/verify/verify_b.py"
    out = "F.\nFAILED hooks/verify/verify_a.py::test_x - assert 0\n1 failed, 1 passed in 0.10s\n"
    rec = _post(monkeypatch, tmp_path, cmd, out, resp={"stdout": out, "stderr": "", "exit_code": 1})["verify_receipts"][_SID][0]
    assert rec["red_cases"] == ["hooks/verify/verify_a.py::test_x"] and rec["red_known"] is True, rec
    cut = "FAILED hooks/verify/verify_a.py::test_x - assert 0\n"
    rec = _post(monkeypatch, tmp_path, cmd, cut, resp={"stdout": cut, "stderr": "", "exit_code": 1})["verify_receipts"][_SID][0]
    assert rec["red_known"] is False, rec
    green = _post(monkeypatch, tmp_path, cmd, "2 passed in 0.10s\n")["verify_receipts"][_SID][0]
    assert "red_cases" not in green and "red_known" not in green


def test_035_3_unreadable_map_blocks_as_judge_error_not_silent_skip(driven, capsys, monkeypatch, tmp_path):
    """035 ③：部位表存在但讀不到（PermissionError）→ _lookup 拋 MapReadError，Stop 走判定錯誤路徑一律擋＋stderr＋guard_log，
    不是「沒有量尺」靜默跳過；配對：表讀得到時驗證範圍閘正常擋「改了沒宣告範圍」。"""
    proj = tmp_path / "proj"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_bytes(_MAP_BYTES)
    mods = [_mf(str(proj / "hooks" / "x.py"), 5, last_at=_T1, last_seq=3), _mf(str(proj / "hooks" / "verify" / "verify_x.py"), 5, last_at=_T1, last_seq=4)]
    out, _, _ = driven("全部完成了。", capsys, modified_files=copy.deepcopy(mods), anti_evasion_report=_aec(5, j="無", k="無"),
                       scope=True)
    assert "VerifyScope" in out and "SCOPE_DECLARED_FOR_CHANGE" in out and "判定錯誤" not in out
    orig = Path.read_text

    def denied(self, *a, **k):
        if self.name == "overview-map.md":
            raise PermissionError(13, "Permission denied", str(self))
        return orig(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(wo.MapReadError, match="存在但讀不到"):
        wo._lookup(str(proj / "hooks" / "x.py"))
    assert wo._lookup(str(tmp_path / "nowhere" / "x.py")) is None                      # 沒有表：照舊 None
    capsys.readouterr()
    assert wo._lookup_quiet(str(proj / "hooks" / "x.py")) is None                      # 注入那幾條路：當沒命中，但 stderr 說一聲
    assert "存在但讀不到" in capsys.readouterr().err
    out, _, logs = driven("全部完成了。", capsys, modified_files=copy.deepcopy(mods), anti_evasion_report=_aec(5, j="無", k="無"),
                          scope=True)
    assert "判定錯誤，一律擋" in out and "MapReadError" in out and "存在但讀不到" in out
    assert "SCOPE_DECLARED_FOR_CHANGE" not in out
    assert any(g in ("scope", "reconcile") and "MapReadError" in str(p.get("error")) for g, p in logs)


def _win_long_short():
    import ctypes
    import tempfile
    if os.name != "nt":
        pytest.skip("8.3 短路徑只在 Windows")
    buf = ctypes.create_unicode_buffer(32768)
    long_ = tempfile.gettempdir()
    n = ctypes.windll.kernel32.GetLongPathNameW(long_, buf, 32768)
    long_ = buf.value if 0 < n < 32768 else long_
    n = ctypes.windll.kernel32.GetShortPathNameW(long_, buf, 32768)
    short = buf.value if 0 < n < 32768 else long_
    if short.lower() == long_.lower():
        pytest.skip("這台機器的暫存目錄沒有 8.3 短名")
    return long_, short


def test_033_2_scratchpad_subdir_long_path_with_short_tempdir_needs_no_case(driven, capsys, monkeypatch, tmp_path):
    """033 ②（9c 實遇）：scratchpad 子目錄的一次性探針（長路徑寫法）、gettempdir 回短路徑 → 經 PostToolUse 不記改檔，
    Stop (d) 不要求案例；配對：同樣的子目錄寫法不在暫存目錄下 → 照記、照擋。"""
    long_, short = _win_long_short()
    from handlers import _shared
    monkeypatch.setattr(_shared.tempfile, "gettempdir", lambda: short)
    probe = long_ + r"\claude\c--Users-x\sess\scratchpad\probe\probe_codegate.py"
    state = _edit_via_post_tool_use(monkeypatch, tmp_path, probe)
    assert not state.get("modified_files")
    out, _, _ = driven("全部完成了。", capsys, modified_files=state.get("modified_files") or [])
    assert "ReconcileGate" not in out
    real = r"c:\proj\scratchpad\probe\probe_codegate.py"
    state = _edit_via_post_tool_use(monkeypatch, tmp_path, real)
    assert [m["path"] for m in state["modified_files"]] == [real]
    out, _, _ = driven("全部完成了。", capsys, modified_files=state["modified_files"])
    assert "(d)" in out and "probe_codegate.py" in out


def _git(repo, *args):
    # 不吃機器的 autocrlf（system config 設 true 時 checkout 會把 LF 寫成 CRLF，雜湊對不上 commit 那刻）
    subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.mark.parametrize("commit_turn", [None, 5])
def test_035_5_restoring_only_code_after_reverting_code_and_case_still_owes(driven, capsys, tmp_path, monkeypatch, commit_turn):
    """035 ⑤（codex 對 033 ① 的反例）：程式與案例同一筆提交 → 反證把兩者都退回舊版 → 只還原程式，案例仍是舊版 →
    (d) 照擋：免補案例的條件不能只看程式檔等於 HEAD，同根案例檔也得仍是提交時的版本。commit 在本 session 之前（commit_turn=None）
    與同 session（last_commit_turn_seq=5）都要擋。真 git repo；案例檔存在用真的 isfile 判。"""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    code, case = repo / "src" / "a.py", repo / "tests" / "test_suite.py"
    code.write_text("def a():\n    return 2\n", encoding="utf-8", newline="\n")
    case.write_text("def test_a():\n    assert a() == 2\n", encoding="utf-8", newline="\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "new code and case")
    code.write_text("def a():\n    return 1\n", encoding="utf-8", newline="\n")                   # 反證：兩者都退回舊版
    case.write_text("def test_a():\n    assert a() == 1\n", encoding="utf-8", newline="\n")
    code.write_text("def a():\n    return 2\n", encoding="utf-8", newline="\n")                   # 只還原程式（等於 HEAD）
    assert subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True).stdout.strip() == "M tests/test_suite.py"
    monkeypatch.setattr(vl, "case_exists", os.path.isfile, raising=False)
    mods = [_mf(str(code), 5, last_at=_T2, last_seq=6), _mf(str(case), 5, last_at=_T1, last_seq=5)]
    extra = {"last_commit_turn_seq": commit_turn} if commit_turn is not None else {}
    out, _, _ = driven("全部完成了。", capsys, modified_files=mods, **extra)
    assert "改了程式碼（a.py）" in out, commit_turn


# ─── 改過又原樣還原的檔不算改碼：內容與 HEAD 相同、本 session 第一次改它之後沒 commit ─────────────────

_DEBT_X = "改了程式碼（x.py）"


def _git(repo: Path, *args: str) -> None:
    import subprocess
    # 不吃機器的 autocrlf（system config 設 true 時 checkout 會把 LF 寫成 CRLF，雜湊對不上 commit 那刻）
    subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture()
def clean_repo(tmp_path, monkeypatch):
    """真 git repo：hooks/x.py 已提交（部位表 hooks/ 列有量尺）；量尺閘的部位查找指到這個 repo。回 (repo, x.py 路徑)。"""
    repo = tmp_path / "repo"
    (repo / "hooks").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "hooks" / "x.py").write_text("x = 1\n", encoding="utf-8", newline="\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    monkeypatch.setattr(wo, "_lookup", _lookup_at(repo))
    return repo, str(repo / "hooks" / "x.py")


def test_reverted_edit_is_not_code_debt_nor_scope_debt(driven, capsys, clean_repo):
    """反證時暫改、又 git checkout 還原的程式檔：內容與 HEAD 相同、本 session 之後沒 commit → (d) 與驗證範圍都不擋；
    配對：檔還改著 → (d) 與驗證範圍照擋。"""
    repo, x = clean_repo
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(x, 5)], scope=True)
    assert _DEBT_X not in out and "VerifyScope" not in out
    (repo / "hooks" / "x.py").write_text("x = 2\n", encoding="utf-8", newline="\n")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(x, 5)], scope=True)
    assert _DEBT_X in out and "VerifyScope" in out


def test_clean_but_committed_since_first_edit_still_owes(driven, capsys, clean_repo):
    """本 session 第一次改它那回合起跑過 commit（last_commit_turn_seq ≥ 該檔 turn_seq）：工作樹乾淨也可能是把改動提交了 → 照擋；
    commit 在第一次改它之前 → 不擋。"""
    _, x = clean_repo
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(x, 5)], last_commit_turn_seq=5)
    assert _DEBT_X in out
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(x, 5)], last_commit_turn_seq=4)
    assert _DEBT_X not in out


def test_subagent_reverted_edit_is_not_code_debt(sub_stop, capsys, clean_repo):
    """子代理 Stop 走同一個 _verify_gates：子代理暫改又還原的檔不欠案例；配對：還改著 → 照擋（無法互動）。"""
    repo, x = clean_repo
    out, _ = sub_stop(capsys, _sub_state(agent_modified_files={"ag1": [_mf(x, 5)]}))
    assert "無法互動，不能放行" not in out and _DEBT_X not in out
    (repo / "hooks" / "x.py").write_text("x = 4\n", encoding="utf-8", newline="\n")
    out, _ = sub_stop(capsys, _sub_state(agent_modified_files={"ag1": [_mf(x, 5)]}))
    assert "無法互動，不能放行" in out and _DEBT_X in out


@pytest.mark.parametrize("kind", ["untracked", "ignored", "staged", "deleted"])
def test_any_git_difference_keeps_debt(driven, capsys, clean_repo, kind):
    """未追蹤、被忽略、已暫存、刪除都算有差（判不出原樣就照算改了）：改到有量尺的部位，驗證範圍照要宣告。(d) 欠案例除了被忽略
    那種都照欠；被 .gitignore 忽略的檔不是本專案程式（EXCLUDED_REGION），不欠案例。"""
    repo, x = clean_repo
    path = x
    if kind == "untracked":
        path = str(repo / "hooks" / "y.py")
        Path(path).write_text("y = 1\n", encoding="utf-8")
    elif kind == "ignored":
        (repo / ".gitignore").write_text("gen/\n", encoding="utf-8")
        (repo / "hooks" / "gen").mkdir()
        path = str(repo / "hooks" / "gen" / "z.py")
        Path(path).write_text("z = 1\n", encoding="utf-8")
    elif kind == "staged":
        Path(x).write_text("x = 3\n", encoding="utf-8", newline="\n")
        _git(repo, "add", "hooks/x.py")
    else:
        Path(x).unlink()
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(path, 5)], scope=True)
    assert (f"改了程式碼（{Path(path).name}）" in out) is (kind != "ignored"), kind
    assert "VerifyScope" in out, kind                                                     # 不是原樣：驗證範圍也照要宣告


def test_040_8_deleted_or_renamed_code_file_no_longer_owes_a_case(driven, capsys, chain, monkeypatch):
    """040 附錄第 3、5 條（總控台定死）：改過的程式檔在 Stop 當下已不存在、而且同根沒有新出現的程式檔（真的刪掉，或改名成不是程式檔）
    → 不再欠補案例；量尺閘照舊看所有改檔。經工具→PostToolUse→Stop、Stop 用真的存在判定與真 git status。舊碼只看修改紀錄，
    刪掉、改名走的檔照樣要案例。（9c 的 test_any_git_difference_keeps_debt[deleted] 用虛構存在判定，驗的是「刪除不算原樣還原」那一層。）"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    state, edit, git, repo, code, _ = chain
    edit(code, 3)                                                                          # 真的改了程式：照欠
    git("rm", "-q", "-f", "src/a.py")                                                      # 改完又整檔刪掉
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **copy.deepcopy(state))
    assert "改了程式碼（a.py" not in out
    tmp = repo / "src" / "tmp_copy.py"
    tmp.parent.mkdir(exist_ok=True)                                                        # git rm 把空的 src/ 一起拿掉了
    tmp.write_text("x = 1\n", encoding="utf-8", newline="\n")
    s2 = copy.deepcopy(state)
    s2["modified_files"].append(_mf(str(tmp), 5, last_at=_T2, last_seq=99))
    tmp.rename(repo / "src" / "tmp_copy.py.txt")                                          # 改名成不是程式檔
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **s2)
    assert "改了程式碼（tmp_copy.py）" not in out and "改了程式碼（a.py" not in out
    s3 = copy.deepcopy(state)
    s3["modified_files"].append(_mf(str(repo / "src" / "kept.py"), 5, last_at=_T2, last_seq=100))
    (repo / "src" / "kept.py").write_text("y = 1\n", encoding="utf-8", newline="\n")
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **s3)
    debt = next((ln for ln in out.split("\\n") if "案例都沒有覆蓋它" in ln), "")
    assert "（kept.py）" in debt                                                            # 配對：還在的照欠
    # 0a：同根冒出的 kept.py 檔名與內容都和 a.py 最後一次寫入時不同，不是它搬過去的 → a.py 算刪除（舊碼：任何新程式檔都分不出，
    # a.py 也照欠）。原內容搬走的照欠見 040_11。


@pytest.mark.parametrize("how", ["git_mv_dir", "plain_mv_file", "git_mv_dir_then_commit"])
def test_040_11_moving_changed_code_away_still_owes(driven, capsys, chain, monkeypatch, how):
    """040 codex 第三、四輪 BLOCK：改了程式後整個目錄改名（git mv src pkg）、用一般 mv 搬到新檔名、或搬完又 commit（工作樹 status 變空）
    → 舊路徑不在了，但同根的 status 或本 session 的提交裡出現新的程式檔 → 判成搬走、照欠補案例；不靠逐一解析每種搬檔寫法。
    舊碼 040 第一版只看檔案在不在、第三輪只看當下 status，搬走（搬完又 commit）就清帳。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    state, edit, git, repo, code, _ = chain
    edit(code, 3)
    if how.startswith("git_mv_dir"):
        git("mv", "src", "pkg")
    else:
        code.rename(repo / "src" / "moved.py")                                            # 沒經過記帳的搬法也要擋
    if how.endswith("then_commit"):
        git("commit", "-qam", "move")
        assert subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True).stdout == ""
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert "改了程式碼（" in out and "a.py" in next((ln for ln in out.split("\\n") if "案例都沒有覆蓋它" in ln), ""), how


def test_040_12_committed_deletion_still_counts_as_deleted(driven, capsys, chain, monkeypatch):
    """040 配對：改了程式後真的刪掉並 commit（提交裡只有刪除、沒有新加進來的程式檔）→ 照算刪掉、不欠補案例。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    state, edit, git, repo, code, _ = chain
    edit(code, 3)
    git("rm", "-q", "-f", "src/a.py")
    git("commit", "-qm", "drop a")
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert "改了程式碼（a.py" not in out


def test_040_9_moving_changed_code_with_git_mv_still_owes_at_new_path(driven, capsys, chain, monkeypatch):
    """040 配套：已不存在的程式檔不欠補案例，所以「改了程式、再 git mv 搬到新檔」要在新路徑照欠，不能靠搬檔清帳。
    經工具→PostToolUse（git mv 的目標記成改檔）→Stop。舊碼 git mv 不記寫入，新路徑沒有修改紀錄。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    state, edit, git, repo, code, _ = chain
    edit(code, 3)
    git("mv", "src/a.py", "src/b.py")
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert "b.py" in next((ln for ln in out.split("\\n") if "案例都沒有覆蓋它" in ln), "")


def test_040_10_change_and_commit_in_one_command_is_not_exempted(driven, capsys, chain):
    """040 codex 第二輪 BLOCK：先改程式＋補案例＋commit（不欠案例），再用同一條 Bash 指令改程式又 commit、沒補案例 →
    PostToolUse 先記這次改檔、再拍 commit 快照：快照時 a.py 已經欠案例，不進不欠清單 → Stop (d) 照擋。
    舊碼先拍快照後記改檔，快照把新內容當成不欠案例的狀態，Stop 比對內容相同就豁免。"""
    state, edit, git, repo, code, case = chain
    edit(code, 3)
    edit(case, 3)
    git("commit", "-qam", "v3")
    code.write_text(_CODE_V.format(4), encoding="utf-8", newline="\n")
    subprocess.run(["git", "-C", str(repo), "commit", "-qam", "v4"], check=True, capture_output=True)
    edit.post("Bash", {"command": "sed -i 's/return 3/return 4/' src/a.py && git commit -qam v4"})
    assert os.path.normpath(str(code)) not in (state.get("commit_snapshot") or {}).get("settled", [])
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert _DEBT_A in out


def test_git_failure_is_reported_not_silent(clean_repo, capsys):
    """git 逾時或回非零 → 照算改了，而且 stderr 說是哪個根、照算改了（不靜默）。"""
    import subprocess
    repo, x = clean_repo

    def timeout(*a, **k):
        raise subprocess.TimeoutExpired("git", 1)
    assert vl.net_unchanged_paths([_mf(x, 5)], _run=timeout) == []
    err = capsys.readouterr().err
    assert str(repo) in err and "照算改了" in err and "TimeoutExpired" in err


def test_undecidable_keeps_debt(driven, capsys, clean_repo, tmp_path):
    """不在 git 工作區、修改紀錄沒有回合、git 逾時或失敗 → 判不出原樣，照算改了（不放寬）。"""
    import subprocess
    _, x = clean_repo
    # 不在 git 工作區用虛構的 c:\proj（pytest 的 tmp 目錄名含 test，找不到專案根時會被 `**/*test*` 當成案例）
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CODE, 5)])
    assert _DEBT_X in out
    assert vl.net_unchanged_paths([_mf(_CODE, 5)]) == []
    assert vl.net_unchanged_paths([_mf(x, 5)]) == [x]                                     # 對照：判得出來就算原樣
    legacy = {k: v for k, v in _mf(x, 5).items() if k not in ("turn_seq", "last_turn_seq")}
    assert vl.net_unchanged_paths([legacy]) == []

    def timeout(*a, **k):
        raise subprocess.TimeoutExpired("git", 1)
    assert vl.net_unchanged_paths([_mf(x, 5)], _run=timeout) == []
    assert vl.net_unchanged_paths([_mf(x, 5)], _run=lambda *a, **k: subprocess.CompletedProcess(a, 128, b"", b"x")) == []


# ─── 037：整根乾淨、git 指定路徑還原進改檔紀錄、裁判 commit 記帳、git 整支時間預算（工具→PostToolUse→Stop 整條鏈） ─────────

import os  # noqa: E402
import subprocess  # noqa: E402
import types  # noqa: E402

_DEBT_A = "改了程式碼（a.py）"
_CODE_V, _CASE_V = "def a():\n    return {}\n", "def test_a():\n    assert a() == {}\n"


def _cover(edit, git, v=3):
    """補一支覆蓋 src/a.py 的案例（tests/test_a.py：檔名照模組取，CASE_COVERS_CHANGE）並加進版控。"""
    p = Path(git.repo) / "tests" / "test_a.py"
    edit(p, v)
    git("add", "tests/test_a.py")
    return p


def _two_version_repo(tmp_path):
    """真 git repo：src/a.py 與 tests/test_suite.py 兩版各一筆提交（舊版回 1、新版回 2），HEAD 是新版。回 (repo, 程式, 案例)。"""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    code, case = repo / "src" / "a.py", repo / "tests" / "test_suite.py"
    for v in (1, 2):
        code.write_text(_CODE_V.format(v), encoding="utf-8", newline="\n")
        case.write_text(_CASE_V.format(v), encoding="utf-8", newline="\n")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", f"v{v}")
    return repo, code, case


@pytest.fixture()
def chain(monkeypatch, tmp_path):
    """一個 session 的工具事件鏈：每一步先真的做（寫檔、跑 git），再把同一個工具呼叫餵給 PostToolUse（一般或裁判入口），state 一路沿用，
    最後交給 Stop。pytest 的 tmp 在系統暫存目錄下，會被當成暫存檔不記改檔：只對受測 repo 底下的路徑關掉這個判斷，其他照舊。
    回 (state, edit(path, 版本, agent_id, judge), git(*args, agent_id, judge), repo, 程式, 案例)。"""
    from handlers import post_tool_use as pt
    from handlers import aec_ledger
    import wg_core
    repo, code, case = _two_version_repo(tmp_path)
    state = {"turn_seq": 5, "session": {"id": _SID, "cwd": str(repo)}}
    real_eph = pt._is_ephemeral_path
    monkeypatch.setattr(pt, "_is_ephemeral_path", lambda p: not vl._under(str(p), str(repo)) and real_eph(p))
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path / "wf")
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    monkeypatch.setattr(aec_ledger, "record_temp_write", lambda *a, **k: None)
    monkeypatch.setattr(wg_core, "read_state", lambda sid: state)                  # 裁判入口自己讀 state
    # PostToolUse 與 Stop 吃同一份設定：driven 預設關驗證範圍閘，commit 快照也照關（要測宣告判法的案把 cfg 打開）
    cfg = {"docdrift": {"enabled": False}, "verify_scope": {"enabled": False}}

    def post(tool, tool_input, agent_id="", judge=False):
        inp = {"session_id": _SID, "tool_name": tool, "tool_input": tool_input, "cwd": str(repo),
               "tool_response": {"stdout": "", "stderr": "", "exit_code": 0}}
        if agent_id:
            inp["agent_id"] = agent_id
        with pytest.raises(SystemExit):
            (pt.handle_judge_post_tool_use if judge else pt.handle_post_tool_use)(inp, cfg)

    def edit(path, v, agent_id="", judge=False):
        Path(path).write_text((_CODE_V if Path(path).name == "a.py" else _CASE_V).format(v), encoding="utf-8", newline="\n")
        post("Edit", {"file_path": str(path)}, agent_id, judge)

    def git(*args, agent_id="", judge=False):
        argv = ["git", "-C", str(repo).replace("\\", "/"), *args]
        # 真跑時不吃機器的 autocrlf；餵給 PostToolUse 的指令字串維持原樣
        subprocess.run(["git", "-c", "core.autocrlf=false", *argv[1:]], check=True, capture_output=True)
        post("Bash", {"command": " ".join(argv)}, agent_id, judge)

    edit.post = post                                  # 複合指令的案例自己先做完動作，再用它送同一條指令的 PostToolUse
    git.repo = repo
    edit.cfg = cfg
    return state, edit, git, repo, code, case


def test_037_git_reverting_both_then_restoring_only_code_still_owes(driven, capsys, chain):
    """037（codex 設計反例，git 版）：新版程式與案例已提交 → `git checkout HEAD~1 -- 程式 案例` 退回舊版 → `git checkout HEAD -- 程式`
    只還原程式 → 經 PostToolUse 兩次 git 還原都記成改檔（最後一次改程式晚於改案例）→ Stop (d) 擋 a.py：案例還留舊版，同根不乾淨，
    程式不剔除。舊碼 git 指令不記改檔，什麼都沒記，直接放行。"""
    state, _, git, _, code, case = chain
    git("checkout", "HEAD~1", "--", "src/a.py", "tests/test_suite.py")
    git("checkout", "HEAD", "--", "src/a.py")
    paths = [m["path"] for m in state.get("modified_files") or []]
    assert os.path.normpath(str(code)) in paths and os.path.normpath(str(case)) in paths
    out, _, _ = driven("全部完成了。", capsys, **state)
    assert _DEBT_A in out


def test_037_git_restoring_everything_back_is_not_code_debt(driven, capsys, chain):
    """配對（新舊都綠）：程式與案例都退回舊版、再都還原成 HEAD，同根全乾淨、本 session 沒 commit → 不算改碼，(d) 不擋。"""
    state, _, git, _, _, _ = chain
    git("checkout", "HEAD~1", "--", "src/a.py", "tests/test_suite.py")
    git("checkout", "HEAD", "--", "src/a.py", "tests/test_suite.py")
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), scope=True, **state)
    assert "ReconcileGate" not in out and "VerifyScope" not in out


def _others_merge(repo, code, case, v):
    """別人（總控台）在本 session 的提交之上再做一筆提交（把 main 合進工作分支）：不經本 session 的 PostToolUse。"""
    code.write_text(_CODE_V.format(v), encoding="utf-8", newline="\n")
    case.write_text(_CASE_V.format(v), encoding="utf-8", newline="\n")
    _git(repo, "commit", "-qam", f"others v{v}")


def test_b13_revert_red_then_restore_after_others_commit_not_owed(driven, capsys, chain):
    """B13 真實序列（track-gate-bypass 派工 004）：改程式＋補案例 → commit（快照）→ 退回舊版看紅、再還原成 HEAD →
    總控台把 main 合進工作分支（HEAD 變成別人的提交、同根檔內容跟快照不同）→ Stop 不該欠案例：檔內容等於 HEAD，
    HEAD 是別人在本 session 提交之上做的，同根本 session 改過的檔全等於 HEAD。舊碼 HEAD 一律不算、快照又對不上 → 照欠。"""
    state, edit, git, repo, code, case = chain
    edit(code, 3)
    edit(case, 3)
    git("commit", "-qam", "v3")
    git("restore", "--source=HEAD~1", "--worktree", "--", "src/a.py")
    git("restore", "--source=HEAD", "--worktree", "--", "src/a.py")
    _others_merge(repo, code, case, 4)
    assert "commit_snapshot" in state and state.get("committed_new_code")                       # 前置：本 session 有提交、有快照
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert "改了程式碼（a.py）" not in out, out


def test_b13_others_commit_but_case_left_old_still_owes(driven, capsys, chain):
    """配對（037 的反例在別人提交之後）：程式與案例都退回舊版、只把程式還原成 HEAD → 案例還留舊版，同根不全等於 HEAD → 照欠。"""
    state, edit, git, repo, code, case = chain
    edit(code, 3)
    edit(case, 3)
    git("commit", "-qam", "v3")
    _others_merge(repo, code, case, 4)
    git("checkout", "HEAD~2", "--", "src/a.py", "tests/test_suite.py")
    git("checkout", "HEAD", "--", "src/a.py")
    out, _, _ = driven("全部完成了。", capsys, **state)
    assert _DEBT_A in out


def test_b13_head_is_own_commit_still_not_a_ref():
    """HEAD 是本 session 自己的提交、或不在本 session 提交之上（不是別人接著做的）→ 不算已提交版本（原規則不變）。"""
    refs = {"HEAD": "h2", "main": "m1"}
    assert rr.committed_refs(["h2"], refs, head_after_own=True) == ["main"]
    assert rr.committed_refs(["h1"], refs) == ["main"]
    assert rr.committed_refs(["h1"], refs, head_after_own=True) == ["HEAD", "main"]


def test_037_edit_reverting_both_then_restoring_only_code_still_owes(driven, capsys, chain):
    """037 整根不剔除（Edit 版，036 test_035_5 的情境走整條鏈）：Edit 把程式與案例改回舊版、再只把程式 Edit 回 HEAD 的內容 →
    程式與 HEAD 相同但案例不同 → 這個根一個都不剔除 → (d) 擋。舊碼只看程式自己乾淨就剔除，案例反而清了帳。"""
    state, edit, _, _, code, case = chain
    edit(code, 1)
    edit(case, 1)
    edit(code, 2)
    out, _, _ = driven("全部完成了。", capsys, **state)
    assert _DEBT_A in out


def test_037_subagent_judged_with_other_agents_dirty_files_in_same_root(sub_stop, capsys, chain):
    """037 整根判定看 session 全部改檔（含其他子代理）：子代理 ag1 把程式改了又改回 HEAD，ag2 改了同根的案例還沒還原 →
    ag1 的 SubagentStop 照擋 (d)（責任仍分代理：ag1 只看自己改的檔）；配對：ag2 也還原 → ag1 不欠。舊碼只看 ag1 自己的檔。"""
    state, edit, _, _, code, case = chain
    edit(code, 1, agent_id="ag1")
    edit(code, 2, agent_id="ag1")
    edit(case, 1, agent_id="ag2")
    out, _ = sub_stop(capsys, state, agent_id="ag1")
    assert "無法互動，不能放行" in out and _DEBT_A in out
    edit(case, 2, agent_id="ag2")
    out, _ = sub_stop(capsys, state, agent_id="ag1")
    assert _DEBT_A not in out


def test_037_judge_edit_then_commit_still_owes(monkeypatch, capsys, chain):
    """037 裁判 commit 記帳：裁判子 session 用 Edit 改程式 → 真的 git commit → 裁判 PostToolUse 記下 commit 回合 → 裁判 Stop 照擋 (d)：
    工作樹乾淨是因為提交了，不是沒改。舊碼裁判入口不記 commit，提交後乾淨就被剔除、放行。"""
    state, edit, git, _, code, _ = chain
    state.update({"turn_seq": 0, "judge": True})
    edit(code, 3, judge=True)
    git("commit", "-qam", "judge", judge=True)
    assert _DEBT_A in _judge_stop(monkeypatch, capsys, state)
    assert state.get("last_commit_turn_seq") == 0


def test_037_judge_edit_then_restore_without_commit_is_not_debt(monkeypatch, capsys, chain):
    """配對（新舊都綠）：裁判 Edit 改程式又改回 HEAD 的內容、沒 commit → 不算改碼，裁判 Stop 不擋。"""
    state, edit, _, _, code, _ = chain
    state.update({"turn_seq": 0, "judge": True})
    edit(code, 3, judge=True)
    edit(code, 2, judge=True)
    assert _DEBT_A not in _judge_stop(monkeypatch, capsys, state)


def test_037_git_budget_is_shared_across_roots(tmp_path, monkeypatch, capsys):
    """037 BLOCK：兩個根各有一個改了又還原的檔；替身讓每次 git 花 2.8 秒（拿到的時間不夠就逾時）→ 整支累計不超過預算 4 秒、
    每個子行程只拿剩餘預算；第一個根的 status 逾時、第二個根沒得查 → 兩個都照算改了，stderr 印出沒查的根。
    舊碼每次各給 3 秒，四次累計 11.2 秒，超過 Stop hook 的 10 秒。"""
    roots = []
    for name in ("live", "wt"):
        r = tmp_path / name
        (r / "hooks").mkdir(parents=True)
        _git(r, "init", "-q")
        _git(r, "config", "user.email", "t@t")
        _git(r, "config", "user.name", "t")
        (r / "hooks" / "x.py").write_text("x = 1\n", encoding="utf-8", newline="\n")
        _git(r, "add", ".")
        _git(r, "commit", "-qm", "init")
        roots.append(r)
    clock = {"t": 100.0, "spent": 0.0, "timeouts": []}
    real_time = vl.time
    monkeypatch.setattr(vl, "time", types.SimpleNamespace(monotonic=lambda: clock["t"], time=real_time.time,
                                                           sleep=real_time.sleep))

    def slow_git(argv, **kw):
        clock["timeouts"].append(kw.get("timeout"))
        took = min(2.8, float(kw.get("timeout") or 2.8))
        clock["t"] += took
        clock["spent"] += took
        if took < 2.8:
            raise subprocess.TimeoutExpired(argv[3], kw.get("timeout"))
        return subprocess.run(argv, **kw)
    mods = [_mf(str(r / "hooks" / "x.py"), 5) for r in roots]
    monkeypatch.setattr(vl, "GIT_BUDGET_S", 4.0, raising=False)          # 本案要量的就是預算本身：蓋回模組預設，不吃 autouse 的 20 秒
    assert vl.net_unchanged_paths(mods, None, _run=slow_git) == []
    assert clock["spent"] <= 4.0 + 1e-9, clock
    assert all(t is not None and t <= 3.0 for t in clock["timeouts"])
    err = capsys.readouterr().err
    assert str(roots[1]) in err and "照算改了" in err and "時間預算" in err


def test_037_git_budget_exhausted_keeps_debt_through_stop(driven, capsys, chain, monkeypatch):
    """037 BLOCK 經 Stop：預算用完（GIT_BUDGET_S=0）時改了又還原的程式不剔除，(d) 照擋；配對：預算正常就剔除、不擋。"""
    state, edit, _, _, code, _ = chain
    edit(code, 1)
    edit(code, 2)
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **copy.deepcopy(state))
    assert "ReconcileGate" not in out
    monkeypatch.setattr(vl, "GIT_BUDGET_S", 0.0, raising=False)
    out, _, _ = driven("全部完成了。", capsys, **copy.deepcopy(state))
    assert _DEBT_A in out


@pytest.mark.parametrize("kind", ["staged_then_reverted", "tracked_but_ignored"])
def test_037_codex_pass_pairs_keep_debt(driven, capsys, clean_repo, kind):
    """codex 010 第 5 條建議補的真 git 配對（新舊都綠）：暫存後工作樹改回 HEAD、已追蹤但符合 .gitignore → 不是原樣（NET_UNCHANGED 不剔），照擋。
    原本第三案「只留空白差異」改由 045 規則 COMMENT_ONLY_CHANGE 接手（見 test_037_whitespace_only_is_comment_only_change）。"""
    repo, x = clean_repo
    if kind == "staged_then_reverted":
        Path(x).write_text("x = 3\n", encoding="utf-8", newline="\n")
        _git(repo, "add", "hooks/x.py")
        Path(x).write_text("x = 1\n", encoding="utf-8", newline="\n")
    else:
        (repo / ".gitignore").write_text("hooks/x.py\n", encoding="utf-8")
        Path(x).write_text("x = 5\n", encoding="utf-8", newline="\n")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(x, 5)])
    assert _DEBT_X in out, kind


def test_037_whitespace_only_is_comment_only_change(driven, capsys, clean_repo, monkeypatch):
    """045 規則 COMMENT_ONLY_CHANGE 取代 037 的第三案：只留空白差異（`x = 1 ` 多一個空白）ast 形狀與 HEAD 相同 → 不算改碼、不擋；
    NET_UNCHANGED 仍不剔它（不是原樣），所以擋不擋由這條規則決定。配對：改了值 → 照擋。"""
    monkeypatch.setattr(vl, "REF_BUDGET_S", 20.0, raising=False)                       # 負載下 git 慢，不讓預算當判定
    monkeypatch.setattr(vl, "GIT_BUDGET_S", 20.0, raising=False)
    repo, x = clean_repo
    Path(x).write_text("x = 1 \n", encoding="utf-8", newline="\n")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(x, 5)])
    assert _DEBT_X not in out, out
    Path(x).write_text("x = 2\n", encoding="utf-8", newline="\n")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(x, 5)])
    assert _DEBT_X in out


@pytest.mark.parametrize("who", ["subagent", "judge"])
def test_039_directory_restore_is_unknown_write_through_stop(sub_stop, monkeypatch, capsys, chain, who):
    """把程式與案例改回舊版、再用 `git -C src checkout .` 只還原程式目錄 → PostToolUse 記成目標不明的寫入（不當成沒寫）；
    子代理／裁判 Stop 不為目標不明擋（UNKNOWN_TARGET_LOGGED：只留帳）。"""
    state, edit, git, _, code, case = chain
    kw = {"agent_id": "ag1"} if who == "subagent" else {"judge": True}
    if who == "judge":
        state.update({"turn_seq": 0, "judge": True})
    edit(code, 1, **kw)
    edit(case, 1, **kw)
    git("-C", "src", "checkout", ".", **kw)
    out = sub_stop(capsys, state, agent_id="ag1")[0] if who == "subagent" else _judge_stop(monkeypatch, capsys, state)
    assert "寫入目標不明" not in out
    unknown = (state.get("agent_unknown_writes") or {}).get("ag1") if who == "subagent" else state.get("unknown_writes")
    assert unknown and unknown[-1]["target"].startswith("UNKNOWN:")


# ─── 040：每次擋都查放行、預算回合以使用者真打字的回合計、dict 回應沒有 exit 欄時認 pytest 摘要 ──────────────────────

_PEER_MSG = '<cross-session-message from="uds:\\\\.\\pipe\\x" from-name="claude-9f">總控台：收到，繼續。</cross-session-message>'
_TASK_NOTE = ("<task-notification>\n<task-id>b1</task-id>\n<status>completed</status>\n"
              "<summary>Background command completed (exit code 0)</summary>\n</task-notification>")


@pytest.fixture()
def gate_run(driven, tmp_path, monkeypatch):
    """真 Stop 入口＋真 transcript 檔（放行答案寫在裡面）＋真 UserPromptSubmit 推進回合。state 一路沿用。
    回 (state, stop(text) → (out, logs), ups(prompt), ask(answer))；改了程式沒補案例，(d) 會擋。"""
    tp = tmp_path / "t.jsonl"
    tp.write_text("", encoding="utf-8")
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: tp)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    monkeypatch.delenv("CLAUDE_COMPANION_JUDGE", raising=False)
    state = {"turn_seq": 4, "session": {"cwd": str(tmp_path)}, "modified_files": [_mf(_CODE, 5, last_at=_T1, last_seq=3)]}
    _ups_turn(monkeypatch, state, "改 hooks/x.py")                          # 使用者打字開回合：turn 5

    def stop(text="全部完成了。"):
        out, after, logs = driven(text, capsys_ref[0], **copy.deepcopy(state))
        state.clear()
        state.update(after)
        return out, logs

    def ups(prompt):
        _ups_turn(monkeypatch, state, prompt)

    def ask(answer):
        with open(tp, "a", encoding="utf-8") as f:
            f.write(_ask_line(answer))

    capsys_ref = [None]
    return state, stop, ups, ask, capsys_ref


def _released(logs):
    return [p for g, p in logs if g == "reconcile" and p.get("event") == "user_release"]


def test_040_1_release_answer_after_first_block_releases(gate_run, capsys):
    """040 規則 (a)：第 1 次擋（還沒擋滿）之後使用者在 AskUserQuestion（題目含標記）選「放行這一回合」→ 下一個 Stop 就放行、
    guard log 記 user_release；之後背景通知、同伴訊息進來都不算新回合，仍不擋；使用者真打字開新回合才又擋。
    舊碼只在擋滿才查放行，第 1 次擋之後的答案被忽略，第 2 次照擋。"""
    state, stop, ups, ask, ref = gate_run
    ref[0] = capsys
    out, _ = stop()
    assert "(d)" in out and "本回合已擋" not in out                                       # 第 1 次擋，還沒擋滿
    ask(rl.OPT_RELEASE)
    out, logs = stop()
    assert "ReconcileGate" not in out
    rel = _released(logs)
    assert rel and rel[0]["via"] == "ask" and "(d)" in rel[0]["reason"]
    for p in (_TASK_NOTE, _PEER_MSG):                                                      # 非使用者的回合推進：放行照撐
        ups(p)
        out, _ = stop()
        assert "ReconcileGate" not in out, p[:20]
    ups("繼續改")                                                                           # 使用者真打字：新回合
    out, _ = stop()
    assert "(d)" in out


def test_no_case_user_release_is_remembered_until_the_file_changes(driven, capsys, tmp_path, monkeypatch):
    """NO_CASE_NEEDS_USER 端到端：宣告 no_case → (d) 擋並帶理由 → 使用者在【收尾放行確認】放行 → 下一個使用者回合沒再改就不重問
    （舊碼沒有這筆紀錄，每回合都要再問）；檔再改了 → 又要裁。guard log 的 user_release 記下裁定了哪些檔。"""
    tp = tmp_path / "t.jsonl"
    tp.write_text("", encoding="utf-8")
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: tp)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    monkeypatch.delenv("CLAUDE_COMPANION_JUDGE", raising=False)
    decl = _declared(_RELATED_CMD)
    decl[_SID][-1]["no_case"] = [{"path": _CODE, "reason": "只改擋訊息字串"}]
    state = {"turn_seq": 4, "session": {"cwd": str(tmp_path)}, "modified_files": [_mf(_CODE, 5, last_at=_T1, last_seq=3)],
             "verify_scope": decl, "verify_receipts": {_SID: [_rcpt(5, at=_T2, seq=4)]}}
    _ups_turn(monkeypatch, state, "改 hooks/x.py 的擋訊息")

    def stop():
        out, after, logs = driven("全部完成了。", capsys, scope=True, **copy.deepcopy(state))
        state.clear()
        state.update(after)
        return out, logs

    out, _ = stop()
    assert "NO_CASE_NEEDS_USER" in out and "只改擋訊息字串" in out, out
    with open(tp, "a", encoding="utf-8") as f:
        f.write(_ask_line(rl.OPT_RELEASE))
    out, logs = stop()
    assert "ReconcileGate" not in out and any(p.get("no_case_approved") == ["x.py"] for p in _released(logs)), logs
    _ups_turn(monkeypatch, state, "繼續")                                                  # 使用者真打字：新回合
    out, _ = stop()
    assert "NO_CASE_NEEDS_USER" not in out and "ReconcileGate" not in out, out
    state["modified_files"] = [_mf(_CODE, 6, last_at=_T3, last_seq=9)]                     # 又改了 x.py
    out, _ = stop()
    assert "NO_CASE_NEEDS_USER" in out, out


def test_040_2_release_answer_before_block_does_not_count(gate_run, capsys):
    """040 規則 (a) 配對（新舊都綠）：擋之前就答過放行、擋之後沒再答 → 仍擋。"""
    state, stop, ups, ask, ref = gate_run
    ref[0] = capsys
    ask(rl.OPT_RELEASE)
    out, _ = stop()
    assert "(d)" in out
    out, logs = stop()
    assert "(d)" in out and not _released(logs)


@pytest.mark.parametrize("prompt", [_PEER_MSG, _TASK_NOTE])
def test_040_3_peer_or_notification_does_not_reset_count(gate_run, capsys, prompt):
    """040 規則 (b)：擋一次 → 同伴訊息／背景通知經 UserPromptSubmit 進來（turn_seq 會 +1）→ 再 Stop：次數接著算是 2、不重置；
    第 3 次送擋滿訊息。舊碼以 turn_seq 計次，有人傳訊息就歸零、永遠擋不滿。"""
    state, stop, ups, ask, ref = gate_run
    ref[0] = capsys
    stop()
    assert {k: state["reconcile_gate_turn"][_SID][k] for k in ("turn", "count")} == {"turn": 5, "count": 1}
    ups(prompt)
    assert state["turn_seq"] == 6 and state["turn_prompts_seq"] == 5
    stop()
    assert {k: state["reconcile_gate_turn"][_SID][k] for k in ("turn", "count")} == {"turn": 5, "count": 2}
    out, _ = stop()
    assert "本回合已擋 2 次仍未解" in out and rl.RELEASE_TAG in out


def test_040_4_user_typed_new_turn_resets_count(gate_run, capsys):
    """040 規則 (b) 配對（新舊都綠）：擋一次 → 使用者真打字開新回合 → 次數重置（預算照使用者的回合給）。"""
    state, stop, ups, ask, ref = gate_run
    ref[0] = capsys
    stop()
    ups("再看一次")
    assert state["turn_prompts_seq"] == 6
    stop()
    assert {k: state["reconcile_gate_turn"][_SID][k] for k in ("turn", "count")} == {"turn": 6, "count": 1}


@pytest.mark.parametrize("summary, ok", [("718 passed in 5.20s", True), ("1 failed, 717 passed in 5.20s", False)])
def test_040_5_dict_response_without_exit_uses_pytest_summary(driven, capsys, monkeypatch, tmp_path, summary, ok):
    """040 規則 (c)：Bash 成功時 tool_response 是 dict（stdout／stderr／interrupted，沒有 exit 欄）→ exit 未知；
    認 pytest 摘要行：`718 passed` 是合格 PASS（說修好放行），`1 failed` 是 FAIL（不採認、TestFailGate 擋）。經 PostToolUse→Stop。"""
    resp = {"stdout": "........\n" + summary + "\n", "stderr": "", "interrupted": False, "isImage": False}
    state = _post(monkeypatch, tmp_path, "python -X utf8 -m pytest -q tests/test_widget.py", "", resp=resp)
    rec = state["verify_receipts"][_SID][0]
    assert rec["exit_code"] is None
    assert [s["verdict"] for s in rec["sentinels"]] == (["PASS", "DONE"] if ok else ["FAIL", "FAIL"])
    out, _, _ = driven("widget 修好了，完成。", capsys, modified_files=copy.deepcopy(_WIDGET_MODS),
                       verify_receipts=state["verify_receipts"], failing_tests=state.get("failing_tests") or [])
    if ok:
        assert "ReconcileGate" not in out and "TestFailGate" not in out
    else:
        assert "TestFailGate" in out


def test_040_6_notification_then_user_prompt_is_a_new_user_turn(gate_run, capsys):
    """040 codex BLOCK：放行並收尾（Stop 關回合）→ 背景通知先進來（續跑回合）→ 下一次 Stop 之前使用者打字交代新任務 →
    這一則仍是使用者開的新回合：turn_prompts_seq 前進、上一回合的放行不沿用，(d) 照擋。舊碼通知把 turn_open 設成 True，
    使用者的字被當成同回合追加，序號不前進，舊放行把新任務的查核原因清掉。"""
    state, stop, ups, ask, ref = gate_run
    ref[0] = capsys
    stop()
    ask(rl.OPT_RELEASE)
    out, _ = stop()
    assert "ReconcileGate" not in out
    ups(_TASK_NOTE)
    assert state["turn_prompts_seq"] == 5
    ups("接著改 hooks/y.py")
    assert state["turn_prompts_seq"] == 7
    out, _ = stop()
    assert "(d)" in out


@pytest.mark.parametrize("flow, owed", [
    ("restore_code", False),           # commit 時有案例覆蓋 → 反證把程式退回舊版又還原 → 不重算
    ("revert_both_restore_code", False),  # 程式與案例都退回、只還原程式 → 案例還在、照樣覆蓋：不重欠
    ("owed_at_commit", False),         # 案例先改、程式後改再 commit → 不比先後：不欠
    ("no_cover", True),                # 只改了不提到 a.py 的案例 → 沒有覆蓋：照欠（單一義務，不因反證多一次）
])
def test_040_7_reversal_after_commit_does_not_double_block(driven, capsys, chain, flow, owed):
    """使用者裁定「commit 後反證多擋一次要修」：PostToolUse 看到 commit 時記下本 session 改過的檔的內容雜湊與當時不欠案例的程式檔；
    之後同根本 session 改過的每個檔內容都回到那一刻、而那個程式檔當時不欠案例 → (d) 不重算。只免補案例，量尺照舊。
    經真 git、工具→PostToolUse→Stop。舊碼 commit 之後的 git checkout 還原一律算改碼，restore_code 那組也擋。"""
    state, edit, git, _, code, case = chain
    if flow == "owed_at_commit":
        _cover(edit, git)
        edit(code, 3)
    else:
        edit(code, 3)
        edit(case, 3) if flow == "no_cover" else _cover(edit, git)
    git("commit", "-qam", "v3")
    assert state["last_commit_turn_seq"] == 5
    if flow == "revert_both_restore_code":
        git("checkout", "HEAD~1", "--", "src/a.py", "tests/test_suite.py")
    else:
        git("checkout", "HEAD~1", "--", "src/a.py")
    git("checkout", "HEAD", "--", "src/a.py")
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert (_DEBT_A in out) is owed, flow


def test_040_13_transcript_from_hook_input_when_session_moved_into_worktree(driven, capsys, tmp_path, monkeypatch):
    """040 現場：session 開場在 live、中途 EnterWorktree，transcript 改寫在 worktree 那個資料夾；Stop 拿 state 裡開場的 cwd 推路徑
    找不到（driven 把那條路設成找不到），擋的位置記成 0、AskUserQuestion 的放行答案讀不到，使用者選放行也沒用。
    改成先用 hook 輸入的 transcript_path：擋的位置是真的檔長、擋之後的放行答案認得到。舊碼只用 cwd 推。"""
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    tp = tmp_path / "C--wt-slug" / f"{_SID}.jsonl"
    tp.parent.mkdir()
    tp.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "改 x.py"}}, ensure_ascii=False) + "\n",
                  encoding="utf-8")
    hook_in = {"transcript_path": str(tp)}
    base = {"modified_files": [_mf(_CODE, 5, last_at=_T1, last_seq=3)], "session": {"cwd": str(tmp_path)}}
    out, st1, _ = driven("全部完成了。", capsys, hook_input=hook_in, **base)
    assert "(d)" in out and st1["last_block"][_SID]["reconcile"]["offset"] == tp.stat().st_size > 0
    with open(tp, "a", encoding="utf-8") as f:
        f.write(_ask_line(rl.OPT_RELEASE))
    keep = {k: st1[k] for k in ("last_block", "reconcile_gate_turn", "modified_files", "session")}
    out, _, logs = driven("全部完成了。", capsys, hook_input=hook_in, **keep)
    assert "ReconcileGate" not in out and _released(logs)


# ─── track-know：部位表類別 knowledge 的部位不欠 (d)、也不能替寫碼部位清帳 ─────────────────────────────
# 判法只看路徑屬部位表哪一列（lib/overview_hub.path_kind，與 OverviewHub 同一份），不看副檔名、不看 git 狀態。
# 舊碼（is_code_file 只看副檔名）：信箱、記憶暫存、文件目錄下的 .py 也欠案例；信箱裡的 test_a.py 能替 tools/a.py 清帳。

_KNOW_MAP = (
    "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
    "| `tools/` | 工具 | 無 | 無 | code |\n"
    "| `scripts/` | 腳本 | 無 | 無 |  |\n"
    "| `workflow/inbox/` | 派工信箱 | 無 | 無 | knowledge |\n"
    "| `memory/` | 記憶 | 無 | 無 | knowledge |\n"
    "| `_AIDocs/` | 文件 | 無 | 無 | 知識 |\n"
)
_KNOW_SRC = "def f(x):\n    return x + 1\n"


def _know_debt(name: str) -> str:
    return f"改了程式碼（{name}）"


@pytest.fixture()
def know_repo(tmp_path):
    """真 git repo，根上放帶「類別」欄的部位表；回 (repo, 寫檔函式)。"""
    repo = tmp_path / "krepo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "overview-map.md").write_text(_KNOW_MAP, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")

    def put(rel: str, text: str = _KNOW_SRC) -> str:
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        return str(p)
    return repo, put


@pytest.mark.parametrize("rel,owed", [
    ("tools/a.py", True),
    ("workflow/inbox/to-x/a.py", False),
    ("memory/_staging/a.py", False),
    ("_AIDocs/a.py", False),
])
def test_know_same_file_owes_in_code_part_not_in_knowledge_part(driven, capsys, know_repo, rel, owed):
    """同一份內容：放在 tools/（類別 code）欠案例；放在信箱、記憶暫存、文件目錄（類別 knowledge／知識）不欠。"""
    _, put = know_repo
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(put(rel), 5)])
    assert (_know_debt("a.py") in out) is owed, rel


def test_know_unmarked_row_and_unlisted_path_default_to_code(driven, capsys, know_repo):
    """沒標類別的列（scripts/）與表上沒列的路徑（根目錄的 b.py、子字串才撞到 memory/ 的 lib/memory/c.py）一律算寫碼部位。"""
    _, put = know_repo
    for rel in ("scripts/a.py", "b.py", "lib/memory/c.py"):
        out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(put(rel), 5)])
        assert _know_debt(Path(rel).name) in out, rel


def test_know_case_in_knowledge_part_cannot_clear_code_debt(driven, capsys, know_repo):
    """案例側也看部位：信箱裡的 test_a.py 不能替 tools/a.py 清帳；tools/verify/ 下的案例照常清帳。"""
    _, put = know_repo
    code = put("tools/a.py")
    inbox_case = put("workflow/inbox/to-x/test_a.py", "def test_a():\n    assert True\n")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(code, 5), _mf(inbox_case, 5)])
    assert _know_debt("a.py") in out
    real_case = put("tools/verify/test_a.py", "def test_a():\n    assert True\n")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(code, 5), _mf(inbox_case, 5), _mf(real_case, 5)],
                       anti_evasion_report=_aec(5, j="無", k="無"))
    assert "ReconcileGate" not in out


def test_know_deleted_inbox_file_not_owed_even_with_new_code_in_status(driven, capsys, know_repo, monkeypatch):
    """claude-91 現場：信箱裡的 .py 被刪掉，同根另有未追蹤的程式檔（看起來像搬走）→ 舊碼照欠；知識部位的檔根本不進 (d)。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    _, put = know_repo
    gone = put("workflow/inbox/to-x/verify_x.py")
    Path(gone).unlink()
    put("tools/new_tool.py")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(gone, 5)])
    assert _know_debt("verify_x.py") not in out


def test_know_code_moved_into_knowledge_part_still_owes(driven, capsys, know_repo, monkeypatch):
    """寫碼部位的程式改完 mv 進信箱：原路徑已不存在，但同根出現新的程式檔（信箱那份，vanished 的 new_code 不過類別排除）
    → 原路徑照欠；信箱那份本身不欠。防回歸：不讓「搬進知識區」變成清帳法。codex 審 a6323cb 新案缺口。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    repo, put = know_repo
    code = put("tools/a.py")
    _git(repo, "add", "tools/a.py")
    _git(repo, "commit", "-qm", "a")
    put("tools/a.py", _KNOW_SRC + "# changed\n")
    moved = repo / "workflow" / "inbox" / "to-x" / "a.py"
    moved.parent.mkdir(parents=True)
    Path(code).replace(moved)
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(code, 5), _mf(str(moved), 5)])
    assert "✗ (d) " in out and "改了程式碼（a.py）" in out    # 舊碼兩份都欠（a.py、a.py），新碼只欠 tools/a.py（045 擋訊息格式：字母後接規則名）


def test_know_knowledge_part_ruler_and_commit_snapshot_unchanged(driven, capsys, tmp_path):
    """知識部位只移出 (d) 與定位三行：表上有量尺的知識部位改了，照樣要宣告驗證範圍（量尺當參考出現）；commit 快照照記
    知識部位的改檔內容。codex 審 a6323cb 新案缺口（契約 3、5 的直接斷言）。"""
    repo = tmp_path / "mrepo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 量尺（量法｜指令｜門檻） | 類別 |\n|---|---|---|---|---|---|\n"
        "| `memory/` | 記憶 | 無 | 無 | 索引一致｜`python -X utf8 tools/check.py`｜exit 0 | knowledge |\n", encoding="utf-8")
    _git(repo, "init", "-q")
    p = repo / "memory" / "_staging" / "a.py"
    p.parent.mkdir(parents=True)
    p.write_text(_KNOW_SRC, encoding="utf-8")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(str(p), 5)], scope=True)
    assert "[Guardian:VerifyScope]" in out and "SCOPE_DECLARED_FOR_CHANGE" in out and "部位【記憶】`python -X utf8 tools/check.py`" in out
    assert _know_debt("a.py") not in out
    snap = vl.commit_snapshot([_mf(str(p), 5)], 5, vl.reconcile_cfg({}), lambda _p: str(repo))
    key = vl.canon_path(str(p))                                                             # 快照鍵用 canon_path（SAME_FILE）
    assert key in snap["files"] and snap["files"][key] is not None


@pytest.mark.parametrize("child", ["./docs/build/", "docs/x/../build/"])
def test_know_code_child_row_written_with_dot_segments_still_owes(driven, capsys, tmp_path, child):
    """knowledge 父列 `docs/` 底下的 code 子列寫成 `./docs/build/` 或 `docs/x/../build/`：子列照樣蓋住 docs/build/，那裡的程式欠案例；
    父列其他地方的 .py 不欠。舊碼表列前綴沒消 `./`、`..`，子列比不到、落回 knowledge，真程式免 (d)。console codex 審 ec4f9e9 BLOCK 1。"""
    repo = tmp_path / "drepo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
        f"| `docs/` | 文件 | 無 | 無 | knowledge |\n| `{child}` | 建置 | 無 | 無 | code |\n", encoding="utf-8")
    _git(repo, "init", "-q")
    code, note = repo / "docs" / "build" / "a.py", repo / "docs" / "b.py"
    for p in (code, note):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_KNOW_SRC, encoding="utf-8")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(str(code), 5), _mf(str(note), 5)])
    assert _know_debt("a.py") in out and "b.py" not in out


def test_know_no_map_keeps_extension_rule(driven, capsys, tmp_path):
    """沒有部位表的專案行為不變：信箱路徑下的 .py 照副檔名算程式檔。"""
    repo = tmp_path / "nomap"
    (repo / "workflow" / "inbox").mkdir(parents=True)
    _git(repo, "init", "-q")
    p = repo / "workflow" / "inbox" / "a.py"
    p.write_text(_KNOW_SRC, encoding="utf-8")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(str(p), 5)])
    assert _know_debt("a.py") in out


# ─── 042：內容回到快照的豁免要連暫存區一起看、amend 不蓋掉有效豁免、已不存在的新檔、排除區、每回合一次的閘 ──────────────

def _status(repo):
    return subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()


def test_042_0_snapshot_exemption_needs_clean_index(driven, capsys, chain):
    """042 第 0 項（041 總控台 codex BLOCK）：改程式＋補案例＋commit（快照：程式不欠案例）→ 再改同一支程式並 git add →
    只把工作樹改回快照內容（暫存區留著新碼）→ Stop (d) 照擋：內容回到快照的豁免要同根改檔 git status 乾淨（含暫存區），
    和「改過又原樣還原」同一個條件。舊碼只比工作樹雜湊，(d) 被清，暫存的新碼可以直接提交。"""
    state, edit, git, repo, code, case = chain
    edit(code, 3)
    edit(case, 3)
    git("commit", "-qam", "v3")
    edit(code, 4)
    git("add", "src/a.py")
    edit(code, 3)                                                                          # 只還原工作樹，暫存區還是新碼
    assert _status(repo) == "MM src/a.py"
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **copy.deepcopy(state))
    assert _DEBT_A in out
    git("reset", "-q", "--", "src/a.py")                                                   # 暫存區也回去：沒有案例覆蓋 a.py 照欠
    assert _status(repo) == ""
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **copy.deepcopy(state))
    assert _DEBT_A in out
    _cover(edit, git)                                                                      # 配對：補覆蓋它的案例 → 不欠
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert _DEBT_A not in out


@pytest.mark.parametrize("amend, owed", [
    ("message_only", False),           # 反證還原後 amend 只改訊息：案例照樣覆蓋，不再欠
    ("with_new_code", False),          # amend 把新改的程式一起提交：案例照樣覆蓋（不比先後），不欠
])
def test_042_0b_amend_after_settled_reversal_keeps_exemption(driven, capsys, chain, amend, owed):
    """042 第 0 項 WARN 2：commit 後反證把程式退回舊版又還原（內容回到快照、豁免成立）→ `git commit --amend` → PostToolUse 拍新快照時
    先拿舊快照判一次，已成立的還原照算不欠。舊碼新快照照修改時間重算，程式被當成欠案例，amend 只改訊息也多擋一次。"""
    state, edit, git, _, code, case = chain
    edit(code, 3)
    _cover(edit, git)
    git("commit", "-qam", "v3")
    git("checkout", "HEAD~1", "--", "src/a.py")
    git("checkout", "HEAD", "--", "src/a.py")
    if amend == "with_new_code":
        edit(code, 4)
        git("commit", "-qa", "--amend", "-m", "v3b")
    else:
        git("commit", "-q", "--amend", "-m", "v3b")
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert (_DEBT_A in out) is owed, amend


@pytest.mark.parametrize("how, owed", [("delete", False), ("rename", False), ("kept", False), ("kept_tracked_dir", True)])
def test_042_1_session_new_code_file_gone_no_longer_owes(driven, capsys, chain, monkeypatch, how, owed):
    """042 根因①（claude-91 現場 72133ffb：cp 進被 .gitignore 的目錄的 .py，之後刪掉、或改名成 .py.txt，(d) 一直擋）：本 session
    新建的程式檔 Stop 時已不存在、同根 status 與本 session 提交都沒有新出現的程式檔 → 判成刪除、不欠補案例（現行
    vanished_code_paths；不是「不在就解除」，搬走的照欠見 040_11）。041 合併前的 main 只看修改紀錄，刪掉、改名照欠。
    還在的：在被忽略的目錄裡不是本專案程式（EXCLUDED_REGION）不欠；配對：同一支放在沒被忽略的目錄照欠。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    state, edit, _, repo, _, _ = chain
    (repo / ".gitignore").write_text("scratch/\n", encoding="utf-8", newline="\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-qm", "ignore scratch")
    new = repo / ("tracked_dir" if how == "kept_tracked_dir" else "scratch") / "copy_x.py"
    new.parent.mkdir()
    new.write_text("x = 1\n", encoding="utf-8", newline="\n")
    edit.post("Write", {"file_path": str(new)})
    if how == "delete":
        new.unlink()
    elif how == "rename":
        new.rename(new.with_name("copy_x.py.txt"))
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert ("改了程式碼（copy_x.py）" in out) is owed, how


@pytest.mark.parametrize("rel, owed", [
    ("tools/probe_x.py", True),
    ("workflow/inbox/to-x/probe_x.py", False),
    ("memory/_staging/probe_x.py", False),
    ("_AIDocs/probe_x.py", False),
])
def test_042_2_same_file_counts_as_code_only_outside_excluded_regions(driven, capsys, chain, rel, owed):
    """042 根因②：路徑分類只看副檔名，放在信箱當素材的 .py（cp 進去）被當成改了本專案程式碼。同內容的檔在 tools/ 下算、
    在 workflow/inbox/、memory/_staging/、_AIDocs/ 下不算（部位表類別 knowledge，錨在專案根；看路徑屬哪個部位、
    不看 git 狀態）。舊碼一律算。"""
    state, edit, _, repo, _, _ = chain
    _put_know_map(repo)
    p = repo / rel
    p.parent.mkdir(parents=True)
    p.write_text("def probe():\n    return 1\n", encoding="utf-8", newline="\n")
    edit.post("Write", {"file_path": str(p)})
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert ("改了程式碼（probe_x.py）" in out) is owed, rel


def test_042_2b_case_in_excluded_region_cannot_settle_real_code(driven, capsys, chain):
    """042 根因②案例側：改了 src/a.py 之後只在信箱寫一支 test_a.py → 排除區的檔也不算案例，(d) 照擋（只排程式側的話，
    信箱裡隨手一支 test_*.py 就能替真程式清帳）。舊碼信箱的 test_a.py 晚於程式、清掉 (d)。配對：補在 tests/ → 不擋。"""
    state, edit, _, repo, code, case = chain
    _put_know_map(repo)
    edit(code, 3)
    inbox_case = repo / "workflow" / "inbox" / "to-x" / "test_a.py"
    inbox_case.parent.mkdir(parents=True)
    inbox_case.write_text(_CASE_V.format(3), encoding="utf-8", newline="\n")
    edit.post("Write", {"file_path": str(inbox_case)})
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **copy.deepcopy(state))
    assert _DEBT_A in out
    edit(repo / "tests" / "test_a.py", 3)                                            # 配對：補在 tests/ 覆蓋它的案例
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert _DEBT_A not in out


def _put_know_map(repo: Path) -> None:
    """專案根放一張帶「類別」欄的部位表：信箱、記憶、文件是 knowledge，其餘照算程式（排除區的真源是部位表，沒有表就不排除）。"""
    (repo / ".claude").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
        "| `src/` | 程式 | 無 | 無 | code |\n| `workflow/inbox/` | 派工信箱 | 無 | 無 | knowledge |\n"
        "| `memory/` | 記憶 | 無 | 無 | knowledge |\n| `_AIDocs/` | 文件 | 無 | 無 | knowledge |\n", encoding="utf-8")


@pytest.mark.parametrize("name", ["verify_x_snapshot.sh", "probe_x.py"])
def test_gitignored_code_file_is_not_owed(driven, capsys, chain, name):
    """git 忽略的目錄裡改程式副檔名的檔（總控台在信箱寫的快照腳本）不是本專案程式：(d) 不欠案例。
    沒有部位表，只靠 .gitignore 判；舊碼只看副檔名與同根，照欠。"""
    state, edit, _, repo, _, _ = chain
    (repo / ".gitignore").write_text("box/\n", encoding="utf-8", newline="\n")
    p = repo / "box" / "_console" / name
    p.parent.mkdir(parents=True)
    p.write_text("echo x\n", encoding="utf-8", newline="\n")
    assert subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", str(p)]).returncode == 0
    edit.post("Write", {"file_path": str(p)})
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert f"改了程式碼（{name}）" not in out


def test_gitignored_case_cannot_settle_tracked_code(driven, capsys, chain):
    """追蹤中的 src/a.py 改了照欠；之後只在 git 忽略的目錄寫一支 test_a.py 不能清帳（舊碼算案例、清掉 (d)）。
    配對：補在追蹤中的 tests/ → 不擋。"""
    state, edit, _, repo, code, case = chain
    (repo / ".gitignore").write_text("box/\n", encoding="utf-8", newline="\n")
    edit(code, 3)
    ignored_case = repo / "box" / "tests" / "test_a.py"
    ignored_case.parent.mkdir(parents=True)
    ignored_case.write_text(_CASE_V.format(3), encoding="utf-8", newline="\n")
    edit.post("Write", {"file_path": str(ignored_case)})
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **copy.deepcopy(state))
    assert _DEBT_A in out
    edit(repo / "tests" / "test_a.py", 3)                                            # 配對：補在 tests/ 覆蓋它的案例
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert _DEBT_A not in out


@pytest.mark.parametrize("how, owed", [("delete", False), ("rm_recorded", False), ("move_to_ignored", False),
                                       ("moved_into_tracked", True)])
def test_0a_gone_material_not_owed_after_ignore_line_dropped(driven, capsys, chain, monkeypatch, how, owed):
    """0a（10-15 調度收尾 (d) MOVED_NEW_CODE_SEEN 誤擋，Logs/guard-reconcile.jsonl session 3b5b2245 turn 67）：在被忽略的信箱寫快照腳本
    → 刪掉（含記帳的 rm）或搬到別的忽略目錄 → 拿掉忽略那一行 → 本 session 又提交一支無關的新程式檔。舊碼把那支新檔當成腳本「可能搬過去」
    照欠；新碼：新檔檔名與內容都和腳本最後一次寫入時不同，不是它搬過去的 → 刪除、不欠。配對：腳本改名搬進追蹤目錄並提交（內容相同）→ 照欠。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    state, edit, git, repo, _, _ = chain
    (repo / ".gitignore").write_text("box/\nbox2/\n", encoding="utf-8", newline="\n")
    git("add", ".gitignore")
    git("commit", "-qm", "ignore box")
    p = repo / "box" / "_console" / "verify_x_snapshot.sh"
    p.parent.mkdir(parents=True)
    p.write_text("echo snapshot\n", encoding="utf-8", newline="\n")
    edit.post("Write", {"file_path": str(p)})
    if how == "moved_into_tracked":
        dst = repo / "tools" / "snap.sh"
        dst.parent.mkdir(parents=True)
        p.rename(dst)                                                    # 沒經過記帳的搬法
        git("add", "tools/snap.sh")
    elif how == "move_to_ignored":
        dst = repo / "box2" / "merge-scripts" / p.name
        dst.parent.mkdir(parents=True)
        p.rename(dst)
    else:
        p.unlink()
        if how == "rm_recorded":
            edit.post("Bash", {"command": f"rm {str(p).replace(chr(92), '/')}"})
    (repo / ".gitignore").write_text("box2/\n", encoding="utf-8", newline="\n")
    git("add", ".gitignore")
    retention = repo / "hooks" / "verify" / "verify_workflow_retention.py"
    retention.parent.mkdir(parents=True)
    retention.write_text("def test_keep():\n    assert True\n", encoding="utf-8", newline="\n")
    git("add", "hooks/verify/verify_workflow_retention.py")
    git("commit", "-qm", "merge retention table")
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert ("改了程式碼（verify_x_snapshot.sh）" in out) is owed, how


def test_0a_dir_move_after_unrelated_commit_still_owes(driven, capsys, chain, monkeypatch):
    """0a codex BLOCK：改 src/a.py → 本 session 提交一支無關的新測試檔（提交紀錄有新程式檔）→ `git mv src pkg` 還沒 commit →
    照欠。副本只認同名或同內容後，不能再因為提交紀錄已有新檔就不查 status：搬過去的 pkg/a.py 只在 status 裡。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    state, edit, git, repo, code, _ = chain
    edit(code, 3)
    other = repo / "tests" / "test_other.py"
    other.write_text("def test_other():\n    assert True\n", encoding="utf-8", newline="\n")
    git("add", "tests/test_other.py")
    git("commit", "-qm", "unrelated test")
    assert "tests/test_other.py" in str(state.get("committed_new_code"))
    git("mv", "src", "pkg")
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert _DEBT_A in out


def test_0a_small_content_sha_skips_big_files(tmp_path, monkeypatch):
    """0a codex WARN：修改紀錄 sha 欄與副本比對只算 SHA_SIZE_CAP 以內的檔（大檔整檔讀會吃掉 Stop 的時間預算）；
    超過、不存在 → None（寫入端不記、比對端當判不出，照欠）。"""
    monkeypatch.setattr(vl, "SHA_SIZE_CAP", 10)
    small, big = tmp_path / "s.py", tmp_path / "b.py"
    small.write_bytes(b"x = 1\n")
    big.write_bytes(b"x = 1234567890\n")
    assert vl.small_content_sha(str(small)) == vl._content_sha(str(small)) is not None
    assert vl.small_content_sha(str(big)) is None and vl.small_content_sha(str(tmp_path / "none.py")) is None


def test_0a_session_new_untracked_code_moved_still_owes(driven, capsys, chain, monkeypatch):
    """0a 配對（新舊都綠；說明為什麼不拿「從沒被 git 追蹤過」當素材的判準）：本 session 新寫、還沒提交的 src/new.py，用沒記帳的方式
    改名成 src/renamed.py（內容相同）→ 照欠。它寫的時候就在追蹤目錄裡、是程式；從沒追蹤過不代表是素材。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    state, edit, _, repo, _, _ = chain
    new = repo / "src" / "new.py"
    new.write_text("def new():\n    return 1\n", encoding="utf-8", newline="\n")
    edit.post("Write", {"file_path": str(new)})
    new.rename(repo / "src" / "renamed.py")
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert "改了程式碼（new.py）" in out


@pytest.mark.parametrize("how, owed", [("deleted", False), ("renamed_copy", True)])
def test_009_launcher_gone_is_not_copied_into_a_committed_file_that_is_gone_too(driven, capsys, chain, monkeypatch, how, owed):
    """009（工作軌收尾實遇：一次性啟動器 _commit_branch.py 跑完刪掉，被當成搬進同 session 提交、之後又 git mv 改名掉的 wg_old_test.py）：
    本 session 提交新模組 tools/mod_old.py → git mv 成 tools/mod_new.py（還沒提交）→ 根目錄 Write 一支啟動器、跑完刪掉。
    舊碼：提交紀錄裡的 tools/mod_old.py 磁碟上已不在、內容雜湊算不出 → 當成啟動器「可能搬過去的副本」，MOVED_NEW_CODE_SEEN 照欠。
    新碼：自己也不在了的新檔不當候選 → 刪除、不欠。配對：啟動器改名成 _launch2.py（內容相同、還在）→ 照欠。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    state, edit, git, repo, _, _ = chain
    mod = repo / "tools" / "mod_old.py"
    mod.parent.mkdir(parents=True)
    mod.write_text("def mod():\n    return 1\n", encoding="utf-8", newline="\n")
    edit.post("Write", {"file_path": str(mod)})
    git("add", "tools/mod_old.py")
    git("commit", "-qm", "add mod")
    assert "tools/mod_old.py" in str(state.get("committed_new_code")), "前置：提交紀錄記到這支新模組"
    git("mv", "tools/mod_old.py", "tools/mod_new.py")
    launcher = repo / "_launch.py"
    launcher.write_text("print('run once')\n", encoding="utf-8", newline="\n")
    edit.post("Write", {"file_path": str(launcher)})
    if how == "deleted":
        launcher.unlink()
    else:
        launcher.rename(repo / "_launch2.py")
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    reason = json.loads(out.strip().splitlines()[-1])["reason"]     # mod_old.py 那幾支自己也欠，只看啟動器這一支
    if owed:
        assert "_launch.py 已不存在、同根出現可能是它的副本（_launch2.py）" in reason, how
    else:
        assert "_launch.py" not in reason, how


_GIT_LAUNCHER = 'import subprocess\nsubprocess.run(["git", "add", "-A"])\nsubprocess.run(["git", "commit", "-qm", "x"])\n'


@pytest.mark.parametrize("how", ["kept", "deleted"])
def test_launcher_not_code_no_case_debt(driven, capsys, chain, monkeypatch, how):
    """LAUNCHER_NOT_CODE：worktree 根 Write 一支只跑 git 的一次性啟動器（留著或跑完刪掉），
    收尾不當改碼：不欠案例、不讓收據作廢（舊碼照算程式 → (d) 欠 _run_once.py → 紅）。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    state, edit, git, repo, _, _ = chain
    launcher = repo / "_run_once.py"
    launcher.write_text(_GIT_LAUNCHER, encoding="utf-8", newline="\n")
    edit.post("Write", {"file_path": str(launcher)})
    assert vl.git_launcher(str(launcher)), "前置：寫入時就認成啟動器"
    if how == "deleted":
        launcher.unlink()
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert "_run_once.py" not in out, out


def test_launcher_with_other_code_is_still_code(driven, capsys, chain, monkeypatch):
    """反例：名義上是啟動器、裡面多寫了別的事（開檔寫）→ 照算程式、照欠案例。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    state, edit, git, repo, _, _ = chain
    launcher = repo / "_run_once.py"
    launcher.write_text(_GIT_LAUNCHER + 'open("x.txt", "w").write("y")\n', encoding="utf-8", newline="\n")
    edit.post("Write", {"file_path": str(launcher)})
    assert not vl.git_launcher(str(launcher))
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert "_run_once.py" in out, out


def test_042_2c_excluded_region_is_anchored_at_known_root(tmp_path):
    """排除區只認相對專案根、錨在根的路徑：拿不到根、檔不在根底下、根所在目錄的名字、根底下別處同名目錄都不排除（照算程式）。"""
    cfg = vl.RECONCILE_DEFAULTS
    proj, aid = tmp_path / "proj", tmp_path / "_AIDocs" / "proj"
    for r in (proj, aid):
        _put_know_map(r)
    p, a = str(proj), str(aid)
    assert vl.is_excluded(p + r"\workflow\inbox\to-x\a.py", cfg, p)
    assert vl.is_excluded(p.upper() + r"\_AIDocs\DevHistory\a.py", cfg, p.replace("\\", "/") + "/")   # 大小寫、斜線不影響
    assert not vl.is_excluded(p + r"\workflow\inbox\a.py", cfg, None)
    assert not vl.is_excluded(str(tmp_path / "other") + r"\workflow\inbox\a.py", cfg, p)
    assert not vl.is_excluded(a + r"\hooks\a.py", cfg, a)                                     # 根所在目錄名含 _AIDocs
    assert not vl.is_excluded(p + r"\hooks\_AIDocs\a.py", cfg, p)                              # 只有子字串撞到
    assert not vl.is_excluded(p + r"\workflow\inbox-old\a.py", cfg, p)
    assert not vl.is_excluded(p + r"\workflow\inbox\..\..\src\a.py", cfg, p)               # 經信箱繞回 src/：照算程式
    assert not vl.is_excluded(str(tmp_path / "nomap") + r"\workflow\inbox\a.py", cfg, str(tmp_path / "nomap"))  # 沒有部位表


@pytest.mark.parametrize("how", [
    pytest.param("case", marks=pytest.mark.skipif(os.name != "nt", reason="大小寫不同的路徑指到同一個檔只在不分大小寫的檔案系統成立")),
    "dotdot",
])
def test_042_0d_aliased_edit_path_still_sees_index(driven, capsys, chain, how):
    """042 codex BLOCK／WARN：修改紀錄的寫法和 git 記的不一樣，但是同一個檔：Windows 上 Edit 用 `src/A.py`（git 記 `src/a.py`）、
    或路徑帶 `src/../src/a.py` → 042_0 的流程（快照後改碼並暫存、只還原工作樹）照擋。舊碼 pathspec 分大小寫查不到、空輸出當乾淨；
    `..` 沒消掉，git 回的 `src/a.py` 比不回修改紀錄，也當乾淨。"""
    state, edit, git, repo, code, case = chain
    alias = code.with_name("A.py") if how == "case" else code.parent / ".." / "src" / "a.py"

    def write_alias(v):
        alias.write_text(_CODE_V.format(v), encoding="utf-8", newline="\n")
        edit.post("Edit", {"file_path": str(alias)})
    write_alias(3)
    edit(case, 3)
    git("commit", "-qam", "v3")
    write_alias(4)
    git("add", "src/a.py")
    write_alias(3)
    assert _status(repo) == "MM src/a.py"
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert f"改了程式碼（{alias.name}）" in out, how


def test_042_0e_snapshot_exemption_checks_every_git_root_of_the_project(tmp_path):
    """042 codex WARN：同一個專案根跨兩個 git 根（主 repo 的程式、巢狀 repo 的案例）→ 案例改了並暫存、只還原工作樹，內容都回到快照，
    但案例那個 git 根的暫存區有差 → 不豁免。舊碼只查程式所在的 git 根。配對：案例的暫存區也還原 → 豁免。"""
    proj = tmp_path / "proj"
    sub = proj / "sub"
    (proj / "src").mkdir(parents=True)
    (sub / "tests").mkdir(parents=True)
    code, case = proj / "src" / "a.py", sub / "tests" / "test_suite.py"
    for repo, f, text in ((proj, code, _CODE_V.format(2)), (sub, case, _CASE_V.format(2))):
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "t@t")
        _git(repo, "config", "user.name", "t")
        f.write_text(text, encoding="utf-8", newline="\n")
        _git(repo, "add", str(f.relative_to(repo)).replace("\\", "/"))
        _git(repo, "commit", "-qm", "v2")
    snap = {"files": {str(code): vl._content_sha(str(code)), str(case): vl._content_sha(str(case))}, "settled": [str(code)]}
    case.write_text(_CASE_V.format(3), encoding="utf-8", newline="\n")
    _git(sub, "add", "tests/test_suite.py")
    case.write_text(_CASE_V.format(2), encoding="utf-8", newline="\n")                         # 只還原工作樹
    args = (snap, [str(code)], [str(code), str(case)])
    assert vl.committed_settled_paths(*args, root_of=lambda q: str(proj)) == []
    _git(sub, "reset", "-q", "--", "tests/test_suite.py")
    assert vl.committed_settled_paths(*args, root_of=lambda q: str(proj)) == [str(code)]


def test_042_0c_snapshot_exemption_outside_git_is_refused(capsys):
    """快照豁免查不了暫存區（不在 git 工作區）→ 不成立、stderr 說一聲：和「改過又原樣還原」同一個 fail-closed，不只比內容就放。"""
    p = r"c:\proj\hooks\x.py"                                         # 虛構路徑：不存在、不在任何 git 工作區（內容雜湊兩邊都是 None）
    snap = {"files": {p: None}, "settled": [p]}
    assert vl.committed_settled_paths(snap, [p], [p], root_of=lambda q: r"c:\proj") == []
    assert "不在 git 工作區" in capsys.readouterr().err


# ─── EXEMPTION_PEERS_CODE_ONLY：三個「內容回到某狀態」的豁免只拿同根程式檔（含案例）一起比 ───────────────────

def _repo_with_doc(tmp_path):
    """_two_version_repo 再加一個已提交的文件 docs/notes.md。回 (repo, 程式, 案例, 文件)。"""
    repo, code, case = _two_version_repo(tmp_path)
    doc = repo / "docs" / "notes.md"
    doc.parent.mkdir()
    doc.write_text("# n\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "docs/notes.md")
    _git(repo, "commit", "-qm", "doc")
    return repo, code, case, doc


def _porcelain(repo) -> str:
    return subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True).stdout


def test_exemption_peers_snapshot_settled_ignores_a_doc_another_session_is_editing(tmp_path):
    """SNAPSHOT_SETTLED：commit 之後同根的文件被別的 session 改著（內容和快照不同、git 有差），程式與案例都回到快照 → 照樣豁免。
    舊碼把文件也算進同根比對 → 不豁免。配對：案例沒回到快照 → 不豁免。"""
    repo, code, case, doc = _repo_with_doc(tmp_path)
    snap = {"files": {str(p): vl._content_sha(str(p)) for p in (code, case, doc)}, "settled": [str(code)]}
    doc.write_text("# 別的 session 改著\n", encoding="utf-8", newline="\n")
    assert _porcelain(repo).strip() == "M docs/notes.md"                                       # 前置：只有文件有差
    args = (snap, [str(code)], [str(code), str(case), str(doc)])
    assert vl.committed_settled_paths(*args, root_of=lambda q: str(repo)) == [str(code)]
    case.write_text(_CASE_V.format(3), encoding="utf-8", newline="\n")
    assert vl.committed_settled_paths(*args, root_of=lambda q: str(repo)) == []


def test_exemption_peers_net_unchanged_ignores_a_dirty_doc(tmp_path):
    """NET_UNCHANGED：程式改了又原樣還原、同根文件還改著 → 程式算原樣，文件照算改了。舊碼文件拖住整個根，一個都不剔除。
    配對：同根的案例還改著 → 一個都不剔除。"""
    repo, code, case, doc = _repo_with_doc(tmp_path)
    code.write_text(_CODE_V.format(9), encoding="utf-8", newline="\n")
    code.write_text(_CODE_V.format(2), encoding="utf-8", newline="\n")                        # 改了又還原
    doc.write_text("# 改著\n", encoding="utf-8", newline="\n")
    mods = [_mf(str(code), 5), _mf(str(doc), 5)]
    assert vl.net_unchanged_paths(mods, None) == [str(code)]
    case.write_text(_CASE_V.format(3), encoding="utf-8", newline="\n")
    assert vl.net_unchanged_paths(mods, None, session_paths=[str(case)]) == []


def test_exemption_peers_comment_only_ignores_a_dirty_doc(tmp_path):
    """COMMENT_ONLY_CHANGE：程式只加註解、同根文件還改著 → 照樣算只差註解。舊碼要求文件也等於 HEAD 或只差註解 → 照欠。
    配對：同根的案例改了實質內容 → 照欠。"""
    repo, code, case, doc = _repo_with_doc(tmp_path)
    code.write_text("# 只加註解\n" + _CODE_V.format(2), encoding="utf-8", newline="\n")
    doc.write_text("# 改著\n", encoding="utf-8", newline="\n")
    cfg = vl.reconcile_cfg({})
    got = vl.committed_equal_paths([_mf(str(code), 5)], cfg, session_paths=[str(doc)])
    assert [v.rule for v in got.values()] == ["COMMENT_ONLY_CHANGE"], got
    case.write_text(_CASE_V.format(3), encoding="utf-8", newline="\n")
    assert vl.committed_equal_paths([_mf(str(code), 5)], cfg, session_paths=[str(doc), str(case)]) == {}


@pytest.fixture()
def peer_flow(driven, monkeypatch):
    """042 加項：使用者打字開回合 → Stop → 同伴 session 訊息經真 UserPromptSubmit 進來（turn_seq +1，使用者回合不變）→ Stop →
    使用者再打字開新回合 → Stop。state 一路沿用。回 run(text, capsys, config, before_stop(state, 步驟)) → 三次 Stop 的輸出。"""
    monkeypatch.setattr(st, "coding_turn", lambda *a, **k: True)   # 測每回合一次本身：當成寫碼回合（CODING_TURN_ONLY 另有案）

    def run(text, capsys, config=None, before_stop=None, **extra):
        state = {"turn_seq": 4, "session": {"cwd": ""}, **extra}
        _ups_turn(monkeypatch, state, "把 x 做完")
        outs = []
        for step, prompt in (("first", None), ("peer", _PEER_MSG), ("user", "接著做 y")):
            if prompt:
                _ups_turn(monkeypatch, state, prompt)
            if before_stop:
                before_stop(state, step)
            out, after, _ = driven(text, capsys, config=config, **copy.deepcopy(state))
            state.clear()
            state.update(after)
            outs.append(out)
        return outs
    return run


def _fresh_budget(state, step):
    """使用者再打字那一步把共用的 stop_gate_max_blocks 次數歸零：那是另一本帳，這裡只看「每回合一次」的鍵。"""
    if step == "user":
        state["stop_blocked_count"] = 0


def test_042_3_deferral_gate_once_per_user_turn(peer_flow, capsys):
    """042 加項（claude-91 讀碼）：DeferralGate 每回合只擋一次，回合要用使用者打字開的回合（_user_turn）。舊碼用 turn_seq 當鍵，
    同伴訊息讓 turn_seq +1，同一回合又擋一次。配對：使用者真打字開新回合 → 照擋。"""
    outs = peer_flow("完工，工作樹乾淨。要不要下個 session 再把 realm atom 瘦身？", capsys, before_stop=_fresh_budget)
    assert ["[Guardian:DeferralGate]" in o for o in outs] == [True, False, True]


def test_042_3_harvest_gate_once_per_user_turn(peer_flow, capsys, monkeypatch):
    """042 加項：KnowledgeHarvest 每回合只擋一次（harvest_gate_turn 記 _user_turn）。claude-91 一整天每則同伴訊息後被重問收割就是這個。"""
    import wg_harvest as wh
    monkeypatch.setattr(st, "harvest_gate_reason", wh.harvest_gate_reason)
    outs = peer_flow("全部完成了。", capsys, config={"harvest": {"enabled": True, "min_turns": 3, "min_accessed": 5,
                                                                "min_turns_between": 3, "background": False}})
    assert ["[Guardian:KnowledgeHarvest]" in o for o in outs] == [True, False, True]   # 擋下這條路（背景關或送不出去時）


def test_042_3_harvest_pending_gate_once_per_user_turn(peer_flow, capsys, monkeypatch):
    """042 加項：Harvest-Pending 每回合只擋一次（harvest_pending_gate_turn 記 _user_turn）。"""
    import wg_harvest as wh
    monkeypatch.setattr(st, "pending_gate_reason", wh.pending_gate_reason)
    outs = peer_flow("全部完成了。", capsys, knowledge_harvest={_SID: {"pending": ["- foo → 已寫入 atom foo（沒有 receipt）"]}})
    assert ["[Guardian:Harvest-Pending]" in o for o in outs] == [True, False, True]


def test_042_3_aec_pending_gate_once_per_user_turn(peer_flow, capsys):
    """042 加項：AEC-Pending 每回合只擋一次（aec_pending_gate_turn 記 _user_turn）：同伴訊息進來後又 emit 一次仍帶「尚未寫」的報告，
    同一回合不再擋第二次。"""
    def before(state, step):
        rec = _aec(state["turn_seq"], j="無", k="無")                                       # 每次 Stop 前都 emit 過一次
        rec["d_pending"] = ["- foo → 尚未寫（見下一動）"]
        state["anti_evasion_report"] = rec
        _fresh_budget(state, step)
    outs = peer_flow("全部完成了。", capsys, before_stop=before)
    assert ["[Guardian:AEC-Pending]" in o for o in outs] == [True, False, True]


# ─── 044：判定規則（wg_release_rules）的端到端案例：同一個檔不同寫法、本回合窗口、轉述句、已不存在的改檔 ──────────────────

import wg_release_rules as rr  # noqa: E402

def _other_spelling(code, how):
    return {"slash": str(code).replace("\\", "/"), "lower": str(code).lower(),
            "dotdot": str(code.parent / ".." / code.parent.name / code.name)}[how]


@pytest.mark.parametrize("how", [
    "slash",
    pytest.param("lower", marks=pytest.mark.skipif(os.name != "nt", reason="大小寫不同指到同一個檔只在不分大小寫的檔案系統成立")),
    "dotdot",
])
def test_044_1_same_file_other_spelling_restored_after_commit_is_settled(driven, capsys, chain, how):
    """044 第 1～3 項（規則 SAME_FILE；043 總控台 codex BLOCK）：改程式＋補案例＋commit（Edit 記反斜線）→ 用另一種寫法（正斜線／小寫／`..`）
    暫改同一個檔又改回 → Stop 不擋：修改紀錄只留一筆、快照成員與內容鍵用 canon_path 比。舊碼兩種寫法記兩筆，第二筆不在快照裡、豁免被拒。
    配對：改回工作樹但暫存區留新碼 → 照擋。"""
    state, edit, git, repo, code, case = chain
    edit(code, 3)
    _cover(edit, git)
    git("commit", "-qam", "v3")
    other = _other_spelling(code, how)

    def write(v):
        Path(other).write_text(_CODE_V.format(v), encoding="utf-8", newline="\n")
        edit.post("Edit", {"file_path": other})
    write(4)
    write(3)
    assert _status(repo) == ""
    assert len([m for m in state["modified_files"] if rr.canon_path(m["path"]) == rr.canon_path(str(code))]) == 1, how
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **copy.deepcopy(state))
    assert _DEBT_A not in out, how
    write(4)
    git("add", "src/a.py")
    write(3)
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **state)
    assert _DEBT_A not in out, how                                                  # 案例覆蓋 a.py：暫存區留新碼也不比先後


def _user_then_peers(monkeypatch, peers=2, **extra):
    """使用者在 turn 5 打字，接著 peers 則同伴訊息經真 UserPromptSubmit 進來（turn_seq 前進、使用者回合仍是 5）。"""
    state = {"turn_seq": 4, "session": {"cwd": ""}}
    _ups_turn(monkeypatch, state, "把 x.py 修好")
    state.update(extra)
    for _ in range(peers):
        _ups_turn(monkeypatch, state, _PEER_MSG)
    assert state["turn_prompts_seq"] == 5 and state["turn_seq"] == 5 + peers
    return state


def test_044_4_pass_receipt_before_peer_messages_still_counts(driven, capsys, monkeypatch):
    """044 第 4 項（規則 TURN_SINCE_USER_PROMPT；track-e8 待命回合實踩）：turn 5 改 x.py、補案例、跑出對得上的 PASS → 兩則同伴訊息
    （turn 7）→ 說修好：本回合收據從使用者打字那回合算起，(a) 不擋。舊碼只認 turn_seq==7，PASS 變成舊回合、擋。配對：沒有 PASS → 照擋，
    擋訊息印出規則名與本回合範圍。"""
    mods = [_mf(_CODE, 5, last_at=_T1, last_seq=1), _mf(_CASE, 5, last_at=_T1, last_seq=2)]
    state = _user_then_peers(monkeypatch, modified_files=mods,
                             verify_receipts={_SID: [_rcpt(5, cmd=_RELATED_CMD, at=_T2, seq=3)]})
    out, _, _ = driven("x.py 修好了，全部完成了。", capsys, **copy.deepcopy(state))
    assert _A_HIT not in out
    state["verify_receipts"] = {_SID: []}
    out, _, _ = driven("x.py 修好了，全部完成了。", capsys, **state)
    assert _A_HIT in out and "TURN_SINCE_USER_PROMPT" in out and "turn 5～7" in out


_A_HIT, _C_HIT = "(a) CLAIM_FIXED_NEEDS_PASS：說「修好」", "(c) CLAIM_TRIED_NEEDS_EXEC：說「試過／跑了」"


def test_044_4_exec_before_peer_messages_counts_for_tried(driven, capsys, monkeypatch):
    """044 第 4 項（(c) 同一根因）：turn 5 跑過 Bash（PostToolUse 記 exec_turn_seq）→ 兩則同伴訊息 → 說「跑過了」：(c) 不擋。
    舊碼只看 transcript 最後一段的工具名與 turn_seq==7 的收據，擋。配對：最後一次執行在使用者打字之前（turn 4）→ 照擋。"""
    state = _user_then_peers(monkeypatch, exec_turn_seq={_SID: 5})
    out, _, _ = driven("我跑過測試了，全部完成了。", capsys, **copy.deepcopy(state))
    assert _C_HIT not in out
    state["exec_turn_seq"] = {_SID: 4}
    out, _, _ = driven("我跑過測試了，全部完成了。", capsys, **state)
    assert _C_HIT in out


def test_044_5_quoted_fixed_modifier_is_not_own_claim(driven, capsys):
    """044 第 5 項（規則 CLAIM_MODIFIER_NOT_OWN；track-e8 現場原句）：轉述別人換上「修好的 probe_codegate.py」不是自己宣稱修好，(a) 不擋。
    舊碼看到「修好」就判宣稱，沒有 PASS 就擋。配對：自己說「修好了」照擋。"""
    out, _, _ = driven("claude-9f 已經把修好的 probe_codegate.py 換上去，043 交付完成。", capsys)
    assert _A_HIT not in out
    out, _, _ = driven("probe_codegate.py 修好了，交付完成。", capsys)
    assert _A_HIT in out


# ─── G6 階段 4（判斷入口盤點 P6）：詞表只是提示，宣稱行是 LLM 介入的入口（規則 CLAIM_WORDS_ARE_HINTS 等三條） ─────────────────

def test_p6_explanation_plus_real_claim_blocks_and_teaches_claim_line(driven, capsys):
    """10-15 實案形狀：說明句「CC 會自己跑完測試」＋真宣稱「修好了」沒收據 → 照擋（真宣稱沒證據照擋），
    但擋訊息要教 AI 回宣稱行（舊碼只說補 PASS → 紅）。"""
    out, _, _ = driven("CC 會自己跑完測試再收尾。閘修好了，完成。", capsys)
    assert _A_HIT in out and "宣稱｜修好：非本回合宣稱" in out and "宣稱｜修好：收據" in out and "CLAIM_WORDS_ARE_HINTS" in out


def test_p6_disclaim_with_reason_passes_and_logs(driven, capsys):
    """AI 回「宣稱｜修好：非本回合宣稱，因為…」→ (a) 放行、guard-reconcile.jsonl 記 claim_disclaimed（哪一條、原行）。"""
    text = ("CC 會自己跑完測試再收尾。閘修好了，完成。\n"
            "宣稱｜修好：非本回合宣稱，因為「修好了」講的是上一回合驗過的狀態，本回合只改了文件")
    out, _, logs = driven(text, capsys)
    assert '"block"' not in out, out        # 不只 ReconcileGate：宣稱行裡的「非本回合」也不能被 DeferralGate 當退縮語（實跑探針踩到）
    hit = [p for g, p in logs if g == "reconcile" and p.get("event") == "claim_disclaimed"]
    assert hit and hit[0]["letter"] == "a" and hit[0]["line"].startswith("宣稱｜修好：非本回合宣稱")


def test_p6_disclaim_without_reason_still_blocks(driven, capsys):
    out, _, _ = driven("閘修好了，完成。\n宣稱｜修好：非本回合宣稱，因為 <理由>", capsys)
    assert "(a) CLAIM_DISCLAIM_NEEDS_REASON" in out


def test_p6_receipt_ref_matching_green_receipt_passes(driven, capsys):
    """對帳程式用檔名對不上的綠收據（run_other.py），AI 指出「收據 run_other.py」→ 對上就放、留帳；指錯或紅的照擋。"""
    rc = {_SID: [_rcpt(5, cmd="python run_other.py")]}
    out, _, _ = driven("閘修好了，完成。", capsys, verify_receipts=rc)
    assert _A_HIT in out, "前置：程式自己對不上這張收據"
    out, _, logs = driven("閘修好了，完成。\n宣稱｜修好：收據 run_other.py", capsys, verify_receipts=rc)
    assert "ReconcileGate" not in out
    assert any(g == "reconcile" and p.get("event") == "claim_receipt_ref" and "run_other.py" in p.get("why", "") for g, p in logs)
    out, _, _ = driven("閘修好了，完成。\n宣稱｜修好：收據 nothing.py", capsys, verify_receipts=rc)
    assert "(a) CLAIM_RECEIPT_REF_MATCH" in out
    out, _, _ = driven("閘修好了，完成。\n宣稱｜修好：收據 run_other.py", capsys,
                       verify_receipts={_SID: [_rcpt(5, "FAIL", cmd="python run_other.py")]})
    assert "(a) CLAIM_RECEIPT_REF_MATCH" in out, "指到紅收據不算"
    for generic in ("python", "pytest", ".py", "-m", "run"):                       # codex BLOCK：通用字指不到哪一張收據
        out, _, _ = driven(f"閘修好了，完成。\n宣稱｜修好：收據 {generic}", capsys, verify_receipts=rc)
        assert "(a) CLAIM_RECEIPT_REF_MATCH" in out, generic
    out, _, _ = driven("閘修好了，完成。\n宣稱｜修好：收據 other", capsys, verify_receipts=rc)
    assert "(a) CLAIM_RECEIPT_REF_MATCH" in out, "檔名的一截（other）不是完整 token"
    out, _, _ = driven("閘修好了，完成。\n宣稱｜修好：收據 X_CHECK", capsys, verify_receipts=rc)
    assert "ReconcileGate" not in out, "哨兵名指得到"
    out, _, _ = driven("閘修好了，完成。\n宣稱｜修好：收據 run_other.py", capsys,
                       verify_receipts={_SID: [_rcpt(5, cmd="python run_other.py", at="2020-01-01T00:00:00+08:00")]},
                       modified_files=[_mf(_CODE, 5, last_at="2030-01-01T00:00:00+08:00")])
    assert "(a) CLAIM_RECEIPT_REF_MATCH" in out, "指到的收據早於改檔不算"


def test_p6_tried_claim_disclaimed_passes(driven, capsys):
    text = "CC 收尾會自己跑了測試。完成。"
    out, _, _ = driven(text, capsys)
    assert _C_HIT in out, "前置：這句詞表會命中、沒執行 → (c) 擋"
    out, _, logs = driven(text + "\n宣稱｜試過：非本回合宣稱，因為那句是在說明 CC 收尾的行為", capsys)
    assert _C_HIT not in out
    assert any(g == "reconcile" and p.get("event") == "claim_disclaimed" and p.get("letter") == "c" for g, p in logs)


# ─── G6 階段 4（P7）：紅測清單的使用者豁免要對到具體哪一筆（規則 USER_WAIVER_NEEDS_CITATION） ─────────────────────

def test_p7_testfail_waives_only_the_cited_test_and_logs(driven, capsys):
    red = [{"cmd": "python -m pytest verify_a.py", "summary": "1 failed", "turn_seq": 5, "session_id": _SID, "pytest": True},
           {"cmd": "python -m pytest verify_b.py", "summary": "1 failed", "turn_seq": 5, "session_id": _SID, "pytest": True}]
    prompts = ["verify_a 先這樣，b 要修"]
    out, _, _ = driven("全部完成了。", capsys, failing_tests=red, recent_user_prompts=prompts, modified_files=[_mf(_CASE, 5)])
    assert "TestFailGate" in out and "2 項失敗" in out, "使用者只說了「先這樣」、AI 沒引用對到哪一支 → 兩支照擋"
    text = "全部完成了。\n不做｜verify_a.py：使用者說「verify_a 先這樣」"
    out, _, logs = driven(text, capsys, failing_tests=red, recent_user_prompts=prompts, modified_files=[_mf(_CASE, 5)])
    assert "TestFailGate" in out and "1 項失敗" in out and "verify_b.py" in out
    hit = [p for g, p in logs if g == "testfail_waived"]
    assert hit and hit[0]["failing_cmd"].endswith("verify_a.py") and hit[0]["user_said"] == "verify_a 先這樣" and hit[0]["turn_seq"] == 5
    both = text + "\n不做｜verify_b.py：使用者說「b 要修」"
    out, _, _ = driven(both, capsys, failing_tests=red, recent_user_prompts=prompts, modified_files=[_mf(_CASE, 5)],
                       anti_evasion_report=_aec(5, "無", "無"))
    assert "TestFailGate" not in out


def _turn_transcript(tmp_path, *assistant_texts):
    """一個使用者回合：使用者一則、之後 AI 各則之間夾 Stop hook 回饋（isMeta，延續同一回合）。"""
    import json as _json
    recs = [{"type": "user", "message": {"role": "user", "content": "把報表改好"}}]
    for k, t in enumerate(assistant_texts):
        if k:
            recs.append({"type": "user", "isMeta": True,
                         "message": {"role": "user", "content": "Stop hook feedback:\n[Guardian:ReadingPath] 拐彎判斷要答"}})
        recs.append({"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}})
    tp = tmp_path / "turn.jsonl"
    tp.write_text("".join(_json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
    return str(tp)


def test_004_patch_reply_without_completion_still_counts_the_turn_claim(driven, capsys, tmp_path):
    """002 留的件：收尾說「全部完成」被別的閘擋下，補件那則只補缺的行、沒重說完成——收尾閘照本回合的宣告判（這裡用紅測閘看）；
    最後一則明說還沒完成就不算。舊碼只看最後一則，補件那則放過紅測。"""
    red = [{"cmd": "python -m pytest verify_a.py", "summary": "1 failed", "turn_seq": 5, "session_id": _SID, "pytest": True}]
    patch = _turn_transcript(tmp_path, "報表改好了，全部完成。",
                             "拐彎判斷｜report.py::monthly｜不會｜只有一層｜合理，因為直線算完就回")
    out, _, _ = driven(None, capsys, hook_input={"transcript_path": patch}, failing_tests=red, modified_files=[_mf(_CASE, 5)])
    assert "TestFailGate" in out
    undone = _turn_transcript(tmp_path, "報表改好了，全部完成。", "verify_a 還是紅的，這件還沒完成，我在查原因。")
    out, _, _ = driven(None, capsys, hook_input={"transcript_path": undone}, failing_tests=red, modified_files=[_mf(_CASE, 5)])
    assert "TestFailGate" not in out


_ERP = "tests/test_erp_contract.py::test_checkout_fields_match_erp_contract"
_ERP_SAID = "test_erp_contract 那支是 ERP 對接的舊合約測試，先不用管它、跳過。其他照做。"


@pytest.mark.parametrize("item", ["test_checkout_fields_match_erp_contract", "test_erp_contract"])
def test_c6_waiver_by_test_name_is_booked_and_survives_the_window(driven, capsys, item):
    """第三跑 C6：紅測摘要是 pytest 節點，不做行照擋訊息範本寫函式名（或檔名不帶 .py）要對得到；豁免一成立就記帳（state
    testfail_waivers、testfail_waived、deferral_declared 各一筆），使用者之後又說三則別的、原句擠出近 3 則窗口，同一支照帳放行。"""
    red = [{"cmd": "python -m pytest tests -q", "summary": f"FAILED {_ERP}", "turn_seq": 5, "session_id": _SID, "pytest": True}]
    text = f"全部完成了。\n不做｜{item}：使用者說「先不用管它、跳過」"
    out, state, logs = driven(text, capsys, failing_tests=red, recent_user_prompts=[_ERP_SAID], modified_files=[_mf(_CASE, 5)])
    assert "TestFailGate" not in out
    led = state.get("testfail_waivers") or []
    assert len(led) == 1 and led[0]["item"] == item and led[0]["quote"] == "先不用管它、跳過" and led[0]["said"] == _ERP_SAID
    assert any(g == "testfail_waived" and p.get("via") == "quote" for g, p in logs)
    assert any(g == "deferral_declared" and p.get("rule") == "USER_WAIVER_NEEDS_CITATION" for g, p in logs)
    later = ["好", "再跑一次測試", "README 也順手更新"]
    out, state2, logs = driven(text, capsys, failing_tests=red, recent_user_prompts=later, testfail_waivers=led,
                               modified_files=[_mf(_CASE, 5)])
    assert "TestFailGate" not in out, "原句不在近 3 則了，照樣放行（引用不再比對原話；帳也在）"
    assert any(g == "testfail_waived" and p.get("via") in ("quote", "ledger") for g, p in logs)
    assert len(state2["testfail_waivers"]) == 1, "同一支不重記"


def test_c6_ledger_needs_the_line_and_covers_only_that_test(driven, capsys):
    """帳只放帳上那一支，而且收尾仍要有對到它的不做行；別支紅測、或沒寫不做行，照擋。"""
    led = [{"item": "test_checkout_fields_match_erp_contract", "quote": "先不用管它、跳過", "said": _ERP_SAID, "turn_seq": 5}]
    erp = [{"cmd": "python -m pytest tests -q", "summary": f"FAILED {_ERP}", "turn_seq": 6, "session_id": _SID, "pytest": True}]
    other = [{"cmd": "python -m pytest tests -q", "summary": "FAILED tests/test_cart.py::test_total", "turn_seq": 6,
              "session_id": _SID, "pytest": True}]
    out, _, _ = driven("全部完成了。", capsys, failing_tests=erp, recent_user_prompts=["好"], testfail_waivers=led,
                       modified_files=[_mf(_CASE, 5)])
    assert "TestFailGate" in out, "沒寫不做行：帳不自動放"
    out, _, _ = driven("全部完成了。\n不做｜test_total：太難了先不修", capsys, failing_tests=other,
                       recent_user_prompts=["好"], testfail_waivers=led, modified_files=[_mf(_CASE, 5)])
    assert "TestFailGate" in out, "帳上沒有 test_total、只寫自己的理由：照擋"


def test_004_waiver_ledger_books_the_test_and_yields_to_later_words(driven, capsys):
    """記帳時記下豁免到的那一支（units）；使用者之後又提到這一支（「取消剛才的豁免…要修好」）→ 帳不算，
    只寫自己理由的不做行照擋（寫「使用者說「…」」的不做行不再比對原話，照樣放行留帳）。"""
    red = [{"cmd": "python -m pytest tests -q", "summary": f"FAILED {_ERP}", "turn_seq": 5, "session_id": _SID, "pytest": True}]
    text = "全部完成了。\n不做｜test_erp_contract：使用者說「先不用管它、跳過」"
    out, state, _ = driven(text, capsys, failing_tests=red, recent_user_prompts=[_ERP_SAID], modified_files=[_mf(_CASE, 5)])
    led = state.get("testfail_waivers") or []
    assert "TestFailGate" not in out and led[0]["units"] == [_ERP] and led[0]["cmd"] == red[0]["cmd"], led
    later = [_ERP_SAID, "取消剛才的豁免，test_erp_contract 要修好", "好", "繼續"]
    out, _, _ = driven("全部完成了。\n不做｜test_erp_contract：太難了先不修", capsys, failing_tests=red,
                       recent_user_prompts=later, testfail_waivers=led, modified_files=[_mf(_CASE, 5)])
    assert "TestFailGate" in out


def test_004_voided_waiver_is_dropped_from_state_so_it_cannot_revive(driven, capsys):
    """使用者記帳後又提到那一支：那次收尾（就算沒有紅測）就把帳從 state 拿掉並留帳 testfail_waiver_voided；之後那則原話擠出近 5 則，
    只寫自己理由的不做行照擋，帳不會活回來。"""
    led = [{"item": "test_erp_contract", "quote": "先不用管它、跳過", "said": _ERP_SAID, "units": [_ERP],
            "cmd": "python -m pytest tests -q"}]
    _, state, logs = driven("改好了。", capsys, failing_tests=[], recent_user_prompts=[_ERP_SAID, "test_erp_contract 還是要修好"],
                            testfail_waivers=led, modified_files=[_mf(_CASE, 5)])
    assert state.get("testfail_waivers") == [] and any(g == "testfail_waiver_voided" for g, _p in logs)
    red = [{"cmd": "python -m pytest tests -q", "summary": f"FAILED {_ERP}", "turn_seq": 9, "session_id": _SID, "pytest": True}]
    out, _, _ = driven("全部完成了。\n不做｜test_erp_contract：太難了先不修", capsys, failing_tests=red,
                       recent_user_prompts=["好", "繼續", "再跑", "看一下", "嗯"], testfail_waivers=state["testfail_waivers"],
                       modified_files=[_mf(_CASE, 5)])
    assert "TestFailGate" in out


@pytest.fixture()
def plain_dir():
    """不含 test 字樣的暫存目錄（pytest 的 tmp 路徑含 test，拿不到專案根時會被 `**/*test*` 當成案例檔，案子就驗不到東西）。"""
    import shutil
    import tempfile
    from wg_core import find_vcs_root
    d = Path(tempfile.mkdtemp(prefix="wg044-"))
    if "test" in str(d).lower() or find_vcs_root(d) is not None:
        shutil.rmtree(d, ignore_errors=True)
        pytest.skip("系統暫存目錄含 test 字樣或在版控根內，構不出這個情境")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_044_7_gone_outside_any_vcs_root_no_longer_owes(driven, capsys, monkeypatch, plain_dir):
    """044 第 7 項（規則 GONE_OUTSIDE_VCS；track-b2 現場）：worktree 外打錯路徑 Write 出一支 need-goal.js 又當場刪掉 → 不在任何版控根內、
    已不存在 → 不欠補案例。舊碼拿不到 git 根就照欠。配對：git 根內刪掉、但同根冒出新程式檔 → 照欠（MOVED_NEW_CODE_SEEN）。"""
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    stray = plain_dir / "outside" / "tools" / "need-goal.js"
    stray.parent.mkdir(parents=True)
    stray.write_text("x;\n", encoding="utf-8")
    stray.unlink()                                                                          # Write 出來又當場刪掉
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(str(stray), 5, last_at=_T1, last_seq=1)])
    assert "need-goal.js" not in out
    repo = plain_dir / "repo"
    (repo / "src").mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / "src" / "new.py").write_text("x = 1\n", encoding="utf-8")                     # 同根新出現的程式檔
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(str(repo / "src" / "a.py"), 5, last_at=_T1, last_seq=1)])
    assert "改了程式碼（a.py）" in out and "MOVED_NEW_CODE_SEEN" in out


def test_044_7_worktree_removed_after_merge_no_longer_owes(driven, capsys, monkeypatch, plain_dir):
    """044 第 7 項第二案（track-a2c 現場）：worktree 裡改程式並補好案例 → 總控台合併後 git worktree remove（整根消失、沒有 .git）→
    同一個 session 再 Stop：程式與案例都不在、拿不到版控根 → 不欠（GONE_OUTSIDE_VCS，同一條規則、沒有另寫特例）。
    舊碼案例不在就沒有 last_case、程式拿不到 git 根就照欠。"""
    import shutil
    monkeypatch.setattr(vl, "code_exists", os.path.isfile)
    monkeypatch.setattr(vl, "case_exists", os.path.isfile)
    wt = plain_dir / "wt"
    (wt / "lib").mkdir(parents=True)
    (wt / "tools" / "verify").mkdir(parents=True)
    _git(wt, "init", "-q")
    code, case = wt / "lib" / "project_root.py", wt / "tools" / "verify" / "verify_root.py"
    code.write_text("x = 1\n", encoding="utf-8")
    case.write_text("def test_x():\n    pass\n", encoding="utf-8")
    mods = [_mf(str(code), 5, last_at=_T1, last_seq=1), _mf(str(case), 5, last_at=_T2, last_seq=2)]
    shutil.rmtree(wt)
    out, _, _ = driven("全部完成了。", capsys, modified_files=mods)
    assert "project_root.py" not in out


# ─── 044 第 6 項：其他把 turn_seq 當「本回合」的點（規則 TURN_SINCE_USER_PROMPT），各一案 ───────────────────────────

def test_044_6_aec_emitted_before_peer_message_satisfies_scan_report(driven, capsys, monkeypatch):
    """stop.py emitted_this_turn：turn 5 已 emit 收尾報告、動了兩個檔 → 同伴訊息（turn 6）→ 說完成：ScanReport 不擋「本回合沒 emit」。
    舊碼要求報告的 turn_seq==6，擋（而且 scan_report_warned 整場只擋一次，被誤判用掉）。"""
    docs = [_mf(r"c:\proj\docs\a.md", 5, last_at=_T1, last_seq=1), _mf(r"c:\proj\docs\b.md", 5, last_at=_T1, last_seq=2)]
    state = _user_then_peers(monkeypatch, peers=1, modified_files=docs, anti_evasion_report=_aec(5, j="無", k="無"))
    out, _, _ = driven("全部完成了。", capsys, **state)
    assert "[Guardian:ScanReport]" not in out


def test_044_7_aec_after_last_edit_satisfies_scan_report_in_later_turn(driven, capsys, monkeypatch):
    """stop.py aec_up_to_date：turn 3 改兩個檔並交收尾檢核 → 使用者 turn 5 另問一句（純問答）→ 回覆帶完成詞：
    上一份檢核之後沒再改檔，沒有新東西可報，ScanReport 不擋。舊碼只認「本回合」有 emit，純問答回合被逼重交整份十一欄
    （TSLG d242fbd8 第 6 回合實踩）。"""
    docs = [_mf(r"c:\proj\docs\a.md", 3, last_at=_T1, last_seq=1), _mf(r"c:\proj\docs\b.md", 3, last_at=_T1, last_seq=2)]
    state = _user_then_peers(monkeypatch, peers=0, modified_files=docs, anti_evasion_report=_aec(3, j="無", k="無"))
    out, _, _ = driven("結論不變，全部完成了。", capsys, **state)
    assert "[Guardian:ScanReport]" not in out


def test_044_7_edit_after_last_aec_still_requires_scan_report(driven, capsys, monkeypatch):
    """配對：turn 3 交過檢核，但 turn 4 又改了一個檔 → turn 5 說完成：有新改動沒交代，ScanReport 照擋。
    隔壁 session 在 turn 4 之後交的檢核（session_id 不符）也不算。"""
    monkeypatch.setattr(st, "coding_turn", lambda *a, **k: True)   # 測收尾檢核對回合本身：當成寫碼回合
    docs = [_mf(r"c:\proj\docs\a.md", 3, last_at=_T1, last_seq=1), _mf(r"c:\proj\docs\b.md", 4, last_at=_T1, last_seq=2)]
    state = _user_then_peers(monkeypatch, peers=0, modified_files=docs, anti_evasion_report=_aec(3, j="無", k="無"))
    out, _, _ = driven("全部完成了。", capsys, **copy.deepcopy(state))
    assert "[Guardian:ScanReport]" in out
    state["anti_evasion_report"] = _aec(4, j="無", k="無", session_id="sibling")
    out, _, _ = driven("全部完成了。", capsys, **state)
    assert "[Guardian:ScanReport]" in out


def test_044_6_commit_before_peer_message_exempts_scan_report(driven, capsys, monkeypatch):
    """stop.py committed_this_turn：turn 5 已 commit、動了兩個檔 → 通知（turn 6）→ 說完成：本回合 commit 了，ScanReport 豁免。
    舊碼要求 last_commit_turn_seq==6，擋。"""
    docs = [_mf(r"c:\proj\docs\a.md", 5, last_at=_T1, last_seq=1), _mf(r"c:\proj\docs\b.md", 5, last_at=_T1, last_seq=2)]
    state = _user_then_peers(monkeypatch, peers=1, modified_files=docs, last_commit_turn_seq=5)
    out, _, _ = driven("全部完成了。", capsys, **state)
    assert "[Guardian:ScanReport]" not in out


def test_044_6_commit_before_peer_message_counts_as_task_done_for_deferral(driven, capsys, monkeypatch):
    """stop.py 傳給 DeferralGate 的「本回合已 commit」：turn 5 commit → 同伴訊息（turn 6）→ 收尾把可做的事推給下個 session（沒寫完成）
    → 主任務已完工（本回合 commit 了），DeferralGate 照擋。舊碼只認 turn_seq==6，判沒完工、漏擋。"""
    state = _user_then_peers(monkeypatch, peers=1, last_commit_turn_seq=5, need_goal_code_decl_turn=5)
    out, _, _ = driven("要不要下個 session 再把 realm atom 瘦身？", capsys, **state)
    assert "[Guardian:DeferralGate]" in out


def test_044_6_atom_injected_earlier_in_user_turn_is_not_audited(driven, capsys, monkeypatch):
    """stop.py AtomAudit：turn 5 以一行路標注入的 atom → 同伴訊息（turn 6）→ Stop：同一個使用者回合注入的不催（給模型完整一回合決定）。
    舊碼只跳過 turn_seq≥6 的注入，turn 5 的被當舊的、擋 AtomAudit。配對：使用者打字之前（turn 4）注入、沒讀 → 照催。"""
    inj = {"name": "foo-atom", "source": "trigger", "form": "skip", "turn_seq": 5, "path": r"c:\proj\memory\foo-atom.md"}
    state = _user_then_peers(monkeypatch, peers=1, injection_log=[inj])
    out, _, _ = driven("全部完成了。", capsys, **copy.deepcopy(state))
    assert "[Guardian:AtomAudit]" not in out
    state["injection_log"] = [{**inj, "turn_seq": 4}]
    out, _, _ = driven("全部完成了。", capsys, **state)
    assert "[Guardian:AtomAudit]" in out and "foo-atom" in out


def test_044_6_failing_test_earlier_in_user_turn_is_turn_failure(monkeypatch):
    """stop.py _detect_turn_outcome（注入有用度學習）：turn 5 測試失敗 → 同伴訊息（turn 6）→ 說完成：本回合有失敗，outcome＝失敗。
    舊碼只認 turn_seq==6 的失敗，判成功，把失敗回合記成有用。"""
    state = _user_then_peers(monkeypatch, peers=1, failing_tests=[{"test": "t", "turn_seq": 5, "session_id": _SID}])
    assert st._detect_turn_outcome(state, "全部完成了。", _SID) is False


def test_044_6_subagent_pass_spanning_user_turns_counts(sub_stop, capsys):
    """SubagentStop（規則 TURN_SINCE_USER_PROMPT 的子代理起點）：背景子代理 turn 5 開跑、改檔並跑出 PASS → 使用者 turn 7 又打字 →
    子代理 turn 8 收尾說修好：本回合從子代理自己最早一筆紀錄算起，(a) 不擋。舊碼只認 turn_seq==8，擋到底（子代理不能放行）。"""
    key = vl.agent_receipt_key(_SID, "ag1")
    s = _sub_state(turn_seq=8, turn_prompts_seq=7,
                   agent_modified_files={"ag1": [_mf(_CODE, 5, last_at=_T1, last_seq=1), _mf(_CASE, 5, last_at=_T1, last_seq=2)]},
                   verify_receipts={key: [_rcpt(5, cmd=_RELATED_CMD, at=_T2, seq=3)]})
    out, _ = sub_stop(capsys, s, last="x.py 修好了，全部完成了。")
    assert _A_HIT not in out
    s["verify_receipts"] = {key: []}                                                        # 配對：子代理沒有 PASS → 照擋
    out, _ = sub_stop(capsys, s, last="x.py 修好了，全部完成了。")
    assert _A_HIT in out


# ─── g12w：收尾檢核附「這次對閱讀路徑的影響」（真 Stop 入口） ───────────────────────────────

import wg_reading_path as rph  # noqa: E402

_RP_BODY = "def {0}(n):\n    k = n + 1\n    k *= 2\n    return k\n"
_RP_APP = {"app.py": "from x import a\nfrom y import b\n\n\ndef main():\n    n = a(1)\n    n += b(2)\n    return n\n\n\n"
                     'if __name__ == "__main__":\n    main()\n',
           "x.py": _RP_BODY.format("a"), "y.py": _RP_BODY.format("b"), "notes.md": "# n\n", "todo.md": "# t\n"}


def _rp_repo(repo: Path, monkeypatch, jobs: Path, worker_run=subprocess.run) -> Path:
    """真 git 夾具；背景量測換成同行程直接跑完（照寫結果檔），工作檔放受測目錄外（git 錄製重播只比對受測目錄）。"""
    def spawn(path):
        job = json.loads(Path(path).read_text(encoding="utf-8"))
        rph.write_result(Path(job["out"]), rph.run_job(job, run=worker_run))

    monkeypatch.setattr(rph, "JOB_DIR", jobs)
    monkeypatch.setattr(rph, "_spawn_worker", spawn)
    repo.mkdir(parents=True)
    for rel, text in _RP_APP.items():
        (repo / rel).write_text(text, encoding="utf-8", newline="\n")
    _git(repo, "init", "-q")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", ".")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    return repo


def test_g12w_code_turn_hands_off_then_the_next_stop_appends_reading_path(driven, capsys, tmp_path, tmp_path_factory,
                                                                         monkeypatch):
    """改碼回合：真 Stop 入口只把量測交給背景、這次擋的訊息不附；背景量完，下一次收尾在擋的訊息後附「改動對閱讀路徑的影響」：
    比較尾行、可評級與否、變差／新增最差一條。附段落本身不擋、不吃 stop_blocked_count；量過的輸入記在 state["reading_path"][sid]。"""
    repo = _rp_repo(tmp_path / "rp", monkeypatch, tmp_path_factory.mktemp("rp-jobs"))
    (repo / "y.py").write_text("from z import c\n\n\ndef b(n):\n    return c(n)\n", encoding="utf-8", newline="\n")
    (repo / "z.py").write_text(_RP_BODY.format("c"), encoding="utf-8", newline="\n")
    _git(repo, "add", "z.py")
    mods = [_mf(str(repo / "y.py"), 5), _mf(str(repo / "z.py"), 5)]
    out, state, _ = driven("全部完成了。", capsys, modified_files=mods)
    assert "ReadingPath" not in json.loads(out)["reason"] and state["reading_path"][_SID]["job"], "交給背景量的那次不附"
    out, state, _ = driven("全部完成了。", capsys, modified_files=mods, reading_path=state["reading_path"])
    reason = json.loads(out)["reason"]
    assert "[Guardian:ReadingPath] 第 5 回合改動對閱讀路徑的影響（背景量完" in reason, reason[-800:]
    assert "READING_PATH DONE mode=compare" in reason and "可評級：" in reason and "[新增]" in reason and "z.py::c" in reason
    assert state["stop_blocked_count"] == 0 and state["reading_path"][_SID]["key"] and "job" not in state["reading_path"][_SID]


def test_g12w_no_code_change_this_turn_appends_nothing(driven, capsys, tmp_path, tmp_path_factory, monkeypatch):
    """沒改程式碼的回合不附：這回合只改 .md（照樣被一般收尾擋），或程式檔是前幾回合改的。
    前置：兩個 .md 真的改了、還沒 commit（已同步的檔照 SYNC_BLOCK_SKIPS_SYNCED 不擋，就驗不到「照樣被擋卻不附」）。"""
    repo = _rp_repo(tmp_path / "rp", monkeypatch, tmp_path_factory.mktemp("rp-jobs"))
    for name in ("notes.md", "todo.md"):
        (repo / name).write_text("# 改了\n", encoding="utf-8", newline="\n")
    docs = [_mf(str(repo / "notes.md"), 5), _mf(str(repo / "todo.md"), 5)]
    out, state, _ = driven("接著看下一段。", capsys, modified_files=docs)
    assert "Workflow Guardian" in state["_err"] and "ReadingPath" not in out and "reading_path" not in state
    out, st2, _ = driven("接著看下一段。", capsys, modified_files=docs + [_mf(str(repo / "y.py"), 3)])
    assert "Workflow Guardian" in out + st2["_err"] and "ReadingPath" not in out


def test_g12w_timeout_appends_the_reason_without_a_manual_command(driven, capsys, tmp_path, tmp_path_factory, monkeypatch):
    """量尺在背景預算內量不完：下一次收尾只附原因、不附手動指令（模型會接單去跑），照樣不擋（擋的是原本的閘）。
    逾時用假的 run 丟 TimeoutExpired，不真的等。"""
    def tool_times_out(args, **kw):
        if str(rph.TOOL) in args:
            raise subprocess.TimeoutExpired(args, kw.get("timeout"))
        return subprocess.run(args, **kw)

    repo = _rp_repo(tmp_path / "rp", monkeypatch, tmp_path_factory.mktemp("rp-jobs"), worker_run=tool_times_out)
    (repo / "y.py").write_text(_RP_BODY.format("b") + "\n", encoding="utf-8", newline="\n")
    mods = [_mf(str(repo / "y.py"), 5), _mf(str(repo / "x.py"), 5)]
    _, state, _ = driven("全部完成了。", capsys, modified_files=mods)
    out, state, _ = driven("全部完成了。", capsys, modified_files=mods, reading_path=state["reading_path"])
    reason = json.loads(out)["reason"]
    assert "[Guardian:ReadingPath]" in reason and f"背景 {rph.WORKER_BUDGET_S:g} 秒內量不完" in reason, reason[-600:]
    assert "手動" not in reason and "--before" not in reason and state["stop_blocked_count"] == 0


# ═══ 045（track-gate-rules）：清冊 B／C 組規則的端到端案（真 git repo） ═══════════════════════════════

_T3 = "2026-10-12T10:10:00+08:00"


def _repo_with_code_and_case(base: Path):
    """真 git repo：src/a.py 與 tests/test_suite.py 同一筆提交。回 (repo, code, case)。"""
    repo = base / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    code, case = repo / "src" / "a.py", repo / "tests" / "test_suite.py"
    code.write_text("def a():\n    return 1\n", encoding="utf-8", newline="\n")
    case.write_text("def test_a():\n    assert a() == 1\n", encoding="utf-8", newline="\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    return repo, code, case


def test_004_committed_equal_paths_git_calls_fixed_per_root(tmp_path):
    """004 件 8：對帳閘查「內容回到已提交版本／只差註解」每個根固定 3 支 git（cat-file --batch-check、hash-object、
    cat-file --batch），不隨改檔數與 ref 數長（舊碼：show-ref＋每個 ref 一支 ls-tree＋每個 .py 一支 git show）；判定照舊。"""
    import subprocess
    repo, code, _case = _repo_with_code_and_case(tmp_path)
    extra = [repo / "src" / f"m{i}.py" for i in range(4)]
    for p in extra:
        p.write_text("def f():\n    return 1\n", encoding="utf-8", newline="\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "more")
    _git(repo, "branch", "-f", "main")                                  # 再多一個 ref 指到同一個 commit
    for p in [code, *extra]:
        p.write_text("# 只加註解\n" + p.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return subprocess.run(cmd, **kw)
    mods = [_mf(str(p), 5, last_at=_T2, last_seq=6) for p in [code, *extra]]
    got = vl.committed_equal_paths(mods, vl.reconcile_cfg({}), budget_s=20.0, _run=run)
    assert set(got) == {str(p) for p in [code, *extra]} and {v.rule for v in got.values()} == {"COMMENT_ONLY_CHANGE"}, got
    assert len(calls) <= 3, [c[5:7] for c in calls]


def test_004_batch_git_reads_mixed_missing_spaces_crlf_non_ascii_and_no_refetch(tmp_path):
    """codex 004 NOTE：批次查詢的解析直接驗：同一支 cat-file --batch-check 裡成功與 missing 混排、路徑含空白與中文；cat-file --batch
    取 CRLF／中文內容的 blob、混一個不存在的 sha；取內容失敗時同根不再重取（照算改了，呼叫次數不隨檔數長）。"""
    import subprocess
    import time
    repo, _code, _case = _repo_with_code_and_case(tmp_path)
    sp, zh = repo / "src" / "a b.py", repo / "src" / "中文.py"
    sp.write_bytes(b"def f():\r\n    return 1\r\n")
    zh.write_bytes("def g():\n    return '中文'\n".encode("utf-8"))
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "more")
    facts = vl.ref_blob_facts(repo, ["src/a b.py", "src/中文.py", "src/nope.py"], time.monotonic() + 20)
    head = facts["blobs"]["HEAD"]
    assert set(head) == {"src/a b.py", "src/中文.py"} and "HEAD" in facts["commits"], facts
    texts = vl._blob_texts(repo, [head["src/a b.py"], head["src/中文.py"], "0" * 40], time.monotonic() + 20, None)
    assert texts == {head["src/a b.py"]: "def f():\r\n    return 1\r\n", head["src/中文.py"]: "def g():\n    return '中文'\n"}, texts
    for p in (sp, zh):
        p.write_bytes(b"# c\n" + p.read_bytes())
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        if "--batch" in cmd:
            return subprocess.CompletedProcess(cmd, 1, b"", b"boom")
        return subprocess.run(cmd, **kw)
    mods = [_mf(str(p), 5, last_at=_T2, last_seq=6) for p in (sp, zh)]
    got = vl.committed_equal_paths(mods, vl.reconcile_cfg({}), budget_s=20.0, _run=run)
    assert got == {} and sum("--batch" in c for c in calls) == 1, [c[5:7] for c in calls]


def _green(repo: Path, cmd: str, at: str, seq: int, turn: int = 5):
    return {"turn_seq": turn, "tool": "Bash", "cmd": cmd, "sentinels": [{"name": "PYTEST_MEASURE", "verdict": "PASS", "kv": {}}],
            "exit_code": 0, "at": at, "seq": seq, "project_root": str(repo), "cwd": str(repo), "env": {}}


def test_045_b1_red_then_green_case_covers_code_regardless_of_order(driven, capsys, tmp_path, monkeypatch):
    """規則 CASE_COVERS_CHANGE（先紅後綠）：先寫會紅的案例 tests/test_a.py（T1）→ 改程式（T2）→ (d) 不欠：案例檔名照模組取就是覆蓋，
    不比先後、不看有沒有跑綠（舊碼：程式比案例新就欠，要點名該案例且晚於改程式的 PASS 才清）；配對：只改了不提到 a.py 的案例 → 照欠。"""
    monkeypatch.setattr(vl, "case_exists", os.path.isfile, raising=False)
    monkeypatch.setattr(vl, "code_exists", os.path.isfile, raising=False)
    repo, code, other = _repo_with_code_and_case(tmp_path)
    case = repo / "tests" / "test_a.py"
    case.write_text("def test_a():\n    assert a() == 2\n", encoding="utf-8", newline="\n")      # 先寫會紅的案例
    code.write_text("def a():\n    return 2\n", encoding="utf-8", newline="\n")                   # 再改程式
    mods = [_mf(str(case), 5, last_at=_T1, last_seq=5), _mf(str(code), 5, last_at=_T2, last_seq=6)]
    early = _green(repo, "python -m pytest -q tests/test_a.py", _T1, 4)                          # 綠在改程式之前也不影響 (d)
    out, _, _ = driven("全部完成了。", capsys, modified_files=mods, verify_receipts={_SID: [early]})
    assert "改了程式碼（a.py）" not in out, out
    out, _, _ = driven("全部完成了。", capsys, modified_files=mods)
    assert "改了程式碼（a.py）" not in out, out
    other.write_text("def test_other():\n    assert True\n", encoding="utf-8", newline="\n")      # 配對：只改不相干的案例
    mods = [_mf(str(other), 5, last_at=_T1, last_seq=5), _mf(str(code), 5, last_at=_T2, last_seq=6)]
    out, _, _ = driven("全部完成了。", capsys, modified_files=mods)
    assert "(d) CASE_COVERS_CHANGE：改了程式碼（a.py）" in out


def test_045_reverted_code_files_needs_every_own_code_file_reverted(tmp_path, monkeypatch):
    """codex 001 BLOCK 5（RED_WHILE_REVERTED 的事實）：A 退回 main 版、B 還留著自己的碼 → (退回=[A], 現行=[B])，呼叫端判不是刻意紅；
    B 也退回 → 現行空。"""
    import subprocess as sp
    monkeypatch.setattr(vl, "REF_BUDGET_S", 20.0, raising=False)
    repo, code, case = _repo_with_code_and_case(tmp_path)
    b = repo / "src" / "b.py"
    b.write_text("def b():\n    return 1\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "src/b.py")
    _git(repo, "commit", "-qm", "b")
    main_name = sp.run(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
    _git(repo, "checkout", "-q", "-b", "feat")
    code.write_text("def a():\n    return 'feat'\n", encoding="utf-8", newline="\n")
    b.write_text("def b():\n    return 'feat'\n", encoding="utf-8", newline="\n")
    _git(repo, "commit", "-qam", "feat")
    # 退回 A 成 main 版、B 改成自己的新碼
    code.write_text("def a():\n    return 1\n", encoding="utf-8", newline="\n")
    b.write_text("def b():\n    return 'mine'\n", encoding="utf-8", newline="\n")
    mods = [_mf(str(code), 5), _mf(str(b), 5)]
    reverted, pending = vl.reverted_code_files(mods, vl.RECONCILE_DEFAULTS)
    assert reverted == [("a.py", main_name)] and pending == ["b.py"]
    b.write_text("def b():\n    return 1\n", encoding="utf-8", newline="\n")                      # B 也退回 → 刻意紅成立
    reverted, pending = vl.reverted_code_files(mods, vl.RECONCILE_DEFAULTS)
    assert sorted(n for n, _ in reverted) == ["a.py", "b.py"] and pending == []


def test_045_b13_checkout_theirs_in_merge_equals_merge_head_not_owed(driven, capsys, tmp_path, monkeypatch):
    """規則 CONTENT_EQUALS_COMMITTED：merge main 衝突時 `git checkout --theirs src/a.py` 取 main 版（內容等於 MERGE_HEAD 的 blob）
    → 不是本 session 改碼、(d) 不欠；配對：內容與 MERGE_HEAD／main 都不同 → 照欠。"""
    import subprocess as sp
    monkeypatch.setattr(vl, "case_exists", os.path.isfile, raising=False)
    monkeypatch.setattr(vl, "code_exists", os.path.isfile, raising=False)
    monkeypatch.setattr(vl, "REF_BUDGET_S", 20.0, raising=False)
    monkeypatch.setattr(vl, "GIT_BUDGET_S", 20.0, raising=False)
    repo, code, case = _repo_with_code_and_case(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feat")
    code.write_text("def a():\n    return 'feat'\n", encoding="utf-8", newline="\n")
    _git(repo, "commit", "-qam", "feat")
    _git(repo, "checkout", "-q", "-")
    code.write_text("def a():\n    return 'main'\n", encoding="utf-8", newline="\n")
    _git(repo, "commit", "-qam", "main side")
    main_name = sp.run(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
    _git(repo, "checkout", "-q", "feat")
    r = sp.run(["git", "-C", str(repo), "merge", main_name], capture_output=True, text=True)
    assert r.returncode != 0 and (repo / ".git" / "MERGE_HEAD").exists()                        # 衝突中
    _git(repo, "checkout", "--theirs", "--", "src/a.py")                                        # 取 main 版
    mods = [_mf(str(code), 5, last_at=_T2, last_seq=6)]
    out, _, _ = driven("全部完成了。", capsys, modified_files=mods)
    assert "改了程式碼（a.py）" not in out, out
    code.write_text("def a():\n    return 'mine'\n", encoding="utf-8", newline="\n")             # 配對：自己改的內容 → 照欠
    out, _, _ = driven("全部完成了。", capsys, modified_files=mods)
    assert "改了程式碼（a.py）" in out


def test_045_b3_comment_only_change_not_owed_identifier_change_owed(driven, capsys, tmp_path, monkeypatch):
    """規則 COMMENT_ONLY_CHANGE：只改一行註解／docstring → 不算改碼、(d) 不欠；改一個識別字 → 照欠。"""
    monkeypatch.setattr(vl, "case_exists", os.path.isfile, raising=False)
    monkeypatch.setattr(vl, "code_exists", os.path.isfile, raising=False)
    monkeypatch.setattr(vl, "REF_BUDGET_S", 20.0, raising=False)                       # 負載下 git 慢，不讓預算當判定
    monkeypatch.setattr(vl, "GIT_BUDGET_S", 20.0, raising=False)
    repo, code, case = _repo_with_code_and_case(tmp_path)
    code.write_text("# 新註解\ndef a():\n    \"\"\"doc\"\"\"\n    return 1  # 行尾\n", encoding="utf-8", newline="\n")
    mods = [_mf(str(code), 5, last_at=_T2, last_seq=6)]
    out, _, _ = driven("全部完成了。", capsys, modified_files=mods)
    assert "改了程式碼（a.py）" not in out, out
    code.write_text("def b():\n    return 1\n", encoding="utf-8", newline="\n")
    out, _, _ = driven("全部完成了。", capsys, modified_files=mods)
    assert "改了程式碼（a.py）" in out
    # fail-closed 邊界（對人總控台 #14）：語法錯解析不了 → 照欠；非 Python 檔無法證等值、只剩空白差異 → 照欠
    code.write_text("def a(:\n    return 1\n", encoding="utf-8", newline="\n")
    out, _, _ = driven("全部完成了。", capsys, modified_files=mods)
    assert "改了程式碼（a.py）" in out
    js = repo / "src" / "c.js"
    js.write_text("const c = 1;\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "src/c.js")
    _git(repo, "commit", "-qm", "js")
    js.write_text("const c = 1; \n", encoding="utf-8", newline="\n")
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(str(js), 5, last_at=_T2, last_seq=6)])
    assert "改了程式碼（c.js）" in out


def test_045_a6_amend_message_only_after_covered_commit_not_owed(driven, capsys, chain):
    """A6「amend 只改訊息」：改程式＋補覆蓋它的案例 → commit → `commit --amend` 只改訊息 → Stop 不欠；之後再改程式，案例仍覆蓋它 →
    照樣不欠（CASE_COVERS_CHANGE 不比先後）；配對：沒有覆蓋它的案例（只改了不提到 a.py 的案例）→ 照欠。"""
    state, edit, git, repo, code, case = chain                       # 基底 HEAD 已是 v2，本 session 從 v3 起改
    edit(code, 3)
    edit(case, 3)
    git("commit", "-qam", "v3")
    git("commit", "--amend", "-qm", "v3 改訊息")
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **copy.deepcopy(state))
    assert "改了程式碼（a.py）" in out, out                                                       # 案例沒覆蓋 a.py
    _cover(edit, git)
    git("commit", "-q", "--amend", "-m", "v3 補案例")
    edit(code, 4)
    out, _, _ = driven("全部完成了。", capsys, anti_evasion_report=_aec(5, j="無", k="無"), **copy.deepcopy(state))
    assert "改了程式碼（a.py）" not in out, out


def test_045_b2_budget_shared_and_exhausted_message_lists_all(driven, capsys):
    """規則 BLOCK_BUDGET_SHARED：寫碼查核每個使用者回合共用一份預算（鍵 "*"，不分哪一條）：本回合已擋 1 次、這次命中別條 →
    照擋、共 2 次；已擋 2 次 → 擋滿改問放行，擋滿訊息列出全部命中條目（(a) 與 (d) 都在）。"""
    rec = {_SID: {"turn": 5, "counts": {"*": 1}, "count": 1}}
    out, state, _ = driven("閘修好了，完成。", capsys, reconcile_gate_turn=rec)
    assert "【收尾放行確認】" not in out and state["reconcile_gate_turn"][_SID]["counts"] == {"*": 2}   # 第 2 次照擋
    rec = {_SID: {"turn": 5, "counts": {"*": 2}, "count": 2}}
    out, state, _ = driven("閘修好了，完成。", capsys, reconcile_gate_turn=rec, modified_files=[_mf(_CODE, 5, last_at=_T1, last_seq=1)])
    head = out.split("原擋訊息")[0]
    assert "【收尾放行確認】" in out and "(a) CLAIM_FIXED_NEEDS_PASS" in head and "(d) CASE_COVERS_CHANGE" in head


def test_045_vcs_root_unreadable_still_owes(driven, capsys, monkeypatch):
    """規則 VCS_ROOT_UNREADABLE（⑧）：找版控根時 OSError → 讀不到不是不在版控，已不存在的改檔照欠；舊碰把兩者都當 None 就不欠。"""
    monkeypatch.setattr(vl, "code_exists", lambda p: False, raising=False)
    monkeypatch.setattr(vl, "find_vcs_root_ex", lambda d: (None, "PermissionError: [WinError 5] 存取被拒"))
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(r"\\srv\share\proj\x.py", 5, last_at=_T1, last_seq=1)])
    assert "VCS_ROOT_UNREADABLE" in out and "改了程式碼（x.py）" in out


@pytest.fixture(autouse=True)
def _cassette(git_cassette):
    """git 子程序錄製重播（lib/git_cassette.py）：平常重播一次真實執行的紀錄、不開 git；git 互動改了 → 失敗要求
    pytest --git-record 重錄。"""
    git_cassette()


# ─── 046 收尾少空轉：已同步的檔不再提醒（SYNC_BLOCK_SKIPS_SYNCED）、擋一次就列出後面還欠的閘（BLOCK_LISTS_LATER_GATES） ───

def _git_out(repo: Path, *args: str) -> str:
    import subprocess
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _synced_repo(tmp_path: Path, names=("a.md", "b.md", "c.md")):
    """真 git repo，names 都已 commit、分支沒有 upstream。回 (repo, 檔案路徑清單)。"""
    repo = tmp_path / "syncrepo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    files = [repo / n for n in names]
    for f in files:
        f.write_text("v1\n", encoding="utf-8", newline="\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    return repo, files


def test_046_sync_block_skips_committed_files(driven, capsys, tmp_path):
    """規則 SYNC_BLOCK_SKIPS_SYNCED：改過的三個檔都已 commit（分支沒 upstream → 不要求 push）→ 底部 sync block 不擋。
    先斷言前置：git status 乾淨。再改其中兩個 → 照擋，而且只數沒同步的那兩個。舊碼只數 state 的改檔 → 已 commit 也擋（紅）。"""
    repo, (a, b, c) = _synced_repo(tmp_path)
    assert _git_out(repo, "status", "--porcelain") == ""
    mf = [_mf(str(p), 5) for p in (a, b, c)]
    out, state, _ = driven("好了。", capsys, modified_files=mf)
    assert "[Workflow Guardian]" not in out and "file(s) modified" not in state["_err"] and state["phase"] == "done", out
    b.write_text("v2\n", encoding="utf-8", newline="\n")
    c.write_text("v2\n", encoding="utf-8", newline="\n")
    out, st_, _ = driven("好了。", capsys, modified_files=mf)
    assert "[Workflow Guardian] 2 file(s) modified" in st_["_err"] and "a.md" not in out, out


def test_046_sync_block_still_owes_unpushed_commits(driven, capsys, tmp_path):
    """反例：有 upstream 時，已 push → 不擋；再 commit 兩個檔但沒 push → 照擋（commit 不等於同步）。"""
    repo, (a, b, _c) = _synced_repo(tmp_path)
    remote = tmp_path / "remote.git"
    _git(repo, "init", "-q", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "HEAD")
    mf = [_mf(str(p), 5) for p in (a, b)]
    out, st_, _ = driven("好了。", capsys, modified_files=mf)
    assert "[Workflow Guardian]" not in out and "file(s) modified" not in st_["_err"], out
    a.write_text("v2\n", encoding="utf-8", newline="\n")
    b.write_text("v2\n", encoding="utf-8", newline="\n")
    _git(repo, "commit", "-qam", "local only")
    assert _git_out(repo, "rev-list", "--count", "@{u}..HEAD") == "1"
    out, _, _ = driven("好了。", capsys, modified_files=mf)
    assert "[Guardian:SyncReminder]" in out and "尚未 push" in out, out                   # 上面那道先提醒一次
    out, st_, _ = driven("好了。", capsys, modified_files=mf, sync_reminder_count=1)
    assert "[Workflow Guardian]" not in out and "[Workflow Guardian] 2 file(s) modified" in st_["_err"], out   # 提醒用完：底部只留 stderr、不重擋


def test_046_sync_block_skips_files_whose_vcs_root_vanished(driven, capsys, tmp_path):
    """規則 SYNC_SKIPS_VANISHED_OUTSIDE_VCS，照接續單的工作樹流程走真 git：在 worktree 改兩個檔 → 在 worktree 提交 → 合回 main →
    `git worktree remove`。移除後檔與所在版控根都不在，沒有東西可同步，底部 sync block 不擋。前置逐步斷言：tmp 不在任何版控根之下、
    改完還沒提交時照擋。舊碼移除後也擋（紅，2026-10-20 v6 推進 session 刪工作樹後連擋兩次）。"""
    assert st._find_vcs_root(tmp_path) is None                                             # 前置：往上找不到版控根
    repo, _files = _synced_repo(tmp_path, names=("a.md", "b.md"))
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "feat", str(wt))
    a, b = wt / "a.md", wt / "b.md"
    a.write_text("v2\n", encoding="utf-8", newline="\n")
    b.write_text("v2\n", encoding="utf-8", newline="\n")
    mf = [_mf(str(p), 5) for p in (a, b)]
    out, st_, _ = driven("好了。", capsys, modified_files=mf)
    assert "[Workflow Guardian] 2 file(s) modified" in st_["_err"], out                            # 前置：還沒提交 → 照擋
    _git(wt, "commit", "-qam", "feat")
    _git(repo, "merge", "-q", "--ff-only", "feat")
    _git(repo, "worktree", "remove", str(wt))
    assert not wt.exists() and (repo / "a.md").read_text(encoding="utf-8") == "v2\n"
    out, st_, _ = driven("好了。", capsys, modified_files=mf)
    assert "[Workflow Guardian]" not in out and "file(s) modified" not in st_["_err"], out


def test_046_sync_block_vanished_counter_cases_still_owe(driven, capsys, tmp_path):
    """反例（期望照擋，先斷言前置）：①檔還在但不在任何版控裡 → 照算未同步；②路徑所在的磁碟根連不到（斷線的網路磁碟看起來也像
    檔不在、版控根也找不到）→ 不能當成已刪除，照算未同步（Codex BLOCK）。"""
    import os
    import string
    loose = tmp_path / "loose"
    loose.mkdir()
    kept = [loose / "n1.md", loose / "n2.md"]
    for f in kept:
        f.write_text("x\n", encoding="utf-8", newline="\n")
    assert st._find_vcs_root(loose) is None and all(f.exists() for f in kept)
    out, st_, _ = driven("好了。", capsys, modified_files=[_mf(str(p), 5) for p in kept])
    assert "[Workflow Guardian] 2 file(s) modified" in st_["_err"], out
    drive = next(f"{c}:\\" for c in reversed(string.ascii_uppercase) if not os.path.isdir(f"{c}:\\"))
    gone = [_mf(drive + r"proj\a.md", 5), _mf(drive + r"proj\b.md", 5)]
    assert not os.path.lexists(gone[0]["path"])                                            # 前置：連不到，看起來就是不在
    out, st_, _ = driven("好了。", capsys, modified_files=gone)
    assert "[Workflow Guardian] 2 file(s) modified" in st_["_err"], out


def test_046_block_lists_later_gates(driven, capsys, monkeypatch, tmp_path):
    """規則 BLOCK_LISTS_LATER_GATES：退縮閘擋下時，照目前狀態後面還欠知識收割、收尾檢核、同步 → 同一則訊息列出來，一回合補齊。
    當下這道就是知識收割時，預覽不重複列它。舊碼每次只回第一道（紅）。"""
    monkeypatch.setattr(st, "deferral_gate_reason", lambda *a, **k: "[Guardian:DeferralGate] 把可做的事推給下個 session")
    monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: "[Guardian:KnowledgeHarvest] 先收割")
    monkeypatch.setattr(st, "detect_missing_aec_emission", lambda *a, **k: True)
    docs = tmp_path / "proj" / "docs"
    docs.mkdir(parents=True)
    for n in ("a.md", "b.md"):
        (docs / n).write_text("x\n", encoding="utf-8", newline="\n")
    assert st._find_vcs_root(docs) is None
    mf = [_mf(str(docs / "a.md"), 5), _mf(str(docs / "b.md"), 5)]   # 還在、不在版控：照算未同步（不存在的假路徑會被 SYNC_SKIPS_VANISHED_OUTSIDE_VCS 剔掉）
    out, _, _ = driven("好了。", capsys, modified_files=mf, need_goal_code_decl_turn=5)   # 寫碼回合才查退縮語
    assert "DeferralGate" in out and "[Guardian:AlsoOwed]" in out, out
    later = out.split("[Guardian:AlsoOwed]", 1)[1]
    assert "knowledge_harvest_report" in later and "anti_evasion_report" in later, later
    assert "同步：" not in later, later      # 後面還欠收尾檢核：(g) 會交代版控，同步不重列（SYNC_COVERED_BY_CLOSING_CHECK）
    monkeypatch.setattr(st, "deferral_gate_reason", lambda *a, **k: None)
    out, _, _ = driven("好了。", capsys, modified_files=mf)
    assert "[Guardian:KnowledgeHarvest] 先收割" in out and "[Guardian:AlsoOwed]" in out, out
    later = out.split("[Guardian:AlsoOwed]", 1)[1]
    assert "knowledge_harvest_report" not in later and "anti_evasion_report" in later, later


def test_046_block_lists_nothing_when_nothing_else_owed(driven, capsys, monkeypatch):
    """期望不發生要先斷言前置：退縮閘真的擋了；後面三道都不欠 → 不附預覽段。"""
    monkeypatch.setattr(st, "deferral_gate_reason", lambda *a, **k: "[Guardian:DeferralGate] 把可做的事推給下個 session")
    monkeypatch.setattr(st, "detect_missing_aec_emission", lambda *a, **k: False)
    out, _, _ = driven("好了。", capsys, modified_files=[], need_goal_code_decl_turn=5)
    assert "DeferralGate" in out and "[Guardian:AlsoOwed]" not in out, out


# ─── 收尾瘦身：只有 reconcile_gate.block_letters 列的條目會擋（規則 RECONCILE_BLOCK_LETTERS） ─────────────────
# 使用者拍板：寫碼查核只留「測試沒過不准說修好」(a) 與「改了程式要有測試」(d)；說量了 (b)、說試過 (c)、搬目錄收據 (v)、
# 收尾報告欄 (e) 只提示不擋。程式預設照舊全擋，live 設定只列 a、d。

_TRIM = {"reconcile_gate": {"block_letters": ["a", "d"]}}


def test_trim_unlisted_letters_do_not_block(driven, capsys):
    """(b) 說量了沒 DONE、(c) 說跑了卻沒執行：預設照擋（前置），block_letters 只列 a、d 時不擋。舊碼不認這個鍵 → 紅。"""
    for text, letter, kw in (("我量了，平均 120 ms，完成。", "(b)", {"verify_receipts": {_SID: [_rcpt(5, "PASS")]}}),
                             ("我跑了測試，完成。", "(c)", {"tool_names": ["Read", "Edit"]})):
        out, _, _ = driven(text, capsys, **kw)
        assert "ReconcileGate" in out and letter in out, out           # 前置：預設設定照擋
        out, _, _ = driven(text, capsys, config=_TRIM, **kw)
        assert "ReconcileGate" not in out, out


def test_trim_kept_letters_still_block(driven, capsys):
    """留著的兩件照擋：說修好卻沒有任何 PASS (a)；改了程式之後沒有案例 (d)。"""
    out, _, _ = driven("閘修好了，完成。", capsys, config=_TRIM)
    assert "[Guardian:ReconcileGate]" in out and "(a)" in out, out
    w = _mf(r"c:\proj\src\widget.py", 5, last_at=_T1, last_seq=3)
    out, _, _ = driven("全部完成了。", capsys, config=_TRIM, modified_files=[w])
    assert "(d)" in out and "改了程式碼（widget.py）" in out, out


def test_trim_report_letter_e_unlisted_does_not_block(driven, capsys):
    """收尾報告欄 (e)（k 空字串）：預設照擋（前置），沒列在 block_letters 就不擋。"""
    rec = _aec(5, j="無", k=_q13("aec_empty_k.json", "")["k_followups"])
    out, _, _ = driven("全部完成了。", capsys, modified_files=[_mf(_CASE, 5)], anti_evasion_report=rec)
    assert "(k)" in out and "空字串" in out, out
    out, _, _ = driven("全部完成了。", capsys, config=_TRIM, modified_files=[_mf(_CASE, 5)], anti_evasion_report=rec)
    assert "空字串" not in out, out


def test_trim_live_config_blocks_only_two_things():
    """live 設定照使用者拍板：寫碼查核只擋 a、d；需求目標對照、驗證範圍宣告、收尾檢核、卡片表態都不擋收尾。"""
    cfg = json.loads((HOOKS_DIR.parent / "workflow" / "config.json").read_text(encoding="utf-8"))
    assert cfg["reconcile_gate"]["block_letters"] == ["a", "d"]
    assert cfg["reconcile_gate"]["goal_gate"] is False
    assert cfg["verify_scope"]["enabled"] is False
    assert cfg["aec"]["scan_report_gate"] is False
    assert cfg["atom_audit"]["enabled"] is False


if __name__ == "__main__":
    # 開乾淨的子行程跑：直接跑時本檔先以 __main__ 載入，wg_core 會在 conftest 隔離資料根之前就 import 進來（資料根指到真的
    # 那一份），同一行程裡再收集測試就沿用它，git 錄音的呼叫序列跟著執行位置變；子行程裡照 pytest 跑法從頭載入
    import subprocess
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("STOP_RECONCILE_CHECK PASS" if rc == 0 else "STOP_RECONCILE_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
