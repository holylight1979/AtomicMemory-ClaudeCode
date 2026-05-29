# Skill 設計核心原則

> SKILL.md 的「為什麼這麼設計」展開。SKILL.md 規則表面，本檔解釋根因。

## 目錄

- [Token Budget 分配（量化指引）](#token-budget-分配量化指引)
- [Progressive Disclosure 三層載入](#progressive-disclosure-三層載入)
- [Lean Instructions](#lean-instructions)
- [Lack of Surprise](#lack-of-surprise)
- [零專案耦合](#零專案耦合)
- [邏輯優先於語意](#邏輯優先於語意)
- [Scripts vs References 的角色分工](#scripts-vs-references-的角色分工)
- [何時抽 Reference / 何時寫 Script](#何時抽-reference--何時寫-script)

---

## Token Budget 分配（量化指引）

行數軟硬上限只是近似 token 預算。實際分配建議（以單次任務 ~20k context window 為基準）：

| 層 | 內容 | 載入時機 | 建議行數 | 估 token | 預算佔比 |
|---|------|---------|---------|---------|---------|
| 1 | frontmatter | 常駐（router 階段） | 5~15 | ~50~150 | ≤ 1% |
| 2 | SKILL.md body | 觸發後完整載入 | ≤ 200（硬 500） | ~1k~2k（硬 ~3k~5k） | 5~15% |
| 3a | references/ 單檔（按需 Read） | LLM 主動讀取 | ≤ 300（>300 加 TOC） | ~2k~3k | 每檔 ≤ 15%，多檔同載 ≤ 30% |
| 3b | assets/template | LLM 主動讀取 | ≤ 150 | ~1k~1.5k | ≤ 10% |
| 4 | scripts/ | **不進 prompt**，執行後只有 stdout 計入 | — | — | 0%（stdout 視操作而定） |

**判定**：
- 觸發 + 主流程消耗應 ≤ 15%（留 ≥ 85% 給實際任務內容）
- 多 references 同載超 30% → 該抽 sub-skill 或合併重組
- scripts/ 是「免費載入」資源 — 凡能寫成 script 的操作都該移過去（呼應 [邏輯優先於語意](#邏輯優先於語意)）

**反例**：
- ❌ SKILL.md 500 行 + 觸發即讀 3 個 reference + 2 個 template = 觸發成本 ≥ 30% context
- ❌ inline 寫整段 200 行模板進 SKILL.md（佔死預算）

**正例**：
- ✅ SKILL.md 150 行 + 流程內按需讀 1 個 reference + 1 個 template = 觸發成本 ~15%

---

## Progressive Disclosure 三層載入

Skill 在 Claude Code 內部的載入時機：

| 層 | 內容 | 何時載入 | 目標大小 |
|---|------|---------|---------|
| 1. Metadata | YAML frontmatter（name / description / triggers） | **常駐**：router 決策階段就讀 | ≤ 100 字 |
| 2. SKILL.md body | 觸發後完整載入 prompt | **觸發時** | ≤ 200 行（軟上限 500） |
| 3. Bundled resources | scripts / references / assets | **按需**：Skill 內指引或 Agent 自行 Read | 無限制 |

**為什麼**：常駐 metadata 必須極簡，否則每個 session 都付這個 token；觸發層放真正會用到的流程；按需層放長尾資訊（領域知識 / 大模板 / 機械腳本）。違反此分層 → token 浪費或觸發失敗。

**判定原則**：

- 「每次觸發都會用到」→ SKILL.md body
- 「特定模式 / 邊角情境才用到」→ references/
- 「機械操作可自動化」→ scripts/
- 「填空模板」→ assets/

---

## Lean Instructions

**規則**：規則只寫一次。重複即罪。

**為什麼**：重複規則 = 維護負擔（兩處改一處） + 模型注意力分散（看到重複以為強調，反而過度解讀）+ token 浪費。

**判定**：
- 同一條鐵則出現 ≥ 2 次 → 抽出去或刪一處
- 「不准 X」「禁止 X」「嚴禁 X」對同一件事重複強調 → 一次說清為什麼即可
- 範例與規則內容重疊 → 範例改成展示「邊界情況」而非「正面案例」

**Anti-pattern**：用 ALL-CAPS / ⚠️ / **粗體** 反覆強調同一件事 — 這是焦慮，不是設計。

---

## Lack of Surprise

**規則**：description 必須準確反映 skill 行為，不能 over-promise 或 under-promise。

**為什麼**：description 是 router 的判斷依據。寫得模糊 → 該觸發時沒觸發（undertrigger）；寫得浮誇 → 不該觸發時觸發（overtrigger）。

**判定**：
- description 不能只寫「what」，要含「when」（觸發場景）
- 不能用「也許」「可能」「視情況」等模糊詞
- 反例：「處理檔案的工具」 → 不知道何時用
- 正例：「**任何**要寫新 skill、改既有 skill、評估 skill 品質的場合都該觸發」（明確 when，且 pushy）

**triggers 欄位**：補充 description 覆蓋面，列出 5–10 個關鍵字 / 短語變體，含中英文混用情境。

---

## 零專案耦合

**規則**：全域 skill（`~/.claude/skills/`）內嚴禁 hardcode 任何專案路徑、專案名稱、團隊內部術語。

**為什麼**：全域 skill 給所有 agent 用。一個 catclaw 專用詞跑進去，其他 agent 看到就會誤判（「這 skill 是給 catclaw 的，我不該用」）或誤套（在錯的專案執行錯的指令）。

**判定**：
- grep skill 內所有檔案，搜尋常見專案關鍵字
- 範例佔位符用 `<project>` / `<workspace>` / `<repo>` / `<your-skill-name>`
- 必須示範實際路徑時用通用範例（`./src/foo.py`）

**例外**：專案本地 skill（`<project>/.claude/skills/` 或 `<project>/agents/*/skills/`）可以 hardcode，但要在 SKILL.md 開頭明寫「限 X 專案使用」。

---

## 邏輯優先於語意

**規則**：能用邏輯（腳本 / 規則 / 結構）處理的事，**禁止**寫成 LLM 自查條目。

**為什麼**：
- LLM 自查的失敗率非零，越是「鐵則」越容易被忽略（鐵則疲勞）
- 同樣的檢查讓 LLM 跑一次 = 燒 token；讓 script 跑一次 = 零成本
- 規則化的事項可驗證、可審計；語意化的事項依模型版本浮動
- analyze-spec 原本「禁止裸 `*(待補)*`」靠 LLM 自查 — 偷懶率非 0；改成 `check-pending.py` findstr 後零漏網

**判定**：

任何 SKILL.md 內看到「請檢查 X」「禁止 X」「確保 X」，先問：
1. X 可以用 grep / regex / 行數 / 檔案存在性 判定嗎 → **必須**寫成 script
2. X 可以用 schema 驗證（JSON / YAML 結構）嗎 → 寫成 script
3. X 是路徑/編碼/格式問題 → 寫成 script wrapper
4. X 真的需要語意理解（內容是否合理、是否誤導）→ 才留給 LLM

**反例**：
- ❌「請確保 frontmatter 含 description」→ 該寫進 audit-skill.py
- ❌「請檢查 SKILL.md 不超過 500 行」→ 該寫進 audit-skill.py
- ❌「請確認所有路徑都是相對的」→ 該寫進 audit-skill.py（已做）

**正例**：
- ✅「請確認生成的報告對讀者有價值」→ 語意層面，LLM 才能判
- ✅「請判斷這份規格與既有系統是否衝突」→ 需領域知識 + 推理

**設計影響**：
- audit-skill.py 是這個原則的具現化 — 把可邏輯化的檢查全部硬閘門
- new-skill.py 也是 — 把骨架生成自動化，不靠 LLM 每次重畫
- 反過來，patterns.md 中 Reviewer 模式應**優先用 script**，只有 script 真的判不了才回退 LLM

---

## Scripts vs References 的角色分工

| 維度 | scripts/ | references/ |
|------|---------|------------|
| 性質 | 可執行程式碼 | 文字文件 |
| 載入方式 | 不進 prompt，呼叫執行 | 進 prompt（按需 Read） |
| 適用 | 確定性任務（檔案 IO / 解析 / 檢查 / 量測） | 領域知識 / 模式說明 / 大段 SOP |
| 變動頻率 | 低（一次寫對長期用） | 中（會隨經驗累積） |
| 失敗模式 | exit code / stderr | 模型解讀錯誤 |

**選擇樹**：

```
這個操作可以由「給定輸入 → 確定性輸出」描述？
├─ 是 → 寫 script
│   └─ Windows 中文 / JSON output / 第三方 CLI 包裝 → 100% 該寫
└─ 否 → 進 references/ 或 SKILL.md
    ├─ 流程性、每次都讀 → SKILL.md
    └─ 模式說明 / 大段細節 / 邊角情境 → references/
```

---

## 何時抽 Reference / 何時寫 Script

**抽 reference 的時機**：

- SKILL.md 內某章節 > 30 行且不是每次都需要
- 同一段 SOP 在多個 skill 重複出現（抽到本 skill 的 references 共用）
- 模式說明（如 5 大設計模式）— 不是流程，是「選擇依據」

**寫 script 的時機**：

- 某操作主 agent 寫過 2 次以上（DRY）
- 步驟固定但容易手打錯（中文路徑 / 編碼 / 多參數）
- 需要硬閘門（檢查器 / 驗證器）
- 量測 / 報告類（每次格式一致）

**反例**：

- ❌ 把「YAML frontmatter 規範」寫成腳本（規範是文字，不是動作）→ 該進 references/
- ❌ 把「中文路徑 xcopy SOP」整段寫進 SKILL.md（每次都讀冗長，且機械操作）→ 該寫 script
- ❌ scripts/ 內寫商業邏輯判斷（會隨需求變動，難維護）→ 應該讓主 agent 決策、script 只做執行
