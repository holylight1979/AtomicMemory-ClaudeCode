"""fm_snap.py — 卡內容快照：多跑對照每跑帶一模一樣的卡（不只同一份卡集清單，連卡的內容都相同）。

為什麼
  w2_build_env --cards-from 只鎖「帶哪幾張」，每跑還是從 live 照清單複製當下的內容；量測期間 live 的卡被改，各跑帶的內容就不同
  （自檢只列 WARN）。這支把一份已核對過的資料根 memory/ 存成快照，每跑建完環境後換上去。
做什麼
  save：把一個建好、還沒跑過的資料根 memory/ 整份複製成快照；不帶 _meta/atom_io_audit.jsonl*（建環境的稽核帳，內容綁資料根路徑）。
        先核它的卡雜湊等於卡集清單，不等就 FAIL。
  apply：w2_build_env 建完（自檢 PASS）之後，把 <dest> 底下三個資料根的 memory/ 換成快照（各自留自己的稽核帳），
         重寫 <專案>-root.cards.json；核每個資料根的卡雜湊＝卡集清單、memory/ 其他檔逐位元組＝快照。
怎麼跑（放在 w2_collect.py 同一個目錄）
  python -X utf8 fm_snap.py save --root C:/w4/qa2-pricing-root --cards <卡集清單.json> --snap <快照資料夾>
  python -X utf8 fm_snap.py apply --snap <快照資料夾> --cards <卡集清單.json> [--dest C:/w4]
尾行 FM_SNAP_CHECK PASS／FAIL（exit 0／1）
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w2_collect  # noqa: E402

ROOTS = ("qa2-pricing-root", "qb2-sales-root", "qc2-orders-root")
AUDIT = "_meta/atom_io_audit.jsonl"


def is_audit(rel):
    return rel == AUDIT or rel.startswith(AUDIT + ".")


def files_of(mem):
    return {p.relative_to(mem).as_posix(): p for p in sorted(mem.rglob("*")) if p.is_file()
            and not is_audit(p.relative_to(mem).as_posix())}


def done(ok, msg):
    print(msg)
    print("FM_SNAP_CHECK " + ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


def save(a, listed):
    mem, snap = Path(a.root) / "memory", Path(a.snap) / "memory"
    got = w2_collect.card_hashes(mem)
    diff = sorted(k for k in set(got) | set(listed) if got.get(k) != listed.get(k))
    if diff:
        done(False, f"{mem} 的卡跟卡集清單不同 {len(diff)} 張：{diff[:5]}")
    if snap.exists():
        done(False, f"快照 {snap} 已存在，不覆蓋")
    for rel, p in files_of(mem).items():
        dst = snap / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)
    n = len(files_of(snap))
    done(True, f"快照存好：{snap}（{n} 檔、卡 {len(got)} 張，雜湊＝清單）")


def apply(a, listed):
    snap, dest = Path(a.snap) / "memory", Path(a.dest)
    want = files_of(snap)
    bad = []
    for name in ROOTS:
        root = dest / name
        mem = root / "memory"
        if not mem.is_dir():
            bad.append(f"{name}：memory/ 不在")
            continue
        for rel, p in files_of(mem).items():
            if rel not in want:
                p.unlink()
        for rel, p in want.items():
            dst = mem / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dst)
        for d in sorted((x for x in mem.rglob("*") if x.is_dir()), key=lambda x: len(x.parts), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
        w2_collect.write_card_manifest(root)
        got = w2_collect.card_hashes(mem)
        cards_diff = sorted(k for k in set(got) | set(listed) if got.get(k) != listed.get(k))
        now = files_of(mem)
        bytes_diff = sorted(r for r in set(now) | set(want) if r not in now or r not in want
                            or now[r].read_bytes() != want[r].read_bytes())
        if cards_diff or bytes_diff:
            bad.append(f"{name}：卡對清單差 {len(cards_diff)} 張 {cards_diff[:3]}、檔對快照差 {len(bytes_diff)} {bytes_diff[:3]}")
        else:
            print(f"  ok  {name}：memory/ 換成快照（{len(now)} 檔、卡 {len(got)} 張＝清單），卡集清單已重寫")
    done(not bad, "；".join(bad) if bad else f"三個資料根都換成快照 {snap}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["save", "apply"])
    ap.add_argument("--snap", required=True)
    ap.add_argument("--cards", required=True)
    ap.add_argument("--root")
    ap.add_argument("--dest", default="C:/w4")
    a = ap.parse_args()
    listed = json.loads(Path(a.cards).read_text(encoding="utf-8"))["cards"]
    if a.step == "save":
        if not a.root:
            done(False, "save 要 --root")
        save(a, listed)
    else:
        apply(a, listed)


if __name__ == "__main__":
    main()
