---
name: refile
description: 拖入非 _AIDocs/_atoms/ 下的任意 .md 檔，先過輸入護欄與核心/設定檔辨識護欄，再用 realm 分類引擎提議歸檔位置，互動確認後移檔並掃描需同步的說明文件引用
userInvocable: true
triggers: refile, 歸檔, 手動歸檔, 重新歸位, 歸到應在的地方, 這檔案該放哪, atom 歸類, 移檔歸位, realm 歸檔, 把這個 md 歸位
pattern: pipeline
---

# Skill：refile（Pipeline）

> 把「**非 `_AIDocs/_atoms/` 下的任意 `.md`**」歸到應在的地方：三段護欄 → 互動確認 → 移檔 → doc-sync。
> deterministic 判定全在 [scripts/refile_classify.py](scripts/refile_classify.py)；**本檔只編排互動，禁止憑眼力重判護欄**。

## 觸發

- 使用者下 `/refile <path-to.md>`
- 「這個 `.md` 該放哪」「把這檔歸位／歸到 atom 樹」「幫我重新歸位這份筆記」

## 核心鐵則

1. **護欄判定一律以 `refile_classify.py` 的 `verdict` 為準**（邏輯優先於語意，不准 LLM 自己判是不是核心檔）
2. `verdict=core_file` → **絕不搬**，回報關聯後只提供「中斷／升級架構級計畫」二選一
3. **任何移檔前必取得使用者明確確認**（這是互動式 skill，非自動）
4. **移檔後必跑 doc-ref 掃描**，列出需同步的人面向文件

## 工作流程

### Step 1：取得目標路徑
- **動作**：從引數取 `<path>`；缺 → 問使用者「要 refile 哪個 `.md`？」
- **完成判定**：手上有一個具體 path 字串

### Step 2：分類（跑護欄引擎）
- **動作**：`python skills/refile/scripts/refile_classify.py classify "<path>"`
- **完成判定**：exit 0 且 JSON 含 `verdict` 欄
- **分流**：依 `verdict` 走下方〈verdict 分流〉；只有 `classify` 才進 Step 3

### Step 3：移檔（**僅 `verdict=classify` 且使用者確認後**）
- **動作**：依 `is_indexed_atom` / `looks_like_atom` / `proposed_realm` 挑工具（見〈移檔決策表〉）
- **依賴**：Step 2 的 JSON + 使用者確認
- **完成判定**：目標出現在新位置（index path 已更新 ∨ loose 原檔已移除）

### Step 4：移檔後 doc-sync
- **動作**：`python skills/refile/scripts/refile_classify.py docrefs "<舊 rel path>"`
- `hits` 非空 → 列「需同步文件」並逐筆提議改引用（使用者確認後改，或標為待辦）
- **完成判定**：`hits` 全數列出並提出處置

## verdict 分流

| verdict | 處置 |
|---------|------|
| `already_archived` | 已在 `_AIDocs/_atoms/` 下，回報「已歸檔、無需 refile」，結束 |
| `not_found` | 回報找不到檔案，請使用者確認路徑，結束 |
| `core_file` | **不搬**。用 `signals` + `index_doc_hits` + atom `Related` 綜述：「這是原子記憶系統核心/設定檔，角色＝X、關聯子系統＝Y/Z」，再提供二選一：① **中斷** ② **升級為架構級改造計畫**（進 EnterPlanMode）。結束 |
| `classify` | 進 Step 3（先取得確認） |

## 移檔決策表（`verdict=classify`）

| 情況 | 動作 |
|------|------|
| 既有 indexed atom（`is_indexed_atom=true`） | `python tools/atom-set-realm.py set <stem> --domain "<proposed_domain>"`（py 端即時、含 `.access.json` 原子搬） |
| loose `.md` 且 `looks_like_atom=true`、`proposed_realm`∈{local, else} | 讀內容 → `atom_write`（`realm=local`, `domain=<proposed_domain>`）建立 atom → 確認落點 → 刪原 loose 檔 |
| `proposed_realm=core` | 判為跨專案核心 → `atom_write` 建為 **core** atom（不帶 realm，**必給 `domain="<Lv1>[/<Lv2>]"`**：Lv1 閉合清單見 `memory/_meta/taxonomy.json`，落 `memory/<Lv1>/`；feedback-* 標題 domain=失敗主題 → `memory/Failures/<主題>/`；分不出範疇不建 atom）；若本就是既有 core atom 則維持原狀、告知無需搬；既有 core atom 換範疇用 `tools/atom-move.py move <slug> --from memory/<舊> --to memory/<新Lv1>[/<Lv2>]` |
| `proposed_realm=defer` | LLM 不可用（基礎設施失敗）→ **不搬**，告知稍後重試，或請使用者人工指定 `--domain` 後走 atom-set-realm |
| `looks_like_atom=false`（TODO / transcript / 散文） | **不塞 atom 樹** → 建議移到 `memory/_staging/` 或 `_AIDocs/`（一般 `mv`），使用者確認 |

- 任一**建立/搬移後**跑 `python tools/sync-memory-index.py --write` 刷新 catalog（與 SessionEnd sweep 同款補觸發）。
- 多段 `domain` 經 `atom_write` 若落點與提議不符（MCP 舊碼單段路由）→ 用 `atom-set-realm.py` 校正到完整路徑。

## 反模式

- ❌ 不跑 `refile_classify.py`、自己用眼睛判是不是核心檔
- ❌ `core_file` 還硬搬（會破壞 bootstrap/設定鏈）
- ❌ 沒問使用者就移檔
- ❌ 移完不掃 doc-ref，留下說明文件的死引用
- ❌ 把 TODO/transcript 硬塞進 atom 樹

## 注意事項

- `proposed_domain` 已過 `normalize_domain_path` canon（對既有樹 snap + 增量深度閘 depth=volume），直接採用即可。
- atom 間 `Related` 用 **slug** 引用、搬 path 不斷；風險僅在**人面向文件**按 path/檔名引用 → 靠 Step 4 掃補。
- 引擎、詞庫自學、canon、Fail-safe 四態的機制全貌見 atom `realm-範疇分區機制-v5`（與 SessionEnd sweep 共用同一引擎，本 skill 為手動前端）。
