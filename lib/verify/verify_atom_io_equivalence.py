"""verify_atom_io_equivalence.py — atom_io.write_atom byte-equivalence vs server.js (S1.3)

10 情境覆蓋 server.js:1065 toolAtomWrite 行為契約。每情境 fixture 寫死 today
日期，比對 build_atom_content 與 write_atom 落檔結果 byte-identical。

S1 不接 caller，故無實際 write-gate / conflict-detector 涉入；測試以 skip_gate=True
跑純 funnel 路徑。S2/S3 切 caller 後再加 e2e gate 測試。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

LIB_PARENT = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude/
if str(LIB_PARENT) not in sys.path:
    sys.path.insert(0, str(LIB_PARENT))

from lib import atom_io  # noqa: E402
from lib.atom_io import write_atom  # noqa: E402
from lib.atom_spec import build_atom_content  # noqa: E402


FIXED_TODAY = "2026-05-04"


@pytest.fixture
def isolated_claude(tmp_path, monkeypatch):
    """把 atom_io 的全域 root path 重指向 tmp_path，避免測試污染現役 ~/.claude/。"""
    fake_claude = tmp_path / ".claude"
    fake_global_mem = fake_claude / "memory"
    fake_audit = fake_global_mem / "_meta" / "atom_io_audit.jsonl"
    fake_global_mem.mkdir(parents=True)
    monkeypatch.setattr(atom_io, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(atom_io, "GLOBAL_MEMORY_DIR", fake_global_mem)
    monkeypatch.setattr(atom_io, "AUDIT_LOG", fake_audit)
    return {
        "root": tmp_path,
        "claude": fake_claude,
        "memory": fake_global_mem,
        "audit": fake_audit,
    }


@pytest.fixture
def fake_project(tmp_path):
    """建一個 fake project root（有 .git marker），供 shared/role/personal 測試用。"""
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / ".git").mkdir()  # marker for find_project_root
    return proj


# ─── 1. global atom create ─────────────────────────────────────────────────────


def test_01_global_create_byte_identical(isolated_claude):
    expected = build_atom_content(
        title="Hello", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["fact1", "fact2"],
        today=FIXED_TODAY,
    )
    result = write_atom(
        title="Hello", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["fact1", "fact2"],
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert result.ok, result.error
    actual = result.path.read_text(encoding="utf-8")
    assert actual == expected, f"DIFF\nEXPECTED:\n{expected}\nACTUAL:\n{actual}"
    assert result.path == isolated_claude["memory"] / "hello.md"


# ─── 2. shared atom create (project scope) ────────────────────────────────────


def test_02_shared_create(isolated_claude, fake_project):
    result = write_atom(
        title="Shared Knowledge", scope="shared", confidence="[臨]",
        triggers=["x", "y", "z"], knowledge=["k1"],
        project_cwd=str(fake_project),
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert result.ok, result.error
    expected_path = fake_project / ".claude" / "memory" / "shared" / "shared-knowledge.md"
    assert result.path == expected_path
    content = result.path.read_text(encoding="utf-8")
    assert "- Scope: shared" in content
    assert "# Shared Knowledge" in content


# ─── 3. role atom create ──────────────────────────────────────────────────────


def test_03_role_create(isolated_claude, fake_project):
    result = write_atom(
        title="Role Atom", scope="role", confidence="[臨]",
        triggers=["t1", "t2", "t3"], knowledge=["k"], role="programmer",
        project_cwd=str(fake_project),
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert result.ok, result.error
    expected_path = fake_project / ".claude" / "memory" / "roles" / "programmer" / "role-atom.md"
    assert result.path == expected_path
    content = result.path.read_text(encoding="utf-8")
    assert "- Scope: role:programmer" in content


# ─── 4. personal atom create ──────────────────────────────────────────────────


def test_04_personal_create(isolated_claude, fake_project):
    result = write_atom(
        title="Personal Atom", scope="personal", confidence="[臨]",
        triggers=["p1", "p2", "p3"], knowledge=["k"], user="alice",
        project_cwd=str(fake_project),
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert result.ok, result.error
    expected_path = fake_project / ".claude" / "memory" / "personal" / "alice" / "personal-atom.md"
    assert result.path == expected_path
    content = result.path.read_text(encoding="utf-8")
    assert "- Scope: personal:alice" in content


# ─── 5. all optional fields render correctly ──────────────────────────────────


def test_05_optional_fields(isolated_claude):
    result = write_atom(
        title="Full Atom", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["k1", "k2"],
        actions=["do this", "- already prefixed"],
        related=["other-atom-1", "other-atom-2"],
        audience=["programmer"],  # not in SENSITIVE_AUDIENCE
        author="testuser", merge_strategy="manual",
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert result.ok, result.error
    content = result.path.read_text(encoding="utf-8")
    assert "- Audience: programmer" in content
    assert "- Author: testuser" in content
    assert "- Merge-strategy: manual" in content
    assert "- Related: other-atom-1, other-atom-2" in content
    assert "- do this" in content
    assert "- already prefixed" in content
    # ai-assist (default) should NOT emit Merge-strategy line
    result2 = write_atom(
        title="Full Atom 2", scope="global", confidence="[臨]",
        triggers=["x", "y", "z"], knowledge=["k"],
        merge_strategy="ai-assist",
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert "Merge-strategy:" not in result2.path.read_text(encoding="utf-8")


# ─── 6. sensitive audience → _pending_review/ ─────────────────────────────────


def test_06_sensitive_audience_routes_pending(isolated_claude, fake_project):
    result = write_atom(
        title="Decision Atom", scope="shared", confidence="[臨]",
        triggers=["d1", "d2", "d3"], knowledge=["k"],
        audience=["decision"],  # sensitive
        project_cwd=str(fake_project),
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert result.ok, result.error
    assert result.routed_to_pending is True
    assert "_pending_review" in str(result.path)
    content = result.path.read_text(encoding="utf-8")
    assert "- Pending-review-by: management" in content


# ─── 7. mode=append ───────────────────────────────────────────────────────────


def test_07_append_mode(isolated_claude):
    write_atom(
        title="Appendable", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["original-fact"],
        mode="create", source="test", skip_gate=True, today="2026-05-01",
    )
    file_path = isolated_claude["memory"] / "appendable.md"
    access_path = file_path.with_suffix(".access.json")
    before = file_path.read_text(encoding="utf-8")
    assert "- original-fact" in before
    # Last-used 不在 .md，在 access.json
    assert "- Last-used:" not in before
    import json as _json
    acc_before = _json.loads(access_path.read_text(encoding="utf-8"))
    assert acc_before["last_used"] == "2026-05-01"

    result = write_atom(
        title="Appendable", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["new-fact-1", "new-fact-2"],
        mode="append", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert result.ok, result.error
    after = file_path.read_text(encoding="utf-8")
    assert "- original-fact" in after  # preserved
    assert "- new-fact-1" in after
    assert "- new-fact-2" in after
    # append 後 last_used 在 access.json 被刷新
    acc_after = _json.loads(access_path.read_text(encoding="utf-8"))
    assert acc_after["last_used"] == FIXED_TODAY
    # appended knowledge must be before ## 行動
    assert after.index("- new-fact-2") < after.index("## 行動")


# ─── 8. mode=replace preserves Confirmations / ReadHits / Author / Created-at ─


def test_08_replace_preserves_counters(isolated_claude):
    initial = write_atom(
        title="Counter Atom", scope="global", confidence="[臨]",
        triggers=["c1", "c2", "c3"], knowledge=["v1"],
        author="orig-author",
        mode="create", source="test", skip_gate=True, today="2026-05-01",
    )
    # 計數在 access.json，模擬 post-write 演進
    fp = initial.path
    from lib.atom_access import write_access_field
    write_access_field(fp, field="confirmations", value=7, source="test")
    write_access_field(fp, field="read_hits", value=42, source="test")

    result = write_atom(
        title="Counter Atom", scope="global", confidence="[臨]",
        triggers=["c1", "c2", "c3"], knowledge=["v2-replaced"],
        author="new-author-should-be-ignored",
        mode="replace", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert result.ok, result.error
    after = fp.read_text(encoding="utf-8")
    # 計數在 access.json，replace 不重建（檔本就分離）
    import json as _json
    acc = _json.loads(fp.with_suffix(".access.json").read_text(encoding="utf-8"))
    assert acc["confirmations"] == 7  # preserved
    assert acc["read_hits"] == 42  # preserved
    assert acc["last_used"] == FIXED_TODAY  # replace 後刷新
    assert "- Author: orig-author" in after  # preserved (initial author wins)
    assert "- Created-at: 2026-05-01" in after  # preserved
    assert "- v2-replaced" in after  # new content
    assert "- v1" not in after  # old content gone


# ─── 9. dry_run: no file written ──────────────────────────────────────────────


def test_09_dry_run_no_write(isolated_claude):
    result = write_atom(
        title="Ghost Atom", scope="global", confidence="[臨]",
        triggers=["g1", "g2", "g3"], knowledge=["k"],
        mode="create", source="test", skip_gate=True,
        dry_run=True, today=FIXED_TODAY,
    )
    assert result.ok
    assert result.extra.get("dry_run") is True
    assert not result.path.exists()
    # content still returned for inspection
    assert "# Ghost Atom" in result.extra["content"]
    # audit log not appended in dry_run
    assert not isolated_claude["audit"].exists()


# ─── 10. error paths ──────────────────────────────────────────────────────────


def test_10_error_paths(isolated_claude, fake_project):
    # 10a: invalid source
    r1 = write_atom(
        title="X", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["k"],
        mode="create", source="hacker:bypass", skip_gate=True,
    )
    assert not r1.ok and "invalid source" in r1.error

    # 10b: invalid scope
    r2 = write_atom(
        title="X", scope="bogus", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["k"],
        mode="create", source="test", skip_gate=True,
    )
    assert not r2.ok and ("scope" in r2.error.lower() or "Unknown" in r2.error)

    # 10c: confidence != [臨] on create
    r3 = write_atom(
        title="X", scope="global", confidence="[固]",
        triggers=["a", "b", "c"], knowledge=["k"],
        mode="create", source="test", skip_gate=True,
    )
    assert not r3.ok and "[臨]" in r3.error

    # 10d: file exists (create twice)
    write_atom(
        title="Once", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["k"],
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    r4 = write_atom(
        title="Once", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["k"],
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert not r4.ok and "already exists" in r4.error

    # 10e: append nonexistent
    r5 = write_atom(
        title="Nonexistent", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["k"],
        mode="append", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert not r5.ok and "not found" in r5.error


# ─── Bonus: audit log byte-shape sanity ───────────────────────────────────────


def test_audit_log_appends_jsonl(isolated_claude):
    write_atom(
        title="LoggedAtom", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["k"],
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    audit_path = isolated_claude["audit"]
    assert audit_path.exists()
    lines = [ln for ln in audit_path.read_text(encoding="utf-8").splitlines() if ln]
    # Expect at least 1 write entry + 1 index entry
    assert len(lines) >= 2
    entries = [json.loads(ln) for ln in lines]
    ops = [e["op"] for e in entries]
    assert "write" in ops
    assert "index" in ops
    sources = {e["source"] for e in entries}
    assert sources == {"test"}


# ─── 11. table / fence block knowledge (block-aware render) ───────────────────


def test_11_table_and_fence_blocks(isolated_claude):
    kn = ["[固] 門檻：", "| 軌 | 值 |\n|---|---|\n| P | 4 |", "```py\nx = 1\n```", "tail"]
    result = write_atom(
        title="Block Atom", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=kn,
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert result.ok, result.error
    content = result.path.read_text(encoding="utf-8")
    # 表格列原樣輸出，不被加 bullet
    assert "\n| 軌 | 值 |\n" in content
    assert "- | 軌" not in content
    # intro bullet 與表格間補空行（GFM 渲染需要）
    assert "- [固] 門檻：\n\n| 軌 | 值 |" in content
    # 程式碼 fence 原樣
    assert "```py\nx = 1\n```" in content
    # 一般文字仍加 bullet 前綴
    assert "\n- tail\n" in content


def test_12_append_table_block(isolated_claude):
    write_atom(
        title="Appendable Table", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["original-fact"],
        mode="create", source="test", skip_gate=True, today="2026-05-01",
    )
    result = write_atom(
        title="Appendable Table", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["| x | y |\n|---|---|\n| 1 | 2 |"],
        mode="append", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert result.ok, result.error
    after = result.path.read_text(encoding="utf-8")
    assert "- original-fact" in after
    # 表格與既有知識間隔一空行、原樣輸出
    assert "- original-fact\n\n| x | y |" in after
    assert "- | x" not in after
    assert after.index("| 1 | 2 |") < after.index("## 行動")


# ─── 13. py↔js byte-parity for buildAtomContent (fulfils file docstring) ───────


def test_13_py_js_byte_parity_table(tmp_path):
    """build_atom_content (py) must be byte-identical to server.js buildAtomContent (js)
    for a table + fence + bullet mix. Skips if node unavailable."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    server_js = LIB_PARENT / "tools" / "workflow-guardian-mcp" / "server.js"
    if not server_js.exists():
        pytest.skip("server.js not found")

    kn = ["[固] 門檻：", "| 軌 | 值 |\n|---|---|\n| P | 4 |", "```py\nx = 1\n```", "tail"]
    py_out = build_atom_content(
        title="Parity", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=kn, actions=["act1"], today=FIXED_TODAY,
    )
    out_file = tmp_path / "js_out.txt"
    js_script = (
        "const fs=require('fs');"
        "const {buildAtomContent}=require(process.argv[1]);"
        "const kn=JSON.parse(process.argv[2]);"
        "fs.writeFileSync(process.argv[3], buildAtomContent({"
        "title:'Parity',scope:'global',confidence:'[臨]',"
        "triggers:['a','b','c'],knowledge:kn,actions:['act1'],today:'" + FIXED_TODAY + "'"
        "}));process.exit(0);"
    )
    proc = subprocess.run(
        [node, "-e", js_script, str(server_js), json.dumps(kn), str(out_file)],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert proc.returncode == 0, f"node failed: {proc.stderr}"
    js_out = out_file.read_text(encoding="utf-8")
    assert js_out == py_out, f"DRIFT\nPY:\n{py_out!r}\nJS:\n{js_out!r}"


# ─── 14. py↔js path / realm routing constants parity (source-level guard) ──────


def test_14_py_js_path_constants_parity():
    """Path/realm routing constants must stay in sync py↔js.

    lib/atom_locations.py is the single source of truth; server.js mirrors it by hand.
    This is a source-level guard (no node exec): if someone edits one side's rel-path
    constant or domain set without the other, this fails — catching the exact drift the
    `// MIRROR: keep in sync` comment alone cannot enforce.
    """
    from lib.atom_locations import (
        FAILURES_REL, LOCAL_ATOMS_REL, FEEDBACK_TITLE_PREFIX,
        LOCAL_REALM_DOMAINS, LOCAL_REALM_DEFAULT_DOMAIN,
    )

    server_js = LIB_PARENT / "tools" / "workflow-guardian-mcp" / "server.js"
    if not server_js.exists():
        pytest.skip("server.js not found")
    js = server_js.read_text(encoding="utf-8")

    assert f'FAILURES_REL = "{FAILURES_REL}"' in js, "FAILURES_REL drift"
    assert f'LOCAL_ATOMS_REL = "{LOCAL_ATOMS_REL}"' in js, "LOCAL_ATOMS_REL drift"
    assert f'FEEDBACK_TITLE_PREFIX = "{FEEDBACK_TITLE_PREFIX}"' in js, "FEEDBACK_TITLE_PREFIX drift"
    assert f'LOCAL_REALM_DEFAULT_DOMAIN = "{LOCAL_REALM_DEFAULT_DOMAIN}"' in js, "default domain drift"
    for dom in LOCAL_REALM_DOMAINS:
        assert f'"{dom}"' in js, f"local domain {dom!r} missing in server.js LOCAL_REALM_DOMAINS"


# ─── 15. realm=local routing → _AIDocs/_atoms/<domain>/ (Scope stays global) ───


def test_15_local_realm_routing(isolated_claude, monkeypatch):
    """realm='local' routes physical file to _AIDocs/_atoms/<domain>/, index path encodes realm,
    and the atom KEEPS Scope=global (realm is orthogonal to scope; derived from path, not stored)."""
    from lib import atom_locations as aloc
    fake_claude = isolated_claude["claude"]
    # local_write_target() reads atom_locations module globals at call time → patch them too
    monkeypatch.setattr(aloc, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(aloc, "GLOBAL_MEMORY_DIR", isolated_claude["memory"])
    monkeypatch.setattr(aloc, "LOCAL_ATOMS_DIR", fake_claude / "_AIDocs" / "_atoms")

    result = write_atom(
        title="Brain World Note", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["k"],
        realm="local", domain="Tools",
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert result.ok, result.error
    expected = fake_claude / "_AIDocs" / "_atoms" / "Tools" / "brain-world-note.md"
    assert result.path == expected, f"routed to {result.path}, want {expected}"
    content = result.path.read_text(encoding="utf-8")
    assert "- Scope: global" in content        # realm orthogonal: stays global
    assert "Realm" not in content              # realm NOT stored as a field (path-derived)

    # default core path unchanged when realm omitted
    core = write_atom(
        title="Plain Core", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["k"],
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert core.ok, core.error
    assert core.path == isolated_claude["memory"] / "plain-core.md"


# ─── 16. realm classifier: zero false positives + correct local detection ──────


def test_16_classify_realm_zero_false_positive():
    """classify_realm 絕不把核心保護清單 / feedback / pipeline 判 local（必驗 #1），
    且實例專屬 atom 須判 local + 正確 domain。對拍驗收 B dry-run 的零誤判硬門檻。"""
    from lib.atom_locations import classify_realm

    # 核心保護：強制 core（protected=True，先於詞庫；含帶 'codex' 的 feedback atom）
    core_protected = [
        ("decisions-architecture", ["guardian", "SessionStart", "hooks"]),
        ("decisions", ["決策", "記憶系統"]),
        ("workflow-rules", ["GIT", "Phase"]),
        ("workflow-parallel-agents", ["多 agent", "並行"]),
        ("toolchain", ["工具鏈", "LanceDB"]),
        ("toolchain-ollama", ["ollama", "embedding"]),
        ("preferences", ["偏好", "上GIT"]),
        ("feedback-tooling-reliability", ["codex", "codex companion", "MCP"]),
        ("feedback-workflow-discipline", ["handoff", "上 GIT"]),
        ("cognitive-patterns", ["過度工程", "proxy metric"]),
        # SGI 詞庫污染（karpathy/verify loop）name 命中也硬擋，列保護
        ("goal-driven-verify-loopkarpathy-吸收", ["karpathy", "verify loop", "成功標準"]),
        ("memory-pipeline-silent-failure-2026-05", ["episodic", "晉升"]),
        ("atom-usefulness-loop", ["usefulness", "Wilson 下界"]),
        ("atom-table-support", ["atom_write", "table"]),
    ]
    for name, trig in core_protected:
        r = classify_realm(name, trig)
        assert r["realm"] == "core", f"FALSE POSITIVE: {name} → local ({r})"
        assert r["protected"] is True, f"{name} should be protected"

    # 未在保護清單但詞庫無命中 → 安全預設 core（非 protected）
    for name, trig in [("memory-index-caption-regen", ["MEMORY.md", "sync-memory-index"]),
                       ("realm-範疇分區機制-v5", ["realm", "範疇分區", "注入閘門"])]:
        r = classify_realm(name, trig)
        assert r["realm"] == "core" and r["protected"] is False, f"{name}: {r}"

    # 實例專屬 atom：name 單獨（weight-10）即足以判 local + 正確 domain
    local_expect = {
        "腦內世界-v3-自癒與-command-bus-架構": "World",
        "reconcile-render-動畫狀態歸屬陷阱": "World",
        "腦內世界-環境演化-放置式架構": "World",
        "gdoc-harvester": "Tools",
        "electron-uia-automation": "Tools",
        "codex-log-bloat-analytics": "Tools",
        "cc-能力查證反編譯實跑-binary": "Tools",
        "guardian-dashboard-孤兒佔埠與新碼重啟": "MemDev",
    }
    for name, dom in local_expect.items():
        r = classify_realm(name, [])
        assert r["realm"] == "local", f"{name} not local: {r}"
        assert r["domain"] == dom, f"{name} domain {r['domain']} != {dom}"


# ─── 17. realm classifier py↔js parity (mirror guard) ──────────────────────────


def test_17_classify_realm_py_js_parity():
    """classify_realm (py) 必與 server.js classifyRealm (js) 對同一 fixture 集一致判定。
    守 lib↔server.js 鏡像漂移（realm/domain/protected/matched 全比）。"""
    import shutil
    import subprocess

    from lib.atom_locations import classify_realm

    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    server_js = LIB_PARENT / "tools" / "workflow-guardian-mcp" / "server.js"
    if not server_js.exists():
        pytest.skip("server.js not found")

    fixtures = [
        ["gdoc-harvester", ["harvester", "Google Docs"]],
        ["guardian-dashboard-孤兒佔埠與新碼重啟", ["guardian", "world.html", "EADDRINUSE"]],
        ["腦內世界-環境演化-放置式架構", ["腦內世界", "環境演化", "world.html"]],
        ["decisions-architecture", ["guardian", "SessionStart"]],
        ["feedback-tooling-reliability", ["codex", "MCP"]],
        ["memory-index-caption-regen", ["MEMORY.md"]],
        ["cc-能力查證反編譯實跑-binary", ["反編譯", "claude binary"]],
        ["atom-usefulness-loop", ["usefulness"]],
        ["some-new-world-note", ["腦內世界", "wander"]],
        ["plain-generic-atom", ["foo", "bar"]],
        # 保護清單 py↔js 鏡像（goal-driven 曾誤降後加硬擋）
        ["goal-driven-verify-loopkarpathy-吸收", ["karpathy", "verify loop"]],
    ]
    py = [classify_realm(n, t) for n, t in fixtures]

    js_script = (
        "const fs=require('fs');"
        "const src=fs.readFileSync(process.argv[1],'utf-8');"
        "const start=src.indexOf('const LOCAL_REALM_CORE_PROTECTED_PREFIXES');"
        "const block=src.slice(start, src.indexOf('const TOOLS_DIR'));"
        "const LOCAL_REALM_DOMAINS=new Set(['World','Tools','MemDev']);"
        "const LOCAL_REALM_DEFAULT_DOMAIN='Else';"  # classifyRealm 出口 guard 引用（block 外常數）
        "eval(block);"
        "const fx=JSON.parse(process.argv[2]);"
        "const out=fx.map(([n,t])=>{const r=classifyRealm(n,t);"
        "return {realm:r.realm,domain:r.domain,prot:r.protected,matched:r.matched};});"
        "process.stdout.write(JSON.stringify(out));"
    )
    proc = subprocess.run(
        [node, "-e", js_script, str(server_js), json.dumps(fixtures)],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert proc.returncode == 0, f"node failed: {proc.stderr}"
    js = json.loads(proc.stdout)
    for (n, _t), p, j in zip(fixtures, py, js):
        assert p["realm"] == j["realm"], f"{n}: realm py={p['realm']} js={j['realm']}"
        assert p["domain"] == j["domain"], f"{n}: domain py={p['domain']} js={j['domain']}"
        assert p["protected"] == j["prot"], f"{n}: protected py={p['protected']} js={j['prot']}"
        assert sorted(p["matched"]) == sorted(j["matched"]), \
            f"{n}: matched py={p['matched']} js={j['matched']}"


# ─── 18. normalize_domain_path: 階層 canon（snap 既有層 + 深度 + 拒非法）─────────


def test_18_normalize_domain_path():
    """OPEN 2 canon：對既有兄弟段 snap（精確/前綴/difflib）、深度截尾、拒 path-traversal。"""
    from lib.atom_locations import normalize_domain_path, LOCAL_REALM_DEFAULT_DOMAIN

    existing = ["OS/Windows/WSL", "Tools", "World"]
    # 大小寫無視精確（逐層）
    assert normalize_domain_path("os/windows/wsl", existing) == "OS/Windows/WSL"
    # 前綴包含 snap：Win → Windows（治縮寫分歧，difflib ratio 0.6 接不住、靠前綴）
    assert normalize_domain_path("OS/Win", existing) == "OS/Windows"
    # 新層保留（既有兄弟在 OS/Windows 下 → 允許深 1 層到 Hermes）
    assert normalize_domain_path("OS/Windows/Hermes", existing) == "OS/Windows/Hermes"
    assert normalize_domain_path("NewRoot/Sub", existing) == "NewRoot/Sub"
    # 增量深度閘：全新分支封頂 Lv3（即使 LLM 灌很深；existing 無 OS 分支）
    assert normalize_domain_path("a/b/c/d/e/f/g/h/i", []) == "a/b/c"
    assert normalize_domain_path("OS/Windows/WSL/Advanced/Troubleshooting", ["Tools", "World"]) == "OS/Windows/WSL"
    # 深度隨內容量長：既有已有 OS/Windows/WSL → 允許再深 1 層到 Lv4
    assert normalize_domain_path("OS/Windows/WSL/Networking", existing) == "OS/Windows/WSL/Networking"
    # path-traversal / 隱藏前綴 → 截斷或退 fail-safe
    assert normalize_domain_path("../etc", []) == LOCAL_REALM_DEFAULT_DOMAIN
    assert normalize_domain_path("Good/_bad/More", existing) == "Good"
    assert normalize_domain_path("", []) == LOCAL_REALM_DEFAULT_DOMAIN
    assert normalize_domain_path("_hidden", []) == LOCAL_REALM_DEFAULT_DOMAIN
    # 非 CJK/ASCII 字元段（如韓文「자동화」亂碼 domain）→ 降 Else / 截斷
    assert normalize_domain_path("자동화流程與協議", existing) == LOCAL_REALM_DEFAULT_DOMAIN
    assert normalize_domain_path("Tools/자동화流程與協議", existing) == "Tools"
    assert normalize_domain_path("Кириллица", []) == LOCAL_REALM_DEFAULT_DOMAIN  # homoglyph 系
    # 合法 CJK 段不受字元集 guard 影響
    assert normalize_domain_path("Tools/自動化流程與協議", existing) == "Tools/自動化流程與協議"


# ─── 19. 階層路徑 segment 抽取 ─────────────────────────────────────────────────


def test_19_local_realm_path_segments():
    from lib.atom_locations import local_realm_path_segments, local_realm_lv1_root

    flat = "_AIDocs/_atoms/Tools/gdoc-harvester.md"
    deep = "_AIDocs/_atoms/OS/Windows/WSL/wsl2-x.md"
    assert local_realm_path_segments(flat) == ["Tools"]
    assert local_realm_path_segments(deep) == ["OS", "Windows", "WSL"]
    assert local_realm_path_segments("memory/foo.md") == []          # 非 local
    assert local_realm_lv1_root(deep) == "OS"
    assert local_realm_lv1_root(flat) == "Tools"


# ─── 20. realm=local 多段階層路徑路由（_AIDocs/_atoms/OS/Windows/WSL/）───────────


def test_20_local_realm_multi_segment_routing(isolated_claude, monkeypatch):
    """realm='local' + 多段 domain → 物理落深層 _AIDocs/_atoms/<a>/<b>/<c>/，Scope 仍 global。"""
    from lib import atom_locations as aloc
    fake_claude = isolated_claude["claude"]
    monkeypatch.setattr(aloc, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(aloc, "GLOBAL_MEMORY_DIR", isolated_claude["memory"])
    monkeypatch.setattr(aloc, "LOCAL_ATOMS_DIR", fake_claude / "_AIDocs" / "_atoms")

    result = write_atom(
        title="WSL2 vhdx Rescue", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["k"],
        realm="local", domain="OS/Windows/WSL",
        mode="create", source="test", skip_gate=True, today=FIXED_TODAY,
    )
    assert result.ok, result.error
    expected = fake_claude / "_AIDocs" / "_atoms" / "OS" / "Windows" / "WSL" / "wsl2-vhdx-rescue.md"
    assert result.path == expected, f"routed to {result.path}, want {expected}"
    assert "- Scope: global" in result.path.read_text(encoding="utf-8")


# ─── 21. classify_realm extra_lexicon（learned 補 recall；None=base 不變）────────


def test_21_classify_realm_extra_lexicon():
    """extra_lexicon=None → base 行為不變（parity 面）；傳 learned → 補命中 + 多段 domain。
    核心保護硬擋永遠先於詞庫（含 learned）。"""
    from lib.atom_locations import classify_realm

    learned = {"wsl2": "OS/Windows/WSL", "vhdx": "OS/Windows/WSL"}
    # base：詞庫無命中 → core
    assert classify_realm("wsl2-0x80070569-救援", ["vhdx", "gpo"])["realm"] == "core"
    # learned 注入：命中 → local + 多段 domain
    r = classify_realm("wsl2-0x80070569-救援", ["vhdx"], extra_lexicon=learned)
    assert r["realm"] == "local" and r["domain"] == "OS/Windows/WSL", r
    # None 時與 base fixture 完全一致（不被 learned 污染）
    assert classify_realm("gdoc-harvester", [])["domain"] == "Tools"
    # 核心保護先於 learned（即使 learned 含會命中的詞）
    prot = classify_realm("feedback-x", [], extra_lexicon={"feedback": "Tools"})
    assert prot["realm"] == "core" and prot["protected"] is True


# ─── 22. path-traversal 守門 py↔js parity（_clean_segment ↔ cleanRealmSegment）──


def test_22_clean_segment_py_js_parity():
    """單段正規化（path-traversal 最後防線）py↔js 一致。守 applyLocalRouting 鏡像漂移。"""
    import shutil
    import subprocess
    from lib.atom_locations import _clean_segment

    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    server_js = LIB_PARENT / "tools" / "workflow-guardian-mcp" / "server.js"
    if not server_js.exists():
        pytest.skip("server.js not found")

    fixtures = ["Windows", "  OS  ", "WSL", "..", "_hidden", ".dot",
                "a/b", "a\\b", "bad<x", 'q"x', "", "Hermes Agent",
                # 非 CJK/ASCII 字元集 guard（防韓文等亂碼 domain）
                "자동화流程與協議", "自動化流程與協議", "Кириллица", "Tools①"]
    py = [_clean_segment(s) for s in fixtures]

    js_script = (
        "const fs=require('fs');"
        "const src=fs.readFileSync(process.argv[1],'utf-8');"
        "const start=src.indexOf('function cleanRealmSegment');"
        "const block=src.slice(start, src.indexOf('function applyLocalRouting'));"
        "eval(block);"
        "const fx=JSON.parse(process.argv[2]);"
        "process.stdout.write(JSON.stringify(fx.map(cleanRealmSegment)));"
    )
    proc = subprocess.run(
        [node, "-e", js_script, str(server_js), json.dumps(fixtures)],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert proc.returncode == 0, f"node failed: {proc.stderr}"
    js = json.loads(proc.stdout)
    assert py == js, f"clean-segment drift\nPY={py}\nJS={js}"


# ─── 23. 自學詞庫 load/append round-trip（Phase C；atomic + 去重 + 餵 classify）──


def test_23_learned_lexicon_roundtrip(tmp_path, monkeypatch):
    """append_learned_terms：atomic 寫 + case-insensitive 去重；load → 餵 classify_realm 補命中。"""
    from lib import atom_locations as aloc

    fake = tmp_path / "_meta" / "realm-lexicon-learned.json"
    monkeypatch.setattr(aloc, "LEARNED_LEXICON_PATH", fake)

    assert aloc.load_learned_lexicon() == {}                       # 缺檔 → {}
    aloc.append_learned_terms({"wsl2": "OS/Windows/WSL"})
    assert fake.exists()
    assert aloc.load_learned_lexicon() == {"wsl2": "OS/Windows/WSL"}

    # 併入 + case-insensitive 去重（WSL2 併進 wsl2 同 key）
    aloc.append_learned_terms({"vhdx": "OS/Windows/WSL", "WSL2": "OS/Windows/WSL"})
    learned = aloc.load_learned_lexicon()
    assert set(learned) == {"wsl2", "vhdx"}

    # learned 餵 classify_realm → 命中 + 多段 domain（base None 時不受影響已由 test_21 覆蓋）
    r = aloc.classify_realm("wsl2-0x80070569", ["vhdx"], extra_lexicon=learned)
    assert r["realm"] == "local" and r["domain"] == "OS/Windows/WSL"


# ─── 24. append CRLF byte-stability（parity：拼接統一走 py 單一實作）─────


def test_24_append_crlf_byte_stability(isolated_claude):
    """CRLF 既有檔 append 後：行尾全保 CRLF、零混寫（\\r\\r\\n）、既有行 byte 不動。
    覆 lib/atom_io.py:_atomic_write L135-138 註解描述的混寫風險面。"""
    from lib.atom_io import append_atom_file

    write_atom(
        title="Crlf Atom", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["original-fact"],
        mode="create", source="test", skip_gate=True, today="2026-05-01",
    )
    fp = isolated_claude["memory"] / "crlf-atom.md"
    # 強制整檔 CRLF（不依賴平台 os.linesep）
    crlf_bytes = fp.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    fp.write_bytes(crlf_bytes)

    result = append_atom_file(fp, ["new-fact-crlf"], source="test")
    assert result.ok, result.error

    raw = fp.read_bytes()
    assert b"\r\r\n" not in raw, "CRLF 二次翻譯（CR CR LF）"
    assert raw.count(b"\n") == raw.count(b"\r\n"), "混寫：存在裸 LF"
    lines = raw.split(b"\r\n")
    assert "- original-fact".encode() in lines
    assert "- new-fact-crlf".encode() in lines
    # 既有行 byte 不動：除插入行與其間隔外，原行序列完整保留
    old_lines = [ln for ln in crlf_bytes.split(b"\r\n") if ln]
    new_lines = [ln for ln in raw.split(b"\r\n") if ln]
    assert [ln for ln in new_lines if ln in old_lines] == old_lines


# ─── 25. CLI build/append 跨語言對拍（server.js spawn 面 + 落檔 byte 驗證）──────


def test_25_cli_build_append_cross_language(tmp_path):
    """atom_io_cli 新 action：build 內容與 py 直呼 byte-identical；append 對 CRLF 檔
    落檔 EOL 穩定。並 source-level 驗 server.js 已退役 js 自拼（delegation guard，
    同 test_14 手法）——兩語言收斂單一實作即 CRLF 跨語言對拍的成立條件。"""
    import os
    import subprocess

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    def run_cli(payload):
        proc = subprocess.run(
            [sys.executable, "-m", "lib.atom_io_cli"],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(LIB_PARENT), env=env, timeout=30,
        )
        assert proc.stdout, f"CLI no stdout; stderr={proc.stderr}"
        return json.loads(proc.stdout)

    # build：與 py build_atom_content byte-identical（含 block knowledge）
    kn = ["[固] 門檻：", "| 軌 | 值 |\n|---|---|\n| P | 4 |", "tail"]
    payload = dict(
        title="Cli Parity", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=kn, actions=["act1"],
        author="testuser", created_at="2026-05-01", today=FIXED_TODAY,
    )
    expected = build_atom_content(**payload)
    res = run_cli({"action": "build", **payload})
    assert res["ok"], res.get("error")
    assert res["extra"]["content"] == expected

    # append：CRLF 既有檔 → 落檔全 CRLF 零混寫（server.js spawn 的同一條路）
    fp = tmp_path / "cli-append.md"
    fp.write_bytes(expected.replace("\n", "\r\n").encode("utf-8"))
    res2 = run_cli({"action": "append", "file_path": str(fp),
                    "knowledge": ["cli-appended"], "source": "test"})
    assert res2["ok"], res2.get("error")
    raw = fp.read_bytes()
    assert b"\r\r\n" not in raw and raw.count(b"\n") == raw.count(b"\r\n")
    assert "- cli-appended".encode() in raw.split(b"\r\n")

    # delegation guard：server.js 三處已 spawn py、js 自拼 splice 已退役
    server_js = LIB_PARENT / "tools" / "workflow-guardian-mcp" / "server.js"
    if server_js.exists():
        js = server_js.read_text(encoding="utf-8")
        assert 'spawnAtomCli("build"' in js, "create/replace 未走 py build"
        assert 'spawnAtomCli("append"' in js, "append 未走 py append"
        assert 'existing.indexOf("## 行動")' not in js, "js 自拼 splice 未退役"


# ─── 26. 詞庫污染雙護欄（泛用詞拒收 + 亂碼 domain 拒收/降 Else）─────────────────


def test_26_learned_lexicon_pollution_guards(tmp_path, monkeypatch):
    """append_learned_terms sink 護欄：泛用詞（如 goal-driven-verify-loop 曾誤降）
    與亂碼 domain（如韓文「자동화」）拒收；classify_realm 出口對已污染
    learned 的亂碼 domain 降 Else。"""
    from lib import atom_locations as aloc

    fake = tmp_path / "_meta" / "realm-lexicon-learned.json"
    monkeypatch.setattr(aloc, "LEARNED_LEXICON_PATH", fake)

    aloc.append_learned_terms({
        "refactor": "Tools", "fix bug": "Tools", "verify": "Tools",
        "寫程式": "Tools", "verify loop": "Tools",             # 泛用詞 → 拒
        "badterm": "Tools/자동화流程與協議",                     # 亂碼 domain → 拒
        "wsl2": "OS/Windows/WSL",                               # 合法 → 收
        "skillbundle": "Tools/自動化流程與協議",                 # 合法 CJK domain → 收
    })
    learned = aloc.load_learned_lexicon()
    assert set(learned) == {"wsl2", "skillbundle"}, learned

    # classify_realm 出口 guard：已污染 learned 的亂碼 domain → 降 Else（不外流成資料夾名）
    polluted = {"weirdterm": "Tools/자동화"}
    r = aloc.classify_realm("weirdterm-case", [], extra_lexicon=polluted)
    assert r["realm"] == "local" and r["domain"] == aloc.LOCAL_REALM_DEFAULT_DOMAIN, r

    # is_generic_lexicon_term 邊界：全泛用 token 才拒；含實例 token 即收
    assert aloc.is_generic_lexicon_term("fix-bug")
    assert aloc.is_generic_lexicon_term("測試")
    assert not aloc.is_generic_lexicon_term("auto-handoff")
    assert not aloc.is_generic_lexicon_term("gpo")              # 既有 3 字 ASCII 實例詞不誤殺


# ─── 27. merged create_atom == 逐一 build+write_raw+init+set last_used+write_index ──


def test_27_create_atom_merged_byte_parity(isolated_claude, tmp_path):
    """create funnel 併單一 spawn：atom_io_cli.create_atom 一次落 .md / .access.json /
    index，須與『逐一呼叫 build+write_raw+init_access+set last_used+write_index』（同組
    函式、同順序）三件 byte-identical——守 5→1 spawn 合併為純重構、零行為變更。"""
    import json as _json
    from lib.atom_io_cli import create_atom
    from lib.atom_access import init_access, write_access_field
    from lib.atom_spec import validate_atom_content

    build_params = dict(
        title="Merge Parity", scope="global", confidence="[臨]",
        triggers=["a", "b", "c"], knowledge=["k1", "k2"], actions=["act1"],
        author="tester", created_at="2026-05-01",
    )
    slug, rel = "merge-parity", "merge-parity.md"

    # Path A — merged create_atom action
    dirA = tmp_path / "A"
    dirA.mkdir()
    fpA = dirA / "merge-parity.md"
    resA = create_atom({
        "build": build_params, "file_path": str(fpA), "today": FIXED_TODAY,
        "index": {"base_dir": str(dirA), "slug": slug, "rel_path": rel,
                  "triggers": build_params["triggers"]},
    })
    assert resA.ok, resA.error
    assert resA.extra["index_ok"] is True

    # Path B — 逐一呼叫同一組函式、同順序
    dirB = tmp_path / "B"
    dirB.mkdir()
    fpB = dirB / "merge-parity.md"
    content = build_atom_content(**build_params)
    assert validate_atom_content(content) is None
    atom_io.write_raw(fpB, content, source="mcp", op="atom_create")
    init_access(fpB, first_seen=FIXED_TODAY, source="mcp")
    write_access_field(fpB, field="last_used", value=FIXED_TODAY, source="mcp")
    atom_io.write_index(base_dir=dirB, slug=slug, rel_path=rel,
                        triggers=build_params["triggers"], source="mcp")

    # 三件 byte-identical
    assert fpA.read_bytes() == fpB.read_bytes(), "atom .md 不一致"
    assert fpA.with_suffix(".access.json").read_bytes() == \
        fpB.with_suffix(".access.json").read_bytes(), ".access.json 不一致"
    assert (dirA / "_atom_index.json").read_bytes() == \
        (dirB / "_atom_index.json").read_bytes(), "_atom_index.json 不一致"

    # 內容正確性抽驗（非只 A==B）
    assert "# Merge Parity" in fpA.read_text(encoding="utf-8")
    idx = _json.loads((dirA / "_atom_index.json").read_text(encoding="utf-8"))
    assert any(e["name"] == slug and e["path"] == rel for e in idx["atoms"])
    acc = _json.loads(fpA.with_suffix(".access.json").read_text(encoding="utf-8"))
    assert acc["first_seen"] == FIXED_TODAY and acc["last_used"] == FIXED_TODAY
    assert acc["read_hits"] == 0 and acc["confirmations"] == 0
