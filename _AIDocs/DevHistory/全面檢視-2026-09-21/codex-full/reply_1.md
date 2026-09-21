**結論：值得優先做的是修正過時的 hook 契約、接入原生 cache 量測、避免 fork 子代理重複注入；未找到足以整套取代 atom 檢索、品質閘門、晉升或遺忘機制的原生功能。**

本次已比對官方文件、GitHub CHANGELOG／Release，以及本機實作。範圍以 **2026-05-01～2026-09-21** 為準；早於此期間的功能只用於釐清誤認，不列為新成果。

- **本機實測**：`C:\Users\holylight\.local\bin\claude.exe --version` 回傳 **2.1.252**，不代表其他 IDE 內嵌版本也相同。
- **官方最新可核對版本**：**2.1.278，2026-09-19**。[官方發布](https://github.com/anthropics/claude-code/releases/tag/v2.1.278)
- **本機靜態盤點**：21 個 active skill，其中 **9 個已有 `disable-model-invocation: true`**，不能把 21 個 skill 全文都算成常駐負擔。
- 全程唯讀；未升級、未改檔，也未啟動會觸發本機寫入 hooks 的測試 session。下列人日與收益均為估算，沒有冒充實測改善數字。

**候選清單**

| # | 名稱 | 來源（版本／日期／URL、檔案:行） | 機制 | 類型 | 對本系統的意義 | 第一個 session 看得到的效果 | 成本／風險 | 證據等級 |
|---|---|---|---|---|---|---|---|---|
| 1 | 修正 hook timeout 契約 | **2.1.268／09-10**：[Release](https://github.com/anthropics/claude-code/releases/tag/v2.1.268)；[官方 timeout 規格](https://code.claude.com/docs/en/hooks#sessionend)；[TECH.md:56](C:/Users/holylight/.claude/TECH.md:56)、[settings.json:193](C:/Users/holylight/.claude/settings.json:193) | UPS 的 30 秒、SessionEnd 的 1.5 秒，目前是預設值，不是不可調上限。SessionEnd 可由設定檔的 per-hook timeout 提高整體預算，最高 60 秒，或用環境變數指定；plugin hook 的 timeout 不會自動提高整體預算。2.1.268 另修正環境變數未延長「未指定 timeout 的 hook」問題。 | **可借力→補強；精簡過時契約** | `TECH.md` 仍寫「settings 設 30 秒無效、只能 detached」，已不符合現行官方規格。但本地 LLM 約 60 秒，尚不足以據此刪掉 detached worker。 | 可直接驗證收尾是否被預算中止，排除錯誤根因假設。 | 0.5–1 人日；拉長退出等待，且多機版本可能不同。 | 官方引述＋本機設定查核；未實測 timeout |
| 2 | 原生 prompt cache 統計接入 statusline | **2.1.251／08-28**：[Release](https://github.com/anthropics/claude-code/releases/tag/v2.1.251)；[欄位規格](https://code.claude.com/docs/en/statusline#prompt-cache-fields)；[statusline.py:38](C:/Users/holylight/.claude/tools/statusline.py:38) | 原生 `prompt_cache` 提供命中率、miss、TTL（快取存活時間）及 warm/cold。可直接把一至兩個欄位顯示在既有 statusline，無須新增日誌推算器。首次主對話 API 回應前欄位可能不存在，且不含子代理請求。 | **可借力→補強** | 搜尋現有 hooks／tools／skills，未找到消費 `prompt_cache` 的實作。既有 `_ctx_segment` 只顯示 context 使用百分比。 | 第一個 session 就能區分「context 很大」與「cache 沒命中」。 | 0.25–0.5 人日；低風險，處理缺欄位即可。 | 官方引述＋程式查核 |
| 3 | fork 子代理只補缺少的 atom | **2.1.232／08-13**：[Release](https://github.com/anthropics/claude-code/releases/tag/v2.1.232)；[fork 規格](https://code.claude.com/docs/en/sub-agents#fork-the-current-conversation)；[pre_tool_use.py:1032](C:/Users/holylight/.claude/hooks/handlers/pre_tool_use.py:1032)、[wg_atoms.py:940](C:/Users/holylight/.claude/hooks/wg_atoms.py:940) | 對話 fork 會繼承父對話、system prompt 與 prompt cache。現行 PreToolUse 對所有 `Agent/Task` 都檢索並 prepend atom，未分辨 `subagent_type: fork`。`build_injection_blob` 已接受 `already_injected`，但此呼叫點沒有傳入。 | **可被原生部分取代→精簡** | 原生已負責傳遞父對話中仍有效的記憶；fork 應只補子任務需要、父 context 沒有的 atom。一般新 context 子代理仍需現有注入。 | 第一個命中相同 atom 的 fork 就能避免重複內容；現有注入預算為 700 tok，**不代表每次都能省 700 tok**。 | 0.5–1 人日；須辨識「目前仍在 context」與單純歷史曝光。 | 官方引述＋靜態缺口；實際重複量未測 |
| 4 | 用 `/skill-doctor` 做技能常駐成本裁剪 | **2.1.261／09-04**：[Release](https://github.com/anthropics/claude-code/releases/tag/v2.1.261)；[官方說明](https://code.claude.com/docs/en/skills#find-unused-skills)；[skill-cost-measure.py:74](C:/Users/holylight/.claude/skills/skill-creator/scripts/skill-cost-measure.py:74) | 原生命令列出技能的 context 成本及使用情況。搭配 `skillOverrides` 可設為只保留名稱、只供手動呼叫或停用。既有成本腳本則統計指定 transcript、技能觸發前後的整體 usage，兩者口徑不同。 | **可借力→補強；部分精簡** | 不再另寫「所有技能常駐成本／未使用清單」掃描器；保留現有腳本的前後對照用途。先看報告再裁剪剩餘 12 個非手動限定技能。 | 首次就可看到成本排序；新安裝技能的「未使用」不能直接解讀成無價值。 | 0.25–0.5 人日；誤停用會降低自動觸發率。 | 官方引述＋21／9 個靜態計數；命令未實跑 |
| 5 | 借官方 resume 修正，減少不必要 handoff | **2.1.261／09-04**：[Release](https://github.com/anthropics/claude-code/releases/tag/v2.1.261)；[session 延續規格](https://code.claude.com/docs/en/how-claude-code-works#resume-or-fork-sessions)；[TECH.md:470](C:/Users/holylight/.claude/TECH.md:470) | 2.1.261 修復 resume 遺失並行工具周邊 hook output／context 的問題。原生 resume 延續同一 session；handoff 則把任務重建到新 session。兩者應依是否保留原對話來分工。 | **可借力→補強；條件式精簡** | 本機 2.1.252 尚未包含此修正。若某些人工交接只是為了繞過 resume 遺失注入，可在升級驗證後取消那部分操作；跨模型、跨工具、重置 context 的交接仍保留。 | 第一個「注入→並行工具→退出→resume」案例即可比對內容是否保留。 | 0.5–1 人日；升級與現有 hooks 相容性需驗收。 | 官方已修復紀錄；本機未重現 |
| 6 | 原生共享記憶目錄 | **2.1.234／08-17**：[Release](https://github.com/anthropics/claude-code/releases/tag/v2.1.234)；[memory 規格](https://code.claude.com/docs/en/memory#storage-location)；[native-memory-bridge.py:73](C:/Users/holylight/.claude/tools/native-memory-bridge.py:73) | 原生可透過自訂 memory 目錄，或固定 project directory name，讓不同啟動位置共用資料。這是共用檔案位置，並不等於具 scope 過濾的跨專案檢索。原生 topic 檔仍由模型按需讀取。 | **可借力，但本案不建議遷移** | 未見可取代 Realm／Scope、RRF、證據衝突與效用晉升的機制。本系統已有只放指標的 native bridge，增量有限。 | 未證明優於現有橋接。 | 不立項；若遷移，主要風險是跨專案污染及雙重寫入。 | 官方引述＋現有橋接查核 |
| 7 | skill frontmatter 新控制 | **2.1.152／05-27**：[Release](https://github.com/anthropics/claude-code/releases/tag/v2.1.152)；**2.1.218／07-22**：[Release](https://github.com/anthropics/claude-code/releases/tag/v2.1.218)；[frontmatter 規格](https://code.claude.com/docs/en/skills#frontmatter-reference) | `disallowed-tools` 可在技能運行期間移除工具。`context: fork` 技能的新預設為背景執行，可用 `background: false` 等結果。這些控制執行方式，不會自動改善技能內容或 atom 寫入品質。 | **條件式補強，暫不立項** | 目前 21 個技能未見 `context: fork` 宣告，沒有此預設改變造成的直接遷移工作。含互動裁決或寫入的技能，不宜為了隔離 context 一律改背景。 | 尚未找到本系統第一個 session 必得的增益。 | 先不投入；錯用可能改變裁決順序。 | 官方引述＋frontmatter 搜尋 |
| 8 | OTel 取代通用運行量測 | **2.1.161／06-02** 修復早期事件遺失：[Release](https://github.com/anthropics/claude-code/releases/tag/v2.1.161)；[Monitoring](https://code.claude.com/docs/en/monitoring-usage)；[wg_friction.py:57](C:/Users/holylight/.claude/hooks/wg_friction.py:57) | OpenTelemetry（標準化事件與指標輸出）已有 API／工具耗時、成功失敗與結果大小等資料。原生 `tool_result_size_bytes` 與本機字元估算不是相同單位。它可供通用效能分析，但沒有 atom 有用率、broken refs 或晉升語意。 | **通用量測可部分取代；不取代 Dashboard** | 本機已量工具結果體積，不能再把它報為新機制。除非已有 OTel collector，否則只為重做這項量測導入整套管線不划算。 | 已有 collector 才能立即受益；目前未確認。 | 1–2 人日以上；整合成本大於單一欄位收益。 | 官方引述＋本機量測查核 |
| 9 | Routines／Agent SDK 取代週健檢 | Routines CLI 條件為 **2.1.225+／08-08**：[規格](https://code.claude.com/docs/en/routines)、[Release](https://github.com/anthropics/claude-code/releases/tag/v2.1.225)；[Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)；[TECH.md:482](C:/Users/holylight/.claude/TECH.md:482) | Routines 是雲端觸發與執行；Desktop Local 排程是另一條路徑。Agent SDK 是可程式化的 agent 執行框架，沒有內建本系統的 atom 健檢規則。換框架仍要搬運資料、執行邏輯與權限。 | **無關／不建議替換** | 現有 Windows Task Scheduler 已能執行本機 Python 健檢。沒有理由為 deterministic 的檢查再啟動一個 LLM 工作流。 | 沒有已證明的第一 session 增益。 | 不立項。 | 官方引述＋現有架構查核 |

**最值得做的 5 件（排序＋理由）**

1. **先修正 timeout 文件與驗收基準。**  
   這是已確認的契約失準，會使後續對 episodic／SessionEnd 的診斷走錯方向。修改範圍先限於 `TECH.md` 與 `_AIDocs/ClaudeCodeInternals/cc-native-memory-hooks-mcp.md`；worker 保留。行為驗證用短工作與刻意超時工作分別確認完成／取消，再判斷是否有程式需要精簡。

2. **把原生 `prompt_cache` 接到現有 statusline。**  
   本機 2.1.252 已超過 2.1.251 的版本門檻。只補顯示、缺值處理與既有 statusline 驗證，不另建 cache 日誌系統。回滾可直接撤掉顯示段，不影響記憶管線。

3. **讓 fork 注入利用既有 `already_injected` 去重。**  
   不要單純看到 `fork` 就全部跳過：子任務可能需要父對話沒載入的 atom。驗收至少涵蓋普通子代理、fork 已有 atom、fork 新 atom、父對話剛 compact 四種情況。收益依實際重複內容計算，不以 700 tok 預算當節省量。

4. **用 `/skill-doctor` 裁剪技能可見性，不先刪檔。**  
   首輪先出基線；只有高成本、低使用、且本來就適合人工啟動者，才改為手動限定。用 `skillOverrides` 能保留檔案並快速回滾。現有 `skill-cost-measure.py` 的「觸發後 usage」不是技能的因果成本，仍需對照任務判讀。

5. **把 2.1.261 的 resume 修正納入下一次版本升級驗收。**  
   先證明 hook 注入能完整跨 resume 保留，再縮減因此產生的補救交接。這一項需要升級後的實機結果，不能僅憑官方修復紀錄直接拆 auto-handoff。

以上可拆成小修改；**目前環境為唯讀，因此本輪交付至可驗收的建議範圍，沒有執行檔案修改或升級。**

**明確不建議做的（＋為什麼）**

- **不把 `PostCompact`／`PostToolBatch` 再當新增成果。**  
  兩者都是目前官方事件。`PostCompact` 收到 `compact_summary`，無法改寫壓縮結果；`PostToolBatch` 在整批工具完成後、下一次模型請求前接收 `tool_calls` 並可注入 context。現有 [post_compact.py:95](C:/Users/holylight/.claude/hooks/handlers/post_compact.py:95) 與 [post_tool_batch.py:33](C:/Users/holylight/.claude/hooks/handlers/post_tool_batch.py:33) 已實作 stash→一次性注入。另須更正版本敘述：**PostCompact 在 2.1.76／03-14 已發布**，不是 2.1.159 才首次出現。[官方事件規格](https://code.claude.com/docs/en/hooks#posttoolbatch)、[2.1.76](https://github.com/anthropics/claude-code/releases/tag/v2.1.76)

- **不新增「壓縮前阻擋、要求模型先寫記憶」迴圈。**  
  PreCompact 可阻擋壓縮，但這早在 **2.1.105／04-13** 就存在；不是本期間的新能力。阻止已因 context 超限而進行的恢復壓縮，還可能讓請求直接失敗。本系統已有預存 handoff 與壓縮後復原，不值得再加一層控制迴圈。[官方發布](https://github.com/anthropics/claude-code/releases/tag/v2.1.105)

- **不把 TTL 拉長當成「動態注入進 cache」的解法。**  
  Prompt caching（提示前綴快取）依照請求前綴精確匹配；TTL 只延長有效時間。新追加的 atom 仍要首次處理，但保持不變的歷史內容可以成為後續快取前綴，所以「注入段每輪全額計費」也需要重新量測，不能當永久事實。**2.1.248／08-27 的 `experimental.cacheTtl` 是 agent frontmatter 欄位**，不是任意片段的快取開關。[快取原理](https://code.claude.com/docs/en/prompt-caching)、[2.1.248](https://github.com/anthropics/claude-code/releases/tag/v2.1.248)

- **不把原生 auto memory 換成 atom 主資料層。**  
  Auto memory 與 `/memory` 在 **2.1.59／02-26** 已發布，不能算 5 月後的新功能。目前 `MEMORY.md` 啟動載入上限為 **200 行或 25KB，先到者為準**；topic 檔按需讀取。共享目錄不等於跨專案權限／相關度檢索，也未查到官方的證據裁決或效用晉升等價機制。[2.1.59](https://github.com/anthropics/claude-code/releases/tag/v2.1.59)、[原生記憶規格](https://code.claude.com/docs/en/memory#how-it-works)

- **不把 21 個 skill 全部改 plugin。**  
  Plugin 的主要增量是分發、版本管理、命名空間與打包 hooks／MCP；不會因為包裝改變而消除技能描述成本。現在是多機 git 共用，尚無足以抵銷搬遷成本的分發需求。真要對外發布時，再抽取不含個人記憶與機器路徑的元件。[官方 plugin 適用條件](https://code.claude.com/docs/en/plugins#when-to-use-plugins-vs-standalone-configuration)

- **不因原生 AGENTS.md 支援而動本專案的 CLAUDE.md。**  
  **2.1.277／09-18** 新增在沒有 CLAUDE.md 時讀 AGENTS.md，且仍有平台限制。本專案 [CLAUDE.md:2](C:/Users/holylight/.claude/CLAUDE.md:2) 明確載入 IDENTITY、USER、MEMORY，沒有可直接刪除的 AGENTS 相容橋接。[官方發布](https://github.com/anthropics/claude-code/releases/tag/v2.1.277)

- **不為事件完整度而把所有 hook 都掛上。**  
  `SubagentStart/Stop`、`Notification`、`PermissionRequest` 本身都不是這次期間才出現。期間內值得注意的是 **2.1.251／08-28** 新增 `PreModelSwitch/PostModelSwitch` 與 resume 快取成本欄位，以及 **2.1.268／09-10** 修復 print mode 的 PermissionRequest；目前沒有理由再加模型切換守門。**2.1.152／05-27** 的 `reloadSkills`、`sessionTitle` 與 `MessageDisplay` 也未找到本系統未滿足的剛需。[2.1.251](https://github.com/anthropics/claude-code/releases/tag/v2.1.251)、[2.1.268](https://github.com/anthropics/claude-code/releases/tag/v2.1.268)、[2.1.152](https://github.com/anthropics/claude-code/releases/tag/v2.1.152)

**未查到／不確定的**

1. **PostToolBatch 的首次官方發布版本：未查到。**  
   現行官方 docs 有完整規格，但此次查到的官方 CHANGELOG 沒有同名發布項。本機註解「2.1.159+」能作為既有相容性線索，不能據此宣稱首發日期。

2. **`/skill-doctor` 的可用性存在官方資料差異。**  
   文件寫 **2.1.252+ 且依賴 feature-flag fetching**，Release 則在 **2.1.261** 列為新增。因此本機 2.1.252 是否能用，仍須在實際 Claude session 確認；不能只用版本號判定。

3. **cache 命中率、fork 重複 tok、SessionEnd 耗時：尚無本輪實測。**  
   已確認量測入口與程式缺口，尚不能給出省費百分比，也不能把 timeout 契約落差直接判為 episodic 停擺根因。

4. **CLAUDE.md／rules 的現行載入能力不構成新的 atom 替代品。**  
   上層指令、子目錄延遲載入及 `paths` 規則處理的是「何時載入指令」。沒有找到 5 月後新增、足以取代本系統按 prompt 檢索與效用歸因的官方機制。[載入規則](https://code.claude.com/docs/en/memory#how-claudemd-files-load)

5. **未找到期間內可讓 hooks 任意編輯既有 context 的官方新 API。**  
   Anthropic 官方部落格介紹 context editing、memory tool 與 Agent SDK 的文章是 **2025-09-29**，且區分 Claude API 與 Claude Code 能力；不能拿來證明 2026 年本地 hook 新增了相同控制權。[官方公告](https://www.anthropic.com/news/claude-sonnet-4-5)

6. **Routines 的首次公開日期未由本次官方部落格搜尋確認。**  
   本報告只採用現行官方規格與已確認的 CLI 版本門檻，沒有把版本門檻誤寫成產品首發日期。
