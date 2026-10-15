"""
handlers/stop.py — Stop hook handler

閘序：
1. Test-Fail Gate（測試未綠 + 宣告完成 → 硬阻）
1b. Reconcile Gate（收尾宣稱 vs 驗證收據：說修好要 PASS、說量了要 DONE、說試過要有執行、改碼要有 case 或 PASS、AEC 要 j／k）
    ＋ 驗證範圍閘（改了程式要有 LLM 宣告的驗證範圍、範圍內每項改完之後跑綠；wg_verify_scope）；獨立預算 reconcile_gate.max_blocks_per_turn
2. Evasion 偵測（軟糾正）／Deferral Gate（退縮歸屬）
3. KnowledgeHarvest Gate（宣告完成 → 要求 knowledge_harvest_report；Harvest-Pending 擋核不過的 item）
4. Scan-Report Gate（宣告完成但缺 anti_evasion_report emit → 硬阻）
5. Sync Reminder Gate（modified_files>0 仍未 commit/push → 軟阻；vcs-sync worker 活鎖中的 root 跳過）
+ 一般 sync block 邏輯
寫程式碼的查核閘（Reconcile／VerifyScope）擋滿 reconcile_gate.max_blocks_per_turn 後不自行放行：改送擋滿訊息要模型用
AskUserQuestion 問使用者（wg_release）；使用者在最後一次擋之後放行，才放這一回合並記 guard-reconcile.jsonl user_release。
無法互動（headless／SDK、子代理、裁判子 session）一律擋到底，不叫它問。其餘共用 stop_gate_max_blocks 的閘照舊第 3 次放行。
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (
    _ensure_state, _now_iso, write_state, read_state, output_nothing, output_block,
    append_guard_log, WORKFLOW_DIR, _atom_debug_error,
)
from wg_release_rules import in_turn, turn_start, user_turn as _user_turn
from wg_evasion import (
    claims_completion, detect_evasion, deferral_gate_reason,
    get_last_assistant_text, detect_missing_aec_emission,
    get_current_turn_text, read_transcript_tail, get_current_turn_visible_text,
)
from wg_verify_ledger import (
    receipts_of, reconcile_cfg, reconcile_gate_parts, agent_receipt_key,
    measure_cmds_of, load_self_runs, measure_parts, self_run_covered, net_unchanged_paths,
    committed_settled_paths, committed_equal_paths, git_deadline,
)
from wg_verify_scope import fix_evidence as _scope_fix_evidence, scope_cfg as _scope_cfg
from wg_release_rules import (
    parse_hits, budget_exhausted, budget_tick, exhausted_summary, is_worktree_checkout, push_required_verdict,
    dpm_instruction_text, retry_rounds_text, RELOAD_ADVICE_RE, reload_advice_verdict,
)
from wg_release import (
    exhausted_message, mark_block, user_released, released_this_turn, record_release,
    non_interactive_reason, non_interactive_message, pending_of, set_pending, clear_pending,
)
from wg_episodic import _find_session_transcript
from wg_handoff import token_warn_payload, estimate_context_usage
from wg_harvest import harvest_gate_reason, pending_gate_reason, vcs_sync_lock_active
from wg_reading_path import reading_path_note
from handlers._shared import (
    _hud_alive,
    _maybe_spawn_user_extract_worker,
    DOCDRIFT_AVAILABLE,
)

# Windows: 外呼 git/svn 時若不帶此 flag，無主控台的 hook 父行程會被配一個可見 console 視窗
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


from handlers import aec_ledger


# walk-up 定 VCS 根（零 subprocess）；與 pre_tool_use／session_start／tools 共用同一支
from wg_core import find_vcs_root as _find_vcs_root  # noqa: E402


def _norm_for_match(p: str) -> str:
    """路徑正規化供集合比對：realpath + 正斜線；Windows 檔案系統不分大小寫 → casefold。"""
    s = os.path.realpath(p).replace("\\", "/")
    return s.casefold() if sys.platform == "win32" else s


def _git_dirty_set(root: Path, paths: List[str]) -> Optional[set]:
    """一次 `git status --porcelain -z` 查整組路徑；回 dirty 集合（_norm_for_match 鍵）。

    -z：NUL 分隔、不做引號跳脫（空白/非 ASCII 路徑安全）。rename 條目的 old-path
    以無狀態前綴的獨立 NUL 段出現——此處只關心「有無未提交變更」，new-path 段已足夠，
    誤切的 old-path 段進集合也不會與任何輸入路徑相符。查詢失敗回 None。
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "-z", "--", *paths],
            capture_output=True, text=True, timeout=5, creationflags=_NO_WINDOW,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    if r.returncode != 0:
        return None
    dirty: set = set()
    for entry in (r.stdout or "").split("\0"):
        if len(entry) > 3:
            dirty.add(_norm_for_match(str(root / entry[3:])))
    return dirty


def _svn_dirty_set(root: Path, paths: List[str]) -> Optional[set]:
    """一次 `svn status` 查整組路徑；回 dirty 集合。乾淨檔無輸出；輸出行 =
    7 欄狀態 + 空格 + 路徑（依傳入形式回顯，此處傳絕對路徑）。查詢失敗回 None。"""
    try:
        r = subprocess.run(
            ["svn", "status", *paths],
            cwd=str(root), capture_output=True, text=True, timeout=5,
            creationflags=_NO_WINDOW,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    if r.returncode != 0:
        return None
    dirty: set = set()
    for line in (r.stdout or "").splitlines():
        if len(line) > 8 and line[:7].strip():
            dirty.add(_norm_for_match(line[8:].strip()))
    return dirty


def _detect_uncommitted_files(
    modified_files: List[Dict[str, Any]],
) -> Optional[List[str]]:
    """偵測 modified_files 裡仍未提交的檔案。

    回傳:
      - List[str]: 未提交檔案路徑（已去重）
      - []: 全已提交
      - None: 偵測失敗（非 git/svn 工作區）— 跳過此閘

    路徑先按 VCS 根分組（_find_vcs_root walk-up，零 subprocess），每根一次
    batch status——N 檔從 ~2N 次 git/svn 子行程降為每根 1 次。
    """
    unique_paths: List[str] = []
    seen: set = set()
    for m in modified_files:
        p = (m or {}).get("path", "")
        if p and p not in seen:
            seen.add(p)
            unique_paths.append(p)
    if not unique_paths:
        return []

    groups: Dict[tuple, List[str]] = {}
    for path in unique_paths:
        if not os.path.exists(path):
            continue
        found = _find_vcs_root(Path(path).parent)
        if found:
            groups.setdefault(found, []).append(path)
    if not groups:
        return None

    uncommitted: List[str] = []
    detected_any_vcs = False
    for (kind, root), paths in groups.items():
        dirty = _git_dirty_set(root, paths) if kind == "git" else _svn_dirty_set(root, paths)
        if dirty is None:
            continue  # 該組查詢失敗（git/svn 執行檔不存在等）——比照單檔查詢失敗略過
        detected_any_vcs = True
        uncommitted.extend(p for p in paths if _norm_for_match(p) in dirty)

    if not detected_any_vcs:
        return None
    return uncommitted


def _git_unpushed_roots(modified_files: List[Dict[str, Any]]) -> List[str]:
    """本 session 改過的檔所屬 git repo 中，本地領先 upstream 的（已 commit 未 push）。

    「上GIT」＝commit＋push 一氣：local commit 會讓 git status 乾淨、讓同步閘閉嘴，
    但對使用者而言仍未同步。無 upstream／查詢失敗的 repo 跳過（fail-open）。
    """
    roots: List[Path] = []
    seen: set = set()
    for m in modified_files:
        p = (m or {}).get("path", "")
        if not p or not os.path.exists(p):
            continue
        found = _find_vcs_root(Path(p).parent)
        if not found or found[0] != "git" or found[1] in seen:
            continue
        seen.add(found[1])
        roots.append(found[1])
    unpushed: List[str] = []
    for root in roots:
        # vcs-sync worker 正持鎖對該 root commit/push 中：領先數此刻是中間狀態，不拿來提醒
        if vcs_sync_lock_active(root):
            continue
        # 規則 WORKTREE_NO_PUSH：git worktree（git-dir ≠ git-common-dir）或分支沒 upstream → 不要求 push
        try:
            dirs = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--git-dir", "--git-common-dir"],
                capture_output=True, text=True, timeout=5, creationflags=_NO_WINDOW,
            )
            r = subprocess.run(
                ["git", "-C", str(root), "rev-list", "--count", "@{u}..HEAD"],
                capture_output=True, text=True, timeout=5, creationflags=_NO_WINDOW,
            )
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            continue
        lines = [ln.strip() for ln in (dirs.stdout or "").splitlines() if ln.strip()] if dirs.returncode == 0 else []
        gd, cd = (lines + ["", ""])[:2]
        gd = gd if os.path.isabs(gd) else str(root / gd) if gd else gd
        cd = cd if os.path.isabs(cd) else str(root / cd) if cd else cd
        verdict = push_required_verdict(str(root), is_worktree_checkout(gd, cd), r.returncode == 0)
        if not verdict.owed:
            print(f"[Guardian:SyncReminder] 規則 {verdict.rule}：{verdict.why}｜證據：{'；'.join(verdict.evidence)}", file=sys.stderr)
            continue
        try:
            n = int((r.stdout or "0").strip() or 0)
        except ValueError:
            continue
        if n > 0:
            unpushed.append(f"{root}（領先 {n} commit）")
    return unpushed


_ACCESSED_FILES_CAP = 500  # accessed_files state 條目上限（超出裁最舊）


def _harvest_accessed_files(state: Dict[str, Any], transcript_text: str) -> bool:
    """從共用 transcript 尾段一次回收 Read 過的檔案到 accessed_files；回是否有新增。

    取代 PostToolUse matcher 含 Read 的做法（每次讀檔 spawn 一個 hook 行程，
    只為記一筆路徑）。同路徑只記首見。已知邊界（消費者 episodic 統計 /
    handoff 提示 / codex 脈絡皆 best-effort 訊號，可接受）：
      - 尾窗（read_transcript_tail）涵蓋不到的極早期讀取會漏
      - `at` 為回收時刻而非讀檔時刻；同 turn 內其他 Stop hook 讀到的
        accessed_files 慢一個 turn 邊界
    """
    if not transcript_text:
        return False
    accessed = state.setdefault("accessed_files", [])
    seen = {a.get("path") for a in accessed if isinstance(a, dict)}
    added = False
    trimmed = False
    for raw in transcript_text.splitlines():
        # 廉價預篩：多數行連 tool_use/Read 字樣都沒有，免逐行 json.loads
        if '"tool_use"' not in raw or '"Read"' not in raw:
            continue
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict) or obj.get("type") != "assistant":
            continue
        content = obj.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") == "Read"
            ):
                fp = (block.get("input") or {}).get("file_path", "")
                if fp and fp not in seen:
                    seen.add(fp)
                    accessed.append({"path": fp, "at": _now_iso()})
                    added = True
    # 上限 500（重讀量大的長 session 不無限累積 state）：裁最舊；被裁路徑之後
    # 再被 Read 會重新回收（消費端皆 best-effort 統計，可接受）。
    if len(accessed) > _ACCESSED_FILES_CAP:
        state["accessed_files"] = accessed[-_ACCESSED_FILES_CAP:]
        trimmed = True
    return added or trimmed


# ─── 取用端閉環稽核（AtomAudit Gate） ───────────────────────────


def _normalize_read_path(p: str) -> str:
    return (p or "").replace("\\", "/").lower()


_ATOM_AUDIT_LIST_MAX = 3  # 收尾訊息最多列名幾顆（其餘以計數帶過）


def _audit_pointer_atom_consumption(
    state: Dict[str, Any],
) -> Optional[tuple]:
    """取用端閉環：trigger 命中（＝與本場任務域吻合）但僅以一行路標注入
    （budget skip / cold）、且整場未 Read 的 atom → 回 (reason, names) 供
    Stop 閘要求三選一表態；無候選回 None。

    寫入端有閘（write-gate/funnel），取用端此前全靠模型自律——路標的具體性
    輸給 context 實體線索時就漏（實證：trigger 命中的肥 atom 被 budget skip
    成一行、全程未展開）。防噪內建：
      - 只稽核 source=trigger（bm25/vector/related 不催——related 擴散本就低確信）
      - 本回合（使用者打字開的回合起，同伴訊息、背景通知不另開回合）注入的不催（至少給模型一個完整回合決定要不要展開）
      - 消費判定用 Stop 已回收的 accessed_files（同 turn 的 Read 先於本判定入 state）
    """
    inj_log = state.get("injection_log") or []
    if not inj_log:
        return None
    turn_seq = _user_turn(state, int(state.get("turn_seq", 0)))
    prompted = set(state.get("atom_audit_prompted") or [])
    accessed = {
        _normalize_read_path(a.get("path"))
        for a in (state.get("accessed_files") or [])
        if isinstance(a, dict)
    }
    seen: set = set()
    candidates: List[Dict[str, Any]] = []
    for rec in inj_log:
        if not isinstance(rec, dict):
            continue
        name = rec.get("name") or ""
        if not name or name in prompted or name in seen:
            continue
        if rec.get("source") != "trigger" or rec.get("form") not in ("skip", "cold"):
            continue
        if turn_seq and int(rec.get("turn_seq", 0)) >= turn_seq:
            continue  # 本 turn 才注入——不催
        rec_path = _normalize_read_path(rec.get("path"))
        suffix = f"/{name.lower()}.md"
        if any(ap == rec_path or ap.endswith(suffix) for ap in accessed):
            continue  # 已 Read（consumed）
        seen.add(name)
        candidates.append(rec)
    if not candidates:
        return None

    msg: List[str] = [
        "[Guardian:AtomAudit] 本 session 有 trigger 命中、但僅以一行路標注入"
        "（token 預算降級/cold）且全程未 Read 的 atom：",
    ]
    for rec in candidates[:_ATOM_AUDIT_LIST_MAX]:
        # 一律用絕對 path（rel 只相對該 atom 自己的 realm root，跨 realm 會斷鏈）
        msg.append(f"  - {rec['name']} → Read {rec.get('path') or rec.get('rel', '')}")
    if len(candidates) > _ATOM_AUDIT_LIST_MAX:
        msg.append(f"  …另 {len(candidates) - _ATOM_AUDIT_LIST_MAX} 顆（見 state injection_log）")
    msg.append(
        "路標命中＝該 atom 的 trigger 與本場任務域吻合，可能含本場獨有的教訓。"
        "請對每顆三選一表態（每 atom 本 session 只提醒一次，不阻工作）：\n"
        "  (a) 已從其他來源取得等價資訊——說明來源\n"
        "  (b) 確與本場任務無關——一句理由即可\n"
        "  (c) 現在補讀（Read 上列路徑）再收尾"
    )
    return "\n".join(msg), [r["name"] for r in candidates]


# ─── 注入→使用→結果 閉環歸因 ───────────────────────────────────


def _budgeted_embed_fn(raw_embed_fn, uconf: Dict[str, Any]):
    """embedding tiebreak 的全 turn 共用時間預算包裝。

    單次 tiebreak 最壞 2×embed_timeout_s（兩段 embed），多顆 atom 疊加會頂到
    Stop hook 上限。累計耗時超過 usefulness.embed_budget_s（預設 3s）→ 之後
    一律回 None（detect_atom_use 退回 lexical 主判）。預算耗盡浮 stderr 一行
    （fail-open 必告知）。raw_embed_fn 為 None 時原樣回 None。
    """
    if raw_embed_fn is None:
        return None
    try:
        budget_s = float(uconf.get("embed_budget_s", 3.0))
    except (TypeError, ValueError):
        budget_s = 3.0
    if budget_s <= 0:
        return raw_embed_fn
    spent = [0.0]
    exhausted_warned = [False]

    def _fn(a: str, b: str):
        if spent[0] >= budget_s:
            if not exhausted_warned[0]:
                exhausted_warned[0] = True
                print(
                    f"[usefulness] embed tiebreak turn budget exhausted "
                    f"({spent[0]:.1f}s ≥ {budget_s}s) — falling back to lexical",
                    file=sys.stderr,
                )
            return None
        t0 = time.monotonic()
        try:
            return raw_embed_fn(a, b)
        finally:
            spent[0] += time.monotonic() - t0

    return _fn


def _own_failing_tests(state: Dict[str, Any], session_id: str) -> List[Dict[str, Any]]:
    """failing_tests 裡 session_id == 本 session 的條目（沒蓋 sid 的舊條目不算自己的）。"""
    return [f for f in (state.get("failing_tests") or []) if isinstance(f, dict) and f.get("session_id") == session_id]


def _detect_turn_outcome(state: Dict[str, Any], last_text: str, session_id: Optional[str] = None) -> Optional[bool]:
    """3 值 success 偵測（複用既有訊號）。回 True(+1)/False(0)/None(unknown=no-op)。

      - 0（fail）：**本 turn** failing_tests 非空 / 本 turn evasion_flag /
        wisdom_retry_count≥2（error / 糾正 / retry / evasion 任一）。
      - +1（success）：宣告完成（claims_completion）且無上述 fail 訊號（硬正向）。
      - None（unknown）：既無完成宣告也無 fail 訊號 → 不動 (α,β)，防雜訊污染。

    failing_tests 只認本回合（規則 TURN_SINCE_USER_PROMPT：使用者打字開的回合起，同伴訊息、背景通知不另開回合）：
    全量累積會讓早前回合的舊失敗污染後續每個回合的 outcome。無 turn_seq 的 entry（升級前
    in-flight session）保守視為本回合（fail-open，不漏 fail 訊號）。sync gate /
    TestFailGate 等其他消費者維持全量語意不變。
    """
    turn_seq = int(state.get("turn_seq", 0))
    since = _user_turn(state, turn_seq)
    pool = _own_failing_tests(state, session_id) if session_id else (state.get("failing_tests") or [])
    failing = [
        f for f in pool
        if in_turn((f or {}).get("turn_seq", turn_seq), turn_seq, since)
    ]
    evasion = bool(state.get("evasion_flag"))
    # wisdom_retry_count 是 session 累計（FixEscalation 等消費者要它累計）；
    # outcome 只看本 turn 的增量——UPS 在 turn 起點快照 base。沒有 base（升級前
    # in-flight session）→ 沿用累計值，不漏 fail 訊號。
    retry_total = int(state.get("wisdom_retry_count", 0) or 0)
    base = state.get("wisdom_retry_turn_base")
    retry = retry_total - int(base) if base is not None else retry_total
    if failing or evasion or retry >= 2:
        return False
    if last_text and claims_completion(last_text):
        return True
    return None


def _bump_outcome_stats(state: Dict[str, Any], outcome: Optional[bool]) -> None:
    """per-turn outcome 三值計數（success/fail/unknown）。SessionEnd flush 成
    unknown 比率遙測——unknown 系統性偏高＝完成語 regex 失配、α/β 晉升軌
    靜默停滯的早期訊號。與 α/β 歸因同守 once-per-turn（caller 已以
    usefulness_attributed_seq 守門）。"""
    stats = state.setdefault(
        "outcome_stats", {"success": 0, "fail": 0, "unknown": 0}
    )
    key = "success" if outcome is True else "fail" if outcome is False else "unknown"
    stats[key] = int(stats.get(key, 0)) + 1


def _attribute_usefulness(
    state: Dict[str, Any], config: Dict[str, Any], session_id: str,
    transcript, last_text: str, transcript_text: Optional[str] = None,
) -> None:
    """per-turn 注入→使用→結果歸因：對 turn_injected + 本 turn sub-agent 注入中
    「被判 used 且 outcome 決定性」者 → record_usefulness(α/β，走 funnel)。

    once-per-turn：以 turn_seq 守門（blocked turn 多次 Stop 不重複計）。fail-open。
    transcript_text 給定時（caller 以 read_transcript_tail 共用尾段）turn 文字
    從該字串解析、不再開檔；None 則自行讀（相容直接呼叫的測試）。
    """
    try:
        uconf = (config or {}).get("usefulness", {}) or {}
        if not uconf.get("enabled", True):
            return
        turn_seq = int(state.get("turn_seq", 0))
        if turn_seq and state.get("usefulness_attributed_seq") == turn_seq:
            return  # 本 turn 已歸因

        from lib.atom_access import record_usefulness
        from wg_atoms import (
            detect_atom_use, detect_atom_use_v2, resolve_atom_path, make_embed_tiebreak_fn,
        )

        rare_min = int(uconf.get("rare_token_min", 2))
        overlap_min = float(uconf.get("lexical_overlap_min", 0.18))
        embed_fn = _budgeted_embed_fn(make_embed_tiebreak_fn(config), uconf)
        # 判用政策：v2＝行動證據（rescue 命中）優先、否定線索、路標未讀不算、去路徑噪音後
        # 共享 ≥6 才算（標註集 57 筆：precision 0.35→0.57、recall 0.84）；v1＝舊詞彙重疊（回滾用）。
        policy = str(uconf.get("attribution_policy", "v2"))
        v2_shared_min = int(uconf.get("v2_shared_min", 6))
        v2_containment_min = float(uconf.get("v2_containment_min", 0.0))

        turn_text = (
            get_current_turn_text(transcript, text=transcript_text)
            if (transcript or transcript_text) else ""
        )
        outcome = _detect_turn_outcome(state, last_text, session_id)
        _bump_outcome_stats(state, outcome)

        turn_seq_now = int(state.get("turn_seq", 0))
        rescue_map: Dict[str, List[str]] = {}
        form_map: Dict[str, str] = {}
        if policy == "v2":
            try:
                from wg_rescue import rescue_hits_for_turn, rescue_hits_for_turn_from_state
                rescue_map = rescue_hits_for_turn_from_state(state, turn_seq_now)
                if not rescue_map and "rescue_hits_by_turn" not in state:
                    rescue_map = rescue_hits_for_turn(session_id, turn_seq_now)  # 升級前 in-flight：退回讀 log
            except Exception as e:
                _atom_debug_error("usefulness:rescue_map", e)
            for rec in (state.get("injection_log") or []):
                if int(rec.get("turn_seq", -1) or -1) == turn_seq_now:
                    form_map[rec.get("name", "")] = rec.get("form_final") or rec.get("form", "ok")

        def _read(path_str: str) -> str:
            try:
                return Path(path_str).read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError, ValueError):
                return ""

        # 同一顆 atom 同一 turn 只寫一筆：先收齊各來源（主回合 / 子代理）的判定，
        # 結果一致才寫；父成功子失敗這種衝突 → unknown、不動 α/β、只留紀錄。
        pending: Dict[str, Dict[str, Any]] = {}

        def _consider(name: str, path_str: str, content: str, match_text: str,
                      decided: Optional[bool], *, origin: str = "parent") -> None:
            if decided is None or not content or not match_text:
                return
            if policy == "v2":
                # 子代理只用自己的產出判用：不借父回合文字、不借父回合 rescue（那是父的工具）；
                # 子代理拿到的是緊湊全文 blob，form 視為 ok。
                det = detect_atom_use_v2(
                    content, match_text, atom_name=name,
                    form=(form_map.get(name, "ok") if origin == "parent" else "ok"),
                    rescue_tokens=(rescue_map.get(name) if origin == "parent" else None),
                    shared_min=v2_shared_min, containment_min=v2_containment_min,
                )
            else:
                det = detect_atom_use(
                    content, match_text,
                    rare_token_min=rare_min, overlap_min=overlap_min, embed_fn=embed_fn,
                )
            if not det.get("used"):
                return
            slot = pending.setdefault(name, {"path": path_str, "outcomes": set()})
            slot["outcomes"].add(bool(decided))

        # 1) UPS per-turn 注入（turn_injected）— 比對本 turn assistant 活動文字
        for entry in (state.get("turn_injected") or []):
            name = entry.get("name", "")
            path_str = entry.get("path", "")
            if not name or not path_str:
                continue
            _consider(name, path_str, _read(path_str), turn_text, outcome)

        # 2) 本回合 sub-agent 注入（state["subagent_injections"]）
        #    只結算本回合的紀錄（規則 TURN_SINCE_USER_PROMPT：使用者打字開的回合起，同伴訊息、背景通知不另開回合）；
        #    更早回合殘留的紀錄標過期不套當輪 outcome。use 偵測比對該 agent 的 output_summary（其實際產物）；outcome 疊 agent 狀態。
        since = _user_turn(state, turn_seq)
        for rec in (state.get("subagent_injections") or []):
            if rec.get("attributed"):
                continue
            rec_turn = rec.get("turn_seq")
            if rec_turn is not None and turn_seq and not in_turn(rec_turn, turn_seq, since):
                if int(rec_turn) < since:
                    rec["attributed"] = True
                    rec["skipped"] = "stale_turn"
                continue
            status = str(rec.get("status", "") or "").lower()
            sub_outcome = outcome
            if any(k in status for k in ("error", "fail", "abort", "cancel")):
                sub_outcome = False  # agent 出錯 → fail（覆寫 turn outcome）
            # 只看子代理自己的產出；接上父回合全文會讓「父採用、子沒採用」變成假的結果衝突（Codex #8 反例）。
            # v1 政策維持舊行為（父文字併入）供回滾。
            sub_text = rec.get("output_summary", "") or ""
            match_text = sub_text if policy == "v2" else (sub_text + "\n" + turn_text)
            if not match_text.strip():
                rec["attributed"] = True
                rec["skipped"] = "no_output"
                continue
            for aname in (rec.get("atoms") or []):
                p = resolve_atom_path(aname)
                if p is None:
                    continue
                _consider(aname, str(p), _read(str(p)), match_text, sub_outcome, origin="subagent")
            rec["attributed"] = True  # 本 turn 已處理（含 no-op，避免下 turn 重算）

        attributed = []  # (atom, success) for telemetry
        conflicted: List[str] = []
        for name, slot in pending.items():
            if len(slot["outcomes"]) != 1:
                conflicted.append(name)
                continue
            decided = next(iter(slot["outcomes"]))
            record_usefulness(Path(slot["path"]), used=True, success=decided, source="hook:usefulness")
            attributed.append((name, decided))

        if turn_seq:
            state["usefulness_attributed_seq"] = turn_seq
        if attributed or conflicted:
            entry = {
                "turn_seq": turn_seq,
                "outcome": ("+1" if outcome is True else "0" if outcome is False else "unknown"),
                "atoms": [{"atom": a, "success": s} for a, s in attributed],
                "at": _now_iso(),
            }
            if conflicted:
                entry["conflicted"] = conflicted
            state.setdefault("usefulness_log", []).append(entry)
            state["usefulness_log"] = state["usefulness_log"][-50:]
    except Exception as e:
        print(f"usefulness attribution error: {e}", file=sys.stderr)


# ─── Stage 3: Deep Post-Mortem Gate（高 effort 失敗 → Claude 深寫指令）──────────


def _should_deep_postmortem(
    state: Dict[str, Any], config: Dict[str, Any], claims_done: bool,
) -> bool:
    """是否要在本 Stop 注入「深寫 post-mortem」指令。

    觸發＝(effort 訊號任一) AND (真失敗訊號任一)：
      effort：wisdom_retry_count>=2 ∨ fix_escalation_triggered ∨ friction
      real_failure：failing_tests 非空 ∨ evasion_flag ∨ 未宣告完成（not claims_done）∨ friction
      friction：使用者糾正次數 ≥ config.friction.min_hits（wg_friction）——測試全綠、
      工作也宣告完成，但人一路在糾正方向，這是原本三個訊號都抓不到的失敗型態，
      故同時算 effort 與真失敗。
    為何 AND：疊一個真失敗訊號，才把「高 effort 成功」與「反覆修不好」區分開。
    effort 只採 retry / fix_escalation——兩者都已在 track_retry 層以 failing_tests
    error-gate，是誠實的「失敗中反覆」訊號。不採同檔 edit 次數：它未 failure-gate、
    對正常重度迭代開發本就會超標（edit 次數 ≠ 失敗）。

    ★獨立預算（不與 Sync/Scan/TestFail 共用 stop_gate_max_blocks）：DPM 本就一次性
    ——deep_postmortem_done 一設即永不再觸，anti-loop 由此 one-shot 保證，無需再疊
    共用計數。曾共用實測會餓死：Sync(1)+TestFail(1) 就吃光 2-block 預算，輪到 DPM 時
    stop_count>=max 而永不觸發，偏偏那正是「反覆修不好」最該補 post-mortem 的 session。
    其它 gate 各自以自身 flag/counter 自限（sr_count / scan_report_warned），唯 DPM
    曾被共用預算綁住；正名獨立後與眾 gate 對稱。config 未關閉才觸發。

    純判定、無副作用——claims_done 由 caller 算好傳入（避免在此讀 transcript）；
    副作用（設旗標、計數、output_block）由 gate 處理。
    """
    dpm = (config or {}).get("deep_postmortem", {}) or {}
    if not dpm.get("enabled", True):
        return False
    if state.get("deep_postmortem_done"):  # 一次性即獨立預算＝1，anti-loop 由此保證
        return False
    from wg_friction import friction_triggered
    friction = friction_triggered(state, config)
    effort = (
        int(state.get("wisdom_retry_count", 0) or 0) >= 2
        or bool(state.get("fix_escalation_triggered"))
        or friction
    )
    real_failure = (
        bool(state.get("failing_tests"))
        or bool(state.get("evasion_flag"))
        or not claims_done
        or friction
    )
    return effort and real_failure


def _dpm_marker(session_id: str) -> Path:
    """DPM one-shot 的檔案側 marker。

    state 旗標在併發 hook 行程的全量覆寫下可能被舊快照競掉（旗標寫入後被他行程
    write_state 蓋回），marker 檔不受 state 覆寫影響；gate 以 state 旗標 OR marker
    判定，保證真 one-shot。
    """
    return WORKFLOW_DIR / "dpm-done" / f"{session_id}.flag"


def _dpm_trigger_text(state: Dict[str, Any], config: Dict[str, Any]) -> str:
    """DPM 指令開頭那句「為什麼觸發」：retry/fix-escalation 走原句；只靠使用者糾正
    觸發時改說糾正幾次、命中哪些詞，讓 Claude 知道要寫的是「方向被糾正」不是「測試修不好」。"""
    from wg_friction import friction_summary, friction_triggered
    parts: List[str] = []
    if int(state.get("wisdom_retry_count", 0) or 0) >= 2 or state.get("fix_escalation_triggered"):
        parts.append("失敗中反覆重試 / fix-escalation")
    if friction_triggered(state, config):
        parts.append(friction_summary(state))
    return "、".join(parts) or "高 effort 失敗"


def _cwd_is_worktree(cwd: str) -> bool:
    """cwd 所在 checkout 是不是 git worktree（規則 DPM_WORKTREE_DELIVERY 的事實）：git-dir ≠ git-common-dir。查不到 → False。"""
    if not cwd or not os.path.isdir(cwd):
        return False
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--git-dir", "--git-common-dir"],
                           capture_output=True, text=True, timeout=3, creationflags=_NO_WINDOW)
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return False
    if r.returncode != 0:
        return False
    lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()] + ["", ""]
    gd, cd = (lines[0] if os.path.isabs(lines[0]) else os.path.join(cwd, lines[0])), \
             (lines[1] if os.path.isabs(lines[1]) else os.path.join(cwd, lines[1]))
    return is_worktree_checkout(gd, cd)


def _dpm_instruction(state: Dict[str, Any], config: Dict[str, Any], cwd: str = "") -> str:
    """DPM 指令文字；worktree 隔離 session（規則 DPM_WORKTREE_DELIVERY）改要求寫進交付信由總控台代寫，不叫它 atom_write。
    有逐輪重試紀錄就在標頭下一行附證據行（規則 RETRY_COUNTS_RERUN_CYCLES，format_hit 格式）。"""
    rounds = state.get("retry_rounds") or []
    return dpm_instruction_text(_dpm_trigger_text(state, config), _cwd_is_worktree(cwd),
                                retry_rounds_text(rounds) if rounds else "")


# ─── 迴歸累積提示（驗收真命中 → 建議補測試/落 atom）───────────────


def _acceptance_regression_hint(
    state: Dict[str, Any], session_id: str, config: Dict[str, Any],
) -> Optional[str]:
    """驗收裁判真命中的迴歸累積提示（非強制）：本 session 的 acceptance-audit.jsonl
    有 verdict=fail 且 severity=high（enforce 級——回測兩輪 4/4 零誤擋的那一級）
    → 收尾訊息搭車建議 (a) 補測試案例 (b) 模式類落 atom。

    純 piggyback（同 token 預警模式）：只搭既有 block 訊息帶出，不獨立打斷；
    一次性（acceptance_hint_emitted，隨該 gate 的 write_state 固化）；
    不建佇列不建表——做不做由模型當場判斷，誤判忽略即可。
    fail-open：讀檔/解析失敗 stderr 浮訊號後回 None。
    """
    try:
        cfg = (config or {}).get("acceptance_regression_hint", {}) or {}
        if not cfg.get("enabled", True):
            return None
        if state.get("acceptance_hint_emitted"):
            return None
        audit_path = WORKFLOW_DIR / "acceptance-audit.jsonl"
        if not audit_path.exists():
            return None
        slugs: List[str] = []
        hits = 0
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            if session_id not in line:  # 廉價預篩，免逐行 json.loads
                continue
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(rec, dict) or rec.get("session_id") != session_id:
                continue
            if rec.get("verdict") != "fail" or rec.get("severity") != "high":
                continue
            hits += 1
            slug = rec.get("task_slug") or Path(str(rec.get("spec_path", ""))).stem
            if slug and slug not in slugs:
                slugs.append(slug)
        if not hits:
            return None
        return (
            f"\n[Guardian:RegressionHint] 本 session 驗收裁判有 {hits} 筆真命中級"
            f"判定（fail/high；任務：{', '.join(slugs[:3])}）。"
            "抓到的漏修完就過去＝同型錯下次照犯，建議（非強制、當場判斷）：\n"
            "  (a) 在該專案為漏掉的行為補一個測試案例（永久防線）\n"
            "  (b) 屬跨任務模式類教訓 → atom_write 落 atom\n"
            "裁判誤判或防線已存在則忽略即可，不建佇列不追蹤。"
        )
    except Exception as e:
        print(f"[Guardian:RegressionHint] hint error (fail-open): {e}", file=sys.stderr)
        return None


def _move_inputs(state: Dict[str, Any], receipt_key: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """規則 MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE 的事實配對：(要查的搬移, 可以拿來對的收據)。
    子代理收尾（receipt_key＝sid#agent:<id>）只查這個子代理搬的、用它自己的收據；主 session 收尾查本 session 全部搬移
    （含子代理搬的），收據是主帳加上那些子代理各自的收據（子代理自己跑了 scan／sample 也算數）。"""
    sid, _, aid = str(receipt_key).partition("#agent:")
    moved = [m for m in state.get("moved_code_dirs") or [] if isinstance(m, dict) and m.get("session_id") == sid]
    if aid:
        return [m for m in moved if m.get("agent_id", "") == aid], receipts_of(state, receipt_key)
    receipts = list(receipts_of(state, sid))
    for a in dict.fromkeys(m.get("agent_id") for m in moved if m.get("agent_id")):
        receipts += receipts_of(state, agent_receipt_key(sid, a))
    return moved, receipts


def _verify_gates(
    state: Dict[str, Any], session_id: str, turn_seq: int, last_text: str,
    transcript, transcript_text: str, own_mod_files: List[Dict[str, Any]],
    rg_cfg: Dict[str, Any], sg_cfg: Dict[str, Any], aec: Dict[str, Any], aec_emitted: bool,
    claims: List[str] = (), pending: bool = False, goal: bool = False, goal_cfg: Optional[Dict[str, Any]] = None,
) -> tuple:
    """對帳閘＋驗證範圍閘的判定。回 (寫碼查核擋訊息或 None, 收尾報告欄 (e) 擋訊息或 None, 種類 reconcile／scope／"",
    提醒或 None：背景全量新記的範圍漏判)。寫碼查核＝對帳 (a)～(d)＋驗證範圍；(e) 屬記憶與報告類，擋滿時不走放行詢問（分開回）。
    goal＝True（只有主 session 的 Stop 傳）另判需求目標的 (f1)(f2)，併進寫碼查核；子代理與裁判不跑目標對照。
    (a)(b)(c) 對 last_text 與 claims（pending 承接的先前宣稱）；(d) 與驗證範圍不看措辭，有改碼紀錄就判（last_text 空也判）。
    自寫收據（_runs/）驗證範圍（入帳找漏判）與 (a) 共用，只讀一次。寫碼查核整個過了 → 這份驗證範圍記成結案。
    判定本身出錯 → 寫碼查核擋訊息（一律擋，仍吃 reconcile_gate.max_blocks_per_turn 預算，擋滿後改問使用者）＋stderr＋guard_log。"""
    receipts = receipts_of(state, session_id)
    reason: Optional[str] = None
    report: Optional[str] = None
    kind = ""
    advice: Optional[str] = None
    _runs: List[List[Dict[str, Any]]] = []
    # 改過又原樣還原的檔（與 HEAD 相同、本 session 之後沒 commit、同根本 session 改過的檔全都乾淨）不算改碼：補案例與驗證範圍都不欠；
    # 判不出來照算改了。同根乾淨看 session 全部改檔（主 session＋所有子代理），剔除只套在這次受查的 own_mod_files
    sid = str(session_id).split("#agent:", 1)[0]
    session_paths = [m["path"] for m in state.get("modified_files") or []
                     if isinstance(m, dict) and m.get("path") and m.get("session_id", sid) == sid]
    for _agent_mods in (state.get("agent_modified_files") or {}).values():
        session_paths += [m["path"] for m in _agent_mods or [] if isinstance(m, dict) and m.get("path")]
    git_dl = git_deadline()           # 兩種「內容回到某狀態」的豁免（這裡與下面 commit 快照）共用一個查 git 的整支預算
    try:
        same = net_unchanged_paths(own_mod_files, state.get("last_commit_turn_seq"), session_paths=session_paths,
                                   deadline=git_dl)
    except Exception as e:  # noqa: BLE001
        same = []
        print(f"[Guardian:ReconcileGate] 判斷改過又還原的檔失敗，照算改了：{type(e).__name__}: {e}", file=sys.stderr)
    if same:
        gone = set(same)
        own_mod_files = [m for m in own_mod_files if (m or {}).get("path") not in gone]
        print("[Guardian:ReconcileGate] 規則 NET_UNCHANGED：改過又原樣還原（與 HEAD 相同、之後沒 commit），不算改碼："
              + "、".join(Path(p).name for p in same[:5]), file=sys.stderr)
    # 內容等於已提交版本（merge 取 theirs、退回 main 版再還原）或與 HEAD 只差註解 → 不是本 session 改碼（CONTENT_EQUALS_COMMITTED／
    # COMMENT_ONLY_CHANGE）；判不出來照算改了
    try:
        equal = committed_equal_paths(own_mod_files, rg_cfg, state.get("last_commit_turn_seq"), state.get("committed_new_code"),
                                      session_paths=session_paths, deadline=git_dl)
    except Exception as e:  # noqa: BLE001
        equal = {}
        print(f"[Guardian:ReconcileGate] 判斷內容是否等於已提交版本失敗，照算改了：{type(e).__name__}: {e}", file=sys.stderr)
    if equal:
        own_mod_files = [m for m in own_mod_files if (m or {}).get("path") not in equal]
        for v in equal.values():
            print(f"[Guardian:ReconcileGate] 規則 {v.rule}：{v.why}｜證據：{'；'.join(v.evidence)}", file=sys.stderr)

    def _self_runs() -> List[Dict[str, Any]]:
        if not _runs:
            _runs.append(load_self_runs() or [])
        return _runs[0]

    if rg_cfg.get("enabled", True):
        try:
            _, probe = get_current_turn_visible_text(transcript, text=transcript_text)
            names = probe.get("turn_tool_names_all") or probe.get("turn_tool_names") or []
            try:                  # 只接匯入失敗；部位表讀不到（MapReadError）要往外拋，走下面的判定錯誤路徑一律擋
                from wg_overview import _lookup as _lk
            except ImportError:
                _lk, mcmds = None, []
            else:
                mcmds = measure_cmds_of(own_mod_files, _lk)
            since = turn_start(_user_turn(state, turn_seq), session_id, own_mod_files, receipts)
            reason, report = reconcile_gate_parts(
                last_text, receipts, turn_seq, names, own_mod_files, rg_cfg,
                aec=aec if aec_emitted else None, aec_emitted=aec_emitted, sid=session_id,
                measure_cmds=mcmds, claims=claims, pending=pending,
                case_settled=lambda owed: committed_settled_paths(state.get("commit_snapshot"), owed, session_paths,
                                                                  deadline=git_dl),
                committed_new=state.get("committed_new_code"), user_turn=since,
                exec_this_turn=in_turn((state.get("exec_turn_seq") or {}).get(session_id), turn_seq, since),
                **dict(zip(("moves", "move_receipts"), _move_inputs(state, session_id))),
                move_scan_hits=state.get("move_scan_hits") or {},
                self_covered=(lambda: self_run_covered(measure_parts(own_mod_files, _lk), _self_runs())) if _lk else None,
                # (a) 說修好：有驗證範圍宣告就認宣告範圍的收據（同一個判斷只一份答案），沒宣告才退回檔名對應
                scope_fix=(lambda: _scope_fix_evidence(state, session_id, own_mod_files, receipts, rg_cfg, _lk, _self_runs()))
                if _lk and sg_cfg.get("enabled", True) else None,
            )
            kind = "reconcile" if reason or report else ""
        except Exception as e:
            reason = (f"[Guardian:ReconcileGate] 判定錯誤，一律擋：{type(e).__name__}: {e}。"
                      "修好設定或回報；先別宣告完成")
            kind = "reconcile"
            print(reason, file=sys.stderr)
            append_guard_log("reconcile", {"session_id": session_id, "turn_seq": turn_seq, "error": repr(e)[:200]})
    closable = None
    if sg_cfg.get("enabled", True):
        # 驗證範圍：該測哪些由 LLM 宣告（need_goal verify_scope），這裡只查有沒有宣告、範圍內每項有沒有改完之後跑綠的收據；
        # 背景全量的自寫收據先入帳（紅掉的測試名拿去找範圍漏判，新記的當提醒送回）
        try:
            import wg_verify_scope as vs
            notes = vs.sync_runs(_self_runs())
            if notes:
                advice = "\n".join(notes)
            if own_mod_files:
                from wg_overview import _lookup
                s_reason, closable = vs.gate_reason(state, session_id, own_mod_files, receipts, rg_cfg, _lookup, sg_cfg,
                                                    self_runs=_self_runs())
                if s_reason:
                    reason = f"{reason}\n{s_reason}" if reason else s_reason
                    kind = kind or "scope"
        except Exception as e:
            s_err = (f"[Guardian:VerifyScope] 判定錯誤，一律擋：{type(e).__name__}: {e}。"
                     "修好設定或回報；先別宣告完成")
            reason = f"{reason}\n{s_err}" if reason else s_err
            kind = kind or "scope"
            closable = None
            print(s_err, file=sys.stderr)
            append_guard_log("scope", {"session_id": session_id, "turn_seq": turn_seq, "error": repr(e)[:200]})
    if goal:
        # 需求目標（4.5）：(f1) 改了程式還沒回頭對照不看措辭、每次都判；(f2) 完整對照與 (f3) 改到的部位都掛目標只在交付邊界
        # （宣告完成、擋滿待查的原宣稱、本回合交了收尾檢核）判。併進寫碼查核：同一個擋滿問使用者、同一個 pending；
        # (f3) 擋訊息帶規則行，擋次預算單獨計次。state 與 transcript 交給 (f3) 從對話補掛補交的定位四行
        try:
            from wg_need_goal import goal_gate_reason
            g_reason = goal_gate_reason(session_id, bool(claims_completion(last_text) or claims or aec_emitted), goal_cfg,
                                        state=state, transcript_path=str(transcript) if transcript else "")
        except Exception as e:  # noqa: BLE001
            g_reason = (f"[Guardian:ReconcileGate] 需求目標對照判定錯誤，一律擋：{type(e).__name__}: {e}。"
                        "修好目標檔（workflow/need-goal/）或回報；先別宣告完成")
            print(g_reason, file=sys.stderr)
            append_guard_log("reconcile", {"session_id": session_id, "turn_seq": turn_seq, "goal_error": repr(e)[:200]})
        if g_reason:
            reason = f"{reason}\n{g_reason}" if reason else g_reason
            kind = "reconcile"
    if closable and not reason:
        # 寫碼查核整個過了：這份驗證範圍記成結案（之後範圍外的測試紅了，才找得到要連回哪一次宣告）
        try:
            vs.close(state, session_id, closable)
        except Exception as e:  # noqa: BLE001
            print(f"[Guardian:VerifyScope] 結案寫帳失敗（不擋）：{type(e).__name__}: {e}", file=sys.stderr)
            append_guard_log("scope", {"session_id": session_id, "turn_seq": turn_seq, "close_error": repr(e)[:200]})
    return reason, report, kind, advice


ASK_HINT = "要問使用者問題請用 AskUserQuestion，不要用文字結束回合。"     # 寫碼查核每次 Stop 都判，用文字發問也會被擋


LEGACY_PENDING = ("[Guardian:ReconcileGate] 先前擋滿的查核紀錄是舊格式，沒有原宣稱可以重查：補證據解不了，"
                  "只能照【收尾放行確認】問使用者放行。")


def _unknown_write_reason(unknown: List[Dict[str, Any]]) -> Optional[str]:
    """寫入目標不明的指令（post_tool_use 記的未知寫入）→ 擋訊息：不知道改了哪些檔，補案例與驗證範圍都查不了。"""
    if not unknown:
        return None
    heads = "；".join(f"`{str(u.get('cmd', ''))[:60]}`" for u in unknown[-3:])
    return (f"[Guardian:ReconcileGate] 有 {len(unknown)} 筆寫入目標不明的指令（{heads}）：不知道改了哪些檔，"
            "補驗證案例與驗證範圍都查不了，不能當成沒改檔。")


def _code_check_text(input_data: Dict[str, Any], transcript, transcript_text: str) -> str:
    """寫碼查核（TestFail、對帳 (a)(b)(c)、pending 原宣稱）看的最後一句：先用 hook 輸入的 last_assistant_message，沒有才退回
    transcript，且不套退避偵測用的 30 字下限（長說明之後只回一句「修好了，全部完成。」也要判這句）。"""
    return (str(input_data.get("last_assistant_message") or "")
            or get_last_assistant_text(transcript, text=transcript_text, min_chars=1))


def _code_gate_to_the_end(input_data: Dict[str, Any], config: Dict[str, Any], state: Optional[Dict[str, Any]],
                          receipt_key: str, own: List[Dict[str, Any]], transcript_path: str, why: str,
                          log_extra: Dict[str, Any], unknown: Optional[List[Dict[str, Any]]] = None) -> None:
    """沒有人能回答 AskUserQuestion 的收尾（子代理、裁判子 session）：只跑寫碼查核閘（對帳 (a)～(d)＋驗證範圍＋未知寫入），
    有原因就擋到底（不計預算、不問使用者、不看放行答案）；(e) 與其他 Stop 閘不跑；自己沒改檔也沒有未知寫入才放行。
    (d) 與驗證範圍不看措辭：沒有收尾文字（transcript 讀不到）也照判。"""
    session_id = input_data.get("session_id", "") or ""
    unknown = list(unknown or [])
    if not state or not (own or unknown):
        output_nothing()
        return
    transcript = Path(transcript_path) if transcript_path and Path(transcript_path).is_file() else None
    transcript_text = read_transcript_tail(transcript)
    last_text = _code_check_text(input_data, transcript, transcript_text)
    turn_seq = int(state.get("turn_seq", 0))
    rg_cfg, sg_cfg = reconcile_cfg(config), _scope_cfg(config)
    if not (rg_cfg.get("enabled", True) or sg_cfg.get("enabled", True)):
        output_nothing()
        return
    reason, kind = None, ""
    if own:
        reason, _report, kind, _advice = _verify_gates(state, receipt_key, turn_seq, last_text, transcript,
                                                       transcript_text, own, rg_cfg, sg_cfg, {}, False)
        write_state(session_id, state)      # 驗證範圍的宣告結案等判定副作用
    u_reason = _unknown_write_reason(unknown)
    if u_reason:
        reason, kind = (f"{u_reason}\n{reason}" if reason else u_reason), "reconcile"
    if not reason:
        output_nothing()
        return
    gate = "VerifyScope" if kind == "scope" else "ReconcileGate"
    summary = reason.split("\n")[1].strip() if "\n" in reason else reason
    append_guard_log("reconcile", {"session_id": session_id, "turn_seq": turn_seq, "kind": kind,
                                   "reason": reason[:300], **log_extra})
    output_block(f"{non_interactive_message(gate, None, summary, why)}\n原擋訊息：\n{reason}")


def handle_subagent_stop(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    """SubagentStop：看子代理自己改的檔（agent_modified_files[agent_id]）與自己的收據（agent_receipt_key），寫碼查核擋到底。"""
    session_id = input_data.get("session_id", "") or ""
    agent_id = str(input_data.get("agent_id") or "")
    state = read_state(session_id) if session_id and agent_id else None
    own = list(((state or {}).get("agent_modified_files") or {}).get(agent_id) or [])
    unknown = list(((state or {}).get("agent_unknown_writes") or {}).get(agent_id) or [])
    _code_gate_to_the_end(input_data, config, state, agent_receipt_key(session_id, agent_id), own,
                          input_data.get("agent_transcript_path") or "", "子代理 Stop",
                          {"event": "subagent_block", "agent_id": agent_id}, unknown)


def handle_judge_stop(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    """裁判子 session（CLAUDE_COMPANION_JUDGE=1）的 Stop：dispatcher 其他事件照舊早退，Stop 只跑寫碼查核閘，擋到底。
    改檔、未知寫入與收據來自 post_tool_use.handle_judge_post_tool_use 的最小記帳。"""
    session_id = input_data.get("session_id", "") or ""
    state = read_state(session_id) if session_id else None
    own = [m for m in ((state or {}).get("modified_files") or []) if (m or {}).get("session_id", session_id) == session_id]
    unknown = [u for u in ((state or {}).get("unknown_writes") or []) if (u or {}).get("session_id", session_id) == session_id]
    _code_gate_to_the_end(input_data, config, state, session_id, own, input_data.get("transcript_path") or "",
                          "裁判子 session（CLAUDE_COMPANION_JUDGE=1）", {"event": "judge_block"}, unknown)


_MCP_CODE_DIR = Path(__file__).resolve().parents[2] / "tools" / "workflow-guardian-mcp"


def _running_mcp_pids(timeout: float = 5.0) -> Optional[set]:
    """正在跑 workflow-guardian-mcp/server.js 的 node 程序 pid；列不出回 None（判不出）。只在收尾文字叫使用者重載時才查（約 1 秒）。"""
    if sys.platform == "win32":
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
               "Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Where-Object { $_.CommandLine -like "
               "'*workflow-guardian-mcp*server.js*' } | ForEach-Object { $_.ProcessId }"]
    else:
        cmd = ["ps", "-eo", "pid=,args="]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[Guardian:ReloadAdvice] 列不出工具服務程序，判不出重載建議要不要擋：{type(e).__name__}", file=sys.stderr)
        return None
    if r.returncode != 0:
        print("[Guardian:ReloadAdvice] 列工具服務程序回非零，判不出重載建議要不要擋", file=sys.stderr)
        return None
    if sys.platform == "win32":
        return {int(x) for x in r.stdout.split() if x.isdigit()}
    return {int(ln.split()[0]) for ln in r.stdout.splitlines()
            if "workflow-guardian-mcp" in ln and "server.js" in ln and ln.split()[0].isdigit()}


def _mcp_load_facts(boot_dir: Optional[Path] = None, code_dir: Optional[Path] = None
                    ) -> Tuple[List[Tuple[Optional[float], float]], Optional[float]]:
    """規則 RELOAD_ADVICE_ALREADY_LOADED 的事實，以正在跑的服務程序為準（_running_mcp_pids）：有啟動紀錄的給
    （啟動時載入的程式版本毫秒, 心跳秒）；在跑卻沒有紀錄或紀錄壞了的給（None, 現在）＝判不出；有紀錄但程序已不在的不算
    （被殺掉的測試服務來不及刪檔）；列不出程序就不給任何紀錄。另回磁碟上的程式版本毫秒（server.js 與 lib/*.js 最新的修改時間，
    和服務端 codeMtime 同算法；讀不到回 None）。"""
    boot_dir = boot_dir or Path(WORKFLOW_DIR) / "mcp-boot"
    code_dir = code_dir or _MCP_CODE_DIR
    by_pid: Dict[int, Tuple[float, float]] = {}
    for f in sorted(boot_dir.glob("*.json")) if boot_dir.is_dir() else []:
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
            by_pid[int(rec["pid"])] = (float(rec["code_mtime"]), float(rec["heartbeat_at"]) / 1000)
        except (OSError, ValueError, KeyError, TypeError) as e:
            print(f"[Guardian:ReloadAdvice] 讀不了工具服務啟動紀錄 {f.name}，跳過：{type(e).__name__}", file=sys.stderr)
    running = _running_mcp_pids()
    now = time.time()
    records: List[Tuple[Optional[float], float]] = [] if running is None else [
        by_pid.get(pid, (None, now)) for pid in sorted(running)]
    try:
        disk: Optional[float] = max(p.stat().st_mtime_ns for p in [code_dir / "server.js", *(code_dir / "lib").glob("*.js")]) / 1e6
    except (OSError, ValueError):
        disk = None
    return records, disk


def handle_stop(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    max_blocks = config.get("stop_gate_max_blocks", 2)
    stop_count = state.get("stop_blocked_count", 0)
    phase = state.get("phase", "working")

    # ── Test-Fail Gate ────────────────────────────────────────────
    # 只認本 session 自己的條目（共用／merged state 下隔壁 session 的紅測不擋本 session；沒蓋 sid 的舊條目視為他人）
    failing = _own_failing_tests(state, session_id)
    cwd = state.get("session", {}).get("cwd", "") or input_data.get("cwd", "")
    # transcript 先用 hook 輸入給的路徑：session 中途切進 worktree（cwd 換了）之後，transcript 寫在新 cwd 的資料夾，
    # 拿 state 裡開場時的 cwd 推會找不到 → 擋的位置記成 0、讀不到 AskUserQuestion 的放行答案。輸入沒給或檔不在才自己推。
    _tp_in = str(input_data.get("transcript_path") or "")
    transcript = (Path(_tp_in) if _tp_in and Path(_tp_in).is_file()
                  else _find_session_transcript(session_id, cwd) if cwd else None)
    # 單次 tail-read：本函式所有 transcript 消費者（last_text / token 預警 /
    # usefulness turn 文字）共用同一份尾段，取代先前各自全檔讀取。
    transcript_text = read_transcript_tail(transcript)
    last_text = get_last_assistant_text(transcript, text=transcript_text)          # 退避偵測等：只看 >30 字的段落
    code_text = _code_check_text(input_data, transcript, transcript_text)          # 寫碼查核：真正的最後一句
    # accessed_files 回收（取代 per-Read PostToolUse hook）——先寫進 state，
    # 後續任何 gate 的 write_state 也會一併固化；此處立即寫防走到不寫 state 的路徑。
    # 關回合：下一則 UserPromptSubmit 才是新回合的第一句（turn_prompts 重開，見 ups_gates.track_turn_prompts）。
    turn_was_open = bool(state.get("turn_open"))
    state["turn_open"] = False
    if _harvest_accessed_files(state, transcript_text) or turn_was_open:
        write_state(session_id, state)
    # 殘檔帳本：每次 Stop 掃一次 session scratchpad 進帳（模型沒 emit 報告也不漏）。fail-open。
    try:
        aec_ledger.collect_at_completion(session_id, cwd, None, int(state.get("turn_seq", 0)))
    except Exception:
        pass

    # ── Layer 1: token 預警 proxy（piggyback 既有 block，不獨立打斷）──────
    # 早段算一次預警句（純函式、無副作用）；於下方各 gate 將 output_block(reason)
    # 前用 _piggyback append。token_warn_emitted 旗標只在「實際 append」時才標，
    # 並隨該 gate 的 write_state 固化（一次性、整 session 一次）。詳見
    # plans/wise-wobbling-gem.md Layer 1 與 Q3 門檻取捨。
    _token_warn = token_warn_payload(
        state, config, transcript, transcript_text=transcript_text
    )
    # 迴歸累積提示同為 piggyback payload：驗收裁判真命中 → 建議補測試/落 atom。
    _accept_hint = _acceptance_regression_hint(state, session_id, config)
    # 閱讀路徑影響（G12）：改碼回合量一次，附在這次擋的訊息與 stderr；只量不擋、不計預算（wg_reading_path）
    try:
        _reading_path = reading_path_note(state, session_id, config)
    except Exception as e:  # noqa: BLE001
        _reading_path = f"[Guardian:ReadingPath] 這次對閱讀路徑的影響量不出來：hook 內部錯誤 {type(e).__name__}: {e}"
    if _reading_path:
        print(_reading_path, file=sys.stderr)
        write_state(session_id, state)

    _tpath = str(transcript) if transcript else None

    def _piggyback(reason: str, gate: Optional[str] = None) -> str:
        """附 token 預警／驗收提示／閱讀路徑影響。gate 有給（對帳／驗證範圍閘＝"reconcile"）就記這個閘最後一次擋的位置；那條路是先 write_state
        再呼叫本函式，所以記完自己再寫一次 state，擋的位置才不會遺失。"""
        if gate:
            mark_block(state, session_id, gate, _tpath, int(state.get("turn_seq", 0)))
        if _token_warn:
            state["token_warn_emitted"] = True
            reason = reason + _token_warn
        if _accept_hint:
            state["acceptance_hint_emitted"] = True
            reason = reason + _accept_hint
        if _reading_path:
            reason = f"{reason}\n{_reading_path}"
        if gate:
            write_state(session_id, state)
        return reason

    # ── 各閘共用前置變數 ─────────────────────────────────────────
    mod_files_all = state.get("modified_files", []) or []
    # 只認「本 session 自己 Edit/Write 的檔」——共用工作樹/merged state 下，他 session
    # 改的 core 檔（session_id 不符）不得誤觸發本 session 的收尾檢核。未標記 session_id
    # 的 legacy entry 保守視為本 session（fail-open，不漏防退避）。
    own_mod_files = [
        m for m in mod_files_all
        if (m or {}).get("session_id", session_id) == session_id
    ]
    # 純 VCS commit turn 豁免收尾檢核：本 turn 已把工作寫進 VCS 歷史（可稽核＝與「藏」相反），
    # anti-evasion 目的在 commit 那刻消解。不開後門——豁免綁「本 turn 真的 commit 了」
    # （post_tool_use 記的 last_commit_turn_seq），而非「本 turn 沒 Edit」；光宣告完成不 commit
    # 仍被擋。未 commit 就 commit 的檔仍由 SyncReminder / 一般 block 兜底。
    # 「本回合」照規則 TURN_SINCE_USER_PROMPT：使用者打字開的回合起到現在（同伴訊息、背景通知不另開回合）。
    turn_seq = int(state.get("turn_seq", 0))
    _since = _user_turn(state, turn_seq)
    committed_this_turn = bool(turn_seq) and in_turn(state.get("last_commit_turn_seq"), turn_seq, _since)
    # emit 滿足＝本回合有呼叫 anti_evasion_report。★雙鍵（回合 **且** session_id）為硬性：
    # merged/sibling session 共用同一實體 state 檔且共用同一 turn_seq 計數器，唯 session_id 能
    # 區辨——否則隔壁 session 的 emit 會誤放行本 session（重演 own_mod_files 要防的洩漏）。
    # bool(turn_seq) 護欄：防 turn_seq==0 的 fallback state 以 0==0 假滿足。
    aec = state.get("anti_evasion_report") or {}
    emitted_this_turn = (
        bool(turn_seq)
        and in_turn(aec.get("turn_seq"), turn_seq, _since)
        and aec.get("session_id") == session_id
    )

    if failing and claims_completion(code_text):
        state["stop_blocked_count"] = stop_count + 1
        reason = _piggyback(
            f"[Guardian:TestFailGate] 測試未綠（{len(failing)} 項失敗），"
            "不得宣告完成。\n"
            + "\n".join(
                f"  - {f.get('cmd', '')[:60]}: "
                f"{(f.get('summary', '').splitlines() or [''])[0][:100]}"
                for f in failing[-3:]
            )
            + "\n選 (a) 修復 (b) 明確說明為何不修並標記為已知 regression "
            "(c) 降級任務定義。不得籠統帶過。"
        )
        write_state(session_id, state)
        output_block(reason)
        return

    # ── Reconcile Gate（收尾宣稱 vs 驗證收據）＋ 驗證範圍閘──────────
    # 緊接 TestFailGate 之後、evasion 偵測之前（correctness 閘優先）。不吃共用 stop_gate_max_blocks：
    # 獨立預算 reconcile_gate.max_blocks_per_turn（state reconcile_gate_turn[sid]={turn,count}）；預算與放行的「回合」是使用者
    # 本人打字開的回合（_user_turn：同伴訊息、背景通知、hook 回饋續跑都不開新回合、不重置次數）。
    # 寫碼查核（對帳 (a)～(d)＋驗證範圍）擋滿後不放行：記 pending_release、改送擋滿訊息要模型問使用者；每次擋（不等擋滿）都查
    # 使用者有沒有在最後一次擋之後放行（wg_release.user_released）→ 放這一回合、清 pending 與計數、guard-reconcile.jsonl
    # 記 user_release（健檢列 red）；擋之前的舊答案不算。
    # pending 跨回合承接：換回合也不重給預算，查核仍不過就直接送擋滿訊息。
    # 不看措辭的部分（(d) 補案例、驗證範圍）每次 Stop 都判，last_text 空也判；(a)(b)(c) 對宣稱，pending 帶著第一次擋滿時的
    # 宣稱原話（claims，之後的文字不附加也擠不掉），換一句話也拿原話重查。pending 只在兩種情況清：重新查核後原因真的消失，
    # 或使用者合格放行：「沒有執行查核」不等於「查核通過」。舊版 pending 沒帶 claims → 原宣稱無從重查 → 照擋，只能使用者放行。
    # (e) 收尾報告欄屬記憶與報告類：照舊第 3 次放行並記 reconcile_overflow（健檢 red），不走放行詢問；與寫碼部分同時擋滿時分開列。
    # 背景全量新記的範圍漏判只提醒（stderr；擋時併進 reason）。
    _rg_cfg = reconcile_cfg(config)
    _sg_cfg = _scope_cfg(config)
    if _rg_cfg.get("enabled", True) or _sg_cfg.get("enabled", True):
        _pend = pending_of(state, session_id, "reconcile")
        _prev_claims = [str(c) for c in (_pend or {}).get("claims") or []]
        _code, _report, _vg_kind, _vg_advice = _verify_gates(
            state, session_id, turn_seq, code_text, transcript, transcript_text, own_mod_files,
            _rg_cfg, _sg_cfg, aec, emitted_this_turn, claims=_prev_claims, pending=_pend is not None,
            goal=True, goal_cfg=config,
        )
        if _vg_advice:
            print(_vg_advice, file=sys.stderr)
            append_guard_log("scope", {"session_id": session_id, "turn_seq": turn_seq, "advisory": _vg_advice[:200]})
        if _pend is not None and "claims" not in _pend:
            _code = f"{_code}\n{LEGACY_PENDING}" if _code else LEGACY_PENDING
            _vg_kind = _vg_kind or "reconcile"
        _pend_cleared = False
        if _code is None and _pend:
            clear_pending(state, session_id, "reconcile")            # 重新查核過了（原因真的消失）→ 清 pending
            _pend, _pend_cleared = None, True
        _uturn = _user_turn(state, turn_seq)
        if _code and released_this_turn(state, session_id, "reconcile", _uturn):
            print("[Guardian:ReconcileGate] 使用者已放行這一回合，本次不擋", file=sys.stderr)
            _code = None
        if _code or _report:
            # 規則 BLOCK_BUDGET_PER_RULE：預算每條規則（擋訊息的字母）各自計次，同一條擋滿 max 才算擋滿；
            # 舊格式紀錄（整場一個 count）不承接。_count＝本回合各條的最大值（(e) overflow 與 log 沿用）
            _budget = state.setdefault("reconcile_gate_turn", {})
            _rec = _budget.get(session_id) if isinstance(_budget.get(session_id), dict) else None
            _letters = parse_hits(_code or "") or (["*"] if _code else [])
            _max = int(_rg_cfg.get("max_blocks_per_turn", 2))
            _full_rules = budget_exhausted(_rec, _uturn, _max, _letters)
            _count = int(_rec.get("count", 0)) if _rec and int(_rec.get("turn", -1)) == _uturn else 0
            _code_full = bool(_code) and (bool(_full_rules) or _pend is not None)
            if _full_rules:
                print(f"[Guardian:ReconcileGate] 規則 BLOCK_BUDGET_PER_RULE：本回合條目 {'、'.join(_full_rules)} 各擋滿 {_max} 次",
                      file=sys.stderr)
            # 每次擋都查放行（不等擋滿）：最後一次擋之後使用者在 AskUserQuestion 選了放行或打字放行 → 放這一回合。無法互動的不查。
            _noninteractive = non_interactive_reason(input_data, _tpath) if _code else None
            _no_ask = _noninteractive if _code_full else None
            _how = user_released(state, session_id, "reconcile", _tpath) if _code and not _noninteractive else None
            _both = "\n".join(x for x in (_code, _report) if x)
            if _how:
                record_release(state, session_id, "reconcile", _uturn)
                mark_block(state, session_id, "reconcile", _tpath, turn_seq)   # 這個答案用掉了：之後要放行得再答一次
                clear_pending(state, session_id, "reconcile")
                _budget[session_id] = {"turn": _uturn, "count": 0}
                append_guard_log("reconcile", {
                    "event": "user_release", "session_id": session_id, "turn_seq": turn_seq, "kind": _vg_kind,
                    "via": _how, "count": _count, "reason": _code[:300],
                })
                print(f"[Guardian:ReconcileGate] 使用者放行這一回合（{_how}），記 user_release", file=sys.stderr)
                _code = None
            if not _code and _report and _count >= _max:
                # 只剩 (e)：照 97128e5 的行為，第 3 次放行並記 reconcile_overflow（健檢 red）
                state.setdefault("reconcile_overflow", {})[session_id] = {
                    "turn": turn_seq, "at": _now_iso(), "kind": "report", "reason": _report[:300],
                }
                append_guard_log("reconcile_overflow", {
                    "session_id": session_id, "turn_seq": turn_seq, "kind": "report", "count": _count,
                    "reason": _report[:300],
                })
                print(f"[Guardian:ReconcileGate] 本回合已擋 {_count} 次（收尾報告欄），這次放行但記 reconcile_overflow（健檢列 red）",
                      file=sys.stderr)
                write_state(session_id, state)
            elif not _code and not (_report and _count < _max):
                write_state(session_id, state)
            else:
                _budget[session_id] = budget_tick(_rec, _uturn, _letters or (["e"] if _report else []))
                _gate = "VerifyScope" if _vg_kind == "scope" else "ReconcileGate"
                if _code_full:
                    set_pending(state, session_id, "reconcile", turn_seq, _now_iso(), _code,
                                [code_text] if claims_completion(code_text) else [])   # pending 已在就沿用原 claims
                    _summary = exhausted_summary(_code)                          # 列全部命中條目，不只第一條
                    _n = _count if _full_rules else None                       # pending 承接自先前回合：不報本回合次數
                    _head = (non_interactive_message(_gate, _n, _summary, _no_ask) if _no_ask
                             else exhausted_message(_gate, _n, _summary))
                    _msg = f"{_head}\n原擋訊息：\n{_code}"
                    if _report:
                        _msg += f"\n另外（記憶與報告類，不走放行詢問，照原規則處理）：\n{_report}"
                else:
                    _msg = _both
                if _code and not _no_ask:
                    _msg += f"\n{ASK_HINT}"
                append_guard_log("reconcile", {
                    "session_id": session_id, "turn_seq": turn_seq, "kind": _vg_kind, "count": _count + 1,
                    "excerpt": _msg.split("\n")[1][:160] if "\n" in _msg else _msg[:160],
                    **({"event": "noninteractive_block" if _no_ask else "exhausted_block", "why": _no_ask}
                       if _code_full else {}),
                })
                write_state(session_id, state)
                output_block(_piggyback(_msg + (f"\n{_vg_advice}" if _vg_advice else ""), "reconcile"))
                return
        elif _vg_advice or _pend_cleared:
            write_state(session_id, state)

    if not state.get("evasion_flag"):
        recent_prompts = state.get("recent_user_prompts", []) or []
        ev = detect_evasion(last_text, recent_prompts)
        if ev:
            ev["at"] = _now_iso()
            state["evasion_flag"] = ev
            # 證據暫存（evasion_flag 會被下輪 UPS 注入後清空；事件列表留存供
            # AEC (b) 欄 cross-check——hook 實測 vs 模型自評，不信自評）
            events = state.setdefault("evasion_events", [])
            events.append({
                "phrase": ev.get("phrase", ""),
                "turn_seq": int(state.get("turn_seq", 0)),
                "at": ev["at"],
            })
            state["evasion_events"] = events[-10:]
            append_guard_log("evasion", {
                "session_id": session_id,
                "phrase": ev.get("phrase", ""),
                "excerpt": (ev.get("context_excerpt", "") or "")[:120],
            })
            write_state(session_id, state)

    # ── Deferral Gate（退縮歸屬）────────────────────────────────
    # 主任務已完工（完成宣告 ∨ 本 turn 已 commit）且 context 用量 ≤ deferral_gate.
    # max_context_ratio 時，收尾把「帶受詞、可做的事」推給下個 session／獨立議題／
    # 非我造成 → 擋回三選一。每回合一次、共用 stop_gate_max_blocks
    # 全域預算。判定純函式在 wg_evasion.deferral_gate_reason；量測失敗 fail-open。
    # 底下四個「每回合最多擋一次」的閘（Deferral、KnowledgeHarvest、Harvest-Pending、AEC-Pending）的回合都用
    # _user_turn（使用者打字開的回合）：同伴訊息、背景通知每則都讓 turn_seq +1，拿它當鍵會每則訊息後又擋一次。
    _uturn = _since
    if stop_count < max_blocks and last_text:
        _ah = config.get("auto_handoff", {}) or {}
        try:
            _dg_ratio = estimate_context_usage(
                transcript,
                _ah.get("context_window_tokens", 1_000_000),
                _ah.get("context_base_overhead_tokens", 15000),
                text=transcript_text,
            )
        except Exception:
            _dg_ratio = 0.0
        try:
            dg = deferral_gate_reason(
                last_text,
                state.get("recent_user_prompts", []) or [],
                turn_seq=_uturn,
                gated_turn=state.get("deferral_gate_turn"),
                committed_this_turn=committed_this_turn,
                context_ratio=_dg_ratio,
                config=config,
            )
        except Exception as e:
            dg = None
            print(f"[Guardian:DeferralGate] error (fail-open): {e}", file=sys.stderr)
        if dg:
            state["deferral_gate_turn"] = _uturn
            state["stop_blocked_count"] = stop_count + 1
            append_guard_log("deferral", {
                "session_id": session_id,
                "turn_seq": turn_seq,
                "context_ratio": round(float(_dg_ratio), 3),
                "excerpt": dg.split("\n")[1][:160] if "\n" in dg else "",
            })
            write_state(session_id, state)
            output_block(_piggyback(dg))
            return

    # ── KnowledgeHarvest Gate（階段完工知識收割）────────────────
    # 宣告完成＝階段完工 → 要求呼叫 knowledge_harvest_report（items=[] 也要）。判定在
    # wg_harvest.harvest_gate_reason（活動門檻、冷卻只認 validated、dismiss 詞表重用 wg_evasion）。
    # 不吃 stop_gate_max_blocks 共用預算、每回合最多擋一次（harvest_gate_turn[sid] 記 _user_turn）；
    # state 全按 session_id 分區——隔壁 session 的收割不放行本 session。
    hv_reason = harvest_gate_reason(state, session_id, last_text, config, own_mod_files, turn_seq, gate_turn=_uturn)
    if hv_reason:
        state.setdefault("harvest_gate_turn", {})[session_id] = _uturn
        append_guard_log("knowledge_harvest", {
            "session_id": session_id, "turn_seq": turn_seq,
            "own_mod_files": len(own_mod_files),
            "accessed": len(state.get("accessed_files") or []),
        })
        write_state(session_id, state)
        output_block(_piggyback(hv_reason))
        return

    # ── Harvest-Pending Gate：收割回報有 item 對不上 receipt ──────
    # post_tool_use 核對落 knowledge_harvest[sid].pending；此處每回合（_user_turn）擋一次要求真做完再重報。
    # 本則是中途狀態句（仍在等 agent 回報…）→ 不擋，等真收尾再擋（wg_harvest.in_progress_text）。
    hp_reason = pending_gate_reason(state, session_id, turn_seq, last_text, gate_turn=_uturn)
    if hp_reason:
        state.setdefault("harvest_pending_gate_turn", {})[session_id] = _uturn
        append_guard_log("harvest_pending", {
            "session_id": session_id, "turn_seq": turn_seq,
            "items": (state.get("knowledge_harvest", {}).get(session_id) or {}).get("pending", [])[:5],
        })
        write_state(session_id, state)
        output_block(_piggyback(hp_reason))
        return

    # ── Scan-Report Gate ────────────────────────────────────────
    # 降條件觸發 — 只在動 core 檔或多檔（≥min_files_to_block）且宣告完成時要求收尾檢核；
    # 純單檔/文件小改不觸發（避免過度觸發成儀式性負擔，非防退避）。
    if own_mod_files and not state.get("scan_report_warned") and not committed_this_turn:
        recent_prompts = state.get("recent_user_prompts", []) or []
        sr_min_files = int(config.get("min_files_to_block", 2))
        if detect_missing_aec_emission(
            last_text, own_mod_files, recent_prompts, sr_min_files, emitted_this_turn
        ):
            state["stop_blocked_count"] = stop_count + 1
            state["scan_report_warned"] = True  # 保留 one-shot anti-nag（比照現況）
            reason = _piggyback(
                "[Guardian:ScanReport] 宣告完成且本 session 動到 core 檔/多檔（達收尾檢核門檻），"
                "但本回合未 emit anti_evasion_report，違反 IDENTITY「反退避契約」。\n"
                "請呼叫 MCP tool anti_evasion_report(a..i) 提交收尾檢核——內容走 HUD、"
                "chat 只留折疊 chip：\n"
                "  (a) 缺失發現與修補清單：`- 檔:行 — 改了什麼`；無則填「無」。**必寫**\n"
                "  (b) AI 逃避通報：本次有/沒有 忽略 / 偷埋的現象；**僅發生時填**，否則「無」\n"
                "  (c) Token 累積警示：見 hook `[Auto-Handoff]` 預警則判斷失真並附接續 prompt；**僅發生時填**，否則「無」\n"
                "  (d) 記憶收錄帳：先掃五個來源——①使用者指正/退回/重申的話 ②重試≥2 次或查了才懂的機制/踩坑 "
                "③外查來的事實（帶日期） ④我做的取捨/契約/偏好 ⑤既有 atom 被證錯或要補的——逐項 "
                "`- <項目> → 已寫入 atom <名>` 或 `→ 不寫（一句理由）`；值得寫的在呼叫 tool **之前** atom_write 完，"
                "⛔「尚未寫／見下一動」會被擋。**必寫**，無則「無」\n"
                "  (e) 未告知決策＋未驗證假設：擅自的取捨（默默選方案/跳過步驟/動了請求之外的檔）與依賴但未驗證的假設；無則「無」\n"
                "  (f) 靜默狀態改變：對話沒交代的環境副作用——裝套件/改 config/重啟服務/建排程/仍在跑的背景程序；無則「無」\n"
                "  (g) 版控收尾：哪些已 commit、哪些未上及理由（併發進度/待拍板/隱私）；無改動則「無」\n"
                "  (h) 收尾判定：單句——「可關閉」或「下一動＝…」（只列使用者要做的事；寫 atom/補測試/commit 是你自己能做的，先做完）。**必寫**\n"
                "  (i) 衍生暫存清單：**一行一路徑** `<路徑> — <備註>`（絕對或相對 cwd，可 glob）；只列「此刻尚存、留給使用者裁決」的，已刪的不列、純說明不列（預設完工即刪）；**必寫**，無則「無」\n"
                "  (j) 證據持久路徑：本回合驗證收據的持久位置（通常是 `workflow/verify-ledger/<sid>.jsonl`，或驗證輸出檔）；"
                "本 session 跑過哨兵驗證就**必填真存在的路徑**（Stop 對帳閘會查 exists），沒有收據才填「無」\n"
                "  (k) 追蹤項：還沒做完、要追的事一行一項（會進 workflow/tracking 帳本）；沒有寫「無」，**不接受空字串**\n"
                "十一參都 required、未發生填「無」。不得用 prose「不在範圍 / 留給未來」籠統帶過。"
            )
            write_state(session_id, state)
            output_block(reason)
            return

    # ── AEC-Pending Gate：報告把「記憶寫入」推到之後 ─────────────────
    # (d)「尚未寫／見下一動」、(h)「下一動＝寫 atom」= 把知識留給下一回合（使用者要再問一次
    # 才會補）。post_tool_use 判定落 report["d_pending"]；此處每回合（_user_turn）擋一次（共用 max_blocks
    # 預算）：模型 atom_write 後重新 emit → 新報告無 d_pending → 放行。
    pending = aec.get("d_pending") or []
    if (
        emitted_this_turn and pending
        and state.get("aec_pending_gate_turn") != _uturn
        and stop_count < max_blocks
    ):
        state["aec_pending_gate_turn"] = _uturn
        state["stop_blocked_count"] = stop_count + 1
        append_guard_log("aec_pending", {
            "session_id": session_id, "turn_seq": turn_seq, "items": pending[:5],
        })
        write_state(session_id, state)
        output_block(_piggyback(
            f"[Guardian:AEC-Pending] 收尾檢核把 {len(pending)} 項記憶寫入推到之後：\n"
            + "\n".join(f"  ✗ {x}" for x in pending[:5])
            + "\n這等於把知識留給下一回合（使用者要再問一次才會補），違反反退避契約。"
            "現在就 atom_write 寫完，再重新呼叫 anti_evasion_report 把該項改成"
            "「→ 已寫入 atom <名>」（或「→ 不寫（一句理由）」）；(h) 只列使用者要做的事。"
        ))
        return

    # HUD 不可達且本回合 emit 為 notable/real-evasion → 大聲 fallback 回 chat（可觀測性鐵律：
    # push 不到窗不得 fail-silent）。post_tool_use 標旗，此處消費一次（新 emit 再標則再補，
    # 不永久靜音 real-evasion）。消費前**再查一次**：emit 當下不可達可能是暫時的（Node 剛換手、
    # HUD 頁重連中），現在窗活著就不吵 chat；兩次判定都落 guard-aec_hud.jsonl 可稽核。
    # Node tool chip 是 emit 當下的主要 UX 面；本 fallback 是 Python 端獨立的觀測保證，
    # 不倚賴窗是否渲染。emit 閘本身已放行（見上），此處不再擋 emit。
    if state.get("aec_hud_fallback"):
        state["aec_hud_fallback"] = False  # 消費，避免重播
        sev = aec.get("severity", "notable")
        _aec_cfg = config.get("aec", {}) or {}
        alive, info = _hud_alive(
            int(config.get("dashboard_port", 3848)), int(_aec_cfg.get("hud_stale_s", 30))
        )
        append_guard_log("aec_hud", {
            "where": "stop", "session_id": session_id, "severity": sev, "alive": alive, **info,
        })
        if alive:
            write_state(session_id, state)
        else:
            state["stop_blocked_count"] = stop_count + 1
            _why = info.get("reason") or f"age_s={info.get('age_s')} clients={info.get('clients')}"
            fb = [
                f"[Guardian:AEC] HUD 不可達（{_why}），{sev} 收尾檢核改回 chat 呈現（不 fail-silent）："
            ]
            for _k, _label in (("a", "(a) 缺失修補"), ("b", "(b) 逃避通報")):
                _v = (aec.get(_k) or "").strip()
                if _v and _v != "無":
                    fb.append(f"  {_label}：{_v}")
            # cross-check 升級：模型自評 (b)=無但 hook 實測退避 → 附 hook 證據（不信自評）
            if aec.get("severity_upgraded_by"):
                fb.append("  ⚠ severity 由 hook cross-check 升級——(b) 自評「無」與 hook 實測不符：")
                for _e in (aec.get("hook_evidence") or [])[:3]:
                    fb.append(
                        f"    - turn {_e.get('turn_seq', '?')}: 退避語『{_e.get('phrase', '')}』"
                    )
            write_state(session_id, state)
            output_block(_piggyback("\n".join(fb)))
            return

    # ── Reload Advice Gate（規則 RELOAD_ADVICE_ALREADY_LOADED）──────────────
    # 收尾叫使用者 Reload Window 前，查每個活著的工具服務是不是已載入磁碟上最新的程式；都是最新就擋一次。每個使用者回合一次。
    _rl_turn = _user_turn(state, int(state.get("turn_seq", 0)))
    if stop_count < max_blocks and state.get("reload_advice_turn") != _rl_turn:
        _rl_text = get_last_assistant_text(transcript, text=transcript_text, min_chars=1)
        if RELOAD_ADVICE_RE.search(_rl_text or ""):
            _rl = reload_advice_verdict(_rl_text, *_mcp_load_facts(), time.time())
            if _rl.owed:
                state["reload_advice_turn"] = _rl_turn
                state["stop_blocked_count"] = stop_count + 1
                write_state(session_id, state)
                output_block(_piggyback(
                    f"[Guardian:ReloadAdvice] 規則 {_rl.rule}：{_rl.why}｜證據：{'；'.join(_rl.evidence)}\n"
                    "不必叫使用者 Reload Window：拿掉那句再收尾。若是程式更新以外的理由要重開（改了 MCP 啟動設定、settings.json 等），"
                    "保留那句並加一行「重載原因：<哪個設定改了>」。"))
                return

    # ── Sync Reminder Gate ──────────────────────────────────────
    sr_config = config.get("sync_reminder", {}) or {}
    sr_enabled = sr_config.get("enabled", True)
    sr_max = int(sr_config.get("max_reminders", 1))
    sr_count = int(state.get("sync_reminder_count", 0))
    # session-filter：只認本 session 自己改的檔（own_mod_files）。共用工作樹下，協調
    # session 不得替他 session 未提交的檔誤觸發同步提醒（比照 Scan-Report 閘的過濾）。
    if (
        sr_enabled
        and own_mod_files
        and not state.get("muted")
        and phase not in ("done", "syncing")
        and sr_count < sr_max
    ):
        uncommitted = _detect_uncommitted_files(own_mod_files)
        unpushed: List[str] = []
        if not uncommitted and sr_config.get("unpushed", True):
            unpushed = _git_unpushed_roots(own_mod_files)
        if uncommitted:
            state["sync_reminder_count"] = sr_count + 1
            state["stop_blocked_count"] = stop_count + 1
            # 訊息瘦身：檔案清單不進 chat（statusline 常駐示數、模型自行 git status）
            reason = _piggyback(
                f"[Guardian:SyncReminder] 偵測到 {len(uncommitted)} 個已修改但"
                "尚未提交的檔案（清單自行 git status），依 USER.md 縮寫指令契約"
                "（上GIT＝commit+push 一氣；口令前不碰 git）應提示同步。\n"
                "請選一個方向：\n"
                "  (a) 使用者本回合已下「上GIT」等口令 — 立刻 commit + push 一氣做完\n"
                "  (b) 尚無口令 — 收尾報告列「改了哪些檔＋驗了什麼／沒驗什麼」等口令，不先 commit\n"
                "  (c) 我不打算上／已在前一輪上過 — 說明原因；git/svn clean 後本 gate 自動清旗標"
            )
            write_state(session_id, state)
            output_block(reason)
            return
        if unpushed:
            state["sync_reminder_count"] = sr_count + 1
            state["stop_blocked_count"] = stop_count + 1
            reason = _piggyback(
                "[Guardian:SyncReminder] 本 session 改的檔已 commit 但尚未 push："
                + "、".join(unpushed) + "\n"
                "「上GIT」＝commit + push 一氣，local commit 不算同步、也不是拆階段的切點。\n"
                "請選一個方向：\n"
                "  (a) 使用者已下「上GIT」等口令 — 立刻 push\n"
                "  (b) 使用者沒下口令我卻先 commit 了 — 說明原因；下一批起口令前不碰 git\n"
                "  (c) 不打算上 — 說明原因"
            )
            write_state(session_id, state)
            output_block(reason)
            return

    # ── Atom Consumption Audit Gate（取用端閉環稽核）──────────────
    # 排序：correctness / sync 之後（那些優先）、DPM 之前；沿用 stop_gate_max_blocks
    # 全域預算（第 3 次強制放行）。per-atom 一次（atom_audit_prompted）防轟炸。
    # fail-open：判定任何失敗 → stderr 浮訊號後照常放行，不比既有慣例更擋人。
    if (
        (config.get("atom_audit", {}) or {}).get("enabled", True)
        and stop_count < max_blocks
    ):
        try:
            aa = _audit_pointer_atom_consumption(state)
        except Exception as e:
            aa = None
            print(f"[Guardian:AtomAudit] audit error (fail-open): {e}", file=sys.stderr)
        if aa:
            aa_reason, aa_names = aa
            prompted = state.setdefault("atom_audit_prompted", [])
            prompted.extend(n for n in aa_names if n not in prompted)
            state["stop_blocked_count"] = stop_count + 1
            write_state(session_id, state)
            output_block(_piggyback(aa_reason))
            return

    # ── Deep Post-Mortem Gate（Stage 3）────────────────────────
    # (effort 訊號) AND (真失敗訊號) + 本 session 未深寫過 → 注入指令，要 Claude 結束前用
    # atom_write 補完整 post-mortem。deep_postmortem_done 一次性防重複＝獨立預算 1；
    # 排在 correctness/sync gate 之後（那些優先）但★不共用 stop_gate_max_blocks——
    # 否則 Sync+TestFail 先吃光預算就餓死 DPM（見 _should_deep_postmortem docstring 實證）。
    claims_done = bool(last_text and claims_completion(last_text))
    if (_should_deep_postmortem(state, config, claims_done)
            and not _dpm_marker(session_id).exists()):
        state["deep_postmortem_done"] = True
        try:
            marker = _dpm_marker(session_id)
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()   # 舊 marker 由開 session 時的 _shared.prune_workflow_records 照表清（7 天）
        except OSError:
            pass
        state["stop_blocked_count"] = stop_count + 1
        reason = _piggyback(_dpm_instruction(state, config, cwd))
        write_state(session_id, state)
        output_block(reason)
        return

    # ── 注入→使用→結果 閉環歸因（correctness gates 通過後、per-turn 一次性）──
    # 走到這裡代表本 Stop 未被 test-fail/scan-report 等 correctness gate 攔下 →
    # 該 turn 的對錯訊號已落定。turn_seq 守門一次性；write_state 立即固化標記
    # （防後續 phase=done / muted 等不寫 state 的終止路徑導致重複計 α/β）。
    _attribute_usefulness(
        state, config, session_id, transcript, last_text, transcript_text
    )
    write_state(session_id, state)

    # ── Anti-loop guard ─────────────────────────────────────────
    if stop_count >= max_blocks:
        state["phase"] = "done"
        write_state(session_id, state)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    if phase in ("done", "syncing"):
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    # session-filter：底部一般 block 亦只數本 session 自己改的檔（own_mod_files）——
    # 協調 session（own 為空）不因共用樹上他 session 的檔而誤觸發。kq_count 不過濾：
    # knowledge_queue 是本 session 自己的待記知識，即使 own 檔為 0 仍是本 session 責任。
    mod_count = len(own_mod_files)
    kq_count = len(state.get("knowledge_queue", []))
    unique_files = list({m["path"] for m in own_mod_files})
    min_files = config.get("min_files_to_block", 2)

    if state.get("muted"):
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    if mod_count == 0 and kq_count == 0:
        state["phase"] = "done"
        write_state(session_id, state)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    if len(unique_files) < min_files and kq_count == 0:
        state["phase"] = "done"
        write_state(session_id, state)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    state["stop_blocked_count"] = stop_count + 1

    file_names = ", ".join(f.rsplit("/", 1)[-1] for f in unique_files[:8])

    reason = (
        f"[Workflow Guardian] {len(unique_files)} file(s) modified"
        + (f", {kq_count} knowledge pending" if kq_count else "")
        + f". Files: {file_names}.\n"
        "Sync: _AIDocs→_CHANGELOG | knowledge→atom | .git→add+commit+push | .svn→add+commit"
    )

    if DOCDRIFT_AVAILABLE:
        try:
            dp = state.get("docdrift_pending", {})
            if dp:
                docs = sorted(set(v["doc"] for v in dp.values()))
                reason += f"\n[DocDrift] {len(dp)} source change(s) → consider updating: {', '.join(docs[:5])}"
        except Exception:
            pass

    reason = _piggyback(reason)
    write_state(session_id, state)
    _maybe_spawn_user_extract_worker(session_id, state, config)

    output_block(reason)
