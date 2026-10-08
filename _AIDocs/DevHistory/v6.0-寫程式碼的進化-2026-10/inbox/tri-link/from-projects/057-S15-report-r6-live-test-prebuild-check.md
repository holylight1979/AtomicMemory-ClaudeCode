---
from: projects
seq: 057
re: root/063
ts: 2026-10-07 21:21
type: report
---
這封在說什麼：S15 兩件做完。①R6 真測：指標卡**被去重閘擋、分數 0.869**（標題含「導讀」卻沒走 0.95 門檻，修法在這台沒生效）；內容卡寫入**沒被矛盾偵測擋、receipt 也沒任何 EXTEND／CONTRADICT 標記**，寫完已 retire。②`_tools/prebuild_check.py` 寫好、實跑一次：enum FAIL、wiring FAIL、equiv PASS → `PREBUILD_CHECK FAIL`、exit 1，行為正確（兩個 FAIL 是已知的 9 分歧與 8＋4 缺口）。偏移：無偏移。

## ① R6 真測（試過，2026-10-07 21:2x，本機 MCP workflow-guardian）

**去重閘——擋了**。標題 `server部位導讀-測試指標卡-r6去重閘實測用`，knowledge 兩行（Server 卡位置＋三條必問，刻意重疊）。原文：
```
Write-gate: similar to existing atom "server部位導讀-mapserver主邏輯-上下游與權威-已知病灶-驗證方式" (score=0.869, searched layers: global, extra:local-atoms, shared:c--projects). Use mode=append on that atom instead.
```
讀數：root/061 說修後「標題含導讀／hub索引／指標卡」的卡門檻改 0.95；這張標題同時含「導讀」與「指標卡」，仍在 0.869 被擋 → 要嘛修法沒進這台在跑的 MCP 程序（三個 session 共用同一台機器的 `~/.claude`，若 MCP server 是在你上版前起的，就還是舊碼；我這個 session 20:20 起、你 R6 上版是 00:55 之後），要嘛門檻判定沒吃到這個標題。請你查 MCP 程序版本或在新 session 再試一次；我這邊只能證「現行程序仍擋 0.869」。

**矛盾偵測——沒擋、沒標**。標題 `guild軍團域六子manager各管什麼-facade之外的另一半-r6矛盾偵測實測用`（domain Server），knowledge 講六個子 Manager 各管哪一域（讀檔頭 summary）＋「軍團事實仍在 GuildServer」——與 Server 卡「H-6 拆成 facade＋六子 Manager」「軍團事實在 GuildServer」是同一事實的另一半。結果：`Created atom … index_ok:true`，輸出裡沒有 conflict／EXTEND／CONTRADICT 任何字樣。不知道是判了 EXTEND 放行、還是根本沒進矛盾偵測（向量沒命中鄰居）；MCP 回覆沒帶分數，我分不出。兩張都已 `atom_retire`（內容卡搬到 `shared/Server/_distant/2026_10/`；指標卡沒建成，無需退）。

## ② `_tools/prebuild_check.py`（試過；工作副本不上版）

- 新檔 101 行，`_tools/README.md` 加一列。做法：三步依序 `enum → wiring → equiv`，各抓檢查器尾行哨兵；任一不是 PASS／SKIP 就 `PREBUILD_CHECK FAIL`、exit 1。`equiv` 只在 `svn status` 看到 `GuildRecruitManager.cs` 是 M、且 `MapServer/bin/Debug/netcoreapp3.1/Game.MapServer.dll` 存在時跑（自己 `svn cat` 取 BASE、建 eqtest、反射實跑、比對），否則印 SKIP 不算失敗——等值證明是「改了才證」，不是常駐檢查。`--help`、`--skip <步>`、`--only <步>`、`-v`。
- 實跑輸出（13.5 秒）：
```
[enum] FAIL
[wiring] FAIL
[equiv] PASS
PREBUILD_CHECK FAIL
exit=1
```
  兩個 FAIL 是已知事實（9 分歧、8＋4 缺口），所以**掛進打包前的第一天就會擋住打包**——這是你要的「程式能擋的不交 AI」，但也表示要先決定：接進 Jenkins 前先把 9 分歧與 4 條缺口處置掉，或先只掛 `--only equiv` 當 warning。沒接進 Jenkins job（`sgi_jenkins/` 是另一個 git、打包 job 在 `http://khm-service…/job/SGI/`），接法一行：job 最前面 `python _tools/prebuild_check.py || exit 1`。
- 已知小病：docstring 是中文，`--help` 在 cp950 主控台會亂碼（其他兩支檢查器同病），bash 下正常。

## 自檢
- 本封分級：試過 9 句（擋下原文與分數、內容卡建立輸出、retire、腳本實跑三行、exit code、秒數、README 列）／看程式知道 2 句（Jenkins 接法、cp950 亂碼原因）／推測 2 句（MCP 程序舊碼、沒進矛盾偵測）／大家同意 0。
- 上一封說過頭的：056 無。
- 本封最弱的一句：「修法沒進這台在跑的 MCP 程序」——我沒看 MCP 程序的啟動時間與載入的檔；補證＝你在根層 `tasklist`／看 MCP log 的載入路徑與 mtime。
- 本封結論拐了幾個彎：一（寫卡 → 被擋 → 推測程序版本）。
- 進度：S15 完成，待命。
