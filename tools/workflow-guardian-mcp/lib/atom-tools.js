// atom-tools.js — atom_write / atom_promote / atom_edit_meta / atom_move / atom_retire / memory_search / atom_source 七個 MCP tool 業務邏輯。
// sendToolResult 來自 mcp.js（循環相依：mcp.handleToolCall lazy-require 本檔，故本檔載入時 mcp 已就緒）。
// atom_write／atom_retire 每次落檔成功，結果文字最後一行固定 `receipt: {...}`（機器可讀收據）；
// Python PostToolUse 解析進 state.atom_ops，knowledge_harvest_report 的逐項核對以它為準（one-writer：本檔不寫 state）。
const fs = require("fs");
const path = require("path");
const { CLAUDE_DIR, MEMORY_DIR, TOOLS_DIR, loadConfig, PYTHON_EXE } = require("./paths");
const { crashLog } = require("./log");
// 落點／定位／路由全部由 py lib/atom_io.locate_atom 裁決（spawnAtomCli("locate")），
// js 只採用回傳的路徑；realm.js 只剩 js 自己真的需要的（使用者名、去重層清單）。
const { getCurrentUser, dedupLayersFor, orgMemoryRoot } = require("./realm");

// SYNC: lib/atom_index_json.py TRIGGER_MAX_LEN — 超長 trigger 在寫入當下即拒，
// 不留給後續 validate_index / atom_move 才爆（exit 2）。
const TRIGGER_MAX_LEN = 30;
const { parseAtomMeta, readAtomAccess, spawnAtomAccess, usefulnessStats } = require("./atom-access");
const {
  execConflictDetector, appendMergeHistory, buildConflictReport, execWriteGate,
  triggerVectorReindex, syncMemoryIndex, spawnAtomCli,
  funnelWriteRaw,
} = require("./funnel");
const { sendToolResult } = require("./mcp");

/** receipt 行：固定格式 `receipt: {json}`，單行、鍵序固定，供 Python PostToolUse 以
 *  最後一行解析。path 一律是實際落點（conflict reroute 到 _pending_review 亦然）。 */
function receiptLine(obj) {
  return `receipt: ${JSON.stringify(obj)}`;
}

/** 從既有 atom 檔頭讀 `- Source:`（provenance）字串；無此行回 null。 */
function readSourceLine(content) {
  const m = content.match(/^- Source:\s*(.+)$/m);
  return m ? m[1].trim() : null;
}

/** 從既有 atom 檔頭讀 `- Quote:` 原句；無此行回 null。 */
function readQuoteLine(content) {
  const m = content.match(/^- Quote:\s*(.+)$/m);
  return m ? m[1].trim() : null;
}

/** 從既有 atom 檔頭讀 `- Depends:` 清單；無此行回 null。 */
function readDependsLine(content) {
  const m = content.match(/^- Depends:\s*(.+)$/m);
  if (!m) return null;
  return m[1].split(",").map((s) => s.trim()).filter(Boolean);
}

/** 從既有 atom 檔頭讀 `- Supersedes:` 清單（replace 未給 supersedes 時保留原行用）；無此行回 null。 */
function readSupersedesLine(content) {
  const m = content.match(/^- Supersedes:\s*(.+)$/m);
  if (!m) return null;
  return m[1].split(",").map((s) => s.trim()).filter(Boolean);
}

// ─── Atom Write Handler ────────────────────────────────────────────────────

async function toolAtomWrite(id, args) {
  let {
    title, scope, confidence, triggers, knowledge, actions, related, mode,
    project_cwd, skip_gate, skip_conflict_check,
    role, user, audience, pending_review_by, merge_strategy,
    realm, domain, status, subdir, allow_new_category, dry_run, cross_project,
    supersedes, provenance, depends, quote,
  } = args;
  dry_run = !!dry_run;
  if (supersedes !== undefined && !Array.isArray(supersedes)) {
    return sendToolResult(id, "supersedes must be an array of atom names (omit to keep, [] to clear)", true);
  }
  if (depends !== undefined && !Array.isArray(depends)) {
    return sendToolResult(id, "depends must be an array of strings like path:<abs path> (omit to keep, [] to clear)", true);
  }
  if (provenance !== undefined && typeof provenance !== "string") {
    return sendToolResult(id, "provenance must be a string (source path / URL / commit)", true);
  }
  if (quote !== undefined && typeof quote !== "string") {
    return sendToolResult(id, "quote must be a string (single-line user quote, ≤200 chars)", true);
  }

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
  // org＝語法糖：公司層就是「orgMemoryRoot() 那個專案根」的 shared 層（py 落點零改）
  const isOrg = scope === "org";
  if (isOrg) {
    const orgRoot = orgMemoryRoot();
    if (!orgRoot) {
      return sendToolResult(id,
        "atom_write: scope=org 但這台機器尚未接上公司層記憶（org_memory）；" +
        "接上：python ~/.claude/tools/org-memory.py --join [<本機路徑>]", true);
    }
    scope = "shared";
    project_cwd = orgRoot;
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
    cross_project: !!cross_project,
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

  // Supersedes 自指在 js 先擋（slug 已知）；目標存在／循環／核心保護由 py build 單源裁決。
  if (Array.isArray(supersedes) && supersedes.includes(slug)) {
    return sendToolResult(id, `supersedes rejected: atom "${slug}" cannot supersede itself`, true);
  }

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
      const gateLayers = dedupLayersFor(isOrg ? "org" : scope, baseDir, { role, user, personalGlobal: !!loc.personal_global });
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
    // supersedes 只在呼叫者有給時才進 build kwargs（未給＝不帶鍵，py 輸出 byte 不變）。
    const cr = await spawnAtomCli("create_atom", {
      build: {
        title, scope: scopeLabel, confidence, triggers, knowledge, actions, related,
        audience, author, pending_review_by: pendingReviewBy, merge_strategy, created_at: today,
        status,
        ...(Array.isArray(supersedes) && { supersedes }),
        ...(typeof provenance === "string" && { provenance }),
        ...(typeof quote === "string" && { quote }),
        ...(Array.isArray(depends) && { depends }),
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
    if (scopeLabel === "global" || loc.personal_global) syncMemoryIndex();
    else if (scope === "shared" && !pendingReviewBy) syncMemoryIndex(baseDir);

    const crx = cr.extra || {};
    return sendToolResult(id,
      `Created atom: ${slug}.md (${confidence}, scope=${scopeLabel})\n` +
      `Path: ${filePath}\n` +
      (category ? `Category: ${category}\n` : "") +
      `Author: ${author}\n` +
      (pendingReviewBy ? `Pending-review-by: ${pendingReviewBy} (sensitive audience auto-routed)\n` : "") +
      `Triggers: ${triggers.join(", ")}\n` +
      `MEMORY.md index updated.` +
      (gateWarnings.length ? `\n[write-gate 樣式警告] ${gateWarnings.join("；")}` : "") +
      "\n" + receiptLine({
        op: "create", ok: true, atom: slug, path: filePath,
        index_ok: crx.index_ok !== false,
        supersedes: Array.isArray(crx.supersedes) ? crx.supersedes : (supersedes || []),
      })
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

    // append 不動索引 → index_ok 恆 true；supersedes 對 append 無意義，收據固定 []。
    return sendToolResult(id,
      `Appended ${knowledge.length} knowledge lines to ${slug}.md\n` +
      `Last-used updated.\n` +
      receiptLine({ op: "append", ok: true, atom: slug, path: filePath, index_ok: true, supersedes: [] })
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
    // Supersedes 三態：未給＝保留原行；[]＝清除；非空＝替換。
    let prevAuthor = author;
    let prevCreatedAt = today;
    let prevSupersedes = null;
    let prevProvenance = null;
    let prevQuote = null;
    let prevDepends = null;
    if (fs.existsSync(filePath)) {
      try {
        const old = fs.readFileSync(filePath, "utf-8");
        const am = old.match(/^- Author:\s*(.+)$/m);
        if (am) prevAuthor = am[1].trim();
        const cm = old.match(/^- Created-at:\s*(.+)$/m);
        if (cm) prevCreatedAt = cm[1].trim();
        prevSupersedes = readSupersedesLine(old);
        prevProvenance = readSourceLine(old);
        prevQuote = readQuoteLine(old);
        prevDepends = readDependsLine(old);
      } catch {}
    }
    // Source / Quote / Depends 三態同 Supersedes：未給＝保留原行；""／[]＝清除；非空＝替換。
    const provenanceFinal = typeof provenance === "string" ? provenance : prevProvenance;
    const quoteFinal = typeof quote === "string" ? quote : prevQuote;
    const dependsFinal = Array.isArray(depends) ? depends : prevDepends;
    const supersedesFinal = Array.isArray(supersedes) ? supersedes : (prevSupersedes || []);
    // 呼叫者明給新清單才重驗（自指／循環／核心保護／可解析，py 單源）；保留原行的不重驗，
    // 原行寫入當時已驗過，且其目標之後若被退役也不該讓這次 replace 失敗。
    if (Array.isArray(supersedes) && supersedes.length) {
      const sc = await spawnAtomCli("check_supersedes", {
        targets: supersedes, self_slug: slug, index_dir: indexDir, index_root: indexRoot,
      });
      if (!sc.ok) return sendToolResult(id, `supersedes rejected: ${sc.error}`, true);
    }

    // 同 create，內容構造 spawn py funnel "build"（含 validate）。supersedes 只在有值
    // （呼叫者給、或原檔有行）時進 kwargs，無則不帶鍵（輸出 byte 不變）。
    const br = await spawnAtomCli("build", {
      title, scope: scopeLabel, confidence, triggers, knowledge, actions, related,
      audience, author: prevAuthor, pending_review_by: pendingReviewBy,
      merge_strategy, created_at: prevCreatedAt, status,
      ...((Array.isArray(supersedes) || prevSupersedes) && { supersedes: supersedesFinal }),
      ...(provenanceFinal !== null && { provenance: provenanceFinal }),
      ...(quoteFinal !== null && { quote: quoteFinal }),
      ...(dependsFinal !== null && { depends: dependsFinal }),
    });
    if (!br.ok) {
      return sendToolResult(id, `Validation failed: ${br.error}`, true);
    }
    const content = (br.extra || {}).content;
    // 落檔用的是 py 正規化後的 slug 清單（build 回傳），receipt 與 dry-run 文字都用它，
    // 收割核對才對得上檔頭的 Supersedes 行。
    const canonSup = (br.extra || {}).supersedes;
    const supersedesOut = Array.isArray(canonSup) ? canonSup : supersedesFinal;
    if (dry_run) {
      return sendToolResult(id,
        `DRY-RUN (nothing written): would replace ${filePath} (build+validate passed; ` +
        `author=${prevAuthor}, created-at=${prevCreatedAt} preserved` +
        (Array.isArray(supersedes) ? `, supersedes=[${supersedesOut.join(", ")}]`
          : prevSupersedes ? `, supersedes kept=[${supersedesOut.join(", ")}]` : "") + ")");
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

    // 索引 upsert 直接走 funnel 取回 ok（receipt 要 index_ok；失敗非致命、crashLog 留訊號）
    const ir = await spawnAtomCli("write_index", {
      base_dir: indexDir, slug, rel_path: relPath, triggers, source: "mcp",
    });
    if (!ir.ok) crashLog("appendToIndex funnel (json)", ir.error);
    triggerVectorReindex();
    if (scopeLabel === "global" || loc.personal_global) syncMemoryIndex();
    else if (scope === "shared" && !pendingReviewBy) syncMemoryIndex(baseDir);

    // 讀 access 給訊息顯示保留的計數
    const accAfter = readAtomAccess(filePath);
    return sendToolResult(id,
      `Replaced atom: ${slug}.md (${confidence}, preserved conf=${accAfter.confirmations || 0} rh=${accAfter.readhits || 0}, author=${prevAuthor})\n` +
      `MEMORY.md index updated.\n` +
      receiptLine({ op: "replace", ok: true, atom: slug, path: filePath, index_ok: !!ir.ok, supersedes: supersedesOut })
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
        PYTHON_EXE, ["-c", inline, memDir, atomName],
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
        PYTHON_EXE, ["-c", inline, payload],
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
    const cp = require("child_process").spawn(PYTHON_EXE, argv, { windowsHide: true });
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

// ─── Atom Retire Handler ───────────────────────────────────────────────────

/** 退役：定位＋護欄＋索引/向量/搬移全由 py `atom_io_cli` action=retire 單源執行
 *  （locate → memory-audit.delete_atom(project_dir)）。js 只組 payload、轉述結果、
 *  附 receipt、專案層成功後刷該專案 MEMORY.md catalog。 */
async function toolAtomRetire(id, args) {
  let { atom_name, scope, project_cwd, role, user, reason, dry_run } = args;
  if (!atom_name || !scope) {
    return sendToolResult(id, "atom_retire: atom_name and scope are required", true);
  }
  if (!String(reason || "").trim()) {
    return sendToolResult(id, "atom_retire: reason is required (why this atom is retired)", true);
  }
  if (scope === "personal" && !user) user = getCurrentUser();
  if (scope === "org") {
    const orgRoot = orgMemoryRoot();
    if (!orgRoot) {
      return sendToolResult(id,
        "atom_retire: scope=org 但這台機器尚未接上公司層記憶（org_memory）；" +
        "接上：python ~/.claude/tools/org-memory.py --join [<本機路徑>]", true);
    }
    scope = "shared";
    project_cwd = orgRoot;
  }
  dry_run = !!dry_run;

  const r = await spawnAtomCli("retire", {
    atom_name, scope, project_cwd, role, user, reason, dry_run,
  });
  // py extra 契約：{op:"retire", atom, old_path, new_path, index_ok, steps_done:[], steps_failed:[]}
  // 缺欄位以已知值補齊（op/atom 由本側、path 取 r.path）。
  const ex = r.extra || {};
  const oldPath = ex.old_path || r.path || null;
  const newPath = ex.new_path || null;
  const stepsDone = Array.isArray(ex.steps_done) ? ex.steps_done : [];
  const stepsFailed = Array.isArray(ex.steps_failed) ? ex.steps_failed : [];

  if (!r.ok) {
    return sendToolResult(id,
      `atom_retire failed: ${r.error || "(unknown error)"}\n` +
      (stepsDone.length ? `steps done: ${stepsDone.join(", ")}\n` : "") +
      (stepsFailed.length ? `steps failed: ${stepsFailed.join(", ")}\n` : "") +
      receiptLine({ op: "retire", ok: false, atom: atom_name, old_path: oldPath,
                    steps_done: stepsDone, steps_failed: stepsFailed }),
      true);
  }
  if (dry_run) {
    return sendToolResult(id,
      `DRY-RUN (nothing changed): would retire ${atom_name}.md\n` +
      `From: ${oldPath}\n` + (newPath ? `To: ${newPath}\n` : "") +
      `Guards passed: [固] / core-protected / referenced-by.`);
  }

  triggerVectorReindex();
  // catalog 同步：global/local → memory/MEMORY.md；專案層 → 該專案 MEMORY.md marker 區塊。
  // 專案 memory 根優先取 py 回的 base_dir/index_root，否則依 project_cwd 組。
  if (scope === "global" || scope === "local") {
    syncMemoryIndex();
  } else {
    const memRoot = ex.base_dir || ex.index_root ||
      path.join(project_cwd || process.cwd(), ".claude", "memory");
    if (fs.existsSync(memRoot)) syncMemoryIndex(memRoot);
  }

  return sendToolResult(id,
    `Retired atom: ${atom_name}.md (scope=${scope})\n` +
    `From: ${oldPath}\n` +
    (newPath ? `To: ${newPath}（可還原：memory-audit --restore）\n` : "") +
    `Reason: ${reason}\n` +
    (stepsDone.length ? `Steps: ${stepsDone.join(", ")}\n` : "") +
    receiptLine({ op: "retire", ok: true, atom: atom_name, path: oldPath,
                  old_path: oldPath, new_path: newPath, index_ok: ex.index_ok !== false })
  );
}

// ─── Memory Search Handler ─────────────────────────────────────────────────

/** 唯讀查詢：檢索全在 py lib/memory_search（atom_io_cli action=search）；js 只組 payload、排版。
 *  warnings 併入回覆文字；不寫 state、不附 receipt。 */
async function toolMemorySearch(id, args) {
  const { query, cwd, top_k, format } = args;
  if (!String(query || "").trim()) {
    return sendToolResult(id, "memory_search: query is required", true);
  }
  const r = await spawnAtomCli("search", {
    query, cwd: cwd || process.cwd(), top_k: top_k || 8,
  });
  if (!r.ok) {
    return sendToolResult(id, `memory_search failed: ${r.error || "(unknown error)"}`, true);
  }
  const res = r.extra || {};
  if (format === "json") {
    return sendToolResult(id, JSON.stringify(res, null, 2));
  }
  const results = res.results || [];
  const lines = [`[memory_search] mode=${res.mode} hits=${results.length}`];
  for (const w of res.warnings || []) lines.push(`⚠ ${w}`);
  lines.push("name | scope | source | score | excerpt");
  for (const x of results) {
    lines.push(`${x.name} | ${x.scope} | ${x.source} | ${Number(x.score).toFixed(4)} | ${x.excerpt}`);
    lines.push(`    ${x.path}`);
  }
  return sendToolResult(id, lines.join("\n"));
}

// ─── Atom Source Handler ───────────────────────────────────────────────────

/** 唯讀：查一張 atom 的來源（Source 指標＋Quote 原句＋transcript 前後文）。定位與 transcript
 *  回讀全在 py `atom_io_cli` action=source；js 只組 payload、排版。
 *  py extra 契約：{atom, path, source, quote, state: "live"|"quote_only"|"unrecoverable",
 *  context: [{role, ts, text}], warnings: []}。不寫 state、無 receipt。 */
async function toolAtomSource(id, args) {
  const { atom, cwd, format } = args;
  if (!String(atom || "").trim()) {
    return sendToolResult(id, "atom_source: atom is required (atom name or absolute path)", true);
  }
  const r = await spawnAtomCli("source", { atom, cwd: cwd || process.cwd() });
  if (!r.ok) {
    return sendToolResult(id, `atom_source failed: ${r.error || "(unknown error)"}`, true);
  }
  const res = r.extra || {};
  if (format === "json") {
    return sendToolResult(id, JSON.stringify(res, null, 2));
  }
  const lines = [`${res.atom || atom} — ${res.state || "?"}`];
  for (const w of res.warnings || []) lines.push(`⚠ ${w}`);
  lines.push(`Source: ${res.source || "(none)"}`);
  lines.push(`Quote: ${res.quote || "(none)"}`);
  if (res.state === "unrecoverable") lines.push("原對話已逾保留期");
  for (const c of res.context || []) {
    const text = String(c.text || "").replace(/\s*\n\s*/g, " ");
    lines.push(`[${c.role || "?"} ${c.ts || "?"}] ${[...text].slice(0, 300).join("")}`);
  }
  return sendToolResult(id, lines.join("\n"));
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

module.exports = { toolAtomWrite, toolAtomPromote, toolAtomEditMeta, toolAtomMove, toolAtomRetire, toolMemorySearch, toolAtomSource };
