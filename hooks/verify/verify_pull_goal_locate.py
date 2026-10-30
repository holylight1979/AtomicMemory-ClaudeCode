"""verify_pull_goal_locate.py：定位閘同缺件擋次有上限、讀不到 transcript 算閘自己判不了、沒部位表的改檔閘擋滿放行照記地圖。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_pull_goal_locate.py
  （直接跑 python -X utf8 hooks/verify/verify_pull_goal_locate.py 也行：開子行程跑 pytest，尾行印哨兵）
每一案改前紅、改後綠；共用 hub_world 的資料根隔離（env／hooked）與部位世界。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

VERIFY = Path(__file__).resolve().parent
sys.path.insert(0, str(VERIFY))

from hub_world import (  # noqa: E402,F401
    SID, _deny_text, _mapped_world, _ptu_run, block_mode, env, hooked, wg_core, wo,
)


@pytest.fixture(autouse=True)
def _whole_card(monkeypatch):
    """這支照整張注入（card_injection=full）寫的；指標制（預設）的案例在 verify_overview_card_pointer.py。"""
    from hub_config import HUB_DEFAULTS
    monkeypatch.setitem(HUB_DEFAULTS, "card_injection", "full")


def _state():
    return json.loads(wg_core.state_file_path(SID).read_text(encoding="utf-8"))


def _hub_events(env):
    p = env["tmp"] / "hub.log"
    return [json.loads(l).get("event") for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


# ─── 定位閘同缺件擋次上限 ───

def _next_user_turn():
    """下一個使用者回合（turn_prompts_seq 跟著進）：第一次改部位那一刀開的那一輪（LOCATE_FIRST_EDIT_BLOCKS_ONCE）只管那個使用者回合，
    一般判定（缺件全文、擋次上限）從下一個回合起算。"""
    state = _state()
    state["turn_seq"] = int(state.get("turn_seq", 0) or 0) + 1
    state["turn_prompts_seq"] = state["turn_seq"]
    wg_core.write_state(SID, state)


def test_locate_gate_same_gap_blocks_twice_then_passes_with_log(hooked, block_mode):
    """同回合同部位同缺件：擋第 1、2 次，第 3 次放行並留帳（edit_deny_capped）；換回合重給 2 次。舊碼第 3 次照擋。"""
    proj, outputs, tp = hooked["proj"], hooked["outputs"], hooked["tp"]
    f1 = _mapped_world(hooked)
    _ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)                    # 注入導讀卡（不算進缺件次數）
    _next_user_turn()
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))
    out = _ptu_run("Edit", {"file_path": f1}, proj, tp, outputs)
    assert _deny_text(out) is None and "放行並留帳" in json.dumps(out, ensure_ascii=False)
    assert "edit_deny_capped" in _hub_events(hooked)
    _next_user_turn()                                                         # 下一個使用者回合：重給 2 次
    assert _deny_text(_ptu_run("Edit", {"file_path": f1}, proj, tp, outputs))


# ─── 沒部位表的改檔閘、讀不到 transcript ───

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
    hub_state = {"turn_seq": 3}
    wo.on_read(hub_state, SID, "Read", {"file_path": f1}, str(env["proj"]), "", {})   # 讀檔建紀錄、記讀過，卡等第一次改檔
    assert "導讀卡現在才送" in wo.on_edit(hub_state, SID, f1, "", {})[1]        # 第一刀：卡（真入口當提醒件送，不擋）
    for _ in range(3):
        assert wo.on_edit(hub_state, SID, f1, "", {})[1] is None
    assert guard[-1]["check"] == "定位行" and "decl_deny_counts" not in hub_state


def test_unreadable_transcript_still_checks_part_file_reads(env, monkeypatch):
    """讀不到 transcript 只免掉驗不了的定位行；「讀過部位檔」不靠 transcript，照查照擋。"""
    monkeypatch.setattr(wo, "append_guard_log", lambda g, p: None, raising=False)
    f1 = _mapped_world(env)
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


if __name__ == "__main__":
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("PULL_GOAL_LOCATE_CHECK PASS" if rc == 0 else "PULL_GOAL_LOCATE_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
