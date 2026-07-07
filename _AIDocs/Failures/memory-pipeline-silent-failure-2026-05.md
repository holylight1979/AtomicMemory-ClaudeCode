# 記憶機制靜默失效（confirmations 零增 + episodic 停擺）

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: memory-review, memory-health, confirmations, episodic, 晉升, 自我迭代, 衰減掃描, 覆轍偵測
- Created-at: 2026-05-22
- Related: decisions, decisions-architecture, workflow-rules, atom-usefulness-loop, atom-元資料編輯與晉升閘真相, confirmations-已退役-phase2-usefulness-接管晉升, 自動萃取層淨值審查-調整式拔除-2026-07, 原子記憶審查總結-好機制被小故障卡死非過重-拔前先實證

## 知識

- [臨] **索引表 parser 空行陷阱**：`_ATOM_INDEX.md` 類 pipe 表格的 strict parser 一遇表內空行即判表格結束，後面所有 atom 靜默讀 0（trigger 注入全死）。寫入端（MCP server.js / lib/atom_io.py）+ batch 重組（sync-memory-index / atom-move）任一次留下空行就中招。現行防線：`wg_atoms._parse_trigger_table` 與 `parse_aidocs_index` 表內空行 skip 不結束（回歸鎖定 `verify_trigger_table_blank_tolerance.py`）；`session_start` 有 `[Guardian:IndexZero]` fail-loud（index 存在但 parse 0 atom → 警告）。診斷「某層 atom 全不注入」先查此。
- [臨] **管線活性指標判讀**：判斷記憶管線是否活著，看三件事——① episodic 檔日期（兩層都要有近期產出）② `memory/_promotion_audit.jsonl` 尾巴有無新事件 ③ access sidecar 的 `useful_hits`/`used_fail`/`read_hits` 是否增長。**勿拿 confirmations=0 誤報失效**：confirmations 軌已除役（唯一資料源停產），庫內殘存計數為凍結歷史值、`confirmation_events` 恆空屬正常。衰減/活躍度判讀一律以 read_hits 校正分數為準，勿信純 confirmations 公式。

## 行動

- 診斷「atom 全不注入」：先驗 index 表內空行與 `[Guardian:IndexZero]` 告警，再懷疑其他
- 判管線健康：episodic mtime + promotion_audit 尾巴 + access useful_hits/read_hits 增長；不用 confirmations
