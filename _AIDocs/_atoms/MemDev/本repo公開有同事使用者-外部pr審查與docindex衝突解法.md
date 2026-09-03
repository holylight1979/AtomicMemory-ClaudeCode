# 本repo公開有同事使用者-外部PR審查與DocIndex衝突解法

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: pull request, PR, 外部貢獻, 同事, DocIndex, 衝突, 向後相容, journal
- Created-at: 2026-09-02

## 知識

- [臨] 本 GitHub repo 公開且有同事實際安裝使用並回發 PR（2026-04 同事發 PR#3 強化 journal-aggregate，2026-09-02 審查後合併）。改共用工具時要顧其他使用者的環境與設定，不能只看本機（例：journal 鏡射清理 14 天/主路徑 60 天為使用者拍板；env 讀取統一 _env() 含 settings*.json fallback）。
- [臨] DocIndex-System.md 為高頻改動檔，外部 PR 幾乎必與它整檔衝突；實證解法：整檔取 HEAD 版，再把 PR 的條目描述植入對應段落，不逐行三方合。

## 行動

- 審外部 PR 時檢查：無惡意碼/外連、與現行 main 的 blob 差距、對其他使用者環境的行為變更（清理/刪檔類最敏感）
