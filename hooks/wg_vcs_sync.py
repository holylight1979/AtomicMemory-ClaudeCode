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

拉（git：commit → 拉 → push；開關 `vcs_sync.pull.enabled`，與 push 開關獨立）：
  fetch 後一次固定 H（本地分支）／U（FETCH_HEAD），之後 rev-list／diff-tree／update-ref／restore 全用這兩個 OID。
  incoming 逐 commit 分類：全部路徑在記憶 pathspec 內且不被 exclude 才是「純記憶」（merge commit 一律非純）。
  - ahead=0 ∧ 純記憶 → 「ref＋pathspec 同步」：記憶路徑乾淨才 `update-ref`（CAS）＋ `restore --source=U --staged
    --worktree -- <pathspecs>`——主工作樹只有記憶路徑的 index／工作樹被對齊，其他路徑零觸碰。用 restore 而非
    `checkout U -- <pathspecs>`：checkout 不會刪上游已刪的檔，留下反向 staged 的新增。
  - ahead=0 ∧ 含非記憶 → 整樹乾淨（status -uno 空）才 `merge --ff-only`（顯式關 autoStash）。
  - ahead>0 → 本地 ahead 純記憶 ∧ incoming 純記憶 ∧ 記憶路徑乾淨才在隔離暫時 worktree 做 rebase（主工作樹不
    rebase：鎖擋不住他 session 同時寫檔，autostash 也不是完整交易）；衝突只接受索引檔（check-attr merge=atomindex）
    且由 merge-atom-index.py --resolve 解開，否則 abort 丟棄。成功後主 repo 只 update-ref（CAS）＋記憶 pathspec restore。
  任何不能自動併入的情況落 `.behind` 標記（JSON：reason/at）+ roots.json pull_error，下個 SessionStart advisory 浮出；
  fetch 失敗只記標記、不影響既有 push 段。拉入的 atom 下一個 session 才進候選池。
  update-ref 之前先驗 symbolic HEAD 仍在該 branch 且 HEAD==H、restore 之前再驗 symbolic HEAD（他 session 中途切分支
  就不動）；update-ref 之前落 `<hash>.recover.json`（branch/from/to/pathspecs），restore 成功才刪：ref 已換但 restore
  失敗時，下輪開頭（拒跑檢查之後、commit 之前）先重跑 restore，仍失敗 → 本輪不 commit 不 push（否則上游新增的
  atom 會被當成本地刪除提交），留下 recover 的那一輪也不 push；切到別的分支也一樣，記憶路徑相對目前 HEAD 乾淨才算已
  對齊。restore 前逐檔擋「恢復／整合期間的新編輯」（檔既非 from 版也非目標版就不覆蓋；未追蹤檔與目標樹新增檔同名也算），
  HEAD 已前進到 to 的後代則以 HEAD 為源；index.lock 重試的每次嘗試都重驗這些條件。
  SessionStart 的 reason=pull 請求：last_pull 在 `pull.cooldown_s` 內且記憶路徑無本地變更 → 跳過拉段（多 session 連開
  不重複 fetch）；advisory「拉入 N 筆」靠 roots.json pull_reported_at 只報一次。
  svn：`svn_update_targets` 先 schedule-delete 已驗證退役的 missing，其他 missing 不自動 update（會把檔補回）；
  update 後只有索引檔的 text 衝突交 resolver，其餘衝突停止本輪。
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import locale
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from wg_core import (
    CLAUDE_DIR, WORKFLOW_DIR, _now_iso, _atom_debug_error,
    append_guard_log, find_project_root, find_vcs_root, load_config, org_memory_root,
)

SYNC_DIR = WORKFLOW_DIR / "vcs-sync"
LOG_PATH = CLAUDE_DIR / "Logs" / "vcs-sync.log"
LEDGER_DIR = WORKFLOW_DIR / "harvest-ledger"

DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "push": True,
    "root_pathspecs": ["memory", "_AIDocs/_atoms"],
    "project_pathspecs": [".claude/memory"],
    "org_extra_pathspecs": ["usage-snapshots"],
    "exclude": ["**/*.access.json"],
    "timeout_s": 60,
    "pull": {"enabled": True, "fetch_timeout_s": 20, "cooldown_s": 600},
}

# 索引檔（merge driver atomindex 管的那幾個）：拉取時唯一允許自動解衝突的檔名
INDEX_FILE_NAMES = {"MEMORY.md", "_ATOM_INDEX.md", "_atom_index.json", "_INDEX.md", "_local_catalog.md"}

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
    pull = dict(DEFAULTS["pull"])
    pull.update(merged.get("pull") or {})
    merged["pull"] = pull
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
    # 公司層記憶 repo（config org_memory）：與專案層同 pathspec；已是當前專案根就不重複
    org = org_memory_root()
    if org and org.is_dir() and all(org.resolve() != b.resolve() for b, _s in bases):
        bases.append((org, vs["project_pathspecs"]))

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
    # 公司層 repo 另收非記憶路徑（週用量截圖）：只進 pathspec（算純記憶 commit、一起自動推拉），不進 mem_dirs（無索引）。
    # git 不要求本機已有該目錄（上游先有時要能拉進來）；svn 對不存在的路徑會報錯，目錄在才收。
    org_t = targets.get(org.resolve().as_posix().lower()) if org and org.is_dir() else None
    if org_t:
        for spec in vs["org_extra_pathspecs"]:
            if spec not in org_t.pathspecs and (org_t.vcs == "git" or (org_t.root / spec).is_dir()):
                org_t.pathspecs.append(spec)
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


def write_behind(root: Path, reason: str) -> None:
    """`.behind`：上游有東西沒併進本地（fetch 失敗／含程式碼 commit 且樹髒／分叉不可自動 rebase／svn 衝突）。
    與 `.unpushed` 分開：一個是「拉不進來」、一個是「推不出去」，解法與清除時機都不同。"""
    rec = {"reason": (reason or "").strip().replace("\n", " ")[:500], "at": _now_iso()}
    _atomic_write(marker_path(root, "behind"), json.dumps(rec, ensure_ascii=False) + "\n")


def clear_behind(root: Path) -> None:
    try:
        marker_path(root, "behind").unlink()
    except OSError:
        pass


def read_behind_record(root: Path) -> Optional[Dict[str, Any]]:
    try:
        rec = json.loads(marker_path(root, "behind").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def recover_path(root: Path) -> Path:
    return marker_path(root, "recover.json")


def write_recover(root: Path, branch: str, from_oid: str, to_oid: str, pathspecs: Sequence[str]) -> None:
    """`.recover.json`：update-ref 之前落檔，restore 成功才刪；留著＝ref 已指向 to 但記憶路徑的 index／工作樹還在 from。"""
    rec = {"branch": branch, "from": from_oid, "to": to_oid, "pathspecs": list(pathspecs), "at": _now_iso()}
    _atomic_write(recover_path(root), json.dumps(rec, ensure_ascii=False) + "\n")


def clear_recover(root: Path) -> None:
    try:
        recover_path(root).unlink()
    except OSError:
        pass


def read_recover(root: Path) -> Optional[Dict[str, Any]]:
    try:
        rec = json.loads(recover_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def load_roots() -> Dict[str, Any]:
    try:
        return json.loads((SYNC_DIR / "roots.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


_UNSET: Any = object()   # update_root_record：「沒傳」≠「設成 None」，push 側與 pull 側欄位互不清除


def update_root_record(target: SyncTarget, *, last_sync: Optional[str] = None,
                       last_error: Any = _UNSET, touch_sync: bool = False,
                       last_pull: Any = _UNSET, pulled_commits: Any = _UNSET,
                       pull_error: Any = _UNSET, pull_reported_at: Any = _UNSET) -> bool:
    """roots.json 讀改寫包在 roots.lock（OS 互斥）內：多 root worker 並行時不互相蓋掉對方的紀錄。
    選單檔＋共用鎖而非每 root 一檔：SessionStart 只讀一個 map，hash↔路徑對照留在同一處。
    等鎖逾時 → 不進讀改寫、記 log、回 False：無鎖寫入會把別人剛寫的紀錄整份蓋掉，少一筆比錯一份好。
    欄位分兩組：last_sync／last_error 是 commit+push 的；last_pull／pulled_commits／pull_error／pull_reported_at 是拉的
    （pull_reported_at＝advisory 已報過的 last_pull，同一次拉入只報一次）。
    只寫有傳的欄位：pull 失敗不得清掉 push 的 last_error，反之亦然。"""
    lk = FileLock(SYNC_DIR / "roots.lock")
    if not lk.acquire(wait_s=3.0):
        msg = f"roots.lock 取鎖逾時，略過 roots.json 更新: {target.root.as_posix()}"
        _default_log(msg)
        _atom_debug_error("vcs_sync:roots_lock", TimeoutError(msg))
        return False
    try:
        roots = load_roots()
        key = target.root.as_posix()
        rec = roots.get(key) or {"vcs": target.vcs, "pathspecs": [], "last_sync": None, "last_error": None,
                                 "last_pull": None, "pulled_commits": 0, "pull_error": None}
        rec["vcs"] = target.vcs
        rec["pathspecs"] = list(target.pathspecs)
        if touch_sync:
            rec["last_sync"] = last_sync or _now_iso()
        for name, val in (("last_error", last_error), ("last_pull", last_pull),
                          ("pulled_commits", pulled_commits), ("pull_error", pull_error),
                          ("pull_reported_at", pull_reported_at)):
            if val is not _UNSET:
                rec[name] = val
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
    """本 root 失敗，須留 `.unpushed` 標記；git 路徑補上當時 HEAD 供 advisory 判已解決，與已跑完的拉段結果。"""

    head_oid: Optional[str] = None
    pull: Optional[Dict[str, Any]] = None


def _run(cmd: List[str], cwd: Path, timeout: float, env: Dict[str, str],
         text: bool = True) -> subprocess.CompletedProcess:
    kw: Dict[str, Any] = {"capture_output": True, "timeout": timeout, "env": env, "cwd": str(cwd)}
    if text:
        kw.update(text=True, encoding="utf-8", errors="replace")
    return subprocess.run(cmd, **kw, **_NO_WINDOW)


def _run_index_tools(target: SyncTarget, timeout: float, env: Dict[str, str], log: Logger,
                     tool_args: Sequence[List[str]]) -> None:
    """對每個有 _atom_index.json 的記憶目錄跑 tools/ 下的索引工具；`--write` 者失敗即 _Stop（半套索引不能
    進版控），其餘（--check）漂移只記 log。"""
    tools = CLAUDE_DIR / "tools"
    for mem in target.mem_dirs:
        if not (mem / "_atom_index.json").exists():
            continue
        for args in tool_args:
            script = tools / args[0]
            if not script.exists():
                continue
            must_pass = "--write" in args
            try:
                r = _run([sys.executable, str(script), *args[1:], "--memory-dir", str(mem)], CLAUDE_DIR, timeout, env)
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


def _sync_indexes(target: SyncTarget, timeout: float, env: Dict[str, str], log: Logger) -> None:
    """提交前把 atom 與索引拉到同一快照：sync-memory-index --write（必過）＋ sync-atom-index --check（只記 log）。"""
    _run_index_tools(target, timeout, env, log,
                     (["sync-memory-index.py", "--write"], ["sync-atom-index.py", "--check"]))


def _index_check(target: SyncTarget, timeout: float, env: Dict[str, str], log: Logger) -> None:
    """拉入後只查漂移不改檔：拉進來的索引是對方機器產的，本機不在這裡重寫（下個 commit 前的 --write 會對齊）。"""
    _run_index_tools(target, timeout, env, log, (["sync-atom-index.py", "--check"],))


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
    r = git("ls-files", "-u")
    if r.returncode != 0:
        raise _Skip(f"ls-files -u 失敗 rc={r.returncode}，無法確認是否有未解衝突: {(r.stderr or '').strip()[:120]}")
    if (r.stdout or "").strip():
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


def _git_changed_files(git, t: SyncTarget, exclude: Sequence[str]) -> List[Tuple[str, str]]:
    """pathspec 內實際變更檔（含 untracked；-uall 展開目錄）過濾 exclude 與 ignored → add/commit 共用的允許集合。
    回 [(xy, path)]：xy 是 porcelain 兩欄狀態（X＝index 對 HEAD、Y＝工作樹對 index），add 段靠它分辨
    「已 staged、工作樹乾淨」的項（如前一輪 add 已 stage 的刪除）——那種 path 已不在工作樹也不在 index，
    再 add 會 rc=128「did not match any files」，只能直接進 commit pathspec。"""
    r = git("status", "--porcelain", "-z", "-uall", "--", *t.pathspecs)
    if r.returncode != 0:
        raise _Stop(f"git status 失敗: {(r.stderr or '').strip()[:200]}")
    entries: List[Tuple[str, str]] = []
    seen: set = set()
    for xy, path in _parse_porcelain_z(r.stdout or ""):
        if xy == "!!" or not path:
            continue
        if not _under_pathspecs(path, t.pathspecs) or _excluded(path, exclude):
            continue
        if path in seen:
            continue
        seen.add(path)
        entries.append((xy, path))
    return entries


def _git_retry_lock(git):
    def git_retry_lock(*args: str) -> subprocess.CompletedProcess:
        """index.lock 競態（他 session 正在 commit）→ 重試 ≤3，每次 sleep 1。"""
        r = git(*args)
        for _ in range(2):
            if r.returncode == 0 or "index.lock" not in (r.stderr or ""):
                break
            time.sleep(1)
            r = git(*args)
        return r
    return git_retry_lock


def _git_on_branch(git, branch: str, head: Optional[str] = None) -> bool:
    """symbolic HEAD 仍是 refs/heads/<branch>（且 HEAD==head）：他 session 中途 checkout 別的分支就不能動 ref／工作樹。"""
    cur = (git("symbolic-ref", "-q", "HEAD").stdout or "").strip()
    if cur != f"refs/heads/{branch}":
        return False
    if head is not None and (git("rev-parse", "HEAD").stdout or "").strip() != head:
        return False
    return True


def _git_mem_diff_files(git, tree: str, specs: Sequence[str]) -> Optional[set]:
    """記憶 pathspec 內「工作樹或 index 與 tree 不同」的檔集合（含已 stage 的新增／刪除；未追蹤檔不在 index，diff 看不到，
    另由 _git_untracked_clash 擋）。git 失敗 → None（不可判定，呼叫端當成不乾淨）。"""
    out: set = set()
    for extra in ((), ("--cached",)):
        r = git("diff", "--name-only", "-z", *extra, tree, "--", *specs)
        if r.returncode != 0:
            return None
        out.update(x for x in (r.stdout or "").split("\0") if x)
    return out


def _git_untracked_clash(git, frm: str, to: str, specs: Sequence[str]) -> Optional[set]:
    """記憶 pathspec 內的未追蹤檔 ∩ frm→to 新增的檔：restore --worktree 會直接拿 to 版蓋掉它（diff 看不到未追蹤檔）。
    git 失敗 → None。"""
    r = git("ls-files", "--others", "--exclude-standard", "-z", "--", *specs)
    if r.returncode != 0:
        return None
    untracked = {x for x in (r.stdout or "").split("\0") if x}
    if not untracked:
        return set()
    r = git("diff-tree", "-r", "--name-only", "--diff-filter=A", "-z", frm, to, "--", *specs)
    if r.returncode != 0:
        return None
    return untracked & {x for x in (r.stdout or "").split("\0") if x}


def _git_new_edits(git, frm: str, to: str, specs: Sequence[str]) -> Optional[List[str]]:
    """restore 前的新編輯偵測：每個檔要嘛還是 frm 版、要嘛已是 to 版，兩者皆非＝恢復／整合期間有人改了它，restore 會
    把編輯蓋掉。逐檔比而非整樹比：他 session 在 ref 前進後又 commit（to 之後代）時，他改的檔≠frm、上游新增的檔≠to，
    整樹比會兩邊都不等而誤判。另加未追蹤檔與 to 新增檔同名的情況（frm==to 時不存在）。回不合格檔清單；frm==to 時就是
    「相對該樹不乾淨」的檔；git 失敗 → None。"""
    a = _git_mem_diff_files(git, frm, specs)
    b = a if frm == to else _git_mem_diff_files(git, to, specs)
    if a is None or b is None:
        return None
    bad = a & b
    if frm != to:
        clash = _git_untracked_clash(git, frm, to, specs)
        if clash is None:
            return None
        bad |= clash
    return sorted(bad)


def _git_restore_mem(git, branch: str, frm: str, to: str, specs: Sequence[str]) -> Optional[str]:
    """`.recover.json` 包住的那一步：把記憶 pathspec 的 index／工作樹從 frm 對齊到 ref 已指向的 to。
    symbolic HEAD 仍在 branch 才動；HEAD==to 以 to 為源，HEAD 是 to 的後代（他 session 在 ref 前進後又 commit）以 HEAD
    為源（對齊回 to 會把那筆 commit 的記憶改動反向 staged），其他情況交人。restore 前擋新編輯（_git_new_edits）。
    index.lock 競態重試 ≤3（每次 sleep 1）：等待期間他 session 可能改檔或 commit，所以每次嘗試都重驗分支、重算 source、
    重擋新編輯，任一不過就停止重試。回 None＝已對齊；否則回理由，recover 檔由呼叫端留著。"""
    for attempt in range(3):
        if attempt:
            time.sleep(1)
        if not _git_on_branch(git, branch):
            return f"分支已切換（HEAD 不在 {branch}，ref 已指向 {to[:8]}）"
        head = (git("rev-parse", "HEAD").stdout or "").strip()
        src = to
        if head != to:
            if not head or git("merge-base", "--is-ancestor", to, head).returncode != 0:
                return f"{branch} 已離開 {to[:8]}（現 {head[:8] or '?'}，非其後代），待人處理"
            src = head
        edits = _git_new_edits(git, frm, src, specs)
        if edits is None:
            return "git diff 失敗，無法確認記憶路徑有無未提交編輯"
        if edits:
            return f"記憶路徑有未提交編輯（{edits[0]}），待人處理"
        # src 與 index 都沒有檔的 pathspec（如尚無人放過截圖的 usage-snapshots）：restore 會 rc≠0「did not match」，無事可做故略過
        live = [s for s in specs if (git("ls-tree", "--name-only", src, "--", s).stdout or "").strip()
                or (git("ls-files", "--", s).stdout or "").strip()]
        if not live:
            return None
        r = git("restore", f"--source={src}", "--staged", "--worktree", "--", *live)
        if r.returncode == 0:
            return None
        if "index.lock" not in (r.stderr or ""):
            break
    return f"restore --source={src[:8]} 失敗: {(r.stderr or '').strip()[:160]}"


def _git_recover(t: SyncTarget, vs: Dict[str, Any], env: Dict[str, str], log: Logger) -> None:
    """上輪 update-ref 成功但 restore 失敗留下的 `.recover.json`：恢復完成才刪，否則 `.behind` + _Skip——recover 在時任何
    分支都不得 commit／push（index 還是 from 的記憶樹，commit 會把上游新增的 atom 當成本地刪除提交）。
    仍在該 branch → 重跑 _git_restore_mem；HEAD 已在別的分支 → index／工作樹跟著切過去了，記憶路徑相對目前 HEAD 乾淨
    才算已對齊（刪檔），否則交人：手動 restore 後再跑。"""
    rec = read_recover(t.root)
    if not rec:
        return
    git = _git_cmd(t, vs, env)
    branch, to, frm = str(rec.get("branch") or ""), str(rec.get("to") or ""), str(rec.get("from") or "")
    specs = list(rec.get("pathspecs") or t.pathspecs)
    cur = (git("symbolic-ref", "-q", "HEAD").stdout or "").strip()
    if not branch or not to or cur != f"refs/heads/{branch}":
        r = git("status", "--porcelain", "-z", "-uno", "--", *specs)
        if r.returncode == 0 and not (r.stdout or "").strip("\0"):
            clear_recover(t.root)
            log(f"[git] {t.root}: HEAD 已不在 {branch or '?'} 且記憶路徑乾淨，放棄記憶路徑恢復（已對齊）")
            return
        reason = (f"記憶路徑恢復未完成（分支已切換，HEAD 不在 {branch or '?'}）；請手動 "
                  f"git restore --source=HEAD --staged --worktree -- {' '.join(specs)} 後刪除 {recover_path(t.root).name}")
    else:
        fail = _git_restore_mem(git, branch, frm or to, to, specs)
        if fail is None:
            clear_recover(t.root)
            log(f"[git] {t.root}: 記憶路徑恢復完成（對齊 {to[:8]}）")
            return
        reason = f"記憶路徑恢復未完成：{fail}"
    log(f"[git] {t.root}: {reason}")
    write_behind(t.root, reason)
    update_root_record(t, pull_error=reason)
    raise _Skip(reason)


def _git_sync(t: SyncTarget, vs: Dict[str, Any], env: Dict[str, str], log: Logger,
              branch: str, config: Optional[Dict[str, Any]] = None, reasons: Sequence[str] = ()) -> Dict[str, Any]:
    git = _git_cmd(t, vs, env)
    timeout = float(vs.get("timeout_s", 60))
    try:
        return _git_sync_body(t, vs, git, _git_retry_lock(git), log, branch, timeout, env, config or {}, reasons)
    except _Stop as e:
        e.head_oid = (git("rev-parse", "HEAD").stdout or "").strip() or None
        raise


def _pull_in_cooldown(t: SyncTarget, vs: Dict[str, Any], reasons: Sequence[str]) -> bool:
    """本輪全部請求都是 SessionStart 的 reason=pull 且 roots.json last_pull 在 pull.cooldown_s 內 → 不必再 fetch。
    呼叫端另外要求記憶路徑無本地變更（有變更就要 commit→拉→push 走完整流程）。"""
    if not reasons or any(r != "pull" for r in reasons):
        return False
    cooldown = float((vs.get("pull") or {}).get("cooldown_s", 600) or 0)
    if cooldown <= 0:
        return False
    last = (load_roots().get(t.root.as_posix()) or {}).get("last_pull")
    if not last:
        return False
    try:
        dt = datetime.fromisoformat(str(last))
        if dt.tzinfo is None:
            dt = dt.astimezone()
        age = (datetime.now(timezone.utc) - dt).total_seconds()
    except (ValueError, TypeError, OSError, OverflowError):
        return False
    return 0 <= age < cooldown


def _git_upstream(git, branch: str) -> Optional[Tuple[str, str]]:
    """分支的 (remote, remoteref)；無 upstream → None。"""
    r = git("for-each-ref", "--format=%(upstream:remotename) %(upstream:remoteref)", f"refs/heads/{branch}")
    parts = (r.stdout or "").split()
    if r.returncode != 0 or len(parts) != 2:
        return None
    return parts[0], parts[1]


def _foreign_commit(git, t: SyncTarget, exclude: Sequence[str], rng: str) -> Optional[str]:
    """`rng`（a..b）內第一個「非純記憶」commit 的描述；全部純記憶 → None。
    非純記憶 ＝ merge commit，或任一路徑不在 pathspec 內／被 exclude（exclude 的檔如 memory/_meta/** 設定檔只會由
    使用者手動 commit，出現就表示有人為 commit 在等上GIT）。git 失敗 → _Stop（無法確認歷史就不動）。"""
    r = git("rev-list", "--parents", rng)
    if r.returncode != 0:
        raise _Stop(f"rev-list {rng[:40]} 失敗: {(r.stderr or '').strip()[:200]}")
    for ln in (r.stdout or "").splitlines():
        fields = ln.split()
        if not fields:
            continue
        sha = fields[0]
        if len(fields) > 2:
            return f"merge commit {sha[:8]}"
        r = git("diff-tree", "--no-commit-id", "--name-only", "-z", "-r", "--root", sha)
        if r.returncode != 0:
            raise _Stop(f"diff-tree {sha[:8]} 失敗，無法確認歷史: {(r.stderr or '').strip()[:120]}")
        foreign = [f for f in (r.stdout or "").split("\0")
                   if f and (not _under_pathspecs(f, t.pathspecs) or _excluded(f, exclude))]
        if foreign:
            return f"非記憶 commit {sha[:8]}（{foreign[0]}）"
    return None


class _Behind(Exception):
    """拉段：上游有東西沒併進來（本輪不自動併入）；訊息落 `.behind` + roots.json pull_error，不影響 push 段。"""


class _RecoverPending(_Behind):
    """update-ref 已成功但 restore 失敗、`.recover.json` 留著：index 還是舊記憶樹，本輪連 push 也不做。"""


def _git_pull(t: SyncTarget, vs: Dict[str, Any], git, git_retry_lock, log: Logger, branch: str,
              env: Dict[str, str], config: Dict[str, Any]) -> Dict[str, Any]:
    """拉段（見檔頭）。回 {"status": up-to-date|pulled|behind|no-upstream, "pulled_commits", "reason"}；
    自己吞掉所有失敗（記 log／`.behind`／pull_error），永不讓 commit+push 段跟著死。"""
    root = t.root
    exclude = vs.get("exclude", [])
    pull_cfg = vs.get("pull") or {}
    fetch_to = float(pull_cfg.get("fetch_timeout_s", 20))
    res: Dict[str, Any] = {"status": "behind", "pulled_commits": 0, "reason": None, "recover_pending": False}
    try:
        up = _git_upstream(git, branch)
        if up is None:
            log(f"[git] {root}: {branch} 無 upstream，不拉")
            res["status"] = "no-upstream"
            return res
        remote, remoteref = up
        try:
            r = git("-c", "fetch.prune=false", "fetch", "--quiet", remote, remoteref, to=fetch_to)
        except subprocess.TimeoutExpired:
            raise _Behind(f"fetch 逾時 {fetch_to:g}s（{remote} {remoteref}）")
        if r.returncode != 0:
            raise _Behind(f"fetch 失敗: {(r.stderr or r.stdout).strip()[-200:]}")
        # 固定 OID：之後的歷史檢查、CAS 與 restore 都用這組，不用 @{u}（fetch 後別人再 fetch 也不會換掉比較基準）
        head = (git("rev-parse", "--verify", "-q", f"refs/heads/{branch}").stdout or "").strip()
        upstream = (git("rev-parse", "--verify", "-q", "FETCH_HEAD").stdout or "").strip()
        if not head or not upstream:
            raise _Behind("fetch 後 HEAD／FETCH_HEAD 不可解析")
        behind = (git("rev-list", "--count", f"{head}..{upstream}").stdout or "").strip()
        ahead = (git("rev-list", "--count", f"{upstream}..{head}").stdout or "").strip()
        if not behind.isdigit() or not ahead.isdigit():
            raise _Behind("rev-list --count 失敗")
        n_behind, n_ahead = int(behind), int(ahead)
        if n_behind == 0:
            clear_behind(root)
            update_root_record(t, last_pull=_now_iso(), pulled_commits=0, pull_error=None)
            res["status"] = "up-to-date"
            return res

        incoming_foreign = _foreign_commit(git, t, exclude, f"{head}..{upstream}")
        r = git("status", "--porcelain", "-z", "--", *t.pathspecs)
        if r.returncode != 0:
            raise _Behind(f"git status 失敗: {(r.stderr or '').strip()[:120]}")
        mem_dirty = [p for _xy, p in _parse_porcelain_z(r.stdout or "") if p]
        if n_ahead == 0 and incoming_foreign is None:
            if mem_dirty:
                raise _Behind(f"上游 {n_behind} 筆純記憶 commit，但本地記憶路徑有未提交改動（{mem_dirty[0]}）")
            _git_cas_and_restore(t, git, branch, upstream, head)
            log(f"[git] {root}: 拉入 {n_behind} 筆純記憶 commit（ref＋pathspec 同步 {head[:8]}→{upstream[:8]}）")
        elif n_ahead == 0:
            r = git("status", "--porcelain", "-uno")
            if r.returncode != 0:
                raise _Behind(f"git status 失敗: {(r.stderr or '').strip()[:120]}")
            if (r.stdout or "").strip():
                raise _Behind(f"上游含{incoming_foreign}且本地有未提交改動，不自動 ff；請自行 git pull")
            if not _git_on_branch(git, branch, head):
                raise _Behind(f"分支已切換（HEAD 不在 {branch}@{head[:8]}），本輪不 ff")
            r = git_retry_lock("-c", "merge.autoStash=false", "merge", "--ff-only", "--no-edit", "--quiet", upstream)
            if r.returncode != 0:
                raise _Behind(f"ff-only 失敗: {(r.stderr or r.stdout).strip()[-160:]}")
            log(f"[git] {root}: 拉入 {n_behind} 筆 commit（含{incoming_foreign}；整樹乾淨 ff-only）")
        else:
            local_foreign = _foreign_commit(git, t, exclude, f"{upstream}..{head}")
            if local_foreign is not None:
                raise _Behind(f"分叉：本地 ahead {n_ahead} 筆含{local_foreign}，不自動 rebase；請自行 git pull --rebase")
            if incoming_foreign is not None:
                raise _Behind(f"分叉：上游 {n_behind} 筆含{incoming_foreign}，不自動 rebase；請自行 git pull --rebase")
            if mem_dirty:
                raise _Behind(f"分叉：本地記憶路徑有未提交改動（{mem_dirty[0]}），不自動 rebase")
            new_head = _git_isolated_rebase(t, vs, git, log, head, upstream, n_ahead, env)
            _git_cas_and_restore(t, git, branch, new_head, head)
            log(f"[git] {root}: 分叉純記憶，隔離 worktree rebase 成功 {head[:8]}→{new_head[:8]}（拉入 {n_behind} 筆）")
        _after_pull(t, vs, env, log, config)
        clear_behind(root)
        update_root_record(t, last_pull=_now_iso(), pulled_commits=n_behind, pull_error=None)
        res.update(status="pulled", pulled_commits=n_behind)
        return res
    except (_Behind, _Stop) as e:
        reason = str(e)[:300]
        res["recover_pending"] = isinstance(e, _RecoverPending)
    except subprocess.TimeoutExpired as e:
        reason = f"拉段子行程逾時 {e.timeout}s: {' '.join(map(str, e.cmd))[:120]}"
    except (OSError, subprocess.SubprocessError) as e:
        reason = f"拉段 {type(e).__name__}: {e}"[:200]
    # 兜底：只要 recover 檔還在（ref 已換、記憶路徑未對齊），不論是哪種例外跳出來，都不得進 push
    if recover_path(root).exists():
        res["recover_pending"] = True
    log(f"[git] {root}: 落後未併入 — {reason}")
    write_behind(root, reason)
    update_root_record(t, pull_error=reason)
    res["reason"] = reason
    return res


def _git_cas_and_restore(t: SyncTarget, git, branch: str, new: str, old: str) -> None:
    """主 repo 的唯一寫入：`update-ref`（CAS：分支仍指向 old 才換成 new，否則別人動過、放棄本輪）＋
    記憶 pathspec 的 index／工作樹對齊到 new（restore --source 會刪 new 沒有的已追蹤檔，不留反向 staged）。
    update-ref 前驗 symbolic HEAD 在 branch 且 HEAD==old（CAS 只保護 ref，擋不住中途 checkout 別的分支），並重驗記憶
    路徑相對 old 乾淨（隔離 rebase 跑的期間他 session 可能已改記憶檔）；restore 那一步交 _git_restore_mem（再驗分支、
    HEAD 前進、新編輯）。`.recover.json` 包住 update-ref→restore，restore 成功才刪。"""
    specs = t.pathspecs
    if not _git_on_branch(git, branch, old):
        raise _Behind(f"分支已切換（HEAD 不在 {branch}@{old[:8]}），本輪不動 ref")
    edits = _git_new_edits(git, old, old, specs)
    if edits is None:
        raise _Behind("git diff 失敗，無法確認記憶路徑是否乾淨，本輪不動 ref")
    if edits:
        raise _Behind(f"記憶路徑有未提交編輯（{edits[0]}），本輪不動 ref")
    write_recover(t.root, branch, old, new, specs)
    r = git("update-ref", f"refs/heads/{branch}", new, old)
    if r.returncode != 0:
        clear_recover(t.root)
        raise _Behind(f"update-ref CAS 失敗（分支已被他人移動）: {(r.stderr or '').strip()[:120]}")
    try:
        fail = _git_restore_mem(git, branch, old, new, specs)
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError) as e:
        # ref 已換、restore 連跑都沒跑完：和「回傳失敗」同一種半套狀態，必須同樣禁 push、留 recover
        fail = f"{type(e).__name__}: {e}"[:160]
    if fail is not None:
        # ref 已換、工作樹沒跟上：不回退 ref（reflog 可查）；recover 檔留著，下輪開頭先重跑恢復再談 commit
        raise _RecoverPending(f"restore 記憶路徑失敗（分支已指向 {new[:8]}，下輪自動重試恢復；手動：git restore "
                              f"--source=HEAD --staged --worktree -- {' '.join(specs)}）: {fail}")
    clear_recover(t.root)


def _git_isolated_rebase(t: SyncTarget, vs: Dict[str, Any], git, log: Logger, head: str, upstream: str,
                         n_ahead: int, env: Dict[str, str]) -> str:
    """暫時 worktree（detach 在 head）內 `rebase upstream`；衝突迴圈有界 ≤ n_ahead+1：每個本地 commit 重放時最多停
    一次衝突（n_ahead 次「解衝突＋--continue」），最後一次 --continue 的 rc 要再進一圈才被判成 0 而 break，所以多一圈。
    unmerged 檔全部 check-attr merge=atomindex 才交 merge-atom-index.py --resolve，成功（rc 0、error null、
    remaining 空、ls-files -u 空）才 --continue；否則 abort。回 rebase 後的 HEAD。
    worktree add 也在 try 內：任何路徑（含 add 半途失敗）都走 _git_worktree_cleanup，殘留就 _Behind（理由含路徑）。"""
    timeout = float(vs.get("timeout_s", 60))
    # resolve：Windows 的 gettempdir 可能是 8.3 短名，拿去跟 `worktree list` 印的長名比對會對不上
    tmp = Path(tempfile.gettempdir()).resolve() / f"vcs-sync-wt-{uuid.uuid4().hex[:10]}"
    wt_env = dict(env)
    wt_env["GIT_EDITOR"] = "true"
    wt_env["GIT_SEQUENCE_EDITOR"] = "true"

    def wgit(*args: str) -> subprocess.CompletedProcess:
        return _run(["git", *args], tmp, timeout, wt_env)

    try:
        r = git("worktree", "add", "--detach", str(tmp), head)
        if r.returncode != 0:
            raise _Behind(f"worktree add 失敗: {(r.stderr or '').strip()[:160]}")
        r = wgit("rebase", "--quiet", upstream)
        for _ in range(n_ahead + 1):
            if r.returncode == 0:
                break
            unmerged = _git_unmerged(wgit)
            if not unmerged:
                raise _Behind(f"rebase 失敗（非衝突）: {(r.stderr or r.stdout).strip()[-160:]}")
            not_index = [p for p in unmerged if Path(p).name not in INDEX_FILE_NAMES]
            if not_index:
                raise _Behind(f"分叉衝突在非索引檔（{not_index[0]}），不自動解；請自行 git pull --rebase")
            chk = wgit("check-attr", "-z", "merge", "--", *unmerged)
            attrs = _parse_check_attr_z(chk.stdout or "")
            missing_attr = [p for p in unmerged if attrs.get(p) != "atomindex"]
            if chk.returncode != 0 or missing_attr:
                raise _Behind(f"衝突檔沒有 merge=atomindex 屬性（{(missing_attr or unmerged)[0]}），不自動解")
            rr = _run([sys.executable, str(CLAUDE_DIR / "tools" / "merge-atom-index.py"),
                       "--resolve", "--quiet", "--cwd", str(tmp)], tmp, timeout, wt_env)
            try:
                rep = json.loads((rr.stdout or "").strip().splitlines()[-1]) if (rr.stdout or "").strip() else {}
            except ValueError:
                rep = {}
            if rr.returncode != 0 or rep.get("error") or rep.get("remaining"):
                raise _Behind(f"索引 resolver 未解開（rc={rr.returncode} error={rep.get('error')} "
                              f"remaining={rep.get('remaining')}）")
            if _git_unmerged(wgit):
                raise _Behind("索引 resolver 回成功但仍有 unmerged 檔")
            r = wgit("rebase", "--continue")
        if r.returncode != 0:
            raise _Behind(f"rebase 衝突迴圈超過 {n_ahead + 1} 次仍未完成")
        new_head = (wgit("rev-parse", "HEAD").stdout or "").strip()
        if not new_head:
            raise _Behind("rebase 後 HEAD 不可解析")
        return new_head
    finally:
        leftover = _git_worktree_cleanup(git, wgit, tmp, log, t.root)
        if leftover:
            cur = sys.exc_info()[1]
            msg = f"暫時 worktree 殘留（{leftover}），請手動 git worktree remove --force 後 git worktree prune"
            raise _Behind(f"{cur}；{msg}" if isinstance(cur, _Behind) else msg)


def _norm_path(p: str) -> str:
    s = Path(p).as_posix()
    return s.lower() if sys.platform == "win32" else s


def _git_worktree_registered(git, tmp: Path) -> bool:
    r = git("worktree", "list", "--porcelain")
    if r.returncode != 0:
        return True   # 查不到就當還在：寧可多報殘留
    want = _norm_path(str(tmp))
    return any(_norm_path(ln[9:]) == want for ln in (r.stdout or "").splitlines() if ln.startswith("worktree "))


def _git_worktree_cleanup(git, wgit, tmp: Path, log: Logger, root: Path) -> Optional[str]:
    """abort 進行中的 rebase → `worktree remove --force`（rc≠0 重試 3 次、間隔 0.5s：Windows 檔鎖常是瞬時）→ prune →
    目錄殘骸 rmtree → 驗證目錄不存在且 `worktree list` 不含該路徑；仍殘留回路徑（呼叫端落 `.behind`）。"""
    if tmp.exists():
        try:
            wgit("rebase", "--abort")   # 沒在 rebase 中就 rc≠0，無害
        except (OSError, subprocess.SubprocessError):
            pass
    for attempt in range(3):
        if attempt:
            time.sleep(0.5)
        try:
            r = git("worktree", "remove", "--force", str(tmp))
        except (OSError, subprocess.SubprocessError) as e:
            log(f"[git] {root}: worktree remove 例外（第 {attempt + 1} 次）: {e}")
            continue
        if r.returncode == 0:
            break
        log(f"[git] {root}: worktree remove rc={r.returncode}（第 {attempt + 1} 次）: {(r.stderr or '').strip()[:120]}")
        if not _git_worktree_registered(git, tmp):
            break   # 從未登記成功（add 半途失敗）：remove 永遠失敗，直接 prune＋rmtree
    try:
        git("worktree", "prune")
    except (OSError, subprocess.SubprocessError) as e:
        log(f"[git] {root}: worktree prune 失敗: {e}")
    if tmp.exists():
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    if tmp.exists() or _git_worktree_registered(git, tmp):
        log(f"[git] {root}: 暫時 worktree 殘留 {tmp.as_posix()}")
        return tmp.as_posix()
    return None


def _parse_check_attr_z(out: str) -> Dict[str, str]:
    """`git check-attr -z <attr> -- paths` → {path: value}（NUL 分隔的 path/attr/value 三元組；路徑不經引號轉義）。"""
    toks = out.split("\0")
    res: Dict[str, str] = {}
    for i in range(0, len(toks) - 2, 3):
        res[toks[i]] = toks[i + 2]
    return res


def _git_unmerged(wgit) -> List[str]:
    """unmerged 檔列表；rc≠0 → _Behind（無法確認衝突集合就不能繼續解，呼叫端 abort＋清 worktree）。"""
    r = wgit("ls-files", "-u", "-z")
    if r.returncode != 0:
        raise _Behind(f"ls-files -u 失敗 rc={r.returncode}，無法確認衝突集合: {(r.stderr or '').strip()[:120]}")
    out: List[str] = []
    for ent in (r.stdout or "").split("\0"):
        if not ent or "\t" not in ent:
            continue
        p = ent.split("\t", 1)[1]
        if p not in out:
            out.append(p)
    return out


def _after_pull(t: SyncTarget, vs: Dict[str, Any], env: Dict[str, str], log: Logger,
                config: Dict[str, Any]) -> None:
    """拉成功後：向量增量索引（fail-open）＋ sync-atom-index --check（漂移只記 log）。"""
    try:
        from wg_atoms import _trigger_incremental_index
        _trigger_incremental_index(config)
    except Exception as e:  # noqa: BLE001 — 向量服務沒跑是常態
        log(f"[git] {t.root}: 向量增量索引未觸發: {type(e).__name__}: {e}")
    _index_check(t, float(vs.get("timeout_s", 60)), env, log)


def _git_sync_body(t: SyncTarget, vs: Dict[str, Any], git, git_retry_lock, log: Logger,
                   branch: str, timeout: float, env: Dict[str, str], config: Dict[str, Any],
                   reasons: Sequence[str] = ()) -> Dict[str, Any]:
    root = t.root
    exclude = vs.get("exclude", [])
    # ── add + commit：同一份允許路徑集合（`:(literal)` 防路徑被當 glob）──
    entries = _git_changed_files(git, t, exclude)
    files = [path for _, path in entries]
    specs = [f":(literal){f}" for f in files]
    # 只 add 工作樹仍與 index 不同的項（Y 欄非空白）；已 staged 的直接進 commit pathspec
    add_specs = [f":(literal){path}" for xy, path in entries if (xy + " ")[1] != " "]
    result: Dict[str, Any] = {"vcs": "git", "root": root.as_posix(), "committed": 0, "pushed": False,
                              "pull": {"status": "disabled", "pulled_commits": 0, "reason": None}}
    if add_specs:
        # -f：已追蹤但路徑被 .gitignore 蓋到的檔（如 memory/personal/ 下的 role.md）被刪除時，
        # 沒有 -f 的 add 會 rc≠0「paths are ignored」；add_specs 只含 status 列出的變更檔（!! 已濾），
        # 不會順手把被忽略的未追蹤檔加進來。
        r = git_retry_lock("add", "-A", "-f", "--", *add_specs)
        if r.returncode != 0:
            raise _Stop(f"git add 失敗: {(r.stderr or r.stdout).strip()[:200]}")
    if files:
        msg = f"chore(memory): knowledge harvest {date.today().isoformat()}（{len(files)} 檔）"
        r = git_retry_lock("commit", "-q", "-m", msg, "--", *specs)
        if r.returncode != 0:
            raise _Stop(f"git commit 失敗: {(r.stderr or r.stdout).strip()[:200]}")
        result["committed"] = len(files)
        log(f"[git] {root}: commit {len(files)} 檔")

    # ── 拉：在本地記憶 commit 之後、push 之前；失敗自己收，不影響 push 段 ──
    if (vs.get("pull") or {}).get("enabled", True):
        if not files and _pull_in_cooldown(t, vs, reasons):
            log(f"[git] {root}: reason=pull 在 cooldown 內且記憶路徑無變更，跳過拉段")
            result["pull"] = {"status": "cooldown", "pulled_commits": 0, "reason": None}
        else:
            result["pull"] = _git_pull(t, vs, git, git_retry_lock, log, branch, env, config)
    if result["pull"].get("recover_pending"):
        log(f"[git] {root}: 記憶路徑恢復未完成（recover 留著），本輪不 push")
        return result
    try:
        return _git_push(t, vs, git, log, branch, timeout, exclude, result)
    except _Stop as e:
        e.pull = result["pull"]   # push 段失敗時拉段結果一樣要回到 _sync_root_once
        raise


def _git_push(t: SyncTarget, vs: Dict[str, Any], git, log: Logger, branch: str, timeout: float,
              exclude: Sequence[str], result: Dict[str, Any]) -> Dict[str, Any]:
    """push 守門：head／upstream 一次固定（拉段整合後重新取），之後插進來的 commit 不在快照內。"""
    root = t.root
    if not vs.get("push", True):
        return result
    up = _git_upstream(git, branch)
    if up is None:
        log(f"[git] {root}: {branch} 無 upstream，不 push")
        return result
    remote, remoteref = up
    head = (git("rev-parse", "--verify", "-q", f"refs/heads/{branch}").stdout or "").strip()
    r = git("rev-parse", "--verify", "-q", f"{branch}@{{upstream}}")
    upstream = (r.stdout or "").strip()
    if not head or r.returncode != 0 or not upstream:
        log(f"[git] {root}: upstream ref 不可解析，不 push: {(r.stderr or '').strip()[:120]}")
        return result
    r = git("rev-list", "--count", f"{upstream}..{head}")
    n = (r.stdout or "").strip()
    if r.returncode != 0 or not n.isdigit():
        raise _Stop(f"rev-list 失敗: {(r.stderr or '').strip()[:200]}")
    if n == "0":
        clear_unpushed(root)
        return result
    foreign = _foreign_commit(git, t, exclude, f"{upstream}..{head}")
    if foreign:
        raise _Stop(f"待推歷史含{foreign}，本地有未發布的非記憶 commit，待使用者上GIT 一起推")
    r = git("push", "--quiet", remote, f"{head}:{remoteref}", to=timeout)
    if r.returncode != 0:
        raise _Stop(f"git push 被拒: {(r.stderr or r.stdout).strip()[-200:]}")
    result["pushed"] = True
    clear_unpushed(root)
    log(f"[git] {root}: push {n} commit ({head[:8]}) → {remote} {remoteref}")
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


def _svn_conflicts(stdout: bytes) -> List[Tuple[str, str]]:
    """status --xml → [(path, kind)]，kind ∈ text（item=conflicted）／property（props=conflicted）／tree。
    三類分開列：只有索引檔的 text 衝突能交 merge driver；property／tree 衝突驅動解不了。"""
    import xml.etree.ElementTree as ET
    if not stdout.strip():
        return []
    out: List[Tuple[str, str]] = []
    for ent in ET.fromstring(stdout).iter("entry"):
        ws = ent.find("wc-status")
        if ws is None:
            continue
        p = ent.get("path", "")
        if ws.get("item") == "conflicted":
            out.append((p, "text"))
        if ws.get("props") == "conflicted":
            out.append((p, "property"))
        if ws.get("tree-conflicted") == "true":
            out.append((p, "tree"))
    return out


def _rel_to(root: Path, p: str) -> Optional[str]:
    try:
        fp = Path(p)
        return (fp if fp.is_absolute() else root / fp).resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _svn_codes(stderr: bytes) -> set:
    return set(m.decode() for m in re.findall(rb"E\d{6}", stderr or b""))


def _svn_argv_encoding() -> str:
    """svn.exe 收 argv 用的 ANSI code page（GetACP；Python 的 UTF-8 mode 會讓 locale 回 utf-8，不能信）。"""
    if sys.platform != "win32":
        return "utf-8"
    try:
        import ctypes
        return f"cp{ctypes.windll.kernel32.GetACP()}"
    except (AttributeError, OSError):
        return locale.getpreferredencoding(False)


_SVN_ARGV_ENCODING = _svn_argv_encoding()


def _svn_argv_encodable(arg: str) -> bool:
    try:
        arg.encode(_SVN_ARGV_ENCODING)
        return True
    except UnicodeEncodeError:
        return False


class _Svn:
    """單 root 的 svn 呼叫包裝（_svn_check 與 _svn_sync 共用）。"""

    def __init__(self, t: SyncTarget, vs: Dict[str, Any], env: Dict[str, str]):
        self.root = t.root
        self.exe = _svn_exe()
        self.timeout = float(vs.get("timeout_s", 60))
        self.env = env

    def run(self, *args: str) -> subprocess.CompletedProcess:
        # Windows 的 svn.exe 以 ANSI code page 收 argv（`--targets` 檔同樣走原生編碼）：code page 外的字元會被
        # best-fit 成別的字（é→e）或 `?`，`add --parents` 便據此在磁碟建出亂碼目錄、delete 可能刪錯鄰居。
        # 編不出來的路徑不交給 svn，直接停並留下可讀理由（落 last_error／.unpushed，SessionStart advisory 浮出）。
        bad = next((a for a in args if not _svn_argv_encodable(a)), None)
        if bad is not None:
            raise _Stop(f"svn 無法定址（路徑含 {_SVN_ARGV_ENCODING} 外字元，請手動處理）: {bad}")
        return _run([self.exe, "--non-interactive", *args], self.root, self.timeout, self.env, text=False)

    @staticmethod
    def err(r: subprocess.CompletedProcess) -> str:
        raw = r.stderr or b""
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:   # svn.exe 的錯誤訊息走 ANSI code page（中文系統 cp950）
            text = raw.decode(_SVN_ARGV_ENCODING, "replace")
        lines = text.strip().splitlines()
        return lines[-1][:200] if lines else f"rc={r.returncode}"

    def status(self, paths: Sequence[str], depth: Optional[str] = None):
        args = ["status", "--xml"] + (["--depth", depth] if depth else []) + ["--", *paths]
        r = self.run(*args)
        if r.returncode != 0:
            raise _Stop(f"svn status 失敗: {self.err(r)}")
        return self._entries(r.stdout)

    def _entries(self, stdout: bytes):
        return _svn_entries(stdout)

    def conflicts(self, paths: Sequence[str]) -> List[Tuple[str, str]]:
        r = self.run("status", "--xml", "--", *paths)
        if r.returncode != 0:
            raise _Stop(f"svn status 失敗: {self.err(r)}")
        return _svn_conflicts(r.stdout)

    def has_conflict(self, paths: Sequence[str]) -> bool:
        return bool(self.conflicts(paths))


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


def svn_update_targets(svn: "_Svn", t: SyncTarget, retired_rel: set, env: Dict[str, str],
                       log: Logger) -> Tuple[str, Optional[str], int]:
    """記憶 pathspec 的 `svn update`（git 拉段的 svn 版）。回 (狀態, 理由, 本次 schedule-delete 數)：
      ok       — 已更新、無衝突（或只有索引檔 text 衝突且 resolver 已解開）
      skipped  — 沒 update：有已驗證退役以外的 missing 檔（update 會把它補回來，交人決定去留）
      conflict — update 後有驅動解不了的衝突（非索引檔、property／tree），工作副本停在衝突態，本輪不得 commit
      error    — update 本身非零、逾時或起不了程序（網路、伺服器、svn 不在）：拉段的事，落 pull_error／`.behind`，
                 不進 push 的 last_error；resolver 起不了程序同逾時 → conflict（工作副本已在衝突態）
    順序：先把 validated retired 且 missing 的檔 `svn delete`（schedule），再查其他 missing，再 update。
    update 只對記憶 pathspec，`--accept postpone` 留衝突給 resolver 判；mixed-revision 工作副本可接受。"""
    root = t.root
    deleted = 0
    other_missing: List[str] = []
    for p, item, _ in sorted(svn.status(t.pathspecs), key=lambda e: e[0]):
        rel = _rel_to(root, p)
        if not rel or item != "missing":
            continue
        if rel in retired_rel:
            r = svn.run("delete", "--", rel)
            if r.returncode != 0:
                raise _Stop(f"svn delete 失敗 ({rel}): {svn.err(r)}")
            deleted += 1
        else:
            other_missing.append(rel)
    if other_missing:
        return "skipped", f"記憶路徑有未登記退役的 missing 檔（{', '.join(other_missing[:3])}），不自動 update", deleted
    try:
        u = svn.run("update", "--accept", "postpone", "--", *t.pathspecs)
    except subprocess.TimeoutExpired as e:
        return "error", f"svn update 逾時 {e.timeout}s", deleted
    except (OSError, subprocess.SubprocessError) as e:
        return "error", f"svn update 無法執行 {type(e).__name__}: {e}"[:200], deleted
    if u.returncode != 0:
        return "error", f"svn update 失敗: {svn.err(u)}", deleted
    conflicts = svn.conflicts(t.pathspecs)
    if not conflicts:
        return "ok", None, deleted
    hard = [f"{p}({kind})" for p, kind in conflicts
            if kind != "text" or Path(p).name not in INDEX_FILE_NAMES]
    if hard:
        return "conflict", f"update 後衝突在驅動解不了的檔：{', '.join(hard[:3])}", deleted
    try:
        r = _run([sys.executable, str(CLAUDE_DIR / "tools" / "merge-atom-index.py"),
                  "--resolve", "--quiet", "--cwd", str(root)], root, svn.timeout, env)
    except subprocess.TimeoutExpired as e:
        return "conflict", f"索引檔衝突 resolver 逾時 {e.timeout}s（工作副本仍在衝突態）", deleted
    except (OSError, subprocess.SubprocessError) as e:
        return "conflict", f"索引檔衝突 resolver 無法執行 {type(e).__name__}: {e}（工作副本仍在衝突態）"[:200], deleted
    try:
        rep = json.loads((r.stdout or "").strip().splitlines()[-1]) if (r.stdout or "").strip() else {}
    except ValueError:
        rep = {}
    if r.returncode != 0 or rep.get("error") or rep.get("remaining") or svn.has_conflict(t.pathspecs):
        return "conflict", (f"索引檔衝突 resolver 未解開（rc={r.returncode} error={rep.get('error')} "
                            f"remaining={rep.get('remaining')}）"), deleted
    log(f"[svn] {root}: update 索引檔衝突已由 resolver 解開 {rep.get('resolved')}")
    return "ok", None, deleted


def _svn_pull(svn: "_Svn", t: SyncTarget, retired_rel: set, env: Dict[str, str], log: Logger,
              stop_on_skip: bool) -> Tuple[str, int]:
    """svn_update_targets 的結果落標記：skipped／error → `.behind`（stop_on_skip 時也 _Stop：commit 已被拒、沒 update
    就推不出去）；conflict → `.behind` + _Stop（工作副本停在衝突態不得 commit）；ok → 清 `.behind`。回 (狀態, delete 數)。"""
    status, reason, deleted = svn_update_targets(svn, t, retired_rel, env, log)
    if status == "ok":
        clear_behind(t.root)
        update_root_record(t, last_pull=_now_iso(), pull_error=None)
        return status, deleted
    log(f"[svn] {t.root}: 落後未併入 — {reason}")
    write_behind(t.root, reason or status)
    update_root_record(t, pull_error=reason)
    if status == "conflict" or stop_on_skip:
        raise _Stop(reason or status)
    return status, deleted


def _svn_local_changes(svn: "_Svn", t: SyncTarget) -> bool:
    return any(item in _SVN_CHANGED_ITEMS or item in ("unversioned", "missing")
               for _p, item, _tc in svn.status(t.pathspecs))


def _svn_sync(t: SyncTarget, vs: Dict[str, Any], env: Dict[str, str], log: Logger,
              retired: Sequence[str], reasons: Sequence[str] = ()) -> Dict[str, Any]:
    root = t.root
    svn = _Svn(t, vs, env)
    exclude = vs.get("exclude", [])

    retired_rel = {rel for rel in (_rel_to(root, p) for p in retired) if rel}
    if svn.has_conflict(t.pathspecs):
        raise _Stop("工作副本有未解衝突，停止（先 svn resolve）")

    added = deleted = 0
    pull_status = "disabled"
    # ── 拉：先 update 記憶路徑再 add/commit（與 git 的「commit → 拉 → push」同義：svn commit 本身就要求 up-to-date）──
    if (vs.get("pull") or {}).get("enabled", True):
        if _pull_in_cooldown(t, vs, reasons) and not _svn_local_changes(svn, t):
            log(f"[svn] {root}: reason=pull 在 cooldown 內且記憶路徑無變更，跳過 update")
            pull_status = "cooldown"
        else:
            pull_status, deleted = _svn_pull(svn, t, retired_rel, env, log, stop_on_skip=False)
    entries = svn.status(t.pathspecs)
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
                              "added": added, "deleted": deleted, "pull": {"status": pull_status}}
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
            result["pull"]["status"], n_del = _svn_pull(svn, t, retired_rel, env, log, stop_on_skip=True)
            deleted += n_del
            result["deleted"] = deleted
            targets = collect_targets()   # update 可能改掉本地變更集，重算；空集合 → 沒東西好提交
            if not targets:
                clear_unpushed(root)
                return result
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
                    retired: Sequence[str], pre_sync: bool, config: Optional[Dict[str, Any]] = None,
                    reasons: Sequence[str] = ()) -> Dict[str, Any]:
    """順序固定：拒跑狀態檢查 → 上輪 restore 失敗的恢復 → 索引同步 → commit → 拉 → push。合併中或 detached 時索引檔
    不得被改寫；恢復未完成時不得 commit（上游新增的 atom 會被當成本地刪除）。
    回傳含 `pull` 段；status=ok 只看 commit＋push（請求是關於推本地變更），拉失敗只留標記不阻 ack。"""
    try:
        branch = _git_check(t, vs, env) if t.vcs == "git" else None
        if t.vcs == "git":
            _git_recover(t, vs, env, log)
        else:
            _svn_check(t, vs, env)
        if pre_sync:
            _sync_indexes(t, float(vs.get("timeout_s", 60)), env, log)
        res = (_git_sync(t, vs, env, log, branch, config, reasons) if t.vcs == "git"
               else _svn_sync(t, vs, env, log, retired, reasons))
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
        return {"vcs": t.vcs, "root": t.root.as_posix(), "status": "unpushed", "reason": str(e),
                "pull": e.pull or {"status": "not-run"}}
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
                reasons = sorted(set(req.get("reasons") or []) | {reason})
                res = _sync_root_once(merged, vs, env, log, merged_retired, pre_sync, config, reasons)
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
