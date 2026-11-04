#!/usr/bin/env python3
"""console-spawn.py：總控台替工作軌開 session 並送開工句（原話 G16：派工全程不用人貼 prompt）。

做什麼（照順序，哪一步不過就停在那步、印開工句退回人貼）：
  1. 前置：開工句檔存在且不是空的；--repo 是 git 主檢出（<repo>/.git 是目錄，連結的 worktree 不行）；kill switch 檔
     <repo>/workflow/console-spawn.STOP 不存在；由本腳本起、還活著的 session 未達上限（skills/console/spawn.json 的 max_parallel，預設 5）。
     「本腳本起過哪些」記在 <repo>/workflow/state-console-spawn.json：讀寫都拿 <檔>.lock 鎖，改動是鎖內重讀再套一筆、
     暫存檔換上，好幾支同時跑也不丟列；檔壞了 → 原因印 stderr、不起（數不出活著的就不放行）；起好後沒記上 → 印出來。
  2. 起 session（--method bg，預設）：
     `claude.exe --bg --name <軌名> --worktree <軌名> --permission-mode <模式> [--settings <檔>] [--model <id>] "<開工句>"`，
     cwd＝主檢出，subprocess 不經 shell（開工句以 / 開頭也原樣送到）。名字就是軌名（SendMessage 的地址，不會因重開而變）。
     worktree 由 Claude Code 原生建：<repo>/.claude/worktrees/<軌名>/、分支 worktree-<軌名>，從哪裡分出看使用者設定
     worktree.baseRef（"head"＝本機 HEAD，含還沒推的 commit）；同名 worktree 已在就直接沿用；信任只查啟動目錄（主檢出），
     主檢出沒信任過 → claude 回 Workspace not trusted、本腳本 FAIL、印原文與「在主檢出開終端機跑一次 claude 接受信任」
     （實測 2.1.317：~/.claude.json 裡只有反斜線形的鍵是 true、正斜線形是 false 時，`claude --bg` 判不信任）。隔離、上鎖、清理也都是原生的。
     stdout 的 `backgrounded · <短 id> · <名字>` 取短 id。
     模型：--model 優先，其次 spawn.json 的 default_model，都沒有就不帶（吃 Claude Code 預設），不猜。
     設定檔：--settings 有給才帶（轉成絕對路徑原樣交給 claude 的 --settings，例：關掉守門的設定檔）；檔不存在 → 前置就 FAIL、不起。
  3. 等它報到：輪詢 `claude agents --json` 用短 id 找到它；讀它的 transcript
     （<資料根>/projects/<cwd-slug>/<sessionId>.jsonl，cwd 是它的 worktree）看有沒有「<軌名> 收到開工」——SendMessage 工具呼叫的正文，
     或 assistant 的文字都認，印出是哪一種。報到後印「模型＝<transcript 最近一則真回應的 message.model>」；
     指定了模型卻對不上（或讀不到）→ FAIL 印「指定＝…／實際＝…」，session 不殺。
     transcript 出現 API 錯誤訊息（例：模型 id 不存在，claude 不拒起、第一回合回錯後停著等輸入）→ 不等逾時、立刻 FAIL 印原文。
     這兩種 FAIL 不退人貼（人貼救不了），只印 stop 指令讓總控台決定。
  4. 逾時（--timeout，預設 90 秒）→ exit 1，印開工句 code block 與「退回人貼」，session 不殺（印 stop 指令讓總控台決定）。
  --method print：同步跑 `claude -p --name <軌名> --worktree <軌名> …`（阻塞到那個 session 結束），備援用；
  --method gui：本腳本不動畫面，直接印開工句退回。

怎麼跑：
  python ~/.claude/skills/console/scripts/console-spawn.py --track track-x --repo C:\\Projects\\x \\
      --prompt-file C:\\...\\kickoff.txt --permission-mode bypassPermissions --model claude-opus-5-5
  完整參數以 --help 為準。尾行 `CONSOLE_SPAWN_CHECK PASS` 或 `CONSOLE_SPAWN_CHECK FAIL`；exit 0／1 對應。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

CODE_DIR = Path(__file__).resolve().parents[3]   # skills/console/scripts/ → 程式碼根
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
from lib.project_root import claude_data_dir  # noqa: E402

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
KILL_SWITCH = "console-spawn.STOP"
STATE_FILE = "state-console-spawn.json"          # workflow/state-*.json 已在 .gitignore
DEFAULTS = {"max_parallel": 5, "timeout_sec": 90, "poll_sec": 3}
SPAWN_CONFIG = Path(__file__).resolve().parents[1] / "spawn.json"   # 跟著 skill 版控的設定（鍵同 DEFAULTS＋default_model）
BG_ID_RE = re.compile(r"backgrounded\s*[·•:]\s*([0-9a-f]{6,})", re.I)
KICKOFF_WORD = "收到開工"
SYNTHETIC_MODEL = "<synthetic>"                  # Claude Code 自己補寫的 assistant（API 錯誤、No response requested）
NO_MODEL = "讀不到（transcript 沒有 model 欄）"
STATE_LOCK_WAIT_SEC = 10.0                       # 別支 console-spawn 拿著 state 鎖只會幾毫秒；等這麼久還拿不到就當卡住的殘鎖


# ─── 純函式：路徑與判定 ───────────────────────────────────────────────────────
def native_worktree(repo: Path, track: str) -> Path:
    """`claude --worktree <軌名>` 預設建的位置（官方：<repo>/.claude/worktrees/<名>/）；只用來記帳與找 transcript。"""
    return repo / ".claude" / "worktrees" / track


def cwd_slug(cwd: Path) -> str:
    """Claude Code 的 projects/ 子目錄名：路徑裡非字母數字全換成 -（實測 C:\\Users\\x\\.claude-wt\\y → C--Users-x--claude-wt-y）。"""
    return re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


def transcript_path(data_dir: Path, cwd: Path, session_id: str) -> Optional[Path]:
    direct = data_dir / "projects" / cwd_slug(cwd) / f"{session_id}.jsonl"
    if direct.is_file():
        return direct
    hits = glob.glob(str(data_dir / "projects" / "*" / f"{session_id}.jsonl"))
    return Path(hits[0]) if hits else None


def kickoff_received(transcript: Path, track: str) -> Optional[str]:
    """transcript 裡 assistant 說過「<軌名> 收到開工」沒有：SendMessage 工具呼叫的正文 → "SendMessage"；
    assistant 文字 → "文字"；都沒有 → None。"""
    hit_text = None
    with transcript.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "assistant":
                continue
            content = (rec.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("name") == "SendMessage":
                    msg = str((block.get("input") or {}).get("message", ""))
                    if KICKOFF_WORD in msg and track in msg:
                        return "SendMessage"
                elif block.get("type") == "text" and hit_text is None:
                    txt = str(block.get("text", ""))
                    if KICKOFF_WORD in txt and track in txt:
                        hit_text = "文字"
    return hit_text


def model_and_api_error(transcript: Path) -> Tuple[Optional[str], Optional[str]]:
    """(最近一則真回應的 message.model, 最近一則 API 錯誤訊息的文字)；model 跳過 "<synthetic>"，沒有就回 None。"""
    model = err = None
    with transcript.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message") or {}
            if rec.get("isApiErrorMessage") is True:
                content = msg.get("content") if isinstance(msg.get("content"), list) else []
                texts = [str(b["text"]) for b in content if isinstance(b, dict) and b.get("text")]
                err = " ".join(texts) or "（API 錯誤，沒有文字）"
            m = msg.get("model")
            if isinstance(m, str) and m and m != SYNTHETIC_MODEL:
                model = m
    return model, err


def build_cmd(claude_bin: str, method: str, track: str, prompt: str, permission_mode: str, model: Optional[str] = None,
              settings: Optional[str] = None) -> List[str]:
    """旗標全在前、開工句固定放最後（官方建議的位置；印指令時遮掉）；--settings、--model 只在有指定時才帶。"""
    native = ["--name", track, "--worktree", track, "--permission-mode", permission_mode]
    tail = (["--settings", settings] if settings else []) + (["--model", model] if model else [])
    if method == "bg":
        return [claude_bin, "--bg"] + native + tail + [prompt]
    if method == "print":
        return [claude_bin, "-p"] + native + ["--output-format", "json"] + tail + [prompt]
    raise ValueError(f"method {method} 不由本腳本起 session")


def parse_bg_id(stdout: str) -> Optional[str]:
    m = BG_ID_RE.search(stdout or "")
    return m.group(1) if m else None


def fallback_block(prompt: str, step: str, extra: str = "") -> str:
    """退回人貼的訊息：哪一步失敗、貼哪裡、貼什麼。"""
    lines = [
        f"退回人貼：停在「{step}」。",
        "請開一個新的 Claude Code 分頁、貼上下面整段、點送出鈕（Enter 只換行）：",
        "```",
        prompt.rstrip("\n"),
        "```",
    ]
    if extra:
        lines.append(extra)
    return "\n".join(lines)


# ─── 外部狀態：設定、state 檔 ─────────────────────────────────────────────────
def load_spawn_config(f: Optional[Path] = None) -> Dict[str, Any]:
    cfg = {**DEFAULTS, "default_model": None}
    f = f or SPAWN_CONFIG
    if not f.is_file():
        return cfg
    try:
        section = json.loads(f.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return cfg
    if not isinstance(section, dict):
        return cfg
    for k in DEFAULTS:
        if isinstance(section.get(k), (int, float)) and section[k] > 0:
            cfg[k] = section[k]
    dm = section.get("default_model")
    if isinstance(dm, str) and dm.strip():
        cfg["default_model"] = dm.strip()
    return cfg


def lock_state(f: Path, log: Callable[[str], None]) -> Optional[Path]:
    """拿 <state 檔>.lock 目錄鎖（建得成才算拿到；本腳本之間共用這一把）。別支拿著就每 0.1 秒再試，
    STATE_LOCK_WAIT_SEC 秒還拿不到 → 印原因回 None；不搶別人的鎖。"""
    lock = f.with_name(f.name + ".lock")
    deadline = time.monotonic() + STATE_LOCK_WAIT_SEC
    while True:
        try:
            lock.mkdir()
            return lock
        except (FileExistsError, PermissionError):  # Windows 上別人正在刪的目錄再建會回拒絕存取，一樣等
            if time.monotonic() >= deadline:
                log(f"  ! 等 {STATE_LOCK_WAIT_SEC:g} 秒拿不到 {lock}（別支正在寫，或留下沒收的鎖）")
                return None
            time.sleep(0.1)
        except OSError as e:
            log(f"  ! 建不了鎖 {lock}：{e}")
            return None


def unlock_state(lock: Path, log: Callable[[str], None]) -> None:
    try:
        lock.rmdir()
    except OSError as e:
        log(f"  ! 放不掉鎖 {lock}：{e}")


def write_json_atomic(f: Path, data: Any) -> None:
    """寫同目錄暫存檔再 os.replace 換上（中途失敗原檔不動、暫存檔刪掉）。"""
    tmp = f.with_name(f"{f.name}.console-spawn.{os.getpid()}.tmp")
    try:
        tmp.write_bytes((json.dumps(data, ensure_ascii=False, indent=2)).encode("utf-8"))
        os.replace(tmp, f)
    finally:
        tmp.unlink(missing_ok=True)


def load_state(f: Path) -> Tuple[List[Dict[str, Any]], str]:
    """讀 state 檔（呼叫端先拿鎖）：(列, 讀不了的原因)；檔不存在＝還沒起過 → ([], "")。
    壞檔不當空清單：當空清單，上限就從 0 數起、等於放行。"""
    try:
        rows = json.loads(f.read_bytes().decode("utf-8"))
    except FileNotFoundError:
        return [], ""
    except (OSError, ValueError) as e:            # ValueError 含 JSONDecodeError、UnicodeDecodeError
        return [], f"{f} 讀不了或不是合法 JSON：{e}"
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return [], f"{f} 格式不對（應為物件清單）"
    return rows, ""


def with_state(repo: Path, change: Optional[Callable[[List[Dict[str, Any]]], None]],
               warn: Callable[[str], None]) -> Tuple[List[Dict[str, Any]], str]:
    """拿 <state>.lock 鎖讀 state；給了 change 就套上它、寫暫存檔再 os.replace（鎖內重讀，別支同時改也不丟列）。
    讀也拿鎖：Windows 上一邊開著檔讀，另一邊的 os.replace 會被拒（PermissionError，實測）。回 (列, 失敗原因)；失敗時壞檔不蓋。"""
    f = repo / "workflow" / STATE_FILE
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return [], f"建不了 {f.parent}：{e}"
    lock = lock_state(f, warn)
    if lock is None:
        return [], f"拿不到 {f} 的鎖"
    try:
        rows, bad = load_state(f)
        if bad or change is None:
            return rows, bad
        change(rows)
        write_json_atomic(f, rows)
        return rows, ""
    except OSError as e:
        return [], f"寫 {f} 失敗：{e}"
    finally:
        unlock_state(lock, warn)


def update_state(repo: Path, change: Callable[[List[Dict[str, Any]]], None], warn: Callable[[str], None]) -> bool:
    """改 state 檔一筆；記不上 → 原因印到 warn、回 False。"""
    _, bad = with_state(repo, change, warn)
    if bad:
        warn(f"  ! {bad}")
    return not bad


def list_agents(claude_bin: str, run_fn: Callable[..., Any]) -> List[Dict[str, Any]]:
    """`claude agents --json`（不需 TTY）；叫不到或不是 JSON 就回空清單。"""
    try:
        r = run_fn([claude_bin, "agents", "--json"], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", stdin=subprocess.DEVNULL, timeout=30, creationflags=NO_WINDOW)
        rows = json.loads(r.stdout or "[]")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []
    return [x for x in rows if isinstance(x, dict)]


def alive_spawned(state: List[Dict[str, Any]], agents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """state 裡記的 session，還出現在 agents 清單的就算活著（不管 busy／idle／waiting）。"""
    alive_ids = {a.get("sessionId") for a in agents} | {a.get("id") for a in agents}
    alive_ids.discard(None)
    return [s for s in state if s.get("sessionId") in alive_ids or s.get("id") in alive_ids]


def _ext_version(p: Path) -> tuple:
    m = re.search(r"claude-code-(\d+)\.(\d+)\.(\d+)", str(p))
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def find_claude_bin(explicit: Optional[str]) -> Optional[str]:
    """--claude-bin > VS Code 擴充內建（最新版；現行 session 都用它、才有 --bg/attach/logs）> PATH。"""
    if explicit:
        return explicit if Path(explicit).is_file() else None
    ext_root = Path.home() / ".vscode" / "extensions"
    cands = sorted(ext_root.glob("anthropic.claude-code-*/resources/native-binary/claude*"), key=_ext_version, reverse=True)
    for c in cands:
        if c.is_file() and c.suffix in (".exe", ""):
            return str(c)
    return shutil.which("claude")


# ─── 主流程 ─────────────────────────────────────────────────────────────────────
def spawn_bg(repo: Path, cmd: List[str], run_fn) -> Dict[str, Any]:
    r = run_fn(cmd, cwd=str(repo), stdin=subprocess.DEVNULL, capture_output=True, text=True,
               encoding="utf-8", errors="replace", timeout=120, creationflags=NO_WINDOW)
    return {"exit": r.returncode, "stdout": r.stdout or "", "stderr": r.stderr or ""}


def wait_kickoff(args, claude_bin: str, short_id: str, run_fn, sleep_fn, now_fn, data_dir: Path) -> Dict[str, Any]:
    """等到 agents 清單有它且 transcript 出現「<軌名> 收到開工」或 API 錯誤；
    回 {ok, how, name, sessionId, elapsed, model, api_error}（api_error 只在沒報到時給）。"""
    t0 = now_fn()
    name, session_id, cwd = "未出現", None, native_worktree(args.repo, args.track)
    while True:
        for a in list_agents(claude_bin, run_fn):
            if a.get("id") == short_id or str(a.get("sessionId", "")).startswith(short_id):
                name, session_id = a.get("name") or name, a.get("sessionId") or session_id
                cwd = Path(a["cwd"]) if a.get("cwd") else cwd
        tp = transcript_path(data_dir, cwd, session_id) if session_id else None
        how = kickoff_received(tp, args.track) if tp else None
        model, err = model_and_api_error(tp) if tp else (None, None)
        if how or err:
            return {"ok": bool(how), "how": how, "name": name, "sessionId": session_id, "elapsed": now_fn() - t0,
                    "model": model, "api_error": None if how else err}
        if now_fn() - t0 >= args.timeout:
            return {"ok": False, "how": None, "name": name, "sessionId": session_id, "elapsed": now_fn() - t0,
                    "model": model, "api_error": None}
        sleep_fn(args.poll)


def main(argv: Optional[List[str]] = None, *, run_fn: Optional[Callable[..., Any]] = None, sleep_fn=time.sleep,
         now_fn=time.monotonic, data_dir: Optional[Path] = None) -> int:
    run_fn = run_fn or subprocess.run     # 呼叫當下才取：不在定義時綁住，測試換掉 subprocess.run 時才攔得到
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--track", required=True,
                    help="軌名：session 名字、worktree 名（.claude/worktrees/<軌名>，分支 worktree-<軌名>）、開工句第一個詞；"
                         "「<軌名> 收到開工」靠它認")
    ap.add_argument("--repo", required=True, type=Path, help="專案的 git 主檢出絕對路徑（新 session 從這裡起，worktree 由 Claude Code 建）")
    ap.add_argument("--prompt-file", required=True, type=Path, help="開工句檔（整檔原樣當第一句送出）")
    ap.add_argument("--permission-mode", required=True, help="明帶，不假設繼承：bypassPermissions／acceptEdits／default…")
    ap.add_argument("--method", choices=("bg", "print", "gui"), default="bg",
                    help="bg＝claude --bg（預設）；print＝claude -p 同步；gui＝不動畫面，只印退路")
    ap.add_argument("--timeout", type=float, default=None, help="等「收到開工」的秒數（預設 spawn.json 的 timeout_sec 或 90）")
    ap.add_argument("--poll", type=float, default=None, help="輪詢間隔秒（預設 config 或 3）")
    ap.add_argument("--max-parallel", type=int, default=None, help="同時活著的本腳本 session 上限（預設 config 或 5）")
    ap.add_argument("--claude-bin", default=None, help="claude 執行檔；不給就找 VS Code 擴充內建最新版，再找 PATH")
    ap.add_argument("--settings", type=Path, default=None,
                    help="新 session 的設定檔（原樣轉給 claude 的 --settings，例：關掉守門的設定檔）；不給就不帶；檔不存在 → FAIL、不起")
    ap.add_argument("--model", default=None,
                    help="新 session 的模型，給完整 id（例 claude-opus-5-5；別名對不上 transcript 記的完整 id 會判 FAIL）；"
                         "不給就用 spawn.json 的 default_model，再沒有就不帶（吃 Claude Code 預設）")
    args = ap.parse_args(argv)

    def log(s: str) -> None:
        print(s)

    def warn(s: str) -> None:
        print(s, file=sys.stderr)

    def fail(step: str, prompt: str = "", extra: str = "") -> int:
        print(fallback_block(prompt, step, extra) if prompt else f"退回人貼：停在「{step}」。")
        print("CONSOLE_SPAWN_CHECK FAIL")
        return 1

    log(f"console-spawn：track={args.track} method={args.method} repo={args.repo}")

    # 1. 前置
    if not args.prompt_file.is_file():
        log(f"  ✗ 開工句檔不存在：{args.prompt_file}")
        return fail("開工句檔不存在")
    prompt = args.prompt_file.read_text(encoding="utf-8-sig").strip()
    if not prompt:
        log("  ✗ 開工句檔是空的")
        return fail("開工句檔是空的")
    if not (args.repo / ".git").is_dir():
        log(f"  ✗ {args.repo} 不是 git 主檢出（沒有 .git 目錄；連結的 worktree 也不行）：從主檢出起，worktree 由 Claude Code 建")
        return fail("repo 檢查：不是 git 主檢出", prompt)
    if args.settings is not None and not args.settings.is_file():
        log(f"  ✗ --settings 的設定檔不存在：{args.settings}")
        return fail("設定檔不存在", prompt)
    settings = str(args.settings.resolve()) if args.settings is not None else None   # 新 session 會換 cwd：相對路徑先轉絕對
    cfg = load_spawn_config()
    args.timeout = args.timeout if args.timeout is not None else cfg["timeout_sec"]
    args.poll = args.poll if args.poll is not None else cfg["poll_sec"]
    max_parallel = args.max_parallel if args.max_parallel is not None else cfg["max_parallel"]
    model = args.model or cfg["default_model"]
    kill = args.repo / "workflow" / KILL_SWITCH
    if kill.exists():
        log(f"  ✗ kill switch 存在：{kill}（刪掉才准起新 session）")
        return fail(f"kill switch {kill} 存在", prompt)
    if args.method == "gui":
        log("  · method=gui：畫面操作由總控台在 session 內用 MCPControl 做（剪貼簿貼進空分頁），本腳本不碰畫面")
        return fail("method=gui 不由腳本起", prompt)
    claude_bin = find_claude_bin(args.claude_bin)
    if not claude_bin:
        log("  ✗ 找不到 claude 執行檔（--claude-bin／VS Code 擴充／PATH 都沒有）")
        return fail("找不到 claude 執行檔", prompt)
    log(f"  · claude={claude_bin}")
    state, bad = with_state(args.repo, None, warn)
    if bad:
        warn(f"  ! {bad}")
        log("  ✗ state 檔讀不了：數不出本腳本起過、還活著的 session，不起新的（原因見 stderr）")
        return fail("state 檔讀不了，數不出還活著的 session", prompt,
                    f"修好或刪掉 {args.repo / 'workflow' / STATE_FILE}（刪掉＝忘記之前起過哪些，先用 `claude agents` 看還有誰活著）再重跑。")
    alive = alive_spawned(state, list_agents(claude_bin, run_fn))
    if len(alive) >= max_parallel:
        log(f"  ✗ 由本腳本起、還活著的 session 已 {len(alive)} 個（上限 {max_parallel}）：")
        for s in alive:
            log(f"      {s.get('id')}  {s.get('track')}  {s.get('worktree')}  起於 {s.get('startedAt')}")
        return fail(f"並行上限 {max_parallel}", prompt, "先 `claude stop <id>` 收掉不用的，或調 skills/console/spawn.json 的 max_parallel。")
    worktree = native_worktree(args.repo, args.track)
    if worktree.is_dir():
        log(f"  · {worktree} 已存在：Claude Code 會沿用它（不重建）")

    # 2. 起 session
    cmd = build_cmd(claude_bin, args.method, args.track, prompt, args.permission_mode, model, settings)
    shown = cmd[:-1] + [f"<開工句 {len(prompt)} 字>"]
    log(f"  · 指令：{shown}  cwd={args.repo}")
    if args.method == "print":
        if model:
            log(f"  · method=print 只把 --model {model} 帶上，不核對實際模型（不讀 transcript）")
        r = run_fn(cmd, cwd=str(args.repo), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=max(args.timeout, 60) * 20, creationflags=NO_WINDOW)
        log(f"  · claude -p exit={r.returncode}")
        if r.returncode != 0:
            log(f"  ✗ stderr：{(r.stderr or '').strip()[-800:]}")
            return fail("claude -p 非零結束", prompt)
        print((r.stdout or "").strip()[-2000:])
        print("CONSOLE_SPAWN_CHECK PASS")
        return 0
    res = spawn_bg(args.repo, cmd, run_fn)
    short_id = parse_bg_id(res["stdout"])
    if res["exit"] != 0 or not short_id:
        log(f"  ✗ claude --bg exit={res['exit']}；stdout={res['stdout'].strip()[-400:]!r}；stderr={res['stderr'].strip()[-400:]!r}")
        untrusted = "Workspace not trusted" in res["stdout"] + res["stderr"]
        return fail("claude --bg 起不來", prompt,
                    f"主檢出沒有 `claude --bg` 認得的信任紀錄：在 {args.repo} 開終端機跑一次 `claude`、"
                    "接受信任提示後重跑本腳本。" if untrusted else "")
    log(f"  · 已起 session 短 id={short_id}")
    row = {"id": short_id, "sessionId": None, "track": args.track, "branch": f"worktree-{args.track}",
           "worktree": str(worktree), "startedAt": time.strftime("%Y-%m-%d %H:%M:%S")}
    recorded = update_state(args.repo, lambda rows: rows.append(row), warn)

    # 3. 等報到
    w = wait_kickoff(args, claude_bin, short_id, run_fn, sleep_fn, now_fn, data_dir or claude_data_dir())

    def note_session_id(rows: List[Dict[str, Any]]) -> None:
        mine = [r for r in rows if r.get("id") == short_id]   # 用短 id 認列：別支同時起的會排在後面，最後一列不一定是自己
        if not mine:                              # 起好時沒記上（鎖被佔、寫入失敗）：這次整列補記
            rows.append({**row, "sessionId": w["sessionId"]})
        for r in mine:
            r["sessionId"] = w["sessionId"]

    if w["sessionId"]:
        recorded = update_state(args.repo, note_session_id, warn)
    if not recorded:
        log(f"  ! 這個 session（{short_id}）沒記進 state 檔（原因見 stderr）：並行上限會少算它一個")
    log(f"  · session id={w['sessionId'] or '未出現'}  名字={w['name']}  等了 {w['elapsed']:.0f} 秒")
    if w["api_error"]:
        # 不退人貼：人貼的新分頁多半撞同一個錯（認證、額度），模型 id 錯則會退回預設模型
        log(f"  ✗ session 回 API 錯誤、停在等輸入：{w['api_error']}")
        log(f"  那個 session 還在：`claude stop {short_id}` 收掉；錯誤講的是模型就改 --model（完整 id）重跑本腳本，其他錯誤排除後再重跑。")
        print("CONSOLE_SPAWN_CHECK FAIL")
        return 1
    if not w["ok"]:
        log(f"  ✗ {args.timeout:.0f} 秒內沒收到「{args.track} 收到開工」")
        return fail(f"{args.timeout:.0f} 秒內沒收到「{args.track} 收到開工」", prompt,
                    f"那個 session 還在（`claude logs {short_id}` 看它在做什麼；確定不要就 `claude stop {short_id}`）。")
    log(f"  ✓ {args.track} 收到開工（{w['how']}）；人要看它：`claude attach {short_id}`")
    actual = w["model"] or NO_MODEL
    if model and w["model"] != model:
        log(f"  ✗ 模型不符：指定＝{model}／實際＝{actual}")
        log(f"  session 已開工、沒殺：要換就 `claude stop {short_id}` 後改 --model 重跑；將就用就 `claude attach {short_id}` 接手。")
        print("CONSOLE_SPAWN_CHECK FAIL")
        return 1
    log(f"  · 模型＝{actual}")
    print("CONSOLE_SPAWN_CHECK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
