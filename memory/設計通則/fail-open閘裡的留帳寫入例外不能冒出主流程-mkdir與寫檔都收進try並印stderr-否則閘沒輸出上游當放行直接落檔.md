# fail-open閘裡的留帳寫入例外不能冒出主流程-mkdir與寫檔都收進try並印stderr-否則閘沒輸出上游當放行直接落檔

- Scope: global
- Author: holylight
- Source: track-dedupe-ai-judge 2026-10-20 補件 ace4ccc4（總控台代寫）
- Confidence: [臨]
- Trigger: fail-open, 留帳失敗, audit log 寫不進去, mkdir 例外, 閘沒輸出, write-gate unavailable, 輔助寫入, except OSError pass, 靜默吞錯
- Created-at: 2026-10-20
- Quote: 「"下個寫碼session" !? 他們有空就讓他們修完不是嗎..? 這也是我說 "我從未答應把這種東西另外放進修正計畫" 的狀況... 倘若是 Codex 或審查時挖出來的、但LLM判斷後 其實屬於"飄移"的，直接不做，但倘若有關且確實有問題，就應該要立即修正」

## 知識

- [臨] fail-open 的閘（上游收不到輸出就放行）裡，留帳、審計、快取這類輔助寫入的例外不能冒出主流程：實例是 write-gate 的 audit mkdir 在 try 外，資料夾建不起來時整支閘無輸出，MCP 端走「write-gate unavailable, allowing」直接落檔；寫檔失敗又被 `except OSError: pass` 吞掉。正解：mkdir 與寫檔都收進 try，失敗印一行 stderr（什麼帳、為什麼沒寫），主判定照跡回。留帳是專給人抽查的唯一依據時，它寫不進去要浮出，不能靜默。

## 行動

- 寫或審 fail-open 閘：每一個輔助寫入都問「它炸了主判定還回得來嗎、有沒有訊號」
- 案例要有一支「留帳目錄建不起來」：閘仍回正常結果、stderr 有訊號
