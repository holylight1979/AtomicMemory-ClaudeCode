"""
wg_coordination.py — 跨 session 協調（衝突預警）。

多 session 共用 ~/.claude 或同一專案工作樹時：
  - Write/Edit/NotebookEdit 動到其他活 session 已改的檔 → advisory 警告
  - Bash 收尾型 git 指令（add -A / reset --hard / checkout -- . / clean -f）
    且存在其他活 session 有未收改動 → advisory 警告（選擇性 staging 規範）

全程唯讀他人 state、warn-only 不阻斷、fail-open（任何異常吞掉並落 log +
每行程一次 stderr）。observation log 落 Logs/session-coordination/<sid>.jsonl
（per-session 分檔迴避跨行程共檔 append/rotate 競寫；log 記完整 session id，
警告文字才用短 id）。config: coordination.*（enabled 一鍵關）。
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from wg_core import WORKFLOW_DIR, _now_iso, rotate_log_if_oversized

COORD_LOG_DIR = WORKFLOW_DIR.parent / "Logs" / "session-coordination"

_STATE_SIZE_LIMIT = 512 * 1024

# 每行程一次的 stderr 去重（hook 行程短命，作用域=單次 hook 呼叫）
_stderr_emitted: set = set()


def _stderr_once(key: str, msg: str) -> None:
    if key in _stderr_emitted:
        return
    _stderr_emitted.add(key)
    try:
        import sys
        sys.stderr.write(msg + "\n")
    except OSError:
        pass


def _norm_path(p: str) -> str:
    """路徑正規化：剝 Win32 namespace 前綴 → resolve → 統一斜線 + casefold。"""
    if not p:
        return ""
    if p.startswith("\\\\?\\") or p.startswith("\\\\.\\"):
        p = p[4:]
    try:
        rp = str(Path(p).resolve())
    except (OSError, ValueError):
        rp = p
    rp = rp.replace("\\", "/").casefold()
    if rp.startswith("//?/") or rp.startswith("//./"):
        rp = rp[4:]
    return rp


def coord_log(session_id: str, ev: str, **fields: Any) -> None:
    """NDJSON observation log（per-session 檔）。log 失敗不得影響主流程。"""
    try:
        COORD_LOG_DIR.mkdir(parents=True, exist_ok=True)
        p = COORD_LOG_DIR / f"{session_id or 'unknown'}.jsonl"
        rotate_log_if_oversized(p, max_mb=5, keep=2)
        rec = {"ts": _now_iso(), "ev": ev, "sid": session_id}
        rec.update(fields)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        _stderr_once("coordlog", f"[Guardian:Coord] observation log 寫入失敗（不影響功能）：{e}")


# ─── warn-cache（同檔重警抑制；壞掉只停用去重、警告照發）──────────────────


def _warn_cache_path(session_id: str) -> Path:
    return WORKFLOW_DIR / f"coord-warn-cache-{session_id}.json"


def _warn_cache_suppressed(session_id: str, norm_target: str, suppress_s: float) -> bool:
    """唯讀查詢：此檔近期已警過？cache 異常一律當「未警過」。"""
    try:
        data = json.loads(_warn_cache_path(session_id).read_text(encoding="utf-8"))
        ts = float(data.get(norm_target, 0))
        return (time.time() - ts) < suppress_s
    except Exception:
        return False


def record_warn_cache(session_id: str, file_path: str) -> None:
    """警告**實際發出時**才記錄（deny 蓋掉警告的回合不記——否則修正後合法重試會被抑制吃掉）。

    寫入時順手修剪 >24h 舊 entry（防單 session 長跑無界增長）。
    並行行程互相覆蓋=可接受（頂多重複警告一次）。
    """
    try:
        norm_target = _norm_path(file_path)
        now = time.time()
        p = _warn_cache_path(session_id)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        data = {k: v for k, v in data.items()
                if isinstance(v, (int, float)) and now - v < 86400}
        data[norm_target] = now
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        pass  # 去重失效無害，警告本體不受影響


# ─── 衝突掃描 ────────────────────────────────────────────────────────────────


def _iter_peer_states(session_id: str, cfg: Dict[str, Any]):
    """依 mtime 降冪列其他 session 的 state 檔（過濾自己/過舊/過大），yield 已 parse dict。

    上限截斷（max_scan_files，預設 20）必落 scan_overflow log——被擠掉的 state 是
    可稽核的盲區，不得靜默（單機併發 session 實務 <10，溢出即異常訊號）。
    """
    window_s = float(cfg.get("scan_mtime_window_s", 1800))
    max_files = int(cfg.get("max_scan_files", 20))
    now = time.time()
    try:
        candidates = []
        for f in WORKFLOW_DIR.glob("state-*.json"):
            try:
                if session_id and session_id in f.name:
                    continue
                st = f.stat()
                if now - st.st_mtime > window_s:
                    continue
                if st.st_size > _STATE_SIZE_LIMIT:
                    coord_log(session_id, "skip_oversize", peer_file=f.name, size=st.st_size)
                    continue
                candidates.append((st.st_mtime, f))
            except OSError:
                continue
        candidates.sort(key=lambda t: t[0], reverse=True)
        if len(candidates) > max_files:
            coord_log(session_id, "scan_overflow",
                      dropped=len(candidates) - max_files, total=len(candidates))
        for _, f in candidates[:max_files]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    yield data
            except Exception:
                coord_log(session_id, "fail_open", degraded_reason=f"bad_state:{f.name}")
                continue
    except Exception as e:
        coord_log(session_id, "fail_open", degraded_reason=f"scan:{e}")


def _entry_within_window(at_iso: str, window_s: float) -> bool:
    """entry.at 距現在 ≤ window_s 才算。壞格式/未來時間 → False（跳過該 entry）。"""
    try:
        at_ts = datetime.fromisoformat(at_iso).timestamp()
    except (ValueError, TypeError):
        return False
    age = time.time() - at_ts
    return 0 <= age <= window_s


def check_cross_session_conflict(
    session_id: str,
    file_path: str,
    config: Dict[str, Any],
    entry_window_s: Optional[float] = None,
    use_cache: bool = True,
    ev: str = "conflict_warn",
) -> Optional[Dict[str, Any]]:
    """此檔是否在其他活 session 的 modified_files？命中回 peer 資訊，否則 None。

    entry_window_s：僅計「檢查當下往前 N 秒內」的 peer entry（late-collision 用）。
    use_cache=False：不做同檔重警抑制（late-collision 純 log 路徑）。
    注意：本函式**只讀** warn-cache 判抑制、不寫入——記錄由 caller 在警告實際
    發出時呼叫 record_warn_cache（deny 蓋掉警告的回合不得記）。
    """
    cfg = config.get("coordination") or {}  # null 容錯：壞型別不得炸到 caller
    if not cfg.get("enabled", False):
        return None
    t0 = time.perf_counter()
    norm_target = _norm_path(file_path)
    if not norm_target:
        return None
    hit: Optional[Dict[str, Any]] = None
    try:
        for state in _iter_peer_states(session_id, cfg):
            phase = state.get("phase", "")
            if phase not in ("working", "syncing") or state.get("merged_into"):
                continue
            owner = (state.get("session") or {}).get("id", "")
            for m in state.get("modified_files", []):
                if not isinstance(m, dict):
                    continue
                entry_sid = m.get("session_id") or owner
                if not entry_sid or entry_sid == session_id:
                    continue  # merged state 內含多 session entry：只認 entry 級歸屬
                if _norm_path(m.get("path", "")) != norm_target:
                    continue
                if entry_window_s is not None and not _entry_within_window(
                    m.get("at", ""), entry_window_s
                ):
                    continue
                hit = {
                    "peer_sid": entry_sid,
                    "peer_sid8": entry_sid[:8],
                    "path": file_path,
                    "peer_at": m.get("at", ""),
                    "peer_count": int(m.get("count", 1)),
                }
                break
            if hit:
                break

        ms = round((time.perf_counter() - t0) * 1000, 1)
        if hit is None:
            if int(time.time()) % 20 == 0:  # 空掃採樣：epoch 秒 %20==0 才記（延遲基線）
                coord_log(session_id, "scan_clear", path=file_path, ms=ms)
            return None

        if use_cache:
            suppress_s = float(cfg.get("warn_suppress_min", 10)) * 60
            if _warn_cache_suppressed(session_id, norm_target, suppress_s):
                coord_log(session_id, "conflict_suppressed", peer=hit["peer_sid"],
                          path=file_path, ms=ms)
                return None
        coord_log(session_id, ev, peer=hit["peer_sid"], path=file_path,
                  peer_at=hit["peer_at"], ms=ms)
        return hit
    except Exception as e:
        coord_log(session_id, "fail_open", degraded_reason=str(e), path=file_path)
        _stderr_once("conflict", f"[Guardian:Coord] 衝突掃描異常（fail-open）：{e}")
        return None


def format_conflict_warning(hit: Dict[str, Any]) -> str:
    return (
        f"⚠️ [Guardian:CoordWarn] 另一個活躍 session（{hit['peer_sid8']}）也改過此檔："
        f"{hit['path']}（最近 {hit['peer_at']}，共 {hit['peer_count']} 次）。"
        "共用工作樹下後寫覆蓋前寫、無自動合併——請先確認不互踩（必要時與使用者確認分工），"
        "收尾 staging 只揀自己的檔、勿 git add -A。"
    )


def format_late_collision(hit: Dict[str, Any]) -> str:
    return (
        f"⚠️ [Guardian:CoordWarn] 寫後偵測：session {hit['peer_sid8']} 於 60 秒內"
        f"也寫過 {hit['path']}（{hit['peer_at']}）。兩邊幾乎同時首寫、寫前互看不見，"
        "請檢查是否覆蓋了對方的內容。"
    )


# ─── Bash 收尾型 git 指令預警 ────────────────────────────────────────────────

# 危險收尾指令：錨定於指令段起始（split 於 && ; | 換行後），允許 git 全域選項
_GIT_DANGER_RE = re.compile(
    r"^git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--no-pager\s+|--git-dir=\S+\s+|--work-tree=\S+\s+)*"
    r"(?:add\s+(?:-A\b|--all\b|\.(?=\s|$))"
    r"|reset\s+--hard\b"
    r"|checkout\s+--\s+\.(?=\s|$)"
    r"|clean\s+-[a-zA-Z]*f)",
)
# 引號**解包**（保留內文、去引號字元）：`git add "-A"` 仍偵測得到，
# 而 `echo "git add -A"` 解包後段首是 echo、錨定比對不中——同時修繞過與誤報
_QUOTE_UNWRAP_RE = re.compile(r"'([^']*)'|\"([^\"]*)\"")
# `#` 只在行首或空白後才是 shell 註解（`-c core.commentChar=#` 的 # 不是）
_COMMENT_RE = re.compile(r"(?m)(?:^|(?<=\s))#.*$")
_CMD_PREFIX_RE = re.compile(r"^(?:command|builtin)\s+")


def _command_has_danger(command: str) -> bool:
    """引號解包 + 註解剝除後，逐指令段（&& ; | 換行分隔）錨定比對。

    寧漏勿誤的已知邊界：dry-run（--dry-run / clean -n）排除；奇異前綴
    （env VAR=x、eval、bash -c 串接字串）不展開——advisory 非攔截器。
    """
    text = _QUOTE_UNWRAP_RE.sub(
        lambda m: m.group(1) if m.group(1) is not None else m.group(2), command)
    text = _COMMENT_RE.sub(" ", text)
    for seg in re.split(r"&&|\|\||;|\||\n", text):
        seg = _CMD_PREFIX_RE.sub("", seg.strip().lstrip("(").lstrip())
        if not _GIT_DANGER_RE.match(seg):
            continue
        if "--dry-run" in seg:
            continue
        if re.search(r"\bclean\s+-[a-zA-Z]*n", seg):
            continue
        return True
    return False


def check_bash_git_finalize(
    session_id: str, command: str, cwd: str, config: Dict[str, Any]
) -> Optional[str]:
    """Bash 收尾型 git 指令 + 同 cwd 存在其他活 session 有改動紀錄 → 警告文字。

    「改動紀錄」以 peer state 的 modified_files 為據——peer 可能已自行 commit
    （state 不追 VCS dirty 狀態），故措辭為提示查證而非斷言未提交。
    """
    cfg = config.get("coordination") or {}  # null 容錯
    if not cfg.get("enabled", False):
        return None
    try:
        if not _command_has_danger(command):
            return None
        norm_cwd = _norm_path(cwd)
        peers: List[str] = []
        for state in _iter_peer_states(session_id, cfg):
            if state.get("phase", "") not in ("working", "syncing") or state.get("merged_into"):
                continue
            if _norm_path((state.get("session") or {}).get("cwd", "")) != norm_cwd:
                continue
            owner = (state.get("session") or {}).get("id", "")
            n = sum(
                1 for m in state.get("modified_files", [])
                if isinstance(m, dict) and (m.get("session_id") or owner) != session_id
            )
            if n > 0 and owner and owner != session_id:
                peers.append(f"{owner[:8]}（{n} 檔）")
        if not peers:
            return None
        coord_log(session_id, "bash_finalize_warn", peers=peers, cwd=cwd)
        return (
            f"⚠️ [Guardian:CoordWarn] 偵測到全域型 git 收尾指令，且同一工作樹有其他活躍 "
            f"session 留有改動紀錄：{'、'.join(peers)}（對方可能已提交、也可能還沒——"
            "state 不追 VCS 狀態，先 git status 查證）。"
            "git add -A / reset --hard 會掃走或沖掉他人未提交的修改——"
            "請改用選擇性 staging（git add <自己的檔>），reset/clean 前先與使用者確認。"
        )
    except Exception as e:
        coord_log(session_id, "fail_open", degraded_reason=f"bash:{e}")
        _stderr_once("bash", f"[Guardian:Coord] Bash 預警異常（fail-open）：{e}")
        return None
