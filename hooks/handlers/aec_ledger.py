"""aec_ledger.py — per-session 產出物帳本：這個 session 額外留下的東西（Python 唯一 writer）。

路徑固定：workflow/aec-tempfiles/<sid>.jsonl（append-only，一行一 JSON；同一樣東西後寫者勝）。
類別（kind）：file／dir（檔案、資料夾）、worktree（git 工作樹）、branch（本地分支）、
remote_branch（推上遠端的分支）、repo（git init／clone 出來的臨時 repo）。舊帳沒有 kind，當 file／dir。
進帳來源（source）：
  write  = PostToolUse Write／NotebookEdit 寫的檔；Edit 只收系統暫存區（Edit 只改既有檔，新檔已由 Write 收）
  bash   = PostToolUse Bash／PowerShell：寫入目標（wg_core.write_paths_from_tool：mkdir、轉向、cp…）
           與 git 指令（worktree add、checkout -b、switch -c、branch、init、clone、push 新分支）
  aec-i  = anti_evasion_report (i) 欄「一行一路徑」宣告（`<路徑> — <備註>`）
  scan   = Stop／收尾時直接 listdir session scratchpad（補模型忘了列的）

帳本只記「進過帳」的東西；「還在不在、能不能刪」不記——由 artifact_status 當下查檔案系統與 git
（權威在那裡，不信模型自報）。檔案進了版控＝正式產出，自動掉出清單。不做 TTL：帳上有、還在 → HUD 一直列到被處置。
刪除由 delete_artifact 當場執行（HUD 按鈕 → Node → tools/session-artifacts.py），不經模型、不等下一則訊息。
fail-open：記帳路徑上任何 I/O 例外都吞掉，不阻斷 hook。

受保護路徑（is_protected_path）一律拒收，不論來源：VCS 已追蹤的檔、memory/ 與 _AIDocs/ 之下、
索引／CHANGELOG／核心設定 md。理由：帳本裡的每一列在 HUD 都配「刪除」鈕，正式產出（改了還沒
commit 的 code/doc/atom/索引）不是「衍生暫存」，模型錯報進 (i) 也不能變成可一鍵刪的候選。
"""
from __future__ import annotations

import glob as _glob
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from wg_core import WORKFLOW_DIR

LEDGER_DIR_NAME = "aec-tempfiles"

# 受保護：路徑任一段等於這些目錄名（知識庫／文件庫，永遠不是暫存）
PROTECTED_DIR_NAMES = frozenset({"memory", "_AIDocs"})
# 受保護：檔名樣式（索引、變更紀錄、核心設定 md）
PROTECTED_BASENAME_RE = re.compile(
    r"^(?:_INDEX|_ATOM_INDEX|_CHANGELOG(?:_ARCHIVE)?|CLAUDE|MEMORY|IDENTITY|USER|TECH|README)(?:\.[^.]+)?$",
    re.IGNORECASE,
)
_VCS_TIMEOUT_S = 3


def _vcs_root_kind(path: str) -> str:
    """往上找 .git（檔或夾）/ .svn → 'git' | 'svn' | ''。純目錄走訪，不起子行程。"""
    try:
        cur = Path(path).resolve()
    except Exception:
        return ""
    for d in [cur] + list(cur.parents):
        try:
            if (d / ".git").exists():
                return "git"
            if (d / ".svn").is_dir():
                return "svn"
        except Exception:
            continue
    return ""


def vcs_tracked(path: str) -> bool:
    """git ls-files --error-unmatch / svn info 回 0 = 已追蹤。無 VCS 祖先 → False，不起子行程。
    任何例外（無 binary、timeout）→ False（fail-open 往「不受保護」偏——但 dir/basename 規則仍擋）。"""
    kind = _vcs_root_kind(path)
    if not kind:
        return False
    p = Path(path)
    if kind == "git":
        cmd = ["git", "-C", str(p.parent), "ls-files", "--error-unmatch", "--", p.name]
    else:
        cmd = ["svn", "info", "--non-interactive", str(p)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=_VCS_TIMEOUT_S,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode == 0
    except Exception:
        return False


def protected_reason(path: str) -> str:
    """回傳受保護原因字串；'' = 不受保護。順序：tempdir 直接放行 → 目錄名 → 檔名 → VCS（最貴放最後）。"""
    if not path:
        return ""
    if is_under_tempdir(path):
        return ""
    try:
        parts = Path(path).parts
    except Exception:
        return ""
    for seg in parts[:-1]:
        if seg in PROTECTED_DIR_NAMES:
            return f"位於受保護目錄 {seg}/"
    if parts and PROTECTED_BASENAME_RE.match(parts[-1]):
        return "受保護檔名（索引／CHANGELOG／核心 md）"
    if vcs_tracked(path):
        return "VCS 已追蹤"
    return ""


def is_protected_path(path: str) -> bool:
    return bool(protected_reason(path))

# (d) 行內「路徑 | 備註」分隔：em-dash / 全形冒號 / 全形括號 / 半形 " - "
_D_SPLIT_RE = re.compile(r"\s+—\s*|\s*—\s+|—|：|（|\s+-\s+")
_BULLET_RE = re.compile(r"^[-*•·]\s*")
_BLANK_RE = re.compile(r"^[無无]\s*(?:[（(][^）)]*[）)])?$")


def ledger_path(session_id: str) -> Path:
    return WORKFLOW_DIR / LEDGER_DIR_NAME / f"{session_id}.jsonl"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _key(p: str) -> str:
    """去重鍵：絕對化 + normcase（Windows 不分大小寫）。"""
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def _tempdir() -> str:
    try:
        return tempfile.gettempdir()
    except Exception:
        return ""


def is_under_tempdir(path: str) -> bool:
    """只認系統 tempdir 之下（scratchpad 在其中）；不擴到 tests/ 等 token 判斷，免誤收。"""
    if not path:
        return False
    tmp = _tempdir()
    if not tmp:
        return False
    try:
        return _key(path).startswith(_key(tmp) + os.sep)
    except Exception:
        return False


# ─── scratchpad 定位 ─────────────────────────────────────────────────────────


def _cwd_slug(cwd: str) -> str:
    """Claude Code 的專案 slug：cwd 內非 [A-Za-z0-9-] 一律換 '-'（`c:\\Users\\x\\.claude`
    → `c--Users-x--claude`）。大小寫照 cwd 原樣（磁碟機字母兩種寫法都見過，讀端兩種都試）。"""
    return re.sub(r"[^A-Za-z0-9-]", "-", cwd or "")


def scratchpad_dirs(cwd: str, session_id: str) -> List[Path]:
    """回傳存在的 session scratchpad 目錄（0~1 個；磁碟機字母大小寫兩種候選）。"""
    tmp = _tempdir()
    if not tmp or not cwd or not session_id:
        return []
    slug = _cwd_slug(cwd)
    cands = {slug}
    if slug[:1].isalpha():
        cands.add(slug[0].swapcase() + slug[1:])
    out: List[Path] = []
    seen: set = set()
    for s in sorted(cands):
        p = Path(tmp) / "claude" / s / session_id / "scratchpad"
        try:
            if not p.is_dir():
                continue
            k = os.path.normcase(os.path.realpath(p))   # 不分大小寫 FS：兩候選同一夾只收一次
            if k in seen:
                continue
            seen.add(k)
            out.append(p)
        except Exception:
            continue
    return out


def scan_scratchpad(cwd: str, session_id: str) -> List[Dict[str, Any]]:
    """listdir scratchpad 頂層（檔案與資料夾各一筆；資料夾不再深入——處置粒度就是頂層）。"""
    entries: List[Dict[str, Any]] = []
    for d in scratchpad_dirs(cwd, session_id):
        try:
            names = sorted(os.listdir(d))
        except Exception:
            continue
        for n in names:
            p = d / n
            entries.append({
                "path": str(p),
                "note": "scratchpad" + ("/" if p.is_dir() else ""),
                "source": "scan",
            })
    return entries


# ─── (d) 欄解析：一行一路徑 ───────────────────────────────────────────────────


def _resolve(raw: str, cwd: str) -> str:
    s = os.path.expandvars(os.path.expanduser(raw.strip().strip("`\"'")))
    m = re.match(r"^/([A-Za-z])(/.*)?$", s) if os.name == "nt" else None
    if m:   # Git Bash 寫法 /c/Users/… → C:/Users/…
        s = f"{m.group(1).upper()}:{m.group(2) or '/'}"
    if not os.path.isabs(s) and cwd:
        s = os.path.join(cwd, s)
    return s


def parse_declared_paths(
    d_text: str, cwd: str, rejected: Optional[List[Dict[str, str]]] = None
) -> List[Dict[str, Any]]:
    """(i) 衍生暫存欄每非空行 → `<路徑> — <備註>`；路徑取分隔符前第一個 token。
    只收「磁碟上此刻存在」的（含 glob 展開）；prose 行 / 已刪的 → 略過（已刪的沒有裁決價值）。
    受保護路徑不收，並記入 rejected（{path, reason}）供 caller 浮出訊號——靜默拒收違反可觀測性鐵律。"""
    out: List[Dict[str, Any]] = []
    for line in str(d_text or "").splitlines():
        raw = _BULLET_RE.sub("", line.strip())
        if not raw or _BLANK_RE.match(raw):
            continue
        parts = _D_SPLIT_RE.split(raw, maxsplit=1)
        head = parts[0].strip()
        note = parts[1].strip(" ）)") if len(parts) > 1 else ""
        tok = head.split()[0] if head.split() else ""
        tok = tok.strip("`\"'，,;；")
        if not tok or ("/" not in tok and "\\" not in tok and "." not in tok):
            continue   # 無路徑樣貌 → prose
        resolved = _resolve(tok, cwd)
        cands = _glob.glob(resolved) if any(ch in resolved for ch in "*?[") else [resolved]
        for c in cands:
            try:
                if not os.path.exists(c):
                    continue
                why = protected_reason(c)
                if why:
                    if rejected is not None:
                        rejected.append({"path": os.path.abspath(c), "reason": why})
                    continue
                out.append({"path": os.path.abspath(c), "note": note, "source": "aec-i"})
            except Exception:
                continue
    return out


# ─── 帳本 I/O ─────────────────────────────────────────────────────────────────


GIT_KINDS = frozenset({"worktree", "branch", "remote_branch", "repo"})
_REF_KINDS = frozenset({"branch", "remote_branch"})   # 沒有自己的路徑：path 欄放所屬 repo
_EXTRA_FIELDS = ("kind", "repo", "name", "remote", "cmd", "cwd")


def entry_key(rec: Dict[str, Any]) -> str:
    """同一樣東西的去重鍵：分支看（類別, repo, 遠端, 分支名）；其餘看路徑。"""
    kind = str(rec.get("kind") or "")
    if kind in _REF_KINDS:
        return f"{kind}:{_key(str(rec.get('repo') or rec.get('path') or ''))}:{rec.get('remote') or ''}:{rec.get('name') or ''}"
    return _key(str(rec.get("path", "") or ""))


def ledger_read(session_id: str) -> List[Dict[str, Any]]:
    """讀帳本並以 entry_key 去重（後寫者勝）。壞行略過。"""
    p = ledger_path(session_id)
    seen: Dict[str, Dict[str, Any]] = {}
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict) or not str(rec.get("path", "") or ""):
            continue
        seen[entry_key(rec)] = rec
    return list(seen.values())


def _write_lines(session_id: str, lines: List[str]) -> int:
    if not lines:
        return 0
    try:
        p = ledger_path(session_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except Exception:
        return 0
    return len(lines)


def ledger_append(session_id: str, entries: List[Dict[str, Any]], turn_seq: Optional[int] = None) -> int:
    """append 新東西（已在帳者：僅當 note 不同且來源非 scan 才追加一筆覆寫 note）。回傳寫入行數。
    檔案／資料夾走受保護判定（正式產出不落帳）；git 類別的建立紀錄照收，能不能刪由 artifact_status 現場判。"""
    if not session_id or not entries:
        return 0
    existing = {entry_key(r): r for r in ledger_read(session_id)}
    lines: List[str] = []
    for e in entries:
        path = str(e.get("path", "") or "")
        kind = str(e.get("kind") or "")
        if not path or (kind not in GIT_KINDS and is_protected_path(path)):   # 最後一道：受保護路徑不落帳
            continue
        rec = {"path": os.path.abspath(path)}
        rec.update({f: e[f] for f in _EXTRA_FIELDS if e.get(f)})
        if rec.get("repo"):
            rec["repo"] = os.path.abspath(str(rec["repo"]))
        k = entry_key(rec)
        prev = existing.get(k)
        if prev is not None and prev.get("decision") != "deleted":   # 刪過又重新出現＝新的一筆
            if e.get("source") in ("scan", "bash", "write") or (prev.get("note") or "") == (e.get("note") or ""):
                continue
            rec = {**prev, **rec}
        rec.update(note=str(e.get("note", "") or ""), source=str(e.get("source", "") or "manual"), at=_now_iso())
        if turn_seq is not None:
            rec["turn_seq"] = int(turn_seq)
        lines.append(json.dumps(rec, ensure_ascii=False))
        existing[k] = rec
    return _write_lines(session_id, lines)


def record_temp_write(session_id: str, file_path: str, turn_seq: Optional[int] = None) -> None:
    """PostToolUse：工具寫入 tempdir 下的檔 → 進帳（source=write）。"""
    if is_under_tempdir(file_path):
        ledger_append(session_id, [{"path": file_path, "note": "", "source": "write"}], turn_seq)


# ─── 工具呼叫 → 進帳（檔案、資料夾、git 產出物）──────────────────────────────

_SEG_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\n|\|)\s*")
_CD_WORDS = frozenset({"cd", "pushd", "set-location", "sl"})
_PUSH_SKIP = frozenset({"main", "master", "head"})
_BRANCH_LIST_FLAGS = frozenset({
    "-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy", "-l", "--list", "-a", "--all",
    "-r", "--remotes", "-v", "-vv", "--verbose", "--show-current", "--contains", "--no-contains", "--merged",
    "--no-merged", "-u", "--set-upstream-to", "--unset-upstream", "--edit-description", "--format", "--sort",
    "--points-at", "--column",
})
# 帶一個值的選項：解析位置參數時跳過它的值
_VALUE_OPTS = {
    "worktree": {"-b", "-B", "--reason"},
    "init": {"--template", "--separate-git-dir", "-b", "--initial-branch", "--object-format", "--ref-format"},
    "clone": {"-b", "--branch", "-o", "--origin", "--depth", "--reference", "-c", "--config", "--template",
              "-j", "--jobs", "--filter", "--separate-git-dir", "--shallow-since", "--shallow-exclude", "-u",
              "--upload-pack", "--bundle-uri"},
    "push": {"-o", "--push-option", "--repo", "--receive-pack", "--exec"},
}


def _tokens(seg: str) -> List[str]:
    """一段指令切詞（posix=False 保留 Windows 反斜線，再剝引號）；切不動就照空白切。"""
    try:
        toks = shlex.split(seg, posix=False)
    except ValueError:
        toks = seg.split()
    return [t.strip("\"'") for t in toks if t.strip("\"'")]


def _positionals(args: List[str], value_opts: set) -> List[str]:
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a.startswith("-"):
            skip = a in value_opts
            continue
        out.append(a)
    return out


def _git_run(repo: str, *args: str, timeout: int = 8) -> Optional[subprocess.CompletedProcess]:
    try:
        return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        return None


def _git_toplevel(d: str) -> str:
    r = _git_run(d, "rev-parse", "--show-toplevel", timeout=_VCS_TIMEOUT_S)
    return os.path.normpath(r.stdout.strip()) if r is not None and r.returncode == 0 and r.stdout.strip() else ""


def _fresh_git_dir(path: str, within_s: int = 600) -> bool:
    """path/.git 是不是剛建的（建立時間在 within_s 秒內）。拿不到建立時間的平台（Linux）一律當剛建。"""
    try:
        st = os.stat(os.path.join(path, ".git"))
    except OSError:
        return False
    born = getattr(st, "st_birthtime", None) or (st.st_ctime if os.name == "nt" else None)
    return born is None or (datetime.now().timestamp() - born) <= within_s


def _git_entries(args: List[str], cur: str, cmd: str) -> List[Dict[str, Any]]:
    """`git …` 一段（不含 git 本身）→ 這段建立的工作樹／分支／repo／遠端分支。"""
    i, repo_dir = 0, cur
    while i < len(args) and args[i].startswith("-"):
        if args[i] in ("-C", "-c") and i + 1 < len(args):
            if args[i] == "-C":
                repo_dir = _resolve(args[i + 1], repo_dir)
            i += 2
            continue
        i += 1
    if i >= len(args):
        return []
    sub, rest = args[i], args[i + 1:]
    base = {"source": "bash", "cmd": cmd[:200], "cwd": cur}
    out: List[Dict[str, Any]] = []
    branch = ""
    if sub == "worktree" and rest[:1] == ["add"]:
        opts = rest[1:]
        for flag in ("-b", "-B"):
            if flag in opts and opts.index(flag) + 1 < len(opts):
                branch = opts[opts.index(flag) + 1]
        pos = _positionals(opts, _VALUE_OPTS["worktree"])
        repo = _git_toplevel(repo_dir)
        if pos and repo:
            out.append({**base, "kind": "worktree", "path": _resolve(pos[0], repo_dir), "repo": repo})
    elif sub == "checkout" or sub == "switch":
        flags = ("-b", "-B") if sub == "checkout" else ("-c", "-C", "--create", "--force-create")
        for flag in flags:
            if flag in rest and rest.index(flag) + 1 < len(rest):
                branch = rest[rest.index(flag) + 1]
    elif sub == "branch":
        if not any(a in _BRANCH_LIST_FLAGS or a.startswith("--format=") for a in rest):
            pos = _positionals(rest, set())
            branch = pos[0] if pos else ""
    elif sub in ("init", "clone"):
        pos = _positionals(rest, _VALUE_OPTS[sub])
        if sub == "init":
            target = pos[0] if pos else "."
        elif pos:
            target = pos[1] if len(pos) > 1 else re.sub(r"\.git$", "", pos[0].rstrip("/\\").replace("\\", "/").rsplit("/", 1)[-1].rsplit(":", 1)[-1])
        else:
            target = ""
        # init 對既有 repo 是「重新初始化」：.git 不是剛建的就不收，免得把真專案列成可刪的臨時 repo（clone 目的地必為新目錄）
        if target and (sub == "clone" or _fresh_git_dir(_resolve(target, repo_dir))):
            out.append({**base, "kind": "repo", "path": _resolve(target, repo_dir)})
    elif sub == "push" and not ({"-d", "--delete", "--tags", "--mirror", "--all"} & set(rest)):
        pos = _positionals(rest, _VALUE_OPTS["push"])
        repo = _git_toplevel(repo_dir)
        for spec in pos[1:]:
            name = spec.lstrip("+").split(":")[-1].removeprefix("refs/heads/")
            if not name or spec.startswith(":") or name.lower() in _PUSH_SKIP or name.startswith("refs/"):
                continue
            if repo:
                out.append({**base, "kind": "remote_branch", "path": repo, "repo": repo, "remote": pos[0], "name": name})
    if branch:
        repo = _git_toplevel(repo_dir)
        if repo:
            out.append({**base, "kind": "branch", "path": repo, "repo": repo, "name": branch})
    return out


def parse_git_artifacts(command: str, cwd: str) -> List[Dict[str, Any]]:
    """一整條 Bash／PowerShell 指令 → git 建立的東西（跟著 `cd X &&` 換目錄；`git -C X` 只影響該段）。
    要在指令跑完之後呼叫：repo 根由 git 現場查，查不到（不是 repo）就不收。"""
    out: List[Dict[str, Any]] = []
    cur = cwd
    for seg in _SEG_SPLIT_RE.split(command or ""):
        toks = _tokens(seg)
        if not toks:
            continue
        head = toks[0].lower()
        if head in _CD_WORDS and len(toks) > 1:
            cur = _resolve(toks[-1], cur)
            continue
        if head in ("git", "git.exe"):
            out += _git_entries(toks[1:], cur, seg.strip())
    return out


def record_tool_artifacts(session_id: str, tool_name: str, tool_input: Dict[str, Any], cwd: str,
                          turn_seq: Optional[int] = None) -> int:
    """PostToolUse：這次工具呼叫建立的東西 → 進帳。Write／NotebookEdit 收寫的檔；Bash／PowerShell 收寫入目標
    （此刻存在的才收）與 git 建立的東西；Edit 只收暫存區（Edit 只改既有檔）。回傳寫入行數。"""
    entries: List[Dict[str, Any]] = []
    if tool_name in ("Write", "NotebookEdit"):
        fp = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        if fp:
            entries.append({"path": _resolve(fp, cwd), "kind": "file", "source": "write"})
    elif tool_name == "Edit":
        fp = str(tool_input.get("file_path") or "")
        if fp and is_under_tempdir(fp):
            entries.append({"path": fp, "kind": "file", "source": "write"})
    elif tool_name in ("Bash", "PowerShell"):
        from wg_core import write_paths_from_tool
        cmd = str(tool_input.get("command", "") or "")
        for t in write_paths_from_tool(tool_name, tool_input, cwd):
            if t.startswith("UNKNOWN") or not os.path.exists(t):
                continue
            entries.append({"path": t, "kind": "dir" if os.path.isdir(t) else "file", "source": "bash",
                            "cmd": cmd[:200], "cwd": cwd})
        entries += parse_git_artifacts(cmd, cwd)
    return ledger_append(session_id, entries, turn_seq)


# ─── 現場狀態：還在不在、能不能刪（給 HUD 的白話）───────────────────────────────


def _worktrees(repo: str, cache: Dict[str, Any]) -> List[Dict[str, str]]:
    """git worktree list --porcelain → [{path, branch}]（第一個是主工作樹）。"""
    ck = ("wt", _key(repo))
    if ck not in cache:
        r = _git_run(repo, "worktree", "list", "--porcelain")
        items: List[Dict[str, str]] = []
        for line in (r.stdout if r is not None and r.returncode == 0 else "").splitlines():
            if line.startswith("worktree "):
                items.append({"path": os.path.normpath(line[9:].strip()), "branch": ""})
            elif line.startswith("branch ") and items:
                items[-1]["branch"] = line[7:].strip().removeprefix("refs/heads/")
        cache[ck] = items
    return cache[ck]


def _default_branch(repo: str, cache: Dict[str, Any]) -> str:
    ck = ("default", _key(repo))
    if ck not in cache:
        cache[ck] = ""
        for cand in ("main", "master"):
            r = _git_run(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{cand}")
            if r is not None and r.returncode == 0:
                cache[ck] = cand
                break
    return cache[ck]


def _git_ignored(path: str) -> bool:
    r = _git_run(str(Path(path).parent), "check-ignore", "-q", "--", Path(path).name, timeout=_VCS_TIMEOUT_S)
    return r is not None and r.returncode == 0


def _ref_exists(repo: str, ref: str) -> bool:
    r = _git_run(repo, "show-ref", "--verify", "--quiet", ref)
    return r is not None and r.returncode == 0


def _unsafe_dir(path: str, rec: Dict[str, Any]) -> str:
    """整個資料夾刪除的保險：磁碟根、家目錄、資料根與它的上層、session 工作目錄與它的上層 → 回原因。"""
    p = _key(path)
    if os.path.dirname(p) == p:
        return "這是磁碟根目錄"
    from wg_core import CLAUDE_DIR
    for name, guard in (("家目錄", str(Path.home())), ("記憶系統資料夾", str(CLAUDE_DIR)),
                        ("這個 session 的工作目錄", str(rec.get("cwd") or ""))):
        if guard and (_key(guard) == p or _key(guard).startswith(p + os.sep)):
            return f"它是{name}或它的上層"
    return ""


def _short(path: str) -> str:
    parts = Path(path).parts
    return "/".join(parts[-2:]) if len(parts) > 1 else path


def artifact_status(rec: Dict[str, Any], cache: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """一筆帳 → {alive, kind, title, label, can_delete, confirm}。alive=False 的不列（不在了、或已進版控成正式產出）。
    label＝白話狀態；can_delete=False 時 label 說為什麼；confirm＝刪之前要再問使用者的一句話（沒有就 None）。"""
    cache = {} if cache is None else cache
    path = str(rec.get("path", "") or "")
    kind = str(rec.get("kind") or ("dir" if os.path.isdir(path) else "file"))
    out: Dict[str, Any] = {"alive": False, "kind": kind, "title": _short(path), "label": "", "can_delete": True,
                           "confirm": None}
    if kind in ("file", "dir"):
        if not os.path.exists(path) or protected_reason(path):
            return out
        if is_under_tempdir(path):
            label = "暫存區"
        elif _vcs_root_kind(path) == "git" and _git_ignored(path):
            label = "被 .gitignore 排除（不會進版控）"
        elif _vcs_root_kind(path):
            label = "還沒進版控的新資料夾" if kind == "dir" else "還沒進版控的新檔（可能是正式產出，也可能是試驗品）"
        else:
            label = "專案外"
        unsafe = _unsafe_dir(path, rec) if kind == "dir" else ""
        out.update(alive=True, label=unsafe or label, can_delete=not unsafe)
        return out
    repo = str(rec.get("repo") or "")
    if kind == "worktree":
        wts = _worktrees(repo, cache) if repo else []
        mine = next((w for w in wts[1:] if _key(w["path"]) == _key(path)), None)
        if mine is None or not os.path.isdir(path):
            return out
        r = _git_run(path, "status", "--porcelain")
        dirty = bool(r is not None and r.returncode == 0 and r.stdout.strip())
        br = f"（分支 {mine['branch']}）" if mine["branch"] else ""
        out.update(alive=True, label=("有未提交的改動" if dirty else "乾淨") + br,
                   confirm="這個工作樹有還沒提交的改動，刪掉會一起丟掉。確定要刪嗎？" if dirty else None)
        return out
    name = str(rec.get("name") or "")
    if kind == "branch":
        if not repo or not name or not _ref_exists(repo, f"refs/heads/{name}"):
            return out
        out["title"] = name
        default = _default_branch(repo, cache)
        user = next((w for w in _worktrees(repo, cache) if w["branch"] == name), None)
        if name in ("main", "master") or name == default:
            out.update(alive=True, label="主分支，不能從這裡刪", can_delete=False)
        elif user is not None:
            out.update(alive=True, label=f"工作樹 {_short(user['path'])} 正在用，先刪工作樹", can_delete=False)
        else:
            r = _git_run(repo, "rev-list", "--count", f"{default}..{name}") if default else None
            ahead = int(r.stdout.strip()) if r is not None and r.returncode == 0 and r.stdout.strip().isdigit() else -1
            if ahead == 0:
                out.update(alive=True, label="已合併")
            else:
                more = f"多 {ahead} 個 commit" if ahead > 0 else "比不出差異"
                out.update(alive=True, label=f"沒合併（{more}）",
                           confirm=f"分支 {name} 還沒合併（{more}），刪掉這些 commit 就只剩 git 的回收紀錄找得回來。確定要刪嗎？")
        return out
    if kind == "remote_branch":
        remote = str(rec.get("remote") or "")
        if not repo or not name or not remote or not _ref_exists(repo, f"refs/remotes/{remote}/{name}"):
            return out
        out.update(alive=True, title=f"{remote}/{name}", label=f"推上遠端 {remote} 的分支",
                   confirm=f"會刪掉遠端 {remote} 上的分支 {name}，其他人也就看不到了。確定要刪嗎？")
        return out
    if kind == "repo":
        if not os.path.isdir(os.path.join(path, ".git")):
            return out
        unsafe = _unsafe_dir(path, rec)
        out.update(alive=True, label=unsafe or "臨時 repo（git init／clone 出來的）", can_delete=not unsafe,
                   confirm=None if unsafe else f"會刪掉整個資料夾 {path}（含裡面所有檔案）。確定要刪嗎？")
    return out


def rec_alive(rec: Dict[str, Any]) -> bool:
    """保留期清理用：這筆帳指的東西還在嗎（不判能不能刪）。"""
    kind = str(rec.get("kind") or "")
    if kind in _REF_KINDS:
        ref = f"refs/heads/{rec.get('name')}" if kind == "branch" else f"refs/remotes/{rec.get('remote')}/{rec.get('name')}"
        repo = str(rec.get("repo") or "")
        return bool(repo) and os.path.isdir(repo) and _ref_exists(repo, ref)
    path = str(rec.get("path", "") or "")
    return bool(path) and os.path.exists(path)


# ─── 刪除與保留（HUD 按鈕 → tools/session-artifacts.py → 這裡；當場執行、結果寫回帳本）────────


def _rm_tree(path: str) -> None:
    def _retry(func, p, _exc):   # Windows 唯讀檔（git 物件）先去唯讀再刪
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=_retry)


def delete_artifact(rec: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
    """刪一筆帳指的東西 → {ok, message, needs_confirm}。要確認的東西沒帶 force 不動手、回 needs_confirm。"""
    st = artifact_status(rec)
    title = st["title"]
    if not st["alive"]:
        return {"ok": True, "message": f"{title} 已經不在了", "needs_confirm": None}
    if not st["can_delete"]:
        return {"ok": False, "message": f"{title} 不能刪：{st['label']}", "needs_confirm": None}
    if st["confirm"] and not force:
        return {"ok": False, "message": st["confirm"], "needs_confirm": st["confirm"]}
    kind, path, repo, name = st["kind"], str(rec.get("path", "")), str(rec.get("repo") or ""), str(rec.get("name") or "")
    try:
        if kind == "file":
            os.remove(path)
        elif kind in ("dir", "repo"):
            _rm_tree(path)
        else:
            args = {"worktree": ["worktree", "remove", *(["--force"] if force else []), path],
                    "branch": ["branch", "-D" if force else "-d", name],
                    "remote_branch": ["push", str(rec.get("remote") or ""), "--delete", name]}[kind]
            r = _git_run(repo, *args, timeout=60)
            if r is None or r.returncode != 0:
                err = (r.stderr or r.stdout).strip().splitlines()[-1:] if r is not None else ["git 沒有回應"]
                return {"ok": False, "message": f"{title} 刪除失敗：{err[0] if err else '未知原因'}", "needs_confirm": None}
    except OSError as e:
        return {"ok": False, "message": f"{title} 刪除失敗：{e.strerror or e}", "needs_confirm": None}
    if kind != "remote_branch" and rec_alive(rec):
        return {"ok": False, "message": f"{title} 刪了但還在，請手動檢查", "needs_confirm": None}
    return {"ok": True, "message": f"已刪除 {title}", "needs_confirm": None}


def record_decision(session_id: str, rec: Dict[str, Any], decision: str, message: str) -> int:
    """保留／刪除的結果寫回帳本（同一樣東西追加一筆，後寫者勝）。"""
    row = {**rec, "decision": decision, "decision_message": message, "decided_at": _now_iso()}
    return _write_lines(session_id, [json.dumps(row, ensure_ascii=False)])


_KIND_ORDER = {"worktree": 0, "branch": 1, "remote_branch": 2, "repo": 3, "dir": 4, "file": 5}


def list_alive(session_id: str) -> List[Dict[str, Any]]:
    """HUD 用：這個 session 帳上還在的東西（含現場狀態與上次的保留／刪除結果），依類別排序。"""
    cache: Dict[str, Any] = {}
    items: List[Dict[str, Any]] = []
    for rec in ledger_read(session_id):
        st = artifact_status(rec, cache)
        if not st["alive"]:
            continue
        items.append({
            "key": entry_key(rec), "kind": st["kind"], "title": st["title"], "path": rec.get("path", ""),
            "label": st["label"], "can_delete": st["can_delete"], "confirm": st["confirm"],
            "note": rec.get("note", ""), "source": rec.get("source", ""), "at": rec.get("at", ""),
            "decision": rec.get("decision") or None, "decision_message": rec.get("decision_message", ""),
        })
    items.sort(key=lambda x: (_KIND_ORDER.get(x["kind"], 9), str(x["at"]), x["title"]))
    return items


def act(session_id: str, key: str, action: str, force: bool = False) -> Dict[str, Any]:
    """HUD 按鈕：找帳上那一筆 → keep 記下、delete 當場刪 → 結果寫回帳本。帳上沒有的 key 一律拒絕（不刪任意路徑）。"""
    rec = next((r for r in ledger_read(session_id) if entry_key(r) == key), None)
    if rec is None:
        return {"ok": False, "message": "帳上找不到這一項（可能已經清掉了）", "needs_confirm": None}
    if action == "keep":
        record_decision(session_id, rec, "keep", "你選了保留")
        return {"ok": True, "message": f"已記下：保留 {artifact_status(rec)['title']}", "needs_confirm": None}
    if action != "delete":
        return {"ok": False, "message": f"不認得的動作：{action}", "needs_confirm": None}
    res = delete_artifact(rec, force)
    if not res["needs_confirm"]:
        record_decision(session_id, rec, "deleted" if res["ok"] else "delete_failed", res["message"])
    return res


def collect_at_completion(
    session_id: str, cwd: str, d_text: Optional[str] = None, turn_seq: Optional[int] = None,
    rejected: Optional[List[Dict[str, str]]] = None,
) -> int:
    """收尾時機（anti_evasion_report / Stop）：(i) 宣告 + scratchpad 掃描一次進帳。
    rejected（可選 out-list）收 (i) 裡被拒的受保護路徑，caller 拿去告知模型。"""
    entries: List[Dict[str, Any]] = []
    if d_text:
        entries += parse_declared_paths(d_text, cwd, rejected)
    entries += scan_scratchpad(cwd, session_id)
    return ledger_append(session_id, entries, turn_seq)
