# conftest隔離資料根要先放本樹受版控資料否則默默讀live設定與真實atom的既有案整批紅-放pytest-configure不放模組層-同行程多次pytest-main才都隔離

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/from-track-data-root-2/001-data-root-2-done.md 第 15、16 條；003-002-done.md
- Confidence: [臨]
- Trigger: conftest 隔離資料根, WG_CLAUDE_DIR 導走, pytest_configure, 種子資料, 默默讀 live, lib/verify 70 紅, pytest.main 多次, 測試寫live 記憶, wg-iso
- Created-at: 2026-10-13

## 知識

- [臨] 實踩（track-data-root-2）：在 repo 根 conftest.py 把 WG_CLAUDE_DIR（資料根）與 TEMP／TMP／TMPDIR 導到暫存目錄後，lib/verify 從全綠變 70 紅——那些案以前其實默默讀 live 的 taxonomy、詞庫與真實 atom。正解：隔離資料根要先放本樹受版控的資料（git ls-files 的 memory/、_AIDocs/_atoms/、workflow/config.json；向量庫與稽核紀錄不拷），在 worktree 裡驗到的就是本分支自己的資料；代價每次 pytest 啟動多約 1.4 秒。
- [臨] 放在 pytest_configure 不放模組層：同一行程連跑兩次 pytest.main 時 conftest 被快取，模組層只跑一次。pytest 開始前已載入的本樹模組（常數已算好）改不到，要在 stderr 列出；各層 conftest.py 會被 pytest 先載，不算預載。暫存目錄名不含 test（有案要「路徑不含 test 字樣」）。同輪載入第二支 conftest 會換掉 sys.modules['conftest']，找根 conftest 要用 request.config.pluginmanager.get_plugins() 比 __file__。
- [臨] 整組 pytest 自寫收據只在目標恰好是整組、沒篩（-k／-m／--deselect／--lf）、沒 --ignore／--collect-only、沒 -o 覆寫收集設定（python_files 等）、沒 -c 別的 ini、跑完全綠才寫，寫到 pytest 啟動時的資料根。
- [臨] 連帶的判讀坑：活體守門（掃索引內每張卡的案）在 pytest 下讀的是這份種出來的暫存資料根；在 worktree 跑時種子取自 worktree 的受版控檔，也就是分支基底那次 commit 的卡，不是 live 工作樹。守門紅不代表 live 現在髒（live 可能已清、只是基底仍是舊版）；要看 live 現況就標 live_data 或直接跑掃描工具本身，回報前別把它講成 live 的問題。
- [臨] verify 檔的直接跑入口（`if __name__ == "__main__"` 裡同行程 pytest.main）也會漏隔離：本檔先以 __main__ 載入、頂層 import 的 wg_core 在 conftest 改資料根之前就算好路徑，pytest 收集同一支檔時沿用這份舊模組，資料根與 git 錄音序列跟著執行位置變（帶 WG_CLAUDE_DIR 跑時看不出來；pytest 跑法綠、直接跑紅）。直接跑入口一律 `subprocess.run([sys.executable, "-m", "pytest", __file__])` 開乾淨子行程再印哨兵。
- [臨] 只換 wg_core.WORKFLOW_DIR 不夠：用 `from wg_core import WORKFLOW_DIR` 的模組（wg_harvest、handlers/post_tool_use…）各存一份常數，同一行程先載入模組再 pytest.main 時這些常數指到正式資料根，追蹤帳本、工具結果帳就漏進去；案例要把這些模組的常數一起 monkeypatch。重現法：子行程設假資料根、先 import 這幾支、再 pytest.main，查假資料根有沒有長檔。


## 行動

- 寫 conftest 導走資料根時：先放本樹受版控資料再跑既有 verify 看翻紅數；用 pytest_configure；預載模組要出聲
- 在多層 conftest 的樹找根 conftest 不看 sys.modules，看 pluginmanager
