# windows的git把worktree的.git檔設成隱藏-python直接覆寫會PermissionError-要先unlink再寫

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: git worktree add, .git 檔, 隱藏檔, PermissionError, write_text, Errno 13, hideDotFiles, 改寫 .git
- Created-at: 2026-10-13
- Source: session:03f81f65 2026-10-13

## 知識

- [臨]（實測 Windows、Git for Windows）`git worktree add` 產生的 worktree 根目錄 `.git` 檔被設成隱藏屬性（core.hideDotFiles 預設 dotGitOnly）。Python `Path.write_text`／`open(..., 'w')` 對隱藏檔走 CREATE_ALWAYS，直接回 `PermissionError: [Errno 13]`；同一支測試在 Linux 不會紅。
- [臨] 解法：先 `path.unlink()` 再寫（刪除不受隱藏屬性影響），或先用 `attrib -h` 拿掉屬性。測試要把真 worktree 的 `.git` 改寫成相對路徑之類的變體時特別會踩到。

## 行動

- 測試或工具要改寫 worktree 的 .git 檔：先 unlink 再寫，不要直接 write_text
