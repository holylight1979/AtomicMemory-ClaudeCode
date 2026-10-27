# 大型svn工作副本整棵svn-status很慢-每檔約45微秒-hook裡查svn狀態要設時間上限-逾時改查點名的檔並記住這個根很慢

- Scope: global
- Author: holylight
- Source: 2026-10-23 Bash 寫入補算改檔實作
- Confidence: [臨]
- Trigger: svn status 很慢, svn status 耗時, 大型 svn 工作副本, 整棵 svn status, hook 查 svn, svn 逾時, 點名的檔
- Created-at: 2026-10-23
- Related: 取svn工作副本的base版-先用status-xml挑出本地改過的檔只對它們svn-cat-r-base-沒改過的base就是工作樹內容

## 知識

- [臨] 大型 svn 工作副本整棵 `svn status` 很慢，耗時跟檔數成正比：每檔約 45µs，1.3 萬檔的子目錄 0.5～0.9 秒，百萬檔級要一分鐘以上；帶幾個檔路徑的 `svn status <檔…>` 只要 0.1～0.2 秒。
- [臨] 所以 hook（有幾秒時間上限的地方）查 svn 狀態一定要設時間上限；逾時就改成只查點名的檔，並記住「這個根很慢」，之後直接只查點名的，不再每次先試整棵。

## 行動

- hook 裡跑 svn status：設逾時；逾時改查點名的檔，把慢的根記下來下次直接只查點名的
