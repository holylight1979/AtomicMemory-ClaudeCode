# atom-table-support

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: atom_write, 表格, table, markdown 表格, code fence, 程式碼 fence, knowledge block, block 渲染, dogfood
- Created-at: 2026-05-29
- Related: workflow-rules, feedback-tooling-reliability, feedback-memory-system-doc-sync

## 知識

- [臨] `atom_write` 的 `knowledge` 陣列支援 block 元素：單一元素去左空白後以豎線（markdown 表格）或三反引號（程式碼 fence）開頭者，整段原樣輸出（不加 `- ` bullet、前後自動補空行，GFM 渲染需要）；其餘元素維持「首行加 `- `」原行為。用法：把表格/程式碼當『獨立 knowledge 元素』傳入，引言句放前一個元素。

| 傳入方式 | 寫法 | 渲染結果 |
|---|---|---|
| 一般條目 | 普通字串元素 | 自動補 `- ` bullet |
| 表格 | 單一元素、以豎線符號開頭、內含換行 | 整段原樣輸出、無 bullet、前後補空行 |
| 程式碼 | 單一元素、以三反引號開頭 | fence 原樣輸出 |
| 引言＋區塊 | 引言句與區塊各自一個元素 | 引言成 bullet、區塊成 block |

- Python 呼叫示意（fence 本身也是 block 元素，一併 dogfood）：

```python
atom_write(knowledge=[
    "引言句（一般元素 → 自動補 bullet）",
    TABLE_STRING,   # 首字元為豎線、內含換行 → 整段 block 原樣輸出
])
```

- [臨] 雙路徑單一邏輯：`lib/atom_spec.py:render_knowledge_lines`（hooks/tools 經 atom_io）與 `tools/workflow-guardian-mcp/server.js:renderKnowledgeLines`（MCP 經 buildAtomContent/append）須 byte-identical。改 server.js 後須重啟 MCP server 進程才生效（本 atom 即重啟後的端到端 dogfood）。守門：`lib/verify/verify_atom_io_equivalence.py` test_11/12/13。詳見 SPEC_ATOM_V5 §11。

## 行動

- 表格/程式碼當獨立 knowledge 元素傳入，引言句放前一個元素
- 改 server.js renderKnowledgeLines 後重啟 MCP server 才生效；py funnel 下次呼叫即生效
- 下游零衝擊：conflict-detector 只抽 `- ` 行、注入剝離整段保留、逐行 [固] parse 不匹配表格列
