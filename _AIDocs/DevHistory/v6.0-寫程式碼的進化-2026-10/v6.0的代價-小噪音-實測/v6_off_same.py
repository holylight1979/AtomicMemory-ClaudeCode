"""v6_off_same.py — v6 關時七項提示的輸出跟 main 逐字相同：同一份情境在指定程式樹上連跑三次，把每次送出的字印成 JSON。

怎麼跑：WG_V6=0 python -X utf8 v6_off_same.py <程式樹根> > out.json；main 匯出與分支各跑一次後比對兩份 out.json。
資料根（WG_CLAUDE_DIR）導到暫存，不碰使用者的 ~/.claude。
"""
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1]).resolve()
tmp = Path(tempfile.mkdtemp(prefix="v6-off-same-"))
os.environ["WG_CLAUDE_DIR"] = str(tmp / "data")
for p in (root / "hooks", root / "lib", root / "tools" / "codex-companion"):
    sys.path.insert(0, str(p))

import codex_companion as cc  # noqa: E402
import wg_coordination as wc  # noqa: E402
import wg_evasion  # noqa: E402
import wg_parallel  # noqa: E402
from handlers import ups_context  # noqa: E402

out = {}
out["handoff"] = [cc._detect_checkpoint("Write", "C:/p/_staging/next-phase-2.md", {}) for _ in range(3)]

st = {"topic_tracker": {"prompt_count": 1}}
seq = []
for n in (1, 2, 5, 9):
    st["topic_tracker"]["prompt_count"] = n
    seq.append(wg_parallel.detect_parallel_opportunity("幫我盤點 hooks/a.py、hooks/b.py 兩個檔的錯誤處理，順便整理測試", st, {}))
out["parallel"] = seq

ref = tmp / "memory" / "_reference" / "internal-pipeline.md"
ref.parent.mkdir(parents=True)
ref.write_text("# 內部管線\nUserPromptSubmit → 檢索 → 注入。\n", encoding="utf-8")
ups_context.MEMORY_DIR = tmp / "memory"
ust = {"session_context_injected": True, "session": {"cwd": "D:/x"}, "topic_tracker": {"prompt_count": 1},
       "aidocs": {"project_root": "C:/p", "entries": [("Routing.md", "路由表"), ("Cache.md", "快取")],
                  "keywords": {"Routing.md": ["routing"], "Cache.md": ["cache"]}}}
ups = []
for prompt in ("routing 表少一列", "routing 再加", "routing 跟 cache", "workflow-guardian 記憶系統注入", "workflow-guardian 記憶系統注入"):
    lines = []
    ups_context.build_context("sid", ust, {}, prompt, prompt, prompt.lower(), 3000, lines)
    ups.append(lines)
out["ups"] = ups

wc.WORKFLOW_DIR = tmp / "wf"
wc.COORD_LOG_DIR = tmp / "wf" / "log"
wc.WORKFLOW_DIR.mkdir()
at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
(wc.WORKFLOW_DIR / "state-peer.json").write_text(json.dumps({
    "phase": "working", "session": {"id": "peer", "cwd": "C:/w"},
    "modified_files": [{"path": "C:/w/a.py", "tool": "Edit", "at": at, "count": 1, "session_id": "peer"}]}), encoding="utf-8")
cfg = {"coordination": {"enabled": True, "warn_suppress_min": 10}}
coord = []
for age in (None, 5, 11):
    if age is not None:
        p = wc._warn_cache_path("self")
        d = json.loads(p.read_text(encoding="utf-8"))
        p.write_text(json.dumps({k: time.time() - age * 60 for k in d}), encoding="utf-8")
    hit = wc.check_cross_session_conflict("self", "C:/w/a.py", cfg)
    coord.append(wc.format_conflict_warning(hit).replace(at, "<at>") if hit else None)
    if hit:
        wc.record_warn_cache("self", "C:/w/a.py")
out["coord"] = coord

mem = tmp / "proj" / ".claude" / "memory"
(mem / "episodic").mkdir(parents=True)
for i in range(2):
    (mem / "episodic" / f"episodic-s{i}.md").write_text(
        f"# s{i}\n\n- Created: 2026-10-2{i}\n\n- [臨] 覆轍信號: same_file_3x:router.py\n- 修改 atoms: routing-rules\n", encoding="utf-8")
wg_evasion.get_project_memory_dir = lambda cwd: mem
wg_evasion.WORKFLOW_DIR = tmp / "wf"
est = {"session": {"cwd": "C:/proj"}}
wg_evasion._save_oscillation_state(wg_evasion._detect_oscillation(est, {}), est)
out["oscillation"] = [wg_evasion._load_oscillation_warnings(est) for _ in range(3)]
out["rut"] = [wg_evasion._detect_rut_patterns(est, {}) for _ in range(3)]
out["state_keys"] = sorted(set(ust) | set(est) | set(st))
print(json.dumps(out, ensure_ascii=False, indent=1))
