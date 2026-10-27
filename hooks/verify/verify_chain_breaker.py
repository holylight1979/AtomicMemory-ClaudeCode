"""verify_chain_breaker.py — 連鎖斷路器（hooks/wg_chain.py 判定、lib/chain_store.py 帳／快照／還原）的行為案例。

做什麼：用 chain_store 的公開函式（gate_fired、before_write、action_done、on_stop、record_only——呼叫端接線用的同一組）
  模擬一個使用者回合：閘擋 → AI 改檔 → 又被擋……驗：深度與同一道閘第 2 次會中止、中止後其餘閘只記錄、Stop 只擋一次送三選項、
  headless 不問人、還原只還原連鎖段、繼續會歸零再問、答案只認 tool_use_id 對得上的 AskUserQuestion；
  反例：沒有連鎖時斷路器不介入、comment_only 只記錄不影響判斷。每條 RULES 至少一案（最後一案檢查）。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_chain_breaker.py
       python -X utf8 hooks/verify/verify_chain_breaker.py   （直接跑，尾行 CHAIN_BREAKER_CHECK PASS／FAIL）
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import chain_store as cs  # noqa: E402
import wg_chain as wc  # noqa: E402
import wg_release  # noqa: E402

SID = "sid-chain"
ON = {"chain_breaker": {"enabled": True}}   # 設定沒寫 enabled＝不開；這裡的案例都要開著
DEPTH = {"chain_breaker": {"depth_alarm": True}}   # 深度警報預設關（CHAIN_ALARM_DEPTH）；測深度機制的案子打開


def _on(cfg):
    """cfg 補上 chain_breaker.enabled=True（明寫 False 的照 False）。"""
    out = {**(cfg or {})}
    out["chain_breaker"] = {"enabled": True, **(out.get("chain_breaker") or {})}
    return out


def _jl(path: Path, obj) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


class Turn:
    """一個使用者回合：閘觸發、AI 改檔、收尾、使用者答題都走 chain_store 的公開函式。"""

    def __init__(self, root: Path, turn: int = 1, cfg=None, agent: str = ""):
        self.root, self.turn, self.cfg, self.agent = root, turn, _on(cfg), agent
        self.tp = root / "transcript.jsonl"
        self.tp.touch()
        self.now = 1000.0 * turn
        self.n = 0
        self.mid, self.calls = "", []

    def inp(self, hook: str):
        self.n += 1
        d = {"hook_event_name": hook, "transcript_path": str(self.tp), "session_id": SID}
        if hook in ("PreToolUse", "PostToolUse"):
            d["tool_use_id"] = f"t{self.turn}-tu{self.n}"
            self.calls.append(d["tool_use_id"])
        if self.agent:
            d["agent_id"] = self.agent
        return d

    def reply(self, mid):
        """AI 送出新的一則回覆 mid（CHAIN_SAME_BATCH）：照 CC，上一則串流完才整則寫進 transcript（含它的 tool_use），
        這一則跑工具時一行都還沒落盤；之後的呼叫都屬 mid。"""
        if self.mid:
            _jl(self.tp, {"type": "assistant", "message": {"id": self.mid, "content": [
                {"type": "tool_use", "id": c, "name": "Write", "input": {}} for c in self.calls]}})
        self.mid, self.calls = mid, []

    def say(self, text="（回覆）"):
        _jl(self.tp, {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})

    def tick(self, s=5.0):
        self.now += s
        return self.now

    def gate(self, name, hook="Stop", call=None, **kw):
        """閘 name 觸發一次；call＝(工具名, 參數) 被擋的那個工具呼叫（CHAIN_SAME_CALL_RETRY 比它；不給＝說不出呼叫長什麼樣）。"""
        if hook in wc.STOP_HOOKS:
            self.say()
        d = self.inp(hook)
        if call is not None:
            d["tool_name"], d["tool_input"] = call
        return cs.gate_fired(SID, self.turn, name, f"{name}：缺東西", d, self.cfg, now=self.tick(), **kw)

    def goal(self, action="set"):
        """AI 改了目標樹（need_goal；CHAIN_ACTION_FACTS 算動作、說不出改了哪些檔）。"""
        cs.action_done(SID, self.turn, "goal", "mcp__workflow-guardian__need_goal", [], self.inp("PostToolUse"), self.cfg,
                       what=f"need_goal {action}", now=self.tick())

    def _did(self, tool, path, before, after, ti):
        tr = {"originalFile": before} if before is not None else {"type": "create"}
        facts = wc.edit_facts(tool, ti, tr)
        cs.action_done(SID, self.turn, "edit", tool, facts, self.inp("PostToolUse"), self.cfg, now=self.tick())

    def edit(self, path, old, new):
        path = Path(path)
        before = path.read_text(encoding="utf-8")
        cs.before_write(SID, self.turn, [str(path)], self.inp("PreToolUse"), self.cfg, now=self.tick(1))
        path.write_text(before.replace(old, new, 1), encoding="utf-8")
        self._did("Edit", path, before, None, {"file_path": str(path), "old_string": old, "new_string": new})

    def write(self, path, text):
        path = Path(path)
        before = path.read_text(encoding="utf-8") if path.exists() else None
        cs.before_write(SID, self.turn, [str(path)], self.inp("PreToolUse"), self.cfg, now=self.tick(1))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._did("Write", path, before, text, {"file_path": str(path), "content": text})

    def bash(self, cmd, kind="edit", files=()):
        cs.action_done(SID, self.turn, kind, "Bash", list(files), self.inp("PostToolUse"), self.cfg, what=cmd,
                       now=self.tick())

    def act(self, cmd="python -m pytest -q"):
        """AI 做了一個動作（重跑）：同一道閘兩次之間有動作才算同閘次數（CHAIN_SAME_GATE_NO_ACTION）。"""
        self.bash(cmd, kind="rerun")

    def stop(self):
        self.say()
        return cs.on_stop(SID, self.turn, self.inp("Stop"), self.cfg, now=self.tick())

    def answer(self, a, q=None):
        """使用者在 AskUserQuestion 選了 a（transcript 照 CC 的格式寫 tool_use 與對到 id 的 tool_result）。"""
        q = q or wc.question(self.chain())
        tid = f"ask-{self.turn}-{self.n}"
        self.n += 1
        _jl(self.tp, {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": tid, "name": "AskUserQuestion",
             "input": {"questions": [{"question": q, "header": "連鎖", "multiSelect": False,
                                      "options": [{"label": o} for o in wc.CHOICES]}]}}]}})
        _jl(self.tp, {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid, "content": f'User has answered your questions: "{q}"="{a}".'}]},
            "toolUseResult": {"answers": {q: a}}})

    def chain(self):
        return wc.fold(cs.read_rows(SID), self.turn, self.agent)

    def record_only(self):
        return cs.record_only(SID, self.turn, self.inp("PreToolUse"), self.cfg)


@pytest.fixture()
def box(monkeypatch, tmp_path):
    monkeypatch.setattr(cs, "_ledger_dir", lambda: tmp_path / "Logs")
    monkeypatch.setattr(cs, "_snap_root", lambda: tmp_path / "workflow" / "chain-snap")
    monkeypatch.setattr(cs, "_RETRY_PAUSE", 0)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")      # 互動入口；headless 的案自己改
    monkeypatch.delenv("CLAUDE_COMPANION_JUDGE", raising=False)
    proj = tmp_path / "proj"
    proj.mkdir()
    return tmp_path


def _kinds(rows):
    return [r.get("type") for r in rows]


def _alarm_rules(turn: Turn):
    return {h[0] for h in (turn.chain().alarm or {}).get("hits", [])}


# ─── 001 紅案例 ─────────────────────────────────────────────────────────

def test_depth2_aborts_and_stop_sends_three_options(box):
    """紅案例：閘A擋 → 改檔 → 閘B擋 → 改檔 → 閘A第二次 → 斷路器中止，本回合其餘閘只記錄，Stop 送三選項
    （CHAIN_EDGE_TIME_ORDER、CHAIN_ALARM_DEPTH、CHAIN_ALARM_SAME_GATE、CHAIN_ABORT_RECORD_ONLY、CHAIN_STOP_NOTICE_ONCE）。"""
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    assert t.gate("A") == cs.PASS
    t.edit(x, "x = 1", "x = 2")
    assert t.gate("B") == cs.PASS
    t.edit(x, "x = 2", "x = 3")
    r = t.gate("A")
    assert r.record_only and r.notice and r.halt is None
    for opt in (wc.OPT_RESTORE, wc.OPT_CONTINUE, wc.OPT_RELEASE):
        assert f"「{opt}」" in r.notice
    assert "AskUserQuestion" in r.notice and f"{wg_release.RELEASE_TAG}{wc.CHAIN_TAG}" in r.notice
    assert "總共連鎖 2 次、深度 2" in r.notice                     # 深度照算、照列
    assert _alarm_rules(t) == {"CHAIN_ALARM_SAME_GATE"}           # 深度警報預設關，響的是同閘第 2 次
    assert [s.link.rule for s in t.chain().steps[1:]] == ["CHAIN_EDGE_TIME_ORDER"] * 2
    assert t.gate("C", hook="PreToolUse") == cs.GateResult(True)      # 其餘閘只記錄
    assert t.gate("D") == cs.GateResult(True)                         # 收尾閘也只記錄、不再送通知
    assert t.record_only()
    out = t.stop()
    assert out is not None and not out.block and "還沒收到使用者三選一" in out.text
    assert _kinds(cs.read_rows(SID)).count("notice") == 1


def test_three_distinct_gates_do_not_alarm_by_default(box):
    """紅案例（CHAIN_ALARM_DEPTH 預設不警報）：A → 改 → B → 改 → C，三道各管各的閘各擋一次 → 不響；
    深度照算（2）、照列進經過表。"""
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.gate("A")
    t.edit(x, "x = 1", "x = 2")
    t.gate("B", hook="PreToolUse")
    t.edit(x, "x = 2", "x = 3")
    assert t.gate("C") == cs.PASS
    ch = t.chain()
    assert ch.alarm is None and ch.depth == 2 and "總共連鎖 2 次、深度 2" in wc.report(ch, t.now)
    assert not wc.settings(ON)["depth_alarm"]


def test_depth_alarm_switch_on_alarms_at_depth2(box):
    """CHAIN_ALARM_DEPTH 開關有效：設定 depth_alarm=true → 同樣三道閘各一次，深度 2 就中止。"""
    t, x = Turn(box, cfg=DEPTH), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.gate("A")
    t.edit(x, "x = 1", "x = 2")
    t.gate("B", hook="PreToolUse")
    t.edit(x, "x = 2", "x = 3")
    r = t.gate("C")
    assert r.notice and _alarm_rules(t) == {"CHAIN_ALARM_DEPTH"}


def test_same_gate_needs_action_between(box):
    """紅案例（C1：CHAIN_SAME_GATE_NO_ACTION、CHAIN_ALARM_SAME_GATE）：閘A 擋 → AI 沒動作又撞閘A（重試同一個呼叫、只改寫回覆就收尾）
    → 不接邊、不算同閘次數、不警報，交回 A 自己的擋次上限；閘A 擋 → AI 動手 → 閘A 再擋 → 警報；中間的動作接在別道閘後面也算。"""
    t = Turn(box)
    assert t.gate("A", hook="PreToolUse") == cs.PASS
    assert t.gate("A", hook="PreToolUse") == cs.PASS
    assert t.gate("A") == cs.PASS
    ch = t.chain()
    assert [s.link.rule for s in ch.steps[1:]] == ["CHAIN_SAME_GATE_NO_ACTION"] * 2 and ch.depth == 0
    assert wc.same_count(ch.steps, {"gate": "A"}) == 1
    t.act()
    r = t.gate("A")
    assert r.notice and _alarm_rules(t) == {"CHAIN_ALARM_SAME_GATE"}
    u = Turn(box, turn=2)
    u.gate("A")
    u.gate("B", later=["A"])
    u.act()                                                      # 動作接在 B 後面
    assert u.gate("A").notice and "CHAIN_ALARM_SAME_GATE" in _alarm_rules(u)


def test_alarm_on_tool_gate_notes_then_stop_notices_once(box):
    """CHAIN_STOP_NOTICE_ONCE：警報在工具閘上響 → 那次只附一句（不擋）；接著的收尾擋一次送經過表，再之後的收尾不擋。"""
    t = Turn(box)
    t.gate("A", hook="PreToolUse")
    t.act()
    r = t.gate("A", hook="PreToolUse")
    assert r.record_only and r.notice is None and "先停手" in r.halt and wc.question(t.chain()) in r.halt
    first, second, third = t.stop(), t.stop(), t.stop()
    assert first.block and "連鎖中止" in first.text
    assert not second.block and not third.block
    assert _kinds(cs.read_rows(SID)).count("notice") == 1


def test_headless_main_session_aborts_without_asking(box, monkeypatch):
    """紅案例（C2：CHAIN_HEADLESS_NO_ASK）：headless 主 session 觸發 → 不叫 AI 問、不停手：其餘閘只記錄、改檔照放、帳上有 alarm；
    transcript 裡就算有答案也不還原、不繼續；收尾通知要 AI 照常做完、在收尾報告寫明。工具閘上響的那一次照放、收尾再送表。"""
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.gate("A")
    t.edit(x, "x = 1", "x = 2")
    r = t.gate("A")
    assert r.notice and "無法互動" in r.notice and "收尾報告" in r.notice and "沒有還原" in r.notice and "照常" in r.notice
    assert "AskUserQuestion" not in r.notice and wc.OPT_RESTORE not in r.notice
    notice = t.chain().notice
    assert notice["interactive"] is False and "headless" in notice["why"]
    t.answer(wc.OPT_RESTORE)
    assert t.stop() is None
    assert cs.halt(SID, 1, "Edit", t.inp("PreToolUse"), ON) is None           # 不停手
    t.edit(x, "x = 2", "x = 3")
    assert x.read_text(encoding="utf-8") == "x = 3\n"
    assert t.gate("B", hook="PreToolUse") == cs.GateResult(True)                # 其餘閘只記錄
    assert not {"answer", "reset", "restore", "halted"} & set(_kinds(cs.read_rows(SID)))
    assert "alarm" in _kinds(cs.read_rows(SID)) and t.record_only()
    u = Turn(box, turn=2)
    assert u.gate("A", hook="PreToolUse") == cs.PASS
    u.act()
    assert u.gate("A", hook="PreToolUse") == cs.GateResult(True)               # 工具閘上響：照放，不給 halt
    out = u.stop()
    assert out.block and "無法互動" in out.text and u.stop() is None


def test_headless_keeps_data_gates_after_alarm(box, monkeypatch):
    """紅案例（CHAIN_HEADLESS_KEEPS_DATA_GATES）：無頭、警報之後，會改使用者資料的閘（KEEP_BLOCKING）照擋、同一道再擋也照擋，
    每次都記一筆 kept、不算進次數；其餘閘（定位閘）只記錄。讓警報響的那一次是動資料檔閘也照擋。能互動的 session 不變：
    響的那次改送停手，使用者選「放行這一回合」之後動資料檔閘照放（使用者的決定）。改前警報後全部只記錄。"""
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    t = Turn(box)
    t.gate("A", hook="PreToolUse")
    t.act()
    assert t.gate("A", hook="PreToolUse") == cs.GateResult(True)                # 警報響：不是資料閘，無頭照放
    for name in sorted(wc.KEEP_BLOCKING):
        assert t.gate(name, hook="PreToolUse") == cs.PASS, name
    assert t.gate("DataFileAsk", hook="PreToolUse") == cs.PASS                  # 同一道閘再擋一次也照擋
    assert t.gate("OverviewHub", hook="PreToolUse") == cs.GateResult(True)      # 管做法的閘只記錄
    ch = t.chain()
    kept = [s for s in ch.steps if s.row.get("kept")]
    assert len(kept) == len(wc.KEEP_BLOCKING) + 1 and all(s.muted and not s.row["record_only"] for s in kept)
    assert ch.count == 1 and "會改使用者資料照擋" in wc.report(ch, t.now)
    out = t.stop()
    assert out.block and "照它的擋訊息補宣告" in out.text and "AskUserQuestion" not in out.text
    f = box / "proj" / "README.md"
    u = Turn(box, turn=2)
    assert u.gate("DataFileAsk", hook="PreToolUse", watched=[str(f)]) == cs.PASS
    u.act()
    assert u.gate("DataFileAsk", hook="PreToolUse", watched=[str(f)]) == cs.PASS   # 讓警報響的這一次也照擋
    assert u.chain().alarm and u.chain().steps[-1].row["kept"] and not u.chain().steps[-1].row["record_only"]
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    v = Turn(box, turn=3)
    v.gate("DataFileAsk", hook="PreToolUse", watched=[str(f)])
    v.act()
    assert v.gate("DataFileAsk", hook="PreToolUse", watched=[str(f)]).halt       # 能互動：改送停手
    v.answer(wc.OPT_RELEASE)
    assert cs.halt(SID, 3, "Write", v.inp("PreToolUse"), ON) is None
    assert v.gate("DataFileAsk", hook="PreToolUse", watched=[str(f)]) == cs.GateResult(True)
    assert not any(s.row.get("kept") for s in v.chain().steps)


def test_subagent_has_own_chain_and_is_not_asked(box):
    """CHAIN_SAME_TURN／CHAIN_HEADLESS_NO_ASK：子代理（帶 agent_id）的觸發另算一條鏈、不算進主 session；子代理裡中止也不問人。"""
    main, sub = Turn(box), Turn(box, agent="agent-1")
    main.gate("A")
    r = sub.gate("A", hook="SubagentStop")
    assert r == cs.PASS and main.chain().count == 0
    sub.act()
    r = sub.gate("A", hook="SubagentStop")
    assert r.notice and "子代理" in r.notice and "AskUserQuestion" not in r.notice
    assert not main.record_only() and sub.record_only()
    assert cs.halt(SID, 1, "Edit", sub.inp("PreToolUse"), ON) is None           # 子代理不停手（C2）


def test_restore_puts_back_chain_segment_only(box):
    """紅案例（CHAIN_RESTORE_SEGMENT、CHAIN_SNAPSHOT_WINDOW）：選還原 → 連鎖段改過的檔內容等於快照、連鎖中新建的檔被刪，
    連鎖前改的檔不變；還原後這一回合其餘閘只記錄。"""
    t, proj = Turn(box), box / "proj"
    pre, x, new = proj / "pre.py", proj / "x.py", proj / "sub" / "new.py"
    pre.write_text("a = 1\n", encoding="utf-8")
    x.write_text("x = 1\n", encoding="utf-8")
    t.edit(pre, "a = 1", "a = 2")                    # 連鎖前的正當改動
    t.gate("A")
    t.edit(x, "x = 1", "x = 2")
    t.write(new, "n = 1\n")
    t.gate("B")
    t.edit(x, "x = 2", "x = 3")                      # 同一段同一檔不再存快照
    r = t.gate("A")
    assert r.notice
    assert sorted(Path(p).name for p in t.chain().snaps) == ["new.py", "x.py"]
    t.answer(wc.OPT_RESTORE)
    out = t.stop()
    assert not out.block and "寫回 1 檔、刪掉連鎖中新建的 1 檔" in out.text
    assert x.read_text(encoding="utf-8") == "x = 1\n"
    assert not new.exists()
    assert pre.read_text(encoding="utf-8") == "a = 2\n"
    assert all(res["ok"] for res in t.chain().restored["results"])
    assert t.gate("C") == cs.GateResult(True)


def test_continue_resets_and_asks_again(box):
    """紅案例（CHAIN_CONTINUE_RESETS）：選繼續 → 計數歸零、閘照常擋；同樣額度再超 → 再問一次。"""
    t = Turn(box)
    t.gate("A")
    t.act()
    assert t.gate("A").notice
    t.answer(wc.OPT_CONTINUE)
    out = t.stop()
    assert not out.block and "歸零" in out.text
    assert not t.record_only()
    assert t.chain().segment == 1 and t.chain().count == 0
    assert t.gate("A") == cs.PASS                     # 新的一段第一次：照擋
    t.act()
    r = t.gate("A")
    assert r.notice and "總共連鎖 1 次" in r.notice
    assert _kinds(cs.read_rows(SID)).count("notice") == 2


def test_release_keeps_record_only_until_next_turn(box):
    """CHAIN_RELEASE_TURN、CHAIN_SAME_TURN：選放行 → 這一回合其餘閘只記錄；下一回合從零起、閘照常擋。"""
    t = Turn(box)
    t.gate("A")
    t.act()
    t.gate("A")
    t.answer(wg_release.OPT_RELEASE)
    out = t.stop()
    assert "放行這一回合" in out.text and t.chain().answer["choice"] == "release"
    assert t.gate("B") == cs.GateResult(True)
    nxt = Turn(box, turn=2)
    assert nxt.gate("A") == cs.PASS and not nxt.record_only()


# ─── 001 反例：沒有連鎖時斷路器不介入 ──────────────────────────────────────

def test_no_chain_breaker_stays_out(box):
    """反例：擋一次、修一次、過 → 斷路器不介入：gate_fired 照擋（PASS）、收尾回 None、帳上沒有警報與通知；既有閘行為不變。"""
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    assert t.gate("A") == cs.GateResult(False, None, None)
    t.edit(x, "x = 1", "x = 2")
    assert t.stop() is None
    assert not t.record_only()
    assert set(_kinds(cs.read_rows(SID))) <= {"gate", "action", "snapshot"}


def test_one_trigger_per_turn_never_alarms(box):
    """反例（CHAIN_SAME_TURN）：同一道閘每回合各擋一次、連五個回合 → 不算同一回合第 2 次，不中止。"""
    for n in range(1, 6):
        t = Turn(box, turn=n)
        assert t.gate("A") == cs.PASS and t.stop() is None


def test_disabled_is_no_op(box):
    """設定 chain_breaker.enabled=false → 什麼都不記、閘照舊。"""
    t = Turn(box, cfg={"chain_breaker": {"enabled": False}})
    assert t.gate("A") == cs.PASS and t.gate("A") == cs.PASS and t.stop() is None
    assert not cs.ledger_path(SID).exists()


def test_v6_off_is_no_op(box, monkeypatch):
    """紅案例（v6 總開關）：WG_V6=0、chain_breaker 開 → 整個斷路器不跑：同閘擋兩次照擋（PASS）、不停手、不存快照、
    不記動作、收尾回 None，帳一筆都不寫。"""
    monkeypatch.setenv("WG_V6", "0")
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    assert t.gate("A") == cs.PASS
    t.edit(x, "x = 1", "x = 2")
    assert t.gate("A") == cs.PASS and t.gate("A", hook="PreToolUse") == cs.PASS
    assert cs.halt(SID, 1, "Edit", t.inp("PreToolUse"), ON) is None
    assert t.stop() is None and not t.record_only()
    assert not cs.ledger_path(SID).exists() and not (box / "workflow" / "chain-snap").exists()


def test_errors_fall_back_to_existing_gates(box, monkeypatch, capsys):
    """斷路器自己出錯 → 照原本的閘行為（不中止、不只記錄），stderr 印一行，不能無聲吞掉。"""
    def boom(sid):
        raise OSError("disk gone")
    monkeypatch.setattr(cs, "read_rows", boom)
    t = Turn(box)
    assert t.gate("A") == cs.PASS and not t.record_only() and t.stop() is None
    assert "[chain-breaker] gate_fired 出錯" in capsys.readouterr().err


def test_breaker_never_demands_fixes(box):
    """CHAIN_ABORT_RECORD_ONLY：斷路器不逼修補、不要求宣告——改檔前後的呼叫什麼都不回；警報後真的改了也照存快照
    （停手由 halt 在動手前擋，見 CHAIN_HALT_UNTIL_ANSWER 的案）。"""
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.gate("A")
    t.act()
    t.gate("A")
    assert cs.before_write(SID, 1, [str(x)], t.inp("PreToolUse"), ON) is None
    assert cs.action_done(SID, 1, "edit", "Edit", [], t.inp("PostToolUse"), ON) is None
    assert wc.canon_path(x) in t.chain().snaps


# ─── 邊的判法 ──────────────────────────────────────────────────────────

def test_same_event_gates_do_not_link(box):
    """CHAIN_SAME_EVENT：同一次收尾裡先後記的兩道閘不接成邊。"""
    t = Turn(box)
    t.say()
    inp = t.inp("Stop")
    cs.gate_fired(SID, 1, "A", "a", inp, ON, now=t.tick())
    cs.gate_fired(SID, 1, "B", "b", inp, ON, now=t.tick())
    ch = t.chain()
    assert ch.steps[1].link.rule == "CHAIN_SAME_EVENT" and ch.depth == 0 and ch.count == 1


def test_previewed_gate_does_not_link(box):
    """CHAIN_EDGE_PREVIEWED：B 已列在 A 擋下時的預覽裡 → A→B 不接；B→C 照接，深度 1 不中止。反例：沒有預覽就深度 2 中止（深度警報打開）。"""
    t, x = Turn(box, cfg=DEPTH), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.gate("A", later=["B"])
    t.edit(x, "x = 1", "x = 2")
    t.gate("B")
    t.edit(x, "x = 2", "x = 3")
    assert t.gate("C") == cs.PASS
    ch = t.chain()
    assert ch.steps[1].link.rule == "CHAIN_EDGE_PREVIEWED" and ch.depth == 1
    u = Turn(box, turn=2, cfg=DEPTH)
    u.gate("A")
    u.edit(x, "x = 3", "x = 4")
    u.gate("B")
    u.edit(x, "x = 4", "x = 5")
    assert u.gate("C").notice


def test_files_disjoint_does_not_link(box):
    """CHAIN_EDGE_FILES_DISJOINT：B 說它看 y.py、A 之後只改了 x.py → 不接；看 x.py 就接；中間有說不出檔的動作（重跑）照接。"""
    proj = box / "proj"
    x, y = proj / "x.py", proj / "y.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t = Turn(box)
    t.gate("A")
    t.edit(x, "x = 1", "x = 2")
    t.gate("B", watched=[str(y)])
    assert t.chain().steps[1].link.rule == "CHAIN_EDGE_FILES_DISJOINT"
    u = Turn(box, turn=2)
    u.gate("A")
    u.edit(x, "x = 2", "x = 3")
    u.gate("B", watched=[str(x).upper()])                    # SAME_FILE：大小寫不同也是同一個檔
    assert u.chain().steps[1].link.linked
    v = Turn(box, turn=3)
    v.gate("A")
    v.edit(x, "x = 3", "x = 4")
    v.bash("python -m pytest -q tests", kind="rerun")
    v.gate("B", watched=[str(y)])
    assert v.chain().steps[1].link.linked


def test_count_is_triggers_minus_one_depth_is_run(box):
    """CHAIN_COUNT_TRIGGERS：次數＝觸發總數減 1（沒接上的、只記錄的都算）；深度只算連續的邊。"""
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.gate("A", hook="PreToolUse")
    t.gate("B")                                              # 沒動手就收尾：不接（CHAIN_NO_FIX_NO_EDGE）
    t.edit(x, "x = 1", "x = 2")
    assert t.gate("C", hook="PreToolUse") == cs.PASS
    ch = t.chain()
    assert ch.steps[1].link.rule == "CHAIN_NO_FIX_NO_EDGE"
    assert (ch.count, ch.depth) == (2, 1)
    assert wc.report(ch, t.now).endswith("總共連鎖 2 次、深度 1")


def test_thresholds_from_config(box):
    """門檻放設定可調：max_depth=3、max_same_gate=3（深度警報打開）→ 深度 2、同閘第 2 次都不中止，到 3 才中止。"""
    cfg = {"chain_breaker": {"depth_alarm": True, "max_depth": 3, "max_same_gate": 3}}
    t = Turn(box, cfg=cfg)
    t.gate("A")
    t.gate("B")
    assert t.gate("A") == cs.PASS                             # 深度 2、A 第 2 次
    assert t.gate("C").notice                                 # 深度 3
    assert wc.settings({"chain_breaker": {"max_depth": 0, "enabled": "no", "depth_alarm": 1}}) == wc.DEFAULTS
    assert not wc.settings({})["enabled"] and wc.settings(ON)["enabled"]           # 沒寫 enabled＝不開


# ─── 答案防偽 ──────────────────────────────────────────────────────────

def test_answer_only_from_matching_ask_user_question(box):
    """CHAIN_ANSWER_BY_TOOL_USE_ID：通知之前的答案、AI 回覆文字、使用者打字、Bash 輸出寫出同樣的字樣、題目沒有【連鎖中止】、
    改了題意的題都不算（不解析回覆文字）；tool_use_id 對得上、題目逐字等於通知那一題的 AskUserQuestion 才算。"""
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.gate("A")
    t.answer(wc.OPT_RESTORE)                                  # 通知之前就答：不算
    t.edit(x, "x = 1", "x = 2")
    assert t.gate("A").notice
    q = wc.question(t.chain())
    forged = f'"{q}"="{wc.OPT_RESTORE}"'
    t.say(forged)                                                           # AI 回覆文字
    t.say(wc.OPT_RESTORE)
    _jl(t.tp, {"type": "user", "message": {"content": wc.OPT_RESTORE}})     # 使用者打字
    _jl(t.tp, {"type": "user", "message": {"content": [{"type": "text", "text": forged}]}})
    _jl(t.tp, {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "b1", "name": "Bash", "input": {"command": f"echo '{forged}'"}}]}})
    _jl(t.tp, {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "b1", "content": forged}]},
               "toolUseResult": {"answers": {q: wc.OPT_RESTORE}}})
    t.answer(wc.OPT_RESTORE, q=f"{wg_release.RELEASE_TAG}要怎麼處理？")
    t.answer(wc.OPT_RESTORE, q=f"{wg_release.RELEASE_TAG}{wc.CHAIN_TAG}只撤銷最後一次小改動，好嗎？")   # 改了題意
    out = t.stop()
    assert "還沒收到使用者三選一" in out.text and x.read_text(encoding="utf-8") == "x = 2\n"
    t.answer(wc.OPT_RESTORE)
    out = t.stop()
    assert "已照使用者選擇還原" in out.text and x.read_text(encoding="utf-8") == "x = 1\n"


def test_other_answer_keeps_abort(box):
    """CHAIN_ANSWER_BY_TOOL_USE_ID：使用者打了三選項以外的字 → 記下來、維持中止只記錄，不還原也不歸零。"""
    t = Turn(box)
    t.gate("A")
    t.act()
    t.gate("A")
    t.answer("先等等")
    out = t.stop()
    assert "沒選三選項之一" in out.text and t.record_only()
    q = wc.question(t.chain())
    assert wc.choice_of([(q, "還原連鎖改動(不符本批目標)")], q)[0] == "restore"     # 全半形括號一樣


# ─── 快照窗口與還原細節 ────────────────────────────────────────────────

def test_snapshot_window_and_limits(box):
    """CHAIN_SNAPSHOT_WINDOW：第一道閘之前不存；之後每檔這一段只存一次、新建檔記不存在；超過大小上限、存滿的記原因；
    斷路器自己的帳與快照目錄不存；使用者答過之後不再存。"""
    cfg = {"chain_breaker": {"snapshot_max_bytes": 20, "snapshot_max_files": 3}}
    proj = box / "proj"
    t = Turn(box, cfg=cfg)
    a, big, c, d = proj / "a.py", proj / "big.bin", proj / "c.py", proj / "d.py"
    a.write_text("a = 1\n", encoding="utf-8")
    big.write_bytes(b"\x00" * 64)
    cs.before_write(SID, 1, [str(a)], t.inp("PreToolUse"), t.cfg)
    assert t.chain().snaps == {}
    t.gate("A")
    paths = [str(a), str(a), str(big), "rel.py", str(c), str(d), str(cs.ledger_path(SID)),
             str(box / "workflow" / "chain-snap" / SID / "x.snap")]
    cs.before_write(SID, 1, paths, t.inp("PreToolUse"), t.cfg)
    snaps = {Path(p).name: r for p, r in t.chain().snaps.items()}
    assert set(snaps) == {"a.py", "big.bin", "c.py", "d.py"}
    assert snaps["a.py"]["existed"] and snaps["a.py"]["sha256"] and not snaps["a.py"].get("skipped")
    assert "超過 20 位元組" in snaps["big.bin"]["skipped"]
    assert snaps["c.py"]["existed"] is False
    assert "已存滿" in snaps["d.py"]["skipped"]
    assert len([r for r in cs.read_rows(SID) if r["type"] == "snapshot"]) == 4
    t.act()
    t.gate("A")
    t.answer(wg_release.OPT_RELEASE)
    t.stop()
    e = proj / "e.py"
    cs.before_write(SID, 1, [str(e)], t.inp("PreToolUse"), t.cfg)
    assert wc.canon_path(e) not in t.chain().snaps


def test_snapshots_of_older_turns_are_pruned(box):
    """存新回合的快照時清掉這個 session 之前回合的快照（中止只在警報那一回合有效）。"""
    x = box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t1 = Turn(box, turn=1)
    t1.gate("A")
    t1.edit(x, "x = 1", "x = 2")
    snap_dir = box / "workflow" / "chain-snap" / SID
    assert [f.name[:3] for f in snap_dir.iterdir()] == ["t1-"]
    t2 = Turn(box, turn=2)
    t2.gate("A")
    t2.edit(x, "x = 2", "x = 3")
    assert [f.name[:3] for f in snap_dir.iterdir()] == ["t2-"]


def test_restore_reports_what_it_could_not_restore(box):
    """CHAIN_RESTORE_SEGMENT：太大沒存的檔、Bash 改了但說不出哪些檔的動作 → 列在結果裡、不假裝還原了。"""
    cfg = {"chain_breaker": {"snapshot_max_bytes": 20}}
    t, big = Turn(box, cfg=cfg), box / "proj" / "big.txt"
    big.write_text("y" * 64, encoding="utf-8")
    t.gate("A")
    t.write(big, "z" * 64)
    t.bash("sed -i 's/a/b/' cfg.ini")
    t.gate("A")
    t.answer(wc.OPT_RESTORE)
    out = t.stop()
    assert "沒還原成功：" in out.text and "proj/big.txt（沒快照：超過 20 位元組）" in out.text
    assert "改過但沒快照、沒還原：Bash：sed -i 's/a/b/' cfg.ini（改了哪些檔判不出）" in out.text
    assert big.read_text(encoding="utf-8") == "z" * 64


def test_restore_retries_and_refuses_tampered_snapshot(box, monkeypatch):
    """CHAIN_RESTORE_SEGMENT：寫回失敗會重試、成功就算；一直失敗回報原因；快照雜湊對不上 → 不寫回（不拿壞快照蓋檔）。"""
    x = box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t = Turn(box)
    t.gate("A")
    t.edit(x, "x = 1", "x = 2")
    ch = t.chain()
    real = cs._restore_one
    calls = []

    def flaky(it, root, cfg):
        calls.append(it.path)
        return (False, "被鎖住") if len(calls) == 1 else real(it, root, cfg)
    monkeypatch.setattr(cs, "_restore_one", flaky)
    res, _ = cs.restore(SID, ch, wc.settings({}))
    assert res[0]["ok"] and len(calls) == 2 and x.read_text(encoding="utf-8") == "x = 1\n"
    monkeypatch.setattr(cs, "_restore_one", lambda it, root, cfg: (False, "被鎖住"))
    res, _ = cs.restore(SID, ch, wc.settings({}))
    assert res == [{"path": str(x), "ok": False, "how": "write", "why": "被鎖住"}]
    monkeypatch.setattr(cs, "_restore_one", real)
    x.write_text("x = 2\n", encoding="utf-8")                              # 回到連鎖最後寫入的內容
    snap = box / "workflow" / "chain-snap" / SID / ch.snaps[wc.canon_path(x)]["snap"]
    snap.write_text("tampered\n", encoding="utf-8")
    res, _ = cs.restore(SID, ch, wc.settings({}))
    assert not res[0]["ok"] and "雜湊對不上" in res[0]["why"] and x.read_text(encoding="utf-8") == "x = 2\n"


# ─── 中止就是停手；還原不傷到連鎖以外的東西 ──────────────────────────────

def test_halt_until_answer(box):
    """CHAIN_HALT_UNTIL_ANSWER：警報後到使用者選之前，讀與問以外的工具呼叫先擋下（附題目與經過表、記 halted、不算閘觸發）；
    讀、AskUserQuestion、呼叫端判定唯讀的指令照過；使用者選繼續 → 這個呼叫當場放行、新的一段照常。"""
    t = Turn(box)
    assert cs.halt(SID, 1, "Edit", t.inp("PreToolUse"), ON) is None      # 沒警報不介入
    t.gate("A")
    t.act()
    t.gate("A")
    msg = cs.halt(SID, 1, "Edit", t.inp("PreToolUse"), ON)
    assert msg and "先停手" in msg and wc.question(t.chain()) in msg and "總共連鎖 1 次" in msg
    for tool in ("Read", "Grep", "AskUserQuestion"):
        assert cs.halt(SID, 1, tool, t.inp("PreToolUse"), ON) is None
    assert cs.halt(SID, 1, "Bash", t.inp("PreToolUse"), ON, readonly=True) is None
    ch = t.chain()
    assert ch.halted == 1 and ch.count == 1                                # 擋下不算閘觸發
    t.answer(wc.OPT_CONTINUE)
    assert cs.halt(SID, 1, "Edit", t.inp("PreToolUse"), ON) is None
    assert t.chain().segment == 1 and not t.record_only()


def test_tripping_alarm_does_not_let_blocked_call_through(box):
    """CHAIN_HALT_UNTIL_ANSWER（codex：故意讓警報響來繞閘）：工具閘 A 擋 → AI 動了別的手 → 再撞 A 讓警報響，
    回的不是放行而是 halt（呼叫端照擋）；之後換別的寫入工具也被 halt 擋，閘只記錄換不到動作過關。"""
    t = Turn(box)
    assert t.gate("A", hook="PreToolUse") == cs.PASS                       # 呼叫端照 A 的訊息擋
    t.act()
    r = t.gate("A", hook="PreToolUse")
    assert r.record_only and r.halt                                       # A 不用擋，但 halt 照擋這個呼叫
    for tool in ("Edit", "Write", "Bash", "mcp__x__write"):
        assert cs.halt(SID, 1, tool, t.inp("PreToolUse"), ON)


def test_restore_does_not_clobber_outside_changes(box):
    """CHAIN_RESTORE_SEGMENT（codex：還原會蓋掉別處的修改）：連鎖改過的檔之後被別處改了、連鎖中新建的檔之後被別處改了
    → 不覆寫、不刪，列出原因；沒被動過的照常還原。"""
    proj = box / "proj"
    x, y, new = proj / "x.py", proj / "y.py", proj / "new.py"
    x.write_text("x = 1\n", encoding="utf-8")
    y.write_text("y = 1\n", encoding="utf-8")
    t = Turn(box)
    t.gate("A")
    t.edit(x, "x = 1", "x = 2")
    t.edit(y, "y = 1", "y = 2")
    t.write(new, "n = 1\n")
    x.write_text("x = 2  # 使用者自己在編輯器改的\n", encoding="utf-8")
    new.write_text("n = 1\nkeep = True\n", encoding="utf-8")
    t.gate("A")
    t.answer(wc.OPT_RESTORE)
    out = t.stop()
    res = {Path(r["path"]).name: r for r in t.chain().restored["results"]}
    assert not res["x.py"]["ok"] and "被別處改過" in res["x.py"]["why"]
    assert not res["new.py"]["ok"] and new.exists()
    assert res["y.py"]["ok"] and y.read_text(encoding="utf-8") == "y = 1\n"
    assert x.read_text(encoding="utf-8") == "x = 2  # 使用者自己在編輯器改的\n"
    assert "沒還原成功：" in out.text


def test_restore_temp_file_never_touches_siblings(box):
    """CHAIN_RESTORE_SEGMENT（codex：固定暫存檔名會蓋掉同名檔）：旁邊原本就有 x.py.chain-restore.tmp → 還原後它原封不動，
    也不留下還原用的暫存檔。"""
    proj = box / "proj"
    x, sib = proj / "x.py", proj / "x.py.chain-restore.tmp"
    x.write_text("x = 1\n", encoding="utf-8")
    sib.write_text("keep\n", encoding="utf-8")
    t = Turn(box)
    t.gate("A")
    t.edit(x, "x = 1", "x = 2")
    t.gate("A")
    t.answer(wc.OPT_RESTORE)
    t.stop()
    assert x.read_text(encoding="utf-8") == "x = 1\n" and sib.read_text(encoding="utf-8") == "keep\n"
    assert sorted(p.name for p in proj.iterdir()) == ["x.py", "x.py.chain-restore.tmp"]


def test_snapshot_file_is_never_overwritten(box):
    """CHAIN_SNAPSHOT_WINDOW（codex：並行兩個 hook 存同一份快照會互蓋）：同一段同一檔的快照正式名已在 → 第二次不覆寫，
    回報的雜湊是已在那份的（帳上不會出現「雜湊對不上」的基準）。"""
    x = box / "proj" / "x.py"
    x.write_text("V0\n", encoding="utf-8")
    t = Turn(box)
    t.gate("A")
    cx = cs._ctx(SID, 1, t.inp("PreToolUse"), ON, None)
    root = box / "workflow" / "chain-snap" / SID
    first = cs._take(x, root, cx, 0)
    x.write_text("V1\n", encoding="utf-8")
    second = cs._take(x, root, cx, 0)
    assert first["snap"] == second["snap"] and first["sha256"] == second["sha256"]
    assert (root / first["snap"]).read_text(encoding="utf-8") == "V0\n"
    assert [p.name for p in root.iterdir()] == [first["snap"]]             # 暫存檔清掉了


def test_restore_refuses_when_real_path_changed(box, monkeypatch):
    """CHAIN_RESTORE_SEGMENT（codex：junction／連結改指向會寫到別處）：快照時記的實際路徑和還原時不同 → 不寫、不刪。"""
    x = box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t = Turn(box)
    t.gate("A")
    t.edit(x, "x = 1", "x = 2")
    t.gate("A")
    monkeypatch.setattr(cs, "_real", lambda p: "d:/elsewhere/x.py")
    t.answer(wc.OPT_RESTORE)
    t.stop()
    r = t.chain().restored["results"][0]
    assert not r["ok"] and "實際路徑變了" in r["why"] and x.read_text(encoding="utf-8") == "x = 2\n"


def test_late_hook_of_older_turn_keeps_newer_snapshots(box):
    """CHAIN_SNAPSHOT_WINDOW（codex：舊回合延遲的 hook 會刪新回合快照）：回合 2 已存快照，回合 1 晚到的 before_write 存快照時
    只清比 1 更早的，回合 2 的留著。"""
    x, y = box / "proj" / "x.py", box / "proj" / "y.py"
    x.write_text("x\n", encoding="utf-8")
    y.write_text("y\n", encoding="utf-8")
    t1, t2 = Turn(box, turn=1), Turn(box, turn=2)
    t1.gate("A")
    t2.gate("A")
    t2.edit(x, "x", "x2")
    cs.before_write(SID, 1, [str(y)], t1.inp("PreToolUse"), ON)
    names = sorted(p.name[:3] for p in (box / "workflow" / "chain-snap" / SID).iterdir())
    assert names == ["t1-", "t2-"]


# ─── 經過表 ────────────────────────────────────────────────────────────

def test_report_table_shape(box):
    """回報內容：每步一列——第幾步、哪道閘、擋的對象（說不出寫 —）、擋了什麼（一句）、AI 做了什麼改動（檔與行數）、這一步耗時；最後一句總次數與深度。"""
    t, x = Turn(box, cfg=DEPTH), box / "proj" / "x.py"
    x.write_text("x = 1\ny = 1\n", encoding="utf-8")
    t.gate("A")
    t.edit(x, "x = 1\ny = 1", "x = 2\ny = 2\nz = 2")
    t.gate("B")
    r = t.gate("C")
    lines = r.notice.splitlines()
    assert "| 步 | 閘 | 擋的對象 | 擋了什麼 | AI 接著做了什麼改動 | 耗時 |" in lines
    row1 = next(ln for ln in lines if ln.startswith("| 1 |"))
    assert "| A | — |" in row1 and "A：缺東西" in row1 and "改 chain-breaker" not in row1
    assert "proj/x.py（+3/−2 行）" in row1 and "| 11 秒 |" in row1      # 閘A 1005 → 閘B 1016
    row2 = next(ln for ln in lines if ln.startswith("| 2 |"))
    assert "（沒記到改動：改寫回覆）" in row2
    assert "| 3 | C | — | C：缺東西（這一次讓警報響：改送中止） |" in r.notice    # 讓警報響的那一次不標「只記錄」
    assert "總共連鎖 2 次、深度 2" in lines
    t.gate("D")                                                               # 警報之後的才標只記錄
    assert "| 4 | D | — | D：缺東西（只記錄） |" in wc.report(t.chain(), t.now)


# ─── 002：comment_only ─────────────────────────────────────────────────

def test_comment_only_add_smell_ok_line_is_true():
    """CHAIN_COMMENT_ONLY_RECORDED 紅案例：只加一行 `# smell-ok: …` → comment_only=true（用 originalFile 比整檔）。"""
    src = "def f(x):\n    return x + 1\n"
    facts = wc.edit_facts("Edit", {"file_path": "c:/p/a.py", "old_string": "    return x + 1",
                                   "new_string": "    # smell-ok: 單行回傳\n    return x + 1"}, {"originalFile": src})
    assert facts == [{"path": "c:/p/a.py", "added": 1, "removed": 0, "comment_only": True}]


def test_comment_only_code_change_with_comment_is_false():
    """CHAIN_COMMENT_ONLY_RECORDED 紅案例：改一行程式、加一行註解 → false。"""
    src = "def f(x):\n    return x + 1\n"
    facts = wc.edit_facts("Edit", {"file_path": "c:/p/a.py", "old_string": "    return x + 1",
                                   "new_string": "    # 改成加二\n    return x + 2"}, {"originalFile": src})
    assert facts[0]["comment_only"] is False and (facts[0]["added"], facts[0]["removed"]) == (2, 1)


def test_comment_only_bash_sed_is_unknown(box):
    """CHAIN_COMMENT_ONLY_RECORDED 紅案例：Bash sed 改檔 → unknown（說不出改了哪些檔、也沒有前後內容）。"""
    assert wc.edit_facts("Bash", {"command": "sed -i 's/a/b/' a.py"}, {"stdout": ""}) == []
    t = Turn(box)
    t.gate("A")
    t.bash("sed -i 's/a/b/' a.py", files=[{"path": str(box / "proj" / "a.py"), "comment_only": None}])
    act = t.chain().steps[0].actions[0]
    assert act["files"][0]["comment_only"] is None and act["what"] == "sed -i 's/a/b/' a.py"


def test_comment_only_step_still_counts(box):
    """反例（CHAIN_COMMENT_ONLY_RECORDED）：comment_only=true 的那步照常算進連鎖邊、次數與深度；表上標「（只改註解）」。"""
    t, x = Turn(box, cfg=DEPTH), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.gate("A")
    t.edit(x, "x = 1", "x = 1  # 第一次")
    t.gate("B")
    t.edit(x, "  # 第一次", "  # 第二次")
    r = t.gate("C")
    ch = t.chain()
    assert [a["files"][0]["comment_only"] for s in ch.steps for a in s.actions] == [True, True]
    assert (ch.count, ch.depth) == (2, 2) and r.notice and "（只改註解）" in r.notice


@pytest.mark.parametrize("path, before, after, want", [
    ("a.js", "let a = 1;\n", "// 說明\nlet a = 1; /* 尾 */\n", True),
    ("a.js", 'let u = "http://x";\n', 'let u = "http://y";\n', False),           # 字串裡的 // 不是註解
    ("a.js", "let r = /\"/g;\n", "let r = /\"/g; // 引號正規式\n", True),
    ("a.js", "let a=b+1;\n", "let a = b + 1;\n", True),                            # 只改空白
    ("a.js", "return x;\n", "returnx;\n", False),                                  # 字詞黏起來是改到程式
    ("a.ts", "const t = `a ${b} // c`;\n", "const t = `a ${b} // d`;\n", False),  # 樣板字串
    ("a.cs", 'var p = @"C:\\x\\";\n', 'var p = @"C:\\x\\"; // 路徑\n', True),       # C# 逐字字串
    ("a.cs", 'var s = """\n// 不是註解\n""";\n', 'var s = """\n// 改了\n""";\n', False),
    ("a.sh", "echo $#\n", "echo $# # 參數個數\n", True),
    ("a.sh", 'echo "a # b"\n', 'echo "a # c"\n', False),                           # 引號裡的 #
    ("a.sh", "echo ${#x}\n", "echo ${#y}\n", False),
    ("a.sh", "cat <<EOF\n# 內文\nEOF\n", "cat <<EOF\n# 改了內文\nEOF\n", False),       # heredoc 內文原樣
    ("a.py", "x = 1\n", '"""docstring 也算註解"""\nx = 1\n', True),
    ("a.py", "x = 1\n", 'x = 1\n"""中段的字串不是 docstring"""\n', False),
    ("a.go", "x := 1\n", "x := 1 // c\n", None),                                    # 認不出的語言
    ("a.js", "let s = 'abc\n", "let s = 'abc // x\n", None),                       # 掃到結尾還在字串裡
    ("a.cs", "/* 沒收尾\n", "/* 沒收尾 x\n", None),
    ("a.py", "x = 1\n", "x = 1\x00\n", None),                                       # 二進位
])
def test_comment_only_languages(path, before, after, want):
    """CHAIN_COMMENT_ONLY_RECORDED：Python／JS／C#／bash 的註解語法與字串避開；判不了回 None（unknown）。"""
    assert wc.comment_only(before, after, path) is want


def test_edit_facts_write_and_fragments():
    """edit_facts：Write 新建檔（原本不存在）比空字串；拿不到 originalFile 的 Edit 退回比片段；MultiEdit 逐筆套用。"""
    w = wc.edit_facts("Write", {"file_path": "c:/p/n.py", "content": "# 只有註解\n"}, {"type": "create"})
    assert w == [{"path": "c:/p/n.py", "added": 1, "removed": 0, "comment_only": True}]
    e = wc.edit_facts("Edit", {"file_path": "c:/p/a.py", "old_string": "x = 1", "new_string": "x = 1  # c"}, {})
    assert e[0]["comment_only"] is True
    m = wc.edit_facts("MultiEdit", {"file_path": "c:/p/a.py", "edits": [
        {"old_string": "a = 1", "new_string": "a = 1  # c"}, {"old_string": "b = 1", "new_string": "b = 2"}]},
        {"originalFile": "a = 1\nb = 1\n"})
    assert m[0]["comment_only"] is False and (m[0]["added"], m[0]["removed"]) == (2, 2)


# ─── 接線用的事實：閘名、AI 動作、唯讀指令、只記錄不灌水 ─────────────────

def test_gate_name_from_message_tag():
    """CHAIN_GATE_NAME：取第一個 [Guardian:名稱]／[名稱] 標記；同一道閘兩種寫法同名；認不出用預設名。"""
    assert wc.gate_name("[Guardian:OverviewHub] 要先交定位", "X") == "OverviewHub"
    assert wc.gate_name("[NeedGoal] 題目要掛節點", "X") == wc.gate_name("[Guardian:NeedGoal] 壞了", "X") == "NeedGoal"
    assert wc.gate_name("前言\n[Guardian:SmellGate] 新寫進的病", "X") == "SmellGate"
    assert wc.gate_name("[Workflow Guardian] 2 file(s)", "SyncBlock") == "SyncBlock"
    assert wc.gate_name("沒有標記", "PreToolUse") == "PreToolUse"


@pytest.mark.parametrize("tool, ti, writes, unknown, ran, want", [
    ("Edit", {"file_path": "c:/p/a.py", "old_string": "a = 1", "new_string": "a = 2"}, (), False, False, "edit"),
    ("Bash", {"command": "sed -i s/a/b/ a.py"}, ("c:/p/a.py",), False, False, "edit"),
    ("Bash", {"command": "python gen.py > $OUT"}, (), True, False, "edit"),          # 判不出目標的寫入也算改
    ("Bash", {"command": "python -m pytest -q t.py"}, (), False, True, "rerun"),
    ("Bash", {"command": "git commit -m x"}, (), False, False, "other"),
    ("Bash", {"command": "grep -n x a.py | head -5"}, (), False, False, None),          # 唯讀指令不算動作
    ("mcp__workflow-guardian__atom_write", {}, (), False, False, "card"),
    ("mcp__workflow-guardian__anti_evasion_report", {}, (), False, False, "report"),
    ("mcp__workflow-guardian__need_goal", {"action": "add"}, (), False, False, "goal"),
    ("Agent", {"description": "查 x"}, (), False, False, "other"),
    ("Read", {"file_path": "c:/p/a.py"}, (), False, False, None),
])
def test_action_facts(tool, ti, writes, unknown, ran, want):
    """CHAIN_ACTION_FACTS：哪些工具呼叫算 AI 動作、算哪一種；Bash 改檔記得出路徑就帶 files（comment_only 判不了＝None）。"""
    got = wc.action_of(tool, ti, {}, writes, unknown, ran)
    assert (got[0] if got else None) == want
    if tool == "Bash" and writes:
        assert got[1] == [{"path": "c:/p/a.py", "added": None, "removed": None, "comment_only": None}]


@pytest.mark.parametrize("tool, cmd, want", [
    ("Bash", "cat a.py", True),
    ("Bash", "grep -rn x hooks/ | head -20 && wc -l a.py", True),
    ("Bash", "git status && git diff --stat", True),
    ("Bash", "git -C /c/w log --oneline -5", True),
    ("Bash", "ls -la 2>/dev/null; echo done 2>&1", True),
    ("Bash", "sed -n '1,40p' a.py", True),
    ("Bash", "find . -name '*.py' -newer a.py", True),
    ("Bash", "echo hi > out.txt", False),                     # 寫檔重導向
    ("Bash", "cat a > b", False),
    ("Bash", "sed -i 's/a/b/' a.py", False),
    ("Bash", "sed -n 's/a/b/w out' a.py", False),             # sed 的 w 指令會寫檔
    ("Bash", "find . -name '*.pyc' -delete", False),
    ("Bash", "git commit -m x", False),
    ("Bash", "git branch -D x", False),
    ("Bash", "python -m pytest -q", False),                   # 會跑程式的一律當動手
    ("Bash", "echo $(rm -rf x)", False),                      # 指令替換
    ("Bash", 'echo "a $(touch x)"', False),
    ("Bash", "cat <(ls)", False),
    ("Bash", "sort -o out.txt a.txt", False),
    ("Bash", "sort -oresult.txt input.txt", False),           # codex：短參數黏著輸出檔
    ("Bash", "sort -rno out.txt a.txt", False),
    ("Bash", "sed -n -e p -e wresult.txt input.txt", False),  # codex：第二段腳本寫檔
    ("Bash", "sed -n -f script.sed a.txt", False),
    ("Bash", "rg --pre ./x.sh foo", False),                   # 前處理會跑程式
    ("Bash", "git -c diff.external=./x.sh diff", False),      # 設定覆寫可以叫外部程式
    ("Bash", "git grep -O./x.sh foo", False),
    ("Bash", "date -s 2020-01-01", False),
    ("Bash", "(rm x)", False),
    ("Bash", "echo 'abc", False),                             # 引號沒收尾
    ("PowerShell", "Get-Item (New-Item owned.txt)", False),   # codex：括號裡執行的命令
    ("PowerShell", "Get-ChildItem | ForEach-Object { Remove-Item $_ }", False),
    ("PowerShell", "Get-Content a.py | Select-String x", True),
    ("PowerShell", "Set-Content a.py 'x'", False),
    ("PowerShell", "Get-Content a.py > b.py", False),
])
def test_readonly_shell(tool, cmd, want):
    """CHAIN_HALT_UNTIL_ANSWER 的唯讀指令：白名單讀檔指令、沒有寫檔重導向與指令替換；判不出當動手。"""
    assert wc.readonly_shell(tool, cmd) is want


def test_muted_triggers_do_not_inflate_count(box):
    """CHAIN_COUNT_TRIGGERS／CHAIN_ABORT_RECORD_ONLY：警報後只記錄的不算進次數與深度；同一道閘這一段只記一筆（收尾一再被叫也不灌水）。"""
    t = Turn(box)
    t.gate("A")
    t.act()
    assert t.gate("A").notice
    for _ in range(3):
        assert t.gate("B") == cs.GateResult(True)
        assert t.gate("C", hook="PreToolUse") == cs.GateResult(True)
    ch = t.chain()
    assert [s.row["gate"] for s in ch.steps] == ["A", "A", "B", "C"] and [s.muted for s in ch.steps] == [False, False, True, True]
    assert (ch.count, ch.depth) == (1, 1)                       # A→重跑→A；B、C 只記錄不算
    assert "總共連鎖 1 次、深度 1" in wc.report(ch, t.now) and "（只記錄）" in wc.report(ch, t.now)


def test_session_cleanup_at_session_end(box):
    """SessionEnd：這個 session 的快照資料夾刪掉；別的 session 的快照與連鎖帳只刪 7 天沒動的；這個 session 的帳留著（事後驗收要讀）。"""
    import os
    root, logs = box / "workflow" / "chain-snap", box / "Logs"
    for name in (SID, "other-new", "other-old"):
        (root / name).mkdir(parents=True)
        (root / name / "t1-main-s0-x.snap").write_bytes(b"x")
    logs.mkdir()
    for name in (SID, "other-new", "other-old"):
        (logs / f"chain-{name}.jsonl").write_text("{}\n", encoding="utf-8")
    (logs / "guard-other.jsonl").write_text("{}\n", encoding="utf-8")
    old = 1000.0
    for p in (root / "other-old", logs / "chain-other-old.jsonl", logs / f"chain-{SID}.jsonl", logs / "guard-other.jsonl"):
        os.utime(p, (old, old))
    cs.session_cleanup(SID, now=old + 8 * 86400)
    assert sorted(p.name for p in root.iterdir()) == ["other-new"]
    assert sorted(p.name for p in logs.iterdir()) == sorted([f"chain-{SID}.jsonl", "chain-other-new.jsonl", "guard-other.jsonl"])


# ─── 同一則回覆算同一步（平行送出的工具呼叫） ─────────────────────────────

def test_same_reply_parallel_writes_same_gate_no_alarm(box):
    """紅案例（CHAIN_SAME_BATCH）：同一則回覆平行送五個 Write，三個被同一道閘擋、中間兩個放行改了檔 → 不警報：
    這一批之間不接邊、同閘次數不加 1、放行的改動不算看過擋訊息後的動作；經過表標出它們跟擋同一則回覆送出。"""
    t, proj = Turn(box), box / "proj"
    t.reply("msg_0")
    t.reply("msg_1")
    for k in range(5):
        if k % 2:
            t.write(proj / f"f{k}.py", "x = 1\n")
        else:
            assert t.gate("OverviewHub", hook="PreToolUse") == cs.PASS
    ch = t.chain()
    assert [s.link.rule for s in ch.steps[1:]] == ["CHAIN_SAME_BATCH"] * 2 and ch.depth == 0 and ch.alarm is None
    assert wc.same_count(ch.steps, {"gate": "OverviewHub"}) == 1
    assert {r.get("batch") for r in cs.read_rows(SID) if r["type"] in ("gate", "action")} == {"msg_0"}   # 鍵＝這則之前那則
    assert "跟這一步同一則回覆送出" in wc.report(ch, t.now)


def test_gate0_first_reply_replay_no_alarm_no_halt(box):
    """紅案例（照一則回覆平行 12 個呼叫的實際帳重演，CHAIN_SAME_BATCH）：同一則回覆 12 個呼叫——DataFileAsk 擋、OverviewHub 擋兩次、
    放行兩個 Write、改舊測試閘擋三次、OverviewHub 再擋、後面三個改檔——改前在最後那次 OverviewHub 判「同閘第 2 次」警報、
    後三個被停手；改後不警報、不停手、帳上沒有 halted。"""
    t, proj = Turn(box), box / "proj"
    t.reply("msg_prev")
    t.reply("msg_batch")
    for k, g in enumerate(["DataFileAsk", "OverviewHub", "OverviewHub", "", "", "OldTestDeclare", "OldTestDeclare",
                           "OldTestDeclare", "OverviewHub"]):
        if g:
            assert t.gate(g, hook="PreToolUse") == cs.PASS
        else:
            t.write(proj / f"w{k}.py", "x = 1\n")
    for k in range(3):
        assert cs.halt(SID, 1, "Write", t.inp("PreToolUse"), t.cfg) is None
        t.write(proj / f"late{k}.py", "y = 1\n")
    assert not {"alarm", "notice", "halted"} & set(_kinds(cs.read_rows(SID)))
    ch = t.chain()
    assert ch.depth == 0 and {s.link.rule for s in ch.steps[1:]} == {"CHAIN_SAME_BATCH"}


def test_next_reply_after_block_still_counts_same_gate(box):
    """反例（CHAIN_SAME_BATCH 不吃掉真的連鎖）：第一則被閘擋 → 第二則 AI 看過擋訊息改了檔 → 又被同一道閘擋 → 照舊算同閘第 2 次、警報。"""
    t, proj = Turn(box), box / "proj"
    t.reply("msg_0")
    t.reply("msg_1")
    assert t.gate("OverviewHub", hook="PreToolUse") == cs.PASS
    t.reply("msg_2")
    t.write(proj / "fix.py", "b = 1\n")
    r = t.gate("OverviewHub", hook="PreToolUse")
    assert r.record_only and r.halt and _alarm_rules(t) == {"CHAIN_ALARM_SAME_GATE"}
    assert t.chain().steps[1].link.rule == "CHAIN_EDGE_TIME_ORDER"


def test_verbatim_retry_after_other_action_is_not_second_trigger(box):
    """紅案例（CHAIN_SAME_CALL_RETRY；004 非改 code 題現況1 的形狀）：動資料檔閘擋 Edit README → 下一則 AI 回應別的提示改了目標樹
    → 原封不動重送同一個 Edit 又被擋 → 原樣重試：不算同閘第 2 次、不接邊、不警報（交回閘自己的擋次上限）。
    舊碼只看中間有沒有動作，重送那次就警報（無頭情境下警報讓這一回合其餘的閘只記錄，該宣告的改動就沒宣告過了）。"""
    t, readme = Turn(box), str(box / "proj" / "ops" / "README.md")
    edit = ("Edit", {"file_path": readme, "old_string": "舊說明", "new_string": "新說明"})
    t.reply("msg_0")
    t.reply("msg_1")
    assert t.gate("DataFileAsk", hook="PreToolUse", call=edit, watched=[readme]) == cs.PASS
    t.reply("msg_2")
    t.goal("set")
    assert t.gate("DataFileAsk", hook="PreToolUse", call=edit, watched=[readme]) == cs.PASS
    ch = t.chain()
    assert ch.steps[1].link.rule == "CHAIN_SAME_CALL_RETRY" and ch.alarm is None
    assert wc.same_count(ch.steps, {"gate": "DataFileAsk", "watched": [readme], "call": ch.steps[1].row["call"]}) == 1


def test_verbatim_retry_across_another_gate_does_not_link(box):
    """CHAIN_SAME_CALL_RETRY 不只跟前一步比（codex 一輪 BLOCK 2）：A 擋 Edit x → 動手 → B 擋另一個呼叫 → 動手 → 原封不動重送 x 又被 A 擋
    → 不接在 B 後面、深度不加、不算 A 第 2 次；深度警報打開也不中止。舊判法接在 B 後面成深度 2 而警報。"""
    t, f = Turn(box, cfg=DEPTH), str(box / "proj" / "a.py")
    x = ("Edit", {"file_path": f, "old_string": "a = 1", "new_string": "a = 2"})
    y = ("Edit", {"file_path": f, "old_string": "b = 1", "new_string": "b = 2"})
    t.reply("m0")
    t.reply("m1")
    t.gate("A", hook="PreToolUse", call=x, watched=[f])
    t.reply("m2")
    t.goal("set")
    t.gate("B", hook="PreToolUse", call=y, watched=[f])
    t.reply("m3")
    t.goal("add")
    assert t.gate("A", hook="PreToolUse", call=x, watched=[f]) == cs.PASS
    ch = t.chain()
    assert ch.steps[2].link.rule == "CHAIN_SAME_CALL_RETRY" and ch.steps[2].depth == 0 and ch.alarm is None


def test_changed_call_after_action_still_counts_second_trigger(box):
    """反例（CHAIN_SAME_CALL_RETRY 不吃掉真的連鎖）：擋 → AI 動手 → 改了內容（或在指令開頭補了宣告，呼叫變了）再送又被擋
    → 照舊算同閘第 2 次、警報；原樣重試夾在中間不改變這個結果。"""
    t, readme = Turn(box), str(box / "proj" / "ops" / "README.md")
    edit = ("Edit", {"file_path": readme, "old_string": "舊說明", "new_string": "新說明"})
    t.reply("msg_0")
    t.reply("msg_1")
    t.gate("DataFileAsk", hook="PreToolUse", call=edit, watched=[readme])
    t.reply("msg_2")
    t.goal("set")
    t.gate("DataFileAsk", hook="PreToolUse", call=edit, watched=[readme])            # 原樣重試：不算
    t.reply("msg_3")
    t.goal("add")
    changed = ("Edit", {**edit[1], "new_string": "新說明（改寫）"})
    r = t.gate("DataFileAsk", hook="PreToolUse", call=changed, watched=[readme])
    assert r.record_only and r.halt and _alarm_rules(t) == {"CHAIN_ALARM_SAME_GATE"}
    u = Turn(box, turn=2)
    bash = ("Bash", {"command": "echo x > ops/README.md"})
    u.reply("m0")
    u.reply("m1")
    u.gate("DataFileAsk", hook="PreToolUse", call=bash, watched=[readme])
    u.reply("m2")
    u.act()
    declared = ("Bash", {"command": "# 動資料檔｜ops/README.md：\necho x > ops/README.md"})   # 補了宣告（寫錯了閘照擋）
    assert u.gate("DataFileAsk", hook="PreToolUse", call=declared, watched=[readme]).halt


def test_same_reply_edits_are_not_reactions(box):
    """反例的另一半（CHAIN_SAME_BATCH、CHAIN_SAME_GATE_NO_ACTION）：第一則被擋、同一則裡放行的改檔不算 AI 的反應 →
    第二則一開頭又撞同一道閘（中間沒有看過擋訊息後的動作）→ 不算同閘第 2 次、不警報。"""
    t, proj = Turn(box), box / "proj"
    t.reply("msg_0")
    t.reply("msg_1")
    t.gate("OverviewHub", hook="PreToolUse")
    t.write(proj / "same.py", "a = 1\n")
    t.reply("msg_2")
    assert t.gate("OverviewHub", hook="PreToolUse") == cs.PASS
    assert t.chain().steps[1].link.rule == "CHAIN_SAME_GATE_NO_ACTION" and t.chain().alarm is None


def test_batch_links_to_deepest_step_of_previous_reply(box):
    """CHAIN_SAME_BATCH／CHAIN_ALARM_DEPTH：A 擋（第一則）→ 第二則改檔後 B、C 同一批被擋（都跟 A 比；C 看的檔跟改的檔沒交集，不接）
    → 第三則改檔後 D 擋：接在第二則最深的 B 上，深度 2 警報（只跟前一步 C 比會算成深度 1；改前則在 C 就誤判深度 2）。深度警報打開。"""
    t, x = Turn(box, cfg=DEPTH), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.reply("m0")
    t.reply("m1")
    t.gate("A", hook="PreToolUse")
    t.reply("m2")
    t.edit(x, "x = 1", "x = 2")
    t.gate("B", hook="PreToolUse")
    assert t.gate("C", hook="PreToolUse", watched=[str(box / "proj" / "other.py")]) == cs.PASS
    assert [(s.link.rule, s.depth) for s in t.chain().steps[1:]] == [("CHAIN_EDGE_TIME_ORDER", 1),
                                                                      ("CHAIN_EDGE_FILES_DISJOINT", 0)]
    t.reply("m3")
    t.edit(x, "x = 2", "x = 3")
    r = t.gate("D", hook="PreToolUse")
    assert r.halt and _alarm_rules(t) == {"CHAIN_ALARM_DEPTH"}


def test_stop_after_batch_sees_only_reactions(box):
    """CHAIN_SAME_BATCH × CHAIN_NO_FIX_NO_EDGE（行為照規則、不退回舊判法）：工具閘 A 擋、同一則回覆裡放行一個改檔
    → AI 下一則就收尾、收尾閘 B 擋：收尾不帶 batch，但一定在那一批之後；那個改檔是 A 擋之前就決定好的，不算 A 之後的修補 → 不接邊。
    改前把它當成 A 之後的動作，接成 A→B。"""
    t, proj = Turn(box), box / "proj"
    t.reply("m0")
    t.reply("m1")
    t.gate("A", hook="PreToolUse")
    t.write(proj / "same.py", "a = 1\n")
    t.reply("m2")
    assert t.gate("B") == cs.PASS
    s = t.chain().steps[1]
    assert (s.link.rule, s.depth) == ("CHAIN_NO_FIX_NO_EDGE", 0) and "batch" not in s.row


def test_batch_unknown_falls_back_and_is_recorded(box):
    """CHAIN_SAME_BATCH 判不出就照舊接邊並留帳：transcript 的 assistant 沒有 message.id → 閘擋 → 改檔 → 同一道閘再擋，照舊警報；
    每筆工具上的觸發與動作記 batch 空值與 batch_why。"""
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.say()
    t.gate("A", hook="PreToolUse")
    t.edit(x, "x = 1", "x = 2")
    assert t.gate("A", hook="PreToolUse").halt and _alarm_rules(t) == {"CHAIN_ALARM_SAME_GATE"}
    rows = [r for r in cs.read_rows(SID) if r["type"] in ("gate", "action")]
    assert rows and all(r["batch"] == "" and r["batch_why"] == "前一則 assistant 沒有 message.id" for r in rows)


def test_batch_key_from_transcript(box):
    """CHAIN_SAME_BATCH 的批次鍵（chain_store._batch）：這次 tool_use 已落盤 → 從那行往前找 message.id 不同的那則（同一則後面的行、
    api-request 這類別種紀錄裡的同一個 id、子代理寫進來的 isSidechain 行都不算）；還沒落盤 → 最後一則 assistant；子代理、讀不到、
    還沒有 assistant 判不出；收尾不帶。"""
    tp = box / "tp.jsonl"
    _jl(tp, {"type": "user", "message": {"content": "做"}})
    d = {"tool_use_id": "tu_b", "transcript_path": str(tp)}
    assert cs._batch(d) == ("", "transcript 上還沒有前一則 assistant")
    _jl(tp, {"type": "assistant", "message": {"id": "m0", "content": [{"type": "text", "text": "看"}]}})
    assert cs._batch(d) == ("m0", "")
    for tid in ("tu_a", "tu_b", "tu_c"):
        _jl(tp, {"type": "assistant", "message": {"id": "m1", "content": [{"type": "tool_use", "id": tid, "name": "Write"}]}})
        _jl(tp, {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid}]}})
    _jl(tp, {"type": "api-request-blob", "content": [{"type": "tool_use", "id": "tu_next"}]})
    _jl(tp, {"type": "assistant", "isSidechain": True, "message": {"id": "sub1", "content": [{"type": "text", "text": "子代理"}]}})
    assert cs._batch(d) == ("m0", "") and cs._batch({**d, "tool_use_id": "tu_c"}) == ("m0", "")
    assert cs._batch({**d, "tool_use_id": "tu_next"}) == ("m1", "")
    assert cs._batch({**d, "agent_id": "ag"})[0] == "" and cs._batch({**d, "transcript_path": str(box / "nope")})[0] == ""
    assert cs._batch_fields({"transcript_path": str(tp)}) == {}


# ─── 同一道閘照擋的對象計數 ───────────────────────────────────────────────

ORD, TST, CLI = "c:/w/shop|訂單結帳", "c:/w/shop|測試", "c:/w/shop|命令列"


def test_same_gate_three_parts_each_once_no_alarm(box):
    """紅案例（CHAIN_SAME_GATE_PER_OBJECT）：定位閘先後擋三個不同部位、每次之間 AI 都改了檔 → 不響：每個部位各要一份定位，
    第 1 次補的沒讓後面多欠什麼，三次都是各自部位的第 1 次；經過表每一筆列出擋的部位。改前第 2 次就判同閘第 2 次警報。"""
    t, proj = Turn(box), box / "proj"
    for k, part in enumerate((ORD, TST, CLI)):
        assert t.gate("OverviewHub", hook="PreToolUse", target=part, watched=[str(proj / f"f{k}.py")]) == cs.PASS
        t.write(proj / f"f{k}.py", "x = 1\n")
    ch = t.chain()
    assert ch.alarm is None and [s.row["same"] for s in ch.steps] == [1, 1, 1]
    table = wc.report(ch, t.now)
    for k, part in enumerate(("訂單結帳", "測試", "命令列")):
        assert f"| {k + 1} | OverviewHub | {part} |" in table


def test_same_gate_same_part_twice_alarms(box):
    """紅案例（CHAIN_SAME_GATE_PER_OBJECT × CHAIN_ALARM_SAME_GATE）：定位閘擋同一個部位兩次、中間 AI 改了檔 → 響（繞回原點）；
    兩次擋的檔不同也一樣（對象是部位）。警報句寫出擋的部位。"""
    t, proj = Turn(box), box / "proj"
    t.gate("OverviewHub", hook="PreToolUse", target=ORD, watched=[str(proj / "pricing.py")])
    t.write(proj / "notes.py", "x = 1\n")
    r = t.gate("OverviewHub", hook="PreToolUse", target=ORD, watched=[str(proj / "checkout.py")])
    assert r.halt and _alarm_rules(t) == {"CHAIN_ALARM_SAME_GATE"}
    assert "OverviewHub（擋 訂單結帳）這一段第 2 次觸發" in r.halt


def test_part_a_b_back_to_a_alarms_on_a(box):
    """紅案例：部位 A → 改檔 → 部位 B → 改檔 → 又回到部位 A → A 第 2 次響（中間的動作接在別的對象後面也算）。"""
    t, proj = Turn(box), box / "proj"
    assert t.gate("OverviewHub", hook="PreToolUse", target=ORD) == cs.PASS
    t.write(proj / "a.py", "a = 1\n")
    assert t.gate("OverviewHub", hook="PreToolUse", target=TST) == cs.PASS
    t.write(proj / "b.py", "b = 1\n")
    assert t.gate("OverviewHub", hook="PreToolUse", target=ORD).halt
    assert [s.row["same"] for s in t.chain().steps] == [1, 1, 2]


def test_gate_without_object_still_counts_by_name(box):
    """紅案例：說不出對象的閘（版控口令、收尾閘這類）擋兩次、中間有動作 → 照舊響；同一道閘一次報了部位、一次沒報（例如閘環境出錯），
    或一次報部位、一次只報檔，比不了 → 照閘名算第 2 次。"""
    t = Turn(box)
    t.gate("CommitOrder", hook="PreToolUse")
    t.act()
    assert t.gate("CommitOrder", hook="PreToolUse").halt and _alarm_rules(t) == {"CHAIN_ALARM_SAME_GATE"}
    for turn, last in ((2, {}), (3, {"watched": [str(box / "proj" / "x.py")]})):
        u = Turn(box, turn=turn)
        u.gate("OverviewHub", hook="PreToolUse", target=ORD)
        u.act()
        assert u.gate("OverviewHub", hook="PreToolUse", **last).halt
    v = Turn(box, turn=4)
    v.gate("TestFailGate")
    v.act()
    assert v.gate("TestFailGate").notice                                    # 收尾閘照閘名


def test_blocked_files_as_object(box):
    """CHAIN_SAME_GATE_PER_OBJECT（擋的檔當對象，動資料檔、改舊測試）：擋 a.json → 改 → 擋 b.json → 不響；
    再擋 c.json 加 B.JSON（大小寫不同也是同一個檔）→ 跟 b.json 那次有交集 → 響。"""
    t, proj = Turn(box), box / "proj"
    a, b = proj / "a.json", proj / "b.json"
    assert t.gate("DataFileAsk", hook="PreToolUse", watched=[str(a)]) == cs.PASS
    t.write(a, "{}\n")
    assert t.gate("DataFileAsk", hook="PreToolUse", watched=[str(b)]) == cs.PASS
    t.write(b, "{}\n")
    assert t.gate("DataFileAsk", hook="PreToolUse", watched=[str(proj / "c.json"), str(b).upper()]).halt
    assert [s.row["same"] for s in t.chain().steps] == [1, 1, 2]
    row1 = next(ln for ln in wc.report(t.chain(), t.now).splitlines() if ln.startswith("| 1 | DataFileAsk | "))
    assert "/proj/a.json | DataFileAsk：缺東西 |" in row1


def test_redo_first_turn_replay_parts_no_alarm(box):
    """紅案例（照一般改碼任務第 1 回合的實際帳重演，CHAIN_SAME_GATE_PER_OBJECT）：第 1 則一次寫 pricing／checkout（定位閘擋
    【訂單結帳】兩筆）、receipt／cli 放行、shop.json 被動資料檔閘擋；第 2 則只讀檔；第 3 則原樣重寫（定位閘【訂單結帳】又擋兩筆、
    動資料檔閘再擋）；第 4 則 Bash 交定位；第 5 則改 pricing／checkout／shop.json 放行；第 6 則改三支舊測試（改舊測試閘各擋一支）、
    新增 test_receipt.py 被定位閘擋【測試】。改前最後那筆判 OverviewHub 同閘第 2 次警報、之後的工具停手；
    改後【測試】是這個部位的第 1 次 → 不響、不停手。"""
    t, proj = Turn(box), box / "proj"
    o, ts, shop = proj / "orders", proj / "tests", proj / "config" / "shop.json"

    def hub(part, f):
        return t.gate("OverviewHub", hook="PreToolUse", target=part, watched=[str(f)])

    def data():
        return t.gate("DataFileAsk", hook="PreToolUse", watched=[str(shop)])
    t.reply("m0")
    t.reply("m1")
    assert hub(ORD, o / "pricing.py") == cs.PASS and hub(ORD, o / "checkout.py") == cs.PASS
    t.write(o / "receipt.py", "r = 1\n")
    t.write(o / "cli.py", "c = 1\n")
    assert data() == cs.PASS
    t.reply("m2")                                                   # 只讀檔：不是動作
    t.reply("m3")
    assert hub(ORD, o / "pricing.py") == cs.PASS and hub(ORD, o / "checkout.py") == cs.PASS and data() == cs.PASS
    t.reply("m4")
    t.bash("# 定位｜部位：訂單結帳——pricing.py 加 discount()", kind="other")
    t.reply("m5")
    for f in (o / "pricing.py", o / "checkout.py", shop):
        t.write(f, "x = 2\n")
    t.reply("m6")
    for name in ("test_pricing.py", "test_checkout.py", "test_erp_contract.py"):
        assert t.gate("OldTestDeclare", hook="PreToolUse", watched=[str(ts / name)]) == cs.PASS
    assert hub(TST, ts / "test_receipt.py") == cs.PASS
    assert cs.halt(SID, 1, "Write", t.inp("PreToolUse"), t.cfg) is None
    assert not {"alarm", "notice", "halted"} & set(_kinds(cs.read_rows(SID)))
    assert max(s.row["same"] for s in t.chain().steps) == 1


def _run_temp(monkeypatch, path: Path) -> None:
    """模擬 root conftest 在一次 pytest 開始時換的暫存目錄（TMPDIR／TEMP／TMP，子行程繼承）。"""
    path.mkdir(parents=True, exist_ok=True)
    for k in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(k, str(path))


def test_test_root_is_per_run_and_shared_with_child_process(monkeypatch, tmp_path):
    """chain_store._test_root：Logs 目錄跨次執行固定（WG_TEST_LOGS_DIR）時，同一案每一次執行（每次 pytest 換一個暫存目錄，同一個行程
    再跑一次 pytest.main 也換）各一份帳——上一次執行留下的觸發看不到；同一次執行裡開的子行程（走真 hook 入口的案）繼承環境變數、
    跟案例共用同一份，子行程比案例先用到也一樣。改前只按案例名分，同一案第二次跑讀到上一次的帳。"""
    monkeypatch.setenv("WG_TEST_LOGS_DIR", str(tmp_path / "logs"))
    _run_temp(monkeypatch, tmp_path / "run1")
    child = subprocess.run([sys.executable, "-c", "import sys; sys.path[:0] = sys.argv[1:3]; import chain_store; "
                            "print(chain_store._test_root())", str(HOOKS_DIR.parent / "lib"), str(HOOKS_DIR)],
                           capture_output=True, text=True, encoding="utf-8")       # 子行程先用到
    first = cs._test_root()
    assert first is not None and child.stdout.strip() == str(first), child.stderr
    tp = tmp_path / "t.jsonl"
    tp.touch()
    cs.gate_fired(SID, 1, "A", "A：缺東西", {"hook_event_name": "Stop", "transcript_path": str(tp), "session_id": SID}, ON, now=1.0)
    assert cs.ledger_path(SID).parent == first and len(cs.read_rows(SID)) == 1
    _run_temp(monkeypatch, tmp_path / "run2")                    # 下一次執行
    second = cs._test_root()
    assert second != first and second.parent.parent == first.parent.parent and cs.read_rows(SID) == []


# ─── 規則表契約 ─────────────────────────────────────────────────────────

def test_every_rule_has_a_case():
    """放行／欠帳判定契約：每條 RULES 至少一個案例點名它。"""
    src = Path(__file__).read_text(encoding="utf-8")
    body = src.split("def test_every_rule_has_a_case", 1)[0]
    assert [r for r in wc.RULES if r not in body] == []
    assert wc.OPT_RELEASE == wg_release.OPT_RELEASE and re.search(r"【[^】]+】", wc.CHAIN_TAG)


if __name__ == "__main__":
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("CHAIN_BREAKER_CHECK PASS" if rc == 0 else "CHAIN_BREAKER_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
