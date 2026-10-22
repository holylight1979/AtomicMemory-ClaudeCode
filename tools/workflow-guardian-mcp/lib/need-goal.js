// need-goal.js：MCP tool `need_goal` 的 Node 面（需求目標樹的五個動作 set／add／update／reconcile／read，
// 加上驗證範圍的宣告 verify_scope：該測哪些由 LLM 判斷，交給 Python PostToolUse 的 wg_verify_scope 收件）。
//
// one-writer：本 handler 只驗參數（動作合法、必填有填、列舉值合法）、回一行 chip；**不讀寫目標檔、不配編號**。
// 套用到 session 的目標樹、配節點編號、記回合與變更紀錄、查證據指標與先後、送回更新後的整棵樹，全由 Python PostToolUse
// （hooks/wg_need_goal.apply_op，帶原始 session_id 與回合）獨佔。契約：_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/need-goal-契約.md
//
// MIRROR: hooks/wg_need_goal.py validate_input（同一組列舉值與規則）。

const ACTIONS = ["set", "add", "update", "reconcile", "read", "verify_scope"];
const REVIEW_VERDICTS = ["missed", "unrelated"];
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
      if (given(it.quote) && typeof it.quote !== "string") errs.push(`${tag}.quote 必須是字串（標 origin=user 時引用使用者原話的字面子句）`);
      return;
    }
    if (!NODE_ID_RE.test(str(it.id))) errs.push(`${tag}.id 必填，格式 T<數字>(.<數字>)*`);
    if (action === "update") {
      if (!str(it.why)) errs.push(`${tag}.why 必填（這次改動讓它更接近了沒、為什麼）`);
      if (!["text", "status", "clarity", "origin"].some((k) => given(it[k]))) errs.push(`${tag} 至少要改 text／status／clarity／origin 其中一項`);
      if (given(it.origin) && !ORIGIN.includes(it.origin)) errs.push(`${tag}.origin 無效（${it.origin}），允許：${ORIGIN.join("|")}`);
      if (given(it.quote) && typeof it.quote !== "string") errs.push(`${tag}.quote 必須是字串（標 origin=user 時引用使用者原話的字面子句）`);
      if (given(it.text) && !str(it.text)) errs.push(`${tag}.text 不能是空的`);
      if (given(it.status) && !NODE_STATUS.includes(it.status)) errs.push(`${tag}.status 無效（${it.status}），允許：${NODE_STATUS.join("|")}`);
      if (given(it.clarity) && !CLARITY.includes(it.clarity)) errs.push(`${tag}.clarity 無效（${it.clarity}），允許：${CLARITY.join("|")}`);
      return;
    }
    if (!TERMINAL.includes(it.status)) errs.push(`${tag}.status 必填且只收終點值：${TERMINAL.join("|")}`);
    if (given(it.same_class) && typeof it.same_class !== "string") errs.push(`${tag}.same_class 必須是字串（同類別處：找到的位置，或為什麼沒有）`);
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

/** verify_scope：items 每項 {target, why} 非空、inputs／depends／case_for（選填）是字串陣列（case_for 要非空）；reviews（選填）每筆
 * {leak, verdict∈missed|unrelated}；no_case（選填）每筆 {path, reason} 非空。內容由 Python 收件時照規則判。 */
function validateVerifyScope(a) {
  if (!Array.isArray(a.items) || !a.items.length) return ["verify_scope 要給 items（非空陣列，每項 {target, why}）"];
  const errs = [];
  a.items.forEach((it, i) => {
    if (!it || typeof it !== "object" || Array.isArray(it)) { errs.push(`items[${i}] 必須是物件`); return; }
    if (!str(it.target)) errs.push(`items[${i}].target 必填（測試檔、測試節點、資料夾或指令）`);
    if (!str(it.why)) errs.push(`items[${i}].why 必填（為什麼和這次改動有關、會受什麼影響）`);
    if (given(it.inputs) && (!Array.isArray(it.inputs) || !it.inputs.every((x) => str(x)))) {
      errs.push(`items[${i}].inputs 必須是非空字串陣列（這一項還讀的檔或資料夾）`);
    }
    if (given(it.depends) && (!Array.isArray(it.depends) || !it.depends.every((x) => str(x)))) {
      errs.push(`items[${i}].depends 必須是字串陣列（這一項用到的程式檔或資料夾）`);
    }
    if (given(it.case_for) && (!Array.isArray(it.case_for) || !it.case_for.length || !it.case_for.every((x) => str(x)))) {
      errs.push(`items[${i}].case_for 必須是非空字串陣列（這支案例驗的程式檔）`);
    }
  });
  if (given(a.no_case) && !Array.isArray(a.no_case)) errs.push("no_case 必須是陣列（[{path, reason}]：不需要新案例的程式檔與理由）");
  (Array.isArray(a.no_case) ? a.no_case : []).forEach((n, j) => {
    if (!n || typeof n !== "object" || Array.isArray(n) || !str(n.path) || !str(n.reason)) {
      errs.push(`no_case[${j}] 要有 path（改過的程式檔）與 reason（為什麼不需要新案例）`);
    }
  });
  if (given(a.reviews) && !Array.isArray(a.reviews)) return [...errs, "reviews 必須是陣列"];
  (a.reviews || []).forEach((r, j) => {
    if (!r || typeof r !== "object" || Array.isArray(r)) { errs.push(`reviews[${j}] 必須是物件`); return; }
    if (!str(r.leak)) errs.push(`reviews[${j}].leak 必填（範圍漏判編號 L…）`);
    if (!REVIEW_VERDICTS.includes(r.verdict)) errs.push(`reviews[${j}].verdict 無效（${r.verdict}），允許：${REVIEW_VERDICTS.join("|")}`);
  });
  return errs;
}

/** 回錯誤字串陣列（空＝合格）。 */
function validateArgs(args) {
  const a = args || {};
  if (!ACTIONS.includes(a.action)) return [`action 無效（${a.action}），允許：${ACTIONS.join("|")}`];
  if (a.action === "verify_scope") return validateVerifyScope(a);
  if (a.action === "set") {
    const errs = [];
    if (!str(a.goal) && !str(a.import_from)) errs.push("set 要給 goal（一句、使用者的語言、只寫目標不寫手段），或給 import_from（續接單路徑）");
    if (given(a.new_task) && typeof a.new_task !== "boolean") errs.push("new_task 必須是 true／false");
    if (given(a.items) && !Array.isArray(a.items)) errs.push("set 的 items 必須是陣列（子目標 [{text, clarity?, origin?, quote?}]，同 add）");
    else if (Array.isArray(a.items) && a.items.length) errs.push(...validateItems("add", a.items));
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
  ACTIONS, NODE_STATUS, TERMINAL, CLARITY, ORIGIN, EVIDENCE_KINDS, EVIDENCE_LEVELS, READ_FORMS, REVIEW_VERDICTS,
};
