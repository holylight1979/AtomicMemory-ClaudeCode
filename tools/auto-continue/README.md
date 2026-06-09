# auto-continue — Auto-Handoff Phase 4 外部編排 watcher（PoC）

> ⚠️ **實驗性質 · 非正式上線元件。** 這是 Auto-Handoff 的「最後一哩」：把半自動的高品質
> handoff stub（Phase 1-3 hook 產出）餵給一個**獨立常駐腳本**，自動 spawn 新 headless
> session 跑 `/continue` 接續，完工再寫新 stub、遞迴。**超出 CC hook 能力邊界**（hook 是
> 被動被呼叫、無 spawn API），故獨立成 tool。設計依據：[plans/wise-wobbling-gem.md](../../plans/wise-wobbling-gem.md) line 50-58 / 81-82。

## 為什麼能做（已實證，非憑記憶）

依 atom `cc-能力查證反編譯實跑-binary`，先實證 `claude -p` headless 是否支援 skill `/continue`：

| 查證 | 方法 | 結論 |
|------|------|------|
| 字串表 | `rg -a` 掃 binary | `local-command-stdout`×51 / `slashCommand`×18 / `disable-slash-commands`×8 → slash-command 處理健全 |
| --help | 實跑 binary | `-p/--print` 存在；`--disable-slash-commands`=「Disable all skills」（slash 即 skills、預設開）；`--bare` 註「Skills still resolve via /skill-name」 |
| **實跑** | `claude -p "/continue" --output-format json`（隔離空目錄） | `is_error:false`、`exit 0`、`num_turns:3`、`result` 為 /continue 在 0-stub 時原文且回報掃了 skill 文件兩條路徑 → **skill 邏輯實際執行**，非 prompt 透傳 |

環境：VSCode 擴充套件 `claude.exe` **2.1.169**（native install 停在 2.1.37 過舊；版本分裂陷阱）。
完整查證紀錄見 [auto_continue.py](auto_continue.py) 檔尾「實證紀錄」區塊。

## 機制

```
監看 resolve_staging_dir(cwd) 的 next-phase*.md
  → 偵測到穩定 stub（mtime 穩定 ≥ stub_stable_sec）
  → 檢查四道 guard
  → 起 headless `claude -p "/continue"`（讀+刪 stub、執行續接、完工寫新 stub）
  → 子 session 同步阻塞至結束（序列化 = 天然「當前 session 結束才接棒」）
  → 下輪 poll 偵測到新 stub → 再 spawn → 遞迴
  → 無新 stub 超過 idle_timeout → 鏈結束，正常退出
```

`/continue` 的 staging 解析與本 watcher 的 `resolve_staging_dir` 對齊（同一 source）。
stdin 接 `DEVNULL` 以免每次 spawn 卡 `no stdin data received in 3s`（實證觀察）。

## 四道 guard（失控防護）

| # | 組態 | 作用 |
|---|------|------|
| 1 | `max_consecutive_spawns` | 連續 spawn 數硬上限（預設 5） |
| 2 | `budget_usd` | 累計成本上限；從子 session JSON `total_cost_usd` 加總（預設 $5） |
| 3 | `confirm_every_n` | 每 N 次 spawn 設人工確認點（0=關）。TTY→`input()`；detached→等 `confirm.ok` flag 檔 |
| 4 | `kill_switch` | flag 檔（預設 watch dir 下 `STOP`）。每輪 poll + 每次 spawn 前檢查，命中即停 |

附帶 **single-stub 不變式**：watch dir 同時 >1 個 `next-phase*.md` 時停手交人工
（headless `/continue` 遇多檔會列選單、無 stdin 可選 → 會卡死）。正常鏈每次恰好 1 個。

## 使用

```powershell
# 先安全試跑（只偵測不 spawn）
python tools\auto-continue\auto_continue.py --cwd C:\YourProject --dry-run

# 正式跑（用組態檔）
copy tools\auto-continue\config.example.json tools\auto-continue\config.json
python tools\auto-continue\auto_continue.py --cwd C:\YourProject --config tools\auto-continue\config.json

# CLI 覆蓋（不寫組態檔）
python tools\auto-continue\auto_continue.py --cwd C:\YourProject `
    --max-spawns 3 --budget-usd 2.0 --confirm-every 2 --kill-switch STOP

# 緊急停手：在 watch dir（staging 目錄）建立 STOP 檔
New-Item <watch_dir>\STOP -ItemType File
```

`--bin` 不給時自動偵測 claude（PATH → VSCode 擴充套件最新版 → native versions）。

## 風險與限制（誠實聲明）

- **`permission_mode` 預設 `bypassPermissions`**：headless 自主接續**必須**非互動授權，否則
  print 模式無法回應權限提問而中斷。代價是子 session 可不經詢問動檔 / 跑指令。**blast radius
  由四道 guard + single-stub 不變式界定**——務必先 `--dry-run`、設低 `max-spawns`/`budget`、
  開 `confirm-every`，確認行為再放寬。
- **成本**：每次 spawn = 一次完整 model session（實測單次 $0.27+）。`budget_usd` 是累計硬煞車。
- **核心層（`~/.claude`）路徑歧異**：`/continue` skill 文件路徑對 `~/.claude` 自身的解析與
  `resolve_staging_dir` 的核心特例不完全一致；watcher 對**專案目錄**運作最乾淨。核心層使用屬
  skill 既有議題、不在 Phase 4 範圍。
- **未做**：跨重啟累計成本持久化、桌面通知、Linux/mac binary 偵測細節（PATH 可用即可）。
- **定位**：PoC，驗證可行性與 guard 骨架；可不納入正式上線。

## 測試

`verify/verify_auto_continue.py`（pytest，被 [run_verify.py](../../run_verify.py) 自動收）以注入的
spawn/sleep/now/confirm + 模擬 stub 驗四道 guard、single-stub 不變式、idle 退出、JSON 解析、
組態優先序——全程不真起 model session。
