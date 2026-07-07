# 模型行為移植-Fable行為契約必載檔

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 模型切換, Opus, Fable, 行為契約, 自動推進, 抓重點, IDENTITY 擴充, 行為移植, model behavior
- Created-at: 2026-07-07
- Related: 自己flag的維護動作直接做完不要反問, feedback-workflow-discipline, workflow-parallel-agents

## 知識

- [臨] 「抓重點、自動推進、自主觀察、收尾完整」這類高階工作風格大半是**行為協議**而非純模型智力，可用必載硬契約在較保守模型（如 Opus）上重現約 8 成。契約本體在 `IDENTITY-holylight.md`（5 節：意圖優先 / 自動推進 / 自主觀察背景執行 / 收尾完整性 / 表達校準），由 CLAUDE.md @import 每 session 必載。
- [臨] **不能靠記憶補的**：底層推理深度、長 context 單次抓取準度、模糊語句意圖解析力——屬模型權重層差異。若 Opus 在同契約下仍反問過多/推進不足，優先檢視契約條文是否被稀釋，而非再加規則。
- [臨] 「每 session 都需要」的行為規範必須放**必載檔**（CLAUDE.md @import 鏈），不能放 trigger 注入 atom——行為類需求沒有可靠的觸發關鍵字時機。atom 只放場景觸發式的細節模式。
- [臨] 踩坑：`IDENTITY-{user}.md` 個人擴充槽在文件（DocIndex-System.md）宣稱 @import，但 CLAUDE.md 實際從未 import，且檔案內容只是 IDENTITY.md 複本——擴充槽長期無效。2026-07-07 已修：改寫為真擴充內容 + CLAUDE.md 補 import。教訓：宣稱的載入鏈要實際驗證 import 語句存在。

## 行動

- 切換到非 Fable 模型後若行為退化（反問多、推進弱、收尾散）→ 先確認 IDENTITY-holylight.md 仍在 CLAUDE.md import 鏈且內容未被稀釋
- 調整行為契約直接改 IDENTITY-holylight.md（必載層），勿新增 trigger atom 承載每-session 行為
