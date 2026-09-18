"""verify_friction_toolwaste.py — wg_friction（工具結果體積 + 使用者糾正）驗證。

1. tool_result_size：模型「看得到」的量法——Bash 取 stdout+stderr、Read 取 file.content、
   Edit/Write 只看到 ack → 0、其餘 str/JSON 近似
2. record_tool_result：per-session 檔 append、門檻以上才回 advisory、advisory 每 session 上限
3. summarize / flush：per-tool 聚合、oversized 排序、聚合後刪暫存、GC 逾期孤兒
4. detect_correction：糾正詞命中、「對不對？」提問不算、bug 詞不算、英文整詞、enabled=false
5. record_correction：計數、明細 cap、guard log
6. Stop DPM gate：只靠糾正 ≥ min_hits 也觸發；<min_hits／關閉／已深寫 → 不觸發；指令句帶糾正摘要

對應：hooks/wg_friction.py、handlers/post_tool_use.py、handlers/user_prompt_submit.py、
      handlers/stop.py、handlers/session_end.py、workflow/config.json friction / tool_result_waste。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import wg_core  # noqa: E402
import wg_friction as wf  # noqa: E402
from handlers import stop as st  # noqa: E402

CFG = {
    "tool_result_waste": {"enabled": True, "oversized_chars": 1000, "max_advisories_per_session": 2},
    "friction": {"enabled": True, "min_hits": 2},
    "deep_postmortem": {"enabled": True},
}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """per-session 檔導到 tmp（跟其他 verify 一樣改 wg_core.WORKFLOW_DIR）；guard log 改收進 list。"""
    logs: list = []
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(wf, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    return tmp_path, logs


# ── 1. 量法 ──────────────────────────────────────────────────────────────────

def test_size_bash_counts_stdout_and_stderr_only():
    tr = {"stdout": "a" * 10, "stderr": "b" * 5, "interrupted": False, "junk": "x" * 1000}
    assert wf.tool_result_size(tr, "Bash") == 15
    # 空 dict（其他 verify 驅動 PostToolUse 時常這樣給）→ 0，record 不落檔
    assert wf.tool_result_size({}, "Bash") == 0


def test_record_empty_bash_response_writes_nothing(sandbox):
    tmp, _ = sandbox
    assert wf.record_tool_result({"turn_seq": 1}, "sid", "Bash", {"command": "x"}, {}, CFG) is None
    assert not (tmp / "tool-results").exists()


def test_size_read_counts_file_content_only():
    tr = {"type": "text", "file": {"filePath": "x.py", "content": "c" * 42, "numLines": 3}}
    assert wf.tool_result_size(tr, "Read") == 42


def test_size_edit_write_are_ack_only():
    tr = {"filePath": "x.py", "originalFile": "z" * 5000, "structuredPatch": []}
    assert wf.tool_result_size(tr, "Edit") == 0
    assert wf.tool_result_size(tr, "Write") == 0
    assert wf.tool_result_size(tr, "NotebookEdit") == 0


def test_size_str_and_generic_json():
    assert wf.tool_result_size("hello", "Grep") == 5
    assert wf.tool_result_size([{"type": "text", "text": "ab"}], "Agent") == len(
        json.dumps([{"type": "text", "text": "ab"}], ensure_ascii=False))
    assert wf.tool_result_size(None, "Bash") == 0


# ── 2. record_tool_result ────────────────────────────────────────────────────

def test_record_below_threshold_appends_without_brief_and_no_advisory(sandbox):
    tmp, logs = sandbox
    state = {"turn_seq": 3}
    adv = wf.record_tool_result(state, "s1", "Bash", {"command": "ls"}, {"stdout": "x" * 100, "stderr": ""}, CFG)
    assert adv is None
    lines = (tmp / "tool-results" / "s1.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    e = json.loads(lines[0])
    assert e["tool"] == "Bash" and e["chars"] == 100 and e["turn"] == 3 and "brief" not in e
    assert logs == [] and "tool_result_advisories" not in state


def test_record_oversized_returns_advisory_with_brief_and_logs(sandbox):
    tmp, logs = sandbox
    state = {"turn_seq": 1}
    tr = {"type": "text", "file": {"filePath": "big.md", "content": "y" * 5000}}
    adv = wf.record_tool_result(state, "s1", "Read", {"file_path": "C:/p/big.md"}, tr, CFG)
    assert adv and "Read" in adv and "C:/p/big.md" in adv and "5K" in adv
    assert state["tool_result_advisories"] == 1
    assert logs[0][0] == "tool-result-size" and logs[0][1]["chars"] == 5000
    e = json.loads((tmp / "tool-results" / "s1.jsonl").read_text(encoding="utf-8"))
    assert e["brief"] == "C:/p/big.md"


def test_record_advisory_capped_per_session_but_still_logged(sandbox):
    _, logs = sandbox
    state = {"turn_seq": 1}
    big = "z" * 3000
    assert wf.record_tool_result(state, "s1", "Grep", {"pattern": "a"}, big, CFG)
    assert wf.record_tool_result(state, "s1", "Grep", {"pattern": "b"}, big, CFG)
    assert wf.record_tool_result(state, "s1", "Grep", {"pattern": "c"}, big, CFG) is None
    assert state["tool_result_advisories"] == 2
    assert len(logs) == 3


def test_record_disabled_or_ack_only_writes_nothing(sandbox):
    tmp, _ = sandbox
    off = {"tool_result_waste": {"enabled": False}}
    assert wf.record_tool_result({}, "s1", "Bash", {}, {"stdout": "q" * 9000}, off) is None
    assert wf.record_tool_result({}, "s1", "Edit", {}, {"originalFile": "q" * 9000}, CFG) is None
    assert not (tmp / "tool-results" / "s1.jsonl").exists()


# ── 3. summarize / flush ─────────────────────────────────────────────────────

def test_summarize_and_flush_aggregate_then_remove_and_gc(sandbox):
    tmp, logs = sandbox
    state = {"turn_seq": 2, "session": {"cwd": "C:/proj"}}
    wf.record_tool_result(state, "s1", "Bash", {"command": "a"}, {"stdout": "x" * 200, "stderr": ""}, CFG)
    wf.record_tool_result(state, "s1", "Bash", {"command": "b"}, {"stdout": "x" * 300, "stderr": ""}, CFG)
    wf.record_tool_result(state, "s1", "Read", {"file_path": "f1"}, "r" * 1500, CFG)
    wf.record_tool_result(state, "s1", "Read", {"file_path": "f2"}, "r" * 2500, CFG)
    logs.clear()

    s = wf.summarize_tool_results("s1")
    assert s["calls"] == 4 and s["total_chars"] == 4500
    assert s["per_tool"]["Bash"] == {"n": 2, "chars": 500, "max": 300}
    assert s["per_tool"]["Read"]["max"] == 2500
    assert s["oversized_n"] == 2 and s["oversized_top"][0]["brief"] == "f2"

    old = tmp / "tool-results" / "orphan.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    os.utime(old, (time.time() - 30 * 86400,) * 2)

    out = wf.flush_tool_result_stats("s1", state)
    assert out["cwd"] == "C:/proj"
    assert logs[0][0] == "tool-result-stats" and logs[0][1]["session_id"] == "s1"
    assert not (tmp / "tool-results" / "s1.jsonl").exists()
    assert not old.exists()


def test_flush_without_file_is_noop(sandbox):
    _, logs = sandbox
    assert wf.flush_tool_result_stats("nope", {}) is None
    assert logs == []


# ── 4./5. 使用者糾正 ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("prompt", [
    "不對，我說的是另一個檔",
    "我說過不要動 config",
    "重來，改回來原本的寫法",
    "That's not what I asked for",
    "I already said use the local path",
])
def test_detect_correction_hits(prompt):
    assert wf.detect_correction(prompt, CFG)


@pytest.mark.parametrize("prompt", [
    "這樣寫對不對？",
    "這個判斷式不對嗎？",
    "測試又失敗了，bug 還在",
    "幫我看一下這段",
    "the unsaid assumption here is fine",
])
def test_detect_correction_misses(prompt):
    assert wf.detect_correction(prompt, CFG) == []


def test_detect_correction_disabled_and_custom_keywords():
    assert wf.detect_correction("不對", {"friction": {"enabled": False}}) == []
    custom = {"friction": {"enabled": True, "keywords": ["zzz"]}}
    assert wf.detect_correction("不對", custom) == []
    assert wf.detect_correction("zzz please", custom) == ["zzz"]


def test_record_correction_counts_caps_and_logs(sandbox):
    _, logs = sandbox
    state = {"turn_seq": 5}
    assert wf.record_correction(state, "s1", "隨便聊聊", CFG) == []
    assert "user_correction_count" not in state
    for i in range(12):
        state["turn_seq"] = i
        assert wf.record_correction(state, "s1", f"不對 第{i}次", CFG)
    assert state["user_correction_count"] == 12
    assert len(state["user_correction_hits"]) == 10
    assert state["user_correction_hits"][-1]["turn"] == 11
    assert len(logs) == 12 and logs[-1][0] == "friction" and logs[-1][1]["count"] == 12
    assert wf.friction_triggered(state, CFG)
    assert "12 次" in wf.friction_summary(state) and "不對" in wf.friction_summary(state)


# ── 6. Stop DPM gate ─────────────────────────────────────────────────────────

def _clean_state(**kw):
    s = {"wisdom_retry_count": 0, "failing_tests": [], "evasion_flag": None}
    s.update(kw)
    return s


def test_dpm_triggers_on_friction_alone_even_when_done_claimed():
    s = _clean_state(user_correction_count=2, user_correction_hits=[{"kw": ["不對"]}])
    assert st._should_deep_postmortem(s, CFG, claims_done=True) is True


def test_dpm_not_triggered_below_min_hits_or_when_disabled_or_done():
    assert st._should_deep_postmortem(_clean_state(user_correction_count=1), CFG, claims_done=True) is False
    off = dict(CFG, friction={"enabled": False, "min_hits": 2})
    assert st._should_deep_postmortem(_clean_state(user_correction_count=5), off, claims_done=True) is False
    assert st._should_deep_postmortem(
        _clean_state(user_correction_count=5, deep_postmortem_done=True), CFG, claims_done=True) is False


def test_dpm_original_path_unchanged():
    # retry≥2 + 測試紅 → 觸發；retry≥2 + 全綠且宣告完成 → 不觸發（維持原語意）
    assert st._should_deep_postmortem(_clean_state(wisdom_retry_count=2, failing_tests=["t"]), CFG, True) is True
    assert st._should_deep_postmortem(_clean_state(wisdom_retry_count=2), CFG, claims_done=True) is False


def test_dpm_instruction_names_trigger():
    s_fric = _clean_state(user_correction_count=3, user_correction_hits=[{"kw": ["我說過", "重來"]}])
    txt = st._dpm_instruction(s_fric, CFG)
    assert "使用者已糾正 3 次" in txt and "我說過" in txt and "{trigger}" not in txt
    s_retry = _clean_state(wisdom_retry_count=2, failing_tests=["t"])
    assert "fix-escalation" in st._dpm_instruction(s_retry, CFG)
    assert "[Guardian:DeepPostMortem]" in st._dpm_instruction(s_retry, CFG)
