# 收尾少空轉：接續（先重量，再依數據提第三波）

> 約束（開頭與結尾各一次）：這一棒**只量、不改程式**，第三波做法要先給使用者拍板；新增或保留任何驗證關卡前，先對照使用者「想把 v6 加的驗證整個拔掉、目前先止血」的方向；commit 一律 `git commit -- <路徑>`（共用工作樹的暫存區會被別的 session 與背景同步同時使用）。

【前置脈絡】
- 專案：`C:/Users/holylight/.claude`（原子記憶系統本身，git main；好幾個 session 共用同一棵工作樹）。
- 目標的始末：
  - **原始目標**（使用者原話）：「我們的流程造成反覆重新跑測、這種浪費時間的地方一定要修掉」。一句話：收尾流程不再讓模型為了同一件事反覆重跑測試、反覆多花回合。
  - **階段目標**：第一波（完成）：已同步的檔不再被同步提醒擋、改測試只重跑那一支、擋一次列出全部欠帳、量尺能和測試串一行。第二波（五件，四件完成、一件未完）：①閱讀路徑量尺不在收尾當下逾時、不附手動指令 ②測試不再真的睡到逾時 ③已 commit 的檔不因別的 session 沒提交的改動就免不掉案例宣告 ④**重量被擋次數（未完）** ⑤驗證範圍閘本身不再造成重跑。第三波：未定，要看④的數據。
  - **簡略經過**：第一波起因是一週 524 次收尾擋下、被擋的回合一半以上連擋 2～7 次（一場空轉 19 分鐘）。第二波：①根層量一次閱讀路徑 56 秒、收尾只給 3 秒，兩天 47 次附段落 39 次逾時、手動指令被照跑 5 次 → 改背景量、之後的收尾附結果；②全庫 5040 案只有閱讀路徑兩支真睡到逾時，順帶主控台追蹤測試 40 秒→3 秒、產出物帳本改每案隔離（刪 22 個依執行順序錄出的錄製檔）；③198 次被拖住九成五是多 session 同時改的非程式檔 → 使用者拍板比對範圍縮成「同根程式檔＋案例檔」；⑤使用者拍板「AI 宣告每項依賴（depends）」，另外收據記紅案清單、清單完整時逐項判紅綠。⑤的第一筆 commit 在共用暫存區撞車（帶進另一軌的程式、漏掉自己 5 檔，pushed HEAD 一度不一致），讓對方先 commit 後補齊。
  - **對原始目標的結果：部分達成。** 已知放大器拆了，還沒有數據證實「不再反覆重跑」。第二波 session 本身：收尾被擋 5 次（3 次是收尾儀式：知識收割、收尾檢核、卡片表態），pytest 25 次共 32.5 分鐘，其中約 6 分鐘是放大器白跑（新規則下不會再發生），其餘約 26 分鐘是「改程式就跑相關測試」的底線成本。上線後約 25 分鐘樣本：閱讀路徑附段落 0、逾時 0、手動跑 0。
- 這一棒為什麼先量：第三波有兩個方向（拆驗證範圍閘的殘餘缺口 vs 拆收尾儀式／v6 閘），成本與風險差很大，要用數據選，不用猜。

【已完成】
- 第一波：ebd44e6c、a9e9f862。第二波：c9063dbd（①②）、566f7733（③）、a51be424＋d7260221（⑤；a51be424 誤含另一軌 HUD 第 2 階段程式，歷史不改寫，3faee677 有說明）。全部已 push origin/main。
- 驗證：⑤最後範圍 1017 passed＋MCP smoke PASS＋文件量尺 PASS；各件新案都先證過在舊碼上紅。

【權威來源】（先讀）
- 本檔；`TECH.md` 規則表的 SYNC_BLOCK_SKIPS_SYNCED、SCOPE_CASE_EDIT_ONLY_ITS_ITEM、BLOCK_LISTS_LATER_GATES、EXEMPTION_PEERS_CODE_ONLY、SCOPE_EDIT_IN_DECLARED_DEPENDS、SCOPE_RED_ONLY_ITS_CASES。
- 程式：`hooks/wg_verify_scope.py`（declare、_item_mods）、`hooks/wg_verify_ledger.py`（scope_item_status、_green_for_item、committed_settled_paths、exemption_peers）、`hooks/wg_reading_path.py`、`hooks/wg_release_rules.py`。
- 資料：`C:/Users/holylight/.claude/projects/**/*.jsonl`（各 session 對話紀錄，量測來源）。
- 卡：[[feedback-驗證閘要對準需求目標不是驗量具-測試檔改了只重跑它自己-流程造成的反覆重跑一律要修]]、[[共用工作樹只stage自己的hunk-別用unidiff-zero-換回head原文再update-index]]、[[錄製重播的兩個假象-核對失敗被fail-open吞掉測試照綠-跨案共用的session帳本讓錄製檔依執行順序]]。

【產出位置】
- 量測腳本：寫在接手 session 的 scratchpad（上一場的腳本已被清掉，要重寫）。
- 量測結果：寫回本檔新的「量測結果」段，接著寫第三波提案（選項＋推薦＋理由），交使用者拍板。

【做法】
1. 重量（只量）：掃 `projects/**/*.jsonl`（排除 subagents）。被擋＝attachment.type `hook_blocking_error` 且 hookEvent `Stop`，以訊息裡第一個 `[Guardian:XXX]`／`[Workflow Guardian]` 當哪道閘；閱讀路徑＝含 `[Guardian:ReadingPath]`，含「逾時」或「量不完」算逾時；手動跑量尺＝Bash 指令同時含 `reading-path.py` 與 `--before`；每個使用者回合連擋分布（真的使用者訊息才換回合）、同閘一回合擋兩次以上的回合數；VerifyScope 擋下裡「改完要重跑」「最近一次跑紅」分開數；另數 need_goal verify_scope 宣告裡帶 `depends` 的項目比例（AI 有沒有用上新欄位）。
2. 時間窗（兩窗都用同一支腳本、同一套口徑重算，不直接拿下面的舊數字比）：改前窗＝`2026-10-14T00:00Z`～`2026-10-16T05:20Z`；改後窗＝`2026-10-16T05:20Z`～量測當下。舊數字只當對照參考（當時的口徑：全部專案、只數被擋的回合、沒有回合分母）：被擋 212 次；閱讀路徑附 47 次、逾時 39 次；手動跑 5 次；被擋回合的連擋分布 {1:48, 2:26, 3:12, 4:9, 5:4, 6:1, 7:2}；同閘擋兩次以上 24 回合。
3. 口徑（兩窗一致）：
   - 專案範圍：只算 `projects/` 底下根層專案的資料夾（名稱以 `c--users-holylight--claude` 開頭、不分大小寫，含 `-wt-*` 工作樹 session）；其他專案另列一行、不併進主數字。
   - 真的使用者訊息＝type `user`、內容是文字（不是 tool_result）、不以 `Stop hook feedback` 開頭、剝掉 `<system-reminder>`／`<task-notification>`／`<cross-session-message>`／`<ide_*>` 區塊後還有字；每一則開一個使用者回合，回合歸屬於它的開始時間落在哪一窗（跨窗的回合整個算前一窗）。
   - 分母：每窗的使用者回合總數（含零次被擋的）與天數；報「每天幾次」「每個使用者回合平均幾次」「被擋過的回合佔幾成」。
   - 去重：同一則擋下訊息在 jsonl 重複出現（同 timestamp＋同內容）只算一次；子代理（subagents 資料夾）不算。
   - VerifyScope 分項：「改完要重跑」「最近一次跑紅」「沒有跑這一項」「還沒宣告驗證範圍」「還沒宣告由哪個案例驗」各數一次（一則擋下可同時命中多項）；兩窗都算，改前窗的數字是新的基準。
   - 閱讀路徑是否讓模型多花回合：逐例看附了 `[Guardian:ReadingPath]` 的擋下，下一個 assistant 動作若是去處理閱讀路徑內容（跑量尺、改程式回應那段數字）才算多花一回合；只附上、模型沒理它不算。列出每一例的 session 與時間。
   - 判不出、還原不了的（例：舊紀錄被清、口徑對不上）一律標「不可比較」或「待確認」，不硬比。
4. 依數據提第三波（判斷留給接手的 session，附理由；使用者拍板才動手）：「改完要重跑」仍大宗 → 針對缺口 1、2；收尾儀式大宗 → 逐閘列「擋下次數×擋下後真的抓到問題的次數」，提拔哪些。
5. 工具：量測寫成 Python 腳本檔再跑（本機閘擋 `python - heredoc`）；Bash 路徑寫字面絕對路徑。

【決策依據】
- 已鎖定、不翻案（使用者拍板）：③比對範圍＝同根程式檔＋案例檔（否決「只看這檔＋它宣告的案例」：依賴宣告、誤放風險高；否決「只改一處」：同一問題留兩處）。⑤作廢範圍＝AI 宣告 depends（否決 import 自動分析：掃全庫的測試與動態載入會漏；否決不動：改一個檔就要全部重跑）。
- 已知缺口（還沒解）：1. depends 要 AI 自己宣告，沒宣告照舊任何程式改動都作廢；2. commit 後又改任何程式，快照豁免失效，已 commit 的檔要留宣告並重跑（③選「程式檔之間照舊嚴格」的代價）；3. 收尾儀式每擋一次多一回合；4. need_goal reconcile 的證據先後不看 depends；5. commit 指引沒有「比對 staged 清單不符就中止」；6. 錄製重播核對失敗被受測程式吞掉時測試照綠。4～6 已記追蹤項。
- 已知坑：共用暫存區撞車（見上方約束）；Git Bash 的 MSYS 會把斜線開頭參數轉成 Windows 路徑（`MSYS_NO_PATHCONV=1`）；scratchpad 路徑太深，開完整 worktree 會撞長檔名（用 sparse checkout）。
- 未驗證、勿據此鎖死：接續的 session 看到的 need_goal 工具說明可能仍是舊版、沒有 depends（伺服器端已確認是新版、會收這個欄位）。

【未解問題】
- 上線後 VerifyScope「改完要重跑」每個使用者回合平均幾次？比基準少多少？
- 收尾儀式（KnowledgeHarvest、ScanReport、AtomAudit…）占全部擋下幾成？
- 驗證範圍宣告裡帶 depends 的項目占幾成？
- 閱讀路徑改背景後，附上的結果有沒有讓模型多花回合？

> 約束（重述）：只量、不改程式；第三波先給使用者拍板；新增或保留關卡前對照「拔掉 v6 驗證」方向；commit 用 `git commit -- <路徑>`。

## 量測結果（2026-10-20，接手 session fe4af483）

腳本：`C:\Users\HOLYLI~1\AppData\Local\Temp\claude\c--Users-holylight--claude\fe4af483-d3a9-4955-b304-5255edef3e97\scratchpad\stop_measure.py`（scratchpad 會被清；口徑全照上面【做法】3，另加三個量：擋下後到下一次收尾之間跑了幾次 pytest／run_verify、這段續跑多久、這段有沒有改程式或文件）。

### 一、兩窗總表（根層專案；其他專案另列）

| | 改前窗 10-14 00:00Z～10-16 05:20Z | 改後窗 10-16 05:20Z～10-20 01:55Z |
|---|---|---|
| 天數／活躍時數 | 2.22 天／67.6 h | 3.86 天／**4.7 h** |
| 使用者回合 | 388 | **17**（其中 11 回合是第二波 session 自己） |
| 被擋 | 177（每天 79.7、每回合 0.46、每活躍小時 2.6） | 11（每回合 0.65、每活躍小時 2.3） |
| 被擋過的回合 | 87（22%） | 9（53%） |
| 被擋回合的連擋分布 | {1:47, 2:16, 3:8, 4:10, 5:4, 7:2} | {1:8, 3:1} |
| 同閘一回合擋 ≥2 次 | 22 回合 | 1 回合 |
| 收尾儀式（知識收割＋收尾檢核＋卡片表態） | 54（31%） | 6（55%） |
| VerifyScope「改完要重跑」 | 16 則（每回合 0.041） | 2 則（每回合 0.118） |
| VerifyScope「最近一次跑紅」 | 6 則 | 0 |
| 「沒有跑這一項」／「還沒宣告驗證範圍」／「還沒宣告由哪個案例驗」 | 5／6／8 則 | 0／2／2 則 |
| 閱讀路徑附段落／逾時／手動跑 | 42／38／8 | 3／**0**／**0** |
| verify_scope 項目帶 depends | 0／423（欄位還不存在） | **12／60（20%）**；8 次宣告裡 3 次有用 |

其他專案：改前 54 回合被擋 39（以同步提醒 10、知識收割 9 為主）；改後 7 回合被擋 4。舊基準 212 次（全部專案）≈ 本次改前窗根層 177＋其他 39＝216，口徑對得上。

**結論：改後窗不可比較。** 10-16 下午之後到今天幾乎沒有使用（只有 4.7 活躍小時、17 回合，而且大半是第二波 session 本身邊改邊跑），「改完要重跑」只有 2 則，算出來的每回合比率沒有意義。能確定的只有閱讀路徑：逾時 38→0、手動跑 8→0、附上的 3 次模型都沒去處理（沒多花回合）；以及 depends 已有人用（20% 項目）。T1.4 的「跟改之前對照」要等正常使用 1～2 天後用同一支腳本再量。

### 二、改前窗：成本落在哪（決定第三波方向用）

被擋則數只說明「多了幾回合」；真正的浪費是擋下之後重跑測試。逐閘列（根層、改前窗；「改程式／文件」是擋下後到下一次收尾之間有沒有動到非 scratchpad、非記憶的檔，是「真的抓到問題」的**上限**，實際更少）：

| 閘（白話） | 擋下 | 擋下後跑 pytest 次數 | 擋下後有改程式／文件 |
|---|---|---|---|
| ReconcileGate（寫碼查核：改程式要有案例、需求目標要對照） | 49 | **119** | 14 |
| MeasureGate（量尺閘：部位量尺沒跑） | 27 | **79** | 3 |
| Workflow Guardian（改了檔還沒同步） | 19 | 26 | 3 |
| TestFailGate（測試紅） | 3 | 16 | 1 |
| VerifyScope（驗證範圍閘） | 16 | 9 | 0 |
| KnowledgeHarvest（知識收割） | 37 | 2 | 2（另 13 次寫了卡） |
| AtomAudit（卡片表態） | 9 | 2 | 1 |
| ScanReport（收尾檢核） | 8 | 0 | 1 |

- 擋下後的 pytest 共約 253 次，**ReconcileGate＋MeasureGate＋VerifyScope 三道 v6 驗證閘佔 207 次（82%）**；收尾儀式三道加起來 4 次（2%）。
- 最常見的單一擋下規則：MEASURE_RULER_NOT_RUN 31、SCOPE_ITEM_RECEIPT_AFTER_EDIT（改完要重跑）21、OWED_AFTER_LAST_CASE 13、CASE_DECLARED_FOR_CHANGE 11、CLAIM_FIXED_NEEDS_PASS 6。
- 收尾儀式是「多一回合」問題（31% 擋下、續跑合計約 40 分鐘），不是「重跑測試」問題。
- 單看「改完要重跑」只佔改前窗擋下 9%，缺口 1、2 就算全補，省的重跑也有限。

### 三、第三波提案（待使用者拍板，未動手）

**推薦：把量尺閘（MeasureGate）從「擋」改成「收尾報告列出、不擋」；卡片表態（AtomAudit）與收尾檢核（ScanReport）同樣改成不擋。**

理由：
1. 量尺閘是重跑的第二大來源（27 擋、79 次 pytest），擋下後改到程式的上限只有 3 次；它最常見的規則 MEASURE_RULER_NOT_RUN 也是全部規則裡擋最多的。拔掉它換來的是最多的省時，抓到問題的損失最小。
2. 卡片表態與收尾檢核 17 擋、擋下後改到東西的上限 2 次，每擋一次就多一回合，而且模型的回應幾乎都只是呼叫一次儀式工具或回一段文字。
3. 方向對得上「把 v6 加的驗證拔掉、先止血」：這一步是拔，不是補新關卡。
4. 不動的部分與原因：寫碼查核（ReconcileGate）重跑最多（119 次），但擋下後改到程式的上限也最高（14 次），可能真的有抓到東西，資料不足以判斷，先不拔，等改後窗有正常使用量再看它的「擋下→改程式」逐例；知識收割擋下後 13 次真的寫了卡，是有產出的，保留；缺口 1、2（depends 預設、commit 後再改）只佔 9%，排在後面。

不推薦先做的：只補缺口 1、2——資料顯示它不是大宗。

待確認：「擋下後有改程式／文件」是上限不是實數，要精確得逐例看；若使用者要更穩，可以拍板前先逐例看 ReconcileGate 那 14 例與 MeasureGate 那 3 例。

### 四、逐例確認（使用者選「先逐筆確認再拿」）

腳本：同 scratchpad 的 `catch_cases.py`。改前窗根層、擋下後到下一次收尾之間有改程式／文件的 19 例，逐例讀擋下訊息、模型的第一段回應、改了哪些檔後判定：

| 閘 | 候選例 | 真的抓到問題 | 逼出漏寫的測試 | 閘自己誤判／只是收據格式 | 跟擋下無關（本來就在做的事） |
|---|---|---|---|---|---|
| 寫碼查核 | 13 | 2（#4 跑出 7 案紅才改；#9 測試還紅時擋住宣告完成） | 2（#2、#14） | 4（#5 收據夾了 tail 不算、#7 漏判帳誤判、#10 萬用字元複製被當搬目錄、#16 收據串了別的指令不算） | 5 |
| 量尺閘 | 3 | **0** | 0 | 0 | 3 |
| 卡片表態 | 1 | 1（很小：一句註解寫了事件經過） | 0 | 0 | 0 |
| 收尾檢核 | 1 | **0** | 0 | 0 | 1 |
| 知識收割 | 2 | 0（它的產出是寫卡，另計 13 次） | 0 | 0 | 2 |

（ReconcileGate 擋下訊息常把量尺規則一起列，#2、#5 兩例算在寫碼查核。）

結論：
- 量尺閘 27 次擋下，0 次真的抓到問題；收尾檢核 8 次，0 次。兩道拿掉沒有已知損失。
- 卡片表態 9 次，抓到 1 個小地方（註解寫法），每次多一回合，划不來。
- 寫碼查核 49 次裡：真的抓到 2 次、逼出漏寫的測試 2 次，但它自己誤判或只卡收據格式也有 4 次。有價值的是「測試還紅就不准說做完」與「改了程式要有測試」這兩條；收據格式、對照表填寫這類手續是空轉來源。

### 五、使用者拍板（2026-10-20）：拿掉前三道，第四道瘦身

- 量尺閘（MeasureGate／MEASURE_RULER_NOT_RUN）、收尾檢核（ScanReport）、卡片表態（AtomAudit）：不再擋。
- 寫碼查核（ReconcileGate）只留兩件會擋：測試還紅不准說做完、改了程式要有測試；收據格式、需求目標對照表、驗證範圍宣告這類手續不再擋。
- 動手是下一棒（這一棒只量）。動手前先讀 `hooks/wg_release_rules.py` 的 RULES 表，逐條歸到「留」或「不再擋」，清單先給使用者看再改。

### 六、這一棒自己踩到的誤擋（下一棒的現場證據）

只改了這份文件，收尾被驗證範圍閘擋 3 次；使用者選「繼續擋，先修好」，查到根因：
- **宣告記錯目錄**：`need_goal verify_scope` 把宣告當下 Bash 的工作目錄記成這一項的執行根（`workflow/state-<session>.json` 的 `base`）。那時 Bash 停在先前 `cd` 過去的 `projects\c--users-holylight--claude`，指令裡的 `tools/sync-memory-index.py` 在那裡根本不存在；之後在專案根照原句跑出的 PASS 全被 `_same_exec_dir`（`hooks/wg_verify_ledger.py`）判成「換了目錄跑」。在專案根重宣告一次，既有的 PASS 立刻被認。
- **說明挑錯收據**：沒對上任何收據時，`scope_item_status` 給的理由從「所有收據裡最近一筆帶 DONE 的」去挑（指令項目 `_mentions` 一律回真），挑到的是不相干的量測腳本，訊息說「指到收據根以外」，把人帶往錯的方向。
- 下一棒若照拍板不再擋驗證範圍宣告，這兩個問題跟著消失；若保留任何一部分，這兩處要一起修。

### 七、更正與第三波已在本 session 做完（2026-10-20）

- **更正**：量尺閘（MeasureGate）在 10-14 21:33（+08，commit 97f730c2）就已拔掉，換成驗證範圍宣告。第二節「量尺閘擋 27 次、擋下後 79 次 pytest」全在它拔掉之前，不是現況。拔掉之後到第二波上線前（10-14 13:34Z～10-16 05:20Z，97 回合、被擋 71 次），擋最多的是驗證範圍宣告那一套：SCOPE_ITEM_RECEIPT_AFTER_EDIT 21、CASE_DECLARED_FOR_CHANGE 11、SCOPE_DECLARED_FOR_CHANGE 6。
- **預估效果**（scratchpad `trim_effect.py`，同一窗）：照新政策，69 次擋下裡 38 次不會再擋，它們之後跑了 47 次 pytest（擋下後 pytest 共 92 次）；還會擋的 31 次多是同步提醒、知識收割與 (a)(d)。這是代理數字：擋下後的 pytest 有一部分本來就該跑。
- **使用者要求本 session 直接修**，已做：`reconcile_gate.block_letters=["a","d"]`、`goal_gate=false`、`verify_scope.enabled=false`、`aec.scan_report_gate=false`、`atom_audit.enabled=false`；規則 RECONCILE_BLOCK_LETTERS、CLOSING_RITUAL_SWITCHES。程式預設照舊全擋，政策只在 `workflow/config.json`。
- **沒動、留給使用者決定的同類手續**：改程式前要先有目標樹（need_goal edit_gate）、提問要掛節點（ASK_LINKED_TO_GOAL）、提問要附推薦（ASK_NEEDS_RECOMMENDATION）。不擋收尾，但每次也多一回合。
- **還要做（已自動化，commit 4fe5762d）**：回訪登記 `closing-gates-trim-2026-10-20`（`workflow/followups.json`），2026-10-22 起任何 CC session 開場自動量（滿 30 回合才判），結果與零記憶交接推給那個 session、第一則回覆向使用者報告。手動跑：`python -X utf8 tools/followup-check.py --run --force --id closing-gates-trim-2026-10-20`。基線：71 次／97 回合。量測腳本已存到 `memory/_staging/收尾少空轉-量測腳本/`（不會再被清）：`python -X utf8 <該資料夾>/measure_window.py 2026-10-20T03:00:00 <現在 UTC>`；逐例看擋下後有沒有抓到問題用同資料夾的 `catch_cases.py`（窗在檔內 sm.W0／W1）。
- **已上版**：commit 80cfa53d（已 push）；TECH 兩列由背景收割 c54499ef 帶進。hooks 全量對照 HEAD 沒有多紅（既有紅：merge_driver_gate 3、vcs_sync_worker 6，HEAD 一樣紅）。
- **本場另踩到、未修（根因未明）**：改碼前的定位閘（OverviewHub）記的對話紀錄位置一度是 9,030,995 位元組，比本 session 對話紀錄（約 4.5 MB）還大，之後交的定位行永遠讀不到 → 改所有程式部位的檔一律被擋（死鎖）。位置在目標改動時由 `wg_overview.on_goal_changed(state, transcript_path, …)` 用 `transcript_size` 重記；當時同專案另一個 session（31aa0da5）的對話紀錄約 9 MB，疑似拿到別的檔。再改一次目標後位置變正確（4,591,316）才解開。要查：PostToolUse 收到的 transcript_path 是不是有時是別的 session 的；防呆可在位置大於檔案大小時從頭讀。

## 【需求目標樹】

（need_goal 產生；下個 session 讀到這份續接單會自動匯入。使用者原話是權威，樹是上一個 session 的解讀。）

### T1：收尾流程不再讓模型為了同一件事反覆重跑測試、反覆多花回合（已對照｜寫碼類｜子目標 5、待展開 0、待對照的改動 0）
- 使用者原話（權威）：
  - 第 1 回合：「<pasted_content id="b168"> 接續「收尾少空轉」第二波（上一波已推 main：ebd44e6c、a9e9f862）。目標：收尾流程不再讓模型為了同一件事反覆重跑測試、反覆多花回合。這波做三件： 1. 閱讀路徑量尺移出收尾當下：根層 repo 3 秒內永遠量不完（兩天 11/11 逾時），量不完時還把「手動指令」塞進擋下訊息，模型會接單去跑。改成背景量、結果留到下次收尾附上；量不完只寫原因，不附手動指令。相關：hooks/wg_reading_path.py、hooks/handlers/stop.py 的 _piggyback。 2. 慢測試：hooks/verify/verify_reading_path_hook.py 有案例真的睡到逾時（最慢一個 8 秒），改用假時鐘或極短預算；再用 pytest --durations 掃全庫最慢清單，同類一起改。 3. 共用工作樹的免宣告條件：已 commit 的檔本來可以免補「由哪支測試驗」的宣告，但只要同一個 repo 裡本 session 動過的檔有別的 session 沒提交的改動，就免不掉（wg_verify_ledger.committed_settled_paths），結果要全部重跑。先提出放寬的做法給我拍板再動手。 背景：使用者想過把 v6 加的驗證整個拔掉，目前先止血；新增驗證關卡前先對照這個方向…」
  - 第 10 回合：「那 收割完畢、可關閉嗎?」
  - 第 11 回合：「本session(延續前個session)的主題:避免反覆瘋狂的驗證這個問題，能算是解決掉了嗎?」
  - 第 12 回合：「之前給的prompt或文件.. 有包含要把問題解決的始末嗎?」
- 同伴轉述（不是使用者說的）：
  - claude-49：「9c06da1b 這邊已全部提交完畢、暫存區是空的，你可以直接接手 stage 你自己的 hunk。 狀況說明（跟你訊息裡寫的有一點不同）： - 你提到我又 staged 的 wg_release_rules.py／post_tool_use.py／verify_release_rules.py 三個檔：我的部分其實已經在你的 a51be424 裡了（EVASION_CONTEXT_EXEMPT、…」
- 節點：
  - T1 [部分｜明確｜使用者說的] 收尾流程不再讓模型為了同一件事反覆重跑測試、反覆多花回合；最近一次為什麼：T1.4 隔天重量；證據：實測 收據 R174 `python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify…`；未完：T1.4 隔天重量
    - T1.1 [達成｜明確｜使用者說的] 閱讀路徑量尺不在收尾當下逾時、量不完也不附手動指令讓模型去跑；最近一次為什麼：這批改檔（wg_verify_ledger、stop.py 補傳 cfg、wg_release_rules、兩支測試）屬 T1.3 的豁免放寬，沒有動閱讀路徑；T1.1 的案例 verify_reading_path_hook 與 g12w…；證據：實測 收據 R174 `python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify…`
    - T1.2 [達成｜明確｜使用者說的] 測試不再真的睡到逾時，全庫最慢的同類一起改快；最近一次為什麼：全庫最慢清單驗過：真的睡到逾時的只有閱讀路徑兩支（8 秒×2，已改假 run）；最慢的主控台追蹤兩案 40 秒→ 3 秒（每窗查一次改一次查全部）；產出物帳本跨案共用讓收尾案例多查 git、錄出依順序的錄製檔 → conftest 每案自己…；證據：實測 收據 R174 `python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify…`
    - T1.3 [達成｜明確｜使用者說的] 共用工作樹裡，已 commit 的檔不會因為別的 session 沒提交的改動就免不掉案例宣告（做法先給使用者拍板）；最近一次為什麼：使用者拍板「縮成程式＋案例檔」：exemption_peers 三個豁免共用、NET_UNCHANGED 改逐檔判、stop.py 補傳 cfg、規則與 TECH 表更新。更接近：新案舊碼三支全紅、新碼綠，範圍 7 項 1104 案綠；文件…；證據：實測 收據 R174 `python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify…`
    - T1.4 [部分｜明確｜使用者說的] 做完重量被擋次數，跟改之前對照；最近一次為什麼：改完後 live 樣本太短，隔天用同一組腳本量 2 天窗再對照 212 次基線；證據：實測 收據 R83 `SP=/c/Users/holylight/AppData/Local/Temp/claude/c--Users-hol…`；未完：改完後 live 樣本太短，隔天用同一組腳本量 2 天窗再對照 212 次基線
    - T1.5 [達成｜明確｜使用者說的] 驗證範圍閘本身不再造成重跑：改一個檔不讓無關的項目作廢、一支紅不讓同指令的其他項目跟著算紅；最近一次為什麼：depends（項目宣告依賴，依賴外的程式改動不作廢）與收據紅案清單（清單完整時同指令沒紅的項目照算綠）都上線；新案 9 支舊碼紅、新碼綠，範圍 1017 案＋MCP smoke 綠；本場宣告已實際用上 depends（smoke 項不被 …；證據：實測 收據 R174 `python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify…`、讀碼 驗證案例 hooks/verify/verify_verify_scope.py::test_red_case_only_reddens_its_own_item（先紅後綠）；同類別處：背景自寫收據（_self_run_item_ok）同樣整份算紅，已一起改；指令項目維持整條算；need_goal reconcile 的證據先後仍以節點最後一次改動算、不看 depends（另記追蹤）
- 未完事項：T1（部分）→ T1.4 隔天重量；T1.4（部分）→ 改完後 live 樣本太短，隔天用同一組腳本量 2 天窗再對照 212 次基線

<!-- need-goal:begin v1 -->
```json
{"version": 1, "session_id": "eefb3380-f6e1-4685-9191-d81bde344bde", "exported_at": "2026-10-16T18:46:06+08:00", "active": "T1", "trees": [{"id": "T1", "status": "reconciled", "kind": "code", "goal_rev": 3, "created_turn": 1, "created_seq": 2, "user_said": [{"seq": 1, "turn": 1, "text": "<pasted_content id=\"b168\">\n接續「收尾少空轉」第二波（上一波已推 main：ebd44e6c、a9e9f862）。目標：收尾流程不再讓模型為了同一件事反覆重跑測試、反覆多花回合。這波做三件：\n1. 閱讀路徑量尺移出收尾當下：根層 repo 3 秒內永遠量不完（兩天 11/11 逾時），量不完時還把「手動指令」塞進擋下訊息，模型會接單去跑。改成背景量、結果留到下次收尾附上；量不完只寫原因，不附手動指令。相關：hooks/wg_reading_path.py、hooks/handlers/stop.py 的 _piggyback。\n2. 慢測試：hooks/verify/verify_reading_path_hook.py 有案例真的睡到逾時（最慢一個 8 秒），改用假時鐘或極短預算；再用 pytest --durations 掃全庫最慢清單，同類一起改。\n3. 共用工作樹的免宣告條件：已 commit 的檔本來可以免補「由哪支測試驗」的宣告，但只要同一個 repo 裡本 session 動過的檔有別的 session 沒提交的改動，就免不掉（wg_verify_ledger.committed_settled_paths），結果要全部重跑。先提出放寬的做法給我拍板再動手。\n背景：使用者想過把 v6 加的驗證整個拔掉，目前先止血；新增驗證關卡前先對照這個方向。量測腳本可重用上一場 scratchpad 的 stop_stats.py、turn_chains.py 的寫法，做完重量一次被擋次數。\n</pasted_content id=\"b168\">"}, {"seq": 120, "turn": 3, "text": "轉告，你自己去SendMessage呀"}, {"seq": 123, "turn": 4, "text": "所以49回應你了?\n後續還要幹嘛嗎?"}, {"seq": 124, "turn": 5, "text": "\"驗證範圍閘本身就會造成重跑\""}, {"seq": 191, "turn": 9, "text": "reload 好了"}, {"seq": 192, "turn": 10, "text": "那 收割完畢、可關閉嗎?"}, {"seq": 193, "turn": 11, "text": "本session(延續前個session)的主題:避免反覆瘋狂的驗證這個問題，能算是解決掉了嗎?"}, {"seq": 195, "turn": 12, "text": "之前給的prompt或文件.. 有包含要把問題解決的始末嗎?"}], "peer_said": [{"seq": 185, "turn": 7, "from": "claude-49", "text": "9c06da1b 這邊已全部提交完畢、暫存區是空的，你可以直接接手 stage 你自己的 hunk。 狀況說明（跟你訊息裡寫的有一點不同）： - 你提到我又 staged 的 wg_release_rules.py／post_tool_use.py／verify_release_rules.py 三個檔：我的部分其實已經在你的 a51be424 裡了（EVASION_CONTEXT_EXEMPT、見收割報告、test_evasion_context_exempt_boundary 都在 HEAD）。那次 staged 的是重複疊加的版本，我已經 git reset 把那三個檔移出暫存區，沒有 commit。 - mcp.js 我的部分（刪 (c)、d 欄說明、十參）也已在 a51be424。 - TECH.md 我的那幾列被背景收割 247e073d 帶進 HEAD；_CHANGELOG 我的第 2 階段條目在 3faee677。都已 push。 - 所以現在工作樹裡這六個檔（wg_release_rules、post_tool_use、verify_release_rules、mcp.js、TECH、_CHANGELOG）相對 HEAD 的差異，應該全部都是你的（depends、red_case、SCOPE_EDIT_IN_DECLARED_DEPENDS、SCOPE_RED_ONLY_ITS_CASES、你的 CHANGELOG 條目）。我不會再碰這幾個檔。 - 提醒：背景收割的 vcs-sync 也會用共用暫存區提交，stage 完盡快 commit。"}], "node_last_edit": {"T1.1": {"seq": 102, "path": "C:\\Users\\holylight\\.claude\\hooks\\verify\\verify_stop_reconcile.py"}, "T1.2": {"seq": 70, "path": "C:\\Users\\holylight\\.claude\\tools\\verify\\verify_tools_data_root.py"}, "T1.5": {"seq": 173, "path": "C:\\Users\\holylight\\.claude\\hooks\\wg_release_rules.py"}}, "last_reconcile": {"seq": 181, "turn": 5, "goal_rev": 3}, "goal_changed": {"seq": 125, "turn": 5}, "imported_from": null, "nodes": {"T1": {"parent": null, "text": "收尾流程不再讓模型為了同一件事反覆重跑測試、反覆多花回合", "origin": "user", "clarity": "clear", "status": "partial", "history": [{"seq": 2, "turn": 1, "what": "create", "why": ""}, {"seq": 84, "turn": 2, "what": "reconcile", "why": "T1.3 等拍板、T1.4 等樣本"}, {"seq": 118, "turn": 2, "what": "reconcile", "why": "T1.4 隔天重量"}, {"seq": 181, "turn": 5, "what": "reconcile", "why": "T1.4 隔天重量"}], "evidence": [{"kind": "receipt", "ref": "R174", "level": "measured", "covers": ["T1"], "seq": 181}], "followup": "T1.4 隔天重量", "note": "", "same_class": ""}, "T1.1": {"parent": "T1", "text": "閱讀路徑量尺不在收尾當下逾時、量不完也不附手動指令讓模型去跑", "origin": "user", "clarity": "clear", "status": "done", "history": [{"seq": 12, "turn": 1, "what": "create", "why": ""}, {"seq": 44, "turn": 1, "what": "status", "why": "wg_reading_path 改成收尾只交工作、背景量、下次收尾附結果；量不完只寫原因不附手動指令（stop.py 呼叫點、hooks/verify/conftest 不在測試起背景行程）。單元 18 案與 Stop 入口 3 案綠，更接近：收尾當下不再等 3 秒逾時、模型不會再收到可接單的手動指令"}, {"seq": 84, "turn": 2, "what": "reconcile", "why": ""}, {"seq": 115, "turn": 2, "what": "status", "why": "這批改檔（wg_verify_ledger、stop.py 補傳 cfg、wg_release_rules、兩支測試）屬 T1.3 的豁免放寬，沒有動閱讀路徑；T1.1 的案例 verify_reading_path_hook 與 g12w 在 R110 照樣綠，結論不變"}, {"seq": 118, "turn": 2, "what": "reconcile", "why": ""}, {"seq": 181, "turn": 5, "what": "reconcile", "why": ""}], "evidence": [{"kind": "receipt", "ref": "R174", "level": "measured", "covers": ["T1.1"], "seq": 181}], "followup": "", "note": "", "same_class": ""}, "T1.2": {"parent": "T1", "text": "測試不再真的睡到逾時，全庫最慢的同類一起改快", "origin": "user", "clarity": "clear", "status": "done", "history": [{"seq": 14, "turn": 1, "what": "create", "why": ""}, {"seq": 75, "turn": 2, "what": "status", "why": "全庫最慢清單驗過：真的睡到逾時的只有閱讀路徑兩支（8 秒×2，已改假 run）；最慢的主控台追蹤兩案 40 秒→ 3 秒（每窗查一次改一次查全部）；產出物帳本跨案共用讓收尾案例多查 git、錄出依順序的錄製檔 → conftest 每案自己的帳本，verify_stop_reconcile 59 秒；scorecard 日期過期釘住。更接近：全量少約 100 秒、單跑不再因順序錯紅"}, {"seq": 84, "turn": 2, "what": "reconcile", "why": ""}, {"seq": 118, "turn": 2, "what": "reconcile", "why": ""}, {"seq": 181, "turn": 5, "what": "reconcile", "why": ""}], "evidence": [{"kind": "receipt", "ref": "R174", "level": "measured", "covers": ["T1.2"], "seq": 181}], "followup": "", "note": "", "same_class": ""}, "T1.3": {"parent": "T1", "text": "共用工作樹裡，已 commit 的檔不會因為別的 session 沒提交的改動就免不掉案例宣告（做法先給使用者拍板）", "origin": "user", "clarity": "clear", "status": "done", "history": [{"seq": 16, "turn": 1, "what": "create", "why": ""}, {"seq": 84, "turn": 2, "what": "reconcile", "why": "等使用者拍板放寬做法（提案：三個豁免的比對範圍縮成同根的程式檔＋案例檔），拍板後動手"}, {"seq": 112, "turn": 2, "what": "status", "why": "使用者拍板「縮成程式＋案例檔」：exemption_peers 三個豁免共用、NET_UNCHANGED 改逐檔判、stop.py 補傳 cfg、規則與 TECH 表更新。更接近：新案舊碼三支全紅、新碼綠，範圍 7 項 1104 案綠；文件被別的 session 改著不再擋豁免"}, {"seq": 118, "turn": 2, "what": "reconcile", "why": ""}, {"seq": 181, "turn": 5, "what": "reconcile", "why": ""}], "evidence": [{"kind": "receipt", "ref": "R174", "level": "measured", "covers": ["T1.3"], "seq": 181}], "followup": "", "note": "", "same_class": ""}, "T1.4": {"parent": "T1", "text": "做完重量被擋次數，跟改之前對照", "origin": "user", "clarity": "clear", "status": "partial", "history": [{"seq": 18, "turn": 1, "what": "create", "why": ""}, {"seq": 84, "turn": 2, "what": "reconcile", "why": "改完後 live 只有約 25 分鐘樣本（ReadingPath 0 次、逾時 0、手動跑 0），隔天用同一組腳本量 2 天窗再對照 212 次基線"}, {"seq": 118, "turn": 2, "what": "reconcile", "why": "改完後 live 樣本太短，隔天用同一組腳本量 2 天窗再對照 212 次基線"}, {"seq": 181, "turn": 5, "what": "reconcile", "why": "改完後 live 樣本太短，隔天用同一組腳本量 2 天窗再對照 212 次基線"}], "evidence": [{"kind": "receipt", "ref": "R83", "level": "measured", "covers": ["T1.4"], "seq": 181}], "followup": "改完後 live 樣本太短，隔天用同一組腳本量 2 天窗再對照 212 次基線", "note": "", "same_class": ""}, "T1.5": {"parent": "T1", "text": "驗證範圍閘本身不再造成重跑：改一個檔不讓無關的項目作廢、一支紅不讓同指令的其他項目跟著算紅", "origin": "user", "clarity": "clear", "status": "done", "history": [{"seq": 126, "turn": 5, "what": "create", "why": ""}, {"seq": 129, "turn": 5, "what": "status", "why": "使用者拍板：作廢範圍用「讓 AI 宣告每項依賴」（每項另列依賴的程式檔，只有改到這些才作廢；沒宣告的項目照舊任何程式改動都作廢）；一支紅的部分照提案直接修（紅的清單完整才放）"}, {"seq": 178, "turn": 5, "what": "status", "why": "depends（項目宣告依賴，依賴外的程式改動不作廢）與收據紅案清單（清單完整時同指令沒紅的項目照算綠）都上線；新案 9 支舊碼紅、新碼綠，範圍 1017 案＋MCP smoke 綠；本場宣告已實際用上 depends（smoke 項不被 wg_release_rules 的修改作廢）"}, {"seq": 181, "turn": 5, "what": "reconcile", "why": ""}], "evidence": [{"kind": "receipt", "ref": "R174", "level": "measured", "covers": ["T1.5"], "seq": 181}, {"kind": "case", "ref": "hooks/verify/verify_verify_scope.py::test_red_case_only_reddens_its_own_item", "level": "read", "covers": ["T1.5"], "seq": 181, "red_then_green": true}], "followup": "", "note": "", "same_class": "背景自寫收據（_self_run_item_ok）同樣整份算紅，已一起改；指令項目維持整條算；need_goal reconcile 的證據先後仍以節點最後一次改動算、不看 depends（另記追蹤）"}}, "points": {"scope_parts": ["c:/users/holylight/.claude|hook 共用模組層", "c:/users/holylight/.claude|hook 事件處理層", "c:/users/holylight/.claude|純函式與資料層", "c:/users/holylight/.claude|專案文件層", "c:/users/holylight/.claude|工具腳本與 MCP 層", "c:/users/holylight/.claude|記憶資料層"], "scope_dirs": {"mark": 181, "dirs": ["c:/users/holylight/.claude|hooks", "c:/users/holylight/.claude|memory", "c:/users/holylight/.claude|(root)"], "sent": true}, "scope_pending": [], "scope_sent_turn": 7, "multi_hinted": ["C:\\Users\\holylight\\.claude\\_AIDocs\\_CHANGELOG.md", "C:\\Users\\holylight\\.claude\\hooks\\verify\\verify_stop_reconcile.py", "C:\\Users\\holylight\\.claude\\TECH.md"]}}]}
```
<!-- need-goal:end -->