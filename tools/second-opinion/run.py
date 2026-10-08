#!/usr/bin/env python3
"""run.py：第二意見（second opinion）執行器：同材料、獨立作答、啟動不了就 failed 絕不報成功。

怎麼跑（MCP `second_opinion_start` 會自己呼叫；手動除錯才直接跑）：
  python tools/second-opinion/run.py prepare --request <request.json | ->    # 打包→提示詞→replay-guard pre；印 job_id/hash/status
  python tools/second-opinion/run.py execute --job <job_dir>                 # 探針→codex exec→replay-guard post→三段解析
  python tools/second-opinion/run.py probe                                   # 只探 codex 起不起得來（Reply CODEX_OK）
  python tools/second-opinion/run.py status --job <job_dir>                  # 印 status.json 與 reply.md
完整參數以 --help 為準。

job 目錄 `<~/.claude>/workflow/second-opinion/<yyyymmdd-HHMMSS>-<sid8>-<kind>/`：
  request.json  materials/  manifest.json  prompt.md  codex.stderr.log  reply.raw.md  reply.md  status.json
status.json 的 status：started（prepare 過閘，等 execute）→ running → done | failed | blocked。
封存答案關鍵字（sealed）寫在 `<job_root>/_sealed/<job_id>.txt`，不放 job 目錄裡（codex 的工作目錄）。

閘的立場：replay-guard pre 非 PASS → blocked、不 spawn；探針逾時／沙箱失敗 → failed、不退 claude；
post FAIL → failed；回覆缺任一段 → failed。沒有預覽模式、沒有延期補做。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
CLAUDE_DIR = Path(os.environ.get("WG_CLAUDE_DIR") or HERE.parents[1])
COMPANION_DIR = CLAUDE_DIR / "tools" / "codex-companion"
REPLAY_GUARD = CLAUDE_DIR / "tools" / "replay-guard.py"
CONFIG_PATH = CLAUDE_DIR / "workflow" / "config.json"
JOB_ROOT = CLAUDE_DIR / "workflow" / "second-opinion"

DEFAULTS: Dict[str, Any] = {
    "model": "gpt-6-astra",
    "probe_timeout_s": 20,
    "timeout_s": 300,
    "defects_top_n": 5,
    "ledger_tail": 20,
    "material_max_chars": 40000,
    "vcs_timeout_s": 20,
    "allow_claude_fallback": False,  # 固定 false：第二意見只接受跨廠模型，config 改了也不理
}

# 探針的強失敗樣式（Windows 沙箱登入型別未授權）；一般 `sandbox` 字樣只拿來標原因
_STRONG_FAIL_RE = re.compile(r"CreateProcessWithLogon|\b1385\b", re.IGNORECASE)
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_NO_CMD_LINE_REASON = "找不到任何指令行"


def _load_sibling(name: str, alias: str):
    """同資料夾模組用獨立名字載入（codex-companion 也有 prompts.py，避免撞名）。"""
    spec = importlib.util.spec_from_file_location(alias, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# 先把自己的資料夾從 sys.path 移走，companion 的 `import prompts` 才不會抓到本資料夾的 prompts.py
sys.path[:] = [p for p in sys.path if p and Path(p).resolve() != HERE]
pack = _load_sibling("pack", "so_pack")
so_prompts = _load_sibling("prompts", "so_prompts")
if str(COMPANION_DIR) not in sys.path:
    sys.path.insert(0, str(COMPANION_DIR))
import judge_backend  # noqa: E402
import assessor  # noqa: E402  （借 _SANDBOX_FAILURE_RE）


# ─── 共用 ────────────────────────────────────────────────────────────────────


def load_config() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """回 (second_opinion 段含預設, codex_companion 段)。config 缺檔／壞檔 → 預設 + stderr 一行。"""
    raw: Dict[str, Any] = {}
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.stderr.write(f"[second-opinion] config 讀取失敗，用預設：{e}\n")
    so = dict(DEFAULTS)
    so.update({k: v for k, v in (raw.get("second_opinion") or {}).items() if not k.startswith("_")})
    so["allow_claude_fallback"] = False
    return so, (raw.get("codex_companion") or {})


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


TERMINAL = ("done", "failed", "blocked")
MAX_LOG_BYTES = 20 * 1024 * 1024  # post_guard 整份掃描的上限；超過直接 failed「紀錄過大無法判定」，不掃尾段
SCAN_DEADLINE_S = 30  # 整份掃描跑在子行程，subprocess.run(timeout=…)；逾時 kill → failed「掃描逾時無法判定」


def write_status(job_dir: Path, status: str, **kw: Any) -> Dict[str, Any]:
    """寫 status.json。終態保護：現況已是 done／failed／blocked 而新狀態不同 → 不寫、回現況（附 rejected_write），
    stderr 一行。並行 execute 的 A 寫 failed 後 B 不能再蓋成 done。"""
    cur = _read_json(job_dir / "status.json")
    if cur.get("status") in TERMINAL and status != cur.get("status"):
        cur["rejected_write"] = f"終態 {cur.get('status')} 不可覆寫為 {status}"
        sys.stderr.write(f"[second-opinion] {job_dir.name}: {cur['rejected_write']}\n")
        return cur
    cur.update(kw)
    cur["status"] = status
    cur["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_json(job_dir / "status.json", cur)
    return cur


def new_job_id(kind: str, session_id: str = "") -> str:
    sid8 = re.sub(r"[^0-9a-z]", "", (session_id or "").lower())[:8] or uuid.uuid4().hex[:8]
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{sid8}-{kind}"


def _tail(path: Path, n: int = 1200) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-n:]
    except OSError:
        return ""


def _read_all(path: Path) -> str:
    """整檔讀，不切（post_guard 的整份掃描與回覆解析用；大小上限由呼叫端先檢查）。"""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _sentinel(out: str) -> Tuple[str, List[str]]:
    """replay-guard 輸出 → (PASS|FAIL|UNKNOWN, 理由行)。"""
    verdict = "UNKNOWN"
    reasons: List[str] = []
    for line in (out or "").splitlines():
        s = line.strip()
        if s.startswith("REPLAY_GUARD_CHECK "):
            verdict = s.split()[-1]
        elif s.startswith("- "):
            reasons.append(s[2:])
    return verdict, reasons


def run_guard(args: List[str], timeout_s: int = 60) -> Tuple[str, List[str], str]:
    cmd = [sys.executable, "-X", "utf8", str(REPLAY_GUARD)] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout_s, creationflags=_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "UNKNOWN", [f"replay-guard 跑不起來：{e}"], ""
    verdict, reasons = _sentinel(r.stdout)
    return verdict, reasons, (r.stdout or "") + (r.stderr or "")


def run_with_timeout(cmd: List[str], timeout_s: int, cwd: Optional[str], stdin_path: Optional[Path],
                     stdout_path: Path, stderr_path: Path) -> Tuple[Optional[int], bool]:
    """Popen + wait(timeout)；逾時就 kill 再 wait。回 (returncode, timed_out)。stdout/stderr 落檔。"""
    stdin_fh = open(stdin_path, "rb") if stdin_path else subprocess.DEVNULL
    with open(stdout_path, "ab") as out_fh, open(stderr_path, "ab") as err_fh:
        try:
            proc = subprocess.Popen(cmd, stdin=stdin_fh, stdout=out_fh, stderr=err_fh, cwd=cwd,
                                    env={**os.environ, "NO_COLOR": "1"}, creationflags=_NO_WINDOW)
        finally:
            if stdin_path:
                stdin_fh.close()
        try:
            rc = proc.wait(timeout=timeout_s)
            return rc, False
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            return None, True


def resolve_model(so_cfg: Dict[str, Any]) -> Tuple[Optional[str], str]:
    return judge_backend.resolve_model_slug({"model": so_cfg.get("model")}, so_cfg.get("models_cache"))


# ─── prepare ─────────────────────────────────────────────────────────────────


def validate_request(req: Dict[str, Any]) -> Optional[str]:
    kind = str(req.get("kind") or "")
    mode = str(req.get("mode") or "")
    if kind not in so_prompts.KINDS:
        return f"kind 只收 {'|'.join(so_prompts.KINDS)}：{kind!r}"
    if mode not in so_prompts.MODES:
        return f"mode 只收 {'|'.join(so_prompts.MODES)}：{mode!r}"
    if not str(req.get("part") or "").strip():
        return "part 必填"
    cwd = str(req.get("cwd") or "")
    if not cwd or not Path(cwd).is_dir():
        return f"cwd 必須是存在的目錄：{cwd!r}"
    if not str(req.get("question") or "").strip():
        return "question 必填"
    has_draft = bool(str(req.get("draft") or "").strip())
    if mode == "independent" and has_draft:
        return "independent 模式不收 draft（獨立作答不能看到己方答案）"
    if mode == "review" and not has_draft:
        return "review 模式必須帶 draft"
    sealed = req.get("sealed")
    if sealed is not None and not (isinstance(sealed, list) and all(isinstance(s, str) for s in sealed)):
        return "sealed 必須是字串陣列"
    return None


def prepare(req: Dict[str, Any], so_cfg: Dict[str, Any], job_root: Path) -> Dict[str, Any]:
    """打包→提示詞→replay-guard pre。回 {job_id, hash, status, reason?, notes, job_dir}；不 spawn codex。"""
    err = validate_request(req)
    if err:
        return {"job_id": "-", "hash": "-", "status": "failed", "reason": err, "notes": [], "job_dir": ""}
    slug, merr = resolve_model(so_cfg)
    if not slug:
        return {"job_id": "-", "hash": "-", "status": "failed", "reason": merr, "notes": [], "job_dir": ""}

    job_id = new_job_id(str(req["kind"]), str(req.get("session_id") or ""))
    job_dir = job_root / job_id
    for _ in range(12):  # 同一秒內同 session 再開一個 job：等下一秒，不改 job 名格式
        if not job_dir.exists():
            break
        time.sleep(0.1)
        job_id = new_job_id(str(req["kind"]), str(req.get("session_id") or ""))
        job_dir = job_root / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    _write_json(job_dir / "request.json", req)

    items, notes = pack.gather_items(req, so_cfg)
    try:
        manifest = pack.pack_materials(job_dir, items, str(req["mode"]), slug)
    except pack.PackError as e:
        write_status(job_dir, "failed", job_id=job_id, reason=str(e), notes=notes)
        return {"job_id": job_id, "hash": "-", "status": "failed", "reason": str(e), "notes": notes, "job_dir": str(job_dir)}
    outside = pack.manifest_outside_paths(manifest)
    if outside:
        reason = "manifest 含沙箱外絕對路徑：" + "、".join(outside[:3])
        write_status(job_dir, "failed", job_id=job_id, hash=manifest["hash"], reason=reason, notes=notes)
        return {"job_id": job_id, "hash": manifest["hash"], "status": "failed", "reason": reason, "notes": notes, "job_dir": str(job_dir)}

    sealed_words = [s.strip() for s in (req.get("sealed") or []) if s.strip()]
    sealed_path: Optional[Path] = None
    if sealed_words:
        sealed_path = job_root / "_sealed" / f"{job_id}.txt"
        sealed_path.parent.mkdir(parents=True, exist_ok=True)
        sealed_path.write_text("\n".join(sealed_words) + "\n", encoding="utf-8", newline="\n")
        leaked = [w for rel, text in items for w in sealed_words if w.lower() in (text or "").lower()]
        if leaked:
            reason = "材料含封存答案關鍵字（出題者洩題）：" + "、".join(sorted(set(leaked))[:5])
            write_status(job_dir, "blocked", job_id=job_id, hash=manifest["hash"], reason=reason, notes=notes)
            return {"job_id": job_id, "hash": manifest["hash"], "status": "blocked", "reason": reason, "notes": notes, "job_dir": str(job_dir)}

    texts = {rel: text for rel, text in items}
    prompt = so_prompts.build_prompt(
        str(req["mode"]), manifest, str(req["question"]), draft=req.get("draft"),
        kind=str(req["kind"]), part=str(req["part"]), texts=texts,
        material_max_chars=int(so_cfg.get("material_max_chars", 40000)))
    (job_dir / "prompt.md").write_text(prompt, encoding="utf-8", newline="\n")

    guard_args = ["pre", "--prompt", str(job_dir / "prompt.md"), "--sandbox", str(job_dir)]
    if sealed_path:
        guard_args += ["--sealed", str(sealed_path)]
    verdict, reasons, raw = run_guard(guard_args)
    (job_dir / "guard.pre.log").write_text(raw, encoding="utf-8", newline="\n")
    base = dict(job_id=job_id, hash=manifest["hash"], model=slug, mode=req["mode"], kind=req["kind"],
                part=req["part"], notes=notes, timeout_s=int(so_cfg.get("timeout_s", 300)))
    if verdict != "PASS":
        reason = f"replay-guard pre {verdict}：" + ("；".join(reasons) or "無理由行")
        write_status(job_dir, "blocked", reason=reason, **base)
        return {"job_id": job_id, "hash": manifest["hash"], "status": "blocked", "reason": reason, "notes": notes, "job_dir": str(job_dir)}
    write_status(job_dir, "started", stage="prepared", **base)
    return {"job_id": job_id, "hash": manifest["hash"], "status": "started", "notes": notes, "job_dir": str(job_dir)}


# ─── execute ─────────────────────────────────────────────────────────────────


def probe_codex(job_dir: Path, slug: str, so_cfg: Dict[str, Any], cc_cfg: Dict[str, Any]) -> Tuple[bool, str]:
    """`codex exec --skip-git-repo-check -s read-only -m <slug> "Reply CODEX_OK"`；逾時／1385／沒回 CODEX_OK → False。"""
    codex_bin = judge_backend.resolve_codex_bin(cc_cfg)
    if not codex_bin:
        return False, "找不到 codex CLI（codex_companion.codex_binary 與 PATH 都沒有）"
    cmd = [codex_bin, "exec", "--skip-git-repo-check", "-s", "read-only", "-m", slug]
    cmd += [str(a) for a in (cc_cfg.get("codex_extra_args") or [])]
    cmd += ["Reply CODEX_OK"]
    out_p, err_p = job_dir / "probe.stdout.log", job_dir / "probe.stderr.log"
    rc, timed_out = run_with_timeout(cmd, int(so_cfg.get("probe_timeout_s", 20)), str(job_dir), None, out_p, err_p)
    stderr = _tail(err_p)
    stdout = _tail(out_p, 4000)
    if timed_out:
        return False, f"探針逾時（{so_cfg.get('probe_timeout_s', 20)}s）；stderr 尾：{stderr[-400:]}"
    if _STRONG_FAIL_RE.search(stderr) or (assessor._SANDBOX_FAILURE_RE.search(stderr) and "CODEX_OK" not in stdout):
        return False, f"codex 沙箱起不來（唯讀沙箱失敗）；stderr 尾：{stderr[-400:]}"
    if rc != 0 or "CODEX_OK" not in stdout:
        return False, f"探針沒回 CODEX_OK（exit={rc}）；stderr 尾：{stderr[-400:]}"
    return True, ""


def _guard_module():
    spec = importlib.util.spec_from_file_location("replay_guard", REPLAY_GUARD)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["replay_guard"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def scan_log(job_dir: Path) -> Dict[str, List[str]]:
    """fallback 掃描本體（跑在子行程裡）：stderr＋stdout **整份**文字，用 guard 原本的 FORBIDDEN_IN_LOG 逐條 re.search 全文、
    paths_outside 判出界。不切塊、不截斷。唯一的加速：先用 guard 同一條 ABS_PATH 把路徑 token 抽出來、**保留完整 token** 去重，
    再交給 paths_outside（它逐筆 realpath，10 MB 重複路徑不去重要跑 30 s＋）；token 集合相同，結果與直接餵全文等價。"""
    g = _guard_module()
    full = _read_all(job_dir / "codex.stderr.log") + "\n" + _read_all(job_dir / "codex.stdout.log")
    hits = [pat for pat in g.FORBIDDEN_IN_LOG if re.search(pat, full, flags=re.IGNORECASE)]
    toks = sorted(set(m.group(0) for m in g.ABS_PATH.finditer(full)))
    outside = g.paths_outside("\n".join(toks), job_dir) if toks else []
    return {"hits": hits, "outside": outside}


def run_scan_subprocess(job_dir: Path) -> Tuple[Optional[Dict[str, List[str]]], str]:
    """在子行程跑 `run.py scan --job <dir>`，`subprocess.run(timeout=SCAN_DEADLINE_S)`；逾時 kill → (None, 原因)。
    回 (結果, "") 或 (None, 原因)。子行程非零 exit（非 0／1）或 JSON 解析失敗也算無法判定。"""
    cmd = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "scan", "--job", str(job_dir)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=SCAN_DEADLINE_S, creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired:
        return None, f"整份掃描逾時（>{SCAN_DEADLINE_S}s）無法判定（子行程已 kill）"
    except OSError as e:
        return None, f"掃描子行程起不來：{e}"
    parsed, why = _parse_scan_output(r.returncode, r.stdout or "")
    if parsed is None:
        return None, f"掃描結果不可信：{why}；exit={r.returncode}；stderr 尾：{(r.stderr or '')[-300:]}"
    return {"hits": parsed[0], "outside": parsed[1]}, ""


def _str_list(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _parse_scan_output(rc: Optional[int], stdout: str) -> Tuple[Optional[Tuple[List[str], List[str]]], str]:
    """子行程協定核對，任一不符回 (None, 原因)：
    尾行恰為 `SCAN_CHECK PASS`／`SCAN_CHECK FAIL`；尾行前是單一 JSON 物件，`hits`／`outside` 兩鍵都在且都是字串陣列；
    一致性：PASS ⇔ rc==0 ⇔ 兩陣列皆空；FAIL ⇔ rc==1 ⇔ 至少一個非空。"""
    lines = [l for l in stdout.splitlines() if l.strip()]
    if not lines:
        return None, "stdout 空"
    sentinel = lines[-1].strip()
    if sentinel not in ("SCAN_CHECK PASS", "SCAN_CHECK FAIL"):
        return None, f"尾行不是 SCAN_CHECK PASS|FAIL：{sentinel[:80]!r}"
    try:
        data = json.loads("\n".join(lines[:-1]))
    except ValueError as e:
        return None, f"JSON 解析失敗：{e}"
    if not isinstance(data, dict) or "hits" not in data or "outside" not in data:
        return None, "JSON 不是物件或缺 hits／outside 鍵"
    hits, outside = data["hits"], data["outside"]
    if not _str_list(hits) or not _str_list(outside):
        return None, "hits／outside 不是字串陣列"
    is_pass = sentinel.endswith("PASS")
    empty = not hits and not outside
    if is_pass and (rc != 0 or not empty):
        return None, f"PASS 但 rc={rc}、hits={len(hits)}、outside={len(outside)}（應 rc 0 且皆空）"
    if not is_pass and (rc != 1 or empty):
        return None, f"FAIL 但 rc={rc}、hits={len(hits)}、outside={len(outside)}（應 rc 1 且至少一個非空）"
    return (list(hits), list(outside)), ""


def post_guard(job_dir: Path) -> Tuple[bool, str]:
    """replay-guard post；FAIL → False。唯一例外：FAIL 只因「找不到指令行」（codex 純推理沒跑指令）時，
    改以 guard 的禁區樣式與出界路徑規則掃**整份** stderr＋stdout；掃不到才算 PASS 並留 note。"""
    log = job_dir / "codex.stderr.log"
    verdict, reasons, raw = run_guard(["post", "--log", str(log), "--sandbox", str(job_dir)])
    (job_dir / "guard.post.log").write_text(raw, encoding="utf-8", newline="\n")
    if verdict == "PASS":
        return True, ""
    if verdict == "FAIL" and len(reasons) == 1 and _NO_CMD_LINE_REASON in reasons[0]:
        stdout_log = job_dir / "codex.stdout.log"
        total = _size(log) + _size(stdout_log)
        if total > MAX_LOG_BYTES:
            return False, f"replay-guard post FAIL（無指令行）且紀錄過大無法判定：{total} bytes > {MAX_LOG_BYTES}"
        scanned, why = run_scan_subprocess(job_dir)  # 子行程整份掃描；逾時／異常都算無法判定 → failed
        if scanned is None:
            return False, f"replay-guard post FAIL（無指令行）且{why}"
        hits, outside = scanned["hits"], scanned["outside"]
        if not hits and not outside:
            return True, "post：codex 未執行任何指令（純推理），整份紀錄無禁區樣式與出界路徑"
        return False, "replay-guard post FAIL（無指令行，但整份紀錄命中）：" + "；".join(hits + outside[:5])
    return False, f"replay-guard post {verdict}：" + ("；".join(reasons) or "無理由行")


def _acquire_executor_lock(job_dir: Path) -> bool:
    """`execute.lock` 以 O_CREAT|O_EXCL 建立：同一 job 只能有一個 executor。拿不到回 False（不刪、不等）。"""
    try:
        fd = os.open(str(job_dir / "execute.lock"), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"pid={os.getpid()} at={time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    return True


def _execute_body(job_dir: Path, so_cfg: Dict[str, Any], cc_cfg: Dict[str, Any], stage: List[str]) -> Dict[str, Any]:
    st = _read_json(job_dir / "status.json")
    slug = str(st.get("model") or "")
    stage[0] = "probe"
    write_status(job_dir, "running", stage="probe")
    ok, why = probe_codex(job_dir, slug, so_cfg, cc_cfg)
    if not ok:
        return write_status(job_dir, "failed", stage="probe", reason=why)

    stage[0] = "codex"
    write_status(job_dir, "running", stage="codex")
    codex_bin = judge_backend.resolve_codex_bin(cc_cfg) or "codex"
    reply_raw = job_dir / "reply.raw.md"
    cmd = [codex_bin, "exec", "-m", slug, "-s", "read-only", "-C", str(job_dir), "--ephemeral",
           "--skip-git-repo-check", "-o", str(reply_raw)]
    cmd += [str(a) for a in (cc_cfg.get("codex_extra_args") or [])]
    cmd += ["-"]
    timeout_s = int(so_cfg.get("timeout_s", 300))
    rc, timed_out = run_with_timeout(cmd, timeout_s, str(job_dir), job_dir / "prompt.md",
                                     job_dir / "codex.stdout.log", job_dir / "codex.stderr.log")
    if timed_out:
        return write_status(job_dir, "failed", stage="codex",
                            reason=f"codex exec 逾時（{timeout_s}s）已 kill；stderr 尾：{_tail(job_dir / 'codex.stderr.log', 400)}")
    if rc != 0:
        return write_status(job_dir, "failed", stage="codex",
                            reason=f"codex exec exit={rc}；stderr 尾：{_tail(job_dir / 'codex.stderr.log', 400)}")

    stage[0] = "post-guard"
    write_status(job_dir, "running", stage="post-guard")
    ok, note = post_guard(job_dir)
    if not ok:
        return write_status(job_dir, "failed", stage="post-guard", reason=note)

    stage[0] = "parse"
    if _size(reply_raw) > MAX_LOG_BYTES:
        return write_status(job_dir, "failed", stage="parse", reason=f"reply.raw.md 過大（{_size(reply_raw)} bytes）無法解析")
    sections = so_prompts.parse_three_sections(_read_all(reply_raw))
    if not sections:
        return write_status(job_dir, "failed", stage="parse",
                            reason="回覆缺段（要恰好 ## 結論／## 證據／## 反例或未解 三段）；原文在 reply.raw.md")
    (job_dir / "reply.md").write_text(so_prompts.render_reply(sections), encoding="utf-8", newline="\n")
    extra = {"guard_note": note} if note else {}
    return write_status(job_dir, "done", stage="done", reason="", **extra)


def execute(job_dir: Path, so_cfg: Dict[str, Any], cc_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """探針→codex→post guard→解析。任何例外都收成 failed（status 不會卡在 running）；同 job 第二個 executor 直接拒。"""
    st = _read_json(job_dir / "status.json")
    if st.get("status") != "started":
        # 拒絕路徑只回傳、不寫檔：failed job 的原始 reason／updated_at 是診斷證據，不能被「只接 started」那句蓋掉
        rejected = dict(st, rejected_execute=f"execute 只接 started 的 job（現為 {st.get('status')!r}）；要重跑請重新 prepare 建新 job")
        sys.stderr.write(f"[second-opinion] {job_dir.name}: {rejected['rejected_execute']}\n")
        return rejected
    if not _acquire_executor_lock(job_dir):
        rejected = dict(st, rejected_execute="已有 executor（execute.lock 存在）；要重跑請重新 prepare 建新 job")
        sys.stderr.write(f"[second-opinion] {job_dir.name}: {rejected['rejected_execute']}\n")
        return rejected
    stage = ["start"]
    try:
        return _execute_body(job_dir, so_cfg, cc_cfg, stage)
    except Exception as e:  # noqa: BLE001  任何啟動／IO 例外都要落 failed，不能留 running
        reason = f"execute 例外（stage={stage[0]}）：{e!r}"
        try:
            return write_status(job_dir, "failed", stage=stage[0], reason=reason)
        except Exception as e2:  # noqa: BLE001  連 status.json 都寫不進去：stderr 留痕，回記憶體狀態
            sys.stderr.write(f"[second-opinion] {job_dir.name}: 寫 failed 狀態也失敗：{e2!r}；原因：{reason}\n")
            return {"status": "failed", "stage": stage[0], "reason": reason, "status_write_error": repr(e2)}


# ─── CLI ─────────────────────────────────────────────────────────────────────


def _print_prepare(res: Dict[str, Any]) -> None:
    print(f"job_id: {res['job_id']}")
    print(f"hash: {res['hash']}")
    print(f"status: {res['status']}")
    if res.get("reason"):
        print(f"reason: {res['reason']}")
    for n in res.get("notes") or []:
        print(f"note: {n}")
    if res.get("job_dir"):
        print(f"job_dir: {res['job_dir']}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="打包材料、寫提示詞、跑 replay-guard pre；印 job_id/hash/status")
    p.add_argument("--request", default="-", help="request.json 路徑，或 - 讀 stdin")
    e = sub.add_parser("execute", help="探針→codex exec→post guard→三段解析；結果寫 status.json/reply.md")
    e.add_argument("--job", required=True)
    sub.add_parser("probe", help="只探 codex（Reply CODEX_OK）")
    s = sub.add_parser("status", help="印 status.json 與 reply.md")
    s.add_argument("--job", required=True)
    sc = sub.add_parser("scan", help="（post_guard 內部用）整份掃 codex.stderr.log＋codex.stdout.log；印 JSON＋尾行 SCAN_CHECK PASS|FAIL")
    sc.add_argument("--job", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "scan":
        job = Path(args.job)
        total = _size(job / "codex.stderr.log") + _size(job / "codex.stdout.log")
        if total > MAX_LOG_BYTES:  # 被當獨立工具用時也不吃光記憶體；協定上以一條 hit 表達，FAIL／rc 1／非空一致
            res = {"hits": [f"oversize: 紀錄 {total} bytes > {MAX_LOG_BYTES}，無法判定"], "outside": []}
        else:
            res = scan_log(job)
        print(json.dumps(res, ensure_ascii=False))
        ok = not res["hits"] and not res["outside"]
        print("SCAN_CHECK " + ("PASS" if ok else "FAIL"))
        return 0 if ok else 1

    so_cfg, cc_cfg = load_config()
    if args.cmd == "prepare":
        raw = sys.stdin.read() if args.request == "-" else Path(args.request).read_text(encoding="utf-8")
        try:
            req = json.loads(raw)
        except ValueError as ex:
            _print_prepare({"job_id": "-", "hash": "-", "status": "failed", "reason": f"request 不是 JSON：{ex}"})
            return 2
        res = prepare(req, so_cfg, JOB_ROOT)
        _print_prepare(res)
        return 0 if res["status"] == "started" else 1
    if args.cmd == "execute":
        st = execute(Path(args.job), so_cfg, cc_cfg)
        print(f"status: {st.get('status')}")
        if st.get("reason"):
            print(f"reason: {st['reason']}")
        return 0 if st.get("status") == "done" else 1
    if args.cmd == "probe":
        slug, merr = resolve_model(so_cfg)
        if not slug:
            print(f"status: failed\nreason: {merr}")
            return 1
        tmp = JOB_ROOT / "_probe"
        tmp.mkdir(parents=True, exist_ok=True)
        ok, why = probe_codex(tmp, slug, so_cfg, cc_cfg)
        print(f"status: {'ok' if ok else 'failed'}\nmodel: {slug}" + (f"\nreason: {why}" if why else ""))
        return 0 if ok else 1
    job = Path(args.job)
    st = _read_json(job / "status.json")
    print(json.dumps(st, ensure_ascii=False, indent=2))
    if (job / "reply.md").is_file():
        print((job / "reply.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
