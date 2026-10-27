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


@pytest.fixture(autouse=True)
def _whole_card(monkeypatch):
    """這支照整張注入（card_injection=full）寫的；指標制（預設）的案例在 verify_overview_card_pointer.py。"""
    from hub_config import HUB_DEFAULTS
    monkeypatch.setitem(HUB_DEFAULTS, "card_injection", "full")

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


def test_006_4_bash_sc_is_not_set_content(world):
    """反例：Bash 下 sc 是 Windows 的 sc.exe（服務控制），不是 Set-Content；別名只在 PowerShell 工具下換。"""
    assert wg_core.write_paths_from_tool("Bash", {"command": "sc query wuauserv"}, "C:/x") == []
    got = wg_core.write_paths_from_tool("PowerShell", {"command": "sc C:/x/a.txt v"}, "C:/x")
    assert [p.replace("\\", "/") for p in got] == ["C:/x/a.txt"]


def test_other_workflow_files_and_running_verify_not_affected(world, tmp_path):
    proj, outputs, tp = world
    for tool, ti in (("Write", {"file_path": str(tmp_path / "wf" / "other.json"), "content": "{}"}),
                     ("Write", {"file_path": str(tmp_path / "wf" / "verify-ledger-notes.md"), "content": "x"}),
                     ("Bash", {"command": "python -X utf8 run_verify.py"})):
        out = _run(tool, ti, proj, tp, outputs)
        assert not _deny(out), (tool, ti)


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


def _reply(tp, mid, *tids, text=""):
    """AI 的一則回覆 mid 整則落進 transcript（文字＋它送出的 tool_use）：之後的呼叫屬下一則（批次鍵＝這則的 message.id）。"""
    blocks = ([{"type": "text", "text": text}] if text else []) + [{"type": "tool_use", "id": t, "name": "Edit", "input": {}}
                                                                    for t in tids]
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"id": mid, "content": blocks or [{"type": "text", "text": "…"}]}},
                           ensure_ascii=False) + "\n")


def _call(tool, tool_input, proj, tp, outputs, tid):
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": tool, "tool_input": tool_input, "session_id": SID, "cwd": str(proj),
                                 "transcript_path": tp, "tool_use_id": tid}, {})
    return outputs[-1]


def test_parallel_edits_in_one_reply_all_denied_then_locate_passes(world):
    """規則 DENY_CAP_PER_REPLY（004 改 code 題 B6 的根因）：同一則回覆平行送出 4 個 Edit 改同一部位的檔、都沒交定位 → 4 個都擋
    （擋次照則數，這一則只算一次；舊碼照每個呼叫算，第 3 個起記 edit_deny_capped、沒交定位就放行）；下一則交了定位 → 放行。"""
    proj, outputs, tp = world
    files = [str(proj / "Game" / "Battle" / f"{n}.cs") for n in "ABCD"]
    for f in files[1:]:
        Path(f).write_text("x", encoding="utf-8")
    _reply(tp, "msg_0")
    assert _deny(_call("Edit", {"file_path": files[0]}, proj, tp, outputs, "tu_inject"))     # 注入導讀卡（不算進缺件次數）
    _reply(tp, "msg_1", "tu_inject")
    state = _state()
    wo.on_read(state, SID, "Read", {"file_path": files[0]}, str(proj), tp, {})                 # 讀部位檔
    wg_core.write_state(SID, state)
    _reply(tp, "msg_2")
    outs = [_call("Edit", {"file_path": f, "old_string": "x", "new_string": "y"}, proj, tp, outputs, f"tu_{i}")
            for i, f in enumerate(files)]
    assert [_deny(o) for o in outs] == [True] * 4, outs
    assert "edit_deny_capped" not in (proj.parent / "hub.log").read_text(encoding="utf-8")
    _reply(tp, "msg_3", "tu_0", "tu_1", "tu_2", "tu_3")
    _reply(tp, "msg_4", text=LOCATE.replace("A.cs", "A.cs、B.cs、C.cs、D.cs"))
    assert not _deny(_call("Edit", {"file_path": files[2], "old_string": "x", "new_string": "y"}, proj, tp, outputs, "tu_5"))
    assert _rec(_state())["located"] is True


# ─── 子代理：對話在 <sid>/subagents/agent-<agent_id>.jsonl，主 session 是同層的 <sid>.jsonl ───

AGENT = "ae3c716a6fc9ec36b"
LOCATE = "定位｜部位：戰鬥：A.cs\n定位｜根因層：邏輯層\n定位｜前例：共用字典"


def _line(text):
    return json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}, ensure_ascii=False) + "\n"


def _agent_layout(tmp_path):
    """Claude Code 的真實佈局：主檔比子代理檔長（主 session 已經聊了很多），子代理檔才剛開始。"""
    main = tmp_path / f"{SID}.jsonl"
    main.write_text("".join(_line(f"主 session 第 {i} 段說明，派子代理去改戰鬥") for i in range(40)), encoding="utf-8")
    agent = tmp_path / SID / "subagents" / f"agent-{AGENT}.jsonl"
    agent.parent.mkdir(parents=True)
    agent.write_text(json.dumps({"type": "user", "message": {"content": "改 A.cs"}}, ensure_ascii=False) + "\n", encoding="utf-8")
    return main, agent


def _agent_edit(proj, outputs, f1, tp):
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": "Edit", "tool_input": {"file_path": f1}, "session_id": SID, "agent_id": AGENT,
                                 "cwd": str(proj), "transcript_path": str(tp)}, {})
    return outputs[-1]


@pytest.mark.parametrize("hook_gives", ["main", "agent"])
def test_subagent_locate_lines_in_its_own_transcript_allow_edit(world, tmp_path, hook_gives):
    """子代理讀過部位檔、在自己的回覆寫了定位三行 → 放行；hook 給主檔或給子代理檔都要認得到。"""
    proj, outputs, _ = world
    main, agent = _agent_layout(tmp_path)
    tp = main if hook_gives == "main" else agent
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    assert _deny(_agent_edit(proj, outputs, f1, tp))                             # 第一次：注入卡＋擋
    state = _state()
    wo.on_read(state, SID, "Read", {"file_path": f1}, str(proj), str(tp), {})     # 子代理的 Read 事件
    wg_core.write_state(SID, state)
    with open(agent, "a", encoding="utf-8") as f:
        f.write(_line(LOCATE))
    out = _agent_edit(proj, outputs, f1, tp)
    assert not _deny(out), (out or {}).get("hookSpecificOutput", {}).get("permissionDecisionReason", "")[:400]
    assert _rec(_state())["located"] is True


@pytest.mark.parametrize("hook_gives", ["main", "agent"])
def test_subagent_without_locate_lines_anywhere_is_denied(world, tmp_path, hook_gives):
    proj, outputs, _ = world
    main, agent = _agent_layout(tmp_path)
    tp = main if hook_gives == "main" else agent
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    assert _deny(_agent_edit(proj, outputs, f1, tp))
    state = _state()
    wo.on_read(state, SID, "Read", {"file_path": f1}, str(proj), str(tp), {})
    wg_core.write_state(SID, state)
    with open(agent, "a", encoding="utf-8") as f:
        f.write(_line("先看 A.cs 的邏輯"))
    assert _deny(_agent_edit(proj, outputs, f1, tp))
    assert _rec(_state())["located"] is False


def test_locate_lines_written_before_injection_in_subagent_file_do_not_count(world, tmp_path):
    """各檔各記注入當下的大小：子代理在讀卡之前就寫的定位行不算（跟主檔的 offset 規則一致）。"""
    proj, outputs, _ = world
    main, agent = _agent_layout(tmp_path)
    with open(agent, "a", encoding="utf-8") as f:
        f.write(_line(LOCATE))                                                   # 注入前就寫
    f1 = str(proj / "Game" / "Battle" / "A.cs")
    assert _deny(_agent_edit(proj, outputs, f1, main))
    state = _state()
    wo.on_read(state, SID, "Read", {"file_path": f1}, str(proj), str(main), {})
    wg_core.write_state(SID, state)
    assert _deny(_agent_edit(proj, outputs, f1, main))


def test_006_scratchpad_written_via_literal_var_is_allowed(world, tmp_path, monkeypatch):
    """閘小修 006 件 5（第五跑 C-1 第 4 回合）：`S='<scratchpad>' && git show … > "$S/old.cs"` 寫進 scratchpad 存舊版做對照。
    前置：同一個 scratchpad 用字面路徑寫是放行的（暫存區不是部位檔）；修之前加了變數就整條當「判不出寫入目標」擋（edit_unknown_target）。
    規則 SHELL_LITERAL_VAR_EXPANDED：同指令的字面指定代換後算得出目標，照字面路徑同樣判。"""
    proj, outputs, tp = world
    monkeypatch.delenv("WG_TEMP_RULES")                       # 暫存區規則本身要開著
    scratch = tmp_path / "claude" / "C--w4-qc2-orders" / SID / "scratchpad"
    scratch.mkdir(parents=True)
    assert not _deny(_run("Bash", {"command": f'git show HEAD:Game/Battle/A.cs > "{scratch}/old0.cs"'}, proj, tp, outputs))
    out = _run("Bash", {"command": f"S='{scratch}' && git show HEAD:Game/Battle/A.cs > \"$S/old_A.cs\""}, proj, tp, outputs)
    assert not _deny(out), out
    # 對照（codex 006）：同一個變數寫法指到部位檔照擋，而且擋的是部位證據、不是判不出目標——變數代換算出了真目標、閘有跑。
    # 假專案本身也在 pytest 暫存目錄下，暫存規則開著會整個當暫存副本，對照這一步關掉它（專案照專案判）
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    battle = proj / "Game" / "Battle"
    out = _run("Bash", {"command": f"S='{battle}' && echo x > \"$S/A.cs\""}, proj, tp, outputs)
    reason = (out or {}).get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
    assert _deny(out) and "戰鬥" in reason and "無法判定" not in reason, out
