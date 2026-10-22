"""goal_inject_replay.py — 同一串事件分別跑某棵樹的 hook 程式，數注入裡「目標樹本身」與「目標改了才有」的 token（改前改後比）。

做什麼
  事件組成與樹的文字照 2026-10-22-B6on-1 那一跑（導讀卡附樹 8 次、使用者訊息 3 則、讀入範圍提示、need_goal set／add／update／reconcile；
  樹根與 4 個子節點是那一跑 AI 寫的原文；--big 另加 8 個子節點），再加上「加子節點後重讀兩個已碰過的部位」與「改節點文字後重讀一個部位」
  （舊碼加節點也會觸發目標視角重送）、壓縮後重送一次；另加改檔：交了定位改兩個部位 → 加子節點後再改（舊碼加節點就清定位、要重交）
  → 改節點文字後再改（兩版都清）。
  在暫存資料根與暫存專案（8 個部位、各一張導讀卡）裡，直接呼叫那棵樹的入口函式：wg_overview.on_read（導讀卡、目標視角重看）、
  wg_overview.on_edit（定位閘）、wg_need_goal_points.scope_on_read＋batch_lines（讀入範圍）、wg_need_goal.on_prompt（每則訊息）、
  recovery_text（壓縮重送）、post_tool_use._need_goal_after_tool（need_goal 呼叫與回覆，含目標改了清定位）。
  「目標樹本身」＝wg_need_goal 的 render／_header／brief 產出的文字（包一層記號後從注入裡切出來、只算最外層）；
  「目標改了才有的其餘」＝目標視角重送的整段、清掉定位後的重擋訊息，扣掉裡面的目標樹文字。
  token 用那棵樹的 wg_core._estimate_tokens（系統自己的口徑，中文約 1.5 token／字）。
  三個數：hook 主動附的目標樹（need_goal 以外的提示）、目標改了才有的其餘注入、need_goal 寫入的回覆（照設計整棵樹回一次）。

怎麼跑
  python -X utf8 goal_inject_replay.py --tree <某棵樹的根，例：工作樹或 git archive 解出來的舊版> [--big] [--json]
  尾行 GOAL_INJECT_REPLAY DONE hook_tok=<n> chain_tok=<n> reply_tok=<n> hook_events=<n>
"""
import argparse
import json
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--tree", required=True)
ap.add_argument("--json", action="store_true")
ap.add_argument("--big", action="store_true")
a = ap.parse_args()
TREE = Path(a.tree).resolve()

BASE = Path(tempfile.mkdtemp(prefix="goal-replay-"))
DATA, PROJ = BASE / "data", BASE / "proj"
(DATA / "workflow").mkdir(parents=True)
(DATA / "workflow" / "config.json").write_text("{}", encoding="utf-8")
os.environ["WG_CLAUDE_DIR"] = str(DATA)
os.environ["WG_TEMP_RULES"] = "off"
sys.path[:0] = [str(TREE / "hooks"), str(TREE / "lib")]

import wg_core  # noqa: E402
wg_core.append_guard_log = lambda *a, **k: None
import wg_need_goal as ng  # noqa: E402
import wg_need_goal_points as ngp  # noqa: E402
import wg_overview as wo  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402

wo.org_memory_root = lambda: None
wo._ORG_ROOT_CACHE = []
wo.LOG_PATH = BASE / "hub.log"

# ─── 假專案：8 個寫碼部位、各一張導讀卡 ───────────────────────────────────
PARTS = ["戰鬥", "介面", "存檔", "網路", "設定", "音效", "動畫", "工具"]
(PROJ / ".git").mkdir(parents=True)
mem = PROJ / ".claude" / "memory" / "shared"
mem.mkdir(parents=True)
rows = "".join(f"| `src\\P{i}\\` | {p} | `{p}導讀` | 有 | code |\n" for i, p in enumerate(PARTS))
(PROJ / ".claude" / "overview-map.md").write_text(
    "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n" + rows, encoding="utf-8")
FILES = []
for i, p in enumerate(PARTS):
    (mem / f"{p}導讀.md").write_text(f"# {p}導讀\n\n## 知識\n\n- [臨] **已知病灶**：{p}的共用狀態兩邊寫\n", encoding="utf-8")
    d = PROJ / "src" / f"P{i}"
    d.mkdir(parents=True)
    (d / "a.py").write_text("x = 1\n", encoding="utf-8")
    FILES.append(str(d / "a.py"))
TP = BASE / "t.jsonl"
TP.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "先看"}]}}) + "\n",
              encoding="utf-8")

# ─── 記號：切出目標樹本身的文字 ───────────────────────────────────────────
OPEN, CLOSE = "\x02", "\x03"
for name in ("render", "_header", "brief"):
    f = getattr(ng, name, None)
    if f is None:
        continue
    setattr(ng, name, (lambda fn: (lambda *x, **k: (lambda s: f"{OPEN}{s}{CLOSE}" if s else s)(fn(*x, **k))))(f))


def tree_text(text):
    out, depth, cur = [], 0, []
    for ch in text or "":
        if ch == OPEN:
            depth += 1
            continue
        if ch == CLOSE:
            depth -= 1
            if depth == 0:
                out.append("".join(cur))
                cur = []
            continue
        if depth > 0:
            cur.append(ch)
    return "\n".join(out)


TOK = defaultdict(int)
N = defaultdict(int)
EXTRA = defaultdict(int)   # 目標改了才有的整段（目標視角重送的卡、清掉定位後的重擋）：樹文字以外的部分


def record(kind, text):
    if not text:
        return
    TOK[kind] += wg_core._estimate_tokens(tree_text(text))
    N[kind] += 1


def extra(kind, text):
    whole = wg_core._estimate_tokens(text.replace(OPEN, "").replace(CLOSE, ""))
    EXTRA[kind] += whole - wg_core._estimate_tokens(tree_text(text))


SID = "replay-0001"
state = {"turn_seq": 1, "session": {"id": SID, "cwd": str(PROJ)}, "need_goal_code_decl_turn": 1}
CFG = {}


def need_goal(tool_input):
    text, _ = pt._need_goal_after_tool(state, SID, "mcp__workflow-guardian__need_goal", tool_input,
                                       {"tool_response": {}, "transcript_path": str(TP), "cwd": str(PROJ)}, CFG)
    record("need_goal 回覆", text)


def read(i, kind="導讀卡附樹"):
    out = wo.on_read(state, SID, "Read", {"file_path": FILES[i]}, str(PROJ), str(TP), CFG)
    if out and "目標視角" in out:
        kind = "目標視角重看"
        extra(kind, out)
    record(kind, out)
    ngp.scope_on_read(state, SID, "Read", {"file_path": FILES[i]}, str(PROJ), CFG)


def batch():
    for line in ngp.batch_lines(SID, state, [], ng.cfg_of(CFG)):
        record("讀入範圍等批次提醒", line)


def say(*idx):
    with open(TP, "a", encoding="utf-8") as fh:
        for i in idx:
            p = PARTS[i]
            lines = (f"定位｜部位：{p}：a.py\n定位｜根因層：候選 A 邏輯層；候選 B 存檔時序；選 A 因為狀態只在邏輯層被寫\n"
                     f"定位｜前例：{p}導讀\n定位｜目標：T1.1（列出產品數量金額）\n"
                     "定位｜批判：不合理，因為狀態兩邊都寫，更好的做法是只留一個寫入點；同類還可能在哪：存檔流程也兩邊寫")
            fh.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": lines}]}},
                                ensure_ascii=False) + "\n")


def edit(i, after_goal_change):
    _warn, deny, _ = wo.on_edit(state, SID, FILES[i], str(TP), CFG)
    if deny and after_goal_change:
        N["目標改了引起的重擋"] += 1
        extra("目標改了引起的重擋", deny)
    elif deny:
        print(f"[replay] 前置失敗：{PARTS[i]} 交了定位還被擋：{deny[:200]}", file=sys.stderr)
    return deny


def prompt(text):
    state["turn_seq"] += 1
    state["need_goal_code_decl_turn"] = state["turn_seq"]
    record("每則訊息", ng.on_prompt(SID, text, state["turn_seq"], CFG, str(PROJ)))


# ─── 事件（樹的文字照 B6on-1 的 AI 原文；--big 另加 8 個子節點，看大一點的樹） ───────────────────
record("每則訊息", ng.on_prompt(SID, "sales cli 加一個 by-product 指令：指定月份，列出那個月每個產品的數量和金額（金額兩位小數）。"
                                     "現有的 monthly 輸出財務那邊在用，不要動到它。要有測試。", 1, CFG, str(PROJ)))
need_goal({"action": "set", "kind": "code",
           "goal": "sales cli 能用 by-product 指定月份，列出那個月每個產品的數量和金額（兩位小數），monthly 輸出完全不變，並有測試保護"})
need_goal({"action": "add", "items": [
    {"text": "by-product 指定月份列出每個產品的數量和金額（金額兩位小數）", "origin": "user", "quote": "列出那個月每個產品的數量和金額（金額兩位小數）"},
    {"text": "monthly 輸出不變", "origin": "user", "quote": "現有的 monthly 輸出財務那邊在用，不要動到它。"},
    {"text": "有測試", "origin": "user", "quote": "要有測試。"},
    {"text": "by-product 的月份歸屬符合 README 台北時間規則", "origin": "inferred"}]
    + ([{"text": f"第 {i} 個延伸子目標：壞參數與邊界月份都要有明確錯誤訊息與測試"} for i in range(8)] if a.big else [])})
for i in range(8):
    read(i)
    if i == 3:
        batch()
batch()
say(0, 1)
edit(0, False)
edit(1, False)
prompt("另外命令列也要能覆蓋")
need_goal({"action": "add", "items": [{"text": "命令列參數優先於設定"}]})
read(0)
read(1)
batch()
for i in (0, 1):                      # 加了子節點之後再改已定位的部位
    if edit(i, True):
        say(i)
        edit(i, False)
need_goal({"action": "update", "items": [{"id": "T1.4", "text": "by-product 的月份歸屬照 README 的台北時間切月"},
                                         {"id": "T1.1", "status": "done", "why": "真 CLI 印出三行且金額兩位小數"}]})
read(0)
if edit(0, True):                     # 改了節點文字之後（兩版都要重交）
    say(0)
    edit(0, False)
prompt("好，繼續")
record("壓縮後重送", ngp.recovery_text(SID, CFG, str(PROJ)))
need_goal({"action": "reconcile", "items": [{"id": n, "status": "partial", "followup": "等驗證"}
                                            for n in ng.active_tree(ng.load(SID))["nodes"]]})

hook_tok = sum(v for k, v in TOK.items() if k != "need_goal 回覆")
hook_n = sum(v for k, v in N.items() if k != "need_goal 回覆")
chain_tok = sum(EXTRA.values())
rows = [{"項目": k, "次數": N[k], "目標樹 token": TOK[k], "目標改了才有的其餘 token": EXTRA[k]}
        for k in sorted(N, key=lambda k: -(TOK[k] + EXTRA[k]))]
if a.json:
    print(json.dumps({"tree": str(TREE), "rows": rows, "hook_tok": hook_tok, "chain_tok": chain_tok,
                      "reply_tok": TOK["need_goal 回覆"]}, ensure_ascii=False, indent=1))
else:
    print(f"樹：{TREE}")
    print("| 項目 | 次數 | 目標樹 token | 目標改了才有的其餘 token |\n|---|---|---|---|")
    for r in rows:
        print(f"| {r['項目']} | {r['次數']} | {r['目標樹 token']} | {r['目標改了才有的其餘 token']} |")
print(f"GOAL_INJECT_REPLAY DONE hook_tok={hook_tok} chain_tok={chain_tok} reply_tok={TOK['need_goal 回覆']} hook_events={hook_n}")
