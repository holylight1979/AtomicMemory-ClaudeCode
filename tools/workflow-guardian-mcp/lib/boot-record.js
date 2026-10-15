// 工具服務程序的啟動紀錄：workflow/mcp-boot/<pid>.json 記「啟動時載入的程式版本」（code_mtime，與 server.js codeMtime 同算法）
// 與每分鐘更新的心跳。hook 收尾時拿它和磁碟上的程式版本比，判斷 AI 叫使用者 Reload Window 是不是多餘
// （規則 RELOAD_ADVICE_ALREADY_LOADED）。寫不了只少這份事實（hook 判不出就放行），stderr 說一聲。
const fs = require("fs");
const path = require("path");

function writeBootRecord(dir, pid, codeMtime, bootedAt, heartbeatAt) {
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${pid}.json`);
  const tmp = `${file}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify({ pid, code_mtime: codeMtime, booted_at: bootedAt, heartbeat_at: heartbeatAt }));
  fs.renameSync(tmp, file);
}

function startBootRecord(dir, pid, codeMtime, intervalMs = 60000) {
  const bootedAt = Date.now();
  const beat = () => {
    try {
      writeBootRecord(dir, pid, codeMtime, bootedAt, Date.now());
    } catch (e) {
      process.stderr.write(`[boot-record] 寫不了啟動紀錄（hook 判不出重載建議要不要擋，照放行）：${e.message}\n`);
    }
  };
  beat();
  const timer = setInterval(beat, intervalMs);
  if (timer.unref) timer.unref();
  process.on("exit", () => {
    try { fs.unlinkSync(path.join(dir, `${pid}.json`)); } catch {}
  });
  return timer;
}

module.exports = { writeBootRecord, startBootRecord };
