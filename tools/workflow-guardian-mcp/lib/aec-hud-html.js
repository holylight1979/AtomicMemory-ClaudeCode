// aec-hud-html.js — Anti-Evasion HUD 頁模板。匯出 render()->string（鏡像 dashboard-html.js）。
//
// dark HUD 單頁：即時最新收尾檢核卡 + 底部近 N 回合 severity 歷史格。
// 卡片分三類給人看：① 你這次要的事（每件掛使用者原話）② 碰到你的長期原則、方向 ③ AI 自己做主的；
// 上面一行「份量」把三類字數攤開比（目標那類一句帶過、自己做主那類一大串 → 標黃）；技術細節與系統帳收進附錄。
// 第一類上方摺疊區列你這回合打的原話（Python 從紀錄取）；每件「你說」旁標核對記號（said_check，對不到標警示色）。
// 沒有三類的舊報告照舊欄位放進同一個框。
// 傳輸＝輪詢（非 SSE）：setInterval 1.5s fetch /api/aec/reports（增量 ?since=）→ 渲染；
// 格子 click → fetch /api/aec/report/<sid>/<turn> 展開；每 10s fetch /api/aec/beat 送心跳。
//
// 視覺（dataviz skill 驗證）：severity 為 status palette，CVD ΔE 44.6（>>12）+ 皆 ≥3:1；
// routine=靜色灰 / notable=琥珀 / real-evasion=紅，且每格附文字標籤（secondary encoding，
// 非 color-alone）。surface 用 github-dark（與 dashboard-html.js 同族）。
//
// ★內層 <script> 為瀏覽器端 JS（非模組 state）：整塊 verbatim、**勿 hoist**（比照 _MAP C7）；
// 為免 nested-backtick，瀏覽器端一律字串串接、不用 template literal。

const { AI_DECIDED_KINDS } = require("./anti-evasion");   // 「AI 自己做主」四種的白話標籤（與 schema、拒收檢查同一份）

function render() {
  return `<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>收尾檢核</title>
<style>
  :root {
    --plane: #0d1117; --surface-1: #161b22; --surface-2: #1c222b;
    --border: #30363d; --ink: #e6edf3; --ink-2: #c9d1d9; --muted: #8b949e;
    --sev-routine: #8b949e; --sev-notable: #fab219; --sev-real: #d03b3b;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: var(--plane); color: var(--ink-2); padding: 18px; }
  h1 { color: var(--ink); font-size: 1.15em; letter-spacing: .3px; }
  .sub { color: var(--muted); font-size: .78em; margin-top: 2px; }
  .top { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 14px; }
  .poll { font-size: .74em; color: var(--muted); }
  .poll .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #3fb950; margin-right: 5px; vertical-align: middle; }
  .card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 16px; }
  .card.sev-notable { border-left: 3px solid var(--sev-notable); }
  .card.sev-real { border-left: 3px solid var(--sev-real); }
  .card-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
  .badge { font-size: .72em; font-weight: 700; padding: 3px 9px; border-radius: 20px; letter-spacing: .3px; }
  .badge.routine { background: #8b949e26; color: var(--sev-routine); border: 1px solid #8b949e55; }
  .badge.notable { background: #fab21926; color: var(--sev-notable); border: 1px solid #fab21966; }
  .badge.real { background: #d03b3b26; color: #ff9a9a; border: 1px solid #d03b3b88; }
  .meta { font-size: .76em; color: var(--muted); font-family: ui-monospace, monospace; }
  .who { font-size: .82em; color: var(--ink); font-weight: 600; font-family: ui-monospace, monospace; }
  .banner { display: none; background: #d03b3b1f; border: 1px solid #d03b3b88; color: #ffb4b4; padding: 8px 12px; border-radius: 8px; font-size: .82em; margin-bottom: 14px; }
  .banner.show { display: block; }
  .sec { border-top: 1px solid var(--border); padding: 9px 0; }
  .sec:first-of-type { border-top: none; }
  .sec-h { font-size: .78em; font-weight: 600; color: var(--ink); margin-bottom: 3px; }
  .sec-h .k { color: var(--muted); font-weight: 400; }
  .sec-body { font-size: .82em; white-space: pre-wrap; color: var(--ink-2); font-family: ui-monospace, monospace; line-height: 1.45; }
  .sec-body.blank { color: #545d68; font-family: inherit; font-style: italic; }
  .grid-wrap { margin-top: 4px; }
  .grid-h { font-size: .8em; color: var(--ink); margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
  .legend { font-size: .72em; color: var(--muted); display: flex; gap: 12px; }
  .legend i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
  .grid { display: flex; flex-wrap: wrap; gap: 5px; }
  .cell { width: 26px; height: 26px; border-radius: 5px; border: 1px solid var(--border); cursor: pointer; position: relative; display: flex; align-items: center; justify-content: center; font-size: .6em; color: #0d1117cc; font-weight: 700; transition: transform .08s; }
  .cell:hover { transform: scale(1.12); outline: 1px solid var(--ink-2); }
  .cell.routine { background: var(--sev-routine); }
  .cell.notable { background: var(--sev-notable); }
  .cell.real { background: var(--sev-real); box-shadow: 0 0 0 2px #d03b3b55; }
  .cell.active { outline: 2px solid var(--ink); }
  .empty { color: var(--muted); font-size: .82em; padding: 24px 0; text-align: center; }
  .dec-list { font-family: inherit; }
  .dec-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 4px 0; border-top: 1px dashed #ffffff0f; }
  .dec-row:first-child { border-top: none; }
  .dec-item { flex: 1; min-width: 0; word-break: break-all; }
  .dec-row.dec-done .dec-item { color: #545d68; }
  .dec-btns { flex-shrink: 0; display: flex; gap: 6px; align-items: center; }
  .aec-dec-btn { font-size: .72em; padding: 3px 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-2); color: var(--ink-2); cursor: pointer; }
  .aec-dec-btn:hover { border-color: var(--ink-2); }
  .aec-dec-btn.danger { color: #ff9a9a; border-color: #d03b3b66; }
  .aec-dec-btn.danger:hover { background: #d03b3b26; border-color: #d03b3b; }
  .dec-status { font-size: .74em; color: var(--muted); }
  .tabs { display: flex; gap: 6px; margin-bottom: 14px; border-bottom: 1px solid var(--border); }
  .tab { font-size: .82em; padding: 6px 14px; border: 1px solid transparent; border-bottom: none; border-radius: 8px 8px 0 0; background: none; color: var(--muted); cursor: pointer; margin-bottom: -1px; }
  .tab.active { background: var(--surface-1); border-color: var(--border); color: var(--ink); }
  .grp { border-top: 1px solid var(--border); padding: 9px 0; }
  .grp:first-child { border-top: none; }
  .lamp { font-weight: 700; font-size: .98em; }
  .lamp.ok { color: #3fb950; } .lamp.todo { color: var(--sev-notable); } .lamp.real { color: #ff9a9a; }
  .item { margin: 5px 0 7px; }
  .item-h { font-size: .76em; color: var(--muted); margin-bottom: 2px; }
  .detail { margin-top: 10px; border-top: 1px solid var(--border); padding-top: 6px; }
  .detail summary { font-size: .76em; color: var(--muted); cursor: pointer; }
  .grp-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; font-size: .8em; color: var(--ink); }
  .grp-head .k { color: var(--muted); }
  .grp details { margin-top: 4px; }
  .grp summary { font-size: .74em; color: var(--muted); cursor: pointer; }
  .all-sum { font-size: .78em; color: var(--muted); display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 6px; }
  .lead { font-size: .88em; color: var(--ink); white-space: pre-wrap; line-height: 1.5; margin-bottom: 6px; }
  .weigh { font-size: .8em; color: var(--muted); }
  .weigh b { color: var(--ink); font-weight: 600; }
  .weigh.warn, .weigh.warn b { color: var(--sev-notable); }
  .gi { margin: 6px 0 10px; padding-left: 10px; border-left: 2px solid #388bfd66; }
  .gi.pi { border-left-color: #a371f766; }
  .gi.ai { border-left-color: #8b949e66; }
  .said { font-size: .86em; color: var(--ink); margin-bottom: 3px; line-height: 1.5; white-space: pre-wrap; }
  .said.none { color: #ff9a9a; }
  .sc { font-size: .84em; margin-left: 6px; }
  .sc.ok { color: #3fb950; }
  .sc.warn { color: #ff9a9a; font-weight: 600; }
  .sc.src { color: var(--muted); border: 1px solid var(--border); border-radius: 10px; padding: 0 7px; }
  .sc.gray { color: #545d68; }
  .usaid summary { font-size: .8em; color: var(--ink); cursor: pointer; }
  .usaid-msg { font-family: inherit; margin: 6px 0 2px; padding-left: 10px; border-left: 2px solid #3fb95066; }
  .kv { font-size: .84em; display: flex; gap: 8px; line-height: 1.55; }
  .kv .kl { flex-shrink: 0; width: 5em; color: var(--muted); }
  .kv .kvv { flex: 1; min-width: 0; white-space: pre-wrap; word-break: break-word; }
  .kv.nd .kvv { color: var(--sev-notable); }
  .tag { font-size: .8em; padding: 1px 7px; border-radius: 10px; border: 1px solid var(--border); color: var(--muted); margin-right: 6px; }
  .tech { margin-top: 2px; }
  .tech summary { font-size: .72em; color: var(--muted); cursor: pointer; }
  .tech .sec-body { font-size: .76em; }
</style>
</head>
<body>
  <div class="top">
    <div>
      <h1>收尾檢核</h1>
      <div class="sub">每輪收尾的白話報告；底下格子是最近幾輪，點一下看那一輪</div>
    </div>
    <div class="poll"><span class="dot"></span><span id="poll-txt">輪詢中…</span></div>
  </div>

  <div class="tabs">
    <button class="tab active" data-tab="report">收尾檢核</button>
    <button class="tab" data-tab="all">全機殘留</button>
  </div>

  <div id="tab-report">
  <div id="banner" class="banner"></div>
  <div id="card-slot">
    <div class="card"><div class="empty">還沒有收尾報告。AI 改了核心檔案或多個檔、宣告完成時會交一份，交了就會出現在這裡。</div></div>
  </div>
  <div id="temp-slot"></div>

  <div class="grid-wrap">
    <div class="grid-h">
      <span>最近 ${64} 輪</span>
      <span class="legend">
        <span><i style="background:var(--sev-routine)"></i>例行</span>
        <span><i style="background:var(--sev-notable)"></i>有修補</span>
        <span><i style="background:var(--sev-real)"></i>疑似偷懶（待核對）</span>
      </span>
    </div>
    <div id="grid" class="grid"></div>
  </div>
  </div>

  <div id="tab-all" style="display:none">
    <div class="card">
      <div class="all-sum"><span id="all-sum">還沒讀取</span><button id="all-refresh" class="aec-dec-btn">重新整理</button></div>
      <div id="all-body"></div>
    </div>
  </div>

<script>
// 瀏覽器端（勿 hoist；字串串接、不用 template literal）。
var POLL_MS = 1500, BEAT_MS = 10000, GRID_N = 64;
var SEV = {
  "routine":      { cls: "routine", label: "例行" },
  "notable":      { cls: "notable", label: "有修補" },
  "real-evasion": { cls: "real",    label: "疑似偷懶（待核對）" }
};
var activeKey = null;   // 使用者點選的歷史格（null=跟隨最新）
var reports = [];       // 新→舊

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>]/g, function (ch) {
    return ch === "&" ? "&amp;" : ch === "<" ? "&lt;" : "&gt;";
  });
}
// 「無」的認定與 Node aecBlank／Python _aec_blank 同規則：容許結尾標點（「無。」）與「無（說明）」
function isBlank(v) {
  var s = String(v == null ? "" : v).trim().replace(/[\\s。．.,，、；;：:!！?？~～\\-—…]+$/, "");
  return s === "" || /^[無无]\\s*(?:[（(][^）)]*[）)])?$/.test(s);
}
function sevOf(r) { return SEV[r && r.severity] || SEV.routine; }
function keyOf(r) { return (r.session_id || "?") + "|" + (r.turn_seq != null ? r.turn_seq : "?"); }
// 這則是哪個 session 寫的（session 前 8 碼）
function whoOf(r) { return "session " + String(r.session_id || "?").slice(0, 8); }
function tipOf(r) {
  return whoOf(r) + " · 第 " + r.turn_seq + " 輪 · " +
    sevOf(r).label + " · " + String(r.at || "").slice(5, 16).replace("T", " ");
}

// 原始欄位照 AI 交的原樣顯示：只有真的空才寫「無」
function sectionHtml(letter, name, val) {
  var blank = String(val == null ? "" : val).trim() === "";
  var body = blank
    ? '<div class="sec-body blank">無</div>'
    : '<div class="sec-body">' + esc(val) + "</div>";
  return '<div class="sec"><div class="sec-h">(' + letter + ') ' + name +
         ' <span class="k"></span></div>' + body + "</div>";
}

function escAttr(s) { return esc(s).replace(/"/g, "&quot;"); }

// 「這個 session 留下的東西」面板：資料來自 /api/aec/tempfiles/<sid>（Python 現場查還在的、附白話狀態），
// 不從 (i) 文字猜。每列「保留／刪除」都給（使用者決定權）；刪除先 confirm()，要再確認的（沒合併的分支、
// 有改動的工作樹、遠端分支、整個 repo）再問一次才帶 force 送出；結果當場顯示在該列。
// 注意：本 script 整塊在外層 render() 的 template literal 內，字串/comment 中的反斜線
// 都須 \\ 跳脫，否則會在 render 時被 outer JS 當跳脫序列吃掉（換行字元須寫 "\\n"）。
var KIND = {
  worktree: "🗂 工作樹", branch: "🌿 分支", remote_branch: "☁ 遠端分支",
  repo: "📦 臨時 repo", dir: "📁 資料夾", file: "📄 檔案"
};
var rowMsg = {};   // key → 上次按鈕的結果（當場顯示，下次重抓清單仍保留）
// scope："one"＝這個 session 的面板（按完重抓那個 session）；"all"＝全機殘留分頁（按完重抓全機清單）
function tempRow(sid, it, scope) {
  var msg = rowMsg[it.key] || (it.decision === "keep" ? "你選了保留" : (it.decision_message || ""));
  var attrs = ' data-sid="' + escAttr(String(sid)) + '" data-key="' + escAttr(String(it.key)) +
              '" data-title="' + escAttr(String(it.title)) + '" data-confirm="' + escAttr(String(it.confirm || "")) +
              '" data-scope="' + (scope || "one") + '"';
  var del = it.can_delete
    ? '<button class="aec-dec-btn danger"' + attrs + ' data-action="delete">刪除</button>'
    : '<button class="aec-dec-btn" disabled title="' + escAttr(String(it.label)) + '">不能刪</button>';
  var btns = (msg ? '<span class="dec-status">' + esc(msg) + "</span>" : "") +
    '<button class="aec-dec-btn"' + attrs + ' data-action="keep">保留</button>' + del;
  var meta = esc(it.label) + (it.origin ? " · " + esc(it.origin) : "") + (it.note ? " · AI 說：" + esc(it.note) : "");
  return '<div class="dec-row' + (it.decision === "keep" ? " dec-done" : "") + '">' +
         '<span class="dec-item" title="' + escAttr(String(it.path)) + '">' + (KIND[it.kind] || esc(it.kind)) + "　" +
           esc(it.title) + '<span class="k"> — ' + meta + "</span></span>" +
         '<span class="dec-btns">' + btns + "</span></div>";
}

function renderTemp(sid, items) {
  var slot = document.getElementById("temp-slot");
  if (!sid) { slot.innerHTML = ""; return; }
  var head = '<div class="card"><div class="sec"><div class="sec-h">這個 session 留下的東西（' + items.length + "）" +
             '<span class="k">　滑鼠停在名稱上看完整路徑</span></div>';
  var rows = "", alive = {};
  for (var i = 0; i < items.length; i++) { rows += tempRow(sid, items[i], "one"); alive[items[i].key] = true; }
  var done = "";   // 已經從清單消失的（刪掉了）：結果留一行，不讓按完就什麼都看不到
  for (var k in rowMsg) {
    if (!alive[k] && rowMsg[k].charAt(0) === "✔") { done += '<div class="dec-row dec-done"><span class="dec-item">' + esc(rowMsg[k]) + "</span></div>"; }
  }
  var body = rows || done ? rows + done : '<div class="sec-body blank">沒有留下東西</div>';
  slot.innerHTML = head + '<div class="sec-body dec-list">' + body + "</div></div></div>";
  var btns = slot.querySelectorAll(".aec-dec-btn");
  for (var b = 0; b < btns.length; b++) { btns[b].addEventListener("click", onDecClick); }
}

var lastTempKey = "";   // 上次已渲染的 sid|json，同內容不重繪（避免每 1.5s 閃）
function pollTemp(sid) {
  if (!sid) { renderTemp("", []); return; }
  fetch("/api/aec/tempfiles/" + encodeURIComponent(sid))
    .then(function (res) { return res.ok ? res.json() : { items: [] }; })
    .then(function (j) {
      var items = (j && j.items) || [];
      var key = sid + "|" + JSON.stringify(items);
      if (key === lastTempKey) { return; }
      lastTempKey = key;
      renderTemp(sid, items);
    })
    .catch(function () {});
}

// 卡片：燈號 → 要你處理 → 份量 → ① 你這次要的事 ② 碰到你的長期原則、方向 ③ AI 自己做主的 → 之後要追 → 附錄（摺疊）。
// 有 goal／principles／ai_decided 三類的是新報告；沒有的是舊格式，照舊欄位放進同一個框（①放全文與修補、③放 e／f）。
var AI_KIND = ${JSON.stringify(AI_DECIDED_KINDS)};
function hasClasses(r) { return Array.isArray(r.goal); }
function listOf(v) { return Array.isArray(v) ? v : []; }
function itemChars(it, keys) {
  var n = 0;
  for (var j = 0; j < keys.length; j++) { var v = (it || {})[keys[j]]; n += isBlank(v) ? 0 : String(v).trim().length; }
  return n;
}
function charsOf(list, keys) {
  var n = 0;
  for (var i = 0; i < list.length; i++) { n += itemChars(list[i], keys); }
  return n;
}
// 三類的份量：件數與 AI 寫的字數（使用者原話不算）。目標那類比自己做主那類少 → 標黃，給人一眼看出力氣花在哪。
function weightOf(r) {
  var g = listOf(r.goal), p = listOf(r.principles), a = listOf(r.ai_decided);
  return { goalN: g.length, goalChars: charsOf(g, ["done", "verified", "not_done"]),
           prinN: p.length, prinChars: charsOf(p, ["principle", "choice"]),
           aiN: a.length, aiChars: charsOf(a, ["what", "why"]) };
}
function goalIsThin(w) { return !w.goalN || w.aiChars > w.goalChars; }
function openGoals(r) { return listOf(r.goal).filter(function (x) { return !isBlank((x || {}).not_done); }).length; }
function nextStep(h) {
  var m = String(h == null ? "" : h).trim().match(/^下一動\\s*[=＝:：]\\s*([\\s\\S]*)$/);
  return m ? m[1].trim() : "";
}
function todoItems(r) {
  var out = [], ns = nextStep(r.h);
  if (ns) { out.push(["下一步要你做", ns]); }
  if (hasClasses(r)) {
    var w = weightOf(r), open = openGoals(r);
    if (!w.goalN) { out.push(["AI 沒列你這次要的事", "第一類是空的：看不出這輪對你要的事做了什麼"]); }
    else if (goalIsThin(w)) {
      out.push(["你要的事寫得比 AI 自己做主的少", "你要的事 " + w.goalChars + " 字、AI 自己做主 " + w.aiChars +
                " 字。看看第一類是不是一句帶過、力氣花在別處。"]);
    }
    if (open) { out.push(["你要的事有 " + open + " 件沒做完", "看第一類標「沒做」的那幾行，理由站不站得住"]); }
    if (w.aiN) { out.push(["AI 自己做主了 " + w.aiN + " 件", "看第三類，有沒有該先問你的"]); }
  } else if (!isBlank(r.e)) {
    out.push(["AI 自己做的決定、沒驗證的假設", "看第三類，對不對"]);
  }
  if (r.d_pending && r.d_pending.length) { out.push(["記憶寫入被推到之後（AI 會被擋回去補寫）", r.d_pending.join("\\n")]); }
  if (r.j_missing) { out.push(["驗證證據的路徑缺了或不存在", jOf(r) || "（空）"]); }
  if (r.k_missing) { out.push(["追蹤項是空的", "AI 要一行一項補上，或寫「無」"]); }
  return out;
}
function lampOf(r) {
  if (sevOf(r).cls === "real") { return { cls: "real", text: "🔴 疑似偷懶（待核對）" }; }
  if (hasClasses(r) && goalIsThin(weightOf(r))) { return { cls: "todo", text: "🟡 你要的事寫得少，看一下" }; }
  if (todoItems(r).length) { return { cls: "todo", text: "🟡 有事要你決定" }; }
  return { cls: "ok", text: "✅ 可以關了" };
}
function itemsHtml(items, empty) {
  if (!items.length) { return '<div class="sec-body blank">' + empty + "</div>"; }
  return items.map(function (x) {
    return '<div class="item"><div class="item-h">' + esc(x[0]) + '</div><div class="sec-body">' + esc(x[1]) + "</div></div>";
  }).join("");
}
function partHtml(title, items, empty) {
  return '<div class="sec"><div class="sec-h">' + title + "</div>" + itemsHtml(items, empty) + "</div>";
}
function picked(pairs) {
  return pairs.filter(function (x) { return !isBlank(x[1]); });
}
// note＝HUD 自己加的提醒（不是 AI 寫的），用灰字接在後面
function kv(label, val, cls, note) {
  return '<div class="kv' + (cls ? " " + cls : "") + '"><span class="kl">' + label + '</span><span class="kvv">' +
         esc(String(val == null ? "" : val).trim()) + (note ? '<span class="k">　' + note + "</span>" : "") + "</span></div>";
}
// 「怎麼確認」沒有任何數字、也不是明說「沒驗」→ 多半是「測過了」這種一句帶過
function vagueCheck(v) {
  var s = String(v == null ? "" : v);
  return !isBlank(s) && !/[0-9０-９]/.test(s) && !/^\\s*沒驗/.test(s);
}
function techHtml(t) {
  return isBlank(t) ? "" : '<details class="tech"><summary>技術細節</summary><div class="sec-body">' + esc(t) + "</div></details>";
}
// 「你說」核對記號：Python 收報告時拿主對話紀錄裡你本人打的字比過（said_check）；舊報告沒有這個欄位就不標。
// 值 → [樣式, 字]；「第 N 回合前」另外組字。
var SAID_CHECK = {
  "本回合": ["ok", "✓"],
  "對不到": ["warn", "⚠ AI 抄的這句在你的訊息裡找不到"],
  "派工": ["src", "出自派工說明，不是你直接打的字"],
  "判不了": ["gray", "讀不到對話紀錄，沒核對"],
  "太短不判": ["gray", "太短，沒核對"]
};
function saidCheckHtml(c) {
  c = String(c == null ? "" : c);
  var m = SAID_CHECK[c];
  if (!m && c.indexOf("第 ") === 0 && c.slice(-3) === "回合前") { m = ["src", "出自你 " + c.slice(2, -3).trim() + " 回合前的訊息"]; }
  return m ? '<span class="sc ' + m[0] + '" title="系統拿你本人打的字核對 AI 抄的這句：' + escAttr(c) + '">' + esc(m[1]) + "</span>" : "";
}
// 你這回合說的原話：Python 從主對話紀錄取（不靠 AI 抄），對照 AI 有沒有漏列你要的事；超過 USAID_OPEN_MAX 字預設收起來
var USAID_OPEN_MAX = 400;
function userSaidHtml(r) {
  if (!Array.isArray(r.user_said_this_turn)) { return ""; }
  var msgs = r.user_said_this_turn, chars = 0;
  for (var i = 0; i < msgs.length; i++) { chars += String(msgs[i]).length; }
  var body = msgs.length
    ? msgs.map(function (m) { return '<div class="sec-body usaid-msg">' + esc(m) + "</div>"; }).join("")
    : '<div class="sec-body blank">紀錄裡沒找到你這回合打的字</div>';
  return '<div class="sec"><details class="usaid"' + (chars <= USAID_OPEN_MAX ? " open" : "") + "><summary>你這回合說的原話" +
    ' <span class="k">' + msgs.length + " 則・" + chars + " 字　對照看 AI 有沒有漏列你要的事</span></summary>" + body + "</details></div>";
}
function goalItemHtml(x) {
  x = x || {};
  var said = isBlank(x.said) ? '<div class="said none">（沒掛你的原話）</div>'
    : '<div class="said">你說：「' + esc(String(x.said).trim()) + "」" + saidCheckHtml(x.said_check) + "</div>";
  var vague = vagueCheck(x.verified);
  return '<div class="gi">' + said + kv("做了", x.done) +
         kv("怎麼確認", x.verified, vague ? "nd" : "", vague ? "（沒附數字或收據）" : "") +
         (isBlank(x.not_done) ? "" : kv("沒做", x.not_done, "nd")) + techHtml(x.tech) + "</div>";
}
function principleItemHtml(x) {
  x = x || {};
  return '<div class="gi pi">' + kv("原則", x.principle) + kv("怎麼取捨", x.choice) + techHtml(x.tech) + "</div>";
}
function aiItemHtml(x) {
  x = x || {};
  return '<div class="gi ai"><div class="said"><span class="tag">' + esc(AI_KIND[x.kind] || x.kind || "沒分種類") + "</span>" +
         esc(String(x.what == null ? "" : x.what).trim()) + "</div>" + kv("為什麼", x.why) + techHtml(x.tech) + "</div>";
}
function classHtml(title, note, list, itemFn, empty) {
  var body = list.length ? list.map(itemFn).join("") : '<div class="sec-body blank">' + empty + "</div>";
  return '<div class="sec"><div class="sec-h">' + title + ' <span class="k">' + list.length + " 件　" + note + "</span></div>" + body + "</div>";
}
function weighHtml(r) {
  var w = weightOf(r), thin = goalIsThin(w);
  return '<div class="weigh' + (thin ? " warn" : "") + '">份量：你要的事 <b>' + w.goalN + " 件・" + w.goalChars + " 字</b>" +
         "｜碰到大原則 " + w.prinN + " 件・" + w.prinChars + " 字｜AI 自己做主 <b>" + w.aiN + " 件・" + w.aiChars + " 字</b>" +
         (thin ? "　⚠ 你要的事寫得比較少" : "") + "</div>";
}
function classesHtml(r) {
  var lead = isBlank(r.report) ? "" : '<div class="lead">' + esc(String(r.report).trim()) + "</div>";
  return '<div class="sec">' + lead + weighHtml(r) + "</div>" + userSaidHtml(r) +
    classHtml("① 你這次要的事", "每件對照你的原話", listOf(r.goal), goalItemHtml, "AI 沒列你這次要的事") +
    classHtml("② 碰到你的長期原則、方向", "怎麼取捨", listOf(r.principles), principleItemHtml, "這輪沒碰到") +
    classHtml("③ AI 自己做主的", "你沒要求、AI 自己決定的", listOf(r.ai_decided), aiItemHtml, "AI 說這輪沒有自己做主的事");
}
// 舊格式（沒有三類）：①放 AI 寫的收尾全文與修補清單、③放 e／f；當時沒有②這一類。
function legacyClassesHtml(r) {
  return '<div class="sec"><div class="weigh">舊格式報告：當時還沒分三類，下面照舊欄位放</div></div>' +
    partHtml("① 你這次要的事", picked([["AI 寫的收尾全文（沒逐件對照你的原話）", r.report], ["修了什麼", r.a]]), "這份舊報告沒寫做了什麼") +
    partHtml("② 碰到你的長期原則、方向", [], "舊格式沒有這一類") +
    partHtml("③ AI 自己做主的", picked([["AI 自己做的決定、沒驗證的假設", r.e], ["環境有變動", r.f]]), "這份舊報告沒寫");
}
// 附錄：系統帳翻成白話（記住了、改了哪些地方、版控、暫存、驗證收據）＋原始欄位，給要查的時候看
function appendixHtml(r) {
  var oldest = r.e == null && !hasClasses(r);   // 最早的格式只有 a～d，d 是暫存清單、不是記憶帳
  var items = picked([
    ["記住了（寫進記憶卡的）", oldest ? null : r.d],
    ["改了哪些地方（檔案:行）", hasClasses(r) ? r.a : null],
    ["版控", r.g],
    ["AI 說留下的暫存（還在不在看下面「這個 session 留下的東西」）", r.i],
    ["驗證收據放在", jOf(r)]
  ]);
  return '<details class="detail"><summary>附錄：技術細節與系統帳（要查的時候看）</summary>' +
    itemsHtml(items, "沒有") + '<div class="item-h">原始欄位（AI 交的原樣）</div>' + detailHtml(r) + "</details>";
}
function cardHtml(r) {
  var lamp = lampOf(r);
  var cls = "card" + (lamp.cls === "todo" ? " sev-notable" : lamp.cls === "real" ? " sev-real" : "");
  var when = String(r.at || "").slice(5, 16).replace("T", " ");
  var html = '<div class="' + cls + '"><div class="card-head"><span class="lamp ' + lamp.cls + '">' + lamp.text + "</span>" +
    '<span class="who">' + esc(whoOf(r)) + "</span>" +
    '<span class="meta">' + esc(when) + " · 第 " + esc(r.turn_seq) + " 輪</span></div>";
  if (lamp.cls === "real") {
    html += partHtml("疑似偷懶的地方（hook 只比對字面，可能是誤判，看一下）", picked([["", r.b]]), "");
  }
  html += partHtml("要你處理", todoItems(r), "沒有要你處理的事") +
    (hasClasses(r) ? classesHtml(r) : legacyClassesHtml(r)) +
    (isBlank(kOf(r)) ? "" : partHtml("記下來之後要追的", [["", kOf(r)]], ""));
  return html + appendixHtml(r) + "</div>";
}
// 每 1.5 秒輪詢一次：內容沒變就不重畫（重畫會讓畫面跳、把點開的「細節」收回去）；「細節」開合照使用者上次的選擇
var cardKey = "", detailOpen = false;
function renderCard(r) {
  if (!r) { return; }
  var key = JSON.stringify(r);
  if (key === cardKey) { return; }
  cardKey = key;
  var slot = document.getElementById("card-slot");
  slot.innerHTML = cardHtml(r);
  var det = slot.querySelector("details.detail");
  if (det) {
    det.open = detailOpen;
    det.addEventListener("toggle", function (e) { detailOpen = e.currentTarget.open; });
  }
}
function detailHtml(r) {
  var sid = String(r.session_id || "?").slice(0, 8);
  var html = '<div class="sec"><div class="sec-body">session ' + esc(sid) + " · 第 " + esc(r.turn_seq) + " 輪 · " +
    esc(r.at || "") + " · 嚴重度 " + esc(r.severity || "") + "</div></div>" +
    sectionHtml("a", "缺失發現與修補清單", r.a) +
    sectionHtml("b", "AI 逃避通報", r.b) +
    (r.c == null ? "" : sectionHtml("c", "Token 累積警示（舊欄位）", r.c)) +
    // 最早的格式只有 a–d 且 d=衍生暫存：沒有 e 欄、也沒有三類，d 以舊標籤渲染。
    (r.e == null && !hasClasses(r)
      ? sectionHtml("d", "衍生暫存清單（舊格式；實際尚存者見下方殘檔面板）", r.d)
      : sectionHtml("d", "記憶收錄帳" + (r.d_pending && r.d_pending.length
            ? ' <span class="badge real">未寫入 ' + r.d_pending.length + " 項（Stop 已擋、待補寫後重提）</span>"
            : ""), r.d) +
        sectionHtml("e", "未告知決策＋未驗證假設", r.e) +
        sectionHtml("f", "靜默狀態改變", r.f) +
        sectionHtml("g", "版控收尾", r.g) +
        sectionHtml("h", "收尾判定", r.h) +
        sectionHtml("i", "衍生暫存清單（宣告；實際尚存者見下方殘檔面板）", r.i) +
        (jOf(r) == null ? "" :
          sectionHtml("j", "證據持久路徑" + (r.j_missing ? ' <span class="badge real">缺或不存在</span>' : ""), jOf(r)) +
          sectionHtml("k", "追蹤項" + (r.k_missing ? ' <span class="badge real">空字串</span>' : ""), kOf(r))));
  return html;
}
// 報告檔存的是 j_evidence_path／k_followups（tool 參數原名）；早期測試資料用 j／k，兩種都認
function jOf(r) { return r.j != null ? r.j : r.j_evidence_path; }
function kOf(r) { return r.k != null ? r.k : r.k_followups; }

var gridHtml = "";
function renderGrid() {
  var grid = document.getElementById("grid");
  var cells = reports.slice(0, GRID_N).slice().reverse();   // 舊→新，最新在右
  if (!cells.length) { grid.innerHTML = ""; gridHtml = ""; return; }
  var out = "";
  for (var i = 0; i < cells.length; i++) {
    var r = cells[i], s = sevOf(r), k = keyOf(r);
    var active = (k === activeKey) ? " active" : "";
    var tip = tipOf(r);
    out += '<div class="cell ' + s.cls + active + '" title="' + esc(tip) +
           '" data-key="' + esc(k) + '">' + (s.cls === "real" ? "!" : "") + "</div>";
  }
  if (out === gridHtml) { return; }   // 格子沒變就不重畫（滑鼠停著看提示時不會被打斷）
  gridHtml = out;
  grid.innerHTML = out;
  var nodes = grid.querySelectorAll(".cell");
  for (var j = 0; j < nodes.length; j++) {
    nodes[j].addEventListener("click", onCellClick);
  }
}

function onCellClick(e) {
  var k = e.currentTarget.getAttribute("data-key");
  var parts = k.split("|");
  activeKey = k;
  fetch("/api/aec/report/" + encodeURIComponent(parts[0]) + "/" + encodeURIComponent(parts[1]))
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (r) { if (r) { renderCard(r); renderGrid(); } })
    .catch(function () {});
}

function findReport(sid, turn) {
  for (var i = 0; i < reports.length; i++) {
    if (String(reports[i].session_id) === String(sid) &&
        String(reports[i].turn_seq) === String(turn)) { return reports[i]; }
  }
  return null;
}

function onDecClick(e) {
  var el = e.currentTarget;
  var action = el.getAttribute("data-action"), extra = el.getAttribute("data-confirm"), force = false;
  if (action === "delete") {
    if (!window.confirm("確定刪除？\\n" + el.getAttribute("data-title"))) { return; }
    if (extra) {
      if (!window.confirm(extra)) { return; }
      force = true;
    }
  }
  postDecision(el.getAttribute("data-sid"), el.getAttribute("data-key"), action, force, el.getAttribute("data-scope"));
}

function refreshAfter(scope, sid) {
  if (scope === "all") { loadAll(); } else { lastTempKey = ""; pollTemp(sid); }
}

// POST → Node 轉給 Python 當場執行（刪除或記下保留），回 {ok, message}；結果寫在該列，再重抓清單。
function postDecision(sid, key, action, force, scope) {
  rowMsg[key] = action === "delete" ? "刪除中…" : "記下中…";
  refreshAfter(scope, sid);
  fetch("/api/aec/decision", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sid: sid, key: key, action: action, force: force })
  })
    .then(function (res) { return res.ok ? res.json() : { ok: false, message: "HUD 伺服器回應錯誤" }; })
    .then(function (j) { rowMsg[key] = (j.ok ? "✔ " : "✖ ") + (j.message || ""); refreshAfter(scope, sid); })
    .catch(function () { rowMsg[key] = "✖ 連不到 HUD 伺服器"; refreshAfter(scope, sid); });
}

// ── 全機殘留分頁：/api/aec/tempfiles-all（Python 掃全部帳本、依 session 分組、附 session 還開著沒有）──
// 每組一行摘要＋「清掉不用再確認的」（Python 現場判哪些不用再確認：暫存檔、專案外檔案資料夾、乾淨工作樹、已合併分支…；
// 要再確認的、按過保留的、來源不明的不動）；展開看每一項，逐項保留／刪除跟單一 session 面板同一套。
var KIND_SHORT = { worktree: "工作樹", branch: "分支", remote_branch: "遠端分支", repo: "臨時 repo", dir: "資料夾", file: "檔案" };
var allOpen = {};     // sid → 使用者展開／收起過的狀態（重繪時保留）
var lastBulk = "";    // 上次整組清的結果（那組刪光消失了也看得到）
function safeCount(items) {
  var n = 0;
  for (var i = 0; i < items.length; i++) {
    var it = items[i];
    if (it.can_delete && !it.confirm && it.decision !== "keep" && it.source !== "snapshot") { n++; }
  }
  return n;
}
function kindSummary(items) {
  var c = {}, order = ["worktree", "branch", "remote_branch", "repo", "dir", "file"], out = [];
  for (var i = 0; i < items.length; i++) { c[items[i].kind] = (c[items[i].kind] || 0) + 1; }
  for (var j = 0; j < order.length; j++) { if (c[order[j]]) { out.push(KIND_SHORT[order[j]] + " " + c[order[j]]); } }
  return out.join("、");
}
function hasGit(items) {
  for (var i = 0; i < items.length; i++) { if (items[i].kind !== "file" && items[i].kind !== "dir") { return true; } }
  return false;
}
function loadAll() {
  document.getElementById("all-sum").textContent = "讀取中…（要查 git，可能要幾秒）";
  fetch("/api/aec/tempfiles-all")
    .then(function (res) { return res.ok ? res.json() : { sessions: [], total: 0, error: "HUD 伺服器回應錯誤" }; })
    .then(renderAll)
    .catch(function () { renderAll({ sessions: [], total: 0, error: "連不到 HUD 伺服器" }); });
}
function renderAll(j) {
  var ss = (j && j.sessions) || [];
  var sum = j && j.error ? "✖ " + j.error
    : (j.total ? "全機還有 " + j.total + " 樣東西，分屬 " + ss.length + " 個 session（只列還在的）" : "全機沒有留下東西");
  document.getElementById("all-sum").textContent = sum + (lastBulk ? "　｜　" + lastBulk : "");
  var html = "";
  for (var i = 0; i < ss.length; i++) {
    var s = ss[i], items = s.items || [], n = safeCount(items);
    var open = allOpen[s.sid] != null ? allOpen[s.sid] : (hasGit(items) || items.length <= 5);
    var rows = "";
    for (var k = 0; k < items.length; k++) { rows += tempRow(s.sid, items[k], "all"); }
    var bulk = n ? '<button class="aec-dec-btn danger aec-bulk" data-sid="' + escAttr(s.sid) + '" data-n="' + n +
                   '" data-state="' + escAttr(s.state) + '">清掉不用再確認的（' + n + "）</button>" : "";
    html += '<div class="grp"><div class="grp-head"><span>session ' + esc(String(s.sid).slice(0, 8)) +
            ' <span class="k">· ' + esc(s.label) + " · " + esc(kindSummary(items)) + " · 最後 " +
            esc(String(s.latest || "").slice(5, 16).replace("T", " ")) + "</span></span>" + bulk + "</div>" +
            '<details data-sid="' + escAttr(s.sid) + '"' + (open ? " open" : "") + "><summary>列出 " + items.length + " 樣</summary>" +
            '<div class="sec-body dec-list">' + rows + "</div></details></div>";
  }
  var body = document.getElementById("all-body");
  body.innerHTML = html || '<div class="sec-body blank">沒有留下東西</div>';
  var btns = body.querySelectorAll(".aec-dec-btn[data-action]");
  for (var b = 0; b < btns.length; b++) { btns[b].addEventListener("click", onDecClick); }
  var bulks = body.querySelectorAll(".aec-bulk");
  for (var u = 0; u < bulks.length; u++) { bulks[u].addEventListener("click", onBulkClick); }
  var dets = body.querySelectorAll("details");
  for (var d = 0; d < dets.length; d++) {
    dets[d].addEventListener("toggle", function (e) { allOpen[e.currentTarget.getAttribute("data-sid")] = e.currentTarget.open; });
  }
}
function onBulkClick(e) {
  var el = e.currentTarget, sid = el.getAttribute("data-sid"), n = el.getAttribute("data-n");
  var warn = el.getAttribute("data-state") === "open" ? "\\n注意：這個 session 還開著，它可能還在用這些東西。" : "";
  if (!window.confirm("要刪掉 session " + sid.slice(0, 8) + " 留下、不用再確認的 " + n + " 樣東西" +
                      "（暫存檔、專案外檔案資料夾、乾淨的工作樹、已合併分支…）。要再確認的、按過保留的、來源不明的不會動。" +
                      warn + "\\n確定嗎？")) { return; }
  el.disabled = true; el.textContent = "刪除中…";
  fetch("/api/aec/decision", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sid: sid, all_safe: true, action: "delete" })
  })
    .then(function (res) { return res.ok ? res.json() : { ok: false, message: "HUD 伺服器回應錯誤" }; })
    .then(function (j) { lastBulk = "session " + sid.slice(0, 8) + "：" + (j.ok ? "✔ " : "✖ ") + (j.message || ""); loadAll(); })
    .catch(function () { lastBulk = "session " + sid.slice(0, 8) + "：✖ 連不到 HUD 伺服器"; loadAll(); });
}
function showTab(t) {
  document.getElementById("tab-report").style.display = t === "report" ? "" : "none";
  document.getElementById("tab-all").style.display = t === "all" ? "" : "none";
  var tabs = document.querySelectorAll(".tab");
  for (var i = 0; i < tabs.length; i++) { tabs[i].className = "tab" + (tabs[i].getAttribute("data-tab") === t ? " active" : ""); }
  if (t === "all") { loadAll(); }
}
(function () {
  var tabs = document.querySelectorAll(".tab");
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].addEventListener("click", function (e) { showTab(e.currentTarget.getAttribute("data-tab")); });
  }
  document.getElementById("all-refresh").addEventListener("click", loadAll);
})();

function updateBanner() {
  var banner = document.getElementById("banner");
  var latest = reports[0];
  if (latest && sevOf(latest).cls === "real") {
    banner.textContent = "🔴 最新一輪疑似偷懶（待核對）：看卡片裡抓到的說法，hook 只比對字面，可能是誤判。";
    banner.className = "banner show";
  } else {
    banner.className = "banner";
  }
}

function applyReports(data) {
  reports = (data && data.reports) || [];
  document.getElementById("poll-txt").textContent =
    reports.length ? (reports.length + " 份報告 · 最新第 " + reports[0].turn_seq + " 輪") : "還沒有報告";
  if (activeKey === null && reports.length) { renderCard(reports[0]); }
  renderGrid();
  updateBanner();
  // 殘檔面板跟著目前顯示的卡片所屬 session（點了歷史格就跟那格）。
  var curSid = activeKey !== null ? String(activeKey).split("|")[0]
                                  : (reports.length ? reports[0].session_id : "");
  pollTemp(curSid);
}
function pollFailed() { document.getElementById("poll-txt").textContent = "連線中斷"; }
function poll() {
  fetch("/api/aec/reports")
    .then(function (res) { return res.ok ? res.json() : { reports: [] }; })
    .then(function (data) { applyReports(data); ackBeat(); })
    .catch(pollFailed);
}
// 心跳＝主執行緒剛把報告畫上去（證明使用者看得到），最多每 BEAT_MS 一拍。
var lastBeatAt = 0;
function ackBeat() {
  var now = Date.now();
  if (now - lastBeatAt < BEAT_MS) return;
  lastBeatAt = now;
  fetch("/api/aec/beat").catch(function () {});
}
// 輪詢排程跑在 Web Worker：Chromium 對「隱藏/被遮住 ≥5 分鐘」的頁面把主執行緒 setInterval 節流成
// 每分鐘一次，HUD 躲在 VS Code 後面時心跳會變 60s、hook 判窗死。Worker 的計時器不受該節流；
// 主執行緒只在收到 Worker 訊息時渲染＋回心跳（事件驅動，不是計時器）。建不出 Worker 才退回主執行緒。
var fallbackStarted = false;
function startMainLoop() {
  if (fallbackStarted) return;
  fallbackStarted = true;
  poll(); setInterval(poll, POLL_MS);
}
function startLoop() {
  var src = "var u=" + JSON.stringify(location.origin + "/api/aec/reports") + ";" +
    "function p(){fetch(u).then(function(r){return r.ok?r.json():{reports:[]};})" +
    ".then(function(d){postMessage({ok:true,data:d});}).catch(function(){postMessage({ok:false});});}" +
    "p();setInterval(p," + POLL_MS + ");";
  try {
    var w = new Worker(URL.createObjectURL(new Blob([src], { type: "text/javascript" })));
    w.onmessage = function (e) {
      if (e.data && e.data.ok) { applyReports(e.data.data); ackBeat(); } else { pollFailed(); }
    };
    w.onerror = function () { try { w.terminate(); } catch (e2) {} startMainLoop(); };
  } catch (e) {
    startMainLoop();
  }
}
// 存在證明：對 Node 開一條 SSE 常駐連線（/api/aec/stream）。頁被瀏覽器凍結時心跳會停、連線仍在；
// 視窗關了才斷，hook 據此判「窗開著」不吵 chat。內容不走這條（仍由 Worker 輪詢），斷線瀏覽器自動重連。
var presence = null;
function openPresence() {
  try { presence = new EventSource("/api/aec/stream"); } catch (e) { presence = null; }
}
startLoop();
openPresence();
</script>
</body>
</html>`;
}

module.exports = { render };
