#!/usr/bin/env python3
"""verify_ai_client_setup.py — 其他 AI 客戶端輕量安裝腳本（tools/ai-client-setup.py）。

做什麼：tmp 設定檔驗 Codex（TOML 檔尾補段）與 Gemini（settings.json 合併）的註冊——
既有內容保留、重跑不重複、dry-run 不寫檔、壞 JSON 不碰且回「失敗」、已接上公司層就不再 join、
印給人貼的片段本身是合法 TOML／JSON。
怎麼跑：python -m pytest tools/verify/verify_ai_client_setup.py -q
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path

import pytest

CLAUDE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(CLAUDE_ROOT / "hooks"))

import wg_core  # noqa: E402

NODE = r"C:\Program Files\nodejs\node.exe"


@pytest.fixture
def acs():
    spec = importlib.util.spec_from_file_location("ai_client_setup", CLAUDE_ROOT / "tools" / "ai-client-setup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_codex_appends_block_keeps_existing_and_is_idempotent(acs, tmp_path):
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir()
    before = "model = 'gpt-x'\n\n[mcp_servers.excel]\ncommand = 'C:\\node.exe'\nargs = [ 'x.js' ]"   # 檔尾無換行
    cfg.write_text(before, encoding="utf-8")
    entry = acs.server_entry(NODE)

    assert "會在" in acs.register_codex(cfg, entry, dry_run=True)
    assert cfg.read_text(encoding="utf-8") == before                     # dry-run 不寫

    assert "已寫入" in acs.register_codex(cfg, entry, dry_run=False)
    text = cfg.read_text(encoding="utf-8")
    assert text.startswith(before)                                       # 既有內容一個字不動
    data = tomllib.loads(text)
    srv = data["mcp_servers"]["workflow-guardian"]
    assert srv["command"] == NODE and srv["args"] == [str(acs.SERVER_JS)]
    assert srv["env"]["WG_PYTHON"] == sys.executable
    assert data["mcp_servers"]["excel"]["args"] == ["x.js"] and data["model"] == "gpt-x"

    assert "已註冊" in acs.register_codex(cfg, entry, dry_run=False)
    assert cfg.read_text(encoding="utf-8") == text                       # 重跑不重複加


def test_codex_creates_missing_config(acs, tmp_path):
    cfg = tmp_path / ".codex" / "config.toml"
    acs.register_codex(cfg, acs.server_entry(NODE), dry_run=False)
    assert tomllib.loads(cfg.read_text(encoding="utf-8"))["mcp_servers"]["workflow-guardian"]["command"] == NODE


def test_gemini_merges_keeps_other_servers_and_is_idempotent(acs, tmp_path):
    path = tmp_path / ".gemini" / "settings.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"theme": "dark", "mcpServers": {"unityMCP": {"httpUrl": "http://x"}}}), encoding="utf-8")
    entry = acs.server_entry(NODE)

    before = path.read_text(encoding="utf-8")
    assert "會在" in acs.register_gemini(path, entry, dry_run=True)
    assert path.read_text(encoding="utf-8") == before

    assert "已寫入" in acs.register_gemini(path, entry, dry_run=False)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["theme"] == "dark" and data["mcpServers"]["unityMCP"] == {"httpUrl": "http://x"}
    assert data["mcpServers"]["workflow-guardian"] == entry

    text = path.read_text(encoding="utf-8")
    assert "已註冊" in acs.register_gemini(path, entry, dry_run=False)
    assert path.read_text(encoding="utf-8") == text


def test_gemini_broken_json_is_left_alone_and_reported(acs, tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ 壞掉的 json", encoding="utf-8")
    msg = acs.register_gemini(path, acs.server_entry(NODE), dry_run=False)
    assert msg.startswith("失敗") and path.read_text(encoding="utf-8") == "{ 壞掉的 json"


def test_snippets_are_valid_toml_and_json(acs):
    out = acs.snippets(acs.server_entry(NODE))
    toml_part, json_part = out.split("—— Gemini CLI 與其他吃 mcpServers JSON 的客戶端 ——\n")
    toml_part = toml_part.split("——\n", 1)[1]
    assert tomllib.loads(toml_part)["mcp_servers"]["workflow-guardian"]["command"] == NODE
    assert json.loads(json_part)["mcpServers"]["workflow-guardian"]["args"] == [str(acs.SERVER_JS)]


def test_join_skipped_when_already_joined_and_failure_is_loud(acs, tmp_path, monkeypatch):
    org = tmp_path / "org"
    (org / ".claude" / "memory").mkdir(parents=True)
    monkeypatch.setattr(wg_core, "org_memory_root", lambda: org)
    called = []
    monkeypatch.setattr(acs.subprocess, "run", lambda *a, **k: called.append(a) or None)
    assert "已接上" in acs.join_org(dry_run=False) and called == []

    monkeypatch.setattr(wg_core, "org_memory_root", lambda: None)
    assert acs.join_org(dry_run=True).startswith("[dry-run]") and called == []

    class _R:
        returncode, stdout, stderr = 1, "", "clone 失敗：權限不足"
    monkeypatch.setattr(acs.subprocess, "run", lambda *a, **k: _R())
    msg = acs.join_org(dry_run=False)
    assert msg.startswith("失敗") and "權限不足" in msg


def test_no_node_exits_2_with_install_hint(acs, monkeypatch, capsys):
    monkeypatch.setattr(acs, "find_node", lambda: None)
    monkeypatch.setattr(sys, "argv", ["ai-client-setup.py"])
    assert acs.main() == 2
    assert "Node.js" in capsys.readouterr().err
