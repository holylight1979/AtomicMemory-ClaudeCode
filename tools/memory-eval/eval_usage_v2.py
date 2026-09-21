"""eval_usage_v2.py — 判用 v1（詞彙重疊）vs v2（行動證據優先＋去路徑噪音＋否定線索）同一標註集對照。

用法：
    python -X utf8 tools/memory-eval/eval_usage_v2.py                # 印對照表
    python -X utf8 tools/memory-eval/eval_usage_v2.py --detail       # 加印 v2 的 FP/FN 明細
唯讀；不呼叫 Ollama；PYTEST_CURRENT_TEST 讓 hook log 導向暫存。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parents[2]
os.environ.setdefault("PYTEST_CURRENT_TEST", "eval-usage-v2")
sys.path.insert(0, str(CLAUDE_DIR / "hooks"))
sys.path.insert(0, str(CLAUDE_DIR))

from wg_atoms import build_atom_df, detect_atom_use, detect_atom_use_v2  # noqa: E402

LABELS = Path(__file__).resolve().parent / "usage_labels.jsonl"


def load(path: Path):
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        obj = json.loads(raw)
        if "_meta" in obj:
            continue
        rows.append(obj)
    return rows


def run(rows, positives, policy, **kw):
    tp = fp = fn = tn = 0
    per_label = Counter(); per_label_used = Counter()
    fps, fns = [], []
    methods = Counter()
    for r in rows:
        if policy == "v1":
            det = detect_atom_use(r["atom_text"], r["turn_text"], rare_token_min=2, overlap_min=0.18)
        else:
            rescue = [h.get("token", "") for h in (r.get("evidence") or {}).get("rescue_hits") or []]
            det = detect_atom_use_v2(
                r["atom_text"], r["turn_text"], atom_name=r.get("atom_name", ""),
                form=r.get("form", "ok"), rescue_tokens=rescue if kw.get("use_rescue", True) else None,
                df_map=kw.get("df_map"), n_docs=kw.get("n_docs", 0), max_df_ratio=kw.get("df_ratio", 1.0),
                shared_min=kw.get("shared_min", 3), containment_min=kw.get("containment_min", 0.25),
            )
        used = bool(det.get("used")); pos = r["label"] in positives
        methods[det.get("method", "?")] += 1
        per_label[r["label"]] += 1
        if used:
            per_label_used[r["label"]] += 1
        if used and pos: tp += 1
        elif used and not pos: fp += 1; fps.append((r, det))
        elif not used and pos: fn += 1; fns.append((r, det))
        else: tn += 1
    p = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * rc / (p + rc) if p + rc else 0.0
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=p, recall=rc, f1=f1,
                per_label=per_label, per_label_used=per_label_used, fps=fps, fns=fns, methods=methods)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(LABELS))
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--positive-include-corrected", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    rows = load(Path(args.labels))
    positives = {"adopted"} | ({"corrected"} if args.positive_include_corrected else set())
    df_map, n_docs = build_atom_df([r["atom_text"] for r in rows])
    labs = sorted({r["label"] for r in rows})
    configs = [
        ("v1 現行（rare≥2 or cont≥0.18）", "v1", {}),
        ("v2 全套（rescue＋否定＋路標未讀不算＋shared≥3∧cont≥0.25）", "v2", {}),
        ("v2 無 rescue 證據", "v2", {"use_rescue": False}),
        ("v2 shared≥2∧cont≥0.2", "v2", {"shared_min": 2, "containment_min": 0.2}),
        ("v2 shared≥4∧cont≥0.3", "v2", {"shared_min": 4, "containment_min": 0.3}),
        ("v2 ＋DF 0.5", "v2", {"df_map": df_map, "n_docs": n_docs, "df_ratio": 0.5}),
    ]
    print(f"標註集 {len(rows)} 筆；正類={sorted(positives)}；標籤分布={dict(Counter(r['label'] for r in rows))}")
    print("| 設定 | TP | FP | FN | TN | P | R | F1 | " + " | ".join(f"{l} used" for l in labs) + " |")
    print("|---|---|---|---|---|---|---|---|" + "---|" * len(labs))
    results = {}
    for title, pol, kw in configs:
        res = run(rows, positives, pol, **kw)
        results[title] = res
        cells = " | ".join(f"{res['per_label_used'][l]}/{res['per_label'][l]}" for l in labs)
        print(f"| {title} | {res['tp']} | {res['fp']} | {res['fn']} | {res['tn']} | {res['precision']:.2f} | {res['recall']:.2f} | {res['f1']:.2f} | {cells} |")
    v2 = results[configs[1][0]]
    print("\nv2 判定方法分布：", dict(v2["methods"]))
    if args.detail:
        print("\n## v2 FP（判 used 但非正類）")
        for r, det in v2["fps"]:
            print(f"- {r['id']} [{r['label']}/{r['form']}] method={det['method']} shared={det['shared']} cont={det['containment']} :: {r['rationale'][:100]}")
        print("\n## v2 FN（正類但判未用）")
        for r, det in v2["fns"]:
            print(f"- {r['id']} [{r['label']}/{r['form']}] method={det['method']} shared={det['shared']} cont={det['containment']} :: {r['rationale'][:100]}")


if __name__ == "__main__":
    main()
