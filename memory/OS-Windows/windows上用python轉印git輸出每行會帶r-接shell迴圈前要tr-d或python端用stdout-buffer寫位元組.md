# windows上用python轉印git輸出每行會帶r-接shell迴圈前要tr-d或python端用stdout-buffer寫位元組

- Scope: global
- Author: holylight
- Source: 2026-10-23 斷路器與紅測閘修補實測
- Confidence: [臨]
- Trigger: \r, CRLF, tr -d, stdout.buffer, No such file, 檔名清單, Python 轉印 git 輸出, shell 迴圈
- Created-at: 2026-10-22
- Related: windows-python-write-text-缺-newline-把-lf-翻-crlf-整檔假-diff

## 知識

- [臨] Windows 上用 Python 啟動器把 git 輸出轉印出來，文字模式的 stdout 會把 \n 換成 \r\n，每行尾巴帶 \r；接到 shell 迴圈時 \r 會黏在每個值後面。
- [臨] 實例：檔名清單每行帶 \r，逐檔 grep 全部回「No such file」（\r 看不見，檔名看起來是對的）。
- [臨] 解法：接 shell 迴圈前先 `tr -d '\r'`，或在 Python 端用 sys.stdout.buffer 寫位元組，不走文字模式換行。

## 行動

- Python 印出的清單要接 shell 迴圈 → 先 tr -d '\r'
- 迴圈裡每筆都報找不到 → 先 `cat -A` 或 repr 看行尾有沒有 ^M
