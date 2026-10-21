# hook多寫一筆guard-log會讓git錄放帶測試判受測目錄不同而跳過閘-錄放帶exclude-Logs並重錄-先只退回改動檔證明是錄放帶問題

- Scope: global
- Author: holylight
- Source: track-entrypoint-contract 002（verify_gate_bypass 重錄 25 檔）
- Confidence: [臨]
- Trigger: git_cassette, 錄放帶, --git-record, 受測目錄不同, verify_gate_bypass 跳過, guard log 多一筆, Logs 目錄
- Created-at: 2026-10-21
- Quote: 「A」

## 知識

- [臨] git 錄放帶測試（git_cassette）用受測目錄內容比對判是不是同一個場景；hook 多寫一筆 guard log（GUARD_LOG_DIR 在 tmp_path 下）會讓 Logs 目錄比錄製時早出現，錄放帶判「受測目錄不同」就跳過受測邏輯，案例看起來綠其實沒驗。修法：git_cassette(exclude=("Logs",)) 再 --git-record 重錄；先只退回改動檔跑一次全綠，證明是錄放帶問題不是閉變了。

## 行動

- 錄放帶測試突然全過但改了 hook：先查是不是被判受測目錄不同而跳過
