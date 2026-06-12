# 記憶機制靜默失效（confirmations 零增 + episodic 停擺）

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: memory-review, memory-health, confirmations, episodic, 晉升, 自我迭代, 衰減掃描, 覆轍偵測
- Created-at: 2026-05-22
- Related: decisions, decisions-architecture, workflow-rules, atom-usefulness-loop, atom-元資料編輯與晉升閘真相

## 知識

- [臨] 2026-05-22 /memory-review 發現：全 35 個 atom 的 confirmations 恆為 0，跨 session 萃取命中未回寫 confirmations。後果：decisions.md 自述的 primary 晉升軌（[臨]→[觀]≥4、[觀]→[固]≥10）實際從未生效，系統僅靠 ReadHits 輔助軌（≥20/≥50）運作。

- [臨] 連帶效應：/memory-review 衰減公式 usage=log10(confirmations+1)/2 因 confirmations=0 退化成純 recency，導致高頻 atom（workflow-rules rh=192、decisions rh=236、toolchain rh=217）被誤判為「封存候選」。判讀活躍度一律改用 read_hits 校正分數，勿信 spec 純 confirmations 分數。

- [臨] episodic 生成疑似停擺：最新 episodic=20260506，但 atom last_used 延續到 0519，中間 16 天、多個 session 無 episodic 產出（config.episodic.auto_generate=true）。震盪偵測與覆轍偵測皆依賴 episodic，停擺期間這兩個機制等於失明。

- [臨] episodic 格式漂移：最近兩個 episodic（20260506-session-work*）缺「工作區域」欄位；全庫無任何「覆轍信號:」標記 → 覆轍偵測即使 episodic 正常也抓不到東西。
- [臨] 2026-05-22 實測重大根因：_ATOM_INDEX.md 表頭「| Atom |」後只要出現一個空行，runtime hook wg_atoms._parse_trigger_table 即判定表格結束（行79: not startswith('|') → in_table=False），後面所有 atom 被忽略。實測：損壞的 working copy → parser 讀到 0 atoms（trigger 注入全死）；committed 紧湊版 → 33 atoms。這就是「從專案層用 CC 記憶對不上」的真因。
- [臨] 關鍵性質：不是「檢查技能過時」。sync-atom-index / sync-memory-index / memory-health 與 runtime hook 用的是同一個 strict parser、同一個真相源（_ATOM_INDEX.md），它們一致。壞的是「寫入端產出的格式」違反 parser 的紧湊假設（表內不得有空行）。寫入端有兩個（MCP server.js / lib/atom_io.py）+ batch 重組（sync-memory-index / atom-move），任一次留下空行就 silent 讀 0。
- [臨] 為何專案層更常中招：atom_write 預設 scope=shared→寫專案層索引；跨層 atom_move/reconcile 會重寫兩層索引（本 session move linemate 即觸發 working-copy 重寫）。寫入頻繁 + 較新 → 更高機率被插入空行 → 該專案 atom 全不注入。
- [臨] 預防方向（需動 hook+MCP，待另 session）：(1) 讓 parser 容忍空行（遇空行 skip 不 break，或改成掃全文 | ... | row regex），同步改 wg_atoms.py + sync-*.py；(2) SessionStart 加 fail-loud：某層 _ATOM_INDEX 存在但 parse 出 0 atoms → 警告（現在 silent）；(3) 寫入後跡 sync-atom-index --check gate。
- [臨] **簽章更新（2026-06-12）**：「confirmations 零增」項已過時——Phase 2 usefulness Wilson 接管晉升後 confirmations 恆 0 屬正常（詳 [[confirmations-已退役-phase2-usefulness-接管晉升]]）。現行有效活性指標：useful_hits/used_fail 增長 + _meta/atom_io_audit.jsonl 追加 + episodic 檔日期。勿再拿 confirmations=0 誤報失效。

## 行動

- 開 session 查 SessionEnd / generate-episodic hook 為何 2026-05-06 後停產

- 開 session 查跨 session 萃取流程為何不回寫 confirmations（primary 晉升軌依賴）

- 修復前，/memory-review 與 /memory-health 判讀 atom 活躍度一律以 read_hits 為準

- 後續 episodic 生成須補齊「工作區域」欄位與「覆轍信號:」標記
