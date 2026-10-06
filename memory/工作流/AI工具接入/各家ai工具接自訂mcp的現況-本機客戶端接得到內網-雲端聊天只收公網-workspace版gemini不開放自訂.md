# 各家AI工具接自訂MCP的現況-本機客戶端接得到內網-雲端聊天只收公網-Workspace版Gemini不開放自訂

- Scope: global
- Author: holylight
- Source: session 32cb5712 2026-10-05；來源文件 support.google.com/gemini/answer/17209137、learn.chatgpt.com/docs/extend/mcp、support.claude.com/en/articles/11175166、antigravity.google/docs/mcp
- Confidence: [臨]
- Trigger: 自訂 MCP, 其他 AI 客戶端, Antigravity, Gemini CLI, 網頁版 Gemini, ChatGPT connector, 公司記憶怎麼接, 中台主機 MCP, 內網 MCP, mcp_config.json, ai-client-setup
- Created-at: 2026-10-06
- Quote: 「<browser_instruction># Claude in Chrome browser automation You have access to browser automation tools (mcp__claude-in-chrome__*) for interacting with web pages in Chrome. Follow these guidelines for…」

## 知識

- [臨] 各家 AI 工具都能「主動連 MCP」，但分兩類，差別在連線從哪裡發出：裝在電腦上的工具（Codex CLI／桌面／IDE 共用 ~/.codex/config.toml、Gemini CLI、Antigravity、Claude Code／Desktop 本機設定、Cursor、VS Code Copilot）從使用者電腦發出，接得到公司內網；網頁版聊天（claude.ai、ChatGPT developer mode、Gemini Enterprise、Gemini 個人版）從廠商雲端發出，官方明寫要公網 HTTPS（OpenAI 另有 Secure MCP Tunnel 從內網主動連出）。公司內網的記憶服務只有第一類接得上。（2026-10-05 三支 agent 讀官方文件查證）
- [臨] 網頁版 Gemini：公司 Workspace 帳號官方明寫不可用自訂 MCP（只有上架第三方連接器）；個人帳號有但限美國、限英文。要讓它吃公司知識只剩：查詢網頁人工貼、或定期匯出到 Google Drive 讓它用原生 Drive 連結／Gem 知識檔讀（只讀、非即時）。
- [臨] 公司內路線：美術用 Codex、企劃主力 Antigravity（公司 Workspace 帳號）→ 兩者都是本機客戶端，用 tools/ai-client-setup.py 就接得上；內網主機版 MCP 服務等裝的人多到各機更新成負擔再做；服務放公網會與「不做 SSO」裁決衝突，不走。
- [臨] 設定檔位置（本機實檔確認）：Antigravity ~/.gemini/config/mcp_config.json，mcpServers 形狀與 Gemini CLI ~/.gemini/settings.json 相同（command/args 或 serverUrl+type:http）；~/.gemini 是兩者共用的家，偵測 Gemini CLI 不能只看該目錄存在。Codex 設定在 ~/.codex/config.toml 的 [mcp_servers.<name>]，測試用 CODEX_HOME=<tmp> codex mcp list 可不碰真設定。http://192.168.x.x 非加密內網位址各家都無官方明文，要實測。

## 行動

- 有人問「X 工具怎麼接公司記憶」：先分它是本機客戶端還是網頁版；本機 → ai-client-setup.py，網頁 → 查詢網頁／Drive 匯出
- 產品功能變得快，進入此題前先重查官方文件，不直接沿用本條
