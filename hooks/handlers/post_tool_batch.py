"""
handlers/post_tool_batch.py — PostToolBatch hook handler（選配 #4：壓縮後 atom 內文復原 / 注入端）

PostToolBatch：一批（含並行）工具呼叫全解析後觸發一次，於下個 model request 前（CC 2.1.159+；
payload: tool_calls[]；反編譯實證支援 hookSpecificOutput.additionalContext）。

職責：壓縮後卡片內文的補位——SessionStart(compact) 沒送成時，把 PostCompact 暫存的內文「一次性」送出
（SessionStart 送過就只清旗標）；PreToolUse 沒攔到的提問事後提醒
（wg_ask_gate）併進同一段送出。
收尾類守門的提醒（規則 REMIND_ON_PRIOR_RESULT；判定與送法照 wg_release_rules 檔尾的 RULE_MODE）：這一批改了程式檔，就算出目前欠的
各一行（closing_reminders：等值意圖、搬目錄、改了 MCP 檔、退縮歸屬、收尾檢核、同步、深度檢討、取用稽核）；
收尾那批附知識收割欠項與報告待寫。同一條規則同一個對象同一個 session
只提醒一次（state remind_sent 清單，wg_overview.remind_mark）；Stop 對同一件只留帳、不擋、不續跑（handlers/stop._remind_logged）。
**每批都會跑** → idle 路徑必須極輕（讀 flag → early exit）。設計：plans/deep-wobbling-bentley.md。
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from wg_core import _ensure_state, write_state, output_json, output_nothing, v6_enabled, coding_turn
from wg_lazy_re import lazy_module

_rr = lazy_module("wg_release_rules")   # 提醒一行的寫法（remind_line）；寫碼守門關時這支 handler 用不到，第一次用到才載


def _ask_module() -> Any:
    """提問閘模組（事後提醒與審計）；載不進來 → stderr 一行、回 None（這批的提問提醒停）。"""
    try:
        import wg_ask_gate
        return wg_ask_gate
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:Ask] 提問閘模組載入失敗，事後提醒停用：{type(e).__name__}: {e}", file=sys.stderr)
        return None


CLOSING_TOOL_SUFFIX = "__anti_evasion_report"
HARVEST_SUFFIX = "__knowledge_harvest_report"


def _calls(tool_calls: Any) -> List[Tuple[str, Dict[str, Any]]]:
    out = []
    for c in tool_calls if isinstance(tool_calls, list) else []:
        c = c if isinstance(c, dict) else {}
        inp = c.get("tool_input", c.get("input"))
        out.append((str(c.get("tool_name") or c.get("name") or ""), inp if isinstance(inp, dict) else {}))
    return out


def closing_call(name: str) -> bool:
    """收尾那批的認法（規則 CLOSING_CALL_ALL_THREE）：收尾檢核（anti_evasion_report，harvest_items 欄帶著知識收割），
    或分開交的知識收割回報（knowledge_harvest_report）。"""
    return name.endswith(CLOSING_TOOL_SUFFIX) or name.endswith(HARVEST_SUFFIX)


# ─── 收尾類守門的提醒：掛在改程式檔那則工具結果（規則 REMIND_ON_PRIOR_RESULT） ──────────────────────────

_HIT_ROW_RE = re.compile(r"^\s*✗ \(([^)]+)\) ([A-Z][A-Z0-9_]*)：(.*?)(?:｜證據：|$)")
_MCP_SEGMENT = "/tools/workflow-guardian-mcp/"
FIX_MOVE = "掃一次舊路徑的引用、跑一支搬過去的抽樣，兩張收據都要在"
FIX_EQUIV = "最後一次改程式之後跑 order／side_effect／boundary 三類變異、各印 PRESERVE_CHECK PASS；不適用寫「等值證法｜不適用｜<理由>」"
FIX_HOT = "收尾答一題「這次改動碰到熱路徑或大量配置嗎」：是→量、附 DONE 收據；否→一句為什麼"
FIX_RELOAD = "服務要重載才生效；收尾叫使用者 Reload 前先查它載的是不是已經最新，已最新就不要叫"
FIX_DEFER = "收尾不把帶受詞、可做的事往後推或推給別人；當場做掉，或寫「不做｜<事>：<理由>」（理由只准寫做了會怎樣）"
FIX_CLOSING = "收尾最後呼叫 anti_evasion_report（知識收割放 harvest_items，一次交齊）"
FIX_SYNC = "收尾照口令規則交代：有「上GIT」口令就 commit＋push 一氣，沒口令就列改了哪些檔等口令、不先 commit"
FIX_DPM = "結束前用 atom_write 補一張完整檢討卡（為什麼失敗、怎麼找到根因、下次怎麼避）"
FIX_AUDIT = "收尾一行交代每張注入的指標卡有沒有用到、用在哪"
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
    時點：這批改了程式檔（modified_files 的 last_seq 比上次看到的大，state remind_mark[sid]）→ 等值意圖、改了 MCP 檔、退縮歸屬、收尾檢核、同步、深度檢討、取用稽核；
    搬了含程式檔的目錄（moved_code_dirs 多一筆）→ (v)；
    這批是收尾那批（closing_call）→ 知識收割、收割對帳、報告待寫。
    每條規則每個對象每 session 一次（wg_overview.remind_mark：已送鍵存 state remind_sent 清單，與工具前守門的提醒帳同一份）。判定重用各閘的純函式，不另複製；
    一段判不出只少那一段、浮 stderr。沒有任何時點成立就不做事（idle 極輕）。"""
    own = [m for m in state.get("modified_files") or [] if isinstance(m, dict) and m.get("path")
           and m.get("session_id", sid) == sid]
    marks = state.setdefault("remind_mark", {})
    mark = int(marks.get(sid) or 0)
    top = max([int(m.get("last_seq") or 0) for m in own], default=0)
    changed = False
    if top != mark:
        marks[sid] = top
        changed = True
    calls = _calls(input_data.get("tool_calls"))
    closing = any(closing_call(n) for n, _inp in calls)
    try:
        from wg_code_path import is_code_path
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
    if not (new_code or closing or new_move):
        return [], changed
    from wg_overview import remind_mark   # 提醒帳本只有一份（state remind_sent 清單），與 remind_flush 同一支記法
    lines: List[str] = []
    turn_seq = int(state.get("turn_seq", 0) or 0)
    cwd = str(input_data.get("cwd") or (state.get("session") or {}).get("cwd") or "")

    def say(rule: str, what: str, fix: str, obj: Any = "") -> None:
        if remind_mark(state, rule, obj):
            lines.append(_rr.remind_line(rule, what, fix))

    def part(name: str, fn) -> None:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            print(f"[Guardian:提醒] {name}判不出（這批少這一段）：{type(e).__name__}: {e}", file=sys.stderr)

    if new_code:
        part("等值意圖", lambda: _equivalence_reminders(state, config, cwd, say))
        if any(_MCP_SEGMENT in str(m["path"]).replace("\\", "/").lower() for m in new_code):
            say("RELOAD_ADVICE_ALREADY_LOADED", "改了 tools/workflow-guardian-mcp/ 的檔", FIX_RELOAD)
        if (config.get("deferral_gate") or {}).get("enabled", True):
            say("DEFERRAL_OF_DOABLE_WORK", "本回合改了程式", FIX_DEFER)
        part("收尾檢核", lambda: _closing_check_reminder(own, config, say))
        if (config.get("sync_reminder") or {}).get("enabled", True):
            say("SYNC_REMINDER_UNSYNCED", f"本 session 改了 {len({str(m['path']) for m in own})} 個檔", FIX_SYNC)
        part("深度檢討與取用稽核", lambda: _postmortem_audit_reminders(state, sid, config, say))
    if new_move:
        part("搬目錄", lambda: _move_reminder(state, sid, config, say))
    if closing:
        part("知識收割", lambda: _closing_batch_reminders(state, sid, own, config, turn_seq, say))
    return lines, changed or bool(lines)




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


def _closing_batch_reminders(state, sid, own, config, turn_seq, say) -> None:
    """收尾那批：知識收割欠不欠、收割對帳待補、收尾檢核把記憶寫入推到之後。"""
    from wg_harvest import harvest_gate_reason, pending_gate_reason
    from wg_release_rules import in_turn, user_turn
    uturn = user_turn(state, turn_seq)
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


def _stub_has_compact_summary(stub_path: str) -> bool:
    """交接單裡已有 PostCompact 寫的壓縮摘要段（記號同 post_compact._SUMMARY_BEGIN）；讀不到當沒有、stderr 一行。"""
    if not stub_path:
        return False
    from handlers.post_compact import _SUMMARY_BEGIN
    try:
        return _SUMMARY_BEGIN in Path(stub_path).read_text(encoding="utf-8")
    except OSError as e:
        print(f"[auto-handoff] 讀不到交接單，補全提示照完整版送：{e}", file=sys.stderr)
        return False


def handle_post_tool_batch(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    v6 = v6_enabled(config)     # 關＝只做 9e476fd0 就有的壓縮後 atom 復原與 handoff 提示
    # 子代理的工具批次（hook 輸入帶 agent_id）：提問的事後提醒、收尾一輪與收尾類提醒都是主 session 的
    sub = bool(input_data.get("agent_id"))
    coding = bool(state) and v6 and not sub and coding_turn(state, config)    # 規則 CODING_TURN_ONLY
    ask = _ask_module() if coding else None
    ask_due = bool(ask) and ask.has_ask_calls(input_data.get("tool_calls"))
    remind_lines, remind_changed = ([], False)
    if state and v6 and not sub:
        try:
            remind_lines, remind_changed = closing_reminders(state, session_id, input_data, config)
        except Exception as e:  # noqa: BLE001
            print(f"[Guardian:提醒] 收尾類提醒算不出（這批不送）：{type(e).__name__}: {e}", file=sys.stderr)
    # idle 極輕路徑：pending 皆無、這批也沒有提問立即退出（每批觸發，杜絕常態開銷）
    if not state or not (
        state.get("pending_reinjection") or state.get("pending_handoff_emit")
        or ask_due or remind_lines or remind_changed
    ):
        output_nothing()
        return

    parts: list = []
    try:
        ah = config.get("auto_handoff", {}) or {}

        # (1) 壓縮後卡片內文補位（一次性）：主路是 SessionStart(compact) 直接送；它送過（compact_reinjected_at，
        #     規則 COMPACT_REINJECT_AT_SESSION_START）就只清旗標不重送，沒送成才由這裡送 PostCompact 暫存的內文
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
            if blob and not state.get("compact_reinjected_at"):
                parts.append(blob)

        # (2) Auto-Handoff 補全提示（Layer 3，與 (1) 合流同一 additionalContext）
        if state.get("pending_handoff_emit"):
            if ah.get("enabled", True) and ah.get("postbatch_emit", True):
                stub_path = state.get("handoff_stub_path", "") or "(staging)"
                if _stub_has_compact_summary(state.get("handoff_stub_path", "")):   # PostCompact 已把壓縮摘要填進去（COMPACT_SUMMARY_TO_HANDOFF）
                    parts.append(
                        f"[Auto-Handoff] 剛發生壓縮。handoff stub `{stub_path}` 的壓縮摘要已填入，"
                        f"只需確認下一步並補 `TODO(模型補全)`，確保接手的 session 用 `/continue` 無損接續。"
                    )
                else:
                    parts.append(
                        f"[Auto-Handoff] 剛發生壓縮。已自動備妥 handoff stub 於 `{stub_path}`"
                        f"（客觀區塊已填）。請**補全其中 `TODO(模型補全)` 三區塊**"
                        f"（why / 做法 / 決策依據）使其達六區塊自足，"
                        f"確保接手的 session 用 `/continue` 無損接續。"
                    )
            state["pending_handoff_emit"] = False  # 一次性，即使 config 關亦清旗標

        # (3) 提問的事後提醒與審計（PreToolUse 沒處理到的提問）：判不了只寫 stderr，不擋其他段
        if ask_due:
            try:
                parts.extend(ask.batch_lines(session_id, state, input_data.get("tool_calls")))
            except Exception as e:  # noqa: BLE001
                print(f"[Guardian:Ask] post_tool_batch 提問提醒失敗（不擋）：{type(e).__name__}: {e}", file=sys.stderr)

        parts.extend(remind_lines)    # (4) 收尾類守門的提醒（REMIND_ON_PRIOR_RESULT）：每規則每對象每 session 一行
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
