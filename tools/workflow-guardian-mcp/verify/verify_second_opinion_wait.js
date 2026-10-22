// verify_second_opinion_wait.js：second_opinion_result 等到 done／failed／blocked 才回（lib/second-opinion.js waitResult）。
// 案例：job 還在跑、跑完了 → 同一次呼叫回 done（不先回 running）；等滿上限仍在跑 → 回 running 並附「再呼叫一次」與「收尾寫明 job_id」；
// failed 不等；result 帶 status.json 的 notes（hook 判跨回合取回的那次材料有沒有帶到樹）；工具入口 toolSecondOpinionResult 走等待。
// 跑：node tools/workflow-guardian-mcp/verify/verify_second_opinion_wait.js（結尾印 SECOND_OPINION_WAIT_CHECK PASS／FAIL）
const fs = require("fs");
const os = require("os");
const path = require("path");

const root = fs.mkdtempSync(path.join(os.tmpdir(), "so-wait-"));
process.env.WG_CLAUDE_DIR = root;          // 在 require 之前：JOB_ROOT 落在暫存資料根
let ok = true;
const fail = (m) => { ok = false; console.error("FAIL: " + m); };
const pad = (n) => String(n).padStart(2, "0");
const now = () => {           // run.py 寫的 updated_at 是本地時間、不帶時區（readResult 照本地解析）
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
};

function job(id, status, extra = {}) {
  const dir = path.join(root, "workflow", "second-opinion", id);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "status.json"), JSON.stringify({
    status, job_id: id, hash: "h", model: "m", mode: "independent", timeout_s: 300, updated_at: now(), stage: "codex",
    notes: ["找不到部位卡（part='p'）", "材料沒有需求目標樹：沒帶 session_id"], ...extra,
  }));
  return dir;
}

(async () => {
  try {
    const so = require("../lib/second-opinion");
    if (typeof so.waitResult !== "function") throw new Error("second-opinion.js 沒有 waitResult（result 不會等）");

    const a = "20261023-120000-aaaaaaaa-stage-review";
    const dirA = job(a, "started");
    setTimeout(() => {
      fs.writeFileSync(path.join(dirA, "reply.md"), "## 結論\n照判定\n");
      job(a, "done");
    }, 400);
    const t0 = Date.now();
    const r1 = await so.waitResult(a, 5000, 50);
    if (!/^status: done/.test(r1.text)) fail("跑完了應回 done：" + r1.text.slice(0, 200));
    if (Date.now() - t0 > 4000) fail("done 之後沒立刻回（等到上限才回）");
    if (!/\nnote: 材料沒有需求目標樹/.test(r1.text)) fail("result 沒帶 status.json 的 notes：" + r1.text.slice(0, 300));
    if (r1.text.indexOf("note: ") > r1.text.indexOf("## 結論")) fail("note 行要在回覆全文之前（標頭段）");

    const b = "20261023-120000-bbbbbbbb-evaluate";
    job(b, "started");
    const t1 = Date.now();
    const r2 = await so.waitResult(b, 600, 50);
    if (!/^status: running/.test(r2.text) || r2.isError) fail("等滿仍在跑應回 running（非錯誤）：" + r2.text.slice(0, 200));
    if (Date.now() - t1 < 550) fail("沒等到上限就回 running");
    if (!/再呼叫一次 second_opinion_result/.test(r2.text) || !r2.text.includes(b)) fail("running 沒附下一步與 job_id：" + r2.text);
    if (!r2.text.includes(`等第二意見｜${b}`)) fail("running 沒教要先結束回覆時收尾寫一行「等第二意見｜<job_id>」：" + r2.text);

    // status.json 寫入空窗（run.py 不是原子替換）：讀不到不當 failed，照等
    const e = "20261023-120000-eeeeeeee-evaluate";
    const dirE = path.join(root, "workflow", "second-opinion", e);
    fs.mkdirSync(dirE, { recursive: true });
    fs.writeFileSync(path.join(dirE, "status.json"), "");
    setTimeout(() => { fs.writeFileSync(path.join(dirE, "reply.md"), "ok\n"); job(e, "done"); }, 300);
    const r5 = await so.waitResult(e, 5000, 50);
    if (!/^status: done/.test(r5.text)) fail("status.json 一時讀不到就提早回了：" + r5.text.slice(0, 200));
    const r6 = await so.waitResult("20261023-120000-ffffffff-evaluate", 5000, 50);
    if (!/找不到 job/.test(r6.text) || !r6.isError) fail("job 目錄不在要立刻回找不到：" + r6.text.slice(0, 200));

    const c = "20261023-120000-cccccccc-diagnose";
    job(c, "failed", { reason: "探針逾時" });
    const t2 = Date.now();
    const r3 = await so.waitResult(c, 5000, 50);
    if (!/^status: failed/.test(r3.text) || !r3.isError || Date.now() - t2 > 1000) fail("failed 要立刻回：" + r3.text.slice(0, 200));

    if (!(so.RESULT_WAIT_MS > 0 && so.RESULT_WAIT_MS < 120000)) fail(`每次等待上限要低於 Claude Code 互動模式 MCP 轉背景的 120 s：${so.RESULT_WAIT_MS}`);

    // 工具入口：toolSecondOpinionResult 走 waitResult（攔 sendToolResult 看回的字）
    const mcp = require("../lib/mcp");
    const sent = [];
    const orig = mcp.sendToolResult;
    mcp.sendToolResult = (id, text, isError) => { sent.push({ id, text, isError }); };
    const d = "20261023-120000-dddddddd-stage-review";
    const dirD = job(d, "started");
    setTimeout(() => { fs.writeFileSync(path.join(dirD, "reply.md"), "ok\n"); job(d, "done"); }, 300);
    await so.toolSecondOpinionResult(7, { job_id: d });
    mcp.sendToolResult = orig;
    if (!(sent.length === 1 && /^status: done/.test(sent[0].text))) fail("工具入口沒等到 done：" + JSON.stringify(sent).slice(0, 300));
  } catch (e) {
    fail((e && e.stack) || String(e));
  }
  fs.rmSync(root, { recursive: true, force: true });
  console.log(ok ? "SECOND_OPINION_WAIT_CHECK PASS" : "SECOND_OPINION_WAIT_CHECK FAIL");
  process.exit(ok ? 0 : 1);
})();
