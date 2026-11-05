"""atom_feedback.py — 記憶卡「有用／誤導」明確回饋票，跨機器、跨使用者累計到晉升判定。

做什麼：
  - vote：對一張卡投 helpful / misleading。票追加到 <memory_root>/_votes/<user>.jsonl
    （每人一檔、只追加，會進版控、靠 vcs-sync 跨機同步），並立刻套到本機 sidecar
    （.access.json 的 useful_hits=α / used_fail=β，晉升看它的 Wilson 下界）。
  - fold：掃 _votes/*.jsonl，把別人／別台機器投的、本機還沒套過的票套進本機 sidecar。
    已套清單存本機 <memory_root>/_meta/feedback-votes-applied.json（不進版控），重跑冪等。

怎麼跑（stdout 一行 JSON，失敗 exit 1、error 印 stderr）：
  python -m lib.atom_feedback vote <atom.md> --verdict helpful|misleading [--by X] [--note ...] [--source mcp]
  python -m lib.atom_feedback fold [--root <memory_dir>]...
"""

from __future__ import annotations

import getpass
import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import atom_access
from .atom_access import (
    record_usefulness, read_access, usefulness_stats, usefulness_promote_eligible,
)
from .atom_io import GLOBAL_MEMORY_DIR, _atomic_write
from .atom_locations import LOCAL_ATOMS_DIR

VERDICTS = ("helpful", "misleading")
FEEDBACK_SOURCE = "user:feedback"
_PROJECT_MARK = "/.claude/memory/"


def _user() -> str:
    return os.environ.get("USERNAME") or getpass.getuser()


def _memory_root_of(atom_path: Path) -> Path:
    """票據檔跟著卡住的那棵樹走，三種樹 vcs-sync 都會同步：
    專案層（路徑含 /.claude/memory/）→ 該專案 memory；local realm（_AIDocs/_atoms）→ 該目錄；其餘 → 全域 memory。"""
    resolved = atom_path.resolve()
    posix = resolved.as_posix()
    idx = posix.find(_PROJECT_MARK)
    if idx >= 0:
        return Path(posix[: idx + len(_PROJECT_MARK) - 1])
    if resolved.is_relative_to(LOCAL_ATOMS_DIR.resolve()):
        return LOCAL_ATOMS_DIR
    return GLOBAL_MEMORY_DIR


def _project_roots_from(cwd: Path) -> List[Path]:
    """cwd 往上每層的 .claude/memory（SessionEnd 的 cwd 就是專案目錄）。"""
    return [p / ".claude" / "memory" for p in (cwd, *cwd.parents) if (p / ".claude" / "memory").is_dir()]


def _applied_path(root: Path) -> Path:
    return root / "_meta" / "feedback-votes-applied.json"


def _load_applied(root: Path) -> set:
    p = _applied_path(root)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except (OSError, ValueError) as e:
        print(f"[atom_feedback] applied list unreadable, treat as empty: {e}", file=sys.stderr)
        return set()


def _save_applied(root: Path, applied: set) -> None:
    p = _applied_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(p, json.dumps(sorted(applied), ensure_ascii=False))


def _apply(atom_path: Path, verdict: str) -> None:
    record_usefulness(
        atom_path, used=True, success=(verdict == "helpful"), source=FEEDBACK_SOURCE,
    )


def record_vote(
    atom_path: Path, verdict: str, *,
    by: Optional[str] = None, note: str = "", source: str = "mcp",
    memory_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """投一票：追加票據、立刻套本機 sidecar、記入已套清單。
    memory_root 預設由 atom 路徑推得（測試／特殊佈局可覆寫）。"""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}, got {verdict!r}")
    atom_path = Path(atom_path)
    if not atom_path.exists():
        raise ValueError(f"atom not found: {atom_path}")
    root = Path(memory_root) if memory_root else _memory_root_of(atom_path)
    try:
        path_rel = atom_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        raise ValueError(f"atom {atom_path} is not under memory root {root}")

    user = by or _user()
    vote_id = f"{int(time.time() * 1000)}-{secrets.token_hex(3)}"
    vote = {
        "id": vote_id,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "by": user,
        "atom": atom_path.stem,
        "path_rel": path_rel,
        "verdict": verdict,
        "note": note,
        "source": source,
    }
    vote_file = root / "_votes" / f"{user}.jsonl"
    vote_file.parent.mkdir(parents=True, exist_ok=True)
    with open(vote_file, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(vote, ensure_ascii=False) + "\n")

    _apply(atom_path, verdict)
    applied = _load_applied(root)
    applied.add(vote_id)
    _save_applied(root, applied)

    access = read_access(atom_path)
    st = usefulness_stats(access)
    return {
        "ok": True, "id": vote_id,
        "useful_hits": st["alpha"], "used_fail": st["beta"],
        "lower_bound": st["lower_bound"], "n": st["n"],
        "promote_eligible": usefulness_promote_eligible(access),
    }


def _fold_root(root: Path, out: Dict[str, Any]) -> None:
    votes_dir = root / "_votes"
    if not votes_dir.is_dir():
        return
    applied = _load_applied(root)
    before = len(applied)
    for vf in sorted(votes_dir.glob("*.jsonl")):
        for line in vf.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                v = json.loads(line)
                vid, rel, verdict = v["id"], v["path_rel"], v["verdict"]
            except (ValueError, KeyError, TypeError):
                out["bad_lines"] += 1
                continue
            if verdict not in VERDICTS:
                out["bad_lines"] += 1
                continue
            if vid in applied:
                out["skipped"] += 1
                continue
            atom_path = root / rel
            if not atom_path.exists():
                out["missing"] += 1
                continue
            _apply(atom_path, verdict)
            applied.add(vid)
            out["applied"] += 1
    if len(applied) != before:
        _save_applied(root, applied)


def fold_votes(memory_roots: Optional[List[Path]] = None, cwd: Optional[Path] = None) -> Dict[str, Any]:
    """把本機還沒套過的票套進 sidecar；冪等。
    不給 memory_roots 時掃全域 memory、local realm、以及 cwd（預設目前目錄）往上的專案 memory。"""
    if memory_roots:
        roots = [Path(r) for r in memory_roots]
    else:
        roots = [GLOBAL_MEMORY_DIR, LOCAL_ATOMS_DIR, *_project_roots_from(Path(cwd or Path.cwd()).resolve())]
    out: Dict[str, Any] = {
        "applied": 0, "skipped": 0, "missing": 0, "bad_lines": 0,
        "roots": [str(r) for r in roots],
    }
    for root in roots:
        _fold_root(root, out)
    return out


def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="atom_feedback")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_vote = sub.add_parser("vote")
    p_vote.add_argument("path")
    p_vote.add_argument("--verdict", required=True, choices=VERDICTS)
    p_vote.add_argument("--by", default=None)
    p_vote.add_argument("--note", default="")
    p_vote.add_argument("--source", default="mcp")

    p_fold = sub.add_parser("fold")
    p_fold.add_argument("--root", action="append", default=None)

    args = parser.parse_args()
    try:
        if args.cmd == "vote":
            res = record_vote(
                Path(args.path), args.verdict,
                by=args.by, note=args.note, source=args.source,
            )
        else:
            res = fold_votes([Path(r) for r in args.root] if args.root else None)
            res["ok"] = True
        print(json.dumps(res, ensure_ascii=False))
    except (ValueError, OSError) as e:
        print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
