# 工作session切進worktree後被隔離寫不到worktree外-交付改用SendMessage回全文-cwd不在worktree時收據根對不上

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: EnterWorktree, worktree 隔離, 寫不到 live, 交付信, 信箱, SendMessage 交付, 工作 session, 收據 root, primary working directory
- Created-at: 2026-10-12
- Source: session:a1cd2ad7#32684599 2026-10-12
- Quote: 「這session所有你學到的重要知識、經驗都記好的話，我就關掉了。」

## 知識

- [臨] 多軌開發實踩：工作 session 的分頁 cwd 若在 live（不在 worktree），驗證收據的 root 由 hook 的 cwd 推出來會是 live，量尺閘對不上。解法是 session 內用 `EnterWorktree(path)` 切進 worktree；但切進去之後，harness 隔離規則與 CrossRealmBashBlock 會擋住對 worktree 外路徑的寫入，**寫不到 live 的信箱**，也跑不了 `git -C <live> status`。
- [臨] 因此派工單要一開始就規定：開工先確認 primary working directory 是 worktree（不是就 EnterWorktree）、**交付一律用 SendMessage 回全文**、總控台收到後存進信箱；live 未動證明改用 mtime 對照，由總控台補跑 porcelain。總控台換人時要先告訴工作 session「送舊總控台失敗就等新總控台訊息再重送」。
- [臨] 工作 session context 將滿時的交棒：先叫它停手、不 commit（未提交的改動留在 worktree 給接手者），只用 SendMessage 回 20 行內的接手備忘（每條工作是已完成且測過／已改未測／未開始、每個未提交檔改到哪、做過的選擇與理由、讀程式碼看不出來的坑）；總控台把備忘存進信箱，再寫一份自足的派工單（含原話目標、待修清單、備忘路徑）給新 session 在同一個 worktree 接著做。新 session 不靠舊對話記憶，比接近滿、會被自動壓縮的舊 session 穩。
- [臨] 原設計者固定在根層 `C:\Users\holylight\.claude` 開 Claude Code，不另開 worktree 資料夾。給工作 session 的開工句要寫「第一步用 EnterWorktree 切進 <worktree 絕對路徑>（已存在，不要新建）」，不要叫他用 VS Code 開 worktree 資料夾；範本在 `workflow/v6-inbox/_console/開工句範本.md`。

## 行動

- 派工單第 0 節寫明：先確認在 worktree、交付用 SendMessage 全文
- 總控台收到 SendMessage 交付就存進 workflow/v6-inbox/from-track-<名>/，並補跑 live porcelain
