---
name: continue
description: 讀取 _staging/next-phase*.md 並立即執行續接任務（多任務時列選單）
disable-model-invocation: true
---

# /continue — 續接暫存任務

> 讀取 staging 區的續接 prompt 並立即執行。輕量版續接，適合已備好下一步的場景。
> 全域 Skill，適用任何專案。支援多任務並存選擇。

---

## 使用方式

```
/continue
```

無需輸入參數。多個任務時自動列出選單，選數字即可。

---

## Step 1: 掃描暫存區

從系統 context 的 "Additional working directories" 或 CWD 找到 staging 區，用 **Glob tool** 掃描：

```
{project_root}/.claude/memory/_staging/next-phase*.md
```

> staging 在 `{project_root}/.claude/memory/_staging/`（專案自治層）。
> 未遷移的舊專案：`~/.claude/projects/{slug}/memory/_staging/next-phase*.md`
> 例：CWD `C:\Projects` → 優先掃描 `C:\Projects\.claude\memory\_staging\next-phase*.md`

每個專案有獨立的 staging 區，確保不同專案的續接互不干擾。

### 分流

- **掃描到 1 個檔案** → 自動選定該檔案，繼續 Step 2
- **掃描到多個檔案** → 列出清單讓使用者**選數字**：

```
_staging/ 下有 N 個待續任務：
  1. bundle-pipeline — [續接] AssetBundle 自建打包管線（Phase 1）
  2. token-diet — [續接] Token 瘦身計畫

請選擇（輸入數字）：
```

> 清單中的名稱取自檔名 `next-phase-{name}.md` 的 `{name}` 部分，摘要取自檔案第一行。

- **掃描到 0 個檔案** → 回覆「沒有待續任務。`_staging/` 目錄下無 `next-phase-*.md` 檔案。使用 `/resume` 可從 atoms/git/todo 推斷續接工作。」→ 結束

## Step 2: 讀取並刪除

1. 讀取選定檔案的全部內容，記住內容
2. **立即刪除**該檔案（防止重複執行）

## Step 3: 執行（先回讀，再動工）

1. **回讀（read-back，閉環確認）**：刪檔後的**第一個輸出**（在任何其他工具呼叫之前）必須是一段給使用者看的白話複述，涵蓋：
   - **我的認知**：這個續接任務在做什麼、目前進度到哪（用自己的話講，不是貼原文）
   - **即將執行的工作**：接下來打算做的具體步驟
   - **關鍵約束 / 未解問題**（有才列）

   目的：讓使用者第一時間看見 LLM 的理解，**倘若有偏頗可以即時溝通修正**。此步驟**非阻塞**——說完直接進第 3 步繼續執行，不等使用者確認、不中斷作業；檔案已刪，這段複述也是內容的唯一留痕。省略或壓成一句帶過 = 違反本 skill。
2. 覆述時若發現文件有**矛盾 / 缺口 / 可疑假設**（對照 [[handoff-綜觀品質與抗失真寫法]]）→ **先回問澄清，不要盲目照做**；無疑點則續第 3 步。
3. 將讀取到的內容視為**任務 prompt**，立即開始執行，不需額外確認。
4. **注意**：如果任務的完成條件中包含「產出下一階段續接 prompt」，在任務完成時寫入新的 `next-phase-{name}.md`（保持原任務名稱）。
