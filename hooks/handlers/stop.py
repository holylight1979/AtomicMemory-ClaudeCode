"""
handlers/stop.py — Stop hook handler

四個 gate：
1. Test-Fail Gate（測試未綠 + 宣告完成 → 硬阻）
2. Evasion 偵測（軟糾正）
3. Scan-Report Gate（宣告完成但缺掃描報告 → 硬阻）
4. Sync Reminder Gate（modified_files>0 仍未 commit → 軟阻）
+ 一般 sync block 邏輯
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from wg_core import (
    _ensure_state, _now_iso, write_state, output_nothing, output_block,
)
from wg_evasion import (
    claims_completion, detect_evasion,
    get_last_assistant_text, detect_missing_aec_emission,
    get_current_turn_text,
)
from wg_episodic import _find_session_transcript
from wg_handoff import token_warn_payload
from handlers._shared import (
    _maybe_spawn_user_extract_worker,
    DOCDRIFT_AVAILABLE,
)

# Windows: 外呼 git/svn 時若不帶此 flag，無主控台的 hook 父行程會被配一個可見 console 視窗
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _detect_uncommitted_files(
    modified_files: List[Dict[str, Any]],
) -> Optional[List[str]]:
    """偵測 modified_files 裡仍未提交的檔案。

    回傳:
      - List[str]: 未提交檔案路徑（已去重）
      - []: 全已提交
      - None: 偵測失敗（非 git/svn 工作區）— 跳過此閘
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

    uncommitted: List[str] = []
    detected_any_vcs = False

    for path in unique_paths:
        if not os.path.exists(path):
            continue
        parent = str(Path(path).parent)
        committed_via_git = False
        try:
            r = subprocess.run(
                ["git", "status", "--porcelain", "--", path],
                cwd=parent, capture_output=True, text=True, timeout=3,
                creationflags=_NO_WINDOW,
            )
            if r.returncode == 0:
                detected_any_vcs = True
                committed_via_git = True
                if r.stdout.strip():
                    uncommitted.append(path)
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            pass
        if committed_via_git:
            continue
        try:
            r = subprocess.run(
                ["svn", "status", path],
                cwd=parent, capture_output=True, text=True, timeout=3,
                creationflags=_NO_WINDOW,
            )
            stderr_low = (r.stderr or "").lower()
            not_a_wc = (
                "is not a working copy" in stderr_low
                or "w155007" in stderr_low
                or "e155007" in stderr_low
            )
            if r.returncode == 0 and not not_a_wc:
                detected_any_vcs = True
                if r.stdout.strip():
                    uncommitted.append(path)
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            pass

    if not detected_any_vcs:
        return None
    return uncommitted


# ─── 注入→使用→結果 閉環歸因 ───────────────────────────────────


def _detect_turn_outcome(state: Dict[str, Any], last_text: str) -> Optional[bool]:
    """3 值 success 偵測（複用既有訊號）。回 True(+1)/False(0)/None(unknown=no-op)。

      - 0（fail）：failing_tests 非空 / 本 turn evasion_flag / wisdom_retry_count≥2
        （error / 糾正 / retry / evasion 任一）。
      - +1（success）：宣告完成（claims_completion）且無上述 fail 訊號（硬正向）。
      - None（unknown）：既無完成宣告也無 fail 訊號 → 不動 (α,β)，防雜訊污染。
    """
    failing = state.get("failing_tests") or []
    evasion = bool(state.get("evasion_flag"))
    retry = int(state.get("wisdom_retry_count", 0) or 0)
    if failing or evasion or retry >= 2:
        return False
    if last_text and claims_completion(last_text):
        return True
    return None


def _attribute_usefulness(
    state: Dict[str, Any], config: Dict[str, Any], session_id: str,
    transcript, last_text: str,
) -> None:
    """per-turn 注入→使用→結果歸因：對 turn_injected + 本 turn sub-agent 注入中
    「被判 used 且 outcome 決定性」者 → record_usefulness(α/β，走 funnel)。

    once-per-turn：以 turn_seq 守門（blocked turn 多次 Stop 不重複計）。fail-open。
    """
    try:
        uconf = (config or {}).get("usefulness", {}) or {}
        if not uconf.get("enabled", True):
            return
        turn_seq = int(state.get("turn_seq", 0))
        if turn_seq and state.get("usefulness_attributed_seq") == turn_seq:
            return  # 本 turn 已歸因

        from lib.atom_access import record_usefulness
        from wg_atoms import detect_atom_use, resolve_atom_path, make_embed_tiebreak_fn

        rare_min = int(uconf.get("rare_token_min", 2))
        overlap_min = float(uconf.get("lexical_overlap_min", 0.18))
        embed_fn = make_embed_tiebreak_fn(config)

        turn_text = get_current_turn_text(transcript) if transcript else ""
        outcome = _detect_turn_outcome(state, last_text)

        def _read(path_str: str) -> str:
            try:
                return Path(path_str).read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError, ValueError):
                return ""

        def _record(path_str: str, content: str, match_text: str, decided: Optional[bool]) -> Optional[bool]:
            if decided is None or not content or not match_text:
                return None
            det = detect_atom_use(
                content, match_text,
                rare_token_min=rare_min, overlap_min=overlap_min, embed_fn=embed_fn,
            )
            if not det.get("used"):
                return None
            record_usefulness(Path(path_str), used=True, success=decided, source="hook:usefulness")
            return decided

        attributed = []  # (atom, success) for telemetry

        # 1) UPS per-turn 注入（turn_injected）— 比對本 turn assistant 活動文字
        for entry in (state.get("turn_injected") or []):
            name = entry.get("name", "")
            path_str = entry.get("path", "")
            if not name or not path_str:
                continue
            res = _record(path_str, _read(path_str), turn_text, outcome)
            if res is not None:
                attributed.append((name, res))

        # 2) 本 turn sub-agent 注入（state["subagent_injections"]）
        #    use 偵測比對該 agent 的 output_summary（其實際產物）；outcome 疊 agent 狀態。
        for rec in (state.get("subagent_injections") or []):
            if rec.get("attributed"):
                continue
            status = str(rec.get("status", "") or "").lower()
            sub_outcome = outcome
            if any(k in status for k in ("error", "fail", "abort", "cancel")):
                sub_outcome = False  # agent 出錯 → fail（覆寫 turn outcome）
            match_text = (rec.get("output_summary", "") or "") + "\n" + turn_text
            for aname in (rec.get("atoms") or []):
                p = resolve_atom_path(aname)
                if p is None:
                    continue
                res = _record(str(p), _read(str(p)), match_text, sub_outcome)
                if res is not None:
                    attributed.append((aname, res))
            rec["attributed"] = True  # 本 turn 已處理（含 no-op，避免下 turn 重算）

        if turn_seq:
            state["usefulness_attributed_seq"] = turn_seq
        if attributed:
            state.setdefault("usefulness_log", []).append({
                "turn_seq": turn_seq,
                "outcome": ("+1" if outcome is True else "0" if outcome is False else "unknown"),
                "atoms": [{"atom": a, "success": s} for a, s in attributed],
                "at": _now_iso(),
            })
            state["usefulness_log"] = state["usefulness_log"][-50:]
    except Exception as e:
        print(f"usefulness attribution error: {e}", file=sys.stderr)


# ─── Stage 3: Deep Post-Mortem Gate（高 effort 失敗 → Claude 深寫指令）──────────


def _should_deep_postmortem(
    state: Dict[str, Any], config: Dict[str, Any], claims_done: bool,
) -> bool:
    """是否要在本 Stop 注入「深寫 post-mortem」指令。

    觸發＝(effort 訊號任一) AND (真失敗訊號任一)：
      effort：wisdom_retry_count>=2 ∨ fix_escalation_triggered
      real_failure：failing_tests 非空 ∨ evasion_flag ∨ 未宣告完成（not claims_done）
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
    effort = (
        int(state.get("wisdom_retry_count", 0) or 0) >= 2
        or bool(state.get("fix_escalation_triggered"))
    )
    real_failure = (
        bool(state.get("failing_tests"))
        or bool(state.get("evasion_flag"))
        or not claims_done
    )
    return effort and real_failure


_DEEP_POSTMORTEM_INSTRUCTION = (
    "[Guardian:DeepPostMortem] 偵測到高 effort 失敗訊號（失敗中反覆重試 /"
    " fix-escalation）。失敗骨架已由 hook 自動落地，但根因與設計脈絡只有你知道。\n"
    "結束前請用 atom_write 補一條完整 post-mortem（寫入既有 failure atom，或"
    " realm=local、domain 視主題新建），涵蓋：\n"
    "  - 始末：觸發場景 → 錯誤行為 → 最終正確做法\n"
    "  - 根因：為何會犯（非表面症狀）\n"
    "  - 該區設計原理：出錯那塊程式/機制當初為何這樣設計\n"
    "  - 運作邏輯：它實際怎麼跑、哪個環節斷掉\n"
    "  - 防再犯：下次如何提早攔截\n"
    "寫完即可宣告完成；此為一次性提示，本 session 不再出現。"
)


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
    failing = state.get("failing_tests") or []
    last_text = ""
    cwd = state.get("session", {}).get("cwd", "") or input_data.get("cwd", "")
    transcript = _find_session_transcript(session_id, cwd) if cwd else None

    # ── Layer 1: token 預警 proxy（piggyback 既有 block，不獨立打斷）──────
    # 早段算一次預警句（純函式、無副作用）；於下方各 gate 將 output_block(reason)
    # 前用 _piggyback append。token_warn_emitted 旗標只在「實際 append」時才標，
    # 並隨該 gate 的 write_state 固化（一次性、整 session 一次）。詳見
    # plans/wise-wobbling-gem.md Layer 1 與 Q3 門檻取捨。
    _token_warn = token_warn_payload(state, config, transcript)

    def _piggyback(reason: str) -> str:
        if _token_warn:
            state["token_warn_emitted"] = True
            return reason + _token_warn
        return reason

    if failing:
        last_text = get_last_assistant_text(transcript)
        if claims_completion(last_text):
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

    if not state.get("evasion_flag"):
        if not last_text:
            last_text = get_last_assistant_text(transcript)
        recent_prompts = state.get("recent_user_prompts", []) or []
        ev = detect_evasion(last_text, recent_prompts)
        if ev:
            ev["at"] = _now_iso()
            state["evasion_flag"] = ev
            write_state(session_id, state)

    # ── Scan-Report Gate ────────────────────────────────────────
    # 降條件觸發 — 只在動 core 檔或多檔（≥min_files_to_block）且宣告完成時要求收尾檢核；
    # 純單檔/文件小改不觸發（避免過度觸發成儀式性負擔，非防退避）。
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
    turn_seq = int(state.get("turn_seq", 0))
    committed_this_turn = bool(turn_seq) and state.get("last_commit_turn_seq") == turn_seq
    # emit 滿足＝本回合有呼叫 anti_evasion_report。★雙鍵（turn_seq **且** session_id）為硬性：
    # merged/sibling session 共用同一實體 state 檔且共用同一 turn_seq 計數器，唯 session_id 能
    # 區辨——否則隔壁 session 的 emit 會誤放行本 session（重演 own_mod_files 要防的洩漏）。
    # bool(turn_seq) 護欄：防 turn_seq==0 的 fallback state 以 0==0 假滿足。
    aec = state.get("anti_evasion_report") or {}
    emitted_this_turn = (
        bool(turn_seq)
        and aec.get("turn_seq") == turn_seq
        and aec.get("session_id") == session_id
    )
    if own_mod_files and not state.get("scan_report_warned") and not committed_this_turn:
        if not last_text:
            last_text = get_last_assistant_text(transcript)
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
                "請呼叫 MCP tool anti_evasion_report(a, b, c, d) 提交收尾檢核——內容走 HUD、"
                "chat 只留折疊 chip：\n"
                "  (a) 缺失發現與修補清單：`- 檔:行 — 改了什麼`；無則填「無」。**必寫**\n"
                "  (b) AI 逃避通報：本次有/沒有 忽略 / 偷埋的現象；**僅發生時填**，否則「無」\n"
                "  (c) Token 累積警示：見 hook `[Auto-Handoff]` 預警則判斷失真並附接續 prompt；**僅發生時填**，否則「無」\n"
                "  (d) 衍生暫存清單：本次衍生暫存檔/資料夾（預設直接刪）；**必寫**，無則「無」\n"
                "四參都 required、未發生填「無」。不得用 prose「不在範圍 / 留給未來」籠統帶過。"
            )
            write_state(session_id, state)
            output_block(reason)
            return

    # HUD 不可達且本回合 emit 為 notable/real-evasion → 大聲 fallback 回 chat（可觀測性鐵律：
    # push 不到窗不得 fail-silent）。post_tool_use 標旗，此處消費一次（新 emit 再標則再補，
    # 不永久靜音 real-evasion）。Node tool chip 是 emit 當下的主要 UX 面；本 fallback 是
    # Python 端獨立的觀測保證，不倚賴窗是否渲染。emit 閘本身已放行（見上），此處不再擋 emit。
    if state.get("aec_hud_fallback"):
        state["aec_hud_fallback"] = False  # 消費，避免重播
        state["stop_blocked_count"] = stop_count + 1
        sev = aec.get("severity", "notable")
        fb = [
            f"[Guardian:AEC] HUD 不可達，{sev} 收尾檢核 fallback 回 chat（不 fail-silent）："
        ]
        for _k, _label in (("a", "(a) 缺失修補"), ("b", "(b) 逃避通報")):
            _v = (aec.get(_k) or "").strip()
            if _v and _v != "無":
                fb.append(f"  {_label}：{_v}")
        write_state(session_id, state)
        output_block(_piggyback("\n".join(fb)))
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
        if uncommitted:
            state["sync_reminder_count"] = sr_count + 1
            state["stop_blocked_count"] = stop_count + 1
            shown = uncommitted[:8]
            names = "\n".join(f"  - {p}" for p in shown)
            more = (
                f"\n  ...（共 {len(uncommitted)} 檔，僅顯示前 8）"
                if len(uncommitted) > 8 else ""
            )
            reason = _piggyback(
                f"[Guardian:SyncReminder] 偵測到 {len(uncommitted)} 個已修改但"
                "尚未提交的檔案，依 rules/core.md「完成修改後主動提出 "
                ".git→commit+push」應提示同步。\n"
                f"{names}{more}\n"
                "請選一個方向：\n"
                "  (a) 上 GIT — 立刻 commit + push\n"
                "  (b) 我不打算上 — 請說明原因（會跳過本次提醒）\n"
                "  (c) 已在前一輪上過了 — git/svn clean 後本 gate 自動清旗標"
            )
            write_state(session_id, state)
            output_block(reason)
            return

    # ── Deep Post-Mortem Gate（Stage 3）────────────────────────
    # (effort 訊號) AND (真失敗訊號) + 本 session 未深寫過 → 注入指令，要 Claude 結束前用
    # atom_write 補完整 post-mortem。deep_postmortem_done 一次性防重複＝獨立預算 1；
    # 排在 correctness/sync gate 之後（那些優先）但★不共用 stop_gate_max_blocks——
    # 否則 Sync+TestFail 先吃光預算就餓死 DPM（見 _should_deep_postmortem docstring 實證）。
    if not last_text:
        last_text = get_last_assistant_text(transcript)
    claims_done = bool(last_text and claims_completion(last_text))
    if _should_deep_postmortem(state, config, claims_done):
        state["deep_postmortem_done"] = True
        state["stop_blocked_count"] = stop_count + 1
        reason = _piggyback(_DEEP_POSTMORTEM_INSTRUCTION)
        write_state(session_id, state)
        output_block(reason)
        return

    # ── 注入→使用→結果 閉環歸因（correctness gates 通過後、per-turn 一次性）──
    # 走到這裡代表本 Stop 未被 test-fail/scan-report 等 correctness gate 攔下 →
    # 該 turn 的對錯訊號已落定。turn_seq 守門一次性；write_state 立即固化標記
    # （防後續 phase=done / muted 等不寫 state 的終止路徑導致重複計 α/β）。
    if not last_text:
        last_text = get_last_assistant_text(transcript)
    _attribute_usefulness(state, config, session_id, transcript, last_text)
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
