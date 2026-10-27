"""target_verify.py — closing-time 這次改動的目標驗證範圍：受改動影響的案例檔整支跑（不跑全量）。

範圍判法：改到的檔（stop.py、post_tool_batch.py、wg_reading_path.py、wg_second_opinion.py、wg_release_rules.py、wg_closing_round.py、
workflow/entrypoints.json、MCP second-opinion.js／mcp.js）＋ 會 import 或驅動它們的案例（grep：handle_stop(、post_tool_batch、
entrypoints.json／load_registry、second_opinion、reading_path）。
怎麼跑：python -X utf8 target_verify.py   （在 closing-time worktree 根跑 pytest 與 node）
尾行：TARGET_VERIFY_CHECK PASS|FAIL
"""
import subprocess
import sys
from pathlib import Path

TREE = Path(r"C:/Users/holylight/.claude-wt/closing-time")
PY = [
    "hooks/verify/verify_closing_round.py", "hooks/verify/verify_release_rules.py", "hooks/verify/verify_g9_second_opinion.py",
    "hooks/verify/verify_pick_one.py", "hooks/verify/verify_g11_turns.py", "hooks/verify/verify_pull_reading_path.py",
    "hooks/verify/verify_reading_path_hook.py", "hooks/verify/verify_post_compact_reinjection_phase4.py",
    "hooks/verify/verify_auto_handoff.py", "hooks/verify/verify_need_goal_points.py", "hooks/verify/verify_evasion_guard.py",
    "hooks/verify/verify_v6_switch.py", "hooks/verify/verify_chain_wiring.py", "hooks/verify/verify_chain_breaker.py",
    "hooks/verify/verify_pull_stop_gates.py", "hooks/verify/verify_gate005_c1_e2e.py", "hooks/verify/verify_entry_wording.py",
    "hooks/verify/verify_pull_verify_ledger.py", "hooks/verify/verify_stop_reconcile.py", "hooks/verify/verify_gate_slimming.py",
    "hooks/verify/verify_gate_trim.py", "hooks/verify/verify_text_score_stop.py", "hooks/verify/verify_g7_equivalence.py",
    "hooks/verify/verify_pull_goal_locate.py", "hooks/verify/verify_hook_timing.py", "hooks/verify/verify_aec_emission_gate.py",
    "hooks/verify/verify_deferral_gate.py", "hooks/verify/verify_deep_postmortem_gate.py", "hooks/verify/verify_knowledge_harvest_gate.py",
    "hooks/verify/verify_sync_reminder_later_turn.py", "hooks/verify/verify_sync_reminder_session_filter.py",
    "hooks/verify/verify_sync_reminder_unpushed.py", "hooks/verify/verify_scan_report_session_filter.py",
    "hooks/verify/verify_g6_rules_to_llm.py", "hooks/verify/verify_pull_dev_residue.py", "hooks/verify/verify_cost_cut.py",
    "hooks/verify/verify_mcp_funnel_hardening.py", "hooks/verify/verify_need_goal.py",
    "tools/verify/verify_entrypoint_contract.py", "tools/verify/verify_entry_stats_asks.py",
    "tools/verify/verify_second_opinion_pack_spawn.py", "lib/verify/verify_reading_path_cs.py",
]
JS = ["tools/workflow-guardian-mcp/verify/verify_second_opinion_wait.js", "tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js"]

ok = True
r = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", "-q", "-p", "no:cacheprovider", *PY], cwd=TREE,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
tail = [ln for ln in r.stdout.splitlines() if ln.strip()][-12:]
print("\n".join(tail))
ok = ok and r.returncode == 0
for js in JS:
    j = subprocess.run(["node", js], cwd=TREE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    last = ([ln for ln in (j.stdout + j.stderr).splitlines() if ln.strip()] or ["(無輸出)"])[-1]
    print(f"{js}: exit={j.returncode} 尾行：{last}")
    ok = ok and j.returncode == 0
print(f"TARGET_VERIFY_CHECK {'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
