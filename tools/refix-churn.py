#!/usr/bin/env python3
"""refix-churn.py：列出「同檔反覆 fix」的熱點檔（G5 老問題的候選；git／svn 自動判）。

做什麼：讀 `--cwd` 的 VCS 歷史（預設最近 60 天），挑 fix 類提交（fix／修／bug／壞／錯），按檔排名：
主尺＝同檔 fix 提交數（≥ refix_min_fixes 才列），副尺＝14 天內的配對數。記憶目錄與收割提交預設排除。

怎麼跑：
  python ~/.claude/tools/refix-churn.py --cwd <工作副本>            # 自動判 git／svn
  python ~/.claude/tools/refix-churn.py --cwd . --since-days 30 --top 10 --json
  python ~/.claude/tools/refix-churn.py --svn-xml log.xml           # 直接吃 `svn log -v --xml` 的輸出（fixture／離線）
尾行：`REFIX_CHURN DONE vcs=<git|svn|none> commits=<n> fix=<n> files_refixed=<n>`
exit：0 完成；2 VCS 讀不到（沒裝、不是工作副本、逾時）。
設定：`workflow/config.json` 的 `refix_churn` 段（fix_patterns、refix_window_days、refix_since_days、refix_min_fixes、
refix_exclude、refix_exclude_msg、refix_same_commit_pairs）；命令列參數覆蓋設定。完整參數以 --help 為準。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

CLAUDE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CLAUDE_DIR))
from lib import refix_churn as rc  # noqa: E402

CONFIG_PATH = CLAUDE_DIR / "workflow" / "config.json"


def load_cfg() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("refix_churn") or {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        print(f"[refix-churn] config.json 讀不出來，用預設值：{e}", file=sys.stderr)
        return {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cwd", default=".", help="工作副本（git 工作樹或 svn 工作副本）")
    ap.add_argument("--vcs", choices=["git", "svn"], help="強制 VCS；不給就自動判")
    ap.add_argument("--svn-xml", help="讀這個 `svn log -v --xml` 輸出檔，不碰 VCS")
    ap.add_argument("--since-days", type=int, help="回看天數（預設 refix_since_days 60）")
    ap.add_argument("--window-days", type=int, help="配對天數窗（預設 refix_window_days 14）")
    ap.add_argument("--min-fixes", type=int, help="至少幾筆 fix 才列（預設 refix_min_fixes 2）")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    cfg = rc.merge_cfg(load_cfg())
    for key, val in (("refix_since_days", args.since_days), ("refix_window_days", args.window_days),
                     ("refix_min_fixes", args.min_fixes)):
        if val is not None:
            cfg[key] = val

    root = Path(args.cwd).resolve()
    try:
        if args.svn_xml:
            vcs = "svn"
            commits = rc.parse_svn_xml(Path(args.svn_xml).read_text(encoding="utf-8", errors="replace"))
        else:
            vcs = args.vcs or rc.detect_vcs(root)
            if vcs is None:
                print(f"[refix-churn] {root} 不是 git 工作樹也不是 svn 工作副本", file=sys.stderr)
                print("REFIX_CHURN DONE vcs=none commits=0 fix=0 files_refixed=0")
                return 2
            commits = rc.read_commits(root, vcs, int(cfg["refix_since_days"]))
    except (rc.VcsError, OSError) as e:
        print(f"[refix-churn] {e}", file=sys.stderr)
        print(f"REFIX_CHURN DONE vcs={args.vcs or 'none'} commits=0 fix=0 files_refixed=0")
        return 2

    ranked = rc.rank_refixed(commits, cfg)
    if args.json:
        print(json.dumps({"cwd": str(root), "vcs": vcs, "since_days": cfg["refix_since_days"],
                          "window_days": cfg["refix_window_days"], "min_fixes": cfg["refix_min_fixes"],
                          **{k: v for k, v in ranked.items() if k != "files"},
                          "files": ranked["files"][:args.top]}, ensure_ascii=False, indent=1))
    else:
        print(f"cwd={root} vcs={vcs} since={cfg['refix_since_days']}d window={cfg['refix_window_days']}d "
              f"min_fixes={cfg['refix_min_fixes']}")
        print(f"commits={ranked['commits']} fix_commits={ranked['fix_commits']} "
              f"files_touched_by_fix={ranked['files_touched_by_fix']} files_refixed={ranked['files_refixed']}")
        print(f"{'fixes':>5} {'pairs':>5}  file  [revs]")
        for f in ranked["files"][:args.top]:
            print(f"{f['fix_commits']:>5} {f['pairs_in_window']:>5}  {f['file']}  [{','.join(f['revs'])}]")
    print(f"REFIX_CHURN DONE vcs={vcs} commits={ranked['commits']} fix={ranked['fix_commits']} "
          f"files_refixed={ranked['files_refixed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
