# pythonw-下-stdout-為-None-排程腳本秒死陷阱

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: pythonw, Task Scheduler, 排程, schtasks, sys.stdout None, reconfigure, 排程器靜默失敗
- Created-at: 2026-07-08

- Related: 向量庫stale清理失效根因-layer標籤含冒號拆鍵錯位-刪0列仍回報成功

## 知識

- [臨] pythonw.exe（無視窗執行，Task Scheduler 靜默排程常用）下 sys.stdout/sys.stderr 為 None——腳本開頭 sys.stdout.reconfigure(encoding='utf-8') 直接 AttributeError 秒死，Exit code 1 且無任何輸出可查（實證：health-weekly.py 首次排程執行 LastTaskResult=1）
- [臨] 標準防護：`for name in ('stdout','stderr'): s=getattr(sys,name); None → setattr 為 open(os.devnull,'w')，否則才 reconfigure`；所有可能被 pythonw 執行的腳本（hook/排程/MCP）都適用
- [臨] 驗證排程任務真跑通：Start-ScheduledTask 後輪詢 Get-ScheduledTaskInfo 至 LastTaskResult≠267009（still-running），0=成功；另驗證副作用檔案 mtime 確實更新，不能只看註冊成功

## 行動

- 寫任何可能被 pythonw/排程器執行的腳本：入口先防護 stdout/stderr None；注冊排程後必 Start-ScheduledTask 實跑一次驗副作用
