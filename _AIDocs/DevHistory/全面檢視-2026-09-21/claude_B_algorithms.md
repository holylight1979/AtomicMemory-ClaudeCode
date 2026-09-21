# Claude 審查者 B：記憶演算法研究（2025H2–2026）— 摘錄

總結：這一年共識是「什麼時候不要注入」——錯誤注入比不注入更糟（append-only 0.21 vs 無記憶 0.31；always-inject 誤注入 17.5%；長上下文 42.6→19.0）。既有檢索管線已是同級最完整，缺口在**注入決策層、撤銷生命週期、負向回饋訊號**。

## 排序前五
1. **注入決策層（RSCB-MC 棄權 + Memory-as-Infrastructure 精準級聯）** arxiv 2604.27283 / 2609.05510
   - 不注入是一等公民；獎勵不對稱 γ(誤注入罰)>α(成功)>β(接受)=4>2>1；`S = R̂ − μ·p̂_fp − λ·ĉ`。
   - 便宜特徵：top1/top2 分、score_margin、候選熵、候選數、IDF 稀有詞重疊、本 session 被糾正次數、歷史誤報率、剩餘預算。
   - 級聯：意圖閘（build/investigate/decision 才檢索）→ IDF 相關閘 → per-session 同 atom 重複阻尼 → 系統回合豁免。
   - 每次 hook 先寫心跳（量分母）。78,933 次呼叫 85 次失敗。
   - 實測：靜態混合 50% 成功 / 17.5% 誤注入 / hard-negative 75% 誤注入 → RSCB 62.5% / 0% / 0%。
2. **TEPA 衝突鍵 + Beta-Bernoulli 撤銷** arxiv 2608.07429：先例 p=(k,v,s,f,σ,τ)；q=(s+1)/(s+f+2)；觀測≥5 且 q<θ_rev 或最近 3 次成功率<0.34 → Revoked（歸檔不刪）。0.950 vs append-only 0.210 vs 無記憶 0.309。
3. **負向回饋（ACE harmful 計數 + Hindsight 矛盾 −2α）** arxiv 2510.04618 / 2512.12818：bullet=id+helpful+harmful；Curator 只出 delta，確定性合併；整份重寫 collapse（18,282→122 tok，66.7%→57.1%，低於不學的 63.7%）。信心：強化 +α、弱化 −α、矛盾 −2α。Hindsight：RRF 後 cross-encoder MiniLM-L6 CPU ms 級。
4. **寫入節流（SAGE 自適應新穎度閘 + RecMem 復現觸發）** arxiv 2605.30711 / 2605.16045：vMF 核密度新穎度 ν；門檻 τ_t = τ_min + τ_0·e^(−λρ_t) 隨庫密度收緊；只灰帶送 LLM（省 3.4×）。RecMem：sim≥0.6 且復現≥4 才 LLM 鞏固成 atom（token −87%）。
5. **SYNAPSE 擴散啟動三件套** arxiv 2601.02744：u^(t+1)=(1−δ)a + Σ S·w·a/fan(j)，δ=0.5、S=0.8、fan=出度；側向抑制 top-M=7、β=0.15；S=0.5·sim+0.3·act+0.2·PR；**τ_gate=0.12 拒答閘**（Adversarial 96.6 vs A-Mem 50.0）。
排名外快贏：**constraint pinning**（Governance Decay arxiv 2606.22528）：compaction 後違規 0%→30–59%，軟規則掉 +50pp；≤50 tok 釘回硬規則 → 0%。

## 其他可補強
- Generative Agents：反思由「累積 importance >150」觸發而非排程。
- Letta sleep-time：handoff 後預產 3–5 條預期問答。
- LightMem：先軟寫 + pending，離線批次過閘。
- DeMem：Trigger 偏「什麼條件做什麼決策」而非「發生了什麼」。
- TrustMem：自動萃取加 faithfulness（每句可回溯來源）。
- Mnemis：MEMORY.md→_INDEX→atom 階層當第四路（只適合顯式 recall）。
- Memory Beyond Recall：週健檢把新 [臨] 聚類歸納高階 atom（效果小）。
- Graphiti：世界有效期 vs 寫入時間。
- claude-mem：cold 表加「展開要多少 token」欄。
- ECC：同 atom ≥2 專案且信心 ≥0.8 → 自動升 global。
- Agent-native memory（2606.24775）：保留原文 > 壓縮；episodic 摘要不要取代原文；保守局部及時鞏固 > 延後整批。

## 刻意不推薦
完整 KG（HippoRAG/Zep/Cognee >116s）、RL 訓練類、永久刪除類（FSFM/FadeMem）、MRAgent 多輪 LLM、MaTTS。
