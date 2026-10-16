// aec-hud-html.js — Anti-Evasion HUD 頁模板。匯出 render()->string（鏡像 dashboard-html.js）。
//
// dark HUD 單頁：即時最新收尾檢核卡（(a)–(i) 分區；舊報告僅 a–d）+ 底部近 N 回合 severity 歷史格。
// 傳輸＝輪詢（非 SSE）：setInterval 1.5s fetch /api/aec/reports（增量 ?since=）→ 渲染；
// 格子 click → fetch /api/aec/report/<sid>/<turn> 展開；每 10s fetch /api/aec/beat 送心跳。
//
// 視覺（dataviz skill 驗證）：severity 為 status palette，CVD ΔE 44.6（>>12）+ 皆 ≥3:1；
// routine=靜色灰 / notable=琥珀 / real-evasion=紅，且每格附文字標籤（secondary encoding，
// 非 color-alone）。surface 用 github-dark（與 dashboard-html.js 同族）。
//
// ★內層 <script> 為瀏覽器端 JS（非模組 state）：整塊 verbatim、**勿 hoist**（比照 _MAP C7）；
// 為免 nested-backtick，瀏覽器端一律字串串接、不用 template literal。

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
function isBlank(v) { var s = String(v == null ? "" : v).trim(); return s === "" || s === "無"; }
function sevOf(r) { return SEV[r && r.severity] || SEV.routine; }
function keyOf(r) { return (r.session_id || "?") + "|" + (r.turn_seq != null ? r.turn_seq : "?"); }

function sectionHtml(letter, name, val) {
  var blank = isBlank(val);
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

// 卡片：燈號＋一句話 → 要你處理 → 這輪做了什麼 → 記住了／之後要追；欄位字母與原始內容收進「細節」。
function nextStep(h) {
  var m = String(h == null ? "" : h).trim().match(/^下一動\\s*[=＝:：]\\s*([\\s\\S]*)$/);
  return m ? m[1].trim() : "";
}
function todoItems(r) {
  var out = [], ns = nextStep(r.h);
  if (ns) { out.push(["下一步要你做", ns]); }
  if (!isBlank(r.e) && r.e != null) { out.push(["AI 自己做的決定、沒驗證的假設（看一下對不對）", r.e]); }
  if (r.d_pending && r.d_pending.length) { out.push(["記憶寫入被推到之後（AI 會被擋回去補寫）", r.d_pending.join("\\n")]); }
  if (r.j_missing) { out.push(["驗證證據的路徑缺了或不存在", jOf(r) || "（空）"]); }
  if (r.k_missing) { out.push(["追蹤項是空的", "AI 要一行一項補上，或寫「無」"]); }
  return out;
}
function lampOf(r) {
  if (sevOf(r).cls === "real") { return { cls: "real", text: "🔴 疑似偷懶（待核對）" }; }
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
  return pairs.filter(function (x) { return !isBlank(x[1]) && x[1] != null; });
}
function cardHtml(r) {
  var lamp = lampOf(r);
  var cls = "card" + (lamp.cls === "todo" ? " sev-notable" : lamp.cls === "real" ? " sev-real" : "");
  var when = String(r.at || "").slice(5, 16).replace("T", " ");
  var html = '<div class="' + cls + '"><div class="card-head"><span class="lamp ' + lamp.cls + '">' + lamp.text + "</span>" +
    '<span class="meta">' + esc(when) + " · 第 " + esc(r.turn_seq) + " 輪</span></div>";
  if (lamp.cls === "real") {
    html += partHtml("疑似偷懶的地方（hook 只比對字面，可能是誤判，看一下）", picked([["", r.b]]), "");
  }
  html += partHtml("要你處理", todoItems(r), "沒有要你處理的事") +
    partHtml("這輪做了什麼", picked([["修了什麼", r.a], ["版控", r.g], ["環境有變動", r.f]]), "這輪沒有修補，也沒有改到環境") +
    (r.e == null ? "" : partHtml("記住了／之後要追", picked([["記住了", r.d], ["之後要追", kOf(r)]]), "沒有新記住的事，也沒有要追的"));
  return html + '<details class="detail"><summary>細節（原始欄位，給要查的時候看）</summary>' + detailHtml(r) + "</details></div>";
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
    // 舊報告（2026-09 前）只有 a–d 且 d=衍生暫存：無 e 欄視為舊格式，d 以舊標籤渲染。
    (r.e == null
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
          sectionHtml("k", "追蹤項" + (r.k_missing ? ' <span class="badge real">空字串</span>' : ""), kOf(r)))) +
    (r.need_goal ? renderGoal(r.need_goal) : "");
  return html;
}
// 報告檔存的是 j_evidence_path／k_followups（tool 參數原名）；早期測試資料用 j／k，兩種都認
function jOf(r) { return r.j != null ? r.j : r.j_evidence_path; }
function kOf(r) { return r.k != null ? r.k : r.k_followups; }

// 目標對照（Python 收尾檢核分支附的 need_goal：原話摘要＋目標樹＋完整對照結果）；只有寫碼類樹才有這一塊
var GOAL_STATUS = { todo: "未開始", doing: "進行中", done: "達成", partial: "部分", none: "沒有", dropped: "放棄" };
function renderGoal(g) {
  var rc = g.reconcile || {};
  var badge = rc.ok ? '<span class="badge routine">完整對照通過</span>' : '<span class="badge real">完整對照未過</span>';
  var said = (g.user_said || []).map(function (s) {
    return "第 " + esc(s.turn) + " 回合" + (s.prior ? "（前一個 session）" : "") + "：「" + esc(s.text) + "」";
  }).join("<br>");
  var nodes = (g.nodes || []).map(function (n) {
    var pad = new Array((n.depth || 0) + 1).join("　　");
    return pad + esc(n.id) + " [" + esc(GOAL_STATUS[n.status] || n.status) + "] " + esc(n.text) +
      (n.evidence && n.evidence.length ? " · 證據：" + esc(n.evidence.join("、")) : "") +
      (n.followup ? " · 未完：" + esc(n.followup) : "");
  }).join("<br>");
  var probs = (rc.problems || []).map(function (p) { return "✗ " + esc(p); }).join("<br>");
  return '<div class="sec"><div class="sec-h">目標對照 ' + badge + ' <span class="k">' + esc(g.tree) +
         " · 目標版本 " + esc(g.goal_rev) + (g.owed ? " · 待對照的改動 " + esc(g.owed) : "") + "</span></div>" +
         '<div class="sec-body">使用者原話（權威）：<br>' + (said || "（沒有記到）") +
         "<br><br>目標樹（AI 的解讀）：<br>" + nodes + (probs ? "<br><br>" + probs : "") + "</div></div>";
}

var gridHtml = "";
function renderGrid() {
  var grid = document.getElementById("grid");
  var cells = reports.slice(0, GRID_N).slice().reverse();   // 舊→新，最新在右
  if (!cells.length) { grid.innerHTML = ""; gridHtml = ""; return; }
  var out = "";
  for (var i = 0; i < cells.length; i++) {
    var r = cells[i], s = sevOf(r), k = keyOf(r);
    var active = (k === activeKey) ? " active" : "";
    var tip = "第 " + r.turn_seq + " 輪 · " + s.label + " · " + String(r.at || "").slice(5, 16).replace("T", " ");
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
