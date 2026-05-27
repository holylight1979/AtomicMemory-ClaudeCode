---
name: handoff
description: 跨 Session Handoff Prompt Builder — 強制 6 區塊 self-sufficient 模板，避免下 session 裸奔
---

# /handoff — 跨 Session Handoff Prompt Builder

> 強制 6 區塊 self-sufficient 模板。避免下 session 裸奔。
> 全域 Skill。與 `/continue`（讀取端）配對：本 skill 是寫入端。

---

## 觸發

使用者要求「給下 session 的 prompt」「續接 prompt」「交接」「寫 next-phase」時主動執行。
若使用者已徒手寫，主動對照 6 區塊清單並補齊缺項。

---

## 核心原則

**讀者 ≠ 當下對話者**。下個 Claude 沒有看到本次對話的任何內容。
凡是「我們剛才討論的」「之前說的」「那個方法」這類代詞，下個 Claude 都無法解析。

---

## 必填 6 區塊（缺一拒絕完成）

### 1.【前置脈絡】
- 專案根目錄絕對路徑（例：`c:/projects/.claude/`）
- 工作分支 / 工作目錄
- 為什麼做這件事（**含 why**，不只 what）

### 2.【已完成】
- Phase 編號或階段名稱
- commit hash（前 8 碼）+ push 狀態
- 已通過的驗證（測試/編譯/手測）

### 3.【權威來源】
- 檔案路徑:行號清單
- 下個 Claude 該**先讀**什麼才能進入狀況
- 外部資源（文件 URL、內網路徑、權限要求）

### 4.【產出位置】
- 已產出的檔案（路徑）
- 接下來要產出的檔案（路徑+格式）

### 5.【做法】
- 步驟清單（可條列）
- **指明工具選擇**（避免下個 Claude 重新評估）
  - 例：用 curl 不開瀏覽器、用 atom_write MCP 不用 Write tool

### 6.【決策依據】
- 為什麼選此做法
- 拒絕了哪些 alternatives 與原因
- 已知限制 / 已知坑

---

## 輸出格式

整段 prompt 包在 ` ``` ` code block，使用者可直接複製貼上。
若使用者要求存到 `_staging/`，寫成 `{project}/.claude/memory/_staging/next-phase-{name}.md`，由下次 `/continue` 自動讀取。

---

## 反模式（自我檢查清單）

執行前對照，命中任一 → 拒絕完成並補齊：

- ❌ 「繼續 X Phase 2」這種一句話 prompt
- ❌ 只有 what 沒有 why（下個 Claude 不知道判斷標準）
- ❌ 使用「我們」「剛才」「之前」「那個」等指代當前對話的代詞
- ❌ 引用「對話中的決定」但未列出該決定本身
- ❌ 缺權威來源（下個 Claude 不知道該先讀哪個檔）
- ❌ 缺 commit hash（下個 Claude 無法定位「已完成」的程式碼版本）

---

## 與 /continue 的關係

| Skill | 角色 | 動作 |
|-------|------|------|
| `/handoff` | **寫入端** | 產出 self-sufficient prompt，可選擇存 staging |
| `/continue` | **讀取端** | 讀 `_staging/next-phase-*.md` 並執行 |

不存 staging 也可：直接給使用者複製貼上的 code block。

---

## 範例對照

### ❌ 反例（截圖事件 2026-04，FcgiHandler）
```
繼續 FcgiHandler 知識庫建置 Phase 2：phpUjAdmin 後台交叉對應。
```
→ 下個 Claude 不知道：專案在哪、Phase 1 做了什麼、權威來源在哪、phpUjAdmin 怎麼進

### ✅ 正例（self-sufficient 版）
```
【前置脈絡】
- 專案：c:/projects/.claude/（SGI Server，team memory repo）
- 任務：FcgiHandler 知識庫建置 Phase 2 — phpUjAdmin 後台交叉對應
- Why：team 同事 wellstseng 之前在 ba3bc84 補齊了 92 路由參數，需與後台路由對齊

【已完成】
- Phase 1：commit d33b896 已 push origin/master
- 權威來源：_AIDocs/API_Endpoints_Report.md（92 路由完整參數）
- Phase 1 產出：c:/projects/.claude/memory/fcgi-api-directory.md（98 路由 §1-4 + §5 phpUjAdmin 占位）

【權威來源】
- 後台路由：BackendServer 92 路由（fcgi-api-directory.md §1-4）
- 同事補齊：commit ba3bc84

【產出位置】
- 既有：fcgi-api-directory.md §5 phpUjAdmin 占位
- 接下來：phpujadmin-route-map.md（新檔）→ 回寫 §5

【做法】
1. 從本機直接連內網後台（不開瀏覽器，省 Playwright 開銷）
2. 用 curl 逐頁抓 HTML，比對 BackendServer 92 路由
3. curl 抓不下來的頁才改用瀏覽器補
4. 產出 phpujadmin-route-map.md → 回寫 §5 → commit + push

【決策依據】
- 為什麼用 curl：本機背景連內網夠用，不需開視窗（之前討論結論）
- 為什麼不全用 Playwright：開銷大且非必要；只在 curl 失敗時 fallback
- 已知坑：phpUjAdmin 帳密在 c:/projects/.claude/secrets/（git ignore），讀檔取
```

---

## Step 1：判斷觸發

從使用者最近的訊息抓取以下意圖之一：
- 「給下 session 的 prompt」「下一個 session 用的 prompt」
- 「續接」「交接」「下次繼續」
- 「寫 next-phase」

抓不到 → skill 不執行，回覆「沒偵測到 handoff 意圖，請明確說明」。

## Step 2：蒐集 6 區塊

對照當前對話脈絡，逐一填入 6 區塊。任一區塊資訊不足 → 主動向使用者補問，**不要猜**。

## Step 3：對照反模式清單

逐項檢查，命中任一 → 回頭補齊，**不要交付**。

## Step 4：輸出

包在 code block。若使用者要求存 staging：
```bash
# 寫入路徑
{project}/.claude/memory/_staging/next-phase-{name}.md
```

完成後告知使用者：「prompt 已產出，可直接貼到下一個 session 開頭」或「已存到 staging，下次 /continue 自動讀取」。
