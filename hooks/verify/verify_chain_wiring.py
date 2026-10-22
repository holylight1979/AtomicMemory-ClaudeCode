"""verify_chain_wiring.py — 連鎖斷路器接到各 hook 之後的行為案例（收尾 handlers/stop.py、工具前 handlers/pre_tool_use.py、
工具後 handlers/post_tool_use.py、SessionEnd 清快照）。

做什麼：走真的 handler 入口模擬一個使用者回合——收尾閘擋（知識收割、收割對帳的判定換成可控的開關）、工具前閘擋（動資料檔閘的判定換成
開關）、AI 改檔（工具前放行才寫、工具後記動作）——驗：深度 2 與同一道閘第 2 次會中止、中止後其餘閘只記錄、工具先停手只准讀與問、
收尾送三選項、headless 不問人不還原、選還原只還原連鎖段、選繼續歸零再問、選放行同時放行既有閘（紅測閘記成使用者放行）、
子代理收尾第 2 次改送中止通知、失敗的重跑也記成動作、只改註解記 comment_only；
反例：沒有連鎖（擋一次、修一次、過）時，每一步的輸出跟關掉斷路器一模一樣。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_chain_wiring.py
       python -X utf8 hooks/verify/verify_chain_wiring.py   （直接跑，尾行 CHAIN_WIRING_CHECK PASS／FAIL）
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import wg_core  # noqa: E402
import chain_store as cs  # noqa: E402
import wg_chain as wc  # noqa: E402
import wg_data_file  # noqa: E402
import wg_release  # noqa: E402
from handlers import post_tool_use as post  # noqa: E402
from handlers import pre_tool_use as ptu  # noqa: E402
from handlers import stop as st  # noqa: E402

KH = "[Guardian:KnowledgeHarvest] 宣告完成：先把值得留的 atom_write，再呼叫 knowledge_harvest_report"
HP = "[Guardian:Harvest-Pending] 收割回報有 1 項對不上收據"
DF = "[Guardian:DataFileAsk] 動到使用者的資料檔，先寫「動資料檔｜<路徑>：<為什麼>」"


class Out(Exception):
    """handler 的輸出：wg_core 的 output_json／output_nothing 換成丟這個，跟真的一樣在出口結束這次 hook。"""


def _jl(path: Path, obj) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _blocked(out) -> bool:
    return bool(out) and out.get("decision") == "block"


def _denied(out) -> bool:
    return bool(out) and (out.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"


def _deny_text(out) -> str:
    return (out.get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")


class Session:
    """一個 session 的一個使用者回合：收尾、工具前、工具後都走真的 handler；閘的判定由 gates 開關決定。"""

    def __init__(self, root: Path, monkeypatch, sid: str, chain_on: bool = True):
        self.sid, self.root = sid, root
        self.proj = root / sid / "proj"
        self.proj.mkdir(parents=True)
        self.tp = root / sid / "transcript.jsonl"
        self.tp.touch()
        self.n = 0
        self.gates = {"KnowledgeHarvest": False, "Harvest-Pending": False, "DataFileAsk": False}
        self.picks = []
        self.cfg = copy.deepcopy(wg_core.load_config())
        self.cfg.setdefault("chain_breaker", {})["enabled"] = chain_on
        wg_core.write_state(sid, {"session": {"id": sid, "cwd": str(self.proj)}, "turn_seq": 1, "turn_prompts_seq": 1,
                                  "phase": "working"})
        gates = self.gates
        monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: KH if gates["KnowledgeHarvest"] else None)
        monkeypatch.setattr(st, "pending_gate_reason", lambda *a, **k: HP if gates["Harvest-Pending"] else None)
        monkeypatch.setattr(st, "background_on", lambda cfg: False)
        monkeypatch.setattr(st, "_pick_one_prompt", lambda *a, **k: self.picks.append(1))
        monkeypatch.setattr(wg_data_file, "gate", lambda *a, **k: DF if gates["DataFileAsk"] else None)

    def inp(self, hook: str, **kw):
        self.n += 1
        return {"hook_event_name": hook, "session_id": self.sid, "transcript_path": str(self.tp), "cwd": str(self.proj), **kw}

    @staticmethod
    def _run(fn, d, cfg):
        """跑一次 hook，回它的輸出（dict；什麼都沒送＝None）。沒換到的出口（模組自己綁了 wg_core 的輸出函式）照真的印 JSON、sys.exit，
        從 stdout 讀回來。"""
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                fn(d, cfg)
        except Out as e:
            return e.args[0]
        except SystemExit:
            lines = buf.getvalue().strip().splitlines()
            return json.loads(lines[-1]) if lines else None
        return None

    def stop(self, text: str = "全部完成。"):
        _jl(self.tp, {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})
        return self._run(st.handle_stop, self.inp("Stop", last_assistant_message=text), self.cfg)

    def pre(self, tool: str, ti, tid: str = ""):
        return self._run(ptu.handle_pre_tool_use, self.inp("PreToolUse", tool_name=tool, tool_input=ti,
                                                           tool_use_id=tid or f"tu{self.n}"), self.cfg)

    def write(self, path: Path, text: str):
        """AI 用 Write 改一個檔：工具前放行才真的寫，寫完走工具後；回工具前的輸出。"""
        ti = {"file_path": str(path), "content": text}
        tid = f"w{self.n}"
        out = self.pre("Write", ti, tid)
        if _denied(out):
            return out
        before = path.read_text(encoding="utf-8") if path.exists() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        resp = {"type": "create", "filePath": str(path), "content": text} if before is None else \
            {"type": "update", "filePath": str(path), "content": text, "originalFile": before}
        self._run(post.handle_post_tool_use, self.inp("PostToolUse", tool_name="Write", tool_input=ti, tool_response=resp,
                                                      tool_use_id=tid), self.cfg)
        return out

    def answer(self, choice: str):
        """使用者在 AskUserQuestion 選了 choice（transcript 照 CC 的格式寫 tool_use 與對到 id 的 tool_result）。"""
        q = wc.question(self.chain())
        tid = f"ask{self.n}"
        _jl(self.tp, {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": tid, "name": "AskUserQuestion",
             "input": {"questions": [{"question": q, "header": "連鎖", "multiSelect": False,
                                      "options": [{"label": o} for o in wc.CHOICES]}]}}]}})
        _jl(self.tp, {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid, "content": f'User has answered your questions: "{q}"="{choice}".'}]},
            "toolUseResult": {"answers": {q: choice}}})

    def chain(self):
        return wc.fold(cs.read_rows(self.sid), 1, "")


@pytest.fixture()
def hk(tmp_path, monkeypatch):
    def out_json(data):
        raise Out(data)

    def out_nothing():
        raise Out(None)
    for mod in (wg_core, ptu, post):
        monkeypatch.setattr(mod, "output_json", out_json)
        monkeypatch.setattr(mod, "output_nothing", out_nothing)
    # 帳與快照放這一案自己的暫存目錄：chain_store 在 pytest 底下的預設位置按案例名分、跨次執行不清，第二次跑會讀到上一次的帳
    monkeypatch.setattr(cs, "_ledger_dir", lambda: tmp_path / "Logs")
    monkeypatch.setattr(cs, "_snap_root", lambda: tmp_path / "workflow" / "chain-snap")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")         # 互動入口；headless 的案自己改
    monkeypatch.delenv("CLAUDE_COMPANION_JUDGE", raising=False)
    made = []

    def make(sid: str = "sid-wire", chain_on: bool = True) -> Session:
        s = Session(tmp_path, monkeypatch, f"{sid}-{len(made)}", chain_on)
        made.append(s)
        return s
    return make


def _depth2(s: Session):
    """閘A（收尾：知識收割）擋 → 改檔 → 閘B（工具前：動資料檔）擋 → 改檔 → 閘A 第二次。回 (第三次的輸出, 兩個檔)。"""
    x, y = s.proj / "notes.txt", s.proj / "other.txt"
    x.write_text("n = 1\n", encoding="utf-8")
    s.gates["KnowledgeHarvest"] = True
    first = s.stop()
    assert _blocked(first) and KH in first["reason"]                  # 前置：閘A 真的照原樣擋
    assert not _denied(s.write(x, "n = 2\n"))
    s.gates["DataFileAsk"] = True
    out = s.write(y, "o = 1\n")
    assert _denied(out) and _deny_text(out).startswith("[Guardian:DataFileAsk]")   # 前置：閘B 照原樣擋（深度 1 還沒中止）
    s.gates["DataFileAsk"] = False
    assert not _denied(s.write(y, "o = 1\n"))
    return s.stop(), x, y


# ─── 001 紅案例 ─────────────────────────────────────────────────────────

def test_depth2_aborts_rest_record_only_and_tools_halt(hk):
    """紅案例：閘A擋 → 改檔 → 閘B擋 → 改檔 → 閘A第二次 → 中止：收尾送三選項與經過表；之後改檔先停手、唯讀指令照放，
    其餘收尾閘只記錄（同一道閘只記一筆）、不送「順手看到最該修」。"""
    s = hk()
    out, x, y = _depth2(s)
    assert _blocked(out) and out["reason"].startswith("[Guardian:ChainBreaker] 連鎖中止")
    for opt in (wc.OPT_RESTORE, wc.OPT_CONTINUE, wc.OPT_RELEASE):
        assert f"「{opt}」" in out["reason"]
    assert "總共連鎖 2 次、深度 2" in out["reason"] and "DataFileAsk" in out["reason"] and "notes.txt" in out["reason"]
    halt = s.write(y, "o = 9\n")
    assert _denied(halt) and _deny_text(halt).startswith("[Guardian:ChainBreaker] 連鎖中止中")
    assert y.read_text(encoding="utf-8") == "o = 1\n"
    assert s.pre("Bash", {"command": f"cat {x.as_posix()}"}) is None          # 讀照放
    s.gates["Harvest-Pending"] = True
    picks = len(s.picks)
    for _ in range(2):
        again = s.stop()
        assert not _blocked(again) and "還沒收到使用者三選一" in again["systemMessage"]
    assert len(s.picks) == picks
    muted = [r for r in cs.read_rows(s.sid) if r.get("type") == "gate" and r["gate"] in ("KnowledgeHarvest", "Harvest-Pending")]
    assert [(r["gate"], r["record_only"]) for r in muted][-2:] == [("KnowledgeHarvest", True), ("Harvest-Pending", True)]
    assert len(muted) == 4                                                    # 擋、第二次（警報）、只記錄各一筆


def test_same_tool_gate_twice_aborts(hk):
    """紅案例（C1）：同一道工具前閘原樣重試、中間沒動作 → 照那道閘原本的擋（不中止）；AI 動了別的手再撞同一道閘 → 改送中止停手
    （不是原擋訊息），收尾擋一次送經過表。"""
    s = hk()
    f = s.proj / "data.txt"
    s.gates["DataFileAsk"] = True
    assert _deny_text(s.write(f, "a\n")).startswith("[Guardian:DataFileAsk]")
    retry = s.write(f, "a\n")
    assert _denied(retry) and _deny_text(retry).startswith("[Guardian:DataFileAsk]")       # 沒動作：交回閘自己
    s.gates["DataFileAsk"] = False
    assert not _denied(s.write(s.proj / "other.txt", "o\n"))                                # AI 動了手
    s.gates["DataFileAsk"] = True
    second = s.write(f, "a\n")
    assert _denied(second) and _deny_text(second).startswith("[Guardian:ChainBreaker] 連鎖中止")
    assert "DataFileAsk 這一段第 2 次觸發" in _deny_text(second) and not f.exists()
    out = s.stop()
    assert _blocked(out) and "AskUserQuestion" in out["reason"]


def test_headless_aborts_without_asking_or_restoring(hk, monkeypatch):
    """紅案例（C2）：headless 主 session 觸發 → 不叫 AI 問、不停手：其餘閘只記錄、改檔照常、帳上有 alarm；transcript 裡就算有答案
    也不還原不繼續。工具前閘上響的那一次照放，收尾擋一次送表、之後不再擋。"""
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    s = hk()
    out, x, y = _depth2(s)
    assert _blocked(out) and "無法互動" in out["reason"] and "收尾報告" in out["reason"] and "照常" in out["reason"]
    assert "AskUserQuestion" not in out["reason"]
    s.answer(wc.OPT_RESTORE)
    s.gates["KnowledgeHarvest"] = True
    after = s.stop()
    assert not _blocked(after)
    assert x.read_text(encoding="utf-8") == "n = 2\n" and y.read_text(encoding="utf-8") == "o = 1\n"
    assert not _denied(s.write(x, "n = 3\n")) and x.read_text(encoding="utf-8") == "n = 3\n"      # 不停手
    s.gates["DataFileAsk"] = True
    assert not _denied(s.write(y, "o = 2\n"))                                                     # 閘只記錄
    kinds = {r.get("type") for r in cs.read_rows(s.sid)}
    assert "alarm" in kinds and not {"answer", "restore", "reset", "halted"} & kinds
    t = hk("sid-headless-tool")
    f = t.proj / "d.txt"
    t.gates["DataFileAsk"] = True
    assert _denied(t.write(f, "a\n"))
    t.gates["DataFileAsk"] = False
    assert not _denied(t.write(t.proj / "e.txt", "e\n"))
    t.gates["DataFileAsk"] = True
    assert not _denied(t.write(f, "a\n")) and f.exists()                                          # 響的那一次照放
    first = t.stop()
    assert _blocked(first) and first["reason"].startswith("[Guardian:ChainBreaker] 連鎖中止") and not _blocked(t.stop())


def test_restore_puts_back_chain_segment_only(hk):
    """紅案例：選還原 → 連鎖段改過的檔等於快照、連鎖中新建的檔刪掉、連鎖前改的檔不動（快照是工具前那一刻存的）。"""
    s = hk()
    pre = s.proj / "pre.txt"
    assert not _denied(s.write(pre, "p = 1\n"))                   # 連鎖前的正當改動（還沒有閘觸發）
    out, x, y = _depth2(s)
    assert _blocked(out)
    snaps = s.chain().snaps
    assert sorted(Path(p).name for p in snaps) == ["notes.txt", "other.txt"]
    s.answer(wc.OPT_RESTORE)
    after = s.stop()
    assert not _blocked(after) and "已照使用者選擇還原連鎖改動：寫回 1 檔、刪掉連鎖中新建的 1 檔" in after["systemMessage"]
    assert x.read_text(encoding="utf-8") == "n = 1\n" and not y.exists()
    assert pre.read_text(encoding="utf-8") == "p = 1\n"


def test_continue_resets_and_asks_again(hk):
    """紅案例：選繼續 → 計數歸零、閘照常擋（原擋訊息，附上選了繼續的那一段）；同樣額度再超 → 再問一次。"""
    s = hk()
    out, x, _y = _depth2(s)
    assert _blocked(out)
    s.answer(wc.OPT_CONTINUE)
    again = s.stop()
    assert _blocked(again) and again["reason"].startswith(KH) and "使用者選繼續" in again["reason"]
    assert s.chain().segment == 1 and s.chain().count == 0
    assert not _denied(s.write(x, "n = 5\n"))
    third = s.stop()
    assert _blocked(third) and third["reason"].startswith("[Guardian:ChainBreaker] 連鎖中止")
    assert [r.get("type") for r in cs.read_rows(s.sid)].count("notice") == 2


def test_release_also_releases_existing_gate(hk, monkeypatch):
    """選「放行這一回合」→ 這一回合其餘閘只記錄；同一個答案也算既有閘的放行（紅測閘記 user_release，題目帶【收尾放行確認】）。"""
    s = hk()
    logs = []
    real_log = st.append_guard_log
    monkeypatch.setattr(st, "append_guard_log", lambda name, rec: (logs.append((name, rec)), real_log(name, rec)))
    state = wg_core.read_state(s.sid)
    state["failing_tests"] = [{"session_id": s.sid, "cmd": "python -m pytest -q t.py", "summary": "FAILED t.py::test_x",
                               "turn_seq": 1, "at": "2026-10-22T10:00:00"}]
    wg_core.write_state(s.sid, state)
    first = s.stop("修好了，全部完成。")
    assert _blocked(first) and first["reason"].startswith("[Guardian:TestFailGate]")       # 前置：紅測閘照原樣擋
    assert not _denied(s.write(s.proj / "fix.txt", "f\n"))
    second = s.stop("修好了，全部完成。")
    assert _blocked(second) and second["reason"].startswith("[Guardian:ChainBreaker] 連鎖中止")
    assert wg_release.RELEASE_TAG in wc.question(s.chain())
    s.answer(wg_release.OPT_RELEASE)
    third = s.stop("修好了，全部完成。")
    assert not _blocked(third) and "放行這一回合" in third["systemMessage"]
    rel = wg_core.read_state(s.sid)["user_released"][s.sid][st.TF_GATE]
    assert rel["turn"] == 1
    assert any(n == "reconcile" and r.get("event") == "user_release" and r.get("kind") == "testfail" for n, r in logs)


def _abort_by_kh(s: Session):
    """知識收割擋 → AI 改檔 → 知識收割再擋 → 中止（同一道閘第 2 次、中間有動作）。"""
    s.gates["KnowledgeHarvest"] = True
    assert _blocked(s.stop())
    assert not _denied(s.write(s.proj / "kh.txt", "k\n"))
    assert s.stop()["reason"].startswith("[Guardian:ChainBreaker] 連鎖中止")
    s.gates["KnowledgeHarvest"] = False


def test_muted_turn_judgment_leaves_no_blocked_mark(hk):
    """codex：拐彎判斷在中止中被改成只記錄時，閘自己記的「本回合擋過」要放回去；選繼續之後它照常擋一次（舊接法：記號留著 → 不再擋）。"""
    s = hk()
    _abort_by_kh(s)
    state = wg_core.read_state(s.sid)
    state.setdefault("reading_path", {})[s.sid] = {"owed": {"turn": 1, "items": [
        {"kind": "入口", "name": "calc", "keys": ["calc"], "nums": "讀了 9 檔才到入口"}]}}
    wg_core.write_state(s.sid, state)
    muted = s.stop()
    assert not _blocked(muted)
    rows = [r for r in cs.read_rows(s.sid) if r.get("type") == "gate" and r["gate"] == "TurnJudgment"]
    assert rows and rows[-1]["record_only"]                                  # 前置：拐彎判斷真的走到要擋、被改成只記錄
    assert "blocked_turn" not in wg_core.read_state(s.sid)["reading_path"][s.sid]
    s.answer(wc.OPT_CONTINUE)
    again = s.stop()
    assert _blocked(again) and "TURN_JUDGMENT_REQUIRED" in again["reason"]


def test_muted_gate_self_error_still_blocks_once_after_continue(hk, monkeypatch):
    """codex 同類：寫碼查核自己判定出錯（GATE_SELF_ERROR，同一個錯每回合擋一次）在中止中只記錄 → 記號放回；選繼續之後照擋那一次。"""
    s = hk()
    assert not _denied(s.write(s.proj / "a.txt", "a\n"))
    _abort_by_kh(s)
    monkeypatch.setattr(st, "reconcile_gate_parts", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("判不出")))
    muted = s.stop()
    assert not _blocked(muted)
    rows = [r for r in cs.read_rows(s.sid) if r.get("type") == "gate" and r["gate"] == "ReconcileGate"]
    assert rows and rows[-1]["record_only"] and "判定錯誤" in rows[-1]["what"]   # 前置：自己出錯的那一擋真的走到、被改成只記錄
    s.answer(wc.OPT_CONTINUE)
    again = s.stop()
    assert _blocked(again) and "判定錯誤" in again["reason"]


def test_subagent_stop_second_block_is_notice(monkeypatch, tmp_path):
    """子代理收尾：同一道寫碼查核第 2 次擋改送中止通知（不叫它問），第 3 次只記錄放行。"""
    monkeypatch.setattr(cs, "_ledger_dir", lambda: tmp_path / "Logs")      # 帳放這一案自己的暫存目錄（同 hk）
    monkeypatch.setattr(cs, "_snap_root", lambda: tmp_path / "workflow" / "chain-snap")
    state ={"turn_seq": 4, "turn_prompts_seq": 4, "agent_modified_files": {"ag": [{"path": "c:/p/a.py", "session_id": "s-sub"}]}}
    monkeypatch.setattr(st, "read_state", lambda sid: state)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "_verify_gates", lambda *a, **k: ("[Guardian:ReconcileGate] x\n  ✗ (d) OWED", None, "reconcile", None))
    monkeypatch.setattr(st, "entry_note", lambda *a, **k: "")
    outs = []
    monkeypatch.setattr(st, "output_block", lambda msg: outs.append(("block", msg)))
    monkeypatch.setattr(st, "output_nothing", lambda: outs.append(("pass", "")))
    cfg = copy.deepcopy(wg_core.load_config())
    for k in range(3):
        st.handle_subagent_stop({"hook_event_name": "SubagentStop", "session_id": "s-sub", "agent_id": "ag"}, cfg)
        cs.action_done("s-sub", 4, "edit", "Edit", [], {"hook_event_name": "PostToolUse", "session_id": "s-sub",
                                                         "agent_id": "ag", "tool_use_id": f"sub{k}"}, cfg)   # 子代理接著改檔
    kinds = [k for k, _ in outs]
    assert kinds[:2] == ["block", "block"] and kinds[-1] == "pass"
    assert "原擋訊息" in outs[0][1] and outs[1][1].startswith("[Guardian:ChainBreaker] 連鎖中止") and "子代理" in outs[1][1]


def test_halt_covers_mcp_write_tools(hk):
    """settings.json 的 PreToolUse 補掛 MCP 寫入工具之後，停手也擋得到：警報後 atom_write／need_goal 先停手；警報前照常放行。"""
    s = hk()
    ti = {"title": "x", "knowledge": "y"}
    assert not _denied(s.pre("mcp__workflow-guardian__atom_write", ti))
    _abort_by_kh(s)
    for tool in ("mcp__workflow-guardian__atom_write", "mcp__workflow-guardian__atom_retire",
                 "mcp__workflow-guardian__atom_edit_meta", "mcp__workflow-guardian__atom_move", "mcp__workflow-guardian__need_goal"):
        out = s.pre(tool, ti)
        assert _denied(out) and _deny_text(out).startswith("[Guardian:ChainBreaker] 連鎖中止中"), tool


def test_failed_rerun_and_comment_only_are_recorded(hk):
    """工具後：紅掉的重跑（PostToolUseFailure、有結束碼）記成重跑動作；只加一行註解的 Edit 記 comment_only=true，照常算動作。"""
    s = hk()
    s.gates["KnowledgeHarvest"] = True
    assert _blocked(s.stop())
    s._run(post.handle_post_tool_use_failure, s.inp("PostToolUseFailure", tool_name="Bash",
                                                     tool_input={"command": "python -m pytest -q t.py"},
                                                     error="Exit code 1\n1 failed", tool_use_id="f1"), s.cfg)
    code = s.proj / "a.py"
    code.write_text("x = 1\n# smell-ok: 說明\n", encoding="utf-8")
    s._run(post.handle_post_tool_use, s.inp("PostToolUse", tool_name="Edit", tool_use_id="e1",
                                             tool_input={"file_path": str(code), "old_string": "x = 1\n",
                                                         "new_string": "x = 1\n# smell-ok: 說明\n"},
                                             tool_response={"originalFile": "x = 1\n"}), s.cfg)
    acts = [r for r in cs.read_rows(s.sid) if r.get("type") == "action"]
    assert [a["kind"] for a in acts] == ["rerun", "edit"]
    assert acts[1]["files"][0]["comment_only"] is True


def test_session_end_drops_snapshots(hk):
    """SessionEnd：這個 session 的快照資料夾刪掉、7 天沒動的別 session 連鎖帳刪掉；這個 session 的帳留著。"""
    import os
    s = hk()
    _depth2(s)
    snap_dir = cs._snap_dir(s.sid)
    stale = cs.ledger_path("old-session")
    stale.write_text("{}\n", encoding="utf-8")
    os.utime(stale, (1000.0, 1000.0))
    assert snap_dir.is_dir() and any(snap_dir.iterdir()) and cs.ledger_path(s.sid).exists()
    from handlers import session_end
    try:
        session_end.handle_session_end({"hook_event_name": "SessionEnd", "session_id": s.sid, "cwd": str(s.proj)}, s.cfg)
    except (Out, SystemExit):
        pass
    assert not snap_dir.exists() and not stale.exists() and cs.ledger_path(s.sid).exists()


def test_v6_off_same_gate_twice_no_abort(hk, monkeypatch):
    """紅案例（v6 總開關）：v6 關、chain_breaker 開 → 同一道閘擋兩次也不中止，每一步的輸出跟關掉斷路器一模一樣，帳一筆都不寫。"""
    monkeypatch.setenv("WG_V6", "0")

    def run(s: Session):
        s.gates["KnowledgeHarvest"] = True
        outs = [s.stop()]
        outs.append(s.write(s.proj / "n.txt", "n\n"))
        outs.append(s.stop())
        return outs
    on = hk("sid-v6off-on", True)
    got_on = run(on)
    off = hk("sid-v6off-off", False)
    got_off = run(off)
    assert all(_blocked(o) and o["reason"].startswith(KH) for o in (got_on[0], got_on[2]))   # 前置：同閘真的擋了兩次
    assert json.dumps(got_on, ensure_ascii=False, sort_keys=True) == json.dumps(got_off, ensure_ascii=False, sort_keys=True)
    assert not cs.ledger_path(on.sid).exists()


# ─── 001 反例：沒有連鎖時斷路器不介入、既有閘行為一行不變 ───────────────────────

def test_no_chain_outputs_identical_to_breaker_off(hk):
    """反例：閘擋一次 → 改一次 → 過；工具前擋一次 → 改宣告 → 過。開著斷路器與關掉時，每一步的輸出完全相同；帳上沒有警報與通知。"""
    def run(s: Session):
        f = s.proj / "notes.txt"
        f.write_text("n = 1\n", encoding="utf-8")
        outs = []
        s.gates["KnowledgeHarvest"] = True
        outs.append(s.stop())
        s.gates["KnowledgeHarvest"] = False
        outs.append(s.write(f, "n = 2\n"))
        outs.append(s.stop())
        s.gates["DataFileAsk"] = True
        outs.append(s.write(s.proj / "d.txt", "d\n"))
        s.gates["DataFileAsk"] = False
        outs.append(s.write(s.proj / "d.txt", "d\n"))
        outs.append(s.stop())
        return outs
    on = hk("sid-on", True)
    got_on = run(on)
    off = hk("sid-off", False)                    # 閘的開關跟著最後建的那個 session：一個跑完再建下一個
    got_off = run(off)
    assert _blocked(got_on[0]) and _denied(got_on[3])                       # 前置：兩道閘都真的擋過
    assert json.dumps(got_on, ensure_ascii=False, sort_keys=True) == json.dumps(got_off, ensure_ascii=False, sort_keys=True)
    assert not {"alarm", "notice", "halted"} & {r.get("type") for r in cs.read_rows(on.sid)}
    assert not cs.ledger_path(off.sid).exists()


if __name__ == "__main__":
    import subprocess
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("CHAIN_WIRING_CHECK PASS" if rc == 0 else "CHAIN_WIRING_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
