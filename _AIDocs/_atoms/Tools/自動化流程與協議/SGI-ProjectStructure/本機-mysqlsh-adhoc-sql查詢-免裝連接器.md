# 本機-mysqlsh-adhoc-sql查詢-免裝連接器

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: mysqlsh, MySQL Shell, SQL查詢, 查表, 下SQL, 資料庫查詢, MySQL, X protocol, 33060, 3306, SELECT, mysql connector, pymysql, 查DB, sgi_playerdb, ad-hoc sql
- Created-at: 2026-06-17
- Related: toolchain, sgi-client-blob-datamoduledb灣入partialbyjson-readcomplete與enum整數兩坑

## 知識

- [臨] 本機（holylight Windows）已裝 MySQL Shell：`C:\Program Files\MySQL\MySQL Shell 8.0\bin\mysqlsh`，可直接下 ad-hoc SQL 查本機 MySQL、秀結果，**不需裝 Python 連接器**（pymysql / mysql.connector / mysqlx 本機皆無）。本機 MySQL classic 3306 + X protocol 33060 都開。
- [臨] 用法（MSYS2 bash、classic 3306）：`"/c/Program Files/MySQL/MySQL Shell 8.0/bin/mysqlsh" --mysql --sql --host=127.0.0.1 --port=3306 --user=sgi --password=pass --schema=<db> -e "SELECT ..."`。CLI 帶密碼會印 WARNING，用 `grep -viE "WARNING|password|insecure"` 濾掉。多語句用多個 `-e` 或分號。`--mysql`=classic、`--mysqlx`=X protocol(33060)。
- [臨] SGI 本機角色庫：`sgi_playerdb`（user sgi / pass pass；連不上備援名 SGI_PlayerDB_1）。Char_Data_Normalize 正規化新表名=`<模組類名小寫>_main/_sub`（例 herodatamodule_sub），p_group=characterId、p_id=0(main)/subId(sub)，repeated/map 欄存 JSON 字串。
- [臨] 程式化跨 SQL 亦可用框架 `MysqlxClient.ExecuteNonQuery(sql, args)`（Userjoy.BaseServer.Sqlx，無結果集）；臨時查詢/秀結果首選 mysqlsh。

## 行動

- 要查本機 MySQL / 驗 SQL 表 → mysqlsh（免裝連接器），classic 3306 + `--mysql --sql -e`，濾掉 password WARNING
- 多語句分多個 -e 或分號；需 X protocol 用 --mysqlx --port=33060
