# 核心規則

> 已由 hook／MCP 程式化強制的事（Sync 提醒、並行建議、研究 fan-out、domain 拒寫、版本脈絡 warn、_INDEX 提示）不在此重述；本檔只留「事前就要知道」與「沒有程式閘」的規則。

## 治理原則
- **Native-first**：原生機制（CLAUDE.md / skills / memory / resume）優先；自製只做原生做不到的「結構化 · 可稽核 · 跨-session 高價值」。過度工程的正解是誠實化＋修剪，非推倒重來。
- **根層只在根層改**：`~/.claude` 核心（hooks/lib/tools/skills/rules、根層設定與文件、根層 repo 版控）只在 `~/.claude` session 改；專案 session 遇到 → 不動手，把需求寫成可貼上的 prompt 交給使用者（閘門會擋，擋下訊息附替代做法）。跑根層工具不算改：`python ~/.claude/tools/<tool>.py …`，不 `cd` 進去。
- **可觀測性鐵律**：所有 fail-open「不阻斷但要告知」——降級／靜默失敗必浮出訊號（告警 / stderr / 收尾報告），不得無聲吞掉。

## 知識庫
- 禁憑記憶改碼；斷言嚴重度/blocker/「必爆」前先實證（跑/查/追根源）。細節 [[feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長]]
- 修改核心結構/新認知/踩坑 → 更新 _AIDocs + _CHANGELOG.md（新增時同步 _INDEX.md）；_AIDocs 只放長期參考，規劃/TODO/進行中 → memory/_staging/。
- live 檔（code/config/test）與 atom 只寫現況，不埋版本脈絡（版本/階段標記、日期戳、變更敘事）；編年歸 `_AIDocs/DevHistory/` 與 `_CHANGELOG.md`。

## 記憶
- 寫入一律走 atom_write MCP（自動驗證去重索引），禁直接 Edit atom .md；已記錄事實直接引用；不寫臨時嘗試/未確認猜測。**新 atom 一律 [臨] 起跳**（系統拒收新建 [固]/[觀]），晉升靠使用或 append。
- **Realm**：跨專案通用 → `memory/<範疇>/`（失敗家族 `memory/Failures/<主題>/`）；只在 ~/.claude 內有用 → `realm=local`（`_AIDocs/_atoms/`）。判定三問見 [[realm-範疇分區機制-v5]]。
- **Scope**（問「遷就專案還是遷就人？」）：專案的規則／決策 → `shared`；只關於這個人 → `personal`；本人跨專案偏好 → `personal, cross_project=true`。
- create 必給 `domain`（Lv1 閉合清單 `memory/_meta/taxonomy.json`），不確定落點先 `dry_run`；分不出範疇的知識不寫。

## 對話
- 「用識流…」→ /consciousness-stream；/resume → /continue。
- 獨立子任務可新開對話，拆分前確保知識已存入；Context 壓縮即將發生 → 提醒開新 session。
- 並行 sub-agent／知識檢索 fan-out：hook 命中會提示，但**未命中而明顯受益**（多個互不衝突切面／幫我查・研究一下型請求）仍主動評估；判準 [[workflow-parallel-agents]]、[[workflow-research-fanout]]。
