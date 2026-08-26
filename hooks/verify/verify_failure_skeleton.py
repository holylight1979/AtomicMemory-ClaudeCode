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
