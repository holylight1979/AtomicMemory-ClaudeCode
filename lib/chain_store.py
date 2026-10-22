"""chain_store.py：連鎖斷路器的帳、快照、還原與使用者答案（I/O；判定全在 hooks/wg_chain.py）。

做什麼：
- 帳：Logs/chain-<session>.jsonl 一行一筆（gate＝閘觸發、action＝AI 動作、alarm、notice、shown、halted、answer、reset、snapshot、restore），
  每筆帶回合、子代理、步序、時間戳，工具呼叫上的觸發與動作另帶 batch（哪一則回覆，從 transcript 取，見 _batch）；
  連鎖狀態每次都由 wg_chain.fold 從帳重算，不另存 state。
- 快照：連鎖段開了之後，每個要被改的檔這一段第一次改之前先存到 workflow/chain-snap/<session>/（原本不存在就記不存在）；
  快照檔先寫暫存再硬連結成正式名，正式名已在就不覆寫（並行的兩個 hook 不互蓋）。存快照時順手清掉這個 session 更早回合的快照。
- 還原：使用者選「還原連鎖改動」→ 先核對實際路徑沒變、現況等於這一段最後一次寫入後的內容，才逐檔寫回快照、刪掉連鎖中新建的檔；
  寫回前核快照雜湊、寫回後重讀比雜湊，比不上重試。
- 答案：只認 wg_release._answers_after 判讀的 AskUserQuestion 結果（tool_use_id 對得上、題目含【收尾放行確認】），再由
  wg_chain.choice_of 取題目逐字等於通知那一題的答案。
呼叫端只用這幾支薄函式：gate_fired（閘要擋或記欠之前）、halt（PreToolUse 一開始：中止停手中要不要擋這個呼叫）、
record_only（只問這一回合是不是只記錄）、before_write（工具改檔之前）、action_done（AI 動作完成之後）、on_stop（收尾、各閘之前）、
session_cleanup（SessionEnd）。
這裡出錯一律照原本的閘行為（不中止、不只記錄、不停手），stderr 印一行；快照存不了照放行改動、帳上記原因。
v6 守門總開關關著整個不跑（_ctx 回 None）：v6 關只跑 v6 以前就有的處理，chain_breaker.enabled 寫開也一樣；SessionEnd 清快照照做。
怎麼跑案例：python -X utf8 -m pytest -q hooks/verify/verify_chain_breaker.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Tuple

_HOOKS = str(Path(__file__).resolve().parents[1] / "hooks")
if _HOOKS not in sys.path:
    sys.path.insert(0, _HOOKS)
import wg_chain as wc  # noqa: E402
import wg_release  # noqa: E402


class GateResult(NamedTuple):
    record_only: bool              # True＝這次不擋、不記欠，只留帳（CHAIN_ABORT_RECORD_ONLY）
    notice: Optional[str] = None   # Stop 上的閘剛讓警報響：用它擋這一次，取代原擋訊息（CHAIN_STOP_NOTICE_ONCE）
    halt: Optional[str] = None     # 工具上的閘剛讓警報響：用它擋下這個工具呼叫，取代原擋訊息（CHAIN_HALT_UNTIL_ANSWER）


class StopOut(NamedTuple):
    block: bool                    # True＝擋這一次（連鎖中止通知）；False＝不擋，text 交呼叫端用 systemMessage 給使用者看
    text: str


PASS = GateResult(False)
_RETRY_PAUSE = 0.2


def _test_root() -> Optional[Path]:
    """pytest 底下（PYTEST_CURRENT_TEST）每一案各用一份帳與快照，放測試用的 Logs 暫存目錄（wg_core.logs_dir）；平常回 None。
    為什麼：同一次 pytest 的資料根共用、案例的 session id 又常一樣，前一案的觸發留在帳上，後一案同一道閘再擋一次就被當成同一回合
    第 2 次而中止；快照也不能落進模組載入時算好的資料根。"""
    t = os.environ.get("PYTEST_CURRENT_TEST", "")
    if not t:
        return None
    from wg_core import logs_dir
    return logs_dir() / "chain-tests" / hashlib.sha1(t.rsplit(" ", 1)[0].encode("utf-8")).hexdigest()[:12]


def _ledger_dir() -> Path:
    from wg_core import logs_dir
    return _test_root() or logs_dir()


def _snap_root() -> Path:
    from wg_core import WORKFLOW_DIR
    t = _test_root()
    return t / "chain-snap" if t else WORKFLOW_DIR / "chain-snap"


def _safe(name: Any) -> str:
    return re.sub(r"[^\w.-]", "_", str(name or ""))[:80]


def ledger_path(sid: str) -> Path:
    return _ledger_dir() / f"chain-{_safe(sid) or 'nosession'}.jsonl"


def _snap_dir(sid: str) -> Path:
    return _snap_root() / (_safe(sid) or "nosession")


def _warn(where: str, e: BaseException) -> None:
    print(f"[chain-breaker] {where} 出錯，照原本的閘行為：{type(e).__name__}: {e}", file=sys.stderr)


def read_rows(sid: str) -> List[Dict[str, Any]]:
    try:
        text = ledger_path(sid).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    rows = []
    for line in text.splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if isinstance(o, dict):
            rows.append(o)
    return rows


def _append(sid: str, rows: List[Dict[str, Any]]) -> None:
    p = ledger_path(sid)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


class _Ctx(NamedTuple):
    sid: str
    turn: int
    agent: str
    rows: List[Dict[str, Any]]
    cfg: Dict[str, Any]
    now: float

    def chain(self) -> wc.Chain:
        return wc.fold(self.rows, self.turn, self.agent)

    def row(self, row_type: str, **fields: Any) -> Dict[str, Any]:
        """一筆新帳（同時加進 rows，之後的 chain() 看得到）：步序接在這一回合、這個對話者既有的筆數之後。"""
        seq = 1 + sum(1 for r in self.rows if r.get("turn") == self.turn and str(r.get("agent") or "") == self.agent)
        r = {"type": row_type, "turn": self.turn, "agent": self.agent, "seq": seq, "ts": round(self.now, 3),
             "at": datetime.fromtimestamp(self.now).isoformat(timespec="seconds"), **fields}
        self.rows.append(r)
        return r

    def put(self, row_type: str, **fields: Any) -> Dict[str, Any]:
        r = self.row(row_type, **fields)
        _append(self.sid, [r])
        return r


def _ctx(sid: str, turn: int, input_data: Optional[Dict[str, Any]], config: Optional[Dict[str, Any]],
         now: Optional[float]) -> Optional[_Ctx]:
    """斷路器這一次要不要跑：v6 守門總開關關著（wg_core.v6_enabled，以它為準）或 chain_breaker.enabled 沒開 → None，
    每個公開函式都照「沒事」回。"""
    from wg_core import v6_enabled
    cfg = wc.settings(config)
    if not cfg["enabled"] or not v6_enabled(config or {}):
        return None
    agent = str((input_data or {}).get("agent_id") or "")
    return _Ctx(str(sid), int(turn), agent, read_rows(sid), cfg, time.time() if now is None else float(now))


def _event(input_data: Dict[str, Any]) -> str:
    """CHAIN_SAME_EVENT 用的事件鍵：工具 hook 用 tool_use_id；收尾用 transcript 當下長度（同一次收尾裡先後擋的閘同鍵）。"""
    tid = input_data.get("tool_use_id")
    if tid:
        return str(tid)
    return f"{input_data.get('hook_event_name') or ''}@{_size(input_data.get('transcript_path'))}"


def _size(path: Any) -> int:
    try:
        return os.path.getsize(path) if path else 0
    except OSError:
        return 0


_BATCH_TAIL_BYTES = 2_000_000


def _assistant(line: str) -> Optional[Dict[str, Any]]:
    """transcript 一行若是 assistant 紀錄，回它的 message（dict）；不是回 None。"""
    if '"assistant"' not in line:
        return None
    try:
        o = json.loads(line)
    except ValueError:
        return None
    if not isinstance(o, dict) or o.get("type") != "assistant":
        return None
    return o["message"] if isinstance(o.get("message"), dict) else {}


def _batch(input_data: Dict[str, Any]) -> Tuple[str, str]:
    """CHAIN_SAME_BATCH 的批次鍵：這次工具呼叫所在那則 assistant 回覆「之前」最後一則 assistant 的 message.id；回 (鍵, 判不出的原因)。
    為什麼取之前那則：CC 一則回覆串流完才整則寫進 transcript——平行一批的呼叫跑 hook 時，這一則一行都還沒落盤（第 0 步實測：
    警報當下 transcript 只寫到這則之前）；只送一個呼叫的回覆則常已落盤。兩種都取「之前那則」，同一批才拿到同一個值：
    自己這次的 tool_use 已在 transcript → 從那行往前找第一個 message.id 不同的 assistant；還不在 → 取最後一則 assistant。
    判不出回 ("", 原因)，呼叫端照舊接邊：子代理（它的回覆不在主 transcript）、讀不到、尾段找不到 assistant、沒有 message.id。"""
    tid = str(input_data.get("tool_use_id") or "")
    if input_data.get("agent_id"):
        return "", "子代理的呼叫（它的回覆不在主 transcript）"
    tp = input_data.get("transcript_path")
    try:
        size = os.path.getsize(tp)
        with open(tp, "rb") as f:
            f.seek(max(0, size - _BATCH_TAIL_BYTES))
            lines = f.read().decode("utf-8", errors="replace").splitlines()
    except (OSError, TypeError, ValueError):
        return "", "transcript 讀不到"
    end, own = len(lines), ""
    for k in range(len(lines) - 1, -1, -1):
        msg = _assistant(lines[k]) if tid and tid in lines[k] else None
        if msg is not None and any(isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id") == tid
                                   for b in msg.get("content") or ()):
            end, own = k, str(msg.get("id") or "")
            if not own:
                return "", "這次的 tool_use 那行沒有 message.id"
            break
    for k in range(end - 1, -1, -1):
        msg = _assistant(lines[k])
        if msg is None or (own and msg.get("id") == own):
            continue
        return (str(msg["id"]), "") if msg.get("id") else ("", "前一則 assistant 沒有 message.id")
    return "", ("transcript 上還沒有前一則 assistant" if size <= _BATCH_TAIL_BYTES
                else f"transcript 尾段 {_BATCH_TAIL_BYTES} 位元組內找不到前一則 assistant")


def _batch_fields(input_data: Dict[str, Any]) -> Dict[str, str]:
    """工具呼叫上的一筆帳要帶的 batch（判不出另記 batch_why）；收尾等沒有 tool_use_id 的事件不帶。"""
    if not input_data.get("tool_use_id"):
        return {}
    key, why = _batch(input_data)
    return {"batch": key} if key else {"batch": "", "batch_why": why}


# ─── 閘觸發、停手、只記錄 ─────────────────────────────────────────────────

def gate_fired(sid: str, turn: int, gate: str, what: str, input_data: Dict[str, Any], config: Dict[str, Any], *,
               watched: Iterable[str] = (), later: Iterable[str] = (), now: Optional[float] = None) -> GateResult:
    """閘要擋下或記欠之前呼叫：記一筆觸發，回這次照擋（record_only=False）還是只記錄。
    watched＝這道閘看哪些檔（說不出就不給）；later＝收尾閘擋下時「後面還會擋」預覽裡的閘名（CHAIN_EDGE_PREVIEWED）。
    警報在這一次響：記通知（答案從這之後算、題目定下來、能不能互動）；收尾上回 notice、工具上回 halt，呼叫端用它取代原擋訊息。"""
    try:
        cx = _ctx(sid, turn, input_data, config, now)
        if cx is None:
            return PASS
        ch = cx.chain()
        hook = str(input_data.get("hook_event_name") or "")
        if wc.muted_again(ch, str(gate)):
            return GateResult(True)
        row = {"gate": str(gate), "what": wc.one_line(what), "hook": hook, "event": _event(input_data),
               "watched": [str(p) for p in watched], "later": [str(g) for g in later], **_batch_fields(input_data)}
        j = wc.judge(ch, row, cx.cfg)
        new = [cx.row("gate", **row, record_only=j.record_only, depth=j.depth, same=j.same,
                      link=j.link.rule if j.link else "")]
        if not j.alarm:
            _append(cx.sid, new)
            return GateResult(j.record_only)
        new.append(cx.row("alarm", hits=[list(h) for h in j.alarm], count=len(ch.steps), depth=j.depth))
        tp = input_data.get("transcript_path")
        why = wg_release.non_interactive_reason(input_data, tp)
        new.append(cx.row("notice", offset=_size(tp), interactive=why is None, why=why or "",
                          question=wc.question(cx.chain())))
        if wc.is_stop(hook):
            new.append(cx.row("shown"))
            _append(cx.sid, new)
            return GateResult(True, notice=wc.notice_text(cx.chain(), cx.now))
        _append(cx.sid, new)
        if why:                                   # CHAIN_HEADLESS_NO_ASK：沒人能答不停手，這次照放（只記錄），收尾再送經過表
            return GateResult(True)
        return GateResult(True, halt=wc.halt_text(cx.chain(), cx.now))
    except Exception as e:  # noqa: BLE001  斷路器壞了不能讓閘跟著壞：照原本的閘行為
        _warn("gate_fired", e)
        return PASS


def halt(sid: str, turn: int, tool: str, input_data: Dict[str, Any], config: Dict[str, Any], *,
         readonly: bool = False, now: Optional[float] = None) -> Optional[str]:
    """PreToolUse 一開始呼叫：中止停手中（CHAIN_HALT_UNTIL_ANSWER）而這個呼叫不是讀或問 → 回擋訊息；否則 None。
    readonly＝呼叫端判定這個指令唯讀（Bash 讀檔指令這類）。擋之前先看使用者是不是已經答了（答繼續／放行就放這個呼叫過）。"""
    try:
        cx = _ctx(sid, turn, input_data, config, now)
        if cx is None or not wc.halted(cx.chain()) or readonly or str(tool) in wc.HALT_ALLOW:
            return None
        done = _apply(cx, input_data)
        ch = cx.chain()
        if not wc.halted(ch):
            return None
        cx.put("halted", tool=str(tool), event=_event(input_data))
        return f"{done}\n{wc.halt_text(ch, cx.now)}" if done else wc.halt_text(ch, cx.now)
    except Exception as e:  # noqa: BLE001
        _warn("halt", e)
        return None


def record_only(sid: str, turn: int, input_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """這一回合（這個對話者）現在是不是警報後只記錄（CHAIN_ABORT_RECORD_ONLY）。出錯回 False（照原本的閘行為）。"""
    try:
        cx = _ctx(sid, turn, input_data, config, None)
        return bool(cx and cx.chain().record_only)
    except Exception as e:  # noqa: BLE001
        _warn("record_only", e)
        return False


# ─── 收尾與使用者答案 ─────────────────────────────────────────────────────

def on_stop(sid: str, turn: int, input_data: Dict[str, Any], config: Dict[str, Any],
            now: Optional[float] = None) -> Optional[StopOut]:
    """收尾時、各閘之前呼叫一次（CHAIN_STOP_NOTICE_ONCE）：警報後還沒送過經過表 → 擋一次送表（使用者已先答了就不擋、附結果與表）；
    送過、使用者答了 → 照答案做、不擋、附結果；送過還沒答 → 不擋、附提醒。沒警報回 None（既有閘照舊）。"""
    try:
        cx = _ctx(sid, turn, input_data, config, now)
        if cx is None:
            return None
        ch = cx.chain()
        step = wc.stop_step(ch)
        if step == "notice":
            cx.put("shown")                    # 先記在中止的這一段（答「繼續」會開新的一段）
            done = _apply(cx, input_data)
            return StopOut(False, f"{done}\n{wc.report(ch, cx.now)}") if done else StopOut(True, wc.notice_text(ch, cx.now))
        if step == "remind":
            done = _apply(cx, input_data)
            return StopOut(False, done or wc.remind_text(ch))
        return None
    except Exception as e:  # noqa: BLE001
        _warn("on_stop", e)
        return None


def _apply(cx: _Ctx, input_data: Dict[str, Any]) -> Optional[str]:
    """中止通知之後使用者答了三選一嗎（CHAIN_ANSWER_BY_TOOL_USE_ID）：答了就照做（還原／歸零／放行）並回一段結果；沒答回 None。"""
    ch = cx.chain()
    if ch.notice is None or ch.answer is not None or not ch.notice.get("interactive"):
        return None
    pairs = wg_release._answers_after(input_data.get("transcript_path"), int(ch.notice.get("offset") or 0))
    got = wc.choice_of(pairs, wc.question(ch))
    if got is None:
        return None
    choice, raw = got
    cx.put("answer", choice=choice, answer=raw[:200])
    if choice == "restore":
        results, missed = restore(cx.sid, cx.chain(), cx.cfg)
        cx.put("restore", results=results, missed=missed)
        return wc.answer_text(choice, raw, results, missed)
    if choice == "continue":
        cx.put("reset")
    return wc.answer_text(choice, raw)


# ─── 快照與還原 ─────────────────────────────────────────────────────────

def before_write(sid: str, turn: int, paths: Iterable[str], input_data: Dict[str, Any], config: Dict[str, Any],
                 cwd: str = "", now: Optional[float] = None) -> None:
    """工具真的要改檔之前呼叫（PreToolUse 決定放行之後）：連鎖段開著、這個檔這一段還沒存過 → 先存快照（CHAIN_SNAPSHOT_WINDOW）。
    相對路徑照 cwd 補成絕對路徑，補不出就不存（還原時列成沒快照）。不擋任何改動。"""
    try:
        cx = _ctx(sid, turn, input_data, config, now)
        if cx is None:
            return
        ch = cx.chain()
        if not ch.open or ch.answer is not None:
            return
        root = _snap_dir(cx.sid)
        mine = (wc.canon_path(_snap_root()), wc.canon_path(_ledger_dir()))
        new = []
        for raw in paths:
            ap = _abs(raw, cwd)
            if ap is None or any(wc.canon_path(ap).startswith(m + "/") for m in mine):
                continue
            need = wc.snapshot_need(ch, ap, cx.cfg)
            if need is None:
                continue
            fields = {"skipped": "這一段快照已存滿"} if need == "full" else _take(ap, root, cx, ch.segment)
            r = cx.row("snapshot", path=str(ap), real=_real(ap), event=_event(input_data), **fields)
            ch.snaps[wc.canon_path(ap)] = r
            new.append(r)
        if new:
            _append(cx.sid, new)
            _prune(root, cx.turn)
    except Exception as e:  # noqa: BLE001
        _warn("before_write", e)


def _abs(raw: Any, cwd: str) -> Optional[Path]:
    if not str(raw or "").strip():
        return None
    p = Path(str(raw))
    if p.is_absolute():
        return p
    return Path(cwd) / p if cwd else None


def _real(p: Any) -> str:
    """實際路徑（解開連結、掛載點）的比對鍵；快照記一份，還原前再算一次比。"""
    return wc.canon_path(os.path.realpath(str(p)))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _take(ap: Path, root: Path, cx: _Ctx, segment: int) -> Dict[str, Any]:
    """存一份快照；檔名帶回合、對話者、段、路徑雜湊（同一段同一檔只有一個正式名）。"""
    if not ap.exists():
        return {"existed": False}
    if not ap.is_file():
        return {"existed": True, "skipped": "不是一般檔"}
    try:
        size = ap.stat().st_size
        if size > cx.cfg["snapshot_max_bytes"]:
            return {"existed": True, "size": size, "skipped": f"超過 {cx.cfg['snapshot_max_bytes']} 位元組"}
        data = ap.read_bytes()
    except OSError as e:
        return {"existed": True, "skipped": f"讀不到：{e}"}
    key = hashlib.sha1(wc.canon_path(ap).encode("utf-8")).hexdigest()[:16]
    name = f"t{cx.turn}-{_safe(cx.agent) or 'main'}-s{segment}-{key}.snap"
    try:
        data = _place_once(root, name, data)
    except OSError as e:
        return {"existed": True, "skipped": f"快照寫不進去：{e}"}
    return {"existed": True, "size": len(data), "snap": name, "sha256": _sha(data)}


def _place_once(root: Path, name: str, data: bytes) -> bytes:
    """快照檔只建一次、建了不覆寫：先寫暫存檔再硬連結成正式名（正式名一出現就是完整內容）；正式名已在（並行的另一個 hook
    先存了）→ 以已在的那份為準。硬連結不支援的磁碟退回排他建立。回正式名實際的內容。"""
    root.mkdir(parents=True, exist_ok=True)
    target = root / name
    fd, tmp = tempfile.mkstemp(prefix=".snap-", dir=root)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        try:
            os.link(tmp, target)
        except FileExistsError:
            return target.read_bytes()
        except OSError:
            try:
                with open(target, "xb") as f:
                    f.write(data)
            except FileExistsError:
                return target.read_bytes()
        return data
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _prune(root: Path, turn: int) -> None:
    """清掉這個 session 更早回合（回合號比現在小）的快照；同回合與更晚回合的不碰。"""
    if not root.is_dir():
        return
    try:
        for f in root.iterdir():
            m = re.match(r"t(\d+)-", f.name)
            if f.is_file() and f.suffix == ".snap" and m and int(m.group(1)) < turn:
                f.unlink()
    except OSError as e:
        _warn("prune", e)


def session_cleanup(sid: str, max_age_days: float = 7.0, now: Optional[float] = None) -> None:
    """SessionEnd 呼叫：這個 session 的快照整個資料夾刪掉（還原只在警報那一回合有效）；別的 session 留下、超過 max_age_days 沒動過的
    快照資料夾與連鎖帳一起刪（當掉沒送 SessionEnd 的也清得到）。這個 session 的帳留著：它是事後看連鎖經過的唯一紀錄
    （無頭跑完 SessionEnd 就到，驗收讀的就是它），由之後的 SessionEnd 照天數清。刪不掉的浮 stderr，不擋收尾。"""
    import shutil
    cutoff = (time.time() if now is None else now) - max_age_days * 86400
    mine = _snap_dir(sid).name
    try:
        root = _snap_root()
        dirs = [d for d in root.iterdir() if d.is_dir()] if root.is_dir() else []
        ldir = _ledger_dir()
        ledgers = [f for f in ldir.glob("chain-*.jsonl") if f != ledger_path(sid)] if ldir.is_dir() else []
    except OSError as e:
        _warn("session_cleanup", e)
        return
    for d in dirs:
        try:
            if d.name == mine or d.stat().st_mtime < cutoff:
                shutil.rmtree(d)
        except OSError as e:
            _warn(f"session_cleanup {d.name}", e)
    for f in ledgers:
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError as e:
            _warn(f"session_cleanup {f.name}", e)


def restore(sid: str, ch: wc.Chain, cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """CHAIN_RESTORE_SEGMENT：照 wg_chain.restore_plan 逐檔還原，每檔最多試 restore_retries 次；回 (逐檔結果, 沒快照到的改動)。"""
    items, missed = wc.restore_plan(ch)
    root = _snap_dir(sid)
    out = []
    for it in items:
        if it.how == "skip":
            out.append({"path": it.path, "ok": False, "how": "skip", "why": f"沒快照：{it.why}"})
            continue
        ok, why = False, ""
        for k in range(cfg["restore_retries"]):
            if k:
                time.sleep(_RETRY_PAUSE)
            ok, why = _restore_one(it, root, cfg)
            if ok:
                break
        out.append({"path": it.path, "ok": ok, "how": it.how, "why": why})
    return out, missed


def _state(p: Path, cap: int) -> Optional[str]:
    """檔案現況：內容雜湊｜"absent"（不存在）｜None（不是一般檔、太大、讀不到）。"""
    try:
        if not os.path.lexists(p):
            return "absent"
        if not p.is_file() or p.stat().st_size > cap:
            return None
        return _sha(p.read_bytes())
    except OSError:
        return None


def _restore_one(it: wc.RestoreItem, root: Path, cfg: Dict[str, Any]) -> Tuple[bool, str]:
    p = Path(it.path)
    target = str(it.snap.get("sha256") or "") if it.how == "write" else "absent"
    cur = _state(p, cfg["snapshot_max_bytes"])
    if cur == target:
        return True, ""                              # 已經是快照的樣子（含上一次重試其實寫成了）
    if it.snap.get("real") and _real(p) != it.snap["real"]:
        return False, "實際路徑變了（連結或掛載點），沒還原"
    if it.expect is None or cur != it.expect:
        return False, "連鎖之後被別處改過（或判不出現況），沒還原"
    if it.how == "delete":
        try:
            p.unlink()
        except OSError as e:
            return False, f"刪不掉：{e}"
        return (False, "刪了還在") if os.path.lexists(p) else (True, "")
    try:
        data = (root / str(it.snap.get("snap") or "")).read_bytes()
    except OSError as e:
        return False, f"快照讀不到：{e}"
    if _sha(data) != target:
        return False, "快照雜湊對不上，不寫回"
    dest = Path(os.path.realpath(str(p)))
    tmp = ""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=f".{dest.name}.chain-restore-", dir=dest.parent)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, dest)
        back = dest.read_bytes()
    except OSError as e:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return False, f"寫不回：{e}"
    return (True, "") if _sha(back) == target else (False, "寫回後重讀比對不上")


# ─── AI 動作 ────────────────────────────────────────────────────────────

def action_done(sid: str, turn: int, kind: str, tool: str, files: Iterable[Dict[str, Any]], input_data: Dict[str, Any],
                config: Dict[str, Any], what: str = "", now: Optional[float] = None) -> None:
    """AI 動作完成之後呼叫（PostToolUse）：連鎖段開著才記一筆（之前的改動不是連鎖）。
    kind＝edit｜rerun｜card｜relocate｜goal｜other；files＝wg_chain.edit_facts 的結果，說不出改了哪些檔（Bash）給空清單、what 給指令。
    每個說得出的檔另記寫入後的內容雜湊 after（還原前核對有沒有被別處改過）。只記錄：不回任何東西、不擋。"""
    try:
        cx = _ctx(sid, turn, input_data, config, now)
        if cx is None or not cx.chain().open:
            return
        rec = []
        for f in files:
            if not isinstance(f, dict):
                continue
            r = {k: f.get(k) for k in ("path", "added", "removed", "comment_only")}
            if f.get("path") and Path(str(f["path"])).is_absolute():
                r["after"] = _state(Path(str(f["path"])), cx.cfg["snapshot_max_bytes"])
            rec.append(r)
        cx.put("action", kind=str(kind), tool=str(tool), files=rec, what=wc.one_line(what), event=_event(input_data),
               **_batch_fields(input_data))
    except Exception as e:  # noqa: BLE001
        _warn("action_done", e)
