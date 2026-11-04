<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w37 | lastmod: 2026-09-25 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w37（官方 zh-TW，lastmod 2026-09-25）｜分類：What's New › What's New｜EN 摘要：Test your plugins with claude plugin eval and pop Claude Code Desktop panes out into their own windows.

# 第 37 週 · 2026 年 9 月 7–11 日

> 使用 claude plugin eval 測試您的外掛程式，並將 Claude Code Desktop 窗格彈出到各自的視窗中。

版本 [v2.1.263 → v2.1.269](https://code.claude.com/docs/en/changelog.md#2-1-263)
2 項功能 · 9 月 7–11 日

使用 claude plugin eval 測試外掛程式
v2.1.269

`claude plugin eval` 針對一套測試案例執行您的外掛程式、評分結果，並且預設會在沒有外掛程式的情況下再次執行每個案例，讓您可以看到外掛程式的貢獻。`claude plugin eval init` 會詢問您良好的結果應該是什麼樣子，然後提議測試案例和評分檢查、嘗試該套件一次，並寫入檔案。每次執行，以及每個有第二個模型判斷回覆的檢查，都是您帳戶上的真實模型呼叫。

![claude plugin eval 的終端輸出：一個包含七個案例的表格，每個案例都有使用和不使用外掛程式的分數、兩者之間的差異、執行次數和成本，後面跟著一個摘要行，顯示平均差異、總持續時間和總成本](https://mintcdn.com/claude-code/f9HTZGyMtxIFOUgt/images/whats-new/plugin-eval.jpg?fit=max\&auto=format\&n=f9HTZGyMtxIFOUgt\&q=85\&s=913066f6d4a2a15426e98a627802f47f)

從您的外掛程式根目錄，讓 Claude 草擬該套件：

```bash terminal theme={null}
claude plugin eval init
```

當 Claude 告訴您該套件已準備好時，退出 `claude plugin eval init` 開啟的工作階段，並執行 `claude plugin eval .` 來評分每個案例。摘要表格會列印在您的終端中，`evals/results/` 下的 `report.html` 包含每次執行的詳細資訊。

[使用評估測試外掛程式](https://code.claude.com/docs/zh-TW/plugin-evals.md)

將 Desktop 窗格彈出到各自的視窗中
Desktop

在 Claude Code Desktop 應用程式中，您可以將任何窗格彈出到其自己的視窗中。將差異或終端拖到第二個螢幕，同時 Claude 在主視窗中繼續工作，然後在完成後將窗格停靠回去。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/f9HTZGyMtxIFOUgt/images/whats-new/desktop-pop-out-panes.mp4?fit=max&auto=format&n=f9HTZGyMtxIFOUgt&q=85&s=ff3770dd09bb15ed9cf17a460f3d1e23" />

[整理您的工作區](https://code.claude.com/docs/zh-TW/desktop.md#arrange-your-workspace)

其他成果

在頂層或 `modelSettings` 下按模型設定 [`maxEffortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#maxeffortlevel)，以限制每個提供者（包括 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry）上的努力等級；任何更高的等級都會以上限執行將 `--plugin-dir` 指向一個外掛程式資料夾，以 [載入每個具有資訊清單的直接子資料夾](https://code.claude.com/docs/zh-TW/plugins/create.md#load-a-directory-or-archive-for-one-session)如果 WebFetch 在五分鐘內未完成下載頁面，[擷取會因截止期限錯誤而失敗](https://code.claude.com/docs/zh-TW/tools-reference.md#webfetch-tool-behavior)，而不是掛起；設定 `CLAUDE_CODE_WEBFETCH_DEADLINE_MS` 以變更截止期限，或設定為 `0` 以移除限制將 `--json` 傳遞給 `claude plugin install`、`uninstall`、`update`、`enable` 或 `disable`，以將結果列印為 [stdout 最後一行上的一個 JSON 物件](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-json-result)當自動模式分類器阻止某個動作時，Claude 收到的原因 [通常會命名相符的規則](https://code.claude.com/docs/zh-TW/auto-mode-config.md#fix-a-denial-with-an-allow-rule-an-environment-entry-or-a-retry)，例如 `[Data Exfiltration]`當您在提示中途輸入 `/` 時，您現在可以從 [相符命令的清單](https://code.claude.com/docs/zh-TW/interactive-mode.md#complete-a-command-mid-prompt)中選擇，而不是單一建議。該清單在全螢幕呈現時隨著您的輸入而開啟。外掛程式技能也會在其名稱上相符，不需要外掛程式前綴在 VS Code 擴充功能中，按一下提示框底部的代理計數以開啟 [代理地圖](https://code.claude.com/docs/zh-TW/vs-code.md#use-the-prompt-box)，您可以在其中開啟子代理的唯讀文字記錄或停止它在 VS Code 擴充功能中，在命令選單的 Customize 部分中選擇 **Hooks** 或 **Permissions**，以 [在您的使用者、專案和本機設定中新增或移除 hooks 和權限規則](https://code.claude.com/docs/zh-TW/vs-code.md#use-the-prompt-box)Claude 可以選擇 [瀏覽器標籤圖示](https://code.claude.com/docs/zh-TW/artifacts.md#create-an-artifact)以符合它發佈的每個成品在雲端工作階段中的 Claude Code 網頁版上，在 Claude 讀取之前取回佇列中的訊息：將其從佇列中移除，或按 `Esc` 或 `Up`，文字會返回到訊息框

[v2.1.263–v2.1.269 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-263)
