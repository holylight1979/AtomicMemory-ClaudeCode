"""probe_state_parallel_perf.py — 平行 N 支 hook 同時讀改寫同一份 session state 時，每支跑多久、離 hook 上限多遠、紀錄掉了沒
（規則 STATE_RMW_LOCKED 的效能量測）。

做什麼：每一輪建一個沙箱（verify_state_parallel_rmw.Sandbox：tmp 資料根、有部位表的專案），對受測樹的真 hook 入口
hooks/workflow-guardian.py 先跑開場、一則提問、改一個程式檔（讓這回合算寫碼回合、計時帳有記）、讀一個部位檔（注入導讀卡），
再一次起 N 支 PostToolUse：Read N 個不同的部位檔、Write N 個不同的檔；另兩組是別人握鎖 1.8 秒（約真實 Stop 整支的長度）與
3.5 秒（超過等鎖期限，走待併帳）時同時起 N 支 Read，跑完再補一支 Read 讓它併回，才核對紀錄。
量每支從起行程到結束的牆鐘、計時帳的「讀 state」段（等鎖＋拿鎖時併帳＋讀檔，不是純等鎖）與每支的總時間，並核對 N 筆讀檔／
改檔紀錄有沒有都在、有沒有留待併帳。不是 pytest 案例（檔名不以 verify_／test_ 開頭）。

怎麼跑：python -X utf8 hooks/verify/probe_state_parallel_perf.py [--tree <受測樹>] [--n 4,10] [--rounds 3]
尾行：STATE_PARALLEL_PERF DONE k=v（數字是尺不是判決）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_state_parallel_rmw import Sandbox, _names, _part_rec, _start  # noqa: E402

LIMIT_S = 5.0     # settings.json 的 PostToolUse timeout


def _timing_rows(sb: Sandbox, skip: int) -> list:
    p = sb.logs / "guard-hook_timing.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [r for r in rows[skip:] if r.get("event") == "PostToolUse" and r.get("kind") == "run"]


def _seg(row: dict, name: str) -> int:
    return next((ms for n, ms in row.get("segments") or [] if n == name), 0)


def _hold_lock(sb: Sandbox, secs: float):
    """別人握著這個 session 的 state 鎖 secs 秒（另一條執行緒；只在 Windows）。回執行緒，join 等它放掉。"""
    import msvcrt
    import threading
    import time
    lock = sb.data / "workflow" / f"state-{sb.sid}.lock"
    fh = open(lock, "ab")
    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)

    def release() -> None:
        time.sleep(secs)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        fh.close()
    t = threading.Thread(target=release)
    t.start()
    return t


def one_round(tree: Path, n: int, kind: str) -> dict:
    base = Path(tempfile.mkdtemp(prefix="state-perf-"))
    try:
        sb = Sandbox(base, tree)
        for i in range(n):
            (sb.proj / "orders" / f"r{i}.py").write_text(f"r{i} = 1\n", encoding="utf-8")
        _start(sb)
        sb.run(sb.write_event(sb.proj / "orders" / "seed.py"))           # 寫碼回合：PostToolUse 計時帳才記
        sb.run(sb.read_event(sb.proj / "orders" / "a.py"))               # 注入導讀卡
        skip = len((sb.logs / "guard-hook_timing.jsonl").read_text(encoding="utf-8").splitlines()) \
            if (sb.logs / "guard-hook_timing.jsonl").exists() else 0
        files = [sb.proj / "orders" / (f"w{i}.py" if kind == "write" else f"r{i}.py") for i in range(n)]
        events = [sb.write_event(f) if kind == "write" else sb.read_event(f) for f in files]
        hold = float(kind.split("hold", 1)[1]) if "hold" in kind else 0.0
        holder = _hold_lock(sb, hold) if hold else None
        res = sb.run_parallel(events)
        if holder:
            holder.join()
            sb.run(sb.read_event(sb.proj / "orders" / "a.py"))       # 下一支拿到鎖的 hook：併回待併帳
        pending_seen = sum(1 for _, _, e, _ in res if "[state:pending-written]" in e)
        st = sb.state()
        want = {f.name.lower() for f in files}
        got = (_names(_part_rec(st)["part_files_read"])
               if kind != "write" else _names(m.get("path") for m in st.get("modified_files") or [] if isinstance(m, dict)))
        rows = _timing_rows(sb, skip)
        return {
            "wall": [ms for _, _, _, ms in res],
            "rc_bad": sum(1 for rc, _, _, _ in res if rc != 0),
            "lost": len(want - got),
            "pending": len(list((sb.data / "workflow").glob(f"state-{sb.sid}.*.pending"))),
            "pending_seen": pending_seen,
            "lock_timeout": sum(1 for _, _, e, _ in res if "[state:lock-timeout]" in e),
            "read_seg": [_seg(r, "讀 state") for r in rows],
            "total": [r.get("total_ms", 0) for r in rows],
            "degraded": sum(1 for r in rows if r.get("degraded_at")),
        }
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tree", default=str(Path(__file__).resolve().parents[2]), help="受測樹（預設本檔所在的樹）")
    ap.add_argument("--n", default="4,10", help="一次起幾支，逗號分隔")
    ap.add_argument("--rounds", type=int, default=3)
    a = ap.parse_args()
    tree = Path(a.tree).resolve()
    kv = {}
    for n in (int(x) for x in a.n.split(",")):
        for kind in ("read", "write", "read+hold1.8", "read+hold3.5"):
            agg = {"wall": [], "read_seg": [], "total": [], "lost": 0, "pending": 0, "lock_timeout": 0, "rc_bad": 0, "degraded": 0,
                   "pending_seen": 0}
            for _ in range(a.rounds):
                r = one_round(tree, n, kind)
                for k in ("wall", "read_seg", "total"):
                    agg[k] += r[k]
                for k in ("lost", "pending", "lock_timeout", "rc_bad", "degraded", "pending_seen"):
                    agg[k] += r[k]
            wall, seg = agg["wall"], agg["read_seg"] or [0]
            print(f"{kind} n={n} rounds={a.rounds}: wall p50={statistics.median(wall):.0f}ms max={max(wall)}ms "
                  f"(上限 {LIMIT_S:g}s 的 {max(wall) / LIMIT_S / 10:.0f}%)；讀 state 段（等鎖＋併帳＋讀檔）p50={statistics.median(seg):.0f}ms "
                  f"max={max(seg)}ms；計時帳 total max={max(agg['total'] or [0])}ms；掉紀錄 {agg['lost']}、留過待併帳 {agg['pending_seen']}、"
                  f"沒併掉的待併帳 {agg['pending']}、"
                  f"等鎖逾時 {agg['lock_timeout']}、降級 {agg['degraded']}、hook 非 0 結束 {agg['rc_bad']}")
            tag = kind.replace("+", "_").replace(".", "_") + "_n"
            kv.update({f"{tag}{n}_wall_max_ms": max(wall), f"{tag}{n}_wall_p50_ms": int(statistics.median(wall)),
                       f"{tag}{n}_readseg_max_ms": max(seg), f"{tag}{n}_lost": agg["lost"],
                       f"{tag}{n}_pending_seen": agg["pending_seen"], f"{tag}{n}_pending_left": agg["pending"]})
    print("STATE_PARALLEL_PERF DONE " + " ".join(f"{k}={v}" for k, v in kv.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
