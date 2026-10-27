// verify_need_goal_locate.js：need_goal set／update 的 locate 欄（規則 LOCATE_VIA_NEED_GOAL）的 Node 面——lib/need-goal.js validateArgs 只驗形狀、
// lib/mcp.js schema 有選填的 locate 且說明寫「不必另發註解指令」。內容判法在 Python（hooks/verify/verify_locate_via_need_goal.py）。
// 案例：set／update 帶合格 locate → 不拒收；locate 不是陣列、項目缺 part、lines 空或含非字串 → 拒收且訊息含「locate」；add 不驗這欄。
// 跑：node tools/workflow-guardian-mcp/verify/verify_need_goal_locate.js（結尾印 NEED_GOAL_LOCATE_CHECK PASS／FAIL）
let ok = true;
const fail = (m) => { ok = false; console.error("FAIL: " + m); };

try {
  const ng = require("../lib/need-goal");
  const mcp = require("../lib/mcp");
  const good = [{ part: "戰鬥", lines: ["定位｜部位：戰鬥：A.cs", "定位｜根因層：候選 A …；候選 B …；選 A 因為 …", "定位｜前例：無", "定位｜批判：合理，因為 …"] }];
  let e = ng.validateArgs({ action: "set", goal: "G", locate: good });
  if (e.length) fail("set 帶合格 locate 被拒：" + e.join("；"));
  e = ng.validateArgs({ action: "update", items: [{ id: "T1", text: "x" }], locate: good });
  if (e.length) fail("update 帶合格 locate 被拒：" + e.join("；"));
  if (ng.validateArgs({ action: "set", goal: "G" }).length) fail("沒帶 locate 的 set 被拒");
  for (const [label, loc] of [["不是陣列", { part: "戰鬥" }], ["缺 part", [{ lines: ["定位｜部位：x"] }]],
    ["lines 空", [{ part: "戰鬥", lines: [] }]], ["lines 含非字串", [{ part: "戰鬥", lines: ["x", 1] }]], ["項目不是物件", ["x"]]]) {
    e = ng.validateArgs({ action: "set", goal: "G", locate: loc });
    if (!e.length || !e.every((x) => x.includes("locate"))) fail(`${label} 沒拒或訊息沒提 locate：${JSON.stringify(e)}`);
  }
  if (ng.validateArgs({ action: "add", items: [{ text: "t" }], locate: "junk" }).length) fail("add 不該驗 locate 欄");

  const t = mcp.TOOL_DEFINITIONS.find((x) => x.name === "need_goal");
  const p = t.inputSchema.properties.locate;
  if (!p || p.type !== "array" || t.inputSchema.required.includes("locate")) fail("schema 沒有選填的 locate 陣列");
  if (!/不必另發註解指令/.test(p.description)) fail("locate 說明沒寫不必另發註解指令");
  if (!p.items || !p.items.required || p.items.required.join() !== "part,lines") fail("locate 項目沒標 part／lines 必填");
} catch (err) {
  fail((err && err.stack) || String(err));
}
console.log(ok ? "NEED_GOAL_LOCATE_CHECK PASS" : "NEED_GOAL_LOCATE_CHECK FAIL");
process.exit(ok ? 0 : 1);
