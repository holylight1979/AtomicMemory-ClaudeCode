"""aec_ledger.py — per-session 殘檔帳本（Python 唯一 writer；Node HUD 唯讀 + exists() 過濾）。

路徑固定：workflow/aec-tempfiles/<sid>.jsonl（append-only，一行一 JSON）。
進帳來源（source）：
  write  = PostToolUse Write/Edit/NotebookEdit 落在系統 tempdir 下的檔（scratchpad 等）
  aec-d  = anti_evasion_report (d) 欄「一行一路徑」宣告（`<路徑> — <備註>`）
  scan   = Stop / 收尾時直接 listdir session scratchpad（補模型忘了列的）

帳本只記「進過帳」的路徑；「還在不在」不記——由讀端當下 exists() 判定（檔案系統才是權威，
不信模型自報）。不做 TTL：殘檔正解是完工即刪；帳本裡有、磁碟上還在 → HUD 一直列到被處置。
fail-open：任何 I/O 例外都吞掉，不阻斷 hook。
"""
from __future__ import annotations

import glob as _glob
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from wg_core import WORKFLOW_DIR

LEDGER_DIR_NAME = "aec-tempfiles"

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
    if not os.path.isabs(s) and cwd:
        s = os.path.join(cwd, s)
    return s


def parse_d_paths(d_text: str, cwd: str) -> List[Dict[str, Any]]:
    """(d) 每非空行 → `<路徑> — <備註>`；路徑取分隔符前第一個 token。
    只收「磁碟上此刻存在」的（含 glob 展開）；prose 行 / 已刪的 → 略過（已刪的沒有裁決價值）。"""
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
                if os.path.exists(c):
                    out.append({"path": os.path.abspath(c), "note": note, "source": "aec-d"})
            except Exception:
                continue
    return out


# ─── 帳本 I/O ─────────────────────────────────────────────────────────────────


def ledger_read(session_id: str) -> List[Dict[str, Any]]:
    """讀帳本並以 _key 去重（後寫者勝）。壞行略過。"""
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
        path = str(rec.get("path", "") or "")
        if not path:
            continue
        seen[_key(path)] = rec
    return list(seen.values())


def ledger_append(session_id: str, entries: List[Dict[str, Any]], turn_seq: Optional[int] = None) -> int:
    """append 新路徑（已在帳者：僅當 note 不同且來源非 scan 才追加一筆覆寫 note）。回傳寫入行數。"""
    if not session_id or not entries:
        return 0
    existing = {_key(r["path"]): r for r in ledger_read(session_id)}
    lines: List[str] = []
    for e in entries:
        path = str(e.get("path", "") or "")
        if not path:
            continue
        k = _key(path)
        prev = existing.get(k)
        if prev is not None:
            if e.get("source") == "scan" or (prev.get("note") or "") == (e.get("note") or ""):
                continue
        rec = {
            "path": os.path.abspath(path),
            "note": str(e.get("note", "") or ""),
            "source": str(e.get("source", "") or "manual"),
            "at": _now_iso(),
        }
        if turn_seq is not None:
            rec["turn_seq"] = int(turn_seq)
        lines.append(json.dumps(rec, ensure_ascii=False))
        existing[k] = rec
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


def record_temp_write(session_id: str, file_path: str, turn_seq: Optional[int] = None) -> None:
    """PostToolUse：工具寫入 tempdir 下的檔 → 進帳（source=write）。"""
    if is_under_tempdir(file_path):
        ledger_append(session_id, [{"path": file_path, "note": "", "source": "write"}], turn_seq)


def collect_at_completion(
    session_id: str, cwd: str, d_text: Optional[str] = None, turn_seq: Optional[int] = None
) -> int:
    """收尾時機（anti_evasion_report / Stop）：(d) 宣告 + scratchpad 掃描一次進帳。"""
    entries: List[Dict[str, Any]] = []
    if d_text:
        entries += parse_d_paths(d_text, cwd)
    entries += scan_scratchpad(cwd, session_id)
    return ledger_append(session_id, entries, turn_seq)
