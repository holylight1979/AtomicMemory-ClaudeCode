# Claude Code設定目錄CLAUDE_CONFIG_DIR取值是有值就用-空字串當沒設-不去空白-設定檔與.claude.json都跟著搬-和記憶系統資料根是兩件事

- Scope: global
- Author: holylight
- Source: track-data-root-2 004 交付（session 616e4407）2026-10-14，調度總控台代寫
- Confidence: [臨]
- Trigger: CLAUDE_CONFIG_DIR, 設定目錄, settings.json 位置, .claude.json, 資料根 WG_CLAUDE_DIR, fix-hook-python, 安裝器 子行程 環境, Claude Code 設定檔路徑, 設定檔跟著搬
- Created-at: 2026-10-14

## 知識

- [臨] 實查（grep Claude Code 2.1.296 Windows 原生執行檔）：讀 CLAUDE_CONFIG_DIR 的地方幾乎都是 `process.env.CLAUDE_CONFIG_DIR || <家目錄>/.claude`，所以空字串當沒設、不去頭尾空白、不展開 `~`；`.claude.json` 也跟著它搬（`join(CLAUDE_CONFIG_DIR || home, '.claude'+後綴+'.json')`）。
- [臨] 記憶系統的資料根（WG_CLAUDE_DIR）和 Claude Code 設定目錄是兩件事：Claude Code 自己讀的檔（settings.json、.claude.json）要跟 CLAUDE_CONFIG_DIR，不能跟資料根。一般安裝三者都是 ~/.claude，只有使用者另設其中一個時差異才浮現。
- [臨] 安裝器這類叫起子行程的程式：WG_CLAUDE_DIR 與 CLAUDE_CONFIG_DIR 兩個都要釘在安裝目標，否則設了變數的機器跑安裝驗證會改到真的 Claude Code 設定；誘餌案兩處各放一份。

## 行動

- 讀 Claude Code 設定用 `os.environ.get("CLAUDE_CONFIG_DIR") or Path.home()/".claude"`，不用資料根函式、不自加 strip
- 升版後 grep CLAUDE_CODE_EXECPATH 指的執行檔裡 `env.CLAUDE_CONFIG_DIR` 的前後文再確認
