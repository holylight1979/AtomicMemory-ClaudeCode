# 失敗的工具呼叫CC只送PostToolUseFailure-靠PostToolUse記改檔與紅測的機制看不到exit1的heredoc寫檔-修改清單與紅測清單會漏記

- Scope: global
- Author: holylight
- Source: track-gate-small-fixes 001 與 track-entrypoint-contract 004 實證；第二波驗收 A-1、B-1(B2) transcript
- Confidence: [臨]
- Trigger: PostToolUseFailure, is_error, exit 1 寫檔, modified_files 漏記, failing_tests 空, heredoc 沒記到, PickOne 沒問, G11 沒量到
- Created-at: 2026-10-21
- Quote: 「收割此session的知識與經驗」

## 知識

- [臨] Claude Code 對結束碼非 0（is_error）的工具呼叫不送 PostToolUse，只送 PostToolUseFailure；只接 PostToolUse 的記帳（modified_files、old_test_added、failing_tests、驗證收據）對 `cat > x.py <<EOF … && pytest` 這種「寫進檔了但指令 exit 1」全部漏記，下游的最該修、拐彎判斷、紅測守門就整條沒被問且無留帳（第二波驗收 A′、B′ 兩次實證；OverviewHub 在 PreToolUse 解析所以看得到）。解法：settings.json 登記 PostToolUseFailure 走同一支 dispatcher，失敗的寫入也記（只記現在存在且在這次呼叫後改過的檔）。

## 行動

- 任何「這次改了哪些檔」的記帳都要問：工具呼叫失敗時我還記得到嗎？
- 驗收判分看到「機制沒被問」先查 transcript 那次寫檔是不是 is_error
