"""verify_aec_said_check.py — 收尾報告「你說」核對與 HUD「你這回合說的原話」。

契約：
  - Python（handlers/aec_said_check.annotate，PostToolUse 收 anti_evasion_report 時呼叫）：每個 goal[i] 加 said_check，
    值只有「本回合／第 N 回合前／派工／對不到／太短不判／判不了」；report["user_said_this_turn"] 存本回合使用者打的原話全文。
    使用者打的字只認主檔的真人訊息與中途插話（queued_command、origin=human），剔系統區塊；AI 回覆、工具結果、背景通知不算。
    兩邊同一套正規化（全形半形、空白換行、清單符號、引號）；said 有省略號就切段、每段都要在同一則找得到。
    讀不到紀錄 → 判不了＋ stderr 一行，hook 照跑；只加記號，不改 severity、守門開關都一樣。
  - HUD：「你說」旁標記號（對不到警示色、第 N 回合前與派工中性、本回合小勾、判不了與太短不判灰字）；
    第一類上方可摺疊區列本回合原話（長的預設收起）；舊報告沒有新欄位照舊畫；使用者原話照樣跳脫。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_aec_said_check.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from handlers import aec_said_check as sc  # noqa: E402
from verify_aec_report_classes import _cards, _NORMAL, _LEGACY, node  # noqa: E402

# ─── 紀錄樣本（形狀照實錄：真人訊息 origin=human、中途插話是 queued_command 附件）────────────────

def _human(text, pid="p0", blocks=False):
    content = [{"type": "text", "text": text}] if blocks else text
    return {"type": "user", "origin": {"kind": "human"}, "promptId": pid, "message": {"role": "user", "content": content}}


def _assistant(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def _queued(text, kind="human"):
    return {"type": "attachment", "attachment": {"type": "queued_command", "origin": {"kind": kind},
                                                 "prompt": [{"type": "text", "text": text}]}}


_TOOL_RESULT = {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "工具輸出裡才有的這一句話"}]}}
_NOTIFY = {"type": "user", "origin": {"kind": "task-notification"}, "message": {"content": "<task-notification>背景任務通知裡的一句話</task-notification>"}}
_PEER = {"type": "user", "origin": {"kind": "peer", "from": "uds:x"},
         "message": {"content": '<cross-session-message from="x">同伴派來的工作說明：把 HUD 改成白話</cross-session-message>'}}

_TURN1 = "我對HUD的內容也老是越寫越偏技術臭，沒有基礎分類"
_TURN2 = "因此我寧可錯殺也不願放過"
_TURN3 = ("<system-reminder>系統提醒才有的一段字</system-reminder>全部按照建議，但我希望\n"
          "1. 這一輪之後沒有再度延展的了\n2. 範圍外看到的問題只報重大")
_INTERJECT = "對了，HUD 那邊也要顯示我打的原話"


def _write(path: Path, recs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")
    return path


def _main_transcript(tmp_path: Path) -> Path:
    return _write(tmp_path / "sess.jsonl", [
        _human(_TURN1, "p1"), _assistant("AI 自己講的一句：要把三類拆開畫"), _TOOL_RESULT,
        _human(_TURN2, "p2", blocks=True), _NOTIFY, _PEER,
        _human(_TURN3, "p3"), _queued(_INTERJECT), _queued("<task-notification>插進來的背景通知內容</task-notification>", "task-notification"),
    ])


def _check(tmp_path, saids, agent_id="", transcript=None):
    tp = transcript if transcript is not None else _main_transcript(tmp_path)
    report = {"goal": [{"said": s} for s in saids]}
    sc.annotate(report, {"transcript_path": str(tp), "agent_id": agent_id})
    return [g["said_check"] for g in report["goal"]], report


def test_found_this_turn_earlier_turns_and_interjection(tmp_path):
    got, report = _check(tmp_path, [
        "這一輪之後沒有再度延展的了",          # 本回合（只抄其中一段）
        _INTERJECT,                           # 本回合中途插話也算本回合
        _TURN2,                               # 1 回合前（區塊形式的真人訊息）
        "越寫越偏技術臭",                       # 2 回合前
    ])
    assert got == ["本回合", "本回合", "第 1 回合前", "第 2 回合前"]
    # 本回合原話：開回合那則＋中途插話，剔系統區塊、保留換行與全文；背景通知不算
    assert report["user_said_this_turn"] == [
        "全部按照建議，但我希望\n1. 這一輪之後沒有再度延展的了\n2. 範圍外看到的問題只報重大", _INTERJECT]


def test_fabricated_and_non_user_text_do_not_count(tmp_path):
    got, _ = _check(tmp_path, [
        "HUD 要直接顯示使用者原話並且每句都核對",   # 捏造
        "要把三類拆開畫",                          # AI 自己講的
        "工具輸出裡才有的這一句話",                  # 工具結果
        "背景任務通知裡的一句話",                    # 背景通知
        "系統提醒才有的一段字",                      # 系統區塊
    ])
    assert got == ["對不到"] * 5


def test_normalization_punct_width_newline_list_quotes(tmp_path):
    got, _ = _check(tmp_path, [
        "全部按照建議,但我希望 1. 這一輪之後沒有再度延展的了",      # 全形逗號→半形、換行→空格、清單符號
        "全部按照建議，但我希望這一輪之後沒有再度延展的了",          # 換行與清單符號整個拿掉
        "「因此我寧可錯殺」也不願放過",                           # 加了引號
        "因此我寧可錯殺\n也不願放過",                              # 自己加換行
        "全部按照建議，但我希望\n１． 這一輪之後",                  # 全形數字與句點的清單符號
        "我對ＨＵＤ的內容也老是越寫越偏",                          # 全形英文字母
        "② 範圍外看到的問題只報重大",                              # 圈號數字當清單符號（使用者那邊是「2.」）
    ])
    assert got == ["本回合", "本回合", "第 1 回合前", "第 1 回合前", "本回合", "第 2 回合前", "本回合"]


def test_ellipsis_segments_each_must_be_found_in_one_message(tmp_path):
    got, _ = _check(tmp_path, [
        "我對HUD的內容…沒有基礎分類",            # 兩段都在同一則
        "沒有基礎分類……我對HUD的內容",          # 順序顛倒也算
        "我對HUD的內容...越寫越偏[…]基礎分類",   # 半形省略與 […]
        "我對HUD的內容…而且全部要重寫",           # 一段是捏造
        "我對HUD的內容…因此我寧可錯殺",           # 兩段在不同則
    ])
    assert got == ["第 2 回合前", "第 2 回合前", "第 2 回合前", "對不到", "對不到"]


def test_too_short(tmp_path):
    # 正規化後算字數（引號、省略號、空格不算）：5 字以下不判，6 字起照比
    got, _ = _check(tmp_path, ["好", "「做」…「對」", "HUD 改", "因此我寧可", "因此我寧可錯", "捏造的六個字"])
    assert got == ["太短不判", "太短不判", "太短不判", "太短不判", "第 1 回合前", "對不到"]


def test_dispatch_subagent_and_peer(tmp_path):
    main = _main_transcript(tmp_path)
    _write(tmp_path / "sess" / "subagents" / "agent-A1.jsonl", [
        {"type": "user", "isSidechain": True, "promptId": "p2",
         "message": {"role": "user", "content": "派工說明：請把收尾報告的你說加上核對記號，只加記號、不擋"}},
        {"type": "user", "isSidechain": True, "message": {"content": "子代理檔裡第二則不是派工"}},
    ])
    got, report = _check(tmp_path, [
        "派工：只加記號、不擋",                 # 派工說明裡找得到
        "請把收尾報告的你說加上核對記號",          # 沒標派工也找派工說明
        "派工：因此我寧可錯殺也不願放過",         # 標了派工但其實是使用者的話 → 認使用者的話（派它的那回合＝本回合）
        "派工：子代理檔裡第二則不是派工",          # 只認第一則
        "全部按照建議，但我希望",                 # 派它之後使用者才說的：子代理看不到，不拿來比
    ], agent_id="A1", transcript=main)
    assert got == ["派工", "派工", "本回合", "對不到", "對不到"]
    assert report["user_said_this_turn"] == [_TURN2]   # 子代理的本回合＝派它的那一回合
    # hook 給的是子代理檔路徑也一樣
    got2, _ = _check(tmp_path, ["派工：只加記號、不擋"], transcript=tmp_path / "sess" / "subagents" / "agent-A1.jsonl")
    assert got2 == ["派工"]
    # 主 session：同伴 session 傳來的工作說明算派工
    got3, _ = _check(tmp_path, ["派工：同伴派來的工作說明：把 HUD 改成白話", "派工：根本沒有這段派工"], transcript=main)
    assert got3 == ["派工", "對不到"]


def test_unreadable_transcript_marks_cannot_judge(tmp_path, capsys):
    report = {"goal": [{"said": _TURN2}, {"said": "好"}]}
    sc.annotate(report, {"transcript_path": str(tmp_path / "沒有這個檔.jsonl")})
    assert [g["said_check"] for g in report["goal"]] == ["判不了", "太短不判"]
    assert "user_said_this_turn" not in report
    report2 = {"goal": [{"said": _TURN2}]}
    sc.annotate(report2, {})
    assert report2["goal"][0]["said_check"] == "判不了"
    err = capsys.readouterr().err
    assert err.count("[Guardian:AEC-Said]") == 2


def _drive_ptu(monkeypatch, tmp_path, tool_input, transcript_path):
    import verify_aec_emission_gate as vae
    pt = vae.pt
    state = {"turn_seq": 7}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(pt, "_hud_alive", lambda *a, **k: (False, {"reason": "test"}))
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_spawn_hud_edge", lambda *a, **k: None)
    inp = {"session_id": "s-said", "tool_name": "mcp__workflow-guardian__anti_evasion_report",
           "tool_input": tool_input, "tool_response": {}, "transcript_path": transcript_path}
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}, "aec": {}})
    return state


@pytest.mark.parametrize("guard", ["0", "1"])
def test_ptu_writes_checks_into_report_file_both_modes(monkeypatch, tmp_path, guard):
    monkeypatch.setenv("WG_CODING_GUARD", guard)
    main = _main_transcript(tmp_path / "t")
    base = {"a": "無", "b": "無", "d": "無", "g": "無", "h": "可關閉", "i": "無", "j_evidence_path": "無", "k_followups": "無",
            "principles": [], "ai_decided": []}
    goal = [{"said": "這一輪之後沒有再度延展的了", "done": "d", "verified": "3 案過", "not_done": "無"},
            {"said": "HUD 要直接顯示使用者原話並且每句都核對", "done": "d", "verified": "3 案過", "not_done": "無"}]
    state = _drive_ptu(monkeypatch, tmp_path, {**base, "goal": goal}, str(main))
    aec = state["anti_evasion_report"]
    assert [g["said_check"] for g in aec["goal"]] == ["本回合", "對不到"]
    assert aec["severity"] == "routine" and len(aec["user_said_this_turn"]) == 2
    on_disk = json.loads((tmp_path / "aec-report" / "s-said-t7.json").read_text(encoding="utf-8"))
    assert on_disk["goal"] == aec["goal"] and on_disk["user_said_this_turn"] == aec["user_said_this_turn"]
    # 讀不到紀錄：hook 照跑、照落檔
    state2 = _drive_ptu(monkeypatch, tmp_path, {**base, "goal": goal}, str(tmp_path / "沒有.jsonl"))
    assert [g["said_check"] for g in state2["anti_evasion_report"]["goal"]] == ["判不了", "判不了"]


# ─── HUD ─────────────────────────────────────────────────────────────────────

def _goal(said, check=None):
    g = {"said": said, "done": "做了", "verified": "2 案過", "not_done": "無"}
    if check is not None:
        g["said_check"] = check
    return g


@node
def test_hud_marks_and_this_turn_region():
    marked = {**_NORMAL, "goal": [_goal("甲句", "本回合"), _goal("乙句", "第 2 回合前"), _goal("丙句", "派工"),
                                  _goal("丁句", "對不到"), _goal("戊句", "判不了"), _goal("己", "太短不判")],
              "user_said_this_turn": ["全部按照建議\n1. 這一輪之後沒有再度延展的了", "對了，HUD 也要顯示原話"]}
    html, = _cards(marked)
    assert '你說：「甲句」<span class="sc ok"' in html and "✓</span>" in html
    assert '<span class="sc src"' in html and "出自你 2 回合前的訊息" in html and "出自派工說明，不是你直接打的字" in html
    assert re.search(r'你說：「丁句」<span class="sc warn"[^>]*>⚠ AI 抄的這句在你的訊息裡找不到</span>', html)
    assert html.count('<span class="sc gray"') == 2 and "讀不到對話紀錄，沒核對" in html and "太短，沒核對" in html
    # 你這回合說的原話：在「份量」之後、① 之前；短的預設展開、全文照列（保留換行）
    i_region = html.index("你這回合說的原話")
    assert html.index("份量") < i_region < html.index("① 你這次要的事")
    assert '<details class="usaid" open>' in html and "2 則・" in html
    assert "全部按照建議\n1. 這一輪之後沒有再度延展的了" in html and "對了，HUD 也要顯示原話" in html
    long_one = {**marked, "user_said_this_turn": ["長" * 401]}
    html_long, = _cards(long_one)
    assert '<details class="usaid">' in html_long and "長" * 401 in html_long
    empty, = _cards({**marked, "user_said_this_turn": []})
    assert "紀錄裡沒找到你這回合打的字" in empty


@node
def test_hud_old_reports_render_without_new_fields():
    normal, legacy = _cards(_NORMAL, _LEGACY)
    for html in (normal, legacy):
        assert 'class="sc ' not in html and "你這回合說的原話" not in html
    assert "你說：「沒有基礎分類」</div>" in normal and "舊格式報告" in legacy


@node
def test_hud_escapes_user_text_and_unknown_check():
    bad = {**_NORMAL, "goal": [_goal("<b>x</b>", "<img src=x onerror=alert(1)>")],
           "user_said_this_turn": ["<script>alert(1)</script> 與 & 符號"]}
    html, = _cards(bad)
    assert "<script>alert" not in html and "&lt;script&gt;alert(1)&lt;/script&gt; 與 &amp; 符號" in html
    assert "<img" not in html and "<b>x" not in html and 'class="sc ' not in html   # 不認得的值不標
