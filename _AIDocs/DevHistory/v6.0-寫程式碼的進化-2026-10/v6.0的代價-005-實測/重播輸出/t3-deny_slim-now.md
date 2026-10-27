[atom_locations] realm-lexicon.json unavailable (FileNotFoundError(2, 'No such file or directory')); fallback to built-in minimal core-protected list; lexicon disabled (all->core)
估算式（同 ftb）：1.321×中日韓字＋0.534×其他字＋-8.8×段數，平均絕對誤差 5.0%
砍前（被之後每次呼叫重讀的總量）：擋訊息本文＋附卡（PreToolUse＋Stop 兩份）全部呼叫 77,302、只算照常 35,249；其他帶判準卡的段（MCP 回覆、注入）全部呼叫 42,359、只算照常 18,264

## 2026-10-23-CCon-R1：第一回合 22 次呼叫、輸入 1,485,029；PreToolUse 擋 9 筆（DataFileAsk 1）
| 呼叫 | 段 | 舊 tok | 新 tok | 被讀幾次 |
|---|---|---|---|---|
| 6 | Guardian:OverviewHub｜擋訊息附的判準卡 | 693 | 175 | 16 |
| 15 | Guardian:DataFileAsk｜擋訊息本文 | 600 | 370 | 7 |
文字少讀：全部呼叫 9,907；只算照常呼叫（ftb b 口徑）5,068
讀檔提示：被擋 Edit 在 call 14；去掉 call 15、16（輸入 151,863），之後每次少讀 D=1,433；提示 2 則＋宣告句（65 tok）被重讀加回 4,397；第一回合 1,485,029 → 1,330,398，省 154,631；秒（模型／含工具與 hook）6.7／9.7
砍前（被之後每次呼叫重讀的總量）：擋訊息本文＋附卡（PreToolUse＋Stop 兩份）全部呼叫 91,020、只算照常 45,011；其他帶判準卡的段（MCP 回覆、注入）全部呼叫 58,023、只算照常 27,338

## 2026-10-23-CCon-R2：第一回合 24 次呼叫、輸入 1,663,606；PreToolUse 擋 8 筆（DataFileAsk 1）
| 呼叫 | 段 | 舊 tok | 新 tok | 被讀幾次 |
|---|---|---|---|---|
| 7 | Guardian:OverviewHub｜擋訊息附的判準卡 | 690 | 174 | 17 |
| 7 | Guardian:OverviewHub｜擋訊息附的判準卡 | 327 | 174 | 17 |
| 15 | Guardian:DataFileAsk｜擋訊息本文 | 600 | 370 | 9 |
文字少讀：全部呼叫 13,440；只算照常呼叫（ftb b 口徑）7,169
讀檔提示：被擋 Edit 在 call 14；去掉 call 15、16（輸入 155,565），之後每次少讀 D=1,571；提示 1 則＋宣告句（65 tok）被重讀加回 4,095；第一回合 1,663,606 → 1,501,139，省 162,467；秒（模型／含工具與 hook）6.7／9.6

## 合計（砍後＝文字瘦身＋讀檔提示生效；讀檔提示沒生效時只算文字瘦身）
- CCon-R1：第一回合 1,485,029 → 讀檔提示生效 1,322,101（省 162,928）；只靠文字 1,475,122（省 9,907）；擋 9 → 8
- CCon-R2：第一回合 1,663,606 → 讀檔提示生效 1,489,769（省 173,837）；只靠文字 1,650,166（省 13,440）；擋 8 → 7
DENY_SLIM_REPLAY DONE r1_text=0.99 r2_text=1.34 r1_df=15.46 r2_df=16.25 avg_total=16.84 blocks_before=17 blocks_after=15 secs=6.7
