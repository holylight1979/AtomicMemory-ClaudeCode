"""atom-io-audit.py — 稽核帳 memory/_meta/atom_io_audit.jsonl 的壞行檢查與修復。

做什麼：逐行讀稽核帳，找出不是合法 UTF-8 JSON 的行（多個 session 同時 append 互蓋留下的半行、被切斷的中文字）。
  --check（預設）列出壞行數與行號，有壞行 exit 1；
  --repair 把壞行就地改寫成合法 JSON 行（op=audit_line_repaired，raw_hex 存原始位元組），好行不動；
           改寫前原檔整份留到旁檔 <稽核帳>.pre-repair-<UTC 時刻>；沒有壞行不動檔。與寫入端同一把鎖，修的同時照常可寫。
怎麼跑：python tools/atom-io-audit.py [--check | --repair] [--path <稽核帳>]；完整參數見 --help。
尾行：--check → ATOM_IO_AUDIT_CHECK PASS|FAIL；--repair → ATOM_IO_AUDIT_REPAIR DONE bad=<n> backup=<旁檔名|none>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import atom_io  # noqa: E402


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")   # 壞行原文印到 cp950 主控台也不炸
    ap = argparse.ArgumentParser(description="稽核帳 atom_io_audit.jsonl 的壞行檢查與修復")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="列出壞行（預設）；有壞行 exit 1")
    mode.add_argument("--repair", action="store_true", help="壞行改寫成合法 JSON 行，原檔整份留到旁檔")
    ap.add_argument("--path", type=Path, default=None, help=f"稽核帳路徑（預設 {atom_io.AUDIT_LOG}）")
    args = ap.parse_args(argv)
    log = args.path or atom_io.AUDIT_LOG

    if args.repair:
        res = atom_io.repair_audit_log(log)
        if res["backup"]:
            print(f"{log}：改寫 {res['bad']} 行壞行，原檔留在 {res['backup']}")
        else:
            print(f"{log}：沒有壞行，檔沒動")
        print(f"ATOM_IO_AUDIT_REPAIR DONE bad={res['bad']} backup={Path(res['backup']).name if res['backup'] else 'none'}")
        return 0

    good, bad = atom_io.read_audit_log(log)
    for n, body in bad[:20]:
        print(f"  第 {n} 行：{body[:120].decode('utf-8', errors='replace')}")
    if len(bad) > 20:
        print(f"  …另 {len(bad) - 20} 行")
    print(f"{log}：{len(good)} 行正常、{len(bad)} 行壞" + ("；修法：加 --repair" if bad else ""))
    print("ATOM_IO_AUDIT_CHECK " + ("FAIL" if bad else "PASS"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
