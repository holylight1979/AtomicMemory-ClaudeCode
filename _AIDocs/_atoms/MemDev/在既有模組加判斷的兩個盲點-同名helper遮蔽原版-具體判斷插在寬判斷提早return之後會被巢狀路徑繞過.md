# 在既有模組加判斷的兩個盲點-同名helper遮蔽原版-具體判斷插在寬判斷提早return之後會被巢狀路徑繞過

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/from-track-a3/002、004 與 a3 session（claude-bd）2026-10-12 交來的 post-mortem 素材
- Quote: 「<cross-session-message from="uds:\\.\pipe\LOCAL\cc-msg-f65dfa633704a56010b93d33252c51f9" from-name="claude-bd" from-mode="bypass"> a3 收尾時 DeepPostMortem 要我用 atom_write 補一張 post-mortem，但 000-prompt 第…」
- Confidence: [臨]
- Trigger: 同名函式, 遮蔽, shadow, 提早 return, 判斷順序, 根層 worktree, 巢狀 worktree, is_root_worktree, detect_layer, _layer_of, 長路徑前綴, UNC, 大小寫
- Created-at: 2026-10-12

## 知識

- [臨] 盲點一：在既有模組新增 helper 沒先 grep `def <名字>`。一條工作軌在 `lib/overview_hub.py` 新增 `_same_dir`（realpath＋小寫），檔內第 79 行已有同名原版（resolve 判法），Python 取後定義那支，`find_map` 的家目錄與 stop_at 比較被悄悄換掉，所有權外的行為變了、測試全綠。正解：新 helper 名字帶用途後綴（`_same_dir_norm`），並加案用 `inspect.getsource` 對比原版一字未動。
- [臨] 盲點二：「更具體」的判斷放在「較寬」判斷的提早 return 之後。`overview_scaffold.detect_layer` 先看 `_layer_of`（依路徑包含判層：在 ~/.claude 之下＝根層）就 return，根層 worktree 判斷放在後面；worktree 開在 ~/.claude 之下時（Claude Code 原生 `EnterWorktree` 就開在 `<repo>/.claude/worktrees/`）先被判成 (root, live)，拒寫比 live 對 live 得 False，`--write` 寫進 live。斷點在順序不在判斷本身：「路徑包含」預設根之下不會有另一棵獨立的樹，worktree 打破這個前提，所以更具體的 `is_root_worktree`（兩張部位表位元組相同）要先判。
- [臨] 附帶：路徑前綴字串比對要不分大小寫（`\\?\unc\` 與 `\\?\UNC\` 都合法，分大小寫會把小寫版剝成相對路徑）；對 UNC 路徑 realpath 在伺服器不存在時約卡 7 秒，測試用 localhost 不存在的分享（0.04 秒）。始末見 DevHistory `v6.0-寫程式碼的進化-2026-10/工作紀錄.md` a3 段（原信已隨信箱清理刪除）。

## 行動

- 在既有模組新增函式前先 grep `def <名字>`，helper 名字帶用途後綴
- 加更具體的判斷時放在所有較寬判斷的提早 return 之前，把具體情況可能出現的位置（獨立目錄、根之下、公司根之下）逐一列成測試
- 路徑前綴比對一律不分大小寫，測試要有大小寫變體
