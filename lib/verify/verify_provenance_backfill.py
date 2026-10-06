"""verify_provenance_backfill — 舊 atom 來源回填：匹配、分級、冪等、消毒、觸發判定。

跑法：python -m pytest -q lib/verify/verify_provenance_backfill.py
全部在 tmp_path 造假 transcript 與 atom；不碰真實 projects/ 與 memory/。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent
for p in (str(CLAUDE_DIR), str(CLAUDE_DIR / "hooks")):
    if p not in sys.path:
        sys.path.insert(0, p)

_spec = importlib.util.spec_from_file_location("atom_provenance_backfill", CLAUDE_DIR / "tools" / "atom-provenance-backfill.py")
bf = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["atom_provenance_backfill"] = bf
_spec.loader.exec_module(bf)  # type: ignore[union-attr]

SID = "11111111-aaaa-bbbb-cccc-000000000001"
SID2 = "22222222-aaaa-bbbb-cccc-000000000002"


def _rec(uuid, parent, ts, type_, content, sid=SID, **extra):
    r = {"uuid": uuid, "parentUuid": parent, "timestamp": ts, "sessionId": sid, "type": type_,
         "message": {"role": "user" if type_ == "user" else "assistant", "content": content}}
    r.update(extra)
    return r


def _human(uuid, parent, ts, text, sid=SID, **extra):
    return _rec(uuid, parent, ts, "user", [{"type": "text", "text": text}], sid=sid, origin={"kind": "human"}, **extra)


def _tool_use(uuid, parent, ts, tid, title, mode="create", sid=SID, **extra):
    return _rec(uuid, parent, ts, "assistant",
                [{"type": "tool_use", "id": tid, "name": "mcp__workflow-guardian__atom_write",
                  "input": {"title": title, "mode": mode}}], sid=sid, **extra)


def _tool_result(uuid, parent, ts, tid, path, ok=True, sid=SID):
    text = f"Created atom: {Path(path).name} ([臨], scope=global)\nPath: {path}\n" if ok else "Error: write-gate rejected"
    blk = {"type": "tool_result", "tool_use_id": tid, "content": [{"type": "text", "text": text}]}
    if not ok:
        blk["is_error"] = True
    return _rec(uuid, parent, ts, "user", [blk], sid=sid)


def _write_jsonl(path: Path, recs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")


ATOM_TPL = """# {title}

- Scope: global
- Author: alice
{extra}- Confidence: [臨]
- Trigger: a, b
- Created-at: {created}

## 知識

- [臨] 內容
{body}
## 行動

- （依知識內容判斷）
"""


def _atom(path: Path, title: str, created="2026-09-01", extra="", body=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ATOM_TPL.format(title=title, created=created, extra=extra, body=body), encoding="utf-8", newline="\n")
    return path


@pytest.fixture
def world(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    mem = tmp_path / "memory"
    monkeypatch.setattr(bf, "AUDIT_LOG", tmp_path / "audit.jsonl")
    monkeypatch.setattr(bf, "MARKER_PATH", tmp_path / "marker.json")
    atom = _atom(mem / "設計通則" / "卡片甲.md", "卡片甲")
    recs = [
        _human("h0", None, "2026-10-01T09:00:00Z", "先講點別的"),
        _human("h1", "h0", "2026-10-01T09:01:00Z", "<system-reminder>x</system-reminder>\n請把  這條\n記成卡片甲"),
        _tool_use("a1", "h1", "2026-10-01T09:01:05Z", "t1", "卡片甲"),
        _tool_result("r1", "a1", "2026-10-01T09:01:06Z", "t1", str(atom)),
    ]
    _write_jsonl(projects / "slug" / f"{SID}.jsonl", recs)
    return {"projects": projects, "mem": mem, "atom": atom, "tmp": tmp_path}


def _run(world, apply=False, atoms=None, only=None):
    atoms = atoms if atoms is not None else [("root", world["atom"])]
    return bf.backfill(apply=apply, projects_dir=world["projects"], atoms=atoms, only=only)


def test_01_single_create_hit_A(world):
    rep = _run(world)
    r = rep["results"][0]
    assert r["grade"] == "A", r
    assert r["source"] == "session:11111111#h1 2026-10-01"
    assert r["quote"] == "「請把 這條 記成卡片甲」"
    assert rep["summary"]["A"] == 1 and rep["summary"]["apply"] is False
    assert "- Quote:" not in world["atom"].read_text(encoding="utf-8")  # dry-run 不寫


def test_02_apply_writes_and_is_idempotent(world):
    rep = _run(world, apply=True)
    assert rep["results"][0]["written"] is True
    text = world["atom"].read_text(encoding="utf-8")
    assert "- Source: session:11111111#h1 2026-10-01\n" in text and "- Quote: 「請把 這條 記成卡片甲」\n" in text
    before = world["atom"].read_bytes()
    rep2 = _run(world, apply=True)
    assert rep2["results"][0]["grade"] == "skip" and rep2["results"][0]["reason"] == "has_quote"
    assert world["atom"].read_bytes() == before


def test_03_replace_after_create_picks_create_earliest(world):
    recs = [
        _human("h5", None, "2026-10-02T09:00:00Z", "改一下", sid=SID2),
        _tool_use("a5", "h5", "2026-10-02T09:00:05Z", "t5", "卡片甲", mode="replace", sid=SID2),
        _tool_result("r5", "a5", "2026-10-02T09:00:06Z", "t5", str(world["atom"]), sid=SID2),
    ]
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", recs)
    r = _run(world)["results"][0]
    assert r["source"].startswith("session:11111111#h1") and r["hit"]["mode"] == "create"


def test_04_failed_then_retry_only_success_counts(world):
    atom_b = _atom(world["mem"] / "設計通則" / "卡片乙.md", "卡片乙")
    recs = [
        _human("h7", None, "2026-10-03T09:00:00Z", "記卡片乙", sid=SID2),
        _tool_use("a7", "h7", "2026-10-03T09:00:05Z", "t7", "卡片乙", sid=SID2),
        _tool_result("r7", "a7", "2026-10-03T09:00:06Z", "t7", str(atom_b), ok=False, sid=SID2),
        _tool_use("a8", "r7", "2026-10-03T09:00:10Z", "t8", "卡片乙", sid=SID2),
        _tool_result("r8", "a8", "2026-10-03T09:00:11Z", "t8", str(atom_b), sid=SID2),
    ]
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", recs)
    r = _run(world, atoms=[("root", atom_b)])["results"][0]
    assert r["grade"] == "A" and r["hit"]["uuid"] == "h7" and r["quote"] == "「記卡片乙」"


def test_05_existing_source_kept_only_quote_added(world):
    _atom(world["atom"], "卡片甲", extra="- Source: C:/x/transcript.md\n")
    rep = _run(world, apply=True)
    r = rep["results"][0]
    assert r["grade"] == "A" and r["source"] is None and r["quote"]
    text = world["atom"].read_text(encoding="utf-8")
    assert text.count("- Source:") == 1 and "- Source: C:/x/transcript.md\n" in text and "- Quote: 「" in text


def test_06_moved_atom_matches_by_basename(world):
    moved = world["mem"] / "Failures" / "工作流" / "卡片甲.md"
    moved.parent.mkdir(parents=True)
    moved.write_bytes(world["atom"].read_bytes())
    world["atom"].unlink()
    r = _run(world, atoms=[("root", moved)])["results"][0]
    assert r["grade"] == "A"


def test_07_same_basename_two_layers_is_ambiguous(world):
    other = _atom(world["tmp"] / "proj" / ".claude" / "memory" / "shared" / "卡片甲.md", "卡片甲")
    rep = _run(world, atoms=[("root", world["atom"]), ("project", other)])
    grades = {Path(r["path"]).as_posix(): (r["grade"], r["reason"]) for r in rep["results"]}
    # transcript 的 Path 指向根層那顆 → 根層精確命中 A；專案層同名無精確命中 → ambiguous 不寫
    assert grades[world["atom"].as_posix()][0] == "A"
    assert grades[other.as_posix()] == ("skip", "ambiguous")
    assert rep["summary"]["ambiguous"] == 1


def test_08_sidechain_falls_back_to_mainline_human(world):
    atom_c = _atom(world["mem"] / "設計通則" / "卡片丙.md", "卡片丙")
    recs = [
        _human("m1", None, "2026-10-04T09:00:00Z", "主線：子代理去寫卡片丙", sid=SID2),
        _tool_use("s1", None, "2026-10-04T09:00:30Z", "ts1", "卡片丙", sid=SID2, isSidechain=True),
        _tool_result("s2", "s1", "2026-10-04T09:00:31Z", "ts1", str(atom_c), sid=SID2),
    ]
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", recs)
    r = _run(world, atoms=[("root", atom_c)])["results"][0]
    assert r["grade"] == "A" and r["quote"] == "「主線：子代理去寫卡片丙」" and r["hit"]["uuid"] == "m1"


def test_09_quote_sanitized_single_line_and_capped(world):
    long = "一" * 150 + "\n" + "一" * 150
    recs = [
        _human("h9", None, "2026-10-05T09:00:00Z", "「" + long + "」", sid=SID2),
        _tool_use("a9", "h9", "2026-10-05T09:00:05Z", "t9", "卡片甲", sid=SID2),
        _tool_result("r9", "a9", "2026-10-05T09:00:06Z", "t9", str(world["atom"]), sid=SID2),
    ]
    (world["projects"] / "slug" / f"{SID}.jsonl").unlink()
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", recs)
    r = _run(world)["results"][0]
    assert "\n" not in r["quote"] and r["quote"].startswith("「一") and r["quote"].endswith("…」")
    assert len(r["quote"]) <= 202


def test_10_no_hit_B_level_created_at_then_git_then_mtime(world, tmp_path):
    (world["projects"] / "slug" / f"{SID}.jsonl").unlink()
    # Created-at 存在 → 用它；非 git → unknown
    r = _run(world)["results"][0]
    assert r["grade"] == "B" and r["source"] == "unknown 2026-09-01（原對話已逾保留期）" and r["date_src"] == "created_at"
    # git repo 裡 → commit:<hash7>
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    g_atom = _atom(repo / "memory" / "x" / "卡片丁.md", "卡片丁", created="")
    text = g_atom.read_text(encoding="utf-8").replace("- Created-at: \n", "")
    g_atom.write_text(text, encoding="utf-8", newline="\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "add"], cwd=repo, check=True)
    r = _run(world, atoms=[("root", g_atom)])["results"][0]
    assert r["grade"] == "B" and r["source"].startswith("commit:") and r["date_src"] == "git"
    # 沒 Created-at、非 git → mtime
    m_atom = _atom(tmp_path / "loose" / "卡片戊.md", "卡片戊", created="")
    m_atom.write_text(m_atom.read_text(encoding="utf-8").replace("- Created-at: \n", ""), encoding="utf-8", newline="\n")
    r = _run(world, atoms=[("root", m_atom)])["results"][0]
    assert r["grade"] == "B" and r["date_src"] == "mtime"


def test_11_src_comment_atom_becomes_A_ai(world):
    recs = [
        _human("h11", None, "2026-10-05T09:00:00Z", "人話", sid=SID2),
        _rec("ab12cd34-0000-0000-0000-000000000000", "h11", "2026-10-05T09:00:05Z", "assistant",
             [{"type": "text", "text": "這是 AI 的失敗片段"}], sid=SID2),
    ]
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", recs)
    a = _atom(world["mem"] / "Failures" / "x" / "feedback-卡片己.md", "feedback-卡片己", body="  <!-- src: 22222222#ab12cd34 -->\n")
    r = _run(world, atoms=[("root", a)])["results"][0]
    assert r["grade"] == "A_ai" and r["source"] == "session:22222222#ab12cd34 2026-10-05"
    assert r["quote"] == "「AI：這是 AI 的失敗片段」"


def test_12_no_weak_match_same_day_prompt_without_tool_use(world):
    atom_z = _atom(world["mem"] / "設計通則" / "卡片庚.md", "卡片庚", created="2026-10-01")
    r = _run(world, atoms=[("root", atom_z)])["results"][0]
    assert r["grade"] == "B"  # 同日有真人訊息也不配


def test_13_bad_lines_meta_and_notification_ignored(world):
    p = world["projects"] / "slug" / f"{SID}.jsonl"
    extra = [
        "{not json",
        json.dumps(_rec("x1", None, "2026-10-01T08:00:00Z", "user", "meta", isMeta=True)),
        json.dumps(_rec("x2", None, "2026-10-01T08:00:01Z", "user", "<task-notification>…</task-notification>",
                        origin={"kind": "task-notification"})),
    ]
    p.write_text("\n".join(extra) + "\n" + p.read_text(encoding="utf-8"), encoding="utf-8")
    idx = bf.build_transcript_index(world["projects"])
    assert idx.bad_lines == 1
    assert not idx.by_uuid["x1"]["human"] and not idx.by_uuid["x2"]["human"]
    r = _run(world)["results"][0]
    assert r["grade"] == "A" and r["hit"]["uuid"] == "h1"


def test_14_only_glob_and_needs_run_marker(world):
    rep = _run(world, only=["*/不存在/*"])
    assert rep["summary"]["atoms"] == 0
    assert bf.needs_run(world["projects"], bf.MARKER_PATH) is True
    bf._write_marker({"A": 1}, world["projects"], bf.MARKER_PATH)
    assert bf.needs_run(world["projects"], bf.MARKER_PATH) is False
    _write_jsonl(world["projects"] / "slug" / "new.jsonl", [_human("n1", None, "2026-10-06T00:00:00Z", "新")])
    import os, time
    os.utime(world["projects"] / "slug" / "new.jsonl", (time.time() + 5, time.time() + 5))
    assert bf.needs_run(world["projects"], bf.MARKER_PATH) is True
    assert bf.needs_run(world["tmp"] / "empty", bf.MARKER_PATH) is False
