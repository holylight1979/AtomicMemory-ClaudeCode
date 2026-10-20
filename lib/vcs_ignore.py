"""vcs_ignore.py — 專案記憶庫的衍生檔退出版控：ignore 自動設定＋已版控偵測。

做什麼：
  專案記憶庫（{proj}/.claude/memory）的 _atom_index.json／_ATOM_INDEX.md 是純衍生索引（每筆全來自
  atom 檔頭，SessionStart 缺檔即從 .md 重建），_staging／episodic／vector-db 是本機暫存。這些東西入版控
  只會讓多人 update 互衝（SVN 沒有 client merge driver，git 那套合併驅動搆不到）。本模組：
    - ensure_ignore(mem)：svn 工作副本 → `svn propset svn:ignore`（併入既有值，不覆蓋）；git repo →
      {mem}/.gitignore 補缺的行。記憶庫目錄本身尚未版控（svn）→ 跳過，下次再試。
    - tracked_derived(mem)：這些衍生檔「已被版控」的清單（svn status／git ls-files）。
    - advisory_lines(mem, marker)：SessionStart 用的總成——設 ignore、偵測已版控、每個記憶庫每種 VCS
      只處理一次（marker 檔記錄），告警附確切退出指令，絕不自動執行 svn rm／git rm。
  svn:ignore／.gitignore 對「已經在版控裡」的檔無效，所以偵測與告警是必要的另一半。

怎麼跑：由 hooks/handlers/session_start.py 與 lib/atom_index_json.save_atom_index_json（索引首次落檔）呼叫。
  手動檢視：python -m lib.vcs_ignore <memory-dir>   （唯讀報告：VCS 根、既有 ignore、已版控衍生檔）
  svn 只用 --xml 輸出（UTF-8；純文字輸出走 cp950，非 ASCII 路徑會壞）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DERIVED_FILES = ("_atom_index.json", "_ATOM_INDEX.md")
DERIVED_DIRS = ("_staging", "episodic", "vector-db")
DERIVED_ENTRIES = DERIVED_FILES + DERIVED_DIRS

REBUILD_HINT = 'python ~/.claude/tools/sync-atom-index.py --rebuild --memory-dir "{mem}"'
_OLD_VERSION_HINT = ("舊版（2026-09-23 前）無缺檔自動重建，索引不見時手動：" + REBUILD_HINT)

try:
    from .project_root import claude_data_dir
except ImportError:  # 頂層模組載入（hooks 把 lib/ 放上 sys.path）
    from project_root import claude_data_dir

_CLAUDE_DIR = claude_data_dir()   # 使用者資料根（WG_CLAUDE_DIR 或 ~/.claude），和 hooks 同一支算法
_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}
# svn status item 值裡「仍在版控中」的那些；deleted（已排程刪除）、unversioned、ignored、external、none 不算
_SVN_TRACKED_ITEMS = frozenset({
    "normal", "modified", "added", "replaced", "conflicted", "merged", "missing", "incomplete", "obstructed",
})
_SVN_NOT_FOUND_WARN = "W200017"  # propget：屬性不存在（rc 1 但不是錯）


# ─── 純檔案系統判定（零子行程）────────────────────────────────────────────────

def under_claude_dir(mem_dir: Path) -> bool:
    """~/.claude 自己的記憶（全域層／舊式 projects/<slug>/memory）不在本模組範圍：根層 repo 自有規則。"""
    try:
        Path(mem_dir).resolve().relative_to(_CLAUDE_DIR.resolve())
        return True
    except (OSError, ValueError):
        return False


def _walk_up(start: Path, marker: str) -> Optional[Path]:
    cur = Path(start)
    while True:
        try:
            if (cur / marker).exists():
                return cur
        except OSError:
            return None
        if cur.parent == cur:
            return None
        cur = cur.parent


def vcs_roots(mem_dir: Path) -> List[Tuple[str, Path]]:
    """往上找 .svn 與 .git 兩種根；同層雙版控（git 疊在 svn 上）兩個都回，svn 在前。"""
    out: List[Tuple[str, Path]] = []
    svn = _walk_up(mem_dir, ".svn")
    if svn is not None and (svn / ".svn").is_dir():
        out.append(("svn", svn))
    git = _walk_up(mem_dir, ".git")
    if git is not None:
        out.append(("git", git))
    return out


def _run(args: List[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, **_NO_WINDOW)


def _new_report(vcs: str, root: Path) -> Dict:
    return {"vcs": vcs, "root": str(root), "added": [], "already": [], "skipped": None, "error": None}


# ─── svn ─────────────────────────────────────────────────────────────────────

def _svn_versioned(path: Path, timeout: float) -> Optional[bool]:
    """None＝svn CLI 不在；False＝路徑不在版控（info rc≠0）。"""
    try:
        r = _run(["svn", "--non-interactive", "info", "--xml", "--", str(path)], path.parent, timeout)
    except FileNotFoundError:
        return None
    return r.returncode == 0


def _svn_ignore_value(mem_dir: Path, timeout: float) -> List[str]:
    """既有 svn:ignore 的每一行。屬性不存在＝空清單；其他失敗 raise（否則 propset 會把既有值蓋掉）。"""
    r = _run(["svn", "--non-interactive", "propget", "svn:ignore", "--xml", "--", str(mem_dir)], mem_dir, timeout)
    if r.returncode and _SVN_NOT_FOUND_WARN not in (r.stderr or ""):
        raise RuntimeError(_tail(r))
    try:
        root = ET.fromstring(r.stdout or "")
    except ET.ParseError:
        if r.returncode:
            return []
        raise RuntimeError("svn propget 輸出不是 XML")
    prop = root.find(".//property[@name='svn:ignore']")
    if prop is None or not prop.text:
        return []
    return [ln.strip() for ln in prop.text.splitlines() if ln.strip()]


def _tail(r: subprocess.CompletedProcess) -> str:
    lines = [ln for ln in ((r.stderr or "") + "\n" + (r.stdout or "")).splitlines() if ln.strip()]
    return (lines[-1] if lines else f"rc={r.returncode}")[:200]


def _svn_ensure(mem_dir: Path, root: Path, timeout: float) -> Dict:
    rep = _new_report("svn", root)
    versioned = _svn_versioned(mem_dir, timeout)
    if versioned is None:
        rep["skipped"], rep["error"] = "no-cli", "svn CLI 不在 PATH"
        return rep
    if not versioned:
        rep["skipped"] = "unversioned"   # 記憶庫目錄還沒 svn add：propset 無處可設，下次再試
        return rep
    try:
        existing = _svn_ignore_value(mem_dir, timeout)
    except RuntimeError as e:
        rep["error"] = f"svn propget 失敗：{e}"
        return rep
    rep["already"] = [e for e in DERIVED_ENTRIES if e in existing]
    missing = [e for e in DERIVED_ENTRIES if e not in existing]
    if not missing:
        return rep
    value = "\n".join(existing + missing) + "\n"
    fd, tmp = tempfile.mkstemp(prefix="svn-ignore-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(value)
        r = _run(["svn", "--non-interactive", "propset", "svn:ignore", "-F", tmp, "--", str(mem_dir)],
                 mem_dir, timeout)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    if r.returncode:
        rep["error"] = f"svn propset 失敗：{_tail(r)}"
        return rep
    rep["added"] = missing
    return rep


def _svn_tracked(mem_dir: Path, timeout: float) -> Dict[str, str]:
    """{衍生檔名: svn status item}，只列仍在版控者。--depth empty：目錄只看自己、不列子項。"""
    targets = [mem_dir / n for n in DERIVED_ENTRIES if (mem_dir / n).exists()]
    if not targets:
        return {}
    r = _run(["svn", "--non-interactive", "status", "-v", "--xml", "--depth", "empty", "--",
              *map(str, targets)], mem_dir, timeout)
    if not (r.stdout or "").strip():
        return {}
    try:
        root = ET.fromstring(r.stdout)
    except ET.ParseError:
        return {}
    out: Dict[str, str] = {}
    for target in root.iter("target"):
        name = Path(target.get("path", "")).name
        ws = target.find("entry/wc-status")
        if ws is None or name not in DERIVED_ENTRIES:
            continue
        item = ws.get("item", "")
        if item in _SVN_TRACKED_ITEMS:
            out[name] = item
    return out


# ─── git ─────────────────────────────────────────────────────────────────────

def _git(args: List[str], cwd: Path, timeout: float) -> Optional[subprocess.CompletedProcess]:
    try:
        return _run(["git", *args], cwd, timeout)
    except FileNotFoundError:
        return None


def _git_ensure(mem_dir: Path, root: Path, timeout: float) -> Dict:
    rep = _new_report("git", root)
    r = _git(["rev-parse", "--show-toplevel"], mem_dir, timeout)
    if r is None:
        rep["skipped"], rep["error"] = "no-cli", "git CLI 不在 PATH"
        return rep
    if r.returncode:
        rep["skipped"] = "not-a-repo"   # 只有一個假 .git 目錄（測試樹）或壞掉的 repo：不動
        return rep
    chk = _git(["check-ignore", "-q", "--", str(mem_dir)], mem_dir, timeout)
    if chk is not None and chk.returncode == 0:
        rep["skipped"] = "dir-ignored"  # 整個 .claude/ 被上層 .gitignore 排除：寫了也沒意義
        return rep
    gi = mem_dir / ".gitignore"
    existing_lines: List[str] = []
    if gi.exists():
        try:
            existing_lines = gi.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeDecodeError) as e:
            rep["error"] = f".gitignore 讀取失敗：{e}"
            return rep
    present = {ln.strip().strip("/") for ln in existing_lines if ln.strip() and not ln.lstrip().startswith("#")}
    wanted = list(DERIVED_FILES) + [d + "/" for d in DERIVED_DIRS]
    rep["already"] = [w.rstrip("/") for w in wanted if w.rstrip("/") in present]
    missing = [w for w in wanted if w.rstrip("/") not in present]
    if not missing:
        return rep
    body = "\n".join(existing_lines).rstrip("\n")
    text = (body + "\n" if body else "") + "\n".join(missing) + "\n"
    try:
        gi.write_text(text, encoding="utf-8", newline="\n")
    except OSError as e:
        rep["error"] = f".gitignore 寫入失敗：{e}"
        return rep
    rep["added"] = [w.rstrip("/") for w in missing]
    return rep


def _git_tracked(mem_dir: Path, timeout: float) -> Dict[str, str]:
    r = _git(["ls-files", "-z", "--", *DERIVED_ENTRIES], mem_dir, timeout)
    if r is None or r.returncode:
        return {}
    out: Dict[str, str] = {}
    for p in (r.stdout or "").split("\0"):
        if not p:
            continue
        head = p.replace("\\", "/").split("/", 1)[0]
        if head in DERIVED_ENTRIES:
            out[head] = "tracked"
    return out


# ─── 對外 API ────────────────────────────────────────────────────────────────

def ensure_ignore_one(vcs: str, mem_dir: Path, root: Path, timeout: float = 5.0) -> Dict:
    return _svn_ensure(mem_dir, root, timeout) if vcs == "svn" else _git_ensure(mem_dir, root, timeout)


def ensure_ignore(mem_dir: Path, timeout: float = 5.0) -> List[Dict]:
    """對 mem_dir 找得到的每種 VCS 設 ignore；回每種的報告（無 VCS → []）。"""
    mem_dir = Path(mem_dir)
    if not mem_dir.is_dir():
        return []
    return [ensure_ignore_one(k, mem_dir, r, timeout) for k, r in vcs_roots(mem_dir)]


def tracked_derived_one(vcs: str, mem_dir: Path, timeout: float = 5.0) -> Dict[str, str]:
    return _svn_tracked(mem_dir, timeout) if vcs == "svn" else _git_tracked(mem_dir, timeout)


def tracked_derived(mem_dir: Path, timeout: float = 5.0) -> Dict[str, Dict[str, str]]:
    """{vcs: {衍生檔名: 狀態}}，只列仍在版控者。"""
    mem_dir = Path(mem_dir)
    out: Dict[str, Dict[str, str]] = {}
    for k, _root in vcs_roots(mem_dir):
        if k == "svn" and _svn_versioned(mem_dir, timeout) is not True:
            continue
        hit = tracked_derived_one(k, mem_dir, timeout)
        if hit:
            out[k] = hit
    return out


def _q(p) -> str:
    return '"' + str(p) + '"'


def exit_command(vcs: str, paths: List[Path], items: Optional[Dict[str, str]] = None) -> str:
    """把衍生檔請出版控、檔留本機的確切指令（只給人看，程式不執行）。

    svn 尚未提交的 added 項用 revert 撤銷加入即可；其餘 rm --keep-local。
    """
    items = items or {}
    if vcs == "svn":
        added = [p for p in paths if items.get(Path(p).name) == "added"]
        rm = [p for p in paths if items.get(Path(p).name) != "added"]
        parts = []
        if rm:
            parts.append("svn rm --keep-local --force " + " ".join(_q(p) for p in rm))
        if added:
            parts.append("svn revert " + " ".join(_q(p) for p in added))
        return " && ".join(parts)
    return "git rm -r --cached " + " ".join(_q(p) for p in paths)


def derived_exit_hint(vcs: str, paths: List[Path], items: Optional[Dict[str, str]] = None) -> str:
    """一句話：這些是衍生檔、正解是退出版控、指令是什麼。IndexConflict 與 VcsIgnore 兩處共用同一套措辭。"""
    names = "／".join(sorted({Path(p).name for p in paths}))
    cmd = exit_command(vcs, paths, items)
    if vcs == "svn":
        teammates = ("隊友 update 遇一次「local edit, incoming delete」樹衝突 → "
                     "svn resolve --accept working <檔>，之後永久脫離")
    else:
        teammates = ("隊友 pull 若本機有改動會報 modify/delete 衝突 → git rm --cached <檔> 後繼續；"
                     "無改動則檔案被刪、下次 SessionStart 自動重建")
    return (f"{names} 是衍生檔（缺檔會自動重建），正解是退出版控（檔留本機）：{cmd} 後 commit；{teammates}")


def _tracked_warning(vcs: str, mem_dir: Path, tracked: Dict[str, str]) -> str:
    paths = [mem_dir / n for n in DERIVED_ENTRIES if n in tracked]
    label = "SVN 版控" if vcs == "svn" else "git 追蹤"
    reason = ("每筆都從 atom 檔頭推導、_staging／episodic／vector-db 是本機暫存，留在版控只會每次 update 都衝突"
              + ("（svn:ignore 對已版控檔無效）" if vcs == "svn" else "（.gitignore 對已追蹤檔無效）"))
    return (f"[Guardian:VcsIgnore] ⚠ 衍生檔已被{label}（{', '.join(sorted(tracked))}）——{reason}。\n"
            f"  {derived_exit_hint(vcs, paths, tracked)}\n"
            f"  {_OLD_VERSION_HINT.format(mem=mem_dir)}")


# ─── SessionStart 總成：每個記憶庫每種 VCS 處理一次 ─────────────────────────────

def _marker_key(mem_dir: Path) -> str:
    try:
        key = str(Path(mem_dir).resolve()).replace("\\", "/")
    except OSError:
        key = str(mem_dir).replace("\\", "/")
    return key.lower() if os.name == "nt" else key


def _load_marker(path: Optional[Path]) -> Dict:
    if path is None or not Path(path).exists():
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_marker(path: Optional[Path], data: Dict) -> None:
    if path is None:
        return
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    except OSError as e:
        print(f"[vcs_ignore] marker 寫入失敗：{e}", file=sys.stderr)


def advisory_lines(mem_dir, marker_path: Optional[Path], *, timeout: float = 5.0,
                   today: Optional[str] = None) -> List[str]:
    """SessionStart 入口。無 VCS／~/.claude 自己的記憶／已處理過 → []（零子行程）。

    每種 VCS 成功設過 ignore 後記 marker，之後不再花子行程；記憶庫目錄尚未版控（svn）時不記，
    下次再試。已版控衍生檔的告警也只出一次（記在同一筆）。
    """
    mem_dir = Path(mem_dir)
    if not mem_dir.is_dir() or under_claude_dir(mem_dir):
        return []
    roots = vcs_roots(mem_dir)
    if not roots:
        return []
    marker = _load_marker(marker_path)
    key = _marker_key(mem_dir)
    entry = marker.setdefault(key, {})
    done: Dict[str, str] = entry.setdefault("ignore_done", {})
    warned: Dict[str, str] = entry.setdefault("warned", {})
    pending = [(k, r) for k, r in roots if k not in done]
    if not pending:
        return []
    today = today or date.today().isoformat()
    lines: List[str] = []
    changed = False
    for vcs, root in pending:
        rep = ensure_ignore_one(vcs, mem_dir, root, timeout)
        if rep["skipped"] in ("unversioned", "not-a-repo"):
            continue
        label = "svn:ignore" if vcs == "svn" else ".gitignore"
        if rep["skipped"] == "no-cli":
            lines.append(f"[Guardian:VcsIgnore] ⚠ 有 {'.svn' if vcs == 'svn' else '.git'} 但 {rep['error']}，"
                         f"無法自動設 {label}（{mem_dir}）→ 請手動把 {', '.join(DERIVED_ENTRIES)} 加進 {label}")
            done[vcs] = today
            changed = True
            continue
        if rep["error"]:
            lines.append(f"[Guardian:VcsIgnore] ⚠ {label} 設定失敗（{mem_dir}）：{rep['error']}"
                         f" → 請手動把 {', '.join(DERIVED_ENTRIES)} 加進 {label}")
            continue   # 不記 marker：下次再試，失敗要一直看得到
        if rep["added"]:
            how = ("屬性為本機修改，隨下次 svn commit 上傳" if vcs == "svn"
                   else f"{mem_dir / '.gitignore'} 隨下次 commit 上傳")
            lines.append(f"[Guardian:VcsIgnore] 已為 {mem_dir} 設 {label}（+{', '.join(rep['added'])}；{how}）")
        if rep["skipped"] != "dir-ignored":
            tracked = tracked_derived_one(vcs, mem_dir, timeout)
            if tracked and vcs not in warned:
                lines.append(_tracked_warning(vcs, mem_dir, tracked))
                warned[vcs] = today
                entry["tracked"] = sorted(tracked)
        done[vcs] = today
        changed = True
    if changed:
        _save_marker(marker_path, marker)
    return lines


# ─── CLI：唯讀報告 ───────────────────────────────────────────────────────────

def _main(argv: List[str]) -> int:
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    mem = Path(argv[0])
    rep: Dict = {"memory_dir": str(mem), "under_claude_dir": under_claude_dir(mem),
                 "vcs": [(k, str(r)) for k, r in vcs_roots(mem)], "ignore": {}, "tracked": tracked_derived(mem)}
    for k, _r in vcs_roots(mem):
        if k == "svn":
            try:
                rep["ignore"]["svn"] = _svn_ignore_value(mem, 5.0) if _svn_versioned(mem, 5.0) else "unversioned"
            except RuntimeError as e:
                rep["ignore"]["svn"] = f"error: {e}"
        else:
            gi = mem / ".gitignore"
            rep["ignore"]["git"] = gi.read_text(encoding="utf-8-sig").splitlines() if gi.exists() else []
    sys.stdout.reconfigure(encoding="utf-8")  # lf-exempt: stdio
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
