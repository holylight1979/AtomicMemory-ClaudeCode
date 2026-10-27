// verify_need_goal_data_files.js：need_goal set／update 的 data_files（動資料檔宣告隨目標樹一起交）js 面——schema 有這個欄位、
// validateArgs 只驗形狀（陣列、每項物件、path 非空字串、why 是字串），why 空不擋（由 Python 收件時判）。
// 跑：node tools/workflow-guardian-mcp/verify/verify_need_goal_data_files.js（結尾印 NEED_GOAL_DATA_FILES_CHECK PASS／FAIL）
let ok = true;
const fail = (m) => { ok = false; console.error("FAIL: " + m); };
try {
  const { validateArgs } = require("../lib/need-goal");
  const { TOOL_DEFINITIONS } = require("../lib/mcp");
  const def = TOOL_DEFINITIONS.find((t) => t.name === "need_goal");
  const prop = def && def.inputSchema.properties.data_files;
  if (!prop || prop.type !== "array") fail("schema 沒有 data_files 陣列欄位");
  else {
    if (!/need_goal|一起交/.test(prop.description) || !/不必另發/.test(prop.description)) fail("data_files 說明要講一起交、不必另發註解指令：" + prop.description);
    const req = (prop.items && prop.items.required) || [];
    if (!req.includes("path") || !req.includes("why")) fail("items.required 要有 path 與 why：" + JSON.stringify(req));
  }
  const good = [{ path: "settings.json", why: "修多逗號，幣別會變 TWD" }];
  let errs = validateArgs({ action: "set", goal: "G", data_files: good });
  if (errs.length) fail("set 合格的 data_files 被拒：" + errs.join("|"));
  errs = validateArgs({ action: "update", items: [{ id: "T1", status: "doing" }], data_files: good });
  if (errs.length) fail("update 合格的 data_files 被拒：" + errs.join("|"));
  errs = validateArgs({ action: "set", goal: "G", data_files: [{ path: "a.json" }] });
  if (errs.length) fail("why 空只驗形狀、不該在 js 擋：" + errs.join("|"));
  errs = validateArgs({ action: "set", goal: "G", data_files: "settings.json" });
  if (!errs.some((e) => e.includes("data_files 必須是陣列"))) fail("非陣列要拒：" + errs.join("|"));
  errs = validateArgs({ action: "set", goal: "G", data_files: [{ why: "x" }, "s", { path: "a.json", why: 3 }] });
  if (errs.length !== 3 || !errs[0].includes("data_files[0].path 必填") || !errs[1].includes("data_files[1] 必須是物件")
      || !errs[2].includes("data_files[2].why 必須是字串")) fail("形狀錯誤逐項點名：" + errs.join("|"));
  errs = validateArgs({ action: "set", goal: "G" });
  if (errs.length) fail("沒帶 data_files 照舊：" + errs.join("|"));
} catch (e) {
  fail((e && e.stack) || String(e));
}
console.log(ok ? "NEED_GOAL_DATA_FILES_CHECK PASS" : "NEED_GOAL_DATA_FILES_CHECK FAIL");
process.exit(ok ? 0 : 1);
