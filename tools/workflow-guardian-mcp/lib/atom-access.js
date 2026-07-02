// atom-access.js — <atom>.access.json 遙測讀取與效用 Wilson 下界（SYNC: lib/atom_access.py）。
// verify_promotion_gate_phase0 讀本檔驗 usefulnessStats / wilsonLowerBound 鏡像。
const fs = require("fs");
const { CLAUDE_DIR } = require("./paths");

/** Parse atom metadata from file content. Returns {confidence, confirmations, ...} */
function parseAtomMeta(content) {
  const meta = {};
  const re = /^- ([\w-]+):\s*(.+)$/gm;
  let m;
  while ((m = re.exec(content)) !== null) {
    const key = m[1].toLowerCase();
    const val = m[2].trim();
    switch (key) {
      case "confidence": meta.confidence = val; break;
      case "scope": meta.scope = val; break;
      case "trigger": meta.triggers = val; break;
      case "related": meta.related = val; break;
      // confirmations / readhits / last-used 從 <atom>.access.json 讀（見 readAtomAccess）
    }
  }
  const titleMatch = content.match(/^# (.+)$/m);
  if (titleMatch) meta.title = titleMatch[1];
  return meta;
}

/** 讀 <atom>.access.json 旁路檔（同步 fs，不 spawn 子程序）。 */
function readAtomAccess(atomPath) {
  try {
    const accessPath = atomPath.replace(/\.md$/, ".access.json");
    if (!fs.existsSync(accessPath)) return {};
    const raw = JSON.parse(fs.readFileSync(accessPath, "utf-8"));
    let confirmations = raw.confirmations;
    if (Array.isArray(confirmations)) confirmations = confirmations.length;
    return {
      confirmations: parseInt(confirmations, 10) || 0,
      readhits: parseInt(raw.read_hits, 10) || 0,
      usefulHits: Number(raw.useful_hits != null ? raw.useful_hits : 1),  // α (v3, Laplace prior 1)
      usedFail: Number(raw.used_fail != null ? raw.used_fail : 1),        // β
      lastUsed: raw.last_used || null,
      lastPromotedAt: raw.last_promoted_at || null,
    };
  } catch {
    return {};
  }
}

// ─── 效用 Wilson 下界（SYNC: lib/atom_access.py wilson_lower_bound /
//     usefulness_stats / usefulness_promote_eligible —— py↔js 鏡像，改一邊要改另一邊）。
function wilsonLowerBound(successes, n, z) {
  if (n <= 0) return 0.0;
  const phat = successes / n;
  const denom = 1.0 + (z * z) / n;
  const centre = phat + (z * z) / (2.0 * n);
  const margin = z * Math.sqrt((phat * (1.0 - phat) + (z * z) / (4.0 * n)) / n);
  const lb = (centre - margin) / denom;
  return Math.max(0.0, Math.min(1.0, lb));
}

/** access(α,β) → succ/fail/n/mean/lowerBound（prior=1 → succ=α−1, fail=β−1）。 */
function usefulnessStats(access, z) {
  const PRIOR = 1;
  const alpha = Number(access.usefulHits != null ? access.usefulHits : PRIOR);
  const beta = Number(access.usedFail != null ? access.usedFail : PRIOR);
  const succ = Math.max(0, alpha - PRIOR);
  const fail = Math.max(0, beta - PRIOR);
  const n = succ + fail;
  return {
    alpha, beta, successes: succ, failures: fail, n,
    mean: n > 0 ? succ / n : 0.0,
    lowerBound: wilsonLowerBound(succ, n, z),
  };
}

// world.html「戰力星級」資料源（v2）：把 <atom>.access.json 的遙測併進 /api/atoms 的
// atom 物件。access.json 為 Wave-2 權威來源（counts/last_used 不在 .md），故覆寫同名 .md 欄位。
const POWER_WILSON_Z = 1.96;
function enrichAtomWithAccess(atom, filePath) {
  const acc = readAtomAccess(filePath);
  if (acc.confirmations != null) atom.confirmations = acc.confirmations;
  if (acc.readhits != null) atom.read_hits = acc.readhits;
  if (acc.lastUsed) atom.last_used = acc.lastUsed;      // Wave-2 權威，覆寫 .md
  atom.useful_hits = acc.usefulHits != null ? acc.usefulHits : 1;  // α (Laplace prior 1)
  atom.used_fail = acc.usedFail != null ? acc.usedFail : 1;        // β
  const stats = usefulnessStats(acc, POWER_WILSON_Z);
  atom.power = Math.round(stats.lowerBound * 1000) / 1000;  // 戰力 = Wilson 下界 0..1
  atom.power_mean = Math.round(stats.mean * 1000) / 1000;
  atom.power_n = stats.n;                                   // 樣本數（succ+fail）
  if (atom.last_used) {
    const lu = new Date(atom.last_used);
    if (!isNaN(lu.getTime())) atom.days_since_used = Math.floor((Date.now() - lu.getTime()) / 86400000);
  }
}

/** spawn `python -m lib.atom_access <subcommand>` 對 access 旁路檔做寫入。 */
function spawnAtomAccess(subcommand, args) {
  return new Promise((resolve) => {
    let cp;
    try {
      cp = require("child_process").spawn(
        "python", ["-m", "lib.atom_access", subcommand, ...args],
        { cwd: CLAUDE_DIR, windowsHide: true,
          env: { ...process.env, PYTHONIOENCODING: "utf-8" } },
      );
    } catch (e) {
      return resolve({ ok: false, error: `spawn failed: ${e.message}` });
    }
    let out = "", err = "";
    cp.stdout.on("data", (d) => { out += d.toString("utf-8"); });
    cp.stderr.on("data", (d) => { err += d.toString("utf-8"); });
    cp.on("close", (code) => {
      try {
        resolve(out ? JSON.parse(out) : { ok: code === 0 });
      } catch (e) {
        resolve({ ok: false, error: `cli parse fail: ${e.message} stderr=${err.slice(0, 200)}` });
      }
    });
    cp.on("error", (e) => resolve({ ok: false, error: `spawn error: ${e.message}` }));
  });
}

module.exports = {
  parseAtomMeta, readAtomAccess, wilsonLowerBound, usefulnessStats,
  enrichAtomWithAccess, spawnAtomAccess,
};
