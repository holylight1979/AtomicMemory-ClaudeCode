"""wg_bg_harvest — 收尾的知識收割與目標樹記帳交給背景的開源免費模型（內網 rdchat 的 gemma4:e4b），不佔寫碼 AI 的回合。

做什麼：
- Stop（on_stop）：本來 KnowledgeHarvest 閘要擋下、叫寫碼 AI 盤點六個來源再呼叫 knowledge_harvest_report（多跑一整回合）；
  harvest.background 開著（預設）就改成寫一個工作檔、起一個背景行程（本檔 --job）就回，不擋。背景同一次也找出這個回合程式剛替
  目標樹記進度的節點（wg_need_goal.auto_progress 寫的 by=program），請本地模型照 transcript 草擬一句「這次改動讓它更接近了沒」。
- 背景（run_job）：讀 transcript 尾段（使用者原話與 AI 回覆，不含工具輸出），問本地模型要 JSON：
  候選卡 [{title, knowledge, why}]（最多 harvest.background_max_cards 張）與進度草稿 [{node, line}]。
  候選卡是待審卡、不是卡：專案有 .claude/memory → 寫進專案 shared/_pending_review/（開場「[Pending Review] N 件待裁決」、
  /conflict pending 審）；沒有 → 寫進資料根 memory/_staging/harvest-candidates/（開場一行提示有幾份待審）。判錯只多一張待審卡。
  進度草稿寫進目標樹節點 history（what=progress_draft、by=local_llm）；目標有沒有更接近仍由寫碼 AI 在完整對照判。
- 留帳 Logs/guard-harvest_bg.jsonl：queued／done（張數、草稿數、用哪個模型）／failed（為什麼）。模型不在、逾時、回的不是 JSON
  一律記 failed 與 worker.log，不改用付費模型、不回頭擋。
寫碼 AI 自己要記的照樣可以 atom_write＋knowledge_harvest_report（Harvest-Pending 閘照核對）；這裡只拿掉「每次宣告完成都擋一回合」。
怎麼跑：Stop 自動呼叫；背景入口 `python hooks/wg_bg_harvest.py --job <工作檔>` 由 Stop 起，不手動跑。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_HOOKS = Path(__file__).resolve().parent
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

from wg_core import CLAUDE_DIR, WORKFLOW_DIR, append_guard_log, rotate_log_if_oversized  # noqa: E402

JOB_DIR = WORKFLOW_DIR / "harvest-bg"
LEDGER = "harvest_bg"
TAG = "[Guardian:HarvestBg]"
STALE_S = 86400.0
TAIL_CHARS = 12000
DEFAULTS = {"background": True, "background_model": "gemma4:e4b", "background_max_cards": 3, "background_timeout_sec": 180}
_DETACHED = (subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS) if sys.platform == "win32" else 0


def bg_cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    """config.harvest 的背景收割設定（沒有 harvest 段＝收割整個關，回空 dict）。"""
    h = (config or {}).get("harvest")
    return {**DEFAULTS, **{k: v for k, v in h.items() if k in DEFAULTS}} if isinstance(h, dict) else {}


def background_on(config: Dict[str, Any]) -> bool:
    return bool(bg_cfg(config).get("background"))


def _spawn(job: Path) -> None:
    kw: Dict[str, Any] = {"creationflags": _DETACHED} if sys.platform == "win32" else {"start_new_session": True}
    log_path = JOB_DIR / "worker.log"
    rotate_log_if_oversized(log_path, max_mb=1, keep=1)
    with open(log_path, "a", encoding="utf-8", newline="\n") as log:
        subprocess.Popen([sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--job", str(job)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log, close_fds=True, **kw)


def on_stop(session_id: str, transcript_path: str, cwd: str, turn: int, config: Dict[str, Any], spawn=None) -> bool:
    """收尾送背景收割：寫工作檔、起背景、留帳 queued。回 True＝送出（呼叫端記這回合已收割、不擋）；起不來回 False 並浮 stderr。"""
    cfg = bg_cfg(config)
    try:
        JOB_DIR.mkdir(parents=True, exist_ok=True)
        cutoff = time.time() - STALE_S
        for p in JOB_DIR.glob("*.json"):
            if p.stat().st_mtime < cutoff:
                p.unlink(missing_ok=True)
        job = JOB_DIR / f"{session_id or 'nosession'}-{uuid.uuid4().hex[:8]}.json"
        job.write_text(json.dumps({"session": session_id, "transcript": transcript_path, "cwd": cwd, "turn": turn,
                                   "cfg": cfg}, ensure_ascii=False),
                       encoding="utf-8", newline="\n")
        (spawn or _spawn)(job)
    except Exception as e:  # noqa: BLE001
        print(f"{TAG} 送背景收割失敗（這回合沒收割）：{type(e).__name__}: {e}", file=sys.stderr)
        append_guard_log(LEDGER, {"event": "failed", "session_id": session_id, "turn_seq": turn,
                                  "why": f"spawn {type(e).__name__}: {e}"[:300]})
        return False
    append_guard_log(LEDGER, {"event": "queued", "session_id": session_id, "turn_seq": turn})
    return True


# ─── 背景 ────────────────────────────────────────────────────────────────

def transcript_tail(path: str, limit: int = TAIL_CHARS) -> str:
    """使用者打的字與 AI 回覆文字（不含工具輸入輸出、thinking），由後往前取到 limit 字。"""
    rows: List[str] = []
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for raw in lines:
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if d.get("type") not in ("user", "assistant"):
            continue
        content = (d.get("message") or {}).get("content")
        texts = [content] if isinstance(content, str) else [c.get("text", "") for c in content or []
                                                           if isinstance(c, dict) and c.get("type") == "text"]
        for t in texts:
            t = (t or "").strip()
            if t:
                rows.append(f"{'使用者' if d['type'] == 'user' else 'AI'}：{t}")
    out, used = [], 0
    for r in reversed(rows):
        if used + len(r) > limit:
            break
        out.append(r)
        used += len(r)
    return "\n".join(reversed(out))


def progress_targets(session: str, turn: int) -> List[Dict[str, Any]]:
    """這個回合程式替目標樹記了進度（history what=progress、by=program）、還沒有草稿的節點：[{node, text, files}]。"""
    import wg_need_goal as ng
    try:
        doc = ng.load(session)
    except Exception as e:  # noqa: BLE001
        print(f"{TAG} 讀目標樹失敗（不草擬進度）：{type(e).__name__}: {e}", file=sys.stderr)
        return []
    out = []
    for tree in (doc.get("trees") or {}).values():
        for nid, node in (tree.get("nodes") or {}).items():
            hist = node.get("history") or []
            last = hist[-1] if hist else {}
            if last.get("what") == "progress" and last.get("by") == "program" and int(last.get("turn") or 0) == turn:
                out.append({"node": nid, "text": node.get("text") or "", "files": [str(last.get("why") or "")[:120]]})
    return out


def build_prompt(tail: str, progress: List[Dict[str, Any]], max_cards: int) -> str:
    nodes = "\n".join(f"- {p['node']}：{p.get('text') or ''}（改了 {'、'.join(p.get('files') or [])}）" for p in progress)
    return (
        "你在幫一個寫程式的 AI 做收尾記帳。下面是這次對話的尾段。只輸出 JSON，不要其他文字。\n"
        f"1. candidates：最多 {max_cards} 條「從程式碼和文件讀不出來、之後會重查或重犯」的知識（使用者的指正、查了才懂的機制、"
        "做過的取捨）。一次性的事實、照抄程式碼的不要。沒有就給空陣列。每條 {\"title\": 一句話標題, \"knowledge\": 一到三句, "
        "\"why\": 為什麼值得記}。\n"
        + (f"2. progress：下面每個目標節點寫一句「這次改動讓它更接近了沒、為什麼」，{{\"node\": 節點編號, \"line\": 一句}}。\n{nodes}\n"
           if progress else "2. progress：給空陣列。\n")
        + "用繁體中文。\n\n對話尾段：\n" + tail
    )


def parse_reply(text: str, max_cards: int) -> Dict[str, List[Dict[str, str]]]:
    """模型回的 JSON → {candidates, progress}，欄位不齊的丟掉。不是 JSON 往外拋 ValueError。"""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        raise ValueError("回覆裡沒有 JSON")
    d = json.loads(m.group(0))
    if not isinstance(d, dict) or not ({"candidates", "progress"} & set(d)):
        raise ValueError("回覆的 JSON 沒有 candidates／progress（沒照要求作答）")
    cands = [{"title": str(c.get("title")).strip(), "knowledge": str(c.get("knowledge")).strip(), "why": str(c.get("why") or "").strip()}
             for c in d.get("candidates") or [] if isinstance(c, dict) and c.get("title") and c.get("knowledge")]
    prog = [{"node": str(p.get("node")).strip(), "line": str(p.get("line")).strip()}
            for p in d.get("progress") or [] if isinstance(p, dict) and p.get("node") and p.get("line")]
    return {"candidates": cands[:max_cards], "progress": prog}


def candidate_dir(cwd: str) -> Path:
    """專案有 .claude/memory → 專案待審區；沒有 → 資料根 memory/_staging/harvest-candidates/。"""
    from wg_core import find_project_root
    root = find_project_root(cwd) if cwd else None
    mem = Path(root) / ".claude" / "memory" if root else None
    if mem is not None and mem.is_dir() and mem.resolve() != (CLAUDE_DIR / "memory").resolve():
        return mem / "shared" / "_pending_review"
    return CLAUDE_DIR / "memory" / "_staging" / "harvest-candidates"


def write_candidates(cands: List[Dict[str, str]], cwd: str, session: str, model: str) -> List[str]:
    if not cands:
        return []
    d = candidate_dir(cwd)
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    written = []
    for i, c in enumerate(cands, 1):
        p = d / f"harvest-{stamp}-{session[:8] or 'nosid'}-{i}.md"
        p.write_text(
            f"# {c['title']}\n\n- Scope: 待審（背景收割候選，{model} 草擬；核可前不注入）\n- Source: session {session}\n\n"
            f"## 知識\n\n- [臨] {c['knowledge']}\n\n## 為什麼記\n\n{c['why'] or '（模型沒寫）'}\n",
            encoding="utf-8", newline="\n")
        written.append(str(p))
    return written


def write_progress(session: str, turn: int, drafts: List[Dict[str, str]], model: str) -> int:
    if not drafts:
        return 0
    import wg_need_goal as ng

    def fn(doc: Dict[str, Any]) -> int:
        n = 0
        for dft in drafts:
            tree = ng.tree_of(doc, dft["node"])
            if not tree:
                continue
            tree["nodes"][dft["node"]]["history"].append({"seq": ng.next_seq(doc), "turn": turn, "what": "progress_draft",
                                                          "by": "local_llm", "model": model, "why": dft["line"][:300]})
            n += 1
        return n
    return ng.update_locked(session, fn)


def ask_model(prompt: str, cfg: Dict[str, Any]) -> str:
    sys.path.insert(0, str(_HOOKS.parent / "tools"))
    from ollama_client import get_client
    return get_client().generate(prompt, model=str(cfg.get("background_model")), format="json",
                                 timeout=int(cfg.get("background_timeout_sec") or 180), think=False)


def run_job(job_path: Path, ask=ask_model) -> int:
    if sys.stderr is None:
        sys.stderr = open(JOB_DIR / "worker.log", "a", encoding="utf-8", newline="\n")
    job: Dict[str, Any] = {}
    try:
        job = json.loads(job_path.read_text(encoding="utf-8"))
        cfg, session, turn = job.get("cfg") or DEFAULTS, str(job.get("session") or ""), int(job.get("turn") or 0)
        max_cards = int(cfg.get("background_max_cards") or 3)
        tail = transcript_tail(str(job.get("transcript") or ""))
        if not tail:
            raise ValueError("transcript 讀不到或是空的")
        targets = progress_targets(session, turn)
        reply = ask(build_prompt(tail, targets, max_cards), cfg)
        if not reply:
            raise ValueError(f"本地模型 {cfg.get('background_model')} 沒回（不在、逾時或被停用）")
        got = parse_reply(reply, max_cards)
        cards = write_candidates(got["candidates"], str(job.get("cwd") or ""), session, str(cfg.get("background_model")))
        asked = {t["node"] for t in targets}       # 模型順手多寫的節點不收：只收有問的
        drafts = write_progress(session, turn, [d for d in got["progress"] if d["node"] in asked],
                                str(cfg.get("background_model")))
        append_guard_log(LEDGER, {"event": "done", "session_id": session, "turn_seq": turn, "cards": cards,
                                  "progress_drafts": drafts, "model": cfg.get("background_model")})
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"{TAG} 背景收割沒做成：{type(e).__name__}: {e}", file=sys.stderr)
        append_guard_log(LEDGER, {"event": "failed", "session_id": job.get("session"), "turn_seq": job.get("turn"),
                                  "why": f"{type(e).__name__}: {e}"[:300]})
        return 2
    finally:
        job_path.unlink(missing_ok=True)


def staged_count() -> int:
    """資料根待審的背景收割候選份數（開場提示用）。"""
    d = CLAUDE_DIR / "memory" / "_staging" / "harvest-candidates"
    try:
        return sum(1 for _ in d.glob("harvest-*.md")) if d.is_dir() else 0
    except OSError:
        return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--job":
        sys.exit(run_job(Path(sys.argv[2])))
    print(__doc__)
    sys.exit(2)
