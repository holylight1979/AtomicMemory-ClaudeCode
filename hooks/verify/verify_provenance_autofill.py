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


def test_injection_strips_html_comments():
    sec = _extract_named_section(ATOM, "知識")
    assert sec is not None
    assert "<!--" not in sec and "src:" not in sec
    assert "- [臨] 內容" in sec
