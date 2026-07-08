"""verify_stop_tailread_batchvcs.py — Stop handler 性能結構修復（B 組）驗證。

1. read_transcript_tail：小檔全讀 / 大檔尾窗（捨首個不完整行）/ None fail-open
2. get_last_assistant_text / get_current_turn_text / estimate_context_usage 的
   text= 共用尾段路徑 ≡ 開檔路徑（單次 tail-read 重構不改語義）
3. _harvest_accessed_files：從尾段回收 Read 路徑、去重、冪等（多次 Stop 不重複）
4. _detect_uncommitted_files：VCS root 分組 batch 查詢（真 git repo fixture）
   — dirty/clean 判定與非工作區 None 語義與逐檔版一致

對應：handlers/stop.py + wg_evasion.py + wg_handoff.py（transcript 三讀合一）、
      settings.json Stop timeout 20→10 的前提保證。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import wg_evasion as we  # noqa: E402
import wg_handoff as wh  # noqa: E402
from handlers import stop as st  # noqa: E402


def _jl(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _assistant(text: str = "", tool: dict = None) -> str:
    content = []
    if text:
        content.append({"type": "text", "text": text})
    if tool:
        content.append({"type": "tool_use", **tool})
    return _jl({"type": "assistant", "message": {"content": content}})


def _user(text: str) -> str:
    return _jl({"type": "user", "message": {"content": text}})


# ─── 1. read_transcript_tail ─────────────────────────────────────────


def test_tail_small_file_reads_whole(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text("line1\nline2\n", encoding="utf-8")
    # bytes-read 不做換行翻譯 → 以行序比對（Windows 上檔內實為 \r\n）
    assert we.read_transcript_tail(p).splitlines() == ["line1", "line2"]


def test_tail_large_file_drops_partial_first_line(tmp_path):
    p = tmp_path / "t.jsonl"
    lines = [f"row-{i:04d}" for i in range(100)]
    p.write_text("\n".join(lines), encoding="utf-8")
    out = we.read_transcript_tail(p, max_bytes=95)
    # 尾窗內首個不完整行被捨棄 → 每一行都完整
    assert out
    for ln in out.splitlines():
        assert ln.startswith("row-") and len(ln) == 8
    assert out.splitlines()[-1] == "row-0099"


def test_tail_none_and_missing_fail_open(tmp_path):
    assert we.read_transcript_tail(None) == ""
    assert we.read_transcript_tail(tmp_path / "nope.jsonl") == ""


# ─── 2. text= 共用尾段 ≡ 開檔路徑 ────────────────────────────────────


def test_last_assistant_text_text_param_equiv(tmp_path):
    p = tmp_path / "t.jsonl"
    body = "\n".join([
        _user("做 X"),
        _assistant("第一段回應——這一句必須明確超過三十個字元的長度門檻，補足說明文字供擷取測試使用"),
        _assistant("最終回應——這一句同樣必須明確超過三十個字元的長度門檻，理應被選為最後文字"),
    ])
    p.write_text(body, encoding="utf-8")
    via_file = we.get_last_assistant_text(p)
    via_text = we.get_last_assistant_text(None, text=body)
    assert via_file == via_text
    assert "最終回應" in via_text


def test_current_turn_text_text_param_equiv(tmp_path):
    p = tmp_path / "t.jsonl"
    body = "\n".join([
        _user("第一個 prompt"),
        _assistant("舊 turn 的文字內容不該入選"),
        _user("第二個 prompt（turn 邊界）"),
        _assistant("本 turn 文字", tool={"name": "Edit", "input": {"file_path": "C:/x/a.py"}}),
    ])
    p.write_text(body, encoding="utf-8")
    via_file = we.get_current_turn_text(p)
    via_text = we.get_current_turn_text(None, text=body)
    assert via_file == via_text
    assert "本 turn 文字" in via_text and "舊 turn" not in via_text


def test_estimate_context_usage_text_param_equiv(tmp_path):
    p = tmp_path / "t.jsonl"
    row = _jl({
        "type": "assistant",
        "message": {"role": "assistant", "usage": {
            "input_tokens": 1000,
            "cache_creation_input_tokens": 2000,
            "cache_read_input_tokens": 77000,
        }, "content": []},
    })
    p.write_text(row, encoding="utf-8")
    assert wh.estimate_context_usage(str(p), 1_000_000, 0) == pytest.approx(
        wh.estimate_context_usage(None, 1_000_000, 0, text=row)
    )
    assert wh.estimate_context_usage(None, 1_000_000, 0, text="") == 0.0


# ─── 3. _harvest_accessed_files ──────────────────────────────────────


def _read_line(fp: str) -> str:
    return _assistant(tool={"name": "Read", "input": {"file_path": fp}})


def test_harvest_adds_dedups_and_idempotent():
    text = "\n".join([
        _read_line("C:/x/a.py"),
        _read_line("C:/x/a.py"),                                   # 同 turn 重讀
        _assistant(tool={"name": "Grep", "input": {"pattern": "Read"}}),  # 非 Read
        _jl({"type": "user", "message": {"content": [
            {"type": "tool_result", "content": 'tool_use "Read" 假訊號'}]}}),
        _read_line("C:/x/b.md"),
    ])
    state = {"accessed_files": [{"path": "C:/x/pre.md", "at": "t0"}]}
    assert st._harvest_accessed_files(state, text) is True
    assert [a["path"] for a in state["accessed_files"]] == [
        "C:/x/pre.md", "C:/x/a.py", "C:/x/b.md",
    ]
    # 冪等：blocked turn 的第二次 Stop 掃同一尾段不重複記
    assert st._harvest_accessed_files(state, text) is False
    assert st._harvest_accessed_files(state, "") is False


# ─── 4. _detect_uncommitted_files（batch VCS）────────────────────────


def _git(repo: Path, *args) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=10, check=True,
        creationflags=st._NO_WINDOW,
    )


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    try:
        _git(tmp_path, "init", "repo")
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git unavailable")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    clean = repo / "clean.txt"
    dirty = repo / "sub" / "dirty.txt"
    clean.write_text("v1", encoding="utf-8")
    dirty.write_text("v1", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    dirty.write_text("v2", encoding="utf-8")
    return repo, clean, dirty


def test_batch_git_detects_dirty_only(git_repo):
    repo, clean, dirty = git_repo
    mf = [{"path": str(clean)}, {"path": str(dirty)}, {"path": str(dirty)}]
    out = st._detect_uncommitted_files(mf)
    assert out == [str(dirty)]


def test_batch_git_all_clean_returns_empty(git_repo):
    repo, clean, dirty = git_repo
    assert st._detect_uncommitted_files([{"path": str(clean)}]) == []


def test_non_vcs_dir_returns_none(tmp_path):
    f = tmp_path / "loose.txt"
    f.write_text("x", encoding="utf-8")
    # tmp 不在任何 git/svn 工作區內 → 偵測失敗語義（None，跳過該閘）
    if st._find_vcs_root(tmp_path) is not None:
        pytest.skip("tmp_path unexpectedly inside a VCS working tree")
    assert st._detect_uncommitted_files([{"path": str(f)}]) is None


def test_empty_modified_files_returns_empty():
    assert st._detect_uncommitted_files([]) == []
