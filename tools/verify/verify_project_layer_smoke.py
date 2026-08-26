"""verify_project_layer_smoke.py — 專案層（<proj>/.claude/memory/）不受核心層範疇資料夾規則波及的 smoke。

核心層改用 memory/<範疇>/… 與 memory/Failures/<主題>/ 後，專案層記憶樹（shared/ 扁平或
shared/<domain>/）必須照舊：路徑判定、failures 落點、注入閘門、索引同步四條純函式通道
在 tmp 假專案上實跑，不碰現役 memory/。

計畫案例對照（「專案層即時驗證」節五斷言）：
  - 案例 1（SessionStart 在專案 cwd：additionalContext 不含 `_local_catalog.md`／`_AIDocs/_atoms/`
    atom；路徑判定與 failures 落點）：test_case1_*（subprocess 餵 hooks/workflow-guardian.py）
  - 案例 2（UserPromptSubmit 帶「上GIT」：命中已搬到 memory/版控/Git/ 的 atom，注入完全 index 驅動）：
    test_case2_*
  - 案例 3（`lib.atom_io_cli locate --scope shared --mode create`：無 domain 拒、domain=vcs →
    shared/版控/；`create_atom dry_run` 不落檔）：test_case3_*
  - 案例 4（memory-audit --project-dir 0 error；atom-categorize plan --memory-dir 出對映草案；
    conflict-review approve 經範疇閘）：test_case4_*
  - 案例 5（sync-memory-index --memory-dir 專案 catalog：marker 區塊 upsert、無 marker → check
    exit 1、CRLF 手寫段逐 byte 不動、不生 _INDEX.md／_local_catalog.md；`cwd=<tmp>/proj` 下
    run_verify 全綠由收尾手動跑）：test_case5_*
hook 子程序以唯一 session_id 跑真實 handler（同真 session 的副作用：workflow/state-<sid>.json，
測後刪；vector starter fire-and-forget 為 SessionStart 常態）。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest  # noqa: F401

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude
for _p in (CLAUDE_DIR / "hooks", CLAUDE_DIR / "lib", CLAUDE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from wg_core import (  # noqa: E402
    _is_under_claude_dir, get_project_memory_dir, resolve_failures_dir,
    is_local_realm_path as _wg_is_local_realm_path, is_cross_project_local,
)
from lib.atom_locations import (  # noqa: E402
    FAILURES_DIR, is_in_failures_path, is_local_realm_path,
)

SYNC_MEMORY_INDEX = CLAUDE_DIR / "tools" / "sync-memory-index.py"
MEMORY_AUDIT = CLAUDE_DIR / "tools" / "memory-audit.py"
ATOM_CATEGORIZE = CLAUDE_DIR / "tools" / "atom-categorize.py"


@pytest.fixture
def proj(tmp_path) -> Path:
    """<tmp>/proj/.claude/memory/{MEMORY.md,_atom_index.json,shared/}：最小專案層記憶樹。"""
    root = tmp_path / "proj"
    mem = root / ".claude" / "memory"
    (mem / "shared").mkdir(parents=True)
    (mem / "MEMORY.md").write_text("# Atom Index — Project\n\n| Atom | 說明 |\n|------|------|\n",
                                   encoding="utf-8")
    atoms = []
    for slug, sub in (("proj-rule-a", ""), ("proj-rule-b", "Domain")):
        d = mem / "shared" / sub if sub else mem / "shared"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{slug}.md").write_text(
            f"# {slug}\n\n- Scope: shared\n- Confidence: [臨]\n- Trigger: {slug}\n\n"
            f"## 知識\n\n- [臨] x\n\n## 行動\n\n- y\n",
            encoding="utf-8")
        rel = f"memory/shared/{sub + '/' if sub else ''}{slug}.md"
        atoms.append({"name": slug, "path": rel, "triggers": [slug], "scope": "shared"})
    (mem / "_atom_index.json").write_text(
        json.dumps({"version": "1.0", "atoms": atoms}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return root


# ─── 案例 1：專案層路徑判定與 failures 落點 ──────────────────────────────────


def test_case1_under_claude_dir_predicate(proj):
    assert _is_under_claude_dir(str(proj)) is False
    assert _is_under_claude_dir(str(CLAUDE_DIR)) is True


def test_case1_project_memory_dir_and_failures_dir(proj, tmp_path):
    mem = proj / ".claude" / "memory"
    assert get_project_memory_dir(str(proj)) == mem
    # 專案層 failures 落 <proj>/.claude/memory/failures（小寫，wg_core 現行行為；mkdir 副作用在 tmp）
    fd = resolve_failures_dir(str(proj))
    assert fd == mem / "failures"
    assert fd.is_dir()
    # 非專案 cwd → 全域 memory/Failures
    outside = tmp_path / "outside"
    outside.mkdir()
    assert resolve_failures_dir(str(outside)) == FAILURES_DIR
    assert resolve_failures_dir(r"C:\Windows\Temp") == FAILURES_DIR
    assert FAILURES_DIR == CLAUDE_DIR / "memory" / "Failures"
    # cwd 在 ~/.claude 本身（get_project_memory_dir 回根層 memory/）→ 也必須落全域家族目錄，
    # 不得走專案佈局長出小寫 memory/failures/（本 session 背景失敗萃取曾因此重生舊址）。
    assert resolve_failures_dir(str(CLAUDE_DIR)) == FAILURES_DIR
    assert resolve_failures_dir(str(CLAUDE_DIR / "tools")) == FAILURES_DIR
    assert not (CLAUDE_DIR / "memory" / "failures").exists() or \
        (CLAUDE_DIR / "memory" / "failures").resolve().name == "Failures"


# ─── 案例 1（續）：路徑前綴判定 + 注入閘門純函式 ──────────────────────────────


def _apply_gate(atoms, cwd):
    """對拍 lib/verify/verify_realm_injection_gate.py 的 _apply_gate（session_start 過濾邏輯）。"""
    if _wg_is_local_realm_path is not None and not _is_under_claude_dir(cwd):
        return [(n, p, t) for (n, p, t) in atoms
                if not _wg_is_local_realm_path(p) or is_cross_project_local(p)]
    return list(atoms)


def test_case1_path_predicates():
    assert is_local_realm_path("_AIDocs/_atoms/MemDev/x.md") is True
    assert is_in_failures_path("memory/Failures/驗證與實證/feedback-x.md") is True
    assert is_in_failures_path("_AIDocs/Failures/feedback-x.md") is True
    assert is_in_failures_path("memory/版控/Git/x.md") is False
    assert is_local_realm_path("memory/Failures/x/feedback-x.md") is False


def test_case1_injection_gate_from_project_keeps_core_category_atoms(proj):
    atoms = [
        ("decisions", "memory/decisions.md", ["決策"]),
        ("feedback-x", "memory/Failures/驗證與實證/feedback-x.md", ["驗證"]),
        ("feedback-legacy", "_AIDocs/Failures/feedback-legacy.md", ["舊址"]),
        ("git-hunk", "memory/版控/Git/git-hunk.md", ["hunk"]),
        ("brain", "_AIDocs/_atoms/MemDev/brain.md", ["腦內世界"]),
        ("handoff-q", "_AIDocs/_atoms/Continuity/handoff-q.md", ["handoff"]),  # local；跨專案清單為空 → 濾
    ]
    names = {n for n, _, _ in _apply_gate(atoms, str(proj))}
    assert names == {"decisions", "feedback-x", "feedback-legacy", "git-hunk"}
    # 核心環境不濾
    assert {n for n, _, _ in _apply_gate(atoms, str(CLAUDE_DIR))} == {n for n, _, _ in atoms}


# ─── 案例 4：memory-audit --project-dir 0 error；atom-categorize plan --memory-dir ──────


def _load_memory_audit():
    import importlib.util
    spec = importlib.util.spec_from_file_location("memory_audit_smoke", MEMORY_AUDIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_case4_memory_audit_project_layer_zero_error(proj, monkeypatch):
    """專案層（shared/ 平鋪 + shared/<Domain>/ 子夾）：index 為 entries、遞迴掃描 → 0 error。"""
    from argparse import Namespace
    mem = proj / ".claude" / "memory"
    MA = _load_memory_audit()
    monkeypatch.setattr(MA, "discover_layers", lambda *a, **k: [("project", mem)])
    monkeypatch.setattr(MA, "parse_audit_log", lambda: {})
    report = MA.run_audit(Namespace(global_only=False, project=None, project_dir=str(mem),
                                    verbose=False))
    errors = [i for i in report.issues if i.level == "error"]
    assert errors == [], [f"{i.file}: {i.message}" for i in errors]
    assert report.total_atoms == 2
    # 子夾 atom 已登記索引 → 不得誤報「未在索引中列出」
    assert not any("proj-rule-b" in i.message for i in report.issues), report.issues


def test_case4_atom_categorize_plan_project_layer(proj, tmp_path):
    """--memory-dir 對假專案：無 map 出詞庫草案；給 map 則產 shared/<範疇>/ 對映且不落地。"""
    mem = proj / ".claude" / "memory"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(ATOM_CATEGORIZE), "plan", "--memory-dir", str(mem)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=120)
    assert r.returncode == 0 and "Traceback" not in r.stderr, (r.stdout, r.stderr)
    draft = json.loads(r.stdout)
    assert draft.get("proposed") is True
    assert "proj-rule-a" in set(draft["atoms"]) | set(draft["undecided"])   # 平鋪者在草案範圍
    assert "proj-rule-b" not in draft["atoms"] and "proj-rule-b" not in draft["undecided"]  # 已在子夾

    mp = tmp_path / "map.json"
    mp.write_text(json.dumps({"atoms": {"proj-rule-a": "驗證與實證"}}, ensure_ascii=False),
                  encoding="utf-8")
    r = subprocess.run([sys.executable, str(ATOM_CATEGORIZE), "plan", "--map", str(mp),
                        "--memory-dir", str(mem), "--dry-run"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=120)
    assert r.returncode == 0 and "Traceback" not in r.stderr, (r.stdout, r.stderr)
    plan = json.loads(r.stdout)
    assert plan["layer"] == "project" and plan["errors"] == []
    assert plan["items"][0]["to"] == "memory/shared/驗證與實證/proj-rule-a.md"
    assert (mem / "shared" / "proj-rule-a.md").exists()   # plan 不搬


# ─── 案例 5：sync-memory-index --check 對專案層索引 ───────────────────────────


def test_case5_sync_memory_index_check_no_traceback(proj):
    mem = proj / ".claude" / "memory"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(
        [sys.executable, str(SYNC_MEMORY_INDEX), "--check", "--memory-dir", str(mem)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=120,
    )
    assert r.returncode in (0, 1), (r.returncode, r.stdout, r.stderr)
    assert "Traceback" not in r.stderr, r.stderr
    assert "Traceback" not in r.stdout, r.stdout
    # --check 不得寫檔：MEMORY.md 原樣
    assert (mem / "MEMORY.md").read_text(encoding="utf-8").startswith("# Atom Index — Project")


# ─── hook 子程序 harness（計畫：subprocess 餵 SessionStart／UserPromptSubmit JSON）────────

GUARDIAN = CLAUDE_DIR / "hooks" / "workflow-guardian.py"
CONFLICT_REVIEW = CLAUDE_DIR / "tools" / "conflict-review.py"
_ENV = dict(os.environ, PYTHONIOENCODING="utf-8")


def _run_hook(event: str, cwd: Path, session_id: str, **extra) -> str:
    """跑真實 dispatcher，回 additionalContext（無 JSON 輸出 → ""）。"""
    data = {"hook_event_name": event, "cwd": str(cwd), "session_id": session_id, **extra}
    r = subprocess.run([sys.executable, str(GUARDIAN)], input=json.dumps(data, ensure_ascii=False),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=_ENV, cwd=str(cwd), timeout=180)
    assert "Traceback" not in r.stderr, r.stderr
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            out = json.loads(line)
        except ValueError:
            continue
        return str((out.get("hookSpecificOutput") or {}).get("additionalContext") or "")
    return ""


@pytest.fixture
def hook_session(proj):
    """唯一 session_id；測後清掉 workflow/state-<sid>.json（hook 真跑的唯一持久副作用）。"""
    import uuid
    from wg_core import state_path
    sid = f"s5smoke-{uuid.uuid4().hex[:12]}"
    yield sid
    try:
        state_path(sid).unlink()
    except FileNotFoundError:
        pass


def _cli(payload: dict) -> dict:
    r = subprocess.run([sys.executable, "-m", "lib.atom_io_cli"],
                       input=json.dumps(payload, ensure_ascii=False),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=_ENV, cwd=str(CLAUDE_DIR), timeout=120)
    assert "Traceback" not in r.stderr, r.stderr
    return json.loads(r.stdout)


def _gate_on() -> bool:
    from lib.atom_io import _category_gate_enabled
    return bool(_category_gate_enabled())


# ─── 案例 1（hook）：SessionStart 在專案 cwd 不外洩本地範疇 ───────────────────────


def test_case1_session_start_from_project_hides_local_catalog(proj, hook_session):
    ctx = _run_hook("SessionStart", proj, hook_session, source="startup")
    assert ctx, "SessionStart 無 additionalContext"
    assert "_local_catalog.md" not in ctx
    assert "本地範疇 Catalog" not in ctx
    assert "_AIDocs/_atoms/" not in ctx
    for m in re.finditer(r"Read (\S+\.md)", ctx):
        p = m.group(1).replace("\\", "/")
        assert "_AIDocs/_atoms/" not in p, p


# ─── 案例 2（hook）：UserPromptSubmit「上GIT」命中 memory/版控/Git/ 的 atom ───────────


def test_case2_ups_upgit_hits_category_atom(proj, hook_session):
    from lib.atom_index_json import load_atom_index_json
    rows = {a["name"]: a["path"] for a in load_atom_index_json(CLAUDE_DIR / "memory")["atoms"]}
    target = "併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a"
    assert rows.get(target, "").startswith("memory/版控/Git/"), rows.get(target)
    _run_hook("SessionStart", proj, hook_session, source="startup")   # 建 state（atom_index 快取）
    ctx = _run_hook("UserPromptSubmit", proj, hook_session, prompt="這段改完幫我上GIT")
    assert f"[Atom:{target}]" in ctx, ctx[:2000]
    assert "_AIDocs/_atoms/" not in ctx


# ─── 案例 3：locate(mode=create) 專案 shared 閘 + create_atom dry_run ─────────────────


def test_case3_locate_shared_create_requires_domain(proj):
    if not _gate_on():
        pytest.skip("taxonomy.gate_enabled=false")
    base = {"action": "locate", "title": "專案層閘測試", "scope": "shared",
            "project_cwd": str(proj), "mode": "create"}
    r = _cli(base)
    assert r["ok"] is False and "domain" in r["error"] and "版控" in r["error"], r
    r = _cli({**base, "domain": "vcs"})
    assert r["ok"] is True and r["path"] is None, r
    target = Path(r["extra"]["target_dir"])
    assert target == proj / ".claude" / "memory" / "shared" / "版控", target
    assert r["extra"]["category"] == "版控"


def test_case3_create_atom_dry_run_writes_nothing(proj):
    mem = proj / ".claude" / "memory"
    fp = mem / "shared" / "驗證與實證" / "dry-run-probe.md"
    r = _cli({
        "action": "create_atom", "dry_run": True,
        "build": {"title": "dry-run-probe", "scope": "shared", "confidence": "[臨]",
                  "triggers": ["dry-run-probe"], "knowledge": ["[臨] x"], "actions": ["y"]},
        "file_path": str(fp), "today": "2026-08-26",
        "index": {"base_dir": str(mem), "slug": "dry-run-probe",
                  "rel_path": "memory/shared/驗證與實證/dry-run-probe.md",
                  "triggers": ["dry-run-probe"], "scope": "shared"},
    })
    assert r["ok"] is True and r["extra"].get("dry_run") is True, r
    assert Path(r["path"]) == fp
    assert not fp.exists() and not fp.with_suffix(".access.json").exists()
    from lib.atom_index_json import load_atom_index_json
    assert "dry-run-probe" not in {a["name"] for a in load_atom_index_json(mem)["atoms"]}


# ─── 案例 4（續）：conflict-review approve 經範疇閘落 shared/<Lv1>/ + index upsert ─────


def _load_conflict_review():
    import importlib.util
    spec = importlib.util.spec_from_file_location("conflict_review_smoke", CONFLICT_REVIEW)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pending_draft(mem: Path, stem: str) -> Path:
    pdir = mem / "shared" / "_pending_review"
    pdir.mkdir(parents=True, exist_ok=True)
    p = pdir / f"{stem}.md"
    p.write_text(f"# {stem}\n\n- Scope: shared\n- Confidence: [臨]\n- Trigger: git, commit\n"
                 f"- Pending-review-by: management\n\n## 知識\n\n- [臨] x\n\n## 行動\n\n- y\n",
                 encoding="utf-8")
    return p


def _patched_conflict_review(monkeypatch):
    CR = _load_conflict_review()
    monkeypatch.setattr(CR, "is_management", lambda *a, **k: True)
    monkeypatch.setattr(CR, "_trigger_reindex", lambda: False)
    monkeypatch.setattr(CR, "_sync_project_catalog", lambda mem: None)
    return CR


def test_case4_conflict_approve_lands_in_category(proj, monkeypatch):
    if not _gate_on():
        pytest.skip("taxonomy.gate_enabled=false")
    CR = _patched_conflict_review(monkeypatch)
    mem = proj / ".claude" / "memory"
    src = _pending_draft(mem, "approve-vcs-probe")
    res = CR.action_approve(str(proj), "approve-vcs-probe", "tester", domain="vcs/git")
    assert res.get("ok") is True, res
    dest = mem / "shared" / "版控" / "Git" / "approve-vcs-probe.md"
    assert dest.is_file() and not src.exists()
    assert res["category"] == "版控/Git"
    assert res["rel_path"] == "memory/shared/版控/Git/approve-vcs-probe.md"
    assert res["index_ok"] is True, res
    from lib.atom_index_json import load_atom_index_json
    rows = {a["name"]: a for a in load_atom_index_json(mem)["atoms"]}
    assert rows["approve-vcs-probe"]["path"] == res["rel_path"]
    assert rows["approve-vcs-probe"]["triggers"] == ["git", "commit"]


def test_case4_conflict_approve_unclassified_stays_pending(proj, monkeypatch):
    if not _gate_on():
        pytest.skip("taxonomy.gate_enabled=false")
    CR = _patched_conflict_review(monkeypatch)
    monkeypatch.setattr(CR, "classify_category",
                        lambda *a, **k: {"status": "unsure", "category": None, "reason": "stub"})
    mem = proj / ".claude" / "memory"
    src = _pending_draft(mem, "approve-unsure-probe")
    res = CR.action_approve(str(proj), "approve-unsure-probe", "tester")
    assert "error" in res and "--domain" in res["error"], res
    assert src.exists()                                                # 草稿留 pending
    assert not (mem / "shared" / "approve-unsure-probe.md").exists()   # 不落未分類 shared
    res = CR.action_approve(str(proj), "approve-unsure-probe", "tester", domain="NoSuchCat")
    assert "error" in res and src.exists()                             # 未知 Lv1 也拒


# ─── 案例 5（續）：sync-memory-index --memory-dir 專案 catalog（marker 區塊 upsert）──────


def _smi(mem: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SYNC_MEMORY_INDEX), *flags, "--memory-dir", str(mem)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=_ENV, timeout=120)


def test_case5_project_catalog_dry_run_rows(proj):
    mem = proj / ".claude" / "memory"
    r = _smi(mem)
    assert r.returncode == 0, (r.stdout, r.stderr)
    out = r.stdout
    assert "<!-- atom-catalog -->" in out and "<!-- /atom-catalog -->" in out
    assert "| Domain | 1 | `memory/shared/Domain/proj-rule-b.md` |" in out   # 範疇列（單葉直指 atom）
    assert "尚未歸類（shared/ 平鋪）" in out and "| proj-rule-a |" in out   # 平鋪 shared 逐顆列
    assert "# Atom Index — Global" not in out
    assert "_local_catalog" not in out


HANDWRITTEN_CRLF = (
    "# Atom Index — Proj\r\n\r\n> 手寫分區規則\r\n\r\n| Atom | Path |\r\n|---|---|\r\n"
    "| a | memory/shared/a.md |\r\n"
).encode("utf-8")


def test_case5_project_catalog_check_missing_then_write_preserves_crlf(proj):
    mem = proj / ".claude" / "memory"
    (mem / "MEMORY.md").write_bytes(HANDWRITTEN_CRLF)
    # 無 marker → --check drift（exit 1 + 專用訊息）
    r = _smi(mem, "--check")
    assert r.returncode == 1 and "project catalog block missing" in r.stderr, (r.returncode, r.stderr)
    # --write 追加檔尾；手寫段逐 byte 不動；行尾沿用 CRLF；不生 _INDEX.md / _local_catalog.md
    w = _smi(mem, "--write")
    assert w.returncode == 0, (w.stdout, w.stderr)
    raw = (mem / "MEMORY.md").read_bytes()
    assert raw.startswith(HANDWRITTEN_CRLF.rstrip(b"\r\n")), raw[:200]
    assert b"<!-- atom-catalog -->" in raw and b"<!-- /atom-catalog -->" in raw
    assert b"\n" not in raw.replace(b"\r\n", b""), "出現非 CRLF 行尾"
    assert not list(mem.rglob("_INDEX.md")) and not (mem / "_local_catalog.md").exists()
    # 已同步 → --check 0；再 --write 冪等
    assert _smi(mem, "--check").returncode == 0
    before = raw
    assert _smi(mem, "--write").returncode == 0
    assert (mem / "MEMORY.md").read_bytes() == before
    # index 變動 → 只換區塊，手寫段仍原樣
    from lib.atom_index_json import upsert_atom
    d = mem / "shared" / "驗證與實證"
    d.mkdir(parents=True, exist_ok=True)
    (d / "proj-rule-c.md").write_text(
        "# proj-rule-c\n\n- Scope: shared\n- Confidence: [臨]\n- Trigger: c\n\n"
        "## 知識\n\n- [臨] x\n\n## 行動\n\n- y\n", encoding="utf-8")
    upsert_atom(mem, "proj-rule-c", "memory/shared/驗證與實證/proj-rule-c.md", ["c"], scope="shared")
    assert _smi(mem, "--check").returncode == 1
    assert _smi(mem, "--write").returncode == 0
    raw2 = (mem / "MEMORY.md").read_bytes()
    assert raw2.startswith(HANDWRITTEN_CRLF.rstrip(b"\r\n"))
    assert raw2.count(b"<!-- atom-catalog -->") == 1
    assert "| 驗證與實證 | 1 |".encode("utf-8") in raw2
