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


@pytest.mark.parametrize("name", ["app.py", "README.md"])
def test_code_and_markdown_are_not_asked(world, name):
    out = _run(world, path=world["proj"] / name)
    assert not _df_deny(out)
    assert not _log(world), "副檔名不在清單：連 exempt 都不記"


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


def test_broken_state_blocks(world):
    wg_core.state_file_path(SID).write_text("{broken", encoding="utf-8")
    out = _run(world)
    assert _df_deny(out) and "判不了" in _reason(out)
    assert _log(world)[-1]["event"] == "error"
