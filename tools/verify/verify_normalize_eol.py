"""verify_normalize_eol.py — tools/normalize-eol.py（換行統一 LF）。

- classify/to_lf：CRLF、mixed、孤立 CR、BOM、NUL 五種輸入。
- --root（tmp git repo）：乾淨檔轉 LF 並 add；dirty 檔工作樹轉 LF、index 寫入 HEAD 正規化版本（純 EOL）；
  untracked 轉工作樹不 add；binary 不動；--check 前 1 後 0。
- --memory-dir：樹內全轉；--write-gitattributes 冪等（重跑 byte-identical）且 check-attr 生效。
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent
TOOL = CLAUDE_DIR / "tools" / "normalize-eol.py"
PY = sys.executable
_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}

_spec = importlib.util.spec_from_file_location("normalize_eol", TOOL)
ne = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ne)


def _git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", **_NO_WINDOW)
    if check and r.returncode:
        raise AssertionError(f"git {' '.join(args)} rc={r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def _run(*args):
    r = subprocess.run([PY, str(TOOL), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       **_NO_WINDOW)
    last = [ln for ln in r.stdout.splitlines() if ln.strip()][-1]
    return r.returncode, json.loads(last), r.stderr


def _assert_staged_pure_eol(repo):
    """staged 內容去掉所有 CR 後必須等於 HEAD 去掉 CR（孤立 CR 檔在 git 眼裡是內容差異，這裡用位元組比對）。"""
    for path in _git(repo, "diff", "--cached", "--name-only").stdout.split():
        head = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{path}"], capture_output=True, **_NO_WINDOW).stdout
        staged = subprocess.run(["git", "-C", str(repo), "show", f":0:{path}"], capture_output=True, **_NO_WINDOW).stdout
        assert b"\r" not in staged, path
        assert staged == head.replace(b"\r\n", b"\n").replace(b"\r", b"\n"), path


def test_classify_and_to_lf():
    assert ne.classify(b"a\nb\n") == "lf"
    assert ne.classify(b"a\r\nb\r\n") == "crlf"
    assert ne.classify(b"a\r\nb\n") == "mixed"
    assert ne.classify(b"a\rb\r") == "cr"
    assert ne.classify(b"\x00\x01") == "binary"
    assert ne.to_lf(b"\xef\xbb\xbfa\r\nb\rc\n") == b"\xef\xbb\xbfa\nb\nc\n"


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(tmp_path, "init", "-q", "-b", "master", str(repo))
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "core.autocrlf", "false")
    (repo / "crlf.md").write_bytes(b"# t\r\nline\r\n")
    (repo / "mixed.md").write_bytes(b"a\r\nb\n")
    (repo / "bom.md").write_bytes(b"\xef\xbb\xbfx\r\ny\r\n")
    (repo / "lonecr.txt").write_bytes(b"p\rq\r")
    (repo / "bin.dat").write_bytes(b"\x00\x01\r\n\x02")
    (repo / "ok.md").write_bytes(b"fine\n")
    (repo / "dirty.md").write_bytes(b"base\r\nline\r\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    # 別的 session 的改動：內容變 + 仍 CRLF；另有一個 untracked CRLF 檔
    (repo / "dirty.md").write_bytes(b"base\r\nline\r\nother-session-edit\r\n")
    (repo / "new-untracked.md").write_bytes(b"u\r\n")
    return repo


def test_root_check_reports_then_convert_clean_only(tmp_path):
    repo = _repo(tmp_path)
    rc, rep, _ = _run("--root", "--repo", str(repo), "--check")
    assert rc == 1 and rep["residual_index"] >= 4 and any("new-untracked.md" in r for r in rep["residual"])
    rc, rep, _ = _run("--root", "--repo", str(repo))
    assert rep["converted_added"] == 4  # crlf, mixed, bom, lonecr
    assert rep["skipped_binary"] == 1 and rep["skipped_dirty"] == 2  # dirty.md + untracked
    assert (repo / "bom.md").read_bytes() == b"\xef\xbb\xbfx\ny\n"
    assert (repo / "lonecr.txt").read_bytes() == b"p\nq\n"
    assert (repo / "bin.dat").read_bytes() == b"\x00\x01\r\n\x02"
    assert b"\r" in (repo / "dirty.md").read_bytes()  # 沒 --include-dirty 不碰
    staged = _git(repo, "diff", "--cached", "--name-only").stdout.split()
    assert sorted(staged) == ["bom.md", "crlf.md", "lonecr.txt", "mixed.md"]
    _assert_staged_pure_eol(repo)


def test_root_include_dirty_keeps_commit_pure_eol(tmp_path):
    repo = _repo(tmp_path)
    rc, rep, _ = _run("--root", "--repo", str(repo), "--include-dirty")
    assert rep["converted_head_staged"] == 1 and rep["converted_untracked"] == 1
    # 工作樹：dirty 檔已 LF 且保留別人的內容改動
    assert (repo / "dirty.md").read_bytes() == b"base\nline\nother-session-edit\n"
    assert (repo / "new-untracked.md").read_bytes() == b"u\n"
    # index：dirty 檔 = HEAD 內容正規化（沒有 other-session-edit），純 EOL
    idx = _git(repo, "show", ":0:dirty.md").stdout
    assert idx == "base\nline\n"
    _assert_staged_pure_eol(repo)
    # 別人的內容改動仍是「未 staged 的工作樹差異」
    assert "other-session-edit" in _git(repo, "diff", "dirty.md").stdout
    assert "new-untracked.md" not in _git(repo, "diff", "--cached", "--name-only").stdout
    _git(repo, "commit", "-qm", "eol")
    rc, rep, _ = _run("--root", "--repo", str(repo), "--check")
    assert rc == 0, rep


def test_memory_dir_and_gitattributes_idempotent(tmp_path):
    repo = _repo(tmp_path)
    mem = repo / ".claude" / "memory"
    (mem / "shared").mkdir(parents=True)
    (mem / "_vectordb").mkdir()
    (mem / "shared" / "a.md").write_bytes(b"x\r\n")
    (mem / "_atom_index.json").write_bytes(b"{}\r\n")
    (mem / "_vectordb" / "skip.md").write_bytes(b"x\r\n")
    rc, rep, _ = _run("--memory-dir", str(mem), "--check")
    assert rc == 1 and len(rep["residual_worktree"]) == 2
    rc, rep, _ = _run("--memory-dir", str(mem), "--write-gitattributes")
    assert rc == 0 and len(rep["converted"]) == 2 and rep["gitattributes"]["ok"], rep
    assert (mem / "_vectordb" / "skip.md").read_bytes() == b"x\r\n"
    ga = (repo / ".gitattributes").read_bytes()
    assert ga.count(ne.ATTR_MARK.encode()) == 1 and b".claude/memory/** text eol=lf" in ga
    rc, rep, _ = _run("--memory-dir", str(mem), "--write-gitattributes")
    assert rc == 0 and (repo / ".gitattributes").read_bytes() == ga
    attrs = _git(repo, "check-attr", "merge", "eol", "--", ".claude/memory/_atom_index.json").stdout
    assert "merge: atomindex" in attrs and "eol: lf" in attrs
