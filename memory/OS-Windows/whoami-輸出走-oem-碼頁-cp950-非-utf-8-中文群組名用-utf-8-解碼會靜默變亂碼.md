# whoami 輸出走 OEM 碼頁 cp950 非 utf-8-中文群組名用 utf-8 解碼會靜默變亂碼

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: whoami, OEM 碼頁, cp950, GetOEMCP, subprocess 中文亂碼, AD 群組, console 編碼, mbcs
- Created-at: 2026-10-01
- Source: commit:3a3c3d0 2026-10-01（原對話已逾保留期）

## 知識

- [臨] 實測：`whoami.exe /groups /fo csv` 的 stdout 位元組是主控台 OEM 碼頁（本機 cp950），不是 utf-8——`decode("utf-8")` 直接 UnicodeDecodeError、`errors="replace"` 則中文群組名（核心程式／美術）全變 U+FFFD，子字串對映靜默落空、職能解析退成空。正解：`ctypes.windll.kernel32.GetOEMCP()` 取碼頁 → `decode(f"cp{n}", errors="replace")`，失敗退 `mbcs`（hooks/wg_roles.py `_oem_encoding`）。
- [臨] 同類 Windows 主控台工具（whoami、net、wmic、tasklist）都走 OEM 碼頁；`locale.getpreferredencoding()` 回的是 ANSI 碼頁（zh-TW 兩者同為 950，其他語系可能不同），不能當 console 輸出的依據。
- [臨] MSYS bash 裡的 `whoami` 是 GNU coreutils 版、不認 `/groups`；要取 AD 群組必須呼叫 `%SystemRoot%/System32/whoami.exe` 的絕對路徑。

## 行動

- subprocess 讀 Windows 主控台工具輸出：`capture_output=True`（不用 text=True），用 GetOEMCP 碼頁解碼，不預設 utf-8
- 解析結果要有可觀測訊號：對映落空時 stderr 一行，不能讓亂碼靜默變成「查不到」
- 從 bash 環境呼叫 Windows 內建指令時寫 System32 絕對路徑，避免撞 coreutils 同名指令
