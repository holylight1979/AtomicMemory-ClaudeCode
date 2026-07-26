"""verify_recall_miss.py — 失念偵測（wg_recall_miss）契約。

collect_problem_texts：
- failing_tests（cmd+summary）/ evasion_events+evasion_flag / failure_kw
  （knowledge_queue pitfall/failure 項 + edit_counts≥3 覆轍檔名 + retry_escalation）
- 無任何失敗證據 → []

detect_recall_misses：
- 未注入 atom 的 trigger 命中問題文本 ≥2 個不同（非泛用）詞 → 落 jsonl 候選
- 1 詞 / 泛用詞（單字元、純數字、黑名單如「錯誤/失敗/bug」）不計門檻
- 已注入 atom（injected_atoms / turn_injected / subagent / rescue_watch）排除
- jsonl 欄位 {at, session_id, atom, matched_triggers, evidence≤200, source}
- 每 (session, atom) 一筆；無候選不建檔（靜默）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_recall_miss  # noqa: E402
from wg_recall_miss import (  # noqa: E402
    _is_generic_trigger, collect_injected_atoms, collect_problem_texts,
    detect_recall_misses,
)

# (name, rel_path, triggers) — triggers 依索引慣例小寫
ATOM_SVN = ("workflow-svn", "memory/workflow-svn.md",
            ["svn", "checkin", "工作副本", "tortoise"])
ATOM_OLLAMA = ("toolchain-ollama", "memory/toolchain-ollama.md",
               ["ollama", "qwen3", "embedding", "rdchat"])
ATOM_GENERIC = ("noisy-atom", "memory/noisy-atom.md",
                ["錯誤", "失敗", "bug", "x", "42", "vector"])


def _state_failing(cmd="svn checkin hooks/foo.py", summary="E155036 工作副本 upgrade required"):
    return {"failing_tests": [{"tool": "Bash", "cmd": cmd, "summary": summary,
                               "at": "t", "turn_seq": 1}]}


# ── collect_problem_texts ───────────────────────────────────────────────────

def test_texts_from_failing_tests():
    texts = collect_problem_texts(_state_failing())
    assert texts == [("failing_tests", "svn checkin hooks/foo.py E155036 工作副本 upgrade required")]


def test_texts_from_evasion_and_flag():
    state = {
        "evasion_events": [{"phrase": "先跳過", "turn_seq": 2, "at": "t"}],
        "evasion_flag": {"phrase": "之後再修", "context_excerpt": "測試紅著"},
    }
    texts = collect_problem_texts(state)
    srcs = [s for s, _ in texts]
    assert srcs == ["evasion", "evasion"]
    assert texts[1][1] == "之後再修 測試紅著"


def test_texts_failure_kw_from_queue_and_rut_signals():
    state = {
        "knowledge_queue": [
            {"content": "ollama embedding 逾時要調 timeout", "type": "pitfall"},
            {"content": "無關的 factual 知識", "type": "factual"},
            {"content": "failure 萃取項", "source": "failure", "type": "factual"},
        ],
        "edit_counts": {"C:/x/hooks/wg_core.py": 3, "C:/x/other.py": 1},
        "wisdom_retry_count": 2,
    }
    texts = collect_problem_texts(state)
    kw_texts = [t for s, t in texts if s == "failure_kw"]
    assert "ollama embedding 逾時要調 timeout" in kw_texts
    assert "failure 萃取項" in kw_texts
    assert any("wg_core.py" in t and "retry_escalation" in t for t in kw_texts)
    assert not any("factual 知識" in t for _, t in texts)


def test_texts_empty_when_no_evidence():
    assert collect_problem_texts({}) == []
    assert collect_problem_texts({"failing_tests": [], "knowledge_queue": [
        {"content": "ok", "type": "factual"}]}) == []


# ── 泛詞 / 注入清單 ─────────────────────────────────────────────────────────

def test_generic_trigger_rules():
    for kw in ("錯誤", "失敗", "bug", "x", "42", "python", "session"):
        assert _is_generic_trigger(kw), kw
    for kw in ("svn", "工作副本", "測試上傳", "rdchat"):
        assert not _is_generic_trigger(kw), kw


def test_injected_union_sources():
    state = {
        "injected_atoms": ["A-One"],
        "turn_injected": [{"name": "b-two", "path": "x"}],
        "pre_compact_injected_atoms": ["C-Three"],
        "subagent_injections": [{"atoms": ["d-four"]}],
        "rescue_watch": {"tok": "e-five\ttok"},
    }
    got = collect_injected_atoms(state)
    assert got == {"a-one", "b-two", "c-three", "d-four", "e-five"}


# ── detect_recall_misses ────────────────────────────────────────────────────

def test_two_distinct_triggers_hit_writes_jsonl(tmp_path):
    log = tmp_path / "recall-miss.jsonl"
    recs = detect_recall_misses(
        "sid-1", _state_failing(), atoms=[ATOM_SVN, ATOM_OLLAMA], log_path=log)
    assert [r["atom"] for r in recs] == ["workflow-svn"]
    line = json.loads(log.read_text(encoding="utf-8").strip())
    assert line["session_id"] == "sid-1"
    assert line["atom"] == "workflow-svn"
    assert sorted(line["matched_triggers"]) == ["checkin", "svn", "工作副本"]
    assert line["source"] == "failing_tests"
    assert "E155036" in line["evidence"] and len(line["evidence"]) <= 200
    assert line["at"]


def test_single_trigger_hit_below_threshold(tmp_path):
    log = tmp_path / "recall-miss.jsonl"
    state = _state_failing(cmd="run something", summary="svn is broken")  # 只中 svn
    recs = detect_recall_misses("sid", state, atoms=[ATOM_SVN], log_path=log)
    assert recs == [] and not log.exists()


def test_generic_triggers_not_counted(tmp_path):
    log = tmp_path / "recall-miss.jsonl"
    # 命中 錯誤+失敗+bug+x+42（全泛用）+ vector（特異 1 詞）→ 不足 2
    state = _state_failing(cmd="vector 42 x", summary="錯誤 失敗 bug")
    recs = detect_recall_misses("sid", state, atoms=[ATOM_GENERIC], log_path=log)
    assert recs == [] and not log.exists()


def test_injected_atom_excluded(tmp_path):
    log = tmp_path / "recall-miss.jsonl"
    state = _state_failing()
    state["injected_atoms"] = ["workflow-svn"]
    recs = detect_recall_misses("sid", state, atoms=[ATOM_SVN], log_path=log)
    assert recs == [] and not log.exists()


def test_one_record_per_atom_and_no_candidates_silent(tmp_path):
    log = tmp_path / "recall-miss.jsonl"
    state = _state_failing()
    # 同名 atom 兩層索引重複 → 只落一筆
    recs = detect_recall_misses("sid", state, atoms=[ATOM_SVN, ATOM_SVN], log_path=log)
    assert len(recs) == 1
    assert len(log.read_text(encoding="utf-8").strip().splitlines()) == 1
    # 無任何失敗證據 → 不掃不寫
    log2 = tmp_path / "empty.jsonl"
    assert detect_recall_misses("sid", {}, atoms=[ATOM_SVN], log_path=log2) == []
    assert not log2.exists()


def test_evidence_capped_200(tmp_path):
    log = tmp_path / "recall-miss.jsonl"
    state = _state_failing(cmd="svn checkin", summary="工作副本 " + "很長" * 300)
    recs = detect_recall_misses("sid", state, atoms=[ATOM_SVN], log_path=log)
    assert len(recs) == 1 and len(recs[0]["evidence"]) <= 200
