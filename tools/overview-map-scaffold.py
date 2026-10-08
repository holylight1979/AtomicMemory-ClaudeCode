#!/usr/bin/env python3
"""overview-map-scaffold.py：從零掃出專案部位表骨架與五段佔位卡；對帳表與卡（G14）。

做什麼：掃 `--cwd` 的頂層目錄當部位、fix 熱點排前、每列一張 [臨] 骨架卡，產 `<專案>/.claude/overview-map.md`。
預設 dry-run：只定卡名、每張卡 dry-run 預驗，不落檔；加 `--write` 才寫：逐張寫卡、全部在了才寫表；任一張卡失敗
立刻停、不寫表、不刪任何東西、exit 1（stderr 列已寫／失敗／未寫）；重跑同一指令會沿用已寫的卡（部位一致才沿用，
不一致改名避撞）接續補完。表已存在一律拒寫，`--merge-missing` 以既有表的前綴→卡名配對為準，只補缺列與「表有列但卡檔不在」的卡。
卡落哪層自動判：~/.claude → 根層（global＋realm local＋MemDev）；公司根 → 公司層；其他 → 專案 shared。

怎麼跑：
  python ~/.claude/tools/overview-map-scaffold.py --cwd <專案根>                 # 預覽（不落檔）
  python ~/.claude/tools/overview-map-scaffold.py --cwd <專案根> --write         # 落表＋寫卡
  python ~/.claude/tools/overview-map-scaffold.py --cwd <專案根> --write --merge-missing   # 只補表上沒有的目錄
  python ~/.claude/tools/overview-map-scaffold.py check --cwd <專案根>           # 表卡對帳
尾行：掃表 `OVERVIEW_SCAFFOLD DONE rows=<n>`；對帳 `OVERVIEW_SCAFFOLD CHECK PASS|FAIL issues=<n>`。
exit：0 完成；1 對帳有問題或有卡寫失敗（表未寫、已寫的卡保留）；2 參數／Lv1／根目錄錯；3 表已存在被拒。
設定：`workflow/config.json` 的 `overview_scaffold`（scaffold_ignore、layers、scaffold_default_lv1）與 `refix_churn`（refix_*）。
完整參數以 --help 為準。
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
from lib import overview_scaffold as sc  # noqa: E402

CONFIG_PATH = CLAUDE_DIR / "workflow" / "config.json"


def load_sections() -> tuple:
    """→ (overview_scaffold 段, refix_churn 段)；config 缺或壞 → ({}, {}) 並在 stderr 說一聲。"""
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, {}
    except (OSError, ValueError) as e:
        print(f"[overview-map-scaffold] config.json 讀不出來，用預設值：{e}", file=sys.stderr)
        return {}, {}
    return (cfg.get("overview_scaffold") or {}), (cfg.get("refix_churn") or {})


def cmd_scaffold(args) -> int:
    root = Path(args.cwd).expanduser().resolve()
    sc_cfg, rc_cfg = load_sections()
    cfg = sc.merge_cfg(sc_cfg)
    try:
        dirs = sc.scan_top_dirs(root, cfg["scaffold_ignore"])
        hot, warn = sc.fix_hotspots_by_dir(root, [d["name"] for d in dirs], rc_cfg, args.since_days)
        if warn:
            print(f"[overview-map-scaffold] {warn}", file=sys.stderr)
        rows = sc.draft_rows(dirs, hot, cfg["layers"], args.top_n)
        layer = sc.detect_layer(root)
        lv1 = sc.ROOT_DOMAIN if layer[0] == sc.LAYER_ROOT else sc.map_lv1(root, args.lv1 or cfg["scaffold_default_lv1"])
        result = sc.write_scaffold(root, rows, lv1, write=args.write, merge_missing=args.merge_missing,
                                   root_label=root.name, layer=layer)
    except sc.ScaffoldError as e:
        print(f"[overview-map-scaffold] {e}", file=sys.stderr)
        return 3 if "不覆寫" in str(e) else 2
    if not result["ok"]:
        print(f"[overview-map-scaffold] {result['error']}", file=sys.stderr)
        for c in result["cards"]:
            print(f"  {'OK ' if c['ok'] else 'ERR'} {c['card']} → {c['path'] or c['error']}", file=sys.stderr)
        if args.json:
            print(json.dumps({k: v for k, v in result.items() if k != "table"} | {"lv1": lv1}, ensure_ascii=False, indent=1))
        print("OVERVIEW_SCAFFOLD DONE rows=0")
        return 1
    if args.json:
        print(json.dumps({k: v for k, v in result.items() if k != "table"} | {"lv1": lv1}, ensure_ascii=False, indent=1))
    else:
        print(result["table"], end="")
        print()
        if result["written"]:
            mode = "已落檔"
        elif args.write:
            mode = "表沒有新列，未改"
        else:
            mode = "dry-run，未落檔；加 --write 才寫"
        print(f"表：{result['map']}（{mode}{'，merge-missing 只補缺列與缺卡' if result['merged'] else ''}）")
        where = "根層 _AIDocs/_atoms/MemDev" if result["layer"] == sc.LAYER_ROOT else f"{result['layer']} 層 Lv1「{lv1}」"
        print(f"卡：{where}，{len(result['cards'])} 張（{'已寫' if args.write else '預驗通過'}）")
        for c in result["cards"]:
            tag = 'OK ' if c['ok'] else 'ERR'
            print(f"  {tag} {c['card']} → {c['path'] or c['error']}{'（既有，沿用）' if c.get('reused') else ''}")
    print(f"OVERVIEW_SCAFFOLD DONE rows={result['rows']}")
    return 0


def cmd_check(args) -> int:
    root = Path(args.cwd).expanduser().resolve()
    issues = sc.check_consistency(root)
    for msg in issues:
        print(f"- {msg}")
    print(f"OVERVIEW_SCAFFOLD CHECK {'FAIL' if issues else 'PASS'} issues={len(issues)}")
    return 1 if issues else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", choices=["scaffold", "check"], default="scaffold")
    ap.add_argument("--cwd", required=True, help="專案根（表落在 <cwd>/.claude/overview-map.md）")
    ap.add_argument("--dry-run", action="store_true", help="預設行為：只預覽不落檔（寫出來方便明示）")
    ap.add_argument("--write", action="store_true", help="落表＋寫骨架卡")
    ap.add_argument("--merge-missing", action="store_true", help="表已存在時只補缺的前綴列（搭 --write）")
    ap.add_argument("--top-n", type=int, default=None, help="只取熱點前 N 個目錄")
    ap.add_argument("--since-days", type=int, default=None, help="fix 熱點回看天數（預設 refix_since_days）")
    ap.add_argument("--lv1", default=None, help="骨架卡的 Lv1（必須是既有的；預設 scaffold_default_lv1）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.dry_run and args.write:
        ap.error("--dry-run 與 --write 二選一")
    return cmd_check(args) if args.command == "check" else cmd_scaffold(args)


if __name__ == "__main__":
    sys.exit(main())
