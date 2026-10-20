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

import sys
from pathlib import Path
from typing import Any, Dict, List

from wg_core import _now_iso, _atom_debug_log, _atom_debug_error, user_typed_text
from wg_extraction import detect_signal
from wg_release_rules import is_dispatch_message
from harness_text import peer_message_bodies   # lib/（wg_core 已把它放進 sys.path）

# Ollama client（dispatcher 已加 tools/ 到 sys.path）；用本檔位置推樹根，不用 Path.home()
_TOOLS_DIR = str(Path(__file__).resolve().parents[2] / "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
try:
    from ollama_client import check_long_die_status, disable_backend, OllamaClient
except ImportError:
    check_long_die_status = lambda: None  # noqa: E731
    disable_backend = lambda *a, **k: False  # noqa: E731
    OllamaClient = None


def track_turn_prompts(state: Dict[str, Any], clean_prompt: str) -> None:
    """本回合使用者原話清單：Stop 關回合（turn_open=False）後第一則重開，
    同回合內排隊送進來的 mid-turn 訊息追加。口令閘看整回合而非只看最後一句
    （否則「上GIT」之後補一句別的話就會把口令蓋掉）。Stop 被 block 後續送的
    mid-turn 訊息會誤判為新回合——閘只會多擋一次、要求重下口令，fail-safe。

    清單只存 user_typed_text（剔掉通知、其他 session 的訊息等非使用者區塊後，先清理再截 500 字）。
    整則都不是使用者的話（背景通知、其他 session 的訊息）也走 UserPromptSubmit：內文永不進清單；
    它在回合關閉後進來＝使用者上一回合的延續，原話沿用（「完工後直接上GIT」跨得過背景等待），
    除非那之後已經 commit 過（口令用掉了）→ 清空，再 commit 要新口令。

    turn_prompts_seq＝使用者本人打字開的回合（寫碼查核的預算與放行看它）。回合關閉後先進來的通知只開「續跑回合」
    （turn_typed=False）；這個續跑回合裡使用者打的第一則字仍算使用者開的新回合，序號前進（清單照舊追加）。"""
    has_list = isinstance(state.get("turn_prompts"), list)
    typed = user_typed_text(clean_prompt)[:500]

    def _new_turn() -> None:
        state["turn_prompts_seq"] = int(state.get("turn_seq", 0)) + 1   # 本則 UPS 收尾後的 turn_seq
        state["user_turn_count"] = int(state.get("user_turn_count", 0) or 0) + 1

    if not typed:
        # 規則 DISPATCH_OPENS_TURN：帶派工標記的跨 session 訊息（首行「派工」或含 to-track- 派工檔路徑）開新回合。
        # 工作 session 整場只在開工句打過一次字，之後每封派工都該是新回合（預算、PASS 窗口、收割冷卻才會重算）；
        # 它不是使用者原話，turn_prompts 照樣不收（口令不認）。一般同伴訊息、背景通知只開續跑回合。
        if is_dispatch_message(peer_message_bodies(clean_prompt)):
            state["turn_prompts"] = []
            state["turn_typed"] = False
            _new_turn()
            state["turn_open"] = True
            return
        spent = int(state.get("last_commit_turn_seq", -1)) >= int(state.get("turn_prompts_seq", 0))
        if not has_list or (not state.get("turn_open") and spent):
            state["turn_prompts"] = []
        if not state.get("turn_open"):
            state["turn_typed"] = False                                  # 通知開的續跑回合：還沒有使用者打字
    elif state.get("turn_open") and has_list:
        state["turn_prompts"] = (state["turn_prompts"] + [typed])[-5:]
        if state.get("turn_typed") is False:                            # 續跑回合裡使用者的第一則字：使用者開的新回合
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
    track_turn_prompts(state, clean_prompt)
    # 使用者說「先這樣／跳過」不再在這裡清掉全部紅測清單：要 LLM 在收尾寫「不做｜<哪一支>：使用者說「<原句>」」，
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
    confirmed = state.get("confirmed_extractions", [])
    if confirmed:
        veto = any(kw in typed_lower for kw in ("否", "不要記", "別記", "取消記憶"))
        if veto:
            for ext in confirmed:
                _atom_debug_log(
                    "user-extract:rejected",
                    f"User vetoed: {ext.get('statement', '')[:80]}",
                    config,
                )
            state["confirmed_extractions"] = []
        else:
            for ext in confirmed:
                stmt = ext.get("statement", "")
                wr = ext.get("write_result")
                if wr in ("wrote", "deduped"):
                    lines.append(
                        f"偵測到決策語句：「{stmt}」— 已記為 atom。回覆「否」可攔截。"
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
                        f"偵測到決策語句：「{stmt}」— 已送萃取管線。回覆「否」可攔截。"
                    )
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
                    if OllamaClient is not None:
                        OllamaClient._clear_long_die_marker()
                    lines.append(
                        f"[Dual-Backend] 已永久停用 '{backend_name}'。"
                        f"如需重新啟用，修改 config.json 中 enabled: true。"
                    )
                else:
                    lines.append(f"[Dual-Backend] 停用 '{backend_name}' 失敗，請手動修改 config.json。")
            elif any(kw in typed_lower for kw in ("保持", "keep", "忽略")):
                if OllamaClient is not None:
                    OllamaClient._clear_long_die_marker()
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
