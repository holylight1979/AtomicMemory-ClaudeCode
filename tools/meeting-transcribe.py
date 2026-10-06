#!/usr/bin/env python3
"""meeting-transcribe.py — 會議錄音 → 逐字稿 → 三段摘要（決議／待辦／未決）→ 決議入專案記憶。

做什麼：
  1. 任何 ffmpeg 吃得下的音檔（m4a／mp3／wav／mp4…）轉 16kHz 單聲道 wav
  2. 用 ffmpeg 偵測靜音，在靜音處切成 ≤ --chunk-seconds 的段（不切在句子中間）
  3. 每段丟給 Ollama 上有 audio 能力的模型（預設 gemma4:e4b；backend 依 workflow/config.json
     `vector_search.ollama_backends` 優先序挑第一個「有該模型且標 audio」的，本機沒有就用遠端）
     → 逐字稿 `<專案>/.claude/memory/_staging/meetings/<日期-標題>/transcript.md`（含時間戳）
  4. 逐字稿交給同一組 backend 的文字模型做摘要（固定 JSON：決議／待辦／未決問題）
     → `summary.md`
  5. 每條決議寫一顆 atom（scope=shared、[臨]）：分得出範疇（專案 `_taxonomy.json` ∪ 核心 Lv1）
     直接落 `shared/<Lv1>/`；分不出就以 audience=decision 走既有的 `_pending_review` 待審路由。
     逐字稿只留路徑（atom 的 Source 行），不進 atom。不 commit；記憶層由背景 vcs-sync 同步。
  _staging 不進索引、不注入、不進版控（.gitignore）。

怎麼跑：
  python ~/.claude/tools/meeting-transcribe.py 會議.m4a --project C:/TSLG --title 專案週會
  python ~/.claude/tools/meeting-transcribe.py --check            # 只檢查 ffmpeg 與音訊 backend
  python ~/.claude/tools/meeting-transcribe.py 會議.m4a --project C:/TSLG --no-ingest   # 只出逐字稿與摘要
  python ~/.claude/tools/meeting-transcribe.py 會議.m4a --project C:/TSLG --dry-run     # 全跑但 atom 只預覽
  完整參數以 --help 為準。
失敗一律 exit 1 並把原因印到 stderr，不靜默。
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

CLAUDE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CLAUDE_DIR))
sys.path.insert(0, str(CLAUDE_DIR / "tools"))

from lib.atom_io import write_atom  # noqa: E402
from lib.atom_taxonomy import core_categories  # noqa: E402
import ollama_client  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SOURCE = "tool:meeting-transcribe"
DEFAULT_AUDIO_MODEL = "gemma4:e4b"
DEFAULT_CHUNK_SECONDS = 180          # 實測 gemma4:e4b 單次 284s 全文無漏；留餘裕
AUDIO_NUM_CTX = 16384                # 180s 音訊約 4500 token + 逐字稿輸出
SUMMARY_NUM_CTX = 32768
TRANSCRIBE_PROMPT = "請逐字轉錄這段音訊，使用原語言（繁體中文，英文術語保留英文），只輸出逐字稿，不要加任何說明。"
ECHO_MARK = TRANSCRIBE_PROMPT[:10]   # 模型偶爾在段尾把指令重複一遍，看到就截掉

SUMMARY_SYSTEM = """你是會議記錄員。根據逐字稿輸出 JSON（只輸出 JSON，不加說明、不加 code fence）：
{
  "decisions": [{"title": "一句話決議（≤30字）", "detail": "決議內容與理由（1–3句）", "owner": "負責人或空字串",
                  "domain": "從候選範疇挑最貼切的一個，都不合就空字串", "triggers": ["3–6個關鍵詞"],
                  "quote": "逐字稿中直接說出這個決議的那一句原話（≤60字，照抄不改寫），找不到就空字串"}],
  "todos": [{"item": "待辦事項", "owner": "負責人或空字串", "due": "期限或空字串"}],
  "open_questions": [{"question": "未決問題", "note": "何時／依什麼決定，沒有就空字串"}]
}
規則：只寫逐字稿明確說到的，不要補完、不要推測；人名術語照原文；沒有的區塊給空陣列。"""


# ---------------------------------------------------------------------------
# 外部程序與 HTTP
# ---------------------------------------------------------------------------

def _run(cmd: List[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, creationflags=_NO_WINDOW)


def _post_json(url: str, body: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _chat(base_url: str, model: str, messages: List[dict], num_ctx: int, timeout: int = 900) -> dict:
    body = {"model": model, "messages": messages, "stream": False, "think": False,
            "options": {"temperature": 0, "num_ctx": num_ctx}, "keep_alive": "10m"}
    return _post_json(base_url.rstrip("/") + "/api/chat", body, timeout)


# ---------------------------------------------------------------------------
# Backend 挑選
# ---------------------------------------------------------------------------

class Backend(NamedTuple):
    name: str
    base_url: str
    llm_model: Optional[str]


def _candidate_backends() -> List[Backend]:
    """依 workflow/config.json 的 ollama_backends 優先序（priority 小者先）；帶 auth 的不支援、略過。"""
    cfg: dict = {}
    if ollama_client.CONFIG_PATH.exists():
        cfg = json.loads(ollama_client.CONFIG_PATH.read_text(encoding="utf-8"))
    out = []
    for b in sorted(ollama_client._build_backends_from_config(cfg), key=lambda x: x.priority):
        if not b.enabled or b.auth:
            continue
        out.append(Backend(b.name, b.base_url, b.llm_model))
    return out


def model_capabilities(base_url: str, model: str, timeout: int = 10) -> Optional[List[str]]:
    """GET /api/show；模型不存在或 backend 連不上回 None。"""
    try:
        d = _post_json(base_url.rstrip("/") + "/api/show", {"name": model}, timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return None
    return list(d.get("capabilities") or [])


def pick_audio_backend(model: str, backends: Optional[List[Backend]] = None,
                       caps_fn=model_capabilities) -> Tuple[Optional[Backend], List[str]]:
    """第一個「有該模型且 capabilities 含 audio」的 backend；順便回每個 backend 的判定給 --check 印。"""
    notes = []
    for b in backends if backends is not None else _candidate_backends():
        caps = caps_fn(b.base_url, model)
        if caps is None:
            notes.append(f"{b.name} {b.base_url}：連不上或沒有 {model}")
            continue
        if "audio" not in caps:
            notes.append(f"{b.name} {b.base_url}：{model} 沒有 audio 能力（{caps}）")
            continue
        notes.append(f"{b.name} {b.base_url}：{model} audio OK")
        return b, notes
    return None, notes


# ---------------------------------------------------------------------------
# 音訊處理
# ---------------------------------------------------------------------------

def to_wav16k(src: Path, dst: Path) -> None:
    r = _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(dst)])
    if r.returncode != 0 or not dst.exists():
        raise RuntimeError(f"ffmpeg 轉檔失敗：{r.stderr.strip()[-400:]}")


def probe_duration(wav: Path) -> float:
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)])
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe 失敗：{r.stderr.strip()[-400:]}")
    return float(r.stdout.strip())


_SIL_RE = re.compile(r"silence_(start|end): ([0-9.]+)")


def detect_silences(wav: Path, noise_db: int = -35, min_sec: float = 0.4) -> List[Tuple[float, float]]:
    r = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav),
              "-af", f"silencedetect=noise={noise_db}dB:d={min_sec}", "-f", "null", "-"])
    return parse_silences(r.stderr)


def parse_silences(ffmpeg_stderr: str) -> List[Tuple[float, float]]:
    out, start = [], None
    for kind, val in _SIL_RE.findall(ffmpeg_stderr):
        if kind == "start":
            start = float(val)
        elif start is not None:
            out.append((start, float(val)))
            start = None
    return out


def plan_chunks(duration: float, silences: List[Tuple[float, float]], target: float) -> List[Tuple[float, float]]:
    """貪婪切段：每段 ≤ target 秒，切點取 (cur+target/2, cur+target] 內最靠後的靜音中點；
    沒靜音就硬切在 cur+target；剩下不到 1.25×target 就一段到底。"""
    chunks, cur = [], 0.0
    mids = [(s + e) / 2 for s, e in silences]
    while cur < duration:
        if duration - cur <= target * 1.25:
            chunks.append((cur, duration))
            break
        limit = cur + target
        cands = [m for m in mids if cur + target / 2 < m <= limit]
        cut = max(cands) if cands else limit
        chunks.append((cur, cut))
        cur = cut
    return chunks


def cut_chunk(wav: Path, start: float, end: float, dst: Path) -> None:
    r = _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
              "-c", "copy", str(dst)])
    if r.returncode != 0 or not dst.exists():
        raise RuntimeError(f"ffmpeg 切段失敗：{r.stderr.strip()[-400:]}")


def clean_transcript(text: str) -> str:
    """去掉模型在段尾回音的指令文字；只留逐字稿。"""
    i = text.find(ECHO_MARK)
    if i > 0:
        text = text[:i]
    return text.strip()


def transcribe_chunk(backend: Backend, model: str, wav: Path, glossary: List[str]) -> str:
    prompt = TRANSCRIBE_PROMPT
    if glossary:
        prompt += "\n可能出現的人名與術語：" + "、".join(glossary) + "。"
    b64 = base64.b64encode(wav.read_bytes()).decode("ascii")
    d = _chat(backend.base_url, model, [{"role": "user", "content": prompt, "images": [b64]}], AUDIO_NUM_CTX)
    return clean_transcript(d.get("message", {}).get("content", ""))


def fmt_ts(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def render_transcript(meta: dict, parts: List[Tuple[float, float, str]]) -> str:
    lines = [f"# 逐字稿：{meta['title']}（{meta['date']}）", "",
             f"- 來源：{meta['source']}", f"- 長度：{fmt_ts(meta['duration'])}",
             f"- 辨識：{meta['audio_model']} @ {meta['backend']}", f"- 段數：{len(parts)}", ""]
    for s, e, text in parts:
        lines += [f"## [{fmt_ts(s)}–{fmt_ts(e)}]", "", text or "（此段無辨識結果）", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 摘要
# ---------------------------------------------------------------------------

def parse_summary_json(text: str) -> dict:
    """容忍 code fence 與前後廢話：取第一個 { 到最後一個 }。缺鍵補空陣列。"""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        raise ValueError(f"摘要不是 JSON：{text[:200]!r}")
    d = json.loads(t[i:j + 1])
    for k in ("decisions", "todos", "open_questions"):
        d.setdefault(k, [])
        if not isinstance(d[k], list):
            raise ValueError(f"摘要 JSON 的 {k} 不是陣列")
    return d


def summarize(backend: Backend, transcript: str, domains: Dict[str, str], glossary: List[str],
              model: Optional[str] = None) -> dict:
    model = model or backend.llm_model
    if not model:
        raise RuntimeError(f"backend {backend.name} 沒設 llm_model，無法摘要")
    dom_lines = [f"- {k}：{v}" if v else f"- {k}" for k, v in domains.items()]
    user = "候選範疇（前面是專案自訂範疇，優先；後面是通用範疇）：\n" + ("\n".join(dom_lines) or "（無）")
    if glossary:
        user += "\n\n人名與術語以這份清單為準，逐字稿裡的同音錯字請校正：" + "、".join(glossary)
    user += f"\n\n逐字稿：\n{transcript}"
    d = _chat(backend.base_url, model, [{"role": "system", "content": SUMMARY_SYSTEM},
                                        {"role": "user", "content": user}], SUMMARY_NUM_CTX)
    return parse_summary_json(d.get("message", {}).get("content", ""))


def render_summary(meta: dict, s: dict) -> str:
    lines = [f"# 會議摘要：{meta['title']}（{meta['date']}）", "", f"- 逐字稿：{meta['transcript']}", "", "## 決議", ""]
    lines += [f"- **{d.get('title', '')}** — {d.get('detail', '')}" + (f"（負責：{d['owner']}）" if d.get("owner") else "")
              for d in s["decisions"]] or ["- （無）"]
    lines += ["", "## 待辦", ""]
    lines += [f"- [ ] {t.get('item', '')}" + (f" — {t['owner']}" if t.get("owner") else "") + (f"，期限 {t['due']}" if t.get("due") else "")
              for t in s["todos"]] or ["- （無）"]
    lines += ["", "## 未決問題", ""]
    lines += [f"- {q.get('question', '')}" + (f"（{q['note']}）" if q.get("note") else "") for q in s["open_questions"]] or ["- （無）"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 入庫
# ---------------------------------------------------------------------------

def project_domains(project: Path) -> Dict[str, str]:
    """專案 `_taxonomy.json` 的 Lv1（含 desc）在前、核心 Lv1 在後；順序就是分類優先序。"""
    tax = project / ".claude" / "memory" / "shared" / "_taxonomy.json"
    out: Dict[str, str] = {}
    if tax.exists():
        try:
            for k, v in (json.loads(tax.read_text(encoding="utf-8")).get("domains") or {}).items():
                out[k] = (v or {}).get("desc", "") if isinstance(v, dict) else ""
        except (ValueError, OSError) as e:
            print(f"[meeting] 警告：{tax} 讀不了（{e}），只用核心範疇", file=sys.stderr)
    for c in core_categories():
        out.setdefault(c, "")
    return out


def ingest_decisions(project: Path, meta: dict, decisions: List[dict], domains: Dict[str, str],
                     dry_run: bool, writer=write_atom) -> List[dict]:
    """每條決議一顆 atom。回每條的落點或失敗原因（不靜默）。"""
    results = []
    for d in decisions:
        title = (d.get("title") or "").strip()
        if not title:
            results.append({"title": "", "ok": False, "error": "決議沒有標題，跳過"})
            continue
        domain = (d.get("domain") or "").strip()
        classified = domain in domains
        owner = f"負責人：{d['owner']}。" if d.get("owner") else ""
        knowledge = [f"[臨] {d.get('detail') or title}。{owner}（{meta['date']} {meta['title']} 決議）"]
        triggers = [t for t in (d.get("triggers") or []) if isinstance(t, str) and t.strip()] or [title]
        kw: Dict[str, Any] = dict(
            title=title, scope="shared", confidence="[臨]", triggers=triggers, knowledge=knowledge,
            project_cwd=str(project), mode="create", source=SOURCE, dry_run=dry_run,
            provenance=meta["transcript"],
        )
        # Quote：逐字稿裡說出這條決議的原句（模型照抄；沒有就不寫），transcript 檔搬走後仍可回看
        quote_raw = d.get("quote") if isinstance(d.get("quote"), str) else ""
        if quote_raw.strip():
            from lib.provenance import format_quote, sanitize_quote
            q = sanitize_quote(quote_raw)
            if q:
                kw["quote"] = format_quote(q)
        if classified:
            kw["domain"] = domain
            kw["audience"] = ["meeting"]
        else:
            kw["audience"] = ["decision"]          # 既有路由：敏感 audience → shared/_pending_review/
        r = writer(**kw)
        item = {"title": title, "ok": bool(r.ok), "domain": domain if classified else "",
                "pending_review": not classified, "dry_run": dry_run}
        if r.ok:
            item["path"] = str(getattr(r, "path", "") or "")
        else:
            item["error"] = str(getattr(r, "error", "") or "write_atom 失敗")
        results.append(item)
    return results


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def slug(text: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\s]+", "-", text.strip()).strip("-") or "meeting"


def run(args: argparse.Namespace, backend: Backend) -> dict:
    src = Path(args.audio).resolve()
    if not src.is_file():
        raise RuntimeError(f"找不到音檔：{src}")
    project = Path(args.project).resolve()
    if not (project / ".claude").is_dir():
        raise RuntimeError(f"--project {project} 下沒有 .claude/，不是專案根")
    meeting_date = args.date or date.fromtimestamp(src.stat().st_mtime).isoformat()
    title = args.title or src.stem
    out_dir = project / ".claude" / "memory" / "_staging" / "meetings" / f"{meeting_date}-{slug(title)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = out_dir / "transcript.md"
    meta = {"title": title, "date": meeting_date, "source": str(src), "audio_model": args.audio_model,
            "backend": f"{backend.name} {backend.base_url}", "transcript": str(transcript_path)}
    glossary = [g.strip() for g in (args.glossary or "").split(",") if g.strip()]
    t0 = time.time()

    with tempfile.TemporaryDirectory(prefix="meeting-") as tmp:
        tmpd = Path(tmp)
        wav = tmpd / "audio16k.wav"
        print(f"[meeting] 轉檔 → 16kHz wav", file=sys.stderr)
        to_wav16k(src, wav)
        duration = probe_duration(wav)
        meta["duration"] = duration
        chunks = plan_chunks(duration, detect_silences(wav), float(args.chunk_seconds))
        print(f"[meeting] 長度 {fmt_ts(duration)}，切 {len(chunks)} 段，辨識 {args.audio_model} @ {backend.name}", file=sys.stderr)
        parts = []
        for i, (s, e) in enumerate(chunks, 1):
            piece = tmpd / f"chunk{i:03d}.wav"
            cut_chunk(wav, s, e, piece)
            text = transcribe_chunk(backend, args.audio_model, piece, glossary)
            if not text:
                print(f"[meeting] 警告：第 {i} 段（{fmt_ts(s)}–{fmt_ts(e)}）沒有辨識結果", file=sys.stderr)
            parts.append((s, e, text))
            print(f"[meeting]   段 {i}/{len(chunks)} {fmt_ts(s)}–{fmt_ts(e)}：{len(text)} 字", file=sys.stderr)

    transcript_md = render_transcript(meta, parts)
    transcript_path.write_text(transcript_md, encoding="utf-8", newline="\n")
    plain = "\n".join(p[2] for p in parts).strip()
    if not plain:
        raise RuntimeError("整份音檔沒有任何辨識結果；逐字稿已寫出但為空，不做摘要")

    domains = project_domains(project)
    print(f"[meeting] 摘要（{backend.llm_model} @ {backend.name}）", file=sys.stderr)
    summary = summarize(backend, plain, domains, glossary)
    summary_path = out_dir / "summary.md"
    summary_path.write_text(render_summary(meta, summary), encoding="utf-8", newline="\n")

    atoms: List[dict] = []
    if args.no_ingest:
        print("[meeting] --no-ingest：不寫 atom", file=sys.stderr)
    else:
        atoms = ingest_decisions(project, meta, summary["decisions"], domains, args.dry_run)
        for a in atoms:
            tag = "預覽" if a["dry_run"] else ("待審" if a["pending_review"] else "寫入")
            print(f"[meeting]   {tag} {a['title']} → {a.get('path') or a.get('error')}", file=sys.stderr)

    return {"ok": True, "transcript": str(transcript_path), "summary": str(summary_path),
            "duration_sec": round(duration, 1), "chunks": len(chunks), "backend": meta["backend"],
            "audio_model": args.audio_model, "seconds": round(time.time() - t0, 1),
            "decisions": summary["decisions"], "todos": summary["todos"],
            "open_questions": summary["open_questions"], "atoms": atoms}


def cmd_check(model: str) -> int:
    ok = True
    for exe in ("ffmpeg", "ffprobe"):
        p = shutil.which(exe)
        print(f"  - {exe}：{p or '找不到 → winget install Gyan.FFmpeg 或 brew install ffmpeg'}")
        ok &= bool(p)
    backend, notes = pick_audio_backend(model)
    for n in notes:
        print(f"  - {n}")
    if backend is None:
        print(f"  - 沒有任何 backend 能跑 {model}：在有顯卡的 Ollama 主機上 `ollama pull {model}`，"
              f"或把它寫進 workflow/config.json 的 ollama_backends")
        ok = False
    print("[meeting] 結果：" + ("可以跑" if ok else "缺東西，見上"))
    return 0 if ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="會議錄音 → 逐字稿 → 摘要 → 決議入專案記憶")
    ap.add_argument("audio", nargs="?", help="音檔（m4a／mp3／wav／mp4…，ffmpeg 吃得下即可）")
    ap.add_argument("--project", help="專案根（含 .claude/）；逐字稿與 atom 都落在這個專案")
    ap.add_argument("--title", help="會議標題（預設音檔檔名）")
    ap.add_argument("--date", help="會議日期 YYYY-MM-DD（預設音檔修改日）")
    ap.add_argument("--glossary", help="逗號分隔的人名／術語，提高辨識準確度")
    ap.add_argument("--audio-model", default=DEFAULT_AUDIO_MODEL, help=f"Ollama 音訊模型（預設 {DEFAULT_AUDIO_MODEL}）")
    ap.add_argument("--chunk-seconds", type=int, default=DEFAULT_CHUNK_SECONDS, help=f"每段上限秒數（預設 {DEFAULT_CHUNK_SECONDS}）")
    ap.add_argument("--no-ingest", action="store_true", help="只出逐字稿與摘要，不寫 atom")
    ap.add_argument("--dry-run", action="store_true", help="全流程照跑，atom 只預覽落點不寫")
    ap.add_argument("--check", action="store_true", help="只檢查 ffmpeg 與音訊 backend")
    ap.add_argument("--json", action="store_true", help="stdout 只印結果 JSON")
    args = ap.parse_args(argv)

    if args.check:
        return cmd_check(args.audio_model)
    if not args.audio or not args.project:
        ap.error("要給音檔與 --project（或用 --check）")
    for exe in ("ffmpeg", "ffprobe"):
        if not shutil.which(exe):
            print(f"[meeting] 失敗：找不到 {exe}（先跑 --check）", file=sys.stderr)
            return 1
    backend, notes = pick_audio_backend(args.audio_model)
    if backend is None:
        print("[meeting] 失敗：沒有 backend 能跑音訊模型：\n  " + "\n  ".join(notes), file=sys.stderr)
        return 1
    try:
        result = run(args, backend)
    except (RuntimeError, ValueError, urllib.error.URLError, OSError, subprocess.TimeoutExpired) as e:
        print(f"[meeting] 失敗：{e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print(f"[meeting] 完成：逐字稿 {result['transcript']}\n[meeting]       摘要 {result['summary']}")
        print(f"[meeting] 決議 {len(result['decisions'])}、待辦 {len(result['todos'])}、未決 {len(result['open_questions'])}"
              f"；atom 寫入 {sum(1 for a in result['atoms'] if a['ok'] and not a['pending_review'])}"
              f"、待審 {sum(1 for a in result['atoms'] if a['ok'] and a['pending_review'])}"
              f"、失敗 {sum(1 for a in result['atoms'] if not a['ok'])}；{result['seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
