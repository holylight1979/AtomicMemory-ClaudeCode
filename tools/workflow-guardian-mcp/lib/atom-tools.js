// atom-tools.js — atom_write / atom_promote / atom_edit_meta / atom_move 四個 MCP tool 業務邏輯。
// sendToolResult 來自 mcp.js（循環相依：mcp.handleToolCall lazy-require 本檔，故本檔載入時 mcp 已就緒）。
const fs = require("fs");
const path = require("path");
const { CLAUDE_DIR, MEMORY_DIR, TOOLS_DIR, loadConfig } = require("./paths");
const { crashLog } = require("./log");
// 落點／定位／路由全部由 py lib/atom_io.locate_atom 裁決（spawnAtomCli("locate")），
// js 只採用回傳的路徑；realm.js 只剩 js 自己真的需要的（使用者名、去重層清單）。
const { getCurrentUser, dedupLayersFor } = require("./realm");

// SYNC: lib/atom_index_json.py TRIGGER_MAX_LEN — 超長 trigger 在寫入當下即拒，
// 不留給後續 validate_index / atom_move 才爆（exit 2）。
const TRIGGER_MAX_LEN = 30;
const { parseAtomMeta, readAtomAccess, spawnAtomAccess, usefulnessStats } = require("./atom-access");
const {
  execConflictDetector, appendMergeHistory, buildConflictReport, execWriteGate,
  appendToIndex, triggerVectorReindex, syncMemoryIndex, spawnAtomCli,
  funnelWriteRaw,
} = require("./funnel");
const { sendToolResult } = require("./mcp");

// ─── Atom Write Handler ────────────────────────────────────────────────────

async function toolAtomWrite(id, args) {
  let {
    title, scope, confidence, triggers, knowledge, actions, related, mode,
    project_cwd, skip_gate, skip_conflict_check,
    role, user, audience, pending_review_by, merge_strategy,
    realm, domain, status, subdir, allow_new_category, dry_run,
  } = args;
  dry_run = !!dry_run;

  // Validate core required fields (scope now optional, defaults to shared)
  if (!title || !confidence || !triggers || !knowledge || !mode) {
    return sendToolResult(id, "Missing required parameters (title, confidence, triggers, knowledge, mode)", true);
  }

  // trigger 長度寫入當下即驗（create/replace 會回寫索引 triggers；append 不動）。
  // [...t] 以 code point 計長，對拍 py len()。
  if ((mode === "create" || mode === "replace") && Array.isArray(triggers)) {
    const tooLong = triggers.filter((t) => [...String(t)].length > TRIGGER_MAX_LEN);
    if (tooLong.length) {
      return sendToolResult(id,
        `trigger too long (>${TRIGGER_MAX_LEN} chars): ${tooLong.map(t => `"${t}"`).join(", ")}\n` +
        `Shorten the trigger — an over-limit trigger poisons every later validate_index run (atom_move exit 2).`,
        true);
    }
  }

  // V4: default scope, transparent legacy mapping
  if (!scope) scope = "shared";
  if (scope === "project") {
    try { process.stderr.write(`[atom_write] scope=project is deprecated; mapped to shared\n`); } catch {}
    scope = "shared";
  }

  // V4 personal default user
  if (scope === "personal" && !user) user = getCurrentUser();

  // Realm gate：專案專屬內容不得落 global——所有 mode（create/append/replace）都跑，
  // 且**不受 skip_gate 影響**（skip_gate 只跳品質/去重閘）。裁決在 py lib/realm_gate.py
  // 單源（專名從 cwd 的專案 root 機械化推導）；缺 project_cwd 時退用本 MCP 進程 cwd
  // （Claude Code 以 session cwd 啟動 stdio server）。cwd∈~/.claude → py 端不啟動。
  if (scope === "global") {
    const gateCwd = project_cwd || process.cwd();
    const rg = await spawnAtomCli("realm_check", {
      project_cwd: gateCwd, title, triggers, knowledge, actions, domain,
    });
    if (!rg.ok) return sendToolResult(id, `atom_write: ${rg.error}`, true);
  }

  // 落點／定位／路由一律問 py 一次（lib/atom_io.locate_atom 單一裁決者）：cwd-scope 防護、
  // 範疇閘（缺 domain 拒寫並列 Lv1）、feedback-* 失敗家族、local realm 自動分類、subdir
  // 沙盒、敏感 audience → _pending_review、分隔符變體撞名、既有檔定位（含子夾）。
  // js 不自算任何路徑，只採用 target_dir / index_dir / index_root / rel_path。
  const lr0 = await spawnAtomCli("locate", {
    title, scope, project_cwd, role, user, audience, realm, domain, triggers,
    subdir, mode, allow_new_category: !!allow_new_category, enforce_cwd_scope: true,
  });
  if (!lr0.ok) return sendToolResult(id, `atom_write: ${lr0.error}`, true);
  const loc = lr0.extra || {};
  const slug = loc.slug;
  const baseDir = loc.base_dir, indexDir = loc.index_dir, indexRoot = loc.index_root;
  const scopeLabel = loc.scope_label;
  const category = loc.category || null;
  const existingPath = lr0.path || null;
  if (Array.isArray(loc.auto_realm) && loc.auto_realm.length) {
    realm = "local";
    domain = loc.domain;
    try { process.stderr.write(
      `[atom_write] auto-realm: ${slug} → local/${domain} (matched: ${loc.auto_realm.join(",")})\n`); } catch {}
  }
  let pendingReviewBy = pending_review_by || null;
  if (loc.routed_to_pending && !pendingReviewBy) pendingReviewBy = "management";

  // memDir/filePath/relPath 可能在 conflict-detector reroute 後重算
  let memDir = loc.target_dir;
  let filePath = existingPath || path.join(memDir, slug + ".md");
  let relPath = existingPath ? loc.rel_path : loc.create_rel_path;

  const author = getCurrentUser();
  const today = new Date().toISOString().slice(0, 10);

  // ── Mode: create ──
  if (mode === "create") {
    // 既有檔（含子夾／local／失敗家族）與分隔符變體撞名皆由 py locate 判定
    if (existingPath || fs.existsSync(filePath)) {
      return sendToolResult(id,
        `Atom already exists: ${existingPath || filePath} — use mode=append or mode=replace`, true);
    }
    fs.mkdirSync(memDir, { recursive: true });

    // 原子記憶語意契約：新 atom 必須 [臨]
    if (confidence !== "[臨]") {
      return sendToolResult(id,
        `New atom must start at [臨] (confidence=${confidence} rejected).\n` +
        `Reason: [觀]/[固] reflect cross-session stability; first-write cannot assert that.\n` +
        `Knowledge items inside should also use [臨] prefix.\n` +
        `Promotion: Confirmations (cross-session) ≥4→[觀] ≥10→[固], OR usefulness Wilson lower-bound ≥ promote_lb (n≥min_n). ReadHits is exposure-only, not a promotion gate.`,
        true);
    }

    let gateWarnings = [];
    if (!skip_gate) {
      // 去重只比「寫入者能 append 到」的層：global + ~/.claude 本地 atom + 當前專案
      // 自己的 shared／role／personal。不限層會撞到別的專案、別人 personal 的 atom。
      const gateLayers = dedupLayersFor(scope, baseDir, { role, user });
      const gateResult = await execWriteGate(knowledge.join("\n"), confidence, gateLayers);
      if (gateResult.action === "skip") {
        return sendToolResult(id, `Write-gate rejected: ${gateResult.reason}`, true);
      }
      if (gateResult.action === "update" && gateResult.dedup_match) {
        return sendToolResult(id,
          `Write-gate: similar to existing atom "${gateResult.dedup_match.atom_name}" ` +
          `(score=${gateResult.dedup_match.score}, searched layers: ${gateLayers.join(", ")}). ` +
          `Use mode=append on that atom instead.`, true);
      }
      // 樣式軟警（逐筆表格/路徑清單）：不擋，附在成功訊息尾端轉述給寫入者
      if (Array.isArray(gateResult.warnings) && gateResult.warnings.length) {
        gateWarnings = gateResult.warnings;
      }
    }

    // ─── write-time conflict detection (SPEC §7.1) ───
    // Only shared scope. skip_conflict_check honored for migrations/tests.
    // dry_run 跳過：偵測器會落 .conflict.md 報告／_pending_review 草稿（副作用），預覽不該留痕。
    if (scope === "shared" && !skip_conflict_check && !dry_run) {
      const cr = await execConflictDetector(knowledge.join("\n"), "shared", project_cwd, subdir);
      // 偵測器降級訊號（複驗不穩 / 跨分區 / LLM ERROR fail-open）→ 併入成功訊息浮出
      if (Array.isArray(cr.warnings) && cr.warnings.length) {
        gateWarnings = gateWarnings.concat(cr.warnings.map(w => `[conflict-detector] ${w}`));
      }
      if (cr.verdict === "contradict") {
        const pendingDir = path.join(baseDir, "shared", "_pending_review");
        fs.mkdirSync(pendingDir, { recursive: true });
        const reportPath = path.join(pendingDir, slug + ".conflict.md");
        const report = buildConflictReport({
          slug, incomingTitle: title, incomingContent: knowledge.join("\n"),
          matches: cr.matches, detectorModel: cr.detector_model, author,
        });
        fs.writeFileSync(reportPath + ".tmp", report, "utf-8");
        fs.renameSync(reportPath + ".tmp", reportPath);
        appendMergeHistory(baseDir, "pending-create", slug, scopeLabel, author,
          `contradict vs ${(cr.matches[0] || {}).atom_name || "?"} sim=${((cr.matches[0] || {}).similarity || 0).toFixed(3)}`);
        return sendToolResult(id,
          `BLOCKED by conflict detector — CONTRADICT (double-confirmed) vs "${(cr.matches[0] || {}).atom_name || "?"}".\n` +
          `Report written: ${reportPath}\n` +
          `Atom NOT written to shared/. 待審出路：/conflict pending 檢視 → approve/reject\n` +
          `（後端 tools/conflict-review.py --list / --action approve|reject --target <name> --project-cwd <root>）`,
          false  // not isError — pending is normal flow
        );
      }
      if (cr.verdict === "extend_overlap") {
        // Reroute to _pending_review/ as atom draft (still full atom format)
        memDir = path.join(baseDir, "shared", "_pending_review");
        fs.mkdirSync(memDir, { recursive: true });
        if (!pendingReviewBy) pendingReviewBy = "management";
        filePath = path.join(memDir, slug + ".md");
        relPath = path.relative(indexRoot, filePath).replace(/\\/g, "/");
        appendMergeHistory(baseDir, "pending-create", slug, scopeLabel, author,
          `extend_overlap vs ${(cr.matches[0] || {}).atom_name || "?"} sim=${((cr.matches[0] || {}).similarity || 0).toFixed(3)}`);
      }
    }

    // create funnel 併單一 spawn（lib.atom_io_cli create_atom）：內容構造 build+validate →
    // write_raw → access.json(init + set last_used) → write_index，一次 Python 冷啟跑完整條
    // 管線。落檔 .md / .access.json / index byte-identical（守 verify_atom_io_equivalence
    // 對拍）。build/validate/write_raw 失敗致命；index 失敗非致命（crashLog-only）。
    const cr = await spawnAtomCli("create_atom", {
      build: {
        title, scope: scopeLabel, confidence, triggers, knowledge, actions, related,
        audience, author, pending_review_by: pendingReviewBy, merge_strategy, created_at: today,
        status,
      },
      file_path: filePath,
      today,
      // index scope 傳 scopeLabel（與 frontmatter 一致）——不再由 py 端預設 global
      // 蹍掉專案層 scope。
      index: { base_dir: indexDir, slug, rel_path: relPath, triggers, scope: scopeLabel },
      dry_run,
    });
    if (!cr.ok) {
      return sendToolResult(id, `atom_create funnel failed: ${cr.error}`, true);
    }
    if (dry_run) {
      return sendToolResult(id,
        `DRY-RUN (nothing written): would create atom ${slug}.md (${confidence}, scope=${scopeLabel})\n` +
        `Path: ${filePath}\n` +
        (category ? `Category: ${category}\n` : "") +
        `Index rel_path: ${relPath}\n` +
        `Gates passed: domain/category, [臨], write-gate, build+validate, budget.` +
        (gateWarnings.length ? `\n[write-gate 樣式警告] ${gateWarnings.join("；")}` : "")
      );
    }
    if (cr.extra && cr.extra.index_ok === false) {
      crashLog("appendToIndex funnel (json)", cr.extra.index_error);
    }
    triggerVectorReindex();
    // catalog 同步：global → memory/MEMORY.md（+側檔/各層 _INDEX.md）；shared → 該專案
    // MEMORY.md 的 marker 區塊（--memory-dir）。待審（_pending_review）不入 index → 不觸發。
    if (scopeLabel === "global") syncMemoryIndex();
    else if (scope === "shared" && !pendingReviewBy) syncMemoryIndex(baseDir);

    return sendToolResult(id,
      `Created atom: ${slug}.md (${confidence}, scope=${scopeLabel})\n` +
      `Path: ${filePath}\n` +
      (category ? `Category: ${category}\n` : "") +
      `Author: ${author}\n` +
      (pendingReviewBy ? `Pending-review-by: ${pendingReviewBy} (sensitive audience auto-routed)\n` : "") +
      `Triggers: ${triggers.join(", ")}\n` +
      `MEMORY.md index updated.` +
      (gateWarnings.length ? `\n[write-gate 樣式警告] ${gateWarnings.join("；")}` : "")
    );
  }

  // ── Mode: append ──
  if (mode === "append") {
    // 既有檔定位（扁平舊址／子夾／local／失敗家族）已由 py locate 一次做完
    if (!existingPath || !fs.existsSync(filePath)) {
      return sendToolResult(id, `Atom not found: ${slug}.md — use mode=create first`, true);
    }
    if (dry_run) {
      return sendToolResult(id,
        `DRY-RUN (nothing written): would append ${knowledge.length} knowledge line(s) to ${filePath}`);
    }

    // 拼接+validate+落檔統一 spawn py（lib.atom_io.append_atom_file）；不走 js readFileSync
    // 自拼 splice（CRLF 混寫面，見 lib/atom_io.py:_atomic_write 註解）。
    // Last-used 不在 .md，append 後改寫 access.json（下方 spawnAtomAccess）。
    const wr = await spawnAtomCli("append", { file_path: filePath, knowledge, source: "mcp" });
    if (!wr.ok) {
      return sendToolResult(id, `funnel append failed: ${wr.error}`, true);
    }

    // 同步刷 access.json last_used
    await spawnAtomAccess("set", [filePath, "--field", "last_used",
                                  "--value", today, "--source", "mcp"]);

    triggerVectorReindex();

    return sendToolResult(id,
      `Appended ${knowledge.length} knowledge lines to ${slug}.md\n` +
      `Last-used updated.`
    );
  }

  // ── Mode: replace ──
  if (mode === "replace") {
    // Guard: replace = overwrite an EXISTING atom. If the target is absent, this was a
    // silent upsert that birthed a brand-new atom bypassing the create [臨] gate. Refuse.
    // 定位（含分隔符變體提示）由 py locate 回。
    if (!existingPath || !fs.existsSync(filePath)) {
      const variant = loc.separator_variant || null;
      return sendToolResult(id,
        `Atom not found: ${slug}.md — mode=replace requires an existing atom.\n` +
        (variant
          ? `(A separator-variant "${variant}" exists — rename it to "${slug}.md" first, or append to it.)\n`
          : "") +
        `To add a NEW atom use mode=create (new atoms must start at [臨]).`,
        true);
    }
    // Confirmations / ReadHits 在 access.json，replace 不需保留（檔本就分離）
    // 仍保留 Author / Created-at（屬知識性 metadata）
    let prevAuthor = author;
    let prevCreatedAt = today;
    if (fs.existsSync(filePath)) {
      try {
        const old = fs.readFileSync(filePath, "utf-8");
        const am = old.match(/^- Author:\s*(.+)$/m);
        if (am) prevAuthor = am[1].trim();
        const cm = old.match(/^- Created-at:\s*(.+)$/m);
        if (cm) prevCreatedAt = cm[1].trim();
      } catch {}
    }

    // 同 create，內容構造 spawn py funnel "build"（含 validate）
    const br = await spawnAtomCli("build", {
      title, scope: scopeLabel, confidence, triggers, knowledge, actions, related,
      audience, author: prevAuthor, pending_review_by: pendingReviewBy,
      merge_strategy, created_at: prevCreatedAt, status,
    });
    if (!br.ok) {
      return sendToolResult(id, `Validation failed: ${br.error}`, true);
    }
    const content = (br.extra || {}).content;
    if (dry_run) {
      return sendToolResult(id,
        `DRY-RUN (nothing written): would replace ${filePath} (build+validate passed; ` +
        `author=${prevAuthor}, created-at=${prevCreatedAt} preserved)`);
    }

    fs.mkdirSync(memDir, { recursive: true });
    // 走 lib.atom_io.write_raw funnel
    const wr = await funnelWriteRaw(filePath, content, "mcp", "atom_replace");
    if (!wr.ok) {
      return sendToolResult(id, `funnel write_raw failed: ${wr.error}`, true);
    }

    // 刷 access.json last_used（access 計數自動保留）
    await spawnAtomAccess("set", [filePath, "--field", "last_used",
                                  "--value", today, "--source", "mcp"]);

    await appendToIndex(indexDir, slug, relPath, triggers);
    triggerVectorReindex();
    if (scopeLabel === "global") syncMemoryIndex();
    else if (scope === "shared" && !pendingReviewBy) syncMemoryIndex(baseDir);

    // 讀 access 給訊息顯示保留的計數
    const accAfter = readAtomAccess(filePath);
    return sendToolResult(id,
      `Replaced atom: ${slug}.md (${confidence}, preserved conf=${accAfter.confirmations || 0} rh=${accAfter.readhits || 0}, author=${prevAuthor})\n` +
      `MEMORY.md index updated.`
    );
  }

  return sendToolResult(id, `Unknown mode: ${mode}. Use create/append/replace.`, true);
}

// ─── Atom Promote Handler ──────────────────────────────────────────────────

// Locate <atom_name>.md anywhere under memDir; needed because feedback/ etc.
// are valid atom subdirs (mirrors lib/atom_spec.SKIP_DIRS exclusions).
/** 依 atom 名定位既有檔（promote / edit_meta 用）：全交 py locate（global 三址：memory/、
 *  memory/Failures/、_AIDocs/_atoms/；專案層依 scope 子層）。scope=project（舊語意＝
 *  整個專案 memory 根）依序試 shared → personal(現用者) → role(若給)，不悄悄跨層。
 *  回 {path|null, error?}。 */
async function locateByName(atomName, scope, projectCwd, { role, user } = {}) {
  const tryScope = async (sc, extra = {}) => {
    const lr = await spawnAtomCli("locate", {
      title: atomName, scope: sc, project_cwd: projectCwd, ...extra,
    });
    if (!lr.ok) return { error: lr.error };
    return { path: lr.path || null };
  };
  if (scope === "project") {
    const attempts = [
      ["shared", {}],
      ["personal", { user: user || getCurrentUser() }],
    ];
    if (role) attempts.push(["role", { role }]);
    let lastErr = null;
    for (const [sc, extra] of attempts) {
      const r = await tryScope(sc, extra);
      if (r.path) return r;
      if (r.error) lastErr = r.error;
    }
    return lastErr ? { error: lastErr } : { path: null };
  }
  if (scope === "personal" && !user) user = getCurrentUser();
  return tryScope(scope, { role, user });
}

/** Spawn inline python → lib.atom_index_json.delete_atom（含 _ATOM_INDEX.md mirror
 *  自動 regenerate）。沿用 spawnEditMetadata 慣例：cwd=CLAUDE_DIR、PYTHONIOENCODING、
 *  windowsHide、30s timeout。Returns Promise<{ok, removed?, error?}>。 */
function spawnIndexDelete(memDir, atomName) {
  const inline = [
    "import sys, json",
    "from pathlib import Path",
    "from lib.atom_index_json import delete_atom",
    "removed = delete_atom(Path(sys.argv[1]), sys.argv[2])",
    "print(json.dumps({'ok': True, 'removed': removed}))",
  ].join("\n");
  return new Promise((resolve) => {
    let cp;
    try {
      cp = require("child_process").spawn(
        "python", ["-c", inline, memDir, atomName],
        { cwd: CLAUDE_DIR, windowsHide: true,
          env: { ...process.env, PYTHONIOENCODING: "utf-8" } },
      );
    } catch (e) {
      return resolve({ ok: false, error: `spawn failed: ${e.message}` });
    }
    let out = "", err = "", timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      try { cp.kill(); } catch {}
    }, 30000);
    cp.stdout.on("data", (d) => { out += d.toString("utf-8"); });
    cp.stderr.on("data", (d) => { err += d.toString("utf-8"); });
    cp.on("close", () => {
      clearTimeout(timer);
      if (timedOut) return resolve({ ok: false, error: "index delete timeout (30s), killed" });
      try {
        resolve(JSON.parse(out.trim()));
      } catch (e) {
        resolve({ ok: false, error: `parse fail: ${e.message} stderr=${err.slice(0, 200)}` });
      }
    });
    cp.on("error", (e) => {
      clearTimeout(timer);
      resolve({ ok: false, error: `spawn error: ${e.message}` });
    });
  });
}

async function toolAtomPromote(id, args) {
  const { atom_name, scope, project_cwd, execute, role, user, merge_to_preferences } = args;

  const located = await locateByName(atom_name, scope, project_cwd, { role, user });
  if (located.error) return sendToolResult(id, `atom_promote: ${located.error}`, true);
  if (!located.path) {
    return sendToolResult(id, `Atom not found: ${atom_name}.md in ${scope} scope`, true);
  }
  let filePath = located.path;

  let content = fs.readFileSync(filePath, "utf-8");
  if (content.charCodeAt(0) === 0xFEFF) content = content.slice(1);

  const meta = parseAtomMeta(content);
  if (!meta.confidence) {
    return sendToolResult(id, `Cannot parse confidence from ${atom_name}.md`, true);
  }

  // Determine promotion path (v3 dual-field)
  // SYNC: memory/decisions.md — promotion thresholds
  const THRESHOLDS = {
    "[臨]": { next: "[觀]", confirmations: 4, readhits: 20 },
    "[觀]": { next: "[固]", confirmations: 10, readhits: 50 },
    "[固]": null, // already max
  };

  const path_info = THRESHOLDS[meta.confidence];
  if (!path_info) {
    return sendToolResult(id,
      `${atom_name} is already at ${meta.confidence} — no promotion available.`
    );
  }

  const { next, confirmations: reqConf, readhits: reqRH } = path_info;
  // 計數從 <atom>.access.json 讀，不走 parseAtomMeta（meta.confidence 仍從 .md 抽）
  const access = readAtomAccess(filePath);
  const confirmations = access.confirmations || 0;
  const readhits = access.readhits || 0;

  // 晉升 = 真實 Confirmations 主軌 OR 效用 Wilson 下界。
  // ReadHits 為純曝光計數，不參與晉升。
  // SYNC: lib/atom_access.py usefulness_promote_eligible + wg_atoms.py:_self_iterate_atoms。
  const uconf = (loadConfig().usefulness) || {};
  const promoteLb = Number(uconf.promote_lb != null ? uconf.promote_lb : 0.6);
  const minN = Number(uconf.min_n != null ? uconf.min_n : 3);
  const wilsonZ = Number(uconf.wilson_z != null ? uconf.wilson_z : 1.28);
  const ustat = usefulnessStats(access, wilsonZ);
  const utilEligible = ustat.n >= minN && ustat.lowerBound >= promoteLb;

  let eligible = confirmations >= reqConf;
  let method = "confirmations";
  if (!eligible && utilEligible) {
    eligible = true;
    method = "usefulness";
  }

  const utilLine =
    `  Usefulness: lb=${ustat.lowerBound.toFixed(3)} (α=${ustat.alpha}, β=${ustat.beta}, n=${ustat.n})` +
    ` — need lb≥${promoteLb} & n≥${minN}\n`;

  if (!eligible) {
    return sendToolResult(id,
      `## Dry-run: ${atom_name}\n` +
      `Current: ${meta.confidence}\n` +
      `  Confirmations: ${confirmations}/${reqConf}\n` +
      utilLine +
      `  ReadHits: ${readhits} (純曝光，不參與晉升)\n` +
      `Required: Confirmations ≥ ${reqConf} OR (Usefulness lb ≥ ${promoteLb} AND n ≥ ${minN})\n` +
      `Deficit: ${Math.max(0, reqConf - confirmations)} conf / lb ${Math.max(0, promoteLb - ustat.lowerBound).toFixed(3)}`
    );
  }

  // Eligible for promotion
  if (!execute) {
    return sendToolResult(id,
      `## Dry-run: ${atom_name}\n` +
      `Current: ${meta.confidence}\n` +
      `  Confirmations: ${confirmations}/${reqConf}\n` +
      utilLine +
      `Eligible via: ${method} → ${next}\n` +
      `Set execute=true to apply.`
    );
  }

  // Execute promotion
  // Last-used 不在 .md，只改 Confidence + 知識條目層級的 [臨]/[觀]
  const updated = content
    .replace(/^- Confidence:\s*.+$/m, `- Confidence: ${next}`);

  // Also update individual knowledge lines: [臨] → [觀] etc.
  // 只處理 ## 知識 段落內、行首（含縮排）的 `- [X]` 條目——全文全域替換會誤改
  // ## 行動 區與引文中出現的同字樣。段落邊界 = 下一個 `## ` 標題。
  // NB: .replace() 已把 [ ] 跳脫成 \[ \]；若再多寫 `\\` 前綴會產出未閉合字元類。
  const confLineRe = new RegExp(
    `^(\\s*- )${meta.confidence.replace(/[[\]]/g, "\\$&")}`);
  const outLines = updated.split("\n");
  let inKnowledge = false;
  for (let i = 0; i < outLines.length; i++) {
    if (/^## /.test(outLines[i])) {
      inKnowledge = /^## 知識/.test(outLines[i]);
      continue;
    }
    if (inKnowledge) outLines[i] = outLines[i].replace(confLineRe, `$1${next}`);
  }
  const finalContent = outLines.join("\n");

  // 走 lib.atom_io.write_raw funnel
  const wrPromote = await funnelWriteRaw(filePath, finalContent, "mcp", "atom_promote");
  if (!wrPromote.ok) {
    return sendToolResult(id, `funnel write_raw failed: ${wrPromote.error}`, true);
  }

  // 同步寫 access.json 的 last_promoted_at + last_used
  await spawnAtomAccess("record-promotion",
    [filePath, "--target", next, "--source", "mcp"]);

  triggerVectorReindex();

  // Promotion audit log
  try {
    const auditPath = path.join(MEMORY_DIR, "_promotion_audit.jsonl");
    const entry = {
      ts: new Date().toISOString().slice(0, 19),
      action: "manual_promote",
      atom: atom_name,
      from: meta.confidence,
      to: next,
      confirmations,
      readhits,
      method,
      scope,
    };
    fs.appendFileSync(auditPath, JSON.stringify(entry) + "\n");
  } catch {}

  // ─── [觀]→[固] 合併流程 ────────────────────────────────
  // 自動提示：只要晉升為 [固]，一律在回覆裡附上「是否合進 preferences.md」提示，
  // 讓 Claude 引導使用者裁決。
  // 自動執行：當 merge_to_preferences=true，立即把 knowledge 追加到 preferences.md、
  // 歸檔本 atom（含 .access.json sidecar）到 _archived/，並從 _atom_index.json
  // 移除條目（mirror 自動 regenerate）。
  const promotedToStable = next === "[固]";
  let mergeReport = "";
  if (promotedToStable && merge_to_preferences) {
    if (scope !== "global") {
      mergeReport = "\n\n[merge_to_preferences] 已略過：僅支援 global scope。";
    } else {
      try {
        const knowledgeLines = extractKnowledgeLines(finalContent);
        const prefPath = path.join(MEMORY_DIR, "preferences.md");
        const archiveDir = path.join(MEMORY_DIR, "_archived");
        if (!fs.existsSync(archiveDir)) fs.mkdirSync(archiveDir, { recursive: true });
        const today = new Date().toISOString().slice(0, 10);
        const archivePath = path.join(archiveDir, `${today}-${atom_name}.md`);

        let prefText = fs.existsSync(prefPath) ? fs.readFileSync(prefPath, "utf-8") : "";
        if (prefText.charCodeAt(0) === 0xFEFF) prefText = prefText.slice(1);
        const mergeSection =
          `\n\n### 歸檔合併 · ${atom_name} (${today})\n` +
          `> 自 [觀]→[固] 晉升時合併自 \`${path.basename(filePath)}\`\n\n` +
          knowledgeLines.map(l => `- ${l}`).join("\n") + "\n";
        // 走 lib.atom_io.write_raw funnel
        const wrPref = await funnelWriteRaw(
          prefPath, prefText.trimEnd() + mergeSection, "mcp", "promote_merge_pref"
        );
        if (!wrPref.ok) throw new Error(`funnel write_raw failed: ${wrPref.error}`);

        fs.renameSync(filePath, archivePath);
        // 同步歸檔 .access.json sidecar（遙測跟著 atom 走，不留孤兒）
        const accSrc = filePath.replace(/\.md$/, ".access.json");
        let accMoved = false;
        if (fs.existsSync(accSrc)) {
          fs.renameSync(accSrc, archivePath.replace(/\.md$/, ".access.json"));
          accMoved = true;
        }

        // 從 _atom_index.json（SoT）移除條目；mirror _ATOM_INDEX.md 由
        // lib.atom_index_json.delete_atom 自動 regenerate。
        const idxDel = await spawnIndexDelete(MEMORY_DIR, atom_name);
        let idxLine;
        if (idxDel.ok) {
          idxLine = idxDel.removed
            ? `  - Removed ${atom_name} from _atom_index.json (+mirror regenerated)`
            : `  - Index entry ${atom_name} not found in _atom_index.json（無需移除）`;
        } else {
          crashLog("merge_to_preferences index delete", idxDel.error);
          idxLine = `  - ⚠ 索引移除失敗（${idxDel.error}）— 請手動清 _atom_index.json 的 ${atom_name} 條目`;
        }

        mergeReport =
          `\n\n[merge_to_preferences] 已執行：\n` +
          `  - Appended ${knowledgeLines.length} 行到 preferences.md\n` +
          `  - Archived → ${path.relative(MEMORY_DIR, archivePath)}` +
          (accMoved ? "（含 .access.json sidecar）" : "") + `\n` +
          idxLine;
      } catch (e) {
        mergeReport = `\n\n[merge_to_preferences] 失敗：${e.message}`;
      }
    }
  }

  const mergeHint = (promotedToStable && !merge_to_preferences)
    ? `\n\n💡 建議：${atom_name} 已達 [固]，若此知識本質為「個人偏好/操作規範」，` +
      `可用 merge_to_preferences=true 重新呼叫，將 knowledge 併入 preferences.md 並歸檔此 atom。`
    : "";

  return sendToolResult(id,
    `Promoted ${atom_name}: ${meta.confidence} → ${next}\n` +
    `Confirmations: ${confirmations} | ReadHits: ${readhits} (via ${method})\n` +
    `Knowledge lines updated to ${next}.` +
    mergeReport +
    mergeHint
  );
}

// ─── Atom Edit-Metadata Handler ────────────────────────────────────────────

/** Spawn inline python that calls lib.atom_io.edit_metadata through the funnel.
 *  list 參數 (triggers/related/tags) 以單一 JSON 字串走 argv 傳入，python 端
 *  json.loads 後展開。沿用 spawnAtomCli/spawnAtomAccess 慣例：cwd=CLAUDE_DIR、
 *  PYTHONIOENCODING=utf-8、windowsHide。回傳 Promise<WriteResult.to_dict()>。
 */
function spawnEditMetadata(filePath, fields) {
  // fields: { triggers?: string[], related?: string[], tags?: string[] }
  const payload = JSON.stringify({ file_path: filePath, ...fields });
  const inline = [
    "import sys, json",
    "from lib.atom_io import edit_metadata",
    "p = json.loads(sys.argv[1])",
    "r = edit_metadata(",
    "    p['file_path'],",
    "    triggers=p.get('triggers'),",
    "    related=p.get('related'),",
    "    tags=p.get('tags'),",
    "    source='mcp',",
    ")",
    "print(json.dumps(r.to_dict(), ensure_ascii=False))",
  ].join("\n");
  return new Promise((resolve) => {
    let cp;
    try {
      cp = require("child_process").spawn(
        "python", ["-c", inline, payload],
        {
          cwd: CLAUDE_DIR,
          windowsHide: true,
          env: { ...process.env, PYTHONIOENCODING: "utf-8" },
        }
      );
    } catch (e) {
      return resolve({ ok: false, error: `spawn failed: ${e.message}` });
    }
    let out = "", err = "", timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      try { cp.kill(); } catch {}
    }, 30000);
    cp.stdout.on("data", (d) => { out += d.toString("utf-8"); });
    cp.stderr.on("data", (d) => { err += d.toString("utf-8"); });
    cp.on("close", () => {
      clearTimeout(timer);
      if (timedOut) return resolve({ ok: false, error: "edit_metadata timeout (30s), killed" });
      try {
        resolve(JSON.parse(out.trim()));
      } catch (e) {
        resolve({ ok: false, error: `cli parse fail: ${e.message} stderr=${err.slice(0, 300)}` });
      }
    });
    cp.on("error", (e) => {
      clearTimeout(timer);
      resolve({ ok: false, error: `spawn error: ${e.message}` });
    });
  });
}

async function toolAtomEditMeta(id, args) {
  const { atom_name, scope, project_cwd, role, user, triggers, related, tags } = args;

  if (!atom_name || !scope) {
    return sendToolResult(id, "atom_edit_meta: atom_name and scope are required", true);
  }

  // At least one metadata field must be provided.
  const fields = {};
  const changed = [];
  if (Array.isArray(triggers)) { fields.triggers = triggers; changed.push("trigger"); }
  if (Array.isArray(related))  { fields.related = related;   changed.push("related"); }
  if (Array.isArray(tags))     { fields.tags = tags;         changed.push("tags"); }
  if (changed.length === 0) {
    return sendToolResult(id,
      "atom_edit_meta: at least one of triggers / related / tags must be provided (array of string).",
      true);
  }

  // 定位同 toolAtomPromote：py locate 單一裁決（global 三址／專案 shared→personal→role）。
  const located = await locateByName(atom_name, scope, project_cwd, { role, user });
  if (located.error) return sendToolResult(id, `atom_edit_meta: ${located.error}`, true);
  if (!located.path) {
    return sendToolResult(id, `Atom not found: ${atom_name}.md in ${scope} scope`, true);
  }
  const filePath = located.path;

  const result = await spawnEditMetadata(filePath, fields);
  if (!result.ok) {
    return sendToolResult(id, `atom_edit_meta failed: ${result.error || "(unknown error)"}`, true);
  }

  triggerVectorReindex();

  return sendToolResult(id,
    `Edited metadata for ${atom_name}.md (fields: ${changed.join(", ")})\n` +
    `audit_id: ${result.audit_id || "(none)"}`
  );
}

// ─── Atom Move Handler ─────────────────────────────────────────────────────

function toolAtomMove(id, args) {
  const { subcommand, atom, dry_run } = args;
  if (!subcommand || !atom) {
    return Promise.resolve(sendToolResult(id, "atom_move: subcommand and atom are required", true));
  }
  const scriptPath = path.join(TOOLS_DIR, "atom-move.py");
  if (!fs.existsSync(scriptPath)) {
    return Promise.resolve(sendToolResult(id, `atom_move: script not found at ${scriptPath}`, true));
  }
  const argv = [scriptPath, subcommand, atom];
  if (subcommand === "move") {
    if (!args.from || !args.to) {
      return Promise.resolve(sendToolResult(id, "atom_move move: --from and --to required", true));
    }
    argv.push("--from", args.from, "--to", args.to);
    // scope 預設沿用索引既有值；明給才覆寫（atom-move.py --scope）
    if (args.scope) argv.push("--scope", args.scope);
  } else if (subcommand === "reconcile") {
    if (!args.at) {
      return Promise.resolve(sendToolResult(id, "atom_move reconcile: --at required", true));
    }
    argv.push("--at", args.at);
  } else {
    return Promise.resolve(sendToolResult(id, `atom_move: unknown subcommand '${subcommand}'`, true));
  }
  if (dry_run) argv.push("--dry-run");

  return new Promise((resolve) => {
    const cp = require("child_process").spawn("python", argv, { windowsHide: true });
    let out = "", err = "";
    const timer = setTimeout(() => { try { cp.kill(); } catch {} }, 30000);
    cp.stdout.on("data", d => { out += d.toString(); });
    cp.stderr.on("data", d => { err += d.toString(); });
    cp.on("close", (code) => {
      clearTimeout(timer);
      const combined = (out || "") + (err ? ("\n[stderr]\n" + err) : "");
      if (code !== 0) {
        sendToolResult(id, `atom_move exited ${code}\n${combined}`, true);
      } else {
        // 本次操作結果與「索引既有問題」分開講：exit 0 = 本次成功；
        // index_preexisting_issues 是搬移前就存在的 validate 錯誤（非本次造成），只轉述。
        sendToolResult(id, formatAtomMoveReport(combined));
      }
      resolve();
    });
    cp.on("error", (e) => {
      clearTimeout(timer);
      sendToolResult(id, `atom_move spawn error: ${e.message}`, true);
      resolve();
    });
  });
}

/** atom-move.py 的 JSON 報告 → 人讀摘要（成功行 + 既有索引問題另段）+ 原始 JSON。
 *  非 JSON 輸出原樣回。 */
function formatAtomMoveReport(raw) {
  const text = (raw || "").trim();
  let rep;
  try { rep = JSON.parse(text.split("\n[stderr]\n")[0]); } catch { return text || "(no output)"; }
  if (!rep || typeof rep !== "object") return text;
  const lines = [];
  if (rep.noop) {
    lines.push(`atom_move: ${rep.msg || "no-op"}`);
  } else {
    const mode = rep.mode || "APPLIED";
    const dest = rep.to_rel || rep.rel || rep.to || "?";
    lines.push(`✅ atom_move ${mode}: ${rep.slug} → ${dest} (scope=${rep.scope}` +
      (rep.scope_changed ? ", scope changed" : "") + ")");
    if (rep.scope_header_synced) lines.push("  - 檔頭 `- Scope:` 已同步為索引 scope");
    if (rep.catalog_sync) {
      for (const [k, v] of Object.entries(rep.catalog_sync)) {
        lines.push(`  - catalog regen ${k}: ${v.ok ? "ok" : "FAILED " + (v.error || "")}`);
      }
    }
    if (Array.isArray(rep.warnings) && rep.warnings.length) {
      lines.push(`  - warnings: ${rep.warnings.join(" | ")}`);
    }
    const pre = rep.index_preexisting_issues || [];
    if (pre.length) {
      lines.push(`⚠ 索引既有問題 ${pre.length} 項（搬移前就存在、非本次造成；` +
        `修法：atom_edit_meta 縮短 trigger 或 tools/sync-atom-index.py --fix）：`);
      for (const e of pre) lines.push(`    - ${e}`);
    }
  }
  lines.push(text);
  return lines.join("\n");
}

function extractKnowledgeLines(content) {
  // 從 atom 檔抓「## 知識」到下個 `## ` 或 EOF 之間，保留以 `- ` 開頭的行（去掉 `- ` 前綴）
  const m = content.match(/^##\s*知識\s*$([\s\S]*?)(?=^##\s|\Z)/m);
  if (!m) return [];
  return m[1]
    .split("\n")
    .map(l => l.trim())
    .filter(l => l.startsWith("- "))
    .map(l => l.slice(2).trim())
    .filter(Boolean);
}

module.exports = { toolAtomWrite, toolAtomPromote, toolAtomEditMeta, toolAtomMove };
