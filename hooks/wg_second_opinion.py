"""wg_second_opinion.py：G9 自動第二意見的事實收集（Stop 的 SecondOpinion 段用；判定在 wg_release_rules 的 G9 段）。

做什麼：
  auto_cfg       config `second_opinion.auto` 段＋預設（門檻由總控台定：4 檔／150 行／risky_prefixes＋部位表類別 gate）。
  turn_events    transcript 尾段裡本回合（最後一則使用者打字或派工訊息之後）的 second_opinion_start／result 呼叫與回傳。
  changed_lines  本 session 改過的程式檔對 HEAD 的改動行數（git diff --numstat HEAD；未追蹤的新檔算整檔行數；查不到 git 回 None）。
  risky_paths    命中 risky_prefixes（相對版控根，沒有就相對部位表根）或部位表該列類別是 gate 的檔。
  has_goal_tree  這個 session 有沒有需求目標樹（有樹時，材料沒帶到樹的那次 run 不算跑過）。
  check          上面的事實交給 wg_release_rules.second_opinion_verdict，回 (Verdict, 事實)；事實的 satisfied＝這次滿足了
                 （跑過或宣告不需），Stop 據此記 second_opinion_ok[sid]，之後沒再改程式不再要求。
怎麼驗：python -X utf8 -m pytest -q hooks/verify/verify_g9_second_opinion.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import wg_release_rules as rr
from wg_core import find_vcs_root

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
GIT_TIMEOUT_S = 5.0
NEW_FILE_MAX_BYTES = 2_000_000     # 未追蹤新檔數行數時最多讀這麼多；更大的檔直接當成過門檻

DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "min_code_files": 4,
    "min_changed_lines": 150,
    "risky_prefixes": ["hooks/wg_release_rules.py", "hooks/handlers/stop.py", "hooks/handlers/pre_tool_use.py",
                       "hooks/wg_overview.py", "tools/workflow-guardian-mcp/"],
    "max_blocks_per_turn": 1,
}
GATE_KIND = "gate"                  # 部位表「類別」欄的原字（overview_hub.parse_map 只分 knowledge／code，這裡讀原字）
LETTER = "第二意見"                 # 擋訊息的條目字母（BLOCK_BUDGET_PER_RULE 照它計次；不在 reconcile_gate.block_letters 裡）
GATE = "second_opinion"             # wg_release 的閘名（last_block／pending_release／user_released）與 guard log 名
START_SUFFIX = "__second_opinion_start"
RESULT_SUFFIX = "__second_opinion_result"


def auto_cfg(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = (((config or {}).get("second_opinion") or {}).get("auto")) or {}
    out = dict(DEFAULTS)
    out.update({k: v for k, v in raw.items() if not str(k).startswith("_")})
    return out


# ─── 本回合的 start／result ─────────────────────────────────────────────

def _blocks(o: Dict[str, Any]) -> List[Dict[str, Any]]:
    msg = o.get("message") if isinstance(o.get("message"), dict) else {}
    content = msg.get("content")
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _result_text(block: Dict[str, Any]) -> str:
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(str(x.get("text") or "") for x in c if isinstance(x, dict))
    return ""


def _field(text: str, key: str) -> str:
    """MCP 回傳的 `key: value` 行（second-opinion.js 的輸出格式）；沒有回空字串。"""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(key + ":"):
            return s[len(key) + 1:].strip()
    return ""


def _notes(text: str) -> List[str]:
    return [ln.strip()[len("note:"):].strip() for ln in text.splitlines() if ln.strip().startswith("note:")]


def turn_events(transcript_text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """本回合（規則 TURN_SINCE_USER_PROMPT：最後一則使用者打字或派工訊息之後；尾段切掉起點就整段算）的
    (starts, results)：starts＝[{mode, kind, job_id, status, reason, notes}]、results＝[{job_id, status, reason}]，依出現順序。"""
    from wg_evasion import _is_real_user_prompt
    recs: List[Dict[str, Any]] = []
    for raw in str(transcript_text or "").splitlines():
        try:
            o = json.loads(raw)
        except ValueError:
            continue
        if isinstance(o, dict):
            recs.append(o)
    begin = 0
    for i, o in enumerate(recs):
        if o.get("type") == "user" and _is_real_user_prompt((o.get("message") or {}).get("content")):
            begin = i + 1
    calls: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    starts: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []
    for o in recs[begin:]:
        for b in _blocks(o):
            name = str(b.get("name") or "")
            if b.get("type") == "tool_use" and (name.endswith(START_SUFFIX) or name.endswith(RESULT_SUFFIX)):
                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                calls[str(b.get("id") or "")] = (name, inp)
                continue
            call = calls.get(str(b.get("tool_use_id") or "")) if b.get("type") == "tool_result" else None
            if call is None:
                continue
            text = _result_text(b)
            ev = {"status": _field(text, "status"), "reason": _field(text, "reason")}
            if call[0].endswith(START_SUFFIX):
                starts.append({"mode": call[1].get("mode"), "kind": call[1].get("kind"),
                               "job_id": _field(text, "job_id") or "-", "notes": _notes(text), **ev})
            else:
                results.append({"job_id": str(call[1].get("job_id") or "").strip(), **ev})
    return starts, results


# ─── 改動行數 ───────────────────────────────────────────────────────────

def _git(root: Path, args: List[str]) -> Optional[str]:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=GIT_TIMEOUT_S, creationflags=_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _rel(path: str, root: Path) -> Optional[str]:
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _new_file_lines(path: Path) -> int:
    try:
        if path.stat().st_size > NEW_FILE_MAX_BYTES:
            return 10 ** 6
        return path.read_bytes().count(b"\n") + 1
    except OSError:
        return 0


def _root_lines(root: Path, rels: List[str]) -> Optional[int]:
    """一個 git 根：numstat 對 HEAD 的增刪行＋未追蹤新檔的整檔行數。git 失敗（含沒有 HEAD）回 None。"""
    numstat = _git(root, ["diff", "--numstat", "HEAD", "--", *rels])
    tracked = _git(root, ["ls-files", "-z", "--", *rels])
    if numstat is None or tracked is None:
        return None
    total = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            total += int(parts[0]) + int(parts[1])
    known = {t for t in tracked.split("\0") if t}
    for rel in rels:
        if rel not in known:
            total += _new_file_lines(root / rel)
    return total


def changed_lines(paths: Sequence[str]) -> Optional[int]:
    """程式檔對 HEAD 的改動行數（各 git 根加總）；沒有任何檔在 git 根、或有一個根查失敗 → None（呼叫端只看檔數）。"""
    by_root: Dict[Path, List[str]] = {}
    for p in paths:
        hit = find_vcs_root(Path(p).parent)
        rel = _rel(p, hit[1]) if hit and hit[0] == "git" else None
        if rel is not None:
            by_root.setdefault(hit[1], []).append(rel)
    if not by_root:
        return None
    total = 0
    for root, rels in by_root.items():
        n = _root_lines(root, rels)
        if n is None:
            print(f"[Guardian:SecondOpinion] {root} 查不到 git 改動行數，只看檔數", file=sys.stderr)
            return None
        total += n
    return total


# ─── 高風險部位 ─────────────────────────────────────────────────────────

def _cells(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _raw_kind(map_text: str, row_line: str) -> str:
    """部位表那一列「類別」欄的原字（小寫、去反引號）；表頭沒有類別欄回空字串。欄位對法與 overview_hub.parse_map 相同（表頭格索引）。"""
    for ln in map_text.splitlines():
        if not ln.lstrip().startswith("|") or "類別" not in ln:
            continue
        idx = next((i for i, c in enumerate(_cells(ln)) if "類別" in c), None)
        row = _cells(row_line)
        return row[idx].strip("` ").lower() if idx is not None and idx < len(row) else ""
    return ""


def _map_of(path: str) -> Optional[Tuple[Path, str]]:
    try:
        from overview_hub import find_map
    except ImportError:
        return None
    found = find_map(str(path))
    if not found:
        return None
    try:
        return found[0], found[1].read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"[Guardian:SecondOpinion] 部位表 {found[1]} 讀不到，不判 gate 類別：{type(e).__name__}: {e}", file=sys.stderr)
        return None


def _gate_part(path: str, found: Optional[Tuple[Path, str]]) -> bool:
    if not found:
        return False
    from overview_hub import match_row, parse_map
    row = match_row(str(path), found[0], parse_map(found[1]), anchored=True)
    return bool(row) and _raw_kind(found[1], row["line"]) == GATE_KIND


def _prefix_hit(rel: str, prefix: str) -> bool:
    pre = str(prefix or "").replace("\\", "/").strip().lower()
    if not pre:
        return False
    return rel.startswith(pre) if pre.endswith("/") else (rel == pre or rel.startswith(pre + "/"))


def risky_paths(paths: Sequence[str], prefixes: Sequence[str]) -> List[str]:
    """命中 risky_prefixes（相對版控根；不在版控就相對部位表根）或部位表該列類別是 gate 的檔，照輸入順序。"""
    out: List[str] = []
    for p in paths:
        found = _map_of(p)
        hit = find_vcs_root(Path(p).parent)
        root = hit[1] if hit else (found[0] if found else None)
        rel = (_rel(p, root) or "").lower() if root else ""
        if (rel and any(_prefix_hit(rel, pre) for pre in prefixes)) or _gate_part(p, found):
            out.append(p)
    return out


# ─── 判定 ───────────────────────────────────────────────────────────────

def _mod_turn(m: Dict[str, Any]) -> int:
    return int((m or {}).get("last_turn_seq") or (m or {}).get("turn_seq") or 0)


def has_goal_tree(session_id: str) -> bool:
    """這個 session 有沒有需求目標樹（有樹時，材料沒帶到樹的 run 不算跑過）。目標檔讀不到或壞了 → 當有（fail-closed）並浮 stderr。"""
    try:
        import wg_need_goal as ng
        return ng.active_tree(ng.load(session_id)) is not None
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:SecondOpinion] 讀不到需求目標樹，當成有樹（材料要帶到樹才算跑過）：{type(e).__name__}: {e}", file=sys.stderr)
        return True


def check(state: Dict[str, Any], session_id: str, own_mod_files: Sequence[Dict[str, Any]], text: str,
          transcript_text: str, config: Dict[str, Any], cfg: Dict[str, Any], claims_done: bool
          ) -> Tuple[rr.Verdict, Dict[str, Any]]:
    """SecondOpinion Gate 的事實＋判定。git 只在檔數與高風險部位都沒觸發時才查（行數是第三個條件）。"""
    from wg_need_goal import writes_code
    code = [m for m in own_mod_files if (m or {}).get("path") and writes_code(str(m["path"]), config)]
    uniq: Dict[str, str] = {}      # 同一個檔不同寫法只算一次（SAME_FILE），保留原寫法給 git pathspec（大小寫敏感）
    for m in code:
        uniq.setdefault(rr.canon_path(m["path"]), str(m["path"]))
    paths = list(uniq.values())
    facts: Dict[str, Any] = {"code_files": len(paths), "triggers": [], "satisfied": False, "decline": ""}
    if not claims_done or not paths:
        return rr.second_opinion_verdict(claims_done, [], False, [], text), facts
    ok_turn = int(((state.get("second_opinion_ok") or {}).get(session_id)) or 0)
    fresh = ok_turn == 0 or any(_mod_turn(m) > ok_turn for m in code)
    risky = risky_paths(paths, list(cfg.get("risky_prefixes") or []))
    min_files, min_lines = int(cfg.get("min_code_files", 4)), int(cfg.get("min_changed_lines", 150))
    lines = None if (len(paths) >= min_files or risky) else changed_lines(paths)
    triggers = rr.second_opinion_triggers(len(paths), lines, risky, min_files, min_lines)
    runs = rr.second_opinion_runs(*turn_events(transcript_text), has_tree=has_goal_tree(session_id)) \
        if (triggers and fresh) else []
    v = rr.second_opinion_verdict(claims_done, triggers, fresh, runs, text)
    facts.update(triggers=triggers, fresh=fresh, runs=runs, changed_lines=lines,
                 satisfied=bool(triggers and fresh and not v.owed),
                 decline=(rr.second_opinion_decline(text) or "") if v.rule == "SECOND_OPINION_DECLINED" else "")
    return v, facts
