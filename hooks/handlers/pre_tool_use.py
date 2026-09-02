"""
handlers/pre_tool_use.py — PreToolUse hook handler

對 Write/Edit 進行 atom 格式/Confidence gate + memory 路徑防呆 + svn test block。
"""

import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (
    WORKFLOW_DIR,
    output_json, output_nothing,
    check_memory_path_block, check_svn_test_block,
    check_cross_realm_write, check_cross_realm_mcp_cmd, check_cross_realm_bash,
    read_state, get_transcript_path, append_guard_log,
    _atom_debug_log,
)

# sub-agent 注入 budget（緊湊，守 token 紅線；2-3 顆最高活化）
_SUBAGENT_INJECT_BUDGET = 700


_CONFIDENCE_FRONTMATTER_RE = re.compile(r"^- Confidence:\s*(\[[臨觀固]\])", re.MULTILINE)
_SOLID_INLINE_RE = re.compile(r"^- \[固\]", re.MULTILINE)
_OBSERVED_INLINE_RE = re.compile(r"^- \[觀\]", re.MULTILINE)


def _scan_atom_confidence(content: str) -> Dict[str, Any]:
    """Parse confidence signals from atom content."""
    fm = _CONFIDENCE_FRONTMATTER_RE.search(content)
    return {
        "frontmatter": fm.group(1) if fm else None,
        "solid_inline": bool(_SOLID_INLINE_RE.search(content)),
        "observed_inline": bool(_OBSERVED_INLINE_RE.search(content)),
    }


def _check_memory_atom_format(
    tool_name: str, tool_input: Dict[str, Any]
) -> Optional[str]:
    """Memory write must follow atom format AND new atoms must start at [臨]."""
    if tool_name != "Write":
        return None
    file_path_raw = tool_input.get("file_path", "")
    file_path = file_path_raw.replace("\\", "/")
    if "/.claude/memory/" not in file_path or not file_path.endswith(".md"):
        return None
    if "/_staging/" in file_path:
        return None
    if "/_pending_review/" in file_path:
        return None
    fname = file_path.rsplit("/", 1)[-1]
    if fname.startswith("_") or fname == "MEMORY.md" or fname.startswith("episodic-"):
        return None
    if fname == "role.md" and ("/personal/" in file_path or "/roles/" in file_path):
        return None
    full_content = tool_input.get("content", "")
    content_head = full_content[:300]
    required = [
        "- Scope:", "- Confidence:", "- Trigger:",
        "- Last-used:", "- Confirmations:", "- ReadHits:",
    ]
    hits = sum(1 for r in required if r in content_head)
    if hits < 3:
        return (
            f"[Guardian:AtomFormat] 偵測到寫入 {file_path}\n"
            f"但內容不符合原子格式（缺少 Scope/Confidence/Trigger 等 frontmatter，僅 {hits}/5 命中）。\n"
            "請改用 atom_write MCP（自動產生標準 frontmatter + 索引登記 + 去重檢查）：\n"
            "  mcp__workflow-guardian__atom_write(scope=\"shared\", project_cwd=\"...\", ...)\n"
            "如為臨時暫存，請寫入 _staging/ 子目錄（自由格式允許）。\n"
            "如為索引/變更日誌，請以 _ 開頭命名（如 _NOTES.md）。"
        )

    try:
        is_new = not Path(file_path_raw).exists()
    except OSError:
        is_new = True
    if is_new:
        sig = _scan_atom_confidence(full_content)
        fm = sig["frontmatter"]
        if fm and fm != "[臨]":
            return (
                f"[Guardian:AtomConfidence] 新 atom {fname} frontmatter Confidence={fm}，"
                "違反語意契約：新 atom 必須以 [臨] 起始（[觀]/[固] 反映跨 session 穩定度，"
                "首寫無法主張）。\n"
                "請改用 atom_write MCP（mode=create，confidence='[臨]'）。"
            )
        if sig["solid_inline"] or sig["observed_inline"]:
            tags = []
            if sig["solid_inline"]:
                tags.append("[固]")
            if sig["observed_inline"]:
                tags.append("[觀]")
            return (
                f"[Guardian:AtomConfidence] 新 atom {fname} 內文含 {'/'.join(tags)} "
                "標籤，違反語意契約：新 atom 的知識行也必須以 [臨] 起始，待跨 session 確認後再晉升。\n"
                "請改用 atom_write MCP（mode=create，knowledge 各行 prefix 為 '[臨]'）。"
            )
    return None


def _check_feedback_routing_advisory(
    tool_name: str, tool_input: Dict[str, Any]
) -> Optional[str]:
    """V5+: 偵測 memory/feedback-*.md Write/Edit → 回 advisory（不阻擋）。

    feedback-* atoms 物理居 memory/Failures/<主題>/（舊址 _AIDocs/Failures/ 遷移中）；
    走 atom_write MCP 自動路由。
    """
    if tool_name not in ("Write", "Edit"):
        return None
    fp_raw = tool_input.get("file_path", "") or ""
    fp = fp_raw.replace("\\", "/")
    if "/.claude/memory/" not in fp or not fp.endswith(".md"):
        return None
    fname = fp.rsplit("/", 1)[-1]
    if not fname.startswith("feedback-"):
        return None
    return (
        "[Guardian:RoutingAdvice] 偵測 memory/feedback-* 寫入。\n"
        f"路徑：{fp_raw}\n"
        "feedback-* atoms 物理居 memory/Failures/<主題>/（舊址 _AIDocs/Failures/ 遷移中）；"
        "走 atom_write MCP 自動路由。請改用：\n"
        "  mcp__workflow-guardian__atom_write(scope=\"global\", title=\"feedback-...\", ...)\n"
        "MCP 會自動路由到 memory/Failures/<主題>/（含索引同步 + access.json）。\n"
        "詳見 _AIDocs/SPEC_ATOM_V5.md「Atom 存放擴展」段。"
    )


# ─── Pre-Action Notice Gate（PAN，Hermes 技轉）────────────────────────────
# 每使用者回合首次「會動手」工具（Write/Edit/NotebookEdit/非唯讀 Bash/
# 非唯讀 PowerShell）呼叫前，檢查本 turn 是否已有可見預告（「執行目標」+
# 「預估/概估」+ 實質內容）。
# mode: observe=只落 guard log / warn=systemMessage 提醒 / deny=攔 + 補救模板
#（每回合上限 max_denies_per_turn，超過強制放行 + log；lenient_first_miss=true
# 時 deny 模式首 miss 降 warn，第 2 次起才 deny——同回合快路徑偵測不可靠的緩衝，
# 見 atom pan-hermes不移植部件與vscode-text-block不落盤實測）。
# compaction continuation 回合（turn 首 user 訊息命中
# harness 續接敘述特徵）整回合豁免。通過寫
# workflow/pan-pass/{sid}-t{turn}.flag（armed 快路徑，回合內全放；marker 抗
# 併發覆寫，仿 dpm-done）。sidechain/resume 保底：state 無 turn_seq 即 fail-open。
# 全程 fail-open；觸發事件落 Logs/guard-pre-action-notice.jsonl。

_PAN_GUARD = "pre-action-notice"
_PAN_GATED_TOOLS = ("Write", "Edit", "NotebookEdit", "Bash", "PowerShell")
_PAN_GOAL_LABEL = "執行目標"
_PAN_TIME_LABELS = ("預估", "概估")
# 實質內容判定的剝除字元集：空白（含全形）、標點、裝飾、括號。
_PAN_STRIP_CHARS = (
    " \t\r\n　"
    "：:，,。．.、；;！!？?…~～"
    "*_#>-—＝=`・•"
    "()（）[]【】「」『』<>＜＞"
)
# 佔位符防呆：deny 模板的「<一句話目標>」被盲目複誦時，整個 <…> span（含內文）
# 視為佔位符移除，不得冒充實質內容。
_PAN_PLACEHOLDER_RE = re.compile(r"[<＜][^<>＜＞\n]{0,60}[>＞]")
_PAN_PURE_TIME_RE = re.compile(
    r"^[0-9０-９一二三四五六七八九十半約\s]*"
    r"(分鐘|分|秒鐘|秒|小時|時|hrs?|mins?|secs?|天|週)$",
    re.IGNORECASE,
)
_PAN_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
# Compaction continuation 豁免：壓縮續接回合的 turn 首 user 訊息是 harness 生成
# 的固定敘述（probe first_user_head 特徵）；該回合預告語境已斷，整回合放行。
_PAN_CONTINUATION_MARKERS = (
    "This session is being continued from a previous conversation",
    "Please continue the conversation from where we left it",
)

_PAN_FAIL_DETAIL = {
    "no_goal_label": "缺「執行目標」標籤",
    "no_est_label": "缺「預估」或「概估」標籤",
    "goal_blank": "「執行目標」後沒有實質內容",
    "goal_time_masq": "「執行目標」後只有時間，缺具體目標",
    "est_blank": "「預估/概估」後沒有實質內容",
}

_PAN_FALLBACK_DENY = (
    "⛔ [Guardian:PreActionNotice] 本回合尚未輸出動手前預告（{fail_detail}），工具呼叫已暫擋。\n"
    "請先以使用者可見的一般文字輸出「執行目標：<具體目標>；預估 <時間或工作量>」，"
    "再重新呼叫工具。（第 {n}/{max} 次提醒）"
)


def pan_validate_notice(visible_text: str) -> Tuple[bool, str]:
    """Hermes 規則移植：雙標籤 + 實質內容 + 時間冒充目標防禦。

    回 (ok, fail_code)。全文任一「執行目標…預估/概估」組合通過即 pass
    （模型寫壞一次再補好可過）。驗證前剝 code fence（引用範例不冒充）。
    """
    if not isinstance(visible_text, str) or not visible_text.strip():
        return False, "no_goal_label"
    text = _PAN_CODE_FENCE_RE.sub("", visible_text)
    idx = 0
    found_goal = False
    last_fail = "no_est_label"
    while True:
        g = text.find(_PAN_GOAL_LABEL, idx)
        if g < 0:
            break
        found_goal = True
        idx = g + len(_PAN_GOAL_LABEL)
        rest = text[idx:]
        hits = [
            (p, lbl) for lbl in _PAN_TIME_LABELS
            if (p := rest.find(lbl)) >= 0
        ]
        if not hits:
            last_fail = "no_est_label"
            continue
        t_pos, t_lbl = min(hits)
        goal_seg = rest[:t_pos]
        goal_core = _PAN_PLACEHOLDER_RE.sub("", goal_seg)
        for ch in _PAN_STRIP_CHARS:
            goal_core = goal_core.replace(ch, "")
        if not goal_core:
            # 目標段剝空：緊鄰時間標籤（執行目標：預估…）視為時間冒充
            last_fail = "goal_time_masq" if len(goal_seg.strip()) <= 2 else "goal_blank"
            continue
        if _PAN_PURE_TIME_RE.match(goal_core):
            last_fail = "goal_time_masq"
            continue
        est_seg = rest[t_pos + len(t_lbl):].split("\n", 1)[0]
        est_core = _PAN_PLACEHOLDER_RE.sub("", est_seg)
        for ch in _PAN_STRIP_CHARS:
            est_core = est_core.replace(ch, "")
        if not est_core:
            last_fail = "est_blank"
            continue
        return True, ""
    return (False, last_fail) if found_goal else (False, "no_goal_label")


def pan_is_readonly_bash(command: str, pan_cfg: Dict[str, Any]) -> bool:
    """Bash/PowerShell 共用唯讀判定（全過才唯讀；解析失敗保守回 False=gated）。

    ① heredoc → gated；② redirect 目標非 null device（含 `$null`）→ gated；
    ③ &&/||/;/| 切段，每段首綴須命中白名單（cd 為透明段例外）；
    ④ find 段含 -delete/-exec → gated。
    PowerShell 語法差異在保守側自然收斂：cmdlet 靠白名單前綴（小寫比對），
    here-string/呼叫運算子 `&`/變數賦值段都不會命中白名單 → gated。
    """
    try:
        cmd = (command or "").strip()
        if not cmd:
            return True
        if "<<" in cmd:
            return False
        tmp = re.sub(r"\d?>\s*&\d", "", cmd)  # 2>&1
        tmp = re.sub(r"\d?>>?\s*(/dev/null|nul|\$null)\b", "", tmp, flags=re.IGNORECASE)
        if ">" in tmp:
            return False
        prefixes = [
            str(p).lower() for p in (pan_cfg.get("bash_readonly_prefixes") or []) if p
        ]
        if not prefixes:
            return False
        for seg in re.split(r"&&|\|\||;|\|", cmd):
            seg_l = seg.strip().lower()
            if not seg_l:
                continue
            first = seg_l.split()[0]
            if first == "cd":
                continue  # 透明段：單獨 cd 無副作用
            if not any(seg_l.startswith(p) for p in prefixes):
                return False
            if first == "find" and re.search(r"\s-(delete|exec)\b", seg_l):
                return False
        return True
    except Exception:
        return False


def pan_is_gated(
    tool_name: str, tool_input: Dict[str, Any], pan_cfg: Dict[str, Any]
) -> bool:
    """本次工具呼叫是否受 PAN 閘門管轄（唯讀 Bash / 豁免路徑不管）。"""
    if tool_name not in _PAN_GATED_TOOLS:
        return False
    if tool_name in ("Bash", "PowerShell"):
        return not pan_is_readonly_bash(tool_input.get("command", "") or "", pan_cfg)
    fp = tool_input.get("file_path", "") or tool_input.get("notebook_path", "") or ""
    if fp:
        norm = str(fp).replace("\\", "/")
        for sub in pan_cfg.get("exempt_path_substrings") or []:
            if sub and sub in norm:
                return False
    return True


def _pan_pass_marker(session_id: str, turn_seq: int) -> Path:
    return WORKFLOW_DIR / "pan-pass" / f"{session_id}-t{turn_seq}.flag"


def _pan_deny_file(session_id: str, turn_seq: int) -> Path:
    return WORKFLOW_DIR / "pan-deny" / f"{session_id}-t{turn_seq}.json"


def _pan_touch_marker(marker: Path) -> None:
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("armed", encoding="utf-8")
    except OSError:
        pass


def _pan_bump_counter(session_id: str, turn_seq: int) -> Optional[int]:
    """deny/observe 計數 +1，回新值。I/O 失敗回 None（caller 走 fail-open——
    counter 壞掉不能變成永久 deny 迴圈）。競態最壞少計一次 → 多 deny 一次，
    force-release 仍會到（單調不減即可，不加鎖）。"""
    try:
        path = _pan_deny_file(session_id, turn_seq)
        count = 0
        if path.exists():
            try:
                count = int(json.loads(path.read_text(encoding="utf-8")).get("count", 0))
            except (json.JSONDecodeError, ValueError, OSError):
                count = 0
        count += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"count": count}), encoding="utf-8")
        return count
    except Exception:
        return None


def _pan_log_ok(session_id: str, turn_seq: int) -> bool:
    """log 節流：同 (sid, turn) 上限 3 筆（含 fail-open 路徑——外部專案 session
    每呼叫落一筆會洗版）。counter I/O 失敗 → 照記（可觀測性優先）。"""
    count = _pan_bump_counter(session_id or "unknown", turn_seq)
    return count is None or count <= 3


def _check_pre_action_notice(
    input_data: Dict[str, Any], config: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str]]:
    """回 (deny_reason, warn_msg)，兩者互斥；放行 = (None, None)。全程 fail-open。"""
    try:
        pan_cfg = (config.get("guard") or {}).get("pre_action_notice") or {}
        if not pan_cfg.get("enabled", False):
            return None, None
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {}) or {}
        if not pan_is_gated(tool_name, tool_input, pan_cfg):
            return None, None

        mode = pan_cfg.get("mode", "observe")
        sid = input_data.get("session_id", "") or ""
        state = read_state(sid) if sid else None
        turn_seq = int((state or {}).get("turn_seq", 0) or 0)
        if not state or turn_seq <= 0:
            # sidechain / resume / state 缺失保底：不擋，只記（節流）
            if _pan_log_ok(sid, 0):
                append_guard_log(_PAN_GUARD, {
                    "tool": tool_name, "mode": mode,
                    "outcome": "fail_open_no_state", "sid": sid[:8],
                })
            return None, None

        marker = _pan_pass_marker(sid, turn_seq)
        if marker.exists():
            return None, None  # armed 快路徑：回合內已通過，零 transcript I/O

        # 惰性 import：wg_evasion 37KB，只在 gated 且未 armed 才付
        from wg_evasion import read_transcript_tail, get_current_turn_visible_text

        tpath = input_data.get("transcript_path") or ""
        if not tpath:
            tp = get_transcript_path(sid, input_data.get("cwd", "") or "")
            tpath = str(tp) if tp else ""
        tail = read_transcript_tail(Path(tpath)) if tpath else ""
        if not tail:
            if _pan_log_ok(sid, turn_seq):
                append_guard_log(_PAN_GUARD, {
                    "tool": tool_name, "mode": mode,
                    "outcome": "fail_open_no_transcript", "sid": sid[:8],
                })
            return None, None
        visible, probe = get_current_turn_visible_text(
            None, max_chars=int(pan_cfg.get("max_turn_text_chars", 12000)), text=tail,
        )
        if not probe:
            if _pan_log_ok(sid, turn_seq):
                append_guard_log(_PAN_GUARD, {
                    "tool": tool_name, "mode": mode,
                    "outcome": "fail_open_probe_failed", "sid": sid[:8],
                })
            return None, None

        head = str(probe.get("first_user_head", "") or "")
        if any(m in head for m in _PAN_CONTINUATION_MARKERS):
            _pan_touch_marker(marker)  # 整回合豁免，後續呼叫走 armed 快路徑
            append_guard_log(_PAN_GUARD, {
                "tool": tool_name, "mode": mode, "turn": turn_seq,
                "sid": sid[:8], "outcome": "exempt_continuation",
            })
            return None, None

        ok, fail_code = pan_validate_notice(visible)
        probe["cur_tool_flushed"] = tool_name in (probe.get("turn_tool_names") or [])
        max_denies = int(pan_cfg.get("max_denies_per_turn", 2))
        base = {
            "tool": tool_name, "mode": mode, "turn": turn_seq, "sid": sid[:8],
            "fail_code": fail_code,
            # 判讀佐證：pass 樣本需能證明「偵測到的預告確實來自落盤 text block」
            "text_blocks": probe.get("text_blocks"),
        }

        if mode == "observe":
            count = _pan_bump_counter(sid, turn_seq) or 1
            if count <= 3:  # 每 turn log 上限，防洗版
                append_guard_log(_PAN_GUARD, {
                    **base, "outcome": "observe",
                    "would_deny": not ok,
                    "payload_keys": sorted(input_data.keys()),
                    "turn_probe": probe,
                })
            # would_deny 時不寫 pass marker：保留同 turn 後續呼叫的時序樣本
            #（判 transcript flush lag 的關鍵縱深）
            if ok:
                _pan_touch_marker(marker)
            return None, None

        if ok:
            _pan_touch_marker(marker)
            append_guard_log(_PAN_GUARD, {**base, "outcome": "pass"})
            return None, None

        count = _pan_bump_counter(sid, turn_seq)
        if count is None or count > max_denies:
            _pan_touch_marker(marker)  # 本回合不再騷擾
            append_guard_log(_PAN_GUARD, {
                **base, "outcome": "force_release", "force_release": True,
                "count": count,
            })
            return None, None

        fail_detail = _PAN_FAIL_DETAIL.get(fail_code, fail_code)
        template = pan_cfg.get("deny_template") or _PAN_FALLBACK_DENY
        try:
            msg = template.format(fail_detail=fail_detail, n=count, max=max_denies)
        except (KeyError, IndexError, ValueError):
            msg = _PAN_FALLBACK_DENY.format(
                fail_detail=fail_detail, n=count, max=max_denies,
            )
        if mode == "warn":
            append_guard_log(_PAN_GUARD, {**base, "outcome": "warn", "count": count})
            return None, msg
        if pan_cfg.get("lenient_first_miss", False) and count == 1:
            # 首 miss 降 warn：同回合快路徑偵測不可靠（長文字+工具訊息 text
            # block 可能不落 transcript），先提醒；模型補獨立短訊息預告即過。
            append_guard_log(_PAN_GUARD, {
                **base, "outcome": "lenient_warn", "count": count,
            })
            return None, msg
        append_guard_log(_PAN_GUARD, {**base, "outcome": "deny", "count": count})
        return msg, None
    except Exception as e:
        try:
            sys.stderr.write(f"[Guardian:PAN] 檢查異常（fail-open）：{e}\n")
        except OSError:
            pass
        return None, None


# ─── Git 隱私硬閘（Bash/PowerShell `git commit` 前擋隱私檔進版控歷史）──────────
# chokepoint 選 commit（寫進歷史的不可逆點；add 錯了還能 unstage）。deny 為硬性、
# 不走「阻擋 N 次放行」——隱私是正確性閘，非收尾儀式。判定：staged（+ commit -a
# 時的 tracked modified）repo 相對路徑比對 deny globs。清單設計上「不全也能運作」：
# .gitignore 是第一道，本閘只兜「沒被 ignore 的明顯隱私檔」；可由 workflow/config.json
# privacy 段增補（deny_globs 追加、enabled 關閉）。fail-open：git 不可用/逾時不擋。
_PRIVACY_DEFAULT_DENY_GLOBS = [
    # 通用憑證/秘密檔（任何 repo 都不該進歷史）
    ".credentials*", "*.pem", "*.key", "*.p12", "*.pfx",
    "id_rsa*", "id_ed25519*", "id_ecdsa*",
    ".env", ".env.*", "*.secret", "*.secrets", "secrets.json", "secrets.yml",
    # Claude Code 本機隱私檔（settings.local / .claude.json 含本機權限與 MCP 憑證）
    "settings.local.json", ".claude.json",
]
# 僅當 git root 是 ~/.claude 本身才加掛（他專案裡同名資料夾是正常檔案，不得誤擋）
_PRIVACY_CLAUDE_ROOT_GLOBS = [
    "history.jsonl", "projects/*", "shell-snapshots/*", "todos/*",
    "statsig/*", "file-history/*", "session-env/*",
]
# git 全域旗標中「帶參數」者（掃 subcommand 時連值一起跳過）
_GIT_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--exec-path", "--namespace"}


def _git_commit_segments(command: str) -> List[Tuple[str, List[str]]]:
    """拆 shell 指令為片段，回傳其中 git subcommand == commit 的 (repo_cd, tokens)。
    repo_cd = `git -C <path>` 的 path（無則 ""）。保守解析：認不出就當非 commit（寧漏勿誤擋）。"""
    out: List[Tuple[str, List[str]]] = []
    for seg in re.split(r"&&|\|\||;|\||\n", command or ""):
        tokens = seg.split()
        git_idx = next(
            (idx for idx, t in enumerate(tokens)
             if t.lower().rstrip('"\'') in ("git", "git.exe")
             or t.lower().endswith(("/git", "\\git", "/git.exe", "\\git.exe"))),
            None,
        )
        if git_idx is None:
            continue
        repo_cd = ""
        j = git_idx + 1
        sub = ""
        while j < len(tokens):
            t = tokens[j]
            if t in _GIT_VALUE_FLAGS:
                if t == "-C" and j + 1 < len(tokens):
                    repo_cd = tokens[j + 1].strip("\"'")
                j += 2
                continue
            if t.startswith("-"):
                j += 1
                continue
            sub = t
            break
        if sub == "commit":
            out.append((repo_cd, tokens[j:]))
    return out


def _git_lines(args: List[str], cwd: str) -> Optional[List[str]]:
    """跑 git 取行清單；任何失敗回 None（fail-open 訊號，caller 不得誤當空清單）。"""
    try:
        r = subprocess.run(
            ["git"] + args, capture_output=True, text=True, timeout=3,
            cwd=cwd or None, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if r.returncode != 0:
            return None
        return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    except Exception:
        return None


def _privacy_globs(config: Dict[str, Any], repo_root: str) -> List[str]:
    globs = list(_PRIVACY_DEFAULT_DENY_GLOBS)
    try:
        if repo_root and Path(repo_root).resolve() == (Path.home() / ".claude").resolve():
            globs += _PRIVACY_CLAUDE_ROOT_GLOBS
    except Exception:
        pass
    extra = (config.get("privacy") or {}).get("deny_globs") or []
    globs += [str(g) for g in extra if g]
    return globs


def _privacy_match(rel_path: str, globs: List[str]) -> Optional[str]:
    """repo 相對路徑（posix、casefold）比對：pattern 含 / 比對全路徑，否則比對 basename。
    fnmatch 的 * 可跨 /（等效 **）。回命中的 pattern 或 None。"""
    rel = rel_path.replace("\\", "/").casefold()
    base = rel.rsplit("/", 1)[-1]
    for g in globs:
        pat = g.replace("\\", "/").casefold()
        target = rel if "/" in pat else base
        if fnmatch.fnmatchcase(target, pat):
            return g
    return None


def check_git_privacy(
    tool_name: str, tool_input: Dict[str, Any], cwd: str, config: Dict[str, Any]
) -> Optional[str]:
    """Bash/PowerShell `git commit` → staged（+-a 的 tracked modified）比對隱私 deny globs。
    命中回 deny 訊息；否則 None。fail-open：git 查詢失敗一律放行。"""
    if tool_name not in ("Bash", "PowerShell"):
        return None
    if not (config.get("privacy") or {}).get("enabled", True):
        return None
    command = tool_input.get("command", "") or ""
    if "git" not in command or "commit" not in command:
        return None   # 快篩，省 regex/子行程
    try:
        for repo_cd, commit_tokens in _git_commit_segments(command):
            run_cwd = repo_cd or cwd
            files = _git_lines(
                ["diff", "--cached", "--name-only", "--diff-filter=ACMR"], run_cwd
            )
            if files is None:
                continue   # fail-open
            if any(
                re.fullmatch(r"-[a-zA-Z]*a[a-zA-Z]*", t) or t == "--all"
                for t in commit_tokens
            ):
                extra = _git_lines(["diff", "--name-only", "--diff-filter=ACMR"], run_cwd)
                files += extra or []
            if not files:
                continue
            root_lines = _git_lines(["rev-parse", "--show-toplevel"], run_cwd)
            repo_root = root_lines[0] if root_lines else ""
            globs = _privacy_globs(config, repo_root)
            hits = []
            for f in dict.fromkeys(files):
                pat = _privacy_match(f, globs)
                if pat:
                    hits.append((f, pat))
            if hits:
                lines = [
                    "[Guardian:GitPrivacy] 待 commit 內容含隱私檔，已擋下（隱私檔不得進版控歷史）：",
                ]
                lines += [f"  ✗ {f} — 命中 deny glob `{p}`" for f, p in hits]
                lines += [
                    "處置：`git restore --staged <檔>` 移出後重 commit；該檔確非隱私 → 調整 "
                    "workflow/config.json privacy.deny_globs（或 privacy.enabled=false 停用本閘）"
                    "；長期正解是把它加進 .gitignore。",
                ]
                return "\n".join(lines)
    except Exception as e:
        try:
            sys.stderr.write(f"[Guardian:GitPrivacy] 檢查異常（fail-open）：{e}\n")
        except OSError:
            pass
    return None


def handle_pre_tool_use(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # ─── Sub-agent 記憶注入 ────────────────────────────────────
    # sub-agent（Agent/Task）開全新 context、不觸發 UserPromptSubmit，吃不到 atom。
    # 唯一 parent→child 通道是工具 prompt 字串 → 經 PreToolUse updatedInput prepend
    # 緊湊記憶 blob。fail-open：任何錯誤都不擋 spawn。
    if tool_name in ("Agent", "Task"):
        try:
            # 惰性 import：wg_atoms 全額 import 成本高，只在 Agent/Task spawn 才付
            from wg_atoms import build_injection_blob

            orig_prompt = tool_input.get("prompt", "") or ""
            blob, injected = build_injection_blob(
                orig_prompt, budget=_SUBAGENT_INJECT_BUDGET,
            )
            if blob and injected:
                new_input = dict(tool_input)
                new_input["prompt"] = f"{blob}\n\n{orig_prompt}"
                _atom_debug_log(
                    "SubagentInject",
                    f"tool={tool_name} injected={injected} "
                    f"blob_tokens=~{len(blob) // 4} prompt_head={orig_prompt[:60]!r}",
                    config,
                )
                output_json({
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "updatedInput": new_input,
                    }
                })
                return
        except Exception as e:
            try:
                sys.stderr.write(f"sub-agent inject error: {e}\n")
            except OSError:
                pass
        output_nothing()
        return

    # Advisory：feedback-* 寫入舊位址提示（不擋）
    advisory = _check_feedback_routing_advisory(tool_name, tool_input)
    if advisory:
        try:
            sys.stderr.write(advisory + "\n")
        except OSError:
            pass

    # ─── 跨 session 衝突預警（warn-only、fail-open；deny 觸發時警告只留 stderr）───
    # config 先判 enabled 才 import wg_coordination（disabled = 零 import 成本）。
    # additionalContext 隨工具結果進下一輪（非寫前攔截）；systemMessage 同步給使用者。
    coord_warn = None
    coord_warn_fp = None  # 發警時才記 warn-cache（deny 蓋掉的回合不記）
    coord_sid = input_data.get("session_id", "") or ""
    if (config.get("coordination") or {}).get("enabled", False):
        try:
            _sid = coord_sid
            if tool_name in ("Write", "Edit", "NotebookEdit"):
                _fp = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
                if _fp:
                    from wg_coordination import (
                        check_cross_session_conflict, format_conflict_warning,
                    )
                    _hit = check_cross_session_conflict(_sid, _fp, config)
                    if _hit:
                        coord_warn = format_conflict_warning(_hit)
                        coord_warn_fp = _fp
            elif tool_name == "Bash":
                _cmd = tool_input.get("command", "") or ""
                if _cmd:
                    from wg_coordination import check_bash_git_finalize
                    coord_warn = check_bash_git_finalize(
                        _sid, _cmd, input_data.get("cwd", "") or "", config,
                    )
            if coord_warn:
                try:
                    sys.stderr.write(coord_warn + "\n")
                except OSError:
                    pass
        except Exception as e:
            try:
                sys.stderr.write(f"[Guardian:Coord] pre_tool_use 檢查異常（fail-open）：{e}\n")
            except OSError:
                pass

    deny_reason = _check_memory_atom_format(tool_name, tool_input)
    if deny_reason:
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        })
        return

    deny_reason = check_memory_path_block(tool_name, tool_input)
    if deny_reason:
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        })
        return

    # 根層敏感檔 + Bash 全域 MCP 變更：
    # 外部專案 session 寫核心層 / 全域 MCP add/remove → deny
    _cwd = input_data.get("cwd", "") or ""
    deny_reason = (
        check_cross_realm_write(tool_name, tool_input, _cwd, config)
        or check_cross_realm_bash(tool_name, tool_input, _cwd, config)
        or check_cross_realm_mcp_cmd(tool_name, tool_input, _cwd, config)
    )
    if deny_reason:
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        })
        return

    deny_reason = check_svn_test_block(tool_name, tool_input)
    if deny_reason:
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        })
        return

    # git commit 隱私硬閘（staged 含隱私檔 → deny；fail-open）
    deny_reason = check_git_privacy(tool_name, tool_input, _cwd, config)
    if deny_reason:
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        })
        return

    # ─── Pre-Action Notice Gate（殿後：特定 guard 先攔，PAN 管透明度）────
    pan_deny, pan_warn = _check_pre_action_notice(input_data, config)
    if pan_deny:
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": pan_deny,
            }
        })
        return

    # 無 deny 才輸出警告（stdout 恆單一 JSON；不帶 permissionDecision——
    # "allow" 會自動核准繞過權限系統，advisory 不得改變放行行為）
    warn_msgs = [m for m in (coord_warn, pan_warn) if m]
    if warn_msgs:
        if coord_warn and coord_warn_fp:
            try:
                from wg_coordination import record_warn_cache
                record_warn_cache(coord_sid, coord_warn_fp)
            except Exception:
                pass
        combined = "\n".join(warn_msgs)
        output_json({
            "systemMessage": combined,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": combined,
            },
        })
        return

    output_nothing()
