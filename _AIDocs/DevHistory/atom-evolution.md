# Atom 演化日誌彙整

> 從各 atom 的「演化日誌」段落集中收錄。按 atom 分組。

## decisions.md

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-03-19 | 精修拆分 — 技術細節移至 decisions-architecture，歷史移至 _reference | 系統精修 |
| 2026-03-22 | V2.16 自我迭代自動化決策記錄 | V2.16 文件同步 |
| 2026-03-22 | V2.17 覆轍偵測 — 寄生式跨 session 重複失敗模式偵測 | V2.17 實作 |
| 2026-03-23 | V2.17 合併升級至公司電腦 | 跨機合併 |

## decisions-architecture.md

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-03-19 | 從 decisions.md 拆出技術細節 | 系統精修 |
| 2026-03-19 | 新增 Token Diet V2.14 段落（7 條 [固]） | V2.14 驗證 |
| 2026-03-22 | 新增自我迭代自動化（V2.16）段落（7 條 [固]） | V2.16 文件同步 |
| 2026-03-22 | 新增覆轍偵測（V2.17）段落（4 條 [觀]） | 覆轍偵測實作 |
| 2026-03-23 | V2.17 合併升級至公司電腦 | 跨機合併 |
| 2026-03-24 | 新增 Section-Level 注入（V2.18）段落（6 條 [固]） | Phase 2 實作 |

## toolchain.md

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-03-10 | 初始建立：從 hardware.md + decisions.md 整理已知工具鏈知識，4 大分類 | manual |
| 2026-03-10 | [觀]→[固] 定期檢閱晉升，Confirmations=4 | periodic-review |
| 2026-03-13 | Dual-Backend A/B 萃取品質實測 + generate() think 參數 + extract-worker think=true | ab-extract-test |
| 2026-03-19 | 拆出 Ollama 區段至 toolchain-ollama.md，移除 path/路徑 trigger | atom-debug 精準化 |

## toolchain-ollama.md

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-03-19 | 從 toolchain.md 拆出 Ollama 區段 | atom-debug 精準化 |
| 2026-03-13 | 原始 A/B 實測數據 | ab-extract-test |

## workflow-rules.md

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-03-06 | 建立為 [固]（使用者明確要求） | session:SVN 工作流規則建立 |
| 2026-03-13 | 合併來源 V2.10 的大型計畫/GIT/同步判斷段落 + 擴展 Trigger | session:選擇性 cherry-pick |
| 2026-03-17 | 合併同事版 V2.11：新增 ICLD 製程 + 製程選擇 + AI 主動建議規則 | session:同事版合併 |
| 2026-03-18 | 拆分 SVN 規則至 workflow-svn.md，移除 SVN triggers | atom-debug 精準化 |
| 2026-03-19 | 拆分 ICLD 至 workflow-icld.md，移除 ICLD/Sprint/功能拆解 triggers | atom-debug 精準化 |

## workflow-icld.md

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-03-17 | 原始建立（含在 workflow-rules.md） | session:同事版合併 |
| 2026-03-19 | 從 workflow-rules.md 拆分為獨立 atom | atom-debug 精準化 |

## workflow-svn.md

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-03-06 | 原始規則（含在 workflow-rules.md 中） | session:SVN 工作流規則建立 |
| 2026-03-18 | 從 workflow-rules.md 拆分為獨立 atom | atom-debug 精準化 |

## feedback_fix_escalation.md

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-03-17 | 初始建立：6 Agent 會議制 + Guardian hook 自動偵測 + /fix-escalation skill | 使用者明確要求 |
| 2026-03-24 | 格式轉換：claude-native → 原子記憶標準格式 | memory-health 診斷 |

## feedback_no_test_to_svn.md

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-03-24 | 初始建立（claude-native 格式） | 使用者明確糾正 r10854 誤上傳 |
| 2026-03-25 | 格式修正：claude-native → 原子記憶標準格式 | memory-health 診斷 |

## feedback_global_install.md

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-03-25 | 初始建立：從 excel MCP 安裝踩坑經驗萃取 | 使用者明確要求 |
