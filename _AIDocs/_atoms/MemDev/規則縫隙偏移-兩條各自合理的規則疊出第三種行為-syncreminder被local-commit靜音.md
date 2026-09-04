# 規則縫隙偏移-兩條各自合理的規則疊出第三種行為-SyncReminder被local-commit靜音

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 行為偏移, 契約偏移, 規則衝突, SyncReminder, 先 commit 再 push, 必載檔, core.md 修剪, 200 token, 知識段截斷, USER.md 死連結, 為什麼以前會現在不會
- Created-at: 2026-09-04
- Related: feedback-上git是commit加push一體-沒口令前不先commit-讓使用者能先看diff, 團隊產出上傳前先問人-記憶庫自動做滿, 注入預算三教訓-裁切要回填-分級看token不看字元-橋接檔須隨索引重產, hook-py改動立即生效-每次呼叫起新進程-只有mcp-node進程需重啟

## 知識

- [臨] 使用者問「以前都自動做對、最近偏了」時，先查三件事而不是猜最近的大改版：(1) 必載檔（IDENTITY/USER/core.md）有沒有刪掉唯一寫明該契約的句子（git log -S）；(2) 同期有沒有新 atom 用重的 trigger 要求相反方向；(3) 定義該契約的 atom 實際注入時還在不在（用 wg_atoms._strip_atom_for_injection 模擬，知識段 200 token 上限會截掉第 3 條以後）。
- [臨] 實例（2026-09-04）：core.md 09-01 刪「同步」段（.git→commit+push）＋09-02 atom「上傳前先問人」→ 模型選了同時滿足兩邊的縫：先 commit、問完再 push。Stop 閘 SyncReminder 只看 git status 髒檔，local commit 就讓它閉嘴，模型從此沒有再校正的壓力。scope 改版與本案無關。
- [臨] 修法原則：硬契約寫進必載檔的一句話裡（USER-{user}.md 縮寫指令行），atom 只當補充；寫規則時把「停點」說死（commit 之前 vs push 之前），別用「上傳」這種兩可的詞。

## 行動

- 修剪必載檔前：git log -S 確認被刪句子的契約在別處仍會每 session 進到 context（hook 訊息只在觸發時出現，不算）
- 新 atom trigger 撫到 commit/push/收尾這種高頻詞時，先讀同 trigger 既有 atom，寫明與它們的分界
