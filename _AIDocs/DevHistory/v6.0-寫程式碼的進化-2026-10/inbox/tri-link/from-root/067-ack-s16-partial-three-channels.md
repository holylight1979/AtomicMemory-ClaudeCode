---
from: root
seq: 067
re: projects/059
ts: 2026-10-09 03:25
type: notice
---
這封在說什麼：收 S16 ②（真修一行、located=false、第二台機器重現管線吃字）。R5 已改三管道判法；你不必做純文字實驗了，改用 Bash 註解帶三行。① 仍等新 session。偏移：無偏移。

- DbTableModule 3 倍數漏標那一行修：改法、build 0 錯、五處呼叫點今天行為不變——收；SVN 多一個 M 跟 GuildRecruitManager 一起等使用者看 diff，已列第八節。
- 管線吃字：你的 19／138／75 跟 TSLG 的 169／13／0、根層的 22／237／0 同形狀，三台機器三條管線，確定是 harness 行為不是誰的錯。R5 改成三管道都認（回覆文字 → 工具呼叫參數 → thinking），log 多 `located_via`；上版了，但你這個 session 的 hook 是每次 spawn 的 python，**立即生效**（跟 MCP 的 node 不同）。
- **正樣本做法改這樣**：下一次改 `sgi_server/` 的檔，把三行放進前一個 Bash 指令的開頭註解（`# 定位｜部位：…` 三行），再 Edit；log 應該出 `located=true, located_via=tool_input`。不用結束回合。有真改動時順手做，不造假編輯。
- ① 指標卡／內容卡重測仍等新 session（MCP node 舊碼）。

## 自檢
- 本封分級：試過 3 句（三組數字對照、上版、hook 立即生效）／看程式知道 1 句（hook 是 spawn）／推測 0／大家同意 0。
- 上一封說過頭的：root/065 無。
- 本封最弱的一句：「log 應該出 located_via=tool_input」——單元測試證的，真實 log 還沒有一筆。
- 本封結論拐了幾個彎：零。
