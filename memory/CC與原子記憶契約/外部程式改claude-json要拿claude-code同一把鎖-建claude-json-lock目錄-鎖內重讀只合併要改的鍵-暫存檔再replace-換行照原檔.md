# 外部程式改claude-json要拿claude-code同一把鎖-建claude-json-lock目錄-鎖內重讀只合併要改的鍵-暫存檔再replace-換行照原檔

- Scope: global
- Author: holylight
- Source: 2026-10-21，實讀 claude.exe 2.1.304、真打 ~/.claude.json 兩次
- Quote: 「不對，checklist 連打勾那個 check 狀態都通通沒了只剩大量文字..，這樣是要怎麼綜觀進度?」
- Confidence: [臨]
- Trigger: ~/.claude.json, claude.json 寫入, hasTrustDialogAccepted, 信任鍵, proper-lockfile, .claude.json.lock, saveConfigWithLock, 原子寫入 config, 整份覆寫設定檔, console-spawn ensure_trust
- Created-at: 2026-10-21
- Depends: path:C:/Users/holylight/.claude/tools/console-spawn.py

## 知識

- [臨] Claude Code（claude.exe 2.1.304 實讀 saveConfigWithLock）存 ~/.claude.json 用 proper-lockfile：鎖是 `<檔>.lock` 目錄（預設 stale 10 秒），鎖內重讀、以磁碟現值合併 projects，再寫 `.tmp.<pid>.<hex>` 改名換上。外部程式整份讀→改一鍵→整份寫回會蓋掉別的 session 剛寫的鍵（實測 KeyError numStartups），寫到一半斷掉會留半截檔讓所有 session 起不來。
- [臨] 外部程式改這個檔照「拿同一把鎖（建 .claude.json.lock 目錄，拿不到就等不搶）→ 鎖內重讀 → 只合併要改的一鍵 → 同目錄暫存檔＋os.replace → 放鎖」；持鎖超過 stale 一半就不換上也不刪鎖。檔格式是 LF、結尾沒換行、indent 2、非 ASCII 不跳脫；Windows 的 write_text 沒帶 newline 會整檔翻成 CRLF。壞 JSON、檔不在、projects 不是物件 → 不寫、印原因、FAIL。
- [臨] 驗證法：只比寫前寫後的鍵名差異（頂層 []、projects 只多那一鍵），再在暫存目錄跑 `claude mcp get <user scope server>` 確認 Claude Code 解析得了；收掉那鍵後位元組要與寫前相同。實作在 tools/console-spawn.py（check_trust／lock_config／write_config_atomic／unlock_config）。

## 行動

- 任何工具要寫 ~/.claude.json：照 console-spawn 的四步，不自己整份寫回
- 驗寫入工具：鍵名差異＋claude mcp get
