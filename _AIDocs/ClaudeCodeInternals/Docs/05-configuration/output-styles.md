<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/output-styles | lastmod: 2026-10-27 | section: Configuration / Model and responses -->
> 來源：https://code.claude.com/docs/zh-TW/output-styles（官方 zh-TW，lastmod 2026-10-27）｜分類：Configuration › Model and responses｜EN 摘要：Change Claude Code's role, tone, and response format with a built-in output style such as Concise or Explanatory, or write a custom style.

# 輸出樣式

> 使用內建輸出樣式（例如簡潔或詳細說明）改變 Claude Code 的角色、語氣和回應格式，或撰寫自訂樣式。

輸出樣式是一組指令，為工作階段中的每個回應設定 Claude 的角色、語氣和回應格式。Claude Code 除了預設樣式外，還包括四種內建樣式，您也可以撰寫自己的樣式。

使用輸出樣式來改變 Claude 在整個工作階段中的回應和協作方式，這樣您就不需要在每個提示中重複請求。例如，內建樣式可以使回應更簡短、為每個變更新增說明，或讓 Claude 在不提出例行問題的情況下開始工作。自訂樣式也可以將 Claude 轉變為軟體工程師以外的角色，例如寫作助手或資料分析師。

* 若要使用內建樣式，請從[內建輸出樣式](#built-in-output-styles)中選擇一個，並[切換到它](#change-your-output-style)。
* 若要撰寫您自己的指令，請[建立自訂輸出樣式](#create-a-custom-output-style)。

> [!NOTE]
>
> 輸出樣式提供 Claude 要遵循的指令。它不保證某些事情總是發生或永遠不會發生。某些需求適合不同的功能：
>
> * 對於 Claude 應該了解的關於您專案的內容，請使用 [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md)。
> * 對於必須每次都發生的事情，例如每次編輯後的格式化或阻止命令，請使用[掛鉤](https://code.claude.com/docs/zh-TW/hooks-guide.md)。
> * 對於技能、子代理和其他選項，請參閱[在輸出樣式和其他功能之間選擇](#choose-between-an-output-style-and-other-features)。

## 內建輸出樣式

Claude Code 以[**預設**](#default)樣式開始，這是其完成軟體工程任務的標準指令。其他四種內建樣式各自保留這些指令並添加自己的指令。

此表格顯示每種樣式如何改變工作階段以及何時適用：

| 樣式 | 改變的內容 | 何時使用 |
| :- | :- | :- |
| [Proactive](#proactive) | Claude 立即開始工作，對例行決策做出合理的假設，而不是詢問 | 您希望 Claude 透過例行決策繼續工作，如果假設有誤，您可以改正方向 |
| [Concise](#concise) | 回應以結果開頭，省略前言、敘述和回顧 | 預設回應比您想要的更長 |
| [Explanatory](#explanatory) | Claude 添加簡短的 `Insight` 區塊，解釋其編寫程式碼背後的選擇 | 您正在熟悉程式碼庫或想要隨著變更一起了解推理過程 |
| [Learning](#learning) | Claude 解釋其選擇，並留下小段程式碼供您自己編寫 | 您想要實踐編碼練習，同時任務仍然完成 |

### 預設

預設表示未選擇任何輸出樣式。Claude Code 不添加樣式指令，Claude 從 Claude Code 的標準系統提示詞工作，該提示詞是為軟體工程任務編寫的。

`default` 出現在 `/output-style` 列表中與其他樣式一起，因此您[以相同方式選擇它](#change-your-output-style)。

### Proactive

在 Proactive 樣式中，Claude 在您發送任務後立即開始實施。它對例行決策做出合理的假設，而不是停下來詢問，除非您要求計畫，否則不會切換到 Plan Mode。您可以隨時重新導向它。

該樣式的指令也告訴 Claude 在刪除資料或變更共享或生產系統的操作前在對話中與您確認。該確認是 Claude 遵循的指令，與權限提示分開。

切換到 Proactive 樣式不會改變您的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)。您的權限模式仍然決定哪些工具呼叫在不詢問您的情況下執行，因此權限提示的出現方式與您切換前相同。

### Concise

在 Concise 樣式中，回應的第一句陳述發生了什麼或答案是什麼。Claude 省略了引言、逐步敘述和結尾回顧，並在一到三句話內回答簡單問題。它以與預設樣式相同的徹底程度進行工程工作。需要 Claude Code v2.1.237 或更新版本。

Claude 在以下情況下仍會完整編寫：

* **您要求的任何內容**：當您要求解釋或更多詳細資訊時，Claude 會完整回答。
* **您安全行動所需的任何內容**：錯誤報告、失敗的測試輸出、安全警告和破壞性操作的確認保留其完整內容。

### Explanatory

在 Explanatory 樣式中，Claude 以與預設樣式相同的方式執行任務，並添加其做出選擇原因的簡短解釋。每個解釋出現在對話中，在其相關程式碼之前或之後，在標記為 `Insight` 的區塊中。解釋不會作為註解寫入您的檔案中。

`Insight` 區塊包含關於您的程式碼庫或 Claude 編寫的程式碼的兩到三個要點，例如在添加 API 端點後的這個：

```text theme={null}
★ Insight ─────────────────────────────────────
- Every route in this repo goes through the withAuth wrapper, so the new endpoint gets session checks without its own middleware.
- Rate limits are set per route in limits.ts, which is why this change adds an entry there rather than a global default.
─────────────────────────────────────────────────
```

### Learning

在 Learning 樣式中，Claude 添加與 [Explanatory 樣式](#explanatory)相同的 `Insight` 區塊，並要求您編寫一些程式碼。Claude 自己處理例行實施。當它到達具有真實設計決策的部分時，例如錯誤處理、資料結構或具有多個有效方法的業務邏輯，它會為您留下幾行。

Claude 用檔案中的 `TODO(human)` 註解標記該位置，然後發送一個請求，說明已經構建的內容、要編寫的內容以及要權衡的內容：

```text theme={null}
● Learn by Doing

Context: The upload form is in place and calls validateFile() before accepting a file. Size and type checks work for images, but the switch statement has no handling for documents yet.

Your Task: In upload.js, implement the case "document" branch inside validateFile(). Look for TODO(human).

Guidance: Decide on a size limit for documents and whether the file extension has to match the MIME type. Return {valid: boolean, error?: string}.
```

Claude 然後停止並等待。在 `TODO(human)` 註解處編寫您的程式碼，並告訴 Claude 您已完成。Claude 會回應一個關於您程式碼的 `Insight`，並繼續執行任務。

## 變更您的輸出樣式

使用命令、選單或設定檔選擇樣式。命令和兩個選單都會將您的選擇儲存到[本地專案層級](https://code.claude.com/docs/zh-TW/settings.md)的 `.claude/settings.local.json`。

* **`/output-style` 命令**：執行 `/output-style <style>` 以切換，例如 `/output-style concise`。不帶引數時，該命令會列出您可以選擇的樣式並標記目前的樣式。

  該命令也適用於[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)和 Agent SDK 工作階段，以及來自行動應用程式或網頁的[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md#limitations)，您只能列出和選擇[內建樣式](#built-in-output-styles)。需要 Claude Code v2.1.269 或更新版本。
* **終端機選單**：執行 `/config` 並選擇**輸出樣式**以從選單中選擇樣式。
* **VS Code 擴充功能**：使用 `/` 開啟[命令選單](https://code.claude.com/docs/zh-TW/vs-code.md#use-the-prompt-box)並選擇**輸出樣式**以選擇樣式，包括您的自訂樣式。需要 Claude Code v2.1.257 或更新版本。
* **桌面應用程式**：在設定檔中設定 `outputStyle` 欄位，例如 `.claude/settings.local.json`，這是終端機選單寫入的檔案。當您在那裡執行 `/config` 時，Claude Code 會[開啟**設定 > Code** 或**設定 > Claude Code**](https://code.claude.com/docs/zh-TW/desktop.md#what’s-not-available-in-desktop)而不是選單。

若要在不使用選單的情況下設定樣式，請直接編輯設定檔中的 `outputStyle` 欄位：

```json theme={null}
{
  "outputStyle": "Explanatory"
}
```

該值區分大小寫，因此請將內建名稱寫成 `Proactive`、`Concise`、`Explanatory` 和 `Learning`。不完全符合樣式名稱的值（例如 `explanatory`）會給您預設樣式。`/output-style` 命令會忽略大小寫。

若要在各專案中將樣式設為預設值，請在 `~/.claude/settings.json` 中設定 `outputStyle`。專案本身的設定檔會[優先於](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)該值。

當您在工作階段中切換樣式時，Claude 會從您的下一則訊息開始使用新樣式。如需了解該第一則訊息在 prompt caching 中的成本，請參閱[變更輸出樣式](https://code.claude.com/docs/zh-TW/prompt-caching.md#changing-output-style)。在 v2.1.251 之前，新樣式僅在您執行 `/clear` 或開始新工作階段後才會套用。

## 建立自訂輸出樣式

自訂輸出樣式是一個 Markdown 檔案：frontmatter 用於中繼資料，然後是 Claude 的指令。

在 VS Code 擴充功能中，您也可以從[**輸出樣式**選單](https://code.claude.com/docs/zh-TW/vs-code.md#use-the-prompt-box)建立檔案，而不是手動編寫。這需要 Claude Code v2.1.261 或更新版本。

**1. 建立 Markdown 檔案**

將其儲存在三個層級之一。檔案名稱成為樣式名稱，除非您在 frontmatter 中設定 `name`。

* 使用者：`~/.claude/output-styles`
* 專案：`.claude/output-styles`
* 受管原則：[受管設定目錄](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)內的 `.claude/output-styles`

專案輸出樣式會從工作目錄和儲存庫根目錄之間的每個 `.claude/output-styles/` 載入。當多個這些巢狀目錄定義同名樣式時，Claude Code 會使用最接近工作目錄的那個。

**2. 新增 frontmatter 和指令**

決定是否保留 Claude Code 的軟體工程指令。如果您改變 Claude 的溝通方式但仍希望它以相同方式編碼，請設定 `keep-coding-instructions: true`。如果 Claude 不會進行軟體工程，請省略它。

此範例在保留 Claude 編碼行為的同時，在每個說明前面加上圖表：

```markdown theme={null}
---
name: Diagrams first
description: Lead every explanation with a diagram
keep-coding-instructions: true
---

When explaining code, architecture, or data flow, start with a Mermaid diagram showing the structure, then explain in prose.

## Diagram conventions

Use `flowchart TD` for control flow and `sequenceDiagram` for request paths. Keep diagrams under 15 nodes.
```

**3. 切換到您的樣式**

在終端機中執行 `/output-style <style>`，或執行 `/config` 並在**輸出樣式**下選擇您的樣式。Claude 從您的下一則訊息開始使用新樣式。在終端機中，Claude Code 在啟動時讀取樣式檔案，因此如果您在執行工作階段期間建立或編輯樣式檔案，請重新啟動 Claude Code 以套用變更。

[Plugins](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md) 也可以在 `output-styles/` 目錄中提供輸出樣式。

### Frontmatter 參考

使用 YAML [frontmatter](https://code.claude.com/docs/zh-TW/glossary.md#frontmatter) 在檔案頂部的 `---` 標記之間設定輸出樣式。所有欄位都是選用的，欄位名稱使用以連字號分隔的小寫單字。拼寫錯誤的欄位會被忽略而不會出現錯誤。如果 YAML 無法解析，樣式仍會以其檔案名稱載入，且不會設定任何欄位；執行 `claude --debug` 以查看解析錯誤。

| 欄位 | 必要 | 描述 |
| :- | :- | :- |
| `name` | 否 | 輸出樣式的名稱，在 `/config` 選擇器中顯示。預設：檔案名稱 |
| `description` | 否 | 輸出樣式的描述，在 `/config` 選擇器中顯示 |
| `keep-coding-instructions` | 否 | 設定為 `true` 以將 Claude Code 內建軟體工程指令的區段（僅完整系統提示詞包含此區段）與您的風格一起保留。請參閱[輸出風格的運作方式](#how-output-styles-work)。預設：`false` |
| `force-for-plugin` | 否 | 僅限 Plugin 輸出樣式。設定為 `true` 以在啟用 plugin 時自動應用此樣式，無需要求使用者選擇它。覆蓋使用者的 `outputStyle` 設定。如果多個啟用的 plugin 設定此項，Claude Code 會使用第一個載入的。預設：`false` |

## 在輸出樣式和其他功能之間選擇

輸出樣式適用於工作階段中的每個回應。這是 Claude 遵循的指令，所以沒有任何東西強制執行它。當您想要的內容比每個回應更狹隘，或必須無一例外地發生時，另一個功能更適合。

此表格將您想要的內容與執行該功能的功能相匹配：

| 您想要 | 使用 | 為什麼適合 |
| :- | :- | :- |
| 每個回應都採用特定的語氣、長度或格式，或 Claude 採用不同的角色 | 輸出樣式 | 它適用於整個工作階段，您可以用一個命令切換樣式 |
| Claude 了解您專案的慣例、命令和結構 | [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md) | 它保存 Claude 應該了解的程式碼庫內容，無論您選擇哪種樣式，它都會保持載入 |
| 一種任務類型的指令，例如發行檢查清單或審查程序 | [skill](https://code.claude.com/docs/zh-TW/skills.md) | Claude 只在您叫用它或任務相符時才載入它，所以它不會影響無關的回應 |
| 每次都無一例外地發生的事情，例如每次編輯後的格式化或阻止命令 | [hook](https://code.claude.com/docs/zh-TW/hooks-guide.md) | Claude Code 在生命週期事件時自己執行 hook，所以它不依賴 Claude 遵循指令 |
| 具有自己的指令、模型和工具的助手，用於專注的任務 | [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) | 它在具有自己系統提示的單獨上下文中執行，並將摘要返回到您的對話 |
| 您在啟動 Claude Code 時傳遞的 Claude 指令的補充 | [`--append-system-prompt`](https://code.claude.com/docs/zh-TW/cli-reference#system-prompt-flags) | 它附加到系統提示而不移除任何內容 |

這些功能可以組合。例如，您可以使用 CLAUDE.md 來保存 Claude 應該了解的內容、輸出樣式來決定它如何回應，以及 hook 來保證任何必須發生的事情。[擴展 Claude Code](https://code.claude.com/docs/zh-TW/features-overview.md) 比較其餘的擴展功能。

## 輸出樣式的運作方式

輸出樣式會變更 Claude Code 提供給 Claude 的指令。

* Claude Code 在每個請求中都會傳送作用中樣式的指令。
* 在完整系統提示詞中，自訂輸出風格會省略 Claude Code 的內建軟體工程指令區段，例如如何限定變更範圍、撰寫註解和驗證工作，除非 `keep-coding-instructions` 設定為 `true`。較短的系統提示詞不包含該區段，因此該欄位在那裡沒有作用。若要依賴該欄位，請將 [`CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設定為 `0`，這會在任何模型上選用完整提示詞。

輸出風格適用於主對話和[分支](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)，分支會繼承父代的完整對話和系統提示詞。其他 [subagent 會執行自己的系統提示詞](https://code.claude.com/docs/zh-TW/sub-agents.md#what-loads-at-startup)，因此風格不會改變它們的回應方式。

權杖使用量取決於樣式。樣式的指令會增加輸入權杖，不過提示快取會在工作階段中的第一個請求之後降低此成本。

內建的 Explanatory 和 Learning 樣式設計上會產生比 Default 更長的回應，這會增加輸出權杖。Concise 樣式則相反，它會指示 Claude 預設保持回應簡潔。對於自訂樣式，輸出權杖使用量取決於您的指令告訴 Claude 要產生什麼。

## 相關資源

* [Settings](https://code.claude.com/docs/zh-TW/settings.md)：`outputStyle` 欄位所在位置以及設定優先順序的工作原理
* [Permission modes](https://code.claude.com/docs/zh-TW/permission-modes.md)：Proactive 樣式與自動模式的比較方式
* [Plugins](https://code.claude.com/docs/zh-TW/plugins/overview.md)：與 skills、hooks 和 agents 一起打包和分發輸出樣式
* [Debug your configuration](https://code.claude.com/docs/zh-TW/debug-your-config.md)：診斷為什麼輸出樣式沒有生效
