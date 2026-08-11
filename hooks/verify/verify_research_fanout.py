"""verify_research_fanout.py — 檢索型 fan-out 偵測器（wg_research）契約。

1. classify：檢索動詞為必要條件（無則 None）；knowledge / codebase 分流
   —— 本地定位訊號 + 明示檔名 vs 知識域訊號 + 預設外求偏移
2. 反例不誤觸發：動手指令 / 已在流程中 / 短答 / slash command / 過短
3. detect_research_fanout：注入文案含兩階段要件、cooldown、config 開關
4. 與 wg_parallel 判準互斥：檢索型 prompt 在 wg_parallel 的計分恆為 0
   （這正是本模組存在的理由，回歸時最容易被誤合併掉）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from wg_research import classify, detect_research_fanout  # noqa: E402
import wg_parallel  # noqa: E402


def _state(turn: int = 5, last: int = -10):
    return {
        "topic_tracker": {"prompt_count": turn},
        "research_last_inject_turn": last,
    }


# ─── 1. classify 分流 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("prompt", [
    "幫我搜索一下 Rust async runtime 的差別",
    "我想知道 LanceDB 跟 Qdrant 選型該怎麼比",
    "幫我查最佳實踐",
    "research the tradeoff between BM25 and vector search",
])
def test_knowledge_mode(prompt):
    mode, hints = classify(prompt)
    assert mode == "knowledge", f"{prompt!r} → {mode} ({hints})"


@pytest.mark.parametrize("prompt", [
    "查詢 wg_parallel.py 裡誰呼叫 score_prompt",
    "幫我找一下 hot_cache 定義在哪個檔",
    "幫我查 這個函式 在哪裡定義的",
])
def test_codebase_mode(prompt):
    mode, hints = classify(prompt)
    assert mode == "codebase", f"{prompt!r} → {mode} ({hints})"


# ─── 2. 反例：不得誤觸發 ─────────────────────────────────────────────────────

@pytest.mark.parametrize("prompt", [
    "把 config.json 的 enabled 改成 false",   # 動手指令
    "繼續做剛剛那個重構",                      # 已在流程中
    "這個 bug 怎麼修",                        # 無檢索動詞
    "好",                                    # 短答
    "/memory health",                        # slash command
    "查",                                    # 過短（min_prompt_chars）
])
def test_no_false_fire(prompt):
    assert detect_research_fanout(prompt, _state(), {}) is None


# ─── 3. 注入內容與閘門 ───────────────────────────────────────────────────────

def test_knowledge_line_carries_two_stages():
    line = detect_research_fanout("幫我搜索 Rust 的並行方案差別", _state(), {})
    assert line is not None
    for token in ("Stage A", "Stage B", "關鍵字", "workflow-research-fanout"):
        assert token in line


def test_codebase_line_is_single_stage():
    """codebase 走單階段：不得出現兩階段字樣（文案明寫「不需 WebSearch」故不比對該詞）。"""
    line = detect_research_fanout("幫我找一下 hot_cache 定義在哪個檔", _state(), {})
    assert line is not None
    assert "Explore" in line
    assert "不需 WebSearch" in line          # 本地 symbol 精確，擴充只引噪音
    assert "Stage A" not in line
    assert "Stage B" not in line


def test_cooldown_blocks_second_hit():
    st = _state(turn=5)
    assert detect_research_fanout("幫我搜索 A 的原理", st, {}) is not None
    # 同輪 / cooldown 內第二次不再注入
    assert detect_research_fanout("我想知道 B 的原理", st, {}) is None


def test_cooldown_expires():
    st = _state(turn=5, last=0)   # 5 - 0 >= 2
    assert detect_research_fanout("幫我搜索 A 的原理", st, {}) is not None


def test_config_kill_switch():
    cfg = {"research_fanout": {"enabled": False}}
    assert detect_research_fanout("幫我搜索 A 的原理", _state(), cfg) is None


# ─── 4. 與 wg_parallel 判準互斥（本模組的存在理由）─────────────────────────

@pytest.mark.parametrize("prompt", [
    "幫我搜索一下 Rust async runtime 的差別",
    "我想知道 LanceDB 跟 Qdrant 選型該怎麼比",
    "幫我查最佳實踐",
])
def test_covers_what_parallel_scores_zero(prompt):
    """檢索型 prompt 在 wg_parallel 恆為 0 分 —— 本模組存在的真正理由。

    檢索意圖不在 wg_parallel 的任一計分維度（連接詞/批量詞/跨目標動詞/多檔）。
    若日後有人「簡化」成共用 wg_parallel 或放寬其門檻，本測試會紅。
    """
    score, _ = wg_parallel.score_prompt(prompt)
    assert score == 0, f"前提失效：wg_parallel 現在對 {prompt!r} 給 {score} 分，需重新評估分模組決策"
    assert detect_research_fanout(prompt, _state(), {}) is not None
