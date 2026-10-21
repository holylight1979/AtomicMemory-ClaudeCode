# hud全機殘留的不用再確認標籤把gitignore的派工信箱檔也算可刪-整組清前先list逐項判-信箱是總控台的帳要記keep

- Scope: global
- Author: holylight
- Source: session:cb4c9c8e 2026-10-21 HUD 全機殘留 171 樣盤點
- Confidence: [臨]
- Trigger: 全機殘留, session-artifacts, --all-safe, 不用再確認的, 清掉暫存, HUD 殘留, 收尾自清, 信箱被刪, 派工單被清
- Created-at: 2026-10-21
- Quote: 「接著也可派工，checklist 文件需要更新 (我要看最新進度狀態)，完工的項目如果不必留在文件內，可以搬去DevHistory或者刪除。並且請你給我白話說明最新狀況(不要技術細節臭味兒)。」

## 知識

- [臨] tools/session-artifacts.py（HUD「全機殘留」背後的工具）把「被 .gitignore 排除」的檔列成不用再確認就能刪；總控台的派工單、交付信、開工句、無頭驗收的 json 證據全在 workflow/inbox/（gitignore），按「整組清」或 `act --all-safe` 會把接續單指著的帳全刪掉。
- [臨] 正確做法：先 `list --sid` 逐項看，信箱與文件指到的路徑 `act --action keep` 記下理由（HUD 就不再列），scratchpad／隔離暫存／已被取代的受測環境才 delete；大量時派文件軌照判準逐項做，不整組按。

## 行動

- 清殘留前先 list 看有沒有 inbox 檔；有就 keep 再清其餘
- 派清理軌時派工單寫死「一律留」與「一律刪」兩張清單
