# 施工圖A-目標樹

> 唯讀 agent 畫的施工圖，行號以 commit 55c748cc 為準。

The whole tree depends on two modules, `wg_need_goal.py` and `wg_need_goal_points.py`. Neither file can be deleted as-is: kept features still use a few pieces of each. Move those pieces out first, then both files can go. Several kept gates also depend on the tree in ways that need reshaping (section 4).

All paths below are under `C:\Users\holylight\.claude\`. Line numbers are as of commit 55c748cc.

## 1. Locations per item

**Whole files to delete, after extraction:**
- `hooks\wg_need_goal.py` (2501 lines). Keep and move:
  - The code-file classifier: `_in_knowledge_part`, `is_code_path`, `_has_code`, `writes_code` and `DIR_SCAN_CAP` (1591-1636).
  - `CRITIQUE_CASES` and `CRITIQUE_CASES_POINTER` (103-109), which the kept critique line uses.
  - Everything else is tree-only.
- `hooks\wg_need_goal_points.py` (703 lines). Keep and move the AskUserQuestion gate parts: `ASK_TOOLS`, `_strings`, `_plan_file`, `ask_text`, `_part_reads`, `_named_parts`, `ask_key`, `mark_asked`, `_call_parts`, `has_ask_calls`, `asks_after`, and `_judge_ask`/`on_ask_full` minus lines 457-480.
- `tools\workflow-guardian-mcp\lib\need-goal.js`.

**Row 3 (update progress):**
- `_op_update` 1309-1373, `auto_progress` 2000-2031.
- `wg_bg_harvest.py` 6, 118-206 (progress_targets, write_progress, progress part of build_prompt).
- PROGRESS_LINE_BY_PROGRAM exists only in comments; it has no RULES entry.

**Row 4 (reconcile / full mapping):**
- In `wg_need_goal`:
  - evidence block 898-1160, `mark_review`/`_review_done`/`_review_fix_unaffected` 1066-1113
  - `_op_reconcile` 1376-1436, receipt stamping 1919-1991
  - `auto_reconcile`/`refresh_auto_evidence`/`_f2_text`/`_f3_text`/`goal_gate_reason`/`commit_gate`/`reconcile_fresh` 2034-2239
  - `snapshot_for_report` 2286-2312, TURNS_* 60-65
- RULES in `wg_release_rules.py`:
  - GOAL_DONE_NEEDS_CASE_OR_RECEIPT 246, GOAL_INFERRED_MAX_PARTIAL 248, CASE_RED_THEN_GREEN 249, EDITED_PART_NEEDS_GOAL_NODE 282 (this is (f3)), KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY 2006
  - CLOSING_RECONCILE_IN_REPORT 4040, CLOSING_MISSING_PART_HINT 4045, CLOSING_GOAL_CODING_ONLY 4048
  - COMMIT_GOAL_RECONCILED 4132, GOAL_RECONCILE_AT_DELIVERY 4170, GOAL_TREE_SET_ONCE 4172 (and the `+=` at 4291)
- Helpers in `wg_release_rules.py`:
  - Delete `_evidence_have`, `goal_done_evidence_verdict`, `goal_inferred_verdict`, `red_then_green` (1619-1657); `edited_part_goal_verdict` (1844-1860); `knowledge_reconcile_verdict` (2020).
  - **Keep `receipt_red`/`receipt_green`** (the equivalence gate and `wg_verify_batch` use them).
- Other tables in `wg_release_rules.py`: `LETTER_RULE` "f3"/"f4" (4214); drop the goal names from the suffix loops at 4217-4224 and 4228-4230.
- `workflow\entrypoints.json`: E26 (281-290) delete; E01 drop EDITED_PART_NEEDS_GOAL_NODE (32, 39).
- `workflow\config.json` 857-858 `reconcile_gate.goal_gate`.

**Row 5 (ReconcileGate (a)(d)) — KEEP.** `stop.py _verify_gates` 948-1049 never reads the goal file. Only the `if goal:` block is cut (section 4).

**Row 8 (edit gate, per-prompt root line, light-tree hint, UPS hint):**
- In `wg_need_goal`: TEXT_SET_* 95-100, HINT_LINE 101-102, CODE_TREE_HINT 1168-1170, `on_prompt` 1528-1586.
- Also: `_ephemeral`, `_edit_gate_applies`, `edit_gate` 1639-1671; `set_via_text`/GOAL_LINE_RE 1674-1763; `tree_owed_for_edit`/`goal_for_edit`/`link_part`/`stamp_edit` 1766-1873; `_knowledge_write`/`_note_untreed` 1876-1916; `knowledge_gate_reason` 2242-2274.
- RULES: CODE_EDIT_NEEDS_GOAL_TREE 4128 (+4293), TREE_SET_VIA_TEXT 4279-4290 (and the RULE_MODE line at 4295), KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE 2003 with `knowledge_light_tree_verdict` 2012.
- Edit the wording only: NON_CODING_TURN_NO_NUDGE 4268 and DECL_HINT_KEEPS_EDIT_TOOLS 2924.

**Row 9 (verify_scope) — already removed** in c5e768f7. What remains:
- Stubs: `TECH.md` §7.9 1628-1632 (TOC line 76) and `TECH\guards.md` A7.9 2197-2201.
- `entrypoints.json:425` note text; `smoke_mcp_stdio.js` 150-154 (goes away with the tool); `verify_lang_guard.py:131` fixture text.
- `workflow\followups.json` 40, 74, 76 (data only).

**Row 27 (ASK_LINKED_TO_GOAL):**
- RULES 1869-1872, ASK_FRAGMENT_MIN 1880, `ask_link_units` 1912-1920, `node_fragment_ref`/`ask_goal_link_verdict`/`ask_audit_note` 1965-2000.
- In `wg_need_goal_points`: NO_TREE_HINT 39-40, 324-358, the link parts of `_ask_audit` 405-426, `_ask_checkpoint` 428, `_judge_ask` 457-480.
- E25 (271-280): keep the entry but shrink it to ASK_NEEDS_RECOMMENDATION and fix its marker/asks/feeds/responses.

**Row 22 (ORIGIN_USER_NEEDS_QUOTE) — still in code:**
- `wg_need_goal` 1213-1272, plus the calls in `_op_set`/`_op_add`/`_op_update`/`import_handoff`.
- `rr` 3044-3127 (both ORIGIN_* rules, ORIGIN_QUOTE_MIN, `_said_*`, `origin_user_verdict`, `root_unquoted_sentences`).
- E23 261-270; `config.json` 503-505 `guard.origin_user_check`.

**Row 2 (HANDOUT_CHECK) — program already removed** in 7f12e93e (`verify_gate_trim.py:57` asserts it is gone). What remains: the `entrypoints.json:5` _doc mention and the judge card `memory\行為契約\交出計畫清單收尾前…落差要說出來.md` (Entry: E26之二).

**Row 13 (E06, goal-view recheck) — still in code:**
- `wg_need_goal_points` 104-283 (scope, external claim, correction) and 541-631 (multi-edit, `_flush`, `batch_due`, `batch_lines`, `goal_view_text`).
- `wg_overview` `on_goal_changed` 482-500, `_goal_view` 921-939, goal_view_due 1051-1067.
- RULES GOAL_VIEW_ONE_LINE 3964, TREE_LINE_IN_HINTS 3930, CRITIQUE_CASES_ONCE_PER_SESSION 3924.
- E06 81-90.

**MCP `need_goal` tool:**
- `lib\mcp.js`: 88 (GUARD_ONLY_TOOLS), 341-352 (the `reconcile` field of anti_evasion_report), 363 (text), 535-593 (tool definition), 622-625 (dispatch).
- `anti-evasion.js` 81-82, 95-99; `aec-hud-html.js` 314, 321-340 (`renderGoal`); `_MAP.md` 21, 40-41, 54-56.
- `settings.json` matcher token `|mcp__workflow-guardian__need_goal` on lines 111 and 123.

**Used only by the tree:**
- `handoff_block`/`import_handoff`/`recovery_blob`/`review_material`/`render`/`brief*`.
- `lib\hub_config.py` 26, 85-87, 237-247, 320.
- `hooks\handlers\_shared.py` retention 314, 317, 340, 426+, 588-589.
- `conftest.py` 197-199.
- State keys: need_goal_code_decl_turn, need_goal_asks, need_goal_ask_blocks, need_goal_batch, need_goal_multi_checked, need_goal_text_scan, need_goal_recovery_sent, pending_reinjection_goal.
- Data dir `workflow\need-goal\`.

**`wg_core.coding_turn` (235-259):**
- Delete the docstring lines 240-242 and the branch at 253-255.
- Re-point the import at 256 to the new classifier module.
- Fix the CODE_INTENTS comment at 232-233 and the CODING_TURN_ONLY rule text at 177.

## 2. Tests

**Delete the whole file:**
- `hooks\verify\verify_need_goal.py` — first move `test_is_code_path_union_and_shebang`@814.
- `verify_need_goal_points.py` — first move the recommendation / overview / release / plan tests at 543, 557, 571, 586, 665, 1106, 1128, 1142, 1151, 1208, 1221, 1252, 1266, 1358.
- `verify_origin_user_check.py`, `verify_goal_tree_once.py`, `verify_locate_via_need_goal.py`, `verify_data_file_via_need_goal.py`, `probe_need_goal_flow.py`.
- `verify_closing_merge.py` — keep or move `test_closing_check_block_says_one_call`@131.
- MCP: `verify_need_goal_schema_budget.js`, `verify_need_goal_locate.js`, `verify_need_goal_data_files.js`, `verify_aec_reconcile.js`.

**Partial edits:**
- verify_release_rules: tests @137, 1413, 1506, 1526, 1936, 2157, 2399, 2688, 2715.
- verify_gate_trim: @68, 85, 126, 194, 245, 315, 394, 476, 487. Test @53 can be dropped.
- verify_pull_goal_locate: the 15 tree tests, keeping @166, 209, 247, 281-329, 563, 580.
- verify_cost_cut: @248-373, 417.
- verify_gate_mode_pre: @110, 126, 141, 159, 176.
- verify_locate_hint: all 5.
- verify_g9_second_opinion: @370, 578, 727, 743.
- verify_gate_slimming: @432, 497-544.
- verify_g11_turns: @549, 561.
- verify_closing_round: @165, 389.
- verify_pull_stop_gates: @555 plus the 10 uses of need_goal_code_decl_turn.
- verify_stop_reconcile: 10 uses of need_goal_code_decl_turn (in the (a) tests @176-205, 782).
- `tools\verify\verify_entrypoint_contract.py`: @613, 671.
- One test or helper each in: verify_read_fast_path@167, verify_pull_tool_gates@374, verify_modified_files_turn@251, verify_chain_breaker@986, verify_chain_wiring@427, verify_v6_switch@296, verify_workflow_retention@97/106, verify_overview_card_pointer@287, verify_rut_scope, verify_hook_timing@530, verify_text_score_stop, verify_pick_one@586, verify_unknown_write_recover@249, verify_entry_wording@88, verify_gate_mode_stop@457, verify_inject_lean:182, verify_lang_guard@136.
- Monkeypatches that will break: verify_gate_bypass:130, verify_sync_reminder_later_turn:56, verify_old_test_declare:491.
- Probes: probe_c_g16 P3/P4 (keep P1/P2/P5), probe_c_g0 (its f3 step); config tweaks in probe_release_rules:35/423-431 and probe_move_dir:34/66.
- `lib\verify\verify_git_cassette.py`@207; `verify_testfail_clear_replay.py:30` (list of file names).
- `smoke_mcp_stdio.js` and `verify_tools_list_guard_off.js`: tool count goes from 13 to 12.

## 3. Docs
- **`TECH.md`**:
  - Delete §7.7 (1535-1585) and its TOC line 74.
  - Fix the anchor references at 25, 761, 1169, 1192, 1205, 1214, 1240-1269, 1288-1293, 1422, 1618, 1700, 2084, 2130, 2500-2613, 3415-3417, 4312, 4376-4379.
- **`TECH\guards.md`**:
  - Delete A7.7 (1876-2196) and the `need_goal.enabled` subsection at 1872.
  - Edit 18-54, 101-217, 241, 324, 354, 377, 471, 504, 719, 779, 820, 1042, 1172, 1243, 1285, 1492, 1664, 1769, 1791, 2552, 2606, 2614, 2671, 2758.
- **`TECH\release-rules.md`**:
  - Index at 1-38.
  - Sections at 844, 854, 911, 923, 952, 1612, 1619, 1836, 1908, 1918, 2008, 2021, 2029, 2038, 2080, 2092, 2137, 2140, 2149.
  - Keep ASK_NEEDS_RECOMMENDATION 939, ASK_OVERVIEW_BEFORE_DECISION 966, LOCATE_LINES_NEED_CRITIQUE 983.
- **`TECH\config.md`** 22, 54, 80, 177. **`TECH\file-tree.md`** 125-132, 160, 208, 509, 573.
- **`_AIDocs\Architecture.md`** 17, 37-38, 42, 121, 127. **`README.md:38`**.
- **Skills**: `skills\handoff\SKILL.md` 59-62, `skills\continue\SKILL.md` 58-69, `skills\console\SKILL.md` 142, `skills\upgrade\SKILL.md` 77.
- **Other**: `tools\second-opinion\README.md` 44-47.
- **Judge cards bound to these entry codes**:
  - E23: `memory\思考與決策\origin標使用者說的…`
  - E26: `…\樹根寫使用者這次要的全部結果…` and `memory\驗證與實證\交付對照的達成要有…`
  - E25: `memory\行為契約\提問掛節點要看…`
  - E26之二: `交出計畫清單…`
- About 20 cards in `_AIDocs\_atoms\MemDev` and `memory\` mention need_goal.

## 4. Entanglements with kept features
1. **Code-file classifier.** `writes_code`/`is_code_path` are used by `wg_core.coding_turn`:256, `stop.py` 1737 and 1939, `wg_data_file` 207/282/325, `wg_second_opinion` 374, `wg_harvest.pick_code_mods` 841 (PickOne), `post_tool_batch` 107, `wg_overview` 1091/1129/1502 (min-map and locate hint), and `tools\project-smells.py` 1046. Fix: move them to a small new module (for example `hooks\wg_code_path.py`, with a lazy import of `wg_verify_ledger`) and re-point all imports.
2. **ReconcileGate (a)(d).**
   - In `stop.py`: delete 1050-1087, the `goal`/`goal_cfg`/`coding` parameters (937-944) and the arguments at 2235.
   - Delete `closing_reconcile_hint` (925-930). Reword `CLOSING_ONE_CALL` (919-920, still used at 2703) to drop the reconcile field.
   - Receipts for (a)(d) come from state via `receipts_of`; `stamp_receipts` only copied them into the goal file. The shared block budget is unaffected: (f2)-(f4) were remind-only when the guard is on.
3. **ASK_NEEDS_RECOMMENDATION (row 26) and ASK_OVERVIEW_BEFORE_DECISION (E05)** live inside the need_goal modules:
   - Move them to a new module and re-point `pre_tool_use._need_goal_ask` 1788-1867 (call at 1910-1913).
   - It is currently switched by `need_goal.enabled` (1804); it needs its own switch, or just follow the guard switch.
   - Its log entries go to `guard-need_goal` (ask_no_recommendation, ask_blocked, ask_audit, ask_error, remind). Rename that log and update the E25 responses.
   - The early reminder "attach a recommendation from now on" is hung on `need_goal set` (`post_tool_use` 2005-2011). Re-anchor it or drop it.
   - The PostToolBatch fallback (`asks_after` and `_ask_audit`, loaded through `_points_module` 28-35 and 336-337) must stay.
   - Reword the error text at 1846-1851.
4. **Locate gate (rows 10, 11, 12) — the biggest risk.**
   - The critique line (row 12, kept) and the two-candidates check are only enforced when a tree exists: `wg_overview._goal_line_check` 1381-1411 is reached only via `goal_tree` at 1982, 2072-2075 and `_locate_ask` 2179. The locate hint switches between 3 and 4 lines based on the tree (1131-1155).
   - Once the tree is gone, critique enforcement silently disappears. Fix: decouple the critique check (and two-candidates, if kept) from the tree, drop the 4th "目標" line, and teach 3 lines plus 批判.
   - Also: `_goal_block` 409-428 (call at 528), `relink_parts` 448-479, `_goal_tree_for`/`_goal_linked` 431-439, `locate_from_goal` 2028-2091 (the MCP channel), the `goal_tree` plumbing at 1851-1883, 1993-2002 and 2127-2146, and the logging through `_ng._guard` at 1409 and 1963.
   - `lib\overview_hub.py` 32 and 699 (GOAL_NODE_PLACEHOLDER).
5. **DataFileAsk (row 16).** The `data_files` channel goes away: `wg_data_file.declare_via_need_goal` 232-260 and `post_tool_use` 1092-1099. The text channel stays.
6. **coding_turn.** Without layer ②, the (a)/stop tests that fake a coding turn with `need_goal_code_decl_turn` need another trigger, such as `modified_files` or `unknown_writes` at the current turn.
7. **SecondOpinion (row 15).**
   - Affected: `pack.goal_material` 272-291, `question_root_missing` 299-310, `run.py` 281, `wg_second_opinion.has_goal_tree` 344-350 (used at 426), `rr` SO_QUESTION_ROOT_MISSING/SO_NO_GOAL_NOTE 3551-3552, and `second_opinion_runs` `has_tree` 3640-3690.
   - The second-opinion hook in `pre_tool_use` 1919-1924 that records review time (`mark_review`) only feeds reconcile; delete it.
   - Fix: no tree means `has_tree=False`, and drop the check that the question contains the tree root.
8. **TextScore (row 23).** Drop the tree branch in `current_goal` (87-98); the `turn_prompts` fallback stays.
9. **Closing round.**
   - Drop the `need_goal` branch in `wg_closing_round` 29 and 61-66.
   - Reword the rules TURN_JUDGMENT_PRE_CLOSE 4004, CLOSING_CALL_ALL_THREE 4051, SECOND_OPINION_PRE_CLOSE 4085.
10. **Chain breaker.** Drop `wg_chain` 36 and 678-679 and the settings matcher token; reword CHAIN_NO_EDIT_NO_EDGE 3896.
11. **Tracking / PickOne.** Reconcile followups (`_append_tracking`) stop being a source of tracking items. Reword `mcp.js:363` and TRACKING_SAME_ITEM_NOT_REWRITTEN 3237.
12. **Judge-card topic.** `wg_entrypoint._topic_key` 308-318 becomes always "session".
13. **Overview card (row 19).** It loses its tree prefix. In `post_compact._overview_blob`, `has_goal` becomes always False.
14. **Settings files.** Add `need_goal` to `hub_config.RETIRED_KEYS` (98) so existing `overview-hub.json` files that still have that key don't fail validation.
15. **Small items.** `wg_gate_bypass` 566 has "NeedGoal" in GATE_WORDS; ATOM_BYPASS_HOWTO_REFUSED (3315) text.

**Pre-v6 behaviour.** Every tree path is gated by the guard switch or excluded by `dispatcher.PRE_V6_TOOLS` (AskUserQuestion and MCP need_goal are not in it). The only ungated tree code is `wg_handoff` 86 and 134 and `codex_companion._review_goal` 62-71. Both do nothing when there is no tree, and removing them returns exactly to the 9e476fd0 code.

## 5. Shared dispatcher call sites to cut
- `user_prompt_submit.py`: 121 (only if nothing else uses it), 208-224, 319-330.
- `pre_tool_use.py`: 1788-1867 (re-home), 1919-1924, 2161-2192, 2206-2211 (`_ng_sources`/`_ng_content`), 2222-2241.
- `post_tool_use.py`: 1055-1144, 1248, 1305-1320, 1411-1433, 1495-1504, 1535-1539, 1865-1866, 1916-1925, 1987-1990, 2005-2011.
- `post_tool_batch.py`: 7-15, 28-35, 107 (swap import), 333-337, 347-349, 373-376, 397-404.
- `stop.py`: 919-930, 937-944, 1050-1087, 1737 and 1939 (swap import), 2235.
- `session_start.py`: 1095-1102, 1130, 1245-1255.
- `session_end.py`: 264-272.
- `post_compact.py`: 20-22, 34, 94-103, 107/128-129, 171-176, 188.
- `_shared.py`: retention lines above.
- `wg_release_rules.py`: everything listed in section 1, plus 4214-4230 and 4291-4295.
- `workflow-guardian.py` and `dispatcher.py`: no change.

## 6. Unresolved
- I read "program part removed" for rows 13 and 22 as an instruction. Neither is removed yet; only row 2 is.
- Rows 11/12 and (f3) EDITED_PART_NEEDS_GOAL_NODE may belong to another removal group. Either way, critique enforcement needs a no-tree path, and someone has to decide whether two-candidates still applies without a tree.
- The ask gate needs a new switch and log name, and the E25/E05 entries need new wording.
- Whether CRITIQUE_CASES (the three-cases text) stays in the critique hint.
- Leftover data in `workflow\need-goal\` and the probe sandboxes under it (`_probe*`): convert the retention rule to an age rule, or delete the folder once.
- Sessions running an old MCP process may still call `need_goal`; once the PostToolUse matcher token is gone, those calls do nothing.
- The 5 judge cards bound to these entry codes: retire them or rebind.