# 驗工具的help前先看有沒有argparse-沒有的工具help等於真跑-會動到現役資料-也要帶隔離資料根

- Scope: global
- Author: holylight
- Source: session:6df28d76 2026-11-06 核心切包第二階段 N4a 事故
- Confidence: [臨]
- Trigger: --help, argparse, help 真跑, 批次驗工具, 隔離資料根, WG_CLAUDE_DIR, health-weekly
- Created-at: 2026-11-06

## 知識

- [臨] 批次跑 `工具 --help` 不等於唯讀：沒有 argparse 的工具會把旗標忽略、直接真跑，或把 --help 當參數（當埠起服務、當查詢、當卡名去呼叫 LLM）。實例：子代理驗語言表時把 health-weekly 真跑兩次，覆寫現役的健檢狀態檔，開場提醒指到被刪掉的報告。
- [臨] 事故不在 git 追蹤範圍時 git status 看不出來，要另查 workflow 與 Logs 的修改時間。
- [臨] 掃出同型 5 支：全部補 argparse，--help 只印說明。

## 行動

- 批次跑工具前環境帶隔離資料根
- 沒看過原始碼的工具不要假設 --help 無副作用
- 寫 CLI 一律 argparse，看說明不得有副作用
