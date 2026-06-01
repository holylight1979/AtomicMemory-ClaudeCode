# feedback-memory-system-doc-sync

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 原子記憶系統, 記憶系統修正, 記憶系統修改, 記憶系統開發, 改 hook, 改 wg_, 改 server.js, memory system, 文件同步, doc sync
- Created-at: 2026-06-01
- Related: workflow-rules, feedback-workflow-discipline, atom-table-support

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

## 行動

- 記憶系統修正完成 → 逐項過上表清單，需更新者更新（cross-ref SoT、不複製本體）；沒改動者不動
- atom .md 走 atom_write/write_raw funnel；README/TECH/_AIDocs 一般 doc 直接 Edit；`_AIDocs/_CHANGELOG.md` 每次必更
- 文件更新完一併上 GIT（與碼同 commit 或紧鄰 commit）
