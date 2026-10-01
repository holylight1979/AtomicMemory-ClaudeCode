#!/usr/bin/env bash
# Atom V4 Phase 5 — post-merge audit hook TEMPLATE.
#
# 本檔為樣板。手動安裝到專案：
#   cp ~/.claude/hooks/post-git-pull.sh <proj>/.git/hooks/post-merge
#   chmod +x <proj>/.git/hooks/post-merge
#
# 或符號連結（跟隨樣板更新）：
#   ln -s ~/.claude/hooks/post-git-pull.sh <proj>/.git/hooks/post-merge
#
# git pull 後自動跑 memory-conflict-detector --mode=pull-audit，
# 比對 shared/ 區段新進 commit vs 本地既有 atom，事實衝突寫進
# _pending_review/{atom}.pull-conflict.md。
# Fail-open：audit 失敗不阻擋 pull，只輸出警告。

set +e

PROJ_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$PROJ_ROOT" ]; then
  exit 0  # not a git repo — nothing to do
fi

DETECTOR="${HOME}/.claude/tools/memory-conflict-detector.py"
SHARED_DIR="$PROJ_ROOT/.claude/memory/shared"

[ -f "$DETECTOR" ] || exit 0
[ -d "$SHARED_DIR" ] || exit 0

LOG_DIR="$PROJ_ROOT/.claude/memory"
mkdir -p "$LOG_DIR"

# 先觸發向量增量索引，讓新進 atom 可被 audit 查到（避免 race：
# git merge 剛寫入的檔案還未被 indexer 看到，audit 查不到相似原子）。
# 若 vector service 未跑則略過（fail-open）。
if command -v curl >/dev/null 2>&1; then
  curl -sS -m 3 -X POST http://127.0.0.1:3849/index/incremental \
    >/dev/null 2>>"$LOG_DIR/_pull_audit.err.log" || true
  # 等待增量索引收斂（輪詢 /status 的 index_job.running，最多 12s；平均新檔 ~2s/個）。
  # /status 沒有 index_job（服務起來後還沒跑過索引）、服務不可達、index_job.error 三種都直接停，不空等到上限。
  for i in 1 2 3 4 5 6; do
    sleep 2
    RAW="$(curl -sS -m 2 http://127.0.0.1:3849/status 2>/dev/null)" || { echo "[atom-v4] vector service unreachable; skip wait" >&2; break; }
    STATE="$(printf '%s' "$RAW" | python -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print('unreadable'); sys.exit()
job = d.get('index_job')
if not isinstance(job, dict):
    print('none')
elif job.get('error'):
    print('error:' + str(job['error'])[:80])
else:
    print('running' if job.get('running') else 'done')
" 2>/dev/null)"
    case "$STATE" in
      running) ;;
      done) break ;;
      none) break ;;
      error:*) echo "[atom-v4] vector index job failed: ${STATE#error:}" >&2; break ;;
      *) echo "[atom-v4] /status unreadable; skip wait" >&2; break ;;
    esac
  done
fi

python "$DETECTOR" \
  --mode=pull-audit \
  --project-cwd="$PROJ_ROOT" \
  --since=last 2>>"$LOG_DIR/_pull_audit.err.log"

RC=$?
if [ $RC -ne 0 ]; then
  echo "[atom-v4] pull-audit exited $RC (non-blocking). See $LOG_DIR/_pull_audit.err.log" >&2
fi

exit 0
