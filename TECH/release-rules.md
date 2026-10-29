# 放行／欠帳判定規則全表（TECH §7.8）
[↑ 主文 §7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy)

## 規則索引

- **[檔案與回合的基礎判定](#檔案與回合的基礎判定)**：[SAME_FILE](#same_file)・[TURN_SINCE_USER_PROMPT](#turn_since_user_prompt)・[CODING_TURN_ONLY](#coding_turn_only)・[GATE_MODE_TABLE／REMIND_ON_PRIOR_RESULT（RULE_MODE）](#gate_mode_tableremind_on_prior_resultrule_mode)
- **[宣稱詞、糾正詞與其他「詞表只是提示」的判斷入口](#宣稱詞糾正詞與其他詞表只是提示的判斷入口)**：[CLAIM_MODIFIER_NOT_OWN](#claim_modifier_not_own)・[CLAIM_FIXED_NEEDS_PASS／CLAIM_MEASURED_NEEDS_DONE／CLAIM_TRIED_NEEDS_EXEC](#claim_fixed_needs_passclaim_measured_needs_doneclaim_tried_needs_exec)・[CLAIM_WORDS_ARE_HINTS／CLAIM_DISCLAIM_NEEDS_REASON／CLAIM_RECEIPT_REF_MATCH](#claim_words_are_hintsclaim_disclaim_needs_reasonclaim_receipt_ref_match)・[CLAIM_CONDITIONAL_NOT_CLAIM](#claim_conditional_not_claim)・[CORRECTION_WORDS_ARE_HINTS](#correction_words_are_hints)・[EXTRACT_VETO_NEEDS_JUDGMENT](#extract_veto_needs_judgment)・[收割與收尾檢核的 dismiss](#收割與收尾檢核的-dismiss)・[CONFLICT_DECLARED_BY_AI](#conflict_declared_by_ai)・[PROJECT_LITERAL_IS_HINT](#project_literal_is_hint)・[PROJECT_RULE_WORDS_ARE_HINTS](#project_rule_words_are_hints)
- **[退避例外與紅測豁免](#退避例外與紅測豁免)**：[NOT_DOING_DECLARED／USER_WAIVER_NEEDS_CITATION](#not_doing_declareduser_waiver_needs_citation)・[BASE_RED_TRACKED_NOT_OWED](#base_red_tracked_not_owed)・[RED_ITEMS_ONLY_FROM_FAILURE_LINES](#red_items_only_from_failure_lines)
- **[收尾儀式與寫碼查核案例](#收尾儀式與寫碼查核案例)**：[RECONCILE_BLOCK_LETTERS](#reconcile_block_letters)・[CLOSING_RITUAL_SWITCHES](#closing_ritual_switches)・[CASE_DECLARED_FOR_CHANGE](#case_declared_for_change)・[NO_CASE_NEEDS_USER](#no_case_needs_user)・[CASE_COVERS_CHANGE](#case_covers_change)
- **[已不存在、還原與等同的改檔](#已不存在還原與等同的改檔)**：[GONE_OUTSIDE_VCS／GONE_IN_GIT_NOTHING_NEW](#gone_outside_vcsgone_in_git_nothing_new)・[MOVED_NEW_CODE_SEEN／GONE_UNVERIFIABLE／VCS_ROOT_UNREADABLE](#moved_new_code_seengone_unverifiablevcs_root_unreadable)・[EXCLUDED_REGION](#excluded_region)・[NET_UNCHANGED／SNAPSHOT_SETTLED](#net_unchangedsnapshot_settled)・[EXEMPTION_PEERS_CODE_ONLY](#exemption_peers_code_only)・[CONTENT_EQUALS_COMMITTED](#content_equals_committed)・[COMMENT_ONLY_CHANGE](#comment_only_change)
- **[擋次預算與放行](#擋次預算與放行)**：[BLOCK_BUDGET_SHARED](#block_budget_shared)・[PENDING_SAME_USER_TURN／RELEASE_COVERS_SHOWN_ITEMS／NONINTERACTIVE_RELEASE_AT_BUDGET](#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)・[GATE_SELF_ERROR](#gate_self_error)・[GATE_DENY_CAP](#gate_deny_cap)・[DENY_CAP_PER_REPLY](#deny_cap_per_reply)・[PICK_ONCE_PER_USER_TURN](#pick_once_per_user_turn)・[PICK_ONE_PRE_CLOSE／PICK_ONE_WITH_TURN_JUDGMENT](#pick_one_pre_closepick_one_with_turn_judgment)
- **[Bash／PowerShell 指令怎麼讀（寫入目標、唯讀、讀檔證據）](#bashpowershell-指令怎麼讀寫入目標唯讀讀檔證據)**：[INLINE_PY_READONLY](#inline_py_readonly)・[UNKNOWN_WRITE_RECOVERED](#unknown_write_recovered)・[INLINE_FLAG_BEFORE_PROGRAM](#inline_flag_before_program)・[SHELL_LITERAL_VAR_EXPANDED](#shell_literal_var_expanded)・[GIT_READONLY_SUBCMD](#git_readonly_subcmd)・[DOT_GIT_PATH_NOT_GIT_CALL／SEGMENTS_SPLIT_LIKE_SHELL／SHELL_KEYWORD_PREFIX_STRIPPED](#dot_git_path_not_git_callsegments_split_like_shellshell_keyword_prefix_stripped)・[DELETE_FORMS_SAME_ACROSS_SHELLS](#delete_forms_same_across_shells)・[UNKNOWN_PART_KEEPS_KNOWN_TARGETS](#unknown_part_keeps_known_targets)・[DIR_TARGET_JUDGED_BY_CONTAINER](#dir_target_judged_by_container)・[GREP_CONTENT_IS_READ／BASH_COMMENT_LINES_STRIPPED](#grep_content_is_readbash_comment_lines_stripped)・[BASH_READONLY_COUNTS_AS_READ](#bash_readonly_counts_as_read)
- **[同步、綜觀與暫存目錄](#同步綜觀與暫存目錄)**：[WORKTREE_NO_PUSH](#worktree_no_push)・[RUNTIME_DATA_NO_OVERVIEW](#runtime_data_no_overview)・[UNMAPPED_EDIT_NEEDS_READABLE_FILES](#unmapped_edit_needs_readable_files)・[TEMP_REPO_COMMIT_EXEMPT／TEMP_COPY_NOT_PROJECT](#temp_repo_commit_exempttemp_copy_not_project)・[SESSION_SCRATCH_NOT_CODE](#session_scratch_not_code)
- **[紅測與重試](#紅測與重試)**：[RED_WHILE_REVERTED／RETRY_COUNTS_RERUN_CYCLES／GREEN_SAME_CASE_CLEARS](#red_while_revertedretry_counts_rerun_cyclesgreen_same_case_clears)
- **[搬程式目錄](#搬程式目錄)**：[MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE](#move_code_dir_needs_scan_and_sample)
- **[紅測清帳：篩選、範圍與最後結果](#紅測清帳篩選範圍與最後結果)**：[GREEN_NARROWED_KEEPS_UNCOVERED_RED](#green_narrowed_keeps_uncovered_red)・[GREEN_CLEARS_ONLY_CASES_IT_RAN](#green_clears_only_cases_it_ran)・[RED_LAST_RESULT_IN_COMMAND](#red_last_result_in_command)・[RED_SCOPE_FROM_FULL_COMMAND](#red_scope_from_full_command)
- **[目標樹：達成、定位與提問](#目標樹達成定位與提問)**：[GOAL_DONE_NEEDS_CASE_OR_RECEIPT／GOAL_INFERRED_MAX_PARTIAL](#goal_done_needs_case_or_receiptgoal_inferred_max_partial)・[CASE_RED_THEN_GREEN](#case_red_then_green)・[LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES](#locate_lines_need_role_and_two_candidates)・[LOCATE_CANDIDATES_WITHOUT_FIXED_LABELS](#locate_candidates_without_fixed_labels)・[EDITED_PART_NEEDS_GOAL_NODE](#edited_part_needs_goal_node)・[KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE／KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY](#knowledge_edit_needs_light_treeknowledge_tree_reconcile_at_delivery)・[ASK_NEEDS_RECOMMENDATION](#ask_needs_recommendation)・[ASK_LINKED_TO_GOAL](#ask_linked_to_goal)・[ASK_OVERVIEW_BEFORE_DECISION](#ask_overview_before_decision)・[LOCATE_LINES_NEED_CRITIQUE](#locate_lines_need_critique)・[LOCATE_LINES_NO_EXAMPLE_PLACEHOLDER](#locate_lines_no_example_placeholder)
- **[驗證範圍：哪些改檔作廢收據](#驗證範圍哪些改檔作廢收據)**：[SCOPE_EDIT_RELATED_TO_ITEM](#scope_edit_related_to_item)・[SCOPE_CASE_EDIT_ONLY_ITS_ITEM](#scope_case_edit_only_its_item)・[SCOPE_EDIT_IN_DECLARED_DEPENDS](#scope_edit_in_declared_depends)・[SCOPE_RED_ONLY_ITS_CASES](#scope_red_only_its_cases)
- **[Stop 底部的同步擋（sync block）](#stop-底部的同步擋sync-block)**：[SYNC_BLOCK_SKIPS_SYNCED](#sync_block_skips_synced)・[SYNC_SKIPS_VANISHED_OUTSIDE_VCS](#sync_skips_vanished_outside_vcs)・[BLOCK_LISTS_LATER_GATES](#block_lists_later_gates)・[PROMPT_REOPENS_DONE](#prompt_reopens_done)・[SYNC_BLOCK_NEW_ITEMS_ONLY](#sync_block_new_items_only)
- **[驗證範圍宣告](#驗證範圍宣告)**：[SCOPE_DECLARED_FOR_CHANGE](#scope_declared_for_change)・[SCOPE_ITEM_WELL_FORMED](#scope_item_well_formed)
- **[案例宣告與收據證據](#案例宣告與收據證據)**：[CASE_DECL_WELL_FORMED](#case_decl_well_formed)・[SCOPE_ITEM_RECEIPT_AFTER_EDIT](#scope_item_receipt_after_edit)・[RECEIPT_UNPARSED_GENERAL_ONLY](#receipt_unparsed_general_only)・[CARRIED_CLAIM_ANY_TURN_RECEIPT](#carried_claim_any_turn_receipt)・[LAUNCHER_NOT_CODE](#launcher_not_code)
- **[收尾提醒與自清](#收尾提醒與自清)**：[RELOAD_ADVICE_ALREADY_LOADED／RELOAD_ADVICE_MCP_EDITS_ONLY](#reload_advice_already_loadedreload_advice_mcp_edits_only)・[LEFTOVER_NEEDS_CLEANUP](#leftover_needs_cleanup)
- **[退避偵測](#退避偵測)**：[EVASION_CONTEXT_EXEMPT](#evasion_context_exempt)・[DEFERRAL_COVERS_EVASION_SENTENCE](#deferral_covers_evasion_sentence)
- **[第二意見](#第二意見)**：[SECOND_OPINION_REQUIRED](#second_opinion_required)・[SECOND_OPINION_RAN_BEFORE](#second_opinion_ran_before)・[SECOND_OPINION_RESULT_ACROSS_TURNS](#second_opinion_result_across_turns)・[SECOND_OPINION_WAITING_NOT_DONE](#second_opinion_waiting_not_done)・[SECOND_OPINION_BACKGROUND／SECOND_OPINION_DONE_NOTICE](#second_opinion_backgroundsecond_opinion_done_notice)・[SECOND_OPINION_DECLINED／SECOND_OPINION_DECLINE_ACCEPTED](#second_opinion_declinedsecond_opinion_decline_accepted)・[SECOND_OPINION_DECLARED_ALWAYS_LOGGED](#second_opinion_declared_always_logged)・[SECOND_OPINION_FACT_TRIGGER](#second_opinion_fact_trigger)・[SECOND_OPINION_EXIT_FINGERPRINT](#second_opinion_exit_fingerprint)・[SECOND_OPINION_PRE_CLOSE](#second_opinion_pre_close)
- **[最小地圖與拐彎判斷](#最小地圖與拐彎判斷)**：[UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP](#unmapped_first_edit_needs_min_map)・[TURN_JUDGMENT_REQUIRED](#turn_judgment_required)・[READING_PATH_EARLY_START／TURN_JUDGMENT_PRE_CLOSE](#reading_path_early_startturn_judgment_pre_close)
- **[重構等值與效能](#重構等值與效能)**：[REFACTOR_NEEDS_EQUIVALENCE](#refactor_needs_equivalence)・[PERF_HOT_PATH_NEEDS_MEASURE](#perf_hot_path_needs_measure)・[EQUIVALENCE_LOOP_EXPANDED](#equivalence_loop_expanded)・[EQUIVALENCE_NA_DECLARED_ALWAYS_LOGGED](#equivalence_na_declared_always_logged)・[NEGATIVE_CONTROL_DECLARED](#negative_control_declared)
- **[Bash 讀檔判定](#bash-讀檔判定)**：[BASH_UNREACHED_READ_NOT_COUNTED](#bash_unreached_read_not_counted)
- **[判準卡、口令閘與驗證批次](#判準卡口令閘與驗證批次)**：[JUDGE_CARD_HASH_CATCHES_INTERPRETER](#judge_card_hash_catches_interpreter)・[COMMIT_ORDER_DECISION_ALWAYS_LOGGED](#commit_order_decision_always_logged)・[VERIFY_FULL_RUN_NEEDS_USER_ORDER／VERIFY_SAME_BATCH_ALREADY_GREEN／VERIFY_BATCH_BLOCK_ONCE_PER_TURN](#verify_full_run_needs_user_orderverify_same_batch_already_greenverify_batch_block_once_per_turn)・[ORDER_UNTIL_PUSH](#order_until_push)・[SVN_TEST_BLOCK_OPT_IN](#svn_test_block_opt_in)
- **[點名判定與漏判記錄](#點名判定與漏判記錄)**：[NEGATED_MENTION_IS_NOT_NAMING／DATA_FILE_DECL_VOIDED_BY_LATER_MENTION](#negated_mention_is_not_namingdata_file_decl_voided_by_later_mention)・[CHOICE_REASON_BELONGS_TO_CHOICE](#choice_reason_belongs_to_choice)・[OWN_COMMIT_CHANGES_STILL_COMPARED](#own_commit_changes_still_compared)・[SCOPE_LEAK_OUTSIDE_SCOPE](#scope_leak_outside_scope)・[SCOPE_LEAK_REVIEW_BEFORE_DECLARE](#scope_leak_review_before_declare)
- **[收尾檢核欄位](#收尾檢核欄位)**：[AEC_EVIDENCE_PATH](#aec_evidence_path)・[AEC_FOLLOWUPS_EMPTY](#aec_followups_empty)
- **[宣告類閘與追蹤帳](#宣告類閘與追蹤帳)**：[USER_DATA_FILE_NEEDS_DECLARATION](#user_data_file_needs_declaration)・[DECL_HINT_KEEPS_EDIT_TOOLS](#decl_hint_keeps_edit_tools)・[ORIGIN_USER_NEEDS_QUOTE](#origin_user_needs_quote)・[ORIGIN_SAID_INCLUDES_UNATTACHED](#origin_said_includes_unattached)・[OLD_TEST_CHANGE_NEEDS_DECLARATION](#old_test_change_needs_declaration)・[GATE_BYPASS_NEEDS_DECLARATION／GATE_BYPASS_NAMED_FILES_MERGED](#gate_bypass_needs_declarationgate_bypass_named_files_merged)・[ATOM_BYPASS_HOWTO_REFUSED](#atom_bypass_howto_refused)・[JUDGE_CARD_CHANGE_NEEDS_DECLARATION](#judge_card_change_needs_declaration)・[TRACKING_SAME_ITEM_NOT_REWRITTEN](#tracking_same_item_not_rewritten)
- **[連鎖斷路器與 state 鎖](#連鎖斷路器與-state-鎖)**：[CHAIN_SAME_GATE_PER_OBJECT](#chain_same_gate_per_object)・[STATE_RMW_LOCKED／STATE_PENDING_MERGED](#state_rmw_lockedstate_pending_merged)・[OLD_TEST_COMPARED_ON_FAILED_COMMAND](#old_test_compared_on_failed_command)
- **[回合、完成宣告與用字](#回合完成宣告與用字)**：[USER_TURN_KEY_KEPT](#user_turn_key_kept)・[COMPLETION_CLAIM_PER_SENTENCE](#completion_claim_per_sentence)・[OPENING_NOTICE_NOT_TODO](#opening_notice_not_todo)・[GATE_TEXT_AVOIDS_EVASION_WORDS](#gate_text_avoids_evasion_words)・[SUBPROCESS_RUN_LOOKED_UP_AT_CALL](#subprocess_run_looked_up_at_call)・[CHAIN_HEADLESS_KEEPS_DATA_GATES](#chain_headless_keeps_data_gates)
- **[讀檔證據](#讀檔證據)**：[SHELL_READ_COUNTS_LIKE_READ](#shell_read_counts_like_read)・[INJECT_TRIGGER_READ_COUNTED](#inject_trigger_read_counted)
- **[定位閘與擋訊息版面](#定位閘與擋訊息版面)**：[LOCATE_FIRST_EDIT_BLOCKS_ONCE](#locate_first_edit_blocks_once)・[LOCATE_BLOCK_ONCE_PER_USER_TURN](#locate_block_once_per_user_turn)・[LOCATE_NOT_IN_THINKING](#locate_not_in_thinking)・[GOAL_VIEW_ONE_LINE](#goal_view_one_line)・[LOCATE_EXAMPLE_ONCE_PER_SESSION](#locate_example_once_per_session)・[CARD_READ_WITH_EDIT_FILES](#card_read_with_edit_files)
- **[寫檔判定與連鎖斷路器](#寫檔判定與連鎖斷路器)**：[SHELL_WRITE_COMMAND_NOT_A_READ](#shell_write_command_not_a_read)・[EPHEMERAL_WRITE_NOTED_ONCE](#ephemeral_write_noted_once)・[CHAIN_NO_EDIT_NO_EDGE](#chain_no_edit_no_edge)・[CHAIN_ABORT_SHOWS_REPLACED_BLOCK](#chain_abort_shows_replaced_block)
- **[提示、回填與收尾組裝](#提示回填與收尾組裝)**：[QUOTE_FROM_USER_OPENED_TURN](#quote_from_user_opened_turn)・[CRITIQUE_CASES_ONCE_PER_SESSION](#critique_cases_once_per_session)・[TREE_LINE_IN_HINTS](#tree_line_in_hints)・[CODING_TURN_FULL_ONLY_ON_TRIGGER](#coding_turn_full_only_on_trigger)・[POINTER_NO_NAME_ECHO](#pointer_no_name_echo)・[NO_RESEND_AFTER_RESUME](#no_resend_after_resume)・[DENY_TEXT_SLIM](#deny_text_slim)・[CARD_FULL_ONCE_PER_SESSION](#card_full_once_per_session)・[DATA_FILE_READ_HINT](#data_file_read_hint)・[CLOSING_RECONCILE_IN_REPORT](#closing_reconcile_in_report)・[CLOSING_MISSING_PART_HINT](#closing_missing_part_hint)・[CLOSING_GOAL_CODING_ONLY](#closing_goal_coding_only)・[CLOSING_CALL_ALL_THREE](#closing_call_all_three)・[LOCATE_HINT_ON_FIRST_READ](#locate_hint_on_first_read)
- **[各閘的閘級規則（照程式 RULES 原文）](#各閘的閘級規則照程式-rules-原文)**：[COMMIT_SMELL_NEW_BLOCKS](#commit_smell_new_blocks)・[RED_TEST_BLOCKS_COMPLETION](#red_test_blocks_completion)・[CODE_EDIT_NEEDS_GOAL_TREE](#code_edit_needs_goal_tree)・[OVERVIEW_CARD_BEFORE_EDIT](#overview_card_before_edit)・[OVERVIEW_CARD_MISSING](#overview_card_missing)・[OVERVIEW_PART_FILES_READ](#overview_part_files_read)・[COMMIT_GOAL_RECONCILED](#commit_goal_reconciled)・[DEFERRAL_OF_DOABLE_WORK](#deferral_of_doable_work)・[HARVEST_AT_PHASE_DONE](#harvest_at_phase_done)・[HARVEST_ITEM_NEEDS_RECEIPT](#harvest_item_needs_receipt)・[CLOSING_CHECK_REQUIRED](#closing_check_required)・[CLOSING_CHECK_MEMORY_NOT_DEFERRED](#closing_check_memory_not_deferred)・[SYNC_REMINDER_UNSYNCED](#sync_reminder_unsynced)・[SYNC_BLOCK_PENDING_ITEMS](#sync_block_pending_items)・[DEEP_POSTMORTEM_ON_FAILURE](#deep_postmortem_on_failure)・[ATOM_CONSUMPTION_AUDIT](#atom_consumption_audit)・[EVASION_FLAG_NEXT_PROMPT](#evasion_flag_next_prompt)・[LOCATE_BEFORE_EDIT](#locate_before_edit)・[OVERVIEW_READONLY_PATHS](#overview_readonly_paths)・[OVERVIEW_HUB_UNDER_V6](#overview_hub_under_v6)・[REMIND_PENDING_IN_STATE](#remind_pending_in_state)・[GOAL_RECONCILE_AT_DELIVERY](#goal_reconcile_at_delivery)・[GOAL_TREE_SET_ONCE](#goal_tree_set_once)・[STOP_REMIND_LEDGER_ONLY](#stop_remind_ledger_only)・[NON_CODING_TURN_NO_NUDGE](#non_coding_turn_no_nudge)・[TREE_SET_VIA_TEXT](#tree_set_via_text)


## 怎麼讀這份表

- **規則**：每一種放行或欠帳情境一條有名字的規則。
  - `RULES` 現有 217 條，每條的名字都出現在本檔某個區塊標題。
  - 相關的幾條併成一個區塊，標題用「／」隔開。
  - 新增規則時，本檔同步補一個區塊。
- **案例檔**：每條規則一個會紅的案例，放在 [`hooks/verify/verify_release_rules.py`](../hooks/verify/verify_release_rules.py)。
  - 端到端案例在各閘自己的 verify 檔。
- **探針**：真 hook 入口探針是 [`hooks/verify/probe_release_rules.py`](../hooks/verify/probe_release_rules.py)。
- **分工**：呼叫端只蒐集事實（state、transcript、git、檔案內容），交給 [`hooks/wg_release_rules.py`](../hooks/wg_release_rules.py) 判，不自己加例外。
  - 不准用「整輪不擋」或「放寬」當解法。
- **暫存規則開關**：測試或探針把假專案建在系統暫存目錄時，用環境變數 `WG_TEMP_RULES=off` 關掉兩條暫存規則。
- **每個區塊的四個面向**：
  - 標題＝規則名。
  - **判什麼**＝這條規則在判哪件事。
  - **不欠／放行**＝符合哪些條件就不欠帳或放行。
  - **照欠／照擋**＝哪些情況照欠帳或照擋；`—` 表示沒有這一面。

### 檔案與回合的基礎判定

#### SAME_FILE
**判什麼**：同一個檔的不同寫法
- **不欠／放行**：反斜線／正斜線、大小寫、`..` 消掉後相同 → 同一個檔
- **照欠／照擋**：—

#### TURN_SINCE_USER_PROMPT
**判什麼**：「本回合」的窗口
- **不欠／放行**：
  - 使用者打字開回合，到現在為止。
  - 這些全吃這個窗口：擋次預算、ScanReport 豁免、AtomAudit、PASS 窗口、退避預告切點、有用度學習單位、收割冷卻（`user_turn_count`）。
- **照欠／照擋**：
  - 跨 session 訊息（不論內文寫什麼）不開回合。
  - 背景通知不開回合。
  - Claude Code 注入的 Stop hook 擋訊息（user 紀錄「Stop hook feedback:…」）不開回合。
  - 同伴訊息不是使用者原話，口令不認。

#### CODING_TURN_ONLY
**判什麼**：寫碼守門每回合的檢查要不要跑（`wg_core.coding_turn`）
- **不欠／放行**：
  - 這個使用者回合已經改了程式檔（`wg_need_goal.writes_code`）、或有判不出目標的寫入、或本回合 need_goal 宣告了寫碼樹 → 要跑。
  - 要跑的檢查：目標樹提示、目標視角重看、退避偵測、退縮閘、收尾檢核、文字評分、閱讀路徑、hook 計時帳。
- **照欠／照擋**：
  - 純問答、只改文件的回合不跑（記憶注入、導讀卡、收割照舊每回合）。
  - prompt 的關鍵字意圖不當開關，只送一行「要改碼先立樹」。
  - `coding_guard.coding_turn_only=false` 退回每回合都跑。

#### GATE_MODE_TABLE／REMIND_ON_PRIOR_RESULT（`RULE_MODE`）
**判什麼**：寫碼守門每條規則照擋還是提醒
- 補充：`RULE_MODE` 由 `RULE_CLASS` 算出；`gate_mode(rule, v6)` 是呼叫端唯一入口；見 [§7](../TECH.md#7-守門與收尾) 開頭「擋或提醒」。
- **不欠／放行**：
  - 不在 `RULE_CLASS` 三類（病形／宣告／紅測）的寫碼守門規則 → 提醒。
  - 提醒的做法：
    - 一行（規則名＋現象＋做法）掛在前一個動作的工具結果。
    - 留帳。
    - 同規則同對象同 session 一次。
    - Stop 不續跑、不開放行題。
- **照欠／照擋**：
  - 三類照擋。
  - 標「不在範圍」的安全邊界與表上沒登的規則名照擋。
  - 寫碼守門關一律 block。

### 宣稱詞、糾正詞與其他「詞表只是提示」的判斷入口

#### CLAIM_MODIFIER_NOT_OWN
**判什麼**：宣稱詞是不是自己的
- **不欠／放行**：「修好的 X」是形容詞用法（轉述）
- **照欠／照擋**：「我修好了」照算宣稱

#### CLAIM_FIXED_NEEDS_PASS／CLAIM_MEASURED_NEEDS_DONE／CLAIM_TRIED_NEEDS_EXEC
**判什麼**：(a)(b)(c) 宣稱對帳
- **不欠／放行**：
  - (a) 修好，有驗證範圍宣告時：
    - 範圍內任一項，在跟它有關的最後一次改動之後跑綠。
    - 不看回合、不比檔名。
  - (a) 修好，沒宣告時：
    - 任一回合對得上、晚於每個對上的改檔、同一棵樹的 PASS。
    - 舊回合的收據要之後本 session 沒再改程式檔才算（子代理改的、判不出目標的寫入都算改）。
  - (b)(c)：本回合有 DONE／執行。
- **照欠／照擋**：
  - 收據缺。
  - 收據對不上。
  - 收據跑在改檔之前。
  - PASS 之後又改了程式檔（訊息點名那個檔）。
  - 有宣告時，本回合檔名對得上但不在範圍內的收據不算。

#### CLAIM_WORDS_ARE_HINTS／CLAIM_DISCLAIM_NEEDS_REASON／CLAIM_RECEIPT_REF_MATCH
**判什麼**：宣稱詞表只是提示，語意交 LLM（G6 判斷入口盤點 P6）
- **不欠／放行**：(a)(b)(c) 命中且沒證據時，收尾文字有下列任一種宣稱行 → 放行。
  - 免責行：`宣稱｜修好（量了／試過）：非本回合宣稱，因為 <理由>`
    - 理由拿掉角括號片段後，還有任一字母或數字（任何語言）。
    - 理由沒留著擋訊息的理由範本佔位 `<理由…>`／`<為什麼…>`。
    - 理由裡引用 `<標籤>` 照算。
    - 程式不評理由充不充分（`wg_release_rules.reason_present`，不做行同一支）。
    - 放行時記 guard-reconcile `claim_disclaimed`。
  - 收據引用行：`宣稱｜…：收據 <指令片段或哨兵名>`
    - 指得到本 session 一筆收據。引用必須是那條指令的完整 token：整個 token、檔名、路徑或節點尾段、帶空白的逐字片段，或哨兵名。
    - python／pytest／旗標／純副檔名這類通用字不算指名。
    - 那張收據要過原本的收據資格：指令完整、記了環境、白名單語法、沒寫哨兵字樣、同一棵樹。
    - 修好要合格 PASS、同根、晚於相關改檔。
    - 量了要 DONE，且指令可信或跑了部位量尺。
    - 試過要指令可信的任一筆。
    - 放行時記 `claim_receipt_ref`。
  - 宣稱行從被判的同一串文字找：承接的先前宣稱加最後一則，中段寫過的不必重寫。
  - 條件句與宣稱行本身不算宣稱，見下一個區塊 [CLAIM_CONDITIONAL_NOT_CLAIM](#claim_conditional_not_claim)。
- **照欠／照擋**：
  - 沒宣稱行 → 照原規則擋（擋訊息附寫法）。
  - 理由空、純標點或佔位。
  - 引用是通用字或檔名的一截。
  - 指的收據找不到、不合格、紅、早於改檔。
  - 結構化的達成＋證據（need_goal 完整對照）仍是正式宣告，不受宣稱行影響。

#### CLAIM_CONDITIONAL_NOT_CLAIM
**判什麼**：講以後的句子算不算宣稱
- 補充：樣式在 [`memory/_meta/forbidden-phrases.json`](../memory/_meta/forbidden-phrases.json) 三類宣稱的 `exclude_patterns`；備用表是 `wg_evasion._conditional_excludes`。
- **不欠／放行**：以下都不算宣稱。
  - 如果／假如／要是／一旦／等到／若（若干除外）…<動詞>
  - 緊貼的「等<動詞>」
  - <動詞>之後／以後…再／一起／才／就／會／要
  - 宣稱行（宣稱｜…）本身是對閘的回答，整行先拿掉再判
- **照欠／照擋**：
  - 子句後段有「了／過」＝已經發生，照算宣稱。
  - 只套修好／量了／試過三類；完成詞（`claims_completion`）是整段粗判、不套。

#### CORRECTION_WORDS_ARE_HINTS
**判什麼**：糾正詞表只是提示（G6 盤點第二節類 1）
- **不欠／放行**：
  - 命中先記待判（state `user_correction_pending`），UPS 問 `[Guardian:Correction]`。
  - Stop 收本回合行首的「糾正｜不是：<理由>」→ 不計、留帳 guard-friction `judged`。
  - 理由判法同 `reason_present`；好幾條以最後一條為準。
- **照欠／照擋**：
  - 「糾正｜是：<理由>」→ 計一次。
  - 到下一則使用者本人打的訊息還沒回 → 不計（詞表不替 AI 判），記 `undeclared` 給健檢抽查。

#### EXTRACT_VETO_NEEDS_JUDGMENT
**判什麼**：「否／不要記」只是提示（盤點 P2 同類）
- **不欠／放行**：
  - 決策萃取寫成卡後，使用者那則有這些字樣，不再整批丟掉通知。
  - 通知照送（附卡的路徑），UPS 問 `[Guardian:ExtractVeto]`。
  - AI 判不是 →「否決記憶｜不是：<理由>」留帳。
- **照欠／照擋**：
  - AI 判是 → 自己 `atom_retire` 撤卡並寫「否決記憶｜是：<理由>」。
  - 沒回 → 記 `undeclared`、不自動撤。

#### 收割與收尾檢核的 dismiss
**判什麼**：收割、收割待補、收尾檢核的使用者豁免
- **不欠／放行**：近 3 則使用者本人打的字有「先這樣／跳過」→ 整批放行、留帳 `harvest_waived`（同一個使用者回合、同閘同一件只記一筆）
- **照欠／照擋**：
  - 同伴訊息裡的 dismiss 詞不算。
  - 不用寫不做行引用。

#### CONFLICT_DECLARED_BY_AI
**判什麼**：寫入時衝突候選交 AI 判（盤點 P8 同類）
- **不欠／放行**：
  - 候選出現的條件：本地標籤 CONTRADICT 複驗一致，或 EXTEND 且相似度 ≥0.85。
  - 要宣告的名單是這次向量前幾名：
    - 不隨本地標籤翻面。
    - 不同層同名寫 `<layer>:<卡名>`。
    - 多寫不在名單的略過。
  - 每張都有 `conflict` 宣告、why 有理由，而且全部 not_conflict → 照寫（[§6.5](../TECH.md#65-壞滅緣證據等級衝突裁決)）。
- **照欠／照擋**：
  - 沒宣告或不全、同候選兩種判法 → 回「衝突待宣告（這次不寫檔）」。
  - 任一 conflict → pending 報告不寫 shared。
  - 都留帳 `conflict_declared`。

#### PROJECT_LITERAL_IS_HINT
**判什麼**：realm 閘的字面「此專案」只是提示（盤點 P8 同類）
- **不欠／放行**：命中的只有字面專案指涉、帶了有理由的 `scope_reason` → 照寫、留帳 `realm_declared`（global、org 兩條）
- **照欠／照擋**：
  - 專名、專案路徑、已登記專案名照擋。
  - 沒帶 scope_reason 照擋並附寫法。

#### PROJECT_RULE_WORDS_ARE_HINTS
**判什麼**：背景萃取／存量整理用線索詞判專案專屬（G6 checklist 最後一處）
- **不欠／放行**：
  - 線索詞（此專案／必須／上傳…）只命中時：
    - 萃取落 personal，留帳 `scope_hint`。
    - classify plan 列 `review`，附命中詞。
- **照欠／照擋**：L2 判 shared、專名／路徑事實照定案 shared

### 退避例外與紅測豁免

#### NOT_DOING_DECLARED／USER_WAIVER_NEEDS_CITATION
**判什麼**：退避例外的入口（退避軟偵測、DeferralGate、紅測清單共用）
- **不欠／放行**：
  - 退避語所在那一行，本身是下列兩種宣告之一（兩種同一種宣告）→ 不標不擋，留帳 `evasion_declared`／`deferral_declared`。
    - `追蹤｜<哪一件>：<原因>`
    - `不做｜<哪一件>：<理由>`
  - 或同文有這種行，且事項出現在那一行、理由有文字內容非佔位 → 同樣放行。
  - 說明句被誤命中時，寫「不是退避｜<命中的詞>：因為 <理由>」同樣不標，留帳。
  - 「不做｜<哪一件>：使用者說「…」」寫了就收，原句不再比對使用者原話（事後抽查）。
  - 紅測豁免只豁免事項指得到的那一筆：
    - 失敗指令或摘要的完整 token：整個 token、檔名、路徑或節點尾段。
    - pytest 節點也認函式名、類別名與不帶副檔名的檔名（`wg_release_rules.names_failed_test`）。
    - 通用字不算。
  - 摘要逐支列出失敗（FAILED／ERROR 行）時，每一支各自要有豁免；有一支沒有，整筆照算紅。
  - 豁免一成立就記帳：
    - state `testfail_waivers`
    - 留帳 `testfail_waived`、`deferral_declared`
    - 之後同 session 同一支看帳，但收尾仍要有對到它的不做行。
  - 使用者在記帳之後又提到這一支 → 帳不算（`testfail_waiver_voided`）。
- **照欠／照擋**：
  - 沒有追蹤／不做行。
  - 理由只有佔位。
  - 使用者只說「先這樣／跳過」，不再整段關掉退避偵測、退縮歸屬、紅測清單（ups_gates 不再清 failing_tests）。

#### BASE_RED_TRACKED_NOT_OWED
**判什麼**：改動前基底就紅、有追蹤項的紅測
- 補充：判法 `wg_release_rules.base_red_failures`；事實由 `post_tool_use._note_red_run_commit` 記、`stop._base_red_facts` 查。
- **不欠／放行**：收尾寫「基底紅｜<紅的那支測試名>：<基底 commit> 也紅；追蹤 <文件路徑>」，紅的每一支下面三件同時成立 → 放行，並留帳 `Logs/guard-testfail_base_red.jsonl`（哪一支、哪個基底、哪份追蹤）。
  - 第一件：本 session 真的在那個 commit 的乾淨工作樹跑過，而且那次紅的有這一支。
    - 跑紅時記 HEAD 與已追蹤檔有沒有改動，state `red_run_commits`。
    - 寫碼守門開時才記。
  - 第二件：那個 commit 的身分要符合三點。
    - 是現在 HEAD 的祖先。
    - 在本 session 開始之前就有（committer 時間；本 session 做的 merge、rebase、提交都不算）。
    - 不在本 session 的提交紀錄裡。
  - 第三件：追蹤文件（.md／.txt）在、本 session 沒改過、內文整詞點名這一支。
- **照欠／照擋**：缺一照擋，擋訊息說缺哪件。
  - 基底綠這次紅（沒有基底的紅可對）。
  - 基底那次工作樹有改動。
  - 基底是自己提交的，或本 session 開始後才有。
  - 不是祖先。
  - 追蹤文件不在、不是文件、本 session 改過、沒點名。
  - 摘要沒逐支列出失敗的不收。
  - 基底那次的指令要只有一段測試（好幾段的紅分不出是哪一段，不記成證據）。
  - 祖先只對紅測條目的 cwd 那個 repo 查。

#### RED_ITEMS_ONLY_FROM_FAILURE_LINES
**判什麼**：紅測的失敗項從哪裡取
- 補充：判法 `wg_release_rules.red_units`／`failure_lines`／`cmd_run_line`／`waiver_miss_notes`；TestFailGate 擋訊息與紅測豁免共用。
- **不欠／放行**：
  - 失敗項只取 pytest 摘要 FAILED／ERROR 開頭的節點行（扣掉 `cleared_units`）。
  - 沒有節點行時，一行一支的失敗各自要有豁免：
    - go：`--- FAIL: TestX`
    - unittest：`FAIL: test_x (…)`
    - jest：`FAIL a.test.js`
    - `FAIL`、`FAILED (failures=2)` 這種結算行不算。
  - 都沒有才整筆當一支。比對文字是測試子命令那幾段的參數（去掉 # 註解，echo 這類別段不算）加上失敗行。
  - 擋訊息的寫法：
    - 逐筆列失敗項與指令實際那行。
    - 沒列出失敗項就說沒列出、要不截斷重跑。
    - 不做行對到了某支，但引用不在近 3 則、帳上也沒有 → 說出是哪一支、引了哪句。
    - 帳上有那支的豁免、收尾卻沒寫不做行 → 給那一行照抄。
- **照欠／照擋**：指令裡 AI 自己寫的不做註解、git status 列出的檔、Exit code 行都不當失敗項，不拿來對不做行（第四跑 C-1 擋訊息印 `Untracked files:`、`Exit code 1`、註解行當失敗項）

### 收尾儀式與寫碼查核案例

#### RECONCILE_BLOCK_LETTERS
**判什麼**：寫碼查核哪些條目會擋收尾
- **不欠／放行**：
  - 沒列在 `reconcile_gate.block_letters` 的條目照判，只印 stderr 不擋。
  - live 只列 a（測試沒過不准說修好）、d（改了程式要有測試），使用者拍板。
- **照欠／照擋**：
  - 列出的字母照擋。
  - 沒設＝全擋。

#### CLOSING_RITUAL_SWITCHES
**判什麼**：收尾儀式要不要擋
- **不欠／放行**：
  - `reconcile_gate.goal_gate`、`aec.scan_report_gate`、`atom_audit.enabled` 設 false → 下列都不擋（目標樹、報告照收；live 全關，使用者拍板）。
    - 需求目標對照與 commit 前的目標對照
    - 收尾檢核
    - 卡片表態
- **照欠／照擋**：
  - `goal_gate` 沒設＝不擋（要擋明寫 true）。
  - 其餘兩個沒設＝照擋。

#### CASE_DECLARED_FOR_CHANGE
**判什麼**：(d) 補案例：由哪個案例驗（驗證範圍閘開著時）
- 補充：`wg_verify_scope.case_check` 收事實。
- **不欠／放行**：驗證範圍宣告裡有一項的 `case_for` 列到這個程式檔，而且下面四件都成立。
  - 那一項點得到案例檔（測試檔、測試節點，或只跑特定測試檔的指令）。
  - 案例檔仍存在。
  - 案例檔本 session 新寫或改過。
  - 那一項在最後一次改動之後跑綠（與 [SCOPE_ITEM_RECEIPT_AFTER_EDIT](#scope_item_receipt_after_edit) 同一個判斷）。
  - 先紅後綠只記錄（[CASE_RED_THEN_GREEN](#case_red_then_green)）。
- **照欠／照擋**：
  - 沒宣告。
  - 宣告的案例不在。
  - 本 session 沒改過（既有案例已經驗到要走 no_case）。
  - 沒跑或跑紅。
  - 改了別支測試不替它清帳。
  - 擋訊息逐檔列哪一項哪裡不成立，並列本 session 改過的案例檔當宣告候選。

#### NO_CASE_NEEDS_USER
**判什麼**：宣告不需要新案例
- **不欠／放行**：
  - 使用者放行那一刻（`wg_verify_scope.approve_no_case`），把宣告裡的 no_case 檔記成已裁定。
  - 裁定綁在它當時的最後一次修改（state `no_case_approved`，user_release 紀錄列出檔名）。
  - 之後沒再改就不再擋、不每回合重問。
- **照欠／照擋**：
  - 宣告了 `no_case: [{path, reason}]` → 照擋。
    - 擋訊息帶理由與【收尾放行確認】的問法（題目寫「<檔> 不需要新案例：<理由>」並掛目標節點）。
    - 要不要補由使用者裁。
  - 裁定之後檔又改了 → 重裁。

#### CASE_COVERS_CHANGE
**判什麼**：(d) 驗證範圍閘關掉時的判法
- **不欠／放行**：
  - 本 session 改過的程式檔，有一個本 session 新寫或改過、仍存在、同根的案例覆蓋它。
  - 覆蓋的認法（任一）：
    - 案例檔名是 test_／verify_<模組名>、<模組名>_test。
    - 案例內容提到它（檔名，或至少 3 字的模組名，整詞）。
    - case_for 列它，來源有兩種：
      - 驗證範圍宣告的 case_for。
      - AI 在回覆文字、`#` 註解指令或 thinking 寫的「case_for｜<程式檔>：<案例檔或節點>」行（`wg_release_rules.parse_case_for_decls`，整個 session 都認，案例相對該程式檔的專案根解析）。
  - 不比改動先後、不看有沒有跑綠。
- **照欠／照擋**：
  - 本 session 改過的案例都沒提到它，也沒有 case_for 宣告。
  - 沒改過任何同根案例。

### 已不存在、還原與等同的改檔

#### GONE_OUTSIDE_VCS／GONE_IN_GIT_NOTHING_NEW
**判什麼**：已不存在的改檔
- **不欠／放行**：算刪除，以下任一。
  - 不在任何版控根內。
  - 在 git 根內，且同根沒有它的副本：沒有新出現的程式檔，或新出現的檔名與內容都和它最後一次寫入時不同。
- **照欠／照擋**：—

#### MOVED_NEW_CODE_SEEN／GONE_UNVERIFIABLE／VCS_ROOT_UNREADABLE
**判什麼**：已不存在的改檔
- **不欠／放行**：—
- **照欠／照擋**：
  - 同根出現它的副本＝搬走。副本的認法：
    - 檔名相同。
    - 內容等於修改紀錄 `sha` 欄記的最後一次寫入內容。
    - 沒有內容紀錄、新檔讀不到 → 全算副本。
  - svn，或查 git 失敗。
  - 找版控根時 OSError（讀不到 ≠ 不在版控）。
  - 已知邊界：搬完又用沒記帳的方式（跑腳本改寫）改了內容，判成刪除。

#### EXCLUDED_REGION
**判什麼**：排除區
- **不欠／放行**：
  - 部位表類別 knowledge 的部位（文件、記憶、派工信箱）裡的檔是素材。
  - 被 .gitignore 忽略或屬執行期資料的檔不是本專案程式（與 [RUNTIME_DATA_NO_OVERVIEW](#runtime_data_no_overview) 同一判式）。
  - 上面兩種：既不算程式、也不能清帳。
- **照欠／照擋**：追蹤中的檔、沒標類別、判不出 → 照算程式

#### NET_UNCHANGED／SNAPSHOT_SETTLED
**判什麼**：改過又還原
- **不欠／放行**：以下任一。
  - 它自己與 HEAD 相同、同根程式檔乾淨、沒 commit。
  - 同根程式檔都回到 commit 那刻不欠的狀態。
- **照欠／照擋**：同根任一程式檔（含案例）不乾淨（程式與案例一起退回、只還原程式）

#### EXEMPTION_PEERS_CODE_ONLY
**判什麼**：上兩條與 [COMMENT_ONLY_CHANGE](#comment_only_change) 一起比的同根改檔
- **不欠／放行**：
  - 只看程式檔（案例檔也是程式檔，`wg_verify_ledger.exemption_peers`）。
  - 文件、紀錄檔、設定、資料改了，或正被別的 session 改著，不擋豁免。
- **照欠／照擋**：程式檔或案例檔本身沒回到那個狀態（含別的 session 正改著同一個程式檔：分不出是誰改的）

#### CONTENT_EQUALS_COMMITTED
**判什麼**：內容等於另一方已提交版本
- **不欠／放行**：
  - blob 等於 MERGE_HEAD／main／master 的版本（merge 取 theirs、退回 main 版）。
  - HEAD 也算，條件是兩件同時成立：
    - HEAD 是別人接在本 session 最後一次提交之上做的（總控台把 main 合進工作分支）。
    - 同根本 session 改過的檔全等於 HEAD。
- **照欠／照擋**：
  - 指到本 session 自己提交的 commit 不算。
  - 其餘情況 HEAD 不算。

#### COMMENT_ONLY_CHANGE
**判什麼**：只改註解
- **不欠／放行**：
  - ast 去註解、docstring、空白後與 HEAD 相同。
  - 本 session 沒 commit 過它。
  - 同根其他程式檔也乾淨。
  - git 事實每個根固定 3 支：
    - ref 與 ref:檔 一支 `cat-file --batch-check`
    - `hash-object`
    - HEAD 原始碼一支 `cat-file --batch`
  - 取不到內容，同根不再重取、照算改了。
- **照欠／照擋**：非 Python、解析不了、改到識別字

### 擋次預算與放行

#### BLOCK_BUDGET_SHARED
**判什麼**：擋次預算
- **不欠／放行**：
  - 紅測與寫碼查核（對帳 (a)～(d)＋驗證範圍）每個使用者回合共用一份：
    - 設定 `reconcile_gate.max_blocks_per_turn`，鍵 `*`，不分哪一條規則。
    - 擋滿才問放行。
    - 擋滿訊息列全部條目。
  - 吃 `stop_gate_max_blocks` 的共用擋次，每個使用者回合歸零、同一回合第 3 次放行（寫碼守門開時）。
    - 這群包含：退縮閘、收尾檢核推遲寫卡、Reload 建議、取用稽核、一般同步擋。
- **照欠／照擋**：
  - 收尾報告那一份（e）另計。
  - 寫碼守門關時，共用擋次整個 session 累計。

#### PENDING_SAME_USER_TURN／RELEASE_COVERS_SHOWN_ITEMS／NONINTERACTIVE_RELEASE_AT_BUDGET
**判什麼**：擋滿之後怎麼放行（[§7.3](../TECH.md#73-擋滿之後怎麼放行hookswg_releasepy)）
- 補充：判法 `wg_release.pending_of`／`release_items`／`keep_released`。
- **不欠／放行**：
  - 待放行只在記下它的那個使用者回合有效；使用者打字開新回合就失效、預算重給。
  - 使用者放行同一回合整個放。
  - 之後的回合只沿用擋訊息列過的那幾件，原因還在也不再問。
  - 沒人能回答（headless／SDK、子代理、裁判）→ 擋滿就放行並留帳。
- **照欠／照擋**：
  - 續跑回合（背景通知、同伴訊息開的）不算換回合，照原宣稱重查。
  - 放行之後又改了檔，整份不沿用。
  - 新原因照擋。

#### GATE_SELF_ERROR
**判什麼**：閘自己判定出錯（例外、設定讀不到）
- 補充：判法 `gate_self_error_verdict`。
- **不欠／放行**：
  - 工具前閘直接放行：動資料檔、改舊測試、繞閘、commit 前目標核對、svn 測試路徑、定位閘讀不到 transcript。
  - 收尾閘同一個錯誤，每個使用者回合擋 1 次後放行。
  - 都 stderr 一行＋guard log event=error。
- **照欠／照擋**：收尾閘同一回合第一次遇到這個錯照擋一次

#### GATE_DENY_CAP
**判什麼**：宣告類閘的擋次上限
- 補充：判法 `wg_core.deny_cap`，上限 `DECL_DENY_CAP` 2。
- **不欠／放行**：
  - 同一個使用者回合、同一道閘、同一件缺件，擋滿 2 則回覆，下一則放行並留帳。
  - 留帳的事件名：
    - 動資料檔／改舊測試／不是繞閘：`cap_released`
    - 定位閘：`edit_deny_capped`
    - 最小地圖：`edit_unmapped_capped`
  - 換使用者回合歸零。
- **照欠／照擋**：
  - 適用五處：定位閘、最小地圖三行、動資料檔、改舊測試、不是繞閘。
  - 沒有 state 可記，照擋、不計次。

#### DENY_CAP_PER_REPLY
**判什麼**：擋次怎麼數
- 補充：`wg_core.deny_cap` 的 `call`；批次鍵 [`lib/chain_store.batch_of`](../lib/chain_store.py)，同 CHAIN_SAME_BATCH。
- **不欠／放行**：
  - 照則數、不照工具呼叫數。
  - 同一則回覆裡平行送出的呼叫，是送出前就決定好的，AI 還沒看到第一則擋訊息。
  - 同一件在同一則裡只算一次；那一則的其他呼叫照第一次的結果（擋就照擋）。
  - 下一則回覆的呼叫才加次數。
- **照欠／照擋**：
  - 判不出是哪一則（子代理、transcript 讀不到、沒有 message.id）→ 照每個呼叫算，留帳 guard-deny_cap event=batch_unknown。
  - 五道閘都從 PreToolUse 帶這次呼叫的 tool_use_id。

#### PICK_ONCE_PER_USER_TURN
**判什麼**：交付時「點出最該修」什麼時候問（[§7.1](../TECH.md#71-stop-閘序) PickOne）
- 補充：`wg_harvest.pick_due`。
- **不欠／放行**：
  - 一個使用者回合問一次（`asked_uturn`／`covered_uturn`）。
  - 收尾是不是續跑出來的（`stop_hook_active`）不當條件：第一次收尾被別的閘擋下、修完續跑收尾照樣問。
  - 交付邊界記整個使用者回合（`boundary_uturn`，被擋的那次收尾也算）。
- **照欠／照擋**：
  - 連鎖中止中不送。
  - 同一批改動問過，或 AI 自己先寫了那段，也不送。
  - state 沒有 `turn_prompts_seq`（使用者回合退回 turn_seq）時，續跑收尾不重問。

#### PICK_ONE_PRE_CLOSE／PICK_ONE_WITH_TURN_JUDGMENT
**判什麼**：「點出最該修」在哪裡送
- 補充：`wg_closing_round.pick_pre_close`、Stop 的 TurnJudgment 段。
- **不欠／放行**：
  - 下列三種批次＝交付邊界（`post_tool_batch._test_green_batch`）：
    - 交收尾檢核（anti_evasion_report）或完整對照（need_goal reconcile）那批。
    - 改過程式之後測試跑綠那批。
    - 測試還紅，但還紅的每一支都在使用者豁免帳上（state testfail_waivers）那批。
  - 該問就附在那批的回應後面，記問過（guard-pick_one via=pre_close）。
  - Stop 的拐彎判斷擋下時，同一則一起問。
  - 開關 `pick_one.pre_close` 關 → 照舊由 Stop 排在所有閘之後送。
- **照欠／照擋**：
  - 連鎖警報後只記錄時不送。
  - 沒交收尾檢核也沒交完整對照的批次不送。

### Bash／PowerShell 指令怎麼讀（寫入目標、唯讀、讀檔證據）

#### INLINE_PY_READONLY
**判什麼**：`python -c` 內嵌碼
- **不欠／放行**：ast 判，下面全部成立才不算寫入。
  - 只能直接呼叫具名函式。
  - 無寫檔 open 模式。
  - 無刪搬寫 API。
  - 無 subprocess／shutil／exec／eval／getattr。
  - `open`、刪搬寫名字不能當值（別名、傳參、放進容器）。
  - 不能 `from … import *`。
    - `import … as` 取別名照判：看呼叫鏈尾的名字。
    - builtins 的 exec／eval 照擋。
  - 不能定義函式。
  - 其他寫法同法判：
    - 多行 `-c`，與 `python -` 從 heredoc 讀的程式。
    - 條件：只有一份 heredoc、沒有別的輸入重導向，而且定界符加了引號或內文沒有 `$`／反引號。
    - 多份 heredoc 時 stdin 是最後那份，判不準照 UNKNOWN。
  - 哪個旗標算內嵌碼、字面變數怎麼代換，見下兩個區塊（[INLINE_FLAG_BEFORE_PROGRAM](#inline_flag_before_program)、[SHELL_LITERAL_VAR_EXPANDED](#shell_literal_var_expanded)）。
- **照欠／照擋**：
  - 任何判不了的寫法都算 UNKNOWN。
  - 擋訊息帶 ast 判出的原因（「內嵌碼：…」，只附在內嵌碼那段自己身上）。
  - node -e、pwsh -Command 判不了照擋，擋訊息指路。

#### UNKNOWN_WRITE_RECOVERED
**判什麼**：寫入目標判不出的 Bash／PowerShell 指令（`python -c`、heredoc 餵給直譯器、變數路徑）跑完後，真的改了哪些檔
- 補充：
  - 判法 [`hooks/wg_unknown_write.recover`](../hooks/wg_unknown_write.py)，呼叫端 `post_tool_use._recover_unknown_write`。
  - PostToolUse、結束碼非 0 的 PostToolUseFailure、裁判子 session 都走。
- **不欠／放行**：算「改了」並補進記錄的條件如下。
  - 哪些檔：
    - git status（`--porcelain=v1 -z --untracked-files=all`）／svn status（`--xml`，只有未納管的目錄往下展開，合計最多 500 檔）列為改動或未納管。
    - 而且 mtime 落在「這次指令開始時間減 0.05 秒」到「現在加 2 秒」之間。
  - 開始時間怎麼取：
    - 開始時間＝transcript 那筆 tool_use 的時戳。
    - Claude Code 邊串流邊執行工具；同一則回覆平行送出的第一個工具跑完時，這則紀錄常還沒落盤。
    - 找不到就用已落盤的最後一筆紀錄的時間，帳記 `start_from=transcript_tail`。
    - 實跑量到指令自己寫的檔 mtime 一律晚於自己的時戳，最少 +31 ms，所以往前只放寬 0.05 秒。
  - 補進哪裡：
    - 記進 `modified_files`（`via=vcs_status`、`tool`＝Bash／PowerShell、本回合）。
    - 對帳 (d)、第二意見數程式檔、同步提醒、目標樹蓋號照常判。
    - 那一筆 `unknown_writes` 記 `recovered`。
  - 太慢的降級：
    - 整棵 status 超過 1.2 秒 → 改查指令文字裡點名、存在的檔。
    - 點名檔的找法：引號字串與裸字樣，照 hook cwd 與指令裡 cd 過去的目錄解；幾個根合用 0.8 秒；萬檔 svn 約 0.12 秒。
    - 該根記進 state `unknown_write_slow_roots`，同 session 之後直接只查點名的。
- **照欠／照擋**：不算改了、或補不到的情況如下。
  - 不算：
    - 快照前就髒、這次沒動的檔（mtime 早於開始）。
    - 本 session 已經記過，而且內容雜湊跟上次一樣（原樣重寫），或沒有雜湊（超過 2 MiB）而 mtime 不晚於上次記下的時間 → 不刷成本回合改的。
    - 版控說跟基準相同的。
    - 未來時間的 mtime。
  - 補不到，那一筆寫明 `unrecovered`：
    - 不在 git／svn 工作區。
    - 找不到開始時間。
    - 查詢失敗。
    - 整棵逾時又沒點名。
    - stderr 與 `Logs/guard-unknown_write.jsonl` 留整段耗時 `ms`、版控查詢耗時 `status_ms`、補到的檔 mtime 比開始晚幾毫秒 `lag_ms` 與原因。
  - 分不出的：
    - 指令跑的那段時間裡，別人（使用者、別的 session）寫的檔會算進來。
    - 同一條指令寫完又 commit 掉的檔（工作樹已乾淨）補不到。
    - 改回跟基準一樣的檔補不到。
    - 刪掉的檔補不到。
    - 保留舊 mtime 的複製或改名補不到。

#### INLINE_FLAG_BEFORE_PROGRAM
**判什麼**：哪個 `-c`／`-e` 才是內嵌碼（`wg_core._inline_flag_at`）
- **不欠／放行**：
  - 程式（腳本、`-m` 模組、pwsh `-File`）之後的參數屬於程式：`python x.py -C <路徑>`、`python x.py -` 不是內嵌碼。
  - 帶值的選項連值一起跳過：python `-X`／`-W`，node `-r`／`-C`…
- **照欠／照擋**：
  - 直譯器自己選項位置上的 python `-c`／`-`、node `-e`／`-p`、pwsh `-Command`／`-c`／`-e` 照內嵌碼判。
  - python／node 分大小寫，pwsh 不分。

#### SHELL_LITERAL_VAR_EXPANDED
**判什麼**：Bash 寫入目標裡的 `$NAME`（`wg_core._remember_vars`／`_expand_vars`）
- **不欠／放行**：
  - 同一條指令裡獨立一段、一定會跑的 `NAME=字面值`（或 export）之後的 `$NAME`／`${NAME}`，代換成那個值再算目標。
  - 例：`S='<scratchpad>' && git show … > "$S/old.py"` 算得出是 scratchpad。
- **照欠／照擋**：照舊 UNKNOWN 的情況如下。
  - 值不是字面（含 `$`、反引號、`$(…)`）。
  - 沒指定過。
  - 前面接 `&&`／`||` 的條件式指定。
  - 管線／背景／子 shell 裡的指定。
  - 單引號裡的 `$`。
  - 指令前綴的指定（`S=x cmd "$S"`）。
  - PowerShell 變數。
  - 內嵌碼的判不了原因只附在它自己那段。

#### GIT_READONLY_SUBCMD
**判什麼**：專案 session 對根層 repo 的 git
- **不欠／放行**：
  - 先按換行，再按 `&& || ; | &` 切段。
    - 引號裡的換行不切。
    - 黏在字上的分隔也切。
    - 段首 shell 保留字剝掉（見 [DOT_GIT_PATH_NOT_GIT_CALL](#dot_git_path_not_git_callsegments_split_like_shellshell_keyword_prefix_stripped) 區塊）。
  - 每段 git 都是唯讀子命令：show、hash-object 無 -w、rev-parse、diff、log、status、ls-files、cat-file…
  - 沒有 `--output`／`-o` 這類寫檔選項。
  - 沒有命令替換。
  - 寫入目標不在根層。
- **照欠／照擋**：
  - 任一段會寫、目標在根層或不明。
  - 擋就留 `Logs/guard-crossrealm.jsonl`。

#### DOT_GIT_PATH_NOT_GIT_CALL／SEGMENTS_SPLIT_LIKE_SHELL／SHELL_KEYWORD_PREFIX_STRIPPED
**判什麼**：跨層閘與寫入目標掃描器怎麼讀指令
- 補充：`wg_core._GIT_WORD_RE`、`wg_release_rules._shlex_segments`／`SHELL_PREFIX_KEYWORDS`、`wg_core._scan_segment`。
- **不欠／放行**：
  - 路徑裡的 `.git`（`ls repo/.git/hooks`）不算 git 字樣。
  - 整條切段時：
    - 引號裡的換行與 `;&|`（多行 `python -c "…"`、`echo ";&" …`）留在同一段。
    - `;`／`&&`／`|` 黏在字上也切。
  - 段首的 do、then、else、elif、if、while、until、!、{ 剝掉才認命令。
    - for／while 迴圈本體、if 分支、{ } 群組裡的寫檔命令與 git 照認。
    - 兩邊同一份字表。
- **照欠／照擋**：
  - 引號到最後都沒收才算解析不了。
  - 目標帶迴圈變數 → 照 UNKNOWN_TARGET_LOGGED 放行留帳。

#### DELETE_FORMS_SAME_ACROSS_SHELLS
**判什麼**：刪除的各種寫法（`wg_core._scan_segment`）
- **不欠／放行**：
  - Bash 的 rm（-r 不帶值，只有 touch -r 才帶）、rmdir。
  - PowerShell 的 Remove-Item，與別名 ri、del、erase、rd、rmdir、rm。
  - 上面兩邊認出同一個目標。
  - Set-Location／sl／chdir／Push-Location（含 -Path、-LiteralPath）之後的相對目標，照換過的目錄算。
- **照欠／照擋**：
  - 目標從管線進來（`Get-Item x | Remove-Item`）、`[System.IO.File|Directory]::` → UNKNOWN（放行留帳，不是沒看到）。
  - `cmd /c rmdir` 這類包一層的，照舊認不出。

#### UNKNOWN_PART_KEEPS_KNOWN_TARGETS
**判什麼**：一條指令裡有判不出目標的部分（`wg_core._scan_segment`、`_shell_write_paths`）
- **不欠／放行**：
  - 判不出的部分只多記一筆 UNKNOWN（放最後）。
  - 判不出的部分包含：`$(…)` 裡有寫入、`[IO.File]::` 這類內嵌碼、展不開的變數目標。
  - 同段與別段看得懂的目標照列、照判。
- **照欠／照擋**：
  - 舊碼有 UNKNOWN 就只回那一筆。
  - 例：`rm <核心檔> '[IO.File]::'`、`rm <核心檔>; echo x > "$VAR/out"` 跨層閘放過，現在照擋。

#### DIR_TARGET_JUDGED_BY_CONTAINER
**判什麼**：改檔閘逐目標判、整個資料夾當目標（`wg_overview.write_target_root`）
- **不欠／放行**：
  - 看資料夾所在的上一層屬於哪個專案，不拿資料夾自己的 `.git`、`_AIDocs`、部位表。
  - 效果：刪掉整個殘留資料夾（工作樹已除名、刪不乾淨），不再被要求讀「(outside)」的檔。
- **照欠／照擋**：
  - 上一層是專案就照它的規則（專案裡的子資料夾整個刪，要先讀過根目錄一檔）。
  - 資料夾裡的單一檔照舊看資料夾自己的標記。
  - cwd 這類「我在哪」的目錄不走這條。

#### GREP_CONTENT_IS_READ／BASH_COMMENT_LINES_STRIPPED
**判什麼**：讀檔證據
- **不欠／放行**：
  - Grep `output_mode=content` 且 path 是檔，算讀過。
  - Bash 行首 `#` 註解行剝掉，每行行首都算指令開頭。
- **照欠／照擋**：—

#### BASH_READONLY_COUNTS_AS_READ
**判什麼**：Bash／PowerShell 讀檔證據
- **不欠／放行**：
  - 讀檔指令：cat、head、tail、less、more、sed -n、grep -n（第一個參數是樣式不算）、svn cat、git show、Get-Content…
  - 一段裡每個路徑參數都算。
  - 執行成功（exit 0 或未知）、字面路徑、是實檔 → 與 Read 同效。
  - Bash 沒加引號的 glob 照 cwd 展開成實檔。
  - `for V in 清單; do …"$V"…; done`：
    - 清單每項是字面（沒加引號的 glob 照展開）。
    - 本體沒有 break／continue／exit／return。
    - 符合就逐項代進本體再認。
- **照欠／照擋**：
  - 其他含 `$` 的、清單含 `$`／`$(…)` 的迴圈。
  - 展不出實檔的 glob。
  - exit≠0。
  - 檔不存在。
  - 重導向目標。
  - echo／printf／ls／find 不是讀檔指令。

### 同步、綜觀與暫存目錄

#### WORKTREE_NO_PUSH
**判什麼**：同步閘要不要求 push
- **不欠／放行**：git worktree 或分支沒 upstream → 不要求
- **照欠／照擋**：主工作樹且有 upstream

#### RUNTIME_DATA_NO_OVERVIEW
**判什麼**：無表檔的綜觀要求
- **不欠／放行**：以下任一 → 免讀同目錄。
  - gitignored。
  - 在執行期資料目錄（`workflow/state*`、`workflow/need-goal`、`Logs`…）。
  - 路徑含快取目錄：`__pycache__`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache`（沒有 .gitignore 也算）。
- **照欠／照擋**：程式檔照要求

#### UNMAPPED_EDIT_NEEDS_READABLE_FILES
**判什麼**：無表檔要讀幾個
- **不欠／放行**：
  - 要讀數＝min(`min_overview_evidence.part_files`, 同頂層目錄非執行期資料的既有檔數)。
  - 目錄只有子目錄、快取或 gitignored 產物 → 不要求。
  - 擋訊息印「該目錄既有可讀檔 N 個」。
- **照欠／照擋**：
  - 有可讀檔沒讀照擋。
  - 讀目錄出錯或檔太多數不完 → 照設定數。

#### TEMP_REPO_COMMIT_EXEMPT／TEMP_COPY_NOT_PROJECT
**判什麼**：暫存目錄
- **不欠／放行**：
  - commit 實際落的 **repo 根**在這些暫存位置下才免口令：系統 TEMP、CC 的 Temp/claude 暫存、pytest tmp。
  - 暫存目錄下的副本：
    - 不找部位表。
    - 不注入。
    - 不要求綜觀。
    - 不當收據。
  - 兩側都展成長路徑再比（8.3 短路徑）。
- **照欠／照擋**：正式 repo（含它裡面叫 scratchpad 的子目錄）、本體

#### SESSION_SCRATCH_NOT_CODE
**判什麼**：本 session 改的程式檔怎麼數
- **不欠／放行**：
  - 這兩處底下的檔是一次性腳本：
    - Claude Code 背景工作的 `<CC 設定目錄>/jobs/<id>/tmp/`（CLAUDE_CONFIG_DIR 與 ~/.claude）。
    - `<系統暫存根>/claude/…/scratchpad/`。
  - 一次性腳本的待遇：
    - 第二意見門檻不數。
    - 寫碼查核補案例不數。
    - 驗證範圍不數。
    - 不能拿來清帳。
  - 判法 `wg_verify_ledger.session_scratch`，兩側先展 8.3 短路徑。
- **照欠／照擋**：repo 裡自己取名 jobs/<x>/tmp、Temp/claude/…/scratchpad 的目錄（不在暫存根底下）

### 紅測與重試

#### RED_WHILE_REVERTED／RETRY_COUNTS_RERUN_CYCLES／GREEN_SAME_CASE_CLEARS
**判什麼**：紅測與重試
- **不欠／放行**：
  - 刻意紅不記：跑紅時，本 session 改過的程式檔**全部**處在非 HEAD 已提交版本（同根沒有任何自己的現行改碼）。
  - 改檔記在每筆還活著的紅測的 `edits_since_run`。
  - 又跑紅時，符合下面條件才算一輪重跑：
    - 重跑**同一組**測試。同一組的認法：
      - 點名的程式檔集合完全相同（共用設定檔不算）。
      - 或兩邊都沒點名檔，且指令前 40 字相同。
    - 而且那組上次跑之後碼有改過。
  - 判完一輪就清掉那組的紀錄：
    - 兩次重跑之間改幾次，都只算一輪。
    - 中間跑別組的綠，不會取走 A 的紀錄。
    - 第一次跑別組紅不算。
  - 不猜改檔是為了修哪一組。
    - 同時修多組時，沒改到的那組重跑仍紅也算一輪（已知限制，代價是多一次提醒）。
  - 紅之後第一次重跑就綠＝0 輪。
  - 只改計畫類檔不記。
  - 綠的點名**同一個**案例檔（含目錄；兩邊有 cwd 就比絕對路徑）就清那筆紅。
- **照欠／照擋**：
  - 只退回其中一檔、另一檔還留著真錯 → 真的紅照記。
  - 同名不同目錄的案例不互清。
  - 兩輪重跑仍紅升級 FixEscalation（plan 與 direct 同門檻）。
  - 提示與 DeepPostMortem 觸發句印第幾輪與每輪的重跑指令＋紅案。

### 搬程式目錄

#### MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE
**判什麼**：(v) 搬程式目錄的義務
- **不欠／放行**：搬了含程式檔的目錄之後，有兩張合格收據。
  - 什麼算「搬了目錄」：
    - 指令：mv、Move-Item、Rename-Item、git mv（含 `-C`）。
    - 跟著前面的 cd／Set-Location，多來源。
    - 子代理搬的也算，帶 agent_id。
    - 搬單一檔案、複製不算。
    - PostToolUse 記 `moved_code_dirs`。
    - 搬了又搬照最終位置算，完整搬回不欠。
  - 第一張收據：[`tools/move-dir-check.py scan --old <舊> --new <新>`](../tools/move-dir-check.py) 的 `MOVE_PATH_SCAN DONE hits=0`。
    - 要點名同一個舊路徑；相對路徑照工具那一段的有效 cwd 與 `--root` 解。
    - 絕對、相對、單雙反斜線都掃。
    - 命中 >0 要修碼重掃；刻意保留用 `--allow`。
  - 第二張收據：`sample --for <新目錄>` 的 `MOVE_SAMPLE_CHECK PASS`。
    - 只替 `--for` 點名的搬移清帳。
    - `--run` 跑被搬模組的 import 或目標 verify。
    - C# 加 `--csproj-check <新目錄>`：每個 .cs 至少被一個 .csproj 編進去（不同檔可由不同專案編）。
      - SDK 型預設收專案目錄底下。
      - 或明列 Compile Include，可連結專案外目錄。
      - Compile Remove 排除。
      - 有 .sln 時，編它的 .csproj 也要被提到。
      - 檢查出錯也印 FAIL 尾行。
  - 收據條件：
    - 要在搬之後（比 session 事件序號）。
    - 指令完整、記了環境、沒寫哨兵字樣。
    - 工具在根層，不套「指到收據根以外」。
  - 子代理與主 session：
    - 子代理收尾只查它搬的、用它的收據。
    - 主 session 收尾查全部，也認子代理的收據。
  - 擋訊息照 Bash 與 PowerShell 各印一行加好引號的指令（含工具絕對路徑），照貼就能跑。
- **照欠／照擋**：
  - 缺任一張。
  - 掃描最後一次 hits>0（擋訊息列命中前幾筆）。
  - 不欠整組案例，也不放寬 (d)：搬完又改的程式檔照欠案例。

### 紅測清帳：篩選、範圍與最後結果

#### GREEN_NARROWED_KEEPS_UNCOVERED_RED
**判什麼**：篩選過的綠能不能清紅
- **不欠／放行**：
  - 綠沒有篩選 → 照 [RED_WHILE_REVERTED](#red_while_revertedretry_counts_rerun_cyclesgreen_same_case_clears) 區塊的清帳。
    - 沒有篩選＝沒有節點 id、-k、-m、Jest -t。
    - 只看測試子命令那段、子命令之後。
    - 指令先以 `;`／`&&`／`||`／`|`／換行切段，同一指令別段的 `python -m <模組>` 不算。
  - 有篩選時，下列任一 → 清：
    - 紅掉的案例都在綠點名的節點裡。
    - 是同一個篩選指令重跑。
- **照欠／照擋**：
  - 單案或 -k 跑綠沒涵蓋紅掉的案例 → 那筆紅與它的改檔紀錄照留。
    - 含 -k 運算式判不了、紅的輸出沒列案例。
  - 重跑整檔仍紅照算輪數。
  - stderr 印規則名與證據。

#### GREEN_CLEARS_ONLY_CASES_IT_RAN
**判什麼**：點名檔案或節點跑綠能清哪幾支紅
- 補充：`wg_release_rules.green_ran_cases_verdict`，post_tool_use 清帳時判。
- **不欠／放行**：
  - 綠沒點名檔也沒篩選（跑整套）→ 照 [GREEN_NARROWED_KEEPS_UNCOVERED_RED](#green_narrowed_keeps_uncovered_red) 區塊的清帳。
  - 點名了整檔或節點時：
    - 紅測摘要逐支列出的失敗（FAILED／ERROR 節點行）都在綠點名的檔或節點裡 → 清整筆。
    - 只跑到一部分 → 跑到的那幾支記進那筆紅的 `cleared_units`，其餘照留（放行要對那支紅測自己的最後一次執行）。
  - 點名範圍含目錄（`tests/unit`；選項的值如 `--basetemp /tmp/x` 不算），同一組點名重跑全清。
  - 紅的輸出沒列案例時，紅點名的範圍綠都跑了才清。
  - 有 -k／-m 照 [GREEN_NARROWED_KEEPS_UNCOVERED_RED](#green_narrowed_keeps_uncovered_red)（只看還沒清掉的那幾支）。
  - 紅那一面：
    - 新的一次紅完整列出失敗（列出的支數等於結算 failed＋error）時，舊紅裡這次也跑到的那幾支以這次為準（`post_tool_use._supersede_reds`）。
    - 截斷沒列的紅不動舊紅。
- **照欠／照擋**：跑別的測試檔變綠 → 那筆紅照留，stderr 印規則名與沒跑到的那幾支。
  - 例：第四跑 C-1，使用者說跳過 ERP 合約測試後，只跑另外 3 支檔變綠。

#### RED_LAST_RESULT_IN_COMMAND
**判什麼**：同一條指令跑了不只一次測試時，哪幾支算紅
- 補充：
  - 判法 `wg_release_rules.red_units_last_result`。
  - 事實 `test_segments`（heredoc 內文先剝掉，`strip_heredoc_bodies` 與口令閘共用）、`command_test_runs`。
  - 套用點 `post_tool_use._track_test_result`，在負向對照之後、重試計數之前。
- **不欠／放行**：
  - 每支紅案以這條指令裡最後一次「看得出範圍」的結果為準。
    - 看得出範圍＝解析得出測試子命令與點名範圍的段。
    - heredoc 餵給直譯器的段（`python - <<EOF`）看不出跑了哪支。
  - 不記紅的兩種情況：
    - 紅之後，看得出範圍的綠跑到它。
    - 紅來自看不出範圍的段，同一指令看得出範圍的綠跑過它（不分先後）。
      - 看不出來源的紅蓋不掉看得出來源的綠，比照 [RECEIPT_UNPARSED_GENERAL_ONLY](#receipt_unparsed_general_only)。
      - 實跑 009-CCon-1：`pytest tests` 5 passed 在前、heredoc 換回 UTC 跑兩支 FF 在後。
  - 全部不記 → 記 deliberate_reds、不進 failing_tests、不計重試；看得出範圍的綠那幾段照常清舊紅。
  - 部分不記 → 那幾支預先記進 cleared_units。
- **照欠／照擋**：照記紅，留帳 `guard-testfail_scope` event=red_last_result。
  - 看得出範圍的紅之後只有看不出範圍的綠。
  - 先綠後紅（都看得出範圍）。
  - 紅 a 之後只跑 b 綠。
  - heredoc 裡單跑一次紅。
  - 段數對不上結算數。
  - 哪次紅沒逐支列出。

#### RED_SCOPE_FROM_FULL_COMMAND
**判什麼**：紅測的範圍從哪裡取
- 補充：`post_tool_use._test_scope`；擋訊息 `stop._rerun_scope`。
- **不欠／放行**：
  - 記紅時從整條指令解析，存解析後的目標 `test_scope.steps`。
    - 每段測試子命令＋點名的檔、目錄、節點、-k 這類篩選。
    - 加上它前面的換目錄。
    - 跟指令多長無關、不截斷。
  - 上面兩個區塊判涵蓋、紅取代紅、重跑同一組時，兩邊都用它比。
  - 判不出目標的紅原樣重跑（空白不同也算）綠了就清。
- **照欠／照擋**：
  - 認不出測試子命令（例 `npm test`），或舊條目 cmd 剛好 200 字（可能被截過）→ 判不出。
    - 不拿片段當路徑。
    - 留帳 `guard-testfail_scope` scope_unparsed。
    - 只認原樣重跑，或列得出名字的紅被跑到。
  - 擋訊息：
    - 對看不出是哪一支的紅，列出解析出的每段，照抄重跑。
    - 判不出或長過 600 字，給「原指令完整照跑或跑整套」。

### 目標樹：達成、定位與提問

#### GOAL_DONE_NEEDS_CASE_OR_RECEIPT／GOAL_INFERRED_MAX_PARTIAL
**判什麼**：目標樹完整對照的「達成」（`wg_need_goal` 收件與交付邊界同一支）
- **不欠／放行**：
  - 寫碼類樹的達成，至少一筆沒紅的收據（實測）或讀碼級驗證案例。
  - 記憶知識類樹不查第一條。
- **照欠／照擋**：
  - 只有檔案、卡片、推論級案例或紅收據。
  - 任何類別證據全是推論。
  - 擋訊息列節點與現有每一筆證據。

#### CASE_RED_THEN_GREEN
**判什麼**：案例有沒有先紅後綠（只記錄）
- **不欠／放行**：
  - 目標檔收據裡點名同一案例檔先紅、之後綠 → 該筆證據記 `red_then_green`，對照摘要印出。
  - 點名哪些檔：蓋號時用完整指令與它的 cwd 解成絕對路徑。
    - 同名不同目錄不算。
    - 引號裡含空白的路徑整段算。
- **照欠／照擋**：
  - 指令裡換目錄或沒記 cwd 的收據不比。
  - 對不上照收，摘要印「案例未見先紅」。
  - 不是閘。

#### LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES
**判什麼**：有目標樹時改寫碼部位的定位四行內容結構
- 補充：`wg_overview.on_edit` 收事實。
- **不欠／放行**：
  - 第四行括號（全形或半形）內寫了這一塊在目標裡的角色。
    - 非空。
    - 不是佔位句。
    - 不是節點原文照抄。
    - 寫在括號外不算。
  - 根因層辨識出兩個候選，加選擇理由。
    - 候選標記：「候選 A／候選一」「第一根因／第二根因」。
    - 選擇理由字樣：因為、理由、原因、由於、所以。
      - 以「；，。」切段。
      - 段裡理由詞前面沒有候選標記才算。
      - 「候選 A 的原因是 …」是候選自己的描述。
      - 「根因為」不算。
  - 或寫了第一個，加「第二個不存在因為／：…」。
    - 只有「第二個不存在」沒有第一個不算。
    - 「候選 A 無鎖競爭」這種以「無／沒有」開頭的描述，不當成不存在。
  - 部位名被同表更長的部位名包含時（UI 之於 UI 設定），提到長名的那組不算短名部位的。
- **照欠／照擋**：
  - 缺角色、照抄節點 → 只記錄不擋（guard-need_goal locate_soft）。
  - 只一個候選又沒寫第二個不存在的理由，或兩個候選沒理由 → 每個使用者回合擋一則回覆。
    - 擋次上限 `wg_core.deny_cap` 為 1。
    - 同一則回覆平行送出的改檔一起擋（[DENY_CAP_PER_REPLY](#deny_cap_per_reply)）。
    - 同回合之後只記錄。
  - 擋訊息列全部缺項，加照抄可過的範例四行（部位名、要指明的層、節點都填好）。
  - 只看結構不評對錯。
  - 知識類部位、沒目標樹的三行情境不查。

#### LOCATE_CANDIDATES_WITHOUT_FIXED_LABELS
**判什麼**：根因層沒寫固定字樣時怎麼數候選（`wg_release_rules.root_candidates`）
- **不欠／放行**：那行完全沒有「候選 A／第一根因」這類標記時，下面兩種也算候選。有標記就只看標記。
  - 兩個以上的列舉：
    - ①②、⑴⑵、(1)(2)／（一）（二）。
    - 括號數字前面接英數字的是函式呼叫，不算。
  - 兩個以上不同名稱的「<名稱>層」：
    - 這層、每層、第二層、第四層、跨層這類泛稱與「根因層」不算。
    - 名稱前黏的「在、修、從…」切掉。
    - 一個名稱是另一個的尾段，算同一層。
  - 選擇理由照 [LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES](#locate_lines_need_role_and_two_candidates) 區塊要寫。
- **照欠／照擋**：
  - 只有一個列舉或一層照舊算 0 個。
  - 固定字樣只是建議寫法（第四跑 B-1：第一版「①邏輯層…；②測試層…」被判 0 個，第三版改成「候選 A」才過）。

#### EDITED_PART_NEEDS_GOAL_NODE
**判什麼**：(f3) 改到的部位都掛到目標（`wg_need_goal` 收事實）
- **不欠／放行**：
  - 目前寫碼類樹上改過程式檔的每個部位，在定位帳（目標檔 `links.parts`）掛到樹裡還活著的節點。
  - 收尾前先從 transcript 三管道找補交的四行（同一套判法）補掛。
- **照欠／照擋**：
  - 沒交過，或掛的節點已放棄、不在樹 → 交付邊界與 commit 前擋。
    - 列「<部位>：<改的檔> 沒掛目標」。
    - 指路補交四行或 need_goal add。
    - 擋訊息帶 `✗ (f3)` 單獨計擋次。
  - 表外的檔、知識類部位、OverviewHub 在那一層關掉的不算。

#### KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE／KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY
**判什麼**：(f4) 記憶知識類的輕樹
- 補充：`wg_need_goal.knowledge_gate_reason` 收事實。
- **不欠／放行**：
  - 本使用者回合沒有在沒樹時改記憶知識類的檔。
  - 交付邊界時，下列任一：
    - 目前的樹是寫碼類（歸 (f2)）。
    - 知識類樹在最後一次對得上目標版本的完整對照之後沒有改檔（純問答樹沒改檔也不要求）。
- **照欠／照擋**：
  - 本回合沒樹時改了記憶知識類的檔（不看措辭）。
  - 交付邊界時知識類樹沒對照過、對照後目標改過，或對照後又改了檔。
  - 屬記憶與報告類：
    - 併進收尾報告欄那一份。
    - 本回合第 3 次放行並記 `reconcile_overflow`，不問使用者。
  - 擋訊息帶 `✗ (f4)` 與指路（寫輕樹／交 reconcile）。

#### ASK_NEEDS_RECOMMENDATION
**判什麼**：AskUserQuestion 每一題有沒有附推薦
- 補充：`wg_need_goal_points` 收事實。
- **不欠／放行**：以下任一。
  - 至少一個選項 label 標 `(Recommended)`（全形括號、大小寫都認）。
  - 題目文字含「建議：」。
  - 【收尾放行確認】而且選項正好是固定兩個的放行題。
  - 工具輸入沒有可判的題目。
- **照欠／照擋**：
  - 任何一題兩者都沒有，不分有沒有樹、哪一類。
  - 含標記但選項走樣（多了、少了、加了 `(Recommended)`）的照擋，並指路照抄兩個選項。
  - 擋訊息列缺的題目與照抄可過的 label／「建議：」寫法。

#### ASK_LINKED_TO_GOAL
**判什麼**：每一題有沒有指到目標樹節點
- **不欠／放行**：
  - 範圍：每一題（題目＋選項 label 與描述，不含 header；ExitPlanMode 是整份計畫）。
  - 各有下列任一：
    - 節點編號（在目前的樹、沒放棄）。
    - 節點原文連續 8 字以上（空白不算字；不到 8 字的節點只能寫編號）。
  - 真有待放行紀錄時，放行題不算。
  - 整次全是放行題（`ask_release_only`）整次豁免。
  - 還沒有樹不記。
- **照欠／照擋**：
  - 有題沒指到（一題掛上不帶過同批其他題）→ 只記錄不擋（guard-need_goal ask_unlinked）。
  - 不分寫碼類或記憶知識類。

#### ASK_OVERVIEW_BEFORE_DECISION
**判什麼**：全貌先於拍板（只提醒）
- **不欠／放行**：
  - 題目不涉及改法選擇。
  - 題目（題目＋選項 label 與描述）提到的路徑 `ask_paths`，經 `wg_overview.read_scope_keys` 對到部位時，那些部位的 `part_files_read` 都不是 0 檔（讀了別的部位不算）。
    - 認的路徑：絕對路徑、含斜線的相對路徑（之後的段可含中文）、引號包住的整段、根目錄檔名。
    - 不算的：網址、日期、版本號、節點編號、單一字元的 A/B。
    - 相對路徑照 session cwd 解。
  - 題目沒提路徑，或提的路徑不在部位表時，退回看本 session `part_files_read` 不全空。
- **照欠／照擋**：
  - 觸發條件：
    - ExitPlanMode。
    - 或題目含改法／做法／方案／寫法／實作／架構／重構／設計，而題目提到的部位有一個讀過 0 檔（證據行「題目提到 <路徑>→部位 <名>，本回合該部位讀過 0 檔」）。
    - 或退回判定時 `part_files_read` 全空。
  - 觸發後擋訊息或提示多一句「先讀過部位檔再問」，不單獨擋。
  - 觸發導讀卡的那一次讀檔不記進 `part_files_read`（與改檔閘同一套）。

#### LOCATE_LINES_NEED_CRITIQUE
**判什麼**：有目標樹時改寫碼部位的定位第五行「批判」
- 補充：`wg_overview.on_edit` 收事實，與四行同一支判定。
- **不欠／放行**：
  - 有「定位｜批判：…」，且去掉標點空白後 ≥ 8 字（`wg_release_rules.CRITIQUE_MIN_CHARS`）就算交。
  - 合不合理、為什麼、更好的做法、同類在哪怎麼寫是 AI 的判斷，閘不認固定字樣。
  - 原設計者 G6：需要判斷的事不寫成固定規則；007 實測真批判被「更好的做法」字樣判沒交。
- **照欠／照擋**：
  - 沒交、照抄範本、太短。
  - 缺的與四行的缺項一起列。
  - 內容不過的那筆帳：
    - 真的擋，記 guard-need_goal `locate_blocked`。
    - 放行（同回合擋過一次、擋次上限），記 `locate_soft` 帶 released=哪條規則。
    - 放行訊息寫「定位缺 X，這次放行」，不寫「已擋 N 則」。

#### LOCATE_LINES_NO_EXAMPLE_PLACEHOLDER
**判什麼**：有目標樹時改寫碼部位的定位各行有沒有填（與四行、批判同一支判定）
- **不欠／放行**：
  - 各行沒留著擋訊息範例的角括號佔位（角括號裡有中文說明，如 `<第一個根因>`）。
  - 程式的泛型角括號（`List<int>`）不算。
- **照欠／照擋**：照抄範例不換佔位 → 當沒填，只記錄不擋（guard-need_goal locate_soft）

### 驗證範圍：哪些改檔作廢收據

#### SCOPE_EDIT_RELATED_TO_ITEM
**判什麼**：驗證範圍一項的收據要晚於哪些改檔
- **不欠／放行**：
  - 程式檔一律算（測試案例檔、宣告了 `depends` 的項目例外，見下兩個區塊）。
  - 不是程式檔的，只有跟這一項有關才算：
    - 同部位。
    - 在它點名的路徑或宣告的 `inputs` 底下。
    - 它就是那部位量尺。
    - 整體驗證或看不出跑了什麼。
- **照欠／照擋**：不是程式檔、也跟這一項無關的改檔，不作廢它的收據（改 `_staging` 的計畫文件不必重跑程式測試）

#### SCOPE_CASE_EDIT_ONLY_ITS_ITEM
**判什麼**：改了測試案例檔要重跑哪幾項
- **不欠／放行**：
  - 案例檔是量具不是受測物。成立條件：
    - 符合 `verify_case_globs`。
    - 不是 conftest／`__init__`。
    - 同資料夾沒有別的程式 import 它（`wg_verify_scope._standalone_case`）。
  - 成立時，只作廢這些項目：
    - 點名它的（在它點名的路徑底下）。
    - 它所在部位的量尺。
    - 整體驗證或看不出跑了什麼的項目。
- **照欠／照擋**：
  - 被同資料夾 import 的案例檔（共用 Sandbox、fixture）與 conftest 照程式檔算，每一項都要重跑。
  - 跨資料夾 import 案例檔不偵測。

#### SCOPE_EDIT_IN_DECLARED_DEPENDS
**判什麼**：宣告了 `depends` 的項目，改了程式要不要重跑
- **不欠／放行**：
  - 項目宣告 `depends`（這一項用到的程式檔或資料夾，LLM 判斷）。
  - 只有下列改動才作廢：
    - 改到依賴裡的。
    - 改到它點名的路徑底下的。
    - 改到它 `case_for` 列的。
    - 改到共用測試設施（conftest／`__init__`／被 import 的案例檔）。
- **照欠／照擋**：
  - 依賴以外的程式改動不作廢它。
  - 沒宣告 `depends` 照 [SCOPE_EDIT_RELATED_TO_ITEM](#scope_edit_related_to_item) 區塊一律算（「改完要重跑」的訊息會提示可以宣告）。
  - 漏列就漏驗，之後紅了由範圍漏判記下。

#### SCOPE_RED_ONLY_ITS_CASES
**判什麼**：一條指令跑好幾項、其中有紅
- **不欠／放行**：
  - 收據記下紅案（FAILED／ERROR 那幾行）與清單完不完整。
    - 完整＝紅案數等於最後結算行的 failed＋error（`wg_release_rules.red_case_facts`）。
  - 完整時，檔案／資料夾／測試節點項目只看紅案有沒有落在它底下，沒有就照算綠。
  - 背景自寫收據的 `failed_cases` 同判法。
- **照欠／照擋**：整條照算紅，當下列任一成立。
  - 清單不完整（輸出被截、不是 pytest）。
  - 指令項目。
  - exit 不是 0／1。
  - 紅案對不到存在的檔（pytest 的根不是執行目錄）。

### Stop 底部的同步擋（sync block）

#### SYNC_BLOCK_SKIPS_SYNCED
**判什麼**：Stop 底部一般 sync block 數哪些檔
- **不欠／放行**：
  - 先剔除已同步的改檔（[`handlers/stop.py`](../hooks/handlers/stop.py) `_synced_paths`）。
  - 已同步＝在 git／svn 工作區、status 乾淨、所在 git 根沒有已 commit 未 push 的。
  - [WORKTREE_NO_PUSH](#worktree_no_push) 的也算已同步。
- **照欠／照擋**：
  - 查不了版控的照算未同步。
  - 待記知識照擋。

#### SYNC_SKIPS_VANISHED_OUTSIDE_VCS
**判什麼**：同上，改過的檔已不在
- **不欠／放行**：
  - 檔已不在、往上也找不到版控根（整個移除的 git worktree、刪掉的暫存目錄）→ 沒有東西可同步。
  - 剔除並寫 stderr（`_synced_paths`）。
- **照欠／照擋**：
  - 檔還在而查不了版控的，照 [SYNC_BLOCK_SKIPS_SYNCED](#sync_block_skips_synced) 算未同步。
  - 磁碟或網路分享根連不到、往上找版控根出錯（斷線看起來也像不在）照算未同步。

#### BLOCK_LISTS_LATER_GATES
**判什麼**：擋下時附哪些「後面還會擋」
- **不欠／放行**：
  - 任一道閘經 `_piggyback` 擋下時，照目前狀態依閘序預覽這些：拐彎判斷、第二意見、知識收割、收尾自清、收尾檢核、同步還欠不欠。
  - 欠的附在 `[Guardian:AlsoOwed]` 一段（只報條數、不列檔名），讓模型一回合補齊。
  - 當下這道本身不重複列。
- **照欠／照擋**：
  - 只讀不寫、不吃預算。
  - 後面的閘另有每回合一次、擋滿放行等條件，以真正擋下為準。
  - 預覽出錯只寫 stderr。

#### PROMPT_REOPENS_DONE
**判什麼**：收尾閘看到的 phase 是不是這一回合的
- 補充：[`handlers/user_prompt_submit.py`](../hooks/handlers/user_prompt_submit.py)。
- **不欠／放行**：
  - 送進新的一則話（UserPromptSubmit，同伴訊息、背景通知也算）時，phase 是 done（上一回合收尾或 SessionEnd 設的）→ 改回 working。
  - 同時拿掉 SessionEnd 留的 `ended_at`（續接中不算已結束，面板清理不會一分鐘就刪）。
  - 當場寫回 state（後面逾時被砍也不留舊的 done）。
  - 同步提醒、底部一般擋、「還會擋」預覽照常判。
- **照欠／照擋**：
  - syncing（同步進行中）、merged（轉址）不動。
  - 擋次照舊：
    - 同步提醒每 session 最多 `sync_reminder.max_reminders` 次。
    - 底部一般擋照 [SYNC_BLOCK_NEW_ITEMS_ONLY](#sync_block_new_items_only)。
    - 寫碼守門關時，共用擋次照舊整個 session 累計。

#### SYNC_BLOCK_NEW_ITEMS_ONLY
**判什麼**：底部一般 sync block 後面回合還擋不擋
- 補充：[`handlers/stop.py`](../hooks/handlers/stop.py) `_sync_block_keys`／`_sync_block_items`。
- **不欠／放行**：
  - 待記知識、文件漂移的同一筆在前面的使用者回合擋過 → 不再擋，只印 stderr。
  - 一筆的定義：
    - 待記知識＝整段內容。
    - 文件漂移＝來源→文件，加記下的時間（解決後又漂移算新的）。
  - state `sync_block_shown`：
    - 記項目與第一次擋的回合記號（開場時間＋使用者回合序號；開場重建 state 時回合序號從頭算也不撞）。
    - 只留還欠的。
    - 重建時跟 `sync_reminder_count` 一起照搬（`session_start._CARRY_ON_REBUILD`）。
  - 「還會擋」預覽用同一個判定。
  - 收尾檢核 (g) 已交代只免同步提醒、不免這段。
- **照欠／照擋**：
  - 有新的一筆照擋。
  - 同一個使用者回合照舊可再擋（擋幾次歸 `stop_gate_max_blocks` 共用預算）。

### 驗證範圍宣告

#### SCOPE_DECLARED_FOR_CHANGE
**判什麼**：要不要宣告驗證範圍（規則；驗哪些交 LLM）
- **不欠／放行**：以下任一。
  - 沒有要宣告的改檔：只改沒量尺的知識素材、改過又還原。
  - 最新那份宣告在每個有改動的 repo 都有項目（判不出 repo 的改檔不要求）。
- **照欠／照擋**：
  - 改了程式檔或有量尺部位的檔卻沒宣告。
  - 某個有改動的 repo 沒有項目。
  - 擋訊息：列改到的檔、叫 LLM 判斷哪些有關聯會受影響、附參考量尺。

#### SCOPE_ITEM_WELL_FORMED
**判什麼**：宣告收件
- **不欠／放行**：
  - 每項目標與理由都非空。
  - 路徑樣子的目標：存在、節點查得到 def。
  - 不是路徑就當指令，且解析得了。
- **照欠／照擋**：一項不合格整份退回

### 案例宣告與收據證據

#### CASE_DECL_WELL_FORMED
**判什麼**：案例宣告收件
- **不欠／放行**：
  - `case_for` 掛在點得到案例檔的項目
  - `case_for` 列的每個路徑是程式檔，而且存在或本 session 改過（搬走的舊路徑也還欠著，要能宣告）
  - `no_case` 每筆同樣的路徑加非空理由
  - 同一個檔沒有兩邊都列
- **照欠／照擋**：整份退回
  - 掛在資料夾、整體驗證或產品檔那一項
  - 列了不存在又沒改過的檔，或不是程式的檔
  - 同檔兩邊都列

#### SCOPE_ITEM_RECEIPT_AFTER_EDIT
**判什麼**：範圍內每一項有沒有跑過
- **不欠／放行**：有一筆收據同時符合下列全部條件，或符合背景跑的自寫收據那一組
  - 一般收據：
    - 跑了這一項、對這一項綠（[SCOPE_RED_ONLY_ITS_CASES](#scope_red_only_its_cases)）
    - 晚於每個跟它有關的改檔的最後一次修改
    - 同一棵樹
    - 指令可信
  - 背景跑的自寫收據：
    - 改完才開始
    - 全綠
    - 環境沒縮範圍
    - 涵蓋這一項
- **照欠／照擋**：
  - 沒跑
  - 跑在改動之前
  - 跑紅
  - 只跑一部分
  - 換目錄
  - 環境縮範圍
  - 指令解析不了
  - 別棵樹
  - 擋訊息說最近那筆為什麼不算（不看前後接了什麼、用什麼串）

#### RECEIPT_UNPARSED_GENERAL_ONLY
**判什麼**：收據指令解析不了（heredoc、`$( )`、反引號、eval…）
- **不欠／放行**：
  - 照算一般證據，不擋：(a)(b) 指令提到改檔、(c) 有執行
  - 量尺與整體驗證只看跑了哪支、在哪棵樹、exit／哨兵
  - 不看前後接了什麼、用什麼串、輸出導去哪
- **照欠／照擋**：
  - 看不出跑了哪支：不算部位量尺、不算整體驗證
  - 本回合帶 PASS／DONE 的這種收據：每次 Stop stderr 一行
  - 留帳 guard-reconcile event=receipt_unparsed

#### CARRIED_CLAIM_ANY_TURN_RECEIPT
**判什麼**：擋滿承接下來的「修好」宣稱 (a) 認哪些收據
- **不欠／放行**：與新說的修好同一個判法，任一回合的合格 PASS 就算
  - 晚於對上改檔最後一次修改
  - 之後本 session 沒再改程式檔
  - 同根的合格 PASS
  - 碼沒動就不必為了續跑重跑
- **照欠／照擋**：PASS 之後又改了程式檔照擋

#### LAUNCHER_NOT_CODE
**判什麼**：worktree 根的一次性 git 啟動器算不算改程式（判定 `is_git_launcher_source`、事實 `wg_verify_ledger.note_git_launcher`）
- **不欠／放行**：同時符合下列條件 → 建、改、刪都不讓收據作廢、不欠案例、不數進第二意見門檻、不蓋到目標樹
  - 放在版控根、沒進版控
  - 整支只用 subprocess 跑 git
  - 其他呼叫只准 print、exit、os.chdir
  - import 只准 subprocess／sys／os／pathlib／shlex
- **照欠／照擋**：
  - 有一處不合就照算程式
  - 啟動器跑的 git 改到的檔，照 python 啟動器那套快照比對記帳

### 收尾提醒與自清

#### RELOAD_ADVICE_ALREADY_LOADED／RELOAD_ADVICE_MCP_EDITS_ONLY
**判什麼**：收尾叫使用者 Reload Window（每回合擋一次）
- **不欠／放行**：
  - 本 session（主 session＋子代理）沒改過路徑含 [`tools/workflow-guardian-mcp/`](../tools/workflow-guardian-mcp/) 的檔（哪一份工作樹都算）→ 整個不判、不列程序表
  - 收尾文字沒叫重載
  - AI 寫明「重載原因：…」（程式更新以外的理由，例如改了 MCP 啟動設定）
  - 列不出正在跑的服務程序、讀不到磁碟版本
  - 有在跑的服務沒有啟動紀錄（加這功能前啟動的舊版、別的視窗還沒重載）
  - 有在跑的服務心跳過期（睡眠後、寫不了紀錄）
  - 有任何一個服務還在跑舊程式
- **照欠／照擋**：這個 session 的每個工具服務程序都符合下列三點 → 擋一次，說明不必叫使用者重載、別的理由就寫「重載原因：…」
  - 有啟動紀錄
  - 心跳 3 分鐘內
  - 載入的程式版本都不舊於磁碟上的版本
  - 怎麼找「這個 session 的服務程序」：
    - 沿程序樹找到收尾閘所屬的 claude 程序，取它底下跑 workflow-guardian-mcp/server.js 的 node 程序
    - 每個 session 各有自己的服務
    - 找不到所屬 claude 程序才看全機
  - 啟動紀錄：
    - 每個 MCP 服務啟動時寫 `workflow/mcp-boot/<pid>.json`
    - 載入版本＝server.js 與 lib/*.js 最新修改時間
    - 每分鐘更新心跳、正常結束時刪檔
    - 程序已不在的紀錄不算
  - 不靠 session 名稱（Claude Code 沒寫進文件的命名行為）
  - 列程序約 1 秒，只在收尾文字提到重載時做

#### LEFTOVER_NEEDS_CLEANUP
**判什麼**：收尾自清（每回合擋一次）
- **不欠／放行**：
  - 沒宣告完成
  - 帳上的東西屬於下列任一種：
    - 沒合併的分支
    - 主工作樹用著的分支
    - 暫存區檔
    - 專案裡未進版控的新檔
    - gitignore 的
    - 遠端分支
    - 別的開著的 session 正在用的
    - HUD 按過保留的
    - (i)（舊格式 (d)）寫過理由的
    - 開場快照比對出來的
- **照欠／照擋**：宣告完成且帳上還有下列任一種 → 擋一次，列每一項與 [`session-artifacts.py act`](../tools/session-artifacts.py) 刪除指令、教 (i) 的 `branch:<名> — 理由` 寫法
  - 本 session 建的工作樹
  - 已合併分支（能刪，或被列出的工作樹用著）
  - 能刪的臨時 repo
  - 專案外能刪的檔案資料夾
  - 事實查法：
    - where／merged／used_by／busy 由 `aec_ledger.cleanup_facts` 現場查
    - 只在宣告完成時查
    - 只查可能成為候選的幾筆
    - 暫存區與版控根底下的檔案資料夾、遠端分支不跑 git

### 退避偵測

#### EVASION_CONTEXT_EXEMPT
**判什麼**：退避軟偵測的 context 豁免（不擋，決定標不標）
- **不欠／放行**：四件都有證據 → 不設 `evasion_flag`、不注入、收尾檢核不升紅，記 guard log `evasion_exempt`
  - 命中的不是延後到下個／新 session、之後再這一類
  - context 用量沒超過 `deferral_gate.max_context_ratio`（剛好等於門檻算還夠，和 DeferralGate 一致；量不出也不豁免）
  - 本回合沒有內容不是「無」的 (k)，也沒寫 `memory/_staging/next-phase-*.md`
  - 本回合使用者原話缺、空、或不屬於目前回合
  - 使用者叫現在做（現在／馬上／立刻／這回合／直接做／這邊做）
- **照欠／照擋**：事實由 [`handlers/stop._evasion_exempt_verdict`](../hooks/handlers/stop.py) 收

#### DEFERRAL_COVERS_EVASION_SENTENCE
**判什麼**：退縮閘擋下的那一句還要不要另記退避旗標（寫碼守門開時）
- **不欠／放行**：這次收尾新記的退避旗標命中的詞就在退縮閘擋下的那一句裡
  - 拿掉旗標（留帳 evasion event=covered_by_deferral）
  - 退避事件照留給收尾檢核對照
  - 下一則使用者訊息不再為同一句追問
- **照欠／照擋**：
  - 不是同一句的旗標照留
  - 寫碼守門關照舊

### 第二意見

#### SECOND_OPINION_REQUIRED
**判什麼**：大任務或高風險部位宣告完成要不要第二意見（G9；[`hooks/wg_second_opinion.py`](../hooks/wg_second_opinion.py) 收事實，閘在 [`handlers/stop.py`](../hooks/handlers/stop.py) SecondOpinion 段）
- **不欠／放行**：下列任一組成立
  - 沒宣告完成
  - 沒到門檻：
    - 程式檔 <4
    - 對 HEAD 改動 <150 行（`git diff --numstat HEAD`，未追蹤新檔算整檔行數；查不到 git 只看檔數）
    - 不在部位表類別 gate 的列，也沒命中 `risky_prefixes`（相對版控根，出廠空）
  - 上次審過之後沒新增欠帳：
    - 「上次審過」指：跑過、宣告不需、使用者放行（state `second_opinion_ok[sid]`），或前面回合跑完的第二意見
    - 之後的修改沒改到新的高風險檔
    - 新改的程式檔數也沒再過門檻（SECOND_OPINION_ONCE_PER_CLAIM）
  - 本回合（[TURN_SINCE_USER_PROMPT](#turn_since_user_prompt)）已跑並交件：
    - 有 `second_opinion_start`（mode=independent、kind=stage-review／evaluate）
    - `second_opinion_result` 回 done／failed／blocked
    - 本回合任一則回覆有段標題與四行（被別的閘擋下後補件那則不必重抄；行首、程式碼區塊外、標籤後有字）
- **照欠／照擋**：
  - 下列情形都不算跑過：
    - 沒跑
    - 只 start 沒取結果
    - result 還 running
    - start 沒開出 job（job_id 是 -）
    - mode／kind 不對
    - question 沒含樹根被擋
    - session 有需求目標樹而那次材料沒帶到樹（start 的 note 以「材料沒有需求目標樹」開頭）
  - 跑過但缺段標題或任一行 → 擋並點名缺哪行
  - 散文裡引用、程式碼區塊裡的宣告行與四行不算
  - 擋訊息末尾印入口：「要跑：second_opinion_start(…)→second_opinion_result；或宣告 `不需第二意見｜<理由>`」
  - 門檻數字由總控台定（`second_opinion.auto`），程式只核對事實與標籤，不評內容
  - 前面的閘擋下時也列進 `[Guardian:AlsoOwed]` 預覽

#### SECOND_OPINION_RAN_BEFORE
**判什麼**：前面回合跑完的第二意見算不算審過
- **不欠／放行**：
  - 本回合跑完（result 回 done／failed／blocked）就記下 job、回合與那時改過的高風險檔，不管有沒有宣告完成
  - 之後的回合宣告完成時拿它當上次審過的基準，符合下列任一 → 不再要第二意見與四行：
    - 之後沒再改程式
    - 之後的修改沒改到新的高風險檔，新改的程式檔數也沒再過門檻
- **照欠／照擋**：
  - 判的是跑完之後有沒有再改程式，不是有沒有換回合
  - 跑完之後才改的高風險檔不算審過

#### SECOND_OPINION_RESULT_ACROSS_TURNS
**判什麼**：start 在前面回合、本回合才取回結果算不算跑過
- **不欠／放行**：
  - 本回合 `second_opinion_result` 回 done／failed／blocked 就算本回合跑過、記 [SECOND_OPINION_RAN_BEFORE](#second_opinion_ran_before) 的基準，不管 start 在哪一回合
  - start 不在本回合時，照 result 自己帶的判：
    - mode 行是 independent
    - job_id 尾的類別是 stage-review／evaluate
    - note 行（材料有沒有帶到樹，second-opinion.js 從 status.json 印出）同 start
  - 前面回合已記成基準的 job，這回合再取一次仍是前面回合的基準（不再要四行）
- **照欠／照擋**：
  - 沒有 mode 行（找不到 job）不列不算
  - mode／類別不對、session 有樹而材料沒帶到樹不算
  - job_id 裡的 session 前 8 碼不是本 session（job 目錄是資料根共用的）→ foreign 不算
  - 開 job 之後（job_id 開頭的時間）本 session 又改過程式檔 → 沒審到後來的改動，stale 不算
  - 結果是這回合才拿到的，四行照要
  - 補題第二版第 5 回合：第 4 回合 start、第 5 回合取回 done、沒改程式仍被要求重跑

#### SECOND_OPINION_WAITING_NOT_DONE
**判什麼**：第二意見還在跑時結束回覆算不算宣告完成
- **不欠／放行**：
  - 條件：
    - 本回合開出（或本回合才取結果）的 job 還在跑（result 回 running，或 start 了還沒取結果）
    - 收尾最後一則有一行「等第二意見｜<job_id>」（行首、程式碼區塊外、完整的那個 job_id）
  - 效果：
    - 不算宣告完成：不擋、不吃擋次、不算滿足
    - 留帳 event=waiting
    - 之後取到結果（回合中背景通知叫回來、或下一回合取回）再照 [SECOND_OPINION_REQUIRED](#second_opinion_required) 判
- **照欠／照擋**：
  - 沒有這行 → 照擋（擋訊息教「直接呼叫 result 會等」與這行寫法）
  - 散文裡提到 job_id、job_id 後面多接字、程式碼區塊裡的都不算
  - `second_opinion_result` 本身等到有結果才回（每次最多 100 s，低於 Claude Code 互動模式 MCP 呼叫 120 s 轉背景），通常用不到這條
  - 補題第二版第 4 回合：start → 背景等 → 結束回覆被當宣告完成再擋，斷路器警報

#### SECOND_OPINION_BACKGROUND／SECOND_OPINION_DONE_NOTICE
**判什麼**：第二意見要不要守著等（`second_opinion_hint_background`、`wg_closing_round.so_done_notice`）
- **不欠／放行**：
  - 開關 `second_opinion.auto.background`（缺＝開）：擋訊息寫 start 後不用等、收尾還在跑寫等第二意見｜<job_id>
  - 開了的 job 記進看守：
    - 範圍：這批 start 自己回的 job_id，或收尾寫了在等哪個 job
    - 不掃 job 目錄，前 8 碼相同的別的 session 的 job 不收
  - 跑完而 AI 這批／本回合沒取回 → 下一批工具回應或收尾提醒一次（每個 job 一次，留帳 event=done_notice）
  - 開始看守時已跑完的不提醒
- **照欠／照擋**：
  - 判定、門檻、擋次不變
  - 還在跑沒寫等待行照 [SECOND_OPINION_REQUIRED](#second_opinion_required) 擋
  - 收尾寫過在等的 job，取回跑完那一回合照宣告完成判四行（不再說完成也要）

#### SECOND_OPINION_DECLINED／SECOND_OPINION_DECLINE_ACCEPTED
**判什麼**：AI 宣告不需第二意見
- **不欠／放行**：
  - 收尾一行「不需第二意見｜<理由>」（行首、程式碼區塊外），理由有文字內容、不是佔位、不是「不需要／不用／無」這類空話 → 放行
  - 留帳 `guard-second_opinion.jsonl`（event=declined、理由、程式檔數），週健檢列筆數與理由（只列不判）
  - 宣告行只看收尾最後一則（跟 [SECOND_OPINION_DECLARED_ALWAYS_LOGGED](#second_opinion_declared_always_logged) 留帳的同一則）
  - 被收下就不擋、也不走擋滿那條路
  - 四行可以在本回合較早那則，但不拿那則蓋掉收尾的宣告行
- **照欠／照擋**：
  - 理由空、佔位或空話 → 照擋
  - 補題第二版第 5 回合帳上同一秒記 declined 又記 exhausted_block：判宣告行時拿的是較早那則四行齊的回覆

#### SECOND_OPINION_DECLARED_ALWAYS_LOGGED
**判什麼**：「不需第二意見」宣告什麼時候留帳（[`handlers/stop.py`](../hooks/handlers/stop.py)，排在所有收尾閘前面）
- **不欠／放行**：
  - 收尾最後一則有理由成立的「不需第二意見｜<理由>」就記 `guard-second_opinion.jsonl` event=declined
  - 記的欄位：
    - 理由
    - 程式檔數
    - 觸發條件
    - `needed`＝閘當下要不要第二意見（null＝設定關或無法互動沒判）
  - 不管第二意見閘這回合要不要、前面的閘有沒有先擋下
  - 同一個使用者回合同一句理由只記一筆（state `second_opinion_declared` 記這回合記過的每一句全文）
- **照欠／照擋**：
  - 理由空、佔位或空話不記（照上一列擋）
  - 第四跑 C-1 第 2～5 回合的宣告因閘不要或前面的閘先擋而沒帳

#### SECOND_OPINION_FACT_TRIGGER
**判什麼**：第二意見閘進不進門（取代 [SECOND_OPINION_REQUIRED](#second_opinion_required) 的「宣告完成時」）
- **不欠／放行**：還沒到收尾的 Stop → 留帳 deferred，欠帳不消、下一次收尾照欠
  - 這個使用者回合沒交收尾那批，而且符合下列任一：
    - 最後一行是問句、這則沒宣告完成
    - 寫明之後工作還在繼續（`wg_evasion` 排除詞第一類；`wg_second_opinion.not_closing`）
- **照欠／照擋**：其餘每次收尾都照 [SECOND_OPINION_REQUIRED](#second_opinion_required) 的門檻與出口判，不看有沒有說完成詞

#### SECOND_OPINION_EXIT_FINGERPRINT
**判什麼**：一組改動只欠一次（`wg_second_opinion.fingerprint`／`mark_exit`，state `second_opinion_exit`）
- **不欠／放行**：
  - 交了出口（不需／等第二意見、跑過＋四行；出口行在所有收尾閘前面先記）之後指紋沒變（沒再改程式）→ 不欠
  - 本回合取回在等的結果除外（要四行）
- **照欠／照擋**：
  - 出口是不需或等第二意見、之後又改了程式（改 1 支也算）→ 再欠一次
  - 出口是跑過＋四行，之後的修改照 SECOND_OPINION_ONCE_PER_CLAIM

#### SECOND_OPINION_PRE_CLOSE
**判什麼**：收尾那批先附第二意見（`wg_closing_round.so_pre_close`）
- **不欠／放行**：下列任一 → 不附（照樣記交過收尾那批，留帳 event=pre_close）
  - 不欠
  - 第二意見設定關
  - headless／子代理
  - 同一個使用者回合附過且指紋沒變
- **照欠／照擋**：
  - 欠 → 附上 Stop 會擋的同一段（`owed_message`）
  - 那批沒出現或附了沒照做，Stop 照擋

### 最小地圖與拐彎判斷

#### UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP
**判什麼**：無部位表專案第一次改程式檔前要最小地圖（G14；`wg_overview._unmapped_edit` 收事實，判定 `min_map_verdict`；開關 `overview_hub.min_map.enabled`）
- **不欠／放行**：下列任一
  - 往上找得到部位表
  - 改的不是程式檔、是執行期資料或知識類
  - 同鍵（`<根>|(unmapped)<頂層目錄>`）交過
  - 交了三行（回覆文字、工具參數、thinking 都認，取最後一組三行齊的）：
    - 「地圖｜讀了：<檔清單>」：讀了至少 1 個檔，且每個都是本 session 讀過的（與 part_files_read 同源）
    - 「地圖｜上游：…」：非空（真的沒有寫「無，因為…」）
    - 「地圖｜下游：…」：非空（真的沒有寫「無，因為…」）
- **照欠／照擋**：
  - 第一次改某頂層目錄的程式檔而三行缺或留著角括號佔位 → deny
  - 放行與限制：
    - 同一個使用者回合同樣缺件擋滿 2 次後放行並留帳 edit_unmapped_capped（[GATE_DENY_CAP](#gate_deny_cap)）
    - 讀不到 transcript 驗不了三行就這次不要求（[GATE_SELF_ERROR](#gate_self_error)）
  - 擋訊息附：
    - `overview_scaffold.preview_lines` 掃表預覽（子程序、上限 `min_map.preview_timeout_s`，每根一次快取在 state；失敗照擋並寫原因）
    - 落表格式
  - 同根換頂層目錄只認上次放行之後交的地圖
  - 只看有沒有、讀過沒，不評內容

#### TURN_JUDGMENT_REQUIRED
**判什麼**：到門檻的側面數據每條要 AI 判並寫理由（G11；`wg_reading_path.turn_judgment_note` 收事實，判定 `turn_judgment_verdict`／`parse_turn_judgments`／`judgment_names`）
- **不欠／放行**：
  - 沒有條目到 `reading_path.turn_judgment` 門檻
  - 每一條都有「拐彎判斷｜對象｜存在理由與作用｜理由｜怎麼改直／合理」五欄齊的行：
    - 「不會」「這一層沒有作用」也要理由
    - 對象欄只認整名或邊界結尾 `::`／`.`／`/`／`\`／`→`，不認子字串
  - 答過的條目記名字＋內容指紋（state judged），同名同指紋的不再問
  - 量完之前又改碼的舊條目只收答案、不擋
- **照欠／照擋**：缺任一條或缺欄 → 每個使用者回合最多擋一次（改碼也不重開）
  - 擋點在寫碼查核之後、SecondOpinion 之前
  - 前面的閘擋下時列進 [BLOCK_LISTS_LATER_GATES](#block_lists_later_gates) 預覽
  - 列缺的「<kind> <name>｜<nums>」與缺哪幾欄
  - Markdown 引言與圍欄程式碼裡的行不算回答
  - 一批最多問 `max_items` 條，其餘報個數不問

#### READING_PATH_EARLY_START／TURN_JUDGMENT_PRE_CLOSE
**判什麼**：拐彎判斷的量測何時起跑、結果何時送（`wg_reading_path.early_start`／`take_early_note`、`wg_closing_round.turn_judgment_pre_close`）
- **不欠／放行**：
  - 每批工具跑完看本回合改過的程式檔指紋（只 stat），變了就照收尾那套交背景量
  - 量完的結果先存著，交收尾檢核或完整對照那批附上
  - 取走後 Stop 不再送；Stop 收到新的一批只送新的
  - 開關 `reading_path.early_start` 關 → 照舊在收尾起跑
- **照欠／照擋**：
  - 還有一批在量（量完前又改了碼）不附，留給 Stop
  - 欠項照 [TURN_JUDGMENT_REQUIRED](#turn_judgment_required) 由 Stop 核對

### 重構等值與效能

#### REFACTOR_NEEDS_EQUIVALENCE
**判什麼**：重構宣告完成要有等值證法（G7；事實在 [`handlers/stop.py _equivalence_gate`](../hooks/handlers/stop.py)，判定 `equivalence_verdict`／`proved_mutations`）
- **不欠／放行**：下列任一
  - 意圖不是 refactor
  - 本回合沒改程式檔
  - 沒宣告完成
  - 最後一次改程式檔之後有三筆 `PRESERVE_CHECK:PASS` 收據：
    - 沒紅、指令完整、指令沒自己寫哨兵字樣
    - 各帶 `--mutation order／side_effect／boundary`
    - 一筆只算最後一個
  - 收尾一行「等值證法｜不適用｜<理由>」（行首、理由有文字內容不是佔位）
- **照欠／照擋**：
  - 三類缺任一且沒有附理由的不適用宣告 → 擋並列已證哪幾類、缺哪幾類與入口
  - 吃寫碼查核預算，擋滿問使用者
  - 留帳 guard-equivalence

#### PERF_HOT_PATH_NEEDS_MEASURE
**判什麼**：重構／效能改動要答熱路徑並量（G7；判定 `hot_path_verdict`／`has_measure`）
- **不欠／放行**：下列任一
  - 意圖不是 refactor／perf
  - 沒改程式檔
  - 沒宣告完成
  - 答「熱路徑｜否｜<為什麼>」附理由
  - 答「熱路徑｜是｜<哪裡>」，而且最後一次改檔後有下列任一：
    - 量測收據（沒紅、至少一個 `DONE` 哨兵帶 k=v）
    - 一行「量測｜不做｜<理由>」
- **照欠／照擋**：
  - 沒答 → 每個使用者回合擋一次
  - 答是缺收據也缺理由、答否沒理由、「量測｜不做」沒理由 → 吃預算擋
  - 有一行答是就照是判
  - 行後留著角括號佔位不算回答

#### EQUIVALENCE_LOOP_EXPANDED
**判什麼**：三類變異寫在一條 for 迴圈裡跑（[`handlers/stop._loop_mutation_receipts`](../hooks/handlers/stop.py)，展開共用 [`lib/overview_hub.bash_for_bodies`](../lib/overview_hub.py)）
- **不欠／放行**：
  - 清單每項字面
  - 本體沒有指令位置上的 break／continue／exit／return（引號裡的字樣不算）
  - → 每份展開的本體各算一筆收據
- **照欠／照擋**：下列任一 → 不算
  - PRESERVE_CHECK PASS 行數（哨兵帳 `n`）少於展開份數
  - 有 FAIL、紅
  - 清單含 `$`／`$(…)`

#### EQUIVALENCE_NA_DECLARED_ALWAYS_LOGGED
**判什麼**：「等值證法｜不適用」宣告什麼時候留帳（[`handlers/stop.py`](../hooks/handlers/stop.py)，排在所有收尾閘前面，比照第二意見宣告）
- **不欠／放行**：
  - 理由成立就記 `guard-equivalence.jsonl` not_applicable（行、理由、needed＝等值閘這回合管不管）
  - 同回合同一行只記一筆（`_declared_once`）
- **照欠／照擋**：沒理由或佔位不記（等值閘照擋）

#### NEGATIVE_CONTROL_DECLARED
**判什麼**：刻意拿舊碼跑新測試的負向對照（[`handlers/post_tool_use._track_test_result`](../hooks/handlers/post_tool_use.py)，在 [RED_WHILE_REVERTED](#red_while_revertedretry_counts_rerun_cyclesgreen_same_case_clears) 之後；收尾入口 [`handlers/stop.py`](../hooks/handlers/stop.py) 紅測閘之前）
- **不欠／放行**：宣告格式「負向對照｜<這條指令裡的字樣>：<理由>」，兩種放法
  - 三管道或這次指令的 `#` 註解 → 這次紅記 deliberate_reds、不進 failing_tests、不計重試
  - 紅記了之後才在本回合回覆寫這一行，字樣在那筆紅存的指令（前 200 字）裡：
    - 收尾把那筆從 failing_tests 搬到 deliberate_reds
    - 留帳 `guard-testfail_scope` event=negative_control_declared
    - 不必重跑，之後的收尾不再拿它擋
    - 不管那則有沒有宣告完成都判
- **照欠／照擋**：字樣不在這條指令裡、沒理由、沒宣告 → 照記紅

### Bash 讀檔判定

#### BASH_UNREACHED_READ_NOT_COUNTED
**判什麼**：Bash 讀檔要在執行鏈上會跑到才算（[`lib/overview_hub._bash_live_text`](../lib/overview_hub.py)，不做完整 shell 解析）
- **不欠／放行**：下列照算
  - 前段是一般指令的 `&&` 後段
  - `||` 前段
  - exit 之前
  - `done` 之後
  - heredoc 內文
- **照欠／照擋**：下列 → 不算讀過
  - `||` 之後
  - 判斷指令（false、test、[、!、grep -q、command -v）接 `&&` 之後
  - break／continue 到 done
  - 開頭或串裡會跑到的 exit／return 之後

### 判準卡、口令閘與驗證批次

#### JUDGE_CARD_HASH_CATCHES_INTERPRETER
**判什麼**：改綁了 Entry 的判準卡只留帳（[JUDGE_CARD_CHANGE_NEEDS_DECLARATION](#judge_card_change_needs_declaration)）：寫入目標解析得到的出口（Edit／Write、Bash／PowerShell 解析出的目標、MCP 寫卡）每次改動每張卡記一筆
- **不欠／放行**：
  - 宣告行「改判準卡｜<卡名>：<理由>」有沒有都放行
  - 直譯器自己開檔改卡（Bash／PowerShell 跑 python／node／perl…，寫入目標解析不到）不管：不記雜湊、不事後比對
- **照欠／照擋**：不擋；只有帳（undeclared／declared／error）

#### COMMIT_ORDER_DECISION_ALWAYS_LOGGED
**判什麼**：口令閘每個判定都留帳（[`handlers/pre_tool_use.check_git_commit_order`](../hooks/handlers/pre_tool_use.py) 外層一處寫）
- **不欠／放行**：判出會 commit 之後，下列判定都記 `guard-commit_order.jsonl`
  - denied
  - order（口令字）
  - quoted（引的原句）
  - temp_exempt
  - claude_exempt
  - fail_open
  - error
- **照欠／照擋**：不是 commit 的指令不寫

#### VERIFY_FULL_RUN_NEEDS_USER_ORDER／VERIFY_SAME_BATCH_ALREADY_GREEN／VERIFY_BATCH_BLOCK_ONCE_PER_TURN
**判什麼**：驗證批次閘（PreToolUse Bash／PowerShell，判定 [`hooks/wg_verify_batch.py`](../hooks/wg_verify_batch.py)，接在口令閘之後；開關 `guard.verify_batch.enabled`，不歸寫碼守門管；子代理與裁判同樣適用）：會拖時間的整組驗證要使用者口令、同一組指令同一批改動只驗一次
- **不欠／放行**：
  - 不管的指令：
    - 不是驗證指令（pytest／`python -m pytest`、[`run_verify.py`](../run_verify.py)、`verify_*.py`／`test_*.py`／`*_test.py` 以外）
    - 解析不了（heredoc、eval、`bash -c`）
  - 整組但不會拖時間 → 放行、留帳 `reason=small`
    - 整組的認定：[`run_verify.py`](../run_verify.py) 不帶參數、pytest 沒點名檔或只給目錄且沒 -k／-m／--lf、PYTEST_ADDOPTS 沒縮範圍
    - 同一組指令最近一筆收據耗時 < `slow_run_s`（預設 120 秒；只有自寫收據記了 `started_at` 能算，session 收據算不出當不知道）
    - 且指令跑的樹底下符合 `verify_case_globs` 的測試檔 < `large_suite_files`（預設 50；數到門檻就停、`state.verify_batch_suite_files` 每根快取一筆）
  - 會拖時間而本回合使用者原話含 `full_run_keywords`（整組／全量／全部測試／run_verify）之一
    - 使用者原話取自 `turn_prompts` 經 `user_typed_prompts`，背景通知與子代理回報不算
  - 同一組指令（self_receipt 正規化：程式＋參數，直譯器選項不算）符合下列任一：
    - 第一次跑
    - 上次收據紅
    - 上次綠（無 FAIL 哨兵且結束碼 0；自寫收據 exit 0 且 failed 0）之後本 session 有改檔
      - 收據 seq 對 `modified_files.last_seq`
      - 自寫收據比 UTC 時間
      - 改檔少序號又少時間當有改
  - 同一使用者回合同一條規則已擋 1 次（第 2 次放行、留帳 released、stderr 說明）
- **照欠／照擋**：
  - 會拖時間的整組沒口令 → `✗ (r) VERIFY_FULL_RUN_NEEDS_USER_ORDER｜證據：上次耗時 N 秒／測試檔 N 支…`
  - 同一組指令上次綠、之後沒改檔 → `✗ (r) VERIFY_SAME_BATCH_ALREADY_GREEN：這批改動已驗證過｜證據：收據時間、指令、綠、改檔數`
    - 口令只開整組的門、不洗掉已驗過
  - 擋下、放行、閘錯都記 `Logs/guard-verify_batch.jsonl`

#### ORDER_UNTIL_PUSH
**判什麼**：版控口令（上GIT 等）什麼時候用掉（寫碼守門開時；判法 [`handlers/ups_gates.order_spent`](../hooks/handlers/ups_gates.py)）
- **不欠／放行**：這批作業 push 完之前、使用者還沒打字開新回合之前都有效
  - 下列都不讓它失效：
    - 只 commit
    - 背景通知開的續跑回合
    - 收尾閘逼出的補修 commit
  - 使用者自己的回合還沒結束時排隊補打的話照舊追加
- **照欠／照擋**：
  - 有一段子命令真的是 git push（不帶 `--dry-run`／`-n`）或 svn commit、對應結果沒標錯 → 用掉
    - echo、commit 訊息字樣不算
    - 收尾與口令閘判口令前都補掃 transcript
  - 續跑回合裡使用者打的第一則字算新回合
  - 寫碼守門關照舊：commit 過就用掉
  - 已知限制：
    - Python 啟動器跑的 push 認不到（撐到使用者新打字）
    - `git push; true` 這種失敗被後面指令蓋掉的會當成推送完成

#### SVN_TEST_BLOCK_OPT_IN
**判什麼**：svn 提交測試路徑閘（[§7.5](../TECH.md#75-其他守門) SvnTestBlock）
- **不欠／放行**：下列任一
  - 預設關：專案 [`overview-hub.json`](../.claude/overview-hub.json) 的 `svn_test_block.enabled` 沒開
  - 路徑參數沒有測試檔（訊息裡寫 test 不算）
  - 有一行「測試上 svn 原句：「…」」，原句逐字在使用者本回合原話裡、子句沒被否定（留帳 user_quote）
- **照欠／照擋**：開了、路徑含測試檔、沒有對得上的原句 → 擋（「不要提交測試」引了也不算）

### 點名判定與漏判記錄

#### NEGATED_MENTION_IS_NOT_NAMING／DATA_FILE_DECL_VOIDED_BY_LATER_MENTION
**判什麼**：資料檔點名與宣告帳（`wg_release_rules.prompt_names_file`／`mention_negated`、[`hooks/wg_data_file`](../hooks/wg_data_file.py)）
- **不欠／放行**：
  - 沒被否定的提及算點名
  - 宣告帳記宣告時主 transcript 位置，之後原話沒提到這個檔照用
- **照欠／照擋**：
  - 提及處被否定（同子句左邊否定字或右邊緊接否定）不算點名
  - 宣告之後原話又提到這個檔 → 舊帳作廢（declared_voided），只認那則原話之後的宣告

#### CHOICE_REASON_BELONGS_TO_CHOICE
**判什麼**：定位根因層「選 A 因為」的理由歸屬（`wg_release_rules._has_choice_reason`）
- **不欠／放行**：
  - 只用「；;。」切句
  - 理由詞同句符合下列任一 → 算選擇理由：
    - 前面有「選／採」
    - 前面沒有候選標記，且在第一個候選之後
- **照欠／照擋**：候選描述句裡的「因為」不算

#### OWN_COMMIT_CHANGES_STILL_COMPARED
**判什麼**：同一條指令改舊測試又 commit（[`hooks/wg_oldtest._snap_pairs`](../hooks/wg_oldtest.py)／`_own_commit_tests`）
- **不欠／放行**：自己 commit 的那幾筆（reflog）前後有變的測試檔也比對，改前取執行前 HEAD
- **照欠／照擋**：
  - 合併提交不算自己的
  - 讀不到 reflog 整段比

#### SCOPE_LEAK_OUTSIDE_SCOPE
**判什麼**：範圍漏判（只記錄）
- **不欠／放行**：下列任一成立就不記
  - 紅的測試在範圍內（退化不是漏判）
  - 它從沒綠過
  - 那次宣告不是在它上次綠之後、這次紅之前結案
  - 它是看到紅的 session 在它上次綠之後新寫或改過、還沒結案的案例：
    - 比上次綠那時的 git 版本：沒有這個案例或定義不同
    - 算它進行中的工作，告訴它、紅照樣進紅測清單
    - 只改同檔別的案例、判不出照記
- **照欠／照擋**：
  - 以上都不成立 → 記一筆疑似漏判，連回那次宣告
  - 看到紅的 session 自己還有沒結案的改動也照記，但標出來
  - 檢討時先查明是不是它自己造成的（不憑 session 狀態丟掉，免得漏掉別人留下的退化）

#### SCOPE_LEAK_REVIEW_BEFORE_DECLARE
**判什麼**：先檢討再宣告
- **不欠／放行**：下列任一
  - 該 repo 沒有待檢討的漏判
  - 宣告附的 reviews 逐筆交了：
    - missed 有 root_cause 與 next_time
    - unrelated 有 reason
- **照欠／照擋**：整份宣告退回
  - 有一筆沒交
  - missed 沒寫根因或下次怎麼改
  - unrelated 沒寫理由
  - verdict 不是兩種之一

### 收尾檢核欄位

#### AEC_EVIDENCE_PATH
**判什麼**：收尾檢核 (j) 證據路徑
- **不欠／放行**：下列任一
  - 本 session 沒有驗證收據
  - (j) 留空／「無」（由 PostToolUse 帶入帳本路徑）
  - 填的路徑存在
- **照欠／照擋**：有收據而 (j) 填了不存在的路徑 → 寫碼查核 (e)（目前只印 stderr，`block_letters` 沒列 e）

#### AEC_FOLLOWUPS_EMPTY
**判什麼**：收尾檢核 (k) 追蹤項
- **不欠／放行**：(k) 寫「無」或逐行追蹤項
- **照欠／照擋**：(k) 是空字串 → 寫碼查核 (e)（同上）

### 宣告類閘與追蹤帳

#### USER_DATA_FILE_NEEDS_DECLARATION
**判什麼**：改使用者既有的資料檔或設定檔（[§7.5](../TECH.md#75-其他守門) DataFileAsk；`data_file_verdict`）
- **不欠／放行**：下列任一
  - 這個 session 沒改過程式檔、這條指令也沒同時寫程式檔（`coding_session`，放行留帳 skipped_non_coding）
  - 不是資料檔
  - 本 session 新建
  - 使用者原話點名了它（記 exempt 帶原話片段）
  - 本 session 已有「動資料檔｜<路徑>：<為什麼>」
- **照欠／照擋**：四件事實都成立又沒宣告 → deny `✗ (df)`（同一個使用者回合同一個檔擋滿 2 次後放行，[GATE_DENY_CAP](#gate_deny_cap)）

#### DECL_HINT_KEEPS_EDIT_TOOLS
**判什麼**：擋 Edit／Write 要先交宣告行的閘，擋訊息怎麼教宣告放哪
- 適用的閘與入口：
  - 改資料檔：`wg_data_file._judge`／`data_file_hint`
  - 改舊測試：`wg_oldtest.hint`
  - 定位與最小地圖：`wg_overview`
  - 立樹：`wg_need_goal`
  - 共用字串：`DECL_VIA_COMMENT`／`DECL_WHERE`／`DECL_WHERE_SHORT`／`DECL_KEEP_EDIT`
- **不欠／放行**：只教一條路、而且是零模型回合的那條
  - 做法：
    - 同一則回覆裡先發一條不寫檔的 Bash／PowerShell 指令（例 `git diff --stat`）
    - 宣告行放它開頭的 `#` 註解
    - 接著就可以改檔
  - 範例寫成能照抄的樣子：
    - `# 定位｜…` 四行加一行 `git diff --stat`
    - 資料檔與地圖同樣給一行
  - 講原因：同一則裡接著呼叫工具的文字要等那則結束才進 transcript，hook 當下讀不到，寫了白寫
  - 宣告完照常用 Edit／Write 改，不要改用 Bash／PowerShell 寫檔
  - 其他管道只在本表與 [§7](../TECH.md#7-守門與收尾) 講，不出現在擋訊息與提示裡：
    - 早一則只有文字的回覆
    - need_goal set／update 的 `locate` 欄與 `data_files`
    - 程式照認
  - 009 實跑三條路並列，AI 挑了最貴的（ToolSearch 載工具、need_goal update 被拒、read、再 update）多 4 個模型回合
- **照欠／照擋**：
  - 不准出現「或寫成 Bash 指令開頭的 # 註解」「下一條 Bash 的註解」這類會被讀成改用 Bash 寫檔的說法（`verify_release_rules` 掃 hooks 全部原始碼）
  - 補題第一版 AI 照舊訊息全程用 python -c 改檔：
    - 寫入判不出目標
    - modified_files 整個 session 是空的
    - 對帳、第二意見、同步提醒都看不到改動
  - 繞閘宣告擋的就是那條 Bash 指令，宣告寫在那條指令的註解是對的，不在此列

#### ORIGIN_USER_NEEDS_QUOTE
**判什麼**：目標樹子節點標「使用者說的」（[§7.7](../TECH.md#77-需求目標樹need_goal)；`origin_user_verdict`）
- **不欠／放行**：quote（或節點文字）符合下列任一
  - 是樹上某則使用者原話的字面子串，至少 6 字
  - 是某則原話的整句
- **照欠／照擋**：對不到或只出現在同伴轉述 → 不擋，強制改成「推出來的」並提醒兩次

#### ORIGIN_SAID_INCLUDES_UNATTACHED
**判什麼**：核對原話時用哪些原話
- **不欠／放行**：樹結束期間收的、還沒掛上任何樹的原話也算核對來源
- **照欠／照擋**：—

#### OLD_TEST_CHANGE_NEEDS_DECLARATION
**判什麼**：動既有測試（[§7.5](../TECH.md#75-其他守門) OldTestDeclare；`old_test_change_verdict`）
- **不欠／放行**：下列任一
  - 只加新測試
  - 改 fixture／helper
  - 只改註解
  - 本 session 自己新加的、基線沒有的
  - 有「改舊測試｜<函式名>：<理由>」
- **照欠／照擋**：
  - 刪、改名、改斷言、加 skip、改說明而沒宣告 → deny `✗ (ot)`
  - Bash 類寫的寫完比對、擋下一個動作
  - 同一個使用者回合同一件擋滿 2 次後放行（[GATE_DENY_CAP](#gate_deny_cap)）

#### GATE_BYPASS_NEEDS_DECLARATION／GATE_BYPASS_NAMED_FILES_MERGED
**判什麼**：被病形閘擋過後的繞閘嫌疑（[§7.5](../TECH.md#75-其他守門) GateBypass）
- **不欠／放行**：
  - 病修掉了
  - 或有自成一行的「不是繞閘｜<理由>」（同一組檔、同一份內容不再問）
  - 同一個 repo 還沒 commit 成功又被病形閘擋下時，這次點名的檔與先前的合併成一份
- **照欠／照擋**：
  - 把被點名的檔移出暫存、改提交範圍、`--no-verify` 而病還在 → deny `✗ (gb)`
  - 宣告寫在該檔被點名之前不替它算數
  - 同一組檔同一個使用者回合擋滿 2 次後放行（[GATE_DENY_CAP](#gate_deny_cap)）

#### ATOM_BYPASS_HOWTO_REFUSED
**判什麼**：教人繞閘的知識卡（[§7.5](../TECH.md#75-其他守門) 繞閘卡片拒寫；`wg_gate_bypass.atom_refusal`）
- **不欠／放行**：下列任一
  - 只命中「提到閘」或「改暫存區做法」其中一個
  - 知識段第一行「不是教繞閘｜<理由>」
- **照欠／照擋**：兩個都命中又沒宣告 → 拒寫

#### JUDGE_CARD_CHANGE_NEEDS_DECLARATION
**判什麼**：改綁了 Entry 的判準卡（[§7.5](../TECH.md#75-其他守門) JudgeCardDeclare；`judge_card_verdict`）：只記錄不擋
- **不欠／放行**：
  - 要改的不是判準卡 → 不記。判準卡的認定：
    - 不在 memory／_atoms 底下
    - `_` 開頭
    - 磁碟上還沒有
    - 檔頭 `- Entry:` 空
  - 有宣告「改判準卡｜<卡名>：<理由>」點到這張且理由有內容 → 記 declared
- **照欠／照擋**：
  - 下列出口沒宣告 → 照放行、記 undeclared：
    - Edit／MultiEdit／Write
    - Bash／PowerShell 解析得出的寫入
    - MCP `atom_write` append／replace
    - `atom_edit_meta`
    - `atom_retire`
  - 只寫 Entry 代號不算點名

#### TRACKING_SAME_ITEM_NOT_REWRITTEN
**判什麼**：追蹤帳本同一件不重記（`wg_harvest.append_tracking`，k 欄、need_goal followup、PickOne 共用）
- **不欠／放行**：
  - 行尾寫「｜同追蹤項：<那筆裡連續至少 8 字>」對到唯一一筆未結項 → 換成新說法（新列帶 supersedes＋結案列關舊的）
  - 沒宣告但部位相同、原文相同（不分 session）→ 不重記
- **照欠／照擋**：
  - 字面相近（只差括號註、開頭相同）程式不併，照記
  - 宣告對不到或對到多筆 → 照記並 stderr

### 連鎖斷路器與 state 鎖

#### CHAIN_SAME_GATE_PER_OBJECT
**判什麼**：連鎖斷路器的「同一道閘第 2 次」怎麼數（判定在 [`hooks/wg_chain.py`](../hooks/wg_chain.py) 的 RULES，[§7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)；這一列記各閘要報什麼）
- **不欠／放行**：同一道閘擋的是不同對象 → 各算各的第 1 次（各要各的證據）。各閘報的對象：
  - 定位閘（OverviewHub）因部位欠證據擋下：
    - 報部位表那一列（專案根＋部位名）
    - 表外的檔報專案根＋同一個頂層目錄，跟它累積證據用的鍵相同
    - 加上擋的檔
    - 設定有錯、唯讀路徑、判不出部位的擋不報
  - 動資料檔（DataFileAsk）：報這次要寫的檔
  - 改舊測試（OldTestDeclare）：報這次要寫的檔，加上呼叫前還欠宣告的那幾支
- **照欠／照擋**：
  - 同一個對象（部位相同、檔有交集）照算第 2 次、照警報
  - 說不出對象的閘照閘名算：
    - 版控口令、提交隱私、病形閘、繞閘
    - 目標樹、svn 測試路徑、跨層寫入
    - 收尾各閘
  - 一次報部位一次只報檔的，也照閘名算

#### STATE_RMW_LOCKED／STATE_PENDING_MERGED
**判什麼**：平行的 hook 同時讀改寫同一份 session state 會不會互相蓋掉（判定在 [`hooks/wg_core`](../hooks/wg_core.py) state 讀寫段，[§3.1](../TECH.md#31-settingsjson-十一個事件)）
- **不欠／放行**：
  - 讀到 state 就握這個 session 的鎖到 handler 結束
    - 讀→改→寫整段在鎖裡、序號在鎖裡配，別支排隊
  - 沒進 hook 模式的寫者寫回時拿鎖，鎖裡發現檔跟自己的基準比被換過就三方合併
  - 背景萃取 worker 與 MCP signal 端點走 [`lib/state_rmw.update_state_locked`](../lib/state_rmw.py)
    - hook 模式讀改寫
    - 案例 [`lib/verify/verify_state_rmw.py`](../lib/verify/verify_state_rmw.py)：別的行程握鎖時不直接改 state 檔
- **照欠／照擋**：
  - 等鎖等到 hook 上限的一半仍拿不到、或換檔失敗：
    - 不無鎖寫、不整份覆蓋
    - 留待併帳（只記跟基準比的變動）＋stderr＋`Logs/guard-state_lock.jsonl`
  - 下一支拿到鎖的行程照欄位分型併回，帳名記進 state 後刪帳（不套兩次）
  - 待併帳也寫不出去才算真的掉，stderr＋guard log 照記

#### OLD_TEST_COMPARED_ON_FAILED_COMMAND
**判什麼**：指令非零結束時改舊測試照樣比（[§7.5](../TECH.md#75-其他守門) OldTestDeclare；`post_tool_use._old_test_after`）
- **不欠／放行**：—
- **照欠／照擋**：
  - Bash／PowerShell 非零結束時 Claude Code 只送 PostToolUseFailure：拿 PreToolUse 拍的快照照樣比
  - 例：`sed -i … tests/x.py && pytest` 紅了、改既有斷言已寫進檔又沒宣告 → 記欠帳、下一個工具呼叫擋
  - 新加的測試同一刻記進 `old_test_added`
  - 裁判子 session 不比

### 回合、完成宣告與用字

#### USER_TURN_KEY_KEPT
**判什麼**：使用者回合鍵（`turn_prompts_seq`）不掉（`session_start._CARRY_ON_REBUILD`、`ups_gates.track_turn_prompts`）
- **不欠／放行**：
  - compact／resume 重建 state 時照搬：turn_seq、turn_prompts_seq、user_turn_count、turn_open、turn_typed
  - 鍵還是不在（從零建）時：
    - 第一則進來的訊息就算是同伴訊息、背景通知也把鍵錨在這一則（不加 user_turn_count；寫碼守門關照舊不錨）
    - 之後照 [TURN_SINCE_USER_PROMPT](#turn_since_user_prompt) 前進
- **照欠／照擋**：鍵不在時 user_turn 退回逐則前進的 turn_seq，每則同伴訊息都當成新使用者回合（實測：PickOne 每則重問、各閘每回合的擋次與預算重來）

#### COMPLETION_CLAIM_PER_SENTENCE
**判什麼**：宣告完成怎麼判（`wg_evasion.claims_completion`；收割待補閘 `wg_harvest.in_progress_text` 同源）
- **不欠／放行**：同時符合下列 → 算宣告完成
  - 最後 2000 字裡沒有「這則之後工作還在繼續」的話（仍在等、等待…回報、尚未開始）
  - 有一句有完成詞
  - 那一句本身沒有其餘排除詞（還沒／尚未…完成、待補、中途、進行中）
  - 句界＝句號、驚嘆號、問號、換行，逗號、分號不切
  - 第二意見往前找宣告完成那則（`wg_second_opinion.turn_completion_text`）同一套
- **照欠／照擋**：
  - 否定、待補、中途、進行中只取消它自己那一句
  - 「三件都做完了。中途被擋了兩次」算完成、不算中途
  - 「A 完成。仍在等 B 回報。」「A1 完成；整合尚未開始」照舊不算

#### OPENING_NOTICE_NOT_TODO
**判什麼**：開場系統提示的處置句（`session_start._harvest_staged_line`）
- **不欠／放行**：寫清誰決定、要不要現在處理：「要不要現在處理由使用者決定：使用者這回合要的是別的事，只在回覆裡轉述這一行、不動這些檔；使用者說要處理，再由你逐張判斷…」
- **照欠／照擋**：寫成待辦口吻（「…不要的刪掉」）時，使用者說「先告訴我、再等我說要做什麼」AI 仍照提示刪了草稿

#### GATE_TEXT_AVOIDS_EVASION_WORDS
**判什麼**：閘的擋訊息、提示與 MCP 回給 AI 的字句用字（[§7.2](../TECH.md#72-反退避anti-evasion)「閘與 MCP 字句不中詞表」列：py 端 `verify_evasion_guard.test_gate_texts_do_not_trip_evasion_detector`、js 端 [`verify_mcp_texts_avoid_evasion_words.py`](../tools/workflow-guardian-mcp/verify/verify_mcp_texts_avoid_evasion_words.py)）
- **不欠／放行**：hooks／lib 的 Python 字串與 MCP 的 js 字串（各自的排除見 [§7.2](../TECH.md#72-反退避anti-evasion)）逐則跑 `detect_evasion` 判不出退避
- **照欠／照擋**：
  - 會中退避詞表的字句（例：DataFileAsk「(c) 非本 session 建」）改說法
  - 退避偵測不開引用豁免，AI 照抄被擋的那則會被記成退避

#### SUBPROCESS_RUN_LOOKED_UP_AT_CALL
**判什麼**：跑子行程的函式怎麼收 `run` 參數（守門案例 `verify_subprocess_run_default`）
- **不欠／放行**：預設 None、呼叫當下才取 `subprocess.run`
- **照欠／照擋**：綁成參數預設值：測試的 git 錄製重播換掉 subprocess.run 也攔不到，結果看匯入順序

#### CHAIN_HEADLESS_KEEPS_DATA_GATES
**判什麼**：沒人能答時連鎖斷路器警報之後，哪幾道閘照擋（判定在 [`hooks/wg_chain.py`](../hooks/wg_chain.py) 的 `KEEP_BLOCKING`／`keeps_blocking`，[§7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)）
- **不欠／放行**：
  - 其餘閘照 CHAIN_ABORT_RECORD_ONLY 只記錄
    - 指管做法與品質的：定位、目標樹、對帳、病形、繞閘、記憶寫入路徑這類
  - 能互動的 session 選「放行這一回合」照放
- **照欠／照擋**：下列照原擋訊息擋，讓警報響的那一次也照擋；帳上每次記一筆 kept、不算進次數
  - 動資料檔（DataFileAsk）
  - 改舊測試（OldTestDeclare）
  - commit 前的版控口令（CommitOrder）／隱私檔（GitPrivacy）／svn 測試路徑（SvnTestBlock）
  - 專案 session 改根層核心或全域 MCP（CrossRealmWriteBlock／CrossRealmBashBlock／CrossRealmMcpBlock）

### 讀檔證據

#### SHELL_READ_COUNTS_LIKE_READ
**判什麼**：唯讀 Bash／PowerShell 讀檔跟 Read 同效（`wg_overview._read_paths`／`on_read`；定位閘的讀過部位檔、需求目標的讀入範圍共用）
- **不欠／放行**：
  - 一條指令讀好幾個檔、第一次碰到部位：注入導讀卡之後的檔照記（跟送幾個 Read 一樣）
  - MSYS `/c/x` 當 `C:/x`（跟寫檔判定同一個檔）
  - 會印出命中行的 grep 不帶 -n 也算
  - 開頭 `cd <目錄> &&` 之後的相對路徑照那個目錄補
- **照欠／照擋**：
  - `grep -l／-L／-c／-q` 只印檔名、筆數或不印，帶了 -n 也不算
  - 中間的 cd 不追
  - 其餘照 [BASH_READONLY_COUNTS_AS_READ](#bash_readonly_counts_as_read)

#### INJECT_TRIGGER_READ_COUNTED
**判什麼**：觸發導讀卡注入的那次讀算不算讀過部位檔（`wg_overview.on_read`）
- **不欠／放行**：Read 或唯讀 Bash／PowerShell 第一次讀到某部位：
  - 觸發注入的那個檔也記進 part_files_read、reads_after
  - 一條指令讀到的同部位其他檔照 [SHELL_READ_COUNTS_LIKE_READ](#shell_read_counts_like_read) 全記
- **照欠／照擋**：
  - 改檔前才補注入（on_edit）沒有讀檔，不記
  - 「看過全貌才改」靠之後的定位四行守

### 定位閘與擋訊息版面

#### LOCATE_FIRST_EDIT_BLOCKS_ONCE
**判什麼**：提醒模式下定位閘唯一還會擋的地方：每部位本 session 第一次改程式檔的那一輪（`wg_overview._first_edit_once` 第一刀、`_locate_round_check` 同一輪後續；state `locate_first_deny[session][部位]`＝{turn: 第一次改的使用者回合, done: 交齊了沒}）
- **不欠／放行**：
  - 交齊（transcript 三管道或 need_goal 的 locate 欄）→ 結束這一輪、放行（`edit_round_located`），之後只看讀檔證據
  - 交了但內容不過、讀不到 transcript → 交一般判定（詳細缺件、[GATE_DENY_CAP](#gate_deny_cap)、[GATE_SELF_ERROR](#gate_self_error)）
  - 下一個使用者回合還缺 → 只提醒
  - state 記不住就只提醒
- **照欠／照擋**：
  - 第一刀定位沒交 → 擋，訊息＝卡＋一次交齊四行的要求，卡排進提醒，這一輪開始
  - 同一個使用者回合、交齊之前，同部位每個改檔（同一則平行送的也是）一行都沒交就照擋
    - 訊息只一句「同一輪，定位交齊前照擋：<檔>」
    - 不計 [GATE_DENY_CAP](#gate_deny_cap)、不記進 `overview_locate_blocked`
  - 留帳 `edit_blocked_once`／`edit_blocked_round`

#### LOCATE_BLOCK_ONCE_PER_USER_TURN
**判什麼**：定位閘一個使用者回合擋幾次（`wg_overview.on_edit`；state `overview_locate_blocked`；管的是第一輪之後）
- **不欠／放行**：同一個使用者回合已經擋過某個部位：
  - 別的部位只缺定位行 → 一行提醒、放行、留帳（`edit_locate_reminded`）
  - 同伴訊息、背景通知續跑不算新回合
- **照欠／照擋**：
  - 缺讀檔證據、導讀卡還沒注入照擋
  - 擋過的那個部位再缺照擋（[GATE_DENY_CAP](#gate_deny_cap)）
  - 下一個使用者回合重來

#### LOCATE_NOT_IN_THINKING
**判什麼**：缺定位行的擋訊息怎麼講 thinking（`wg_overview._locate_ask` 的 where）
- **不欠／放行**：—
- **照欠／照擋**：
  - 明說 thinking 預設不寫進 transcript、hook 讀不到、只寫那裡會再擋一次
  - 要放同一則先發的不寫檔指令開頭的 # 註解（DECL_WHERE；只教這一條路）

#### GOAL_VIEW_ONE_LINE
**判什麼**：目標視角重看送多少（`wg_overview._goal_view`）
- **不欠／放行**：
  - 只送一行：目標視角提問＋當前節點（`goal_view_text` 併成一行）
  - 第一次 need_goal set 也照樣觸發
- **照欠／照擋**：不重貼導讀卡、定位範本與部位表原文

#### LOCATE_EXAMPLE_ONCE_PER_SESSION
**判什麼**：有目標樹時缺定位行的擋訊息帶不帶完整範例（`wg_overview.on_edit` 的 LOCATE_ASK_ONCE 那條；state `overview_locate_example_sent`）
- **不欠／放行**：`guard.deny_text_slim` 開、本 session 已送過一則完整範例 → 那條換成短句
  - 短句內容：四行格式同第一則、放同一則先發的不寫檔指令開頭的 # 註解、thinking 讀不到
  - 缺件清單照原文比
  - 擋次上限與同批短訊息不重新計次
- **照欠／照擋**：本 session 第一則、或精簡關掉 → 照給完整範例

#### CARD_READ_WITH_EDIT_FILES
**判什麼**：指標制讀卡提示怎麼講下一步（[`lib/overview_hub._pointer_body`](../lib/overview_hub.py)、`wg_overview._card_unread_line`）
- **不欠／放行**：—
- **照欠／照擋**：
  - 指標行與讀卡缺件行都寫「下一則讀卡時順便讀要改的檔」，不再只說「可跟…同一則送」
  - 只改文字，判定不變

### 寫檔判定與連鎖斷路器

#### SHELL_WRITE_COMMAND_NOT_A_READ
**判什麼**：會寫檔的指令讀到的檔算不算讀過（`wg_overview._writes_files`，事實取 `wg_core.write_paths_from_tool`）
- **不欠／放行**：沒有寫檔目標（`2>&1`、`> /dev/null` 不算目標）
- **照欠／照擋**：
  - 有任何寫檔目標（重導向 >、tee、sed -i、Out-File…，判不出的也算）：整條讀到的檔都不算讀過、不注入導讀卡
  - 判寫檔目標出錯也當寫檔、stderr 一行

#### EPHEMERAL_WRITE_NOTED_ONCE
**判什麼**：系統暫存目錄底下的專案寫入（[`handlers/_shared.note_ephemeral_skip`](../hooks/handlers/_shared.py)，`post_tool_use` 的 Edit／Write、Bash／PowerShell、失敗指令、判不出目標補算四處）
- **不欠／放行**：—
- **照欠／照擋**：
  - 照舊不記進改檔清單
  - 同一 session、同一個專案根第一次印一行 stderr `[Guardian:EphemeralWrite]` 說明沒記、收尾閘看不到
    - 專案根的認定：版控根，沒有就 cwd，再沒有就暫存根底下第一層
    - state `ephemeral_noted_roots`，上限 20 個根，超過時最早的根之後會再說一次
  - 不在暫存根底下、只因快取目錄（__pycache__、.pytest_cache）判成暫存的不印

#### CHAIN_NO_EDIT_NO_EDGE
**判什麼**：連鎖斷路器：兩次擋之間沒改檔算不算修補（判定在 [`hooks/wg_chain.py`](../hooks/wg_chain.py) 的 `changes_files`／`link`／`same_count`，[§7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)）
- **不欠／放行**：兩次擋之間的動作都沒改到檔 → 同一道閘不接邊、不算同閘次數
  - 沒改檔的動作：重跑、沒寫入目標的指令、重交報告、改目標樹
  - 不同的閘照「沒記到動作」判
- **照欠／照擋**：
  - 中間有改檔、寫卡、子代理 → 照接、照算
  - 原樣重送被擋的呼叫照 CHAIN_SAME_CALL_RETRY

#### CHAIN_ABORT_SHOWS_REPLACED_BLOCK
**判什麼**：中止換掉的那次擋，原擋訊息送不送得到 AI（`wg_chain.notice_text`／`halt_text` 的 replaced，`chain_store.gate_fired` 傳全文）
- **不欠／放行**：—
- **照欠／照擋**：
  - 讓警報響的那一次，原擋訊息（含附註）照附在中止通知或停手訊息最後
  - 超過 2000 字留開頭並標原文長度
  - 之後的停手訊息、提醒不附

### 提示、回填與收尾組裝

#### QUOTE_FROM_USER_OPENED_TURN
**判什麼**：卡片 Quote 自動填與回填取哪則使用者原話（`wg_provenance._turn_quote`、回填的 `not_user_turn`；案例 `verify_quote_user_turn`；細節見 [§8](../TECH.md#8-可觀測與自我維護)「來源自動填」）
- **不欠／放行**：寫卡那一回合是使用者本人打字開的
  - 主 session 取 `turn_prompts` 最後一則
  - 子代理取派它那一回合的真人原話（子代理檔第一筆 `promptId` 對主檔開回合的紀錄）
  - 貼上的內容剔掉
- **照欠／照擋**：不填 Quote（Source 照補）
  - 同伴訊息、背景通知開的續跑回合（`turn_typed=False`）
  - 子代理派出的回合不是真人開的或對不到
  - 子代理檔裡的任務 prompt
  - 整則是貼上的內容

#### CRITIQUE_CASES_ONCE_PER_SESSION
**判什麼**：需求目標提示帶的三種情況（`wg_need_goal.CRITIQUE_CASES`；讀入範圍、外部主張、目標視角重看、導讀卡附樹的定位第五行提示）送全文還是指回（`critique_mark`／`critique_once`；案例 `verify_pull_goal_locate`）
- **不欠／放行**：這個 session 已送過全文（目標檔 `critique_sent`）→ 送一句指回（`CRITIQUE_CASES_POINTER`），兩問與定位第五行格式照送
- **照欠／照擋**：下列 → 送全文
  - 還沒送過
  - 壓縮後重送目標樹之後（`forget_reminders` 清掉）
  - 還沒有目標檔
  - 讀寫失敗
  - `coding_guard.slim_reminders=false`

#### TREE_LINE_IN_HINTS
**判什麼**：need_goal 以外的 hook 提示附多少目標樹（`wg_need_goal.brief_for`／`brief_line`；案例 `verify_pull_goal_locate`）
- **不欠／放行**：只附一行當前節點（沒有子節點就是樹根自己）。適用的提示：
  - 導讀卡附樹
  - 目標視角重看
  - 讀入範圍
  - 糾正
  - 外部主張
  - 每則訊息
  - 交付對照
  - 樹根與整棵樹在 need_goal set／add／update／reconcile 的回覆送
- **照欠／照擋**：
  - 壓縮後重送（`recovery_blob`）照附樹根一行＋當前節點
  - `coding_guard.slim_reminders=false` 每則附樹根一行

#### CODING_TURN_FULL_ONLY_ON_TRIGGER
**判什麼**：寫碼回合哪些記憶卡給整段（[`handlers/ups_inject.assemble_injection`](../hooks/handlers/ups_inject.py)，開關 `_lean_turn`）
- 開關 `_lean_turn` 的條件：
  - 守門總開關開
  - `wg_core.coding_turn` 為真＝這個使用者回合已改過程式檔或宣告了寫碼樹
  - 關鍵字意圖不算
  - 使用者打字開的第一則不瘦身、同回合後續 prompt 改過碼才瘦身
  - 案例 `verify_inject_lean`
- **不欠／放行**：trigger 命中的照舊：hot、同題節錄、塞不下時的印象節錄、路標
- **照欠／照擋**：
  - bm25／vector／related 命中的不看 hot／cold，一律 cold 一行（form `cold`，取用端稽核只追 trigger 的、不受影響）
  - 一行送過的卡照舊進 `injected_atoms`（搜尋段不再給它當候選、失念偵測當它注入過）
  - 之後的寫碼回合被 trigger 命中時，由 `_line_upgrades` 從全池補回候選給整段（來源記 trigger）
  - 總開關關、或不是寫碼回合照舊看 hot／cold

#### POINTER_NO_NAME_ECHO
**判什麼**：寫碼回合一行指標（cold 行、budget 退的路標）印不印摘要（`wg_atoms.title_echoes_name`）
- **不欠／放行**：摘要是印象行、或比卡名多資訊 → 照印
- **照欠／照擋**：摘要／標題去掉標點、空白、底線、大小寫與截斷的 … 後是卡名的開頭（含相同）→ 不重印，只留 `[Atom:卡名]`、Status、路徑

#### NO_RESEND_AFTER_RESUME
**判什麼**：寫碼回合同一張卡要不要再整段送（`ups_inject.delivered_forms` 的 full）
- **不欠／放行**：最近一次壓縮（`pre_compact_snapshot`／`post_compact_at`）之後沒整段送過 → 照常送。具體情形：
  - 之前只送過一行
  - 只抽了命中章節（紀錄 `sections`）
  - 壓縮前送的
  - 紀錄沒有送出時間 `at` 又有壓縮
  - 送出時間跟壓縮在一秒內
- **照欠／照擋**：
  - `injection_log` 有 form_final＝ok、`at` 晚於壓縮一秒以上 → 一行「(前面已整段送過)」指回
    - form `seen`，不算路標、AtomAudit 不追問
  - `at` 只在總開關開時記

#### DENY_TEXT_SLIM
**判什麼**：擋訊息的版面（共用組裝 `wg_release_rules.slim_deny`；採用的閘交規則名與一句修法：動資料檔 `data_file_fix`）
- **不欠／放行**：`guard.deny_text_slim=false` → 各閘原本的長文字（原處不動）
- **照欠／照擋**：
  - 第一行「[<閘>] 修法：<一句>」
  - 下面每條命中一行 `format_hit`（規則名＋現象＋證據）
    - 每項證據超過 `DENY_EVIDENCE_CAP`＝160 字截短
    - `parse_hits` 照認
  - 判準卡名由 `entry_note` 接在後面

#### CARD_FULL_ONCE_PER_SESSION
**判什麼**：判準卡同一個 session 再被問到（`wg_entrypoint.judgment_cards`／`entry_note`，紀錄 `workflow/entry-sent/<sid>.json` 的 names＋entries）
- **不欠／放行**：
  - 子代理開工句照送全文、不佔主對話
  - 壓縮前清掉紀錄（之後重送）
  - `entrypoint.card_once_per_session=false` 退回 CARD_ONCE_PER_TOPIC
- **照欠／照擋**：
  - 送過全文的卡（換回合、換目標樹都一樣）併成一行「判準卡：<卡名>、…」，不印「這個話題前面已送過全文」
  - 這個 session 拿過卡的切入點不再往下送新卡、帳上不記截斷
  - 同一則認出好幾個切入點、額度被平分到比單一額度小時：
    - 截斷送出的卡不算送過
    - 被截的切入點不算拿過卡（下次單獨被問照送）

#### DATA_FILE_READ_HINT
**判什麼**：讀到改了會被動資料檔閘問的檔（`wg_data_file.read_hint`，PostToolUse 接線在 `handle_post_tool_use` 導讀卡段之後）
- **不欠／放行**：下列任一 → 不提示
  - 這個 session 沒改過程式檔（`coding_session`：閘不會問就不提示）
  - 程式檔
  - 副檔名不在清單
  - 系統文件
  - 本 session 新建
  - 宣告過
  - state 裡的使用者原話點名
  - 提示過的檔
  - 子代理讀的
  - 閘或 寫碼守門關著
- **照欠／照擋**：
  - 讀檔結果後附一行「改 <檔> 前先宣告：動資料檔｜<路徑>：<為什麼…>（放同一則先發的不寫檔指令開頭的 `#` 註解，接著就可以改檔）」
  - 只教這一條路：早一則的回覆文字、need_goal 的 `data_files` 程式照認、不提（[DECL_HINT_KEEPS_EDIT_TOOLS](#decl_hint_keeps_edit_tools)）
  - 第二個檔起「也要先宣告（格式同前一則提示）」
  - 判定不動

#### CLOSING_RECONCILE_IN_REPORT
**判什麼**：收尾檢核帶目標對照（`post_tool_use._aec_reconcile`、[`anti-evasion.js`](../tools/workflow-guardian-mcp/lib/anti-evasion.js) `aecArgErrors`、[`mcp.js`](../tools/workflow-guardian-mcp/lib/mcp.js) schema；案例 `verify_closing_merge`、[`verify_aec_reconcile.js`](../tools/workflow-guardian-mcp/verify/verify_aec_reconcile.js)）
- **不欠／放行**：
  - anti_evasion_report 的 `reconcile` 欄＝need_goal reconcile 的 {items, turns?}
  - MCP 端同一套驗法
  - PostToolUse 交 `wg_need_goal.apply_op`（同判法、同回覆、同樣記進目標檔），先套用再附樹給 HUD
  - 報告記 `reconcile`＝applied／rejected／off／error
  - 跟 `harvest_items` 一起交＝收尾三段一次交齊
- **照欠／照擋**：
  - 套不上只少這段，收尾檢核照收，回覆寫明只補對照
  - 分開交照收
  - 總開關關不驗不套用

#### CLOSING_MISSING_PART_HINT
**判什麼**：收尾段擋下時寫缺哪段（`stop.closing_reconcile_hint`、`CLOSING_ONE_CALL`）
- **不欠／放行**：(f2) 擋時依情形寫缺哪段
  - 本回合交過收尾檢核 → 只補 need_goal reconcile
  - 沒交 → 放進收尾檢核的 reconcile 欄一次交
  - 收尾檢核閘擋訊息、「後面還會擋」預覽的收尾檢核與知識收割兩列寫一次交齊
- **照欠／照擋**：判定、擋次不變

#### CLOSING_GOAL_CODING_ONLY
**判什麼**：(f2)(f3) 何時判（`stop._verify_gates` 的 `coding`＝`handle_stop` 的 `_coding`）
- **不欠／放行**：寫碼回合才當交付邊界
  - 本回合改了程式或宣告了寫碼樹
  - 或前幾回合改過程式，這則宣告完成或本回合交了收尾檢核
- **照欠／照擋**：
  - 非寫碼回合（例：續接單匯入的舊樹、本 session 沒改程式）不要求
  - (f1)(f4) 照舊

#### CLOSING_CALL_ALL_THREE
**判什麼**：哪一批是收尾那批（`wg_closing_round.closing_call`；收尾前附著點與第二意見接縫共用）
- **不欠／放行**：下列任一支就算
  - 收尾檢核
  - need_goal action=reconcile
  - knowledge_harvest_report
- **照欠／照擋**：need_goal 其他動作不算

#### LOCATE_HINT_ON_FIRST_READ
**判什麼**：讀到部位的程式檔就先講改之前要交什麼（`wg_overview._locate_read_hint`，掛在 `on_read` 的讀檔結果，PostToolUse；立樹判式 `wg_need_goal.tree_owed_for_edit` 與 `edit_gate` 共用 `_edit_gate_applies`）
- **不欠／放行**：下列任一 → 不提示
  - 沒有改程式的意圖：
    - 既不是寫碼回合 `wg_core.coding_turn`
    - 這則 prompt 的關鍵字也沒判成寫碼類 `wg_core.CODE_INTENTS`
    - 純問答不送也不消耗額度，`locate_hint` 留在 due，之後成了寫碼回合再讀到照送
  - 改檔時才補注入的部位（擋訊息已講過）
  - 已交過定位
  - 非程式檔（含知識類部位）
  - 本 session 這個部位提示過（部位紀錄 `locate_hint`：注入時 due、送了 sent）
  - 子代理讀的
  - OverviewHub 或 寫碼守門關著
- **照欠／照擋**：讀檔結果後附一行
  - 還沒有目標樹就先講「先立需求目標樹（寫一行「目標｜…」，hook 照它立樹），再」
  - 然後「交定位四行：部位、根因層（候選 A；候選 B；選 A 因為）、前例、批判（先下合理／不合理的判斷）」（need_goal 關＝三行）
  - 放同一則先發的不寫檔指令開頭的 `#` 註解（DECL_WHERE；只教這一條路，need_goal 的 locate 欄與早一則的回覆文字程式照認、不提）
  - thinking 讀不到、宣告完照常用 Edit／Write
  - 第二個部位起只點名「（格式同前一則提示）」
  - 判定與擋訊息不動
  - 004 兩跑重播（[`_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/v6.0的代價-定位先提示-實測/locate_hint_replay.py`](../_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/v6.0的代價-定位先提示-實測/locate_hint_replay.py)）：
    - 提示都出在第一個改檔之前
    - AI 照做時那一段被擋重做（每跑 4 次呼叫）不發生

### 各閘的閘級規則（照程式 `RULES` 原文）

這幾條是各道閘本身的規則名（擋訊息與 `RULE_MODE` 用的名字），內容照 [`hooks/wg_release_rules.py`](../hooks/wg_release_rules.py) 的 `RULES` 原文列出。

#### COMMIT_SMELL_NEW_BLOCKS
**程式原文**：commit／svn commit 那刻，這次提交新寫進的病形（巢狀過深、匿名區塊過長…，判法在 tools/project-smells.py check_commit）→ 擋；拆不出要提交什麼（包在 bash -c、--git-dir、查不到的別名）判不了也擋。舊碼原本就有的只列出、不擋。判法在 handlers/pre_tool_use.check_smell_gate。

#### RED_TEST_BLOCKS_COMPLETION
**程式原文**：本 session 自己跑紅、還沒綠的測試在，收尾宣告完成 → 擋（紅測閘，handlers/stop._testfail_gate）；預算、放行、豁免照 [BLOCK_BUDGET_SHARED](#block_budget_shared)、[USER_WAIVER_NEEDS_CITATION](#not_doing_declareduser_waiver_needs_citation)、[BASE_RED_TRACKED_NOT_OWED](#base_red_tracked_not_owed)。紅只在宣告完成的收尾才被拿出來判：沒宣告完成的回合不判、也不算判過不算，那筆紅照留，之後哪個回合宣告完成就擋（改完程式跑紅、之後沒再跑綠，不管隔幾回合照擋）。判過不算的一律落帳、之後的收尾不再拿它擋：使用者放行記 user_released（[RELEASE_COVERS_SHOWN_ITEMS](#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)）、不做行記 testfail_waivers（[USER_WAIVER_NEEDS_CITATION](#not_doing_declareduser_waiver_needs_citation)）、收尾寫的負向對照宣告把那筆搬到 deliberate_reds（[NEGATIVE_CONTROL_DECLARED](#negative_control_declared) 收尾入口）。同一條指令跑了不只一次測試的紅在記帳時就定案（[RED_LAST_RESULT_IN_COMMAND](#red_last_result_in_command)），不等收尾。擋訊息抬頭「還有 N 支沒跑綠」只在真的有綠掉幾支時附「（M 支已綠）」。

#### CODE_EDIT_NEEDS_GOAL_TREE
**程式原文**：改程式檔時這個需求還沒有目標樹（wg_need_goal.edit_gate）：寫碼守門開時提醒一行 need_goal set，不擋。｜目標樹只立一次（[GOAL_TREE_SET_ONCE](#goal_tree_set_once)）：need_goal 只在改程式前提醒 set 一次；改程式檔那則不再提醒 reconcile／verify_scope，收尾檢核的提醒不寫目標對照。｜擋／提醒訊息教的是寫「目標｜…」行（子目標每件一行「子目標｜…」），放同一則先發的不寫檔指令開頭的 # 註解（DECL_WHERE；只教這一條路），改檔時 hook 照它立樹（[TREE_SET_VIA_TEXT](#tree_set_via_text)）；need_goal(action=set) 程式照收、訊息不提。

#### OVERVIEW_CARD_BEFORE_EDIT
**程式原文**：改某部位的檔時本 session 還沒看過這個部位的導讀卡（wg_overview.on_edit 的 not_injected）：提醒、卡隨改檔結果送到。

#### OVERVIEW_CARD_MISSING
**程式原文**：部位表列了導讀卡、卡檔卻找不到（wg_overview.on_edit 的 card_missing）：提醒列出找過哪裡。

#### OVERVIEW_PART_FILES_READ
**程式原文**：改某部位的檔前要讀過這個部位的檔與卡指到的檔（min_overview_evidence，wg_overview.on_edit 的 evidence）：提醒、不擋。

#### COMMIT_GOAL_RECONCILED
**程式原文**：commit 前目前寫碼類樹的完整對照 (f2) 與改到的部位掛目標 (f3)（wg_need_goal.commit_gate）：提醒、不擋。

#### DEFERRAL_OF_DOABLE_WORK
**程式原文**：主任務完工、context 還夠，收尾把帶受詞、可做的事推給下個 session／獨立議題／非我造成（wg_evasion.deferral_gate_reason）。｜寫碼守門開：提醒不擋，掛在改程式檔（或觸發事實成立）那則工具結果一行（handlers/post_tool_batch.closing_reminders），Stop 只留帳 event=remind、不續跑、不開放行題；寫碼守門關照舊擋。

#### HARVEST_AT_PHASE_DONE
**程式原文**：階段完工要交知識收割清單（wg_harvest.harvest_gate_reason；背景收割開著就交背景）。｜寫碼守門開：提醒不擋，掛在改程式檔（或觸發事實成立）那則工具結果一行（handlers/post_tool_batch.closing_reminders），Stop 只留帳 event=remind、不續跑、不開放行題；寫碼守門關照舊擋。

#### HARVEST_ITEM_NEEDS_RECEIPT
**程式原文**：收割回報裡的項目要對得上寫卡收據（wg_harvest.pending_gate_reason）。｜寫碼守門開：提醒不擋，掛在改程式檔（或觸發事實成立）那則工具結果一行（handlers/post_tool_batch.closing_reminders），Stop 只留帳 event=remind、不續跑、不開放行題；寫碼守門關照舊擋。

#### CLOSING_CHECK_REQUIRED
**程式原文**：動到 core 檔或多檔、宣告完成，本回合要交收尾檢核 anti_evasion_report（handlers/stop.py ScanReport 段）。｜寫碼守門開：提醒不擋，掛在改程式檔（或觸發事實成立）那則工具結果一行（handlers/post_tool_batch.closing_reminders），Stop 只留帳 event=remind、不續跑、不開放行題；寫碼守門關照舊擋。｜目標樹只立一次（[GOAL_TREE_SET_ONCE](#goal_tree_set_once)）：need_goal 只在改程式前提醒 set 一次；改程式檔那則不再提醒 reconcile／verify_scope，收尾檢核的提醒不寫目標對照。

#### CLOSING_CHECK_MEMORY_NOT_DEFERRED
**程式原文**：收尾檢核 (d)／(h) 不得把寫 atom 推到之後（post_tool_use 判 d_pending，handlers/stop.py AEC-Pending 段）。｜寫碼守門開：提醒不擋，掛在改程式檔（或觸發事實成立）那則工具結果一行（handlers/post_tool_batch.closing_reminders），Stop 只留帳 event=remind、不續跑、不開放行題；寫碼守門關照舊擋。

#### SYNC_REMINDER_UNSYNCED
**程式原文**：本 session 改過的檔還沒 commit 或還沒 push，要照口令規則交代（handlers/stop.py SyncReminder 段；口令閘本身不在此）。｜寫碼守門開：提醒不擋，掛在改程式檔（或觸發事實成立）那則工具結果一行（handlers/post_tool_batch.closing_reminders），Stop 只留帳 event=remind、不續跑、不開放行題；寫碼守門關照舊擋。

#### SYNC_BLOCK_PENDING_ITEMS
**程式原文**：還有待記知識或文件漂移沒處理（handlers/stop.py 底部同步段，[SYNC_BLOCK_NEW_ITEMS_ONLY](#sync_block_new_items_only)）。｜寫碼守門開：提醒不擋，掛在改程式檔（或觸發事實成立）那則工具結果一行（handlers/post_tool_batch.closing_reminders），Stop 只留帳 event=remind、不續跑、不開放行題；寫碼守門關照舊擋。

#### DEEP_POSTMORTEM_ON_FAILURE
**程式原文**：這個 session 有真失敗訊號，結束前補一張完整檢討卡（handlers/stop._should_deep_postmortem）。｜寫碼守門開：提醒不擋，掛在改程式檔（或觸發事實成立）那則工具結果一行（handlers/post_tool_batch.closing_reminders），Stop 只留帳 event=remind、不續跑、不開放行題；寫碼守門關照舊擋。

#### ATOM_CONSUMPTION_AUDIT
**程式原文**：注入的指標卡要回報有沒有用到（handlers/stop._audit_pointer_atom_consumption）。｜寫碼守門開：提醒不擋，掛在改程式檔（或觸發事實成立）那則工具結果一行（handlers/post_tool_batch.closing_reminders），Stop 只留帳 event=remind、不續跑、不開放行題；寫碼守門關照舊擋。

#### EVASION_FLAG_NEXT_PROMPT
**程式原文**：收尾文字有退避語：記旗標、下一則使用者訊息時注入（wg_evasion.detect_evasion），不續跑。

#### LOCATE_BEFORE_EDIT
**程式原文**：改某部位的程式檔前要交定位行（wg_overview.on_edit 的 evidence／wrong_layer／locate_content 缺件）：寫碼守門開時提醒一行、不擋；第一次讀到該部位程式檔的讀檔結果（[LOCATE_HINT_ON_FIRST_READ](#locate_hint_on_first_read)）送過就算提醒過，之後沒交不再提醒也不擋；唯一例外：每部位本 session 第一次改程式檔的那個使用者回合、定位沒交齊 → 整輪照擋（[LOCATE_FIRST_EDIT_BLOCKS_ONCE](#locate_first_edit_blocks_once)）。

#### OVERVIEW_READONLY_PATHS
**程式原文**：寫入目標命中這一層 readonly_paths（程式產物／索引）：不在寫碼守門範圍，照擋、不注入（wg_overview.on_edit 的 readonly）。

#### OVERVIEW_HUB_UNDER_V6
**程式原文**：OverviewHub 整道（導讀卡注入、候選前 N、讀檔記錄、定位）綁寫碼守門總開關：寫碼守門關時 wg_overview._cfg 的 enabled 一律 False，不注入、不記、不擋；同事預設關寫碼守門就完全不會收到導讀卡。

#### REMIND_PENDING_IN_STATE
**程式原文**：工具前守門判成提醒的那一件先記進 state remind_pending（規則名、對象、現象、做法、順帶要注入的卡），下一個工具結果（PostToolUse）取走：該提醒的併進 additionalContext、記進 remind_sent；送過的只留帳不重送（wg_overview.remind_queue／remind_flush）。state 寫不進去就只 stderr＋留帳，不改用 PreToolUse 送。remind_sent 是**一份清單**（元素 remind_key(規則, 對象)；state 本來就一 session 一檔，不按 session 分桶），工具前守門與改程式檔那批的收尾類提醒（post_tool_batch.closing_reminders）都走 wg_overview.remind_mark 記同一份；讀到舊寫法的 dict 由 remind_sent_list 攤平，不炸。

#### GOAL_RECONCILE_AT_DELIVERY
**程式原文**：(f2) 交付前目前寫碼類樹的完整對照（need_goal reconcile；判法 wg_need_goal._f2_text）：寫碼守門開時提醒，Stop 只留帳；commit 前那份歸 [COMMIT_GOAL_RECONCILED](#commit_goal_reconciled)。｜目標樹只立一次（[GOAL_TREE_SET_ONCE](#goal_tree_set_once)）：need_goal 只在改程式前提醒 set 一次；改程式檔那則不再提醒 reconcile／verify_scope，收尾檢核的提醒不寫目標對照。

#### GOAL_TREE_SET_ONCE
**程式原文**：目標樹只立一次：改程式前還沒樹才提醒一行 need_goal set（[CODE_EDIT_NEEDS_GOAL_TREE](#code_edit_needs_goal_tree)），之後不再送任何會促使 AI 去呼叫need_goal reconcile／verify_scope 的文字：改程式檔那則工具結果不附 SCOPE_*、(f2)(f3)(f4)（post_tool_batch.closing_reminders），PostToolUse 改程式檔不問驗證範圍（原 SCOPE_ASK_ONCE_PER_CODE_TURN 拿掉），收尾檢核的提醒與預覽不寫「目標對照放 reconcile」，need_goal set 的回覆、MCP 工具說明都不寫接著對照（沒樹改知識類檔已不送提示，見 [NON_CODING_TURN_NO_NUDGE](#non_coding_turn_no_nudge)）。判定不動：Stop 照判、只留帳（[STOP_REMIND_LEDGER_ONLY](#stop_remind_ledger_only)）；交付時完整對照由程式照收據代填（RECONCILE_BY_PROGRAM）；AI 自己交的 reconcile／verify_scope 照收。寫碼守門關整道不動（照擋）。為什麼：提醒一句 AI 就多呼叫一次工具＝多一個模型回合、多載一次工具定義。｜立樹本身走文字管道（[TREE_SET_VIA_TEXT](#tree_set_via_text)）：提醒 set 那一行教的是「目標｜」行，照做的成本是零個模型回合；need_goal(action=set) 程式照收、訊息不提。

#### STOP_REMIND_LEDGER_ONLY
**程式原文**：Stop 遇到提醒類規則（gate_mode 回 remind）：判定照跑、一回合一次的記號照記，但只留帳（guard log event=remind）＋stderr 一行，不 output_block、不送 additionalContext 續跑、不開【收尾放行確認】、不記 pending_release、不吃擋滿預算、不算進連鎖斷路器的觸發；寫碼查核一批條目混了照擋與提醒的，只有照擋條目進擋訊息（handlers/stop._remind_logged；子代理與裁判收尾同一套）。

#### NON_CODING_TURN_NO_NUDGE
**程式原文**：守門「純問答與只改文件的回合不跑」的四個例外收斂：寫碼回合一律照 wg_core.coding_turn（本使用者回合改過程式檔或宣告了寫碼樹；prompt 關鍵字意圖不算）。① 沒樹改記憶知識類檔只記 untreed（之後立樹自動掛進去）、不再送「知識類也要一棵輕樹」；② 記憶注入瘦身（[CODING_TURN_FULL_ONLY_ON_TRIGGER](#coding_turn_full_only_on_trigger)）看 coding_turn，不看關鍵字意圖；③ 讀程式檔附的定位提示（[LOCATE_HINT_ON_FIRST_READ](#locate_hint_on_first_read)）只在寫碼回合或 prompt 關鍵字判成寫碼類（wg_core.CODE_INTENTS）時送，純問答不送、額度不消耗；④ 動資料檔閘（[USER_DATA_FILE_NEEDS_DECLARATION](#user_data_file_needs_declaration)）與它的讀檔提示（[DATA_FILE_READ_HINT](#data_file_read_hint)）只在這個 session 改過程式檔、或這次指令同時寫程式檔時管（wg_data_file.coding_session；讀檔提示另外在 prompt 關鍵字判成寫碼類時也先送，提示要趕在第一次改檔前），否則放行、留帳 skipped_non_coding。第一則訊息的「要改碼先立樹」一行（CODE_TREE_HINT）仍看關鍵字，不在此列。

#### TREE_SET_VIA_TEXT
**程式原文**：立需求目標樹走文字管道。格式：「目標｜<整個需求一句，用使用者的話，只寫目標不寫手段>」一行，之後可多行「子目標｜<一件子目標>」（一行一件；沒有可省）。管道與定位行相同（DECL_WHERE）：同一則回覆裡先發一條不寫檔的 Bash／PowerShell 指令（例如 `git diff --stat`），宣告行放在它開頭的 `#` 註解，接著就可以改檔（同一則裡接著呼叫工具的文字，hook 當下讀不到）；擋訊息與提示只教 # 註解這一條路（[DECL_HINT_KEEPS_EDIT_TOOLS](#decl_hint_keeps_edit_tools)），早一則只有文字的回覆程式照認、工具 need_goal(action=set) 照收，兩者都不出現在訊息裡；thinking 不讀、程式碼區塊裡的不算、含 <…> 的佔位句不算；同一段文字最後一個「目標｜」那組算現行。套用點：改程式檔的 PreToolUse（handlers/pre_tool_use 需求目標第一層，wg_need_goal.set_via_text 在 edit_gate 之前）：這個 session 還沒有進行中的樹、主 transcript 本使用者回合（最後一則使用者本人打字之後）或子代理檔裡有「目標｜」→ 組成與 need_goal(action=set, kind=code, goal, items=[{text}]) 等價的輸入呼叫 apply_op，state 效果與 PostToolUse 收工具呼叫相同（need_goal_code_decl_turn＝本回合）；這裡立的一定是新樹，不作廢之前交的定位、不動掃描起點（AI 多半先寫目標行、再交定位、才第一次改檔）；同一使用者回合 transcript 沒長就不重讀（state need_goal_text_scan）。留帳 Logs/guard-need_goal.jsonl event=set_via_text（拒收 set_via_text_rejected、出錯 set_via_text_error 不擋，沒樹照舊由 edit_gate 判）。同一則回覆裡的定位四行與「動資料檔｜」各走自己的解析器。
