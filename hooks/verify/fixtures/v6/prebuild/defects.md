# fixture 病灶清單（verify_prebuild_template 用）

| 位置 | 症狀 | 根因 | 修法 | 狀態 | 規格 | 形狀 |
|---|---|---|---|---|---|---|
| `src/` | 吞例外 | 沒人擁有錯誤路徑 | 改成明寫的錯誤訊號 | 未修 | `待規格：錯誤碼表還沒定` | `shape: except\s*:\s*pass\b` |
| `src/` | 一行兩個 lambda | 把分支塞進表達式 | 抽具名函式 | 未修 | `Spec§2` | 無 |

shape: lambda\b.*\blambda\b
