"""verify_failure_skeleton.py — 失敗記錄多區塊骨架。

驗證 extract-worker 的失敗深記骨架（取代舊「- [臨] 一行」）：
  - _build_failure_skeleton 必含五區塊標題：始末/根因/設計原理/運作邏輯/防再犯
  - 「（根因: …）」能從 LLM content 拆出 → 填入根因區、始末區排除之
  - 無根因標註 → 根因區留「待補」標記
  - 設計原理/運作邏輯/防再犯 三段一律留「待補」給 Claude 深寫
  - _failure_dedup_hit 對新骨架始末行 + 舊單行格式皆能去重
  - _failure_writeback 端到端：新建檔含五區塊、二次同條被去重不重寫

對應修補：extract-worker.py _build_failure_skeleton / _split_root_cause /
_failure_dedup_hit / _failure_writeback / _create_failure_atom（補「失敗只寫一行、
根因與設計脈絡全丟」缺口）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

# 連字號檔名（extract-worker.py）無法 import，用 importlib 以路徑載入
_spec = importlib.util.spec_from_file_location(
    "extract_worker", HOOKS_DIR / "extract-worker.py")
ew = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ew)


# ─── 骨架結構 ────────────────────────────────────────────────────────

def test_skeleton_has_five_sections():
    """五區塊標題（始末/根因/設計原理/運作邏輯/防再犯）全在。"""
    block = ew._build_failure_skeleton("觸發 → 錯 → 對", [], "2026-06-17")
    for sect in ("始末", "根因", "設計原理", "運作邏輯", "防再犯"):
        assert sect in block, f"缺區塊：{sect}"
    # 與宣告常數同步
    for sect in ew._FAILURE_SKELETON_SECTIONS:
        assert sect in block


def test_skeleton_tags_rendered():
    """domain_tags 以 #tag 形式入標題行。"""
    block = ew._build_failure_skeleton("X → Y → Z", ["memory-system", "git"], "2026-06-17")
    assert "#memory-system" in block
    assert "#git" in block


# ─── 根因拆解 ────────────────────────────────────────────────────────

def test_root_cause_parsed_into_section():
    """content 尾端「（根因: …）」→ 拆入根因區，始末不含該尾段。"""
    content = "改 config 沒重啟 → 設定沒生效 → 改完重啟服務（根因: 設定快取在啟動時讀）"
    narrative, root = ew._split_root_cause(content)
    assert root == "設定快取在啟動時讀"
    assert "根因" not in narrative  # 敘事段已排除根因標註
    block = ew._build_failure_skeleton(content, [], "2026-06-17")
    assert "- **根因**：設定快取在啟動時讀" in block
    assert "- **始末**：" + narrative in block


def test_root_cause_halfwidth_paren():
    """半形括號 (根因: ...) 也能拆。"""
    _, root = ew._split_root_cause("a → b → c (根因: 半形也行)")
    assert root == "半形也行"


def test_no_root_cause_leaves_todo():
    """無根因標註 → 根因區留待補標記、始末為原文。"""
    narrative, root = ew._split_root_cause("只是描述沒有根因標註")
    assert root == ""
    assert narrative == "只是描述沒有根因標註"
    block = ew._build_failure_skeleton("只是描述沒有根因標註", [], "2026-06-17")
    assert f"- **根因**：{ew._FAILURE_TODO_MARK}" in block


def test_three_sections_always_todo():
    """設計原理/運作邏輯/防再犯 一律留待補給 Claude（即使有根因）。"""
    block = ew._build_failure_skeleton("a → b → c（根因: r）", [], "2026-06-17")
    for sect in ("設計原理", "運作邏輯", "防再犯"):
        assert f"- **{sect}**：{ew._FAILURE_TODO_MARK}" in block


# ─── 去重 ────────────────────────────────────────────────────────────

def test_dedup_hit_new_skeleton_format():
    """既有檔含同條始末行 → 判重複。"""
    content = "資料庫連線池沒設上限 → 高峰耗盡連線 → 設 max_pool（根因: 預設無限）"
    existing = ew._build_failure_skeleton(content, [], "2026-06-17")
    assert ew._failure_dedup_hit(existing, content) is True


def test_dedup_hit_legacy_single_line():
    """舊版「- [臨] …」單行格式 backward-compat 也能判重複。"""
    content = "正則回溯造成嚴重效能問題需改寫表達式避免災難性回溯情形"
    legacy = f"- [臨] {content}  #perf  (2026-01-01)"
    assert ew._failure_dedup_hit(legacy, content) is True


def test_dedup_miss_distinct_content():
    """完全不同內容 → 不判重複。"""
    existing = ew._build_failure_skeleton("容器映像未多階段建構導致體積過大", [], "2026-06-17")
    assert ew._failure_dedup_hit(existing, "前端路由改懶載入縮短首屏時間提升體驗") is False


# ─── 端到端 writeback ────────────────────────────────────────────────

@pytest.fixture
def patched_dir(monkeypatch, tmp_path):
    """把 failures_dir 導向 tmp、write_raw 改真寫 tmp 檔（不過 funnel）。"""
    monkeypatch.setattr(ew, "resolve_failures_dir", lambda cwd: tmp_path)

    class _Res:
        ok = True
        error = ""

    def fake_write_raw(path, text, source="", op=""):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text, encoding="utf-8")
        return _Res()

    monkeypatch.setattr(ew, "write_raw", fake_write_raw)
    return tmp_path


def test_writeback_creates_skeleton_file(patched_dir):
    """首次寫入 → 建檔且含五區塊。"""
    item = {
        "content": "改 hook 沒清 pyc → 跑到舊碼 → 清 __pycache__（根因: import 快取）",
        "failure_type": "env",
        "domain_tags": ["hooks"],
    }
    ew._failure_writeback({"cwd": "", "config": {}}, [item])
    # 主題＝classify 命中或 failure_type_fallback（env → OS-Windows）；檔名帶主題 slug
    target = patched_dir / "OS-Windows" / "env-traps-os-windows.md"
    assert target.exists(), sorted(p.as_posix() for p in patched_dir.rglob("*.md"))
    text = target.read_text(encoding="utf-8")
    for sect in ("始末", "根因", "設計原理", "運作邏輯", "防再犯"):
        assert sect in text, f"檔內缺區塊：{sect}"
    assert "import 快取" in text  # 根因被拆入


def test_writeback_dedup_second_time(patched_dir):
    """同條寫兩次 → 第二次被去重，檔內只一個始末。"""
    item = {
        "content": "靜默吞掉例外 → 結果沒寫入卻不報錯 → 移除裸 except（根因: bare except）",
        "failure_type": "silent",
        "domain_tags": [],
    }
    ctx = {"cwd": "", "config": {}}
    ew._failure_writeback(ctx, [item])
    ew._failure_writeback(ctx, [item])
    # silent → fallback 主題 驗證與實證
    target = patched_dir / "驗證與實證" / "silent-failures-驗證與實證.md"
    text = target.read_text(encoding="utf-8")
    assert text.count("**始末**") == 1


# ─── provenance：reader 保留來源識別、萃取項對回原段、骨架寫 src 註解 ─────────

import json as _json

_SID = "127e56a5-eba1-4a53-bdc2-2b960666ddf5"
_SEG_A = ("PreToolUse 閘門把 tools/usage-snapshot 的 LF 檢查誤判成 CRLF 違規，"
          "因為 verify_lf_writes 讀的是 git index 而不是工作樹內容，重跑 run_verify 就會浮出。")
_SEG_B = ("Ollama 向量服務啟動時 LanceDB 的 schema 版本不合，vector_service 會靜默退回純 BM25，"
          "統計裡 vector_hits 恆 0 卻沒有任何警告訊號。")


def _write_transcript(tmp_path, rows):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(_json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def _assistant(text, uuid="", ts="2026-09-21T06:42:45.711Z"):
    row = {"type": "assistant", "timestamp": ts,
           "message": {"content": [{"type": "text", "text": text}]}}
    if uuid:
        row["uuid"] = uuid
    return row


def test_reader_keeps_record_uuid_and_offset(tmp_path):
    """每段帶 transcript 紀錄 uuid/ts；user 列、短文字跳過；缺 uuid 留空不補造；
    max_chars 中斷後 final_offset 仍前進（舊版 for-in 迭代中 tell() 會炸、offset 退回原值）。"""
    rows = [
        {"type": "user", "uuid": "u-1", "message": {"content": "使用者說了一段夠長的話但不是 assistant 不該被讀進來"}},
        _assistant(_SEG_A, uuid="aaaaaaaa-1111"),
        _assistant("短", uuid="bbbbbbbb-2222"),
        _assistant(_SEG_B),  # 無 uuid
        _assistant("第三段夠長的 assistant 文字，用來確認 max_chars 中斷後 offset 有前進。" * 2,
                   uuid="cccccccc-3333"),
    ]
    p = _write_transcript(tmp_path, rows)
    segs, off = ew._read_assistant_segments(p)
    assert [s["uuid"] for s in segs] == ["aaaaaaaa-1111", "", "cccccccc-3333"]
    assert segs[0]["ts"].startswith("2026-09-21") and segs[0]["text"] == _SEG_A
    assert off == p.stat().st_size
    # 舊介面仍是純文字清單
    texts, off2 = ew._extract_all_assistant_texts(p)
    assert texts == [s["text"] for s in segs] and off2 == off
    # max_chars 命中即停：offset 要落在第二段之後、檔尾之前，且能從該處續讀到第三段
    segs_cut, off_cut = ew._read_assistant_segments(p, max_chars=len(_SEG_A) + 10)
    assert [s["uuid"] for s in segs_cut] == ["aaaaaaaa-1111", ""]
    assert 0 < off_cut < p.stat().st_size
    rest, _ = ew._read_assistant_segments(p, byte_offset=off_cut)
    assert [s["uuid"] for s in rest] == ["cccccccc-3333"]


def test_attach_sources_resolves_or_leaves_empty():
    """對得回 → sources=[sid8#uuid8]；對不回 → []（不補造）；LLM 沒看到的段不可當來源。"""
    segs = [{"text": _SEG_A, "uuid": "aaaaaaaa-1111", "ts": ""},
            {"text": _SEG_B, "uuid": "bbbbbbbb-2222", "ts": ""}]
    items = [
        {"content": "verify_lf_writes 讀 git index 不讀工作樹 → tools/usage-snapshot LF 被誤判 CRLF 違規 → 改讀工作樹（根因: PreToolUse 閘門資料來源錯）"},
        {"content": "LanceDB schema 版本不合 → vector_service 靜默退回 BM25、vector_hits 恆 0 → 啟動時檢查 schema 並告警（根因: 無警告訊號）"},
        {"content": "煮雞湯火候太大 → 湯變濁 → 轉小火慢燉（根因: 沸騰過度）"},
    ]
    ew._attach_failure_sources(items, segs, _SID, 3000)
    assert items[0]["sources"] == ["127e56a5#aaaaaaaa"]
    assert items[1]["sources"] == ["127e56a5#bbbbbbbb"]
    assert items[2]["sources"] == [] and items[2]["source_session"] == "127e56a5"
    # 第二段在 3000 字窗之外（LLM 沒看到）→ 不得成為來源
    far = [{"text": "x" * 3100, "uuid": "ffffffff-0000", "ts": ""}] + segs
    items2 = [{"content": items[1]["content"]}]
    ew._attach_failure_sources(items2, far, _SID, 3000)
    assert items2[0]["sources"] == []
    # 段缺 uuid → 沒有識別可引用，不得寫出「#」空殼
    nouuid = [{"text": _SEG_B, "uuid": "", "ts": ""}]
    items3 = [{"content": items[1]["content"]}]
    ew._attach_failure_sources(items3, nouuid, _SID, 3000)
    assert items3[0]["sources"] == []


def test_skeleton_src_comment_modes():
    """有來源 → `<!-- src: … -->`；對不回 → 明示 unresolved；呼叫端沒做對回 → 無來源行。
    註解行不是 `- ` 開頭、不干擾 _failure_dedup_hit。"""
    with_src = ew._build_failure_skeleton("A → B → C", [], "2026-09-21",
                                          sources=["127e56a5#aaaaaaaa"], source_session="127e56a5")
    lines = with_src.split("\n")
    i = next(i for i, ln in enumerate(lines) if "**始末**" in ln)
    assert lines[i + 1].strip() == "<!-- src: 127e56a5#aaaaaaaa -->"
    assert not lines[i + 1].lstrip().startswith("- ")
    unresolved = ew._build_failure_skeleton("A → B → C", [], "2026-09-21",
                                            sources=[], source_session="127e56a5")
    assert "<!-- src: 127e56a5#unresolved 未對回原句 -->" in unresolved
    plain = ew._build_failure_skeleton("A → B → C", [], "2026-09-21")
    assert "<!--" not in plain
    # 沒 session 也沒來源 → 不寫任何 src 行（沒有可核對的東西就不寫）
    assert "<!--" not in ew._build_failure_skeleton("A → B → C", [], "2026-09-21", sources=[])
    assert ew._failure_dedup_hit(with_src, "A → B → C")


def test_writeback_persists_src_and_still_dedups(patched_dir):
    item = {
        "content": "改 hook 沒清 pyc → 跑到舊碼 → 清 __pycache__（根因: import 快取）",
        "failure_type": "env", "domain_tags": ["hooks"],
        "sources": ["127e56a5#aaaaaaaa"], "source_session": "127e56a5",
    }
    ctx = {"cwd": "", "config": {}}
    ew._failure_writeback(ctx, [item])
    ew._failure_writeback(ctx, [item])
    target = patched_dir / "OS-Windows" / "env-traps-os-windows.md"
    text = target.read_text(encoding="utf-8")
    assert text.count("<!-- src: 127e56a5#aaaaaaaa -->") == 1
    assert text.count("**始末**") == 1
