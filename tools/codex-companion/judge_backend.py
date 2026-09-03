"""judge_backend.py — 裁判後端解析與執行（規則唯一來源）。

「AI 審查 AI」的裁判鏈，由本檔單一決定：

  1. codex        跨廠獨立 → 獨立性滿血，擁有 block 權
  2. claude -p    同廠不同模型（預設 Sonnet）→ 獨立性降級，預設**無** block 權
  3. 皆不可用     回 BACKEND_NONE，上層退回 heuristics-only

codex 未安裝、或裝了但未開通授權（未登入 / 401 / 額度用盡）→ 自動退 (2)。
授權類失敗會落 `workflow/companion-backend.json` 抑制標記，`reprobe_hours`
內不再試 codex（省掉每輪兩次逾時），期滿自動重探；一旦 codex 成功即清除。

備援子 session 以 env `CLAUDE_COMPANION_JUDGE=1` 標記，hooks 端據此整組
早退——否則裁判 session 會再觸發裁判（遞迴）並被自家收尾閘擋住。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

CLAUDE_DIR = Path.home() / ".claude"
STATE_PATH = CLAUDE_DIR / "workflow" / "companion-backend.json"

BACKEND_CODEX = "codex"
BACKEND_CLAUDE = "claude"
BACKEND_NONE = ""

# 子 session 標記：hooks 端見此值一律早退（防遞迴 + 防狀態汙染）
JUDGE_ENV = "CLAUDE_COMPANION_JUDGE"

# Windows detached 父進程呼叫 .cmd wrapper 會彈 console 視窗
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# 授權/額度類失敗（≠ 一般逾時或輸出解析失敗）。命中才切備援並抑制 codex。
_ENTITLEMENT_RE = re.compile(
    r"not logged in|please run [`\"']?codex login|codex login|"
    r"unauthori[sz]|forbidden|\b401\b|\b403\b|\b429\b|"
    r"invalid api key|missing api key|no credentials|authentication failed|"
    r"usage limit|rate limit|quota exceeded|no active subscription",
    re.IGNORECASE,
)

_JUDGE_INSTRUCTION = (
    "你是獨立驗收裁判。依 stdin 提供的完整材料做判定，"
    "只輸出一個 JSON 物件，不得有任何前後文字或 markdown 圍欄。"
)


def _log(msg: str) -> None:
    try:
        sys.stderr.write(f"[judge_backend] {msg}\n")
    except OSError:
        pass


# ─── config helpers ──────────────────────────────────────────────────────────


def fallback_cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    return (config or {}).get("fallback") or {}


def fallback_enabled(config: Dict[str, Any]) -> bool:
    return bool(fallback_cfg(config).get("enabled", True))


def fallback_can_block(config: Dict[str, Any]) -> bool:
    """備援裁判是否有 block 權。預設 False。

    同廠同家族的模型盲點相關，獨立性低於跨廠的 codex；預設只發 advisory，
    要升級成硬閘是使用者的明示選擇（config `fallback.allow_block`）。
    """
    return bool(fallback_cfg(config).get("allow_block", False))


# ─── binary 解析 ─────────────────────────────────────────────────────────────


def resolve_codex_bin(config: Dict[str, Any]) -> Optional[str]:
    """config 值（可為絕對路徑或名稱）→ 檔案存在 → PATH → 裸 `codex`。

    config 寫死的絕對路徑在別台機器不存在時**不是錯誤**，退 PATH 尋找，
    避免「有裝 codex 卻被靜默關掉」。
    """
    raw = str((config or {}).get("codex_binary") or "codex").strip()
    if raw and os.path.isfile(raw):
        return raw
    return shutil.which(raw) or shutil.which("codex")


def _ver_key(name: str) -> Tuple[int, int, int]:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", name or "")
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def resolve_claude_bin(config: Dict[str, Any]) -> Optional[str]:
    """找可跑的 claude CLI：config 指定 → PATH → VSCode 擴充 → native versions。

    Windows 的 native versions 目錄下是**無副檔名的版本檔**（`versions/2.1.221`），
    非 Windows 則多為 `versions/<ver>/claude`；兩種佈局都認。
    """
    raw = str(fallback_cfg(config).get("claude_binary") or "").strip()
    if raw:
        if os.path.isfile(raw):
            return raw
        found = shutil.which(raw)
        if found:
            return found

    on_path = shutil.which("claude")
    if on_path:
        return on_path

    exe = "claude.exe" if sys.platform == "win32" else "claude"
    ext_root = Path.home() / ".vscode" / "extensions"
    if ext_root.is_dir():
        cands = list(ext_root.glob(f"anthropic.claude-code-*/resources/native-binary/{exe}"))
        if cands:
            cands.sort(key=lambda p: _ver_key(p.parts[-4]), reverse=True)
            return str(cands[0])

    versions = Path.home() / ".local" / "share" / "claude" / "versions"
    if versions.is_dir():
        nested = sorted(versions.glob(f"*/{exe}"),
                        key=lambda p: _ver_key(p.parent.name), reverse=True)
        if nested:
            return str(nested[0])
        flat = sorted((p for p in versions.iterdir()
                       if p.is_file() and _ver_key(p.name) > (0, 0, 0)),
                      key=lambda p: _ver_key(p.name), reverse=True)
        if flat:
            return str(flat[0])
    return None


# ─── 抑制狀態（codex 授權失敗記憶） ───────────────────────────────────────────


def read_backend_state() -> Dict[str, Any]:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _write_backend_state(data: Dict[str, Any]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        tmp.replace(STATE_PATH)
    except OSError as e:
        _log(f"state write failed: {e}")


def mark_codex_unavailable(reason: str) -> None:
    data = read_backend_state()
    data["codex_unavailable"] = {"reason": (reason or "")[-300:], "ts": time.time()}
    _write_backend_state(data)
    _log(f"codex 授權類失敗，切備援並抑制重試：{(reason or '')[-120:]}")


def clear_codex_unavailable() -> None:
    data = read_backend_state()
    if data.pop("codex_unavailable", None) is not None:
        _write_backend_state(data)


def codex_suppressed(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """回未過期的抑制紀錄；已過 reprobe_hours 或無紀錄 → None（可重探）。"""
    rec = read_backend_state().get("codex_unavailable")
    if not isinstance(rec, dict):
        return None
    hours = float(fallback_cfg(config).get("reprobe_hours", 24) or 24)
    if time.time() - float(rec.get("ts", 0)) > hours * 3600:
        return None
    return rec


# ─── 後端選擇 ────────────────────────────────────────────────────────────────


def select_backend(config: Dict[str, Any]) -> Tuple[str, str]:
    """回 (backend, binary)。純解析、不跑任何子程序，可安全用在 hook fast-path。"""
    codex_bin = resolve_codex_bin(config)
    if codex_bin and not codex_suppressed(config):
        return BACKEND_CODEX, codex_bin
    if fallback_enabled(config):
        claude_bin = resolve_claude_bin(config)
        if claude_bin:
            return BACKEND_CLAUDE, claude_bin
    return BACKEND_NONE, ""


def is_entitlement_failure(stderr: str) -> bool:
    return bool(_ENTITLEMENT_RE.search(stderr or ""))


def describe_unavailable(config: Dict[str, Any]) -> str:
    """無可用後端時的白話原因（給一次性揭露訊息用）。"""
    codex_raw = str((config or {}).get("codex_binary") or "codex")
    parts = [f"找不到 codex CLI（設定值：{codex_raw}）"]
    rec = codex_suppressed(config)
    if rec:
        parts = [f"codex 授權未開通或額度受限：{rec.get('reason', '')[-120:]}"]
    if not fallback_enabled(config):
        parts.append("備援已關閉（fallback.enabled=false）")
    else:
        parts.append("也找不到 claude CLI 可當備援裁判")
    return "；".join(parts)


# ─── claude headless 裁判 ────────────────────────────────────────────────────


def run_claude_judge(
    prompt_text: str, cwd: str, config: Dict[str, Any],
    claude_bin: str, timeout: Optional[int] = None,
) -> Tuple[str, str]:
    """跑 headless `claude -p` 當備援裁判，回 (stdout, stderr)。

    材料走 stdin（22k 級 prompt 不塞 argv，避開 Windows 命令列長度上限）；
    工具面只留唯讀（Bash/Write/Edit 等一律禁用），裁判不得改動受審的東西。
    """
    fb = fallback_cfg(config)
    model = str(fb.get("model") or "sonnet")
    eff_timeout = int(timeout or fb.get("timeout", 90))

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    , newline="\n") as f:
        f.write(prompt_text)
        prompt_file = f.name

    cmd = [
        claude_bin, "-p", _JUDGE_INSTRUCTION,
        "--model", model,
        "--output-format", "text",
        "--permission-mode", "bypassPermissions",
        "--disallowed-tools", "Bash,Write,Edit,NotebookEdit,Task,WebFetch,WebSearch",
    ]
    env = {**os.environ, JUDGE_ENV: "1", "NO_COLOR": "1"}

    try:
        _log(f"fallback judge: claude -p --model {model} (timeout={eff_timeout}s)")
        with open(prompt_file, "r", encoding="utf-8") as pf:
            result = subprocess.run(
                cmd, stdin=pf, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=eff_timeout,
                cwd=cwd if cwd and os.path.isdir(cwd) else None,
                env=env, creationflags=_NO_WINDOW,
            )
        _log(f"claude judge exit code: {result.returncode}")
        return (result.stdout or "").strip(), (result.stderr or "")
    except subprocess.TimeoutExpired:
        return "", f"[judge_backend] claude judge timeout after {eff_timeout}s"
    except FileNotFoundError:
        return "", f"[judge_backend] claude binary not found: {claude_bin}"
    except Exception as e:  # noqa: BLE001 — 裁判失效不得炸掉宿主 hook
        return "", f"[judge_backend] claude judge error: {type(e).__name__}: {e}"
    finally:
        for p in (prompt_file,):
            try:
                os.unlink(p)
            except OSError:
                pass
