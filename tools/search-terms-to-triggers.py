#!/usr/bin/env python3
"""search-terms-to-triggers.py — 把 Claude 主動搜過的詞列成「卡片觸發詞候選」（只出清單，不改卡）。

做什麼：取 injection-miss-report.py 掃到的 memory_search 搜尋句，切成詞，逐詞對 memory/_atom_index.json 的每張卡比：
詞出現在卡名、標題（# 行）或知識段（## 知識／## 印象），而且這張卡現有的觸發詞都不會因為這個詞命中
（比對規則跟 UPS 注入同一支 wg_atoms.any_trigger_hit：英數詞整字比、中文子字串）→ 列成候選「卡名 ← 詞」。
略過：
  - 泛用詞（lib.atom_locations.is_generic_lexicon_term，跟詞庫自學同一份黑名單）；
  - 太廣：一個詞出現在超過 TOO_BROAD_CARDS 張卡，當觸發詞會一次叫出一大堆卡，只列名不展開；
  - 不相關：一次搜尋切出多個詞時，卡片至少要命中其中 2 個詞才算跟這次搜尋有關（只沾到一個字的不列）。
輸出：重寫 memory/_staging/trigger-candidates.md；要採用就用 atom_edit_meta 把詞加進該卡 Trigger。
不餵既有詞庫自學：realm-lexicon-learned.json／taxonomy-lexicon-learned.json 是「詞 → 範疇」的分類詞庫，
不是「詞 → 卡片觸發詞」，餵進去會變成分類依據而不是觸發詞。
怎麼跑：python ~/.claude/tools/search-terms-to-triggers.py [--sessions 150]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent   # 程式碼根：lib／hooks／tools 都在本檔那棵樹
sys.path[:0] = [str(CODE_DIR), str(CODE_DIR / "hooks")]
from lib.atom_locations import is_generic_lexicon_term  # noqa: E402
from lib.atom_spec import KNOWLEDGE_SECTIONS  # noqa: E402
from lib.project_root import claude_data_dir  # noqa: E402
from wg_atoms import any_trigger_hit  # noqa: E402

CLAUDE_DIR = claude_data_dir()   # 資料根：索引與 _staging 在這裡（WG_CLAUDE_DIR 或 ~/.claude）
_SPEC = importlib.util.spec_from_file_location("injection_miss_report", CODE_DIR / "tools" / "injection-miss-report.py")
imr = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(imr)

INDEX_PATH = CLAUDE_DIR / "memory" / "_atom_index.json"
OUT_PATH = CLAUDE_DIR / "memory" / "_staging" / "trigger-candidates.md"
TOO_BROAD_CARDS = 5  # 一個詞出現在超過這麼多張卡就不當觸發詞（會一次注入一大堆）
TITLE_RE = re.compile(r"^# (.+)$", re.MULTILINE)


def _knowledge(content: str) -> str:
    parts = []
    for sec in KNOWLEDGE_SECTIONS:
        m = re.search(r"^##[ \t]+" + re.escape(sec) + r"[ \t]*\n([\s\S]*?)(?=^## |\Z)", content, re.MULTILINE)
        if m:
            parts.append(m.group(1))
    return "\n".join(parts)


def load_cards(index_path: Path = INDEX_PATH, base_dir: Path = CLAUDE_DIR):
    """索引 → [{name, triggers, head, body}]（head＝卡名＋標題，body＝知識段，皆小寫）。讀不到的卡略過並計數。"""
    atoms = json.loads(index_path.read_text(encoding="utf-8")).get("atoms") or []
    cards, missing = [], 0
    for a in atoms:
        try:
            content = (base_dir / a["path"]).read_text(encoding="utf-8")
        except (OSError, KeyError):
            missing += 1
            continue
        title = TITLE_RE.search(content)
        cards.append({
            "name": a["name"],
            "triggers": [str(t).strip().lower() for t in a.get("triggers") or [] if str(t).strip()],
            "head": (a["name"] + "\n" + (title.group(1) if title else "")).lower(),
            "body": _knowledge(content).lower(),
        })
    if missing:
        print(f"[search-terms-to-triggers] 索引裡 {missing} 張卡讀不到檔，已略過", file=sys.stderr)
    return cards


def _where(term: str, card: dict):
    if any_trigger_hit([term], card["head"]):
        return "標題"
    if any_trigger_hit([term], card["body"]):
        return "知識"
    return None


def _query_pairs(terms, hit, too_broad, triggers):
    """一次搜尋的詞 → [(卡名, 詞, 出現處)]：卡跟這次搜尋有關、詞不太廣、卡的觸發詞沒涵蓋這個詞。"""
    touched = Counter()
    for t in terms:
        touched.update(hit[t].keys())
    out = []
    for name, k in touched.items():
        if len(terms) >= 2 and k < 2:
            continue  # 多詞搜尋只沾到其中一個詞：這張卡跟這次搜尋無關
        out.extend((name, t, hit[t][name]) for t in terms
                   if name in hit[t] and t not in too_broad and not any_trigger_hit(triggers[name], t))
    return out


def find_candidates(queries, cards):
    """搜尋句清單 → (候選 [(卡名, 詞, 幾次搜尋, 出現處)], 詞數, 泛用詞數, 太廣 {詞: 內容含此詞的卡數})。"""
    all_terms = {t for q in queries for t in imr.split_terms(q)}
    generic = {t for t in all_terms if is_generic_lexicon_term(t)}
    hit = {t: {c["name"]: w for c in cards if (w := _where(t, c))} for t in all_terms - generic}
    too_broad = {t: len(names) for t, names in hit.items() if len(names) > TOO_BROAD_CARDS}
    triggers = {c["name"]: c["triggers"] for c in cards}
    pairs, where = Counter(), {}
    for q in queries:
        terms = [t for t in imr.split_terms(q) if t not in generic]
        for name, t, w in _query_pairs(terms, hit, too_broad, triggers):
            pairs[(name, t)] += 1
            where[(name, t)] = w
    candidates = sorted(((name, t, n, where[(name, t)]) for (name, t), n in pairs.items()),
                        key=lambda x: (-x[2], x[0], x[1]))
    return candidates, len(all_terms), len(generic), too_broad


def render_md(sessions: int, n_queries: int, n_terms: int, candidates, generic: int, too_broad: dict) -> str:
    lines = [
        "# 觸發詞候選（Claude 主動搜過、卡片內容有、Trigger 沒涵蓋）",
        "",
        "> 由 `tools/search-terms-to-triggers.py` 產生，每次重寫；不自動改卡。"
        "採用：`atom_edit_meta` 把詞加進該卡 Trigger；不採用就不理它。",
        f"> 依據：最近 {sessions} 場 transcript 的 memory_search {n_queries} 次、切出 {n_terms} 個詞"
        f"（略過泛用詞 {generic} 個、出現在超過 {TOO_BROAD_CARDS} 張卡的太廣詞 {len(too_broad)} 個；"
        "多詞搜尋只沾到一個詞的卡不列）。",
        "",
        "| 卡 | 候選詞 | 幾次搜尋 | 詞出現在 |",
        "|---|---|---|---|",
    ]
    lines.extend(f"| {name} | {term} | {n} | {where} |" for name, term, n, where in candidates)
    if not candidates:
        lines.append("| （無） | | | |")
    if too_broad:
        lines += ["", f"太廣（出現在超過 {TOO_BROAD_CARDS} 張卡，不當觸發詞）：" +
                  "、".join(f"{t}（{k}）" for t, k in sorted(too_broad.items(), key=lambda x: (-x[1], x[0])))]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="把 Claude 主動搜過的詞列成卡片觸發詞候選（不改卡）")
    ap.add_argument("--sessions", type=int, default=150, help="掃最近幾場（預設 150）")
    args = ap.parse_args()
    _files, turns, _bad = imr.scan(imr.PROJECTS_DIR, args.sessions)
    queries = [q for t in turns for q in t["queries"]]
    candidates, n_terms, generic, too_broad = find_candidates(queries, load_cards())
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render_md(args.sessions, len(queries), n_terms, candidates, generic, too_broad),
                        encoding="utf-8", newline="\n")
    print(f"memory_search {len(queries)} 次、詞 {n_terms} 個：泛用略過 {generic}、太廣 {len(too_broad)}；"
          f"候選 {len(candidates)} 條 → {OUT_PATH}")
    print(f"TRIGGER_CANDIDATES DONE terms={n_terms} candidates={len(candidates)}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
