# feedback-completion-gates

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: 完成宣告, 收尾, pytest, run_verify, verify, smoke test, 研究先行, trial-and-error, 清理, 先清後建, 基線, 測試上傳, 上 SVN, known regression, xfail, 衍生暫存, 暫存檔, 清暫存, 收尾檢核
- Created-at: 2026-05-26
- Related: feedback-workflow-discipline, feedback-tooling-reliability, 自己flag的維護動作直接做完不要反問, handoff-綜觀品質與抗失真寫法, feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長, cognitive-patterns, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, 巨檔純機械拆分-carve腳本與驗證盲點, 專案工作驗收裁判的分級啟動與殺閘設計, 並行agent產出併入交付物必須標驗證強度分層, 歸因早停-找到合理嫌疑機制就停止驗證, hud暫存清單靠prose猜路徑的失敗-改殘檔帳本以檔案系統為權威, 背景驗證未收就結束回合-stop閘裁判只看當下事證不看未來承諾, 多phase計畫的驗收規格要一開始就標phase-否則分session收尾會被裁判當全案未完

## 知識

- [觀] 宣告完成前跑 `python run_verify.py`（H-test-prune 後取代 `pytest tests/`；動態掃 hooks/verify/、tools/verify/、tools/codex-companion/verify/、lib/verify/、skills/{name}/verify/）；失敗逆向分流（相關→修 / 無關≤ 5 行→順手修 / 無關超門→known-regression）
- [觀] 測試 / 練習碼禁上 SVN/GIT，tests/__tests__/Test.* PreToolUse hook 擋
- [觀] 修復失敗 ≥ 2-3 次啟動網搜，不躺溝 trial-and-error
- [觀] 重構先清殘骩到 _archive/{date}/，跑乾淨 baseline 確認
- [觀] 整合 / 上線手動 E2E smoke + 肉眼確認 output
- [觀] xfail / known-regression 必附：原因 / 何時修 / 收尾清單
- [觀] 完工後清暫存：每個需求/任務完成宣告時，AI 必列「衍生暫存清單」（IDENTITY 收尾 (d)），**預設直接刪**。例外只在 user 明確標「保留？」項。
- [觀] 衍生暫存判定 = 工具自動產生 + 無 git track + 無人工填值 + 僅服務當次任務。例：`.pytest_cache/` / `backups/.claude.json.backup.*` / `.playwright-mcp/` / `workflow/companion-*.json` / `workflow/state-*.json` / `_staging/next-phase-*.md`（已執行完者）/ `tmp/` / `downloads/` / `cache/` 內 ad-hoc 檔。**不算**：source code / `_AIDocs/` 知識庫 / `memory/` atom / `workflow/config.json` 等 tracked 設定 / persistent SOP `_staging/next-phase-{name}.md`（檔頭聲明保留者）。
- [觀] 收尾檢核四項（IDENTITY）：(a) 缺失修補清單必寫 / (b) AI 逃避通報僅發生時寫 / (c) Token 巨量警示僅發生時寫 / (d) 衍生暫存清單必寫。全項必檢視，非擇一。
- [觀] `plans/{slug}.md`（Plan mode 自動產出，任務完成後）屬衍生暫存：gitignored + 自動產出 + AI 撰寫 + 僅服務當次任務四要件全中 → 預設刪。**禁用「設計慣例 / 訂規保留」等籠統話術自我合理化**；唯一例外：plan 內含長期參考價值的設計決策時，先抽到 `_AIDocs/` 對應目錄再刪 plan，禁原地保留。
- [觀] 背景任務（測試/build）還在跑時的回合末狀態小結，若用「已落地的改動」條列式寫法會被驗收裁判讀成完成宣稱而擋收尾（2026-08-14 V1 看圖實例）。正解：等得到結果就用 TaskOutput 阻塞等完再續作，不提前結束回合；非結不可時期中報告首句明寫「尚未完成、等候中」且不用完成式句型。
- [觀] anti_evasion_report (d) 是「給使用者裁決的路徑清單」，不是備註欄：只寫此刻尚存、需人決定的路徑（一行一路徑 `<路徑> — <備註>`）；已刪的、系統執行期狀態檔（如 workflow/aec-tempfiles 帳本）、解釋性文字一律不寫，無就寫「無」——括號補述會被 HUD 當成一列要人裁決，使用者看到不認識的檔名還得反問「這是什麼」（2026-08-25 實際發生）。Python one-writer 已把「無（…）」正規化成「無」兜底，但正解是不寫。

## 行動

- 完成前跑 run_verify.py（H-test-prune 後取代 pytest tests/）
- 測試碼不上版控
- 修復失 ≥ 2 走搜尋
- 重構先清 _archive
- 上線 smoke + 肉眼
- 完工列衍生暫存清單 + 預設刪
