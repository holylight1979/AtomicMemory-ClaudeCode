"""
handlers/user_prompt_submit.py — UserPromptSubmit hook handler（orchestrator）

拆為四個子模組，本檔收斂為串聯呼叫：
- ups_gates.run_pre_gates — detect 段（evasion 追蹤 / user decision gate / long_die /
  hot cache / atom-write guard）
- ups_context.build_context — context build 段（session context / wisdom /
  parallel 建議 / AIDocs / JIT）
- ups_search.collect_matched_atoms — search pipeline 段（trigger / BM25 /
  vector / supersedes / ACT-R 排序）
- ups_inject.assemble_injection — injection assemble 段（hot/cold / budget /
  related spread / 效用晉升提示）

本檔保留收尾職責：blind-spot reporter、fix escalation、evasion 舉證、
handoff 提醒、failure-triggered extraction、topic tracking、sync reminders、
turn_injected 歸因記錄、atom-debug summary、budget 截斷輸出。
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from wg_core import (
    _ensure_state, _estimate_tokens, _now_iso, write_state,
    output_json, output_nothing,
    _atom_debug_log, _atom_debug_error, WORKFLOW_DIR, v6_enabled, coding_turn,
    DEFAULTS as CORE_DEFAULTS,  # config 缺鍵時的預設只認 wg_core 那一份
)
from harness_text import IDE_TAG_NAMES, strip_harness_blocks, user_typed_text  # lib/（wg_core 已把它放進 sys.path）
from wg_atoms import (
    classify_intent,
    compute_token_budget,
    _truncate_context_by_activation,
    _update_topic_tracker,
)
from wg_extraction import _maybe_spawn_failure_extraction
from handlers.ups_gates import run_pre_gates
from handlers.ups_context import build_context
from handlers.ups_search import collect_matched_atoms
from handlers.ups_inject import assemble_injection, reconcile_injection_after_trim
import wg_hook_timing as _hook_timing
from wg_hook_timing import degraded as _hook_degraded, lap as _hook_lap


def _ups_output(lines: List[str]) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "\n".join(lines)}},
                      ensure_ascii=False)


def _fallback_output(lines: List[str]) -> str:
    """背景鬧鐘代送（到上限 95% 還沒送出）：當下已備好的注入＋一行說明；state 這次沒寫回、哨兵留著（下一則會告警）。"""
    return _ups_output([*lines, "[Guardian:HookTiming] 這則 UserPromptSubmit 快到上限被取消，先送出已備好的部分，"
                                "記憶檢索與注入可能缺；各段耗時記在 Logs/guard-hook_timing.jsonl。"])


# ─── UPS 被 kill 哨兵：偵測上輪注入被 harness timeout 砍掉 ────────────────────


def _ups_sentinel_path(session_id: str) -> Path:
    return WORKFLOW_DIR / "ups-sentinel" / f"{session_id}.json"


def _ups_sentinel_check_and_arm(
    session_id: str, state: Dict[str, Any], lines: List[str]
) -> None:
    """UPS 開頭 touch 哨兵檔、正常結尾清除（_ups_sentinel_clear）。本輪見殘留哨兵
    ＝上輪 UPS 未跑完（harness timeout 砍掉 / hook 例外中斷）→ 該輪記憶注入缺失
    ——過去完全靜默，本哨兵讓它浮出（可觀測性鐵律）。fail-open。"""
    if not session_id:
        return
    try:
        p = _ups_sentinel_path(session_id)
        if p.exists():
            info: Dict[str, Any] = {}
            try:
                info = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
            lines.append(
                f"[Guardian:UPS-Sentinel] 上輪（turn {info.get('turn_seq', '?')}，"
                f"{info.get('at', '?')}）UserPromptSubmit 未跑完即中斷"
                "（疑 harness timeout / hook 例外）——該輪記憶注入可能缺失。"
            )
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({
                "turn_seq": int(state.get("turn_seq", 0)) + 1,
                "at": _now_iso(),
            }, ensure_ascii=False),
            encoding="utf-8",
        newline="\n")
    except Exception:
        pass


def _ups_sentinel_clear(session_id: str) -> None:
    if not session_id:
        return
    try:
        p = _ups_sentinel_path(session_id)
        if p.exists():
            p.unlink()
    except Exception:
        pass


def evasion_ask(ev: Dict[str, Any]) -> str:
    """上輪退避旗標（Stop detect_evasion 記的 phrase／context_excerpt／hint）→ 舉證要求：明說先處理這件再做新請求，
    判準直接寫出來、不點卡名（點了也送不到）。"""
    return (f"[Guardian:Evasion] 你上輪用了退避語『{ev.get('phrase', '')}』，可能把一件事往後推了：\n"
            f"  context: …{ev.get('context_excerpt', '')[:200]}…\n"
            "先處理這件，再做使用者這回合的新請求（只回新請求、不理這段，不算處理）：\n"
            "  (a) 寫出補它的實際成本（要改的檔、行數）；成本小（幾行、一支測試）就這一回合先做掉\n"
            "  (b) 真的不做、或那句只是在描述沒推事 → 照下面寫一行（使用者換了話題不等於放行）：\n"
            f"  {ev.get('hint') or ''}")


# 關鍵字分類（classify_intent）判成要改程式的意圖：只用來送「先立樹」提示與記憶選片，不當守門開關
_CODE_INTENTS = frozenset({"debug", "feature", "refactor", "perf", "new_project", "build"})


def handle_user_prompt_submit(
    input_data: Dict[str, Any], config: Dict[str, Any]
) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    prompt = input_data.get("prompt", "")
    # 只剔最外層是 IDE 的區塊（其餘內容留給檢索與注入）；巢狀與交錯照樣看所有 harness 標籤判斷，
    # 所以權威判斷再對它取 user_typed_text，和直接對原文取的結果相同
    clean_prompt = strip_harness_blocks(prompt, only=IDE_TAG_NAMES).strip()
    prompt_lower = clean_prompt.lower()
    lines: List[str] = []

    # 被 kill 哨兵：見上輪殘留 → 告警；隨即 arm 本輪（正常結尾 clear）
    _ups_sentinel_check_and_arm(session_id, state, lines)

    # fallback state 重建告警（_ensure_state 標旗，此處消費一次）——
    # 原 state 遭 TTL 清除 / SessionStart 未跑，已重建最小 atom_index。
    if state.pop("_fallback_state_rebuilt", None):
        idx = state.get("atom_index", {})
        lines.append(
            f"[Guardian] state 已重建（原 state 遺失/被 TTL 清除）——最小 atom index "
            f"global={len(idx.get('global', []))} project={len(idx.get('project', []))}，"
            "trigger 注入已恢復；本 session 早前累積脈絡（modified/accessed）不可復原。"
        )

    # config.json 解析失敗告警（load_config 標旗；一 session 一次）
    if config.get("_config_parse_failed") and not state.get("_config_warned"):
        state["_config_warned"] = True
        lines.append(
            "[Guardian:Config⚠] workflow/config.json 解析失敗，本 session 以內建 "
            "DEFAULTS 運行——請修復 JSON（詳 Logs/atom-debug）。"
        )

    # 分段計時（wg_hook_timing）：累計過上限 80% → 降級，脈絡、導讀卡、檢索與注入組裝這次不跑；
    # 前置閘、記原話（目標樹）、收尾記帳與寫 state 照做。到 95% 還沒送出 → 背景鬧鐘代送已備好的 lines。
    _hook_timing.set_fallback(lambda: _fallback_output(lines))

    v6 = v6_enabled(config)     # 關＝只送 9e476fd0 就有的注入與提示

    # ─── Detect 段：前置閘（evasion 追蹤 / user decision gate / long_die / atom-write guard）
    run_pre_gates(
        session_id, state, config, clean_prompt, prompt_lower, lines
    )
    _hook_lap("前置閘")

    # ─── Context build 段：session context / wisdom / parallel / AIDocs / JIT
    # budget_total 是整包 additionalContext 的上限；build_context 回傳的是扣掉它自己塞進
    # lines 的保留量後的餘額（只供它內部的 JIT 判斷）。最終裁切量的是整包 lines，所以要用
    # 總額——以前拿餘額當上限，episodic/JIT 等於被扣兩次。
    budget_total = compute_token_budget(prompt)
    if not _hook_degraded():
        build_context(
            session_id, state, config, prompt, clean_prompt, prompt_lower,
            budget_total, lines,
        )
        _hook_lap("脈絡")

    # 意圖前移（A0.1）：注入前就知道這回合要做什麼，OverviewHub 依 goal_weights 選片；十鍵見 wg_atoms.INTENT_PATTERNS。
    # 意圖是「使用者要做什麼」的權威判斷，只吃使用者本人打的字（user_typed_text：剔掉同伴訊息、背景通知等 harness 區塊）；
    # 整則沒有使用者的字 → 沿用上一則判的意圖（同伴信、通知正文裡的「重構」不改意圖；G7 等值閘據此擋）
    typed = user_typed_text(prompt)
    turn_intent = classify_intent(typed) if typed else (state.get("turn_intent") or "general")
    state["turn_intent"] = turn_intent
    coding = v6 and coding_turn(state, config)     # 規則 CODING_TURN_ONLY：不是寫碼回合 v6 守門不送（記憶注入、導讀卡照舊）
    if not coding:
        _hook_timing.quiet()                       # 不寫計時帳；新的使用者回合起點：拿掉寫碼回合標記
        _hook_timing.mark_coding(session_id, False)

    # 需求目標（4.1）：使用者本人打的字記進目前的目標樹、同伴訊息記成轉述；沒樹時提醒先寫目標、有樹時送回樹根一行。
    # 排在導讀卡之前（目標那一行先到眼前）；本則的回合號＝turn_seq＋1（這則收尾才加一）
    try:
        _ng_txt = None
        if v6:
            from wg_need_goal import on_prompt as _ng_on_prompt
            _ng_txt = _ng_on_prompt(session_id, clean_prompt, int(state.get("turn_seq", 0)) + 1, config,
                                    cwd=input_data.get("cwd", "") or state.get("session", {}).get("cwd", "") or "")
        if _ng_txt and coding:                   # 原話照記；提示只在寫碼回合送
            lines.append(_ng_txt)
        elif v6 and turn_intent in _CODE_INTENTS:   # 規則 CODING_TURN_ONLY 第三層：關鍵字判寫碼只送一行「先立樹」，不啟動守門
            from wg_need_goal import CODE_TREE_HINT
            lines.append(CODE_TREE_HINT)
    except Exception as e:
        _atom_debug_error("ups:need_goal", e)
        print(f"[NeedGoal] UserPromptSubmit 記原話失敗：{type(e).__name__}: {e}", file=sys.stderr)
    _hook_lap("目標樹")

    # OverviewHub：提示詞提到某部位的檔且本 session 未注入過該部位 → 依意圖選片注入導讀卡（fail-open）
    if not _hook_degraded():
        try:
            from wg_overview import on_prompt as _hub_on_prompt
            _hub_txt = _hub_on_prompt(
                state, session_id, clean_prompt, input_data.get("transcript_path", "") or "", config,
                **({"intent": turn_intent} if v6 else {}),   # 依意圖選片是 v6 加的；關閉時照舊整張注入
            )
            if _hub_txt:
                lines.append(_hub_txt)
        except Exception as e:
            _atom_debug_error("ups:overview_hub", e)
        _hook_lap("導讀卡")

    # ─── Search pipeline 段：候選收集（trigger/BM25/vector）+ supersedes + ACT-R 排序
    # ─── Injection assemble 段：hot/cold + budget + related spread + 效用晉升提示
    # 已降級：這則不檢索、不注入（intent 同 collect_matched_atoms 的取法：本則已判的 turn_intent）
    already_injected = state.get("injected_atoms", [])
    matched_with_dir: list = []
    newly_injected: List[str] = []
    atom_source_dirs: Dict[str, Path] = {}
    intent = turn_intent
    if not _hook_degraded():
        (
            matched_with_dir, atom_source, all_atoms,
            sem_atoms, section_hints, alias_injected_projects, intent,
            caches,
        ) = collect_matched_atoms(
            session_id, state, config, prompt, prompt_lower, lines
        )
        if not _hook_lap("檢索"):
            newly_injected, atom_source_dirs = assemble_injection(
                session_id, state, config,
                matched_with_dir, all_atoms, already_injected,
                atom_source, section_hints, lines,
                caches=caches, prompt=clean_prompt,
            )
            _hook_lap("注入組裝")

    # Fix Escalation Protocol
    # 規則 RETRY_COUNTS_RERUN_CYCLES：輪數到門檻才提示，訊息帶每輪的重跑指令與紅案
    from wg_release_rules import fix_escalation_text
    fix_esc = fix_escalation_text(state)
    if fix_esc and not state.get("fix_escalation_warned", False):
        state["fix_escalation_warned"] = True
        state["fix_escalation_triggered"] = True
        lines.append(fix_esc)

    # Evasion 上輪命中 → 注入舉證要求，放在這則注入最前面（排在其他注入後面時模型只做新請求、不理舉證）
    ev = state.get("evasion_flag")
    if ev:
        lines.insert(0, evasion_ask(ev))
        state["evasion_flag"] = None

    # 文字評分（G15）：上一則回覆背景評完了 → 只留帳（評分不送到眼前、不叫 AI 照抄；wg_text_score.tail_note 一律回空字串）
    try:
        _ts_txt = None
        if v6:
            from wg_text_score import tail_note as _ts_tail_note
            _ts_txt = _ts_tail_note(state, session_id, config,
                                    cwd=input_data.get("cwd", "") or state.get("session", {}).get("cwd", "") or "")
        if _ts_txt:
            lines.insert(0, _ts_txt)
    except Exception as e:
        _atom_debug_error("ups:text_score", e)
        print(f"[Guardian:TextScore] UserPromptSubmit 送上則評分失敗：{type(e).__name__}: {e}", file=sys.stderr)

    # Handoff Protocol
    if intent == "handoff":
        lines.append(
            "[Guardian:Handoff] 偵測到 handoff 意圖。"
            "下 session 的 Claude 不會看到本次對話脈絡。"
            "請執行 /handoff 走 6 區塊強制模板，不要徒手寫 prompt。"
        )

    # Failure-triggered extraction
    _maybe_spawn_failure_extraction(
        session_id, state, config, clean_prompt, lines
    )

    # 使用者糾正訊號：跨 turn 計數（wg_friction），達門檻由 Stop 的 Deep Post-Mortem 消費；
    # 命中（只算使用者本人打的字）且有需求目標樹 → 提醒回頭看樹（4.3，不擋）
    correction_hits: List[str] = []
    try:
        from wg_friction import correction_question, record_correction
        correction_hits = record_correction(state, session_id, clean_prompt, config)
        if correction_hits and v6:   # 詞表只是提示：問 AI「是不是糾正」，問的那一刻接判準卡、記 guard-entry（規則 CORRECTION_WORDS_ARE_HINTS）
            from handlers._shared import entry_note, with_note
            _cq = correction_question(correction_hits)
            lines.append(with_note(_cq, entry_note(_cq, "user_prompt", session_id=session_id, state=state, config=config)))
    except Exception as e:
        _atom_debug_error("ups:friction", e)
        print(f"[Guardian:Correction] 糾正詞待判或問句失敗（這次沒問）：{type(e).__name__}: {e}", file=sys.stderr)
    # 使用者糾正：提醒回頭看目標樹（4.3）
    if coding and correction_hits:
        try:
            import wg_need_goal as _ng
            from wg_need_goal_points import on_correction
            if _ng.cfg_for_cwd(config, _ng.hook_cwd(input_data, state)).get("enabled", True):
                _ng_line = on_correction(session_id, correction_hits, int(state.get("turn_seq", 0) or 0) + 1)
                if _ng_line:
                    lines.append(_ng_line)
        except Exception as e:
            print(f"[NeedGoal] 糾正或外部主張提醒失敗（不送）：{type(e).__name__}: {e}", file=sys.stderr)
            _atom_debug_error("ups:need_goal_correction", e)

    # Topic tracking
    _update_topic_tracker(state, prompt, intent, newly_injected)

    # Sync reminders
    mod_count = len(state.get("modified_files", []))
    kq_count = len(state.get("knowledge_queue", []))
    sync_kw = config.get("sync_keywords", CORE_DEFAULTS["sync_keywords"])
    prompt_has_sync = any(kw in prompt for kw in sync_kw)

    # 同步數字只留 stderr 一行、不進 chat：記憶卡由 vcs-sync 背景自動上，程式檔的版控交代在收尾檢核 (g)；
    # statusline（tools/statusline.py）常駐顯示改檔／佇列數（零 token）。
    if prompt_has_sync and (mod_count > 0 or kq_count > 0):
        print(f"[Guardian] Sync context: {mod_count} files modified, {kq_count} knowledge items pending.", file=sys.stderr)

    # ─── 最終裁切 → 以「實際送出」結算注入記帳 ───
    # 所有 lines 生產者都在上面；這裡裁切一次，之後不再動 lines。
    _hook_lap("收尾提示")
    if lines:
        lines = _truncate_context_by_activation(lines, budget_total, atom_source_dirs, config)
    delivered = reconcile_injection_after_trim(session_id, state, config, lines)
    if _hook_degraded():
        lines.append(_hook_timing.degrade_note())             # 裁切之後才加：這一行不能被預算裁掉

    # per-turn 注入記錄（每 turn 覆寫）：只存「本 turn 實際送出」的 atom + 檔路徑，
    # 供 Stop 做注入→使用→結果 (α,β) 歸因。被最終裁切丟掉的不算注入。
    # 無注入 turn → 覆寫為 []（清上一 turn）。
    state["turn_injected"] = [
        {"name": nm, "path": str(atom_source_dirs[nm] / f"{nm}.md")}
        for nm in delivered if nm in atom_source_dirs
    ]
    # 單調遞增 turn 序號 → Stop 端 per-turn 一次性歸因守門（防 blocked turn 重複計）。
    state["turn_seq"] = int(state.get("turn_seq", 0)) + 1
    # turn 起點的重試計數快照：Stop 的 outcome 只看本 turn 增量（累計值留給 FixEscalation）。
    state["wisdom_retry_turn_base"] = int(state.get("wisdom_retry_count", 0) or 0)

    write_state(session_id, state)

    # atom-debug summary
    if (config or {}).get("atom_debug", False):
        prompt_preview = re.sub(r"<[^>]+>", "", prompt[:300]).strip()[:120] if prompt else ""
        total_tok = 0
        summary_parts = []
        _ATOM_BLOCK_RE = re.compile(r"^\[Atom:(\S+)\](?:\s*\(related\))?\n")
        for line_item in lines:
            tok = _estimate_tokens(line_item)
            total_tok += tok
            am = _ATOM_BLOCK_RE.match(line_item)
            if am:
                aname = am.group(1)
                is_related = "(related) " if "(related)" in line_item[:60] else ""
                src = f"memory/{aname}.md"
                for (n, rp, _), bd in matched_with_dir:
                    if n == aname and rp:
                        src = rp
                        break
                summary_parts.append(f"  [注入了 {src}] {is_related}(~{tok} tok)")
            else:
                first = line_item.split("\n", 1)[0][:120]
                if line_item.count("\n") > 1:
                    n_lines = line_item.count("\n") + 1
                    summary_parts.append(f"  {first} ...({n_lines}行, ~{tok} tok)")
                else:
                    summary_parts.append(f"  {first} (~{tok} tok)")
        injection_body = (
            f"[PROMPT] {prompt_preview}\n"
            f"[注入摘要] {len(lines)}項, 合計 ~{total_tok} tok\n"
            + ("\n".join(summary_parts) if summary_parts else "NONE")
        )
        _atom_debug_log("注入", injection_body, config)

    # 走到這裡＝本輪 UPS 完整跑完 → 拆哨兵（timeout 砍掉時到不了這行，哨兵殘留）
    _ups_sentinel_clear(session_id)

    _hook_timing.claim_output()
    if lines:
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "\n".join(lines),
            }
        })
    else:
        output_nothing()
