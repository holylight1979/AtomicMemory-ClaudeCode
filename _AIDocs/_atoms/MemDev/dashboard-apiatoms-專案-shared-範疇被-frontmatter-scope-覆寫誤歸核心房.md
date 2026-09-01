# dashboard apiAtoms 專案 shared 範疇被 frontmatter Scope 覆寫誤歸核心房

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: dashboard, world.html, 腦內世界, apiAtoms, scanProjMemDir, 專案atom消失, project shared, scope 誤歸, 核心房, 看不到專案記憶
- Created-at: 2026-06-17
- Related: guardian-dashboard-孤兒佔埠與新碼重啟, realm-範疇分區機制-v5, atom-scope-讀取端可見性-候選池一次收窄-他專案不進池-personal只給本人

## 知識

- [臨] 症狀：腦內世界網頁某專案房間空的（如 c--projects 0 顆），但磁碟 <root>/.claude/memory/shared/ 明明有 atom。根因不在收集，在 scope 標記：atom 被誤貼到「核心」房藏起來了。
- [臨] 機制：server.js apiAtoms 的 pushAtomFromFile 解析 frontmatter 時 `case "scope": atom.scope = val` 會用檔案裡的 bare `Scope: shared` 覆寫掉由路徑推導的權威 composite scope（project:<slug>:shared）。world.html buildModel 以 `sc.startsWith("project:")` 分房，scope 變 "shared" → 落 core 房。
- [臨] 為何只中 shared/：scanProjMemDir 原本的補正迴圈只認字面值 "project"（扁平層 V4 SPEC 值）、且跑在 scanV4ScopeDirs 之前，完全沒蓋到 shared/personal/role 子層。扁平 atom（Scope: project）正常、shared/ 全滅。
- [臨] 修法（路徑即權威）：scanProjMemDir 改成兩段掃描後統一補正——bare scope（project/shared/personal/role:x）一律補回 project:<slug>[:subscope]。fix 落在 apiAtoms 權威層，所有消費者（world.html 等）自動正確，勿在 buildModel 端補。
- [臨] 診斷心法：live :3848 與臨時埠跑『同一份磁碟碼』對拍能分辨『進程陳舊 vs 程式 bug』；手寫 replica 漏掉 enrichAtomWithAccess/frontmatter 解析會誤判，要嘛跑真檔、要嘛插樁印 defaultScope。改 server.js 後 live 生效仍需重啟佔埠進程（見 [[guardian-dashboard-孤兒佔埠與新碼重啟]]）。

## 行動

- 專案房間空但磁碟有 atom → 先查 atom scope 是否被 frontmatter 覆寫成 bare 值落到 core 房，非收集問題
- 改 dashboard atom 分房邏輯 → 動 apiAtoms 的 scope 標記（權威層），勿在 world.html buildModel 端補
- 驗 server.js 掃描行為 → 跑真磁碟碼於臨時埠或插樁，勿手寫 replica（會漏 frontmatter 解析/enrich）
- 改完 server.js → 重啟佔 3848 的舊碼進程才 live
