"""verify_data_file_ask.py：動使用者資料檔要先宣告（規則 USER_DATA_FILE_NEEDS_DECLARATION，hooks/wg_data_file.py）端到端。

正例：使用者既有的 settings.json（非本 session 建、原話沒點名）Edit 沒宣告 → 擋（規則名、四件證據、入口行範例）；
回覆文字宣告 → 放行、留帳 declared、同 session 第二次不再擋；宣告放下一個 Bash 開頭 # 註解（管道二）→ 放行；
宣告路徑寫成別的檔 → 照擋點名路徑不符；冒號後只有標點或佔位 → 擋；使用者原話點名 → exempt (d)；
本 session Write 新建（PostToolUse 記 created_files）再 Edit → exempt (c)；.py／.md 不管；enabled=false 整條不管；
驗收題 B 實跑材料（wave1-kit/results/2026-10-20/B-1：state 的路徑寫法、使用者原話、git diff 的改動）→ 擋。
live 檔全 monkeypatch：WORKFLOW_DIR（state 落 tmp）、GUARD_LOG_DIR（守門紀錄落 tmp）。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_data_file_ask.py
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
import wg_data_file as df  # noqa: E402
from handlers import pre_tool_use as ptu  # noqa: E402

SID = "sess-datafile-0001"
RULE = "USER_DATA_FILE_NEEDS_DECLARATION"
# 驗收題 B 第 1 段：使用者原話（state turn_prompts 原文）與 settings.json 改前改後（git.md diff）
B1_PROMPT = "report 的 cli 加一個 `--format csv`：輸出第一列是 name,amount，之後每列一筆，小數位照設定檔。要有測試。"
B1_OLD = '{"currency": "TWD", "tz": "Asia/Taipei", "decimals": 0,}'
B1_NEW = '{"currency": "TWD", "tz": "Asia/Taipei", "decimals": 0}'
DECL = "動資料檔｜settings.json：修掉多逗號讓 cli 讀得到；幣別會從預設 USD 變成檔內的 TWD"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """假專案 qb-report（settings.json 已存在）＋ tmp workflow／Logs；回 dict(proj, tp, outputs, logs)。"""
    proj = tmp_path / "w1" / "qb-report"
    proj.mkdir(parents=True)
    (proj / "settings.json").write_text(B1_OLD + "\n", encoding="utf-8")
    (proj / "app.py").write_text("x = 1\n", encoding="utf-8")
    (proj / "README.md").write_text("# r\n", encoding="utf-8")
    wf = tmp_path / "wf"
    wf.mkdir()
    logs = tmp_path / "Logs"
    monkeypatch.setenv("WG_TEMP_RULES", "off")
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
                              "recent_user_prompts": [B1_PROMPT], "turn_prompts": [B1_PROMPT]})
    tp = tmp_path / "t.jsonl"
    _transcript(tp, [_user(B1_PROMPT), _assistant("text", "先看 report 的設定怎麼讀")])
    return {"proj": proj, "tp": str(tp), "outputs": outputs, "logs": logs}


def _user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def _assistant(kind, payload):
    block = {"text": {"type": "text", "text": payload},
             "thinking": {"type": "thinking", "thinking": payload},
             "tool_use": {"type": "tool_use", "name": "Bash", "input": {"command": payload}}}[kind]
    return {"type": "assistant", "message": {"content": [block]}}


def _transcript(tp, entries):
    Path(tp).write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")


def _run(w, tool="Edit", path=None, config=None, **extra):
    path = str(path or (w["proj"] / "settings.json"))
    tool_input = {"file_path": path, "old_string": B1_OLD, "new_string": B1_NEW} if tool == "Edit" else {"file_path": path, **extra}
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": tool, "tool_input": tool_input, "session_id": SID, "cwd": str(w["proj"]),
                                 "transcript_path": w["tp"]}, config or {})
    return w["outputs"][-1]


def _df_deny(out):
    """這次被 DataFileAsk 擋了沒（別的閘——OverviewHub、NeedGoal——擋的不算）。"""
    hso = (out or {}).get("hookSpecificOutput") or {}
    return hso.get("permissionDecision") == "deny" and "[Guardian:DataFileAsk]" in hso.get("permissionDecisionReason", "")


def _reason(out):
    return ((out or {}).get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")


def _log(w):
    p = w["logs"] / "guard-data_file.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def test_existing_settings_json_without_declaration_is_denied(world):
    out = _run(world)
    assert _df_deny(out), out
    r = _reason(out)
    assert f"✗ (df) {RULE}：" in r
    for fact in ("(a) 不是程式檔", "(b) 使用者既有", "(c) 非本 session 建", "(d) 需求沒點名"):
        assert fact in r, fact
    assert "入口行範例：動資料檔｜settings.json：" in r and "AskUserQuestion" in r and "Bash 開頭 `#` 註解" in r
    assert [e["event"] for e in _log(world)] == ["denied"]


def test_b1_real_input_from_acceptance_run_is_denied(world):
    """驗收題 B 第 1 段：Windows 反斜線路徑（state modified_files 原樣寫法）、使用者原話只說「小數位照設定檔」沒點名檔。"""
    path = str(world["proj"]) + "\\settings.json"
    assert "\\" in path and wg_core.user_typed_prompts([B1_PROMPT]) == [B1_PROMPT]    # 前置：原話認得到、只是沒點名
    out = _run(world, path=path)
    assert _df_deny(out), out


def test_text_declaration_allows_and_second_edit_uses_state(world):
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("text", DECL)])
    assert not _df_deny(_run(world))
    ev = _log(world)
    assert ev[-1]["event"] == "declared" and ev[-1]["via"] == "text"
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("text", "繼續")])     # 第二次：transcript 已沒有宣告，靠 state
    assert not _df_deny(_run(world))
    assert _log(world)[-1] == {**_log(world)[-1], "event": "declared", "via": "state"}


def test_bash_comment_declaration_allows(world):
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("tool_use", f"# {DECL}\necho ok")])
    assert not _df_deny(_run(world))
    assert _log(world)[-1]["via"] == "tool_input"


def test_declaration_for_other_file_is_denied_and_named(world):
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("text", "動資料檔｜other.json：要改它")])
    out = _run(world)
    assert _df_deny(out) and "宣告的是 other.json，要改的是 settings.json" in _reason(out)


@pytest.mark.parametrize("why", ["", "。。", "<為什麼要動它、動了使用者會看到什麼>"])
def test_declaration_without_reason_is_denied(world, why):
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("text", f"動資料檔｜settings.json：{why}")])
    out = _run(world)
    assert _df_deny(out) and "冒號後沒有理由" in _reason(out)


def test_prompt_naming_the_file_is_exempt(world):
    asked = "把 settings.json 的多逗號修掉"
    st = wg_core.read_state(SID)
    st["recent_user_prompts"] = [asked]
    st["turn_prompts"] = [asked]
    wg_core.write_state(SID, st)
    assert not _df_deny(_run(world))
    ev = _log(world)[-1]
    assert ev["event"] == "exempt" and ev["why"].startswith("(d) 不成立")


def test_naming_after_earlier_declaration_is_exempt_not_state(world):
    """第三跑 C4：本 session 先宣告動過 settings.json（state 記著），使用者之後在原話點名它——帳記點名豁免（exempt，帶原話片段），
    不是沿用舊宣告（舊碼先看 state、命中就放，點名那條走不到）。"""
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("text", DECL)])
    assert not _df_deny(_run(world)) and _log(world)[-1]["via"] == "text", "前置：舊宣告記進 state"
    asked = "補一個：小數位放進 settings.json，之後改設定檔就好。"
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("text", "好"), _user(asked)])
    assert not _df_deny(_run(world))
    ev = _log(world)[-1]
    assert ev["event"] == "exempt" and "via" not in ev and ev["why"].startswith("(d) 不成立")
    assert "settings.json" in ev["quote"] and ev["quote"] in asked, "點名對得到原話"


def test_prompt_naming_only_in_transcript_counts(world):
    """state 只留近 5 則：較早的原話在 transcript 裡點名也算（本 session 所有使用者原話）。"""
    _transcript(world["tp"], [_user("先記住：settings.json 等下要改"), _user(B1_PROMPT), _assistant("text", "好")])
    assert not _df_deny(_run(world))
    assert _log(world)[-1]["why"].startswith("(d) 不成立")


def test_session_created_file_is_exempt(world):
    """本 session 先 Write 建 new.json（呼叫前不存在 → (b) 不成立）；PostToolUse 記 created_files；再 Edit → (c) 不成立。"""
    new = world["proj"] / "new.json"
    assert not new.exists()
    assert not _df_deny(_run(world, tool="Write", path=new, content="{}"))
    assert _log(world)[-1]["why"].startswith("(b) 不成立")
    new.write_text("{}", encoding="utf-8")
    st = wg_core.read_state(SID)
    assert df.note_created(st, "Write", str(new), {"type": "create", "filePath": str(new)})
    wg_core.write_state(SID, st)
    out = _run(world, path=new)
    assert not _df_deny(out), out
    assert _log(world)[-1]["why"].startswith("(c) 不成立")


def test_note_created_only_for_new_files():
    st = {}
    assert not df.note_created(st, "Write", "C:/p/a.json", {"type": "update"})       # 覆寫既有檔不算新建
    assert not df.note_created(st, "Write", "C:/p/a.json", "ok")                     # 判不出就不記（之後寧可多問）
    assert not df.note_created(st, "Edit", "C:/p/a.json", {"type": "create"})
    assert df.note_created(st, "Write", "C:\\P\\a.json", {"type": "create"})
    assert not df.note_created(st, "Write", "c:/p/A.json", {"type": "create"})       # 同一個檔不重記
    assert st["created_files"] == ["c:/p/a.json"]


def test_post_tool_use_records_created_file(world, monkeypatch):
    """接線：handlers/post_tool_use 收到 Write type=create → state created_files 有這個檔。"""
    from handlers import post_tool_use as post
    new = world["proj"] / "made.json"
    new.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(post, "_emit_post_tool_output", lambda *a, **k: None)
    post.handle_post_tool_use({"session_id": SID, "cwd": str(world["proj"]), "tool_name": "Write",
                               "tool_input": {"file_path": str(new), "content": "{}"},
                               "tool_response": {"type": "create", "filePath": str(new)},
                               "transcript_path": world["tp"]}, {})
    assert df._rr.canon_path(str(new)) in wg_core.read_state(SID).get("created_files", [])


@pytest.mark.parametrize("name", ["app.py"])
def test_code_and_markdown_are_not_asked(world, name):
    out = _run(world, path=world["proj"] / name)
    assert not _df_deny(out)
    assert not _log(world), "副檔名不在清單：連 exempt 都不記"


# ─── .md 文件（原設計者 10-21 裁「納」：題 A′ AI 沒被要求就刪了 defects.md 一列、改了 README，閘沒問）───

def test_existing_readme_md_without_declaration_is_denied(world):
    out = _run(world, path=world["proj"] / "README.md")
    assert _df_deny(out), out
    assert "README.md" in _reason(out) and "(a) 不是程式檔：副檔名 .md 在資料／設定清單" in _reason(out)


def test_existing_md_with_declaration_allowed(world):
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("text", "動資料檔｜README.md：使用者要的 --plain 用法要寫進跑法；可見影響：README 多一行")])
    assert not _df_deny(_run(world, path=world["proj"] / "README.md"))
    assert _log(world)[-1]["event"] == "declared"


def test_shell_deleting_line_in_existing_defects_md_is_denied(world):
    (world["proj"] / "defects.md").write_text("| cli.py | 參數手切 |\n| catalog.py | 價格寫死 |\n", encoding="utf-8")
    out = _shell(world, "sed -i '/cli.py.*參數手切/d' defects.md")
    assert _df_deny(out) and "defects.md" in _reason(out)


def test_session_created_md_and_system_doc_md_not_asked(world):
    new = world["proj"] / "NOTES.md"
    assert not _df_deny(_run(world, tool="Write", path=new, content="# n\n"))           # 呼叫前不存在：新建
    for rel in ("_AIDocs/_CHANGELOG.md", "memory/工作流/x.md", ".claude/overview-map.md"):
        p = world["proj"] / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# x\n", encoding="utf-8")
        assert not _df_deny(_run(world, path=p)), rel                                  # 系統文件目錄的 .md 照既有規則不問
    assert all(not e["path"].endswith(("_CHANGELOG.md", "x.md", "overview-map.md")) for e in _log(world))
    j = world["proj"] / "memory" / "_meta" / "phrases.json"
    j.parent.mkdir(parents=True, exist_ok=True)
    j.write_text("{}", encoding="utf-8")
    assert _df_deny(_run(world, path=j))                                                 # 同目錄的 json 照舊要宣告


def test_disabled_skips_everything(world):
    out = _run(world, config={"guard": {"data_file_ask": {"enabled": False}}})
    assert not _df_deny(out) and not _log(world)


def test_extensions_list_from_config_replaces_default(world):
    cfg = {"guard": {"data_file_ask": {"extensions": [".md"]}}}
    assert _df_deny(_run(world, path=world["proj"] / "README.md", config=cfg))
    assert not _df_deny(_run(world, config=cfg))


@pytest.mark.parametrize("asked", ["請修改「備份設定.json」", "請修改備份設定.json"])
def test_longer_unicode_name_is_not_naming(world, asked):
    """codex BLOCK 1：原話點的是「備份設定.json」，要改的是 設定.json → 不算點名，照擋。"""
    target = world["proj"] / "設定.json"
    target.write_text("{}", encoding="utf-8")
    st = wg_core.read_state(SID)
    st["recent_user_prompts"] = [asked]
    wg_core.write_state(SID, st)
    assert _df_deny(_run(world, path=target))


def test_created_files_are_never_evicted():
    """codex BLOCK 2：本 session 新建過的檔不能因為清單上限被擠掉，否則 AI 自己建的檔會被當成使用者既有。"""
    st = {}
    for i in range(260):
        df.note_created(st, "Write", f"C:/p/f{i}.json", {"type": "create"})
    assert "c:/p/f0.json" in st["created_files"]


@pytest.mark.parametrize("why", ["修正 <幣別> 標籤，讓報表能正確讀取", "通貨の設定を直す"])
def test_reason_with_tag_or_other_language_is_a_reason(world, why):
    """codex BLOCK 3＋另問：理由裡引用 XML 標籤、用別的語言寫，都是有理由；只有整段是佔位或只有標點才不算。"""
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("text", f"動資料檔｜settings.json：{why}")])
    assert not _df_deny(_run(world))


def test_tool_input_channel_needs_hash_comment(world):
    """管道二只認工具參數裡 # 開頭的註解行；寫進檔案內容的字樣不算宣告。"""
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("tool_use", f"echo '{DECL}'")])
    assert _df_deny(_run(world))


# ─── Bash／PowerShell 寫入目標（write_paths_from_tool）走同一支判定 ───

def _shell(w, command, tool="Bash", tuid="tu-1"):
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": tool, "tool_input": {"command": command}, "session_id": SID, "tool_use_id": tuid,
                                 "cwd": str(w["proj"]), "transcript_path": w["tp"]}, {})
    return w["outputs"][-1]


@pytest.mark.parametrize("tool,cmd", [("Bash", "sed -i 's/,}/}/' settings.json"),
                                      ("PowerShell", "Set-Content -Path settings.json -Value '{}'")])
def test_shell_write_to_existing_data_file_is_denied(world, tool, cmd):
    from wg_core import write_paths_from_tool
    assert write_paths_from_tool(tool, {"command": cmd}, str(world["proj"])) == [str(world["proj"] / "settings.json")]  # 前置：目標算得出
    out = _shell(world, cmd, tool)
    assert _df_deny(out) and f"✗ (df) {RULE}：" in _reason(out)


@pytest.mark.parametrize("tool,cmd", [("Bash", "sed -i 's/,}/}/' settings.json"),
                                      ("PowerShell", "Set-Content -Path settings.json -Value '{}'")])
def test_shell_write_with_declaration_in_same_command_allows(world, tool, cmd):
    """宣告寫在同一條指令開頭的 # 註解：PreToolUse 當下這則工具呼叫不一定已寫進 transcript，指令本身也要認。"""
    out = _shell(world, f"# {DECL}\n{cmd}", tool)
    assert not _df_deny(out), out
    assert _log(world)[-1]["event"] == "declared" and _log(world)[-1]["via"] == "tool_input"


def test_shell_creating_new_file_is_not_asked_and_later_edit_is_exempt(world, monkeypatch):
    """`echo x > new.json` 新建 → (b) 不成立；PostToolUse 確認檔真的出現 → created_files；之後 Edit 它 → (c) 不成立。"""
    from handlers import post_tool_use as post
    monkeypatch.setattr(post, "_emit_post_tool_output", lambda *a, **k: None)
    new = world["proj"] / "new.json"
    assert not new.exists()
    assert not _df_deny(_shell(world, "echo x > new.json", tuid="tu-new"))
    assert _log(world)[-1]["why"].startswith("(b) 不成立")
    new.write_text("x\n", encoding="utf-8")
    post.handle_post_tool_use({"session_id": SID, "cwd": str(world["proj"]), "tool_name": "Bash", "tool_use_id": "tu-new",
                               "tool_input": {"command": "echo x > new.json"}, "tool_response": {"stdout": "", "stderr": ""},
                               "transcript_path": world["tp"]}, {})
    assert df._rr.canon_path(str(new)) in wg_core.read_state(SID).get("created_files", [])
    assert not _df_deny(_run(world, path=new))
    assert _log(world)[-1]["why"].startswith("(c) 不成立")


def test_shell_existing_file_overwrite_is_not_recorded_as_created(world):
    """覆寫既有檔（`>` 寫到已存在的 settings.json）不能被記成本 session 建，否則之後改它就不問了。"""
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("text", DECL)])
    assert not _df_deny(_shell(world, "echo {} > settings.json", tuid="tu-ow"))
    st = wg_core.read_state(SID)
    assert "tu-ow" not in (st.get("data_file_pending_new") or {})
    assert df.confirm_shell_created(st, "tu-ow") is False
    assert df._rr.canon_path(str(world["proj"] / "settings.json")) not in st.get("created_files", [])


def test_shell_two_data_files_one_declared_names_the_other(world):
    (world["proj"] / "rates.csv").write_text("a,1\n", encoding="utf-8")
    out = _shell(world, "# " + DECL + "\nsed -i 's/,}/}/' settings.json && sed -i 's/1/2/' rates.csv")
    assert _df_deny(out)
    r = _reason(out)
    assert "要改的是 rates.csv" in r and r.count("✗ (df)") == 1, "只擋沒宣告的 rates.csv，settings.json 對上了"
    assert "入口行範例：動資料檔｜rates.csv：" in r and "入口行範例：動資料檔｜settings.json" not in r


def test_shell_without_data_file_targets_is_untouched(world):
    assert not _df_deny(_shell(world, "sed -i 's/1/2/' app.py && cat settings.json"))
    assert not _log(world)


# ─── 子代理：對話紀錄在 <sid>/subagents/agent-<agent_id>.jsonl，主 session 是同層的 <sid>.jsonl ───

AGENT = "ae3c716a6fc9ec36b"


def _agent_world(w):
    """把 fixture 的 transcript 擺成 Claude Code 的真實佈局：主檔 <sid>.jsonl、子代理檔 <sid>/subagents/agent-<id>.jsonl。"""
    main = Path(w["tp"]).with_name(f"{SID}.jsonl")
    agent = main.with_suffix("") / "subagents" / f"agent-{AGENT}.jsonl"
    agent.parent.mkdir(parents=True)
    return main, agent


def _agent_run(w, tp):
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": "Edit", "session_id": SID, "agent_id": AGENT, "cwd": str(w["proj"]),
                                 "transcript_path": str(tp), "tool_input": {"file_path": str(w["proj"] / "settings.json"),
                                                                            "old_string": B1_OLD, "new_string": B1_NEW}}, {})
    return w["outputs"][-1]


def test_subagent_declaration_in_its_own_transcript_is_seen(world):
    """hook 給主檔時：子代理寫在自己回覆裡的宣告也要認得到（子代理不能問使用者，看不到就擋到底）。"""
    main, agent = _agent_world(world)
    _transcript(main, [_user(B1_PROMPT), _assistant("text", "派子代理去改報表")])
    _transcript(agent, [_user("改 report，必要時修資料檔"), _assistant("text", DECL)])
    assert not _df_deny(_agent_run(world, main))
    assert _log(world)[-1]["event"] == "declared"


def test_subagent_dispatch_prompt_is_not_user_words(world):
    """hook 給子代理檔時：子代理檔裡的 user 訊息是 AI 寫的派工 prompt，點名檔名也不算使用者原話；原話從主檔與 state 取。"""
    main, agent = _agent_world(world)
    _transcript(main, [_user(B1_PROMPT), _assistant("text", "派子代理")])
    _transcript(agent, [_user("把 settings.json 的多逗號修掉"), _assistant("text", "好")])
    out = _agent_run(world, agent)
    assert _df_deny(out), out
    assert "(d) 需求沒點名" in _reason(out)


def test_subagent_declaration_seen_when_hook_gives_agent_transcript(world):
    main, agent = _agent_world(world)
    _transcript(main, [_user(B1_PROMPT)])
    _transcript(agent, [_user("改 report"), _assistant("text", DECL)])
    assert not _df_deny(_agent_run(world, agent))


def test_broken_state_blocks(world):
    wg_core.state_file_path(SID).write_text("{broken", encoding="utf-8")
    out = _run(world)
    assert _df_deny(out) and "判不了" in _reason(out)
    assert _log(world)[-1]["event"] == "error"
