---
name: behavior-preservation
description: 行為保持重構的等值證法：預期值來自舊源碼或舊產物、實際值來自新產物，兩邊來源必不同；order／side_effect／boundary 三類變異各要證。被要求「改寫法但結果完全相同」「重構後行為不變」「等值證明」時觸發。
user-invocable: true
triggers: 行為保持, 等值證明, 重構後結果一樣, 結果完全相同, 行為不變, behavior preservation, preserve-check, switch 改查表, 特徵測試
pattern: reviewer
---

# Skill：behavior-preservation（Reviewer）

> 「改寫法但結果完全相同」要用證明，不用描述。本 skill 只定原則與介面；怎麼解析某語言的舊碼、怎麼跑某框架的新產物，由專案自己接（預期來源與執行器都可替換）。

## 原則（三條，缺一不算證）

1. **預期值來自舊源碼或舊產物**：用 regex 從舊碼（svn BASE、git 的舊版）解析 case→值，或用別的工具解析好的 `.json` 表。不手抄、不從新碼反推。
2. **實際值來自新產物**：真的跑新碼（import、反射、外部指令），全枚舉每個 case，連沒列出的值一起跑。不讀新碼猜。
3. **兩邊來源必不同**：`--expected-from` 與 `--actual-from` 同一路徑直接拒收（exit 2）。同一份東西比自己永遠相等，不是證明。

## 三類變異（每類跑一次，三次都 PASS 才算行為保持）

| `--mutation` | 證什麼 | 典型漏法 |
|---|---|---|
| `order` | 回序列的函式逐項同序 | 查表改用 dict／set 後迭代順序變了 |
| `side_effect` | 每個 case 觸發的副作用（log／send／event）引數相同、守衛在同一個 case | 抽純函數時把 log 搬到表外，變成每個 case 都發 |
| `boundary` | 舊碼沒列的值落到同一個預設 | `else` 的值在新表的 `.get(k, default)` 寫錯 |

三次都另外比對所有列出的 case→值，常數改壞任何一次都 FAIL。

## 怎麼跑

```
python scripts/preserve-check.py --expected-from <舊源碼或 .json> --actual-from <新產物 .py> \
    --mutation <order|side_effect|boundary> --func <查表函式> [--order-func <序列函式>] [--effect log]
```

- 尾行哨兵 `PRESERVE_CHECK PASS|FAIL`；exit 0 相同、1 有差異、2 拒收。三次輸出貼進收尾報告，不貼就不算驗過。
- 預期來源換法：舊碼不是 Python 也行，regex 認 `case K:`／`== K:`／`else`／`default` 與 `return V`；認不到就先用自己的工具解析成 `.json`（格式見腳本檔頭）再餵。
- 執行器換法：`--actual-cmd "<指令> {key}"` 用外部程式當執行器（例如 dotnet 小程式反射跑 dll）；它看不到副作用，`side_effect` 會明說不支援並 FAIL，該類要另寫執行器。
- 證不到的要明寫：時序、執行緒、live 狀態不在此證法內。

## 不做的事

- 不替專案寫解析器或執行器，只收兩個來源與三類變異的結果。
- 不把「編譯過」「看起來一樣」當證據。
