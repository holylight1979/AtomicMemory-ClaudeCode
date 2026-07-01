"""verify_session_end_flush.py — Stage 1：session_end 知識自動落地 flush 編排。

驗證 extract-worker._session_end_writeback 的編排正確性（monkeypatch 攔掉真實
atom 寫入與 classifier，只測我新增的邏輯）：
  - queue 全寫 → 對應 index 全清
  - fresh 先於 queue；fresh 不在 queue 故不清，queue 命中項才清
  - 過短句被濾、不寫不清
  - max_atoms 上限：只寫前 N、只清前 N，其餘留 queue（不丟）
  - 批內重複：第二條跳過寫入但仍標記為已捕捉可清
  - 寫入失敗：不清，留 queue 下次重試
  - enabled=false：完全 no-op

對應修補：extract-worker.py _session_end_writeback / _flush_item_to_atom（補
「session_end 萃取算完即丟、knowledge_queue 從未落地」長期缺口）。
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


# ─── helpers ─────────────────────────────────────────────────────────

# 各 ≥12 字（過 _FLUSH_MIN_LEN）且彼此幾乎無共字，確保不論詞/字級分詞都判「不重複」
_DISTINCT = [
    "資料庫連線池務必設定上限避免耗盡",
    "前端路由改用懶載入縮短首屏時間",
    "容器映像採多階段建構減少體積",
    "正則表達式回溯造成嚴重效能問題",
    "日期時間統一以協調世界儲存",
]


def _item(content, tags=None):
    return {"content": content, "knowledge_type": "factual", "domain_tags": tags or []}


def _ctx(queue, config=None):
    return {"session_id": "sid-test", "knowledge_queue": queue, "config": config or {}}


@pytest.fixture
def patched(monkeypatch):
    """攔截真實副作用：記錄 flush 內容與 ack_then_clear 的 index；classifier 固定非 plan。"""
    calls = {"flushed": [], "cleared": None}

    def fake_flush(content, triggers, **kwargs):
        calls["flushed"].append(content)
        calls.setdefault("scopes", []).append(kwargs.get("scope"))
        return "wrote"

    def fake_ack(state_path, key, indices):
        calls["cleared"] = list(indices)
        return True

    monkeypatch.setattr(ew, "_flush_item_to_atom", fake_flush)
    monkeypatch.setattr(ew, "ack_then_clear", fake_ack)
    monkeypatch.setattr(ew, "classify_extracted_item", lambda it: "knowledge")
    return calls


# ─── 主流程 ──────────────────────────────────────────────────────────

def test_flush_queue_and_clear_indices(patched):
    """queue 兩條相異知識 → 都寫、index [0,1] 都清。"""
    queue = [_item(_DISTINCT[0]), _item(_DISTINCT[1])]
    ew._session_end_writeback(_ctx(queue), {"extracted_items": []})
    assert len(patched["flushed"]) == 2
    assert patched["cleared"] == [0, 1]


def test_fresh_first_then_queue(patched):
    """fresh 先寫；fresh 不在 queue 不清，queue 命中項才清。"""
    fresh = [_item(_DISTINCT[2])]
    queue = [_item(_DISTINCT[3])]
    ew._session_end_writeback(_ctx(queue), {"extracted_items": fresh})
    assert patched["flushed"][0] == _DISTINCT[2]   # fresh 先
    assert len(patched["flushed"]) == 2
    assert patched["cleared"] == [0]               # 只清 queue 第 0 項


# ─── 品質閘 ──────────────────────────────────────────────────────────

def test_too_short_filtered(patched):
    """短於 _FLUSH_MIN_LEN → 不寫、不清。"""
    queue = [_item("短")]
    ew._session_end_writeback(_ctx(queue), {"extracted_items": []})
    assert patched["flushed"] == []
    assert patched["cleared"] is None


# ─── 上限與不丟保證 ──────────────────────────────────────────────────

def test_cap_limits_and_leaves_rest_in_queue(patched):
    """max_atoms=2、5 條相異 → 只寫 2、只清 [0,1]，其餘留 queue 下次再 flush。"""
    cfg = {"response_capture": {"session_end_flush": {"max_atoms": 2}}}
    queue = [_item(c) for c in _DISTINCT]
    ew._session_end_writeback(_ctx(queue, cfg), {"extracted_items": []})
    assert len(patched["flushed"]) == 2
    assert patched["cleared"] == [0, 1]


def test_failed_write_not_cleared(patched, monkeypatch):
    """寫入失敗 → 不清，留 queue。"""
    monkeypatch.setattr(ew, "_flush_item_to_atom", lambda c, t, **kw: "failed")
    queue = [_item(_DISTINCT[0])]
    ew._session_end_writeback(_ctx(queue), {"extracted_items": []})
    assert patched["cleared"] is None


def test_in_batch_dup_marked_cleared(patched):
    """批內重複（同句兩次）→ 只寫一條，但兩個 index 都標記為已捕捉、都清。"""
    same = _DISTINCT[4]
    queue = [_item(same), _item(same)]
    ew._session_end_writeback(_ctx(queue), {"extracted_items": []})
    assert len(patched["flushed"]) == 1
    assert sorted(patched["cleared"]) == [0, 1]


# ─── 開關 ────────────────────────────────────────────────────────────

def test_disabled_noop(patched):
    """enabled=false → 完全 no-op。"""
    cfg = {"response_capture": {"session_end_flush": {"enabled": False}}}
    queue = [_item(_DISTINCT[0])]
    ew._session_end_writeback(_ctx(queue, cfg), {"extracted_items": []})
    assert patched["flushed"] == []
    assert patched["cleared"] is None


# ─── 落點路由端到端 wiring ───────────────────────────

def test_flush_routes_global_when_no_cwd(patched):
    """ctx 無 cwd → 落點 global（_flush_route 預設）。"""
    queue = [_item(_DISTINCT[0])]
    ew._session_end_writeback(_ctx(queue), {"extracted_items": []})
    assert patched["scopes"] == ["global"]


def test_flush_routes_shared_for_project_cwd(patched, monkeypatch):
    """專案 session（cwd 有非 ~/.claude 的 project root）→ 落點 shared、不污染 global core。"""
    monkeypatch.setattr(ew, "find_project_root", lambda c: Path("C:/Projects/Game"))
    queue = [_item(_DISTINCT[0])]
    ctx = _ctx(queue)
    ctx["cwd"] = "C:/Projects/Game/src"
    ew._session_end_writeback(ctx, {"extracted_items": []})
    assert patched["scopes"] == ["shared"]
