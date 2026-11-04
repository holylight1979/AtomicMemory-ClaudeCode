# 01-getting-started 導讀：Platforms and integrations / Code review and pull requests

> 依 `_manifest.json` 篩出 33 頁；每頁一張導讀卡。原文見同資料夾各 .md。


## Platforms and integrations

### 在 Chrome 中使用 Claude Code（`chrome`）
- 檔案：[chrome.md](chrome.md)｜https://code.claude.com/docs/zh-TW/chrome｜lastmod 2026-10-30｜24.0 KB
- 一句話：Claude in Chrome 擴充功能整合：用 --chrome 讓 CLI/VS Code 操作已登入的瀏覽器。
- 何時讀：要測網頁、除錯 console、填表單、自動化無 API 網站時。
- 關鍵內容：
  - claude --chrome 啟用；需擴充功能 1.0.36+ 與 /login 直接訂閱
  - 不支援 Bedrock/Vertex/Foundry 第三方供應商
  - 支援 Chrome、Edge 及其他 Chromium（Brave、Arc 等）
  - 可讀 console、DOM、上傳檔案、錄 GIF、存截圖
  - /clear 或結束時關閉其標籤群組；網站權限可管理
  - plan mode 內有瀏覽器工具規則
- 新名詞：`Claude in Chrome` ＝ 官方瀏覽器擴充功能，供 Claude 操作你已登入的分頁；`標籤頁群組` ＝ 擴充功能把 Claude 開的分頁綁在會話的群組
- 記憶系統接點：瀏覽器工具屬 MCP 類工具，可被 PreToolUse hook 攔截；分頁隨 /clear 清理。

### 在雲端使用 Claude Code（`claude-code-on-the-web`）
- 檔案：[claude-code-on-the-web.md](claude-code-on-the-web.md)｜https://code.claude.com/docs/zh-TW/claude-code-on-the-web｜lastmod 2026-10-30｜48.7 KB
- 一句話：雲端會話：Anthropic VM 跑 Claude Code，含 --cloud、--teleport、自動修復 PR 與安全隔離。
- 何時讀：要用雲端會話、在終端機/雲端間搬工作、設環境時。
- 關鍵內容：
  - claude --cloud 啟動；舊 --remote 為別名；一次一個儲存庫
  - claude --teleport / /teleport(/tp) / /tasks 按 t 把雲端會話拉回終端機
  - GitHub：Claude GitHub App 或 /web-setup（gh token）
  - 無 GitHub 遠端時打包上傳（<100MB；CCR_FORCE_BUNDLE=1）
  - /autofix-pr 與 Changes 卡片的自動修復：回應 CI 失敗與審查留言
  - 隔離 VM、網路等級、憑證留在沙箱外、setup script 約五分鐘內才快取
- 新名詞：`雲端環境` ＝ 保存網路存取、環境變數、setup script 的雲端設定；`teleport` ＝ 把雲端會話單向拉進本機終端機繼續；`自動修復` ＝ 監看 PR、依 CI/審查事件推送修正；`快速設定` ＝ Team/Enterprise 減少 GitHub 與環境上線步驟的組織開關
- 記憶系統接點：雲端會話不載使用者層設定/外掛；SessionStart hook 在雲端有逾時；與本機記憶檔層不共享。

### 讓 Claude 使用 Projects 協調進行中的工作（`claude-projects`）
- 檔案：[claude-projects.md](claude-projects.md)｜https://code.claude.com/docs/zh-TW/claude-projects｜lastmod 2026-10-30｜60.7 KB
- 一句話：Projects（公開測試版）：一個協調對話啟動並追蹤多個雲端執行緒完成一項工作。
- 何時讀：工作大於單一會話、跨多儲存庫或需持續投餵任務時。
- 關鍵內容：
  - 組成：project 對話(協調者)、執行緒(雲端會話)、Overview 窗格、Library
  - 每執行緒開始：儲存庫+檔案+指示與記憶、各庫 CLAUDE.md、連接器、雲端環境
  - 執行緒不載入庫內 skill、.claude/settings.json、.mcp.json
  - 設定在 claude.ai/code 或 Desktop，不在 settings.json；Pause/Archive/Delete
  - Pro/Max/Ultra；project 屬個人，與 Claude Tag 的共享頻道不同
  - 需在複製的每個庫安裝 Claude GitHub App
- 新名詞：`project` ＝ 長期協調對話加其啟動的執行緒；`thread(執行緒)` ＝ project 中單一工作的雲端會話；`Overview` ＝ 一眼看所有執行緒與需你處理者的窗格；`Project instructions` ＝ 每個新執行緒都會收到的常設規則
- 記憶系統接點：project 有 Memory 檔與指示注入每個執行緒，類似 SessionStart 注入；執行緒僅取 CLAUDE.md，不取 hooks/skills。

### Work with Claude Tag（`claude-tag`）
- 檔案：[claude-tag.md](claude-tag.md)｜https://code.claude.com/docs/en/claude-tag｜lastmod 無｜12.7 KB
- 一句話：Claude Tag（公開測試版）：Team/Enterprise 在 Slack 以組織共享身分執行 @Claude，管理員管控存取。
- 何時讀：評估或設定 Slack 中組織共享的 Claude、查計費與記憶範圍時。
- 關鍵內容：
  - 僅 Team/Enterprise、Anthropic 一方服務；個人方案不可
  - Owner 於 claude.ai/admin-settings/claude-tag 設定；Slack 發 @Claude connect 取配對碼
  - 用量計費（usage balance+每月支出上限），不依席位
  - 臨時沙箱執行；經 connectors、plugins、skills 擴充存取
  - 頻道記憶、頻道/串/群組 DM 與一對一 DM（走個人帳戶）規則不同
  - 能力：排程作業、頻道監看、觸發
- 新名詞：`Claude Tag` ＝ 在 Slack 頻道標記即可交付工作的共享身分 Claude；`usage balance` ＝ Claude Tag 按用量扣款的組織餘額；`channel memory` ＝ 按頻道保留、依地點跟隨的記憶
- 記憶系統接點：有頻道記憶與「依地點跟隨」記憶範圍模型，可對照 atom 的 scope；沙箱臨時，擴充走 plugins/skills/connectors。

### 讓 Claude 從 CLI 使用您的電腦（`computer-use`）
- 檔案：[computer-use.md](computer-use.md)｜https://code.claude.com/docs/zh-TW/computer-use｜lastmod 2026-10-30｜12.0 KB
- 一句話：CLI 的 computer use：macOS 上讓 Claude 開 app、點擊、看螢幕（內建 MCP computer-use）。
- 何時讀：需要驅動沒有 CLI/API 的原生 GUI app 時。
- 關鍵內容：
  - macOS 限定、研究預覽、Pro/Max/Ultra；Team/Enterprise 無
  - 在 /mcp 啟用內建 computer-use 伺服器（按專案）
  - 需授權 Accessibility 與 Screen Recording
  - 優先序：MCP > Bash > Chrome > computer use
  - 護欄：按 app 核准、終端機排除於截圖、Esc 全域中止、鎖檔一次一會話
  - 與 Desktop 差異：Desktop 有 Windows、拒絕清單設定
- 新名詞：`computer-use` ＝ 內建 MCP 伺服器，提供螢幕截圖與點擊鍵盤控制；`哨兵警告` ＝ 核准前對可存取 shell/檔案系統的 app 的標示
- 記憶系統接點：內建 MCP 伺服器可用 /mcp 開關；工具名可被 hook matcher 比對；鎖檔機制可類比多 session 互斥。

### Desktop 應用程式（`desktop`）
- 檔案：[desktop.md](desktop.md)｜https://code.claude.com/docs/zh-TW/desktop｜lastmod 2026-11-04｜219.2 KB
- 一句話：Desktop App 的 Code 標籤全貌：並行會話、窗格、預覽、電腦使用、Dispatch、SSH、企業設定。
- 何時讀：要深入用 Desktop、設定 launch.json、SSH 會話、受管設定時。
- 關鍵內容：
  - 會話=獨立聊天+資料夾；可在 worktree 並行
  - Browser 窗格預覽；設定存 .claude/launch.json（autoVerify 預設開）
  - 電腦使用（macOS/Windows，Pro/Max/Ultra 研究預覽）；依 app 分層授權
  - Claude 可跨會話列出、傳訊、封存其他本機/SSH/WSL 會話
  - 會話可 Cloud 繼續；Remote Control 開關；disableRemoteControl 設定
  - 企業：管理員主控台、受管設定、裝置管理、SSO；SSH 預設設定檔
- 新名詞：`session` ＝ Desktop 中一個對話＋專案資料夾的獨立單位；`Suggested task` ＝ Claude 發現範圍外待辦後提出、可另開會話的卡片；`launch.json` ＝ Desktop 預覽伺服器啟動設定檔（.claude/launch.json）；`Cowork` ＝ Desktop 內負責 Dispatch 與長時間代理工作的部分
- 記憶系統接點：launch.json/受管設定與設定分層同構；跨會話傳訊是機制事實，涉多 session 協作；Desktop 沿用同一 hooks/skills/MCP。

### 在模擬器中測試 iOS 應用程式（`desktop-ios-simulator`）
- 檔案：[desktop-ios-simulator.md](desktop-ios-simulator.md)｜https://code.claude.com/docs/zh-TW/desktop-ios-simulator｜lastmod 2026-10-30｜11.8 KB
- 一句話：Desktop 的 iOS Simulator 窗格：Claude 建置並在模擬器跑 iOS app。
- 何時讀：在 Mac 上用 Desktop 測 iOS app 時。
- 關鍵內容：
  - macOS 限定、公開測試版；Desktop v1.24012.0+
  - 需 Xcode 與 iOS 平台；用 xcode-select 選版本
  - 只限本機會話，雲端/SSH 不可
  - 不需電腦使用，直接驅動模擬器
  - 裝置存取可首次允許、可關閉；遵循權限模式
- 新名詞：`Simulator 窗格` ＝ Desktop 中顯示 iOS Simulator 的窗格
- 記憶系統接點：無

### Linux 上的 Claude Desktop（測試版）（`desktop-linux`）
- 檔案：[desktop-linux.md](desktop-linux.md)｜https://code.claude.com/docs/zh-TW/desktop-linux｜lastmod 2026-10-21｜12.3 KB
- 一句話：Linux 上的 Claude Desktop（測試版）安裝與 Cowork 需求。
- 何時讀：在 Ubuntu/Debian 安裝 Desktop 時。
- 關鍵內容：
  - Ubuntu 22.04+/Debian 12+；x86_64 或 arm64
  - 加 Anthropic apt 儲存庫與簽署金鑰（驗證指紋）
  - Cowork 需 KVM、QEMU、UEFI；使用者加入 kvm 群組
  - 更新走 apt
  - 部分功能於測試版尚未提供
- 新名詞：`KVM` ＝ Linux 硬體虛擬化，Cowork 用它跑 VM
- 記憶系統接點：無

### 開始使用桌面應用程式（`desktop-quickstart`）
- 檔案：[desktop-quickstart.md](desktop-quickstart.md)｜https://code.claude.com/docs/zh-TW/desktop-quickstart｜lastmod 2026-10-30｜11.6 KB
- 一句話：安裝 Desktop 並開第一個 Code 會話。
- 何時讀：第一次裝 Desktop、不知道從哪開始時。
- 關鍵內容：
  - macOS/Windows(x64、ARM64) 下載；Linux 用 apt
  - 側邊欄 Code 標籤；內建 Claude Code，無需 Node 或 CLI
  - 環境選擇器選 Local 與資料夾
  - 需付費方案，否則提示升級
  - 403 錯誤見驗證疑難排解
- 新名詞：`環境選擇器` ＝ Desktop 提示詞下方選 Local/Cloud/SSH 的控制項
- 記憶系統接點：無

### 在 Claude Code Desktop 中排程定期任務（`desktop-scheduled-tasks`）
- 檔案：[desktop-scheduled-tasks.md](desktop-scheduled-tasks.md)｜https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks｜lastmod 2026-10-27｜16.0 KB
- 一句話：Desktop 本機排程任務：定時開新會話跑提示詞，並與雲端/loop 比較。
- 何時讀：想在自己電腦定時跑 Claude（每日審查、相依性檢查）時。
- 關鍵內容：
  - 三選項對照：Cloud(1h 最小)、Desktop(表單 1h/Claude 設 1 分鐘)、/loop(1 分鐘)
  - 需 Desktop 1.1.5368+；開 Only on this computer 並選本機資料夾
  - 排程選項 Hourly/Daily/Weekdays/Weekly/Manual/Custom(cron)
  - 應用程式開著時每分鐘檢查；睡眠錯過的補跑回溯七天
  - 任務提示存 ~/.claude/scheduled-tasks/<name>/SKILL.md
  - 每任務有自己權限模式；requiresUserInteraction MCP 工具每次提示
- 新名詞：`本機排程任務` ＝ 在自己電腦、app 開啟時才會觸發的 Desktop 排程；`Run now` ＝ 立即執行一次任務並藉此預先核准權限；`Only on this computer` ＝ 把任務限制為本機而非雲端的開關
- 記憶系統接點：任務以 SKILL.md 形式落在 ~/.claude/scheduled-tasks/，與 skills 目錄機制同形；Desktop 排程會話同樣觸發 hooks。

### Claude Code Desktop in WSL（`desktop-wsl`）
- 檔案：[desktop-wsl.md](desktop-wsl.md)｜https://code.claude.com/docs/zh-TW/desktop-wsl｜lastmod 2026-10-19｜4.1 KB
- 一句話：Desktop 在 WSL2 發行版內執行 Code 會話。
- 何時讀：儲存庫在 WSL 檔案系統內、想用 Desktop 時。
- 關鍵內容：
  - 需 WSL 2（不支援 WSL1）與發行版內 git
  - 環境選擇器選發行版；信任按發行版+資料夾授予
  - 平行會話、diff、worktree 可用
  - 外掛不可用；檔案窗格唯讀；附件可能僅圖片
  - 終端機與連接器逐步推出，第三方供應商下不提供
- 新名詞：`WSL 會話` ＝ Desktop 在 WSL2 發行版內執行的會話
- 記憶系統接點：無

### JetBrains IDEs（`jetbrains`）
- 檔案：[jetbrains.md](jetbrains.md)｜https://code.claude.com/docs/zh-TW/jetbrains｜lastmod 2026-11-03｜12.0 KB
- 一句話：JetBrains IDE 外掛：差異檢視、選取共享、/ide 連線與 WSL 設定。
- 何時讀：在 IntelliJ/PyCharm/WebStorm 等使用 Claude Code、/ide 偵測不到 IDE 時。
- 關鍵內容：
  - 外掛在 IDE 終端跑 claude；需另裝 CLI
  - /ide 從外部終端連到 JetBrains；/config 的 Diff tool = auto|terminal
  - 檔案參考 Cmd+Option+K / Alt+Ctrl+K，如 @src/auth.ts#L1-99
  - 內建 IDE MCP 伺服器 ide，模型只見 mcp__ide__getDiagnostics
  - 鎖檔 ~/.claude/ide/<port>.lock；ws:// 本機；Read deny 規則擋選取共享
  - WSL2：防火牆規則或 .wslconfig networkingMode=mirrored
- 新名詞：`ide MCP server` ＝ 外掛開的本機 MCP，供開 diff、讀選取與診斷，不顯示於 /mcp
- 記憶系統接點：PreToolUse hook 若白名單 MCP 工具需知 mcp__ide__getDiagnostics 存在；Read deny 規則同時擋 IDE 選取內容。

### Claude Code 行動版（`mobile`）
- 檔案：[mobile.md](mobile.md)｜https://code.claude.com/docs/zh-TW/mobile｜lastmod 2026-10-30｜9.0 KB
- 一句話：Claude iOS/Android app 作為 Code 的用戶端：雲端會話、專案、Remote Control、Dispatch。
- 何時讀：想用手機啟動或監控 Claude Code 時。
- 關鍵內容：
  - 沒有獨立行動版；皆在 Claude app 的 Code 標籤
  - /mobile 在會話內顯示下載 QR
  - 四種連線：雲端會話、專案、Remote Control、Dispatch
  - Remote Control 附件：照片存 ~/.claude/uploads/
  - 電腦關閉時用雲端會話或專案
- 新名詞：`Code 標籤` ＝ Claude 手機 app 中進入 Code 會話的入口
- 記憶系統接點：無

### 平台和整合（`platforms`）
- 檔案：[platforms.md](platforms.md)｜https://code.claude.com/docs/zh-TW/platforms｜lastmod 2026-10-30｜10.0 KB
- 一句話：比較 CLI、Desktop、IDE、Web、Mobile 各平台與整合，並列出離開終端機的工作方式。
- 何時讀：選擇要在哪裡跑 Claude Code、或想知道 Dispatch/Remote Control/Channels/排程差在哪時。
- 關鍵內容：
  - 六平台：CLI、Desktop、VS Code、JetBrains、Web、Mobile
  - Agent SDK 與指令碼僅 CLI 有；IDE 內第三方供應商是跑 CLI
  - 配置、專案記憶、MCP 在本機各介面間共用
  - 整合：Chrome、GitHub Actions、GitLab CI/CD、Code Review、Slack、Claude Tag
  - 遠離終端機六法：Dispatch、Remote Control、Channels、Slack、自託管環境、排程
  - 排程三處：CLI(/loop)、Desktop、雲端 routines
- 新名詞：`Dispatch` ＝ 從手機 Claude app 傳任務給 Desktop，由它決定怎麼跑；`Channels` ＝ 把 Telegram/Discord 或自家伺服器事件推進會話的機制；`Self-hosted environments` ＝ 雲端會話改在組織自己基礎設施的執行器上跑
- 記憶系統接點：「配置、專案記憶、MCP 在本機介面間共享」與記憶系統的檔案層一致；無新衝突。

### 使用 Remote Control 從任何裝置繼續本地會話（`remote-control`）
- 檔案：[remote-control.md](remote-control.md)｜https://code.claude.com/docs/zh-TW/remote-control｜lastmod 2026-11-02｜63.0 KB
- 一句話：Remote Control：用 claude.ai/code 或手機驅動本機執行中的會話（本機執行、只出站 HTTPS）。
- 何時讀：想從別的裝置延續本機工作、設定自動連線或排錯時。
- 關鍵內容：
  - claude remote-control 伺服器模式；claude --remote-control(--rc)；/remote-control(/rc)
  - 伺服器旗標：--name、--spawn same-dir|worktree|session、--capacity(預設32)、-c、--session-id
  - 設定鍵 remoteControlAtStartup、disableRemoteControl；僅 claude.ai 登入
  - 本機程序只出站 HTTPS，不開入站埠；記錄存 Anthropic 伺服器
  - 受信任裝置（測試版）：註冊裝置+登入≤18小時，需 Face ID/Touch ID 等
  - 限制：ZDR/HIPAA、Bedrock/Vertex/Foundry、ANTHROPIC_BASE_URL 非官方皆不可
- 新名詞：`Remote Control` ＝ 遠端視窗操作本機 Claude 會話，執行仍在你的機器；`伺服器模式` ＝ claude remote-control 常駐等遠端連線並可多會話；`受信任裝置` ＝ 要求註冊裝置與近期登入才能遠端控制；`spawn 模式` ＝ 伺服器建立新會話時共用目錄或各用 worktree
- 記憶系統接點：--spawn worktree 與多會話隔離同概念；CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC 會使其不可用；遠端所見斜線命令受限。

### 使用排程任務自動化工作（`routines`）
- 檔案：[routines.md](routines.md)｜https://code.claude.com/docs/zh-TW/routines｜lastmod 2026-11-03｜50.2 KB
- 一句話：Scheduled tasks（前稱 routines）：雲端排程/API/GitHub 觸發的自動 Claude Code 任務（研究預覽）。
- 何時讀：要在雲端定時或事件驅動自動跑 Claude，或用 API 呼叫觸發時。
- 關鍵內容：
  - 觸發三種可組合：Schedule、API(/fire + bearer token)、GitHub event
  - CLI：/schedule（別名 /routines）、/schedule list|update|run；GitHub 觸發需 v2.1.225+
  - /fire 需 beta 標頭 experimental-cc-routine-2026-04-01；text 被包成 <routine-fire-payload> 視為不受信任
  - 排程時區：預設本地時區；cron 五欄位為 UTC；不得高於每小時一次
  - 限制：排程每小時100/帳戶；Run now+API 每任務30/小時；GitHub 事件有上限
  - 預設自動模式；分支前綴 claude/；GitHub 斷線最多略過72小時
- 新名詞：`routine/scheduled task` ＝ 已存的提示詞+儲存庫+連接器，在雲端依觸發自動跑；`fire URL` ＝ API 觸發的專屬端點，含任務專屬 token；`routine-fire-payload` ＝ 包住 API text 並標示為不受信任資料的區塊
- 記憶系統接點：提示詞與 API text 的信任分離可借鏡；與 hooks 無直接關係；雲端 run 不載入本機記憶檔，只讀 clone 的 CLAUDE.md。

### Slack 中的 Claude Code（`slack`）
- 檔案：[slack.md](slack.md)｜https://code.claude.com/docs/zh-TW/slack｜lastmod 2026-11-02｜15.1 KB
- 一句話：舊版 Slack 中的 Claude Code：Pro/Max/Ultra 帳戶在頻道 @Claude 派編碼任務到雲端。
- 何時讀：個人方案用 Slack 派任務，或工作區已被 Claude Tag 取代而收到通知時。
- 關鍵內容：
  - 僅限未被組織連到 Claude Tag 的工作區、Pro/Max/Ultra
  - 安裝 Claude app→Connect Claude account→雲端會話→/invite @Claude
  - 路由模式：僅代碼、代碼+聊天（自動偵測，可 Switch to code）
  - 僅頻道內有效，DM 不行；執行緒/近期頻道訊息作背景
  - 限制：只 GitHub、每會話一個 PR
  - 錯誤：Claude Tag 工作區顯示 legacy bot is retired
- 新名詞：`路由模式` ＝ 決定 @Claude 訊息送 Code 或 Chat 的設定；`Claude Tag` ＝ 組織共享身分的新 Slack 整合，取代此舊版於 Team/Enterprise
- 記憶系統接點：Slack 訊息成為任務背景資訊（類似外部輸入來源）；無記憶接點。

### 在 VS Code 中使用 Claude Code（`vs-code`）
- 檔案：[vs-code.md](vs-code.md)｜https://code.claude.com/docs/zh-TW/vs-code｜lastmod 2026-11-04｜101.6 KB
- 一句話：VS Code 擴充功能的安裝、提示詞輸入框、對話管理、外掛、設定與疑難排解。
- 何時讀：在 VS Code 使用 Claude Code、調整 claudeCode.* 設定、排除擴充功能問題。
- 關鍵內容：
  - 快捷鍵：Cmd/Ctrl+Esc 切焦點、Cmd/Ctrl+Shift+Esc 新分頁
  - @-mention 檔案/資料夾；Option/Alt+K 插入目前選取參照
  - 設定鍵：claudeCode.initialPermissionMode、useTerminal、environmentVariables
  - claudeCode.continueAfterReload：重新載入後接續對話
  - 內建 IDE MCP 伺服器（getDiagnostics）；有 /rc 與 /remote-control
  - /mcp、/plugin 管理；可繼續 claude.ai 雲端會話
- 新名詞：`Spark 圖示` ＝ VS Code 內 Claude Code 的入口圖示；`continueAfterReload` ＝ VS Code 重載後自動重開對話的設定；`Focus view` ＝ 隱藏對話中工具活動的檢視模式
- 記憶系統接點：擴充功能走同一 settings.json/hooks/MCP 體系，記憶注入 hook 同樣生效；cloud 會話不載入使用者層外掛。

### 在雲端開始使用 Claude Code（`web-quickstart`）
- 檔案：[web-quickstart.md](web-quickstart.md)｜https://code.claude.com/docs/zh-TW/web-quickstart｜lastmod 2026-11-03｜24.7 KB
- 一句話：雲端會話快速入門：連 GitHub、設環境、送第一個任務。
- 何時讀：第一次用 claude.ai/code 時。
- 關鍵內容：
  - 適用 Pro/Max/Ultra/Team 及 Enterprise 高級席位
  - 流程：複製→網路設定→工作→推送分支，推送後會話不關
  - 對照表：雲端 / 本機 / 本機+Remote Control
  - 連 GitHub：登入授權；私有庫需 Claude GitHub App
  - 權限模式：接受編輯、Plan、Auto
  - 適合並行任務與沒檢出的儲存庫
- 新名詞：`預設環境` ＝ 首次上線建立、網路等級為 Trusted 的雲端環境
- 記憶系統接點：無


## Code review and pull requests

### 掃描程式碼庫以尋找漏洞（`claude-security`）
- 檔案：[claude-security.md](claude-security.md)｜https://code.claude.com/docs/zh-TW/claude-security｜lastmod 2026-10-26｜16.6 KB
- 一句話：Claude Security 外掛：/claude-security 在工作階段內多 agent 掃描程式碼庫漏洞並產出修補。
- 何時讀：要整庫或針對變更做漏洞掃描、取得 patch 時。
- 關鍵內容：
  - 安裝 /plugin install claude-security@claude-plugins-official；需 Python 3.9+、git（變更掃描）
  - 指令 /claude-security：Scan codebase / Scan changes / Suggest patches
  - 強度 low / medium(預設) / high，皆有獨立驗證
  - 結果寫入 CLAUDE-SECURITY-<timestamp>/，含 CLAUDE-SECURITY-RESULTS.md 與 patches/
  - 進度在 /workflows 查看；修補不自動套用，需 git apply
  - 在工作階段模型上本機執行，計入使用量；用動態工作流程協調 agent
- 新名詞：`Claude Security plugin` ＝ 會話內多 agent 漏洞掃描外掛；`動態工作流程` ＝ 外掛用來協調多 agent 的工作流機制，可由 /workflows 檢視
- 記憶系統接點：外掛提供斜線命令與 /workflows；結果落成時間戳目錄於 repo；與 security-guidance 分工（寫時 vs 掃描）。

### Code Review（`code-review`）
- 檔案：[code-review.md](code-review.md)｜https://code.claude.com/docs/zh-TW/code-review｜lastmod 2026-10-24｜10.4 KB
- 一句話：Code Review 託管服務總覽：多 agent 並行審查 GitHub PR，驗證後發行內留言。
- 何時讀：評估 Code Review 是否適用、了解四階段與審查等級時。
- 關鍵內容：
  - 僅 Team/Enterprise、GitHub（含 GHES）；ZDR/HIPAA/CMEK 組織不可用
  - 四階段：尋找（多 agent 並行）→驗證（濾誤判）→排名→發佈
  - PR 上產出：行內留言+摘要+名為 Claude Code Review 的 check run（不致失敗）
  - 審查等級 Quick / Standard(預設) / Deep，可每儲存庫覆寫
  - 預設專注正確性而非風格；以 REVIEW.md 調整
  - Owner 在 Admin settings > Claude Code 啟用
- 新名詞：`Code Review` ＝ Anthropic 基礎設施上對 PR 自動審查的託管服務；`審查等級` ＝ Quick/Standard/Deep，徹底度與費用遞增；`check run` ＝ PR 上名為 Claude Code Review 的檢查項，列出發現
- 記憶系統接點：服務讀 CLAUDE.md 與 REVIEW.md；本機 /code-review 只讀 CLAUDE.md，兩者是不同工具。

### Code Review 費用與用量（`code-review-costs`）
- 檔案：[code-review-costs.md](code-review-costs.md)｜https://code.claude.com/docs/zh-TW/code-review-costs｜lastmod 2026-10-29｜6.1 KB
- 一句話：Code Review 以用量點數計費：估算、每月支出上限與分析儀表板。
- 何時讀：估算 Code Review 費用、設預算、查用量時。
- 關鍵內容：
  - 依 token 以用量點數計費，與方案內含額度分開，費用計到組織
  - 費用隨審查等級、變更大小、周邊複雜度；次數隨 Review runs
  - 草稿與 fork 的 PR 自動審查略過
  - @claude review always 會把 PR 加入推送觸發
  - 預算在 claude.ai/admin-settings/usage；用盡則略過並在 PR 留言
  - 儀表板 claude.ai/analytics/code-review，Average cost 欄
- 新名詞：`用量點數` ＝ Code Review 與 ultrareview 計費用的額度
- 記憶系統接點：無

### 自訂 Code Review（`code-review-customize`）
- 檔案：[code-review-customize.md](code-review-customize.md)｜https://code.claude.com/docs/zh-TW/code-review-customize｜lastmod 2026-10-24｜16.5 KB
- 一句話：用 REVIEW.md 與 CLAUDE.md 調整 Code Review 的標記內容、嚴重度與略過範圍。
- 何時讀：審查太吵、想略過生成檔、想加團隊規則時。
- 關鍵內容：
  - CLAUDE.md：專案指令，違反即成發現；讀根目錄與變更檔上層目錄的檔
  - REVIEW.md：僅審查用；根目錄與子目錄皆可
  - 可重定義 Important、限制 Nit 數量、列出 Do not report、Always check
  - 找問題與驗證兩類 agent 都讀 REVIEW.md
  - 需合併到預設分支並建議保護預設分支
  - 可要求某類發現附 file:line 證據
- 新名詞：`REVIEW.md` ＝ Code Review 專用審查指令檔；`Nit` ＝ 低嚴重度、不擋合併的小問題
- 記憶系統接點：REVIEW.md/CLAUDE.md 分層（根+子目錄）與 CLAUDE.md 載入規則同構；審查讀的是預設分支版本。

### 使用 /code-review 在本機審查（`code-review-local`）
- 檔案：[code-review-local.md](code-review-local.md)｜https://code.claude.com/docs/zh-TW/code-review-local｜lastmod 2026-11-03｜14.4 KB
- 一句話：本機 /code-review：在自己會話審查分支/PR/路徑，可 --fix 或 --comment。
- 何時讀：要在合併前本機審查、想讓 Claude 自動套用修正時。
- 關鍵內容：
  - 任何方案可用；/review 是別名（v2.1.223 前為獨立命令）
  - 旗標：--fix（審查後套用到工作樹）、--comment（貼 GitHub PR 行內或 GitLab MR 備註）
  - 目標：HEAD~15..HEAD、main...my-feature、單一提交、PR 編號、路徑
  - 終端機中以背景 forked subagent 執行，有獨立 context
  - 背景審查的 --fix 編輯在 checkpoint 之外，/rewind 無法回復
  - 遵循 CLAUDE.md（含 -p），不讀 REVIEW.md；effort 等級低到 ultra
- 新名詞：`forked subagent` ＝ 分叉出去、擁有獨立 context 視窗的背景子代理；`ReportFindings 工具` ＝ 宿主 app 用來接收審查發現清單的工具
- 記憶系統接點：審查以 forked subagent 跑，不佔主 context；--fix 在 checkpoint 外屬 context/回溯管理要點。

### 在 pull request 上閱讀與請求審查（`code-review-pull-requests`）
- 檔案：[code-review-pull-requests.md](code-review-pull-requests.md)｜https://code.claude.com/docs/zh-TW/code-review-pull-requests｜lastmod 2026-10-24｜15.5 KB
- 一句話：開發者視角：在 PR 上讀發現、回應或駁回，並用 @claude review 請求審查。
- 何時讀：收到 Claude Code Review 留言、要請求重審時。
- 關鍵內容：
  - 嚴重度：Important(紅)、Nit(黃)、Pre-existing(紫)
  - 駁回需在 GitHub 解決討論串；僅回覆不算
  - @claude review 單次；@claude review always 訂閱後續推送
  - check run 結論 neutral 或 skipped；Details 為依嚴重度的表
  - 推送無新變更時保留先前結果：skipped / not repeated
  - 可從 CI 腳本讀結果
- 新名詞：`Pre-existing` ＝ 非此 PR 引入、既有程式碼的問題；`Why this was flagged` ＝ 收合區段，說明該發現的推理
- 記憶系統接點：無

### 設定 Code Review（`code-review-setup`）
- 檔案：[code-review-setup.md](code-review-setup.md)｜https://code.claude.com/docs/zh-TW/code-review-setup｜lastmod 2026-10-20｜14.1 KB
- 一句話：Owner 啟用 Code Review：連 GitHub、裝 Claude GitHub App、選庫與審查時機。
- 何時讀：組織要開通 Code Review、改審查觸發頻率時。
- 關鍵內容：
  - 需 Claude 組織 Owner＋GitHub 組織 owner＋對庫的寫入權
  - Admin settings > Claude Code > Allow code review 開關
  - 步驟：Connect GitHub→Install GitHub App→選庫→Finish
  - 新增庫預設 After every push（最多審查次數）
  - Review runs 三種：Once after PR creation / After every push / Manual (@claude review)
  - 用測試 PR（非草稿）驗證 Claude Code Review check run 出現
- 新名詞：`Review runs` ＝ 每儲存庫設定何時觸發審查；`Claude GitHub App` ＝ 需安裝的 GitHub App，權限比審查實際用的更廣
- 記憶系統接點：無

### Code Review 疑難排解（`code-review-troubleshooting`）
- 檔案：[code-review-troubleshooting.md](code-review-troubleshooting.md)｜https://code.claude.com/docs/zh-TW/code-review-troubleshooting｜lastmod 2026-10-24｜10.7 KB
- 一句話：依 Claude Code Review check run 標題診斷審查沒啟動、失敗、被預算略過。
- 何時讀：PR 上沒出現審查、顯示 skipped/failed/declined 時。
- 關鍵內容：
  - check run 標題對照：queued/in progress/found no issues/skipped/not repeated/failed/timed out/declined
  - @claude review 需頂層留言、開頭、且有 write/maintain/admin 權限
  - 預算訊息三種：月支出上限、無額外用量、餘額過低
  - 補預算後再留言 @claude review 取得被略過的審查
  - 失敗/逾時有重新觸發流程；行內留言未顯示可看 Details 或 Files changed
- 新名詞：`Code review declined` ＝ 因預算等原因審查未執行的狀態
- 記憶系統接點：無

### Claude Code GitHub Actions（`github-actions`）
- 檔案：[github-actions.md](github-actions.md)｜https://code.claude.com/docs/zh-TW/github-actions｜lastmod 2026-10-30｜28.8 KB
- 一句話：Claude Code GitHub Actions：在 workflow 中以 @claude 提及觸發、自動化 PR/議題任務。
- 何時讀：要在 CI 中跑 Claude、設 /install-github-app 或寫 workflow 時。
- 關鍵內容：
  - 快速設定 /install-github-app（僅 github.com）；或手動裝 App+secret+複製 examples/claude.yml
  - 憑證 secret：ANTHROPIC_API_KEY 或 CLAUDE_CODE_OAUTH_TOKEN（claude setup-token）
  - action 為 anthropics/claude-code-action；輸入 prompt、claude_args、trigger_phrase(預設 @claude)、plugins、settings
  - use_bedrock/use_vertex/use_foundry 改走雲端供應商
  - 需 id-token: write；可執行 skill、排程、回應 @claude
  - 透過 CLAUDE.md 定義標準；留意成本與憑證保護
- 新名詞：`claude-code-action` ＝ 官方 GitHub Action，在 workflow 內跑 Claude Code；`trigger_phrase` ＝ 觸發 Claude 的留言詞，預設 @claude
- 記憶系統接點：claude_args 可傳 CLI 旗標；plugins/plugin_marketplaces 與 settings 輸入可帶入 settings/外掛；CLAUDE.md 為 CI 規則來源。

### 使用 Claude Code GitHub Actions 搭配雲端提供者（`github-actions-cloud-providers`）
- 檔案：[github-actions-cloud-providers.md](github-actions-cloud-providers.md)｜https://code.claude.com/docs/zh-TW/github-actions-cloud-providers｜lastmod 2026-09-17｜16.9 KB
- 一句話：GitHub Actions 搭配 Bedrock/Agent Platform/Foundry 的 OIDC 與身分設定。
- 何時讀：要讓 CI 的 Claude 走自己的雲端帳戶時。
- 關鍵內容：
  - 三旗標：use_bedrock / use_vertex / use_foundry = "true"
  - GitHub 身分三選：官方 App、自訂 GitHub App（Contents/Issues/PR 權限）、預設 GITHUB_TOKEN
  - GITHUB_TOKEN 的提交不會觸發 CI workflow
  - 雲端側用 OIDC：AWS IAM 角色、GCP Workload Identity、Azure
  - 需對應供應商已授權 Claude 模型存取
- 新名詞：`Workload Identity Federation` ＝ 免長期金鑰、以 OIDC 向雲端換取身分的機制
- 記憶系統接點：無

### Claude Code 與 GitHub Enterprise Server（`github-enterprise-server`）
- 檔案：[github-enterprise-server.md](github-enterprise-server.md)｜https://code.claude.com/docs/zh-TW/github-enterprise-server｜lastmod 2026-10-28｜20.1 KB
- 一句話：GHES（自託管 GitHub）支援：雲端會話、Code Review、teleport、外掛市集與限制。
- 何時讀：組織用 GitHub Enterprise Server 要接 Claude Code 時。
- 關鍵內容：
  - Team/Enterprise 專屬；支援雲端會話、Code Review、Claude Security、teleport、外掛市集、GitHub Actions(手動)
  - 不支援：Contribution metrics、GitHub MCP server；/install-github-app 僅 github.com
  - Owner 在 Organization settings > Git providers 引導建 GitHub App（manifest，最多20字元顯示名）
  - Code Review 於 claude.ai/admin-settings/claude-code 啟用
  - GHES 外掛市集可用託管設定預先註冊與白名單
  - 網路需求與常見連線/克隆錯誤排除
- 新名詞：`GHES` ＝ GitHub Enterprise Server，自管的 GitHub 執行個體；`GitHub App manifest` ＝ 預填權限的 App 建立流程
- 記憶系統接點：外掛市集預註冊與白名單走受管設定（extraKnownMarketplaces/strictKnownMarketplaces 類機制），屬設定分層。

### Claude Code GitLab CI/CD（`gitlab-ci-cd`）
- 檔案：[gitlab-ci-cd.md](gitlab-ci-cd.md)｜https://code.claude.com/docs/zh-TW/gitlab-ci-cd｜lastmod 2026-09-10｜17.7 KB
- 一句話：Claude Code GitLab CI/CD（測試版，GitLab 維護）：在 CI job 內以 @claude 建 MR、實作議題。
- 何時讀：在 GitLab 做 CI 驅動 Claude 時。
- 關鍵內容：
  - 基於 CLI 與 Agent SDK；在 .gitlab-ci.yml 加 claude job
  - 變數 ANTHROPIC_API_KEY（masked）；image 例 node:24-alpine
  - 可選 Claude API、Amazon Bedrock、Google Cloud Agent Platform（OIDC/WIF）
  - 事件驅動：議題/MR/審查串的 @claude 留言觸發
  - 遵守 CLAUDE.md、分支保護與核准；沙箱容器執行
  - 疑難：不回應 @claude、無法寫評論/開 MR、驗證錯誤
- 新名詞：`masked variable` ＝ GitLab 中遮罩日誌的 CI/CD 變數
- 記憶系統接點：無

### 在 Claude 編寫程式碼時捕捉安全問題（`security-guidance`）
- 檔案：[security-guidance.md](security-guidance.md)｜https://code.claude.com/docs/zh-TW/security-guidance｜lastmod 2026-10-23｜18.2 KB
- 一句話：security-guidance 外掛：Claude 寫碼時三層自動檢查（每編輯、每回合、每次 commit/push）。
- 何時讀：想讓 Claude 自檢程式碼漏洞並於同會話修復時。
- 關鍵內容：
  - 安裝 /plugin install security-guidance@claude-plugins-official；Python 3.7+（代理審查 3.10+）
  - 每次編輯：無模型呼叫的樣式比對（eval、pickle、innerHTML、workflow 檔）
  - 每回合結束：背景模型審查，最多30檔、連續三次後放行
  - Claude 經 Bash 執行 git commit/push 時：更深的代理審查
  - 自訂：security-patterns.yaml 與團隊指導；可獨立停用每層
  - 專案 .claude/settings.json 的 enabledPlugins 可為團隊啟用
- 新名詞：`security-guidance` ＝ 會話內持續檢查 Claude 自己改動的安全外掛；`security-patterns.yaml` ＝ 自訂每編輯樣式的規則檔
- 記憶系統接點：以 hook 式時機運作（編輯後、回合結束、commit/push）並附加警告進下一步 context；首次在 ~/.claude/security/ 建 venv；每警告每會話每檔每樣式僅一次。

### 使用 Ultrareview 尋找錯誤（`ultrareview`）
- 檔案：[ultrareview.md](ultrareview.md)｜https://code.claude.com/docs/zh-TW/ultrareview｜lastmod 2026-10-30｜19.3 KB
- 一句話：Ultrareview（研究預覽）：/code-review ultra 在雲端用多 agent 深度審查並獨立重現驗證每項發現。
- 何時讀：合併前要最高信號的深度審查，或在 CI 非互動執行時。
- 關鍵內容：
  - 指令 /code-review ultra [分支|PR 編號|說明文字]；Claude 不會自己啟動
  - claude ultrareview 子命令：--json、--timeout(預設45分)、--post/--no-post、--trust-workspace；結束碼 0/1/130
  - --post 以你的 GitHub 帳戶貼單一評論；預設不貼；v2.1.227+
  - 通常 5～15 分鐘；背景任務，/tasks 追蹤
  - 差異上限預設 500 檔/8000 行；首次提交需確認
  - Pro/Max/Ultra 各 3 次免費（一次性），之後約 $5～$25 計用量點數；需 claude.ai 登入
- 新名詞：`ultrareview` ＝ 雲端多 agent 深度審查，每項發現皆獨立重現；`免費執行次數` ＝ 每帳戶一次性 3 次配額，不刷新
- 記憶系統接點：claude -p '/code-review ultra' 取不到發現，需用子命令；--trust-workspace 為非互動信任旁路；上傳依雲端會話打包規則。
