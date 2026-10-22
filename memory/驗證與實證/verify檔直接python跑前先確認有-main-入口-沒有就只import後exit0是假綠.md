# verify檔直接python跑前先確認有__main__入口-沒有就只import後exit0是假綠

- Scope: global
- Author: holylight
- Source: reading-path 減量交付（2026-10-22）
- Confidence: [臨]
- Trigger: 直接跑, __main__, 假綠, exit 0, 哨兵尾行, verify 直接 python
- Created-at: 2026-10-22

## 知識

- [臨] 沒有 `if __name__ == "__main__"` 的測試檔，「python 檔名.py」只 import 完就 exit 0，看起來像過了；宣稱「直接跑也過」之前先 grep 入口，並看尾行有沒有 `<NAME>_CHECK PASS`；沒尾行就不算這種驗證。

## 行動

- 報「直接跑 PASS」前：該檔有 __main__ 入口、尾行印哨兵，兩個都有才算
