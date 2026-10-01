"""Plan Mode Bash 彈窗攔截閘（PreToolUse / Bash）。

做什麼：只在 permission_mode == "plan" 時動作。遇到「CC 一定會彈權限視窗、而且 allow
規則壓不過」的 Bash 寫法，直接 deny 並告訴模型改用哪種寫法；其餘不表態，交回 CC 原生判定。

為什麼要有（拆 claude.exe 與 debug log 實證）：
1. CC 原生唯讀判定只認 `sed -n 'N,Mp'`；正則位址（`/## x/,$p`）一律當成寫入。路徑含
   `.claude` 片段又被列為敏感檔 → 走「safety check」→ allow 規則與 hook 的 allow 都壓不過
   （debug log：Hook returned 'allow' for Bash, but ask rule/safety check requires full
   permission pipeline）。按「不再詢問」只會把整條指令寫成一條無用的精準規則塞進 settings.json。
2. `cd /c/...`（MSYS 絕對路徑）在 Windows 被判「工作目錄外」，同屬 safety check。
所以唯一不彈窗的路徑是：讓模型一開始就不要這樣寫 → deny + 提示。

怎麼跑：由 settings.json 的 PreToolUse(matcher=Bash) 呼叫，stdin 收 hook JSON。
手測：echo '{"permission_mode":"plan","tool_name":"Bash","tool_input":{"command":"sed -n \\"/a/,$p\\" x"}}' | python plan_bash_guard.py
"""
import json
import re
import shlex
import sys

WRITE_CMDS = {"rm", "mv", "cp", "touch", "mkdir", "chmod", "chown", "tee"}
# 下面兩條鏡射 CC 2.1.286 內建的 sed 唯讀判定（OXe）：旗標只准這些、腳本只准 p / Np / N,Mp；-e、正則位址、$ 都不算唯讀
SED_FLAGS_OK = {"-n", "--quiet", "--silent", "-E", "--regexp-extended", "-r", "-z", "--zero-terminated", "--posix"}
SED_PRINT_SCRIPT = re.compile(r"^(?:\d+|\d+,\d+)?p$")

HINT_CD = ("Plan Mode：不要 cd（MSYS 絕對路徑會被 CC 判為工作目錄外而彈窗，allow 規則壓不過）。"
           "直接在指令裡寫絕對路徑，或改用 Read/Grep/Glob 工具。")
HINT_SED = ("Plan Mode：CC 只把 `sed -n 'N,Mp'` 當唯讀，正則位址／替換一律視為寫入；"
            "路徑含 .claude 又屬敏感檔，必彈窗且 allow 規則壓不過。查讀請改用 Read（含 offset/limit）或 Grep 工具。")
HINT_WRITE = "Plan Mode 禁止寫入檔案（rm/mv/cp/touch/mkdir/chmod/重導向）；要改檔請先 ExitPlanMode。"


def split_segments(cmd: str):
    """依未加引號的 ; | & 與換行切子段；引號內不切。"""
    segs, buf, quote, i = [], [], None, 0
    while i < len(cmd):
        c = cmd[i]
        if quote:
            buf.append(c)
            if c == "\\" and quote == '"' and i + 1 < len(cmd):
                buf.append(cmd[i + 1]); i += 1
            elif c == quote:
                quote = None
        elif c in "'\"":
            quote = c; buf.append(c)
        elif c in ";|&\n":
            segs.append("".join(buf)); buf = []
        else:
            buf.append(c)
        i += 1
    segs.append("".join(buf))
    return [s.strip() for s in segs if s.strip()]


def has_unquoted(cmd: str, chars: str) -> bool:
    quote = None
    for i, c in enumerate(cmd):
        if quote:
            if c == quote and cmd[i - 1] != "\\":
                quote = None
        elif c in "'\"":
            quote = c
        elif c in chars:
            return True
    return False


def sed_is_print_only(tokens) -> bool:
    args = tokens[1:]
    flags = [a for a in args if a.startswith("-") and a != "--"]
    rest = [a for a in args if not (a.startswith("-") and a != "--")]
    for f in flags:
        if f.startswith("--") or len(f) <= 2:
            if f not in SED_FLAGS_OK: return False
        elif not all(f"-{ch}" in SED_FLAGS_OK for ch in f[1:]):
            return False
    has_n = any(f in ("-n", "--quiet", "--silent") or (not f.startswith("--") and "n" in f[1:]) for f in flags)
    if not has_n or not rest:
        return False
    return all(SED_PRINT_SCRIPT.match(part.strip()) for part in rest[0].split(";"))


def touches_claude_dir(tokens, cwd: str) -> bool:
    """任一引數路徑（相對者先接上 cwd）含 .claude 片段即算。"""
    for t in tokens[1:]:
        if t.startswith("-"):
            continue
        path = t if (t.startswith("/") or re.match(r"^[A-Za-z]:[/\\]", t) or t.startswith("~")) else f"{cwd}/{t}"
        if ".claude" in re.split(r"[/\\]", path):
            return True
    return False


def judge(cmd: str, cwd: str):
    """回傳 deny 提示字串；不需攔就回 None。"""
    if has_unquoted(cmd, ">"):
        return HINT_WRITE
    for seg in split_segments(cmd):
        try:
            tokens = shlex.split(seg, posix=True)
        except ValueError:
            continue
        if not tokens:
            continue
        name = tokens[0].rsplit("/", 1)[-1]
        if name == "cd":
            return HINT_CD
        if name == "sed" and not sed_is_print_only(tokens) and touches_claude_dir(tokens, cwd):
            return HINT_SED
        if name in WRITE_CMDS:
            return HINT_WRITE
    return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("permission_mode") != "plan" or data.get("tool_name") != "Bash":
        return
    cmd = (data.get("tool_input") or {}).get("command") or ""
    hint = judge(cmd, data.get("cwd") or "")
    if not hint:
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"[plan_bash_guard] {hint}",
        }
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
