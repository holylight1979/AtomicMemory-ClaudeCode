# git-pathspec短魔法把非英數字元都當魔法字-排除底線開頭的檔要寫:(exclude)

- Scope: global
- Author: holylight
- Source: reading-path 減量交付（2026-10-22）
- Confidence: [臨]
- Trigger: pathspec, Unimplemented pathspec magic, :(exclude), 排除檔案, git diff 排除, :!
- Created-at: 2026-10-22

## 知識

- [臨] `:!_x.py` 會報 `fatal: Unimplemented pathspec magic '_'`：冒號後的非英數字元都被當成短魔法字。排除底線開頭這類檔名要寫長形式 `:(exclude)_x.py`。

## 行動

- git 指令排除檔案一律用 `:(exclude)<路徑>`，不用 `:!`
