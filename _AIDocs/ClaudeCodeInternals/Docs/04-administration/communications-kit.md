<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/communications-kit | lastmod: 2026-10-03 | section: Administration / Adoption -->
> 來源：https://code.claude.com/docs/zh-TW/communications-kit（官方 zh-TW，lastmod 2026-10-03）｜分類：Administration › Adoption｜EN 摘要：Launch announcements, drip-campaign messages, and FAQ responses for rolling Claude Code out to your engineering organization.

# 通訊工具包

> 推出公告、滴灌式行銷訊息和常見問題解答，用於在您的工程組織中推出 Claude Code。

本頁面適用於在團隊中推出 Claude Code 的管理員和工程主管。它提供了可直接使用的推出公告、提示和技巧滴灌式行銷活動，以及針對您最常被問到的問題的單行常見問題解答。

> [!NOTE]
>
> 將此處的所有內容視為草稿副本，而非最終副本。用您組織的語氣重寫每條訊息，用您自己程式碼庫中的實際錯誤和模組替換示例任務，並在發送前替換 `[括號中的佔位符]`。推動採用的公告是那些看起來像您公司某人寫的公告。

## 推出通訊

一份公告分為兩種格式，加上兩個可選變體。選擇最適合您推出的格式，然後從那裡開始重寫。

### 發送前

在公告發出前，請完成此檢查清單。每一項都會關閉一個差距，否則會變成推出當天的支援討論串。

| 項目 | 為什麼重要 |
| - | - |
| `#claude-code` 頻道已建立並在訊息中連結 | 讓問題有一個集中的地方 |
| 在您環境中至少一台機器上測試過安裝命令 | 在所有人同時遇到代理或防火牆問題之前捕捉它們 |
| 安全和資料處理連結已準備好（[資料使用](https://code.claude.com/docs/zh-TW/data-usage.md) 或您的內部等效項） | "我的程式碼去哪裡了？" 將是第一個回覆 |
| 已選擇一個具體的首個任務，您程式碼庫中的實際錯誤或檔案 | 通用示例不會轉換；"修復 `auth_test.go` 中的不穩定測試" 會 |
| 為前 48 小時指定的頻道擁有者 | 未回答的推出當天問題會扼殺動力 |
| 已安排一位 C 級主管贊助者發送或共同簽署公告 | 由高管發送的推出在第一週採用率上始終比由管理員或工具團隊發送的要高 |

### 公告

將此用作您的標準組織範圍推出訊息。它涵蓋了 Claude Code 是什麼，提供了兩分鐘的安裝路徑，為讀者提供了一個具體的任務來嘗試，並在任何人必須提出問題之前回答了 "我的程式碼去哪裡了？"。

> [tab] 電子郵件
>
> ```text theme={null}
> 主旨：Claude Code 現已為 [工程部門 / 您的團隊] 推出
>
> 團隊，
>
> 從今天開始，您可以存取 Claude Code，這是一個在您的終端機中執行、讀取您的實際程式碼庫並端到端完成實際任務的 AI 編碼 agent：除錯、重構、測試、PR。它不是自動完成，也不是聊天視窗。它會編輯檔案並執行您的命令。
>
> 在兩分鐘內開始執行：
>
>     curl -fsSL https://claude.ai/install.sh | bash
>     cd <your-repo>
>     claude
>
> 然後執行一次 /init。Claude 讀取您的專案並寫入一個 CLAUDE.md，其中包含您的建置命令和約定，因此您不再需要重新解釋基礎知識。
>
> 然後在您已經在的儲存庫上嘗試以下其中之一：
>
>   - "檔案 [file] 中的測試不穩定。找出原因並修復它"
>   - "向我介紹 [module] 如何處理 [X]"
>   - "查看我的工作差異並告訴我在我推送前什麼是風險的"
>
> 您的程式碼去哪裡了：Claude Code 在您的終端機中執行，並直接與 Anthropic 的 API 通訊。在我們的 Team 或 Enterprise 方案下，Anthropic 不會使用您的程式碼或提示詞來訓練其模型。
> 詳情：https://code.claude.com/docs/en/data-usage
>       https://code.claude.com/docs/en/security
>
> 有問題去哪裡：#claude-code。[擁有者名稱] 本週正在監視它。
>
> - [名稱]
>
> P.S. 更喜歡您的編輯器？有一個 VS Code 擴充功能和一個 JetBrains 外掛。相同的 agent，不需要終端機。
> ```

> [tab] Slack 或 Teams
>
> ```markdown theme={null}
> 🚀 *Claude Code 現已為 [團隊] 推出*
>
> AI 編碼 agent，在您的終端機中執行，讀取您的儲存庫，完成實際工作：
> 錯誤、重構、測試、PR。
>
> `curl -fsSL https://claude.ai/install.sh | bash` → `cd your-repo` → `claude`
>
> *首先要嘗試的* → 執行 `/init`，然後："檔案 [file] 中的測試不穩定，
> 找出原因並修復它。"
>
> 🔒 在您的終端機中執行，直接與 Anthropic 的 API 通訊。在我們的 Team 或
> Enterprise 方案下，您的程式碼和提示詞不會用於訓練模型。
> 資料使用 → https://code.claude.com/docs/en/data-usage
>
> 📚 快速入門 · VS Code · 免費 1 小時課程
>    https://code.claude.com/docs/en/quickstart
>    https://code.claude.com/docs/en/vs-code
>    https://academy.claude.com/courses/claude-code-in-action
>
> 問題 → 此討論串。[擁有者] 正在負責。
> ```

### 執行贊助商變體

從您的贊助執行官（如 CTO、CIO 或 SVP 工程）發送此訊息，使用他們的名字和帳戶。由高管名義發出的推出在開啟率和第一週啟用速度上始終比來自管理員或工具團隊的相同訊息要高。它表示公司優先事項，而不是可選實驗。

此版本故意精簡為一個要求：安裝它並在一個實際任務上執行它。高管的工作是讓要求落實；標準公告和 `#claude-code` 處理方式。

> [tab] 電子郵件
>
> ```text theme={null}
> 主旨：我希望每位工程師本週嘗試的一件事
>
> 團隊，
>
> 我們已為所有工程部門開啟了 Claude Code。它是一個直接在您的終端中、在您的實際程式碼庫上工作的 AI 代理，已經使用它的團隊的早期結果足夠強勁，我希望本週每個人都使用它。
>
> 我要求十分鐘：
>
>     curl -fsSL https://claude.ai/install.sh | bash
>     cd <your-repo>
>     claude
>
> 然後給它一個實際任務：您一直在推遲的錯誤，或 "向我介紹 [module] 如何工作"。
>
> 這就是全部要求。[擁有者名稱] 和團隊在 #claude-code 中處理您遇到的任何問題。
>
> - [執行官名稱]
>   [職位]
> ```

> [tab] Slack 或 Teams
>
> ```markdown theme={null}
> 📣 *來自 [執行官名稱]：本週要嘗試的一件事*
>
> 我們已為所有工程部門開啟了 *Claude Code*。早期結果足夠強勁，我要求每個人本週在實際工作上給它十分鐘。
>
> `curl -fsSL https://claude.ai/install.sh | bash` → `cd your-repo` →
> `claude` → 給它一個實際任務。
>
> 就這樣。問題 → #claude-code。
> ```

### 試點小組變體

用於分階段推出。僅發送給試點隊列。

```text theme={null}
主旨：您在 Claude Code 試點中

[名稱 / 團隊]，

您是 [公司] Claude Code 的第一波。我們選擇了這個小組，因為您會在實際問題上使用它，並告訴我們關於它的真實情況。

要求：本週至少在一個實際任務上使用它，然後在 #claude-code-pilot 中留下一條筆記，涵蓋什麼有效、什麼令人煩惱以及什麼讓您驚訝。該反饋決定了我們如何向其他人推出。

[繼續標準公告中的 "在兩分鐘內開始執行"]

試點的一個額外事項：在您的第一個多檔案變更時，按 Shift+Tab
直到您看到 "plan"。Claude 會說明它打算做什麼，而不會編輯您的原始碼。這是校準您應該信任多少的最快方式。
```

### 冠軍招募直訊

推出後，直訊在 `#claude-code` 中最活躍的兩三個人。

```text theme={null}
嘿 [名稱]，您的 #claude-code 貼文對採用的推動比我的公告做得更多。幾個人告訴我您的 [討論串 / 螢幕截圖]
是他們實際嘗試它的原因。

想讓這成為半官方的嗎？低投入：主要是繼續發佈您正在發佈的內容，加上新功能的首先嘗試和與 Anthropic 團隊的直接聯繫。如果您有興趣，我可以分享一個簡短的遊戲手冊。
```

## 提示和技巧行銷活動

設計用於在推出後推動功能啟用的現成 Slack 或 Teams 訊息。每個都遵循相同的模式：一個鉤子、收益、一個「現在嘗試」提示和一個文件連結。在 `#claude-code` 中每週滴灌一兩個，或選擇與您團隊差距相符的少數幾個。它們獨立存在，沒有必需的順序。

### 開始使用

**選擇正確的模型**

```markdown theme={null}
🎯 *提示：將模型與時刻相匹配*

使用 Opus 修復打字錯誤會浪費計算。使用 Haiku 進行 12 檔案重構
是要求重做。

Claude Code 在與 Claude 應用相同的模型上執行，您可以在會話中間切換。*Sonnet* 是日常功能工作、錯誤、測試和審查的預設主力。在大型重構、複雜除錯或任何高風險的事情上使用 *Opus*。對於快速問題、格式化和速度獲勝的機械編輯，降低到 *Haiku*。

*Fable* 是您最困難、最長時間執行任務的最有能力的模型；它不是
預設值，所以使用 `/model fable` 選擇它，並注意網路安全和生物學內容會自動回退到 Opus。Opus 5.5、Sonnet 5.5 和 Opus 5 執行自己的檢查：標記的內容會切換到同一系列中的較早模型，除了 Opus 5 或 Sonnet 5.5 上標記的生物學內容會被拒絕。

*現在嘗試：* 輸入 `/model` 並選擇 Sonnet（如果您還沒有的話）。它是大多數任務的正確預設。

📖 Model configuration → https://code.claude.com/docs/zh-TW/model-config
```

| 模型 | 最適合 |
| - | - |
| Fable | 最困難、最長時間執行的任務。僅選擇加入：使用 `/model fable` 選擇它。網路安全或生物學內容觸發[自動模型回退到 Opus](https://code.claude.com/docs/zh-TW/model-config.md#automatic-model-fallback) |
| Opus | 大規模重構、複雜除錯、架構決策、高風險變更。在 Opus 5.5 和 Opus 5 上，網路安全或生物學內容觸發[自動模型回退或拒絕](https://code.claude.com/docs/zh-TW/model-config.md#automatic-model-fallback) |
| Sonnet | 日常功能工作、錯誤修復、測試、文件、程式碼審查。建議預設。在 Sonnet 5.5 上，網路安全或生物學內容觸發[自動模型回退或拒絕](https://code.claude.com/docs/zh-TW/model-config.md#automatic-model-fallback) |
| Haiku | 快速問題、格式化、機械編輯、快速迭代 |

**首先嘗試的快速勝利**

```markdown theme={null}
🚀 *提示：在您的前 10 分鐘內嘗試的三件事*

已安裝 Claude Code 但不確定實際要求什麼？從一直困擾您整週的東西開始。

  - 修復令人煩惱的東西：「檔案 [file] 中的測試不穩定，找出原因」
  - 在您沒有寫的程式碼中定位：「向我介紹 [module] 如何工作」
  - 在您推送前進行理智檢查：「查看我的工作差異並告訴我什麼看起來風險」

這些都不需要設定。只需 `cd` 進入您的儲存庫並執行 `claude`。

*現在嘗試：* 選擇您一直在迴避的錯誤並貼上錯誤訊息。

📖 Quickstart → https://code.claude.com/docs/zh-TW/quickstart
```

### 專案記憶

**`/init` 和 CLAUDE.md**

```markdown theme={null}
📁 *提示：停止每個會話重新解釋您的儲存庫*

第五次告訴 Claude「我們使用 pnpm，而不是 npm」？有一個一次性修復。

每個儲存庫執行一次 `/init`。Claude 讀取您的專案結構並寫入一個 CLAUDE.md 檔案，其中包含您的建置命令、架構和約定。該儲存庫中的每個未來會話都會自動從此檔案開始。將其保持在兩個螢幕以下。它是一個速查表，而不是文件。

*現在嘗試：* 開啟您的主儲存庫，執行 `claude`，輸入 `/init`。三十秒，在之後的每個會話中都有回報。

📖 CLAUDE.md and project memory → https://code.claude.com/docs/zh-TW/memory
```

**@-參考**

```markdown theme={null}
📎 *提示：停止將檔案內容貼到聊天中*

複製一個元件的 200 行到您的提示中，以便 Claude 可以「看到」它？您不必這樣做。

輸入 `@` 然後是檔案路徑。Claude 直接將檔案拉入上下文。也適用於整個目錄。

> @src/components/Button.tsx 中的樣式看起來不對，根據 @docs/design-system.md 檢查

*現在嘗試：* 輸入 `@` 然後 Tab。自動完成顯示您可以到達的每個檔案。

📖 Referencing files → https://code.claude.com/docs/zh-TW/common-workflows
```

### 控制和安全

**Permission modes**

```markdown theme={null}
🛡️ *提示：一個按鍵在「查看但不觸及」和「就做吧」之間*

有時您希望 Claude 在每次編輯前詢問。有時您只是希望它直接交付。您不應該永遠只選擇一個。

*Shift+Tab* 循環切換 Claude 無需詢問即可執行的範圍：*Manual*（`default` 設定值）在檔案編輯和大多數 shell 命令前詢問，*acceptEdits* 讓檔案編輯和常見檔案系統命令直接通過，同時仍在其他 shell 命令前檢查，而 *plan* 會研究並提議變更，而不編輯您的原始碼。plan mode 是信任建立者，因此對於觸及多個檔案的任何事情，從那裡開始。

*現在嘗試：* 在您的下一個重構上，按 Shift+Tab 直到您看到「plan」，然後描述變更。您將獲得一份完整的提案供審閱。

📖 Permission modes → https://code.claude.com/docs/zh-TW/permissions
```

**Checkpointing 和 `/rewind`**

```markdown theme={null}
⏪ *提示：整個對話有一個撤銷按鈕*

Claude 三個回合前走錯了路，現在您正在解開它？您不必向前修復。

`/rewind` 回滾到對話中的較早點，包括 Claude 沿途所做的檔案變更。Checkpointing 是自動的；您不需要設定任何東西。

*現在嘗試：* 按 *Esc* 兩次以開啟倒帶菜單，或輸入 `/rewind`。選擇事情變得不對勁之前的點。

📖 Checkpointing → https://code.claude.com/docs/zh-TW/checkpointing
```

### 連接您的工具

**MCP connectors**

```markdown theme={null}
🔌 *提示：讓 Claude 讀取您的問題追蹤器，這樣您就不必貼票證*

將 Jira 票證複製貼到終端感覺像是向後退一步。確實如此。

一個設定檔（您的專案根目錄中的 `.mcp.json`）將 Claude 連接到 GitHub、Jira、Linear 或您使用的任何追蹤器。然後「什麼是分配給我的最高優先級問題？」和「繼續修復它」在同一對話中發生。

*現在嘗試：* 要求 Claude「在此儲存庫中為 [GitHub/Jira/Linear] 設定 MCP 連接器」。它將為您寫入設定。

📖 MCP connectors → https://code.claude.com/docs/zh-TW/mcp
```

### 自動化您的工作流程

**Skills**

```markdown theme={null}
⚡ *提示：將您一直重新輸入的提示變成命令*

本週三次輸入「從 git log 總結我今天所做的工作，為站立會議格式化」？那是一個等待發生的斜杠命令。

`.claude/skills/<name>/` 中的 SKILL.md 檔案變成可重用提示；輸入 `/name` 來執行它。在您輸入您之前輸入過的多步驟提示的第二次時製作一個。最簡單的路徑：要求 Claude 為您製作它。

*現在嘗試：* 輸入「為我製作一個 /standup skill，從 git log 總結我今天所做的工作」，然後明天早上執行 `/standup`。

📖 Skills → https://code.claude.com/docs/zh-TW/skills
```

**Hooks**

```markdown theme={null}
🔔 *提示：當您的重構完成時收到通知*

坐在您的辦公桌前看著 Claude 完成一個長任務？您有更好的事情要做那八分鐘。

Hooks 是在 Claude Code 事件上觸發的 shell 命令。一個發送桌面通知的 Stop hook 意味著您可以啟動一個長重構、走開，並在完成時立即收到通知。

*現在嘗試：* 要求 Claude「新增一個 Stop hook，當您完成時發送桌面通知」。它將寫入指令碼並連接它。

📖 Hooks guide → https://code.claude.com/docs/zh-TW/hooks-guide
```

### 日常開發

**Screenshots 和圖像**

```markdown theme={null}
📸 *提示：停止描述錯誤對話框。只需顯示它。*

輸出「有一個紅色框說一些關於空參考的東西，它指向第 47 行左右」？螢幕截圖它。

直接將螢幕截圖拖到終端中，Claude 看到它：錯誤對話框、UI 模型、白板照片、Figma 匯出。*Ctrl+V* 從剪貼板貼上，或在 Windows 和 WSL 上使用 *Alt+V*。

*現在嘗試：* 下次視覺上出現問題時，螢幕截圖它並直接貼到提示中。然後只需輸入「這裡出了什麼問題？」

📖 Working with images → https://code.claude.com/docs/zh-TW/common-workflows
```

**Git 工作流程**

```markdown theme={null}
🌿 *提示：交接整個 git 儀式*

修復花了 5 分鐘。提交訊息、分支和 PR 描述花了 15 分鐘。該比率是錯誤的。

Claude 處理完整的 git 流程：具有常規訊息的提交、分支、具有適當摘要的 PR。一個要求：「修復偏差一，使用常規提交訊息提交，並開啟 PR。」審查別人的工作？貼上 PR URL 並要求 Claude 向您介紹差異。

*現在嘗試：* 在您的下一個修復後，而不是切換到您的 git 客戶端，只需輸入「用好訊息提交此內容並開啟 PR」。

📖 Creating pull requests → https://code.claude.com/docs/zh-TW/common-workflows
```

### 分享和擴展

**Plugins**

```markdown theme={null}
📦 *提示：有人可能已經建立了該 skill*

即將花一小時建立 `/deploy` 命令？檢查它是否已經存在。

Skills 被捆綁並作為外掛共享。`/plugin` 瀏覽可用的內容並在一個步驟中安裝。五分鐘的瀏覽可以節省一小時的建立。

*現在嘗試：* 輸入 `/plugin` 並滾動瀏覽。您會找到至少一件您不知道自己想要的東西。

📖 Plugins → https://code.claude.com/docs/zh-TW/plugins
```

### 安全和管理

**Security architecture**

```markdown theme={null}
🔐 *提示：下次被問到時「這安全嗎？」的答案*

您團隊中的某個人會問「等等，我的程式碼去哪裡了？」
這是您可以貼上的簡短版本。

權限模式決定 Claude 無需事先詢問您即可採取哪些動作。CLI 在您的終端機中執行，直接與 Anthropic 的 API 通訊，並支援 shell 命令的可選作業系統級沙箱機制。在 Team 或 Enterprise 方案中，Anthropic 不使用您的程式碼或提示詞來訓練其模型。

*現在嘗試：* 保存這兩個連結，以備下次問題出現時使用。它們回答了大多數安全審查問題。

📖 https://code.claude.com/docs/zh-TW/security
📖 https://code.claude.com/docs/zh-TW/data-usage
```

**Best practices**

```markdown theme={null}
✅ *提示：將「嘗試過一次」與「每天使用」分開的 4 個習慣*

大多數從 Claude Code 反彈的人跳過了其中之一。大多數堅持的人在第一週完成了全部四個。

  - 對於觸及多個檔案的任何事情，在 Plan Mode 中開始
  - 早期執行 /init；上下文複合
  - 在提交前審查差異；Claude 可以自信地出錯
  - 驗證觸及關鍵路徑的變更；將其視為銳利的初級，而不是預言家

*現在嘗試：* 如果您只做了其中一兩個，選擇您缺少的那個並在您的下一個任務上執行它。在 #claude-code 中發佈發生了什麼變化。

📖 Best practices → https://code.claude.com/docs/zh-TW/best-practices
```

## 快速參考

### 常見問題解答回應

針對您最常被問到的問題的單行回覆。

| 問題 | 回應 |
| - | - |
| "它在 VS Code 中工作嗎？" | 是的。有一個 VS Code 擴充功能和一個 JetBrains 外掛，具有相同的功能，嵌入在您的編輯器中。[VS Code →](https://code.claude.com/docs/zh-TW/vs-code.md) |
| "我必須先配置什麼嗎？" | 不。安裝，然後在任何儲存庫中執行 `claude`。執行一次 `/init`，您就設定好了。[快速入門 →](https://code.claude.com/docs/zh-TW/quickstart.md) |
| "我的程式碼去哪裡了？" | CLI 在您的終端機中執行，並將上下文發送到 Anthropic 的 API 進行推理。在 Team 或 Enterprise 計畫上，您的程式碼和提示詞不用於訓練模型。[資料使用 →](https://code.claude.com/docs/zh-TW/data-usage.md) |
| "它能看到我的整個儲存庫嗎？" | 它讀取您給它存取權限的內容。您工作目錄內的檔案讀取不會提示。[權限 →](https://code.claude.com/docs/zh-TW/permissions.md) |
| "這與 Copilot 有什麼不同？" | Copilot 自動完成行。Claude Code 是一個讀取檔案、執行命令和進行多檔案編輯的代理。[概述 →](https://code.claude.com/docs/zh-TW/overview.md) |
| "我應該首先嘗試什麼？" | 您一直在推遲的錯誤，因為它很乏味。"檔案 \[file] 中的測試不穩定，找出原因。" [快速入門 →](https://code.claude.com/docs/zh-TW/quickstart.md) |

### 提示範本

與已安裝但不確定要求什麼的工程師分享這些入門提示。每一個都以它在實際會話中輸入的方式措辭；用您自己儲存庫中的檔案替換括號中的部分。

| 任務 | 提示 |
| - | - |
| 修復錯誤 | "檔案 \[file] 中的測試失敗，找出原因並修復它" |
| 理解程式碼 | "向我介紹 \[module] 如何工作，然後告訴我進入點在哪裡" |
| 安全重構 | "重構 \[module] 到 \[goal]，使用 plan 模式，以便我可以先審查" |
| 寫測試 | "為 \[file] 寫測試，涵蓋 \[scenario] 周圍的邊界情況" |
| 提交前審查 | "查看我的工作差異並告訴我什麼看起來風險" |
| 開啟 PR | "修復 \[issue]，寫一個常規提交，並用摘要開啟 PR" |
| 製作 skill | "為我製作一個 /ship skill，在提交前執行測試和 lint" |
| 除錯堆棧追蹤 | "這是堆棧追蹤，找到根本原因，不要只是掩蓋它" |

> [!TIP]
>
> Claude Code 頻繁發貨。在內部分發前，根據 [文件首頁](https://code.claude.com/docs/zh-TW/overview.md) 驗證版本特定詳情。
