# 病灶文件：排程器

這份文件列排程器已知的形狀病灶；每節一個，前 N 節優先。

## 病灶一：邊界比較漏等號
shape: `len\(\w+\)\s*>\s*cap`
位置：`src/sched/queue.py:41`
規格｜第 3 節「插播上限含等號」

## 病灶二：兩步寫入沒原子性
shape: `mark_done\(.*\)\s*\n\s*write_back`
位置：`src/sched/returns.py:17`
規格｜待規格

## 病灶三：空清單用負索引
shape: `\[-1\]`
位置：`src/sched/queue.py:88`
規格｜第 5 節「空槽」

## 病灶四：巢狀四層
位置：`src/sched/plan.py:120-160`
規格｜待規格

## 病灶五：重複掃描
位置：`src/sched/plan.py:200`
規格｜待規格

## 病灶六：命名不一致
位置：全域
規格｜待規格
