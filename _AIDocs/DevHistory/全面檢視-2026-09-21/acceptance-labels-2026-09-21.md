# Codex 驗收裁判紀錄 — 人工標註第一輪（AI 標註、未人工複核）

> 本檔：`C:\Users\holylight\.claude\_AIDocs\DevHistory\全面檢視-2026-09-21\acceptance-labels-2026-09-21.md`
> 專案根 `C:\Users\holylight\.claude`（branch `main`）；資料檔 `workflow/acceptance-audit.jsonl`（只透過 `tools/codex-companion/acceptance.py --label` 寫入）。
> 計畫出處：`memory/_staging/next-phase-全面檢視-2026-09-21.md` §6 Phase 3「Codex 裁判紀錄分母」延後項 ④。
>
> **標註者是 AI（Claude，sub-agent），未經人工複核。** 每筆都附證據位置；§4 列出最沒把握的 5 筆供人挑錯。標錯可直接 `--label <ID> <新類別>` 覆寫（原地重寫、保留其他列）。

## 1. 判類規則（依 `acceptance.py` 註解，標「案子的真相」不是「裁判說了什麼」）

| 類別 | 定義 | 對應裁判判定 |
|---|---|---|
| known_good | 事後看該回合的交付**已合格**（含：唯一未達項已由後續事實證明無問題） | fail＝誤擋；uncertain＝多餘保留 |
| known_defect | 事後看該回合**確有缺陷或未達完成定義**（含「代理人自承還沒做完」的進行中回合） | fail＝真命中；uncertain/pass＝漏放 |
| insufficient_evidence | 從紀錄＋transcript 仍無法判定（本機無 transcript、或關鍵事實本質上要等外部事件） | uncertain＝正確棄權 |

證據來源：`workflow/acceptance-audit.jsonl` 該列的 summary／problems；transcript `projects/<slug>/<session_id>.jsonl` 裁判 ts 前最後一則 assistant 文字與其後第一至三則 user 訊息（含 Stop hook feedback）。8/6–8/21 的 20 筆本機**沒有 transcript**（`projects/` 與 `_archive/` 皆無），只從中挑 6 筆標 insufficient_evidence，其餘 14 筆留空未標。

## 2. `--stats` 前後對照

| 指標 | 標註前 | 標註後 |
|---|---|---|
| labeled | 2 | **35**（本輪 +33） |
| labeled_by_class（good／defect／insufficient） | 0／2／0 | **6／22／7** |
| fail_labeled | 2 | 20 |
| precision（fail 列中 known_defect 佔比） | 1.00（2/2） | **0.95**（19/20） |
| miss_rate（known_defect 卻非 fail） | 0.00 | **0.136**（3/22） |
| unwarranted_uncertain_rate（good/defect 案被判 uncertain） | 0.00 | **0.286**（8/28，門檻 ≤0.30） |
| unlabeled_fails | 28 | 7 |
| labeled_enough／promotion_ready | false／false | **true／true** |
| kill_switch | false | false |

`binding_events` 444→445 是期間他 session 新增一列綁定列，與本輪無關。

## 3. 逐筆標註（33 筆）

ID＝`session_id 前 8 碼#turn_index`。「型」欄是我加的補充分類：**等待**＝代理人自承任務進行中／等背景或他方，裁判 fail 判得對但無可補做；**範圍**＝規格檔涵蓋多階段、該回合只交付其中一階段；**實缺**＝交付物本身有 bug 或違規；**合格**＝事後證明沒問題。

### 3.1 known_good（6）

| ID | 裁判 | 型 | 證據位置與關鍵句 | 理由 |
|---|---|---|---|---|
| 127e56a5#13 | fail/medium | 合格 | transcript 09-21 16:12 assistant：「1,888 案例 1,885 過，2 筆失敗都不是本次改動造成」；16:14 assistant：`git stash` 換回 HEAD 版重跑仍 2.55 秒失敗、三連跑一次通過。後續 user 16:36／16:45 只糾正報告路徑，未質疑改動 | 字面「全綠」未達，但第二筆失敗已實證與本次無關且抖動；交付物本身合格 |
| 127e56a5#14 | uncertain/low | 合格 | 同上案，16:14 之後裁判仍棄權（summary：核心檔案內容未採樣）；user 16:45「OK我看到了…繼續把所有 phase 推進」 | 與 #13 同案；棄權屬多餘保留 |
| 094f7ab1#4 | uncertain/low | 合格 | transcript 09-18 18:20 assistant：「全套 run_verify 1873 passed, 0 failed」，唯一 ⏳ 是 SessionEnd 聚合；事後 `Logs/guard-tool-result-stats.jsonl` 確有 `session_id: 094f7ab1` 一筆；user 18:22 追問的 `synced` 資料夾經查是 CC 自身雲端快取（18:25 assistant），非本任務殘留 | 唯一未驗項事後成立，交付合格 |
| 412b09bb#0 | uncertain/low | 合格 | transcript 09-07 19:50 Write 規格檔 `status: done`；19:56 assistant：「A1～A5 五個檔改完…AllServers.sln 皆 0 error、警告數與改前相同（19）」、V1/V2/V5/V8 實測數字；19:58 console 來信 006：「003 report 審過收案（五檔 diff 逐行看過…）」 | 審查方（console session）收案並派下一任務；裁判棄權因 A3–A5 未採樣 |
| 836a43f1#17 | uncertain/low 　 | 合格（Phase 0） | transcript 09-04 14:55 assistant 把規格檔補 `phases` 欄、Phase 0 兩條標 ✅；user 15:06 直接「上GIT」 | 本回合宣稱範圍只有 Phase 0，五項有實證（PHP 裝好、8080 監聽、r15581）；user 接受 |
| c020a964#4 | uncertain/low | 合格 | transcript 08-07 15:54 assistant：三檔改動、「等你煙測」；user 08-28 09:12：「測試的 Editor 已經跑了許久，目前都沒有發生問題，是否 Log 可以都拔掉了?」 | 唯一待驗項（使用者煙測）事後通過 |

### 3.2 known_defect（20）

| ID | 裁判 | 型 | 證據位置與關鍵句 | 理由 |
|---|---|---|---|---|
| 094f7ab1#3 | fail/medium | 等待 | transcript 09-18 18:12 assistant：「全套 run_verify 尚在跑（78%）…留到結果回來那一刻一併提交」 | 收尾當下驗證未跑完、SessionEnd 未驗，完成定義未達 |
| 836a43f1#16 | fail/high | 範圍 | transcript 09-04 14:54 assistant：「Phase 0 完成，Phase 1（寫 PHP）可以開工」「sgi_server、sgi_client 未動」；規格檔當時涵蓋全案 6 phase | 依當時規格，PHP／MapServer／登入／Client 條目確實未做；代理人隨後才把規格改成分 phase |
| f08d5873#1 | fail/high | 等待 | transcript 09-03 15:16 assistant：「run_verify 全套正在背景跑…跑完會自動接續收尾（staging → commit → push → 移 done/）」 | 驗證與收尾條目自承未做 |
| 879c4c60#12 | fail/high | 等待 | transcript 09-03 11:29 assistant：「現在等兩個 sub-agent 回報…回來後跑真 hook 探針與全套 verify，再做 Commit 3」 | Commit 3 條目自承未完成 |
| 879c4c60#13 | fail/high | 等待 | transcript 09-03 11:30 assistant：「裁判判定正確，這不是收尾：Commit 3 還在進行中」；同刻 TestFailGate 另報 1 項測試失敗 | 代理人自認判定正確 |
| d25915c6#0 | fail/medium | 實缺 | audit problems：DocIndex 可見變更含「沒走過的邊不跨區接（使用者定調 2026-08-31）」；MudClient repo `git log -S"使用者定調 2026-08-31"` 無命中＝該字串在 16:41 commit `ec46ba5` 前已被拿掉；專案 atom 在 `ec46ba5` 才入 commit | live 文件埋日期敘事違反 core.md；裁判抓到後被修掉，屬真命中（輕） |
| 5e547646#2 | fail/high | 等待 | transcript 08-28 15:23 assistant：「全量 reindex 仍在跑…完成後接著做：盤點孤兒→反查→寫根因 atom」 | 四條核心條目自承未做 |
| 5e547646#3 | fail/high | 等待 | transcript 08-28 15:24 assistant：「收尾被擋是對的——reindex 還沒完」 | 代理人自認判定正確 |
| 625b1550#8 | uncertain/low | 實缺 | transcript 08-25 16:06 user 貼 HUD 截圖：「紅框框起來的檔案我不知道到底是什麼…同一行涵蓋『已刪除』+『未刪除』是不是寫錯了?」；16:07 assistant：「兩點都是我的錯」，(d) 欄違反自訂契約塞了說明文字，改程式正規化 | HUD 殘檔帳本輸出有真缺陷，裁判棄權＝漏放 |
| 625b1550#9 | uncertain/low | 實缺 | 同上（#9 在 16:05 「修復完成」宣稱後，16:06 user 即指出問題） | 同上 |
| 71a37e54#9 | fail/medium | 等待 | transcript 08-24 16:27 assistant：「Task C 實證大半完成…繼續等 Grok 面板 session 的正式回信做總驗收」；atom 於 16:29 才 replace | 收尾條目（atom 寫回）當下未做 |
| 71a37e54#66 | fail/high | 範圍 | transcript 08-25 11:48 assistant：「Phase A 已派工…後續節奏：A 收工上 GIT → B 開打」；規格檔當時要求 A→E 全部落地 | 依當時規格未達；代理人隨後把戰役計畫移 `_staging`、規格改只綁 Phase A（等於承認規格綁錯） |
| 71a37e54#67 | fail/high | 範圍 | transcript 08-25 11:51 assistant「裁判誤判說明…從未宣稱 A–E 任何一項完工」 | 同上；規格層面的未達是事實 |
| 71a37e54#68 | fail/high | 等待 | transcript 08-25 11:53 assistant：「status: open 反映真實狀態：已派工、Grok 實作中」 | Phase A 四條自承未完成 |
| 71a37e54#69 | fail/high | 等待 | transcript 08-25 11:54 assistant：「驗收檔四條的狀態我方與裁判認知完全一致：全部未完成」 | 同上 |
| 71a37e54#74 | fail/high | 等待 | transcript 08-25 12:04 assistant：「三個設計題已派…它交設計提案、我核可後才實作」 | B1–B3 未開工 |
| 71a37e54#75 | fail/high | 等待 | transcript 08-25 12:05 assistant：「本回合無完成宣稱…明示 B1–B3 全部未完成」 | 同上 |
| b4bb91ed#7 | fail/high | 等待 | transcript 08-25 14:55 assistant：「Grok 現在離線寫 D，D session 開場就是審 diff」 | FlowAnalyzer 尚不存在 |
| b4bb91ed#8 | fail/high | 等待 | transcript 08-25 14:56 assistant：「裁判列的四條未達標項正確描述了 Phase D 現況」；user 14:57「? 你是說CC這邊也需要新開session??」（對代理人訊息的困惑，非對裁判） | 同上 |
| b4bb91ed#20 | uncertain/low | 等待 | transcript 08-25 17:41 assistant：「工作樹裡 Grok 未 commit 的 Phase E 半成品」、安排 reload 交接；17:44 Grok 才送 080 交付信 | Phase E 當下未完成，裁判棄權＝漏放（同型回合他處判 fail） |

### 3.3 insufficient_evidence（7）

| ID | 裁判 | 證據位置 | 理由 |
|---|---|---|---|
| 71a37e54#10 | uncertain/low | `~/.grok/.claude/verify/done/acceptance-ai-inbox-grok-alignment.md`：六條全 [x]，但「PostCompact 已掛、未觸發未驗」「--resume 對活 id 未測（設計上禁測）」列殘留 | 條目要求三種 hook 驗證，PostCompact 只能等真實壓縮事件；真相不可判，棄權合理 |
| 32f0555d#0 | uncertain/low | 本機無 transcript（8/21） | 無法核對 |
| cd015b0b#0 | uncertain/low | 本機無 transcript（8/14） | 無法核對 |
| 63205882#1 | uncertain/low | 本機無 transcript（8/6） | 無法核對 |
| f6567d1c#0 | fail/high | 本機無 transcript（8/20）；裁判理由「修改了允許範圍外的 _AIDocs」 | 是否經使用者授權無從查證，不硬判 |
| 06808d8f#5 | fail/high | 本機無 transcript（8/19）；裁判理由「移除房名並改用五段門狀態，違反兩項核心驗收條目」 | 規格可能已由使用者口頭改動，無從查證 |
| 34aaa35f#7 | fail/high | 本機無 transcript（8/13）；裁判理由「核心新增檔仍未追蹤、驗收檔未移 done」 | 無法核對 |

## 4. 最沒把握的 5 筆（請優先挑錯）

1. **127e56a5#13 → known_good**（fail/medium）。規格字面是「除 usage-snapshot LF 外全綠」，實際多一筆 merge-driver 時間預算失敗。我採「已實證與本次無關＋抖動」判合格；若你認定字面全綠是硬條件，改 known_defect，precision 變 20/20。
2. **836a43f1#17 → known_good**（uncertain/low）。規格檔整體仍 open（Phase 1–5 未做），我以「本回合宣稱範圍＝Phase 0 且使用者隨即上GIT」判合格。若你認為多階段規格未 done 就不算合格，改 known_defect 或 insufficient_evidence。
3. **71a37e54#66／#67 → known_defect**（fail/high，範圍型）。裁判依「A→E 全部落地」的規格判 fail 沒錯，但該回合本來就只是建規格＋派工；也可主張是規格綁定失誤、裁判誤擋 → known_good。這兩筆連同 836a43f1#16 共 3 筆，改標會讓 precision 掉到 16/20＝0.80（仍過門檻）。
4. **d25915c6#0 → known_defect**（fail/medium）。只憑 audit 引文＋「該字串從未進 commit」推斷日期敘事當時存在後被修掉；atom 是否在裁判當下已 replace 無法直接證明（AEC 報告說已 replace，diff --stat 沒列）。
5. **71a37e54#10 → insufficient_evidence**（uncertain/low）。規格六條全 [x] 但 PostCompact 未驗；也可判 known_defect（條目字面未滿足）。改標會讓 miss_rate 變 4/23。

## 5. 對「轉正」數字的解讀（重要）

`promotion_ready` 翻成 **true**，但不該直接當放行依據：

- **precision 0.95 幾乎全靠「等待型」與「範圍型」撐起**：20 筆 fail 標註中（本輪 18＋先前已標 2），本輪的 18 筆＝等待型 13、範圍型 3、實缺 1（d25915c6#0）、誤擋 1（127e56a5#13）。等待型＝代理人自己說「還沒做完」，裁判照抄就對——這量的是「裁判會不會讀錯完成宣稱」，不是「裁判能不能從 diff 抓到真 bug」。真正需要裁判眼力的樣本只有 2 筆，1 中 1 誤。
- **等待型 13 筆對使用者都是噪音**：每筆都逼代理人寫一段「裁判誤判說明」再收尾，b4bb91ed#8 還連帶讓使用者困惑。這是**觸發時機**問題（進行中回合也觸發 stop_enforce），不是精度問題；轉正前應先決定：代理人明示「等待外部／背景」的回合是否不觸發或只 warn。
- **unwarranted_uncertain 0.286 貼著 0.30 上限**：5 筆 known_good∧uncertain 裡 3 筆（094f7ab1#4、c020a964#4、412b09bb#0）的關鍵事實在裁判當下本來就拿不到（session 結束後的 log、使用者煙測、未採樣的檔），棄權其實合理；把它們改成 insufficient_evidence 會讓比率降到 5/25＝0.20。反過來，只要上述 5 筆有 1 筆被複核成 known_defect，比率也可能跳過 0.30。這個指標對標註口徑極敏感，門檻意義有限。
- **真漏放 3 筆都值得看**：625b1550#8／#9（HUD 輸出真有錯，裁判兩次棄權）、b4bb91ed#20（同型等待回合他處全 fail，這裡卻 uncertain）——裁判在「測試全綠但輸出語意錯」的案子上沒有抓力，因為案卷只有 diff 採樣與測試輸出、沒有實際 HUD 內容。

**單一建議**：把本輪標註視為「分母已達標、口徑待人核」；轉正決策等 (1) 人工複核 §4 五筆、(2) 決定等待型回合的觸發策略之後再下。

## 6. 本輪異動檔案

- `C:\Users\holylight\.claude\workflow\acceptance-audit.jsonl` — 33 列 `human_label` 由 null 改為三類之一（另加 `human_label_at`），列數 445 不變（期間他 session +1 綁定列）。
- `C:\Users\holylight\.claude\_AIDocs\DevHistory\全面檢視-2026-09-21\acceptance-labels-2026-09-21.md` — 本檔（新增）。
- 未 commit／push／stash。
