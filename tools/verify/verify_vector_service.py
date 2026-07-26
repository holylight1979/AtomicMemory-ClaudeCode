"""verify_vector_service.py — memory-vector-service 域修復驗證

acceptance：
  1. parse_and_chunk 遙測欄位（last_used/confirmations/readhits）讀 <atom>.access.json
     sidecar（lib.atom_access），不再信 .md frontmatter 的死欄位。
  2. discover_layers 走 atom_search_roots()：local realm（_AIDocs/_atoms/ 階層）
     以 extra:local-atoms layer 進索引；discover_atoms 遞迴撿深層 atom、跳 `_` 前綴檔。
  3. 服務 ThreadingHTTPServer：慢請求不 block /health（starter 不再誤殺健康服務）。
  4. starter._kill_stale_pid：pid 身分（cmdline 指紋）驗不過 → 保守不殺。
  5. _delete_stale_keys：已刪/改名 atom 的殘留 chunk 被清（增量索引順帶清理核心）。
  6. _embed_input：embedding 輸入帶「標題 — 層/domain」contextual prefix，原文欄位不變。

不依賴 Ollama / LanceDB 在線：embed 不實跑、DB 以 fake table 替身。
"""

from __future__ import annotations

import inspect
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude/
SVC_DIR = CLAUDE_DIR / "tools" / "memory-vector-service"
sys.path.insert(0, str(SVC_DIR))

import indexer  # noqa: E402
import reranker  # noqa: E402
import service  # noqa: E402
import starter  # noqa: E402


# ─── 1. 遙測欄位讀 sidecar ───────────────────────────────────────────────────


def _write_atom(md: Path, extra_meta: str = "") -> None:
    md.write_text(
        "# 示例 Atom\n\n- Confidence: [觀]\n" + extra_meta +
        "\n## 知識\n\n- 這是一則足夠長的知識內容，供 chunk 切割使用\n",
        encoding="utf-8",
    )


def test_parse_and_chunk_reads_access_sidecar(tmp_path):
    md = tmp_path / "demo-atom.md"
    # frontmatter 埋舊值（死欄位）：不得被採用
    _write_atom(md, "- Last-used: 2020-01-01\n- ReadHits: 99\n- Confirmations: 42\n")
    (tmp_path / "demo-atom.access.json").write_text(json.dumps({
        "schema": "atom-access-v3",
        "read_hits": 7, "last_used": "2026-07-01", "confirmations": 3,
    }), encoding="utf-8")

    chunks = indexer.parse_and_chunk("global", md, "demo-atom.md")
    assert chunks, "atom 應切出至少 1 個 chunk"
    c = chunks[0]
    assert c["last_used"] == "2026-07-01"
    assert c["confirmations"] == 3
    assert c["readhits"] == 7


def test_parse_and_chunk_defaults_without_sidecar(tmp_path):
    md = tmp_path / "no-sidecar.md"
    _write_atom(md, "- Last-used: 2020-01-01\n- Confirmations: 42\n")
    chunks = indexer.parse_and_chunk("global", md, "no-sidecar.md")
    assert chunks
    assert chunks[0]["last_used"] == ""      # sidecar 缺 → 空，不回落 frontmatter
    assert chunks[0]["confirmations"] == 0
    assert chunks[0]["readhits"] == 0


# ─── 2. local realm atoms 進索引 ─────────────────────────────────────────────


def test_discover_layers_includes_local_atoms_root(tmp_path, monkeypatch):
    local = tmp_path / "_atoms"
    (local / "Tools").mkdir(parents=True)
    monkeypatch.setattr(indexer, "LOCAL_ATOMS_DIR", local)
    monkeypatch.setattr(
        indexer, "atom_search_roots", lambda: [indexer.MEMORY_DIR, local])

    layers = indexer.discover_layers(layer_filter="global")
    assert ("global", indexer.MEMORY_DIR, "recursive") in layers
    assert (indexer.LOCAL_ATOMS_LAYER_LABEL, local, "recursive") in layers


def test_discover_layers_real_env_has_local_label():
    # 真實 ~/.claude：_AIDocs/_atoms/ 存在 → local layer 必在
    labels = [l for l, _p, _k in indexer.discover_layers(layer_filter="global")]
    assert indexer.LOCAL_ATOMS_LAYER_LABEL in labels
    assert indexer.FAILURES_LAYER_LABEL in labels
    assert "global" in labels


def test_discover_atoms_local_hierarchy(tmp_path):
    local = tmp_path / "_atoms"
    (local / "Tools").mkdir(parents=True)
    (local / "MemDev" / "deep").mkdir(parents=True)
    _write_atom(local / "Tools" / "gizmo-tool.md")
    _write_atom(local / "MemDev" / "deep" / "deep-atom.md")
    (local / "Tools" / "_INDEX.md").write_text("# 索引\n", encoding="utf-8")

    atoms = indexer.discover_atoms(
        [(indexer.LOCAL_ATOMS_LAYER_LABEL, local, "recursive")])
    stems = {p.stem for _ln, p, _rp in atoms}
    assert stems == {"gizmo-tool", "deep-atom"}, "遞迴撿 atom、跳 _ 前綴檔"


# ─── 3. ThreadingHTTPServer：/health 不被慢請求 block ────────────────────────


def test_health_not_blocked_by_slow_request(monkeypatch):
    def slow_status(self, params):
        time.sleep(2.0)
        self._send_json({"slow": True})

    monkeypatch.setattr(service.VectorServiceHandler, "_handle_status", slow_status)
    srv = service.ThreadingHTTPServer(("127.0.0.1", 0), service.VectorServiceHandler)
    srv.daemon_threads = True
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        slow = threading.Thread(
            target=lambda: urllib.request.urlopen(
                f"http://127.0.0.1:{port}/status", timeout=10).read(),
            daemon=True)
        slow.start()
        time.sleep(0.3)  # 讓慢請求先佔住 handler
        t0 = time.monotonic()
        body = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health", timeout=5).read()
        elapsed = time.monotonic() - t0
        assert b"ok" in body
        assert elapsed < 1.5, f"/health 被慢請求 block（{elapsed:.2f}s）"
    finally:
        srv.shutdown()
        srv.server_close()


def test_run_server_uses_threading_server():
    src = inspect.getsource(service.run_server)
    assert "ThreadingHTTPServer" in src


# ─── 4. starter pid 身分驗證 ─────────────────────────────────────────────────


def test_kill_stale_pid_refuses_foreign_pid(tmp_path, monkeypatch):
    logs = []
    monkeypatch.setattr(starter, "_slog", lambda msg, *a, **k: logs.append(msg))
    killed = []
    monkeypatch.setattr(starter.os, "kill", lambda pid, sig: killed.append(pid))

    pid_file = tmp_path / "service.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")  # 本 pytest 程序 ≠ 服務
    assert starter._kill_stale_pid(pid_file) is None
    assert not killed, "非本服務 pid 不得殺"
    assert logs, "拒殺必須落 log（可觀測性鐵律）"


def test_kill_stale_pid_kills_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(starter, "_slog", lambda msg, *a, **k: None)
    monkeypatch.setattr(
        starter, "_pid_cmdline",
        lambda pid: r"C:\py\python.exe C:\x\tools\memory-vector-service\service.py")
    killed = []
    monkeypatch.setattr(starter.os, "kill", lambda pid, sig: killed.append(pid))

    pid_file = tmp_path / "service.pid"
    pid_file.write_text("12345", encoding="utf-8")
    assert starter._kill_stale_pid(pid_file) == 12345
    assert killed == [12345]


def test_kill_stale_pid_refuses_unverifiable(tmp_path, monkeypatch):
    logs = []
    monkeypatch.setattr(starter, "_slog", lambda msg, *a, **k: logs.append(msg))
    monkeypatch.setattr(starter, "_pid_cmdline", lambda pid: None)
    killed = []
    monkeypatch.setattr(starter.os, "kill", lambda pid, sig: killed.append(pid))

    pid_file = tmp_path / "service.pid"
    pid_file.write_text("12345", encoding="utf-8")
    assert starter._kill_stale_pid(pid_file) is None
    assert not killed
    assert any("unverifiable" in m for m in logs)


# ─── 5. stale chunk 清理核心（增量順帶清理共用）──────────────────────────────


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, cols):
        return self

    def limit(self, n):
        return self

    def to_list(self):
        return self._rows


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows
        self.deleted = []

    def count_rows(self):
        return len(self._rows)

    def search(self):
        return _FakeQuery(self._rows)

    def delete(self, where):
        self.deleted.append(where)


def test_delete_stale_keys_removes_orphans():
    table = _FakeTable([
        {"layer": "global", "atom_name": "keep"},
        {"layer": "global", "atom_name": "gone"},
        {"layer": "global", "atom_name": "gone"},
    ])
    stats = indexer._delete_stale_keys(table, {"global:keep"})
    assert stats["deleted_atoms"] == 1
    assert stats["deleted_chunks"] == 2
    assert len(table.deleted) == 1 and "atom_name = 'gone'" in table.deleted[0]


def test_build_index_incremental_wires_stale_cleanup():
    src = inspect.getsource(indexer.build_index)
    assert "_delete_stale_keys" in src, "增量索引須順帶清 stale"


# ─── 6. contextual prefix（embed 輸入前置脈絡行）─────────────────────────────


def test_embed_input_prefix_global():
    rec = {"title": "示例 Atom", "atom_name": "demo", "layer": "global",
           "file_path": "demo.md", "text": "原文內容"}
    out = indexer._embed_input(rec)
    assert out.splitlines()[0] == "示例 Atom — global"
    assert out.endswith("原文內容")
    assert rec["text"] == "原文內容"  # 存儲欄位不變


def test_embed_input_prefix_local_domain():
    rec = {"title": "", "atom_name": "gizmo-tool",
           "layer": indexer.LOCAL_ATOMS_LAYER_LABEL,
           "file_path": "Tools/gizmo-tool.md", "text": "內容"}
    out = indexer._embed_input(rec)
    assert out.splitlines()[0] == "gizmo-tool — local:Tools"


def test_build_index_embeds_with_prefix():
    src = inspect.getsource(indexer.build_index)
    assert "_embed_input" in src


# ─── 附帶：reranker json import（/extract NameError 根治）────────────────────


def test_reranker_has_json():
    assert reranker.json is json
