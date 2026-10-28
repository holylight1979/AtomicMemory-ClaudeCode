"""wg_release_rules.py：放行／欠帳判定規則（純函式：不讀檔、不跑 git、不改 state）。

做什麼：「算不算同一個檔、算不算本回合、算不算自己的宣稱、欠不欠補案例、算不算改碼、算不算寫入、算不算唯讀、
要不要求 push／綜觀／口令、算不算重試」集中在這裡判。每一種情境是一條有名字的規則（RULES）；呼叫端（stop、post_tool_use、
pre_tool_use、wg_verify_ledger、wg_core、wg_overview、wisdom_engine、lib/overview_hub）只蒐集事實（state、transcript、git 結果、
檔案內容）交給這裡，擋訊息與 stderr 印命中的規則名與證據（format_hit）。
新情境＝這裡加一條規則＋hooks/verify/verify_release_rules.py 一個會紅的案例；不在呼叫端加例外，也不靠整輪不擋或放寬。
要查 git 的豁免（SNAPSHOT_SETTLED、NET_UNCHANGED、CONTENT_EQUALS_COMMITTED、COMMENT_ONLY_CHANGE、RED_WHILE_REVERTED）
由 wg_verify_ledger／post_tool_use 查完事實，規則名與條件登記在這裡。
擋訊息格式（契約，parse_hits 反解靠它）：`✗ (<字母>) <規則名>：<一句現象>｜證據：<一行一證據>`。
怎麼跑案例：python -X utf8 -m pytest -q hooks/verify/verify_release_rules.py
"""
from __future__ import annotations

import ast
import fnmatch
import hashlib
import os
import re
import shlex
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple
from wg_lazy_re import lazy_re  # 模組層樣式第一次用到才編譯（HOOK_IMPORT_ON_USE）

RULES: Dict[str, str] = {
    "SAME_FILE": "同一個檔不同寫法（反斜線／正斜線、大小寫、`..`）是同一個檔：去重、快照成員、同根比較一律用 canon_path。",
    "TURN_SINCE_USER_PROMPT": "本回合＝使用者打字開的那一回合到現在的每個 turn_seq；同伴 session 訊息、背景通知不另開回合"
                              "（收據、改檔、commit、收尾報告、收割、注入都照這個窗口算）。",
    "CLAIM_MODIFIER_NOT_OWN": "宣稱詞後面直接接「的＋名詞」（修好的 X、跑過的測試）是形容後面的東西、常是轉述，不算自己宣告完成。",
    "CASE_COVERS_CHANGE": "驗證範圍閘關掉（verify_scope.enabled=false）時的 (d)：本 session 改過的每個程式檔，要有本 session 新寫或改過、"
                          "仍存在、同根的案例檔覆蓋它：案例檔名是 test_<模組名>／verify_<模組名>／<模組名>_test，或內容提到它（檔名，"
                          "或至少 3 字的模組名，整詞、不分大小寫），或驗證範圍宣告裡"
                          "那支案例那一項的 case_for 列了它（呼叫端有給宣告時）。不比改動先後（案例紅了回頭修程式、修完不必再碰案例），"
                          "也不看有沒有跑綠（說修好要的 PASS 歸 (a)）；沒有覆蓋 → 欠補案例。開著時改看 CASE_DECLARED_FOR_CHANGE。",
    "GONE_OUTSIDE_VCS": "改過的程式檔已不存在、也不在任何版控根內（打錯路徑寫到 worktree 外又刪、worktree 被移除整根消失）"
                        "→ 算刪除、不欠：同根的案例無從補，也沒有 status 可查搬去哪。",
    "GONE_IN_GIT_NOTHING_NEW": "改過的程式檔已不存在、在 git 根內、同根 status 與本 session 提交都沒有它的副本（沒有新出現的程式檔，"
                               "或新出現的檔名與內容都和它不同）→ 算刪除、不欠。",
    "MOVED_NEW_CODE_SEEN": "改過的程式檔已不存在、同根 status 或本 session 提交出現它的副本 → 可能是搬過去了，照欠。副本＝新出現的程式檔裡"
                           "檔名相同（不分大小寫）、或內容與它最後一次寫入時相同；它沒有內容紀錄、新檔讀不到 → 判不出，全算副本。",
    "GONE_UNVERIFIABLE": "改過的程式檔已不存在、但在 svn 工作副本裡、或查 git 失敗／逾時 → 判不出去向，照欠。",
    "EXCLUDED_REGION": "屬部位表類別 knowledge 的部位（文件、記憶、信件匣；錨在專案根的最長前綴列）的檔是素材，"
                       "被 .gitignore 忽略或屬執行期資料的檔（與 RUNTIME_DATA_NO_OVERVIEW 同一判式）不是本專案程式：兩者都不算程式、"
                       "也不能拿來清帳。沒有部位表、沒標類別、追蹤中、判不出 → 照算程式。",
    "SNAPSHOT_SETTLED": "commit 那刻不欠案例、之後同根程式檔內容都回到那刻、git status 乾淨（含暫存區）→ 不重算補案例（wg_verify_ledger）。",
    "NET_UNCHANGED": "改過又原樣還原（它自己與 HEAD 相同、之後沒 commit、同根程式檔 git status 全乾淨）→ 不算改碼（wg_verify_ledger）。",
    "EXEMPTION_PEERS_CODE_ONLY": "SNAPSHOT_SETTLED、NET_UNCHANGED、COMMENT_ONLY_CHANGE 要一起比的同根改檔只看程式檔（案例檔也是程式檔）："
                                 "文件、紀錄檔、設定、資料改了或正被別的 session 改著，不擋豁免；程式檔或案例檔本身沒回到那個狀態照擋"
                                 "（wg_verify_ledger.exemption_peers）。",
    "BLOCK_BUDGET_SHARED": "寫碼查核（紅測、對帳 (a)～(d)＋驗證範圍）"
                           "每個使用者回合共用一份擋次預算（reconcile_gate.max_blocks_per_turn，預設 2，鍵 *，"
                           "不分是哪幾條規則）：同一個使用者回合擋滿就改問使用者【收尾放行確認】；收尾報告那一份（e）另計。"
                           "吃 stop_gate_max_blocks 的那份共用擋次（退縮閘、收尾檢核推遲寫卡、Reload 建議、取用稽核、"
                           "一般同步擋）每個使用者回合歸零、同一回合第 3 次放行（v6 開時；v6 關照舊，整個 session 累計）。"
                           "判法在 handlers/stop.py。",
    "COMMENT_ONLY_CHANGE": "程式檔與基準版本（本 session 沒 commit 過它時的 HEAD）用 ast 去掉註解、docstring、空白後相同，"
                           "同根其他程式檔也等於 HEAD 或只差註解 → 不算改碼；非 Python、解析不了、基準拿不到 → 照算。",
    "CONTENT_EQUALS_COMMITTED": "程式檔現在的 blob 等於另一方已提交的版本（MERGE_HEAD、main／master；指到 HEAD 或本 session 自己提交的 commit 不算）"
                                "→ 不是本 session 改碼（merge 取 theirs、退回 main 版都在此）；等於 HEAD 走 NET_UNCHANGED／SNAPSHOT_SETTLED。"
                                "例外：HEAD 是別人接在本 session 最後一次提交之上做的提交（另一個 session 或人把 main 合進這個分支，本 session 的 commit 快照"
                                "拍在那之前）、而且同根本 session 改過的程式檔（含案例）全等於 HEAD → HEAD 也算已提交版本（退回看紅再還原不欠）。",
    "INLINE_PY_READONLY": "python -c 的內嵌碼（多行也一樣）與 `python -` 從 heredoc 讀的程式（定界符加了引號、或內文沒有 $／反引號）"
                          "用 ast 靜態判：無寫檔 open 模式、無刪搬寫 API、無 subprocess／shutil／exec／eval（含 builtins.exec 這類）→ 不算寫入，放行；"
                          "import … as 取別名照判（看呼叫鏈尾的名字）。判出可能寫檔或判不了（node -e、pwsh -Command）→ 當成讀不懂"
                          "寫入目標，放行並留帳（UNKNOWN_TARGET_LOGGED）。",
    "UNKNOWN_WRITE_RECOVERED": "Bash／PowerShell 寫入目標判不出（UNKNOWN_TARGET_LOGGED 那一筆）的指令跑完後（PostToolUse 與"
                               "結束碼非 0 的 PostToolUseFailure 都算），從版控狀態補出它真的改了哪些檔、記進 modified_files（via=vcs_status），"
                               "對帳、第二意見、同步提醒照常判。真的改了＝git status／svn status 列為改動或未納管，而且 mtime 不早於"
                               "這次指令的開始時間減 0.05 秒、也不晚於現在加 2 秒（開始時間＝transcript 裡那筆 tool_use 的時戳；"
                               "同則平行送出的第一個工具常常還沒落盤，找不到就用已落盤的最後一筆紀錄的時間）：快照前就髒、"
                               "這次沒動的檔不算；本 session 已經記過的檔，內容雜湊跟上次一樣、或沒有雜湊（超過 2 MiB）而 mtime 不晚於"
                               "上次記下的時間，也不算（不刷成本回合改的）。整棵 status 超過 1.2 秒 → 只查指令文字裡點名、存在的檔"
                               "（幾個根合用 0.8 秒），同 session 之後這個根直接只查點名的。不在 git／svn 工作區、找不到開始時間、"
                               "查詢失敗 → 照舊只記未知寫入，那一筆寫明補不到的原因（unrecovered）。判法在 hooks/wg_unknown_write.recover。",
    "INLINE_FLAG_BEFORE_PROGRAM": "內嵌碼旗標（python -c／-、node -e／-p、pwsh -Command／-c／-e）只認直譯器自己的選項位置：程式（腳本、"
                                  "-m 模組、pwsh 的 -File）之後的參數屬於程式，`python x.py -C <路徑>`、`python x.py -` 不是內嵌碼；"
                                  "python／node 分大小寫、帶值的選項（python -X／-W，node -r／-C…）連值一起跳過；PowerShell 不分大小寫。"
                                  "判定在 hooks/wg_core._inline_flag_at。",
    "SHELL_LITERAL_VAR_EXPANDED": "Bash 寫入目標解析：同一條指令裡獨立一段、一定會跑的 `NAME=字面值`（或 export；前面不是 &&／|| 條件，"
                                  "不在管線、背景、子 shell 裡），之後的 $NAME／${NAME} 代換成那個值再算目標（C5：`S='<scratchpad>' && "
                                  "git show … > \"$S/old.py\"` 算得出是 scratchpad）；值不是字面（含 $、反引號、$(…)）、沒指定過、"
                                  "單引號裡的 $、指令前綴的指定（`S=x cmd \"$S\"`）、PowerShell 變數照舊判不出（UNKNOWN）。"
                                  "內嵌碼被 ast 判成可能寫檔的原因只附在它自己那段：前面已有判不出的段時不黏過去。判定在 hooks/wg_core._remember_vars／_expand_vars。"
                                  "子規則 SHELL_ENV_VAR_EXPANDED：指令裡沒碰過的環境變數（$TEMP、$TMP…；名字只以 $NAME／${NAME} 出現，"
                                  "沒有 NAME=、export／unset／read／for NAME in、${NAME:=…}，條件式的也算碰過）照 hook 行程的 os.environ 代換（同 $HOME 理）；"
                                  "環境裡沒有、大小寫不同、PWD／OLDPWD 這類 shell 自己改的、source／. ／eval 之後的段照舊判不出。判定在 hooks/wg_core._env_for_expansion。",
    "GIT_READONLY_SUBCMD": "跨層閘：指令裡每段 git 都是唯讀子命令（show、hash-object 無 -w、rev-parse、diff、log、status、ls-files、cat-file、"
                           "ls-tree、rev-list、blame、describe、branch 無改名）且沒有寫到根層的目標 → 放行；擋就留 guard-crossrealm.jsonl（帶 session_id）。"
                           "「每段 git」只算 repo 在根層（家目錄 .claude、資料根、程式碼根）的段：Bash 用寫入目標掃描器的 cd／-C 追蹤推 repo，"
                           "cd 到專案 repo 之後的 git archive 不算；repo 推不出、參數（-o、--output=、目錄）碰到根層或含展不開的變數照算；"
                           "有命令替換、git 字樣比掃描器認到的 git 段多（eval、bash -c、heredoc 裡）、GIT_DIR／GIT_WORK_TREE、PowerShell → 照舊整條每段都算。"
                           "寫入目標算不出（UNKNOWN）照擋，擋訊息說「算不出」不說「落在根層」。判定在 hooks/wg_core._root_git_segments。",
    "DOT_GIT_PATH_NOT_GIT_CALL": "跨層閘數 git 字樣、判指令有沒有 git 時，路徑裡的 `.git`（`ls repo/.git/hooks`）不算：它不是在叫 git。"
                                 "不然唯讀的 ls 會被當成「有 git、掃描器沒認到」，退回整條切段判。樣式在 hooks/wg_core._GIT_WORD_RE。",
    "SEGMENTS_SPLIT_LIKE_SHELL": "整條切段判 git 時（_shlex_segments）照 shell 切：引號裡的換行不是段界，一行的引號沒收就接下一行再切，"
                                 "`python -c \"…多行…\"` 整段是一個參數，接到最後引號仍不完整才算解析不了；引號外的換行照切段；"
                                 "`;`／`&&`／`|` 黏在字上（`a; do`、`x&&git`）也是分隔。",
    "SHELL_KEYWORD_PREFIX_STRIPPED": "段首的 shell 保留字（do、then、else、elif、if、while、until、!、{）不是命令，剝掉再認："
                                     "for／while 迴圈本體、if 分支、{ } 群組裡的寫檔命令與 git 照樣認得（寫入目標掃描器 hooks/wg_core._scan_segment"
                                     "與整條切段的 _shlex_segments 同一份字表 SHELL_PREFIX_KEYWORDS）。",
    "DELETE_FORMS_SAME_ACROSS_SHELLS": "同一件刪除換個寫法，寫入目標照樣認得：Bash 的 rm（-r 不帶值，舊碼把它當 touch -r 吃掉下一個字）、"
                                       "rmdir；PowerShell 的 Remove-Item 與別名 ri、del、erase、rd、rmdir、rm；Set-Location／sl／chdir／"
                                       "Push-Location（含 -Path、-LiteralPath）之後的相對目標照換過的目錄算。目標從管線進來（Get-Item x | Remove-Item）"
                                       "或 [System.IO.File|Directory]:: → UNKNOWN（照 UNKNOWN_TARGET_LOGGED），不是沒看到。判定在 hooks/wg_core._scan_segment。",
    "UNKNOWN_PART_KEEPS_KNOWN_TARGETS": "寫入目標掃描器：一條指令裡有判不出目標的部分（$(…) 裡有寫入、[IO.File]:: 這類內嵌碼、展不開的變數目標），"
                                        "只多記一筆 UNKNOWN，同段與別段看得懂的目標照列：`rm <核心檔> '[IO.File]::'`、"
                                        "`rm <核心檔>; echo x > \"$VAR/out\"` 舊碼只回 UNKNOWN、跨層閘放過，現在照擋。"
                                        "判定在 hooks/wg_core._scan_segment 與 _shell_write_paths。",
    "DIR_TARGET_JUDGED_BY_CONTAINER":"改檔閘逐目標判時，整個資料夾當目標（rm -rf、Remove-Item -Recurse、搬走）看它所在的上一層屬於哪個專案，"
                                      "不拿資料夾自己的專案標記（.git、_AIDocs、部位表）：刪掉整個專案資料夾不是在改那個專案的檔，拿它自己當根只會要求"
                                      "讀「(outside)」的檔、永遠讀不到。上一層是專案就照它的規則；資料夾裡的單一檔照舊。cwd 這類「我在哪」的目錄不走這條。"
                                      "判定在 hooks/wg_overview.write_target_root。",
    "GREP_CONTENT_IS_READ": "Grep 工具 output_mode=content 且 path 是一個檔 → 算讀過該檔（部位證據 part_files_read）。",
    "BASH_COMMENT_LINES_STRIPPED": "Bash 指令裡行首 # 註解行先剝掉再認讀檔命令，且每一行行首都算指令開頭（定位三行放註解不讓同條 head 失效）。",
    "WORKTREE_NO_PUSH": "改檔所在 repo 是 git worktree（common-dir ≠ git-dir）或分支沒有 upstream → 同步閘不要求 push。",
    "SYNC_BLOCK_SKIPS_SYNCED": "Stop 底部的一般 sync block 先剔除已同步的改檔再判門檻：在 git／svn 工作區、status 乾淨、所在 git 根"
                               "沒有已 commit 未 push 的（WORKTREE_NO_PUSH 不要求 push 的也算）。查不了版控的照算未同步。"
                               "判法在 handlers/stop.py 的 _synced_paths。",
    "SYNC_SKIPS_VANISHED_OUTSIDE_VCS": "Stop 底部的一般 sync block：改過的檔已不在、往上也找不到版控根（整個移除的 git worktree、刪掉的暫存目錄）"
                                       "→ 沒有任何東西可同步，不算未同步（stderr 列出）。檔還在而查不了版控的照 SYNC_BLOCK_SKIPS_SYNCED 算未同步；"
                                       "磁碟或網路分享根連不到、往上找版控根時出錯（斷線看起來也像不在）也照算未同步。"
                                       "判法在 handlers/stop.py 的 _synced_paths。",
    "PROMPT_REOPENS_DONE": "送進新的一則話（UserPromptSubmit，同伴訊息、背景通知也算）時，phase 是 done（上一回合收尾或 SessionEnd 設的）"
                           "就改回 working、拿掉 SessionEnd 留的 ended_at，當場寫回 state（後面檢索、注入逾時被砍也不留舊的 done）；"
                           "syncing（同步進行中）、merged（轉址）不動。收尾的同步提醒與底部一般 sync block 都跳過 done，"
                           "不改回的話第一回合收得乾淨之後整個 session 都不再提醒。擋次照舊：同步提醒每 session 最多 "
                           "sync_reminder.max_reminders 次，底部一般 block 照 SYNC_BLOCK_NEW_ITEMS_ONLY。判法在 handlers/user_prompt_submit.py。",
    "SYNC_BLOCK_NEW_ITEMS_ONLY": "Stop 底部的一般 sync block（待記知識、文件漂移）：同一筆在前面的使用者回合擋過就不再擋，有新的一筆才擋；"
                                 "同一個使用者回合照舊（擋幾次歸 stop_gate_max_blocks 共用預算）。一筆＝待記知識的整段內容、文件漂移的"
                                 "來源→文件加記下的時間（解決後又漂移算新的）。擋過的記在 state.sync_block_shown（項目 → 第一次擋的回合記號＝開場時間＋"
                                 "使用者回合序號，開場重建 state 回合序號從頭算也不撞；只留還欠的），重建時連同同步提醒次數一起照搬；「還會擋」預覽用同一個判定，收尾檢核 (g) 已交代只免同步提醒、不免這段。"
                                 "判法在 handlers/stop.py 的 _sync_block_keys／_sync_block_items。",
    "BLOCK_LISTS_LATER_GATES": "Stop 任一道閘擋下時，附一段照目前狀態預覽後面還會擋的閘（拐彎判斷、第二意見、知識收割、收尾自清、收尾檢核、同步），讓模型一回合補齊。"
                               "只讀不寫：不動 state、不吃預算；後面的閘另有每回合一次、擋滿放行等條件，以真正擋下為準。"
                               "判法在 handlers/stop.py 的 _later_gates。",
    "RUNTIME_DATA_NO_OVERVIEW": "寫入／刪除目標被 .gitignore 忽略、落在執行期資料目錄（workflow/state*、workflow/need-goal、Logs）、"
                                "或路徑含快取目錄（__pycache__、.pytest_cache、.mypy_cache、.ruff_cache；沒有 .gitignore 也算）"
                                "→ 不要求先讀同目錄的檔。",
    "BASH_READONLY_COUNTS_AS_READ": "Bash／PowerShell 唯讀讀檔指令（cat、head、tail、less、more、sed -n、grep -n、svn cat、git show、"
                                    "Get-Content…；一段裡每個路徑參數都算）執行成功後，字面路徑且是實檔的算讀過，與 Read 同效；"
                                    "Bash 沒加引號的 glob 照 cwd 展開成實檔再算（展不出東西不算）；`for V in 清單; do …\"$V\"…; done` 清單每項都是字面"
                                    "（沒加引號的 glob 照展開）、本體沒有 break／continue／exit／return 時逐項代進本體再認讀檔指令"
                                    "（lib/overview_hub.bash_for_bodies）；"
                                    "其他含變數（$）、清單含 $／$(…) 的迴圈、指令失敗（exit≠0）、檔不存在不算；echo／printf／ls／find 不是讀檔指令。",
    "BASH_UNREACHED_READ_NOT_COUNTED": "Bash 讀檔指令要在執行鏈上會跑到才算讀過（lib/overview_hub._bash_live_text，不做完整 shell 解析）："
                                       "照 ; 與換行切串、串內照 && ／|| 切段；|| 之後到串尾、判斷指令（false、test、[、[[、!、grep -q、"
                                       "command -v）接 && 之後到串尾、break／continue 開頭到 done、exit／return 開頭或串裡會跑到的"
                                       "exit／return 之後全部 → 不算。"
                                       "前段是一般指令的 && 後段照算（它失敗整條結束碼非零，交結束碼篩）；heredoc 內文原樣、不套這幾條。",
    "UNMAPPED_EDIT_NEEDS_READABLE_FILES":"表外檔改檔前要讀的同頂層目錄檔數＝min(設定的 part_files, 該目錄非執行期資料的既有檔數)："
                                          "目錄沒有可讀檔（只有子目錄、快取或 gitignored 產物）就不要求；有檔沒讀算欠（送法照 GATE_MODE_TABLE：v6 開提醒一次、關照擋）。",
    "TEMP_REPO_COMMIT_EXEMPT": "git commit 落在暫存目錄（系統 TEMP／TMP、scratchpad、/tmp）下的 repo → 不要求版控口令。",
    "TEMP_COPY_NOT_PROJECT": "寫入目標或跑的腳本在暫存目錄下 → 不當專案：不找部位表、不注入、不要求綜觀；量尺與對帳也不把它當收據。",
    "RED_WHILE_REVERTED": "跑紅時，受測根裡有本 session 改過的程式檔內容等於非 HEAD 的已提交版本（退回舊碼反證）→ 刻意紅：不算失敗、不計重試。",
    "RETRY_COUNTS_RERUN_CYCLES": "重試只數「同一組測試上次跑之後碼有改過、再跑仍紅」的輪數：兩次重跑之間不論改幾次、幾個檔只算一輪；"
                                 "紅之後第一次重跑就綠＝0；第一次跑別組紅不算；plan 與 direct 同門檻，兩輪升級 FixEscalation；"
                                 "刻意紅、只改計畫類檔不算。不猜改檔為了哪一組，同時修多組時沒改到的那組也算（已知限制）。",
    "GREEN_SAME_CASE_CLEARS": "跑綠的指令點名與某筆紅測同一個案例檔 → 那筆紅測清掉（不限 pytest、不看指令前綴）。",
    "MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE": "搬了含程式檔的目錄（mv、Move-Item、git mv）→ 不欠整組案例，欠兩張搬之後跑的收據："
                                           "路徑引用掃描（tools/move-dir-check.py scan 點名舊路徑，MOVE_PATH_SCAN DONE hits=0）"
                                           "與抽樣驗證（sample，MOVE_SAMPLE_CHECK PASS）；收據指令不准自己寫哨兵字樣。",
    "GREEN_NARROWED_KEEPS_UNCOVERED_RED":"綠的範圍有篩選（節點 id、-k、-m、Jest -t）時，紅掉的案例都在綠點名的節點裡才清那筆紅；"
                                          "判不了（-k 運算式、輸出沒列案例）照留，同一個篩選指令重跑除外。沒篩選照既有清帳規則。",
    "GREEN_CLEARS_ONLY_CASES_IT_RAN": "綠只清它真的跑到的紅案：綠點名了整檔或節點（沒 -k／-m 這類篩選）時，紅測摘要逐支列出的失敗"
                                      "（FAILED／ERROR 節點行）在綠點名的檔或節點裡才算跑到；全跑到才清整筆，只跑到一部分就把跑到的那幾支"
                                      "從那筆紅拿掉（cleared_units）、其餘照留；紅的輸出沒列案例時，紅點名的案例檔都在綠點名的檔裡才清。"
                                      "綠沒點名檔也沒篩選＝跑整套，照既有清帳規則；有篩選照 GREEN_NARROWED_KEEPS_UNCOVERED_RED。"
                                      "點名的範圍含目錄（選項的值不算）；同一組點名重跑全清。紅那一面：新的一次紅完整列出失敗"
                                      "（列出的支數等於結算 failed＋error）時，舊紅裡這次也跑到的那幾支以這次為準（還紅的這次照列）；"
                                      "輸出截斷或沒列的紅不動舊紅。",
    "RED_SCOPE_FROM_FULL_COMMAND": "紅測的範圍從整條指令解析、不用只存前 200 字的 cmd（handlers/post_tool_use._test_scope）：記紅時存每段測試子命令"
                                   "與它前面的換目錄（test_scope.steps，跟指令多長無關、不截斷）；判綠涵不涵蓋、紅取不取代舊紅、是不是重跑同一組，"
                                   "兩邊都用解析後的目標比。認不出測試子命令＝判不出目標（舊條目 cmd 剛好 200 字也算）：不拿片段當路徑、留帳"
                                   " guard-testfail_scope，只認原樣重跑或列得出名字的紅被跑到；擋訊息（handlers/stop._rerun_scope）對看不出是哪一支的紅"
                                   "列出解析出的每段照抄重跑，判不出或太長就給「原指令完整照跑或跑整套」。",
    "CODING_TURN_ONLY": "v6 的每回合守門（目標樹提示、目標視角重看、退避偵測、退縮閘、收尾檢核、文字評分、閱讀路徑、hook 計時帳）只在寫碼回合跑"
                        "（wg_core.coding_turn）：這個使用者回合已經改了程式檔或有判不出目標的寫入，或本回合 need_goal 宣告了寫碼樹；"
                        "prompt 的關鍵字意圖不當開關。v6 以前就有的處理（記憶注入、導讀卡、收割）照舊每回合跑；v6.coding_turn_only=false 退回每回合都跑。",
    "VCS_ROOT_UNREADABLE": "找改檔所在版控根時檔案系統出錯（OSError：權限、網路路徑斷、路徑太長）→ 讀不到不等於不在版控：判不出去向，照欠（fail-closed）。",
    # 既有對帳條目的名字（(a)(b)(c)(e)、量尺），讓每一條擋訊息都有規則名
    "CLAIM_FIXED_NEEDS_PASS": "(a) 說「修好」：有驗證範圍宣告（need_goal verify_scope）→ 認宣告範圍內任一項在跟它有關的最後一次改動之後"
                              "跑綠的收據（SCOPE_EDIT_RELATED_TO_ITEM；session 收據或背景自寫收據，不看回合、不比檔名），"
                              "該測哪些已經由 LLM 宣告，(a) 不再用另一套答案；沒宣告才退回檔名對應：對得上改檔、晚於每個對上的改檔"
                              "最後一次修改、同一棵樹的 PASS（不限本回合：舊回合的只要之後本 session 沒再改任何程式檔就算，子代理改的與"
                              "判不出目標的寫入都算改；改過就要新的 PASS，擋訊息點名改了哪個檔），或改檔部位的合格自寫收據。",
    "CLAIM_MEASURED_NEEDS_DONE": "(b) 說「量了」要有本回合能當證據的 DONE，或改檔部位的合格自寫收據。",
    "CLAIM_TRIED_NEEDS_EXEC": "(c) 說「試過／跑了」要有本回合的 Bash／PowerShell 執行。",
    "GATE_SELF_ERROR": "閘自己判定時出錯（例外、設定讀不到），不讓 AI 一直付代價：收尾閘（有擋次預算）同一個使用者回合因這個錯"
                       "擋 1 次後放行；工具前閘（出錯時常讀不到 state、無從計次）直接放行。兩者都要 stderr 一行＋guard log 記一筆"
                       " event=error（閘名、錯誤種類與訊息）。判法在 gate_self_error_verdict。",
    "GATE_DENY_CAP": "宣告類閘的擋次上限：同一個使用者回合、同一道閘、同一件缺件，擋滿 2 則回覆（wg_core.DECL_DENY_CAP；怎麼數則見 "
                     "DENY_CAP_PER_REPLY）後下一則放行並留帳，換使用者回合歸零（判法 wg_core.deny_cap）。定位閘第一輪（LOCATE_FIRST_EDIT_BLOCKS_ONCE）"
                     "一行都沒交的擋不計次。適用定位閘、最小地圖三行、動資料檔、"
                     "改舊測試、不是繞閘五處；留帳事件：動資料檔／改舊測試／不是繞閘 cap_released，定位閘 edit_deny_capped，最小地圖 "
                     "edit_unmapped_capped。舊稱 DECL_GATE_DENY_CAP、LOCATE_DENY_CAP 併入本條。",
    "DENY_CAP_PER_REPLY": "擋次上限照「則」數，不照工具呼叫數：同一則回覆裡平行送出的呼叫是送出前就決定好的，AI 還沒看到第一則擋訊息。"
                          "同一件缺件在同一則裡只算一次，那一則的其他呼叫照第一次的結果（擋就照擋）、不加次數；下一則回覆的呼叫才加。"
                          "哪一則＝這次呼叫之前最後一則 assistant 的 message.id（同 CHAIN_SAME_BATCH，lib/chain_store.batch_of）。"
                          "判不出是哪一則（子代理、transcript 讀不到、沒有 message.id）照每個呼叫算，留帳 guard-deny_cap event=batch_unknown。",
    "PICK_ONCE_PER_USER_TURN": "交付時「點出最該修」一個使用者回合問一次（wg_harvest.pick_due 看 asked_uturn、covered_uturn）；這次收尾是不是"
                               "收尾 hook 讓對話續跑出來的（stop_hook_active）不當條件：第一次收尾先被別的閘（例：紅測閘）擋下、修完續跑"
                               "收尾，照樣問這一次。交付邊界（宣告完成、交了收尾檢核、commit）也看整個使用者回合：到過的那次收尾"
                               "被後面的閘擋下也記（state pick_one[sid].boundary_uturn），之後沒被擋的那次收尾最後一則在答別的閘、"
                               "沒再說完成也照樣問。state 沒有使用者回合鍵（turn_prompts_seq）時使用者回合會退回 turn_seq、續跑就前進，"
                               "這時續跑收尾不重問已經問過的。連鎖中止中照舊不送。",
    "SVN_TEST_BLOCK_OPT_IN": "svn 提交測試路徑的閘預設關，專案設定（overview-hub.json 的 svn_test_block.enabled）開了才判；開了只看 "
                             "svn commit 的路徑參數（訊息裡寫 test 不算）；放行要有一行「測試上 svn 原句：「…」」，引的句子逐字在使用者本回合的"
                             "原話裡、而且那個子句沒被否定（「不要提交測試」引了也不算），留帳 user_quote。",
    "GATE_BYPASS_NAMED_FILES_MERGED": "同一個 repo 還沒 commit 成功又被病形閘擋下時，這次點名的檔與先前點名的合併成一份；「不是繞閘｜」宣告要寫在"
                                      "該檔被點名之後才替它算數（先寫的宣告不替後來才點名的檔放行）。",
    "PENDING_SAME_USER_TURN": "擋滿留下的待放行（寫碼查核、紅測、第二意見）只在記下它的那個使用者回合有效：使用者打字開了新回合就失效，預算重給、"
                              "不拿原宣稱重查；背景通知、同伴訊息開的續跑回合不算換回合，同一回合裡照第一次擋滿時的宣稱原話重查。"
                              "判法在 wg_release.pending_of。",
    "RELEASE_COVERS_SHOWN_ITEMS": "使用者放行：同一個使用者回合照選項字面「放行這一回合」整個放；之後的回合只沿用擋訊息列過、"
                                  "使用者看過的那幾件（對帳每條 ✗ 的規則與現象，沒有 ✗ 的段（例：判定錯誤）整段算一件；紅測是指令＋全部失敗節點）。"
                                  "原因還在就不再擋、不再問，原因消失就拿掉那件；寫碼查核在放行之後又改了檔，整份放行不再沿用；新出現的照擋。"
                                  "判法在 wg_release（release_items／keep_released）。",
    "NONINTERACTIVE_RELEASE_AT_BUDGET": "沒有人能回答放行詢問（headless／SDK 主 session、子代理、裁判子 session）：寫碼查核、紅測、"
                                        "等值證法照預算擋，擋滿就放行並留帳（主 session event=noninteractive_released，"
                                        "子代理與裁判 *_released），不叫它問、不擋到底；擋訊息不說「不能放行」。",
    "ORDER_UNTIL_PUSH": "版控口令（上GIT 等）在該批作業 push 完、或使用者打字開新回合之前持續有效（v6 開時；v6 關照舊："
                        "commit 過就用掉）。只 commit、背景通知開的續跑回合、收尾閘逼出的補修 commit 都不讓它失效；"
                        "續跑回合裡使用者打的第一則字算新回合、口令失效；使用者自己的回合還沒結束時排隊補打的話照舊追加。"
                        "push 完成＝Bash／PowerShell 指令有一段子命令真的是 git push（不帶 --dry-run／-n）"
                        "或 svn commit，對應結果沒標錯；收尾與口令閘判口令前都補掃 transcript。"
                        "判法在 handlers/ups_gates（order_spent）。",
    "RELOAD_ADVICE_MCP_EDITS_ONLY": "本 session（主 session＋子代理）"
                                    "沒改過路徑含 tools/workflow-guardian-mcp/ 的檔（哪一份工作樹都算），"
                                    "就不判 Reload 建議、不列程序表（RELOAD_ADVICE_ALREADY_LOADED 不查）。",
    "DEFERRAL_COVERS_EVASION_SENTENCE": "退縮閘這次擋下的那一句，若這次收尾新記的退避旗標命中的詞就在那一句裡，"
                                        "就拿掉旗標（留帳 evasion event=covered_by_deferral；退避事件照留給收尾檢核對照），"
                                        "下一則使用者訊息不再為同一句追問；不是同一句的旗標照留（v6 開時；v6 關照舊）。",
    "RECEIPT_UNPARSED_GENERAL_ONLY":"收據指令含解析不了的語法（heredoc、$( )、反引號、eval…）→ 看不出跑了哪支：不算部位量尺、不算整體驗證，"
                                     "照算一般證據（(a)(b) 的指令提到改檔、(c) 有執行），不擋；本回合帶 PASS／DONE 的這種收據每次 Stop "
                                     "stderr 一行並留帳 guard-reconcile event=receipt_unparsed。量尺與整體驗證只看跑了哪支、在哪棵樹、"
                                     "exit／哨兵，不看前後接了什麼、用什麼串、輸出導去哪。",
    "CARRIED_CLAIM_ANY_TURN_RECEIPT":"擋滿待放行承接到新回合的「修好」宣稱，(a) 與新回合自己說的同一個判法：任一回合、晚於對上改檔"
                                      "最後一次修改、之後本 session 沒再改程式檔、同根的合格 PASS 就算；碼沒動就不必為了換回合重跑。",
    "AEC_EVIDENCE_PATH": "(e) 收尾檢核 (j) 證據路徑缺或不存在，但本 session 有驗證收據。",
    "AEC_FOLLOWUPS_EMPTY": "(e) 收尾檢核 (k) 追蹤項是空字串（「無」才放）。",
    "RECONCILE_BLOCK_LETTERS": "寫碼查核只擋 reconcile_gate.block_letters 列出的條目字母（沒設＝全擋）；沒列的條目照判、改印 stderr "
                               "只提示不擋。live 設定只列 a（測試沒過不准說修好）與 d（改了程式要有測試），使用者拍板。",
    "CLOSING_RITUAL_SWITCHES": "收尾儀式各有開關，關掉就不擋收尾：reconcile_gate.goal_gate=false → 需求目標對照 (f1)～(f4) 與 commit 前的"
                               "目標對照不擋（目標樹照記）；aec.scan_report_gate=false → 沒交收尾檢核不擋；atom_audit.enabled=false → "
                               "卡片表態不擋。goal_gate 沒設＝不擋（設 true 才擋）；另兩個開關沒設＝照擋。",
    # 需求目標樹的完整對照（wg_need_goal 收事實、這裡判）
    "GOAL_DONE_NEEDS_CASE_OR_RECEIPT": "寫碼類目標樹標「達成」的節點，至少一筆證據是沒紅的收據（實測）或讀碼級的驗證案例；"
                                       "只有檔案、卡片、推論級案例或紅收據 → 擋，擋訊息列節點與現有每一筆證據。記憶知識類的樹不擋。",
    "GOAL_INFERRED_MAX_PARTIAL": "標「達成」的節點證據全是推論 → 擋（推論最多標部分），不分寫碼類或記憶知識類。",
    "CASE_RED_THEN_GREEN": "完整對照的案例證據，對上目標檔收據裡點名同一案例檔「先紅、之後綠」的序列 → 該筆證據記 red_then_green；"
                           "收據點名哪些案例檔在蓋號時用完整指令與它的 cwd 解成絕對路徑，指令裡換目錄或沒記 cwd 的不比。"
                           "對不上照收，對照摘要印「案例未見先紅」。只是紀錄，不是閘。",
    # G0 綜觀：動手前說出角色與兩個根因候選、收尾查改到的部位都掛到目標（wg_overview／wg_need_goal 收事實、這裡判）
    "LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES": "有需求目標樹時改寫碼部位的定位四行：第四行「定位｜目標：<節點>（<角色>）」括號內要寫"
                                                 "這一塊在目標裡的角色（非空、不是佔位句、不是節點原文照抄；幾個節點串寫「T1.1/T1.4（…）」也認）；"
                                                 "第二行「定位｜根因層」要辨識得出"
                                                 "至少兩個根因候選＋選擇理由（候選 A …；候選 B …；選 A 因為 …／第一根因 …，第二根因 …），"
                                                 "或一個候選＋「第二個不存在因為 …」。只看結構不評對錯；知識類部位不查。"
                                                 "角色那半只記錄不擋（guard-need_goal locate_soft）；根因層兩候選不夠時每個使用者"
                                                 "回合擋一則回覆（wg_core.deny_cap 上限 1；同一則回覆平行送出的改檔一起擋，"
                                                 "DENY_CAP_PER_REPLY），同回合之後只記錄。",
    "LOCATE_CANDIDATES_WITHOUT_FIXED_LABELS": "根因層那行完全沒寫「候選 A／第一根因」這類標記時，兩個以上的列舉（①②、⑴⑵、(1)(2)）、"
                                              "或寫到兩個以上不同的「<名稱>層」（這層、每層、第二層這類泛稱不算）也算候選；只有一個列舉或一層"
                                              "照舊算 0 個。有標記就只看標記。固定字樣只是建議寫法，選擇理由照樣要寫。",
    "CHOICE_REASON_BELONGS_TO_CHOICE": "根因層那行的「因為／理由／原因／由於／所以」要屬於選擇才算選擇理由：只以「；;。」切句（逗號不切），"
                                       "同一句裡理由詞前面有「選／採」（「候選」的選不算）就算；否則要同一句裡理由詞前面沒有候選標記、"
                                       "且在整行第一個候選標記之後（沒有固定標記從頭算）。「候選 A 快取層，因為沒清」是候選描述，"
                                       "第一個候選前面的「新功能，所以…」是前言，都不算；「選候選 A 因為…」「採用候選 A 的理由是…」算。",
    # G1 側觀：定位之後的批判與舉一反三（原話輯 G1 2026-10-15）
    "RELOAD_ADVICE_ALREADY_LOADED": "收尾文字叫使用者 Reload Window（重新載入視窗）→ 查這個 session 的工具服務程序（每個 session 的 claude"
                                    "程序底下各有自己的服務；找不到所屬 claude 程序就看全機）啟動時載入的程式版本：全部有紀錄、心跳 3 分鐘內、"
                                    "不舊於磁碟上的版本 → 這個建議多餘，每個使用者回合擋一次並附兩邊版本；列不出、讀不到、有服務沒紀錄或心跳過期、"
                                    "有任何一個還是舊的 → 放行；AI 寫明「重載原因：…」（程式更新以外的理由）照它的判斷。依據是程序樹與服務自己"
                                    "記的版本，不是 session 名稱（Claude Code 沒寫進文件的命名行為）；「有沒有叫人重載」用字詞找，只當觸發點。",
    "LOCATE_LINES_NEED_CRITIQUE": "有需求目標樹時改寫碼部位，定位四行之後要第五行「定位｜批判：…」：只查有沒有寫、有沒有內容"
                                  "（去掉標點空白後至少 CRITIQUE_MIN_CHARS＝8 個字），不認固定字樣：寫「合理」附原因、寫哪裡不合理、"
                                  "寫更好的做法、寫同類在哪，怎麼判是 AI 的事（原設計者 G6：需要判斷的事不寫成固定規則）。"
                                  "照抄範本不算交（lib/overview_hub.locate_values 丟掉範本句）。與定位四行同一支判定、每個部位交一次；"
                                  "知識類部位不查。",
    "LOCATE_LINES_NO_EXAMPLE_PLACEHOLDER": "有需求目標樹時改寫碼部位，定位各行（部位／根因／前例／目標／批判）還留著擋訊息範例的角括號佔位"
                                           "（角括號裡有中文說明，如 <第一個根因>）→ 當沒填，只記錄不擋（guard-need_goal locate_soft）；"
                                           "程式的泛型角括號（List<int>）不算。查的是有沒有填，不評內容。",
    "EDITED_PART_NEEDS_GOAL_NODE": "交付邊界與 commit 前：目前寫碼類目標樹上，本 session 改過程式檔的每個寫碼部位，都要在定位帳"
                                   "（目標檔 links.parts）掛到樹裡還活著的節點；沒交過、掛的節點已放棄或不在樹 → 擋，列"
                                   "「<部位>：<改的檔> 沒掛目標」並指路補交定位四行或 need_goal add 子目標。表外的檔、知識類部位、"
                                   "OverviewHub 在那一層關掉的不算。",
    # G6 階段 5：其餘固定規則改交 AI 判（字詞表與門檻只篩候選，判斷由 AI 宣告附理由、程式只核對有沒有理由並留帳）
    "CORRECTION_WORDS_ARE_HINTS": "糾正詞表（wg_friction）只是提示：使用者本人打的字命中時不直接計糾正，記成待判、UserPromptSubmit 問 AI"
                                  "「他是在糾正你嗎」；AI 在那一回合寫一行「糾正｜是：<理由>」→ 計一次；「糾正｜不是：<理由>」→ 不計"
                                  "（guard-friction event=judged 留理由）；到下一則使用者本人打的訊息還沒回 → 不計（詞表不替 AI 判）、"
                                  "留帳 undeclared 給健檢抽查沒回的比例。"
                                  "理由只查有沒有文字、不是佔位（reason_present），不評充不充分。",
    "EXTRACT_VETO_NEEDS_JUDGMENT": "決策萃取已寫成卡（confirmed_extractions）之後，使用者下一則含「否／不要記／別記／取消記憶」不再整批丟掉通知："
                                   "通知照送，另問 AI「這句是不是在否決剛記的那條」；是 → AI 用 atom_retire 撤那張卡並寫"
                                   "「否決記憶｜是：<理由>」；只是句子裡剛好有這個字（是否、否則）→「否決記憶｜不是：<理由>」；"
                                   "兩種都留帳（guard-extract_veto event=judged），沒回留 undeclared、不自動撤。",
    "CONFLICT_DECLARED_BY_AI": "寫入時衝突偵測（memory-conflict-detector write-check）的相似度門檻與本地模型標籤只篩候選：判 CONTRADICT（複驗一致）"
                               "或 EXTEND 且相似度 ≥ 門檻的候選不再自動擋寫或改道待審，atom_write 回「衝突待宣告（這次不寫檔）」列候選；"
                               "AI 帶 conflict=[{of, verdict: conflict|not_conflict, why}] 重送，要宣告的是這次向量前幾名的候選"
                               "（不同層同名寫 <layer>:<卡名>）、why 要有文字，多寫的略過不算錯："
                               "任一 conflict → 照舊落待審報告不寫 shared；全部 not_conflict → 照寫；兩種都留帳（guard-conflict_declared）。"
                               "拉取稽核本地模型沒判出結果（ERROR）時，相似度高只標候選、不標衝突。",
    "PROJECT_LITERAL_IS_HINT": "realm 閘（scope=global／org 寫入）的字面「此專案／本專案／這個專案／這專案」只是提示：命中的只有這類字樣時，"
                               "AI 帶 scope_reason（一句：為什麼這段是跨專案的，例如在講這個詞本身）→ 照寫、留帳（guard-realm_declared）；"
                               "沒帶 → 照擋並說明可宣告。專案專名、專案路徑、已登記專案名是查得到的事實，照擋、宣告不放。",
    "STATE_RMW_LOCKED": "同一個 session 的 hook 行程（同一則回覆的平行工具呼叫、共用 session_id 的子代理）讀改寫 state 要排隊："
                        "dispatcher 開 hook 模式（wg_core.begin_state_rmw），第一次讀某個 session 的 state 就拿它的鎖（state-<sid>.lock）、"
                        "握到 handler 結束，讀→改→寫整段在鎖裡，序號（event_seq）也在鎖裡配。等鎖最多等到 hook 上限的一半（起點＝行程建立）；"
                        "等不到不無鎖寫、不整份覆蓋：照讀沒上鎖的那份讓閘照判，寫回改留待併帳（state-<sid>.<時間>-<pid>.pending，只記跟這支行程的"
                        "基準比改了哪些鍵；同一支再寫只記之後的變動），stderr 與 Logs/guard-state_lock.jsonl 留訊號；換檔失敗也改留待併帳。"
                        "子規則 STATE_PENDING_MERGED：下一支拿到鎖的行程讀 state 前把待併帳照欄位分型併回（集合取聯集、業務鍵紀錄逐筆併、累加計數"
                        "兩邊都沒歸零才相加、回合與序號取大、時間取新、分版本整組新的勝、整組綁定的與判不出的留磁碟那份並記下），併過的帳名跟合併"
                        "結果同一次寫進 state（_state_pending_applied），刪不掉的下次跳過再刪，不套兩次。讀到檔不在＝讀到空 state：留的帳逐欄合併、"
                        "不當整份換掉；fallback 重建的 state 不蓋掉已存在的檔。沒進 hook 模式的寫者寫回時才拿鎖，鎖裡發現檔跟自己的基準比被換過"
                        "也照同一套三方合併。判定在 hooks/wg_core（state 讀寫段）。",
}


class Verdict(NamedTuple):
    rule: str                        # RULES 的鍵
    owed: bool                       # 照這條規則還欠不欠（要擋＝True）
    why: str                         # 一句現象（擋訊息與 stderr 原樣印）
    evidence: Tuple[str, ...] = ()   # 一行一證據


def canon_path(path: Any) -> str:
    """SAME_FILE：比對用的路徑鍵。先消掉 `.`／`..`，再統一斜線、去尾斜線、轉小寫（Windows 檔名不分大小寫）。"""
    return os.path.normpath(str(path)).replace("\\", "/").rstrip("/").lower()


def same_file(a: Any, b: Any) -> bool:
    """SAME_FILE：兩種寫法指的是不是同一個檔。"""
    return canon_path(a) == canon_path(b)


def user_turn(state: Dict[str, Any], turn_seq: int) -> int:
    """TURN_SINCE_USER_PROMPT：本回合的起點＝使用者本人打字開的那一回合（ups_gates.track_turn_prompts 記的 turn_prompts_seq，
    與 turn_seq 同一套編號）。舊 state 沒有這個欄位才用 turn_seq。"""
    v = state.get("turn_prompts_seq")
    return int(v) if isinstance(v, int) and not isinstance(v, bool) and v > 0 else int(turn_seq)


def in_turn(t: Any, turn_seq: int, since: Optional[int] = None) -> bool:
    """TURN_SINCE_USER_PROMPT：turn_seq 值 t 落在本回合。since＝user_turn 給了就是 since ≤ t ≤ turn_seq；沒給只認 t == turn_seq
    （只給舊呼叫端與單元案用）。t 不是整數 → 不算。"""
    try:
        t = int(t)
    except (TypeError, ValueError):
        return False
    return (min(int(since), int(turn_seq)) <= t <= int(turn_seq)) if since is not None else t == int(turn_seq)


def turn_start(user_since: int, session_key: str, own_mods: Iterable[Any] = (), own_receipts: Iterable[Any] = ()) -> int:
    """TURN_SINCE_USER_PROMPT 的起點。主 session＝user_since。子代理（session_key 帶 `#agent:`）這一趟可能跨好幾個使用者回合
    （背景子代理），本回合從它自己最早一筆改檔或收據算起，和 user_since 取早的那個。"""
    if "#agent:" not in str(session_key):
        return int(user_since)
    turns = []
    for rec in [*(own_mods or []), *(own_receipts or [])]:
        t = rec.get("turn_seq") if isinstance(rec, dict) else None
        if isinstance(t, int) and not isinstance(t, bool):
            turns.append(t)
    return min([int(user_since), *turns])


def in_user_turn(t: Any, state: Dict[str, Any], turn_seq: Optional[int] = None) -> bool:
    """TURN_SINCE_USER_PROMPT：呼叫端只有 state 時用（turn_seq 沒給就拿 state 的）。"""
    now = int(state.get("turn_seq", 0)) if turn_seq is None else int(turn_seq)
    return in_turn(t, now, user_turn(state, now))


_MODIFIER_TAIL_RE = lazy_re(r"^的\s*[^\s，。；！？、,.;!?：:）)」』]")


def claim_is_modifier(clause: str, end: int) -> bool:
    """CLAIM_MODIFIER_NOT_OWN：子句裡宣稱詞（結尾在 end）後面直接接「的＋名詞」→ 是形容詞用法（修好的 X），不算自己宣稱。
    「是我修好的。」（的 後面是句尾）照算宣稱。"""
    return bool(_MODIFIER_TAIL_RE.match(clause[end:]))


def excluded_region(path: Any, root: Optional[str], kind: Optional[str], gitignored: Optional[bool] = None) -> bool:
    """EXCLUDED_REGION：path 在專案根底下，而且①部位表判它屬類別 knowledge 的部位（kind＝lib/overview_hub.path_kind 的結果，
    呼叫端查完部位表傳進來），或②它是執行期資料：被 .gitignore 忽略（gitignored＝呼叫端查 git check-ignore 的結果，
    None＝查不到當不忽略）、在執行期資料目錄、路徑含快取目錄；與 RUNTIME_DATA_NO_OVERVIEW 同一個判式（runtime_data_verdict）。
    拿不到根、不在根底下、沒有部位表又不是執行期資料 → 不排除（照算）。不看副檔名。"""
    full, base = canon_path(path), (canon_path(root) if root else "")
    if not base or not full.startswith(base + "/"):
        return False
    return kind == "knowledge" or not runtime_data_verdict(path, root, gitignored).owed


def _base_name(p: Any) -> str:
    return os.path.basename(str(p).replace("\\", "/"))


def moved_copy_candidates(name: str, last_sha: Optional[str],
                          new_code: Dict[str, Optional[str]]) -> Tuple[List[str], List[str]]:
    """MOVED_NEW_CODE_SEEN 的副本判定：new_code＝同根新出現的程式檔 → 現在內容的雜湊（讀不到＝None）；last_sha＝已不存在的
    name 最後一次寫入時的內容雜湊（None＝沒有紀錄）。檔名相同（不分大小寫）、內容相同、或判不出的算可能是它搬過去的副本；
    檔名與內容都不同的是別的檔。回 (副本, 別的檔)，各照 new_code 的順序。"""
    if last_sha is None:
        return list(new_code), []
    seen: List[str] = []
    other: List[str] = []
    for path, sha in new_code.items():
        same = sha is None or sha == last_sha or _base_name(path).lower() == name.lower()
        (seen if same else other).append(path)
    return seen, other


def gone_verdict(name: str, vcs_kind: Optional[str], new_code: Iterable[str] = (), git_failed: str = "",
                 unrelated: Iterable[str] = ()) -> Verdict:
    """已不存在的改過程式檔欠不欠補案例（GONE_* ／ MOVED_NEW_CODE_SEEN）。
    vcs_kind＝它（或最近還在的上層目錄）所在的版控根種類 git／svn，None＝不在任何版控根內；
    new_code＝同根 status 新出現、本 session 提交新加進來的程式檔裡可能是它副本的（moved_copy_candidates）；
    unrelated＝新出現但檔名與內容都和它不同的（證據用）；git_failed＝查 git 失敗的原因（空＝查到了）。"""
    if vcs_kind is None:
        return Verdict("GONE_OUTSIDE_VCS", False, f"{name} 已不存在、也不在任何版控根內")
    if vcs_kind != "git":
        return Verdict("GONE_UNVERIFIABLE", True, f"{name} 已不存在、在 {vcs_kind} 工作副本裡查不了搬去哪")
    if git_failed:
        return Verdict("GONE_UNVERIFIABLE", True, f"{name} 已不存在、{git_failed}")
    seen = [_base_name(n) for n in new_code or []]
    if seen:
        return Verdict("MOVED_NEW_CODE_SEEN", True, f"{name} 已不存在、同根出現可能是它的副本（{'、'.join(seen[:3])}），可能是搬過去了")
    other = [_base_name(n) for n in unrelated or []]
    if other:
        return Verdict("GONE_IN_GIT_NOTHING_NEW", False,
                       f"{name} 已不存在、同根新出現的程式檔（{'、'.join(other[:3])}）檔名與內容都和它不同，不是搬過去的")
    return Verdict("GONE_IN_GIT_NOTHING_NEW", False, f"{name} 已不存在、同根 status 與本 session 提交都沒有新的程式檔")


def gate_self_error_verdict(gate: str, stage: str, error: str, blocked_this_turn: bool = False) -> Verdict:
    """GATE_SELF_ERROR：gate＝閘名；stage＝"stop"（收尾閘，有擋次預算）或 "tool"（工具前閘）；error＝錯誤種類與訊息；
    blocked_this_turn＝收尾閘這個使用者回合已因自己出錯擋過一次。owed＝這次要擋。記 stderr 與 guard log 由呼叫端做。"""
    if stage == "stop" and not blocked_this_turn:
        return Verdict("GATE_SELF_ERROR", True, f"{gate} 判定出錯，這個使用者回合擋一次", (error[:200],))
    why = "工具前閘出錯直接放行" if stage == "tool" else "這個使用者回合已因判定出錯擋過一次，放行"
    return Verdict("GATE_SELF_ERROR", False, f"{gate}：{why}", (error[:200],))


def case_cover_verdict(name: str, covering: Sequence[str], cases: Sequence[str]) -> Verdict:
    """CASE_COVERS_CHANGE：name＝改過的程式檔；covering＝覆蓋它的案例檔名；cases＝本 session 改過、仍存在、同根的案例檔名。"""
    if covering:
        return Verdict("CASE_COVERS_CHANGE", False, f"{name} 有本 session 改過的案例覆蓋：{'、'.join(covering[:3])}")
    if cases:
        return Verdict("CASE_COVERS_CHANGE", True,
                       f"本 session 改過的案例（{'、'.join(cases[:4])}）都沒提到 {name}，宣告裡也沒有 case_for 列它")
    return Verdict("CASE_COVERS_CHANGE", True, f"本 session 沒有改過仍存在、同根的案例檔，{name} 改過")


# ─── 擋訊息格式（契約） ───────────────────────────────────────────────────────
HIT_PREFIX = "✗ "
_HIT_RE = lazy_re(r"^\s*✗ \(([^)]+)\) ([A-Z][A-Z0-9_]*)：")


def format_hit(letter: str, v: Verdict) -> str:
    """`✗ (<字母>) <規則名>：<一句現象>｜證據：<一行一證據>`。沒有證據就印 why 當唯一一行證據。"""
    ev = list(v.evidence) or [v.why]
    return f"{HIT_PREFIX}({letter}) {v.rule}：{v.why}｜證據：" + "；".join(ev)


DENY_EVIDENCE_CAP = 160      # DENY_TEXT_SLIM：每項證據最多幾個字，超過截短


def deny_slim_enabled(config: Any) -> bool:
    """guard.deny_text_slim（預設開，規則 DENY_TEXT_SLIM）；寫 false 時採用的閘退回自己原本的長文字（原處不動）。"""
    return (((config or {}).get("guard") or {}).get("deny_text_slim", True)) is not False


def slim_deny(tag: str, fix: str, hits: Sequence[Tuple[str, Verdict]], cap: int = DENY_EVIDENCE_CAP) -> str:
    """DENY_TEXT_SLIM 的擋訊息：第一行 `[<閘>] 修法：<一句>`，下面每條命中一行 format_hit（parse_hits 照認，
    每項證據超過 cap 字截短）。判準卡名由接卡處（wg_entrypoint.entry_note）接在後面。"""
    rows = [format_hit(letter, v._replace(evidence=tuple(e if len(e) <= cap else e[:cap] + "…" for e in v.evidence)))
            for letter, v in hits]
    return "\n".join([f"[{tag}] 修法：{fix}", *rows])


def split_blocking(hits: List[str], block_letters: Any) -> Tuple[List[str], List[str]]:
    """規則 RECONCILE_BLOCK_LETTERS：format_hit 條目分成（會擋, 只提示）。block_letters 不是清單＝全擋。"""
    if not isinstance(block_letters, list):
        return list(hits), []
    keep = {str(x) for x in block_letters}
    block = [h for h in hits if (parse_hits(h) or [""])[0] in keep]
    return block, [h for h in hits if h not in block]


def parse_hits(text: str) -> List[str]:
    """擋訊息裡每一條 `✗ (<字母>) <規則名>：` 的字母（保序、去重）。預算與擋滿訊息用它知道這次擋了哪幾條。"""
    out: List[str] = []
    for ln in str(text or "").splitlines():
        m = _HIT_RE.match(ln)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def parse_hit_rules(text: str) -> List[Tuple[str, str]]:
    """擋訊息裡 (字母, 規則名) 清單（擋滿訊息列全部條目用）。"""
    out: List[Tuple[str, str]] = []
    for ln in str(text or "").splitlines():
        m = _HIT_RE.match(ln)
        if m and (m.group(1), m.group(2)) not in out:
            out.append((m.group(1), m.group(2)))
    return out


# ─── BLOCK_BUDGET_SHARED ────────────────────────────────────────────────────

def budget_counts(rec: Any, uturn: int) -> Dict[str, int]:
    """state reconcile_gate_turn[sid] 的紀錄 → 本使用者回合每條規則擋過幾次。換了回合 → 全部從 0 起。
    升級前的舊格式（只有整場一個 count）保守承接成每條規則都已擋 count 次（鍵 "*"），不因升級多放兩次。"""
    if not isinstance(rec, dict) or int(rec.get("turn", -1)) != int(uturn):
        return {}
    counts = rec.get("counts")
    if isinstance(counts, dict):
        return {str(k): int(v) for k, v in counts.items()}
    legacy = int(rec.get("count", 0) or 0)
    return {"*": legacy} if legacy else {}


def _count_of(counts: Dict[str, int], letter: str) -> int:
    return int(counts.get(letter, counts.get("*", 0)))


def budget_exhausted(rec: Any, uturn: int, max_blocks: int, letters: Iterable[str]) -> List[str]:
    """這次命中的字母裡，哪幾條在本回合已經擋滿（count ≥ max）。空清單＝還沒擋滿。"""
    counts = budget_counts(rec, uturn)
    return [l for l in letters if _count_of(counts, l) >= int(max_blocks)]


def budget_tick(rec: Any, uturn: int, letters: Iterable[str]) -> Dict[str, Any]:
    """擋了一次：命中的每條規則各 +1，回新紀錄 {"turn", "counts", "count"}；count 欄＝最大值（舊讀取端相容）。"""
    counts = budget_counts(rec, uturn)
    for l in letters:
        counts[l] = _count_of(counts, l) + 1
    real = [v for k, v in counts.items() if k != "*"] or list(counts.values())
    return {"turn": int(uturn), "counts": counts, "count": max(real) if real else 0}


def exhausted_summary(code_text: str) -> str:
    """擋滿訊息的摘要：列出全部命中條目「✗ (a) RULE；✗ (d) RULE」，不只第一行。"""
    pairs = parse_hit_rules(code_text)
    if pairs:
        return "；".join(f"{HIT_PREFIX}({l}) {r}" for l, r in pairs)
    lines = [ln.strip() for ln in str(code_text or "").splitlines() if ln.strip()]
    return lines[1] if len(lines) > 1 else (lines[0] if lines else "")


# ─── CASE_COVERS_CHANGE：案例內容提到程式檔 ────────────────────────────────────

def case_covers_code(case_path: str, case_text: str, path: str) -> bool:
    """CASE_COVERS_CHANGE 的「碰過它的案例」：案例檔名是 test_<模組名>／verify_<模組名>／<模組名>_test（不分大小寫），
    或案例內容提到它（case_names_code）。"""
    stem = os.path.basename(str(path).replace("\\", "/")).lower().rsplit(".", 1)[0]
    case_stem = os.path.basename(str(case_path).replace("\\", "/")).lower().rsplit(".", 1)[0]
    return bool(stem) and case_stem in (f"test_{stem}", f"verify_{stem}", f"{stem}_test") or case_names_code(case_text, path)


def case_names_code(text: str, path: str) -> bool:
    """CASE_COVERS_CHANGE 的「內容提到」：text 裡有這個程式檔的檔名，或至少 3 字的模組名（去副檔名），前後不接英數字或底線、
    不分大小寫（`import wg_x`、`"hooks/wg_x.py"`、`tools/foo-bar.py` 都算；`wg_xy` 不算 `wg_x`）。"""
    name = os.path.basename(str(path).replace("\\", "/")).lower()
    if not name:
        return False
    stem = name.rsplit(".", 1)[0] if "." in name else name
    low = str(text or "").lower()
    words = [name] + ([stem] if len(stem) >= 3 and stem != name else [])
    return any(re.search(r"(?<![a-z0-9_])" + re.escape(w) + r"(?![a-z0-9_])", low) for w in words)


# ─── COMMENT_ONLY_CHANGE ────────────────────────────────────────────────────

def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return tree


def code_shape(src: str) -> Optional[str]:
    """Python 原始碼去掉註解、docstring、空白、行號後的形狀（ast.dump）；解析不了回 None。"""
    try:
        tree = ast.parse(str(src))
    except (SyntaxError, ValueError, RecursionError):
        return None
    return ast.dump(_strip_docstrings(tree), annotate_fields=True, include_attributes=False)


def comment_only_change(old_src: Optional[str], new_src: Optional[str], path: str = "x.py") -> Optional[bool]:
    """COMMENT_ONLY_CHANGE：True＝只改了註解／docstring／空白；False＝改到程式；None＝判不了（非 .py、任一邊解析不了、基準缺）。"""
    if old_src is None or new_src is None or not str(path).lower().endswith((".py", ".pyw")):
        return None
    a, b = code_shape(old_src), code_shape(new_src)
    if a is None or b is None:
        return None
    return a == b


def comment_only_verdict(name: str, baseline: str) -> Verdict:
    return Verdict("COMMENT_ONLY_CHANGE", False, f"{name} 與 {baseline} 只差註解／docstring／空白",
                   (f"ast 去註解與 docstring 後與 {baseline} 相同",))


# ─── CONTENT_EQUALS_COMMITTED ──────────────────────────────────────────────

def blob_sha(data: bytes) -> str:
    """git blob 的 sha1（`blob <len>\\0<內容>`），不開 git 子行程就能和 ls-tree 的結果比。"""
    data = bytes(data)
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def committed_refs(own_commit_shas: Iterable[str], ref_commits: Dict[str, str], committed_since_edit: bool = True,
                   head_after_own: bool = False) -> List[str]:
    """哪些 ref 可以當「已提交版本」：MERGE_HEAD／main／master（指到本 session 自己提交的 commit 除外）。
    HEAD 平常不算：「等於 HEAD」走 NET_UNCHANGED／SNAPSHOT_SETTLED（它們還會查同根案例檔乾不乾淨，程式與案例一起退回舊版、
    只還原程式時案例還是舊的，照欠；verify_stop_reconcile 035 ⑤）。例外 head_after_own：HEAD 是別人接在本 session 最後一次提交
    之上做的提交（另一個 session 或人把 main 合進這個分支）→ 本 session 的 commit 快照拍在那之前、對不上，HEAD 才是已提交版本，算；
    呼叫端要另外確認同根本 session 改過的檔全等於 HEAD（擋同一個反例）。ref_commits＝ref → 它指到的 commit sha。"""
    own = {str(s) for s in own_commit_shas or ()}
    head = str((ref_commits or {}).get("HEAD") or "")
    out: List[str] = []
    for ref, sha in (ref_commits or {}).items():
        if not sha or str(sha) in own:
            continue
        if ref == "HEAD" or str(sha) == head:
            if head_after_own and ref == "HEAD":
                out.append(ref)
            continue
        out.append(ref)
    return out


def content_equals_committed(name: str, current_blob: Optional[str], ref_blobs: Dict[str, Optional[str]],
                             usable_refs: Iterable[str]) -> Optional[Verdict]:
    """CONTENT_EQUALS_COMMITTED：現在的 blob 等於任一可用 ref 裡該檔的 blob → Verdict(owed=False)；都不等、或拿不到 → None（照算）。"""
    if not current_blob:
        return None
    for ref in usable_refs:
        sha = (ref_blobs or {}).get(ref)
        if sha and str(sha) == str(current_blob):
            return Verdict("CONTENT_EQUALS_COMMITTED", False, f"{name} 內容等於 {ref} 已提交的版本",
                           (f"blob {str(current_blob)[:12]} == {ref}:{name} 的 blob",))
    return None


# ─── INLINE_PY_READONLY ─────────────────────────────────────────────────────
_WRITE_MODE_RE = lazy_re(r"[wax+]")
_DENY_MODULES = frozenset({"subprocess", "shutil", "tempfile", "sqlite3", "shelve", "dbm", "zipfile", "tarfile", "ctypes",
                           "importlib", "runpy", "code", "socket", "multiprocessing", "threading", "pty", "signal"})
_DENY_ATTRS = frozenset({"remove", "unlink", "rename", "renames", "replace", "rmdir", "removedirs", "makedirs", "mkdir",
                         "write", "write_text", "write_bytes", "writelines", "touch", "copy", "copy2", "copyfile", "copytree",
                         "copymode", "copystat", "move", "rmtree", "system", "popen", "run", "call", "check_call",
                         "check_output", "Popen", "chmod", "chown", "truncate", "symlink", "link", "fdopen", "startfile",
                         "execv", "execl", "execvp", "execve", "spawnl", "spawnv", "kill", "putenv", "unsetenv",
                         "setattr", "delattr", "dump", "save", "to_csv", "to_json", "to_excel", "to_pickle", "mknod"})
_DENY_NAMES = frozenset({"exec", "eval", "compile", "__import__", "globals", "locals", "vars", "getattr", "setattr", "delattr",
                         "breakpoint", "input", "open", "__builtins__", "memoryview"})
_ALLOW_WRITE_CHAINS = frozenset({"sys.stdout.write", "sys.stderr.write", "sys.stdout.writelines", "sys.stderr.writelines",
                                 "sys.stdout.flush", "sys.stderr.flush"})
# 這些名字只准當「呼叫的那個函式」直接出現：拿去指派、當參數、放進容器（f = open；[open][0]('x','w')）都是別名，判不了 → 擋
_ALIAS_SENSITIVE = _DENY_NAMES | {"open"}


def _attr_chain(node: ast.AST) -> str:
    parts: List[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif isinstance(node, ast.Call):
        parts.append("(call)")
    return ".".join(reversed(parts))


def _open_mode(call: ast.Call) -> Optional[str]:
    """open(...) 的 mode：位置第 2 參或 mode= 關鍵字；是字串常數回字串；沒給回 "r"；不是常數回 None（判不了）。"""
    mode_node = call.args[1] if len(call.args) >= 2 else None
    for kw in call.keywords:
        if kw.arg == "mode":
            mode_node = kw.value
        elif kw.arg is None:
            return None            # **kwargs 展開：判不了
    if mode_node is None:
        return "r"
    if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
        return mode_node.value
    return None


def inline_python_verdict(code: str) -> Verdict:
    """INLINE_PY_READONLY：owed=False＝只讀、放行；owed=True＝有寫入可能或判不了、照擋。why 說第一個被擋的原因。"""
    try:
        tree = ast.parse(str(code or ""))
    except (SyntaxError, ValueError, RecursionError) as e:
        return Verdict("INLINE_PY_READONLY", True, f"內嵌碼解析不了（{type(e).__name__}）", (str(code)[:60],))
    call_funcs = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    # import … as 取別名照判：寫入靠呼叫鏈尾的名字判（o.remove 一樣抓得到），別名只拿來認出 builtins 的動態執行
    aliases = {a.asname: a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names if a.asname}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else [str(node.module or "").split(".")[0]]
            bad = [n for n in names if n in _DENY_MODULES]
            if bad:
                return Verdict("INLINE_PY_READONLY", True, f"內嵌碼匯入 {bad[0]}（可能寫檔或跑子行程）", (f"import {bad[0]}",))
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                return Verdict("INLINE_PY_READONLY", True, "內嵌碼 from … import *，判不了呼叫的是誰", (ast.dump(node)[:60],))
            if isinstance(node, ast.ImportFrom) and any(a.name in _DENY_ATTRS or a.name in _DENY_NAMES for a in node.names):
                bad = next(a.name for a in node.names if a.name in _DENY_ATTRS or a.name in _DENY_NAMES)
                return Verdict("INLINE_PY_READONLY", True, f"內嵌碼 from … import {bad}（刪搬寫或動態執行）", (bad,))
        elif isinstance(node, ast.Name) and id(node) not in call_funcs and node.id in _ALIAS_SENSITIVE:
            return Verdict("INLINE_PY_READONLY", True, f"內嵌碼把 {node.id} 當值使用（別名、傳參、放進容器），判不了", (node.id,))
        elif isinstance(node, ast.Attribute) and id(node) not in call_funcs and node.attr in _DENY_ATTRS:
            return Verdict("INLINE_PY_READONLY", True, f"內嵌碼把 {_attr_chain(node)} 當值使用（別名），判不了", (_attr_chain(node),))
        elif isinstance(node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return Verdict("INLINE_PY_READONLY", True, "內嵌碼定義函式／類別，呼叫路徑判不了", (type(node).__name__,))
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, (ast.Name, ast.Attribute)):
                return Verdict("INLINE_PY_READONLY", True, "內嵌碼呼叫的不是具名函式（呼叫結果再呼叫、下標、lambda），判不了", (ast.dump(node.func)[:60],))
            chain = _attr_chain(node.func)              # `Path('a').read_text()`、`open('a').read()` 這類在呼叫結果上取屬性：看葉子名
            leaf = chain.rsplit(".", 1)[-1]
            if leaf == "open":
                mode = _open_mode(node)
                if mode is None:
                    return Verdict("INLINE_PY_READONLY", True, "open() 的 mode 不是字面常數，判不了", (chain,))
                if _WRITE_MODE_RE.search(mode):
                    return Verdict("INLINE_PY_READONLY", True, f"open(…, '{mode}') 會寫檔", (chain,))
                if chain in ("os.open",):
                    return Verdict("INLINE_PY_READONLY", True, "os.open 的旗標可能含寫入", (chain,))
                continue
            if chain in _ALLOW_WRITE_CHAINS:
                continue
            root = chain.split(".", 1)[0]
            if "." in chain and aliases.get(root, root) in ("builtins", "__builtins__") and leaf in _DENY_NAMES:
                return Verdict("INLINE_PY_READONLY", True, f"內嵌碼呼叫 {chain}（動態執行或互動）", (chain,))
            if leaf in _DENY_ATTRS and "." in chain:
                return Verdict("INLINE_PY_READONLY", True, f"內嵌碼呼叫 {chain}（刪搬寫或子行程）", (chain,))
            if isinstance(node.func, ast.Name) and node.func.id in _DENY_NAMES:
                return Verdict("INLINE_PY_READONLY", True, f"內嵌碼呼叫 {node.func.id}（動態執行或互動）", (node.func.id,))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                chain = _attr_chain(t)
                if chain in ("sys.stdout", "sys.stderr") or chain.startswith("os.environ"):
                    continue
                if isinstance(t, ast.Subscript) and _attr_chain(t.value).startswith("os.environ"):
                    continue
                if chain.startswith("sys.") or chain.startswith("os."):
                    return Verdict("INLINE_PY_READONLY", True, f"內嵌碼改了 {chain}", (chain,))
    return Verdict("INLINE_PY_READONLY", False, "內嵌碼只讀（ast 無寫檔、刪搬、子行程、動態執行）", (str(code)[:60],))


# ─── GIT_READONLY_SUBCMD ────────────────────────────────────────────────────
_GIT_READONLY_SUBS = frozenset({"show", "hash-object", "rev-parse", "diff", "log", "status", "ls-files", "cat-file",
                                "ls-tree", "rev-list", "blame", "describe", "branch", "remote", "worktree", "config",
                                "for-each-ref", "name-rev", "merge-base", "shortlog", "grep", "check-ignore", "var", "tag"})
_GIT_WRITE_FLAGS = {"hash-object": ("-w",),
                    "branch": ("-m", "-M", "-d", "-D", "-c", "-C", "--move", "--delete", "--copy", "-f", "--force", "-u", "--set-upstream-to",
                               "--unset-upstream", "--edit-description"),
                    "remote": ("add", "remove", "rm", "rename", "set-url", "set-head", "set-branches", "prune", "update"),
                    "worktree": ("add", "remove", "move", "prune", "lock", "unlock", "repair"),
                    "config": ("--unset", "--add", "--replace-all", "--edit", "-e", "--unset-all", "--remove-section", "--rename-section"),
                    "tag": ("-a", "-d", "-f", "-m", "-s", "-u", "--delete", "--force"),
                    # 唯讀子命令也有會寫檔的選項
                    "diff": ("--output", "-o"), "log": ("--output", "-o"), "show": ("--output", "-o"), "shortlog": ("--output", "-o"),
                    "grep": ("--output", "-O", "--open-files-in-pager")}
_GIT_OUTPUT_OPT = "--output"       # 每個唯讀子命令都認得的寫檔選項
# 規則 SHELL_KEYWORD_PREFIX_STRIPPED：段首這些字是 shell 語法，後面才是命令（for／while 迴圈本體、if 分支、{ } 群組）
SHELL_PREFIX_KEYWORDS = frozenset({"do", "then", "else", "elif", "if", "while", "until", "!", "{"})
_GIT_GLOBAL_VALUE_OPTS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix", "--config-env"})


_SEG_BREAKS = frozenset(";&|\n")


def _unquoted_pieces(raw: str) -> Optional[List[str]]:
    """引號外的 ; & | 換行切開（單引號裡什麼都照字面；雙引號裡與引號外 \\ 跳脫下一個字）；引號到最後沒收回 None。"""
    pieces: List[str] = []
    buf: List[str] = []
    quote = ""
    i = 0
    while i < len(raw):
        c = raw[i]
        i += 1
        if c == "\\" and quote != "'" and i < len(raw):
            buf += [c, raw[i]]
            i += 1
            continue
        if quote:
            quote = "" if c == quote else quote
        elif c in "'\"":
            quote = c
        elif c in _SEG_BREAKS:
            pieces.append("".join(buf))
            buf = []
            continue
        buf.append(c)
    return None if quote else pieces + ["".join(buf)]


def _shlex_segments(raw: str) -> Optional[List[List[str]]]:
    """指令切段：按引號外的換行與 && || ; | & 切（shlex 會把換行當空白吞掉，第二行的 reset 會被當成第一行 status 的參數），
    每段再用 shlex 斷字。規則 SEGMENTS_SPLIT_LIKE_SHELL：引號裡的換行與 ; & | 都不是段界（`python -c "…多行…"`、
    `echo ";&" git reset` 整段是 echo 的參數），引號到最後沒收才回 None；分隔符黏在字上（`a; do`、`x&&git`）也切。
    段首的 shell 保留字（do、then、{…）剝掉（SHELL_KEYWORD_PREFIX_STRIPPED）。"""
    pieces = _unquoted_pieces(raw)
    if pieces is None:
        return None
    segs: List[List[str]] = []
    for piece in pieces:
        try:
            tokens = shlex.split(piece, posix=True)
        except ValueError:
            return None
        while tokens and tokens[0] in SHELL_PREFIX_KEYWORDS:
            tokens.pop(0)
        if tokens:                       # && 與 || 之間、只有保留字的段是空的
            segs.append(tokens)
    return segs


def _git_segments_readonly(command: str, segments: Optional[Sequence[Sequence[str]]] = None) -> Tuple[bool, List[str]]:
    """每個以 git 開頭的指令段是不是唯讀子命令。回 (全唯讀, 證據)。segments 沒給：整條指令自己切段（_shlex_segments），
    每段 git 都判；給了（跨層閘從掃描器挑出 repo 在根層的 git 段，每段是 git 後面的參數）只判那幾段。
    引號不完整、含命令替換（$( 或反引號）→ 判不了，當不唯讀。"""
    raw = str(command or "").replace("\r\n", "\n").replace("\r", "\n")
    if re.search(r"\$\(|`", raw):
        return False, ["指令含命令替換（$( 或反引號），判不了"]
    segs = [["git", *s] for s in segments] if segments is not None else _shlex_segments(raw)
    if segs is None:
        return False, ["指令引號不完整，解析不了"]
    evidence: List[str] = []
    seen_git = False
    for seg in segs:
        if not seg:
            continue
        name = seg[0].rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
        if name.endswith(".exe"):
            name = name[:-4]
        if name != "git":
            continue
        seen_git = True
        i = 1
        while i < len(seg) and seg[i].startswith("-"):
            if seg[i] in _GIT_GLOBAL_VALUE_OPTS:
                i += 2
            else:
                i += 1
        if i >= len(seg):
            return False, evidence + ["git 沒有子命令"]
        sub = seg[i].lower()
        rest = seg[i + 1:]
        if sub not in _GIT_READONLY_SUBS:
            return False, evidence + [f"git {sub} 不是唯讀子命令"]
        for flag in (*_GIT_WRITE_FLAGS.get(sub, ()), _GIT_OUTPUT_OPT):
            if flag in rest or any(r.startswith(flag + "=") for r in rest if flag.startswith("--")) \
                    or (not flag.startswith("--") and len(flag) == 2 and any(r.startswith(flag) and len(r) > 2 and not r.startswith("--") for r in rest)):
                return False, evidence + [f"git {sub} {flag} 會寫"]
        if sub == "config" and not any(r in ("--get", "--get-all", "--list", "-l", "--get-regexp") for r in rest):
            return False, evidence + ["git config 沒帶 --get／--list，可能在設定"]
        evidence.append(f"git {sub} 唯讀")
    return seen_git, evidence


def git_readonly_verdict(command: str, root_write_targets: Sequence[str],
                         git_segments: Optional[Sequence[Sequence[str]]] = None) -> Verdict:
    """GIT_READONLY_SUBCMD：owed=False＝放行（每段 git 都唯讀、且寫入目標沒有落在根層）；owed=True＝照擋。
    root_write_targets 裡 UNKNOWN 開頭的是算不出的目標（擋訊息照實說算不出，不說落在根層）。
    git_segments：要判的 git 段（git 後的參數）；None＝整條指令每段 git 都判；[]＝git 都在別的 repo 跑，不用判。"""
    if root_write_targets:
        known = [t for t in root_write_targets if not str(t).startswith("UNKNOWN")]
        why = "指令有寫入目標落在根層" if known else "寫入目標算不出（變數展不開、cd 去向不明或內嵌碼判不了），寧可多擋"
        return Verdict("GIT_READONLY_SUBCMD", True, why, tuple(str(t)[:80] for t in root_write_targets[:3]))
    if git_segments is not None and not git_segments:
        return Verdict("GIT_READONLY_SUBCMD", False, "git 都在根層以外的 repo 跑（cd／-C 推得出 repo）、寫入目標也不在根層",
                       ("沒有在根層 repo 跑的 git",))
    ok, ev = _git_segments_readonly(command, git_segments)
    if not ok:
        return Verdict("GIT_READONLY_SUBCMD", True, "不是全唯讀的 git 指令", tuple(ev[-2:]) or (str(command)[:60],))
    return Verdict("GIT_READONLY_SUBCMD", False, "每段 git 都是唯讀子命令且沒寫到根層", tuple(ev[:4]))


# ─── GREP_CONTENT_IS_READ ／ BASH_COMMENT_LINES_STRIPPED ────────────────────

def grep_read_paths(tool_input: Dict[str, Any], is_file: Any = os.path.isfile) -> List[str]:
    """GREP_CONTENT_IS_READ：Grep 工具 output_mode=content 且 path 指到一個檔 → [path]；其他（目錄、files_with_matches、count）→ []。
    is_file 可注入（案例用）。"""
    if str((tool_input or {}).get("output_mode") or "") != "content":
        return []
    p = str((tool_input or {}).get("path") or "")
    return [p] if p and is_file(p) else []


def strip_comment_lines(command: str) -> str:
    """BASH_COMMENT_LINES_STRIPPED：去掉行首（可有空白）以 # 開頭的整行，其餘原樣；接續行（上一行以 \\ 結尾）不算註解。"""
    out: List[str] = []
    cont = False
    for ln in str(command or "").splitlines():
        if not cont and ln.lstrip().startswith("#"):
            continue
        out.append(ln)
        cont = ln.rstrip().endswith("\\")
    return "\n".join(out)


# ─── ⑧ VCS_ROOT_UNREADABLE ──────────────────────────────────────────────────────

def vcs_unreadable_verdict(name: str, error: str) -> Verdict:
    """VCS_ROOT_UNREADABLE：找版控根時 OSError → 照欠。"""
    return Verdict("VCS_ROOT_UNREADABLE", True, f"{name} 所在的版控根讀不到，判不出去向", (str(error)[:120],))


# ─── WORKTREE_NO_PUSH ───────────────────────────────────────────────────────

def is_worktree_checkout(git_dir: Optional[str], common_dir: Optional[str]) -> bool:
    """`git rev-parse --git-dir` 與 `--git-common-dir` 不同＝這個 checkout 是 worktree。任一拿不到 → False（判不了當主工作樹）。"""
    if not git_dir or not common_dir:
        return False
    return canon_path(git_dir) != canon_path(common_dir)


def push_required_verdict(root: str, is_worktree: bool, has_upstream: bool) -> Verdict:
    """WORKTREE_NO_PUSH：owed=True＝要求 push；worktree 或沒 upstream → False。"""
    if is_worktree:
        return Verdict("WORKTREE_NO_PUSH", False, f"{root} 是 git worktree，分支之後由人合併，不要求 push",
                       ("git-dir ≠ git-common-dir",))
    if not has_upstream:
        return Verdict("WORKTREE_NO_PUSH", False, f"{root} 的分支沒有 upstream，無從 push", ("@{u} 解析不到",))
    return Verdict("WORKTREE_NO_PUSH", True, f"{root} 是主工作樹且有 upstream", ("git-dir == git-common-dir", "@{u} 存在"))


# ─── RUNTIME_DATA_NO_OVERVIEW ───────────────────────────────────────────────
RUNTIME_DATA_DIRS: Tuple[str, ...] = ("workflow/state", "workflow/need-goal", "workflow/verify-ledger", "workflow/dpm-done",
                                      "workflow/acceptance-spec", "workflow/aec-report", "Logs")
# 工具自己生的快取目錄名：路徑任一段是它就算執行期資料（專案沒寫 .gitignore 時 check-ignore 不會命中）
RUNTIME_CACHE_DIR_NAMES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})


def runtime_data_verdict(path: str, root: Optional[str], gitignored: Optional[bool],
                         runtime_dirs: Iterable[str] = RUNTIME_DATA_DIRS) -> Verdict:
    """RUNTIME_DATA_NO_OVERVIEW：owed=False＝免綜觀（gitignored、在執行期資料目錄、或路徑含快取目錄）；owed=True＝照要求。
    gitignored=None＝查不到（當不忽略）。目錄比對：相對根的路徑以 runtime_dirs 之一開頭（`workflow/state` 也含 `workflow/state-xxxx.json`）；
    快取目錄只比相對根的各段（根以外的上層目錄名不算），沒給根就比整條路徑。"""
    if gitignored:
        base_name = os.path.basename(str(path).replace("\\", "/").rstrip("/"))
        return Verdict("RUNTIME_DATA_NO_OVERVIEW", False, f"{base_name} 被 .gitignore 忽略，是執行期資料", ("git check-ignore 命中",))
    rel = None
    if root:
        full, base = canon_path(path), canon_path(root)
        if full.startswith(base + "/"):
            rel = full[len(base) + 1:]
    cache = next((s for s in (rel if rel is not None else canon_path(path)).split("/") if s in RUNTIME_CACHE_DIR_NAMES), None)
    if cache:
        return Verdict("RUNTIME_DATA_NO_OVERVIEW", False, f"路徑含快取目錄 {cache}，是執行期資料", (f"路徑 {str(path)[:80]}",))
    if rel is not None:
        for d in runtime_dirs:
            d = str(d).replace("\\", "/").strip("/").lower()
            if rel == d or rel.startswith(d + "/") or rel.startswith(d + "-") or rel.startswith(d + "."):
                return Verdict("RUNTIME_DATA_NO_OVERVIEW", False, f"{rel} 在執行期資料目錄 {d}", (f"相對根路徑 {rel}",))
    return Verdict("RUNTIME_DATA_NO_OVERVIEW", True, "不是執行期資料，照要求先讀同目錄的檔", (str(path)[:80],))


_GLOB_CHARS = frozenset("*?[")


def bash_read_counts(paths: Iterable[str], exit_code: Optional[int], is_file: Any = os.path.isfile) -> List[str]:
    """BASH_READONLY_COUNTS_AS_READ：Bash／PowerShell 讀檔指令解析出的路徑（lib/overview_hub.read_paths_from_tool）裡，
    算讀過的那些：exit 0 或未知才算；含 $、未展開 glob、不是實檔的不算。"""
    if exit_code not in (None, 0):
        return []
    return [p for p in paths if "$" not in p and not (_GLOB_CHARS & set(p)) and is_file(p)]


def unmapped_edit_verdict(need: int, readable: int, have: int) -> Verdict:
    """UNMAPPED_EDIT_NEEDS_READABLE_FILES：要讀數＝min(need, readable)；have（本 session 讀過同頂層目錄的檔數）不到就欠。
    readable＝呼叫端數到的非執行期資料既有檔數（數到 need 就可停，所以 readable ≥ need 只代表「至少這麼多」）。"""
    want = max(0, min(need, readable))
    pool = f"至少 {readable} 個" if readable >= need else f"只有 {readable} 個"
    ev = (f"設定要讀 {need} 個", f"該目錄既有可讀檔 {pool}", f"本 session 讀過 {have} 個")
    if have >= want:
        why = "該目錄沒有可讀的既有檔，不要求先讀" if want == 0 else f"已讀 {have} 個，夠 {want} 個"
        return Verdict("UNMAPPED_EDIT_NEEDS_READABLE_FILES", False, why, ev)
    return Verdict("UNMAPPED_EDIT_NEEDS_READABLE_FILES", True, f"至少 {want} 個檔（目前 {have} 個）", ev)


# ─── B9／B14 暫存目錄 ─────────────────────────────────────────────────────────
# 暫存目錄特徵片段：只認系統暫存下才會出現的形狀（pytest 的 tmp 根、CC 的 Temp/claude/…/scratchpad）；
# 專案裡一個普通目錄取名 scratchpad 不算（正式 repo 的子目錄不能靠名字拿暫存豁免）
_TEMP_TOKENS: Tuple[str, ...] = ("/pytest-of-", "/temp/claude/", "/.pytest_cache/")


def norm_temp_path(path: str) -> str:
    """暫存判斷用的表示：去 `\\\\?\\` 前綴（UNC 寫法還原成 `\\\\server`）、normpath、斜線統一、小寫。8.3 短路徑的展開由呼叫端
    （handlers/_shared._comparable）做完再傳進來；這裡不碰檔案系統。"""
    p = str(path or "")
    if p[:8].upper() == "\\\\?\\UNC\\":
        p = "\\\\" + p[8:]
    elif p.startswith("\\\\?\\"):
        p = p[4:]
    return os.path.normpath(p).replace("\\", "/").rstrip("/").lower() if p else ""


TEMP_DISABLED: Tuple[str, ...] = ("<temp-rules-off>",)     # 案例與探針把專案建在 tmp 時關掉暫存規則（WG_TEMP_RULES=off）


def temp_roots(environ: Optional[Dict[str, str]] = None, tempdir: Optional[str] = None) -> List[str]:
    """暫存根清單：tempfile.gettempdir()（呼叫端傳）、環境 TEMP／TMP／TMPDIR、/tmp、/var/tmp。正規化、去重。
    環境 WG_TEMP_RULES=off → 回 TEMP_DISABLED（is_temp_path 一律 False）：pytest 把假專案建在 tmp 下時用。"""
    env = environ if environ is not None else os.environ
    if str(env.get("WG_TEMP_RULES", "")).lower() == "off":
        return list(TEMP_DISABLED)
    cands = [tempdir or "", env.get("TEMP", ""), env.get("TMP", ""), env.get("TMPDIR", ""), "/tmp", "/var/tmp"]
    out: List[str] = []
    for c in cands:
        n = norm_temp_path(c)
        if n and n not in out:
            out.append(n)
    return out


def is_temp_path(path: str, roots: Iterable[str]) -> bool:
    """TEMP_REPO_COMMIT_EXEMPT／TEMP_COPY_NOT_PROJECT 共用：路徑在任一暫存根之下，或含暫存目錄特徵片段（pytest-of-、scratchpad、Temp/claude）。
    `<tmp>/../../專案/x.py` 消掉 .. 之後不在暫存根下，不算。"""
    roots = list(roots or ())
    if roots == list(TEMP_DISABLED):
        return False
    n = norm_temp_path(path)
    if not n:
        return False
    for r in roots:
        r = str(r).rstrip("/")
        if r and (n == r or n.startswith(r + "/")):
            return True
    return any(tok in n + "/" for tok in _TEMP_TOKENS)


def temp_commit_verdict(run_dir: str, roots: Iterable[str]) -> Verdict:
    """TEMP_REPO_COMMIT_EXEMPT：owed=False＝免口令。"""
    if is_temp_path(run_dir, roots):
        return Verdict("TEMP_REPO_COMMIT_EXEMPT", False, f"commit 落在暫存目錄的 repo（{str(run_dir)[:60]}），是拋棄式實驗", ("路徑在暫存根之下",))
    return Verdict("TEMP_REPO_COMMIT_EXEMPT", True, "commit 落在正式 repo，照要口令", (str(run_dir)[:60],))


def temp_copy_verdict(path: str, roots: Iterable[str]) -> Verdict:
    """TEMP_COPY_NOT_PROJECT：owed=False＝不當專案（不找表、不注入、不要求綜觀、不當收據）。"""
    if is_temp_path(path, roots):
        return Verdict("TEMP_COPY_NOT_PROJECT", False, f"{str(path)[:60]} 在暫存目錄下，是副本不是專案", ("路徑在暫存根之下",))
    return Verdict("TEMP_COPY_NOT_PROJECT", True, "不在暫存目錄，照專案規則", (str(path)[:60],))


RULES.update({
    "SESSION_SCRATCH_NOT_CODE": "session 暫存區的檔是一次性腳本，不算本 session 改的程式檔：Claude Code 背景工作的 "
                                "`<CC 設定目錄>/jobs/<id>/tmp/`（設定目錄＝CLAUDE_CONFIG_DIR 與 ~/.claude）與 session scratchpad"
                                "（`<系統暫存根>/claude/…/scratchpad/`）。第二意見門檻（wg_second_opinion.check）、寫碼查核的補案例與驗證範圍"
                                "（wg_verify_ledger.is_excluded）都不數、也不能拿來清帳。只認錨在這兩個根底下的形狀：repo 裡自己取名 "
                                "jobs/<x>/tmp、Temp/claude/…/scratchpad 的目錄照算程式。",
})


RULES.update({
    "LAUNCHER_NOT_CODE": "worktree 根目錄的一次性 git 啟動器不算本 session 改的程式檔：放在版控根、沒進版控、整支只用 subprocess 跑 git"
                         "（第一個參數是 git 開頭的清單字面值，或 for 迴圈走過的這種清單），其他呼叫只准 print、exit、sys.exit、os.chdir，"
                         "import 只准 subprocess／sys／os／pathlib／shlex。建、改、刪都不讓收據作廢、不欠案例、不數進第二意見門檻、"
                         "不蓋到需求目標樹（判定 is_git_launcher_source、事實 wg_verify_ledger.note_git_launcher）；有一處不合就照算程式。"
                         "啟動器跑的 git 改到的檔照 python 啟動器那套快照比對記帳。",
})

_LAUNCHER_IMPORTS = frozenset({"subprocess", "sys", "os", "pathlib", "shlex"})
_LAUNCHER_RUNS = frozenset({"run", "call", "check_call", "check_output", "Popen"})
_LAUNCHER_OTHER_CALLS = frozenset({"print", "exit", "sys.exit", "os.chdir"})
# subprocess 呼叫只准這些關鍵字（不准 shell、executable、env…換掉實際跑的程式）；git 參數不准這些會叫別的程式的寫法
_LAUNCHER_KWARGS = frozenset({"capture_output", "text", "encoding", "errors", "cwd", "check", "timeout", "stdout", "stderr",
                              "input", "universal_newlines"})
_LAUNCHER_GIT_DENY = frozenset({"-c", "--config-env", "--exec-path", "--upload-pack", "--receive-pack", "--exec", "-x",
                                "foreach", "filter-branch", "difftool", "mergetool", "bisect", "--extcmd", "-u"})


def _dotted(node: Any) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr}" if head else ""
    return ""


def _git_argv(node: Any) -> bool:
    """git 開頭、每個參數都是字串字面值、沒有會叫別的程式的寫法（-c alias.x=!…、submodule foreach、rebase --exec…）。"""
    if not (isinstance(node, (ast.List, ast.Tuple)) and node.elts):
        return False
    args = [e.value if isinstance(e, ast.Constant) and isinstance(e.value, str) else None for e in node.elts]
    if None in args or args[0] not in ("git", "git.exe"):
        return False
    return not any(a in _LAUNCHER_GIT_DENY or a.startswith(("--exec=", "--config-env=", "-c=")) for a in args[1:])


def is_git_launcher_source(src: str) -> bool:
    """LAUNCHER_NOT_CODE 的內容判定：src 整支只用 subprocess 跑 git（至少一次），沒有別的呼叫與 import。解析不了 → 不是。"""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return False
    loops = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] not in _LAUNCHER_IMPORTS for a in node.names):
            return False
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] not in _LAUNCHER_IMPORTS:
            return False
        if (isinstance(node, ast.For) and isinstance(node.target, ast.Name) and isinstance(node.iter, (ast.List, ast.Tuple))
                and node.iter.elts and all(_git_argv(e) for e in node.iter.elts)):
            loops.add(node.target.id)
    runs = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func)
        if name.startswith("subprocess.") and name.split(".", 1)[1] in _LAUNCHER_RUNS:
            first = node.args[0] if node.args else None
            if not (_git_argv(first) or (isinstance(first, ast.Name) and first.id in loops)):
                return False
            if len(node.args) > 1 or any(k.arg not in _LAUNCHER_KWARGS for k in node.keywords):
                return False
            runs += 1
        elif name not in _LAUNCHER_OTHER_CALLS:
            return False
    return runs > 0


def cc_config_dirs(environ: Optional[Dict[str, str]] = None, home: Optional[str] = None) -> List[str]:
    """SESSION_SCRATCH_NOT_CODE 的事實：Claude Code 設定目錄（CLAUDE_CONFIG_DIR 有設就加上它，~/.claude 一律算），原樣路徑。"""
    env = environ if environ is not None else os.environ
    dirs = [env.get("CLAUDE_CONFIG_DIR") or "", os.path.join(home or os.path.expanduser("~"), ".claude")]
    return [d for d in dict.fromkeys(dirs) if d]


def is_session_scratch(path: str, config_dirs: Iterable[str], tmp_roots: Iterable[str]) -> bool:
    """SESSION_SCRATCH_NOT_CODE：path 在 `<設定目錄>/jobs/<id>/tmp/` 底下，或在 `<暫存根>/claude/…/scratchpad/` 底下
    （tmp_roots＝temp_roots 的結果；關掉暫存規則時只認 jobs）。兩側都用 norm_temp_path 比、不碰檔案系統（8.3 短路徑由呼叫端先展開）。"""
    n = norm_temp_path(path) + "/"

    def rest(root: str) -> List[str]:
        base = norm_temp_path(root)
        return n[len(base) + 1:].split("/") if base and n.startswith(base + "/") else []
    for d in config_dirs:
        parts = rest(d)
        if len(parts) >= 4 and parts[0] == "jobs" and parts[1] and parts[2] == "tmp":
            return True
    for r in tmp_roots:
        parts = rest(r)
        if len(parts) >= 3 and parts[0] == "claude" and "scratchpad" in parts[1:-1]:
            return True
    return False


# ─── DeepPostMortem 指令 ───────────────────────────────────────────────────
_DPM_BODY = (
    "  - 始末：觸發場景 → 錯誤行為 → 最終正確做法\n"
    "  - 根因：為何會犯（非表面症狀）\n"
    "  - 該區設計原理：出錯那塊程式/機制當初為何這樣設計\n"
    "  - 運作邏輯：它實際怎麼跑、哪個環節斷掉\n"
    "  - 防再犯：下次如何提早攔截\n"
)


def dpm_instruction_text(trigger: str, evidence: str = "") -> str:
    """DeepPostMortem 指令：叫 atom_write 補一條完整 post-mortem（worktree 裡的 session 也一樣，記憶寫到資料根）。
    evidence＝規則證據行（format_hit 格式，例：重試的逐輪證據），放在標頭下一行，parse_hits 讀得到。"""
    head = f"[Guardian:DeepPostMortem] 偵測到高 effort 失敗訊號（{trigger}）。失敗骨架已由 hook 自動落地，但根因與設計脈絡只有你知道。\n"
    if evidence:
        head += evidence.rstrip("\n") + "\n"
    return (head + "結束前請用 atom_write 補一條完整 post-mortem（寫入既有 failure atom，或 realm=local、domain 視主題新建），涵蓋：\n"
            + _DPM_BODY + "寫完即可宣告完成；此為一次性提示，本 session 不再出現。")


# ─── C1 刻意紅／重試／同案例綠清帳 ────────────────────────────────────────────

def deliberate_red_verdict(reverted: Sequence[Tuple[str, str]], pending: Sequence[str] = ()) -> Verdict:
    """RED_WHILE_REVERTED：reverted＝[(檔名, 等於哪個 ref)]、pending＝同根本 session 還有現行改碼（沒退回）的程式檔。
    刻意紅＝有退回的檔**而且**同根沒有任何自己的現行改碼（那時跑紅不可能是自己現行的碼造成）；只退回其中一檔、另一檔還留著真錯
    → 真的紅照記。"""
    if reverted and not pending:
        name, ref = reverted[0]
        return Verdict("RED_WHILE_REVERTED", False, f"跑紅時 {name} 的內容等於 {ref} 的已提交版本、同根沒有其他現行改碼（退回舊碼反證）",
                       tuple(f"{n} == {r}" for n, r in reverted[:3]))
    if reverted and pending:
        return Verdict("RED_WHILE_REVERTED", True, f"同根還有現行改碼（{'、'.join(pending[:3])}），這次紅不能算刻意", tuple(f"{n} == {r}" for n, r in reverted[:2]))
    return Verdict("RED_WHILE_REVERTED", True, "跑紅時沒有改檔處在已提交的舊版本，是真的紅", ())


RULES["COMMIT_ORDER_DECISION_ALWAYS_LOGGED"] = ("git commit 口令閘（handlers/pre_tool_use.check_git_commit_order）判出這條指令會 commit 之後，每個結果都留一筆 "
                                                "Logs/guard-commit_order.jsonl（event：denied／order＋口令字／quoted＋引的原句／temp_exempt／"
                                                "claude_exempt／fail_open／error，帶 session_id、allowed、指令前 200 字）；不是 commit 的指令不寫。"
                                                "放行條件裡有交給 LLM 判的語意授權（授權原句），事後要抽查得到。")
RULES["PROJECT_RULE_WORDS_ARE_HINTS"] = ("背景自動萃取（user-extract-worker）與存量整理（classify-project-scope plan）判「這條是不是專案專屬規則」時，"
                                        "線索詞（此專案／本專案／上傳／發布／必須／禁止／git／svn…）只是提示：命中只有線索詞 → 萃取落 personal、"
                                        "留帳 guard-scope_hint（event=hint，附命中的詞與原句），整理建議表列 suggest=review（疑似專案專屬，待確認）"
                                        "附命中的詞給人判，不自動寫 shared、不自動搬。可定案的只有 L2（LLM）宣告 shared，與查得到的事實"
                                        "（目前專案的專名、專案路徑、已登記專案名）。")
RULES["NEGATIVE_CONTROL_DECLARED"] = ("刻意拿舊碼（或別的對照組）跑測試、預期它紅＝負向對照：宣告行「負向對照｜<這條指令裡出現的路徑或字樣>："
                                      "<理由>」（回覆文字／工具參數／thinking 三管道，主檔與子代理檔，含這次指令自己的 `#` 註解）點到的字樣"
                                      "是這條指令的一段、理由有文字內容 → 這次紅記 deliberate_reds（rule＝本規則、附宣告行），不進 failing_tests、"
                                      "不計重試；點到的字樣不在指令裡、沒寫理由、沒宣告 → 照記紅。宣告只綁出現那段字樣的指令，蓋不到別的紅。"
                                      "收尾入口（handlers/stop.py 紅測閘之前）：紅記了之後才在本回合回覆寫這一行、點到的字樣在那筆紅存的指令（前 200 字）裡 → "
                                      "那筆從 failing_tests 搬到 deliberate_reds、留帳 guard-testfail_scope event=negative_control_declared，不必重跑；"
                                      "搬過就不會再被拿來擋。")
_NEG_CONTROL_RE = lazy_re(r"負向對照\s*[｜|]\s*(.+)")


def parse_negative_controls(text: str) -> List[Dict[str, str]]:
    """「負向對照｜<字樣>：<理由>」→ [{subject, reason, line}]；字樣與理由用第一個「：」分，沒有全形冒號才找不接路徑分隔的「:」。"""
    out: List[Dict[str, str]] = []
    for raw in str(text or "").splitlines():
        m = _NEG_CONTROL_RE.search(raw)
        if not m:
            continue
        rest = m.group(1)
        sep = rest.find("：")
        if sep < 0:
            ascii_sep = _JUDGE_CARD_ASCII_SEP_RE.search(rest)
            subject, reason = (rest[:ascii_sep.start()], rest[ascii_sep.end():]) if ascii_sep else (rest, "")
        else:
            subject, reason = rest[:sep], rest[sep + 1:]
        out.append({"subject": subject.strip().strip("`'\"「」"), "reason": reason.strip(), "line": raw.strip()[:240]})
    return out


def negative_control_verdict(command: str, decls: Sequence[Dict[str, str]]) -> Verdict:
    """NEGATIVE_CONTROL_DECLARED：owed＝這次紅要照記（沒有點到這條指令、附理由的負向對照宣告）。斜線方向不分；
    比的是指令真的會跑的行（`#` 註解行去掉），宣告寫在註解裡不能自己對上自己。"""
    rule = "NEGATIVE_CONTROL_DECLARED"
    cmd = "\n".join(ln for ln in str(command or "").splitlines() if not ln.lstrip().startswith("#")).replace("\\", "/")
    for d in decls:
        subject = d["subject"].replace("\\", "/")
        if subject and subject in cmd and reason_present(d["reason"]):
            return Verdict(rule, False, f"宣告過負向對照：{d['subject']}", (d["line"],))
    return Verdict(rule, True, "沒有點到這條指令、附理由的負向對照宣告", ())


RETRY_ESCALATE_ROUNDS = 2          # 兩輪重跑仍紅就升級 FixEscalation（plan 與 direct 同一個門檻）
RETRY_ROUNDS_SHOWN = 5             # 訊息最多列幾輪證據
_RED_CASE_RE = lazy_re(r"^(?:FAILED|ERROR) (\S+)", re.MULTILINE)


def red_case_names(summary: str) -> List[str]:
    """pytest 輸出裡紅掉的案例（FAILED／ERROR 開頭那行的節點 id），依出現順序、去重。"""
    out: List[str] = []
    for name in _RED_CASE_RE.findall(str(summary or "")):
        if name not in out:
            out.append(name)
    return out


_PYTEST_TALLY_RE = lazy_re(r"^=*\s*\d+ (?:passed|failed|errors?|skipped|deselected|xfailed|xpassed|warnings?)\b.*$",
                              re.MULTILINE)
RED_CASES_CAP = 200     # 收據最多記這麼多支紅案；超過就當清單不完整


def red_case_facts(output: str) -> Tuple[List[str], bool]:
    """SCOPE_RED_ONLY_ITS_CASES 的事實：pytest 輸出裡紅掉的案例（red_case_names）與這份清單完不完整：最後一行 pytest 結算
    （「N failed, M passed … in Xs」）的 failed＋error 數要等於列出的紅案數。沒有結算行（輸出被截、不是 pytest）、數不合、
    超過 RED_CASES_CAP → 不完整。"""
    names = red_case_names(output)
    tallies = _PYTEST_TALLY_RE.findall(str(output or ""))
    if not names or not tallies or len(names) > RED_CASES_CAP:
        return names[:RED_CASES_CAP], False
    count = sum(int(n) for n in re.findall(r"(\d+) (?:failed|errors?)\b", tallies[-1]))
    return names, count == len(names)


def same_test_run(prev_cmd: str, cmd: str, prev_cwd: Optional[str] = None, cwd: Optional[str] = None) -> bool:
    """RETRY_COUNTS_RERUN_CYCLES：這次是不是重跑同一組測試。兩邊點名的程式檔集合完全相同（共用的設定檔不會讓不同案例檔
    算同一組；兩邊都給 cwd 就比絕對路徑），或兩邊都沒點名檔而指令前 40 字相同。"""
    both = bool(prev_cwd) and bool(cwd)
    a = set(case_files_in_cmd(prev_cmd, prev_cwd if both else None))
    b = set(case_files_in_cmd(cmd, cwd if both else None))
    if a or b:
        return a == b
    return str(prev_cmd).strip()[:40] == str(cmd).strip()[:40]


def retry_round_verdict(prev_red: Any, edited: Any, round_no: int, cmd: str, red_cases: Sequence[str]) -> Verdict:
    """RETRY_COUNTS_RERUN_CYCLES：測試又跑紅了，這次算不算一輪重試。prev_red＝同一組測試還活著的紅（呼叫端用
    same_test_run 找；沒有就是 None）、edited＝那組上次跑之後改過的檔；重跑同一組、而且中間碼有改過（不論幾次、
    幾個檔）才算一輪。不猜改檔是為了修哪一組：同時修好幾組時，沒改到的那組重跑仍紅也算（已知限制）。"""
    if not isinstance(prev_red, dict):
        return Verdict("RETRY_COUNTS_RERUN_CYCLES", False, "不是重跑同一組測試（第一次跑或別組）", ())
    if not edited:
        return Verdict("RETRY_COUNTS_RERUN_CYCLES", False, "這組上次跑之後沒改過檔，只是重跑", ())
    return Verdict("RETRY_COUNTS_RERUN_CYCLES", True, f"第 {round_no} 輪：紅了、改了、再跑仍紅",
                   (f"指令 {str(cmd)[:120]}", f"紅案 {'、'.join(red_cases[:3]) or '（輸出沒列案例）'}",
                    f"改過 {'、'.join(sorted(edited)[:3])}"))


def retry_rounds_text(rounds: Sequence[Dict[str, Any]]) -> str:
    """FixEscalation／DeepPostMortem 共用的證據行（format_hit 格式，字母 r，parse_hits 讀得到）：規則名、第幾輪、
    每輪的重跑指令與紅案（輸出沒列案例就用失敗摘要第一行）。"""
    shown = [r for r in rounds if isinstance(r, dict)][-RETRY_ROUNDS_SHOWN:]
    if not shown:
        return format_hit("r", Verdict("RETRY_COUNTS_RERUN_CYCLES", True, "沒有逐輪紀錄", ()))
    rows = tuple(f"第 {r.get('round')} 輪 指令 {str(r.get('cmd', ''))[:120]} 紅案 "
                 f"{'、'.join(r.get('red') or []) or r.get('summary') or '（輸出沒列案例）'}" for r in shown)
    return format_hit("r", Verdict("RETRY_COUNTS_RERUN_CYCLES", True, f"第 {shown[-1].get('round')} 輪重跑仍紅", rows))


def fix_escalation_text(state: Dict[str, Any]) -> Optional[str]:
    """重試輪數到門檻 → FixEscalation 提示（標頭、規則證據行、照做就能過的下一步）；沒到回 None。"""
    count = int(state.get("wisdom_retry_count", 0) or 0)
    if count < RETRY_ESCALATE_ROUNDS:
        return None
    return (f"[Guardian:FixEscalation] 偵測到重複修正（retry={count}）。\n{retry_rounds_text(state.get('retry_rounds') or [])}\n"
            "依「精確修正升級」規則先停下直接修：用三句寫出①失敗現象與原文、②已試過的改法與各自為何沒解、"
            "③下一個能區分候選原因的最小檢查；做完那個檢查再動手。刻意跑紅（退回舊碼反證）不算在內。")


MOVE_TOOL = "move-dir-check.py"


def move_dir_verdict(move: Dict[str, Any], scan_hits: Optional[int], sample_ok: bool,
                     hit_lines: Sequence[str] = ()) -> Verdict:
    """MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE：一筆搬目錄（呼叫端蒐集：舊、新路徑與時間）配上搬之後的收據事實
    （scan_hits＝最後一次合格掃描的命中數，沒有就 None；sample_ok＝有合格的抽樣 PASS），回欠不欠。"""
    rule = "MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE"
    old, new = str(move.get("old") or "（舊路徑不明）"), str(move.get("new") or "")
    missing, why_parts = [], []
    if scan_hits is None:
        missing.append("缺路徑引用掃描收據 MOVE_PATH_SCAN（搬之後跑、點名舊路徑）")
        why_parts.append("MOVE_PATH_SCAN")
    elif scan_hits > 0:
        missing.append(f"最後一次路徑引用掃描 hits={scan_hits}：修碼後重掃到 0，刻意保留的用 --allow 註明")
        why_parts.append(f"MOVE_PATH_SCAN hits={scan_hits}")
    if not sample_ok:
        missing.append("缺抽樣驗證收據 MOVE_SAMPLE_CHECK PASS（搬之後跑、--for 點名這個新目錄）")
        why_parts.append("MOVE_SAMPLE_CHECK")
    if not missing:
        return Verdict(rule, False, f"{old} → {new} 兩張收據都有", ())
    tool = str(Path(__file__).resolve().parent.parent / "tools" / MOVE_TOOL)
    run = "<被搬模組的 import 或目標 verify 指令>"
    how = []
    for shell, q in (("Bash", shlex.quote), ("PowerShell", _ps_quote)):
        how.append(f"掃描（{shell}）：python {q(tool)} scan --old {q(old)} --new {q(new)}")
        how.append(f"抽樣（{shell}）：python {q(tool)} sample --for {q(new)} --run {q(run)}")
    how.append(f"C# 抽樣再加 --csproj-check <新目錄>")
    return Verdict(rule, True, f"搬了含程式檔的目錄 {old} → {new}，還缺 {'、'.join(why_parts)}（不欠整組案例）",
                   (*missing, *[f"命中 {h}" for h in list(hit_lines)[:5]], *how))


def _ps_quote(s: str) -> str:
    """PowerShell 單引號字串（裡面的單引號寫兩次），整段照字面、不展開變數。"""
    return "'" + str(s).replace("'", "''") + "'"


def collapse_move_chain(moves: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE 的搬移鏈：照先後（seq，沒有就 at）把「A→B、B→C」併成 A→C，時間取最後一次搬
    （收據要在最後一次搬之後）；完整搬回原處（A→B→A）就不欠。同一個 session、同一個子代理的搬移才串。"""
    out: List[Dict[str, Any]] = []
    for m in sorted(moves, key=lambda x: (int(x.get("seq") or 0), str(x.get("at") or ""))):
        prev = next((e for e in out if canon_path(e.get("new") or "") == canon_path(m.get("old") or "")
                     and e.get("session_id") == m.get("session_id") and e.get("agent_id", "") == m.get("agent_id", "")), None)
        if prev is None:
            out.append(dict(m))
            continue
        prev.update({"new": m.get("new"), "at": m.get("at"), "seq": m.get("seq")})
        if canon_path(prev.get("old") or "") == canon_path(prev.get("new") or ""):
            out.remove(prev)
    return out


_NARROW_FLAG_RE = lazy_re(r"(?:^|\s)(?:-k|-m|-t|--testNamePattern|--deselect|--lf|--last-failed)(?=\s|=|$)")
_RUN_MODULE_RE = lazy_re(r"(?:^|\s)-m\s+(?:pytest|unittest)\b")     # python -m pytest 的 -m 是「跑模組」，不是標記篩選
_NODE_ID_TOKEN_RE = lazy_re(r"""[^\s"']+::[^\s"']+""")
_CMD_SEG_SPLIT_RE = lazy_re(r"\|\||&&|[;|\n]")
_TEST_RUNNER_RE = lazy_re(r"(?:^|[\s/\\\"'])(?:pytest|py\.test|unittest|jest|vitest)(?:\.exe)?(?=[\s\"']|$)", re.IGNORECASE)


def _test_runner_args(cmd: str) -> str:
    """指令裡測試子命令之後的文字：以 ; && || | 換行切段，只取含 pytest／unittest／jest／vitest 的段、子命令之後那截；
    同一指令別段的 `python -m <模組>` 不算篩選。沒有任何段認得出測試子命令 → 整條（-m pytest／unittest 已剝），照舊保守判。"""
    text = str(cmd or "")
    parts = [seg[m.end():] for seg in _CMD_SEG_SPLIT_RE.split(text) for m in [_TEST_RUNNER_RE.search(seg)] if m]
    return " ; ".join(parts) if parts else _RUN_MODULE_RE.sub(" ", text)


def _norm_node(s: str) -> str:
    return str(s).strip().strip("'\"").replace("\\", "/").lower().lstrip("./")


def _node_covered(red: str, nodes: Sequence[str]) -> bool:
    """紅掉的案例在不在綠點名的節點裡（同一個節點，或路徑寫法不同但尾段相同）。"""
    return any(red == n or red.endswith("/" + n) or n.endswith("/" + red) for n in nodes)


def green_covers_red_verdict(red_cmd: str, red_summary: str, green_cmd: str) -> Verdict:
    """GREEN_NARROWED_KEEPS_UNCOVERED_RED：這次綠能不能清這筆紅（owed＝True 表示照留）。綠沒有篩選 → 交給既有清帳規則；
    有篩選（節點 id、-k、-m、Jest -t）→ 紅掉的案例（red_case_names）都在綠點名的節點裡才清；同一個篩選指令重跑也清；
    其餘照留（-k 運算式判不了、輸出沒列案例）。篩選旗標與節點 id 只看測試子命令之後（_test_runner_args）。"""
    rule = "GREEN_NARROWED_KEEPS_UNCOVERED_RED"
    args = _test_runner_args(green_cmd)
    nodes = [_norm_node(n) for n in _NODE_ID_TOKEN_RE.findall(args)]
    if not nodes and not _NARROW_FLAG_RE.search(args):
        return Verdict(rule, False, "綠的沒有篩選案例，照既有清帳規則", ())
    if " ".join(str(red_cmd or "").split()) == " ".join(str(green_cmd or "").split()):
        return Verdict(rule, False, "綠的是同一個篩選指令重跑", ())
    red = [_norm_node(c) for c in red_case_names(red_summary)]
    missing = [r for r in red if not _node_covered(r, nodes)]
    if red and not missing:
        return Verdict(rule, False, "紅掉的案例都在綠點名的節點裡", tuple(red[:3]))
    return Verdict(rule, True, "綠只跑了篩選過的案例，沒涵蓋紅掉的，那筆紅照留",
                   (f"綠 {str(green_cmd)[:120]}", f"沒涵蓋 {'、'.join(missing[:3]) or '（紅的輸出沒列案例，判不了涵蓋）'}"))


def _file_covered(red_file: str, files: Sequence[str]) -> bool:
    """同一個檔：路徑相同或尾段相同（pytest 節點相對它的 rootdir、指令相對 cwd，兩邊只能靠尾段接起來）。"""
    return any(red_file == f or red_file.endswith("/" + f) or f.endswith("/" + red_file) for f in files)


def _dir_covered(red_file: str, dirs: Sequence[str]) -> bool:
    return any(red_file.startswith(d + "/") or f"/{d}/" in "/" + red_file for d in dirs)


# 會吃下一個參數當值的 pytest 選項：它後面那個字不是要跑的路徑
_VALUE_OPTS = frozenset({"-k", "-m", "-p", "-c", "-o", "-n", "-W", "--tb", "--maxfail", "--basetemp", "--rootdir", "--deselect",
                         "--ignore", "--ignore-glob", "--junitxml", "--junit-xml", "--cov", "--cov-report", "--durations",
                         "--log-level", "--confcutdir", "--import-mode", "--lfnf", "--capture"})
_PATH_ARG_RE = lazy_re(r"^[\w./\-]+$")


def _runner_dirs(args: str) -> List[str]:
    """測試子命令之後點名的目錄（不是選項、不是選項的值、沒有副檔名、不是節點）；「.」＝整套不算。小寫正斜線。"""
    toks = [t.strip("'\"").replace("\\", "/") for t in str(args or "").split()]
    out: List[str] = []
    for i, t in enumerate(toks):
        prev = toks[i - 1] if i else ""
        if (not t or t.startswith("-") or "::" in t or not _PATH_ARG_RE.match(t) or prev in _VALUE_OPTS
                or re.search(r"\.[A-Za-z0-9]+$", t)):
            continue
        d = t.lower().strip("/").removeprefix("./")
        if d and d != "." and d not in out:
            out.append(d)
    return out


def green_ran_cases_verdict(red_cmd: str, red_summary: str, green_cmd: str,
                            cleared: Sequence[str] = ()) -> Tuple[Verdict, List[str]]:
    """GREEN_CLEARS_ONLY_CASES_IT_RAN：這次綠跑到這筆紅的哪幾支。回 (Verdict, 跑到的紅案)；owed＝True 表示還有沒跑到的、那筆紅照留
    （呼叫端把跑到的那幾支記進 cleared_units）。cleared＝之前的綠已經跑到的（不再算）。綠點名的範圍＝節點、整檔、目錄；同一組點名重跑
    全清；有 -k／-m 這類篩選交給 green_covers_red_verdict（只看還沒清掉的那幾支）；綠什麼都沒點名＝整套，全清。"""
    rule = "GREEN_CLEARS_ONLY_CASES_IT_RAN"
    args = _test_runner_args(green_cmd)
    nodes = [_norm_node(n) for n in _NODE_ID_TOKEN_RE.findall(args)]
    files = case_files_in_cmd(_NODE_ID_TOKEN_RE.sub(" ", args))
    dirs = _runner_dirs(args)
    listed = failed_units(red_summary)
    red = [u for u in listed if u not in set(cleared or ())]
    if _NARROW_FLAG_RE.search(args):
        left = "\n".join(f"FAILED {u}" for u in red) if listed else red_summary
        v = green_covers_red_verdict(red_cmd, left, green_cmd)
        return v, ([] if v.owed else red)
    if not nodes and not files and not dirs:
        return Verdict(rule, False, "綠沒點名檔、目錄也沒篩選（跑整套）", ()), red
    if " ".join(_test_runner_args(red_cmd).split()) == " ".join(args.split()):
        return Verdict(rule, False, "綠是同一組點名重跑", ()), red
    if not red:
        red_args = _test_runner_args(red_cmd)
        red_sel = case_files_in_cmd(red_args) + _runner_dirs(red_args)
        if red_sel and all(_file_covered(f, files) or _dir_covered(f, dirs) or f in dirs for f in red_sel):
            return Verdict(rule, False, "紅的輸出沒列案例，紅點名的範圍綠都跑了", tuple(red_sel[:3])), []
        return Verdict(rule, True, "紅的輸出沒列案例、綠只跑了點名的範圍，判不了有沒有跑到紅的那支，那筆紅照留",
                       (f"綠 {str(green_cmd)[:120]}", f"紅 {str(red_cmd)[:120]}")), []
    ran = [u for u in red if _node_covered(u, nodes) or _file_covered(u.split("::", 1)[0], files)
           or _dir_covered(u.split("::", 1)[0], dirs)]
    left = [u for u in red if u not in ran]
    if not left:
        return Verdict(rule, False, "紅掉的案例綠都跑到了", tuple(ran[:3])), ran
    return Verdict(rule, True, f"綠只跑到紅的 {len(ran)} 支、還有 {len(left)} 支沒跑，沒跑到的照留",
                   (f"綠 {str(green_cmd)[:120]}", f"沒跑到 {'、'.join(left[:3])}")), ran


_CASE_EXTS = r"(?:py|js|ts|cs|lua|go|rs|rb|java|kt|sh|ps1)"
_CASE_TOKEN_RE = lazy_re(r"[\w./\\:-]+\." + _CASE_EXTS + r"\b", re.IGNORECASE)
_QUOTED_CASE_RE = lazy_re(r"""(["'])([^"'\n]*?\.""" + _CASE_EXTS + r""")(?:::[^"'\n]*)?\1""", re.IGNORECASE)


def case_files_in_cmd(cmd: str, cwd: Optional[str] = None) -> List[str]:
    """指令裡像程式檔的 token，保留路徑（不只檔名：service_a/tests/test_api.py 與 service_b/… 是兩個檔）；
    引號裡的路徑整段算一個（`"my tests/test_a.py"` 不切成 tests/test_a.py）。
    給 cwd 時相對路徑接在 cwd 後面變成絕對正規化路徑。`::test_x` 尾段去掉。"""
    text = str(cmd or "")
    raws = [m.group(2) for m in _QUOTED_CASE_RE.finditer(text)]
    raws += [m.group(0) for m in _CASE_TOKEN_RE.finditer(_QUOTED_CASE_RE.sub(" ", text))]
    out: List[str] = []
    for raw in raws:
        tok = raw.replace("\\", "/").split("::", 1)[0]
        if cwd and not (os.path.isabs(tok) or re.match(r"^[A-Za-z]:/", tok)):
            tok = str(cwd).replace("\\", "/").rstrip("/") + "/" + tok
        key = canon_path(tok) if (cwd or os.path.isabs(tok) or re.match(r"^[A-Za-z]:/", tok)) else tok.lower().lstrip("./")
        if key and key not in out:
            out.append(key)
    return out


def green_clears_red(red_cmd: str, green_cmd: str, red_cwd: Optional[str] = None, green_cwd: Optional[str] = None) -> bool:
    """GREEN_SAME_CASE_CLEARS：綠的指令點名的案例檔與紅的是同一個檔（含目錄；兩邊都給 cwd 就比絕對路徑，沒給就比指令裡的相對路徑原字）。
    兩邊都沒點名檔 → False（交給既有前綴／pytest 規則）。只有一邊有 cwd → 不比絕對路徑，照相對字串比。"""
    both = bool(red_cwd) and bool(green_cwd)
    a = set(case_files_in_cmd(red_cmd, red_cwd if both else None))
    b = set(case_files_in_cmd(green_cmd, green_cwd if both else None))
    return bool(a and b and (a & b))


# ─── 同一條指令跑了不只一次測試：每支紅案以最後一次看得出範圍的結果為準 ─────────────────────────────
# heredoc 內文不是 shell 指令（文件補丁／內嵌 python 常含「git commit」「pytest」字樣）；剝掉再拆段：口令閘不把文字當 commit 段、
# 紅測記帳不把內文的「import pytest」當成一段測試。只剝內文（起始行 delimiter 之後到第一個結束行，零行內文也算）：起始行 delimiter
# 後面的字（`cat > msg <<'EOF' && git commit -F msg` 的 commit 在那裡）是真命令，照留。逐行掃不用 regex 跨行比對，所以空 heredoc
# 後面接同名 heredoc 不會把中間的命令一起剝掉。沒有結束行的 heredoc 不動，內文會被當命令段檢查（寧多擋）。
HEREDOC_MARK = "<<HEREDOC_STRIPPED"
_HEREDOC_START_RE = lazy_re(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1(.*)$")


def strip_heredoc_bodies(command: str) -> str:
    lines = (command or "").split("\n")
    out: List[str] = []
    i = 0
    while i < len(lines):
        m = _HEREDOC_START_RE.search(lines[i])
        end = next((k for k in range(i + 1, len(lines)) if lines[k].strip() == m.group(2)), None) if m else None
        if end is None:
            out.append(lines[i])
            i += 1
            continue
        out.append(lines[i][:m.start()] + HEREDOC_MARK + m.group(3))
        i = end + 1
    return "\n".join(out)


RULES["RED_LAST_RESULT_IN_COMMAND"] = ("同一條指令跑了不只一次測試（輸出有多個 pytest 結算行）：每支紅案以這條指令裡最後一次「看得出範圍」的結果為準。"
                                        "看得出範圍的段＝解析得出測試子命令與點名範圍的段；heredoc 內文餵給直譯器的那段（`python - <<EOF`）看不出跑了哪支。"
                                        "紅之後同一指令裡看得出範圍的綠跑到它 → 不記；紅來自看不出範圍的段、而同一指令裡看得出範圍的綠跑過它（不分先後）→ 不記"
                                        "（看不出來源的紅蓋不掉看得出來源的綠，比照 RECEIPT_UNPARSED_GENERAL_ONLY）；看得出範圍的紅之後只有看不出範圍的綠 → 照記；"
                                        "段數對不上結算數、哪次紅沒逐支列出 → 判不了，照舊整筆記。全部不記 → 這次紅記 deliberate_reds（rule＝本規則）、不進 failing_tests、"
                                        "不計重試，同指令看得出範圍的綠照常清舊紅；部分不記 → 不記的那幾支預先記進那筆紅的 cleared_units。只跑一次的指令不在此列"
                                        "（heredoc 裡單跑一次紅照記）。判定 wg_release_rules.red_units_last_result（事實 test_segments／command_test_runs），"
                                        "套用點 handlers/post_tool_use._track_test_result（負向對照之後、重試計數之前），留帳 guard-testfail_scope event=red_last_result。")
_CONTINUATION_RE = lazy_re(r"[\\`]\r?\n")
# heredoc 餵給直譯器的那段：會跑東西（可能跑測試）但看不出跑了哪支；`cat > 檔 <<EOF` 只是寫檔，不算一段
_INTERPRETER_HEREDOC_RE = lazy_re(r"(?:^|[\s/\\])(?:python[0-9.]*|py|node|bash|sh|zsh|pwsh|powershell|ruby|perl)(?:\.exe)?\b[^\n]*<<HEREDOC_STRIPPED",
                                  re.IGNORECASE)


def test_segments(command: str) -> List[Tuple[str, bool]]:
    """指令裡依序會跑測試的段 [(段文字, 看得出範圍)]：heredoc 內文先剝掉、續行先併，再照 ; && || | 換行切段；認得出測試子命令的段
    看得出範圍（點名的檔、目錄、節點、篩選都在段裡）；heredoc 餵給直譯器的段看不出範圍。"""
    text = _CONTINUATION_RE.sub(" ", strip_heredoc_bodies(str(command or "")))
    out: List[Tuple[str, bool]] = []
    for seg in _CMD_SEG_SPLIT_RE.split(text):
        if _TEST_RUNNER_RE.search(seg):
            out.append((" ".join(seg.split()), True))
        elif _INTERPRETER_HEREDOC_RE.search(seg):
            out.append((" ".join(seg.split()), False))
    return out


def command_test_runs(output: str) -> List[Tuple[List[str], bool]]:
    """輸出裡每一次 pytest 結算（結算行）依序 → (這一次之前逐支列出的 FAILED／ERROR 節點, 這一次綠不綠)；結算行上沒有非零的 failed／error 就是綠。"""
    runs: List[Tuple[List[str], bool]] = []
    pending: List[str] = []
    for raw in str(output or "").splitlines():
        line = raw.strip()
        m = _FAILED_UNIT_RE.match(line)
        if m:
            pending.append(m.group(1).replace("\\", "/").lower())
            continue
        if _PYTEST_TALLY_RE.match(line):
            green = not re.search(r"\b[1-9]\d* (?:failed|errors?)\b", line.lower())
            runs.append((list(dict.fromkeys(pending)), green))
            pending = []
    return runs


def red_units_last_result(segments: Sequence[Tuple[str, bool]],
                          runs: Sequence[Tuple[List[str], bool]]) -> Optional[Tuple[List[str], List[str], str]]:
    """RED_LAST_RESULT_IN_COMMAND：segments＝test_segments、runs＝command_test_runs，依序一一對應。回 (照記的紅案, 不記的紅案, 一句原因)；
    只跑一次、段數對不上結算數、哪次紅沒逐支列出 → None（判不了，照舊整筆記）。"""
    if len(runs) < 2 or len(segments) != len(runs) or any(not units and not green for units, green in runs):
        return None

    def covers(unit: str, seg: str) -> bool:
        v, ran = green_ran_cases_verdict("", f"FAILED {unit}", seg)
        return (not v.owed) or unit in ran

    keep: List[str] = []
    drop: List[str] = []
    for u in dict.fromkeys(u for units, _ in runs for u in units):
        last_red = max(i for i, (units, _) in enumerate(runs) if u in units)
        greens = [j for j, (_, green) in enumerate(runs) if green and segments[j][1] and covers(u, segments[j][0])]
        if any(j > last_red for j in greens) or (not segments[last_red][1] and greens):
            drop.append(u)
        else:
            keep.append(u)
    why = (f"同一條指令跑了 {len(runs)} 次測試，每支以最後一次看得出範圍的結果為準："
           f"{len(drop)} 支之後（或紅來自看不出範圍的段時，不分先後）有看得出範圍的綠跑過、不記；{len(keep)} 支還紅")
    return keep, drop, why


# ─── 需求目標樹的完整對照：GOAL_DONE_NEEDS_CASE_OR_RECEIPT／GOAL_INFERRED_MAX_PARTIAL／CASE_RED_THEN_GREEN ───
# evidence 一筆＝(種類, 證據級, 收據紅不紅, 顯示字)；種類與證據級用 need_goal 的列舉值（receipt／case／file／atom、measured／read／inferred）

def receipt_red(verdicts: Iterable[str], exit_code: Any) -> bool:
    """收據紅不紅：任一哨兵 FAIL（verdicts 是「名稱:結論」字串），或 exit 不是 0；沒記 exit 不算紅。"""
    return any(str(v).upper().endswith(":FAIL") for v in verdicts or ()) or exit_code not in (0, None)


def receipt_green(verdicts: Iterable[str], exit_code: Any) -> bool:
    """收據綠不綠：有 PASS 而且沒紅（只有 DONE 的量測收據不算綠）。"""
    return any(str(v).upper().endswith(":PASS") for v in verdicts or ()) and not receipt_red(verdicts, exit_code)


def _evidence_have(node: str, evidence: Sequence[Tuple[str, str, bool, str]]) -> str:
    return f"{node} 現有證據：" + ("、".join(text + ("（紅）" if red else "") for _, _, red, text in evidence) or "沒有")


def goal_done_evidence_verdict(node: str, code_tree: bool, evidence: Sequence[Tuple[str, str, bool, str]]) -> Verdict:
    """GOAL_DONE_NEEDS_CASE_OR_RECEIPT：標「達成」的節點有沒有試過的證據（沒紅的收據，或讀碼級的驗證案例）。"""
    rule = "GOAL_DONE_NEEDS_CASE_OR_RECEIPT"
    if not code_tree:
        return Verdict(rule, False, f"{node} 在記憶知識類的樹，不要求案例或收據")
    tried = [text for kind, level, red, text in evidence
             if (kind == "receipt" and not red) or (kind == "case" and level == "read")]
    if tried:
        return Verdict(rule, False, f"{node} 標「達成」有試過的證據", tuple(tried[:2]))
    return Verdict(rule, True, f"{node} 標「達成」但沒指到試過的驗證案例或沒紅的收據（沒試過不算達成，做不到就標部分＋followup）",
                   (_evidence_have(node, evidence), "要有：沒紅的收據 R<號>（實測）或驗證案例檔（讀碼）"))


def goal_inferred_verdict(node: str, evidence: Sequence[Tuple[str, str, bool, str]]) -> Verdict:
    """GOAL_INFERRED_MAX_PARTIAL：標「達成」的節點證據全是推論 → 擋。沒附證據不歸這條（另有「沒附證據」）。"""
    rule = "GOAL_INFERRED_MAX_PARTIAL"
    if evidence and all(level == "inferred" for _, level, _, _ in evidence):
        return Verdict(rule, True, f"{node} 標「達成」但證據只有推論（推論最多標部分）", (_evidence_have(node, evidence),))
    return Verdict(rule, False, f"{node} 的證據不是只有推論")


def red_then_green(case_path: str, receipts: Sequence[Tuple[Any, Sequence[str], bool, bool]]) -> Optional[Tuple[Any, Any]]:
    """CASE_RED_THEN_GREEN：receipts＝依時間排的 [(收據號, 點名的案例檔, 紅, 綠)]，案例檔是 case_files_in_cmd 帶 cwd 解出的
    絕對正規化路徑（同名不同目錄不算同一個）；點名 case_path 的收據裡第一筆紅之後有綠 → (紅的號, 綠的號)；對不上回 None。"""
    key = canon_path(case_path)
    red = None
    for seq, cases, is_red, is_green in receipts:
        if key not in cases:
            continue
        if is_red and red is None:
            red = seq
        elif is_green and red is not None:
            return red, seq
    return None


# ─── G0 綜觀：LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES／EDITED_PART_NEEDS_GOAL_NODE ───

_LABEL_NO = {**{c: 1 for c in "Aa1一甲Ａ１①"}, **{c: 2 for c in "Bb2二乙Ｂ２②"}, **{c: 3 for c in "Cc3三丙Ｃ３③"},
             **{c: 4 for c in "Dd4四丁Ｄ４④"}, **{c: 5 for c in "Ee5五戊Ｅ５⑤"}}
_LABELS = "".join(_LABEL_NO)
# 候選標記：「候選 A／候選一／候選（B）」或「第一根因／第 2 個根因」
_CANDIDATE_RE = lazy_re(rf"候選\s*[（(]?\s*([{_LABELS}])|第\s*([{_LABELS}])\s*個?\s*根因")
_REASON_WORDS = r"(?:(?<!根)因為|理由|原因|由於|所以|because)"
_REASON_RE = lazy_re(_REASON_WORDS, re.IGNORECASE)
# 「不存在／沒有／無」後面接標點、理由詞或行尾才算「這個候選不存在」（「候選 A 無鎖競爭」是描述）
_ABSENT_WORD = rf"(?:不存在|沒有|找不到|無)(?=\s*(?:[，,。；;:：]|{_REASON_WORDS}|$))"
_ABSENT_RE = lazy_re(rf"\s*[:：]?\s*(?:是)?\s*{_ABSENT_WORD}", re.IGNORECASE)
# 「第二個不存在，因為…」「第二根因不存在：…」「候選 B 不存在因為…」：要寫出為什麼
_SECOND_ABSENT_RE = lazy_re(
    rf"(?:第\s*[二2]\s*個?\s*(?:根因|候選)?|候選\s*[（(]?\s*[Bb二乙Ｂ２②])\s*[:：]?\s*(?:是)?\s*{_ABSENT_WORD}"
    rf"[^；;。]*?(?:{_REASON_WORDS}|[:：])\s*\S{{2,}}", re.IGNORECASE)
_ROLE_PLACEHOLDERS = {"", "角色", "這一塊在目標裡的角色", "這一塊的角色", "…", "...", "略", "無"}
_ROLE_STRIP_RE = lazy_re(r"[\s，。、；;:：,.!！?？「」『』（）()【】\[\]<>《》—－\-~～*_`'\"]+")


_ENUM_NO = {**{c: i for i, c in enumerate("①②③④⑤", 1)}, **{c: i for i, c in enumerate("⑴⑵⑶⑷⑸", 1)},
            **{c: i for i, c in enumerate("12345", 1)}, **{c: i for i, c in enumerate("一二三四五", 1)}}
# 列舉：①②、⑴⑵、(1)(2)／（一）（二）；括號數字前面接英數字的是函式呼叫，不算
_ENUM_RE = lazy_re(r"([①-⑤⑴-⑸])|(?<![A-Za-z0-9_])[（(]\s*([1-5一二三四五])\s*[)）]")
_LAYER_RE = lazy_re(r"([A-Za-z][A-Za-z0-9_\-]*|[一-鿿]+)\s*層")
# 「這層、每層、第二層、第四層、跨層」這類泛稱（層前一個字）與「根因層」不是一層的名字
_LAYER_GENERIC_TAIL = set("這那哪每同各一二兩三四五六七八九十百幾多上下本該底表外內深單雙其此某任跨分0123456789")
_LAYER_LEAD_RE = lazy_re(r"^.*[在是於從到修改看查的為由和與及或往向把將先再都只就也跟]")


def _absent_after(text: str, end: int) -> bool:
    return bool(_ABSENT_RE.match(text, end))


def _unlabeled_candidates(text: str) -> List[int]:
    """LOCATE_CANDIDATES_WITHOUT_FIXED_LABELS：沒寫固定標記時，兩個以上的列舉、或兩個以上不同名稱的「<名稱>層」當候選。"""
    enums: List[int] = []
    for m in _ENUM_RE.finditer(text):
        n = _ENUM_NO[m.group(1) or m.group(2)]
        if not _absent_after(text, m.end()) and n not in enums:
            enums.append(n)
    if len(enums) >= 2:
        return enums
    layers: List[str] = []
    for m in _LAYER_RE.finditer(text):
        name = m.group(1).lower()
        if name[-1] in _LAYER_GENERIC_TAIL or name.endswith("根因"):
            continue
        # 中文前面常黏著動詞與介詞（「根因在邏輯」「先修邏輯」）：切到最後一個這種字之後；一個名字是另一個的尾段也算同一層，留短的
        name = _LAYER_LEAD_RE.sub("", name) or name
        same = next((i for i, k in enumerate(layers) if k.endswith(name) or name.endswith(k)), None)
        if same is None:
            layers.append(name)
        elif len(name) < len(layers[same]):
            layers[same] = name
    return list(range(1, len(layers) + 1)) if len(layers) >= 2 else []


def root_candidates(root_line: str) -> List[int]:
    """根因層那行辨識出的候選編號（去重保序）；標記後面緊接「不存在／沒有」的是「第二個不存在」說明，不算候選。
    一個標記都沒有時看列舉與跨層（_unlabeled_candidates）。"""
    text = str(root_line or "")
    out: List[int] = []
    marked = False
    for m in _CANDIDATE_RE.finditer(text):
        marked = True
        if _absent_after(text, m.end()):
            continue
        n = _LABEL_NO[m.group(1) or m.group(2)]
        if n not in out:
            out.append(n)
    return out if marked else _unlabeled_candidates(text)


_CHAINED_NODES_RE = lazy_re(r"^(?:\s*[/／、,，+＋]\s*T\d+(?:\.\d+)*)+")
def goal_role(goal_line: str, node_id: str) -> str:
    """第四行節點編號後面括號（全形或半形）裡的角色；編號後面先接著別的節點編號（T1.1/T1.4、T1.2、T1.3）就跳過去再找括號。
    沒有括號回空字串（角色要寫在括號裡）。"""
    v = str(goal_line or "")
    i = v.find(node_id) if node_id else -1
    rest = _CHAINED_NODES_RE.sub("", v[i + len(node_id):] if i >= 0 else v, count=1)
    m = re.match(r"\s*[（(](.*?)[）)]", rest)
    return m.group(1).strip() if m else ""


def _role_core(text: str) -> str:
    return _ROLE_STRIP_RE.sub("", str(text or ""))


# 選擇動詞：「選 A／選候選 A／採用／採取／採納」；「候選」裡的選、候選描述裡的「採集」不算
_CHOICE_VERB_RE = lazy_re(r"(?<!候)選|採(?:用|取|納)")


def _has_choice_reason(root_line: str) -> bool:
    """CHOICE_REASON_BELONGS_TO_CHOICE：只以「；;。」切句（逗號不切，候選描述被逗號拆開後的「因為…」仍屬那個候選）。
    理由詞符合任一條才算選擇理由：同一句裡它前面有選擇動詞；或同一句裡它前面沒有候選標記、且位置在整行第一個候選標記之後
    （沒有固定標記從 0 起算；「候選 A 的原因是 …」是候選描述，第一個候選前面的「所以…」是前言）。"""
    text = str(root_line or "")
    first = _CANDIDATE_RE.search(text)
    floor = first.start() if first else 0
    for r in _REASON_RE.finditer(text):
        before = re.split(r"[；;。]", text[:r.start()])[-1]     # 同一句裡理由詞前面那段
        if _CHOICE_VERB_RE.search(before):
            return True
        if r.start() >= floor and not _CANDIDATE_RE.search(before):
            return True
    return False


def _second_absent(root_line: str, cands: List[int]) -> bool:
    """「第二個不存在因為 …」有理由，而且前面真的寫了第一個（有候選標記，或那句之前有內容）。"""
    text = str(root_line or "")
    m = _SECOND_ABSENT_RE.search(text)
    return bool(m) and (bool(cands) or len(_role_core(text[:m.start()])) >= 2)


def locate_lines_verdict(root_line: str, goal_line: str, node_id: str, node_text: str) -> Verdict:
    """LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES：定位四行的根因層（第二行）與目標（第四行）結構夠不夠；缺的項一起列。
    node_id／node_text＝第四行指到、已核對存在的節點與它的文字。"""
    rule = "LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES"
    missing: List[str] = []
    role, node_core = _role_core(goal_role(goal_line, node_id)), _role_core(node_text)
    if role in _ROLE_PLACEHOLDERS:
        missing.append(f"第四行 {node_id} 後面括號裡沒寫這一塊在目標裡的角色（{node_id}（這一塊替 {node_id} 做什麼））")
    elif node_core and (role == node_core or (role in node_core and len(role) * 5 >= len(node_core) * 4)):
        missing.append(f"第四行的角色是 {node_id} 節點原文照抄，要寫這一塊替 {node_id} 做什麼")
    cand = _candidates_missing(root_line)
    if cand:
        missing.append(cand)
    if not missing:
        return Verdict(rule, False, "定位四行有角色、有兩個候選或第二個不存在的理由")
    return Verdict(rule, True, "；".join(missing), (f"定位｜根因層：{root_line}", f"定位｜目標：{goal_line}"))


def _candidates_missing(root_line: str) -> str:
    cands = root_candidates(root_line)
    if len(cands) >= 2:
        return "" if _has_choice_reason(root_line) else f"根因層辨識出 {len(cands)} 個候選，但沒寫選擇理由（「選 A 因為 …」）"
    if _second_absent(root_line, cands):
        return ""
    return (f"根因層只辨識出 {len(cands)} 個候選，也沒寫「第二個不存在因為 …」"
            "（寫法：候選 A …；候選 B …；選 A 因為 …）")


def locate_candidates_verdict(root_line: str) -> Verdict:
    """LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES 的根因層那半：至少兩個候選加選擇理由，或寫「第二個不存在因為 …」。
    第四行的角色那半只記錄（呼叫端另用 locate_lines_verdict 留帳）。"""
    rule = "LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES"
    miss = _candidates_missing(root_line)
    if not miss:
        return Verdict(rule, False, "根因層有兩個候選與選擇理由，或第二個不存在的理由")
    return Verdict(rule, True, miss, (f"定位｜根因層：{root_line}",))


# 「無／沒有」後面接標點、理由詞或行尾才算「沒有」（「無鎖佇列」是位置的名字）
_SAME_NONE_RE = lazy_re(rf"^(?:無|沒有|不存在|找不到)(?=\s*(?:[，,。；;:：]|{_REASON_WORDS}|$))", re.IGNORECASE)
CRITIQUE_MIN_CHARS = 8   # 批判行去掉標點空白後至少幾個字才算有內容（「合理」「無」這種不算批判）


def locate_critique_verdict(line: str) -> Verdict:
    """LOCATE_LINES_NEED_CRITIQUE：定位第五行「定位｜批判」只查有沒有寫、有沒有內容（≥ CRITIQUE_MIN_CHARS 字）。
    合不合理、更好的做法、同類在哪都是 AI 的判斷，不認固定字樣（原設計者 G6：需要判斷的事不寫成固定規則）。"""
    rule = "LOCATE_LINES_NEED_CRITIQUE"
    text = str(line or "").strip()
    if not text:
        return Verdict(rule, True, "沒交第五行「定位｜批判：…」（這段寫法合不合理：合理寫原因、不合理寫哪裡與更好的做法；同類還可能在哪）")
    if len(_role_core(text)) < CRITIQUE_MIN_CHARS:
        return Verdict(rule, True, f"第五行「定位｜批判」太短（去掉標點不到 {CRITIQUE_MIN_CHARS} 字），寫出你對這段寫法的判斷與原因",
                       (f"定位｜批判：{text}",))
    return Verdict(rule, False, "批判那行有內容")


# 擋訊息範例的佔位：角括號裡有中文說明（`<第一個根因>`）；程式的泛型角括號（List<int>）不算
_EXAMPLE_PLACEHOLDER_RE = lazy_re(r"<[^<>\n]*[一-鿿][^<>\n]*>")


def locate_placeholder_verdict(vals: Dict[str, str]) -> Verdict:
    """LOCATE_LINES_NO_EXAMPLE_PLACEHOLDER：定位各行（部位／根因／前例／目標／批判）還留著擋訊息範例的角括號佔位 → 當沒填。"""
    rule = "LOCATE_LINES_NO_EXAMPLE_PLACEHOLDER"
    left = [f"定位｜{k}：{v}" for k, v in (vals or {}).items() if _EXAMPLE_PLACEHOLDER_RE.search(str(v or ""))]
    if not left:
        return Verdict(rule, False, "定位各行沒有留著範例佔位")
    return Verdict(rule, True, "定位行還留著範例的角括號佔位（<…>），換成你對這一塊的判斷才算交", tuple(left))


def edited_part_goal_verdict(parts: Sequence[Tuple[str, Sequence[str], str]]) -> Verdict:
    """EDITED_PART_NEEDS_GOAL_NODE：parts＝[(部位, 改的檔, 掛的狀態)]，狀態 linked／none（沒交過定位第四行）／
    dropped:<節點>（掛的節點已放棄）／gone:<節點>（節點不在目前的樹）。沒掛的一部位一行證據。"""
    rule = "EDITED_PART_NEEDS_GOAL_NODE"
    why_of = {"none": "沒交過定位第四行", "dropped": "掛的 {} 已放棄", "gone": "掛的 {} 不在目前的樹"}
    rows: List[str] = []
    for part, files, link in parts:
        if link == "linked":
            continue
        kind, _, node = str(link).partition(":")
        rows.append(f"{part}：{'、'.join(files)} 沒掛目標（{why_of.get(kind, kind).format(node)}）")
    if not rows:
        return Verdict(rule, False, "改到的寫碼部位都掛到目標節點")
    return Verdict(rule, True, f"{len(rows)} 個改到的寫碼部位沒掛到目前目標樹裡活著的節點", tuple(rows))




# ─── 提問（AskUserQuestion／ExitPlanMode 前）：附推薦、掛目標、全貌先於拍板（wg_need_goal_points 收事實、這裡判） ───

RULES.update({
    "ASK_NEEDS_RECOMMENDATION": "AskUserQuestion 每一題至少一個選項 label 標 (Recommended)，或題目文字含「建議：」一句；"
                                "【收尾放行確認】固定兩選項（放行這一回合／繼續擋，先修好）的放行題不是決策題、豁免；含標記但選項走樣"
                                "（多了、少了、加了 (Recommended)）照擋並指路照抄兩個選項；工具輸入判不了不擋。"
                                "沒有就擋（不分有沒有樹、哪一類），擋訊息列缺的題目與照抄可過的寫法。",
    "ASK_LINKED_TO_GOAL": "有目標樹時每一題（題目＋選項 label 與描述，不含 header；ExitPlanMode 是整份計畫）各自要指到節點："
                          "節點編號（T<n>／T<n>.<m>，在目前的樹、沒放棄）或節點原文連續 8 字以上的片段（空白不算字；不到 8 字的節點"
                          "只能寫編號）；一題掛上不帶過同批其他題。有題沒指到只記錄不擋（guard-need_goal ask_unlinked），"
                          "不分寫碼類或記憶知識類；沒有樹不記。真有待放行紀錄時放行題不算；整次全是放行題才整次豁免（ask_release_only）。",
    "ASK_OVERVIEW_BEFORE_DECISION": "提問涉及改法選擇（ExitPlanMode，或題目含改法／做法／方案／寫法／實作／架構／重構／設計）時："
                                    "題目與選項 label／描述提到的路徑對得上部位表 → 只看那些部位，有部位的 part_files_read 是 0 檔就提醒"
                                    "（讀了別的部位不算），證據行「題目提到 <路徑>→部位 <名>，本回合該部位讀過 0 檔」；題目沒提路徑或提的"
                                    "路徑不在部位表 → 退回看 part_files_read 是不是全空。提醒＝擋訊息或提示多一句「先讀過部位檔再問」；"
                                    "只提醒，不單獨擋（owed＝要附這句）。",
})

ASK_FRAGMENT_MIN = 8
_REC_LABEL_RE = lazy_re(r"[(（]\s*recommended\s*[)）]", re.IGNORECASE)
_REC_TEXT_RE = lazy_re(r"建議\s*[:：]")
_DECISION_RE = lazy_re(r"改法|做法|方案|寫法|怎麼改|如何改|實作|架構|重構|設計|approach|implement|refactor|design", re.IGNORECASE)


def _ask_questions(tool_input: Any) -> List[Tuple[str, List[str], List[str]]]:
    """AskUserQuestion 的工具輸入 → [(題目, [選項 label…], [選項 label 與描述的字串…])]；不含 header；格式不對的題目略過。"""
    qs = tool_input.get("questions") if isinstance(tool_input, dict) else None
    out: List[Tuple[str, List[str], List[str]]] = []
    for q in qs if isinstance(qs, list) else []:
        if not isinstance(q, dict):
            continue
        opts = q.get("options") if isinstance(q.get("options"), list) else []
        labels = [str(o.get("label") or "") if isinstance(o, dict) else str(o) for o in opts]
        texts = [f"{o.get('label') or ''}\n{o.get('description') or ''}" if isinstance(o, dict) else str(o) for o in opts]
        out.append((str(q.get("question") or ""), labels, texts))
    return out


def _is_release_q(text: str, labels: Sequence[str], release_tag: str, release_labels: Iterable[str]) -> bool:
    """放行題看結構：題目含標記、選項正好是固定兩個（光有標記不算）。"""
    return release_tag in text and set(labels) == set(release_labels)


def ask_release_only(tool_input: Any, release_tag: str, release_labels: Iterable[str]) -> bool:
    """整次提問全是放行題：真有待放行紀錄時整次豁免（夾了一般題、標記塞進一般題都不算）。"""
    fixed = tuple(release_labels)
    qs = _ask_questions(tool_input)
    return bool(qs) and all(_is_release_q(t, ls, release_tag, fixed) for t, ls, _x in qs)


def ask_link_units(tool_input: Any, skip_release: bool, release_tag: str, release_labels: Iterable[str]
                   ) -> List[Tuple[str, str]]:
    """ASK_LINKED_TO_GOAL 要各自掛節點的單位：每一題一個（標籤「第 i 題「題目」」, 題目＋選項 label 與描述），不含 header；
    skip_release（真有待放行紀錄）時放行題不算單位。題目判不了回 []（呼叫端改用整份文字一個單位）。"""
    fixed = tuple(release_labels)
    return [(f"第 {i} 題「{t[:40]}」", "\n".join([t, *texts]))
            for i, (t, ls, texts) in enumerate(_ask_questions(tool_input), 1)
            if not (skip_release and _is_release_q(t, ls, release_tag, fixed))]


def _unrecommended(tool_input: Any, release_tag: str, release_labels: Iterable[str]) -> List[Tuple[int, str, List[str]]]:
    """沒附推薦的題目：(第幾題, 題目, 選項 label)。放行題（題目含標記、選項正好是固定兩個）不算；
    含標記但選項走樣的照列（加了 (Recommended) 也列：它已不是放行題，使用者選了也不會被認成放行）。"""
    fixed = tuple(release_labels)
    out = []
    for i, (text, labels, _x) in enumerate(_ask_questions(tool_input), 1):
        if _is_release_q(text, labels, release_tag, fixed):
            continue
        if release_tag not in text and (_REC_TEXT_RE.search(text) or any(_REC_LABEL_RE.search(l) for l in labels)):
            continue
        out.append((i, text, labels))
    return out


def ask_recommendation_verdict(tool_input: Any, release_tag: str, release_labels: Iterable[str]) -> Verdict:
    """ASK_NEEDS_RECOMMENDATION：每一題都要有推薦（選項 label 標 (Recommended) 或題目含「建議：」）。"""
    rule = "ASK_NEEDS_RECOMMENDATION"
    release_labels = tuple(release_labels)
    if not _ask_questions(tool_input):
        return Verdict(rule, False, "工具輸入沒有可判的題目（交給工具自己驗）")
    miss = _unrecommended(tool_input, release_tag, release_labels)
    if not miss:
        return Verdict(rule, False, "每一題都附了推薦")
    fixed = "／".join(release_labels)

    def line(i: int, t: str, ls: List[str]) -> str:
        head = f"第 {i} 題「{t[:40]}」："
        if release_tag in t:
            return (head + f"含{release_tag}但選項不是固定兩個（{fixed}）：放行題照抄這兩個選項、不加 (Recommended)；"
                    "不是放行題就拿掉標記並附推薦")
        return head + f"選項 {'／'.join(l or '（空）' for l in ls) or '（無）'} 都沒標 (Recommended)、題目也沒有「建議：」"
    return Verdict(rule, True, f"{len(miss)} 題沒附推薦：人要看得到你建議哪個、為什麼", tuple(line(*m) for m in miss))


def ask_recommendation_fix(tool_input: Any, release_tag: str, release_labels: Iterable[str]) -> str:
    """照抄可過的寫法：拿第一個沒推薦的題目示範兩種補法。"""
    miss = _unrecommended(tool_input, release_tag, release_labels)
    label = next((l for l in (miss[0][2] if miss else []) if l), "A")
    return (f"照抄可過：把你推薦的選項排第一、label 後面加「 (Recommended)」，例如 "
            f'{{"label": "{label} (Recommended)", "description": "<一句理由>"}}；'
            f"或在題目文字加一句「建議：選 {label}，因為 <一句理由>。」每一題都要。")


def node_fragment_ref(node_texts: Dict[str, str], text: str, min_len: int = ASK_FRAGMENT_MIN) -> Optional[str]:
    """文字裡出現某節點原文連續 min_len 字以上（空白不算字）→ 回那個節點編號，多個命中取 node_texts 裡先出現的；
    節點原文不到 min_len 字的不比（只能寫編號）。node_texts＝{節點編號: 原文}，呼叫端只放沒放棄的節點。"""
    hay = re.sub(r"\s+", "", str(text or ""))
    for nid, raw in node_texts.items():
        t = re.sub(r"\s+", "", str(raw or ""))
        if len(t) >= min_len and any(t[i:i + min_len] in hay for i in range(len(t) - min_len + 1)):
            return nid
    return None


def ask_goal_link_verdict(kind: Optional[str], links: Sequence[Tuple[str, Optional[str]]]) -> Verdict:
    """ASK_LINKED_TO_GOAL：kind＝目前樹的類別（code／knowledge，沒有樹 None）；links＝每個單位（ask_link_units 的每一題，
    或整份計畫）的 (標籤, 指到的節點或 None)。每個單位都指到節點才算掛上；一題掛上不帶過同批其他題。"""
    rule = "ASK_LINKED_TO_GOAL"
    miss = [lab for lab, nid in links if not nid]
    if links and not miss:
        nodes = tuple(dict.fromkeys(nid for _l, nid in links if nid))
        return Verdict(rule, False, f"題目掛在 {'、'.join(nodes)}", nodes)
    tail = f"沒有節點編號（T<n>／T<n>.<m>），也沒有節點原文連續 {ASK_FRAGMENT_MIN} 字"
    ev = tuple(f"{lab}：題目與選項描述{tail}" for lab in miss) or (f"題目與選項描述{tail}",)
    if kind is None:
        return Verdict(rule, False, "還沒有目標樹：不擋，審計記「提問未掛目標（知識類）」", ev)
    if kind != "code":
        return Verdict(rule, False, "記憶知識類的樹：題目沒指到節點，只提醒", ev)
    return Verdict(rule, True, "寫碼類的樹：有題目沒指到任何節點", ev)


def ask_audit_note(kind: Optional[str], linked: Optional[str]) -> Optional[str]:
    """提問審計的備註：沒掛上節點 → 「提問未掛目標（寫碼類｜知識類）」（沒有樹算知識類）；掛上了 None。"""
    if linked:
        return None
    return f"提問未掛目標（{'寫碼類' if kind == 'code' else '知識類'}）"


# ─── 記憶知識類的輕樹（(f4)；wg_need_goal.knowledge_gate_reason 收事實、這裡判）────────────────────────

RULES.update({
    "KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE": "本使用者回合在還沒有任何需求目標樹時改了記憶知識類的檔（不是程式檔、不是暫存檔；寫入當下只記 untreed 與"
                                       "守門紀錄 knowledge_no_tree，不送「寫一棵輕樹」的催促）→ 回合結束要補一棵輕樹（一個節點即可，之前改的檔寫樹時自動掛進去）。不看措辭；"
                                       "屬記憶與報告類：併進收尾報告那一份擋，本回合第 3 次放行並記 reconcile_overflow，不問使用者。",
    "KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY": "交付邊界（宣告完成、本回合交了收尾檢核、擋滿待查的原宣稱）時，目前的樹是記憶知識類，而且最後一次"
                                            "對得上目標版本的完整對照之後還有改檔（沒對照過＝全部改檔）→ 要交 need_goal reconcile；達成不要求"
                                            "案例或收據，推論最多標部分。樹上沒有改檔（純問答）不要求；寫碼類樹歸 (f2)。同屬記憶與報告類。",
})


def knowledge_light_tree_verdict(untreed: Sequence[str]) -> Verdict:
    """KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE：untreed＝本使用者回合、還沒有目標樹時改的記憶知識類檔（寫樹時會清空並掛進樹）。"""
    rule = "KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE"
    if not untreed:
        return Verdict(rule, False, "本回合沒有在沒樹時改記憶知識類的檔")
    return Verdict(rule, True, f"本回合改了 {len(untreed)} 個記憶知識類的檔，但還沒有需求目標樹", tuple(untreed[:5]))


def knowledge_reconcile_verdict(kind: Optional[str], edited: Sequence[str], tree_id: str = "") -> Verdict:
    """KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY：kind＝這棵樹的類別（沒有樹 None）；edited＝最後一次對得上目標版本的完整對照之後
    改過的檔（沒對照過或對照已作廢＝這棵樹全部改檔）；tree_id 只用來寫進訊息。只在交付邊界問。"""
    rule = "KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY"
    name = f"記憶知識類的樹{(' ' + tree_id) if tree_id else ''}"
    if kind != "knowledge":
        return Verdict(rule, False, "這棵樹是寫碼類，交付前的完整對照歸 (f2)" if kind else "沒有目標樹")
    if not edited:
        return Verdict(rule, False, f"{name}在最後一次完整對照之後沒有改檔")
    return Verdict(rule, True, f"{name}在最後一次完整對照之後改了 {len(edited)} 個檔，還沒交收尾對照", tuple(edited[:5]))


_CJK ="㐀-鿿豈-﫿"
_SEG = rf"[A-Za-z0-9_.\-{_CJK}]+"                                     # 中間段：可含中文
_SEG_ASCII = r"[A-Za-z0-9_.\-]+"
_LAST = rf"(?:[A-Za-z0-9_.\-{_CJK}]*?\.[A-Za-z][A-Za-z0-9]{{0,5}}(?![A-Za-z0-9_])|{_SEG_ASCII})"   # 最後一段：含中文要有副檔名
_URL_RE = lazy_re(r"[A-Za-z][A-Za-z0-9+.\-]*://\S+")
_QUOTED_RE = lazy_re(r"`([^`\n]+)`|「([^」\n]+)」|\"([^\"\n]+)\"|'([^'\n]+)'")
_ASK_ABS_PATH_RE = lazy_re(rf"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])(?:{_SEG}[\\/])*{_LAST}?")
_ASK_REL_PATH_RE = lazy_re(rf"(?<![A-Za-z0-9_.\-\\/:])(?:\.{{1,2}}[\\/])?{_SEG_ASCII}(?:[\\/](?:{_SEG}(?=[\\/])|{_LAST}))+[\\/]?")
_ASK_BARE_FILE_RE = lazy_re(
    r"(?<![A-Za-z0-9_.\-\\/:])[A-Za-z0-9_\-]*[A-Za-z][A-Za-z0-9_\-]*\.[A-Za-z][A-Za-z0-9]{0,5}(?![A-Za-z0-9_.\\/])")
_NOT_PATH_SEG_RE = lazy_re(r"T\d+(?:\.\d+)*|[\d.\-]*|.")          # 節點編號、純數字（日期、版本號）、單一字元（A/B）


def _looks_like_path(p: str) -> bool:
    """相對寫法每一段都是節點編號、純數字或單一字元 → 不是路徑（T1.1/T1.2、2026/10/14、1.2/3.4、A/B）。"""
    segs = [s for s in re.split(r"[\\/]", p) if s not in ("", ".", "..")]
    return bool(segs) and not all(_NOT_PATH_SEG_RE.fullmatch(s) for s in segs)


def ask_paths(tool_input: Any) -> List[str]:
    """題目與選項 label／描述（不含 header）裡像路徑的字，依出現順序去重：引號（`、「」、"、'）包住而含斜線或像檔名的整段照原樣
    （可含空白與中文）；絕對路徑（磁碟代號開頭）；含斜線的相對路徑（第一段英數，之後的段可含中文，最後一段含中文要帶副檔名）；
    不含斜線的檔名（TECH.md）。網址整段先拿掉；相對寫法每段都是節點編號、純數字或單一字元的不算。"""
    out: List[str] = []

    def add(p: str) -> None:
        if p and p not in out and (re.match(r"[A-Za-z]:[\\/]", p) or _looks_like_path(p)):
            out.append(p)

    for t, _l, texts in _ask_questions(tool_input):
        for s in [t, *texts]:
            s = _URL_RE.sub(" ", s)
            for m in _QUOTED_RE.finditer(s):
                q = next(g for g in m.groups() if g is not None).strip()
                if re.search(r"[\\/]", q) or _ASK_BARE_FILE_RE.fullmatch(q):
                    add(q)
            s = _QUOTED_RE.sub(" ", s)
            for rx in (_ASK_ABS_PATH_RE, _ASK_REL_PATH_RE, _ASK_BARE_FILE_RE):
                for m in rx.finditer(s):
                    add(m.group(0).rstrip("."))
                s = rx.sub(" ", s)
    return out


_ASK_OVERVIEW_HOW = "（這條不單獨擋；但這題被別條擋下要重組時，先讀題目提到、還沒讀的部位檔，讀完再定推薦，或判斷根本不必問）"


def ask_overview_verdict(tool_name: str, tool_input: Any, part_files_read: int,
                         named: Sequence[Tuple[str, str, int]] = ()) -> Verdict:
    """ASK_OVERVIEW_BEFORE_DECISION：只看題目文字（不看 header、選項）判改法選擇；ExitPlanMode 一律算。
    named＝題目提到、對得上部位表的路徑：(題目裡的寫法, 部位名, 該部位 part_files_read 檔數)，每個部位一筆；有就只看這些部位，
    有部位讀過 0 檔就提醒（讀了別的部位不算）。沒有 named → 退回看 part_files_read（OverviewHub 各部位總數）是不是全空。
    owed＝要附提醒句，呼叫端不因這條單獨擋。"""
    rule = "ASK_OVERVIEW_BEFORE_DECISION"
    decision = tool_name == "ExitPlanMode" or any(_DECISION_RE.search(t) for t, _l, _x in _ask_questions(tool_input))
    if not decision:
        return Verdict(rule, False, "題目不涉及改法選擇")
    if named:
        unread = [(p, part) for p, part, n in named if not n]
        if not unread:
            return Verdict(rule, False, "題目提到的部位都讀過檔",
                           tuple(f"題目提到 {p}→部位 {part}，本回合該部位讀過 {n} 檔" for p, part, n in named))
        return Verdict(rule, True, f"題目涉及改法選擇，但題目提到的部位還沒讀過檔：先讀過部位檔再問{_ASK_OVERVIEW_HOW}",
                       tuple(f"題目提到 {p}→部位 {part}，本回合該部位讀過 0 檔" for p, part in unread))
    if part_files_read > 0:
        return Verdict(rule, False, f"題目沒提到部位表上的路徑；已讀過 {part_files_read} 個部位檔")
    return Verdict(rule, True, f"題目涉及改法選擇，但本 session 還沒讀過任何部位檔：先讀過部位檔再問{_ASK_OVERVIEW_HOW}",
                   ("題目沒提到部位表上的路徑；OverviewHub 的 part_files_read 全空",))


# ─── 驗證範圍：要不要驗是規則，驗哪些由 LLM 判斷（wg_verify_scope 收事實、這裡判） ───
RULES.update({
    "SCOPE_DECLARED_FOR_CHANGE": "改了程式檔、或改到部位表上有量尺的部位（不看措辭、每次收尾都判）→ 要有 need_goal(action=verify_scope) 的宣告，"
                                 "而且每個有改動的 repo 至少一項落在裡面。宣告是 LLM 對「哪些有關聯、會受影響」的判斷，程式不替它列；"
                                 "部位表的整把量尺只在宣告回應與擋訊息當參考。子代理沒有自己的宣告時沿用主 session 的。",
    "SCOPE_ITEM_WELL_FORMED": "宣告收件：每項的目標與理由都不能空；看起來是路徑的目標要存在，測試節點（檔::名）要查得到那個 def；"
                              "不是路徑的目標當指令。有一項不合格整份退回。",
    "SCOPE_CASE_EDIT_ONLY_ITS_ITEM": "測試案例檔是量具不是受測物：改了它（符合 verify_case_globs 的程式檔、不是 conftest／__init__、同資料夾"
                                     "沒有別的程式 import 它）只作廢點名它（就在這一項點名的路徑底下）、它所在部位的量尺指令、整體驗證或看不出"
                                     "跑了什麼的項目，範圍裡其他測試不必重跑。被同資料夾別的程式 import 的案例檔（共用的 Sandbox、fixture）"
                                     "與 conftest 照程式檔算。判法在 wg_verify_scope._standalone_case。",
    "SCOPE_EDIT_RELATED_TO_ITEM": "宣告的一項要晚於哪些改檔的最後一次修改：程式檔一律算（測試案例檔例外，見 SCOPE_CASE_EDIT_ONLY_ITS_ITEM）；"
                                  "不是程式檔的（文件、記憶，落在有量尺的部位才要宣告）"
                                  "只有跟這一項有關才算：和這一項點名的檔同一個部位、就在它點名的路徑或它宣告的 inputs（這一項還讀的檔或"
                                  "資料夾，跨部位的資料由 LLM 宣告）底下、這一項就是那個部位的量尺指令，或這一項是整體驗證／看不出跑了什麼（照算）。"
                                  "這四個條件都是查得到的事實（部位表同一列、路徑包含、量尺逐字相同、指令涵蓋），不是替 LLM 判斷關聯；"
                                  "「測試讀了哪份資料」是判斷，只認 LLM 在項目宣告的 inputs，沒有別的對應表、不看檔名規則。"
                                  "改 _staging 的計畫文件不作廢程式測試的收據；宣告回應列出不算進任何一項的文件改動，讓 LLM 判斷要不要加 inputs。",
    "SCOPE_EDIT_IN_DECLARED_DEPENDS": "項目宣告了 depends（這一項用到的程式檔或資料夾，LLM 判斷）→ 程式檔改動只作廢依賴裡的、它點名的路徑底下的、"
                                      "它 case_for 列的，以及共用的測試設施（conftest／__init__／被同資料夾 import 的案例檔）；"
                                      "依賴以外的程式改動不作廢它。沒宣告 depends 的項目照 SCOPE_EDIT_RELATED_TO_ITEM（程式檔一律算）。"
                                      "宣告漏列就漏驗：之後那支測試紅了由 SCOPE_LEAK_OUTSIDE_SCOPE 記下。",
    "SCOPE_RED_ONLY_ITS_CASES": "一條指令跑了好幾項、其中有紅：收據記下紅掉的案例（FAILED／ERROR 那幾行），紅案數和 pytest 結尾的 "
                                "「N failed、M error」對得上（清單完整）時，檔案／資料夾／測試節點項目只看紅案有沒有落在它底下，沒有就照算綠；"
                                "清單不完整（輸出被截、不是 pytest）、指令項目、exit 不是 0／1 → 整條照算紅。背景自寫收據的 failed_cases 同一個判法。",
    "SCOPE_ITEM_RECEIPT_AFTER_EDIT": "最新那份宣告的每一項都要有一筆收據：晚於跟這一項有關的改檔（SCOPE_EDIT_RELATED_TO_ITEM）最後一次修改、綠（有 PASS／DONE、沒有 FAIL、"
                                     "exit 0 或未知、failed=0）、同一棵樹、指令完整可信（解析得了、沒有換目錄、環境沒縮範圍；"
                                     "不看前後接了什麼、用什麼串）。"
                                     "檔案／資料夾項目：pytest 點名該檔或它所在的資料夾、直接執行的腳本就是它、或整體驗證；pytest 選項走白名單"
                                     "（-k、-m、-o、--deselect、連寫的 -kfoo 等其他選項一律當只跑一部分，那一段點名的都不算），python 直譯器"
                                     "只准 -X utf8、-u、-B；別的程式（compileall 等）的參數不算跑過。測試節點項目：點名那個節點，或照檔案項目的"
                                     "條件跑了它的檔；指令項目：照宣告的原字串、在宣告時的目錄跑（cmd_matches）。",
    "SCOPE_LEAK_OUTSIDE_SCOPE": "測試 T 紅了 → 在 T 上次綠之後、這次紅之前結案、範圍沒涵蓋 T 的宣告，各記一筆疑似範圍漏判（連回那次宣告）。"
                                "T 從沒綠過、T 在範圍內 → 不記。看到紅的 session（或子代理）在這個 repo 還有沒結案的改動 → 照記但標出來，"
                                "檢討時先查明是不是它自己這次改動造成的（不憑 session 狀態丟掉，免得漏掉別人留下的退化）。"
                                "例外：T 這個案例是它在 T 上次綠之後新寫或改過、還沒結案的（上次綠那時的 git 版本沒有它、或定義不同；"
                                "先紅後綠的新案例、改了案例）→ 是它進行中的工作，不記，告訴它（紅照樣進紅測清單）。只改同檔別的案例、"
                                "判不出（查不了 git、解析不了）照記。只記錄，不擋。",
    "SCOPE_LEAK_REVIEW_BEFORE_DECLARE": "該 repo 有還沒檢討的範圍漏判 → 新的宣告要逐筆附檢討才收：missed（該驗的沒驗到）要寫沒驗到的根因"
                                        "（root_cause）與下次判斷範圍時怎麼改（next_time）；unrelated（與那次改動無關）要寫查明的理由（reason）。"
                                        "哪一種、根因是什麼由 LLM 判斷，程式只要求交出來。",
})


def _rel_key(p: Any) -> str:
    """repo 相對路徑的比對鍵：斜線統一、去頭尾斜線與 ./、小寫（節點 id 的 :: 原樣保留）。"""
    s = str(p or "").replace("\\", "/").strip().strip("/")
    while s.startswith("./"):
        s = s[2:]
    return s.lower()


def scope_covers(covers: Iterable[str], test: str) -> bool:
    """範圍（repo 相對路徑；`*`＝整個 repo；節點寫 `檔::名`）有沒有涵蓋測試 test（檔或節點）。資料夾涵蓋底下所有檔；
    節點項目只涵蓋它自己（含它的參數化與子節點）。"""
    tf, _, tn = _rel_key(test).partition("::")
    for c in covers or ():
        if c == "*":
            return True
        cf, _, cn = _rel_key(c).partition("::")
        if cn:
            if cf == tf and tn and (tn == cn or tn.startswith(cn + "::") or tn.startswith(cn + "[")):
                return True
        elif cf and (tf == cf or tf.startswith(cf + "/")):
            return True
    return False


def scope_failed_in(failed: Iterable[str], test: str) -> bool:
    """一輪測試的紅名單 failed 裡有沒有 test：同一個節點，或同一支檔而其中一邊只寫到檔。"""
    tf, _, tn = _rel_key(test).partition("::")
    for f in failed or ():
        ff, _, fn = _rel_key(f).partition("::")
        if ff == tf and (not tn or not fn or tn == fn):
            return True
    return False


def _base(p: Any) -> str:
    return os.path.basename(str(p).replace("\\", "/"))


def scope_declared_verdict(changed: Sequence[str], declared: bool,
                           repos_without_item: Sequence[Tuple[str, Sequence[str]]] = ()) -> Verdict:
    """SCOPE_DECLARED_FOR_CHANGE：changed＝要宣告的改檔；declared＝有宣告；repos_without_item＝(repo, 那裡的改檔) 宣告裡沒有項目落在那。"""
    rule = "SCOPE_DECLARED_FOR_CHANGE"
    names = [_base(p) for p in changed]
    if not changed:
        return Verdict(rule, False, "沒有要宣告驗證範圍的改動")
    if not declared:
        return Verdict(rule, True, f"改了 {'、'.join(names[:5])}{'…' if len(names) > 5 else ''}，但還沒宣告驗證範圍",
                       ("該測哪些由你判斷：看這次改了什麼、哪些測試有關聯、哪些地方會受影響，"
                        "用 need_goal(action=\"verify_scope\", items=[{target, why}…]) 宣告",))
    if repos_without_item:
        return Verdict(rule, True, "宣告裡沒有落在這些 repo 的項目：" + "、".join(r for r, _ in repos_without_item),
                       tuple(f"{r} 改了 {'、'.join(_base(p) for p in fs[:4])}" for r, fs in repos_without_item))
    return Verdict(rule, False, "每個有改動的 repo 都有宣告項目")


def scope_item_form_verdict(target: str, why: str, problem: str = "") -> Verdict:
    """SCOPE_ITEM_WELL_FORMED：problem＝呼叫端查到的事實問題（檔不存在、節點查不到 def）；空＝目標存在或是指令。"""
    rule = "SCOPE_ITEM_WELL_FORMED"
    if not str(target or "").strip():
        return Verdict(rule, True, "有一項沒寫目標（target）")
    if not str(why or "").strip():
        return Verdict(rule, True, f"「{target}」沒寫理由（why：為什麼和這次改動有關、會受什麼影響）")
    if problem:
        return Verdict(rule, True, f"「{target}」{problem}")
    return Verdict(rule, False, f"「{target}」收下")


def scope_edit_related_verdict(name: str, is_code: bool, same_part: bool = False, under_item: bool = False,
                               runs_part_ruler: bool = False, whole_or_unknown: bool = False,
                               standalone_case: bool = False, declares_deps: bool = False, in_deps: bool = False,
                               shared_case: bool = False) -> Verdict:
    """SCOPE_EDIT_RELATED_TO_ITEM：owed＝這個改檔（name）算進這一項的「最後一次改動」（收據要晚於它）。事實由 wg_verify_scope._item_mods 查。
    standalone_case＝它是測試案例檔、不是 conftest／__init__、同資料夾沒有別的程式 import 它：只作廢點名它的項目（規則 SCOPE_CASE_EDIT_ONLY_ITS_ITEM）。
    declares_deps＝這一項宣告了 depends；in_deps＝改檔在依賴裡或它的 case_for 列了它；shared_case＝改檔是共用的測試設施
    （conftest／__init__／被 import 的案例檔）：宣告了 depends 的項目，程式改動只算這三種與它點名的路徑底下（規則 SCOPE_EDIT_IN_DECLARED_DEPENDS）。"""
    rule = "SCOPE_EDIT_RELATED_TO_ITEM"
    if is_code and standalone_case:
        rule = "SCOPE_CASE_EDIT_ONLY_ITS_ITEM"
        why = ("就在這一項點名的路徑底下" if under_item else "這一項就是它所在部位的量尺指令" if runs_part_ruler
               else "這一項是整體驗證或看不出跑了什麼" if whole_or_unknown
               else "在這一項宣告的依賴裡" if in_deps else "")   # 檔名像案例（wg_old_test.py）的模組，宣告了依賴就要算
        if why:
            return Verdict(rule, True, f"{name} 是測試案例檔，{why}")
        return Verdict(rule, False, f"{name} 是測試案例檔、沒有別的程式 import 它，這一項沒點名它：改它不作廢這一項的收據")
    if is_code and declares_deps:
        rule = "SCOPE_EDIT_IN_DECLARED_DEPENDS"
        why = ("在這一項宣告的依賴裡" if in_deps else "就在這一項點名的路徑底下" if under_item
               else "是共用的測試設施（conftest／__init__／被 import 的案例檔）" if shared_case else "")
        if why:
            return Verdict(rule, True, f"{name} 是程式檔，{why}")
        return Verdict(rule, False, f"{name} 是程式檔，但不在這一項宣告的依賴裡：改它不作廢這一項的收據")
    if is_code:
        return Verdict(rule, True, f"{name} 是程式檔：每一項的收據都要晚於它（這一項沒宣告 depends）")
    why = ("和這一項點名的檔同一個部位" if same_part else "就在這一項點名的路徑底下" if under_item
           else "這一項就是它所在部位的量尺指令" if runs_part_ruler else "這一項是整體驗證或看不出跑了什麼" if whole_or_unknown else "")
    if why:
        return Verdict(rule, True, f"{name} 不是程式檔，但{why}")
    return Verdict(rule, False, f"{name} 不是程式檔，也跟這一項無關：改它不作廢這一項的收據")


def scope_item_verdict(scope_id: str, target: str, ok: bool, why_not: str = "") -> Verdict:
    """SCOPE_ITEM_RECEIPT_AFTER_EDIT：一項有沒有合格收據（事實由 wg_verify_ledger.scope_item_status 查）。"""
    rule = "SCOPE_ITEM_RECEIPT_AFTER_EDIT"
    if ok:
        return Verdict(rule, False, f"{scope_id} 的「{target}」有改完之後跑綠的收據")
    return Verdict(rule, True, f"{scope_id} 的「{target}」沒有改完之後跑綠的收據", (why_not or "沒有跑這一項的收據",))


def scope_leak_verdict(test: str, scope_id: str, in_scope: bool, observer_open: bool, last_green: Optional[str],
                       closed_between: bool, observer_changed_case: bool = False) -> Verdict:
    """SCOPE_LEAK_OUTSIDE_SCOPE：owed＝要記一筆疑似漏判。closed_between＝那次宣告在 T 上次綠（last_green）之後、這次紅之前結案。
    observer_open＝看到紅的 session 自己還有沒結案的改動：照記，證據多一行叫檢討時先查明是不是它自己造成的。
    observer_changed_case＝T 這個案例是看到紅的 session 在 T 上次綠之後新寫或改過、還沒結案的（比上次綠那時的 git 版本）：
    是它進行中的工作，不記（紅照樣進紅測清單、收尾前要綠）。只改了同檔別的案例不算。"""
    rule = "SCOPE_LEAK_OUTSIDE_SCOPE"
    if in_scope:
        return Verdict(rule, False, f"{test} 在 {scope_id} 的範圍內（那是退化，不是漏判）")
    if not last_green:
        return Verdict(rule, False, f"{test} 沒有綠過的紀錄，無從歸因")
    if observer_changed_case:
        return Verdict(rule, False, f"{test} 是看到紅的 session 在它上次綠之後新寫或改過、還沒結案的案例：算它進行中的工作")
    if not closed_between:
        return Verdict(rule, False, f"{scope_id} 不是在 {test} 上次綠之後、這次紅之前結案的")
    ev = (f"{test} 上次綠：{last_green}",)
    if observer_open:
        ev += ("看到紅的 session 當時自己還有沒結案的改動：檢討時先查明是不是它自己這次改動造成的",)
    return Verdict(rule, True, f"{test} 紅了，{scope_id} 結案時的範圍沒涵蓋它", ev)


def scope_review_verdict(pending: Sequence[str], reviews: Any) -> Verdict:
    """SCOPE_LEAK_REVIEW_BEFORE_DECLARE：pending＝這次宣告涉及的 repo 裡還沒檢討的漏判編號；reviews＝宣告附的檢討。"""
    rule = "SCOPE_LEAK_REVIEW_BEFORE_DECLARE"
    by = {str(r.get("leak") or "").strip(): r for r in (reviews or []) if isinstance(r, dict)}
    probs: List[str] = []
    for lid in pending:
        r = by.get(lid)
        if not r:
            probs.append(f"{lid} 還沒檢討")
            continue
        v = str(r.get("verdict") or "")
        if v == "missed":
            if not str(r.get("root_cause") or "").strip():
                probs.append(f"{lid} 判「該驗的沒驗到」要寫沒驗到的根因（root_cause：當初判斷範圍時漏看了什麼、為什麼漏看）")
            if not str(r.get("next_time") or "").strip():
                probs.append(f"{lid} 判「該驗的沒驗到」要寫下次判斷範圍時要怎麼改（next_time）")
        elif v == "unrelated":
            if not str(r.get("reason") or "").strip():
                probs.append(f"{lid} 判「與那次改動無關」要寫查明的理由（reason）")
        else:
            probs.append(f"{lid} 的 verdict 只收 missed（該驗的沒驗到）或 unrelated（與那次改動無關）")
    if probs:
        return Verdict(rule, True, f"還有 {len(pending)} 筆範圍漏判待檢討，先逐筆檢討才收新的宣告", tuple(probs))
    return Verdict(rule, False, f"{len(pending)} 筆待檢討的漏判都交了檢討")


# ─── RELOAD_ADVICE_ALREADY_LOADED ──────────────────────────────────────────────

RELOAD_ADVICE_RE = lazy_re(r"reload\s*window|重新載入視窗|重載視窗|重新載入\s*vs\s*code", re.IGNORECASE)
RELOAD_REASON_RE = lazy_re(r"重載原因\s*[:：]\s*\S")     # AI 宣告程式更新以外的重載理由（改了啟動設定等）
RELOAD_ALIVE_S = 180.0      # 心跳在這麼久之內才算新（服務每 60 秒更新一次；過期＝睡眠後或寫不了紀錄）


def _ms_text(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000).strftime("%m-%d %H:%M:%S")


def reload_advice_verdict(text: str, records: Sequence[Tuple[Optional[float], float]], disk_mtime: Optional[float],
                          now: float, alive_s: float = RELOAD_ALIVE_S) -> Verdict:
    """RELOAD_ADVICE_ALREADY_LOADED：owed＝收尾叫使用者重載是多餘的。records＝每個正在跑的工具服務的（啟動時載入的程式版本毫秒、
    心跳秒），載入版本 None＝那個服務沒有啟動紀錄（舊版服務）；disk_mtime＝磁碟上的程式版本毫秒（讀不到 None）。
    在跑的服務都有紀錄、心跳都新、都不舊於磁碟版本才算多餘（容許 1 毫秒的浮點誤差）；判不出一律放行；
    AI 寫明「重載原因：…」（程式更新以外的理由，例如改了啟動設定）照它的判斷放行。"""
    rule = "RELOAD_ADVICE_ALREADY_LOADED"
    if not RELOAD_ADVICE_RE.search(text or ""):
        return Verdict(rule, False, "收尾文字沒有叫使用者重載")
    if RELOAD_REASON_RE.search(text or ""):
        return Verdict(rule, False, "AI 寫明了重載原因（程式更新以外的理由），照它的判斷")
    if disk_mtime is None or not records:
        return Verdict(rule, False, "判不出工具服務載入的版本（列不出在跑的服務，或讀不到磁碟版本），照放行")
    if any(m is None or now - beat > alive_s for m, beat in records):
        return Verdict(rule, False, "有正在跑的工具服務沒有啟動紀錄（舊版）或心跳過期（睡眠後、寫不了紀錄），判不出，照放行")
    if any(m + 1.0 < disk_mtime for m, _ in records):
        return Verdict(rule, False, "有工具服務還在跑舊程式，叫使用者重載是對的")
    return Verdict(rule, True, f"叫使用者 Reload Window，但正在跑的 {len(records)} 個工具服務都已載入磁碟上最新的程式",
                   (f"磁碟程式版本 {_ms_text(disk_mtime)}；服務載入版本 {'、'.join(_ms_text(m) for m, _ in records[:3])}",))


# ─── (d) 補案例：由哪個案例驗交 LLM 宣告（判斷入口盤點 P4；wg_verify_scope 收事實、這裡判） ───
RULES.update({
    "CASE_DECLARED_FOR_CHANGE": "(d) 補案例（驗證範圍閘開著時）：每個改過的程式檔（案例檔本身、EXCLUDED_REGION、判成刪除的除外）要由 LLM 在"
                                "驗證範圍宣告「由哪個案例驗」：宣告那支案例的那一項帶 case_for，列它驗的程式檔。程式只核對事實：那一項"
                                "點得到案例檔（測試檔、測試節點，或只跑特定測試檔的指令）、案例檔仍存在而且本 session 新寫或改過、"
                                "那一項在最後一次改動之後跑綠（和 "
                                "SCOPE_ITEM_RECEIPT_AFTER_EDIT 同一個判斷）。改了哪支案例檔不再替別的程式清帳；先紅後綠只記錄"
                                "（CASE_RED_THEN_GREEN），不在這裡擋。",
    "NO_CASE_NEEDS_USER": "LLM 宣告某個改過的程式檔不需要新案例（verify_scope 的 no_case：[{path, reason}]，理由必填；既有案例已經驗到也走這條）"
                          "→ 照擋：要不要補案例由使用者裁，照【收尾放行確認】問、題目帶上這個理由（擋滿不准自行放行的裁定不變）。"
                          "使用者放行那一刻把宣告裡的 no_case 檔記成已裁定（綁在它當時的最後一次修改）：之後沒再改就不再為它擋、"
                          "不每回合重問；再改了要重新裁。",
    "CASE_DECL_WELL_FORMED": "宣告收件：case_for 只能掛在點得到案例檔的項目（測試檔、測試節點，或只跑特定測試檔的指令；案例檔＝符合 "
                             "verify_case_globs 的程式檔；資料夾與整體驗證不算），列的每個路徑都要是程式檔、存在或本 session 改過（搬走的"
                             "舊路徑也還欠著）；no_case 每筆同樣的 path 加非空 reason；同一個檔不能同時列在 case_for 與 no_case。"
                             "有一處不合格整份退回。",
})


def case_decl_form_verdict(problems: Sequence[str]) -> Verdict:
    """CASE_DECL_WELL_FORMED：problems＝收件時查到的事實問題（wg_verify_scope.declare 查：項目種類、是不是案例檔、路徑在不在）。"""
    rule = "CASE_DECL_WELL_FORMED"
    if problems:
        return Verdict(rule, True, "案例宣告（case_for／no_case）不合格，整份退回", tuple(problems))
    return Verdict(rule, False, "案例宣告收下")


def case_for_change_verdict(name: str, checks: Sequence[Tuple[str, str]], no_case_reason: str = "",
                            user_approved: bool = False) -> Verdict:
    """CASE_DECLARED_FOR_CHANGE／NO_CASE_NEEDS_USER：name＝改過的程式檔；checks＝宣告驗它的每個案例 (案例, 問題)，問題空＝成立
    （事實由 wg_verify_scope.case_check 查：案例在不在、本 session 新寫或改過沒、那一項改完之後跑綠沒）；no_case_reason＝宣告
    不需要新案例的理由；user_approved＝使用者放行時記下的裁定還對得上它現在的最後一次修改。有一個案例成立就不欠；宣告的案例
    都不成立照欠（不退去看 no_case）。"""
    rule = "CASE_DECLARED_FOR_CHANGE"
    ok = [c for c, problem in checks if not problem]
    if ok:
        return Verdict(rule, False, f"{name} 由 {ok[0]} 驗：本 session 新寫或改過、改完之後跑綠")
    if checks:
        return Verdict(rule, True, f"{name} 宣告由 {'、'.join(c for c, _ in checks[:3])} 驗，還不成立",
                       tuple(f"{c}：{p}" for c, p in checks[:3]))
    reason = " ".join(str(no_case_reason or "").split())[:160]
    if reason and user_approved:
        return Verdict("NO_CASE_NEEDS_USER", False, f"{name} 宣告不需要新案例（理由：{reason}），使用者已放行，之後沒再改")
    if reason:
        return Verdict("NO_CASE_NEEDS_USER", True, f"{name} 宣告不需要新案例（理由：{reason}）：要不要補由使用者裁",
                       (f"用 AskUserQuestion 照【收尾放行確認】問，題目寫「{name} 不需要新案例：{reason}」並掛目標節點",))
    return Verdict(rule, True, f"{name} 改過，還沒宣告由哪個案例驗",
                   ("在 verify_scope 宣告驗它的那支案例（本 session 新寫或改過的測試檔／測試節點）那一項加 case_for: [\"<程式檔>\"]；"
                    "真的不需要新案例就加 no_case: [{path, reason}]，再照【收尾放行確認】問使用者",))


# ─── 收尾自清：本 session 建的東西用完要清（事實由 handlers/aec_ledger.cleanup_facts 現場查，閘在 handlers/stop.py） ───
RULES.update({
    "LEFTOVER_NEEDS_CLEANUP": "宣告完成時，本 session 帳上有建立紀錄的（開場快照比對出來、來源不明的不算）、還在、沒說要留的這些東西 → "
                              "每個使用者回合擋一次，列每一項與刪除指令：刪掉，或在收尾檢核 (i) 寫一行理由（路徑照寫，分支寫 "
                              "`branch:<名> — 理由`）。列的：工作樹、已合併的分支（被列出的工作樹用著的也算，刪完工作樹就刪得掉）、"
                              "能刪的臨時 repo、專案外能刪的檔案資料夾。不列：沒合併的分支（可能是還要的工作）、暫存區（使用者在 HUD "
                              "清）、專案裡還沒進版控的新檔（多半是待 commit 的正式產出）、被 .gitignore 排除的、推上遠端的分支（刪了"
                              "別人也看不到，要使用者決定）、別的開著的 session 正在用的。「說要留」＝使用者在 HUD 按過保留，或 AI 在 "
                              "(i)（舊格式 (d)）寫過理由。不吃 stop_gate_max_blocks。",
})


def leftover_candidates(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """LEFTOVER_NEEDS_CLEANUP：帳上還在的東西（aec_ledger.cleanup_facts／list_alive 的列）→ 該由 AI 收尾清掉或寫理由的那些，順序照原列。
    吃結構化事實：kind、where（檔案資料夾在哪：temp／ignored／untracked／outside）、merged、used_by（用著這個分支的工作樹）、
    busy（別的開著的 session 正在用）、can_delete、decision、note、source。"""
    def kept(it: Dict[str, Any]) -> bool:
        return it.get("decision") == "keep" or (it.get("source") in ("aec-i", "aec-d") and bool(str(it.get("note") or "").strip()))

    base = [it for it in items if it.get("source") != "snapshot" and not it.get("busy") and not kept(it)]
    worktrees = {canon_path(it.get("path") or "") for it in base if it.get("kind") == "worktree"}
    out: List[Dict[str, Any]] = []
    for it in base:
        kind = it.get("kind")
        if kind == "worktree":
            ok = True
        elif kind == "branch":
            ok = it.get("merged") is True and (bool(it.get("can_delete")) or (bool(it.get("used_by"))
                                                                           and canon_path(it["used_by"]) in worktrees))
        elif kind == "repo":
            ok = bool(it.get("can_delete"))
        elif kind in ("file", "dir"):
            ok = it.get("where") == "outside" and bool(it.get("can_delete"))
        else:
            ok = False
        if ok:
            out.append(it)
    return out


def leftover_cleanup_verdict(claims_done: bool, items: Sequence[Dict[str, Any]]) -> Verdict:
    """LEFTOVER_NEEDS_CLEANUP：owed＝宣告完成而帳上還有該清的東西；evidence 一行一項（名稱與白話狀態）。"""
    rule = "LEFTOVER_NEEDS_CLEANUP"
    if not claims_done:
        return Verdict(rule, False, "沒有宣告完成")
    cands = leftover_candidates(items)
    if not cands:
        return Verdict(rule, False, "帳上沒有該清的東西")
    return Verdict(rule, True, f"宣告完成，但這個 session 建的 {len(cands)} 樣東西還在、也沒說要留",
                   tuple(f"{c.get('title')}（{c.get('label')}）" for c in cands))


# ─── 紅燈精準：退避軟偵測的 context 豁免（事實由 handlers/stop.py 收，詞表在 memory/_meta/forbidden-phrases.json） ───
RULES.update({
    "EVASION_CONTEXT_EXEMPT": "退避軟偵測（Stop detect_evasion → evasion_flag → 下輪注入舉證、收尾檢核升紅）在下列四件事都有證據時豁免："
                              "context 用量大於 deferral_gate.max_context_ratio（剛好等於門檻和 DeferralGate 一樣算還夠；量不出不豁免）；"
                              "命中的是延後到下個／新 session、之後／下次再這一類（詞表 context_exempt_deferral）；被推的事有落地："
                              "本使用者回合交過 (k) 有內容（不是「無」）的收尾檢核，或寫了 memory/_staging/next-phase-*.md；本回合使用者"
                              "原話在（turn_prompts 存在、非空、屬於目前回合）而且沒叫現在做（現在／馬上／立刻／這回合／直接做／這邊做）。"
                              "任一判不出就照舊標記。豁免照記錄（guard log），不注入、不升紅。owed＝照舊標記。",
})

_DO_IT_NOW_RE = lazy_re(r"現在|馬上|立刻|這回合|直接做|這邊做|這裡做")


def evasion_context_exempt_verdict(exempt_phrase: bool, ratio: float, max_ratio: float, landed: bool,
                                   prompts: Optional[Sequence[str]], prompts_current: bool) -> Verdict:
    """EVASION_CONTEXT_EXEMPT：owed＝照舊標記（不豁免）。exempt_phrase＝命中詞屬可豁免的延後語（wg_evasion 判）；ratio＝context
    用量（0.0＝量不出）；landed＝本回合 (k) 有內容或寫了交接檔；prompts＝本回合使用者原話（None＝沒有這個欄位）；
    prompts_current＝那份原話屬於目前的使用者回合。"""
    rule = "EVASION_CONTEXT_EXEMPT"
    if not exempt_phrase:
        return Verdict(rule, True, "命中的不是可豁免的延後語")
    if not ratio or ratio <= max_ratio:
        return Verdict(rule, True, f"context 用量 {ratio:.2f} 沒超過門檻 {max_ratio:.2f}（或量不出）")
    if not landed:
        return Verdict(rule, True, "被推的事沒落地：本回合沒有內容不是「無」的 (k)，也沒寫交接檔")
    if not prompts or not prompts_current:
        return Verdict(rule, True, "判不出使用者本回合有沒有叫現在做（本回合原話缺、空、或不是這一回合的）")
    if any(_DO_IT_NOW_RE.search(str(p or "")) for p in prompts):
        return Verdict(rule, True, "使用者本回合叫現在做")
    return Verdict(rule, False, f"context 用量 {ratio:.2f} 超過門檻、延後的事已落地、使用者沒叫現在做 → 豁免")


# ─── G6 階段 4（判斷入口盤點 P6／P7）：宣稱與退避留給 LLM 介入的入口。事實由 wg_verify_ledger／wg_evasion／handlers/stop 收，這裡只判結構與對應 ───
RULES.update({
    "CLAIM_WORDS_ARE_HINTS": "(a)(b)(c) 的宣稱詞表只是提示，不替 LLM 判語意。命中且沒證據時，被判的同一串文字（承接的先前宣稱＋最後一則；"
                             "中段寫過的宣稱行最後一則不必重寫）要有一行"
                             "「宣稱｜<修好|量了|試過>：收據 <指令片段或哨兵名>」或「宣稱｜<…>：非本回合宣稱，因為 <理由>」："
                             "沒這行 → 照原規則擋並附寫法；「非本回合宣稱」附理由 → 放行、留帳（guard-reconcile.jsonl event=claim_disclaimed，"
                             "健檢抽查）；「收據」→ 走 CLAIM_RECEIPT_REF_MATCH。結構化的達成＋證據（need_goal 完整對照）仍是寫碼類的正式宣告，"
                             "宣稱行只處理散文裡的詞。",
    "CLAIM_CONDITIONAL_NOT_CLAIM": "(a)(b)(c) 判宣稱時，講以後的條件句不算：如果／假如／要是／一旦／等到／若（若干除外）…<動詞>、緊貼的「等<動詞>」、"
                                   "<動詞>之後／以後…再／一起／才／就／會／要（子句後段有「了／過」＝已經發生，照算宣稱）；宣稱行（宣稱｜…）"
                                   "本身是對閘的回答，整行先拿掉再判。樣式在 memory/_meta/forbidden-phrases.json 三類宣稱的 exclude_patterns"
                                   "（備用表 hooks/wg_evasion._conditional_excludes）；完成詞（claims_completion）是整段尾巴排除的粗判，不套。",
    "CLAIM_DISCLAIM_NEEDS_REASON": "宣稱行寫「非本回合宣稱」要附理由：拿掉角括號片段後還有任一字母或數字（任何語言），而且沒留著擋訊息的"
                                   "理由範本佔位（<理由…>、<為什麼…>）；純標點不算，理由裡引用 <標籤> 照算；沒理由不算回。程式不評理由充不充分。",
    "CLAIM_RECEIPT_REF_MATCH": "宣稱行指的收據要能辨識出是哪一張：引用的字要是那條指令的一個完整 token（整個 token、檔名、路徑尾段、"
                               "測試節點尾段），或帶空白的逐字片段，或哨兵名相同；python／pytest／py／-m 這類通用字、旗標、純副檔名不算指名。"
                               "對上的那張還要過原本的收據資格（指令完整、記了環境、同一棵樹）："
                               "說修好 → 合格 PASS、同根、晚於相關改檔最後一次修改；說量了 → DONE 且指令可信或跑了部位量尺；"
                               "說試過 → 指令可信的任一筆。對不上照擋。",
    "NOT_DOING_DECLARED": "退避語（軟偵測與 DeferralGate）命中的那一行若本身就是「不做｜<哪一件>：<理由>」，或同一段文字有不做行而它的事項"
                          "出現在命中那一行 → 不標、不擋、留帳（guard log evasion_declared／deferral_declared）；理由要有文字內容、不是佔位。"
                          "說明句被詞表誤命中（「下個 session 開場會列出…」是在描述已驗過的事）→ 寫「不是退避｜<命中的詞或句>：因為 <理由>」"
                          "同樣只查有沒有理由、留帳。詞表各類的 exception 文字（風險、為什麼超出）附在提示裡給 LLM 寫理由用，程式不評理由內容。",
    "USER_WAIVER_NEEDS_CITATION": "紅測清單的使用者豁免（名稱沿用）：近 3 則使用者原話含「先這樣／跳過／留著」不直接清掉紅測清單；"
                                  "LLM 寫「不做｜<哪一支>：使用者說「<原句片段>」」就留帳放行，原句不再比對使用者原話（事後抽查）。"
                                  "只豁免事項指得到那一筆的（事項是失敗指令或摘要的一個完整 token：整個 token、檔名、路徑或節點尾段；"
                                  "pytest 節點也認函式名、類別名與不帶副檔名的檔名；通用字不算）；摘要逐支列出失敗（FAILED／ERROR 行）時每一支"
                                  "各自要有豁免，有一支沒有整筆照算紅。豁免一成立就記帳（state testfail_waivers；留帳 testfail_waived 與 "
                                  "deferral_declared），之後同 session 同一支看帳，但收尾仍要有對到它的不做行；使用者在記帳之後又提到這一支 → 帳不算。",
    "RED_ITEMS_ONLY_FROM_FAILURE_LINES": "紅測的失敗項只從失敗行取：pytest 摘要 FAILED／ERROR 開頭的節點行（扣掉之後的綠已跑到的 "
                                         "cleared_units）；沒有節點行時只認行首 FAIL／FAILED／ERROR 的行（unittest、go、jest）"
                                         "加上指令點名的案例檔。指令裡 # 開頭的註解行（AI 自己寫的不做行）、git 輸出、Exit code 行都不是失敗項，"
                                         "不拿來對不做行。擋訊息抬頭算還沒跑綠的支數與已綠的支數（不是幾筆紀錄），逐筆只列還沒跑綠的失敗項（已清的絕不列）與指令實際跑的那行（不是摘要第一行、不是註解），附重跑哪幾支檔就夠（還紅的那幾支所在的檔）；沒列出失敗項就說沒列出、"
                                         "要不截斷重跑；不做行對到了某支、但引用不在近 3 則使用者原話、帳上也沒有 → 擋訊息說出是哪一支、缺什麼；"
                                         "帳上有那支的豁免、這次收尾卻沒寫對到它的不做行 → 擋訊息給那一行照抄（帳不自動放）。",
})

CLAIM_LABELS: Dict[str, str] = {"fixed": "修好", "measured": "量了", "tried": "試過"}
_CLAIM_LABEL_KINDS: Dict[str, str] = {"修好": "fixed", "修復": "fixed", "量了": "measured", "量過": "measured",
                                      "試過": "tried", "跑了": "tried", "跑過": "tried"}
_CLAIM_DISP_RE = lazy_re(r"宣稱\s*[｜|]\s*(修好|修復|量了|量過|試過|跑了|跑過)\s*[：:]\s*(.+)")
_DISCLAIM_RE = lazy_re(r"^(?:非|不是|並非)\s*本回合\s*(?:自己的?)?\s*宣稱\s*[，,：:、]?\s*(?:因為|理由[：:]?|原因[：:]?)?\s*(.*)$")
_RECEIPT_REF_RE = lazy_re(r"^收據\s*[：:]?\s*(.+)$")
# 「追蹤｜<哪一件>：<現在不做的原因>」與舊寫法「不做｜…」同一種宣告（收尾那一問：快又有效的現在做，其餘各記一行追蹤）
_NOT_DOING_RE = lazy_re(r"(?:不做|追蹤)\s*[｜|]\s*([^：:\n]{1,80}?)\s*[：:]\s*(.+)")
# 說明句被退避詞表誤命中（「下個 session 開場會列出…」是在描述已驗過的事）→ AI 說明這不是退避，程式只查有沒有理由、留帳
_NOT_EVASION_RE = lazy_re(r"不是退避\s*[｜|]\s*([^：:\n]{1,80}?)\s*[：:]\s*(?:因為|理由[：:]?)?\s*(.+)")
_USER_SAID_RE = lazy_re(r"使用者\s*(?:說|原話|的話|說的)\s*[：:]?\s*[「『\"“]([^「」『』\"”\n]{1,160})[」』\"”]")
_WS_RE = lazy_re(r"\s+")
_ITEM_STRIP_RE = lazy_re(r"[\s，,、：:（）()「」『』`*\-—–~～?？!！.。；;]")
_WORD_CHAR_RE = lazy_re(r"[A-Za-z0-9一-鿿]")
_LATIN_ONLY_RE = lazy_re(r"^[A-Za-z0-9 _.\-]+$")
_TOKEN_TRIM = "\"'`「」『』（）()[]{}<>,，;；。:："
# 指不到特定收據／測試的通用字：直譯器、跑測工具、旗標、純副檔名（規則 CLAIM_RECEIPT_REF_MATCH／USER_WAIVER_NEEDS_CITATION）
GENERIC_NAMES = frozenset({"python", "python3", "py", "pytest", "test", "tests", "verify", "run", "node", "npm", "npx", "bash", "sh",
                           "pwsh", "powershell", "cd", "cmd", "exe", "md", "json", "txt", "m", "q", "x", "utf8"})


def _nows(s: Any) -> str:
    return _WS_RE.sub("", str(s or "")).lower()


def has_text(s: Any, min_chars: int = 2) -> bool:
    """有文字內容：至少 min_chars 個中文或英數字（純標點、「....」不算）。"""
    return len(_WORD_CHAR_RE.findall(str(s or ""))) >= min_chars


_ANGLE_SEGMENT_RE = lazy_re(r"<[^<>\n]*>")
# 擋訊息教 AI 填理由的範本佔位：<理由>、<理由：…>、<一句理由>、<為什麼…>（各閘的 hint 都這樣開頭）
_REASON_PLACEHOLDER_RE = lazy_re(r"<\s*(?:一句)?(?:理由|為什麼)[^<>\n]*>")


def reason_present(reason: str, hint_texts: Sequence[str] = ()) -> bool:
    """理由有填：拿掉角括號片段之後還有任一字母或數字（任何語言），而且沒留著擋訊息的範本佔位：<理由…>、<為什麼…>，
    或角括號裡的字出現在呼叫端印給 AI 的範本說明 hint_texts 裡（半抄範本「留到下個 session，<理由>」不算）。
    理由裡引用標籤（「修正 <幣別> 標籤」）照算。只查有沒有，不評內容充不充分。"""
    text = str(reason or "")
    if _REASON_PLACEHOLDER_RE.search(text):
        return False
    for seg in _ANGLE_SEGMENT_RE.findall(text):
        inner = seg[1:-1].strip()
        if inner and any(inner in h for h in hint_texts if h):
            return False
    return any(ch.isalnum() for ch in _ANGLE_SEGMENT_RE.sub("", text))


def is_generic_name(name: str) -> bool:
    """指不到特定東西的字：通用字表、旗標（- 開頭）、純副檔名（. 開頭）、沒有文字內容。"""
    n = str(name or "").strip().lower()
    return (not has_text(n) or n in GENERIC_NAMES or n.startswith("-") or n.startswith(".")
            or n.lstrip(".") in GENERIC_NAMES)


def names_item(text: str, item: str) -> bool:
    """item 指得到 text（指令或摘要）裡的一個完整 token：整個 token 相等、token 的檔名相等、token 以 /item 或 \\item 結尾（路徑尾段）、
    或 item 含 :: 時 token 以它結尾（測試節點尾段）；item 含空白時改成逐字片段比對（去多餘空白，不分大小寫）。通用字一律不算。
    `verify_a.py` 對得到 `hooks/verify/verify_a.py` 與 `verify_a.py::test_x`，對不到 `old_verify_a.py`、`verify_ab.py`。"""
    it = _WS_RE.sub(" ", str(item or "")).strip().lower()
    if not it or is_generic_name(it):
        return False
    hay = _WS_RE.sub(" ", str(text or "")).lower()
    if " " in it:
        return it in hay
    for raw in hay.split(" "):
        tok = raw.strip(_TOKEN_TRIM)
        if not tok:
            continue
        if tok == it or tok.endswith("/" + it) or tok.endswith("\\" + it):
            return True
        base = tok.replace("\\", "/").rsplit("/", 1)[-1]
        if base == it or base.startswith(it + "::") or ("::" in it and (tok.endswith(it) or base.endswith(it))):
            return True
    return False


def parse_claim_dispositions(text: str) -> Dict[str, List[Dict[str, str]]]:
    """收尾文字裡的宣稱行 → {kind: [{mode: receipt|disclaim|unknown, ref|reason|raw, line}]}。一行一條，kind 用詞對應 CLAIM_LABELS。"""
    out: Dict[str, List[Dict[str, str]]] = {}
    for raw in str(text or "").splitlines():
        m = _CLAIM_DISP_RE.search(raw)
        if not m:
            continue
        kind, val, line = _CLAIM_LABEL_KINDS[m.group(1)], m.group(2).strip(), raw.strip()[:200]
        d = _DISCLAIM_RE.match(val)
        if d:
            out.setdefault(kind, []).append({"mode": "disclaim", "reason": d.group(1).strip(), "line": line})
            continue
        r = _RECEIPT_REF_RE.match(val)
        if r:
            out.setdefault(kind, []).append({"mode": "receipt", "ref": r.group(1).strip(), "line": line})
            continue
        out.setdefault(kind, []).append({"mode": "unknown", "raw": val, "line": line})
    return out


def is_claim_line(line: str) -> bool:
    """這一行是宣稱行（「宣稱｜修好：非本回合宣稱，因為…」）：它本身是對閘的回答，裡面的「非本回合」不是退避語（實跑探針踩到：
    回了宣稱行反被 DeferralGate 當「非本回合」擋）。"""
    return bool(_CLAIM_DISP_RE.search(str(line or "")))


def claim_hint(kind: str) -> str:
    label = CLAIM_LABELS.get(kind, kind)
    return (f"詞表只是提示（規則 CLAIM_WORDS_ARE_HINTS）：這句不是這一回合自己做了的宣稱 → 回一行「宣稱｜{label}：非本回合宣稱，因為 <理由>」；"
            f"是宣稱 → 補證據，或回「宣稱｜{label}：收據 <指令片段或哨兵名>」指出對應哪張收據")


def claim_disposition_verdict(kind: str, dispositions: Dict[str, List[Dict[str, str]]],
                              find_receipt: Callable[[str], Optional[str]]) -> Verdict:
    """CLAIM_WORDS_ARE_HINTS／CLAIM_DISCLAIM_NEEDS_REASON／CLAIM_RECEIPT_REF_MATCH：owed＝照原規則擋。
    find_receipt(ref) 回對上的收據描述或 None（對帳端用本 session 收據與改檔時間判）。同類多行取第一條成立的；都不成立回最後一條的理由。"""
    label, hint = CLAIM_LABELS.get(kind, kind), claim_hint(kind)
    ds = dispositions.get(kind) or []
    if not ds:
        return Verdict("CLAIM_WORDS_ARE_HINTS", True, f"說「{label}」沒證據，也沒回宣稱行", (hint,))
    last = Verdict("CLAIM_WORDS_ARE_HINTS", True, "宣稱行格式認不得", (ds[-1]["line"], hint))
    for d in ds:
        if d["mode"] == "disclaim":
            if reason_present(d.get("reason", "")):
                return Verdict("CLAIM_WORDS_ARE_HINTS", False, f"AI 回「非本回合宣稱」：{d['reason'][:120]}", (d["line"],))
            last = Verdict("CLAIM_DISCLAIM_NEEDS_REASON", True, "宣稱行寫「非本回合宣稱」但沒附理由（或只有佔位）", (d["line"], hint))
        elif d["mode"] == "receipt":
            found = find_receipt(d.get("ref", ""))
            if found:
                return Verdict("CLAIM_RECEIPT_REF_MATCH", False, f"AI 指到收據「{d['ref'][:80]}」→ 對上：{found}", (d["line"],))
            last = Verdict("CLAIM_RECEIPT_REF_MATCH", True,
                           f"宣稱行指的收據「{d['ref'][:80]}」對不上本 session 任何一筆合格收據（或早於相關改檔）", (d["line"], hint))
        else:
            last = Verdict("CLAIM_WORDS_ARE_HINTS", True, "宣稱行格式認不得（要「收據 …」或「非本回合宣稱，因為 …」）", (d["line"], hint))
    return last


def parse_not_doing(text: str) -> List[Dict[str, str]]:
    """收尾文字裡的不做行與不是退避行 → [{mode, item, reason, quote, line}]：mode＝not_doing（「不做｜<哪一件>：<理由>」）或
    disclaim（「不是退避｜<命中的詞或句>：因為 <理由>」，說明句被詞表誤命中時用）；quote＝「使用者說「…」」引用的片段（沒有＝空字串，
    不是退避行一律空）。"""
    out: List[Dict[str, str]] = []
    for raw in str(text or "").splitlines():
        m = _NOT_DOING_RE.search(raw)
        if m:
            reason = m.group(2).strip()
            q = _USER_SAID_RE.search(reason)
            out.append({"mode": "not_doing", "item": m.group(1).strip(), "reason": reason,
                        "quote": q.group(1).strip() if q else "", "line": raw.strip()[:240]})
            continue
        m = _NOT_EVASION_RE.search(raw)
        if m:
            out.append({"mode": "disclaim", "item": m.group(1).strip(), "reason": m.group(2).strip(), "quote": "",
                        "line": raw.strip()[:240]})
    return out


def not_doing_covering(line: str, decls: Sequence[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """命中退避語的那一行對到哪一條不做行：那一行本身就是不做行，或某條的事項（去標點、至少 2 字）出現在那一行。"""
    ln = _nows(line)
    for d in decls:
        if _nows(d["line"]) and _nows(d["line"]) in ln:
            return d
    for d in decls:
        item = _ITEM_STRIP_RE.sub("", d["item"]).lower()
        if len(item) >= 2 and item in _ITEM_STRIP_RE.sub("", str(line or "")).lower():
            return d
    return None


def quote_in_prompts(quote: str, prompts: Sequence[str]) -> bool:
    """引用的片段有文字內容（至少 2 個中文或英數字，純標點不算）且出現在任一則使用者原話裡：中文片段去空白子字串比對；
    純英數片段整詞比對（「ok」對不到「broken」）。"""
    if not has_text(quote):
        return False
    q = _WS_RE.sub(" ", str(quote or "")).strip()
    if _LATIN_ONLY_RE.match(q):
        rx = re.compile(r"(?<![A-Za-z0-9])" + re.escape(q).replace(r"\ ", r"\s*") + r"(?![A-Za-z0-9])", re.IGNORECASE)
        return any(rx.search(_WS_RE.sub(" ", str(p or ""))) for p in prompts or ())
    qn = _nows(q)
    return any(qn in _nows(p) for p in prompts or ())


def not_doing_reason_hint(exception: str = "") -> str:
    """不做行範本裡「<理由：…>」那段說明：詞表那一類的 exception（去掉「除非附」），沒有就用通用的四種理由。"""
    return re.sub(r"^除非附\s*", "", str(exception or "")).strip().strip("「」") or "風險／為什麼超出／不可逆／要使用者拍板"


CLOSING_ASK = "剩下沒做的，哪些改得快又有效？快又有效的現在做掉；其餘每件寫一行「追蹤｜<哪一件>：<現在不做的原因>」（記進追蹤帳本）"


def not_doing_hint(exception: str = "") -> str:
    return (f"{CLOSING_ASK}（規則 NOT_DOING_DECLARED，會留帳）；"
            "這句只是在描述、沒推任何事 → 「不是退避｜<命中的詞>：因為 <理由>」（留帳抽查）")


def not_doing_verdict(line: str, decls: Sequence[Dict[str, str]], prompts: Sequence[str], exception: str = "") -> Verdict:
    """NOT_DOING_DECLARED：owed＝照舊標記或擋。line＝命中退避語的那一行；prompts＝近 3 則使用者原話（退避這一路不再核引用）。
    理由裡的角括號片段若是這個範本印給 AI 的說明（<不修的實際風險>）＝沒換掉的佔位，不算理由。"""
    hint_why = (not_doing_reason_hint(exception),)
    d = not_doing_covering(line, decls)
    if d is None:
        return Verdict("NOT_DOING_DECLARED", True, "退避語沒有對應的不做行", (str(line or "").strip()[:120], not_doing_hint(exception)))
    if d.get("mode") == "disclaim":
        if reason_present(d["reason"], hint_why):
            return Verdict("NOT_DOING_DECLARED", False, f"AI 說明「{d['item'][:60]}」不是退避，因為 {d['reason'][:120]}", (d["line"],))
        return Verdict("NOT_DOING_DECLARED", True, "不是退避行沒附理由（或只有佔位）", (d["line"], not_doing_hint(exception)))
    if d["quote"]:              # 使用者叫跳過：不再要求逐件引到原句（退避這一路），寫了就收、留帳
        return Verdict("NOT_DOING_DECLARED", False, f"使用者說「{d['quote'][:60]}」：{d['item'][:60]}", (d["line"],))
    if reason_present(d["reason"], hint_why):
        return Verdict("NOT_DOING_DECLARED", False, f"AI 宣告不做「{d['item'][:60]}」，因為 {d['reason'][:120]}", (d["line"],))
    return Verdict("NOT_DOING_DECLARED", True, "不做行沒附理由（或只有佔位）", (d["line"], not_doing_hint(exception)))


def yes_no_declaration(text: str, label: str) -> Optional[Dict[str, Any]]:
    """AI 回程式問句的宣告行「<label>｜是：<理由>」或「<label>｜不是：<理由>」→ 理由有填（reason_present）的最後一條：
    {"yes", "reason", "line"}；沒有回 None（理由空、純標點、範本佔位都不算）。只認行首（可帶空白、清單符號、粗體）：
    句中引用的宣告字樣（「不要寫成『糾正｜是：…』」）是說明不是答覆；寫了好幾條以最後一條為準。
    CORRECTION_WORDS_ARE_HINTS／EXTRACT_VETO_NEEDS_JUDGMENT 用。"""
    rx = re.compile(rf"^[\s*\-•]*{re.escape(label)}\s*[｜|]\s*(不是|是)\s*[：:]\s*(.+)")
    found = None
    for raw in str(text or "").splitlines():
        m = rx.match(raw)
        if m and reason_present(m.group(2)):
            found = {"yes": m.group(1) == "是", "reason": m.group(2).strip()[:200], "line": raw.strip()[:240]}
    return found


def correction_verdict(decl: Optional[Dict[str, Any]]) -> Verdict:
    """CORRECTION_WORDS_ARE_HINTS：owed＝計一次糾正，只有 AI 判是才計；沒回不計（詞表不替 AI 判，沒回的比例靠留帳抽查）。"""
    if decl is None:
        return Verdict("CORRECTION_WORDS_ARE_HINTS", False, "命中糾正詞，AI 沒回糾正行：不計、記成沒回")
    if decl["yes"]:
        return Verdict("CORRECTION_WORDS_ARE_HINTS", True, f"AI 判是糾正：{decl['reason'][:120]}", (decl["line"],))
    return Verdict("CORRECTION_WORDS_ARE_HINTS", False, f"AI 判不是糾正：{decl['reason'][:120]}", (decl["line"],))


CONFLICT_VERDICTS = ("conflict", "not_conflict")


def conflict_declarations(declared: Any) -> List[Dict[str, Any]]:
    """atom_write 的 conflict 參數（一個物件或物件陣列）→ 物件陣列；別的型別回空。"""
    if isinstance(declared, dict):
        return [declared]
    if isinstance(declared, list):
        return [d for d in declared if isinstance(d, dict)]
    return []


def conflict_declaration_verdict(candidates: Sequence[str], declared: Any) -> Tuple[Verdict, List[Dict[str, str]]]:
    """CONFLICT_DECLARED_BY_AI：candidates＝門檻篩出的候選卡名。每個候選都要有一條 {of: 候選名, verdict: conflict|not_conflict,
    why: 理由（reason_present）} → not owed，回照候選順序的宣告 [{of, verdict, why}]；owed＝要（重新）宣告，why 列出缺的與寫錯的。
    宣告了不在候選裡的卡不算錯，略過不收。"""
    decls = conflict_declarations(declared)
    problems: List[str] = []
    got: List[Dict[str, str]] = []
    for name in candidates:
        mine = [d for d in decls if str(d.get("of", "")).strip() == name]
        d = mine[0] if mine else None
        if d is None:
            problems.append(f"{name}：沒宣告")
        elif len({str(x.get("verdict", "")).strip() for x in mine}) > 1:
            problems.append(f"{name}：同一張候選宣告了兩種判法，只留一條")
        elif str(d.get("verdict", "")).strip() not in CONFLICT_VERDICTS:
            problems.append(f"{name}：verdict 要是 conflict 或 not_conflict")
        elif not reason_present(str(d.get("why", ""))):
            problems.append(f"{name}：why 要寫一句理由")
        else:
            got.append({"of": name, "verdict": str(d["verdict"]).strip(), "why": str(d["why"]).strip()[:200]})
    if problems:
        return Verdict("CONFLICT_DECLARED_BY_AI", True, "衝突候選要逐一宣告：" + "；".join(problems)), []
    hit = [d["of"] for d in got if d["verdict"] == "conflict"]
    why = f"AI 宣告衝突：{'、'.join(hit)}" if hit else "AI 宣告全部候選都不是衝突"
    return Verdict("CONFLICT_DECLARED_BY_AI", False, why, tuple(f"{d['of']}：{d['verdict']}：{d['why']}" for d in got)), got


_PENDING_ATOM_RE = lazy_re(r"^\s*([^\s:：]+)[:：]")     # 卡名是不含空白的 slug，緊接冒號


def names_failed_test(text: str, item: str) -> bool:
    """USER_WAIVER_NEEDS_CITATION 的事項比對：names_item 之外，紅測摘要裡的 pytest 節點（檔::類::函式[參數]）也認函式名、類別名與
    不帶副檔名的檔名：擋訊息範本叫 AI 寫「紅的那支測試名」，照寫的就是這些。通用字、含空白的事項不放寬。"""
    if names_item(text, item):
        return True
    it = str(item or "").strip().strip("`").lower()
    if not it or " " in it or is_generic_name(it):
        return False
    for raw in _WS_RE.sub(" ", str(text or "")).lower().split(" "):
        tok = raw.strip(_TOKEN_TRIM).replace("\\", "/")
        if "::" not in tok:
            continue
        path, *parts = tok.split("::")
        name = path.rsplit("/", 1)[-1]
        if (it in (name, name.rsplit(".", 1)[0]) or ("/" in it and (path == it or path.endswith("/" + it)))
                or any(it in (p, p.split("[", 1)[0]) for p in parts)):
            return True
    return False


_FAILED_UNIT_RE = lazy_re(r"^(?:FAILED|ERROR)\s+(\S+)", re.MULTILINE)


def failed_units(summary: Any) -> List[str]:
    """紅測摘要裡 pytest 逐支列出的失敗（FAILED／ERROR 開頭那幾行的節點或檔，收集錯誤只有檔），小寫正斜線；沒列就空。"""
    return list(dict.fromkeys(m.group(1).replace("\\", "/").lower() for m in _FAILED_UNIT_RE.finditer(str(summary or ""))))


_FAILURE_LINE_RE = lazy_re(r"^\s*(?:-{2,3}\s*)?(?:FAILED|FAIL|ERROR)\b.*$", re.MULTILINE)
# 一行一支的失敗（沒有 pytest 節點時）：go「--- FAIL: TestX」、unittest「FAIL: test_x (mod.Cls)」、jest「FAIL src/a.test.js」；
# 「FAIL」「FAILED (failures=2)」「FAIL\t<套件>」這種結算行不是一支
_TEST_FAIL_LINE_RE = lazy_re(r"^\s*(?:-{2,3}\s*FAIL:\s*([^\s/]+)|(?:FAIL|ERROR):\s*(\S+)\s+\(|FAIL\s+(\S+\.(?:js|jsx|ts|tsx|mjs|cjs|py))\b)",
                                re.MULTILINE)
# 註解：行首的 #，或前面是空白的 #（shell 只在字首把 # 當註解開頭）
_COMMENT_RE = lazy_re(r"(?:^|(?<=\s))#.*$", re.MULTILINE)


def red_units(entry: Dict[str, Any]) -> List[str]:
    """RED_ITEMS_ONLY_FROM_FAILURE_LINES：這筆紅測還算紅的那幾支（failed_units 扣掉之後的綠已跑到的 cleared_units）。"""
    done = set((entry or {}).get("cleared_units") or ())
    return [u for u in failed_units((entry or {}).get("summary", "")) if u not in done]


def failure_lines(summary: Any) -> List[str]:
    """沒有 pytest 節點行時的失敗行：行首 FAIL／FAILED／ERROR（可帶 go 的 ---）的那幾行，去頭尾空白；其他行不是失敗項。"""
    return [m.group(0).strip() for m in _FAILURE_LINE_RE.finditer(str(summary or ""))]


def failure_units(summary: Any) -> List[str]:
    """沒有 pytest 節點行時一行一支的失敗名稱（go 子測試只取上層名），去重保序；結算行不算。"""
    names = (next(g for g in m.groups() if g) for m in _TEST_FAIL_LINE_RE.finditer(str(summary or "")))
    return list(dict.fromkeys(n.replace("\\", "/") for n in names))


def cmd_run_line(cmd: Any) -> str:
    """指令實際跑的部分（去掉 # 註解，多行併成一行）：擋訊息與比對用，AI 寫在指令註解裡的不做行不算指令。"""
    return " ".join(ln.strip() for ln in _COMMENT_RE.sub("", str(cmd or "")).splitlines() if ln.strip())


def _unlisted_unit(entry: Dict[str, Any]) -> str:
    """摘要沒列哪一支時整筆當一支的比對文字：測試子命令那幾段的參數（認不出測試子命令就整條，都去掉註解）＋失敗行；
    git 輸出、Exit code 行、echo 這類別段、註解都不算。"""
    return " ".join([_test_runner_args(cmd_run_line(entry.get("cmd", ""))).strip(),
                     *failure_lines(entry.get("summary", ""))]).strip()


def _waiver_units(entry: Dict[str, Any]) -> Tuple[List[str], bool]:
    """紅測豁免逐支比的單位與「有沒有逐支列出」：pytest 節點（扣掉已清的）→ 一行一支的失敗名稱 → 都沒有就整筆當一支。"""
    units = red_units(entry) or failure_units(entry.get("summary", ""))
    return (units, True) if units else ([_unlisted_unit(entry)], False)


def cleared_units(entry: Dict[str, Any]) -> List[str]:
    """這筆紅測逐支列出的失敗裡，之後的綠已經跑到的那幾支（cleared_units 與 failed_units 的交集，照摘要順序）。"""
    done = set((entry or {}).get("cleared_units") or ())
    return [u for u in failed_units((entry or {}).get("summary", "")) if u in done]


def red_unit_files(units: Sequence[str]) -> List[str]:
    """這幾支紅案所在的檔（去重保序）：重跑這幾支檔就夠。"""
    return list(dict.fromkeys(str(u).split("::", 1)[0] for u in units))


def red_count_label(failing: Sequence[Dict[str, Any]]) -> str:
    """擋訊息抬頭的數字：還沒跑綠的支數（逐支列出的扣掉已清；沒列出的整筆算 1 支），不是幾筆紀錄；真的有綠掉幾支才附「（M 支已綠）」
    （「0 支已綠」讀起來像清過帳卻一支沒綠，實跑誤導過 AI）。"""
    left = sum(len(red_units(f or {})) or 1 for f in failing)
    done = sum(len(cleared_units(f or {})) for f in failing)
    return f"還有 {left} 支沒跑綠" + (f"（{done} 支已綠）" if done else "")


RERUN_FILES_SHOWN_MAX = 600


def red_rerun_files_label(entry: Dict[str, Any]) -> str:
    """這筆紅測還沒跑綠的那幾支所在的檔，重跑這幾支檔就夠（整檔跑綠＝那檔的紅案全清，GREEN_CLEARS_ONLY_CASES_IT_RAN）；
    沒逐支列出的回空（由 _rerun_scope 給範圍）。太長就只列前三支加支數。"""
    files = red_unit_files(red_units(entry))
    if not files:
        return ""
    shown = "、".join(files)
    if len(shown) > RERUN_FILES_SHOWN_MAX:
        shown = "、".join(files[:3]) + f" 等 {len(files)} 支"
    return "重跑這幾支檔就夠：" + shown


def red_item_label(entry: Dict[str, Any], shown: int = 3) -> str:
    """擋訊息裡這筆紅測的失敗項：逐支列還沒跑綠的節點（已清的絕不列）；沒有就列失敗行；都沒有就明說輸出沒列出是哪一支。"""
    units = red_units(entry)
    if units:
        return "、".join(units[:shown]) + (f" 等 {len(units)} 支" if len(units) > shown else "")
    lines = failure_lines(entry.get("summary", ""))
    if lines:
        return "、".join(ln[:100] for ln in lines[:shown])
    return "（輸出沒列出 FAILED／ERROR 那幾行，看不出是哪一支：別截斷輸出、單獨重跑一次）"


def waiver_mentioned_since(entry: Dict[str, Any], history: Sequence[str]) -> bool:
    """帳記下之後使用者又提到這一支：history（近幾則原話，舊到新）裡記帳那則原話之後（那則不在了就整段）出現事項、或帳上那幾支的
    檔名／不帶副檔名的檔名／函式名（使用者不一定用同一個名字叫它；中文句子不靠空白斷詞，只要前後不是英數字）。通用字不算。"""
    names = [str(entry.get("item") or "")]
    for u in entry.get("units") or ():
        path, *parts = str(u).split("::")
        base = path.rsplit("/", 1)[-1]
        names += [base, base.rsplit(".", 1)[0], *(p.split("[", 1)[0] for p in parts)]
    words = {n.strip().lower() for n in names if n.strip() and not is_generic_name(n)}
    if not words:
        return False
    pat = re.compile("|".join(rf"(?<![a-z0-9_]){re.escape(w)}(?![a-z0-9_])" for w in sorted(words)))
    said = str(entry.get("said") or "")[:200]
    at = max((i for i, h in enumerate(history) if said and str(h)[:200] == said), default=-1)
    return any(pat.search(str(h).lower()) for h in history[at + 1:])


def _booked_for(entry: Dict[str, Any], unit: str, listed: bool, cmd: str) -> bool:
    """帳上這筆是不是同一支：摘要逐支列出時比記帳那時的同一個節點（別檔同名函式不算）；沒列出時比同一條指令＋事項。"""
    if listed:
        return unit in (entry.get("units") or ())
    return not entry.get("units") and entry.get("cmd") == cmd[:200] and names_failed_test(unit, str(entry.get("item") or ""))


def _unit_waiver(unit: str, listed: bool, cmd: str, cited: Sequence[Dict[str, str]], lines: Sequence[Dict[str, str]],
                 ledger: Sequence[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    hit = next(({**d, "via": "quote"} for d in cited if names_failed_test(unit, d["item"])), None)
    if hit is not None:
        return hit
    booked = next((e for e in ledger if _booked_for(e, unit, listed, cmd)), None)
    if booked is None:
        return None
    return next(({**d, "quote": d["quote"] or str(booked.get("quote") or ""), "via": "ledger"}
                 for d in lines if names_failed_test(unit, d["item"])), None)


def waived_failures(failing: Sequence[Dict[str, Any]], decls: Sequence[Dict[str, str]], prompts: Sequence[str],
                    ledger: Sequence[Dict[str, Any]] = (), history: Sequence[str] = ()
                    ) -> Tuple[List[Dict[str, Any]], List[Tuple[Dict[str, Any], Dict[str, Any]]]]:
    """USER_WAIVER_NEEDS_CITATION 套在紅測清單：回 (還算紅的, [(被豁免的那筆, 對上的不做行＋via＋units)])。
    豁免條件：不做行的事項指得到那支失敗（names_failed_test；通用字不算），而且寫了「使用者說「…」」（via＝quote；原句不再
    比對近 3 則原話，留帳抽查）；或本 session
    帳上（ledger＝state testfail_waivers，豁免成立時記的）有同一支的豁免（via＝ledger：引用看帳、不看窗口）。
    摘要逐支列出失敗（failed_units）時每一支各自要有豁免，有一支沒有整筆照算紅；沒列出就整筆（指令＋摘要）當一支。
    帳只認記帳那時的同一支（_booked_for），而且使用者在那之後沒再提到這支（waiver_mentioned_since；history＝近幾則原話，預設
    prompts；提到了就以新的話為準，回到引用窗口判；stop 每次收尾也把這種帳從 state 拿掉，免得那則原話擠出近 5 則後帳又活回來）；
    帳不自動放：收尾仍要有對到那一支的不做行。"""
    lines = [d for d in decls if d.get("mode", "not_doing") == "not_doing"]
    cited = [d for d in lines if d["quote"]]       # 引用不再比對近 3 則原話：寫了就留帳放行（原句照記、事後抽查）
    hist = list(history or prompts)
    live = [e for e in ledger or () if not waiver_mentioned_since(e, hist)]
    kept: List[Dict[str, Any]] = []
    waived: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for f in failing:
        cmd = str((f or {}).get("cmd", ""))
        units, listed = _waiver_units(f or {})
        hits = [_unit_waiver(u, listed, cmd, cited, lines, live) for u in units]
        if not all(hits):
            kept.append(f)
            continue
        merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for u, h in zip(units, hits):
            got = merged.setdefault((h["line"], h["via"]), {**h, "units": []})
            if listed:
                got["units"].append(u)
        waived += [(f, h) for h in merged.values()]
    return kept, waived


def waiver_miss_notes(kept: Sequence[Dict[str, Any]], decls: Sequence[Dict[str, str]], prompts: Sequence[str],
                      ledger: Sequence[Dict[str, Any]] = ()) -> List[str]:
    """RED_ITEMS_ONLY_FROM_FAILURE_LINES：還算紅的那幾筆為什麼沒豁免（不說的話 AI 只看到又被擋，會以為是名字沒對上）：
    不做行對到了某支、卻只寫了 AI 自己的理由（沒有「使用者說「…」」）→ 說是哪一支、要怎麼寫；帳上有這支的豁免、這次收尾卻沒寫
    對到它的不做行 → 給那一行照抄（帳不自動放）。"""
    out: List[str] = []
    lines = [d for d in decls if d.get("mode", "not_doing") == "not_doing"]
    for f in kept:
        units, listed = _waiver_units(f or {})
        for u in units:
            named = [d for d in lines if names_failed_test(u, d["item"])]
            e = next((e for e in ledger or () if _booked_for(e, u, listed, str(f.get("cmd", "")))), None)
            if named and e:
                continue                         # 這支照帳豁免了，整筆還紅是因為別支
            d = next((d for d in named if not d.get("quote")), None)
            line = ""
            if d:
                line = (f"不做行「{d['item'][:60]}」對到了 {u[:100]}，但只寫了自己的理由：紅測要使用者說了才豁免，寫成"
                        f"「不做｜{d['item'][:60]}：使用者說「<原句>」」，或照 (b)(c) 處理")
            elif not named and e:
                line = (f"帳上有 {u[:100]} 的豁免（使用者說「{str(e.get('quote') or '')[:40]}」），這次收尾沒寫對到它的不做行："
                        f"補一行「不做｜{str(e.get('item') or '')[:60]}：使用者說「{str(e.get('quote') or '')[:40]}」」就放行")
            if line and line not in out:
                out.append(line)
    return out


# ─── BASE_RED_TRACKED_NOT_OWED：改動前基底就紅、有追蹤項的紅測 ───
RULES["BASE_RED_TRACKED_NOT_OWED"] = (
    "改動前的基底 commit 上就紅、而且有追蹤項點名的紅測，不算本回合欠帳：收尾寫「基底紅｜<紅的那支測試名>：<基底 commit> 也紅；"
    "追蹤 <文件路徑>」，紅的每一支都要三件同時成立才留帳放行（Logs/guard-testfail_base_red.jsonl 記哪一支、哪個基底 commit、"
    "哪份追蹤文件）：(1) 本 session 真的在那個 commit 的乾淨工作樹跑過、那次紅的就有這一支（跑紅時記下 HEAD 與已追蹤檔有沒有改動，"
    "state red_run_commits；不從別處推論）；(2) 那個 commit 是現在 HEAD 的祖先、在本 session 開始之前就有（committer 時間；"
    "本 session 做的 merge、rebase、提交都不算）、不在本 session 的提交紀錄裡；(3) 追蹤文件（.md／.txt）"
    "在、本 session 沒改過、內文點名這一支（整詞）。缺一照擋：基底綠、這次紅 → 沒有基底的紅可對，照擋；擋訊息說缺哪一件。"
    "摘要沒逐支列出失敗的不收（看不出基底紅的是不是同一支）；基底那次的指令要只有一段測試，好幾段測試的紅分不出是哪一段的、不記成證據。事實在 handlers/post_tool_use._track_test_result（記）與 "
    "handlers/stop.py 的 TestFailGate 段（查祖先、讀追蹤文件）蒐集。")
_BASE_RED_RE = lazy_re(r"基底紅\s*[｜|]\s*([^：:\n]{1,80}?)\s*[：:]\s*(.+)")
_BASE_SHA_RE = lazy_re(r"(?<![0-9a-fA-F])[0-9a-fA-F]{7,40}(?![0-9a-fA-F])")
_TRACK_REF_RE = lazy_re(r"追蹤\s*[｜|：:]?\s*(?:`([^`\n]+)`|([^\s，。；;、）)｜|]+))")
BASE_RED_DOC_EXTS = (".md", ".txt")


def parse_base_red(text: str) -> List[Dict[str, str]]:
    """收尾文字裡的基底紅行 →[{item, base, tracking, line}]：base＝「追蹤」之前第一個 7～40 位十六進位（小寫；沒有＝空字串），
    tracking＝「追蹤」後面的路徑（反引號包住的可含空白；尾端 :<行號> 拿掉；沒有＝空字串）。"""
    out: List[Dict[str, str]] = []
    for raw in str(text or "").splitlines():
        m = _BASE_RED_RE.search(raw)
        if not m:
            continue
        rest = m.group(2)
        sha = _BASE_SHA_RE.search(rest.split("追蹤", 1)[0])
        trk = _TRACK_REF_RE.search(rest)
        path = re.sub(r":\d+$", "", (trk.group(1) or trk.group(2)).strip()) if trk else ""
        out.append({"item": m.group(1).strip().strip("`"), "base": sha.group(0).lower() if sha else "",
                    "tracking": path, "line": raw.strip()[:240]})
    return out


def listed_red_units(summary: Any) -> List[str]:
    """紅測輸出逐支列出的失敗：pytest 節點，沒有就一行一支的失敗名稱；沒列出回空。跑紅時記基底證據與收尾比對用同一份。"""
    return failed_units(summary) or failure_units(summary)


def _base_red_gap(unit: str, d: Dict[str, str], cwd: str, facts: Dict[str, Any]) -> str:
    """一支紅測對一條基底紅行：三件都成立回空字串，否則回缺的那一件（擋訊息照印）。facts 見 base_red_failures。"""
    base = d["base"]
    if not base:
        return "沒寫基底 commit（7 位以上的雜湊）"
    if not any(r.get("clean") is True and str(r.get("head") or "").lower().startswith(base) and unit in (r.get("units") or ())
               for r in facts.get("runs") or ()):
        return f"本 session 沒在基底 {base} 的乾淨工作樹跑紅過這一支（基底綠、或沒在基底跑過 → 照算本回合的紅）"
    if any(str(s).lower().startswith(base) for s in facts.get("own_shas") or ()):
        return f"基底 {base} 是本 session 自己提交的，不是改動前"
    born, started = (facts.get("base_times") or {}).get(base), facts.get("started")
    if born is None or started is None or born >= started:
        return f"基底 {base} 要早於本 session 開始，這個 commit 沒有（本 session 做的 merge、rebase 之後的 commit 不算；查不到時間也不算）"
    if (facts.get("ancestry") or {}).get((base, cwd)) is not True:
        return f"基底 {base} 不是現在 HEAD 的祖先（或查不到）"
    t = (facts.get("tracking") or {}).get(d["tracking"]) if d["tracking"] else None
    if t is None:
        return "沒寫追蹤文件（「追蹤 <路徑>」）"
    if not t.get("exists"):
        return f"追蹤文件 {d['tracking']} 不存在"
    if not t.get("doc"):
        return f"追蹤文件 {d['tracking']} 不是 {'／'.join(BASE_RED_DOC_EXTS)}（測試檔、程式檔不算追蹤項）"
    if t.get("own_edit"):
        return f"追蹤文件 {d['tracking']} 本 session 改過（追蹤項要是改動前就記下的）"
    if not re.search(rf"(?<!\w){re.escape(d['item'])}(?!\w)", str(t.get("text") or ""), re.IGNORECASE):
        return f"追蹤文件 {d['tracking']} 沒點名 {d['item']}（要整詞出現，test_x_other 不算點名 test_x）"
    return ""


def base_red_failures(failing: Sequence[Dict[str, Any]], decls: Sequence[Dict[str, str]], facts: Dict[str, Any]
                      ) -> Tuple[List[Dict[str, Any]], List[Tuple[Dict[str, Any], List[Dict[str, str]]]], List[str]]:
    """BASE_RED_TRACKED_NOT_OWED 套在紅測清單：回 (還算紅的, [(放行的那筆, 每支一筆 {unit, base, tracking, line})], 擋訊息附註)。
    facts 由呼叫端蒐集：runs＝state red_run_commits（本 session 的）、ancestry[(基底, 那筆紅的 cwd)]＝是不是 HEAD 的祖先、
    own_shas＝本 session 提交過的 commit、base_times[基底]＝committer 時間（epoch 秒，查不到 None）、started＝本 session 開始時間、
    tracking[路徑]＝{exists, doc, own_edit, text}。沒有任何基底紅行對到的紅照原樣留著、不附註。"""
    kept: List[Dict[str, Any]] = []
    based: List[Tuple[Dict[str, Any], List[Dict[str, str]]]] = []
    notes: List[str] = []
    for f in failing:
        units, listed = _waiver_units(f or {})
        named = [(u, next((d for d in decls if names_failed_test(u, d["item"])), None)) for u in units]
        if not any(d for _, d in named):
            kept.append(f)
            continue
        if not listed:
            kept.append(f)
            notes.append("基底紅要逐支列得出是哪一支：這筆紅的輸出沒列 FAILED／ERROR 行，別截斷輸出、單獨重跑一次")
            continue
        cwd = str(f.get("cwd") or "")
        gaps = [(u, _base_red_gap(u, d, cwd, facts) if d else "沒有對到它的基底紅行") for u, d in named]
        bad = [f"基底紅不成立（{u[:100]}）：{g}" for u, g in gaps if g]
        if bad:
            kept.append(f)
            notes += [n for n in bad if n not in notes]
            continue
        based.append((f, [{"unit": u, "base": d["base"], "tracking": d["tracking"], "line": d["line"]} for u, d in named]))
    return kept, based, notes


# ─── 動資料檔 ───
RULES.update({
    "USER_DATA_FILE_NEEDS_DECLARATION": "Edit／Write／NotebookEdit 動到使用者既有的資料檔或設定檔要先問或先宣告。四件事實全成立才管："
                                        "(a) 不是程式檔（wg_need_goal.writes_code 為 False）且副檔名在 guard.data_file_ask.extensions，"
                                        "清單只決定程式要不要把它當資料檔問，該不該改仍是 AI 判；(b) 呼叫前檔已存在；(c) 不是本 session Write 新建的"
                                        "（state created_files）；(d) 本 session 使用者原話都沒點名它（檔名含副檔名完整比對，不做模糊）。"
                                        "成立而且回覆文字／工具呼叫參數裡 # 開頭的註解行／thinking 都找不到「動資料檔｜<路徑>：<為什麼>」"
                                        "（路徑檔名對得上這次要改的檔、冒號後的理由過 reason_present）→ 擋。宣告過記 state data_file_declared，"
                                        "同 session 同檔不再擋；換檔要再宣告。一律留帳 Logs/guard-data_file.jsonl（denied／declared／exempt）。"
                                        "只在寫過程式的 session 管（wg_data_file.coding_session）：state modified_files 沒有任何程式檔、這次指令也沒"
                                        "同時寫程式檔 → 放行、不留宣告帳，只留 skipped_non_coding（純文件／設定的回合不問；使用者裁定）。",
})

_DATA_FILE_DECL_RE = lazy_re(r"動資料檔\s*[｜|]\s*((?:[A-Za-z]:[\\/])?[^：:\n]+?)\s*[：:]\s*([^\n]*)")
_DECL_PATH_TRIM = "`'\"「」『』<>（）() "


def parse_data_file_decls(text: str) -> List[Tuple[str, str, str]]:
    """文字裡每一行宣告「動資料檔｜<路徑>：<為什麼>」→ [(路徑, 為什麼, 那一行)]。路徑可帶磁碟代號（C:\\…）。"""
    return [(m.group(1).strip().strip(_DECL_PATH_TRIM), m.group(2).strip(), m.group(0).strip()[:200])
            for m in _DATA_FILE_DECL_RE.finditer(str(text or ""))]


def decl_names_file(decl_path: str, target: str) -> bool:
    """SAME_FILE 的宣告版：宣告的路徑就是要改的檔，或是它的路徑尾段（`settings.json`、`config/settings.json` 對得到
    `C:\\proj\\config\\settings.json`；`other.json`、`ettings.json` 對不到）。"""
    d = str(decl_path or "").strip().strip(_DECL_PATH_TRIM).replace("\\", "/")
    while d.startswith("./"):
        d = d[2:]
    d = d.rstrip("/").lower()
    if not d:
        return False
    t = canon_path(target)
    return t == d or t.endswith("/" + d) or (os.path.isabs(d) and canon_path(d) == t)


_CJK_CHAR_RE = lazy_re(r"[一-鿿㐀-䶿぀-ヿ가-힯]")
_QUOTED_NAME_RE = lazy_re(r"[「『\"“`]([^「」『』\"“”`\n]+)[」』\"”`]")


def _quoted_other_name(text: str, start: int, end: int, base: str) -> bool:
    """命中處在引號／反引號裡，而引號裡是另一個更長的檔名（「備份設定.json」裡的 設定.json）。"""
    for q in _QUOTED_NAME_RE.finditer(text):
        if q.start(1) <= start and end <= q.end(1):
            name = q.group(1).strip().replace("\\", "/").lower()
            return name != base.lower() and not name.endswith("/" + base.lower())
    return False


# 使用者原話的子句與否定字（口令閘 pre_tool_use._order_negated 與資料檔點名共用）。否定詞表只會多擋不會多放：
# 子句以逗號、句號、分號、問嘆號、換行為界；頓號與「或」不斷，否定會跨列舉
CLAUSE_END_RE = lazy_re(r"[，,。！？!?；;\n]")
NEG_WORD_RE = lazy_re(r"不要|不可以|不能|不行|不用|不必|不准|不許|禁止|先不|先別|(?<![特分類個區識差告性級])別|勿|暫不|暫緩"
                         r"|\b(?:don'?t|do\s+not|not|never|no)\b", re.IGNORECASE)
# 檔名右邊緊接著否定（「shop.json 先不要動」「settings.json 別碰」）
_MENTION_RIGHT_NEG_RE = lazy_re(r"^\s*(?:先|就|也|都|請)?\s*(?:不要|不可以|不能|不用|不必|不准|別|勿|暫不|先不要|先別)")
RULES["DATA_FILE_DECL_VOIDED_BY_LATER_MENTION"] = ("資料檔宣告帳（state data_file_declared）記下宣告當時主 transcript 寫到的位置 at；之後有使用者原話"
                                                   "提到這個檔（否定的也算）→ 舊帳作廢（拿掉、留帳 declared_voided），transcript 裡的宣告也只認"
                                                   "最後一則提到它的原話之後寫的（子代理檔從頭找；這次指令自己的 `#` 註解照認）。後話肯定點名"
                                                   "走點名豁免；後話沒提到這個檔照用舊帳（hooks/wg_data_file）。")
RULES["NEGATED_MENTION_IS_NOT_NAMING"] = ("使用者原話提到資料檔、但那一處被否定（同一子句裡檔名左邊有否定字，或右邊緊接否定："
                                          "「不要放 shop.json」「shop.json 先不要動」）→ 不算點名，照走宣告／問使用者；同一則或別則原話"
                                          "裡另有沒被否定的提及照算點名（prompt_names_file）。")
RULES["DECL_HINT_KEEPS_EDIT_TOOLS"] = ("擋 Edit／Write 要先交宣告行的閘（改資料檔宣告 wg_data_file._judge／data_file_hint、改舊測試宣告 "
                                       "wg_oldtest.hint、定位與最小地圖 wg_overview、立樹 wg_need_goal），擋訊息與提示講清楚宣告放哪，順位固定："
                                       "第一、同一則回覆裡先發一條不寫檔的 Bash／PowerShell 指令、宣告放它開頭的 `#` 註解（DECL_VIA_COMMENT），"
                                       "接著就可以改檔；第二、寫在早一則只有文字的回覆（那一則不呼叫工具，下一則再改檔）。原因要講：同一則裡"
                                       "接著呼叫工具的文字要等那則結束才進 transcript，hook 當下讀不到，寫了白寫。"
                                       "共用句 DECL_WHERE（整句）／DECL_WHERE_SHORT（一行提示用）。並寫明宣告完照常用 "
                                       "Edit／Write 改、不要改用 Bash／PowerShell 寫檔（DECL_KEEP_EDIT：指令寫的檔常判不出目標，"
                                       "modified_files 漏記，對帳、第二意見、同步提醒都看不到）。不准出現「或寫成 Bash 指令開頭的 # 註解」"
                                       "「放在下一條 Bash 的註解」這類會被讀成改用 Bash 寫檔的說法。擋的本來就是那條 Bash 指令的閘"
                                       "（繞閘宣告 wg_gate_bypass）不在此列：宣告寫在那條指令的註解是對的。")
DECL_VIA_COMMENT = "一條不寫檔的 Bash／PowerShell 指令（例如 `git diff --stat`）開頭的 `#` 註解"
# 宣告放哪（規則 DECL_HINT_KEEPS_EDIT_TOOLS 的順位）：先 `#` 註解、其次早一則的回覆文字；同一則裡接著呼叫工具的文字 hook 當下讀不到
DECL_WHERE = (f"同一則回覆裡先發{DECL_VIA_COMMENT}、接著就可以改檔；或寫在早一則只有文字的回覆（那一則不呼叫工具，下一則再改檔；"
              "同一則裡接著呼叫工具的文字，hook 當下讀不到）")
DECL_WHERE_SHORT = f"放在同一則先發的{DECL_VIA_COMMENT}（接著就可以改檔），或早一則只有文字的回覆"
DECL_KEEP_EDIT = ("宣告完照常用 Edit／Write 改，不要改用 Bash／PowerShell 寫檔：指令裡寫的檔 hook 常判不出是哪個，"
                  "改檔紀錄會漏掉，之後對帳、第二意見、同步提醒都看不到這次改動")


def _file_mentions(text: str, base: str) -> Iterable["re.Match"]:
    """原話裡提到這個檔名的每一處：前後不接檔名字元；引號裡是更長的檔名、中日韓檔名前接中日韓字的不算。"""
    rx = re.compile(r"(?<![A-Za-z0-9_.\-])" + re.escape(base) + r"(?![A-Za-z0-9_\-]|\.[A-Za-z0-9])", re.IGNORECASE)
    cjk_head = bool(_CJK_CHAR_RE.match(base))
    for m in rx.finditer(text):
        if _quoted_other_name(text, m.start(), m.end(), base):
            continue
        if cjk_head and m.start() > 0 and _CJK_CHAR_RE.match(text[m.start() - 1]):
            continue
        yield m


def mention_negated(text: str, start: int, end: int) -> bool:
    """NEGATED_MENTION_IS_NOT_NAMING：text[start:end]（檔名）所在子句裡左邊有否定字，或右邊緊接否定。"""
    seps = [m.end() for m in CLAUSE_END_RE.finditer(text, 0, start)]
    return bool(NEG_WORD_RE.search(text[seps[-1] if seps else 0:start]) or _MENTION_RIGHT_NEG_RE.match(text[end:]))


def prompt_mentions_file(prompt: str, target: str) -> bool:
    """這則原話有沒有提到這個檔（否定的也算）：DATA_FILE_DECL_VOIDED_BY_LATER_MENTION 判後話用。"""
    base = Path(str(target)).name
    return bool(base) and any(True for _ in _file_mentions(str(prompt or ""), base))


def prompt_names_file(prompts: Sequence[str], target: str) -> Optional[str]:
    """事實 (d)：使用者原話有沒有點名這個檔，檔名含副檔名完整比對，不分大小寫：前後不接檔名字元（前面可接路徑分隔）；
    引號裡是更長的檔名不算；檔名以中日韓字開頭時前一個字也是中日韓字不算（「備份設定.json」分不出是不是別的檔，寧可多問）；
    被否定的那一處不算（NEGATED_MENTION_IS_NOT_NAMING）。英文檔名前接中文動詞照算（「把settings.json的逗號修掉」）。
    回點名那則原話的片段，沒有回 None。"""
    base = Path(str(target)).name
    if not base:
        return None
    for p in prompts or ():
        text = str(p or "")
        for m in _file_mentions(text, base):
            if not mention_negated(text, m.start(), m.end()):
                return text[max(0, m.start() - 30):m.end() + 30]
    return None


def data_file_hint(rel: str) -> str:
    return (f"入口行範例：動資料檔｜{rel}：<為什麼要動它、動了使用者會看到什麼>\n"
            f"{DECL_WHERE}；也可在 need_goal set 的 data_files 一起交；"
            "宣告完照常用 Edit／Write 改。拿不準要不要動就用 AskUserQuestion 問使用者（附推薦）。")


def data_file_fix(rels: Sequence[str]) -> str:
    """DENY_TEXT_SLIM 的動資料檔修法句，一行：宣告怎麼寫（每個檔一行範例）＋放哪＋宣告完照常用 Edit／Write
    （DECL_HINT_KEEPS_EDIT_TOOLS）。其餘說明（拿不準先問、留帳）在 TECH §7.5 DataFileAsk 與判準卡，不放訊息裡。"""
    lines = "；".join(f"動資料檔｜{r}：<為什麼要動它、動了使用者會看到什麼>" for r in rels)
    return (f"先發一條不寫檔的 Bash／PowerShell 指令、開頭的 `#` 註解寫 {lines}（接著改檔；或早一則只有文字的回覆，或 need_goal set 的 data_files）；"
            "改檔照常用 Edit／Write，不要改用 Bash／PowerShell 寫檔。")


DATA_FILE_HINT_SHOWN = 4      # DATA_FILE_READ_HINT 一行最多列幾個檔名


def data_file_read_hint(rels: Sequence[str], first: bool) -> str:
    """DATA_FILE_READ_HINT：第一次讀到會被 DataFileAsk 管的檔時附的一行（判定不動，沒宣告照擋）；
    first＝這個 session 第一次提示，給格式與管道；之後只點名檔、說格式同前。"""
    names = "、".join(rels[:DATA_FILE_HINT_SHOWN]) + (f" 等 {len(rels)} 個檔" if len(rels) > DATA_FILE_HINT_SHOWN else "")
    if not first:
        return f"[Guardian:DataFileAsk] 改 {names} 也要先宣告（格式同前一則提示）。"
    return (f"[Guardian:DataFileAsk] 改 {names} 前先宣告：動資料檔｜<路徑>：<為什麼要動它、動了使用者會看到什麼>"
            "（放先發的不寫檔指令開頭的 `#` 註解再改檔，或早一則只有文字的回覆，或 need_goal set 的 data_files）。")


def data_file_verdict(target: str, rel: str, facts: Dict[str, Any], decls: Sequence[Tuple[str, str, str]]) -> Verdict:
    """USER_DATA_FILE_NEEDS_DECLARATION：owed＝擋。facts＝{code, ext, ext_listed, existed, created, named, prompts}
    （named＝prompt_names_file 的結果，prompts＝原話則數）；decls＝三管道收到的宣告（parse_data_file_decls）。
    不管的情況回 owed=False，why 寫哪一件事實不成立（留帳 exempt 用）。"""
    rule = "USER_DATA_FILE_NEEDS_DECLARATION"
    ext = facts.get("ext") or "（無副檔名）"
    if facts.get("code") or not facts.get("ext_listed"):
        return Verdict(rule, False, "(a) 不成立：" + ("是程式檔" if facts.get("code") else f"副檔名 {ext} 不在資料／設定清單"))
    if not facts.get("existed"):
        return Verdict(rule, False, "(b) 不成立：呼叫前檔不存在（新建）")
    if facts.get("created"):
        return Verdict(rule, False, "(c) 不成立：本 session 新建的檔")
    if facts.get("named"):
        return Verdict(rule, False, f"(d) 不成立：使用者原話點名了：「{str(facts['named']).strip()[:80]}」")
    base = Path(str(target)).name
    ev = [f"(a) 不是程式檔，副檔名 {ext} 在資料／設定清單",
          "(b) 呼叫前已存在",
          "(c) 這個 session 沒建過它",
          f"(d) 使用者原話（{int(facts.get('prompts') or 0)} 則）找不到「{base}」"]
    hit = [d for d in decls if decl_names_file(d[0], target)]
    for _path, why, line in hit:
        if reason_present(why):
            return Verdict(rule, False, f"AI 宣告動資料檔 {rel}：{why[:120]}", (line,))
    if hit:
        return Verdict(rule, True, f"宣告行冒號後沒有理由（空白、只有標點或角括號佔位）：{rel}", tuple(ev + [hit[-1][2]]))
    if decls:
        named = "、".join(dict.fromkeys(d[0] for d in decls))[:120]
        return Verdict(rule, True, f"宣告行的路徑對不上這次要改的檔：宣告的是 {named}，要改的是 {rel}", tuple(ev))
    return Verdict(rule, True, f"要改使用者既有的資料檔 {rel}，沒先問也沒宣告", tuple(ev))
# ─── origin 核對 ───
# 目標樹子節點標「使用者說的」要對得到原話（wg_need_goal 的 add／update 收事實、這裡判）。只核字面在不在、是誰說的；
# 要不要標、引哪一句由 AI 判（引一句不相干的原話硬掛，程式看不出來：quote 與節點文字並列留帳給人抽查）
RULES.update({
    "ORIGIN_USER_NEEDS_QUOTE": "目標樹子節點標 origin=user（使用者說的）：quote 或節點文字本身（去頭尾空白、不正規化標點）"
                               "要是樹上某則使用者原話（user_said，含匯入的前一個 session 原話）的字面子串，至少 6 字；不到 6 字要是某則原話"
                               "的整句（前後是句首、句末標點或換行，逗號不算句界；去掉句末標點至少 2 個字；引用自帶句末標點時要跟原話"
                               "那個標點一樣）；對不到、或只出現在同伴轉述"
                               "（peer_said）裡 → 強制改 inferred（推出來的）並提醒。樹根與匯入的節點不核。",
    "ORIGIN_SAID_INCLUDES_UNATTACHED": "origin 核對的原話來源包含本 session 還沒掛上任何樹的使用者原話（樹已結束時收的、doc said_log "
                                       "attached=false）：樹對照完結束後使用者再糾正，那則原話要等樹重開才掛回去，而重開排在同一次 update "
                                       "的核對之後；不看它的話逐字引用也會被降成推出來的。",
})
ORIGIN_QUOTE_MIN = 6
_SENTENCE_END = "。！？!?；;\n"
_SENTENCE_TAIL_RE = lazy_re(r"[。！？!?；;\s]+$")


def _said_with(s: str, entries: Sequence[Any]) -> Optional[Dict[str, Any]]:
    return next((e for e in entries or () if isinstance(e, dict) and s in str(e.get("text") or "")), None)


def _said_whole(s: str, entries: Sequence[Any]) -> Optional[Dict[str, Any]]:
    """不到 ORIGIN_QUOTE_MIN 字的引用要是某則原話的整句：去掉尾端句末標點後至少 2 個字，在原話裡左邊是開頭或句末標點、
    右邊是句末標點或結尾（逗號不算句界：「好，」「有測試」這種片段不算）。"""
    core = _SENTENCE_TAIL_RE.sub("", s)
    tail = _WS_RE.sub("", s[len(core):])           # 引用自帶的句末標點要跟原話一樣（「要有測試。」對不到「要有測試？」）
    if len(re.sub(r"[\W_]", "", core)) < 2:
        return None
    for e in entries or ():
        text = str(e.get("text") or "") if isinstance(e, dict) else ""
        at = text.find(core)
        while at >= 0:
            left, right = text[:at].rstrip(" \t"), text[at + len(core):].lstrip(" \t")
            if (not left or left[-1] in _SENTENCE_END) and (right.startswith(tail) if tail else (not right or right[0] in _SENTENCE_END)):
                return e
            at = text.find(core, at + 1)
    return None


def _said_quote(s: str, entries: Sequence[Any]) -> Optional[Dict[str, Any]]:
    """ORIGIN_USER_NEEDS_QUOTE 的比法：至少 6 字比字面子串，不到 6 字比整句。"""
    if not s:
        return None
    return _said_with(s, entries) if len(s) >= ORIGIN_QUOTE_MIN else _said_whole(s, entries)


def origin_user_verdict(text: Any, quote: Any, user_said: Sequence[Any],
                        peer_said: Sequence[Any] = ()) -> Tuple[str, Verdict, Optional[Dict[str, Any]]]:
    """ORIGIN_USER_NEEDS_QUOTE：回 (origin, Verdict, 對上的 {"quote": 對上的字串, "said": 那則原話})；對不到第三項是 None、
    owed＝要降級成 inferred。先核 quote、再核節點文字；兩個都對不到時，原因以 quote（有給的話）為準。"""
    rule = "ORIGIN_USER_NEEDS_QUOTE"
    q = quote.strip() if isinstance(quote, str) else ""
    t = text.strip() if isinstance(text, str) else ""
    for s, how in ((q, "quote"), (t, "節點文字")):
        hit = _said_quote(s, user_said)
        if hit is not None:
            return ("user", Verdict(rule, False, f"{how}對得到第 {hit.get('turn', '?')} 回合的使用者原話", (f"引用：{s[:120]}",)),
                    {"quote": s, "said": hit})
    s = q or t
    peer = _said_quote(s, peer_said)
    if peer is not None:
        why = f"這句是同伴 {peer.get('from') or '?'} 說的，不是使用者"
    elif q and len(q) < ORIGIN_QUOTE_MIN:
        why = f"quote 只有 {len(q)} 字：至少要 {ORIGIN_QUOTE_MIN} 字，或是某則使用者原話的整句"
    elif q:
        why = "quote 不在任何一則使用者原話裡"
    elif len(t) < ORIGIN_QUOTE_MIN:
        why = f"沒給 quote，節點文字只有 {len(t)} 字（不到 {ORIGIN_QUOTE_MIN} 字不拿來比）"
    else:
        why = "沒給 quote，節點文字也不是使用者原話的字面子句"
    return "inferred", Verdict(rule, True, why, (f"節點文字：{t[:120]}", f"quote：{q[:120] or '（沒給）'}")), None


_ROOT_SPLIT_RE = lazy_re("[。；，、]|" + chr(0x2014) * 2)   # 第二支是雙破折號（本檔不准出現破折號字面）


def root_unquoted_sentences(text: Any, user_said: Sequence[Any]) -> List[str]:
    """ORIGIN_USER_NEEDS_QUOTE 的樹根版：樹根依契約是 AI 對原話的解讀（不改 origin）。切句（。；，、雙破折號）後至少 6 字的句子，
    逐句看是不是某則使用者原話的字面子串；回對不到的句子（保序、去重），給提醒列出「這幾句原話裡沒有」。"""
    out: List[str] = []
    for s in _ROOT_SPLIT_RE.split(text if isinstance(text, str) else ""):
        s = s.strip()
        if len(s) >= ORIGIN_QUOTE_MIN and s not in out and _said_with(s, user_said) is None:
            out.append(s)
    return out
# ─── 改舊測試 ───
RULES.update({
    "OLD_TEST_CHANGE_NEEDS_DECLARATION": "Edit／MultiEdit／Write 動到測試檔裡既有的測試函式（消失、改名、同名測試的斷言行被刪或改，只加新斷言不算；"
                                         "新加跳過標記 skip／skipif／xfail／.skip(／[Ignore]／@Disabled；原本有的說明 docstring 被改或刪，"
                                         "只加新說明不算），要先有宣告行"
                                         "「改舊測試｜<函式名或 檔:函式名>：<理由>」（回覆文字／工具參數／thinking 三管道都認；多支以「、」分隔）："
                                         "名字要點到這次抓到的那一支既有測試（改名寫舊的名字；寫了檔名或類別就要對得上那個檔、那個類別），"
                                         "理由要有文字內容、不是擋訊息的角括號佔位；沒有 → 擋（字母 ot）。宣告過的那支與本 session 自己新加的"
                                         "測試記 state，同 session 再動不擋。只加新測試、只改 fixture／helper、只改註解不觸發。改名與消失怎麼標"
                                         "（本體行相似度）只影響證據寫法，放不放行都要宣告點名舊的那支。Bash／PowerShell／NotebookEdit "
                                         "寫之前看不到改後內容：PreToolUse 拍改前快照、PostToolUse 比對，沒宣告的記 state，下一個工具呼叫擋到"
                                         "補宣告（declared_late）或撤回（reverted）為止；只讀、只寫那幾個欠帳檔的呼叫不擋。事實由 wg_oldtest 收，"
                                         "留帳 Logs/guard-old_test.jsonl（denied／declared／exempt／undeclared／denied_late／declared_late／reverted）。",
    "OWN_COMMIT_CHANGES_STILL_COMPARED": "執行 python 的指令在同一條裡自己 commit（commit、amend、revert；合併提交不算）、工作樹又乾淨時，"
                                         "那幾筆 commit 前後有變的測試檔照樣拿執行前的內容比，事後補記的基線取執行前的 HEAD（同指令新加又 commit 的"
                                         "測試仍算本 session 新加）；讀不到 reflog → 整段都比，git diff 失敗 → stderr＋留帳 own_commit_diff_error"
                                         "（wg_oldtest._own_commit_tests）。",
})

OLD_TEST_KIND_LABELS: Dict[str, str] = {"gone": "消失", "renamed": "改名", "assert": "斷言變了", "skip": "加 skip", "doc": "說明變了"}
_OLD_TEST_FILE_RE = lazy_re(r"\.[a-z]{1,5}$")
_OLD_TEST_DECL_RE = lazy_re(r"改舊測試\s*[｜|]\s*(.+)")
_OLD_TEST_ASCII_SEP_RE = lazy_re(r":(?![A-Za-z0-9_\\/:])")
_OLD_TEST_NAME_SPLIT_RE = lazy_re(r"\s*[、，,；;]\s*")
# 一行多支各帶理由（「名1：理由1、名2：理由2」）的每一段開頭：行首或分隔符後面接 ASCII 名字（可帶 檔:、::、/），再接冒號
_OLD_TEST_NAME_LIKE_RE = lazy_re(r"test|::|[._/\\]", re.IGNORECASE)   # 像測試名（不是 ERP、TECH 這種標籤字）
_OLD_TEST_SEG_RE = lazy_re(r"(?:^|[、，,；;])\s*`?(?P<name>[A-Za-z0-9_./\\-]+(?:::?[A-Za-z0-9_.]+)*)`?\s*(?:：|:(?![A-Za-z0-9_\\/:]))")


def parse_old_test_declarations(text: str) -> List[Dict[str, Any]]:
    """宣告行 → [{names, reason, line}]。名字與理由用第一個「：」分；沒有全形冒號才找後面不接識別字的「:」
    （`tests/test_a.py:test_x: 理由` 的第一個冒號屬於名字）。names 是去反引號後的整段與「、，,；;」切開的每一段。
    一行裡出現兩段以上「名字：理由」（「名1：理由1、名2：理由2；名3：理由3」）→ 每段一筆；第一段之前只列名字的
    （「名0、名1：理由1、名2：理由2」的名0）併進第一段。"""
    out: List[Dict[str, Any]] = []
    for raw in str(text or "").splitlines():
        m = _OLD_TEST_DECL_RE.search(raw)
        if not m:
            continue
        rest = m.group(1)
        segs = [s for i, s in enumerate(_OLD_TEST_SEG_RE.finditer(rest))
                if i == 0 or _OLD_TEST_NAME_LIKE_RE.search(s.group("name"))]   # 理由裡的「ERP：」不是新的一段
        if len(segs) >= 2:
            lead = [p.strip("` ") for p in _OLD_TEST_NAME_SPLIT_RE.split(rest[:segs[0].start()]) if p.strip("` ")]
            for i, sg in enumerate(segs):
                end = segs[i + 1].start() if i + 1 < len(segs) else len(rest)
                out.append({"names": (lead if i == 0 else []) + [sg.group("name")],
                            "reason": rest[sg.end():end].strip(" 、，,；;"), "line": raw.strip()[:240]})
            continue
        if "：" in rest:
            names, reason = rest.split("：", 1)
        else:
            sep = _OLD_TEST_ASCII_SEP_RE.search(rest)
            names, reason = (rest[:sep.start()], rest[sep.end():]) if sep else (rest, "")
        names = names.strip().strip("`")
        parts = [p.strip("` ") for p in _OLD_TEST_NAME_SPLIT_RE.split(names) if p.strip("` ")]
        out.append({"names": [names, *parts], "reason": reason.strip(), "line": raw.strip()[:240]})
    return out


def _old_test_name_hits(name: str, key: str, path: str = "") -> bool:
    """宣告的名字點到這支測試（key＝wg_oldtest 的 key：`類別.函式`、`函式`、`describe:<名>`，尾巴 `#2` 拿掉）：
    整個相等；或拆成「檔」與「函式」（`檔:函式`、`檔::類別::函式`，檔＝結尾有副檔名的那段）：寫了檔就要是 path 本身或它的路徑尾段，
    函式寫了類別（`類別.函式`）就要整段對上，只寫函式名比最後一段。不分大小寫。"""
    n = str(name or "").strip().replace("\\", "/").lower()
    k = re.sub(r"#\d+$", "", str(key or "").strip().lower())
    if not n or not k:
        return False
    if n == k or (k.startswith(("describe:", "context:")) and n == k.split(":", 1)[1]):
        return True
    file_part, func = "", n.replace("::", ".")
    if "::" in n and _OLD_TEST_FILE_RE.search(n.split("::", 1)[0]):
        file_part, func = n.split("::", 1)[0], n.split("::", 1)[1].replace("::", ".")
    elif "::" not in n and ":" in n and _OLD_TEST_FILE_RE.search(n.rsplit(":", 1)[0]):
        file_part, func = n.rsplit(":", 1)
    if file_part:
        p, f = canon_path(path) if path else "", file_part.lstrip("./")
        if not p or not (p == f or p.endswith("/" + f)):
            return False
    if "." in func:
        return k == func or k.endswith("." + func)
    return func == k.rsplit(".", 1)[-1]


def old_test_declaration_for(change: Dict[str, str], decls: Sequence[Dict[str, Any]], path: str = "") -> Optional[Dict[str, Any]]:
    """這一筆動作有沒有合格的宣告行：名字點到那支既有測試（改名看舊名；新名不能替舊的那支宣告），理由有文字內容、不是佔位。"""
    for d in decls:
        if reason_present(d.get("reason", "")) and any(_old_test_name_hits(n, change.get("key", ""), path) for n in d["names"]):
            return d
    return None


def old_test_change_verdict(path: str, changes: Sequence[Dict[str, str]], decls: Sequence[Dict[str, Any]]) -> Verdict:
    """OLD_TEST_CHANGE_NEEDS_DECLARATION：owed＝有動到既有測試、而那一支沒有合格的宣告行。changes 來自 wg_oldtest.diff_tests；
    decls 來自 parse_old_test_declarations。"""
    rule = "OLD_TEST_CHANGE_NEEDS_DECLARATION"
    owed = [c for c in changes if old_test_declaration_for(c, decls, path) is None]
    if not owed:
        return Verdict(rule, False, "動到的每一支既有測試都有宣告行" if changes else "沒動到既有測試")
    name = _base_name(path)
    ev = []
    for c in owed:
        label = OLD_TEST_KIND_LABELS.get(c["kind"], c["kind"])
        tail = f" → {c['new_key']}" if c.get("new_key") else (f"：{c['detail']}" if c.get("detail") else "")
        ev.append(f"{name}：{c['key']}（{label}{tail}）")
    ev += [f"宣告行沒附理由（或只有佔位）：{d['line']}" for d in decls if not reason_present(d.get("reason", ""))][:2]
    n = len({c["key"] for c in owed})
    return Verdict(rule, True, f"動到 {n} 支既有測試，沒先宣告「改舊測試｜哪支：理由」", tuple(ev))
# ─── 閘小修 006 追蹤帳本同一件 ───
RULES.update({
    "TRACKING_SAME_ITEM_NOT_REWRITTEN": "追蹤帳本唯一寫入口 wg_harvest.append_tracking：open 列寫進去前，對帳上（含同一批較早的列）部位相容"
                                        "（相同或一邊沒寫）的未結項：① AI 在那行寫了「｜同追蹤項：<那筆裡連續至少 8 字>」（k 欄、need_goal followup "
                                        "行尾；PickOne 多一行「同追蹤項：」）而去標點空白後恰好是一筆的一段 → 換成新說法（新列帶 supersedes、"
                                        "同時寫結案列關掉舊的）；對不到或對到多筆 → 不合併、照記、stderr。② 沒宣告但跟某筆部位相同（嚴格相等）、原文相同"
                                        "（不分 session）→ 不重記、stderr，PickOne 記 repeat；字面相近（只差括號註、開頭相同）程式不併，併錯會吞掉一件。"
                                        "換句話說的同一件程式不判，交 ①；"
                                        "PickOne 問句列出本 session 還開著的項目。",
})
# ─── 改判準卡留帳 ───
RULES.update({
    "JUDGE_CARD_CHANGE_NEEDS_DECLARATION": "要改的檔是綁了 Entry 的判準卡（memory／_atoms 目錄底下的 .md，磁碟上那份檔頭 metadata 的 `- Entry:` "
                                           "非空，判定只用 lib/atom_locations.entry_bound_ids）＝判 AI 做得對不對的量尺：要先有宣告行"
                                           "「改判準卡｜<卡名>：<理由>」（回覆文字／工具參數裡 `#` 開頭的註解行／thinking 三管道，主檔與子代理檔都找；"
                                           "Bash／PowerShell 另認這次指令自己的 `#` 註解行）；卡名＝檔名去 .md（寫路徑也行，取最後一段比；只寫 Entry 代號不算），"
                                           "多張以「、，,」分隔；理由要有文字內容、不是佔位；有沒有宣告都放行，只記錄不擋。出口：Edit／MultiEdit／Write、"
                                           "Bash／PowerShell 的寫入目標、MCP atom_write 的 append／replace、atom_edit_meta、atom_retire（MCP 由 PreToolUse "
                                           "matcher 掛工具名、Python 判，MCP 端照 locate_atom 同一份定位）。不分 session，每個 session 都一樣。"
                                           "每次改動都留帳 Logs/guard-judge_card.jsonl（卡名、entry、宣告行、session、allowed）；"
                                           "事實由 hooks/wg_judge_card.py 收。沒綁 Entry 的卡、新建的卡不觸發。",
    "JUDGE_CARD_HASH_CATCHES_INTERPRETER": "直譯器自己開檔寫卡（Bash／PowerShell 跑 python／node／perl…，寫入目標解析不到）：不記雜湊、"
                                           "不事後比對、不擋；改到綁 Entry 的判準卡最多留一筆帳（guard-judge_card），寫入目標解析得到的照 "
                                           "JUDGE_CARD_CHANGE_NEEDS_DECLARATION 留帳。送法 remind（RULE_MODE）：本來就只留帳不擋，標 mode 不改行為。",
})
_JUDGE_CARD_DECL_RE = lazy_re(r"改判準卡\s*[｜|]\s*(.+)")
_JUDGE_CARD_ASCII_SEP_RE = lazy_re(r":(?![\\/])")   # 「C:\…」「C:/…」的冒號屬於路徑
_JUDGE_CARD_NAME_SPLIT_RE = lazy_re(r"\s*[、，,]\s*")


def parse_judge_card_decls(text: str) -> List[Dict[str, Any]]:
    """宣告行 →[{names, reason, line}]。卡名與理由用第一個「：」分；沒有全形冒號才找不接路徑分隔的「:」。
    names 是「、，,」切開的每一段（去反引號、引號、書名號）。"""
    out: List[Dict[str, Any]] = []
    for raw in str(text or "").splitlines():
        m = _JUDGE_CARD_DECL_RE.search(raw)
        if not m:
            continue
        rest = m.group(1)
        if "：" in rest:
            names, reason = rest.split("：", 1)
        else:
            sep = _JUDGE_CARD_ASCII_SEP_RE.search(rest)
            names, reason = (rest[:sep.start()], rest[sep.end():]) if sep else (rest, "")
        parts = [p.strip("`'\"「」『』 ") for p in _JUDGE_CARD_NAME_SPLIT_RE.split(names)]
        out.append({"names": [p for p in parts if p], "reason": reason.strip(), "line": raw.strip()[:240]})
    return out


def judge_card_name_hits(name: str, stem: str) -> bool:
    """宣告的卡名點到這張卡（stem＝檔名去 .md）：取路徑最後一段、去 .md 後與 stem 相同，不分大小寫。
    擋訊息印的就是 stem，照抄一定對得上；只寫 Entry 代號（E29）不算，因為一個 Entry 綁好幾張卡，要點名是哪一張。"""
    n = str(name or "").strip().replace("\\", "/").rsplit("/", 1)[-1].lower()
    n = n[:-3] if n.endswith(".md") else n
    return bool(n) and n == str(stem or "").lower()


def judge_card_verdict(stem: str, entry: Sequence[str], decls: Sequence[Dict[str, Any]]) -> Verdict:
    """JUDGE_CARD_CHANGE_NEEDS_DECLARATION：owed＝要改的是綁 Entry 的卡、而且沒有點到它又附理由的宣告行。
    entry 來自 entry_bound_ids（空＝不是判準卡）；decls 來自 parse_judge_card_decls。放行時證據第一筆是那一行宣告。"""
    rule = "JUDGE_CARD_CHANGE_NEEDS_DECLARATION"
    if not entry:
        return Verdict(rule, False, f"{stem} 沒綁 Entry，不是判準卡")
    for d in decls:
        if reason_present(d.get("reason", "")) and any(judge_card_name_hits(n, stem) for n in d["names"]):
            return Verdict(rule, False, f"宣告過改判準卡 {stem}", (d["line"],))
    ev = [f"{stem}：綁 Entry {'、'.join(entry)}"]
    ev += [f"宣告行沒附理由（或只有佔位）：{d['line']}" for d in decls
           if any(judge_card_name_hits(n, stem) for n in d["names"]) and not reason_present(d.get("reason", ""))][:2]
    return Verdict(rule, True, "要改綁了 Entry 的判準卡，沒先宣告「改判準卡｜哪張：理由」", tuple(ev))


# ─── 繞閘嫌疑 ───
RULES.update({
    "GATE_BYPASS_NEEDS_DECLARATION": "被病形閘擋過之後（state smell_deny_last；同一個 repo 根、還沒成功 commit），這條指令把被點名的檔"
                                     "移出暫存（git restore --staged／reset／rm --cached／stash、svn revert／changelist）、commit 的提交範圍"
                                     "排除了它、或 commit 帶 --no-verify／core.hooksPath，而它重掃仍帶同一條病 → 要有一行「不是繞閘｜<理由>」"
                                     "（這條指令裡、或擋下之後的回覆文字／工具參數／thinking）；沒有就擋，有就放行並留帳"
                                     "（guard-gate_bypass.jsonl declared，含理由全文）、同一組被點名的檔不再問。重掃無病＝病修掉了，清帳不問。"
                                     "是不是繞閘 AI 判，程式只核對序列事實與宣告行在不在；事實由 hooks/wg_gate_bypass.py 收。",
    "ATOM_BYPASS_HOWTO_REFUSED": "atom 內容同時 ① 提到 Guardian 的閘（[Guardian: 標籤、SmellGate／病形閘／隱私閘／PrivacyGate／CommitOrder／"
                                 "NeedGoal、本表規則名）② 含改暫存區或改提交範圍的做法字樣（guard.gate_bypass.staging_words）→ 拒寫："
                                 "閘誤擋要修判定（加規則＋紅案例），不寫繞法。只命中一個不拒（記閘的機制、記 git 指令用法照寫）。"
                                 "AI 判斷這張卡不是在教繞法（寫的是禁止怎麼繞、在分析誤擋）→ 知識段第一行寫「不是教繞閘｜<理由>」，"
                                 "理由有文字內容、不是佔位就寫入並留帳（guard-gate_bypass.jsonl atom_declared）；程式不評理由。"
                                 "入口 tools/memory-write-gate.py 與 lib/atom_io.write_atom；事實由 hooks/wg_gate_bypass.py 收。",
})


def gate_bypass_verdict(denied: str, facts: Sequence[str], reason: str = "") -> Verdict:
    """GATE_BYPASS_NEEDS_DECLARATION：denied＝上次擋的檔與病一行；facts＝這條指令動到／排除了哪些檔（空＝不是嫌疑）；
    reason＝宣告行「不是繞閘｜」後面的理由（沒有＝空字串）。"""
    if not facts:
        return Verdict("GATE_BYPASS_NEEDS_DECLARATION", False, "這條指令沒有動到上次被擋的檔", ())
    if reason_present(reason):
        return Verdict("GATE_BYPASS_NEEDS_DECLARATION", False, f"AI 宣告不是繞閘：{reason[:160]}", (denied, *facts))
    return Verdict("GATE_BYPASS_NEEDS_DECLARATION", True, "被病形閘擋過之後，這條指令可能讓同一批內容繞過閘，沒有宣告",
                   (f"上次擋：{denied}", "這條指令：" + "；".join(facts)))


def atom_bypass_verdict(gates: Sequence[str], words: Sequence[str], reason: str = "") -> Verdict:
    """ATOM_BYPASS_HOWTO_REFUSED：gates＝內容提到的 Guardian 閘、words＝命中的做法字樣；兩個都有才拒。
    reason＝知識段第一行「不是教繞閘｜」後面的理由：有文字內容、不是佔位 → 放行（AI 判過不是在教繞法）。"""
    if gates and words and reason_present(reason):
        return Verdict("ATOM_BYPASS_HOWTO_REFUSED", False, f"AI 宣告不是教繞閘：{reason[:160]}",
                       (f"提到的閘：{'、'.join(gates)}", f"做法字樣：{'、'.join(words)}"))
    if gates and words:
        return Verdict("ATOM_BYPASS_HOWTO_REFUSED", True, f"這張卡在教怎麼繞 {'、'.join(gates[:4])}",
                       (f"提到的閘：{'、'.join(gates)}", f"做法字樣：{'、'.join(words)}"))
    return Verdict("ATOM_BYPASS_HOWTO_REFUSED", False, "只命中一個訊號（或都沒有），照寫",
                   (f"提到的閘：{'、'.join(gates) or '無'}", f"做法字樣：{'、'.join(words) or '無'}"))
# ─── G14 最小地圖 ───
# 沒有部位表的專案第一次改程式檔前要 AI 先寫出跟需求相關的最小地圖（wg_overview._unmapped_edit 收事實、這裡判）
RULES.update({
    "UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP": "往上找不到任何部位表的專案，本 session 第一次改某頂層目錄的程式檔前（state 鍵 <根>|(unmapped)<頂層目錄>"
                                         " 為單位），要交最小地圖三行「地圖｜讀了：<檔清單>」「地圖｜上游：…」「地圖｜下游：…」"
                                         "（回覆文字、工具參數、thinking 三管道都認，取最後一組三行齊的）：讀了至少列 1 個檔、每個都是"
                                         "本 session 讀過的（與 part_files_read 同源）；上下游非空，真的沒有寫「無，因為…」；留著範例角括號"
                                         "佔位當沒填。只看有沒有、讀過沒，不評內容；交過同鍵不再擋，同根下一個頂層目錄只認之後交的地圖。"
                                         "執行期資料、知識類、非程式檔、有部位表的專案不查；min_map.enabled=false 整條不觸發。",
})

MIN_MAP_KEYS = ("讀了", "上游", "下游")
MIN_MAP_RE = lazy_re(   # 行首可帶 # 或 // 註解符號（三行放在 Bash 參數裡時）；值可空（空的要點名擋）
    r"^[ \t]*(?:#+[ \t]*|//[ \t]*)?地圖[ \t]*[｜|][ \t]*(讀了|上游|下游)[ \t]*[:：][ \t]*(.*?)[ \t]*[\"']?,?$", re.MULTILINE
)
_MAP_NOTE_RE = lazy_re(r"[（(][^（）()\n]*[）)]")        # 檔名後的括號附註（入口、主程式）不當檔名
_MAP_SPLIT_RE = lazy_re(r"[、，,；;\s]+")
_MAP_TOKEN_TRIM = "`'\"「」『』"
_MAP_UNREAD_SHOWN = 5


def min_map_group(text: str) -> Optional[Dict[str, str]]:
    """text 裡的最小地圖：每遇「讀了」行開一組；回最後一組三行齊的（被擋後補交的那組才是現行），都不齊回最後一組，沒有地圖行回 None。"""
    groups: List[Dict[str, str]] = []
    for m in MIN_MAP_RE.finditer(text or ""):
        if m.group(1) == "讀了" or not groups:
            groups.append({})
        groups[-1][m.group(1)] = m.group(2).strip()
    complete = [g for g in groups if all(k in g for k in MIN_MAP_KEYS)]
    if complete:
        return complete[-1]
    return groups[-1] if groups else None


def min_map_files(value: str) -> List[str]:
    """「讀了」那行的檔清單：先去掉括號附註，再以「、，,；;」與空白切開，剝反引號與引號。"""
    out: List[str] = []
    for tok in _MAP_SPLIT_RE.split(_MAP_NOTE_RE.sub(" ", value or "")):
        tok = tok.strip(_MAP_TOKEN_TRIM)
        if tok:
            out.append(tok)
    return out


def _map_line_problem(key: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return f"缺「地圖｜{key}」那行"
    if not value.strip():
        return f"「地圖｜{key}」是空的" + ("" if key == "讀了" else "（真的沒有就寫「無，因為…」）")
    if _EXAMPLE_PLACEHOLDER_RE.search(value):
        return f"「地圖｜{key}」還留著範例的角括號佔位（<…>）"
    if key != "讀了" and _SAME_NONE_RE.match(value) and not _REASON_RE.search(value):
        return f"「地圖｜{key}」寫了無但沒附理由（寫「無，因為…」）"
    return None


def min_map_verdict(group: Optional[Dict[str, str]], root: str, read: Iterable[str], transcript_problem: str = "") -> Verdict:
    """UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP：group＝min_map_group 的結果；root＝專案根（「讀了」的相對路徑以它為基準）；
    read＝本 session 讀過的檔（canon_path 或原樣皆可）；transcript_problem＝transcript 讀不到時的原因（放進證據）。"""
    rule = "UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP"
    if group is None:
        ev = transcript_problem or "回覆文字、工具參數、thinking 都找不到「地圖｜讀了：」那行"
        return Verdict(rule, True, "還沒交最小地圖三行（讀了／上游／下游）", (ev,))
    problems = [p for p in (_map_line_problem(k, group.get(k)) for k in MIN_MAP_KEYS) if p]
    files = [] if _map_line_problem("讀了", group.get("讀了")) else min_map_files(group["讀了"])
    if not files and not _map_line_problem("讀了", group.get("讀了")):
        problems.append("「地圖｜讀了」沒列任何檔")
    seen = {canon_path(p) for p in read}
    unread = [f for f in files if canon_path(os.path.join(root, f)) not in seen]
    if unread:
        shown = "、".join(unread[:_MAP_UNREAD_SHOWN]) + (f" 等 {len(unread)} 個" if len(unread) > _MAP_UNREAD_SHOWN else "")
        problems.append(f"「地圖｜讀了」列的 {shown} 本 session 沒讀過（先讀再列，或從清單拿掉）")
    if problems:
        return Verdict(rule, True, "最小地圖不完整", tuple(problems))
    return Verdict(rule, False, f"最小地圖三行齊，讀了列的 {len(files)} 個檔本 session 都讀過", tuple(files))
# ─── G11 拐彎判斷（程式只算側面數據、只核對五欄齊；這一層有沒有作用、會不會讓人拐超過三個彎由 AI 判並寫理由。事實由 wg_reading_path 收，這裡判結構） ───
RULES.update({
    "TURN_JUDGMENT_REQUIRED": "收尾附的側面數據（入口拐彎數、函式巢狀深度、各自巢狀的條件區塊數、連續轉手鏈、繼承鏈層數與空層）到了"
                              " reading_path.turn_judgment 的門檻（預設 拐彎 ≥2／巢狀 ≥3／條件塊 ≥2／轉手鏈 ≥2／繼承 ≥3 層或有空層；"
                              "這是「從第幾個彎起要人看」的事實門檻，不是判臭）的每一條，收尾文字都要有一行"
                              "「拐彎判斷｜<函式、類別或入口>｜<這一層／這個彎存在的理由與有沒有作用>｜<理由>｜<怎麼改直／合理，因為…>」"
                              "五欄齊（「不會」「這一層沒有作用」都要理由）；缺 → 每個使用者回合擋一次並列缺的那幾條與填好名字的範例行；"
                              "齊 → 放行、guard-reading_path.jsonl 記 judged。程式不評內容；量不出（不可評級、不支援的語言）只列不問；"
                              "一批最多問 max_items 條（預設 8，到門檻的優先、其餘報個數不問）；對象欄只認整名或邊界結尾，不認子字串；"
                              "Markdown 引言與圍欄程式碼裡的行不算回答。答過的條目記名字＋內容指紋，同名同指紋不再問；"
                              "量完前又改碼的舊條目只收答案、不擋；每個使用者回合最多擋一次。",
})

JUDGMENT_LABEL = "拐彎判斷"
JUDGMENT_COLUMNS = ("對象（函式、類別或入口）", "這一層／這個彎存在的理由、有沒有真正的作用（不會／會：第 N 個彎在…／這一層沒有作用，因為…）",
                    "理由", "怎麼改直／合理，因為…")
JUDGMENT_EXAMPLE = "拐彎判斷｜{name}｜<不會／會：第 N 個彎在…／這一層沒有作用，因為…>｜<理由>｜<怎麼改直／合理，因為…>"
# 行首（可帶清單記號）才算回答：Markdown 引言（> …）與圍欄程式碼裡引用上一版的行不算
_JUDGMENT_RE = lazy_re(r"^\s*(?:[-*•]\s*|\d+[.)]\s*)?拐彎判斷\s*[｜|]\s*(.+)")
_FENCE_RE = lazy_re(r"^\s*(```|~~~)")
_COL_SPLIT_RE = lazy_re(r"\s*[｜|]\s*")
_NAME_BOUNDARY = ("::", ".", "/", "\\", "→")


def parse_turn_judgments(text: str) -> List[Dict[str, Any]]:
    """收尾文字裡的拐彎判斷行 → [{target, verdict, reason, fix, missing: [缺的欄名], line}]。五欄用｜隔開；超過五段的尾段併回最後一欄。
    只查每欄有沒有填（有文字、不是擋訊息範例的角括號佔位），不評內容。"""
    out: List[Dict[str, Any]] = []
    fenced = False
    for raw in str(text or "").splitlines():
        if _FENCE_RE.match(raw):
            fenced = not fenced
            continue
        m = None if fenced else _JUDGMENT_RE.match(raw)
        if not m:
            continue
        parts = [p.strip() for p in _COL_SPLIT_RE.split(m.group(1))]
        if len(parts) > 4:
            parts = parts[:3] + ["｜".join(parts[3:])]
        parts += [""] * (4 - len(parts))
        target, verdict, reason, fix = parts
        filled = (reason_present(target), reason_present(verdict), reason_present(reason), reason_present(fix))
        out.append({"target": target, "verdict": verdict, "reason": reason, "fix": fix,
                    "missing": [col for col, ok in zip(JUDGMENT_COLUMNS, filled) if not ok], "line": raw.strip()[:240]})
    return out


def judgment_names(target: str, keys: Sequence[str]) -> bool:
    """判斷行的對象欄指得到這一條數據：對象（去空白、不分大小寫）等於某個鍵，或以「<邊界>鍵」結尾（邊界＝::、.、/、\\、→，
    例：hooks/y.py::b 對 y.py::b、Cls.m 對 m）。不做子字串比對：y.py::load_config 對不到 y.py::load。
    鍵＝函式限定名、檔::名、入口與落點的寫法；同名不同檔的短名會同時對到（程式只核對結構，不猜是哪個）。"""
    t = _nows(target)
    if len(t) < 2:
        return False
    for k in keys or ():
        kn = _nows(k)
        if len(kn) >= 2 and (t == kn or any(t.endswith(b + kn) for b in _NAME_BOUNDARY)):
            return True
    return False


def turn_judgment_verdict(items: Sequence[Dict[str, Any]], judgments: Sequence[Dict[str, Any]]) -> Verdict:
    """TURN_JUDGMENT_REQUIRED：items＝到門檻的數據 [{kind, name, keys, nums}]；judgments＝parse_turn_judgments 的結果。
    owed＝有任一條沒有五欄齊的對應行。evidence：缺的每條「<kind> <name>｜<nums>」；對到但缺欄的行另列缺哪幾欄。"""
    missing: List[str] = []
    partial: List[str] = []
    covered: List[str] = []
    for it in items:
        hits = [j for j in judgments if judgment_names(j["target"], it.get("keys") or [it["name"]])]
        if any(not j["missing"] for j in hits):
            covered.append(f"{it['kind']} {it['name']}")
            continue
        missing.append(f"{it['kind']} {it['name']}｜{it.get('nums', '')}")
        partial += [f"「{j['line'][:120]}」缺「{'」「'.join(j['missing'])}」欄" for j in hits]
    if not missing:
        return Verdict("TURN_JUDGMENT_REQUIRED", False, f"到門檻的 {len(items)} 條都有五欄齊的拐彎判斷行", tuple(covered))
    return Verdict("TURN_JUDGMENT_REQUIRED", True,
                   f"側面數據到門檻的 {len(items)} 條裡 {len(missing)} 條沒有五欄齊的「拐彎判斷｜」行（程式只核對五欄，不評內容）",
                   tuple(missing + partial))
# ─── G9 第二意見 ───
# 事實由 hooks/wg_second_opinion.py 收（本回合 transcript 的 start／result、git numstat、高風險部位），閘在 handlers/stop.py 的
# SecondOpinion 段；material 端（tools/second-opinion/pack.py）引用 SO_QUESTION_ROOT_MISSING 當 blocked 原因的開頭。
RULES.update({
    "SECOND_OPINION_REQUIRED": "收尾時（看事實不看措辭，中途問使用者與寫明還在等的不算：SECOND_OPINION_FACT_TRIGGER），本 session 改過的程式檔（寫碼類判準）達大任務門檻（檔數 ≥ second_opinion.auto.min_code_files，"
                               "或對 HEAD 的程式改動行數 ≥ min_changed_lines：git diff --numstat HEAD，未追蹤的新檔算整檔行數，查不到 git "
                               "只看檔數）或路徑命中高風險部位（部位表該列類別是 gate，或 config 另列的 risky_prefixes，預設空），而且上次審過"
                               "（滿足、使用者放行，或前面回合跑完的第二意見：SECOND_OPINION_RAN_BEFORE）之後的修改改到新的高風險檔、或新改的程式檔數"
                               "再過門檻（SECOND_OPINION_ONCE_PER_CLAIM）→ 本回合（TURN_SINCE_USER_PROMPT）要真的跑過第二意見：second_opinion_start"
                               "（mode=independent，kind=stage-review 或 evaluate）由 second_opinion_result 回 done／failed／blocked（start 在前面"
                               "回合、本回合才取回也算：SECOND_OPINION_RESULT_ACROSS_TURNS；running、"
                               "只 start 沒取結果、start 沒開出 job、question 沒含樹根被擋、session 有樹而材料沒帶到樹都不算，還在跑時收尾寫明在等的"
                               " job_id 不算宣告完成：SECOND_OPINION_WAITING_NOT_DONE），而且本回合任一則回覆"
                               "有「第二意見與分歧裁決」段與四行（被別的閘擋下後補件那則不必重抄；行首、程式碼區塊外；Codex 結論／我方結論／分歧點／裁決與理由，標籤後要有字）。門檻是事實核對；"
                               "程式只核對有沒有跑、標籤在不在，不評內容。擋 max_blocks_per_turn 次（預設 1）後擋滿，不自行放行、改問使用者"
                               "（wg_release）；子代理、裁判 session、headless 不觸發；前面的閘擋下時列進 BLOCK_LISTS_LATER_GATES 預覽。",
    "SECOND_OPINION_RAN_BEFORE": "本回合跑完第二意見（result 回 done／failed／blocked）就記下 job、回合與那時改過的高風險檔，不管有沒有"
                                 "宣告完成；之後的回合宣告完成時，把它當成上次審過的基準：之後沒再改程式、或之後的修改沒改到新的高風險檔、"
                                 "新改的程式檔數也沒再過門檻 → 不再要第二意見，也不再要四行（判的是跑完之後有沒有再改程式，不是有沒有換回合）。",
    "SECOND_OPINION_DECLINED": "收尾寫一行「不需第二意見｜<理由>」→ 不擋、留帳 Logs/guard-second_opinion.jsonl（event=declined、理由、"
                               "程式檔數），週健檢列筆數與理由（只列不判）；理由空、只有佔位、或只寫「不需要」這類空話 → 照擋。",
    "SECOND_OPINION_DECLARED_ALWAYS_LOGGED": "收尾最後一則有「不需第二意見｜<理由>」（行首、程式碼區塊外、理由過 second_opinion_decline_ok）"
                                             "就留帳 event=declined，不管第二意見閘這回合要不要、前面的閘有沒有先擋下；needed 記閘當下"
                                             "要不要第二意見（null＝設定關或無法互動沒判）。同一個使用者回合同一句理由只記一筆（被擋後重寫"
                                             "同一句不重記）。",
    "SECOND_OPINION_DECLINE_ACCEPTED": "宣告行只看收尾最後一則（跟 SECOND_OPINION_DECLARED_ALWAYS_LOGGED 留帳的是同一則）：理由成立就判"
                                       "SECOND_OPINION_DECLINED 不擋，也不走擋滿那條路。四行可以寫在本回合較早那則（section_text 往前找），"
                                       "但不能拿那則蓋掉收尾的宣告行。",
    "SECOND_OPINION_RESULT_ACROSS_TURNS": "本回合 second_opinion_result 回 done／failed／blocked 就算本回合跑過、記 SECOND_OPINION_RAN_BEFORE"
                                          "的基準，不管 start 在哪一回合。start 不在本回合時照 result 自己帶的判：mode 行要是 independent、"
                                          "job_id 的類別要是 stage-review／evaluate、note 行（材料有沒有帶到樹）同 start；沒有 mode 行"
                                          "（找不到 job）不列、不算；job_id 裡的 session 前 8 碼不是本 session → foreign 不算；開 job 之後"
                                          "（job_id 開頭的時間）本 session 又改過程式檔 → 沒審到後來的改動，判 stale 不算（這兩項在 "
                                          "wg_second_opinion.check 判）。前面回合已記成基準的 job，這一回合再取一次結果"
                                          "仍是前面回合的基準。",
    "SECOND_OPINION_WAITING_NOT_DONE": "本回合開出（或本回合才取結果）的 job 還在跑（result 回 running，或 start 了還沒取結果），收尾最後一則"
                                       "有一行「等第二意見｜<job_id>」（行首、程式碼區塊外、完整的那個 job_id，後面不接 job_id 用的字元）"
                                       " → 這次結束回覆不算宣告完成：不擋、不吃擋次、不算滿足，留帳 event=waiting；"
                                       "之後取到 done／failed／blocked 再照 SECOND_OPINION_REQUIRED 判（回合中背景通知叫回來、或下一回合"
                                       "取回都算：SECOND_OPINION_RESULT_ACROSS_TURNS）。沒有這行（散文裡提到 job_id 不算）→ 照擋。second_opinion_result "
                                       "本身會等到有結果（每次最多 second-opinion.js RESULT_WAIT_MS，低於 Claude Code 互動模式 MCP 呼叫"
                                       "120 s 轉背景），所以通常用不到這條。",
})

SO_SECTION = "第二意見與分歧裁決"
SO_LABELS: Tuple[str, ...] = ("Codex 結論", "我方結論", "分歧點", "裁決與理由")
SO_KINDS: Tuple[str, ...] = ("stage-review", "evaluate")
SO_RAN: Tuple[str, ...] = ("done", "failed", "blocked")
SO_QUESTION_ROOT_MISSING = "question 沒含需求目標樹的樹根那句"
SO_NO_GOAL_NOTE = "材料沒有需求目標樹"      # pack 的 note 開頭（start 回傳的 `note:` 行）；session 有樹時這種 run 不算跑過
SO_WAIT_LINE = "等第二意見｜<job_id>"
SO_RESULT_WAITS = ("start 後直接呼叫 second_opinion_result，它會等到有結果（回 running 就再呼叫一次），不用另開背景等待；"
                   f"要先結束回覆就在收尾寫一行 `{SO_WAIT_LINE}`，那次不算宣告完成")
SO_WAITING = "SECOND_OPINION_WAITING_NOT_DONE"
_SO_JOB_KIND_RE = lazy_re(r"-(diagnose|evaluate|stage-review)$")     # job_id 尾的類別（second-opinion.js JOB_ID_RE）
# 等待宣告行：行首（可帶空白、清單符號）、程式碼區塊外，｜後是完整 job_id（後面不能再接 job_id 用的字元）
_SO_WAIT_RE = lazy_re(r"^[\s*\-]*等第二意見(?:\*\*)?\s*[｜|]\s*`?(\d{8}-\d{6}-[0-9a-z]{8}-(?:diagnose|evaluate|stage-review))"
                      r"(?![0-9A-Za-z_-])")
# 宣告行與四行只認行首（可帶空白、清單符號、粗體）、不在程式碼區塊裡：散文裡引用的範例、引用區塊（>）不算
_SO_DECLINE_RE = lazy_re(r"^[\s*\-]*不需第二意見(?:\*\*)?\s*[｜|]\s*(.*)$")
_SO_FENCE_RE = lazy_re(r"^\s*(?:```|~~~)")
_SO_EMPTY_REASONS = frozenset({"不需要", "不需", "不用", "沒必要", "不必", "無", "略", "沒有", "na", "none"})


def _so_label_re(label: str) -> "re.Pattern[str]":
    return re.compile(rf"^[\s*\-#]*(?:\*\*)?{re.escape(label)}(?:\*\*)?\s*[：:｜|]\s*(.*)$")


_SO_LABEL_RES = tuple((lb, _so_label_re(lb)) for lb in SO_LABELS)


def _so_lines(text: str) -> List[str]:
    """收尾文字裡不在程式碼區塊（``` 或 ~~~ 圍起來）的行。"""
    out: List[str] = []
    fenced = False
    for ln in str(text or "").splitlines():
        if _SO_FENCE_RE.match(ln):
            fenced = not fenced
            continue
        if not fenced:
            out.append(ln)
    return out


def second_opinion_hint() -> str:
    """擋訊息末尾的入口（G6 樣式：擋的同時告訴 AI 入口在哪）。"""
    return (f"跑完在收尾最後一則寫「{SO_SECTION}」段，四行：" + "／".join(f"{lb}：…" for lb in SO_LABELS)
            + "（failed／blocked 也要寫明狀態與自己的結論）；寫在本回合任一則回覆都算，被別的閘擋下後補件那則不必重抄。\n"
            "要跑：second_opinion_start(mode=independent, kind=stage-review, question=<含樹根那句>)→second_opinion_result；"
            f"{SO_RESULT_WAITS}；或宣告 `不需第二意見｜<理由>`")


def second_opinion_decline(text: str) -> Optional[str]:
    """收尾文字裡最後一行「不需第二意見｜<理由>」的理由（可能是空字串）；沒有這行回 None。只認行首、程式碼區塊外。"""
    found: Optional[str] = None
    for line in _so_lines(text):
        m = _SO_DECLINE_RE.match(line)
        if m:
            found = m.group(1).strip()
    return found


def second_opinion_decline_ok(reason: str) -> bool:
    """SECOND_OPINION_DECLINED：理由有文字內容、不是佔位、不是「不需要」這類空話。不評理由充不充分。"""
    core = _ITEM_STRIP_RE.sub("", str(reason or "")).lower()
    return reason_present(reason) and core not in _SO_EMPTY_REASONS


def second_opinion_waiting(text: str) -> List[str]:
    """SECOND_OPINION_WAITING_NOT_DONE：收尾裡每一行「等第二意見｜<job_id>」的 job_id（行首、程式碼區塊外、完整 job_id）。"""
    return [m.group(1) for m in (_SO_WAIT_RE.match(ln) for ln in _so_lines(text)) if m]


def second_opinion_section_missing(text: str) -> List[str]:
    """收尾缺的項目：段標題、四行標籤（行首、標籤後要有至少 2 個中文或英數字）。全在回 []。程式碼區塊裡的不算。"""
    lines = _so_lines(text)
    missing = [] if any(SO_SECTION in ln for ln in lines) else [f"段標題「{SO_SECTION}」"]
    for label, rx in _SO_LABEL_RES:
        filled = [m for m in (rx.match(ln) for ln in lines) if m and has_text(m.group(1))]
        if not filled:
            missing.append(f"「{label}：」行")
    return missing


def second_opinion_triggers(n_code: int, changed_lines: Optional[int], risky: Sequence[str],
                            min_files: int, min_lines: int) -> List[str]:
    """SECOND_OPINION_REQUIRED 的門檻事實 → 命中的觸發原因（空＝沒過門檻）。changed_lines=None＝查不到 git，只看檔數。"""
    out: List[str] = []
    if n_code >= min_files:
        out.append(f"程式檔 {n_code} 個 ≥ {min_files}")
    if changed_lines is not None and changed_lines >= min_lines:
        out.append(f"對 HEAD 的程式改動 {changed_lines} 行 ≥ {min_lines}")
    if risky:
        out.append("改到高風險部位：" + "、".join(_base_name(p) for p in list(risky)[:5]))
    return out


def second_opinion_runs(starts: Sequence[Dict[str, Any]], results: Sequence[Dict[str, Any]],
                        has_tree: bool = False) -> List[Tuple[str, str]]:
    """本回合每個 job 的最終狀態 [(job_id, 狀態)]：先列本回合每次 start，再列本回合只有 result、start 在前面回合的 job
    （SECOND_OPINION_RESULT_ACROSS_TURNS：mode 照 result 的 mode 行、kind 照 job_id 尾、notes 照 result 的 note 行；沒有 mode 行＝
    找不到 job，不列）。starts／results＝transcript 依序收的 {mode, kind, job_id, status, reason, notes}／
    {job_id, status, reason, mode, notes}；has_tree＝這個 session 有需求目標樹。只認 second_opinion_result 回的狀態（result 回
    done／failed／blocked 才算跑過）。狀態：done／failed／blocked（算跑過）、running、started（start 了沒取結果）、
    rejected（question 沒含樹根被擋）、no-goal（session 有樹但材料沒帶到：note 以 SO_NO_GOAL_NOTE 開頭）、
    invalid（start 沒開出 job：被拒收或 prepare 失敗，job_id 是 -）、off-mode（不是 independent 或 kind 不對）。"""
    last: Dict[str, Dict[str, Any]] = {}
    for r in results:
        last[str(r.get("job_id") or "")] = r
    started = {str(s.get("job_id") or "-") for s in starts}
    only_result = []
    for jid, r in last.items():
        if jid and jid not in started and r.get("mode"):
            m = _SO_JOB_KIND_RE.search(jid)
            only_result.append({"job_id": jid, "mode": r.get("mode"), "kind": m.group(1) if m else "",
                                "notes": r.get("notes") or ()})
    out: List[Tuple[str, str]] = []
    for s in [*starts, *only_result]:
        jid = str(s.get("job_id") or "-")
        no_goal = has_tree and any(str(n).startswith(SO_NO_GOAL_NOTE) for n in s.get("notes") or ())
        if s.get("mode") != "independent" or s.get("kind") not in SO_KINDS:
            out.append((jid, "off-mode"))
            continue
        if jid == "-" or no_goal:
            out.append((jid, "invalid" if jid == "-" else "no-goal"))
            continue
        fin = last.get(jid) or {}
        st = str(fin.get("status") or "")
        why = str(fin.get("reason") or s.get("reason") or "")
        if SO_QUESTION_ROOT_MISSING in why:
            out.append((jid, "rejected"))
        elif st in SO_RAN or st == "running":
            out.append((jid, st))
        else:
            out.append((jid, "started"))
    return out


_SO_WAIT = {
    "running": "第二意見還在跑（result=running）：再呼叫一次 second_opinion_result({job_id})，它會等到有結果；"
               f"要先結束回覆就在收尾寫一行 `{SO_WAIT_LINE}`",
    "started": "start 了但還沒取結果：直接呼叫 second_opinion_result({job_id})，它會等到 done／failed／blocked；"
               f"要先結束回覆就在收尾寫一行 `{SO_WAIT_LINE}`",
    "stale": "取回的 job 是前面回合開的，開了之後又改過程式檔，沒審到後來的改動：重跑 second_opinion_start",
    "foreign": "取回的 job 不是這個 session 開的（job_id 裡的 session 前 8 碼對不上），不算：本 session 自己跑 second_opinion_start",
    "rejected": f"start 被擋：{SO_QUESTION_ROOT_MISSING}，照 reason 把那句抄進 question 重跑",
    "no-goal": f"這次的材料沒有需求目標樹（start 的 note：{SO_NO_GOAL_NOTE}…），不算跑過：確認 start 帶到 session_id"
               "（PreToolUse 補）後重跑",
    "invalid": "start 沒開出 job（被拒收或 prepare 失敗，job_id 是 -），照 reason 修正後重跑；修不好就宣告不需並寫明原因，或問使用者",
    "off-mode": "本回合跑的不是 mode=independent＋kind=stage-review／evaluate，不算",
}


def second_opinion_verdict(claims_done: bool, triggers: Sequence[str], edited_since_ok: bool,
                           runs: Sequence[Tuple[str, str]], text: str, closing: Optional[str] = None) -> Verdict:
    """SECOND_OPINION_REQUIRED／SECOND_OPINION_DECLINED／SECOND_OPINION_WAITING_NOT_DONE：owed＝要擋。triggers＝
    second_opinion_triggers 的結果；edited_since_ok＝上次滿足之後又改過程式；runs＝second_opinion_runs 的結果；text＝看四行的那則
    （wg_second_opinion.section_text）；closing＝收尾最後一則（宣告行與在等哪個 job 只看它：SECOND_OPINION_DECLINE_ACCEPTED），
    沒給就同 text。"""
    rule = "SECOND_OPINION_REQUIRED"
    closing = text if closing is None else closing
    if not claims_done:
        return Verdict(rule, False, "沒有宣告完成")
    if not triggers:
        return Verdict(rule, False, "改動沒過大任務門檻、也沒改到高風險部位")
    if not edited_since_ok:
        return Verdict(rule, False, "上次第二意見之後的修改沒改到新的高風險部位、新改的程式檔也沒過門檻（採納意見的修改不再要一輪）")
    ran = [(j, s) for j, s in runs if s in SO_RAN]
    missing = second_opinion_section_missing(text)
    if ran and not missing:
        return Verdict(rule, False, f"本回合跑過第二意見（{ran[-1][0]} {ran[-1][1]}），收尾有分歧裁決四行")
    reason = second_opinion_decline(closing)
    if reason is not None:
        if second_opinion_decline_ok(reason):
            return Verdict("SECOND_OPINION_DECLINED", False, f"AI 宣告不需第二意見：{reason[:120]}")
        return Verdict("SECOND_OPINION_DECLINED", True, "宣告「不需第二意見」但理由空、只有佔位或只寫不需要",
                       tuple(triggers) + (f"理由：「{reason[:60]}」",))
    declared = set(second_opinion_waiting(closing))
    waiting = [j for j, s in runs if s in ("running", "started") and j in declared]
    if waiting:
        return Verdict(SO_WAITING, False, f"第二意見 {waiting[-1]} 還在跑、收尾寫明在等它：這次結束回覆不算宣告完成",
                       tuple(waiting))
    if ran:
        return Verdict(rule, True, "跑過第二意見，但收尾缺：" + "、".join(missing),
                       tuple(triggers) + tuple(f"{j} {s}" for j, s in ran[-3:]))
    seen = [s for _j, s in runs]
    wait = next((_SO_WAIT[k] for k in ("running", "started", "stale", "foreign", "rejected", "no-goal", "invalid", "off-mode")
                 if k in seen), "")
    return Verdict(rule, True, wait or "大任務或高風險部位收尾，本回合沒有跑第二意見",
                   tuple(triggers) + tuple(f"{j} {s}" for j, s in runs[-3:]))


# ─── G7 等值與熱路徑 ───
# 重構意圖收尾要有等值證法三類收據（或附理由的不適用宣告），熱路徑答「是」要有量測收據。事實（意圖、改檔、收據、收尾文字）
# 由 handlers/stop.py 的 Equivalence Gate 收，這裡只判；判斷（適不適用、是不是熱路徑、量法）交 AI 宣告並附理由，程式只核對有沒有答、
# 收據在不在。
RULES.update({
    "REFACTOR_NEEDS_EQUIVALENCE": "意圖 refactor、本回合改過程式檔、宣告完成 → 最後一次改程式檔之後要有三筆 PRESERVE_CHECK PASS 收據"
                                  "（指令各帶 --mutation order／side_effect／boundary，沒紅、指令沒自己寫哨兵字樣），或收尾文字一行"
                                  "「等值證法｜不適用｜<理由>」（理由有文字內容、不是佔位；留帳 guard-equivalence.jsonl）。"
                                  "缺 → 照寫碼查核的預算擋，擋滿問使用者。意圖（state turn_intent）只由使用者本人打的字判"
                                  "（user_typed_text；同伴訊息、背景通知沿用上一個意圖），AI 自己說「重構」不會把自己擋住。",
    "PERF_HOT_PATH_NEEDS_MEASURE": "意圖 refactor 或 perf、本回合改過程式檔、宣告完成 → 收尾文字要答「熱路徑｜是｜<哪裡>」或"
                                   "「熱路徑｜否｜<為什麼>」。答是 → 最後一次改程式檔之後要有量測收據（`<NAME> DONE k=v` 哨兵，要帶 k=v 數字；"
                                   "pytest 統計行轉成的 PYTEST_MEASURE 沒有數字不算）或"
                                   "「量測｜不做｜<理由>」（留帳）；答否附理由 → 放行（留帳）。沒答 → 每個使用者回合擋一次；"
                                   "答了但缺收據或缺理由 → 照寫碼查核的預算擋，擋滿問使用者。是不是熱路徑、怎麼量由 AI 判。",
})

RULES["EQUIVALENCE_LOOP_EXPANDED"] = ("三類變異寫在一條 for 迴圈裡跑（`for m in order side_effect boundary; do … --mutation $m …; done`，"
                                      "清單每項字面、本體沒有指令位置上的 break／continue／exit／return；引號裡的字樣不算）→ 每份展開的本體各算一筆"
                                      "收據，條件是那筆收據的 PRESERVE_CHECK PASS 行數（哨兵帳 n）不少於展開份數、沒有 FAIL、沒紅；"
                                      "展開在 handlers/stop._loop_mutation_receipts（lib/overview_hub.bash_for_bodies），判類別照 proved_mutations。")
RULES["EQUIVALENCE_NA_DECLARED_ALWAYS_LOGGED"] = ("收尾文字有「等值證法｜不適用｜<理由>」（理由有文字內容、不是佔位）→ 每次都留帳 guard-equivalence.jsonl "
                                                  "not_applicable（行、理由、needed＝等值閘這回合管不管），排在所有收尾閘前面（比照 "
                                                  "SECOND_OPINION_DECLARED_ALWAYS_LOGGED）：意圖不是重構、本回合沒改程式、前面的閘先擋下都照記；"
                                                  "同一個使用者回合同一行只記一筆（handlers/stop._declared_once）。")
EQUIVALENCE_MUTATIONS = ("order", "side_effect", "boundary")
EQUIVALENCE_SENTINEL = "PRESERVE_CHECK"
EQUIVALENCE_ENTRY = "跑三類 `preserve-check.py --mutation order|side_effect|boundary`（尾行 PRESERVE_CHECK PASS），或宣告 `等值證法｜不適用｜<理由>`"
HOT_PATH_ENTRY = "答 `熱路徑｜是｜<哪裡>`＋量測收據（`<NAME> DONE k=v`）或 `量測｜不做｜<理由>`；或 `熱路徑｜否｜<為什麼>`"
_MUTATION_ARG_RE = lazy_re(r"--mutation(?:\s+|=)[\"']?(order|side_effect|boundary)\b")
_EQ_NA_RE = lazy_re(r"等值證法\s*[｜|]\s*不適用\s*(?:[｜|]\s*(.*))?$")
_HOT_RE = lazy_re(r"熱路徑\s*[｜|]\s*(是|否)\s*(?:[｜|]\s*(.*))?$")
_MEASURE_SKIP_RE = lazy_re(r"量測\s*[｜|]\s*不做\s*(?:[｜|]\s*(.*))?$")


def proved_mutations(receipts: Iterable[Tuple[Any, ...]]) -> List[str]:
    """(指令, 哨兵「名稱:結論」, exit[, …]) → 證到的類別（照三類順序）：有 PRESERVE_CHECK:PASS、沒紅、指令帶 --mutation <類>。
    一筆收據只算一類：取指令裡最後一個 --mutation（preserve-check.py 的 argparse 單值參數，重複指定只跑最後一個；
    三次串成一條指令的，哨兵同一行只記一次，也只算最後一類，三類要分三次跑）。
    收據資格（指令完整、沒自己寫哨兵字樣、在最後一次改檔之後）由呼叫端先篩。"""
    got = set()
    for cmd, verdicts, exit_code, *_ in receipts:
        if f"{EQUIVALENCE_SENTINEL}:PASS" not in {str(v).upper() for v in verdicts or ()} or receipt_red(verdicts, exit_code):
            continue
        found = _MUTATION_ARG_RE.findall(str(cmd or ""))
        if found:
            got.add(found[-1])
    return [m for m in EQUIVALENCE_MUTATIONS if m in got]


def has_measure(receipts: Iterable[Tuple[Any, ...]]) -> bool:
    """(指令, 哨兵「名稱:結論」, exit, 這筆收據各 DONE 哨兵的 k=v 清單) → 有一筆沒紅、而且至少一個 DONE 帶 k=v（`<NAME> DONE k=v`
    的量測數字）。只有 DONE 沒有數字的不算：設定把 pytest 統計行轉成的 PYTEST_MEASURE:DONE 沒有 k=v，跑一般測試不等於量了熱路徑。"""
    for _cmd, verdicts, exit_code, *rest in receipts:
        kvs = rest[0] if rest else ()
        if not receipt_red(verdicts, exit_code) and any(kv for kv in kvs or ()):
            return True
    return False


def parse_equivalence_lines(text: str) -> Dict[str, List[Dict[str, str]]]:
    """收尾文字裡的三種入口行 → {"na": [{reason, line}], "hot": [{answer, why, line}], "skip": [{reason, line}]}，一行一條。
    行首的 markdown 記號（`、*、-、>）與行尾的 `、* 先剝掉（行尾的 > 留著：它可能是角括號佔位的一半）。
    熱路徑行後面還留著擋訊息的角括號佔位（照抄入口寫法）不算回答。"""
    out: Dict[str, List[Dict[str, str]]] = {"na": [], "hot": [], "skip": []}
    for raw in str(text or "").splitlines():
        ln = raw.strip().lstrip("`*->").strip().rstrip("`*").strip()
        m = _EQ_NA_RE.search(ln)
        if m:
            out["na"].append({"reason": (m.group(1) or "").strip().strip("`"), "line": ln[:200]})
            continue
        m = _HOT_RE.search(ln)
        if m and not _EXAMPLE_PLACEHOLDER_RE.search(m.group(2) or ""):
            out["hot"].append({"answer": m.group(1), "why": (m.group(2) or "").strip().strip("`"), "line": ln[:200]})
            continue
        m = _MEASURE_SKIP_RE.search(ln)
        if m:
            out["skip"].append({"reason": (m.group(1) or "").strip().strip("`"), "line": ln[:200]})
    return out


def equivalence_verdict(proved: Sequence[str], na: Sequence[Dict[str, str]]) -> Verdict:
    """REFACTOR_NEEDS_EQUIVALENCE：owed＝三類沒證齊、也沒有附理由的不適用宣告。"""
    ok = next((d for d in na if reason_present(d.get("reason", ""))), None)
    if ok:
        return Verdict("REFACTOR_NEEDS_EQUIVALENCE", False, f"AI 宣告等值證法不適用：{ok['reason'][:120]}", (ok["line"],))
    missing = [m for m in EQUIVALENCE_MUTATIONS if m not in proved]
    if not missing:
        return Verdict("REFACTOR_NEEDS_EQUIVALENCE", False, "三類 PRESERVE_CHECK PASS 都在")
    why = (f"宣告了「等值證法｜不適用」但沒附理由（或只有佔位），三類缺 {'、'.join(missing)}" if na
           else f"重構宣告完成，等值證法三類缺 {'、'.join(missing)}")
    have = f"已證：{'、'.join(proved)}" if proved else "已證：無"
    return Verdict("REFACTOR_NEEDS_EQUIVALENCE", True, why, (have, *(d["line"] for d in na[:2]), f"入口：{EQUIVALENCE_ENTRY}"))


def hot_path_verdict(hot: Sequence[Dict[str, str]], skip: Sequence[Dict[str, str]], measured: bool) -> Verdict:
    """PERF_HOT_PATH_NEEDS_MEASURE：owed＝沒答、答是但沒量測收據也沒附理由的不做、答否沒附理由。有一行答是就照是判（嚴的那邊）。"""
    entry = f"入口：{HOT_PATH_ENTRY}"
    yes = [h for h in hot if h["answer"] == "是"]
    if yes:
        where = yes[0]["why"][:80] or "（沒寫哪裡）"
        if measured:
            return Verdict("PERF_HOT_PATH_NEEDS_MEASURE", False, f"熱路徑是（{where}），量測收據在", (yes[0]["line"],))
        ok = next((d for d in skip if reason_present(d.get("reason", ""))), None)
        if ok:
            return Verdict("PERF_HOT_PATH_NEEDS_MEASURE", False, f"熱路徑是（{where}），AI 宣告不量：{ok['reason'][:120]}",
                           (yes[0]["line"], ok["line"]))
        why = (f"答了熱路徑是（{where}），「量測｜不做」沒附理由" if skip
               else f"答了熱路徑是（{where}），最後一次改檔之後沒有量測收據（DONE 哨兵）")
        return Verdict("PERF_HOT_PATH_NEEDS_MEASURE", True, why, (yes[0]["line"], *(d["line"] for d in skip[:1]), entry))
    no = [h for h in hot if h["answer"] == "否"]
    ok = next((h for h in no if reason_present(h["why"])), None)
    if ok:
        return Verdict("PERF_HOT_PATH_NEEDS_MEASURE", False, f"AI 答熱路徑否：{ok['why'][:120]}", (ok["line"],))
    if no:
        return Verdict("PERF_HOT_PATH_NEEDS_MEASURE", True, "答了熱路徑否但沒附為什麼（或只有佔位）", (no[0]["line"], entry))
    return Verdict("PERF_HOT_PATH_NEEDS_MEASURE", True, "沒答「這次改動碰到熱路徑或大量配置嗎」", (entry,))


# ─── 閘小修 008 A：閘的判定與提示（事實由各自的模組收，這裡只登錄規則名與說明） ───
RULES.update({
    "OLD_TEST_COMPARED_ON_FAILED_COMMAND": "Bash／PowerShell 指令非零結束時 Claude Code 不送 PostToolUse、改送 PostToolUseFailure；"
                                           "改舊測試的事後比對（wg_oldtest.after_tool）兩個事件都跑（post_tool_use._old_test_after）："
                                           "`sed -i … tests/x.py && pytest` 紅了，改既有斷言已經寫進檔，照樣比、沒宣告記欠帳、下一個工具呼叫擋；"
                                           "新加的測試同一刻記進 old_test_added。裁判子 session 不比（它的 PreToolUse 不拍快照）。",
    "USER_TURN_KEY_KEPT": "使用者回合鍵（turn_prompts_seq）不掉：state 在 compact／resume 重建時回合編號與回合鍵照搬"
                          "（session_start._CARRY_ON_REBUILD：turn_seq、turn_prompts_seq、user_turn_count、turn_open、turn_typed）；"
                          "鍵還是不在（state 從零建）時，UserPromptSubmit 第一則進來的訊息就算是同伴訊息、背景通知也把鍵錨在這一則"
                          "（ups_gates.track_turn_prompts；不加 user_turn_count；v6 關照舊不錨），之後照 TURN_SINCE_USER_PROMPT 前進。鍵不在時 user_turn "
                          "退回逐則前進的 turn_seq，每則同伴訊息都被當成新使用者回合（PickOne 每則重問、各閘每回合的擋次與預算重來）。",
    "COMPLETION_CLAIM_PER_SENTENCE": "宣告完成（wg_evasion.claims_completion）：最後 2000 字裡有「這則之後工作還在繼續」的話（仍在等、"
                                     "等待…回報、尚未開始）整則不算；否則逐句看，有一句有完成詞、而那一句本身沒有其餘排除詞（還沒／尚未…完成、"
                                     "待補、中途、進行中）就算，這幾個只取消它自己那一句；收尾閘往前找宣告完成的那則（wg_second_opinion.turn_completion_text）同一套（第二意見閘進不進門不靠它：SECOND_OPINION_FACT_TRIGGER，只借第一類「還在繼續」的詞判這則還沒到收尾）；"
                                     "句界＝句號、驚嘆號、問號、換行，逗號、分號不切（「A2 已完成，仍在等 A1 回報」仍是中途）。"
                                     "收割待補閘的「中途狀態句不擋」（wg_harvest.in_progress_text）同源：另有一句宣告完成就不算中途。",
    "OPENING_NOTICE_NOT_TODO": "開場的系統提示不寫成待辦口吻：處置句寫清誰決定、要不要現在處理；使用者這回合要的是別的事時只轉述、不動手"
                               "（session_start._harvest_staged_line：背景收割候選待審那一行）。",
    "GATE_TEXT_AVOIDS_EVASION_WORDS": "閘的擋訊息與提示（hooks／lib 送得到 AI 眼前的字串）不用會中退避詞表（memory/_meta/forbidden-phrases.json）"
                                      "的字句：AI 在回覆裡照抄被擋的那則時，退避偵測不開引用豁免，照抄的字會被記成 AI 退避。"
                                      "改說法、不改偵測面；守門案例對每則字串跑 detect_evasion（verify_evasion_guard）。",
    "SUBPROCESS_RUN_LOOKED_UP_AT_CALL": "跑子行程的函式不把 subprocess.run 綁成參數預設值：預設 None、呼叫當下才取 subprocess.run。"
                                        "綁在定義時，測試的 git 錄製重播換掉 subprocess.run 也攔不到，結果看匯入順序、錄製檔對不上。",
})


# ─── 閘的三件設計題（無頭警報後資料閘照擋、唯讀 Bash 讀檔、暫存目錄專案寫入）：判定在各自的模組，這裡只登錄規則名與說明 ───
RULES.update({
    "CHAIN_HEADLESS_KEEPS_DATA_GATES": "沒人能答（無頭、子代理）時連鎖斷路器警報之後，會改使用者資料的閘照擋（含讓警報響的那一次），其餘閘照舊只記錄。"
                                       "哪幾道與理由見 hooks/wg_chain.py 的 RULES 同名條與 KEEP_BLOCKING（判定 keeps_blocking）。",
    "SHELL_READ_COUNTS_LIKE_READ": "唯讀 Bash／PowerShell 讀檔跟 Read 同效（定位閘的讀過部位檔、需求目標的讀入範圍共用 wg_overview.read_targets）："
                                   "一條指令讀好幾個檔、第一次碰到部位時，注入導讀卡之後的檔照記（跟送幾個 Read 一樣）；MSYS 寫法 /c/x 當 C:/x"
                                   "（跟寫檔判定 wg_core._write_target_abs 同一個檔）；會印出命中行的 grep 不帶 -n 也算（只印檔名、筆數或不印的 -l、-L、-c、-q 帶了 -n 也不算）；"
                                   "開頭 `cd <目錄> &&` 之後的相對路徑照那個目錄補（中間的 cd 不追）。其餘照 BASH_READONLY_COUNTS_AS_READ。",
    "SHELL_WRITE_COMMAND_NOT_A_READ": "Bash／PowerShell 指令有寫檔目標（wg_core.write_paths_from_tool 判出任何目標，含判不出的；重導向 >、tee、"
                                      "sed -i、Out-File…）就不是唯讀：整條讀到的檔都不算讀過、也不注入導讀卡；`2>&1`、`> /dev/null` 不是寫檔目標。",
    "EPHEMERAL_WRITE_NOTED_ONCE": "專案放在系統暫存目錄底下（handlers/_shared._is_ephemeral_path 的暫存根那一支），寫入照舊不記進改檔清單；"
                                  "同一 session、同一個專案根（版控根，沒有就 cwd，再沒有就暫存根底下第一層）第一次印一行 stderr "
                                  "[Guardian:EphemeralWrite] 說明沒記、收尾閘看不到（_shared.note_ephemeral_skip）；不在暫存根底下、只因快取目錄"
                                  "（__pycache__、.pytest_cache）判成暫存的不是專案，不印。",
})
RULES.update({
    "CHAIN_NO_EDIT_NO_EDGE": "連鎖斷路器：兩次擋之間的動作都沒改到檔（重跑、沒寫入目標的指令、重交報告、改目標樹）不算修補，同一道閘不接邊、"
                             "不算同閘次數。判定與「改到檔」的清單見 hooks/wg_chain.py 的 RULES 同名條（changes_files）。",
    "CHAIN_ABORT_SHOWS_REPLACED_BLOCK": "連鎖斷路器警報在哪一次響，那道閘原本的擋訊息（含附註）照附在取代它的中止通知或停手訊息最後（截長留開頭）。"
                                        "見 hooks/wg_chain.py 的 RULES 同名條（notice_text／halt_text 的 replaced）。",
})


# ─── 卡片來源自動填：使用者原話（判定在 hooks/wg_provenance.py，這裡只登錄規則名與說明） ───
RULES.update({
    "QUOTE_FROM_USER_OPENED_TURN": "卡片的 Quote 只取寫卡那一回合是使用者本人打字開的原話（wg_provenance._turn_quote；回填工具 "
                                   "atom-provenance-backfill 的 not_user_turn 同一條）：主 session 的 state.turn_typed 是 False"
                                   "（同伴訊息、背景通知開的續跑回合，turn_prompts 沿用前一回合原話給口令閘用）→ 不填；子代理（hook 帶 "
                                   "agent_id）不看 state、不拿子代理檔的任務 prompt，改由子代理檔第一筆的 promptId 對主檔開那一回合的紀錄"
                                   "（wg_provenance._subagent_opener），lib/provenance.is_human_record 是才填（isSidechain 一律不算真人）；"
                                   "貼上的內容（lib/harness_text.strip_pasted）不當原話。守門總開關開關都套。",
})


# ─── 觸發導讀卡注入那次讀也算讀過（判定在 hooks/wg_overview.on_read，這裡只登錄規則名與說明） ───
RULES.update({
    "INJECT_TRIGGER_READ_COUNTED": "觸發導讀卡注入的那次讀就是真讀：Read 或唯讀 Bash／PowerShell 第一次讀到某部位，觸發注入的那個檔本身"
                                   "也記進讀過部位檔（part_files_read、reads_after），一條指令讀到的同部位其他檔照 SHELL_READ_COUNTS_LIKE_READ"
                                   "全記；改檔前才補注入（on_edit）沒有讀檔，不記。「看過全貌才改」靠注入後還要交的定位四行守。",
})


# ─── 需求目標提示減量：三種情況一次全文、提示附樹一行（送法在 hooks/wg_need_goal.py，這裡只登錄規則名與說明） ───
RULES.update({
    "CRITIQUE_CASES_ONCE_PER_SESSION": "「用目標視角重看」三個提示（讀入範圍變大、收到外部主張、目標改了重看）與導讀卡附樹的定位第五行提示"
                                       "帶的三種情況（wg_need_goal.CRITIQUE_CASES）每個 session 送一次全文，之後換成一句指回"
                                       "（CRITIQUE_CASES_POINTER）；兩問與定位第五行格式照送。已送記在目標檔 critique_sent"
                                       "（wg_need_goal.critique_mark／critique_once；還沒有目標檔就照送全文、不建檔；讀寫失敗照送全文），"
                                       "壓縮後重送目標樹時清掉（wg_need_goal_points.recovery_text 呼叫 forget_reminders），下一則再送一次全文。"
                                       "設定 v6.slim_reminders=false 退回每則全文。",
    "TREE_LINE_IN_HINTS": "need_goal 以外的 hook 提示（導讀卡附樹、目標視角重看、讀入範圍、糾正、外部主張、每則訊息、交付對照）附的目標樹"
                          "只一行當前節點（wg_need_goal.brief_line；沒有子節點就是樹根自己）；樹根與整棵樹只在 need_goal "
                          "set／add／update／reconcile 的回覆送（TREE_ONCE_PER_CALL）。壓縮後重送照附樹根一行＋當前節點"
                          "（recovery_blob，context 裡已沒有寫入回覆的樹）。設定 v6.slim_reminders=false 退回每則附樹根一行。",
})


# ─── 寫碼回合的記憶注入只送該到的（判定在 hooks/handlers/ups_inject.assemble_injection，這裡只登錄規則名與說明） ───
RULES.update({
    "CODING_TURN_FULL_ONLY_ON_TRIGGER": "寫碼回合（守門總開關開、而且這個使用者回合已經改過程式檔或宣告了寫碼樹：wg_core.coding_turn，"
                                        "ups_inject._lean_turn 看它；prompt 關鍵字判成的寫碼意圖不算，所以使用者打字開的第一則永遠不瘦身、"
                                        "同回合排隊進來的後續 prompt 在改過碼之後才瘦身）記憶卡只有 trigger 命中的給整段"
                                        "（含原有的同題節錄、塞不下時的印象節錄）；bm25／vector／related 命中的不看 hot／cold 一律走 cold 一行"
                                        "（form＝cold，取用端稽核只追 trigger 命中的，不受影響）。一行送過的卡照舊進 injected_atoms"
                                        "（搜尋段不再給它當候選、失念偵測當它注入過），之後的寫碼回合被 trigger 命中時從全池補回候選給整段"
                                        "（ups_inject._line_upgrades，來源記 trigger）。總開關關、或不是寫碼回合照舊。",
    "POINTER_NO_NAME_ECHO": "寫碼回合的一行指標（cold 行、budget 塞不下退的路標）摘要或標題只是卡名再寫一次時不重印，只留卡名＋路徑"
                            "（wg_atoms.title_echoes_name：去掉標點、空白、大小寫與截斷的 … 後是卡名的開頭）；摘要是印象行、或比卡名多資訊的照留。",
    "NO_RESEND_AFTER_RESUME": "寫碼回合同一張卡在這個 session 最近一次壓縮之後已整段送出過（injection_log 的 form_final＝ok、不是只抽了"
                              "命中章節 sections，送出時間 at 晚於 pre_compact_snapshot／post_compact_at 一秒以上：ups_inject.delivered_forms"
                              " 的 full），resume 清空 injected_atoms 後再命中只給一行指回（form＝seen，不算路標、取用端稽核不追問）；"
                              "壓縮之後、之前只送過一行或只送章節、判不出先後的照常送。送出時間與章節標記只在總開關開時記。",
})


# ─── 定位閘每個使用者回合最多擋一次、thinking 那條路講死、目標視角重看只一行（判定在 hooks/wg_overview.py，這裡只登錄） ───
RULES.update({
    "LOCATE_BLOCK_ONCE_PER_USER_TURN": "同一個使用者回合（user_turn：使用者本人打字開的回合，同伴訊息、背景通知續跑不算新回合）定位閘已經擋過"
                                       "某個部位之後，別的部位只缺定位行 → 一行提醒、放行、留帳（_overview-hub.log event=edit_locate_reminded）；"
                                       "缺讀檔證據、導讀卡還沒注入照擋，擋過的那個部位再缺照擋（照 GATE_DENY_CAP），下一個使用者回合重來；本條只在送法是 block 時有意義（v6 關）"
                                       "（wg_overview.on_edit、_blocked_parts／_note_block，state overview_locate_blocked）。本條管的是第一輪"
                                       "（LOCATE_FIRST_EDIT_BLOCKS_ONCE：每部位第一次改的那個使用者回合）之後的擋；第一輪的擋不記進 overview_locate_blocked。",
    "LOCATE_NOT_IN_THINKING": "缺定位行的擋訊息明說 thinking 預設不寫進 transcript、hook 讀不到、只寫那裡會再擋一次，要放"
                              "先發的不寫檔指令開頭的 # 註解或早一則的回覆文字（DECL_WHERE；wg_overview._locate_ask 的 where）。",
    "GOAL_VIEW_ONE_LINE": "目標視角重看（目標改了之後已碰過的部位再讀到，第一次 need_goal set 也算）只送一行：目標視角提問＋當前節點"
                          "（wg_need_goal_points.goal_view_text 併成一行），不重貼導讀卡、定位範本與部位表原文（wg_overview._goal_view）。",
})


# ─── 擋訊息與判準卡瘦身、讀到資料檔就先提示：判定在各自的模組，這裡登錄規則名與說明 ───
RULES.update({
    "DENY_TEXT_SLIM": "擋訊息精簡格式（guard.deny_text_slim，預設開）：第一行「[<閘>] 修法：<一句>」，下面每條命中一行 format_hit"
                      "（規則名＋現象＋證據，每項證據超過 DENY_EVIDENCE_CAP 字截短，parse_hits 照認），判準卡名由接卡處接在後面；"
                      "共用組裝 slim_deny，採用的閘交規則名與一句修法（動資料檔閘：data_file_fix）。寫 false 退回各閘原本的長文字（原處不動）。",
    "CARD_FULL_ONCE_PER_SESSION": "判準卡一個 session 每張最多送一次全文（entrypoint.card_once_per_session，預設開；hooks/wg_entrypoint）："
                                  "之後換回合、換目標樹都只併成一行「判準卡：<卡名>、…」，不印「這個話題前面已送過全文」；"
                                  "同一個切入點這個 session 拿過卡，再被問就不往下送新卡、帳上不記截斷；同一則認出好幾個切入點、額度被平分到比單一額度小時，截斷送出的卡不算送過、被截的切入點不算拿過卡（下次單獨被問照送）。壓縮前清掉紀錄（之後重送）、"
                                  "子代理開工句照送全文也不佔主對話；寫 false 退回 CARD_ONCE_PER_TOPIC。",
    "DATA_FILE_READ_HINT": "第一次讀到改了會被動資料檔閘問的檔（Read／唯讀 Bash／PowerShell／Grep，讀了什麼跟定位閘同一支 read_targets；"
                           "副檔名在清單、不是系統文件、不是程式檔、已存在、本 session 沒新建過、本 session 沒宣告過、state 裡的使用者原話沒點名）"
                           "→ 讀檔結果後附一行宣告格式（wg_data_file.read_hint；一個檔一個 session 一次，第二個檔起只點名、說格式同前；"
                           "子代理讀的不提示），讓第一次改就帶宣告。這個 session 沒改過程式檔（wg_data_file.coding_session）閘不會問，"
                           "也就不提示。判定（USER_DATA_FILE_NEEDS_DECLARATION）不動：閘會問的沒宣告照擋。",
})
RULES.update({
    "LOCATE_EXAMPLE_ONCE_PER_SESSION": "有目標樹時缺定位行的擋訊息（LOCATE_ASK_ONCE 那條完整範例）每個 session 只給一次完整範例：擋訊息精簡"
                                       "（guard.deny_text_slim）開、本 session 已送過（state overview_locate_example_sent）→ 那一條換成短句"
                                       "（wg_overview.LOCATE_EXAMPLE_AGAIN：四行格式同第一則、先放 # 註解其次早一則回覆文字、thinking 讀不到）；"
                                       "缺件清單照原文比（擋次上限、同批短訊息不因換字重新計次）；精簡關掉每則照給完整範例。",
})
RULES.update({
    "CARD_READ_WITH_EDIT_FILES": "指標制送卡時，指標行（lib/overview_hub._pointer_body）與讀卡缺件行（wg_overview._card_unread_line）"
                                 "直接講下一步：「下一則讀卡時順便讀要改的檔」，讓讀卡跟讀要改的檔併在同一則送、不為讀卡多停一次。只改文字，判定不變。",
})


# ─── 收尾只跑一輪、第二意見背景跑（事實與時點在 hooks/wg_closing_round.py、wg_reading_path.py、handlers/stop.py，這裡只登錄規則名、說明與提示） ───
RULES.update({
    "READING_PATH_EARLY_START": "拐彎判斷的背景量測改完程式就起跑，不等第一次收尾：每批工具跑完（PostToolBatch）看本回合改過的程式檔"
                                "指紋（修改時間、大小，只 stat 不起 git），變了就照收尾那套交背景量（量測中又改了先記 pending、同一批不重量）；"
                                "量完的結果先存著（wg_reading_path.early_start、EARLY_NOTE），由收尾前的附著點或 Stop 送一次，"
                                "Stop 收到新的一批就只送新的。開關 reading_path.early_start（缺＝開）；關了照舊在收尾起跑。",
    "TURN_JUDGMENT_PRE_CLOSE": "交收尾檢核（anti_evasion_report）或完整對照（need_goal action=reconcile）那批＝收尾前最後一個工具回應：先存著的拐彎判斷結果（到門檻的條目＋那一題）"
                               "附在那批的回應後面（wg_closing_round.turn_judgment_pre_close），取走後 Stop 不再送；還有一批在量（量完前又改了碼）"
                               "就不附，留給 Stop。欠項照舊由 Stop 的 TURN_JUDGMENT_REQUIRED 核對收尾文字（不放寬、不改擋次）。",
    "PICK_ONE_PRE_CLOSE": "交收尾檢核或完整對照（need_goal reconcile，交付時的對照）那批就是交付邊界：「順手看到最該修」該問（同 Stop：上次問過或記過之後又改了程式、這個使用者回合還沒問過，"
                          "連鎖警報後只記錄時不送）就附在那批的回應後面、記問過（guard-pick_one via=pre_close）；Stop 的 pick_due 看到問過"
                          "就不再送，對話不再為它續跑一輪。開關 pick_one.pre_close（缺＝開）；兩樣都沒交或開關關照舊由 Stop 送。",
    "PICK_ONE_WITH_TURN_JUDGMENT": "Stop 的拐彎判斷擋下時，「順手看到最該修」該問就接在同一則擋訊息後面一起問（記問過）：補一次就兩件都寫，"
                                   "不再擋完又另讓對話續跑一輪。跟 PICK_ONE_PRE_CLOSE 同一個開關。",
    "SECOND_OPINION_BACKGROUND": "第二意見背景跑、收尾不等它：開關 second_opinion.auto.background（缺＝開）開時，第二意見閘的擋訊息寫"
                                 "「start 後不用等結果，先把收尾其餘的事做完；收尾時還在跑就寫等第二意見｜<job_id>（不算宣告完成、不擋）」"
                                 "（second_opinion_hint_background；判定、門檻、擋次都不變，還在跑照 SECOND_OPINION_WAITING_NOT_DONE）；"
                                 "MCP 端 second_opinion_start 的下一步與 second_opinion_result 的說明同一個說法。關了照舊寫 start 後直接呼叫 result 等結果。",
    "SECOND_OPINION_DONE_NOTICE": "本 session 開的第二意見 job（這批 second_opinion_start 自己回的 job_id，或收尾寫了等第二意見｜<job_id>；"
                                  "不掃 job 目錄：job_id 裡只有 session 前 8 碼，掃目錄會收進別的 session 的 job）記進看守"
                                  "（state second_opinion_watch）；從在跑變成 done／failed／blocked 而 AI 還沒取回（這批或本回合沒有對那個 job 的 "
                                  "second_opinion_result）→ 附一次「取回、補四行」：下一批工具回應（PostToolBatch）或收尾（Stop 跟最該修同一則）"
                                  "先到先送，每個 job 只送一次、留帳 guard-second_opinion event=done_notice。開始看守時已經跑完的 job 不提醒。"
                                  "收尾寫過等第二意見｜<job_id> 的 job，取回它跑完的那一回合照宣告完成判（要四行或宣告不需，不再說完成也要；擋次照 "
                                  "SECOND_OPINION_REQUIRED）：在等的結果回來就得接上，不能靠之後不說完成跳過。"
                                  "跟 SECOND_OPINION_BACKGROUND 同一個開關；取回之後照 SECOND_OPINION_RESULT_ACROSS_TURNS 判跑過。",
})

SO_BACKGROUND_WAITS = ("start 後不用等結果：先把收尾其餘的事做完（驗證、文件、收尾檢核），跑完了系統會在下一批工具回應或收尾時提醒你取回；"
                       f"收尾時還在跑就寫一行 `{SO_WAIT_LINE}`（那次不算宣告完成、不擋），跑完了用 second_opinion_result 取回"
                       "（跑完了馬上回；還在跑它會等，每次最多約 100 秒）、補四行")


def second_opinion_hint_background() -> str:
    """SECOND_OPINION_BACKGROUND：擋訊息末尾的入口，同 second_opinion_hint，只換掉「start 後直接呼叫 result 等結果」那句。"""
    return second_opinion_hint().replace(SO_RESULT_WAITS, SO_BACKGROUND_WAITS)


# ─── 收尾三段一次交齊（事實與時點在 handlers/post_tool_use.py 收尾檢核段、handlers/stop.py 目標對照段、wg_closing_round.closing_call，這裡只登錄規則名與說明） ───
RULES.update({
    "CLOSING_RECONCILE_IN_REPORT": "收尾檢核（anti_evasion_report）可帶 reconcile 欄＝need_goal action=reconcile 的 {items, turns?}：MCP 端同一套驗法、"
                                   "PostToolUse 交給同一個入口 wg_need_goal.apply_op（同一套判法、同一段回覆、同樣記進目標檔，報告記 reconcile="
                                   "applied／rejected／off／error），先套用再附樹給 HUD。跟 harvest_items（CLOSING_REPORT_ONE_CALL）一起交＝收尾三段"
                                   "一次交齊，Stop 不再要求另呼叫 need_goal reconcile、knowledge_harvest_report；套不上只少這段，收尾檢核照收，"
                                   "回覆寫明只要補交對照。分開交的舊走法照收。總開關關時不驗、不套用。",
    "CLOSING_MISSING_PART_HINT": "收尾段的擋訊息寫明缺哪段、怎麼補，跟工具說明同一個說法：(f2) 擋下時本回合交過收尾檢核 → 只補 need_goal reconcile、"
                                 "收尾檢核不重交；還沒交 → 目標對照放進收尾檢核的 reconcile 欄一次交。收尾檢核閘擋訊息與「後面還會擋」預覽"
                                 "（收尾檢核、知識收割兩列）都寫一次交齊的走法。判定不變。",
    "CLOSING_GOAL_CODING_ONLY": "目標對照的 (f2) 完整對照與 (f3) 改到的部位掛目標只在寫碼回合判（stop.py 的 _coding：本回合改了程式或宣告了寫碼樹，"
                                "或前幾回合改過程式、這則宣告完成或本回合交了收尾檢核）；不是寫碼回合（例：續接單匯入的舊樹、本 session 沒改程式）宣告完成不要求。"
                                "(f1) 記進度、(f4) 記憶知識類輕樹照舊。",
    "CLOSING_CALL_ALL_THREE": "收尾那批（wg_closing_round.closing_call：收尾前附著點、第二意見接縫都靠它）認三支：收尾檢核（一次交齊時三段都在裡面）、"
                              "need_goal action=reconcile、knowledge_harvest_report；任一支所在的那批就是收尾前最後一個工具回應。",
})


# ─── 定位與立樹先提示後擋（提示在 hooks/wg_overview._locate_read_hint；立樹判式 wg_need_goal.tree_owed_for_edit 與 edit_gate 共用） ───
RULES.update({
    "LOCATE_HINT_ON_FIRST_READ": "讀檔時注入導讀卡的部位，本 session 第一次讀到它的程式檔（Read／唯讀 Bash／PowerShell／Grep，PostToolUse 的"
                                 "讀檔結果，不掛在改檔的 PreToolUse）→ 附一行：還沒有目標樹就先 need_goal set（判式與 edit_gate 同一支"
                                 "_edit_gate_applies＋目前的樹），交定位四行（根因層兩候選＋選擇理由、批判先下判斷；need_goal 關＝三行，"
                                 "同缺定位擋訊息 LOCATE_ASK_ONCE），放同一則先發的不寫檔指令開頭的 # 註解、其次早一則的回覆文字、thinking 讀不到"
                                 "（DECL_HINT_KEEPS_EDIT_TOOLS 的 DECL_WHERE）；立樹與定位併成同一行。一部位一 session 一次，第二個部位起只點名、說格式同前；"
                                 "改檔時才補注入的部位、已交過定位、非程式檔、子代理讀的、v6 總開關關都不送；沒有改程式的意圖（既不是寫碼回合 wg_core.coding_turn，"
                                 "這則 prompt 的關鍵字也沒判成寫碼類 wg_core.CODE_INTENTS；提示要趕在第一次改檔前到，所以關鍵字意圖算數）不送、也不消耗一部位一次的額度（locate_hint 留在 due，之後成了寫碼回合再讀到照送）。"
                                 "判定不動；送過就算提醒過（記進 remind_sent：LOCATE_BEFORE_EDIT、"
                                 "要立樹時 CODE_EDIT_NEEDS_GOAL_TREE），之後沒照做不擋、也不再提醒（GATE_MODE_TABLE）。",
})


# ─── 第二意見看事實觸發（事實與時點在 hooks/wg_second_opinion.py、wg_closing_round.py、handlers/stop.py，這裡只登錄規則名與說明） ───
RULES.update({
    "SECOND_OPINION_FACT_TRIGGER": "第二意見閘進不進門看事實、不看措辭：本 session 改過的程式檔過門檻（檔數、行數、高風險部位，同 "
                                   "SECOND_OPINION_REQUIRED）的每次收尾都判，不再要 AI 說了完成詞（取代原本的「宣告完成時」"
                                   "與 turn_completion_text 往前找）。只有還沒到收尾的 Stop 不判（wg_second_opinion.not_closing；這個使用者回合"
                                   "沒交收尾那批（closing_call）才算）：中途問使用者，即收尾這則最後一行（程式碼區塊外）是問句、這則沒宣告完成；"
                                   "或寫明之後工作還在繼續，即 wg_evasion 判完成的排除詞第一類（仍在等、等待…回報、尚未開始，同一份詞）。"
                                   "不判時留帳 event=deferred（kind＝question／pending），欠帳不消，下一次收尾照欠。"
                                   "出口照舊兩條：「不需第二意見｜<理由>」或「等第二意見｜<job_id>」（跑過＋四行也算），都留帳。",
    "SECOND_OPINION_EXIT_FINGERPRINT": "一組改動只欠一次：交了出口（不需／等第二意見、跑過＋四行）就記出口時的改檔指紋（state "
                                       "second_opinion_exit：本 session 程式檔的路徑＋最後改的時間與回合；收尾的出口行在所有收尾閘前面先記，"
                                       "前面的閘擋下、補件那則不重寫出口行也算）；之後的收尾指紋沒變 → 不欠（Verdict 規則名用本條），"
                                       "本回合取回在等的結果不在此列（要四行；在等的 job 跟指紋一起記在出口帳 jobs，不靠背景看守開關）。出口是不需或等第二意見、之後又改了程式（指紋變了，改 1 支也算）"
                                       "→ 再欠一次；出口是跑過＋四行，之後的修改照 SECOND_OPINION_ONCE_PER_CLAIM（採納意見不再欠）。",
    "SECOND_OPINION_PRE_CLOSE": "收尾那批（closing_call 認的：收尾檢核或完整對照）照 Stop 同一套事實先判第二意見（"
                                "wg_closing_round.so_pre_close），欠就把 Stop 會擋的同一段（wg_second_opinion.owed_message）附在那批的回應"
                                "後面，AI 第一次寫收尾就寫出口行、不再被 Stop 多擋一輪；同一個使用者回合附過、改檔指紋沒變就不重附。"
                                "那批沒出現（沒交收尾檢核也沒完整對照）→ Stop 照舊擋；附了沒照做 → Stop 照擋（判定、擋次不變）。"
                                "留帳 guard-second_opinion event=pre_close（owed、sent）。",
})


# ─── 驗證批次閘（PreToolUse Bash／PowerShell；事實與擋次在 hooks/wg_verify_batch.py，這裡只登錄規則名與說明；不歸 v6 開關管） ───
RULES.update({
    "VERIFY_FULL_RUN_NEEDS_USER_ORDER": "會拖時間的整組驗證（run_verify.py 不帶參數；pytest 沒點名檔，即沒有位置參數或只有目錄，也沒 -k／-m／--lf 這類縮範圍選項；"
                                        "PYTEST_ADDOPTS 縮了範圍不算整組；會拖時間＝同一組指令最近一筆收據耗時 ≥ guard.verify_batch.slow_run_s〔只有自寫收據記了"
                                        " started_at 能算，算不出當不知道〕或 指令跑的樹底下符合 verify_case_globs 的測試檔 ≥ large_suite_files〔數到門檻停、"
                                        "state.verify_batch_suite_files 每根快取一筆〕）要本回合使用者原話有口令（guard.verify_batch.full_run_keywords，預設 整組／全量／"
                                        "全部測試／run_verify；原話取法同 CommitOrder：state.turn_prompts 經 user_typed_prompts，背景通知、子代理回報不算）"
                                        "→ 沒口令擋，擋訊息說上次耗時幾秒／測試檔幾支。不拖時間（含不知道）的整組沒口令也放行、留帳 reason=small。"
                                        "解析不了的指令（heredoc、eval、bash -c）不管。",
    "VERIFY_SAME_BATCH_ALREADY_GREEN": "同一組驗證指令（self_receipt 正規化後的 程式＋參數；`python -m pytest` 與 `pytest` 同一組、直譯器選項不算）"
                                       "最近一筆收據是綠的（沒有 FAIL 哨兵、結束碼 0；自寫收據 exit_code=0 且 failed=0），而且收據之後本 session"
                                       "（子代理看自己的 agent_modified_files）沒有改檔（收據 seq 對改檔 last_seq；自寫收據沒 seq 就比 UTC 時間）→ 擋"
                                       "「這批改動已驗證過：收據時間、指令、綠」。上次紅、之後有改檔、改檔少序號又少時間（分不出先後）→ 放行。"
                                       "口令只開整組的門、不洗掉已驗過：全量綠了沒改檔再跑全量照擋。",
    "VERIFY_BATCH_BLOCK_ONCE_PER_TURN": "驗證批次閘每個使用者回合每條規則最多擋 1 次（wg_core.deny_cap cap=1），第 2 次放行、留帳 released、stderr 說明已放行；"
                                        "擋訊息格式 `✗ (r) <規則名>：<一句現象>｜證據：<一行一證據>`；擋下與放行都留帳 Logs/guard-verify_batch.jsonl；"
                                        "閘自己出錯放行留帳 error（GATE_SELF_ERROR）。",
})


# ─── 擋或提醒（RULE_MODE）：v6 守門每條規則照擋（block）還是提醒（remind），判定與送法只讀這一處 ───
# 照擋只三類：病形閘（含防繞）、改使用者資料檔／改舊測試沒先宣告、測試沒過卻說修好；其餘 v6 守門一律提醒。
# 「不在範圍」是不屬於 v6 的安全與權限邊界（版控口令、記憶寫入、svn 測試路徑），照擋、不讀本表。
# 本段放在檔尾、最後算 RULE_MODE：之後再加規則的段落要同時把它登進本表（verify_release_rules 掃表案會紅）。
RULES.update({
    "COMMIT_SMELL_NEW_BLOCKS": "commit／svn commit 那刻，這次提交新寫進的病形（巢狀過深、匿名區塊過長…，判法在 tools/project-smells.py check_commit）"
                               "→ 擋；拆不出要提交什麼（包在 bash -c、--git-dir、查不到的別名）判不了也擋。舊碼原本就有的只列出、不擋。"
                               "判法在 handlers/pre_tool_use.check_smell_gate。",
    "RED_TEST_BLOCKS_COMPLETION": "本 session 自己跑紅、還沒綠的測試在，收尾宣告完成 → 擋（紅測閘，handlers/stop._testfail_gate）；"
                                  "預算、放行、豁免照 BLOCK_BUDGET_SHARED、USER_WAIVER_NEEDS_CITATION、BASE_RED_TRACKED_NOT_OWED。"
                                  "紅只在宣告完成的收尾才被拿出來判：沒宣告完成的回合不判、也不算判過不算，那筆紅照留，之後哪個回合宣告完成就擋"
                                  "（改完程式跑紅、之後沒再跑綠，不管隔幾回合照擋）。判過不算的一律落帳、之後的收尾不再拿它擋：使用者放行記 user_released"
                                  "（RELEASE_COVERS_SHOWN_ITEMS）、不做行記 testfail_waivers（USER_WAIVER_NEEDS_CITATION）、收尾寫的負向對照宣告把那筆搬到"
                                  " deliberate_reds（NEGATIVE_CONTROL_DECLARED 收尾入口）。同一條指令跑了不只一次測試的紅在記帳時就定案（RED_LAST_RESULT_IN_COMMAND），"
                                  "不等收尾。擋訊息抬頭「還有 N 支沒跑綠」只在真的有綠掉幾支時附「（M 支已綠）」。",
    "CODE_EDIT_NEEDS_GOAL_TREE": "改程式檔時這個需求還沒有目標樹（wg_need_goal.edit_gate）：v6 開時提醒一行 need_goal set，不擋。",
    "OVERVIEW_CARD_BEFORE_EDIT": "改某部位的檔時本 session 還沒看過這個部位的導讀卡（wg_overview.on_edit 的 not_injected）：提醒、卡隨改檔結果送到。",
    "OVERVIEW_CARD_MISSING": "部位表列了導讀卡、卡檔卻找不到（wg_overview.on_edit 的 card_missing）：提醒列出找過哪裡。",
    "OVERVIEW_PART_FILES_READ": "改某部位的檔前要讀過這個部位的檔與卡指到的檔（min_overview_evidence，wg_overview.on_edit 的 evidence）：提醒、不擋。",
    "COMMIT_GOAL_RECONCILED": "commit 前目前寫碼類樹的完整對照 (f2) 與改到的部位掛目標 (f3)（wg_need_goal.commit_gate）：提醒、不擋。",
    "DEFERRAL_OF_DOABLE_WORK": "主任務完工、context 還夠，收尾把帶受詞、可做的事推給下個 session／獨立議題／非我造成（wg_evasion.deferral_gate_reason）。",
    "HARVEST_AT_PHASE_DONE": "階段完工要交知識收割清單（wg_harvest.harvest_gate_reason；背景收割開著就交背景）。",
    "HARVEST_ITEM_NEEDS_RECEIPT": "收割回報裡的項目要對得上寫卡收據（wg_harvest.pending_gate_reason）。",
    "CLOSING_CHECK_REQUIRED": "動到 core 檔或多檔、宣告完成，本回合要交收尾檢核 anti_evasion_report（handlers/stop.py ScanReport 段）。",
    "CLOSING_CHECK_MEMORY_NOT_DEFERRED": "收尾檢核 (d)／(h) 不得把寫 atom 推到之後（post_tool_use 判 d_pending，handlers/stop.py AEC-Pending 段）。",
    "SYNC_REMINDER_UNSYNCED": "本 session 改過的檔還沒 commit 或還沒 push，要照口令規則交代（handlers/stop.py SyncReminder 段；口令閘本身不在此）。",
    "SYNC_BLOCK_PENDING_ITEMS": "還有待記知識或文件漂移沒處理（handlers/stop.py 底部同步段，SYNC_BLOCK_NEW_ITEMS_ONLY）。",
    "DEEP_POSTMORTEM_ON_FAILURE": "這個 session 有真失敗訊號，結束前補一張完整檢討卡（handlers/stop._should_deep_postmortem）。",
    "ATOM_CONSUMPTION_AUDIT": "注入的指標卡要回報有沒有用到（handlers/stop._audit_pointer_atom_consumption）。",
    "EVASION_FLAG_NEXT_PROMPT": "收尾文字有退避語：記旗標、下一則使用者訊息時注入（wg_evasion.detect_evasion），不續跑。",
    "REMIND_ON_PRIOR_RESULT": "提醒掛在前一個動作的工具結果（PostToolUse），不掛 PreToolUse 的 additionalContext；收尾類的要求掛在改程式檔那則"
                              "工具結果，Stop 只留帳、不續跑、不開放行題。提醒一行內：規則名＋現象＋做法（remind_line），不附卡全文；"
                              "同一條規則同一個對象同一個 session 只提醒一次（remind_due）。",
    "GATE_MODE_TABLE": "v6 守門照擋或提醒只看 RULE_MODE：三類（RULE_CLASS 標病形／宣告／紅測）是 block，其餘 v6 守門是 remind；"
                       "表上沒登的規則名當 block（行為不變）。總開關關時一律照舊（gate_mode 回 block），判定不放寬。",
    "LOCATE_BEFORE_EDIT": "改某部位的程式檔前要交定位行（wg_overview.on_edit 的 evidence／wrong_layer／locate_content 缺件）：v6 開時提醒一行、不擋；"
                          "第一次讀到該部位程式檔的讀檔結果（LOCATE_HINT_ON_FIRST_READ）送過就算提醒過，之後沒交不再提醒也不擋；"
                          "唯一例外：每部位本 session 第一次改程式檔的那個使用者回合、定位沒交齊 → 整輪照擋（LOCATE_FIRST_EDIT_BLOCKS_ONCE）。",
    "OVERVIEW_READONLY_PATHS": "寫入目標命中這一層 readonly_paths（程式產物／索引）：不在 v6 守門範圍，照擋、不注入（wg_overview.on_edit 的 readonly）。",
    "OVERVIEW_HUB_UNDER_V6": "OverviewHub 整道（導讀卡注入、候選前 N、讀檔記錄、定位）綁 v6 總開關：v6 關時 wg_overview._cfg 的 enabled 一律 False，"
                             "不注入、不記、不擋；同事預設關 v6 就完全不會收到導讀卡。",
    "LOCATE_FIRST_EDIT_BLOCKS_ONCE": "定位閘在提醒模式下的例外（使用者裁「第一次改檔前沒先說清楚就攔一次」，一次＝一輪）：同一 session 第一次改某部位的程式檔"
                                     "（送卡那一刀；子代理同主 session）先驗定位行：交了就放、卡照舊當提醒件送；沒交 → 擋，訊息＝卡＋定位要求（一次交齊四行），"
                                     "卡同時排進提醒，這一輪開始。這一輪＝第一次改它的那個使用者回合、定位交齊之前：同部位之後每個改檔（同一則回覆平行送的也是）"
                                     "一行都沒交就照擋，訊息只一句「同一輪，定位交齊前照擋：<檔>」，不計 GATE_DENY_CAP、不記進 overview_locate_blocked；"
                                     "交齊（transcript 三管道或 need_goal 的 locate 欄）就結束這一輪、放行，之後只看讀檔證據；交了但內容不過走一般判定"
                                     "（有詳細缺件、計 GATE_DENY_CAP、送法照 GATE_MODE_TABLE）。下一個使用者回合還缺只提醒不擋。"
                                     "判定 wg_overview._first_edit_once（第一刀）與 _locate_round_check（同一輪後續），state.locate_first_deny[session][部位]＝"
                                     "{turn: 第一次改的使用者回合, done: 交齊了沒}（locate_first_deny_due 開輪、locate_round_open 判、_mark_located 結輪）；"
                                     "送法 pre_tool_use（第一刀提醒件帶 block_once，後續 deny 不帶提醒件；state 記不住就只提醒），"
                                     "留帳 hub log event=edit_blocked_once（第一刀）／edit_blocked_round（後續）／edit_round_located（交齊那一刀）。",
    "REMIND_PENDING_IN_STATE": "工具前守門判成提醒的那一件先記進 state remind_pending（規則名、對象、現象、做法、順帶要注入的卡），"
                               "下一個工具結果（PostToolUse）取走：該提醒的併進 additionalContext、記進 remind_sent；送過的只留帳不重送"
                               "（wg_overview.remind_queue／remind_flush）。state 寫不進去就只 stderr＋留帳，不改用 PreToolUse 送。"
                               "remind_sent 是**一份清單**（元素 remind_key(規則, 對象)；state 本來就一 session 一檔，不按 session 分桶），"
                               "工具前守門與改程式檔那批的收尾類提醒（post_tool_batch.closing_reminders）都走 wg_overview.remind_mark 記同一份；"
                               "讀到舊寫法的 dict 由 remind_sent_list 攤平，不炸。",
    "GOAL_RECONCILE_AT_DELIVERY": "(f2) 交付前目前寫碼類樹的完整對照（need_goal reconcile；判法 wg_need_goal._f2_text）：v6 開時提醒，"
                                  "Stop 只留帳；commit 前那份歸 COMMIT_GOAL_RECONCILED。",
    "GOAL_TREE_SET_ONCE": "目標樹只立一次：改程式前還沒樹才提醒一行 need_goal set（CODE_EDIT_NEEDS_GOAL_TREE），之後不再送任何會促使 AI 去呼叫"
                          "need_goal reconcile／verify_scope 的文字：改程式檔那則工具結果不附 SCOPE_*、(f2)(f3)(f4)（post_tool_batch.closing_reminders），"
                          "PostToolUse 改程式檔不問驗證範圍（原 SCOPE_ASK_ONCE_PER_CODE_TURN 拿掉），收尾檢核的提醒與預覽不寫「目標對照放 reconcile」，"
                          "need_goal set 的回覆、MCP 工具說明都不寫接著對照（沒樹改知識類檔已不送提示，見 NON_CODING_TURN_NO_NUDGE）。判定不動：Stop 照判、只留帳（STOP_REMIND_LEDGER_ONLY）；"
                          "交付時完整對照由程式照收據代填（RECONCILE_BY_PROGRAM）；AI 自己交的 reconcile／verify_scope 照收。v6 關整道不動（照擋）。"
                          "為什麼：提醒一句 AI 就多呼叫一次工具＝多一個模型回合、多載一次工具定義。",
    "STOP_REMIND_LEDGER_ONLY": "Stop 遇到提醒類規則（gate_mode 回 remind）：判定照跑、一回合一次的記號照記，但只留帳（guard log "
                               "event=remind）＋stderr 一行，不 output_block、不送 additionalContext 續跑、不開【收尾放行確認】、"
                               "不記 pending_release、不吃擋滿預算、不算進連鎖斷路器的觸發；寫碼查核一批條目混了照擋與提醒的，只有照擋條目進擋訊息"
                               "（handlers/stop._remind_logged；子代理與裁判收尾同一套）。",
})

BLOCK = "block"
REMIND = "remind"

# 照擋的規則名 → 屬哪一類（上表三類＋不在範圍）。共用的判事實規則（SAME_FILE、TURN_SINCE_USER_PROMPT…）不決定送法，標 remind 不影響照擋閘使用。
RULE_CLASS: Dict[str, str] = {
    **dict.fromkeys(("COMMIT_SMELL_NEW_BLOCKS", "GATE_BYPASS_NEEDS_DECLARATION", "GATE_BYPASS_NAMED_FILES_MERGED"), "病形"),
    **dict.fromkeys(("USER_DATA_FILE_NEEDS_DECLARATION", "DATA_FILE_DECL_VOIDED_BY_LATER_MENTION",
                     "OLD_TEST_CHANGE_NEEDS_DECLARATION", "OLD_TEST_COMPARED_ON_FAILED_COMMAND",
                     "OWN_COMMIT_CHANGES_STILL_COMPARED"), "宣告"),
    **dict.fromkeys(("RED_TEST_BLOCKS_COMPLETION", "RED_ITEMS_ONLY_FROM_FAILURE_LINES", "RED_SCOPE_FROM_FULL_COMMAND",
                     "GREEN_CLEARS_ONLY_CASES_IT_RAN", "GREEN_NARROWED_KEEPS_UNCOVERED_RED", "GREEN_SAME_CASE_CLEARS",
                     "USER_WAIVER_NEEDS_CITATION", "BASE_RED_TRACKED_NOT_OWED", "NEGATIVE_CONTROL_DECLARED",
                     "RED_LAST_RESULT_IN_COMMAND", "RED_WHILE_REVERTED", "BLOCK_BUDGET_SHARED", "RELEASE_COVERS_SHOWN_ITEMS", "PENDING_SAME_USER_TURN",
                     "NONINTERACTIVE_RELEASE_AT_BUDGET", "CLAIM_FIXED_NEEDS_PASS", "CARRIED_CLAIM_ANY_TURN_RECEIPT",
                     "CLAIM_WORDS_ARE_HINTS", "CLAIM_RECEIPT_REF_MATCH", "CLAIM_DISCLAIM_NEEDS_REASON",
                     "CLAIM_CONDITIONAL_NOT_CLAIM", "CLAIM_MODIFIER_NOT_OWN", "COMPLETION_CLAIM_PER_SENTENCE"), "紅測"),
    **dict.fromkeys(("COMMIT_ORDER_DECISION_ALWAYS_LOGGED", "ORDER_UNTIL_PUSH", "TEMP_REPO_COMMIT_EXEMPT",
                     "SVN_TEST_BLOCK_OPT_IN", "ATOM_BYPASS_HOWTO_REFUSED", "CONFLICT_DECLARED_BY_AI",
                     "OVERVIEW_READONLY_PATHS", "VERIFY_FULL_RUN_NEEDS_USER_ORDER", "VERIFY_SAME_BATCH_ALREADY_GREEN",
                     "VERIFY_BATCH_BLOCK_ONCE_PER_TURN", "LOCATE_FIRST_EDIT_BLOCKS_ONCE"), "不在範圍"),
}
RULE_MODE: Dict[str, str] = {name: BLOCK if name in RULE_CLASS else REMIND for name in RULES}

# 寫碼查核的條目字母 → 決定這一條送法的規則（同一個字母的擋訊息可能帶判宣稱的共用規則名，送法照字母的主規則）
LETTER_RULE: Dict[str, str] = {
    "a": "CLAIM_FIXED_NEEDS_PASS", "b": "CLAIM_MEASURED_NEEDS_DONE", "c": "CLAIM_TRIED_NEEDS_EXEC",
    "d": "CASE_COVERS_CHANGE", "v": "MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE", "e": "AEC_EVIDENCE_PATH",
    "f3": "EDITED_PART_NEEDS_GOAL_NODE", "f4": "KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE",
}
REMIND_LINE_CAP = 240


# Stop 原本會擋、v6 開時改成提醒的規則：說明文字補一句現況（判定與原文不動；送法見 GATE_MODE_TABLE／STOP_REMIND_LEDGER_ONLY）
for _name in ("CASE_COVERS_CHANGE", "CASE_DECLARED_FOR_CHANGE", "NO_CASE_NEEDS_USER", "CLAIM_MEASURED_NEEDS_DONE", "CLAIM_TRIED_NEEDS_EXEC",
              "MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE", "AEC_EVIDENCE_PATH", "AEC_FOLLOWUPS_EMPTY", "SCOPE_DECLARED_FOR_CHANGE",
              "SCOPE_ITEM_RECEIPT_AFTER_EDIT", "EDITED_PART_NEEDS_GOAL_NODE", "KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE",
              "KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY", "TURN_JUDGMENT_REQUIRED", "SECOND_OPINION_REQUIRED", "SECOND_OPINION_DECLINED",
              "REFACTOR_NEEDS_EQUIVALENCE", "PERF_HOT_PATH_NEEDS_MEASURE", "LEFTOVER_NEEDS_CLEANUP", "RELOAD_ADVICE_ALREADY_LOADED",
              "DEFERRAL_OF_DOABLE_WORK", "HARVEST_AT_PHASE_DONE", "HARVEST_ITEM_NEEDS_RECEIPT", "CLOSING_CHECK_REQUIRED",
              "CLOSING_CHECK_MEMORY_NOT_DEFERRED", "SYNC_REMINDER_UNSYNCED", "SYNC_BLOCK_PENDING_ITEMS", "DEEP_POSTMORTEM_ON_FAILURE",
              "ATOM_CONSUMPTION_AUDIT", "PICK_ONE_PRE_CLOSE", "SECOND_OPINION_DONE_NOTICE"):
    RULES[_name] += "｜v6 開：提醒不擋，掛在改程式檔（或觸發事實成立）那則工具結果一行（handlers/post_tool_batch.closing_reminders），Stop 只留帳 event=remind、不續跑、不開放行題；v6 關照舊擋。"

# 目標樹只立一次（GOAL_TREE_SET_ONCE）：這幾條 v6 開時連改程式檔那則提醒也不送（提醒了 AI 就多叫一次 need_goal reconcile／verify_scope），Stop 照判只留帳
for _name in ("SCOPE_DECLARED_FOR_CHANGE", "SCOPE_ITEM_RECEIPT_AFTER_EDIT", "GOAL_RECONCILE_AT_DELIVERY", "EDITED_PART_NEEDS_GOAL_NODE",
              "KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE", "KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY", "CODE_EDIT_NEEDS_GOAL_TREE", "CLOSING_CHECK_REQUIRED"):
    RULES[_name] += "｜目標樹只立一次（GOAL_TREE_SET_ONCE）：need_goal 只在改程式前提醒 set 一次；改程式檔那則不再提醒 reconcile／verify_scope，收尾檢核的提醒不寫目標對照。"


def mode_of(rule: str) -> str:
    """規則 GATE_MODE_TABLE：這條規則照擋還是提醒；表上沒登的當 block（沒分類前行為不變）。"""
    return RULE_MODE.get(str(rule), BLOCK)


def gate_mode(rule: str, v6: bool) -> str:
    """呼叫端決定送法的唯一入口：總開關關（v6=False）一律 block＝照舊；開時照 RULE_MODE。"""
    return mode_of(rule) if v6 else BLOCK


def hit_mode(letter: str, rule: str, v6: bool = True) -> str:
    """format_hit 一條（parse_hit_rules 拆出的字母、規則名）的送法：寫碼查核的字母照 LETTER_RULE 的主規則，其餘照規則名。"""
    return gate_mode(LETTER_RULE.get(str(letter), rule), v6)


def remind_line(rule: str, what: str, fix: str) -> str:
    """規則 REMIND_ON_PRIOR_RESULT：提醒一行，格式 `[Guardian:提醒] <規則名>：<現象>｜做法：<做法>`；換行壓成空白，超過上限截斷。"""
    flat = " ".join(f"[Guardian:提醒] {rule}：{what}｜做法：{fix}".split())
    return flat if len(flat) <= REMIND_LINE_CAP else flat[:REMIND_LINE_CAP - 1] + "…"


def remind_key(rule: str, obj: Any = "") -> str:
    """同一條規則、同一個對象（部位、檔、頂層目錄；空＝整個 session 一件）的提醒鍵。對象是路徑時照 canon_path 比。"""
    o = str(obj or "")
    is_path = "/" in o or "\\" in o
    return f"{rule}|{canon_path(o) if is_path else o}"


def remind_due(sent: Iterable[str], rule: str, obj: Any = "") -> bool:
    """這件提醒這個 session 送過沒（sent＝呼叫端存在 state 的提醒鍵）；沒送過才送，送了由呼叫端把 remind_key 加進去。"""
    return remind_key(rule, obj) not in set(sent or ())


# ─── 非寫碼回合不介入（判定在各自的模組：wg_need_goal.stamp_edit、ups_inject._lean_turn、wg_overview._locate_read_hint、wg_data_file.gate／read_hint；這裡只登錄） ───
RULES.update({
    "NON_CODING_TURN_NO_NUDGE": "守門「純問答與只改文件的回合不跑」的四個例外收斂：寫碼回合一律照 wg_core.coding_turn（本使用者回合改過程式檔或宣告了"
                                "寫碼樹；prompt 關鍵字意圖不算）。① 沒樹改記憶知識類檔只記 untreed（之後立樹自動掛進去）、不再送「知識類也要一棵輕樹」；"
                                "② 記憶注入瘦身（CODING_TURN_FULL_ONLY_ON_TRIGGER）看 coding_turn，不看關鍵字意圖；③ 讀程式檔附的定位提示"
                                "（LOCATE_HINT_ON_FIRST_READ）只在寫碼回合或 prompt 關鍵字判成寫碼類（wg_core.CODE_INTENTS）時送，純問答不送、額度不消耗；④ 動資料檔閘（USER_DATA_FILE_NEEDS_DECLARATION）與"
                                "它的讀檔提示（DATA_FILE_READ_HINT）只在這個 session 改過程式檔、或這次指令同時寫程式檔時管（wg_data_file.coding_session；讀檔提示另外在 prompt 關鍵字判成寫碼類時也先送，提示要趕在第一次改檔前），"
                                "否則放行、留帳 skipped_non_coding。第一則訊息的「要改碼先立樹」一行（CODE_TREE_HINT）仍看關鍵字，不在此列。",
})
RULE_MODE.setdefault("NON_CODING_TURN_NO_NUDGE", REMIND)   # 登在 RULE_MODE 建表之後：說明型規則，不是擋點（GATE_MODE_TABLE 要每條都有送法）

# ─── 立樹走文字管道（T2 成本：need_goal set 多一個模型回合、ToolSearch 載工具再一回合）───────────────────────────
RULES.update({
    "TREE_SET_VIA_TEXT": "立需求目標樹走文字管道，工具 need_goal(action=set) 只當備援。格式：「目標｜<整個需求一句，用使用者的話，只寫目標不寫手段>」"
                         "一行，之後可多行「子目標｜<一件子目標>」（一行一件；沒有可省）。管道與定位行相同（DECL_WHERE）："
                         + DECL_WHERE + "；thinking 不讀、程式碼區塊裡的不算、含 <…> 的佔位句不算；同一段文字最後一個「目標｜」那組算現行。"
                         "套用點：改程式檔的 PreToolUse（handlers/pre_tool_use 需求目標第一層，wg_need_goal.set_via_text 在 edit_gate 之前）："
                         "這個 session 還沒有進行中的樹、主 transcript 本使用者回合（最後一則使用者本人打字之後）或子代理檔裡有「目標｜」"
                         "→ 組成與 need_goal(action=set, kind=code, goal, items=[{text}]) 等價的輸入呼叫 apply_op，state 效果與 PostToolUse 收工具"
                         "呼叫相同（need_goal_code_decl_turn＝本回合）；這裡立的一定是新樹，不作廢之前交的定位、不動掃描起點（AI 多半先寫目標行、再交定位、才第一次改檔）；同一使用者回合 transcript 沒長就不重讀"
                         "（state need_goal_text_scan）。留帳 Logs/guard-need_goal.jsonl event=set_via_text（拒收 set_via_text_rejected、"
                         "出錯 set_via_text_error 不擋，沒樹照舊由 edit_gate 判）。同一則回覆裡的定位四行與「動資料檔｜」各走自己的解析器。",
})
RULES["GOAL_TREE_SET_ONCE"] += ("｜立樹本身走文字管道（TREE_SET_VIA_TEXT）：提醒 set 那一行教的是「目標｜」行，need_goal(action=set) 只當備援，"
                                "照做的成本是零個模型回合。")
RULES["CODE_EDIT_NEEDS_GOAL_TREE"] += ("｜擋／提醒訊息教的是寫「目標｜…」行（子目標每件一行「子目標｜…」），先放同一則先發的不寫檔指令開頭的 # 註解、"
                                       "其次早一則的回覆文字（DECL_WHERE），改檔時 hook 照它立樹（TREE_SET_VIA_TEXT）；need_goal(action=set) 只當備援。")
RULE_MODE["TREE_SET_VIA_TEXT"] = REMIND     # 不是閘（立樹成功只附一行、失敗留帳不擋）；RULE_MODE 在上面算完，這裡補登
