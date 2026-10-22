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
- [臨] 改正：記 keep 之後 `session-artifacts list` 照樣列出（帶 decision=keep），只有 `--all-safe` 會跳過它；HUD 前端會不會另外藏起來沒查。
- [臨] 對工作樹或分支記 keep，wg_release_rules.leftover_candidates 的 kept() 會把它永久排除在 LEFTOVER_NEEDS_CLEANUP 之外，工具沒有取消 keep 的動作（只能直接刪）。所以開著的軌的工作樹與分支只留著、不記 keep（軌開著時它們本來就因 busy 不被列）；開著的軌自己帳上的檔也不替它記。
- [臨] `list --all` 是即時的，作業中途會有新 session 與新檔進帳；判「開著的工作軌」用 state=open 且不是總控台，不寫死 sid 名單（寫死就會把中途新開的軌的檔誤記）。

## 行動

- 清殘留前先 list 看有沒有 inbox 檔；有就 keep 再清其餘
- 派清理軌時派工單寫死「一律留」與「一律刪」兩張清單
