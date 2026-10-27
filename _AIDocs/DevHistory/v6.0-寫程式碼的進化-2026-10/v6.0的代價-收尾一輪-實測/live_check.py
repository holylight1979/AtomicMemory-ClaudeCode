"""live_check.py — 無頭實跑沒動到 live（~/.claude）的證明：逐個受測 session id 查 live 的 Logs、workflow state、projects。

做什麼：每一跑的回合 JSON 取 session_id，查
  1. live Logs/ 底下所有檔（含子目錄）的內容有沒有這個 id；
  2. live workflow/ 底下檔名或 state 檔內容有沒有這個 id；
  3. live projects/ 有沒有這一跑的 slug 目錄、有沒有任何 <id>.jsonl；
  4. 受測資料根（C:/w4/closing-time/<n>/qb2-sales-root）的 Logs 有沒有這個 id（應該有＝hook 寫對了地方）。
另印 live 的 HEAD 與 git status 行數（其他 session 背景上傳會讓它變，不拿來判，只列出）。
怎麼跑：python -X utf8 live_check.py <run> [<run> …]
尾行：LIVE_CHECK PASS|FAIL
"""
import json
import subprocess
import sys
from pathlib import Path

LIVE = Path.home() / ".claude"
TMP = Path(r"C:/Users/holylight/.claude/jobs/778a48b3/tmp")


def has_text(root: Path, needle: str, name_only: bool = False) -> list:
    hits = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if needle in p.name:
            hits.append(str(p))
            continue
        if name_only or p.stat().st_size > 50_000_000:
            continue
        try:
            if needle in p.read_text(encoding="utf-8", errors="ignore"):
                hits.append(str(p))
        except OSError:
            pass
    return hits


def main(runs):
    ok = True
    for run in runs:
        turn = json.loads((TMP / "results" / run / "B-1" / "turns" / "B-1-t1.json").read_text(encoding="utf-8"))
        sid = str(turn.get("session_id") or "")
        n = run.rsplit("-", 1)[-1]
        logs = has_text(LIVE / "Logs", sid)
        wf = has_text(LIVE / "workflow", sid, name_only=True) + \
            [str(p) for p in (LIVE / "workflow").glob("state-*.json") if sid in p.read_text(encoding="utf-8", errors="ignore")]
        slug = LIVE / "projects" / f"C--w4-closing-time-{n}-qb2-sales"
        proj = [str(p) for p in (LIVE / "projects").rglob(f"{sid}*")] + ([str(slug)] if slug.exists() else [])
        mine = has_text(Path(f"C:/w4/closing-time/{n}/qb2-sales-root/Logs"), sid)
        good = bool(sid) and not logs and not wf and not proj and bool(mine)
        ok = ok and good
        print(f"{run} sid={sid}：live Logs 命中 {len(logs)}、live workflow 命中 {len(wf)}、live projects 命中 {len(proj)}；"
              f"受測資料根 Logs 命中 {len(mine)} 檔 → {'OK' if good else 'NG'}")
        for h in (logs + wf + proj)[:5]:
            print("   ", h)
    head = subprocess.run(["git", "-C", str(LIVE), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", str(LIVE), "status", "--porcelain"], capture_output=True, text=True).stdout
    print(f"live HEAD={head} status 行數={len(st.splitlines())}（其他 session 會動它，只列不判）")
    print(f"LIVE_CHECK {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
