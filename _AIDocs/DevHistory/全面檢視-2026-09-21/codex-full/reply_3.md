**結論：優先修正現有 skill 的失效指令、寫入契約與評估方法；目前沒有足夠證據，支持再整套導入另一個記憶、守門或多代理框架。** 外部最值得借用的是「有／無 skill 的對照評估」與「只留下無法從程式碼重新取得的經驗」，而不是更多自動萃取。

本次完成網頁調查、21 個本機 `SKILL.md` 對照、現有 skill 稽核程式實跑，以及工具輸出統計分析。沒有修改檔案、安裝套件或執行付費模型評估。

查詢日為 **2026-09-21**。GitHub 頁面顯示 superpowers 約 289k stars、ECC 約 264k、gstack 約 134k；這只能證明關注度，不能證明改善成功率。調查也使用 awesome 清單、HN、Reddit 與 X 搜尋，但機制判斷以下列官方文件、專案原始碼及本機實作為準。[superpowers](https://github.com/obra/superpowers)、[ECC](https://github.com/affaan-m/ECC)、[gstack](https://github.com/garrytan/gstack)

**本機先確認的三個重要數字**

| 檢查 | 結果 | 解讀 |
|---|---|---|
| 21 個 active skill 的現有稽核 | **19 個失敗，全部因缺少自訂 `triggers` 欄位**；另外 2 個通過 | 是本機稽核契約與現有技能不一致，**不代表 Claude Code 無法載入這 19 個 skill**。[稽核規則](C:/Users/holylight/.claude/skills/skill-creator/scripts/audit-skill.py:72) |
| 觸發評估 | 只有 2 個 skill 有 `evals/triggers.json`；目前稽核只檢查檔案、案例數與占位文字 | 有測試資料，不等於已測試模型會不會正確觸發。[檢查實作](C:/Users/holylight/.claude/skills/skill-creator/scripts/audit-skill.py:211) |
| 現存工具輸出統計 | 3 筆 session、65 次工具呼叫、67,631 字元，達既定超量門檻者 **0 筆** | 樣本很小，但目前不能用它支持「急需再裝輸出壓縮器」。門檻預設為 20,000 字元。[統計檔](C:/Users/holylight/.claude/Logs/guard-tool-result-stats.jsonl:1)、[量測程式](C:/Users/holylight/.claude/hooks/wg_friction.py:112) |

**候選清單**

下表成本為本次估算，並非實測工時。「第一個 session 效果」除上述數字外，均是可驗證的預期，不冒充已達成成果。

| # | 名稱 | 來源（URL／檔案:行） | 機制 | 類型 | 對本系統的意義 | 第一個 session 看得到的效果 | 成本／風險 | 證據等級 |
|---|---|---|---|---|---|---|---|---|
| 1 | 官方 skill／plugin 對照評估 | [官方 skill-creator](https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md)、[plugin evals](https://code.claude.com/docs/en/plugin-evals) | 同一題在隔離環境分別跑有技能與無技能版本。比較任務結果，而非只看是否呼叫 Skill。核心量是 **Δ＝有技能得分－無技能得分**，搭配時間與 token。 | **補強，優先** | 本機已有成本記錄與 atom 評估，但未找到同題 skill 成效對照；trigger JSON 也沒有真正執行模型。 | 第一批案例就能區分「有幫助」與「只是增加流程」。 | 0.5–1 人日起；模型用量、評分偏差 | 官方引述＋本機程式核對；收益待測 |
| 2 | 本機 skill 契約校正 | [audit-skill.py:72](C:/Users/holylight/.claude/skills/skill-creator/scripts/audit-skill.py:72)、[Agent Skills 規格](https://agentskills.io/specification) | 把平台必需欄位與本機偏好分開。`triggers`、`pattern` 可以是自己的慣例，但不能冒充官方必填。500 行也應視為編寫建議，而不是平台載入紅線。 | **精簡，優先** | 直接消除目前 19 個錯誤判定，避免往全部 skill 補沒有執行用途的欄位。 | 同一批稽核立即得到可解讀的結果。 | 約 0.5 人日；需同步模板與規則 | **本機實跑 19/21**＋規格 |
| 3 | 過時 skill 指令清理 | [extract:49](C:/Users/holylight/.claude/skills/extract/SKILL.md:49)、[read-project:132](C:/Users/holylight/.claude/skills/read-project/SKILL.md:132)、[core:16](C:/Users/holylight/.claude/rules/core.md:16) | 修正手動入口仍指向舊流程的問題。萃取不得呼叫缺少必要參數的 worker；記憶不得再指示人工維護鏡像索引。已除役流程的引用應移除，不重新啟用。 | **補強＋精簡，優先** | 這是可定位的現有缺陷，不需要借外部框架。 | `/extract` 不再沿文件指令走到空結果；寫入流程不再互相矛盾。 | 0.5–1.5 人日；保留手動用途，避免誤刪仍用中的入口 | 原始碼與指令資料流核對 |
| 4 | superpowers：以失敗案例驗證 skill | [writing-skills](https://raw.githubusercontent.com/obra/superpowers/main/skills/writing-skills/SKILL.md)、[subagent-driven-development](https://raw.githubusercontent.com/obra/superpowers/main/skills/subagent-driven-development/SKILL.md) | 先在未套用 skill 時重現違規，再加規則確認改善，類似測試驅動開發（先證明測試能抓到錯誤）。執行任務與審查採新的代理上下文，降低自我合理化。現行流程也設有修訂次數上限。 | **補強；獨立驗收已有** | 可借壓力案例設計；不必再複製一套 verifier，現有 Codex 驗收已有第二意見。 | 用一個「要求跳過驗證」案例，確認規則到底能否抵抗捷徑。 | 約 0.5 人日試作；每題增加模型成本 | 上游設計引述；本機收益待測 |
| 5 | ECC：instinct 聚類與跨專案晉升 | [continuous-learning-v2](https://raw.githubusercontent.com/affaan-m/ECC/main/skills/continuous-learning-v2/SKILL.md)、[聚類實作](https://raw.githubusercontent.com/affaan-m/ECC/main/skills/continuous-learning-v2/scripts/instinct-cli.py) | 先把觀察變成小型 instinct，再以關鍵詞重疊聚類。相似度用 **交集數／較小集合大小**，門檻 0.5 且至少共享 2 詞；聚類核心持續取交集以抑制主題漂移。跨專案晉升另看出現專案數及平均信心。 | **已有；不導入** | 小知識、證據累積、晉升皆重疊；其英文 token 規則也不適合直接搬進 CJK 記憶。重複觀察不等於實際有用，本機效用歸因更切題。 | 未找到符合本系統條件的首場新增效益。 | 不採用；若改造需處理中文與錯誤自我強化 | 原始碼引述；未做本機品質比較 |
| 6 | Compound Engineering：反事實留存門檻 | [ce-compound](https://raw.githubusercontent.com/EveryInc/compound-engineering-plugin/main/skills/ce-compound/SKILL.md) | 只保留已解決、非顯而易見、無法從最終程式碼／測試／文件直接恢復的經驗。反問：「拿掉這條經驗，未來是否會重犯或付出昂貴重查成本？」沒有合格內容就不寫，且集中由主流程持久化。 | **補強，輕量採用** | 本機已有品質閘與去重；可补的是「能否從其他真相來源再生」這條編輯判準，不是新增記憶庫。 | 第一次 `/read-project` 就可避免把可再生目錄索引寫成 atom。 | 約 0.25 人日；別把有價值的決策理由誤當可再生資料 | 上游引述＋本機規則對照 |
| 7 | gstack：同題模型比較 | [benchmark-models](https://raw.githubusercontent.com/garrytan/gstack/main/benchmark-models/SKILL.md.tmpl)、[review](https://raw.githubusercontent.com/garrytan/gstack/main/review/SKILL.md.tmpl) | 同題比較不同模型的時間、用量與可選評分，保存結果供後續比較。審查另把證據綁定審查起點的程式狀態。這是可重跑基準，不是模型品質下降的自動證明。 | **補強評估；不整套導入** | 本機已有 token 記錄及獨立驗收；可把固定案例接到既有評估，避免另建儀表板。 | 第一輪取得基準值；尚不能宣稱偵測到退化。 | 0.5–1 人日；模型、題目與評審變動會混淆原因 | 上游引述；未實跑 |
| 8 | context-mode／RTK：輸出留外部、只送相關摘要 | [context-mode](https://raw.githubusercontent.com/mksglu/context-mode/main/README.md)、[RTK](https://github.com/rtk-ai/rtk) | context-mode 把完整結果留在工具環境，較大輸出建全文索引後用 BM25 返回相關片段。RTK 則針對命令輸出做確定性壓縮，例如收合成功項目、保留失敗。兩者改變的是進入模型的資料量，不只是發警告。 | **可新增機制，但暫緩** | 本機只有量測與提醒，確實不同；然而目前 65 次呼叫沒有達既定超量門檻，尚不足以優先導入。 | 只有真的遇到大量輸出才有直接效果；目前未證明。 | 1–2 人日小試；遺漏關鍵輸出、命令相容性與 hook 衝突 | 作者數據＋本機小樣本；壓縮率未複測 |
| 9 | cc-sessions／disler hooks：強制流程閘 | [cc-sessions](https://github.com/GWUDCAP/cc-sessions)、[disler hook 原始碼](https://raw.githubusercontent.com/disler/claude-code-hooks-mastery/main/.claude/hooks/pre_tool_use.py) | cc-sessions 在討論階段阻擋修改，核准任務後才開放，任務改動又回到討論。disler 範例以工具輸入比對及 hook exit code 攔截。它們把流程限制從提示詞搬到執行點。 | **已有；不再加硬閘** | 本機已有多個 PreToolUse／Stop 閘，PAN deny 更已因漏偵退役。沒有新證據支持再導入同類阻擋。 | 容易先增加等待與誤攔，而非新增可靠性。 | 不採用；誤攔及多閘互鎖風險 | 上游原始碼＋既有退役紀錄 |
| 10 | beads／CCPM：可執行的任務相依圖 | [beads](https://github.com/gastownhall/beads)、[CCPM](https://github.com/automazeio/ccpm) | beads 用持久化任務圖找出沒有未完成前置條件的工作，並支援原子領取。CCPM 把需求、任務與 GitHub issue 串接。它们管理的是工作狀態與協作分工，而非知識可信度。 | **本次無關；專案層再評估** | atom 的 Depends 不等於任務排程，但本次也未證明缺少任務排程是記憶系統瓶頸。 | 複雜專案可能受益；對原子召回沒有直接首場效果。 | 不納入本次；避免兩套任務真相 | 官方 repo 引述 |
| 11 | planning-with-files／GSD：外部進度與新上下文 | [planning-with-files](https://github.com/OthmanAdi/planning-with-files)、[GSD Core](https://github.com/open-gsd/gsd-core) | 前者以計畫、發現、進度三檔持久化，並定期提醒刷新。後者把研究、計畫與執行交給新上下文代理，以結構化產物接續。共同重點是把任務狀態移出聊天歷史。 | **已有；不整套導入** | 本機已有 handoff、continue 與交接機制。每兩次操作寫檔、固定週期重新注入，不是已證明優於現況的增量。 | 未查到能超越現有交接的首場證據。 | 不採用；多一套狀態檔與生命週期 | 上游引述；未比較 |
| 12 | Ralph loop：Stop 重送原提示 | [官方 stop-hook](https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/plugins/ralph-loop/hooks/stop-hook.sh) | Stop 時檢查迭代數與完成字串；未完成就阻擋結束並重送原提示。完成字串是模型輸出，不是測試通過證據。這個實作也不能一概稱為「每輪全新上下文」。 | **已有較強驗收；不採用** | 本機反退避、測試失敗閘與 Codex 驗收更接近可驗證完成。再疊迴圈容易把卡住變成持續耗用。 | 未找到新增效益。 | 不採用；重複失敗、停止条件失效 | 原始碼引述 |
| 13 | Context7 | [Context7](https://github.com/upstash/context7) | 先解析函式庫識別碼，再查版本相關文件。已知識別碼可省略解析。它提供外部文件檢索，不負責長期記憶演化。 | **互補，但本次非新增記憶機制** | 適合有版本 API 問題的專案；不應把整批可再查的文件灌成 atom。 | 首次遇到版本問題可能有效；取決於任務。 | 專案按需使用；外部服務與版本匹配風險 | 官方 repo 引述 |
| 14 | HumanLayer 舊開源套件 | [HumanLayer repo](https://github.com/humanlayer/humanlayer) | 目前 README 已明示舊程式碼大多 deprecated，repo 主要作公開 issue 用途。舊文章中的研究、計畫、實作分階段理念，不能證明舊套件仍適合安裝。此處需分開看理念與維護狀態。 | **不建議採用舊套件** | 不把仍流傳的推薦文章當成當前維護承諾。 | 避免第一場就背上已棄用整合。 | 不採用 | **維護者明示** |

**最值得做的 5 件，依優先順序**

**1. 修正 `/extract` 的失效路徑，移除對已除役逐輪萃取的依賴。**

這是本次最明確的功能問題：

- [`extract/SKILL.md:54`](C:/Users/holylight/.claude/skills/extract/SKILL.md:54) 傳入的 JSON 只有 `mode`、`max_chars`、`max_items`。
- [`extract-worker.py:320`](C:/Users/holylight/.claude/hooks/extract-worker.py:320) 卻需要 `session_id`、`cwd`。
- [`wg_core.py:422`](C:/Users/holylight/.claude/hooks/wg_core.py:422) 在缺少任一值時回傳 `None`，worker 隨即返回空結果。
- 此外，該模式實際從其他位置取得限制值；skill 傳的頂層 `8000`／`5` 也不是那段程式使用的設定。[worker:338](C:/Users/holylight/.claude/hooks/extract-worker.py:338)

**建議範圍：**保留使用者主動整理本輪知識的能力，移除這條過時 worker 呼叫；以當前對話中的可驗證證據及既有 `atom_write` 完成手動流程。不要為了救這段文件而復活 per-turn 萃取。

**驗收：**有明確知識、沒有新知識、無 transcript 三種情境；沒有新知識可以正常結束，不把空結果誤稱成功萃取。另移除「新建時可直接調成 [觀]／[固]」的舊描述，與 MCP 實際限制一致。[skill:97](C:/Users/holylight/.claude/skills/extract/SKILL.md:97)、[MCP 限制](C:/Users/holylight/.claude/tools/workflow-guardian-mcp/lib/atom-tools.js:114)

**2. 統一 active skill 的記憶寫入契約，停止保存可再生索引與未確認推論。**

目前至少三處仍有明顯偏移：

| 檔案 | 已確認的問題 | 建議處置 |
|---|---|---|
| [read-project:78](C:/Users/holylight/.claude/skills/read-project/SKILL.md:78)、[132](C:/Users/holylight/.claude/skills/read-project/SKILL.md:132) | 建 doc-index atom，並要求手動補 MEMORY.md | 專案導覽保留在可再生文件／索引；只有非顯而易見的決策或踩坑才進 atom，統一走 MCP |
| [consciousness-stream:119](C:/Users/holylight/.claude/skills/consciousness-stream/SKILL.md:119) | 依風險字詞及自檢結果引導寫 pitfalls／decisions，另更新 MEMORY.md | 保留使用者明確呼叫「識流」的分析用途；只有確認的結論可進寫入入口 |
| [upgrade:276](C:/Users/holylight/.claude/skills/upgrade/SKILL.md:276) | 遷移配方仍含直接複製 atom、改 metadata 與手動索引步驟 | 先判定哪些歷史版本仍需支援；舊配方不得作現行預設操作 |

本次未找到寫入品質閘明確表達「是否能從程式碼／測試／既有文件重新取得」的同等判準。可以借 Compound 的反事實問題補進既有規則，**不另做 LLM 分類器、分數或資料庫**。[現有品質閘](C:/Users/holylight/.claude/tools/memory-write-gate.py:137)

**驗收：**用「目錄清單」「尚未確認的懷疑」「已重現且解決的非顯然故障」三類案例，確認只有最後一類需要考慮寫入。

**3. 修正 skill-creator 的自訂規格，不要讓錯誤模板繼續繁殖。**

目前 `userInvocable` 出現在本機 skill 及模板，而 Claude Code 文件使用的是 `user-invocable`。因為預設本來就是可由使用者呼叫，這個拼字問題**不代表現在斜線指令失效**，但表示模板沒有對齊平台契約。[本機 frontmatter](C:/Users/holylight/.claude/skills/skill-creator/SKILL.md:4)、[官方欄位](https://code.claude.com/docs/en/skills)

建議修改範圍：

- `audit-skill.py`：官方錯誤與本機建議分開；`triggers`、`pattern` 不再一律判必填。
- `skill-creator/SKILL.md`、`references/principles.md` 與模板：修正欄位、路由說明及 500 行「紅線」說法。
- `refile/SKILL.md`：同步清理自訂欄位；若自訂資料仍有消費者，明確記錄用途，不把它當平台路由條件。
- frontmatter 解析：現有單行正規表示式不能完整理解合法 YAML，多行 description 不應被誤判。[解析位置](C:/Users/holylight/.claude/skills/skill-creator/scripts/audit-skill.py:38)

**驗收：**重新稽核 21 個 skill，並加入少量合法／非法 frontmatter 案例。目標不是全綠，而是每項失敗都對應真正的格式問題。

**4. 把現有 trigger fixtures 升級為真正的成效測試，不再以「有評估檔」代替驗證。**

目前成本工具以第一次 Skill 呼叫切分前後，後續整段 session 都算入；它能描述用量，卻不能把差異歸因於該 skill。[skill-cost-measure.py:74](C:/Users/holylight/.claude/skills/skill-creator/scripts/skill-cost-measure.py:74)

建議先選三個高價值對象：`extract`、`read-project`、`skill-creator`。每個先準備：

- 明確應觸發的案例。
- 用字相近但不應觸發的案例。
- 有結果可驗證的工作案例，例如是否走正確寫入入口、是否新增不該存在的 atom。

觸發準確度與任務成效分開計分。**「呼叫了 Skill」本身不能算成相對於無 skill 的品質提升。**

官方 plugin eval 已提供隔離執行、重複試驗與無 plugin 基準，但需要相應版本及可用功能；一般 skill 也可採官方 skill-creator 流程。兩者評估檔案格式不同，不要直接混用，更不必為了測試就把整套記憶系統重新包成 plugin。[官方 plugin eval](https://code.claude.com/docs/en/plugin-evals)

**5. 精簡固定儀式：先處理九次代理呼叫與無條件訪談，再考慮合併 skill。**

`fix-escalation` 標題稱六 Agent 會議，但完整流程實際列了 **2＋3＋3＋1＝9 次代理呼叫**，並把前階段報告帶入下一階段。這是文件靜態計數，不是實測 token 成本。[phase 1](C:/Users/holylight/.claude/skills/fix-escalation/SKILL.md:37)、[phase 2](C:/Users/holylight/.claude/skills/fix-escalation/SKILL.md:83)、[phase 3](C:/Users/holylight/.claude/skills/fix-escalation/SKILL.md:134)、[收尾](C:/Users/holylight/.claude/skills/fix-escalation/SKILL.md:172)

建議先採「根因調查＋獨立驗證」，只有證據相互矛盾或仍無法重現時才擴大會議；不要預先保證每次都需要九次呼叫。

另外，`skill-creator` 強制四題逐一詢問，即使對話已提供答案也沒有省略規則。可改為先從現有資料填入，只詢問缺口。[訪談規則](C:/Users/holylight/.claude/skills/skill-creator/SKILL.md:30)

**驗收：**同一批修復案例比較原流程與精簡流程的修復正確率、重開率、時間及用量。若只能少花 token 卻增加錯修，就不採用。

以上五項宜分開修改與驗證；回滾各自檔案即可，不搬移現有 atoms、不批次重建索引、不更換 hook 架構。

**2026 年「skill 怎麼寫」：哪些有共識，哪些沒有**

| 議題 | 查到的結論 | 對本機的處置 |
|---|---|---|
| description 寫什麼 | 官方要求說明「做什麼、何時用」；superpowers 更偏向只寫觸發條件，避免模型只照摘要做事。**這點不是完全一致的社群共識。**[官方規格](https://agentskills.io/specification)、[superpowers](https://raw.githubusercontent.com/obra/superpowers/main/skills/writing-skills/SKILL.md) | 採「適用情境＋產出」短描述，流程留正文，再用近似反例測試 |
| 長度 | 官方建議精簡並採漸進揭露（需要時才讀詳細內容）；500 行是建議，不是合法性分界。[官方最佳實務](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | 不為了行數拆檔；只有很少需要的範例、腳本與歷史遷移內容才抽離 |
| `context: fork` | 是新代理的隔離上下文，**不會自動繼承目前完整對話**。[Claude Code skills](https://code.claude.com/docs/en/skills) | 可用於輸入已封裝完整的研究任務；不能直接套在 handoff、extract 這類依賴當前對話的 skill |
| skill 與 hook 分工 | skill 表達任務程序；確定性命令、檢查與執行點限制由腳本／hook 承擔。自然語言「必須」不等於執行保證。[官方最佳實務](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | 不把同一硬規則複製成第二套 skill 守門，也不把模型判斷硬塞成無條件 deny |
| 評估方法 | 先確認無 skill 的基準，再測加上 skill 是否改善；好看、完整或被呼叫不等於有效。[官方 skill-creator](https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md) | 優先修正現有 eval 流程，無須再造另一個成本量測系統 |

目前 21 個 skill 中有 **9 個設為 `disable-model-invocation: true`**。依官方行為，這些手動技能的 description 不會供模型自動選用；因此不能把「21 個技能」直接算成 21 份常駐路由負擔。[官方控制方式](https://code.claude.com/docs/en/skills)

**21 個 skill 的去留對照**

| Skill | 建議 | 本機依據 |
|---|---|---|
| `extract` | **修正**，移除失效與退役路徑 | [49](C:/Users/holylight/.claude/skills/extract/SKILL.md:49) |
| `read-project` | **修正**，保留專案閱讀，不自動把可再生導覽變成 atom | [78](C:/Users/holylight/.claude/skills/read-project/SKILL.md:78) |
| `consciousness-stream` | **保留明確呼叫、精簡寫入分支**；description 與分析用途重新對齊 | [3](C:/Users/holylight/.claude/skills/consciousness-stream/SKILL.md:3)、[119](C:/Users/holylight/.claude/skills/consciousness-stream/SKILL.md:119) |
| `skill-creator` | **優先修正**規格、訪談與評估流程 | [30](C:/Users/holylight/.claude/skills/skill-creator/SKILL.md:30) |
| `refile` | 保留分類用途；同步校正 frontmatter | [1](C:/Users/holylight/.claude/skills/refile/SKILL.md:1) |
| `fix-escalation` | **精簡固定代理流程**，改依未解決證據擴大 | [37](C:/Users/holylight/.claude/skills/fix-escalation/SKILL.md:37) |
| `upgrade` | **隔離歷史配方、更新現行入口**；不因 368 行就直接砍掉 | [276](C:/Users/holylight/.claude/skills/upgrade/SKILL.md:276) |
| `memory` | 保留；修正無參數時究竟直接 health 或先列選單的矛盾 | [24](C:/Users/holylight/.claude/skills/memory/SKILL.md:24)、[151](C:/Users/holylight/.claude/skills/memory/SKILL.md:151) |
| `browse-sprites` | 保留；把適用情境移入 description，內嵌 fallback 程式按需載入 | [3](C:/Users/holylight/.claude/skills/browse-sprites/SKILL.md:3)、[54](C:/Users/holylight/.claude/skills/browse-sprites/SKILL.md:54) |
| `karpathy-guidelines` | **候選縮減自動載入**，但先做有／無對照；內容與 coding-style 高度相近 | [13](C:/Users/holylight/.claude/skills/karpathy-guidelines/SKILL.md:13)、[既有規則](C:/Users/holylight/.claude/rules/coding-style.md:20) |
| `handoff`、`continue` | 保留寫出／讀回的不同入口，不為減少數量硬併 | [handoff](C:/Users/holylight/.claude/skills/handoff/SKILL.md:15)、[continue](C:/Users/holylight/.claude/skills/continue/SKILL.md:1) |
| `generate-episodic`、`journal` | 保留；人工復原與日誌聚合用途不同 | [generate-episodic](C:/Users/holylight/.claude/skills/generate-episodic/SKILL.md:9)、[journal](C:/Users/holylight/.claude/skills/journal/SKILL.md:27) |
| `conflict`、`heal-review` | 保留；衝突裁決與健檢修復不是同一入口 | [conflict](C:/Users/holylight/.claude/skills/conflict/SKILL.md:1)、[heal-review](C:/Users/holylight/.claude/skills/heal-review/SKILL.md:50) |
| `harvest`、`vector` | 未找到足以支持合併或刪除的證據 | [harvest](C:/Users/holylight/.claude/skills/harvest/SKILL.md:1)、[vector](C:/Users/holylight/.claude/skills/vector/SKILL.md:1) |
| `atom-debug`、`changelog-debug`、`codex-companion` | 保留短小手動入口；數量本身不是成本證據 | [atom-debug](C:/Users/holylight/.claude/skills/atom-debug/SKILL.md:1)、[changelog-debug](C:/Users/holylight/.claude/skills/changelog-debug/SKILL.md:1)、[codex-companion](C:/Users/holylight/.claude/skills/codex-companion/SKILL.md:1) |

**明確不建議做的**

1. **不要讓每次失敗自動改 `CLAUDE.md` 或自動生成新 skill。**  
   本機已有失敗萃取與使用者糾正訊號。再直接改長期指令，會把「一次失敗的假說」轉成所有未來任務都要承受的規則；未找到足以證明此路線優於現有證據閘的資料。ECC 的 observer 在原生 Windows 另有 hook 結束後程序生命週期限制，也不適合照搬。[ECC 平台限制](https://raw.githubusercontent.com/affaan-m/ECC/main/skills/continuous-learning-v2/SKILL.md)

2. **不要全面強制 plan-first、TDD 或多代理會議。**  
   這些流程適合特定任務，沒有「小修改也全部開啟比較好」的共識。Reddit 確有對 superpowers 耗時、用量的抱怨，也有人支持用於大型工作；這是分歧，不是公認失敗。[討論一](https://www.reddit.com/r/ClaudeAI/comments/1v49gxt/superpower_takes_too_long_and_consumes_too_much/)、[討論二](https://www.reddit.com/r/ClaudeAI/comments/1uatdmp/is_the_superpowers_skill_worth_it_on_a_pro_plan/)

3. **不要把壓縮率當成整個 session 的節費率。**  
   context-mode／RTK 的作者數字主要描述輸出縮減，不等於相同品質下的整體帳單下降。context-mode 也有多 session 路由干擾的 issue，整合風險對本系統特別相關；issue 是回報，尚非本機重現。[context-mode 回報](https://github.com/mksglu/context-mode/issues/1055)

4. **不要照抄教學型 hook 當完整可靠性基礎。**  
   disler 範例有每次讀取整份 JSON 陣列再重寫的紀錄方式；隨呼叫數成長，累積序列化工作量可達平方級，且該段沒有並行寫入保護。本機已有 append-only 紀錄，不值得倒退。[範例程式](https://raw.githubusercontent.com/disler/claude-code-hooks-mastery/main/.claude/hooks/pre_tool_use.py)、[本機 append-only](C:/Users/holylight/.claude/hooks/wg_friction.py:119)

5. **不要從熱門榜直接推導「應刪除／應新增」。**  
   HumanLayer 舊碼有維護者明示棄用；GSD 舊 repo 則是搬家，不能混為一談。其他套件沒有查到可稱「社群公認雞肋」的一致證據。[HumanLayer](https://github.com/humanlayer/humanlayer)、[GSD 搬遷說明](https://github.com/gsd-build/get-shit-done)

**未查到／不確定的**

- **未驗證本機 Claude Code 版本與官方新功能是否已開放。** 查詢時官方最新 release 指向 v2.1.278；這不代表本機已使用該版本。[官方 release](https://github.com/anthropics/claude-code/releases/tag/v2.1.278)
- **未執行真正的 skill 模型評估。** 19/21 是既有稽核程式的結果；九次代理是文件計數；`extract` 空結果是指令與程式資料流核對，沒有冒充完整端到端執行。
- **沒有本機證據證明模型已退化。** 要判斷，必須固定題目、工具環境、skill 版本及評分方式重跑；單次覺得變笨、token 增加或 LLM 評審分數下降都不足。
- **X 搜尋未取得足以支撐關鍵主張的原始貼文。** 搜到的轉述不作「官方建議每次犯錯就改 CLAUDE.md」的證據。
- **沒有 GitHub Trending 歷史排名或 stars 成長序列。** 本報告僅使用當次關注度快照及目錄線索。[awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)、[awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills)
- **工具輸出樣本不足以否定未來壓縮需求。** 三筆 session 中主要是 Bash，不能外推到大量瀏覽器、測試日誌或 MCP 回傳。
- episodic 停擺、broken refs 與重複 atom 的根因不在本次角度內，未將其推定為任何外部套件能修復的問題。

目前可交給主持者直接排入實作的是前述五項，優先前三項已有具體缺陷證據。**本次環境僅允許讀取，無法落地修改；因此交付止於已驗證發現與可執行範圍，並未宣稱修復完成。**
