# identity-變動需同步更新-identity-template-且所有文件

- Scope: global
- Audience: programmer
- Author: holylight
- Confidence: [臨]
- Trigger: identity, identity.template, LF格式, 統一LF
- Created-at: 2026-09-03
- Source: commit:d0358a2 2026-09-03（原對話已逾保留期）

## 知識

- [臨] Identity 變動需同步更新 identity.template，且所有文件必須使用 LF 格式
- <!-- src: 0b44131f-9c5f-44e6-9e7b-2b7e90aaa91e-5 -->
- [觀] 實例 `~/.claude/IDENTITY.md` 被 gitignore 刻意排除（私人實例），**有版控的是 `templates/IDENTITY.template.md`**；SessionStart 實例損毀時從模板還原。改了實例不同步模板，別台機器跟還原都拿不到；使用者已提醒 N 次。「git add 被拒 ignored」不是「不用上版」，是「上錯檔」的訊號。

## 行動

- （依知識內容判斷）
