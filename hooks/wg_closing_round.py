"""wg_closing_round — 收尾只跑一輪：收尾要問的東西在收尾前最後一個工具回應就送到，AI 第一次寫收尾就一起寫，不再被 Stop 叫回去重寫。

做什麼（每批工具跑完，hooks/handlers/post_tool_batch.py 呼叫 on_batch；判斷交 AI，程式只管時點）：
  ① 改完程式就起跑：拐彎判斷的背景量測（wg_reading_path.early_start；規則 READING_PATH_EARLY_START，開關 reading_path.early_start）。
  ② 這批有收尾檢核（anti_evasion_report；收尾檢核放最後，交了就是交付邊界）或完整對照（need_goal reconcile：交付時的對照）＝收尾前最後一個工具回應（closing_call），附上：
     - 量好的拐彎判斷結果（到門檻的條目＋那一題；TURN_JUDGMENT_PRE_CLOSE，跟 ① 同一個開關）。還有一批在量就不附，留給 Stop；
     - 「順手看到最該修」該問就附材料、記問過（PICK_ONE_PRE_CLOSE，開關 pick_one.pre_close）：Stop 的 pick_due 看到問過就不再送、
       不再讓對話續跑一輪。
     - 第二意見照 Stop 同一套事實判欠不欠，欠就把 Stop 會擋的那段先附上（SECOND_OPINION_PRE_CLOSE；so_pre_close），並記「這個使用者回合
       交過收尾那批」（wg_second_opinion.mid_question 據此不把這次 Stop 當中途提問）。
  ③ 本 session 開的第二意見 job（start 自己回的 job_id，或收尾等待行寫明的；不掃 job 目錄）從在跑變成跑完 → 附一次「取回、補四行」（SECOND_OPINION_DONE_NOTICE，開關
     second_opinion.auto.background）；Stop 在最後也問同一支（so_done_notice），收尾當下才跑完的照樣接上。
沒走到附著點（沒交收尾檢核、量測還沒好、開關關）→ Stop 照舊送（舊送法原處不動）。v6 總開關關、子代理的批次 → 呼叫端不呼叫。
判準卡照舊接：附著點在 MCP 工具（收尾檢核）回覆之後，路是 mcp_reply（workflow/entrypoints.json 的 E04、E13 登錄了這條路）。
怎麼驗：python -X utf8 -m pytest -q hooks/verify/verify_closing_round.py
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from wg_core import WORKFLOW_DIR, append_guard_log, coding_turn

CLOSING_TOOL_SUFFIX = "__anti_evasion_report"
NEED_GOAL_SUFFIX = "__need_goal"
SO_START_SUFFIX = "__second_opinion_start"
SO_RESULT_SUFFIX = "__second_opinion_result"
SO_JOB_ROOT = WORKFLOW_DIR / "second-opinion"       # 同 tools/second-opinion/run.py 的 job 目錄
SO_FINAL = ("done", "failed", "blocked")             # 同 wg_release_rules.SO_RAN
SO_WATCH = "second_opinion_watch"                    # state 鍵：{sid: {"on", "running": [job], "noticed": [job]}}
SO_NOTICED_MAX = 20
ENTRY_PATH = "mcp_reply"


def pick_pre_close_on(config: Dict[str, Any]) -> bool:
    """開關 pick_one.pre_close（缺＝開；pick_one.enabled 本身要是 true）。"""
    pick = (config or {}).get("pick_one") or {}
    return pick.get("enabled") is True and pick.get("pre_close", True) is not False


def so_background_on(config: Dict[str, Any]) -> bool:
    """開關 second_opinion.auto.background（缺＝開）：開＝start 後不用等、跑完再接上；關＝照舊叫 AI 直接呼叫 result 等結果。"""
    auto = (((config or {}).get("second_opinion") or {}).get("auto")) or {}
    return auto.get("background", True) is not False


def _calls(tool_calls: Any) -> List[Tuple[str, Dict[str, Any]]]:
    out = []
    for c in tool_calls if isinstance(tool_calls, list) else []:
        c = c if isinstance(c, dict) else {}
        inp = c.get("tool_input", c.get("input"))
        out.append((str(c.get("tool_name") or c.get("name") or ""), inp if isinstance(inp, dict) else {}))
    return out


def closing_call(name: str, inp: Dict[str, Any]) -> bool:
    """收尾前最後一個工具回應的認法：收尾檢核（anti_evasion_report），或需求目標樹的完整對照（need_goal action=reconcile；
    need_goal 說明裡它就是交付時的對照）。"""
    return name.endswith(CLOSING_TOOL_SUFFIX) or (name.endswith(NEED_GOAL_SUFFIX) and inp.get("action") == "reconcile")


def _own(state: Dict[str, Any], sid: str) -> List[Dict[str, Any]]:
    return [m for m in state.get("modified_files") or [] if (m or {}).get("session_id", sid) == sid]


def _note(text: str, state: Dict[str, Any], sid: str, config: Dict[str, Any]) -> str:
    """判準卡（切入點契約 §7.10）：照舊送法同一套，問句後面接卡；接不上只少卡、問句照送。"""
    from wg_entrypoint import entry_note, with_note
    return with_note(text, entry_note(text, ENTRY_PATH, session_id=sid, state=state, config=config))


# ─── ② 收尾前附著：拐彎判斷結果、最該修 ─────────────────────────────────────────

def pick_pre_close(state: Dict[str, Any], sid: str, config: Dict[str, Any], input_data: Dict[str, Any]) -> Optional[str]:
    """規則 PICK_ONE_PRE_CLOSE：交收尾檢核或完整對照那批＝交付邊界，「順手看到最該修」該問（wg_harvest.pick_due：上次問過或記過之後又改了程式、
    這個使用者回合還沒問過）就回那一問並記問過；不該問、靜音、連鎖警報後只記錄 → None。判斷出錯只 stderr、不送（Stop 照舊會問）。"""
    if not pick_pre_close_on(config) or state.get("muted"):
        return None
    turn_seq = int(state.get("turn_seq", 0) or 0)
    try:
        import chain_store
        from wg_harvest import mark_pick_asked, pick_due, pick_material, pick_prompt, session_open_tracking
        from wg_need_goal import is_code_path
        from wg_release_rules import user_turn
        code = [m for m in _own(state, sid) if (m or {}).get("path") and is_code_path(m["path"], config)]
        if not pick_due(state, sid, code, True):
            return None
        if chain_store.record_only(sid, user_turn(state, turn_seq), input_data, config):
            print("[Guardian:ChainBreaker] 連鎖中止中：收尾前不送「順手看到最該修」", file=sys.stderr)
            return None
        cwd = str((state.get("session") or {}).get("cwd") or input_data.get("cwd") or "")
        text = pick_prompt(pick_material(list(dict.fromkeys(m["path"] for m in code)), config),
                           session_open_tracking(cwd, sid) if cwd else [])
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:PickOne] 收尾前「最該修」那一問判斷出錯（這次不送，收尾照舊問）：{type(e).__name__}: {e}", file=sys.stderr)
        return None
    mark_pick_asked(state, sid, turn_seq)
    append_guard_log("pick_one", {"session_id": sid, "turn_seq": turn_seq, "event": "asked", "files": len(code), "via": "pre_close"})
    return text


def turn_judgment_pre_close(state: Dict[str, Any], sid: str, config: Dict[str, Any]) -> Optional[str]:
    """規則 TURN_JUDGMENT_PRE_CLOSE：改完程式就起跑量好的結果（到門檻的條目＋那一題）在交收尾檢核或完整對照那批附上，取走後 Stop 不再送；
    欠項照舊由 Stop 的 turn_judgment_note 核對收尾文字。還有一批在量、沒有結果、開關關 → None。"""
    from wg_reading_path import early_start_on, take_early_note
    if not early_start_on(config):
        return None
    text = take_early_note(state, sid)
    if text:
        append_guard_log("reading_path", {"event": "pre_close_sent", "session_id": sid,
                                          "turn_seq": int(state.get("turn_seq", 0) or 0),
                                          "items": [it.get("name") for it in ((((state.get("reading_path") or {}).get(sid))
                                                                               or {}).get("owed") or {}).get("items") or []]})
    return text


def so_pre_close(state: Dict[str, Any], sid: str, config: Dict[str, Any], input_data: Dict[str, Any]) -> Optional[str]:
    """規則 SECOND_OPINION_PRE_CLOSE：收尾那批照 Stop 同一套事實（wg_second_opinion.check，closing＝True、收尾還沒寫）判第二意見欠不欠，
    欠 → 回 Stop 會擋的同一段（owed_message）；不管欠不欠都記這個使用者回合交過收尾那批（PRE_CLOSE）。第二意見設定關、沒人能回答
    （headless、子代理）→ 只記、不判不附（Stop 也不判）。同一個使用者回合已經附過、改檔指紋沒變（收尾分兩批交）→ 不重附。
    改了 state，呼叫端寫回。"""
    import wg_second_opinion as so
    from wg_evasion import read_transcript_tail
    from wg_release import non_interactive_reason
    from wg_release_rules import user_turn
    turn_seq = int(state.get("turn_seq", 0) or 0)
    prev = ((state.get(so.PRE_CLOSE) or {}).get(sid)) or {}
    rec = {"uturn": user_turn(state, turn_seq), "owed": False, "fp": ""}
    state.setdefault(so.PRE_CLOSE, {})[sid] = rec
    tpath = str(input_data.get("transcript_path") or "")
    cfg = so.auto_cfg(config)
    if not cfg.get("enabled", True) or non_interactive_reason(input_data, tpath or None):
        return None
    from pathlib import Path
    v, facts = so.check(state, sid, _own(state, sid), "", read_transcript_tail(Path(tpath)) if tpath else "", config, cfg, True)
    rec.update(owed=bool(v.owed), fp=str(facts.get("fingerprint") or ""))
    again = bool(v.owed and prev.get("owed") and prev.get("uturn") == rec["uturn"] and prev.get("fp") == rec["fp"])
    if facts.get("code_files"):
        append_guard_log("second_opinion", {"event": "pre_close", "session_id": sid, "turn_seq": turn_seq, "owed": v.owed,
                                            "rule": v.rule, "code_files": facts.get("code_files"),
                                            "triggers": facts.get("triggers"), "sent": bool(v.owed and not again)})
    return so.owed_message(v, facts, config) if v.owed and not again else None


# ─── ③ 第二意見跑完接上 ─────────────────────────────────────────────────────────

_JOB_ID_RE = re.compile(r"^\s*job_id:\s*(\d{8}-\d{6}-[0-9a-z]{8}-(?:diagnose|evaluate|stage-review))\s*$", re.M)  # second-opinion.js JOB_ID_RE
TRANSCRIPT_TAIL_BYTES = 1 << 20      # 找 start 回傳只讀 transcript 尾段這麼多


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(x.get("text") or "") for x in content if isinstance(x, dict))
    if isinstance(content, dict):
        return str(content.get("text") or content.get("content") or "")
    return ""


def start_job_ids(tool_calls: Any, transcript_path: str = "") -> List[str]:
    """這批 second_opinion_start 自己回的 job_id：hook 輸入那筆帶 tool_response 就讀它，沒帶就照 tool_use_id 到本 session 的 transcript
    尾段找那筆 tool_result。只認本 session 這次呼叫的回傳，不掃 job 目錄（job_id 裡只有 session 前 8 碼，掃目錄會收進別的 session 的 job）。
    找不到就不看守這個 start（收尾寫了等第二意見｜<job_id> 時 Stop 照樣記進看守）。"""
    want: Dict[str, str] = {}
    out: List[str] = []
    for c in tool_calls if isinstance(tool_calls, list) else []:
        c = c if isinstance(c, dict) else {}
        if not str(c.get("tool_name") or c.get("name") or "").endswith(SO_START_SUFFIX):
            continue
        got = _JOB_ID_RE.findall(_text_of(c.get("tool_response")))
        if got:
            out += got
        elif c.get("tool_use_id"):
            want[str(c["tool_use_id"])] = ""
    if want and transcript_path:
        try:
            with open(transcript_path, "rb") as fh:
                fh.seek(0, 2)
                fh.seek(max(0, fh.tell() - TRANSCRIPT_TAIL_BYTES))
                lines = fh.read().decode("utf-8", "replace").splitlines()
        except OSError as e:
            print(f"[Guardian:SecondOpinion] 讀不到 transcript 找第二意見 job_id（這個 start 不看守）：{e}", file=sys.stderr)
            lines = []
        for ln in lines:
            if not any(tid in ln for tid in want):
                continue
            try:
                blocks = (json.loads(ln).get("message") or {}).get("content") or []
            except ValueError:
                continue
            for b in blocks if isinstance(blocks, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_result" and str(b.get("tool_use_id")) in want:
                    out += _JOB_ID_RE.findall(_text_of(b.get("content")))
    return list(dict.fromkeys(out))


def _job_status(job: str) -> str:
    try:
        return str(json.loads((SO_JOB_ROOT / job / "status.json").read_text(encoding="utf-8")).get("status") or "")
    except (OSError, ValueError):
        return ""                                                      # 還沒寫或寫到一半：當還在跑


def watch_job(state: Dict[str, Any], sid: str, job: str, waited: bool = False) -> None:
    """記下本 session 開的第二意見 job（start 自己回的 job_id，或收尾等待行寫明的 job_id）。
    waited＝收尾寫了「等第二意見｜<job>」：另記進 waited，取回它的那一回合照宣告完成判四行（waited_jobs）。"""
    rec = state.setdefault(SO_WATCH, {}).setdefault(sid, {})
    rec["on"] = True
    if job not in rec.setdefault("running", []) and job not in rec.get("noticed", []):
        rec["running"].append(job)
    if waited and job not in rec.setdefault("waited", []):
        rec["waited"] = (rec["waited"] + [job])[-SO_NOTICED_MAX:]


def waited_jobs(state: Dict[str, Any], sid: str) -> List[str]:
    """規則 SECOND_OPINION_DONE_NOTICE：收尾寫過「等第二意見｜<job>」的 job（wg_second_opinion.check 據此在取回那一回合要四行）。"""
    return list((((state.get(SO_WATCH) or {}).get(sid)) or {}).get("waited") or [])


def so_done_notice(state: Dict[str, Any], sid: str, fetched: Sequence[str] = ()) -> Optional[str]:
    """規則 SECOND_OPINION_DONE_NOTICE：本 session 開的 job 記成在跑之後跑完了（done／failed／blocked），而 AI 還沒取回 → 回一次提醒；
    fetched＝這批（或本回合）已經呼叫 second_opinion_result 取過的 job，跑完了就不再提醒。只看看守裡的 job（watch_job 記的），
    不掃 job 目錄。沒有在看守 → None，不讀任何檔。改了 state（看守紀錄），呼叫端寫回。"""
    rec = ((state.get(SO_WATCH) or {}).get(sid)) or {}
    if not rec.get("on"):
        return None
    running = list(rec.get("running") or [])
    noticed = list(rec.get("noticed") or [])
    done = [(j, st) for j, st in ((j, _job_status(j)) for j in running) if st in SO_FINAL]
    left = [j for j in running if j not in {j for j, _ in done}]
    tell = [(j, st) for j, st in done if j not in set(fetched)]
    rec.update(running=left, noticed=(noticed + [j for j, _ in done])[-SO_NOTICED_MAX:], on=bool(left))
    state.setdefault(SO_WATCH, {})[sid] = rec
    if not tell:
        return None
    append_guard_log("second_opinion", {"event": "done_notice", "session_id": sid, "turn_seq": int(state.get("turn_seq", 0) or 0),
                                        "jobs": [f"{j} {st}" for j, st in tell]})
    return "\n".join(
        f"[Guardian:SecondOpinion] 第二意見 {j} 跑完了（{st}）：呼叫 second_opinion_result({{job_id: \"{j}\"}}) 取回（已跑完，馬上回），"
        "照結果在收尾寫「第二意見與分歧裁決」四行（Codex 結論／我方結論／分歧點／裁決與理由；failed／blocked 也寫明狀態與自己的結論）。"
        for j, st in tell)


# ─── 入口 ───────────────────────────────────────────────────────────────────────

def on_batch(state: Dict[str, Any], sid: str, input_data: Dict[str, Any], config: Dict[str, Any]) -> Tuple[List[str], bool]:
    """PostToolBatch 每批呼叫 → (要附的段落, state 有沒有改)。每段各自 try：一段壞了只少那一段、浮 stderr，其他照送。"""
    calls = _calls(input_data.get("tool_calls"))
    parts: List[str] = []
    changed = False
    coding = coding_turn(state, config)
    if coding:
        from wg_reading_path import early_start, early_start_on
        if early_start_on(config):
            try:
                changed = early_start(state, sid, config) or changed
            except Exception as e:  # noqa: BLE001
                print(f"[Guardian:ReadingPath] 改完程式就起跑的量測出錯（收尾照舊起跑）：{type(e).__name__}: {e}", file=sys.stderr)
    if coding and any(closing_call(n, inp) for n, inp in calls):
        try:
            tj = turn_judgment_pre_close(state, sid, config)
        except Exception as e:  # noqa: BLE001
            tj = None
            print(f"[Guardian:ReadingPath] 收尾前附拐彎判斷出錯（收尾照舊附）：{type(e).__name__}: {e}", file=sys.stderr)
        pick = pick_pre_close(state, sid, config, input_data)
        try:
            so_text = so_pre_close(state, sid, config, input_data)
            changed = True
        except Exception as e:  # noqa: BLE001
            so_text = None
            print(f"[Guardian:SecondOpinion] 收尾前判第二意見出錯（這次不附，收尾照舊由 Stop 判）：{type(e).__name__}: {e}",
                  file=sys.stderr)
        for text in (tj, pick, so_text):
            if text:
                print(text.splitlines()[0], file=sys.stderr)
                parts.append(_note(text, state, sid, config))
                changed = True
    if so_background_on(config):
        try:
            for job in start_job_ids(input_data.get("tool_calls"), str(input_data.get("transcript_path") or "")):
                watch_job(state, sid, job)
                changed = True
            fetched = [str(inp.get("job_id") or "").strip() for n, inp in calls if n.endswith(SO_RESULT_SUFFIX)]
            had = bool(((state.get(SO_WATCH) or {}).get(sid) or {}).get("on"))
            notice = so_done_notice(state, sid, fetched)
            changed = changed or had
            if notice:
                parts.append(notice)
        except Exception as e:  # noqa: BLE001
            print(f"[Guardian:SecondOpinion] 第二意見跑完的提醒出錯（這次不送）：{type(e).__name__}: {e}", file=sys.stderr)
    return parts, changed
