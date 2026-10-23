"""verify_unknown_write_recover.py：規則 UNKNOWN_WRITE_RECOVERED——Bash／PowerShell 寫入目標判不出的指令跑完後，從版控狀態補出真的改了哪些檔。

做什麼：真 git repo（pytest tmp）裡照 AI 的寫法用內嵌 python 改檔（`python -I -c "…"`、`python -I - <<'EOF' … EOF` 再 exit 1），
走真的 PostToolUse／PostToolUseFailure 入口，驗：
- 改到的檔與新建的未追蹤檔進 modified_files（via=vcs_status、本回合、tool=Bash），那一筆 unknown_writes 記 recovered；
- 快照前就髒、這次沒動的檔不算；快照前就髒、這次又改了的照算；本 session 記過、內容沒變的檔不刷成本回合改的；
- 不在版控、找不到指令開始時間 → 不補，那一筆寫明 unrecovered；裁判子 session 一樣補；補到的檔交目標樹蓋號；
- 整棵 status 逾時 → 只查指令點名的檔，同 session 之後該根直接走點名；svn（真 svn 工作副本＋--xml 解析，未納管目錄往下展開）。
三道收尾閘吃補進來的檔，案例在各閘自己的檔（都用本檔的 init_repo／bash_unknown_write 產 state）：
對帳 verify_stop_reconcile.py、第二意見 verify_g9_second_opinion.py、同步提醒 verify_sync_reminder_later_turn.py。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_unknown_write_recover.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

from handlers import post_tool_use as pt  # noqa: E402
import wg_unknown_write as uw  # noqa: E402
from wg_core import write_paths_from_tool  # noqa: E402
from wg_release_rules import canon_path  # noqa: E402

_SID = "sid-unk"
NOTIFY = {
    "README.md": "# notify\n\n- send() 失敗重試 3 次。\n",
    "notify/__init__.py": "",
    "notify/sender.py": "MAX_RETRIES = 3\n\n\ndef send(msg):\n    return True\n",
    "notify/format.py": "def format_message(text):\n    return text.strip()\n",
    "tests/test_format.py": "from notify.format import format_message\n\n\ndef test_strip():\n    assert format_message(' a ') == 'a'\n",
}
# AI 的寫法：先 cd 到專案、再用內嵌 python 讀改寫（open 的路徑是變數 → 寫入目標判不出）
PY_C_SENDER = ("p='notify/sender.py'\ns=open(p,encoding='utf-8').read()\n"
               "open(p,'w',encoding='utf-8').write(s.replace('MAX_RETRIES = 3','MAX_RETRIES = 6'))\n")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(repo), *args], check=True, capture_output=True)


def init_repo(root: Path, files: Dict[str, str]) -> Path:
    """真 git repo：寫入 files 並提交一次。"""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


def msys(p: Path) -> str:
    """C:\\x\\y → /c/x/y（AI 在 Bash 裡 cd 的寫法）。"""
    s = str(p).replace("\\", "/")
    return f"/{s[0].lower()}{s[2:]}" if len(s) > 1 and s[1] == ":" else s


def py_c(repo: Path, code: str) -> str:
    return f'cd {msys(repo)} && python -I -c "\n{code}"'


def heredoc(code: str, tail: str = "") -> str:
    return f"python -I - <<'EOF'\n{code}EOF\n{tail}"


def stale(path: Path, text: Optional[str] = None, age_s: float = 3600) -> None:
    """快照前就髒：（改寫內容後）把 mtime 拉回 age_s 秒前。"""
    if text is not None:
        path.write_text(text, encoding="utf-8", newline="\n")
    t = time.time() - age_s
    os.utime(path, (t, t))


def bash_unknown_write(monkeypatch, repo: Path, state: Dict[str, Any], command: str, effect: str, *, failure: bool = False,
                       sid: str = _SID, tool: str = "Bash", transcript: bool = True, cwd: Optional[Path] = None,
                       flushed: bool = True) -> Tuple[Dict[str, Any], List[Tuple[str, Dict[str, Any]]]]:
    """照 AI 的寫法跑一次判不出目標的寫入：先確認 command 的寫入目標真的判不出（UNKNOWN），transcript 記這次 tool_use 的時戳
    （flushed=False：同一則回覆平行送出的第一個工具跑完時，這則的紀錄還沒落盤——transcript 只有更早的一筆使用者紀錄），
    再在 repo 裡真的跑 effect（python 程式碼，改檔；failure=True 時它自己 exit 1），最後把 command 交給真的 PostToolUse
    （failure=True 走 PostToolUseFailure）。回 (state, 守門紀錄)。"""
    where = str(cwd or repo)
    targets = write_paths_from_tool(tool, {"command": command}, where)
    assert targets and targets[0].startswith("UNKNOWN:"), targets          # 前提：舊碼就是在這裡什麼都不記
    logs: List[Tuple[str, Dict[str, Any]]] = []                           # 守門紀錄；寫回 state 記成 ("write_state", {})
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: logs.append(("write_state", {})))
    monkeypatch.setattr(pt, "WORKFLOW_DIR", repo.parent / f"wf-{uuid.uuid4().hex[:6]}")
    monkeypatch.setattr(pt, "append_guard_log", lambda name, rec: logs.append((name, rec)))
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_is_ephemeral_path", lambda p: False)        # 專案建在 pytest tmp（系統暫存目錄）底下
    tu = f"tu-{uuid.uuid4().hex[:8]}"
    tr = repo.parent / f"{tu}.jsonl"
    started = datetime.fromtimestamp(time.time() - 0.5, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    rec = ({"type": "assistant", "timestamp": started, "message": {"content": [
        {"type": "tool_use", "id": tu, "name": tool, "input": {"command": command}}]}} if flushed
           else {"type": "user", "timestamp": started, "message": {"role": "user", "content": "照做"}})
    tr.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "-I", "-c", effect], cwd=where, capture_output=True, text=True)
    assert r.returncode == (1 if failure else 0), r.stderr
    inp = {"session_id": sid, "tool_name": tool, "tool_input": {"command": command}, "cwd": where, "tool_use_id": tu,
           "transcript_path": str(tr) if transcript else ""}
    try:
        if failure:
            pt.handle_post_tool_use_failure({**inp, "hook_event_name": "PostToolUseFailure", "error": "Exit code 1\n"}, {})
        else:
            pt.handle_post_tool_use({**inp, "tool_response": {"stdout": "", "stderr": "", "exit_code": 0}},
                                    {"docdrift": {"enabled": False}})
    except SystemExit:
        pass
    return state, logs


def _paths(state: Dict[str, Any]) -> List[str]:
    return [canon_path(m["path"]) for m in state.get("modified_files") or []]


def _entry(state: Dict[str, Any], path: Path) -> Dict[str, Any]:
    return next(m for m in state.get("modified_files") or [] if canon_path(m["path"]) == canon_path(path))


@pytest.fixture()
def repo(tmp_path):
    return init_repo(tmp_path / "qs3-notify", NOTIFY)


def _state(turn: int = 5) -> Dict[str, Any]:
    return {"turn_seq": turn, "session": {"cwd": ""}}


# ─── 會紅案例：成功路徑、失敗路徑 ──────────────────────────────────────────────

def test_python_c_edit_recovered_untouched_dirty_file_not(monkeypatch, repo):
    """補題第一版的寫法：`cd 專案 && python -I -c "…open(p,'w')…"` 改 notify/sender.py → 進 modified_files（via=vcs_status、本回合），
    同步提醒的旗標也立起來；README.md 快照前就髒、這次沒動 → 不算。舊碼：modified_files 空（紅）。"""
    stale(repo / "README.md", "# notify\n\n- 使用者自己改到一半。\n")
    state, logs = bash_unknown_write(monkeypatch, repo, _state(), py_c(repo, PY_C_SENDER), PY_C_SENDER)
    sender = repo / "notify" / "sender.py"
    assert _paths(state) == [canon_path(sender)], state.get("modified_files")
    m = _entry(state, sender)
    assert m["via"] == "vcs_status" and m["tool"] == "Bash" and m["last_turn_seq"] == 5 and m["session_id"] == _SID
    assert state["sync_pending"] is True
    rec = state["unknown_writes"][-1]
    assert [canon_path(p) for p in rec["recovered"]] == [canon_path(sender)] and "unrecovered" not in rec
    hit = [r for n, r in logs if n == "unknown_write"]
    assert hit and hit[0]["recovered"] == 1 and hit[0]["listed"] == 1 and isinstance(hit[0]["ms"], int)


HEREDOC_EDIT = ("def edit(p, old, new):\n"
                "    s = open(p, encoding='utf-8').read()\n"
                "    open(p, 'w', encoding='utf-8').write(s.replace(old, new))\n"
                "edit('notify/format.py', 'text.strip()', 'text.strip().upper()')\n"
                "open('notify/' + 'log.py', 'w').write('import logging\\n')\n")


def test_heredoc_exit1_failure_event_recovered(monkeypatch, repo):
    """heredoc 餵給 python、整條 exit 1（Claude Code 只送 PostToolUseFailure）：改的 format.py 與新建的未追蹤 log.py 都補得到，
    也記一筆未知寫入。舊碼：失敗路徑連未知寫入都不記（紅）。"""
    effect = HEREDOC_EDIT + "raise SystemExit(1)\n"
    state, _ = bash_unknown_write(monkeypatch, repo, _state(), heredoc(HEREDOC_EDIT, "exit 1"), effect, failure=True)
    want = {canon_path(repo / "notify" / "format.py"), canon_path(repo / "notify" / "log.py")}
    assert set(_paths(state)) == want, state.get("modified_files")
    assert all(m["via"] == "vcs_status" for m in state["modified_files"])
    assert len(state["unknown_writes"]) == 1 and len(state["unknown_writes"][0]["recovered"]) == 2


def test_dirty_before_and_rewritten_now_counts(monkeypatch, repo):
    """快照前就髒的檔：這次沒動（README.md）不算；這次又改了內容（format.py）照算。"""
    stale(repo / "README.md", "# notify\n\n- 別人的改動。\n")
    stale(repo / "notify" / "format.py", "def format_message(text):\n    return text\n")
    code = ("p='notify/format.py'\ns=open(p,encoding='utf-8').read()\n"
            "open(p,'w',encoding='utf-8').write(s.replace('return text','return text.strip()'))\n")
    state, _ = bash_unknown_write(monkeypatch, repo, _state(), py_c(repo, code), code)
    assert _paths(state) == [canon_path(repo / "notify" / "format.py")], state.get("modified_files")


def test_recorded_same_content_rewrite_not_bumped(monkeypatch, repo):
    """本 session 第 2 回合就改過 sender.py（記了內容雜湊）；第 5 回合的腳本原樣重寫一次（mtime 變了、內容沒變）→ 不刷成第 5 回合改的。
    （newline=''：Windows 文字模式寫檔會把 LF 換成 CRLF，那是真的改了內容，照算。）"""
    sender = repo / "notify" / "sender.py"
    sender.write_text("MAX_RETRIES = 4\n", encoding="utf-8", newline="\n")
    state = _state(turn=2)
    pt._note_modified(state, _SID, str(sender), "Edit")
    state["turn_seq"] = 5
    code = ("p='notify/sender.py'\ns=open(p,encoding='utf-8',newline='').read()\n"
            "open(p,'w',encoding='utf-8',newline='').write(s)\n")
    state, _ = bash_unknown_write(monkeypatch, repo, state, py_c(repo, code), code)
    m = _entry(state, sender)
    assert m["last_turn_seq"] == 2 and m["count"] == 1 and "via" not in m, m


def test_first_parallel_tool_without_flushed_record_still_recovered(monkeypatch, repo):
    """實跑抓到的：同一則回覆平行送出的第一個工具跑完時，這則的 transcript 紀錄還沒落盤，用 tool_use_id 找不到時戳（12 次漏 3 次，
    其中一支改既有測試的整個沒記到，對帳因此誤擋、觸發斷路器）。改用已落盤的最後一筆紀錄的時間當下界 → 照樣補到、帳上記 start_from。"""
    state, logs = bash_unknown_write(monkeypatch, repo, _state(), py_c(repo, PY_C_SENDER), PY_C_SENDER, flushed=False)
    assert _paths(state) == [canon_path(repo / "notify" / "sender.py")], state.get("unknown_writes")
    assert [r["start_from"] for n, r in logs if n == "unknown_write"] == ["transcript_tail"]


def test_user_edit_one_second_before_start_not_counted(monkeypatch, repo):
    """codex BLOCK 1 的情境：使用者在指令開始前 1 秒改了 README.md（本 session 沒記過它），這條指令只改 sender.py → README 不算。
    （往前放寬原本 2 秒會收進來；實跑量到指令自己寫的檔 mtime 一律晚於自己的時戳，放寬只留 0.05 秒。）"""
    readme = repo / "README.md"
    readme.write_text("# notify\n\n- 使用者剛改的。\n", encoding="utf-8")
    t = time.time() - 1.5                                     # helper 的開始時間是現在減 0.5 秒：這是開始前 1 秒
    os.utime(readme, (t, t))
    state, _ = bash_unknown_write(monkeypatch, repo, _state(), py_c(repo, PY_C_SENDER), PY_C_SENDER)
    assert _paths(state) == [canon_path(repo / "notify" / "sender.py")], state.get("modified_files")


def test_not_in_vcs_or_no_start_time_logged_unrecovered(monkeypatch, tmp_path, repo):
    """不在版控的目錄 → 不補、寫明原因；在 repo 但 transcript 找不到這次 tool_use → 也不補、寫明原因。"""
    plain = tmp_path / "plain"
    (plain / "notify").mkdir(parents=True)
    (plain / "notify" / "sender.py").write_text("MAX_RETRIES = 3\n", encoding="utf-8")
    state, _ = bash_unknown_write(monkeypatch, plain, _state(), py_c(plain, PY_C_SENDER), PY_C_SENDER)
    assert not state.get("modified_files") and "不在 git／svn 工作區" in state["unknown_writes"][-1]["unrecovered"]
    state, _ = bash_unknown_write(monkeypatch, repo, _state(), py_c(repo, PY_C_SENDER), PY_C_SENDER, transcript=False)
    assert not state.get("modified_files") and "找不到這次指令的開始時間" in state["unknown_writes"][-1]["unrecovered"]


def test_judge_session_recovers_too(monkeypatch, repo):
    """裁判子 session（CLAUDE_COMPANION_JUDGE=1）的最小記帳也補：裁判 Stop 的寫碼查核讀同一份 modified_files。"""
    import wg_core
    judge_state = {"turn_seq": 3, "session": {"id": _SID, "cwd": str(repo)}}
    monkeypatch.setattr(wg_core, "read_state", lambda sid: judge_state)
    monkeypatch.setattr(pt, "handle_post_tool_use", pt.handle_judge_post_tool_use)
    bash_unknown_write(monkeypatch, repo, judge_state, py_c(repo, PY_C_SENDER), PY_C_SENDER)
    assert _paths(judge_state) == [canon_path(repo / "notify" / "sender.py")]
    assert judge_state["unknown_writes"][-1]["recovered"]


def test_recovered_files_stamped_into_goal_tree(monkeypatch, repo):
    """補到的檔跟算得出的目標一樣交目標樹蓋號（成功路徑走 _need_goal_after_tool、失敗路徑走 _need_goal_stamp_failed）。"""
    import wg_need_goal as ng
    stamped: List[str] = []
    monkeypatch.setattr(ng, "cfg_for_cwd", lambda cfg, cwd: {"enabled": True})
    monkeypatch.setattr(ng, "stamp_edit", lambda sid, p, aid, turn, cfg: stamped.append(canon_path(p)) or None)
    monkeypatch.setattr(ng, "stamp_receipts", lambda sid, st, turn: None)
    bash_unknown_write(monkeypatch, repo, _state(), py_c(repo, PY_C_SENDER), PY_C_SENDER)
    assert stamped == [canon_path(repo / "notify" / "sender.py")]
    stamped.clear()
    effect = HEREDOC_EDIT + "raise SystemExit(1)\n"
    bash_unknown_write(monkeypatch, repo, _state(), heredoc(HEREDOC_EDIT, "exit 1"), effect, failure=True)
    assert canon_path(repo / "notify" / "log.py") in stamped


def test_big_file_without_sha_not_bumped_unless_written_after(monkeypatch, repo):
    """codex BLOCK 2：超過雜湊上限（2 MiB）的檔沒有 sha 可比。本 session 第 2 回合記過 big.py；第 5 回合子代理 B 的腳本沒碰它
    （mtime 不晚於上次記下的時間）→ 不刷成第 5 回合、不記到 B 名下；上次記下之後又被寫過 → 照補。"""
    big = repo / "notify" / "big.py"
    big.write_bytes(b"x = 1\n" + b"#" * (2 * 1024 * 1024 + 1))
    state = _state(turn=2)
    pt._note_modified(state, _SID, str(big), "Edit")
    assert "sha" not in state["modified_files"][0]
    state["turn_seq"] = 5
    real = pt.handle_post_tool_use
    monkeypatch.setattr(pt, "handle_post_tool_use", lambda inp, cfg: real({**inp, "agent_id": "agB"}, cfg))   # 子代理 B
    state, _ = bash_unknown_write(monkeypatch, repo, state, py_c(repo, PY_C_SENDER), PY_C_SENDER)
    m = _entry(state, big)
    assert m["last_turn_seq"] == 2 and m["count"] == 1, m
    assert canon_path(big) not in [canon_path(x["path"]) for x in state["agent_modified_files"]["agB"]]
    monkeypatch.setattr(pt, "handle_post_tool_use", real)
    _entry(state, big)["last_at"] = "2020-01-01T00:00:00+08:00"                # 上次記下是很久以前：之後的寫入照補
    code = "open('notify/big.py','ab').write(b'#')\n"
    state, _ = bash_unknown_write(monkeypatch, repo, state, py_c(repo, code), code)
    assert _entry(state, big)["last_turn_seq"] == 5 and _entry(state, big)["via"] == "vcs_status"


def test_failure_path_non_utf8_py_still_written_back(monkeypatch, repo):
    """codex BLOCK 4：失敗指令寫出合法的 cp1252 .py（有 coding 宣告）。判啟動器時讀它會 UnicodeDecodeError——不能讓已經記進 state 的
    改檔因此沒寫回、未知寫入也沒記：modified_files 有它、unknown_writes 有一筆、state 有寫回。"""
    code = "p='notify/latin.py'\nopen(p,'wb').write(b\"# -*- coding: cp1252 -*-\\nNAME = '\\xe9'\\n\")\n"
    state, logs = bash_unknown_write(monkeypatch, repo, _state(), heredoc(code, "exit 1"), code + "raise SystemExit(1)\n",
                                     failure=True)
    assert _paths(state) == [canon_path(repo / "notify" / "latin.py")], state.get("modified_files")
    assert len(state["unknown_writes"]) == 1 and ("write_state", {}) in logs


def test_long_command_with_many_newlines_stays_fast(repo):
    """codex BLOCK 3：一萬六千個換行後接一條內嵌 python。找 cd 目標與點名的檔不能隨換行數二次方變慢（舊 regex 7 秒，hook 上限 5 秒）。"""
    cmd = "\n" * 16000 + heredoc(PY_C_SENDER)                 # 換行後面沒有 cd：舊 regex 每個起點都吞完整串換行再回溯
    t = time.monotonic()
    dirs = uw.work_dirs(cmd, str(repo))
    named = uw.named_files(cmd, dirs)
    took = time.monotonic() - t
    assert took < 0.5 and [canon_path(p) for p in named] == [canon_path(repo / "notify" / "sender.py")], (took, named)


def test_future_mtime_not_counted(monkeypatch, repo):
    """mtime 在未來（時鐘調過、解壓保留時間）的髒檔不是這條指令寫的。"""
    fut = repo / "notify" / "format.py"
    fut.write_text("def format_message(text):\n    return text\n", encoding="utf-8")
    t = time.time() + 3600
    os.utime(fut, (t, t))
    state, _ = bash_unknown_write(monkeypatch, repo, _state(), py_c(repo, PY_C_SENDER), PY_C_SENDER)
    assert _paths(state) == [canon_path(repo / "notify" / "sender.py")], state.get("modified_files")


# ─── 判法本體（wg_unknown_write）：預算、點名、svn ──────────────────────────────

def test_git_porcelain_rename_in_either_column(tmp_path):
    """-z 輸出裡改名／複製（X 欄或 Y 欄是 R／C）後面多一筆原路徑，不能當成下一筆紀錄。"""
    out = b"R  new.py\0old.py\0MR moved.py\0orig_name.py\0 M a.py\0?? b.py\0"
    got = uw._git_changed(tmp_path, [], 1.0, lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, out, b""))
    assert [Path(p).name for p in got] == ["new.py", "moved.py", "a.py", "b.py"], got


def test_named_status_budget_shared_across_roots(tmp_path):
    """兩個版控根都整棵查逾時：點名查詢兩根合用一份 NAMED_TIMEOUT_S，不是每根各一份。"""
    a, b = init_repo(tmp_path / "a", {"x.py": "1\n"}), init_repo(tmp_path / "b", {"y.py": "1\n"})
    given: List[float] = []

    def run(cmd, **kw):
        if cmd[-1] == "--":
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        given.append(kw["timeout"])
        time.sleep(0.3)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")
    cmd = f"cd {msys(a)} && python -c \"p='x.py'\" && cd {msys(b)} && python -c \"p='y.py'\""
    uw.recover(cmd, str(tmp_path), time.time() - 5, run=run)
    assert len(given) == 2 and given[1] <= uw.NAMED_TIMEOUT_S - 0.25, given


def test_svn_expands_only_unversioned_dirs_with_one_global_cap(tmp_path, monkeypatch):
    """svn：只有未納管的目錄往下展開（加入、衝突的目錄底下的改動 svn 會逐筆列）；展開的檔數上限是全部合計，到了就停並寫明。"""
    root = tmp_path / "wc"
    (root / ".svn").mkdir(parents=True)
    for rel in ("added/a.cs", "new1/x.cs", "new1/y.cs", "new2/z.cs"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x", encoding="utf-8")
    xml = ('<?xml version="1.0" encoding="UTF-8"?><status><target path=".">'
           '<entry path="added"><wc-status item="added" props="none"/></entry>'
           '<entry path="new1"><wc-status item="unversioned" props="none"/></entry>'
           '<entry path="new2"><wc-status item="unversioned" props="none"/></entry>'
           '</target></status>').encode("utf-8")
    monkeypatch.setattr(uw, "UNVERSIONED_DIR_CAP", 2)
    paths, note = uw.recover("python -I - <<'EOF'\nimport os\nEOF", str(root), time.time() - 5,
                             run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, xml, b""))
    assert sorted(Path(p).name for p in paths) == ["x.cs", "y.cs"] and "展開到 2 個檔就停" in note["why"], (paths, note)


def test_full_status_timeout_falls_back_to_named_and_remembers_root(monkeypatch, repo):
    """整棵 git status 逾時 → 只查指令點名的檔（帶路徑的 status）照樣補到，那個根記進 slow；下次帶著 slow 呼叫就不再整棵查。
    經 handler 時根記進 state unknown_write_slow_roots、那一筆寫明只查了點名的檔。"""
    calls: List[List[str]] = []

    def run(cmd, **kw):
        calls.append(cmd)
        if cmd[-1] == "--":                                              # 整棵查（-- 後面沒有路徑）
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        return subprocess.run(cmd, **kw)
    (repo / "notify" / "sender.py").write_text("MAX_RETRIES = 6\n", encoding="utf-8")
    cmd = py_c(repo, PY_C_SENDER)
    paths, note = uw.recover(cmd, str(repo), time.time() - 5, run=run)
    assert [canon_path(p) for p in paths] == [canon_path(repo / "notify" / "sender.py")] and note["slow"], note
    assert "只查指令點名的檔" in note["why"] and len(calls) == 2
    calls.clear()
    paths, note = uw.recover(cmd, str(repo), time.time() - 5, slow_roots=note["slow"], run=run)
    assert paths and all(c[-1] != "--" for c in calls) and "之前整棵查逾時" in note["why"], (calls, note)
    real = uw.recover
    monkeypatch.setattr(uw, "recover", lambda *a, **k: real(*a, **k, run=run))
    state, _ = bash_unknown_write(monkeypatch, repo, _state(), cmd, PY_C_SENDER)
    assert state["unknown_write_slow_roots"] and _paths(state) == [canon_path(repo / "notify" / "sender.py")]
    assert "只查指令點名的檔" in state["unknown_writes"][-1]["unrecovered"]


def test_slow_root_with_nothing_named_says_unrecovered(repo):
    """整棵查逾時、指令又沒點名這個根底下的檔 → 補不到，原因寫明。"""
    def run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
    paths, note = uw.recover("python -I - <<'EOF'\nimport glob\nEOF", str(repo), time.time() - 5, run=run)
    assert paths == [] and "指令沒有點名" in note["why"], note


def test_work_dirs_and_named_files(repo, tmp_path):
    """cd 的目標（MSYS 寫法、相對前一個 cd）算工作目錄；點名的檔：外層雙引號裡的單引號字串、裸字樣都試，不存在的、旗標、網址不算。"""
    sub = repo / "notify"
    cmd = f'cd {msys(repo)} && cd notify && python -c "open(\'sender.py\',\'w\')" ../README.md -v https://x.y/a.py nope.py'
    dirs = uw.work_dirs(cmd, str(tmp_path))
    assert [canon_path(d) for d in dirs] == [canon_path(tmp_path), canon_path(repo), canon_path(sub)]
    named = {canon_path(p) for p in uw.named_files(cmd, dirs)}
    assert named == {canon_path(sub / "sender.py"), canon_path(repo / "README.md")}, named
    assert uw.work_dirs('cd "$DIR" && cd - && python x.py', str(repo)) == [os.path.normpath(str(repo))]
    same = f"cd {msys(repo)} && python -c \"p='notify/sender.py'\""                  # /c/… 跟 cwd 的 C:\… 是同一個目錄
    assert uw.work_dirs(same, str(repo)) == [os.path.normpath(str(repo))]
    assert len(uw.named_files(same, [str(repo), str(repo).lower()])) == 1


def test_svn_status_xml_parsed_unversioned_dir_expanded(tmp_path):
    """svn status --xml：modified／unversioned 算，只改屬性（item=normal）、missing 不算；未納管的目錄往下展開；mtime 早於開始的不算。"""
    root = tmp_path / "wc"
    (root / ".svn").mkdir(parents=True)
    for rel in ("src/a.cs", "src/b.cs", "src/old.cs", "newdir/x.cs", "newdir/sub/y.cs"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x", encoding="utf-8")
    stale(root / "src" / "old.cs")
    xml = ('<?xml version="1.0" encoding="UTF-8"?><status><target path=".">'
           '<entry path="src\\a.cs"><wc-status item="modified" props="none"/></entry>'
           '<entry path="src\\b.cs"><wc-status item="normal" props="modified"/></entry>'
           '<entry path="src\\old.cs"><wc-status item="modified" props="none"/></entry>'
           '<entry path="gone.cs"><wc-status item="missing" props="none"/></entry>'
           '<entry path="newdir"><wc-status item="unversioned" props="none"/></entry>'
           '</target></status>').encode("utf-8")
    seen: List[List[str]] = []

    def run(cmd, **kw):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, xml, b"")
    paths, note = uw.recover("python -I - <<'EOF'\nimport os\nEOF", str(root), time.time() - 5, run=run)
    want = {canon_path(root / r) for r in ("src/a.cs", "newdir/x.cs", "newdir/sub/y.cs")}
    assert {canon_path(p) for p in paths} == want and seen[0][:3] == ["svn", "status", "--xml"], (paths, seen)


@pytest.mark.skipif(not (shutil.which("svn") and shutil.which("svnadmin")), reason="這台沒有 svn／svnadmin")
def test_real_svn_working_copy(monkeypatch, tmp_path):
    """真 svn 工作副本：內嵌 python 改了已納管的檔、新增一個未納管的檔 → 都補得到；快照前就改、這次沒動的不算。"""
    repo_dir, wc = tmp_path / "svnrepo", tmp_path / "svnwc"
    subprocess.run(["svnadmin", "create", str(repo_dir)], check=True, capture_output=True)
    url = "file:///" + str(repo_dir).replace("\\", "/")
    subprocess.run(["svn", "checkout", "-q", url, str(wc)], check=True, capture_output=True)
    for rel, text in NOTIFY.items():
        (wc / rel).parent.mkdir(parents=True, exist_ok=True)
        (wc / rel).write_text(text, encoding="utf-8", newline="\n")
    subprocess.run(["svn", "add", "-q", "--force", "."], cwd=str(wc), check=True, capture_output=True)
    subprocess.run(["svn", "commit", "-q", "-m", "init"], cwd=str(wc), check=True, capture_output=True)
    stale(wc / "README.md", "# notify\n\n- 先前就改的。\n")
    code = PY_C_SENDER + "open('notify/'+'log.py','w').write('x = 1\\n')\n"
    state, _ = bash_unknown_write(monkeypatch, wc, _state(), py_c(wc, code), code)
    want = {canon_path(wc / "notify" / "sender.py"), canon_path(wc / "notify" / "log.py")}
    assert set(_paths(state)) == want, state.get("modified_files")
