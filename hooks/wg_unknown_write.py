"""wg_unknown_write.py — 判不出寫入目標的 Bash／PowerShell 指令跑完後，從檔案系統補出它真的改了哪些檔（規則 UNKNOWN_WRITE_RECOVERED）。

做什麼：write_paths_from_tool 算不出寫入目標（`python -c`、heredoc 餵給直譯器、變數路徑…）時，PostToolUse／PostToolUseFailure
呼叫 recover()：
  1. 候選檔＝版控狀態列出的改動檔（git status --porcelain／svn status --xml，整棵查，有時間上限）；
     整棵查逾時 → 改查指令文字裡點名、真的存在的檔（帶路徑的 status，萬檔 repo 也快），同 session 之後這個根直接走點名。
  2. 只留「指令開始之後才寫過」的檔（mtime ≥ 開始時間 − MTIME_SLACK_S）：快照前就髒、這次沒動的檔 mtime 早於開始時間，不算；
     版控說跟基準相同的檔（改了又改回、原樣重寫）status 列不出來，也不算。
不在 git／svn 工作區、找不到指令開始時間、查詢失敗 → 不補，回原因（呼叫端記進那一筆 unknown_writes）。
怎麼跑：不單獨跑；案例 hooks/verify/verify_unknown_write_recover.py。
"""
from __future__ import annotations

import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from wg_core import find_vcs_root

VIA = "vcs_status"           # modified_files 的來源欄：從版控狀態補算
MTIME_SLACK_S = 2.0          # 開始時間往前放寬：檔案系統時間粒度（FAT 2 秒）與 transcript 時戳的誤差
FUTURE_SLACK_S = 2.0         # mtime 晚於「現在」超過這麼多不算（未來時間不是這條指令寫的）
FULL_TIMEOUT_S = 1.2         # 整棵 status 上限：2.7 千檔 git 約 0.14 秒、1.3 萬檔 svn 約 0.5～0.9 秒；138 萬檔的 svn 要一分鐘以上
NAMED_TIMEOUT_S = 0.8        # 只查點名的檔：萬檔 svn 查 3 個檔約 0.1～0.2 秒
NAMED_CAP = 200              # 指令文字裡最多拿幾個字樣去試是不是檔
UNVERSIONED_DIR_CAP = 500    # svn 未納管的目錄整個列成一筆，往下展開最多看幾個檔
CHANGED_CAP = 5000           # 版控列出的改動檔最多逐一看幾個 mtime（每個一次 stat，約 20～40 微秒）
_SVN_CHANGED = {"modified", "added", "replaced", "unversioned", "conflicted"}
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_QUOTED_RES = (re.compile(r"'([^'\n]{1,260})'"), re.compile(r'"([^"\n]{1,260})"'))   # 兩種引號分開找：外層 "…" 不吃掉裡面的 '…'
_BARE_RE = re.compile(r"[^\s'\"<>|;&()=,\[\]{}]{1,260}")
# 只吃同一行的空白（[ \t]）：\s 跨換行時，一長串換行在每個起點都要整串回溯，萬行指令要好幾秒
_CD_RE = re.compile(r"(?:^|[;&|(])[ \t]*(?:cd|pushd|chdir|set-location|sl)[ \t]+(?:-\w+[ \t]+)*"
                    r"('[^'\n]+'|\"[^\"\n]+\"|[^\s;&|)]+)", re.IGNORECASE | re.MULTILINE)
_MSYS_RE = re.compile(r"^/([A-Za-z])/(.*)$")


def _abs(tok: str, base: str) -> str:
    """字樣 → 絕對路徑：MSYS `/c/x` 轉 `C:/x`、`~` 展開，相對的照 base 補。"""
    tok = tok.strip().strip("'\"")
    m = _MSYS_RE.match(tok)
    if m:
        tok = f"{m.group(1).upper()}:/{m.group(2)}"
    if tok.startswith("~"):
        tok = os.path.expanduser(tok)
    return os.path.normpath(tok if os.path.isabs(tok) or re.match(r"^[A-Za-z]:[\\/]", tok) else os.path.join(base, tok))


def work_dirs(command: str, cwd: str) -> List[str]:
    """指令可能在哪些目錄寫：hook 給的 cwd，加上指令裡 cd 過去、真的存在的目錄（依序以前一個為基準；含變數的跳過）。"""
    out = [os.path.normpath(cwd)] if cwd else []
    base = cwd
    for m in _CD_RE.finditer(command or ""):
        tok = m.group(1)
        if not base or any(c in tok for c in "$`%") or tok.strip("'\"") == "-":
            continue
        d = _abs(tok, base)
        if os.path.isdir(d):
            base = d
            if all(os.path.normcase(d) != os.path.normcase(x) for x in out):
                out.append(d)
    return out


def named_files(command: str, dirs: Sequence[str]) -> List[str]:
    """指令文字裡點名、真的存在的檔：引號裡的字串與裸字樣，像路徑（含 . 或斜線）的照每個工作目錄試一次。"""
    toks: Dict[str, None] = {}                     # 保序去重
    for rx in (*_QUOTED_RES, _BARE_RE):
        for m in rx.finditer(command or ""):
            if len(toks) >= NAMED_CAP:
                break
            t = (m.group(1) if m.groups() else m.group(0)).strip()
            if t and t not in toks and ("." in t or "/" in t or "\\" in t) and not t.startswith("-") and "://" not in t \
                    and not any(c in t for c in "$`%*?\n"):
                toks[t] = None
    out: List[str] = []
    seen = set()
    for t in toks:
        for d in dirs or [""]:
            try:
                p = _abs(t, d)
                if os.path.normcase(p) not in seen and os.path.isfile(p):
                    seen.add(os.path.normcase(p))
                    out.append(p)
            except (OSError, ValueError):
                continue
    return out


def _under(path: str, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _git_changed(root: Path, paths: Sequence[str], timeout: float, run: Callable[..., Any]) -> List[str]:
    """git status 列出的改動檔（含未追蹤；改名取新路徑）：絕對路徑。查不到丟例外（逾時是 subprocess.TimeoutExpired）。"""
    r = run(["git", "--no-optional-locks", "-C", str(root), "status", "--porcelain=v1", "-z", "--untracked-files=all",
             "--", *paths], capture_output=True, timeout=timeout, creationflags=_NO_WINDOW)
    if r.returncode:
        raise RuntimeError(f"git status 失敗：{(r.stderr or b'').decode('utf-8', 'replace').strip()[:200]}")
    entries = (r.stdout or b"").decode("utf-8", "replace").split("\0")
    out, i = [], 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        if e[0] in "RC" or e[1] in "RC":
            i += 1                     # -z 的改名／複製（X 或 Y 欄）後面多一筆原路徑
        out.append(os.path.normpath(os.path.join(str(root), e[3:])))
    return out


def _svn_changed(root: Path, paths: Sequence[str], timeout: float, run: Callable[..., Any],
                 deadline: float, clock: Callable[[], float], whys: List[str]) -> List[str]:
    """svn status --xml 列出的改動檔（改、加、取代、衝突、未納管）：絕對路徑。未納管的目錄整個列成一筆，往下展開
    （全部合計最多 UNVERSIONED_DIR_CAP 個檔、不過 deadline；展開不完寫進 whys）；其他狀態的目錄底下的改動 svn 會逐筆列，不展開。
    查不到丟例外。"""
    r = run(["svn", "status", "--xml", *(paths or ["."])], cwd=str(root), capture_output=True, timeout=timeout,
            creationflags=_NO_WINDOW)
    if r.returncode:
        raise RuntimeError(f"svn status 失敗：{(r.stderr or b'').decode('utf-8', 'replace').strip()[:200]}")
    out: List[str] = []
    walked = 0
    for entry in ET.fromstring(r.stdout or b"<status/>").iter("entry"):
        st = entry.find("wc-status")
        item = st.get("item") if st is not None else None
        if item not in _SVN_CHANGED:
            continue
        p = os.path.normpath(os.path.join(str(root), entry.get("path") or ""))
        if not os.path.isdir(p):
            out.append(p)
            continue
        if item != "unversioned":
            continue
        for d, ds, fs in os.walk(p):
            ds[:] = [x for x in ds if x != ".svn"]
            for f in fs:
                if walked >= UNVERSIONED_DIR_CAP or clock() > deadline:
                    whys.append(f"svn 未納管目錄展開到 {walked} 個檔就停（上限或時間到），其餘沒看")
                    return out
                out.append(os.path.join(d, f))
                walked += 1
    return out


def recover(command: str, cwd: str, started: Optional[float], slow_roots: Sequence[str] = (),
            run: Optional[Callable[..., Any]] = None, clock: Callable[[], float] = time.monotonic
            ) -> Tuple[List[str], Dict[str, Any]]:
    """規則 UNKNOWN_WRITE_RECOVERED：回 (這條指令開始後寫過、版控說有改動的檔, 帳)。
    帳：roots＝查了哪些版控根、named＝指令點名的檔數、slow＝這次整棵查逾時的根（呼叫端記住，同 session 之後直接走點名）、
    lag_ms＝補到的檔 mtime 比開始時間晚幾毫秒（最小的 10 個；負的＝落在往前放寬的那段）、why＝補不到或只補到一部分的原因、
    ms＝耗時。slow_roots 裡的根不整棵查。
    run 沒給＝呼叫當下的 subprocess.run（不在定義時綁住：測試的 git 錄製重播換掉它時才攔得到）。"""
    run = run or subprocess.run
    t0 = clock()
    note: Dict[str, Any] = {"roots": [], "named": 0, "slow": [], "lag_ms": [], "why": ""}

    def done(paths: List[str], why: str = "") -> Tuple[List[str], Dict[str, Any]]:
        note["why"] = why
        note["ms"] = int((clock() - t0) * 1000)
        return paths, note

    if started is None:
        return done([], "找不到這次指令的開始時間，分不出哪些檔是它寫的")
    dirs = work_dirs(command, cwd)
    roots: List[Tuple[str, Path]] = []
    for d in dirs:
        hit = find_vcs_root(Path(d))
        if hit and all(os.path.normcase(str(hit[1])) != os.path.normcase(str(r)) for _, r in roots):
            roots.append(hit)
        if len(roots) >= 2:
            break
    note["roots"] = [str(r).replace("\\", "/") for _, r in roots]
    if not roots:
        return done([], "指令的工作目錄不在 git／svn 工作區，補不到")
    named = named_files(command, dirs)
    note["named"] = len(named)
    deadline = t0 + FULL_TIMEOUT_S
    named_deadline: Optional[float] = None       # 點名查詢幾個根合用一份 NAMED_TIMEOUT_S，從第一次點名查詢起算
    out: List[str] = []
    seen = set()
    whys: List[str] = []
    for kind, root in roots:
        key = str(root).replace("\\", "/").lower()
        mine = [p for p in named if _under(p, root)]
        changed: Optional[List[str]] = None
        if key in slow_roots:
            whys.append(f"{kind} 根之前整棵查逾時，只查指令點名的檔")
        elif clock() >= deadline:
            whys.append(f"{kind} 整棵查的時間預算已用完，只查指令點名的檔")
        else:
            try:
                changed = (_git_changed(root, [], deadline - clock(), run) if kind == "git"
                           else _svn_changed(root, [], deadline - clock(), run, deadline, clock, whys))
            except subprocess.TimeoutExpired:
                note["slow"].append(key)
                whys.append(f"{kind} 整棵查超過 {FULL_TIMEOUT_S} 秒，只查指令點名的檔")
            except (OSError, RuntimeError, ET.ParseError) as e:
                whys.append(f"{kind} status 查不到（{type(e).__name__}: {str(e)[:120]}）")
        if changed is None and mine:
            named_deadline = named_deadline or clock() + NAMED_TIMEOUT_S
            left = named_deadline - clock()
            try:
                if left <= 0:
                    raise subprocess.TimeoutExpired("status", 0)
                changed = (_git_changed(root, mine, left, run) if kind == "git"
                           else _svn_changed(root, mine, left, run, named_deadline, clock, whys))
            except (subprocess.TimeoutExpired, OSError, RuntimeError, ET.ParseError) as e:
                whys.append(f"{kind} 點名查詢也查不到（{type(e).__name__}）")
        elif changed is None:
            whys.append(f"指令沒有點名 {key} 底下的檔，補不到")
        changed = changed or []
        if len(changed) > CHANGED_CAP:
            whys.append(f"{kind} 列出 {len(changed)} 個改動檔，只看前 {CHANGED_CAP} 個")
        latest = time.time() + FUTURE_SLACK_S       # 未來時間的 mtime（時鐘被調過、解壓保留的時間）不是這條指令寫的
        for p in changed[:CHANGED_CAP]:
            try:
                mt = os.path.getmtime(p) if os.path.normcase(p) not in seen and os.path.isfile(p) else None
                if mt is not None and started - MTIME_SLACK_S <= mt <= latest:
                    seen.add(os.path.normcase(p))
                    out.append(p)
                    note["lag_ms"].append(int((mt - started) * 1000))
            except OSError:
                continue
    note["lag_ms"] = sorted(note["lag_ms"])[:10]
    return done(out, "；".join(whys))
