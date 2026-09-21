"""verify_attribution_turn_identity.py — 效用歸因的回合身分與去重契約（2026-09-21 全面檢視 Phase 1a）。

守住：
1. get_current_turn_text 不把 Agent/Task 的 prompt 欄攤進比對文字（派工時 atom 原文在裡面 → 自己命中自己）。
2. _detect_turn_outcome 的重試訊號看本 turn 增量（wisdom_retry_turn_base），不看 session 累計。
3. 同一 atom 同一 turn 只寫一筆 α/β；主回合與子代理結果衝突 → 不寫、留 conflicted 紀錄。
4. 子代理注入紀錄只結算 turn_seq 相符者；更早 turn 的殘留標 stale_turn、不套當輪 outcome。

受控 tmp atom + tmp 轉錄，不依賴磁碟既有 atom。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
import wg_evasion  # noqa: E402
from lib import atom_access as A  # noqa: E402
from handlers.stop import _attribute_usefulness, _detect_turn_outcome  # noqa: E402

ATOM_BODY = (
    "# atom-x\n"
    "- [臨] atom_write 兩個防護缺口：mode=replace 無閘 silent upsert；"
    "server.js 新增 findSeparatorVariant(memDir, slug) 守門，create 命中變體即擋。"
    "lib/atom_spec.py 規則唯一來源，改全域 MCP server 需重啟生效。\n"
)
USED_TURN = (
    "我新增了 findSeparatorVariant 到 server.js 並守住 atom_write 的 replace 路徑，"
    "編輯 tools/workflow-guardian-mcp/server.js 與 lib/atom_spec.py。"
)
UNUSED_TURN = "我重構了 React 元件 state，修了 dashboard widget 的 CSS flexbox 版面。"
# 回合身分／去重契約與判用政策無關：固定 v1 詞彙判用讓 USED_TURN 必判 used；v2 見 verify_attribution_v2.py
CONFIG = {"usefulness": {"enabled": True, "rare_token_min": 2, "lexical_overlap_min": 0.18,
                         "attribution_policy": "v1"}}


@pytest.fixture(autouse=True)
def _silence_audit(monkeypatch):
    monkeypatch.setattr(A, "_audit_log", lambda *a, **k: None)


@pytest.fixture
def atom_md(tmp_path):
    p = tmp_path / "atom-x.md"
    p.write_text(ATOM_BODY, encoding="utf-8")
    return p


@pytest.fixture
def resolve_to_tmp(monkeypatch, atom_md):
    monkeypatch.setattr(wg_atoms, "resolve_atom_path", lambda name: atom_md if name == "atom-x" else None)


def _write_transcript(tmp_path, records):
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")
    return p


def _user(text):
    return {"type": "user", "message": {"content": text}}


def _assistant(text, tool=None):
    content = [{"type": "text", "text": text}]
    if tool:
        content.append({"type": "tool_use", "name": tool[0], "input": tool[1]})
    return {"type": "assistant", "message": {"content": content}}


# ─── 1. Agent prompt 欄不進比對文字 ──────────────────────────────────────────


def test_turn_text_skips_agent_prompt_field(tmp_path):
    tr = _write_transcript(tmp_path, [
        _user("派個 agent"),
        _assistant("派工", ("Agent", {"description": "DESCTOKEN", "prompt": "[WG:SubagentMemory] ATOMSECRET 原文"})),
    ])
    txt = wg_evasion.get_current_turn_text(tr)
    assert "ATOMSECRET" not in txt
    assert "DESCTOKEN" in txt  # 其他欄位照常


def test_turn_text_keeps_prompt_field_for_non_delegation_tools(tmp_path):
    tr = _write_transcript(tmp_path, [
        _user("跑指令"),
        _assistant("跑", ("Bash", {"command": "echo hi", "prompt": "PROMPTTOKEN"})),
    ])
    assert "PROMPTTOKEN" in wg_evasion.get_current_turn_text(tr)


# ─── 2. retry 看本 turn 增量 ─────────────────────────────────────────────────


def test_outcome_retry_delta_ignores_session_history():
    # session 累計 5、本 turn 起點也是 5 → 本 turn 沒新重試 → 完成宣告算成功
    assert _detect_turn_outcome({"wisdom_retry_count": 5, "wisdom_retry_turn_base": 5}, "已完成") is True


def test_outcome_retry_delta_two_in_turn_is_fail():
    assert _detect_turn_outcome({"wisdom_retry_count": 5, "wisdom_retry_turn_base": 3}, "已完成") is False


def test_outcome_retry_without_base_keeps_cumulative():
    # 升級前 in-flight session 沒 base → 沿用累計語意，不漏 fail
    assert _detect_turn_outcome({"wisdom_retry_count": 2}, "已完成") is False


# ─── 3/4. 去重、衝突、stale 子代理紀錄 ────────────────────────────────────────


def _base_state(atom_md, **extra):
    s = {"turn_seq": 1, "turn_injected": [{"name": "atom-x", "path": str(atom_md)}]}
    s.update(extra)
    return s


def test_same_atom_two_sources_single_write(tmp_path, atom_md, resolve_to_tmp):
    tr = _write_transcript(tmp_path, [_user("修 atom_write"), _assistant(USED_TURN)])
    state = _base_state(atom_md, subagent_injections=[
        {"atoms": ["atom-x"], "status": "done", "output_summary": USED_TURN, "turn_seq": 1},
    ])
    _attribute_usefulness(state, CONFIG, "sess", tr, "已完成")
    acc = A.read_access(atom_md)
    assert acc["useful_hits"] == 2 and acc["used_fail"] == 1  # 主＋子同結果 → 只 +1


def test_conflicting_outcomes_write_nothing(tmp_path, atom_md, resolve_to_tmp):
    tr = _write_transcript(tmp_path, [_user("修 atom_write"), _assistant(USED_TURN)])
    state = _base_state(atom_md, subagent_injections=[
        {"atoms": ["atom-x"], "status": "error", "output_summary": USED_TURN, "turn_seq": 1},
    ])
    _attribute_usefulness(state, CONFIG, "sess", tr, "已完成")
    acc = A.read_access(atom_md)
    assert acc["useful_hits"] == 1 and acc["used_fail"] == 1  # 父成功子失敗 → unknown 不動
    log = state["usefulness_log"][-1]
    assert log["conflicted"] == ["atom-x"] and log["atoms"] == []


def test_stale_subagent_record_not_attributed(tmp_path, atom_md, resolve_to_tmp):
    tr = _write_transcript(tmp_path, [_user("改 CSS"), _assistant(UNUSED_TURN)])
    state = {"turn_seq": 3, "turn_injected": [], "subagent_injections": [
        {"atoms": ["atom-x"], "status": "done", "output_summary": USED_TURN, "turn_seq": 1},
    ]}
    _attribute_usefulness(state, CONFIG, "sess", tr, "已完成")
    acc = A.read_access(atom_md)
    assert acc["useful_hits"] == 1 and acc["used_fail"] == 1  # 舊 turn 紀錄不套本輪成功
    rec = state["subagent_injections"][0]
    assert rec["attributed"] is True and rec["skipped"] == "stale_turn"


def test_legacy_subagent_record_without_turn_seq_still_attributed(tmp_path, atom_md, resolve_to_tmp):
    tr = _write_transcript(tmp_path, [_user("改 CSS"), _assistant(UNUSED_TURN)])
    state = {"turn_seq": 3, "turn_injected": [], "subagent_injections": [
        {"atoms": ["atom-x"], "status": "done", "output_summary": USED_TURN},  # 升級前紀錄
    ]}
    _attribute_usefulness(state, CONFIG, "sess", tr, "已完成")
    assert A.read_access(atom_md)["useful_hits"] == 2
