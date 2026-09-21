#!/usr/bin/env python
"""eval_usage.py — 用標註集評估 detect_atom_use（效用歸因的「這輪有沒有用到這顆 atom」判定）。

做什麼：讀 usage_labels.jsonl（同目錄），對每筆跑 hooks/wg_atoms.detect_atom_use，
把 adopted（--positive-include-corrected 時含 corrected）當正類、其餘當負類，
輸出混淆矩陣、precision/recall、FP／FN 明細；可同時掃多組參數。
唯讀：不寫 sidecar／state／Logs（透過 PYTEST_CURRENT_TEST 把 hook 的 log 導向暫存）。

怎麼跑：
  python -X utf8 tools/memory-eval/eval_usage.py                 # 現行參數 + 預設候選組
  python -X utf8 tools/memory-eval/eval_usage.py --rare-token-min 2,3 --overlap-min 0.18,0.3 --df-ratio none,0.5,0.1
  python -X utf8 tools/memory-eval/eval_usage.py --no-report      # 只印 stdout，不寫 usage_eval_report.md
完整參數以 --help 為準。
"""
import argparse
import itertools
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
os.environ.setdefault("PYTEST_CURRENT_TEST", "eval_usage")  # wg_core.logs_dir() → 暫存，不落正式 Logs
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT))
from wg_atoms import build_atom_df, detect_atom_use, extract_distinctive_tokens  # noqa: E402

LABELS_PATH = HERE / "usage_labels.jsonl"
REPORT_PATH = HERE / "usage_eval_report.md"
CURRENT = {"rare_token_min": 2, "overlap_min": 0.18, "df_ratio": None}  # workflow/config.json usefulness 現行值


def load_labels(path: Path):
    meta, rows = None, []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        obj = json.loads(raw)
        if "_meta" in obj:
            meta = obj["_meta"]
        else:
            rows.append(obj)
    return meta or {}, rows


def parse_list(s: str, cast):
    out = []
    for p in s.split(","):
        p = p.strip()
        if not p:
            continue
        out.append(None if p.lower() == "none" else cast(p))
    return out


def evaluate(rows, positives, *, rare_token_min, overlap_min, df_ratio, df_map=None, n_docs=0):
    tp = fp = fn = tn = 0
    fps, fns = [], []
    per_label = Counter()
    per_label_used = Counter()
    per_form = Counter()
    per_form_used = Counter()
    for r in rows:
        kw = dict(rare_token_min=rare_token_min, overlap_min=overlap_min)
        if df_ratio is not None and df_map is not None:
            kw.update(df_map=df_map, n_docs=n_docs, max_df_ratio=df_ratio)
        det = detect_atom_use(r["atom_text"], r["turn_text"], **kw)
        used = bool(det.get("used"))
        pos = r["label"] in positives
        per_label[r["label"]] += 1
        per_form[r["form"]] += 1
        if used:
            per_label_used[r["label"]] += 1
            per_form_used[r["form"]] += 1
        if used and pos:
            tp += 1
        elif used and not pos:
            fp += 1
            fps.append((r, det))
        elif not used and pos:
            fn += 1
            fns.append((r, det))
        else:
            tn += 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "params": {"rare_token_min": rare_token_min, "overlap_min": overlap_min, "df_ratio": df_ratio},
        "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec, "f1": f1,
        "fps": fps, "fns": fns,
        "per_label": per_label, "per_label_used": per_label_used,
        "per_form": per_form, "per_form_used": per_form_used,
    }


_POINTER_RE = re.compile(r"\s*\(full: Read [^)]*\)")


def apply_atom_source(rows, source, strip_pointer):
    out = []
    for r in rows:
        r = dict(r)
        if source == "file":
            try:
                txt = Path(r.get("atom_path", "")).read_text(encoding="utf-8-sig")
                if txt.strip():
                    r["atom_text"] = txt
                    r["_atom_source"] = "file"
            except (OSError, ValueError):
                r["_atom_source"] = "sent(fallback)"
        if strip_pointer and r.get("_atom_source") != "file":
            r["atom_text"] = _POINTER_RE.sub("", r["atom_text"])
        out.append(r)
    return out


def fmt_params(p):
    return f"rare≥{p['rare_token_min']} / cont≥{p['overlap_min']} / DF {'無' if p['df_ratio'] is None else p['df_ratio']}"


def shared_tokens(r, df_map=None, n_docs=0, df_ratio=None):
    rare = extract_distinctive_tokens(r["atom_text"])
    if df_ratio is not None and df_map is not None and n_docs:
        cutoff = df_ratio * n_docs
        rare = {t for t in rare if df_map.get(t, 0) <= cutoff}
    return sorted(rare & extract_distinctive_tokens(r["turn_text"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", default=str(LABELS_PATH))
    ap.add_argument("--rare-token-min", default="2,3", help="逗號分隔，例 2,3")
    ap.add_argument("--overlap-min", default="0.18,0.3", help="逗號分隔，例 0.18,0.3")
    ap.add_argument("--df-ratio", default="none,0.5,0.1", help="逗號分隔，none=不接 DF")
    ap.add_argument("--embed", default="off", choices=["off"], help="embedding tiebreak；本評估器只支援 off（不呼叫 Ollama）")
    ap.add_argument("--positive-include-corrected", action="store_true", help="把 corrected 也算正類")
    ap.add_argument("--atom-source", default="sent", choices=["sent", "file"],
                    help="sent=用實際送出形式（預設）；file=讀 atom_path 整檔（鏡像現行 Stop 的比對對象；檔不存在退回 sent）")
    ap.add_argument("--strip-pointer-path", action="store_true",
                    help="比對前把送出形式裡的 '(full: Read …)' 路徑段去掉（診斷：路標路徑片段 users/holylight/claude 幾乎每輪都命中）")
    ap.add_argument("--no-report", action="store_true", help="不寫 usage_eval_report.md")
    ap.add_argument("--report", default=str(REPORT_PATH), help="報告輸出路徑")
    ap.add_argument("--detail-limit", type=int, default=60, help="FP/FN 明細每組最多列幾筆")
    args = ap.parse_args()

    meta, rows = load_labels(Path(args.labels))
    rows = apply_atom_source(rows, args.atom_source, args.strip_pointer_path)
    positives = {"adopted"} | ({"corrected"} if args.positive_include_corrected else set())
    df_map, n_docs = build_atom_df([r["atom_text"] for r in rows])  # DF 母體 = 標註集內所有 atom_text（含重複形式）
    uniq_atoms = len({r["atom_text"] for r in rows})

    grid = list(itertools.product(parse_list(args.rare_token_min, int), parse_list(args.overlap_min, float), parse_list(args.df_ratio, float)))
    # 現行參數永遠先跑
    if (CURRENT["rare_token_min"], CURRENT["overlap_min"], CURRENT["df_ratio"]) in grid:
        grid.remove((CURRENT["rare_token_min"], CURRENT["overlap_min"], CURRENT["df_ratio"]))
    grid.insert(0, (CURRENT["rare_token_min"], CURRENT["overlap_min"], CURRENT["df_ratio"]))

    results = [evaluate(rows, positives, rare_token_min=a, overlap_min=b, df_ratio=c, df_map=df_map, n_docs=n_docs) for a, b, c in grid]

    out = []
    w = out.append
    w("# detect_atom_use 標註集評估報告")
    w("")
    w(f"- 標註集：`{Path(args.labels)}`（{len(rows)} 筆；labeler={meta.get('labeler', '?')}，AI 判定未人工複核）")
    w(f"- 正類：{'、'.join(sorted(positives))}；負類：其餘（cited／rejected／unknown{'' if args.positive_include_corrected else '／corrected'}）")
    w(f"- 標籤分布：{dict(sorted(Counter(r['label'] for r in rows).items()))}；origin：{dict(Counter(r['origin'] for r in rows))}；form：{dict(Counter(r['form'] for r in rows))}")
    w(f"- DF 母體：標註集內全部 {n_docs} 筆 atom_text（去重後 {uniq_atoms} 種送出形式）用 `build_atom_df` 建；小語料——DF 比例門檻的意義是「出現在超過 ratio×{n_docs} 筆 atom_text 的 token 視為過泛」。")
    src_note = {"sent": "實際送出形式（全文／節錄／路標／cold 行）", "file": "atom_path 整檔（鏡像現行 Stop；檔不存在退回送出形式）"}[args.atom_source]
    w(f"- atom 比對文字：{src_note}{'；已去除路標 (full: Read …) 路徑段' if args.strip_pointer_path else ''}。")
    w("- embedding tiebreak：關閉（不呼叫 Ollama）。")
    w("- 現行參數（workflow/config.json usefulness）：rare_token_min=2、lexical_overlap_min=0.18、未接 DF。")
    w("")
    labs = sorted(Counter(r["label"] for r in rows))

    def emit_table(res_list, title):
        w(f"## {title}")
        w("")
        w("| 參數 | TP | FP | FN | TN | precision | recall | F1 | 判 used 佔比 | " + " | ".join(f"{l} used" for l in labs) + " |")
        w("|---|---|---|---|---|---|---|---|---|" + "---|" * len(labs))
        for res in res_list:
            used = res["tp"] + res["fp"]
            is_cur = res["params"] == {"rare_token_min": CURRENT["rare_token_min"], "overlap_min": CURRENT["overlap_min"], "df_ratio": CURRENT["df_ratio"]}
            cells = " | ".join(f"{res['per_label_used'][l]}/{res['per_label'][l]}" for l in labs)
            w(f"| {fmt_params(res['params'])}{'（現行）' if is_cur else ''} | {res['tp']} | {res['fp']} | {res['fn']} | {res['tn']} | {res['precision']:.2f} | {res['recall']:.2f} | {res['f1']:.2f} | {used}/{len(rows)} | {cells} |")
        w("")

    emit_table(results, "參數對照表（主設定）")
    # 變體：同一網格，換比對對象／正類定義，供 Phase 2 對照
    variants = [
        ("變體 A：atom 比對文字改為整檔（鏡像現行 Stop 讀 atom_path）", apply_atom_source(load_labels(Path(args.labels))[1], "file", False), positives),
        ("變體 B：送出形式去除路標 (full: Read …) 路徑段", apply_atom_source(load_labels(Path(args.labels))[1], "sent", True), positives),
        ("變體 C：corrected 也算正類（主設定的比對文字）", rows, {"adopted", "corrected"}),
    ]
    for title, rows_v, pos_v in variants:
        df_v, n_v = build_atom_df([r["atom_text"] for r in rows_v])
        res_v = [evaluate(rows_v, pos_v, rare_token_min=a, overlap_min=b, df_ratio=c, df_map=df_v, n_docs=n_v) for a, b, c in grid]
        # 借用外層 rows 長度顯示佔比：三個變體筆數相同
        emit_table(res_v, title)
    cur = results[0]
    w("## 現行參數：各標籤／各形式被判 used 的比例")
    w("")
    w("| 標籤 | 判 used / 總數 |")
    w("|---|---|")
    for lab in sorted(cur["per_label"]):
        w(f"| {lab} | {cur['per_label_used'][lab]}/{cur['per_label'][lab]} |")
    w("")
    w("| 送出形式 | 判 used / 總數 |")
    w("|---|---|")
    for f_ in sorted(cur["per_form"]):
        w(f"| {f_} | {cur['per_form_used'][f_]}/{cur['per_form'][f_]} |")
    w("")
    for res in results:
        w(f"## 明細：{fmt_params(res['params'])}")
        w("")
        w(f"### FP（{res['fp']} 筆：負類被判 used）")
        w("")
        if res["fps"]:
            w("| id | label | form | origin | shared | containment | 共享 token |")
            w("|---|---|---|---|---|---|---|")
            for r, det in res["fps"][: args.detail_limit]:
                toks = shared_tokens(r, df_map, n_docs, res["params"]["df_ratio"])
                w(f"| {r['id']} | {r['label']} | {r['form']} | {r['origin']} | {det.get('shared')} | {det.get('containment')} | {' '.join(toks)[:160]} |")
        else:
            w("（無）")
        w("")
        w(f"### FN（{res['fn']} 筆：正類被判 not used）")
        w("")
        if res["fns"]:
            w("| id | label | form | origin | shared | containment | method | 共享 token |")
            w("|---|---|---|---|---|---|---|---|")
            for r, det in res["fns"][: args.detail_limit]:
                toks = shared_tokens(r, df_map, n_docs, res["params"]["df_ratio"])
                w(f"| {r['id']} | {r['label']} | {r['form']} | {r['origin']} | {det.get('shared')} | {det.get('containment')} | {det.get('method')} | {' '.join(toks)[:160]} |")
        else:
            w("（無）")
        w("")
    w("## 人工複核優先（標註者自 flag）")
    w("")
    flagged = [r for r in rows if r.get("review_flag")]
    if flagged:
        w("| id | label | review_flag |")
        w("|---|---|---|")
        for r in flagged:
            w(f"| {r['id']} | {r['label']} | {r['review_flag']} |")
    else:
        w("（無）")
    w("")
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    if not args.no_report:
        REPORT_PATH.write_text(text, encoding="utf-8", newline="\n")
        print(f"[eval_usage] 報告已寫：{REPORT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
