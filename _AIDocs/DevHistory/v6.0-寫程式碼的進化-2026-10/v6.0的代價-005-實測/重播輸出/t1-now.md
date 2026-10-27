[atom_locations] realm-lexicon.json unavailable (FileNotFoundError(2, 'No such file or directory')); fallback to built-in minimal core-protected list; lexicon disabled (all->core)
[org_memory] workflow/config.json 缺 org_memory 鍵，已停用 org
## A 組：004 五跑第一回合 OverviewHub 事件重播（pointer 對 full）

| 跑 | 事件 | 重播 full 對 transcript 原注入（逐字相同） | 注入 pointer 對 full（逐字相同） | 改檔（擋不擋、擋訊息相同） | 注入裡有卡正文 | 指標制多要讀的卡 |
|---|---|---|---|---|---|---|
| 2026-10-23-CCon-R1 | 17 | 2/2 | 2/2 | 15/15 | 0 | 0 |
Traceback (most recent call last):
  File "C:\Users\holylight\.claude-wt\measure-005\_AIDocs\DevHistory\v6.0-寫程式碼的進化-2026-10\v6.0的代價-導讀卡指標-實測\card_pointer_replay.py", line 194, in <module>
    sys.exit(main())
             ~~~~^^
  File "C:\Users\holylight\.claude-wt\measure-005\_AIDocs\DevHistory\v6.0-寫程式碼的進化-2026-10\v6.0的代價-導讀卡指標-實測\card_pointer_replay.py", line 130, in main
    if o in got_full or "視角：" + wo.GOAL_VIEW_LENS not in o:
                                   ^^^^^^^^^^^^^^^^^
AttributeError: module 'wg_overview' has no attribute 'GOAL_VIEW_LENS'
