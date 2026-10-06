# edit-metadata用re-subn字串替換會把值裡的反斜線當跳脫-Windows路徑或引述值一律用函式替換

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: bad escape, re.subn, re.sub 替換字串, edit_metadata, 反斜線跳脫, Quote 寫入失敗, provenance-backfill error, regex replacement template
- Created-at: 2026-10-06
- Source: session:f1e8b9d8#501adf46 2026-10-06
- Quote: 「而且，肯定會動到code， 全面完工也全面驗證完成無誤後，我在此先直接授權你 ** 上GIT **。」

## 知識

- [臨] 始末（2026-10-06 回填 920 顆 atom）：16 顆寫入失敗 `bad escape \\P at position 71`——`lib/atom_io.edit_metadata` 用 `line_re.subn(replacement, text)`，replacement 是字串時 re 會把裡面的 `\\U`、`\\P`當 regex 跳脫解析；以前只寫 Trigger/Related/Tags（無反斜線）所以沒爆，一裝 Quote（使用者原話含 Windows 路徑）就炸。
- [臨] 正解：替換字串改傳函式 `line_re.subn(lambda _m: replacement, text)`，函式回傳值不走 template 解析；測試要放含 `\\U`、`\\P` 的值（寫測試源碼時用 chr(92) 拼，免得源碼自己被 unicode escape 吃掉）。

## 行動

- 任何把「使用者文字／路徑」塗進 re.sub/subn 的地方一律用函式回傳替換值，或 re.escape 不適用時改 str.replace
- Bash heredoc 寫 Python 測試源碼時反斜線會被摺半，含反斜線的字面值用 chr(92) 拼
