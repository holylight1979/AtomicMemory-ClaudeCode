# 向量服務查修-vec綠燈只代表服務活著-索引失敗看status的index_job-重啟要確認埠上只剩一支-各層file_path基準目錄不同

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 向量服務, 向量庫, vector service, index_job, 增量索引, 向量重建, 3849, vec✓, 向量庫缺卡, 向量庫路徑
- Created-at: 2026-10-29
- Related: 換資料根的session向量檢索查的是全機共用live向量庫再用資料根可見池過濾-bm25為主時向量只在全沒命中才打-新卡要等向量重建
- Source: session:5c82ed86#21a053d6 2026-10-29
- Quote: 「TECH.md 第 #11 .. 寫的是 v6的改版過程? 還是現況? 這些資訊是不是已經有存在部分過時了的問題 ? 而且沒有標明是針對 "寫"code".. 也沒有 程式守門 這樣的範疇說明； 會讓人聯想： v6 的開關關閉的情況下，好像整個系統都被關掉了? 還是說.. 真的是這樣!?!?」

## 知識

- [臨] statusline 的 vec✓ 只看服務活著（/health）；索引重建成敗只寫在 GET /status 的 `index_job`（running／result／error）。曾因 indexer 印卡名碰到 cp950 編不出的字整輪中止很久，716 張卡有 348 張不在向量庫卻沒人發現。查向量先看 /status。
- [臨] Windows 上可以同時有兩支 service.py 聽 3849；POST /shutdown 只關到接到請求的那支。重啟後看 /health 的 uptime_seconds 是不是接近 0，或用 Get-NetTCPConnection -LocalPort 3849 確認只剩一個行程。
- [臨] 向量庫 file_path 是各層自己的相對路徑：global 相對 memory/、extra:local-atoms 相對 _AIDocs/_atoms/；稽核「路徑還在不在」拿錯基準會算出大量假的失效。向量庫比索引多出的卡（episodic 摘要、wisdom）是 indexer 本來就會收的檔，不是殘留。

## 行動

- 卡存在卻語意搜不到：先 curl /status 看 index_job.error
- 重啟向量服務後確認 uptime 接近 0、埠上只剩一支
- 稽核向量庫路徑按層用各自的基準目錄
