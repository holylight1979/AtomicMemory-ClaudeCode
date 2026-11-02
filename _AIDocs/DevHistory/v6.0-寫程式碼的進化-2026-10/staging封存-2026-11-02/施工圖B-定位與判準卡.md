# 施工圖B-定位與判準卡

> 唯讀 agent 畫的施工圖，行號以 commit 55c748cc 為準。

I mapped all ten items. The biggest issue: with the guard off today, OverviewHub doesn't run at all, so the pre-v6 warn-only behaviour you want to keep is not what currently runs.

All paths are under `C:/Users/holylight/.claude/`. Line numbers are at HEAD 55c748cc.

## 1. Locations per item

**Row 10 – OverviewHub write gate** (`hooks/wg_overview.py`, 2206 lines; the pre-v6 version is 189 lines, see `git show 9e476fd0:hooks/wg_overview.py`)
- **Pre-v6 baseline:** `on_read` / `on_prompt` / `on_edit`, `dry_run=True` by default, only three locate lines (部位/根因層/前例) via `lib/overview_hub.locate_channel`, nothing for files outside a part table.
- **v6 additions inside `edit_check` (1679-1954):**
  - card-missing deny 1748-1776; first-edit block 1777-1803 plus `_first_edit_once` 2096-2118
  - locate round 1821-1828 (`_locate_round_probe` 2124-2146, `_locate_round_check` 2149-2168, round book 1251-1306 except `remind_sent_list` 1283-1292)
  - part-file / depends evidence 1844-1849; transcript self-error 1839-1843; 4th line from the goal tree 1850-1873
  - "must Read the pointer card" `_unread_cards` / `_card_unread_line` 1658-1669 (used at 1780, 1808, 1835)
  - once-per-turn 1908-1918 (`_blocked_parts` / `_note_block` 2191-2206); deny cap 1919-1931; same-batch short 1932-1943; example-once 1944-1954
  - layer check `_row_layers` / `_layer_mismatch` 1360-1371 (pre-v6 had none); `_find_locate` 1966, `_mark_located` 1992, `_locate_ask` 2172-2188, `_locate_gap_guard` 1957
- **Files outside a part table, "read same dir first":** `_unmapped_edit` 1585-1655, `_readable_existing` 1452-1478, `_gitignored` 1427-1436, branch 1742-1743. Keep `_gitignored_set` 1439-1449 (used by `wg_verify_ledger.py:1265`).
- **RULES in `hooks/wg_release_rules.py`:** LOCATE_FIRST_EDIT_BLOCKS_ONCE 4154 (and RULE_CLASS 4203), LOCATE_BEFORE_EDIT 4148, OVERVIEW_PART_FILES_READ 4131, OVERVIEW_CARD_BEFORE_EDIT 4129, LOCATE_BLOCK_ONCE_PER_USER_TURN 3957, LOCATE_NOT_IN_THINKING 3962, LOCATE_EXAMPLE_ONCE_PER_SESSION 3987, CARD_READ_WITH_EDIT_FILES 3993, INJECT_TRIGGER_READ_COUNTED 3916, UNMAPPED_EDIT_NEEDS_READABLE_FILES 151, RUNTIME_DATA_NO_OVERVIEW 137 (`runtime_data_verdict` 934-962; check its other users first), OVERVIEW_HUB_UNDER_V6 4152. The GATE_DENY_CAP text at 190-194 mentions locate.
- **State keys:** `locate_first_deny`, `overview_locate_blocked`, `overview_locate_example_sent`; deny_cap buckets `overview_locate` and `overview_unmapped`; record fields `last_deny`, `card_pending`, `goal_node`, `goal_tree`, `goal_reset_turn`, `located_quality`.
- **Config:**
  - `lib/hub_config.py:98` `RETIRED_KEYS=("dry_run","deny_parts")` — these are the pre-v6 keys; reverting means un-retiring them with `dry_run` defaulting to true.
  - `min_overview_evidence` (line 45) is v6.
  - `workflow/config.json:643` `_doc` describes blocking.
- **Handler:** `hooks/handlers/pre_tool_use.py` 2194-2313. Lines 2222-2241 in that block are need_goal `set_via_text` / `edit_gate` (row 8) and must stay. `_pre_v6_hub_warn` 1870-1889 is called at 2198.

**Row 11:** RULES 253, 261, CHOICE_REASON_BELONGS_TO_CHOICE 266, 279. Code at `wg_release_rules.py` 1659-1843; keep `edited_part_goal_verdict` 1844-1860 (that's f3). `wg_overview._goal_line_check` 1381-1410 (deny_cap `two_candidates`, guard event `locate_soft`) and `_locate_example` 1413-1424. `lib/overview_hub.py` 29-32 (目標/批判 added to `LOCATE_RE`, `GOAL_NODE_PLACEHOLDER`). Entrypoint E01.

**Row 12:** RULES LOCATE_LINES_NEED_CRITIQUE 274; `CRITIQUE_MIN_CHARS` / `locate_critique_verdict` 1814-1831. `wg_overview.py` 391-406 (`CRITIQUE_LINE_HINT` / `_SHORT`). `lib/overview_hub.CRITIQUE_TEMPLATE` line 34. Entrypoint E02.

**Row 18:** the literal "保險做法" sentence is already gone; `hooks/verify/verify_gate_trim.py:179-181` asserts it is absent. What's left is the "put it in a `#` comment" wording (`DECL_WHERE`) inside the locate messages: `wg_overview.py` 1157, 1487, 1651, 1883, 2005, 2176-2178, 2193. The constants `DECL_WHERE`, `DECL_WHERE_SHORT`, `DECL_KEEP_EDIT` (`wg_release_rules.py` 2936-2943) and rule DECL_HINT_KEEPS_EDIT_TOOLS (2924) are shared with kept gates (DataFile, OldTest, tree-set), so keep them.

**Row 19:**
- Tree summary: `_goal_block` 409-428, called from `_card_text` 528.
- The two extra root-cause questions: `_CANDIDATE_QUESTIONS` 90-91 (used at 778) and `lib/overview_hub.ROOT_CAUSE_SENTENCE` 92 (used at 655 and 698).
- Read path: `on_read` 1025-1073 (card-deferral at 1061-1065); `hooks/handlers/post_tool_use.py:1472` tool list (v6 adds PowerShell and Grep); `_goal_view` 921-940 (GOAL_VIEW_ONE_LINE 3964, shared with row 13).

**PostToolUse "改【X】的程式檔前…再交定位四行" reminder:** `_locate_read_hint` 1112-1143 and `locate_read_hint` 1146-1158, called at 1054 and 1070. State `overview_locate_hint_sent` (1076) and `rec.locate_hint`. Rule LOCATE_HINT_ON_FIRST_READ 4058-4066; item ③ of NON_CODING_TURN_NO_NUDGE (4270-4271) refers to it.

**Row 28:**
- `wg_overview.py` 1481-1655: `MIN_MAP_ENTRY`, `_PREVIEW_CODE`, `_min_map_due`, `_min_map_check`, `_min_map_preview`, `_min_map_lines`. `_session_reads` and `_transcript_self_error` in that range are also used by other code.
- Hint in `_unmapped_read_hint` 1105-1108.
- RULES block 3346-3423.
- State `min_map` and `rec.min_map_done` / `min_map_via`.
- Config `overview_hub.min_map` (`config.json` 634-638; `hub_config.py` 90 and 250-260). Entrypoint E03.

**Row 1 – judgment-card delivery:**
- **Whole files:** `hooks/wg_entrypoint.py`, `workflow/entrypoints.json`, `tools/entry-stats.py`.
- **Runtime leftovers:** `workflow/entry-sent/` (`.gitignore:74`; cleanup table `hooks/handlers/_shared.py` 343-344); `Logs/guard-entry.jsonl`.
- **Config:** `wg_core.DEFAULTS["entrypoint"]` 164-167; `config.json` 589-593.
- **Rules and tools:** CARD_FULL_ONCE_PER_SESSION 3974-3977; docstring 472; `tools/health-weekly.py` 521-526.
- **`Entry:` field:**
  - `lib/atom_spec.py` 66-67, 206, 231, 633-681
  - `lib/atom_index_json.py` 8-15, 212-267
  - `lib/atom_io.py` 91, 595-677, 942-1044, 1234, 1658-1723 (`realm_hold`)
  - `lib/atom_io_cli.py` 254-261; `lib/atom_locations.py` 275-293 (`ENTRY_BOUND_STAYS_CORE`, `entry_bound_ids`)
  - `hooks/wg_atoms.py` 63-73, 2961-3015
  - `tools/sync-atom-index.py` 80, 93, 213, 232, 338-353, 424-434; `tools/atom-categorize.py:356`
  - MCP: `lib/mcp.js` 185-187 and 321-323; `lib/atom-tools.js` 64-67, 126-127, 202, 219, 392, 566-567, 914, 957-975; `lib/atom-render.js` 62, 95-97

**Row 33:** `hooks/wg_judge_card.py` whole file (it already only logs; `gate()` always returns None). `pre_tool_use.py` line 34, 1932-1939 (MCP branch), 2069-2073. RULES block 3245-3305, but `_JUDGE_CARD_ASCII_SEP_RE` (3261) is also used by `parse_negative_controls` (1221) — keep it, ideally renamed. `Logs/guard-judge_card.jsonl`; config `guard.judge_card_declare` (default value only); `settings.json:111` matcher entries for atom_write, atom_edit_meta and atom_retire exist only for this gate.

## 2. Tests
- **Delete whole file:**
  - `hooks/verify/verify_judge_card_declare.py` plus `fixtures/gate006/c1_judge_card_events.json`
  - `hooks/verify/verify_g14_min_map.py`, `verify_locate_hint.py`, `probe_c_g0.py`
  - `tools/verify/verify_entrypoint_contract.py`, `verify_entry_stats_asks.py`
  - Only if the need_goal `locate` field goes: `verify_locate_via_need_goal.py`, `verify_pull_goal_locate.py` (24 tests, mostly locate), MCP `verify/verify_need_goal_locate.js`
  - Only if `Entry` goes: MCP `verify/verify_atom_write_entry.js`
- **Partial edits:**
  - `verify_overview_hub.py`: 122 tests, about 66 touch v6 parts. A 9e476fd0 version exists as a baseline.
  - `verify_gate_mode_pre.py`: test_first_edit_without_tree_denied_once_then_reminded, test_tree_hint_once_per_session, test_locate_reminded_on_read_then_first_edit_denied_once, test_locate_remind_once_per_part, test_card_injected_after_edit_denied_once_card_follows, test_locate_first_round_blocks_parallel_edits_until_declared, test_unmapped_reminded_once_per_top; plus the OVERVIEW_HUB_UNDER_V6 block at 406-410.
  - `verify_gate_mode_stop.py`: test_reminders_ask_judgment_cards_once_per_batch, test_remind_sent_list_from_locate_hint_does_not_crash_and_sends.
  - `verify_gate_slimming.py`: the 6 card tests.
  - `verify_gate_trim.py`: test_two_candidates_asked_once_goal_node_only_logged, test_locate_lines_not_duplicated_into_tool_args, test_judge_card_change_logged_not_blocked, test_selfscore_not_an_entrypoint_and_lives_in_console_skill; also the patches at 233 and 277.
  - `verify_cost_cut.py`: the 3 `test_locate_*` tests.
  - `verify_need_goal.py`: test_004_locate_example…, test_cg0_locate_two_candidates…, test_cg1_locate_needs_critique_line, test_cg0_one_candidate…, test_cg0_relink_* (f3).
  - `verify_release_rules.py`: test_cg0/cg1_locate_*, test_004/005/007_*, test_g14_unmapped_first_edit_needs_min_map, test_006_judge_card…, test_locate_hint_rule_registered_with_case, test_overview_hub_under_v6_rule_registered, test_locate_first_edit_blocks_once_rule_registered; the rule lists in test_044_every_rule_has_a_case and test_pre_gate_remind_rules_registered_with_mode.
  - `verify_entry_wording.py`: drop the registry assertions at 36-40.
  - `verify_g6_rules_to_llm.py`: test_question_moment_logs_guard_entry_for_each_new_entry.
  - Patch lines only: `verify_text_score_stop.py` 38 and 82; `verify_chain_wiring.py` 413.
  - Smaller hits: `verify_overview_card_pointer.py`, `verify_card_injection_slim.py`, `verify_candidates_trigger.py` (the two questions), `verify_dir_target_root.py`, `verify_pre_tool_use_overview_gate.py`, `verify_pull_tool_gates.py` (test_interpreter_bash_takes_no_judge_card_snapshot), `verify_realm_sweep.py` (`ENTRY_BOUND_STAYS_CORE`), `verify_need_goal_points.py` (test_cg1_regard_prompts…, shared with row 13), `skills/console/verify/verify_selfscore.py`.

## 3. Docs (DevHistory excluded)
- **`TECH.md`:**
  - TOC 77; §4.1 363 and 437-458; 905
  - §7.0 切入點 1274-1278; §7.5 1457 and 1620; §7.6 1490-1534; §7.7 1560
  - §7.10 1634-1666 (whole section)
  - 2132, 2512-2526, 2812, 2922-2929, 3409, 3519-3528 (閘：Entry), 4051, 4313-4318
- **`TECH/guards.md`:** ③ 動手前定位 112-144; 切入點（完整）231-236; JudgeCardDeclare 1313-1341; A7.6 1573-1704 (最小地圖 1625, 寫入閘 1633-1674); locate field 1916-1924; 第二層：定位行 2038-2064; A7.10 2203-2403 (whole).
- **`TECH/release-rules.md`:** index line 36; sections 866-1010, 1327, 1454-1460, 1655-1683, 1794-1860, 1908, 1976-1988, 2046-2145.
- **Other TECH files:** `TECH/config.md` 124, 133-134, 302. `TECH/file-tree.md` 143, 154, 165, 203, 339, 491.
- **`_AIDocs`, README, config docs:** `_AIDocs/Architecture.md:36`; `README.md:38`; `workflow/config.json` `_doc` strings at 590 and 643; `_AIDocs/_CHANGELOG.md` is history (add an entry, don't rewrite).
- **Skills and templates:** no `.md` hits; only `skills/console/scripts/selfscore.py` code.

## 4. Entanglements with kept features
1. **The reminder ledger in `wg_overview.py` 1241-1343** (`remind_hit`, `remind_mark`, `remind_once`, `remind_queue`, `remind_flush`) is used by kept gates via `post_tool_batch.py:122`, `post_tool_use.py:2001`, `pre_tool_use.py` 1671, 1817, 1822, 2186, 2237. Keep it, or move it to its own module.
2. **Kept code imports other `wg_overview` helpers:**
   - `_cfg` — `stop.py:1442` equivalence, `wg_depends.py:19` (row 48), `wg_need_goal.py:313`, `post_compact.py:111`, svn test gate `pre_tool_use.py:1451`
   - `read_targets` — `wg_data_file.py:208`, `wg_need_goal_points.py`
   - `_lookup` — `stop.py:1011`
   - `_intent_of`
   - `_hub_part` — chain breaker, `pre_tool_use.py` 1752-1771; it reports parts blocked by the locate gate, so simplify it once that gate is gone
3. **f3 (EDITED_PART_NEEDS_GOAL_NODE)** gets its facts from the 4th locate line: rule 282, `stop.py` 1051-1068, `wg_need_goal.py` 1788 and 2157 (`relink_parts`, `wg_overview.py` 448-479, calls `_goal_line_check`). So does the need_goal `locate` field (`wg_need_goal.py` 803-835 and 876-887, `post_tool_use.py` 1088-1091, MCP `need-goal.js` 64-73 and 111, `mcp.js` 540 and 553). Smallest change: `relink_parts` only resolves the node and drops the role / two-candidate / critique checks.
4. **Shared with row 13:** `CRITIQUE_CASES`, `critique_once`, `critique_mark` (`wg_need_goal.py` 105-109, 627-666) are also used by `wg_need_goal_points.py` 109-114, 256, 570, 630 — remove only the `wg_overview` users. `on_goal_changed` (482-498, called from `post_tool_use.py` 1085 and 1143) only resets v6 locate state.
5. **Shared with negative control (row 41):** `LOCATE_CHANNELS` / `assistant_text_after` (`lib/overview_hub.py` 752-790) are used by `post_tool_use.py` 1262-1266 — keep.
6. **PreToolUse MCP branch (1932-1939):** if you just delete it, atom_write, atom_edit_meta and atom_retire fall through the whole PreToolUse path. Either return `output_nothing()` early or remove those three from the `settings.json:111` matcher.
7. **`ENTRY_BOUND_STAYS_CORE` (realm hold):** removing it lets the SessionEnd realm sweep move the 34 Entry-bound cards to local.
8. **`skills/console/scripts/selfscore.py:38`** uses `ep.MEMORY_DIR` and `ep._knowledge` (58, 67) — needs its own helper.
9. **`post_compact.py` 106-160:** the reinjection text says "定位三行已交否" — reword if locate changes.

## 5. Card call sites to cut
- `hooks/handlers/_shared.py` 77-90 (import shim), 343-344.
- `pre_tool_use.py`: `_with_cards` 1646-1652, used by `_deny` 1702, the ask hint 1865, the warnings 2334; subagent prompt 1964-1970.
- `post_tool_use.py`: 75, 2077-2082 (MCP reply).
- `post_tool_batch.py`: 162 and `_remind_cards` 166-175 — this is the "ask once per batch" path that kept reminders (second opinion, turn judgment, equivalence, hot path, min map) go through.
- `stop.py`: 93-94; 1166-1169 (subagent block); `_piggyback` 1856 and 1877; 2411; 2966-2968.
- `ups_gates.py` 23 and 274 (E39); `user_prompt_submit.py` 312-315 (E38).
- `wg_closing_round.py` 16, 37, `_note` 73-76 and its callers 111, 290 — return plain text.
- `pre_compact.py` 43-44 (`forget_sent`); `health-weekly.py` 521-526.

## 6. Atoms
- **Entry-bound cards:** `grep -rlE "^- Entry: *\S" memory _AIDocs/_atoms --include=*.md` gives 34 files. 45 files have an `Entry:` line, 11 of them empty (for example g0/g1/g11-評分規格). `memory/_atom_index.json` has 34 entries with an `entry` key.
- **E01–E03 (lose their trigger; content can stay as plain knowledge):** 根因候選要跨層找…, 批判這段寫法時先抓兩種不合理…, feedback-現有程式只證明現況不證明應然…, 最小地圖的上下游要寫….
- **Content about the mechanism itself becomes dead:**
  - `_AIDocs/_atoms/MemDev/寫碼守門閘/`: 切入點帳guard-entry…, 判準卡在對的時刻送出…, 定位閘的掃描起點…
  - `_AIDocs/_atoms/MemDev/檢索排序與注入量測/`: 判準卡entry綁定一張卡只綁主代號…, 同一切入點綁兩張以上判準卡…
  - `_AIDocs/_atoms/MemDev/` other: atom工具與索引/解除entry綁定的卡…, 架構決策與規則檔/原子記憶是llm切入點的調校層…, 擋訊息與放行判定/userpromptsubmit路的判斷入口形狀… (partly), _distant/2026_10/無頭驗收受測ai會改…判準卡…
  - `memory/CC與原子記憶契約/切入點識別字樣含常見中文詞…`
- **Broader triage:** grepping `判準卡|切入點|entry_note|定位｜|定位四行|最小地圖|LOCATE_|JudgeCard` hits 128 atom files, most about kept features. Project `_AIAtoms` and org layers were not scanned.

## 7. Uncertainties
1. **OverviewHub with the guard off is off entirely.** Commit f3871137 made `_cfg` set `enabled = enabled and v6` (`wg_overview.py:153`, rule OVERVIEW_HUB_UNDER_V6), so `_pre_v6_hub_warn` and the guard-off `on_read` are effectively dead. Decide whether "revert to pre-v6" means guard-on falls back to dry-run warnings, or guard-off also gets the dry-run back. Either way `_cfg` gating also switches `wg_depends` and the need_goal read paths.
2. **Row 19 "inject on Read":** the 9e476fd0 code handled Read, but its PostToolUse matcher (`dispatcher.py` `PRE_V6_TOOLS` 69-73) had no Read, so pre-v6 effectively injected only on Bash reads. The current code already defers the card to the first edit, so "keep pre-v6" here is ambiguous.
3. **Row 18** is already done in its literal form; removing the remaining `# comment` wording only applies to the locate messages.
4. **f3 and the need_goal `locate` field** aren't in your list but depend on locate lines; their owner group needs to decide.
5. **Fully dropping `Entry:`** touches the atom format, the index sync and MCP schemas, and leaves 45 inert `- Entry:` lines unless they're stripped.
6. **Row 33 is already log-only.** The inventory's "blocks the next call" is stale, and before v6 the dispatcher never routed MCP tools to PreToolUse.

A broad read-only grep I started in the background may still be running; it writes nothing.