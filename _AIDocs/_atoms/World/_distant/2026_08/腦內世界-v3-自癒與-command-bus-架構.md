# 腦內世界 v3 自癒與 Command Bus 架構

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 腦內世界, atom-heal, 記憶自癒, command bus, world.html, jobRunner, _heal_review, heal-review
- Created-at: 2026-06-02
- Related: guardian-dashboard-孤兒佔埠與新碼重啟, decisions-architecture, toolchain-ollama, reconcile-render-動畫狀態歸屬陷阱, 腦內世界-環境演化-放置式架構, 腦內世界生物對話系統真相-模型觸發方針背景

## 知識

- [臨] 記憶自癒 tools/atom-heal.py 是單一來源：分級 L1 reverse_refs 機械補(免 LLM) / L2 broken_refs 呼 LLM 出結構提案再經 funnel 套用 / L3 stale 唤醒。重用 atom-health-check.py(importlib 載入、single_atom_report 偵測+--atom 過濾) + lib.atom_io.edit_metadata(source=tool:atom-heal) + lib.atom_spec.validate_atom_content + tools/ollama_client.get_client。
- [臨] LLM 後端可插拔：config.json heal.backend 預設 ollama(本地免費序列 max_concurrent=1)；cloud 為選配(並行 cap=N，adapter 未實作→退 needs_human)。安全：repoint 只能指真實候選、LLM 失敗/不確定一律 needs_human、禁盲刪死連結。本地 crack 模型 format=json 仍加 ```圍欄 → _extract_json 剥除。
- [臨] 修不好(驗證不過/needs_human) → atom-heal 寫 memory/_heal_review/<atom>.json 診斷卡 + audit append _merge_history.log；/heal-review skill(tools/heal-review.py) 人工裁決 resolve(重掃確認健康才清卡)/dismiss，需 management。
- [臨] server.js：抽泛用 makeJobRunner(maxConcurrent/ttl) + execJson 重構 testJobs，heal 路由群(/api/heal/:atom?auto=1, heal-job, heal-all, heal-review)與 test 共用。spawn atom-heal 前以 ATOM_NAME_RE 擋 shell 注入。改 server.js 需走重啟 SOP（見 [[guardian-dashboard-孤兒佔埠與新碼重啟]]）。
- [臨] world.html：(1) 個性 personaOf(類別×年資×狀態→sys prompt、不增 LLM 呼叫) (2) 自主 wander + sickWalk(生病生物自走診所觸發自動 L1) (3) dialogueDirector 對話節流(共用 chatBusy、速率封頂) (4) 單一 WORLD_COMMANDS registry 衅生選項式指令台+executor+/api/world-* poll。autoOn 總開關；自主只跑免費 L1，L2 需手動。
- [臨] 誠實痊癒原則：前端只有 server 回 fixed 才移 .sick（收緊 healed Set）；修不好貼 .bandaged 🩹 「轉診人工」不假裝痊癒。詳細架構見 _AIDocs/Architecture.md。

## 行動

- 改 atom 修復邏輯 → 動 atom-heal.py(唯一來源)，勿在 server.js/JS 重寫
- 加新指令 → world.html WORLD_COMMANDS 加一筆（UI/說明/executor 自動長出）
- 改 server.js 後走重啟 SOP 才生效
- 自癒品質不足 → config heal.backend 升 cloud（需接 adapter）


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-08-05 | --enforce 自動淘汰 (34d > 30d) | memory-audit --enforce |
