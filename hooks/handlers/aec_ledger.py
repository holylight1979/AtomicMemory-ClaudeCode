"""aec_ledger.py — per-session 產出物帳本：這個 session 額外留下的東西（Python 唯一 writer）。

路徑固定：workflow/aec-tempfiles/<sid>.jsonl（append-only，一行一 JSON；同一樣東西後寫者勝）。
類別（kind）：file／dir（檔案、資料夾）、worktree（git 工作樹）、branch（本地分支）、
remote_branch（推上遠端的分支）、repo（git init／clone 出來的臨時 repo）。舊帳沒有 kind，當 file／dir。
進帳來源（source）：
  write  = PostToolUse Write／NotebookEdit 寫的檔；Edit 只收系統暫存區（Edit 只改既有檔，新檔已由 Write 收）
  bash   = PostToolUse Bash／PowerShell：寫入目標（wg_core.write_paths_from_tool：mkdir、轉向、cp…）
           與 git 指令（worktree add、checkout -b、switch -c、branch、init、clone、push 新分支）
  aec-i  = anti_evasion_report (i) 欄「一行一路徑」宣告（`<路徑> — <備註>`）；分支寫 `branch:<名> — <備註>`（只認帳上的分支）
  scan   = Stop／收尾時直接 listdir session scratchpad（補模型忘了列的）
  snapshot = Stop 拿開場快照（SessionStart 記的 cwd 所在 repo 工作樹與本地分支）比對多出來、帳上又沒有的（python 腳本裡
           開的工作樹等指令解析看不到的建立）；歸屬不明（共用工作樹下可能是別的 session 建的），HUD 標來源不明、不進收尾自清

帳本只記「進過帳」的東西；「還在不在、能不能刪」不記——由 artifact_status 當下查檔案系統與 git
（權威在那裡，不信模型自報）。檔案進了版控＝正式產出，自動掉出清單。不做 TTL：帳上有、還在 → HUD 一直列到被處置。
刪除由 delete_artifact 當場執行（HUD 按鈕 → Node → tools/session-artifacts.py），不經模型、不等下一則訊息。
收尾自清：Stop 的 LEFTOVER_NEEDS_CLEANUP 閘（判定在 wg_release_rules）吃 cleanup_facts 的結構化事實（只為可能成為候選的
幾筆查 git，帳再長收尾也不變慢），擋訊息由 cleanup_block_message 組。
全機殘留：list_all 掃全部帳本、依 session 分組、附 session 還開著沒有（state 檔最近更新時間）；別的開著的 session 正在用的
資料夾（工作目錄在裡面、改過或讀過裡面的檔）標正在用、刪除要再確認。
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
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import CODE_DIR, WORKFLOW_DIR

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
# (i) 分支宣告：`branch:<名> — <理由>`（冒號全形半形都收）；分支沒有路徑，名字對帳上這個 session 建的分支
_BRANCH_DECL_RE = re.compile(r"^branch\s*[:：]\s*`?([^\s`—：（(]+)`?(.*)$", re.IGNORECASE)
_NOTE_LEAD_RE = re.compile(r"^\s*(?:—+|–|-+|：|:|（|\()\s*")


def ledger_path(session_id: str) -> Path:
    return WORKFLOW_DIR / LEDGER_DIR_NAME / f"{session_id}.jsonl"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _key(p: str) -> str:
    """去重鍵：realpath + normcase（Windows 不分大小寫）。realpath 會把 8.3 短檔名（系統暫存區常是 C:\\Users\\ABCDEF~1\\…）
    展開成長檔名、git 回報的工作樹路徑也是長檔名；只用 abspath 的話同一個地方兩種寫法比不上（暫存區檔被當專案外）。"""
    try:
        return os.path.normcase(os.path.realpath(p))
    except (OSError, ValueError):
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
    受保護路徑不收，並記入 rejected（{path, reason}）供 caller 浮出訊號——靜默拒收違反可觀測性鐵律。
    `branch:<名> — <備註>` 回 {kind: branch, name, path: ''}，由 collect_at_completion 對帳上的分支（帳上沒有的拒收）。"""
    out: List[Dict[str, Any]] = []
    for line in str(d_text or "").splitlines():
        raw = _BULLET_RE.sub("", line.strip())
        if not raw or _BLANK_RE.match(raw):
            continue
        bm = _BRANCH_DECL_RE.match(raw)
        if bm:
            note = _NOTE_LEAD_RE.sub("", bm.group(2)).strip(" ）)")
            out.append({"kind": "branch", "name": bm.group(1).strip("，,;；"), "path": "", "note": note, "source": "aec-i"})
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
    """讀帳本並以 entry_key 去重（後寫者勝；created_at 帶第一次進帳的時間，刪過又出現的重算）。壞行略過。"""
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
        k = entry_key(rec)
        prev = seen.get(k)
        if prev is not None and prev.get("decision") != "deleted" and not rec.get("created_at"):
            rec["created_at"] = prev.get("created_at") or prev.get("at", "")
        seen[k] = rec
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
            if e.get("source") in ("scan", "bash", "write", "snapshot") or (prev.get("note") or "") == (e.get("note") or ""):
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


# ─── 別的 session：還開著沒有、正在用哪些資料夾（看 workflow/state-<sid>.json）─────────────────

SESSION_ACTIVE_S = 1800   # state 檔 30 分鐘內有更新＝開著（任何工具呼叫、每則訊息都會寫 state；想事情或等長任務很少超過）


def _state_snapshot(sid: str) -> Tuple[Optional[float], Dict[str, Any]]:
    """(state 檔最後更新時間, 內容)；檔不在 → (None, {})，讀壞或正在被寫 → (時間, {})。"""
    p = WORKFLOW_DIR / f"state-{sid}.json"
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return None, {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return mtime, data if isinstance(data, dict) else {}


def _ago(seconds: float) -> str:
    if seconds < 60:
        return "剛剛"
    if seconds < 3600:
        return f"{int(seconds // 60)} 分鐘前"
    if seconds < 86400:
        return f"{int(seconds // 3600)} 小時前"
    return f"{int(seconds // 86400)} 天前"


def _liveness(mtime: Optional[float], data: Dict[str, Any], now: float) -> Dict[str, str]:
    if mtime is None:
        return {"state": "closed", "label": "已關"}
    try:
        ended = datetime.fromisoformat(str(data.get("ended_at"))).timestamp() if data.get("ended_at") else None
    except ValueError:
        ended = None
    if ended is not None and mtime - ended < 120:   # SessionEnd 之後沒再寫過（恢復的 session 會再寫 state）
        return {"state": "closed", "label": "已關"}
    age = max(0.0, now - mtime)
    if age <= SESSION_ACTIVE_S:
        return {"state": "open", "label": f"開著（{_ago(age)}有動靜）"}
    return {"state": "idle", "label": f"{_ago(age)}起沒動靜（多半已關）"}


def session_liveness(sid: str, now: Optional[float] = None) -> Dict[str, str]:
    """{state: open|idle|closed, label: 白話}。open＝state 檔 30 分鐘內有更新；idle＝更久沒動靜（多半已關，判不死）；
    closed＝state 檔不在（清掉了）或收過 SessionEnd 之後沒再動。"""
    mtime, data = _state_snapshot(sid)
    return _liveness(mtime, data, time.time() if now is None else now)


def _open_session_paths(now: float) -> List[Tuple[str, str]]:
    """開著的 session 各自在用的路徑 [(sid, key)]：工作目錄、改過的檔、讀過的檔。"""
    out: set = set()
    for p in WORKFLOW_DIR.glob("state-*.json"):
        sid = p.name[len("state-"):-len(".json")]
        mtime, data = _state_snapshot(sid)
        if _liveness(mtime, data, now)["state"] != "open":
            continue
        paths = [str((data.get("session") or {}).get("cwd") or "")]
        for field in ("modified_files", "accessed_files"):
            paths += [str(m.get("path") or "") if isinstance(m, dict) else str(m) for m in (data.get(field) or [])]
        out.update((sid, _key(q)) for q in paths if q)
    return sorted(out)


def _busy(path: str, cache: Dict[str, Any]) -> str:
    """別的開著的 session 正在用這個資料夾嗎（工作目錄在裡面、或改過讀過裡面的檔）→ 白話一句；沒有回 ''。"""
    if "busy_idx" not in cache:
        cache["busy_idx"] = _open_session_paths(time.time())
    own, p = str(cache.get("sid") or ""), _key(path)
    for sid, q in cache["busy_idx"]:
        if sid != own and (q == p or q.startswith(p + os.sep)):
            return f"另一個開著的 session（{sid[:8]}）正在用"
    return ""


def artifact_status(rec: Dict[str, Any], cache: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """一筆帳 → {alive, kind, title, label, can_delete, confirm, where, merged, used_by, busy}。alive=False 的不列
    （不在了、或已進版控成正式產出）。label＝白話狀態；can_delete=False 時 label 說為什麼；confirm＝刪之前要再問使用者的
    一句話（沒有就 None）。後四個是給判定用的結構化事實（收尾自清閘不讀白話）：where＝檔案資料夾在哪（temp／ignored／
    untracked／outside）；merged＝分支併進主分支沒（判不出 None）；used_by＝用著這個分支的工作樹；busy＝別的開著的
    session 正在用（cache["sid"] 是自己，不算）。"""
    cache = {} if cache is None else cache
    path = str(rec.get("path", "") or "")
    kind = str(rec.get("kind") or ("dir" if os.path.isdir(path) else "file"))
    out: Dict[str, Any] = {"alive": False, "kind": kind, "title": _short(path), "label": "", "can_delete": True,
                           "confirm": None, "where": "", "merged": None, "used_by": "", "busy": ""}
    if kind in ("file", "dir"):
        if not os.path.exists(path) or protected_reason(path):
            return out
        if is_under_tempdir(path):
            where, label = "temp", "暫存區"
        elif _vcs_root_kind(path) == "git" and _git_ignored(path):
            where, label = "ignored", "被 .gitignore 排除（不會進版控）"
        elif _vcs_root_kind(path):
            where = "untracked"
            label = "還沒進版控的新資料夾" if kind == "dir" else "還沒進版控的新檔（可能是正式產出，也可能是試驗品）"
        else:
            where, label = "outside", "專案外"
        unsafe = _unsafe_dir(path, rec) if kind == "dir" else ""
        busy = _busy(path, cache) if kind == "dir" and not unsafe else ""
        out.update(alive=True, where=where, label=unsafe or (f"{label}；{busy}" if busy else label), can_delete=not unsafe,
                   busy=busy, confirm=f"{busy}，刪掉它那邊會出錯。確定要刪嗎？" if busy else None)
        return out
    repo = str(rec.get("repo") or "")
    if kind == "worktree":
        wts = _worktrees(repo, cache) if repo else []
        mine = next((w for w in wts[1:] if _key(w["path"]) == _key(path)), None)
        if mine is None or not os.path.isdir(path):
            return out
        r = _git_run(path, "status", "--porcelain")
        dirty = bool(r is not None and r.returncode == 0 and r.stdout.strip())
        busy = _busy(path, cache)
        br = f"（分支 {mine['branch']}）" if mine["branch"] else ""
        warn = ("這個工作樹有還沒提交的改動，刪掉會一起丟掉。" if dirty else "") + (f"{busy}，刪掉它那邊會出錯。" if busy else "")
        out.update(alive=True, label=("有未提交的改動" if dirty else "乾淨") + br + (f"；{busy}" if busy else ""), busy=busy,
                   confirm=f"{warn}確定要刪嗎？" if warn else None)
        return out
    name = str(rec.get("name") or "")
    if kind == "branch":
        if not repo or not name or not _ref_exists(repo, f"refs/heads/{name}"):
            return out
        out["title"] = name
        default = _default_branch(repo, cache)
        user = next((w for w in _worktrees(repo, cache) if w["branch"] == name), None)
        is_main = name in ("main", "master") or name == default
        ahead = -1
        if default and not is_main:
            r = _git_run(repo, "rev-list", "--count", f"{default}..{name}")
            ahead = int(r.stdout.strip()) if r is not None and r.returncode == 0 and r.stdout.strip().isdigit() else -1
        out.update(merged=None if is_main or ahead < 0 else ahead == 0, used_by=user["path"] if user else "")
        if is_main:
            out.update(alive=True, label="主分支，不能從這裡刪", can_delete=False)
        elif user is not None:
            out.update(alive=True, label=f"工作樹 {_short(user['path'])} 正在用，先刪工作樹", can_delete=False)
        elif ahead == 0:
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
        busy = "" if unsafe else _busy(path, cache)
        label = "臨時 repo（git init／clone 出來的）" + (f"；{busy}" if busy else "")
        out.update(alive=True, label=unsafe or label, can_delete=not unsafe, busy=busy,
                   confirm=None if unsafe else (f"{busy}。" if busy else "") + f"會刪掉整個資料夾 {path}（含裡面所有檔案）。確定要刪嗎？")
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


ORIGIN_SNAPSHOT = "來源不明（開場之後才出現、這個 session 沒有建立它的指令，可能是別的 session 或腳本建的）"


def list_alive(session_id: str, cache: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """HUD 與收尾自清閘用：這個 session 帳上還在的東西（含現場狀態、結構化事實、上次的保留／刪除結果），依類別排序。
    cache 可跨 session 共用（list_all：git 查詢依 repo 快取）；cache["sid"] 會設成這個 session。"""
    return _alive_items(session_id, ledger_read(session_id), cache)


def _may_be_leftover(rec: Dict[str, Any]) -> bool:
    """可能成為收尾自清候選嗎（不跑 git 的粗篩；與 wg_release_rules.leftover_candidates 同步：檔案資料夾只收「專案外」、
    遠端分支不收）。暫存區與任何版控根底下的檔案資料夾一律不是候選，判它們只需看資料夾、不必問 git。"""
    kind = str(rec.get("kind") or "")
    if kind in ("worktree", "branch", "repo"):
        return True
    if kind in _REF_KINDS:
        return False
    path = str(rec.get("path", "") or "")
    return bool(path) and os.path.exists(path) and not is_under_tempdir(path) and not _vcs_root_kind(path)


def cleanup_facts(session_id: str) -> List[Dict[str, Any]]:
    """收尾自清閘的事實：只為可能成為候選的那幾筆查現場狀態（帳再長，收尾也只為工作樹、分支、臨時 repo、專案外檔案資料夾
    跑 git），列的格式同 list_alive。"""
    return _alive_items(session_id, [r for r in ledger_read(session_id) if _may_be_leftover(r)], None)


def _alive_items(session_id: str, recs: List[Dict[str, Any]], cache: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cache = {} if cache is None else cache
    cache["sid"] = session_id
    items: List[Dict[str, Any]] = []
    for rec in recs:
        st = artifact_status(rec, cache)
        if not st["alive"]:
            continue
        items.append({
            "key": entry_key(rec), "kind": st["kind"], "title": st["title"], "path": rec.get("path", ""),
            "label": st["label"], "can_delete": st["can_delete"], "confirm": st["confirm"],
            "where": st["where"], "merged": st["merged"], "used_by": st["used_by"], "busy": st["busy"],
            "note": rec.get("note", ""), "source": rec.get("source", ""), "at": rec.get("at", ""),
            "created_at": rec.get("created_at") or rec.get("at", ""),
            "origin": ORIGIN_SNAPSHOT if rec.get("source") == "snapshot" else "",
            "decision": rec.get("decision") or None, "decision_message": rec.get("decision_message", ""),
        })
    items.sort(key=lambda x: (_KIND_ORDER.get(x["kind"], 9), str(x["created_at"]), x["title"]))
    return items


def list_all(now: Optional[float] = None) -> Dict[str, Any]:
    """全機殘留：掃全部帳本，只回還在的，依 session 分組 → {sessions: [{sid, state, label, latest, items}], total}。
    同一樣東西出現在好幾本帳：有建立紀錄的那個 session 認領（開場快照比對出來的讓出），都一樣就取先掃到的。
    組依最近進帳時間新→舊排。"""
    now = time.time() if now is None else now
    cache: Dict[str, Any] = {}
    best: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    for p in sorted((WORKFLOW_DIR / LEDGER_DIR_NAME).glob("*.jsonl")):
        if not re.match(r"^[A-Za-z0-9-]{1,80}$", p.stem):
            continue
        for it in list_alive(p.stem, cache):
            prev = best.get(it["key"])
            if prev is None or (prev[1]["source"] == "snapshot" and it["source"] != "snapshot"):
                best[it["key"]] = (p.stem, it)
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for sid, it in best.values():
        groups.setdefault(sid, []).append(it)
    sessions = []
    for sid, items in groups.items():
        items.sort(key=lambda x: (_KIND_ORDER.get(x["kind"], 9), str(x["created_at"]), x["title"]))
        sessions.append({"sid": sid, **session_liveness(sid, now),
                         "latest": max(str(x["created_at"]) for x in items), "items": items})
    sessions.sort(key=lambda s: s["latest"], reverse=True)
    return {"sessions": sessions, "total": sum(len(s["items"]) for s in sessions)}


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


def act_all_safe(session_id: str) -> Dict[str, Any]:
    """HUD 全機殘留的「整組清」：這個 session 帳上不用再確認就能刪的一次刪掉（暫存檔、專案外檔案資料夾、乾淨的工作樹、
    已合併分支…）。不動：要再確認的（沒合併、有改動、別人在用、遠端、整個 repo）、按過保留的、來源不明的（快照比對出來）。
    每一項照 act 的路徑刪（保護規則現場再判一次、結果寫回帳本）→ {ok, message, deleted, failed}。"""
    cache: Dict[str, Any] = {"sid": session_id}
    deleted, failed = 0, []
    for rec in ledger_read(session_id):
        if rec.get("decision") == "keep" or rec.get("source") == "snapshot":
            continue
        st = artifact_status(rec, cache)
        if not st["alive"] or not st["can_delete"] or st["confirm"]:
            continue
        res = act(session_id, entry_key(rec), "delete")
        if res["ok"]:
            deleted += 1
        else:
            failed.append(res["message"])
    msg = f"刪了 {deleted} 樣" + (f"；{len(failed)} 樣沒刪成：{'；'.join(failed[:3])}" if failed else "")
    return {"ok": not failed, "message": msg, "needs_confirm": None, "deleted": deleted, "failed": failed}


# ─── 開場快照：補抓指令解析看不到的工作樹與分支（python 腳本裡開的等）──────────────────


def _local_branches(repo: str) -> Optional[List[str]]:
    r = _git_run(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    if r is None or r.returncode != 0:
        return None
    return sorted(line.strip() for line in r.stdout.splitlines() if line.strip())


def git_snapshot(cwd: str) -> Optional[Dict[str, Any]]:
    """SessionStart：cwd 所在 repo 的工作樹與本地分支 → {repo, worktrees, branches, at}；不是 repo 或查不動 → None。"""
    repo = _git_toplevel(cwd) if cwd else ""
    if not repo:
        return None
    wts, branches = _worktrees(repo, {}), _local_branches(repo)
    if not wts or branches is None:
        return None
    return {"repo": repo, "worktrees": [w["path"] for w in wts], "branches": branches, "at": _now_iso()}


def snapshot_entries(snap: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """現在比開場快照多出來的工作樹與分支 → 進帳候選（source=snapshot；帳上已有建立紀錄的由 ledger_append 略過）。"""
    repo = str((snap or {}).get("repo") or "")
    if not repo or not os.path.isdir(repo):
        return []
    wts, branches = _worktrees(repo, {}), _local_branches(repo)
    if not wts or branches is None:
        return []
    had_wt = {_key(p) for p in snap.get("worktrees") or []}
    had_br = set(snap.get("branches") or [])
    out = [{"kind": "worktree", "path": w["path"], "repo": repo, "source": "snapshot"}
           for w in wts[1:] if _key(w["path"]) not in had_wt]
    out += [{"kind": "branch", "path": repo, "repo": repo, "name": b, "source": "snapshot"}
            for b in branches if b not in had_br]
    return out


def _branch_notes(session_id: str, decls: List[Dict[str, Any]],
                  rejected: Optional[List[Dict[str, str]]]) -> List[Dict[str, Any]]:
    """(i) 的 `branch:<名> — 理由` → 帳上同名分支各追加一筆備註；帳上沒有的拒收（只能替自己建的分支寫理由）。"""
    branches = [r for r in ledger_read(session_id) if r.get("kind") == "branch"]
    out: List[Dict[str, Any]] = []
    for d in decls:
        hits = [r for r in branches if r.get("name") == d["name"]]
        if not hits and rejected is not None:
            rejected.append({"path": f"branch:{d['name']}", "reason": "帳上沒有這個 session 建的這個分支（只能替自己建的分支寫理由）"})
        out += [{**{f: h[f] for f in ("kind", "path", "repo", "name") if h.get(f)}, "note": d["note"], "source": "aec-i"}
                for h in hits]
    return out


def collect_at_completion(
    session_id: str, cwd: str, d_text: Optional[str] = None, turn_seq: Optional[int] = None,
    rejected: Optional[List[Dict[str, str]]] = None, snapshot: Optional[Dict[str, Any]] = None,
) -> int:
    """收尾時機（anti_evasion_report / Stop）：(i) 宣告 + scratchpad 掃描 + 開場快照比對一次進帳。
    rejected（可選 out-list）收 (i) 裡沒收下的行（受保護路徑、帳上沒有的分支），caller 拿去告知模型。"""
    entries: List[Dict[str, Any]] = []
    if d_text:
        decl = parse_declared_paths(d_text, cwd, rejected)
        entries += [e for e in decl if e.get("path")]
        entries += _branch_notes(session_id, [e for e in decl if not e.get("path")], rejected)
    entries += scan_scratchpad(cwd, session_id)
    if snapshot:
        entries += snapshot_entries(snapshot)
    return ledger_append(session_id, entries, turn_seq)


# ─── 收尾自清閘的擋訊息（判定在 wg_release_rules.leftover_cleanup_verdict）────────────────

_KIND_WORD = {"worktree": "工作樹", "branch": "分支", "remote_branch": "遠端分支", "repo": "臨時 repo",
              "dir": "資料夾", "file": "檔案"}
CLI_PATH = (CODE_DIR / "tools" / "session-artifacts.py").as_posix()


def cleanup_block_message(session_id: str, cands: List[Dict[str, Any]], why: str) -> str:
    """LEFTOVER_NEEDS_CLEANUP 擋訊息：一項一行＋刪除指令（走 session-artifacts.py：保護規則照判、結果寫回帳本）＋怎麼寫留的理由。"""
    worktrees = {_key(c["path"]) for c in cands if c["kind"] == "worktree"}
    lines = [f"[Guardian:Cleanup] 規則 LEFTOVER_NEEDS_CLEANUP：{why}。",
             "用完的現在刪掉（照下面的指令，結果會記回帳本、HUD 同步）；要留的在收尾檢核 (i) 寫一行理由——"
             "路徑照寫 `<路徑> — <理由>`，分支寫 `branch:<名> — <理由>`。"]
    for i, c in enumerate(cands, 1):
        after = "；先刪上面的工作樹才刪得掉" if c["kind"] == "branch" and c.get("used_by") and _key(c["used_by"]) in worktrees else ""
        key = str(c["key"]).replace("'", "'\\''")
        lines.append(f"  {i}. {_KIND_WORD.get(c['kind'], c['kind'])} {c['title']}：{c['label']}{after}")
        lines.append(f"     python \"{CLI_PATH}\" act --sid {session_id} --action delete --key '{key}'")
    if any(c["kind"] == "worktree" and c.get("confirm") for c in cands):
        lines.append("有未提交改動的工作樹要加 --force 才刪得掉，改動會一起丟掉；不確定就留下、寫理由。")
    lines.append("這道每個使用者回合只擋一次。")
    return "\n".join(lines)
