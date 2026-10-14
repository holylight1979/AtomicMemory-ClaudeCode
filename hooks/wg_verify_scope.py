"""wg_verify_scope.py：驗證範圍——該測哪些由 LLM 依關聯與影響判斷並負責，程式只管流程。

做什麼：
- 收件 declare：need_goal(action="verify_scope", items=[{target, why}], reviews=[…]) 經 PostToolUse 交到這裡。每項正規化成
  檔案／資料夾／測試節點／指令，記在 state["verify_scope"][收據鍵]；每次宣告是完整範圍，最新那份算數。該 repo 有沒檢討的
  範圍漏判 → 要逐筆附檢討才收。回應附這次改到的檔、部位整把量尺（只當參考）、每項現況、累計數字。
- 收尾閘 gate_reason（stop._verify_gates 叫）：要宣告的改檔（程式檔，或部位表上有量尺的部位）→ 要有宣告、每個 repo 有項目、
  每項有改完之後跑綠的收據。過了 → close 記結案。
- 範圍漏判 observe_run／sync_runs：每輪測試記進 runs.jsonl（跑了哪些、哪些紅）；紅的測試 T，找「T 上次綠之後、這次紅之前結案、
  範圍沒涵蓋 T」的宣告記疑似漏判。背景全量（run_verify 自寫收據的 failed_cases）由 sync_runs 入帳。
- 送回與數字：pending_leaks／stats／stats_line／advisory（SessionStart）。
規則（名字、條件）都在 wg_release_rules 的 SCOPE_*；收據對不對得上一項在 wg_verify_ledger.scope_item_status。
帳本：<WORKFLOW_DIR>/verify-scope/scope.jsonl（結案、漏判、檢討；不自動清）、runs.jsonl（每輪測試；超過上限砍掉舊的一半）、
self-observed.json（已入帳的自寫收據）。worktree 與主工作樹用同一個 repo 鍵（repo_key）。
怎麼跑案例：python -X utf8 -m pytest -q hooks/verify/verify_verify_scope.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import wg_release_rules as rr
import wg_verify_ledger as vl
from wg_core import WORKFLOW_DIR, _now_iso

SCOPE_DIR = Path(WORKFLOW_DIR) / "verify-scope"
DEFAULTS: Dict[str, Any] = {"enabled": True, "runtime_gate_timeout_s": 2}
DECL_CAP = 20                 # 每個收據鍵留幾份宣告
RUNS_MAX_BYTES = 4_000_000    # runs.jsonl 超過就砍掉舊的一半
OBSERVED_CAP = 500            # self-observed.json 記幾份已入帳的自寫收據
TAG = "[Guardian:VerifyScope]"
Lookup = Optional[Callable[[str], Optional[Tuple[Path, Dict[str, Any]]]]]


def scope_cfg(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    c = dict(DEFAULTS)
    sec = (config or {}).get("verify_scope")
    if isinstance(sec, dict):
        c.update(sec)
    return c


# ─── 路徑與 repo ───────────────────────────────────────────────────────────

def repo_key(root: Optional[str]) -> str:
    """同一個 repo 的鍵：git worktree（.git 是檔、指到 <主>/.git/worktrees/<名>）換成主工作樹，其餘就是 root 本身；正規化小寫。"""
    if not root:
        return ""
    p = Path(str(root))
    try:
        g = p / ".git"
        if g.is_file():
            first = (g.read_text(encoding="utf-8", errors="replace").splitlines() or [""])[0]
            m = re.match(r"\s*gitdir:\s*(.+?)\s*$", first)
            if m:
                gd = Path(m.group(1))
                gd = gd if gd.is_absolute() else p / gd
                cd = gd / "commondir"
                if cd.is_file():
                    common = Path(cd.read_text(encoding="utf-8", errors="replace").strip())
                    common = Path(os.path.normpath(str(common if common.is_absolute() else gd / common)))
                    p = common.parent if common.name.lower() == ".git" else common
    except OSError as e:
        print(f"{TAG} 讀 {p} 的 .git 失敗，當成獨立 repo：{type(e).__name__}: {e}", file=sys.stderr)
    return rr.canon_path(p)


def _default_lookup() -> Lookup:
    try:
        from wg_overview import _lookup_quiet
        return _lookup_quiet
    except ImportError:
        return None


def _root_of(path: str, lookup: Lookup) -> Optional[str]:
    """改檔或項目所在的樹根：部位表命中就用表的根，否則 file_root_of（專案根，找不到退版控根）。"""
    hit = lookup(path) if lookup else None
    if hit:
        return str(hit[0])
    return vl.file_root_of(path)


def _rel(path: str, root: Optional[str]) -> str:
    """樹根相對路徑（比對鍵，節點段照接）；不在根底下就回正規化絕對路徑。"""
    f, sep, node = str(path).partition("::")
    full, base = rr.canon_path(f), (rr.canon_path(root) if root else "")
    rel = full[len(base) + 1:] if base and full.startswith(base + "/") else (full if full != base else "")
    return rel + (sep + node.lower() if sep else "")


def _utc(s: Any) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _before(a: Any, b: Any) -> bool:
    ta, tb = _utc(a), _utc(b)
    return bool(ta and tb and ta < tb)


# ─── 帳本 ─────────────────────────────────────────────────────────────────

def _append(name: str, rec: Dict[str, Any]) -> None:
    p = SCOPE_DIR / name
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"{TAG} 帳本寫不進 {p}：{type(e).__name__}: {e}", file=sys.stderr)
        return
    if name == "runs.jsonl":
        _trim_runs(p)


def _trim_runs(p: Path) -> None:
    try:
        if p.stat().st_size <= RUNS_MAX_BYTES:
            return
        lines = p.read_text(encoding="utf-8").splitlines()
        tmp = p.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text("\n".join(lines[len(lines) // 2:]) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp, p)
    except OSError as e:
        print(f"{TAG} 整理 {p} 失敗（照舊追加）：{type(e).__name__}: {e}", file=sys.stderr)


def _read(name: str) -> List[Dict[str, Any]]:
    p = SCOPE_DIR / name
    if not p.is_file():
        return []
    out: List[Dict[str, Any]] = []
    bad = 0
    try:
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ln.strip():
                continue
            try:
                rec = json.loads(ln)
            except ValueError:
                bad += 1
                continue
            if isinstance(rec, dict):
                out.append(rec)
    except OSError as e:
        print(f"{TAG} 帳本讀不到 {p}：{type(e).__name__}: {e}", file=sys.stderr)
    if bad:
        print(f"{TAG} {p} 有 {bad} 行壞掉已跳過", file=sys.stderr)
    return out


def _leaks(repo: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """該 repo 的漏判（編號 → 那筆）與檢討（漏判編號 → 最後一筆檢討）。"""
    leaks: Dict[str, Dict[str, Any]] = {}
    reviews: Dict[str, Dict[str, Any]] = {}
    for e in _read("scope.jsonl"):
        if e.get("ev") == "leak" and e.get("repo") == repo:
            leaks.setdefault(str(e.get("id")), e)
        elif e.get("ev") == "review":
            reviews[str(e.get("leak"))] = e
    return leaks, {k: v for k, v in reviews.items() if k in leaks}


def pending_leaks(repo: str) -> List[Dict[str, Any]]:
    leaks, reviews = _leaks(repo)
    return [e for lid, e in leaks.items() if lid not in reviews]


def stats(repo: str) -> Dict[str, Any]:
    closed = {str(e.get("scope_id")) for e in _read("scope.jsonl") if e.get("ev") == "close" and repo in (e.get("repos") or [])}
    leaks, reviews = _leaks(repo)
    missed = sum(1 for r in reviews.values() if r.get("verdict") == "missed")
    unrelated = sum(1 for r in reviews.values() if r.get("verdict") == "unrelated")
    return {"closed": len(closed), "leaks": len(leaks), "missed": missed, "unrelated": unrelated,
            "pending": len(leaks) - len(reviews), "rate": (missed / len(closed)) if closed else 0.0}


def stats_line(repo: str) -> str:
    s = stats(repo)
    return (f"範圍宣告：結案 {s['closed']}｜疑似漏判 {s['leaks']}（該驗沒驗到 {s['missed']}、與改動無關 {s['unrelated']}、"
            f"待檢討 {s['pending']}）｜漏判率 {s['rate'] * 100:.0f}%")


def _leak_text(e: Dict[str, Any]) -> str:
    items = "、".join(f"「{i.get('target')}」" for i in e.get("items") or []) or "（無）"
    files = "、".join(str(f).rsplit("/", 1)[-1] for f in e.get("files") or []) or "（無）"
    busy = "｜看到紅時那個 session 自己還有沒結案的改動：先查明是不是它這次改動造成的" if e.get("observer_open") else ""
    return (f"{e.get('id')}：{e.get('test')} 紅了（{str(e.get('red_at') or '')[:16]}），{e.get('scope_id')}"
            f"（{str(e.get('closed_at') or '')[:16]} 結案）的範圍沒涵蓋它｜那次範圍 {items}｜改了 {files}"
            f"｜它上次綠 {str(e.get('last_green') or '')[:16]}{busy}")


# ─── 宣告收件 ─────────────────────────────────────────────────────────────

def _key_mods(state: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    """收據鍵自己的改檔：子代理（鍵帶 #agent:）看 agent_modified_files，主 session 看 modified_files 裡同 session 的。"""
    sid, _, agent = str(key).partition("#agent:")
    if agent:
        return list(((state.get("agent_modified_files") or {}).get(agent)) or [])
    return [m for m in state.get("modified_files") or [] if isinstance(m, dict) and m.get("session_id", sid) == sid]


def required_mods(mods: Iterable[Dict[str, Any]], rg_cfg: Dict[str, Any], lookup: Lookup) -> List[Dict[str, Any]]:
    """要宣告驗證範圍的改檔（要不要驗是規則）：程式檔（排除知識部位、被忽略與執行期資料：EXCLUDED_REGION），或落在部位表上
    有量尺的部位。升級前的舊改檔紀錄（at、序號、turn 都沒記）看不出何時改的，不要求（與 (d) 的舊格式規則一致）。
    部位表讀不到（MapReadError）往外拋：不能當成沒有量尺。"""
    exts = rg_cfg.get("code_exts") or []
    picked: List[Tuple[Dict[str, Any], str, bool]] = []
    for m in mods or []:
        p = str((m or {}).get("path") or "")
        if not p or p.startswith("UNKNOWN:"):
            continue
        if (m.get("last_turn_seq", m.get("turn_seq")) is None and not (m.get("last_at") or m.get("at"))
                and m.get("last_seq") is None):
            continue
        hit = lookup(p) if lookup else None
        ruler = bool(hit and str(((hit[1].get("measure") or {}).get("cmd")) or "").strip())
        picked.append((m, str(hit[0]) if hit else (vl.file_root_of(p) or ""), ruler))
    ignored: Dict[str, set] = {}
    out: List[Dict[str, Any]] = []
    for m, root, ruler in picked:
        p = str(m["path"])
        if ruler:
            out.append(m)
            continue
        if not vl.is_code_file(p, exts):
            continue
        if root and root not in ignored:
            ignored[root] = vl.gitignored_paths(root, [str(x["path"]) for x, r, _ in picked if r == root])
        if not vl.is_excluded(p, rg_cfg, root or None, ignored.get(root, set())):
            out.append(m)
    return out


def _mark(m: Dict[str, Any]) -> Tuple[str, int]:
    return str(m.get("last_at") or m.get("at") or ""), int(m.get("last_seq") or 0)


def _marker(mods: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """一批改檔最後一次修改的位置（結案時記下；之後改過 → 有沒結案的改動）。"""
    at, seq = "", 0
    for m in mods:
        a, s = _mark(m)
        if a and (not at or _before(at, a)):
            at = a
        seq = max(seq, s)
    return {"at": at, "seq": seq}


def _edited_after(m: Dict[str, Any], marker: Dict[str, Any]) -> bool:
    a, s = _mark(m)
    if a and marker.get("at"):
        if a != marker["at"]:
            return _before(marker["at"], a)
    return s > int(marker.get("seq") or 0)


def current_decl(state: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    """最新那份宣告；子代理自己沒宣告就沿用主 session 的。"""
    sv = state.get("verify_scope") or {}
    decls = sv.get(key) or (sv.get(str(key).split("#agent:", 1)[0]) if "#agent:" in str(key) else None) or []
    return decls[-1] if decls else None


def _normalize(target: str, cwd: str, lookup: Lookup) -> Tuple[Optional[Dict[str, Any]], str]:
    """宣告的一項 → {target, kind, abs, root, repo, rel, base, covers}；檔／節點不存在回 (None, 問題)。"""
    import wg_need_goal as ng
    t = target.strip().strip("`")
    looks_path = not re.search(r"\s", t) and ("::" in t or "/" in t or "\\" in t or bool(re.search(r"\.\w{1,6}$", t)))
    if looks_path:
        f, sep, node = t.partition("::")
        p = Path(f) if os.path.isabs(f) else Path(cwd or ".") / f
        if not p.exists():
            return None, f"不存在（{p}）"
        if sep:
            miss = ng._node_id_missing("case", t, cwd)
            if miss:
                return None, f"查不到這個測試節點：{miss}"
        kind = "node" if sep else ("dir" if p.is_dir() else "file")
        root = _root_of(str(p), lookup) or cwd or None
        full = str(p) + (sep + node if sep else "")
        rel = _rel(full, root)
        return {"target": target, "kind": kind, "abs": vl._abs_target("", full), "root": root, "repo": repo_key(root),
                "rel": rel, "base": cwd, "covers": [rel]}, ""
    bad = vl.unsupported_syntax(t)
    if bad:
        return None, f"這條指令本身含解析不了的語法（{bad}），任何收據都對不上；改成單一指令或 && 串接再宣告"
    root = (_root_of(cwd, lookup) if cwd else None) or cwd or None
    fake = {"cmd": t, "cmd_full": True, "env": {}, "cwd": cwd, "project_root": root or cwd, "tool": "Bash"}
    tg = vl.run_targets(fake)
    covers = (["*"] if tg and tg["whole"] else [_rel(p, root) for p in (tg or {}).get("paths") or []])
    return {"target": target, "kind": "cmd", "abs": "", "root": root, "repo": repo_key(root), "rel": "", "base": cwd,
            "covers": covers}, ""


def _rulers(mods: Iterable[Dict[str, Any]], lookup: Lookup) -> List[str]:
    """改到的部位原本那把整的量尺（候選材料，不是門檻）。"""
    out: List[str] = []
    for m in mods:
        hit = lookup(str(m.get("path") or "")) if lookup else None
        cmd = str(((hit[1].get("measure") or {}).get("cmd")) or "").strip() if hit else ""
        if cmd:
            line = f"部位【{hit[1].get('part_short') or hit[1].get('part') or '?'}】`{cmd}`"
            if line not in out:
                out.append(line)
    return out


def _sid_tag(key: str) -> str:
    sid, _, agent = str(key).partition("#agent:")
    return sid[:8] + (f"-{agent[:6]}" if agent else "")


def declare(state: Dict[str, Any], key: str, tool_input: Dict[str, Any], cwd: str,
            config: Optional[Dict[str, Any]] = None, lookup: Lookup = None) -> str:
    """need_goal(action=verify_scope) 收件。回要送回 AI 的整段提示（收下或退回）。"""
    import wg_need_goal as ng
    lookup = lookup or _default_lookup()
    tool_input = tool_input or {}
    items = tool_input.get("items")
    errs = [] if isinstance(items, list) and items and all(isinstance(it, dict) for it in items) else ng.validate_input(tool_input)
    if errs:
        return f"{TAG} verify_scope 拒收，沒有套用：\n" + "\n".join(f"  ✗ {e}" for e in errs)
    norm: List[Dict[str, Any]] = []
    bad: List[str] = []
    for it in items:
        target, why = str(it.get("target") or "").strip(), str(it.get("why") or "").strip()
        rec, problem = _normalize(target, cwd, lookup) if target and why else (None, "")
        v = rr.scope_item_form_verdict(target, why, problem)
        if v.owed:
            bad.append(rr.format_hit("s", v))
            continue
        rec["why"] = why
        norm.append(rec)
    if bad:
        return f"{TAG} verify_scope 拒收，沒有套用（整份重交）：\n" + "\n".join("  " + b for b in bad)
    errs = ng.validate_input(tool_input)                     # 項目都合格了，再看 reviews 的形狀
    if errs:
        return f"{TAG} verify_scope 拒收，沒有套用：\n" + "\n".join(f"  ✗ {e}" for e in errs)
    repos = sorted({it["repo"] for it in norm})
    pend = [e for r in repos for e in pending_leaks(r)]
    reviews = [r for r in tool_input.get("reviews") or [] if isinstance(r, dict)]
    if pend:
        v = rr.scope_review_verdict([str(e.get("id")) for e in pend], reviews)
        if v.owed:
            return (f"{TAG} verify_scope 拒收，沒有套用：\n  {rr.format_hit('s', v)}\n待檢討的範圍漏判：\n"
                    + "\n".join(f"  - {_leak_text(e)}" for e in pend)
                    + "\n先查明每一筆是不是「該驗的沒驗到」：是的話寫沒驗到的根因與下次判斷範圍時要怎麼改"
                      "（reviews=[{leak, verdict:\"missed\", root_cause, next_time}]）；不是就寫查明的理由"
                      "（{leak, verdict:\"unrelated\", reason}）。跟這次的範圍一起重交。")
        now = _now_iso()
        for e in pend:
            r = next(x for x in reviews if str(x.get("leak") or "").strip() == str(e.get("id")))
            _append("scope.jsonl", {"ev": "review", "leak": e.get("id"), "verdict": r.get("verdict"),
                                    "root_cause": str(r.get("root_cause") or ""), "next_time": str(r.get("next_time") or ""),
                                    "reason": str(r.get("reason") or ""), "by": key, "at": now})
    seqs = state.setdefault("verify_scope_seq", {})
    seqs[key] = int(seqs.get(key) or 0) + 1
    decl = {"id": f"{_sid_tag(key)}-S{seqs[key]}", "at": _now_iso(), "turn": int(state.get("turn_seq", 0) or 0),
            "cwd": cwd, "items": norm}
    decls = state.setdefault("verify_scope", {}).setdefault(key, [])
    decls.append(decl)
    del decls[:-DECL_CAP]
    return _accept_text(state, key, decl, lookup, repos, len(pend))


def _accept_text(state: Dict[str, Any], key: str, decl: Dict[str, Any], lookup: Lookup, repos: List[str],
                 reviewed: int) -> str:
    rg = vl.reconcile_cfg({})
    try:
        mods = required_mods(_key_mods(state, key), rg, lookup)
    except Exception as e:  # noqa: BLE001  收件回應只是資訊；部位表讀不到在收尾閘照擋
        print(f"{TAG} 收件時列改檔失敗：{type(e).__name__}: {e}", file=sys.stderr)
        mods = []
    receipts = vl.receipts_of(state, key)
    lines = [f"{TAG} verify_scope 收下：{decl['id']}（{len(decl['items'])} 項；每次宣告都是完整範圍，最新這份算數）"
             + (f"；{reviewed} 筆漏判檢討已記下" if reviewed else "")]
    for it in decl["items"]:
        ok, why = vl.scope_item_status(it, receipts, mods)
        lines.append(f"  - 「{it['target']}」（{it['kind']}）{'已有改完之後跑綠的收據' if ok else '還沒有收據：' + why}")
    if mods:
        names = "、".join(Path(str(m.get("path"))).name for m in mods[:8])
        lines.append(f"這次要宣告的改檔：{names}{'…' if len(mods) > 8 else ''}")
    rulers = _rulers(mods, lookup)
    if rulers:
        lines.append("參考（部位原本那把整的量尺，只當候選材料，不必全跑；整把在發版前全量跑）：" + "；".join(rulers))
    lines.append("收尾前範圍內每一項都要在最後一次改動之後跑綠；之後若範圍外的測試因這次改動紅了，會記成範圍漏判送回檢討。")
    for r in repos:
        lines.append(stats_line(r))
    return "\n".join(lines)


# ─── 收尾閘 ───────────────────────────────────────────────────────────────

def gate_reason(state: Dict[str, Any], key: str, own_mod_files: List[Dict[str, Any]], receipts: List[Dict[str, Any]],
                rg_cfg: Dict[str, Any], lookup: Lookup, cfg: Optional[Dict[str, Any]] = None,
                chains_of: Callable[[Path], Dict[str, Dict[str, str]]] = vl.load_verify_chains,
                runner: Callable[[str, float, Optional[str]], Tuple[bool, str]] = vl.run_runtime_gate,
                self_runs: Iterable[Dict[str, Any]] = (),
                ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """回 (擋訊息或 None, 可結案的資料或 None)。不看措辭：有要宣告的改檔每次收尾都判。
    self_runs＝背景跑的自寫收據（超過工具 10 分鐘上限的範圍只能背景跑，跑完自寫收據也算數）。"""
    self_runs = list(self_runs or [])
    mods = required_mods(own_mod_files, rg_cfg, lookup)
    if not mods:
        return None, None
    roots = {str(m["path"]): _root_of(str(m["path"]), lookup) for m in mods}
    by_repo: Dict[str, List[str]] = {}
    for p, root in roots.items():
        by_repo.setdefault(repo_key(root), []).append(p)
    decl = current_decl(state, key)
    hits: List[rr.Verdict] = []
    if decl is None:
        hits.append(rr.scope_declared_verdict(list(roots), False))
    else:
        have = {it.get("repo") for it in decl.get("items") or []}
        missing = [(r, ps) for r, ps in by_repo.items() if r and r not in have]     # 判不出 repo 的改檔不要求（項目照樣要收據）
        v = rr.scope_declared_verdict(list(roots), True, missing)
        if v.owed:
            hits.append(v)
        for it in decl.get("items") or []:
            ok, why = vl.scope_item_status(it, receipts, mods, self_runs)
            v = rr.scope_item_verdict(decl["id"], str(it.get("target")), ok, why)
            if v.owed:
                hits.append(v)
    if not hits:
        return None, {"decl_id": decl["id"], "marker": _marker(mods), "files": sorted(set(roots)), "roots": roots}
    lines = [f"{TAG} 改了程式，收尾前要有你判斷的驗證範圍，而且範圍內每一項都在改完之後跑綠："]
    lines += ["  " + rr.format_hit("s", v) for v in hits]
    lines += _env_notes(mods, lookup, chains_of, runner, float((cfg or DEFAULTS).get("runtime_gate_timeout_s", 2)))
    lines.append("  該測哪些由你判斷：看這次改了什麼、哪些測試有關聯、哪些地方會受影響，可以重新宣告（整份重交）；"
                 "宣告之後只跑範圍內的項目。")
    rulers = _rulers(mods, lookup)
    if rulers:
        lines.append("  參考（不必全跑）：" + "；".join(rulers))
    lines.append("  跑不了就照【收尾放行確認】問使用者，改寫收尾文字不會解帳。")
    return "\n".join(lines), None


def _env_notes(mods: List[Dict[str, Any]], lookup: Lookup, chains_of: Callable[[Path], Dict[str, Dict[str, str]]],
               runner: Callable[[str, float, Optional[str]], Tuple[bool, str]], timeout: float) -> List[str]:
    """還欠收據時，改到的部位設了 runtime_gate（verify_chains）就探一次：量不了要說原因。"""
    out: List[str] = []
    seen = set()
    for m in mods:
        hit = lookup(str(m.get("path") or "")) if lookup else None
        if not hit:
            continue
        root, row = hit
        part = row.get("part_short") or row.get("part") or "?"
        if (str(root), part) in seen:
            continue
        seen.add((str(root), part))
        gate = str(((chains_of(root) or {}).get(part) or {}).get("runtime_gate") or "").strip()
        if gate:
            ok, why = runner(gate, timeout, str(root))
            if not ok:
                out.append(f"  部位【{part}】驗證環境未就緒：{why}。讓環境就緒再跑；量不了就照【收尾放行確認】問使用者（題目寫明量不了的原因）。")
    return out


def close(state: Dict[str, Any], key: str, closable: Optional[Dict[str, Any]], lookup: Lookup = None) -> None:
    """收尾閘整個過了：把這份宣告記成結案（同一批改動只記一次）。"""
    if not closable:
        return
    decl = current_decl(state, key)
    if not decl or decl.get("id") != closable.get("decl_id"):
        return
    done = state.setdefault("verify_scope_closed", {})
    prev = done.get(key) or {}
    if prev.get("decl") == decl["id"] and prev.get("marker") == closable["marker"]:
        return
    now = _now_iso()
    done[key] = {"decl": decl["id"], "marker": closable["marker"], "at": now}
    roots = closable.get("roots") or {}
    files = [f"{repo_key(r)}|{_rel(p, r)}" for p, r in roots.items()]
    _append("scope.jsonl", {
        "ev": "close", "scope_id": decl["id"], "key": key, "at": now,
        "repos": sorted({it.get("repo") for it in decl.get("items") or []} | {repo_key(r) for r in roots.values()}),
        "items": [{k: it.get(k) for k in ("target", "why", "kind", "repo", "covers")} for it in decl.get("items") or []],
        "files": files,
    })


# ─── 範圍漏判 ────────────────────────────────────────────────────────────

def _open_in_repo(state: Dict[str, Any], key: str, repo: str, rg_cfg: Dict[str, Any], lookup: Lookup) -> bool:
    """收據鍵在這個 repo 還有沒結案的改動（結案之後又改過，或改了還沒結案）。"""
    mods = [m for m in required_mods(_key_mods(state, key), rg_cfg, lookup)
            if repo_key(_root_of(str(m["path"]), lookup)) == repo]
    if not mods:
        return False
    done = (state.get("verify_scope_closed") or {}).get(key)
    return not done or any(_edited_after(m, done.get("marker") or {}) for m in mods)


def _failed_rel(names: Iterable[str], base: str, targets: Iterable[str], tree: str) -> List[str]:
    """pytest 紅名單（節點 id，相對 rootdir）→ 樹根相對路徑：依序試執行根、點名的資料夾與檔所在資料夾，第一個存在的。"""
    dirs = [base] + [t.split("::", 1)[0] for t in targets]
    dirs = [d if not os.path.isfile(d) else os.path.dirname(d) for d in dirs]
    out: List[str] = []
    for n in names:
        f, sep, node = str(n).partition("::")
        hit = next((os.path.join(d, f) for d in dirs if d and os.path.exists(os.path.join(d, f))), os.path.join(base, f))
        rel = _rel(hit + (sep + node if sep else ""), tree)
        if rel not in out:
            out.append(rel)
    return out


def _record_run(run: Dict[str, Any]) -> None:
    _append("runs.jsonl", run)


def _attribute(repo: str, failed: List[str], red_at: str, observer: str, observer_open: bool) -> List[Dict[str, Any]]:
    """紅名單逐一找漏判（規則 SCOPE_LEAK_OUTSIDE_SCOPE），新記的那幾筆回傳。"""
    if not failed:
        return []
    runs = [r for r in _read("runs.jsonl") if r.get("repo") == repo and _before(r.get("at"), red_at)]
    entries = _read("scope.jsonl")
    closes: Dict[str, Dict[str, Any]] = {}
    for e in entries:
        if e.get("ev") == "close" and repo in (e.get("repos") or []) and _before(e.get("at"), red_at):
            closes[str(e.get("scope_id"))] = e                 # 同一份宣告多次結案取最後一次
    known = {str(e.get("id")) for e in entries if e.get("ev") == "leak"}
    new: List[Dict[str, Any]] = []
    for test in failed:
        greens = [r.get("at") for r in runs if rr.scope_covers(r.get("covers") or [], test)
                  and (r.get("green") or (r.get("failed_known") and not rr.scope_failed_in(r.get("failed") or [], test)))]
        last_green = max(greens, key=lambda a: _utc(a) or datetime.min.replace(tzinfo=timezone.utc)) if greens else None
        for sid, c in closes.items():
            covers = [cv for it in c.get("items") or [] if it.get("repo") == repo for cv in it.get("covers") or []]
            v = rr.scope_leak_verdict(test, sid, rr.scope_covers(covers, test), observer_open, last_green,
                                      bool(last_green) and _before(last_green, c.get("at")))
            if not v.owed:
                continue
            lid = "L" + hashlib.sha1(f"{repo}|{sid}|{test}".encode("utf-8")).hexdigest()[:6]   # 同一份宣告跨 repo 的同名測試分開記
            if lid in known:
                continue
            known.add(lid)
            rec = {"ev": "leak", "id": lid, "repo": repo, "scope_id": sid, "scope_key": c.get("key"), "test": test,
                   "red_at": red_at, "last_green": last_green, "closed_at": c.get("at"), "observer": observer,
                   "observer_open": bool(observer_open),
                   "items": [{"target": it.get("target"), "why": it.get("why")} for it in c.get("items") or []],
                   "files": [str(f).split("|", 1)[-1] for f in c.get("files") or [] if str(f).startswith(repo + "|")],
                   "at": _now_iso()}
            _append("scope.jsonl", rec)
            new.append(rec)
    return new


def _leak_notice(new: List[Dict[str, Any]]) -> str:
    return (f"{TAG} 記下 {len(new)} 筆疑似範圍漏判（規則 SCOPE_LEAK_OUTSIDE_SCOPE）：\n"
            + "\n".join(f"  - {_leak_text(e)}" for e in new)
            + "\n下次宣告驗證範圍時要逐筆檢討：查明是不是「該驗的沒驗到」，是的話寫沒驗到的根因與下次判斷範圍時要怎麼改。")


def observe_run(state: Dict[str, Any], key: str, receipt: Dict[str, Any], output: str, rg_cfg: Dict[str, Any],
                lookup: Lookup = None) -> Optional[str]:
    """一輪測試（PostToolUse 剛落帳的收據）記進 runs.jsonl；紅了就找漏判。回要送回 AI 的提示或 None。"""
    t = vl.run_targets(receipt)
    if t is None:
        return None
    lookup = lookup or _default_lookup()
    tree = str(receipt.get("project_root") or t["base"] or "")
    repo = repo_key(tree)
    red = vl.receipt_is_red(receipt)
    names = rr.red_case_names(output) if red else []
    failed = _failed_rel(names, t["base"], t["paths"], tree) if names else []
    if red and not failed and not t["whole"]:
        failed = [_rel(p, tree) for p in t["paths"] if not os.path.isdir(p.split("::", 1)[0])]
    covers = (["*"] if not _rel(t["base"], tree) else [_rel(t["base"], tree)]) if t["whole"] else [_rel(p, tree) for p in t["paths"]]
    at = str(receipt.get("at") or _now_iso())
    _record_run({"ev": "run", "repo": repo, "at": at, "key": key, "covers": covers, "failed": failed,
                 "failed_known": bool(failed) or not red, "green": not red, "source": "session"})
    if not failed:
        return None
    try:
        busy = _open_in_repo(state, key, repo, rg_cfg, lookup)
    except Exception as e:  # noqa: BLE001  判不出來 → 當成自己在改（照記，標出來讓檢討時先查明）
        print(f"{TAG} 判斷是否還有沒結案的改動失敗，當成有：{type(e).__name__}: {e}", file=sys.stderr)
        busy = True
    new = _attribute(repo, failed, at, key, busy)
    return _leak_notice(new) if new else None


def _observed() -> List[str]:
    p = SCOPE_DIR / "self-observed.json"
    try:
        v = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else []
    except (OSError, ValueError) as e:
        print(f"{TAG} {p} 讀不到，重新入帳（漏判編號去重）：{type(e).__name__}: {e}", file=sys.stderr)
        v = []
    return [str(x) for x in v] if isinstance(v, list) else []


def _save_observed(ids: List[str]) -> None:
    p = SCOPE_DIR / "self-observed.json"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(ids[-OBSERVED_CAP:], ensure_ascii=False), encoding="utf-8", newline="\n")
        os.replace(tmp, p)
    except OSError as e:
        print(f"{TAG} 寫不進 {p}：{type(e).__name__}: {e}", file=sys.stderr)


def _self_covers(r: Dict[str, Any], tree: str) -> List[str]:
    """自寫收據涵蓋哪些：argv 點名的既有路徑（根 conftest 整組跑 tools/verify 這類），沒點名（run_verify.py）就是整棵樹。"""
    rels = [_rel(p, tree) for p in vl.self_run_targets(r)]
    return [x for x in rels if x] or ["*"]


def sync_runs(self_runs: Iterable[Dict[str, Any]]) -> List[str]:
    """背景全量（run_verify／根 conftest 的自寫收據）入帳：每份一輪（涵蓋 _self_covers）；紅掉的測試名（failed_cases）照常歸因。
    同一份只入帳一次。回新記漏判的提示（每份一則）。"""
    seen = _observed()
    fresh: List[str] = []
    notes: List[str] = []
    for r in self_runs or []:
        if not isinstance(r, dict) or r.get("source") != "run_verify_self":
            continue
        tree = str(r.get("project_root") or "")
        rid = f"{rr.canon_path(tree)}|{r.get('started_at')}|{r.get('at')}"
        if not tree or rid in seen or rid in fresh:
            continue
        fresh.append(rid)
        green = r.get("exit_code") == 0 and str(r.get("failed")) == "0"
        names = [str(x) for x in r.get("failed_cases") or []]
        failed = _failed_rel(names, tree, [], tree) if names else []
        at = str(r.get("at") or "")
        repo = repo_key(tree)
        _record_run({"ev": "run", "repo": repo, "at": at, "key": "", "covers": _self_covers(r, tree), "failed": failed,
                     "failed_known": green or bool(failed), "green": green, "source": "self"})
        new = _attribute(repo, failed, at, "run_verify", False)
        if new:
            notes.append(_leak_notice(new))
    if fresh:
        _save_observed(seen + fresh)
    return notes


def advisory(cwd: str) -> List[str]:
    """SessionStart：這個 repo 待檢討的範圍漏判與累計數字（沒有任何結案紀錄就不出聲）。"""
    root = vl.file_root_of(cwd) if cwd else None
    repo = repo_key(root or cwd)
    if not repo:
        return []
    s = stats(repo)
    if not s["closed"] and not s["leaks"]:
        return []
    pend = pending_leaks(repo)
    if not pend:
        return [f"{TAG} {stats_line(repo)}"]
    lines = [f"{TAG} 範圍漏判待檢討 {len(pend)} 筆（下次宣告驗證範圍時要逐筆檢討：查明是不是該驗的沒驗到，"
             f"是的話寫沒驗到的根因與下次判斷範圍時要怎麼改）："]
    lines += [f"- {_leak_text(e)}" for e in pend[:5]]
    if len(pend) > 5:
        lines.append(f"- 另有 {len(pend) - 5} 筆")
    lines.append(stats_line(repo))
    return ["\n".join(lines)]
