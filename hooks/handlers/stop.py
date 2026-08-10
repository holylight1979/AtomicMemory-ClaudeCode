"""
handlers/stop.py — Stop hook handler

四個 gate：
1. Test-Fail Gate（測試未綠 + 宣告完成 → 硬阻）
2. Evasion 偵測（軟糾正）
3. Scan-Report Gate（宣告完成但缺掃描報告 → 硬阻）
4. Sync Reminder Gate（modified_files>0 仍未 commit → 軟阻）
+ 一般 sync block 邏輯
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from wg_core import (
    _ensure_state, _now_iso, write_state, output_nothing, output_block,
    append_guard_log, WORKFLOW_DIR,
)
from wg_evasion import (
    claims_completion, detect_evasion,
    get_last_assistant_text, detect_missing_aec_emission,
    get_current_turn_text, read_transcript_tail,
)
from wg_episodic import _find_session_transcript
from wg_handoff import token_warn_payload
from handlers._shared import (
    _maybe_spawn_user_extract_worker,
    DOCDRIFT_AVAILABLE,
)

# Windows: 外呼 git/svn 時若不帶此 flag，無主控台的 hook 父行程會被配一個可見 console 視窗
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _find_vcs_root(start: Path) -> Optional[tuple]:
    """從 start 向上找最近的 VCS 根：.git（dir 或 worktree/submodule 的 file）或 .svn 目錄。

    純檔案系統 walk-up、零 subprocess——供 _detect_uncommitted_files 按根分組後，
    每根只跑一次 batch status。回 ("git"|"svn", root)；非工作區回 None。
    """
    cur = start
    while True:
        try:
            if (cur / ".git").exists():
                return ("git", cur)
            if (cur / ".svn").is_dir():
                return ("svn", cur)
        except OSError:
            return None
        if cur.parent == cur:
            return None
        cur = cur.parent


def _norm_for_match(p: str) -> str:
    """路徑正規化供集合比對：realpath + 正斜線；Windows 檔案系統不分大小寫 → casefold。"""
    s = os.path.realpath(p).replace("\\", "/")
    return s.casefold() if sys.platform == "win32" else s


def _git_dirty_set(root: Path, paths: List[str]) -> Optional[set]:
    """一次 `git status --porcelain -z` 查整組路徑；回 dirty 集合（_norm_for_match 鍵）。

    -z：NUL 分隔、不做引號跳脫（空白/非 ASCII 路徑安全）。rename 條目的 old-path
    以無狀態前綴的獨立 NUL 段出現——此處只關心「有無未提交變更」，new-path 段已足夠，
    誤切的 old-path 段進集合也不會與任何輸入路徑相符。查詢失敗回 None。
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "-z", "--", *paths],
            capture_output=True, text=True, timeout=5, creationflags=_NO_WINDOW,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    if r.returncode != 0:
        return None
    dirty: set = set()
    for entry in (r.stdout or "").split("\0"):
        if len(entry) > 3:
            dirty.add(_norm_for_match(str(root / entry[3:])))
    return dirty


def _svn_dirty_set(root: Path, paths: List[str]) -> Optional[set]:
    """一次 `svn status` 查整組路徑；回 dirty 集合。乾淨檔無輸出；輸出行 =
    7 欄狀態 + 空格 + 路徑（依傳入形式回顯，此處傳絕對路徑）。查詢失敗回 None。"""
    try:
        r = subprocess.run(
            ["svn", "status", *paths],
            cwd=str(root), capture_output=True, text=True, timeout=5,
            creationflags=_NO_WINDOW,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    if r.returncode != 0:
        return None
    dirty: set = set()
    for line in (r.stdout or "").splitlines():
        if len(line) > 8 and line[:7].strip():
            dirty.add(_norm_for_match(line[8:].strip()))
    return dirty


def _detect_uncommitted_files(
    modified_files: List[Dict[str, Any]],
) -> Optional[List[str]]:
    """偵測 modified_files 裡仍未提交的檔案。

    回傳:
      - List[str]: 未提交檔案路徑（已去重）
      - []: 全已提交
      - None: 偵測失敗（非 git/svn 工作區）— 跳過此閘

    路徑先按 VCS 根分組（_find_vcs_root walk-up，零 subprocess），每根一次
    batch status——N 檔從 ~2N 次 git/svn 子行程降為每根 1 次。
    """
    unique_paths: List[str] = []
    seen: set = set()
    for m in modified_files:
        p = (m or {}).get("path", "")
        if p and p not in seen:
            seen.add(p)
            unique_paths.append(p)
    if not unique_paths:
        return []

    groups: Dict[tuple, List[str]] = {}
    for path in unique_paths:
        if not os.path.exists(path):
            continue
        found = _find_vcs_root(Path(path).parent)
        if found:
            groups.setdefault(found, []).append(path)
    if not groups:
        return None

    uncommitted: List[str] = []
    detected_any_vcs = False
    for (kind, root), paths in groups.items():
        dirty = _git_dirty_set(root, paths) if kind == "git" else _svn_dirty_set(root, paths)
        if dirty is None:
            continue  # 該組查詢失敗（git/svn 執行檔不存在等）——比照單檔查詢失敗略過
        detected_any_vcs = True
        uncommitted.extend(p for p in paths if _norm_for_match(p) in dirty)

    if not detected_any_vcs:
        return None
    return uncommitted


_ACCESSED_FILES_CAP = 500  # accessed_files state 條目上限（超出裁最舊）


def _harvest_accessed_files(state: Dict[str, Any], transcript_text: str) -> bool:
    """從共用 transcript 尾段一次回收 Read 過的檔案到 accessed_files；回是否有新增。

    取代 PostToolUse matcher 含 Read 的做法（每次讀檔 spawn 一個 hook 行程，
    只為記一筆路徑）。同路徑只記首見。已知邊界（消費者 episodic 統計 /
    handoff 提示 / codex 脈絡皆 best-effort 訊號，可接受）：
      - 尾窗（read_transcript_tail）涵蓋不到的極早期讀取會漏
      - `at` 為回收時刻而非讀檔時刻；同 turn 內其他 Stop hook 讀到的
        accessed_files 慢一個 turn 邊界
    """
    if not transcript_text:
        return False
    accessed = state.setdefault("accessed_files", [])
    seen = {a.get("path") for a in accessed if isinstance(a, dict)}
    added = False
    trimmed = False
    for raw in transcript_text.splitlines():
        # 廉價預篩：多數行連 tool_use/Read 字樣都沒有，免逐行 json.loads
        if '"tool_use"' not in raw or '"Read"' not in raw:
            continue
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict) or obj.get("type") != "assistant":
            continue
        content = obj.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") == "Read"
            ):
                fp = (block.get("input") or {}).get("file_path", "")
                if fp and fp not in seen:
                    seen.add(fp)
                    accessed.append({"path": fp, "at": _now_iso()})
                    added = True
    # 上限 500（重讀量大的長 session 不無限累積 state）：裁最舊；被裁路徑之後
    # 再被 Read 會重新回收（消費端皆 best-effort 統計，可接受）。
    if len(accessed) > _ACCESSED_FILES_CAP:
        state["accessed_files"] = accessed[-_ACCESSED_FILES_CAP:]
        trimmed = True
    return added or trimmed


# ─── 取用端閉環稽核（AtomAudit Gate） ───────────────────────────


def _normalize_read_path(p: str) -> str:
    return (p or "").replace("\\", "/").lower()


_ATOM_AUDIT_LIST_MAX = 3  # 收尾訊息最多列名幾顆（其餘以計數帶過）


def _audit_pointer_atom_consumption(
    state: Dict[str, Any],
) -> Optional[tuple]:
    """取用端閉環：trigger 命中（＝與本場任務域吻合）但僅以一行路標注入
    （budget skip / cold）、且整場未 Read 的 atom → 回 (reason, names) 供
    Stop 閘要求三選一表態；無候選回 None。

    寫入端有閘（write-gate/funnel），取用端此前全靠模型自律——路標的具體性
    輸給 context 實體線索時就漏（實證：trigger 命中的肥 atom 被 budget skip
    成一行、全程未展開）。防噪內建：
      - 只稽核 source=trigger（bm25/vector/related 不催——related 擴散本就低確信）
      - 同 turn 注入不催（至少給模型一個完整 turn 決定要不要展開）
      - 消費判定用 Stop 已回收的 accessed_files（同 turn 的 Read 先於本判定入 state）
    """
    inj_log = state.get("injection_log") or []
    if not inj_log:
        return None
    turn_seq = int(state.get("turn_seq", 0))
    prompted = set(state.get("atom_audit_prompted") or [])
    accessed = {
        _normalize_read_path(a.get("path"))
        for a in (state.get("accessed_files") or [])
        if isinstance(a, dict)
    }
    seen: set = set()
    candidates: List[Dict[str, Any]] = []
    for rec in inj_log:
        if not isinstance(rec, dict):
            continue
        name = rec.get("name") or ""
        if not name or name in prompted or name in seen:
            continue
        if rec.get("source") != "trigger" or rec.get("form") not in ("skip", "cold"):
            continue
        if turn_seq and int(rec.get("turn_seq", 0)) >= turn_seq:
            continue  # 本 turn 才注入——不催
        rec_path = _normalize_read_path(rec.get("path"))
        suffix = f"/{name.lower()}.md"
        if any(ap == rec_path or ap.endswith(suffix) for ap in accessed):
            continue  # 已 Read（consumed）
        seen.add(name)
        candidates.append(rec)
    if not candidates:
        return None

    msg: List[str] = [
        "[Guardian:AtomAudit] 本 session 有 trigger 命中、但僅以一行路標注入"
        "（token 預算降級/cold）且全程未 Read 的 atom：",
    ]
    for rec in candidates[:_ATOM_AUDIT_LIST_MAX]:
        # 一律用絕對 path（rel 只相對該 atom 自己的 realm root，跨 realm 會斷鏈）
        msg.append(f"  - {rec['name']} → Read {rec.get('path') or rec.get('rel', '')}")
    if len(candidates) > _ATOM_AUDIT_LIST_MAX:
        msg.append(f"  …另 {len(candidates) - _ATOM_AUDIT_LIST_MAX} 顆（見 state injection_log）")
    msg.append(
        "路標命中＝該 atom 的 trigger 與本場任務域吻合，可能含本場獨有的教訓。"
        "請對每顆三選一表態（每 atom 本 session 只提醒一次，不阻工作）：\n"
        "  (a) 已從其他來源取得等價資訊——說明來源\n"
        "  (b) 確與本場任務無關——一句理由即可\n"
        "  (c) 現在補讀（Read 上列路徑）再收尾"
    )
    return "\n".join(msg), [r["name"] for r in candidates]


# ─── 注入→使用→結果 閉環歸因 ───────────────────────────────────


def _budgeted_embed_fn(raw_embed_fn, uconf: Dict[str, Any]):
    """embedding tiebreak 的全 turn 共用時間預算包裝。

    單次 tiebreak 最壞 2×embed_timeout_s（兩段 embed），多顆 atom 疊加會頂到
    Stop hook 上限。累計耗時超過 usefulness.embed_budget_s（預設 3s）→ 之後
    一律回 None（detect_atom_use 退回 lexical 主判）。預算耗盡浮 stderr 一行
    （fail-open 必告知）。raw_embed_fn 為 None 時原樣回 None。
    """
    if raw_embed_fn is None:
        return None
    try:
        budget_s = float(uconf.get("embed_budget_s", 3.0))
    except (TypeError, ValueError):
        budget_s = 3.0
    if budget_s <= 0:
        return raw_embed_fn
    spent = [0.0]
    exhausted_warned = [False]

    def _fn(a: str, b: str):
        if spent[0] >= budget_s:
            if not exhausted_warned[0]:
                exhausted_warned[0] = True
                print(
                    f"[usefulness] embed tiebreak turn budget exhausted "
                    f"({spent[0]:.1f}s ≥ {budget_s}s) — falling back to lexical",
                    file=sys.stderr,
                )
            return None
        t0 = time.monotonic()
        try:
            return raw_embed_fn(a, b)
        finally:
            spent[0] += time.monotonic() - t0

    return _fn


def _detect_turn_outcome(state: Dict[str, Any], last_text: str) -> Optional[bool]:
    """3 值 success 偵測（複用既有訊號）。回 True(+1)/False(0)/None(unknown=no-op)。

      - 0（fail）：**本 turn** failing_tests 非空 / 本 turn evasion_flag /
        wisdom_retry_count≥2（error / 糾正 / retry / evasion 任一）。
      - +1（success）：宣告完成（claims_completion）且無上述 fail 訊號（硬正向）。
      - None（unknown）：既無完成宣告也無 fail 訊號 → 不動 (α,β)，防雜訊污染。

    failing_tests 只認本 turn（entry turn_seq == state turn_seq）——全量累積會讓
    早前 turn 的舊失敗污染後續每個 turn 的 outcome。無 turn_seq 的 entry（升級前
    in-flight session）保守視為本 turn（fail-open，不漏 fail 訊號）。sync gate /
    TestFailGate 等其他消費者維持全量語意不變。
    """
    turn_seq = int(state.get("turn_seq", 0))
    failing = [
        f for f in (state.get("failing_tests") or [])
        if int((f or {}).get("turn_seq", turn_seq)) == turn_seq
    ]
    evasion = bool(state.get("evasion_flag"))
    retry = int(state.get("wisdom_retry_count", 0) or 0)
    if failing or evasion or retry >= 2:
        return False
    if last_text and claims_completion(last_text):
        return True
    return None


def _bump_outcome_stats(state: Dict[str, Any], outcome: Optional[bool]) -> None:
    """per-turn outcome 三值計數（success/fail/unknown）。SessionEnd flush 成
    unknown 比率遙測——unknown 系統性偏高＝完成語 regex 失配、α/β 晉升軌
    靜默停滯的早期訊號。與 α/β 歸因同守 once-per-turn（caller 已以
    usefulness_attributed_seq 守門）。"""
    stats = state.setdefault(
        "outcome_stats", {"success": 0, "fail": 0, "unknown": 0}
    )
    key = "success" if outcome is True else "fail" if outcome is False else "unknown"
    stats[key] = int(stats.get(key, 0)) + 1


def _attribute_usefulness(
    state: Dict[str, Any], config: Dict[str, Any], session_id: str,
    transcript, last_text: str, transcript_text: Optional[str] = None,
) -> None:
    """per-turn 注入→使用→結果歸因：對 turn_injected + 本 turn sub-agent 注入中
    「被判 used 且 outcome 決定性」者 → record_usefulness(α/β，走 funnel)。

    once-per-turn：以 turn_seq 守門（blocked turn 多次 Stop 不重複計）。fail-open。
    transcript_text 給定時（caller 以 read_transcript_tail 共用尾段）turn 文字
    從該字串解析、不再開檔；None 則自行讀（相容直接呼叫的測試）。
    """
    try:
        uconf = (config or {}).get("usefulness", {}) or {}
        if not uconf.get("enabled", True):
            return
        turn_seq = int(state.get("turn_seq", 0))
        if turn_seq and state.get("usefulness_attributed_seq") == turn_seq:
            return  # 本 turn 已歸因

        from lib.atom_access import record_usefulness
        from wg_atoms import detect_atom_use, resolve_atom_path, make_embed_tiebreak_fn

        rare_min = int(uconf.get("rare_token_min", 2))
        overlap_min = float(uconf.get("lexical_overlap_min", 0.18))
        embed_fn = _budgeted_embed_fn(make_embed_tiebreak_fn(config), uconf)

        turn_text = (
            get_current_turn_text(transcript, text=transcript_text)
            if (transcript or transcript_text) else ""
        )
        outcome = _detect_turn_outcome(state, last_text)
        _bump_outcome_stats(state, outcome)

        def _read(path_str: str) -> str:
            try:
                return Path(path_str).read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError, ValueError):
                return ""

        def _record(path_str: str, content: str, match_text: str, decided: Optional[bool]) -> Optional[bool]:
            if decided is None or not content or not match_text:
                return None
            det = detect_atom_use(
                content, match_text,
                rare_token_min=rare_min, overlap_min=overlap_min, embed_fn=embed_fn,
            )
            if not det.get("used"):
                return None
            record_usefulness(Path(path_str), used=True, success=decided, source="hook:usefulness")
            return decided

        attributed = []  # (atom, success) for telemetry

        # 1) UPS per-turn 注入（turn_injected）— 比對本 turn assistant 活動文字
        for entry in (state.get("turn_injected") or []):
            name = entry.get("name", "")
            path_str = entry.get("path", "")
            if not name or not path_str:
                continue
            res = _record(path_str, _read(path_str), turn_text, outcome)
            if res is not None:
                attributed.append((name, res))

        # 2) 本 turn sub-agent 注入（state["subagent_injections"]）
        #    use 偵測比對該 agent 的 output_summary（其實際產物）；outcome 疊 agent 狀態。
        for rec in (state.get("subagent_injections") or []):
            if rec.get("attributed"):
                continue
            status = str(rec.get("status", "") or "").lower()
            sub_outcome = outcome
            if any(k in status for k in ("error", "fail", "abort", "cancel")):
                sub_outcome = False  # agent 出錯 → fail（覆寫 turn outcome）
            match_text = (rec.get("output_summary", "") or "") + "\n" + turn_text
            for aname in (rec.get("atoms") or []):
                p = resolve_atom_path(aname)
                if p is None:
                    continue
                res = _record(str(p), _read(str(p)), match_text, sub_outcome)
                if res is not None:
                    attributed.append((aname, res))
            rec["attributed"] = True  # 本 turn 已處理（含 no-op，避免下 turn 重算）

        if turn_seq:
            state["usefulness_attributed_seq"] = turn_seq
        if attributed:
            state.setdefault("usefulness_log", []).append({
                "turn_seq": turn_seq,
                "outcome": ("+1" if outcome is True else "0" if outcome is False else "unknown"),
                "atoms": [{"atom": a, "success": s} for a, s in attributed],
                "at": _now_iso(),
            })
            state["usefulness_log"] = state["usefulness_log"][-50:]
    except Exception as e:
        print(f"usefulness attribution error: {e}", file=sys.stderr)


# ─── Stage 3: Deep Post-Mortem Gate（高 effort 失敗 → Claude 深寫指令）──────────


def _should_deep_postmortem(
    state: Dict[str, Any], config: Dict[str, Any], claims_done: bool,
) -> bool:
    """是否要在本 Stop 注入「深寫 post-mortem」指令。

    觸發＝(effort 訊號任一) AND (真失敗訊號任一)：
      effort：wisdom_retry_count>=2 ∨ fix_escalation_triggered
      real_failure：failing_tests 非空 ∨ evasion_flag ∨ 未宣告完成（not claims_done）
    為何 AND：疊一個真失敗訊號，才把「高 effort 成功」與「反覆修不好」區分開。
    effort 只採 retry / fix_escalation——兩者都已在 track_retry 層以 failing_tests
    error-gate，是誠實的「失敗中反覆」訊號。不採同檔 edit 次數：它未 failure-gate、
    對正常重度迭代開發本就會超標（edit 次數 ≠ 失敗）。

    ★獨立預算（不與 Sync/Scan/TestFail 共用 stop_gate_max_blocks）：DPM 本就一次性
    ——deep_postmortem_done 一設即永不再觸，anti-loop 由此 one-shot 保證，無需再疊
    共用計數。曾共用實測會餓死：Sync(1)+TestFail(1) 就吃光 2-block 預算，輪到 DPM 時
    stop_count>=max 而永不觸發，偏偏那正是「反覆修不好」最該補 post-mortem 的 session。
    其它 gate 各自以自身 flag/counter 自限（sr_count / scan_report_warned），唯 DPM
    曾被共用預算綁住；正名獨立後與眾 gate 對稱。config 未關閉才觸發。

    純判定、無副作用——claims_done 由 caller 算好傳入（避免在此讀 transcript）；
    副作用（設旗標、計數、output_block）由 gate 處理。
    """
    dpm = (config or {}).get("deep_postmortem", {}) or {}
    if not dpm.get("enabled", True):
        return False
    if state.get("deep_postmortem_done"):  # 一次性即獨立預算＝1，anti-loop 由此保證
        return False
    effort = (
        int(state.get("wisdom_retry_count", 0) or 0) >= 2
        or bool(state.get("fix_escalation_triggered"))
    )
    real_failure = (
        bool(state.get("failing_tests"))
        or bool(state.get("evasion_flag"))
        or not claims_done
    )
    return effort and real_failure


def _dpm_marker(session_id: str) -> Path:
    """DPM one-shot 的檔案側 marker。

    state 旗標在併發 hook 行程的全量覆寫下可能被舊快照競掉（旗標寫入後被他行程
    write_state 蓋回），marker 檔不受 state 覆寫影響；gate 以 state 旗標 OR marker
    判定，保證真 one-shot。
    """
    return WORKFLOW_DIR / "dpm-done" / f"{session_id}.flag"


_DEEP_POSTMORTEM_INSTRUCTION = (
    "[Guardian:DeepPostMortem] 偵測到高 effort 失敗訊號（失敗中反覆重試 /"
    " fix-escalation）。失敗骨架已由 hook 自動落地，但根因與設計脈絡只有你知道。\n"
    "結束前請用 atom_write 補一條完整 post-mortem（寫入既有 failure atom，或"
    " realm=local、domain 視主題新建），涵蓋：\n"
    "  - 始末：觸發場景 → 錯誤行為 → 最終正確做法\n"
    "  - 根因：為何會犯（非表面症狀）\n"
    "  - 該區設計原理：出錯那塊程式/機制當初為何這樣設計\n"
    "  - 運作邏輯：它實際怎麼跑、哪個環節斷掉\n"
    "  - 防再犯：下次如何提早攔截\n"
    "寫完即可宣告完成；此為一次性提示，本 session 不再出現。"
)


# ─── 迴歸累積提示（驗收真命中 → 建議補測試/落 atom）───────────────


def _acceptance_regression_hint(
    state: Dict[str, Any], session_id: str, config: Dict[str, Any],
) -> Optional[str]:
    """驗收裁判真命中的迴歸累積提示（非強制）：本 session 的 acceptance-audit.jsonl
    有 verdict=fail 且 severity=high（enforce 級——回測兩輪 4/4 零誤擋的那一級）
    → 收尾訊息搭車建議 (a) 補測試案例 (b) 模式類落 atom。

    純 piggyback（同 token 預警模式）：只搭既有 block 訊息帶出，不獨立打斷；
    一次性（acceptance_hint_emitted，隨該 gate 的 write_state 固化）；
    不建佇列不建表——做不做由模型當場判斷，誤判忽略即可。
    fail-open：讀檔/解析失敗 stderr 浮訊號後回 None。
    """
    try:
        cfg = (config or {}).get("acceptance_regression_hint", {}) or {}
        if not cfg.get("enabled", True):
            return None
        if state.get("acceptance_hint_emitted"):
            return None
        audit_path = WORKFLOW_DIR / "acceptance-audit.jsonl"
        if not audit_path.exists():
            return None
        slugs: List[str] = []
        hits = 0
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            if session_id not in line:  # 廉價預篩，免逐行 json.loads
                continue
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(rec, dict) or rec.get("session_id") != session_id:
                continue
            if rec.get("verdict") != "fail" or rec.get("severity") != "high":
                continue
            hits += 1
            slug = rec.get("task_slug") or Path(str(rec.get("spec_path", ""))).stem
            if slug and slug not in slugs:
                slugs.append(slug)
        if not hits:
            return None
        return (
            f"\n[Guardian:RegressionHint] 本 session 驗收裁判有 {hits} 筆真命中級"
            f"判定（fail/high；任務：{', '.join(slugs[:3])}）。"
            "抓到的漏修完就過去＝同型錯下次照犯，建議（非強制、當場判斷）：\n"
            "  (a) 在該專案為漏掉的行為補一個測試案例（永久防線）\n"
            "  (b) 屬跨任務模式類教訓 → atom_write 落 atom\n"
            "裁判誤判或防線已存在則忽略即可，不建佇列不追蹤。"
        )
    except Exception as e:
        print(f"[Guardian:RegressionHint] hint error (fail-open): {e}", file=sys.stderr)
        return None


def handle_stop(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    max_blocks = config.get("stop_gate_max_blocks", 2)
    stop_count = state.get("stop_blocked_count", 0)
    phase = state.get("phase", "working")

    # ── Test-Fail Gate ────────────────────────────────────────────
    failing = state.get("failing_tests") or []
    cwd = state.get("session", {}).get("cwd", "") or input_data.get("cwd", "")
    transcript = _find_session_transcript(session_id, cwd) if cwd else None
    # 單次 tail-read：本函式所有 transcript 消費者（last_text / token 預警 /
    # usefulness turn 文字）共用同一份尾段，取代先前各自全檔讀取。
    transcript_text = read_transcript_tail(transcript)
    last_text = get_last_assistant_text(transcript, text=transcript_text)
    # accessed_files 回收（取代 per-Read PostToolUse hook）——先寫進 state，
    # 後續任何 gate 的 write_state 也會一併固化；此處立即寫防走到不寫 state 的路徑。
    if _harvest_accessed_files(state, transcript_text):
        write_state(session_id, state)

    # ── Layer 1: token 預警 proxy（piggyback 既有 block，不獨立打斷）──────
    # 早段算一次預警句（純函式、無副作用）；於下方各 gate 將 output_block(reason)
    # 前用 _piggyback append。token_warn_emitted 旗標只在「實際 append」時才標，
    # 並隨該 gate 的 write_state 固化（一次性、整 session 一次）。詳見
    # plans/wise-wobbling-gem.md Layer 1 與 Q3 門檻取捨。
    _token_warn = token_warn_payload(
        state, config, transcript, transcript_text=transcript_text
    )
    # 迴歸累積提示同為 piggyback payload：驗收裁判真命中 → 建議補測試/落 atom。
    _accept_hint = _acceptance_regression_hint(state, session_id, config)

    def _piggyback(reason: str) -> str:
        if _token_warn:
            state["token_warn_emitted"] = True
            reason = reason + _token_warn
        if _accept_hint:
            state["acceptance_hint_emitted"] = True
            reason = reason + _accept_hint
        return reason

    if failing and claims_completion(last_text):
        state["stop_blocked_count"] = stop_count + 1
        reason = _piggyback(
            f"[Guardian:TestFailGate] 測試未綠（{len(failing)} 項失敗），"
            "不得宣告完成。\n"
            + "\n".join(
                f"  - {f.get('cmd', '')[:60]}: "
                f"{(f.get('summary', '').splitlines() or [''])[0][:100]}"
                for f in failing[-3:]
            )
            + "\n選 (a) 修復 (b) 明確說明為何不修並標記為已知 regression "
            "(c) 降級任務定義。不得籠統帶過。"
        )
        write_state(session_id, state)
        output_block(reason)
        return

    if not state.get("evasion_flag"):
        recent_prompts = state.get("recent_user_prompts", []) or []
        ev = detect_evasion(last_text, recent_prompts)
        if ev:
            ev["at"] = _now_iso()
            state["evasion_flag"] = ev
            # 證據暫存（evasion_flag 會被下輪 UPS 注入後清空；事件列表留存供
            # AEC (b) 欄 cross-check——hook 實測 vs 模型自評，不信自評）
            events = state.setdefault("evasion_events", [])
            events.append({
                "phrase": ev.get("phrase", ""),
                "turn_seq": int(state.get("turn_seq", 0)),
                "at": ev["at"],
            })
            state["evasion_events"] = events[-10:]
            append_guard_log("evasion", {
                "session_id": session_id,
                "phrase": ev.get("phrase", ""),
                "excerpt": (ev.get("context_excerpt", "") or "")[:120],
            })
            write_state(session_id, state)

    # ── Scan-Report Gate ────────────────────────────────────────
    # 降條件觸發 — 只在動 core 檔或多檔（≥min_files_to_block）且宣告完成時要求收尾檢核；
    # 純單檔/文件小改不觸發（避免過度觸發成儀式性負擔，非防退避）。
    mod_files_all = state.get("modified_files", []) or []
    # 只認「本 session 自己 Edit/Write 的檔」——共用工作樹/merged state 下，他 session
    # 改的 core 檔（session_id 不符）不得誤觸發本 session 的收尾檢核。未標記 session_id
    # 的 legacy entry 保守視為本 session（fail-open，不漏防退避）。
    own_mod_files = [
        m for m in mod_files_all
        if (m or {}).get("session_id", session_id) == session_id
    ]
    # 純 VCS commit turn 豁免收尾檢核：本 turn 已把工作寫進 VCS 歷史（可稽核＝與「藏」相反），
    # anti-evasion 目的在 commit 那刻消解。不開後門——豁免綁「本 turn 真的 commit 了」
    # （post_tool_use 記的 last_commit_turn_seq），而非「本 turn 沒 Edit」；光宣告完成不 commit
    # 仍被擋。未 commit 就 commit 的檔仍由 SyncReminder / 一般 block 兜底。
    turn_seq = int(state.get("turn_seq", 0))
    committed_this_turn = bool(turn_seq) and state.get("last_commit_turn_seq") == turn_seq
    # emit 滿足＝本回合有呼叫 anti_evasion_report。★雙鍵（turn_seq **且** session_id）為硬性：
    # merged/sibling session 共用同一實體 state 檔且共用同一 turn_seq 計數器，唯 session_id 能
    # 區辨——否則隔壁 session 的 emit 會誤放行本 session（重演 own_mod_files 要防的洩漏）。
    # bool(turn_seq) 護欄：防 turn_seq==0 的 fallback state 以 0==0 假滿足。
    aec = state.get("anti_evasion_report") or {}
    emitted_this_turn = (
        bool(turn_seq)
        and aec.get("turn_seq") == turn_seq
        and aec.get("session_id") == session_id
    )
    if own_mod_files and not state.get("scan_report_warned") and not committed_this_turn:
        recent_prompts = state.get("recent_user_prompts", []) or []
        sr_min_files = int(config.get("min_files_to_block", 2))
        if detect_missing_aec_emission(
            last_text, own_mod_files, recent_prompts, sr_min_files, emitted_this_turn
        ):
            state["stop_blocked_count"] = stop_count + 1
            state["scan_report_warned"] = True  # 保留 one-shot anti-nag（比照現況）
            reason = _piggyback(
                "[Guardian:ScanReport] 宣告完成且本 session 動到 core 檔/多檔（達收尾檢核門檻），"
                "但本回合未 emit anti_evasion_report，違反 IDENTITY「反退避契約」。\n"
                "請呼叫 MCP tool anti_evasion_report(a, b, c, d) 提交收尾檢核——內容走 HUD、"
                "chat 只留折疊 chip：\n"
                "  (a) 缺失發現與修補清單：`- 檔:行 — 改了什麼`；無則填「無」。**必寫**\n"
                "  (b) AI 逃避通報：本次有/沒有 忽略 / 偷埋的現象；**僅發生時填**，否則「無」\n"
                "  (c) Token 累積警示：見 hook `[Auto-Handoff]` 預警則判斷失真並附接續 prompt；**僅發生時填**，否則「無」\n"
                "  (d) 衍生暫存清單：本次衍生暫存檔/資料夾（預設直接刪）；**必寫**，無則「無」\n"
                "四參都 required、未發生填「無」。不得用 prose「不在範圍 / 留給未來」籠統帶過。"
            )
            write_state(session_id, state)
            output_block(reason)
            return

    # HUD 不可達且本回合 emit 為 notable/real-evasion → 大聲 fallback 回 chat（可觀測性鐵律：
    # push 不到窗不得 fail-silent）。post_tool_use 標旗，此處消費一次（新 emit 再標則再補，
    # 不永久靜音 real-evasion）。Node tool chip 是 emit 當下的主要 UX 面；本 fallback 是
    # Python 端獨立的觀測保證，不倚賴窗是否渲染。emit 閘本身已放行（見上），此處不再擋 emit。
    if state.get("aec_hud_fallback"):
        state["aec_hud_fallback"] = False  # 消費，避免重播
        state["stop_blocked_count"] = stop_count + 1
        sev = aec.get("severity", "notable")
        fb = [
            f"[Guardian:AEC] HUD 視窗未開啟，{sev} 收尾檢核改回 chat 呈現（不 fail-silent）："
        ]
        for _k, _label in (("a", "(a) 缺失修補"), ("b", "(b) 逃避通報")):
            _v = (aec.get(_k) or "").strip()
            if _v and _v != "無":
                fb.append(f"  {_label}：{_v}")
        # cross-check 升級：模型自評 (b)=無但 hook 實測退避 → 附 hook 證據（不信自評）
        if aec.get("severity_upgraded_by"):
            fb.append("  ⚠ severity 由 hook cross-check 升級——(b) 自評「無」與 hook 實測不符：")
            for _e in (aec.get("hook_evidence") or [])[:3]:
                fb.append(
                    f"    - turn {_e.get('turn_seq', '?')}: 退避語『{_e.get('phrase', '')}』"
                )
        write_state(session_id, state)
        output_block(_piggyback("\n".join(fb)))
        return

    # ── Sync Reminder Gate ──────────────────────────────────────
    sr_config = config.get("sync_reminder", {}) or {}
    sr_enabled = sr_config.get("enabled", True)
    sr_max = int(sr_config.get("max_reminders", 1))
    sr_count = int(state.get("sync_reminder_count", 0))
    # session-filter：只認本 session 自己改的檔（own_mod_files）。共用工作樹下，協調
    # session 不得替他 session 未提交的檔誤觸發同步提醒（比照 Scan-Report 閘的過濾）。
    if (
        sr_enabled
        and own_mod_files
        and not state.get("muted")
        and phase not in ("done", "syncing")
        and sr_count < sr_max
    ):
        uncommitted = _detect_uncommitted_files(own_mod_files)
        if uncommitted:
            state["sync_reminder_count"] = sr_count + 1
            state["stop_blocked_count"] = stop_count + 1
            # 訊息瘦身：檔案清單不進 chat（statusline 常駐示數、模型自行 git status）
            reason = _piggyback(
                f"[Guardian:SyncReminder] 偵測到 {len(uncommitted)} 個已修改但"
                "尚未提交的檔案（清單自行 git status），依 rules/core.md"
                "「完成修改後主動提出 .git→commit+push」應提示同步。\n"
                "請選一個方向：\n"
                "  (a) 上 GIT — 立刻 commit + push\n"
                "  (b) 我不打算上 — 請說明原因（會跳過本次提醒）\n"
                "  (c) 已在前一輪上過了 — git/svn clean 後本 gate 自動清旗標"
            )
            write_state(session_id, state)
            output_block(reason)
            return

    # ── Atom Consumption Audit Gate（取用端閉環稽核）──────────────
    # 排序：correctness / sync 之後（那些優先）、DPM 之前；沿用 stop_gate_max_blocks
    # 全域預算（第 3 次強制放行）。per-atom 一次（atom_audit_prompted）防轟炸。
    # fail-open：判定任何失敗 → stderr 浮訊號後照常放行，不比既有慣例更擋人。
    if (
        (config.get("atom_audit", {}) or {}).get("enabled", True)
        and stop_count < max_blocks
    ):
        try:
            aa = _audit_pointer_atom_consumption(state)
        except Exception as e:
            aa = None
            print(f"[Guardian:AtomAudit] audit error (fail-open): {e}", file=sys.stderr)
        if aa:
            aa_reason, aa_names = aa
            prompted = state.setdefault("atom_audit_prompted", [])
            prompted.extend(n for n in aa_names if n not in prompted)
            state["stop_blocked_count"] = stop_count + 1
            write_state(session_id, state)
            output_block(_piggyback(aa_reason))
            return

    # ── Deep Post-Mortem Gate（Stage 3）────────────────────────
    # (effort 訊號) AND (真失敗訊號) + 本 session 未深寫過 → 注入指令，要 Claude 結束前用
    # atom_write 補完整 post-mortem。deep_postmortem_done 一次性防重複＝獨立預算 1；
    # 排在 correctness/sync gate 之後（那些優先）但★不共用 stop_gate_max_blocks——
    # 否則 Sync+TestFail 先吃光預算就餓死 DPM（見 _should_deep_postmortem docstring 實證）。
    claims_done = bool(last_text and claims_completion(last_text))
    if (_should_deep_postmortem(state, config, claims_done)
            and not _dpm_marker(session_id).exists()):
        state["deep_postmortem_done"] = True
        try:
            marker = _dpm_marker(session_id)
            marker.parent.mkdir(parents=True, exist_ok=True)
            cutoff = time.time() - 7 * 86400  # 舊 marker 順手清，防執行期狀態檔累積
            for old in marker.parent.glob("*.flag"):
                if old.stat().st_mtime < cutoff:
                    old.unlink()
            marker.touch()
        except OSError:
            pass
        state["stop_blocked_count"] = stop_count + 1
        reason = _piggyback(_DEEP_POSTMORTEM_INSTRUCTION)
        write_state(session_id, state)
        output_block(reason)
        return

    # ── 注入→使用→結果 閉環歸因（correctness gates 通過後、per-turn 一次性）──
    # 走到這裡代表本 Stop 未被 test-fail/scan-report 等 correctness gate 攔下 →
    # 該 turn 的對錯訊號已落定。turn_seq 守門一次性；write_state 立即固化標記
    # （防後續 phase=done / muted 等不寫 state 的終止路徑導致重複計 α/β）。
    _attribute_usefulness(
        state, config, session_id, transcript, last_text, transcript_text
    )
    write_state(session_id, state)

    # ── Anti-loop guard ─────────────────────────────────────────
    if stop_count >= max_blocks:
        state["phase"] = "done"
        write_state(session_id, state)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    if phase in ("done", "syncing"):
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    # session-filter：底部一般 block 亦只數本 session 自己改的檔（own_mod_files）——
    # 協調 session（own 為空）不因共用樹上他 session 的檔而誤觸發。kq_count 不過濾：
    # knowledge_queue 是本 session 自己的待記知識，即使 own 檔為 0 仍是本 session 責任。
    mod_count = len(own_mod_files)
    kq_count = len(state.get("knowledge_queue", []))
    unique_files = list({m["path"] for m in own_mod_files})
    min_files = config.get("min_files_to_block", 2)

    if state.get("muted"):
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    if mod_count == 0 and kq_count == 0:
        state["phase"] = "done"
        write_state(session_id, state)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    if len(unique_files) < min_files and kq_count == 0:
        state["phase"] = "done"
        write_state(session_id, state)
        _maybe_spawn_user_extract_worker(session_id, state, config)
        output_nothing()
        return

    state["stop_blocked_count"] = stop_count + 1

    file_names = ", ".join(f.rsplit("/", 1)[-1] for f in unique_files[:8])

    reason = (
        f"[Workflow Guardian] {len(unique_files)} file(s) modified"
        + (f", {kq_count} knowledge pending" if kq_count else "")
        + f". Files: {file_names}.\n"
        "Sync: _AIDocs→_CHANGELOG | knowledge→atom | .git→add+commit+push | .svn→add+commit"
    )

    if DOCDRIFT_AVAILABLE:
        try:
            dp = state.get("docdrift_pending", {})
            if dp:
                docs = sorted(set(v["doc"] for v in dp.values()))
                reason += f"\n[DocDrift] {len(dp)} source change(s) → consider updating: {', '.join(docs[:5])}"
        except Exception:
            pass

    reason = _piggyback(reason)
    write_state(session_id, state)
    _maybe_spawn_user_extract_worker(session_id, state, config)

    output_block(reason)
