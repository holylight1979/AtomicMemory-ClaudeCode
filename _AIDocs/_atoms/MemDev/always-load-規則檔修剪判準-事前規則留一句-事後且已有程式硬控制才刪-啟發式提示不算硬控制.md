# always-load 規則檔修剪判準-事前規則留一句-事後且已有程式硬控制才刪-啟發式提示不算硬控制

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: core.md 太肥, 修剪規則, always-load, CLAUDE.md 瘦身, IDENTITY.md 精簡, rules/core.md, 重複規則, hook 已強制, 事前規則, 事後諸葛
- Created-at: 2026-09-01

## 知識

- [臨] 使用者定的 always-load 規則檔（rules/core.md / IDENTITY.md / templates）修剪判準：① **事前型**規則（不先知道就會浪費一次被閘擋的呼叫，如根層閘、新 atom [臨] 起跳、PreActionNotice 預告）→ 留一句；② **事後型 且 已有程式硬控制**（Stop 閘 block、atom_write 拒寫、atom_io 拒收）→ 刪；③ 只有**啟發式提示**（wg_parallel / wg_research 命中才注入）不算硬控制 → 留一句；④ 無任何程式閘的（走 atom_write 禁直接 Edit atom、Native-first、可觀測性）→ 完整留。無條件每 session 注入的提醒（SessionStart `[查閱知識庫]`）視為等價替代可刪。技術根據：hook 是 JIT/事後注入、always-load 是事前常駐。修削時順手抓「與系統行為矛盾」的條目（如『記住』→[固] vs atom_io 拒收）。IDENTITY.md 是 gitignored，改它必同步 `templates/IDENTITY.template.md`（SessionStart 災難還原來源）。

## 行動

- 修剪 always-load 檔前先 grep hooks 確認每條是 block/拒寫（硬）還是命中才提示（軟），別靠印象
- 改 IDENTITY.md 必同步 templates/IDENTITY.template.md
