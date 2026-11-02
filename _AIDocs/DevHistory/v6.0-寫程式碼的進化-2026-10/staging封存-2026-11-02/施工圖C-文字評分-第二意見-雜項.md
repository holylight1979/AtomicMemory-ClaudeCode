# 施工圖C-文字評分-第二意見-雜項

> 唯讀 agent 畫的施工圖，行號以 commit 55c748cc 為準。

Several items in this group were already done in commit 7f12e93e (2026-10-22): DISPATCH_OPENS_TURN, DPM_WORKTREE_DELIVERY, the E36 registration, row 38, and the E37 "上則評分" injection. The inventory was written before that commit, so for those items only leftover text remains. Line numbers are from HEAD 55c748cc, with a clean working tree.

## 1. Locations

**A. Row 23 – G15 background text scoring**
- Delete the whole file `C:\Users\holylight\.claude\hooks\wg_text_score.py`. It holds `on_stop`, `tail_note`, `current_goal`, `_reply_in_scope` and the `--job` background worker.
- `C:\Users\holylight\.claude\hooks\handlers\stop.py`:
  - line 81: top-level import, which runs even when the guard is off.
  - lines 1934-1950: the call block, including `_timed_out("文字評分")`.
  - line 1894: a comment that lists 文字評分.
- `C:\Users\holylight\.claude\hooks\handlers\user_prompt_submit.py:280-291`.
- The "上則評分" injection is already gone: `tail_note` always returns "" (wg_text_score.py:186-210). E37 is already out of `workflow\entrypoints.json`; only the stale text at line 21 is left.
- Rules:
  - TEXT_SCORE_CODE_REPLY_ONLY is referenced in code and docs but was never added to `RULES`.
  - CODING_TURN_ONLY (`hooks\wg_release_rules.py:177`) lists 文字評分 in its text; edit that text.
- State key `state["text_score"][sid]`. Dead ledgers: `Logs\guard-text_score_tail.jsonl` and `workflow\text-score\` (job files plus worker.log; `.gitignore:56`). Keep `Logs\guard-text_score.jsonl`, because manual runs also write to it.
- `C:\Users\holylight\.claude\tools\text-score.py` has parts only the background path uses: the `--auto-kind`, `--tail-line` and `--session` arguments (708-714), `path_matches` (659-668), `auto_skip_reason` (671-688), `main` 728-736 and 749-751, `DEFAULTS` 51 and 60-64, and docstring 9-10 and 17-18.
- **Manual `/text-score` skill:**
  - It can stand alone. `skills\text-score\SKILL.md` calls `tools\text-score.py`, which only needs `lib\project_root`, `tools\ollama_client`, `text-specs\` and the config keys `default_spec`, `judge_model`, `judge_model_by_backend`, `timeout_sec`, `num_ctx`. It does not depend on any hook.
  - **But it does not score anything today.** The default spec `text-specs\reader-designer.md` uses `{{goal}}` (lines 4 and 22). The skill never passes `--goal`, so the tool prints "不評：沒有當下的需求目標"; `verify_gate_trim.py:452-460` asserts exactly this.
  - Fix: either the skill passes `--goal "<需求一句>"`, or the spec stops requiring a goal.
  - Also rewrite SKILL.md:3 and 12 and `skills\_skill_index.json:132-134`.
  - Keep `tools\text-score-weekly.py`.

**B. Row 15 – SecondOpinion (E16)**
- Delete whole:
  - `C:\Users\holylight\.claude\hooks\wg_second_opinion.py`, except the helpers in §4.
  - `C:\Users\holylight\.claude\tools\second-opinion\` (run.py, pack.py, prompts.py, README.md).
  - `C:\Users\holylight\.claude\tools\workflow-guardian-mcp\lib\second-opinion.js`.
- `hooks\wg_release_rules.py`:
  - 3503-3734: the G9 block. Seven rules (3507-3538), the SO_* constants (3547-3564), and `second_opinion_hint`, `_decline`, `_decline_ok`, `_waiting`, `_section_missing`, `_triggers`, `_runs`, `_verdict` (3567-3733).
  - 4014-4025: SECOND_OPINION_BACKGROUND and SECOND_OPINION_DONE_NOTICE. This `RULES.update` block also holds rules you keep.
  - 4028-4036: `second_opinion_hint_background`.
  - 4071-4092: FACT_TRIGGER, EXIT_FINGERPRINT, PRE_CLOSE.
  - Names to drop from the tuple at 4220 and 4224.
  - Text mentions inside kept rules: 1056, 3867, 4051.
- MCP `C:\Users\holylight\.claude\tools\workflow-guardian-mcp\lib\mcp.js`: definitions 481-516, handlers 611-617, and line 88 (see G). Also `lib\_MAP.md:41`.
- `workflow\entrypoints.json:191-200` (E16). The judgment card `memory\驗證與實證\第二意見\第二意見分歧裁決-codex的block要親自重現成立才採-重現不了才不採-我方測試全綠不是駁回理由.md` has `- Entry: E16` on line 9. Without E16 the health check will list it under info.
- `settings.json:111`: remove `mcp__workflow-guardian__second_opinion_start` from the PreToolUse matcher.
- `tools\health-weekly.py`: 437-462 and 505-506.
- `.claude\overview-map.md`: line 9 explains the `gate` category, and rows 14, 16 and 19 are marked `gate` / "高風險：改了要第二意見". The only code that reads the raw `gate` value is `wg_second_opinion._gate_part`, so those rows become plain `code`.
- State keys: `second_opinion_gate_turn`, `_declared`, `_ok`, `_ran`, `_cover`, `_watch`, `_exit`, `_pre_close`, and `remind_so_fp`.
- Ledgers: `Logs\guard-second_opinion.jsonl` and `workflow\second-opinion\` (`.gitignore:211`).
- **Keep:**
  - `tools\replay-guard.py`: it existed before v6.
  - `lib\codex_models.py`: Codex Companion uses it.
  - Codex Companion's "第二意見" wording refers to a different feature.

**C. MCP `project_smells`**
- It is a read-only MCP tool. `lib\project-smells.js` spawns the candidate-pool mode of `tools\project-smells.py --json`, which reads a report, a `smells_cmd`, or built-in git hotspots. Both pieces were added in v6 (2be1b748).
- No hook calls it. The only reference is the text `wg_overview.py:88` IDLE_SCAN_LINE ("跑 `project_smells(part)`"), sent at 1186-1190 when the guard is on. If the tool goes, reword that line.
- Row 24 SmellGate does **not** depend on the MCP tool. It uses the commit-check half of `tools\project-smells.py`:
  - lines 369-1342: `check_commit`, `commit_entries`, `render_commit_report`, `_commit_check_cli`.
  - loaded from `pre_tool_use.py:1099-1111` and from `wg_gate_bypass.py`.
  - `_report_rows` (1222-1240) also reuses `find_root`, `_hub_inputs`, `load_hub_cfg`, `read_report` and `_rows_of` (64-136). Keep those.
- Delete:
  - `C:\Users\holylight\.claude\tools\workflow-guardian-mcp\lib\project-smells.js`.
  - mcp.js 517-534 and 618-621.
  - `_MAP.md:39`.
- Optional deletes:
  - the candidate-pool CLI in project-smells.py: 139-306 and `main` 1356-1369.
  - `lib\hub_config.py` keys `smells_cmd`, `smells_timeout_s`, `smells_category_map` (52-56, 102, 223).
  - `tools\verify\verify_project_smells.py`.

**D. Console/multi-session rules – already removed, only text left**
- DISPATCH_OPENS_TURN:
  - Not in `RULES`; `rr.is_dispatch_message` no longer exists (`verify_gate_trim.py:254-259` asserts this).
  - Stale text: `hooks\verify\verify_release_rules.py:565` (section header) and `verify_knowledge_harvest_gate.py:187` (docstring).
- DPM_WORKTREE_DELIVERY:
  - Gone. `dpm_instruction_text` (`wg_release_rules.py:1158-1174`) now gives everyone the same instruction.
  - Stale header at `verify_release_rules.py:671`.
- E36 selfscore:
  - The registry row is gone (`verify_gate_trim.py:275-279` asserts this). The tool now lives at `C:\Users\holylight\.claude\skills\console\scripts\selfscore.py`, with its test at `skills\console\verify\verify_selfscore.py` and ledger `Logs\guard-selfscore.jsonl`.
  - Leftover dead mechanism in `hooks\wg_entrypoint.py`: the `extra=` parameter (264-292) and `responses[].match` (377-385). Only E36 used them; nothing calls them now.
  - `entrypoints.json:26`: the `tool_cli` path value says "目前沒有接卡的".
  - Deleting the tool itself means deleting files under `skills\console`, the console-only skill.

**E. Row 38 – subagent code gate (already changed in 7f12e93e)**
- `C:\Users\holylight\.claude\hooks\handlers\stop.py`:
  - `_code_gate_no_ask` 1110-1169. The budget is at 1146-1155: `state["no_ask_gate_turn"][agent_id]` against `reconcile_gate.max_blocks_per_turn`, then it logs `subagent_released` / `judge_released` and lets the stop through.
  - `handle_subagent_stop` 1172-1181 and `handle_judge_stop` 1184-1192.
- The registered rule is NONINTERACTIVE_RELEASE_AT_BUDGET (`wg_release_rules.py:217-219`). `stop.py:1114` instead cites `SUBAGENT_SAME_BUDGET`, which is not registered.
- `wg_release.non_interactive_reason` is at `hooks\wg_release.py:70-76`.
- Covered by `verify_gate_trim.py:223-240`.
- Docs still say "擋到底":
  - `C:\Users\holylight\.claude\README.md:73`
  - `C:\Users\holylight\.claude\_AIDocs\Architecture.md:20`
  - the header at `verify_stop_reconcile.py:866`

**F. Config keys that become dead**
- G15: `text_score.enabled`, `min_chars`, `reply_scope`, `auto_targets` (`workflow\config.json:334, 343-347`; rewrite the `_doc` at 333).
- Second opinion: the whole `second_opinion` section (config.json:309-325), plus `wg_second_opinion.DEFAULTS` (44-50) and `workflow\config-consistency-notes.json:14, 58, 59`.
- need_goal tree:
  - `reconcile_gate.goal_gate` and its `_doc_goal_gate` (857-858).
  - `guard.origin_user_check` (503-506).
  - `coding_guard.slim_reminders`: no config.json entry; read in `wg_need_goal.py:337-341`; RULES text at 3929-3933.
  - `coding_guard.coding_turn_only` loses its trigger ② (`wg_core.py:240`, `need_goal_code_decl_turn`).
- Locate lines (only if the other agent removes the gate): `overview_hub.locate_template`, `locate_extra` (`lib\hub_config.py:36-37, 101-102`) and `min_overview_evidence` (config.json:655-659).
- Judgment cards: `entrypoint.inject_budget_tokens` and `inject_budget_total` (config.json:589-592).
- `hooks\wg_core.py` DEFAULTS has only `coding_guard.enabled` (124), so nothing to remove there. `paths.js`'s `v6Enabled` (59-76) stays; anti-evasion.js, atom-tools.js and harvest.js use it.

**G. GUARD_ONLY_TOOLS**
- After need_goal, second_opinion_start/result and project_smells are removed, the set is empty and the tool list is the same 9 tools whether the guard is on or off.
- In mcp.js:
  - Remove `GUARD_ONLY_TOOLS` and `listedTools` (86-92) and their export (652).
  - Line 70 returns `TOOL_DEFINITIONS` directly.
  - Drop the `v6Enabled` import at line 3.
- Delete `verify\verify_tools_list_guard_off.js` (it asserts 13 and 9), or rewrite it to assert 9 in both modes.
- `verify\smoke_mcp_stdio.js`: `EXPECTED_TOOLS` at 28-32 becomes 9, the count check at 85 becomes 9, and the checks at 90-110 and the header at 2-3 go.

## 2. Tests
**Delete whole files.** Two of these are imported by other test files, so fix the importers first:

| File | Note |
|---|---|
| `hooks\verify\verify_text_score_stop.py` | Move `test_weekly_counts_judges_and_kinds` (400-418) out first. `verify_pull_dev_residue.py:44` imports `world`, `spawned`, `wts` from it. |
| `hooks\verify\verify_g9_second_opinion.py` | `verify_closing_round.py:32` imports constants from it. |
| `tools\codex-companion\verify\verify_second_opinion.py` and `verify_second_opinion_new_files.py` | They test `tools\second-opinion\` despite the folder name. |
| `tools\verify\verify_second_opinion_pack_spawn.py` | |
| `tools\workflow-guardian-mcp\verify\verify_second_opinion_wait.js` and `verify_tools_list_guard_off.js` | |

**Partial edits:**
- `verify_gate_trim.py`: remove 184-191, 476-517 and the `second_opinion_result` call at 249; edit 282-290 (imports `wg_second_opinion`) and the docstring at 337-339. Keep 444-473; those are tool tests.
- `verify_gate_slimming.py`: remove 165-230 and 328-335 (the `wg_second_opinion` / `second_opinion_hint` asserts), 432-445, and 497-575 (`mark_review` / review tests, overlapping need_goal). Edit 231-234, which expects `TEXT_SCORE_CODE_REPLY_ONLY` in SKILL.md.
- `verify_pull_dev_residue.py`: 43-44, 178-195, 198-216, and the `run.py` half of 238-250.
- `verify_closing_round.py`: 251-399.
- `verify_pull_verify_ledger.py`: 27 and 128-255.
- Single tests:
  - `verify_pull_stop_gates.py:458`
  - `verify_gate_mode_stop.py:325`, and check the preview assert at 391
  - `verify_g11_turns.py:494`
  - `verify_release_rules.py:2000`, 2171, and the parameter lists at 2591-2621
  - `verify_workflow_retention.py:122-150`
  - `verify_v6_switch.py:147`
  - `verify_need_goal_points.py:421-430`
  - `verify_user_turn_key.py:126-127`
  - `verify_turn_judgment_threshold.py:30`
  - `verify_mcp_funnel_hardening.py:68, 99`
  - `verify_mcp_texts_avoid_evasion_words.py:208`
  - `tools\verify\verify_tools_data_root.py:53-54`
  - `lib\verify\verify_codex_models.py:88-90`
- `tools\verify\verify_text_score.py`: remove 572-640, `test_path_matches` and `test_config_section_matches_defaults` only if the background-only flags are dropped.
- Docstring-only mentions (verify_unknown_write_recover:10, verify_evasion_guard:278/393, verify_stop_reconcile:1415, verify_self_receipt:580) and the fixture `fixtures\gate005\c1_redtest_events.json` can be left as they are.

## 3. Docs (DevHistory and _CHANGELOG excluded)
- `TECH.md`:
  - 25, 78, 132, 324-325, 807
  - 1171-1205, 1252, 1301, 1311, 1329, 1353, 1370, 1619
  - §7.11 at 1667-1693: rewrite as manual-only
  - 1224, 1808 ("13 個 tool"), 2047, 2052, 2095, 2098, 2174, 2201
  - 2500 and 2525 (matcher), 2611, 2620, 2622, 3448, 4049
  - 4312, 4318-4319, 4331, 4376, 4382-4387
- `TECH\guards.md`:
  - 20, 23, 37, 78, 199, 256, 269, 458
  - SecondOpinion section 473-532, plus 544 and 568
  - 1765-1803, 2228, 2328, 2330-2347
  - A7.11 at 2404-2587: cut 2507-2564 (auto-scoring, tail line, Stop wiring) and keep spec, judge, ledger and weekly.
- `TECH\config.md`: 39, 57-59, 253-279 (keep the judge and spec rows), 300, 314, 322-324.
- `TECH\file-tree.md`: 17, 155, 159, 169-170, 368, 513-514.
- `TECH\release-rules.md`: 22, 79, 512, 692, 1029, 1094, the 第二意見 section 1179-1320, 1358, 1609, 1745, 2039.
- `_AIDocs\Architecture.md`: 20, 44, 205 ("12 tool").
- `_AIDocs\DocIndex-System.md`: 158, 176-177, 238.
- `README.md`: 38, 73.
- `text-specs\README.md`: 10 (mentions the 上則評分 tail line) and 18 (`auto_targets`).
- Skills: text-score SKILL.md and `_skill_index.json`.

## 4. Entanglements with kept features
- **Biggest one:** some helpers in `wg_second_opinion.py` are used by gates you keep. `_blocks` (71), `_turn_records` (99-114), `_COMPLETION_NEG_RE`, `turn_completion_text` and `turn_texts` (117-149) are called from:
  - `stop.py:1787`: `_turn_claim`, which feeds `_done()` for every closing gate.
  - `stop.py:2097`: NEGATIVE_CONTROL_DECLARED.
  
  Move these helpers before deleting the module; `wg_evasion.py` is a natural home since they already import from it. `turn_events` (161-187) and `section_text` are second-opinion only.
- **`wg_closing_round.py`**: keep `closing_call`, reading-path, turn-judgment and pick-one. Cut:
  - 11-14, 31-36, 46-49 (`so_background_on`)
  - 130-155 (`so_pre_close`)
  - 158-256 (done-notice)
  - 280-287 and 292-304 in `on_batch`
- **Kept row 13 (`wg_need_goal_points.py:227` REPORT_TOOLS)**: drop the second_opinion_result entry; the review-file regex at 228 stays. `wg_need_goal.py:798-799` and 1058-1112 (`mark_review`, REVIEW_FIX_RERUN_TOUCHED_ONLY) belong to the need_goal agent.
- **BLOCK_LISTS_LATER_GATES**: drop the second-opinion entry from `_later_gates` (stop.py:2000-2004).
- **Config check**: the config-consistency self-test in `tool_selftests` will report the removed and no-longer-read keys; run it afterwards.

## 5. Call sites to cut in shared files
- `stop.py`:
  - 9-10, 63 (`second_opinion_decline`, `_ok`, `_waiting`), 81, 82 (two `second_opinion_hint*` names), 84-87
  - 1934-1950, 1967-1986, 2000-2004, 2051-2070, 2421-2490
  - 2947-2968: keep the `_pick` path.
- `user_prompt_submit.py:280-291`.
- `post_tool_batch.py`: 10, 12, 39, 61, 84, 147, 269-283, 406.
- `pre_tool_use.py:1915-1929`.
- `session_start.py:1030-1034`.
- `_shared.py`: 317, 360-361, `_prune_job_dirs` at 472+, 592-593. The `job_dirs` kind is used only for second-opinion jobs.
- `dispatcher.py`: no change; second_opinion_start is not in `PRE_V6_TOOLS`.

## 6. Uncertainties
- For section D and row 38 the work is only leftover cleanup, since the code change already happened. Confirm that's what you want.
- Row 38's budget is counted per subagent (`no_ask_gate_turn[agent_id]`), not shared with the main session's counter. It has the same shape as the main session's budget, but not literally the same counter. Separately, `stop.py:1114` cites a rule name that isn't registered.
- Should `_prune_job_dirs` stay for one cleanup cycle so old `workflow\second-opinion\` folders get deleted, or should we just remove that folder by hand?
- For the E16 card: retire it, or only remove its `Entry` line?
- Keep the project-smells candidate CLI or not? It is referenced by IDLE_SCAN_LINE and by scorecard-report's "M4" note.
- Should the whole console skill go? That is outside this group, and `verify_gate_trim.py:289-290` asserts its files exist.
- How to fix the manual skill's goal problem: have the skill pass `--goal`, or relax `{{goal}}` in reader-designer?