#!/usr/bin/env python3
"""install.py — 原子記憶系統安裝器：自檢、安裝（接管既有 ~/.claude）、升級、驗證。

做什麼：把本 repo 裝進 `~/.claude`。既有、非 git 的 `~/.claude` 會被「接管」——原地接上版控，
使用者的檔先進備份再換成系統版本，`settings.json` 與 `workflow/config.json`（覆蓋檔）
把使用者的值疊回系統版本上，並下 skip-worktree 標記讓 git 不把它們當成修改。
`~/.claude` 不存在時先建立空目錄再接管：`settings.json` 只含系統的 hooks 與 statusLine。

怎麼跑（目標一律是 `~/.claude`；來源是本腳本所在的 clone）：
  python tools/install.py --check     # 安裝前自檢，唯讀
  python tools/install.py --apply     # 安裝，可重跑，中斷後重跑會從斷點接續
  python tools/install.py --upgrade   # 已安裝機器升級（pull + 重新合併覆蓋檔）
  python tools/install.py --verify    # 安裝後驗證，印三層記憶現況；唯讀，重開 Claude Code 後在裡面跑

本腳本不安裝任何套件、不註冊 MCP（下次啟動 Claude Code 時自動註冊）、不 commit、不 push。
完整參數與 exit code 以 --help 為準。
"""
from __future__ import annotations

import argparse
import functools
import getpass
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Callable, List, Optional, Tuple

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

HOME = Path.home()
TARGET = HOME / ".claude"
SOURCE = Path(__file__).resolve().parent.parent
STATE_FILE = TARGET / ".git" / "atom-install-state.json"
OVERLAYS = ("settings.json", "workflow/config.json")
# 無條件備份：ignored 的個人檔 git 不會列；覆蓋檔即使與系統版相同也要留一份當「使用者的」
ALWAYS_BACKUP = ("USER.md", "IDENTITY.md", *OVERLAYS)
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
# 指令裡的 .claude/hooks/<檔> 或 .claude/tools/<檔>；group(1)＝相對 ~/.claude 的路徑
HOOK_PATH_RE = re.compile(r"\.claude/((?:hooks|tools)/[^\s\"'`;|&()<>]+)")
# 緊接在 .claude/ 之前、代表「家目錄」的寫法（小寫比對）；家目錄的實際路徑另由 system_path 補上
HOME_SPELLINGS = ("$home/", "${home}/", "~/", "%userprofile%/", "$userprofile/", "home()/'", 'home()/"')
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
# 子程序一律看到同一個家目錄：Windows 上 Python 看 USERPROFILE、bash 看 HOME
ENV = {**os.environ, "HOME": str(HOME), "USERPROFILE": str(HOME), "PYTHONIOENCODING": "utf-8"}


class InstallError(Exception):
    """安裝流程中止；訊息直接印給使用者。"""


# ─── 子程序與檔案小工具 ─────────────────────────────────────────────────────

def run(cmd: List[str], cwd: Optional[Path] = None, check: bool = True,
        env: Optional[dict] = None, timeout: int = 600) -> subprocess.CompletedProcess:
    """跑子程序（強制家目錄環境、不彈視窗、UTF-8）。check=True 時非零即 InstallError。"""
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env or ENV, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as e:
        if check:
            raise InstallError(f"無法執行 {cmd[0]}：{type(e).__name__}: {e}")
        return subprocess.CompletedProcess(cmd, 127, "", f"{type(e).__name__}: {e}")
    if check and r.returncode != 0:
        raise InstallError(f"指令失敗（exit {r.returncode}）：{' '.join(cmd)}\n{(r.stderr or r.stdout).strip()}")
    return r


def git(*args: str, cwd: Path = TARGET, check: bool = True) -> subprocess.CompletedProcess:
    return run(["git", *args], cwd=cwd, check=check)


def tool(rel: str, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """用跑本腳本的這支 Python 執行目標樹內的工具；失敗不拋，由呼叫端判讀。"""
    return run([sys.executable, str(TARGET / rel), *args], cwd=TARGET, check=False, timeout=timeout)


def write_json(path: Path, data: dict) -> None:
    """暫存檔 + os.replace，中斷不留半截檔。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".install-tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def read_user_json(path: Path) -> Optional[dict]:
    """使用者的 JSON 檔：不存在 → None；壞檔 → 中止（不默默當成沒有）。"""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise InstallError(f"{path} 不是可讀的 JSON（{e}）。修好它，或刪掉它表示不保留，再重跑。")
    if not isinstance(data, dict):
        raise InstallError(f"{path} 的最外層不是物件。修好它，或刪掉它表示不保留，再重跑。")
    return data


def head_json(rel: str, rev: str = "HEAD") -> dict:
    """系統的版本：git show <rev>:<檔>。"""
    return json.loads(git("show", f"{rev}:{rel}").stdout)


def resolve_bash() -> str:
    """與 hooks/run-bash-hidden.py 同一套找法；找不到回空字串。"""
    for p in (r"C:\Program Files\Git\usr\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe"):
        if os.path.exists(p):
            return p
    return shutil.which("bash") or ""


# ─── 覆蓋檔合併 ─────────────────────────────────────────────────────────────

def system_path(command: str) -> Optional[str]:
    """指令指向家目錄的 .claude/hooks/ 或 .claude/tools/ 時，回該檔相對 ~/.claude 的路徑；否則 None。
    別的專案的 .claude（例如 "$CLAUDE_PROJECT_DIR"/.claude/hooks/…）不算。"""
    cmd = command.replace("\\", "/")
    home = HOME.as_posix().lower()
    # 家目錄的實際路徑兩種寫法：C:/Users/x/ 與 Git Bash 的 /c/Users/x/
    homes = (*HOME_SPELLINGS, home + "/", "/" + home.replace(":", "", 1) + "/")
    for found in HOOK_PATH_RE.finditer(cmd):
        if cmd[:found.start()].lower().endswith(homes):
            return found.group(1)
    return None


def replaced_by_system(entry: object, tracked: frozenset) -> bool:
    """hook／statusLine 條目是否該讓位給系統版本。指向家目錄 .claude 的指令才考慮：
    指到 repo 追蹤的檔 → 是；檔案在 ~/.claude 裡但不是追蹤檔（使用者自己放的腳本）→ 否；檔案不存在（舊系統殘留）→ 是。"""
    command = entry.get("command") if isinstance(entry, dict) else None
    rel = system_path(command) if isinstance(command, str) else None
    if rel is None:
        return False
    return rel in tracked or not (TARGET / rel).exists()


def hook_commands(settings: dict) -> List[str]:
    """settings 的 hooks 區塊裡所有指令字串；結構不合的條目略過。"""
    hooks = settings.get("hooks")
    out = []
    for groups in hooks.values() if isinstance(hooks, dict) else []:
        for group in groups if isinstance(groups, list) else []:
            entries = group.get("hooks") if isinstance(group, dict) else None
            out += [h["command"] for h in entries or [] if isinstance(h, dict) and isinstance(h.get("command"), str)]
    return out


def merge_settings(user: Optional[dict], system: dict, tracked: frozenset) -> Tuple[dict, List[str]]:
    """hooks 取系統整段＋使用者自己的條目；statusLine 使用者自己的優先；其餘頂層鍵只用使用者的。
    tracked＝repo 追蹤的 hooks/、tools/ 檔案清單。回（合併結果, 被丟掉且系統版沒有接手的使用者指令）。"""
    user = user or {}
    hooks = json.loads(json.dumps(system.get("hooks") or {}))
    system_status = system.get("statusLine")
    system_commands = [*hook_commands(system), str((system_status or {}).get("command", ""))]
    taken_over = {system_path(c) for c in system_commands}
    dropped = []
    user_hooks = user.get("hooks") if isinstance(user.get("hooks"), dict) else {}
    for event, groups in user_hooks.items():
        for group in groups if isinstance(groups, list) else []:
            entries = (group.get("hooks") if isinstance(group, dict) else None) or []
            own = [h for h in entries if not replaced_by_system(h, tracked)]
            dropped += [h["command"] for h in entries if replaced_by_system(h, tracked)]
            if own:
                hooks.setdefault(event, []).append({**group, "hooks": own})
    merged = {k: v for k, v in user.items() if k not in ("hooks", "statusLine")}
    merged["hooks"] = hooks
    status = user.get("statusLine")
    if status and replaced_by_system(status, tracked):
        dropped.append(status["command"])
        status = None
    if status or system_status:
        merged["statusLine"] = status or system_status
    return merged, [c for c in dropped if system_path(c) not in taken_over]


def print_dropped(dropped: List[str]) -> None:
    """被丟掉的使用者 hook 一行一條印出來。"""
    for command in dropped:
        print(f"    ⚠ 已移除你原有的這條 hook（指向本系統已沒有的檔案，或系統不再掛它）：{command[:120]}")


def deep_merge(base: dict, over: dict) -> dict:
    """over 的值疊在 base 上；兩邊都是物件才往下併，其餘（含陣列）整個取 over。"""
    out = dict(base)
    for key, value in over.items():
        both_dict = isinstance(value, dict) and isinstance(out.get(key), dict)
        out[key] = deep_merge(out[key], value) if both_dict else value
    return out


def changed_keys(mine: dict, base: dict) -> dict:
    """mine 相對 base 改過或新增的鍵（遞迴）；base 有而 mine 沒有的不算（使用者刪掉的鍵會被新版補回）。"""
    out = {}
    for key, value in mine.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            sub = changed_keys(value, base[key])
            if sub:
                out[key] = sub
            continue
        if key not in base or value != base[key]:
            out[key] = value
    return out


def drop_type_conflicts(changed: dict, base: dict, new: dict, path: str = "") -> Tuple[dict, List[str]]:
    """changed（changed_keys 的結果）要套到 new 上之前，挑掉型別衝突：使用者只改了物件裡的子鍵，
    但 new 的同一個鍵已不是物件 → 以 new 為準。回（留下的, 被挑掉的鍵路徑）。"""
    kept, dropped = {}, []
    for key, value in changed.items():
        partial = isinstance(value, dict) and isinstance(base.get(key), dict)
        if not partial or key not in new:
            kept[key] = value
            continue
        if not isinstance(new[key], dict):
            dropped.append(path + key)
            continue
        kept[key], below = drop_type_conflicts(value, base[key], new[key], f"{path}{key}.")
        dropped += below
    return kept, dropped


def tracked_system_files() -> frozenset:
    """repo 追蹤的 hooks/、tools/ 檔案（相對 ~/.claude 的路徑）。"""
    return frozenset(p for p in git("ls-files", "-z", "--", "hooks", "tools").stdout.split("\0") if p)


def mark_overlay(rel: str, check: bool = True) -> None:
    r = git("update-index", "--skip-worktree", "--", rel, check=check)
    if r.returncode != 0:
        print(f"  ⚠ {rel} 下 skip-worktree 標記失敗：{r.stderr.strip()}")


# ─── 環境探測（--check 與 --verify 共用） ───────────────────────────────────

def probe_python() -> Tuple[bool, str]:
    return sys.version_info >= (3, 10), "%d.%d.%d" % sys.version_info[:3]


def probe_git() -> Tuple[bool, str]:
    r = run(["git", "--version"], check=False, timeout=20)
    return r.returncode == 0, r.stdout.strip() or r.stderr.strip()


def probe_bash() -> Tuple[bool, str]:
    bash = resolve_bash()
    return bool(bash), bash


def probe_node() -> Tuple[bool, str]:
    exe = shutil.which("node")
    if not exe:
        return False, "找不到 node"
    ver = run([exe, "--version"], check=False, timeout=20).stdout.strip()
    try:
        major = int(ver.lstrip("v").split(".")[0])
    except ValueError:
        return False, f"版本無法解析：{ver!r}"
    return major >= 18, ver


@functools.lru_cache(maxsize=1)
def ollama_models() -> Optional[Tuple[str, ...]]:
    """本機 Ollama daemon 的模型清單；daemon 沒回應 → None。"""
    try:
        with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=3) as resp:
            tags = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return tuple(str(m.get("name", "")) for m in tags.get("models") or [])


def probe_ollama() -> Tuple[bool, str]:
    models = ollama_models()
    if models is None:
        return False, f"daemon 沒回應（{OLLAMA_TAGS_URL}）"
    return True, f"daemon 在線，{len(models)} 個模型"


def probe_model(name: str) -> Callable[[], Tuple[bool, str]]:
    def probe() -> Tuple[bool, str]:
        models = ollama_models() or ()
        hit = [m for m in models if m == name or m.startswith(name + ":")]
        return bool(hit), hit[0] if hit else "本機 Ollama 沒有這個模型"
    return probe


@functools.lru_cache(maxsize=1)
def hook_python() -> str:
    """hook 實際用的 Python：settings.json 裡 workflow-guardian.py 那條 hook 指令開頭那支（目標優先、其次來源）；
    是 pythonw 而旁邊有 python 就取 python（同一個環境，看得到輸出）。
    讀不到或檔案不存在就用跑本腳本的這支（fix-hook-python.py 也會改用它）。"""
    for base in (TARGET, SOURCE):
        try:
            settings = json.loads((base / "settings.json").read_text(encoding="utf-8-sig"))
            commands = [c for c in hook_commands(settings) if "workflow-guardian.py" in c]
            exe = shlex.split(commands[0])[0]
        except (OSError, ValueError, AttributeError, IndexError):
            continue
        exe = os.path.expandvars(exe.replace("$HOME", HOME.as_posix()))
        console = os.path.join(os.path.dirname(exe), os.path.basename(exe).lower().replace("pythonw", "python"))
        exe = console if os.path.isfile(console) else exe
        if os.path.basename(exe).lower().startswith("python") and os.path.isfile(exe):
            return exe
    return sys.executable


def fix_hint(fix: str) -> str:
    """補裝指令裡的直譯器佔位字換成 hook 實際用的那支。"""
    return fix.replace("<hook 用的 python>", f'"{hook_python()}"')


def probe_package(module: str) -> Callable[[], Tuple[bool, str]]:
    def probe() -> Tuple[bool, str]:
        code = f"import importlib.util, sys; sys.exit(importlib.util.find_spec('{module}') is None)"
        found = run([hook_python(), "-c", code], check=False, timeout=60).returncode == 0
        return found, f"已安裝（{hook_python()}）" if found else f"{hook_python()} 找不到這個套件"
    return probe


def probe_codex() -> Tuple[bool, str]:
    exe = shutil.which("codex")
    return bool(exe), exe or "找不到 codex"


# (名稱, 探測函式, 缺了少什麼, 補裝方式, 是否必要)
PROBES = [
    ("Python ≥ 3.10", probe_python, "所有 hook 與工具都跑不起來，記憶系統整個不啟動", "安裝 Python 3.10 以上", True),
    ("Git", probe_git, "無法安裝與升級，記憶也不會同步到版控", "安裝 Git（Windows：Git for Windows）", True),
    ("bash", probe_bash, "個人啟動檔 USER.md 不會自動生成，WebFetch 防護 hook 不會執行",
     "Windows 安裝 Git for Windows（內含 Git Bash）", False),
    ("Node.js ≥ 18", probe_node, "MCP 工具（atom_write、memory_search 等）與 Dashboard 網頁不可用；hook 與記憶注入照常",
     "安裝 Node.js LTS", False),
    ("Ollama daemon", probe_ollama, "本機向量嵌入與自動萃取不可用；關鍵字檢索與手動寫記憶照常",
     "安裝 Ollama 並啟動；或在 workflow/config.json 設遠端 backend", False),
    ("模型 qwen3-embedding", probe_model("qwen3-embedding"), "向量嵌入改走 sentence-transformers，再沒有就只剩關鍵字檢索",
     "ollama pull qwen3-embedding", False),
    ("模型 qwen3:1.7b", probe_model("qwen3:1.7b"), "本機輕量判斷（決策快篩、失敗分類）跳過",
     "ollama pull qwen3:1.7b", False),
    ("模型 gemma4:e4b", probe_model("gemma4:e4b"), "本機的對話結束自動萃取跳過（有遠端 backend 則不受影響）",
     "ollama pull gemma4:e4b", False),
    ("套件 lancedb", probe_package("lancedb"), "向量服務起不來，專案層檢索只剩關鍵字", "<hook 用的 python> -m pip install lancedb", False),
    ("套件 sentence-transformers", probe_package("sentence_transformers"), "沒有 Ollama 時就沒有本地嵌入備援",
     "<hook 用的 python> -m pip install sentence-transformers", False),
    ("Codex CLI", probe_codex, "跨廠 AI 審查改由 Claude 自己擔任，只提醒不擋收尾",
     "npm i -g @openai/codex 後 codex login", False),
]


def cmd_check() -> int:
    """安裝前自檢：每項 OK 或「缺：少什麼＋補裝指令」。"""
    blocked = False
    for name, probe, lost, fix, required in PROBES:
        ok, detail = probe()
        if ok:
            print(f"[OK] {name}：{detail}")
            continue
        blocked = blocked or required
        print(f"[缺] {name}：{detail}\n     少了：{lost}\n     補裝：{fix_hint(fix)}")
    if blocked:
        print("\n必要項目不足（Python ≥ 3.10 與 Git），補齊後才能安裝。")
        return 2
    print("\n可以安裝：python tools/install.py --apply（缺的選配項只會少功能，不會壞）。")
    return 0


# ─── --apply ────────────────────────────────────────────────────────────────

def norm_url(url: str) -> str:
    url = url.strip().replace("\\", "/").rstrip("/")
    return (url[:-4] if url.endswith(".git") else url).lower()


def origin_url(repo: Path) -> str:
    """repo 的 origin URL；沒有 → 空字串。"""
    r = git("remote", "get-url", "origin", cwd=repo, check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def read_state() -> dict:
    if not STATE_FILE.is_file():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise InstallError(f"安裝狀態檔讀不出來：{STATE_FILE}（{e}）")


def to_backup(rel: str, backup: Path, move: bool) -> None:
    """把目標內的 rel 收進備份。複製：已有備份就不覆寫；搬移：備份位置被占用即中止。
    指向檔案的 symlink 一律存它的實際內容再移除連結（相對連結搬了位置會斷）；指向目錄的 symlink 搬連結本身。"""
    src, dst = TARGET / rel, backup / rel
    file_link = src.is_symlink() and src.is_file()
    taken = os.path.lexists(dst)
    if taken and move and not file_link:
        raise InstallError(f"備份位置已有同名項目，無法再把 {src} 搬進去：{dst}")
    if taken and not file_link:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if move and not file_link:
        shutil.move(str(src), str(dst))
    elif not taken:
        # 先寫到暫存檔名再改名：複製到一半中斷，不會留下看起來像完整備份的檔
        tmp = dst.with_name(dst.name + ".install-tmp")
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
    if file_link:
        src.unlink()
        print(f"  備份（symlink 指向的檔案內容；連結本身已移除）：{rel}")
        return
    print(f"  備份（{'搬移' if move else '複製'}）：{rel}")


def backup_before_checkout(backup: Path) -> None:
    """checkout 會蓋掉或擋到的東西全部先進備份。"""
    tracked = [p for p in git("ls-files", "-z").stdout.split("\0") if p]
    ancestors = {str(a) for rel in tracked for a in PurePosixPath(rel).parents if str(a) != "."}
    # 祖先由淺到深：應該是目錄的位置卻是檔案或 symlink → 整個搬走
    for rel in sorted(ancestors, key=lambda a: a.count("/")):
        path = TARGET / rel
        if os.path.lexists(path) and (path.is_symlink() or not path.is_dir()):
            to_backup(rel, backup, move=True)
    # 應該是檔案的位置卻是目錄或 symlink → 搬走
    for rel in tracked:
        path = TARGET / rel
        if path.is_symlink() or path.is_dir():
            to_backup(rel, backup, move=True)
    # 一般檔：git 判定內容與系統版不同的才複製
    refresh = git("update-index", "-q", "--refresh", check=False)
    if refresh.returncode not in (0, 1):
        print(f"  ⚠ git update-index --refresh 異常（exit {refresh.returncode}）：{refresh.stderr.strip()}")
    differing = [p for p in git("diff-files", "--name-only", "-z").stdout.split("\0") if p]
    for rel in [*differing, *ALWAYS_BACKUP]:
        if (TARGET / rel).is_file():
            to_backup(rel, backup, move=False)


def merge_overlays(backup: Path) -> None:
    """使用者的（備份裡的原檔）疊回系統的（HEAD）；兩檔都下 skip-worktree。"""
    user_settings = read_user_json(backup / "settings.json")
    merged, dropped = merge_settings(user_settings, head_json("settings.json"), tracked_system_files())
    write_json(TARGET / "settings.json", merged)
    print_dropped(dropped)
    if user_settings is None:
        print("  settings.json：原本沒有 → 只放入系統的 hooks 與 statusLine，不帶入任何授權清單、模型或權限模式。")
        print("    想要同款授權清單見：git -C ~/.claude show HEAD:settings.json")
    else:
        print("  settings.json：系統 hooks＋你原有的其餘設定與你自己的 hook。")
    user_config = read_user_json(backup / "workflow" / "config.json")
    if user_config is not None:
        write_json(TARGET / "workflow" / "config.json", deep_merge(head_json("workflow/config.json"), user_config))
        print("  workflow/config.json：你的值優先，新鍵補系統預設。")
    for rel in OVERLAYS:
        mark_overlay(rel)


def adopt(state: dict) -> Path:
    """接管非 git 的 ~/.claude；依狀態檔的階段從斷點續跑。回備份目錄。"""
    if state.get("phase") in (None, "adopting"):
        # 這個階段目標裡還是使用者的原檔：覆蓋檔讀不懂就在任何改動之前中止
        for rel in OVERLAYS:
            read_user_json(TARGET / rel)
        head = git("rev-parse", "--abbrev-ref", "HEAD", cwd=SOURCE).stdout.strip()
        branch = state.get("branch") or ("main" if head == "HEAD" else head)
        git("init", "-b", branch)
        backup_dir = state.get("backup_dir") or str(TARGET / "backups" / time.strftime("install-%Y%m%d-%H%M%S"))
        state = {"phase": "adopting", "backup_dir": backup_dir, "branch": branch}
        write_json(STATE_FILE, state)
        if sys.platform == "win32":
            git("config", "core.longpaths", "true")
        url = origin_url(SOURCE)
        git("remote", "set-url" if origin_url(TARGET) else "add", "origin", url)
        print(f"從 {url} 抓取分支 {branch} …")
        git("fetch", "origin", branch)
        if git("rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}", check=False).returncode != 0:
            raise InstallError(f"fetch 之後沒有 origin/{branch}：遠端 {url} 可能沒有這個分支。")
        git("reset", "--mixed", "-q", f"origin/{branch}")
        git("branch", f"--set-upstream-to=origin/{branch}", branch)
        print(f"備份到 {backup_dir}")
        backup_before_checkout(Path(backup_dir))
        state["phase"] = "backed-up"
        write_json(STATE_FILE, state)
    backup = Path(state["backup_dir"])
    if state["phase"] == "backed-up":
        git("checkout", "--", ".")
        state["phase"] = "restored"
        write_json(STATE_FILE, state)
        print("系統檔案已就位。")
    if state["phase"] == "restored":
        print("合併覆蓋檔：")
        merge_overlays(backup)
        state = {**state, "phase": "merged", "overlay_base": git("rev-parse", "HEAD").stdout.strip()}
        write_json(STATE_FILE, state)
    return backup


def fix_interpreter() -> None:
    """跑目標樹的 fix-hook-python.py；有缺失的直譯器才 --write。"""
    report = tool("tools/fix-hook-python.py")
    if report.returncode != 0:
        raise InstallError(f"hook 直譯器檢查失敗：\n{(report.stdout + report.stderr).strip()}")
    if "[缺失]" not in report.stdout:
        print("hook 直譯器：全部存在，不改動。")
        return
    fixed = tool("tools/fix-hook-python.py", "--write")
    if fixed.returncode != 0:
        raise InstallError(f"hook 直譯器校正失敗：\n{(fixed.stdout + fixed.stderr).strip()}")
    print(f"hook 直譯器：已改用 {sys.executable}（原檔備份 settings.json.bak）。")


def post_install() -> None:
    """直譯器校正 → 個人啟動檔 → 索引檢查。後兩項失敗只告知，不中止。"""
    fix_interpreter()
    bash = resolve_bash()
    if not bash:
        print("⚠ 找不到 bash：USER.md 未生成。裝好 Git Bash 後重跑 --apply。")
    else:
        # 直接叫 usr/bin/bash.exe 時 PATH 不含它自己的工具目錄（cp、sed、whoami）
        env = {**ENV, "PATH": os.path.dirname(bash) + os.pathsep + ENV.get("PATH", "")}
        init = run([bash, str(TARGET / "hooks" / "user-init.sh")], cwd=TARGET, check=False, env=env, timeout=60)
        ok = init.returncode == 0 and (TARGET / "USER.md").is_file()
        print("個人啟動檔：USER.md、IDENTITY.md 已就緒。" if ok
              else f"⚠ 個人啟動檔生成失敗（exit {init.returncode}）：{init.stderr.strip()}")
    index = tool("tools/sync-memory-index.py", "--check")
    print("記憶索引：一致。" if index.returncode == 0
          else f"⚠ 記憶索引有差異（不影響安裝；多半是上游尚未同步，之後 --upgrade 會帶進修正）：\n{index.stderr.strip()[:600]}")


def print_apply_summary(backup: Optional[Path]) -> None:
    print("\n=== 安裝完成 ===")
    saved = sorted(p.relative_to(backup).as_posix() for p in backup.rglob("*") if p.is_file()) if backup else []
    if saved:
        print(f"你原有的檔案備份在 {backup}（{len(saved)} 個）：")
        for rel in saved[:40]:
            print(f"  {rel}")
        if len(saved) > 40:
            print(f"  …其餘 {len(saved) - 40} 個見備份目錄")
    if "CLAUDE.md" in saved:
        print(f"注意：你原本 CLAUDE.md 的內容已不再載入。要保留的部分請從備份貼進 ~/.claude/USER-{getpass.getuser()}.md。")
    print("MCP 工具會在下次啟動 Claude Code 時自動註冊。")
    missing = [(name, fix) for name, probe, _, fix, required in PROBES if not required and not probe()[0]]
    print("選配項還缺這些（缺了只少功能）：" if missing else "選配項都已具備。")
    for name, fix in missing:
        print(f"  {name}：{fix_hint(fix)}")
    print("公司共用記憶（選配）：在 Claude Code 裡說「接上公司記憶」")
    print("請重開 Claude Code，然後跑：python ~/.claude/tools/install.py --verify")


def cmd_apply() -> int:
    if not (SOURCE / ".git").exists():
        raise InstallError(f"來源 {SOURCE} 不是 git clone。請用 git clone 取得本系統後，在 clone 裡跑本腳本。")
    source_url = origin_url(SOURCE)
    if not source_url:
        raise InstallError(f"來源 {SOURCE} 沒有 origin 遠端，無法得知要從哪裡安裝與升級。")
    if not os.path.lexists(TARGET):
        TARGET.mkdir(parents=True)
        print(f"{TARGET} 不存在，已建立空目錄。")
    if not TARGET.is_dir():
        raise InstallError(f"{TARGET} 存在但不是目錄。把它移走後重跑。")
    has_git = (TARGET / ".git").exists()
    state = read_state() if has_git else {}
    if state.get("phase") == "upgrading":
        print("上次的升級沒有跑完。未做任何改動。請執行：python ~/.claude/tools/install.py --upgrade")
        return 1
    target_url = origin_url(TARGET) if has_git else ""
    # git init 之後、狀態檔寫入之前就中斷的目標：沒有 origin 也沒有任何 commit，仍屬接管
    untouched_init = has_git and not target_url and git("rev-parse", "--verify", "--quiet", "HEAD", check=False).returncode != 0
    installed = has_git and state.get("phase") in (None, "done") and not untouched_init
    same_repo = SOURCE == TARGET.resolve() or norm_url(target_url) == norm_url(source_url)
    if installed and not same_repo:
        print(f"{TARGET} 已是另一個 git repo（origin：{target_url or '無'}），不是本系統（{source_url}）。未做任何改動。\n"
              "若其實是同一個庫的不同網址（例如 ssh 與 https），把來源 clone 的 origin 改成與目標相同再重跑：\n"
              f"  git -C \"{SOURCE}\" remote set-url origin {target_url or '<目標的 origin 網址>'}")
        return 3
    backup = None
    if installed:
        print("模式：就地。這台被視為開發機或已安裝的機器，不動 settings.json 與 workflow/config.json。")
    else:
        print("模式：接管（把 ~/.claude 原地接上版控；你的檔案先備份）。")
        backup = adopt(state)
    post_install()
    if not installed:
        write_json(STATE_FILE, {**read_state(), "phase": "done"})
    print_apply_summary(backup)
    return 0


# ─── --upgrade ──────────────────────────────────────────────────────────────

def restore_overlays(marked: List[str], saved_dir: Path) -> bool:
    """升級沒跑完的收拾：中止進行中的 rebase，把存檔寫回原位並重新下標記。回是否全部還原。"""
    git_dir = TARGET / ".git"
    if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
        aborted = git("rebase", "--abort", check=False)
        print("  已中止 rebase。" if aborted.returncode == 0 else f"  ⚠ git rebase --abort 失敗：{aborted.stderr.strip()}")
    restored = True
    for rel in marked:
        try:
            shutil.copy2(saved_dir / rel, TARGET / rel)
        except OSError as e:
            print(f"  ⚠ {rel} 還原失敗（{e}）；你的版本仍在 {saved_dir / rel}")
            restored = False
            continue
        mark_overlay(rel, check=False)
        print(f"  已還原 {rel}")
    return restored


def remerge_overlay(rel: str, mine: dict, base: dict) -> dict:
    """升級後的覆蓋檔內容：mine＝使用者升級前的檔，base＝當初合併所依據的系統版，新的系統版取 HEAD。"""
    new = head_json(rel)
    if rel == "settings.json":
        merged, dropped = merge_settings(mine, new, tracked_system_files())
        print_dropped(dropped)
        return merged
    changed, conflicts = drop_type_conflicts(changed_keys(mine, base), base, new)
    for key_path in conflicts:
        print(f"    ⚠ {rel} 的 {key_path}：新版已不是物件，你在它底下改過的值不再適用，改用新版的值。")
    return deep_merge(new, changed)


def cmd_upgrade() -> int:
    git_dir = TARGET / ".git"
    if not git_dir.exists():
        raise InstallError(f"{TARGET} 不是 git repo，尚未安裝。請先跑 --apply。")
    state = read_state()
    if state.get("phase") not in (None, "done", "upgrading"):
        raise InstallError("安裝還沒跑完。先跑 --apply 把安裝做完，再升級。")
    if state.get("phase") == "upgrading":
        print("上次的升級沒有跑完，先把覆蓋檔還原成升級前的樣子：")
        if not restore_overlays(state["marked"], Path(state["saved_dir"])):
            raise InstallError("覆蓋檔沒有全部還原。排除上面列的原因後重跑 --upgrade。")
        state = {k: v for k, v in state.items() if k not in ("saved_dir", "marked")}
        state["phase"] = "done"
        write_json(STATE_FILE, state)
    in_progress = [n for n in ("rebase-merge", "rebase-apply", "MERGE_HEAD") if (git_dir / n).exists()]
    if in_progress or git("ls-files", "-u", "-z").stdout:
        raise InstallError("repo 有未解的衝突或進行中的 rebase／merge。先處理完（git status 會說明怎麼做）再升級。")
    dirty = git("-c", "core.quotepath=false", "status", "--porcelain", "--untracked-files=no").stdout.rstrip()
    if dirty:
        raise InstallError("有還沒提交的修改，未做任何改動：\n" + dirty + "\n"
                           "記憶檔（memory/ 底下）通常會在關閉 Claude Code 對話後自動提交：請關掉其他對話，稍候再試。\n"
                           "其他檔請先自行處理（提交，或用 git restore 放棄修改）。")
    listing = git("ls-files", "-v", "-z", "--", *OVERLAYS).stdout.split("\0")
    marked = [line[2:] for line in listing if line.startswith("S ")]
    # 取消標記之前先確認現檔讀得懂、存好一份，並把還原所需的資訊寫進狀態檔
    mine = {rel: read_user_json(TARGET / rel) or {} for rel in marked}
    base_rev = state.get("overlay_base") or "HEAD"
    base = {rel: head_json(rel, base_rev) for rel in marked}
    saved_dir = TARGET / "backups" / time.strftime("upgrade-%Y%m%d-%H%M%S")
    for rel in marked:
        (saved_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TARGET / rel, saved_dir / rel)
    if marked:
        print(f"覆蓋檔現況已存到 {saved_dir}")
        write_json(STATE_FILE, {**state, "phase": "upgrading", "saved_dir": str(saved_dir), "marked": marked})
    upgraded = False
    try:
        for rel in marked:
            git("update-index", "--no-skip-worktree", "--", rel)
            git("checkout", "--", rel)
        print("git pull --rebase …")
        git("pull", "--rebase")
        for rel in marked:
            write_json(TARGET / rel, remerge_overlay(rel, mine[rel], base[rel]))
            mark_overlay(rel)
            print(f"  已重新合併 {rel}")
        upgraded = True
    finally:
        if not upgraded:
            print("升級失敗，還原覆蓋檔：")
            restored = restore_overlays(marked, saved_dir)
        # 還原不完整時狀態檔留在 upgrading，下次 --upgrade 會再還原一次
        if marked and (upgraded or restored):
            head = git("rev-parse", "HEAD", check=False).stdout.strip()
            write_json(STATE_FILE, {**state, "phase": "done", "overlay_base": head if upgraded else base_rev})
    try:
        fix_interpreter()
    except InstallError as e:
        print(f"\n升級已完成，但 hook 直譯器校正失敗：{e}", file=sys.stderr)
        return 1
    print("升級完成。請重開 Claude Code。")
    return 0


# ─── --verify ───────────────────────────────────────────────────────────────

def verify_version() -> Tuple[str, str]:
    try:
        ver = json.loads((TARGET / "version.json").read_text(encoding="utf-8"))
        return "PASS", f"原子記憶 {ver['atom_memory']}／Guardian {ver['guardian']}"
    except (OSError, ValueError, KeyError) as e:
        return "FAIL", f"version.json 讀不到（{e}）→ 重跑 python tools/install.py --apply"


def verify_repo() -> Tuple[str, str]:
    if not (TARGET / ".git").exists():
        return "FAIL", "~/.claude 不是 git repo，無法升級與同步 → 重跑 python tools/install.py --apply"
    upstream = git("rev-parse", "--abbrev-ref", "@{u}", check=False)
    if upstream.returncode != 0:
        return "FAIL", "目前分支沒有 upstream → git -C ~/.claude branch --set-upstream-to=origin/<分支>"
    return "PASS", f"upstream {upstream.stdout.strip()}"


def verify_interpreter() -> Tuple[str, str]:
    report = tool("tools/fix-hook-python.py")
    slots = report.stdout.count("[OK ]")
    if report.returncode != 0 or "[缺失]" in report.stdout or not slots:
        return "FAIL", "settings.json 的 hook 直譯器有缺 → python ~/.claude/tools/fix-hook-python.py --write"
    return "PASS", f"{slots} 處指令的直譯器都存在"


def verify_hook_fired() -> Tuple[str, str]:
    """hook 真的在 Claude Code 裡跑過的證據：安裝（或升級）之後、且在一天內，有 session 狀態檔。
    只讀檔，不實跑 hook（實跑 SessionStart 會啟動背景記憶同步與向量服務）。"""
    since = time.time() - 86400
    if STATE_FILE.is_file():
        since = max(since, STATE_FILE.stat().st_mtime)
    recent = [p for p in (TARGET / "workflow").glob("state-*.json") if p.stat().st_mtime > since]
    if not recent:
        return "FAIL", ("安裝或升級之後（最多看最近一天）沒有 hook 啟動紀錄 → 重開 Claude Code 後在裡面重跑本驗證；"
                        "仍失敗跑 python ~/.claude/tools/fix-hook-python.py 看直譯器")
    return "PASS", f"安裝或升級之後（最多看最近一天）有 {len(recent)} 個 session 啟動過 hook"


def verify_boot_files() -> Tuple[str, str]:
    missing = [n for n in ("IDENTITY.md", "USER.md") if not (TARGET / n).is_file()]
    if missing:
        return "FAIL", f"缺 {'、'.join(missing)} → 重跑 python tools/install.py --apply"
    return "PASS", "IDENTITY.md、USER.md 都在"


def verify_index() -> Tuple[str, str]:
    if tool("tools/sync-memory-index.py", "--check").returncode != 0:
        return "DEGRADED", ("記憶索引或文件計數與 atom 不一致，部分記憶可能不會被列出；多半是上游尚未同步，"
                            "先 python ~/.claude/tools/install.py --upgrade，仍在再看 python ~/.claude/tools/sync-memory-index.py --check 的明細")
    return "PASS", "記憶索引一致"


def verify_search() -> Tuple[str, str]:
    found = tool("tools/memory-search.py", "git commit", "--no-vector", "--json")
    try:
        hits = len(json.loads(found.stdout).get("results") or [])
    except ValueError:
        return "FAIL", f"memory-search.py 沒有回 JSON（exit {found.returncode}）：{found.stderr.strip()[:300]}"
    if not hits:
        return "FAIL", "memory-search.py 查「git commit」沒有任何結果 → 檢查 memory/ 是否完整（git -C ~/.claude status）"
    return "PASS", f"查「git commit」回 {hits} 筆"


def verify_mcp() -> Tuple[str, str]:
    try:
        servers = json.loads((HOME / ".claude.json").read_text(encoding="utf-8")).get("mcpServers") or {}
    except (OSError, ValueError):
        servers = {}
    if "workflow-guardian" not in servers:
        return "DEGRADED", "MCP 尚未註冊，atom_write 等工具暫不可用；重開 Claude Code 後自動註冊"
    return "PASS", "workflow-guardian 已註冊"


def verify_merge_driver() -> Tuple[str, str]:
    if tool("tools/merge-atom-index.py", "--status").returncode != 0:
        return "DEGRADED", "索引合併驅動未裝，多機同時新增記憶時索引檔會衝突；第一次 pull 前會自動裝，或手動 python ~/.claude/tools/merge-atom-index.py --install"
    return "PASS", "已安裝"


def org_root() -> Optional[str]:
    """公司層接上的根目錄；未接上 → None。"""
    try:
        local = json.loads((TARGET / "workflow" / "org-memory.local.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        print(f"  ⚠ workflow/org-memory.local.json 讀不出來，視為未接上：{e}")
        return None
    roots = local.get("roots") or []
    if not local.get("enabled") or len(roots) != 1:
        return None
    root = str(roots[0].get("root", ""))
    return root if (Path(root) / ".claude" / "memory").is_dir() else None


VERIFY_ITEMS = [
    ("版本檔", verify_version),
    ("版控", verify_repo),
    ("hook 直譯器", verify_interpreter),
    ("hook 啟動紀錄", verify_hook_fired),
    ("個人啟動檔", verify_boot_files),
    ("記憶索引", verify_index),
    ("記憶檢索", verify_search),
    ("MCP 註冊", verify_mcp),
    ("索引合併驅動", verify_merge_driver),
]


def cmd_verify() -> int:
    """安裝後驗證：每項 PASS／DEGRADED（少了什麼）／FAIL（怎麼修），末尾印三層現況。"""
    if not TARGET.is_dir():
        print(f"FAIL  {TARGET} 不存在，尚未安裝。")
        return 1
    results = [(name, *check()) for name, check in VERIFY_ITEMS]
    for name, probe, lost, fix, required in PROBES:
        ok, detail = probe()
        missing_level = "FAIL" if required else "DEGRADED"
        results.append((name, "PASS" if ok else missing_level, detail if ok else f"{lost}；補裝：{fix_hint(fix)}"))
    for name, level, detail in results:
        print(f"{level:<8} {name}：{detail}")
    org = org_root()
    print(f"INFO     公司層：{'已接上 ' + org if org else '未接上（選配；在 Claude Code 裡說「接上公司記憶」）'}")
    try:
        atoms = len(json.loads((TARGET / "memory" / "_atom_index.json").read_text(encoding="utf-8")).get("atoms") or [])
    except (OSError, ValueError) as e:
        atoms = f"讀不到（{e}）"
    print("\n記憶三層現況：")
    print(f"  根層   {TARGET / 'memory'}：{atoms} 顆 atom")
    print(f"  公司層 {org or '未接上'}")
    print("  專案層 各專案的 .claude/memory/，隨專案版控，不需安裝")
    fails = sum(1 for _, level, _ in results if level == "FAIL")
    degraded = sum(1 for _, level, _ in results if level == "DEGRADED")
    print(f"\n結果：{fails} 項 FAIL、{degraded} 項 DEGRADED（DEGRADED 只是少功能，不影響使用）。")
    return 1 if fails else 0


# ─── CLI ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="原子記憶系統安裝器。目標一律是 ~/.claude；來源是本腳本所在的 git clone。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit code：\n"
            "  --check    0＝可安裝；2＝Python < 3.10 或缺 git\n"
            "  --apply    0＝完成；3＝~/.claude 是別的 git repo（零改動）；1＝其他失敗\n"
            "  --upgrade  0＝完成；1＝失敗（覆蓋檔已還原），或升級完成但 hook 直譯器校正失敗\n"
            "  --verify   0＝沒有 FAIL；1＝有 FAIL\n\n"
            "--apply 的兩種模式：\n"
            "  接管：~/.claude 不是 git repo（不存在則先建立空目錄）。你的檔案先備份到\n"
            "    ~/.claude/backups/install-<時間戳>/，再換成系統版本；settings.json 與 workflow/config.json\n"
            "    把你的值疊回去並下 skip-worktree 標記（原本沒有 settings.json → 只含系統的 hooks 與 statusLine）。\n"
            "    這兩個檔若不是合法 JSON，會在任何改動之前中止。\n"
            "    進度記在 ~/.claude/.git/atom-install-state.json，中斷後重跑會接續。\n"
            "  就地：~/.claude 已是本系統的 clone（開發機，或已安裝過的機器）。不動上述兩個檔。\n"
            "--upgrade 會把覆蓋檔現況存到 ~/.claude/backups/upgrade-<時間戳>/ 再 pull 與重新合併；\n"
            "  有還沒提交的修改時不動手；被中斷的升級在下次 --upgrade 開頭自動還原後重來。"
        ),
    )
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="安裝前自檢（唯讀）：列出每項依賴有沒有、缺了少什麼、怎麼補")
    mode.add_argument("--apply", action="store_true", help="安裝到 ~/.claude，可重跑")
    mode.add_argument("--upgrade", action="store_true", help="已安裝機器升級：pull 新版並重新合併覆蓋檔")
    mode.add_argument("--verify", action="store_true", help="安裝後驗證（PASS／DEGRADED／FAIL），並印三層記憶現況；唯讀，重開 Claude Code 後在裡面跑")
    args = ap.parse_args()

    print(f"目標目錄：{TARGET}\n來源目錄：{SOURCE}\n")
    command = cmd_check if args.check else cmd_apply if args.apply else cmd_upgrade if args.upgrade else cmd_verify
    try:
        return command()
    except InstallError as e:
        print(f"\n失敗：{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
