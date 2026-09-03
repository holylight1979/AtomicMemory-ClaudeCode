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
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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


# ─── auto_project_eol：專案樹 LF 自動化（sync-memory-index 專案模式 --write 的漏斗尾端）───────

SVN_OK = shutil.which("svn") is not None and shutil.which("svnadmin") is not None
svn_only = pytest.mark.skipif(not SVN_OK, reason="svn／svnadmin 不在 PATH")
SYNC = CLAUDE_DIR / "tools" / "sync-memory-index.py"


def _svn(cwd, *args, check=True):
    r = subprocess.run(["svn", "--non-interactive", *args], cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60, **_NO_WINDOW)
    if check and r.returncode:
        raise AssertionError(f"svn {' '.join(args)} failed rc={r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def _mem_tree(mem: Path):
    (mem / "shared").mkdir(parents=True)
    (mem / "shared" / "a.md").write_bytes(b"# a\r\nx\r\n")
    (mem / "shared" / "b.md").write_bytes(b"# b\ny\n")
    (mem / "shared" / "bin.dat").write_bytes(b"\x00\x01\r\n")
    (mem / "_atom_index.json").write_bytes(b"{}\r\n")


def test_auto_project_eol_git(tmp_path):
    repo = _repo(tmp_path)
    mem = repo / ".claude" / "memory"
    _mem_tree(mem)
    rep = ne.auto_project_eol(mem)
    assert rep["vcs"] == "git" and rep["converted"] == 2 and rep["skipped_binary"] == 1, rep
    assert rep["error"] is None and rep["attrs"]["ok"], rep
    assert (mem / "shared" / "a.md").read_bytes() == b"# a\nx\n"
    ga = (repo / ".gitattributes").read_bytes()
    assert ga.count(ne.ATTR_MARK.encode()) == 1
    rep2 = ne.auto_project_eol(mem)
    assert rep2["converted"] == 0 and rep2["error"] is None and (repo / ".gitattributes").read_bytes() == ga


@svn_only
def test_auto_project_eol_svn(tmp_path):
    subprocess.run(["svnadmin", "create", str(tmp_path / "repo")], check=True, capture_output=True, **_NO_WINDOW)
    wc = tmp_path / "wc"
    _svn(tmp_path, "co", "-q", "file:///" + str(tmp_path / "repo").replace("\\", "/"), str(wc))
    mem = wc / ".claude" / "memory"
    _mem_tree(mem)
    _svn(wc, "add", "-q", "--force", ".claude")
    _svn(wc, "ci", "-q", "-m", "base")
    (mem / "shared" / "new.md").write_bytes(b"u\r\n")  # 剛寫入、尚未 svn add 的 atom
    rep = ne.auto_project_eol(mem)
    assert rep["vcs"] == "svn" and rep["error"] is None, rep
    assert rep["converted"] == 3 and rep["skipped_binary"] == 1, rep  # a.md、_atom_index.json、new.md
    assert rep["attrs"]["set"] == 3 and rep["attrs"]["already"] == 0, rep  # 已版控文字檔：a、b、_atom_index.json
    pg = _svn(wc, "propget", "svn:eol-style", "-R", "--xml", ".claude/memory").stdout
    assert pg.count(">LF<") == 3 and "bin.dat" not in pg and "new.md" not in pg
    rep2 = ne.auto_project_eol(mem)
    assert rep2["converted"] == 0 and rep2["attrs"] == {"set": 0, "already": 3, "error": None}, rep2
    _svn(wc, "ci", "-q", "-m", "props")  # 屬性改動能提交
    _svn(wc, "add", "-q", ".claude/memory/shared/new.md")
    rep3 = ne.auto_project_eol(mem)
    assert rep3["attrs"]["set"] == 1 and rep3["error"] is None, rep3  # 新 atom 進版控後下一輪補上


def test_auto_project_eol_without_vcs(tmp_path):
    mem = tmp_path / "plain" / ".claude" / "memory"
    _mem_tree(mem)
    rep = ne.auto_project_eol(mem)
    assert rep["vcs"] is None and rep["converted"] == 2 and rep["attrs"] is None and rep["error"] is None, rep


def _project_with_index(tmp_path: Path) -> Path:
    """tmp git 專案：.claude/memory 含一顆 CRLF atom 與對應 _atom_index.json（sync-memory-index 專案模式輸入）。"""
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(tmp_path, "init", "-q", "-b", "master", str(repo))
    mem = repo / ".claude" / "memory"
    (mem / "shared" / "Server").mkdir(parents=True)
    (mem / "shared" / "Server" / "a.md").write_bytes(b"# a\r\n\r\n- [\xe8\x87\xa8] x\r\n")
    (mem / "_atom_index.json").write_bytes(json.dumps({"version": "1.0", "atoms": [
        {"name": "a", "path": "memory/shared/Server/a.md", "triggers": ["x"], "scope": "shared"}]}).encode("utf-8"))
    (mem / "MEMORY.md").write_bytes(b"# Atom Index \xe2\x80\x94 Project\r\n")
    return repo


def _sync(mem: Path, *extra):
    return subprocess.run([PY, str(SYNC), "--write", "--memory-dir", str(mem), *extra], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=120, **_NO_WINDOW)


def test_sync_memory_index_project_write_normalizes_tree(tmp_path):
    repo = _project_with_index(tmp_path)
    mem = repo / ".claude" / "memory"
    r = _sync(mem)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[sync-memory-index] eol: converted" in r.stdout and "eol normalize failed" not in r.stderr, r.stdout + r.stderr
    assert (mem / "shared" / "Server" / "a.md").read_bytes() == b"# a\n\n- [\xe8\x87\xa8] x\n"
    assert b"\r" not in (mem / "MEMORY.md").read_bytes()
    assert ne.ATTR_MARK.encode() in (repo / ".gitattributes").read_bytes()
    r2 = _sync(mem)  # 已 up to date 仍走漏斗尾端（冪等、零轉檔）
    assert r2.returncode == 0 and "eol: converted 0" in r2.stdout, r2.stdout + r2.stderr


def test_sync_memory_index_no_eol_flag_and_config_off(tmp_path):
    repo = _project_with_index(tmp_path)
    mem = repo / ".claude" / "memory"
    r = _sync(mem, "--no-eol")
    assert r.returncode == 0 and "eol:" not in r.stdout, r.stdout + r.stderr
    assert (mem / "shared" / "Server" / "a.md").read_bytes().startswith(b"# a\r\n")
    assert not (repo / ".gitattributes").exists()
    spec = importlib.util.spec_from_file_location("sync_memory_index", SYNC)
    smi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smi)
    cfg = tmp_path / "config.json"
    cfg.write_bytes(b'{"eol": {"auto_normalize_project": false}}')
    assert smi._eol_auto_enabled(cfg) is False
    cfg.write_bytes(b'{"merge_driver": {}}')
    assert smi._eol_auto_enabled(cfg) is True
    assert smi._eol_auto_enabled(tmp_path / "missing.json") is True
