#!/usr/bin/env python
"""auto_continue.py — Auto-Handoff Phase 4 外部編排 watcher（PoC，獨立於 hook）

⚠️ 實驗性質：超出 CC hook 能力邊界的「全自動 spawn 新 session」最後一哩。
   非正式上線元件；預設安全（dry-run 友善 + 四道 guard）。設計來源：
   plans/wise-wobbling-gem.md line 50-58（可行性邊界）+ 81-82（Phase 4 範圍）。

機制（已實證 claude -p 支援 skill /continue，見檔尾「實證紀錄」）：
   監看 resolve_staging_dir(cwd) 的 next-phase*.md
   → 偵測到穩定 stub（且當前無子 session 在跑）
   → 起 headless `claude -p "/continue"`（讀+刪 stub、執行續接、完工再寫新 stub）
   → 子 session 結束 → 下輪 poll 偵測到新 stub → 再 spawn → 遞迴
   每輪同步阻塞執行（序列化），天然保證「當前 session 結束」才接下一棒。

四道 guard（plan line 55）：
   1. max_consecutive_spawns  連續 spawn 數硬上限
   2. budget_usd             累計成本（從子 session JSON total_cost_usd 加總）上限
   3. confirm_every_n        每 N 次人工確認點（TTY input 或 flag 檔，detached 也可用）
   4. kill_switch            kill switch flag 檔（每輪 + spawn 前檢查，命中即停）
   附帶：single-stub 不變式（多 stub 時 headless /continue 會選單卡死 → 停手交人工）

可測試性：spawn / sleep / now / confirm 全可注入，verify/ 下 pytest 以模擬資料驗 guard。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

CLAUDE_DIR = Path.home() / ".claude"
TOOL_DIR = Path(__file__).resolve().parent

# ─── 預設組態 ─────────────────────────────────────────────────────────────────
DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "claude_bin": None,            # None → 自動偵測（VSCode 擴充套件最新版優先）
    "permission_mode": "bypassPermissions",  # headless 自主性需非互動授權；風險見 README
    "model": None,                 # None → 用子 session 預設模型
    "extra_args": [],              # 額外 claude flags（如 ["--dangerously-skip-permissions"]）
    "poll_interval_sec": 5.0,
    "idle_timeout_sec": 60.0,      # 無新 stub 超過此秒數 → 視為鏈結束，正常退出
    "stub_stable_sec": 3.0,        # stub mtime 須穩定此秒數才處理（避免讀到半寫檔）
    "spawn_timeout_sec": 1800.0,   # 單個子 session 上限（一個續接 phase 可能很久）
    "max_consecutive_spawns": 5,   # guard 1
    "budget_usd": 5.0,             # guard 2
    "confirm_every_n": 0,          # guard 3（0 = 關閉）
    "confirm_timeout_sec": 300.0,
    "kill_switch": "STOP",         # guard 4（watch dir 下檔名，或絕對路徑）
    "watch_dir": None,             # None → resolve_staging_dir(cwd)
    "dry_run": False,
}

# ─── 與 hook 對齊的 staging 解析（單一來源：wg_core.resolve_staging_dir）──────────
sys.path.insert(0, str(CLAUDE_DIR / "hooks"))
try:
    from wg_core import resolve_staging_dir as _resolve_staging  # type: ignore
except Exception:  # pragma: no cover - fallback 僅在 hook 缺失時走
    _resolve_staging = None


def resolve_watch_dir(cwd: str, config: Dict[str, Any]) -> Path:
    """決定要監看的 staging 目錄。優先 config.watch_dir → wg_core → 內建 fallback。"""
    if config.get("watch_dir"):
        return Path(config["watch_dir"]).expanduser()
    if _resolve_staging is not None:
        return Path(_resolve_staging(cwd))
    # fallback：無 hook 可用時的最小複製（核心層）
    return CLAUDE_DIR / "memory" / "_staging"


# ─── claude binary 偵測（依 atom cc-能力查證：擴充套件版常遠新於 native）──────────
def _parse_ver(name: str) -> tuple:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", name)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def detect_claude_bin() -> Optional[str]:
    """找實跑 claude binary。順序：PATH → VSCode 擴充套件（最新版）→ native versions。"""
    on_path = shutil.which("claude")
    if on_path:
        return on_path
    exe = "claude.exe" if sys.platform == "win32" else "claude"
    ext_root = Path.home() / ".vscode" / "extensions"
    cands: List[Path] = []
    if ext_root.is_dir():
        cands += list(ext_root.glob(f"anthropic.claude-code-*/resources/native-binary/{exe}"))
    if cands:
        cands.sort(key=lambda p: _parse_ver(p.parts[-4]), reverse=True)
        return str(cands[0])
    native = Path.home() / ".local" / "share" / "claude" / "versions"
    if native.is_dir():
        vers = sorted(native.glob(f"*/{exe}"), key=lambda p: _parse_ver(p.parent.name), reverse=True)
        if vers:
            return str(vers[0])
    return None


# ─── stub 偵測 ────────────────────────────────────────────────────────────────
def list_stubs(watch_dir: Path) -> List[Path]:
    if not watch_dir.is_dir():
        return []
    return sorted(watch_dir.glob("next-phase*.md"))


def find_stub(watch_dir: Path, stable_sec: float, now_fn: Callable[[], float]) -> Optional[Path]:
    """回傳最舊且 mtime 已穩定的 stub；無則 None。"""
    for s in list_stubs(watch_dir):
        try:
            if now_fn() - s.stat().st_mtime >= stable_sec:
                return s
        except OSError:
            continue
    return None


# ─── guards ──────────────────────────────────────────────────────────────────
def kill_switch_path(watch_dir: Path, config: Dict[str, Any]) -> Path:
    ks = config["kill_switch"]
    p = Path(ks).expanduser()
    return p if p.is_absolute() else (watch_dir / ks)


def check_guards(state: Dict[str, Any], config: Dict[str, Any], watch_dir: Path) -> Optional[str]:
    """spawn 前硬性 guard 檢查。回傳停手原因字串，None = 放行。"""
    ks = kill_switch_path(watch_dir, config)
    if ks.exists():
        return f"kill switch 命中：{ks}"
    if state["spawns"] >= config["max_consecutive_spawns"]:
        return f"達 max_consecutive_spawns={config['max_consecutive_spawns']}"
    if state["cost_usd"] >= config["budget_usd"]:
        return f"達 budget_usd={config['budget_usd']}（已花 ${state['cost_usd']:.4f}）"
    return None


def need_confirm(state: Dict[str, Any], config: Dict[str, Any]) -> bool:
    n = config["confirm_every_n"]
    return n > 0 and state["spawns"] > 0 and state["spawns"] % n == 0


def _default_confirm(state, watch_dir, config, sleep_fn, now_fn, log) -> bool:
    """人工確認點。TTY → input()；detached → 等 confirm.ok flag 檔（kill switch 可中止）。"""
    msg = f"已 spawn {state['spawns']} 次、花 ${state['cost_usd']:.4f}"
    if sys.stdin and sys.stdin.isatty():
        try:
            return input(f"[confirm] {msg}。續跑？[y/N] ").strip().lower() in ("y", "yes")
        except EOFError:
            return False
    ok = watch_dir / "confirm.ok"
    ks = kill_switch_path(watch_dir, config)
    log(f"[confirm] {msg}。建立 {ok} 續跑，或 {ks} 停手（等 {config['confirm_timeout_sec']:.0f}s）")
    deadline = now_fn() + config["confirm_timeout_sec"]
    while now_fn() < deadline:
        if ks.exists():
            return False
        if ok.exists():
            try:
                ok.unlink()
            except OSError:
                pass
            return True
        sleep_fn(config["poll_interval_sec"])
    return False


# ─── spawn ───────────────────────────────────────────────────────────────────
def parse_result_json(stdout: str) -> Dict[str, Any]:
    """從 stdout 末尾找出 type==result 的 JSON 物件（前面可能有 warning 行）。"""
    for line in reversed([ln for ln in stdout.splitlines() if ln.strip()]):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("type") == "result":
            return obj
    return {}


def spawn_continue(target_cwd: str, config: Dict[str, Any], log: Callable[[str], None]) -> Dict[str, Any]:
    """起 headless `claude -p "/continue"`，回 {exit, data, stdout, stderr}。

    stdin 接 DEVNULL（避免 'no stdin data received in 3s' 每次卡 3 秒，實證見檔尾）。
    """
    cmd = [config["claude_bin"], "-p", "/continue", "--output-format", "json"]
    if config.get("permission_mode"):
        cmd += ["--permission-mode", config["permission_mode"]]
    if config.get("model"):
        cmd += ["--model", config["model"]]
    cmd += list(config.get("extra_args") or [])
    try:
        proc = subprocess.run(
            cmd, cwd=target_cwd, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=config["spawn_timeout_sec"],
        )
        return {"exit": proc.returncode, "data": parse_result_json(proc.stdout),
                "stdout": proc.stdout, "stderr": proc.stderr}
    except subprocess.TimeoutExpired as e:
        log(f"  ! 子 session 逾時（>{config['spawn_timeout_sec']:.0f}s）")
        return {"exit": -1, "data": {"is_error": True, "subtype": "timeout"},
                "stdout": e.stdout or "", "stderr": e.stderr or ""}


# ─── 主迴圈 ───────────────────────────────────────────────────────────────────
def _finish(state: Dict[str, Any], reason: str, log: Callable[[str], None]) -> Dict[str, Any]:
    state["stop_reason"] = reason
    log("─" * 60)
    log(f"[stop] {reason}")
    log(f"  spawns={state['spawns']}  cost=${state['cost_usd']:.4f}  errors={state['errors']}")
    return state


def run_watch_loop(
    config: Dict[str, Any],
    target_cwd: str,
    *,
    spawn_fn: Callable[..., Dict[str, Any]] = spawn_continue,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.time,
    confirm_fn: Optional[Callable[..., bool]] = None,
    log: Callable[[str], None] = print,
    max_iter: Optional[int] = None,
) -> Dict[str, Any]:
    """watcher 主迴圈。所有外部依賴可注入 → verify/ 以模擬資料測 guard。"""
    watch_dir = resolve_watch_dir(target_cwd, config)
    state: Dict[str, Any] = {"spawns": 0, "cost_usd": 0.0, "errors": 0,
                             "history": [], "stop_reason": None}
    confirm = confirm_fn or _default_confirm
    idle_since = now_fn()
    it = 0
    while True:
        it += 1
        if max_iter is not None and it > max_iter:
            return _finish(state, "max_iter 達到（測試）", log)

        # guard 4：kill switch 每輪先檢查
        ks = kill_switch_path(watch_dir, config)
        if ks.exists():
            return _finish(state, f"kill switch 命中：{ks}", log)

        stub = find_stub(watch_dir, config["stub_stable_sec"], now_fn)
        if stub is None:
            if now_fn() - idle_since >= config["idle_timeout_sec"]:
                return _finish(state, "idle 逾時 — 無新 stub，鏈結束", log)
            sleep_fn(config["poll_interval_sec"])
            continue

        # single-stub 不變式：多 stub 時 headless /continue 會選單卡死
        stubs = list_stubs(watch_dir)
        if len(stubs) > 1:
            return _finish(state, f"歧義：{len(stubs)} 個 stub 並存"
                                  f"（headless /continue 會選單卡死）→ 交人工處理", log)

        # guard 1+2+4：spawn 前硬檢查
        reason = check_guards(state, config, watch_dir)
        if reason:
            return _finish(state, reason, log)

        # guard 3：人工確認點
        if need_confirm(state, config):
            if not confirm(state, watch_dir, config, sleep_fn, now_fn, log):
                return _finish(state, "人工確認未通過 / 逾時", log)

        # dry-run：偵測到即報告、不 spawn、不無限迴圈
        if config.get("dry_run"):
            log(f"[dry-run] 將對 {stub.name} 起 /continue（cwd={target_cwd}）")
            return _finish(state, "dry-run：已偵測 stub，未實際 spawn", log)

        # ─── SPAWN ───
        log(f"[spawn #{state['spawns'] + 1}] /continue  stub={stub.name}  cwd={target_cwd}")
        res = spawn_fn(target_cwd, config, log)
        state["spawns"] += 1
        data = res.get("data") or {}
        cost = float(data.get("total_cost_usd") or 0.0)
        state["cost_usd"] += cost
        is_err = bool(data.get("is_error")) or res.get("exit", 0) != 0
        if is_err:
            state["errors"] += 1
        state["history"].append({
            "stub": stub.name, "session_id": data.get("session_id"),
            "cost_usd": cost, "num_turns": data.get("num_turns"),
            "is_error": is_err, "exit": res.get("exit"),
        })
        snippet = (data.get("result") or "").replace("\n", " ")[:120]
        log(f"  → done  cost=${cost:.4f}  total=${state['cost_usd']:.4f}  "
            f"turns={data.get('num_turns')}  err={is_err}")
        if snippet:
            log(f"    result: {snippet}")

        if is_err:
            return _finish(state, f"子 session 出錯（exit={res.get('exit')}, "
                                  f"is_error={data.get('is_error')}）", log)

        idle_since = now_fn()
        sleep_fn(config["poll_interval_sec"])


# ─── 組態載入 / CLI ───────────────────────────────────────────────────────────
def load_config(path: Optional[str], overrides: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    if path:
        p = Path(path).expanduser()
        if p.exists():
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
    for k, v in overrides.items():
        if v is not None:
            cfg[k] = v
    if not cfg.get("claude_bin"):
        cfg["claude_bin"] = detect_claude_bin()
    return cfg


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Auto-Handoff Phase 4 watcher（PoC，實驗性）：監看 staging next-phase*.md "
                    "→ headless `claude -p /continue` 自動接續 → 遞迴。")
    ap.add_argument("--cwd", default=None, help="目標專案根（決定 staging 解析與子 session cwd）；預設當前目錄")
    ap.add_argument("--config", default=None, help="JSON 組態檔路徑")
    ap.add_argument("--watch-dir", default=None, help="直接指定監看目錄（覆蓋 staging 解析）")
    ap.add_argument("--dry-run", action="store_true", help="只偵測不 spawn（安全試跑）")
    ap.add_argument("--max-spawns", type=int, default=None, help="guard 1：連續 spawn 上限")
    ap.add_argument("--budget-usd", type=float, default=None, help="guard 2：累計成本上限（USD）")
    ap.add_argument("--confirm-every", type=int, default=None, help="guard 3：每 N 次人工確認（0=關）")
    ap.add_argument("--kill-switch", default=None, help="guard 4：kill switch flag 檔名/路徑")
    ap.add_argument("--poll", type=float, default=None, help="poll 間隔秒")
    ap.add_argument("--idle-timeout", type=float, default=None, help="無新 stub 退出秒數")
    ap.add_argument("--model", default=None, help="子 session 模型")
    ap.add_argument("--bin", default=None, help="claude binary 路徑（預設自動偵測）")
    ap.add_argument("--permission-mode", default=None, help="子 session 權限模式（預設 bypassPermissions）")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    import os
    target_cwd = args.cwd or os.getcwd()
    overrides = {
        "watch_dir": args.watch_dir,
        "dry_run": True if args.dry_run else None,
        "max_consecutive_spawns": args.max_spawns,
        "budget_usd": args.budget_usd,
        "confirm_every_n": args.confirm_every,
        "kill_switch": args.kill_switch,
        "poll_interval_sec": args.poll,
        "idle_timeout_sec": args.idle_timeout,
        "model": args.model,
        "claude_bin": args.bin,
        "permission_mode": args.permission_mode,
    }
    config = load_config(args.config, overrides)

    if not config.get("enabled"):
        print("[auto-continue] config.enabled=false，退出。")
        return 0
    if not config.get("claude_bin"):
        print("[auto-continue] 找不到 claude binary（--bin 指定或裝 VSCode 擴充套件）。", file=sys.stderr)
        return 2

    watch_dir = resolve_watch_dir(target_cwd, config)
    print("=" * 60)
    print("Auto-Handoff Phase 4 watcher（PoC · 實驗性 · 非正式上線）")
    print(f"  時間      : {datetime.now().isoformat(timespec='seconds')}")
    print(f"  目標 cwd  : {target_cwd}")
    print(f"  監看目錄  : {watch_dir}")
    print(f"  claude    : {config['claude_bin']}")
    print(f"  權限模式  : {config['permission_mode']}  | 模型: {config['model'] or '(預設)'}")
    print(f"  guards    : max_spawns={config['max_consecutive_spawns']} "
          f"budget=${config['budget_usd']} confirm_every={config['confirm_every_n']} "
          f"kill_switch={kill_switch_path(watch_dir, config)}")
    print(f"  模式      : {'DRY-RUN（不 spawn）' if config['dry_run'] else 'LIVE'}")
    print("=" * 60)

    try:
        state = run_watch_loop(config, target_cwd)
    except KeyboardInterrupt:
        print("\n[auto-continue] 收到 Ctrl+C，停手。")
        return 130
    return 1 if state.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())


# ─── 實證紀錄（依 atom cc-能力查證反編譯實跑-binary，不憑記憶斷言）──────────────
# 環境：VSCode 擴充套件 claude.exe 2.1.169（native install 停在 2.1.37，過舊）。
# 查證一（binary 字串表）：disable-slash-commands×8 / slashCommand×18 /
#   local-command-stdout×51 / commandName×118 → headless slash-command 處理健全。
#   --help：`-p,--print` 存在；`--disable-slash-commands` 註「Disable all skills」
#   （= slash 即 skills、預設開）；`--bare` 註明「Skills still resolve via /skill-name」。
# 查證二（實跑，隔離空目錄 C:\Temp\cc-skill-probe）：
#   claude -p "/continue" --output-format json --dangerously-skip-permissions
#   → is_error:false, terminal_reason:"completed", exit 0, num_turns:3,
#     result 為 /continue skill 在 0 stub 時的原文「_staging/ 下沒有待續任務…」，
#     且回報掃了 skill 文件記載的兩條路徑 → 證實 skill 邏輯實際執行（非 prompt 透傳）。
#   total_cost_usd≈0.276；觀察到 "no stdin data received in 3s" → 故 spawn 時接 DEVNULL。
# 結論：claude -p headless 支援 skill(/continue)，Phase 4 watcher 可行。
