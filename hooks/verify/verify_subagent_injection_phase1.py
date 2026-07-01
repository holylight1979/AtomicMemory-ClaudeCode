"""verify_subagent_injection_phase1.py — Phase 1 (#1) sub-agent 記憶注入守門.

守住 Phase 1 的不變式：
1. `build_injection_blob`（wg_atoms）對含 trigger 的 prompt 產出緊湊 blob，
   含可解析的 `[WG:SubagentMemory] ... atoms=a,b,c` header；無關 prompt 回 ("", [])。
2. 冪等：prompt 已帶 marker（巢狀 sub-agent）不重複注入；already_injected 排除。
3. 緊湊 top-k（≤3）+ budget 守紅線。
4. PostToolUse `_record_subagent_injection` 從注入後 prompt 無狀態回推 atom 清單，
   keyed by agentId，擷取 content 摘要（capped）；無 marker → 不記錄。
5. 端到端 round-trip：build → 模擬 tool_response → record 回推一致。
6. 結構守門：PreToolUse 有 Agent/Task 分支且用 updatedInput（CC 版本相依欄位，probe 已驗）；
   settings.json Pre+Post matcher 含 Agent|Task。

純函式 + 受控 tmp 索引，不依賴磁碟既有 atom。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE / "lib"))

import wg_atoms  # noqa: E402
from handlers.post_tool_use import (  # noqa: E402
    _record_subagent_injection,
    _extract_agent_output_summary,
    _SUBAGENT_INJ_CAP,
    _SUBAGENT_SUMMARY_CAP,
)


# ─── fixtures ───────────────────────────────────────────────────────────────


def _atom_text(title: str, triggers: list[str]) -> str:
    return (
        f"# {title}\n\n"
        f"- Scope: global\n"
        f"- Confidence: [固]\n"
        f"- Trigger: {', '.join(triggers)}\n"
        f"- Last-used: 2026-06-01\n"
        f"- Confirmations: 5\n"
        f"- ReadHits: 0\n\n"
        f"## 印象\n\n- {title} 的印象重點一句話。\n\n"
        f"## 行動\n\n- 做 {title} 對應的動作。\n"
    )


def _write_memory(tmp_path: Path, atoms: dict[str, list[str]]) -> Path:
    """建立受控 memory dir：_ATOM_INDEX.md 觸發表 + atom 檔。回傳 memory dir。"""
    mem = tmp_path / "memory"
    mem.mkdir(parents=True, exist_ok=True)
    rows = ["| Atom | Path | Triggers |", "|------|------|----------|"]
    for name, trig in atoms.items():
        (mem / f"{name}.md").write_text(_atom_text(name, trig), encoding="utf-8")
        rows.append(f"| {name} | memory/{name}.md | {', '.join(trig)} |")
    (mem / "_ATOM_INDEX.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return mem


@pytest.fixture
def patched_memory(tmp_path, monkeypatch):
    mem = _write_memory(tmp_path, {
        "alpha-atom": ["alphakeyword", "阿爾法"],
        "beta-atom": ["betakeyword"],
    })
    monkeypatch.setattr(wg_atoms, "MEMORY_DIR", mem)
    return mem


# ─── build_injection_blob: 命中 ─────────────────────────────────────────────


def test_blob_injects_on_trigger_hit(patched_memory):
    blob, inj = wg_atoms.build_injection_blob(
        "please handle the alphakeyword task now", budget=700,
    )
    assert inj, "trigger 命中應有注入"
    assert "alpha-atom" in inj
    assert wg_atoms.SUBAGENT_INJECT_MARKER in blob
    assert "alpha-atom 的印象重點" in blob


def test_blob_marker_atoms_match_injected(patched_memory):
    blob, inj = wg_atoms.build_injection_blob(
        "alphakeyword betakeyword 一起來", budget=700,
    )
    # header 的 atoms= 清單須與回傳 injected 一致（PostToolUse 靠它回推）
    import re
    m = re.search(r"atoms=([^\n]+)", blob)
    assert m, "blob 缺 atoms= marker"
    marker_atoms = [a.strip() for a in m.group(1).split(",") if a.strip()]
    assert marker_atoms == inj


def test_cjk_trigger_substring_match(patched_memory):
    _blob, inj = wg_atoms.build_injection_blob("處理阿爾法相關需求", budget=700)
    assert "alpha-atom" in inj


# ─── build_injection_blob: 不注入 / 冪等 / 排除 ──────────────────────────────


def test_empty_when_no_match(patched_memory):
    blob, inj = wg_atoms.build_injection_blob("zzqq totally unrelated xyzzy", budget=700)
    assert blob == "" and inj == []


def test_idempotent_when_marker_present(patched_memory):
    blob, inj = wg_atoms.build_injection_blob("alphakeyword task", budget=700)
    assert inj
    blob2, inj2 = wg_atoms.build_injection_blob(blob + "\n\n真正任務", budget=700)
    assert blob2 == "" and inj2 == [], "已含 marker 不得重複注入（巢狀 sub-agent 防爆）"


def test_already_injected_excluded(patched_memory):
    _b, inj = wg_atoms.build_injection_blob("alphakeyword", budget=700)
    assert "alpha-atom" in inj
    _b2, inj2 = wg_atoms.build_injection_blob(
        "alphakeyword", budget=700, already_injected=["alpha-atom"],
    )
    assert "alpha-atom" not in inj2


def test_empty_prompt(patched_memory):
    blob, inj = wg_atoms.build_injection_blob("", budget=700)
    assert blob == "" and inj == []


# ─── 緊湊 top-k + budget ─────────────────────────────────────────────────────


def test_respects_top_k(tmp_path, monkeypatch):
    mem = _write_memory(tmp_path, {
        f"atom-{i}": ["sharedtrigger"] for i in range(6)
    })
    monkeypatch.setattr(wg_atoms, "MEMORY_DIR", mem)
    _blob, inj = wg_atoms.build_injection_blob("sharedtrigger everywhere", budget=5000)
    assert len(inj) <= wg_atoms._SUBAGENT_TOP_K, "top-k 須緊湊（≤3）"


def test_tiny_budget_shrinks_injection(patched_memory):
    _b_big, inj_big = wg_atoms.build_injection_blob("alphakeyword betakeyword", budget=5000)
    _b_small, inj_small = wg_atoms.build_injection_blob("alphakeyword betakeyword", budget=10)
    assert len(inj_small) <= len(inj_big)


# ─── PostToolUse: _record_subagent_injection 無狀態回推 ──────────────────────


def _fake_input(prompt: str, *, agent_id="agent_x", content=None, tool_use_id="toolu_1"):
    return {
        "tool_name": "Agent",
        "tool_use_id": tool_use_id,
        "tool_input": {"prompt": prompt},
        "tool_response": {
            "agentId": agent_id,
            "agentType": "general-purpose",
            "status": "completed",
            "prompt": prompt,
            "content": content if content is not None else [{"type": "text", "text": "完成。"}],
        },
    }


def test_record_recovers_atoms_from_marker(patched_memory):
    blob, inj = wg_atoms.build_injection_blob("alphakeyword betakeyword", budget=700)
    full_prompt = blob + "\n\n實際任務內容"
    state: dict = {}
    ok = _record_subagent_injection(state, _fake_input(full_prompt, agent_id="agent_777"))
    assert ok is True
    recs = state["subagent_injections"]
    assert len(recs) == 1
    rec = recs[0]
    assert rec["agent_id"] == "agent_777"
    assert rec["atoms"] == inj, "回推 atom 清單須與注入一致"
    assert rec["status"] == "completed"
    assert rec["tool_use_id"] == "toolu_1"


def test_record_no_marker_returns_false():
    state: dict = {}
    ok = _record_subagent_injection(state, _fake_input("沒有任何 marker 的純任務"))
    assert ok is False
    assert "subagent_injections" not in state


def test_record_non_dict_response_safe():
    state: dict = {}
    ok = _record_subagent_injection(state, {"tool_name": "Agent", "tool_response": "oops-string"})
    assert ok is False


def test_record_caps_list(patched_memory):
    blob, _inj = wg_atoms.build_injection_blob("alphakeyword", budget=700)
    full_prompt = blob + "\n\n任務"
    state: dict = {}
    for i in range(_SUBAGENT_INJ_CAP + 10):
        _record_subagent_injection(state, _fake_input(full_prompt, agent_id=f"a{i}"))
    assert len(state["subagent_injections"]) == _SUBAGENT_INJ_CAP, "spawn 記錄須上限封頂"
    # 保留最新（FIFO 截尾）
    assert state["subagent_injections"][-1]["agent_id"] == f"a{_SUBAGENT_INJ_CAP + 9}"


def test_extract_summary_caps():
    long_text = "句" * 1000
    tr = {"content": [{"type": "text", "text": long_text}]}
    summary = _extract_agent_output_summary(tr)
    assert len(summary) == _SUBAGENT_SUMMARY_CAP


def test_extract_summary_handles_str_content():
    assert _extract_agent_output_summary({"content": "純字串輸出"}) == "純字串輸出"


def test_extract_summary_empty():
    assert _extract_agent_output_summary({}) == ""


# ─── 端到端 round-trip ───────────────────────────────────────────────────────


def test_roundtrip_build_then_record(patched_memory):
    """PreToolUse 注入 → PostToolUse 回推：atoms 清單必須無損往返。"""
    orig = "請處理 alphakeyword 與 betakeyword 的整合"
    blob, injected = wg_atoms.build_injection_blob(orig, budget=700)
    assert injected
    sub_agent_prompt = blob + "\n\n" + orig  # PreToolUse 實際 prepend 形式
    state: dict = {}
    _record_subagent_injection(state, _fake_input(sub_agent_prompt, agent_id="rt1"))
    assert state["subagent_injections"][0]["atoms"] == injected


# ─── 結構守門（版本相依 / 配置回歸）────────────────────────────────────────


def test_pretool_has_agent_branch_with_updatedinput():
    """probe 已驗 CC 採納 updatedInput（非 modifiedInput）。守住欄位名 + 分支不被改回。"""
    src = (HOOKS_DIR / "handlers" / "pre_tool_use.py").read_text(encoding="utf-8")
    assert 'tool_name in ("Agent", "Task")' in src, "PreToolUse 缺 Agent/Task 注入分支"
    assert "build_injection_blob" in src
    assert "updatedInput" in src, "updatedInput 是當前 CC 版本實測採納的欄位（不可改回 modifiedInput）"


def test_posttool_has_agent_record_branch():
    src = (HOOKS_DIR / "handlers" / "post_tool_use.py").read_text(encoding="utf-8")
    assert 'tool_name in ("Agent", "Task")' in src
    assert "_record_subagent_injection" in src


def test_settings_matchers_include_agent_task():
    settings = json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))
    hooks = settings.get("hooks", {})

    def _has_agent_task(event: str) -> bool:
        for block in hooks.get(event, []):
            matcher = block.get("matcher", "")
            if "Agent" in matcher and "Task" in matcher:
                return True
        return False

    assert _has_agent_task("PreToolUse"), "PreToolUse matcher 缺 Agent|Task"
    assert _has_agent_task("PostToolUse"), "PostToolUse matcher 缺 Agent|Task"


def test_no_temp_probe_residue():
    """臨時 probe / diag（sentinel / phase1-*.log / LIVE 診斷）不得殘留於正式碼。"""
    pre = (HOOKS_DIR / "handlers" / "pre_tool_use.py").read_text(encoding="utf-8")
    post = (HOOKS_DIR / "handlers" / "post_tool_use.py").read_text(encoding="utf-8")
    for src in (pre, post):
        assert "WG_PROBE_SENTINEL" not in src
        assert "phase1-probe.log" not in src
        assert "phase1-diag.log" not in src
        assert "LIVE Agent branch" not in src
        assert "LIVE PostToolUse Agent" not in src
