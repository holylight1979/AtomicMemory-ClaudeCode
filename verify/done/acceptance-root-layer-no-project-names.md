---
task_slug: root-layer-no-project-names
session_id: d78db3ba-6961-4ed3-89a5-1079c7e2da54
created_at: 2026-10-08
source: multifile
status: done
---
## 必須發生
- realm gate 認得本機已登記專案名（registry 根資料夾名、ASCII 別名、project_names 手列名單）與專案根底下的絕對路徑
- 根層 cwd 寫全域卡片時 realm gate 也啟動；本人跨專案 personal 卡片同受 realm gate
- 自動補的 Quote 欄在根層卡片裡不帶專案名與專案路徑
- 版控內的根層檔案（卡片、skill、程式註解與說明、測試、文件）不再出現專案名與專案路徑，必要的第三方產品名除外
- 整張專屬某專案的卡片移出根層
- 改寫遵守四原則：非必要就拔名只寫要點或現象；要指涉寫「某專案」；代稱優先於路徑；拔名不得讓事實走樣
## 禁止發生
- 不動其他 session 的未提交改動（settings.json 等）
- 不改變任何知識的意義、不刪知識，只去專案化
- registry 不進版控
## 驗證指令
- python -m pytest hooks/verify lib/verify tools/verify -q
- git ls-files 全掃專案名清單，命中只剩說明過的例外
