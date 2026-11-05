# feedback-撤回版控改動要從現行檔做最小修改-不要整檔退回上一版-先分清共用值與個人值

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 退版, 撤回, settings.json, 個人偏好, 還原上一版, claudeMdExcludes, 共用設定
- Created-at: 2026-11-05
- Source: session:d164c54c#73e15770 2026-11-05
- Quote: 「收割後，可以關session囉?」

## 知識

- [臨] 使用者指出 settings.json 不該帶個人偏好，我直接整檔退回上一版，蓋掉本機設定，還誤報設定仍在；上一版也還留著帳號名。使用者原話：「要做的不應該是直接退版、而是把有我的名字的那邊去掉」。
- [臨] 根層 settings.json 共用：帳號名改用通用 glob（目前排除家目錄 AGENTS.md 用 **/Users/*/AGENTS.md），模型與 effort 不寫，走原廠預設。/model 會改寫這個檔，上GIT 前要看 diff 剔掉個人值。

## 行動

- 使用者要撤掉某項改動：從現行檔改掉那一項，先 diff 確認其他內容不受影響
- 上GIT 碰到 settings.json：逐行看 diff，個人值不進 commit
