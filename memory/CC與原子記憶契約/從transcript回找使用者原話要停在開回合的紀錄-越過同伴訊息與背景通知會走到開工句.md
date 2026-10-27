# 從transcript回找使用者原話要停在開回合的紀錄-越過同伴訊息與背景通知會走到開工句

- Scope: global
- Author: holylight
- Source: 2026-10-23 MCP 與寫卡工具修補實測
- Confidence: [臨]
- Trigger: transcript, parentUuid, 回找使用者原話, Quote 回填, origin.kind, peer, task-notification, isMeta, 開工句, 開回合紀錄, 使用者原話, isSidechain, 真人訊息, 純字串 content
- Created-at: 2026-10-27
- Related: 子代理的對話紀錄是獨立檔-讀transcript的hook閘要分主檔與子代理檔-使用者原話只認主檔, 糾正與失敗偵測把sub-agent完成通知當使用者輸入-task-notification整則進ups-引用的糾正詞誤觸deeppostmortem

## 知識

- [臨] Claude Code 對話紀錄（transcript）裡的 user 紀錄分四種：origin.kind=human 是使用者打的字；peer 是同伴訊息；task-notification 是背景任務通知；沒有 origin 的 isMeta（Stop hook 回饋、附圖）算同一回合的延續。
- [臨] 判「是不是使用者打的」兩種形狀都要認：content 是區塊清單（VSCode 多半這樣），或 content 是純字串＋origin.kind=human（終端機 CLI 打的訊息、使用者下的 slash 指令；本機實查百餘筆）；只認清單會漏掉後者。不算真人的：isSidechain=true 的紀錄（子代理那邊）一律不算；沒有 origin 的純字串（compact 摘要、程式用 `claude -p` 送的提示、slash 指令回顯）也不算。
- [臨] 沿 parentUuid 往回找「觸發這次工具呼叫的使用者原話」時，peer、task-notification、沒有 origin 的純字串提示都是開新回合的紀錄；越過它們繼續往上，找到的就不是這回合的原話。
- [臨] 靠同伴訊息推進的 session 一路越過去會走到開工那一句：實例是 18 張卡的 Quote（使用者原話欄）都被回填成開工句。
- [臨] 判法：往回走只越過 isMeta 這種延續紀錄；遇到開回合、但不是認得出的真人訊息，就停下、不填。

## 行動

- 往回找原話碰到開回合的紀錄就停：認得出是真人訊息才取用，不是就不填
- 只越過沒有 origin 的 isMeta 延續紀錄，不越過 peer、task-notification、沒有 origin 的純字串提示
- 判真人訊息兩種形狀都認（區塊清單、純字串＋origin.kind=human），isSidechain 一律否
