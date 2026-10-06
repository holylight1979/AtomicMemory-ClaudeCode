"""verify_atom_source.py — lib/provenance.py 與 tools/atom-source.py 的來源回看封閉（全走 tmp_path，不碰真 transcript）。

cases：
  1. live：Source=session 且 transcript 在 → state=live、context 含命中句與前後各一則文字記錄（tool 記錄跳過）
  2. quote_only：transcript 不在 → 只剩 Quote，warnings 有「transcript 已不在」
  3. unrecoverable：B 級 Source（commit:/unknown）且無 Quote
  4. src 註解路徑：無 Source 行、知識段有 `<!-- src: sid8#uuid8 -->` → 同樣 live
  5. sanitize_quote 五案：system-reminder 剝除／換行折疊／頭尾引號／>200 截斷／空字串
  6. 找不到 atom → {"error"}；CLI exit 1；非標準 Source 字串不 crash
  7. CLI：--json 結構、人讀第一行 `<atom> — <state>`；atom_io_cli action=source 走通
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lib import provenance  # noqa: E402

SID = "0123abcd-1111-2222-3333-444455556666"
U_PREV, U_HIT, U_NEXT = "bbbb2222-0000-0000-0000-000000000000", "cccc3333-0000-0000-0000-000000000000", "dddd4444-0000-0000-0000-000000000000"


def _load_cli():
    spec = importlib.util.spec_from_file_location("atom_source_cli", CLAUDE_DIR / "tools" / "atom-source.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["atom_source_cli"] = mod
    spec.loader.exec_module(mod)
    return mod


def _rec(kind: str, uuid: str, ts: str, blocks: list, **extra) -> dict:
    return {"type": kind, "uuid": uuid, "parentUuid": None, "timestamp": ts, "sessionId": SID,
            "isSidechain": False, "message": {"role": kind, "content": blocks}, **extra}


def _write_transcript(projects: Path) -> Path:
    d = projects / "c--proj"
    d.mkdir(parents=True)
    rows = [
        {"type": "queue-operation", "operation": "enqueue", "timestamp": "2026-10-06T01:00:00Z"},
        _rec("user", "aaaa1111-0000-0000-0000-000000000000", "2026-10-06T01:00:01Z",
             [{"type": "text", "text": "第一句"}], origin={"kind": "human"}),
        _rec("assistant", U_PREV, "2026-10-06T01:00:02Z", [{"type": "text", "text": "助理回應一"}]),
        _rec("assistant", "eeee5555-0000-0000-0000-000000000000", "2026-10-06T01:00:03Z",
             [{"type": "tool_use", "name": "Read", "input": {}}]),
        _rec("user", "ffff6666-0000-0000-0000-000000000000", "2026-10-06T01:00:04Z",
             [{"type": "tool_result", "content": "x"}]),
        _rec("user", U_HIT, "2026-10-06T01:00:05Z",
             [{"type": "text", "text": "<system-reminder>注入</system-reminder>人讀文件只寫使用者體驗到的"}],
             origin={"kind": "human"}),
        _rec("assistant", U_NEXT, "2026-10-06T01:00:06Z", [{"type": "text", "text": "了解，收成三點"}]),
        _rec("user", "9999aaaa-0000-0000-0000-000000000000", "2026-10-06T01:00:07Z",
             [{"type": "text", "text": "最後一句"}], origin={"kind": "human"}),
    ]
    p = d / f"{SID}.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return p


def _atom(path: Path, *, source: str = "", quote: str = "", src_comment: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = "- Confidence: [臨]\n- Trigger: zzz\n"
    if source:
        meta += f"- Source: {source}\n"
    if quote:
        meta += f"- Quote: 「{quote}」\n"
    path.write_text(f"# {path.stem}\n\n{meta}\n## 知識\n\n- [臨] 知識一 {src_comment}\n\n## 行動\n\n- 無\n",
                    encoding="utf-8")
    return path


@pytest.fixture
def world(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    projects.mkdir()
    monkeypatch.setattr(provenance, "PROJECTS_DIR", projects)
    return {"projects": projects, "atoms": tmp_path / "atoms"}


# ─── 1 live ───────────────────────────────────────────────────────────────────

def test_live_context_has_prev_hit_next(world):
    _write_transcript(world["projects"])
    atom = _atom(world["atoms"] / "card-live.md", source=f"session:{SID[:8]}#{U_HIT[:8]} 2026-10-06", quote="原句")
    r = provenance.atom_source(str(atom))
    assert r["state"] == "live" and r["atom"] == "card-live" and r["quote"] == "原句"
    assert [c["uuid"] for c in r["context"]] == [U_PREV, U_HIT, U_NEXT]
    assert [c["role"] for c in r["context"]] == ["assistant", "user", "assistant"]
    assert "人讀文件" in r["context"][1]["text"] and r["context"][1]["ts"] == "2026-10-06T01:00:05Z"
    assert r["warnings"] == []


def test_find_transcript_and_last_human(world):
    p = _write_transcript(world["projects"])
    assert provenance.find_transcript(SID[:8]) == p
    assert provenance.find_transcript("ffffffff") is None
    last = provenance.last_human_record(p)
    assert last["text"] == "最後一句" and last["uuid"].startswith("9999aaaa")
    assert provenance.resolve_context(p, "nonexist") == []


# ─── 2 quote_only ─────────────────────────────────────────────────────────────

def test_quote_only_when_transcript_gone(world):
    atom = _atom(world["atoms"] / "card-q.md", source=f"session:{SID[:8]}#{U_HIT[:8]} 2026-10-06", quote="只剩這句")
    r = provenance.atom_source(str(atom))
    assert r["state"] == "quote_only" and r["quote"] == "只剩這句" and r["context"] == []
    assert any("transcript 已不在" in w for w in r["warnings"])


# ─── 3 unrecoverable ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("src", ["commit:abc1234 2026-09-01（原對話已逾保留期）", "unknown 2026-09-01（原對話已逾保留期）"])
def test_unrecoverable_b_grade_source(world, src):
    atom = _atom(world["atoms"] / "card-b.md", source=src)
    r = provenance.atom_source(str(atom))
    assert r["state"] == "unrecoverable" and r["quote"] == "" and r["context"] == []
    assert any("逾保留期" in w for w in r["warnings"])


def test_parse_source_kinds():
    s = provenance.parse_source("session:0123ABCD#89abcdef 2026-10-06")
    assert (s["kind"], s["sid8"], s["uuid8"], s["date"]) == ("session", "0123abcd", "89abcdef", "2026-10-06")
    assert provenance.parse_source("session:0123abcd 2026-10-06")["uuid8"] == ""
    c = provenance.parse_source("commit:abc1234 2026-09-01（原對話已逾保留期）")
    assert (c["kind"], c["hash7"], c["date"]) == ("commit", "abc1234", "2026-09-01")
    assert provenance.parse_source("unknown 2026-09-01")["kind"] == "unknown"
    p = provenance.parse_source("session 2026-10-06 ~/.claude README 重寫")
    assert (p["kind"], p["date"]) == ("path", "2026-10-06")
    assert provenance.parse_source("")["kind"] == ""
    assert provenance.format_source_session(SID, U_HIT, "2026-10-06") == f"session:{SID[:8]}#{U_HIT[:8]} 2026-10-06"
    assert provenance.format_source_session(SID, None, "2026-10-06") == f"session:{SID[:8]} 2026-10-06"


# ─── 4 src 註解路徑 ───────────────────────────────────────────────────────────

def test_src_comment_without_source_line(world):
    _write_transcript(world["projects"])
    atom = _atom(world["atoms"] / "card-c.md", src_comment=f"<!-- src: {SID[:8]}#{U_HIT[:8]} -->")
    assert provenance.read_src_comment(atom.read_text(encoding="utf-8")) == (SID[:8], U_HIT[:8])
    r = provenance.atom_source(str(atom))
    assert r["state"] == "live" and r["source"] == "" and r["context"][1]["uuid"] == U_HIT


# ─── 5 sanitize_quote ─────────────────────────────────────────────────────────

def test_sanitize_quote_cases():
    sq = provenance.sanitize_quote
    assert sq("<system-reminder>\n注入\n</system-reminder>真句子") == "真句子"
    assert sq("[WG:Sync] 提醒\n<ide_selection>x</ide_selection>第一行\n\n  第二行\t尾") == "第一行 第二行 尾"
    assert sq("「引號內」") == "引號內" and sq('"雙"') == "雙" and sq("“全形”") == "全形"
    long = "甲" * 250
    out = sq(long)
    assert len(out) == 200 and out.endswith("…") and out[:199] == "甲" * 199
    assert sq("") == "" and sq("<task-notification>a</task-notification>") == ""
    assert provenance.format_quote(" 「x」 ") == "「x」"


# ─── 6 找不到／非標準 Source ──────────────────────────────────────────────────

def test_missing_atom_returns_error(world, monkeypatch):
    monkeypatch.setattr(provenance, "_locate_atom_path", lambda atom, cwd, warnings: None)
    r = provenance.atom_source("no-such-card")
    assert "error" in r and "not found" in r["error"]
    assert "error" in provenance.atom_source("")


def test_nonstandard_source_does_not_crash(world):
    atom = _atom(world["atoms"] / "card-legacy.md", source="session 2026-10-06 ~/.claude README 重寫")
    r = provenance.atom_source(str(atom))
    assert r["state"] == "unrecoverable" and r["context"] == []


# ─── 7 CLI 與 bridge ─────────────────────────────────────────────────────────

def test_cli_json_and_human(world, capsys):
    _write_transcript(world["projects"])
    atom = _atom(world["atoms"] / "card-cli.md", source=f"session:{SID[:8]}#{U_HIT[:8]} 2026-10-06", quote="原句")
    cli = _load_cli()
    assert cli.main([str(atom), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"atom", "path", "source", "quote", "state", "context", "warnings"} and data["state"] == "live"
    assert cli.main([str(atom)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "card-cli — live" and lines[1].startswith("Source: session:") and lines[2] == "Quote: 「原句」"
    assert lines[3].startswith("[assistant 2026-10-06T01:00:02Z] 助理回應一")
    assert cli.main([str(world["atoms"] / "nope.md")]) == 1
    assert "not found" in capsys.readouterr().err


def test_atom_io_cli_source_action(world, monkeypatch, capsys):
    import io
    from lib import atom_io_cli
    atom = _atom(world["atoms"] / "card-bridge.md", source="unknown 2026-09-01（原對話已逾保留期）")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"action": "source", "atom": str(atom)})))
    assert atom_io_cli.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and out["extra"]["state"] == "unrecoverable"
    monkeypatch.setattr(provenance, "_locate_atom_path", lambda atom, cwd, warnings: None)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"action": "source", "atom": "ghost"})))
    assert atom_io_cli.main() == 1
    out = json.loads(capsys.readouterr().out)
    assert not out["ok"] and "not found" in out["error"]
