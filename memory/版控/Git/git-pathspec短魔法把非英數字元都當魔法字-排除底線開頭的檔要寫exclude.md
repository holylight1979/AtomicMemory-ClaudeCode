# git-pathspec短魔法把非英數字元都當魔法字-排除底線開頭的檔要寫:(exclude)

- Scope: global
- Author: holylight
- Source: reading-path 減量交付（2026-10-22）
- Confidence: [臨]
- Trigger: pathspec, Unimplemented pathspec magic, :(exclude), 排除檔案, git diff 排除, :!
- Created-at: 2026-10-22
- Quote: 「<pasted_content id="e02d"> 調度總控台：你是 v6.0 的調度總控台，執行 /console 調度，接替 claude-ba（token 快乾）。專案根 C:\Users\holylight\.claude（main）；接續單 C:\Users\holylight\.claude\memory\_staging\next-phase-v6.0-寫程式碼的進化.md；信箱…」

## 知識

- [臨] `:!_x.py` 會報 `fatal: Unimplemented pathspec magic '_'`：冒號後的非英數字元都被當成短魔法字。排除底線開頭這類檔名要寫長形式 `:(exclude)_x.py`。

## 行動

- git 指令排除檔案一律用 `:(exclude)<路徑>`，不用 `:!`
