#!/usr/bin/env python3
"""normalize-eol.py — 把文字檔的換行統一成 LF（根層 repo 與專案記憶樹共用）

為什麼：Windows 上的 Python 文字模式寫檔預設會把 \\n 翻成 \\r\\n，多年下來 repo 混著 LF 與 CRLF；
兩台機器各寫一次同一個檔就變成整檔衝突。規則定為「全部 LF」，本工具負責存量轉換與之後的巡檢。

用法：
  python tools/normalize-eol.py --root [--include-dirty] [--check] [--repo <path>]
      根層 repo（預設 ~/.claude）的 git 追蹤檔。
      乾淨檔：工作樹轉 LF 並 git add。
      --include-dirty：別的 session 正在改的檔也處理——工作樹就地轉 LF，index 則寫入「HEAD 版本正規化成 LF」的
      blob（純換行差異、不掃進別人的內容改動）；untracked 檔只轉工作樹不 add。
      --check：唯讀。列出 index／工作樹仍有 CRLF 或 mixed 的檔（含 untracked），有殘留 exit 1。
  python tools/normalize-eol.py --memory-dir <dir> [--check] [--write-gitattributes | --auto]
      專案 .claude/memory 樹（不分 tracked／untracked，跳過 _vectordb、__pycache__、.svn）。
      --write-gitattributes：在該 repo 的 .gitattributes 寫入帶標記的區塊（重跑整段換新）：memory 樹 text eol=lf
      ＋索引三檔 merge=atomindex，寫完用 git check-attr 驗證。
      --auto：依最近的 VCS 根自動選——git 同 --write-gitattributes；svn 對已版控文字檔 svn propset svn:eol-style LF
      （已是 LF 的略過，冪等）；無 VCS 只轉檔。tools/sync-memory-index.py 專案模式 --write 後就是呼叫這條
      （auto_project_eol），使用者不必貼任何 prompt。
  python tools/normalize-eol.py --all-projects [--check]
      所有登記專案的 memory dir（hooks/wg_core.discover_all_project_memory_dirs）。

判定：整檔含 NUL → 當二進位跳過並列出；\\r\\n 與孤立 \\r 都視為換行、一律變 \\n；UTF-8 BOM 原樣保留。
列舉一律用 git 的 -z 輸出（非 ASCII 路徑不會被引號化漏掉）。
stdout 最後一行是 JSON 摘要；人讀訊息走 stderr。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CLAUDE_DIR = Path(__file__).resolve().parent.parent
INDEX_FILES = ("MEMORY.md", "_ATOM_INDEX.md", "_atom_index.json")
ATTR_MARK = "# AtomicMemory eol/merge rules"
SKIP_DIR_PARTS = {"_vectordb", "__pycache__", "node_modules", ".git", ".svn"}
_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}


def _say(msg: str) -> None:
    try:
        sys.stderr.write(msg + "\n")
    except Exception:
        pass


def _git(repo: Path, *args: str, inp: Optional[bytes] = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], input=inp, capture_output=True, timeout=60, **_NO_WINDOW)


def _git_z(repo: Path, *args: str) -> List[str]:
    r = _git(repo, *args)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.decode('utf-8', 'replace').strip()}")
    return [p.decode("utf-8", "surrogateescape") for p in r.stdout.split(b"\0") if p]


# ─── 位元組層判定與轉換 ─────────────────────────────────────────────────────

def classify(raw: bytes) -> str:
    """回 'binary' / 'lf' / 'crlf' / 'mixed' / 'cr'。"""
    if b"\0" in raw:
        return "binary"
    crlf = raw.count(b"\r\n")
    cr_total = raw.count(b"\r")
    lone_cr = cr_total - crlf
    lf_total = raw.count(b"\n")
    lone_lf = lf_total - crlf
    if cr_total == 0:
        return "lf"
    if crlf and not lone_cr and not lone_lf:
        return "crlf"
    if lone_cr and not crlf and not lone_lf:
        return "cr"
    return "mixed"


def to_lf(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _write_bytes_atomic(path: Path, data: bytes, expect: bytes) -> bool:
    """寫前重讀比對（縮小與其他行程的競態窗）；內容變了就放棄回 False。"""
    if path.read_bytes() != expect:
        return False
    tmp = path.with_suffix(path.suffix + f".lf.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return True


# ─── 根層 repo 模式 ────────────────────────────────────────────────────────

def _dirty_sets(repo: Path) -> Tuple[set, set]:
    """回 (tracked 但有改動的路徑, untracked 路徑)。用 -z 解析 porcelain v1。"""
    r = _git(repo, "status", "--porcelain", "-z", "--untracked-files=all")
    items = r.stdout.split(b"\0")
    dirty, untracked = set(), set()
    i = 0
    while i < len(items):
        ent = items[i]
        if not ent:
            i += 1
            continue
        xy, path = ent[:2].decode("ascii", "replace"), ent[3:].decode("utf-8", "surrogateescape")
        if xy == "??":
            untracked.add(path)
        else:
            dirty.add(path)
            if xy[0] in "RC":  # rename/copy 多帶一個舊路徑
                i += 1
        i += 1
    return dirty, untracked


def _index_modes(repo: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for ent in _git_z(repo, "ls-files", "-s", "-z"):
        meta, _, path = ent.partition("\t")
        out[path] = meta.split(" ")[0]
    return out


def _stage_head_normalized(repo: Path, path: str, mode: str) -> bool:
    """index 寫入「HEAD 版本正規化成 LF」的 blob；HEAD 沒這檔（新增中）就跳過。"""
    r = _git(repo, "show", f"HEAD:{path}")
    if r.returncode != 0:
        return False
    blob = _git(repo, "hash-object", "-w", "--stdin", inp=to_lf(r.stdout))
    sha = blob.stdout.decode().strip()
    upd = _git(repo, "update-index", "--cacheinfo", f"{mode},{sha},{path}")
    return upd.returncode == 0


def run_root(repo: Path, *, include_dirty: bool, check: bool) -> Tuple[Dict, int]:
    tracked = _git_z(repo, "ls-files", "-z")
    dirty, untracked = _dirty_sets(repo)
    modes = _index_modes(repo) if include_dirty and not check else {}
    rep: Dict[str, List] = {"converted_added": [], "converted_head_staged": [], "converted_untracked": [],
                            "skipped_dirty": [], "skipped_binary": [], "skipped_missing": [], "residual_index": [],
                            "residual_worktree": []}
    candidates = [(p, "tracked") for p in tracked] + [(p, "untracked") for p in sorted(untracked)]
    for rel, kind in candidates:
        fp = repo / rel
        if not fp.is_file():
            rep["skipped_missing"].append(rel)
            continue
        raw = fp.read_bytes()
        cls = classify(raw)
        if cls == "binary":
            rep["skipped_binary"].append(rel)
            continue
        if cls == "lf":
            continue
        if check:
            rep["residual_worktree"].append(f"{rel} ({cls}, {kind})")
            continue
        if kind == "untracked":
            if include_dirty and _write_bytes_atomic(fp, to_lf(raw), raw):
                rep["converted_untracked"].append(rel)
            else:
                rep["skipped_dirty"].append(rel)
            continue
        if rel in dirty:
            if not include_dirty:
                rep["skipped_dirty"].append(rel)
                continue
            if _write_bytes_atomic(fp, to_lf(raw), raw):
                _stage_head_normalized(repo, rel, modes.get(rel, "100644"))
                rep["converted_head_staged"].append(rel)
            else:
                rep["skipped_dirty"].append(rel)
            continue
        if _write_bytes_atomic(fp, to_lf(raw), raw):
            _git(repo, "add", "--", rel)
            rep["converted_added"].append(rel)
        else:
            rep["skipped_dirty"].append(rel)
    # index 端殘留（不論 check 與否都報，作為結果守衛）
    for ent in _git_z(repo, "ls-files", "--eol", "-z"):
        meta, _, path = ent.partition("\t")
        fields = meta.split()
        i_attr = next((f for f in fields if f.startswith("i/")), "i/none")
        if i_attr in ("i/crlf", "i/mixed"):
            rep["residual_index"].append(f"{path} ({i_attr})")
    if check:
        # dirty 檔工作樹狀態也在 residual_worktree 裡（candidates 含 tracked 全部＋untracked）
        pass
    rc = 1 if (rep["residual_index"] or rep["residual_worktree"]) else 0
    return rep, rc


# ─── 專案 memory 樹模式 ───────────────────────────────────────────────────

def _iter_memory_files(mem_dir: Path):
    for p in sorted(mem_dir.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_DIR_PARTS for part in p.relative_to(mem_dir).parts):
            continue
        yield p


def run_memory_dir(mem_dir: Path, *, check: bool) -> Tuple[Dict, int]:
    rep: Dict[str, List] = {"converted": [], "skipped_binary": [], "residual_worktree": []}
    for fp in _iter_memory_files(mem_dir):
        raw = fp.read_bytes()
        cls = classify(raw)
        if cls == "binary":
            rep["skipped_binary"].append(str(fp))
        elif cls != "lf":
            if check:
                rep["residual_worktree"].append(f"{fp} ({cls})")
            elif _write_bytes_atomic(fp, to_lf(raw), raw):
                rep["converted"].append(str(fp))
    return rep, (1 if rep["residual_worktree"] else 0)


def _attr_block(prefix: str) -> str:
    lines = [f"{ATTR_MARK}（python ~/.claude/tools/normalize-eol.py --write-gitattributes 寫入；重跑會整段換新）",
             f"{prefix}/** text eol=lf"]
    lines += [f"{prefix}/{n} merge=atomindex" for n in INDEX_FILES]
    return "\n".join(lines) + "\n"


def write_gitattributes(mem_dir: Path) -> Dict:
    top = _git(mem_dir, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return {"ok": False, "error": "memory dir 不在 git repo 內"}
    root = Path(top.stdout.decode("utf-8", "replace").strip())
    prefix = mem_dir.resolve().relative_to(root.resolve()).as_posix()
    ga = root / ".gitattributes"
    cur = ga.read_bytes().decode("utf-8", "replace").replace("\r\n", "\n") if ga.exists() else ""
    if ATTR_MARK in cur:
        head, _, rest = cur.partition(ATTR_MARK)
        rest_lines = rest.split("\n")[1:]
        while rest_lines and rest_lines[0].startswith(prefix + "/"):
            rest_lines.pop(0)
        cur = head + "\n".join(rest_lines)
    cur = cur.rstrip("\n")
    new = (cur + "\n\n" if cur else "") + _attr_block(prefix)
    tmp = ga.with_suffix(".tmp")
    tmp.write_bytes(new.encode("utf-8"))
    os.replace(tmp, ga)
    paths = [f"{prefix}/{n}" for n in INDEX_FILES]
    chk = _git(root, "check-attr", "merge", "text", "eol", "--", *paths)
    lines = chk.stdout.decode("utf-8", "replace").replace("\r\n", "\n").strip().split("\n")
    ok = all(any(l.endswith(": merge: atomindex") and l.startswith(p) for l in lines) for p in paths) \
        and all(any(l.endswith(": eol: lf") and l.startswith(p) for l in lines) for p in paths)
    return {"ok": ok, "gitattributes": str(ga), "check_attr": lines}


def _wg_core():
    hooks = CLAUDE_DIR / "hooks"
    if str(hooks) not in sys.path:
        sys.path.insert(0, str(hooks))
    import wg_core  # noqa: E402
    return wg_core


def _project_memory_dirs() -> List[Tuple[str, Path]]:
    return [(slug, mem) for slug, mem in _wg_core().discover_all_project_memory_dirs() if mem.is_dir()]


# ─── SVN：svn:eol-style=LF ─────────────────────────────────────────────────

def _svn(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["svn", "--non-interactive", *args], capture_output=True, cwd=str(cwd), timeout=60,
                          **_NO_WINDOW)


def _norm_key(p) -> str:
    return os.path.normcase(str(Path(p).resolve()))


def svn_set_eol_props(mem_dir: Path, root: Path) -> Dict:
    """記憶樹裡已版控的文字檔設 svn:eol-style=LF。只用 --xml 輸出（UTF-8；純文字輸出走 locale，非 ASCII 路徑會壞）。
    明列 unversioned 檔會 rc 1、混行尾檔會被 svn 拒（所以先 run_memory_dir 轉完再呼叫）；已是 LF 的略過 → 第二次 set=0。"""
    import xml.etree.ElementTree as ET
    rep: Dict = {"set": 0, "already": 0, "error": None}
    st = _svn(root, "status", "-v", "--xml", "--", str(mem_dir))
    if st.returncode or not st.stdout.strip():
        rep["error"] = f"svn status 失敗：{st.stderr.decode('utf-8', 'replace').strip().splitlines()[-1:] or st.returncode}"
        return rep
    skip_items = {"unversioned", "ignored", "missing", "deleted", "none", "external"}
    versioned = set()
    for ent in ET.fromstring(st.stdout).iter("entry"):
        ws = ent.find("wc-status")
        if ws is not None and ws.get("item") not in skip_items:
            versioned.add(_norm_key(root / ent.get("path", "")))
    already = set()
    pg = _svn(root, "propget", "svn:eol-style", "--xml", "-R", "--", str(mem_dir))
    if pg.returncode == 0 and pg.stdout.strip():
        for t in ET.fromstring(pg.stdout).iter("target"):
            if (t.findtext("property") or "").strip() == "LF":
                already.add(_norm_key(t.get("path", "")))
    todo: List[str] = []
    for fp in _iter_memory_files(mem_dir):
        key = _norm_key(fp)
        if key not in versioned:
            continue
        if key in already:
            rep["already"] += 1
            continue
        if classify(fp.read_bytes()) != "binary":
            todo.append(str(fp))
    for i in range(0, len(todo), 200):
        r = _svn(root, "propset", "svn:eol-style", "LF", "--", *todo[i:i + 200])
        rep["set"] += r.stdout.count(b"property 'svn:eol-style' set on")
        if r.returncode:
            tail = r.stderr.decode("utf-8", "replace").strip().splitlines()
            rep["error"] = f"svn propset 部分失敗：{tail[-1] if tail else 'rc=' + str(r.returncode)}"
    return rep


def auto_project_eol(mem_dir: Path) -> Dict:
    """專案記憶樹 LF 自動化（sync-memory-index 專案模式 --write 後呼叫）：樹內轉 LF → 依最近的 VCS 根
    git 寫 .gitattributes 區塊／svn 設 svn:eol-style=LF／無 VCS 只轉檔。不 raise；問題寫進 error。"""
    rep: Dict = {"dir": str(mem_dir), "vcs": None, "converted": 0, "skipped_binary": 0, "attrs": None, "error": None}
    try:
        conv, _rc = run_memory_dir(mem_dir, check=False)
        rep["converted"], rep["skipped_binary"] = len(conv["converted"]), len(conv["skipped_binary"])
        vcs = _wg_core().find_vcs_root(mem_dir)
        if vcs is None:
            return rep
        kind, root = vcs
        rep["vcs"] = kind
        attrs = write_gitattributes(mem_dir) if kind == "git" else svn_set_eol_props(mem_dir, root)
        rep["attrs"] = attrs
        if attrs.get("error"):
            rep["error"] = attrs["error"]
        elif kind == "git" and not attrs.get("ok"):
            rep["error"] = f".gitattributes 寫入後 check-attr 驗證未通過：{attrs.get('check_attr')}"
    except Exception as e:  # noqa: BLE001
        rep["error"] = f"{type(e).__name__}: {e}"
    return rep


# ─── CLI ──────────────────────────────────────────────────────────────────

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="統一換行為 LF（根層 repo／專案記憶樹）")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--root", action="store_true", help="根層 repo 的 git 追蹤檔")
    mode.add_argument("--memory-dir", type=Path, help="專案 .claude/memory 樹")
    mode.add_argument("--all-projects", action="store_true", help="所有登記專案的 memory dir")
    ap.add_argument("--repo", type=Path, default=CLAUDE_DIR, help="--root 的 repo 路徑（預設 ~/.claude；測試用）")
    ap.add_argument("--include-dirty", action="store_true", help="--root：連別的 session 正在改的檔與 untracked 一起處理")
    ap.add_argument("--check", action="store_true", help="唯讀巡檢，有殘留 exit 1")
    ap.add_argument("--write-gitattributes", action="store_true", help="--memory-dir：在該 repo 的 .gitattributes 寫入規則區塊")
    ap.add_argument("--auto", action="store_true", help="--memory-dir：依 VCS 自動（git .gitattributes／svn eol-style）")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if a.root:
        rep, rc = run_root(a.repo.resolve(), include_dirty=a.include_dirty, check=a.check)
        for k, v in rep.items():
            if v:
                _say(f"[normalize-eol] {k}: {len(v)}" + ("" if len(v) > 12 else " → " + ", ".join(v)))
        print(json.dumps({"mode": "root", "check": a.check, "rc": rc, **{k: len(v) for k, v in rep.items()},
                          "residual": rep["residual_index"] + rep["residual_worktree"]}, ensure_ascii=False))
        return rc

    if a.memory_dir and a.auto and not a.check:
        rep = auto_project_eol(a.memory_dir.resolve())
        if rep["error"]:
            _say(f"[normalize-eol] {rep['error']}")
        print(json.dumps({"mode": "memory-dir-auto", **rep}, ensure_ascii=False))
        return 1 if rep["error"] else 0

    if a.memory_dir:
        mem = a.memory_dir.resolve()
        rep, rc = run_memory_dir(mem, check=a.check)
        if a.write_gitattributes and not a.check:
            rep["gitattributes"] = write_gitattributes(mem)
            if not rep["gitattributes"].get("ok"):
                rc = 1
        for k, v in rep.items():
            if isinstance(v, list) and v:
                _say(f"[normalize-eol] {k}: {len(v)}")
        print(json.dumps({"mode": "memory-dir", "dir": str(mem), "check": a.check, "rc": rc, **rep}, ensure_ascii=False))
        return rc

    worst = 0
    summary = []
    for slug, mem in _project_memory_dirs():
        rep, rc = run_memory_dir(mem, check=a.check)
        worst = max(worst, rc)
        summary.append({"project": slug, "dir": str(mem), "rc": rc, **{k: len(v) for k, v in rep.items()}})
    print(json.dumps({"mode": "all-projects", "check": a.check, "rc": worst, "projects": summary}, ensure_ascii=False))
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
