# 測試隔離的這次執行記號要在開子行程前就存在-用root-conftest每次換的暫存目錄當記號-第一次用到才產生的環境變數記號會分帳或共用

- Scope: global
- Author: holylight
- Source: 2026-10-23 斷路器照對象計數修補實測
- Confidence: [臨]
- Trigger: 這次執行記號, 測試隔離記號, run id, pytest.main 兩次, 子行程分帳, root conftest 暫存目錄, TMPDIR 當記號
- Created-at: 2026-10-22
- Related: 子行程沙箱改暫存目錄要連TMPDIR一起改-Git Bash帶TMPDIR=/tmp-gettempdir先看它, conftest隔離資料根要先放本樹受版控資料否則默默讀live設定與真實atom的既有案整批紅-放pytest-configure不放模組層-同行程多次pytest-main才都隔離

## 知識

- [臨] 測試隔離用的「這次執行」記號，要在案例開任何子行程之前就存在。
- [臨] 用 root conftest 每次 pytest 換的暫存目錄（TMPDIR／TEMP／TMP，子行程會繼承）當記號。
- [臨] 不要在第一次用到時才產生一個寫進環境變數的記號：子行程先用到會跟父行程分帳，同一個行程跑兩次 pytest.main 又會共用同一份。

## 行動

- 要分「這次執行」的帳時，記號取 root conftest 換好的暫存目錄，不另產生
