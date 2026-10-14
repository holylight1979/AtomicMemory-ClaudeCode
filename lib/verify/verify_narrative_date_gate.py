"""verify_narrative_date_gate.py：記憶卡知識行寫入時就擋敘事型日期（KNOWLEDGE_LINE_NO_NARRATIVE_DATE），判式與 atom-date-lint 同一份。

三條寫入路都驗：py write_atom（程式寫手、自動萃取）的 create／append／replace；MCP js 走的 atom_io_cli
create_atom／build／append；兩個背景萃取器（user-extract-worker 經 write_atom、extract-worker 失敗回寫）擋下要留 ERROR 記錄。
日期只在 Source 欄、code fence、反引號、參照點或日期本身是知識（EOL）照收，而且收下的卡 lint 也掃不出東西。
全程在 tmp，不碰現役記憶庫。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_narrative_date_gate.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

LIB_PARENT = Path(__file__).resolve().parents[2]
HOOKS_DIR = LIB_PARENT / "hooks"
for _p in (LIB_PARENT, HOOKS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lib import atom_io  # noqa: E402
from lib.atom_io import write_atom  # noqa: E402
from lib.atom_spec import build_atom_content  # noqa: E402

RULE = "KNOWLEDGE_LINE_NO_NARRATIVE_DATE"
TODAY = "2026-10-14"
DATED = "[臨] 實踩（2026-10-14）：寫入閘以前不擋日期"
CLEAN = "[臨] 寫入閘在落檔前擋敘事日期"
TRIGGERS = ["日期閘", "敘事日期", "寫入閘"]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture
def isolated_claude(tmp_path, monkeypatch):
    """atom_io 與落點函式的全域根改指 tmp，不碰現役 ~/.claude。"""
    fake_claude = tmp_path / ".claude"
    mem = fake_claude / "memory"
    mem.mkdir(parents=True)
    monkeypatch.setattr(atom_io, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(atom_io, "GLOBAL_MEMORY_DIR", mem)
    monkeypatch.setattr(atom_io, "AUDIT_LOG", mem / "_meta" / "atom_io_audit.jsonl")
    from lib import atom_locations as aloc
    monkeypatch.setattr(aloc, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(aloc, "GLOBAL_MEMORY_DIR", mem)
    monkeypatch.setattr(aloc, "FAILURES_DIR", mem / "Failures")
    monkeypatch.setattr(aloc, "LOCAL_ATOMS_DIR", fake_claude / "_AIDocs" / "_atoms")
    monkeypatch.setattr(aloc, "TAXONOMY_LEARNED_PATH", mem / "_meta" / "taxonomy-lexicon-learned.json")
    return mem


def _write(title, knowledge, mode, **kw):
    kw.setdefault("domain", "設計通則" if mode == "create" else None)
    return write_atom(title=title, scope="global", confidence="[臨]", triggers=TRIGGERS, knowledge=knowledge,
                      mode=mode, source="test", skip_gate=True, today=TODAY, **kw)


def _assert_rejected(err, hit):
    assert err and RULE in err, f"要帶規則名：{err!r}"
    assert hit in err, f"要印出命中的那一行：{err!r}"
    assert "Source" in err and "DevHistory" in err, f"要指路日期該寫哪：{err!r}"


def test_write_atom_rejects_dated_knowledge_in_all_three_modes(isolated_claude):
    r = _write("date gate card", [CLEAN], "create")
    assert r.ok, r.error
    before = r.path.read_bytes()

    rc = _write("date gate dated", [DATED], "create")
    assert not rc.ok
    _assert_rejected(rc.error, "實踩（2026-10-14）")
    assert not list(isolated_claude.rglob("date-gate-dated.md")), "被擋的 create 不得落檔"

    ra = _write("date gate card", [DATED], "append")
    assert not ra.ok
    _assert_rejected(ra.error, "實踩（2026-10-14）")

    rr = _write("date gate card", [DATED], "replace")
    assert not rr.ok
    _assert_rejected(rr.error, "實踩（2026-10-14）")

    rx = _write("date gate card", [CLEAN], "replace", actions=["2026-10-14 之後改用新流程，使用者 2026-10-13 指正"])
    assert not rx.ok, "行動行一樣看"
    _assert_rejected(rx.error, "2026-10-13 指正")
    assert r.path.read_bytes() == before, "被擋的 append／replace 不得動到原檔"


def _cli(payload, claude_dir: Path):
    proc = subprocess.run([sys.executable, "-m", "lib.atom_io_cli"], input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True, encoding="utf-8", cwd=str(LIB_PARENT),
                          env={**os.environ, "PYTHONIOENCODING": "utf-8", "WG_CLAUDE_DIR": str(claude_dir)},
                          timeout=60)
    return json.loads(proc.stdout)


def test_mcp_cli_rejects_dated_knowledge_in_all_three_modes(tmp_path):
    """MCP js：create 走 create_atom、replace 走 build（js 拿 content 再 write_raw）、append 走 append。"""
    claude = tmp_path / ".claude"
    mem = claude / "memory"
    target = mem / "設計通則" / "date-gate-mcp.md"
    build = {"title": "date-gate-mcp", "scope": "global", "confidence": "[臨]", "triggers": TRIGGERS,
             "created_at": TODAY, "today": TODAY}
    index = {"base_dir": str(mem), "slug": "date-gate-mcp", "rel_path": "memory/設計通則/date-gate-mcp.md",
             "triggers": TRIGGERS, "scope": "global"}

    res = _cli({"action": "create_atom", "build": {**build, "knowledge": [DATED]}, "file_path": str(target),
                "today": TODAY, "index": index}, claude)
    assert not res["ok"]
    _assert_rejected(res["error"], "實踩（2026-10-14）")
    assert not target.exists(), "被擋的 create 不得落檔"

    res = _cli({"action": "create_atom", "build": {**build, "knowledge": [CLEAN]}, "file_path": str(target),
                "today": TODAY, "index": index, "dry_run": True}, claude)
    assert res["ok"], res.get("error")

    res = _cli({"action": "build", **build, "knowledge": [DATED]}, claude)
    assert not res["ok"]
    _assert_rejected(res["error"], "實踩（2026-10-14）")

    target.parent.mkdir(parents=True)
    target.write_text(build_atom_content(**build, knowledge=[CLEAN]), encoding="utf-8", newline="\n")
    before = target.read_bytes()
    res = _cli({"action": "append", "file_path": str(target), "knowledge": [DATED], "source": "mcp"}, claude)
    assert not res["ok"]
    _assert_rejected(res["error"], "實踩（2026-10-14）")
    assert target.read_bytes() == before, "被擋的 append 不得動到原檔"


def test_dates_outside_knowledge_prose_are_accepted_and_lint_agrees(isolated_claude):
    lint = _load(LIB_PARENT / "tools" / "atom-date-lint.py", "atom_date_lint_for_gate")
    knowledge = [
        "[臨] 判式只看知識行與行動行",
        "```\n2026-10-14 12:00 log 原樣保留\n```",
        "[臨] 舊卡有 `- Last-used: 2026-04-23` 欄",
        "[觀] 7.5 於 2026-11-10 EOL",
        "[臨] 2026-09-10 起交棒版本改為新算法",
        "| 日期 | 事件 |\n|---|---|\n| 2028-11-14 | 7.6 支援到 |",
    ]
    r = _write("date gate accepted", knowledge, "create", provenance=f"session:abcd1234 {TODAY}",
               quote="「日期寫 Source」", actions=["日期寫 Source 欄"])
    assert r.ok, r.error
    assert _write("date gate accepted", ["[臨] 追加一條沒有日期的現況"], "append").ok
    assert _write("date gate accepted", knowledge, "replace").ok
    text = r.path.read_text(encoding="utf-8")
    assert f"- Source: session:abcd1234 {TODAY}" in text
    changes, _ = lint.fix_lines(text.split("\n"))
    assert changes == [], f"閘收下的卡 lint 不該再抓到：{changes}"


def test_hit_line_is_cut_at_120_chars():
    from lib.narrative_date import narrative_date_error
    line = "- [臨] 實踩（2026-10-14）：" + "長" * 200
    err = narrative_date_error([line])
    assert line[:120] in err and line[:121] not in err


def test_lint_and_gate_share_one_judgment():
    from lib import atom_io_cli, narrative_date
    lint = _load(LIB_PARENT / "tools" / "atom-date-lint.py", "atom_date_lint_identity")
    ew = _load(HOOKS_DIR / "extract-worker.py", "extract_worker_identity")
    assert lint.fix_line is narrative_date.fix_line
    assert lint.fix_lines is narrative_date.fix_lines
    for mod in (atom_io, atom_io_cli, ew):
        assert mod.narrative_date_error is narrative_date.narrative_date_error, mod.__name__
    src = (LIB_PARENT / "tools" / "atom-date-lint.py").read_text(encoding="utf-8")
    assert "DATE_TOKEN = re.compile" not in src, "lint 不得再留自己的一份日期正規表達式"


def test_user_extract_worker_rejection_is_logged(isolated_claude, tmp_path, monkeypatch):
    m = _load(HOOKS_DIR / "user-extract-worker.py", "uew_date_gate")
    assert m.write_atom is atom_io.write_atom, "自動萃取要走同一個 funnel"
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    errors = []
    monkeypatch.setattr(m, "_atom_debug_error", lambda src, exc: errors.append(f"{src} {exc}"))
    monkeypatch.setattr(m, "_write_pending_candidate", lambda *a, **k: None)
    l2 = {"statement": "喜歡用兩格縮排（2026-10-14 使用者指正）", "scope": "personal",
          "audience": "programmer", "trigger": ["縮排", "格式", "風格"]}
    out = m._write_atom_via_mcp(l2, {"turn_id": "t-1", "cwd": str(proj)}, "sid12345", "holylight", {})
    assert out == "failed"
    assert any(RULE in e for e in errors), errors
    assert not list((proj / ".claude" / "memory").rglob("*.md")), "被擋就不落檔"


def test_extract_worker_failure_writeback_rejection_is_logged(isolated_claude, tmp_path, monkeypatch):
    ew = _load(HOOKS_DIR / "extract-worker.py", "extract_worker_date_gate")
    fdir = tmp_path / "Failures"
    logs = []
    monkeypatch.setattr(ew, "resolve_failures_dir", lambda cwd: fdir)
    monkeypatch.setattr(ew, "_failure_topic", lambda *a, **k: "")
    monkeypatch.setattr(ew, "_atom_debug_log", lambda tag, content, config=None: logs.append((tag, content)))
    monkeypatch.setattr(ew, "_failure_catalog_sync", lambda *a, **k: None)
    monkeypatch.setattr(ew, "_failure_index_upsert", lambda *a, **k: None)
    dated = {"failure_type": "assumption", "domain_tags": [],
             "content": "以為寫入閘會擋日期（2026-10-14 實踩），結果事後 lint 才抓到"}
    ew._failure_writeback({"cwd": "", "config": {}}, [dated])
    assert not list(fdir.rglob("*.md")), "帶日期的失敗條目不落檔"
    assert any(tag == "ERROR" and RULE in c for tag, c in logs), logs

    clean = {**dated, "content": "以為寫入閘會擋日期，結果事後 lint 才抓到"}
    ew._failure_writeback({"cwd": "", "config": {}}, [clean])
    assert list(fdir.rglob("*.md")), "沒日期的照寫"
