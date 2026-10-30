"""verify_token_usage.py — token skill 契約：lib/transcript_tokens.py 的去重與合計、scripts/token_usage.py 的找目標與出口。

守住規則：
- 同一則回覆拆成多行（同 message.id）usage 只算一次；壞行跳過；子代理檔一起算；首末紀錄相隔 → 分鐘。
- session id 前綴在 CLAUDE_CONFIG_DIR/projects/*/ 底下找得到；transcript 路徑直接吃。
- 不給目標：有 CLAUDE_CODE_SESSION_ID 用它；沒有就用 cwd 對應的專案資料夾裡最近改過的那份，並印出選了哪份。
- 找不到、前綴對到多份 → exit 1、沒有 DONE 行；成功尾行 `TOKENS DONE sessions=<n>`。
怎麼跑：python -X utf8 -m pytest -q skills/token/verify/verify_token_usage.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = CODE_ROOT / "skills" / "token" / "scripts" / "token_usage.py"
sys.path.insert(0, str(CODE_ROOT))
from lib.transcript_tokens import find_transcripts, session_totals  # noqa: E402

SID = "1234abcd-0000-4000-8000-000000000001"
SID2 = "1234abff-0000-4000-8000-000000000002"
DONE_RE = re.compile(r"^[A-Z][A-Z0-9_]* DONE( \w+=\S+)*$")
U_A = {"input_tokens": 10, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 50, "output_tokens": 5}
U_B = {"input_tokens": 1, "cache_read_input_tokens": 200, "cache_creation_input_tokens": 0, "output_tokens": 7}
U_C = {"input_tokens": 2, "cache_read_input_tokens": 20, "cache_creation_input_tokens": 3, "output_tokens": 4}


def _assistant(msg_id: str, usage: dict, ts: str, block: dict) -> dict:
    return {"type": "assistant", "timestamp": ts, "uuid": f"u-{msg_id}-{block['type']}",
            "message": {"id": msg_id, "role": "assistant", "content": [block], "usage": usage}}


def _write_jsonl(path: Path, rows: list, extra_lines: tuple = ()) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in rows] + list(extra_lines)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _fixture(project: Path, sid: str = SID) -> Path:
    """主 transcript：msg_A 拆三行（同 usage）、msg_B 一行、一行壞 JSON；子代理一檔 msg_C；首末相隔 30 分鐘。"""
    tx = _write_jsonl(project / f"{sid}.jsonl", [
        {"type": "user", "timestamp": "2026-10-30T01:00:00.000Z", "message": {"role": "user", "content": "hi"}},
        _assistant("msg_A", U_A, "2026-10-30T01:00:05.000Z", {"type": "thinking", "thinking": "..."}),
        _assistant("msg_A", U_A, "2026-10-30T01:00:06.000Z", {"type": "text", "text": "ok"}),
        _assistant("msg_A", U_A, "2026-10-30T01:00:07.000Z", {"type": "tool_use", "name": "Read", "input": {}}),
        _assistant("msg_B", U_B, "2026-10-30T01:30:00.000Z", {"type": "text", "text": "done"}),
    ], extra_lines=("{not json",))
    _write_jsonl(project / sid / "subagents" / "agent-x.jsonl", [
        _assistant("msg_C", U_C, "2026-10-30T01:10:00.000Z", {"type": "text", "text": "sub"}),
    ])
    return tx


def _run(args: list, config_dir: Path, cwd: Path, session_id: str | None = None):
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CONFIG_DIR", "CLAUDE_CODE_SESSION_ID")}
    env.update({"CLAUDE_CONFIG_DIR": str(config_dir), "PYTHONIOENCODING": "utf-8"})
    if session_id:
        env["CLAUDE_CODE_SESSION_ID"] = session_id
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


def _json_out(stdout: str) -> dict:
    lines = stdout.strip().splitlines()
    assert DONE_RE.match(lines[-1]), lines[-1]
    return json.loads("\n".join(lines[:-1]))


EXPECTED = {"replies": 3, "input_uncached": 13, "cache_read": 320, "cache_create": 53, "output": 16,
            "input": 386, "total": 402, "subagent_files": 1, "minutes": 30.0}


def test_totals_dedupe_by_message_id_and_include_subagents(tmp_path):
    tx = _fixture(tmp_path / "projects" / "proj")
    tot = session_totals(tx)
    assert {k: tot[k] for k in EXPECTED} == EXPECTED


def test_find_by_prefix_and_path(tmp_path):
    root = tmp_path / "projects"
    tx = _fixture(root / "proj")
    assert find_transcripts("1234abcd", root) == [tx]
    assert find_transcripts(str(tx), root) == [tx]
    assert find_transcripts("*", root) == []                       # 不是 session id 字元 → 不當 glob 用
    assert find_transcripts(str(tmp_path / "nope.jsonl"), root) == []


def test_script_prefix_lookup_json(tmp_path):
    _fixture(tmp_path / "projects" / "proj")
    r = _run(["1234abcd", "--json"], tmp_path, tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().splitlines()[-1] == "TOKENS DONE sessions=1"
    row = _json_out(r.stdout)["sessions"][0]
    assert {k: row[k] for k in EXPECTED} == EXPECTED
    assert row["label"] == "1234abcd"


def test_script_two_paths_table(tmp_path):
    a = _fixture(tmp_path / "projects" / "proj")
    b = _fixture(tmp_path / "projects" / "proj", SID2)
    r = _run([str(a), str(b)], tmp_path, tmp_path)
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert lines[-1] == "TOKENS DONE sessions=2"
    assert sum(1 for ln in lines if "402" in ln and "386" in ln) == 2


def test_script_default_uses_session_env(tmp_path):
    _fixture(tmp_path / "projects" / "proj")
    r = _run([], tmp_path, tmp_path, session_id=SID)
    assert r.returncode == 0, r.stderr
    assert "CLAUDE_CODE_SESSION_ID" in r.stdout.splitlines()[0]
    assert r.stdout.strip().splitlines()[-1] == "TOKENS DONE sessions=1"


def test_script_default_falls_back_to_latest_in_cwd_project(tmp_path):
    work = tmp_path / "work dir"
    work.mkdir()
    project = tmp_path / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(work))
    old = _fixture(project, SID)
    new = _fixture(project, SID2)
    os.utime(old, (1_000_000, 1_000_000))
    r = _run([], tmp_path, work)
    assert r.returncode == 0, r.stderr
    assert new.name in r.stdout.splitlines()[0] and old.name not in r.stdout.splitlines()[0]


def test_script_missing_target_exit_1(tmp_path):
    _fixture(tmp_path / "projects" / "proj")
    r = _run(["deadbeef"], tmp_path, tmp_path)
    assert r.returncode == 1
    assert "deadbeef" in r.stdout and "DONE" not in r.stdout


def test_script_ambiguous_prefix_exit_1(tmp_path):
    _fixture(tmp_path / "projects" / "proj", SID)
    _fixture(tmp_path / "projects" / "proj", SID2)
    r = _run(["1234ab"], tmp_path, tmp_path)
    assert r.returncode == 1
    assert "2 份" in r.stdout and "DONE" not in r.stdout
