# svn commit 中文訊息在 cp950 主控台會亂碼-必加 --encoding UTF-8

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: svn commit, svn 上版, commit 訊息, 亂碼, 中文亂碼, encoding, cp950, Big5, svn log, revprop, pre-revprop-change, 上版訊息
- Created-at: 2026-08-28
- Related: commit-前必須核對-staged-清單而非只信自己-add-了什麼

## 知識

- [臨] **Windows 主控台字碼頁是 950(Big5) 時，`svn commit -F file` / `-m` 的中文 log 訊息會被當成本地編碼解讀後轉存，入庫即亂碼**。log 訊息與 property 的處理路徑不同——`svn propset -F` 讀 UTF-8 檔正常（property 視為二進位安全），只有 log 訊息會轉碼。實例：sgi_server r15323 中文全毀，僅 ASCII 的 commit id 與 SHA-256 三值倖存。
- [臨] **正解＝`svn commit --encoding UTF-8 -F <utf8檔>`**（`svn help commit` 明列 `--encoding ARG`）。注意 `--encoding` 只吃 textual property，對 `svn propset` 二進位屬性會回 E200007，別拿 propset 當驗證代理。
- [臨] **事後補救幾乎不可行**：log 是 revprop，改寫要 `svn propset --revprop -r N svn:log`，但 UJ 的 SVN 伺服器未啟用 `pre-revprop-change` hook，client 端一律回 E165006，必須請管理員暫時開 hook 才改得掉。⇒ **commit 訊息一次定生死，送出前就要把編碼弄對**。
- [臨] 損害控管設計：commit 訊息裡的**對帳關鍵值（commit hash、SHA-256、版號、檔名）保持 ASCII**，即使中文段落壞掉，機器可驗的部分仍完整可用。

## 行動

- svn commit 帶中文訊息 → 一律 `svn commit --encoding UTF-8 -F <檔>`，不要裸用 -F 或 -m
- 送出前若不確定，先 `chcp` 看字碼頁；非 65001 就必須加 --encoding
- 已經送出才發現亂碼 → 先確認伺服器有無 pre-revprop-change hook（`svn propset --revprop` 試一次），沒有就只能請管理員開，別自行嘗試其他改寫路徑
- 重要對帳值寫成 ASCII，讓編碼事故不會毀掉可驗證資訊
