#!/usr/bin/env python3
"""deps_mtime_svn_acceptance.py — 「依賴比卡新」對 svn 專案記憶的真實資料驗收（唯讀：不改卡片、不動工作副本）。

做什麼：載入 tools/atom-health-check.py，卡片日期暫改只看 Created-at（整批剛重驗、Verified-at 都是今天的卡直接跑必為 0，
驗不出判法），對 --memory-root 的卡跑 check_depends_mtime；另外逐條直接問 svn，照下列規則獨立算預期，兩邊對帳：
  1. 該報＝依賴的 svn 最後變更日（svn info --show-item last-changed-date，換成本地日期）晚於卡片 Created-at；
     同一天時，依賴的 last-changed-revision 大於卡片第一次進版的版號（svn log -q --stop-on-copy 最舊一筆）。
     依賴本機有未提交修改或沒進版控 → 用該檔 mtime（健檢口徑：版控日期看不到沒提交的修改）。
  2. 舊判法（依賴 mtime 日期晚於卡片 Created-at）會報、但照第 1 條不該報的，新版一條都不得報。
  3. 新版報出的條目與第 1 條的預期完全一致。
前提：依賴與卡片在同一個 svn repo（版號才能互比）。只跑 svn info／status／log，svn log 要連得到伺服器。
怎麼跑：python -X utf8 tools/verify/deps_mtime_svn_acceptance.py --memory-root C:/TSLG/.claude/memory
尾行：<NAME>_DEPS_MTIME_CHECK PASS／FAIL（NAME 預設取專案資料夾名，例 TSLG）；FAIL 前先列出不一致的條目。
"""

import argparse
import importlib.util
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_hc():
    spec = importlib.util.spec_from_file_location("atom_health_check_acceptance", ROOT / "tools" / "atom-health-check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _svn(*args: str) -> str | None:
    r = subprocess.run(["svn", *args, "--non-interactive"], capture_output=True)
    return r.stdout.decode("utf-8", "replace").strip() if r.returncode == 0 else None


def _local(utc_iso: str) -> datetime:
    return datetime.fromisoformat(utc_iso.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)


def _dep_change(dep: Path) -> tuple[datetime, int | None, str]:
    """依賴的改動 (時刻, 版號, 來源)：svn 乾淨 → last-changed-date／revision；本機有未提交修改或沒進版控 → mtime。"""
    mtime = datetime.fromtimestamp(dep.stat().st_mtime)
    when = _svn("info", "--show-item", "last-changed-date", str(dep))
    if not when:
        return mtime, None, "mtime（未進版控）"
    if _svn("status", "-q", str(dep)):
        return mtime, None, "mtime（本機未提交修改）"
    rev = int(_svn("info", "--show-item", "last-changed-revision", str(dep)))
    return _local(when), rev, f"svn r{rev}"


def _card_first(card: Path) -> tuple[datetime, int | None, str]:
    """卡片第一次進版 (時刻, 版號, 來源)：svn log -q --stop-on-copy 最舊一筆；沒進過版 → 卡片 mtime。"""
    out = _svn("log", "-q", "--xml", "--stop-on-copy", str(card))
    entries = list(ET.fromstring(out).iter("logentry")) if out else []
    if not entries:
        return datetime.fromtimestamp(card.stat().st_mtime), None, "卡片 mtime（未進版）"
    oldest = entries[-1]
    return _local(oldest.findtext("date")), int(oldest.get("revision")), f"r{oldest.get('revision')}"


def main() -> int:
    ap = argparse.ArgumentParser(description="「依賴比卡新」對 svn 專案記憶的真實資料驗收（唯讀）")
    ap.add_argument("--memory-root", required=True, help="svn 工作副本裡的專案記憶目錄，例 C:/TSLG/.claude/memory")
    ap.add_argument("--name", help="哨兵前綴（預設取專案資料夾名）")
    args = ap.parse_args()
    root = Path(args.memory_root).resolve()
    name = re.sub(r"[^A-Z0-9_]", "_", (args.name or root.parent.parent.name).upper())

    hc = _load_hc()
    hc._VERIFIED_FIELDS = ("Created-at",)      # 只在本行程內改判法，不寫回任何檔
    atoms = {k: v for k, v in hc.find_atoms(root).items() if not hc._under_mojibake(v, root)}
    got = {(i["atom"], i["dep"]): i for i in hc.check_depends_mtime(atoms)}

    expected: dict[tuple[str, str], str] = {}     # (卡, 依賴) → 為何該報
    old_only: list[tuple[tuple[str, str], str]] = []
    checked = 0
    for atom, card in sorted(atoms.items()):
        fm = hc.parse_frontmatter(card)
        created = re.search(r"\d{4}-\d{2}-\d{2}", fm.get("Created-at", ""))
        if not fm.get("Depends") or not created:
            continue
        card_day = datetime.strptime(created.group(0), "%Y-%m-%d").date()
        base = hc.depends_base_for_file(card)
        first = None
        for e in hc.parse_depends(fm["Depends"]):
            dep = hc.resolve_depends_path(e["value"], base=base) if e["type"] == "path" and e["value"] else None
            if dep is None or not dep.exists():
                continue
            checked += 1
            at, rev, how = _dep_change(dep)
            key = (atom, e["value"])
            if at.date() != card_day:
                should = at.date() > card_day
                text = f"依賴 {how} {at:%Y-%m-%d} {'晚' if should else '早'}於卡片 {card_day}"
            else:
                first = first or _card_first(card)
                should = rev > first[1] if rev is not None and first[1] is not None else at > first[0]
                text = f"同日 {card_day}，依賴 {how} {'晚於' if should else '不晚於'}卡片第一次進版 {first[2]}"
            if should:
                expected[key] = text
            elif datetime.fromtimestamp(dep.stat().st_mtime).date() > card_day:
                old_only.append((key, text))

    extra = sorted(set(got) - set(expected))
    missing = sorted(set(expected) - set(got))
    old_hit = [(k, r) for k, r in old_only if k in got]
    print(f"檢查 {checked} 條存在的 path 型依賴（{len(atoms)} 張卡，卡片日期只看 Created-at）")
    print(f"新版報 {len(got)} 條；照規則預期 {len(expected)} 條")
    print(f"舊判法（mtime）會報、照規則不該報：{len(old_only)} 條，新版報了其中 {len(old_hit)} 條")
    for (atom, dep), reason in old_only:
        print(f"  {'✗' if (atom, dep) in got else '✓'} {atom[:40]} ← {dep}：{reason}")
    for atom, dep in extra:
        i = got[(atom, dep)]
        print(f"✗ 多報：{atom} ← {dep}（新版：{i['dep_source']} {i['dep_changed']}，{i['same_day'] or '非同日'}）")
    for atom, dep in missing:
        print(f"✗ 漏報：{atom} ← {dep}（{expected[(atom, dep)]}）")
    ok = not extra and not missing and not old_hit
    print(f"{name}_DEPS_MTIME_CHECK {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
