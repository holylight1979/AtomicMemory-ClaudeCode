"""
handlers/ups_gates.py — UserPromptSubmit detect 段（前置閘）

從 user_prompt_submit.py 拆出。
職責：每輪 prompt 的前置偵測與輕量通知，全部在 atom 注入之前執行：
- evasion guard 旁路（追蹤近 5 則 prompt、清 failing_tests）
- user decision detector gate
- confirmed extractions / veto
- long_die response（停用/保持 backend）
- atom-write guard reminder（建議階段不該宣告 [固]/[觀]）
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from wg_core import _now_iso, _atom_debug_error, _atom_debug_log, user_typed_text, v6_enabled, WORKFLOW_DIR
from wg_extraction import detect_signal, extract_veto_hints, extract_veto_question, settle_pending_veto
from wg_evasion import is_dismiss_prompt
from handlers._shared import entry_note, with_note

# Ollama client（dispatcher 已加 tools/ 到 sys.path）；用本檔位置推樹根，不用 Path.home()
_TOOLS_DIR = str(Path(__file__).resolve().parents[2] / "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
# long_die 標記檔（ollama_client.OllamaClient.LONG_DIE_MARKER，同一個資料根）：每則訊息先看檔在不在，在才載 ollama_client
# （它連帶 urllib／http／ssl 約 40 ms，HOOK_IMPORT_ON_USE）
_LONG_DIE_MARKER = WORKFLOW_DIR / ".backend_long_die.json"


def check_long_die_status() -> Any:
    if not _LONG_DIE_MARKER.exists():
        return None
    try:
        from ollama_client import check_long_die_status as _f
    except ImportError:
        return None
    return _f()


def disable_backend(*a: Any, **k: Any) -> bool:
    try:
        from ollama_client import disable_backend as _f
    except ImportError:
        return False
    return _f(*a, **k)


_LAZY = object()
OllamaClient: Any = _LAZY      # 名字留在模組上（換成 None＝不清標記）；用到才載


def _clear_long_die_marker() -> None:
    cls = OllamaClient
    if cls is _LAZY:
        try:
            from ollama_client import OllamaClient as cls
        except ImportError:
            return
    if cls is not None:
        cls._clear_long_die_marker()


_SEG_SPLIT_RE = re.compile(r"&&|\|\||[;|&\n]")
_ENV_PREFIX_RE = re.compile(r"^(?:[A-Za-z_]\w*=\S*\s+)*")
_PUSH_SEG_RE = re.compile(r"^(?:git(?:\s+-[Cc]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*\s+push\b(?P<git>.*)"
                          r"|svn(?:\s+--?[\w-]+(?:=\S+)?)*\s+(?:commit|ci)\b)", re.IGNORECASE | re.DOTALL)
_DRY_RUN_RE = re.compile(r"(?:^|\s)(?:--dry-run|-n)(?=\s|$)")
_PUSH_SCAN_CAP = 2_000_000     # 一次最多掃這麼多位元組（第一次掃、resume 的長 transcript 只看尾段）
_PUSH_WAITING_CAP = 20


def is_push_command(command: str) -> bool:
    """指令裡有一段真的在推送：剔掉註解行，照 &&、||、;、|、&、換行切段，去掉開頭的環境變數指定，那一段以 git … push
    （不帶 --dry-run／-n；前面只准全域選項）或 svn commit／ci 起頭。echo、commit 訊息裡的字樣不算。"""
    from wg_release_rules import strip_comment_lines
    for seg in _SEG_SPLIT_RE.split(strip_comment_lines(command or "")):
        m = _PUSH_SEG_RE.match(_ENV_PREFIX_RE.sub("", seg.strip()))
        if m and not (m.group("git") is not None and _DRY_RUN_RE.search(m.group("git"))):
            return True
    return False


def note_order_push(state: Dict[str, Any], transcript_path: Any) -> bool:
    """transcript 上次掃到的地方之後的完整行裡有跑成功的推送（Bash／PowerShell 指令 is_push_command、對應的 tool_result
    沒標 is_error）→ state order_push_seq＝目前 turn_seq。Stop 每次收尾掃、口令閘判口令前也掃（push 完、收尾之前再 commit
    也認得）。掃到哪裡記 order_scan_offset（只算到最後一個換行，半行留給下次）；指令看到了、結果還沒寫進來的記
    order_push_waiting 留給下次配對。讀不到 transcript 只印 stderr。回這次有沒有記到推送。"""
    if not transcript_path:
        return False
    try:
        size = os.path.getsize(transcript_path)
        off = int(state.get("order_scan_offset") or 0)
        off = max(0 if off > size else off, size - _PUSH_SCAN_CAP)     # transcript 變短＝換了一份，從頭掃
        with open(transcript_path, "rb") as f:
            f.seek(off)
            data = f.read(size - off)
    except (OSError, TypeError, ValueError) as e:
        print(f"[Guardian:CommitOrder] 讀不了 transcript，這次沒查有沒有推送：{type(e).__name__}: {e}", file=sys.stderr)
        return False
    cut = data.rfind(b"\n") + 1
    state["order_scan_offset"] = off + cut
    waiting = [str(i) for i in state.get("order_push_waiting") or []]
    pushed = False
    for line in data[:cut].decode("utf-8", errors="replace").splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        msg = o.get("message") if isinstance(o, dict) else None
        for b in msg.get("content") if isinstance(msg, dict) and isinstance(msg.get("content"), list) else []:
            if not isinstance(b, dict):
                continue
            if (b.get("type") == "tool_use" and b.get("name") in ("Bash", "PowerShell")
                    and is_push_command(str((b.get("input") or {}).get("command") or ""))):
                waiting.append(str(b.get("id")))
            elif b.get("type") == "tool_result" and str(b.get("tool_use_id")) in waiting:
                waiting.remove(str(b.get("tool_use_id")))
                pushed = pushed or not b.get("is_error")
    state["order_push_waiting"] = waiting[-_PUSH_WAITING_CAP:]
    if pushed:
        state["order_push_seq"] = int(state.get("turn_seq", 0) or 0)
    return pushed


def order_spent(state: Dict[str, Any]) -> bool:
    """版控口令這批做完了沒：使用者開這個回合之後跑成功了推送（order_push_seq；「上GIT」＝commit→push 一氣，push 完成這批
    就結束）。先照 order_transcript（Stop／UserPromptSubmit 記的 transcript 路徑）補掃一次新寫進來的部分。只 commit 沒 push、
    中間夾背景通知或收尾閘逼出的補修 commit 都不算做完。口令閘（pre_tool_use 的 CommitOrder）與 track_turn_prompts 共用。"""
    note_order_push(state, state.get("order_transcript"))
    push, seq = state.get("order_push_seq"), state.get("turn_prompts_seq")
    return (isinstance(push, int) and not isinstance(push, bool) and isinstance(seq, int) and not isinstance(seq, bool)
            and push >= seq)


def track_turn_prompts(state: Dict[str, Any], clean_prompt: str, v6: Optional[bool] = None) -> None:
    """本回合使用者原話清單：Stop 關回合（turn_open=False）後第一則重開，
    同回合內排隊送進來的 mid-turn 訊息追加。口令閘看整回合而非只看最後一句
    （否則「上GIT」之後補一句別的話就會把口令蓋掉）。Stop 被 block 後續送進來的
    使用者訊息算新回合：清單重開，口令要重下（使用者新打的字＝口令失效的時點）。

    清單只存 user_typed_text（剔掉通知、其他 session 的訊息等非使用者區塊後，先清理再截 500 字）。
    整則都不是使用者的話（背景通知、其他 session 的訊息）也走 UserPromptSubmit：內文永不進清單；
    它在回合關閉後進來＝使用者上一回合的延續，原話沿用（「完工後直接上GIT」跨得過背景等待、收尾閘逼出的補修 commit），
    除非那之後這批已經 push 完（order_spent：口令用掉了）→ 清空，再 commit 要新口令。

    turn_prompts_seq＝使用者本人打字開的回合（寫碼查核的預算與放行看它）。回合關閉後先進來的通知只開「續跑回合」
    （turn_typed=False）；這個續跑回合裡使用者打的第一則字算使用者開的新回合：序號前進、清單重開（先前的口令失效）。
    v6＝守門總開關（沒給就照環境變數 WG_V6 判）。關時照 9e476fd0：口令 commit 過就用掉（last_commit_turn_seq），
    續跑回合裡使用者打的字照舊追加、口令沿用。"""
    has_list = isinstance(state.get("turn_prompts"), list)
    typed = user_typed_text(clean_prompt)[:500]

    def _new_turn() -> None:
        state["turn_prompts_seq"] = int(state.get("turn_seq", 0)) + 1   # 本則 UPS 收尾後的 turn_seq
        state["user_turn_count"] = int(state.get("user_turn_count", 0) or 0) + 1

    v6 = v6_enabled({}) if v6 is None else v6
    if not typed:
        # 同伴訊息、背景通知只開續跑回合（回合只由使用者打字開，規則 TURN_SINCE_USER_PROMPT）
        if not state.get("turn_open"):
            spent = (order_spent(state) if v6
                     else int(state.get("last_commit_turn_seq", -1)) >= int(state.get("turn_prompts_seq", 0)))
            if spent:
                state["turn_prompts"] = []
            state["turn_typed"] = False                                  # 通知開的續跑回合：還沒有使用者打字
        if not has_list:
            state["turn_prompts"] = []
    elif state.get("turn_open") and has_list:
        continuation = state.get("turn_typed") is False                  # 續跑回合裡使用者的第一則字：使用者開的新回合
        state["turn_prompts"] = [typed] if v6 and continuation else (state["turn_prompts"] + [typed])[-5:]
        if continuation:
            _new_turn()
    else:
        state["turn_prompts"] = [typed]
        _new_turn()
    if typed:
        state["turn_typed"] = True
    state["turn_open"] = True


def run_pre_gates(
    session_id: str,
    state: Dict[str, Any],
    config: Dict[str, Any],
    clean_prompt: str,
    prompt_lower: str,
    lines: List[str],
) -> None:
    """執行 detect 段全部前置閘。mutate state / append lines。"""
    # 下面的「使用者說了算」判斷（口令、豁免、使用者決策、否決記憶、停用後端）只吃使用者本人打的字：
    # 剔掉通知、其他 session 的訊息等區塊後的文字（先清理、再截長）；整則都不是使用者的話 → 空字串。
    typed = user_typed_text(clean_prompt)
    typed_lower = typed.lower()

    # ── Evasion Guard: 追蹤近 5 則 user prompt（存清理後的文字；不是使用者的話存空字串，保留「收過一則」的紀錄）─────
    rup = state.setdefault("recent_user_prompts", [])
    rup.append(typed[:500])
    if len(rup) > 5:
        state["recent_user_prompts"] = rup[-5:]
    v6 = v6_enabled(config)
    track_turn_prompts(state, clean_prompt, v6)
    if not v6 and state.get("failing_tests") and is_dismiss_prompt(clean_prompt):
        state["failing_tests"] = []   # v6 守門關閉：照 9e476fd0，使用者說「先這樣／跳過」就清掉紅測清單
    # v6：使用者說「先這樣／跳過」不再在這裡清掉全部紅測清單：要 LLM 在收尾寫「不做｜<哪一支>：使用者說「<原句>」」，
    # Stop 的 TestFailGate 只豁免對得上的那幾筆（規則 USER_WAIVER_NEEDS_CITATION，wg_release_rules.waived_failures）。

    # ─── User Decision Detector gate ────────────────────────────
    ue_config = config.get("userExtraction", {})
    if typed and ue_config.get("enabled", False):
        try:
            det = detect_signal(typed)
            if det.get("signal"):
                turn_n = state.get("topic_tracker", {}).get("prompt_count", 0)
                pending = state.setdefault("pending_user_extract", [])
                pending.append({
                    "turn_id": f"{session_id}-{turn_n}",
                    "prompt": user_typed_text(clean_prompt, keep_lines=True),   # 保留換行，worker 才能逐句看
                    "score": det["score"],
                    "matched": det["matched"],
                    "ts": _now_iso(),
                })
                if len(pending) > 10:
                    state["pending_user_extract"] = pending[-10:]
        except Exception as e:
            _atom_debug_error("user_extract_gate", e)

    # ─── Confirmed extractions ──
    # 「否／不要記…」只是提示（規則 EXTRACT_VETO_NEEDS_JUDGMENT）：通知照送；使用者本人打的字有這些字樣 → 問 AI 是不是在否決，
    # AI 判是才用 atom_retire 撤卡並宣告。上次問了沒回的，這則使用者訊息先結帳（undeclared，不自動撤）。
    if typed and v6:
        settle_pending_veto(state, session_id)
    confirmed = state.get("confirmed_extractions", [])
    if confirmed and not v6 and any(kw in prompt_lower for kw in ("否", "不要記", "別記", "取消記憶")):
        for ext in confirmed:   # v6 守門關閉：照 9e476fd0，否決詞直接丟掉這批萃取結果（v6 改成問 AI 再撤卡）
            _atom_debug_log("user-extract:rejected", f"User vetoed: {ext.get('statement', '')[:80]}", config)
        state["confirmed_extractions"] = []
        confirmed = []
    if confirmed:
        for ext in confirmed:
            stmt = ext.get("statement", "")
            wr = ext.get("write_result")
            where = f"（{ext['atom_path']}）" if ext.get("atom_path") else ""
            if wr in ("wrote", "deduped"):
                lines.append(
                    f"偵測到決策語句：「{stmt}」— 已記為 atom{where}。使用者要撤回 → atom_retire 那張卡。"
                )
            elif wr == "failed":
                lines.append(
                    f"[user-extract] 決策語句「{stmt}」atom 寫入失敗，未入庫（詳見 atom-debug log）。"
                )
                # 已逐筆宣告 → 從 aggregate 告警清單去重
                fw = state.get("user_extract_write_failed", [])
                state["user_extract_write_failed"] = [
                    s for s in fw if s != stmt[:80]
                ]
            else:
                # 舊 state / worker 尚未回寫結果 → 只宣告已送管線，不假成功
                lines.append(
                    f"偵測到決策語句：「{stmt}」— 已送萃取管線。使用者要撤回 → 等寫成卡後 atom_retire。"
                )
        hints = extract_veto_hints(typed)
        written = [e for e in confirmed if e.get("write_result") in ("wrote", "deduped")]
        if v6 and hints and written:
            q = extract_veto_question(hints, written)
            lines.append(with_note(q, entry_note(q, "user_prompt", session_id=session_id, state=state, config=config)))
            state["extract_veto_pending"] = {
                "turn": int(state.get("turn_seq", 0) or 0), "hints": hints,
                "statements": [str(e.get("statement", ""))[:80] for e in written],
                "atoms": [str(e.get("atom_path", "")) for e in written],
            }
        state["confirmed_extractions"] = []

    # ─── User-extract 寫入失敗告警（可觀測性鐵律：fail 必告知） ──
    failed_writes = state.get("user_extract_write_failed", [])
    if failed_writes:
        lines.append(
            f"[user-extract] {len(failed_writes)} 筆決策 atom 寫入失敗："
            + "；".join(f"「{s}」" for s in failed_writes[:3])
            + ("…" if len(failed_writes) > 3 else "")
        )
        state["user_extract_write_failed"] = []

    # ─── Dual-Backend: long_die user response ─────
    try:
        long_die = check_long_die_status() if typed else None   # 「停用／保持」是使用者的回覆
        if long_die:
            backend_name = long_die.get("backend", "")
            if any(kw in typed_lower for kw in ("停用", "disable")):
                if disable_backend(backend_name):
                    _clear_long_die_marker()
                    lines.append(
                        f"[Dual-Backend] 已永久停用 '{backend_name}'。"
                        f"如需重新啟用，修改 config.json 中 enabled: true。"
                    )
                else:
                    lines.append(f"[Dual-Backend] 停用 '{backend_name}' 失敗，請手動修改 config.json。")
            elif any(kw in typed_lower for kw in ("保持", "keep", "忽略")):
                _clear_long_die_marker()
                lines.append(f"[Dual-Backend] 保持 '{backend_name}'，long_die 將在時間段到期後自動恢復。")
    except Exception as e:
        print(f"[dual-backend] Long DIE response error: {e}", file=sys.stderr)

    # ─── Atom-Write Guard: confidence gate reminder ─────────────────────
    atom_write_triggers = (
        "記住", "記下來", "存起來", "存下來", "值得存", "值得記",
        "寫成 atom", "寫 atom", "存成 atom", "存atom", "存成[固]", "存成 [固]",
        "存成[觀]", "存成 [觀]", "記為[固]", "記為 [固]",
    )
    if any(kw in typed for kw in atom_write_triggers):                     # 只看使用者打的字：通知、同伴訊息不觸發
        lines.append(
            "[Atom-Write Guard] 偵測到記憶寫入意圖。硬規則："
            "(1) 新 atom 一律 [臨]，MCP atom_write 會 reject [固]/[觀]；"
            "(2) 單次成功 ≠ 穩定模式，需 4+ session 命中才建議晉升；"
            "(3) 晉升走 atom_promote（Confirmations ≥4→[觀]/≥10→[固] 主軌，或效用 Wilson 下界 ≥0.6 且 n≥3；ReadHits 已退出晉升、僅純曝光計數），不手動改 frontmatter；"
            "(4) 若是更新既有 atom，用 mode=append 並保留原 confidence。"
        )
