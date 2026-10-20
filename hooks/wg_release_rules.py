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

RULES: Dict[str, str] = {
    "SAME_FILE": "同一個檔不同寫法（反斜線／正斜線、大小寫、`..`）是同一個檔：去重、快照成員、同根比較一律用 canon_path。",
    "TURN_SINCE_USER_PROMPT": "本回合＝使用者打字開的那一回合到現在的每個 turn_seq；同伴 session 訊息、背景通知不另開回合"
                              "（收據、改檔、commit、收尾報告、收割、注入都照這個窗口算）。",
    "CLAIM_MODIFIER_NOT_OWN": "宣稱詞後面直接接「的＋名詞」（修好的 X、跑過的測試）是形容後面的東西、常是轉述，不算自己宣告完成。",
    "OWED_AFTER_LAST_CASE": "驗證範圍閘關掉（verify_scope.enabled=false）時的退路：本 session 最後一次改仍存在的案例檔之後，同根還改過程式檔"
                            " → 欠補案例。開著時改看 CASE_DECLARED_FOR_CHANGE（由哪個案例驗交 LLM 宣告）。",
    "GONE_OUTSIDE_VCS": "改過的程式檔已不存在、也不在任何版控根內（打錯路徑寫到 worktree 外又刪、worktree 被移除整根消失）"
                        "→ 算刪除、不欠：同根的案例無從補，也沒有 status 可查搬去哪。",
    "GONE_IN_GIT_NOTHING_NEW": "改過的程式檔已不存在、在 git 根內、同根 status 與本 session 提交都沒有它的副本（沒有新出現的程式檔，"
                               "或新出現的檔名與內容都和它不同）→ 算刪除、不欠。",
    "MOVED_NEW_CODE_SEEN": "改過的程式檔已不存在、同根 status 或本 session 提交出現它的副本 → 可能是搬過去了，照欠。副本＝新出現的程式檔裡"
                           "檔名相同（不分大小寫）、或內容與它最後一次寫入時相同；它沒有內容紀錄、新檔讀不到 → 判不出，全算副本。",
    "GONE_UNVERIFIABLE": "改過的程式檔已不存在、但在 svn 工作副本裡、或查 git 失敗／逾時 → 判不出去向，照欠。",
    "EXCLUDED_REGION": "屬部位表類別 knowledge 的部位（文件、記憶、派工信箱；錨在專案根的最長前綴列）的檔是素材，"
                       "被 .gitignore 忽略或屬執行期資料的檔（與 RUNTIME_DATA_NO_OVERVIEW 同一判式）不是本專案程式：兩者都不算程式、"
                       "也不能拿來清帳。沒有部位表、沒標類別、追蹤中、判不出 → 照算程式。",
    "SNAPSHOT_SETTLED": "commit 那刻不欠案例、之後同根程式檔內容都回到那刻、git status 乾淨（含暫存區）→ 不重算補案例（wg_verify_ledger）。",
    "NET_UNCHANGED": "改過又原樣還原（它自己與 HEAD 相同、之後沒 commit、同根程式檔 git status 全乾淨）→ 不算改碼（wg_verify_ledger）。",
    "EXEMPTION_PEERS_CODE_ONLY": "SNAPSHOT_SETTLED、NET_UNCHANGED、COMMENT_ONLY_CHANGE 要一起比的同根改檔只看程式檔（案例檔也是程式檔）："
                                 "文件、紀錄檔、設定、資料改了或正被別的 session 改著，不擋豁免；程式檔或案例檔本身沒回到那個狀態照擋"
                                 "（wg_verify_ledger.exemption_peers）。",
    # ── 045（track-gate-rules）起：誤判清冊 B／C 組 ──
    "CASE_GREEN_AFTER_EDIT": "與 OWED_AFTER_LAST_CASE 同一條退路（驗證範圍閘關掉時）：改碼之後，有本 session 改過、仍存在、同根的案例檔被跑綠"
                             "（收據點名該案例、PASS 無 FAIL、exit 0、晚於該程式檔最後一次修改）→ 不欠補案例；案例 mtime 先後只當輔助"
                             "（先紅後綠的正確順序不被擋）。",
    "BLOCK_BUDGET_PER_RULE": "寫碼查核的擋次預算每條規則（擋訊息的字母）各自計次；同一條在同一個使用者回合擋滿 max 才算擋滿；"
                             "擋滿訊息列出全部命中條目。",
    "COMMENT_ONLY_CHANGE": "程式檔與基準版本（本 session 沒 commit 過它時的 HEAD）用 ast 去掉註解、docstring、空白後相同，"
                           "同根其他程式檔也等於 HEAD 或只差註解 → 不算改碼；非 Python、解析不了、基準拿不到 → 照算。",
    "CONTENT_EQUALS_COMMITTED": "程式檔現在的 blob 等於另一方已提交的版本（MERGE_HEAD、main／master；指到 HEAD 或本 session 自己提交的 commit 不算）"
                                "→ 不是本 session 改碼（merge 取 theirs、退回 main 版都在此）；等於 HEAD 走 NET_UNCHANGED／SNAPSHOT_SETTLED。"
                                "例外：HEAD 是別人接在本 session 最後一次提交之上做的提交（總控台把 main 合進工作分支，本 session 的 commit 快照"
                                "拍在那之前）、而且同根本 session 改過的程式檔（含案例）全等於 HEAD → HEAD 也算已提交版本（退回看紅再還原不欠）。",
    "INLINE_PY_READONLY": "python -c 的內嵌碼用 ast 靜態判：無寫檔 open 模式、無刪搬寫 API、無 subprocess／shutil／exec／eval → 不算寫入，放行；"
                          "node -e、python - heredoc、pwsh -Command 判不了照擋，擋訊息指路（寫成腳本檔、python -m json.tool）。",
    "GIT_READONLY_SUBCMD": "跨層閘：指令裡每段 git 都是唯讀子命令（show、hash-object 無 -w、rev-parse、diff、log、status、ls-files、cat-file、"
                           "ls-tree、rev-list、blame、describe、branch 無改名）且沒有寫到根層的目標 → 放行；擋就留 guard-crossrealm.jsonl。",
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
    "BLOCK_LISTS_LATER_GATES": "Stop 任一道閘擋下時，附一段照目前狀態預覽後面還會擋的閘（知識收割、收尾自清、收尾檢核、同步），讓模型一回合補齊。"
                               "只讀不寫：不動 state、不吃預算；後面的閘另有每回合一次、擋滿放行等條件，以真正擋下為準。"
                               "判法在 handlers/stop.py 的 _later_gates。",
    "RUNTIME_DATA_NO_OVERVIEW": "寫入／刪除目標被 .gitignore 忽略、落在執行期資料目錄（workflow/state*、workflow/need-goal、Logs）、"
                                "或路徑含快取目錄（__pycache__、.pytest_cache、.mypy_cache、.ruff_cache；沒有 .gitignore 也算）"
                                "→ 不要求先讀同目錄的檔。",
    "BASH_READONLY_COUNTS_AS_READ": "Bash／PowerShell 唯讀讀檔指令（cat、head、tail、less、more、sed -n、grep -n、svn cat、git show、"
                                    "Get-Content…；一段裡每個路徑參數都算）執行成功後，字面路徑且是實檔的算讀過，與 Read 同效；"
                                    "含變數（$）、未展開 glob（* ? [）、指令失敗（exit≠0）、檔不存在不算；echo／printf／ls／find 不是讀檔指令。",
    "UNMAPPED_EDIT_NEEDS_READABLE_FILES":"表外檔改檔前要讀的同頂層目錄檔數＝min(設定的 part_files, 該目錄非執行期資料的既有檔數)："
                                          "目錄沒有可讀檔（只有子目錄、快取或 gitignored 產物）就不要求；有檔沒讀照擋。",
    "TEMP_REPO_COMMIT_EXEMPT": "git commit 落在暫存目錄（系統 TEMP／TMP、scratchpad、/tmp）下的 repo → 不要求版控口令。",
    "TEMP_COPY_NOT_PROJECT": "寫入目標或跑的腳本在暫存目錄下 → 不當專案：不找部位表、不注入、不要求綜觀；量尺與對帳也不把它當收據。",
    "DPM_WORKTREE_DELIVERY": "cwd 是 git worktree 的隔離 session：post-mortem 改寫進交付信由總控台代寫，不叫它 atom_write（會寫 live）。",
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
    "DISPATCH_OPENS_TURN": "回合起點＝使用者打字，或帶派工標記的跨 session 訊息（正文首行以「派工」開頭、或含 to-track-<軌> 派工檔路徑）；"
                           "一般同伴訊息、背景通知不開回合。擋次預算、ScanReport 豁免、AtomAudit、PASS 窗口、退避預告切點、有用度學習單位、"
                           "收割冷卻全吃同一個起點（user_turn／turn_prompts_seq／user_turn_count）。派工訊息不是使用者原話：口令照樣不認。",
    "VCS_ROOT_UNREADABLE": "找改檔所在版控根時檔案系統出錯（OSError：權限、網路路徑斷、路徑太長）→ 讀不到不等於不在版控：判不出去向，照欠（fail-closed）。",
    # 既有對帳條目的名字（(a)(b)(c)(e)、量尺），讓每一條擋訊息都有規則名
    "CLAIM_FIXED_NEEDS_PASS": "(a) 說「修好」：有驗證範圍宣告（need_goal verify_scope）→ 認宣告範圍內任一項在跟它有關的最後一次改動之後"
                              "跑綠的收據（SCOPE_EDIT_RELATED_TO_ITEM；session 收據或背景自寫收據，不看回合、不比檔名），"
                              "該測哪些已經由 LLM 宣告，(a) 不再用另一套答案；沒宣告才退回檔名對應：本回合對得上改檔、"
                              "晚於最後一次修改、同一棵樹的 PASS，或改檔部位的合格自寫收據。",
    "CLAIM_MEASURED_NEEDS_DONE": "(b) 說「量了」要有本回合能當證據的 DONE，或改檔部位的合格自寫收據。",
    "CLAIM_TRIED_NEEDS_EXEC": "(c) 說「試過／跑了」要有本回合的 Bash／PowerShell 執行。",
    "AEC_EVIDENCE_PATH": "(e) 收尾檢核 (j) 證據路徑缺或不存在，但本 session 有驗證收據。",
    "AEC_FOLLOWUPS_EMPTY": "(e) 收尾檢核 (k) 追蹤項是空字串（「無」才放）。",
    "RECONCILE_BLOCK_LETTERS": "寫碼查核只擋 reconcile_gate.block_letters 列出的條目字母（沒設＝全擋）；沒列的條目照判、改印 stderr "
                               "只提示不擋。live 設定只列 a（測試沒過不准說修好）與 d（改了程式要有測試），使用者拍板。",
    "CLOSING_RITUAL_SWITCHES": "收尾儀式各有開關，關掉就不擋收尾：reconcile_gate.goal_gate=false → 需求目標對照 (f1)～(f4) 與 commit 前的"
                               "目標對照不擋（目標樹照記）；aec.scan_report_gate=false → 沒交收尾檢核不擋；atom_audit.enabled=false → "
                               "卡片表態不擋。沒設＝照擋。",
    # 需求目標樹的完整對照（wg_need_goal 收事實、這裡判）
    "GOAL_DONE_NEEDS_CASE_OR_RECEIPT": "寫碼類目標樹標「達成」的節點，至少一筆證據是沒紅的收據（實測）或讀碼級的驗證案例；"
                                       "只有檔案、卡片、推論級案例或紅收據 → 擋，擋訊息列節點與現有每一筆證據。記憶知識類的樹不擋。",
    "GOAL_INFERRED_MAX_PARTIAL": "標「達成」的節點證據全是推論 → 擋（推論最多標部分），不分寫碼類或記憶知識類。",
    "CASE_RED_THEN_GREEN": "完整對照的案例證據，對上目標檔收據裡點名同一案例檔「先紅、之後綠」的序列 → 該筆證據記 red_then_green；"
                           "收據點名哪些案例檔在蓋號時用完整指令與它的 cwd 解成絕對路徑，指令裡換目錄或沒記 cwd 的不比。"
                           "對不上照收，對照摘要印「案例未見先紅」。只是紀錄，不是閘。",
    # G0 綜觀：動手前說出角色與兩個根因候選、收尾查改到的部位都掛到目標（wg_overview／wg_need_goal 收事實、這裡判）
    "LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES": "有需求目標樹時改寫碼部位的定位四行：第四行「定位｜目標：<節點>（<角色>）」括號內要寫"
                                                 "這一塊在目標裡的角色（非空、不是佔位句、不是節點原文照抄）；第二行「定位｜根因層」要辨識得出"
                                                 "至少兩個根因候選＋選擇理由（候選 A …；候選 B …；選 A 因為 …／第一根因 …，第二根因 …），"
                                                 "或一個候選＋「第二個不存在因為 …」。只看結構不評對錯；知識類部位不查。",
    # G1 側觀：定位之後的批判與舉一反三（原話輯 G1 2026-10-15）
    "RELOAD_ADVICE_ALREADY_LOADED": "收尾文字叫使用者 Reload Window（重新載入視窗）→ 查這個 session 的工具服務程序（每個 session 的 claude"
                                    "程序底下各有自己的服務；找不到所屬 claude 程序就看全機）啟動時載入的程式版本：全部有紀錄、心跳 3 分鐘內、"
                                    "不舊於磁碟上的版本 → 這個建議多餘，每個使用者回合擋一次並附兩邊版本；列不出、讀不到、有服務沒紀錄或心跳過期、"
                                    "有任何一個還是舊的 → 放行；AI 寫明「重載原因：…」（程式更新以外的理由）照它的判斷。依據是程序樹與服務自己"
                                    "記的版本，不是 session 名稱（Claude Code 沒寫進文件的命名行為）；「有沒有叫人重載」用字詞找，只當觸發點。",
    "LOCATE_LINES_NEED_CRITIQUE": "有需求目標樹時改寫碼部位，定位四行之後要第五行「定位｜批判：…」：下「合理」或「不合理」的判斷並附理由"
                                  "（因為／理由／原因／由於），不合理要寫更好的做法（更好／改成／應該／改用／換成），還要寫「同類還可能在哪：…」"
                                  "（或「無，因為…」）。同類欄位認最後一個「同類…：」標籤（理由裡提到同類不切斷）；「無」後面接標點、"
                                  "理由詞或行尾才算沒有同類（「無鎖佇列」是位置）。照抄範本不算交。與定位四行同一支判定、每個部位交一次；"
                                  "只看結構不評對錯，知識類部位不查。",
    "LOCATE_LINES_NO_EXAMPLE_PLACEHOLDER": "有需求目標樹時改寫碼部位，定位各行（部位／根因／前例／目標／批判）還留著擋訊息範例的角括號佔位"
                                           "（角括號裡有中文說明，如 <第一個根因>）→ 當沒填、照擋；程式的泛型角括號（List<int>）不算。"
                                           "查的是有沒有填，不評內容。",
    "EDITED_PART_NEEDS_GOAL_NODE": "交付邊界與 commit 前：目前寫碼類目標樹上，本 session 改過程式檔的每個寫碼部位，都要在定位帳"
                                   "（目標檔 links.parts）掛到樹裡還活著的節點；沒交過、掛的節點已放棄或不在樹 → 擋，列"
                                   "「<部位>：<改的檔> 沒掛目標」並指路補交定位四行或 need_goal add 子目標。表外的檔、知識類部位、"
                                   "OverviewHub 在那一層關掉的不算。",
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


_MODIFIER_TAIL_RE = re.compile(r"^的\s*[^\s，。；！？、,.;!?：:）)」』]")


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


def owed_after_last_case(name: str, last_case: Optional[str]) -> Verdict:
    """OWED_AFTER_LAST_CASE：照修改時間判下來欠補案例的程式檔，附「最後一次改的案例是哪個」當證據。"""
    tail = f"最後一次改的案例是 {last_case}，{name} 在那之後還改過" if last_case else f"本 session 沒有改過仍存在的案例檔，{name} 改過"
    return Verdict("OWED_AFTER_LAST_CASE", True, tail)


# ═══════════════════════════════════════════════════════════════════════════════
# 045（track-gate-rules）：以下一律加在檔尾，不插在上面（與 044 合併時衝突最少）
# ═══════════════════════════════════════════════════════════════════════════════

# ─── 擋訊息格式（契約） ───────────────────────────────────────────────────────
HIT_PREFIX = "✗ "
_HIT_RE = re.compile(r"^\s*✗ \(([^)]+)\) ([A-Z][A-Z0-9_]*)：")


def format_hit(letter: str, v: Verdict) -> str:
    """`✗ (<字母>) <規則名>：<一句現象>｜證據：<一行一證據>`。沒有證據就印 why 當唯一一行證據。"""
    ev = list(v.evidence) or [v.why]
    return f"{HIT_PREFIX}({letter}) {v.rule}：{v.why}｜證據：" + "；".join(ev)


def split_blocking(hits: List[str], block_letters: Any) -> Tuple[List[str], List[str]]:
    """規則 RECONCILE_BLOCK_LETTERS：format_hit 條目分成（會擋, 只提示）。block_letters 不是清單＝全擋。"""
    if not isinstance(block_letters, list):
        return list(hits), []
    keep = {str(x) for x in block_letters}
    block = [h for h in hits if (parse_hits(h) or [""])[0] in keep]
    return block, [h for h in hits if h not in block]


def parse_hits(text: str) -> List[str]:
    """擋訊息裡每一條 `✗ (<字母>) <規則名>：` 的字母（保序、去重）。BLOCK_BUDGET_PER_RULE 用它知道這次擋了哪幾條。"""
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


# ─── B2 BLOCK_BUDGET_PER_RULE ──────────────────────────────────────────────────

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


# ─── B1 CASE_GREEN_AFTER_EDIT ──────────────────────────────────────────────────

def green_after_edit_verdict(name: str, case_name: str, receipt_cmd: str, receipt_when: str) -> Verdict:
    """程式檔 name 改過之後，點名案例檔 case_name 的收據跑綠了（呼叫端已確認 PASS 無 FAIL、exit 0、晚於最後一次改碼、同根）→ 不欠。"""
    return Verdict("CASE_GREEN_AFTER_EDIT", False, f"{name} 改完之後 {case_name} 跑綠",
                   (f"收據 `{str(receipt_cmd)[:80]}` PASS exit 0", f"收據時間 {receipt_when} 晚於 {name} 最後一次修改"))


def cmd_names_file(cmd: str, path: str) -> bool:
    """收據指令是否點名這個檔：含完整檔名（整詞）或相對路徑尾段。"""
    name = os.path.basename(str(path).replace("\\", "/"))
    if not name:
        return False
    low = str(cmd or "").replace("\\", "/").lower()
    return re.search(r"(?<![A-Za-z0-9_])" + re.escape(name.lower()) + r"(?![A-Za-z0-9_])", low) is not None


# ─── B3 COMMENT_ONLY_CHANGE ────────────────────────────────────────────────────

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


# ─── B13 CONTENT_EQUALS_COMMITTED ──────────────────────────────────────────────

def blob_sha(data: bytes) -> str:
    """git blob 的 sha1（`blob <len>\\0<內容>`），不開 git 子行程就能和 ls-tree 的結果比。"""
    data = bytes(data)
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def committed_refs(own_commit_shas: Iterable[str], ref_commits: Dict[str, str], committed_since_edit: bool = True,
                   head_after_own: bool = False) -> List[str]:
    """哪些 ref 可以當「已提交版本」：MERGE_HEAD／main／master（指到本 session 自己提交的 commit 除外）。
    HEAD 平常不算：「等於 HEAD」走 NET_UNCHANGED／SNAPSHOT_SETTLED（它們還會查同根案例檔乾不乾淨，程式與案例一起退回舊版、
    只還原程式時案例還是舊的，照欠；verify_stop_reconcile 035 ⑤）。例外 head_after_own：HEAD 是別人接在本 session 最後一次提交
    之上做的提交（總控台把 main 合進工作分支）→ 本 session 的 commit 快照拍在那之前、對不上，HEAD 才是已提交版本，算；
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


# ─── B4 INLINE_PY_READONLY ─────────────────────────────────────────────────────
_WRITE_MODE_RE = re.compile(r"[wax+]")
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
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else [str(node.module or "").split(".")[0]]
            bad = [n for n in names if n in _DENY_MODULES]
            if bad:
                return Verdict("INLINE_PY_READONLY", True, f"內嵌碼匯入 {bad[0]}（可能寫檔或跑子行程）", (f"import {bad[0]}",))
            if isinstance(node, ast.Import) and any(a.asname for a in node.names):
                return Verdict("INLINE_PY_READONLY", True, "內嵌碼用 import … as 取別名，判不了呼叫的是誰", (ast.dump(node)[:60],))
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" or a.asname for a in node.names):
                return Verdict("INLINE_PY_READONLY", True, "內嵌碼 from … import 取別名或 *，判不了呼叫的是誰", (ast.dump(node)[:60],))
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


def inline_code_hint(interp: str) -> str:
    """判不了的內嵌碼（node -e、python - heredoc、pwsh -Command）的指路句。"""
    low = str(interp or "").lower()
    if low.startswith("node"):
        return "node -e 的內嵌碼閘判不了：把程式寫成腳本檔再 `node <檔>`，或改用 Read／Grep 查資料。"
    if low.startswith(("pwsh", "powershell")):
        return "pwsh -Command 的內嵌碼閘判不了：把程式寫成 .ps1 腳本檔再執行，或改用 Read／Grep 查資料。"
    return ("python - heredoc 閘判不了：只讀的話改 `python -c '<單行>'`（ast 會放行）、`python -m json.tool <檔>`，"
            "或把程式寫成腳本檔再 `python <檔>`。")


# ─── B5 GIT_READONLY_SUBCMD ────────────────────────────────────────────────────
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
                    # 唯讀子命令也有會寫檔的選項（codex 001 BLOCK 2）
                    "diff": ("--output", "-o"), "log": ("--output", "-o"), "show": ("--output", "-o"), "shortlog": ("--output", "-o"),
                    "grep": ("--output", "-O", "--open-files-in-pager")}
_GIT_OUTPUT_OPT = "--output"       # 每個唯讀子命令都認得的寫檔選項
_GIT_GLOBAL_VALUE_OPTS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix", "--config-env"})


def _git_segments_readonly(command: str) -> Tuple[bool, List[str]]:
    """每個以 git 開頭的指令段是不是唯讀子命令。回 (全唯讀, 證據)。先按換行切（shlex 會把換行當空白吞掉，第二行的 reset
    會被當成第一行 status 的參數；codex 001 BLOCK 2），再按 && || ; | & 切段（引號內不切）；引號不完整、含命令替換（$( 或反引號）
    → 判不了，當不唯讀。"""
    raw = str(command or "").replace("\r\n", "\n").replace("\r", "\n")
    if re.search(r"\$\(|`", raw):
        return False, ["指令含命令替換（$( 或反引號），判不了"]
    segs: List[List[str]] = []
    for line in raw.split("\n"):
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            return False, ["指令引號不完整，解析不了"]
        segs.append([])
        for tok in tokens:
            if tok in ("&&", "||", ";", "|", "&"):
                segs.append([])
            else:
                segs[-1].append(tok)
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


def git_readonly_verdict(command: str, root_write_targets: Sequence[str]) -> Verdict:
    """GIT_READONLY_SUBCMD：owed=False＝放行（每段 git 都唯讀、且寫入目標沒有落在根層）；owed=True＝照擋。"""
    if root_write_targets:
        return Verdict("GIT_READONLY_SUBCMD", True, "指令有寫入目標落在根層", tuple(str(t)[:80] for t in root_write_targets[:3]))
    ok, ev = _git_segments_readonly(command)
    if not ok:
        return Verdict("GIT_READONLY_SUBCMD", True, "不是全唯讀的 git 指令", tuple(ev[-2:]) or (str(command)[:60],))
    return Verdict("GIT_READONLY_SUBCMD", False, "每段 git 都是唯讀子命令且沒寫到根層", tuple(ev[:4]))


# ─── B6 GREP_CONTENT_IS_READ ／ BASH_COMMENT_LINES_STRIPPED ────────────────────

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


# ─── ⑥ DISPATCH_OPENS_TURN ／ ⑧ VCS_ROOT_UNREADABLE ────────────────────────────
_DISPATCH_HEAD_RE = re.compile(r"^\s*[\[【（(]?\s*派工")
_DISPATCH_PATH_RE = re.compile(r"to-track-[A-Za-z0-9_-]+[\\/][^\s\"'<>]*?\.md\b", re.IGNORECASE)


def is_dispatch_message(bodies: Iterable[str]) -> bool:
    """DISPATCH_OPENS_TURN：任一同伴訊息正文的**第一個非空行**以「派工」開頭（可帶括號），或第一行同時含「派工」字樣與
    to-track-<軌>/<檔>.md 派工檔路徑。正文其他地方提到派工檔路徑（交付、進度、審查通知常引用原派工單）不算：
    那會清掉使用者先前的口令、重開回合（codex 001 BLOCK 7）。"""
    for body in bodies or ():
        lines = [ln for ln in str(body or "").splitlines() if ln.strip()]
        if not lines:
            continue
        head = lines[0]
        if _DISPATCH_HEAD_RE.match(head) or ("派工" in head and _DISPATCH_PATH_RE.search(head)):
            return True
    return False


def vcs_unreadable_verdict(name: str, error: str) -> Verdict:
    """VCS_ROOT_UNREADABLE：找版控根時 OSError → 照欠。"""
    return Verdict("VCS_ROOT_UNREADABLE", True, f"{name} 所在的版控根讀不到，判不出去向", (str(error)[:120],))


# ─── B7 WORKTREE_NO_PUSH ───────────────────────────────────────────────────────

def is_worktree_checkout(git_dir: Optional[str], common_dir: Optional[str]) -> bool:
    """`git rev-parse --git-dir` 與 `--git-common-dir` 不同＝這個 checkout 是 worktree。任一拿不到 → False（判不了當主工作樹）。"""
    if not git_dir or not common_dir:
        return False
    return canon_path(git_dir) != canon_path(common_dir)


def push_required_verdict(root: str, is_worktree: bool, has_upstream: bool) -> Verdict:
    """WORKTREE_NO_PUSH：owed=True＝要求 push；worktree 或沒 upstream → False。"""
    if is_worktree:
        return Verdict("WORKTREE_NO_PUSH", False, f"{root} 是 git worktree，多軌分支由總控台合併，不要求 push",
                       ("git-dir ≠ git-common-dir",))
    if not has_upstream:
        return Verdict("WORKTREE_NO_PUSH", False, f"{root} 的分支沒有 upstream，無從 push", ("@{u} 解析不到",))
    return Verdict("WORKTREE_NO_PUSH", True, f"{root} 是主工作樹且有 upstream", ("git-dir == git-common-dir", "@{u} 存在"))


# ─── B8 RUNTIME_DATA_NO_OVERVIEW ───────────────────────────────────────────────
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
# 專案裡一個普通目錄取名 scratchpad 不算（codex 001 BLOCK 6：正式 repo 的子目錄不能靠名字拿暫存豁免）
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


# ─── B10 DPM_WORKTREE_DELIVERY ─────────────────────────────────────────────────
_DPM_BODY = (
    "  - 始末：觸發場景 → 錯誤行為 → 最終正確做法\n"
    "  - 根因：為何會犯（非表面症狀）\n"
    "  - 該區設計原理：出錯那塊程式/機制當初為何這樣設計\n"
    "  - 運作邏輯：它實際怎麼跑、哪個環節斷掉\n"
    "  - 防再犯：下次如何提早攔截\n"
)


def dpm_instruction_text(trigger: str, is_worktree: bool, evidence: str = "") -> str:
    """DeepPostMortem 指令：主工作樹叫 atom_write；worktree 隔離 session（DPM_WORKTREE_DELIVERY）改寫進交付信由總控台代寫。
    evidence＝規則證據行（format_hit 格式，例：重試的逐輪證據），放在標頭下一行，parse_hits 讀得到。"""
    head = f"[Guardian:DeepPostMortem] 偵測到高 effort 失敗訊號（{trigger}）。失敗骨架已由 hook 自動落地，但根因與設計脈絡只有你知道。\n"
    if evidence:
        head += evidence.rstrip("\n") + "\n"
    if is_worktree:
        return (head + "規則 DPM_WORKTREE_DELIVERY：這個 session 在 git worktree 隔離，atom_write 走 live MCP 會寫 live，不要呼叫。"
                "改把完整 post-mortem 寫進交付信（SendMessage 給總控台）的「post-mortem」段，由總控台代寫 atom，涵蓋：\n"
                + _DPM_BODY + "寫進交付信即可宣告完成；此為一次性提示，本 session 不再出現。")
    return (head + "結束前請用 atom_write 補一條完整 post-mortem（寫入既有 failure atom，或 realm=local、domain 視主題新建），涵蓋：\n"
            + _DPM_BODY + "寫完即可宣告完成；此為一次性提示，本 session 不再出現。")


# ─── C1 刻意紅／重試／同案例綠清帳 ────────────────────────────────────────────

def deliberate_red_verdict(reverted: Sequence[Tuple[str, str]], pending: Sequence[str] = ()) -> Verdict:
    """RED_WHILE_REVERTED：reverted＝[(檔名, 等於哪個 ref)]、pending＝同根本 session 還有現行改碼（沒退回）的程式檔。
    刻意紅＝有退回的檔**而且**同根沒有任何自己的現行改碼（那時跑紅不可能是自己現行的碼造成）；只退回其中一檔、另一檔還留著真錯
    → 真的紅照記（codex 001 BLOCK 5）。"""
    if reverted and not pending:
        name, ref = reverted[0]
        return Verdict("RED_WHILE_REVERTED", False, f"跑紅時 {name} 的內容等於 {ref} 的已提交版本、同根沒有其他現行改碼（退回舊碼反證）",
                       tuple(f"{n} == {r}" for n, r in reverted[:3]))
    if reverted and pending:
        return Verdict("RED_WHILE_REVERTED", True, f"同根還有現行改碼（{'、'.join(pending[:3])}），這次紅不能算刻意", tuple(f"{n} == {r}" for n, r in reverted[:2]))
    return Verdict("RED_WHILE_REVERTED", True, "跑紅時沒有改檔處在已提交的舊版本，是真的紅", ())


RETRY_ESCALATE_ROUNDS = 2          # 兩輪重跑仍紅就升級 FixEscalation（plan 與 direct 同一個門檻）
RETRY_ROUNDS_SHOWN = 5             # 訊息最多列幾輪證據
_RED_CASE_RE = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.MULTILINE)


def red_case_names(summary: str) -> List[str]:
    """pytest 輸出裡紅掉的案例（FAILED／ERROR 開頭那行的節點 id），依出現順序、去重。"""
    out: List[str] = []
    for name in _RED_CASE_RE.findall(str(summary or "")):
        if name not in out:
            out.append(name)
    return out


_PYTEST_TALLY_RE = re.compile(r"^=*\s*\d+ (?:passed|failed|errors?|skipped|deselected|xfailed|xpassed|warnings?)\b.*$",
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


_NARROW_FLAG_RE = re.compile(r"(?:^|\s)(?:-k|-m|-t|--testNamePattern|--deselect|--lf|--last-failed)(?=\s|=|$)")
_RUN_MODULE_RE = re.compile(r"(?:^|\s)-m\s+(?:pytest|unittest)\b")     # python -m pytest 的 -m 是「跑模組」，不是標記篩選
_NODE_ID_TOKEN_RE = re.compile(r"""[^\s"']+::[^\s"']+""")
_CMD_SEG_SPLIT_RE = re.compile(r"\|\||&&|[;|\n]")
_TEST_RUNNER_RE = re.compile(r"(?:^|[\s/\\\"'])(?:pytest|py\.test|unittest|jest|vitest)(?:\.exe)?(?=[\s\"']|$)", re.IGNORECASE)


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


_CASE_EXTS = r"(?:py|js|ts|cs|lua|go|rs|rb|java|kt|sh|ps1)"
_CASE_TOKEN_RE = re.compile(r"[\w./\\:-]+\." + _CASE_EXTS + r"\b", re.IGNORECASE)
_QUOTED_CASE_RE = re.compile(r"""(["'])([^"'\n]*?\.""" + _CASE_EXTS + r""")(?:::[^"'\n]*)?\1""", re.IGNORECASE)


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
_CANDIDATE_RE = re.compile(rf"候選\s*[（(]?\s*([{_LABELS}])|第\s*([{_LABELS}])\s*個?\s*根因")
_REASON_WORDS = r"(?:(?<!根)因為|理由|原因|由於|所以|because)"
_REASON_RE = re.compile(_REASON_WORDS, re.IGNORECASE)
# 「不存在／沒有／無」後面接標點、理由詞或行尾才算「這個候選不存在」（「候選 A 無鎖競爭」是描述）
_ABSENT_WORD = rf"(?:不存在|沒有|找不到|無)(?=\s*(?:[，,。；;:：]|{_REASON_WORDS}|$))"
_ABSENT_RE = re.compile(rf"\s*[:：]?\s*(?:是)?\s*{_ABSENT_WORD}", re.IGNORECASE)
# 「第二個不存在，因為…」「第二根因不存在：…」「候選 B 不存在因為…」：要寫出為什麼
_SECOND_ABSENT_RE = re.compile(
    rf"(?:第\s*[二2]\s*個?\s*(?:根因|候選)?|候選\s*[（(]?\s*[Bb二乙Ｂ２②])\s*[:：]?\s*(?:是)?\s*{_ABSENT_WORD}"
    rf"[^；;。]*?(?:{_REASON_WORDS}|[:：])\s*\S{{2,}}", re.IGNORECASE)
_ROLE_PLACEHOLDERS = {"", "角色", "這一塊在目標裡的角色", "這一塊的角色", "…", "...", "略", "無"}
_ROLE_STRIP_RE = re.compile(r"[\s，。、；;:：,.!！?？「」『』（）()【】\[\]<>《》—－\-~～*_`'\"]+")


def root_candidates(root_line: str) -> List[int]:
    """根因層那行辨識出的候選編號（去重保序）；標記後面緊接「不存在／沒有」的是「第二個不存在」說明，不算候選。"""
    text = str(root_line or "")
    out: List[int] = []
    for m in _CANDIDATE_RE.finditer(text):
        if _ABSENT_RE.match(text, m.end()):
            continue
        n = _LABEL_NO[m.group(1) or m.group(2)]
        if n not in out:
            out.append(n)
    return out


def goal_role(goal_line: str, node_id: str) -> str:
    """第四行節點編號後面括號（全形或半形）裡的角色；沒有括號回空字串（角色要寫在括號裡）。"""
    v = str(goal_line or "")
    i = v.find(node_id) if node_id else -1
    m = re.match(r"\s*[（(](.*?)[）)]", v[i + len(node_id):] if i >= 0 else v)
    return m.group(1).strip() if m else ""


def _role_core(text: str) -> str:
    return _ROLE_STRIP_RE.sub("", str(text or ""))


def _has_choice_reason(root_line: str) -> bool:
    """選擇理由：以「；，。」切段，段裡的理由詞前面沒有候選標記才算（「候選 A 的原因是 …」是候選自己的描述，不是選擇理由）。"""
    for seg in re.split(r"[；;。，,]", str(root_line or "")):
        r = _REASON_RE.search(seg)
        c = _CANDIDATE_RE.search(seg)
        if r and (c is None or r.start() < c.start()):
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
    cands = root_candidates(root_line)
    if len(cands) >= 2:
        if not _has_choice_reason(root_line):
            missing.append(f"根因層辨識出 {len(cands)} 個候選，但沒寫選擇理由（「選 A 因為 …」）")
    elif not _second_absent(root_line, cands):
        missing.append(f"根因層只辨識出 {len(cands)} 個候選，也沒寫「第二個不存在因為 …」"
                       "（寫法：候選 A …；候選 B …；選 A 因為 …）")
    if not missing:
        return Verdict(rule, False, "定位四行有角色、有兩個候選或第二個不存在的理由")
    return Verdict(rule, True, "；".join(missing), (f"定位｜根因層：{root_line}", f"定位｜目標：{goal_line}"))


_UNREASONABLE_RE = re.compile(r"不合理")
_REASONABLE_RE = re.compile(r"(?<!不)合理")
_BETTER_RE = re.compile(r"更好|改成|應該|改用|換成")
# 同類欄位的標籤：「同類…：」（冒號前最多 8 字，如「同類還可能在哪：」「同類別處：」）；沒冒號時退回「；同類…」這種分隔符後的同類
_SAME_LABEL_COLON_RE = re.compile(r"同類[^：:；;，,。]{0,8}[:：]")
_SAME_LABEL_SEP_RE = re.compile(r"(?:^|[；;。，,])\s*同類(?:別處|還可能在哪(?:裡)?|有沒有|在哪)?\s*")
# 「無／沒有」後面接標點、理由詞或行尾才算「沒有同類」（「無鎖佇列」是位置的名字）
_SAME_NONE_RE = re.compile(rf"^(?:無|沒有|不存在|找不到)(?=\s*(?:[，,。；;:：]|{_REASON_WORDS}|$))", re.IGNORECASE)


def _split_same_class(text: str) -> Tuple[str, Optional[str]]:
    """批判那行切成（判斷段, 同類段）；找不到同類欄位回 (全文, None)。取最後一個標籤，理由裡提到「同類」不會被切斷。"""
    hits = list(_SAME_LABEL_COLON_RE.finditer(text)) or list(_SAME_LABEL_SEP_RE.finditer(text))
    if not hits:
        return text, None
    m = hits[-1]
    return text[:m.start()], text[m.end():].strip()


def locate_critique_verdict(line: str) -> Verdict:
    """LOCATE_LINES_NEED_CRITIQUE：定位第五行「定位｜批判」的結構：同類欄位之前要有合理／不合理的判斷＋理由（不合理另要更好的做法），
    同類欄位要寫在哪（或「無／沒有」＋理由）。缺的項一起列。"""
    rule = "LOCATE_LINES_NEED_CRITIQUE"
    text = str(line or "").strip()
    if not text:
        return Verdict(rule, True, "沒交第五行「定位｜批判：…」（這段寫法合不合理、更好的做法、同類還可能在哪）")
    head, where = _split_same_class(text)
    missing: List[str] = []
    bad = _UNREASONABLE_RE.search(head)
    if bad:
        rest = head[bad.end():]
        if not _REASON_RE.search(rest):
            missing.append("判「不合理」沒寫理由（不合理，因為 …）")
        if not _BETTER_RE.search(rest):
            missing.append("判「不合理」沒寫更好的做法（更好的做法是 …）")
    elif _REASONABLE_RE.search(head):
        if not _REASON_RE.search(head):
            missing.append("判「合理」沒寫理由（合理，因為 …）")
    else:
        missing.append("沒下這段寫法合不合理的判斷（合理，因為 …／不合理，因為 …，更好的做法是 …）")
    if where is not None and _SAME_NONE_RE.match(where):
        if not (_REASON_RE.search(where) and len(_role_core(_REASON_RE.split(where, 1)[-1])) >= 2):
            missing.append("同類寫「無」要附為什麼沒有（無，因為 …）")
    elif where is None or len(_role_core(where)) < 2:
        missing.append("沒寫同類還可能在哪（同類還可能在哪：…；沒有就寫「無，因為 …」）")
    if not missing:
        return Verdict(rule, False, "批判那行有判斷、理由與同類別處")
    return Verdict(rule, True, "；".join(missing), (f"定位｜批判：{text}",))


# 擋訊息範例的佔位：角括號裡有中文說明（`<第一個根因>`）；程式的泛型角括號（List<int>）不算
_EXAMPLE_PLACEHOLDER_RE = re.compile(r"<[^<>\n]*[一-鿿][^<>\n]*>")


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
                          "只能寫編號）；一題掛上不帶過同批其他題。寫碼類有題沒指到擋；記憶知識類只提示；沒有樹不擋，PostToolBatch "
                          "審計記「提問未掛目標（知識類）」。真有待放行紀錄時放行題不算；整次全是放行題才整次豁免（ask_release_only）。",
    "ASK_OVERVIEW_BEFORE_DECISION": "提問涉及改法選擇（ExitPlanMode，或題目含改法／做法／方案／寫法／實作／架構／重構／設計）時："
                                    "題目與選項 label／描述提到的路徑對得上部位表 → 只看那些部位，有部位的 part_files_read 是 0 檔就提醒"
                                    "（讀了別的部位不算），證據行「題目提到 <路徑>→部位 <名>，本回合該部位讀過 0 檔」；題目沒提路徑或提的"
                                    "路徑不在部位表 → 退回看 part_files_read 是不是全空。提醒＝擋訊息或提示多一句「先讀過部位檔再問」；"
                                    "只提醒，不單獨擋（owed＝要附這句）。",
})

ASK_FRAGMENT_MIN = 8
_REC_LABEL_RE = re.compile(r"[(（]\s*recommended\s*[)）]", re.IGNORECASE)
_REC_TEXT_RE = re.compile(r"建議\s*[:：]")
_DECISION_RE = re.compile(r"改法|做法|方案|寫法|怎麼改|如何改|實作|架構|重構|設計|approach|implement|refactor|design", re.IGNORECASE)


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
    "KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE": "本使用者回合在還沒有任何需求目標樹時改了記憶知識類的檔（不是程式檔、不是暫存檔；寫入當下已送過一次"
                                       "「寫一棵輕樹」）→ 回合結束要補一棵輕樹（一個節點即可，之前改的檔寫樹時自動掛進去）。不看措辭；"
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
_URL_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://\S+")
_QUOTED_RE = re.compile(r"`([^`\n]+)`|「([^」\n]+)」|\"([^\"\n]+)\"|'([^'\n]+)'")
_ASK_ABS_PATH_RE = re.compile(rf"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])(?:{_SEG}[\\/])*{_LAST}?")
_ASK_REL_PATH_RE = re.compile(rf"(?<![A-Za-z0-9_.\-\\/:])(?:\.{{1,2}}[\\/])?{_SEG_ASCII}(?:[\\/](?:{_SEG}(?=[\\/])|{_LAST}))+[\\/]?")
_ASK_BARE_FILE_RE = re.compile(
    r"(?<![A-Za-z0-9_.\-\\/:])[A-Za-z0-9_\-]*[A-Za-z][A-Za-z0-9_\-]*\.[A-Za-z][A-Za-z0-9]{0,5}(?![A-Za-z0-9_.\\/])")
_NOT_PATH_SEG_RE = re.compile(r"T\d+(?:\.\d+)*|[\d.\-]*|.")          # 節點編號、純數字（日期、版本號）、單一字元（A/B）


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
        return Verdict(rule, True, "題目涉及改法選擇，但題目提到的部位還沒讀過檔：先讀過部位檔再問（只提醒，不因這條擋）",
                       tuple(f"題目提到 {p}→部位 {part}，本回合該部位讀過 0 檔" for p, part in unread))
    if part_files_read > 0:
        return Verdict(rule, False, f"題目沒提到部位表上的路徑；已讀過 {part_files_read} 個部位檔")
    return Verdict(rule, True, "題目涉及改法選擇，但本 session 還沒讀過任何部位檔：先讀過部位檔再問（只提醒，不因這條擋）",
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
                                     "exit 0 或未知、failed=0）、同一棵樹、指令完整可信（白名單語法、沒有換目錄、環境沒縮範圍）。"
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

RELOAD_ADVICE_RE = re.compile(r"reload\s*window|重新載入視窗|重載視窗|重新載入\s*vs\s*code", re.IGNORECASE)
RELOAD_REASON_RE = re.compile(r"重載原因\s*[:：]\s*\S")     # AI 宣告程式更新以外的重載理由（改了啟動設定等）
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

_DO_IT_NOW_RE = re.compile(r"現在|馬上|立刻|這回合|直接做|這邊做|這裡做")


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
    "CLAIM_WORDS_ARE_HINTS": "(a)(b)(c) 的宣稱詞表只是提示，不替 LLM 判語意。命中且沒證據時，收尾文字要有一行"
                             "「宣稱｜<修好|量了|試過>：收據 <指令片段或哨兵名>」或「宣稱｜<…>：非本回合宣稱，因為 <理由>」："
                             "沒這行 → 照原規則擋並附寫法；「非本回合宣稱」附理由 → 放行、留帳（guard-reconcile.jsonl event=claim_disclaimed，"
                             "健檢抽查）；「收據」→ 走 CLAIM_RECEIPT_REF_MATCH。結構化的達成＋證據（need_goal 完整對照）仍是寫碼類的正式宣告，"
                             "宣稱行只處理散文裡的詞。",
    "CLAIM_DISCLAIM_NEEDS_REASON": "宣稱行寫「非本回合宣稱」要附理由：拿掉角括號片段後還有任一字母或數字（任何語言），而且沒留著擋訊息的"
                                   "理由範本佔位（<理由…>、<為什麼…>）；純標點不算，理由裡引用 <標籤> 照算；沒理由不算回。程式不評理由充不充分。",
    "CLAIM_RECEIPT_REF_MATCH": "宣稱行指的收據要能辨識出是哪一張：引用的字要是那條指令的一個完整 token（整個 token、檔名、路徑尾段、"
                               "測試節點尾段），或帶空白的逐字片段，或哨兵名相同；python／pytest／py／-m 這類通用字、旗標、純副檔名不算指名。"
                               "對上的那張還要過原本的收據資格（指令完整、記了環境、白名單語法、沒寫哨兵字樣、同一棵樹）："
                               "說修好 → 合格 PASS、同根、晚於相關改檔最後一次修改；說量了 → DONE 且指令可信或跑了部位量尺；"
                               "說試過 → 指令可信的任一筆。對不上照擋。",
    "NOT_DOING_DECLARED": "退避語（軟偵測與 DeferralGate）命中的那一行若本身就是「不做｜<哪一件>：<理由>」，或同一段文字有不做行而它的事項"
                          "出現在命中那一行 → 不標、不擋、留帳（guard log evasion_declared／deferral_declared）；理由要有文字內容、不是佔位。"
                          "說明句被詞表誤命中（「下個 session 開場會列出…」是在描述已驗過的事）→ 寫「不是退避｜<命中的詞或句>：因為 <理由>」"
                          "同樣只查有沒有理由、留帳。詞表各類的 exception 文字（風險、為什麼超出）附在提示裡給 LLM 寫理由用，程式不評理由內容。",
    "USER_WAIVER_NEEDS_CITATION": "使用者豁免不再整段清掉：近 3 則使用者原話含「先這樣／跳過／留著」不直接關掉退避偵測、退縮歸屬、紅測清單。"
                                  "LLM 要寫「不做｜<哪一件>：使用者說「<原句片段>」」且片段（至少 2 個中文或英數字，純標點不算；英文片段整詞比對）"
                                  "真的出現在近 3 則使用者原話裡 → 只豁免那一件；紅測清單只豁免事項指得到那一筆的（事項是失敗指令或摘要的一個"
                                  "完整 token：整個 token、檔名、路徑或節點尾段；通用字不算）。沒引用、引用找不到 → 照判。",
})

CLAIM_LABELS: Dict[str, str] = {"fixed": "修好", "measured": "量了", "tried": "試過"}
_CLAIM_LABEL_KINDS: Dict[str, str] = {"修好": "fixed", "修復": "fixed", "量了": "measured", "量過": "measured",
                                      "試過": "tried", "跑了": "tried", "跑過": "tried"}
_CLAIM_DISP_RE = re.compile(r"宣稱\s*[｜|]\s*(修好|修復|量了|量過|試過|跑了|跑過)\s*[：:]\s*(.+)")
_DISCLAIM_RE = re.compile(r"^(?:非|不是|並非)\s*本回合\s*(?:自己的?)?\s*宣稱\s*[，,：:、]?\s*(?:因為|理由[：:]?|原因[：:]?)?\s*(.*)$")
_RECEIPT_REF_RE = re.compile(r"^收據\s*[：:]?\s*(.+)$")
_NOT_DOING_RE = re.compile(r"不做\s*[｜|]\s*([^：:\n]{1,80}?)\s*[：:]\s*(.+)")
# 說明句被退避詞表誤命中（「下個 session 開場會列出…」是在描述已驗過的事）→ AI 說明這不是退避，程式只查有沒有理由、留帳
_NOT_EVASION_RE = re.compile(r"不是退避\s*[｜|]\s*([^：:\n]{1,80}?)\s*[：:]\s*(?:因為|理由[：:]?)?\s*(.+)")
_USER_SAID_RE = re.compile(r"使用者\s*(?:說|原話|的話|說的)\s*[：:]?\s*[「『\"“]([^「」『』\"”\n]{1,160})[」』\"”]")
_WS_RE = re.compile(r"\s+")
_ITEM_STRIP_RE = re.compile(r"[\s，,、：:（）()「」『』`*\-—–~～?？!！.。；;]")
_WORD_CHAR_RE = re.compile(r"[A-Za-z0-9一-鿿]")
_LATIN_ONLY_RE = re.compile(r"^[A-Za-z0-9 _.\-]+$")
_TOKEN_TRIM = "\"'`「」『』（）()[]{}<>,，;；。:："
# 指不到特定收據／測試的通用字：直譯器、跑測工具、旗標、純副檔名（規則 CLAIM_RECEIPT_REF_MATCH／USER_WAIVER_NEEDS_CITATION）
GENERIC_NAMES = frozenset({"python", "python3", "py", "pytest", "test", "tests", "verify", "run", "node", "npm", "npx", "bash", "sh",
                           "pwsh", "powershell", "cd", "cmd", "exe", "md", "json", "txt", "m", "q", "x", "utf8"})


def _nows(s: Any) -> str:
    return _WS_RE.sub("", str(s or "")).lower()


def has_text(s: Any, min_chars: int = 2) -> bool:
    """有文字內容：至少 min_chars 個中文或英數字（純標點、「....」不算）。"""
    return len(_WORD_CHAR_RE.findall(str(s or ""))) >= min_chars


_ANGLE_SEGMENT_RE = re.compile(r"<[^<>\n]*>")
# 擋訊息教 AI 填理由的範本佔位：<理由>、<理由：…>、<一句理由>、<為什麼…>（各閘的 hint 都這樣開頭）
_REASON_PLACEHOLDER_RE = re.compile(r"<\s*(?:一句)?(?:理由|為什麼)[^<>\n]*>")


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
    return (f"詞表只是提示（規則 CLAIM_WORDS_ARE_HINTS）：這句不是本回合自己做了的宣稱 → 回一行「宣稱｜{label}：非本回合宣稱，因為 <理由>」；"
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


def not_doing_hint(exception: str = "") -> str:
    why = not_doing_reason_hint(exception)
    return (f"真的不做 → 寫一行「不做｜<哪一件>：<理由：{why}>」（規則 NOT_DOING_DECLARED，會留帳）；"
            "使用者叫你跳過 → 「不做｜<哪一件>：使用者說「<原句片段>」」（規則 USER_WAIVER_NEEDS_CITATION）；"
            "這句只是在描述、沒推任何事 → 「不是退避｜<命中的詞>：因為 <理由>」（留帳抽查）")


def not_doing_verdict(line: str, decls: Sequence[Dict[str, str]], prompts: Sequence[str], exception: str = "") -> Verdict:
    """NOT_DOING_DECLARED／USER_WAIVER_NEEDS_CITATION：owed＝照舊標記或擋。line＝命中退避語的那一行；prompts＝近 3 則使用者原話。
    理由裡的角括號片段若是這個範本印給 AI 的說明（<不修的實際風險>）＝沒換掉的佔位，不算理由。"""
    hint_why = (not_doing_reason_hint(exception),)
    d = not_doing_covering(line, decls)
    if d is None:
        return Verdict("NOT_DOING_DECLARED", True, "退避語沒有對應的不做行", (str(line or "").strip()[:120], not_doing_hint(exception)))
    if d.get("mode") == "disclaim":
        if reason_present(d["reason"], hint_why):
            return Verdict("NOT_DOING_DECLARED", False, f"AI 說明「{d['item'][:60]}」不是退避，因為 {d['reason'][:120]}", (d["line"],))
        return Verdict("NOT_DOING_DECLARED", True, "不是退避行沒附理由（或只有佔位）", (d["line"], not_doing_hint(exception)))
    if d["quote"]:
        if quote_in_prompts(d["quote"], prompts):
            return Verdict("USER_WAIVER_NEEDS_CITATION", False, f"使用者原話「{d['quote'][:60]}」豁免：{d['item'][:60]}", (d["line"],))
        return Verdict("USER_WAIVER_NEEDS_CITATION", True,
                       f"不做行引用的使用者原話「{d['quote'][:60]}」在近 3 則使用者訊息裡找不到", (d["line"], not_doing_hint(exception)))
    if reason_present(d["reason"], hint_why):
        return Verdict("NOT_DOING_DECLARED", False, f"AI 宣告不做「{d['item'][:60]}」，因為 {d['reason'][:120]}", (d["line"],))
    return Verdict("NOT_DOING_DECLARED", True, "不做行沒附理由（或只有佔位）", (d["line"], not_doing_hint(exception)))


def waived_failures(failing: Sequence[Dict[str, Any]], decls: Sequence[Dict[str, str]],
                    prompts: Sequence[str]) -> Tuple[List[Dict[str, Any]], List[Tuple[Dict[str, Any], Dict[str, str]]]]:
    """USER_WAIVER_NEEDS_CITATION 套在紅測清單：回 (還算紅的, [(被豁免的那筆, 對上的不做行)])。
    豁免條件：不做行帶使用者引用、引用在原話裡、事項指得到那筆失敗的指令或摘要裡的一個完整 token（names_item；通用字不算）。"""
    cited = [d for d in decls if d.get("mode", "not_doing") == "not_doing" and d["quote"] and quote_in_prompts(d["quote"], prompts)]
    kept: List[Dict[str, Any]] = []
    waived: List[Tuple[Dict[str, Any], Dict[str, str]]] = []
    for f in failing:
        hay = f"{(f or {}).get('cmd', '')} {(f or {}).get('summary', '')}"
        hit = next((d for d in cited if names_item(hay, d["item"])), None)
        (waived.append((f, hit)) if hit else kept.append(f))
    return kept, waived


# ─── T2.16 動資料檔 ───
RULES.update({
    "USER_DATA_FILE_NEEDS_DECLARATION": "Edit／Write／NotebookEdit 動到使用者既有的資料檔或設定檔要先問或先宣告。四件事實全成立才管："
                                        "(a) 不是程式檔（wg_need_goal.writes_code 為 False）且副檔名在 guard.data_file_ask.extensions，"
                                        "清單只決定程式要不要把它當資料檔問，該不該改仍是 AI 判；(b) 呼叫前檔已存在；(c) 不是本 session Write 新建的"
                                        "（state created_files）；(d) 本 session 使用者原話都沒點名它（檔名含副檔名完整比對，不做模糊）。"
                                        "成立而且回覆文字／工具呼叫參數裡 # 開頭的註解行／thinking 都找不到「動資料檔｜<路徑>：<為什麼>」"
                                        "（路徑檔名對得上這次要改的檔、冒號後的理由過 reason_present）→ 擋。宣告過記 state data_file_declared，"
                                        "同 session 同檔不再擋；換檔要再宣告。一律留帳 Logs/guard-data_file.jsonl（denied／declared／exempt）。",
})

_DATA_FILE_DECL_RE = re.compile(r"動資料檔\s*[｜|]\s*((?:[A-Za-z]:[\\/])?[^：:\n]+?)\s*[：:]\s*([^\n]*)")
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


_CJK_CHAR_RE = re.compile(r"[一-鿿㐀-䶿぀-ヿ가-힯]")
_QUOTED_NAME_RE = re.compile(r"[「『\"“`]([^「」『』\"“”`\n]+)[」』\"”`]")


def _quoted_other_name(text: str, start: int, end: int, base: str) -> bool:
    """命中處在引號／反引號裡，而引號裡是另一個更長的檔名（「備份設定.json」裡的 設定.json）。"""
    for q in _QUOTED_NAME_RE.finditer(text):
        if q.start(1) <= start and end <= q.end(1):
            name = q.group(1).strip().replace("\\", "/").lower()
            return name != base.lower() and not name.endswith("/" + base.lower())
    return False


def prompt_names_file(prompts: Sequence[str], target: str) -> Optional[str]:
    """事實 (d)：使用者原話有沒有點名這個檔，檔名含副檔名完整比對，不分大小寫：前後不接檔名字元（前面可接路徑分隔）；
    引號裡是更長的檔名不算；檔名以中日韓字開頭時前一個字也是中日韓字不算（「備份設定.json」分不出是不是別的檔，寧可多問）。
    英文檔名前接中文動詞照算（「把settings.json的逗號修掉」）。回點名那則原話的片段，沒有回 None。"""
    base = Path(str(target)).name
    if not base:
        return None
    rx = re.compile(r"(?<![A-Za-z0-9_.\-])" + re.escape(base) + r"(?![A-Za-z0-9_\-]|\.[A-Za-z0-9])", re.IGNORECASE)
    cjk_head = bool(_CJK_CHAR_RE.match(base))
    for p in prompts or ():
        text = str(p or "")
        for m in rx.finditer(text):
            if _quoted_other_name(text, m.start(), m.end(), base):
                continue
            if cjk_head and m.start() > 0 and _CJK_CHAR_RE.match(text[m.start() - 1]):
                continue
            return text[max(0, m.start() - 30):m.end() + 30]
    return None


def data_file_hint(rel: str) -> str:
    return (f"入口行範例：動資料檔｜{rel}：<為什麼要動它、動了使用者會看到什麼>\n"
            "放回覆文字或下一個 Bash 開頭 `#` 註解；拿不準要不要動就用 AskUserQuestion 問使用者（附推薦）。")


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
    ev = [f"(a) 不是程式檔：副檔名 {ext} 在資料／設定清單",
          "(b) 使用者既有：呼叫前檔已存在",
          "(c) 非本 session 建：本 session 沒新建過它",
          f"(d) 需求沒點名：本 session 使用者原話（{int(facts.get('prompts') or 0)} 則）找不到「{base}」"]
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
# ─── T2.18 origin 核對 ───
# 目標樹子節點標「使用者說的」要對得到原話（wg_need_goal 的 add／update 收事實、這裡判）。只核字面在不在、是誰說的；
# 要不要標、引哪一句由 AI 判（引一句不相干的原話硬掛，程式看不出來：quote 與節點文字並列留帳給人抽查）
RULES.update({
    "ORIGIN_USER_NEEDS_QUOTE": "目標樹子節點標 origin=user（使用者說的）：quote 或節點文字本身（去頭尾空白、至少 6 字、不正規化標點）"
                               "要是樹上某則使用者原話（user_said，含匯入的前一個 session 原話）的字面子串；對不到、或只出現在同伴轉述"
                               "（peer_said）裡 → 強制改 inferred（推出來的）並提醒。樹根與匯入的節點不核。",
})
ORIGIN_QUOTE_MIN = 6


def _said_with(s: str, entries: Sequence[Any]) -> Optional[Dict[str, Any]]:
    return next((e for e in entries or () if isinstance(e, dict) and s in str(e.get("text") or "")), None)


def origin_user_verdict(text: Any, quote: Any, user_said: Sequence[Any],
                        peer_said: Sequence[Any] = ()) -> Tuple[str, Verdict, Optional[Dict[str, Any]]]:
    """ORIGIN_USER_NEEDS_QUOTE：回 (origin, Verdict, 對上的 {"quote": 對上的字串, "said": 那則原話})；對不到第三項是 None、
    owed＝要降級成 inferred。先核 quote、再核節點文字；兩個都對不到時，原因以 quote（有給的話）為準。"""
    rule = "ORIGIN_USER_NEEDS_QUOTE"
    q = quote.strip() if isinstance(quote, str) else ""
    t = text.strip() if isinstance(text, str) else ""
    for s, how in ((q, "quote"), (t, "節點文字")):
        if len(s) < ORIGIN_QUOTE_MIN:
            continue
        hit = _said_with(s, user_said)
        if hit is not None:
            return ("user", Verdict(rule, False, f"{how}對得到第 {hit.get('turn', '?')} 回合的使用者原話", (f"引用：{s[:120]}",)),
                    {"quote": s, "said": hit})
    s = q or t
    peer = _said_with(s, peer_said) if len(s) >= ORIGIN_QUOTE_MIN else None
    if peer is not None:
        why = f"這句是同伴 {peer.get('from') or '?'} 說的，不是使用者"
    elif q and len(q) < ORIGIN_QUOTE_MIN:
        why = f"quote 只有 {len(q)} 字，至少要 {ORIGIN_QUOTE_MIN} 字"
    elif q:
        why = "quote 不在任何一則使用者原話裡"
    elif len(t) < ORIGIN_QUOTE_MIN:
        why = f"沒給 quote，節點文字只有 {len(t)} 字（不到 {ORIGIN_QUOTE_MIN} 字不拿來比）"
    else:
        why = "沒給 quote，節點文字也不是使用者原話的字面子句"
    return "inferred", Verdict(rule, True, why, (f"節點文字：{t[:120]}", f"quote：{q[:120] or '（沒給）'}")), None


_ROOT_SPLIT_RE = re.compile("[。；，、]|" + chr(0x2014) * 2)   # 第二支是雙破折號（本檔不准出現破折號字面）


def root_unquoted_sentences(text: Any, user_said: Sequence[Any]) -> List[str]:
    """ORIGIN_USER_NEEDS_QUOTE 的樹根版：樹根依契約是 AI 對原話的解讀（不改 origin）。切句（。；，、雙破折號）後至少 6 字的句子，
    逐句看是不是某則使用者原話的字面子串；回對不到的句子（保序、去重），給提醒列出「這幾句原話裡沒有」。"""
    out: List[str] = []
    for s in _ROOT_SPLIT_RE.split(text if isinstance(text, str) else ""):
        s = s.strip()
        if len(s) >= ORIGIN_QUOTE_MIN and s not in out and _said_with(s, user_said) is None:
            out.append(s)
    return out
# ─── T2.17 改舊測試 ───
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
})

OLD_TEST_KIND_LABELS: Dict[str, str] = {"gone": "消失", "renamed": "改名", "assert": "斷言變了", "skip": "加 skip", "doc": "說明變了"}
_OLD_TEST_FILE_RE = re.compile(r"\.[a-z]{1,5}$")
_OLD_TEST_DECL_RE = re.compile(r"改舊測試\s*[｜|]\s*(.+)")
_OLD_TEST_ASCII_SEP_RE = re.compile(r":(?![A-Za-z0-9_\\/:])")
_OLD_TEST_NAME_SPLIT_RE = re.compile(r"\s*[、，,]\s*")


def parse_old_test_declarations(text: str) -> List[Dict[str, Any]]:
    """宣告行 → [{names, reason, line}]。名字與理由用第一個「：」分；沒有全形冒號才找後面不接識別字的「:」
    （`tests/test_a.py:test_x: 理由` 的第一個冒號屬於名字）。names 是去反引號後的整段與「、，,」切開的每一段。"""
    out: List[Dict[str, Any]] = []
    for raw in str(text or "").splitlines():
        m = _OLD_TEST_DECL_RE.search(raw)
        if not m:
            continue
        rest = m.group(1)
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
# ─── T2.19 繞閘嫌疑 ───
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
