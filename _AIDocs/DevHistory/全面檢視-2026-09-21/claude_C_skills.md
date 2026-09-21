# Claude 審查者 C：社群熱門／特殊設計 skill（2026-09-21）— 摘錄

## 可補強／可新增（依該 agent 排序）
1. **注入 10k 字元上限**（issue #91473，CLI 2.1.207 實測）：hook stdout/additionalContext >10,000 字元 → 存檔只注入 ~2KB 預覽、無警告。→ 量我們每 prompt 實際注入字元數，加上限＋超限告警。**待本機驗證**。
2. **PostToolUse `updatedToolOutput`**（v2.1.121，2026-04-28）可直接替換模型看到的工具輸出 → wg_friction 從「提醒」升級為實截斷（context-mode：全文落檔、頭 60%/尾 40%、315KB→5.4KB；hook 硬強制 98% vs CLAUDE.md 軟引導 60%）。
3. **skill-creator 補行為證據**：superpowers writing-skills「先不裝 skill 跑 baseline → 藉口表 → 紅旗清單」；官方「先寫 3 個 eval」；description 只寫何時用；接 `claude plugin eval`（v2.1.269）／`/skill-doctor`。description+when_to_use 合計 1,536 字元截斷。
4. **atom 信心雙向動態**：ECC instincts（confidence 0.3–0.9；使用者拒絕／反證／長期未出現 → 降；同 instinct 2+ 專案且 ≥0.8 → 升 global；注入數上限參數化）；claude-evolve（EMA 30/70、15 session 未用標「死」不刪、受管圍欄區塊）。我們有 Wilson 降級候選，但無「反證」「跨專案自動升 global」。
5. **PreCompact flush ＋ 進行中計畫每回合重誦**（planning-with-files 27k★：SessionStart 還原、UPS 重注入計畫、PreCompact flush、Stop 檢查 phase；恢復 5.0 回合 vs 13.3）。我們有 PreCompact hook，但做什麼待驗。
次選：週健檢加「黃金任務基準線」（5–10 任務加權 rubric，`claude -p` 週跑，掉 >0.3 開 issue）＋「舊糾正規則是否已被新模型內建」修剪審查（Boris Cherny：新模型砍 80% 系統提示）；gstack 決策帳本（拍過板的取捨不重問）、`/freeze <dir>`（PreToolUse 路徑白名單）、連修 3 次失敗停手質疑架構；**SubagentStop 驗子代理回報**（hook 可回 additionalContext 延長子代理；「子代理回報成功實際失敗」是 CC Safety Lab 結構性叢集）；compound-engineering「能從 code 讀出的不寫」加進 atom_write 守則；beads 舊事件語意壓縮 → episodic；hook 三執行體 command／prompt／agent（60s、≤50 輪）。

## 已有
brainstorming 一次一題、handoff／fan-out、learnings 注入、Codex 裁判、動手前預告閘（cc-sessions DAIC 的輕量版）、loop 本體。

## 雞肋／棄用
CLAUDE.md 肥大、always-on 輸出風格、MCP 堆疊（5 server ≈55k tok）、每子任務 subagent review 迴圈（superpowers v5 自己拆掉）、全寫入鎖 DAIC、hook `decision/reason` 舊欄位、靠 CLAUDE.md 講「必須」、舊糾正規則不修剪、召回記憶當政策、本機服務無認證（claude-mem 37777 零認證）、FRAME 33 指令六階段。

## 待本機驗
是否已有 PreCompact flush、孤兒 linter；每 prompt 注入實際字元數是否曾 >10k。
