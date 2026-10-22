"""b6_verdicts.py — 把四跑八張判分表（Opus、Codex 各一張）的 B′ 各條結論抽成一張對照表，分出只有現況過／兩邊都過／兩邊都沒過。

做什麼
  1. 每張判分表逐列找條件代號 B1～B11（列裡第一個 `B<數字>` 字樣），取該列第一個內容恰為「過／沒過／沒發生」的格（去掉粗體與括號註）。
     同一代號出現多列（表尾摘要）只取第一列。抓不到的條件記「—」並列在 missing，不猜。
  2. 每組（全關／現況）四張表（兩跑 × 兩位）：四張都過＝「過」，都不過＝「沒過」，混著＝「分歧」（列出哪張不同；分歧只記不裁）。
  3. 依兩組結論分類：只有現況過／兩邊都過／兩邊都沒過／只有全關過／有分歧。

怎麼跑
  python -X utf8 b6_verdicts.py --runs off:2026-10-22-B6off-1,on:2026-10-22-B6on-1,off:2026-10-22-B6off-2,on:2026-10-22-B6on-2r [--kit …]
  尾行 B6_VERDICTS DONE tables=<讀到幾張> only_on=… both=… neither=… only_off=… split=… missing=<抓不到的格數>
"""
import argparse
import re
from pathlib import Path

DEFAULT_KIT = "C:/Users/holylight/.claude/workflow/inbox/wave2-kit"
JUDGES = (("opus", "判分-claude-opus.md"), ("codex", "判分-codex.md"))
VERDICTS = ("過", "沒過", "沒發生")
CODES = [f"B{i}" for i in range(1, 12)]
CODE_RE = re.compile(r"\bB(\d{1,2})\b")


def clean(cell):
    return re.sub(r"[*`]|（.*?）|\(.*?\)", "", cell).strip()


def read_table(path):
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = next((CODE_RE.search(c) for c in cells[:3] if CODE_RE.search(c)), None)
        if not m or f"B{m.group(1)}" not in CODES:
            continue
        code = f"B{m.group(1)}"
        verdict = next((clean(c) for c in cells if clean(c) in VERDICTS), None)
        if code not in out and verdict:
            out[code] = verdict
    return out


def arm_verdict(vals):
    got = [v for _who, v in vals if v]
    if got and all(v == "過" for v in got) and len(got) == len(vals):
        return "過"
    if got and all(v != "過" for v in got) and len(got) == len(vals):
        return "沒過"
    return "分歧"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--kit", default=DEFAULT_KIT)
    a = ap.parse_args()
    table = {}   # (arm, 日期, 判分者) → {條件: 結論}
    for spec in a.runs.split(","):
        arm, d = spec.split(":", 1)
        for who, name in JUDGES:
            p = Path(a.kit) / "results" / d / name
            table[(arm, d, who)] = read_table(p) if p.is_file() else {}
    keys = list(table)
    print("| 條件 | " + " | ".join(f"{arm} {d[-6:]} {who}" for arm, d, who in keys) + " | 全關 | 現況 | 分類 |")
    print("|---" * (len(keys) + 4) + "|")
    counts = {"只有現況過": 0, "兩邊都過": 0, "兩邊都沒過": 0, "只有全關過": 0, "有分歧": 0}
    missing = 0
    for code in CODES:
        row = [table[k].get(code) for k in keys]
        missing += sum(1 for v in row if not v)
        off = arm_verdict([(k, table[k].get(code)) for k in keys if k[0] == "off"])
        on = arm_verdict([(k, table[k].get(code)) for k in keys if k[0] == "on"])
        kind = ("有分歧" if "分歧" in (off, on) else
                "只有現況過" if (off, on) == ("沒過", "過") else
                "兩邊都過" if (off, on) == ("過", "過") else
                "兩邊都沒過" if (off, on) == ("沒過", "沒過") else "只有全關過")
        counts[kind] += 1
        print(f"| {code} | " + " | ".join(v or "—" for v in row) + f" | {off} | {on} | {kind} |")
    print(f"B6_VERDICTS DONE tables={sum(1 for v in table.values() if v)} only_on={counts['只有現況過']} both={counts['兩邊都過']} "
          f"neither={counts['兩邊都沒過']} only_off={counts['只有全關過']} split={counts['有分歧']} missing={missing}")


if __name__ == "__main__":
    main()
