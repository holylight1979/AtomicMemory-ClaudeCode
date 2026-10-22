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


# ─── G6 階段 4（P7）：使用者延後要 AI 引用原句對到事項；AI 自己的不做行要附理由（NOT_DOING_DECLARED／USER_WAIVER_NEEDS_CITATION）──

def test_p7_user_defer_line_no_citation_check():
    text = "完工。realm atom 瘦身留到下個 session 做。"
    assert detect_deferral(text, ["這顆 atom 下個 session 再做就好"]) is not None   # 沒寫那一行 → 照標
    cited = text + "\n不做｜realm atom 瘦身：使用者說「下個 session 再做就好」"
    audit = []
    assert detect_deferral(cited, ["這顆 atom 下個 session 再做就好"], audit=audit) is None
    assert audit and audit[0]["rule"] == "NOT_DOING_DECLARED" and "realm atom 瘦身" in audit[0]["why"]
    # 引用的句子不再比對使用者原話（USER_WAIVER_NEEDS_CITATION 已拿掉）：寫了那一行就不標，留帳抽查
    assert detect_deferral(cited, ["為什麼你會判斷還需要新開 session？"]) is None


def test_p6_claim_line_is_not_a_deferral_sentence():
    """宣稱行「宣稱｜修好：非本回合宣稱，因為…」是對閘的回答，裡面的「非本回合」不是退縮語（實跑探針：回了宣稱行反被擋）。"""
    text = "閘修好了，完成。\n宣稱｜修好：非本回合宣稱，因為那句講的是上一回合驗過的狀態，本回合只改了文件"
    assert detect_deferral(text, []) is None
    from wg_evasion import detect_evasion
    assert detect_evasion(text, []) is None


def test_p7_descriptive_sentence_needs_disclaim_line():
    """b 軌 10-20 實遇：「下個 session 開場列出的內容…三段都正常」在描述已驗過的事、沒推任何事，卻被「下個 session」擋。
    詞表只是提示：AI 寫「不是退避｜<命中的詞>：因為 <理由>」→ 不擋、留帳；沒寫照擋（真退縮沒理由照擋）。"""
    text = "完工。在假專案上真跑了一遍：交付時送出的提醒、記進帳本的那一筆、下個 session 開場列出的內容，三段都正常。"
    assert detect_deferral(text, []) is not None, "前置：這句詞表會命中"
    audit = []
    assert detect_deferral(text + "\n不是退避｜下個 session：因為那句在描述新功能開場會列出什麼，是已跑過的驗證結果", [],
                           audit=audit) is None
    assert audit and audit[0]["rule"] == "NOT_DOING_DECLARED" and "不是退避" in audit[0]["why"]
    assert detect_deferral(text + "\n不是退避｜下個 session：<理由>", []) is not None, "只有佔位不算"


def test_p7_not_doing_with_reason_passes_gate_and_audits():
    text = "完工。\n不做｜realm atom 瘦身：留到下個 session，因為要重算全庫索引（約 20 分鐘）、會飄移主任務。"
    audit = []
    assert deferral_gate_reason(text, [], turn_seq=5, gated_turn=None, committed_this_turn=False, context_ratio=0.3,
                                config=_CFG, audit=audit) is None
    assert audit and audit[0]["rule"] == "NOT_DOING_DECLARED"
    # 理由只有佔位 → 照擋，擋訊息問收尾那一問（快又有效的做掉、其餘寫追蹤行）
    bad = "完工。\n不做｜realm atom 瘦身：留到下個 session，<理由>"
    reason = deferral_gate_reason(bad, [], turn_seq=5, gated_turn=None, committed_this_turn=False, context_ratio=0.3, config=_CFG)
    assert reason and "追蹤｜" in reason and "改得快又有效" in reason


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
    assert "剩下沒做的，哪些改得快又有效？" in r and "追蹤｜" in r
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
            "turn_intent": "feature",                     # 寫碼回合才查退縮語（CODING_TURN_ONLY）
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


def test_p7_stop_passes_with_not_doing_line_and_logs(driven, capsys, monkeypatch):
    """整合：收尾有「不做｜…：<理由>」→ DeferralGate 不擋，guard-deferral_declared.jsonl 留一筆（規則、原行）。"""
    logs = []
    monkeypatch.setattr(st, "append_guard_log", lambda g, p: logs.append((g, p)))
    text = "完工，工作樹乾淨。\n不做｜realm atom 瘦身：留到下個 session，因為要重算全庫索引、會飄移主任務。"
    out, state = driven(text, capsys)
    assert "[Guardian:DeferralGate]" not in out and "deferral_gate_turn" not in state
    hit = [p for g, p in logs if g == "deferral_declared"]
    assert hit and hit[0]["rule"] == "NOT_DOING_DECLARED" and hit[0]["line"].startswith("不做｜realm atom 瘦身")


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


# ─── markdown 表格列與 ``` 程式區塊不觸發（列舉詞表／貼程式碼不是退縮句）────────

def test_markdown_table_row_not_flagged():
    text = "完工。詞表如下：\n| 詞 | 說明 |\n|---|---|\n| 之後再 | 這個 realm atom 瘦身留給下個 session 處理 |\n"
    assert detect_deferral(text, []) is None


def test_code_fence_not_flagged():
    text = "完工。範例：\n```python\n# realm atom 瘦身留給下個 session 處理\nx = 1\n```\n"
    assert detect_deferral(text, []) is None


def test_plain_sentence_after_table_still_flagged():
    text = "| 詞 |\n|---|\n| 之後再 |\n完工。realm atom 瘦身留給下個 session 處理。"
    det = detect_deferral(text, [])
    assert det and "realm atom 瘦身" in det["sentence"]
