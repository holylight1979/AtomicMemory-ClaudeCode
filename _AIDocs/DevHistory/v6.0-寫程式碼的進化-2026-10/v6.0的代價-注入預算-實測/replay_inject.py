"""replay_inject.py — 用 004 事件帳重播 UserPromptSubmit 記憶卡段：同一批候選（state injection_log 的名字與來源、
atom_index 的路徑）交給指定版本的 ups_inject.assemble_injection 組裝，輸出每回合的 [Atom:] 區塊。

怎麼跑：python -X utf8 replay_inject.py --code <hooks 所在的 repo 根> --out <json> [--runs R1,R2,…]
- 候選的 hot／cold 照當時：非 trigger 的卡存取紀錄填空（transcript 證實當時三張都是 cold），trigger 本來就 hot。
- WG_CLAUDE_DIR 指到受測專案資料根 C:/w4/qb2-sales-root（同當時），WG_V6=1；只呼叫組裝，不結算、不記曝光、不寫 log。
"""
import argparse
import json
import os
import sys
from pathlib import Path

RES = Path(r"C:\Users\holylight\.claude\workflow\inbox\wave2-kit\results")
ROOT = Path("C:/w4/qb2-sales-root")
RUNS = "2026-10-23-CCon-R1,2026-10-23-CCon-R2,2026-10-23-CCon-1,2026-10-23-CCon-2,2026-10-23-CCon-3"

ap = argparse.ArgumentParser()
ap.add_argument("--code", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--runs", default=RUNS)
a = ap.parse_args()

os.environ["WG_CLAUDE_DIR"] = str(ROOT)
os.environ["WG_V6"] = "1"
code = Path(a.code)
for p in (code / "hooks", code, code / "lib"):
    sys.path.insert(0, str(p))
from handlers import ups_inject  # noqa: E402
from wg_atoms import classify_intent  # noqa: E402

cfg = json.loads((code / "workflow" / "config.json").read_text(encoding="utf-8"))
cfg["atom_debug"] = False
out = {}
for run in a.runs.split(","):
    seg = RES / run / "B-1"
    st = json.loads(next((seg / "workflow").glob("state-*.json")).read_text(encoding="utf-8"))
    idx = {e[0]: e for e in st["atom_index"]["global"]}
    all_atoms = [((e[0], e[1], e[2]), ROOT) for e in st["atom_index"]["global"]]
    res = {}
    for t in (1, 2):
        prompt = json.loads((seg / "turns" / f"B-1-t{t}.json").read_text(encoding="utf-8"))["_meta"]["prompt"]
        recs = [r for r in st["injection_log"] if r["turn_seq"] == t and r["source"] != "related"]
        matched = [((idx[r["name"]][0], idx[r["name"]][1], idx[r["name"]][2]), ROOT) for r in recs]
        src = {r["name"]: r["source"] for r in recs}
        access = {str(ROOT / idx[r["name"]][1]): {} for r in st["injection_log"]}   # 當時非 trigger 全是 cold
        for e in st["atom_index"]["global"]:
            access.setdefault(str(ROOT / e[1]), {})
        state = {"turn_seq": t - 1, "turn_intent": classify_intent(prompt), "atom_index": {"scopes": {}}, "injected_atoms": []}
        lines = []
        ups_inject.assemble_injection("replay", state, cfg, matched, all_atoms, [], src, {}, lines,
                                      caches={"content": {}, "access": access}, prompt=prompt)
        res[f"t{t}"] = {"intent": state["turn_intent"], "blocks": lines,
                        "forms": [(r["name"], r["source"], r["form"]) for r in state.get("injection_log", [])]}
    out[run] = res
Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"REPLAY_INJECT DONE runs={len(out)} code={code.name}")
