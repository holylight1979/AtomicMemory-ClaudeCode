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
from typing import Any, Dict, List

from wg_core import (
    _ensure_state, _estimate_tokens, write_state,
    output_json, output_nothing,
    _atom_debug_log, WORKFLOW_DIR,
)
from wg_atoms import (
    compute_token_budget,
    _truncate_context_by_activation,
    _update_topic_tracker,
)
from wg_extraction import _maybe_spawn_failure_extraction
from handlers.ups_gates import run_pre_gates
from handlers.ups_context import build_context
from handlers.ups_search import collect_matched_atoms
from handlers.ups_inject import assemble_injection


def _drain_aec_decisions(session_id: str, lines: List[str]) -> None:
    """HUD (d) 保留/刪除決策 drain（注入端）。

    decision 檔由 Node（anti-evasion.js apiAecDecisionPost）落於 workflow/aec-decision/
    <sid>-t<turn>-<idx>.json（Node 寫 / 本處 Python 讀 = 對稱 one-writer）。glob 本 session
    未注入的決策 → 聚合成一段 additionalContext → 標 injected（atomic），供模型下回合 deferred
    執行（刪除 / 略過保留）。fail-open：讀不到 / 壞檔 skip，不阻斷 UPS。
    """
    if not session_id:
        return
    ddir = WORKFLOW_DIR / "aec-decision"
    try:
        paths = sorted(ddir.glob(f"{session_id}-t*.json"))
    except Exception:
        return
    deletes: List[str] = []
    keeps: List[str] = []
    consumed: List[tuple] = []
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue   # 壞檔 / 過渡檔 → skip
        if data.get("injected"):
            continue
        if data.get("session_id") != session_id:
            continue   # 檔名前綴已 scope，再校驗 session_id 欄位
        item = str(data.get("item", "")).strip() or f"(idx {data.get('idx')})"
        action = data.get("action")
        if action == "delete":
            deletes.append(item)
        elif action == "keep":
            keeps.append(item)
        else:
            continue
        consumed.append((p, data))
    if not consumed:
        return
    block = ["[Guardian:AEC-Decision] 使用者於 HUD 對 (d) 暫存清單做了處置："]
    block += [f"  🗑 刪除：{it}" for it in deletes]
    block += [f"  📌 保留：{it}" for it in keeps]
    block.append("請據此執行——刪除項確認路徑後移除、保留項略過；為 deferred，本回合執行。")
    lines.append("\n".join(block))
    for p, data in consumed:   # 標 injected（atomic tmp→replace），防下回合重注入
        data["injected"] = True
        try:
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(p)
        except Exception:
            pass


def handle_user_prompt_submit(
    input_data: Dict[str, Any], config: Dict[str, Any]
) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    prompt = input_data.get("prompt", "")
    clean_prompt = re.sub(r'<ide_\w+>.*?</ide_\w+>', '', prompt, flags=re.DOTALL).strip()
    prompt_lower = clean_prompt.lower()
    lines: List[str] = []

    # ─── Detect 段：前置閘（evasion 追蹤 / user decision gate / long_die / hot cache / atom-write guard）
    hot_cache_tokens = run_pre_gates(
        session_id, state, config, clean_prompt, prompt_lower, lines
    )

    # ─── Context build 段：session context / wisdom / parallel / AIDocs / JIT
    budget = compute_token_budget(prompt)
    budget = max(budget - hot_cache_tokens, 500)
    budget = build_context(
        session_id, state, config, prompt, clean_prompt, prompt_lower,
        budget, lines,
    )

    # ─── Search pipeline 段：候選收集（trigger/BM25/vector）+ supersedes + ACT-R 排序
    already_injected = state.get("injected_atoms", [])
    (
        matched_with_dir, atom_source, all_atoms,
        sem_atoms, section_hints, alias_injected_projects, intent,
    ) = collect_matched_atoms(
        session_id, state, config, prompt, prompt_lower, lines
    )

    # ─── Injection assemble 段：hot/cold + budget + related spread + 效用晉升提示
    newly_injected, atom_source_dirs = assemble_injection(
        session_id, state, config,
        matched_with_dir, all_atoms, already_injected,
        atom_source, section_hints, lines,
    )

    # Blind-Spot Reporter
    if (not matched_with_dir and not newly_injected and not alias_injected_projects
            and len(clean_prompt) >= 10):
        sem_count = len(sem_atoms) if sem_atoms else 0
        _atom_debug_log(
            "BlindSpot",
            f"未匹配: {clean_prompt[:80]} | intent={intent}, sem_results={sem_count}, already_injected={len(already_injected)}",
            config,
        )

    # Fix Escalation Protocol
    retry_count = state.get("wisdom_retry_count", 0)
    fix_esc_warned = state.get("fix_escalation_warned", False)
    if retry_count >= 2 and not fix_esc_warned:
        state["fix_escalation_warned"] = True
        state["fix_escalation_triggered"] = True
        lines.append(
            f"[Guardian:FixEscalation] 偵測到重複修正 "
            f"(retry={retry_count})。"
            "依據「精確修正升級」規則，必須暫停直接修復，"
            "執行 /fix-escalation 精確修正會議。"
        )

    # Evasion 上輪命中 → 注入舉證要求
    ev = state.get("evasion_flag")
    if ev:
        lines.append(
            f"[Guardian:Evasion] 你上輪用了退避語『{ev.get('phrase', '')}』。\n"
            f"  context: …{ev.get('context_excerpt', '')[:200]}…\n"
            "feedback-rigor-standards 規則：1-3 行能修就當場修。請說明：\n"
            "  (a) 實際修補成本（列出要改的檔/行數）\n"
            "  (b) 若仍選擇不修，為何這不是 feedback atom 所禁的退避說法？"
        )
        state["evasion_flag"] = None

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

    # Topic tracking
    _update_topic_tracker(state, prompt, intent, newly_injected)

    # AEC HUD 決策 drain：HUD (d) 保留/刪除鈕落的決策 → 注入 → 模型本回合 deferred 執行
    _drain_aec_decisions(session_id, lines)

    # Sync reminders
    mod_count = len(state.get("modified_files", []))
    kq_count = len(state.get("knowledge_queue", []))
    sync_kw = config.get("sync_keywords", [])
    prompt_has_sync = any(kw in prompt for kw in sync_kw)

    if prompt_has_sync and (mod_count > 0 or kq_count > 0):
        lines.append(f"[Guardian] Sync context: {mod_count} files modified, {kq_count} knowledge items pending.")
        if mod_count > 0:
            files = list({m["path"] for m in state["modified_files"]})
            lines.append(f"Files: {', '.join(f.rsplit('/', 1)[-1] for f in files[:10])}")
        if kq_count > 0:
            for q in state["knowledge_queue"]:
                lines.append(f"  - {q.get('classification', '[臨]')} {q['content'][:60]}")
    elif mod_count > 0 or kq_count > 0:
        remind_after = config.get("remind_after_turns", 3)
        remind_count = state.get("remind_count", 0)
        if remind_count < remind_after:
            state["remind_count"] = remind_count + 1
        else:
            max_reminders = config.get("max_reminders", 3)
            total_reminds = state.get("total_reminds", 0)
            if total_reminds < max_reminders:
                lines.append(
                    f"[Guardian] Reminder: {mod_count} files modified, {kq_count} knowledge items pending. "
                    "Consider syncing when current task completes."
                )
                state["remind_count"] = 0
                state["total_reminds"] = total_reminds + 1

    # per-turn 注入記錄（每 turn 覆寫）。
    # injected_atoms 是 session 累積（line 582 合併後 per-turn delta 遺失），
    # 無法精準歸因；turn_injected 只存「本 turn 注入」清單 + atom 檔路徑，
    # 供 Stop 做注入→使用→結果 (α,β) 歸因。無注入 turn → 覆寫為 []（清上一 turn）。
    state["turn_injected"] = [
        {"name": nm, "path": str(atom_source_dirs[nm] / f"{nm}.md")}
        for nm in newly_injected if nm in atom_source_dirs
    ]
    # 單調遞增 turn 序號 → Stop 端 per-turn 一次性歸因守門（防 blocked turn 重複計）。
    state["turn_seq"] = int(state.get("turn_seq", 0)) + 1

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

    if lines:
        lines = _truncate_context_by_activation(lines, budget, atom_source_dirs)
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "\n".join(lines),
            }
        })
    else:
        output_nothing()
