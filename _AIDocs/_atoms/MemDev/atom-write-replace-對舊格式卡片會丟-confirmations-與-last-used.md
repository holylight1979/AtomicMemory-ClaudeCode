# atom-write-replace-對舊格式卡片會丟-confirmations-與-last-used

- Scope: global
- Author: holylight
- Source: 某專案的一張舊格式卡片（該專案 repo 留有改寫前版本）
- Confidence: [臨]
- Trigger: atom_write replace, Confirmations 歸零, 舊格式 atom, Last-used 丟失, preserved conf=0, 裁剪 atom, 超預算 append 被拒
- Created-at: 2026-10-07
- Quote: 「幫你登入了啊」

## 知識

- [臨] 實測：對舊格式專案 atom（標題行為中文、檔名為英文 slug、`- Scope: project`、有 `- Last-used: 2026-04-23` / `- Confirmations: 10`）做 `atom_write mode=replace`，回訊「preserved conf=0 rh=0」，結果標題被改成檔名、Confirmations 與 Last-used 行消失、Created-at 變成當天；歸因候選：replace 路徑的中繼資料讀取沒容忍舊格式（標題≠檔名或 Scope=project）。附帶：knowledge 區超 3072 bytes 的舊卡 append 必被預算擋，只能 replace，所以這個丟失會在「裁剪舊卡」時必然觸發。

## 行動

- 修：在 ~/.claude session 追 lib/atom_io 的 replace 中繼資料保留邏輯，對舊格式標題/Scope 也要讀到 Confirmations 與 Last-used
- 裁剪舊卡前先記下 Confirmations，replace 後核對回訊的 preserved conf
