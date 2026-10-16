#!/usr/bin/env python3
"""session-artifacts.py：session 產出物帳本的查詢與處置（HUD 的「保留／刪除」鈕由 Node 呼叫這支）。

帳本：workflow/aec-tempfiles/<sid>.jsonl（hooks/handlers/aec_ledger.py 寫）。這支只做兩件事：
  list：列出帳上「還在」的東西與白話狀態（檔案、資料夾、git 工作樹、分支、遠端分支、臨時 repo）
  act ：對帳上某一項 keep（記下保留）或 delete（當場刪，刪前查保護規則；要確認的東西沒帶 --force 不動手）
帳上沒有的東西一律不碰——HUD 只能指名帳上的 key，不能叫它刪任意路徑。

怎麼跑：
  python tools/session-artifacts.py list --sid <session_id> [--json]
  python tools/session-artifacts.py act  --sid <session_id> --key <key> --action keep|delete [--force] [--json]
--json：第一行是結果 JSON（Node 讀這行），最後一行是哨兵 `SESSION_ARTIFACTS DONE …`。完整參數見 --help。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR / "hooks"))

from handlers import aec_ledger  # noqa: E402

_SID_RE = re.compile(r"^[A-Za-z0-9-]{1,80}$")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list", help="列出帳上還在的東西")
    p_list.add_argument("--sid", required=True)
    p_list.add_argument("--json", action="store_true")
    p_act = sub.add_parser("act", help="對帳上一項保留或刪除")
    p_act.add_argument("--sid", required=True)
    p_act.add_argument("--key", required=True)
    p_act.add_argument("--action", required=True, choices=("keep", "delete"))
    p_act.add_argument("--force", action="store_true",
                       help="使用者已在 HUD 確認過（沒合併的分支、有改動的工作樹、遠端分支、整個 repo）")
    p_act.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not _SID_RE.match(args.sid):
        print(json.dumps({"ok": False, "message": "session id 格式不對"}, ensure_ascii=False))
        return 1

    if args.cmd == "list":
        items = aec_ledger.list_alive(args.sid)
        if args.json:
            print(json.dumps({"sid": args.sid, "items": items}, ensure_ascii=False))
        else:
            for it in items:
                print(f"[{it['kind']}] {it['title']} — {it['label']}" + (f"（{it['decision']}）" if it["decision"] else ""))
        print(f"SESSION_ARTIFACTS DONE cmd=list items={len(items)}")
        return 0

    res = aec_ledger.act(args.sid, args.key, args.action, args.force)
    print(json.dumps(res, ensure_ascii=False) if args.json else res["message"])
    print(f"SESSION_ARTIFACTS DONE cmd=act ok={int(bool(res['ok']))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
