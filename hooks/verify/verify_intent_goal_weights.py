"""verify_intent_goal_weights.py：A0.2 十個 intent 鍵。

正例：十類各兩句命中；十鍵與 hub_config.INTENT_KEYS 對拍；UPS 把算出的意圖存進 state["turn_intent"]。
反例：空字串 → general；同時含 debug 與 feature 詞且平手 → debug（最前鍵）；不在十鍵的意圖當 general。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_intent_goal_weights.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_overview as wo  # noqa: E402
from hub_config import INTENT_KEYS  # noqa: E402
from wg_atoms import INTENT_PATTERNS, classify_intent  # noqa: E402

SENTENCES = {
    "debug": ["這個按鈕按下去沒反應，幫我查為什麼", "打怪不掉血，怪物血條不會動"],
    "feature": ["新增一個匯出 CSV 的按鈕", "幫我加功能：支援多語系切換"],
    "refactor": ["重構這支檔，把三層 if 抽出來簡化", "整理一下 Export 模組，去重後改名"],
    "perf": ["列表捲動很慢，幫我優化效能", "載入耗時 3 秒，看能不能加速"],
    "new_project": ["從零立案一個新專案的目錄骨架", "開新專案：用 scaffold 起一個 CLI 工具"],
    "build": ["幫我建置並部署到測試機", "安裝環境、設定 config 後啟動服務"],
    "design": ["這個模組的架構設計要怎麼分層", "給我一個 design 方案比較"],
    "recall": ["之前我們為什麼選這個做法", "上次的決策記得是什麼"],
    "handoff": ["幫我寫交接給下 session", "給下次的 resume prompt"],
    "general": ["今天天氣如何", "好的"],
}


@pytest.mark.parametrize("intent,sentence", [(k, s) for k, v in SENTENCES.items() for s in v])
def test_each_intent_two_sentences(intent, sentence):
    assert classify_intent(sentence) == intent


def test_ten_keys_frozen_and_aligned():
    assert tuple(INTENT_PATTERNS) == INTENT_KEYS[:-1] and INTENT_KEYS[-1] == "general"
    assert next(iter(INTENT_PATTERNS)) == "debug"                              # debug 最前：平手取先鍵
    assert wo._intent_of({"turn_intent": "perf"}) == "perf" and wo._intent_of({"turn_intent": "bogus"}) == "general"


def test_counterexamples_empty_and_tie():
    assert classify_intent("") == "general"
    assert classify_intent("新增欄位後報錯") == "debug"                         # debug 與 feature 各一分 → debug
    assert classify_intent("重構後 crash") == "debug"


def test_ups_wiring_intent_is_computed_and_stored(monkeypatch):
    """A0.1：user_prompt_submit 用使用者本人打的字算 classify_intent，存進 state["turn_intent"]。"""
    import wg_friction
    from handlers import user_prompt_submit as ups
    state = {"turn_seq": 0}
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
    monkeypatch.setattr(ups, "output_json", lambda d: None)
    monkeypatch.setattr(ups, "output_nothing", lambda: None)
    monkeypatch.setattr(wg_friction, "record_correction", lambda *a: None)
    ups.handle_user_prompt_submit({"session_id": "s", "prompt": "列表捲動很慢，幫我優化效能", "transcript_path": ""}, {"sync_keywords": []})
    assert state["turn_intent"] == "perf"


