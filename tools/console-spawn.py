#!/usr/bin/env python3
"""console-spawn.py：總控台替工作軌開 session 並送開工句（原話 G16：派工全程不用人貼 prompt）。

做什麼（照順序，哪一步不過就停在那步、印開工句退回人貼）：
  1. 前置：開工句檔存在；worktree 不是 live 根、且登記在 live 的 .git/worktrees/ 名單；kill switch 檔
     <live>/workflow/console-spawn.STOP 不存在；由本腳本起、還活著的 session 未達上限（console.spawn.max_parallel，預設 5）。
  2. 信任：worktree 在 ~/.claude.json 沒有信任紀錄時 `claude --bg` 會拒起；live 根已信任就替 worktree 補一筆
     （鍵用正斜線形，跟 Claude Code 自己寫的一樣）並印出來；live 根也沒信任 → FAIL。
  3. 起 session（--method bg，預設）：`claude.exe --bg "<開工句>" --permission-mode <模式> [--model <id>]`，cwd＝worktree，
     subprocess 不經 shell（開工句以 / 開頭也原樣送到）。stdout 的 `backgrounded · <短 id>` 就是 session 短 id。
     模型：--model 優先，其次 config console.spawn.default_model，都沒有就不帶（吃 Claude Code 預設），不猜。
  4. 等它報到：輪詢 `claude agents --json` 取它在 ListAgents 的名字；讀它的 transcript
     （<資料根>/projects/<cwd-slug>/<sessionId>.jsonl）看有沒有「<軌名> 收到開工」——SendMessage 工具呼叫的正文，
     或 assistant 的文字都認，印出是哪一種。報到後印「模型＝<transcript 最近一則真回應的 message.model>」；
     指定了模型卻對不上（或讀不到）→ FAIL 印「指定＝…／實際＝…」，session 不殺。
     transcript 出現 API 錯誤訊息（例：模型 id 不存在，claude 不拒起、第一回合回錯後停著等輸入）→ 不等逾時、立刻 FAIL 印原文。
     這兩種 FAIL 不退人貼（人貼救不了），只印 stop 指令讓總控台決定。
  5. 逾時（--timeout，預設 90 秒）→ exit 1，印開工句 code block 與「退回人貼」，session 不殺（印 stop 指令讓總控台決定）。
  --method print：同步跑 `claude -p`（阻塞到那個 session 結束），備援用；--method gui：本腳本不動畫面，直接印開工句退回。

怎麼跑：
  python ~/.claude/tools/console-spawn.py --track track-x --worktree C:\\...\\.claude-wt\\x --branch x \\
      --prompt-file C:\\...\\kickoff.txt --permission-mode bypassPermissions --model claude-opus-5-5
  完整參數以 --help 為準。尾行 `CONSOLE_SPAWN_CHECK PASS` 或 `CONSOLE_SPAWN_CHECK FAIL`；exit 0／1 對應。
"""
from __future__ import annotations

import argparse
import glob
import json
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

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
from lib.project_root import claude_data_dir, claude_global_config  # noqa: E402

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
KILL_SWITCH = "console-spawn.STOP"
STATE_FILE = "state-console-spawn.json"          # workflow/state-*.json 已在 .gitignore
DEFAULTS = {"max_parallel": 5, "timeout_sec": 90, "poll_sec": 3}
BG_ID_RE = re.compile(r"backgrounded\s*[·•:]\s*([0-9a-f]{6,})", re.I)
KICKOFF_WORD = "收到開工"
SYNTHETIC_MODEL = "<synthetic>"                  # Claude Code 自己補寫的 assistant（API 錯誤、No response requested）
NO_MODEL = "讀不到（transcript 沒有 model 欄）"


# ─── 純函式：路徑與判定 ───────────────────────────────────────────────────────
def norm(p: Path) -> str:
    """路徑比對用：resolve 後小寫、統一正斜線（Windows 大小寫與斜線不影響同一目錄）。"""
    return str(Path(p).resolve()).replace("\\", "/").rstrip("/").lower()


def trust_key(p: Path) -> str:
    """Claude Code 在 ~/.claude.json projects 用的鍵：絕對路徑、正斜線、保留大小寫（反斜線形它不認，實測 2.1.304）。"""
    return str(Path(p).resolve()).replace("\\", "/")


def live_root_of(worktree: Path) -> Optional[Path]:
    """從 worktree 的 .git 檔（gitdir: <live>/.git/worktrees/<名>）推 live 根；不是 worktree 就回 None。"""
    dotgit = worktree / ".git"
    if not dotgit.is_file():
        return None
    line = dotgit.read_text(encoding="utf-8", errors="replace").strip()
    if not line.startswith("gitdir:"):
        return None
    gitdir = Path(line[len("gitdir:"):].strip())
    if gitdir.parent.name != "worktrees" or gitdir.parent.parent.name != ".git":
        return None
    return gitdir.parent.parent.parent


def worktree_registered(worktree: Path, live_root: Path) -> bool:
    """live 的 .git/worktrees/<名>/gitdir 要指回這棵 worktree 的 .git 檔。"""
    reg = live_root / ".git" / "worktrees"
    if not reg.is_dir():
        return False
    target = norm(worktree / ".git")
    for entry in reg.iterdir():
        f = entry / "gitdir"
        if f.is_file() and norm(Path(f.read_text(encoding="utf-8", errors="replace").strip())) == target:
            return True
    return False


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


def build_cmd(claude_bin: str, method: str, prompt: str, permission_mode: str, model: Optional[str] = None) -> List[str]:
    """開工句固定在 index 2（印指令時遮掉）；--model 只在有指定時接在最後。"""
    tail = ["--model", model] if model else []
    if method == "bg":
        return [claude_bin, "--bg", prompt, "--permission-mode", permission_mode] + tail
    if method == "print":
        return [claude_bin, "-p", prompt, "--permission-mode", permission_mode, "--output-format", "json"] + tail
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


# ─── 外部狀態：設定、信任、state 檔 ─────────────────────────────────────────────
def load_spawn_config(live_root: Path) -> Dict[str, Any]:
    cfg = {**DEFAULTS, "default_model": None}
    f = live_root / "workflow" / "config.json"
    if not f.is_file():
        return cfg
    try:
        section = (json.loads(f.read_text(encoding="utf-8-sig")).get("console") or {}).get("spawn") or {}
    except (json.JSONDecodeError, OSError, AttributeError):
        return cfg
    for k in DEFAULTS:
        if isinstance(section.get(k), (int, float)) and section[k] > 0:
            cfg[k] = section[k]
    dm = section.get("default_model")
    if isinstance(dm, str) and dm.strip():
        cfg["default_model"] = dm.strip()
    return cfg


def ensure_trust(config_path: Path, worktree: Path, live_root: Path, log: Callable[[str], None]) -> bool:
    """worktree 已信任 → True；未信任但 live 根已信任 → 補一筆後 True；都沒有 → False。"""
    try:
        data = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    except json.JSONDecodeError:
        log(f"  ! {config_path} 不是合法 JSON，不敢改；當作未信任")
        return False
    projects = data.setdefault("projects", {})
    wt_key = trust_key(worktree)
    if (projects.get(wt_key) or {}).get("hasTrustDialogAccepted") is True:
        return True
    live_norm = norm(live_root)
    live_trusted = any(
        (v or {}).get("hasTrustDialogAccepted") is True and k.replace("\\", "/").rstrip("/").lower() == live_norm
        for k, v in projects.items()
    )
    if not live_trusted:
        log(f"  ! live 根 {live_root} 在 {config_path} 沒有信任紀錄，不替 worktree 補")
        return False
    projects.setdefault(wt_key, {})["hasTrustDialogAccepted"] = True
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"  · 已替 worktree 補信任紀錄（沿用 live 根的信任）：projects[{wt_key!r}].hasTrustDialogAccepted=true")
    return True


def load_state(live_root: Path) -> List[Dict[str, Any]]:
    f = live_root / "workflow" / STATE_FILE
    if not f.is_file():
        return []
    try:
        rows = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return rows if isinstance(rows, list) else []


def save_state(live_root: Path, rows: List[Dict[str, Any]]) -> None:
    f = live_root / "workflow" / STATE_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


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
def spawn_bg(worktree: Path, cmd: List[str], run_fn) -> Dict[str, Any]:
    r = run_fn(cmd, cwd=str(worktree), stdin=subprocess.DEVNULL, capture_output=True, text=True,
               encoding="utf-8", errors="replace", timeout=120, creationflags=NO_WINDOW)
    return {"exit": r.returncode, "stdout": r.stdout or "", "stderr": r.stderr or ""}


def wait_kickoff(args, claude_bin: str, short_id: str, run_fn, sleep_fn, now_fn, data_dir: Path) -> Dict[str, Any]:
    """等到 agents 清單有它且 transcript 出現「<軌名> 收到開工」或 API 錯誤；
    回 {ok, how, name, sessionId, elapsed, model, api_error}（api_error 只在沒報到時給）。"""
    t0 = now_fn()
    name, session_id = "未出現", None
    while True:
        for a in list_agents(claude_bin, run_fn):
            if a.get("id") == short_id or str(a.get("sessionId", "")).startswith(short_id):
                name, session_id = a.get("name") or name, a.get("sessionId") or session_id
        tp = transcript_path(data_dir, args.worktree, session_id) if session_id else None
        how = kickoff_received(tp, args.track) if tp else None
        model, err = model_and_api_error(tp) if tp else (None, None)
        if how or err:
            return {"ok": bool(how), "how": how, "name": name, "sessionId": session_id, "elapsed": now_fn() - t0,
                    "model": model, "api_error": None if how else err}
        if now_fn() - t0 >= args.timeout:
            return {"ok": False, "how": None, "name": name, "sessionId": session_id, "elapsed": now_fn() - t0,
                    "model": model, "api_error": None}
        sleep_fn(args.poll)


def main(argv: Optional[List[str]] = None, *, run_fn=subprocess.run, sleep_fn=time.sleep, now_fn=time.monotonic,
         config_path: Optional[Path] = None, data_dir: Optional[Path] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--track", required=True, help="軌名（開工句第一個詞；「<軌名> 收到開工」靠它認）")
    ap.add_argument("--worktree", required=True, type=Path, help="worktree 絕對路徑（新 session 的 cwd；不能是 live 根）")
    ap.add_argument("--branch", required=True, help="該軌分支名（只記進 state，不切換）")
    ap.add_argument("--prompt-file", required=True, type=Path, help="開工句檔（整檔原樣當第一句送出）")
    ap.add_argument("--permission-mode", required=True, help="明帶，不假設繼承：bypassPermissions／acceptEdits／default…")
    ap.add_argument("--method", choices=("bg", "print", "gui"), default="bg",
                    help="bg＝claude --bg（預設）；print＝claude -p 同步；gui＝不動畫面，只印退路")
    ap.add_argument("--timeout", type=float, default=None, help="等「收到開工」的秒數（預設 config console.spawn.timeout_sec 或 90）")
    ap.add_argument("--poll", type=float, default=None, help="輪詢間隔秒（預設 config 或 3）")
    ap.add_argument("--max-parallel", type=int, default=None, help="同時活著的本腳本 session 上限（預設 config 或 5）")
    ap.add_argument("--claude-bin", default=None, help="claude 執行檔；不給就找 VS Code 擴充內建最新版，再找 PATH")
    ap.add_argument("--model", default=None,
                    help="新 session 的模型，給完整 id（例 claude-opus-5-5；別名對不上 transcript 記的完整 id 會判 FAIL）；"
                         "不給就用 config console.spawn.default_model，再沒有就不帶（吃 Claude Code 預設）")
    args = ap.parse_args(argv)

    def log(s: str) -> None:
        print(s)

    def fail(step: str, prompt: str = "", extra: str = "") -> int:
        print(fallback_block(prompt, step, extra) if prompt else f"退回人貼：停在「{step}」。")
        print("CONSOLE_SPAWN_CHECK FAIL")
        return 1

    log(f"console-spawn：track={args.track} method={args.method} worktree={args.worktree}")

    # 1. 前置
    if not args.prompt_file.is_file():
        log(f"  ✗ 開工句檔不存在：{args.prompt_file}")
        return fail("開工句檔不存在")
    prompt = args.prompt_file.read_text(encoding="utf-8-sig").strip()
    if not prompt:
        log("  ✗ 開工句檔是空的")
        return fail("開工句檔是空的")
    if not args.worktree.is_dir():
        log(f"  ✗ worktree 目錄不存在：{args.worktree}")
        return fail("worktree 目錄不存在", prompt)
    live_root = live_root_of(args.worktree)
    if live_root is None or norm(live_root) == norm(args.worktree):
        log(f"  ✗ {args.worktree} 不是 git worktree（或就是 live 根）：新 session 只准開在 worktree")
        return fail("worktree 檢查：不是 worktree／是 live 根", prompt)
    if not worktree_registered(args.worktree, live_root):
        log(f"  ✗ {args.worktree} 沒登記在 {live_root / '.git' / 'worktrees'}")
        return fail("worktree 檢查：未登記", prompt)
    cfg = load_spawn_config(live_root)
    args.timeout = args.timeout if args.timeout is not None else cfg["timeout_sec"]
    args.poll = args.poll if args.poll is not None else cfg["poll_sec"]
    max_parallel = args.max_parallel if args.max_parallel is not None else cfg["max_parallel"]
    model = args.model or cfg["default_model"]
    kill = live_root / "workflow" / KILL_SWITCH
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
    state = load_state(live_root)
    alive = alive_spawned(state, list_agents(claude_bin, run_fn))
    if len(alive) >= max_parallel:
        log(f"  ✗ 由本腳本起、還活著的 session 已 {len(alive)} 個（上限 {max_parallel}）：")
        for s in alive:
            log(f"      {s.get('id')}  {s.get('track')}  {s.get('worktree')}  起於 {s.get('startedAt')}")
        return fail(f"並行上限 {max_parallel}", prompt, "先 `claude stop <id>` 收掉不用的，或調 console.spawn.max_parallel。")

    # 2. 信任
    cfg_path = config_path or claude_global_config()
    if not ensure_trust(cfg_path, args.worktree, live_root, log):
        return fail("worktree 未信任且 live 根也沒信任紀錄", prompt,
                    f"在 {args.worktree} 跑一次 `claude` 接受信任提示，再重跑本腳本。")

    # 3. 起 session
    cmd = build_cmd(claude_bin, args.method, prompt, args.permission_mode, model)
    shown = [c if i != 2 else f"<開工句 {len(prompt)} 字>" for i, c in enumerate(cmd)]
    log(f"  · 指令：{shown}  cwd={args.worktree}")
    if args.method == "print":
        if model:
            log(f"  · method=print 只把 --model {model} 帶上，不核對實際模型（不讀 transcript）")
        r = run_fn(cmd, cwd=str(args.worktree), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=max(args.timeout, 60) * 20, creationflags=NO_WINDOW)
        log(f"  · claude -p exit={r.returncode}")
        if r.returncode != 0:
            log(f"  ✗ stderr：{(r.stderr or '').strip()[-800:]}")
            return fail("claude -p 非零結束", prompt)
        print((r.stdout or "").strip()[-2000:])
        print("CONSOLE_SPAWN_CHECK PASS")
        return 0
    res = spawn_bg(args.worktree, cmd, run_fn)
    short_id = parse_bg_id(res["stdout"])
    if res["exit"] != 0 or not short_id:
        log(f"  ✗ claude --bg exit={res['exit']}；stdout={res['stdout'].strip()[-400:]!r}；stderr={res['stderr'].strip()[-400:]!r}")
        return fail("claude --bg 起不來", prompt)
    log(f"  · 已起 session 短 id={short_id}")
    state.append({"id": short_id, "sessionId": None, "track": args.track, "branch": args.branch,
                  "worktree": str(args.worktree), "startedAt": time.strftime("%Y-%m-%d %H:%M:%S")})
    save_state(live_root, state)

    # 4. 等報到
    w = wait_kickoff(args, claude_bin, short_id, run_fn, sleep_fn, now_fn, data_dir or claude_data_dir())
    if w["sessionId"]:
        state[-1]["sessionId"] = w["sessionId"]
        save_state(live_root, state)
    log(f"  · session id={w['sessionId'] or '未出現'}  ListAgents 名字={w['name']}  等了 {w['elapsed']:.0f} 秒")
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
