# _AIDocs/_atoms/MemDev/hook與MCP執行期 — 範疇索引

> 階層範疇索引（自動生成，`_` 前綴非 atom）。機制見 [[realm-範疇分區機制-v5]]。

## 本層 atom

| Atom | 說明 |
|------|------|
| cc實測-pretooluse對askuserquestion與exitplanmode會觸發且tool-input完整-deny時posttooluse不觸發posttoolbatch會-中途到的同伴訊息是queued-command不經任何hook | cc實測-PreToolUse對AskUserQuestion與ExitPlanMode會觸發且tool_input完整-deny時PostToolUse不觸發PostToolBatch會-中途到的同伴訊息是queued_command不經任何hook |
| episodic衍生提示讀取池要與寫入端同源-專案session不併根層池-全機單檔狀態要依池分格 | episodic衍生提示讀取池要與寫入端同源-專案session不併根層池-全機單檔狀態要依池分格 |
| hook-py改動立即生效-每次呼叫起新進程-只有mcp-node進程需重啟 | hook-py改動立即生效-每次呼叫起新進程-只有MCP-node進程需重啟 |
| hook-state並行寫入共用tmp檔名-鎖拿不到就直接寫-短內容蓋長檔尾端殘留extra-data-整session後續hook全跳過 | hook-state並行寫入共用tmp檔名-鎖拿不到就直接寫-短內容蓋長檔尾端殘留Extra-data-整session後續hook全跳過 |
| hook-state跨行程三方合併要依欄位業務語意分型-通用合併會破壞去重鍵-事件序號-分回合版本 | hook-state跨行程三方合併要依欄位業務語意分型-通用合併會破壞去重鍵-事件序號-分回合版本 |
| hook-內呼叫外部工具的四個坑-home覆寫下claude-dir指錯-pythonw無stdio-5秒預算-探針要隔離global設定 | hook 內呼叫外部工具的四個坑-HOME覆寫下CLAUDE_DIR指錯-pythonw無stdio-5秒預算-探針要隔離global設定 |
| mcp-js-改動後未重啟-lazy-require-新舊模組混載-tool-回-undefined-類錯誤不是-bug-reload-window-即復原 | MCP js 改動後未重啟-lazy-require 新舊模組混載-tool 回 undefined 類錯誤不是 bug-Reload Window 即復原 |
| mcp的node端程式改了要開新session才載到-同機其他session的mcp程序仍跑舊碼-python端每次spawn立即生效 | MCP的node端程式改了要開新session才載到-同機其他session的MCP程序仍跑舊碼-python端每次spawn立即生效 |
| posttooluse的tool-response不等於模型看到的結果-edit帶整份originalfile-量context浪費要按工具取可見欄位 | PostToolUse的tool_response不等於模型看到的結果-Edit帶整份originalFile-量context浪費要按工具取可見欄位 |
| state待併帳退路的不變量-基準記讀到的原文與指紋-自己的帳沒落盤只能再留帳-併過帳名與結果同次落盤-不轉給別的session | state待併帳退路的不變量-基準記讀到的原文與指紋-自己的帳沒落盤只能再留帳-併過帳名與結果同次落盤-不轉給別的session |
| windows-每支-hook-子程序啟動約-150ms-同事件多支-standalone-hook-先量再併-過-100ms-且等價回放全過才合 | Windows 每支 hook 子程序啟動約 150ms-同事件多支 standalone hook 先量再併-過 100ms 且等價回放全過才合 |
| workflow底下新增state旁檔不可命名成state-星號json-十來處glob會當成一個session-待併帳用pending副檔名並精確比對sid | workflow底下新增state旁檔不可命名成state-星號.json-十來處glob會當成一個session-待併帳用pending副檔名並精確比對sid |
| 子代理的對話紀錄是獨立檔-讀transcript的hook閘要分主檔與子代理檔-使用者原話只認主檔 | 子代理的對話紀錄是獨立檔-讀transcript的hook閘要分主檔與子代理檔-使用者原話只認主檔 |
| 平行hook讀改寫session-state要整段握鎖-寫時重讀再合併只當拿不到鎖的退路-鎖內只有50到80ms | 平行hook讀改寫session-state要整段握鎖-寫時重讀再合併只當拿不到鎖的退路-鎖內只有50到80ms |
| 活躍session的state被fallback覆蓋-讀失敗不等於遺失且working-ttl-30分太短-多sub-agent共用session-id時必撞 | 活躍session的state被fallback覆蓋-讀失敗不等於遺失且working-ttl-30分太短-多sub-agent共用session-id時必撞 |
| 跨session協調-衝突預警機制與cc原生現況 | 跨session協調-衝突預警機制與CC原生現況 |
| 跨層bash閘與sessionstart逾時-fd複製非寫檔-開場提醒無聲消失 | 跨層Bash閘與SessionStart逾時-fd複製非寫檔-開場提醒無聲消失 |
