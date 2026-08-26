#!/usr/bin/env python3
"""atom-heal.py — 記憶自癒（單一來源；腦內世界 P3）

分級修復一個壞掉的 atom，腳本主導、判斷才呼 LLM、修完即驗證：
  L1 missing_reverse_refs → 機械補反向連結（免 LLM，零成本）
  L2 broken_refs / 格式錯  → 呼 LLM 出「結構化修復提案」→ 腳本經 funnel 套用 → 驗證
  L3 stale (>60d)         → 非真壞，回 wake（不修）
  修不好（驗證不過 / needs_human）→ fixed=False + needs_human=True，由 caller 退回人工審查

L1 與 SessionEnd 重疊，dedup 契約：反向連結（L1）SessionEnd 已跑 atom-health-check
  --fix-refs 全庫機械補齊。故「背景/批次」呼叫者（server.js /api/heal-all）只餵 broken_refs
  的 atom（→ 分級 L2，僅治死連結，不碰 reverse），別對純 L1 的 atom 重覆跑。單一 atom 的
  L1 仍由診所 /api/heal/:atom 按需觸發（世界 UI 用，非批次）。

重用（不重寫）：
  tools/atom-health-check.py  偵測(single_atom_report) + reverse 修復邏輯（importlib 載入）
  lib/atom_io.edit_metadata   改 Related（byte-stable + audit，source=tool:atom-heal）
  lib/atom_spec.validate_atom_content  格式驗證
  tools/ollama_client.get_client      本地 LLM 判斷（預設 backend；雲端為選配）

用法：
  python atom-heal.py --atom <name> [--apply] [--backend ollama|cloud|none] [--json]
    無 --apply＝dry-run（只診斷分級 + L2 出提案，不寫檔）
"""
import sys, io, json, re, argparse, difflib, importlib.util
from datetime import datetime
from pathlib import Path

# Windows cp950 → 強制 UTF-8（先於 import atom-health-check，避免它二次包裝）
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent          # ~/.claude
TOOLS = ROOT / "tools"
MEMORY = ROOT / "memory"
HEAL_SOURCE = "tool:atom-heal"

sys.path.insert(0, str(ROOT))                          # lib.*
sys.path.insert(0, str(TOOLS))                         # ollama_client
from lib.atom_io import edit_metadata                  # noqa: E402
from lib.atom_spec import validate_atom_content        # noqa: E402
from lib.atom_locations import LEGACY_FAILURES_DIR     # noqa: E402  舊址 _AIDocs/Failures/（遷移期讀端相容）

# atom-health-check.py 檔名含連字號、無法直接 import → importlib 載入，重用其偵測/解析函式
_spec = importlib.util.spec_from_file_location("atom_health_check", TOOLS / "atom-health-check.py")
ahc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ahc)


# ── 共用小工具 ─────────────────────────────────────────────────────────────
def atom_file(name):
    """找出 atom 的 .md 路徑：memory/ 遞迴（含 memory/Failures/<主題>/，跳過 _ 前綴目錄），
    再退舊址 _AIDocs/Failures/（尚未遷入的 feedback-*）。"""
    if not name:
        return None
    for p in MEMORY.rglob(f"{name}.md"):
        if not any(part.startswith("_") for part in p.relative_to(MEMORY).parts[:-1]):
            return p
    if LEGACY_FAILURES_DIR.is_dir():
        for p in LEGACY_FAILURES_DIR.rglob(f"{name}.md"):
            return p
    return None


def related_of(path):
    """讀該 atom 目前的 Related 清單（重用 ahc 的解析，與偵測同源）。"""
    try:
        return [r for r in ahc.parse_related(ahc.parse_frontmatter(path)) if r and r != "(none)"]
    except Exception:
        return []


def scan(name, atoms, aliases):
    """針對性重掃單一 atom（重用 single_atom_report；每次重讀檔 → 反映剛套用的修復）。"""
    return ahc.single_atom_report(name, atoms, aliases)


def classify(report):
    broken = report.get("broken_refs") or []
    reverse = report.get("missing_reverse_refs") or []
    stale = report.get("stale_atoms") or []
    path = atom_file(report.get("atom"))
    fmt_err = validate_atom_content(path.read_text(encoding="utf-8")) if path and path.exists() else None
    if broken or fmt_err:
        return "L2", fmt_err
    if reverse:
        return "L1", None
    if stale:
        return "L3", None
    return "noop", None


# ── L1：機械補反向連結（免 LLM）──────────────────────────────────────────────
def heal_L1(name, report, atoms, aliases, apply):
    rev = report.get("missing_reverse_refs") or []
    # reverse 項：atom_a → atom_b 存在，但 atom_b → atom_a 缺 → 需把 atom_a 加進 atom_b 的 Related
    plans = [{"add_to": r["atom_b"], "ref": r["atom_a"]} for r in rev]
    if not apply:
        return {"level": "L1", "action": "reverse_ref_fix", "applied": False,
                "plans": plans, "fixed": False, "needs_human": False, "note": "dry-run"}
    applied = []
    for pl in plans:
        tpath = atoms.get(pl["add_to"]) or atom_file(pl["add_to"])
        if not tpath:
            applied.append({**pl, "ok": False, "err": "目標 atom 檔不存在"}); continue
        related = related_of(tpath)
        if pl["ref"] in related:
            applied.append({**pl, "ok": True, "skipped": "已存在"}); continue
        related.append(pl["ref"])
        res = edit_metadata(tpath, related=related, source=HEAL_SOURCE)
        applied.append({**pl, "ok": bool(getattr(res, "ok", False)), "err": getattr(res, "error", None)})
    after = scan(name, atoms, aliases)
    ok = len(after.get("missing_reverse_refs") or []) == 0
    return {"level": "L1", "action": "reverse_ref_fix", "applied": True, "fixes": applied,
            "verification": {"reverse_after": after.get("missing_reverse_refs") or []},
            "fixed": ok, "needs_human": not ok}


# ── L2：死連結 / 格式 → LLM 出提案，腳本套用安全提案 ─────────────────────────
def _extract_json(s):
    """剝 ```json``` 圍欄 + 取首個 {…}（本地 crack 模型常無視 format=json 而加圍欄）。"""
    s = (s or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    i, j = s.find("{"), s.rfind("}")
    return s[i:j + 1] if (i != -1 and j > i) else s


def _ollama_propose(name, content, bad_ref, candidates):
    """呼本地 Ollama 判斷死連結怎麼修；只回 repoint/remove/needs_human。失敗一律 needs_human。"""
    near = difflib.get_close_matches(bad_ref, candidates, n=12, cutoff=0.3) or candidates[:30]
    usr = (
        f"原子「{name}」的 Related 欄含一個指向不存在原子的死連結：「{bad_ref}」。\n"
        f"現有原子候選（可能是打錯字想指的對象）：{', '.join(near)}\n"
        "判斷該怎麼修：\n"
        f"- 若「{bad_ref}」明顯是某候選的錯字/變體 → repoint 到那個候選\n"
        "- 若該連結對象根本不該存在、無對應 → remove 移除\n"
        "- 若需要新建原子或無法判斷 → needs_human\n"
        '只回 JSON：{"action":"repoint|remove|needs_human","target":"<候選名或 null>","reason":"<簡短理由>"}'
    )
    try:
        from ollama_client import get_client
        raw = get_client().generate(usr, timeout=60, format="json")
        obj = json.loads(_extract_json(raw))
        act = obj.get("action")
        tgt = obj.get("target")
        if act not in ("repoint", "remove", "needs_human"):
            return {"action": "needs_human", "target": tgt, "reason": f"提案 action 非法：{act}"}
        if act == "repoint" and tgt not in candidates:                 # 安全：repoint 必須指向真實候選
            return {"action": "needs_human", "target": tgt, "reason": f"repoint 目標 {tgt} 不存在"}
        return {"action": act, "target": tgt, "reason": str(obj.get("reason", ""))[:200]}
    except Exception as e:
        return {"action": "needs_human", "target": None, "reason": f"LLM 判斷失敗：{str(e)[:150]}"}


def _propose(name, content, bad_ref, candidates, backend):
    if backend == "ollama":
        return _ollama_propose(name, content, bad_ref, candidates)
    if backend == "cloud":
        # 選配：雲端後端（claude -p / API）。預設未實作 → 退回人工，不阻斷流程。
        return {"action": "needs_human", "target": None, "reason": "cloud 後端尚未啟用（config.heal.backend）"}
    return {"action": "needs_human", "target": None, "reason": f"backend={backend}：未啟用自動判斷"}


def heal_L2(name, report, atoms, aliases, apply, backend):
    broken = report.get("broken_refs") or []
    path = atom_file(name)
    content = path.read_text(encoding="utf-8") if path else ""
    fmt_err = validate_atom_content(content) if content else "atom 檔不存在"
    candidates = sorted(atoms.keys())
    related = related_of(path) if path else []
    new_related = list(related)
    proposals, needs_human = [], False

    for b in broken:
        bad = b["missing_ref"]
        prop = _propose(name, content, bad, candidates, backend)
        proposals.append({"missing_ref": bad, **prop})
        if prop["action"] == "repoint" and prop.get("target") in atoms:
            new_related = [prop["target"] if x == bad else x for x in new_related]
        elif prop["action"] == "remove":
            new_related = [x for x in new_related if x != bad]
        else:
            needs_human = True                                          # 該死連結交人工

    # 純格式問題（無死連結）：不自動改寫知識內容 → 交人工
    if fmt_err and not broken:
        needs_human = True
        proposals.append({"format_error": fmt_err, "action": "needs_human"})

    if not apply:
        return {"level": "L2", "action": "broken_ref_fix", "applied": False,
                "proposals": proposals, "fixed": False, "needs_human": needs_human, "note": "dry-run"}

    apply_res = None
    if path and new_related != related:
        res = edit_metadata(path, related=new_related, source=HEAL_SOURCE)
        apply_res = {"ok": bool(getattr(res, "ok", False)), "err": getattr(res, "error", None), "related": new_related}

    after = scan(name, atoms, aliases)
    fmt_after = validate_atom_content(path.read_text(encoding="utf-8")) if path and path.exists() else "missing"
    broken_after = after.get("broken_refs") or []
    ok = (len(broken_after) == 0) and (fmt_after is None) and not needs_human
    return {"level": "L2", "action": "broken_ref_fix", "applied": True, "proposals": proposals,
            "apply_result": apply_res,
            "verification": {"broken_after": broken_after, "format_after": fmt_after},
            "fixed": ok, "needs_human": not ok}


# ── L3：stale 喚醒（非真壞）──────────────────────────────────────────────────
def heal_L3(name, report):
    return {"level": "L3", "action": "wake", "fixed": True, "needs_human": False,
            "stale": report.get("stale_atoms") or [], "note": "stale 非壞，喚醒即可（不改檔）"}


def write_heal_review(name, result):
    """修不好 → 寫 _heal_review 診斷卡（JSON、非 atom 格式）+ 審計 append _merge_history.log。"""
    review_dir = MEMORY / "_heal_review"
    review_dir.mkdir(parents=True, exist_ok=True)
    card = {"atom": name, "created_at": datetime.now().isoformat(), **result}
    (review_dir / f"{name}.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        with open(MEMORY / "_merge_history.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()}\theal_failed\t{name}\tglobal\t{HEAL_SOURCE}\t{result.get('action', '')}\n")
    except Exception:
        pass
    return str(review_dir / f"{name}.json")


def main():
    ap = argparse.ArgumentParser(description="記憶自癒：分級修復單一 atom")
    ap.add_argument("--atom", required=True, help="要修復的 atom 名")
    ap.add_argument("--apply", action="store_true", help="實際套用修復（預設 dry-run 只診斷）")
    ap.add_argument("--auto", action="store_true", help="自主模式：只跑免費 L1/L3，L2 改回報 needs_manual（不呼 LLM、不改內容）")
    ap.add_argument("--backend", default="ollama", choices=["ollama", "cloud", "none"],
                    help="L2 判斷後端（預設本地 ollama 免費；cloud 選配；none 全交人工）")
    ap.add_argument("--json", action="store_true", help="JSON 輸出")
    a = ap.parse_args()

    atoms = ahc.find_atoms(ahc.MEMORY_ROOT)
    aliases = ahc.parse_memory_index(ahc.MEMORY_ROOT)
    report = scan(a.atom, atoms, aliases)

    if not report.get("exists"):
        out = {"atom": a.atom, "level": "missing", "action": "none",
               "fixed": False, "needs_human": True, "reason": "找不到此 atom"}
    else:
        level, fmt_err = classify(report)
        if level == "L1":
            out = heal_L1(a.atom, report, atoms, aliases, a.apply)
        elif level == "L2" and a.auto:
            out = {"level": "L2", "action": "needs_manual", "fixed": False, "needs_human": False,
                   "note": "L2（死連結/格式）需手動觸發；自主只跑免費 L1", "broken_refs": report.get("broken_refs")}
        elif level == "L2":
            out = heal_L2(a.atom, report, atoms, aliases, a.apply, a.backend)
        elif level == "L3":
            out = heal_L3(a.atom, report)
        else:
            out = {"level": "noop", "action": "none", "fixed": True,
                   "needs_human": False, "note": "此 atom 目前健康，無需修復"}
        out["atom"] = a.atom
        out["backend"] = a.backend
        # 修不好（驗證不過）→ 寫 _heal_review 退人工審查（僅 L1/L2 實修失敗）
        if a.apply and out.get("needs_human") and out.get("level") in ("L1", "L2"):
            out["heal_review_card"] = write_heal_review(a.atom, out)

    out["health_before"] = {
        "broken": len(report.get("broken_refs") or []),
        "reverse": len(report.get("missing_reverse_refs") or []),
        "stale": len(report.get("stale_atoms") or []),
    }
    print(json.dumps(out, ensure_ascii=False, **({} if a.json else {"indent": 2})))


if __name__ == "__main__":
    main()
