"""verify_judge_card_declare.py：改判準卡要先宣告（規則 JUDGE_CARD_CHANGE_NEEDS_DECLARATION，裁定 #53，hooks/wg_judge_card.py）端到端。

全部走 handlers.pre_tool_use.handle_pre_tool_use 真入口：
只留帳不擋：每次改綁 Entry 的判準卡都放行，帳上記 undeclared（沒宣告）或 declared（含宣告行與管道）。
- 端到端：C-1 真事件（fixtures/gate006/c1_judge_card_events.json：AI 用 atom_write mode=append 改綁 E22／E29 的卡）
  照原樣重播 → 放行、帳記 undeclared；補一行宣告 → 帳記 declared。卡用 repo 裡那張真卡（唯讀，閘不寫檔）。
- MCP 其他出口：atom_edit_meta、atom_retire 改同一張也留帳；atom_write mode=create 不管（不是改既有卡）。
- 檔案出口：Edit 綁 Entry 的卡沒宣告 → 帳記 undeclared；Bash 指令開頭 `#` 宣告 → declared；沒綁 Entry 的卡 → 不留帳。
- 宣告格式：只寫 Entry 代號、理由留佔位、宣告字樣只寫在卡片內容（工具參數非註解行）都不算宣告。
- 不靠 settings.json：三個 MCP 工具名的事件直接餵 handler 都走到本閘。
- 直譯器自己開檔寫卡不管（JUDGE_CARD_HASH_CATCHES_INTERPRETER 已拔除，案例在 verify_pull_tool_gates.py）。
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


def test_c1_replay_mcp_append_without_declaration_is_logged_not_denied(world):
    """C-1 原樣重播：AI 沒宣告就 atom_write append 到判它的 E29 卡 → 放行，帳記 undeclared（誰改了哪張量尺看得到）。"""
    path = _real_c1_card()
    out = _run(world, C1["tool_name"], C1["tool_input"])
    assert not _jc_deny(out), out
    ev = _log(world)
    assert [(e["event"], e["card"], e["entry"], e["allowed"]) for e in ev] == [("undeclared", C1_STEM, ["E22", "E29"], True)]
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


def test_mcp_edit_meta_and_retire_on_bound_card_are_logged(world):
    _real_c1_card()
    out = _run(world, "mcp__workflow-guardian__atom_edit_meta", {"atom_name": C1_STEM, "scope": "global", "entry": []})
    assert not _jc_deny(out), out
    out = _run(world, "mcp__workflow-guardian__atom_retire", {"atom_name": C1_STEM, "scope": "global", "reason": "過時"})
    assert not _jc_deny(out), out
    assert [e["tool"].rsplit("__", 1)[-1] for e in _log(world)] == ["atom_edit_meta", "atom_retire"]


@pytest.mark.parametrize("tool, make_input", [
    ("mcp__workflow-guardian__atom_write", lambda w: {**C1["tool_input"], "mode": "replace"}),
    ("Write", lambda w: {"file_path": str(w["bound"]), "content": "# 卡\n\n- Entry: E99\n\n## 知識\n\n- [臨] 整張改寫\n"}),
    ("PowerShell", lambda w: {"command": f"Add-Content -Path '{w['bound']}' -Value '- [臨] 補一條'"}),
], ids=["mcp-replace", "write", "powershell"])
def test_other_exits_without_declaration_are_logged(world, tool, make_input):
    """其餘出口（atom_write replace、Write 整檔改寫、PowerShell 寫入）沒宣告一樣放行、一樣留帳 undeclared。"""
    if tool.startswith("mcp__"):
        _real_c1_card()
    out = _run(world, tool, make_input(world))
    assert not _jc_deny(out), out
    assert [e["event"] for e in _log(world)] == ["undeclared"]


def test_mcp_create_is_not_a_change_of_existing_card(world):
    _real_c1_card()
    out = _run(world, C1["tool_name"], {**C1["tool_input"], "mode": "create"})
    assert not _jc_deny(out) and _log(world) == []


def test_edit_bound_card_without_declaration_is_logged(world):
    out = _run(world, "Edit", _edit(world))
    assert not _jc_deny(out), out
    assert [(e["event"], e["card"], e["entry"]) for e in _log(world)] == [("undeclared", "測試判準卡-綁e99", ["E99"])]


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
    _run(world, "Edit", _edit(world))
    assert [e["event"] for e in _log(world)] == ["undeclared"]


def test_declaration_written_inside_card_content_does_not_count(world):
    """宣告字樣只出現在工具參數的內容裡（不是 `#` 註解行）＝在卡上寫字，不是對使用者宣告。"""
    _add(world, _assistant("tool_use", {"title": "x", "knowledge": ["改判準卡｜測試判準卡-綁e99：自己覺得要改"]},
                           tool="mcp__workflow-guardian__atom_write"))
    _run(world, "Edit", _edit(world))
    assert [e["event"] for e in _log(world)] == ["undeclared"]


def test_disabled_config_skips_gate(world):
    out = _run(world, "Edit", _edit(world), config={"guard": {"judge_card_declare": {"enabled": False}}})
    assert not _jc_deny(out) and _log(world) == []


def test_handler_routes_three_mcp_tools_without_settings(world):
    """不靠 settings，直接把三個 MCP 工具名的事件餵給 handler，每個都要走到改判準卡閘（帳上有它的一筆），不會掉進其他分支。"""
    _real_c1_card()
    for name, ti in (("atom_write", C1["tool_input"]), ("atom_edit_meta", {"atom_name": C1_STEM, "scope": "global"}),
                     ("atom_retire", {"atom_name": C1_STEM, "scope": "global", "reason": "x"})):
        assert not _jc_deny(_run(world, f"mcp__workflow-guardian__{name}", ti)), name
    assert [e["tool"].rsplit("__", 1)[-1] for e in _log(world)] == ["atom_write", "atom_edit_meta", "atom_retire"]


# ─── 直譯器自己開檔寫卡（JUDGE_CARD_HASH_CATCHES_INTERPRETER）已拔除 ───
# PreToolUse 不再替判準卡記雜湊、PostToolUse 不再比對（每次跑直譯器都要全掃卡、只能留帳）；
# 拔除後的案例（不記快照、改卡不擋）在 verify_pull_tool_gates.py。


def test_parse_declarations_names_and_paths():
    d = rr.parse_judge_card_decls("# 改判準卡｜`a-卡`、C:\\x\\memory\\b-卡.md：理由一\n改判準卡| c-卡: 理由二")
    assert [x["names"] for x in d] == [["a-卡", "C:\\x\\memory\\b-卡.md"], ["c-卡"]]
    assert [x["reason"] for x in d] == ["理由一", "理由二"]
    assert rr.judge_card_name_hits("C:\\x\\memory\\B-卡.md", "b-卡") and not rr.judge_card_name_hits("E29", "b-卡")
    assert RULE in rr.RULES
