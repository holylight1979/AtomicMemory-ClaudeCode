# 行為保持重構的高速等值證法-舊原始碼解析出預期表-新dll反射實跑全枚舉值比對-副作用守衛文字相等

- Scope: global
- Author: holylight
- Source: scratchpad eqtest/check_equivalence.py（2026-10-08）
- Confidence: [臨]
- Trigger: 等值證明, 行為保持重構, 結果完全相同, switch 改查表, 對照表重構, 特徵測試, 反射實跑, 高速修整, 收口, 同一事實兩份
- Created-at: 2026-10-07
- Quote: 「你跩什麼? 真正的問題是什麼? 是LLM要怎麼主動將這種狀況 高速修整、且結果與原本錯亂的寫法還完全相同呀!」

## 知識

- [臨]（2026-10-08 實做，GuildRecruitManager 7 段 switch → 7 張靜態對照表，+86/−137 行，從動手到證明約 10 分鐘）「改寫法但結果完全相同」的快速證法，不需要既有測試專案：①把映射抽成純函數或靜態表，副作用（log／send）用明寫的 if 守衛留在原位；②「舊」的預期表不手抄，用 regex 從 svn BASE 原始碼解析 case→值（異源真相）；③「新」的實際行為不讀碼，用 net8 小程式 `Assembly.LoadFrom` 新建置的 dll，反射取 private static 表，`Enum.GetValues` 全枚舉（含未列值的預設）實跑；④逐值比對＋副作用呼叫的引數文字在新檔逐字存在＋對應 case 有守衛；⑤`dotnet build` 0 錯。印單行哨兵 `<NAME>_CHECK PASS|FAIL`。證不到的：時序與執行緒（要 live）。

## 行動

- 被要求「修整寫法但結果不變」→ 先抽純映射，再用舊碼解析表 vs 新 dll 反射實跑全枚舉比對，不用描述代替證明
- 比對器的預期表一律從 BASE 原始碼解析，不手抄
