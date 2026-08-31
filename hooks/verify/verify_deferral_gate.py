"""verify_deferral_gate.py — Stop DeferralGate（退縮歸屬）。

純函式：wg_evasion.detect_deferral / deferral_gate_reason；
整合：handlers.stop.handle_stop 走 DeferralGate 分支（driven fixture 比照 verify_aec_emission_gate）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from wg_evasion import detect_deferral, deferral_gate_reason, claims_completion  # noqa: E402
from handlers import stop as st  # noqa: E402

_CFG = {"deferral_gate": {"enabled": True, "max_context_ratio": 0.75, "min_object_chars": 6}}


# ─── detect_deferral：命中（帶受詞）────────────────────────────────

@pytest.mark.parametrize("text", [
    "完工。要不要下個 session 就把 realm atom 瘦身？",                       # 實案：推給下個 session
    "已 push。縮寫 11 KB realm atom 列為獨立議題，不在本案。",              # 實案：獨立議題／不在本案
    "這個 registry 污染 bug 非我造成，留給下個 session 處理。",             # 歸咎非我 + 留給
    "trigger 重疊排序問題屬注入端，記為遺留議題。",                         # 遺留議題
    "I'll leave the flaky test cleanup for the next session.",              # 英文
    "edit_metadata 缺口不是本輪範圍，下一階段再補。",                       # 不是本輪／下一階段再補
])
def test_detect_deferral_hits_with_object(text):
    r = detect_deferral(text, [])
    assert r is not None, text
    assert r["phrase"] and r["sentence"]


# ─── detect_deferral：不命中 ───────────────────────────────────────

@pytest.mark.parametrize("text", [
    "全部完成，工作樹乾淨。",                # 無退縮語
    "下個 session。",                        # 有退縮語但無受詞
    "非我造成",                              # 裸片語
    "",
])
def test_detect_deferral_no_hit(text):
    assert detect_deferral(text, []) is None


def test_detect_deferral_user_explicit_defer_is_escape_hatch():
    text = "完工。realm atom 瘦身留到下個 session 做。"
    assert detect_deferral(text, ["這顆 atom 下個 session 再做就好"]) is None
    assert detect_deferral(text, ["先這樣，其他不用管"]) is None            # 一般 dismiss 也放行
    # 使用者只是「質問」為何要新開 session → 不算放行
    assert detect_deferral(text, ["為什麼你會判斷還需要新開 session？"]) is not None


def test_min_object_chars_respected():
    text = "完工。bug 下個 session。"
    assert detect_deferral(text, [], min_object_chars=6) is None
    assert detect_deferral(text, [], min_object_chars=2) is not None


# ─── completion 詞補「完工／結案」──────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("完工，已 push。", True),
    ("本案結案。", True),
    ("完工狀態尚未確認", False),   # exclude：尚未…（否定修飾）
])
def test_completion_words_extended(text, expected):
    assert claims_completion(text) is expected


# ─── deferral_gate_reason：條件組合 ────────────────────────────────

_DEFER_DONE = "完工，工作樹乾淨。要不要下個 session 再把 realm atom 瘦身？"


def _reason(text=_DEFER_DONE, *, turn=5, gated=None, committed=False, ratio=0.3, cfg=_CFG, prompts=()):
    return deferral_gate_reason(
        text, list(prompts), turn_seq=turn, gated_turn=gated,
        committed_this_turn=committed, context_ratio=ratio, config=cfg,
    )


def test_gate_fires_when_done_and_tokens_plentiful():
    r = _reason()
    assert r and "[Guardian:DeferralGate]" in r
    assert "(a)" in r and "(b)" in r and "(c)" in r
    assert "下個 session" in r                       # 退縮語回顯


def test_gate_skips_when_task_not_done():
    text = "還在修 registry，realm atom 瘦身留給下個 session 處理。"
    assert _reason(text) is None


def test_commit_this_turn_counts_as_done():
    text = "realm atom 瘦身留給下個 session 處理，其餘照舊。"  # 無完成詞
    assert _reason(text) is None
    assert _reason(text, committed=True) is not None


def test_gate_skips_when_context_over_threshold():
    assert _reason(ratio=0.76) is None
    assert _reason(ratio=0.75) is not None


def test_unmeasurable_context_treated_as_plentiful():
    r = _reason(ratio=0.0)
    assert r and "無法量測" in r


def test_gate_once_per_turn():
    assert _reason(turn=5, gated=5) is None
    assert _reason(turn=6, gated=5) is not None
    assert _reason(turn=0, gated=0) is not None      # turn_seq 0 不當作已擋


def test_gate_disabled_by_config():
    assert _reason(cfg={"deferral_gate": {"enabled": False}}) is None
    assert _reason(cfg={}) is not None               # 缺 config → 預設開


# ─── handle_stop 整合 ─────────────────────────────────────────────

@pytest.fixture
def driven(monkeypatch):
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [])
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)
    monkeypatch.setattr(st, "estimate_context_usage", lambda *a, **k: 0.3)

    def drive(last_text, capsys, **extra):
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: last_text)
        state = {
            "phase": "working", "modified_files": [], "failing_tests": [],
            "recent_user_prompts": [], "stop_blocked_count": 0, "turn_seq": 7,
        }
        state.update(extra)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": "sid", "cwd": ""}, _CFG)
        return capsys.readouterr().out, state

    return drive


def test_stop_blocks_on_deferral(driven, capsys):
    out, state = driven(_DEFER_DONE, capsys)
    assert "[Guardian:DeferralGate]" in out
    assert state["deferral_gate_turn"] == 7
    assert state["stop_blocked_count"] == 1


def test_stop_does_not_reblock_same_turn(driven, capsys):
    out, _ = driven(_DEFER_DONE, capsys, deferral_gate_turn=7)
    assert "[Guardian:DeferralGate]" not in out


def test_stop_passes_when_context_high(driven, capsys, monkeypatch):
    monkeypatch.setattr(st, "estimate_context_usage", lambda *a, **k: 0.9)
    out, _ = driven(_DEFER_DONE, capsys)
    assert "[Guardian:DeferralGate]" not in out


# ─── 引號內轉述不觸發（strip_quoted_spans 套用）─────────────────────────

def test_quoted_deferral_phrase_not_flagged():
    """轉述 hook 判定或詞庫字面（引號內）不算退縮；同語寫在敘述句照標。"""
    quoted = "詞庫要補「下個 session」「另案」這幾個字串，已補完並驗證。"
    assert detect_deferral(quoted, []) is None
    plain = "完工。這個 registry 清理留給下個 session 處理比較好。"
    assert detect_deferral(plain, []) is not None
