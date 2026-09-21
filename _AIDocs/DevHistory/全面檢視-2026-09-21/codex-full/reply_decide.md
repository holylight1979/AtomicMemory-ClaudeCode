**不批准整包直接執行；優先做最終注入記帳、對齊評估器與歸因標註集，其餘依下表拍板。** 修正版方向正確，但回合身分、統計分母及來源定位仍有未封住的漏洞。

已完整重讀計畫及 §8，以下只展開新增發現或採納後仍存在的缺口。全程未修改檔案；驗證採讀碼與不落盤的合成案例，未執行可能寫入正式資料的完整測試套件。合成結果不代表線上發生率。

## 零容忍 BLOCK 清單（項目 → 為什麼 → 要先補什麼）

### B1．1a-2、1a-4：回合邊界尚未統一，不能只修取文與加去重集合

**為什麼：**

- `_is_real_user_prompt()` 修成忽略通知後，UPS 仍會覆寫 `turn_injected`、遞增 `turn_seq`。因此「取文認定的回合」與「注入記帳的回合」仍可能不同。[UPS:352](/C:/Users/holylight/.claude/hooks/handlers/user_prompt_submit.py:352)、[取文:631](/C:/Users/holylight/.claude/hooks/wg_evasion.py:631)
- 子代理紀錄只有 `agent_id/tool_use_id/at`，**沒有來源回合**；Stop 掃所有未歸因紀錄，再套用當輪 outcome，且把子代理摘要與父回合全文合併判用。[紀錄端:85](/C:/Users/holylight/.claude/hooks/handlers/post_tool_use.py:85)、[歸因端:449](/C:/Users/holylight/.claude/hooks/handlers/stop.py:449)
- 本次以原函式、記憶體替身重現：同 atom 父回合成功、子代理失敗，產生 **兩次寫入：一勝、一敗**；一筆舊子代理紀錄也會被計入新的成功回合。

**要先補：**統一真實使用者回合 ID；子代理綁來源回合與工具呼叫 ID；以 atom 的完整定位識別去重，先收齊證據再結算。同 atom 同輪結果衝突，我拍板為 **unknown、不更新 α/β、保留分項證據**，不能依迴圈順序取第一筆。這是技術正確性決策，不需問使用者。

### B2．1a-8、4-5：Codex 紀錄改計數會改變驗收分母；「標 20 筆」也不是充分條件

**為什麼：**

未綁定紀錄不是單純無消費者的垃圾：`promotion_stats()` 把所有 `pass/fail/uncertain` 列計入樣本與 uncertain 比例。刪列而未改讀取端，會改變轉正判定。[寫入端:542](/C:/Users/holylight/.claude/hooks/codex_companion.py:542)、[統計端:477](/C:/Users/holylight/.claude/tools/codex-companion/acceptance.py:477)

本次合成驗證保持裁判結果完全相同：

| 條件 | uncertain 比例 | 已標註 fail | `promotion_ready` |
|---|---:|---:|---|
| 181 筆未綁定＋20 筆裁判結果 | 90.05% | 1 筆，判真陽性 | false |
| 移除未綁定列 | 0% | 同一筆 | true |

此外，目前條件是 **總樣本 ≥20**，不是人工標註 ≥20；只有一筆標註也可能達標。

實際檔案截至最新紀錄往前 30 天共 **206 列，24 列 bound、182 列未綁定、人工標註 0 列**。全檔沒有 pass 列。這些尚未排除測試污染，不能直接當裁判品質樣本。

**要先補：**分開「綁定覆蓋率」與「已送審案件的裁判品質」，寫入端、報表及轉正條件同步修改；人工標註需包含已知合格、已知缺陷、證據不足案例，才能量誤擋與漏放。**目前保留裁判，不因零 pass 或 20 這個數字決定去留。** hint 支線停寫可另外先做。

### B3．2-1：`rare_token_min 2→3` 沒封住短節錄誤判，DF 門檻也缺語料範圍契約

**為什麼：**

判用條件是「命中數達標 **或** 覆蓋率達標」。改比對節錄後，分母變小，覆蓋率反而更容易達標。[判定:1129](/C:/Users/holylight/.claude/hooks/wg_atoms.py:1129)

本次直接執行既有 tokenizer 與判定函式：

- 節錄 `alphabet betatron`，回合只出現 `alphabet`，門檻設 3：仍 **used=true，shared=1，containment=0.5**。
- DF 語料只有 5 張各含獨有詞的卡，比例設 0.1：獨有詞的 DF=1，大於門檻 0.5，連完全命中的詞也被濾光。

本機還開著 embedding 平手裁決；門檻改為 3 後，共享兩詞會進入另一條判定／耗時路徑，不能只驗純詞彙版本。[設定:123](/C:/Users/holylight/.claude/workflow/config.json:123)、[分支:1145](/C:/Users/holylight/.claude/hooks/wg_atoms.py:1145)

**要先補：**先完成 2-3 標註集，再共同校準命中數、覆蓋率、短節錄與 embedding 分支；明定 DF 母體及小語料處置。**撤掉預先拍死的 2→3；0.1 保持實驗候選。**

### B4．1a-6：「週健檢 episodic 列變綠」不是正確驗收條件

**為什麼：**

健檢目前以「有近期 session、沒有近期產物」判停擺；生成端另有改檔／閱讀／知識佇列及時長資格。[健檢:222](/C:/Users/holylight/.claude/tools/health-weekly.py:222)、[生成資格:42](/C:/Users/holylight/.claude/hooks/wg_episodic.py:42)

只擴大掃描範圍，仍可能出現：

- 所有 session 都不符合生成資格，卻報故障。
- 一個專案有新產物，掩蓋另一個符合資格卻沒有產物的專案。

**要先補：**驗收改成能區分「成功產出／正常跳過／符合資格但失敗或逾時／資料不足」，並保留專案對應。正常跳過不必變綠，未知不能冒充健康。既有跳過原因紀錄足以承載，不另建常駐框架。

### B5．3-6：provenance 不能只加一個看似精確的行號

*Provenance 指可追溯到原始證據的位置。*

**為什麼：**

failure reader 丟掉 JSONL 原始位置，只留下 assistant 文字，再以分隔線串接；回傳值也只有文字與末端 offset。[讀取:89](/C:/Users/holylight/.claude/hooks/extract-worker.py:89)、[串接:358](/C:/Users/holylight/.claude/hooks/extract-worker.py:358)

user-extract 現有 `src` 是 `session_id＋prompt_count` 形成的 turn ID，**不是 transcript 行號**，不能直接複製成 `{sid}-L{line}` 的保證。[ID 產生:55](/C:/Users/holylight/.claude/hooks/handlers/ups_gates.py:55)、[寫入:373](/C:/Users/holylight/.claude/hooks/user-extract-worker.py:373)

**要先補：**reader 保留原始訊息位置與區塊對應；萃取結果引用已存在的來源 ID，由程式驗證能回查原文。跨多段的結論允許多個來源；沒有位置就明示缺來源，禁止補造行號。worker 起訖 log 可獨立先做。

### B6．4-2：預算撞頂不能證明需要四層棄權閘

**為什麼：**

計畫以「30% 撞頂、40% 候選被砍」支持棄權，但這些是容量數字，沒有回答被砍或被送出的內容是否錯誤。[計畫:42](/C:/Users/holylight/.claude/memory/_staging/next-phase-全面檢視-2026-09-21.md:42)

既有評估器的負例量測只回答「負例查詢是否回傳任何候選」，無法量「正例查詢同時夾入無關卡」。[評估器:153](/C:/Users/holylight/.claude/tools/memory-eval/run.py:153)

排名差距也不是經校準的信心：兩張都相關時差距小，不能因此整輪棄權。外部研究證明棄權值得測試，沒有證明本機需要這四層串接。[原論文](https://arxiv.org/abs/2604.27283)

**要先補：**先建立查詢—卡片相關性標註，分開量誤送與漏送；一次只測一個閘，加入單候選、多張皆相關案例。**目前 BLOCK 上線四層閘，允許離線驗證是否有缺口。**

### B7．4-4：TEPA／Hindsight 尚未證明比修好現有機制多解決什麼

這裡不重述 #6 已指出的公式混用問題。

**新增缺口：**本機已有 Evidence 裁決、Depends 條件及 Supersedes。衝突裁決已按證據等級、時間等排序；TEPA 的新價值必須用「這些現有路徑修好後仍處理不了」的案例證明。[衝突裁決:219](/C:/Users/holylight/.claude/tools/memory-conflict-detector.py:219)、[Depends:62](/C:/Users/holylight/.claude/lib/atom_spec.py:62)

TEPA 論文本身也指出，在其單跳事實整合設定，強的同鍵覆寫基線可與之匹敵；不能把整套撤銷狀態機視為必需。[TEPA](https://arxiv.org/abs/2608.07429)

**要先補：**先提出至少一個本機實例，以現有機制為基線證明增量，再談 schema。**本輪砍新增 conflict_key／信心更新機制；保留研究資料即可。**

### B8．跨項執行契約：每 Phase 自動 commit 不成立

計畫寫「每 Phase 一個 commit，口令上GIT後 push」，但既有契約是 **口令前不先 commit**；Stop 的提示也明確如此。[計畫:128](/C:/Users/holylight/.claude/memory/_staging/next-phase-全面檢視-2026-09-21.md:128)、[既有契約:907](/C:/Users/holylight/.claude/hooks/handlers/stop.py:907)

**要先補：**Phase 作為驗證與交付切點；commit、push 都依既有口令授權。這次是只讀審查，沒有任何版控寫入授權。

## 逐項評分表

每個 Phase 內依 checkbox 出現順序編號。0＝無直接貢獻，1＝間接或有限，2＝明確，3＝核心貢獻；五維等權，合計 15 分。**BLOCK 不給分，也不以其他優點抵銷。**「做」若是研究項，只批准對照實驗，不代表批准上線。

| Phase/項 | 立即有效 | 自我迭代 | 不飄移 | 體貼親和 | 不zombie | 合計 | 建議（做／延後／砍） | 一句理由 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| 1a-1 recall-miss 型別護欄 | 2 | 2 | 3 | 2 | 3 | 12 | 做 | 本次重現字串佇列造成 AttributeError；修範圍小。[證據](/C:/Users/holylight/.claude/hooks/wg_recall_miss.py:89) |
| 1a-2 Agent 取文／通知邊界 | — | — | — | — | — | — | 延後：BLOCK B1 | 必須與 UPS 的回合身分一起修。 |
| 1a-3 retry 改本輪差分 | 2 | 3 | 3 | 2 | 3 | 13 | 做 | 僅改 outcome 讀法，保留其他消費者的 session 累計。[證據](/C:/Users/holylight/.claude/hooks/handlers/stop.py:366) |
| 1a-4 主／子代理去重 | — | — | — | — | — | — | 延後：BLOCK B1 | 須先定來源回合與衝突結算。 |
| 1a-5 forget 共用保護判定 | 0 | 2 | 3 | 2 | 3 | 10 | 做 | 確有 EXACT／PREFIX 判定差異；目前忘卻未啟用，不宣稱立即改善召回。[證據](/C:/Users/holylight/.claude/lib/atom_locations.py:209) |
| 1a-6 健檢／heartbeat／跳過紀錄 | — | — | — | — | — | — | 延後：BLOCK B4 | 修驗收語意後即可做，不追求強制變綠。 |
| 1a-7 advisory／測試 Logs 隔離 | 2 | 1 | 3 | 3 | 3 | 12 | 做 | 當前 health、followup 例外已有回告；補剩餘靜默路徑，避免重複告警。[證據](/C:/Users/holylight/.claude/hooks/handlers/session_start.py:387) |
| 1a-8 hint／裁判紀錄／cross_session | — | — | — | — | — | — | 延後：BLOCK B2 | 拆項：hint 可先做，裁判分母先修，共享開關先保留。 |
| 1a-9 TECH／Architecture 校正 | 2 | 1 | 3 | 3 | 3 | 12 | 做 | 以實際設定與官方契約改文件，不把估算改寫成實測。[證據](/C:/Users/holylight/.claude/hooks/handlers/session_end.py:207) |
| 1b-1 最終輸出後統一記帳 | 3 | 3 | 3 | 3 | 2 | 14 | 做，最高優先 | 是曝光、去重、使用歸因共同依賴的真相來源。[證據](/C:/Users/holylight/.claude/hooks/handlers/ups_inject.py:381) |
| 1b-2 對齊評估器 | 2 | 3 | 3 | 2 | 3 | 13 | 做 | 現行 retrieve 沒走實際融合與裁切，無法保護後续變更。[證據](/C:/Users/holylight/.claude/tools/memory-eval/run.py:77) |
| 1b-3 舊 sidecar 快照／切點 | 1 | 3 | 3 | 2 | 3 | 12 | 做 | 新事件另算；衰減中的累計值不能直接減快照當新樣本。[證據](/C:/Users/holylight/.claude/lib/atom_access.py:485) |
| 2-1 DF／門檻／節錄／rescue | — | — | — | — | — | — | 延後：BLOCK B3 | 先校準完整判定，不能先固定 2→3。 |
| 2-2 糾正標待查 | 1 | 2 | 2 | 2 | 2 | 9 | 延後 | 保留診斷價值，但不新增待辦噪音或自動負分。[證據](/C:/Users/holylight/.claude/hooks/wg_friction.py:212) |
| 2-3 使用判定標註集 | 2 | 3 | 3 | 3 | 3 | 14 | 做，最高優先 | 校準誤判與漏判的必要基礎，可與評估器並行準備。 |
| 2-4 晉升／session 封頂政策 | 0 | 2 | 3 | 2 | 3 | 10 | 延後 | 我拍板先維持統計單位与門檻，修去重後再測；不問使用者選數字。[證據](/C:/Users/holylight/.claude/lib/atom_access.py:571) |
| 2-5 gain／裁切／BM25 對照 | 1 | 2 | 3 | 2 | 3 | 11 | 做，限離線 | 逐項測；没有端到端證據前不直接部署 gain=0。[證據](/C:/Users/holylight/.claude/hooks/handlers/ups_search.py:320) |
| 2-6 Supersedes 全路徑 | 2 | 3 | 3 | 3 | 2 | 13 | 做 | 路徑清單須包含子代理與 compact 復原，不只 UPS／Related。[證據](/C:/Users/holylight/.claude/hooks/wg_atoms.py:940) |
| 3-1 `/extract` 路徑 A／信心描述 | 2 | 2 | 3 | 3 | 3 | 13 | 做 | 手動萃取需明確輸入與可見結果，不能順手復活舊自動 writeback。[證據](/C:/Users/holylight/.claude/hooks/extract-worker.py:927) |
| 3-2 skill 稽核器契約 | 2 | 2 | 3 | 3 | 3 | 13 | 做 | 修解析與真假失敗分類；name／description 的本機要求也須與官方規則分開。[證據](/C:/Users/holylight/.claude/skills/skill-creator/scripts/audit-skill.py:67) |
| 3-3 active skill 寫入與固定儀式 | 2 | 3 | 3 | 3 | 3 | 14 | 做 | 已讀到推測迴寫、手改索引、固定四題訪談；直接消除錯寫與打擾。[證據](/C:/Users/holylight/.claude/skills/consciousness-stream/SKILL.md:119) |
| 3-4 memory skill／Architecture | 2 | 1 | 3 | 3 | 3 | 12 | 做 | 空參數行為確實互斥；讓指令一次可用。[證據](/C:/Users/holylight/.claude/skills/memory/SKILL.md:151) |
| 3-5 fork／cache 顯示／孤兒清理 | 1 | 1 | 2 | 2 | 3 | 9 | 延後，拆項排程 | fork 有依據；cache 顯示非核心，外部引用未查完不刪 helper。[證據](/C:/Users/holylight/.claude/hooks/handlers/pre_tool_use.py:1032) |
| 3-6 failure provenance／worker log | — | — | — | — | — | — | 延後：BLOCK B5 | 起訖 log 可先做，來源標記需可驗證定位。 |
| 3-7 skill-doctor／可見性裁剪 | 1 | 1 | 2 | 2 | 3 | 9 | 延後 | 先出本機成本基線，再裁；零呼叫不等於沒價值。 |
| 3-8 hook 程序合併／AEC 涵蓋 | 0 | 1 | 2 | 1 | 2 | 6 | 延後 | 尚無本次真實延遲收益證據；保持既定對照前置條件。 |
| 4-1 constraint pinning 缺口驗證 | 0 | 1 | 2 | 1 | 3 | 7 | 延後 | 只驗缺口；既有復原機制已存在，不預設需要再注入。[證據](/C:/Users/holylight/.claude/hooks/handlers/post_tool_batch.py:32) |
| 4-2 四層棄權閘 | — | — | — | — | — | — | 延後：BLOCK B6 | 先證明誤注入，再決定是否加閘。 |
| 4-3 Related 三組對照 | 1 | 2 | 3 | 2 | 3 | 11 | 做，限離線 | 現有 gate 不接 query；關閉對照有明確精簡價值。[證據](/C:/Users/holylight/.claude/hooks/handlers/ups_inject.py:102) |
| 4-4 TEPA／Hindsight | — | — | — | — | — | — | 砍本輪：BLOCK B7 | 尚未證明超越既有機制的本機增量。 |
| 4-5 裁判 20 筆標註後去留 | — | — | — | — | — | — | 延後：BLOCK B2 | 先修抽樣與分母，再談保留或移除。 |

兩項外部契約已重新核對：官方 skill frontmatter 欄位均非必填，`description` 為建議；fork 繼承父對話，而一般子代理不繼承。因此 **不可把父代理的 `already_injected` 無條件套到所有子代理**。[官方 skills](https://code.claude.com/docs/en/skills#frontmatter-reference)、[官方 fork 說明](https://code.claude.com/docs/en/sub-agents#fork-the-current-conversation)

## 只有使用者能決定的（白話三段）

**本輪沒有必須先問使用者才能繼續的事項。** 唯一保留人工裁決的是：日後是否把精簡結果同步成其他機器／同事共同承受的預設。

**錯哪裡：**計畫把三類共享變更綁在一起：關閉 `cross_session`、裁 skill 可見性、刪 helper。本機確認 `cross_session.enabled=true`；其他機器的依賴數量尚未查到，未知不能當成 0。本機使用率不足以決定別人的功能去留。[設定](/C:/Users/holylight/.claude/workflow/config.json:75)

**改什麼：**本輪保留共享預設與 helper；先完成本機報表、引用清查和測試。若未來確需跨機器套用，再提交具體影響清單與回復方式，讓使用者只決定同步範圍與時機。

**具體成效與風險：**不阻擋記帳、歸因與文件修補，也不會讓其他機器突然失去入口。代價是共享精簡收益延後，這比在資訊不足時刪除共用功能合理。

gain、session 封頂、DF 門檻及局部可回復的整理，均由審查者依驗證結果決定；不列使用者選擇題。

## 被帶偏的地方

1. **把「塞不下」推成「該增加棄權演算法」。** 這跳過了相關性標註。先分辨容量不足、排序錯誤與無關注入，才能決定修哪一層。

2. **為了借用 TEPA 先增加 conflict_key。** 順序應是先找現有 Evidence／Depends／Supersedes 無法處理的實例；找不到就不新增資料欄位與生命週期。

3. **把觀測指標當成果。** episodic 變綠、uncertain 下降、判用率下降都可能只是分母或分類方式變了。驗收必須保留相同案例，確認錯誤真的減少且沒有新增漏判。

4. **把工程判斷轉交使用者。** 計畫仍要求使用者決定 gain、session 封頂與裁判去留；目前真正缺的是可靠實驗與抽樣，並非使用者偏好。主持者應守住長期契約與優先序，程式與數字的判斷由我們完成。
