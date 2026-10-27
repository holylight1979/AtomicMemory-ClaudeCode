"""
handlers/stop.py — Stop hook handler

閘序：
1. Test-Fail Gate（測試未綠 + 宣告完成 → 擋；吃寫碼查核那份每個使用者回合的預算）
1b. Reconcile Gate（收尾宣稱 vs 驗證收據：說修好要 PASS、說量了要 DONE、說試過要有執行、改碼要有 case 或 PASS、AEC 要 j／k）
    ＋ 驗證範圍閘（改了程式要有 LLM 宣告的驗證範圍、範圍內每項改完之後跑綠；wg_verify_scope）；獨立預算 reconcile_gate.max_blocks_per_turn
1c. TurnJudgment Gate（G11：背景量完到門檻的側面數據要有「拐彎判斷｜」五欄行；每個使用者回合擋一次；前面的閘擋下時列進預覽）
1d. SecondOpinion Gate（G9：大任務或改到高風險部位宣告完成 → 本回合真的跑過第二意見、收尾有分歧裁決四行；擋一次後問使用者；
    還在跑時收尾寫一行「等第二意見｜<job_id>」不算宣告完成，只留帳 waiting）
1e. Equivalence Gate（G7：重構／效能意圖、本回合改過程式檔、宣告完成 → 等值證法三類與熱路徑一問；自己的預算，擋滿問使用者）
2. Evasion 偵測（軟糾正）／Deferral Gate（退縮歸屬）
3. KnowledgeHarvest Gate（宣告完成 → 要求 knowledge_harvest_report；Harvest-Pending 擋核不過的 item）
4. Scan-Report Gate（宣告完成但缺 anti_evasion_report emit → 硬阻）
5. Sync Reminder Gate（modified_files>0 仍未 commit/push → 軟阻；vcs-sync worker 活鎖中的 root 跳過）
+ 一般 sync block 邏輯
寫程式碼的查核閘（TestFail、Reconcile／VerifyScope）共用一份預算：每個使用者回合 reconcile_gate.max_blocks_per_turn 次，
擋滿後不自行放行：改送擋滿訊息要模型用 AskUserQuestion 問使用者（wg_release）；使用者在最後一次擋之後放行，才放這一回合並記
guard-reconcile.jsonl user_release，放行的那幾件之後的回合原因還在也不再要求放行。擋滿的待放行只在同一個使用者回合有效。
無法互動（headless／SDK、子代理、裁判子 session）不叫它問：擋滿就放行並留帳。查核自己判定出錯：同一個錯誤每個使用者回合
擋一次，之後放行並留帳。其餘共用 stop_gate_max_blocks 的閘每個使用者回合重新計次，同一回合第 3 次放行。
連鎖斷路器（v6；判定 hooks/wg_chain.py、帳與還原 lib/chain_store.py）：各閘之前問 chain_store.on_stop 一次；每道閘要擋或記欠之前
問 _chain_hold——警報後只記錄（跳過那道閘的擋與記欠、往下走），讓警報響的那一次改送中止通知。沒有警報時各閘照原樣擋。
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from wg_core import (
    _ensure_state, _now_iso, write_state, read_state,
    append_guard_log, WORKFLOW_DIR, _atom_debug_error, v6_enabled, coding_turn,
)
import wg_core as _core
import chain_store                     # 連鎖斷路器的帳、快照、還原（lib/；判定在 hooks/wg_chain.py）
from wg_release_rules import JUDGMENT_EXAMPLE, in_turn, turn_start, user_turn as _user_turn
from wg_evasion import (
    claims_completion, detect_evasion, deferral_gate_reason,
    get_last_assistant_text, detect_missing_aec_emission,
    get_current_turn_text, read_transcript_tail, get_current_turn_visible_text,
    is_context_exempt_phrase, _aec_blank, closing_check_waiver, completion_threshold_met, dismissed_recently, CLOSING_CHECK_ITEM,
)
from wg_verify_ledger import (
    receipts_of, reconcile_cfg, reconcile_gate_parts, agent_receipt_key,
    measure_cmds_of, load_self_runs, measure_parts, self_run_covered, net_unchanged_paths,
    committed_settled_paths, committed_equal_paths, git_deadline, copied_glob_source, git_launcher, declared_cases,
)
from wg_verify_scope import case_check as _scope_case_check, fix_evidence as _scope_fix_evidence, scope_cfg as _scope_cfg
from wg_release_rules import (
    parse_hits, budget_exhausted, budget_tick, exhausted_summary, is_worktree_checkout, push_required_verdict,
    dpm_instruction_text, retry_rounds_text, RELOAD_ADVICE_RE, reload_advice_verdict,
    leftover_candidates, leftover_cleanup_verdict, evasion_context_exempt_verdict,
    parse_not_doing, quote_in_prompts, waived_failures, waiver_mentioned_since, waiver_miss_notes, red_item_label,
    cmd_run_line, second_opinion_decline, second_opinion_decline_ok, parse_equivalence_lines,
    reason_present, red_units, failure_lines,
)
from wg_core import user_typed_prompts as _user_typed_prompts
from wg_release import (
    exhausted_message, mark_block, user_released, released_this_turn, record_release,
    non_interactive_reason, non_interactive_message, pending_of, set_pending, clear_pending,
    release_items, keep_released, drop_items, shown_items,
)
from wg_episodic import _find_session_transcript
from wg_handoff import token_warn_payload, estimate_context_usage
from wg_bg_harvest import background_on, on_stop as bg_harvest
from wg_harvest import (
    harvest_gate_reason, pending_gate_reason, vcs_sync_lock_active,
    record_pick, pick_due, mark_pick_asked, pick_material, pick_prompt, session_open_tracking,
)
from wg_reading_path import reading_path_note, turn_judgment_missing, turn_judgment_note, without_judgment_prompt
from wg_text_score import on_stop as _text_score_on_stop
from wg_release_rules import format_hit, second_opinion_hint, second_opinion_hint_background
from wg_second_opinion import auto_cfg as _so_auto_cfg, check as _so_facts, LETTER as _SO_LETTER, GATE as _SO_GATE, \
    mark_ok as _so_mark_ok
from wg_closing_round import pick_pre_close_on as _pick_pre_close_on, so_background_on as _so_background_on, \
    so_done_notice as _so_done_notice, watch_job as _so_watch_job
from wg_hook_timing import lap as _hook_lap, quiet as _hook_quiet
from handlers._shared import (
    _hud_alive,
    _maybe_spawn_user_extract_worker,
    DOCDRIFT_AVAILABLE,
    entry_note,
    with_note,
)

# Windows: 外呼 git/svn 時若不帶此 flag，無主控台的 hook 父行程會被配一個可見 console 視窗
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


from handlers import aec_ledger


# walk-up 定 VCS 根（零 subprocess）；與 pre_tool_use／session_start／tools 共用同一支
from wg_core import find_vcs_root as _find_vcs_root, find_vcs_root_ex as _find_vcs_root_ex  # noqa: E402

# 連鎖斷路器在收尾時不擋、要給使用者看的一段（使用者答了三選一的結果、還在等答的提醒）：這次收尾的每個出口都帶上
_CHAIN_TAIL: List[str] = []


def output_json(data: Dict[str, Any]) -> None:
    if _CHAIN_TAIL:
        data = {**data, "systemMessage": "\n".join(x for x in (data.get("systemMessage"), *_CHAIN_TAIL) if x)}
    _core.output_json(data)


def output_nothing() -> None:
    if _CHAIN_TAIL:
        output_json({})
    _core.output_nothing()


def output_block(reason: str) -> None:
    output_json({"decision": "block", "reason": "\n".join([reason, *_CHAIN_TAIL])})


def _unmark(book: Any, key: str, prev: Any) -> None:
    """連鎖斷路器把這次擋改成只記錄：閘在擋之前自己記下的「本回合擋過」標記放回原值（選繼續之後這道閘照常擋一次）。"""
    if not isinstance(book, dict):
        return
    if prev is None:
        book.pop(key, None)
    else:
        book[key] = prev


def _chain_gate(session_id: str, turn: int, gate: str, what: str, input_data: Dict[str, Any], config: Dict[str, Any],
                state: Dict[str, Any], later: Iterable[str] = ()) -> bool:
    """連鎖斷路器（chain_store.gate_fired）：這道閘要擋或記欠了，先記一筆觸發。回 True＝警報後只記錄（呼叫端跳過這道閘的擋與記欠，
    照往下走）；這一次讓警報響 → 寫回 state、送中止通知取代原擋訊息，結束這次收尾；照擋回 False。"""
    r = chain_store.gate_fired(session_id, turn, gate, what, input_data, config, later=later)
    if r.notice:
        write_state(session_id, state)
        output_block(r.notice)
    if r.record_only:
        print(f"[Guardian:ChainBreaker] 連鎖中止中：{gate} 這次只記錄，不擋", file=sys.stderr)
    return r.record_only


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


def _synced_paths(paths: Iterable[str]) -> set:
    """已同步的檔（規則 SYNC_BLOCK_SKIPS_SYNCED）：在 git／svn 工作區、status 乾淨、所在 git 根沒有已 commit 未 push 的
    （worktree 或沒 upstream 照 WORKTREE_NO_PUSH 不要求 push，也算）。已刪除的檔照查：status 乾淨＝刪除已提交。
    查不了（不在工作區、git／svn 失敗或逾時）一律不算已同步；但檔已不在、往上也找不到版控根（整個移除的工作樹、刪掉的
    暫存目錄）沒有東西可同步，算進來（規則 SYNC_SKIPS_VANISHED_OUTSIDE_VCS）。磁碟或網路分享根連不到、往上找時出錯的
    （斷線看起來也像不在）照算未同步。"""
    groups: Dict[tuple, List[str]] = {}
    synced: set = set()
    for p in dict.fromkeys(str(x) for x in paths if x):
        found, err = _find_vcs_root_ex(Path(p).parent)
        if found:
            groups.setdefault(found, []).append(p)
        elif not err and os.path.isdir(Path(p).anchor or os.sep) and not os.path.lexists(p):
            synced.add(p)
            print(f"[Workflow Guardian] 規則 SYNC_SKIPS_VANISHED_OUTSIDE_VCS：{p} 與所在版控根都已不在，沒有東西可同步",
                  file=sys.stderr)
    for (kind, root), ps in groups.items():
        dirty = _git_dirty_set(root, ps) if kind == "git" else _svn_dirty_set(root, ps)
        if dirty is None:
            continue
        if kind == "git" and _git_unpushed_roots([{"path": str(root / ".git")}]):
            continue
        synced.update(p for p in ps if _norm_for_match(p) not in dirty)
    return synced


def _drop_synced(mod_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """從改檔清單剔除已同步的檔（_synced_paths）；判斷失敗照原清單（stderr 告知）。"""
    if not mod_files:
        return mod_files
    try:
        synced = _synced_paths((m or {}).get("path") for m in mod_files)
    except Exception as e:  # noqa: BLE001
        print(f"[Workflow Guardian] 判斷哪些檔已同步失敗，照算未同步：{type(e).__name__}: {e}", file=sys.stderr)
        return mod_files
    if synced:
        print(f"[Workflow Guardian] 規則 SYNC_BLOCK_SKIPS_SYNCED：{len(synced)} 個改過的檔已 commit 並 push，不再要求同步",
              file=sys.stderr)
    return [m for m in mod_files if (m or {}).get("path") not in synced]


def _sync_block_keys(state: Dict[str, Any], unsynced: int, min_files: int) -> List[str]:
    """底部一般 sync block 照目前狀態欠的全部項目（不管擋過沒）：有待記知識，或未同步改檔 ≥ min_files 時有文件漂移才算欠
    （只剩改檔數歸同步提醒，規則 SYNC_BLOCK_NOT_REPEATED）。unsynced＝剔除已同步之後的不重複改檔數。
    待記知識以整段內容的雜湊當鍵（前段相同、後段不同算兩筆）；文件漂移的鍵帶它記下的時間（同一對來源→文件解決後又漂移是新的一筆）。"""
    kq = [f"kq:{hashlib.sha1(str(q.get('content', '') if isinstance(q, dict) else q).encode('utf-8')).hexdigest()[:16]}"
          for q in state.get("knowledge_queue") or []]
    pending = (state.get("docdrift_pending") or {}) if DOCDRIFT_AVAILABLE else {}
    drift = [f"drift:{k}@{v.get('added_at', '') if isinstance(v, dict) else ''}" for k, v in pending.items()]
    if not kq and not (drift and unsynced and unsynced >= min_files):
        return []
    return kq + drift


def _turn_mark(state: Dict[str, Any], uturn: int) -> str:
    """sync_block_shown 記的「哪一個使用者回合」：開場時間＋回合序號。專案根指紋變了、開場重建 state 時回合序號從頭算、開場時間換新，
    重建前擋過的不會被當成同一回合再擋。"""
    return f"{(state.get('session') or {}).get('started_at', '')}#{uturn}"


def _sync_block_items(state: Dict[str, Any], unsynced: int, min_files: int, uturn: int) -> List[str]:
    """底部一般 sync block 這次要擋的項目（空＝不擋；收尾的擋與「還會擋」預覽共用）。規則 SYNC_BLOCK_NEW_ITEMS_ONLY：
    前面使用者回合擋過的同一筆不再算，同一回合照舊（擋幾次歸共用預算）；擋過的記在 state sync_block_shown（項目→第一次擋的回合記號）。"""
    shown = state.get("sync_block_shown") or {}
    mark = _turn_mark(state, uturn)
    return [k for k in _sync_block_keys(state, unsynced, min_files) if shown.get(k, mark) == mark]


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


def _dpm_instruction(state: Dict[str, Any], config: Dict[str, Any], cwd: str = "") -> str:
    """DPM 指令文字；有逐輪重試紀錄就在標頭下一行附證據行（規則 RETRY_COUNTS_RERUN_CYCLES，format_hit 格式）。cwd 留著與呼叫端同簽名。"""
    rounds = state.get("retry_rounds") or []
    return dpm_instruction_text(_dpm_trigger_text(state, config), retry_rounds_text(rounds) if rounds else "")


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
    moved = [m for m in state.get("moved_code_dirs") or [] if isinstance(m, dict) and m.get("session_id") == sid
             and not copied_glob_source(str(m.get("old") or ""))]          # 萬用字元來源還有符合的檔＝其實是複製
    if aid:
        return [m for m in moved if m.get("agent_id", "") == aid], receipts_of(state, receipt_key)
    receipts = list(receipts_of(state, sid))
    for a in dict.fromkeys(m.get("agent_id") for m in moved if m.get("agent_id")):
        receipts += receipts_of(state, agent_receipt_key(sid, a))
    return moved, receipts


def _judge_error(state: Dict[str, Any], key: str, turn_seq: int, gate: str, what: str, log_name: str, log_key: str,
                 e: BaseException, fix: str) -> Optional[str]:
    """規則 GATE_SELF_ERROR（判法 wg_release_rules.gate_self_error_verdict）：寫碼查核自己判定出錯：stderr＋guard_log
    event=error 每次都記；同一個錯誤（閘＋例外型別＋訊息）每個使用者回合只擋一次，之後放行（留帳 released=true）。
    key＝收據鍵（主 session 是 sid，子代理是 sid#agent:<id>）。回擋訊息或 None。"""
    from wg_release_rules import gate_self_error_verdict
    error = f"{type(e).__name__}: {e}"
    head = f"[Guardian:{gate}] {what}判定錯誤：{error}"
    uturn = _user_turn(state, turn_seq)
    book = state.setdefault("judge_error_blocked", {})
    mine = book.get(key) if isinstance(book.get(key), dict) and book[key].get("turn") == uturn else {"turn": uturn, "errors": []}
    book[key] = mine
    sig = f"{gate}|{what}|{error}"[:300]
    v = gate_self_error_verdict(f"{gate}{what}", "stop", error, blocked_this_turn=sig in mine["errors"])
    append_guard_log(log_name, {"event": "error", "rule": v.rule, "gate": gate, "session_id": key, "turn_seq": turn_seq,
                                log_key: repr(e)[:200], "released": not v.owed})
    if not v.owed:
        print(f"{head}（{v.why}，已留帳）", file=sys.stderr)
        return None
    mine["errors"].append(sig)
    print(head, file=sys.stderr)
    return f"{head}。{fix}；先別宣告完成（規則 GATE_SELF_ERROR：同一個錯誤只擋這一次，之後放行並留帳）"


def _verify_gates(
    state: Dict[str, Any], session_id: str, turn_seq: int, last_text: str,
    transcript, transcript_text: str, own_mod_files: List[Dict[str, Any]],
    rg_cfg: Dict[str, Any], sg_cfg: Dict[str, Any], aec: Dict[str, Any], aec_emitted: bool,
    claims: List[str] = (), pending: bool = False, goal: bool = False, goal_cfg: Optional[Dict[str, Any]] = None,
) -> tuple:
    """對帳閘＋驗證範圍閘的判定。回 (寫碼查核擋訊息或 None, 收尾報告欄 (e) 擋訊息或 None, 種類 reconcile／scope／"",
    提醒或 None：背景全量新記的範圍漏判)。寫碼查核＝對帳 (a)～(d)＋驗證範圍；(e) 屬記憶與報告類，擋滿時不走放行詢問（分開回）。
    goal＝True（只有主 session 的 Stop 傳）另判需求目標的 (f1)(f2)(f3)，併進寫碼查核；記憶知識類的輕樹 (f4) 併進 (e) 那一份；
    子代理與裁判不跑目標對照。
    (a)(b)(c) 對 last_text 與 claims（pending 承接的本回合先前宣稱）；(d) 與驗證範圍不看措辭，有改碼紀錄就判（last_text 空也判）。
    自寫收據（_runs/）驗證範圍（入帳找漏判）與 (a) 共用，只讀一次。寫碼查核整個過了 → 這份驗證範圍記成結案。
    判定本身出錯 → stderr＋guard_log 每次都記；同一個錯誤每個使用者回合只擋一次（_judge_error），之後放行並留帳。"""
    receipts = receipts_of(state, session_id)
    reason: Optional[str] = None
    report: Optional[str] = None
    kind = ""
    advice: Optional[str] = None
    _runs: List[List[Dict[str, Any]]] = []
    _claim_audit: List[Dict[str, Any]] = []
    # 改過又原樣還原的檔（與 HEAD 相同、本 session 之後沒 commit、同根本 session 改過的程式檔全都乾淨）不算改碼：補案例與驗證範圍都不欠；
    # 判不出來照算改了。同根乾淨看 session 全部改過的程式檔（主 session＋所有子代理；文件等不算，EXEMPTION_PEERS_CODE_ONLY），
    # 剔除只套在這次受查的 own_mod_files
    sid = str(session_id).split("#agent:", 1)[0]
    session_paths = [m["path"] for m in state.get("modified_files") or []
                     if isinstance(m, dict) and m.get("path") and m.get("session_id", sid) == sid]
    for _agent_mods in (state.get("agent_modified_files") or {}).values():
        session_paths += [m["path"] for m in _agent_mods or [] if isinstance(m, dict) and m.get("path")]
    # worktree 根的一次性 git 啟動器（寫入時就認好、記了標記）建、改、刪都不算改碼：不讓收據作廢、不欠案例（LAUNCHER_NOT_CODE）
    launchers = [m["path"] for m in own_mod_files if (m or {}).get("path") and git_launcher(str(m["path"]))]
    session_paths = [p for p in session_paths if not git_launcher(str(p))]
    if launchers:
        own_mod_files = [m for m in own_mod_files if (m or {}).get("path") not in set(launchers)]
        print("[Guardian:ReconcileGate] 規則 LAUNCHER_NOT_CODE：一次性 git 啟動器不算改碼："
              + "、".join(Path(p).name for p in launchers[:5]), file=sys.stderr)
    git_dl = git_deadline()           # 兩種「內容回到某狀態」的豁免（這裡與下面 commit 快照）共用一個查 git 的整支預算
    try:
        same = net_unchanged_paths(own_mod_files, state.get("last_commit_turn_seq"), session_paths=session_paths,
                                   deadline=git_dl, cfg=rg_cfg)
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
                # 驗證範圍閘關著時，verify_scope 照收的 case_for 宣告也算案例覆蓋
                case_for=declared_cases(state, session_id, rg_cfg),
                case_settled=lambda owed: committed_settled_paths(state.get("commit_snapshot"), owed, session_paths,
                                                                  deadline=git_dl, cfg=rg_cfg),
                committed_new=state.get("committed_new_code"), user_turn=since,
                exec_this_turn=in_turn((state.get("exec_turn_seq") or {}).get(session_id), turn_seq, since),
                **dict(zip(("moves", "move_receipts"), _move_inputs(state, session_id))),
                move_scan_hits=state.get("move_scan_hits") or {},
                self_covered=(lambda: self_run_covered(measure_parts(own_mod_files, _lk), _self_runs())) if _lk else None,
                # (a) 說修好：有驗證範圍宣告就認宣告範圍的收據（同一個判斷只一份答案），沒宣告才退回檔名對應
                scope_fix=(lambda: _scope_fix_evidence(state, session_id, own_mod_files, receipts, rg_cfg, _lk, _self_runs()))
                if _lk and sg_cfg.get("enabled", True) else None,
                # (d) 補案例：由哪個案例驗看 LLM 在驗證範圍的宣告（case_for／no_case）；驗證範圍閘關掉才退回時序判法
                case_check=_scope_case_check(state, session_id, own_mod_files, receipts, rg_cfg, _lk, _self_runs())
                if _lk and sg_cfg.get("enabled", True) else None,
                audit=_claim_audit,
            )
            kind = "reconcile" if reason or report else ""
        except Exception as e:
            reason = _judge_error(state, session_id, turn_seq, "ReconcileGate", "", "reconcile", "error", e, "修好設定或回報")
            kind = "reconcile" if reason else ""
        # 規則 CLAIM_WORDS_ARE_HINTS：(a)(b)(c) 被宣稱行解掉的留帳（guard-reconcile.jsonl event=claim_disclaimed／claim_receipt_ref），健檢抽查；
        # 判定後段出例外也照記（解掉那一筆已發生）
        for _ca in _claim_audit:
            append_guard_log("reconcile", {"session_id": session_id, "turn_seq": turn_seq,
                                           "event": "claim_receipt_ref" if _ca.get("rule") == "CLAIM_RECEIPT_REF_MATCH" else "claim_disclaimed",
                                           "letter": _ca.get("letter"), "kind": _ca.get("kind"), "why": str(_ca.get("why", ""))[:200],
                                           "line": str(_ca.get("line", ""))[:200]})
            print(f"[Guardian:ReconcileGate] ({_ca.get('letter')}) 宣稱行解掉：{_ca.get('why')}（已留帳）", file=sys.stderr)
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
            s_err = _judge_error(state, session_id, turn_seq, "VerifyScope", "", "scope", "error", e, "修好設定或回報")
            if s_err:
                reason = f"{reason}\n{s_err}" if reason else s_err
                kind = kind or "scope"
            closable = None
    if goal:
        # 需求目標（4.5）：(f1) 改了程式還沒回頭對照由程式記進度、不擋（PROGRESS_LINE_BY_PROGRAM）；(f2) 完整對照與 (f3) 改到的部位都掛目標只在交付邊界
        # （宣告完成、擋滿待查的原宣稱、本回合交了收尾檢核）判。併進寫碼查核：同一個擋滿問使用者、同一個 pending；
        # (f3) 擋訊息帶規則行，擋次預算單獨計次。state 與 transcript 交給 (f3) 從對話補掛補交的定位四行
        boundary = bool(claims_completion(last_text) or claims or aec_emitted)
        try:
            from wg_need_goal import goal_gate_reason
            g_reason = goal_gate_reason(session_id, boundary, goal_cfg,
                                        state=state, transcript_path=str(transcript) if transcript else "")
        except Exception as e:  # noqa: BLE001
            g_reason = _judge_error(state, session_id, turn_seq, "ReconcileGate", "需求目標對照", "reconcile", "goal_error", e,
                                    "修好目標檔（workflow/need-goal/）或回報")
        if g_reason:
            reason = f"{reason}\n{g_reason}" if reason else g_reason
            kind = "reconcile"
        # 記憶知識類的輕樹 (f4)：屬記憶與報告類，併進收尾報告那一份（擋滿第 3 次放行並記 reconcile_overflow，不走放行詢問）；
        # 判不了不擋（stderr＋guard_log），寫碼類那邊照舊一律擋
        try:
            from wg_need_goal import knowledge_gate_reason
            k_reason = knowledge_gate_reason(session_id, boundary, goal_cfg, turn_seq, _user_turn(state, turn_seq))
        except Exception as e:  # noqa: BLE001
            k_reason = None
            print(f"[Guardian:NeedGoal] 記憶知識類輕樹判定錯誤（這次不擋）：{type(e).__name__}: {e}", file=sys.stderr)
            append_guard_log("reconcile", {"session_id": session_id, "turn_seq": turn_seq, "knowledge_goal_error": repr(e)[:200]})
        if k_reason:
            report = f"{report}\n{k_reason}" if report else k_reason
            kind = kind or "reconcile"
    if closable and not reason:
        # 寫碼查核整個過了：這份驗證範圍記成結案（之後範圍外的測試紅了，才找得到要連回哪一次宣告）
        try:
            vs.close(state, session_id, closable)
        except Exception as e:  # noqa: BLE001
            print(f"[Guardian:VerifyScope] 結案寫帳失敗（不擋）：{type(e).__name__}: {e}", file=sys.stderr)
            append_guard_log("scope", {"session_id": session_id, "turn_seq": turn_seq, "close_error": repr(e)[:200]})
    return reason, report, kind, advice


ASK_HINT = "要問使用者問題請用 AskUserQuestion，不要用文字結束回合。"     # 寫碼查核每次 Stop 都判，用文字發問也會被擋


def _scan_report_gate_on(config: Dict[str, Any]) -> bool:
    """規則 CLOSING_RITUAL_SWITCHES：aec.scan_report_gate=false → 沒交收尾檢核不擋收尾。沒設＝照擋。"""
    return (config.get("aec") or {}).get("scan_report_gate", True) is not False


LEGACY_PENDING = ("[Guardian:ReconcileGate] 先前擋滿的查核紀錄是舊格式，沒有原宣稱可以重查：補證據解不了，"
                  "只能照【收尾放行確認】問使用者放行。")


def _code_check_text(input_data: Dict[str, Any], transcript, transcript_text: str) -> str:
    """寫碼查核（TestFail、對帳 (a)(b)(c)、pending 原宣稱）看的最後一句：先用 hook 輸入的 last_assistant_message，沒有才退回
    transcript，且不套退避偵測用的 30 字下限（長說明之後只回一句「修好了，全部完成。」也要判這句）。"""
    return (str(input_data.get("last_assistant_message") or "")
            or get_last_assistant_text(transcript, text=transcript_text, min_chars=1))


def _code_gate_no_ask(input_data: Dict[str, Any], config: Dict[str, Any], state: Optional[Dict[str, Any]],
                      receipt_key: str, own: List[Dict[str, Any]], transcript_path: str, why: str,
                      log_extra: Dict[str, Any], unknown: Optional[List[Dict[str, Any]]] = None) -> None:
    """沒有人能回答 AskUserQuestion 的收尾（子代理、裁判子 session）：只跑寫碼查核閘（對帳 (a)～(d)＋驗證範圍），
    跟主 session 同一份預算（每個使用者回合 reconcile_gate.max_blocks_per_turn 次，規則 SUBAGENT_SAME_BUDGET）：擋滿就放行、
    留帳 event=*_released，主 session 收尾照看這些改檔。未知寫入只留帳不擋（UNKNOWN_TARGET_LOGGED）。(e) 與其他 Stop 閘不跑。
    (d) 與驗證範圍不看措辭：沒有收尾文字（transcript 讀不到）也照判。headless 主 session 走 handle_stop，擋滿同樣放行留帳。"""
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
    if unknown:
        append_guard_log("reconcile", {**log_extra, "session_id": session_id, "turn_seq": turn_seq,
                                       "event": "unknown_writes_logged", "count": len(unknown),
                                       "cmds": [str(u.get("cmd", ""))[:60] for u in unknown[-3:]]})
    if not reason:
        output_nothing()
        return
    uturn = _user_turn(state, turn_seq)
    budgets = state.setdefault("no_ask_gate_turn", {})
    key = str(log_extra.get("agent_id") or receipt_key)
    rec = budgets.get(key) if isinstance(budgets.get(key), dict) and budgets[key].get("turn") == uturn else {"turn": uturn, "count": 0}
    if int(rec.get("count") or 0) >= int(rg_cfg.get("max_blocks_per_turn", 2)):
        append_guard_log("reconcile", {"session_id": session_id, "turn_seq": turn_seq, "kind": kind,
                                       "reason": reason[:300], **{**log_extra, "event": str(log_extra.get("event", "")).replace("_block", "_released")}})
        print(f"[Guardian:ReconcileGate] {why}擋滿 {rec['count']} 次，放行並留帳（主 session 收尾照看這些改檔）", file=sys.stderr)
        output_nothing()
        return
    gate = "VerifyScope" if kind == "scope" else "ReconcileGate"
    if log_extra.get("event") != "judge_block" and v6_enabled(config) and _chain_gate(
            session_id, uturn, gate, reason, input_data, config, state):
        output_nothing()
        return
    budgets[key] = {"turn": uturn, "count": int(rec.get("count") or 0) + 1}
    write_state(session_id, state)
    summary = reason.split("\n")[1].strip() if "\n" in reason else reason
    append_guard_log("reconcile", {"session_id": session_id, "turn_seq": turn_seq, "kind": kind,
                                   "reason": reason[:300], **log_extra})
    # 切入點契約（§7.10）：子代理收尾接判準卡；裁判子 session 不注入（與 PreToolUse 的 JudgeWrite 同一條：防裁判觸發裁判）
    note = "" if log_extra.get("event") == "judge_block" else entry_note(
        reason, "stop_piggyback", session_id=session_id, state=state, config=config)
    output_block(with_note(f"{non_interactive_message(gate, None, summary, why)}\n原擋訊息：\n{reason}", note))


def handle_subagent_stop(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    """SubagentStop：看子代理自己改的檔（agent_modified_files[agent_id]）與自己的收據（agent_receipt_key），寫碼查核照預算擋。"""
    session_id = input_data.get("session_id", "") or ""
    agent_id = str(input_data.get("agent_id") or "")
    state = read_state(session_id) if session_id and agent_id else None
    own = list(((state or {}).get("agent_modified_files") or {}).get(agent_id) or [])
    unknown = list(((state or {}).get("agent_unknown_writes") or {}).get(agent_id) or [])
    _code_gate_no_ask(input_data, config, state, agent_receipt_key(session_id, agent_id), own,
                      input_data.get("agent_transcript_path") or "", "子代理 Stop",
                      {"event": "subagent_block", "agent_id": agent_id}, unknown)


def handle_judge_stop(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    """裁判子 session（CLAUDE_COMPANION_JUDGE=1）的 Stop：dispatcher 其他事件照舊早退，Stop 只跑寫碼查核閘，照預算擋。
    改檔、未知寫入與收據來自 post_tool_use.handle_judge_post_tool_use 的最小記帳。"""
    session_id = input_data.get("session_id", "") or ""
    state = read_state(session_id) if session_id else None
    own = [m for m in ((state or {}).get("modified_files") or []) if (m or {}).get("session_id", session_id) == session_id]
    unknown = [u for u in ((state or {}).get("unknown_writes") or []) if (u or {}).get("session_id", session_id) == session_id]
    _code_gate_no_ask(input_data, config, state, session_id, own, input_data.get("transcript_path") or "",
                      "裁判子 session（CLAUDE_COMPANION_JUDGE=1）", {"event": "judge_block"}, unknown)


_MCP_CODE_DIR = Path(__file__).resolve().parents[2] / "tools" / "workflow-guardian-mcp"
_MCP_SEGMENT = "/tools/workflow-guardian-mcp/"


def _session_touched_mcp(state: Dict[str, Any], session_id: str) -> bool:
    """本 session（主 session＋子代理）改過記憶系統工具服務的檔（路徑含 tools/workflow-guardian-mcp/，哪一份工作樹都算）。"""
    paths = [m.get("path") for m in state.get("modified_files") or []
             if isinstance(m, dict) and m.get("session_id", session_id) == session_id]
    for mods in (state.get("agent_modified_files") or {}).values():
        paths += [m.get("path") for m in mods or [] if isinstance(m, dict)]
    return any(_MCP_SEGMENT in str(p or "").replace("\\", "/").lower() for p in paths)


def _process_rows(timeout: float = 5.0) -> Optional[List[Tuple[int, int, str, str]]]:
    """全機程序表（pid, ppid, 程式名, 指令列）；列不出回 None。只在收尾文字叫使用者重載時才查（約 1 秒）。"""
    if sys.platform == "win32":
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
               "Get-CimInstance Win32_Process | ForEach-Object { \"{0}`t{1}`t{2}`t{3}\" -f "
               "$_.ProcessId,$_.ParentProcessId,$_.Name,$_.CommandLine }"]
    else:
        cmd = ["ps", "-eo", "pid=,ppid=,comm=,args="]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[Guardian:ReloadAdvice] 列不出程序表，判不出重載建議要不要擋：{type(e).__name__}", file=sys.stderr)
        return None
    if r.returncode != 0:
        print("[Guardian:ReloadAdvice] 列程序表回非零，判不出重載建議要不要擋", file=sys.stderr)
        return None
    rows: List[Tuple[int, int, str, str]] = []
    for ln in r.stdout.splitlines():
        parts = ln.split("\t", 3) if sys.platform == "win32" else ln.split(None, 3)
        if len(parts) >= 3 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
            rows.append((int(parts[0]), int(parts[1]), parts[2].strip(), parts[3] if len(parts) > 3 else ""))
    return rows


def _session_mcp_pids(rows: List[Tuple[int, int, str, str]], self_pid: int) -> set:
    """這個 session 的工具服務程序：每個 session（claude 程序）各有自己的服務（實測：服務經 pythonw 外殼掛在各自的 claude.exe 底下，
    不是整個視窗共用一個）。從 self_pid 往上找最近的 claude 程序，回它底下跑 workflow-guardian-mcp/server.js 的程序；
    找不到所屬的 claude 程序就回全機的（保守：別的 session 的舊服務會讓判斷放行）。"""
    parent = {pid: ppid for pid, ppid, _, _ in rows}
    name = {pid: n.lower() for pid, _, n, _ in rows}
    mcp = {pid for pid, _, n, c in rows                       # 只認 node 程序：啟動外殼（pythonw run-hidden.py）的指令列也帶 server.js
           if n.lower().startswith("node") and "workflow-guardian-mcp" in c and "server.js" in c}

    def ancestors(pid: int) -> List[int]:
        out: List[int] = []
        while pid in parent and parent[pid] not in out and len(out) < 30:
            pid = parent[pid]
            out.append(pid)
        return out
    session = next((p for p in ancestors(self_pid) if name.get(p, "").startswith("claude")), None)
    return mcp if session is None else {m for m in mcp if session in ancestors(m)}


def _running_mcp_pids(timeout: float = 5.0) -> Optional[set]:
    """這個 session 正在跑的工具服務程序 pid（_session_mcp_pids）；列不出程序表回 None（判不出）。"""
    rows = _process_rows(timeout)
    return None if rows is None else _session_mcp_pids(rows, os.getpid())


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


# ─── 交付時順手點出最該修的一件（v6 G4／G5／G13）：只提醒、不擋 ─────────────────────
# 判斷交 AI、程式只管時點與記帳（wg_harvest）。缺 config pick_one 區段或 enabled 不是 true＝整個關。

def _pick_on(config: Dict[str, Any]) -> bool:
    return (config.get("pick_one") or {}).get("enabled") is True


def _record_pick(state: Dict[str, Any], session_id: str, text: str, cwd: str, config: Dict[str, Any]) -> None:
    """交付回覆裡的「順手看到最該修」段 → 本專案追蹤帳本（附建議怎麼解、該誰解）；帳上已有同一件不重記。排在所有閘之前，
    後面的閘這次擋不擋都不漏記。記失敗只 stderr（不算答過，下次照問）。"""
    if not _pick_on(config):
        return
    turn_seq = int(state.get("turn_seq", 0))
    try:
        res = record_pick(state, session_id, turn_seq, text, cwd)
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:PickOne] 「順手看到最該修」記進追蹤帳本失敗（這次沒記）：{type(e).__name__}: {e}", file=sys.stderr)
        return
    if res is not None:
        event, pick = res
        write_state(session_id, state)
        append_guard_log("pick_one", {"session_id": session_id, "turn_seq": turn_seq, "event": event, "text": pick["text"][:120]})


def _record_tracking_lines(text: str, session_id: str, turn_seq: int, cwd: str) -> None:
    """收尾那一問的答案：回覆裡的「追蹤｜<哪一件>：<現在不做的原因>」各記一筆進追蹤帳本 workflow/tracking（同收尾檢核 (k)）。
    記不下只浮 stderr。"""
    lines = [m.group(0) for m in re.finditer(r"^[\s*\-•]*追蹤\s*[｜|][^\n]+", str(text or ""), re.M)]
    if not lines:
        return
    try:
        from wg_harvest import tracking_entries, append_tracking, tracking_slug
        entries = tracking_entries(session_id, turn_seq, "\n".join(re.sub(r"^[\s*\-•]*追蹤\s*[｜|]\s*", "", ln) for ln in lines))
        if entries:
            append_tracking(tracking_slug(cwd), entries)
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:DeferralGate] 追蹤行記不進追蹤帳本：{type(e).__name__}: {e}", file=sys.stderr)


def _log_waivers(state: Dict[str, Any], session_id: str, turn_seq: int, uturn: Any, gate: str,
                 waived: Sequence[Dict[str, str]]) -> None:
    """使用者說「先這樣／跳過」放行的留帳（guard-harvest_waived）：同一個使用者回合、同一閘、同一件只記一筆
    （同回合被後面的閘擋回再 Stop、宣告行還在，不重記）。記過的鍵存 state harvest_waived_logged[sid]，換回合清掉。"""
    if not waived:
        return
    book = state.setdefault("harvest_waived_logged", {})
    mine = book.get(session_id) if isinstance(book.get(session_id), dict) else {}
    if mine.get("uturn") != uturn:
        mine = {"uturn": uturn, "keys": []}
    logged = 0
    for w in waived:
        key = f"{gate}|{w['item']}"
        if key in mine["keys"]:          # 跨 Stop 與同一批重複的那件都只記一次
            continue
        mine["keys"].append(key)
        logged += 1
        append_guard_log("harvest_waived", {"session_id": session_id, "turn_seq": turn_seq, "gate": gate,
                                            "item": w["item"], "quote": w["quote"], "line": w["line"]})
    book[session_id] = mine
    if logged:
        write_state(session_id, state)


def _record_prompt_judgments(state: Dict[str, Any], session_id: str, transcript: Any, transcript_text: str) -> None:
    """UserPromptSubmit 問過的「這句是不是糾正」「是不是在否決剛記的決策」→ 收本回合可見文字裡的宣告行
    （規則 CORRECTION_WORDS_ARE_HINTS／EXTRACT_VETO_NEEDS_JUDGMENT）。排在所有閘之前，後面的閘擋不擋都不漏收；
    沒有待判零成本。收失敗只 stderr：待判留著，下一則使用者訊息照舊規則結帳。"""
    if not (state.get("user_correction_pending") or state.get("extract_veto_pending")):
        return
    try:
        from wg_extraction import resolve_extract_veto
        from wg_friction import resolve_correction
        text, _ = get_current_turn_visible_text(transcript, text=transcript_text)
        got = [resolve_correction(state, session_id, text), resolve_extract_veto(state, session_id, text)]
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:Correction] 收糾正／否決宣告行失敗（待判留著，下一則使用者訊息照舊規則結）：{type(e).__name__}: {e}",
              file=sys.stderr)
        return
    if any(g is not None for g in got):
        write_state(session_id, state)


def _pick_boundary_seen(state: Dict[str, Any], session_id: str, turn_seq: int, boundary_now: bool) -> bool:
    """規則 PICK_ONCE_PER_USER_TURN 的交付邊界：這次收尾到了（宣告完成、交了收尾檢核、commit）就記下這個使用者回合
    （state pick_one[sid].boundary_uturn）；沒到但同一個使用者回合先前到過（那次被別的閘擋下、之後的回覆在答別的閘）也算。"""
    from wg_release_rules import user_turn
    uturn = user_turn(state, int(turn_seq or 0))
    if boundary_now:
        state.setdefault("pick_one", {}).setdefault(session_id, {})["boundary_uturn"] = uturn
        return True
    return ((state.get("pick_one") or {}).get(session_id) or {}).get("boundary_uturn") == uturn


def _pick_one_prompt(state: Dict[str, Any], session_id: str, own_mod_files: List[Dict[str, Any]], boundary: bool,
                     config: Dict[str, Any], cwd: str = "", continuation: bool = False) -> Optional[str]:
    """到了交付邊界、本 session 在上次問過或記過之後又改了程式 → 回要送的那一問（並記下問過）；不到時候回 None。
    程式檔照 wg_need_goal.is_code_path（寫碼類判準同一份；暫存檔在 post_tool_use 記改檔時就不進帳）。判斷出錯只 stderr、不送。
    問句附本 session 還沒結的追蹤項，點的是同一件就寫「同追蹤項：」（TRACKING_SAME_ITEM_NOT_REWRITTEN）。
    continuation＝這次收尾是 Stop hook 讓對話續跑出來的：一般不當條件（PICK_ONCE_PER_USER_TURN 看使用者回合）；只有 state 沒有
    使用者回合鍵（turn_prompts_seq）時，使用者回合會退回 turn_seq、續跑一回合就前進，這時續跑收尾不重問已經問過的。"""
    if not _pick_on(config) or state.get("muted"):
        return None
    turn_key = state.get("turn_prompts_seq")
    if (continuation and not (isinstance(turn_key, int) and not isinstance(turn_key, bool) and turn_key > 0)
            and ((state.get("pick_one") or {}).get(session_id) or {}).get("asked_turn")):
        return None
    turn_seq = int(state.get("turn_seq", 0))
    try:
        from wg_need_goal import is_code_path
        code = [m for m in own_mod_files if (m or {}).get("path") and is_code_path(m["path"], config)]
        if not pick_due(state, session_id, code, boundary):
            return None
        text = pick_prompt(pick_material(list(dict.fromkeys(m["path"] for m in code)), config),
                           session_open_tracking(cwd, session_id) if cwd else [])
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:PickOne] 交付時「最該修」那一問判斷出錯（這次不送）：{type(e).__name__}: {e}", file=sys.stderr)
        return None
    mark_pick_asked(state, session_id, turn_seq)
    append_guard_log("pick_one", {"session_id": session_id, "turn_seq": turn_seq, "event": "asked", "files": len(code)})
    return text


_DEFERRAL_SENTENCE_RE = re.compile(r"「(.+?)」（退縮語：")


def _deferral_covers(block: str, ev: Dict[str, Any]) -> bool:
    """退縮閘擋訊息引的那一句（wg_evasion.deferral_gate_reason 的「<句子>」（退縮語：…））含退避旗標命中的詞 → 是同一句。
    擋訊息格式對不上就當不是（旗標照留）。"""
    m = _DEFERRAL_SENTENCE_RE.search(block or "")
    phrase = str(ev.get("phrase") or "")
    return bool(m and phrase and phrase in m.group(1))


def _evasion_exempt_verdict(state: Dict[str, Any], session_id: str, ev: Dict[str, Any], transcript: Any,
                            transcript_text: str, config: Dict[str, Any], own_mod_files: List[Dict[str, Any]]) -> Any:
    """規則 EVASION_CONTEXT_EXEMPT 的事實收集：context 用量（和 DeferralGate 同一個量法）、延後的事有沒有落地（本使用者回合
    交過內容不是「無」的 (k)，或寫了 memory/_staging/next-phase-*.md）、本回合使用者原話。判定在 wg_release_rules。"""
    turn_seq = int(state.get("turn_seq", 0))
    since = _user_turn(state, turn_seq)
    ah = config.get("auto_handoff", {}) or {}
    ratio = estimate_context_usage(transcript, ah.get("context_window_tokens", 1_000_000),
                                   ah.get("context_base_overhead_tokens", 15000), text=transcript_text)
    max_ratio = float(((config.get("deferral_gate") or {}).get("max_context_ratio", 0.75)))
    aec = state.get("anti_evasion_report") or {}
    k_landed = (aec.get("session_id") == session_id and bool(turn_seq) and in_turn(aec.get("turn_seq"), turn_seq, since)
                and not _aec_blank(aec.get("k_followups")))
    handoff_landed = any(
        re.search(r"[\\/]memory[\\/]_staging[\\/]next-phase-[^\\/]*\.md$", str((m or {}).get("path", "")), re.IGNORECASE)
        and in_turn((m or {}).get("last_turn_seq", (m or {}).get("turn_seq")), turn_seq, since)
        for m in own_mod_files)
    prompts = state.get("turn_prompts") if isinstance(state.get("turn_prompts"), list) else None
    tp_seq = state.get("turn_prompts_seq")
    current = isinstance(tp_seq, int) and not isinstance(tp_seq, bool) and 0 < tp_seq <= turn_seq
    return evasion_context_exempt_verdict(is_context_exempt_phrase(str(ev.get("phrase", ""))), float(ratio or 0.0),
                                          max_ratio, k_landed or handoff_landed, prompts, current)


# ─── 等值與熱路徑（G7）：重構／效能意圖的收尾核對（規則 REFACTOR_NEEDS_EQUIVALENCE／PERF_HOT_PATH_NEEDS_MEASURE） ───
EQ_GATE = "Equivalence"


def _equivalence_on(config: Dict[str, Any], cwd: str) -> bool:
    """OverviewHub 四層合併後的 equivalence.enabled（專案層覆蓋檔也算）；讀設定失敗照開著判並浮一行。"""
    try:
        from wg_overview import _cfg as _hub_cfg, _project_root_of
        sec = _hub_cfg(config or {}, _project_root_of(cwd) if cwd else None).get("equivalence")
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:{EQ_GATE}] 讀 equivalence 設定失敗，照開著判：{type(e).__name__}: {e}", file=sys.stderr)
        return True
    return not (isinstance(sec, dict) and sec.get("enabled") is False)


def _equivalence_applies(state: Dict[str, Any], config: Dict[str, Any], code_text: str, own_mod_files: List[Dict[str, Any]],
                         turn_seq: int, since: int, cwd: str, claimed: Optional[bool] = None) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
    """等值閘這回合管不管：意圖 refactor／perf、宣告完成、本回合改過程式檔、閘開著 → (意圖, 本回合改過的程式檔)；不管回 None。
    閘本身與「不適用宣告每次留帳」（EQUIVALENCE_NA_DECLARED_ALWAYS_LOGGED 的 needed 欄）共用。"""
    import wg_verify_ledger as _vl
    from wg_overview import _intent_of
    intent = _intent_of(state)
    if intent not in ("refactor", "perf") or not (claims_completion(code_text) if claimed is None else claimed):
        return None
    exts = reconcile_cfg(config).get("code_exts") or []
    code_mods = [m for m in own_mod_files
                 if in_turn((m or {}).get("last_turn_seq", (m or {}).get("turn_seq")), turn_seq, since)
                 and _vl.is_code_file(str((m or {}).get("path") or ""), exts)]
    if not code_mods or not _equivalence_on(config, cwd):
        return None
    return intent, code_mods


def _declared_once(state: Dict[str, Any], key: str, session_id: str, since: int, text: str) -> bool:
    """收尾宣告留帳的去重：同一個使用者回合同一句只記一筆（被擋後重寫同一句不重記）。沒記過 → 記進 state[key] 並回 True。"""
    seen = state.setdefault(key, {})
    mine = seen.get(session_id) if isinstance(seen.get(session_id), dict) else {}
    said = list(mine.get("reasons") or []) if mine.get("turn") == since else []
    if text in said:
        return False
    seen[session_id] = {"turn": since, "reasons": [*said, text]}
    return True


def _loop_mutation_receipts(cmd: str, sents: List[Dict[str, Any]], exit_code: Any, cwd: str) -> List[Tuple[Any, ...]]:
    """規則 EQUIVALENCE_LOOP_EXPANDED：`for m in order side_effect boundary; do … --mutation $m …; done` 這種清單每項字面的迴圈，
    展開的每份本體各當一筆收據；條件是這筆收據的 PRESERVE_CHECK PASS 行數不少於展開份數、而且沒有 FAIL（哪一輪沒印哨兵或紅了都不算）。
    展開與「本體有跳出指令不展開」照讀檔同一支 lib/overview_hub.bash_for_bodies。"""
    from overview_hub import bash_for_bodies
    bodies = [b for b in bash_for_bodies(cmd, cwd) if "--mutation" in b]
    passes = sum(int(s.get("n") or 1) for s in sents if s.get("name") == "PRESERVE_CHECK" and s.get("verdict") == "PASS")
    if not bodies or passes < len(bodies) or any(s.get("verdict") == "FAIL" for s in sents):
        return []
    return [(b, ["PRESERVE_CHECK:PASS"], exit_code, []) for b in bodies]


def _equivalence_gate(state: Dict[str, Any], session_id: str, config: Dict[str, Any], input_data: Dict[str, Any],
                      code_text: str, own_mod_files: List[Dict[str, Any]], turn_seq: int, since: int,
                      tpath: Optional[str], cwd: str, claimed: Optional[bool] = None, hold=None) -> Optional[str]:
    """事實收集＋預算＋留帳，判定在 wg_release_rules。回擋訊息；None＝不關事或放行。改了 state（預算、擋的位置、已留帳的行），
    由呼叫端 write_state。hold＝連鎖斷路器的問法（handle_stop 的 _chain_hold）：要擋之前問，只記錄就不擋、不吃預算。
    事實：意圖（state turn_intent，只由使用者本人打的字判）、本回合改過的程式檔、它們最後一次修改之後的收據（指令完整、記了環境、
    指令沒自己寫哨兵字樣）、收尾文字的入口行。等值沒證齊、熱路徑答了缺東西 → 照寫碼查核預算擋、擋滿問使用者（無法互動 → 擋滿放行並留帳）；
    熱路徑沒答每個使用者回合擋一次。"""
    import wg_verify_ledger as _vl
    from wg_release_rules import (equivalence_verdict, format_hit, has_measure, hot_path_verdict, parse_equivalence_lines,
                                  proved_mutations)
    applies = _equivalence_applies(state, config, code_text, own_mod_files, turn_seq, since, cwd, claimed)
    if applies is None:
        return None
    intent, code_mods = applies
    last_seq = max(int(m.get("last_seq") or 0) for m in code_mods)
    receipts = []                                   # (指令, 哨兵「名稱:結論」, exit, 各 DONE 哨兵的 k=v)
    for r in receipts_of(state, session_id):
        cmd = str(r.get("cmd") or "")
        if int(r.get("seq") or 0) <= last_seq or not _vl._usable(r):
            continue
        sents = [s for s in r.get("sentinels") or [] if isinstance(s, dict)]
        receipts.append((cmd, [f"{s.get('name')}:{s.get('verdict')}" for s in sents], r.get("exit_code"),
                         [s.get("kv") or {} for s in sents if s.get("verdict") == "DONE"]))
        receipts.extend(_loop_mutation_receipts(cmd, sents, r.get("exit_code"), cwd))
    lines = parse_equivalence_lines(code_text)
    eq = equivalence_verdict(proved_mutations(receipts), lines["na"]) if intent == "refactor" else None
    hot = hot_path_verdict(lines["hot"], lines["skip"], has_measure(receipts))

    sec = state.setdefault("equivalence_gate", {})
    rec = sec.get(session_id) if isinstance(sec.get(session_id), dict) and sec[session_id].get("turn") == since else {"turn": since}
    sec[session_id] = rec
    logged = rec.setdefault("logged", [])

    def _log(event: str, line: str = "", **kw: Any) -> None:
        if line and f"{event}|{line}" in logged:
            return
        if line:
            logged.append(f"{event}|{line}")
        append_guard_log("equivalence", {"event": event, "session_id": session_id, "turn_seq": turn_seq, "intent": intent,
                                         **({"line": line[:200]} if line else {}), **kw})

    if not hot.owed:          # 不適用宣告的帳在收尾閘前面記（EQUIVALENCE_NA_DECLARED_ALWAYS_LOGGED）
        _log("hot_path", hot.evidence[0] if hot.evidence else "", why=hot.why[:200])

    # 字母：eq＝等值、hot＝熱路徑答了但缺東西（兩條照寫碼查核預算，擋滿問使用者）；hot0＝熱路徑沒答（每個使用者回合擋一次）
    answered = bool(lines["hot"] or lines["skip"])
    hits = ([("eq", eq)] if eq is not None and eq.owed else []) + ([("hot" if answered else "hot0", hot)] if hot.owed else [])
    if not hits or released_this_turn(state, session_id, "equivalence", since):
        return None
    budget = rec.get("budget")
    if any(l != "hot0" for l, _ in hits):
        how = user_released(state, session_id, "equivalence", tpath)
        if how:
            record_release(state, session_id, "equivalence", since)
            _log("user_release", via=how, why="；".join(v.why[:100] for _, v in hits))
            return None
    if any(l == "hot0" for l, _ in hits) and budget_exhausted(budget, since, 1, ["hot0"]):
        hits = [h for h in hits if h[0] != "hot0"]
        _log("hot_unanswered_passed", why="沒答熱路徑，本回合已擋過一次，放行")
    if not hits:
        return None
    text = "\n".join(format_hit(l, v) for l, v in hits)
    if hold is not None and hold(EQ_GATE, text):
        return None
    if budget_exhausted(budget, since, int(reconcile_cfg(config).get("max_blocks_per_turn", 2)), [l for l, _ in hits if l != "hot0"]):
        no_ask = non_interactive_reason(input_data, tpath)
        if no_ask:
            _log("noninteractive_released", why="；".join(v.why[:100] for _, v in hits), no_ask=no_ask)
            print(f"[Guardian:{EQ_GATE}] {no_ask}：本回合已擋滿，放行並留帳", file=sys.stderr)
            return None
        block = f"{exhausted_message(EQ_GATE, None, exhausted_summary(text))}\n原擋訊息：\n{text}\n{ASK_HINT}"
        _log("exhausted_block", why="；".join(v.why[:100] for _, v in hits))
    else:
        rec["budget"] = budget_tick(budget, since, [l for l, _ in hits])
        block = f"[Guardian:{EQ_GATE}] 收尾核對沒過：\n{text}"
        _log("block", rules=[v.rule for _, v in hits], why="；".join(v.why[:100] for _, v in hits))
    mark_block(state, session_id, "equivalence", tpath, turn_seq)
    return block


def testfail_message(failing: List[Dict[str, Any]], notes: Sequence[str] = ()) -> str:
    """TestFailGate 擋訊息：最後 3 筆紅測＋三條出路。先問使用者有沒有叫跳過（程式只收引原話的不做行豁免），
    再分程式錯還是舊斷言跟不上新需求；不給 skip／xfail 這種讓紅消失的出路——「標記為已知 regression」這種說法會把 AI 帶去加
    xfail。每筆列失敗項（規則 RED_ITEMS_ONLY_FROM_FAILURE_LINES：FAILED／ERROR 節點，不是摘要第一行）與指令實際跑的
    那行（不含註解）；notes＝不做行對到了卻沒豁免的原因（waiver_miss_notes）。"""
    return (f"[Guardian:TestFailGate] 測試未綠（{len(failing)} 項失敗），不得宣告完成。\n"
            + "\n".join(f"  - {red_item_label(f)}（指令：{cmd_run_line(f.get('cmd', ''))[:80]}）{_rerun_scope(f)}"
                        for f in failing[-3:])
            + "".join(f"\n  ! {n}" for n in notes)
            + "\n先看使用者有沒有叫你跳過或先不管這支：(a) 有 → 不動測試檔、讓它照紅，收尾寫一行"
            "「不做｜<紅的那支測試名>：使用者說「<原句片段>」」，程式對到這筆紅測就留帳放行 "
            "(b) 沒有 → 修到綠：程式錯就修程式；是使用者要的新行為讓舊斷言不再對，先寫「改舊測試｜<測試名>：<為什麼；使用者原話>」"
            "再改斷言；不准加 skip／xfail、不准只為了變綠改斷言；刻意拿舊碼跑新測試的負向對照 → 重跑那條指令、開頭加 "
            "`# 負向對照｜<指令裡的路徑>：<理由>`，那次紅就不記 "
            "(c) 修不了、使用者也沒叫跳過 → 收尾別說完成，照實寫哪支還紅、為什麼。不得籠統帶過。"
            "改動前的基底 commit 上就紅、追蹤文件也記了這一支 → 在基底 commit 的乾淨工作樹跑一次那支（要紅），收尾寫"
            "「基底紅｜<紅的那支測試名>：<基底 commit> 也紅；追蹤 <文件路徑>」，程式核對得上就留帳放行。")


RERUN_SCOPE_SHOWN_MAX = 600


def _rerun_scope(f: Dict[str, Any]) -> str:
    """規則 RED_SCOPE_FROM_FULL_COMMAND：輸出沒列出是哪一支的紅，給一條做得到的路——記紅時從整條指令解析出的每一段測試子命令與
    換目錄（test_scope.steps，不是截過的 cmd）照抄重跑、別截斷輸出：綠了而且涵蓋這個範圍就清掉，紅了照列出的那幾支記。
    判不出目標、舊條目、或範圍長過 RERUN_SCOPE_SHOWN_MAX 給通用的出路（原指令完整照跑或跑整套）。看得出是哪一支的不加。"""
    if red_units(f) or failure_lines(f.get("summary", "")):
        return ""
    tail = "；綠了而且涵蓋這個範圍就清掉這筆，紅了照列出的那幾支記（列得出是哪一支，才能用「不做｜」那條出口）"
    scope = f.get("test_scope") if isinstance(f.get("test_scope"), dict) else {}
    shown = " ； ".join(str(s) for s in scope.get("steps") or [])
    if not shown or len(shown) > RERUN_SCOPE_SHOWN_MAX:   # 判不出目標、舊條目、範圍太長：給通用的出路（不截一半給人照抄）
        return "\n    重跑：原指令完整照跑、別截斷輸出，或不點名檔跑整套" + tail
    return f"\n    重跑這個範圍（每段照抄、照順序、別接 tail／head 截輸出）：{shown}" + tail


TF_GATE = "testfail"      # wg_release 的閘名（last_block／pending_release／user_released）


def _base_red_facts(state: Dict[str, Any], session_id: str, failing: List[Dict[str, Any]], decls: List[Dict[str, str]],
                    cwd: str) -> Dict[str, Any]:
    """BASE_RED_TRACKED_NOT_OWED 的事實（判定在 wg_release_rules.base_red_failures，鍵見那裡）：本 session 的跑紅紀錄、
    每個基底對每筆紅的 cwd 是不是 HEAD 的祖先（git merge-base --is-ancestor；查不到當不是）與 committer 時間、本 session
    開始時間與提交過的 commit、每份追蹤文件（相對路徑照 session cwd 解；有沒有、是不是 .md／.txt、本 session 改過沒、內文）。"""
    from datetime import datetime
    from wg_release_rules import BASE_RED_DOC_EXTS, canon_path
    from wg_verify_ledger import _run_git
    runs = [r for r in state.get("red_run_commits") or [] if isinstance(r, dict) and r.get("session_id") == session_id]
    own = [s for rec in (state.get("committed_new_code") or {}).values() if isinstance(rec, dict) for s in rec.get("shas") or []]
    try:
        started: Optional[float] = datetime.fromisoformat(str((state.get("session") or {}).get("started_at") or "")).timestamp()
    except ValueError:
        started = None
    ancestry: Dict[Tuple[str, str], Optional[bool]] = {}
    base_times: Dict[str, Optional[float]] = {}
    for base in {d["base"] for d in decls if d["base"]}:
        for fcwd in {str(f.get("cwd") or "") for f in failing}:
            ancestry[(base, fcwd)] = bool(fcwd) and _run_git(Path(fcwd), ["merge-base", "--is-ancestor", base, "HEAD"], 3) is not None
            ct = _run_git(Path(fcwd), ["show", "-s", "--format=%ct", base], 3) if fcwd and base_times.get(base) is None else None
            if ct and ct.strip().isdigit():
                base_times[base] = float(ct.strip())
        base_times.setdefault(base, None)
    edited = {canon_path(m.get("path")) for m in state.get("modified_files") or []
              if isinstance(m, dict) and m.get("session_id", session_id) == session_id}
    tracking: Dict[str, Dict[str, Any]] = {}
    for ref in {d["tracking"] for d in decls if d["tracking"]}:
        p = Path(os.path.expanduser(ref))
        p = p if p.is_absolute() or not cwd else Path(cwd) / p
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[:2_000_000] if p.is_file() else ""
        except OSError as e:
            print(f"[Guardian:TestFailGate] 追蹤文件 {p} 讀不了（當不存在）：{type(e).__name__}: {e}", file=sys.stderr)
            text = ""
        tracking[ref] = {"exists": p.is_file(), "doc": p.suffix.lower() in BASE_RED_DOC_EXTS,
                         "own_edit": canon_path(str(p)) in edited, "text": text}
    return {"runs": runs, "ancestry": ancestry, "own_shas": own, "base_times": base_times, "started": started, "tracking": tracking}


def _red_key(f: Dict[str, Any]) -> str:
    """一筆紅測「那一件」的鍵：跑的指令＋全部失敗節點（沒有節點就用失敗輸出）；不用擋訊息的摘要（只列前三支）。"""
    units = red_units(f)
    return f"紅測 {cmd_run_line(f.get('cmd', ''))}｜" + ("、".join(sorted(units)) if units else str(f.get("summary") or "")[:500])


def _mods_sig(mods: List[Dict[str, Any]]) -> str:
    """改檔情境指紋：本 session 改過的檔與各自最後一次修改的序號／時間（放行之後又改了檔就不一樣）。"""
    rows = sorted(f"{m.get('path')}|{m.get('last_seq', m.get('seq'))}|{m.get('last_at', m.get('at'))}"
                  for m in mods if isinstance(m, dict))
    return hashlib.sha1("\n".join(rows).encode("utf-8")).hexdigest()[:16]


def _testfail_gate(state: Dict[str, Any], session_id: str, input_data: Dict[str, Any], config: Dict[str, Any],
                   failing: List[Dict[str, Any]], code_text: str, history: List[str], turn_seq: int, uturn: int,
                   tpath: Optional[str], hold=None, extra_notes: Sequence[str] = ()) -> Tuple[Optional[str], List[str]]:
    """TestFailGate（紅測＋宣告完成才呼叫）的預算與放行：吃寫碼查核那份每個使用者回合的預算（reconcile_gate_turn 鍵 "*"，
    reconcile_gate.max_blocks_per_turn），擋滿不自行放行、記 pending 要模型照【收尾放行確認】問使用者；無法互動擋滿放行並留帳。
    使用者放行的那幾筆紅測（_red_key：指令＋全部失敗節點；只放擋訊息列過的），之後的回合還紅也不再擋（綠了就從紀錄拿掉）。
    回（擋訊息或 None＝放行, 這次列出的紅測鍵）。改了 state，呼叫端寫回。hold＝連鎖斷路器的問法：要擋之前問，只記錄就不擋、不吃預算。"""
    if released_this_turn(state, session_id, TF_GATE, uturn):
        print("[Guardian:TestFailGate] 使用者已放行這一回合，本次不擋", file=sys.stderr)
        return None, []
    keys = [_red_key(f) for f in failing]
    kept = set(keep_released(state, session_id, TF_GATE, keys))
    if kept:
        print(f"[Guardian:TestFailGate] {len(kept)} 筆紅測是使用者先前放行過、還沒綠的，照放行", file=sys.stderr)
    failing, keys = [f for f, k in zip(failing, keys) if k not in kept], [k for k in keys if k not in kept]
    if not failing:
        return None, []
    msg = testfail_message(failing, waiver_miss_notes(failing, parse_not_doing(code_text), history[-3:],
                                                      state.get("testfail_waivers") or []) + list(extra_notes))
    shown_keys = keys[-3:]                                   # testfail_message 只列最後 3 筆
    budget = state.setdefault("reconcile_gate_turn", {})
    rec = budget.get(session_id) if isinstance(budget.get(session_id), dict) else None
    full = (bool(budget_exhausted(rec, uturn, int(reconcile_cfg(config).get("max_blocks_per_turn", 2)), ["*"]))
            or pending_of(state, session_id, TF_GATE) is not None)
    no_ask = non_interactive_reason(input_data, tpath)
    how = None if no_ask else user_released(state, session_id, TF_GATE, tpath)
    log = {"session_id": session_id, "turn_seq": turn_seq, "kind": "testfail", "reason": msg[:300]}
    if how:
        seen = shown_items(state, session_id, TF_GATE)
        record_release(state, session_id, TF_GATE, uturn, [*kept, *(k for k in keys if seen is None or k in seen)])
        mark_block(state, session_id, TF_GATE, tpath, turn_seq)      # 這個答案用掉了：之後要放行得再答一次
        clear_pending(state, session_id, TF_GATE)
        budget[session_id] = {"turn": uturn, "count": 0}
        append_guard_log("reconcile", {**log, "event": "user_release", "via": how})
        print(f"[Guardian:TestFailGate] 使用者放行這一回合（{how}），記 user_release", file=sys.stderr)
        return None, []
    if full and no_ask:
        append_guard_log("reconcile", {**log, "event": "noninteractive_released", "why": no_ask})
        print(f"[Guardian:TestFailGate] {no_ask}：寫碼查核本回合已擋滿，放行並留帳", file=sys.stderr)
        return None, []
    if hold is not None and hold("TestFailGate", msg):
        return None, []
    budget[session_id] = budget_tick(rec, uturn, ["*"])
    append_guard_log("reconcile", {**log, **({"event": "exhausted_block"} if full else {})})
    if not full:
        return msg, shown_keys
    set_pending(state, session_id, TF_GATE, turn_seq, _now_iso(), msg, [code_text])
    return f"{exhausted_message('TestFailGate', None, exhausted_summary(msg))}\n原擋訊息：\n{msg}\n{ASK_HINT}", shown_keys


def pre_v6_testfail_message(failing: List[Dict[str, Any]]) -> str:
    """v6 守門關閉時的 TestFailGate 擋訊息（9e476fd0 原文）：關閉時沒有「不做｜」豁免與負向對照，不能叫 AI 走那兩條出口。"""
    return (f"[Guardian:TestFailGate] 測試未綠（{len(failing)} 項失敗），"
            "不得宣告完成。\n"
            + "\n".join(f"  - {f.get('cmd', '')[:60]}: {(f.get('summary', '').splitlines() or [''])[0][:100]}"
                        for f in failing[-3:])
            + "\n選 (a) 修復 (b) 明確說明為何不修並標記為已知 regression "
            "(c) 降級任務定義。不得籠統帶過。")


def _wrote_code(mods: List[Dict[str, Any]], config: Dict[str, Any]) -> bool:
    """本 session 改過的檔裡有沒有程式檔（wg_need_goal.writes_code）。"""
    from wg_need_goal import writes_code
    return any(isinstance(m, dict) and writes_code(str(m.get("path") or ""), config) for m in mods)


def handle_stop(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    _CHAIN_TAIL.clear()
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    max_blocks = config.get("stop_gate_max_blocks", 2)
    v6 = v6_enabled(config)     # 關＝只跑 9e476fd0 就有的閘（各 v6 閘的分派點各自看它）
    # 「本回合」照規則 TURN_SINCE_USER_PROMPT：使用者打字開的回合起到現在（同伴訊息、背景通知不另開回合）。
    turn_seq = int(state.get("turn_seq", 0))
    _since = _user_turn(state, turn_seq)
    # 共用擋次（stop_gate_max_blocks 那份）：v6 開＝每個使用者回合重新計次（同一回合擋滿後放行，換了使用者回合歸零）；
    # v6 關＝照 9e476fd0，整個 session 累計
    if v6 and state.get("stop_blocked_turn") != _since:
        state["stop_blocked_count"], state["stop_blocked_turn"] = 0, _since
    stop_count = int(state.get("stop_blocked_count", 0) or 0)
    phase = state.get("phase", "working")

    def _timed_out(seg: str) -> bool:
        """這一段跑完打點（wg_hook_timing）；累計過 hook 上限的 80%（已留帳＋stderr）→ 寫回 state、放行，後面的閘這次不跑。"""
        if not _hook_lap(seg):
            return False
        write_state(session_id, state)
        output_nothing()
        return True

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
    # 收尾閘的「宣告完成」看整回合：被別的閘擋下後補件那則常不重說完成（wg_second_opinion.turn_completion_text 找出本回合宣告完成的
    # 那一則；最後一則有談到完成與否就照它）。內容檢查（退避詞、宣稱詞）仍看最後一則
    _turn_claim = ""
    if v6:
        from wg_second_opinion import turn_completion_text
        _turn_claim = turn_completion_text(transcript_text)

    def _done(text: str) -> bool:
        return bool(text and claims_completion(text)) or bool(_turn_claim)
    # accessed_files 回收（取代 per-Read PostToolUse hook）——先寫進 state，
    # 後續任何 gate 的 write_state 也會一併固化；此處立即寫防走到不寫 state 的路徑。
    # 關回合：下一則 UserPromptSubmit 才是新回合的第一句（turn_prompts 重開，見 ups_gates.track_turn_prompts）。
    # v6 開：版控口令用到這批 push 完成為止，上次收尾之後跑成功的 push 記下來（ups_gates.order_spent 據此判口令用掉了）；
    # v6 關照 9e476fd0，口令 commit 過就用掉，不掃
    turn_was_open = bool(state.get("turn_open"))
    state["turn_open"] = False
    _pushed = False
    if v6:
        from handlers.ups_gates import note_order_push
        if transcript:
            state["order_transcript"] = str(transcript)
        _pushed = note_order_push(state, transcript)
    if _harvest_accessed_files(state, transcript_text) or turn_was_open or _pushed:
        write_state(session_id, state)
    if _timed_out("讀 transcript"):
        return
    # 殘檔帳本：每次 Stop 掃一次 session scratchpad、比一次開場快照（SessionStart 記的工作樹與分支）進帳
    # （模型沒 emit 報告也不漏；python 腳本裡開的工作樹指令解析看不到，靠快照補）。fail-open。
    try:
        aec_ledger.collect_at_completion(session_id, cwd, None, int(state.get("turn_seq", 0)),
                                         snapshot=state.get("git_snapshot") if v6 else None)
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:Cleanup] 帳本收尾進帳失敗（這次少收）：{type(e).__name__}: {e}", file=sys.stderr)
    if _timed_out("殘檔帳本"):
        return
    if v6:
        _record_pick(state, session_id, code_text, cwd, config)   # 交付回覆裡的「順手看到最該修」→ 追蹤項（G13）
        _record_prompt_judgments(state, session_id, transcript, transcript_text)   # UPS 問過的「是不是糾正／否決」收宣告行（G6）

    if _timed_out("最該修記帳"):
        return

    # ── token 預警 proxy（piggyback 既有 block，不獨立打斷）──────
    # 早段算一次預警句（純函式、無副作用）；於下方各 gate 將 output_block(reason)
    # 前用 _piggyback append。token_warn_emitted 旗標只在「實際 append」時才標，
    # 並隨該 gate 的 write_state 固化（一次性、整 session 一次）。門檻見 wg_handoff.token_warn_payload。
    _token_warn = token_warn_payload(
        state, config, transcript, transcript_text=transcript_text
    )
    # 迴歸累積提示同為 piggyback payload：驗收裁判真命中 → 建議補測試/落 atom。
    _accept_hint = _acceptance_regression_hint(state, session_id, config)
    # 閱讀路徑影響（G12）：改碼回合交給背景量、這次不等；量完的結果之後的收尾附一次在擋的訊息與 stderr。只量不擋、不計預算（wg_reading_path）
    try:
        _reading_path, _rp_changed = reading_path_note(state, session_id, config) if v6 and coding_turn(state, config) else ("", False)
    except Exception as e:  # noqa: BLE001
        _reading_path, _rp_changed = f"[Guardian:ReadingPath] 閱讀路徑量測出錯：hook 內部錯誤 {type(e).__name__}: {e}", False
    if _reading_path:
        print(_reading_path, file=sys.stderr)
    if _reading_path or _rp_changed:
        write_state(session_id, state)

    _tpath = str(transcript) if transcript else None

    _later: List[Any] = []   # 後面還會擋的閘的預覽（規則 BLOCK_LISTS_LATER_GATES）；各閘共用變數算好後才掛上
    _unsynced_memo: List[Any] = []

    def _piggyback(reason: str, gate: Optional[str] = None, items: Optional[List[str]] = None) -> str:
        """附後面還會擋的閘／token 預警／驗收提示／閱讀路徑影響，最後接判準卡（切入點契約 §7.10：只認這道閘自己的擋訊息，
        後面附加的預覽與提示不拿來認切入點）。gate 有給（對帳／驗證範圍閘＝"reconcile"）就記這個閘最後一次擋的位置；
        那條路是先 write_state 再呼叫本函式，所以記完自己再寫一次 state，擋的位置才不會遺失。
        閱讀路徑結果：這次擋的是拐彎判斷 → 尾段拿掉那一題（擋訊息自己已經問了，同一則只出現一次）；別的閘擋 → 附原文
        （拐彎判斷這回合擋過、改由別的閘擋時，尾段是這一則唯一看得到那一題的地方）。
        items＝這次列給使用者看的那幾件（沒給就照擋訊息取 release_items）：使用者之後放行只放這幾件。"""
        card_note = entry_note(reason, "stop_piggyback", session_id=session_id, state=state, config=config) if v6 else ""
        rp_tail = without_judgment_prompt(_reading_path) if "TURN_JUDGMENT_REQUIRED" in reason else _reading_path
        if gate:
            mark_block(state, session_id, gate, _tpath, int(state.get("turn_seq", 0)),
                       items if items is not None else release_items(reason))
        if _later:
            try:
                note = _later[0](reason)
            except Exception as e:  # noqa: BLE001
                note = ""
                print(f"[Guardian:AlsoOwed] 預覽後面的閘失敗，略過：{type(e).__name__}: {e}", file=sys.stderr)
            if note:
                reason = f"{reason}\n{note}"
        if _token_warn:
            state["token_warn_emitted"] = True
            reason = reason + _token_warn
        if _accept_hint:
            state["acceptance_hint_emitted"] = True
            reason = reason + _accept_hint
        if rp_tail:
            reason = f"{reason}\n{rp_tail}"
        reason = with_note(reason, card_note)
        if gate:
            write_state(session_id, state)
        return reason

    if _timed_out("token 預警與閱讀路徑"):
        return

    # ── 各閘共用前置變數 ─────────────────────────────────────────
    mod_files_all = state.get("modified_files", []) or []
    # 只認「本 session 自己 Edit/Write 的檔」——共用工作樹/merged state 下，他 session
    # 改的 core 檔（session_id 不符）不得誤觸發本 session 的收尾檢核。未標記 session_id
    # 的 legacy entry 保守視為本 session（fail-open，不漏防退避）。
    own_mod_files = [
        m for m in mod_files_all
        if (m or {}).get("session_id", session_id) == session_id
    ]
    # 規則 CODING_TURN_ONLY：退避偵測、退縮閘、收尾檢核、文字評分、閱讀路徑只在寫碼回合跑（收割、收割待補照舊每回合）；
    # 本 session 前幾回合改過程式、這則宣告完成也算（改碼已經發生過，收尾照查）
    _coding = v6 and (coding_turn(state, config) or (_done(last_text) and _wrote_code(own_mod_files, config)))
    if not _coding:
        _hook_quiet()                                # 非寫碼回合不寫計時帳
    # 純 VCS commit turn 豁免收尾檢核：本 turn 已把工作寫進 VCS 歷史（可稽核＝與「藏」相反），
    # anti-evasion 目的在 commit 那刻消解。不開後門——豁免綁「本 turn 真的 commit 了」
    # （post_tool_use 記的 last_commit_turn_seq），而非「本 turn 沒 Edit」；光宣告完成不 commit
    # 仍被擋。未 commit 就 commit 的檔仍由 SyncReminder / 一般 block 兜底。「本回合」＝函式開頭算好的 _since 起到現在。
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
    # 「點出最該修」的交付邊界在各閘之前先記（規則 PICK_ONCE_PER_USER_TURN）：這次收尾被後面的閘擋下也算到過，
    # 同一個使用者回合之後沒被擋的那次收尾照樣問；state 由擋下的出口或後面的路徑寫回
    _pick_boundary = v6 and _pick_boundary_seen(
        state, session_id, turn_seq,
        _done(last_text) or claims_completion(code_text) or emitted_this_turn or committed_this_turn)
    # 上一份收尾檢核之後本 session 沒再 Edit/Write（每個改檔最後改到的回合都不晚於報告那回合）→ 沒有新東西可報，
    # ScanReport 視同已交，純問答回合不再逼重交整份（同回合的後續改動由 emitted_this_turn 覆蓋，這裡只看更早的回合）。
    # 改檔紀錄沒有回合號（legacy entry）就不知道是不是報告之後改的，不算已交（fail-safe）。
    def _mod_turn(m: Dict[str, Any]) -> int:
        return int((m or {}).get("last_turn_seq") or (m or {}).get("turn_seq") or 0)

    # 收尾檢核 (g) 交代的版控還算數：本回合交過、而且交了之後本 session 沒再改檔（報告沒記時間或改檔沒記時間 → 不算，照提醒）
    aec_covers_sync = emitted_this_turn and bool(aec.get("at")) and all(
        str((m or {}).get("last_at") or (m or {}).get("at") or "9") <= str(aec["at"]) for m in own_mod_files)
    aec_up_to_date = (
        bool(aec.get("turn_seq"))
        and aec.get("session_id") == session_id
        and all(0 < _mod_turn(m) <= int(aec.get("turn_seq") or 0) for m in own_mod_files)
    )

    # 文字評分（G15）：交付「改了哪些程式」那則回覆與本回合改過的 .md 交背景評、不等不擋；上回合送到眼前的評分一行有沒有照抄記帳
    # （wg_text_score）。回覆評不評由 wg_text_score 依 code_reply（本使用者回合改了程式、這則宣告完成）判，規則 TEXT_SCORE_CODE_REPLY_ONLY
    if _coding:
        _ts_since = _user_turn(state, turn_seq)
        try:
            from wg_need_goal import is_code_path
            _code_reply = _done(code_text) and any(
                in_turn(_mod_turn(m), turn_seq, _ts_since) and is_code_path(str(m.get("path") or ""), config)
                for m in own_mod_files)
        except Exception as e:  # noqa: BLE001
            print(f"[Guardian:TextScore] 判不出這則是不是交付改程式的回覆（這則不評）：{type(e).__name__}: {e}", file=sys.stderr)
            _code_reply = False
        if _text_score_on_stop(state, session_id, code_text, own_mod_files, turn_seq, config, code_reply=_code_reply,
                               user_turn=_ts_since):
            write_state(session_id, state)
    if _timed_out("文字評分"):
        return

    _cleanup_memo: List[Any] = []

    def _cleanup_facts() -> List[Dict[str, Any]]:
        """收尾自清閘的事實：宣告完成時才查，只查可能成為候選的那幾筆（要問 git），一次 Stop 只查一次。查失敗照放行並浮 stderr。"""
        if not _cleanup_memo:
            items: List[Dict[str, Any]] = []
            if _done(last_text):
                try:
                    if aec_ledger.ledger_path(session_id).exists():
                        items = aec_ledger.cleanup_facts(session_id)
                except Exception as e:  # noqa: BLE001
                    print(f"[Guardian:Cleanup] 查帳上的東西失敗，這次不擋：{type(e).__name__}: {e}", file=sys.stderr)
            _cleanup_memo.append(items)
        return _cleanup_memo[0]

    _so_memo: List[Any] = []

    def _so_check() -> Tuple[Any, Dict[str, Any]]:
        """SecondOpinion Gate（G9）的判定，一次 Stop 只算一次（_later_gates 預覽與本閘共用）。設定關、無法互動（headless）→ (None, {})；
        判不出照放行並浮 stderr。"""
        if not _so_memo:
            v, facts = None, {}
            cfg = _so_auto_cfg(config)
            if cfg.get("enabled", True) and not non_interactive_reason(input_data, _tpath):
                try:
                    v, facts = _so_facts(state, session_id, own_mod_files, code_text, transcript_text, config, cfg,
                                         claims_completion(code_text))
                except Exception as e:  # noqa: BLE001  判不出不擋，但浮 stderr 並留帳（健檢可查）
                    print(f"[Guardian:SecondOpinion] 判不出，這次不擋：{type(e).__name__}: {e}", file=sys.stderr)
                    append_guard_log(_SO_GATE, {"event": "error", "session_id": session_id, "turn_seq": turn_seq,
                                                "error": f"{type(e).__name__}: {e}"[:300]})
            _so_memo.append((v, facts, cfg))
        return _so_memo[0][0], {**_so_memo[0][1], "cfg": _so_memo[0][2]}

    def _later_gates(reason: str, names: Optional[List[str]] = None) -> str:
        """規則 BLOCK_LISTS_LATER_GATES：這次擋下時，照目前狀態依閘序預覽後面還會擋的閘（拐彎判斷、第二意見、知識收割、收尾自清、
        收尾檢核、同步），讓模型一回合
        補齊，不用每道閘各多花一回合。只讀不寫：不動 state、不吃預算；後面的閘還有每回合一次、擋滿放行等條件，以真正擋下為準。
        names 有給就補上預覽裡的閘名（連鎖斷路器用：預覽裡的閘之後擋下，不算這道閘之後的動作造成的）。"""
        later: List[Tuple[Tuple[str, ...], str]] = []
        _tj_missing = turn_judgment_missing(state, session_id, code_text, _user_turn(state, turn_seq)) \
            if "TURN_JUDGMENT_REQUIRED" not in reason else []
        if _tj_missing:
            later.append((("TurnJudgment",),
                          f"拐彎判斷：缺 {len(_tj_missing)} 條，收尾每條寫一行「{JUDGMENT_EXAMPLE.format(name='<名稱>')}」"))
        _so_v = _so_check()[0] if "[Guardian:SecondOpinion]" not in reason else None
        if _so_v is not None and _so_v.owed and not released_this_turn(state, session_id, _SO_GATE, _user_turn(state, turn_seq)):
            later.append((("SecondOpinion",),
                          "第二意見：跑 second_opinion_start→second_opinion_result 並在收尾寫分歧裁決四行，或宣告「不需第二意見｜理由」"))
        if "[Guardian:KnowledgeHarvest]" not in reason and not background_on(config) and harvest_gate_reason(
                state, session_id, last_text, config, own_mod_files, turn_seq, gate_turn=_user_turn(state, turn_seq),
                claimed=_done(last_text)):
            later.append((("KnowledgeHarvest",), "知識收割：值得留的先 atom_write，再呼叫 knowledge_harvest_report"))
        if ("[Guardian:Cleanup]" not in reason
                and (state.get("cleanup_gate_turn") or {}).get(session_id) != _user_turn(state, turn_seq)):
            _cv = leftover_cleanup_verdict(True, _cleanup_facts())
            if _cv.owed:
                later.append((("Cleanup",), f"收尾自清：這個 session 建的 {len(_cv.evidence)} 樣東西還在（工作樹、分支、臨時 repo、專案外資料夾），"
                              "用完的刪掉、要留的在 (i) 寫理由"))
        if ("[Guardian:ScanReport]" not in reason and own_mod_files and not state.get("scan_report_warned")
                and not committed_this_turn and _scan_report_gate_on(config)
                and detect_missing_aec_emission(last_text, own_mod_files, state.get("recent_user_prompts", []) or [],
                                                int(config.get("min_files_to_block", 2)), emitted_this_turn,
                                                claimed=_done(last_text))):
            later.append((("ScanReport",), "收尾檢核：最後呼叫 anti_evasion_report"))
        if ("[Guardian:SyncReminder]" not in reason and "[Workflow Guardian]" not in reason
                and not state.get("muted") and phase not in ("done", "syncing")):
            sr = config.get("sync_reminder", {}) or {}
            if not _unsynced_memo:       # 一次收尾只問一次 git（連鎖斷路器的閘名預覽與擋訊息的預覽共用）
                _unsynced_memo.append({(m or {}).get("path") for m in _drop_synced(own_mod_files)} - {None, ""})
            unsynced = _unsynced_memo[0]
            # 收尾檢核 (g) 已交代、或後面還欠收尾檢核（(g) 會交代版控）只免同步提醒那段（SYNC_COVERED_BY_CLOSING_CHECK）；
            # 底部一般擋（待記知識、文件漂移）不看收尾檢核，照它自己的判定列
            reminder_owed = (unsynced and not aec_covers_sync and not any("ScanReport" in n for n, _ in later)
                             and sr.get("enabled", True)
                             and int(state.get("sync_reminder_count", 0)) < int(sr.get("max_reminders", 1)))
            block_items = _sync_block_items(state, len(unsynced), int(config.get("min_files_to_block", 2)),
                                            _user_turn(state, turn_seq))
            if reminder_owed:
                later.append((("SyncReminder", "SyncBlock"),
                              f"同步：{len(unsynced)} 個改過的檔還沒 commit 或還沒 push（照口令規則處理）"))
            elif block_items:
                later.append((("SyncBlock",), f"同步：{len(block_items)} 筆待記知識或文件漂移還沒處理（待記的寫成 atom、漂移的文件補上）"))
        if names is not None:
            names.extend(g for n, _ in later for g in n)
        if not later:
            return ""
        return ("[Guardian:AlsoOwed] 這道過了之後，照目前狀態還會擋：" + "；".join(t for _, t in later)
                + "。可以這一回合一起補完再收尾（收尾檢核放最後）。")
    if v6:
        _later.append(_later_gates)

    # 規則 SECOND_OPINION_DECLARED_ALWAYS_LOGGED：收尾有「不需第二意見｜<理由>」就留帳，排在所有收尾閘前面——第二意見閘這回合不要、
    # 或前面的閘先擋下，宣告照樣記；needed 記閘當下要不要。同一個使用者回合同一句理由只記一筆（被擋後重寫同一句不重記）。
    _so_reason = second_opinion_decline(code_text)
    if (v6 and _so_reason is not None and second_opinion_decline_ok(_so_reason)
            and _declared_once(state, "second_opinion_declared", session_id, _since, _so_reason)):
        _so_v0, _so_f0 = _so_check()
        append_guard_log(_SO_GATE, {"event": "declined", "session_id": session_id, "turn_seq": turn_seq,
                                    "reason": _so_reason[:300], "code_files": _so_f0.get("code_files"),
                                    "triggers": _so_f0.get("triggers"),
                                    "needed": None if _so_v0 is None else _so_v0.rule == "SECOND_OPINION_DECLINED"})
        write_state(session_id, state)

    # 規則 EQUIVALENCE_NA_DECLARED_ALWAYS_LOGGED：收尾有「等值證法｜不適用｜<理由>」（理由成立）就留帳，同第二意見宣告排在所有收尾閘前面；
    # needed＝等值閘這回合管不管（意圖 refactor、宣告完成、改過程式檔、閘開著）。同回合同一行只記一筆。
    for _na in parse_equivalence_lines(code_text)["na"] if v6 else ():
        if reason_present(_na["reason"]) and _declared_once(state, "equivalence_na_declared", session_id, _since, _na["line"]):
            _eq_app = _equivalence_applies(state, config, code_text, own_mod_files, turn_seq, _since, cwd, _done(code_text))
            append_guard_log("equivalence", {"event": "not_applicable", "session_id": session_id, "turn_seq": turn_seq,
                                             "intent": _eq_app[0] if _eq_app else None, "line": _na["line"][:200],
                                             "reason": _na["reason"][:300], "needed": bool(_eq_app and _eq_app[0] == "refactor")})
            write_state(session_id, state)

    # 規則 USER_WAIVER_NEEDS_CITATION：使用者說「先這樣／跳過」不再整段清掉紅測；LLM 寫「不做｜<哪一支>：使用者說「<原句>」」、
    # 事項對得上那筆失敗 → 只豁免那幾筆並留帳（對到哪一筆、引了哪句、哪一回合寫的；原句不再比對使用者原話）。
    # 豁免一成立就記進 state testfail_waivers（事項、原句、那一則原話），之後同 session 同一支看帳、不看近 3 則窗口；
    # 使用者在記帳之後又提到那一支 → 那筆帳每次收尾都拿掉（原話只留近 5 則，不拿掉的話那則擠出去後帳又活回來）
    _history = _user_typed_prompts(state.get("recent_user_prompts") or [])
    _voided = [e for e in state.get("testfail_waivers") or [] if waiver_mentioned_since(e, _history)] if v6 else []
    if _voided:
        state["testfail_waivers"] = [e for e in state["testfail_waivers"] if e not in _voided]
        write_state(session_id, state)
        for _e in _voided:
            append_guard_log("testfail_waiver_voided", {"session_id": session_id, "turn_seq": turn_seq,
                                                        "item": str(_e.get("item", ""))[:80], "said": str(_e.get("said", ""))[:120]})
    if v6 and failing:
        _recent = _history[-3:]
        _ledger = state.get("testfail_waivers") or []
        failing, _waived = waived_failures(failing, parse_not_doing(code_text), _recent, _ledger, _history)
        for _f, _d in _waived:
            _said = next((p for p in reversed(_recent) if _d["via"] == "quote" and quote_in_prompts(_d["quote"], [p])), "")
            append_guard_log("testfail_waived", {"session_id": session_id, "turn_seq": turn_seq, "via": _d["via"],
                                                 "failing_cmd": str(_f.get("cmd", ""))[:120], "failing_turn": _f.get("turn_seq"),
                                                 "failing_summary": str(_f.get("summary", ""))[:200],
                                                 "item": _d.get("item", "")[:80], "user_said": _d.get("quote", "")[:120],
                                                 "said": _said[:200], "line": _d.get("line", "")[:200]})
            append_guard_log("deferral_declared", {"session_id": session_id, "turn_seq": turn_seq, "phrase": "",
                                                   "rule": "USER_WAIVER_NEEDS_CITATION",
                                                   "why": f"使用者原話「{_d.get('quote', '')[:60]}」豁免紅測 {_d.get('item', '')[:60]}",
                                                   "line": _d.get("line", "")[:200]})
            print(f"[Guardian:TestFailGate] 使用者原話「{_d.get('quote', '')[:40]}」豁免紅測 {str(_f.get('cmd', ''))[:50]}（已留帳）",
                  file=sys.stderr)
            if _said:                   # 同一事項再引用一次就換成新的那則原話（之後提到這支的判斷從新的算起）
                _old = next((e for e in _ledger if e.get("item") == _d["item"] and e.get("said") == _said[:200]), {})
                _ledger = [e for e in _ledger if e.get("item") != _d["item"]] + [
                    {"item": _d["item"][:120], "quote": _d["quote"][:120], "said": _said[:200], "turn_seq": turn_seq,
                     "units": list(dict.fromkeys([*(_old.get("units") or []), *(_d.get("units") or [])])),
                     "cmd": str(_f.get("cmd") or "")[:200], "failing": str(_f.get("summary") or _f.get("cmd") or "")[:200]}]
                state["testfail_waivers"] = _ledger
                write_state(session_id, state)
    # 規則 BASE_RED_TRACKED_NOT_OWED：收尾寫「基底紅｜<那支>：<基底 commit> 也紅；追蹤 <文件>」，三件事實（本 session 在那個 commit
    # 的乾淨工作樹跑紅過那支、那個 commit 是 HEAD 的祖先且不是自己提交的、追蹤文件點名它）都對得上才留帳放行；缺哪一件寫進擋訊息
    _base_notes: List[str] = []
    if v6 and failing:
        from wg_release_rules import base_red_failures, parse_base_red
        _bdecls = parse_base_red(code_text)
        if _bdecls:
            failing, _based, _base_notes = base_red_failures(failing, _bdecls, _base_red_facts(state, session_id, failing, _bdecls, cwd))
            for _f, _rows in _based:
                append_guard_log("testfail_base_red", {"session_id": session_id, "turn_seq": turn_seq, "rule": "BASE_RED_TRACKED_NOT_OWED",
                                                       "failing_cmd": str(_f.get("cmd", ""))[:120], "units": [r["unit"][:120] for r in _rows],
                                                       "base": sorted({r["base"] for r in _rows}), "tracking": sorted({r["tracking"] for r in _rows}),
                                                       "line": _rows[0]["line"]})
                print(f"[Guardian:TestFailGate] 基底就紅、有追蹤項：{'、'.join(r['unit'][:60] for r in _rows[:3])}"
                      f"（基底 {'、'.join(sorted({r['base'] for r in _rows}))}，已留帳）", file=sys.stderr)
    # ── 連鎖斷路器（判定 hooks/wg_chain.py，帳與還原 lib/chain_store.py；v6 才有）─────────────
    # 各閘之前問一次：警報後還沒送經過表 → 擋這一次送表；使用者答了三選一 → 照答案做（還原／歸零／放行），結果附在這次收尾的出口。
    # 之後每道閘要擋或記欠之前問 _chain_hold：警報後只記錄（跳過那道閘的擋與記欠、往下走），這一次讓警報響就送中止通知取代原擋訊息。
    _chain_ro = [False]
    if v6:
        _cs_out = chain_store.on_stop(session_id, _since, input_data, config)
        if _cs_out is not None and _cs_out.block:
            write_state(session_id, state)
            output_block(_cs_out.text)
            return
        if _cs_out is not None:
            _CHAIN_TAIL.append(_cs_out.text)
            print(_cs_out.text, file=sys.stderr)
        _chain_ro[0] = chain_store.record_only(session_id, _since, input_data, config)

    def _chain_hold(gate: str, what: str) -> bool:
        """這道閘要擋或記欠了：記一筆觸發（連預覽裡的閘名，規則 CHAIN_EDGE_PREVIEWED；只取閘名，擋訊息的預覽由 _piggyback 照原樣算）。
        True＝只記錄，呼叫端跳過擋與記欠。"""
        if not v6:
            return False
        names: List[str] = []
        if _later and not _chain_ro[0]:
            tag = "[Workflow Guardian]" if gate == "SyncBlock" else f"[Guardian:{gate}]"
            try:
                _later[0](f"{tag} {what}", names)       # 帶上這道閘的標記：預覽排除自己的方式跟真的擋訊息一樣
            except Exception as e:  # noqa: BLE001  預覽壞了只少一條排除規則，照記觸發
                names.clear()
                print(f"[Guardian:AlsoOwed] 預覽後面的閘失敗（連鎖帳這筆沒有預覽）：{type(e).__name__}: {e}", file=sys.stderr)
        _chain_ro[0] = _chain_gate(session_id, _since, gate, what, input_data, config, state, later=names)
        return _chain_ro[0]

    if not v6 and failing and claims_completion(last_text):
        state["stop_blocked_count"] = stop_count + 1
        reason = _piggyback(pre_v6_testfail_message(failing))
        write_state(session_id, state)
        output_block(reason)
        return
    if v6 and not failing:
        keep_released(state, session_id, TF_GATE, [])       # 紅測都綠了：先前放行的那幾支拿掉（state 由後面的路徑寫回）
    if v6 and failing and _done(code_text):
        _tf_block, _tf_shown = _testfail_gate(state, session_id, input_data, config, failing, code_text, _history, turn_seq,
                                              _since, _tpath, hold=_chain_hold, extra_notes=_base_notes)
        if _tf_block:
            state["stop_blocked_count"] = stop_count + 1
            write_state(session_id, state)
            output_block(_piggyback(_tf_block, TF_GATE, _tf_shown))
            return
        write_state(session_id, state)

    if _timed_out("紅測閘"):
        return

    # ── Reconcile Gate（收尾宣稱 vs 驗證收據）＋ 驗證範圍閘──────────
    # 緊接 TestFailGate 之後、evasion 偵測之前（correctness 閘優先）。不吃共用 stop_gate_max_blocks：
    # 獨立預算 reconcile_gate.max_blocks_per_turn（state reconcile_gate_turn[sid]={turn,count}，TestFailGate 也吃這份）；預算與
    # 放行的「回合」是使用者本人打字開的回合（_user_turn：同伴訊息、背景通知、hook 回饋續跑都不開新回合、不重置次數）。
    # 寫碼查核（對帳 (a)～(d)＋驗證範圍）擋滿後不放行：記 pending_release、改送擋滿訊息要模型問使用者；每次擋（不等擋滿）都查
    # 使用者有沒有在最後一次擋之後放行（wg_release.user_released）→ 放這一回合、清 pending 與計數、guard-reconcile.jsonl
    # 記 user_release（健檢列 red）；擋之前的舊答案不算。放行記「那幾件」（release_items）：之後的回合同一件原因還在就不再擋、
    # 不再問，原因消失就從放行紀錄拿掉；新出現的照判。
    # pending 只在同一個使用者回合有效（wg_release.pending_of）：換了使用者回合預算重給、不拿先前的宣稱重查。
    # 不看措辭的部分（(d) 補案例、驗證範圍）每次 Stop 都判，last_text 空也判；(a)(b)(c) 對宣稱，同一回合的 pending 帶著第一次擋滿時的
    # 宣稱原話（claims，之後的文字不附加也擠不掉），換一句話也拿原話重查。pending 只在兩種情況清：重新查核後原因真的消失，
    # 或使用者合格放行：「沒有執行查核」不等於「查核通過」。沒帶 claims 的 pending → 原宣稱無從重查 → 照擋，只能使用者放行。
    # 無法互動（headless／SDK）：不叫它問，擋滿就放行並留帳 event=noninteractive_released（比照子代理）。
    # (e) 收尾報告欄屬記憶與報告類：照舊第 3 次放行並記 reconcile_overflow（健檢 red），不走放行詢問；與寫碼部分同時擋滿時分開列。
    # 背景全量新記的範圍漏判只提醒（stderr；擋時併進 reason）。
    _rg_cfg = reconcile_cfg(config)
    _sg_cfg = _scope_cfg(config)
    if v6 and (_rg_cfg.get("enabled", True) or _sg_cfg.get("enabled", True)):
        _pend = pending_of(state, session_id, "reconcile")
        _prev_claims = [str(c) for c in (_pend or {}).get("claims") or []]
        if _turn_claim and not claims_completion(code_text) and _turn_claim not in _prev_claims:
            _prev_claims.append(_turn_claim)     # 補件那則沒重說完成：(a)(b)(c) 與交付邊界照本回合宣告完成的那一則判
        _jeb_prev = json.loads(json.dumps((state.get("judge_error_blocked") or {}).get(session_id)))   # GATE_SELF_ERROR 擋過的錯
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
        _uturn = _since
        _kept: List[str] = []
        _ctx = _mods_sig(own_mod_files)          # 放行之後又改了檔＝情境變了，先前放行的那幾件不再沿用
        if _code and released_this_turn(state, session_id, "reconcile", _uturn):
            print("[Guardian:ReconcileGate] 使用者已放行這一回合，本次不擋", file=sys.stderr)
            _code = None
        else:
            # 先前回合放行過的那幾件：原因還在照放行、拿出擋訊息；原因消失（這次沒有它）就從放行紀錄拿掉
            _kept = keep_released(state, session_id, "reconcile", release_items(_code) if _code else [], _ctx)
            if _kept:
                _code = drop_items(_code, _kept)
                print(f"[Guardian:ReconcileGate] {len(_kept)} 件是使用者先前放行過、原因還在的，照放行"
                      + ("；其餘照判" if _code else ""), file=sys.stderr)
        if _code or _report:
            # 規則 BLOCK_BUDGET_SHARED：寫碼查核每個使用者回合共用一份預算（鍵 "*"，不分是哪一條規則），擋滿 max 才算擋滿；
            # _count＝本回合擋過幾次（log 沿用）
            _budget = state.setdefault("reconcile_gate_turn", {})
            _rec = _budget.get(session_id) if isinstance(_budget.get(session_id), dict) else None
            _max = int(_rg_cfg.get("max_blocks_per_turn", 2))
            _full_rules = budget_exhausted(_rec, _uturn, _max, ["*"] if _code else [])
            _count = int(_rec.get("count", 0)) if _rec and int(_rec.get("turn", -1)) == _uturn else 0
            _code_full = bool(_code) and (bool(_full_rules) or _pend is not None)
            if _full_rules:
                print(f"[Guardian:ReconcileGate] 規則 BLOCK_BUDGET_SHARED：本回合寫碼查核已擋滿 {_max} 次",
                      file=sys.stderr)
            # 每次擋都查放行（不等擋滿）：最後一次擋之後使用者在 AskUserQuestion 選了放行或打字放行 → 放這一回合。無法互動的不查。
            _noninteractive = non_interactive_reason(input_data, _tpath) if _code else None
            _how = user_released(state, session_id, "reconcile", _tpath) if _code and not _noninteractive else None
            if _how:
                _shown = shown_items(state, session_id, "reconcile")      # 只放使用者在擋訊息裡看過的那幾件
                record_release(state, session_id, "reconcile", _uturn,
                               [*_kept, *(i for i in release_items(_code) if _shown is None or i in _shown)], _ctx)
                mark_block(state, session_id, "reconcile", _tpath, turn_seq)   # 這個答案用掉了：之後要放行得再答一次
                clear_pending(state, session_id, "reconcile")
                _budget[session_id] = {"turn": _uturn, "count": 0}
                # 規則 NO_CASE_NEEDS_USER：宣告不需要新案例的檔記成使用者已裁定（沒再改就不每回合重問）
                try:
                    import wg_verify_scope as _vs
                    _approved = _vs.approve_no_case(state, session_id)
                except Exception as e:  # noqa: BLE001  記不下只會下一回合再問一次，照擋不放寬
                    _approved = []
                    print(f"[Guardian:ReconcileGate] 記使用者對 no_case 的裁定失敗（下一回合會再問）：{type(e).__name__}: {e}",
                          file=sys.stderr)
                append_guard_log("reconcile", {
                    "event": "user_release", "session_id": session_id, "turn_seq": turn_seq, "kind": _vg_kind,
                    "via": _how, "count": _count, "reason": _code[:300], **({"no_case_approved": _approved} if _approved else {}),
                })
                print(f"[Guardian:ReconcileGate] 使用者放行這一回合（{_how}），記 user_release", file=sys.stderr)
                _code = None
            elif _code_full and _noninteractive:
                # 沒有人能回答放行詢問：比照子代理，擋滿就放行並留帳（主 session 之後的收尾照看這些改檔）
                append_guard_log("reconcile", {
                    "event": "noninteractive_released", "session_id": session_id, "turn_seq": turn_seq, "kind": _vg_kind,
                    "count": _count, "why": _noninteractive, "reason": _code[:300],
                })
                print(f"[Guardian:ReconcileGate] {_noninteractive}：寫碼查核本回合擋滿 {_max} 次，放行並留帳", file=sys.stderr)
                _code = None
            if not _code:
                _code_full = False
            # 收尾報告那一份（(e)、(f4)，記憶與報告類）只數自己的「e」：寫碼查核先擋過幾次不吃掉它的次數
            _report_full = bool(budget_exhausted(_rec, _uturn, _max, ["e"]))
            if not _code and _report and _report_full:
                # 只剩收尾報告那一份：第 3 次放行並記 reconcile_overflow（健檢 red）
                state.setdefault("reconcile_overflow", {})[session_id] = {
                    "turn": turn_seq, "at": _now_iso(), "kind": "report", "reason": _report[:300],
                }
                append_guard_log("reconcile_overflow", {
                    "session_id": session_id, "turn_seq": turn_seq, "kind": "report", "count": _count,
                    "reason": _report[:300],
                })
                print(f"[Guardian:ReconcileGate] 收尾報告那一份本回合已擋滿 {_max} 次，這次放行但記 reconcile_overflow（健檢列 red）",
                      file=sys.stderr)
                write_state(session_id, state)
            elif not _code and not (_report and not _report_full):
                write_state(session_id, state)
            elif _chain_hold("VerifyScope" if _vg_kind == "scope" else "ReconcileGate", _code or _report):
                _unmark(state.get("judge_error_blocked"), session_id, _jeb_prev)
                write_state(session_id, state)
            else:
                _budget[session_id] = budget_tick(_rec, _uturn, ["*"] if _code else ["e"])
                _gate = "VerifyScope" if _vg_kind == "scope" else "ReconcileGate"
                if _code_full:
                    set_pending(state, session_id, "reconcile", turn_seq, _now_iso(), _code,
                                [code_text] if claims_completion(code_text)
                                else ([_turn_claim] if _turn_claim else []))      # pending 已在就沿用原 claims
                    _summary = exhausted_summary(_code)                          # 列全部命中條目，不只第一條
                    _n = _count if _full_rules else None                       # 擋滿來自本回合先前記的 pending：不報次數
                    _msg = f"{exhausted_message(_gate, _n, _summary)}\n原擋訊息：\n{_code}"
                    if _report:
                        _msg += f"\n另外（記憶與報告類，不走放行詢問，照原規則處理）：\n{_report}"
                else:
                    _msg = "\n".join(x for x in (_code, _report) if x)
                if _code and not _noninteractive:
                    _msg += f"\n{ASK_HINT}"
                append_guard_log("reconcile", {
                    "session_id": session_id, "turn_seq": turn_seq, "kind": _vg_kind, "count": _count + 1,
                    "excerpt": _msg.split("\n")[1][:160] if "\n" in _msg else _msg[:160],
                    **({"event": "exhausted_block"} if _code_full else {}),
                })
                write_state(session_id, state)
                output_block(_piggyback(_msg + (f"\n{_vg_advice}" if _vg_advice else ""), "reconcile"))
                return
        elif _vg_advice or _pend_cleared or _kept:
            write_state(session_id, state)

    _ev_now: Optional[Dict[str, Any]] = None      # 這次收尾新記的退避旗標（退縮閘擋下同一句時拿掉，見下）
    if not state.get("evasion_flag") and (_coding or not v6):
        recent_prompts = state.get("recent_user_prompts", []) or []
        _nd_audit: List[Dict[str, Any]] = []
        ev = detect_evasion(last_text, recent_prompts, audit=_nd_audit)
        # 規則 NOT_DOING_DECLARED：退避語對到有理由的不做行（含「使用者說「…」」）→ 不標、留帳
        for _a in _nd_audit:
            append_guard_log("evasion_declared", {"session_id": session_id, "turn_seq": int(state.get("turn_seq", 0)),
                                                  "phrase": _a.get("phrase", ""), "rule": _a.get("rule", ""),
                                                  "why": str(_a.get("why", ""))[:200], "line": str(_a.get("line", ""))[:200]})
        if ev and v6:
            # 規則 EVASION_CONTEXT_EXEMPT：context 快滿、延後的事已落地、使用者沒叫現在做 → 這筆延後語不標紅不注入（照記錄）
            try:
                _ex = _evasion_exempt_verdict(state, session_id, ev, transcript, transcript_text, config, own_mod_files)
            except Exception as e:  # noqa: BLE001
                _ex = None
                print(f"[Guardian:Evasion] context 豁免判不出，照舊標記：{type(e).__name__}: {e}", file=sys.stderr)
            if _ex is not None and not _ex.owed:
                append_guard_log("evasion_exempt", {"session_id": session_id, "turn_seq": int(state.get("turn_seq", 0)),
                                                    "phrase": ev.get("phrase", ""), "why": _ex.why})
                ev = None
        if ev:
            ev["at"] = _now_iso()
            state["evasion_flag"] = _ev_now = ev
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

    if _timed_out("寫碼查核"):
        return

    # ── TurnJudgment Gate（G11）──────────────────────────────────
    # 規則 TURN_JUDGMENT_REQUIRED（判定在 wg_release_rules 的 G11 段，核對與留帳在 wg_reading_path.turn_judgment_note）：背景量完附的
    # 「到門檻的側面數據＋那一題」要有對應的「拐彎判斷｜」五欄行。拐彎判斷是收尾的輔助視角，排在寫碼查核（對帳）之後、與 G9／G7 同序；
    # 前面的閘擋下時由 _later_gates 預告還缺幾條。缺 → 每個使用者回合擋一次（不吃 stop_gate_max_blocks）；齊 → 留帳 judged。
    # 程式只核對五欄不評內容；判不了不擋，浮 stderr。
    _tj_prev = ((state.get("reading_path") or {}).get(session_id) or {}).get("blocked_turn")
    try:
        _turn_block, _tj_changed = turn_judgment_note(state, session_id, code_text, _since, turn_seq) if v6 else (None, False)
    except Exception as e:  # noqa: BLE001
        _turn_block, _tj_changed = None, False
        print(f"[Guardian:ReadingPath] 拐彎判斷核對出錯（這次不擋）：{type(e).__name__}: {e}", file=sys.stderr)
    if _turn_block and _chain_hold("TurnJudgment", _turn_block):
        _unmark((state.get("reading_path") or {}).get(session_id), "blocked_turn", _tj_prev)
        _turn_block = None
    if _turn_block:
        reason = _piggyback(_turn_block)
        # 規則 PICK_ONE_WITH_TURN_JUDGMENT：拐彎判斷擋下時「順手看到最該修」該問就同一則一起問（記問過），補一次就兩件都寫，
        # 不再另讓對話續跑一輪（開關 pick_one.pre_close；關了照舊排在所有閘之後另送）
        _tj_pick = (v6 and not _chain_ro[0] and _pick_pre_close_on(config) and _pick_one_prompt(
            state, session_id, own_mod_files, _pick_boundary, config, cwd, continuation=bool(input_data.get("stop_hook_active"))))
        if _tj_pick:
            reason = f"{reason}\n{with_note(_tj_pick, entry_note(_tj_pick, 'stop_piggyback', session_id=session_id, state=state, config=config))}"
        write_state(session_id, state)          # 記擋的回合（blocked_turn）、_piggyback 標的一次性旗標與最該修問過
        output_block(reason)
        return
    if _tj_changed:
        write_state(session_id, state)

    if _timed_out("拐彎判斷"):
        return

    # ── SecondOpinion Gate（G9）──────────────────────────────────
    # 規則 SECOND_OPINION_REQUIRED／SECOND_OPINION_DECLINED（判定在 wg_release_rules 的 G9 段，事實由 wg_second_opinion 收）：大任務或
    # 改到高風險部位宣告完成 → 本回合要真的跑過第二意見、收尾有分歧裁決四行，或宣告「不需第二意見｜理由」（留帳 guard-second_opinion.jsonl）。
    # 吃寫碼查核那套（wg_release，閘名 second_opinion）：每個使用者回合擋 second_opinion.auto.max_blocks_per_turn 次（預設 1）後擋滿，
    # 不自行放行、記 pending、要模型用 AskUserQuestion 問使用者。滿足或使用者放行 mark_ok（記回合與已審的高風險檔）：之後為採納意見做的修改不再要求，改到新的高風險檔或新改的檔數再過門檻才再要（SECOND_OPINION_ONCE_PER_CLAIM）。
    # 子代理、裁判 session 走別的 Stop 入口；headless 由 _so_check 的 non_interactive_reason 判，都不觸發。
    _sov, _sof = _so_check() if v6 else (None, {})
    _so_uturn = _user_turn(state, turn_seq)
    if _sov is not None and _sof.get("satisfied"):
        _so_mark_ok(state, session_id, turn_seq, _sof)
        clear_pending(state, session_id, _SO_GATE)
        write_state(session_id, state)          # 宣告不需的帳在收尾閘前面已記（SECOND_OPINION_DECLARED_ALWAYS_LOGGED）
    elif _sov is not None and _sof.get("waiting"):
        # 規則 SECOND_OPINION_WAITING_NOT_DONE：還在跑、收尾有「等第二意見｜<job_id>」行 → 不算宣告完成，不擋不吃擋次，只留帳
        append_guard_log(_SO_GATE, {"event": "waiting", "session_id": session_id, "turn_seq": turn_seq,
                                    "job": _sof["waiting"][-1], "code_files": _sof.get("code_files")})
        if _so_background_on(config):           # 規則 SECOND_OPINION_DONE_NOTICE：在等的 job 記進看守，跑完了下一批工具回應或收尾提醒取回
            for _so_job in _sof["waiting"]:
                _so_watch_job(state, session_id, _so_job, waited=True)
            write_state(session_id, state)
    elif _sov is not None and _sov.owed and released_this_turn(state, session_id, _SO_GATE, _so_uturn):
        print("[Guardian:SecondOpinion] 使用者已放行這一回合，本次不擋", file=sys.stderr)
    elif _sov is not None and _sov.owed:
        _so_how = user_released(state, session_id, _SO_GATE, _tpath)
        if _so_how:
            record_release(state, session_id, _SO_GATE, _so_uturn)
            mark_block(state, session_id, _SO_GATE, _tpath, turn_seq)   # 這個答案用掉了：之後要放行得再答一次
            clear_pending(state, session_id, _SO_GATE)
            _so_mark_ok(state, session_id, turn_seq, _sof)
            append_guard_log(_SO_GATE, {"event": "user_release", "session_id": session_id, "turn_seq": turn_seq,
                                        "via": _so_how, "reason": format_hit(_SO_LETTER, _sov)[:300]})
            print(f"[Guardian:SecondOpinion] 使用者放行這一回合（{_so_how}），記 user_release", file=sys.stderr)
            write_state(session_id, state)
        elif _chain_hold("SecondOpinion", format_hit(_SO_LETTER, _sov)):
            pass
        else:
            _so_budget = state.setdefault("second_opinion_gate_turn", {})
            _so_rec = _so_budget.get(session_id) if isinstance(_so_budget.get(session_id), dict) else None
            _so_pend = pending_of(state, session_id, _SO_GATE) is not None
            _so_max = int(_sof["cfg"].get("max_blocks_per_turn", 1))
            _so_full = _so_pend or bool(budget_exhausted(_so_rec, _so_uturn, _so_max, [_SO_LETTER]))
            _so_hit = format_hit(_SO_LETTER, _sov)
            # 規則 SECOND_OPINION_BACKGROUND：開關 second_opinion.auto.background 開 → 提示寫 start 後不用等、跑完再接上；關照舊
            _so_hint = second_opinion_hint_background() if _so_background_on(config) else second_opinion_hint()
            if _so_full:
                set_pending(state, session_id, _SO_GATE, turn_seq, _now_iso(), _so_hit, [code_text])
                _so_msg = (f"{exhausted_message('SecondOpinion', None if _so_pend else _so_max, _so_hit)}\n原擋訊息：\n"
                           f"{_so_hit}\n{_so_hint}")
            else:
                _so_msg = (f"[Guardian:SecondOpinion] 宣告完成前要第二意見（本 session 改了 {_sof.get('code_files')} 個程式檔）\n"
                           f"{_so_hit}\n{_so_hint}")
            _so_budget[session_id] = budget_tick(_so_rec, _so_uturn, [_SO_LETTER])
            append_guard_log(_SO_GATE, {"event": "exhausted_block" if _so_full else "block", "session_id": session_id,
                                        "turn_seq": turn_seq, "rule": _sov.rule, "why": _sov.why[:200],
                                        "code_files": _sof.get("code_files"), "triggers": _sof.get("triggers")})
            write_state(session_id, state)
            output_block(_piggyback(_so_msg, _SO_GATE))
            return
    if _timed_out("第二意見"):
        return

    # ── Equivalence Gate（G7）──
    # 重構／效能意圖、本回合改過程式檔、宣告完成 → 等值證法三類與熱路徑一問的收尾核對（_equivalence_gate；規則在 wg_release_rules）。
    # 自己的預算（不吃 stop_gate_max_blocks），擋滿問使用者。判不出（hook 內部錯）→ 不擋，浮 stderr 並留帳。
    try:
        _eq_block = v6 and _equivalence_gate(state, session_id, config, input_data, code_text, own_mod_files, turn_seq, _since, _tpath, cwd,
                                      claimed=_done(code_text), hold=_chain_hold)
    except Exception as e:  # noqa: BLE001
        _eq_block = None
        print(f"[Guardian:{EQ_GATE}] 收尾核對出錯，這次不擋：{type(e).__name__}: {e}", file=sys.stderr)
        append_guard_log("equivalence", {"event": "error", "session_id": session_id, "turn_seq": turn_seq, "error": repr(e)[:200]})
    if _eq_block:
        reason = _piggyback(_eq_block)
        write_state(session_id, state)          # 連同 _piggyback 標的一次性旗標一起寫
        output_block(reason)
        return

    if _timed_out("等值證法"):
        return

    # ── Deferral Gate（退縮歸屬）────────────────────────────────
    # 主任務已完工（完成宣告 ∨ 本 turn 已 commit）且 context 用量 ≤ deferral_gate.
    # max_context_ratio 時，收尾把「帶受詞、可做的事」推給下個 session／獨立議題／
    # 非我造成 → 擋回三選一。每回合一次、共用 stop_gate_max_blocks
    # 全域預算。判定純函式在 wg_evasion.deferral_gate_reason；量測失敗 fail-open。
    # 底下四個「每回合最多擋一次」的閘（Deferral、KnowledgeHarvest、Harvest-Pending、AEC-Pending）的回合都用
    # _user_turn（使用者打字開的回合）：同伴訊息、背景通知每則都讓 turn_seq +1，拿它當鍵會每則訊息後又擋一次。
    _uturn = _since
    if stop_count < max_blocks and last_text and (_coding or not v6):
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
        _dg_audit: List[Dict[str, Any]] = []
        try:
            dg = deferral_gate_reason(
                last_text,
                state.get("recent_user_prompts", []) or [],
                claimed=_done(last_text),
                turn_seq=_uturn,
                gated_turn=state.get("deferral_gate_turn"),
                committed_this_turn=committed_this_turn,
                context_ratio=_dg_ratio,
                config=config,
                audit=_dg_audit,
            )
        except Exception as e:
            dg = None
            print(f"[Guardian:DeferralGate] error (fail-open): {e}", file=sys.stderr)
        for _a in _dg_audit:   # 規則 NOT_DOING_DECLARED：退縮句對到不做行或追蹤行 → 不擋、留帳
            append_guard_log("deferral_declared", {"session_id": session_id, "turn_seq": turn_seq,
                                                   "phrase": _a.get("phrase", ""), "rule": _a.get("rule", ""),
                                                   "why": str(_a.get("why", ""))[:200], "line": str(_a.get("line", ""))[:200]})
        _record_tracking_lines(last_text, session_id, turn_seq, cwd)
        if dg and not _chain_hold("DeferralGate", dg):
            state["deferral_gate_turn"] = _uturn
            state["stop_blocked_count"] = stop_count + 1
            if v6 and _ev_now is not None and state.get("evasion_flag") is _ev_now and _deferral_covers(dg, _ev_now):
                # 退縮閘這次擋下的就是退避旗標那一句：已逼著當場處理，下一則使用者訊息不再追問同一件（事件照留給收尾檢核對照）
                state["evasion_flag"] = None
                append_guard_log("evasion", {"session_id": session_id, "event": "covered_by_deferral",
                                             "phrase": _ev_now.get("phrase", "")})
            append_guard_log("deferral", {
                "session_id": session_id,
                "turn_seq": turn_seq,
                "context_ratio": round(float(_dg_ratio), 3),
                "excerpt": dg.split("\n")[1][:160] if "\n" in dg else "",
            })
            write_state(session_id, state)
            output_block(_piggyback(dg))
            return

    if _timed_out("退縮歸屬"):
        return

    # ── KnowledgeHarvest Gate（階段完工知識收割）────────────────
    # 宣告完成＝階段完工 → 要求呼叫 knowledge_harvest_report（items=[] 也要）。判定在
    # wg_harvest.harvest_gate_reason（活動門檻、冷卻只認 validated、dismiss 詞表重用 wg_evasion）。
    # 不吃 stop_gate_max_blocks 共用預算、每回合最多擋一次（harvest_gate_turn[sid] 記 _user_turn）；
    # state 全按 session_id 分區——隔壁 session 的收割不放行本 session。
    _hv_waived: List[Dict[str, str]] = []
    hv_reason = harvest_gate_reason(state, session_id, last_text, config, own_mod_files, turn_seq, gate_turn=_uturn,
                                    claimed=_done(last_text), waived=_hv_waived)
    _log_waivers(state, session_id, turn_seq, _uturn, "harvest", _hv_waived)   # 使用者說先這樣／跳過 → 放行並留帳
    if hv_reason and v6 and background_on(config):
        # 規則 HARVEST_IN_BACKGROUND：收割交背景的本地免費模型產待審候選卡，不擋寫碼 AI 一回合；送不出去才照舊擋（不靜默略過）
        state.setdefault("harvest_gate_turn", {})[session_id] = _uturn
        if bg_harvest(session_id, _tpath or "", cwd, turn_seq, config):
            write_state(session_id, state)
            hv_reason = None
    if hv_reason and not _chain_hold("KnowledgeHarvest", hv_reason):
        state.setdefault("harvest_gate_turn", {})[session_id] = _uturn
        append_guard_log("knowledge_harvest", {
            "session_id": session_id, "turn_seq": turn_seq,
            "own_mod_files": len(own_mod_files),
            "accessed": len(state.get("accessed_files") or []),
        })
        write_state(session_id, state)
        output_block(_piggyback(hv_reason))
        return

    if _timed_out("知識收割"):
        return

    # ── Harvest-Pending Gate：收割回報有 item 對不上 receipt ──────
    # post_tool_use 核對落 knowledge_harvest[sid].pending；此處每回合（_user_turn）擋一次要求真做完再重報。
    # 本則是中途狀態句（仍在等 agent 回報…）→ 不擋，等真收尾再擋（wg_harvest.in_progress_text）。
    _hp_waived: List[Dict[str, str]] = []
    hp_reason = pending_gate_reason(state, session_id, turn_seq, last_text, gate_turn=_uturn,
                                    waived=_hp_waived)
    _log_waivers(state, session_id, turn_seq, _uturn, "harvest_pending", _hp_waived)   # 使用者說先這樣／跳過 → 整批放行並留帳
    if hp_reason and not _chain_hold("Harvest-Pending", hp_reason):
        state.setdefault("harvest_pending_gate_turn", {})[session_id] = _uturn
        append_guard_log("harvest_pending", {
            "session_id": session_id, "turn_seq": turn_seq,
            "items": (state.get("knowledge_harvest", {}).get(session_id) or {}).get("pending", [])[:5],
        })
        write_state(session_id, state)
        output_block(_piggyback(hp_reason))
        return

    if _timed_out("收割對帳"):
        return

    # ── Cleanup Gate（收尾自清：規則 LEFTOVER_NEEDS_CLEANUP）─────────────
    # 宣告完成時，這個 session 建的工作樹、已合併分支、臨時 repo、專案外檔案資料夾還在又沒說要留 → 擋一次，列刪除指令，
    # 讓 AI 自己清（使用者原話：要提醒 LLM 才會刪用完的工作分支）。事實由 aec_ledger.cleanup_facts 現場查（只查可能成為候選的）、判定在
    # wg_release_rules；排在收尾檢核之前，AI 寫留的理由才進得了同一份 (i)。不吃 stop_gate_max_blocks、每個使用者回合最多擋一次
    # （cleanup_gate_turn[sid] 記 _uturn）。
    if v6 and (state.get("cleanup_gate_turn") or {}).get(session_id) != _uturn:
        cv = leftover_cleanup_verdict(_done(last_text), _cleanup_facts())
        if cv.owed and not _chain_hold("Cleanup", cv.why):
            state.setdefault("cleanup_gate_turn", {})[session_id] = _uturn
            append_guard_log("cleanup", {"session_id": session_id, "turn_seq": turn_seq, "items": list(cv.evidence[:8])})
            write_state(session_id, state)
            output_block(_piggyback(aec_ledger.cleanup_block_message(
                session_id, leftover_candidates(_cleanup_facts()), cv.why)))
            return

    if _timed_out("收尾自清"):
        return

    # ── Scan-Report Gate ────────────────────────────────────────
    # 降條件觸發 — 只在動 core 檔或多檔（≥min_files_to_block）且宣告完成時要求收尾檢核；
    # 純單檔/文件小改不觸發（避免過度觸發成儀式性負擔，非防退避）。aec.scan_report_gate=false 整道不擋（規則 CLOSING_RITUAL_SWITCHES）。
    if (own_mod_files and not state.get("scan_report_warned") and not committed_this_turn and _scan_report_gate_on(config)
            and (_coding or not v6)):
        recent_prompts = state.get("recent_user_prompts", []) or []
        sr_min_files = int(config.get("min_files_to_block", 2))
        # 門檻達到、本來要擋，使用者近 3 則說了「先這樣／跳過」→ 收尾檢核放行並留帳
        _cc_w = None if (emitted_this_turn or aec_up_to_date or not completion_threshold_met(
            last_text, own_mod_files, sr_min_files, claimed=_done(last_text))) else closing_check_waiver(last_text, recent_prompts)
        _log_waivers(state, session_id, turn_seq, _uturn, "closing_check", [_cc_w] if _cc_w else [])
        if detect_missing_aec_emission(
            last_text, own_mod_files, recent_prompts, sr_min_files, emitted_this_turn or aec_up_to_date, claimed=_done(last_text)
        ) and not _chain_hold("ScanReport", "宣告完成且動到 core 檔或多檔，本回合沒交收尾檢核 anti_evasion_report"):
            state["stop_blocked_count"] = stop_count + 1
            state["scan_report_warned"] = True  # 保留 one-shot anti-nag（比照現況）
            reason = _piggyback(
                "[Guardian:ScanReport] 宣告完成且本 session 動到 core 檔/多檔（達收尾檢核門檻），"
                "但本回合未 emit anti_evasion_report，違反 IDENTITY「反退避契約」。\n"
                "請呼叫 MCP tool anti_evasion_report(a..i) 提交收尾檢核——內容走 HUD、"
                "chat 只留折疊 chip：\n"
                "  (a) 缺失發現與修補清單：`- 檔:行 — 改了什麼`；無則填「無」。**必寫**\n"
                "  (b) AI 逃避通報：本次有/沒有 忽略 / 偷埋的現象；**僅發生時填**，否則「無」\n"
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
                "十參都 required、未發生填「無」（(c) 已刪，不必送）；本回合已交收割報告的話 (d) 可只寫「見收割報告」。"
                "不得用 prose「不在範圍 / 留給未來」籠統帶過。"

            )
            write_state(session_id, state)
            output_block(reason)
            return

    if _timed_out("收尾檢核"):
        return

    # ── AEC-Pending Gate：報告把「記憶寫入」推到之後 ─────────────────
    # (d)「尚未寫／見下一動」、(h)「下一動＝寫 atom」= 把知識留給下一回合（使用者要再問一次
    # 才會補）。post_tool_use 判定落 report["d_pending"]；此處每回合（_user_turn）擋一次（共用 max_blocks
    # 預算）：模型 atom_write 後重新 emit → 新報告無 d_pending → 放行。
    pending = (aec.get("d_pending") or []) if (_coding or not v6) else []
    if (
        emitted_this_turn and pending
        and state.get("aec_pending_gate_turn") != _uturn
        and stop_count < max_blocks
        and not _chain_hold("AEC-Pending", f"收尾檢核把 {len(pending)} 項記憶寫入推到之後")
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

    if _timed_out("報告待寫"):
        return

    # HUD 不可達且本回合 emit 為 notable/real-evasion → 印一行告知報告檔在哪（可觀測性鐵律：push 不到窗不得 fail-silent），
    # 不擋、不把報告內容貼回聊天（設計取捨：報告任何理由都不進聊天）。post_tool_use 標旗，此處消費一次。
    # 消費前**再查一次**：emit 當下不可達可能是暫時的（Node 剛換手、HUD 頁重連中），現在窗活著就不印；
    # 兩次判定都落 guard-aec_hud.jsonl 可稽核。
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
        if not alive:
            _why = info.get("reason") or f"心跳 {info.get('age_s')} 秒前、連線 {info.get('clients')} 條"
            _file = WORKFLOW_DIR / "aec-report" / f"{session_id}-t{aec.get('turn_seq', turn_seq)}.json"
            print(f"[Guardian:AEC] HUD 視窗開不起來（{_why}），這輪的收尾報告在 {_file}，開 "
                  f"http://127.0.0.1:{int(config.get('dashboard_port', 3848))}/aec/hud 就看得到", file=sys.stderr)
        write_state(session_id, state)

    if _timed_out("報告視窗"):
        return

    # ── Reload Advice Gate（規則 RELOAD_ADVICE_ALREADY_LOADED）──────────────
    # 收尾叫使用者 Reload Window 前，查每個活著的工具服務是不是已載入磁碟上最新的程式；都是最新就擋一次。每個使用者回合一次。
    # 只對記憶系統自己的工具服務有意義：本 session 沒改過 tools/workflow-guardian-mcp/ 底下的檔就不判（也不列全機程序表）。
    _rl_turn = _user_turn(state, int(state.get("turn_seq", 0)))
    if (v6 and stop_count < max_blocks and state.get("reload_advice_turn") != _rl_turn
            and _session_touched_mcp(state, session_id)):
        _rl_text = get_last_assistant_text(transcript, text=transcript_text, min_chars=1)
        if RELOAD_ADVICE_RE.search(_rl_text or ""):
            _rl = reload_advice_verdict(_rl_text, *_mcp_load_facts(), time.time())
            if _rl.owed and not _chain_hold("ReloadAdvice", _rl.why):
                state["reload_advice_turn"] = _rl_turn
                state["stop_blocked_count"] = stop_count + 1
                write_state(session_id, state)
                output_block(_piggyback(
                    f"[Guardian:ReloadAdvice] 規則 {_rl.rule}：{_rl.why}｜證據：{'；'.join(_rl.evidence)}\n"
                    "不必叫使用者 Reload Window：拿掉那句再收尾。若是程式更新以外的理由要重開（改了 MCP 啟動設定、settings.json 等），"
                    "保留那句並加一行「重載原因：<哪個設定改了>」。"))
                return

    if _timed_out("Reload 建議"):
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
        if (uncommitted or unpushed) and aec_covers_sync:
            # 規則 SYNC_COVERED_BY_CLOSING_CHECK：本回合的收尾檢核 (g) 已交代哪些 commit、哪些沒上與理由（AI 的宣告＋HUD 留帳），
            # 而且交了之後沒再改檔 → 同一件事不再擋一回合；只留 stderr 一行與留帳
            print(f"[Guardian:SyncReminder] {len(uncommitted)} 個未 commit、{len(unpushed)} 個 repo 未 push："
                  "本回合收尾檢核 (g) 已交代，不另擋", file=sys.stderr)
            append_guard_log("sync_reminder", {"event": "covered_by_aec", "session_id": session_id, "turn_seq": turn_seq,
                                               "uncommitted": len(uncommitted), "unpushed": len(unpushed)})
        elif uncommitted and not _chain_hold("SyncReminder", f"{len(uncommitted)} 個已修改的檔還沒 commit"):
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
        if unpushed and not _chain_hold("SyncReminder", f"{len(unpushed)} 個 repo 已 commit 還沒 push"):
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

    if _timed_out("同步提醒"):
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
        if aa and not _chain_hold("AtomAudit", aa[0]):
            aa_reason, aa_names = aa
            prompted = state.setdefault("atom_audit_prompted", [])
            prompted.extend(n for n in aa_names if n not in prompted)
            state["stop_blocked_count"] = stop_count + 1
            write_state(session_id, state)
            output_block(_piggyback(aa_reason))
            return

    if _timed_out("取用稽核"):
        return

    # ── Deep Post-Mortem Gate（Stage 3）────────────────────────
    # (effort 訊號) AND (真失敗訊號) + 本 session 未深寫過 → 注入指令，要 Claude 結束前用
    # atom_write 補完整 post-mortem。deep_postmortem_done 一次性防重複＝獨立預算 1；
    # 排在 correctness/sync gate 之後（那些優先）但★不共用 stop_gate_max_blocks——
    # 否則 Sync+TestFail 先吃光預算就餓死 DPM（見 _should_deep_postmortem docstring 實證）。
    claims_done = _done(last_text)
    if (_should_deep_postmortem(state, config, claims_done)
            and not _dpm_marker(session_id).exists()
            and not _chain_hold("DeepPostMortem", "這個 session 有真失敗訊號，結束前要補完整檢討卡")):
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

    if _timed_out("深度檢討"):
        return

    # ── 注入→使用→結果 閉環歸因（correctness gates 通過後、per-turn 一次性）──
    # 走到這裡代表本 Stop 未被 test-fail/scan-report 等 correctness gate 攔下 →
    # 該 turn 的對錯訊號已落定。turn_seq 守門一次性；write_state 立即固化標記
    # （防後續 phase=done / muted 等不寫 state 的終止路徑導致重複計 α/β）。
    _attribute_usefulness(
        state, config, session_id, transcript, last_text, transcript_text
    )
    write_state(session_id, state)

    if _timed_out("閉環歸因"):
        return

    # ── 交付時順手點出最該修的一件（G4／G5）：排在所有閘之後；Stop 的 additionalContext＝對話續跑一回合、不算擋 ──
    # 規則 PICK_ONCE_PER_USER_TURN：同一個使用者回合問過就不再問（pick_due 看 asked_uturn）；這次收尾是不是續跑出來的
    # （stop_hook_active）不當條件——第一次收尾先被別的閘擋下、修完續跑收尾，照樣問這一次
    if v6 and _chain_ro[0]:
        print("[Guardian:ChainBreaker] 連鎖中止中：這次收尾不送「順手看到最該修」", file=sys.stderr)
    _pick = v6 and not _chain_ro[0] and _pick_one_prompt(
        state, session_id, own_mod_files, _pick_boundary, config, cwd, continuation=bool(input_data.get("stop_hook_active")))
    # 規則 SECOND_OPINION_DONE_NOTICE：看守中的第二意見收尾當下已跑完、本回合還沒取回 → 跟最該修同一則提醒取回（只提醒一次）
    _so_note = None
    if v6 and _so_background_on(config) and ((state.get("second_opinion_watch") or {}).get(session_id) or {}).get("on"):
        try:
            from wg_second_opinion import turn_events
            _so_note = _so_done_notice(state, session_id, [r["job_id"] for r in turn_events(transcript_text)[1]
                                                           if r.get("status") in ("done", "failed", "blocked")])
        except Exception as e:  # noqa: BLE001
            print(f"[Guardian:SecondOpinion] 第二意見跑完的提醒出錯（這次不送）：{type(e).__name__}: {e}", file=sys.stderr)
        write_state(session_id, state)
    if _pick or _so_note:
        write_state(session_id, state)
        _ctx = "\n".join(with_note(t, entry_note(t, "stop_piggyback", session_id=session_id, state=state, config=config))
                         for t in (_pick, _so_note) if t)
        output_json({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": _ctx}})
        return

    if _timed_out("點出最該修"):
        return

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

    # 規則 SYNC_BLOCK_SKIPS_SYNCED：已 commit 並 push 的檔不再進一般 sync block（查不了 git 的照算）
    own_mod_files = _drop_synced(own_mod_files)

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

    docdrift = (state.get("docdrift_pending") or {}) if DOCDRIFT_AVAILABLE else {}
    sync_block_owed = _sync_block_items(state, len(unique_files), min_files, _since)
    if not sync_block_owed:
        if kq_count == 0 and not docdrift:
            # 只剩「改了 N 個檔」：跟同步提醒、收尾檢核 (g) 是同一件事（規則 SYNC_BLOCK_NOT_REPEATED），只留 stderr 一行
            print(f"[Workflow Guardian] {len(unique_files)} file(s) modified（同步交代見同步提醒／收尾檢核 (g)，不另擋）",
                  file=sys.stderr)
        else:
            # 規則 SYNC_BLOCK_NEW_ITEMS_ONLY：這批待記知識／文件漂移前面的使用者回合擋過了，沒有新的一筆
            print(f"[Workflow Guardian] {kq_count} 筆待記知識、{len(docdrift)} 筆文件漂移前面回合已提醒過，沒有新的，不另擋",
                  file=sys.stderr)
        state["phase"] = "done"
        write_state(session_id, state)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    if _chain_hold("SyncBlock", f"{len(unique_files)} 個改過的檔、{kq_count} 筆待記知識"):
        write_state(session_id, state)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    state["stop_blocked_count"] = stop_count + 1
    # 只留這次還欠的項目（已解決、已清掉的不留著越記越多）；前面回合擋過的保留第一次擋的回合
    _prev, _mark = state.get("sync_block_shown") or {}, _turn_mark(state, _since)
    state["sync_block_shown"] = {k: _prev.get(k, _mark) for k in _sync_block_keys(state, len(unique_files), min_files)}

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
