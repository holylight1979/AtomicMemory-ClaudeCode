"""run.py — 檢索回歸評估：對 queries.jsonl 跑實際檢索管線並算指標。

檢索走與線上 ups_search 同一套原語與合併順序（import hooks/wg_atoms）：
    1. trigger match（any_trigger_hit，索引序）
    2. trigger 命中 ≤2 → BM25 補位（bm25_match，config 的 min_score/top_k）
    3. （--with-vector）前兩層零命中 → 打 vector service /search/ranked 補位
不含 ACT-R activation 重排（依賴 access.json 使用統計，會讓評估隨時間漂移）。

指標：
- Recall@1 / Recall@3：direct 查詢的期望 atom 落在第 1 名 / 前 3 名的比率
- MRR：mean(1/rank)，miss 計 0
- 負例誤注入率：negative 查詢命中任一 atom 的比率
- per-atom miss：期望 atom 未進前 3 的查詢，按 atom 彙整

用法：
    python run.py                          # 跑一輪印指標
    python run.py --baseline baseline.json # 首跑存基線；之後比對（差異 >2% 標紅）
    python run.py --with-vector            # 加測 vector fallback 層（服務離線自動跳過）
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

CLAUDE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CLAUDE_DIR / "hooks"))

from wg_atoms import any_trigger_hit, bm25_match, parse_memory_index  # noqa: E402

DEFAULT_MEMORY_DIR = CLAUDE_DIR / "memory"
DEFAULT_QUERIES = Path(__file__).resolve().parent / "queries.jsonl"
CONFIG_PATH = CLAUDE_DIR / "workflow" / "config.json"

# 比對基線時的告警門檻（絕對百分點）
DIFF_THRESHOLD = 0.02

_RED = "\033[31m"
_GREEN = "\033[32m"
_RESET = "\033[0m"


def load_retrieval_config() -> Dict:
    """讀 workflow/config.json 的 vector_search 段（BM25 參數 + vector 埠）。"""
    cfg = {"bm25_min_score": 1.0, "bm25_top_k": 3,
           "service_port": 3849, "search_top_k": 5, "search_min_score": 0.65}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        vs = data.get("vector_search", {})
        for k in cfg:
            if k in vs:
                cfg[k] = vs[k]
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def load_queries(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# ─── 檢索（鏡像 ups_search 全域層合併順序） ──────────────────────────────────

def retrieve(
    prompt: str,
    entries: List,
    bm25_min_score: float,
    bm25_top_k: int,
    vector_fn: Optional[Callable[[str], List[str]]] = None,
) -> List[str]:
    """回傳 ranked atom name 清單：trigger 命中在前、BM25 補位、vector 殿後。"""
    prompt_lower = prompt.lower()
    ranked = [name for (name, _p, trig) in entries
              if any_trigger_hit(trig, prompt_lower)]
    if len(ranked) <= 2:
        for entry in bm25_match(prompt, entries,
                                min_score=bm25_min_score, top_k=bm25_top_k):
            if entry[0] not in ranked:
                ranked.append(entry[0])
    if vector_fn is not None and not ranked:
        known = {e[0] for e in entries}
        for name in vector_fn(prompt):
            if name in known and name not in ranked:
                ranked.append(name)
    return ranked


def make_vector_fn(cfg: Dict) -> Optional[Callable[[str], List[str]]]:
    """回傳打 vector service /search/ranked 的 closure；服務不通回 None。"""
    import urllib.error
    import urllib.parse
    import urllib.request

    port = cfg["service_port"]
    base = f"http://127.0.0.1:{port}"
    try:
        req = urllib.request.Request(base + "/health")
        with urllib.request.urlopen(req, timeout=2):
            pass
    except Exception:
        return None

    def _fn(prompt: str) -> List[str]:
        try:
            params = urllib.parse.urlencode({
                "q": prompt, "top_k": cfg["search_top_k"],
                "min_score": cfg["search_min_score"],
            })
            req = urllib.request.Request(
                f"{base}/search/ranked?{params}",
                headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                results = json.loads(resp.read())
            return [r.get("atom_name", "") for r in results if r.get("atom_name")]
        except Exception:
            return []

    return _fn


# ─── 指標計算 ────────────────────────────────────────────────────────────────

def evaluate(
    queries: List[Dict],
    entries: List,
    bm25_min_score: float,
    bm25_top_k: int,
    vector_fn: Optional[Callable[[str], List[str]]] = None,
    k: int = 3,
) -> Dict:
    """跑全部 queries 回傳指標 dict（含 per-atom miss 與 skipped 清單）。"""
    known = {e[0] for e in entries}
    n_direct = n_neg = 0
    hit1 = hitk = 0
    rr_sum = 0.0
    neg_hits = 0
    per_atom_miss: Dict[str, List[str]] = {}
    skipped: List[str] = []

    for row in queries:
        q = row.get("q", "")
        expect = row.get("expect")
        cls = row.get("cls", "direct")
        if cls == "direct" and expect not in known:
            skipped.append(f"{expect}: {q}")
            continue
        ranked = retrieve(q, entries, bm25_min_score, bm25_top_k, vector_fn)
        if cls == "negative":
            n_neg += 1
            if ranked:
                neg_hits += 1
            continue
        n_direct += 1
        rank = ranked.index(expect) + 1 if expect in ranked else 0
        if rank == 1:
            hit1 += 1
        if 1 <= rank <= k:
            hitk += 1
        else:
            per_atom_miss.setdefault(expect, []).append(q)
        if rank:
            rr_sum += 1.0 / rank

    return {
        "n_direct": n_direct,
        "n_negative": n_neg,
        "recall_at_1": hit1 / n_direct if n_direct else 0.0,
        "recall_at_3": hitk / n_direct if n_direct else 0.0,
        "mrr": rr_sum / n_direct if n_direct else 0.0,
        "neg_injection_rate": neg_hits / n_neg if n_neg else 0.0,
        "per_atom_miss": per_atom_miss,
        "skipped": skipped,
    }


# ─── 報表 / 基線 ─────────────────────────────────────────────────────────────

_METRIC_KEYS = ["recall_at_1", "recall_at_3", "mrr", "neg_injection_rate"]
# neg_injection_rate 越低越好，其餘越高越好
_LOWER_IS_BETTER = {"neg_injection_rate"}


def print_report(m: Dict, elapsed: float, vector_status: str) -> None:
    print(f"queries: direct={m['n_direct']} negative={m['n_negative']}  "
          f"vector={vector_status}  ({elapsed:.2f}s)")
    print(f"  Recall@1          : {m['recall_at_1']:.1%}")
    print(f"  Recall@3          : {m['recall_at_3']:.1%}")
    print(f"  MRR               : {m['mrr']:.3f}")
    print(f"  負例誤注入率      : {m['neg_injection_rate']:.1%}")
    if m["skipped"]:
        print(f"  [skip] {len(m['skipped'])} 條查詢的 expect atom 已不在索引"
              f"（重跑 genqueries 或 --regen 清理）")
    miss = m["per_atom_miss"]
    if miss:
        top = sorted(miss.items(), key=lambda kv: len(kv[1]), reverse=True)[:10]
        print(f"  per-atom miss（前 {len(top)}）:")
        for name, qs in top:
            print(f"    {name} ({len(qs)} miss)")
            for q in qs[:2]:
                print(f"      - {q}")


def compare_baseline(m: Dict, baseline_path: Path, use_color: bool) -> bool:
    """有基線 → 比對（回傳是否有 >2% 退步）；沒有 → 寫入。"""
    if not baseline_path.exists():
        payload = {k: m[k] for k in _METRIC_KEYS}
        payload.update({"n_direct": m["n_direct"], "n_negative": m["n_negative"],
                        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        baseline_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print(f"基線已建立：{baseline_path}")
        return False
    try:
        base = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"基線讀取失敗（{e}），略過比對", file=sys.stderr)
        return False
    print(f"與基線比對（{baseline_path.name}，門檻 ±{DIFF_THRESHOLD:.0%}）:")
    regressed = False
    for key in _METRIC_KEYS:
        if key not in base:
            continue
        cur, old = m[key], base[key]
        diff = cur - old
        worse = (diff < -DIFF_THRESHOLD) if key not in _LOWER_IS_BETTER \
            else (diff > DIFF_THRESHOLD)
        better = (diff > DIFF_THRESHOLD) if key not in _LOWER_IS_BETTER \
            else (diff < -DIFF_THRESHOLD)
        mark = ""
        if worse:
            regressed = True
            mark = f"{_RED}▼ 退步{_RESET}" if use_color else "▼ 退步 !!"
        elif better:
            mark = f"{_GREEN}▲ 進步{_RESET}" if use_color else "▲ 進步"
        print(f"  {key:<18}: {old:.3f} → {cur:.3f} ({diff:+.3f}) {mark}")
    return regressed


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="檢索回歸評估")
    ap.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    ap.add_argument("--memory-dir", type=Path, default=DEFAULT_MEMORY_DIR)
    ap.add_argument("--baseline", type=Path, default=None,
                    help="基線 JSON：不存在則寫入，存在則比對")
    ap.add_argument("--with-vector", action="store_true",
                    help="前兩層零命中時打 vector service（離線自動跳過）")
    args = ap.parse_args(argv)

    if not args.queries.exists():
        print(f"queries 不存在：{args.queries}（先跑 genqueries.py）", file=sys.stderr)
        return 1
    entries = parse_memory_index(args.memory_dir)
    if not entries:
        print(f"index 無 atom：{args.memory_dir}", file=sys.stderr)
        return 1
    queries = load_queries(args.queries)
    cfg = load_retrieval_config()

    vector_fn = None
    vector_status = "off"
    if args.with_vector:
        vector_fn = make_vector_fn(cfg)
        vector_status = "on" if vector_fn else "offline(skipped)"

    t0 = time.time()
    m = evaluate(queries, entries,
                 bm25_min_score=cfg["bm25_min_score"],
                 bm25_top_k=cfg["bm25_top_k"],
                 vector_fn=vector_fn)
    elapsed = time.time() - t0

    print(f"atoms={len(entries)}  bm25(min_score={cfg['bm25_min_score']}, "
          f"top_k={cfg['bm25_top_k']})")
    print_report(m, elapsed, vector_status)
    if args.baseline:
        compare_baseline(m, args.baseline, use_color=sys.stdout.isatty())
    return 0


if __name__ == "__main__":
    sys.exit(main())
