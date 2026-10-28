// verify_need_goal_schema_budget.js：need_goal 工具定義（description＋inputSchema）的 token 預算閘。
// 為什麼：工具定義每次模型呼叫都重讀，一跑十幾次；定義肥一倍，整個 session 多花幾萬 token。
// 量法：照 tools/list 回的物件算，description 與 JSON.stringify(inputSchema) 分開估，估 token＝1.314×中日韓字數＋0.538×其他字元數。
// 跑：node tools/workflow-guardian-mcp/verify/verify_need_goal_schema_budget.js（結尾印 NEED_GOAL_SCHEMA_BUDGET_CHECK PASS／FAIL；印實際數字）
const BUDGET = 1800;
const CJK = /[　-鿿豈-﫿＀-￯]/g;
const est = (s) => { const c = (s.match(CJK) || []).length; return Math.round(1.314 * c + 0.538 * (s.length - c)); };

let ok = true;
try {
  const { TOOL_DEFINITIONS } = require("../lib/mcp");
  const t = TOOL_DEFINITIONS.find((x) => x.name === "need_goal");
  if (!t) throw new Error("tools/list 沒有 need_goal");
  const desc = est(t.description || "");
  const schema = est(JSON.stringify(t.inputSchema || {}));
  const total = desc + schema;
  console.log(`need_goal 定義估 token：description=${desc} inputSchema=${schema} total=${total} budget=${BUDGET}`);
  if (total > BUDGET) { ok = false; console.error(`FAIL: 超過預算 ${total - BUDGET} tok`); }
} catch (e) {
  ok = false;
  console.error("FAIL: " + ((e && e.stack) || String(e)));
}
console.log(ok ? "NEED_GOAL_SCHEMA_BUDGET_CHECK PASS" : "NEED_GOAL_SCHEMA_BUDGET_CHECK FAIL");
process.exit(ok ? 0 : 1);
