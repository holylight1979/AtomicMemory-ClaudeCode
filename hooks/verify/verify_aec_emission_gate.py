"""verify_aec_emission_gate.py — Anti-Evasion HUD 收尾檢核閘（emit 滿足 + sibling 隔離）。

驗證 A/B（Anti-Evasion HUD）核心閉環的閘門正確性，比照 verify_scan_report_session_filter.py：
  - ScanReport 閘滿足方式從 prose 標記 → 本回合 emit anti_evasion_report（turn_seq+session_id 雙鍵）。
  - ★sibling 隔離：隔壁 session 的 emit（session_id 不符）不得放行本 session（本 initiative 核心防護）。
  - 純 commit turn 豁免、own 過濾等既有紀律不回歸。
  - severity 模型（Python/Node single source）+ HUD 不可達 fallback（可觀測性鐵律）。
  - one-writer：post_tool_use 收 MCP emit 事件 → 獨佔寫 state + 落 per-turn 報告檔。

對應：handlers/stop.py（emit 閘 + fallback）、handlers/post_tool_use.py（one-writer 落 state/檔）、
     wg_evasion.py（detect_missing_aec_emission / aec_severity）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from handlers import stop as st  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
from wg_evasion import detect_missing_aec_emission, aec_severity, _aec_blank  # noqa: E402

_SID = "sid"
_CORE = r"c:\a\.claude\hooks\x.py"
_DOC = r"c:\a\.claude\_AIDocs\note.md"
_DONE = "全部完成了"  # claims_completion=True


@pytest.fixture
def driven(monkeypatch):
    """驅動 handle_stop，只保留 gate 控制流；回 drive(modified_files, capsys, **extra) → stdout。

    比照 verify_scan_report_session_filter.py 的 driven fixture（同攔截面）。"""
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: _DONE)
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [])
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)
    monkeypatch.setattr(st, "_hud_alive", lambda *a, **k: (False, {"reason": "test"}))  # Stop 再查：仍死
    monkeypatch.setattr(st, "append_guard_log", lambda *a, **k: None)

    def drive(modified_files, capsys, config=None, **extra):
        state = {
            "phase": "working",
            "modified_files": modified_files,
            "failing_tests": [],
            "recent_user_prompts": [],
            "stop_blocked_count": 0,
        }
        state.update(extra)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, config or {})
        cap = capsys.readouterr()
        drive.err = cap.err   # stderr 另存（HUD 開不起來的一行提示印在這裡），回傳值照舊只有 stdout
        return cap.out

    return drive


def _mf(path, session_id=_SID):
    return {"path": path, "tool": "Edit", "session_id": session_id}


def _emit(turn_seq, session_id=_SID, severity="routine", a="無", b="無", **fields):
    rec = {
        "turn_seq": turn_seq, "session_id": session_id,
        "a": a, "b": b, "severity": severity, "at": "now",
    }
    for k in ("c", "d", "e", "f", "g", "h", "i"):
        rec[k] = fields.get(k, "無")
    return rec


# ─── emit 閘：滿足 / 未滿足 ───────────────────────────────────────

def test_own_core_no_emit_blocks(driven, capsys):
    """本 session own core + 宣告完成 + 未 emit → block，訊息要求呼叫 anti_evasion_report。"""
    out = driven([_mf(_CORE)], capsys, turn_seq=5)
    assert "[Guardian:ScanReport]" in out
    assert "anti_evasion_report" in out


def test_scan_report_gate_switch_off_does_not_block(driven, capsys):
    """收尾瘦身：aec.scan_report_gate=false → 沒交收尾檢核也不擋收尾。前置：同一情境預設照擋。舊碼不認這個鍵 → 紅。"""
    assert "[Guardian:ScanReport]" in driven([_mf(_CORE)], capsys, turn_seq=5)
    assert "ScanReport" not in driven([_mf(_CORE)], capsys, turn_seq=5, config={"aec": {"scan_report_gate": False}})


def test_emit_this_turn_passes(driven, capsys):
    """本回合 emit（turn_seq+session_id 雙鍵皆符）→ 放行，不 block。"""
    out = driven([_mf(_CORE)], capsys, turn_seq=5, anti_evasion_report=_emit(5))
    assert "ScanReport" not in out


def test_sibling_emit_still_blocks(driven, capsys):
    """★核心 sibling 隔離：隔壁 session emit（session_id="other" 不符）→ 本 session 仍 block。

    模擬共用工作樹 / merged state 下，B 讀到的 state 含 A 戳的 emit；雙鍵防誤放行。"""
    out = driven([_mf(_CORE)], capsys, turn_seq=5,
                 anti_evasion_report=_emit(5, session_id="other"))
    assert "[Guardian:ScanReport]" in out


def test_prior_turn_emit_not_satisfied(driven, capsys):
    """emit 發生在別 turn（turn_seq 不符）→ 不滿足，照 block（不因歷史 emit 永久放行）。"""
    out = driven([_mf(_CORE)], capsys, turn_seq=5, anti_evasion_report=_emit(4))
    assert "[Guardian:ScanReport]" in out


def test_turn_seq_zero_guard(driven, capsys):
    """turn_seq==0 的 fallback state：bool(turn_seq)=False → emit 不以 0==0 假滿足 → block。"""
    out = driven([_mf(_CORE)], capsys, turn_seq=0, anti_evasion_report=_emit(0))
    assert "[Guardian:ScanReport]" in out


# ─── 既有紀律不回歸 ──────────────────────────────────────────────

def test_pure_commit_turn_exempt(driven, capsys):
    """純 commit turn 豁免不回歸：committed_this_turn → 不要求 emit（即使動 core）。"""
    out = driven([_mf(_CORE)], capsys, turn_seq=5, last_commit_turn_seq=5)
    assert "ScanReport" not in out


def test_foreign_core_not_triggered(driven, capsys):
    """own 過濾不回歸：他 session 改 core（session_id≠本）→ own 空 → 不觸發。"""
    out = driven([_mf(_CORE, session_id="other")], capsys, turn_seq=5)
    assert "ScanReport" not in out


def test_coordinator_docs_only_not_triggered(driven, capsys):
    """協調 session 只改單一 docs + 隔壁改 core → own 僅單一非 core → 不觸發。"""
    out = driven([_mf(_DOC), _mf(_CORE, session_id="other")], capsys, turn_seq=5)
    assert "ScanReport" not in out


# ─── HUD 不可達 fallback（可觀測性鐵律：push 不到窗不得 fail-silent）──────

def test_hud_fallback_surfaces_notable(driven, capsys):
    """emit 為 notable + HUD 不可達（aec_hud_fallback）→ Stop 印一行告知報告檔在哪（不 fail-silent），
    但不擋、不把報告內容貼回聊天（原設計者裁定：報告任何理由都不進聊天）。"""
    out = driven(
        [_mf(_CORE)], capsys, turn_seq=5,
        anti_evasion_report=_emit(5, severity="notable", a="- x.py:10 — 修了 y"),
        aec_hud_fallback=True,
    )
    assert "[Guardian:AEC]" in driven.err and "aec-report" in driven.err
    assert "修了 y" not in out + driven.err and "[Guardian:AEC]" not in out


# ─── severity 模型（Python/Node single source of truth）──────────

@pytest.mark.parametrize("a,b,expected", [
    ("無", "無", "routine"),
    ("", "", "routine"),
    ("- x.py:1 — fix", "無", "notable"),
    ("無", "偷埋了 X", "real-evasion"),
    ("- x — y", "偷埋", "real-evasion"),  # (b) 優先於 (a)
    # ── blank-detection 回歸：模型慣寫「無。」（含尾標點）須視同「無」，否則 routine 誤升 real-evasion（洗 chat）──
    ("無。", "無", "routine"),               # (a) 尾標點「無。」仍 blank → routine
    ("無程式修補。x", "無。", "notable"),      # (b)「無。」blank 不誤判 real；(a) 真有內容 → notable
    ("無", "我略過了測試", "real-evasion"),   # 守無漏判：(b) 真敘述絕不當 blank
])
def test_aec_severity(a, b, expected):
    assert aec_severity(a, b, "無", "無") == expected


def test_aec_severity_trailing_punct_full_fields():
    """資訊欄亦帶尾標點/括註的 dogfood 現場案例：(b)「無。」須 blank → notable、非 real-evasion。"""
    assert aec_severity("無程式修補。x", "無。", "無。", "無（略）") == "notable"


def test_aec_severity_informational_fields_ignored():
    """(c)–(i) 資訊欄非空不升級 severity（severity 只衡量退避訊號 (a)/(b)）。"""
    assert aec_severity("無", "無", "token 警示!", "有記憶未寫", "偷改了", "裝了套件", "未上", "下一動=x", "temp/foo") == "routine"


@pytest.mark.parametrize("v,blank", [
    ("", True), ("無", True), ("  無  ", True), ("x", False), ("- a — b", False),
    # ── blank-detection 回歸：尾標點「無。」「無、」須 blank；有實質字尾（「無程式修補」）非 blank ──
    ("無。", True), ("無、", True), ("無 。", True), ("無程式修補", False),
])
def test_aec_blank(v, blank):
    assert _aec_blank(v) is blank


# ─── detect_missing_aec_emission 前置門檻（鏡像 scan_report）─────

def _mfs(*paths):
    return [{"path": p, "tool": "Edit"} for p in paths]


def test_detect_no_completion_not_blocked():
    assert detect_missing_aec_emission("還在做", _mfs(_CORE), [], 2, False) is False


def test_detect_single_noncore_not_blocked():
    assert detect_missing_aec_emission(
        _DONE, _mfs(r"c:\a\.claude\memory\f.md"), [], 2, False
    ) is False


def test_detect_core_missing_emit_blocks():
    assert detect_missing_aec_emission(_DONE, _mfs(_CORE), [], 2, False) is True


def test_detect_core_emitted_not_blocked():
    assert detect_missing_aec_emission(_DONE, _mfs(_CORE), [], 2, True) is False


def test_detect_dismiss_prompt_not_blocked():
    assert detect_missing_aec_emission(_DONE, _mfs(_CORE), ["先這樣"], 2, False) is False


# ─── one-writer：post_tool_use 收 MCP emit → 獨佔寫 state + 落報告檔 ──────

def _drive_ptu(monkeypatch, tmp_path, tool_input, turn_seq=7, session_id=_SID, **extra):
    state = {"turn_seq": turn_seq, **extra}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(pt, "_hud_alive", lambda *a, **k: (False, {"reason": "test"}))  # HUD 死
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_spawn_hud_edge", lambda *a, **k: None)
    inp = {
        "session_id": session_id,
        "tool_name": "mcp__workflow-guardian__anti_evasion_report",
        "tool_input": tool_input,
        "tool_response": {},
    }
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}, "aec": {}})
    return state


def test_ptu_emit_writes_state_and_file(monkeypatch, tmp_path):
    """emit notable → state["anti_evasion_report"] 帶原始 session_id+turn_seq + 落 per-turn 檔
    + notable+HUD死 → aec_hud_fallback。"""
    state = _drive_ptu(
        monkeypatch, tmp_path,
        {"a": "- x.py:10 — fix", "b": "無", "c": "無", "d": "無", "e": "無",
         "f": "無", "g": "無", "h": "可關閉", "i": "無"},
    )
    aec = state.get("anti_evasion_report")
    assert aec and aec["turn_seq"] == 7 and aec["session_id"] == _SID
    assert aec["severity"] == "notable"
    p = tmp_path / "aec-report" / f"{_SID}-t7.json"
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["a"].startswith("- x.py:10")
    assert data["session_id"] == _SID and data["turn_seq"] == 7
    assert state.get("aec_hud_fallback") is True


def test_ptu_routine_no_fallback(monkeypatch, tmp_path):
    """routine emit → 落檔但窗死不 fallback（無退避訊號、可事後由歷史格瀏覽）。"""
    state = _drive_ptu(
        monkeypatch, tmp_path,
        {"a": "無", "b": "無", "c": "無", "d": "無", "e": "無",
         "f": "無", "g": "無", "h": "可關閉", "i": "無"},
    )
    assert state["anti_evasion_report"]["severity"] == "routine"
    assert (tmp_path / "aec-report" / f"{_SID}-t7.json").exists()
    assert not state.get("aec_hud_fallback")


# ─── AEC-Pending：(d)/(h) 把「記憶寫入」推到之後 ─────────────────────────────
# 真實案例（2026-09-03 d38eaff2-t8）：(d) 寫「→ 尚未寫（見下一動）」、(h)「下一動=寫一顆 dotnet
# atom」，回合照樣結束，使用者再問一次才補寫。閘門：post_tool_use 落 d_pending、Stop 擋一次。

from wg_evasion import aec_pending_items  # noqa: E402

_D_REAL = (
    "- 「WinForms X」→ 已寫進 MapWindow 註解與 DocIndex；屬 dotnet 跨專案知識，值得 atom → 尚未寫（見下一動）\n"
    "- 使用者 app bin 被鎖 → 既有 atom 已涵蓋，不重寫"
)
_H_REAL = "下一動=寫一顆 dotnet atom（ContextMenuStrip Closed 裡不可 Dispose）；使用者重啟 client 驗"

_PENDING_CASES = [
    # (d, h, expected_count, why)
    (_D_REAL, _H_REAL, 2, "真實案例：(d) 尚未寫（見下一動）+ (h) 下一動=寫 atom"),
    ("- X → 待補 atom", "可關閉", 1, "待補"),
    ("- X → 之後再寫", "可關閉", 1, "之後再寫"),
    ("- X → TODO", "可關閉", 1, "TODO"),
    ("- X → 已寫入 atom Y", "可關閉", 0, "已寫入"),
    ("- 未記錄的踩坑 X → 已寫入 atom Y", "可關閉", 0, "項目段含「未記錄」但結論段已寫入 → 不算"),
    ("- Z → 不寫（之後有需要再補）", "可關閉", 0, "不寫定論優先"),
    ("- Z → 併入既有 atom W（已 append）", "可關閉", 0, "已 append"),
    ("無", "可關閉", 0, "空"),
    ("無", "下一動＝使用者重啟 client 驗刪房", 0, "(h) 使用者動作不算"),
    ("無", "下一動＝補寫 feedback atom", 1, "(h) 模型自己的 atom 工作"),
]


@pytest.mark.parametrize("d,h,n,why", _PENDING_CASES, ids=[c[3] for c in _PENDING_CASES])
def test_aec_pending_items(d, h, n, why):
    assert len(aec_pending_items(d, h)) == n, why


def test_ptu_emit_pending_marks_report(monkeypatch, tmp_path):
    """emit 帶「尚未寫」→ report/state 落 d_pending（HUD 標紅、Stop 閘讀）。"""
    state = _drive_ptu(
        monkeypatch, tmp_path,
        {"a": "無", "b": "無", "c": "無", "d": _D_REAL, "e": "無",
         "f": "無", "g": "無", "h": _H_REAL, "i": "無"},
    )
    aec = state["anti_evasion_report"]
    assert len(aec["d_pending"]) == 2
    data = json.loads((tmp_path / "aec-report" / f"{_SID}-t7.json").read_text(encoding="utf-8"))
    assert data["d_pending"] == aec["d_pending"]


def test_ptu_emit_clean_no_pending_key(monkeypatch, tmp_path):
    state = _drive_ptu(
        monkeypatch, tmp_path,
        {"a": "無", "b": "無", "c": "無", "d": "- X → 已寫入 atom Y", "e": "無",
         "f": "無", "g": "無", "h": "可關閉", "i": "無"},
    )
    assert "d_pending" not in state["anti_evasion_report"]


def test_stop_pending_blocks_once(driven, capsys):
    """本回合 emit 帶 d_pending → Stop 擋（AEC-Pending）；同 turn 已擋過 → 放行（不無限 nag）。"""
    rec = _emit(5, d=_D_REAL, h=_H_REAL)
    rec["d_pending"] = ["- … → 尚未寫（見下一動）", "(h) 下一動=寫一顆 dotnet atom"]
    out = driven([_mf(_CORE)], capsys, turn_seq=5, anti_evasion_report=rec)
    assert "[Guardian:AEC-Pending]" in out and "尚未寫" in out
    out2 = driven([_mf(_CORE)], capsys, turn_seq=5, anti_evasion_report=rec,
                  aec_pending_gate_turn=5)
    assert "AEC-Pending" not in out2


# ─── B7：收尾欄 (j) 證據持久路徑／(k) 追蹤項 ─────────────────────────────────

def _full_input(**over):
    base = {"a": "無", "b": "無", "c": "無", "d": "無", "e": "無", "f": "無", "g": "無", "h": "可關閉", "i": "無",
            "j_evidence_path": "無", "k_followups": "無"}
    base.update(over)
    return base


def test_ptu_emit_stores_j_k_and_missing_flags(monkeypatch, tmp_path):
    """無收據：j「無」合法（j_missing False）；k 空字串 → k_missing True 並回告。"""
    state = _drive_ptu(monkeypatch, tmp_path, _full_input(k_followups=""))
    aec = state["anti_evasion_report"]
    assert aec["j_evidence_path"] == "無" and aec["k_followups"] == ""
    assert aec["j_missing"] is False and aec["k_missing"] is True
    data = json.loads((tmp_path / "aec-report" / f"{_SID}-t7.json").read_text(encoding="utf-8"))
    assert data["k_missing"] is True


def test_ptu_emit_j_missing_when_receipts_exist(monkeypatch, tmp_path):
    """本 session 有驗證收據而 j「無」→ j_missing True；j 指到真存在的檔 → False。"""
    receipts = {"verify_receipts": {_SID: [{"turn_seq": 7, "sentinels": [{"name": "X_CHECK", "verdict": "PASS"}], "exit_code": None}]}}
    state = _drive_ptu(monkeypatch, tmp_path, _full_input(), **receipts)
    assert state["anti_evasion_report"]["j_missing"] is True
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("{}\n", encoding="utf-8", newline="\n")
    state = _drive_ptu(monkeypatch, tmp_path, _full_input(j_evidence_path=str(ledger)), **receipts)
    assert state["anti_evasion_report"]["j_missing"] is False


_RECEIPTS = {"verify_receipts": {_SID: [{"turn_seq": 7, "sentinels": [{"name": "PYTEST", "verdict": "PASS"}], "exit_code": 0}]}}


def _ledger(tmp_path):
    p = tmp_path / "verify-ledger" / f"{_SID}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}\n", encoding="utf-8", newline="\n")
    return p


@pytest.mark.parametrize("j", ["無", "", "  "])
def test_b5_j_autofilled_from_ledger_when_receipts(monkeypatch, tmp_path, capsys, j):
    """B5：pytest 有收據、j 空／「無」→ 系統帶入本 session 帳本絕對路徑（資料根底下），不擋、回告「已自動帶入」（改前 j_missing、要模型自己找）。"""
    ledger = _ledger(tmp_path)
    state = _drive_ptu(monkeypatch, tmp_path, _full_input(j_evidence_path=j), **_RECEIPTS)
    aec = state["anti_evasion_report"]
    assert aec["j_evidence_path"] == str(ledger) and aec["j_autofilled"] is True and aec["j_missing"] is False
    out = capsys.readouterr().out
    assert f"(j) 已自動帶入 {ledger}".replace("\\", "\\\\") in out and "證據持久路徑缺或不存在" not in out


def test_b5_j_not_touched_without_receipts(monkeypatch, tmp_path, capsys):
    """沒收據、j「無」→ 不帶入、不回告 (j)。"""
    _ledger(tmp_path)
    state = _drive_ptu(monkeypatch, tmp_path, _full_input(j_evidence_path="無"))
    aec = state["anti_evasion_report"]
    assert aec["j_evidence_path"] == "無" and "j_autofilled" not in aec and aec["j_missing"] is False
    assert "(j)" not in capsys.readouterr().out


def test_b5_j_model_path_wins(monkeypatch, tmp_path, capsys):
    """有收據、模型填了別的真存在路徑 → 用模型填的；填的不存在 → j_missing，回告印帳本絕對路徑（改前印相對路徑 workflow/verify-ledger/…）。"""
    ledger = _ledger(tmp_path)
    own = tmp_path / "out.csv"
    own.write_text("x", encoding="utf-8")
    state = _drive_ptu(monkeypatch, tmp_path, _full_input(j_evidence_path=str(own)), **_RECEIPTS)
    aec = state["anti_evasion_report"]
    assert aec["j_evidence_path"] == str(own) and "j_autofilled" not in aec and aec["j_missing"] is False
    capsys.readouterr()
    state = _drive_ptu(monkeypatch, tmp_path, _full_input(j_evidence_path="workflow/verify-ledger/x.jsonl"), **_RECEIPTS)
    assert state["anti_evasion_report"]["j_missing"] is True
    assert str(ledger).replace("\\", "\\\\") in capsys.readouterr().out


def test_b5_stop_does_not_block_autofilled_j(monkeypatch, tmp_path, driven, capsys):
    """Stop 對帳閘 (e) 讀報告裡帶入後的 j：有收據、模型 j「無」→ 不出 AEC_EVIDENCE_PATH。"""
    _ledger(tmp_path)
    aec = _drive_ptu(monkeypatch, tmp_path, _full_input(), **_RECEIPTS)["anti_evasion_report"]
    rec = {**aec, "turn_seq": 5}
    out = driven([_mf(_CORE)], capsys, turn_seq=5, anti_evasion_report=rec, verify_receipts=_RECEIPTS["verify_receipts"])
    assert "AEC_EVIDENCE_PATH" not in out


@pytest.mark.skipif(not __import__("shutil").which("node"), reason="node not available")
def test_b5_node_chip_does_not_print_j(tmp_path):
    """Node 端不知收據與 session，不印 (j)（改前一律印「(j) 證據持久路徑未填…請填 workflow/verify-ledger/<sid>.jsonl」）；
    aecEvidenceAutofill 與 Python 同結果（MIRROR）。"""
    import subprocess
    from wg_verify_ledger import aec_evidence_autofill
    ledger = _ledger(tmp_path)
    js = HOOKS_DIR.parent / "tools" / "workflow-guardian-mcp" / "lib" / "anti-evasion.js"
    cases = [["無", True, str(ledger)], ["", True, str(ledger)], ["無", False, str(ledger)], ["x.csv", True, str(ledger)],
             ["無", True, str(tmp_path / "nope.jsonl")]]
    script = ("const p=require('path');const js=process.argv[1];const mp=require.resolve(p.join(p.dirname(js),'mcp.js'));"
              "require.cache[mp]={id:mp,filename:mp,loaded:true,exports:{sendToolResult:(id,t)=>console.log(JSON.stringify(t))}};"
              "const ae=require(js);const c=JSON.parse(process.argv[2]);"
              "console.log(JSON.stringify(c.map(([j,r,l])=>ae.aecEvidenceAutofill(j,r,l))));"
              "ae.toolAntiEvasionReport(1,{a:'無',b:'無',d:'無',h:'可關閉',j_evidence_path:'',k_followups:'無'});")
    res = subprocess.run(["node", "-e", script, str(js), json.dumps(cases, ensure_ascii=False)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res.returncode == 0, res.stderr
    fills, chip = [json.loads(l) for l in res.stdout.strip().splitlines()]
    assert fills == [aec_evidence_autofill(j, r, l) for j, r, l in cases]
    assert "(j)" not in chip and "例行" in chip   # 回條一行白話（不再印英文嚴重度）


def test_ptu_legacy_emit_without_jk_keys_is_exempt(monkeypatch, tmp_path, driven, capsys):
    """舊格式呼叫（a～i，沒有 j／k 鍵）：報告不寫 j／k、不標 k_missing；Stop 對帳閘 (e) 不拿缺鍵當空字串擋（只有明給空字串才擋）。"""
    receipts = {"verify_receipts": {_SID: [{"turn_seq": 7, "sentinels": [{"name": "X_CHECK", "verdict": "PASS"}], "exit_code": None}]}}
    legacy_input = {k: "無" for k in "abcdefghi"}
    legacy_input["h"] = "可關閉"
    state = _drive_ptu(monkeypatch, tmp_path, legacy_input, **receipts)
    aec = state["anti_evasion_report"]
    assert "j_evidence_path" not in aec and "k_followups" not in aec
    assert "j_missing" not in aec and "k_missing" not in aec
    rec = {**aec, "turn_seq": 5}
    out = driven([_mf(_CORE)], capsys, turn_seq=5, anti_evasion_report=rec, verify_receipts=receipts["verify_receipts"])
    assert "ReconcileGate" not in out and "空字串" not in out


def test_scan_report_message_lists_j_and_k(driven, capsys):
    out = driven([_mf(_CORE)], capsys, turn_seq=5)
    assert "(j) 證據持久路徑" in out and "(k) 追蹤項" in out and "十參" in out and "(c) Token" not in out


def test_ptu_k_followups_tracking_hook(monkeypatch, tmp_path):
    """(k)≠「無」→ 呼叫 wg_harvest.append_tracking；k=「無」不呼叫。wg_harvest 的兩函式以 monkeypatch 提供。
    本案的輸入沒有 cwd → slug＝tracking_slug("")＝"_no-cwd"（舊版寫 "root"，讀回端永遠對不上）。"""
    import wg_harvest
    calls = []
    monkeypatch.setattr(wg_harvest, "tracking_entries",
                        lambda sid, turn, k: [] if str(k).strip() in ("", "無") else [{"text": k, "turn_seq": turn}],
                        raising=False)
    monkeypatch.setattr(wg_harvest, "append_tracking", lambda slug, entries: calls.append((slug, entries)), raising=False)
    _drive_ptu(monkeypatch, tmp_path, _full_input(k_followups="[hooks] 補 PowerShell 案"))
    assert len(calls) == 1 and calls[0][0] == "_no-cwd" and calls[0][1][0]["text"] == "[hooks] 補 PowerShell 案"
    _drive_ptu(monkeypatch, tmp_path, _full_input(k_followups="無"))
    assert len(calls) == 1


@pytest.mark.skipif(not __import__("shutil").which("node"), reason="node not available")
def test_aec_evidence_py_js_parity(tmp_path):
    """MIRROR：aecEvidenceMissing／aecFollowupsMissing 與 Python 同結果。"""
    import subprocess
    from wg_verify_ledger import aec_evidence_missing, aec_followups_missing
    exists = tmp_path / "e.txt"
    exists.write_text("x", encoding="utf-8", newline="\n")
    cases = [["無", True], ["無", False], ["", True], [str(exists), True], [str(tmp_path / "nope"), True],
             [f"{exists} \u2014 帳本", True], [f"{exists}\n{tmp_path / 'nope'}", True]]
    ks = ["", "  ", "無", "x \u2014 y"]
    js = HOOKS_DIR.parent / "tools" / "workflow-guardian-mcp" / "lib" / "anti-evasion.js"
    script = ("const ae=require(process.argv[1]);const c=JSON.parse(process.argv[2]);const k=JSON.parse(process.argv[3]);"
              "console.log(JSON.stringify([c.map(([j,r])=>ae.aecEvidenceMissing(j,r)),k.map(x=>ae.aecFollowupsMissing(x))]));")
    res = subprocess.run(["node", "-e", script, str(js), json.dumps(cases, ensure_ascii=False), json.dumps(ks, ensure_ascii=False)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res.returncode == 0, res.stderr
    got_j, got_k = json.loads(res.stdout)
    assert got_j == [aec_evidence_missing(j, r) for j, r in cases]
    assert got_k == [aec_followups_missing(k) for k in ks]


@pytest.mark.skipif(not __import__("shutil").which("node"), reason="node not available")
def test_mcp_schema_requires_j_k():
    import subprocess
    js = HOOKS_DIR.parent / "tools" / "workflow-guardian-mcp" / "lib" / "mcp.js"
    script = ("const m=require(process.argv[1]);const t=m.TOOL_DEFINITIONS.find(x=>x.name==='anti_evasion_report');"
              "console.log(JSON.stringify(t.inputSchema.required));")
    res = subprocess.run(["node", "-e", script, str(js)], capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0, res.stderr
    req = json.loads(res.stdout)
    assert req[-2:] == ["j_evidence_path", "k_followups"] and len(req) == 10 and "c" not in req   # (c) Token 警示欄已刪


def test_stop_pending_sibling_not_blocked(driven, capsys):
    """隔壁 session 的 pending 報告（session_id 不符）不擋本 session；本 session 也未 emit → 走 ScanReport。"""
    rec = _emit(5, session_id="other")
    rec["d_pending"] = ["x"]
    out = driven([_mf(_CORE)], capsys, turn_seq=5, anti_evasion_report=rec)
    assert "AEC-Pending" not in out


@pytest.mark.parametrize("harvest_turn, pending", [(5, False), (4, True)])
def test_044_6_harvest_validated_earlier_in_user_turn_skips_d_pending(monkeypatch, tmp_path, harvest_turn, pending):
    """044 第 6 項（規則 TURN_SINCE_USER_PROMPT；post_tool_use 判 (d) pending 前看「本回合收割已核過」）：使用者 turn 5 打字、收割在
    turn 5 核過 → 同伴訊息讓 turn_seq 到 7 → emit 的 (d) 寫「尚未寫」：收割已核過，(d) 不判 pending。舊碼要收割的 turn_seq 剛好是 7，
    判不到、照標 d_pending（Stop 再擋 AEC-Pending）。配對：收割在使用者打字之前（turn 4）→ 照標。"""
    vals = {"a": "無", "b": "無", "c": "無", "d": _D_REAL, "e": "無", "f": "無", "g": "無", "h": "可關閉", "i": "無"}
    state = _drive_ptu(monkeypatch, tmp_path, vals, turn_seq=7, turn_prompts_seq=5,
                       knowledge_harvest={_SID: {"turn_seq": harvest_turn, "validated": True}})
    assert ("d_pending" in state["anti_evasion_report"]) is pending
