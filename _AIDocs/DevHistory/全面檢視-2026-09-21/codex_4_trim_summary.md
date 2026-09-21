# Codex #4（gpt-6-astra）精簡審查 — 摘要（全文 reply_4.md，345K tokens）

結論：局部精簡（重複產物、重複啟動、重複規範）；無證據支持拔整個子系統或 Stop 閘。31 個 Python 檔 15,759 行 AST 引用盤點：14 個 wg_* 都有匯入端；孤兒只 4 個 helper 64 行（0.4%）。

## 候選
1. **孤兒 helper + 無讀取端設定**：`_parse_atom_index_file`（wg_atoms:152）、`build_atom_df`（wg_atoms:1079 ← 注意 Codex #5 建議把它接進 Stop 歸因，所以不是刪而是接線）、`get_scope_dir`（wg_core:373）、`get_project_claude_dir`（wg_core:413）；config `heal.run_full_verify`（:337）無讀取端、`world_dev`（:350）為宣告鏡像。64 行 + 21 行設定。
2. **PostToolUse 四支程序合併**（settings:97）：一次 Edit/Write 啟動 guardian、codex companion、version_guard、acceptance_spec；後兩支各自重做 stdin/JSON/config；可讓 guardian 共用入口跑兩個輕檢查（需改 sys.exit 為回傳、matcher 取原範圍）。空 Python 子程序啟動中位 311ms（233–654ms）；hook 可能並行，不能直接乘。1–2 人日中風險。
3. **read-project 詳細目錄只存一份**（SKILL:78/114/134）：有 _AIDocs 時 atom 只留主題+摘要+文件錨點。
4. **skill 長範例/備援程式按需讀取**：browse-sprites 內嵌備援 40 行/447 tok；handoff 長範例 39 行/579 tok。
5. **規範單一權威版本**：Architecture.md 自稱索引卻含大量機制細節且與 TECH 矛盾（可減 150–250 行）；memory skill `--self-iterate` 不存在；memory:25 vs :153 矛盾。
6. **always-load 只修剪純說明句**：IDENTITY:6 與 core:3 兩段「本檔留什麼」共 167 tok；需同步 template、跑 verify_always_load_contracts.py。
7. **upgrade 降 dormant 暫緩**：V4/V5 遷移流程（行數判版本、掃舊 commands/），368 行；需先確認所有機器版本。

## 前五（Codex 排序）
read-project 去重 → PostToolUse 合併（事件等價回放）→ skill 按需讀取 → 收斂 Architecture/skill 規範 → 清 64 行孤兒 + 21 行設定。

## 不建議
設定 false 就刪整功能（architecture_review 仍有事件判定；forget 有 memory-audit 手動路徑）；Stop 各閘硬併（可共用 transcript 取文：lang_guard 缺訊息時掃整份 transcript 是次順位效能候選）；為減數量合併 debug/手動 skill；合併 tools CLI（sync-atom-index vs sync-memory-index 責任不同；tools 90 支含 verify 28 支）；大砍 always-load（MEMORY.md 19 行是 hook 全掛時導航保底）；刪零曝光 atom。

## 未查到
真實 hook 加速幅度；其他機器外部引用；TECH:378 寫全量萃取「在跑」但 session_end.py:208 受停用設定控制（文件≠執行事實）；本輪只靜態 AST，無行為回歸。
