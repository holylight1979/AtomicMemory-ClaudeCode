// need-goal.js：MCP tool `need_goal` 的 Node 面（需求目標樹的五個動作 set／add／update／reconcile／read）。
//
// one-writer：本 handler 只驗參數（動作合法、必填有填、列舉值合法）、回一行 chip；**不讀寫目標檔、不配編號**。
// 套用到 session 的目標樹、配節點編號、記回合與變更紀錄、查證據指標與先後、送回更新後的整棵樹，全由 Python PostToolUse
// （hooks/wg_need_goal.apply_op，帶原始 session_id 與回合）獨佔；判法以 hooks/wg_need_goal.apply_op 為準。
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
      if (given(it.quote) && typeof it.quote !== "string") errs.push(`${tag}.quote 必須是字串（標 origin=user 時引用使用者原話的字面子句）`);
      return;
    }
    if (!NODE_ID_RE.test(str(it.id))) errs.push(`${tag}.id 必填，格式 T<數字>(.<數字>)*`);
    if (action === "update") {
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
      if (given(e.unaffected) && typeof e.unaffected !== "string") {
        errs.push(`${etag}.unaffected 必須是字串（為什麼第二意見之後改的檔不影響這筆收據）`);
      }
    });
  });
  return errs;
}

/** set／update 選填 locate=[{part, lines}]（規則 LOCATE_VIA_NEED_GOAL）：只驗形狀，內容由 Python wg_overview.locate_from_goal 判。 */
function validateLocate(a) {
  if (!given(a.locate)) return [];
  if (!Array.isArray(a.locate)) return ["locate 必須是陣列（[{part, lines}]：部位名或檔路徑、定位四行）"];
  const errs = [];
  a.locate.forEach((it, i) => {
    if (!it || typeof it !== "object" || Array.isArray(it)) { errs.push(`locate[${i}] 必須是物件`); return; }
    if (!str(it.part)) errs.push(`locate[${i}].part 必填（部位名或該部位的檔路徑）`);
    if (!Array.isArray(it.lines) || !it.lines.length || !it.lines.every((x) => str(x))) {
      errs.push(`locate[${i}].lines 必須是非空字串陣列（定位｜部位／根因層／前例／批判各一行）`);
    }
  });
  return errs;
}

/** data_files（set／update 選填）：改使用者資料檔前的宣告隨目標樹一起交，[{path, why}]；只驗形狀（陣列、每項物件、path 非空字串、
 * why 是字串），why 空不空、路徑對不對由 Python 收件時判（hooks/wg_data_file.declare_via_need_goal）。 */
function validateDataFiles(a) {
  if (!given(a.data_files)) return [];
  if (!Array.isArray(a.data_files)) return ["data_files 必須是陣列（[{path, why}]：要動的使用者資料檔與為什麼）"];
  const errs = [];
  a.data_files.forEach((d, i) => {
    if (!d || typeof d !== "object" || Array.isArray(d)) { errs.push(`data_files[${i}] 必須是物件 {path, why}`); return; }
    if (!str(d.path)) errs.push(`data_files[${i}].path 必填（要動的資料檔路徑）`);
    if (given(d.why) && typeof d.why !== "string") errs.push(`data_files[${i}].why 必須是字串（為什麼要動、改完使用者會看到什麼不同）`);
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
    if (given(a.kind) && !["code", "knowledge"].includes(a.kind)) errs.push(`kind 無效（${a.kind}），允許：code|knowledge`);
    if (given(a.items) && !Array.isArray(a.items)) errs.push("set 的 items 必須是陣列（子目標 [{text, clarity?, origin?, quote?}]，同 add）");
    else if (Array.isArray(a.items) && a.items.length) errs.push(...validateItems("add", a.items));
    errs.push(...validateLocate(a));
    errs.push(...validateDataFiles(a));
    return errs;
  }
  if (a.action === "read") {
    return given(a.form) && !READ_FORMS.includes(a.form) ? [`form 無效（${a.form}），允許：${READ_FORMS.join("|")}`] : [];
  }
  const onlyDecl = a.action === "update" && !(Array.isArray(a.items) && a.items.length) && (given(a.locate) || given(a.data_files));   // 只交定位／資料檔宣告，不改節點
  if (!onlyDecl && (!Array.isArray(a.items) || !a.items.length)) return [`${a.action} 要給 items（非空陣列）`];
  const errs = validateItems(a.action, a.items || []);
  if (a.action === "update") { errs.push(...validateLocate(a)); errs.push(...validateDataFiles(a)); }
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
  toolNeedGoal, validateArgs, validateLocate,
  ACTIONS, NODE_STATUS, TERMINAL, CLARITY, ORIGIN, EVIDENCE_KINDS, EVIDENCE_LEVELS, READ_FORMS,
};
