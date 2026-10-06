# 身份與職能自動來自AD-帳號即get-current-user-職能由whoami群組對映-查不到就空不預設programmer-裁決名單review-deciders

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 身份, AD 帳號, 職能, roles, role.md, wg_roles, init-roles, 管理職, is_management, review.deciders, ad_group_map, whoami /groups, 待審裁決, pending review, 看不到 role atom
- Created-at: 2026-10-01
- Source: session:d892b7c9#160556c3 2026-10-01
- Quote: 「你會繼續推進到全部完工吧?」

## 知識

- [臨] 身份＝公司 AD 帳號，`wg_roles.get_current_user()`（`CLAUDE_USER` → OS 帳號）回的就是去網域的 AD 名（`uj\\holylight`→`holylight`）；取不到回 `unknown`，`unknown` 不讀任何 personal。不做 SSO／RBAC／簽章／成員表（2026-10-01 辩論會議裁決）。
- [臨] 職能三層解析 `load_user_role`：① `personal/<u>/role.md`（專案 → 根層）的 `- Role:`；② AD 群組 `whoami /groups /fo csv`（OEM 碼頁解碼），群組名 `UJ\\<專案代碼>_<序號>_<職能名>` 依 config `roles.ad_group_map` 子字串對映（核心程式／伺服器程式→programmer、美術→art…），專案 MEMORY.md `> Project-Code: PJA146` 可限定；③ 都沒有 → `[]`（只看 shared／org／global，**不預設 programmer**，否則「不知道」被當成「是程式」擴大 role atom 可見範圍）。
- [臨] 「管理職」概念已拿掉：`is_management()` 讀 `workflow/config.json review.deciders`，空＝人人可裁決待審草稿（＝實戰現況：TSLG 成員自己 approve/reject），`[Pending Review]` 全員顯示；要限制填 AD 帳號清單。`_roles.md` 白名單與 `--promote-mgmt` 已刪。

## 行動

- 看不到 roles/<r>/ 的 atom → `python ~/.claude/tools/init-roles.py --project-cwd <專案> --status` 看三層各解析到什麼
- 例外覆寫職能：`init-roles.py --project-cwd <專案> --me art`；删掉 role.md 即回到 AD 解析
- 新職能名出現在 AD 群組→ 加進 config roles.ad_group_map，不寫程式
