"""wg_entrypoint.py — 切入點契約：程式問 → 卡教 → LLM 判 → 留帳回看。

登錄表 workflow/entrypoints.json（程式碼根，版控資料）每列一個「程式停下來要 LLM 判斷」的位置。
本模組只查表、不寫死任何代號：
- load_registry()               讀登錄表；讀不到或格式壞了回空表並浮 stderr（不擋任何事）
- match_entries(text, path)     問句裡出現某列的規則名或識別字樣、且那列登記了這條路 → 那幾列
- card_pool(state)              看得到的卡（全域＋state 記的專案層／公司層索引；scope 可見性、被取代的卡照 SessionStart 同一套）
- cards_for_entry(row, pool)    先取卡片 Entry 欄命中的卡，再拿那列的規則名＋識別字樣當 trigger 查詢當退路
- judgment_cards(text, path)    上面三步串起來，只取知識段、總預算內截斷，回要接在問句後面的那段文字
- entry_note(text, path, …)     問的那一刻的單一入口（Stop 擋訊息與續跑提醒、PreToolUse deny、MCP 回覆、子代理 prompt 都呼叫它）：
                                挑卡＋每個切入點記一筆帳到 Logs/guard-entry.jsonl，回要接在問句後面的文字；
                                同一個使用者回合已送過全文的卡只送一行指回（workflow/entry-sent/<sid>.json，規則 CARD_ONCE_PER_TURN）
- resolve_responses(asks, …)    依各閘自己的留帳（登錄表每列的 responses）推每次問之後 AI 的回應型；tools/entry-stats.py 用
- health_block()                健檢：RULES 裡沒登錄的規則名、登錄表寫錯的規則名、卡片寫了登錄表沒有的代號——只列不擋
"""

import json
import sys
from datetime import datetime, timezone
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
    """一個切入點的判準卡：[(卡, "entry"|"keyword")]。先放 Entry 欄寫了這個代號的卡，知識段短的在前（短卡先送、預算才夠多送幾張）；
    再拿這列的規則名＋識別字樣當查詢，比卡的 trigger（與 UPS 同一支比對），命中數多的在前、同分時知識段短的在前。"""
    from wg_atoms import count_trigger_hits
    eid = str(row.get("id"))
    size: Dict[str, int] = {}

    def _size(c: Dict[str, Any]) -> int:
        if c["name"] not in size:
            size[c["name"]] = _estimate_tokens(_knowledge(c))
        return size[c["name"]]

    bound = sorted((c for c in pool if eid in c["entry"]), key=lambda c: (_size(c), c["name"]))
    query = " ".join(_keys(row)).lower()
    names = {c["name"] for c in bound}
    hits = [(n, c) for n, c in ((count_trigger_hits(c["triggers"], query), c) for c in pool if c["name"] not in names) if n > 0]
    keyword = [c for n, c in sorted(hits, key=lambda x: (-x[0], _size(x[1]), x[1]["name"]))]
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


def inject_budget(config: Optional[Dict[str, Any]] = None, key: str = "inject_budget_tokens") -> int:
    """entrypoint.<key>：inject_budget_tokens＝每個切入點各一份；inject_budget_total＝同一則問句的總上限。壞值退預設。"""
    default = CORE_DEFAULTS["entrypoint"][key]
    try:
        return int(((config or {}).get("entrypoint") or {}).get(key, default))
    except (TypeError, ValueError):
        return default


def judgment_cards(text: str, path: str, *, state: Optional[Dict[str, Any]] = None,
                   config: Optional[Dict[str, Any]] = None, registry: Optional[Dict[str, Any]] = None,
                   pool: Optional[List[Dict[str, Any]]] = None, seen: Optional[set] = None) -> Dict[str, Any]:
    """問句 → {"entries": [代號], "cards": [{"name", "entries", "via"}], "truncated": bool, "truncated_entries": [代號],
    "note": "<要接在問句後面的文字>"}。沒認出切入點 → entries 空；認出但沒卡 → note 空字串（不接、不印「無」）。
    預算每個切入點各一份＝min(entrypoint.inject_budget_tokens, inject_budget_total ÷ 認出的切入點數)，整則加起來不超過總上限，
    切入點多時每個都分得到。先送每個切入點的綁定卡、再送各自的退路卡（_send_order），超過這個切入點的預算就截斷最後一張
    （尾端標「已截斷」）、它後面的卡不送；有卡卻沒送完的切入點都記進 truncated_entries。
    一張卡同時是幾個切入點的判準卡只送一次（算在第一個送它的切入點），標題列出它在這句裡服務的全部代號；
    綁定的那一列算綁定（via=entry）。truncated＝有任何截斷，truncated_entries＝哪幾個切入點被截。
    seen＝這個回合已送過全文的卡名：只送一行指回、不佔預算，記進 repeated（全文還在前面的對話裡）。"""
    rows = match_entries(text, path, registry)
    out: Dict[str, Any] = {"entries": [str(r["id"]) for r in rows], "cards": [], "truncated": False,
                           "truncated_entries": [], "repeated": [], "note": ""}
    if not rows:
        return out
    pool = pool if pool is not None else card_pool(state)
    per_row = [(str(row["id"]), cards_for_entry(row, pool)) for row in rows]
    serves: Dict[str, List[str]] = {}
    bound_somewhere = set()
    for eid, cards in per_row:
        for card, via in cards:
            serves.setdefault(card["name"], [])
            if eid not in serves[card["name"]]:
                serves[card["name"]].append(eid)
            if via == "entry":
                bound_somewhere.add(card["name"])
    left_total, blocks, sent = inject_budget(config, "inject_budget_total"), [], set()
    each = min(inject_budget(config), left_total // len(per_row))      # 總上限平分給認出的切入點，不讓排後面的永遠落空
    used = {eid: 0 for eid, _ in per_row}
    for eid, card in _send_order(per_row):
        name = card["name"]
        if left_total < _TRUNCATE_MIN_TOKENS:
            break
        if name in sent or eid in out["truncated_entries"]:
            continue
        if name in (seen or ()):
            blocks.append(f"判準卡（{'、'.join(serves[name])}）：{name}（本回合前面的訊息已送過全文，照那張判）")
            out["cards"].append({"name": name, "entries": serves[name], "via": "entry" if name in bound_somewhere else "keyword"})
            out["repeated"].append(name)
            sent.add(name)
            continue
        body = _knowledge(card)
        if not body:
            continue
        cost, room = _estimate_tokens(body), min(each - used[eid], left_total)
        if cost > room:
            body = _knowledge(card, max_tokens=room) if room >= _TRUNCATE_MIN_TOKENS else ""
            cost = room
            out["truncated"] = True
            out["truncated_entries"].append(eid)        # 這個切入點的預算用完：它後面的卡不送，別的切入點照送
        if body:
            blocks.append(f"判準卡（{'、'.join(serves[name])}）：{name}\n{body}")
            out["cards"].append({"name": name, "entries": serves[name], "via": "entry" if name in bound_somewhere else "keyword"})
            sent.add(name)
            used[eid] += cost
            left_total -= cost
    for eid, cards in per_row:        # 有卡卻一張都沒送到的切入點也記截斷（帳上分得出「沒卡」和「被擠掉」）
        if eid not in out["truncated_entries"] and any(c["name"] not in sent and _knowledge(c) for c, _ in cards):
            out["truncated"] = True
            out["truncated_entries"].append(eid)
    out["note"] = "\n\n".join(blocks)
    return out


def _send_order(per_row: List[Tuple[str, List[Tuple[Dict[str, Any], str]]]]) -> List[Tuple[str, Dict[str, Any]]]:
    """送卡順序：先送每個切入點的綁定卡（照登錄表順序），再送每個切入點的關鍵字退路卡——總上限很緊時，
    前一個切入點的退路卡不會擠掉後一個切入點的專卡。"""
    order: List[Tuple[str, Dict[str, Any]]] = []
    for phase in ("entry", "keyword"):
        for eid, cards in per_row:
            order += [(eid, card) for card, via in cards if via == phase]
    return order


LEDGER = "entry"          # Logs/guard-entry.jsonl
RESPONSE_TYPES = ("declared", "denied", "judged", "released", "none")


def entry_note(text: str, path: str, *, session_id: str = "", state: Optional[Dict[str, Any]] = None,
               config: Optional[Dict[str, Any]] = None, registry: Optional[Dict[str, Any]] = None,
               pool: Optional[List[Dict[str, Any]]] = None, extra: Optional[Dict[str, Any]] = None) -> str:
    """問的那一刻的單一入口：text 是程式這次要送給 LLM 的問句、path 是哪條路問（登錄表 path_values）。
    認出切入點 → 挑判準卡 → 每個認出的切入點記一筆帳 → 回要接在問句後面的文字（沒認出或沒卡回空字串）。
    帳一筆一個切入點：時間、session、回合（state 的 turn_seq，沒有 state 記 null）、代號、路、這個切入點送了哪幾張卡、
    有沒有截斷、同一問句還認出哪些代號、回應型（問的當下還沒有回應，記 none；之後 AI 怎麼回由 resolve_responses 依各閘留帳推）。
    extra 是這次問的標的（例：自檢評分評哪個 G，{"g": "G8"}），原樣寫進帳；登錄表 responses 的 match 照它配對回應。
    state 沒給且認出了切入點才讀 state（沒認出的問句零成本）。炸了只印 stderr、回空字串：問句照原樣送，閘的結果不受影響。"""
    try:
        reg = registry if registry is not None else load_registry()
        if not match_entries(text, path, reg):
            return ""
        if state is None and session_id:
            from wg_core import read_state
            state = read_state(session_id)
        turn = (state or {}).get("turn_seq")
        seen = _sent_this_turn(session_id, turn)
        res = judgment_cards(text, path, state=state, config=config, registry=reg, pool=pool, seen=seen)
        _remember_sent(session_id, turn, seen | {c["name"] for c in res["cards"]})
        from wg_core import append_guard_log
        for eid in res["entries"]:
            append_guard_log(LEDGER, {**(extra or {}), "event": "ask", "session_id": session_id, "turn_seq": turn, "entry": eid, "path": path,
                                      "cards": [c["name"] for c in res["cards"] if eid in c["entries"]],
                                      "repeated": [c["name"] for c in res["cards"] if eid in c["entries"] and c["name"] in res["repeated"]],
                                      "truncated": eid in res["truncated_entries"],
                                      "with": [e for e in res["entries"] if e != eid], "response": "none"})
        return res["note"]
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:Entrypoint] 接判準卡失敗，問句照原樣送：{type(e).__name__}: {e}", file=sys.stderr)
        return ""


def _sent_path(session_id: str) -> Path:
    from wg_core import WORKFLOW_DIR
    return WORKFLOW_DIR / "entry-sent" / f"{''.join(c if c.isalnum() or c in '-_' else '_' for c in session_id)}.json"


def _sent_this_turn(session_id: str, turn: Any) -> set:
    """規則 CARD_ONCE_PER_TURN：這個 session 這個使用者回合已送過全文的卡名。沒有 session 或回合、檔讀不到 → 空集合（照送全文）。"""
    if not session_id or turn is None:
        return set()
    try:
        rec = json.loads(_sent_path(session_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return set(rec.get("names") or []) if rec.get("turn") == turn else set()


def _remember_sent(session_id: str, turn: Any, names: set) -> None:
    if not session_id or turn is None or not names:
        return
    p = _sent_path(session_id)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"turn": turn, "names": sorted(names)}, ensure_ascii=False), encoding="utf-8",
                     newline="\n")
    except OSError as e:
        print(f"[Guardian:Entrypoint] 記不下本回合已送的判準卡（下次照送全文）：{e}", file=sys.stderr)


def with_note(text: str, note: str) -> str:
    """問句後面接判準卡（沒卡原樣回，不多一個換行）。"""
    return f"{text}\n{note}" if note else text


def _event_session(rec: Dict[str, Any]) -> str:
    return str(rec.get("session_id") or rec.get("session") or "")


def _ts(rec: Dict[str, Any]) -> datetime:
    """guard log 的 at（帶時區的 ISO，wg_core._now_iso）→ 可比大小的時間；壞的或沒有排最前面。"""
    try:
        t = datetime.fromisoformat(str(rec.get("at", "")))
        return t if t.tzinfo else t.astimezone()
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _first_response(rules: List[Dict[str, Any]], guard_logs: Dict[str, List[Dict[str, Any]]], sid: str,
                    at: datetime, until: Optional[datetime], ask: Dict[str, Any]) -> Optional[Tuple[datetime, Dict[str, Any]]]:
    """窗口 (at, until] 裡、同 session、對得上登錄表 responses 某條的第一筆閘紀錄 → (時間, 那條規則)；沒有回 None。
    規則寫了 match（鍵名清單）就還要問的帳與閘紀錄這些鍵的值相同（例：自檢評分問 G8、答 G3 不算回應）。"""
    best: Optional[Tuple[datetime, Dict[str, Any]]] = None
    for rule in rules:
        keys = [str(k) for k in rule.get("match") or []]
        for rec in guard_logs.get(str(rule.get("guard")), []):
            t = _ts(rec)
            if _event_session(rec) != sid or t <= at or (until is not None and t > until):
                continue
            if any(str(ask.get(k)) != str(rec.get(k)) for k in keys):
                continue
            if rule.get("event") in ("*", rec.get("event")) and (best is None or t < best[0]):
                best = (t, rule)
    return best


def resolve_responses(asks: List[Dict[str, Any]], guard_logs: Dict[str, List[Dict[str, Any]]],
                      registry: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """每筆問（guard-entry 的 ask）之後 AI 怎麼回，照各閘自己的留帳推：登錄表那列的 responses
    [{guard, event, type}]（event 寫 "*" 表示那個 guard 的任何一筆）。窗口＝這筆問之後、同 session 同代號下一次問之前（含）；
    窗口裡第一筆對得上的閘紀錄 → 它的 type；對不上但同一回合（turn_seq 相同）同代號又被問了一次 → denied（上一個回應沒過）；
    換了回合才又被問、或不知道回合 → none（可能是另一件事，不硬判）。
    已知限制：時間戳只到秒，與問同一秒寫的閘紀錄不算回應（閘紀錄自己記到微秒就不受影響：問的帳只到秒、一定不晚於實際問的時間）；
    帳上沒有標的（哪個檔、哪支測試）的切入點，同 session 同代號別件事的回應會算進來——有標的的列在 responses 寫 match。
    回 asks 的複本，每筆多 response 與 response_by（哪個 guard／event 判的）。"""
    reg = registry if registry is not None else load_registry()
    spec = {str(r["id"]): list(r.get("responses") or []) for r in reg["entrypoints"]}
    ordered = sorted(asks, key=_ts)
    out: List[Dict[str, Any]] = []
    for i, ask in enumerate(ordered):
        sid, eid, at = _event_session(ask), str(ask.get("entry")), _ts(ask)
        nxt = next((b for b in ordered[i + 1:] if _event_session(b) == sid and str(b.get("entry")) == eid), None)
        hit = _first_response(spec.get(eid, []), guard_logs, sid, at, _ts(nxt) if nxt else None, ask)
        if hit:
            rule = hit[1]
            resp, by = str(rule.get("type")), f"{rule.get('guard')}:{rule.get('event')}"
        elif nxt is not None and ask.get("turn_seq") is not None and nxt.get("turn_seq") == ask.get("turn_seq"):
            resp, by = "denied", "asked_again_same_turn"
        else:
            resp, by = "none", ""
        out.append({**ask, "response": resp if resp in RESPONSE_TYPES else "none", "response_by": by})
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
