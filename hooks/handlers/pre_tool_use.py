"""
handlers/pre_tool_use.py — PreToolUse hook handler

對 Write/Edit 進行 atom 格式/Confidence gate + memory 路徑防呆 + svn test block。
"""

import fnmatch
import functools
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from wg_core import (
    CLAUDE_DIR,
    output_json, output_nothing, append_guard_log,
    check_memory_path_block,
    check_cross_realm_write, check_cross_realm_mcp_cmd, check_cross_realm_bash,
    read_state, read_state_status,
    _atom_debug_log, v6_enabled,
    find_vcs_root, find_svn_root, memory_dir_candidates,
    user_typed_prompts,
)
import chain_store  # 連鎖斷路器的帳、停手、快照（lib/；判定在 hooks/wg_chain.py）
import wg_chain
import wg_data_file  # T2.16 動使用者資料檔要先宣告
import wg_read_fast  # 規則 READ_FAST_PATH：改檔前先把累積的 Read 補帳
import wg_judge_card  # 改判準卡留帳（JUDGE_CARD_CHANGE_NEEDS_DECLARATION）
import wg_oldtest
import wg_gate_bypass
import wg_release_rules as _rr   # 擋或提醒（gate_mode／RULE_MODE，規則 GATE_MODE_TABLE）
# 分段計時只打點、不看回傳：逾時被 Claude Code 取消本來就放行，提早放行只會少查（降級不改判定）
from wg_hook_timing import lap as _hook_lap

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


def _shell_tokens(seg: str) -> List[str]:
    """最小 quote-aware 切詞：引號內整段保留（含空白）、引號本身剝掉；不解跳脫。
    目的只有一個——`git -C "C:\\My Repo" pull` 的路徑不被 str.split 切碎。"""
    out: List[str] = []
    buf: List[str] = []
    quote = ""
    for ch in seg:
        if quote:
            if ch == quote:
                quote = ""
            else:
                buf.append(ch)
        elif ch in "\"'":
            quote = ch
        elif ch.isspace():
            if buf:
                out.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


_CD_HEADS = {"cd", "chdir", "pushd", "set-location", "sl"}


def _join_cd(base: str, nxt: str) -> str:
    """換目錄累加：相對路徑接在前一個落點後面（連續 cd、cd 之後的 `git -C`、多個 `-C` 都是這個語意），
    絕對路徑或 `~` 開頭的蓋掉前一個。"""
    if not base or os.path.isabs(os.path.expanduser(nxt)):
        return nxt
    return os.path.join(base, nxt)


def _vcs_segment_pairs(command: str, subcommands: Optional[set], exe_names: Tuple[str, ...], value_flags: set,
                       problems: Optional[List[str]] = None, shell: str = "",
                       alias_cwd: Optional[str] = None) -> List[Tuple[str, List[Tuple[str, str]]]]:
    """_vcs_segments 的本體，token 帶原文：(repo_cd, [(raw, value), …])。problems、shell 照 _scan_segments。
    alias_cwd 不是 None（只有 git 的呼叫端給，值是 tool cwd）→ 子命令是 git 別名就先展開再比（_expand_git_alias）。"""
    suffixes = tuple(f"{sep}{n}" for n in exe_names for sep in ("/", "\\"))
    out: List[Tuple[str, List[Tuple[str, str]]]] = []
    last_cd = ""
    for seg in _scan_segments(command, problems, shell):
        tokens = [v for _, v in seg]
        if tokens[0].lower() in _CD_HEADS:
            args = [t for t in tokens[1:] if not t.startswith("-") and t.lower() != "/d"]
            if args:
                last_cd = _join_cd(last_cd, args[0])
            continue
        exe_idx = next(
            (idx for idx, t in enumerate(tokens)
             if t.lower() in exe_names or t.lower().endswith(suffixes)),
            None,
        )
        if exe_idx is None:
            continue
        repo_cd = ""
        j = exe_idx + 1
        sub = ""
        inline: Dict[str, str] = {}   # 行內別名 `git -c alias.<名>=<展開> …`
        while j < len(tokens):
            t = tokens[j]
            if t == "-C" and t in value_flags and j + 1 < len(tokens):
                repo_cd = _join_cd(repo_cd, tokens[j + 1])
            if t == "-c" and t in value_flags and j + 1 < len(tokens) and tokens[j + 1].lower().startswith("alias."):
                name, _eq, value = tokens[j + 1][len("alias."):].partition("=")
                inline[name.lower()] = value
            if t in value_flags:
                j += 2
                continue
            if t.startswith("-"):
                j += 1
                continue
            sub = t
            break
        cd = _join_cd(last_cd, repo_cd) if repo_cd else last_cd
        rest = seg[j:] or [("", "")]
        if alias_cwd is not None and (subcommands is None or sub.lower() not in subcommands):
            rest = _expand_git_alias(rest, inline, _resolve_run_cwd(cd, alias_cwd, shell))
            sub = rest[0][1]
        if subcommands is None or sub.lower() in subcommands:
            out.append((cd, rest))
    return out


def _vcs_segments(command: str, subcommands: Optional[set], exe_names: Tuple[str, ...],
                  value_flags: set, shell: str = "", alias_cwd: Optional[str] = None) -> List[Tuple[str, List[str]]]:
    """拆 shell 指令為片段，回傳其中 <exe> subcommand ∈ subcommands 的 (repo_cd, tokens)；subcommands=None 回全部
    <exe> 段（沒接 subcommand 的 tokens 為 [""]）。
    exe_names 如 ("git", "git.exe")；也認路徑尾綴（`C:/x/git.exe`）與大小寫。
    tokens 從 subcommand 起算（tokens[0] 即 subcommand）。repo_cd＝同一條命令裡前面的 `cd <path>` 與 `git -C <path>`
    依序累加（相對的接在前一個後面，見 _join_cd）；都沒有 → ""（caller 用 tool cwd）。
    切段與斷詞走 _scan_segments：只在引號外切（`&& || ; | & 換行`），多行 `-m "…"`、PowerShell here-string 是一個 token，
    後面的 `-- <路徑>` 留在同一段；續行接回、註解略過；shell 給了就照那個 shell 解跳脫。支援引號路徑、`cd X && git …`／
    `cd X; git …`、PowerShell `Set-Location`。認不出就當非目標；拆得準不準要擋的另看 _commit_shape_problem。
    alias_cwd 照 _vcs_segment_pairs：給了就先展開 git 別名，tokens 換成展開後的（`git ci -m x` → commit -m x）。"""
    return [(cd, [v for _, v in pairs])
            for cd, pairs in _vcs_segment_pairs(command, subcommands, exe_names, value_flags, shell=shell,
                                                alias_cwd=alias_cwd)]


def _git_segments(command: str, subcommands: set, shell: str = "", cwd: str = "") -> List[Tuple[str, List[str]]]:
    """git 段一律先展開別名（cwd＝tool cwd，用來找別名所在的 repo；空字串＝hook 行程的目錄）。"""
    return _vcs_segments(command, subcommands, ("git", "git.exe"), _GIT_VALUE_FLAGS, shell, alias_cwd=cwd)


_SVN_VALUE_FLAGS = {"--config-dir", "--config-option", "--username", "--password"}


def _svn_segments(command: str, subcommands: set, shell: str = "") -> List[Tuple[str, List[str]]]:
    return _vcs_segments(command, subcommands, ("svn", "svn.exe"), _SVN_VALUE_FLAGS, shell)


def _git_commit_segments(command: str, cwd: str = "", shell: str = "") -> List[Tuple[str, List[str]]]:
    """薄包裝：只取 git commit 段（別名展開後是 commit 的也算）。"""
    return _git_segments(command, {"commit"}, shell, cwd)


# 常見內建子命令：遇到就不查別名（git 不認與內建同名的別名）。不在表上的才查設定，查到同名別名時再用 _git_commands
# 確認它是不是 git 自己的指令，所以這張表只省子行程，漏列不會判錯
_GIT_BUILTIN_SUBS = frozenset((
    "add am annotate apply archive bisect blame branch bundle cat-file check-attr check-ignore check-mailmap checkout "
    "cherry cherry-pick clean clone commit commit-graph commit-tree config count-objects describe diff diff-files "
    "diff-index diff-tree difftool fetch for-each-ref format-patch fsck gc grep help init log ls-files ls-remote ls-tree "
    "maintenance merge merge-base mergetool mv notes prune pull push range-diff read-tree rebase reflog remote repack "
    "replace reset restore rev-list rev-parse revert rm shortlog show show-ref sparse-checkout stash status submodule "
    "switch symbolic-ref tag update-index update-ref var version worktree write-tree").split())


def _git_config_aliases(run_cwd: str) -> Optional[Dict[str, str]]:
    """run_cwd 看得到的 git 別名（系統、全域、repo 設定合併後）→ {名: 展開}；git 失敗（目錄不存在、git 跑不起來）回 None。
    用 `-z` 取：值可以跨行（多行的 `!` 別名），逐行讀會把第二行起丟掉。"""
    try:
        r = subprocess.run(["git", "config", "-z", "--get-regexp", r"^alias\."], capture_output=True, timeout=3,
                           cwd=run_cwd or None,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    except Exception:
        return None
    if r.returncode not in (0, 1):   # 1＝一個別名都沒有
        return None
    out: Dict[str, str] = {}
    for rec in r.stdout.decode("utf-8", "replace").split("\0"):
        key, _nl, value = rec.partition("\n")
        if key.lower().startswith("alias."):
            out[key[len("alias."):].lower()] = value
    return out


def _alias_note(text: str) -> None:
    try:
        sys.stderr.write(f"[Guardian:GitAlias] {text}\n")
    except OSError:
        pass


@functools.lru_cache(maxsize=None)
def _git_aliases(run_cwd: str) -> Optional[Dict[str, str]]:
    """commit 落點看得到的別名表（hook 每個事件一個行程，快取只活一次事件）。查不到（`-C` 指到還不存在的目錄、git 逾時）
    回 None 並在 stderr 留訊號：不拿別的目錄的設定頂替（local 別名會套錯 repo），由 _expand_git_alias 當判不了。"""
    found = _git_config_aliases(run_cwd)
    if found is None:
        _alias_note(f"查 {run_cwd or '目前目錄'} 的 git 別名失敗（git config），不是 git 指令的子命令一律當判不了")
    return found


@functools.lru_cache(maxsize=1)
def _git_commands() -> frozenset:
    """git 自己的指令名（內建、exec-path 裡的、PATH 上的 git-* 外掛）：跟它們同名的別名 git 不認。查不到回空集合並在
    stderr 留訊號——這時同名別名照別名判（可能多擋，不會漏放）。"""
    names = _git_lines(["--list-cmds=builtins,main,others"], "")
    if names is None:
        _alias_note("查不到 git 指令清單（git --list-cmds），跟 git 指令同名的別名照別名判")
    return frozenset(n.lower() for n in names or [])


def _expand_git_alias(pairs: List[Tuple[str, str]], inline: Dict[str, str], run_cwd: str) -> List[Tuple[str, str]]:
    """子命令是 git 別名就換成展開後的子命令與參數：行內 `-c alias.<名>=…` 優先，再查設定；別名接別名一路追，名字重複出現
    ＝循環（git 自己也會報錯）就停；跟 git 自己的指令同名的別名不認。展開出的字 git 直接當參數、不經 shell，raw 一律寫成
    單引號字面（`commit -m 'literal $HOME'` 的 $ 不是展開）。`!` 開頭的 shell 別名不展開，換成 [("!", "!"), (內容, 內容)]
    兩段；落點的別名表查不到、子命令又不是 git 指令 → [("?", "?")]（可能是 local 別名）；兩種都交 _git_opaque_alias_commit。"""
    seen: set = set()
    while True:   # 每圈多記一個名字，別名有限，必停
        sub = pairs[0][1].lower()
        if not sub or sub in _GIT_BUILTIN_SUBS or sub in seen:
            return pairs
        seen.add(sub)
        table = _git_aliases(run_cwd)
        expansion = inline.get(sub, (table or {}).get(sub))
        if expansion is None:
            return [("?", "?")] if table is None and sub not in _git_commands() else pairs
        if sub in _git_commands():
            return pairs
        if expansion.startswith("!"):
            return [("!", "!"), (expansion[1:], expansion[1:])]
        pairs = [("'" + w.replace("'", "") + "'", w) for w in _shell_tokens(expansion) or [""]] + pairs[1:]


def _git_opaque_alias_commit(command: str, cwd: str = "", shell: str = "") -> bool:
    """命令叫用了看不進去、可能藏 commit 的 git 別名：`!` 開頭的 shell 別名而內容照包裝那套判（_wrapped_commit_verdict）
    有或可能有 commit，或落點的別名表查不到（_expand_git_alias 的 "?"）。拆不出落在哪個 repo、提交哪些檔，呼叫端當
    「包裝裡可能有 commit」處理。"""
    return any(p[0][1] == "?" or p[0][1] == "!" and len(p) > 1 and _wrapped_commit_verdict(p[1][1], 1, strict=True)
               for _cd, p in _vcs_segment_pairs(command, None, ("git", "git.exe"), _GIT_VALUE_FLAGS, shell=shell,
                                                alias_cwd=cwd))


def _subst_commit(raw: str, shell: str) -> bool:
    """直接 commit 段裡的命令替換（`$(…)`，Bash 另有反引號；單引號裡是字面）之後又有 git…commit：外層 commit 跑之前
    先跑了一次看不到範圍的 commit（`git commit --dry-run -m "$(git commit -am x)"`）。heredoc 本文呼叫端已剝掉。"""
    live = re.sub(r"'[^']*'", "''", raw)
    m = re.search(r"\$\(" if shell == "powershell" else r"\$\(|`", live)
    return bool(m and _GIT_COMMIT_WORDS_RE.search(live, m.start()))


def _hidden_commit(command: str, cwd: str = "", shell: str = "") -> bool:
    """直接拆得出的 git commit 段以外，有沒有別處（看不進去的 git 別名、bash -c 之類的包裝、eval／展開、commit 訊息裡的
    命令替換）可能藏 commit。有一段拆得出不代表整條拆得出：`git save && git commit --dry-run`（save 是 `!git commit …`）
    只看得到後面那段。"""
    if _git_opaque_alias_commit(command, cwd, shell):
        return True
    for seg in _scan_segments(command, None, shell):
        raw = " ".join(r for r, _ in seg)
        direct = bool(_git_commit_segments(raw, cwd, shell))
        if _subst_commit(raw, shell) if direct else _wrapped_commit_verdict(raw):
            return True
    return False


def _resolve_run_cwd(repo_cd: str, cwd: str, shell: str = "") -> str:
    """把 `-C`／`cd` 抓到的路徑解成子行程 cwd：展開 ~；相對路徑以 tool cwd 為基準。
    shell="bash"（Bash 工具）時 Git Bash 的磁碟機路徑 `/c/…` 先轉成 `C:/…`（_drive_path）；不轉的話 git 拿它當 cwd 會
    WinError 267、各 commit 前閘只能判不了。PowerShell 的 `/c/…` 原生就是 `C:\\c\\…`，不轉。"""
    if not repo_cd:
        return cwd
    p = os.path.expanduser(_drive_path(repo_cd) if shell == "bash" else repo_cd)
    if not os.path.isabs(p) and cwd:
        p = os.path.join(cwd, p)
    return p


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
        if repo_root and Path(repo_root).resolve() == Path(CLAUDE_DIR).resolve():
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


# ─── git commit 口令閘（USER.md 縮寫指令契約的程式化版本）───────────────────
# 「上GIT」＝commit＋push 一氣；口令下達前不碰 git——使用者要先看 diff 再下令。
# 事後閘（SyncReminder）只看得到「髒不髒」，模型 local commit 就能讓它閉嘴；本閘把
# 「口令前不 commit」放到動手前：本回合使用者原話沒有任何版控口令 → deny。
# fail-open：state 缺失（sidechain／resume／subagent）或本 session 尚無 user prompt → 放行並落 stderr。
_COMMIT_ORDER_DEFAULT_KEYWORDS = (
    "上GIT", "上 GIT", "上傳GIT", "上乾淨", "全上", "上版", "上SVN",
    "執P", "執驗上P",
)
# 「commit／push／提交」這類一般字不是口令：出現在使用者原話裡不等於授權（「先不要 commit」「commit 訊息怎麼寫」）。
# 是不是授權是語意，交 LLM：判斷是授權就在指令裡附「授權原句：「…」」，程式核對原句逐字在本回合使用者原話裡、所在子句沒被否定。
_AUTH_QUOTE_RE = re.compile(r"授權原句\s*[:：]\s*「([^」]+)」")
_COMMIT_WORD_RE = re.compile(r"commit|提交|上傳|送出|上版|上\s*git|push|推送", re.IGNORECASE)
# 口令或授權動作字有沒有被否定，逐個看它在原話裡的位置。否定詞表只會多擋不會多放：判錯的代價是請使用者再說一次，
# 放錯的代價是推出去收不回。子句以逗號、句號、分號、問嘆號、換行為界；頓號與「或」不斷，否定會跨列舉。
from wg_release_rules import CLAUSE_END_RE as _ORDER_CLAUSE_END_RE, NEG_WORD_RE as _ORDER_NEG_RE  # noqa: E402  資料檔點名共用
_ORDER_WAIT_RE = re.compile(r"(?:等我|我看完|我確認|我說|我同意)[^，,。！？!?；;\n]*$")     # 延後到使用者自己確認之後
_ORDER_WAIT_PHRASE_RE = re.compile(r"等我|我看完|我確認|我先看|晚點|稍後再")             # 整則原話裡有延後
_ORDER_RIGHT_NEG_RE = re.compile(r"^\s*(?:先不要|不要|先別|別|先不|暫不|不用)\s*(?:了|啦|吧|喔)?\s*$")


def _order_negated(text: str, start: int, end: int) -> bool:
    """text[start:end]（口令或授權動作字）被否定或延後：同一子句裡它左邊有否定字或「等我…」，或右邊只剩一個不帶對象的
    否定（「上GIT 先不要」）。「上GIT 別碰 X」「commit 吧，但不要 push」的否定各有自己的對象，不算否定這個口令。"""
    seps = [m.end() for m in _ORDER_CLAUSE_END_RE.finditer(text, 0, start)]
    left = text[seps[-1] if seps else 0:start]
    m = _ORDER_CLAUSE_END_RE.search(text, end)
    right = text[end:m.start() if m else len(text)]
    return bool(_ORDER_NEG_RE.search(left) or _ORDER_WAIT_RE.search(left) or _ORDER_RIGHT_NEG_RE.match(right))


def _quote_authorizes(p: str, i: int, q: str) -> bool:
    """原話 p 在位置 i 的引用 q 算不算授權（擋訊息寫的規則：逐字在原話裡、所在子句沒被否定）。q 含提交類動作字 → 至少一個
    動作字在原話裡沒被否定或延後；q 沒有動作字（「其他照做」這類，LLM 依上下文判斷是在回應提交）→ q 本身與它的子句沒有否定、
    同一則原話裡沒有被否定或延後的提交動作字，也沒有「等我／我看完／我確認」這類延後。"""
    words = list(_COMMIT_WORD_RE.finditer(q))
    if words:
        return any(not _order_negated(p, i + m.start(), i + m.end()) for m in words)
    return not (_ORDER_NEG_RE.search(q) or _order_negated(p, i, i + len(q)) or _ORDER_WAIT_PHRASE_RE.search(p)
                or any(_order_negated(p, m.start(), m.end()) for m in _COMMIT_WORD_RE.finditer(p)))


def _quoted_authorization(command: str, turn_prompts: List[str]) -> Optional[str]:
    """LLM 判斷使用者本回合的話是授權、在指令裡附「授權原句：「…」」：原句逐字出現在本回合使用者原話裡、
    照 _quote_authorizes 沒被否定或延後 → 回原句；否則 None（照擋）。"""
    for q in (x.strip() for x in _AUTH_QUOTE_RE.findall(command or "")):
        for p in turn_prompts:
            i = p.find(q) if q else -1
            if i >= 0 and _quote_authorizes(p, i, q):
                return q
    return None


# heredoc 內文不是 shell 指令（文件補丁／內嵌 python 常含「git commit」字樣）；剝掉再拆段，
# 否則口令閘會把文字當成 commit 段誤擋。隱私閘不需要：它接著查 staged，無檔即靜默。
# 剝法與紅測記帳的切段共用一份（wg_release_rules.strip_heredoc_bodies；只剝內文、起始行 delimiter 後面的真命令照留）。
from wg_release_rules import HEREDOC_MARK as _HEREDOC_MARK, strip_heredoc_bodies as _strip_heredoc_bodies  # noqa: E402


def _git_commits_to_run(command: str, cwd: str = "",
                        shell: str = "") -> Tuple[str, List[Tuple[str, List[str]]], bool]:
    """命令裡真的會執行的 git commit（CommitOrder、病形閘與需求目標 commit_gate 共用這一支）：先剝 heredoc 本文，寫在
    文件裡的 commit 範例不算、heredoc 結束後真的執行的照算。回（剝過的命令、直接拆得出的 commit 段（git 別名展開後是
    commit 的也算）、有沒有 commit：拆得出段，或 `!` shell 別名、包裝／展開裡可能有）。快篩只看 git 字樣（別名的
    命令裡沒有 commit 字樣），與 _vcs_segments 同一套大小寫規則：Windows 的 Git／GIT.EXE 也是 git。cwd＝tool cwd，
    shell＝_tool_shell（跳脫規則與 Git Bash 的 `/c/…` 落點，別名要在落點的 repo 查）。"""
    low = (command or "").lower()
    if "git" not in low:
        return command or "", [], False
    stripped = _strip_heredoc_bodies(command)
    segments = _git_commit_segments(stripped, cwd, shell)
    if segments:
        return stripped, segments, True
    return stripped, [], (_git_opaque_alias_commit(stripped, cwd, shell)
                          or ("commit" in low and _wrapped_commit_verdict(stripped)))


def _commit_order_keyword_hit(prompt: str, keywords) -> Optional[str]:
    """口令命中：關鍵字出現在使用者原話裡，而且至少一處沒被否定或延後（_order_negated；「先不要上GIT」不算）。"""
    prompt = prompt or ""
    low = prompt.lower()
    for k in keywords:
        i = low.find(k.lower()) if k else -1
        while i >= 0:
            if not _order_negated(prompt, i, i + len(k)):
                return k
            i = low.find(k.lower(), i + 1)
    return None


# 口令閘的「記憶系統自己的程式」豁免只給整條命令都對得上白名單句型的寫法；其他寫法不豁免、照常檢查口令
# （不會擋死，只是要使用者口令），所以白名單寧窄勿寬：只認 `&&` 串起的這幾種段，不解析其他 shell 語法。
_GIT_REPO_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")
# 包裝偵測走斷詞不走 regex：_scan_segments 保留引號狀態切段（續行接回、不切段），每段看執行檔 basename（去路徑、去 .exe、
# 不分大小寫，所以帶引號的完整路徑 `"C:/Program Files/Git/bin/bash.exe"` 也認得；PowerShell 的 `&` 呼叫運算子是分隔），
# 再往後找執行旗標：POSIX shell 的短旗標組含 c 就算（-c、-lc、-l -c），內容是旗標後那一個 token；PowerShell 認 -Command
# 與其縮寫（-c、-com…）、cmd 認 /c、/k，內容是旗標後整串。內容再交 _wrapped_commit_verdict 逐段辨識真子命令。
_POSIX_SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
_PS_SHELLS = {"pwsh", "powershell"}
_SUBSHELL_RE = re.compile(r"\beval\b|\$\(|`|\(")                  # 看不進去的：eval、命令替換、子 shell 括號
_GIT_COMMIT_WORDS_RE = re.compile(r"\bgit(?:\.exe)?\b.*\bcommit\b", re.S | re.I)
_SAFE_WRAPPED_GIT_SUBS = {"log", "status", "diff", "show"}        # 包裝裡確定不是提交的查詢子命令
_EXEMPT_GIT_SUBS = {"add", "commit", "push", "status", "diff", "log", "show", "rm", "mv", "restore"}


def _unquoted(command: str) -> str:
    """把引號裡的字換成空字串（commit 訊息裡的括號不該影響寫法判斷）。"""
    return re.sub(r'"[^"]*"|\'[^\']*\'', '""', command or "")


def _wrap_flag(exe: str):
    """exe（basename、小寫、去 .exe）是哪種 shell → 回「這個 token 是不是它的執行旗標」判斷式；不是 shell → None。"""
    if exe in _POSIX_SHELLS:
        return lambda t: re.fullmatch(r"-[a-z]*c[a-z]*", t, re.I) is not None
    if exe in _PS_SHELLS:
        return lambda t: re.fullmatch(r"-c[a-z]*", t, re.I) is not None
    if exe == "cmd":
        return lambda t: t.lower() in ("/c", "/k")
    return None


_SEPARATORS = ("&&", "||", "\n", ";", "|", "&")
_HERESTRING_OPEN_RE = re.compile(r"@(['\"])[ \t]*\r?\n")


def _escaped(s: str, i: int, quote: str, shell: str) -> bool:
    """s[i] 是不是跳脫字元（下一個字照字面）：Bash 引號外的 `\\`、雙引號裡 `\\` 接 `" \\ $ ``；PowerShell 引號外與雙引號裡
    的反引號。單引號裡沒有跳脫；shell 不明（""）不解跳脫。"""
    if not s[i + 1:i + 2] or quote == "'":
        return False
    if shell == "bash":
        return s[i] == "\\" and (not quote or s[i + 1] in '"\\$`')
    return shell == "powershell" and s[i] == "`"


_ANSI_C_RE = re.compile(r"\\(x[0-9A-Fa-f]{1,2}|.)|'", re.S)
_ANSI_C_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v", "e": "\x1b",
                   "E": "\x1b", "\\": "\\", "'": "'", '"': '"', "?": "?"}


def _ansi_c_quoted(s: str, i: int) -> Optional[Tuple[str, int]]:
    """Bash 的 ANSI-C 引號：s[i:i+2] 是 `$'`。回 (解開的內容, 收尾引號後的位置)；沒收尾回 None（照一般引號拆、記沒閉合）。
    解常見跳脫與 `\\xHH`，`\\'` 不收尾；其餘 `\\` 照字面留。"""
    out, j = [], i + 2
    for m in _ANSI_C_RE.finditer(s, j):
        out.append(s[j:m.start()])
        if m.group() == "'":
            return "".join(out), m.end()
        esc = m.group(1)
        out.append(chr(int(esc[1:], 16)) if len(esc) > 1 else _ANSI_C_ESCAPES.get(esc, "\\" + esc))
        j = m.end()
    return None


def _scan_segments(command: str, problems: Optional[List[str]] = None,
                   shell: str = "") -> List[List[Tuple[str, str]]]:
    """保留引號狀態的切段＋斷詞 → 每段一串 (raw, value)：raw 是 token 的原文（含引號、已去掉續行），value 剝一層引號。
    只在引號外切段（&& || ; | & 換行；重導向 `2>&1`、`&>` 裡的 & 不算）。續行接回、不切段：Bash 的 `\\`＋換行（引號外與
    雙引號裡）、cmd 的 `^`＋換行、PowerShell 的反引號＋換行（都只在引號外）；三種都認，判定只會因此多擋不會少擋。raw 不留
    續行字元，所以拿 raw 重組再判（`git\\⏎commit`）和展開檢查（`$\\⏎(`）看到的都是接回後的命令。
    註解：引號外、位在 token 起頭的 `#` 到行尾略過（Bash 與 PowerShell 同語意），換行照切段；引號裡與 token 中間的 `#`
    是字面（`git commit -m "fix #12"`、`a#b`）。
    跳脫：shell 給 "bash"／"powershell" 就照那個 shell 解（_escaped；`"fix \\"a; b\\""` 裡的分號不切段），raw 留跳脫字元、
    value 只留被跳脫的字；不給不解。Bash 引號外的 `$'…'`（ANSI-C 引號）整段照 _ansi_c_quoted 解、`$"…"` 照雙引號解，
    raw 原樣保留。
    PowerShell here-string（shell 不是 bash）：token 起頭的 `@'`／`@"` 接換行，到行首的 `'@`／`"@` 為止整段是一個 token
    （內文的引號不算數）；value 是內文，raw 換成等價的一般引號寫法（`'內文'`／`"內文"`，內文裡同種引號拿掉），展開檢查
    照引號語意走。找不到結束行就不當 here-string，照一般引號拆。
    problems：給了就記下拆不準的原因（引號沒閉合、here-string 沒有結束行）——這時後面的分隔符號與路徑都可能被吞進
    同一個 token，要拆提交範圍的呼叫端不能信這次的結果。"""
    s = command or ""
    segs: List[List[Tuple[str, str]]] = []
    toks: List[Tuple[str, str]] = []
    val: List[str] = []
    raw: List[str] = []
    in_token, quote, i = False, "", 0

    def end_token() -> None:
        nonlocal val, raw, in_token
        if in_token:
            toks.append(("".join(raw), "".join(val)))
        val, raw, in_token = [], [], False

    while i < len(s):
        ch = s[i]
        if s[i + 1:i + 2] == "\n" and (ch == "\\" and quote in ("", '"') or ch in "^`" and not quote):
            i += 2
            continue
        if _escaped(s, i, quote, shell):
            raw.append(s[i:i + 2])
            val.append(s[i + 1])
            in_token, i = True, i + 2
            continue
        if quote:
            quote = "" if ch == quote else quote
            raw.append(ch)
            if quote:
                val.append(ch)
            i += 1
            continue
        ansi = _ansi_c_quoted(s, i) if shell == "bash" and s.startswith("$'", i) else None
        if ansi:
            raw.append(s[i:ansi[1]])
            val.append(ansi[0])
            in_token, i = True, ansi[1]
            continue
        if shell == "bash" and s.startswith('$"', i):   # $"…"（locale 翻譯引號）的值同雙引號，$ 只留在 raw
            raw.append("$")
            in_token, i = True, i + 1
            continue
        here = _HERESTRING_OPEN_RE.match(s, i) if ch == "@" and not in_token and shell != "bash" else None
        if here:
            q = here.group(1)
            end = s.find("\n" + q + "@", here.end() - 1)
            if end >= 0:
                body = s[here.end():end]
                raw.append(q + body.replace(q, "") + q)
                val.append(body)
                in_token, i = True, end + 3
                continue
            if problems is not None:
                problems.append("PowerShell here-string（@'…'@／@\"…\"@）沒有行首的結束行")
        if ch == "#" and not in_token:
            nl = s.find("\n", i)
            i = len(s) if nl < 0 else nl
            continue
        sep = next((p for p in _SEPARATORS if s.startswith(p, i)), "")
        if sep == "&" and (raw and raw[-1][-1:] in ("<", ">") or s.startswith(">", i + 1)):
            sep = ""                                       # 重導向 `2>&1`、`<&3`、`&>檔` 的 & 不是分隔
        if sep or ch.isspace():
            end_token()
            if sep and toks:
                segs.append(toks)
                toks = []
            i += len(sep) or 1
            continue
        in_token = True
        raw.append(ch)
        if ch in "\"'":
            quote = ch
        else:
            val.append(ch)
        i += 1
    end_token()
    if toks:
        segs.append(toks)
    if quote and problems is not None:
        problems.append("引號沒有閉合")
    return segs


def _live_expansion(raw: str) -> bool:
    """這段文字給 shell 讀時會不會執行看不見的命令：引號外的 eval／子 shell 括號，或單引號外（雙引號裡也算）的
    `$(`／反引號／跳脫、沒閉合的引號。只有單引號裡是字面。"""
    return bool(_SUBSHELL_RE.search(_unquoted(raw))) or _expands_outside_single_quotes(raw)


def _wrapper_split(seg: List[Tuple[str, str]]) -> Optional[str]:
    """seg 是「shell ＋ 執行旗標」段 → 內層命令（剝一層引號）；不是 → None。"""
    for idx, (_, tok) in enumerate(seg):
        exe = os.path.basename(tok.replace("\\", "/")).lower()
        exe = exe[:-4] if exe.endswith(".exe") else exe
        is_flag = _wrap_flag(exe)
        if is_flag is None:
            continue
        flag_at = next((k for k in range(idx + 1, len(seg)) if is_flag(seg[k][1])), None)
        if flag_at is None:
            return None
        cut = flag_at + 1
        take = len(seg) - cut if exe == "cmd" or exe in _PS_SHELLS else 1
        return " ".join(v for _, v in seg[cut:cut + take])
    return None


def _wrapped_commit_verdict(command: str, depth: int = 0, strict: bool = False) -> bool:
    """解析器拆不出 git commit 段時的第二層判斷：True＝有 commit 或判不明（走口令檢查），False＝確定沒有。
    逐段判（_scan_segments，續行已接回、註解已略過）：
      每段先用外層 shell 語意查整段原文（含包裝內層自己的外層引號；只有單引號是字面）：有展開訊號（_live_expansion）
      且命令有 git…commit 字樣 → True。所以 `bash -c "git log --grep='$(…)'"` 的 `$(` 在外層雙引號裡就算數。
      包裝段 → 再把剝一層引號的內層遞迴（strict，最多 3 層，超過就只看 git…commit 字樣）。
    strict（包裝內層）另加：git 子命令不在 log/status/diff/show 而命令有 git…commit 字樣 → True；
      整段內層既沒有 git 呼叫也沒有包裝卻有 git…commit 字樣 → True（判不明寧擋）。
    續行接回後拆得出 git commit 段 → True。"""
    words = bool(_GIT_COMMIT_WORDS_RE.search(command))
    if depth > 3:
        return words
    segs = _scan_segments(command)
    if _git_commit_segments("\n".join(" ".join(r for r, _ in seg) for seg in segs)):
        return True
    explained = False
    for seg in segs:
        raw = " ".join(r for r, _ in seg)
        if words and _live_expansion(raw):
            return True
        inner = _wrapper_split(seg)
        if inner is not None:
            explained = True
            if _wrapped_commit_verdict(inner, depth + 1, strict=True):
                return True
            continue
        if strict:
            subs = [t[0].lower() for _, t in _vcs_segments(raw, None, ("git", "git.exe"), _GIT_VALUE_FLAGS)]
            explained = explained or bool(subs)
            if words and any(sub not in _SAFE_WRAPPED_GIT_SUBS for sub in subs):
                return True
    return strict and words and not explained


def _split_and(command: str) -> List[str]:
    """照引號外的 `&&` 切段（引號裡的 && 是訊息內容）。"""
    out, buf, quote, i = [], [], "", 0
    while i < len(command):
        ch = command[i]
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        elif command.startswith("&&", i):
            out.append("".join(buf))
            buf, i = [], i + 2
            continue
        buf.append(ch)
        i += 1
    out.append("".join(buf))
    return out


def _expands_outside_single_quotes(command: str) -> bool:
    """照真實引號狀態掃：單引號外（含雙引號裡）出現 `$(`、反引號，或反斜線跳脫 `$`／反引號／引號，或引號沒閉合 → True。"""
    quote = ""
    for i, ch in enumerate(command):
        if quote == "'":
            quote = "" if ch == "'" else quote
            continue
        if ch == "\\" and command[i + 1:i + 2] in ("$", "`", '"', "'"):
            return True
        if ch == "`" or command.startswith("$(", i):
            return True
        if ch == '"':
            quote = "" if quote == '"' else '"'
        elif ch == "'" and not quote:
            quote = "'"
    return bool(quote)


def _literal_path(token: str) -> bool:
    """cd／-C 的路徑是不是字面值：含 `$`（bash／PowerShell 變數）、`%`（cmd 變數）、開頭 `~`、萬用字元 → 不是，
    shell 會展開成看不到的路徑，不能拿字面去找歸屬。"""
    return bool(token) and not token.startswith("~") and not any(c in token for c in "$%*?")


def _drive_path(token: str) -> str:
    """Git Bash 的磁碟機路徑（`/c/Users/…`）在 Windows 轉成 `C:/Users/…`；不轉的話 abspath 會把它接到現行磁碟機、找錯 `.git`。
    其他形式原樣回傳（`//server/…`、`/cygdrive/c/…` 都不是已知寫法，照舊不豁免）。
    只有 Bash 工具的命令有這個語意（caller 以 msys_paths 開關）；PowerShell 的 `/c/Users` 原生就是 `C:\\c\\Users`，不轉。"""
    m = re.fullmatch(r"/([A-Za-z])(/.*)?", token or "")
    if sys.platform != "win32" or not m:
        return token
    return f"{m.group(1).upper()}:{m.group(2) or '/'}"


def _exempt_run_dirs(raw: str, base: str, msys_paths: bool = False) -> Optional[List[str]]:
    """白名單句型：整條命令只由 `&&` 串起，每段都是下列之一 → 回每段 git commit 落的目錄；否則 None（不豁免）。
      第一段可以是 `cd <絕對路徑>`（msys_paths=True 時 Git Bash 的 `/c/…` 磁碟機路徑也算，見 _drive_path）；
      其餘每段都是 `git [-C <路徑>] <add|commit|push|status|diff|log|show|rm|mv|restore> …`
      （相對 -C 接在那個 cd 或 tool cwd 後面），commit 段可帶 heredoc，但 delimiter 要加引號（`<<'EOF'`，內文不展開）、
      起始行 delimiter 後面不准再接東西。
    任何其他東西都不在白名單：未知命令段（builtin、env、變數指定、echo…）、`;`／`|`／`||`／換行、重導向、括號、
    單引號外的 `$(`／反引號／跳脫（照真實引號狀態掃，雙引號裡也算）、沒閉合的引號、repo 覆寫參數（--git-dir、
    --work-tree，引號裡也算）、hook 行程繼承的 GIT_DIR 等環境變數、第二個 cd、多個或黏在一起的 -C。"""
    if any(os.environ.get(k) for k in _GIT_REPO_ENV):
        return None
    for m in re.finditer(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1([^\n]*)", raw):
        if not m.group(1) or m.group(3).strip():
            return None
    command = _strip_heredoc_bodies(raw)
    if _expands_outside_single_quotes(command):
        return None
    if re.search(r"[;|()<>\n]|(?<!&)&(?!&)", _unquoted(command).replace(_HEREDOC_MARK, "")):
        return None
    run_base, out = base, []
    fix_path = _drive_path if msys_paths else (lambda t: t)
    for idx, seg in enumerate(_split_and(command)):
        tokens = [t for t in _shell_tokens(seg) if t != _HEREDOC_MARK]
        if not tokens:
            return None
        if tokens[0].lower() == "cd":
            if idx != 0 or len(tokens) != 2 or not _literal_path(tokens[1]):
                return None
            run_base = fix_path(tokens[1])
            if not os.path.isabs(run_base):
                return None
            continue
        if tokens[0].lower() not in ("git", "git.exe"):
            return None
        if any(t.lower().startswith(("--git-dir", "--work-tree")) for t in tokens):
            return None
        rest, target = tokens[1:], ""
        if rest[:1] == ["-C"]:
            if len(rest) < 2 or not _literal_path(rest[1]):
                return None
            target, rest = fix_path(rest[1]), rest[2:]
        if not rest or rest[0].lower() not in _EXEMPT_GIT_SUBS or any(t.startswith("-C") for t in rest):
            return None
        if rest[0].lower() == "commit":
            if target and not os.path.isabs(target):
                if not run_base:
                    return None
                target = os.path.join(run_base, target)    # 相對 -C 接在唯一的 cd（或 tool cwd）後面
            out.append(target or run_base)
    return out or None


def _commit_target_is_claude(run_dir: str) -> Optional[bool]:
    """這段 commit 實際落在原子記憶系統這個 repo（~/.claude 本身，或它的 git worktree）嗎？
    從 run_dir 往上找最近的 `.git`（檔或目錄都算，遇到就停，所以內嵌 repo／submodule 歸它自己）；
    該根就是 CLAUDE_DIR → True；`.git` 是檔且 gitdir 指到 <CLAUDE_DIR>/.git/worktrees/ 之下 → True；其他 → False。
    run_dir 不是絕對路徑、或讀檔出錯 → None（判不了）；網路路徑直接 False（不碰網路；本機長路徑 `\\\\?\\C:\\…` 不算）。"""
    if run_dir.startswith("\\\\?\\"):
        run_dir = run_dir[4:]
    if not run_dir or not os.path.isabs(run_dir):
        return None
    if run_dir.startswith(("\\\\", "//")):
        return False
    try:
        p = Path(os.path.abspath(run_dir))                 # 先消掉 `..`：`.claude/../other` 的字面父層不是 .claude
        root = next((d for d in (p, *p.parents) if (d / ".git").exists()), None)
        if root is None:
            return False
        if root.resolve() == Path(CLAUDE_DIR).resolve():
            return True
        dot = root / ".git"
        if not dot.is_file():
            return False
        text = dot.read_text(encoding="utf-8", errors="replace")   # 只讀一次；讀不到 → 例外 → 判不了
        value = next((ln[len("gitdir:"):].strip() for ln in text.splitlines() if ln.startswith("gitdir:")), "")
        if not value:
            return False
        gitdir = Path(value) if os.path.isabs(value) else root / value
        return (Path(CLAUDE_DIR) / ".git" / "worktrees").resolve() in gitdir.resolve().parents
    except Exception as e:  # noqa: BLE001
        try:
            sys.stderr.write(f"[Guardian:CommitOrder] 判斷 {run_dir} 是否屬於原子記憶系統 repo 失敗：{type(e).__name__}: {e}\n")
        except OSError:
            pass
        return None


def check_git_commit_order(
    tool_name: str, tool_input: Dict[str, Any], config: Dict[str, Any],
    state: Optional[Dict[str, Any]], cwd: str = "", session_id: str = "",
) -> Optional[str]:
    """Bash/PowerShell `git commit` 且本回合使用者原話無版控口令 → deny 訊息；否則 None。
    規則 COMMIT_ORDER_DECISION_ALWAYS_LOGGED：判出這條指令會 commit 之後，每個結果（擋、口令、引原句、暫存 repo、原子記憶系統
    repo、沒原話紀錄、閘出錯）都留一筆 Logs/guard-commit_order.jsonl；不是 commit 的指令不寫。"""
    msg, event, extra = _commit_order_decide(tool_name, tool_input, config, state, cwd)
    if event:
        from wg_core import append_guard_log
        sid = session_id or str(((state or {}).get("session") or {}).get("id") or "")
        append_guard_log("commit_order", {"event": event, "rule": "COMMIT_ORDER_DECISION_ALWAYS_LOGGED", "session_id": sid,
                                          "allowed": msg is None, "cmd": str(tool_input.get("command") or "")[:200], **extra})
    return msg


def _co_stderr(msg: str) -> None:
    try:
        sys.stderr.write(msg + "\n")
    except OSError:
        pass


def _temp_repo_exempt(command: str, base: str, tool_name: str):
    """規則 TEMP_REPO_COMMIT_EXEMPT：每段 commit 都落在暫存目錄（系統 TEMP、scratchpad、pytest tmp）下的拋棄式 repo → 回放行的
    Verdict（並 stderr 一行）；不豁免回 None。同一套白名單句型（_exempt_run_dirs）判落點，寫法拆不出來就不豁免。
    暫存根與目標兩側都展成長路徑再比（8.3 短路徑）；判的是 commit 實際落的 repo 根，不是執行目錄
    （正式 repo 裡一個叫 scratchpad 的子目錄拿不到豁免；codex 001 BLOCK 6／WARN 9）。"""
    run_dirs = _exempt_run_dirs(command, base, msys_paths=(tool_name == "Bash"))
    if not run_dirs:
        return None
    import tempfile
    from wg_release_rules import norm_temp_path, temp_commit_verdict, temp_roots
    from handlers._shared import _comparable
    from wg_core import find_vcs_root
    roots = [norm_temp_path(_comparable(r)) for r in temp_roots(tempdir=tempfile.gettempdir())]
    hits = [find_vcs_root(Path(_comparable(d))) for d in run_dirs]
    verdicts = [temp_commit_verdict(_comparable(str(h[1])), roots) if h else
                temp_commit_verdict("", roots)._replace(owed=True, why="找不到 commit 落的 repo 根") for h in hits]
    if any(v.owed for v in verdicts):
        return None
    _co_stderr(f"[Guardian:CommitOrder] 規則 {verdicts[0].rule}：{verdicts[0].why}")
    return verdicts[0]


def _commit_order_decide(
    tool_name: str, tool_input: Dict[str, Any], config: Dict[str, Any],
    state: Optional[Dict[str, Any]], cwd: str = "",
) -> Tuple[Optional[str], str, Dict[str, Any]]:
    """口令閘的判定：(擋訊息或 None, 留帳事件（空字串＝不是 commit、不留帳）, 帳的附帶欄位)。"""
    if tool_name not in ("Bash", "PowerShell"):
        return None, "", {}
    cfg = (config.get("guard") or {}).get("commit_order") or {}
    if not cfg.get("enabled", True):
        return None, "", {}
    command = tool_input.get("command", "") or ""
    try:
        _stripped, segments, has_commit = _git_commits_to_run(command, cwd, _tool_shell(tool_name))
        if not has_commit:
            # 包在 shell 包裝／子 shell／eval 裡的 git commit 解析器拆不出來：拆得出內層且確定是查詢才放行，其餘照常檢查口令
            return None, "", {}
        # 原子記憶系統自己的程式與文件不等口令：驗證過就直接上版控（USER.md 例外條）；記憶內容三層由 vcs-sync worker
        # 自動提交，不經此閘。看的是每段 commit 實際落在哪個 repo，不是 session 開在哪；只認看得出落點的寫法
        # （_exempt_run_dirs 白名單），每段都落在 ~/.claude 本身或它的 git worktree 才豁免；其餘照常檢查口令。
        # 拆不出直接的 git commit、是靠包裝或展開判出來的：已知邊界（fail-closed）在擋訊息裡講清楚，讓查詢有路可走
        shape_hint = "" if segments else (
            "\n這次拆不出直接的 git commit，是包裝（bash -c、powershell -Command、cmd /c…）或展開（$()、反引號、eval、括號）"
            "裡可能有 commit：命令裡有 `$()` 等展開又含 commit 字樣時一律要口令；只是查詢的話把 commit 字樣拿掉或改用單引號。")
        base = cwd or str(((state or {}).get("session") or {}).get("cwd") or "")
        temp_ok = _temp_repo_exempt(command, base, tool_name) if segments else None
        if temp_ok is not None:
            return None, "temp_exempt", {"exempt_rule": temp_ok.rule, "why": temp_ok.why[:200]}
        if segments and cfg.get("exempt_cwd_under_claude_dir", True):
            run_dirs = _exempt_run_dirs(command, base, msys_paths=(tool_name == "Bash"))
            verdicts = [_commit_target_is_claude(d) for d in run_dirs or []]
            if verdicts and all(v is True for v in verdicts):
                return None, "claude_exempt", {"run_dirs": list(run_dirs or [])[:5]}
            if run_dirs is None or any(v is None for v in verdicts):
                _co_stderr("[Guardian:CommitOrder] 看不出這次 commit 落在哪個 repo（或寫法不在豁免白名單），不套用豁免，繼續口令檢查")
            if run_dirs is None and _commit_target_is_claude(base) is True:
                shape_hint = ("\n若這次 commit 是在原子記憶系統自己的 repo（或它的 worktree）：豁免只認整條命令由 `&&` 串起、"
                              "第一段可 `cd <絕對路徑>`、其餘每段都是 `git [-C <字面路徑>] add|commit|push|status|diff|log|show|rm|mv|restore …` "
                              "的寫法；把管線、`;`、命令替換、未加引號的 heredoc 拿掉，單獨下 commit 指令就不用口令。")
        prompts = (state or {}).get("recent_user_prompts") or []
        if not prompts:
            try:
                sys.stderr.write("[Guardian:CommitOrder] 無 user prompt 紀錄，口令閘 fail-open\n")
            except OSError:
                pass
            return None, "fail_open", {"why": "沒有使用者原話紀錄"}
        keywords = cfg.get("keywords") or list(_COMMIT_ORDER_DEFAULT_KEYWORDS)
        # 整回合的使用者原話（含 mid-turn 排隊訊息；背景通知內文不在內，見 ups_gates.track_turn_prompts）都算。
        # 空清單＝本回合沒有使用者原話（通知開的回合且口令已用掉）→ 擋；舊 state 沒有 turn_prompts 才退回只看最後一句。
        # 讀取端再濾一次：舊版曾把其他 session 的訊息記進 turn_prompts；濾完是空清單照樣擋（不走 fail-open）
        turn_prompts = user_typed_prompts(state.get("turn_prompts") if isinstance(state.get("turn_prompts"), list) else prompts[-1:])
        from handlers.ups_gates import order_spent
        spent = v6_enabled(config) and order_spent(state)   # v6：這批 commit→push 已做完＝口令用掉了，原話不再算授權
        if spent:
            turn_prompts = []
        keyword = next((k for k in (_commit_order_keyword_hit(p, keywords) for p in turn_prompts) if k), None)
        if keyword:
            return None, "order", {"keyword": keyword}
        quoted = _quoted_authorization(command, turn_prompts)
        if quoted:
            try:
                sys.stderr.write(f"[Guardian:CommitOrder] 依 LLM 引用的使用者原句放行：「{quoted[:80]}」\n")
            except OSError:
                pass
            return None, "quoted", {"quote": quoted[:200]}
        return (
            "[Guardian:CommitOrder] 本回合使用者原話沒有版控口令（上GIT／上乾淨／全上／執P…），"
            "已擋下 git commit。\n"
            "使用者用一般說法授權（例如「好，commit 吧」）：判斷是授權就在指令裡附一行 `# 授權原句：「<使用者本回合的原句>」`，"
            "程式核對原句逐字在本回合使用者原話裡、所在子句沒有否定（「先不要 commit」不算）。\n"
            "契約（USER.md 縮寫指令）：口令前不碰 git——先在收尾報告列「改了哪些檔＋驗了什麼／沒驗什麼」，"
            "等使用者看過 diff 下「上GIT」，再 commit → push 一氣做完；不得先 commit 再等 push。\n"
            "記憶目錄（根層／專案層／公司層）不適用「記憶相關直上」手動 commit：vcs-sync worker 會在收割與 session 結束時"
            "自動 commit＋push，AI 不碰也不問。\n"
            "使用者原話只認剔掉背景通知、其他 session 的訊息、系統注入後的字；那則訊息若夾了這些區塊或標籤字樣而整則不被認，"
            "請使用者單獨再打一次口令（只認最新一則使用者原話，中間夾系統通知或背景事件就要重下口令）。\n"
            "確為使用者本回合要求：引用其原話請他重下口令；長期口令調整 workflow/config.json "
            "guard.commit_order.keywords（enabled=false 停用本閘）。" + shape_hint
            + ("\n這批已 push 完：本回合先前的口令用掉了，再 commit 要使用者新下口令。" if spent else "")
        ), "denied", {"spent": True} if spent else {}
    except Exception as e:
        try:
            sys.stderr.write(f"[Guardian:CommitOrder] 檢查異常（fail-open）：{e}\n")
        except OSError:
            pass
        return None, "error", {"error": f"{type(e).__name__}: {e}"[:200]}


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
    low = command.lower()                       # 與口令閘同一套：Git／GIT.EXE 不分大小寫
    if "git" not in low:
        return None   # 快篩，省 regex/子行程；不看 commit 字樣：git 別名（`git ci`）的命令裡沒有
    try:
        # 這次會提交哪些檔跟病形閘同一份判法（tools/project-smells.py commit_entries）：暫存區、commit -a、commit <路徑>，
        # 加上同一條指令前面 git add 要加進來的檔（PreToolUse 時 add 還沒跑，只看暫存區會讓 `git add .env && git commit` 漏過）
        tool = _smells_tool()
        adds: List[Tuple[str, List[str]]] = []
        for repo_cd, tokens in _git_segments(_strip_heredoc_bodies(command), {"add", "commit"}, _tool_shell(tool_name),
                                             cwd):
            run_cwd = _resolve_run_cwd(repo_cd, cwd, _tool_shell(tool_name))
            if tokens[0].lower() == "add":
                adds.append((run_cwd, tokens))
                continue
            try:
                found = tool.commit_entries(run_cwd, tokens, list(adds))
            except tool.SmellsError:
                continue   # fail-open
            if not found:
                continue
            repo_root, _base, _has_head, entries = found
            files = [rel for rel, (src, _old) in entries.items() if src != "gone"]
            if not files:
                continue
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


# ─── commit 前病形閘（G2：帶病的改動上不了版）──────────────────────────────
# 查的是這次真的會進版的內容（暫存區、commit -a、commit <路徑>、同一條指令前面 git add 才要加進來的檔、svn commit 的
# 工作副本改動），不是本 session 改了哪些檔。新寫進的病 → deny 並點名病名、檔、行；舊碼原本就有、這次沒碰的 → 只列出。
# 怎麼判（病形、新舊之分、smell-ok 放行）全在 tools/project-smells.py「commit 前病形檢查」段；這裡只拆指令、交給它、出訊息。
# 判不了（拆不出 commit 落點、寫法拆不準要提交什麼（_commit_shape_problem）、git 查詢失敗、檢查出錯）一律擋；
# guard.smell_gate.enabled=false 停用。
_SMELLS_TOOL = Path(__file__).resolve().parents[2] / "tools" / "project-smells.py"
_SMELL_REPO_OVERRIDE_RE = re.compile(r"--git-dir\b|--work-tree\b|\bGIT_(?:DIR|WORK_TREE|INDEX_FILE)\s*=", re.I)


def _smells_tool():
    mod = sys.modules.get("project_smells")
    if mod is None or not hasattr(mod, "check_commit"):
        spec = importlib.util.spec_from_file_location("project_smells", _SMELLS_TOOL)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["project_smells"] = mod
        spec.loader.exec_module(mod)
    return mod


def _tool_shell(tool_name: str) -> str:
    """工具名 → _scan_segments 的 shell（決定跳脫規則）。"""
    return "powershell" if tool_name == "PowerShell" else "bash"


def _quote_split(raw: str, shell: str) -> Tuple[str, str]:
    """一個 token 的原文 → (引號外的字, 雙引號裡的字)：跳脫過的字與單引號裡的字（shell 照字面）都不算，規則同 _scan_segments。"""
    bare: List[str] = []
    dq: List[str] = []
    quote, i = "", 0
    while i < len(raw):
        ch = raw[i]
        if _escaped(raw, i, quote, shell):
            i += 2
            continue
        if ch == quote:
            quote = ""
        elif quote == '"':
            dq.append(ch)
        elif not quote and ch in "\"'":
            quote = ch
        elif not quote:
            bare.append(ch)
        i += 1
    return "".join(bare), "".join(dq)


# 引號外會被 shell 換成看不到的字、或拆成好幾個參數的寫法。Bash：`$x`、`$(…)`、`${…}`、反引號、`{a,b}`／`{1..3}`；
# PowerShell 的單純變數 `$x` 是一個參數（字串不拆），`$(…)`／`@(…)`／`@x` 可能攤成好幾個、`{…}` 是程式區塊。開頭 `~` 兩邊都算。
_BASH_EXPANSION_RE = re.compile(r"\$[\w({@*#?!$]|`|\{[^}]*(?:,|\.\.)[^}]*\}")
_PS_EXPANSION_RE = re.compile(r"[$@]\(|@\w|\{")


def _dynamic_path(vcs: str, pairs: List[Tuple[str, str]], shell: str, tool) -> str:
    """commit／add 段裡當路徑用、而且會被 shell 展開（引號外或雙引號裡有沒跳脫的 `$`、反引號）的 token 原文；沒有回 ""。
    字面拿去查會查不到、看成沒東西要提交；單引號裡的 `$`（`'routes/$id.tsx'`）是字面檔名，照查。
    哪個 token 是路徑交給 project-smells 的同一份文法（add_specs／commit_options／svn_commit_args）：把會展開的 token
    換成記號再拆，記號落在路徑裡就是它。選項（`-` 開頭，含 `--message="$x"`）與重導向（`2>$null`）不換。"""
    live = set()
    for k, (raw, value) in enumerate(pairs[1:], 1):
        if value.startswith("-") or tool._REDIRECT_RE.match(value):
            continue
        if re.search(r"[$`]", "".join(_quote_split(raw, shell))):
            live.add(k)
    if not live:
        return ""
    marked = [f"\0{k}" if k in live else value for k, (_raw, value) in enumerate(pairs)]
    if marked[0].lower() == "add":
        paths = tool.add_specs(marked)[0]
    elif vcs == "git":
        paths = tool.commit_options(marked)["paths"]
    else:
        paths = tool.svn_commit_args(marked)[0]
    hit = next((p for p in paths if p.startswith("\0")), "")
    return pairs[int(hit[1:])][0] if hit else ""


def _commit_shape_problem(command: str, shell: str, tool, cwd: str = "") -> str:
    """git／svn commit 段拆不準要提交什麼的原因；拆得準回 ""。拆不準＝引號或 here-string 沒閉合（後面的分隔符號與路徑
    都可能被吞進訊息裡）、commit 落點（cd／-C）是變數、commit 段（與同一條指令裡會改變提交範圍的 git add 段）有引號外的
    展開（-m 的邊界與路徑都不準）、或路徑本身是變數（_dynamic_path）。重導向（`2>$null`）不是參數，用 project-smells 的
    _not_args 跳過。tool＝project-smells 模組；cwd＝tool cwd（git 別名展開後是 commit 的段照查）。"""
    problems: List[str] = []
    segs = ([("git", cd, p) for cd, p in _vcs_segment_pairs(command, {"add", "commit"}, ("git", "git.exe"),
                                                           _GIT_VALUE_FLAGS, problems, shell, alias_cwd=cwd)]
            + [("svn", cd, p) for cd, p in _vcs_segment_pairs(command, {"commit", "ci"}, ("svn", "svn.exe"),
                                                             _SVN_VALUE_FLAGS, shell=shell)])
    if problems:
        return problems[0]
    expansion = _PS_EXPANSION_RE if shell == "powershell" else _BASH_EXPANSION_RE
    for vcs, repo_cd, pairs in segs:
        if "$" in repo_cd or "`" in repo_cd:
            return f"commit 落點 `{repo_cd}` 是變數"
        for raw in tool._not_args([r for r, _ in pairs[1:]]):
            bare = _quote_split(raw, shell)[0]
            if bare.startswith("~") or expansion.search(bare):
                return f"`{raw[:60]}` 在引號外有展開，shell 會把它換成看不到的字或拆成好幾個參數"
        path = _dynamic_path(vcs, pairs, shell, tool)
        if path:
            return f"路徑 `{path[:60]}` 是變數或命令替換，字面拿去查會查不到"
    return ""


def check_smell_gate(
    tool_name: str, tool_input: Dict[str, Any], cwd: str, config: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str]]:
    """Bash/PowerShell 的 git／svn commit → (deny 訊息, 只提醒的訊息)；都沒有回 (None, None)。"""
    if tool_name not in ("Bash", "PowerShell"):
        return None, None
    if not ((config.get("guard") or {}).get("smell_gate") or {}).get("enabled", True):
        return None, None
    command = tool_input.get("command", "") or ""
    low = command.lower()
    if "git" not in low and "svn" not in low:   # 不看 commit 字樣：git 別名（`git ci`）的命令裡沒有
        return None, None
    shell = _tool_shell(tool_name)
    body = _strip_heredoc_bodies(command)
    has_git_commit = _git_commits_to_run(command, cwd, shell)[2]
    svn_segs = _svn_segments(body, {"commit", "ci"}, shell) if "svn" in low else []
    if not has_git_commit and not svn_segs:
        return None, None
    git_segs = _git_segments(body, {"add", "commit"}, shell, cwd) if has_git_commit else []
    if has_git_commit and (not any(t[0].lower() == "commit" for _cd, t in git_segs) or _hidden_commit(body, cwd, shell)):
        return ("[Guardian:SmellGate] 這條指令裡有 git commit 包在 bash -c／powershell -Command／$()、commit 訊息裡的 "
                "$(…)、`!` 開頭或查不到的 git 別名之類的包裝裡（同一條指令另有直接寫的 commit 也一樣），拆不出它落在哪個 "
                "repo、要提交哪些檔，病形檢查判不了，一律擋。把 git commit 直接寫在指令裡再下一次。"), None
    if has_git_commit and _SMELL_REPO_OVERRIDE_RE.search(body):
        return ("[Guardian:SmellGate] 這條 git commit 用 --git-dir／--work-tree 或 GIT_DIR／GIT_WORK_TREE／GIT_INDEX_FILE "
                "指定 repo，病形檢查重現不了它實際提交哪個 repo、哪份暫存區，判不了，一律擋。改用 `git -C <repo> commit` 或先 cd 進 repo。"), None
    try:
        tool = _smells_tool()
        problem = _commit_shape_problem(body, shell, tool, cwd)
        if problem:
            return (f"[Guardian:SmellGate] 這條 commit 指令的寫法拆不出要提交什麼（{problem}），病形檢查判不了，一律擋。"
                    "請改成單行 `-m \"…\"`（要分段就給多個 -m，或把訊息寫進檔案用 `-F <檔>`），路徑與 repo 位置直接寫字面值"
                    "（檔名本身有 `$` 就用單引號包起來），再下一次。"), None
        results, adds, repos = [], [], []
        for repo_cd, tokens in git_segs:
            run_cwd = _resolve_run_cwd(repo_cd, cwd, shell)
            if tokens[0].lower() == "add":
                adds.append((run_cwd, tokens))
                continue
            res = tool.check_commit("git", run_cwd, tokens, list(adds), config)
            if res is not None:
                results.append(res)
                repos.append(run_cwd)
        for repo_cd, tokens in svn_segs:
            run_cwd = _resolve_run_cwd(repo_cd, cwd, shell)
            res = tool.check_commit("svn", run_cwd, tokens, [], config)
            if res is not None:
                results.append(res)
                repos.append(run_cwd)
        return tool.render_commit_report(results, repos[0] if repos else cwd)
    except Exception as e:
        return (f"[Guardian:SmellGate] commit 前病形檢查出錯，判不了一律擋：{type(e).__name__}: {e}\n"
                f"手動重查：python ~/.claude/tools/project-smells.py --commit-check --cwd <repo>；"
                "確定是檢查本身壞了，照實告訴使用者（workflow/config.json 的 guard.smell_gate.enabled=false 可暫停本閘）。"), None


# ─── 索引三檔合併驅動閘（advisory-only，永不 deny）─────────────────────────
# 多機共享記憶庫：兩機各加 atom 後 pull/rebase，索引三檔（MEMORY.md 計數表／_ATOM_INDEX.md／
# _atom_index.json）同區塊各加一列必衝突。兩層自動化（workflow/config.json merge_driver）：
#   (A) auto_install：合併類 git 指令（pull/merge/rebase/cherry-pick/stash pop|apply）前，
#       本機未裝語意合併驅動 → 自動 `merge-atom-index.py --install`（git 全域設定，各機一次）。
#   (B) auto_resolve：解衝突收尾指令（rebase/merge/cherry-pick --continue、commit、stash pop|apply）
#       前，索引三檔仍 unmerged → 先 `--resolve`（語意合併 stages 並 git add），再放行原指令。
#       不含 `git add`：使用者自己 add 索引檔即 git 已解除 stage，B 在此多餘。
# 唯一權威＝`git ls-files -u`（index-only、涵蓋 stash／worktree）。全程 fail-open、總時限 2.5s、
# Windows-safe（CREATE_NO_WINDOW；hook 跑在 pythonw 下，子行程直譯器改用同目錄 python.exe）。
_INDEX_FILE_NAMES = frozenset({"MEMORY.md", "_ATOM_INDEX.md", "_atom_index.json", "_INDEX.md", "_local_catalog.md"})
# 用 hook 自己的檔案位置定位工具，不靠 HOME 推導（HOME 被覆寫的環境下 CLAUDE_DIR 會指錯地方）
_MERGE_TOOL = Path(__file__).resolve().parents[2] / "tools" / "merge-atom-index.py"
_MERGE_GATE_BUDGET_S = 2.5
_MERGE_RESOLVE_SUBS = {"rebase", "merge", "cherry-pick", "commit", "stash"}
_MERGE_INSTALL_SUBS = {"pull", "merge", "rebase", "cherry-pick", "stash"}
_MERGE_MANUAL_RESOLVE = "手動 python ~/.claude/tools/merge-atom-index.py --resolve"
_MERGE_MANUAL_INSTALL = "手動 python ~/.claude/tools/merge-atom-index.py --install"


def _hook_python_exe() -> str:
    """子行程直譯器（本體在 wg_core.hook_python_exe，與 wg_reading_path 共用）：hook 在 pythonw.exe 下跑就改用同目錄 python.exe。"""
    from wg_core import hook_python_exe
    return hook_python_exe()


def _run_capture(args: List[str], cwd: str, timeout: float) -> subprocess.CompletedProcess:
    """A/B 共用的 Windows-safe 子行程：capture、UTF-8、errors=replace、timeout、不閃窗。
    不吞例外（TimeoutExpired 由 caller 轉成 ⚠ advisory）。"""
    return subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, cwd=cwd or None,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def _stash_pop_or_apply(tokens: List[str]) -> bool:
    return any(t.lower() in ("pop", "apply") for t in tokens[1:])


def _is_resolve_trigger(tokens: List[str]) -> bool:
    sub = tokens[0].lower()
    if sub == "commit":
        return True
    if sub in ("rebase", "merge", "cherry-pick"):
        return "--continue" in tokens
    if sub == "stash":
        return _stash_pop_or_apply(tokens)
    return False


def _is_install_trigger(tokens: List[str]) -> bool:
    sub = tokens[0].lower()
    if sub in ("pull", "merge", "rebase", "cherry-pick"):
        return True
    if sub == "stash":
        return _stash_pop_or_apply(tokens)
    return False


def _unmerged_index_files(run_cwd: str, timeout: float) -> Optional[List[str]]:
    """`git ls-files -u -z` 解出仍 unmerged 的索引三檔 repo 相對路徑。
    None＝查不到（非 repo／git 失敗）→ caller 當「無資訊」跳過；[]＝沒有。"""
    if not run_cwd or not os.path.isdir(run_cwd):
        return None
    r = _run_capture(["git", "ls-files", "-u", "-z"], run_cwd, timeout)
    if r.returncode != 0:
        return None
    found: List[str] = []
    for entry in (r.stdout or "").split("\0"):
        if "\t" not in entry:
            continue
        path = entry.split("\t", 1)[1]
        if path.rsplit("/", 1)[-1] in _INDEX_FILE_NAMES and path not in found:
            found.append(path)
    return found


_SVN_RESOLVE_SUBS = {"commit", "ci", "resolve", "resolved"}
_SVN_ACCEPT_PICKS = {"base", "mine-full", "theirs-full", "mine-conflict", "theirs-conflict", "mf", "tf", "mc", "tc"}


def _is_svn_resolve_trigger(tokens: List[str]) -> bool:
    """svn commit/ci 一律；svn resolve 只在沒明確選邊時（--accept working/postpone 或未給）——
    使用者已指定 mine-full/theirs-full 等就是他的決定，不搶先合併。svn update 不是觸發（無驅動可裝）。"""
    sub = tokens[0].lower()
    if sub in ("commit", "ci"):
        return True
    if sub not in ("resolve", "resolved"):
        return False
    for i, t in enumerate(tokens):
        if t.startswith("--accept="):
            val = t.split("=", 1)[1]
        elif t == "--accept" and i + 1 < len(tokens):
            val = tokens[i + 1]
        else:
            continue
        if val.lower() in _SVN_ACCEPT_PICKS:
            return False
    return True


def _svn_derived_exit_hint(run_cwd: str, rels: List[str]) -> str:
    """svn 索引自動合併只是暫時處置：_atom_index.json／_ATOM_INDEX.md 是衍生檔，正解是退出版控。
    把確切指令附在同一行（措辭與 lib/vcs_ignore 同源；SessionStart 的 [Guardian:VcsIgnore] 也會提）。
    rels＝相對 WC 根的路徑；沒有衍生檔或 lib 不在 → 空字串。"""
    try:
        from vcs_ignore import DERIVED_FILES, derived_exit_hint
    except ImportError:
        return ""
    root = find_svn_root(Path(run_cwd))
    if root is None:
        return ""
    paths = [root / rel for rel in rels if Path(rel).name in DERIVED_FILES]
    if not paths:
        return ""
    return "自動合併只是暫時處置——" + derived_exit_hint("svn", paths)


def _svn_unmerged_index_files(run_cwd: str, timeout: float) -> Optional[List[str]]:
    """svn 工作副本裡 update 後仍衝突的索引三檔（相對 WC 根）。
    純檔案系統先找 .svn（不是 svn WC → None、零子行程），再只對 memory dir 候選跑 `svn status --xml`
    （整個 WC 的 status 要 3～6 秒，超出預算）。None＝查不到；[]＝沒有。"""
    if not run_cwd or not os.path.isdir(run_cwd):
        return None
    root = find_svn_root(Path(run_cwd))  # git 疊在 svn 上時 find_vcs_root 回 git，svn 側要另找
    if root is None:
        return None
    dirs = memory_dir_candidates(Path(run_cwd), root)
    if not dirs:
        return []
    r = _run_capture(["svn", "--non-interactive", "status", "--xml", "--", *map(str, dirs)], str(root), timeout)
    if r.returncode != 0 or not (r.stdout or "").strip():
        return None
    found: List[str] = []
    for ent in ET.fromstring(r.stdout).iter("entry"):
        ws = ent.find("wc-status")
        if ws is None or ws.get("item") != "conflicted":
            continue
        p = Path(ent.get("path", ""))
        if p.name not in _INDEX_FILE_NAMES:
            continue
        try:
            rel = (p if p.is_absolute() else root / p).resolve().relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            continue
        if rel not in found:
            found.append(rel)
    return found


def _resolve_json(stdout: str) -> Optional[Dict[str, Any]]:
    """--resolve 的 stdout 契約是單行 JSON；保守取最後一個非空行解析。"""
    for ln in reversed((stdout or "").splitlines()):
        ln = ln.strip()
        if ln:
            try:
                d = json.loads(ln)
                return d if isinstance(d, dict) else None
            except ValueError:
                return None
    return None


_NON_ASCII_RE = re.compile(r"[^\x00-\x7f]")
_SVN_ENCODING_WARN = ("[Guardian:SvnEncoding] 中文路徑的 svn add 請交給 vcs-sync 背景提交"
                      "（手動 add 曾產生亂碼資料夾）")


def check_svn_encoding(tool_name: str, tool_input: Dict[str, Any]) -> Optional[str]:
    """Bash／PowerShell 的 `svn add` 帶非 ASCII 路徑 → 提醒改走 vcs-sync。只警告、零子行程、永不 deny。
    （某專案的 `shared/UIºt¥X` 就是 session 內手動 svn add 中文路徑，位元組經 shell 轉碼後進了工作副本。）"""
    if tool_name not in ("Bash", "PowerShell"):
        return None
    command = tool_input.get("command", "") or ""
    if "svn" not in command.lower():
        return None
    for _cd, tokens in _svn_segments(command, {"add"}):
        if any(_NON_ASCII_RE.search(t) for t in tokens[1:]):
            return _SVN_ENCODING_WARN
    return None


# svn 測試路徑閘：svn commit 段的路徑參數含測試目錄（test／tests／__tests__）或 *Test.<副檔名> 檔就擋；commit 訊息不看
_SVN_TEST_PATH_RE = re.compile(r"(?:^|[/\\])(?:tests?|__tests__)(?:[/\\]|$)"
                               r"|(?:^|[/\\])[^/\\]*Test\.(?:cs|py|js|ts|tsx|jsx|go|java)$", re.IGNORECASE)
# 使用者本回合明說要把測試上 svn：AI 在指令裡逐字引用那一句（判斷交 AI，程式核對原句在本回合原話裡、沒被否定）
_SVN_TEST_QUOTE_RE = re.compile(r"測試上\s*svn\s*原句\s*[:：]\s*「([^」\n]+)」", re.IGNORECASE)
_SVN_TEST_QUOTE_MIN = 4


def _svn_test_block_on(run_cwd: str, config: Dict[str, Any]) -> bool:
    """這段 svn commit 落的專案有沒有開測試路徑閘：OverviewHub 四層合併後的 svn_test_block.enabled（預設關；專案層
    <專案根>/.claude/overview-hub.json 寫 true 才開）。專案根：往上有部位表取表的根，沒有照無表那條路（認領／標記，退 VCS 根）。
    設定讀不到當關，浮 stderr。"""
    try:
        from wg_overview import _cfg as _hub_cfg, _unmapped_root_of, find_map
        hit = find_map(run_cwd)
        root = hit[0] if hit else _unmapped_root_of(run_cwd)
        sec = _hub_cfg(config, root).get("svn_test_block")
        return isinstance(sec, dict) and sec.get("enabled") is True
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[Guardian:SvnTestBlock] 讀不到專案的 svn_test_block 設定，這次當關：{type(e).__name__}: {e}\n")
        return False


def _svn_test_quote(command: str, turn_prompts: List[str]) -> Optional[str]:
    """指令裡「測試上 svn 原句：「…」」的原句：逐字出現在使用者本回合原話裡、所在子句沒被否定（與授權原句同一套
    _quote_authorizes；「不要提交測試」引用了也不算）、至少 _SVN_TEST_QUOTE_MIN 字 → 回原句；否則 None。"""
    for q in (x.strip() for x in _SVN_TEST_QUOTE_RE.findall(command or "")):
        if len(q) < _SVN_TEST_QUOTE_MIN:
            continue
        for p in turn_prompts:
            i = p.find(q)
            if i >= 0 and _quote_authorizes(p, i, q):
                return q
    return None


def check_svn_test_block(tool_name: str, tool_input: Dict[str, Any], cwd: str, config: Dict[str, Any],
                         state: Optional[Dict[str, Any]], session_id: str = "") -> Optional[str]:
    """Bash／PowerShell 的 svn commit：路徑參數（svn_commit_args 拆出來的，-m 訊息與帶值選項的值不算）含測試檔或測試目錄、
    而且那個專案開了閘（_svn_test_block_on）→ 擋。指令裡的原句出口（_svn_test_quote）對得上 → 放行。
    放行與擋都留帳 Logs/guard-svn_test_block.jsonl。"""
    if tool_name not in ("Bash", "PowerShell"):
        return None
    command = tool_input.get("command", "") or ""
    if "svn" not in command.lower():
        return None
    shell = _tool_shell(tool_name)
    hits: List[str] = []
    try:
        for repo_cd, tokens in _svn_segments(_strip_heredoc_bodies(command), {"commit", "ci"}, shell):
            paths = [p for p in _smells_tool().svn_commit_args(tokens)[0] if _SVN_TEST_PATH_RE.search(p)]
            if paths and _svn_test_block_on(_resolve_run_cwd(repo_cd, cwd, shell), config):
                hits += [p for p in paths if p not in hits]
    except Exception as e:  # noqa: BLE001  閘預設關、守的是專案慣例：拆不出路徑不擋，浮 stderr 並留帳
        err = f"{type(e).__name__}: {e}"
        sys.stderr.write(f"[Guardian:SvnTestBlock] 拆不出 svn commit 的路徑，這次不擋：{err}\n")
        append_guard_log("svn_test_block", {"event": "error", "rule": "GATE_SELF_ERROR", "session_id": session_id, "tool": tool_name,
                                            "error": err})
        return None
    if not hits:
        return None
    turn = user_typed_prompts(state.get("turn_prompts")) if isinstance((state or {}).get("turn_prompts"), list) else []
    quote = _svn_test_quote(command, turn)
    append_guard_log("svn_test_block", {"event": "user_quote" if quote else "denied", "session_id": session_id,
                                        "tool": tool_name, "paths": hits, **({"quote": quote} if quote else {})})
    if quote:
        return None
    return (f"[Guardian:SvnTestBlock] 這次 svn commit 的路徑含測試檔或測試目錄：{'、'.join(hits)}。"
            "這個專案設定測試／練習檔不上 svn（overview-hub.json 的 svn_test_block）。\n"
            "- 不是要提交測試 → 把這幾個路徑從 commit 的路徑清單拿掉再提交；\n"
            "- 使用者本回合明說要把測試一起上 svn → 在這條指令開頭加一行 "
            "`# 測試上 svn 原句：「<使用者本回合原話裡說要提交測試的那一句，逐字照抄>」`，原句在本回合原話裡、沒被否定就放行並留帳；\n"
            "- 拿不準 → 先問使用者。")


def check_merge_driver(
    tool_name: str, tool_input: Dict[str, Any], cwd: str, config: Dict[str, Any]
) -> Optional[str]:
    """Bash/PowerShell git 指令前的索引三檔合併自動化。回 advisory 字串或 None；永不 deny。
    省錢階梯：工具名 → 字串含 git → 拆段命中 → 才動子行程；(B) 命中後不再跑 (A)。"""
    if tool_name not in ("Bash", "PowerShell"):
        return None
    mcfg = config.get("merge_driver") or {}
    auto_resolve = bool(mcfg.get("auto_resolve", True))
    auto_install = bool(mcfg.get("auto_install", True))
    if not (auto_resolve or auto_install):
        return None
    command = tool_input.get("command", "") or ""
    low = command.lower()
    if "git" not in low and "svn" not in low:
        return None
    try:
        git_segs = _git_segments(command, _MERGE_RESOLVE_SUBS | _MERGE_INSTALL_SUBS) if "git" in low else []
        svn_segs = _svn_segments(command, _SVN_RESOLVE_SUBS) if "svn" in low else []
        if not git_segs and not svn_segs:
            return None
        deadline = time.monotonic() + _MERGE_GATE_BUDGET_S

        def _left(cap: float) -> float:
            return max(0.05, min(cap, deadline - time.monotonic()))

        interp = _hook_python_exe()

        # (B) 解衝突收尾指令 → 索引三檔仍 unmerged（git stage／svn conflicted）就先 --resolve
        if auto_resolve:
            tagged = [("git", cd, tk) for cd, tk in git_segs] + [("svn", cd, tk) for cd, tk in svn_segs]
            for kind, repo_cd, tokens in tagged:
                is_git = kind == "git"
                if not (_is_resolve_trigger(tokens) if is_git else _is_svn_resolve_trigger(tokens)):
                    continue
                run_cwd = _resolve_run_cwd(repo_cd, cwd, _tool_shell(tool_name))
                finder = _unmerged_index_files if is_git else _svn_unmerged_index_files
                try:
                    unmerged = finder(run_cwd, _left(1.0))
                except subprocess.TimeoutExpired:
                    return (f"[Guardian:IndexConflict] ⚠ 索引檔衝突檢查逾時（{'git ls-files' if is_git else 'svn status'}）"
                            f" → {_MERGE_MANUAL_RESOLVE}")
                if not unmerged:
                    continue
                try:
                    r = _run_capture(
                        [interp, str(_MERGE_TOOL), "--resolve", "--vcs", kind, "--cwd", run_cwd, "--quiet"],
                        run_cwd, _left(_MERGE_GATE_BUDGET_S),
                    )
                except subprocess.TimeoutExpired:
                    return (f"[Guardian:IndexConflict] ⚠ 索引檔自動解逾時（{', '.join(unmerged)}）"
                            f" → {_MERGE_MANUAL_RESOLVE}")
                d = _resolve_json(r.stdout)
                if d is None:
                    tail = ((r.stderr or "").strip().splitlines() or [f"rc={r.returncode}"])[-1]
                    return (f"[Guardian:IndexConflict] ⚠ 索引檔自動解未完成：{tail}"
                            f" → {_MERGE_MANUAL_RESOLVE}")
                remaining = [str(x) for x in (d.get("remaining") or [])]
                error = d.get("error")
                if remaining or error or r.returncode != 0:
                    why = error or ", ".join(remaining) or f"rc={r.returncode}"
                    return (f"[Guardian:IndexConflict] ⚠ 索引檔自動解未完成：{why}"
                            f" → {_MERGE_MANUAL_RESOLVE}")
                resolved = [str(x) for x in (d.get("resolved") or [])]
                staged = [str(x) for x in (d.get("staged_user_version") or [])]
                parts = []
                if resolved:
                    parts.append(f"已自動合併並 {'add' if is_git else '標記 resolved'} 索引檔：{', '.join(resolved)}")
                if staged:
                    parts.append(f"已{'stage' if is_git else '標記 resolved'} 你解好的版本：{', '.join(staged)}")
                if not parts:
                    parts.append("索引三檔已無未合併項")
                if not is_git:
                    hint = _svn_derived_exit_hint(run_cwd, resolved + staged)
                    if hint:
                        parts.append(hint)
                return "[Guardian:IndexConflict] " + "；".join(parts)

        # (A) 合併類 git 指令 → 本機未裝驅動就自動 --install（只對第一個命中段做一次；svn 無驅動可裝）
        if auto_install:
            for repo_cd, tokens in git_segs:
                if not _is_install_trigger(tokens):
                    continue
                run_cwd = _resolve_run_cwd(repo_cd, cwd, _tool_shell(tool_name))
                try:
                    chk = _run_capture(
                        [interp, str(_MERGE_TOOL), "--is-installed", "--cwd", run_cwd],
                        cwd, _left(1.5),
                    )
                    if chk.returncode == 0:
                        return None
                    ins = _run_capture(
                        [interp, str(_MERGE_TOOL), "--install", "--quiet"], cwd, _left(1.5),
                    )
                except subprocess.TimeoutExpired:
                    return f"[Guardian:MergeDriver] ⚠ 驅動安裝檢查逾時 → {_MERGE_MANUAL_INSTALL}"
                if ins.returncode == 0:
                    return "[Guardian:MergeDriver] 已自動安裝索引三檔合併驅動（git 全域設定，各機一次）"
                tail = ((ins.stderr or ins.stdout or "").strip().splitlines() or [f"rc={ins.returncode}"])[-1]
                return f"[Guardian:MergeDriver] ⚠ 驅動安裝失敗：{tail} → {_MERGE_MANUAL_INSTALL}"
    except Exception as e:
        try:
            sys.stderr.write(f"[Guardian:MergeDriver] 檢查異常（fail-open）：{e}\n")
        except OSError:
            pass
    return None


def handle_judge_pre_tool_use(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    """裁判子 session（CLAUDE_COMPANION_JUDGE=1）的 PreToolUse：只跑「寫入目標判不出 → 放行並留帳 judge_write」這一道
    （與主 session 的 OverviewHub 同一個判定：wg_core.write_paths_from_tool）；其他閘、注入、state 一律不碰（防裁判觸發裁判）。"""
    tool_name = input_data.get("tool_name", "") or ""
    if tool_name not in ("Bash", "PowerShell"):
        output_nothing()
        return
    from wg_core import write_paths_from_tool
    unknown = [t for t in write_paths_from_tool(tool_name, input_data.get("tool_input") or {}, input_data.get("cwd") or None)
               if t.startswith("UNKNOWN:")]
    if unknown:              # 規則 UNKNOWN_TARGET_LOGGED：判不出就放行並留帳
        from wg_core import append_guard_log
        append_guard_log("judge_write", {"event": "unknown_target", "session_id": str(input_data.get("session_id") or ""),
                                         "target": unknown[0][:120], "allowed": True})
    # 驗證批次閘裁判也適用（不碰 state：沒有收據與擋次帳，只判整組驗證要口令；裁判沒有使用者原話，整組一律擋）
    import wg_verify_batch
    deny_reason = wg_verify_batch.check(tool_name, input_data.get("tool_input") or {}, config, None,
                                        input_data.get("cwd") or "", str(input_data.get("session_id") or ""))
    if deny_reason:
        output_json({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                            "permissionDecisionReason": deny_reason}})
        return
    output_nothing()


def _with_cards(input_data: Dict[str, Any], config: Dict[str, Any], text: str, path: str) -> str:
    """切入點契約（TECH §7.10）：text 原樣在前，認出切入點就接判準卡並留帳。只在真的要送訊息（deny 或提醒）時才呼叫，
    一般工具什麼都不送的放行路徑不匯入、不讀登錄表。"""
    if not v6_enabled(config):      # 判準卡是 v6 才有
        return text
    from handlers._shared import entry_note, with_note
    return with_note(text, entry_note(text, path, session_id=str(input_data.get("session_id") or ""), config=config))


def _remind_later(input_data: Dict[str, Any], state: Optional[Dict[str, Any]], hit: Dict[str, Any], guard: str, **kw: Any) -> bool:
    """PreToolUse 的提醒出口（規則 REMIND_ON_PRIOR_RESULT、REMIND_PENDING_IN_STATE）：這一件判成 remind、不擋 → 留帳 event=remind
    （guard＝哪一道閘的守門紀錄；overview_hub 走 hub log）、記進 state 的待提醒，由下一個工具結果（PostToolUse）送一行。
    state 拿不到（讀不到、沒 session）就只 stderr＋留帳，回 False；呼叫端負責把 state 寫回。"""
    from wg_core import append_guard_log as _glog
    sid = str(input_data.get("session_id") or "")
    row = {"event": "remind", "rule": hit["rule"], "obj": hit.get("obj") or "", "session_id": sid,
           "tool": str(input_data.get("tool_name") or ""), **kw}
    if guard == "overview_hub":
        from wg_overview import _log as _hub_log
        _hub_log("edit_remind", sid, part=hit.get("obj") or None, **{k: v for k, v in row.items() if k not in ("event", "session_id", "obj")})
    else:
        _glog(guard, row)
    if not isinstance(state, dict):
        sys.stderr.write(f"[Guardian:{guard}] 提醒記不進 state（{hit['rule']}），這次只留帳：{hit.get('what', '')}\n")
        return False
    from wg_overview import REMIND_SENT_KEY, remind_queue
    if not _rr.remind_due(state.get(REMIND_SENT_KEY) or [], hit["rule"], hit.get("obj")):
        return False                              # 同規則同對象本 session 提醒過：只留帳、不再排
    remind_queue(state, hit)
    return True


def _deny(input_data: Dict[str, Any], config: Dict[str, Any], reason: str, watched: Sequence[str] = (),
          target: str = "") -> None:
    """PreToolUse 的 deny 出口（裁判子 session 除外）：擋不擋由呼叫端決定，這裡只負責把問句送出去、接判準卡。
    v6 先交連鎖斷路器記一筆觸發（閘名取擋訊息的標記）：警報後只記錄 → 不擋、存快照後放行；這一次讓警報響 → 改送中止停手訊息。
    watched／target＝這次擋的對象（擋的檔／定位閘的部位，規則 CHAIN_SAME_GATE_PER_OBJECT）：每個部位、每個檔各要各的證據的閘才報，
    說不出擋什麼的閘（版控口令、病形閘這類看整批提交的）不報，斷路器照舊只看閘名。"""
    try:
        chain = _chain_ctx(input_data, config, need_ledger=False)
        r = chain_store.gate_fired(chain[0], chain[1], wg_chain.gate_name(reason, "PreToolUse"), reason, input_data,
                                   config, watched=watched, target=target) if chain else chain_store.PASS
    except Exception as e:  # noqa: BLE001  斷路器壞了不能讓閘跟著壞：照原本的擋
        sys.stderr.write(f"[chain-breaker] 工具前記觸發出錯，照原本的閘行為：{type(e).__name__}: {e}\n")
        chain, r = None, chain_store.PASS
    if chain is not None:
        if r.halt:
            output_json({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                "permissionDecisionReason": r.halt}})
            return
        if r.record_only:
            sys.stderr.write(f"[Guardian:ChainBreaker] 連鎖中止中：{wg_chain.gate_name(reason, 'PreToolUse')} 這次只記錄，不擋\n")
            _chain_before_write(input_data, config, chain)
            output_nothing()
            return
    output_json({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                        "permissionDecisionReason": _with_cards(input_data, config, reason, "pretool_deny")}})


def _chain_ctx(input_data: Dict[str, Any], config: Dict[str, Any], need_ledger: bool = True) -> Optional[Tuple[str, int]]:
    """連鎖斷路器要用的 (session_id, 使用者回合)；v6 關、沒 session、（need_ledger）這個 session 還沒有連鎖帳 → None。
    沒有帳就不可能在中止中、也沒開連鎖段，先看帳在不在，免得每次工具呼叫都讀 state。"""
    sid = str(input_data.get("session_id") or "")
    if not sid or not v6_enabled(config) or (need_ledger and not chain_store.ledger_path(sid).exists()):
        return None
    from wg_release_rules import user_turn
    state = read_state(sid) or {}
    return sid, user_turn(state, int(state.get("turn_seq", 0) or 0))


def _chain_before_write(input_data: Dict[str, Any], config: Dict[str, Any], chain: Optional[Tuple[str, int]] = None) -> None:
    """工具真的要改檔之前（放行出口）：連鎖段開著就先存快照（chain_store.before_write；判定在 wg_chain.snapshot_need）。
    出錯只浮 stderr、照放行（還原時這個檔列成沒快照）。"""
    tool_name = input_data.get("tool_name", "") or ""
    if tool_name not in ("Write", "Edit", "MultiEdit", "NotebookEdit", "Bash", "PowerShell"):
        return
    try:
        chain = chain or _chain_ctx(input_data, config)
        if chain is None:
            return
        cwd = input_data.get("cwd", "") or ""
        paths = _known_write_paths(tool_name, input_data.get("tool_input") or {}, cwd)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[chain-breaker] 改檔前存快照的事實算不出（這次不存）：{type(e).__name__}: {e}\n")
        return
    if paths:
        chain_store.before_write(chain[0], chain[1], paths, input_data, config, cwd=cwd)


def _known_write_paths(tool_name: str, tool_input: Dict[str, Any], cwd: str) -> List[str]:
    """這次工具呼叫算得出的寫入目標（wg_core.write_paths_from_tool；算不出的 UNKNOWN 不列）。改檔前存快照、記閘擋的檔共用。"""
    from wg_core import write_paths_from_tool
    return [p for p in write_paths_from_tool(tool_name, tool_input or {}, cwd) if not p.startswith("UNKNOWN:")]


def _blocked_files(tool_name: str, tool_input: Dict[str, Any], cwd: str, owed: Sequence[str] = ()) -> List[str]:
    """CHAIN_SAME_GATE_PER_OBJECT：每個檔各要一行宣告的閘（動資料檔、改舊測試）擋下時報給斷路器的檔＝這次要寫的檔，加上 owed
    （改舊測試：上一個 Bash 欠著宣告的那幾支，這次任何工具都可能因它們被擋）。多報不少報：寧可多算同一個對象、不可漏算。
    算不出（例外）回空清單＝照舊只看閘名，stderr 說一聲。"""
    try:
        return list(dict.fromkeys([*(str(p) for p in owed if p), *_known_write_paths(tool_name, tool_input, cwd)]))
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[chain-breaker] 算不出這次擋的檔（照閘名計數）：{type(e).__name__}: {e}\n")
        return []


def _hub_part(file_path: str, config: Dict[str, Any]) -> str:
    """CHAIN_SAME_GATE_PER_OBJECT：定位閘因「這個部位欠證據」擋這個檔時報給斷路器的部位鍵——跟定位閘累積證據用的是同一把鍵
    （wg_overview 的 state 鍵：專案根|部位表那一列的部位名；表外的檔＝專案根|(unmapped)頂層目錄）。
    不是欠這個部位證據的擋回空字串＝照閘名計數：設定有錯（整層設定壞了，換哪個部位都一樣擋）、唯讀路徑（禁區）；判定順序跟 on_edit 相同。
    判不出（部位表讀不到、查表例外）也回空字串，不當成表外的檔，stderr 說一聲。"""
    try:
        from wg_overview import _cfg, _is_readonly, _key, _lookup, _unmapped_key, write_target_root
        if _cfg(config)["_errors"]:
            return ""
        hit = _lookup(file_path)
        root = hit[0] if hit else write_target_root(file_path)      # 跟 on_edit 同一支判根（資料夾目標看上一層）
        if root is None:
            return ""
        cfg = _cfg(config, root)
        if cfg["_errors"] or _is_readonly(file_path, root, cfg):
            return ""
        return _key(*hit) if hit else _unmapped_key(root, file_path)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[chain-breaker] 判不出 {file_path} 的部位（照閘名計數）：{type(e).__name__}: {e}\n")
        return ""


def _chain_halt(input_data: Dict[str, Any], config: Dict[str, Any], tool_name: str, tool_input: Dict[str, Any]) -> Optional[str]:
    """連鎖中止中（警報後、使用者還沒選繼續或放行）：讀與問以外的工具先停手 → 回擋訊息（規則 CHAIN_HALT_UNTIL_ANSWER）。
    出錯照原本的閘行為（不停手），stderr 浮一行。"""
    try:
        chain = _chain_ctx(input_data, config)
        if chain is None:
            return None
        readonly = tool_name in ("Bash", "PowerShell") and wg_chain.readonly_shell(tool_name, (tool_input or {}).get("command"))
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[chain-breaker] 停手判斷出錯，照原本的閘行為：{type(e).__name__}: {e}\n")
        return None
    return chain_store.halt(chain[0], chain[1], tool_name, input_data, config, readonly=readonly)


def _need_goal_ask(tool_name: str, input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    """需求目標 4.4（AskUserQuestion／ExitPlanMode 前）：有目標樹就要題目或計畫裡寫節點編號；寫碼類沒寫 deny 並列節點，
    知識類與還沒有樹只補提示（wg_need_goal_points.on_ask）。子代理不跑（裁判子 session 由 dispatcher 分去
    handle_judge_pre_tool_use，到不了這裡）。處理過的提問記進 state["need_goal_asks"]，PostToolBatch 就不再事後處理。
    這支本身炸了 → 照契約擋＋stderr＋守門紀錄 ask_error；只放過【收尾放行確認】而且本 session 真有擋滿待放行紀錄的題目
    （放行題問不出去，收尾就死鎖）。"""
    sid = input_data.get("session_id", "") or ""
    if not sid or input_data.get("agent_id"):
        output_nothing()
        return
    import wg_release
    try:
        import wg_need_goal as _ng
        from wg_need_goal_points import mark_asked, note_ask_blocked, on_ask_full
        from wg_core import write_state
        state, status = read_state_status(sid)
        if not _ng.cfg_for_cwd(config, _ng.hook_cwd(input_data, state)).get("enabled", True):
            output_nothing()
            return
        tool_input = input_data.get("tool_input") or {}
        deny, hint, hits = on_ask_full(sid, tool_name, tool_input, state or {})
        v6 = v6_enabled(config)
        # 規則 GATE_MODE_TABLE：本來要擋的那幾條有任一條照擋（表上 block、或總開關關）才 deny；否則連提示一起改成下一個工具結果附一行
        block = bool(deny) and any(_rr.gate_mode(h["rule"], v6) == _rr.BLOCK for h in hits if h.get("block"))
        remind = v6 and bool(hits) and not block
        if status == "ok" and state is not None:
            mark_asked(state, str(input_data.get("tool_use_id") or ""), tool_input)
            note_ask_blocked(state, deny)     # PostToolBatch 的提問審計看「擋過幾次」（改提醒的也算一次）
            if remind:
                from wg_overview import remind_hit
                for h in hits:
                    _remind_later(input_data, state, remind_hit(h["rule"], "", h["what"], h["fix"]), "need_goal")
            write_state(sid, state)
        elif remind:                              # state 讀不到：只留帳＋stderr（提醒送不出去）
            from wg_overview import remind_hit
            _remind_later(input_data, None, remind_hit(hits[0]["rule"], "", hits[0]["what"], hits[0]["fix"]), "need_goal")
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        state = read_state(sid) or {}
        raw_input = input_data.get("tool_input") or {}
        try:   # 整次全是放行題才放（夾一般題、標記塞進一般題照擋）；判規則的模組也壞了才退回只看標記，免得收尾死鎖
            release_only = _rr.ask_release_only(raw_input, wg_release.RELEASE_TAG,
                                                (wg_release.OPT_RELEASE, wg_release.OPT_KEEP))
        except Exception as rr_err:  # noqa: BLE001
            sys.stderr.write(f"[NeedGoal] 放行題判定也壞了，退回只看標記：{type(rr_err).__name__}: {rr_err}\n")
            release_only = wg_release.RELEASE_TAG in json.dumps(raw_input, ensure_ascii=False)
        release = tool_name == "AskUserQuestion" and release_only and wg_release.pending_any(state, sid)
        sys.stderr.write(f"[NeedGoal] 提問前檢查失敗（{'放行題照放' if release else '擋'}）：{err}\n")
        try:
            from wg_core import append_guard_log
            append_guard_log("need_goal", {"event": "ask_error", "rule": "GATE_SELF_ERROR", "session_id": sid, "tool": tool_name,
                                           "error": err, "released": release})
        except Exception as log_err:  # noqa: BLE001
            sys.stderr.write(f"[NeedGoal] ask_error 守門紀錄寫不進去：{type(log_err).__name__}: {log_err}\n")
        if release:
            output_nothing()
            return
        if _rr.gate_mode("GATE_SELF_ERROR", v6_enabled(config)) == _rr.BLOCK:
            _deny(input_data, config, (f"[NeedGoal] 提問前檢查壞了，判不了這題掛在目標樹哪個節點，一律擋（{err}）。"
                                       "修好 hooks/wg_need_goal*.py 再問；只有【收尾放行確認】而且真有擋滿待放行紀錄的題目照放。"))
            return
        # 規則 GATE_SELF_ERROR：閘自己壞＝判不了 → 不擋，下一個工具結果附一行、stderr 與 ask_error 留帳已在上面
        hit = {"rule": "GATE_SELF_ERROR", "obj": "need_goal_ask", "what": f"提問前檢查壞了，判不了這題掛哪個節點（{err}）",
               "fix": "修好 hooks/wg_need_goal*.py；這題照問", "extra": ""}
        if _remind_later(input_data, state if state.get("session") else None, hit, "need_goal"):
            from wg_core import write_state as _ws_err
            _ws_err(sid, state)
        output_nothing()
        return
    if block:
        _deny(input_data, config, deny)
        return
    if remind:
        output_nothing()                  # 規則 REMIND_ON_PRIOR_RESULT：不掛 PreToolUse 的 additionalContext
        return
    if hint:
        output_json({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                            "additionalContext": _with_cards(input_data, config, hint, "pretool_hint")}})
        return
    output_nothing()


def _pre_v6_hub_warn(input_data: Dict[str, Any], config: Dict[str, Any], tool_name: str, tool_input: Dict[str, Any],
                     sid: str, state: Optional[Dict[str, Any]]) -> Optional[str]:
    """v6 守門關閉時的 OverviewHub（9e476fd0 的行為）：只看 Write／Edit／NotebookEdit、只管有部位表且命中表列的檔，
    當時 dry_run＝只提醒不擋——on_edit 的 deny 一律降成提醒。閘自己炸只 stderr、不擋（當時 fail-open）。"""
    fp = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
    if tool_name not in ("Write", "Edit", "NotebookEdit") or not fp:
        return None
    try:
        from wg_overview import _lookup_quiet, on_edit as _hub_on_edit
        if not _lookup_quiet(fp):
            return None
        hub_state = state if state is not None else {}
        warn, deny, changed = _hub_on_edit(hub_state, sid, fp, input_data.get("transcript_path", "") or "", config)
        if sid and state is not None and changed:
            from wg_core import write_state as _ws
            _ws(sid, state)
        return (deny or warn) and f"{deny or warn}（v6 守門關閉：只提醒不擋）"
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[Guardian:OverviewHub] pre_tool_use 檢查異常（fail-open）：{type(e).__name__}: {e}\n")
        return None


def handle_pre_tool_use(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    v6 = v6_enabled(config)     # 關＝只跑 9e476fd0 就有的閘（dispatcher 已擋掉 v6 才掛的工具）

    # 規則 READ_FAST_PATH：Read 的 PostToolUse 只落 read-log；要讀檔證據的閘（OverviewHub、動資料檔、無表專案、提問前讀過部位檔）
    # 之前先把累積的 Read 補帳（沒累積只多一次 stat）
    if v6 and wg_read_fast.pending(str(input_data.get("session_id") or "")):
        from handlers.post_tool_use import replay_reads_before_tool
        replay_reads_before_tool(input_data, config)

    # 連鎖斷路器：警報後、使用者選繼續或放行之前，讀與問以外的工具先停手（不是閘觸發、不進次數）
    _halt = _chain_halt(input_data, config, tool_name, tool_input) if v6 else None
    if _halt:
        output_json({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                            "permissionDecisionReason": _halt}})
        return

    # 需求目標 4.4：問使用者之前（settings.json PreToolUse matcher 掛了這兩個工具才會走到這裡；沒掛時由 PostToolBatch 事後提醒）
    if tool_name in ("AskUserQuestion", "ExitPlanMode"):
        _need_goal_ask(tool_name, input_data, config)
        return

    # G9：MCP 進程沒有 session 身份，second_opinion_start 由這裡補上 hook 輸入的 session_id（updatedInput），pack 才找得到
    # 這個 session 的需求目標樹（goal.md）與驗證帳本。settings.json PreToolUse matcher 要掛這個工具才會走到這裡。
    if tool_name.endswith("__second_opinion_start"):
        sid = str(input_data.get("session_id") or "")
        if sid:
            try:       # REVIEW_FIX_RERUN_TOUCHED_ONLY：材料在這一刻打包，之後的改動算審完的修補（只重跑碰到的 verify）
                import wg_need_goal as _ng
                _ng.mark_review(sid)
            except Exception as e:  # noqa: BLE001
                print(f"[Guardian:SecondOpinion] 記不下審查時刻（之後的修補照舊要全部重跑）：{type(e).__name__}: {e}", file=sys.stderr)
        if sid and isinstance(tool_input, dict) and tool_input.get("session_id") != sid:
            output_json({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                "updatedInput": {**tool_input, "session_id": sid}}})
            return
        output_nothing()
        return

    # 改判準卡：MCP 改卡的三個工具（settings.json PreToolUse matcher 掛了才會走到這裡）只過改判準卡閘
    if tool_name.endswith(wg_judge_card.MCP_TOOLS):
        deny_reason = wg_judge_card.gate(tool_name, tool_input, input_data, config)
        if deny_reason:
            _deny(input_data, config, deny_reason)
            return
        output_nothing()
        return

    # ─── Sub-agent 記憶注入 ────────────────────────────────────
    # sub-agent（Agent/Task）開全新 context、不觸發 UserPromptSubmit，吃不到 atom。
    # 唯一 parent→child 通道是工具 prompt 字串 → 經 PreToolUse updatedInput prepend
    # 緊湊記憶 blob。fail-open：任何錯誤都不擋 spawn。
    if tool_name in ("Agent", "Task"):
        try:
            # 惰性 import：wg_atoms 全額 import 成本高，只在 Agent/Task spawn 才付
            from wg_atoms import build_injection_blob

            orig_prompt = tool_input.get("prompt", "") or ""
            # fork 子代理（CC 2.1.232 起）繼承父對話與 prompt cache：父對話已注入的 atom 它看得到，
            # 只補父 context 沒有的。一般子代理開全新 context、不繼承 → already_injected 不能套。
            subagent_type = str(tool_input.get("subagent_type") or "")
            already: List[str] = []
            if subagent_type == "fork":
                sid = input_data.get("session_id", "") or ""
                state = read_state(sid) if sid else None
                already = list((state or {}).get("injected_atoms") or [])
            blob, injected = build_injection_blob(
                orig_prompt, budget=_SUBAGENT_INJECT_BUDGET, already_injected=already,
            )
            if not (blob and injected):
                blob = ""
            # 切入點契約（TECH §7.10）：開工句認得出登錄表 subagent_prompt 路的切入點，判準卡接在記憶 blob 後面
            from handlers._shared import entry_note
            note = entry_note(orig_prompt, "subagent_prompt", session_id=str(input_data.get("session_id") or ""),
                              config=config) if v6 else ""
            if blob or note:
                new_input = dict(tool_input)
                new_input["prompt"] = "\n\n".join(p for p in (blob, note, orig_prompt) if p)
                _atom_debug_log(
                    "SubagentInject",
                    f"tool={tool_name} type={subagent_type or '-'} injected={injected} "
                    f"parent_already={len(already)} "
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
    _hook_lap("前置提示")

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
    _hook_lap("跨 session 衝突")

    deny_reason = _check_memory_atom_format(tool_name, tool_input)
    if deny_reason:
        _deny(input_data, config, deny_reason)
        return

    deny_reason = check_memory_path_block(tool_name, tool_input)
    if deny_reason:
        _deny(input_data, config, deny_reason)
        return

    # 根層敏感檔 + Bash 全域 MCP 變更：
    # 外部專案 session 寫核心層 / 全域 MCP add/remove → deny
    _cwd = input_data.get("cwd", "") or ""
    deny_reason = (
        check_cross_realm_write(tool_name, tool_input, _cwd, config)
        or check_cross_realm_bash(tool_name, tool_input, _cwd, config, str(input_data.get("session_id") or ""))
        or check_cross_realm_mcp_cmd(tool_name, tool_input, _cwd, config)
    )
    if deny_reason:
        _deny(input_data, config, deny_reason)
        return

    # ── DataFileAsk（T2.16 動使用者資料檔要先宣告）──
    # 使用者既有、非程式、非本 session 建、原話沒點名的資料檔／設定檔，沒有「動資料檔｜<路徑>：<為什麼>」就擋（wg_data_file）
    deny_reason = v6 and wg_data_file.gate(tool_name, tool_input, input_data, config)
    if deny_reason:
        _deny(input_data, config, deny_reason, watched=_blocked_files(tool_name, tool_input, _cwd))
        return

    # ── JudgeCardDeclare（改判準卡留帳）── 綁了 Entry 的卡有沒有「改判準卡｜哪張：理由」都放行、記帳（wg_judge_card）
    deny_reason = v6 and wg_judge_card.gate(tool_name, tool_input, input_data, config)
    if deny_reason:
        _deny(input_data, config, deny_reason)
        return

    # state 這裡讀一次（動資料檔閘自己讀寫過之後）：svn 測試路徑閘、改舊測試閘與後面的口令閘、繞閘閘、OverviewHub 共用同一份
    # （改舊測試閘就地改、有改自己寫回）
    _co_sid = input_data.get("session_id", "") or ""
    _co_state, _co_status = read_state_status(_co_sid) if _co_sid else (None, "missing")

    deny_reason = check_svn_test_block(tool_name, tool_input, _cwd, config, _co_state, _co_sid)
    if deny_reason:
        _deny(input_data, config, deny_reason)
        return
    _hook_lap("寫入閘")

    # ── OldTestDeclare（改舊測試要先宣告）──
    # 動到既有測試（消失、改名、斷言變了、加 skip）沒有「改舊測試｜哪支：理由」就擋；閘自己炸＝判不了，不擋（stderr＋留帳 error，規則 GATE_SELF_ERROR）
    # 閘會就地改 state（補了宣告的欠帳拿掉）：擋下時報給斷路器的檔要含呼叫前還欠著的那幾支
    _ot_pending = _co_state.get(wg_oldtest.PENDING_KEY) if isinstance(_co_state, dict) else None
    _ot_owed = [str(e.get("file") or "") for e in _ot_pending if isinstance(e, dict)] if isinstance(_ot_pending, list) else []
    try:
        deny_reason = v6 and wg_oldtest.gate(tool_name, tool_input, input_data, config, _cwd, _co_state)
    except Exception as e:
        deny_reason = None
        err = f"{type(e).__name__}: {e}"
        sys.stderr.write(f"[Guardian:OldTestDeclare] 改舊測試閘內部錯誤，判不了有沒有動到既有測試（這次不擋，已留帳）：{err}\n")
        append_guard_log("old_test", {"event": "error", "rule": "GATE_SELF_ERROR", "session": _co_sid, "tool": tool_name, "error": err})
    if deny_reason:
        _deny(input_data, config, deny_reason, watched=_blocked_files(tool_name, tool_input, _cwd, _ot_owed))
        return
    _hook_lap("舊測試閘")

    # 索引三檔合併驅動閘（advisory-only）——必須在隱私閘之前：resolver 會 git add 索引檔，
    # 隱私檢查要看到它 stage 完的 index。之後 privacy 仍可能 deny；已 stage 的索引檔
    # 是冪等的無害合併結果（下次同指令直接放行），不需回滾。訊息同步落 stderr：
    # 後面若 deny，stdout 只能給 deny JSON，advisory 不能就此無聲消失。
    merge_warn = check_merge_driver(tool_name, tool_input, _cwd, config)
    if merge_warn:
        try:
            sys.stderr.write(merge_warn + "\n")
        except OSError:
            pass

    # svn add 中文路徑提醒（advisory-only；同樣先落 stderr，後面 deny 時不消失）
    svn_enc_warn = check_svn_encoding(tool_name, tool_input)
    if svn_enc_warn:
        try:
            sys.stderr.write(svn_enc_warn + "\n")
        except OSError:
            pass

    # git commit 口令閘（本回合使用者原話無版控口令 → deny；fail-open）
    deny_reason = check_git_commit_order(tool_name, tool_input, config, _co_state, _cwd, _co_sid)
    if deny_reason:
        _deny(input_data, config, deny_reason)
        return

    # 驗證批次閘（整組驗證要使用者口令；同一組指令同一批改動只驗一次 → deny；不歸 v6 管；判定在 hooks/wg_verify_batch.py，fail-open）
    if tool_name in ("Bash", "PowerShell"):
        import wg_verify_batch
        deny_reason = wg_verify_batch.check(tool_name, tool_input, config, _co_state, _cwd, _co_sid,
                                            agent_id=str(input_data.get("agent_id") or ""), call=input_data)
        if deny_reason:
            _deny(input_data, config, deny_reason)
            return

    # git commit 隱私硬閘（staged 含隱私檔 → deny；fail-open）
    deny_reason = check_git_privacy(tool_name, tool_input, _cwd, config)
    if deny_reason:
        _deny(input_data, config, deny_reason)
        return

    # commit 前病形閘（新寫進的病 → deny；舊碼原本就有的只列出，跟其他提醒一起送）
    deny_reason, smell_warn = check_smell_gate(tool_name, tool_input, _cwd, config) if v6 else (None, None)
    if deny_reason:
        wg_gate_bypass.note_smell_deny(_co_state, _co_sid, _cwd, deny_reason, tool_name, tool_input, input_data.get("transcript_path", "") or "", config)
        _deny(input_data, config, deny_reason)
        return

    # ── GateBypass（T2.19 繞閘嫌疑）──
    # 這個 session 被病形閘擋過之後，unstage／改提交範圍／--no-verify 讓同一批內容過關 → 要宣告「不是繞閘｜理由」，沒宣告就擋；
    # 事實與判定在 hooks/wg_gate_bypass.py
    deny_reason = v6 and wg_gate_bypass.check(tool_name, tool_input, _cwd, config, _co_state, _co_sid,
                                              input_data.get("transcript_path", "") or "",
                                              agent_id=str(input_data.get("agent_id") or ""),
                                              tool_use_id=str(input_data.get("tool_use_id") or ""))
    if deny_reason:
        _deny(input_data, config, deny_reason)
        return

    # 需求目標（4.5）：commit 指令執行前，改了程式還沒回頭對照 (f1)、目前寫碼類樹的完整對照 (f2)、改到的部位沒掛目標 (f3)
    # 缺了就擋；核對本身出錯不擋（stderr＋留帳 commit_gate_error，規則 GATE_SELF_ERROR）。是不是 commit 與 CommitOrder 同一支判定（heredoc 本文裡的 commit 範例不算）
    if v6 and tool_name in ("Bash", "PowerShell"):
        _ng_cmd = tool_input.get("command", "") or ""
        if (_git_commits_to_run(_ng_cmd, input_data.get("cwd", "") or "", _tool_shell(tool_name))[2]
                or _svn_segments(_strip_heredoc_bodies(_ng_cmd), {"commit", "ci"})):
            try:
                from wg_need_goal import commit_gate
                deny_reason = commit_gate(_co_sid, config, _co_state, input_data.get("transcript_path", "") or "")
            except Exception as e:
                deny_reason = None
                err = f"{type(e).__name__}: {e}"
                sys.stderr.write(f"[NeedGoal] commit 前核對需求目標時出錯（這次不擋，已留帳）：{err}\n")
                append_guard_log("need_goal", {"event": "commit_gate_error", "rule": "GATE_SELF_ERROR", "session_id": _co_sid,
                                               "tool": tool_name, "command": _ng_cmd[:300], "error": err})
            if deny_reason and _rr.gate_mode("COMMIT_GOAL_RECONCILED", v6) == _rr.BLOCK:
                _deny(input_data, config, deny_reason)
                return
            if deny_reason:
                # 規則 COMMIT_GOAL_RECONCILED（remind）：commit 照跑，那則 Bash 的工具結果附一行；每棵樹一次
                try:
                    from wg_need_goal import load as _ng_load
                    _tree = str(_ng_load(_co_sid).get("active") or "")
                except Exception:  # noqa: BLE001
                    _tree = ""
                from wg_overview import remind_hit
                _what = " ".join(ln.strip() for ln in deny_reason.splitlines()[1:3] if ln.strip()) or deny_reason.splitlines()[0]
                if _remind_later(input_data, _co_state, remind_hit("COMMIT_GOAL_RECONCILED", _tree, f"commit 前的目標對照沒過：{_what}",
                                                                   "改到的部位補定位第四行（目標對照由程式代填，不必呼叫 reconcile）"),
                                 "need_goal", command=_ng_cmd[:300]):
                    from wg_core import write_state as _ws_cg
                    _ws_cg(_co_sid, _co_state)

    # OverviewHub：改某部位的檔前要先看過導讀卡、讀過部位檔、交定位三行，條件不足照 RULE_MODE 擋或提醒（規則 GATE_MODE_TABLE）。
    # 五工具：Write／Edit／NotebookEdit 取 file_path；Bash／PowerShell 取指令裡每個寫入目標，逐目標 on_edit。
    # state：沒有 state 檔（SessionStart 被跳過）就 _ensure_state 建一份再用，注入紀錄才落得了盤；
    # 檔在但讀不到（鎖住／JSON 壞）不建 fallback 覆蓋，本次用空 state 判（仍會擋，只是不落盤）。
    hub_warn = None if v6 else _pre_v6_hub_warn(input_data, config, tool_name, tool_input, _co_sid, _co_state)
    if v6 and tool_name in ("Write", "Edit", "NotebookEdit", "Bash", "PowerShell"):
        hub_deny, hub_file = None, ""          # hub_file＝定位閘自己擋下的那個檔（報部位給斷路器）；目標樹、state、環境的擋不報
        _hub_state = _co_state
        try:
            from wg_core import (_ensure_state as _hub_ensure_state, write_paths_from_tool, write_sources_from_tool,
                                 write_state as _ws)
            from wg_overview import edit_check as _hub_edit_check, remind_hit as _remind_hit
            from wg_need_goal import TEXT_SET_FORMAT as _ng_fmt, edit_gate as _ng_edit_gate, set_via_text as _ng_set_via_text
            _hub_targets = write_paths_from_tool(tool_name, tool_input, _cwd)
            if _hub_targets:
                # 需求目標判「是不是改程式」另看 cp／mv 的來源與 Write 要寫的內容（目的地還不存在、新建的腳本沒副檔名）
                _ng_sources = write_sources_from_tool(tool_name, tool_input, _cwd)
                _ng_content = tool_input.get("content") if tool_name == "Write" else None
                _hub_state = _co_state
                if _hub_state is None and _co_sid and _co_status == "missing":
                    _hub_state = _hub_ensure_state(_co_sid, input_data, config)
                _hub_persist = _hub_state is not None and bool(_co_sid)
                if _hub_state is None:
                    _hub_state = {}
                _hub_warns: List[str] = []
                hub_changed = False
                _once = False
                for _hub_fp in _hub_targets:
                    # 需求目標第一層（4.2）：寫碼類檔沒有目標樹，在 OverviewHub 任何判斷之前（OverviewHub 關掉、沒專案根、表外都照查）；
                    # 送法照 RULE_MODE（CODE_EDIT_NEEDS_GOAL_TREE 提醒；目標檔損毀／判定出錯＝GATE_SELF_ERROR）。
                    # 先看 transcript 本回合有沒有「目標｜」行（規則 TREE_SET_VIA_TEXT）：有就照它立樹，不必多一個 need_goal 工具回合
                    _ng_line, _ng_changed = _ng_set_via_text(
                        _co_sid, _hub_state, _hub_fp, config, input_data.get("transcript_path", "") or "",
                        str(input_data.get("agent_id") or ""), _cwd, _ng_sources.get(_hub_fp, ()), _ng_content)
                    hub_changed = hub_changed or _ng_changed
                    if _ng_line:
                        _hub_warns.append(_ng_line)
                    _ng_deny = _ng_edit_gate(_co_sid, _hub_fp, config, _ng_sources.get(_hub_fp, ()), _ng_content)
                    if _ng_deny:
                        _ng_rule = "GATE_SELF_ERROR" if ("目標檔損毀" in _ng_deny or "時出錯" in _ng_deny) else "CODE_EDIT_NEEDS_GOAL_TREE"
                        if _rr.gate_mode(_ng_rule, v6) == _rr.BLOCK:
                            hub_deny = _ng_deny
                            break
                        _ng_hit = (_remind_hit(_ng_rule, "need_goal_edit", _ng_deny.splitlines()[0], "need_goal(action=set, goal=…) 重寫樹")
                                   if _ng_rule == "GATE_SELF_ERROR" else
                                   _remind_hit(_ng_rule, "", "改程式檔前這個需求還沒有目標樹",
                                               f"寫一行「{_ng_fmt}」（子目標每件一行「子目標｜…」），{_rr.DECL_WHERE_SHORT}，hook 照它立樹；"
                                               "備援 need_goal(action=set, goal=…)"))
                        hub_changed = _remind_later(input_data, _hub_state, _ng_hit, "need_goal", path=_hub_fp) or hub_changed
                    _w, _d, _c, _hit = _hub_edit_check(
                        _hub_state, _co_sid, _hub_fp, input_data.get("transcript_path", "") or "", config,
                        agent_id=str(input_data.get("agent_id") or ""), tool_use_id=str(input_data.get("tool_use_id") or ""),
                    )
                    hub_changed = hub_changed or _c
                    if _w and not _d:              # 有 deny 理由時警告文字就是擋訊息本身，不當警告送
                        _hub_warns.append(_w)
                    _once = bool(_d and _hit and _hit.get("block_once"))   # 規則 LOCATE_FIRST_EDIT_BLOCKS_ONCE：第一次改、缺定位，擋這一次
                    if _d and (_hit is None or _rr.gate_mode(_hit["rule"], v6) == _rr.BLOCK):
                        hub_deny, hub_file = _d, _hub_fp
                        break
                    if _hit:
                        # 規則 GATE_MODE_TABLE：定位閘、導讀卡、無表專案、設定壞 → 不擋，下一個工具結果附一行（導讀卡順帶注入）；
                        # 第一次改就交了定位（_d 空）卡也走這裡當提醒件送
                        hub_changed = _remind_later(input_data, _hub_state, _hit, "overview_hub", path=_hub_fp) or hub_changed
                    if _once and _hub_persist:
                        # 卡已排進提醒（隨下一個工具結果到），這一次照擋、訊息＝卡＋定位要求；state 記不住「擋過了」（沒 session）就只提醒
                        hub_deny, hub_file = _d, _hub_fp
                        break
                if _hub_persist and hub_changed:   # 放行也要落盤（located／edits／part_files_read）
                    _ws(_co_sid, _hub_state)
                    # write_state 失敗只吞 OSError 不回報：回讀磁碟核對，寫不進去就擋（否則下一次 Edit 又被當第一次）
                    _cid = (_hub_state.get("session") or {}).get("id") or _co_sid
                    _disk, _dst = read_state_status(_cid)
                    if _dst != "ok" or (_disk or {}).get("overview_hub") != _hub_state.get("overview_hub"):
                        hub_file = ""
                        _persist_msg = (f"[Guardian:OverviewHub] state 無法持久化（{_dst}；workflow/state-{_cid[:8]}….json）："
                                        f"注入與定位紀錄寫不進 state 檔，閘無法累積證據。修好 workflow/ 目錄的寫入再改。")
                        from wg_overview import _log as _hub_log
                        if _rr.gate_mode("GATE_SELF_ERROR", v6) == _rr.BLOCK:
                            hub_deny = _persist_msg.replace("閘無法累積證據。", "閘無法累積證據，一律擋。")
                            _hub_log("state_persist_failed", _co_sid, tool=tool_name, status=_dst, deny_reason="state_unpersisted")
                        else:
                            # 規則 GATE_SELF_ERROR（remind）：state 寫不進去，待提醒也存不住 → 這一行只能跟著這次放行的警告走、stderr＋留帳
                            _hub_log("state_persist_failed", _co_sid, tool=tool_name, status=_dst, rule="GATE_SELF_ERROR", allowed=True)
                            if hub_deny and _once:                        # 「只擋第一次」的擋要靠 state 記住；記不住就放行（否則每次 Edit 都被當第一次）
                                hub_deny = None
                            sys.stderr.write(_persist_msg + "\n")
                            _hub_warns.append(_rr.remind_line("GATE_SELF_ERROR", f"state 無法持久化（{_dst}），閘判不了",
                                                              "修好 workflow/ 目錄的寫入"))
                hub_warn = "\n".join(_hub_warns) or None
        except Exception as e:
            # 閘自己炸（state 檔鎖住、import 壞、解析例外）＝判不了：送法照 RULE_MODE（GATE_SELF_ERROR：v6 開提醒、關照擋）；traceback 進 stderr 與 hub log
            hub_file = ""
            err = f"{type(e).__name__}: {e}"
            if _rr.gate_mode("GATE_SELF_ERROR", v6) == _rr.BLOCK:
                hub_deny = (f"[Guardian:OverviewHub] 閘環境異常，無法判定，一律擋：{err}。"
                            f"修好環境（state 檔／hook 依賴）再改；先用 Read 查原因。")
                try:
                    sys.stderr.write(f"[Guardian:OverviewHub] pre_tool_use 閘內部錯誤（已 deny）：{err}\n")
                    from wg_overview import _log as _hub_log
                    _hub_log("gate_error", _co_sid, tool=tool_name, error=err, deny_reason="gate_error")
                except Exception:
                    pass
            else:
                try:
                    sys.stderr.write(f"[Guardian:OverviewHub] pre_tool_use 閘內部錯誤，判不了（這次不擋，已留帳）：{err}\n")
                    from wg_overview import _log as _hub_log, remind_hit as _remind_hit
                    _hub_log("gate_error", _co_sid, tool=tool_name, error=err, rule="GATE_SELF_ERROR", allowed=True)
                    if _hub_state is None and _co_sid and _co_status == "missing":
                        from wg_core import _ensure_state as _hub_ensure_state2
                        _hub_state = _hub_ensure_state2(_co_sid, input_data, config)
                    if _remind_later(input_data, _hub_state, _remind_hit("GATE_SELF_ERROR", "overview_hub", f"OverviewHub 閘內部錯誤，判不了：{err}",
                                                                        "修好環境（state 檔／hook 依賴）；先用 Read 查原因"), "overview_hub"):
                        from wg_core import write_state as _ws_err
                        _ws_err(_co_sid, _hub_state)
                except Exception as e2:  # noqa: BLE001
                    sys.stderr.write(f"[Guardian:OverviewHub] 閘內部錯誤的留帳也失敗：{type(e2).__name__}: {e2}\n")
        if hub_deny:
            part = _hub_part(hub_file, config) if hub_file else ""   # 說不出部位就連檔也不報：同部位換個檔不能算成別的對象
            _deny(input_data, config, hub_deny, watched=[hub_file] if part else (), target=part)
            return

    # 放行：連鎖段開著就先存要改的檔的快照（連鎖斷路器選「還原」時用）
    if v6:
        _chain_before_write(input_data, config)

    # 無 deny 才輸出警告（stdout 恆單一 JSON；不帶 permissionDecision——
    # "allow" 會自動核准繞過權限系統，advisory 不得改變放行行為）
    warn_msgs = [m for m in (coord_warn, merge_warn, svn_enc_warn, smell_warn, hub_warn) if m]
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
                "additionalContext": _with_cards(input_data, config, combined, "pretool_hint"),   # 判準卡只給模型
            },
        })
        return

    output_nothing()
