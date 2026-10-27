"""verify_quote_user_turn — 卡片的 Quote 只取使用者本人在「寫卡那一回合」打的字（規則 QUOTE_FROM_USER_OPENED_TURN）。

測什麼（三個寫 Quote 的入口共用的判定）：
- PostToolUse 自動填（hooks/wg_provenance.autofill_from_receipt）：
  主 session 在同伴訊息／背景通知開的續跑回合寫卡 → 不填（state.turn_prompts 沿用的是前一回合的原話）；
  子代理寫卡 → 看派它的那一回合（子代理檔第一筆 promptId 對主檔開回合的紀錄）：是真人訊息才填它的原話，
  不拿主 session 現在的回合、也不拿子代理檔裡的任務 prompt。
- 貼上的內容（`<pasted_content id=…>…</pasted_content id=…>`）不是本人打的字：lib/provenance.sanitize_quote 剔掉。
- lib/provenance.is_human_record：內容是純字串、origin.kind=human 的真人訊息認得出；子代理那邊的紀錄（isSidechain）一律不算。
- 舊卡回填（tools/atom-provenance-backfill.py）走同一套判定。
跑法：python -m pytest -q hooks/verify/verify_quote_user_turn.py
造假：tmp_path 下的 atom、假 transcript（主檔＋subagents/agent-<id>.jsonl）、state dict；不碰真實記憶庫。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CODE_DIR = HOOKS_DIR.parent
for p in (str(CODE_DIR), str(HOOKS_DIR), str(HOOKS_DIR / "handlers")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_provenance  # noqa: E402
from handlers.ups_gates import track_turn_prompts  # noqa: E402
from lib.provenance import is_human_record, record_text, sanitize_quote  # noqa: E402

SID = "9af7f47a-c420-4ff3-b1fe-0ceace03da23"
AID = "a25ce6db16b7499bf"

ATOM = """# 測試卡片

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: a, b
- Created-at: 2026-10-27

## 知識

- [臨] 內容

## 行動

- （依知識內容判斷）
"""

# 實錄形狀（文字換成假的）：使用者貼上一則開工句開 session；之後的回合都是同伴訊息開的
PASTED_KICKOFF = ('\n\n<pasted_content id="e925">\n值班 session：你是這個專案的值班 session，接替已離線的上一位。'
                  '先讀 C:\\inbox\\next.md，照「用法二」做。\n</pasted_content id="e925">\n')
PEER_UPS = '<cross-session-message from="uds:x" from-name="claude-x">直接開始第一步。</cross-session-message>'
PEER = "Another Claude session sent a message:\n" + PEER_UPS        # transcript 裡的同一則（UserPromptSubmit 收到的沒有這行開頭）
SUB_PROMPT = ("你是代寫卡子代理。任務：把一條已關掉的工作線留下的經驗寫成記憶卡。"
              "Quote 欄：這些是 AI 自己的工作經驗，不是使用者原話——Quote 不填。")


def _user(uuid, ts, content, prompt_id, **extra):
    return {"type": "user", "uuid": uuid, "parentUuid": None, "timestamp": ts, "sessionId": SID,
            "promptId": prompt_id, "message": {"role": "user", "content": content}, **extra}


def _human(uuid, ts, text, prompt_id, as_str=False):
    content = text if as_str else [{"type": "text", "text": text}]
    return _user(uuid, ts, content, prompt_id, origin={"kind": "human"})


def _write(path: Path, recs) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")
    return path


def _transcripts(tmp_path: Path, main_recs, sub_prompt_id):
    main = _write(tmp_path / "projects" / "slug" / f"{SID}.jsonl", main_recs)
    sub = _write(main.with_suffix("") / "subagents" / f"agent-{AID}.jsonl", [
        {"type": "user", "uuid": "s0", "parentUuid": None, "timestamp": "2026-10-27T02:11:30Z", "sessionId": SID,
         "isSidechain": True, "agentId": AID, "promptId": sub_prompt_id,
         "message": {"role": "user", "content": "[WG:SubagentMemory] 長期記憶…\n\n" + SUB_PROMPT}}])
    return main, sub


def _atom(tmp_path: Path, name="測試卡片") -> Path:
    p = tmp_path / "memory" / "設計通則" / f"{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(ATOM, encoding="utf-8", newline="\n")
    return p


def _receipt(path: Path, op="create") -> dict:
    return {"op": op, "ok": True, "atom": path.stem, "path": str(path), "index_ok": True}


def _quote_line(path: Path):
    return [l for l in path.read_text(encoding="utf-8").splitlines() if l.startswith("- Quote:")]


def _state_after_peer_turn(v6=True):
    """UserPromptSubmit 照實際順序收兩則：使用者貼上的開工句 → Stop 關回合 → 同伴訊息開續跑回合。"""
    st = {"session": {"id": SID}}
    track_turn_prompts(st, PASTED_KICKOFF, v6)
    st["turn_open"] = False
    track_turn_prompts(st, PEER_UPS, v6)
    return st


def _main_with_peer_turn():
    return [_human("k1", "2026-10-27T01:55:52Z", PASTED_KICKOFF, "P-kick"),
            _user("p1", "2026-10-27T01:57:09Z", PEER, "P-peer", origin={"kind": "peer"}, isMeta=True)]


# ─── 子代理寫卡：實錄重放 ───────────────────────────────────────────────────────

@pytest.mark.parametrize("hook_gives", ["main", "agent"])
def test_subagent_in_peer_turn_does_not_quote_kickoff_or_task_prompt(tmp_path, hook_gives):
    # 實錄：同伴訊息開的回合裡派出背景子代理寫卡；舊碼拿主 session state 沿用的那則（貼上的開工句）填進每張卡的 Quote
    main, sub = _transcripts(tmp_path, _main_with_peer_turn(), "P-peer")
    st = _state_after_peer_turn()
    assert st["turn_prompts"] and st["turn_typed"] is False, st      # 前提：續跑回合沿用了開工句
    atom = _atom(tmp_path)
    out = wg_provenance.autofill_from_receipt(
        _receipt(atom), {"session_id": SID, "agent_id": AID, "transcript_path": str(main if hook_gives == "main" else sub)}, st)
    assert _quote_line(atom) == [], f"子代理寫的卡被填了 Quote：{atom.read_text(encoding='utf-8')}"
    assert out.get("quote_skipped") == "not_user_turn" and out["done"], out
    assert "- Source: session:9af7f47a#k1 2026-" in atom.read_text(encoding="utf-8")   # Source 照補，指主檔最近一則真人訊息


@pytest.mark.parametrize("v6", [True, False])
def test_main_session_peer_opened_turn_does_not_quote_carried_prompt(tmp_path, v6):
    # 同一個回合由主 session 自己寫卡也一樣：續跑回合沿用的原話不是這張卡的觸發句（守門總開關開關都一樣，這不是閘）
    main, _ = _transcripts(tmp_path, _main_with_peer_turn(), "P-peer")
    st = _state_after_peer_turn(v6)
    st["turn_prompts"] = ["把這次查到的根因記成卡片"]                    # 就算沿用的是一句正常的話也不填
    atom = _atom(tmp_path)
    out = wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID, "transcript_path": str(main)}, st)
    assert _quote_line(atom) == [] and out.get("quote_skipped") == "not_user_turn", out


def test_subagent_quotes_the_user_words_of_the_turn_that_launched_it(tmp_path):
    # 使用者打字開的回合派出子代理；子代理寫卡時主 session 已進到下一個使用者回合 → Quote 取派它那回合的原話，Source 指那則
    main, _ = _transcripts(tmp_path, [
        _human("h1", "2026-10-27T03:00:00Z", "把這次查到的根因記成卡片", "P-1"),
        _human("h2", "2026-10-27T03:05:00Z", "幫我看另一個檔案的縮排格式", "P-2"),
    ], "P-1")
    st = {"session": {"id": SID}, "turn_prompts": ["幫我看另一個檔案的縮排格式"], "turn_typed": True, "turn_open": True}
    atom = _atom(tmp_path)
    out = wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID, "agent_id": AID, "transcript_path": str(main)}, st)
    assert _quote_line(atom) == ["- Quote: 「把這次查到的根因記成卡片」"], (out, atom.read_text(encoding="utf-8"))
    assert "- Source: session:9af7f47a#h1 2026-" in atom.read_text(encoding="utf-8")


def test_subagent_launched_by_plain_string_user_prompt_still_quotes(tmp_path):
    # 真人訊息內容是純字串（origin.kind=human）也認得出：主 session 使用者真的說過的原話照樣能填
    main, _ = _transcripts(tmp_path, [_human("h1", "2026-10-27T03:00:00Z", "把這次查到的根因記成卡片", "P-1", as_str=True)], "P-1")
    st = {"session": {"id": SID}, "turn_prompts": [], "turn_typed": True}
    atom = _atom(tmp_path)
    wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID, "agent_id": AID, "transcript_path": str(main)}, st)
    assert _quote_line(atom) == ["- Quote: 「把這次查到的根因記成卡片」"], atom.read_text(encoding="utf-8")


@pytest.mark.parametrize("case", ["no_agent_file", "prompt_id_not_in_main"])
def test_subagent_without_traceable_turn_writes_no_quote(tmp_path, case):
    main, sub = _transcripts(tmp_path, [_human("h1", "2026-10-27T03:00:00Z", "把這次查到的根因記成卡片", "P-1")], "P-other")
    if case == "no_agent_file":
        sub.unlink()
    st = {"session": {"id": SID}, "turn_prompts": ["把這次查到的根因記成卡片"], "turn_typed": True}
    atom = _atom(tmp_path)
    out = wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID, "agent_id": AID, "transcript_path": str(main)}, st)
    assert _quote_line(atom) == [] and out.get("quote_skipped") == "not_user_turn", out
    assert SUB_PROMPT[:10] not in atom.read_text(encoding="utf-8")


def test_main_session_user_turn_still_quotes(tmp_path):
    # 保護案：使用者打字開的回合，主 session 寫卡照填
    st = {"session": {"id": SID}}
    track_turn_prompts(st, "把保留舊標題這項決策記成卡片", True)
    assert st["turn_typed"] is True
    atom = _atom(tmp_path)
    out = wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID}, st)
    assert out["done"] and "quote_skipped" not in out, out
    assert _quote_line(atom) == ["- Quote: 「把保留舊標題這項決策記成卡片」"]


# ─── 貼上的內容 ─────────────────────────────────────────────────────────────────

def test_pasted_kickoff_in_user_turn_is_not_quote(tmp_path):
    # 使用者貼上開工句開的第一回合就寫卡：貼上的材料不是本人打的字（舊碼連標籤一起填進 Quote）
    st = {"session": {"id": SID}}
    track_turn_prompts(st, PASTED_KICKOFF, True)
    assert st["turn_typed"] is True                                  # 前提：這回合算使用者開的（口令等判斷照舊）
    atom = _atom(tmp_path)
    out = wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID}, st)
    assert _quote_line(atom) == [] and out.get("quote_skipped") == "pasted", (out, atom.read_text(encoding="utf-8"))


def test_typed_words_around_paste_are_kept(tmp_path):
    st = {"session": {"id": SID}}
    track_turn_prompts(st, '看這段：<pasted_content id="a1">\nTraceback: KeyError x\n</pasted_content id="a1">\n這個錯誤怎麼修', True)
    atom = _atom(tmp_path)
    wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID}, st)
    assert _quote_line(atom) == ["- Quote: 「看這段： 這個錯誤怎麼修」"], atom.read_text(encoding="utf-8")


def test_paste_with_mismatched_closing_id_does_not_leak_into_quote(tmp_path):
    # 閉合標籤的 id 大小寫不同：後面那句仍是貼上的材料，不能被當成本人打的字填進 Quote
    st = {"session": {"id": SID}}
    track_turn_prompts(st, '<pasted_content id="a1">日誌</pasted_content id="A1">這一整句都是貼上的材料', True)
    atom = _atom(tmp_path)
    wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID}, st)
    assert _quote_line(atom) == [], atom.read_text(encoding="utf-8")


def test_strip_pasted_matches_closing_id_and_eats_unclosed():
    from lib.harness_text import strip_pasted
    nested ='前<pasted_content id="A">外<pasted_content id="B">內</pasted_content id="B">外</pasted_content id="A">後'
    assert strip_pasted(nested, "") == "前後"
    assert strip_pasted('前<pasted_content>材料</pasted_content>後', "") == "前後"           # 沒 id：第一個閉合
    assert strip_pasted('前<pasted_content id="A">截斷的材料…', "") == "前"                  # 沒閉合（state 截 500 字）吃到尾
    for fake_close in ('</pasted_content id="A1">', '</pasted_content data-id="a1">'):        # id 要逐字相同、data-id 不算
        assert strip_pasted(f'前<pasted_content id="a1">日誌{fake_close}這一整句都是貼上的材料', "") == "前", fake_close
    assert strip_pasted('前<pasted_content data-id="x" id="a1">日誌</pasted_content id="a1">後', "") == "前後"
    assert strip_pasted('前</pasted_content id="A">後') == ""                               # 殘留標籤字樣：整則不認
    assert strip_pasted("沒有貼上") == "沒有貼上"
    assert sanitize_quote('「' + PASTED_KICKOFF + '」') == ""


# ─── is_human_record ─────────────────────────────────────────────────────────

def test_is_human_record_plain_string_and_sidechain():
    assert is_human_record(_human("h", "t", "把這條記成卡片", "P", as_str=True))           # 純字串＋origin human
    assert record_text(_human("h", "t", "  把這條記成卡片 ", "P", as_str=True)) == "把這條記成卡片"
    assert not is_human_record(_user("x", "t", "This session is being continued…", "P"))  # 沒 origin 的純字串
    assert not is_human_record(_user("x", "t", "   ", "P", origin={"kind": "human"}))
    side = _user("s", "t", [{"type": "text", "text": SUB_PROMPT}], "P", isSidechain=True)
    assert not is_human_record(side), "子代理那邊的 user 紀錄被當成真人訊息"               # 舊格式：子代理紀錄寫在主檔
    assert not is_human_record(dict(side, origin={"kind": "human"}))
    assert is_human_record(_user("o", "t", [{"type": "text", "text": "舊紀錄沒有 origin"}], "P"))   # 舊格式真人訊息照認


# ─── 舊卡回填走同一套 ───────────────────────────────────────────────────────────

_spec = importlib.util.spec_from_file_location("atom_provenance_backfill_qt", CODE_DIR / "tools" / "atom-provenance-backfill.py")
bf = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["atom_provenance_backfill_qt"] = bf
_spec.loader.exec_module(bf)  # type: ignore[union-attr]


def _tool_use(uuid, parent, ts, tid, title, **extra):
    return {"type": "assistant", "uuid": uuid, "parentUuid": parent, "timestamp": ts, "sessionId": SID,
            "message": {"role": "assistant", "content": [{"type": "tool_use", "id": tid,
                                                          "name": "mcp__workflow-guardian__atom_write",
                                                          "input": {"title": title, "mode": "create"}}]}, **extra}


def _tool_result(uuid, parent, ts, tid, path, **extra):
    return {"type": "user", "uuid": uuid, "parentUuid": parent, "timestamp": ts, "sessionId": SID,
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid,
                                                     "content": [{"type": "text", "text": f"Path: {path}\n"}]}]}, **extra}


def _backfill(tmp_path, monkeypatch, recs, atom):
    monkeypatch.setattr(bf, "AUDIT_LOG", tmp_path / "audit.jsonl")
    projects = tmp_path / "projects"
    _write(projects / "slug" / f"{SID}.jsonl", recs)
    return bf.backfill(apply=True, projects_dir=projects, atoms=[("root", atom)])["results"][0]


def test_backfill_inline_sidechain_task_prompt_is_not_quote(tmp_path, monkeypatch):
    # 舊格式 transcript 把子代理紀錄寫在主檔（isSidechain）：沿 parentUuid 回溯會走到子代理的任務 prompt，不得當 Quote
    atom = _atom(tmp_path)
    side = _user("sc0", "2026-10-27T03:01:00Z", [{"type": "text", "text": SUB_PROMPT}], "P-1", isSidechain=True)
    r = _backfill(tmp_path, monkeypatch, [
        _human("h1", "2026-10-27T03:00:00Z", "主線上使用者說的另一件事情", "P-1"),
        side,
        _tool_use("a1", "sc0", "2026-10-27T03:01:05Z", "t1", "測試卡片", isSidechain=True),
        _tool_result("r1", "a1", "2026-10-27T03:01:06Z", "t1", atom, isSidechain=True)], atom)
    text = atom.read_text(encoding="utf-8")
    assert "代寫卡子代理" not in text, f"子代理的任務 prompt 被回填成 Quote：{text}"
    assert r["grade"] == "A_noquote" and r.get("quote_skipped") == "not_user_turn", r


def test_backfill_plain_string_human_prompt_is_quoted(tmp_path, monkeypatch):
    # 真人訊息內容是純字串（origin.kind=human）：回填認得出，Quote 照補
    atom = _atom(tmp_path)
    r = _backfill(tmp_path, monkeypatch, [
        _human("h1", "2026-10-27T03:00:00Z", "把這次查到的根因記成卡片", "P-1", as_str=True),
        _tool_use("a1", "h1", "2026-10-27T03:00:05Z", "t1", "測試卡片"),
        _tool_result("r1", "a1", "2026-10-27T03:00:06Z", "t1", atom)], atom)
    assert r["grade"] == "A" and _quote_line(atom) == ["- Quote: 「把這次查到的根因記成卡片」"], r


def test_backfill_pasted_kickoff_is_not_quote(tmp_path, monkeypatch):
    atom = _atom(tmp_path)
    r = _backfill(tmp_path, monkeypatch, [
        _human("k1", "2026-10-27T01:55:52Z", PASTED_KICKOFF, "P-kick"),
        _tool_use("a1", "k1", "2026-10-27T01:56:05Z", "t1", "測試卡片"),
        _tool_result("r1", "a1", "2026-10-27T01:56:06Z", "t1", atom)], atom)
    assert _quote_line(atom) == [] and r["grade"] == "A_noquote", (r, atom.read_text(encoding="utf-8"))
