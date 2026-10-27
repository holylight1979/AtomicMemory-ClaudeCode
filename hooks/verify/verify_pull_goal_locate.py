"""verify_pull_goal_locate.py：目標樹與定位不再「修了又欠」——加子節點不清定位、子代理與程式記錄不動主樹的提示、
定位閘同缺件擋次有上限、目標對照閘預設關、hook 提示只附樹根與當前節點、審查材料不印空段、案例寫入不落正式資料根。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_pull_goal_locate.py
  （直接跑 python -X utf8 hooks/verify/verify_pull_goal_locate.py 也行：開子行程跑 pytest，尾行印哨兵）
每一案改前紅、改後綠；共用 verify_need_goal 的資料根隔離（env／hooked）與部位世界。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

VERIFY = Path(__file__).resolve().parent
sys.path.insert(0, str(VERIFY))

from verify_need_goal import (  # noqa: E402,F401
    CRIT, ON, SID, THREE, THREE2, _code_tree, _deny_text, _mapped_world, _op, _ptu_run, _read_part, _say, _tree,
    _two_part_world, env, hooked, ng, pt, ptu, wg_core, wo,
)
import wg_need_goal_points as ngp  # noqa: E402
from handlers import post_tool_batch as ptb  # noqa: E402

NG_TOOL = "mcp__workflow-guardian__need_goal"


def _state():
    return json.loads(wg_core.state_file_path(SID).read_text(encoding="utf-8"))


def _ng_call(state, tool_input, tp, cwd=""):
    pt._need_goal_after_tool(state, SID, NG_TOOL, tool_input, {"tool_response": {}, "transcript_path": tp, "cwd": cwd}, {})


def _hub_events(env):
    p = env["tmp"] / "hub.log"
    return [json.loads(l).get("event") for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


# ─── 加子節點不算目標改（盤查第 4 列） ────────────────────────────────────────

def test_add_child_keeps_located_only_root_rewrite_and_node_text_clear(hooked):
    """need_goal add 子節點、update 只改清楚度或狀態 → 已交定位的部位不清；set 改寫樹根、update 改節點文字 → 清。舊碼 add 就清。"""
    tp = hooked["tp"]
    _op("set", goal="戰鬥不卡", items=[{"text": "共用字典只留一個寫入點"}])
    state = {"turn_seq": 3, "overview_hub": {"p|戰鬥": {"located": True, "goal_tree": "T1", "goal_node": "T1.1"}}}
    rec = state["overview_hub"]["p|戰鬥"]
    for call in ({"action": "add", "items": [{"text": "介面跟著刷新"}]},
                 {"action": "update", "items": [{"id": "T1.2", "clarity": "open"}]},
                 {"action": "update", "items": [{"id": "T1.1", "status": "doing"}]},
                 {"action": "set", "goal": "戰鬥不卡"}):                      # 樹根沒變
        _ng_call(state, call, tp)
        assert rec["located"] is True and rec.get("goal_node") == "T1.1", call
    assert _tree()["goal_rev"] == 1                                           # 目標版本沒動
    _ng_call(state, {"action": "update", "items": [{"id": "T1.1", "text": "共用字典改成唯讀"}]}, tp)
    assert rec["located"] is False and "goal_node" not in rec                # 改節點文字＝目標改了
    rec["located"] = True
    _ng_call(state, {"action": "set", "goal": "戰鬥與介面都不卡"}, tp)
    assert rec["located"] is False                                            # 改寫樹根＝目標改了


def test_flow_scope_prompt_then_add_does_not_reblock_edit(hooked):
    """流程級：交了定位能改 → 讀到第二個部位，提示問「要不要長子目標」→ AI 照做 add → 下一個 Edit 不被定位閘擋。
    舊碼 add 清掉所有定位、下一個 Edit 要重讀重交（讀入範圍再變大又被問，繞成環）。"""
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    files = _two_part_world(hooked)
    f1 = files["Battle"]
    _op("set", goal="戰鬥不卡", cwd=str(proj), items=[{"text": "共用字典不再被兩邊改"}])
    _ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)                    # 第一次碰部位：注入導讀卡
    _read_part(f1, proj, tp)
    _say(tp, THREE2 + "\n定位｜目標：T1.1（共用字典的唯一寫入點）" + CRIT)
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)) is None
    state = _state()
    for f in (f1, files["UI"]):
        ngp.scope_on_read(state, SID, "Read", {"file_path": f}, str(proj), {})
    lines = ngp.batch_lines(SID, state, [], ng.cfg_of({}))
    assert lines and "目標樹要長新的子目標嗎" in lines[0]                      # 前置：提示真的叫 AI 加節點
    _ng_call(state, {"action": "add", "items": [{"text": "介面跟著刷新"}]}, tp, str(proj))
    wg_core.write_state(SID, state)
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)) is None


# ─── 子代理與程式記錄不觸發主樹提示（續掃新列） ───────────────────────────────

def _post(monkeypatch, state, tool_input, cwd, tp, agent_id=""):
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_run_companion_hooks", lambda *a: ([], []))
    inp = {"session_id": SID, "hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": tool_input,
           "tool_response": {}, "cwd": cwd, "transcript_path": tp, **({"agent_id": agent_id} if agent_id else {})}
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}})


def _batch(monkeypatch, state, agent_id="", capsys=None):
    monkeypatch.setattr(ptb, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(ptb, "write_state", lambda *a, **k: None)
    capsys.readouterr()
    try:
        ptb.handle_post_tool_batch({"session_id": SID, "tool_calls": [], **({"agent_id": agent_id} if agent_id else {})}, {})
    except SystemExit:
        pass
    out = capsys.readouterr().out.strip()
    return ((json.loads(out) if out else {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""


def test_subagent_read_leaves_main_scope_and_gets_no_tree_prompts(hooked, monkeypatch, capsys):
    """子代理讀新部位：主 session 的讀入範圍不變、不排「要不要長子目標」、子代理那一批不送主樹的提醒、目標視角重看不送也不吃掉
    主 session 那一次；主 session 自己讀照常。舊碼子代理讀檔照算進主樹。"""
    proj, tp = hooked["proj"], hooked["tp"]
    files = _two_part_world(hooked)
    _op("set", goal="戰鬥不卡", kind="code", cwd=str(proj), items=[{"text": "共用字典不再被兩邊改"}])
    state = {"turn_seq": 2, "need_goal_code_decl_turn": 2, "session": {"id": SID, "cwd": str(proj)}}
    _post(monkeypatch, state, {"file_path": files["Battle"]}, str(proj), tp)                 # 主 session：第一個部位
    parts = list((_tree().get("points") or {}).get("scope_parts") or [])
    assert len(parts) == 1
    _post(monkeypatch, state, {"file_path": files["UI"]}, str(proj), tp, agent_id="ag1")      # 子代理：第二個部位
    assert (_tree().get("points") or {}).get("scope_parts") == parts and not state.get("need_goal_batch")
    ngp.scope_growth_line(SID, "x|另一塊", ng.cfg_of({}))                                     # 主 session 排著一則待送
    state["need_goal_batch"] = True
    assert "讀入範圍變大" not in _batch(monkeypatch, state, "ag1", capsys)                   # 子代理那批不送
    assert "讀入範圍變大" in _batch(monkeypatch, state, "", capsys)                          # 主 session 那批照送
    rec = next(v for k, v in state["overview_hub"].items() if k.endswith("|戰鬥"))
    rec["goal_reset_turn"] = 2
    assert wo.on_read(state, SID, "Read", {"file_path": files["Battle"]}, str(proj), tp, {}, agent_id="ag1") is None
    assert rec.get("goal_view_turn") is None                                                  # 沒吃掉主 session 的那一次
    view = wo.on_read(state, SID, "Read", {"file_path": files["Battle"]}, str(proj), tp, {})
    assert view and "目標視角" in view


def test_program_progress_does_not_reset_cross_dir_count(env):
    """程式自己記的進度（history by=program）不算樹更新：跨 3 個頂層目錄的計數不歸零。舊碼一記進度就從 0 重數。"""
    proj = env["proj"]
    _op("set", goal="G", kind="code")
    cfg = ng.cfg_of({})
    assert ngp.scope_dir_line(SID, "c:/p|a", cfg) is None
    assert ngp.scope_dir_line(SID, "c:/p|b", cfg) is None
    ng.stamp_edit(SID, str(proj / "a.py"), "", 2, {})
    assert ng.auto_progress(SID, 2)                                           # 前置：程式真的記了一筆進度
    line = ngp.scope_dir_line(SID, "c:/p|c", cfg)
    assert line and "跨了 3 個頂層目錄" in line


# ─── 定位閘同缺件擋次上限（盤查第 5 列） ──────────────────────────────────────

def test_locate_gate_same_gap_blocks_twice_then_passes_with_log(hooked):
    """同回合同部位同缺件：擋第 1、2 次，第 3 次放行並留帳（edit_deny_capped）；換回合重給 2 次。舊碼第 3 次照擋。"""
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    f1 = _mapped_world(hooked)
    _op("set", goal="戰鬥不卡", items=[{"text": "共用字典不再被兩邊改"}])
    _ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)                    # 注入導讀卡（不算進缺件次數）
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    out = _ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)
    assert _deny_text(out) is None and "放行並留帳" in json.dumps(out, ensure_ascii=False)
    assert "edit_deny_capped" in _hub_events(hooked)
    state = _state()
    state["turn_seq"] = int(state.get("turn_seq", 0) or 0) + 1                # 下一個使用者回合
    wg_core.write_state(SID, state)
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))


def test_locate_deny_asks_exactly_the_lines_the_gate_checks(hooked):
    """擋訊息要的行＝閘判交齊的條件：有目標樹時擋訊息要「一次交齊四行」（部位、根因層兩候選＋理由、前例、批判），範例照填
    （角括號換成自己的判斷）交上去 → 一次放行、不再擋第二輪。擋訊息沒要的第四行目標節點，閘也只記錄（locate_soft、掛樹根）。
    擋訊息少要一行、或閘多擋一行，這案就紅。"""
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    f1 = _mapped_world(hooked)
    _op("set", goal="戰鬥不卡", items=[{"text": "共用字典不再被兩邊改"}])
    _ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)                    # 注入導讀卡
    _read_part(f1, proj, tp)
    deny = _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert deny and "一次交齊四行" in deny
    example = [ln.strip() for ln in deny.splitlines() if ln.strip().startswith("定位｜")]
    assert [ln.split("：", 1)[0] for ln in example] == ["定位｜部位", "定位｜根因層", "定位｜前例", "定位｜批判"]
    text = "\n".join(example)
    for k, v in (("<這次改哪個檔、哪一段>", "A.cs 的暴擊分支"), ("<第一個根因>", "邏輯層寫字典"), ("<第二個根因>", "存檔時序"),
                 ("<為什麼不是 B>", "存檔只讀字典"), ("<卡名>／無", "共用字典"), ("<現在寫法的問題>", "字典兩邊都寫"),
                 ("<替代做法>", "只留邏輯層一個寫入點"), ("<別處同樣寫法的位置>", "存檔流程")):
        text = text.replace(k, v)
    assert "<" not in text, text
    _say(tp, text)
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)) is None
    soft = [p for g, p in hooked["guard"] if g == "need_goal" and p.get("event") == "locate_soft"]
    assert soft and "LOCATE_GOAL_NODE" in soft[-1]["rules"]


def _reply(tp, mid, *tids):
    """AI 的一則回覆 mid 整則落進 transcript（含它送出的 tool_use）：之後的呼叫屬下一則（批次鍵＝這則的 message.id）。"""
    blocks = [{"type": "tool_use", "id": t, "name": "Edit", "input": {}} for t in tids] or [{"type": "text", "text": "…"}]
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"id": mid, "content": blocks}}, ensure_ascii=False) + "\n")


def _edit_call(f, proj, tp, outputs, tid):
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": "Edit", "tool_input": {"file_path": f, "old_string": "x", "new_string": "y"},
                                 "session_id": SID, "cwd": str(proj), "transcript_path": tp, "tool_use_id": tid}, {})
    return outputs[-1]


def test_two_candidates_ask_once_counts_one_reply(hooked):
    """規則 DENY_CAP_PER_REPLY（同類：TWO_CANDIDATES_ASK_ONCE，上限 1 則回覆）：定位行根因層只寫一個候選、同一則回覆平行送出
    3 個改同部位的 Edit → 3 個都擋（是同一次問）；舊碼照呼叫記「這回合問過了」，第 2 個起只記錄、放行。下一則同樣的定位行 → 只記錄、放行。"""
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    f1 = _mapped_world(hooked)
    files = [f1] + [str(Path(f1).with_name(n)) for n in ("B.cs", "C.cs")]
    for f in files[1:]:
        Path(f).write_text("x", encoding="utf-8")
    _op("set", goal="戰鬥不卡")
    _op("add", items=[{"text": "共用字典不再被兩邊改"}])
    _ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)                  # 注入導讀卡
    _read_part(f1, proj, tp)
    _say(tp, THREE + "\n定位｜目標：T1.1（共用字典的唯一寫入點）" + CRIT)    # 根因層只一個候選
    _reply(tp, "msg_1")
    denies = [_deny_text(_edit_call(f, proj, tp, outputs, f"tu_{i}")) for i, f in enumerate(files)]
    assert all(d and "LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES" in d for d in denies), denies
    _reply(tp, "msg_2", "tu_0", "tu_1", "tu_2")
    assert _deny_text(_edit_call(files[1], proj, tp, outputs, "tu_3")) is None      # 下一則：這回合問過了，只記錄


def _bare(base):
    """沒有部位表的專案：有 .git、src 底下兩支既有程式檔。"""
    root = base / "bare"
    (root / ".git").mkdir(parents=True)
    for rel in ("src/a.py", "src/b.py"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x\n", encoding="utf-8")
    return root


MIN_MAP_OFF = {"overview_hub": {"min_map": {"enabled": False, "preview_timeout_s": 2}}}
MIN_MAP_ON = {"overview_hub": {"min_map": {"enabled": True, "preview_timeout_s": 5}}}


def test_unmapped_gate_same_gap_blocks_twice_then_passes_with_log(env):
    """沒在部位表上的改檔閘（讀檔數、最小地圖三行）：同回合同目錄同缺件擋 2 次、第 3 次放行並留帳（edit_unmapped_capped）；
    換回合重給。舊碼第 3 次照擋（地圖三行交了閘卻看不到時一直擋）。"""
    root = _bare(env["tmp"])
    f = str(root / "src" / "a.py")
    state = {"turn_seq": 3}
    assert wo.on_edit(state, "s", f, "", MIN_MAP_OFF)[1]
    assert wo.on_edit(state, "s", f, "", MIN_MAP_OFF)[1]
    warn, deny, changed = wo.on_edit(state, "s", f, "", MIN_MAP_OFF)
    assert deny is None and changed and "放行並留帳" in warn
    assert "edit_unmapped_capped" in _hub_events(env)
    state["turn_seq"] = 4
    assert wo.on_edit(state, "s", f, "", MIN_MAP_OFF)[1]


def test_unreadable_transcript_is_gate_self_error_not_a_block(env, monkeypatch):
    """讀不到 transcript＝閘驗不了 AI 交的那幾行（定位行、最小地圖三行）＝閘自己判不了（規則 GATE_SELF_ERROR）：放行、
    stderr＋守門紀錄 error、不計擋次、地圖不記成交過。舊碼「環境異常一律擋」（第 3 次也擋，因為不計上限）。"""
    guard = []
    monkeypatch.setattr(wo, "append_guard_log", lambda g, p: guard.append(p), raising=False)
    root = _bare(env["tmp"])
    state = {"turn_seq": 3}
    wo.on_read(state, "s", "Read", {"file_path": str(root / "src" / "b.py")}, str(root), "", {})   # 讀檔數夠了，只欠地圖
    for _ in range(3):
        assert wo.on_edit(state, "s", str(root / "src" / "a.py"), "", MIN_MAP_ON)[1] is None
    assert [p["rule"] for p in guard] == ["GATE_SELF_ERROR"] * 3 and "decl_deny_counts" not in state
    assert not any(r.get("min_map_done") for r in state["overview_hub"].values())
    f1 = _mapped_world(env)                                                    # 有部位表：定位行也一樣
    _op("set", goal="戰鬥不卡", items=[{"text": "共用字典不再被兩邊改"}])
    hub_state = {"turn_seq": 3}
    for _ in range(2):                                                         # 第一次注入導讀卡、第二次才算讀過部位檔
        wo.on_read(hub_state, SID, "Read", {"file_path": f1}, str(env["proj"]), "", {})
    for _ in range(3):
        assert wo.on_edit(hub_state, SID, f1, "", {})[1] is None
    assert guard[-1]["check"] == "定位行" and "decl_deny_counts" not in hub_state


def test_unreadable_transcript_still_checks_part_file_reads(env, monkeypatch):
    """讀不到 transcript 只免掉驗不了的定位行；「讀過部位檔」不靠 transcript，照查照擋。"""
    monkeypatch.setattr(wo, "append_guard_log", lambda g, p: None, raising=False)
    f1 = _mapped_world(env)
    _op("set", goal="戰鬥不卡", items=[{"text": "共用字典不再被兩邊改"}])
    hub_state = {"turn_seq": 3}
    assert wo.on_edit(hub_state, SID, f1, "", {})[1]                         # 第一次碰部位：注入導讀卡（擋）
    deny = wo.on_edit(hub_state, SID, f1, "", {})[1]
    assert deny and "還沒讀過這個部位的檔" in deny and "還沒交出定位" not in deny


def test_unmapped_cap_release_keeps_a_passed_min_map(env):
    """沒在部位表上的改檔閘擋滿放行時，這次真的通過的最小地圖照記成交過（不因放行走捷徑而漏存）；擋滿放行本身不算交地圖。"""
    root = _bare(env["tmp"])
    (root / "lib").mkdir()
    (root / "lib" / "c.py").write_text("x\n", encoding="utf-8")
    tp = env["tmp"] / "map.jsonl"
    tp.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text":
                  "地圖｜讀了：lib/c.py（設定）\n地圖｜上游：無，因為是入口腳本\n地圖｜下游：lib/c.py"}]}},
                             ensure_ascii=False) + "\n", encoding="utf-8")
    state = {"turn_seq": 3}
    wo.on_read(state, "s", "Read", {"file_path": str(root / "lib" / "c.py")}, str(root), str(tp), {})   # src 一個都沒讀
    f = str(root / "src" / "a.py")
    assert wo.on_edit(state, "s", f, str(tp), MIN_MAP_ON)[1] and wo.on_edit(state, "s", f, str(tp), MIN_MAP_ON)[1]
    warn, deny, _ = wo.on_edit(state, "s", f, str(tp), MIN_MAP_ON)
    assert deny is None and "放行並留帳" in warn
    rec = next(v for k, v in state["overview_hub"].items() if "(unmapped)src" in k)
    assert rec["min_map_done"] is True and rec["edits"] == 1


# ─── 目標對照閘程式預設關（盤查第 7 列） ──────────────────────────────────────

def test_goal_gate_missing_key_does_not_block(hooked, monkeypatch):
    """設定缺 reconcile_gate.goal_gate 鍵 → 收尾與 commit 前都不擋（交付邊界由程式代填對照）；明寫 true 才擋。舊碼缺鍵＝照擋。"""
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    _code_tree(hooked)
    for cfg in ({}, {"reconcile_gate": {}}):
        assert not ng.goal_gate_on(cfg)
        assert ng.commit_gate(SID, cfg) is None and ng.goal_gate_reason(SID, True, cfg) is None
    monkeypatch.setattr(ptu, "check_git_commit_order", lambda *a, **k: None)
    monkeypatch.setattr(ptu, "check_git_privacy", lambda *a, **k: None)
    assert _deny_text(_ptu_run("Bash", {"command": 'git commit -m "x"'}, proj, tp, outputs)) is None
    assert (_tree().get("last_reconcile") or {}).get("by") == "program"      # 對照照記，由程式代填
    assert "(f2)" in ng.commit_gate(SID, ON)                                  # 明寫開著照擋


# ─── 目標樹注入瘦身（24 列第 8 列） ───────────────────────────────────────────

TOKEN_CAP = 300


def _big_tree(env):
    """樹根 100 字、30 個子節點各 80 字（全中文），舊碼的精簡樹一定截、會出「其餘 N 個節點略」。"""
    _op("set", goal="讓戰鬥" * 34, kind="code", cwd=str(env["proj"]))
    r = _op("add", items=[{"text": f"第{i}條子目標" + "字典只留一個寫入點" * 8} for i in range(30)])
    ng.stamp_edit(SID, str(env["proj"] / "a.py"), "", 2, {})
    return r


def _hook_texts(config):
    """need_goal 以外的 hook 提示各一則（config＝整份設定）：導讀卡附樹、目標視角重看、讀入範圍、糾正、外部主張、每則訊息、
    壓縮後重送、交付對照。"""
    cfg = ng.cfg_of(config)
    for part in ("x|a", "x|b"):
        ngp.scope_growth_line(SID, part, cfg)
    return {
        "導讀卡附樹": wo._goal_block(SID, wo._cfg(config)),
        "目標視角重看": ngp.goal_view_text(SID, "戰鬥"),
        "讀入範圍": ngp.batch_lines(SID, {"turn_seq": 5, "need_goal_batch": True}, [], cfg)[0],
        "糾正": ngp.on_correction(SID, ["不對"], 5),
        "外部主張": ngp.on_external_claim(SID, "審查報告", "codex", 5),
        "每則訊息": ng.on_prompt(SID, "再看一下", 6, config),
        "壓縮後重送": ngp.recovery_text(SID, config),
        "交付對照": ng.goal_gate_reason(SID, True, {**ON, **config}),
    }


CRITIQUE_SENT = ("導讀卡附樹", "目標視角重看", "讀入範圍", "外部主張")       # 帶三種情況的四則（依 _hook_texts 的送出順序）


def test_hook_prompts_carry_only_current_node_line(env):
    """規則 TREE_LINE_IN_HINTS：need_goal 以外的 hook 提示附的目標樹只一行當前節點、不附樹根一行；壓縮後重送照附樹根＋當前節點
    （context 裡沒有寫入回覆送的樹了）；≤300 token、不含「其餘 N 個節點略」；need_goal add 的回覆照回整棵樹。
    舊碼（5ccf44d2）每則提示都附樹根一行＋當前節點一行（紅）；更早的碼附精簡樹、超過就印「其餘 N 個節點略」。"""
    r = _big_tree(env)
    assert all(f"T1.{i}" in r["text"] for i in range(1, 31)) and "節點略" not in r["text"]   # add 回覆：整棵樹
    texts = _hook_texts({})
    brief = ng.brief(_tree())
    assert wg_core._estimate_tokens(brief) <= TOKEN_CAP, brief
    assert brief.count("\n") == 1 and "當前節點 T1.30" in brief             # 兩行；當前節點＝最近有動靜、還沒到終點的
    root_line, node_line = brief.split("\n")
    assert ng.brief_line(_tree()) == node_line
    for name, text in texts.items():                                          # 樹根行的計數會隨記帳變，比到括號前
        assert text and node_line in text and "節點略" not in text, name
        assert (root_line.split("（")[0] in text) is (name == "壓縮後重送"), name
        if name != "交付對照":                                                # 交付對照另列缺件，不算樹
            assert sum(f"T1.{i} " in text or f"T1.{i} [" in text for i in range(1, 30)) == 0, name


def test_hook_prompts_slim_off_keep_root_line_and_full_cases(env, monkeypatch):
    """接縫：v6.slim_reminders=false 退回舊送法——每則 hook 提示照附樹根一行＋當前節點、三種情況每則全文、不記已送。"""
    _big_tree(env)
    off = {"v6": {"slim_reminders": False}}
    monkeypatch.setattr(wg_core, "load_config", lambda: off)
    assert ng.slim_reminders() is False and ng.slim_reminders({}) is True and ng.slim_reminders({"v6": {"slim_reminders": "false"}})
    texts = _hook_texts(off)
    root_line, node_line = ng.brief(_tree()).split("\n")
    for name, text in texts.items():
        assert text and root_line.split("（")[0] in text and node_line in text, name
    for name in CRITIQUE_SENT:
        assert ng.CRITIQUE_CASES in texts[name] and ng.CRITIQUE_CASES_POINTER not in texts[name], name
    assert "critique_sent" not in ng.load(SID)


def test_critique_cases_full_once_per_session_then_pointer(env):
    """規則 CRITIQUE_CASES_ONCE_PER_SESSION：三種情況（CRITIQUE_CASES）本 session 第一則送全文，之後的導讀卡附樹、目標視角重看、
    讀入範圍、外部主張只送指回句（定位第五行的格式與兩問照送）；壓縮後重送目標樹時清掉已送紀錄，下一則再送一次全文；
    還沒有目標檔時外部主張照送全文、不為記這筆建檔。舊碼（5ccf44d2）每則都送全文（紅）。"""
    assert ngp.CRITIQUE_QUESTIONS in ngp.on_external_claim(SID, "審查報告", "codex", 1)   # 沒樹：全文
    assert not ng.goal_path(SID).exists()
    _big_tree(env)
    cfg = ng.cfg_of({})
    first = wo._goal_block(SID, wo._cfg({}), None, 7)
    again = wo._goal_block(SID, wo._cfg({}), None, 8)
    for part in ("x|a", "x|b"):
        ngp.scope_growth_line(SID, part, cfg)
    later = {"讀入範圍": ngp.batch_lines(SID, {"turn_seq": 8, "need_goal_batch": True}, [], cfg)[0],
             "目標視角重看": ngp.goal_view_text(SID, "戰鬥"),
             "外部主張": ngp.on_external_claim(SID, "審查報告", "codex", 8)}
    assert wo.CRITIQUE_LINE_HINT in first                                     # 第一則：全文
    assert wo.CRITIQUE_LINE_SHORT in again and ng.CRITIQUE_CASES not in again  # 第二張導讀卡：第五行格式照送、三種情況指回
    assert "定位｜批判：" in wo.CRITIQUE_LINE_SHORT
    for name, text in later.items():
        assert ng.CRITIQUE_CASES not in text and ng.CRITIQUE_CASES_POINTER in text and ngp.CRITIQUE_TWO in text, name
    assert ng.load(SID)["critique_sent"] is True
    assert ngp.recovery_text(SID, {})                                         # 壓縮後重送目標樹：清掉已送紀錄
    assert "critique_sent" not in ng.load(SID)
    assert ng.CRITIQUE_CASES in ngp.goal_view_text(SID, "戰鬥")               # 壓縮之後的第一則：再送一次全文
    assert ng.CRITIQUE_CASES_POINTER in ngp.goal_view_text(SID, "戰鬥")


def test_card_brief_once_per_turn_unless_content_changes(env):
    """導讀卡附的兩行：同一個使用者回合內容沒變只附第一張（後面的只留定位第五行提醒）；換回合、當前節點換了或文字改了就再附。
    舊碼每張卡都附整棵精簡樹。"""
    _big_tree(env)
    cfg = wo._cfg({})
    first = wo._goal_block(SID, cfg, None, 7)
    again = wo._goal_block(SID, cfg, None, 7)
    assert "當前節點 T1.30" in first and "當前節點" not in again and "同本回合前面那則" in again
    assert "當前節點 T1.30" in wo._goal_block(SID, cfg, None, 8)              # 換回合
    _op("update", items=[{"id": "T1.30", "text": "第29條子目標改寫"}], turn=8)
    assert "第29條子目標改寫" in wo._goal_block(SID, cfg, None, 8)            # 內容變了
    ngp.scope_growth_line(SID, "x|a", ng.cfg_of({}))
    ngp.scope_growth_line(SID, "x|b", ng.cfg_of({}))
    line = ngp.batch_lines(SID, {"turn_seq": 8, "need_goal_batch": True}, [], ng.cfg_of({}))[0]
    assert "讀入範圍變大" in line and "當前節點" not in line                  # 同回合導讀卡附過了


def test_current_node_prefers_the_part_link(env):
    """有部位鍵、而且那個部位的定位掛在活著的節點 → 當前節點就是它（導讀卡、目標視角重看用）。"""
    _big_tree(env)
    ng.link_part(SID, "x|戰鬥", "T1.3", 3)
    assert "當前節點 T1.3 " in ng.brief(_tree(), "x|戰鬥")
    assert "當前節點 T1.3 " in ngp.goal_view_text(SID, "戰鬥", part_key="x|戰鬥")
    _op("update", items=[{"id": "T1.3", "status": "dropped", "why": "不做"}])
    assert "當前節點 T1.3 " not in ng.brief(_tree(), "x|戰鬥")                 # 放棄的節點不當當前


def test_added_node_after_reconcile_is_reconciled_again(env):
    """加子節點不升目標版本，但新節點還沒結論：對照不算新鮮，交付邊界程式代填會補到它（不會因版本沒變就跳過）。"""
    _code_tree(env)
    ng.auto_reconcile(SID, 3)
    assert ng.reconcile_fresh(_tree()) and not ng.auto_reconcile(SID, 3)     # 新鮮就不重填
    _op("add", items=[{"text": "後來長出的"}], turn=4)
    assert not ng.reconcile_fresh(_tree())
    assert "T1.3" in ng.auto_reconcile(SID, 4) and ng.reconcile_fresh(_tree())
    assert _tree()["nodes"]["T1.3"]["status"] in ("done", "partial")


# ─── 審查材料不印空的同伴段（續掃新列） ───────────────────────────────────────

def test_review_material_omits_empty_peer_section(env):
    """沒有同伴轉述就不印那段（同 render）；有才印。舊碼印「同伴轉述…（沒有）」。"""
    ng.on_prompt(SID, "幫我讓設定改完不用重開程式", 1, {})
    _op("set", goal="改完設定不用重開")
    text = ng.review_material(SID)
    assert "【使用者原話（權威）】" in text and "【目標樹" in text and "同伴轉述" not in text
    ng.on_prompt(SID, '<cross-session-message from="x" from-name="同伴">記得也改 B</cross-session-message>', 2, {})
    assert "同伴轉述" in ng.review_material(SID)


# ─── 案例寫入不落正式資料根 ───────────────────────────────────────────────────

_PRELOADED_RUN = r"""
import os, sys
from pathlib import Path
tree, fake = Path(sys.argv[1]), Path(sys.argv[2])
os.environ["WG_CLAUDE_DIR"] = str(fake)
sys.path[:0] = [str(tree / "hooks"), str(tree / "lib")]
import wg_core, wg_harvest, wg_need_goal  # noqa
from handlers import post_tool_use  # noqa
import pytest
os.chdir(tree)
sys.exit(pytest.main([str(tree / "hooks" / "verify" / "verify_need_goal.py"), "-q", "-p", "no:cacheprovider"]))
"""


def test_need_goal_cases_never_write_data_root_even_when_modules_preloaded(tmp_path):
    """同一行程先載入本樹模組再跑 pytest（例：run_verify.py）時，模組層的資料夾常數指到啟動時的資料根；verify_need_goal 的案例
    照樣不能在那裡留追蹤帳本或工具結果帳。舊案例只換 wg_core.WORKFLOW_DIR，追蹤帳本與工具結果帳寫進資料根。"""
    fake = tmp_path / "data"
    (fake / "workflow").mkdir(parents=True)
    tree = VERIFY.parent.parent
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", _PRELOADED_RUN, str(tree), str(fake)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300,
                       creationflags=0x08000000 if sys.platform == "win32" else 0)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    left = sorted(str(p.relative_to(fake)) for p in fake.rglob("*") if p.is_file())
    assert left == [], left


if __name__ == "__main__":
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("PULL_GOAL_LOCATE_CHECK PASS" if rc == 0 else "PULL_GOAL_LOCATE_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
