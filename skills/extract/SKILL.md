---
name: extract
description: 手動知識萃取：從當前對話整理值得留的知識，逐項確認後走 atom_write 寫入
disable-model-invocation: true
---

# /extract — 手動知識萃取

> 從**當前對話**整理知識點，使用者確認後用 MCP `atom_write` 寫入。
> 全域 Skill，適用任何專案。不依賴 Ollama、不讀 transcript、不呼叫 `hooks/extract-worker.py`
> （worker 是 hook 專用：靠 stdin 的 session_id／cwd 找 transcript、結果回寫 session state 的 knowledge_queue——那條 per-turn 管線已停用，手動不復活）。

---

## 使用方式

```
/extract
```

無參數。

---

## Step 1: 從對話整理知識點

回顧本次對話（使用者的糾正、踩到的坑、拍板的決策、驗證過的事實），分五類找：

- **factual**：事實性知識（API 行為、工具特性、環境差異）
- **procedural**：操作步驟、指令組合
- **architectural**：架構決策、設計選擇
- **pitfall**：踩到的坑、容易出錯的地方
- **decision**：做出的決策及理由

**不收**：能從最終程式碼／測試／既有文件直接讀出的內容（函式清單、參數表、檔案索引、逐行程式碼）——反事實自問「拿掉這條，未來會重犯或付昂貴重查成本嗎？」不會就不寫，改成文件路徑一行。未經使用者確認的推測也不收。

## Step 2: 範疇判定（Realm，每項都評估）

決定知識該歸**核心**還是**非核心（local）**——三問：① 可重用 ≥2 專案？② 系統規則 vs 單一 app/工具/環境的特定範疇？③ 月級穩定 vs 週級易變？

- **核心**（預設）：跨專案通用（偏好/決策/工作流/工具鏈/記憶系統機制）→ `atom_write` 不帶 realm（預設 core，住 `memory/<Lv1>/`，全專案注入）；**必給 `domain`**（Lv1 閉合清單 `memory/_meta/taxonomy.json`）。
- **非核心（local）**：只在 ~/.claude 內才有用（記憶系統/Guardian「特定實例」開發、腦內世界 world.html、特定外部工具踩坑如 gdoc/codex/electron-uia）→ `atom_write` 帶 `realm=local` + `domain`（World/Tools/MemDev）；**仍 scope=global**，自動歸 `_AIDocs/_atoms/<domain>/`、只在 cwd∈~/.claude 注入、外部專案零負擔。
- 拿不準 → 預設 core（安全側；分類器同樣安全預設 core、核心保護清單硬擋）。機制見 atom `realm-範疇分區機制-v5`。
- 專案專屬的規則／決策 → `scope=shared`；只關於使用者本人 → `scope=personal`。

## Step 3: 展示結果

```
## 萃取結果

1. [類型] 知識摘要
   → 建議：append 到 {既有 atom 名稱} ／ 新建 atom（domain=…, realm=…, scope=…）
   → 信心：[臨]

2. ...
```

既有 atom 是否命中：用對話中已注入的 atom、`memory/_ATOM_INDEX.md` 或 `_atom_index.json` 比對 Trigger，相似就 append 不新建。

## Step 4: 互動確認後寫入

一次問完：哪些要寫、寫進哪顆 atom（建議＋使用者決定）、範疇／scope 是否照建議。

確認後逐項呼叫 MCP `atom_write`（新建 `mode=create`、補充 `mode=append`）。
- 新建 atom **一律 `[臨]`**：MCP 對 create 拒收 `[觀]`／`[固]`（跨 session 穩定性不能在首寫斷言）；晉升靠後續 session 使用或 append，不在此調。
- 被 write-gate 拒收（重複／過長／可再生內容）→ 照拒收訊息處理（append 到既有 atom、縮成結論、或放棄），不繞 `skip_gate`。
- 不手改 `MEMORY.md`／`_INDEX.md`：索引由 `atom_write` 與 hook 自動維護。

回報：寫了幾顆／append 幾顆，各附絕對路徑；被拒收的列原因。
