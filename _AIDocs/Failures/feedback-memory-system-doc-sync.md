# feedback-memory-system-doc-sync

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 原子記憶系統, 記憶系統修正, 記憶系統修改, 記憶系統開發, 改 hook, 改 wg_, 改 server.js, memory system, 文件同步, doc sync
- Created-at: 2026-06-01
- Related: workflow-rules, feedback-workflow-discipline, atom-table-support, memory-index-caption-regen, atom-usefulness-loop, atom-元資料編輯與晉升閘真相, windows-cc-hook-閃-console-pythonw-修-layer-1勿只補巢狀-creationflags, realm-遷移-llm-domain-跨文字系統亂碼-snap-防線穿透, 對談結束自動記憶與錯誤加權深記, skill-計數單一來源-skill-index

## 知識

- [臨] **針對原子記憶系統（~/.claude 的 hooks/wg_*、handlers/、lib/atom_*、tools/.../server.js、skills/、workflow/config.json 等）的任何修正/重構/新增，完成後必須逐項檢視並同步更新所有相關重要文件**（沒改動的不動、不耗 token）。下表為標準檢視清單：

| 文件 | 何時更新 |
|---|---|
| `_AIDocs/_CHANGELOG.md` | **每次必更**（一條） |
| `TECH.md` / `_AIDocs/SPEC_ATOM_V5.md` | 動到架構 / 流程 / 規則 |
| `README.md` / `Install-forAI.md` | 動到對外行為 / 安裝 / 檔案清單 |
| `_AIDocs/DocIndex-System.md` / `Architecture.md` | 動到檔案結構 / 子系統 |
| `memory/MEMORY.md` / `_ATOM_INDEX.md` | 新增/改名 atom（多走 atom_write 自動同步） |
| `memory/decisions.md` / `toolchain.md` 等 atom | 動到該 atom 描述的規則 / 門檻（走 funnel） |
| `CLAUDE.md` / `IDENTITY.md` / `USER.md` | 僅動到啟動契約 / 身份 / 偏好時 |

- [臨] 更新方式 = **對 SoT 用 cross-ref、不複製衍生事實/規則本體**（呼應 [[feedback-workflow-discipline]] 的 TECH.md same_file_3x 覆轍根因：計數/規則真源在 code/SPEC/`_atom_index.json`，給人文件只指向、不複製）。atom `.md` 一律走 funnel（`atom_write` / `atom_io.write_raw`，禁直接 Edit）；`README`/`TECH`/`_AIDocs` 等一般 doc 直接編輯。表格/程式當獨立 knowledge 元素傳入見 [[atom-table-support]]。
- [臨] 此清單治的是「系統自我認知文件」——CC + 原子記憶的**架構/邏輯/流程/工具/說明**（`Architecture.md` / `SPEC_ATOM_V5` / `TECH.md` / `DocIndex-System` / `Project_File_Tree` + `decisions-architecture` 印象 atom），讓 CC 能隨時查詢全系統架構流程、有更深需求時調整並再同步——**非僅 `_CHANGELOG` 變更紀錄**。同步＝cross-ref SoT 不複製本體；印象→索引→知識分層。
- [臨] 覆轍實例（Realm S1–S3，2026-06）：realm 範疇分區 landed 後，`TECH.md` 連 §2.1 Failures 多根都一直漏更、「~17 atoms」過時，直到 S3 收尾 user 追問「是否都同步」才 doc-audit 補齊。**最易漏＝`TECH.md` / `Project_File_Tree` 這類「全貌型」檔**（不像 `_CHANGELOG` 有 Stop 提醒）。教訓：記憶系統變更收尾、逐項過清單前先點名這兩支。
- [臨]「自動」現況：靠本 atom + Stop hook「Sync: _AIDocs→_CHANGELOG」提醒 + `wg_docdrift`（src Edit→偻測對應 _AIDocs 需更新）；但 docdrift 未涵蓋 TECH/SPEC/Project_File_Tree 全清單 → 仍靠人/AI 紀律、會漏。要真程式化強制 → 擴 `wg_docdrift` 對照表納本清單（待拍板）。
- [臨] **覆轍（2026-06-04）：phase 收尾 doc-sync 只照「當階段 plan 列的清單」做 → 漏更 TECH.md / Install-forAI.md**。實例：realm V6 Phase G 只更 SPEC/Architecture/DocIndex（plan 列的），漏 TECH.md（skill 20→22、atom 17→32、`_atoms` domain 階層、verify 14→26）與 Install-forAI.md（skill 數、MCP 3→4 tool），經 user 點出才補。**鐵則：doc-sync 一律以本 atom 完整表為準、非 plan 子集**；TECH.md（架構/流程/計數）與 Install-forAI.md（對外安裝/skill·tool 計數/檔案清單）最易漏——凡動 skill 數 / atom 數 / MCP tool 數 / 檔案結構，必檢這兩檔。

## 行動

- 記憶系統修正完成 → 逐項過上表清單，需更新者更新（cross-ref SoT、不複製本體）；沒改動者不動
- atom .md 走 atom_write/write_raw funnel；README/TECH/_AIDocs 一般 doc 直接 Edit；`_AIDocs/_CHANGELOG.md` 每次必更
- 文件更新完一併上 GIT（與碼同 commit 或紧鄰 commit）
