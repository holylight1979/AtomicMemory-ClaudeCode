# Claude 審查者 F：萃取／晉升／遺忘迴路內審 — 摘要（63 次工具呼叫，192K tokens）

## 已實證的缺陷
1. **效用歸因假陽性三來源**（stop.py:386-482、wg_atoms.py:1110-1157）：
   (a) `get_current_turn_text`（wg_evasion.py:605-660）把所有 tool_use input 字串攤平，含 **Agent/Task 的 prompt 欄前 2000 字**；parent 派工時 `[WG:SubagentMemory]` 把 atom 原文塞進 prompt → atom 必中。wg_rescue.py 明文排除此欄，歸因端沒有。
   (b) `build_atom_df`（wg_atoms.py:1085）寫好但**全 repo 零呼叫**，stop.py 未傳 df_map → IDF 過濾從未生效。（與 Codex #5 #4 同一發現；Codex #4 把它列為孤兒 helper——正解是接線不是刪）
   (c) 「2 個共享 token」對中文 bigram 太低。
   實測 session 094f7ab1：turn 1 注入 9 顆判用 10 顆；turn 6 注入 4 顆判用 9 顆 → 基本全判用，α/β 退化成「turn 成敗率」。87 顆 n≥3 平均成功率 0.629 貼著 turn 成功率。rescue-log 已有 638 筆高精度「工具參數命中 atom 專屬 token」證據（115 顆）只餵報表不餵 α/β。
2. **outcome 訊號 session 級污染**（stop.py:347-371）：`wisdom_retry_count` 只在 wisdom_engine.py:317 遞增、無重置點 → 一場 session ≥2 後每 turn 皆 fail，所有判用 atom 吃 β。outcome unknown 43%（50 場 402 turn、172 unknown）。wg_friction 的使用者糾正訊號只餵 DPM 未餵 outcome。
3. **晉升門檻與 decay 時序耦合**（wg_atoms.py:2454-2466）：SessionEnd 先 decay（α←1+0.97(α−1)）再判 n≥3 → 3 勝當日首次 SessionEnd n=2.91 不升，隔天更少，除非第 4 勝；`record_usefulness` 無 per-(atom, session) 去重 → 同 session 三 turn 即達 3。Wilson：3/3→0.647 ✔、4/5→0.514 ✘、6/7→0.623 ✔（只有連勝能升）。同日連跳殘留：未見。
4. **episodic「停擺」根因（非管線失效）**：
   - 程式 09-03 後未變；無 generation failed 例外。
   - 09-18 兩場 cwd=C:\TSLG → episodic 寫到 **C:/TSLG/.claude/memory/episodic/**；`health-weekly.py:228` 只算 ~/.claude/memory/episodic → 專案層產出不計。
   - 今日 094f7ab1 正常產出 memory/episodic/episodic-20260921-guardian.md → 管線活著。
   - 今日 8 個 state 中 6 個 modified=0 且 accessed=0（sub-agent／唯讀）→ `_should_generate_episodic`（wg_episodic.py:54）False；`accessed_files` 只從 Read tool_use 回收，bypass 模式用 cat 讀檔 → 恆 0 → 唯讀研究 session 永不產 episodic。
   - 長壽 session（09-18 開 09-21 關）SessionEnd 稀少；skip 原因沒落 log；舊 state 已被 `_cleanup_old_states` 清掉無法鑑識。
   - 順帶：`wg_recall_miss.py:90` 09-10/09-18 四次 SessionEnd 丟 `AttributeError: 'str' object has no attribute 'get'`（knowledge_queue 含 str）→ recall-miss 靜默失效。
   改法（0.2 人日）：health-weekly 併計專案層；`_should_generate_episodic` 加 turn_seq≥3 替代條件並在 False 時 `_atom_debug_log("episodic:skip", 原因)`；recall_miss 加 isinstance 護欄。
5. **Detached worker 死活不可分**：extract-worker.log 最後 09-15 只有重複行無 start/end；`session_end_flush.enabled=false` 使 SessionEnd 全量 worker **根本不 spawn**（session_end.py:242）——TECH §6.3「在跑」不準（Codex #4 同發現）；實跑的 LLM worker 只有 failure（UPS）與 user-extract。user-extract 有 `_merge_history.log` 198 筆（最新 09-18）。
6. **provenance**：user-extract 已寫 `<!-- src: {sid}-{turn} -->`（庫內 11 顆）；failure 萃取沒有。改 `_extract_all_assistant_texts` 回傳 (line_no, text)，知識行附 `<!-- src: {sid[:8]}-L{line} -->`（0.5 人日，best-effort）。
7. **selective forget 保護清單**（wg_atoms.py:2127-2146）只 import EXACT（preferences/cognitive-patterns），未用 `is_core_protected_name`（含 prefixes decisions*/workflow-*/feedback-*）；usage 項不看 β。目前 dry-run 無實害。一行改。
8. **衝突偵測無量測**：SessionEnd `_detect_atom_conflicts` 只 vector 0.60–0.95、不過 LLM、只印 stderr；audit.log 896 行無任何 AGREE/CONTRADICT 判定持久化。pending 幾乎空。
9. demote 候選 17 顆（n≥5 且 lb≤0.35）含 realm-範疇分區機制-v5、toolchain-ollama 等核心參考，β 來源正是 #1/#2 污染 → 上游沒修前維持人裁決。

## 前五
1. 歸因假陽性三合一（0.5 人日）：turn_text 跳過 Agent/Task prompt 欄；接 build_atom_df；rescue-log 命中=used 高置信，lexical 只在無 rescue 時用且 rare_token_min 2→3。指標：判用/注入 從 ≈1.0 降到 <0.5。
2. outcome 修正（0.3）：wisdom_retry_count 本 turn 差分；pending_attribution 延到下一 UPS 看 friction 糾正再結算。
3. 晉升確定化（0.2）：先判 eligible 再 decay（或 last_used==today no-op）；record_usefulness per-(atom, session) 去重。
4. episodic 量測與閘門（0.2）。
5. worker 起訖 log `Logs/worker-runs.jsonl` + forget 保護一行（0.3）。

## 不建議
per-line α/β；LLM importance 進排序；自動執行降級/遺忘；擴大 SessionEnd 衝突偵測接 LLM；重構 worker lease/heartbeat。
