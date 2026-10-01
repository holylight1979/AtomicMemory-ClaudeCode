// harvest.js — MCP tool `knowledge_harvest_report` 的 Node 面（階段完工知識收割回報）。
//
// one-writer spine：本 handler 只驗 schema、統計、回一行 chip；**不碰 state、不寫檔**。
// items ↔ 本 session atom receipt 的逐項核對、state.knowledge_harvest 分區與 ledger 寫入，
// 全由 Python PostToolUse（帶原始 session_id + turn_seq）獨佔。
//
// sendToolResult 來自 mcp.js（mcp.handleToolCall lazy-require 本檔，handler 內 lazy-require 即可）。

const SOURCES = ["correction", "mechanism", "external_fact", "decision", "atom_fix", "atom_retire"];
const ACTIONS = ["created", "appended", "replaced", "superseded", "retired", "skip"];
const WRITE_ACTIONS = new Set(["created", "appended", "replaced", "superseded"]);

/** 逐 item 驗必填；回錯誤字串陣列（空＝合格）。 */
function validateItems(items) {
  const errs = [];
  items.forEach((it, i) => {
    const tag = `items[${i}]`;
    if (!it || typeof it !== "object") { errs.push(`${tag}: 必須是物件`); return; }
    if (!SOURCES.includes(it.source)) errs.push(`${tag}.source 無效（${it.source}），允許：${SOURCES.join("|")}`);
    if (!ACTIONS.includes(it.action)) errs.push(`${tag}.action 無效（${it.action}），允許：${ACTIONS.join("|")}`);
    if (!String(it.summary || "").trim()) errs.push(`${tag}.summary 必填`);
    if (it.action === "skip") {
      if (!String(it.reason || "").trim()) errs.push(`${tag}: action=skip 必填 reason（一句為何不寫）`);
      return;
    }
    if (!String(it.atom || "").trim()) errs.push(`${tag}: action=${it.action} 必填 atom（atom 名）`);
    if (!String(it.path || "").trim()) {
      errs.push(`${tag}: action=${it.action} 必填 path（atom_write/atom_retire receipt 回的絕對路徑）`);
    }
  });
  return errs;
}

function harvestChip(items) {
  if (!items.length) return "[Harvest] 本場無新知識";
  let written = 0, retired = 0, skipped = 0;
  for (const it of items) {
    if (WRITE_ACTIONS.has(it.action)) written++;
    else if (it.action === "retired") retired++;
    else skipped++;
  }
  return `[Harvest] ${written} 寫入／${retired} 退役／${skipped} 不寫`;
}

async function toolKnowledgeHarvestReport(id, args) {
  const { sendToolResult } = require("./mcp");
  const items = args && args.items;
  if (!Array.isArray(items)) {
    return sendToolResult(id, "knowledge_harvest_report: items 必須是陣列（本場無值得寫的也要給 items=[]）", true);
  }
  const errs = validateItems(items);
  if (errs.length) {
    return sendToolResult(id,
      "knowledge_harvest_report 拒收：\n" + errs.map((e) => "  ✗ " + e).join("\n") +
      "\n修正後重新呼叫（action≠skip 的 path 必須是 receipt 的絕對路徑；skip 必附 reason）。",
      true);
  }
  return sendToolResult(id, harvestChip(items));
}

module.exports = { toolKnowledgeHarvestReport, validateItems, harvestChip, SOURCES, ACTIONS };
