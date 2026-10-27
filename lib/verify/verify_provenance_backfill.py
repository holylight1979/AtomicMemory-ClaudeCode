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
        _human("h7", None, "2026-10-03T09:00:00Z", "把這條記成卡片乙", sid=SID2),
        _tool_use("a7", "h7", "2026-10-03T09:00:05Z", "t7", "卡片乙", sid=SID2),
        _tool_result("r7", "a7", "2026-10-03T09:00:06Z", "t7", str(atom_b), ok=False, sid=SID2),
        _tool_use("a8", "r7", "2026-10-03T09:00:10Z", "t8", "卡片乙", sid=SID2),
        _tool_result("r8", "a8", "2026-10-03T09:00:11Z", "t8", str(atom_b), sid=SID2),
    ]
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", recs)
    r = _run(world, atoms=[("root", atom_b)])["results"][0]
    assert r["grade"] == "A" and r["hit"]["uuid"] == "h7" and r["quote"] == "「把這條記成卡片乙」"


def test_003_short_human_reply_is_not_quote(world):
    # 003：回填找到的真人訊息是「A」這種一兩個字的回覆 → 不寫 Quote（A_noquote、too_short），Source 照補
    atom_c = _atom(world["mem"] / "設計通則" / "卡片丙.md", "卡片丙")
    recs = [
        _human("h9", None, "2026-10-04T09:00:00Z", "A", sid=SID2),
        _tool_use("a9", "h9", "2026-10-04T09:00:05Z", "t9", "卡片丙", sid=SID2),
        _tool_result("r9", "a9", "2026-10-04T09:00:06Z", "t9", str(atom_c), sid=SID2),
    ]
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", recs)
    r = _run(world, apply=True, atoms=[("root", atom_c)])["results"][0]
    text = atom_c.read_text(encoding="utf-8")
    assert r["grade"] == "A_noquote" and r.get("quote_skipped") == "too_short", r
    assert "- Quote:" not in text and "- Source: session:22222222#h9 2026-10-04" in text


def test_003_caller_cleared_quote_is_not_backfilled(world):
    # 003（codex 審）：呼叫者 replace 時明傳 quote="" 清空，背景回填找到那則原話也不補回；Source 照補。對照：沒傳 quote 照補
    atom_d = _atom(world["mem"] / "設計通則" / "卡片丁.md", "卡片丁")
    use = _tool_use("a10", "h10", "2026-10-05T09:00:05Z", "t10", "卡片丁", mode="replace", sid=SID2)
    use["message"]["content"][0]["input"]["quote"] = ""
    recs = [_human("h10", None, "2026-10-05T09:00:00Z", "把卡片丁的 Quote 清掉重寫", sid=SID2), use,
            _tool_result("r10", "a10", "2026-10-05T09:00:06Z", "t10", str(atom_d), sid=SID2)]
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", recs)
    r = _run(world, apply=True, atoms=[("root", atom_d)])["results"][0]
    text = atom_d.read_text(encoding="utf-8")
    assert r["grade"] == "A_noquote" and r.get("quote_skipped") == "caller_cleared", r
    assert "- Quote:" not in text and "- Source: session:22222222#h10 2026-10-05" in text
    r2 = _run(world, atoms=[("root", atom_d)])["results"][0]                   # 已有 Source：不寫，理由寫清楚
    assert r2["grade"] == "skip" and r2["reason"] == "caller_cleared_not_quoted", r2
    plain = _atom(world["mem"] / "設計通則" / "卡片戊.md", "卡片戊")
    _write_jsonl(world["projects"] / "slug2" / f"{SID2}.jsonl", [
        _human("h11", None, "2026-10-05T10:00:00Z", "把卡片戊記下來，原因寫清楚", sid=SID2),
        _tool_use("a11", "h11", "2026-10-05T10:00:05Z", "t11", "卡片戊", mode="replace", sid=SID2),
        _tool_result("r11", "a11", "2026-10-05T10:00:06Z", "t11", str(plain), sid=SID2)])
    r3 = _run(world, atoms=[("root", plain)])["results"][0]
    assert r3["grade"] == "A" and r3["quote"] == "「把卡片戊記下來，原因寫清楚」", r3


KICKOFF = ("你是 v6.0 的工作 session track-x（共用檔同步），總控台是 claude-9f。"
           "第一步用 EnterWorktree 切進 worktree C:\\wt\\x。派工 prompt 在 C:\\inbox\\000.md，用絕對路徑讀完全文照做。")


def _kickoff_world(world, peer_turn=True):
    """工作分頁：開工句是唯一的真人訊息；之後是同伴訊息開的回合（不是真人），atom_write 在那回合。
    回填沿 parentUuid 往回走會走到開工句。"""
    recs = [_human("k1", None, "2026-10-05T09:00:00Z", KICKOFF, sid=SID2)]
    parent = "k1"
    if peer_turn:
        recs.append(_rec("p1", "k1", "2026-10-05T09:30:00Z", "user",
                         [{"type": "text", "text": '<cross-session-message from="uds:x" from-name="claude-9f">寫卡</cross-session-message>'}],
                         sid=SID2, origin={"kind": "peer"}))
        parent = "p1"
    recs += [_tool_use("a9", parent, "2026-10-05T09:30:05Z", "t9", "卡片丙", sid=SID2),
             _tool_result("r9", "a9", "2026-10-05T09:30:06Z", "t9", str(world["mem"] / "設計通則" / "卡片丙.md"), sid=SID2)]
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", recs)
    return _atom(world["mem"] / "設計通則" / "卡片丙.md", "卡片丙")


@pytest.mark.parametrize("peer_turn", [True, False])
def test_005_kickoff_is_not_used_as_quote(world, peer_turn):
    # 005：回填找到的真人訊息是開工句 → 不寫 Quote（A_noquote），Source 照補（指到那則真人訊息）
    atom = _kickoff_world(world, peer_turn)
    rep = _run(world, apply=True, atoms=[("root", atom)])
    r = rep["results"][0]
    text = atom.read_text(encoding="utf-8")
    assert "- Quote:" not in text, f"開工句被回填成 Quote：{text}"
    assert r["grade"] == "A_noquote" and r.get("quote_skipped") == "kickoff", r
    assert "- Source: session:22222222#k1 2026-10-05\n" in text and r["written"] is True
    assert rep["summary"]["A_noquote"] == 1 and rep["summary"]["A"] == 0 and rep["summary"]["skip"] == 0


def test_005_kickoff_with_existing_source_is_skipped_with_reason(world):
    atom = _kickoff_world(world)
    _atom(atom, "卡片丙", extra="- Source: commit:abc1234 2026-03-02（原對話已逾保留期）\n")
    before = atom.read_bytes()
    r = _run(world, apply=True, atoms=[("root", atom)])["results"][0]
    assert r["grade"] == "skip" and r["reason"] == "kickoff_not_quoted", r
    assert atom.read_bytes() == before


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
    assert r["quote"] is None                                       # 指到的是 AI 的話：只補 Source，Quote 只放使用者原話
    r = _run(world, apply=True, atoms=[("root", a)])["results"][0]
    text = a.read_text(encoding="utf-8")
    assert r["written"] and "- Source: session:22222222#ab12cd34 2026-10-05" in text and "- Quote:" not in text


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


# 樣板認不出的開工句（角色句不是「工作 session／工作軌」，後面也沒有第一步 EnterWorktree）
UNRECOGNIZED_KICKOFF = ("你是這個專案的「值班」session（新任，接前一位）。"
                        "職責：審查、合併、推送。先讀接續單 C:\\inbox\\next.md。")


def _peer(uuid, parent, ts, body="寫卡", sid=SID2, kind="peer"):
    return _rec(uuid, parent, ts, "user",
                f'Another Claude session sent a message:\n<cross-session-message from="uds:x">{body}</cross-session-message>',
                sid=sid, origin={"kind": kind}, isMeta=True)


def test_peer_turn_does_not_quote_unrecognized_kickoff(world):
    # 寫卡那回合是同伴訊息開的 → 往回走越過它走到的真人訊息（樣板認不出的開工句）不得當 Quote；Source 照補
    from lib.provenance import is_kickoff_text
    assert not is_kickoff_text(UNRECOGNIZED_KICKOFF), "前提：這句開工句樣板認不出（認得出就測不到回合歸屬）"
    atom = _atom(world["mem"] / "設計通則" / "卡片辛.md", "卡片辛")
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", [
        _human("k1", None, "2026-10-05T09:00:00Z", UNRECOGNIZED_KICKOFF, sid=SID2),
        _peer("p1", "k1", "2026-10-05T09:30:00Z"),
        _tool_use("a1", "p1", "2026-10-05T09:30:05Z", "t1", "卡片辛", sid=SID2),
        _tool_result("r1", "a1", "2026-10-05T09:30:06Z", "t1", str(atom), sid=SID2)])
    r = _run(world, apply=True, atoms=[("root", atom)])["results"][0]
    text = atom.read_text(encoding="utf-8")
    assert "- Quote:" not in text, f"同伴訊息開的回合把開工句回填成 Quote：{text}"
    assert r["grade"] == "A_noquote" and r.get("quote_skipped") == "not_user_turn", r
    assert "- Source: session:22222222#k1 2026-10-05\n" in text


def test_task_notification_turn_is_not_user_turn(world):
    # 背景任務通知開的回合同樣不是使用者開的：前一回合使用者的話不是這張卡的觸發句
    atom = _atom(world["mem"] / "設計通則" / "卡片壬.md", "卡片壬")
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", [
        _human("h1", None, "2026-10-05T09:00:00Z", "跑背景測試，跑完告訴我結果", sid=SID2),
        _rec("n1", "h1", "2026-10-05T09:20:00Z", "user", "<task-notification>done</task-notification>",
             sid=SID2, origin={"kind": "task-notification"}),
        _tool_use("a1", "n1", "2026-10-05T09:20:05Z", "t1", "卡片壬", sid=SID2),
        _tool_result("r1", "a1", "2026-10-05T09:20:06Z", "t1", str(atom), sid=SID2)])
    r = _run(world, atoms=[("root", atom)])["results"][0]
    assert r["grade"] == "A_noquote" and r.get("quote_skipped") == "not_user_turn" and r["quote"] is None, r


def test_stop_hook_feedback_is_same_turn(world):
    # 對照：沒有 origin 的 meta 紀錄（Stop hook 回饋）是同一回合的延續，越過它照樣用使用者原話
    atom = _atom(world["mem"] / "設計通則" / "卡片癸.md", "卡片癸")
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", [
        _human("h1", None, "2026-10-05T09:00:00Z", "把這次的踩坑記成卡片", sid=SID2),
        _rec("m1", "h1", "2026-10-05T09:05:00Z", "user", "Stop hook feedback:\n[Guardian:X] …", sid=SID2, isMeta=True),
        _tool_use("a1", "m1", "2026-10-05T09:05:05Z", "t1", "卡片癸", sid=SID2),
        _tool_result("r1", "a1", "2026-10-05T09:05:06Z", "t1", str(atom), sid=SID2)])
    r = _run(world, atoms=[("root", atom)])["results"][0]
    assert r["grade"] == "A" and r["quote"] == "「把這次的踩坑記成卡片」", r


def test_sidechain_fallback_respects_peer_turn(world):
    # 子代理寫卡（走不回主線）退回主線 ts≤hit 最近一則：主線最近開回合的是同伴訊息 → 不寫 Quote
    atom = _atom(world["mem"] / "設計通則" / "卡片子.md", "卡片子")
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", [
        _human("k1", None, "2026-10-05T09:00:00Z", UNRECOGNIZED_KICKOFF, sid=SID2),
        _peer("p1", "k1", "2026-10-05T09:30:00Z", body="請子代理代寫卡片"),
        _tool_use("s1", None, "2026-10-05T09:31:00Z", "ts1", "卡片子", sid=SID2, isSidechain=True),
        _tool_result("s2", "s1", "2026-10-05T09:31:01Z", "ts1", str(atom), sid=SID2)])
    r = _run(world, atoms=[("root", atom)])["results"][0]
    assert r["grade"] == "A_noquote" and r.get("quote_skipped") == "not_user_turn", r


def test_empty_quote_and_source_lines_do_not_read_next_line(world):
    # 空的 `- Quote:` 行不算已有 Quote（舊判法 `\s*\S` 跨行吃到下一行的 `-`，整張被當 has_quote 跳過）；
    # 空的 `- Source:` 行不算已有 Source（舊判法把下一行當成既有來源，Source 就不補）
    _atom(world["atom"], "卡片甲", extra="- Source:\n- Quote:\n")
    r = _run(world, apply=True)["results"][0]
    text = world["atom"].read_text(encoding="utf-8")
    assert r["grade"] == "A" and r.get("reason") != "has_quote", r
    assert "- Source: session:11111111#h1 2026-10-01\n" in text and "- Quote: 「請把 這條 記成卡片甲」\n" in text, text
    assert text.count("- Quote:") == 1 and text.count("- Source:") == 1


def test_broken_chain_after_peer_turn_keeps_not_user_turn(world):
    # 回溯先越過同伴訊息（在 sidechain 上，不進主線的開回合清單）、接著斷鏈退主線：主線最近開回合的是真人也不能當 Quote
    # （越過別人回合的證據要帶著）
    atom = _atom(world["mem"] / "設計通則" / "卡片丑.md", "卡片丑")
    peer = _peer("p1", "gone", "2026-10-05T09:30:00Z", body="請寫卡")
    peer["isSidechain"] = True
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", [
        _human("h1", None, "2026-10-05T09:00:00Z", "主線上使用者說的另一件事情", sid=SID2),
        peer,
        _tool_use("a1", "p1", "2026-10-05T09:30:05Z", "t1", "卡片丑", sid=SID2),
        _tool_result("r1", "a1", "2026-10-05T09:30:06Z", "t1", str(atom), sid=SID2)])
    r = _run(world, atoms=[("root", atom)])["results"][0]
    assert r["grade"] == "A_noquote" and r.get("quote_skipped") == "not_user_turn" and r["quote"] is None, r


def test_plain_string_prompt_opens_a_turn(world):
    # 內容是純字串、沒有 origin 的提示（程式用 -p 送的這類，is_human_record 否）也開了新回合：不能越過它拿更早那則真人訊息當 Quote
    atom = _atom(world["mem"] / "設計通則" / "卡片寅.md", "卡片寅")
    _write_jsonl(world["projects"] / "slug" / f"{SID2}.jsonl", [
        _human("h1", None, "2026-10-05T09:00:00Z", "很早以前的另一則使用者訊息", sid=SID2),
        _rec("s1", "h1", "2026-10-05T09:30:00Z", "user", "只做一件事：把這次的結論記成卡片", sid=SID2),
        _tool_use("a1", "s1", "2026-10-05T09:30:05Z", "t1", "卡片寅", sid=SID2),
        _tool_result("r1", "a1", "2026-10-05T09:30:06Z", "t1", str(atom), sid=SID2)])
    r = _run(world, atoms=[("root", atom)])["results"][0]
    assert r["grade"] == "A_noquote" and r.get("quote_skipped") == "not_user_turn", r
