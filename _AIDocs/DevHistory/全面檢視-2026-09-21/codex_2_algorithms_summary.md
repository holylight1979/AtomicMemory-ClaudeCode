# Codex #2（gpt-6-astra）記憶演算法 — 摘要（全文 reply_2.md，217K tokens）

結論：優先修「評估器與線上管線不一致、失效記憶被 Related 帶回、拒用被判使用」三項；不導入另一套框架。

## 本地實證（L1–L6）
- L1 已有一跳 Related BFS（wg_atoms.py:302）；但 Related 篩選不看 query，只依效用/activation，最多 6 顆（ups_inject.py:102）。
- L2 Supersedes 只掃當次命中候選；移除舊 atom 後仍把 all_atoms 傳給後段（ups_search.py:293），Related 從該池擴散（ups_inject.py:302）→ **合成案例重現：New supersedes Old，New.Related 指 Old，spread_related() 把 Old 帶回**。另：只有舊 atom 命中、新 atom 沒命中時，取代聲明讀不到。
- L3 回歸評估器 retrieve() = trigger → BM25 補位 → 零命中才 vector，**無 RRF / ACT-R / Supersedes / Related / 裁切**（tools/memory-eval/run.py:77）。實跑：193 atom、正例 175、負例 14、**34 題目標已不在索引被跳過**、R@1 64.6%、R@3 91.4%、MRR 0.774、負例誤命中 1/14；baseline.json R@1 67.0%，TECH.md:326 寫 53.6%——三處不一致。
- L4 detect_atom_use()（wg_atoms.py:1110）只看 token 重疊；**合成測試：回合文字寫「不要使用，兩者已過時」仍 used=true、containment=1.0**。成功訊號=「宣告完成且無失敗訊號」套到 used atom（stop.py:350/425）。
- L5 負面記憶格式已有（extract-worker.py:180）。
- L6 memory-effect-report.py 已有曝光/α β/token 稅；recall_miss 排除已注入。
- Wilson LB(3/3, z=1.28)=0.6468 過 0.6；z=1.28 對應 80% 雙側/90% 單側（atom_access.py:26 註解寫錯）；λ=0.97 半衰期 22.76 天。

## 前五
1. **評估器對齊線上管線**（1–2 人日）：三層量測 候選召回 / 內容送達（正文 vs cold 指標 vs 裁掉）/ 任務效果；先修 34 題失效對應，不重生題庫；測試不得更新 access sidecar。
2. **Supersedes 改全路徑不變條件**（0.5–1）：從可見有效索引池建取代關係，直接檢索、Related、最終輸出共用；處理鏈式/循環/跨 scope。（Revoked but Still Authoritative 2609.08258：暴露舊記錄 43.1% 錯誤動作 vs store-level filter 0%）
3. **效用歸因校準：拒用不算採用**（1–2）：採用/引用/拒用/修正/未知標註集；不加第二套 helpful/harmful 計數。
4. **Related 一跳 query-aware + 度數正規化實驗**：s1=(1−ρ)s0+ρPᵀs0，P 按出邊數正規化；三組對照（關閉 / 現況 / 傳播+query gate）；關閉若不差 → 砍擴散也算成果。不加全域 embedding、不把 LLM 塞進 UPS。
5. **整併只在有證據時局部更新**（2–3 實驗）：對照保留題；不用「產出幾顆 atom」當績效。
暫緩：REALM（2609.16053）邊權重學習 w←clip(w+ηc)——歸因不可靠前不做。

## 不建議
新增 spreading activation（已有）；一般反模式子系統；ACE 第二套計數；MemoryBank 遺忘曲線；整套 Mem0/Graphiti/Cognee/MemOS/Mem-α；每輪反思或整庫重寫；LLM confidence 直接更新 Related 權重；混排論文榜單。

## 未查到
新演算法在本系統的提升數字；Supersedes 回流與拒用誤歸因的真實 session 發生率；本地小模型 recognition filter 品質；14 條負例多為明顯域外題，缺「詞彙相近但不適用/舊版本/否定/跨 scope」負例。
