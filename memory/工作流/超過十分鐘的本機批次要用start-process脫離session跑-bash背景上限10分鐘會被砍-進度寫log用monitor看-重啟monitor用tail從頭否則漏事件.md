# 超過十分鐘的本機批次要用start-process脫離session跑-bash背景上限10分鐘會被砍-進度寫log用monitor看-重啟monitor用tail從頭否則漏事件

- Scope: global
- Author: holylight
- Source: 本場 14 件 CPU 形狀生成批次：run_in_background 10 分鐘被砍 → 改 Start-Process + shapes_progress.log + Monitor
- Confidence: [臨]
- Trigger: run_in_background, 背景執行, 10 分鐘, timeout 600000, 長耗時, 批次迴圈, Start-Process, 脱離 session, Monitor, tail -f, 進度 log, 漏事件
- Created-at: 2026-11-06

## 知識

- [臨] Bash 工具 `run_in_background` 的上限跟前景一樣是 10 分鐘（timeout 最大 600000），超過就被砍；一個要跑一小時的迴圈放進去會在第三輪中途死掉。做法：寫成 .ps1，用 `Start-Process pwsh -ArgumentList ... -WindowStyle Hidden -PassThru` 脱離 session 跑，迴圈自己把每件 START/DONE/FAIL 寫進進度 log，再用 Monitor `tail -f log | grep --line-buffered` 收事件；迴圈要能跳過已完成的項目，死掉重跑不重做。
- [臨] Monitor 最長 30 分鐘就過期，重開時若用 `tail -n 0 -f` 會漏掉過期與重開之間完成的事件；要嘗試不漏就記住上次看到的行數，或用 `tail -n +N`。跑完要主動比對 log 裡的 DONE 數與預期總數。

## 行動

- 估超過 10 分鐘的本機批次：寫 .ps1 → Start-Process 脱離 → 進度 log → Monitor；不用 run_in_background 硬塞
- Monitor 過期重開後，用 log 的總數對帳補漏掉的事件
