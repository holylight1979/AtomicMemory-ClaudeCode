"""so_offline_replay.py — 第 0 步補題第 4 回合第二意見閘為什麼沒判：拿收來的 state 與 transcript，離線呼叫 live 同版的
writing_code／claims_completion／turn_claims_completion，看程式檔數與「宣告完成」認不認得到。不跑模型、不寫資料根。
怎麼跑：在放了 so_replay/workflow（S-1/workflow 複本）的目錄下 python -X utf8 so_offline_replay.py
"""
import json, glob, os, sys
W = r"C:/Users/holylight/.claude-wt/measure-005"
os.environ.update(WG_CLAUDE_DIR=os.path.abspath("so_replay/root"), WG_TEST_LOGS_DIR=os.path.abspath("so_replay/root/Logs"), WG_V6="1")
os.makedirs("so_replay/root/Logs", exist_ok=True)
sys.path[:0] = [W + "/hooks", W + "/lib"]
R = r"C:/Users/holylight/.claude/workflow/inbox/wave2-kit/results/2026-10-27-005-GATE0-SUP/S-1/"
st = json.load(open(glob.glob("so_replay/workflow/state-*.json")[0], encoding="utf-8"))
sid = "43bb6165-e8d4-488b-b393-016028aee904"
mods = [m for m in st["modified_files"] if m.get("session_id") == sid]
print("mods", [(m["path"], m.get("turn_seq"), m.get("last_turn_seq")) for m in mods])
from wg_need_goal import writes_code
cfg_all = json.load(open(W + "/workflow/config.json", encoding="utf-8"))
print("code?", [(m["path"], writes_code(m["path"], cfg_all)) for m in mods])
tx = glob.glob(R + "transcript/*.jsonl")[0]
last = ""
for l in open(tx, encoding="utf-8"):
    r = json.loads(l)
    if r.get("type") == "assistant":
        for c in (r.get("message") or {}).get("content") or []:
            if c.get("type") == "text": last = c["text"]
from wg_evasion import claims_completion
print("claims_completion(last)", claims_completion(last))
import wg_second_opinion as so
print("turn_claims", so.turn_claims_completion(open(tx, encoding="utf-8").read()))
print("LAST TEXT head:", last[:200].replace("\n"," | "))
txt = open(tx, encoding="utf-8").read()
import wg_second_opinion as so
print("turn_completion_text", (so.turn_completion_text(txt) or "")[:200] if hasattr(so, "turn_completion_text") else "na")
