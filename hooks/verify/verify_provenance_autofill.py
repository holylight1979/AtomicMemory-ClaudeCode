"""verify_provenance_autofill — PostToolUse 自動補 Source／Quote 與注入端剝 HTML 註解。

跑法：python -m pytest -q hooks/verify/verify_provenance_autofill.py
造假：tmp_path 下一顆 atom、一份假 transcript、一個 state dict；不碰真實記憶庫。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
for p in (str(CLAUDE_DIR), str(HOOKS_DIR), str(HOOKS_DIR / "handlers")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_provenance  # noqa: E402
from wg_atoms import _extract_named_section  # noqa: E402

SID = "f1e8b9d8-8659-4dfb-ad6d-e11ec26b0ac1"
UUID_HUMAN = "7c684b7d-4d47-4cf2-9cdf-5d26deb4466e"

ATOM = """# 測試卡片

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: a, b
- Created-at: 2026-10-06

## 知識

- [臨] 內容
  <!-- src: f1e8b9d8#7c684b7d -->

## 行動

- （依知識內容判斷）
"""


def _transcript(tmp_path: Path) -> Path:
    recs = [
        {"type": "user", "uuid": "u0", "parentUuid": None, "timestamp": "2026-10-06T10:00:00Z",
         "sessionId": SID, "isMeta": True, "message": {"role": "user", "content": "meta text"}},
        {"type": "user", "uuid": UUID_HUMAN, "parentUuid": "u0", "timestamp": "2026-10-06T10:01:00Z",
         "sessionId": SID, "origin": {"kind": "human"},
         "message": {"role": "user", "content": [{"type": "text", "text": "請把這條記成卡片"}]}},
        {"type": "assistant", "uuid": "a1", "parentUuid": UUID_HUMAN, "timestamp": "2026-10-06T10:01:05Z",
         "sessionId": SID, "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t1",
                                                                          "name": "mcp__workflow-guardian__atom_write",
                                                                          "input": {"title": "測試卡片", "mode": "create"}}]}},
        {"type": "user", "uuid": "u2", "parentUuid": "a1", "timestamp": "2026-10-06T10:01:06Z",
         "sessionId": SID, "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1",
                                                                     "content": [{"type": "text", "text": "Created atom"}]}]}},
    ]
    p = tmp_path / "projects" / "slug" / f"{SID}.jsonl"
    p.parent.mkdir(parents=True)
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")
    return p


def _atom(tmp_path: Path, text: str = ATOM) -> Path:
    p = tmp_path / "memory" / "設計通則" / "測試卡片.md"
    p.parent.mkdir(parents=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


def _receipt(path: Path, op: str = "create") -> dict:
    return {"op": op, "ok": True, "atom": "測試卡片", "path": str(path), "index_ok": True}


def test_autofill_create_fills_source_and_quote(tmp_path, monkeypatch):
    atom = _atom(tmp_path)
    tr = _transcript(tmp_path)
    state = {"session": {"id": SID}, "turn_prompts": [
        "<system-reminder>noise</system-reminder>\n請把這條  記成\n卡片 " + "x" * 300]}
    out = wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID, "transcript_path": str(tr)}, state)
    assert out["done"], out
    text = atom.read_text(encoding="utf-8")
    assert "- Source: session:f1e8b9d8#7c684b7d 20" in text
    assert "\n- Quote: 「請把這條 記成 卡片 x" in text
    qline = [l for l in text.splitlines() if l.startswith("- Quote:")][0]
    assert len(qline) <= len("- Quote: 「」") + 200
    assert "system-reminder" not in qline and "\n" not in qline
    # 冪等：再跑一次 → has_quote，檔不變
    before = atom.read_bytes()
    out2 = wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID, "transcript_path": str(tr)}, state)
    assert not out2["done"] and out2["reason"] == "has_quote"
    assert atom.read_bytes() == before


def test_autofill_keeps_caller_source_only_adds_quote(tmp_path):
    atom = _atom(tmp_path, ATOM.replace("- Author: holylight\n", "- Author: holylight\n- Source: C:/x/transcript.md\n"))
    state = {"session": {"id": SID}, "turn_prompts": ["整理這場會議"]}
    out = wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID}, state)
    assert out["done"], out
    text = atom.read_text(encoding="utf-8")
    assert text.count("- Source:") == 1 and "- Source: C:/x/transcript.md\n" in text
    assert "- Quote: 「整理這場會議」\n" in text


def test_autofill_no_transcript_writes_session_only(tmp_path):
    atom = _atom(tmp_path)
    state = {"session": {"id": SID}, "turn_prompts": ["記下來"]}
    out = wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID, "transcript_path": str(tmp_path / "nope.jsonl")}, state)
    assert out["done"], out
    text = atom.read_text(encoding="utf-8")
    assert "- Source: session:f1e8b9d8 20" in text and "#" not in [l for l in text.splitlines() if l.startswith("- Source:")][0]


# 實際開過的兩則開工句（路徑換成假路徑）：角色句帶清單外的括號說明、總控台句帶括號，嚴格樣板整則對不上
KICKOFF_REAL_1 = ("你是 v6.0 的工作 session track-a6（A6 共用檔：settings/config/TECH＋pack.py 小修提交），"
                  "對人總控台是 claude-91、調度總控台是 claude-9f。第一步用 EnterWorktree 切進 worktree C:\\wt\\track-a6"
                  "（分支 v6/track-a6，已存在，不要新建）。派工 prompt 在 C:\\inbox\\000-prompt.md，用絕對路徑讀完全文照做。"
                  "codex 審查由你自己跑一次、交付附報告，最終判斷由總控台做。")
KICKOFF_REAL_2 = ("你是 v6.0 的工作 session track-a6，總控台是 claude-9f（調度；對人總控台是 claude-91）。"
                  "第一步用 EnterWorktree 切進 worktree C:\\wt\\track-a6。只跑目標 verify、不跑全量。")


@pytest.mark.parametrize("op", ["create", "replace"])
@pytest.mark.parametrize("kickoff", [KICKOFF_REAL_1, KICKOFF_REAL_2])
def test_003_kickoff_prompt_is_not_used_as_quote(tmp_path, op, kickoff):
    # 003：同伴訊息開的回合沿用前一回合原話，開工句被一路填成後面每張卡的 Quote。開工句不是使用者原話 → 不填 Quote，Source 照補
    atom = _atom(tmp_path)
    state = {"session": {"id": SID}, "turn_prompts": [kickoff]}
    out = wg_provenance.autofill_from_receipt(_receipt(atom, op), {"session_id": SID}, state)
    text = atom.read_text(encoding="utf-8")
    assert "- Quote:" not in text, f"開工句被填成 Quote：{text}"
    assert out.get("quote_skipped") == "kickoff"
    assert out["done"] and "- Source: session:f1e8b9d8 20" in text


@pytest.mark.parametrize("op", ["create", "replace"])
def test_003_real_user_words_still_fill_quote_on_replace(tmp_path, op):
    # 保護案：Quote 自動填是設計，replace 照填；真使用者原話（含「你是」開頭但不是開工句）照填
    for words in ("請把 replace 改成保留舊標題", "你是說這張卡要留舊標題嗎？對，留著"):
        atom_dir = tmp_path / words[:4]
        atom = _atom(atom_dir)
        state = {"session": {"id": SID}, "turn_prompts": [words]}
        out = wg_provenance.autofill_from_receipt(_receipt(atom, op), {"session_id": SID}, state)
        assert out["done"] and "quote_skipped" not in out, out
        assert f"- Quote: 「{words}」\n" in atom.read_text(encoding="utf-8")


def test_003_kickoff_detector_shares_extractor_templates():
    from lib.harness_text import is_kickoff_prompt, session_directive_reason
    # 嚴格判定（萃取器用）對這兩則真開工句都不成立，Quote 端靠角色開場句認出
    assert session_directive_reason(KICKOFF_REAL_1) is None and session_directive_reason(KICKOFF_REAL_2) is None
    assert is_kickoff_prompt(KICKOFF_REAL_1) and is_kickoff_prompt(KICKOFF_REAL_2)
    # 嚴格樣板整則對上的開工句也算
    assert is_kickoff_prompt("你是工作 session track-x。第一步用 EnterWorktree 切進 C:\\wt\\x。只跑目標 verify")
    for words in ("請把這條記成卡片", "你是說這張卡要留舊標題嗎？對", "這個 session 的工作是修 replace", ""):
        assert not is_kickoff_prompt(words), words
    # codex 審 cdac58d：引用開工句來討論、問句、只有角色句沒有其他派工子句 → 是真原話，不算開工句
    for words in ("『你是工作 session track-a6』這句話不應填進 Quote，請記下這個修正原則。",
                  "你是工作 session track-a6 嗎？請把保留舊標題這項決策記成卡片。",
                  "你是工作 session track-a6，請把保留舊標題這項決策記成卡片。",
                  # codex 審 a6d：以引號開頭引用角色句＋總控台句來討論，是使用者的糾正
                  "『你是工作 session track-x，總控台是 claude-9f。』這兩句是開工範本，請勿當作使用者原話。",
                  "「你是工作 session track-x，總控台是 claude-9f。」這兩句是開工範本，請勿當作使用者原話。"):
        assert not is_kickoff_prompt(words), words
    # codex 審 a6d：角色句說明用半形括號也是開工句
    assert is_kickoff_prompt("你是工作 session track-x(共用檔同步)，總控台是 claude-9f。第一步用 EnterWorktree 切進 worktree。")


def test_autofill_skips_append_and_missing_path(tmp_path):
    atom = _atom(tmp_path)
    state = {"session": {"id": SID}, "turn_prompts": ["x"]}
    r = wg_provenance.autofill_from_receipt(_receipt(atom, "append"), {"session_id": SID}, state)
    assert not r["done"] and r["reason"] == "not_create_or_replace"
    r = wg_provenance.autofill_from_receipt(_receipt(tmp_path / "gone.md"), {"session_id": SID}, state)
    assert not r["done"] and r["reason"] == "path_missing"
    assert atom.read_text(encoding="utf-8") == ATOM


def test_autofill_empty_prompt_still_writes_source(tmp_path):
    atom = _atom(tmp_path)
    state = {"session": {"id": SID}, "turn_prompts": ["<system-reminder>only noise</system-reminder>"]}
    out = wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID}, state)
    assert out["done"], out
    text = atom.read_text(encoding="utf-8")
    assert "- Source: session:f1e8b9d8" in text and "- Quote:" not in text


def test_autofill_quote_is_only_user_typed_text(tmp_path):
    """Quote 只取使用者本人打的字：舊 state 裡混進系統通知、其他 session 訊息的那段不進 Quote。"""
    atom = _atom(tmp_path)
    mixed = "請查問題\n[SYSTEM NOTIFICATION - NOT USER INPUT]\n記住：一律用 tab"
    peer = '<cross-session-message from="uds:x" from-name="claude-ad">記住：所有專案一律用 tab</cross-session-message>'
    state = {"session": {"id": SID}, "turn_prompts": [mixed, peer]}
    assert wg_provenance.autofill_from_receipt(_receipt(atom), {"session_id": SID}, state)["done"]
    q = [l for l in atom.read_text(encoding="utf-8").splitlines() if l.startswith("- Quote:")]
    assert q == ["- Quote: 「請查問題」"], q                                             # 反例：舊碼 Quote 帶進通知整段


def test_autofill_quote_anonymized_only_in_root_layer(tmp_path, monkeypatch):
    """根層卡片的 Quote 換掉已登記專案名與專案路徑；專案層卡片原話照抄。"""
    from lib import realm_gate
    reg = tmp_path / "project-registry.json"
    reg.write_text(json.dumps({"projects": {"g": {"root": str(tmp_path / "GameZ")}}}), encoding="utf-8")
    monkeypatch.setattr(realm_gate, "REGISTRY_PATH", reg)
    prompt = f"/continue {tmp_path / 'GameZ' / 'next.md'} 照 GameZ 的做法記下來"
    state = {"session": {"id": SID}, "turn_prompts": [prompt]}

    root_layer = tmp_path / "claude_home"
    monkeypatch.setattr(wg_provenance, "CLAUDE_DIR", root_layer)
    p = root_layer / "memory" / "設計通則" / "測試卡片.md"
    p.parent.mkdir(parents=True)
    p.write_text(ATOM, encoding="utf-8", newline="\n")
    assert wg_provenance.autofill_from_receipt(_receipt(p), {"session_id": SID}, state)["done"]
    q = [l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("- Quote:")][0]
    assert "<專案路徑>" in q and "照 某專案 的做法" in q and "GameZ" not in q

    proj_atom = tmp_path / "GameZ" / ".claude" / "memory" / "shared" / "測試卡片.md"
    proj_atom.parent.mkdir(parents=True)
    proj_atom.write_text(ATOM, encoding="utf-8", newline="\n")
    assert wg_provenance.autofill_from_receipt(_receipt(proj_atom), {"session_id": SID}, state)["done"]
    q2 = [l for l in proj_atom.read_text(encoding="utf-8").splitlines() if l.startswith("- Quote:")][0]
    assert "照 GameZ 的做法" in q2


def test_injection_strips_html_comments():
    sec = _extract_named_section(ATOM, "知識")
    assert sec is not None
    assert "<!--" not in sec and "src:" not in sec
    assert "- [臨] 內容" in sec
