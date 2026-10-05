"""memory_search.py — 原子記憶讀取端：一句話查記憶，回穩定 JSON。

做什麼：把 UserPromptSubmit 注入用的同一條檢索管線（候選池 → trigger / BM25 / vector →
RRF 融合）包成可呼叫的函式，給 MCP `memory_search`、`atom_io_cli search`、
`tools/memory-search.py` 三個入口共用。只讀不寫。

契約（schema_version 1）：
  search(prompt, cwd, *, user=None, roles=None, top_k=8, use_vector=True) -> {
    "schema_version": 1,
    "mode": "trigger+bm25" | "trigger+bm25+vector",
    "warnings": [str, ...],          # 同名遮蔽、向量路關閉、身份缺席等 fail-open 訊號
    "results": [{name, path, rel_path, scope, source, score, excerpt,
                 author, audience, tags, status}, ...],
  }
身份：user=None 或 "unknown" → 不讀任何 personal；roles=None → 不讀任何 role 層。
入口要「以現用身份查」時用 default_identity(cwd) 取 (user, roles) 再傳入。
同名跨層：project > org > global 先到先贏，被遮蔽者進 warnings。
"""
from __future__ import annotations

import copy
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_CLAUDE_ROOT = Path(__file__).resolve().parent.parent
_HOOKS_DIR = _CLAUDE_ROOT / "hooks"
for _p in (_HOOKS_DIR, _HOOKS_DIR / "handlers", _CLAUDE_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import wg_core  # noqa: E402
import wg_atoms  # noqa: E402
import ups_search  # noqa: E402
from wg_atoms import AtomEntry  # noqa: E402

SCHEMA_VERSION = 1
EXCERPT_CHARS = 120
_FRONTMATTER_KEYS = ("Author", "Audience", "Tags", "Status")
_META_RE = re.compile(r"^-\s+(\w[\w-]*):\s*(.+)$")


def default_identity(cwd: str) -> Tuple[str, List[str]]:
    """入口預設身份：現用 OS 帳號與其職能（wg_roles 單源）。"""
    from wg_roles import get_current_user, load_user_role
    user = get_current_user()
    roles = list(load_user_role(cwd, user).get("roles") or [])  # 查不到職能＝[]，不預設 programmer
    return user, roles


def _atom_path(entry: AtomEntry, base_dir: Path) -> Path:
    name, rel_path, _t = entry
    return (base_dir / rel_path) if rel_path else (base_dir / "memory" / f"{name}.md")


def _parse_hit_file(text: Optional[str]) -> Dict[str, str]:
    """命中檔一次讀：frontmatter 四欄（對拍 indexer META_RE 樣式）＋ `## 知識` 第一條摘要。缺欄回空字串。"""
    out = {k.lower(): "" for k in _FRONTMATTER_KEYS}
    out["excerpt"] = ""
    if not text:
        return out
    in_knowledge = False
    for line in text.split("\n"):
        if line.startswith("## "):
            in_knowledge = line[3:].strip() == "知識"
            continue
        if in_knowledge:
            if line.startswith("- ") and not out["excerpt"]:
                out["excerpt"] = line[2:].strip()[:EXCERPT_CHARS]
            continue
        m = _META_RE.match(line)
        if m and m.group(1) in _FRONTMATTER_KEYS:
            out[m.group(1).lower()] = m.group(2).strip()
    return out


def _layer_base(pool: Dict[str, Any], layer: str, rel_path: str) -> Path:
    """與 ups_search 同一套 base 規則：global 相對 ~/.claude；project 的 `_AIAtoms/` 相對專案根，其餘相對 .claude。"""
    if layer == "global":
        return wg_atoms.MEMORY_DIR.parent
    if layer == "org":
        return Path(pool.get("org_base") or wg_atoms.MEMORY_DIR.parent)
    if rel_path.startswith("_AIAtoms/") and pool.get("project_root"):
        return Path(pool["project_root"])
    return Path(pool["project_memory_dir"]).parent


def _dedup_layers(pool: Dict[str, Any], warnings: List[str]) -> None:
    """同名跨層先到先贏 project > org > global；被遮蔽者移出池並記 warnings（就地改 pool）。
    同一實體檔從兩層看到（cwd 在 ~/.claude 時 project 層＝全域記憶）不算遮蔽、不警告。"""
    taken: Dict[str, Tuple[str, Path]] = {}
    for layer in ("project", "org", "global"):
        kept: List[AtomEntry] = []
        for entry in pool.get(layer) or []:
            abs_path = _atom_path(entry, _layer_base(pool, layer, entry[1]))
            if entry[0] not in taken:
                taken[entry[0]] = (layer, abs_path)
                kept.append(entry)
                continue
            winner_layer, winner_path = taken[entry[0]]
            if winner_path != abs_path:
                warnings.append(f"同名被遮蔽: {entry[0]} ({layer}，{winner_layer} 層優先)")
        pool[layer] = kept


def _search_config(use_vector: bool, top_k: int, warnings: List[str]) -> Dict[str, Any]:
    """hook config 副本：BM25 交給本模組對整池跑（關掉 ups 的 global BM25 閘）；use_vector=False 直接關向量路。"""
    cfg = copy.deepcopy(wg_core.load_config())
    if cfg.get("_config_parse_failed"):
        warnings.append("workflow/config.json 解析失敗，已用預設值")
    vs = dict(cfg.get("vector_search") or {})
    if use_vector and not vs.get("enabled", True):
        warnings.append("向量路已由 config 關閉（vector_search.enabled=false）")
    if not use_vector:
        vs["enabled"] = False
    vs["global_layer"] = "bm25"
    vs["bm25_gate_max_trigger_hits"] = -1
    vs["bm25_top_k"] = top_k
    cfg["vector_search"] = vs
    return cfg


def search(
    prompt: str, cwd: str, *,
    user: Optional[str] = None, roles: Optional[List[str]] = None,
    top_k: int = 8, use_vector: bool = True,
) -> Dict[str, Any]:
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("query is empty")
    top_k = max(1, int(top_k))
    warnings: List[str] = []
    if not user or user == "unknown":
        user = None
        warnings.append("未指定使用者身份：personal 層未納入")

    org_root = wg_core.org_memory_root()
    pool = wg_atoms.build_candidate_pool(cwd, user, roles, org_root=str(org_root) if org_root else None)
    _dedup_layers(pool, warnings)
    cfg = _search_config(use_vector, top_k, warnings)
    vs = cfg["vector_search"]

    state: Dict[str, Any] = {
        "atom_index": pool,
        "user_identity": {"user": user, "roles": list(roles or []), "management": False},
        "session": {"cwd": cwd},
        "injected_atoms": [],
    }
    prompt_lower = prompt.lower()
    lines: List[str] = []
    matched, atom_source, all_atoms, sem_atoms, _hints, _alias, _intent, caches = (
        ups_search.collect_matched_atoms("memory-search", state, cfg, prompt, prompt_lower, lines)
    )

    # BM25 對整池一次跑（不受 hook 的 global-only 與 trigger 閘限制），命中未在池者併入。
    by_name = {e[0][0]: e for e in all_atoms}
    bm25_route = [
        e[0] for e in wg_atoms.bm25_match(
            prompt, [e[0] for e in all_atoms],
            min_score=vs.get("bm25_min_score", wg_atoms.BM25_MIN_SCORE_DEFAULT), top_k=top_k,
        )
    ]
    for name in bm25_route:
        if name in atom_source:
            continue
        matched.append(by_name[name])
        atom_source[name] = "bm25"

    # 分數：RRF（與 ups_search._fused_key 同式：rrf × exp(gain × activation rank)）；legacy 以名次 1/(rank+1)。
    scores: Dict[str, float] = {}
    if vs.get("fusion", "rrf") == "rrf":
        trigger_route = [e[0][0] for e in all_atoms if atom_source.get(e[0][0]) == "trigger"]
        trigger_route.sort(
            key=lambda n: wg_atoms.count_trigger_hits(by_name[n][0][2], prompt_lower), reverse=True,
        )
        rrf = wg_atoms.rrf_fuse({
            "trigger": trigger_route,
            "bm25": bm25_route,
            "vector": [s[0] for s in sem_atoms],
        })
        gain = float(vs.get("rrf_activation_gain", wg_atoms.RRF_ACTIVATION_GAIN))
        for entry, base_dir in matched:
            rank = wg_atoms.compute_injection_rank(
                entry[0], _atom_path(entry, base_dir).parent, cfg, caches["access"])
            scores[entry[0]] = rrf.get(entry[0], 0.0) * math.exp(gain * rank)
        matched.sort(key=lambda e: scores[e[0][0]], reverse=True)
    else:
        for i, (entry, _b) in enumerate(matched):
            scores[entry[0]] = 1.0 / (i + 1)

    results: List[Dict[str, Any]] = []
    for entry, base_dir in matched[:top_k]:
        name, rel_path, _t = entry
        path = _atom_path(entry, base_dir)
        meta = _parse_hit_file(wg_atoms.read_atom_text(path, caches["content"]))
        results.append({
            "name": name,
            "path": str(path),
            "rel_path": rel_path,
            "scope": pool["scopes"].get(name, "global"),
            "source": atom_source.get(name, "bm25"),
            "score": round(scores.get(name, 0.0), 6),
            "excerpt": meta["excerpt"],
            "author": meta["author"],
            "audience": meta["audience"],
            "tags": meta["tags"],
            "status": meta["status"],
        })

    mode = "trigger+bm25" + ("+vector" if vs.get("enabled", True) else "")
    return {"schema_version": SCHEMA_VERSION, "mode": mode, "warnings": warnings, "results": results}


def format_table(result: Dict[str, Any]) -> str:
    """人讀表格：標頭 `name | scope | source | score | excerpt`，warnings 列在最前。"""
    out = [f"[memory_search] mode={result['mode']} hits={len(result['results'])}"]
    out.extend(f"⚠ {w}" for w in result.get("warnings") or [])
    out.append("name | scope | source | score | excerpt")
    for r in result["results"]:
        out.append(f"{r['name']} | {r['scope']} | {r['source']} | {r['score']:.4f} | {r['excerpt']}")
        out.append(f"    {r['path']}")
    return "\n".join(out)
