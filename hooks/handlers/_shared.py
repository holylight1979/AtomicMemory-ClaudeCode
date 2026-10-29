"""
handlers/_shared.py — module-level state + 跨 handler 共用 helper

共用：
- regex 常數（_SUPERSEDES_RE / _V4_TRIGGER_LINE_RE / _MEMORY_MD_AUTO_HEADER）
- lazy import flag（WISDOM_AVAILABLE / DOCDRIFT_AVAILABLE）
- entry_note / with_note（切入點契約 hooks/wg_entrypoint；模組壞了退成不接卡，不拖垮閘）
- _call_project_hook（subprocess invoke project hook）
- _cleanup_old_states（state 檔 TTL 清理）
- _is_ephemeral_path（路徑過濾）／note_ephemeral_skip（暫存目錄專案的寫入不記帳時，一個專案根說一次）
- _maybe_spawn_user_extract_worker（user extract worker spawn）
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (
    CLAUDE_DIR, CODE_DIR, WORKFLOW_DIR,
    _now_iso, _atom_debug_error,
    write_state,
)
from wg_extraction import _is_lease_valid, _set_lease
from wg_roles import get_current_user

# Windows: 外呼 python/git 等 console 程式時若不帶此 flag，無主控台的 hook 父行程會被配一個可見 console 視窗
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# ─── module-level regex / 常數 ───────────────────────────────────────────────

_SUPERSEDES_RE = re.compile(r"^- Supersedes:\s*(.+)", re.MULTILINE)
_V4_TRIGGER_LINE_RE = re.compile(r"^-\s+Trigger:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_MEMORY_MD_AUTO_HEADER = "<!-- AUTO-GENERATED: V4 role filter -->"

_EPHEMERAL_DIR_TOKENS = (
    "/pytest-of-",
    "/.pytest_cache/",
    "/__pycache__/",
)


# ─── Lazy import flags (graceful degrade) ────────────────────────────────────

try:
    from wisdom_engine import (
        classify_situation,
        get_reflection_summary,
        reflect as wisdom_reflect,
        track_retry as wisdom_track_retry,
    )
    WISDOM_AVAILABLE = True
except ImportError:
    WISDOM_AVAILABLE = False
    classify_situation = None
    get_reflection_summary = None
    wisdom_reflect = None
    wisdom_track_retry = None

try:
    from wg_docdrift import (
        check_source_drift, resolve_doc_update, build_drift_advisory,
        prune_committed_entries,
    )
    DOCDRIFT_AVAILABLE = True
except ImportError:
    DOCDRIFT_AVAILABLE = False
    check_source_drift = None
    resolve_doc_update = None
    build_drift_advisory = None
    prune_committed_entries = None

# 切入點契約（TECH §7.10）：Stop 擋訊息、PreToolUse deny、MCP 回覆、子代理 prompt 在問的那一刻接判準卡並留帳。
# 這支壞了只能讓問句沒有卡，不能讓 handler 匯入失敗（那會讓整支 handler 的閘一起失效）→ 退成不接卡、浮 stderr。
try:
    from wg_entrypoint import entry_note, with_note
except Exception as _entry_err:  # noqa: BLE001
    print(f"[Guardian:Entrypoint] 載入失敗，這次不接判準卡：{type(_entry_err).__name__}: {_entry_err}", file=sys.stderr)

    def entry_note(text: str, path: str, **_kw: Any) -> str:
        return ""

    def with_note(text: str, note: str) -> str:
        return text


# ─── AEC HUD 活性判定（post_tool_use 標旗 / stop 再查一次，兩端共用）─────────────


def _hud_alive(port: int, threshold_s: int) -> Tuple[bool, Dict[str, Any]]:
    """GET /api/aec/beat-status → HUD 窗活著？回 (alive, info)。

    活著 = clients ≥ 1（HUD 頁的 SSE 常駐連線在：視窗開著，即使頁面被瀏覽器凍結/節流）
        或 age_s < threshold（心跳新；舊版 Node 無 clients 欄時的退路）。
    心跳是「頁面正在渲染」的證據，Edge --app 視窗被遮住久了會停（瀏覽器休眠/凍結隱藏頁；現場實證窗開著 age 仍上百秒），
    單靠它會把開著的窗判死；連線才是「窗開著」的直接證據。
    info 一律帶實際用的 port/threshold/耗時、查到的 age_s/clients、失敗原因——呼叫端落 guard log
    （可觀測性鐵律：不可達的原因不得吞掉）。不可達 / 舊碼 404 / 逾時 → (False, info)。"""
    import urllib.request
    info: Dict[str, Any] = {"port": port, "threshold_s": threshold_s}
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/aec/beat-status", timeout=0.6
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
        age = int(data.get("age_s", 10 ** 9))
        clients = int(data.get("clients", 0))
        info.update(age_s=age, clients=clients)
        alive = clients >= 1 or age < threshold_s
        info["reason"] = "" if alive else "no_hud_client_and_beat_stale"
    except Exception as e:  # 逾時 / 連線拒絕 / 404 / 非 JSON：全記原因，不分類吞掉
        alive = False
        info["reason"] = f"{type(e).__name__}: {e}"[:200]
    info["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)
    return alive, info


# ─── Path helpers ────────────────────────────────────────────────────────────


def _long_path(path: str) -> str:
    """Windows 8.3 短路徑 → 長路徑（GetLongPathNameW）。檔案還不存在就往上找到存在的祖先轉，再接回其餘部分；
    非 Windows、UNC 網路路徑（不為了改檔去查網路）或整條都轉不了 → 原樣。暫存目錄在這台機器同時以長路徑與 `HOLYLI~1`
    這種短路徑出現，比對前兩邊都要轉。"""
    if os.name != "nt" or not path or path.startswith("\\\\"):
        return path
    import ctypes
    buf = ctypes.create_unicode_buffer(32768)
    head, tail = path, []
    while head:
        n = ctypes.windll.kernel32.GetLongPathNameW(head, buf, 32768)
        if 0 < n < 32768:
            return os.path.join(buf.value, *reversed(tail))
        parent, name = os.path.split(head)
        if not name or parent == head:
            break
        tail.append(name)
        head = parent
    if re.search(r"~\d", path):                           # 只有帶短檔名記號的路徑轉不了才影響比對：說一聲，不靜默
        print(f"[_shared] 8.3 短路徑轉長路徑失敗（GetLongPathNameW 對 {path} 與各層祖先都回 0），照原樣比對", file=sys.stderr)
    return path


def _comparable(path: str) -> str:
    """暫存判斷用的統一表示（路徑與系統 tmp 兩側都走這個）：Windows 先拿掉 `\\\\?\\` 長路徑前綴（磁碟機路徑去前綴、
    `\\\\?\\UNC\\server\\share\\…` → `\\\\server\\share\\…`；normpath 對帶前綴的路徑整條原樣不動，連 .. 都不消），再 normpath 消
    . 與 ..、轉長路徑（8.3 短路徑）、轉完再 normpath 一次（API 會保留 ..），斜線統一成 /。"""
    p = path
    if os.name == "nt":
        p = p.replace("/", "\\")
        if p[:8].upper() == "\\\\?\\UNC\\":
            p = "\\\\" + p[8:]
        elif p.startswith("\\\\?\\"):
            p = p[4:]
    return os.path.normpath(_long_path(os.path.normpath(p))).replace("\\", "/")


def _is_ephemeral_path(path: str) -> bool:
    """過濾測試/快取/系統 tmp 路徑，避免污染 modified_files。兩側都轉成同一種表示（_comparable：去 `\\\\?\\` 前綴、長路徑、
    消 . 與 ..）才比包含：8.3 短路徑、`\\\\?\\` 寫法都認得；`<tmp>\\..\\..\\專案\\x.py` 是專案原碼，不是暫存；含 `~1` 的字樣
    本身不算暫存。"""
    if not path:
        return False
    norm = _comparable(path)
    if _temp_root_of(norm):
        return True
    norm_low = norm.lower()
    return any(tok in norm_low for tok in _EPHEMERAL_DIR_TOKENS)


def _temp_root_of(norm: str) -> str:
    """norm（_comparable 過的路徑）在系統暫存目錄底下 → 回暫存根（同一種表示）；不在、判不了回空字串。"""
    try:
        tmp_root = _comparable(tempfile.gettempdir()).rstrip("/")
        return tmp_root if tmp_root and norm.lower().startswith(tmp_root.lower() + "/") else ""
    except Exception as e:  # noqa: BLE001  判不了暫存目錄 → 當一般路徑（照記改檔），浮一行
        print(f"[_shared] 判斷暫存目錄失敗，路徑照一般檔處理：{type(e).__name__}: {e}", file=sys.stderr)
        return ""


EPHEMERAL_NOTED_KEY = "ephemeral_noted_roots"
EPHEMERAL_NOTED_CAP = 20


def note_ephemeral_skip(state: Dict[str, Any], path: str) -> bool:
    """規則 EPHEMERAL_WRITE_NOTED_ONCE：寫入目標在系統暫存目錄底下（_is_ephemeral_path 的暫存根那一支）→ 照舊不記進改檔清單，
    同一 session（state）、同一個專案根第一次印一行 stderr 說明為什麼沒記，state 記下這個根；回 True＝這次印了（呼叫端要寫回 state）。
    不在暫存根底下、只因快取目錄（__pycache__、.pytest_cache）判成暫存的那一支不是專案，不印。專案根＝檔所在的版控根；沒有就 session 的 cwd（檔在它底下時）；
    再沒有就暫存根底下第一層資料夾。"""
    norm = _comparable(path) if path else ""
    tmp_root = _temp_root_of(norm) if norm else ""
    if not tmp_root:
        return False
    root = _ephemeral_project_root(norm, tmp_root, str((state.get("session") or {}).get("cwd") or ""))
    seen = state.get(EPHEMERAL_NOTED_KEY)
    seen = [str(r) for r in seen] if isinstance(seen, list) else []
    if root.lower() in seen:
        return False
    state[EPHEMERAL_NOTED_KEY] = (seen + [root.lower()])[-EPHEMERAL_NOTED_CAP:]
    print(f"[Guardian:EphemeralWrite] {root} 在系統暫存目錄底下，這個專案的寫入照暫存檔處理、不記進改檔清單："
          "收尾的對帳、第二意見、同步提醒都看不到這些改動。要讓閘照看，把專案放到暫存目錄以外。本 session 這個專案只說這一次。",
          file=sys.stderr)
    return True


def _ephemeral_project_root(norm: str, tmp_root: str, cwd: str) -> str:
    try:
        from wg_verify_ledger import vcs_root_of
        vcs = vcs_root_of(norm)
    except Exception as e:  # noqa: BLE001  找不到版控根 → 退回 cwd／暫存根第一層
        print(f"[_shared] 找暫存專案的版控根失敗，改用 cwd 或暫存根第一層：{type(e).__name__}: {e}", file=sys.stderr)
        vcs = None
    if vcs is not None:
        return _comparable(str(vcs))
    base = _comparable(cwd) if cwd else ""
    if base and norm.lower().startswith(base.lower().rstrip("/") + "/"):
        return base.rstrip("/")
    return f"{tmp_root}/{norm[len(tmp_root) + 1:].split('/', 1)[0]}"


# ─── Project delegate hook ───────────────────────────────────────────


def _call_project_hook(project_root: Path, action: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Call project-level delegate hook via subprocess isolation.

    {project_root}/.claude/hooks/project_hooks.py
    Stdin/stdout JSON. Timeout 5s. Never raises.
    """
    hook_script = project_root / ".claude" / "hooks" / "project_hooks.py"
    if not hook_script.exists():
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(hook_script), action],
            input=json.dumps(context, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=_NO_WINDOW,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError, Exception) as e:
        _atom_debug_error(f"project_hook:{action}", e)
    return None


# ─── State file TTL cleanup (was _cleanup_old_states in workflow-guardian) ───


_ACTIVE_WORKING_TTL_S = 6 * 3600  # 有 prompt 的 working state 的孤兒兜底 TTL


def _cleanup_old_states() -> None:
    """V3/2.2A: Tiered TTL cleanup for state files.
    age < 600s keep; merged_into → 10min; empty working → 1h; working（有 prompt）> 6h；
    done synced > 1h; done pending > 4h; anything > 7d.

    empty working 取 1h：idle session（開著沒下 prompt）state 被清後，
    _ensure_state fallback 只能重建最小 index、早前脈絡不可復原——寬限放長。
    """
    now = time.time()
    for f in WORKFLOW_DIR.glob("state-*.json"):
        try:
            age = now - f.stat().st_mtime
            if age < 600:
                continue

            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                if age > 7 * 86400:
                    f.unlink(missing_ok=True)
                continue

            phase = data.get("phase", "")
            prompt_count = data.get("topic_tracker", {}).get("prompt_count", 0)
            merged = data.get("merged_into")
            sync_pending = data.get("sync_pending", False)

            if merged and age > 600:
                f.unlink(missing_ok=True)
            elif prompt_count == 0 and phase == "working" and age > 3600:
                f.unlink(missing_ok=True)
            elif prompt_count > 0 and phase == "working" and age > _ACTIVE_WORKING_TTL_S:
                # 有 prompt 的活躍 session：以前 30 分鐘沒寫 state 就刪——使用者在想、或在等
                # 長時間背景任務時就會中招，下一個 hook 只能建 fallback、整場歷史歸零
                #（2026-09-21 本 session turn 15 實證）。CC 真正結束會走 SessionEnd 標 done，
                # 這條只是兜底孤兒，放寬到 6 小時。
                f.unlink(missing_ok=True)
            elif phase == "done" and not sync_pending and age > 3600:
                f.unlink(missing_ok=True)
            elif phase == "done" and sync_pending and age > 14400:
                f.unlink(missing_ok=True)
            elif age > 7 * 86400:
                f.unlink(missing_ok=True)
        except OSError:
            pass
    # 其餘 workflow/ 紀錄的保留規則都在下面的 WORKFLOW_RETENTION（SessionStart 由 prune_workflow_records 照表清）


# ─── workflow/ 執行紀錄保留規則表（SessionStart 照表清一次）─────────────────────
# 每列：dir（相對 workflow/；"../Logs/…" 是 workflow 的上一層）｜patterns（只看該層，不往下找）｜kind＋param｜keep（保留多久，給人讀）｜why（為什麼刪了不會壞事）。
# 依據：每類在 session 結束後還有沒有讀者、讀者看多久以前的資料。檔名含目前 session id 的一律不動（resume 回來還要用）。
# kind：age＝mtime 超過 param 天就刪；need_goal／aec_tempfiles／job_dirs／months／tracking_pairs＝下面同名的判斷；
# rotate＝超過大小輪替；elsewhere＝規則在別支程式（param 寫在哪），表上只登記；keep＝永久保留。

RETENTION_KINDS = ("age", "need_goal", "aec_tempfiles", "job_dirs", "months", "tracking_pairs", "rotate", "elsewhere", "keep")
OVERVIEW_LOG_MAX_MB = 10

WORKFLOW_RETENTION: List[Dict[str, Any]] = [
    {"dir": "", "patterns": ("state-*.json",), "kind": "elsewhere", "param": "handlers/_shared._cleanup_old_states（SessionStart、SessionEnd）",
     "keep": "10 分鐘到 6 小時分級，最長 7 天", "why": "只有該 session 自己讀；分級要看檔案內容，留在 _cleanup_old_states"},
    {"dir": "", "patterns": ("companion-*.json",), "kind": "age", "param": 7,
     "keep": "7 天", "why": "codex 旁路紀錄只給當時那個 session 用"},
    {"dir": "", "patterns": ("coord-warn-cache-*.tmp", "state-*.tmp", "companion-*.tmp", "*.corrupt*", "coord-warn-cache-*.json",
                             "state-*.pending"),
     "kind": "age", "param": 7, "keep": "7 天",
     "why": "寫到一半被砍的殘檔、壞檔備份與協調快取，沒人讀；state 待併帳只有同一個 session 下一支 hook 併，7 天沒併＝session 早結束"},
    {"dir": "../Logs/session-coordination", "patterns": ("*.jsonl*",), "kind": "age", "param": 30,
     "keep": "30 天", "why": "多 session 協調的觀測紀錄，只拿來查近期"},
    {"dir": "aec-report", "patterns": ("*.json", "*.tmp"), "kind": "age", "param": 7,
     "keep": "7 天", "why": "收尾報告只給近期 session 的 HUD 看；.tmp 是寫入殘檔"},
    {"dir": "aec-decision", "patterns": ("*.json",), "kind": "age", "param": 7,
     "keep": "7 天", "why": "舊版 HUD 按鈕留的決策紙條；現在按鈕當場執行、不再產生，只清舊檔"},
    {"dir": "aec-tempfiles", "patterns": ("*.jsonl",), "kind": "aec_tempfiles", "param": 7,
     "keep": "超過 7 天而且帳上列的東西都已不在（檔案看磁碟、分支看 git）",
     "why": "session 留下的東西還在，HUD 就要一直列出來讓使用者處置（原設計者拒絕「放 N 天就刪」）"},
    {"dir": "dpm-done", "patterns": ("*.flag",), "kind": "age", "param": 7,
     "keep": "7 天", "why": "只防同一 session 重複要求 post-mortem"},
    {"dir": "need-goal", "patterns": ("*.json", "*.tmp", "*.lock"), "kind": "need_goal", "param": "wg_need_goal.STALE_DAYS",
     "keep": "目標檔與殘檔 30 天；壞檔備份 30 天；鎖檔在同名目標檔已不在、而且超過 30 天才刪",
     "why": "只有該 session 讀（從續接單接手讀的是續接單）；目標檔都清掉的鎖不會再有人鎖"},
    {"dir": "entry-sent", "patterns": ("*.json",), "kind": "age", "param": 7,
     "keep": "7 天", "why": "只給同一 session 同一個話題判「這張判準卡送過全文了沒」用（wg_entrypoint CARD_ONCE_PER_TOPIC）"},
    {"dir": "git-launchers", "patterns": ("*.json",), "kind": "age", "param": 7,
     "keep": "7 天", "why": "只給同一 session 收尾判「這支是一次性 git 啟動器、不算改程式」用（wg_verify_ledger LAUNCHER_NOT_CODE）"},
    {"dir": "ups-sentinel", "patterns": ("*.json",), "kind": "age", "param": 7,
     "keep": "7 天", "why": "只給同一 session 下一輪偵測「上一輪被中斷」用"},
    {"dir": "mcp-boot", "patterns": ("*.json", "*.tmp"), "kind": "age", "param": 7,
     "keep": "7 天", "why": "活著的工具服務每分鐘更新心跳；收尾只看 3 分鐘內有心跳的，關掉的程序留下的檔沒人讀"},
    {"dir": "acceptance-spec", "patterns": ("*.json",), "kind": "age", "param": 30,
     "keep": "30 天", "why": "只在該 session 內讀；規格本體在專案 .claude/verify/，不受影響"},
    {"dir": "harvest-ledger", "patterns": ("*.jsonl",), "kind": "age", "param": 30,
     "keep": "30 天", "why": "SessionEnd 同步時已交接到 vcs-sync 佇列；只有 resume 同一 session 才會再讀"},
    {"dir": "verify-ledger", "patterns": ("*.jsonl",), "kind": "age", "param": 14,
     "keep": "14 天（含 .agents.jsonl；_runs/ 另列）",
     "why": "查核閘看 state 裡的收據、不讀這檔；第二意見只讀最後 20 行；收尾報告 7 天就清"},
    {"dir": "verify-ledger/_runs", "patterns": ("*.json",), "kind": "elsewhere", "param": "lib/self_receipt.prune_self_runs（SessionEnd）",
     "keep": "留最新 200 份、超過 30 天也刪", "why": "對帳閘只讀最新 50 份"},
    {"dir": "second-opinion", "patterns": ("<job 目錄>", "_sealed/<job>.txt"), "kind": "job_dirs", "param": 14,
     "keep": "14 天（看目錄裡最新的檔）", "why": "結果在發起的 session 裡幾分鐘內就取走；_probe/ 會自己覆寫，不動"},
    {"dir": "usage-snapshots", "patterns": ("*-FAILED.png",), "kind": "age", "param": 30,
     "keep": "30 天", "why": "失敗診斷圖只看當次；用量 log 與成功截圖是成品，不刪"},
    {"dir": "scorecard", "patterns": ("<YYYYMM>.jsonl",), "kind": "months", "param": 3,
     "keep": "當月加前 2 個月", "why": "報表只讀近 4 週；candidates.json 不動"},
    {"dir": "tracking", "patterns": ("*.jsonl",), "kind": "tracking_pairs", "param": 90,
     "keep": "已結案的一對（開項＋結案）結案超過 90 天就拿掉；沒結案的永遠留",
     "why": "沒結案的就是這本帳存在的目的；結案的一對沒有程式再讀"},
    {"dir": "tool-results", "patterns": ("*.jsonl",), "kind": "elsewhere", "param": "wg_friction.flush_tool_result_stats（SessionEnd）",
     "keep": "彙整完刪自己的，其他 7 天", "why": "只有自己的 session 彙整時讀"},
    {"dir": "health-reports", "patterns": ("health-*.md",), "kind": "elsewhere", "param": "tools/health-weekly.py（寫報告時）",
     "keep": "留最新 12 份", "why": "週報只需要近幾週對照"},
    {"dir": "se-sentinel", "patterns": ("*.json",), "kind": "elsewhere", "param": "session_start._check_se_sentinel_residual",
     "keep": "開 session 時偵測、告警、刪", "why": "要先告警才刪，不能併進靜默清理"},
    {"dir": "", "patterns": ("_overview-hub.log",), "kind": "rotate", "param": "OVERVIEW_LOG_MAX_MB",
     "keep": "超過 10 MB 輪替成 .1～.3", "why": "沒有程式讀，只會一直長"},
    {"dir": "", "patterns": ("config.json", "followups.json", "org-memory.local.json", "health-last-run.json", "world-dev.json"),
     "kind": "keep", "param": None, "keep": "永久", "why": "設定與本機狀態"},
    {"dir": "", "patterns": ("inbox/", "vcs-sync/", "usage-snapshots/usage-log.jsonl", "usage-snapshots/<成功截圖>", "scorecard/candidates.json"),
     "kind": "keep", "param": None, "keep": "永久", "why": "信件匣、版控同步佇列（鎖刻意不刪）、使用者的成品"},
]

_DAY = 86400


def _file_sig(p: Path) -> Tuple[int, int]:
    st = p.stat()
    return st.st_size, st.st_mtime_ns


def _rm(p: Path, dry_run: bool, res: Dict[str, Any]) -> bool:
    """刪一個檔或目錄並記帳：成功列 deleted、刪不掉（被占用、權限）列 failed、已經被別人刪掉不算。"""
    if dry_run:
        res["deleted"].append(str(p))
        return True
    try:
        if p.is_dir():
            import shutil
            shutil.rmtree(p)
        else:
            p.unlink()
        res["deleted"].append(str(p))
        return True
    except FileNotFoundError:
        return False
    except OSError:
        res["failed"].append(str(p))
        return False


def _older(p: Path, cutoff: float) -> bool:
    try:
        return p.stat().st_mtime < cutoff
    except OSError:
        return False


def _prune_age(d: Path, patterns, days: float, now: float, sid: str, dry_run: bool, res: Dict[str, Any]) -> None:
    cutoff = now - days * _DAY
    for pattern in patterns:
        for f in d.glob(pattern):
            if f.is_file() and not (sid and sid in f.name) and _older(f, cutoff):
                _rm(f, dry_run, res)


def _prune_need_goal(d: Path, now: float, sid: str, dry_run: bool, res: Dict[str, Any]) -> None:
    """目標檔（<sid>.json）與殘檔（*.tmp）、壞檔備份（*.corrupt-*.json）超過 STALE_DAYS 刪；
    鎖檔只在同名目標檔已不在（或這一輪剛清掉）、而且本身也超過 STALE_DAYS 才刪——目標檔還在就可能有人要鎖它。"""
    try:
        from wg_need_goal import STALE_DAYS as days
    except Exception:  # noqa: BLE001
        days = 30
    cutoff = now - days * _DAY
    gone = set()
    for f in list(d.glob("*.json")) + list(d.glob("*.tmp")):
        if not f.is_file() or (sid and sid in f.name) or not _older(f, cutoff):
            continue
        if _rm(f, dry_run, res) and f.suffix == ".json":
            gone.add(f.stem)
    for lock in d.glob("*.lock"):
        if (sid and sid in lock.name) or not _older(lock, cutoff):
            continue
        if lock.stem in gone or not lock.with_suffix(".json").exists():
            _rm(lock, dry_run, res)


def _prune_aec_tempfiles(d: Path, days: float, now: float, dry_run: bool, res: Dict[str, Any]) -> None:
    """產出物帳本：過期而且帳上列的東西全都不在了才清（檔案看磁碟、分支看 git）；
    只要還有一樣在，帳本就要留著讓 HUD 繼續列。"""
    from handlers.aec_ledger import rec_alive
    cutoff = now - days * _DAY
    for p in d.glob("*.jsonl"):
        if not _older(p, cutoff):
            continue
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        alive = False
        for line in lines:
            try:
                rec = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(rec, dict) and rec_alive(rec):
                alive = True
                break
        if not alive:
            _rm(p, dry_run, res)


def _prune_job_dirs(d: Path, days: float, now: float, dry_run: bool, res: Dict[str, Any]) -> None:
    """第二意見 job 目錄：目錄與裡面最新的檔都超過期限才整個刪，連同 _sealed/<job>.txt；_ 開頭的（_probe、_sealed）不當 job。"""
    cutoff = now - days * _DAY
    for job in d.iterdir():
        if not job.is_dir() or job.name.startswith("_"):
            continue
        try:
            newest = max([job.stat().st_mtime] + [f.stat().st_mtime for f in job.rglob("*")])
        except OSError:
            continue
        if newest < cutoff and _rm(job, dry_run, res):
            sealed = d / "_sealed" / f"{job.name}.txt"
            if sealed.exists():
                _rm(sealed, dry_run, res)
    sealed_dir = d / "_sealed"
    if sealed_dir.is_dir():
        for s in sealed_dir.glob("*.txt"):
            if str(s) not in res["deleted"] and _older(s, cutoff):
                _rm(s, dry_run, res)


def _prune_months(d: Path, months: int, now: float, dry_run: bool, res: Dict[str, Any]) -> None:
    """<YYYYMM>.jsonl 只留當月與前 months-1 個月（依檔名，不看 mtime）。"""
    t = datetime.fromtimestamp(now)
    idx = t.year * 12 + t.month - 1
    keep = {f"{(i // 12):04d}{(i % 12) + 1:02d}" for i in range(idx - months + 1, idx + 1)}
    for f in d.glob("*.jsonl"):
        if re.fullmatch(r"\d{6}", f.stem) and f.stem not in keep:
            _rm(f, dry_run, res)


def _prune_tracking_pairs(d: Path, days: float, now: float, dry_run: bool, res: Dict[str, Any]) -> None:
    """追蹤帳本：結案列（closed 且 closes.id 指到同本帳的開項）的 at 超過期限 → 那一對一起拿掉；其他列逐字原樣保留。
    帳本會被多個 session 同時追加且沒有鎖：改寫前後各看一次檔案大小與時間，中間有變就這一輪不動。"""
    try:
        from wg_harvest import tracking_entry_id
    except Exception:  # noqa: BLE001
        def tracking_entry_id(e):  # type: ignore[no-redef]
            return str(e.get("id") or "")
    cutoff = now - days * _DAY
    for t in d.glob("*.jsonl.*.tmp"):   # 改寫途中被砍留下的暫存
        if _older(t, now - _DAY):
            _rm(t, dry_run, res)
    for p in d.glob("*.jsonl"):
        try:
            sig = _file_sig(p)
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.split("\n")
        rows: Dict[int, Dict[str, Any]] = {}
        for i, line in enumerate(lines):
            try:
                row = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(row, dict):
                rows[i] = row
        open_at = {tracking_entry_id(r): i for i, r in rows.items() if r.get("status") == "open"}
        drop = set()
        for i, r in rows.items():
            closes = r.get("closes")
            if r.get("status") != "closed" or not isinstance(closes, dict):
                continue
            target = open_at.get(str(closes.get("id")))
            if target is None or target in drop:
                continue
            try:
                at = datetime.fromisoformat(str(r.get("at"))).timestamp()
            except (TypeError, ValueError):
                continue
            if at < cutoff:
                drop.update((i, target))
        if not drop:
            continue
        kept = [line for i, line in enumerate(lines) if i not in drop]
        if dry_run:
            res["compacted"][str(p)] = len(drop)
            continue
        tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text("\n".join(kept), encoding="utf-8", newline="\n")
            if _file_sig(p) != sig:
                tmp.unlink()
                continue
            os.replace(tmp, p)
            res["compacted"][str(p)] = len(drop)
        except OSError:
            res["failed"].append(str(p))
            try:
                tmp.unlink()
            except OSError:
                pass


def prune_workflow_records(wf: Optional[Path] = None, current_sid: str = "", now: Optional[float] = None,
                           dry_run: bool = False) -> Dict[str, Any]:
    """照 WORKFLOW_RETENTION 清 workflow/ 底下的執行紀錄（SessionStart 跑一次）。
    回 {deleted: [...], failed: [...], compacted: {帳本: 拿掉幾列}, rotated: [...]}；dry_run 只列不刪。
    單列出錯不影響其他列；有刪不掉的檔或某列出錯，各寫一行 atom-debug（不靜默）。"""
    wf = Path(wf) if wf is not None else WORKFLOW_DIR
    now = time.time() if now is None else now
    res: Dict[str, Any] = {"deleted": [], "failed": [], "compacted": {}, "rotated": []}
    if not wf.is_dir():
        return res
    for row in WORKFLOW_RETENTION:
        kind = row["kind"]
        if kind in ("elsewhere", "keep"):
            continue
        rel = row["dir"]
        d = wf.parent / rel[3:] if rel.startswith("../") else (wf / rel if rel else wf)
        if not d.is_dir():
            continue
        try:
            if kind == "age":
                _prune_age(d, row["patterns"], row["param"], now, current_sid, dry_run, res)
            elif kind == "need_goal":
                _prune_need_goal(d, now, current_sid, dry_run, res)
            elif kind == "aec_tempfiles":
                _prune_aec_tempfiles(d, row["param"], now, dry_run, res)
            elif kind == "job_dirs":
                _prune_job_dirs(d, row["param"], now, dry_run, res)
            elif kind == "months":
                _prune_months(d, row["param"], now, dry_run, res)
            elif kind == "tracking_pairs":
                _prune_tracking_pairs(d, row["param"], now, dry_run, res)
            elif kind == "rotate":
                from wg_core import rotate_log_if_oversized
                for name in row["patterns"]:
                    log = d / name
                    if dry_run:
                        continue
                    if rotate_log_if_oversized(log, max_mb=OVERVIEW_LOG_MAX_MB):
                        res["rotated"].append(str(log))
        except Exception as e:  # noqa: BLE001
            _atom_debug_error(f"workflow_retention:{row['dir'] or 'workflow'}", e)
    if res["failed"]:
        names = "、".join(Path(f).name for f in res["failed"][:5])
        _atom_debug_error("workflow_retention",   # OSError 才會把訊息原文寫進 log（其他型別只記 traceback）
                          OSError(f"{len(res['failed'])} 個刪不掉（被占用或沒權限）：{names}"))
    return res


# ─── User Extract Worker Spawning ──────────────────────────────────────


def _maybe_spawn_user_extract_worker(
    session_id: str, state: Dict[str, Any], config: Dict[str, Any],
) -> bool:
    """Spawn user-extract-worker.py as detached subprocess if conditions met.

    Returns True if spawned (worker will call session evaluator itself),
    False if skipped (caller should run fallback evaluator).
    """
    ue_config = config.get("userExtraction", {})
    if not ue_config.get("enabled", False):
        return False

    pending = state.get("pending_user_extract", [])
    if not pending:
        return False

    if _is_lease_valid(state, "user_extract_worker_pid"):
        return False

    worker_path = CODE_DIR / "hooks" / "user-extract-worker.py"
    if not worker_path.exists():
        return False

    cwd = state.get("session", {}).get("cwd", "")
    user_id = state.get("user_identity", {})
    user = user_id.get("user") or get_current_user()

    worker_ctx = {
        "session_id": session_id,
        "cwd": cwd,
        "config": config,
        "user": user,
    }

    try:
        import subprocess as _sp
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = _sp.CREATE_NO_WINDOW | _sp.DETACHED_PROCESS
        else:
            kwargs["start_new_session"] = True

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        json_ctx = json.dumps(worker_ctx, ensure_ascii=False)
        # worker 的錯誤（例如萃取紀錄寫不進）落到資料根 Logs/user-extract-worker.log，不丟進 DEVNULL
        worker_log = CLAUDE_DIR / "Logs" / "user-extract-worker.log"
        worker_log.parent.mkdir(parents=True, exist_ok=True)
        with open(worker_log, "a", encoding="utf-8", newline="\n") as worker_log_fh:
            proc = _sp.Popen(
                [sys.executable, str(worker_path)],
                stdin=_sp.PIPE,
                stdout=_sp.DEVNULL,
                stderr=worker_log_fh,
                env=env,
                **kwargs,
            )
        proc.stdin.write(json_ctx.encode("utf-8"))
        proc.stdin.close()

        _set_lease(state, "user_extract_worker_pid", proc.pid)
        write_state(session_id, state)
        print(
            f"user-extract-worker spawned (pid={proc.pid}, "
            f"pending={len(pending)})",
            file=sys.stderr,
        )
        return True
    except Exception as e:
        _atom_debug_error("spawn_user_extract_worker", e)
        return False
