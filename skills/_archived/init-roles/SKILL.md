---
name: init-roles
description: 專案多職務模式啟用引導 — 初始化 shared/roles/personal 三層 atom 結構
---

# /init-roles — 專案多職務模式啟用引導

> 在當前專案啟用「多職務共享記憶」的互動引導。
> 建自己的 `personal/{user}/role.md`、`shared/_roles.md` 樣板、補 `.gitignore`、可選安裝 `post-merge` hook。
> 全部呼叫 `~/.claude/tools/init-roles.py` 後端，冪等。

---

## 使用方式

```
/init-roles                # 全流程引導（預設）
/init-roles status         # 只看現況
/init-roles add-member alice:art
/init-roles promote alice  # 加到 Management 白名單
/init-roles install-hook   # 只安裝 post-merge hook
```

---

## Step 0: 偵測專案

用 Bash tool：

```bash
python ~/.claude/tools/init-roles.py --project-cwd="$(pwd)" --status
```

讀回的 JSON：
- `project_root` 空 → 當前目錄不是 V4 合法專案根（無 `.git`/`.svn`/`_AIDocs/`/`.claude/memory/MEMORY.md`）。告知使用者須先在專案根執行。
- 其餘欄位呈現給使用者確認（personal/role.md 是否存在、shared/_roles.md 是否存在、hook 是否已裝、當前 user 的 role + 是否管理職生效）。

---

## Step 1: 核心 bootstrap（預設動作）

```bash
python ~/.claude/tools/init-roles.py --project-cwd="$(pwd)" \
  --bootstrap-personal \
  --scaffold-roles
```

做三件事：
1. 建 `{proj}/.claude/memory/personal/{user}/role.md` 樣板（預設 `Role: programmer`、`Management: false`）
2. 冪等 append `.claude/memory/personal/` 到 `{proj}/.gitignore`
3. 若 `{proj}/.claude/memory/_roles.md` 不存在 → 寫 roster 樣板（成員 + 管理職白名單；與 `wg_roles.load_management_roster` 讀取位置一致）

回報給使用者：改了哪幾個檔、改 vs 沒改。

---

## Step 2: 引導使用者編輯 role.md（人工）

提示：

> 已建立 `.claude/memory/personal/{user}/role.md`，內容是 `Role: programmer` 預設。
> 若你是美術/企劃/其他職務，請立即開檔修改 `Role:` 行（逗號分隔多值，例 `Role: programmer, management`）。

**不自動替使用者改** — role 是使用者自己拍板的事。

---

## Step 3: 互動增成員 / 開管理職（可選）

若使用者要加其他成員或自選為管理職：

```bash
# 加成員（可重複呼叫，冪等覆寫該 user row）
python ~/.claude/tools/init-roles.py --project-cwd="$(pwd)" \
  --add-member alice:art

# 開管理職（白名單端；使用者 personal/role.md 也要自己宣告 Management: true）
python ~/.claude/tools/init-roles.py --project-cwd="$(pwd)" \
  --promote-mgmt holylight1979
```

**雙向認證提醒**（SPEC §6.2）：白名單只是其中一端。使用者自己的 `personal/{user}/role.md` 也必須含 `- Management: true` 或 `- Role: ..., management`，`is_management()` 才會生效。任一缺失 → 無法裁決衝突。

---

## Step 4: 安裝 post-merge hook（保守，**先詢問後才裝**）

SPEC §9「git/SVN 自動 add = 否（保守）」— 不主動寫 `.git/hooks/`，先問使用者：

> **要安裝 `post-git-pull.sh` 到 `.git/hooks/post-merge` 嗎？**
> 它在 `git pull / merge` 後自動跑 pull-audit，偵測 shared/ 新進 atom 的事實衝突。
> Fail-open：audit 失敗不擋 pull。

回答是 → 執行：

```bash
python ~/.claude/tools/init-roles.py --project-cwd="$(pwd)" --install-hook
```

回報安裝路徑、chmod 是否成功。

回答否 → 告知日後可自行 `cp ~/.claude/hooks/post-git-pull.sh <proj>/.git/hooks/post-merge && chmod +x` 或重新 `/init-roles install-hook`。

---

## Step 5: 總結

顯示：
- 哪些檔案被建立 / 更新
- 使用者下一步要做的事（改 role.md、安裝 hook、跑 `/init-roles status` 驗證）
- 使用者現在的有效角色 + 是否管理職生效

若管理職未通過雙向認證 → 明確指出缺哪一端：
- personal 宣告缺 → 指向 `personal/{user}/role.md`
- shared 白名單缺 → 建議跑 `/init-roles promote <user>`

---

## 錯誤處理

| 情境 | 處理 |
|---|---|
| 非 V4 專案根（無標記） | 告知使用者要在專案根目錄執行；不動任何檔 |
| 已經全部就緒 | 回 `changed: false`，告知無事可做 |
| hook source 缺失 | 告知 `~/.claude/hooks/post-git-pull.sh` 不見，需先修 global 安裝 |
| 非 git repo | `install-hook` 失敗，告知使用者專案尚未 `git init` |

---

## 注意事項

- 不動使用者既有的 `role.md`（只建不覆寫）
- `.gitignore` 冪等 append（不重複寫入）
- `shared/_roles.md` 的成員 table 依 user 欄覆寫既有 row、否則 append（冪等）
- Management 白名單 append 前先檢查 user 是否已列（冪等）
