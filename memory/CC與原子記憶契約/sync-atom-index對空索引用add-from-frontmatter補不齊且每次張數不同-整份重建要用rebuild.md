# sync-atom-index對空索引用add-from-frontmatter補不齊且每次張數不同-整份重建要用rebuild

- Scope: global
- Author: holylight
- Source: session 26d36367 track-wave2-kit 派工 003（w2_build_env 實跑）
- Confidence: [臨]
- Trigger: sync-atom-index, add-from-frontmatter, --rebuild, 重建索引, 索引張數不對, _atom_index.json, 資料根建索引, 複製卡片進新資料根
- Created-at: 2026-10-21

## 知識

- [臨] 把一批卡複製進一個沒有索引的新 memory 目錄後，`tools/sync-atom-index.py --add-from-frontmatter` 補不齊：同一批 291 張，三個目錄各補出 130／97／142 張，每次跑結果還不一樣；drift 報告照樣列出缺的。
- [臨] 整份從磁碟重建用 `--rebuild --fix-scope-from-path --sync-depends`：連跑兩次都穩定 291 張；只剩 depends 漂移時加 `--sync-depends` 收掉。之後再跑 `tools/sync-memory-index.py --memory-dir <dir> --write` 產 MEMORY.md。兩支都吃 WG_CLAUDE_DIR。
- [臨] 根因沒追（逐張 upsert 每次讀寫整份 JSON 的路徑），已交根層寫碼 session 當追蹤項。

## 行動

- 新建或整批搬卡進一個 memory 目錄 → 用 --rebuild，不用 --add-from-frontmatter
- 建完一定核對索引張數 ≥ 預期，不信工具的 rc
