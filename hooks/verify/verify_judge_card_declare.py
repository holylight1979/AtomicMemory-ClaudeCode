"""verify_judge_card_declare.py：改判準卡要先宣告（規則 JUDGE_CARD_CHANGE_NEEDS_DECLARATION，裁定 #53，hooks/wg_judge_card.py）端到端。

全部走 handlers.pre_tool_use.handle_pre_tool_use 真入口：
- 端到端：第五跑 C-1 第 3 回合真事件（fixtures/gate006/c1_judge_card_events.json：AI 用 atom_write mode=append 改綁 E22／E29 的卡）
  照原樣重播 → 擋、帳記 denied；補一行宣告 → 放行、帳記 declared（含宣告行與管道）。卡用 repo 裡那張真卡（唯讀，閘擋或放行都不寫檔）。
- MCP 其他出口：atom_edit_meta、atom_retire 改同一張也擋；atom_write mode=create 不管（不是改既有卡）。
- 檔案出口：Edit 綁 Entry 的卡沒宣告 → 擋；Bash 指令開頭 `#` 宣告 → 放行；沒綁 Entry 的卡 → 不擋也不留帳。
- 宣告格式：只寫 Entry 代號、理由留佔位、宣告字樣只寫在卡片內容（工具參數非註解行）都不算。
- 不靠 settings.json：三個 MCP 工具名的事件直接餵 handler 都走到本閘（matcher 由原設計者套用，沒套之前 MCP 出口不經過閘）。
- 直譯器出口（JUDGE_CARD_HASH_CATCHES_INTERPRETER）：PreToolUse 記雜湊 → 模擬腳本寫卡 → PostToolUse／PostToolUseFailure 比對；
  沒宣告留帳 undeclared、下一個呼叫擋、補宣告 declared_late；同指令 `#` 宣告直接 declared；沒改卡、不跑直譯器不留帳不記雜湊。
live 檔全 monkeypatch：WORKFLOW_DIR（state 落 tmp）、GUARD_LOG_DIR（留帳落 tmp）。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_judge_card_declare.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
REPO = HOOKS_DIR.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(REPO))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(REPO / "lib"))

import wg_core  # noqa: E402
import wg_release_rules as rr  # noqa: E402
from handlers import pre_tool_use as ptu  # noqa: E402

SID = "sess-judgecard-0001"
RULE = "JUDGE_CARD_CHANGE_NEEDS_DECLARATION"
TAG = "[Guardian:JudgeCardDeclare]"
C1 = json.loads((HOOKS_DIR / "verify" / "fixtures" / "gate006" / "c1_judge_card_events.json").read_text(encoding="utf-8"))
C1_STEM = C1["tool_input"]["title"]
CARD_HEAD = "# 卡\n\n- Scope: global\n- Confidence: [臨]\n- Trigger: 測試\n{entry}\n## 知識\n\n- [臨] 原本的判準\n"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """假專案（memory 底下一張綁 E99 的卡、一張沒綁的卡）＋ tmp workflow／Logs；回 dict(proj, bound, plain, tp, outputs, logs)。"""
    proj = tmp_path / "proj"
    cards = proj / "memory" / "版控"
    cards.mkdir(parents=True)
    bound = cards / "測試判準卡-綁e99.md"
    bound.write_text(CARD_HEAD.format(entry="- Entry: E99\n"), encoding="utf-8")
    plain = cards / "一般卡-沒綁entry.md"
    plain.write_text(CARD_HEAD.format(entry=""), encoding="utf-8")
    wf = tmp_path / "wf"
    wf.mkdir()
    logs = tmp_path / "Logs"
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", logs)
    monkeypatch.setattr(wg_core, "_rebuild_min_atom_index", lambda cwd: {})
    monkeypatch.setattr(wg_core, "_find_active_sibling_state", lambda *a, **k: None)
    monkeypatch.setattr(wg_core, "_atom_debug_log", lambda *a, **k: None)
    outputs = []

    def _out(d):
        outputs.append(d)
        raise SystemExit(0)

    def _nothing():
        outputs.append(None)
        raise SystemExit(0)
    monkeypatch.setattr(ptu, "output_json", _out)
    monkeypatch.setattr(ptu, "output_nothing", _nothing)
    wg_core.write_state(SID, {"session": {"id": SID, "cwd": str(proj)}, "turn_seq": 1,
                              "recent_user_prompts": [C1["user_prompt"]], "turn_prompts": [C1["user_prompt"]]})
    tp = tmp_path / "t.jsonl"
    _transcript(tp, [_user(C1["user_prompt"])] + [_assistant("text", t) for t in C1["assistant_texts"]])
    return {"proj": proj, "bound": bound, "plain": plain, "tp": str(tp), "outputs": outputs, "logs": logs}


def _user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def _assistant(kind, payload, tool="Bash"):
    block = {"text": {"type": "text", "text": payload},
             "thinking": {"type": "thinking", "thinking": payload},
             "tool_use": {"type": "tool_use", "name": tool, "input": payload}}[kind]
    return {"type": "assistant", "message": {"content": [block]}}


def _transcript(tp, entries):
    Path(tp).write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")


def _add(w, *entries):
    with open(w["tp"], "a", encoding="utf-8") as f:
        f.write("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))


def _run(w, tool, tool_input, config=None):
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": tool, "tool_input": tool_input, "session_id": SID, "cwd": str(w["proj"]),
                                 "transcript_path": w["tp"]}, config or {})
    return w["outputs"][-1]


def _jc_deny(out):
    """這次被改判準卡閘擋了沒（別的閘擋的不算）。"""
    hso = (out or {}).get("hookSpecificOutput") or {}
    return hso.get("permissionDecision") == "deny" and TAG in hso.get("permissionDecisionReason", "")


def _reason(out):
    return ((out or {}).get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")


def _log(w):
    p = w["logs"] / "guard-judge_card.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def _edit(w, path=None):
    return {"file_path": str(path or w["bound"]), "old_string": "- [臨] 原本的判準", "new_string": "- [臨] 原本的判準\n- [臨] 新加一條"}


def _real_c1_card():
    """前置：資料根（測試時是 conftest 隔離出來的副本）裡那張 C-1 被改的卡在、而且真的綁了 E22／E29
    （不然擋不擋都不是規則的功勞）。"""
    from atom_locations import GLOBAL_MEMORY_DIR, entry_bound_ids
    path = GLOBAL_MEMORY_DIR / "版控" / f"{C1_STEM}.md"
    assert path.is_file() and entry_bound_ids(None, path) == ["E22", "E29"], path
    return path


def test_c1_replay_mcp_append_without_declaration_is_denied(world):
    """第五跑 C-1 第 3 回合原樣重播：AI 沒宣告就 atom_write append 到判它的 E29 卡 → 擋，擋訊息給照抄行，帳記 denied。"""
    path = _real_c1_card()
    out = _run(world, C1["tool_name"], C1["tool_input"])
    assert _jc_deny(out), out
    r = _reason(out)
    assert f"✗ (jc) {RULE}：" in r and "綁 Entry E22、E29" in r
    assert f"改判準卡｜{C1_STEM}：<" in r and "atom_write mode=create" in r
    ev = _log(world)
    assert [(e["event"], e["card"], e["entry"], e["allowed"]) for e in ev] == [("denied", C1_STEM, ["E22", "E29"], False)]
    assert os.path.normcase(os.path.realpath(ev[0]["path"])) == os.path.normcase(os.path.realpath(path))
    assert ev[0]["tool"] == C1["tool_name"]


def test_c1_replay_after_declaration_is_allowed_and_logged(world):
    _real_c1_card()
    decl = f"改判準卡｜{C1_STEM}：使用者第 3 回合說 export_csv.py 是同事的，補「說了一起提交也照樣只提自己的」"
    _add(world, _assistant("text", decl))
    out = _run(world, C1["tool_name"], C1["tool_input"])
    assert not _jc_deny(out), out
    ev = _log(world)
    assert [(e["event"], e["allowed"], e["via"]) for e in ev] == [("declared", True, "text")]
    assert ev[0]["line"] == decl and ev[0]["session_id"] == SID


def test_mcp_edit_meta_and_retire_on_bound_card_are_denied(world):
    _real_c1_card()
    out = _run(world, "mcp__workflow-guardian__atom_edit_meta", {"atom_name": C1_STEM, "scope": "global", "entry": []})
    assert _jc_deny(out), out
    out = _run(world, "mcp__workflow-guardian__atom_retire", {"atom_name": C1_STEM, "scope": "global", "reason": "過時"})
    assert _jc_deny(out), out
    assert [e["tool"].rsplit("__", 1)[-1] for e in _log(world)] == ["atom_edit_meta", "atom_retire"]


@pytest.mark.parametrize("tool, make_input", [
    ("mcp__workflow-guardian__atom_write", lambda w: {**C1["tool_input"], "mode": "replace"}),
    ("Write", lambda w: {"file_path": str(w["bound"]), "content": "# 卡\n\n- Entry: E99\n\n## 知識\n\n- [臨] 整張改寫\n"}),
    ("PowerShell", lambda w: {"command": f"Add-Content -Path '{w['bound']}' -Value '- [臨] 補一條'"}),
], ids=["mcp-replace", "write", "powershell"])
def test_other_exits_without_declaration_are_denied(world, tool, make_input):
    """codex 006 第二輪：其餘出口（atom_write replace、Write 整檔改寫、PowerShell 寫入）沒宣告一樣擋、一樣留帳。"""
    if tool.startswith("mcp__"):
        _real_c1_card()
    out = _run(world, tool, make_input(world))
    assert _jc_deny(out), out
    assert [e["event"] for e in _log(world)] == ["denied"]


def test_mcp_create_is_not_a_change_of_existing_card(world):
    _real_c1_card()
    out = _run(world, C1["tool_name"], {**C1["tool_input"], "mode": "create"})
    assert not _jc_deny(out) and _log(world) == []


def test_edit_bound_card_without_declaration_is_denied(world):
    out = _run(world, "Edit", _edit(world))
    assert _jc_deny(out), out
    assert "測試判準卡-綁e99：綁 Entry E99" in _reason(out)
    assert [e["event"] for e in _log(world)] == ["denied"]


def test_bash_comment_declaration_in_same_command_allows(world):
    cmd = f"# 改判準卡｜測試判準卡-綁e99：使用者說這張卡的判準寫錯了\necho '- [臨] 補一條' >> '{world['bound']}'"
    out = _run(world, "Bash", {"command": cmd})
    assert not _jc_deny(out), out
    assert [(e["event"], e["via"]) for e in _log(world)] == [("declared", "tool_input")]


def test_plain_card_without_entry_is_not_gated_and_not_logged(world):
    from atom_locations import entry_bound_ids
    assert world["plain"].is_file() and entry_bound_ids(None, world["plain"]) == []    # 前置：真的沒綁
    out = _run(world, "Edit", _edit(world, world["plain"]))
    assert not _jc_deny(out) and _log(world) == []


@pytest.mark.parametrize("line", [
    "改判準卡｜E99：使用者說判準錯了",                                        # 只寫 Entry 代號：一個 Entry 綁好幾張，要點名哪一張
    "改判準卡｜測試判準卡-綁e99：<為什麼要改這張量尺；使用者原話或判錯的證據>",  # 照抄沒換掉佔位
    "改判準卡｜別張卡：使用者說判準錯了",                                      # 點到別張
])
def test_declaration_must_name_this_card_with_a_reason(world, line):
    _add(world, _assistant("text", line))
    out = _run(world, "Edit", _edit(world))
    assert _jc_deny(out), out


def test_declaration_written_inside_card_content_does_not_count(world):
    """宣告字樣只出現在工具參數的內容裡（不是 `#` 註解行）＝在卡上寫字，不是對使用者宣告。"""
    _add(world, _assistant("tool_use", {"title": "x", "knowledge": ["改判準卡｜測試判準卡-綁e99：自己覺得要改"]},
                           tool="mcp__workflow-guardian__atom_write"))
    out = _run(world, "Edit", _edit(world))
    assert _jc_deny(out), out


def test_disabled_config_skips_gate(world):
    out = _run(world, "Edit", _edit(world), config={"guard": {"judge_card_declare": {"enabled": False}}})
    assert not _jc_deny(out) and _log(world) == []


def test_handler_routes_three_mcp_tools_without_settings(world):
    """settings.json 的 matcher 由原設計者套用；這裡不靠 settings，直接把三個 MCP 工具名的事件餵給 handler，
    每個都要走到改判準卡閘（帳上有它的 denied），不會掉進其他分支。"""
    _real_c1_card()
    for name, ti in (("atom_write", C1["tool_input"]), ("atom_edit_meta", {"atom_name": C1_STEM, "scope": "global"}),
                     ("atom_retire", {"atom_name": C1_STEM, "scope": "global", "reason": "x"})):
        assert _jc_deny(_run(world, f"mcp__workflow-guardian__{name}", ti)), name
    assert [e["tool"].rsplit("__", 1)[-1] for e in _log(world)] == ["atom_write", "atom_edit_meta", "atom_retire"]


# ─── 直譯器自己開檔寫卡（JUDGE_CARD_HASH_CATCHES_INTERPRETER）───
# PreToolUse 記雜湊 → 模擬指令寫進磁碟 → PostToolUse（或 PostToolUseFailure）比對 → 下一個呼叫在 PreToolUse 擋到補宣告。

HASH_RULE = "JUDGE_CARD_HASH_CATCHES_INTERPRETER"


@pytest.fixture
def post(world, tmp_path, monkeypatch):
    """世界加上 PostToolUse 真入口：同一份 state 檔（PreToolUse 讀得到欠帳），其餘副作用關掉；資料根索引換成假專案那份
    （只有綁 E99 的卡，沒綁的卡不在索引的 entry 欄）。回 post(tool, tool_input, tool_use_id, failed=False)。"""
    from handlers import post_tool_use as pt
    proj = world["proj"]
    (proj / "memory" / "_atom_index.json").write_text(json.dumps({"version": 1, "atoms": [
        {"name": world["bound"].stem, "path": "memory/版控/測試判準卡-綁e99.md", "entry": ["E99"]},
        {"name": world["plain"].stem, "path": "memory/版控/一般卡-沒綁entry.md", "entry": []},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(wg_core, "MEMORY_DIR", proj / "memory")
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", proj)
    monkeypatch.setattr(pt, "_ensure_state", lambda sid, *a, **k: wg_core.read_state(sid))
    monkeypatch.setattr(pt, "write_state", lambda sid, st: wg_core.write_state(sid, st))
    monkeypatch.setattr(pt, "WORKFLOW_DIR", wg_core.WORKFLOW_DIR)
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)

    def _post(tool, tool_input, tool_use_id, failed=False):
        ev = {"tool_name": tool, "tool_input": tool_input, "session_id": SID, "cwd": str(proj),
              "transcript_path": world["tp"], "tool_use_id": tool_use_id}
        with pytest.raises(SystemExit):
            if failed:
                pt.handle_post_tool_use_failure({**ev, "error": "Exit code 1\nTraceback ..."}, {"docdrift": {"enabled": False}})
            else:
                pt.handle_post_tool_use({**ev, "tool_response": {"stdout": "", "stderr": ""}}, {"docdrift": {"enabled": False}})
    return _post


def _pre(w, tool, tool_input, tool_use_id):
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": tool, "tool_input": tool_input, "session_id": SID, "cwd": str(w["proj"]),
                                 "transcript_path": w["tp"], "tool_use_id": tool_use_id}, {})
    return w["outputs"][-1]


def _snaps():
    d = Path(wg_core.WORKFLOW_DIR) / "judge-card-snap"
    return sorted(p.name for p in d.glob("*.json")) if d.is_dir() else []


def _pending_cards():
    return [e["card"] for e in (wg_core.read_state(SID) or {}).get("judge_card_undeclared") or []]


def _append(path, text="- [臨] 腳本補一條\n"):
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)


def _interp_round(w, post, cmd, *, write=True, failed=False, tid="toolu_interp_1"):
    """一輪直譯器指令：PreToolUse 放行並記雜湊 → （模擬腳本寫卡）→ PostToolUse 比對。"""
    ti = {"command": cmd}
    out = _pre(w, "Bash", ti, tid)
    assert not _jc_deny(out), out
    assert _snaps(), "前置：這條指令會跑直譯器，PreToolUse 要記雜湊"
    if write:
        _append(w["bound"])
    post("Bash", ti, tid, failed=failed)
    assert not _snaps(), "比完要刪快照"


def test_python_script_editing_bound_card_without_declaration_blocks_next_call(world, post):
    """python 腳本自己開檔寫綁 E99 的卡（寫入目標解析不到）→ 事後比對留帳 undeclared，下一個呼叫擋。"""
    _interp_round(world, post, "python tools/fix_cards.py")
    assert _pending_cards() == ["測試判準卡-綁e99"]
    ev = _log(world)
    assert [(e["event"], e["channel"], e["card"], e["entry"], e["allowed"]) for e in ev] == \
        [("undeclared", "interpreter", "測試判準卡-綁e99", ["E99"], False)]
    out = _run(world, "Edit", _edit(world, world["plain"]))       # 下一個呼叫（改的是別張沒綁的卡）也擋
    assert _jc_deny(out), out
    r = _reason(out)
    assert "直譯器改了綁 Entry 的判準卡" in r and f"✗ (jc) {RULE}：" in r and "改判準卡｜測試判準卡-綁e99：<" in r
    assert _log(world)[-1]["event"] == "denied_late"


def test_late_declaration_clears_pending_and_is_logged(world, post):
    _interp_round(world, post, "python tools/fix_cards.py")
    decl = "改判準卡｜測試判準卡-綁e99：使用者說 E99 的判準寫反了，腳本批次修正"
    _add(world, _assistant("text", decl))
    out = _run(world, "Edit", _edit(world, world["plain"]))
    assert not _jc_deny(out), out
    assert _pending_cards() == []
    late = [e for e in _log(world) if e["event"] == "declared_late"]
    assert [(e["card"], e["line"], e["channel"]) for e in late] == [("測試判準卡-綁e99", decl, "interpreter")]


def test_declaration_in_same_interpreter_command_is_logged_not_pending(world, post):
    cmd = "# 改判準卡｜測試判準卡-綁e99：使用者要的判準改法，腳本一次改\npython tools/fix_cards.py"
    _interp_round(world, post, cmd)
    assert _pending_cards() == []
    assert [(e["event"], e["channel"], e["via"]) for e in _log(world)] == [("declared", "interpreter", "tool_input")]


def test_failed_command_still_compared(world, post):
    """指令非零結束：Claude Code 只送 PostToolUseFailure，前段已經寫進卡的改動照樣比到。"""
    _interp_round(world, post, "python tools/fix_cards.py && pytest -q", failed=True)
    assert _pending_cards() == ["測試判準卡-綁e99"]


def test_unparsed_writer_naming_card_is_hashed(world, post):
    """不是直譯器、寫入目標也解析不到，但指令字面點了卡的檔名 → 照樣記雜湊比對。"""
    _interp_round(world, post, "mytool --in-place memory/版控/測試判準卡-綁e99.md")
    assert _pending_cards() == ["測試判準卡-綁e99"]


def test_interpreter_run_not_touching_cards_leaves_no_log(world, post):
    _interp_round(world, post, "python -m pytest -q tests", write=False)
    assert _pending_cards() == [] and _log(world) == []


@pytest.mark.parametrize("cmd", ["pypy3 tools/fix_cards.py", "./tools/fix_cards.py --all", "uv run tools/fix_cards.py"],
                         ids=["pypy3", "direct-script", "uv-run"])
def test_other_interpreter_launches_are_hashed(world, post, cmd):
    """codex 007：清單外的直譯器（pypy3）、直接跑腳本檔、`uv run 腳本` 也記雜湊，改了卡照樣欠帳。"""
    _interp_round(world, post, cmd)
    assert _pending_cards() == ["測試判準卡-綁e99"]


def test_plain_command_takes_no_snapshot(world, post):
    """不跑直譯器、也沒點到卡名的指令不記雜湊（別每次全掃）。前置：索引裡真的有綁 Entry 的卡。"""
    import wg_judge_card as jc
    assert jc.data_root_cards() == {str(world["proj"] / "memory/版控/測試判準卡-綁e99.md"): ["E99"]}
    out = _pre(world, "Bash", {"command": "ls -la src"}, "toolu_plain")
    assert not _jc_deny(out) and _snaps() == []
    assert HASH_RULE in rr.RULES


def test_parse_declarations_names_and_paths():
    d = rr.parse_judge_card_decls("# 改判準卡｜`a-卡`、C:\\x\\memory\\b-卡.md：理由一\n改判準卡| c-卡: 理由二")
    assert [x["names"] for x in d] == [["a-卡", "C:\\x\\memory\\b-卡.md"], ["c-卡"]]
    assert [x["reason"] for x in d] == ["理由一", "理由二"]
    assert rr.judge_card_name_hits("C:\\x\\memory\\B-卡.md", "b-卡") and not rr.judge_card_name_hits("E29", "b-卡")
    assert RULE in rr.RULES
