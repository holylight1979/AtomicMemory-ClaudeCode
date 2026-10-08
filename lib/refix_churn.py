"""refix_churn：「同一個檔在短期內被兩筆以上 fix 類提交改到」的量尺（純函式；git／svn 都吃）。

做什麼：讀 VCS 歷史，挑出訊息像在修東西的提交（fix／bugfix／hotfix／bug／修正／修復／修好／修補／壞了／壞掉／錯誤，
詞級比對，「修改排版」「錯位動畫」不算；中文詞後面同一子句若以「嗎／？」收尾是問句也不算），按檔統計 fix 提交數
（主尺 fix_commits）與「window 天內兩筆 fix 配對數」（副尺 pairs_in_window）。修了又修的檔＝可能在修症狀，
這是預計畫 S2 的代理量、也是從零掃表的熱點來源。

邊界：
- 同一個 commit 裡同一檔只算一次（refix_same_commit_pairs=False 預設），所以配對一定是兩個不同 commit。
- 跨檔重修不算：A 修 X、B 修 Y，X 與 Y 各只有一筆 fix，都不列。
- 記憶目錄（`.claude/memory/`、根層 `memory/`、`_AIDocs/_atoms/`）、索引三檔、部位表預設排除；收割提交（knowledge harvest／[memory]／atom）預設排除。
- 日期口徑：git 用 `--date=short`、svn 取 ISO 日期前十字（UTC），兩邊都只到「日」；window 是日曆天差，不看時區與時分。
- VCS 讀不到（沒裝、不是工作副本、逾時）丟 VcsError，由呼叫端決定要停還是降級（不靜默）。

輸入來源三種：read_git(root)、read_svn(root)、parse_svn_xml(text)（svn log --xml 的輸出，供 fixture）。
"""

from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULTS: Dict[str, Any] = {
    "fix_patterns": [r"\bfix(?:e[sd]|ing)?\b", r"\bbugfix\b", r"\bhotfix\b", r"\bbug\b",
                     *(f"{w}(?![^。；;！!\n]*[嗎？?])" for w in ("修正", "修復", "修好", "修補", "壞了", "壞掉", "錯誤"))],
    "refix_window_days": 14,
    "refix_since_days": 60,
    "refix_min_fixes": 2,
    "refix_exclude": [r"(^|/)\.claude/memory/", r"^memory/", r"(^|/)_AIDocs/_atoms/", r"_ATOM_INDEX\.md$",
                      r"_atom_index\.json$", r"(^|/)MEMORY\.md$", r"(^|/)_INDEX\.md$", r"(^|/)_local_catalog\.md$",
                      r"overview-map\.md$", r"overview-hub\.json$"],
    "refix_exclude_msg": [r"knowledge harvest", r"\[memory\]", r"\batom\b"],
    "refix_same_commit_pairs": False,
}
VCS_TIMEOUT = 20
_RS, _US = chr(30), chr(31)
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class VcsError(RuntimeError):
    """VCS 讀不到：沒裝、不是工作副本、指令失敗、逾時。"""


@dataclass
class Commit:
    rev: str
    date: datetime
    msg: str
    paths: List[str] = field(default_factory=list)


def merge_cfg(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """DEFAULTS 疊上 cfg 裡有的鍵（只認 DEFAULTS 有的鍵）。"""
    out = dict(DEFAULTS)
    for k, v in (cfg or {}).items():
        if k in out and v is not None:
            out[k] = v
    return out


def _norm_path(p: str) -> str:
    return p.replace("\\", "/").strip().lstrip("/")


# ─── 讀 VCS ──────────────────────────────────────────────────────────

def detect_vcs(root: Path) -> Optional[str]:
    """root 是 svn 工作副本 → "svn"；在 git 工作樹內 → "git"；都不是 → None（不丟錯，掃表要能無 VCS 仍產）。"""
    root = Path(root)
    if (root / ".svn").is_dir():
        return "svn"
    if (root / ".git").exists():
        return "git"
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True,
                           timeout=VCS_TIMEOUT, creationflags=_NO_WINDOW)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    return "git" if r.returncode == 0 else None


def _since_date(since_days: int, now: Optional[datetime] = None) -> str:
    return ((now or datetime.now()) - timedelta(days=int(since_days))).strftime("%Y-%m-%d")


def read_git(root: Path, since_days: int = 60, now: Optional[datetime] = None) -> List[Commit]:
    cmd = ["git", "-C", str(root), "-c", "core.quotepath=off", "log", f"--since={_since_date(since_days, now)}",
           "--date=short", "--name-only",
           f"--pretty=format:{_RS}%h{_US}%ad{_US}%s"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=VCS_TIMEOUT, creationflags=_NO_WINDOW)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        raise VcsError(f"git log 失敗：{e}") from e
    if r.returncode != 0:
        raise VcsError(f"git log exit {r.returncode}：{r.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return parse_git_log(r.stdout.decode("utf-8", "replace"))


def parse_git_log(text: str) -> List[Commit]:
    """`--pretty=format:<RS>%h<US>%ad<US>%s --name-only` 的輸出 → commits（檔路徑相對 repo 根、posix）。"""
    out: List[Commit] = []
    for block in text.split(_RS):
        if not block.strip():
            continue
        head, _, files = block.partition("\n")
        parts = head.split(_US)
        if len(parts) < 3:
            continue
        rev, day, msg = parts[0].strip(), parts[1].strip(), _US.join(parts[2:])
        try:
            date = datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            continue
        out.append(Commit(rev, date, msg, [_norm_path(f) for f in files.splitlines() if f.strip()]))
    return out


def read_svn(root: Path, since_days: int = 60, now: Optional[datetime] = None) -> List[Commit]:
    cmd = ["svn", "log", "-v", "--xml", "--non-interactive", "-r", f"{{{_since_date(since_days, now)}}}:HEAD"]
    try:
        r = subprocess.run(cmd, cwd=str(root), capture_output=True, timeout=VCS_TIMEOUT * 3, creationflags=_NO_WINDOW)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        raise VcsError(f"svn log 失敗：{e}") from e
    if r.returncode != 0:
        raise VcsError(f"svn log exit {r.returncode}：{r.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return parse_svn_xml(r.stdout.decode("utf-8", "replace"))


def parse_svn_xml(text: str) -> List[Commit]:
    """`svn log -v --xml` → commits；path 只收 kind=file（舊 svn 沒 kind 屬性也收），去掉開頭的 /。"""
    try:
        tree = ET.fromstring(text)
    except ET.ParseError as e:
        raise VcsError(f"svn log xml 解析失敗：{e}") from e
    out: List[Commit] = []
    for e in tree.findall("logentry"):
        day = (e.findtext("date") or "")[:10]
        try:
            date = datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            continue
        paths = [_norm_path(p.text or "") for p in e.findall("./paths/path") if p.get("kind") in ("file", None)]
        out.append(Commit(e.get("revision", ""), date, e.findtext("msg") or "", [p for p in paths if p]))
    return out


def read_commits(root: Path, vcs: Optional[str], since_days: int = 60, now: Optional[datetime] = None) -> List[Commit]:
    """vcs 為 None → []（無 VCS 仍能往下算，結果就是零熱點）。"""
    if vcs == "git":
        return read_git(root, since_days, now)
    if vcs == "svn":
        return read_svn(root, since_days, now)
    return []


# ─── 判定與排名 ──────────────────────────────────────────────────────

def _compile(patterns: Any) -> List[re.Pattern]:
    if isinstance(patterns, str):
        patterns = [patterns]
    return [re.compile(p, re.I) for p in (patterns or []) if p]


def is_fix(msg: str, patterns: Any = None) -> bool:
    """訊息任一行命中任一 fix 樣式（不分大小寫）。"""
    return any(p.search(msg or "") for p in _compile(DEFAULTS["fix_patterns"] if patterns is None else patterns))


def rank_refixed(commits: List[Commit], cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """→ {commits, fix_commits, files_touched_by_fix, files_refixed, files: [ {file, fix_commits, pairs_in_window,
    revs, first_lines} … ]}；files 依主尺 fix_commits 降冪、副尺 pairs_in_window 降冪、再檔名。"""
    c = merge_cfg(cfg)
    fix_re, ex_path, ex_msg = _compile(c["fix_patterns"]), _compile(c["refix_exclude"]), _compile(c["refix_exclude_msg"])
    window = timedelta(days=int(c["refix_window_days"]))
    min_fixes = int(c["refix_min_fixes"])
    same_commit_pairs = bool(c["refix_same_commit_pairs"])

    fixes = 0
    by_file: Dict[str, List[tuple]] = {}
    for cm in commits:
        if not any(p.search(cm.msg) for p in fix_re) or any(p.search(cm.msg) for p in ex_msg):
            continue
        fixes += 1
        first = (cm.msg.strip().splitlines() or [""])[0][:80]
        seen: set = set()
        for path in cm.paths:
            if any(p.search(path) for p in ex_path):
                continue
            if not same_commit_pairs:
                if path in seen:
                    continue
                seen.add(path)
            by_file.setdefault(path, []).append((cm.date, cm.rev, first))

    files: List[Dict[str, Any]] = []
    for path, hits in by_file.items():
        if len(hits) < min_fixes:
            continue
        hits.sort(key=lambda h: (h[0], h[1]))
        pairs = sum(1 for i, a in enumerate(hits) for b in hits[i + 1:] if b[0] - a[0] <= window)
        files.append({"file": path, "fix_commits": len(hits), "pairs_in_window": pairs,
                      "revs": [h[1] for h in hits], "first_lines": sorted({h[2] for h in hits})})
    files.sort(key=lambda d: (-d["fix_commits"], -d["pairs_in_window"], d["file"]))
    return {"commits": len(commits), "fix_commits": fixes, "files_touched_by_fix": len(by_file),
            "files_refixed": len(files), "files": files}


def top_dir_of(path: str, top_dirs: Optional[List[str]] = None) -> str:
    """檔路徑的頂層目錄。git 路徑取第一段；svn 路徑是 repo 絕對路徑（trunk/src/…），給 top_dirs 時取
    第一個落在 top_dirs 裡的段（大小寫不分）。都對不上回 ""。"""
    segs = [s for s in _norm_path(path).split("/") if s]
    if len(segs) < 2:
        return ""
    if not top_dirs:
        return segs[0]
    wanted = {d.lower(): d for d in top_dirs}
    for s in segs[:-1]:
        if s.lower() in wanted:
            return wanted[s.lower()]
    return ""


def hotspots_by_dir(ranked: Dict[str, Any], top_dirs: Optional[List[str]] = None) -> Dict[str, int]:
    """rank_refixed 的結果 → {頂層目錄: 該目錄下被重修檔的 fix_commits 總和}（只含 >0 的）。"""
    out: Dict[str, int] = {}
    for f in ranked.get("files") or []:
        d = top_dir_of(f["file"], top_dirs)
        if d:
            out[d] = out.get(d, 0) + int(f["fix_commits"])
    return out
