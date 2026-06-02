// ════════════════════════════════════════════════════════════════════
//  world-chat.js — 腦內世界「生物 LLM 對話」代理（被 server.js require，
//                  同進程生命週期：server.js 啟動它就在、關閉它就沒）。
//
//  職責：把瀏覽器(world.html)的對話請求轉發到 config 的 rdchat-direct 後端
//        原生 Ollama /api/chat。base_url / 認證 留在此端（單一來源、不外洩 token）；
//        model / prompt / options 由前端帶（免重啟即可調整對話風格）。
//
//  零外部依賴，只用 Node 內建 http/https；server.js 內部 helper 透過 ctx 注入，
//  故本模組與 server.js 其餘程式解耦（只依賴 ctx 介面）。
// ════════════════════════════════════════════════════════════════════
"use strict";
const http = require("http");
const https = require("https");

const BACKEND_NAME = "rdchat-direct";   // config.vector_search.ollama_backends 的鍵
const UPSTREAM_TIMEOUT_MS = 30000;       // 31B 暖機可能久，給足；前端另有自己的逾時+fallback
const MAX_BODY = 100 * 1024;             // 100KB 上限，防爆

/**
 * 處理 POST /api/creature-chat。
 * @param req,res  Node http req/res
 * @param ctx      { loadConfig, jsonRes, WORKFLOW_DIR, fs, path }（由 server.js 注入）
 *
 * 前端 body：{ model, messages:[{role,content}...], options?, think? }
 * 回傳：{ content, eval_count, total_ms } 或 { error }
 */
function handleCreatureChat(req, res, ctx) {
  let body = "";
  let aborted = false;
  req.on("data", (c) => {
    body += c;
    if (body.length > MAX_BODY) { aborted = true; ctx.jsonRes(res, 413, { error: "body too large" }); req.destroy(); }
  });
  req.on("end", () => {
    if (aborted) return;
    let payload;
    try { payload = JSON.parse(body || "{}"); } catch { return ctx.jsonRes(res, 400, { error: "bad json" }); }
    if (!Array.isArray(payload.messages) || !payload.messages.length) {
      return ctx.jsonRes(res, 400, { error: "messages[] required" });
    }

    const cfg = ctx.loadConfig();
    const b = (cfg.vector_search && cfg.vector_search.ollama_backends || {})[BACKEND_NAME];
    if (!b || !b.base_url) return ctx.jsonRes(res, 503, { error: BACKEND_NAME + " backend not configured" });

    // 認證：rdchat-direct 原生 API 通常免 token；僅在 backend 標 auth 時帶 Bearer（沿用既有 .rdchat_token.json）
    let token = null;
    if (b.auth) {
      try { token = JSON.parse(ctx.fs.readFileSync(ctx.path.join(ctx.WORKFLOW_DIR, ".rdchat_token.json"), "utf-8")).token; } catch {}
    }

    const upstreamBody = Buffer.from(JSON.stringify({
      model: payload.model || b.llm_model,            // 前端指定的對話模型優先；否則退回 config 的 llm_model
      messages: payload.messages,
      stream: false,
      think: payload.think === true,                  // 預設 false（casual 台詞不需 thinking → 快）
      options: payload.options || { num_predict: 64, temperature: 0.9 },
    }));

    const url = new URL(b.base_url.replace(/\/+$/, "") + "/api/chat");
    const isHttps = url.protocol === "https:";
    const mod = isHttps ? https : http;
    const headers = { "Content-Type": "application/json", "Content-Length": upstreamBody.length };
    if (token) headers["Authorization"] = "Bearer " + token;

    const opts = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname,
      method: "POST",
      headers,
      timeout: UPSTREAM_TIMEOUT_MS,
      rejectUnauthorized: false,
    };

    const up = mod.request(opts, (ur) => {
      let buf = "";
      ur.on("data", (d) => (buf += d));
      ur.on("end", () => {
        if (ur.statusCode !== 200) return ctx.jsonRes(res, 502, { error: "upstream " + ur.statusCode, detail: buf.slice(0, 300) });
        let j;
        try { j = JSON.parse(buf); } catch { return ctx.jsonRes(res, 502, { error: "upstream bad json" }); }
        ctx.jsonRes(res, 200, {
          content: (j.message && j.message.content) || "",
          eval_count: j.eval_count != null ? j.eval_count : null,
          total_ms: j.total_duration ? Math.round(j.total_duration / 1e6) : null,
        });
      });
    });
    up.on("error", (e) => ctx.jsonRes(res, 502, { error: "upstream error: " + e.message }));
    up.on("timeout", () => { up.destroy(); ctx.jsonRes(res, 504, { error: "upstream timeout" }); });
    up.write(upstreamBody);
    up.end();
  });
  req.on("error", () => { if (!aborted) ctx.jsonRes(res, 400, { error: "request error" }); });
}

module.exports = { handleCreatureChat, BACKEND_NAME };
