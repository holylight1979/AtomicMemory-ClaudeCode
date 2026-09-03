#!/usr/bin/env python3
"""heal-review.py — 記憶自癒失敗佇列的人工裁決後端（/heal-review skill）

atom-heal.py 修不好（驗證不過 / needs_human）時會在 memory/_heal_review/<atom>.json
留診斷卡。本工具列卡 + 人工裁決：
  list                列出待人工的卡（atom / 壞在哪 / LLM 提案 / 失敗原因）
  show  <atom>        看單張卡完整內容
  resolve <atom>      標記已修好 → 清卡（會先重掃確認真的健康，未健康需 --force）
  dismiss <atom>      決定不修 → 清卡（won't-fix）
resolve/dismiss 需 management 角色（裁決權，沿用 conflict-review 認證）。
JSON over stdout；非零 exit code 代表操作失敗。
"""
import sys, io, json, argparse, subprocess
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CLAUDE = Path.home() / ".claude"
MEMORY = CLAUDE / "memory"
REVIEW = MEMORY / "_heal_review"
TOOLS = CLAUDE / "tools"

sys.path.insert(0, str(CLAUDE / "hooks"))
try:
    from wg_roles import is_management, get_current_user   # noqa: E402
except Exception:
    def is_management(): return True          # 角色模組缺 → 不阻擋（單人環境）
    def get_current_user(): return "unknown"


def _iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(action, atom, by, detail):
    try:
        with open(MEMORY / "_merge_history.log", "a", encoding="utf-8", newline="\n") as f:
            f.write("\t".join([_iso(), action, atom, "global", by or "-", detail or "-"]) + "\n")
    except OSError:
        pass


def list_cards():
    cards = []
    if REVIEW.is_dir():
        for f in sorted(REVIEW.glob("*.json")):
            try:
                cards.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                cards.append({"atom": f.stem, "_parse_error": True})
    return cards


def rescan(atom):
    try:
        r = subprocess.run([sys.executable, str(TOOLS / "atom-health-check.py"), "--atom", atom, "--json"],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        h = json.loads(r.stdout)
        n = len(h.get("broken_refs") or []) + len(h.get("missing_reverse_refs") or [])
        return n, h
    except Exception as e:
        return -1, {"_err": str(e)}


def emit(obj, as_json, code=0):
    print(json.dumps(obj, ensure_ascii=False, **({} if as_json else {"indent": 2})))
    sys.exit(code)


def main():
    ap = argparse.ArgumentParser(description="記憶自癒失敗佇列裁決")
    ap.add_argument("action", choices=["list", "show", "resolve", "dismiss"])
    ap.add_argument("atom", nargs="?")
    ap.add_argument("--force", action="store_true", help="resolve 時即使仍有問題也清卡")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.action == "list":
        cards = list_cards()
        summary = [{
            "atom": c.get("atom"), "level": c.get("level"), "action": c.get("action"),
            "needs_human": c.get("needs_human"), "created_at": c.get("created_at"),
            "broken_after": (c.get("verification") or {}).get("broken_after"),
            "proposals": c.get("proposals"),
        } for c in cards]
        emit({"ok": True, "count": len(summary), "cards": summary}, a.json)

    if not a.atom:
        emit({"ok": False, "error": "需指定 atom"}, a.json, 1)
    p = REVIEW / f"{a.atom}.json"

    if a.action == "show":
        if not p.exists():
            emit({"ok": False, "error": "找不到該卡"}, a.json, 1)
        emit({"ok": True, "card": json.loads(p.read_text(encoding="utf-8"))}, a.json)

    # resolve / dismiss → 需 management
    if not is_management():
        emit({"ok": False, "error": "需 management 角色才能裁決（resolve/dismiss）"}, a.json, 1)
    if not p.exists():
        emit({"ok": False, "error": "找不到該卡"}, a.json, 1)
    by = get_current_user()

    if a.action == "resolve":
        n, h = rescan(a.atom)
        if n > 0 and not a.force:
            emit({"ok": False, "error": f"該 atom 仍有 {n} 個問題；請先修好或加 --force", "health": h}, a.json, 1)
        p.unlink()
        _log("heal_resolved", a.atom, by, f"remaining={n}")
        emit({"ok": True, "resolved": a.atom, "remaining_issues": n}, a.json)

    if a.action == "dismiss":
        p.unlink()
        _log("heal_dismissed", a.atom, by, "won't-fix")
        emit({"ok": True, "dismissed": a.atom}, a.json)


if __name__ == "__main__":
    main()
