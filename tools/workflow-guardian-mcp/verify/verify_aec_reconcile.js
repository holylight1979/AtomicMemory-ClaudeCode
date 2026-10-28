// verify_aec_reconcile.js：收尾三段一次交齊的 Node 面（lib/anti-evasion.js aecArgErrors／toolAntiEvasionReport、lib/mcp.js 說明與 schema）。
// 案例：reconcile 欄合格 → 不拒收、chip 寫目標對照已收到；不是物件、items 缺、status 不是終點值 → 拒收且前綴「reconcile：」；
// 守門關閉時不驗這欄（同改動前）；schema 有 reconcile、不列必填；anti_evasion_report 說明寫 reconcile 欄選填、knowledge_harvest_report 說明寫 harvest_items 一次交
// （need_goal 的說明受 1,800 tok 預算限制，不再要求它提這條路）（目標對照不再被要求：規則 GOAL_TREE_SET_ONCE，verify_goal_tree_once.py 禁「目標對照放 reconcile」字樣）。
// 跑：node tools/workflow-guardian-mcp/verify/verify_aec_reconcile.js（自己帶 WG_V6=1；結尾印 AEC_RECONCILE_CHECK PASS／FAIL）
process.env.WG_V6 = "1";
let ok = true;
const fail = (m) => { ok = false; console.error("FAIL: " + m); };

(async () => {
  try {
    const ae = require("../lib/anti-evasion");
    const mcp = require("../lib/mcp");
    const good = { report: "r", reconcile: { items: [{ id: "T1", status: "none", followup: "f" }], turns: 1 } };
    const errsOf = (r, v6 = true) => ae.aecArgErrors({ report: "r", reconcile: r }, v6);
    if (ae.aecArgErrors(good, true).length) fail("合格的 reconcile 被拒：" + ae.aecArgErrors(good, true).join("；"));
    for (const [label, r] of [["不是物件", [1]], ["items 缺", {}], ["status 不是終點值", { items: [{ id: "T1", status: "doing" }] }],
      ["turns 不是整數", { items: [{ id: "T1", status: "none" }], turns: -1 }]]) {
      const e = errsOf(r);
      if (!e.length || !e.every((x) => x.startsWith("reconcile"))) fail(`${label} 沒拒或沒前綴：${JSON.stringify(e)}`);
    }
    if (errsOf([1], false).some((x) => x.includes("reconcile"))) fail("守門關閉時不該驗 reconcile 欄");   // e／f／g 照舊必填那幾條不算

    const t = mcp.TOOL_DEFINITIONS.find((x) => x.name === "anti_evasion_report");
    if (!t.inputSchema.properties.reconcile || t.inputSchema.required.includes("reconcile")) fail("schema 沒有選填的 reconcile");
    if (!/reconcile 欄選填/.test(t.description)) fail("收尾檢核說明沒寫 reconcile 欄選填");
    const hv = mcp.TOOL_DEFINITIONS.find((x) => x.name === "knowledge_harvest_report").description;
    if (!/anti_evasion_report 的 harvest_items 一次交/.test(hv)) fail("收割報告說明沒寫一次交齊");

    const sent = [];
    const orig = mcp.sendToolResult;
    mcp.sendToolResult = (id, text, isError) => { sent.push({ id, text, isError }); };
    await ae.toolAntiEvasionReport(1, { a: "無", b: "無", d: "無", h: "可關閉", i: "無", j_evidence_path: "無", k_followups: "無", ...good });
    await ae.toolAntiEvasionReport(2, { a: "無", b: "無", d: "無", h: "可關閉", i: "無", report: "r", reconcile: {} });
    mcp.sendToolResult = orig;
    if (!(sent[0] && !sent[0].isError && /目標對照已收到/.test(sent[0].text))) fail("chip 沒寫目標對照已收到：" + JSON.stringify(sent[0]));
    if (!(sent[1] && sent[1].isError && /reconcile：/.test(sent[1].text))) fail("壞的 reconcile 沒被拒收：" + JSON.stringify(sent[1]));
  } catch (e) {
    fail((e && e.stack) || String(e));
  }
  console.log(ok ? "AEC_RECONCILE_CHECK PASS" : "AEC_RECONCILE_CHECK FAIL");
  process.exit(ok ? 0 : 1);
})();
