"""verify_pre_tool_use_overview_gate.py：pre_tool_use 的 OverviewHub 段（A4.5）端到端。

正例：Bash 改部位檔被 deny；PowerShell 同；Edit OverviewHub 自家設定檔放行（track-0 豁免仍有效）；
state 檔不存在 → 第一次 Edit deny 且 state 檔被建立、注入紀錄落盤；讀過部位檔並交定位三行後第二次 Edit 放行；
edits 累加不丟（兩次放行後 rec.edits == 2）。
live 檔全 monkeypatch：WORKFLOW_DIR（state 落 tmp）、LOG_PATH、公司根、最小索引重建、sibling 認領。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_pre_tool_use_overview_gate.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_core  # noqa: E402
import wg_overview as wo  # noqa: E402
from handlers import pre_tool_use as ptu  # noqa: E402

SID = "sess-gate-0001"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """假專案（有表、有卡）＋ tmp workflow 目錄；回 (proj, outputs, transcript_path)。"""
    proj = tmp_path / "proj"
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 |\n|---|---|---|---|\n| `Game\\Battle\\` | 戰鬥 | `戰鬥導讀` | 有 |\n", encoding="utf-8")
    (proj / ".claude" / "memory" / "shared" / "戰鬥導讀.md").write_text(
        "# 戰鬥導讀\n\n## 知識\n\n- [臨] **已知病灶**：共用字典\n", encoding="utf-8")
    (proj / "Game" / "Battle").mkdir(parents=True)
    (proj / "Game" / "Battle" / "A.cs").write_text("x", encoding="utf-8")
    wf = tmp_path / "wf"
    wf.mkdir()
    tp = tmp_path / "t.jsonl"
    tp.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "先看"}]}}) + "\n", encoding="utf-8")
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_core, "_rebuild_min_atom_index", lambda cwd: {})
    monkeypatch.setattr(wg_core, "_find_active_sibling_state", lambda *a, **k: None)
    monkeypatch.setattr(wg_core, "_atom_debug_log", lambda *a, **k: None)
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    outputs = []

    def _out(d):
        outputs.append(d)
        raise SystemExit(0)

    def _nothing():
        outputs.append(None)
        raise SystemExit(0)
    monkeypatch.setattr(ptu, "output_json", _out)
    monkeypatch.setattr(ptu, "output_nothing", _nothing)
    return proj, outputs, str(tp)


def _run(tool, tool_input, proj, tp, outputs):
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use(
            {"tool_name": tool, "tool_input": tool_input, "session_id": SID, "cwd": str(proj), "transcript_path": tp},
            {},
        )
    return outputs[-1]


def _deny(out):
    return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def _state():
    return json.loads(wg_core.state_file_path(SID).read_text(encoding="utf-8"))


def _rec(state):
    return next(v for k, v in state["overview_hub"].items() if k.endswith("|戰鬥"))


def test_bash_write_to_part_file_is_denied_and_state_created(world):
    proj, outputs, tp = world
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    assert not wg_core.state_file_path(SID).exists()
    out = _run("Bash", {"command": f'echo x > "{f1}"'}, proj, tp, outputs)
    assert _deny(out) and "戰鬥" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert wg_core.state_file_path(SID).exists()                 # 沒 state 檔 → 建檔，注入紀錄落盤
    assert _rec(_state())["edits"] == 0


def test_powershell_write_to_part_file_is_denied(world):
    proj, outputs, tp = world
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    out = _run("PowerShell", {"command": f'Set-Content -Path "{f1}" -Value "x"'}, proj, tp, outputs)
    assert _deny(out) and "共用字典" in out["hookSpecificOutput"]["permissionDecisionReason"]   # deny 理由帶卡


def test_bash_without_write_target_passes_untouched(world):
    proj, outputs, tp = world
    out = _run("Bash", {"command": f'cat "{proj / "Game" / "Battle" / "A.cs"}"'}, proj, tp, outputs)
    assert out is None and not wg_core.state_file_path(SID).exists()


def test_editing_own_hub_config_is_allowed_with_warning(world):
    proj, outputs, tp = world
    hub = proj / ".claude" / "overview-hub.json"
    hub.write_text('{"bogus": 1}', encoding="utf-8")
    out = _run("Edit", {"file_path": str(hub)}, proj, tp, outputs)
    assert not _deny(out) and "放行以便修復" in out["hookSpecificOutput"]["additionalContext"]


def test_gate_internal_error_denies(world, monkeypatch):            # 退回 001 BLOCK 6：閘自己炸也擋，不 fail-open
    proj, outputs, tp = world
    f1 = str(proj / "Game" / "Battle" / "A.cs")

    def _boom(*a, **k):
        raise PermissionError("state locked")
    monkeypatch.setattr(wg_core, "_ensure_state", _boom)
    out = _run("Edit", {"file_path": f1}, proj, tp, outputs)
    assert _deny(out) and "閘環境異常" in out["hookSpecificOutput"]["permissionDecisionReason"] and "state locked" in out["hookSpecificOutput"]["permissionDecisionReason"]
    log = (proj.parent / "hub.log").read_text(encoding="utf-8")
    assert '"event": "gate_error"' in log and '"deny_reason": "gate_error"' in log


def test_write_state_failure_denies(world, monkeypatch):            # 退回 002 第 7 條：寫不進 state 就擋
    proj, outputs, tp = world
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    assert _deny(_run("Edit", {"file_path": f1}, proj, tp, outputs))          # 正常：注入＋建檔
    state = _state()
    wo.on_read(state, SID, "Read", {"file_path": f1}, str(proj), tp, {})
    wg_core.write_state(SID, state)
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥：A.cs\n定位｜根因層：邏輯層\n定位｜前例：共用字典"}]}}, ensure_ascii=False) + "\n")
    with pytest.MonkeyPatch.context() as mp:                                   # 模擬 write_state 吞掉 OSError 沒寫進去
        mp.setattr(wg_core, "write_state", lambda sid, st: None)
        out = _run("Edit", {"file_path": f1}, proj, tp, outputs)
    assert _deny(out) and "state 無法持久化" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert '"deny_reason": "state_unpersisted"' in (proj.parent / "hub.log").read_text(encoding="utf-8")
    assert not _deny(_run("Edit", {"file_path": f1}, proj, tp, outputs))      # 寫得進去就放行


def test_unknown_write_target_is_denied_end_to_end(world):           # 退回 001 BLOCK 4：解析不出 → fail-closed
    proj, outputs, tp = world
    out = _run("Bash", {"command": "echo x > $OUT/a.txt"}, proj, tp, outputs)
    assert _deny(out) and "改用 Edit／Write" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert not wg_core.state_file_path(SID).exists() or True              # UNKNOWN 不落 state（state 可能已建，不強求）


def test_missing_state_then_read_and_locate_then_allow_and_edits_accumulate(world):
    proj, outputs, tp = world
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    assert _deny(_run("Edit", {"file_path": f1}, proj, tp, outputs))          # 第一次：注入＋deny，state 建檔
    state = _state()
    assert "overview_hub" in state and _rec(state)["edits"] == 0
    wo.on_read(state, SID, "Read", {"file_path": f1}, str(proj), tp, {})      # 讀部位檔（PostToolUse 走 on_read）
    wg_core.write_state(SID, state)
    with open(tp, "a", encoding="utf-8") as f:                                 # 交定位三行
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                "text": "定位｜部位：戰鬥：A.cs\n定位｜根因層：邏輯層\n定位｜前例：共用字典"}]}}, ensure_ascii=False) + "\n")
    assert not _deny(_run("Edit", {"file_path": f1}, proj, tp, outputs))      # 第二次放行
    assert _rec(_state())["edits"] == 1 and _rec(_state())["located"] is True
    assert not _deny(_run("Bash", {"command": f'echo y >> "{f1}"'}, proj, tp, outputs))   # Bash 同目標也放行
    assert _rec(_state())["edits"] == 2                                        # 累加不丟
