// need-goal.js：MCP tool `need_goal` 的 Node 面（需求目標樹的五個動作 set／add／update／reconcile／read）。
//
// one-writer：本 handler 只驗參數（動作合法、必填有填、列舉值合法）、回一行 chip；**不讀寫目標檔、不配編號**。
// 套用到 session 的目標樹、配節點編號、記回合與變更紀錄、查證據指標與先後、送回更新後的整棵樹，全由 Python PostToolUse
// （hooks/wg_need_goal.apply_op，帶原始 session_id 與回合）獨佔。契約：_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/need-goal-契約.md
//
// MIRROR: hooks/wg_need_goal.py validate_input（同一組列舉值與規則）。

const ACTIONS = ["set", "add", "update", "reconcile", "read"];
const NODE_STATUS = ["todo", "doing", "done", "partial", "none", "dropped"];
const TERMINAL = ["done", "partial", "none", "dropped"];
const CLARITY = ["clear", "open"];
const ORIGIN = ["user", "inferred", "grown"];
const EVIDENCE_KINDS = ["receipt", "case", "file", "atom"];
const EVIDENCE_LEVELS = ["measured", "read", "inferred"];
const READ_FORMS = ["full", "compact", "handoff"];
const NODE_ID_RE = /^T\d+(\.\d+)*$/;

const str = (v) => (typeof v === "string" ? v.trim() : "");
const given = (v) => v !== undefined && v !== null;

function validateItems(action, items) {
  const errs = [];
  items.forEach((it, i) => {
    const tag = `items[${i}]`;
    if (!it || typeof it !== "object" || Array.isArray(it)) { errs.push(`${tag} 必須是物件`); return; }
    if (action === "add") {
      if (!str(it.text)) errs.push(`${tag}.text 必填`);
      if (given(it.clarity) && !CLARITY.includes(it.clarity)) errs.push(`${tag}.clarity 無效（${it.clarity}），允許：${CLARITY.join("|")}`);
      if (given(it.origin) && !ORIGIN.includes(it.origin)) errs.push(`${tag}.origin 無效（${it.origin}），允許：${ORIGIN.join("|")}`);
      return;
    }
    if (!NODE_ID_RE.test(str(it.id))) errs.push(`${tag}.id 必填，格式 T<數字>(.<數字>)*`);
    if (action === "update") {
      if (!str(it.why)) errs.push(`${tag}.why 必填（這次改動讓它更接近了沒、為什麼）`);
      if (!["text", "status", "clarity"].some((k) => given(it[k]))) errs.push(`${tag} 至少要改 text／status／clarity 其中一項`);
      if (given(it.text) && !str(it.text)) errs.push(`${tag}.text 不能是空的`);
      if (given(it.status) && !NODE_STATUS.includes(it.status)) errs.push(`${tag}.status 無效（${it.status}），允許：${NODE_STATUS.join("|")}`);
      if (given(it.clarity) && !CLARITY.includes(it.clarity)) errs.push(`${tag}.clarity 無效（${it.clarity}），允許：${CLARITY.join("|")}`);
      return;
    }
    if (!TERMINAL.includes(it.status)) errs.push(`${tag}.status 必填且只收終點值：${TERMINAL.join("|")}`);
    if (given(it.evidence) && !Array.isArray(it.evidence)) { errs.push(`${tag}.evidence 必須是陣列`); return; }
    (it.evidence || []).forEach((e, j) => {
      const etag = `${tag}.evidence[${j}]`;
      if (!e || typeof e !== "object" || Array.isArray(e)) { errs.push(`${etag} 必須是物件`); return; }
      if (!EVIDENCE_KINDS.includes(e.kind)) errs.push(`${etag}.kind 無效（${e.kind}），允許：${EVIDENCE_KINDS.join("|")}`);
      if (!EVIDENCE_LEVELS.includes(e.level)) errs.push(`${etag}.level 無效（${e.level}），允許：${EVIDENCE_LEVELS.join("|")}`);
      if (!str(e.ref)) errs.push(`${etag}.ref 必填`);
      if (given(e.covers) && (!Array.isArray(e.covers) || !e.covers.every((c) => NODE_ID_RE.test(str(c))))) {
        errs.push(`${etag}.covers 必須是節點編號陣列`);
      }
    });
  });
  return errs;
}

/** 回錯誤字串陣列（空＝合格）。 */
function validateArgs(args) {
  const a = args || {};
  if (!ACTIONS.includes(a.action)) return [`action 無效（${a.action}），允許：${ACTIONS.join("|")}`];
  if (a.action === "set") {
    const errs = [];
    if (!str(a.goal) && !str(a.import_from)) errs.push("set 要給 goal（一句、使用者的語言、只寫目標不寫手段），或給 import_from（續接單路徑）");
    if (given(a.new_task) && typeof a.new_task !== "boolean") errs.push("new_task 必須是 true／false");
    return errs;
  }
  if (a.action === "read") {
    return given(a.form) && !READ_FORMS.includes(a.form) ? [`form 無效（${a.form}），允許：${READ_FORMS.join("|")}`] : [];
  }
  if (!Array.isArray(a.items) || !a.items.length) return [`${a.action} 要給 items（非空陣列）`];
  const errs = validateItems(a.action, a.items);
  if (a.action === "reconcile" && given(a.turns) && !(Number.isInteger(a.turns) && a.turns >= 0)) errs.push("turns 必須是 ≥0 的整數");
  return errs;
}

async function toolNeedGoal(id, args) {
  const { sendToolResult } = require("./mcp");
  const errs = validateArgs(args);
  if (errs.length) {
    return sendToolResult(id,
      "need_goal 拒收：\n" + errs.map((e) => "  ✗ " + e).join("\n") + "\n修正後重新呼叫。",
      true);
  }
  return sendToolResult(id, `[NeedGoal] ${args.action} 已收到（更新後的整棵樹隨後由 hook 送回）`);
}

module.exports = {
  toolNeedGoal, validateArgs,
  ACTIONS, NODE_STATUS, TERMINAL, CLARITY, ORIGIN, EVIDENCE_KINDS, EVIDENCE_LEVELS, READ_FORMS,
};
