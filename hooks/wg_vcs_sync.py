"""wg_vcs_sync.py — 記憶庫背景上版控（git 精確檔集 commit + push 快照守門；svn --xml add/delete/--depth empty commit）。

分三層：
  1. 目標集：`collect_sync_targets(cwd, config)` → 根層 memory/ + _AIDocs/_atoms/、專案 .claude/memory/；
     每個記憶目錄各自以 `find_vcs_root` 找最近的 VCS 根（巢狀 repo 取最近者），pathspec 轉成相對該根。
  2. 鎖與請求交接：`workflow/vcs-sync/<root-hash>.lock` 靠 OS 互斥（msvcrt.locking / fcntl.flock），檔內 pid
     只給 stop.py 的活鎖判定看；每次請求先持久化成 `<root-hash>.req/<uuid>.json` 再取鎖，取不到就退出。
     持鎖者每輪開頭把 `.req/` 全部請求改名領取到 `.req/inflight/`（連同上個 worker 中途死掉的殘留）
     合併成聯集跑一輪；只有該輪 status=ok 才刪 inflight，失敗／跳過／crash 都留著給下個持鎖者重做。
     為何不接管死鎖：程序死亡 OS 自動釋放，殘鎖不存在；「讀 pid→判死→unlink」有 pid 重用與 unlink 競態。
  3. 同步主邏輯 `sync_targets_inline`：worker 與測試共用，不 spawn。失敗一律落 `.unpushed` 標記（JSON：
     reason/head_oid/at）+ log（可觀測性鐵律），下個 SessionStart advisory 浮出。

為何 git add/commit 都用同一份「status 列出的實際變更檔」而非整個 pathspec 目錄：已追蹤但被 exclude 的檔
（*.access.json）改了也不得進 commit；pathspec 整目錄 add 或 commit 都會把它帶進去。
為何 push 用固定快照：檢查完待推歷史後才 rev-parse HEAD 會把檢查後插進來的 commit 一起推出去；
head/upstream 在 for-each-ref 之後一次固定，歷史檢查與 push 都用那組 OID。
為何 push 守門：本地若有未發布的程式碼 commit，push 記憶 commit 會連帶發布祖先，違反「程式碼等上GIT」。
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from wg_core import (
    CLAUDE_DIR, WORKFLOW_DIR, _now_iso, _atom_debug_error,
    append_guard_log, find_project_root, find_vcs_root, load_config,
)

SYNC_DIR = WORKFLOW_DIR / "vcs-sync"
LOG_PATH = CLAUDE_DIR / "Logs" / "vcs-sync.log"
LEDGER_DIR = WORKFLOW_DIR / "harvest-ledger"

DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "push": True,
    "root_pathspecs": ["memory", "_AIDocs/_atoms"],
    "project_pathspecs": [".claude/memory"],
    "exclude": ["**/*.access.json"],
    "timeout_s": 60,
}

_NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}

# svn：commit 被拒且可用 update 解開的錯誤碼（out-of-date／需先 update／遠端已變）
_SVN_RETRY_CODES = {"E155011", "E160028", "E170004"}
# svn：一律停止的錯誤碼（WC lock、認證、tree conflict）
_SVN_STOP_CODES = {"E160024", "E155004", "E170001", "E215004"}
_SVN_CHANGED_ITEMS = {"modified", "added", "deleted", "replaced"}


# ─── config ──────────────────────────────────────────────────────────────────

def vcs_sync_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """`vcs_sync` 區塊補預設；缺省時相容舊鍵 self_iteration.auto_commit_promotions / auto_push_promotions。"""
    vs = (config or {}).get("vcs_sync")
    if vs is None:
        si = (config or {}).get("self_iteration", {}) or {}
        vs = {"enabled": si.get("auto_commit_promotions", True),
              "push": si.get("auto_push_promotions", True)}
    merged = dict(DEFAULTS)
    merged.update(vs or {})
    return merged


# ─── 目標集 ──────────────────────────────────────────────────────────────────

@dataclass
class SyncTarget:
    vcs: str                      # "git" | "svn"
    root: Path                    # VCS 根（絕對）
    pathspecs: List[str] = field(default_factory=list)   # 相對 root 的 posix 路徑
    mem_dirs: List[Path] = field(default_factory=list)   # 記憶目錄絕對路徑（跑索引同步用）

    def to_dict(self) -> Dict[str, Any]:
        return {"vcs": self.vcs, "root": self.root.as_posix(),
                "pathspecs": list(self.pathspecs), "mem_dirs": [p.as_posix() for p in self.mem_dirs]}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SyncTarget":
        return cls(d["vcs"], Path(d["root"]), list(d.get("pathspecs", [])),
                   [Path(p) for p in d.get("mem_dirs", [])])


def collect_sync_targets(cwd: str, config: Dict[str, Any],
                         claude_dir: Optional[Path] = None) -> List[SyncTarget]:
    """根層 + 專案層記憶目錄 → 依 VCS 根分組。記憶目錄不存在或不在任何 VCS 內者略過。"""
    vs = vcs_sync_config(config)
    base_root = claude_dir or CLAUDE_DIR
    bases: List[tuple] = [(base_root, vs["root_pathspecs"])]
    proj = find_project_root(cwd) if cwd else None
    if proj and proj.resolve() != base_root.resolve():
        bases.append((proj, vs["project_pathspecs"]))

    targets: Dict[str, SyncTarget] = {}
    for base, specs in bases:
        for spec in specs:
            mem_dir = Path(base) / spec
            if not mem_dir.is_dir():
                continue
            vcs = find_vcs_root(mem_dir)
            if vcs is None:
                continue
            kind, root = vcs
            try:
                rel = mem_dir.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
            key = root.resolve().as_posix().lower()
            t = targets.setdefault(key, SyncTarget(kind, root.resolve()))
            if rel not in t.pathspecs:
                t.pathspecs.append(rel)
                t.mem_dirs.append(mem_dir.resolve())
    return list(targets.values())


# ─── 鎖（OS 互斥） ───────────────────────────────────────────────────────────

def root_hash(root: Path) -> str:
    return hashlib.sha1(Path(root).resolve().as_posix().lower().encode("utf-8")).hexdigest()[:12]


def marker_path(root: Path, suffix: str) -> Path:
    return SYNC_DIR / f"{root_hash(root)}.{suffix}"


# 鎖的位元組放在檔案遠端（1 GiB 處）：Windows 的 msvcrt 鎖是強制鎖，鎖在 0 偏移會讓
# stop.py 用 read_text 讀 pid 時撞 lock violation；鎖在內容之外，讀 pid 不受影響。
_LOCK_OFFSET = 1 << 30


class FileLock:
    """單一檔案的 OS 互斥鎖：持有者保持 fd 開到 release；程序死亡由 OS 自動釋放。
    檔內寫 pid 只供人／stop.py 的活鎖判定看，不參與互斥。"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.fd: Optional[int] = None

    @staticmethod
    def _try_lock(fd: int) -> bool:
        try:
            if sys.platform == "win32":
                import msvcrt
                os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    @staticmethod
    def _unlock(fd: int) -> None:
        try:
            if sys.platform == "win32":
                import msvcrt
                os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass

    def acquire(self, wait_s: float = 0.0) -> bool:
        """非阻塞取鎖；wait_s>0 時每 50ms 重試到期限。任何失敗（含權限）都視為他人持有。"""
        if self.fd is not None:
            return True
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        except OSError:
            return False
        deadline = time.monotonic() + wait_s
        while True:
            if self._try_lock(fd):
                break
            if time.monotonic() >= deadline:
                os.close(fd)
                return False
            time.sleep(0.05)
        self.fd = fd
        self._write(str(os.getpid()))
        return True

    def _write(self, text: str) -> None:
        try:
            data = text.encode("utf-8")
            os.lseek(self.fd, 0, os.SEEK_SET)
            os.write(self.fd, data)
            os.ftruncate(self.fd, len(data))
        except OSError:
            pass

    def release(self) -> None:
        """清 pid 再放鎖；不 unlink——別人可能已開同一檔等著取鎖，unlink 會造成雙持有。"""
        if self.fd is None:
            return
        self._write("0")
        self._unlock(self.fd)
        try:
            os.close(self.fd)
        finally:
            self.fd = None

    @classmethod
    def is_held(cls, path: Path) -> bool:
        """嘗試非阻塞取鎖：取到立刻放掉 → 無人持有；取不到 → 有人持有。檔不存在 → 無人。"""
        if not Path(path).exists():
            return False
        try:
            fd = os.open(path, os.O_RDWR)
        except OSError:
            return True
        try:
            if cls._try_lock(fd):
                cls._unlock(fd)
                return False
            return True
        finally:
            os.close(fd)


_held_locks: Dict[str, FileLock] = {}   # root_hash → 本程序持有的鎖


def acquire_lock(root: Path) -> bool:
    lk = _held_locks.get(root_hash(root)) or FileLock(marker_path(root, "lock"))
    if not lk.acquire():
        return False
    _held_locks[root_hash(root)] = lk
    return True


def release_lock(root: Path) -> None:
    lk = _held_locks.pop(root_hash(root), None)
    if lk:
        lk.release()


def lock_is_live(root: Path) -> bool:
    """有人持鎖（stop.py SyncReminder 用此判定「root 正在同步中」）；pid 只進 log 不參與判定。"""
    return FileLock.is_held(marker_path(root, "lock"))


# ─── 請求交接（.req/<uuid>.json） ────────────────────────────────────────────

def request_dir(root: Path) -> Path:
    return SYNC_DIR / f"{root_hash(root)}.req"


def write_request(root: Path, pathspecs: Sequence[str], retired_paths: Sequence[str] = (),
                  reason: str = "", session_id: str = "", mem_dirs: Sequence[Path] = ()) -> Path:
    """本次請求持久化；spawn 失敗或被鎖拒都不會遺失，持鎖者或下一個 worker 會消費。"""
    d = request_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{uuid.uuid4().hex}.json"
    _atomic_write(p, json.dumps({
        "pathspecs": list(pathspecs), "retired_paths": list(retired_paths),
        "mem_dirs": [Path(m).as_posix() for m in mem_dirs],
        "reason": reason, "sid": session_id, "at": _now_iso(),
    }, ensure_ascii=False))
    return p


INFLIGHT = "inflight"


def inflight_dir(root: Path) -> Path:
    return request_dir(root) / INFLIGHT


def _json_files(d: Path) -> List[Path]:
    try:
        return sorted(p for p in d.iterdir() if p.suffix == ".json")
    except OSError:
        return []


def pending_requests(root: Path, include_inflight: bool = False) -> int:
    """未領取的請求數（持鎖者迴圈用）；include_inflight 連同已領取未完成的一起算（advisory 判孤兒用）。"""
    n = len(_json_files(request_dir(root)))
    if include_inflight:
        n += len(_json_files(inflight_dir(root)))
    return n


def claim_requests(root: Path) -> Tuple[Dict[str, List[str]], List[Path]]:
    """領取：`.req/*.json` 改名到 `.req/inflight/` 再讀成聯集，連同 inflight 既有殘留（上個 worker 中途死）。
    不在這裡刪檔：讀完就刪的話，同步中途被殺（_Stop／timeout／程序死）請求就蒸發，沒人再補跑；
    改名是原子操作，領取後別的 worker 不會重複領。只有持鎖者呼叫。回 (聯集, 已領取檔列表) 供 ack_requests。"""
    merged: Dict[str, List[str]] = {"pathspecs": [], "retired_paths": [], "mem_dirs": [], "reasons": [], "sids": []}
    inflight = inflight_dir(root)
    claimed: List[Path] = _json_files(inflight)
    fresh = _json_files(request_dir(root))
    if fresh:
        inflight.mkdir(parents=True, exist_ok=True)
    for p in fresh:
        dst = inflight / p.name
        try:
            os.replace(p, dst)
        except OSError:
            continue
        claimed.append(dst)
    usable: List[Path] = []
    for p in claimed:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # 讀不到的留在 inflight、不列入 ack，下輪再領；避免請求內容未併入就被刪
        usable.append(p)
        for key, src in (("pathspecs", "pathspecs"), ("retired_paths", "retired_paths"),
                         ("mem_dirs", "mem_dirs"), ("reasons", "reason"), ("sids", "sid")):
            vals = rec.get(src) or []
            for v in (vals if isinstance(vals, list) else [vals]):
                if v and v not in merged[key]:
                    merged[key].append(v)
    return merged, usable


def ack_requests(claimed: Sequence[Path]) -> None:
    """同步成功後刪已領取的請求檔。"""
    for p in claimed:
        try:
            p.unlink()
        except OSError:
            pass


# ─── unpushed 標記／roots.json ───────────────────────────────────────────────

def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:6]}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def write_unpushed(root: Path, reason: str, head_oid: Optional[str] = None) -> None:
    """JSON 標記：reason + 當時 HEAD（git）。advisory 看到 HEAD 已換且 ahead=0 → 視為已解決自動清掉。"""
    rec = {"reason": (reason or "").strip().replace("\n", " ")[:500], "head_oid": head_oid or None,
           "at": _now_iso()}
    _atomic_write(marker_path(root, "unpushed"), json.dumps(rec, ensure_ascii=False) + "\n")


def clear_unpushed(root: Path) -> None:
    try:
        marker_path(root, "unpushed").unlink()
    except OSError:
        pass


def read_unpushed_record(root: Path) -> Optional[Dict[str, Any]]:
    try:
        raw = marker_path(root, "unpushed").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        rec = json.loads(raw)
        if isinstance(rec, dict):
            return rec
    except ValueError:
        pass
    return {"reason": raw, "head_oid": None, "at": None}   # 舊格式純文字


def read_unpushed(root: Path) -> Optional[str]:
    rec = read_unpushed_record(root)
    return (rec or {}).get("reason") or None


def load_roots() -> Dict[str, Any]:
    try:
        return json.loads((SYNC_DIR / "roots.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def update_root_record(target: SyncTarget, *, last_sync: Optional[str] = None,
                       last_error: Optional[str] = None, touch_sync: bool = False) -> bool:
    """roots.json 讀改寫包在 roots.lock（OS 互斥）內：多 root worker 並行時不互相蓋掉對方的紀錄。
    選單檔＋共用鎖而非每 root 一檔：SessionStart 只讀一個 map，hash↔路徑對照留在同一處。
    等鎖逾時 → 不進讀改寫、記 log、回 False：無鎖寫入會把別人剛寫的紀錄整份蓋掉，少一筆比錯一份好。"""
    lk = FileLock(SYNC_DIR / "roots.lock")
    if not lk.acquire(wait_s=3.0):
        msg = f"roots.lock 取鎖逾時，略過 roots.json 更新: {target.root.as_posix()}"
        _default_log(msg)
        _atom_debug_error("vcs_sync:roots_lock", TimeoutError(msg))
        return False
    try:
        roots = load_roots()
        key = target.root.as_posix()
        rec = roots.get(key) or {"vcs": target.vcs, "pathspecs": [], "last_sync": None, "last_error": None}
        rec["vcs"] = target.vcs
        rec["pathspecs"] = list(target.pathspecs)
        if touch_sync:
            rec["last_sync"] = last_sync or _now_iso()
        rec["last_error"] = last_error
        roots[key] = rec
        _atomic_write(SYNC_DIR / "roots.json", json.dumps(roots, ensure_ascii=False, indent=2))
    finally:
        lk.release()
    return True


# ─── spawn ───────────────────────────────────────────────────────────────────

def _gui_python() -> str:
    """uv default-shim 的 pythonw（無 console；與 wg_extraction 同源，路徑無版本號）。"""
    if sys.platform == "win32":
        cand = Path.home() / "AppData" / "Local" / "Python" / "bin" / "pythonw.exe"
        if cand.exists():
            return str(cand)
    return sys.executable


def worker_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"   # 憑證過期時 git 不得開互動提示掛住 worker
    env["GCM_INTERACTIVE"] = "0"       # Git Credential Manager 同上
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def read_retired_paths(session_id: str) -> List[str]:
    """harvest-ledger/<sid>.jsonl 內 `validated: true` 紀錄的 action=retired path（退役前路徑）。
    缺 validated 欄位視為 false：核不過的收割回報不得驅動 svn delete。"""
    out: List[str] = []
    if not session_id:
        return out
    p = LEDGER_DIR / f"{session_id}.jsonl"
    if not p.exists():
        return out
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("validated") is not True:
                continue
            for it in rec.get("items") or []:
                if it.get("action") == "retired" and it.get("path"):
                    out.append(str(it["path"]))
    except OSError:
        pass
    return out


def spawn_vcs_sync(session_id: str, cwd: str, reason: str,
                   retired_paths: Optional[Sequence[str]] = None,
                   config: Optional[Dict[str, Any]] = None) -> int:
    """請求先落 `.req/`，再 detached 起 vcs-sync-worker.py；回 pid（0＝未起：關閉／無目標／失敗）。
    起不來時請求仍在 `.req/`（下個 worker 消費）、每 root 落 `.unpushed` + last_error 供 advisory 浮出。fail-open。"""
    targets: List[SyncTarget] = []
    try:
        cfg = config if config is not None else load_config()
        vs = vcs_sync_config(cfg)
        if not vs.get("enabled", True):
            return 0
        targets = collect_sync_targets(cwd, cfg)
        if not targets:
            return 0
        worker_path = CLAUDE_DIR / "hooks" / "vcs-sync-worker.py"
        if not worker_path.exists():
            raise FileNotFoundError(str(worker_path))
        retired = list(retired_paths or [])
        for p in read_retired_paths(session_id):
            if p not in retired:
                retired.append(p)
        for t in targets:
            write_request(t.root, t.pathspecs, retired, reason, session_id, t.mem_dirs)
        kwargs: Dict[str, Any] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        else:
            kwargs["start_new_session"] = True
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        log_fh = open(LOG_PATH, "a", encoding="utf-8", newline="\n")
        payload = json.dumps({
            "session_id": session_id, "cwd": cwd, "reason": reason,
            "retired_paths": retired, "config": cfg, "enqueued": True,
            "targets": [t.to_dict() for t in targets],
        }, ensure_ascii=False)
        try:
            proc = subprocess.Popen(
                [_gui_python(), str(worker_path)],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log_fh,
                env=worker_env(), **kwargs)
        finally:
            log_fh.close()
        proc.stdin.write(payload.encode("utf-8"))
        proc.stdin.close()
        append_guard_log("worker-runs", {
            "event": "spawn", "pid": proc.pid, "mode": f"vcs-sync:{reason}",
            "session_id": session_id, "roots": [t.root.as_posix() for t in targets],
        })
        return proc.pid
    except Exception as e:
        _atom_debug_error("vcs_sync:spawn", e)
        msg = f"worker 起不來: {type(e).__name__}: {e}"[:200]
        for t in targets:
            try:
                write_unpushed(t.root, msg)
                update_root_record(t, last_error=msg)
            except Exception as e2:
                _atom_debug_error("vcs_sync:spawn:mark", e2)
        return 0


# ─── 同步主邏輯（worker 與測試共用） ──────────────────────────────────────────

Logger = Callable[[str], None]


def _default_log(msg: str) -> None:
    print(f"[{_now_iso()}] {msg}", file=sys.stderr, flush=True)


def _under_pathspecs(path: str, pathspecs: Sequence[str]) -> bool:
    """pathspec "." 或 "" 代表整個 root。"""
    for s in pathspecs:
        s = s.strip("/")
        if s in ("", "."):
            return True
        if path == s or path.startswith(s + "/"):
            return True
    return False


def _excluded(rel: str, exclude: Sequence[str]) -> bool:
    """pattern 含 "/"（memory/_meta/**）只比完整相對路徑；不含 "/" 的（*.access.json；**/*.access.json 取尾段）
    另比 basename，讓根目錄下的檔也中。不對含 "/" 的 pattern 截尾段比 basename：`memory/_meta/**` 的
    尾段是 `**`，拿去比 basename 會把所有檔都排除。"""
    name = rel.rsplit("/", 1)[-1]
    for pat in exclude:
        if fnmatch.fnmatch(rel, pat):
            return True
        body = pat[3:] if pat.startswith("**/") else pat
        if "/" not in body and fnmatch.fnmatch(name, body):
            return True
    return False


class _Skip(Exception):
    """本 root 本輪不動（狀態不乾淨／不支援的佈局）；訊息進 log 與 roots.json。"""


class _Stop(Exception):
    """本 root 失敗，須留 `.unpushed` 標記；git 路徑補上當時 HEAD 供 advisory 判已解決。"""

    head_oid: Optional[str] = None


def _run(cmd: List[str], cwd: Path, timeout: float, env: Dict[str, str],
         text: bool = True) -> subprocess.CompletedProcess:
    kw: Dict[str, Any] = {"capture_output": True, "timeout": timeout, "env": env, "cwd": str(cwd)}
    if text:
        kw.update(text=True, encoding="utf-8", errors="replace")
    return subprocess.run(cmd, **kw, **_NO_WINDOW)


def _sync_indexes(target: SyncTarget, timeout: float, env: Dict[str, str], log: Logger) -> None:
    """提交前把 atom 與索引拉到同一快照：有 _atom_index.json 的記憶目錄跑 sync-memory-index --write，
    失敗即 _Stop（本輪不提交，半套索引不能進版控）；sync-atom-index --check 漂移只記 log。"""
    tools = CLAUDE_DIR / "tools"
    for mem in target.mem_dirs:
        if not (mem / "_atom_index.json").exists():
            continue
        for args in (["sync-memory-index.py", "--write", "--memory-dir", str(mem)],
                     ["sync-atom-index.py", "--check", "--memory-dir", str(mem)]):
            script = tools / args[0]
            if not script.exists():
                continue
            must_pass = "--write" in args
            try:
                r = _run([sys.executable, str(script), *args[1:]], CLAUDE_DIR, timeout, env)
            except (OSError, subprocess.SubprocessError) as e:
                if must_pass:
                    raise _Stop(f"索引同步失敗 {args[0]} ({mem}): {e}"[:200])
                log(f"[index] {args[0]} 例外 ({mem}): {e}")
                continue
            if r.returncode == 0:
                continue
            tail = (r.stderr or r.stdout).strip()[-200:]
            if must_pass:
                raise _Stop(f"索引同步失敗 {args[0]} rc={r.returncode} ({mem}): {tail}")
            log(f"[index] {args[0]} rc={r.returncode} ({mem}): {tail}")


# ── git ──

def _git_cmd(t: SyncTarget, vs: Dict[str, Any], env: Dict[str, str]):
    timeout = float(vs.get("timeout_s", 60))

    def git(*args: str, to: Optional[float] = None) -> subprocess.CompletedProcess:
        return _run(["git", *args], t.root, to or timeout, env)
    return git


def _git_check(t: SyncTarget, vs: Dict[str, Any], env: Dict[str, str]) -> str:
    """拒跑狀態檢查（在索引同步之前，合併中不得改寫 catalog）；回目前分支名。"""
    git = _git_cmd(t, vs, env)
    root = t.root
    r = git("rev-parse", "--git-dir", "--git-common-dir")
    if r.returncode != 0:
        raise _Skip(f"不是 git 工作樹: {(r.stderr or '').strip()[:120]}")
    lines = (r.stdout or "").splitlines()
    git_dir = Path(lines[0]) if lines else root / ".git"
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        if (git_dir / name).exists():
            raise _Skip(f"{name} 存在（合併／rebase 進行中）")
    if (git("ls-files", "-u").stdout or "").strip():
        raise _Skip("有未解衝突（ls-files -u 非空）")
    if git("rev-parse", "--verify", "-q", "HEAD").returncode != 0:
        raise _Skip("unborn branch（尚無 commit）")
    r = git("symbolic-ref", "--short", "-q", "HEAD")
    if r.returncode != 0 or not (r.stdout or "").strip():
        raise _Skip("detached HEAD")
    branch = r.stdout.strip()
    if (git("config", "--bool", "core.sparseCheckout").stdout or "").strip() == "true" \
            or (git_dir / "info" / "sparse-checkout").exists():
        raise _Skip("sparse checkout 不支援")
    if (git("rev-parse", "--show-superproject-working-tree").stdout or "").strip():
        raise _Skip("submodule 內記憶目錄不支援")
    return branch


def _parse_porcelain_z(out: str) -> List[Tuple[str, str]]:
    """`git status --porcelain -z` → [(XY, path)]；rename/copy 的來源路徑另成一筆（同 XY）。"""
    toks = out.split("\0")
    res: List[Tuple[str, str]] = []
    i = 0
    while i < len(toks):
        tok = toks[i]
        i += 1
        if len(tok) < 4:
            continue
        xy, path = tok[:2], tok[3:]
        res.append((xy, path))
        if "R" in xy or "C" in xy:
            if i < len(toks) and toks[i]:
                res.append((xy, toks[i]))
            i += 1
    return res


def _git_changed_files(git, t: SyncTarget, exclude: Sequence[str]) -> List[str]:
    """pathspec 內實際變更檔（含 untracked；-uall 展開目錄）過濾 exclude 與 ignored → add/commit 共用的允許集合。"""
    r = git("status", "--porcelain", "-z", "-uall", "--", *t.pathspecs)
    if r.returncode != 0:
        raise _Stop(f"git status 失敗: {(r.stderr or '').strip()[:200]}")
    files: List[str] = []
    for xy, path in _parse_porcelain_z(r.stdout or ""):
        if xy == "!!" or not path:
            continue
        if not _under_pathspecs(path, t.pathspecs) or _excluded(path, exclude):
            continue
        if path not in files:
            files.append(path)
    return files


def _git_sync(t: SyncTarget, vs: Dict[str, Any], env: Dict[str, str], log: Logger,
              branch: str) -> Dict[str, Any]:
    git = _git_cmd(t, vs, env)
    timeout = float(vs.get("timeout_s", 60))
    root = t.root

    def git_retry_lock(*args: str) -> subprocess.CompletedProcess:
        """index.lock 競態（他 session 正在 commit）→ 重試 ≤3，每次 sleep 1。"""
        r = git(*args)
        for _ in range(2):
            if r.returncode == 0 or "index.lock" not in (r.stderr or ""):
                break
            time.sleep(1)
            r = git(*args)
        return r

    try:
        return _git_sync_body(t, vs, git, git_retry_lock, log, branch, timeout)
    except _Stop as e:
        e.head_oid = (git("rev-parse", "HEAD").stdout or "").strip() or None
        raise


def _git_sync_body(t: SyncTarget, vs: Dict[str, Any], git, git_retry_lock, log: Logger,
                   branch: str, timeout: float) -> Dict[str, Any]:
    root = t.root
    exclude = vs.get("exclude", [])
    # ── add + commit：同一份允許路徑集合（`:(literal)` 防路徑被當 glob）──
    files = _git_changed_files(git, t, exclude)
    specs = [f":(literal){f}" for f in files]
    result: Dict[str, Any] = {"vcs": "git", "root": root.as_posix(), "committed": 0, "pushed": False}
    if files:
        r = git_retry_lock("add", "-A", "--", *specs)
        if r.returncode != 0:
            raise _Stop(f"git add 失敗: {(r.stderr or r.stdout).strip()[:200]}")
        msg = f"chore(memory): knowledge harvest {date.today().isoformat()}（{len(files)} 檔）"
        r = git_retry_lock("commit", "-q", "-m", msg, "--", *specs)
        if r.returncode != 0:
            raise _Stop(f"git commit 失敗: {(r.stderr or r.stdout).strip()[:200]}")
        result["committed"] = len(files)
        log(f"[git] {root}: commit {len(files)} 檔")

    # ── push 守門：head／upstream 一次固定，之後插進來的 commit 不在快照內 ──
    if not vs.get("push", True):
        return result
    r = git("for-each-ref", "--format=%(upstream:remotename) %(upstream:remoteref)", f"refs/heads/{branch}")
    parts = (r.stdout or "").split()
    if r.returncode != 0 or len(parts) != 2:
        log(f"[git] {root}: {branch} 無 upstream，不 push")
        return result
    remote, remoteref = parts
    head = (git("rev-parse", "--verify", "-q", f"refs/heads/{branch}").stdout or "").strip()
    r = git("rev-parse", "--verify", "-q", f"{branch}@{{upstream}}")
    up = (r.stdout or "").strip()
    if not head or r.returncode != 0 or not up:
        log(f"[git] {root}: upstream ref 不可解析，不 push: {(r.stderr or '').strip()[:120]}")
        return result
    r = git("rev-list", "--parents", f"{up}..{head}")
    if r.returncode != 0:
        raise _Stop(f"rev-list 失敗: {(r.stderr or '').strip()[:200]}")
    pending = [ln.split() for ln in (r.stdout or "").splitlines() if ln.strip()]
    if not pending:
        clear_unpushed(root)
        return result
    for fields in pending:
        sha = fields[0]
        if len(fields) > 2:
            raise _Stop(f"待推歷史含 merge commit {sha[:8]}，本地有未發布的非記憶 commit，待使用者上GIT 一起推")
        r = git("diff-tree", "--no-commit-id", "--name-only", "-z", "-r", "--root", sha)
        if r.returncode != 0:
            raise _Stop(f"diff-tree {sha[:8]} 失敗，無法確認待推歷史: {(r.stderr or '').strip()[:120]}")
        # 可自動發布 ＝ 在 pathspec 內且不被 exclude；exclude 的檔（memory/_meta/** 設定檔）只會由使用者
        # 手動 commit，出現在待推歷史就表示有人為 commit 等著一起上GIT，不能替他推
        foreign = [f for f in (r.stdout or "").split("\0")
                   if f and (not _under_pathspecs(f, t.pathspecs) or _excluded(f, exclude))]
        if foreign:
            raise _Stop(f"待推歷史含非記憶 commit {sha[:8]}（{foreign[0]}），本地有未發布的非記憶 commit，待使用者上GIT 一起推")
    r = git("push", "--quiet", remote, f"{head}:{remoteref}", to=timeout)
    if r.returncode != 0:
        raise _Stop(f"git push 被拒: {(r.stderr or r.stdout).strip()[-200:]}")
    result["pushed"] = True
    clear_unpushed(root)
    log(f"[git] {root}: push {len(pending)} commit ({head[:8]}) → {remote} {remoteref}")
    return result


# ── svn ──

def _svn_exe() -> str:
    import shutil
    found = shutil.which("svn")
    if found:
        return found
    cand = Path(r"C:\Program Files\TortoiseSVN\bin\svn.exe")
    return str(cand) if cand.exists() else "svn"


def _svn_entries(stdout: bytes):
    import xml.etree.ElementTree as ET
    if not stdout.strip():
        return []
    out = []
    for ent in ET.fromstring(stdout).iter("entry"):
        ws = ent.find("wc-status")
        if ws is None:
            continue
        out.append((ent.get("path", ""), ws.get("item", ""), ws.get("tree-conflicted") == "true"))
    return out


def _rel_to(root: Path, p: str) -> Optional[str]:
    try:
        fp = Path(p)
        return (fp if fp.is_absolute() else root / fp).resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _svn_codes(stderr: bytes) -> set:
    return set(m.decode() for m in re.findall(rb"E\d{6}", stderr or b""))


class _Svn:
    """單 root 的 svn 呼叫包裝（_svn_check 與 _svn_sync 共用）。"""

    def __init__(self, t: SyncTarget, vs: Dict[str, Any], env: Dict[str, str]):
        self.root = t.root
        self.exe = _svn_exe()
        self.timeout = float(vs.get("timeout_s", 60))
        self.env = env

    def run(self, *args: str) -> subprocess.CompletedProcess:
        return _run([self.exe, "--non-interactive", *args], self.root, self.timeout, self.env, text=False)

    @staticmethod
    def err(r: subprocess.CompletedProcess) -> str:
        lines = (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        return lines[-1][:200] if lines else f"rc={r.returncode}"

    def status(self, paths: Sequence[str], depth: Optional[str] = None):
        args = ["status", "--xml"] + (["--depth", depth] if depth else []) + ["--", *paths]
        r = self.run(*args)
        if r.returncode != 0:
            raise _Stop(f"svn status 失敗: {self.err(r)}")
        return self._entries(r.stdout)

    def _entries(self, stdout: bytes):
        return _svn_entries(stdout)

    def has_conflict(self, paths: Sequence[str]) -> bool:
        return any(item == "conflicted" or tc for _, item, tc in self.status(paths))


def _svn_check(t: SyncTarget, vs: Dict[str, Any], env: Dict[str, str]) -> None:
    """拒跑狀態（衝突）檢查在索引同步之前。"""
    if _Svn(t, vs, env).has_conflict(t.pathspecs):
        raise _Stop("工作副本有未解衝突，停止（先 svn resolve）")


def _svn_ancestors(pathspecs: Sequence[str]) -> List[str]:
    out: List[str] = []
    for spec in pathspecs:
        parts = spec.split("/")
        for i in range(1, len(parts) + 1):
            a = "/".join(parts[:i])
            if a not in pathspecs and a not in out:
                out.append(a)
    return out


def _svn_sync(t: SyncTarget, vs: Dict[str, Any], env: Dict[str, str], log: Logger,
              retired: Sequence[str]) -> Dict[str, Any]:
    root = t.root
    svn = _Svn(t, vs, env)
    exclude = vs.get("exclude", [])

    retired_rel = {rel for rel in (_rel_to(root, p) for p in retired) if rel}
    entries = svn.status(t.pathspecs)
    if any(item == "conflicted" or tc for _, item, tc in entries):
        raise _Stop("工作副本有未解衝突，停止（先 svn resolve）")

    added = deleted = 0
    for p, item, _ in sorted(entries, key=lambda e: e[0]):
        rel = _rel_to(root, p)
        if not rel:
            continue
        if item == "unversioned":
            abs_p = root / rel
            files = [rel] if abs_p.is_file() else [
                (Path(dp) / fn).resolve().relative_to(root.resolve()).as_posix()
                for dp, _dn, fns in os.walk(abs_p) for fn in fns]
            for f in files:
                if _excluded(f, exclude):
                    continue
                r = svn.run("add", "--depth", "empty", "--parents", "--", f)
                if r.returncode != 0:
                    raise _Stop(f"svn add 失敗 ({f}): {svn.err(r)}")
                added += 1
        elif item == "missing" and rel in retired_rel:
            # 冪等：只刪 status 仍為 missing（已退役、尚未 svn delete）的檔
            r = svn.run("delete", "--", rel)
            if r.returncode != 0:
                raise _Stop(f"svn delete 失敗 ({rel}): {svn.err(r)}")
            deleted += 1

    # ── commit targets＝status 實際變更項（在 pathspec 內、不被 exclude）＋ --parents 新加的祖先；
    #    一律 --depth empty：pathspec 目錄下別人 svn add 但不屬記憶的檔不得被整目錄提交帶走 ──
    def collect_targets() -> List[str]:
        out: List[str] = []
        for p, item, _ in svn.status(_svn_ancestors(t.pathspecs), depth="empty"):
            rel = _rel_to(root, p)
            if rel and item == "added" and rel not in out:
                out.append(rel)
        for p, item, _ in sorted(svn.status(t.pathspecs), key=lambda e: e[0]):
            rel = _rel_to(root, p)
            if not rel or item not in _SVN_CHANGED_ITEMS:
                continue
            if not _under_pathspecs(rel, t.pathspecs) or _excluded(rel, exclude):
                continue
            if rel not in out:
                out.append(rel)
        return out

    targets = collect_targets()
    result: Dict[str, Any] = {"vcs": "svn", "root": root.as_posix(), "committed": 0,
                              "added": added, "deleted": deleted}
    if not targets:
        clear_unpushed(root)
        return result

    msg = f"chore(memory): knowledge harvest {date.today().isoformat()}（+{added} −{deleted}）"
    fd, msg_path = tempfile.mkstemp(prefix="vcs-sync-", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(msg)
    try:
        r = svn.run("commit", "--depth", "empty", "--encoding", "UTF-8", "-F", msg_path, "--", *targets)
        if r.returncode != 0:
            codes = _svn_codes(r.stderr)
            if codes & _SVN_STOP_CODES or not (codes & _SVN_RETRY_CODES):
                raise _Stop(f"svn commit 失敗 {sorted(codes)}: {svn.err(r)}")
            log(f"[svn] {root}: commit 被拒 {sorted(codes)} → update 後重試一次")
            u = svn.run("update", "--accept", "postpone", "--", *t.pathspecs)
            if u.returncode != 0:
                raise _Stop(f"svn update 失敗: {svn.err(u)}")
            if svn.has_conflict(t.pathspecs):
                _run([sys.executable, str(CLAUDE_DIR / "tools" / "merge-atom-index.py"),
                      "--resolve", "--quiet", "--cwd", str(root)], root, svn.timeout, env)
                if svn.has_conflict(t.pathspecs):
                    raise _Stop("update 後有衝突（非索引檔或索引驅動解不開），停止不重試")
            targets = collect_targets()   # update 可能改掉本地變更集，重算
            r = svn.run("commit", "--depth", "empty", "--encoding", "UTF-8", "-F", msg_path, "--", *targets)
            if r.returncode != 0:
                raise _Stop(f"svn commit 重試仍失敗 {sorted(_svn_codes(r.stderr))}: {svn.err(r)}")
    finally:
        try:
            os.unlink(msg_path)
        except OSError:
            pass
    result["committed"] = len(targets)
    clear_unpushed(root)
    log(f"[svn] {root}: commit {len(targets)} 項（+{added} −{deleted}）")
    return result


# ── 單 root 一輪 + 鎖迴圈 ──

def _sync_root_once(t: SyncTarget, vs: Dict[str, Any], env: Dict[str, str], log: Logger,
                    retired: Sequence[str], pre_sync: bool) -> Dict[str, Any]:
    """順序固定：拒跑狀態檢查 → 索引同步 → commit/push。合併中或 detached 時索引檔不得被改寫。"""
    try:
        branch = _git_check(t, vs, env) if t.vcs == "git" else None
        if t.vcs != "git":
            _svn_check(t, vs, env)
        if pre_sync:
            _sync_indexes(t, float(vs.get("timeout_s", 60)), env, log)
        res = _git_sync(t, vs, env, log, branch) if t.vcs == "git" else _svn_sync(t, vs, env, log, retired)
        update_root_record(t, touch_sync=True, last_error=None)
        res["status"] = "ok"
        return res
    except _Skip as e:
        log(f"[{t.vcs}] {t.root}: 跳過 — {e}")
        update_root_record(t, last_error=f"skip: {e}")
        return {"vcs": t.vcs, "root": t.root.as_posix(), "status": "skipped", "reason": str(e)}
    except _Stop as e:
        log(f"[{t.vcs}] {t.root}: 停止 — {e}")
        write_unpushed(t.root, str(e), head_oid=e.head_oid)
        update_root_record(t, last_error=str(e))
        return {"vcs": t.vcs, "root": t.root.as_posix(), "status": "unpushed", "reason": str(e)}
    except subprocess.TimeoutExpired as e:
        reason = f"子行程逾時 {e.timeout}s: {' '.join(map(str, e.cmd))[:120]}"
        log(f"[{t.vcs}] {t.root}: {reason}")
        write_unpushed(t.root, reason)
        update_root_record(t, last_error=reason)
        return {"vcs": t.vcs, "root": t.root.as_posix(), "status": "error", "reason": reason}
    except (OSError, subprocess.SubprocessError) as e:
        reason = f"{type(e).__name__}: {e}"[:200]
        log(f"[{t.vcs}] {t.root}: {reason}")
        write_unpushed(t.root, reason)
        update_root_record(t, last_error=reason)
        return {"vcs": t.vcs, "root": t.root.as_posix(), "status": "error", "reason": reason}


def _merge_target(t: SyncTarget, req: Dict[str, List[str]]) -> Tuple[SyncTarget, List[str]]:
    """本次 target 與 `.req/` 內所有請求聯集（pathspecs／mem_dirs／retired_paths）。"""
    specs = list(t.pathspecs)
    mems = list(t.mem_dirs)
    for s in req.get("pathspecs", []):
        if s not in specs:
            specs.append(s)
    for m in req.get("mem_dirs", []):
        mp = Path(m)
        if mp not in mems:
            mems.append(mp)
    return SyncTarget(t.vcs, t.root, specs, mems), list(req.get("retired_paths", []))


def sync_targets_inline(targets: Sequence[SyncTarget], config: Dict[str, Any],
                        retired_paths: Sequence[str] = (), log: Optional[Logger] = None,
                        pre_sync: bool = False, max_rounds: int = 5, reason: str = "inline",
                        session_id: str = "", enqueue: bool = True) -> List[Dict[str, Any]]:
    """同步跑完所有 target（不 spawn）。每 root：請求落 `.req/` → 取鎖（取不到即退出，持鎖者會消費）→
    每輪領取全部請求（含 inflight 殘留）跑一次，成功才刪 → `.req/` 又有新檔就再跑 → 釋鎖後再查一次，
    有新請求就重新取鎖接手。"""
    log = log or _default_log
    vs = vcs_sync_config(config)
    env = worker_env()
    results: List[Dict[str, Any]] = []
    for t in targets:
        if enqueue:
            write_request(t.root, t.pathspecs, retired_paths, reason, session_id, t.mem_dirs)
        if not acquire_lock(t.root):
            log(f"[{t.vcs}] {t.root}: 他 worker 持鎖，請求已落 .req/ 交由持鎖者補跑")
            results.append({"vcs": t.vcs, "root": t.root.as_posix(), "status": "locked",
                            "pending": pending_requests(t.root)})
            continue
        rounds = 0
        res: Dict[str, Any] = {"vcs": t.vcs, "root": t.root.as_posix(), "status": "ok", "committed": 0}
        try:
            while True:
                req, claimed = claim_requests(t.root)
                merged, merged_retired = _merge_target(t, req)
                for p in retired_paths:
                    if p not in merged_retired:
                        merged_retired.append(p)
                res = _sync_root_once(merged, vs, env, log, merged_retired, pre_sync)
                if res.get("status") == "ok":
                    ack_requests(claimed)   # 失敗／跳過的請求留在 inflight，下個持鎖者重做
                rounds += 1
                res["rounds"] = rounds
                if pending_requests(t.root) and rounds < max_rounds:
                    continue
                release_lock(t.root)
                # 釋鎖前後的縫隙：別人剛被鎖拒、請求已落檔 → 這裡接回來補跑
                if pending_requests(t.root) and rounds < max_rounds and acquire_lock(t.root):
                    continue
                if pending_requests(t.root):
                    log(f"[{t.vcs}] {t.root}: 已達 {max_rounds} 輪上限，剩餘請求留給下個 worker")
                break
        finally:
            release_lock(t.root)
        results.append(res)
    return results
