# 按空白斷詞的token比對拿去比中文原話會失效-中文整句是一個token-比原話要用前後不是英數字的regex

- Scope: global
- Author: holylight
- Source: commit:cfda1231 2026-10-21（修補實證）
- Confidence: [臨]
- Trigger: 中文斷詞, 原話比對, names_item, token 比對失效, 測試名在原話裡
- Created-at: 2026-10-21

## 知識

- [臨] 為指令設計的按空白斷詞比對（例：names_item 找測試名）拿去比使用者的中文原話會失效：中文句子沒有空白，「取消剛才的豁免，test_total 必須修好」整句變成一個 token，找不到 test_total。
- [臨] 比原話要用「前後不是英數字」的 regex（(?<![A-Za-z0-9_])name(?![A-Za-z0-9_])），不用 split 後的 token 集合。

## 行動

- 凡是「使用者原話裡有沒有提到 X」的判斷，先問比對法是不是靠空白斷詞
