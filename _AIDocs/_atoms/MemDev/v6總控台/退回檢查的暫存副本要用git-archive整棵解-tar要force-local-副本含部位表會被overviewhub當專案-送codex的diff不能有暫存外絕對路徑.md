# 退回檢查的暫存副本要用git-archive整棵解-tar要force-local-副本含部位表會被overviewhub當專案-送codex的diff不能有暫存外絕對路徑

- Scope: global
- Author: holylight
- Source: session:6ea645d0 2026-10-13
- Confidence: [臨]
- Trigger: 退回檢查, 退回紅, 暫存副本, git archive, tar --force-local, Cannot connect to C, 舊版檔跑新測試, 舊碼回放樹, 回放樹位置, 祖先 conftest
- Created-at: 2026-10-13
- Related: worktree隔離session改部位檔被overviewhub閘連擋-證據只認read事件與bash註解三行-git-c-live與python-heredoc與變數路徑一律被拒, 在子目錄跑git-apply會靜默略過子目錄外的路徑照樣回0-重建修補前版本做紅回放改用git-archive解到暫存再patch-p1, git-bash的tar解windows絕對路徑報cannot-connect-to-c-resolve-failed-冒號前被當遠端主機-加force-local或改用python-tarfile
- Quote: 「施工agent若能多開就多開，提速吧」

## 知識

- [臨] 始末：工作 session 要證「新案在舊版程式紅在斷言」，只把 hooks/、lib/ 複製到 scratchpad 再換回舊檔，pytest 收集一路缺 tools/ 的模組、.claude/overview-map.md、workflow/config.json，連撒三次。根因：hooks 的 verify 會讀 repo 根的部位表與 config、import tools/ 的模組，零碎複製必漏。正解：`git archive --format=tar -o <scratch>/head.tar HEAD`，進目標目錄 `tar --force-local -xf ../head.tar` 解整棵，再只覆蓋新測試與新模組、保留要退回的舊檔。
- [臨] GNU tar（Git Bash）把 `C:/…` 的冒號當遠端主機：報 `Cannot connect to C: resolve failed`，加 `--force-local` 或用相對路徑。
- [臨] 在暫存副本跑的「預期要紅」會被 TestFailGate 記進本 session 的 failing_tests，收尾被擋「測試未綠」。做法：退回跑完回本樹重跑同一案留綠紀錄，擋了選 (b) 說明是刻意的退回檢查並回報主持端。
- [臨] 有別的工作樹並行時不用 stash 退回：stash 堆疊整個 repo 共用、跨 worktree 都看得到。改用 git archive 解基底樹、只放新案例檔進去跑；綠的那幾條應該就是「照舊」那一側，順便驗案例沒寫成兩邊都綠。
- [臨] shell 的 cwd 還停在暫存樹裡時刪不掉（Device or resource busy），先 cd 出來再刪。
- [臨] 舊碼回放樹不能放在 ~/.claude 底下（例：job 暫存）：pytest 會沿祖先目錄吃到 live 的 conftest.py，回放結果混進 live 的程式；回放樹要放 repo 外（C:\w4\…）。
- [臨] 不用 tar 也行：Python tarfile 直接吃 Windows 絕對路徑，`tarfile.open(p).extractall(dst, filter='data')`。

## 行動

- 退回檢查：git archive HEAD 整棵解到 scratchpad（tar --force-local），只覆蓋新測試與新模組，junitxml 看每案是 failure 不是 error
