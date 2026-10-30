"""verify_pre_tool_use_overview_gate.py：pre_tool_use 的 OverviewHub 段（A4.5）端到端。

正例：Bash／PowerShell 寫進 readonly_paths 被 deny、沒命中照放；Edit OverviewHub 自家設定檔放行（track-0 豁免仍有效）；
閘自己炸、state 寫不進去照 GATE_SELF_ERROR 送法（v6 開提醒、block 照擋）；判不出寫入目標放行留帳。
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
    monkeypatch.setenv("WG_TEMP_RULES", "off")        # 假專案在 pytest tmp 下：關掉 TEMP_COPY_NOT_PROJECT（B14 的案自己再開）
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


def _readonly(proj, pattern="Game/Battle/A.cs"):
    (proj / ".claude" / "overview-hub.json").write_text(f'{{"readonly_paths": ["{pattern}"]}}', encoding="utf-8")


def test_bash_write_to_readonly_path_is_denied(world):
    proj, outputs, tp = world
    _readonly(proj)
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    out = _run("Bash", {"command": f'echo x > "{f1}"'}, proj, tp, outputs)
    assert _deny(out) and "readonly_paths（樣式「Game/Battle/A.cs」）" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_powershell_write_to_readonly_path_is_denied(world):
    proj, outputs, tp = world
    _readonly(proj)
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    out = _run("PowerShell", {"command": f'Set-Content -Path "{f1}" -Value "x"'}, proj, tp, outputs)
    assert _deny(out) and "readonly_paths" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert not _deny(_run("Edit", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, proj, tp, outputs))   # 沒命中照放


def test_006_4_bash_sc_is_not_set_content(world):
    """反例：Bash 下 sc 是 Windows 的 sc.exe（服務控制），不是 Set-Content；別名只在 PowerShell 工具下換。"""
    assert wg_core.write_paths_from_tool("Bash", {"command": "sc query wuauserv"}, "C:/x") == []
    got = wg_core.write_paths_from_tool("PowerShell", {"command": "sc C:/x/a.txt v"}, "C:/x")
    assert [p.replace("\\", "/") for p in got] == ["C:/x/a.txt"]


def test_other_workflow_files_and_running_verify_not_affected(world, tmp_path):
    proj, outputs, tp = world
    for tool, ti in (("Write", {"file_path": str(tmp_path / "wf" / "other.json"), "content": "{}"}),
                     ("Write", {"file_path": str(tmp_path / "wf" / "verify-ledger-notes.md"), "content": "x"})):
        out = _run(tool, ti, proj, tp, outputs)
        assert not _deny(out), (tool, ti)
    # 整組 run_verify 另有驗證批次閘（wg_verify_batch）要使用者口令：給本回合原話「跑整組」，這裡只看綜觀閘不擋它
    wg_core.write_state(SID, {"session": {"id": SID}, "turn_seq": 1, "turn_prompts_seq": 1,
                              "turn_prompts": ["跑整組"], "recent_user_prompts": ["跑整組"]})
    out = _run("Bash", {"command": "python -X utf8 run_verify.py"}, proj, tp, outputs)
    assert not _deny(out)


def test_bash_without_write_target_passes_untouched(world):
    proj, outputs, tp = world
    out = _run("Bash", {"command": f'cat "{proj / "Game" / "Battle" / "A.cs"}"'}, proj, tp, outputs)
    assert out is None and not wg_core.state_file_path(SID).exists()


def test_editing_own_hub_config_is_allowed_with_warning(world):
    proj, outputs, tp = world
    hub = proj / ".claude" / "overview-hub.json"
    hub.write_text('{"bogus": 1}', encoding="utf-8")
    # 既有設定檔、原話沒點名：動資料檔閘（wg_data_file）要先宣告；這裡只守 OverviewHub 自家設定檔的豁免
    Path(tp).write_text(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "動資料檔｜.claude/overview-hub.json：修掉 bogus 鍵讓閘讀得到設定"}]}}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    out = _run("Edit", {"file_path": str(hub)}, proj, tp, outputs)
    assert not _deny(out) and "放行以便修復" in out["hookSpecificOutput"]["additionalContext"]


def test_gate_internal_error_reminds_v6_on_denies_v6_off(world, monkeypatch):
    """閘自己炸（規則 GATE_SELF_ERROR）：v6 開 → 不擋、stderr＋hub log gate_error（rule、allowed）；state 建不出來就只留帳。
    送法是 block（表上標 block、或 v6 關時 gate_mode 回 block）→ 照 001 BLOCK 6 擋、不 fail-open（擋訊息「閘環境異常」帶錯誤）。"""
    proj, outputs, tp = world
    f1 = str(proj / "Game" / "Battle" / "A.cs")

    def _boom(*a, **k):
        raise PermissionError("state locked")
    monkeypatch.setattr(wg_core, "_ensure_state", _boom)
    out = _run("Edit", {"file_path": f1}, proj, tp, outputs)
    assert out is None, out
    log = (proj.parent / "hub.log").read_text(encoding="utf-8")
    assert '"event": "gate_error"' in log and '"rule": "GATE_SELF_ERROR"' in log and '"allowed": true' in log
    monkeypatch.setattr(ptu._rr, "gate_mode", lambda rule, v6: ptu._rr.BLOCK)   # 送法固定成擋（同 v6 關時 gate_mode 的回法）
    out = _run("Edit", {"file_path": f1}, proj, tp, outputs)
    assert _deny(out) and "閘環境異常" in out["hookSpecificOutput"]["permissionDecisionReason"] and "state locked" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert '"deny_reason": "gate_error"' in (proj.parent / "hub.log").read_text(encoding="utf-8")


def test_write_state_failure_reminds_v6_on(world, monkeypatch):
    """寫不進 state（規則 GATE_SELF_ERROR，v6 開）：不擋；待提醒存不住，一行提醒跟著這次放行的警告走（additionalContext），
    hub log state_persist_failed 帶 rule、allowed；寫得進去就安靜放行。觸發待提醒的是設定錯誤那一件（GATE_SELF_ERROR 提醒）。"""
    proj, outputs, tp = world
    (proj / ".claude" / "overview-hub.json").write_text('{"bogus": 1}', encoding="utf-8")
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    with pytest.MonkeyPatch.context() as mp:                                   # 模擬 write_state 吞掉 OSError 沒寫進去
        mp.setattr(wg_core, "write_state", lambda sid, st: None)
        out = _run("Edit", {"file_path": f1}, proj, tp, outputs)
    ctx = (out or {}).get("hookSpecificOutput", {}).get("additionalContext", "")
    assert not _deny(out) and "[Guardian:提醒] GATE_SELF_ERROR" in ctx and "state 無法持久化" in ctx, out
    log = (proj.parent / "hub.log").read_text(encoding="utf-8")
    assert '"event": "state_persist_failed"' in log and '"rule": "GATE_SELF_ERROR"' in log and "state_unpersisted" not in log
    assert not _deny(_run("Edit", {"file_path": f1}, proj, tp, outputs))      # 寫得進去就放行


def test_unknown_write_target_is_allowed_end_to_end(world):
    """規則 UNKNOWN_TARGET_LOGGED：解析不出寫入目標（變數路徑）→ 放行並留帳，不擋。"""
    proj, outputs, tp = world
    out = _run("Bash", {"command": "echo x > $OUT/a.txt"}, proj, tp, outputs)
    assert not _deny(out)


def test_013_4_subagent_tool_call_gets_same_unknown_target_handling(world):
    """子代理的工具呼叫（hook 輸入帶 agent_id）走同一個 handle_pre_tool_use，沒有 agent_id 分支：
    內嵌碼寫檔判不出目標，跟主 session 一樣放行並留帳。"""
    proj, outputs, tp = world
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": "Bash", "tool_input": {"command": "python -c \"open('x','w').write('1')\""}, "session_id": SID,
                                 "agent_id": "ag1", "agent_type": "general-purpose", "cwd": str(proj), "transcript_path": tp}, {})
    assert not _deny(outputs[-1] if outputs else None)


def test_045_inline_py_readonly_end_to_end_allows_pure_read_and_node(world):
    """規則 INLINE_PY_READONLY：`python -c "print(1)"` 只讀 → 放行；`node -e` 判不了 → 也放行（UNKNOWN_TARGET_LOGGED 留帳）。"""
    proj, outputs, tp = world
    out = _run("Bash", {"command": 'python -c "import json;print(json.dumps({}))"'}, proj, tp, outputs)
    assert not _deny(out)
    out = _run("Bash", {"command": 'node -e "console.log(1)"'}, proj, tp, outputs)
    assert not _deny(out)


# ─── 子代理：對話在 <sid>/subagents/agent-<agent_id>.jsonl，主 session 是同層的 <sid>.jsonl ───


def test_006_scratchpad_written_via_literal_var_is_allowed(world, tmp_path, monkeypatch):
    """閘小修 006 件 5（第五跑 C-1 第 4 回合）：`S='<scratchpad>' && git show … > "$S/old.cs"` 寫進 scratchpad 存舊版做對照。
    前置：同一個 scratchpad 用字面路徑寫是放行的；修之前加了變數就整條當「判不出寫入目標」。
    規則 SHELL_LITERAL_VAR_EXPANDED：同指令的字面指定代換後算得出目標，照字面路徑同樣判。"""
    proj, outputs, tp = world
    monkeypatch.delenv("WG_TEMP_RULES")                       # 暫存區規則本身要開著
    scratch = tmp_path / "claude" / "C--w4-qc2-orders" / SID / "scratchpad"
    scratch.mkdir(parents=True)
    assert not _deny(_run("Bash", {"command": f'git show HEAD:Game/Battle/A.cs > "{scratch}/old0.cs"'}, proj, tp, outputs))
    out = _run("Bash", {"command": f"S='{scratch}' && git show HEAD:Game/Battle/A.cs > \"$S/old_A.cs\""}, proj, tp, outputs)
    assert not _deny(out), out
    # 對照（codex 006）：同一個變數寫法指到唯讀檔照擋——變數代換算出了真目標、閘有跑。
    # 假專案本身也在 pytest 暫存目錄下，暫存規則開著會整個當暫存副本，對照這一步關掉它（專案照專案判）
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    _readonly(proj)
    battle = proj / "Game" / "Battle"
    out = _run("Bash", {"command": f"S='{battle}' && echo x > \"$S/A.cs\""}, proj, tp, outputs)
    reason = (out or {}).get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
    assert _deny(out) and "readonly_paths" in reason and "無法判定" not in reason, out
