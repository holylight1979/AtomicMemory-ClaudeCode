# bash同一命令多份heredoc時stdin是最後那份-fd前綴的不是stdin-小於號也換stdin-靜態判python減號只在單一heredoc且無其他輸入重導向時準

- Scope: global
- Author: holylight
- Source: commit:cfda1231 2026-10-21（修補實證）
- Confidence: [臨]
- Trigger: heredoc, python -, stdin 重導向, 多份 heredoc, 靜態判寫入目標
- Created-at: 2026-10-21

## 知識

- [臨] bash 同一個命令接多份 heredoc 時，stdin 是最後那份；帶 fd 前綴（3<<EOF）的不是 stdin；`<` 也會換掉 stdin。
- [臨] 静態判 `python -` 內文的程式（例：拿 heredoc 內文交 ast 判寫入目標），只有在單一 heredoc、沒有別的輸入重導向時才判得準；兩份 heredoc 只看第一份會把寫檔的第二份判成沒寫入目標。其餘情形照 UNKNOWN 擋。

## 行動

- （依知識內容判斷）
