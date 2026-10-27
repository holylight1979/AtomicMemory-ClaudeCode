"""
handlers/post_tool_batch.py — PostToolBatch hook handler（選配 #4：壓縮後 atom 內文復原 / 注入端）

PostToolBatch：一批（含並行）工具呼叫全解析後觸發一次，於下個 model request 前（CC 2.1.159+；
payload: tool_calls[]；反編譯實證支援 hookSpecificOutput.additionalContext）。

職責：把 PostCompact stash 的 atom 復原內文、需求目標樹、部位綜觀「一次性」注入，閉合 mid-turn auto-compact 缺口
（壓縮後不一定有 UserPromptSubmit 可重 trigger，但隨後的工具批次會觸發本 hook）；另把需求目標流程的批次提醒
（讀入範圍變大、同檔改多次、PreToolUse 沒攔到的提問）合併成同一段送出；收尾只跑一輪（wg_closing_round）：改完程式就起跑拐彎判斷量測、
交收尾檢核那批附上收尾要問的（拐彎判斷結果、最該修）、第二意見跑完接上。
收尾類守門的提醒（規則 REMIND_ON_PRIOR_RESULT；判定與送法照 wg_release_rules 檔尾的 RULE_MODE）：這一批改了程式檔，就算出目前欠的
各一行（closing_reminders：欠案例、等值意圖、搬目錄、改了 MCP 檔、退縮歸屬、收尾檢核、同步、第二意見、深度檢討、取用稽核；
目標樹只立一次（規則 GOAL_TREE_SET_ONCE）：驗證範圍 SCOPE_*、目標對照 (f2)(f3)(f4) 不再提醒——提醒了 AI 就多叫一次 need_goal
reconcile／verify_scope，各一個模型回合；Stop 照判、只留帳）；建了工作樹那則 Bash 附自清、背景量完附拐彎判斷欠項、收尾那批附知識收割欠項與報告待寫。同一條規則同一個對象同一個 session
只提醒一次（state remind_sent[sid]）；Stop 對同一件只留帳、不擋、不續跑（handlers/stop._remind_logged）。
**每批都會跑** → idle 路徑必須極輕（讀 flag → early exit）。設計：plans/deep-wobbling-bentley.md。
"""

import re
import sys
from typing import Any, Dict, List, Tuple

from wg_core import _ensure_state, write_state, output_json, output_nothing, v6_enabled, coding_turn
from wg_release_rules import remind_due, remind_key, remind_line


def _points_module() -> Any:
    """需求目標的批次模組；載不進來 → stderr 一行、回 None（這批的需求目標提醒全停）。"""
    try:
        import wg_need_goal_points
        return wg_need_goal_points
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 需求目標模組載入失敗，批次提醒停用：{type(e).__name__}: {e}", file=sys.stderr)
        return None


def _closing_round(state: Dict[str, Any], session_id: str, input_data: Dict[str, Any], config: Dict[str, Any]) -> tuple:
    """收尾只跑一輪（wg_closing_round）：改完程式就起跑拐彎判斷量測、交收尾檢核那批附上收尾要問的、第二意見跑完接上。
    回 (段落, state 有沒有改)；載入失敗 → stderr 一行、這批不做（收尾照舊在 Stop 送）。"""
    try:
        import wg_closing_round
        return wg_closing_round.on_batch(state, session_id, input_data, config)
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:ClosingRound] 收尾一輪的批次處理失敗（收尾照舊送）：{type(e).__name__}: {e}", file=sys.stderr)
        return [], False


# ─── 收尾類守門的提醒：掛在改程式檔那則工具結果（規則 REMIND_ON_PRIOR_RESULT） ──────────────────────────

_HIT_ROW_RE = re.compile(r"^\s*✗ \(([^)]+)\) ([A-Z][A-Z0-9_]*)：(.*?)(?:｜證據：|$)")
_MCP_SEGMENT = "/tools/workflow-guardian-mcp/"
FIX_CASE = "補一支會紅的案例（檔名照它取或內容提到它）"
FIX_MOVE = "掃一次舊路徑的引用、跑一支搬過去的抽樣，兩張收據都要在"
FIX_EQUIV = "最後一次改程式之後跑 order／side_effect／boundary 三類變異、各印 PRESERVE_CHECK PASS；不適用寫「等值證法｜不適用｜<理由>」"
FIX_HOT = "收尾答一題「這次改動碰到熱路徑或大量配置嗎」：是→量、附 DONE 收據；否→一句為什麼"
FIX_RELOAD = "服務要重載才生效；收尾叫使用者 Reload 前先查它載的是不是已經最新，已最新就不要叫"
FIX_DEFER = "收尾不把帶受詞、可做的事往後推或推給別人；當場做掉，或寫「不做｜<事>：<理由>」（理由只准寫做了會怎樣）"
FIX_CLOSING = "收尾最後呼叫 anti_evasion_report（知識收割放 harvest_items，一次交齊）"
FIX_SYNC = "收尾照口令規則交代：有「上GIT」口令就 commit＋push 一氣，沒口令就列改了哪些檔等口令、不先 commit"
FIX_SO = "second_opinion_start→second_opinion_result，收尾寫分歧裁決四行；或寫「不需第二意見｜<理由>」"
FIX_DPM = "結束前用 atom_write 補一張完整檢討卡（為什麼失敗、怎麼找到根因、下次怎麼避）"
FIX_AUDIT = "收尾一行交代每張注入的指標卡有沒有用到、用在哪"
FIX_CLEANUP = "用完的刪掉（git worktree remove／branch -d／刪暫存 repo）；要留的在收尾檢核 (i) 寫理由"
FIX_TJ = "收尾每條寫一行「拐彎判斷｜<名稱>｜<不會／會：…>｜<理由>｜<怎麼改直／合理>」"
FIX_HARVEST = "值得留的先 atom_write，再交收割清單（anti_evasion_report 的 harvest_items 一起交，或 knowledge_harvest_report）"
FIX_HARVEST_ITEM = "收割清單裡的每一項要對得上寫卡收據：真寫完再重報"
FIX_AEC_PENDING = "現在就 atom_write 寫完，再重交 anti_evasion_report 把該項改成「→ 已寫入 atom <名>」或「→ 不寫（理由）」"


def _hit_rows(text: str) -> List[Tuple[str, str, str]]:
    """擋訊息裡每一條 `✗ (<字母>) <規則名>：<現象>` → (字母, 規則名, 現象)。"""
    rows = []
    for ln in str(text or "").splitlines():
        m = _HIT_ROW_RE.match(ln)
        if m:
            rows.append((m.group(1), m.group(2), m.group(3).strip()))
    return rows


def closing_reminders(state: Dict[str, Any], sid: str, input_data: Dict[str, Any], config: Dict[str, Any]) -> Tuple[List[str], bool]:
    """這一批之後欠的收尾類守門，各一行（remind_line）→ (要附的行, state 有沒有改)。
    時點：這批改了程式檔（modified_files 的 last_seq 比上次看到的大，state remind_mark[sid]）→ 欠案例 (d)、搬目錄 (v)、等值意圖、改了 MCP 檔、退縮歸屬、收尾檢核、同步、第二意見（事實成立）、深度檢討、取用稽核；
    這批有 git 建東西的 Bash → 收尾自清；搬了含程式檔的目錄（moved_code_dirs 多一筆）→ (v)；背景量完有欠項 → 拐彎判斷；
    這批是收尾那批（closing_call）→ 知識收割、收割對帳、報告待寫。
    每條規則每個對象每 session 一次（remind_due／remind_key，已送鍵存 state remind_sent[sid]）。判定重用各閘的純函式，不另複製；
    一段判不出只少那一段、浮 stderr。沒有任何時點成立就不做事（idle 極輕）。"""
    import wg_closing_round as cr
    own = [m for m in state.get("modified_files") or [] if isinstance(m, dict) and m.get("path")
           and m.get("session_id", sid) == sid]
    marks = state.setdefault("remind_mark", {})
    mark = int(marks.get(sid) or 0)
    top = max([int(m.get("last_seq") or 0) for m in own], default=0)
    changed = False
    if top != mark:
        marks[sid] = top
        changed = True
    calls = cr._calls(input_data.get("tool_calls"))
    closing = any(cr.closing_call(n, inp) for n, inp in calls)
    git_cmds = [str(inp.get("command") or "") for n, inp in calls
                if n in ("Bash", "PowerShell") and "git" in str(inp.get("command") or "")]
    rp = ((state.get("reading_path") or {}).get(sid)) or {}
    tj_owed = rp.get("owed") or {}
    tj_due = bool(tj_owed.get("items")) and not tj_owed.get("stale") and not rp.get("job")   # 還有一批在量：等它量完再提
    try:
        from wg_need_goal import is_code_path
        new_code = [m for m in own if int(m.get("last_seq") or 0) > mark and is_code_path(str(m["path"]), config)]
    except Exception as e:  # noqa: BLE001
        new_code = []
        print(f"[Guardian:提醒] 判不出這批改了哪些程式檔（這批不提醒）：{type(e).__name__}: {e}", file=sys.stderr)
    moved = [m for m in state.get("moved_code_dirs") or [] if isinstance(m, dict) and m.get("session_id") == sid]
    seen_moves = state.setdefault("remind_moves_n", {})
    new_move = len(moved) > int(seen_moves.get(sid) or 0)
    if new_move:
        seen_moves[sid] = len(moved)
        changed = True
    if not (new_code or closing or git_cmds or tj_due or new_move):
        return [], changed
    sent = state.setdefault("remind_sent", {}).setdefault(sid, [])
    lines: List[str] = []
    turn_seq = int(state.get("turn_seq", 0) or 0)
    cwd = str(input_data.get("cwd") or (state.get("session") or {}).get("cwd") or "")

    def say(rule: str, what: str, fix: str, obj: Any = "") -> None:
        if remind_due(sent, rule, obj):
            sent.append(remind_key(rule, obj))
            lines.append(remind_line(rule, what, fix))

    def part(name: str, fn) -> None:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            print(f"[Guardian:提醒] {name}判不出（這批少這一段）：{type(e).__name__}: {e}", file=sys.stderr)

    if new_code:
        part("欠案例", lambda: _code_check_reminders(state, sid, own, config, say))
        part("等值意圖", lambda: _equivalence_reminders(state, config, cwd, say))
        if any(_MCP_SEGMENT in str(m["path"]).replace("\\", "/").lower() for m in new_code):
            say("RELOAD_ADVICE_ALREADY_LOADED", "改了 tools/workflow-guardian-mcp/ 的檔", FIX_RELOAD)
        if (config.get("deferral_gate") or {}).get("enabled", True):
            say("DEFERRAL_OF_DOABLE_WORK", "本回合改了程式", FIX_DEFER)
        part("收尾檢核", lambda: _closing_check_reminder(own, config, say))
        if (config.get("sync_reminder") or {}).get("enabled", True):
            say("SYNC_REMINDER_UNSYNCED", f"本 session 改了 {len({str(m['path']) for m in own})} 個檔", FIX_SYNC)
        part("第二意見", lambda: _second_opinion_reminder(state, sid, own, input_data, config, say))
        part("深度檢討與取用稽核", lambda: _postmortem_audit_reminders(state, sid, config, say))
    if new_move:
        part("搬目錄", lambda: _move_reminder(state, sid, config, say))
    if git_cmds:
        part("收尾自清", lambda: _cleanup_reminder(sid, git_cmds, cwd, say))
    if tj_due:
        names = "、".join(str(it.get("name")) for it in tj_owed["items"][:4])
        say("TURN_JUDGMENT_REQUIRED", f"背景量完，{len(tj_owed['items'])} 條到門檻：{names}", FIX_TJ, tj_owed.get("at") or tj_owed.get("turn"))
    if closing:
        part("知識收割", lambda: _closing_batch_reminders(state, sid, own, config, turn_seq, say))
    return lines, changed or bool(lines)


def _code_check_reminders(state, sid, own, config, say) -> None:
    """(d) 每個改過的程式檔一次（wg_verify_ledger.case_debt，同 Stop 的判法）。驗證範圍 SCOPE_* 不提醒（GOAL_TREE_SET_ONCE：
    提醒了 AI 就多叫一次 need_goal verify_scope），Stop 照判、只留帳；案例覆蓋仍認 verify_scope 收過的宣告（有才用）。"""
    import wg_verify_ledger as vl
    import wg_verify_scope as vs
    from pathlib import Path
    rg, sg = vl.reconcile_cfg(config), vs.scope_cfg(config)
    if not rg.get("enabled", True):
        return
    receipts = vl.receipts_of(state, sid)
    try:
        from wg_overview import _lookup
    except ImportError:
        _lookup = None
    why: Dict[str, Any] = {}
    case_check = vs.case_check(state, sid, own, receipts, rg, _lookup) if (_lookup and sg.get("enabled", True)) else None
    for p in vl.case_debt(own, int(state.get("turn_seq", 0) or 0), rg, vl.file_root_of, evidence=why,
                          case_check=case_check, case_for=vl.declared_cases(state, sid, rg)):
        v = why.get(p)
        say(v.rule if v else "CASE_COVERS_CHANGE", f"改了 {Path(p).name}，{v.why if v else '還沒有案例覆蓋它'}", FIX_CASE, p)


def _move_reminder(state, sid, config, say) -> None:
    """(v) 搬了含程式檔的目錄那則 Bash：照 Stop 同一套（stop._move_inputs 配對事實、reconcile_gate_parts 的 (v) 條目）判欠不欠。"""
    import wg_verify_ledger as vl
    from handlers.stop import _move_inputs
    rg = vl.reconcile_cfg(config)
    if not rg.get("enabled", True):
        return
    moves, move_receipts = _move_inputs(state, sid)
    if not moves:
        return
    rem: List[str] = []
    vl.reconcile_gate_parts("", vl.receipts_of(state, sid), int(state.get("turn_seq", 0) or 0), [], [], rg, sid=sid, moves=moves,
                            move_receipts=move_receipts, move_scan_hits=state.get("move_scan_hits") or {}, remind=rem)
    for letter, rule, what in (r for h in rem for r in _hit_rows(h)):
        if letter == "v":
            say(rule, what, FIX_MOVE, what[:80])


def _equivalence_reminders(state, config, cwd, say) -> None:
    """意圖 refactor／perf（state turn_intent，只由使用者本人的字判）、等值閘開著 → 第一次改程式檔就提醒等值證法與熱路徑那一問。"""
    from wg_overview import _intent_of
    from handlers.stop import _equivalence_on
    intent = _intent_of(state)
    if intent not in ("refactor", "perf") or not _equivalence_on(config, cwd):
        return
    if intent == "refactor":
        say("REFACTOR_NEEDS_EQUIVALENCE", "意圖 refactor、改了程式", FIX_EQUIV)
    say("PERF_HOT_PATH_NEEDS_MEASURE", f"意圖 {intent}、改了程式", FIX_HOT)


def _closing_check_reminder(own, config, say) -> None:
    from wg_evasion import completion_threshold_met
    if (config.get("aec") or {}).get("scan_report_gate", True) is False:
        return
    if completion_threshold_met("", own, int(config.get("min_files_to_block", 2)), claimed=True):
        say("CLOSING_CHECK_REQUIRED", "本 session 動到 core 檔或多檔（達收尾檢核門檻）", FIX_CLOSING)


def _second_opinion_reminder(state, sid, own, input_data, config, say) -> None:
    """規則 SECOND_OPINION_REQUIRED 的事實（wg_second_opinion.check，同 Stop 一套）成立那則改檔就提醒；改檔指紋沒變不重判（不多跑 git）。"""
    import wg_second_opinion as so
    from wg_release import non_interactive_reason
    cfg = so.auto_cfg(config)
    if not cfg.get("enabled", True) or non_interactive_reason(input_data, str(input_data.get("transcript_path") or "") or None):
        return
    fp = so.fingerprint(so._code_entries(own, config))
    seen = state.setdefault("remind_so_fp", {})
    if not fp or seen.get(sid) == fp:
        return
    seen[sid] = fp
    v, facts = so.check(state, sid, own, "", "", config, cfg, True)
    if v.owed:
        say(v.rule, f"{v.why}（程式檔 {facts.get('code_files')} 個）", FIX_SO, fp)


def _postmortem_audit_reminders(state, sid, config, say) -> None:
    from handlers.stop import _audit_pointer_atom_consumption, _dpm_marker, _should_deep_postmortem
    if _should_deep_postmortem(state, config, True) and not _dpm_marker(sid).exists():
        say("DEEP_POSTMORTEM_ON_FAILURE", "這個 session 有真失敗訊號", FIX_DPM)
    if (config.get("atom_audit") or {}).get("enabled", True):
        aa = _audit_pointer_atom_consumption(state)
        if aa:
            prompted = state.setdefault("atom_audit_prompted", [])
            prompted.extend(n for n in aa[1] if n not in prompted)
            say("ATOM_CONSUMPTION_AUDIT", f"注入的指標卡還沒回報有沒有用到：{'、'.join(aa[1][:3])}", FIX_AUDIT, "|".join(sorted(aa[1])[:5]))


def _cleanup_reminder(sid, git_cmds, cwd, say) -> None:
    """這批的 Bash 有 git 建東西（worktree／branch／init／clone）→ 照收尾自清閘同一套事實（aec_ledger.cleanup_facts）判，欠就提醒。"""
    from handlers import aec_ledger
    from wg_release_rules import leftover_cleanup_verdict
    if not any(aec_ledger.parse_git_artifacts(cmd, cwd) for cmd in git_cmds):
        return
    cv = leftover_cleanup_verdict(True, aec_ledger.cleanup_facts(sid))
    if cv.owed:
        say(cv.rule, f"這個 session 建的還在：{'；'.join(cv.evidence[:3])}", FIX_CLEANUP, "|".join(sorted(cv.evidence)))


def _closing_batch_reminders(state, sid, own, config, turn_seq, say) -> None:
    """收尾那批：知識收割欠不欠（背景收割開著就不提）、收割對帳待補、收尾檢核把記憶寫入推到之後。"""
    from wg_bg_harvest import background_on
    from wg_harvest import harvest_gate_reason, pending_gate_reason
    from wg_release_rules import in_turn, user_turn
    uturn = user_turn(state, turn_seq)
    if not background_on(config):
        hv = harvest_gate_reason(state, sid, "", config, own, turn_seq, gate_turn=uturn, claimed=True)
        if hv:
            say("HARVEST_AT_PHASE_DONE", "階段完工還沒交知識收割清單", FIX_HARVEST, uturn)
    hp = pending_gate_reason(state, sid, turn_seq, "", gate_turn=uturn)
    if hp:
        items = (state.get("knowledge_harvest", {}).get(sid) or {}).get("pending", [])[:5]
        say("HARVEST_ITEM_NEEDS_RECEIPT", f"收割回報有 {len(items)} 項對不上寫卡收據", FIX_HARVEST_ITEM, "|".join(map(str, items)))
    aec = state.get("anti_evasion_report") or {}
    pending = aec.get("d_pending") or []
    if pending and aec.get("session_id") == sid and in_turn(aec.get("turn_seq"), turn_seq, uturn):
        say("CLOSING_CHECK_MEMORY_NOT_DEFERRED", f"收尾檢核把 {len(pending)} 項記憶寫入推到之後", FIX_AEC_PENDING, aec.get("turn_seq"))


def handle_post_tool_batch(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    v6 = v6_enabled(config)     # 關＝只做 9e476fd0 就有的壓縮後 atom 復原與 handoff 提示
    # 子代理的工具批次（hook 輸入帶 agent_id）：目標樹是主 session 的——不送讀入範圍、同檔多次、提問、外部主張的提醒，
    # 壓縮後要重送的樹也留給主 session
    sub = bool(input_data.get("agent_id"))
    ngp = _points_module() if state and v6 and not sub and coding_turn(state, config) else None   # 規則 CODING_TURN_ONLY
    goal_due = bool(ngp) and ngp.batch_due(state, input_data.get("tool_calls"))
    close_parts, close_changed = _closing_round(state, session_id, input_data, config) if state and v6 and not sub else ([], False)
    remind_lines, remind_changed = ([], False)
    if state and v6 and not sub:
        try:
            remind_lines, remind_changed = closing_reminders(state, session_id, input_data, config)
        except Exception as e:  # noqa: BLE001
            print(f"[Guardian:提醒] 收尾類提醒算不出（這批不送）：{type(e).__name__}: {e}", file=sys.stderr)
    # idle 極輕路徑：pending 皆無、需求目標也沒有待送立即退出（每批觸發，杜絕常態開銷；沒有目標檔的 session 只多一次 stat）
    if not state or not (
        state.get("pending_reinjection") or state.get("pending_handoff_emit")
        or (v6 and (state.get("pending_reinjection_overview") or (state.get("pending_reinjection_goal") and not sub)))
        or goal_due or close_parts or close_changed or remind_lines or remind_changed
    ):
        output_nothing()
        return

    parts: list = []
    try:
        ah = config.get("auto_handoff", {}) or {}

        # (1) 壓縮後 atom 內文復原（既有 #4 機制，一次性）
        if state.get("pending_reinjection"):
            blob = state.get("pending_reinjection_blob", "") or ""
            atoms = state.get("pending_reinjection_atoms", []) or []
            state["pending_reinjection"] = False
            state.pop("pending_reinjection_blob", None)
            state.pop("pending_reinjection_atoms", None)
            # 復原名單 merge 回 injected_atoms（若 SessionStart(compact) 曾清空亦復原；
            # 維持 PostToolUse use 偵測 / Phase 2 效用歸因不中斷）
            if atoms:
                merged = list(dict.fromkeys((state.get("injected_atoms", []) or []) + atoms))
                state["injected_atoms"] = merged
            if blob:
                parts.append(blob)

        # (1a) 壓縮後需求目標樹獨立重送（不依附部位綜觀）：排在 atom 內文後、綜觀前（綜觀的「主目標」指向它）；一次性 pop
        goal = state.pop("pending_reinjection_goal", None) if v6 and not sub else None
        if goal:
            parts.append(goal)

        # (1b) 壓縮後 OverviewHub 綜觀重注（A2.2／A2.3）：順序 atom 內文先、綜觀後；一次性 pop
        overview = state.pop("pending_reinjection_overview", None) if v6 else None
        if v6:
            state.pop("pending_reinjection_parts", None)
        if overview:
            parts.append(overview)

        # (2) Auto-Handoff 補全提示（Layer 3，與 (1) 合流同一 additionalContext）
        if state.get("pending_handoff_emit"):
            if ah.get("enabled", True) and ah.get("postbatch_emit", True):
                stub_path = state.get("handoff_stub_path", "") or "(staging)"
                parts.append(
                    f"[Auto-Handoff] 剛發生壓縮。已自動備妥 handoff stub 於 `{stub_path}`"
                    f"（客觀區塊已填）。請**補全其中 `TODO(模型補全)` 三區塊**"
                    f"（why / 做法 / 決策依據）使其達六區塊自足，"
                    f"確保接手的 session 用 `/continue` 無損接續。"
                )
            state["pending_handoff_emit"] = False  # 一次性，即使 config 關亦清旗標

        # (3) 需求目標的批次提醒（4.3 讀入範圍、同檔多次、外部主張；4.4 提問審計與沒攔到的提問）：判不了只寫 stderr，不擋其他段
        if goal_due:
            try:
                import wg_need_goal as _ng
                parts.extend(ngp.batch_lines(session_id, state, input_data.get("tool_calls"),
                                             _ng.cfg_for_cwd(config, _ng.hook_cwd(input_data, state))))
            except Exception as e:  # noqa: BLE001
                print(f"[NeedGoal] post_tool_batch 提醒失敗（不擋）：{type(e).__name__}: {e}", file=sys.stderr)

        parts.extend(close_parts)     # (4) 收尾一輪：收尾前附的拐彎判斷、最該修，第二意見跑完的提醒
        parts.extend(remind_lines)    # (5) 收尾類守門的提醒（REMIND_ON_PRIOR_RESULT）：每規則每對象每 session 一行
        write_state(session_id, state)
    except Exception as e:
        print(f"[#4] post_tool_batch reinject error: {e}", file=sys.stderr)
        output_nothing()
        return

    if not parts:
        output_nothing()
        return

    output_json({
        "hookSpecificOutput": {
            "hookEventName": "PostToolBatch",
            "additionalContext": "\n\n".join(parts),
        }
    })
