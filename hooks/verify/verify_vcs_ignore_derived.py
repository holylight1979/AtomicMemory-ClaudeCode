"""verify_vcs_ignore_derived.py — 專案記憶庫衍生檔退出版控（lib/vcs_ignore）＋ SessionStart 缺檔重建。

不變式：
1. 缺 _atom_index.json 的記憶目錄跑 SessionStart 的重建 → JSON 產出、條目數＝磁碟 atom 數、_ATOM_INDEX.md 一併存在。
2. 只缺 _ATOM_INDEX.md → 就地從 JSON 重生（JSON 位元組不變、零子行程）；兩檔都在 → 零行。
3. 重建子行程失敗 → ⚠ 告警帶後果與手動 --rebuild 指令（現有訊息保留）。
4. git：ensure_ignore 寫 {mem}/.gitignore 五項（LF）；既有檔只補缺的行、保留原行；再跑零改動；
   整個 .claude/ 被上層 .gitignore 排除 → 不寫；假 .git（非 repo）→ 零動作。
5. git：衍生檔已被追蹤 → advisory 一次（git rm --cached 確切路徑＋隊友端說明＋舊版手動重建句），
   marker 記下後再跑零行；絕不自動 git rm。
6. svn（svnadmin 在 PATH 才跑）：propset 併入既有值不覆蓋、冪等、ignore 真的生效；記憶庫目錄未版控 →
   skipped 不報錯、不記 marker、svn add 後下一次補上；已版控衍生檔 → svn rm --keep-local --force 告警
   （排程加入未提交的用 svn revert）、一次、絕不自動執行。
7. 無 VCS → 零子行程、零行；~/.claude 自己的記憶 → 零行。
8. 索引首次落檔（save_atom_index_json）即設 ignore；第二次存檔不再碰 VCS。
9. SVN IndexConflict：衍生索引衝突時先指退出版控（MEMORY.md 不在退出清單），自動合併列為暫時處置；
   只有 MEMORY.md 衝突維持原句。PreToolUse 的自動解訊息同樣附退出指令。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parents[2]  # hooks/verify/ → repo root
sys.path.insert(0, str(CLAUDE / "hooks"))
sys.path.insert(0, str(CLAUDE / "lib"))

import vcs_ignore as vi  # noqa: E402
from handlers import session_start as ss  # noqa: E402

_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}
SVN_OK = shutil.which("svn") is not None and shutil.which("svnadmin") is not None
svn_only = pytest.mark.skipif(not SVN_OK, reason="svn／svnadmin 不在 PATH")
INDEX_JSON = "_atom_index.json"
INDEX_MD = "_ATOM_INDEX.md"


def _boom(*_a, **_k):
    raise AssertionError("不該起子行程")


def _atom(d: Path, name: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(f"# {name}\n\n- Scope: shared\n- Confidence: [臨]\n- Trigger: {name}, t-{name}\n\n"
                 f"## 知識\n\n- [臨] {name}\n\n## 行動\n\n- x\n", encoding="utf-8", newline="\n")
    return p


def _mem(tmp_path: Path) -> Path:
    return tmp_path / "proj" / ".claude" / "memory"


# ─── 1-3. SessionStart 缺檔重建 ─────────────────────────────────────────────


def test_rebuild_json_and_mirror_from_index_less_dir(tmp_path):
    mem = _mem(tmp_path)
    for n in ("a", "b", "c"):
        _atom(mem / "shared", n)
    msg = ss._rebuild_index_if_missing(mem)
    data = json.loads((mem / INDEX_JSON).read_text(encoding="utf-8"))
    assert {a["name"] for a in data["atoms"]} == {"a", "b", "c"}, data
    assert (mem / INDEX_MD).exists()
    assert "已從磁碟重建" in msg and "共 3 筆" in msg and "⚠" not in msg, msg
    assert ss._rebuild_index_if_missing(mem) == ""


def test_mirror_only_missing_regenerated_in_process(tmp_path, monkeypatch):
    mem = _mem(tmp_path)
    _atom(mem / "shared", "a")
    (mem / INDEX_JSON).write_text(json.dumps({"version": "1.0", "atoms": [
        {"name": "a", "path": "memory/shared/a.md", "triggers": ["a"], "scope": "shared"}]}),
        encoding="utf-8", newline="\n")
    before = (mem / INDEX_JSON).read_bytes()
    monkeypatch.setattr(subprocess, "run", _boom)
    msg = ss._rebuild_index_if_missing(mem)
    assert "已從 _atom_index.json 重生" in msg and "⚠" not in msg, msg
    assert "| a |" in (mem / INDEX_MD).read_text(encoding="utf-8")
    assert (mem / INDEX_JSON).read_bytes() == before
    assert ss._rebuild_index_if_missing(mem) == ""


def test_rebuild_failure_is_loud_with_manual_command(tmp_path, monkeypatch):
    mem = _mem(tmp_path)
    _atom(mem / "shared", "a")

    def fail(*_a, **_k):
        raise OSError("no interpreter")

    monkeypatch.setattr(subprocess, "run", fail)
    msg = ss._rebuild_index_if_missing(mem)
    assert "⚠" in msg and "重建失敗" in msg and "空的" in msg, msg
    assert "--rebuild --memory-dir" in msg and str(mem) in msg, msg


# ─── 4-5. git ────────────────────────────────────────────────────────────────


def _git(repo: Path, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **_NO_WINDOW)


def _git_repo(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    return root


def test_git_ensure_ignore_adds_missing_lines_only(tmp_path):
    root = _git_repo(tmp_path)
    mem = root / ".claude" / "memory"
    mem.mkdir(parents=True)
    (mem / ".gitignore").write_text("# mine\nfoo\n_staging/\n", encoding="utf-8", newline="\n")
    reps = vi.ensure_ignore(mem)
    assert [r["vcs"] for r in reps] == ["git"], reps
    rep = reps[0]
    assert rep["error"] is None and rep["skipped"] is None, rep
    assert rep["added"] == ["_atom_index.json", "_ATOM_INDEX.md", "episodic", "vector-db"], rep
    assert rep["already"] == ["_staging"], rep
    raw = (mem / ".gitignore").read_bytes()
    assert b"\r\n" not in raw
    lines = raw.decode("utf-8").splitlines()
    assert lines[:3] == ["# mine", "foo", "_staging/"], lines
    assert lines[3:] == ["_atom_index.json", "_ATOM_INDEX.md", "episodic/", "vector-db/"], lines
    rep2 = vi.ensure_ignore(mem)[0]
    assert rep2["added"] == [] and len(rep2["already"]) == 5, rep2
    assert (mem / ".gitignore").read_bytes() == raw
    # ignore 真的生效
    for n in ("_atom_index.json", "episodic/e.md", "vector-db/x"):
        assert _git(root, "check-ignore", "-q", "--", f".claude/memory/{n}").returncode == 0, n


def test_git_ensure_skips_when_memory_dir_itself_ignored(tmp_path):
    root = _git_repo(tmp_path)
    (root / ".gitignore").write_text(".claude/\n", encoding="utf-8", newline="\n")
    mem = root / ".claude" / "memory"
    mem.mkdir(parents=True)
    rep = vi.ensure_ignore(mem)[0]
    assert rep["skipped"] == "dir-ignored" and rep["error"] is None, rep
    assert not (mem / ".gitignore").exists()


def test_fake_git_dir_is_not_a_repo(tmp_path):
    root = tmp_path / "p"
    (root / ".git").mkdir(parents=True)
    mem = root / ".claude" / "memory"
    mem.mkdir(parents=True)
    rep = vi.ensure_ignore(mem)[0]
    assert rep["skipped"] == "not-a-repo" and rep["error"] is None, rep
    assert not (mem / ".gitignore").exists()
    marker = tmp_path / "m.json"
    assert vi.advisory_lines(mem, marker) == [] and not marker.exists()


def test_git_tracked_derived_warned_once_with_exact_commands(tmp_path):
    root = _git_repo(tmp_path)
    mem = root / ".claude" / "memory"
    _atom(mem / "shared", "a")
    (mem / INDEX_JSON).write_text("{}\n", encoding="utf-8", newline="\n")
    (mem / INDEX_MD).write_text("# x\n", encoding="utf-8", newline="\n")
    (mem / "episodic").mkdir()
    (mem / "episodic" / "e.md").write_text("e\n", encoding="utf-8", newline="\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")
    marker = tmp_path / "marker.json"

    lines = vi.advisory_lines(mem, marker, today="2026-10-01")
    joined = "\n".join(lines)
    assert "[Guardian:VcsIgnore] 已為" in joined and ".gitignore" in joined, joined
    warn = [ln for ln in lines if "已被git 追蹤" in ln]
    assert len(warn) == 1, lines
    w = warn[0]
    assert all(n in w for n in ("_atom_index.json", "_ATOM_INDEX.md", "episodic")), w
    assert "vector-db" not in w.split("——")[0]  # 沒被追蹤的不列
    assert f'git rm -r --cached "{mem / INDEX_JSON}" "{mem / INDEX_MD}" "{mem / "episodic"}"' in w, w
    assert "modify/delete" in w and "--rebuild --memory-dir" in w and "2026-09-23" in w, w

    entry = next(iter(json.loads(marker.read_text(encoding="utf-8")).values()))
    assert entry["ignore_done"]["git"] == "2026-10-01" and entry["warned"]["git"] == "2026-10-01", entry
    assert entry["tracked"] == ["_ATOM_INDEX.md", "_atom_index.json", "episodic"], entry
    # 一次：marker 後零行、零子行程
    assert vi.advisory_lines(mem, marker) == []
    # 唯讀：沒有自動 git rm
    assert "_atom_index.json" in _git(root, "ls-files", "--", ".claude/memory").stdout


# ─── 6. svn ──────────────────────────────────────────────────────────────────


def _svn(cwd: Path, *args, check: bool = True):
    r = subprocess.run(["svn", "--non-interactive", *args], cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60, **_NO_WINDOW)
    if check and r.returncode:
        raise AssertionError(f"svn {' '.join(args)} failed rc={r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def _svn_wc(tmp_path: Path, *, add_memory: bool = True) -> Path:
    subprocess.run(["svnadmin", "create", str(tmp_path / "repo")], check=True, capture_output=True, **_NO_WINDOW)
    wc = tmp_path / "wc"
    _svn(tmp_path, "co", "-q", "file:///" + str(tmp_path / "repo").replace("\\", "/"), str(wc))
    mem = wc / ".claude" / "memory"
    _atom(mem / "shared", "a")
    if add_memory:
        _svn(wc, "add", "-q", "--force", ".claude")
        _svn(wc, "ci", "-q", "-m", "base")
    return wc


@svn_only
def test_svn_ensure_ignore_merges_existing_and_takes_effect(tmp_path):
    wc = _svn_wc(tmp_path)
    mem = wc / ".claude" / "memory"
    _svn(wc, "propset", "svn:ignore", "foo", str(mem))
    _svn(wc, "ci", "-q", "-m", "ign")
    rep = vi.ensure_ignore(mem)[0]
    assert rep["vcs"] == "svn" and rep["error"] is None and rep["skipped"] is None, rep
    assert rep["added"] == list(vi.DERIVED_ENTRIES) and rep["already"] == [], rep
    assert _svn(wc, "propget", "svn:ignore", str(mem)).stdout.split() == ["foo", *vi.DERIVED_ENTRIES]
    rep2 = vi.ensure_ignore(mem)[0]
    assert rep2["added"] == [] and rep2["already"] == list(vi.DERIVED_ENTRIES), rep2
    _svn(wc, "ci", "-q", "-m", "ignore")  # 屬性是本機修改、可提交
    (mem / INDEX_JSON).write_text("{}\n", encoding="utf-8", newline="\n")
    (mem / "_staging").mkdir()
    st = _svn(wc, "status", "--no-ignore", str(mem)).stdout
    ignored = [ln for ln in st.splitlines() if ln.startswith("I")]
    assert len(ignored) == 2 and all(any(n in ln for ln in ignored) for n in (INDEX_JSON, "_staging")), st
    assert vi.tracked_derived(mem) == {}


@svn_only
def test_svn_unversioned_memory_dir_skipped_then_retried(tmp_path):
    wc = _svn_wc(tmp_path, add_memory=False)
    mem = wc / ".claude" / "memory"
    rep = vi.ensure_ignore(mem)[0]
    assert rep["skipped"] == "unversioned" and rep["error"] is None, rep
    marker = tmp_path / "m.json"
    assert vi.advisory_lines(mem, marker) == [] and not marker.exists()
    _svn(wc, "add", "-q", "--force", ".claude")  # 排程加入即可 propset，不必先 commit
    lines = vi.advisory_lines(mem, marker, today="2026-10-01")
    assert len(lines) == 1 and "已為" in lines[0] and "svn:ignore" in lines[0] and "svn commit" in lines[0], lines
    entry = next(iter(json.loads(marker.read_text(encoding="utf-8")).values()))
    assert entry["ignore_done"]["svn"] == "2026-10-01" and "svn" not in entry["warned"], entry
    assert vi.advisory_lines(mem, marker) == []


@svn_only
def test_svn_tracked_derived_warned_once_with_exact_commands(tmp_path):
    wc = _svn_wc(tmp_path)
    mem = wc / ".claude" / "memory"
    (mem / INDEX_JSON).write_text("{}\n", encoding="utf-8", newline="\n")
    (mem / INDEX_MD).write_text("# x\n", encoding="utf-8", newline="\n")
    (mem / "_staging").mkdir()
    (mem / "_staging" / "s.md").write_text("s\n", encoding="utf-8", newline="\n")
    _svn(wc, "add", "-q", "--force", ".claude")
    _svn(wc, "ci", "-q", "-m", "derived in")
    (mem / "episodic").mkdir()
    _svn(wc, "add", "-q", str(mem / "episodic"))  # 排程加入、未提交 → revert 即可
    marker = tmp_path / "m.json"

    lines = vi.advisory_lines(mem, marker, today="2026-10-01")
    warn = [ln for ln in lines if "已被SVN 版控" in ln]
    assert len(warn) == 1, lines
    w = warn[0]
    assert all(n in w for n in (INDEX_JSON, INDEX_MD, "_staging", "episodic")), w
    assert (f'svn rm --keep-local --force "{mem / INDEX_JSON}" "{mem / INDEX_MD}" "{mem / "_staging"}"'
            f' && svn revert "{mem / "episodic"}"') in w, w
    assert "svn resolve --accept working" in w and "svn:ignore 對已版控檔無效" in w, w
    assert "--rebuild --memory-dir" in w and "2026-09-23" in w, w
    assert vi.advisory_lines(mem, marker) == []
    # 唯讀：沒有自動 rm／revert
    tracked = vi.tracked_derived(mem)["svn"]
    assert tracked[INDEX_JSON] == "normal" and tracked["episodic"] == "added", tracked


# ─── 7. 零成本邊界 ───────────────────────────────────────────────────────────


def test_no_vcs_zero_subprocess(tmp_path, monkeypatch):
    mem = _mem(tmp_path)
    mem.mkdir(parents=True)
    monkeypatch.setattr(vi.subprocess, "run", _boom)
    assert vi.ensure_ignore(mem) == []
    assert vi.tracked_derived(mem) == {}
    marker = tmp_path / "m.json"
    assert vi.advisory_lines(mem, marker) == [] and not marker.exists()


def test_under_claude_dir_zero_lines(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".git").mkdir(parents=True)
    monkeypatch.setattr(vi, "_CLAUDE_DIR", home / ".claude")
    mem = home / ".claude" / "projects" / "x" / "memory"
    mem.mkdir(parents=True)
    monkeypatch.setattr(vi.subprocess, "run", _boom)
    assert vi.advisory_lines(mem, tmp_path / "m.json") == []
    assert ss._vcs_ignore_advisory(None) == []


# ─── 8. 索引首次落檔 ─────────────────────────────────────────────────────────


def test_index_first_save_sets_ignore_once(tmp_path, monkeypatch):
    import atom_index_json as aij
    root = _git_repo(tmp_path)
    mem = root / ".claude" / "memory"
    mem.mkdir(parents=True)
    aij.save_atom_index_json(mem, {"version": "1.0", "atoms": []})
    assert (mem / ".gitignore").exists()
    assert "_atom_index.json" in (mem / ".gitignore").read_text(encoding="utf-8")
    monkeypatch.setattr(vi.subprocess, "run", _boom)
    aij.save_atom_index_json(mem, {"version": "1.0", "atoms": []})  # 第二次：索引已在，不碰 VCS


# ─── 9. IndexConflict 訊息 ──────────────────────────────────────────────────


def test_svn_index_conflict_advisory_points_to_exit(tmp_path):
    wc = tmp_path / "wc"
    (wc / ".svn").mkdir(parents=True)
    mem = wc / ".claude" / "memory"
    mem.mkdir(parents=True)
    for n in (INDEX_JSON, "MEMORY.md"):
        (mem / n).write_text("x\n", encoding="utf-8", newline="\n")
        (mem / (n + ".mine")).write_text("y\n", encoding="utf-8", newline="\n")
    lines = ss._svn_index_conflict_advisory(str(wc), wc)
    assert len(lines) == 1, lines
    msg = lines[0]
    assert "MEMORY.md" in msg and INDEX_JSON in msg
    cmd = msg.split("svn rm --keep-local --force", 1)[1].split(" 後 commit", 1)[0]
    assert f'"{mem / INDEX_JSON}"' in cmd and "MEMORY.md" not in cmd, msg  # MEMORY.md 不是衍生檔
    assert "暫時處置" in msg and "merge-atom-index.py --resolve" in msg, msg
    (mem / (INDEX_JSON + ".mine")).unlink()
    only_memory = ss._svn_index_conflict_advisory(str(wc), wc)[0]
    assert "svn rm" not in only_memory and "→ 在 CC 下 svn commit 前 hook 會自動解" in only_memory, only_memory


def test_pre_tool_use_svn_resolve_message_carries_exit_hint(tmp_path):
    from handlers import pre_tool_use as ptu
    wc = tmp_path / "wc"
    (wc / ".svn").mkdir(parents=True)
    rels = [".claude/memory/_atom_index.json", ".claude/memory/MEMORY.md"]
    hint = ptu._svn_derived_exit_hint(str(wc), rels)
    assert hint.startswith("自動合併只是暫時處置") and "svn rm --keep-local --force" in hint, hint
    assert str(wc / ".claude" / "memory" / "_atom_index.json") in hint and "MEMORY.md" not in hint, hint
    assert ptu._svn_derived_exit_hint(str(wc), [".claude/memory/MEMORY.md"]) == ""
    assert ptu._svn_derived_exit_hint(str(tmp_path / "nowc"), rels) == ""


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
