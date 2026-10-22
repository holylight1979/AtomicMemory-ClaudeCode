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


def _jl(path: Path, obj) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


class Turn:
    """一個使用者回合：閘觸發、AI 改檔、收尾、使用者答題都走 chain_store 的公開函式。"""

    def __init__(self, root: Path, turn: int = 1, cfg=None, agent: str = ""):
        self.root, self.turn, self.cfg, self.agent = root, turn, cfg or {}, agent
        self.tp = root / "transcript.jsonl"
        self.tp.touch()
        self.now = 1000.0 * turn
        self.n = 0

    def inp(self, hook: str):
        self.n += 1
        d = {"hook_event_name": hook, "transcript_path": str(self.tp), "session_id": SID}
        if hook in ("PreToolUse", "PostToolUse"):
            d["tool_use_id"] = f"t{self.turn}-tu{self.n}"
        if self.agent:
            d["agent_id"] = self.agent
        return d

    def say(self, text="（回覆）"):
        _jl(self.tp, {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})

    def tick(self, s=5.0):
        self.now += s
        return self.now

    def gate(self, name, hook="Stop", **kw):
        if hook in wc.STOP_HOOKS:
            self.say()
        return cs.gate_fired(SID, self.turn, name, f"{name}：缺東西", self.inp(hook), self.cfg, now=self.tick(), **kw)

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
    assert "總共連鎖 2 次、深度 2" in r.notice
    assert _alarm_rules(t) == {"CHAIN_ALARM_DEPTH", "CHAIN_ALARM_SAME_GATE"}
    assert [s.link.rule for s in t.chain().steps[1:]] == ["CHAIN_EDGE_TIME_ORDER"] * 2
    assert t.gate("C", hook="PreToolUse") == cs.GateResult(True)      # 其餘閘只記錄
    assert t.gate("D") == cs.GateResult(True)                         # 收尾閘也只記錄、不再送通知
    assert t.record_only()
    out = t.stop()
    assert out is not None and not out.block and "還沒收到使用者三選一" in out.text
    assert _kinds(cs.read_rows(SID)).count("notice") == 1


def test_depth2_three_distinct_gates_aborts(box):
    """紅案例（CHAIN_ALARM_DEPTH 單獨）：A → 改 → B → 改 → C，三道閘各一次，深度 2 就中止。"""
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.gate("A")
    t.edit(x, "x = 1", "x = 2")
    t.gate("B", hook="PreToolUse")
    t.edit(x, "x = 2", "x = 3")
    r = t.gate("C")
    assert r.notice and _alarm_rules(t) == {"CHAIN_ALARM_DEPTH"}


def test_same_gate_second_time_aborts_without_edge(box):
    """紅案例（CHAIN_ALARM_SAME_GATE、CHAIN_NO_FIX_NO_EDGE）：工具閘 A 擋 → AI 沒動手就收尾 → 收尾閘 A 又擋：
    沒接成邊、深度 0，照樣中止。"""
    t = Turn(box)
    assert t.gate("A", hook="PreToolUse") == cs.PASS
    r = t.gate("A")
    ch = t.chain()
    assert r.notice and ch.steps[1].link.rule == "CHAIN_NO_FIX_NO_EDGE" and ch.depth == 0
    assert _alarm_rules(t) == {"CHAIN_ALARM_SAME_GATE"}


def test_alarm_on_tool_gate_notes_then_stop_notices_once(box):
    """CHAIN_STOP_NOTICE_ONCE：警報在工具閘上響 → 那次只附一句（不擋）；接著的收尾擋一次送經過表，再之後的收尾不擋。"""
    t = Turn(box)
    t.gate("A", hook="PreToolUse")
    t.gate("B", hook="PreToolUse")
    r = t.gate("A", hook="PreToolUse")
    assert r.record_only and r.notice is None and "先停手" in r.halt and wc.question(t.chain()) in r.halt
    first, second, third = t.stop(), t.stop(), t.stop()
    assert first.block and "連鎖中止" in first.text
    assert not second.block and not third.block
    assert _kinds(cs.read_rows(SID)).count("notice") == 1


def test_headless_main_session_aborts_without_asking(box, monkeypatch):
    """紅案例（CHAIN_HEADLESS_NO_ASK）：headless 主 session 觸發 → 不叫 AI 問、只留帳；transcript 裡就算有答案也不還原、
    不繼續；通知要 AI 在收尾報告寫明。"""
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.gate("A")
    t.edit(x, "x = 1", "x = 2")
    r = t.gate("A")
    assert r.notice and "無法互動" in r.notice and "收尾報告" in r.notice and "沒有還原" in r.notice
    assert "AskUserQuestion" not in r.notice and wc.OPT_RESTORE not in r.notice
    notice = t.chain().notice
    assert notice["interactive"] is False and "headless" in notice["why"]
    t.answer(wc.OPT_RESTORE)
    assert t.stop() is None
    halt = cs.halt(SID, 1, "Edit", t.inp("PreToolUse"), {})
    assert halt and "無法互動" in halt and "不再動手" in halt
    assert x.read_text(encoding="utf-8") == "x = 2\n"
    assert not {"answer", "reset", "restore"} & set(_kinds(cs.read_rows(SID)))
    assert t.record_only()


def test_subagent_has_own_chain_and_is_not_asked(box):
    """CHAIN_SAME_TURN／CHAIN_HEADLESS_NO_ASK：子代理（帶 agent_id）的觸發另算一條鏈、不算進主 session；子代理裡中止也不問人。"""
    main, sub = Turn(box), Turn(box, agent="agent-1")
    main.gate("A")
    r = sub.gate("A", hook="SubagentStop")
    assert r == cs.PASS and main.chain().count == 0
    r = sub.gate("A", hook="SubagentStop")
    assert r.notice and "子代理" in r.notice and "AskUserQuestion" not in r.notice
    assert not main.record_only() and sub.record_only()


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
    assert t.gate("A").notice
    t.answer(wc.OPT_CONTINUE)
    out = t.stop()
    assert not out.block and "歸零" in out.text
    assert not t.record_only()
    assert t.chain().segment == 1 and t.chain().count == 0
    assert t.gate("A") == cs.PASS                     # 新的一段第一次：照擋
    r = t.gate("A")
    assert r.notice and "總共連鎖 1 次" in r.notice
    assert _kinds(cs.read_rows(SID)).count("notice") == 2


def test_release_keeps_record_only_until_next_turn(box):
    """CHAIN_RELEASE_TURN、CHAIN_SAME_TURN：選放行 → 這一回合其餘閘只記錄；下一回合從零起、閘照常擋。"""
    t = Turn(box)
    t.gate("A")
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
    t.gate("A")
    assert cs.before_write(SID, 1, [str(x)], t.inp("PreToolUse"), {}) is None
    assert cs.action_done(SID, 1, "edit", "Edit", [], t.inp("PostToolUse"), {}) is None
    assert wc.canon_path(x) in t.chain().snaps


# ─── 邊的判法 ──────────────────────────────────────────────────────────

def test_same_event_gates_do_not_link(box):
    """CHAIN_SAME_EVENT：同一次收尾裡先後記的兩道閘不接成邊。"""
    t = Turn(box)
    t.say()
    inp = t.inp("Stop")
    cs.gate_fired(SID, 1, "A", "a", inp, {}, now=t.tick())
    cs.gate_fired(SID, 1, "B", "b", inp, {}, now=t.tick())
    ch = t.chain()
    assert ch.steps[1].link.rule == "CHAIN_SAME_EVENT" and ch.depth == 0 and ch.count == 1


def test_previewed_gate_does_not_link(box):
    """CHAIN_EDGE_PREVIEWED：B 已列在 A 擋下時的預覽裡 → A→B 不接；B→C 照接，深度 1 不中止。反例：沒有預覽就深度 2 中止。"""
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\n", encoding="utf-8")
    t.gate("A", later=["B"])
    t.edit(x, "x = 1", "x = 2")
    t.gate("B")
    t.edit(x, "x = 2", "x = 3")
    assert t.gate("C") == cs.PASS
    ch = t.chain()
    assert ch.steps[1].link.rule == "CHAIN_EDGE_PREVIEWED" and ch.depth == 1
    u = Turn(box, turn=2)
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
    t.gate("B")                                              # 沒動手就收尾：不接
    t.edit(x, "x = 1", "x = 2")
    assert t.gate("C", hook="PreToolUse") == cs.PASS
    ch = t.chain()
    assert (ch.count, ch.depth) == (2, 1)
    assert wc.report(ch, t.now).endswith("總共連鎖 2 次、深度 1")


def test_thresholds_from_config(box):
    """門檻放設定可調：max_depth=3、max_same_gate=3 → 深度 2、同閘第 2 次都不中止，到 3 才中止。"""
    cfg = {"chain_breaker": {"max_depth": 3, "max_same_gate": 3}}
    t = Turn(box, cfg=cfg)
    t.gate("A")
    t.gate("B")
    assert t.gate("A") == cs.PASS                             # 深度 2、A 第 2 次
    assert t.gate("C").notice                                 # 深度 3
    assert wc.settings({"chain_breaker": {"max_depth": 0, "enabled": "no"}}) == wc.DEFAULTS


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
    cs.before_write(SID, 1, [str(a)], t.inp("PreToolUse"), cfg)
    assert t.chain().snaps == {}
    t.gate("A")
    paths = [str(a), str(a), str(big), "rel.py", str(c), str(d), str(cs.ledger_path(SID)),
             str(box / "workflow" / "chain-snap" / SID / "x.snap")]
    cs.before_write(SID, 1, paths, t.inp("PreToolUse"), cfg)
    snaps = {Path(p).name: r for p, r in t.chain().snaps.items()}
    assert set(snaps) == {"a.py", "big.bin", "c.py", "d.py"}
    assert snaps["a.py"]["existed"] and snaps["a.py"]["sha256"] and not snaps["a.py"].get("skipped")
    assert "超過 20 位元組" in snaps["big.bin"]["skipped"]
    assert snaps["c.py"]["existed"] is False
    assert "已存滿" in snaps["d.py"]["skipped"]
    assert len([r for r in cs.read_rows(SID) if r["type"] == "snapshot"]) == 4
    t.gate("A")
    t.answer(wg_release.OPT_RELEASE)
    t.stop()
    e = proj / "e.py"
    cs.before_write(SID, 1, [str(e)], t.inp("PreToolUse"), cfg)
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
    assert cs.halt(SID, 1, "Edit", t.inp("PreToolUse"), {}) is None      # 沒警報不介入
    t.gate("A")
    t.gate("A")
    msg = cs.halt(SID, 1, "Edit", t.inp("PreToolUse"), {})
    assert msg and "先停手" in msg and wc.question(t.chain()) in msg and "總共連鎖 1 次" in msg
    for tool in ("Read", "Grep", "AskUserQuestion"):
        assert cs.halt(SID, 1, tool, t.inp("PreToolUse"), {}) is None
    assert cs.halt(SID, 1, "Bash", t.inp("PreToolUse"), {}, readonly=True) is None
    ch = t.chain()
    assert ch.halted == 1 and ch.count == 1                                # 擋下不算閘觸發
    t.answer(wc.OPT_CONTINUE)
    assert cs.halt(SID, 1, "Edit", t.inp("PreToolUse"), {}) is None
    assert t.chain().segment == 1 and not t.record_only()


def test_tripping_alarm_does_not_let_blocked_call_through(box):
    """CHAIN_HALT_UNTIL_ANSWER（codex：故意讓警報響來繞閘）：工具閘 A 擋 → AI 原樣重送 → 第 2 次讓警報響，
    回的不是放行而是 halt（呼叫端照擋）；之後換別的寫入工具也被 halt 擋，閘只記錄換不到動作過關。"""
    t = Turn(box)
    assert t.gate("A", hook="PreToolUse") == cs.PASS                       # 呼叫端照 A 的訊息擋
    r = t.gate("A", hook="PreToolUse")
    assert r.record_only and r.halt                                       # A 不用擋，但 halt 照擋這個呼叫
    for tool in ("Edit", "Write", "Bash", "mcp__x__write"):
        assert cs.halt(SID, 1, tool, t.inp("PreToolUse"), {})


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
    cx = cs._ctx(SID, 1, t.inp("PreToolUse"), {}, None)
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
    cs.before_write(SID, 1, [str(y)], t1.inp("PreToolUse"), {})
    names = sorted(p.name[:3] for p in (box / "workflow" / "chain-snap" / SID).iterdir())
    assert names == ["t1-", "t2-"]


# ─── 經過表 ────────────────────────────────────────────────────────────

def test_report_table_shape(box):
    """回報內容：每步一列——第幾步、哪道閘、擋了什麼（一句）、AI 做了什麼改動（檔與行數）、這一步耗時；最後一句總次數與深度。"""
    t, x = Turn(box), box / "proj" / "x.py"
    x.write_text("x = 1\ny = 1\n", encoding="utf-8")
    t.gate("A")
    t.edit(x, "x = 1\ny = 1", "x = 2\ny = 2\nz = 2")
    t.gate("B")
    r = t.gate("C")
    lines = r.notice.splitlines()
    assert "| 步 | 閘 | 擋了什麼 | AI 接著做了什麼改動 | 耗時 |" in lines
    row1 = next(ln for ln in lines if ln.startswith("| 1 |"))
    assert "| A |" in row1 and "A：缺東西" in row1 and "改 chain-breaker" not in row1
    assert "proj/x.py（+3/−2 行）" in row1 and "| 11 秒 |" in row1      # 閘A 1005 → 閘B 1016
    row2 = next(ln for ln in lines if ln.startswith("| 2 |"))
    assert "（沒記到改動：改寫回覆）" in row2
    assert "| 3 | C | C：缺東西（只記錄） |" in r.notice
    assert "總共連鎖 2 次、深度 2" in lines


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
    t, x = Turn(box), box / "proj" / "x.py"
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


# ─── 規則表契約 ─────────────────────────────────────────────────────────

def test_every_rule_has_a_case():
    """放行／欠帳判定契約：每條 RULES 至少一個案例點名它。"""
    src = Path(__file__).read_text(encoding="utf-8")
    body = src.split("def test_every_rule_has_a_case", 1)[0]
    assert [r for r in wc.RULES if r not in body] == []
    assert wc.OPT_RELEASE == wg_release.OPT_RELEASE and re.search(r"【[^】]+】", wc.CHAIN_TAG)


if __name__ == "__main__":
    import subprocess
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("CHAIN_BREAKER_CHECK PASS" if rc == 0 else "CHAIN_BREAKER_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
