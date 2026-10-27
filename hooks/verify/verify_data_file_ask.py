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
import wg_release_rules as rr  # noqa: E402
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
    for fact in ("(a) 不是程式檔", "(b) 使用者既有", "(c) 這個 session 沒建過它", "(d) 需求沒點名"):
        assert fact in r, fact
    assert "入口行範例：動資料檔｜settings.json：" in r and "AskUserQuestion" in r and "開頭的 `#` 註解" in r
    assert [e["event"] for e in _log(world)] == ["denied"]


def test_block_message_keeps_edit_write_not_bash_writes(world):
    """規則 DECL_HINT_KEEPS_EDIT_TOOLS（補題第一版第 2 回合）：舊擋訊息「或寫成 Bash 指令開頭的 # 註解」「放…下一個 Bash 開頭
    # 註解」被讀成改用 Bash 寫檔，之後全程 python -c 改檔、改檔清單整個 session 是空的。擋訊息要寫明宣告完照常用 Edit／Write、
    不要改用 Bash 寫檔，註解只放在不寫檔的指令上。"""
    r = _reason(_run(world))
    assert "照常用 Edit／Write" in r and "不要改用 Bash／PowerShell 寫檔" in r and "不寫檔的 Bash／PowerShell 指令" in r
    for old in ("或寫成 Bash／PowerShell 指令開頭的 `#` 註解", "下一個 Bash 開頭"):
        assert old not in r, old


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


# ─── NEGATED_MENTION_IS_NOT_NAMING／DATA_FILE_DECL_VOIDED_BY_LATER_MENTION ─────────────────────
# 第五跑 C-1 使用者原話（第 4、5 回合）：先叫放進 shop.json，後來翻案「折扣碼不要放 shop.json」、但 shop.json 留門檻改動
C5_T4 = "補一個：折扣碼不要寫死在程式裡，放進 config/shop.json，之後要加新碼改設定檔就好。"
C5_T5 = "不對，折扣碼不要放 shop.json，改成另外開一個新檔 config/promos.json 放；shop.json 只留門檻那一個改動。"


def _shop(w):
    p = w["proj"] / "config" / "shop.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(B1_OLD + "\n", encoding="utf-8")
    return p


def _said(w, *prompts, extra=()):
    st = wg_core.read_state(SID)
    st["recent_user_prompts"] = list(prompts)
    st["turn_prompts"] = list(prompts[-1:])
    wg_core.write_state(SID, st)
    _transcript(w["tp"], [_user(p) for p in prompts] + list(extra))


@pytest.mark.parametrize("said", [
    "config/shop.json 先不要動，折扣碼放新檔",
    "不要動 shop.json，等我確認",
    "折扣碼不要放 shop.json，放新檔",                 # C5 第 5 回合前半句單獨講
    "shop.json 別碰",
], ids=["right-neg", "left-neg", "c5-first-clause", "bie"])
def test_negated_mention_is_not_naming(world, said):
    """原話提到資料檔、但那一處被否定 → 不算點名，沒宣告照擋（之前字面命中就點名豁免）。前置：同一個檔沒被否定時會豁免。"""
    shop = _shop(world)
    assert rr.prompt_names_file(["把 shop.json 的門檻改成 500"], str(shop)), "前置：一般點名認得到"
    _said(world, said)
    out = _run(world, path=shop)
    assert _df_deny(out), (said, out)
    assert "NEGATED_MENTION_IS_NOT_NAMING" in rr.RULES


@pytest.mark.parametrize("said", [C5_T4, C5_T5], ids=["c5-t4-negation-in-earlier-clause", "c5-t5-second-mention-not-negated"])
def test_unnegated_mention_still_names(world, said):
    """反例（C5 原話）：否定在前一個子句、或同一則另有沒被否定的提及 → 照算點名豁免。"""
    shop = _shop(world)
    _said(world, said)
    assert not _df_deny(_run(world, path=shop))
    assert _log(world)[-1]["event"] == "exempt"


def test_declaration_voided_by_later_negating_prompt(world):
    """宣告動過 settings.json（帳記 state）之後，使用者說「settings.json 先不要動」→ 舊帳作廢、留帳 declared_voided，這次照擋；
    宣告前寫的那行不再算（只認最後一則提到它的原話之後的宣告）。"""
    _said(world, B1_PROMPT, extra=[_assistant("text", DECL)])
    assert not _df_deny(_run(world)) and _log(world)[-1]["via"] == "text", "前置：舊宣告記進 state"
    _said(world, B1_PROMPT, "settings.json 先不要動，等我確認",
          extra=[_assistant("text", DECL), _user("settings.json 先不要動，等我確認"), _assistant("text", "好，先不動")])
    out = _run(world)
    assert _df_deny(out), out
    assert [e["event"] for e in _log(world)][-2:] == ["declared_voided", "denied"]
    assert not any(k.endswith("settings.json") for k in wg_core.read_state(SID).get("data_file_declared") or {})
    _add_line = _assistant("text", "動資料檔｜settings.json：使用者後來說可以改了，重新確認過")    # 翻案之後重新宣告 → 照認
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("text", DECL), _user("settings.json 先不要動，等我確認"), _add_line])
    assert not _df_deny(_run(world)) and _log(world)[-1]["event"] == "declared"


def test_early_naming_overridden_by_later_negation(world):
    """codex 007：早先原話點名「放進 shop.json」，最後一則提到它的原話只有否定（「shop.json 先不要動」）→ 早先的點名不再算。
    前置：只有早先那則時是點名豁免。"""
    shop = _shop(world)
    _said(world, "折扣碼放進 config/shop.json")
    assert not _df_deny(_run(world, path=shop)), "前置：早先那則單獨是點名"
    _said(world, "折扣碼放進 config/shop.json", "等等，shop.json 先不要動，我想一下")
    assert _df_deny(_run(world, path=shop))


def test_subagent_declaration_does_not_survive_later_mention(world, tmp_path):
    """codex 007：子代理先宣告過這個檔，使用者之後在主對話提到它（否定）→ 子代理檔裡的舊宣告不再算（位置對不上主檔、分不出先後）。
    前置：使用者沒提過這個檔時，子代理檔的宣告照認。"""
    main = Path(world["tp"])
    sub_dir = main.with_suffix("") / "subagents"
    sub_dir.mkdir(parents=True)
    _transcript(sub_dir / "agent-a1.jsonl", [_assistant("text", DECL)])
    _transcript(main, [_user(B1_PROMPT), _assistant("text", "交給子代理")])
    from wg_core import transcripts_of
    assert len(transcripts_of(str(main), "a1")[1]) == 2, "前置：子代理呼叫時讀得到子代理檔"

    def _sub_edit():
        ti = {"file_path": str(world["proj"] / "settings.json"), "old_string": B1_OLD, "new_string": B1_NEW}
        with pytest.raises(SystemExit):
            ptu.handle_pre_tool_use({"tool_name": "Edit", "tool_input": ti, "session_id": SID, "cwd": str(world["proj"]),
                                     "transcript_path": str(main), "agent_id": "a1"}, {})
        return world["outputs"][-1]
    assert not _df_deny(_sub_edit()) and _log(world)[-1]["via"] == "text", "前置：使用者沒提過時子代理的宣告照認"
    st = wg_core.read_state(SID)
    st.pop("data_file_declared", None)
    wg_core.write_state(SID, st)
    _said(world, B1_PROMPT, "settings.json 先不要動", extra=[_assistant("text", "好")])
    assert _df_deny(_sub_edit())


def test_later_prompt_not_mentioning_file_keeps_declaration(world):
    """反例：宣告之後的原話沒提到這個檔 → 舊帳照用（via=state），不作廢。"""
    _said(world, B1_PROMPT, extra=[_assistant("text", DECL)])
    assert not _df_deny(_run(world))
    _transcript(world["tp"], [_user(B1_PROMPT), _assistant("text", DECL), _user("繼續，其他照做")])
    assert not _df_deny(_run(world))
    assert _log(world)[-1]["via"] == "state" and "declared_voided" not in [e["event"] for e in _log(world)]
    assert "DATA_FILE_DECL_VOIDED_BY_LATER_MENTION" in rr.RULES


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


def test_broken_state_does_not_block_and_logs(world):
    """state 讀壞＝閘判不了（GATE_SELF_ERROR）：這次不擋，留帳 error。"""
    wg_core.state_file_path(SID).write_text("{broken", encoding="utf-8")
    out = _run(world)
    assert not _df_deny(out)
    assert (_log(world)[-1]["event"], _log(world)[-1]["rule"]) == ("error", "GATE_SELF_ERROR")


# ─── 擋訊息精簡（DENY_TEXT_SLIM）與讀到就先提示（DATA_FILE_READ_HINT）───

def test_deny_text_slim_rule_fix_and_hit_only(world):
    """規則 DENY_TEXT_SLIM：擋訊息第一行「[Guardian:DataFileAsk] 修法：<一句>」、下面是 ✗ 條目（規則名＋證據），整段管道說明不再重送；
    guard.deny_text_slim=false 退回原本的長文字（原處不動）。舊碼只有長文字 → 紅。"""
    slim = _reason(_run(world))
    head, hit = slim.splitlines()[:2]
    assert head.startswith("[Guardian:DataFileAsk] 修法：比這次工具呼叫早一則訊息送出宣告行（入口行範例：動資料檔｜settings.json：")
    assert hit.startswith(f"✗ (df) {RULE}：") and rr.parse_hit_rules(slim) == [("df", RULE)]
    assert "先宣告一行再改" not in slim and "留帳給健檢抽查" not in slim
    old = _reason(_run(world, config={"guard": {"deny_text_slim": False}}))
    body = lambda t: t.split("\n判準卡")[0]                                            # 判準卡另由 CARD_FULL_ONCE_PER_SESSION 管
    assert "先宣告一行再改" in old and len(body(slim)) < len(body(old)) * 0.75, (len(body(slim)), len(body(old)))


def test_slim_deny_caps_long_evidence():
    v = rr.Verdict("R_X", True, "現象", ("短證據", "長" * 300))
    t = rr.slim_deny("Guardian:X", "做某事", [("x", v)])
    assert t.splitlines()[0] == "[Guardian:X] 修法：做某事" and rr.parse_hits(t) == ["x"]
    assert "長" * rr.DENY_EVIDENCE_CAP + "…" in t and "長" * (rr.DENY_EVIDENCE_CAP + 1) not in t and "短證據" in t


@pytest.fixture
def post_read(world, monkeypatch):
    """PostToolUse 讀檔：回這次送給模型的 additionalContext（沒送回空字串）。"""
    from handlers import post_tool_use as post
    sent = []
    monkeypatch.setattr(post, "_emit_post_tool_output", lambda adv, msgs: sent.append("\n".join(adv)))

    def run(tool_input, tool="Read", config=None, **extra):
        sent.clear()
        post.handle_post_tool_use({"session_id": SID, "cwd": str(world["proj"]), "tool_name": tool, "tool_input": tool_input,
                                   "tool_response": {"stdout": "", "stderr": ""} if tool == "Bash" else {},
                                   "transcript_path": world["tp"], **extra}, config or {})
        return "\n".join(sent)
    return run


def test_read_hint_on_first_read_of_data_file(world, post_read):
    """規則 DATA_FILE_READ_HINT：第一次讀到改了會被問的資料檔 → 讀檔結果後附一行宣告格式；同檔再讀不重送；之後的檔只點名「格式同前」；
    程式檔、子代理讀的不提示。判定不動：沒宣告照擋。舊碼讀檔後什麼都不說、第一次改才被擋 → 紅。"""
    first = post_read({"file_path": str(world["proj"] / "settings.json")})
    assert "[Guardian:DataFileAsk] 改 settings.json 要先宣告｜格式：動資料檔｜<路徑>：" in first and "早一則訊息送出" in first
    assert "[Guardian:DataFileAsk]" not in post_read({"file_path": str(world["proj"] / "settings.json")})
    assert "[Guardian:DataFileAsk]" not in post_read({"file_path": str(world["proj"] / "app.py")})
    assert "[Guardian:DataFileAsk]" not in post_read({"file_path": str(world["proj"] / "README.md")}, agent_id="ag-1")
    assert "[Guardian:DataFileAsk] 改 README.md 也要先宣告（格式同前一則提示）" in post_read({"command": "cat README.md"}, tool="Bash")
    assert _df_deny(_run(world))
    assert [e["event"] for e in _log(world)] == ["read_hint", "read_hint", "denied"]


def test_read_hint_skips_named_declared_and_switched_off(world, post_read, monkeypatch):
    """使用者原話點名的、本 session 宣告過的不提示（改它本來就不會被問）；動資料檔閘關掉、v6 總開關關掉都不提示。"""
    (world["proj"] / "rates.csv").write_text("a,1\n", encoding="utf-8")
    (world["proj"] / "app.toml").write_text("x = 1\n", encoding="utf-8")
    st = wg_core.read_state(SID)
    wg_core.write_state(SID, {**st, "recent_user_prompts": [B1_PROMPT, "rates.csv 的匯率要更新"],
                              "data_file_declared": {df._rr.canon_path(str(world["proj"] / "settings.json")): {"line": DECL}}})
    for name in ("rates.csv", "settings.json"):
        assert "[Guardian:DataFileAsk]" not in post_read({"file_path": str(world["proj"] / name)}), name
    assert "[Guardian:DataFileAsk]" not in post_read({"file_path": str(world["proj"] / "app.toml")},
                                                     config={"guard": {"data_file_ask": {"enabled": False}}})
    monkeypatch.setenv("WG_V6", "0")
    assert "[Guardian:DataFileAsk]" not in post_read({"file_path": str(world["proj"] / "app.toml")})
    assert not [e for e in _log(world) if e["event"] == "read_hint"]
