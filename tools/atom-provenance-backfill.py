#!/usr/bin/env python3
"""atom-provenance-backfill — 對既有 atom 一次性補來源（Source／Quote）。

做什麼：掃本機 ~/.claude/projects/*/*.jsonl（Claude Code transcript），找出每顆 atom 是哪個
session、哪則使用者訊息觸發 atom_write 寫出來的，補 `- Source:` 與 `- Quote:`；transcript
已清（約 30 天）的 atom 補出處（建立日＋首次 commit）並固定措辭「原對話已逾保留期」。

分級：
  A        transcript 命中 atom_write → `Source: session:<sid8>#<uuid8> <日期>` ＋ `Quote: 「使用者原話」`
  A-ai     只找得到 `<!-- src: -->` 指標的自動萃取 atom → Source 同上，Quote 寫 `「AI：…」`（非使用者原話）
  B        無命中 → `Source: commit:<hash7> <日期>（原對話已逾保留期）`（無 git 用 `unknown <日期>（…）`）
  skip     已有 Quote（冪等）／既有 Source 非空且無命中／ambiguous（同檔名多層無法判定，不寫）

怎麼跑：
  python ~/.claude/tools/atom-provenance-backfill.py                 # dry-run，印摘要
  python ~/.claude/tools/atom-provenance-backfill.py --apply --json  # 真寫，JSON 報表
  --layer root|aidocs|project|org|all（預設 all）  --only <glob>（只處理符合的 atom 路徑）
  --quiet（worker 用：只寫 log 不印）
SessionStart 會在「有新 transcript」時 detached 跑一次 --apply（hooks/handlers/session_start.py）；
週健檢對快到期的 session 來源補 Quote（tools/health-weekly.py）。寫入走 lib.atom_io.edit_metadata，
source=tool:provenance-backfill；dry-run 不碰任何檔。
"""
from __future__ import annotations

import argparse
import fnmatch
import glob
import io
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

CLAUDE_DIR = Path(__file__).resolve().parent.parent
for _p in (str(CLAUDE_DIR), str(CLAUDE_DIR / "hooks")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lib.provenance import (  # noqa: E402
    format_quote, format_source_session, is_human_record, read_src_comment, record_text, sanitize_quote,
)

PROJECTS_DIR = CLAUDE_DIR / "projects"
AUDIT_LOG = CLAUDE_DIR / "memory" / "_meta" / "atom_io_audit.jsonl"
LOG_PATH = CLAUDE_DIR / "Logs" / "provenance-backfill.log"
LOCK_PATH = CLAUDE_DIR / "Logs" / "provenance-backfill.lock"
MARKER_PATH = CLAUDE_DIR / "workflow" / "provenance-backfill-last.json"
SOURCE = "tool:provenance-backfill"
EXPIRED = "（原對話已逾保留期）"
_SKIP_NAME_RE = re.compile(r"_INDEX|^MEMORY\.md$|_ATOM_INDEX|_local_catalog", re.I)
_SKIP_DIR_PARTS = {"_meta", "_distant", "_vectordb", "_staging", "episodic", "wisdom", "_reference"}
_PATH_RE = re.compile(r"Path:\s*(\S.*?\.md)\s*$", re.M)
_RECEIPT_PATH_RE = re.compile(r'"path"\s*:\s*"((?:[^"\\]|\\.)*)"')
_QUOTE_LINE_RE = re.compile(r"^- Quote:\s*\S", re.M)
_SOURCE_LINE_RE = re.compile(r"^- Source:\s*(\S.*)$", re.M)
_CREATED_RE = re.compile(r"^- Created-at:\s*(\d{4}-\d{2}-\d{2})", re.M)
_CONFIDENCE_RE = re.compile(r"^- Confidence:\s*\[", re.M)
_H1_RE = re.compile(r"^# (.+?)\s*$", re.M)


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip().casefold()


def _log(msg: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


# ─── transcript 索引（一趟掃描） ─────────────────────────────────────────────

@dataclass
class Hit:
    ts: str
    sid: str
    uuid: str            # tool_use 所在 assistant 記錄 uuid（回溯起點）
    path: str            # tool_result 回報的 atom 路徑
    mode: str
    transcript: str
    quote: Optional[str] = None       # 使用者原話（已消毒）；None＝找不到
    human_uuid: Optional[str] = None  # 原話記錄 uuid（Source 用）


@dataclass
class TranscriptIndex:
    by_title: Dict[str, List[Hit]] = field(default_factory=dict)
    by_stem: Dict[str, List[Hit]] = field(default_factory=dict)
    by_uuid: Dict[str, Dict[str, Any]] = field(default_factory=dict)   # uuid → 精簡記錄
    files: int = 0
    bad_lines: int = 0

    def add(self, title: str, hit: Hit) -> None:
        self.by_title.setdefault(_norm(title), []).append(hit)
        self.by_stem.setdefault(_norm(Path(hit.path).stem), []).append(hit)


def _tool_result_text(block: Dict[str, Any]) -> str:
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(str(b.get("text", "")) for b in c if isinstance(b, dict))
    return ""


def _result_path(text: str) -> Optional[str]:
    m = _PATH_RE.search(text)
    if m:
        return m.group(1).strip()
    m = _RECEIPT_PATH_RE.search(text)
    if m:
        try:
            return json.loads(f'"{m.group(1)}"')
        except ValueError:
            return m.group(1).replace("\\\\", "\\")
    return None


def build_transcript_index(projects_dir: Path = PROJECTS_DIR) -> TranscriptIndex:
    idx = TranscriptIndex()
    pending: Dict[str, Tuple[str, str, str, str, str, str]] = {}  # tool_use_id → (uuid, ts, title, mode, sid, file)
    humans_by_sid: Dict[str, List[Tuple[str, str, str]]] = {}      # sid → [(ts, uuid, text)] 主線真人
    for fp in sorted(projects_dir.glob("*/*.jsonl")):
        idx.files += 1
        try:
            fh = open(fp, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    idx.bad_lines += 1
                    continue
                if not isinstance(rec, dict):
                    continue
                uuid = rec.get("uuid")
                rtype = rec.get("type")
                ts = str(rec.get("timestamp") or "")
                sid = str(rec.get("sessionId") or fp.stem)
                side = bool(rec.get("isSidechain"))
                msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
                content = msg.get("content")
                blocks = content if isinstance(content, list) else []
                human = rtype == "user" and is_human_record(rec)
                text = record_text(rec) if (human or rtype == "assistant") else ""
                if isinstance(uuid, str):
                    idx.by_uuid[uuid] = {"parent": rec.get("parentUuid"), "type": rtype, "ts": ts,
                                         "side": side, "human": human, "text": text if (human or rtype == "assistant") else ""}
                if human and not side and isinstance(uuid, str):
                    humans_by_sid.setdefault(sid, []).append((ts, uuid, text))
                if rtype == "assistant":
                    for b in blocks:
                        if not isinstance(b, dict) or b.get("type") != "tool_use":
                            continue
                        if not str(b.get("name", "")).endswith("atom_write"):
                            continue
                        inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                        if inp.get("mode") not in ("create", "replace"):
                            continue
                        pending[str(b.get("id"))] = (str(uuid), ts, str(inp.get("title") or ""), str(inp["mode"]), sid, str(fp))
                elif rtype == "user":
                    for b in blocks:
                        if not isinstance(b, dict) or b.get("type") != "tool_result":
                            continue
                        key = str(b.get("tool_use_id"))
                        tu = pending.pop(key, None)
                        if tu is None or b.get("is_error"):
                            continue
                        rtext = _tool_result_text(b)
                        path = _result_path(rtext)
                        if not path or "Error" in rtext[:12]:
                            continue
                        tu_uuid, tu_ts, title, mode, tu_sid, tfile = tu
                        if title:
                            idx.add(title, Hit(ts=tu_ts, sid=tu_sid, uuid=tu_uuid, path=path, mode=mode, transcript=tfile))
    for lst in humans_by_sid.values():
        lst.sort()
    # 回溯原話：沿 parentUuid 走到最近真人；sidechain 走不到 → 同 sid 主線 ts≤hit 最近一則
    for hits in idx.by_title.values():
        for h in hits:
            _resolve_quote(h, idx, humans_by_sid)
    return idx


def _resolve_quote(h: Hit, idx: TranscriptIndex, humans_by_sid: Dict[str, List[Tuple[str, str, str]]]) -> None:
    cur = h.uuid
    seen = set()
    steps = 0
    while cur and cur not in seen and steps < 500:
        seen.add(cur)
        steps += 1
        rec = idx.by_uuid.get(cur)
        if rec is None:
            break
        if rec.get("human"):
            q = sanitize_quote(rec.get("text") or "")
            h.human_uuid = cur
            h.quote = q or None
            return
        cur = rec.get("parent")
    cands = [t for t in humans_by_sid.get(h.sid, []) if t[0] <= h.ts]
    if cands:
        ts, uid, text = cands[-1]
        h.human_uuid = uid
        h.quote = sanitize_quote(text) or None


# ─── atom 掃描 ───────────────────────────────────────────────────────────────

def _iter_md(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return
    for p in root.rglob("*.md"):
        if _SKIP_NAME_RE.search(p.name):
            continue
        if any(part in _SKIP_DIR_PARTS for part in p.relative_to(root).parts[:-1]):
            continue
        yield p


def collect_atoms(layer: str = "all") -> List[Tuple[str, Path]]:
    out: List[Tuple[str, Path]] = []
    if layer in ("root", "all"):
        out += [("root", p) for p in _iter_md(CLAUDE_DIR / "memory")]
    if layer in ("aidocs", "all"):
        out += [("aidocs", p) for p in _iter_md(CLAUDE_DIR / "_AIDocs" / "_atoms")]
    if layer in ("project", "all"):
        try:
            import wg_core
            for _slug, mem in wg_core.discover_all_project_memory_dirs():
                out += [("project", p) for p in _iter_md(Path(mem))]
        except Exception as e:  # 專案層發現失敗不擋根層
            _log(f"discover_project_dirs failed: {e}")
    if layer in ("org", "all"):
        try:
            import wg_core
            org = wg_core.org_memory_root()
            if org:
                out += [("org", p) for p in _iter_md(Path(org) / ".claude" / "memory")]
        except Exception as e:
            _log(f"org_memory_root failed: {e}")
    return out


# ─── B 級日期來源 ─────────────────────────────────────────────────────────────

def _audit_earliest_by_basename() -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not AUDIT_LOG.is_file():
        return out
    try:
        with open(AUDIT_LOG, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("op") not in ("atom_create", "write", "failure_create"):
                    continue
                if d.get("source") == "test" or "pytest-of-" in str(d.get("path", "")):
                    continue
                base = _norm(Path(str(d.get("path") or "")).name)
                ts = str(d.get("ts") or "")[:10]
                if base and ts and (base not in out or ts < out[base]):
                    out[base] = ts
    except OSError:
        pass
    return out


def _vcs_root(p: Path) -> Optional[Tuple[str, Path]]:
    for anc in [p.parent, *p.parents]:
        if (anc / ".git").exists():
            return ("git", anc)
        if (anc / ".svn").is_dir():
            return ("svn", anc)
    return None


def _git_first_commit(repo: Path, rel: str) -> Optional[Tuple[str, str]]:
    try:
        r = subprocess.run(["git", "-C", str(repo), "log", "--diff-filter=A", "--follow",
                            "--format=%H%x09%aI", "--", rel],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    lines = [l for l in (r.stdout or "").splitlines() if "\t" in l]
    if r.returncode != 0 or not lines:
        return None
    h, ts = lines[-1].split("\t", 1)
    return h[:7], ts[:10]


def b_level_source(path: Path, text: str, audit: Dict[str, str]) -> Tuple[str, str]:
    """回 (Source 值, 日期來源標籤)。"""
    m = _CREATED_RE.search(text)
    d = m.group(1) if m else ""
    src_label = "created_at" if d else ""
    if not d:
        d = audit.get(_norm(path.name), "")
        src_label = "audit" if d else ""
    vcs = _vcs_root(path)
    h = None
    if vcs and vcs[0] == "git":
        fc = _git_first_commit(vcs[1], str(path.relative_to(vcs[1])).replace("\\", "/"))
        if fc:
            h, gd = fc
            if not d:
                d, src_label = gd, "git"
    if not d:
        d = date.fromtimestamp(path.stat().st_mtime).isoformat()
        src_label = "mtime"
    return (f"commit:{h} {d}{EXPIRED}" if h else f"unknown {d}{EXPIRED}"), src_label


# ─── 主流程 ─────────────────────────────────────────────────────────────────

def _pick_hit(hits: List[Hit], atom_path: Path, same_base_count: int) -> Tuple[Optional[Hit], str]:
    base = _norm(atom_path.name)
    cands = [h for h in hits if _norm(Path(h.path).name) == base]
    if not cands:
        return None, "no_basename_match"
    exact = [h for h in cands if _norm(str(Path(h.path))) == _norm(str(atom_path))]
    if not exact and same_base_count > 1:
        return None, "ambiguous"
    pool = exact or cands
    pool.sort(key=lambda h: (0 if h.mode == "create" else 1, h.ts))
    return pool[0], ""


def backfill(*, apply: bool = False, layer: str = "all", only: Optional[List[str]] = None,
             index: Optional[TranscriptIndex] = None, projects_dir: Path = PROJECTS_DIR,
             atoms: Optional[List[Tuple[str, Path]]] = None) -> Dict[str, Any]:
    idx = index if index is not None else build_transcript_index(projects_dir)
    atoms = atoms if atoms is not None else collect_atoms(layer)
    if only:
        atoms = [(l, p) for (l, p) in atoms if any(fnmatch.fnmatch(str(p).replace("\\", "/"), pat) for pat in only)]
    base_count: Dict[str, int] = {}
    for _l, p in atoms:
        base_count[_norm(p.name)] = base_count.get(_norm(p.name), 0) + 1
    audit = _audit_earliest_by_basename()
    summary = {"A": 0, "A_ai": 0, "A_noquote": 0, "B": 0, "skip": 0, "ambiguous": 0, "error": 0, "atoms": len(atoms),
               "transcripts": idx.files, "apply": apply}
    results: List[Dict[str, Any]] = []
    edit_metadata = None
    if apply:
        from lib.atom_io import edit_metadata as _em
        edit_metadata = _em
    for layer_name, path in atoms:
        r: Dict[str, Any] = {"path": str(path), "layer": layer_name, "grade": "skip", "reason": ""}
        try:
            text = path.read_text(encoding="utf-8-sig")
            if _QUOTE_LINE_RE.search(text):
                r["reason"] = "has_quote"
                results.append(r); summary["skip"] += 1
                continue
            if not _CONFIDENCE_RE.search(text):
                r["reason"] = "not_atom"  # 記憶目錄裡的規劃／現況文件，沒有 metadata 區塊
                results.append(r); summary["skip"] += 1
                continue
            sm = _SOURCE_LINE_RE.search(text)
            existing_source = sm.group(1).strip() if sm else ""
            h1 = _H1_RE.search(text)
            title = h1.group(1) if h1 else path.stem
            hits = list(idx.by_title.get(_norm(title), [])) + [
                h for h in idx.by_stem.get(_norm(path.stem), []) if h not in idx.by_title.get(_norm(title), [])]
            hit, why = _pick_hit(hits, path, base_count.get(_norm(path.name), 1)) if hits else (None, "no_hit")
            provenance: Optional[str] = None
            quote: Optional[str] = None
            if hit is not None:
                r["grade"] = "A" if hit.quote else "A_noquote"
                r["hit"] = {"sid": hit.sid[:8], "uuid": (hit.human_uuid or hit.uuid)[:8], "ts": hit.ts, "mode": hit.mode}
                if not existing_source:
                    provenance = format_source_session(hit.sid, hit.human_uuid, hit.ts[:10] or date.today().isoformat())
                quote = format_quote(hit.quote) if hit.quote else None
                if provenance is None and quote is None:
                    r["grade"], r["reason"] = "skip", "has_source_no_quote_found"
            elif why == "ambiguous":
                r["grade"], r["reason"] = "skip", "ambiguous"
                summary["ambiguous"] += 1
            else:
                src = read_src_comment(text)
                if src and not existing_source:
                    sid8, uuid8 = src
                    rec = next((v for k, v in idx.by_uuid.items() if k.startswith(uuid8)), None)
                    d = (rec or {}).get("ts", "")[:10] or (_CREATED_RE.search(text).group(1) if _CREATED_RE.search(text) else date.today().isoformat())
                    provenance = f"session:{sid8}#{uuid8} {d}"
                    ai_q = sanitize_quote((rec or {}).get("text") or "", max_chars=196)
                    quote = format_quote("AI：" + ai_q) if ai_q else None
                    r["grade"] = "A_ai"
                elif existing_source:
                    r["reason"] = "has_source_no_match"
                else:
                    provenance, r["date_src"] = b_level_source(path, text, audit)
                    r["grade"] = "B"
            r["source"], r["quote"] = provenance, quote
            if r["grade"] == "skip":
                summary["skip"] += 1
            else:
                summary[r["grade"]] += 1
                if apply and edit_metadata is not None:
                    res = edit_metadata(path, provenance=provenance, quote=quote, source=SOURCE)
                    r["written"] = bool(res.ok)
                    if not res.ok:
                        r["error"] = res.error or "edit_failed"
                        summary["error"] += 1
        except Exception as e:
            r["grade"], r["error"] = "error", f"{type(e).__name__}: {e}"
            summary["error"] += 1
        results.append(r)
    return {"summary": summary, "results": results}


# ─── SessionStart 觸發判定與 worker 鎖 ────────────────────────────────────────

def newest_transcript_mtime(projects_dir: Path = PROJECTS_DIR) -> float:
    try:
        return max((p.stat().st_mtime for p in projects_dir.glob("*/*.jsonl")), default=0.0)
    except OSError:
        return 0.0


def needs_run(projects_dir: Path = PROJECTS_DIR, marker: Path = MARKER_PATH) -> bool:
    """有 transcript 且（沒跑過或有比上次更新的 transcript）→ True。只看 mtime，不掃 atom，<50ms。"""
    newest = newest_transcript_mtime(projects_dir)
    if newest <= 0:
        return False
    try:
        last = json.loads(marker.read_text(encoding="utf-8"))
        return float(last.get("newest_transcript_mtime", 0)) < newest
    except (OSError, ValueError, TypeError):
        return True


def _write_marker(summary: Dict[str, Any], projects_dir: Path = PROJECTS_DIR, marker: Path = MARKER_PATH) -> None:
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                  "newest_transcript_mtime": newest_transcript_mtime(projects_dir),
                                  "summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def _acquire_lock() -> bool:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        if time.time() - LOCK_PATH.stat().st_mtime < 3600:
            return False
        LOCK_PATH.unlink(missing_ok=True)
    LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8", newline="\n")
    return True


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="對既有 atom 回填 Source／Quote（預設 dry-run）")
    ap.add_argument("--apply", action="store_true", help="真寫入（預設只預覽）")
    ap.add_argument("--json", action="store_true", help="輸出 JSON 報表")
    ap.add_argument("--layer", default="all", choices=["root", "aidocs", "project", "org", "all"])
    ap.add_argument("--only", action="append", help="只處理路徑符合此 glob 的 atom（可重複）")
    ap.add_argument("--quiet", action="store_true", help="worker 用：不印到 stdout，只寫 Logs/provenance-backfill.log")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if a.apply and not _acquire_lock():
        msg = "another backfill is running (lock < 1h); skip"
        _log(msg)
        if not a.quiet:
            print(f"[provenance-backfill] {msg}", file=sys.stderr)
        return 3
    try:
        t0 = time.time()
        rep = backfill(apply=a.apply, layer=a.layer, only=a.only)
        rep["summary"]["elapsed_s"] = round(time.time() - t0, 2)
        if a.apply:
            _write_marker(rep["summary"])
        _log(f"{'apply' if a.apply else 'dry-run'} {json.dumps(rep['summary'], ensure_ascii=False)}")
        if a.quiet:
            return 0 if rep["summary"]["error"] == 0 else 1
        if a.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            s = rep["summary"]
            print(f"[provenance-backfill] {'APPLY' if a.apply else 'DRY-RUN'} atoms={s['atoms']} transcripts={s['transcripts']} "
                  f"A={s['A']} A_ai={s['A_ai']} A_noquote={s['A_noquote']} B={s['B']} skip={s['skip']} "
                  f"ambiguous={s['ambiguous']} error={s['error']} ({s['elapsed_s']}s)")
            for r in rep["results"]:
                if r["grade"] in ("A", "A_ai", "A_noquote", "B", "error") or r.get("reason") == "ambiguous":
                    print(f"  {r['grade']:<9} {Path(r['path']).name}  {r.get('source') or ''}  {r.get('quote') or ''}  {r.get('error') or r.get('reason') or ''}")
        return 0 if rep["summary"]["error"] == 0 else 1
    finally:
        if a.apply:
            LOCK_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
