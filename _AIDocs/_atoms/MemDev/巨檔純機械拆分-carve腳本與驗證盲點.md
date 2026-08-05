# 巨檔純機械拆分-carve腳本與驗證盲點

- Scope: global
- Author: holylight
- Confidence: [固]
- Trigger: 拆檔, server.js 拆分, 純機械拆分, carve, 模組拆分, split module, depgraph, 循環相依, live MCP 測試汙染, byte-identical 搬移
- Created-at: 2026-07-02
- Related: guardian-dashboard-孤兒佔埠與新碼重啟, feedback-completion-gates

## 知識

- [固] 巨檔拆模組先建「符號→模組→行範圍」表，再寫 carve 腳本逐段 verbatim 抽原檔行拼模組體（不手抄）；加「每非空行覆蓋剛好一次」accounting 不變式當防呆，git diff 才是純搬移。
- [固] 依賴圖 depgraph 只追「跨模組符號」→ 會漏各模組自身的 builtin（path/fs/http/https/exec）import。每模組 header 須另按 body 內 `path.`/`fs.`/`http.`/`exec(`/裸 `https` 用法補齊（log.js 漏 path 即載入即炸，靠 handshake 才抓到）。
- [固] carve 腳本永遠讀「pristine 原檔備份」（如 server.js.orig-bak），別讀工作區已 swap 的輸出——一旦 swap 過，重跑會拿已拆的瘦檔當源、產出全垃圾。
- [固] CRLF 檔要先 split(/\r\n/) 去 \r、拼裝用 \n、落檔再統一轉回 CRLF，否則字串 needle（含大括號+換行）對不上且破壞 byte-identity。
- [固] 雙向相依（mcp↔atom-tools）用「上游對下游 lazy require（handleToolCall 內 require）+ 下游對上游 top-level destructure」化解；載入序保證下游載入時上游已完整。
- [固] live-MCP happy-path 測試會經 funnel 汙染真實 index：atom_edit_meta 會 write_index 把測試 atom 寫進 memory/_atom_index.json + _ATOM_INDEX.md（.md 刪了 index 條目仍殘）。收尾必查 git status、git checkout 還原兩 index；audit jsonl 為 append-only 忠實記錄不改。
- [固] edit_metadata 有「檔須在 ~/.claude 內」安全護欄→隔離 temp 專案測 edit_meta 會被擋（非拆分 bug）；驗 happy-path 需就地建 throwaway atom 於 memory/ 再刪。
- [固] 計畫的 move-map 可能有誤（deleteState 標死碼實則 route 有用需 export；atom-tools 標 import render 實則沒用）；以機械 depgraph 為準覆蓋人工清單，並實測 parity 確認哪些 verify 讀原檔源碼需重指（test_14/17/22→realm.js、test_25→atom-tools.js、promotion_gate→atom-access.js）。

## 行動

- [觀] 拆檔流程：讀全檔→符號/行範圍表→depgraph（補 builtin）→carve 腳本（accounting 不變式）→波次冒煙（葉先、循環用 lazy require）→重指讀源碼的 parity 測試→6 驗證（require 不綁埠/handshake/run_verify/HTTP/埠自癒/live MCP）→查 git status 還原測試汙染→選擇性 staging。
- [觀] 收尾務必 git status 全掃，還原非任務檔（測試汙染的 index）、刪衍生備份（.orig-bak）。
