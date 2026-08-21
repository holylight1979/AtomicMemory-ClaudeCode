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
from pathlib import Path
from typing import Any, Dict, List, Optional

from wg_core import (
    _ensure_state, _estimate_tokens, _now_iso, write_state,
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


def _write_decision_file(p: Path, data: Dict[str, Any]) -> None:
    """決策檔回寫（atomic tmp→replace）。fail-open。"""
    try:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        pass


def _decision_item_path(item: str) -> Optional[Path]:
    """把 (d) 決策項字串保守解析為可 exists() 檢查的路徑；非路徑樣貌回 None。

    只認含路徑分隔符的單行短字串（prose 敘述 / 裸檔名無從定位 → None＝不後驗）；
    相對路徑以 ~/.claude 為基準（HUD (d) 項慣為 repo 相對路徑）。"""
    s = (item or "").strip().strip("`\"'")
    if not s or len(s) > 400 or "\n" in s:
        return None
    if "/" not in s and "\\" not in s:
        return None
    p = Path(s).expanduser()
    if not p.is_absolute():
        p = Path.home() / ".claude" / s
    return p


def _drain_aec_decisions(session_id: str, lines: List[str]) -> None:
    """HUD (d) 保留/刪除決策 drain（注入端）+ 刪除決策後驗。

    decision 檔由 Node（anti-evasion.js apiAecDecisionPost）落於 workflow/aec-decision/
    <sid>-t<turn>-<idx>.json（Node 寫 / 本處 Python 讀 = 對稱 one-writer）。glob 本 session
    未注入的決策 → 聚合成一段 additionalContext → 標 injected（atomic），供模型下回合 deferred
    執行（刪除 / 略過保留）。fail-open：讀不到 / 壞檔 skip，不阻斷 UPS。

    後驗（exists() 實查，不信宣告）：上輪已注入的 delete 項，本輪檢查檔案是否真的
    消失——仍在 → 重注入一次（reinjected 標記）；重注入後仍在 → 浮告警後結案
    （verified 標記，不無限 nag）；已消失/無從解析路徑 → 靜默結案。"""
    if not session_id:
        return
    ddir = WORKFLOW_DIR / "aec-decision"
    try:
        paths = sorted(ddir.glob(f"{session_id}-t*.json"))
    except Exception:
        return
    loaded: List[tuple] = []
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue   # 壞檔 / 過渡檔 → skip
        if data.get("session_id") != session_id:
            continue   # 檔名前綴已 scope，再校驗 session_id 欄位
        loaded.append((p, data))

    # ── Phase 1：刪除決策後驗（只看已 injected 且未 verified 的 delete 項）──
    reinject: List[str] = []
    warn: List[str] = []
    for p, data in loaded:
        if (
            not data.get("injected")
            or data.get("action") != "delete"
            or data.get("verified")
        ):
            continue
        item = str(data.get("item", ""))
        target = _decision_item_path(item)
        if target is None or not target.exists():
            data["verified"] = True     # 已刪 / 無從檢查 → 結案
        elif not data.get("reinjected"):
            data["reinjected"] = True   # 仍在 → 重注入一次
            reinject.append(item)
        else:
            data["verified"] = True     # 重注入過仍在 → 告警後結案
            warn.append(item)
        _write_decision_file(p, data)
    if reinject or warn:
        blk = ["[Guardian:AEC-Decision] 刪除決策後驗（exists() 實查）："]
        blk += [f"  🔁 上輪已注入刪除但檔案仍存在，請本回合執行刪除：{it}" for it in reinject]
        blk += [f"  ⚠ 重注入後仍未刪除，請說明原因或請使用者手動處理：{it}" for it in warn]
        lines.append("\n".join(blk))

    # ── Phase 2：新決策注入（未 injected 者）──
    deletes: List[str] = []
    keeps: List[str] = []
    consumed: List[tuple] = []
    for p, data in loaded:
        if data.get("injected"):
            continue
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
        _write_decision_file(p, data)


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
        )
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

    # ─── Detect 段：前置閘（evasion 追蹤 / user decision gate / long_die / atom-write guard）
    run_pre_gates(
        session_id, state, config, clean_prompt, prompt_lower, lines
    )

    # ─── Context build 段：session context / wisdom / parallel / AIDocs / JIT
    budget = compute_token_budget(prompt)
    budget = build_context(
        session_id, state, config, prompt, clean_prompt, prompt_lower,
        budget, lines,
    )

    # ─── Search pipeline 段：候選收集（trigger/BM25/vector）+ supersedes + ACT-R 排序
    already_injected = state.get("injected_atoms", [])
    (
        matched_with_dir, atom_source, all_atoms,
        sem_atoms, section_hints, alias_injected_projects, intent,
        caches,
    ) = collect_matched_atoms(
        session_id, state, config, prompt, prompt_lower, lines
    )

    # ─── Injection assemble 段：hot/cold + budget + related spread + 效用晉升提示
    newly_injected, atom_source_dirs = assemble_injection(
        session_id, state, config,
        matched_with_dir, all_atoms, already_injected,
        atom_source, section_hints, lines,
        caches=caches,
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
    # 週期性「N files modified」提醒不進 chat——statusline（tools/statusline.py）
    # 常駐顯示改檔/佇列數（零 token）；模型端 enforcement 由 Stop SyncReminder 閘兜底。

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

    # 走到這裡＝本輪 UPS 完整跑完 → 拆哨兵（timeout 砍掉時到不了這行，哨兵殘留）
    _ups_sentinel_clear(session_id)

    if lines:
        lines = _truncate_context_by_activation(lines, budget, atom_source_dirs, config)
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "\n".join(lines),
            }
        })
    else:
        output_nothing()
