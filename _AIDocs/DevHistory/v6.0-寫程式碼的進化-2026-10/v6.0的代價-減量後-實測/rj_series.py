"""rj_series.py — 重新判分：只跑題 B′ 現況組（live 完整 hook），串行兩跑 <日>-CCon-R1、-R2，不跑全關組、不跑非改 code 題。

做什麼
  每跑照 fm_series.one_run 同一套：重建 C:\\w4（w2_build_env --selfcheck --cards-from）→ fm_snap apply 換卡內容快照 → w2_run_all --only B
  → 收資料根 Logs → 量測寫 _fm/measure.json → 作廢判定。兩跑後照 fm_series.need_extra（有作廢、或 token／牆鐘相差超過 25%）加跑 -R3，只加一次。
  fm_series 的 MEASURE_DIR 指向已拆掉的 final-measure worktree，這裡先把 rejudge worktree 同一份 b6_measure 放進 sys.path。
  總表寫 <kit>/results/_rj-series-<日>.json（不碰 004 的 _fm-series-<日>.json）。
怎麼跑（放在 fm_series.py 同一個目錄）
  WG_V6=1 python -X utf8 rj_series.py --cards <卡集清單.json> --snap <卡內容快照資料夾> [--day 2026-10-23] [--dest C:/w4]
尾行 RJ_SERIES DONE runs=<跑數> void=<作廢數> extra=<加跑原因或 none>；建環境失敗印 RJ_SERIES FAIL reason=…（exit 1）
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEASURE = Path("C:/Users/holylight/.claude-wt/rejudge/_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/v6.0的代價-實測")
sys.path.insert(0, str(MEASURE))
sys.path.insert(0, str(HERE))
import fm_series as fs  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--day", default="2026-10-23")
    ap.add_argument("--cards", required=True)
    ap.add_argument("--snap", required=True)
    ap.add_argument("--dest", default="C:/w4")
    a = ap.parse_args()
    if os.environ.get("WG_V6") != "1":
        print("RJ_SERIES FAIL reason=WG_V6 沒設成 1")
        sys.exit(1)
    dest, cards, snap = Path(a.dest), Path(a.cards), Path(a.snap)
    summary = fs.KIT / "results" / f"_rj-series-{a.day}.json"
    recs = []

    def run(n, extra_reason=""):
        r = fs.one_run("CC", "on", n, a.day, dest, cards, snap)
        if extra_reason:
            r["extra_reason"] = extra_reason
        recs.append(r)
        summary.write_text(json.dumps(recs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        if r.get("fatal"):
            print(f"RJ_SERIES FAIL reason={r['why']}")
            sys.exit(1)

    run("R1")
    run("R2")
    why = fs.need_extra(recs)
    if why:
        fs.log(f"加跑一跑：{why}")
        run("R3", why)
    print(f"RJ_SERIES DONE runs={len(recs)} void={sum(r['void'] for r in recs)} extra={why or 'none'}")


if __name__ == "__main__":
    main()
