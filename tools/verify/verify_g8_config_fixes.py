"""verify_g8_config_fixes.py：G8 量測報告裡程式端真問題的修補案例（派工 002），每條改前紅、改後綠。

做什麼：
  (c) vcs_sync.exclude：config 缺這段（舊安裝）時，合併後的排除清單也要有 memory/_meta/**。
  (d) 資料根：WG_CLAUDE_DIR 指暫存根時，核心 session 判定、跨 realm 寫入閘、隱私閘的根層 globs、
      vcs_ignore 的「~/.claude 自己的記憶」判定、merge-atom-index 讀的 config 都落在暫存根（各一案；常數在
      import 時決定，所以開子行程量）。
  (b) 三個原本沒人讀的開關：write_gate.enabled=false 跳過品質／去重評分；provenance.quote_max_chars 決定 Quote 截斷長度；
      cross_session.enabled=false 不打向量服務。
  其餘 (c)／(d) 的「各處預設相等、沒有自拼資料根」由 verify_config_consistency 的本樹重跑把關。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_g8_config_fixes.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "hooks"
for _p in (str(ROOT), str(HOOKS), str(ROOT / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ─── (c) vcs_sync.exclude ────────────────────────────────────────────────

def test_vcs_sync_exclude_default_keeps_meta_when_config_lacks_section():
    import wg_vcs_sync
    merged = wg_vcs_sync.vcs_sync_config({})
    assert "**/*.access.json" in merged["exclude"]          # 前置：確實走到預設
    assert "memory/_meta/**" in merged["exclude"]


# ─── (d) 資料根：子行程裡設 WG_CLAUDE_DIR ───────────────────────────────

PROBE = r'''
import importlib.util, json, sys
from pathlib import Path
root, data, proj = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path[:0] = [str(root), str(root / "hooks"), str(root / "lib")]
import wg_core
from handlers.pre_tool_use import _privacy_globs
import vcs_ignore
spec = importlib.util.spec_from_file_location("mai", root / "tools" / "merge-atom-index.py")
mai = importlib.util.module_from_spec(spec); sys.modules["mai"] = mai; spec.loader.exec_module(mai)
print(json.dumps({
    "claude_dir": str(wg_core.CLAUDE_DIR),
    "core_session": wg_core._is_core_session(str(data / "sub")),
    "cross_realm": wg_core.check_cross_realm_write("Write", {"file_path": str(data / "hooks" / "x.py")}, str(proj), {}),
    "privacy_root_globs": "projects/*" in _privacy_globs({}, str(data)),
    "vcs_ignore_own": vcs_ignore.under_claude_dir(data / "memory"),
    "merge_toggles": mai._load_toggles(),
}, ensure_ascii=False))
'''


@pytest.fixture(scope="module")
def probe(tmp_path_factory):
    base = tmp_path_factory.mktemp("g8_data_root")
    data, proj = base / "data", base / "proj"
    (data / "workflow").mkdir(parents=True)
    (data / "sub").mkdir()
    proj.mkdir()
    (data / "workflow" / "config.json").write_text(
        json.dumps({"merge_driver": {"auto_install": False, "auto_resolve": False, "_probe": "tmp"}}), encoding="utf-8")
    env = {**os.environ, "WG_CLAUDE_DIR": str(data)}
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", PROBE, str(ROOT), str(data), str(proj)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=env)
    assert r.returncode == 0, r.stderr[-1500:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert Path(out["claude_dir"]) == data                   # 前置：子行程的資料根確實是暫存根
    return out


def test_core_session_follows_data_root(probe):
    assert probe["core_session"] is True


def test_cross_realm_write_guards_data_root(probe):
    assert probe["cross_realm"] and "CrossRealmWriteBlock" in probe["cross_realm"]


def test_privacy_root_globs_follow_data_root(probe):
    assert probe["privacy_root_globs"] is True


def test_vcs_ignore_own_memory_follows_data_root(probe):
    assert probe["vcs_ignore_own"] is True


def test_merge_atom_index_reads_data_root_config(probe):
    assert probe["merge_toggles"].get("_probe") == "tmp"


# ─── (b) 三個開關接回 ────────────────────────────────────────────────────

LOW_QUALITY = "ok"   # 太短、沒有任何知識訊號：品質閘一定不放行


def test_write_gate_disabled_skips_quality_gate():
    wg = _load("_g8_write_gate", "tools/memory-write-gate.py")
    on = wg.evaluate(LOW_QUALITY, config={"enabled": True, "auto_threshold": 0.5, "ask_threshold": 0.3})
    assert on["action"] != "add"                              # 前置：開著時這段內容不會被放行
    off = wg.evaluate(LOW_QUALITY, config={"enabled": False, "auto_threshold": 0.5, "ask_threshold": 0.3})
    assert off["action"] == "add" and "disabled" in off["reason"]


def test_quote_max_chars_comes_from_config(tmp_path, monkeypatch):
    from lib import provenance
    (tmp_path / "workflow").mkdir()
    (tmp_path / "workflow" / "config.json").write_text(json.dumps({"provenance": {"quote_max_chars": 10}}), encoding="utf-8")
    monkeypatch.setenv("WG_CLAUDE_DIR", str(tmp_path))
    provenance.quote_max_chars.cache_clear()
    try:
        assert len(provenance.sanitize_quote("字" * 50)) == 10
    finally:
        provenance.quote_max_chars.cache_clear()


def test_cross_session_disabled_does_not_query_vector_service(monkeypatch):
    ew = _load("_g8_extract_worker", "hooks/extract-worker.py")
    calls = []

    def fake_urlopen(*a, **k):
        calls.append(a)
        raise OSError("no service in test")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    items = [{"content": "跨 session 去重要看這一段夠長的內容是否出現過"}]
    base = {"vector_search": {"enabled": True, "service_port": 1}}
    ew._cross_session_search(items, "sid12345", {**base, "cross_session": {"enabled": True}})
    assert calls                                              # 前置：開著時確實會打向量服務
    calls.clear()
    assert ew._cross_session_search(items, "sid12345", {**base, "cross_session": {"enabled": False}}) == []
    assert calls == []
