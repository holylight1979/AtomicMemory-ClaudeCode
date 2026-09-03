# windows認證管理員blob上限-credwrite回傳值必檢-大token禁keyring

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: CredWrite, Credential Manager, 認證管理員, keyring, DPAPI, token 儲存, OAuth token, 保險庫, vault, ProtectedData, 靜默失敗, WindowsCredentialStorage
- Created-at: 2026-08-12

## 知識

- [臨] Windows 認證管理員（CredWrite/CRED_TYPE_GENERIC）單筆 credential blob 有上限（約 2560 bytes）；超過時 CredWrite 回傳 false 而非丟例外——呼叫端不檢查回傳值就是靜默寫入失敗，讀回的是舊值。2026-08-12 於 ChatGPT-codex-CS `WindowsCredentialStorage.Save`（CredWrite 回傳值被忽略）實測證實：~1KB 寫入成功、2KB 以上「假成功」。
- [臨] 真實 ChatGPT OAuth token 組（id/access/refresh JWT）JSON 動輒 >10KB，必超過上限——Windows 認證管理員不適合存大 token；要存大 secret 用 DPAPI 檔案（ProtectedData.Protect + 專屬 entropy + CurrentUser scope），Proj-JARVIS `ClientLlmVault` 是現成範本。
- [臨] 症狀特徵：OAuth 流程一路成功（瀏覽器授權、token 交換都過）但登入永遠沒完成、儲存層讀回舊值或空值——先懷疑儲存層靜默失敗，別追流程本身。

## 行動

- P/Invoke 寫入類 API（CredWrite 等）一律檢查 bool 回傳值＋Marshal.GetLastWin32Error，禁 fire-and-forget
- >2.5KB 的 secret 不進 Windows 認證管理員；改 DPAPI 檔案保險庫
- OAuth『交換成功但登入沒完成』先查儲存層是否靜默失敗
