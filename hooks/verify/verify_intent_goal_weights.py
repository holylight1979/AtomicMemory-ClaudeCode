"""verify_intent_goal_weights.py：A0.2 十個 intent 鍵與 A0.3 goal_weights 預設表／驗證。

正例：十類各兩句命中；十鍵與 wg_overview.INTENT_KEYS、_DEFAULT.goal_weights 三方對拍；每個 intent 的預設 slices 都在 SLICE_NAMES 內。
反例：空字串 → general；同時含 debug 與 feature 詞且平手 → debug（最前鍵）；未知 slice／未知 intent／card:false 進 _errors。
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

import overview_hub as oh  # noqa: E402
import wg_overview as wo  # noqa: E402
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


def test_ten_keys_frozen_and_three_way_aligned():
    assert tuple(INTENT_PATTERNS) == wo.INTENT_KEYS[:-1] and wo.INTENT_KEYS[-1] == "general"
    assert set(wo._DEFAULT["goal_weights"]) == set(wo.INTENT_KEYS)
    assert next(iter(INTENT_PATTERNS)) == "debug"                              # debug 最前：平手取先鍵
    for intent, spec in wo._DEFAULT["goal_weights"].items():
        assert {"slices", "lens", "ask_first"} <= set(spec) <= {"slices", "lens", "ask_first", "extra"}, intent   # extra 選填（G7）
        assert set(spec["slices"]) <= set(oh.SLICE_NAMES), intent
    assert wo._DEFAULT["goal_weights"]["debug"]["slices"][0] == "defects"
    assert wo._DEFAULT["goal_weights"]["new_project"]["slices"][0] == "authority"
    assert wo._DEFAULT["goal_weights"]["refactor"]["lens"] == "數彎視角"
    assert all(wo._DEFAULT["goal_weights"][k]["slices"] == [] for k in ("recall", "handoff", "general"))


def test_counterexamples_empty_and_tie():
    assert classify_intent("") == "general"
    assert classify_intent("新增欄位後報錯") == "debug"                         # debug 與 feature 各一分 → debug
    assert classify_intent("重構後 crash") == "debug"


def test_unknown_slice_or_intent_or_card_false_are_errors():
    errs = wo._validate_cfg(dict(wo._DEFAULT, goal_weights={"debug": {"slices": ["defects", "bogus"]}}), None)
    assert len(errs) == 1 and "未知的片「bogus」" in errs[0]
    errs = wo._validate_cfg(dict(wo._DEFAULT, goal_weights={"hotfix": {"slices": []}}), None)
    assert len(errs) == 1 and "hotfix" in errs[0] and "十鍵" in errs[0]
    errs = wo._validate_cfg(dict(wo._DEFAULT, goal_weights={"debug": {"slices": [], "foo": 1}}), None)
    assert len(errs) == 1 and "未知鍵「foo」" in errs[0]
    errs = wo._validate_cfg(dict(wo._DEFAULT, min_overview_evidence={"card": False, "part_files": 1, "depends_files": 0}), None)
    assert len(errs) == 1 and "不可關" in errs[0]
    errs = wo._validate_cfg(dict(wo._DEFAULT, min_overview_evidence={"card": True, "part_files": -1, "depends_files": 0}), None)
    assert len(errs) == 1 and "part_files" in errs[0]
    assert wo._validate_cfg(dict(wo._DEFAULT), None) == []


def test_ups_wiring_intent_is_computed_before_hub_and_passed_in(monkeypatch):
    """A0.1：user_prompt_submit 在 OverviewHub 段前算 classify_intent 存 state["turn_intent"]，on_prompt 收到同一個 intent。"""
    import wg_friction
    from handlers import user_prompt_submit as ups
    src = (HOOKS_DIR / "handlers" / "user_prompt_submit.py").read_text(encoding="utf-8")
    assert src.index('state["turn_intent"] = turn_intent') < src.index("_hub_on_prompt(")          # 原始碼順序
    state = {"turn_seq": 0}
    seen = {}
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

    def _hub(st, sid, prompt, tp, cfg, intent=None):
        seen["intent"] = intent
        seen["state_intent"] = st.get("turn_intent")
        return None
    monkeypatch.setattr(wo, "on_prompt", _hub)
    ups.handle_user_prompt_submit({"session_id": "s", "prompt": "列表捲動很慢，幫我優化效能", "transcript_path": ""}, {"sync_keywords": []})
    assert seen == {"intent": "perf", "state_intent": "perf"} and state["turn_intent"] == "perf"


def test_project_override_deep_merges_goal_weights(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "overview-hub.json").write_text(
        '{"goal_weights": {"debug": {"slices": ["verify"]}}}', encoding="utf-8")
    c = wo._cfg({}, tmp_path)
    assert c["_errors"] == []
    assert c["goal_weights"]["debug"]["slices"] == ["verify"]                   # list 整個取覆蓋方
    assert c["goal_weights"]["debug"]["ask_first"] == "幾份存法、有無訊號"      # 巢狀其他鍵保留
    assert c["goal_weights"]["feature"]["slices"] == ["what", "authority", "verify"]
