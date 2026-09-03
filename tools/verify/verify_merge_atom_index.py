"""verify_merge_atom_index.py — 索引三檔 git 合併驅動（tools/merge-atom-index.py）。

三層：
  1. 純函式：JSON / _ATOM_INDEX.md / MEMORY.md 各自的語意三方規則（兩側各加、一側刪、兩側同改、CRLF、壞 JSON）
  2. 真 git：tmp repo 掛 .gitattributes + repo-local driver，merge 與 rebase 都零衝突且內容正確、blob 為 LF
  3. 安裝：--install 寫到隔離的 GIT_CONFIG_GLOBAL / XDG_CONFIG_HOME，重跑冪等
另附「driver 執行當下工作樹只有 HEAD 側 atom 檔」實測（設計依據：為何不從磁碟重建）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent
DRIVER = CLAUDE_DIR / "tools" / "merge-atom-index.py"
PY = sys.executable
_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}

_spec = importlib.util.spec_from_file_location("merge_atom_index", DRIVER)
drv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drv)


# ─── helpers ───────────────────────────────────────────────────────────────

def _index(*atoms):
    return {"version": "1.0", "atoms": [
        {"name": n, "path": p, "triggers": list(t), "scope": "shared"} for n, p, t in atoms]}


def _json_text(d, eol="\n"):
    return json.dumps(d, ensure_ascii=False, indent=2).replace("\n", eol)


def _md_table(*atoms):
    head = ["# Atom Trigger Index — Global", "", "> **Deprecated mirror.** Machine source: `_atom_index.json`.",
            "", "| Atom | Path | Trigger | Scope |", "|------|------|---------|-------|"]
    rows = [f"| {n} | {p} | {', '.join(t)} | shared |" for n, p, t in atoms]
    return "\n".join(head + rows) + "\n"


def _memory_md(counts, free_text="人寫的說明段。"):
    rows = "\n".join(f"| {k} | {v} | `memory/shared/{k}/` |" for k, v in counts.items())
    return (f"# Atom Index — Project\n\n{free_text}\n\n<!-- atom-catalog -->\n> 範疇目錄（自動生成）\n\n"
            f"| 範疇 | atom 數 | 深入 |\n|------|------|------|\n{rows}\n<!-- /atom-catalog -->\n")


def _run(tmp_path, base, ours, theirs, hint=""):
    p = {}
    for k, v in (("base", base), ("ours", ours), ("theirs", theirs)):
        p[k] = tmp_path / k
        p[k].write_bytes(v.encode("utf-8"))
    rc = drv.run_driver(str(p["base"]), str(p["ours"]), str(p["theirs"]), hint)
    return rc, p["ours"].read_bytes().decode("utf-8")


A = ("a", "memory/shared/Server/a.md", ("port", "架構"))
B = ("b", "memory/shared/Server/b.md", ("build",))
C = ("c", "memory/shared/Tools/c.md", ("jenkins",))


# ─── 1. JSON ───────────────────────────────────────────────────────────────

def test_json_both_add(tmp_path):
    rc, out = _run(tmp_path, _json_text(_index(A)), _json_text(_index(A, B)), _json_text(_index(A, C)), "x/_atom_index.json")
    assert rc == 0
    d = json.loads(out)
    assert [a["name"] for a in d["atoms"]] == ["a", "b", "c"]
    assert "\r" not in out and not out.endswith("\n")  # 與 lib 寫檔同格式：LF、無尾換行


def test_json_delete_vs_unchanged_and_modify(tmp_path):
    base = _index(A, B, C)
    ours = _index(A, C)  # 刪 b
    theirs = _index(A, B, C)
    theirs["atoms"][0]["triggers"].append("新觸發")  # 改 a
    rc, out = _run(tmp_path, _json_text(base), _json_text(ours), _json_text(theirs), "_atom_index.json")
    d = json.loads(out)
    assert rc == 0 and [a["name"] for a in d["atoms"]] == ["a", "c"]
    assert d["atoms"][0]["triggers"] == ["port", "架構", "新觸發"]


def test_json_delete_vs_modify_keeps_modified(tmp_path):
    base = _index(A, B)
    ours = _index(A)
    theirs = _index(A, B)
    theirs["atoms"][1]["scope"] = "personal"
    rc, out = _run(tmp_path, _json_text(base), _json_text(ours), _json_text(theirs), "_atom_index.json")
    assert rc == 0 and [a["name"] for a in json.loads(out)["atoms"]] == ["a", "b"]


def test_json_both_modify_same_atom_union_triggers(tmp_path):
    base, ours, theirs = _index(A), _index(A), _index(A)
    ours["atoms"][0]["triggers"] = ["port", "ours新"]  # 刪 架構、加 ours新
    theirs["atoms"][0]["triggers"] = ["port", "架構", "theirs新"]
    theirs["atoms"][0]["scope"] = "global"
    rc, out = _run(tmp_path, _json_text(base), _json_text(ours), _json_text(theirs), "_atom_index.json")
    a = json.loads(out)["atoms"][0]
    assert rc == 0 and a["triggers"] == ["port", "ours新", "theirs新"] and a["scope"] == "global"


def test_json_top_level_layout_marker_and_crlf(tmp_path):
    base = _index(A)
    ours = dict(_index(A, B), layout="scope-v2")
    theirs = _index(A, C)
    rc, out = _run(tmp_path, _json_text(base), _json_text(ours, eol="\r\n"), _json_text(theirs), "%P")
    d = json.loads(out)
    assert rc == 0 and d["layout"] == "scope-v2" and len(d["atoms"]) == 3 and "\r" not in out


def test_json_broken_side_falls_back_with_conflict(tmp_path):
    rc, out = _run(tmp_path, _json_text(_index(A)), _json_text(_index(A, B)), '{"version": "1.0", "atoms": [ BROKEN', "_atom_index.json")
    assert rc == 1 and "<<<<<<<" in out


# ─── 2. _ATOM_INDEX.md ─────────────────────────────────────────────────────

def test_atom_index_md_both_add_and_delete(tmp_path):
    rc, out = _run(tmp_path, _md_table(A, B), _md_table(A, B, C), _md_table(A), "_ATOM_INDEX.md")
    assert rc == 0
    rows = [ln for ln in out.split("\n") if ln.startswith("| ") and "| memory/" in ln]
    assert [r.split("|")[1].strip() for r in rows] == ["a", "c"]
    assert out.startswith("# Atom Trigger Index") and out.endswith("|\n")


def test_atom_index_md_trigger_cell_union(tmp_path):
    A2 = ("a", A[1], ("port", "架構", "ours新"))
    A3 = ("a", A[1], ("port", "theirs新"))
    rc, out = _run(tmp_path, _md_table(A), _md_table(A2), _md_table(A3), "_ATOM_INDEX.md")
    assert rc == 0 and "| port, ours新, theirs新 |" in out


# ─── 3. MEMORY.md ──────────────────────────────────────────────────────────

def test_memory_md_counts_sum_deltas_and_new_category(tmp_path):
    base = _memory_md({"Server": 20})
    ours = _memory_md({"Server": 21})
    theirs = _memory_md({"Server": 21, "Tools": 1})
    rc, out = _run(tmp_path, base, ours, theirs, "MEMORY.md")
    assert rc == 0 and "| Server | 22 |" in out and "| Tools | 1 |" in out and "<<<<<<<" not in out


def test_memory_md_root_style_without_markers(tmp_path):
    def root(counts):
        rows = "\n".join(f"| {k} | {v} | `memory/{k}/_INDEX.md` |" for k, v in counts.items())
        return f"# Atom Index — Global\n\n> 說明\n\n| 範疇 | atom 數 | 深入 |\n|------|---------|------|\n{rows}\n\n> 尾註\n"
    rc, out = _run(tmp_path, root({"版控": 9, "dotnet": 10}), root({"版控": 10, "dotnet": 10}), root({"版控": 9, "dotnet": 12}), "MEMORY.md")
    assert rc == 0 and "| 版控 | 10 |" in out and "| dotnet | 12 |" in out and out.endswith("> 尾註\n")


def test_memory_md_row_emptied_on_one_side(tmp_path):
    rc, out = _run(tmp_path, _memory_md({"Server": 3, "Tools": 2}), _memory_md({"Server": 4, "Tools": 2}), _memory_md({"Server": 3}), "MEMORY.md")
    assert rc == 0 and "| Server | 4 |" in out and "Tools" not in out.split("<!-- atom-catalog -->")[1]


def test_memory_md_free_text_conflict_keeps_markers(tmp_path):
    rc, out = _run(tmp_path, _memory_md({"Server": 1}, "原文"), _memory_md({"Server": 2}, "ours 改"), _memory_md({"Server": 2}, "theirs 改"), "MEMORY.md")
    assert rc == 1 and "<<<<<<<" in out


def test_memory_md_free_text_edits_on_both_sides_merge(tmp_path):
    base = _memory_md({"Server": 1}, "第一段")
    ours = base.replace("# Atom Index — Project", "# Atom Index — Project（ours 改標題）")
    theirs = _memory_md({"Server": 2}, "第一段\n\ntheirs 加的段落")
    rc, out = _run(tmp_path, base, ours, theirs, "MEMORY.md")
    assert rc == 0 and "ours 改標題" in out and "theirs 加的段落" in out and "| Server | 2 |" in out


def test_kind_sniff_without_path_hint(tmp_path):
    rc, out = _run(tmp_path, _md_table(A), _md_table(A, B), _md_table(A, C), "")
    assert rc == 0 and "| b |" in out and "| c |" in out


# ─── 4. 真 git：merge 與 rebase ─────────────────────────────────────────────

def _git(repo, *args, check=True, env=None):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, **_NO_WINDOW)
    if check and r.returncode:
        raise AssertionError(f"git {' '.join(args)} failed rc={r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def _write_index_set(mem: Path, atoms, counts, json_eol="\n"):
    (mem / "_atom_index.json").write_bytes(_json_text(_index(*atoms), eol=json_eol).encode("utf-8"))
    (mem / "_ATOM_INDEX.md").write_bytes(_md_table(*atoms).encode("utf-8"))
    (mem / "MEMORY.md").write_bytes(_memory_md(counts).encode("utf-8"))
    for n, p, _t in atoms:
        f = mem.parent.parent / p.replace("memory/", ".claude/memory/", 1)
        f.parent.mkdir(parents=True, exist_ok=True)
        if not f.exists():
            f.write_text(f"# {n}\n", encoding="utf-8")


def _make_repo(tmp_path: Path, *, install_driver=True) -> Path:
    repo = tmp_path / "proj"
    mem = repo / ".claude" / "memory"
    mem.mkdir(parents=True)
    _git(tmp_path, "init", "-q", "-b", "master", str(repo))
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "core.autocrlf", "false")
    if install_driver:
        _git(repo, "config", "merge.atomindex.driver", drv.driver_command())
    (repo / ".gitattributes").write_text("\n".join(drv.ATTR_LINES) + "\n", encoding="utf-8")
    _write_index_set(mem, [A], {"Server": 1})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    # 分支 A：加 b（Server 2）；master：加 c（Server 1 + Tools 1），JSON 故意寫 CRLF
    _git(repo, "checkout", "-qb", "A")
    _write_index_set(mem, [A, B], {"Server": 2})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "A adds b")
    _git(repo, "checkout", "-q", "master")
    _write_index_set(mem, [A, C], {"Server": 1, "Tools": 1}, json_eol="\r\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "master adds c")
    return repo


def _assert_merged(repo: Path):
    mem = repo / ".claude" / "memory"
    d = json.loads((mem / "_atom_index.json").read_text(encoding="utf-8"))
    assert sorted(a["name"] for a in d["atoms"]) == ["a", "b", "c"]
    md = (mem / "_ATOM_INDEX.md").read_text(encoding="utf-8")
    assert "| b |" in md and "| c |" in md and "<<<<<<<" not in md
    mm = (mem / "MEMORY.md").read_text(encoding="utf-8")
    assert "| Server | 2 |" in mm and "| Tools | 1 |" in mm and "<<<<<<<" not in mm
    for n in ("a", "b"):
        assert (mem / "shared" / "Server" / f"{n}.md").exists()
    assert (mem / "shared" / "Tools" / "c.md").exists()
    for f in ("_atom_index.json", "_ATOM_INDEX.md", "MEMORY.md"):
        assert b"\r" not in _git(repo, "show", f"HEAD:.claude/memory/{f}").stdout.encode("utf-8")


def test_git_merge_is_clean(tmp_path):
    repo = _make_repo(tmp_path)
    r = _git(repo, "merge", "A", "-m", "merge A")
    assert "CONFLICT" not in r.stdout + r.stderr
    assert "[merge-atom-index]" in r.stderr
    _assert_merged(repo)


def test_git_rebase_is_clean(tmp_path):
    repo = _make_repo(tmp_path)
    r = _git(repo, "rebase", "A")
    assert "CONFLICT" not in r.stdout + r.stderr
    _assert_merged(repo)
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""


def test_without_driver_same_scenario_conflicts(tmp_path):
    """對照組：沒裝驅動 → 三檔全衝突（＝使用者實際遇到的狀況）。"""
    repo = _make_repo(tmp_path, install_driver=False)
    # 本機 global config 可能已 --install 過驅動 → 用空的 global/system config 隔離，重現「沒裝」
    (tmp_path / "empty-gitconfig").write_text("", encoding="utf-8")
    env = dict(os.environ, GIT_CONFIG_GLOBAL=str(tmp_path / "empty-gitconfig"), GIT_CONFIG_NOSYSTEM="1")
    r = _git(repo, "merge", "A", "-m", "merge A", check=False, env=env)
    out = r.stdout + r.stderr
    assert r.returncode != 0
    for f in ("MEMORY.md", "_ATOM_INDEX.md", "_atom_index.json"):
        assert f"Merge conflict in .claude/memory/{f}" in out


def test_driver_time_worktree_lacks_other_side(tmp_path):
    """設計依據：merge driver 執行當下工作樹只有 HEAD 那側的 atom 檔 → 從磁碟重建會丟另一側。"""
    repo = _make_repo(tmp_path, install_driver=False)
    log = tmp_path / "probe.log"
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import os,sys,pathlib\n"
        f"p=pathlib.Path(r'{log}')\n"
        "names=sorted(x.name for x in pathlib.Path('.claude/memory/shared').rglob('*.md'))\n"
        "p.write_text(' '.join(names))\n"
        "sys.exit(1)\n", encoding="utf-8")
    _git(repo, "config", "merge.atomindex.driver", f'"{PY}" "{probe}" %O %A %B %P')
    _git(repo, "merge", "A", "-m", "m", check=False)
    seen = log.read_text()
    assert "c.md" in seen and "b.md" not in seen  # merge：只有自己（master）的 c，沒有對方的 b
    _git(repo, "merge", "--abort")
    _git(repo, "rebase", "A", check=False)
    seen = log.read_text()
    assert "b.md" in seen and "c.md" not in seen  # rebase：只有 upstream 的 b，沒有自己的 c
    _git(repo, "rebase", "--abort")


# ─── 5. --install 冪等（隔離 global config） ────────────────────────────────

def test_install_and_status_isolated(tmp_path):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=str(tmp_path / "gitconfig"), XDG_CONFIG_HOME=str(tmp_path / "xdg"),
               HOME=str(tmp_path), USERPROFILE=str(tmp_path))
    for _ in range(2):
        r = subprocess.run([PY, str(DRIVER), "--install"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, **_NO_WINDOW)
        assert r.returncode == 0, r.stderr
    attr = tmp_path / "xdg" / "git" / "attributes"
    text = attr.read_text(encoding="utf-8")
    assert text.count(drv.ATTR_MARK) == 1 and text.count("merge=atomindex text eol=lf") == 3
    cfg = subprocess.run(["git", "config", "--global", "--get", "merge.atomindex.driver"], capture_output=True,
                         text=True, encoding="utf-8", env=env, **_NO_WINDOW).stdout.strip()
    assert cfg.endswith("%O %A %B %P") and "merge-atom-index.py" in cfg
    r = subprocess.run([PY, str(DRIVER), "--status"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, **_NO_WINDOW)
    assert r.returncode == 0 and "已安裝" in r.stdout


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
