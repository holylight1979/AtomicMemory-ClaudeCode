# 核心規則

## 治理原則
- **Native-first**：原生機制（CLAUDE.md / skills / memory / resume）優先；自製只做原生做不到的「結構化 · 可稽核 · 跨-session 高價值」，不為想像中的需求長枝葉。過度工程的正解是誠實化＋修剪，非推倒重來。
- **可觀測性鐵律**：所有 fail-open「不阻斷但要告知」——降級／靜默失敗必浮出訊號（告警 / stderr / 收尾報告），不得無聲吞掉。

## 知識庫
- 開工前查 _AIDocs/_INDEX.md 確認已有文件；禁止憑記憶改碼
- 斷言嚴重度/blocker/「必爆」前先實證（跑/查/追根源）；框架前提跨域複用先驗新對象型別/值域。細節 [[feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長]]
- 修改核心結構/新認知/踩坑 → 更新 _AIDocs + _CHANGELOG.md；新增時同步 _INDEX.md
- _AIDocs 只放長期參考知識；規劃/TODO/進行中 → memory/_staging/

## 版本與文件治理（timeless）
- live 檔（code/config/test）與 atom 只寫現況，禁埋版本操作脈絡（版本/階段標記、日期戳、變更敘事）；舊版本宣告主動移除；編年紀錄歸 `_AIDocs/DevHistory/` 與 `_CHANGELOG.md`。完整 pattern + KEEP 邊界見 [[feedback-live-檔與記憶不留版本操作脈絡歷史歸專門檔]]；`hooks/version_guard.py` 程式化 warn。

## 記憶
- 分類：「記住」→[固]、反覆模式→[觀]、做取捨→[臨]；不寫臨時嘗試/未確認猜測
- 寫入用 atom_write MCP（自動驗證去重索引晉升）；已記錄事實直接引用
- **Realm**：核心知識（跨專案通用）→ `memory/<範疇>/` 全專案注入（失敗家族 `memory/Failures/<主題>/`）；非核心（只在 ~/.claude 內有用）→ `_AIDocs/_atoms/<domain>/` 僅本環境注入（scope 仍 global）。判定三問與機制全貌見 [[realm-範疇分區機制-v5]]。
- **Scope 分界**（問「遷就專案還是遷就人？」）：專案的規則／決策（專名、此專案、程式、流程、格式、工具選型、上傳／發布／版控）→ `scope=shared`（Author 自動記提出者，異議找 Author）；只關於這個人（要 AI 怎麼溝通／回饋、個人環境帳號習慣）→ `scope=personal`（只本專案、只本人）；本人在所有專案都適用的偏好 → `scope=personal, cross_project=true`（住 `~/.claude/memory/personal/<user>/`）。讀取端只給本人與本專案：他人 personal、他專案 atom 不進候選池——寫錯層的知識別人看不到、或看到不該看的。
- **分類必填**：`atom_write(mode=create)` 對 global／feedback-*／shared 一律給 `domain`（`<Lv1>[/<Lv2>]`，Lv1 閉合清單見 `memory/_meta/taxonomy.json`；別名如 `vcs/git` 自動 snap 回 `版控/Git`；不確定落點先 `dry_run`）。分不出範疇的知識不寫 atom。

## 同步
完成修改後主動提出：_AIDocs→_CHANGELOG | 新知識→atom | .git→commit+push | .svn→commit
（git/svn clean 後 guardian Stop gate 自動標 sync_completed）

## 對話
- 「用識流…」→ /consciousness-stream
- 獨立子任務可新開對話；拆分前確保知識已存入
- 段落完成即存；Token 快上限時優先存檔；Context 壓縮即將發生 → 提醒開新 session；/resume → /continue
- 多 agent 並行：任務**明確要求**或**明顯受益**（多個互不衝突的獨立切面）才評估拆，不每 prompt 硬掃。判準見 [[workflow-parallel-agents]]
- 知識檢索型請求（幫我查/搜索/我想知道/研究一下）：預設兩階段 fan-out — Stage A 關鍵字擴充（含中↔英術語橋）→ Stage B 記憶庫+網路併搜；本地程式碼定位型則單階段 Explore fan-out。判準見 [[workflow-research-fanout]]
