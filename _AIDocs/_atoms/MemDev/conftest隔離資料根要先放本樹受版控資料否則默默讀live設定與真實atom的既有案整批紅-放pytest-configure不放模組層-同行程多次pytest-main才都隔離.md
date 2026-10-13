# conftest隔離資料根要先放本樹受版控資料否則默默讀live設定與真實atom的既有案整批紅-放pytest-configure不放模組層-同行程多次pytest-main才都隔離

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/from-track-data-root-2/001-data-root-2-done.md 第 15、16 條；003-002-done.md
- Confidence: [臨]
- Trigger: conftest 隔離資料根, WG_CLAUDE_DIR 導走, pytest_configure, 種子資料, 默默讀 live, lib/verify 70 紅, pytest.main 多次, 測試寫live 記憶, wg-iso
- Created-at: 2026-10-13
- Quote: 「你是 v6.0 的「調度」總控台（新任，接 claude-aa；對人總控台見接續單「現任」行）。職責：派工、對帳、快照複跑、合併、推送、刪樹刪分支、與各工作 session 通訊；不改碼、不開子代理、不回答原設計者。第一步 ToolSearch 載入 SendMessage 與 ListAgents，ListAgents 看自己的名字，SendMessage claude-aa 與對人總控台各一…」

## 知識

- [臨] 實踩（track-data-root-2）：在 repo 根 conftest.py 把 WG_CLAUDE_DIR（資料根）與 TEMP／TMP／TMPDIR 導到暫存目錄後，lib/verify 從全綠變 70 紅——那些案以前其實默默讀 live 的 taxonomy、詞庫與真實 atom。正解：隔離資料根要先放本樹受版控的資料（git ls-files 的 memory/、_AIDocs/_atoms/、workflow/config.json；向量庫與稽核紀錄不拷），在 worktree 裡驗到的就是本分支自己的資料；代價每次 pytest 啟動多約 1.4 秒。
- [臨] 放在 pytest_configure 不放模組層：同一行程連跑兩次 pytest.main 時 conftest 被快取，模組層只跑一次。pytest 開始前已載入的本樹模組（常數已算好）改不到，要在 stderr 列出；各層 conftest.py 會被 pytest 先載，不算預載。暫存目錄名不含 test（有案要「路徑不含 test 字樣」）。同輪載入第二支 conftest 會換掉 sys.modules['conftest']，找根 conftest 要用 request.config.pluginmanager.get_plugins() 比 __file__。
- [臨] 整組 pytest 自寫收據只在目標恰好是整組、沒篩（-k／-m／--deselect／--lf）、沒 --ignore／--collect-only、沒 -o 覆寫收集設定（python_files 等）、沒 -c 別的 ini、跑完全綠才寫，寫到 pytest 啟動時的資料根。

## 行動

- 写 conftest 導走資料根時：先放本樹受版控資料再跑既有 verify 看翻紅數；用 pytest_configure；預載模組要出聲
- 在多層 conftest 的樹找根 conftest 不看 sys.modules，看 pluginmanager
