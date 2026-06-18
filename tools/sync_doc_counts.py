#!/usr/bin/env python3
"""sync_doc_counts.py — 人讀文件 atom 計數單一真相同步（SoT = memory/_atom_index.json）。

根治「atom 計數跨人讀文件 chronic drift」（2026-06-17 手動校正即此痛點：總數 32/38/48
三方矛盾且全落後磁碟）。**只動明確標記的 live-count 欄位**：
  `<!-- atom-total -->54<!-- /atom-total -->`        ← 純總數（含 ~NN 近似寫法）
  `<!-- atom-breakdown -->54 atoms：…<!-- /atom-breakdown -->`  ← 總數 + realm/domain 分解
不碰未標記的歷史敘述（SPEC「V4 全域 ~30 atoms」/ BM25 文件「17 atoms」等過往事實），
故零誤改史料——標記＝唯一授權改寫面。

  --check  drift → stderr 列差異 + exit 1（可作 pre-commit / run_verify 閘）
  --write  就地把標記內容改成 SoT 實算
靜默自動推進：`sync-memory-index.py`（atom_write 經 server.js 背景 fire-and-forget 觸發）
末尾呼叫 `sync(root, write=True)`，故每次 atom 增刪/搬移後計數自動跟上、不再進對話雜訊。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

CLAUDE_DIR = Path.home() / ".claude"
ATOM_INDEX_REL = "memory/_atom_index.json"

# 已埋標記的 live-count 人讀文件（相對 claude_root）。歷史/次要文件刻意不列（防誤改史料）。
DOC_FILES = ["TECH.md", "_AIDocs/_INDEX.md", "_AIDocs/DocIndex-System.md"]

# local domain 顯示序：已知根固定在前，其餘（如 Continuity / Else）按字母接後。
KNOWN_DOMAIN_ORDER = ["World", "Tools", "MemDev", "OS"]

# marker id → compute_counts() 回傳 key。component marker 供 prose 句內逐項標記
# （如「core <!-- atom-core -->14<!-- /atom-core --> + …」），不破壞解說文字。
_MARKERS = {
    "atom-total": "total",
    "atom-breakdown": "breakdown",
    "atom-core": "core",
    "atom-feedback": "feedback",
    "atom-failmode": "failmode",
    "atom-local": "local",
}


def compute_counts(root: Path) -> Dict[str, str]:
    """讀 _atom_index.json（唯一機器源）→ 算 total 與 realm/domain 分解字串。

    分類純依 index path 前綴（與 lib.atom_locations 同語意）：
      memory/…                     → core
      _AIDocs/Failures/feedback-*  → feedback；其餘 _AIDocs/Failures/ → 失敗模式
      _AIDocs/_atoms/<domain>/…    → local（依 Lv1 domain 分組）
    """
    data = json.loads((root / ATOM_INDEX_REL).read_text(encoding="utf-8-sig"))
    atoms = data.get("atoms", [])
    core = feedback = failmode = 0
    locals_by_dom: Counter = Counter()
    for a in atoms:
        p = a.get("path", "")
        nm = a.get("name", "")
        if p.startswith("_AIDocs/_atoms/"):
            dom = p[len("_AIDocs/_atoms/"):].split("/")[0] or "Else"
            locals_by_dom[dom] += 1
        elif p.startswith("_AIDocs/Failures/"):
            if nm.startswith("feedback-"):
                feedback += 1
            else:
                failmode += 1
        else:  # memory/… = core
            core += 1
    total = len(atoms)
    local_total = sum(locals_by_dom.values())
    ordered = ([d for d in KNOWN_DOMAIN_ORDER if d in locals_by_dom]
               + sorted(d for d in locals_by_dom if d not in KNOWN_DOMAIN_ORDER))
    dom_str = "/".join(f"{d}{locals_by_dom[d]}" for d in ordered)
    breakdown = (f"{total} atoms：core {core} + feedback {feedback} + "
                 f"失敗模式 {failmode} + local {local_total}〔{dom_str}〕")
    return {
        "total": str(total), "breakdown": breakdown,
        "core": str(core), "feedback": str(feedback),
        "failmode": str(failmode), "local": str(local_total),
    }


def _apply(text: str, vals: Dict[str, str]) -> Tuple[str, int]:
    """把 text 內所有已知 marker 的夾心內容換成 vals。回 (新文字, marker 命中數)。"""
    hits = 0
    for marker, key in _MARKERS.items():
        pat = re.compile(r"(<!-- " + marker + r" -->).*?(<!-- /" + marker + r" -->)", re.S)

        def repl(m: "re.Match", _v=vals[key]) -> str:
            nonlocal hits
            hits += 1
            return m.group(1) + _v + m.group(2)

        text = pat.sub(repl, text)
    return text, hits


def sync(root: Path, write: bool) -> Tuple[bool, List[str]]:
    """同步（或檢查）所有 DOC_FILES 的計數標記。回 (有無 drift, 訊息列)。"""
    vals = compute_counts(root)
    drift = False
    msgs: List[str] = []
    for rel in DOC_FILES:
        fp = root / rel
        if not fp.exists():
            continue
        # newline="" 保留各檔原始行尾（repo 混 LF/CRLF）：marker 替換不含換行，故行尾零變動。
        # 用 read_text/write_text（newline=None）會把 \n→os.linesep 整檔 CRLF 化、製造假 drift。
        with open(fp, "r", encoding="utf-8-sig", newline="") as f:
            text = f.read()
        new, hits = _apply(text, vals)
        if hits == 0 or new == text:
            continue  # 無 marker 或已同步 → 跳過
        drift = True
        if write:
            with open(fp, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            msgs.append(f"[sync-doc-counts] updated {rel}")
        else:
            msgs.append(f"[sync-doc-counts] drift: {rel}")
    return drift, msgs


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync atom counts in human docs from _atom_index.json SoT")
    ap.add_argument("--check", action="store_true", help="drift 偵測，任一 drift → exit 1")
    ap.add_argument("--write", action="store_true", help="就地修正標記內容")
    ap.add_argument("--root", type=Path, default=CLAUDE_DIR)
    a = ap.parse_args()
    drift, msgs = sync(a.root, write=a.write)
    for m in msgs:
        print(m, file=sys.stderr)
    if a.write:
        print(f"[sync-doc-counts] atoms={compute_counts(a.root)['total']}")
        return 0
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
