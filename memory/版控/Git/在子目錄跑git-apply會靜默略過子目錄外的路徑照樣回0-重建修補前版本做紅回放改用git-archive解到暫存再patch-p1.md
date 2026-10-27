# 在子目錄跑git-apply會靜默略過子目錄外的路徑照樣回0-重建修補前版本做紅回放改用git-archive解到暫存再patch-p1

- Scope: global
- Author: holylight
- Source: 2026-10-23 判分修補實測
- Confidence: [臨]
- Trigger: git apply, 子目錄, 略過路徑, 照樣回 0, git archive, patch -p1, 紅回放, 修補前版本, 舊樹加 patch 重建
- Created-at: 2026-10-23
- Related: 退回檢查的暫存副本要用git-archive整棵解-tar要force-local-副本含部位表會被overviewhub當專案-送codex的diff不能有暫存外絕對路徑

## 知識

- [臨] 在 repo 的子目錄跑 `git apply`，patch 裡子目錄以外的路徑會整個被略過，而且照樣回 0，看不出沒套上。
- [臨] 拿舊樹＋patch 重建「修補前」版本做紅回放：用 `git archive` 解到暫存，再 `patch -p1 -d <目錄>` 套上；用 git apply 會以為重建好了，回放其實跑在舊碼上。
- [臨] 後果：紅的原因變成「舊函式不收新參數」，不是要證的行為差，紅回放等於白做。

## 行動

- 重建修補前版本：git archive 解到暫存，patch -p1 -d <目錄> 套 patch，套完 grep 一個預期改動確認真的套上
- 看到紅回放的紅是參數不符這類錯誤，先懷疑重建沒套上
