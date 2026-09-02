"""aec_ledger.py — per-session 殘檔帳本（Python 唯一 writer；Node HUD 唯讀 + exists() 過濾）。

路徑固定：workflow/aec-tempfiles/<sid>.jsonl（append-only，一行一 JSON）。
進帳來源（source）：
  write  = PostToolUse Write/Edit/NotebookEdit 落在系統 tempdir 下的檔（scratchpad 等）
  aec-i  = anti_evasion_report (i) 欄「一行一路徑」宣告（`<路徑> — <備註>`；
           2026-09 前為 (d) 欄，舊帳 source=aec-d 僅顯示差異、判定不變）
  scan   = Stop / 收尾時直接 listdir session scratchpad（補模型忘了列的）

帳本只記「進過帳」的路徑；「還在不在」不記——由讀端當下 exists() 判定（檔案系統才是權威，
不信模型自報）。不做 TTL：殘檔正解是完工即刪；帳本裡有、磁碟上還在 → HUD 一直列到被處置。
fail-open：任何 I/O 例外都吞掉，不阻斷 hook。

受保護路徑（is_protected_path）一律拒收，不論來源：VCS 已追蹤的檔、memory/ 與 _AIDocs/ 之下、
索引／CHANGELOG／核心設定 md。理由：帳本裡的每一列在 HUD 都配「刪除」鈕，正式產出（改了還沒
commit 的 code/doc/atom/索引）不是「衍生暫存」，模型錯報進 (d) 也不能變成可一鍵刪的候選。
"""
from __future__ import annotations

import glob as _glob
import json
import os
import re
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
        r = subprocess.run(cmd, capture_output=True, timeout=_VCS_TIMEOUT_S)
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
        if not path or is_protected_path(path):   # 最後一道：不論來源，受保護路徑不落帳
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
