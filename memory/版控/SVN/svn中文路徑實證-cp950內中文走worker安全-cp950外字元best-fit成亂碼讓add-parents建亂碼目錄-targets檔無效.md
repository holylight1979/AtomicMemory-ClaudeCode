# svn中文路徑實證-cp950內中文走worker安全-cp950外字元best-fit成亂碼讓add-parents建亂碼目錄-targets檔無效

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: svn 亂碼, svn add 中文, UIºt¥X, 亂碼資料夾, cp950, best-fit, --targets, svn argv 編碼, GetACP, 中文路徑 svn, SvnEncoding
- Created-at: 2026-10-01
- Source: session:d892b7c9#160556c3 2026-10-01
- Quote: 「你會繼續推進到全部完工吧?」

## 知識

- [臨] 實測（svn 1.14.5、Windows ACP=cp950、svnadmin 本地倉）：svn.exe 收 argv 與 `--targets` 檔都走 ANSI code page 轉 UTF-8，cp950 內的中文（如「UI演出」）經 Python subprocess list args → svn add/commit → 另一副本 checkout，磁碟名與 status xml 全程正確；worker 通道本來就安全。
- [臨] 真正危險是 cp950 外字元（如 `ゔ`、`é`）：Windows 把 argv 做 best-fit 轉碼（`é`→`e`）或 `?`，`svn add --parents` 會真的建出亂碼目錄、`delete` 可能刪錯鄰居。`--targets` 檔無法繞過（UTF-8 內容 → W155010 not found；cp950 內容根本編不出來）。注意「ヴ」U+30F4 其實在 cp950 內（`\xc7\xae`），要測 cp950 外得用 `ゔ`。
- [臨] 現行防線（`hooks/wg_vcs_sync.py`）：`_Svn.run` 前置守門——argv 含 ACP 編不出的字元就 `_Stop`不呼叫 svn，留 `.unpushed` 與可讀理由；`_svn_argv_encoding()` 用 GetACP。偵測：`atom-health-check`「`mojibake_names`」與 `sync-memory-index` 對名稱含 U+0080–U+00FF 的項 stderr `⚠ 疑似亂碼名稱` 並跳過；PreToolUse `check_svn_encoding` 對 Bash/PowerShell 的 `svn add <非 ASCII 路徑>` 出 `[Guardian:SvnEncoding]` 提醒。
- [臨] 某專案的 `shared/UIºt¥X`（＝`UI演出` 的 Big5 位元組被當 cp1252 解碼）建於 2026-09-24、svn 本地 added、空、遠端無，早於 vcs-sync worker 誕生，非 worker 所建；最可能是 session 內從 MSYS bash（LANG=zh_TW.UTF-8）手動 svn add。清理：`svn revert "<該路徑>"`。

## 行動

- 看到記憶目錄出現 Latin-1 字元的資料夾 → 先 `svn status --xml` 看是 local added 還是遠端有，本地的直接 revert
- 中文路徑的 svn add 交給 vcs-sync 背景提交，不要在 bash 手打
- 測 svn 編碼案：用 `hooks/verify/verify_svn_unicode_paths.py` 的矩陣，cp950 外字元用 `ゔ` 不用 `ヴ`
