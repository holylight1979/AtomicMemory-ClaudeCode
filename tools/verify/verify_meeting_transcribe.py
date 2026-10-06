"""verify_meeting_transcribe.py — tools/meeting-transcribe.py 流程驗證（不碰 GPU、不打 Ollama）。

辨識器與摘要器都用 mock；ffmpeg 有裝才跑真轉檔／靜音切段（沒裝 → 那幾條 skip 並明示）。
cases：
  1. parse_silences / plan_chunks：切點落在靜音中點、不超過上限、尾段合併、無靜音硬切
  2. clean_transcript：段尾回音的指令被截掉
  3. parse_summary_json：code fence／前後廢話容忍；缺鍵補空陣列；不是 JSON → ValueError
  4. pick_audio_backend：依優先序挑第一個有 audio 能力的；都沒有 → None + 每個 backend 的原因
  5. ingest_decisions：分得出範疇 → shared/<Lv1>/；分不出 → shared/_pending_review/；
     無標題 → ok=False 帶原因；write_atom 失敗 → 回 error 不吞
  6. 端到端（mock 辨識＋mock 摘要，ffmpeg 真轉檔）：合成 wav → transcript.md／summary.md 落
     <專案>/.claude/memory/_staging/meetings/<日期-標題>/、--json 結構、--no-ingest 不寫 atom
  7. 失敗訊號：沒有音訊 backend → exit 1 + stderr 說明；音檔不存在 → exit 1
"""
from __future__ import annotations

import importlib.util
import json
import math
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("meeting_transcribe", CLAUDE_DIR / "tools" / "meeting-transcribe.py")
mt = importlib.util.module_from_spec(_spec)
sys.modules["meeting_transcribe"] = mt
_spec.loader.exec_module(mt)

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe 不在 PATH（真轉檔與切段略過）")


# ---------------------------------------------------------------------------
# 1. 切段
# ---------------------------------------------------------------------------

def test_parse_silences_pairs_start_end():
    err = ("[silencedetect] silence_start: 3.0\n[silencedetect] silence_end: 4.0 | silence_duration: 1.0\n"
           "[silencedetect] silence_start: 10.5\n")       # 最後一個沒有 end（檔尾靜音）→ 不成對、丟掉
    assert mt.parse_silences(err) == [(3.0, 4.0)]


def test_plan_chunks_cuts_at_silence_midpoint_within_window():
    silences = [(50.0, 51.0), (110.0, 112.0), (170.0, 171.0)]
    chunks = mt.plan_chunks(300.0, silences, 120.0)
    # 第一刀：(60,120] 內最靠後的靜音中點 = 111.0；剩 189 > 150 → 第二刀 (171,231] 無靜音 → 硬切 231；剩 69 → 到底
    assert chunks == [(0.0, 111.0), (111.0, 231.0), (231.0, 300.0)]
    assert all(e - s <= 120.0 * 1.25 + 1e-9 for s, e in chunks)
    assert chunks[0][0] == 0.0 and chunks[-1][1] == 300.0


def test_plan_chunks_short_file_is_single_chunk():
    assert mt.plan_chunks(100.0, [(30.0, 31.0)], 180.0) == [(0.0, 100.0)]


def test_plan_chunks_no_silence_hard_cuts():
    # 剩 150 > 125 仍切；剩 50 才併到底
    assert mt.plan_chunks(250.0, [], 100.0) == [(0.0, 100.0), (100.0, 200.0), (200.0, 250.0)]


# ---------------------------------------------------------------------------
# 2. 回音截除
# ---------------------------------------------------------------------------

def test_clean_transcript_strips_prompt_echo():
    text = "各位好，今天開會。" + mt.TRANSCRIBE_PROMPT
    assert mt.clean_transcript(text) == "各位好，今天開會。"
    assert mt.clean_transcript("  純逐字稿  ") == "純逐字稿"


# ---------------------------------------------------------------------------
# 3. 摘要 JSON
# ---------------------------------------------------------------------------

def test_parse_summary_json_tolerates_fence_and_fills_missing():
    raw = "好的，以下是摘要：\n```json\n{\"decisions\": [{\"title\": \"A\"}]}\n```\n以上。"
    d = mt.parse_summary_json(raw)
    assert d["decisions"] == [{"title": "A"}] and d["todos"] == [] and d["open_questions"] == []


def test_parse_summary_json_rejects_non_json():
    with pytest.raises(ValueError):
        mt.parse_summary_json("我無法產生摘要")
    with pytest.raises(ValueError):
        mt.parse_summary_json('{"decisions": "not a list"}')


# ---------------------------------------------------------------------------
# 4. backend 挑選
# ---------------------------------------------------------------------------

def test_pick_audio_backend_first_with_audio_capability():
    bs = [mt.Backend("local", "http://127.0.0.1:11434", "qwen3:1.7b"),
          mt.Backend("gpu", "http://10.0.0.2:11434", "gemma4:e4b"),
          mt.Backend("other", "http://10.0.0.3:11434", "gemma4:e4b")]
    caps = {"http://127.0.0.1:11434": None, "http://10.0.0.2:11434": ["completion", "audio"], "http://10.0.0.3:11434": ["completion", "audio"]}
    picked, notes = mt.pick_audio_backend("gemma4:e4b", bs, caps_fn=lambda url, m: caps[url])
    assert picked.name == "gpu"
    assert "連不上或沒有" in notes[0] and "audio OK" in notes[1] and len(notes) == 2


def test_pick_audio_backend_none_reports_each_reason():
    bs = [mt.Backend("a", "http://a:1", None), mt.Backend("b", "http://b:1", None)]
    caps = {"http://a:1": None, "http://b:1": ["completion", "vision"]}
    picked, notes = mt.pick_audio_backend("gemma4:e4b", bs, caps_fn=lambda url, m: caps[url])
    assert picked is None
    assert "連不上" in notes[0] and "沒有 audio 能力" in notes[1]


# ---------------------------------------------------------------------------
# 5. 入庫
# ---------------------------------------------------------------------------

@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / ".claude" / "memory" / "shared").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    (root / ".claude" / "memory" / "shared" / "_taxonomy.json").write_text(json.dumps(
        {"version": 1, "domains": {"網路登入": {"desc": "登入、token"}}}, ensure_ascii=False), encoding="utf-8")
    return root


def _meta(project: Path) -> dict:
    return {"title": "週會", "date": "2026-10-06",
            "transcript": str(project / ".claude" / "memory" / "_staging" / "meetings" / "x" / "transcript.md")}


def test_project_domains_project_first_then_core(project: Path):
    d = mt.project_domains(project)
    keys = list(d)
    assert keys[0] == "網路登入" and d["網路登入"] == "登入、token"
    assert "工作流" in keys and keys.index("工作流") > 0


def test_ingest_routes_classified_pending_and_reports_errors(project: Path):
    decisions = [
        {"title": "Token 過期改 24 小時", "detail": "登入 token 由 2 小時改 24 小時", "owner": "阿凱",
         "domain": "網路登入", "triggers": ["token", "過期"]},
        {"title": "商城折扣活動十一月上線", "detail": "需三張活動主圖", "domain": "", "triggers": ["商城"]},
        {"title": "", "detail": "無標題"},
    ]
    res = mt.ingest_decisions(project, _meta(project), decisions, mt.project_domains(project), dry_run=False)
    assert [r["ok"] for r in res] == [True, True, False]
    a, b, c = res
    assert a["domain"] == "網路登入" and not a["pending_review"]
    assert Path(a["path"]).is_relative_to(project / ".claude" / "memory" / "shared" / "網路登入")
    body = Path(a["path"]).read_text(encoding="utf-8")
    assert "[臨]" in body and "阿凱" in body and _meta(project)["transcript"] in body
    assert b["pending_review"] and "_pending_review" in b["path"]
    assert "沒有標題" in c["error"]


def test_ingest_surfaces_writer_failure(project: Path):
    class R:  # 模擬 write_atom 失敗
        ok, path, error = False, None, "write gate: duplicate"
    res = mt.ingest_decisions(project, _meta(project), [{"title": "X", "domain": "", "triggers": ["x"]}],
                              {}, dry_run=False, writer=lambda **kw: R())
    assert res[0]["ok"] is False and res[0]["error"] == "write gate: duplicate"


# ---------------------------------------------------------------------------
# 6. 端到端（mock 辨識＋摘要）
# ---------------------------------------------------------------------------

def _tone_wav(path: Path, seconds: float = 3.0, rate: int = 16000) -> None:
    """1 秒 440Hz、1 秒靜音、1 秒 440Hz。"""
    frames = bytearray()
    for i in range(int(seconds * rate)):
        t = i / rate
        amp = 0.4 if (t < 1.0 or t >= 2.0) else 0.0
        frames += struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * 440 * t)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


FAKE_SUMMARY = {"decisions": [{"title": "決議甲", "detail": "內容甲", "owner": "小明", "domain": "網路登入", "triggers": ["甲"]}],
                "todos": [{"item": "待辦乙", "owner": "小華", "due": "週五"}],
                "open_questions": [{"question": "問題丙", "note": ""}]}


@needs_ffmpeg
def test_end_to_end_with_mocks(project: Path, tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "會議.wav"
    _tone_wav(src)
    calls = []
    monkeypatch.setattr(mt, "pick_audio_backend", lambda model, *a, **k: (mt.Backend("mock", "http://mock:1", "mock-llm"), []))
    monkeypatch.setattr(mt, "transcribe_chunk", lambda backend, model, wav, glossary: calls.append(wav) or "這是逐字稿")
    monkeypatch.setattr(mt, "summarize", lambda backend, transcript, domains, glossary, model=None: FAKE_SUMMARY)
    rc = mt.main([str(src), "--project", str(project), "--title", "週會 測試", "--date", "2026-10-06",
                  "--chunk-seconds", "2", "--json"])
    out = capsys.readouterr()
    assert rc == 0, out.err
    res = json.loads(out.out)
    d = project / ".claude" / "memory" / "_staging" / "meetings" / "2026-10-06-週會-測試"
    assert Path(res["transcript"]) == d / "transcript.md" and Path(res["summary"]) == d / "summary.md"
    assert res["chunks"] == len(calls) >= 1
    assert "這是逐字稿" in (d / "transcript.md").read_text(encoding="utf-8")
    smd = (d / "summary.md").read_text(encoding="utf-8")
    assert "決議甲" in smd and "待辦乙" in smd and "問題丙" in smd
    assert res["atoms"][0]["ok"] and res["atoms"][0]["domain"] == "網路登入"
    assert Path(res["atoms"][0]["path"]).exists()


@needs_ffmpeg
def test_no_ingest_writes_nothing(project: Path, tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "m.wav"
    _tone_wav(src)
    monkeypatch.setattr(mt, "pick_audio_backend", lambda model, *a, **k: (mt.Backend("mock", "http://mock:1", "mock-llm"), []))
    monkeypatch.setattr(mt, "transcribe_chunk", lambda *a, **k: "逐字稿")
    monkeypatch.setattr(mt, "summarize", lambda *a, **k: FAKE_SUMMARY)
    rc = mt.main([str(src), "--project", str(project), "--no-ingest", "--json"])
    res = json.loads(capsys.readouterr().out)
    assert rc == 0 and res["atoms"] == []
    assert not list((project / ".claude" / "memory" / "shared").rglob("*.md"))


# ---------------------------------------------------------------------------
# 7. 失敗訊號不靜默
# ---------------------------------------------------------------------------

def test_no_audio_backend_exits_1_with_reason(project: Path, tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "m.wav"
    src.write_bytes(b"RIFF")
    monkeypatch.setattr(mt.shutil, "which", lambda exe: "/usr/bin/" + exe)
    monkeypatch.setattr(mt, "pick_audio_backend", lambda model, *a, **k: (None, ["gpu http://x：連不上或沒有 gemma4:e4b"]))
    rc = mt.main([str(src), "--project", str(project)])
    err = capsys.readouterr().err
    assert rc == 1 and "沒有 backend" in err and "連不上" in err


@needs_ffmpeg
def test_missing_audio_file_exits_1(project: Path, tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(mt, "pick_audio_backend", lambda model, *a, **k: (mt.Backend("mock", "http://mock:1", None), []))
    rc = mt.main([str(tmp_path / "nope.m4a"), "--project", str(project)])
    assert rc == 1 and "找不到音檔" in capsys.readouterr().err
