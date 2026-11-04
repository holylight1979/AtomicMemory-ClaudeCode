# Claude Code 新名詞／術語白話表（_GLOSSARY）

> 來源：各夾導讀卡「新名詞」欄彙整（453 詞），白話是 LLM 依官方原文改寫；官方詞彙表在 [glossary.md](06-reference/glossary.md)；首次出現版本見 [TIMELINE](08-whats-new/TIMELINE-新功能與新名詞.md) 第一節。

| 詞 | 白話 | 出處頁 |
|---|---|---|
| `$.store` | 機器上所有 session 共用的 JSON 鍵值儲存 | [plugins/mods/api](03-plugins/plugins__mods__api.md) |
| `--bare` | `claude -p` 旗標：略過 hook/skill/外掛/MCP/CLAUDE.md，確保可重現 | [best-practices](01-getting-started/best-practices.md)、[headless](02-build/headless.md) |
| `--permission-prompts none` | 無人值守時把會彈提示的動作一律拒絕 | [headless](02-build/headless.md) |
| `--plugin-dir` | 單一 session 從目錄載入 plugin 的旗標 | [plugins/create](03-plugins/plugins__create.md) |
| `--safe-mode` | 停用所有自訂項目但保留認證／模型／內建工具的啟動模式 | [debug-your-config](02-build/debug-your-config.md) |
| `.claude 目錄` | 設定、hooks、skills、rules 所在資料夾 | [glossary](06-reference/glossary.md) |
| `.worktreeinclude` | 指定要複製進新 worktree 的 gitignored 檔案清單 | [worktrees](02-build/worktrees.md) |
| `/batch` | 把大變更拆成 5～30 個 worktree 隔離子代理的內建 skill | [agents](02-build/agents.md) |
| `/context` | 顯示 context 視窗佔用明細的命令 | [debug-your-config](02-build/debug-your-config.md) |
| `/deep-research` | 內建工作流程：多角度搜尋並投票驗證後出引用報告 | [workflows](02-build/workflows.md) |
| `/goal` | 設定完成條件並自動續跑直到達成的命令 | [best-practices](01-getting-started/best-practices.md)、[goal](02-build/goal.md) |
| `/loop` | 隨附 skill，重複執行提示的命令 | [scheduled-tasks](02-build/scheduled-tasks.md) |
| `/reload-plugins` | 不重啟就套用待處理 plugin 變更的命令 | [plugins/cli-reference](03-plugins/plugins__cli-reference.md) |
| ``/cd`` | 把進行中的 session 移到新工作目錄 | [whats-new/2026-w24](08-whats-new/whats-new__2026-w24.md) |
| ``/code-review`` | 在選定 effort 下報告正確性問題的審查指令 | [whats-new/2026-w21](08-whats-new/whats-new__2026-w21.md) |
| ``/design`` | 從簡短描述產出可編輯 UI 畫板的技能 | [whats-new/2026-w34](08-whats-new/whats-new__2026-w34.md) |
| ``/doctor`` | 完整設定檢查，可診斷並修復，別名 /checkup | [whats-new/2026-w28](08-whats-new/whats-new__2026-w28.md) |
| ``/goal`` | 設定終止條件、Claude 持續回合直到成立 | [whats-new/2026-w20](08-whats-new/whats-new__2026-w20.md) |
| ``/powerup`` | 終端內的互動式 Claude Code 功能教學 | [whats-new/2026-w14](08-whats-new/whats-new__2026-w14.md) |
| ``/recap`` | 返回 session 時給一行離開期間摘要 | [whats-new/2026-w16](08-whats-new/whats-new__2026-w16.md) |
| ``/reload-skills`` | 不重啟重新掃描 skill 目錄 | [whats-new/2026-w22](08-whats-new/whats-new__2026-w22.md) |
| ``/skill-doctor`` | 列出各 skill 的上下文成本與使用率 | [whats-new/2026-w36](08-whats-new/whats-new__2026-w36.md) |
| ``/subtask`` | session 內的分叉子代理（原 /fork 的舊義） | [whats-new/2026-w29](08-whats-new/whats-new__2026-w29.md) |
| ``/team-onboarding`` | 把你的 Claude Code 用法打包成新人指南 | [whats-new/2026-w15](08-whats-new/whats-new__2026-w15.md) |
| ``@session`` | 在提示用 @ 提及另一個 Claude session 名稱並用 SendMessage 傳訊 | [whats-new/2026-w33](08-whats-new/whats-new__2026-w33.md) |
| ``alwaysLoad`` | MCP 伺服器設定，讓其全部工具不被 tool search 延遲載入 | [whats-new/2026-w18](08-whats-new/whats-new__2026-w18.md) |
| ``classifyAllShell`` | 讓所有 shell 命令都過 auto mode 分類器 | [whats-new/2026-w26](08-whats-new/whats-new__2026-w26.md) |
| ``context: fork`` | skill frontmatter：在分叉子代理中執行 | [whats-new/2026-w30](08-whats-new/whats-new__2026-w30.md) |
| ``crossSessionInbound`` | 設定是否接受他 session 訊息（accept/hold/refuse） | [whats-new/2026-w32](08-whats-new/whats-new__2026-w32.md) |
| ``DirectoryAdded` hook` | `/add-dir` 註冊新工作目錄後觸發的 hook | [whats-new/2026-w30](08-whats-new/whats-new__2026-w30.md) |
| ``maxEffortLevel`` | 限制努力等級上限的設定 | [whats-new/2026-w37](08-whats-new/whats-new__2026-w37.md) |
| ``MessageDisplay` hook` | 轉換或隱藏助手訊息顯示文字的 hook 事件 | [whats-new/2026-w22](08-whats-new/whats-new__2026-w22.md) |
| ``notify_when_idle`` | SendMessage 參數：請對方 session 閒置時回報一次 | [whats-new/2026-w34](08-whats-new/whats-new__2026-w34.md) |
| ``PreModelSwitch` hook` | 模型切換前觸發，可阻擋 | [whats-new/2026-w36](08-whats-new/whats-new__2026-w36.md) |
| ``sandbox.credentials`` | 阻止沙箱化命令讀憑證檔與祕密環境變數 | [whats-new/2026-w26](08-whats-new/whats-new__2026-w26.md) |
| ``SendFeedback`` | Claude 自行草擬回饋報告的工具 | [whats-new/2026-w35](08-whats-new/whats-new__2026-w35.md) |
| ``Tool(param:value)`` | 權限規則依工具輸入參數比對的語法 | [whats-new/2026-w25](08-whats-new/whats-new__2026-w25.md) |
| ``ultracode`` | 動態 workflows 的提示觸發關鍵字（原為 workflow） | [whats-new/2026-w23](08-whats-new/whats-new__2026-w23.md) |
| ``updatedToolOutput`` | PostToolUse hook 可替換任何工具的輸出 | [whats-new/2026-w18](08-whats-new/whats-new__2026-w18.md) |
| ``worktree.baseRef`` | 新 worktree 的分支基準設定 | [whats-new/2026-w19](08-whats-new/whats-new__2026-w19.md) |
| `additionalContext` | hook 往 Claude 上下文塞的文字（上限 10,000 字元） | [hooks](06-reference/hooks.md) |
| `advisor tool` | 顧問工具：伺服器端第二個較強模型，在決策點被主模型諮詢 | [advisor](05-configuration/advisor.md) |
| `agent harness` | 代理工具層：包在模型外、提供工具並管理 context 的那一層 | [how-claude-code-works](01-getting-started/how-claude-code-works.md) |
| `agent hook` | 啟動多輪子代理驗證的 hook（實驗） | [hooks-guide](02-build/hooks-guide.md) |
| `Agent SDK` | 把 Claude Code 當函式庫嵌進自己程式的套件 | [agent-sdk/overview](07-agent-sdk/agent-sdk__overview.md) |
| `agent team` | 由 lead 與多個隊友 session 組成、共享任務清單的團隊（實驗） | [agent-teams](02-build/agent-teams.md) |
| `Agent teams` | 多個獨立工作階段協作 | [glossary](06-reference/glossary.md) |
| `agent view` | claude agents 開啟的背景 session 總覽畫面（研究預覽） | [agent-view](02-build/agent-view.md)、[whats-new/2026-w20](08-whats-new/whats-new__2026-w20.md) |
| `agent 檢視` | claude agents 監控多個背景工作階段 | [cli-reference](06-reference/cli-reference.md) |
| `AgentDefinition` | SDK 內定義子代理的設定物件 | [agent-sdk/subagents](07-agent-sdk/agent-sdk__subagents.md) |
| `Agentic coding` | AI 自主讀檔跑命令改程式 | [glossary](06-reference/glossary.md) |
| `Agentic harness` | 把模型變編碼代理的工具＋上下文＋執行環境 | [glossary](06-reference/glossary.md) |
| `agentic loop` | 代理迴圈：Claude 反覆「看→做→驗」直到任務完成 | [how-claude-code-works](01-getting-started/how-claude-code-works.md) |
| `Agentic loop` | 蒐集上下文→行動→驗證循環 | [glossary](06-reference/glossary.md) |
| `AGENTS.md` | 其他編碼 agent 通用的指令檔，無 CLAUDE.md 時預設改讀它（v2.1.277+） | [glossary](06-reference/glossary.md)、[memory](01-getting-started/memory.md) |
| `allowManagedModsOnly` | 只允許組織自家 mod 的防護選項 | [plugins/mods/admin](03-plugins/plugins__mods__admin.md) |
| `alternate screen buffer` | 終端的替代螢幕緩衝區 | [fullscreen](05-configuration/fullscreen.md) |
| `Always-on cost` | plugin 每個 session 固定增加的 token 數 | [plugins/measure](03-plugins/plugins__measure.md) |
| `apiKeyHelper` | 回傳 API 金鑰的 shell 腳本設定，用於輪替/保管庫憑證 | [authentication](04-administration/authentication.md) |
| `args` | 保存的工作流程接收呼叫輸入的全域變數 | [workflows](02-build/workflows.md) |
| `Artifact` | 發佈到 claude.ai 的私人互動網頁 | [glossary](06-reference/glossary.md) |
| `Artifacts` | Claude Code 發佈的即時可分享頁面 | [whats-new/2026-w25](08-whats-new/whats-new__2026-w25.md) |
| `artifact（成品）` | 從 session 發佈的自包含互動網頁 | [artifacts](02-build/artifacts.md) |
| `asyncRewake` | 背景 hook 以 exit 2 喚醒 Claude | [hooks](06-reference/hooks.md) |
| `auto memory` | 自動記憶：Claude 自己寫、跨 session 累積的筆記 | [memory](01-getting-started/memory.md) |
| `Auto memory` | Claude 自己寫的筆記，存 ~/.claude/projects/ | [glossary](06-reference/glossary.md) |
| `auto mode` | 自動模式：不問例行權限，改由背景分類器模型逐一審查動作 | [permission-modes](05-configuration/permission-modes.md)、[whats-new/2026-w13](08-whats-new/whats-new__2026-w13.md) |
| `Auto mode` | 分類器模型代審動作的權限模式 | [glossary](06-reference/glossary.md) |
| `auto mode classifier` | 替你審查工具呼叫並擋掉不安全操作的另一個模型 | [auto-mode-config](04-administration/auto-mode-config.md) |
| `auto-allow mode` | 沙箱內執行的命令自動核准 | [sandboxing](05-configuration/sandboxing.md) |
| `auto-compact window` | 上下文填到多滿才自動壓縮 | [model-config](05-configuration/model-config.md) |
| `autocompact thrashing` | 自動壓縮成功卻立刻被檔案／工具輸出再填滿的循環 | [troubleshooting](02-build/troubleshooting.md) |
| `BAA` | 醫療資料用的業務夥伴協議 | [legal-and-compliance](06-reference/legal-and-compliance.md) |
| `background session` | 背景工作階段：脫離終端機持續執行，可 `claude attach` | [sessions](01-getting-started/sessions.md) |
| `background subagent` | 子代理預設背景執行、不阻塞主對話 | [whats-new/2026-w27](08-whats-new/whats-new__2026-w27.md) |
| `band` | 提示上方所有 mod 共享的橫條 | [plugins/mods/interface](03-plugins/plugins__mods__interface.md) |
| `Bare mode` | --bare 最簡啟動 | [glossary](06-reference/glossary.md) |
| `baseline arm` | 不載 plugin 的對照組，用來算 plugin 增益Δ | [plugin-evals](03-plugins/plugin-evals.md) |
| `bundle plugin` | 只含依賴清單、用來一次裝一組 plugin 的 plugin | [plugins/dependencies](03-plugins/plugins__dependencies.md) |
| `bundled skill` | 隨附的提示詞型劇本指令 | [commands](06-reference/commands.md) |
| `Bundled skills` | 隨附提示型劇本 | [glossary](06-reference/glossary.md) |
| `byte watchdog` | 網路層沒位元組到達（含 SSE ping）就中止串流的計時器 | [network-config](04-administration/network-config.md) |
| `cache TTL` | 快取存活時間，5 分鐘或 1 小時 | [prompt-caching](01-getting-started/prompt-caching.md) |
| `cache_read_input_tokens` | 從 prompt cache 讀入的 token 數 | [agent-sdk/cost-tracking](07-agent-sdk/agent-sdk__cost-tracking.md) |
| `canUseTool` | SDK 專屬的工具核准回呼函式 | [agent-sdk/user-input](07-agent-sdk/agent-sdk__user-input.md) |
| `canUseTool shadowed` | 回呼因更早步驟已核准而永遠不會被呼叫的狀況 | [agent-sdk/permissions](07-agent-sdk/agent-sdk__permissions.md) |
| `channel` | 可雙向的 MCP 伺服器，把外部事件推到執行中的 session | [channels](02-build/channels.md)、[channels-reference](06-reference/channels-reference.md)、[plugins/components](03-plugins/plugins__components.md) |
| `Channel` | 推事件進工作階段的 MCP 伺服器 | [glossary](06-reference/glossary.md) |
| `channel memory` | 按頻道保留、依地點跟隨的記憶 | [claude-tag](01-getting-started/claude-tag.md) |
| `Channels` | 把 Telegram/Discord 或自家伺服器事件推進會話的機制 | [platforms](01-getting-started/platforms.md) |
| `check run` | PR 上名為 Claude Code Review 的檢查項，列出發現 | [code-review](01-getting-started/code-review.md) |
| `checkpoint` | 檢查點：編輯前的檔案快照，可回溯但不含 Bash 改的檔 | [agent-sdk/file-checkpointing](07-agent-sdk/agent-sdk__file-checkpointing.md)、[checkpointing](06-reference/checkpointing.md)、[how-claude-code-works](01-getting-started/how-claude-code-works.md) |
| `Checkpoint` | 每提示詞前的還原點 | [glossary](06-reference/glossary.md) |
| `chord` | 和弦：先按一組鍵再按下一組的多步快捷鍵 | [keybindings](05-configuration/keybindings.md) |
| `classifier` | 分類器：審查動作是否超出你的請求範圍的獨立模型 | [permission-modes](05-configuration/permission-modes.md) |
| `Claude apps gateway` | Anthropic 提供、內建於 claude 二進位的自託管閘道 | [claude-apps-gateway](04-administration/claude-apps-gateway.md) |
| `claude doctor` | shell 內執行的安裝與設定唯讀診斷命令 | [troubleshoot-install](02-build/troubleshoot-install.md) |
| `Claude GitHub App` | 需安裝的 GitHub App，權限比審查實際用的更廣 | [code-review-setup](01-getting-started/code-review-setup.md) |
| `Claude in Chrome` | 官方瀏覽器擴充功能，供 Claude 操作你已登入的分頁 | [chrome](01-getting-started/chrome.md) |
| `Claude Security plugin` | 會話內多 agent 漏洞掃描外掛 | [claude-security](01-getting-started/claude-security.md) |
| `Claude Tag` | 組織共享身分的新 Slack 整合，取代此舊版於 Team/Enterprise | [claude-tag](01-getting-started/claude-tag.md)、[slack](01-getting-started/slack.md) |
| `claude-code-action` | 官方 GitHub Action，在 workflow 內跑 Claude Code | [github-actions](01-getting-started/github-actions.md) |
| `claude-code-hint` | CLI 輸出的標籤，讓 Claude Code 推薦安裝 plugin | [plugins/cli-hints](03-plugins/plugins__cli-hints.md) |
| `CLAUDE.local.md` | 個人專案偏好檔，與 CLAUDE.md 同載入，需自行 gitignore | [memory](01-getting-started/memory.md) |
| `CLAUDE.md` | 寫給 Claude 的持久指示 | [glossary](06-reference/glossary.md) |
| `CLAUDE_JOB_DIR` | 背景 session 自己可寫報告檔的目錄環境變數 | [agent-view](02-build/agent-view.md) |
| `CLAUDE_PLUGIN_DATA` | 更新後仍保留的 plugin 持久資料目錄 | [plugins/components](03-plugins/plugins__components.md) |
| `claudeMdExcludes` | 設定鍵：以 glob 排除特定 CLAUDE.md/規則檔 | [large-codebases](02-build/large-codebases.md)、[memory](01-getting-started/memory.md) |
| `ClaudeSDKClient` | Python 持續對話用的客戶端類別 | [agent-sdk/python](07-agent-sdk/agent-sdk__python.md) |
| `CLIConnectionError` | SDK 連不上或啟動不了 CLI 子程序的錯誤 | [agent-sdk/troubleshooting](07-agent-sdk/agent-sdk__troubleshooting.md) |
| `Client` | 在 mod 內嵌自訂 UI 模組的元素 | [plugins/mods/gallery](03-plugins/plugins__mods__gallery.md) |
| `cloud environment` | 雲端環境：雲端工作階段的網路、環境變數、設定指令碼組合 | [cloud-environments](05-configuration/cloud-environments.md) |
| `Cloud session` | 跑在雲端的工作階段 | [glossary](06-reference/glossary.md) |
| `code intelligence plugin` | 把 LSP 接進 Claude Code 的 plugin | [plugins/code-intelligence](03-plugins/plugins__code-intelligence.md) |
| `Code Review` | Anthropic 基礎設施上對 PR 自動審查的託管服務 | [code-review](01-getting-started/code-review.md) |
| `Code review declined` | 因預算等原因審查未執行的狀態 | [code-review-troubleshooting](01-getting-started/code-review-troubleshooting.md) |
| `Code 標籤` | Claude 手機 app 中進入 Code 會話的入口 | [mobile](01-getting-started/mobile.md) |
| `Command` | 輸入 /name 叫用的可重用指示 | [glossary](06-reference/glossary.md) |
| `command source` | 由 Claude Code 在使用者機器執行命令產生 plugin 目錄的來源 | [plugins/host-marketplace](03-plugins/plugins__host-marketplace.md)、[plugins/marketplace-reference](03-plugins/plugins__marketplace-reference.md) |
| `community marketplace` | 第三方作者提交的目錄 claude-community | [plugins/anthropic-marketplaces](03-plugins/plugins__anthropic-marketplaces.md) |
| `compact_boundary` | 自動壓縮發生時串流中的系統訊息 | [agent-sdk/agent-loop](07-agent-sdk/agent-sdk__agent-loop.md) |
| `compaction` | 壓縮：把舊對話換成結構化摘要以騰出空間 | [context-window](01-getting-started/context-window.md) |
| `Compaction` | 上下文將滿時自動摘要 | [glossary](06-reference/glossary.md) |
| `computer-use` | 內建 MCP 伺服器，提供螢幕截圖與點擊鍵盤控制 | [computer-use](01-getting-started/computer-use.md) |
| `ConfigChange hook` | 設定檔變更時觸發的 hook 事件 | [settings](05-configuration/settings.md) |
| `Connector` | 加在 claude.ai 帳戶的 MCP 伺服器 | [glossary](06-reference/glossary.md) |
| `Context cost` | 官方市集 plugin 安裝前顯示的 token 估計 | [plugins/measure](03-plugins/plugins__measure.md) |
| `Context window` | 工作階段的工作記憶 | [glossary](06-reference/glossary.md) |
| `context: fork` | 讓 skill 在隔離子代理中執行 | [skills](02-build/skills.md) |
| `continueAfterReload` | VS Code 重載後自動重開對話的設定 | [vs-code](01-getting-started/vs-code.md) |
| `contribution metrics` | 把合併 PR 的程式行對應到 Claude Code 工作階段的歸因指標 | [analytics](04-administration/analytics.md) |
| `control matrix` | 列出各政策金鑰能做與不能做之事的表 | [plugins/org](03-plugins/plugins__org.md) |
| `Cookbook` | Anthropic 的配方筆記本集合 | [agent-sdk/examples](07-agent-sdk/agent-sdk__examples.md) |
| `Cowork` | Desktop 內負責 Dispatch 與長時間代理工作的部分 | [desktop](01-getting-started/desktop.md) |
| `credential masking` | 遮罩憑證：讓沙箱內命令拿不到真實密鑰 | [sandboxing](05-configuration/sandboxing.md) |
| `critical path` | 關鍵路徑：如 `/`、`~` 的刪除，任何模式都不放行 | [permission-modes](05-configuration/permission-modes.md) |
| `cross-session messaging` | 跨工作階段傳訊：一個 session 的 Claude 傳訊息給另一個 session | [cross-session-messaging](02-build/cross-session-messaging.md)、[features-overview](01-getting-started/features-overview.md)、[whats-new/2026-w32](08-whats-new/whats-new__2026-w32.md) |
| `customization lockdown` | `strictPluginOnlyCustomization`：skills/agents/hooks/MCP 只能來自外掛或受管設定 | [admin-setup](04-administration/admin-setup.md) |
| `deep link` | 自訂 URL scheme，點擊後在本機啟動 Claude Code | [deep-links](02-build/deep-links.md) |
| `defaultEnabled` | manifest 欄位，false 表示裝了也預設關閉 | [plugins/install](03-plugins/plugins__install.md) |
| `defer` | PreToolUse 決策值，-p 會話在工具呼叫處暫停待外部決定後 --resume | [hooks](06-reference/hooks.md)、[whats-new/2026-w14](08-whats-new/whats-new__2026-w14.md) |
| `dependency` | 此 plugin 運作所需、須同時啟用的其他 plugin | [plugins/dependencies](03-plugins/plugins__dependencies.md) |
| `dev container` | 用 devcontainer.json 定義、可在本機或 Codespaces 重現的容器開發環境 | [devcontainer](04-administration/devcontainer.md) |
| `directory` | claude.ai 上供 claude.ai/Cowork 使用者瀏覽的 plugin 目錄 | [plugins/publish](03-plugins/plugins__publish.md) |
| `directory listing fields` | icon、documentationUrl 等僅供目錄用的欄位 | [plugins/manifest-reference](03-plugins/plugins__manifest-reference.md) |
| `disableDeepLinkRegistration` | 阻止註冊 URL 處理程式的設定 | [deep-links](02-build/deep-links.md) |
| `Dispatch` | 從手機 Claude app 傳任務給 Desktop，由它決定怎麼跑 | [glossary](06-reference/glossary.md)、[platforms](01-getting-started/platforms.md) |
| `dontAsk mode` | 一律拒絕未預先核准的操作，不提示 | [permission-modes](05-configuration/permission-modes.md) |
| `dynamic workflow` | 動態工作流程：Claude 寫腳本在背景跑多個 subagent 回傳單一結果 | [features-overview](01-getting-started/features-overview.md)、[workflows](02-build/workflows.md) |
| `dynamic workflows` | Claude 為任務寫的協調腳本，背景驅動大量子代理 | [whats-new/2026-w22](08-whats-new/whats-new__2026-w22.md) |
| `effort level` | 推理力度等級，越高越慢越貴越聰明 | [model-config](05-configuration/model-config.md) |
| `Effort level` | 自適應推理深淺設定 | [glossary](06-reference/glossary.md) |
| `enableArtifact` | 關閉／開啟 artifact 功能的設定鍵 | [artifacts](02-build/artifacts.md) |
| `env 區塊` | settings.json 內替工作階段設環境變數的欄位 | [env-vars](06-reference/env-vars.md) |
| `environment caching` | 環境快取：把設定指令碼跑完的檔案系統快照重用 | [cloud-environments](05-configuration/cloud-environments.md) |
| `eval suite` | 一組針對 plugin 的測試案例 | [plugin-evals](03-plugins/plugin-evals.md) |
| `exclusive control` | 部署 `managed-mcp.json` 後，只有受管集合能用，使用者無法新增 | [managed-mcp](04-administration/managed-mcp.md) |
| `extended context` | 延伸上下文：1M token 視窗 | [model-config](05-configuration/model-config.md) |
| `Extended thinking` | 回應前可見的逐步推理 | [glossary](06-reference/glossary.md) |
| `fail closed` | hook 失敗時預設拒絕而非放行 | [plugins/mods/events](03-plugins/plugins__mods__events.md) |
| `fallbackModel` | 主模型不可用時自動切換的備援模型 | [agent-sdk/configuration](07-agent-sdk/agent-sdk__configuration.md) |
| `fast mode` | 快速模式：Opus 的高速付費配置，非另一個模型 | [fast-mode](05-configuration/fast-mode.md) |
| `fire URL` | API 觸發的專屬端點，含任務專屬 token | [routines](01-getting-started/routines.md) |
| `first-wins / merge` | 多個受管來源並存時的處理：只取最高一個，或全部合併 | [managed-settings](04-administration/managed-settings.md) |
| `Focus view` | 隱藏對話中工具活動的檢視模式 | [vs-code](01-getting-started/vs-code.md) |
| `fork` | 複製既有 session 歷史成新 session，原本不變 | [agent-sdk/sessions](07-agent-sdk/agent-sdk__sessions.md)、[sessions](01-getting-started/sessions.md) |
| `fork mode` | 子代理繼承整份對話與快取的分叉模式 | [whats-new/2026-w33](08-whats-new/whats-new__2026-w33.md) |
| `fork subagent` | 複製目前對話內容再開始的子代理 | [agent-sdk/subagents](07-agent-sdk/agent-sdk__subagents.md)、[whats-new/2026-w17](08-whats-new/whats-new__2026-w17.md) |
| `forked subagent` | 分叉出去、擁有獨立 context 視窗的背景子代理 | [code-review-local](01-getting-started/code-review-local.md) |
| `fork（/subtask）` | 繼承目前整段對話的子代理，放棄輸入隔離換取上下文 | [sub-agents](02-build/sub-agents.md) |
| `Frontmatter` | Markdown 頂端 YAML 區 | [glossary](06-reference/glossary.md) |
| `fullscreen rendering` | 全螢幕渲染：像 vim 那樣接管終端繪製，不是最大化視窗 | [fullscreen](05-configuration/fullscreen.md) |
| `gateway` | 組織自管、位於 Claude Code 與模型提供者之間的代理 | [gateways](04-administration/gateways.md) |
| `gateway hint headers` | Claude Code 附的路由/排程提示標頭，供閘道分類請求 | [llm-gateway-protocol](04-administration/llm-gateway-protocol.md) |
| `GHES` | GitHub Enterprise Server，自管的 GitHub 執行個體 | [github-enterprise-server](01-getting-started/github-enterprise-server.md) |
| `git worktree` | 同 repo 另一個獨立工作目錄＋分支 | [worktrees](02-build/worktrees.md) |
| `git-subdir` | 以 sparse checkout 取 git repo 子目錄的來源 | [plugins/marketplace-reference](03-plugins/plugins__marketplace-reference.md) |
| `GitHub App manifest` | 預填權限的 App 建立流程 | [github-enterprise-server](01-getting-started/github-enterprise-server.md) |
| `grader` | 對 Claude 產出評分的規則(regex、tool_used、llm 等) | [plugin-evals](03-plugins/plugin-evals.md) |
| `gVisor` | 在使用者空間攔截系統呼叫的容器隔離層 | [agent-sdk/secure-deployment](07-agent-sdk/agent-sdk__secure-deployment.md) |
| `hard_deny` | auto mode 中無論允許例外都一律封鎖的規則 | [whats-new/2026-w19](08-whats-new/whats-new__2026-w19.md) |
| `hard_deny / soft_deny` | 硬阻擋（不可覆蓋）與軟阻擋（使用者意圖或 allow 可放行） | [auto-mode-config](04-administration/auto-mode-config.md) |
| `headersHelper` | 印出短期憑證標頭的命令，用於受保護下載 | [plugins/host-marketplace](03-plugins/plugins__host-marketplace.md) |
| `HIPAA configuration` | Enterprise 方案的組織設定，用於處理 PHI 並簽有 BAA | [hipaa-setup](04-administration/hipaa-setup.md) |
| `hold` | 入站訊息擱置待使用者核准 | [cross-session-messaging](02-build/cross-session-messaging.md) |
| `hold-to-record` | 按住錄音：按著鍵說話、放開即停 | [voice-dictation](05-configuration/voice-dictation.md) |
| `hook` | 在生命週期節點確定性執行的使用者定義處理 | [hooks-guide](02-build/hooks-guide.md) |
| `Hook` | 生命週期特定點自動執行的處理程式 | [glossary](06-reference/glossary.md) |
| `hook `if` field` | hook 條件欄位，只在符合權限規則語法時才啟動 | [whats-new/2026-w13](08-whats-new/whats-new__2026-w13.md) |
| `hook `type: mcp_tool`` | hook 直接呼叫已連線 MCP 工具，免開子程序 | [whats-new/2026-w17](08-whats-new/whats-new__2026-w17.md) |
| `hook callback` | 註冊在選項裡的程式化函式，非 shell 命令 | [agent-sdk/hooks](07-agent-sdk/agent-sdk__hooks.md) |
| `hook event / matcher group / handler` | 時間點／篩選條件／實際執行者三層結構 | [hooks](06-reference/hooks.md) |
| `hook exec form `args`` | 不經 shell 直接 spawn 命令的 hook 寫法 | [whats-new/2026-w20](08-whats-new/whats-new__2026-w20.md) |
| `hook module` | 匯出 register(on) 的 JS/TS 檔，註冊事件處理函式 | [plugins/mods/overview](03-plugins/plugins__mods__overview.md) |
| `hooks worker` | 執行 mod hook 的獨立工作行程 | [plugins/mods/troubleshoot](03-plugins/plugins__mods__troubleshoot.md) |
| `hot reload` | 儲存或回合結束時重新載入 mod，不必重開 session | [plugins/mods/create](03-plugins/plugins__mods__create.md) |
| `ide MCP server` | 外掛開的本機 MCP，供開 diff、讀選取與診斷，不顯示於 /mcp | [jetbrains](01-getting-started/jetbrains.md) |
| `idleCompaction` | 閒置壓縮：人離開約一小時、提示快取過期前，先把長對話壓成摘要 | [settings-reference](05-configuration/settings-reference.md) |
| `IdP group policy` | 依 OIDC token 的 groups 宣告套用不同受管設定與模型允許清單 | [claude-apps-gateway](04-administration/claude-apps-gateway.md) |
| `in-place plugin` | 不複製進快取、直接從原位置載入的 plugin | [plugins/loading](03-plugins/plugins__loading.md) |
| `in-process MCP server` | 與應用同程序執行、不需獨立子程序的 MCP 伺服器 | [agent-sdk/custom-tools](07-agent-sdk/agent-sdk__custom-tools.md) |
| `inference profile` | Bedrock 的跨區域/應用程式推論設定檔，決定實際呼叫的模型 ID | [amazon-bedrock](04-administration/amazon-bedrock.md) |
| `installed_plugins.json` | 記錄已安裝 plugin 的 scope、路徑與版本的檔案 | [plugins/loading](03-plugins/plugins__loading.md) |
| `Instruction file not loaded` | 記憶檔因 Read 拒絕規則等原因未載入的通知 | [errors](02-build/errors.md) |
| `IRSA` | EKS 上讓 Pod 取得 IAM 角色的機制 | [claude-apps-gateway-on-aws](04-administration/claude-apps-gateway-on-aws.md) |
| `keep-coding-instructions` | 保留內建寫程式指令的 frontmatter 開關 | [output-styles](05-configuration/output-styles.md) |
| `keybinding context` | 綁定的作用範圍，例如 Chat | [keybindings](05-configuration/keybindings.md) |
| `known_marketplaces.json` | 記錄已提取 marketplace 的檔案 | [plugins/loading](03-plugins/plugins__loading.md) |
| `KVM` | Linux 硬體虛擬化，Cowork 用它跑 VM | [desktop-linux](01-getting-started/desktop-linux.md) |
| `launch.json` | Desktop 預覽伺服器啟動設定檔（.claude/launch.json） | [desktop](01-getting-started/desktop.md) |
| `layered policy_mode` | 多群組政策疊加套用，而非只取第一個符合者 | [claude-apps-gateway-config](04-administration/claude-apps-gateway-config.md) |
| `lead／teammate` | 主管 session／被生成的獨立 Claude Code 實例 | [agent-teams](02-build/agent-teams.md) |
| `lifecycle hook` | 生命週期 hook：runner 端階段腳本，不同於會話內的 Claude Code hook | [self-hosted-environments-configuration](05-configuration/self-hosted-environments-configuration.md) |
| `local 範圍` | 預設；僅你、僅此專案，存 ~/.claude.json | [mcp-quickstart](02-build/mcp-quickstart.md) |
| `loop.md` | 取代內建維護提示的自訂預設迴圈提示檔 | [scheduled-tasks](02-build/scheduled-tasks.md) |
| `LSP` | Language Server Protocol，語言伺服器協定，提供診斷與跳定義 | [plugins/code-intelligence](03-plugins/plugins__code-intelligence.md) |
| `Managed Agents` | Anthropic 雲端託管代理迴圈的服務 | [agent-sdk/overview](07-agent-sdk/agent-sdk__overview.md) |
| `managed policy CLAUDE.md` | 組織層 CLAUDE.md，只是指引、不被程式強制 | [admin-setup](04-administration/admin-setup.md) |
| `managed settings` | 受管設定：組織部署、你的檔案蓋不掉的最高層設定 | [plugins/org](03-plugins/plugins__org.md)、[settings](05-configuration/settings.md) |
| `Managed settings` | IT 強制套用的組織設定 | [glossary](06-reference/glossary.md) |
| `managed-settings.d/` | 管理設定的分片目錄，讓多團隊各自放政策片段 | [whats-new/2026-w13](08-whats-new/whats-new__2026-w13.md) |
| `managed-settings.json` | 企業強制設定，使用者設定與 `--settings` 都不能蓋過（少數例外） | [claude-directory](01-getting-started/claude-directory.md) |
| `manifest` | plugin.json，替 plugin 命名並放中繼資料 | [plugins/overview](03-plugins/plugins__overview.md) |
| `Mantle` | Bedrock 上以原生 Anthropic API 形狀提供 Claude 的端點 | [amazon-bedrock](04-administration/amazon-bedrock.md) |
| `Manual 權限模式` | 原 default 權限模式的新名稱 | [whats-new/2026-w27](08-whats-new/whats-new__2026-w27.md) |
| `marketplace` | 列出 plugin 與取得位置的目錄檔(marketplace.json)，不是商店 | [plugins/overview](03-plugins/plugins__overview.md) |
| `marketplace root` | 含 .claude-plugin/ 的目錄，相對來源由此解析 | [plugins/create-marketplace](03-plugins/plugins__create-marketplace.md) |
| `masked variable` | GitLab 中遮罩日誌的 CI/CD 變數 | [gitlab-ci-cd](01-getting-started/gitlab-ci-cd.md) |
| `match: {} 基礎層` | 對所有已驗證使用者生效的預設政策，其他政策從它繼承 | [claude-apps-gateway-config](04-administration/claude-apps-gateway-config.md) |
| `matcher` | 以 \| 或 , 分隔工具名稱過濾 hook 觸發 | [hooks-guide](02-build/hooks-guide.md) |
| `MCP` | Model Context Protocol，連接外部工具的開放標準 | [mcp](02-build/mcp.md) |
| `MCP (Model Context Protocol)` | 連接外部資料／服務的開放標準 | [glossary](06-reference/glossary.md) |
| `MCP server` | 提供工具／提示／資源的程式 | [glossary](06-reference/glossary.md) |
| `MCP Tool Search` | 延遲載入 MCP 工具定義以省 context | [glossary](06-reference/glossary.md) |
| `MCP 任務` | 伺服器端長時間工作，用 MCP tasks 擴充追蹤 | [mcp](02-build/mcp.md) |
| `MCP 工具搜尋` | 隱藏 MCP 工具定義、每回合只載入需要者以省 context | [agent-sdk/mcp](07-agent-sdk/agent-sdk__mcp.md) |
| `memory 欄位（user/project/local）` | 給子代理的持久目錄，跨對話累積知識 | [sub-agents](02-build/sub-agents.md) |
| `middleware chain` | hook 以 next 串成的處理鏈，最後到達 Claude Code 自身行為 | [plugins/mods/events](03-plugins/plugins__mods__events.md) |
| `mirror_error` | 鏡像寫入失敗時串流中的系統訊息 | [agent-sdk/session-storage](07-agent-sdk/agent-sdk__session-storage.md) |
| `mock` | 假 MCP 伺服器回應，讓測試不連真服務 | [plugin-evals](03-plugins/plugin-evals.md) |
| `mod` | 帶 hook 模組、能在 Claude Code 內改介面與行為的 plugin | [permissions](05-configuration/permissions.md)、[plugins/mods/overview](03-plugins/plugins__mods__overview.md)、[plugins/overview](03-plugins/plugins__overview.md) |
| `modelSettings` | 每個模型各自存一份 effort 等級的設定 | [settings-reference](05-configuration/settings-reference.md) |
| `modelUsage` | 結果訊息中按模型拆分的 token 與成本 | [agent-sdk/cost-tracking](07-agent-sdk/agent-sdk__cost-tracking.md) |
| `mods API` | hook 收到的 `$`，提供 ui/command/tool/model/fs/process 等方法 | [plugins/mods/overview](03-plugins/plugins__mods__overview.md) |
| `monitor` | 隨 session 常駐的背景命令，輸出以通知進 Claude | [plugins/components](03-plugins/plugins__components.md) |
| `Monitor` | 背景跑命令並把每行輸出餵回 Claude | [tools-reference](06-reference/tools-reference.md) |
| `Monitor tool` | 開背景監看並把事件當訊息串流進對話的內建工具 | [whats-new/2026-w15](08-whats-new/whats-new__2026-w15.md) |
| `Nit` | 低嚴重度、不擋合併的小問題 | [code-review-customize](01-getting-started/code-review-customize.md) |
| `Non-interactive mode` | -p 單次執行（舊稱 headless） | [glossary](06-reference/glossary.md) |
| `not cached` | 已啟用 plugin 在磁碟快取找不到時的錯誤狀態 | [plugins/troubleshooting](03-plugins/plugins__troubleshooting.md) |
| `notify_when_idle` | 訂閱目標 session 下次閒置時通知的 SendMessage 輸入 | [cross-session-messaging](02-build/cross-session-messaging.md) |
| `official marketplace` | Anthropic 維護並預設自動註冊的 plugin 目錄 | [plugins/anthropic-marketplaces](03-plugins/plugins__anthropic-marketplaces.md) |
| `omitClaudeMd` | 啟動時不載入 CLAUDE.md 的子代理選項 | [sub-agents](02-build/sub-agents.md) |
| `onFailure` | callback 失敗時選擇放行或阻擋的設定 | [agent-sdk/hooks](07-agent-sdk/agent-sdk__hooks.md) |
| `Only on this computer` | 把任務限制為本機而非雲端的開關 | [desktop-scheduled-tasks](01-getting-started/desktop-scheduled-tasks.md) |
| `opusplan` | plan mode 用 Opus、執行用 Sonnet 的模型設定，每次切換都是一次模型切換 | [model-config](05-configuration/model-config.md)、[prompt-caching](01-getting-started/prompt-caching.md) |
| `orchestrator` | 協調器：依需求自動擴縮 runner 的程序 | [self-hosted-environments](05-configuration/self-hosted-environments.md) |
| `OSC 8` | 終端機可點連結的逸出序列 | [statusline](05-configuration/statusline.md) |
| `OTLP` | OpenTelemetry Protocol，遙測傳輸協定（Claude Code 支援 grpc/http） | [agent-sdk/observability](07-agent-sdk/agent-sdk__observability.md)、[monitoring-usage](04-administration/monitoring-usage.md) |
| `output style` | 輸出風格：設定回應角色、語氣、格式的常駐指令，一次只有一個生效 | [features-overview](01-getting-started/features-overview.md)、[output-styles](05-configuration/output-styles.md) |
| `Output style` | 改變回應語氣格式的設定 | [glossary](06-reference/glossary.md) |
| `output style（輸出樣式）` | 存成 markdown 的角色/語氣/格式指令組 | [agent-sdk/modifying-system-prompts](07-agent-sdk/agent-sdk__modifying-system-prompts.md) |
| `Overview` | 一眼看所有執行緒與需你處理者的窗格 | [claude-projects](01-getting-started/claude-projects.md) |
| `pane` | 文字記錄旁或提示上方的 mod 側邊/內嵌面板 | [plugins/mods/interface](03-plugins/plugins__mods__interface.md) |
| `parent settings` | 嵌入主機（Desktop/IDE/SDK 用 `managedSettings`）傳進來的設定；有管理員來源時預設被忽略 | [managed-settings](04-administration/managed-settings.md) |
| `path-scoped rule` | 路徑範圍規則：frontmatter 有 `paths` 的 rule，碰到符合檔案才載入 | [memory](01-getting-started/memory.md) |
| `paths（skill）` | 限制只在處理符合 glob 的檔案時自動載入 | [skills](02-build/skills.md) |
| `Permission mode` | 基線批准行為 | [glossary](06-reference/glossary.md) |
| `permission relay` | channel 把權限提示轉發到聊天上批准的能力 | [channels](02-build/channels.md)、[channels-reference](06-reference/channels-reference.md) |
| `permission rule` | 權限規則：寫成 `Bash(git diff *)` 這種形式的允許／詢問／拒絕條目 | [permissions](05-configuration/permissions.md) |
| `Permission rule` | 依工具與參數允許／詢問／拒絕，deny→ask→allow | [glossary](06-reference/glossary.md) |
| `PermissionDenied hook` | auto mode 分類器拒絕時觸發，可回 retry 讓 Claude 換法 | [whats-new/2026-w14](08-whats-new/whats-new__2026-w14.md) |
| `Plan mode` | 只研究提議不改檔 | [glossary](06-reference/glossary.md) |
| `plugin` | 外掛：把 skill、hook、subagent、MCP 打包成可安裝單元 | [agent-sdk/plugins](07-agent-sdk/agent-sdk__plugins.md)、[features-overview](01-getting-started/features-overview.md)、[plugins/overview](03-plugins/plugins__overview.md) |
| `Plugin` | skills+hooks+subagents+MCP 套件 | [glossary](06-reference/glossary.md) |
| `plugin entry` | marketplace.json 中描述單一 plugin 與來源的物件 | [plugins/create-marketplace](03-plugins/plugins__create-marketplace.md) |
| `plugin eval` | 對 plugin 跑測試案例、評分並與無 plugin 基準比較 | [whats-new/2026-w37](08-whats-new/whats-new__2026-w37.md) |
| `plugin root` | plugin 自己的目錄，非 ~/.claude | [plugins/create](03-plugins/plugins__create.md) |
| `plugin-authoring` | 教 Claude 寫 mod 的內建 skill | [plugins/mods/create](03-plugins/plugins__mods__create.md) |
| `pluginRoot` | 裸名 plugin 來源解析的基底目錄 | [plugins/marketplace-reference](03-plugins/plugins__marketplace-reference.md) |
| `policy key` | 除 `wslInheritsWindowsSettings`、`managedSourcesBehavior` 外的任何設定鍵，才算該來源有提供政策 | [managed-settings](04-administration/managed-settings.md) |
| `policy mod` | 用 plugin.register 事件檢查並拒絕其他 mod 的組織 mod | [plugins/mods/admin](03-plugins/plugins__mods__admin.md) |
| `policyHelper` | 啟動時執行並輸出 `managedSettings` 物件的可執行檔，輸出取代其他受管來源 | [managed-settings](04-administration/managed-settings.md)、[settings-reference](05-configuration/settings-reference.md) |
| `Pre-existing` | 非此 PR 引入、既有程式碼的問題 | [code-review-pull-requests](01-getting-started/code-review-pull-requests.md) |
| `preset: claude_code` | 沿用 Claude Code CLI 那份完整 system prompt 的選項 | [agent-sdk/migration-guide](07-agent-sdk/agent-sdk__migration-guide.md) |
| `print mode` | -p 單次執行後退出 | [cli-reference](06-reference/cli-reference.md) |
| `process wrapper` | 強制所有衍生程序通過企業啟動器的設定 | [whats-new/2026-w29](08-whats-new/whats-new__2026-w29.md) |
| `process wrapper / launcher` | 包住 Claude Code 自己衍生程序的公司啟動腳本 | [corporate-launcher](04-administration/corporate-launcher.md) |
| `project` | 長期協調對話加其啟動的執行緒 | [claude-projects](01-getting-started/claude-projects.md) |
| `Project instructions` | 每個新執行緒都會收到的常設規則 | [claude-projects](01-getting-started/claude-projects.md) |
| `Project trust` | 載入專案設定前的信任對話框 | [glossary](06-reference/glossary.md) |
| `project 範圍` | .mcp.json，隨版控共享 | [mcp-quickstart](02-build/mcp-quickstart.md) |
| `prompt cache miss` | 快取已過期或失效，整段前綴需重新處理並重寫入快取 | [costs](04-administration/costs.md) |
| `Prompt injection` | 藏在內容中的敵對指令 | [glossary](06-reference/glossary.md) |
| `prompt prefix` | 前綴：每次請求開頭與快取比對的那段內容 | [prompt-caching](01-getting-started/prompt-caching.md) |
| `prompt.id` | UUID，連結同一提示觸發的所有事件 | [monitoring-usage](04-administration/monitoring-usage.md) |
| `protected paths` | 受保護路徑：寫入永遠要確認的目錄清單 | [permission-modes](05-configuration/permission-modes.md) |
| `query()` | SDK 的主入口，回傳訊息串流 | [agent-sdk/quickstart](07-agent-sdk/agent-sdk__quickstart.md) |
| `queued message` | 回應中先排隊稍後送的訊息 | [interactive-mode](06-reference/interactive-mode.md) |
| `Raster` | 以彩色儲存格網格繪圖的元素 | [plugins/mods/gallery](03-plugins/plugins__mods__gallery.md) |
| `Referenced file` | 壓縮後以路徑引用、不含內容的大檔顯示 | [context-window](01-getting-started/context-window.md) |
| `release channel` | 更新通道，latest 即時、stable 延遲約一週並跳過重大迴歸版 | [plugins/host-marketplace](03-plugins/plugins__host-marketplace.md)、[setup](04-administration/setup.md) |
| `release tag` | 格式 name--vX.Y.Z 的 git 標籤，供版本範圍解析 | [plugins/dependencies](03-plugins/plugins__dependencies.md) |
| `relevance` | marketplace 項目上的相關性規則，決定何時推薦該 plugin | [plugins/relevance](03-plugins/plugins__relevance.md) |
| `Remote Control` | 遠端視窗操作本機 Claude 會話，執行仍在你的機器 | [glossary](06-reference/glossary.md)、[remote-control](01-getting-started/remote-control.md) |
| `renames map` | marketplace.json 內舊名→新名的遷移對應 | [plugins/publish](03-plugins/plugins__publish.md) |
| `render site` | 介面上 mod 可介入繪製的位置 | [plugins/mods/interface](03-plugins/plugins__mods__interface.md) |
| `ReportFindings` | 以結構化清單回報審查發現 | [tools-reference](06-reference/tools-reference.md) |
| `ReportFindings 工具` | 宿主 app 用來接收審查發現清單的工具 | [code-review-local](01-getting-started/code-review-local.md) |
| `requiredMinimumVersion` | 管理員設定，版本不在範圍內的 client 啟動即退出 | [whats-new/2026-w23](08-whats-new/whats-new__2026-w23.md) |
| `restricted mode` | 啟動時不含任何可執行命令的工具與使用者／專案設定 | [whats-new/2026-w35](08-whats-new/whats-new__2026-w35.md) |
| `Review runs` | 每儲存庫設定何時觸發審查 | [code-review-setup](01-getting-started/code-review-setup.md) |
| `REVIEW.md` | Code Review 專用審查指令檔 | [code-review-customize](01-getting-started/code-review-customize.md) |
| `rollout switch` | Anthropic 遠端開關，可關閉已安裝 mod | [plugins/mods/troubleshoot](03-plugins/plugins__mods__troubleshoot.md) |
| `routine-fire-payload` | 包住 API text 並標示為不受信任資料的區塊 | [routines](01-getting-started/routines.md) |
| `routine/scheduled task` | 已存的提示詞+儲存庫+連接器，在雲端依觸發自動跑 | [routines](01-getting-started/routines.md) |
| `Routines` | 在雲端依排程或事件觸發的範本化 agent | [whats-new/2026-w16](08-whats-new/whats-new__2026-w16.md) |
| `Rules` | .claude/rules/ 模組化指示 | [glossary](06-reference/glossary.md) |
| `Run now` | 立即執行一次任務並藉此預先核准權限 | [desktop-scheduled-tasks](01-getting-started/desktop-scheduled-tasks.md) |
| `runner` | 執行器：認領並執行工作階段的程式，概念同 CI runner | [self-hosted-environments](05-configuration/self-hosted-environments.md) |
| `safe mode` | 停用一切自訂項目的乾淨啟動模式 | [whats-new/2026-w24](08-whats-new/whats-new__2026-w24.md) |
| `sandbox runtime` | 把整個 Claude Code 行程（不只 Bash）關進沙箱的獨立執行方式 | [sandbox-environments](05-configuration/sandbox-environments.md) |
| `sandbox-runtime` | Anthropic 的 OS 級檔案系統/網路限制工具 | [agent-sdk/secure-deployment](07-agent-sdk/agent-sdk__secure-deployment.md) |
| `sandboxed Bash tool` | 沙箱化 Bash 工具：把 shell 命令關進 OS 層級邊界 | [sandboxing](05-configuration/sandboxing.md) |
| `ScheduleWakeup` | 動態節奏迴圈用來預約下次喚醒／停止的工具 | [scheduled-tasks](02-build/scheduled-tasks.md)、[tools-reference](06-reference/tools-reference.md) |
| `scope` | 安裝範圍：誰能啟用這個 plugin | [plugins/install](03-plugins/plugins__install.md) |
| `scratchpad` | 暫存簿：每個 session 的臨時檔目錄，位於系統暫存區 | [claude-directory](01-getting-started/claude-directory.md) |
| `scratchpad_dir` | 工作階段暫存目錄路徑 | [hooks](06-reference/hooks.md) |
| `screen reader mode` | 螢幕閱讀器模式：把介面換成可被朗讀的純文字行 | [accessibility](05-configuration/accessibility.md) |
| `sec-default@builtin` | 內建於 Claude Code、先於使用者 mod 載入的防護 mod | [plugins/mods/reference](03-plugins/plugins__mods__reference.md) |
| `security approval dialog` | 下發含 hook/shell 命令等高風險設定時要求使用者明確同意的對話框 | [server-managed-settings](04-administration/server-managed-settings.md) |
| `security-guidance` | 會話內持續檢查 Claude 自己改動的安全外掛 | [security-guidance](01-getting-started/security-guidance.md) |
| `security-patterns.yaml` | 自訂每編輯樣式的規則檔 | [security-guidance](01-getting-started/security-guidance.md) |
| `seed directory` | 預先放好 marketplace 與 plugin 的唯讀目錄 | [plugins/org](03-plugins/plugins__org.md) |
| `self-hosted environment` | 在自家機器／容器上跑 Claude Code 雲端 session 的執行器 | [self-hosted-environments](05-configuration/self-hosted-environments.md)、[whats-new/2026-w32](08-whats-new/whats-new__2026-w32.md) |
| `Self-hosted environments` | 雲端會話改在組織自己基礎設施的執行器上跑 | [platforms](01-getting-started/platforms.md) |
| `sender gating` | 只接受白名單寄件者 | [channels-reference](06-reference/channels-reference.md) |
| `server-managed settings` | Anthropic 伺服器（或閘道）下發的受管設定，啟動拉取並每小時刷新 | [server-managed-settings](04-administration/server-managed-settings.md) |
| `server-side classifier check` | 伺服器端分類器檢查：由 Anthropic 端審查動作，目前不對分類器請求計費 | [auto-mode-classifier-billing](05-configuration/auto-mode-classifier-billing.md) |
| `session` | 工作階段：綁定專案目錄、存成 JSONL 的已儲存對話 | [desktop](01-getting-started/desktop.md)、[sessions](01-getting-started/sessions.md) |
| `session access token` | 工作階段存取令牌：JWT，用於自託管工作階段向服務自證身分 | [self-hosted-environments-identity](05-configuration/self-hosted-environments-identity.md) |
| `session 範圍排程` | 任務綁在 session，不是系統級排程 | [scheduled-tasks](02-build/scheduled-tasks.md) |
| `session.send` | 把訊息送到另一個 session/subagent 的 API | [plugins/mods/api](03-plugins/plugins__mods__api.md) |
| `SessionStore` | SDK 定義的 session 逐字稿外部儲存介面 | [agent-sdk/session-storage](07-agent-sdk/agent-sdk__session-storage.md) |
| `settings scope` | 設定範圍：某個檔案影響到哪些人／專案 | [settings](05-configuration/settings.md) |
| `settingSources` | 指定 SDK 要載入哪幾層檔案系統設定的選項 | [agent-sdk/claude-code-features](07-agent-sdk/agent-sdk__claude-code-features.md) |
| `setup script` | 設定指令碼：雲端 VM 啟動時先跑的 Bash | [cloud-environments](05-configuration/cloud-environments.md) |
| `sha256 pin` | archive 來源用摘要固定，下載不符即拒絕 | [plugins/security](03-plugins/plugins__security.md) |
| `shell mode` | 以 ! 開頭直接執行命令 | [interactive-mode](06-reference/interactive-mode.md) |
| `signal` | 相關性比對條件，如工作目錄、讀過的檔案、執行過的命令 | [plugins/relevance](03-plugins/plugins__relevance.md) |
| `Simulator 窗格` | Desktop 中顯示 iOS Simulator 的窗格 | [desktop-ios-simulator](01-getting-started/desktop-ios-simulator.md) |
| `Skill` | SKILL.md 指令／知識／流程 | [glossary](06-reference/glossary.md) |
| `SKILL.md` | skill 的指示檔，含 YAML frontmatter | [skills](02-build/skills.md) |
| `skillOverrides` | 從設定覆寫 skill 可見性的鍵 | [skills](02-build/skills.md) |
| `skills-dir plugin` | 放在 ~/.claude/skills/ 且帶 plugin.json 的 plugin，ID 為 @skills-dir | [plugins/create](03-plugins/plugins__create.md) |
| `slash_commands` | init 訊息中列出會話可用命令的欄位 | [agent-sdk/skills](07-agent-sdk/agent-sdk__skills.md) |
| `span` | 追蹤中的單一步驟紀錄 | [agent-sdk/observability](07-agent-sdk/agent-sdk__observability.md) |
| `Spark 圖示` | VS Code 內 Claude Code 的入口圖示 | [vs-code](01-getting-started/vs-code.md) |
| `spawn 模式` | 伺服器建立新會話時共用目錄或各用 worktree | [remote-control](01-getting-started/remote-control.md) |
| `spawnClaudeCodeProcess` | 自訂如何在 VM/容器產生 CLI 程序的回呼 | [agent-sdk/typescript](07-agent-sdk/agent-sdk__typescript.md) |
| `startup()/prewarm()` | 預先啟動 CLI 子程序以縮短首回應延遲 | [agent-sdk/typescript](07-agent-sdk/agent-sdk__typescript.md) |
| `status line` | 狀態列：提示下方由你的腳本產生的資訊列 | [statusline](05-configuration/statusline.md) |
| `Stop hook` | Claude 想結束回合時觸發的 hook，exit 2 可逼它繼續 | [best-practices](01-getting-started/best-practices.md) |
| `stop_hook_active` | Stop hook 輸入欄位，用來避免無限阻擋 | [hooks](06-reference/hooks.md)、[hooks-guide](02-build/hooks-guide.md) |
| `stream-json` | 邊跑邊輸出每則訊息的格式 | [headless](02-build/headless.md) |
| `StreamEvent` | 啟用部分訊息時封裝原始 API 串流事件的訊息 | [agent-sdk/streaming-output](07-agent-sdk/agent-sdk__streaming-output.md) |
| `streaming input` | 以非同步生成器持續餵入使用者訊息的輸入模式 | [agent-sdk/streaming-vs-single-mode](07-agent-sdk/agent-sdk__streaming-vs-single-mode.md) |
| `strict` | marketplace 項目是否可再給已有 plugin.json 的 plugin 附加元件 | [plugins/manifest-reference](03-plugins/plugins__manifest-reference.md) |
| `StructuredOutput 工具` | Claude Code 自動加入、用來回傳結構化結果的內部工具 | [agent-sdk/structured-outputs](07-agent-sdk/agent-sdk__structured-outputs.md) |
| `stub` | 測試中代替 Claude Code 回答事件的假處理函式 | [plugins/mods/test](03-plugins/plugins__mods__test.md) |
| `subagent` | 在主工作階段內、自有 context 執行並回報摘要的委派工作者 | [sub-agents](02-build/sub-agents.md) |
| `Subagent` | 獨立上下文的專門助理 | [glossary](06-reference/glossary.md) |
| `SubagentHandback` | 子代理交付最終報告的工具 | [tools-reference](06-reference/tools-reference.md) |
| `subprocess model` | SDK 以子程序方式驅動 CLI 的架構 | [agent-sdk/hosting](07-agent-sdk/agent-sdk__hosting.md) |
| `SUBPROCESS_ENV_SCRUB` | 啟動子程序時剝除憑證類變數 | [env-vars](06-reference/env-vars.md) |
| `Suggested task` | Claude 發現範圍外待辦後提出、可另開會話的卡片 | [desktop](01-getting-started/desktop.md) |
| `supervisor` | 託管背景 session 的獨立背景服務 | [agent-view](02-build/agent-view.md)、[cli-reference](06-reference/cli-reference.md) |
| `synced plugin` | 由 claude.ai 帳戶同步下來的 plugin，ID 結尾 @synced | [plugins/install](03-plugins/plugins__install.md) |
| `system-reminder` | Claude Code 插在對話中的上下文提示訊息（非 system prompt） | [agent-sdk/modifying-system-prompts](07-agent-sdk/agent-sdk__modifying-system-prompts.md) |
| `SystemPromptFile` | 從檔案載入 system prompt 的設定型別 | [agent-sdk/python](07-agent-sdk/agent-sdk__python.md) |
| `TaskCreate/TaskUpdate` | 新版任務追蹤工具，取代 TodoWrite | [agent-sdk/todo-tracking](07-agent-sdk/agent-sdk__todo-tracking.md) |
| `team-lead` | config.json 內 lead 的 agent 類型 | [agent-teams](02-build/agent-teams.md) |
| `telemetry services` | Anthropic 自己的營運遙測（指標、錯誤報告），不同於客戶端 OTel 匯出 | [data-usage](04-administration/data-usage.md) |
| `teleport` | 把雲端會話單向拉進本機終端機繼續 | [claude-code-on-the-web](01-getting-started/claude-code-on-the-web.md) |
| `Teleport` | 把雲端工作階段拉回本機 | [glossary](06-reference/glossary.md) |
| `terminal-setup` | `/terminal-setup`：把 Shift+Enter 寫進終端設定檔的指令 | [terminal-config](05-configuration/terminal-config.md) |
| `terminalSequence` | hook 請 Claude Code 代發的終端機通知碼 | [hooks](06-reference/hooks.md) |
| `thread(執行緒)` | project 中單一工作的雲端會話 | [claude-projects](01-getting-started/claude-projects.md) |
| `tier` | mod 的來源層級(core/builtin/append/user) | [plugins/mods/reference](03-plugins/plugins__mods__reference.md) |
| `Tool` | Claude 可採取的動作 | [glossary](06-reference/glossary.md) |
| `tool search` | 以搜尋方式延後載入工具定義的機制 | [agent-sdk/tool-search](07-agent-sdk/agent-sdk__tool-search.md) |
| `ToolSearch` | 延遲載入 MCP 工具定義的搜尋工具 | [tools-reference](06-reference/tools-reference.md) |
| `Transcript` | 工作階段儲存紀錄檔 | [glossary](06-reference/glossary.md) |
| `transcript viewer` | Ctrl+O 開啟的詳細工具輸出檢視 | [interactive-mode](06-reference/interactive-mode.md) |
| `trigger_phrase` | 觸發 Claude 的留言詞，預設 @claude | [github-actions](01-getting-started/github-actions.md) |
| `trust tier` | marketplace 分官方/社群/第三方三層 | [plugins/security](03-plugins/plugins__security.md) |
| `Turn` | 從你送訊息到 Claude 回應完的一輪 | [glossary](06-reference/glossary.md) |
| `turn（回合）` | Claude 一次輸出加工具執行的往返 | [agent-sdk/agent-loop](07-agent-sdk/agent-sdk__agent-loop.md) |
| `ultracode` | 啟用自動工作流程協調的 effort 設定／提示關鍵字 | [workflows](02-build/workflows.md) |
| `Ultraplan` | 雲端起草計畫的規劃模式（已移除） | [whats-new/2026-w15](08-whats-new/whats-new__2026-w15.md) |
| `ultrareview` | 雲端多 agent 深度審查，每項發現皆獨立重現 | [cli-reference](06-reference/cli-reference.md)、[ultrareview](01-getting-started/ultrareview.md) |
| `unsandboxed retry` | 沙箱內失敗時，經核准後在沙箱外重跑 | [sandboxing](05-configuration/sandboxing.md) |
| `updatedInput` | 工具執行前改寫其參數 | [hooks](06-reference/hooks.md) |
| `usage balance` | Claude Tag 按用量扣款的組織餘額 | [claude-tag](01-getting-started/claude-tag.md) |
| `usage credits` | 舊稱 extra usage 的額外用量額度 | [whats-new/2026-w21](08-whats-new/whats-new__2026-w21.md) |
| `userConfig` | manifest 宣告、安裝時向使用者收集的設定值 | [plugins/components](03-plugins/plugins__components.md) |
| `V2 session API` | 已移除的實驗性 send/stream 會話介面 | [agent-sdk/typescript-v2-preview](07-agent-sdk/agent-sdk__typescript-v2-preview.md) |
| `Verification loop` | 用可執行檢查確認完成 | [glossary](06-reference/glossary.md) |
| `Why this was flagged` | 收合區段，說明該發現的推理 | [code-review-pull-requests](01-getting-started/code-review-pull-requests.md) |
| `Workload Identity Federation` | 免長期金鑰、以 OIDC 向雲端換取身分的機制 | [authentication](04-administration/authentication.md)、[github-actions-cloud-providers](01-getting-started/github-actions-cloud-providers.md) |
| `workspace ID` | Claude Platform on AWS 的工作區識別，每次請求必帶 | [claude-platform-on-aws](04-administration/claude-platform-on-aws.md) |
| `workspace trust` | 工作區信任：首次進資料夾時問你是否信任，決定 repo 內設定能不能生效 | [permissions](05-configuration/permissions.md) |
| `Worktree isolation` | 在獨立 git worktree 執行 | [glossary](06-reference/glossary.md) |
| `worktree 隔離` | 阻止隔離 session 寫入主檢出的工具檢查 | [worktrees](02-build/worktrees.md) |
| `worktree.sparsePaths` | 建立 worktree 時只簽出列出目錄的設定 | [large-codebases](02-build/large-codebases.md) |
| `WSL 會話` | Desktop 在 WSL2 發行版內執行的會話 | [desktop-wsl](01-getting-started/desktop-wsl.md) |
| `xhigh` | 新努力等級，介於 high 與 max | [whats-new/2026-w16](08-whats-new/whats-new__2026-w16.md) |
| `ZDR` | Zero Data Retention，提示與回應處理完即不保留 | [zero-data-retention](04-administration/zero-data-retention.md) |
| `@inline` | 用 --plugin-dir/--plugin-url 載入的 session 專用 plugin 的來源標記 | [plugins/cli-reference](03-plugins/plugins__cli-reference.md) |
| `伺服器模式` | claude remote-control 常駐等遠端連線並可多會話 | [remote-control](01-getting-started/remote-control.md) |
| `使用介面 (Surface)` | CLI／VS Code／Desktop／claude.ai 等入口 | [glossary](06-reference/glossary.md) |
| `信箱（inbox）` | 每個 agent 一個 JSON 檔，寫入成功才算訊息送出 | [agent-teams](02-build/agent-teams.md) |
| `免費執行次數` | 每帳戶一次性 3 次配額，不刷新 | [ultrareview](01-getting-started/ultrareview.md) |
| `分叉子代理` | 繼承完整對話的子代理，用 /subtask 啟動 | [agents](02-build/agents.md) |
| `動態工作流程` | 外掛用來協調多 agent 的工作流機制，可由 /workflows 檢視 | [claude-security](01-getting-started/claude-security.md) |
| `受信任裝置` | 要求註冊裝置與近期登入才能遠端控制 | [remote-control](01-getting-started/remote-control.md) |
| `哨兵警告` | 核准前對可存取 shell/檔案系統的 app 的標示 | [computer-use](01-getting-started/computer-use.md) |
| `審查等級` | Quick/Standard/Deep，徹底度與費用遞增 | [code-review](01-getting-started/code-review.md) |
| `工作階段 (Session)` | 綁目前目錄的獨立對話 | [glossary](06-reference/glossary.md) |
| `工具搜尋（tool search）` | 工具定義延後到需要才載入以省 context | [mcp](02-build/mcp.md) |
| `徵詢（elicitation）` | 伺服器中途向使用者要結構化輸入 | [mcp](02-build/mcp.md) |
| `快速設定` | Team/Enterprise 減少 GitHub 與環境上線步驟的組織開關 | [claude-code-on-the-web](01-getting-started/claude-code-on-the-web.md) |
| `收件匣 socket` | 每個 session 綁定、供其他 session 投遞訊息的通訊端 | [cross-session-messaging](02-build/cross-session-messaging.md) |
| `本機排程任務` | 在自己電腦、app 開啟時才會觸發的 Desktop 排程 | [desktop-scheduled-tasks](01-getting-started/desktop-scheduled-tasks.md) |
| `標籤頁群組` | 擴充功能把 Claude 開的分頁綁在會話的群組 | [chrome](01-getting-started/chrome.md) |
| `沙箱機制 (Sandbox)` | Bash 的 OS 層級隔離 | [glossary](06-reference/glossary.md) |
| `環境選擇器` | Desktop 提示詞下方選 Local/Cloud/SSH 的控制項 | [desktop-quickstart](01-getting-started/desktop-quickstart.md) |
| `用量點數` | Code Review 與 ultrareview 計費用的額度 | [code-review-costs](01-getting-started/code-review-costs.md) |
| `簽到（check-in）` | 背景工作拖過 30 分鐘時要 Claude 檢查任務狀態的機制 | [goal](02-build/goal.md) |
| `系統提示詞` | 每次請求前置的指令 | [glossary](06-reference/glossary.md) |
| `系統提醒 (system reminder)` | harness 塞入對話的上下文訊息 | [glossary](06-reference/glossary.md) |
| `背景 agent` | /background 或 /fork 脫離終端機持續跑的工作階段 | [commands](06-reference/commands.md) |
| `背景工作階段` | 由 supervisor 託管、關閉終端機仍繼續跑的 session | [agent-view](02-build/agent-view.md) |
| `自動修復` | 監看 PR、依 CI/審查事件推送修正 | [claude-code-on-the-web](01-getting-started/claude-code-on-the-web.md) |
| `自動重試` | Claude Code 對暫時性 API 失敗的指數退避重試（最多 10 次） | [errors](02-build/errors.md) |
| `設定層級` | 設定來源優先順序 | [glossary](06-reference/glossary.md) |
| `評估器（evaluator）` | 每回合後判定條件是否滿足的小型快速模型 | [goal](02-build/goal.md) |
| `路徑範圍規則` | rules 檔的 paths: glob，處理符合檔案時才載入 | [large-codebases](02-build/large-codebases.md) |
| `路由模式` | 決定 @Claude 訊息送 Code 或 Chat 的設定 | [slack](01-getting-started/slack.md) |
| `連接器呼叫` | 頁面透過 MCP 連接器在檢視者開啟時取資料 | [artifacts](02-build/artifacts.md) |
| `配對（pairing）` | 用機器人回覆的代碼把你的帳號 ID 加入允許清單 | [channels](02-build/channels.md) |
| `雲端環境` | 保存網路存取、環境變數、setup script 的雲端設定 | [claude-code-on-the-web](01-getting-started/claude-code-on-the-web.md) |
| `預設環境` | 首次上線建立、網路等級為 Trusted 的雲端環境 | [web-quickstart](01-getting-started/web-quickstart.md) |
