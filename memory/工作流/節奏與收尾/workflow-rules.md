# 工作流規則（全域）

- Scope: global
- Confidence: [固]
- Type: procedural
- Trigger: 工作流程, 大型任務, 分階段, SOP, 任務拆分, 上版, GIT, Phase
- Created: 2026-03-06
- Tags: workflow, vcs
- Related: decisions, workflow-svn, workflow-icld, handoff-綜觀品質與抗失真寫法, feedback-workflow-discipline, memory-pipeline-silent-failure-2026-05, workflow-parallel-agents, atom-table-support, feedback-memory-system-doc-sync, atom-usefulness-loop, a執p-自執驗上p-自動完工協議, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, git-已push-commit-勿改寫-雙-push-url-gitlab-main-force-保護致遠端分叉, pan-hermes不移植部件與vscode-text-block不落盤實測, workflow-research-fanout, preferences

## 知識

### 大型計畫執行
- 分階段 session 執行
- 每階段：完成 → 驗證 → 上傳 GIT → 提供下一階段 prompt 給使用者
- **「執驗上P」**：階段收尾口令，等同 執行 → 驗證 → 上 GIT → 產 Prompt（四步都做完）
- 拆分規則 → 見 `workflow-parallel-agents`（何時拆 sub-agent）與 `handoff-綜觀品質與抗失真寫法`（開新 session 的交接寫法）

### 製程選擇
- **Phase 模式**（預設）：按技術層切分（定義→邏輯→UI），每 Phase 結束「執驗上P」
- **ICLD 模式**：按功能切片切分 → 詳見 `workflow-icld.md`

選擇標準：需要中間可驗證的功能節點 → ICLD；按層堆疊即可 → Phase

### GIT / 同步流程
→ 同步條件見 `rules/core.md`「同步」段（_AIDocs→_CHANGELOG｜新知識→atom｜.git→commit+push｜.svn→commit；clean 後 Guardian Stop gate 自動標 sync_completed）
→ 「上GIT」「執P」等縮寫定義見 `preferences` atom（memory/工作流/節奏與收尾/preferences.md）

## 行動

- 大型任務主動拆分多個 session 階段，每階段結束提供延續 prompt
- 功能需求 / 拆解請求 → 先評估規模 → 滿足 ICLD 條件見 `workflow-icld.md`
- 批量修改先確認 1-2 個模式正確，再批量執行
- Token 節省：有 _AIDocs 文件的不重新掃描原始碼，直接引用文件

