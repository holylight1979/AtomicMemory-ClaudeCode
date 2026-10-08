# v6.0 寫程式碼的進化 — 開發歷史資料夾

> 這一波把原子記憶系統推進為 **v6.0（針對寫程式碼的進化）**：讓任何裝了 CC＋原子記憶系統的人、任何專案，AI 寫程式時自動綜觀、判斷、深入、驗證。
> 本資料夾只放歷史與輸入；實作後的現況文件在 `_AIDocs/Architecture.md`、`TECH.md`、`_AIDocs/_CHANGELOG.md`。

## 內容

| 檔／資料夾 | 是什麼 | 原位置 |
|---|---|---|
| `預計畫-原子記憶系統根基調整.md` | 原設計者認可的預計畫（目標 G0～G16、核心模型、每目標補什麼怎麼驗、角色分工、並行軌道；附錄給實作 AI） | `memory/_staging/下一波調整計畫-AI寫碼守門.md` |
| `全貌-AI寫碼守門三方討論.md` | 前一波三方討論定稿（失敗案例、回放實驗、審查者、量出來的壞味道、逐項對帳） | `memory/_staging/全貌-AI寫碼守門三方討論.md` |
| `原設計者原話輯.md` | 原設計者原話逐字，按目標 G 分組，附來源 | 從卡片 Quote 欄與信件蒐集 |
| `前一波-第二視角-Companion三面鏡-綱要.md` | 更早一波的周邊機制綱要（三面鏡、哨兵、拐彎數），被 v6.0 核心取代 | `memory/_staging/next-phase-第二視角-Companion三面鏡.md` |
| `inbox/tri-link/` | 根層、SGI、TSLG 三槽信箱全文（from-root 077 封、from-projects 073 封、from-tslg 064 封）與附件（兩專案輸入、三份 Codex 審查、對帳表、基線腳本） | `c:\Projects\.claude\inbox\tri-link\` |
| `inbox/root-link/` | 更早的根層↔SGI 雙槽信箱 | `c:\Projects\.claude\inbox\root-link\` |

## 路徑變更說明

- 卡片（atom）的 `Source:` 欄寫的是搬家前的原位置（同上表「原位置」欄的信箱路徑），對應本資料夾 `inbox/` 底下同名檔；Source 是落檔當時的出處，不回改。
- 兩個專案（SGI、TSLG）自己的接續單若仍指向原信箱路徑，屬專案層歷史，v6.0 不調整參與專案；要重接信箱由使用者另開新一波。

## 接續

- 接續單（仍在 `memory/_staging/next-phase-v6.0-寫程式碼的進化.md`）：下一步是 Plan Mode 定執行細節，再以「執P」分階段 session 實作，每階段驗證綠、上版、給下一階段 prompt。
