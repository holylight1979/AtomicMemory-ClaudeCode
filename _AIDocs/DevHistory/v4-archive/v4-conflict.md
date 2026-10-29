# V4 三時段衝突偵測（Phase 5+6 完整流程）

> 從 Architecture.md 移入（2026-04-17 索引化）。實作：`memory-conflict-detector.py`, `server.js`, `post-git-pull.sh`, `conflict-review.py`。規範真相：`SPEC_ATOM_V4.md` §7。
> keywords: conflict, pending_review, 衝突, write-check, pull-audit, conflict-review, CONTRADICT, EXTEND

## 三時段對照表

shared 寫入的事實衝突防線，由 `memory-conflict-detector.py` 承擔 LLM 分類（gemma4:e4b），`server.js`/git hook/skill 分別對接三個時段：

| 時段 | 觸發點 | 落點 | 關鍵行為 |
|------|--------|------|---------|
| Write-time | `atom_write scope=shared` create 分支 | MCP server.js | vector top-3 ≥ 0.60 → ollama_classify → CONTRADICT 寫 `_pending_review/{slug}.conflict.md`（非 atom、阻擋寫入）；EXTEND + sim ≥ 0.85 reroute 為 `_pending_review/{slug}.md` 草稿 |
| Pull-time | `git pull` 後 `.git/hooks/post-merge` | `hooks/post-git-pull.sh` → detector `--mode=pull-audit` | 讀 `.last_pull_audit_ts` → `git log --since` 抓 shared/*.md 變動 → classify → CONTRADICT 寫 `_pending_review/{slug}.pull-conflict.md` |
| Git-conflict-time | 硬碰硬 merge conflict | `git mergetool` | 純文件約定：Claude 只給合併建議，**不動檔**；整份走 git tool |

## 關鍵機制

- **Fail-open**：vector/LLM 服務 down → verdict=ok + skipped=true（不阻塞所有寫入）
- **Conservative pending**：LLM 分類失敗但 sim ≥ 0.85 → 當作 CONTRADICT 進 pending（漏判好過誤判）
- **`Merge-strategy: git-only`**：標此欄位的 atom 跳過所有 AI 合併（write-check + pull-audit 雙方都跳）
- **敏感類別自動 pending**（Phase 3 既有）：Audience 含 `architecture`/`decision` 強制進 `_pending_review/`（與衝突偵測獨立，互為 AND）
- **管理職 `/conflict-review`**：`commands/conflict-review.md` + `tools/conflict-review.py` 後端，list/approve/reject 三動作；`is_management(cwd, user)` 雙向認證（personal role.md + shared _roles.md 白名單）未通過一律拒絕
- **_merge_history.log**：per-project `{proj}/.claude/memory/_merge_history.log`，TSV append-only 6 欄 `ts, action, atom, scope, by, detail`；action ∈ {auto-merge, pending-create, approve, reject, pull-audit-flag}
- **Approve 流程**：搬 `_pending_review/{slug}.md` → `shared/{slug}.md`、移除 `Pending-review-by:` 行、加 `Decided-by:` + 更新 `Last-used`、刪同名 .conflict.md、POST `/index/incremental` 重索引
- **阻擋寫入但不 isError**：CONTRADICT 回傳 sendToolResult(false)，讓使用者知道 pending 是正常流程

## 完整流程圖（Phase 6 收尾補）

```
┌──────────────────────── Write-time (MCP atom_write) ────────────────────────┐
│                                                                              │
│  caller → server.js → normalize_scope                                        │
│    │                                                                         │
│    ├─ scope=role|personal → 寫 {proj}/memory/{layer}/ ──── END（不檢查衝突） │
│    │                                                                         │
│    └─ scope=shared                                                           │
│        │                                                                     │
│        ├─ skip_gate=false → memory-write-gate（去重 cosine ≥ 0.80） ──→ dedup │
│        │                                                                     │
│        ├─ skip_conflict_check=false → memory-conflict-detector               │
│        │   --mode=write-check（vector top-3 ≥ 0.60 → gemma4:e4b classify）   │
│        │     │                                                               │
│        │     ├─ verdict=CONTRADICT → 寫 shared/_pending_review/              │
│        │     │     {slug}.conflict.md  + merge_history: pending-create       │
│        │     │     回傳 BLOCKED ── END                                       │
│        │     │                                                               │
│        │     └─ verdict=EXTEND sim ≥ 0.85 → reroute 為                       │
│        │         shared/_pending_review/{slug}.md                            │
│        │         +Pending-review-by: management                              │
│        │                                                                     │
│        └─ audience ∈ {architecture, decision}                                │
│            → 強制 reroute 為 shared/_pending_review/{slug}.md                │
│            +Pending-review-by: management  （與衝突檢查獨立 AND）            │
│                                                                              │
│        最終落點：shared/{slug}.md OR shared/_pending_review/{slug}[.conflict].md│
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────── Pull-time (post-merge hook) ────────────────────────┐
│                                                                              │
│  git pull/merge → .git/hooks/post-merge (hooks/post-git-pull.sh)             │
│    │                                                                         │
│    ├─ curl POST /index/incremental → 等 indexing=False 最多 12s              │
│    │   （避免 race：新進 atom 還沒被 vector indexer 看到）                   │
│    │                                                                         │
│    └─ python memory-conflict-detector --mode=pull-audit                      │
│        │                                                                     │
│        ├─ 讀 .last_pull_audit_ts → git log --since 抓 shared/*.md 變動       │
│        ├─ 對每個新 atom 跑 classify                                          │
│        │   CONTRADICT → 寫 shared/_pending_review/{slug}.pull-conflict.md    │
│        │              + merge_history: pull-audit-flag                       │
│        └─ 更新 .last_pull_audit_ts                                           │
│                                                                              │
│  Fail-open：任何步驟掛掉 → warning stderr，不阻擋 pull                       │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────── Review-time (/conflict-review skill) ───────────────────┐
│                                                                              │
│  mgmt_user → conflict-review.py --action=approve|reject                      │
│    │                                                                         │
│    ├─ is_management(cwd, user) 雙向認證（personal role.md + shared 白名單）  │
│    │   失敗 → {"error": "not authorized as management"} ── END               │
│    │                                                                         │
│    ├─ approve {slug} 或 {slug}.resolved                                      │
│    │   │                                                                     │
│    │   ├─ strip Pending-review-by: / append Decided-by: / bump Last-used     │
│    │   ├─ 搬到 shared/{slug}.md（與 resolved 支線共用 stem）                 │
│    │   ├─ 刪同名 .conflict.md（若存在）                                      │
│    │   ├─ 刪 source （_pending_review/{slug}[.resolved].md）                 │
│    │   └─ merge_history: approve + POST /index/incremental                   │
│    │                                                                         │
│    └─ reject {slug}                                                          │
│        ├─ 刪 _pending_review/{slug}*.{md,.conflict.md,.pull-conflict.md}     │
│        └─ merge_history: reject                                              │
└──────────────────────────────────────────────────────────────────────────────┘

JIT 保護：_collect_v4_role_atoms 以 rel_parts[:-1] startswith("_") 過濾
  → shared/_pending_review/* 不會被注入任何 user 的 additionalContext
  → 管理職改從 SessionStart [Pending Review] N 件 提示得知有待裁決項
```
