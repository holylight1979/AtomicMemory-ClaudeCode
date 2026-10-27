"""verify_notice_once.py — v6 守門開著時，跟手上事情無關的提示一個 session 只送一次；v6 關照舊每次送。

七項（各一個開關，程式預設；提示文字原處不動、判不判命中照舊）：
  1. Codex 接續單自檢（codex_companion._detect_checkpoint）：v6 開看 codex_companion.soft_gate.handoff_review_v6（沒寫＝關），
     v6 關照 soft_gate.handoff_review（沒寫＝開）。
  2. [Parallel:Suggest]（wg_parallel.detect_parallel_opportunity）：parallel_agents.v6_once，送過一次就不再送；v6 關照 cooldown_turns 冷卻。
  3. [Guardian:AIDocs] Relevant project docs（handlers/ups_context.build_context）：aidocs.v6_once，同一份文件只指一次，新命中的照指。
  4. [JIT:InternalPipeline]（同上）：jit_internal_pipeline.v6_once，送過一次就不再送。
  5. [Guardian:CoordWarn] 同檔預警（wg_coordination.check_cross_session_conflict）：coordination.v6_once，同一個檔警過就不再警
     （v6 關照 warn_suppress_min 分鐘後重警）。
  6. [Guardian:Oscillation]、7.[Guardian:覆轍]（wg_evasion._load_oscillation_warnings／_detect_rut_patterns，SessionStart 每次開場都叫，
     含 resume、compact）：self_iteration.oscillation_v6_once／rut_v6_once，清單裡列過的項不再列、只列新出現的，全列過就不送。
  另：PostToolUse 寫暫時性檔名進 _AIDocs 的 [Guardian:AIDocs] 提醒（handlers/post_tool_use.handle_post_tool_use）：
     aidocs.advisory_v6_once，同一個檔只提醒一次。
每項三案：v6 開第二次不送（main 5ccf44d2 照送，回放紅）、開關寫 false 退回照舊、v6 關兩次都送且字一樣。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_notice_once.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))
sys.path.insert(0, str(HOOKS_DIR.parent / "tools" / "codex-companion"))

import codex_companion as cc  # noqa: E402
import wg_coordination as wc  # noqa: E402
import wg_evasion  # noqa: E402
import wg_parallel  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
from handlers import ups_context  # noqa: E402

PARALLEL_PROMPT = "幫我盤點 hooks/a.py、hooks/b.py 兩個檔的錯誤處理，順便整理測試"


def _v6(monkeypatch, on: bool) -> None:
    monkeypatch.setenv("WG_V6", "1" if on else "0")


# ─── 1. Codex 接續單自檢 ──────────────────────────────────────────────────────

HANDOFF = "C:/p/.claude/memory/_staging/next-phase-2.md"


def test_handoff_review_off_under_v6(monkeypatch):
    _v6(monkeypatch, True)
    assert cc._detect_checkpoint("Write", HANDOFF, {"soft_gate": {"handoff_review": True}}) is None


def test_handoff_review_v6_switch_turns_it_back_on(monkeypatch):
    _v6(monkeypatch, True)
    assert cc._detect_checkpoint("Write", HANDOFF, {"soft_gate": {"handoff_review_v6": True}}) == "handoff_review"


def test_handoff_review_unchanged_when_v6_off(monkeypatch):
    _v6(monkeypatch, False)
    assert cc._detect_checkpoint("Write", HANDOFF, {"soft_gate": {"handoff_review": True}}) == "handoff_review"
    assert cc._detect_checkpoint("Write", HANDOFF, {}) == "handoff_review"
    assert cc._detect_checkpoint("Write", HANDOFF, {"soft_gate": {"handoff_review": False}}) is None


def test_plan_review_untouched_by_v6(monkeypatch):
    _v6(monkeypatch, True)
    assert cc._detect_checkpoint("ExitPlanMode", "", {}) == "plan_review"


# ─── 2. Parallel:Suggest ──────────────────────────────────────────────────────


def _parallel_twice(cfg: dict) -> tuple:
    state = {"topic_tracker": {"prompt_count": 1}}
    first = wg_parallel.detect_parallel_opportunity(PARALLEL_PROMPT, state, cfg)
    state["topic_tracker"]["prompt_count"] = 9          # 早過了冷卻
    return first, wg_parallel.detect_parallel_opportunity(PARALLEL_PROMPT, state, cfg)


def test_parallel_suggest_once_per_session_under_v6(monkeypatch):
    _v6(monkeypatch, True)
    first, second = _parallel_twice({})
    assert first and first.startswith("[Parallel:Suggest]")
    assert second is None


def test_parallel_suggest_v6_once_false_keeps_cooldown(monkeypatch):
    _v6(monkeypatch, True)
    first, second = _parallel_twice({"parallel_agents": {"v6_once": False}})
    assert first and second == first


def test_parallel_suggest_unchanged_when_v6_off(monkeypatch):
    _v6(monkeypatch, False)
    first, second = _parallel_twice({})
    assert first and second == first


# ─── 3／4. AIDocs 指引、JIT 內部管線（UserPromptSubmit）─────────────────────────


@pytest.fixture
def ups_world(tmp_path, monkeypatch):
    ref = tmp_path / "memory" / "_reference" / "internal-pipeline.md"
    ref.parent.mkdir(parents=True)
    ref.write_text("# 內部管線\nUserPromptSubmit → 檢索 → 注入。\n", encoding="utf-8")
    monkeypatch.setattr(ups_context, "MEMORY_DIR", tmp_path / "memory")
    return {
        "session_context_injected": True,
        "session": {"cwd": "D:/x"},
        "topic_tracker": {"prompt_count": 1},
        "aidocs": {"project_root": "C:/p", "entries": [("Routing.md", "路由表怎麼排"), ("Cache.md", "快取層")],
                   "keywords": {"Routing.md": ["routing"], "Cache.md": ["cache"]}},
    }


def _ups(state: dict, prompt: str, config: dict | None = None) -> str:
    lines: list = []
    ups_context.build_context("sid", state, config or {}, prompt, prompt, prompt.lower(), 3000, lines)
    return "\n".join(lines)


def test_aidocs_pointer_once_per_doc_under_v6(ups_world, monkeypatch):
    _v6(monkeypatch, True)
    assert "`_AIDocs/Routing.md`" in _ups(ups_world, "routing 表少一列")
    assert "[Guardian:AIDocs]" not in _ups(ups_world, "routing 表再加一列")
    both = _ups(ups_world, "routing 跟 cache 一起看")     # 新命中的文件照指，指過的不再列
    assert "`_AIDocs/Cache.md`" in both and "Routing.md" not in both


def test_aidocs_pointer_v6_once_false_repeats(ups_world, monkeypatch):
    _v6(monkeypatch, True)
    cfg = {"aidocs": {"v6_once": False}}
    assert _ups(ups_world, "routing 表少一列", cfg) == _ups(ups_world, "routing 表少一列", cfg)
    assert "[Guardian:AIDocs]" in _ups(ups_world, "routing 表少一列", cfg)


def test_aidocs_pointer_unchanged_when_v6_off(ups_world, monkeypatch):
    _v6(monkeypatch, False)
    first = _ups(ups_world, "routing 表少一列")
    assert "`_AIDocs/Routing.md`" in first and _ups(ups_world, "routing 表少一列") == first
    assert "aidocs_pointed" not in ups_world


JIT_PROMPT = "workflow-guardian 的記憶系統注入順序要調"


def test_jit_pipeline_once_per_session_under_v6(ups_world, monkeypatch):
    _v6(monkeypatch, True)
    assert "[JIT:InternalPipeline]" in _ups(ups_world, JIT_PROMPT)
    assert "[JIT:InternalPipeline]" not in _ups(ups_world, JIT_PROMPT)


def test_jit_pipeline_v6_once_false_repeats(ups_world, monkeypatch):
    _v6(monkeypatch, True)
    cfg = {"jit_internal_pipeline": {"v6_once": False}}
    assert "[JIT:InternalPipeline]" in _ups(ups_world, JIT_PROMPT, cfg)
    assert "[JIT:InternalPipeline]" in _ups(ups_world, JIT_PROMPT, cfg)


def test_jit_pipeline_unchanged_when_v6_off(ups_world, monkeypatch):
    _v6(monkeypatch, False)
    first = _ups(ups_world, JIT_PROMPT)
    assert "[JIT:InternalPipeline]" in first and _ups(ups_world, JIT_PROMPT) == first
    assert "jit_pipeline_sent" not in ups_world


# ─── 5. CoordWarn 同檔預警 ────────────────────────────────────────────────────

SELF, PEER = "self-session-0000", "peer-session-1111"
SHARED = "C:/w/app/main.py"


@pytest.fixture
def coord_world(tmp_path, monkeypatch):
    monkeypatch.setattr(wc, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(wc, "COORD_LOG_DIR", tmp_path / "coordlog")
    at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    (tmp_path / f"state-{PEER}.json").write_text(json.dumps({
        "phase": "working", "session": {"id": PEER, "cwd": "C:/w"},
        "modified_files": [{"path": SHARED, "tool": "Edit", "at": at, "count": 1, "session_id": PEER}],
    }), encoding="utf-8")
    return tmp_path


def _warn_then_age(cfg: dict, minutes: float):
    """警一次（記 warn-cache）、把那筆往前推 minutes 分鐘，再查一次。"""
    hit = wc.check_cross_session_conflict(SELF, SHARED, cfg)
    assert hit and hit["peer_sid"] == PEER
    wc.record_warn_cache(SELF, SHARED)
    p = wc._warn_cache_path(SELF)
    data = json.loads(p.read_text(encoding="utf-8"))
    data = {k: v - minutes * 60 for k, v in data.items()}
    p.write_text(json.dumps(data), encoding="utf-8")
    return wc.check_cross_session_conflict(SELF, SHARED, cfg)


CO = {"coordination": {"enabled": True, "warn_suppress_min": 10}}


def test_coord_warn_once_per_file_under_v6(coord_world, monkeypatch):
    _v6(monkeypatch, True)
    assert _warn_then_age(CO, 11) is None


def test_coord_warn_v6_once_false_rewarns_after_suppress(coord_world, monkeypatch):
    _v6(monkeypatch, True)
    cfg = {"coordination": {**CO["coordination"], "v6_once": False}}
    assert _warn_then_age(cfg, 11)


def test_coord_warn_unchanged_when_v6_off(coord_world, monkeypatch):
    _v6(monkeypatch, False)
    assert _warn_then_age(CO, 11)                        # 過了 10 分鐘照重警
    wc.record_warn_cache(SELF, SHARED)
    assert wc.check_cross_session_conflict(SELF, SHARED, CO) is None   # 10 分鐘內照抑制


# ─── 6／7. Oscillation、覆轍（SessionStart）──────────────────────────────────


@pytest.fixture
def episodic_world(tmp_path, monkeypatch):
    mem = tmp_path / "proj" / ".claude" / "memory"
    ep = mem / "episodic"
    ep.mkdir(parents=True)
    for i in range(2):
        f = ep / f"episodic-s{i}.md"
        f.write_text(f"# Session s{i}\n\n- Created: 2026-10-2{i}\n\n## 知識\n\n"
                     "- [臨] 覆轍信號: same_file_3x:router.py\n- 修改 atoms: routing-rules\n", encoding="utf-8")
        t = time.time() - 100 * i
        os.utime(f, (t, t))
    monkeypatch.setattr(wg_evasion, "get_project_memory_dir", lambda cwd: mem)
    monkeypatch.setattr(wg_evasion, "WORKFLOW_DIR", tmp_path / "workflow")
    (tmp_path / "workflow").mkdir()
    state = {"session": {"cwd": "C:/proj"}}
    wg_evasion._save_oscillation_state(wg_evasion._detect_oscillation(state, {}), state)
    return state


def test_oscillation_notice_once_per_session_under_v6(episodic_world, monkeypatch):
    _v6(monkeypatch, True)
    first = wg_evasion._load_oscillation_warnings(episodic_world)
    assert first and first.startswith("[Guardian:Oscillation]") and "routing-rules" in first
    assert wg_evasion._load_oscillation_warnings(episodic_world) is None


def test_oscillation_v6_once_false_repeats(episodic_world, monkeypatch):
    _v6(monkeypatch, True)
    cfg = {"self_iteration": {"oscillation_v6_once": False}}
    first = wg_evasion._load_oscillation_warnings(episodic_world, cfg)
    assert first and wg_evasion._load_oscillation_warnings(episodic_world, cfg) == first


def test_oscillation_unchanged_when_v6_off(episodic_world, monkeypatch):
    _v6(monkeypatch, False)
    first = wg_evasion._load_oscillation_warnings(episodic_world)
    assert first and wg_evasion._load_oscillation_warnings(episodic_world) == first
    assert "oscillation_notice_sent" not in episodic_world


def test_rut_notice_once_per_session_under_v6(episodic_world, monkeypatch):
    _v6(monkeypatch, True)
    first = wg_evasion._detect_rut_patterns(episodic_world, {})
    assert first and first.startswith("[Guardian:覆轍]") and "same_file_3x:router.py" in first
    assert wg_evasion._detect_rut_patterns(episodic_world, {}) is None


def test_rut_notice_lists_only_new_signals_under_v6(episodic_world, monkeypatch, tmp_path):
    """同一個 session 中段又開場（resume／compact）時出現新信號＝新資訊，只列新的；列過的不再列。"""
    _v6(monkeypatch, True)
    assert "same_file_3x:router.py" in wg_evasion._detect_rut_patterns(episodic_world, {})
    ep = tmp_path / "proj" / ".claude" / "memory" / "episodic"
    for i in range(2):
        f = ep / f"episodic-n{i}.md"
        f.write_text(f"# Session n{i}\n\n## 知識\n\n- [臨] 覆轍信號: same_file_3x:cache.py, same_file_3x:router.py\n",
                     encoding="utf-8")
        t = time.time() + 10 + i
        os.utime(f, (t, t))
    again = wg_evasion._detect_rut_patterns(episodic_world, {})
    assert again and "same_file_3x:cache.py" in again and "router.py" not in again
    assert wg_evasion._detect_rut_patterns(episodic_world, {}) is None


def test_oscillation_lists_only_new_atoms_under_v6(episodic_world, monkeypatch):
    _v6(monkeypatch, True)
    assert "routing-rules" in wg_evasion._load_oscillation_warnings(episodic_world)
    wg_evasion._save_oscillation_state([{"atom": "routing-rules", "count": 2, "sessions": ["a", "b"]},
                                        {"atom": "cache-rules", "count": 2, "sessions": ["a", "b"]}], episodic_world)
    again = wg_evasion._load_oscillation_warnings(episodic_world)
    assert again and "cache-rules" in again and "routing-rules" not in again


def test_rut_v6_once_false_repeats(episodic_world, monkeypatch):
    _v6(monkeypatch, True)
    cfg = {"self_iteration": {"rut_v6_once": False}}
    first = wg_evasion._detect_rut_patterns(episodic_world, cfg)
    assert first and wg_evasion._detect_rut_patterns(episodic_world, cfg) == first


def test_rut_unchanged_when_v6_off(episodic_world, monkeypatch):
    _v6(monkeypatch, False)
    first = wg_evasion._detect_rut_patterns(episodic_world, {})
    assert first and wg_evasion._detect_rut_patterns(episodic_world, {}) == first
    assert "rut_notice_sent" not in episodic_world


# ─── 另：PostToolUse 寫暫時性檔名進 _AIDocs 的提醒 ─────────────────────────────

PLAN_DOC = "C:/p/_AIDocs/plan-routing.md"


def _ptu_write(monkeypatch, state: dict, config: dict | None = None) -> str:
    """走真 PostToolUse 入口寫一次 PLAN_DOC，回這次送給模型的提示全文。"""
    out: list = []
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_emit_post_tool_output", lambda adv, sys_msgs: out.extend(adv))
    inp = {"session_id": "sid-aidocs", "tool_name": "Write", "cwd": "C:/p",
           "tool_input": {"file_path": PLAN_DOC, "content": "# 草稿\n"}, "tool_response": {}}
    try:
        pt.handle_post_tool_use(inp, config or {"docdrift": {"enabled": False}})
    except SystemExit:
        pass
    return "\n".join(out)


def test_aidocs_advisory_once_per_file_under_v6(monkeypatch):
    _v6(monkeypatch, True)
    state = {"turn_seq": 3}
    assert "[Guardian:AIDocs]" in _ptu_write(monkeypatch, state)
    assert "[Guardian:AIDocs]" not in _ptu_write(monkeypatch, state)


def test_aidocs_advisory_v6_once_false_repeats(monkeypatch):
    _v6(monkeypatch, True)
    state = {"turn_seq": 3}
    cfg = {"docdrift": {"enabled": False}, "aidocs": {"advisory_v6_once": False}}
    assert "[Guardian:AIDocs]" in _ptu_write(monkeypatch, state, cfg)
    assert "[Guardian:AIDocs]" in _ptu_write(monkeypatch, state, cfg)


def test_aidocs_advisory_unchanged_when_v6_off(monkeypatch):
    _v6(monkeypatch, False)
    state = {"turn_seq": 3}
    first = _ptu_write(monkeypatch, state)
    assert "[Guardian:AIDocs]" in first and "[Guardian:AIDocs]" in _ptu_write(monkeypatch, state)
    assert "aidocs_advisory_sent" not in state
