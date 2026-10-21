"""wg_entrypoint.py — 切入點契約：程式問 → 卡教 → LLM 判 → 留帳回看。

登錄表 workflow/entrypoints.json（程式碼根，版控資料）每列一個「程式停下來要 LLM 判斷」的位置。
本模組只查表、不寫死任何代號：
- load_registry()               讀登錄表；讀不到或格式壞了回空表並浮 stderr（不擋任何事）
- match_entries(text, path)     問句裡出現某列的規則名或識別字樣、且那列登記了這條路 → 那幾列
- card_pool(state)              看得到的卡（全域＋state 記的專案層／公司層索引；scope 可見性、被取代的卡照 SessionStart 同一套）
- cards_for_entry(row, pool)    先取卡片 Entry 欄命中的卡，再拿那列的規則名＋識別字樣當 trigger 查詢當退路
- judgment_cards(text, path)    上面三步串起來，只取知識段、總預算內截斷，回要接在問句後面的那段文字
- health_block()                健檢：RULES 裡沒登錄的規則名、登錄表寫錯的規則名、卡片寫了登錄表沒有的代號——只列不擋
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import CODE_DIR, MEMORY_DIR, DEFAULTS as CORE_DEFAULTS, _estimate_tokens

sys.path.insert(0, str(CODE_DIR / "lib"))   # atom_index_json（與 wg_atoms 同一個程式碼根）

REGISTRY_PATH = CODE_DIR / "workflow" / "entrypoints.json"
_TRUNCATE_MIN_TOKENS = 40     # 剩下的預算不到這麼多就不截半張卡，整張跳過（只剩標題沒有判準等於沒送）

_REGISTRY_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def load_registry(path: Optional[Path] = None) -> Dict[str, Any]:
    """登錄表 → {"entrypoints": [...], "not_entrypoints": {...}}。讀不到或格式壞了回空表並印 stderr：
    登錄表壞掉只會讓問句沒有卡，不能讓任何閘跟著壞。同一行程內依 mtime 快取。"""
    p = Path(path) if path else REGISTRY_PATH
    try:
        mtime = p.stat().st_mtime
    except OSError as e:
        print(f"[Guardian:Entrypoint] 切入點登錄表讀不到，這次不接判準卡：{p}（{type(e).__name__}）", file=sys.stderr)
        return {"entrypoints": [], "not_entrypoints": {}}
    hit = _REGISTRY_CACHE.get(str(p))
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        entries, skip = data.get("entrypoints") or [], data.get("not_entrypoints") or {}
        if not isinstance(entries, list) or not isinstance(skip, dict):
            raise TypeError("entrypoints 要是陣列、not_entrypoints 要是物件")
        rows = [r for r in entries if isinstance(r, dict) and r.get("id")]
        reg = {"entrypoints": rows, "not_entrypoints": dict(skip)}
    except (OSError, ValueError, AttributeError, TypeError) as e:
        print(f"[Guardian:Entrypoint] 切入點登錄表格式壞了，這次不接判準卡：{p}（{type(e).__name__}: {e}）", file=sys.stderr)
        return {"entrypoints": [], "not_entrypoints": {}}
    _REGISTRY_CACHE[str(p)] = (mtime, reg)
    return reg


def _keys(row: Dict[str, Any]) -> List[str]:
    """一列的識別字串：規則名＋識別字樣（去空、保序去重）。"""
    out: List[str] = []
    for s in list(row.get("rules") or []) + list(row.get("markers") or []):
        s = str(s).strip()
        if s and s not in out:
            out.append(s)
    return out


def match_entries(text: str, path: str, registry: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """問句 text 是從 path 這條路問的：登錄表裡登記了這條路、而且規則名或識別字樣出現在問句裡的列（照登錄表順序）。"""
    if not text:
        return []
    reg = registry if registry is not None else load_registry()
    return [row for row in reg["entrypoints"]
            if path in (row.get("paths") or []) and any(k in text for k in _keys(row))]


def _index_atoms(mem_dir: Path) -> List[Dict[str, Any]]:
    try:
        from atom_index_json import load_atom_index_json
        return list(load_atom_index_json(Path(mem_dir)).get("atoms") or [])
    except Exception as e:  # noqa: BLE001  索引壞了這次沒卡，浮 stderr
        print(f"[Guardian:Entrypoint] 讀卡片索引失敗（{mem_dir}），這次不接判準卡：{type(e).__name__}: {e}", file=sys.stderr)
        return []


def card_pool(state: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """看得到的卡：[{name, file, triggers, entry}]。全域索引，加上 state 記的專案層、公司層索引（SessionStart 建池時記的位置）；
    scope 可見性用同一支 entry_visible（沒有 state 時沒有身份 → personal／role 卡不給）；被取代的卡不進。"""
    from wg_atoms import entry_visible, superseded_names_cached
    ident = (state or {}).get("user_identity") or {}
    idx = (state or {}).get("atom_index") or {}
    user, roles = ident.get("user"), ident.get("roles")
    project_root = Path(idx["project_root"]) if idx.get("project_root") else None
    layers: List[Tuple[Path, Path, bool]] = [(MEMORY_DIR, MEMORY_DIR.parent, False)]    # (索引目錄, 相對路徑的根, 是專案層)
    if idx.get("project_memory_dir"):
        pm = Path(idx["project_memory_dir"])
        layers.append((pm, pm.parent, True))
    if idx.get("org_base"):
        layers.append((Path(idx["org_base"]) / "memory", Path(idx["org_base"]), False))
    superseded = set(idx.get("superseded") or []) | set(superseded_names_cached(MEMORY_DIR))
    pool: List[Dict[str, Any]] = []
    seen = set()
    for mem_dir, base, is_project in layers:
        for a in _index_atoms(mem_dir):
            name, rel = str(a.get("name") or ""), str(a.get("path") or "")
            if not name or name in seen or name in superseded or not entry_visible(rel, user, roles):
                continue
            # 與 build_candidate_pool 同規則：專案層 `_AIAtoms/` 相對專案根，其餘相對索引目錄的上一層
            root = project_root if (is_project and project_root and rel.startswith("_AIAtoms/")) else base
            seen.add(name)
            pool.append({"name": name, "file": root / rel if rel else mem_dir / f"{name}.md",
                         "triggers": [str(t).lower() for t in a.get("triggers") or []],
                         "entry": [str(e).strip() for e in a.get("entry") or [] if str(e).strip()]})
    return pool


def cards_for_entry(row: Dict[str, Any], pool: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], str]]:
    """一個切入點的判準卡：[(卡, "entry"|"keyword")]。先取 Entry 欄寫了這個代號的卡（照池的順序），
    再拿這列的規則名＋識別字樣當查詢，比卡的 trigger（與 UPS 同一支比對），命中數多的在前。"""
    from wg_atoms import count_trigger_hits
    eid = str(row.get("id"))
    bound = [c for c in pool if eid in c["entry"]]
    query = " ".join(_keys(row)).lower()
    names = {c["name"] for c in bound}
    hits = [(count_trigger_hits(c["triggers"], query), c) for c in pool if c["name"] not in names]
    keyword = [c for n, c in sorted(hits, key=lambda x: (-x[0], x[1]["name"])) if n > 0]
    return [(c, "entry") for c in bound] + [(c, "keyword") for c in keyword]


def _knowledge(card: Dict[str, Any], max_tokens: Optional[int] = None) -> str:
    """卡的知識段本文（不含 `## 知識` 標題）；給 max_tokens 就照 wg_atoms 同一支截斷（尾端標「已截斷」）。讀不到回空字串。"""
    from wg_atoms import _extract_named_section
    try:
        content = Path(card["file"]).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return ""
    sec = _extract_named_section(content, "知識", max_tokens=max_tokens)
    return sec.split("\n", 1)[1].strip() if sec and "\n" in sec else ""


def inject_budget(config: Optional[Dict[str, Any]] = None) -> int:
    default = CORE_DEFAULTS["entrypoint"]["inject_budget_tokens"]
    try:
        return int(((config or {}).get("entrypoint") or {}).get("inject_budget_tokens", default))
    except (TypeError, ValueError):
        return default


def judgment_cards(text: str, path: str, *, state: Optional[Dict[str, Any]] = None,
                   config: Optional[Dict[str, Any]] = None, registry: Optional[Dict[str, Any]] = None,
                   pool: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """問句 → {"entries": [代號], "cards": [{"name", "entries", "via"}], "truncated": bool, "note": "<要接在問句後面的文字>"}。
    沒認出切入點 → entries 空；認出但沒卡 → note 空字串（不接、不印「無」）。
    一張卡同時是幾個切入點的判準卡只送一次，標題列出全部代號。整個問句先送 Entry 綁定的卡、再送關鍵字退路的卡
    （同時認出好幾個切入點時，前一列的退路卡不會擠掉後一列綁定的卡）。總預算 entrypoint.inject_budget_tokens，
    超過就截斷最後一張（尾端標「已截斷」）、後面的不送，truncated=True。"""
    rows = match_entries(text, path, registry)
    out: Dict[str, Any] = {"entries": [str(r["id"]) for r in rows], "cards": [], "truncated": False, "note": ""}
    if not rows:
        return out
    pool = pool if pool is not None else card_pool(state)
    picked: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        for card, via in cards_for_entry(row, pool):
            got = picked.setdefault(card["name"], {"card": card, "entries": [], "via": via})
            if via == "entry":
                got["via"] = "entry"      # 別列只靠關鍵字命中、這列綁定 → 算綁定
            if str(row["id"]) not in got["entries"]:
                got["entries"].append(str(row["id"]))
    ordered = sorted(picked.items(), key=lambda kv: kv[1]["via"] != "entry")     # 穩定排序：綁定在前、各自保持原序
    budget, used, blocks = inject_budget(config), 0, []
    for name, got in ordered:
        body = _knowledge(got["card"])
        if not body:
            continue
        cost = _estimate_tokens(body)
        if used + cost > budget:
            out["truncated"] = True
            left = budget - used
            body = _knowledge(got["card"], max_tokens=left) if left >= _TRUNCATE_MIN_TOKENS else ""
            if not body:
                break
            cost = left
        blocks.append(f"判準卡（{'、'.join(got['entries'])}）：{name}\n{body}")
        out["cards"].append({"name": name, "entries": got["entries"], "via": got["via"]})
        used += cost
        if out["truncated"]:
            break
    out["note"] = "\n\n".join(blocks)
    return out


def _rule_names() -> List[str]:
    import wg_release_rules
    return list(wg_release_rules.RULES)


def health_block(registry: Optional[Dict[str, Any]] = None, rule_names: Optional[List[str]] = None,
                 index_atoms: Optional[List[Dict[str, Any]]] = None, shown: int = 12) -> Dict[str, List[str]]:
    """週健檢區塊（tools/health-weekly.py 讀）：只列不擋，全進 info。
    - RULES 裡既沒登錄、也不在 not_entrypoints 的規則名（要不要登錄由人判）
    - 登錄表寫了、RULES 沒有的規則名（改名或打錯，那列靠規則名就認不到）
    - 卡片 Entry 寫了、登錄表沒有的代號（卡送不到）
    - 登錄表重複的代號"""
    reg = registry if registry is not None else load_registry()
    names = rule_names if rule_names is not None else _rule_names()
    atoms = index_atoms if index_atoms is not None else _index_atoms(MEMORY_DIR)
    ids = [str(r["id"]) for r in reg["entrypoints"]]
    registered = {s for r in reg["entrypoints"] for s in r.get("rules") or []}
    info: List[str] = []

    def _line(label: str, items: List[str]) -> None:
        if items:
            more = f"…等 {len(items)} 條" if len(items) > shown else ""
            info.append(f"切入點登錄表：{label} {len(items)} 條：{'、'.join(items[:shown])}{more}（workflow/entrypoints.json；只列不擋）")

    _line("RULES 有規則沒登錄、也沒標不是切入點",
          [n for n in names if n not in registered and n not in reg["not_entrypoints"]])
    _line("登錄表寫的規則名 RULES 沒有", sorted(registered - set(names)))
    _line("卡片 Entry 寫了登錄表沒有的代號",
          [f"{a.get('name')}→{e}" for a in atoms for e in a.get("entry") or [] if str(e) not in ids])
    _line("登錄表代號重複", sorted({i for i in ids if ids.count(i) > 1}))
    return {"info": info}
