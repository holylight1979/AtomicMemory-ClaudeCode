#!/usr/bin/env python3
"""codex-call.py：把提示詞交給 `codex exec`，回答案或明確失敗。本系統叫 Codex 的單一入口（驗收裁判 assessor 也走這支）。

做什麼：
  執行檔照 judge_backend.resolve_codex_bin 找（設定 codex_binary → PATH）；必帶 --ephemeral、--skip-git-repo-check；
  提示詞寫進暫存檔再當 stdin 餵（讀完就 EOF，不接呼叫端的 stdin）；答案取 -o 檔，-o 檔空的才退 stdout；
  stderr 剝掉 codex 回聲的那份提示詞（提示詞裡的錯誤字樣不能被當成 codex 自己的錯）。
  指定沙箱（--sandbox）時帶 -s <模式>，Windows 另帶 -c windows.sandbox="unelevated"（沒帶的話沙箱裡 spawn 不起 shell：1385）；
  沒指定就不帶，照 ~/.codex/config.toml 的預設。設定的 codex_extra_args 原樣附在最後。
  模型名照 ~/.codex/models_cache.json 精確比對（lib/codex_models，經 judge_backend.resolve_model_slug），查不到就不跑。
  逾時 kill；跑不起來、逾時、exit 非 0、沒有回答 → exit 1 並在 stderr 印原因，絕不報成功。
怎麼跑：
  python tools/codex-call.py --prompt "問題" [--cwd 目錄] [--model gpt-6-astra] [--timeout 300] [--sandbox read-only]
  python tools/codex-call.py --prompt-file 提示詞.md          # --prompt-file - 從 stdin 讀
  成功：stdout 印答案、exit 0。完整參數以 --help 為準。
  程式內用：run_codex(prompt, config=..., cwd=..., model=..., timeout_s=...) → CodexResult（ok／text／stderr／reason／returncode）。
設定：workflow/config.json（再蓋 config.local.json）的 codex_companion 段：codex_binary、codex_extra_args、model（--model 沒給時用它）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
COMPANION_DIR = CODE_DIR / "tools" / "codex-companion"
if str(COMPANION_DIR) not in sys.path:
    sys.path.append(str(COMPANION_DIR))   # 排在後面：companion 的 prompts.py 不蓋掉呼叫端自己的同名模組
import judge_backend  # noqa: E402
from lib.config_local import merge_local  # noqa: E402
from lib.project_root import claude_data_dir  # noqa: E402

CONFIG_PATH = claude_data_dir() / "workflow" / "config.json"
DEFAULT_TIMEOUT_S = 300
SANDBOX_MODES = ("read-only", "workspace-write", "danger-full-access")
# 無主控台的父行程（detached 的 audit.py、hook）呼叫 codex.cmd 時，不帶這個 flag 會彈出 cmd.exe 視窗
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass
class CodexResult:
    ok: bool                    # codex 跑完、exit 0、有回答
    text: str                   # 回答：-o 檔，空的退 stdout
    stderr: str                 # codex 自己的 stderr（剝掉提示詞回聲）
    reason: str                 # 沒成功的原因；成功是 ""
    returncode: Optional[int]   # None＝codex 沒跑完（找不到執行檔、逾時、例外、模型名不對）


def _log(msg: str) -> None:
    print(f"[codex-call {time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def sandbox_args(mode: Optional[str]) -> list:
    if not mode:
        return []
    args = ["-s", mode]
    if sys.platform == "win32":
        args += ["-c", 'windows.sandbox="unelevated"']
    return args


def _not_run(reason: str) -> CodexResult:
    return CodexResult(False, "", "", reason, None)


def run_codex(prompt: str, *, config: Optional[Dict[str, Any]] = None, cwd: Optional[str] = None, model: str = "",
              timeout_s: Any = DEFAULT_TIMEOUT_S, sandbox: Optional[str] = None, ignore_rules: bool = False,
              validate_model: bool = True, log: Callable[[str], None] = _log) -> CodexResult:
    """跑一次 `codex exec`。config＝codex_companion 段（codex_binary、codex_extra_args）。
    validate_model=False 時模型名不比對 models_cache，原樣交給 codex（驗收裁判沿用它一直以來的做法：名字錯由 codex 自己報、
    失敗分類接手）。"""
    config = config or {}
    if model and validate_model:
        slug, err = judge_backend.resolve_model_slug({"model": model})
        if not slug:
            return _not_run(err)
        model = slug
    codex_bin = judge_backend.resolve_codex_bin(config) or config.get("codex_binary", "codex")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8", newline="\n") as f:
        f.write(prompt)
        prompt_file = f.name
    output_file = prompt_file + ".out"

    try:
        cmd = [codex_bin, "exec"]
        if model:
            cmd += ["-m", model]
        cmd += ["--ephemeral"]
        if ignore_rules:
            cmd += ["--ignore-rules"]
        cmd += [*sandbox_args(sandbox), "--skip-git-repo-check", "-o", output_file]
        # 機器層附加旗標（例：停用這台用不到的 MCP server，免每次啟動連線重試）
        cmd += [str(a) for a in (config.get("codex_extra_args") or [])]

        log(f"Running: {' '.join(cmd[:6])}... (timeout={timeout_s}s)")
        with open(prompt_file, "r", encoding="utf-8") as pf:
            result = subprocess.run(
                cmd, stdin=pf, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=timeout_s, cwd=cwd if cwd and os.path.isdir(cwd) else None,
                env={**os.environ, "NO_COLOR": "1"}, creationflags=_NO_WINDOW,
            )
        log(f"codex exec exit code: {result.returncode}")
        stderr_text = result.stderr or ""
        if prompt.strip():   # codex 的 stderr 在 `user` 段把整份提示詞回聲一次
            stderr_text = stderr_text.replace(prompt.strip(), "", 1)
        text = ""
        if os.path.exists(output_file):
            text = Path(output_file).read_text(encoding="utf-8").strip()
        if not text:
            text = result.stdout.strip()
        if result.returncode != 0:
            return CodexResult(False, text, stderr_text, f"codex exec exit={result.returncode}", result.returncode)
        if not text:
            return CodexResult(False, "", stderr_text, "codex 沒有回答（-o 檔與 stdout 都是空的）", 0)
        return CodexResult(True, text, stderr_text, "", 0)
    except subprocess.TimeoutExpired:
        log(f"codex exec timed out after {timeout_s}s")
        return _not_run(f"timeout after {timeout_s}s")
    except FileNotFoundError:
        log(f"codex binary not found: {codex_bin}")
        return _not_run(f"codex binary not found: {codex_bin}")
    except Exception as e:  # noqa: BLE001  叫不起來一律收成失敗回給呼叫端，不讓例外炸掉宿主
        log(f"codex exec error: {e}")
        return _not_run(f"exception: {e}")
    finally:
        for p in (prompt_file, output_file):
            try:
                os.unlink(p)
            except OSError:
                pass


def load_config() -> Dict[str, Any]:
    """codex_companion 段（config.json 再蓋 config.local.json）。讀不到 → 空設定＋stderr 一行。"""
    raw: Any = {}
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"[codex-call] config 讀取失敗，用預設：{e}", file=sys.stderr)
    raw = merge_local(raw if isinstance(raw, dict) else {}, CONFIG_PATH.with_name("config.local.json"), "codex-call")
    cc = raw.get("codex_companion")
    return cc if isinstance(cc, dict) else {}


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--prompt", help="提示詞原文")
    src.add_argument("--prompt-file", help="提示詞檔；- 從 stdin 讀")
    ap.add_argument("--cwd", help="codex 的工作目錄（預設：目前目錄）")
    ap.add_argument("--model", help="模型 slug（預設 codex_companion.model；沒設就用 codex 自己的預設）")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help=f"秒數上限，逾時 kill（預設 {DEFAULT_TIMEOUT_S}）")
    ap.add_argument("--sandbox", choices=SANDBOX_MODES, help="沙箱模式（不給＝照 ~/.codex/config.toml 預設）")
    a = ap.parse_args(argv)

    try:
        if a.prompt is not None:
            prompt = a.prompt
        elif a.prompt_file == "-":
            prompt = sys.stdin.read()
        else:
            prompt = Path(a.prompt_file).read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        print(f"[codex-call] 失敗：提示詞讀不到：{e}", file=sys.stderr)
        return 1
    if not prompt.strip():
        print("[codex-call] 失敗：提示詞是空的", file=sys.stderr)
        return 1

    cfg = load_config()
    res = run_codex(prompt, config=cfg, cwd=a.cwd, model=a.model or str(cfg.get("model") or ""),
                    timeout_s=a.timeout, sandbox=a.sandbox)
    if not res.ok:
        print(f"[codex-call] 失敗：{res.reason}", file=sys.stderr)
        if res.stderr.strip():
            print(f"[codex-call] codex stderr 尾：{res.stderr.strip()[-800:]}", file=sys.stderr)
        return 1
    print(res.text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
