# 無頭驗收實跑期間不要合併進live-受測session的hook程式是live的只有資料根是副本-中途合併會讓同一題前後半段跑不同程式

- Scope: global
- Author: holylight
- Source: 第二波 C′ 第二跑（results/2026-10-21-C2）與總控台 16:50～17:25 三次合併對照
- Confidence: [臨]
- Trigger: 無頭實跑, 驗收期間合併, WG_CLAUDE_DIR, 受測資料根, claude -p 驗收, 程式是 live 的, 混淆因素
- Created-at: 2026-10-21
- Quote: 「改 Opus」

## 知識

- [臨] 無頭 claude -p 驗收只把資料根（WG_CLAUDE_DIR）指到副本，hook／lib／MCP 程式每次呼叫都從 live 載入；總控台在題目跑到一半時合進 main，同一題前後半段跑的是不同程式，判分時分不出是機制沒動還是中途被換掉（實例：一題 40 分鐘內合進三個分支，第二意見閉第一次有擋、第二次只提醒）。
- [臨] 规矩：實跑前記下 live HEAD，跑完前不合不推；非合不可就停掉實跑重來，判分信要寫明受測時的 HEAD。要並行就把程式樹也複製一份（或用 worktree 當程式根）再跑。
- [臨] 受測 session 的模型吃 settings.json 的 model（設 fable 就是 Fable，大題一次 50 美元）；要換用 `ANTHROPIC_MODEL=claude-opus-5-5` 環境變數前綴跑 claude -p，不改腳本也不動使用者設定；成本約半，代價是不再是使用者真實用的模型。Opus 比 Fable 更常用 heredoc 寫檔。

## 行動

- 起無頭驗收前寫下 live HEAD 並在接續單標「實跑中、凍結合併」，跑完才合
- 判分時先核對整題期間 live HEAD 有沒有變，變了就標混淆
