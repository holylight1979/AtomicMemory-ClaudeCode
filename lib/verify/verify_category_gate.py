"""verify_category_gate.py — 核心記憶分類階層化：範疇寫入閘（S4）。

不變式（計畫 §3／§4）：
  - mode=create 且 gate 開：scope=global 非 local／feedback- 標題／scope=shared 的 domain 必填；
    缺或未知 Lv1 → 拒並列出全部 Lv1；別名／大小寫 snap 回正名；allow_new_category 才准新 Lv1；
    保留名即使 allow_new 也拒。
  - append/replace 忽略 domain（stderr 提示、不阻斷）；role/personal/_pending_review 不受閘影響。
  - gate 關 → 退回扁平舊落點（相容分支，釘住只在 false 時生效）。
  - locate(mode=create) 回 extra.target_dir/category 給 js。
  - 程式寫手：classify_category 詞庫命中→用；LLM stub unsure/error → 拒；
    extract-worker 失敗回寫永不拒（fallback 主題）+ 新建檔 index upsert。
  - episodic/_drafts 不是 atom：不經閘、不進 index。
全程 tmp 樹（monkeypatch atom_io / atom_locations 的根），不碰現役 memory/。
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude
sys.path.insert(0, str(CLAUDE))

from lib import atom_io  # noqa: E402
from lib import atom_locations as aloc  # noqa: E402
from lib.atom_io import write_atom, locate_atom  # noqa: E402
from lib.atom_io_cli import create_atom  # noqa: E402
from lib.atom_index_json import load_atom_index_json  # noqa: E402

TODAY = "2026-08-26"
ALL_LV1 = ["版控", "工作流", "思考與決策", "驗證與實證", "dotnet", "OS-Windows",
           "文字與格式", "設計通則", "行為契約", "CC與原子記憶契約"]


@pytest.fixture
def tmp_claude(tmp_path, monkeypatch):
    """假 ~/.claude 樹 + gate 強制開；atom_io 與 atom_locations 的根全指 tmp。"""
    claude = tmp_path / ".claude"
    mem = claude / "memory"
    (mem / "_meta").mkdir(parents=True)
    monkeypatch.setattr(atom_io, "CLAUDE_DIR", claude)
    monkeypatch.setattr(atom_io, "GLOBAL_MEMORY_DIR", mem)
    monkeypatch.setattr(atom_io, "AUDIT_LOG", mem / "_meta" / "atom_io_audit.jsonl")
    monkeypatch.setattr(atom_io, "_category_gate_enabled", lambda: True)
    monkeypatch.setattr(aloc, "CLAUDE_DIR", claude)
    monkeypatch.setattr(aloc, "GLOBAL_MEMORY_DIR", mem)
    monkeypatch.setattr(aloc, "FAILURES_DIR", mem / "Failures")
    monkeypatch.setattr(aloc, "LOCAL_ATOMS_DIR", claude / "_AIDocs" / "_atoms")
    monkeypatch.setattr(aloc, "TAXONOMY_LEARNED_PATH", mem / "_meta" / "taxonomy-lexicon-learned.json")
    return {"claude": claude, "memory": mem}


def _create(title, **kw):
    base = dict(title=title, scope="global", confidence="[臨]", triggers=["a", "b", "c"],
                knowledge=["k"], mode="create", source="test", skip_gate=True, today=TODAY)
    base.update(kw)
    return write_atom(**base)


def _mkproject(tmp_path: Path) -> Path:
    mem = tmp_path / "proj" / ".claude" / "memory"
    mem.mkdir(parents=True)
    (tmp_path / "proj" / ".git").mkdir()
    (mem / "MEMORY.md").write_text("# idx\n", encoding="utf-8")
    (mem / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": []}), encoding="utf-8")
    return tmp_path / "proj"


# ─── 1–4：閘的四種裁決 ────────────────────────────────────────────────────────

def test_global_create_without_domain_rejected_lists_all_lv1(tmp_claude):
    r = _create("No Domain Atom")
    assert not r.ok
    assert "unclassified core atom rejected" in r.error
    for lv1 in ALL_LV1:
        assert lv1 in r.error, f"錯誤訊息缺 Lv1：{lv1}"
    assert "allow_new_category" in r.error
    assert not list(tmp_claude["memory"].rglob("*.md")), "拒寫不得落檔"


def test_alias_and_casefold_snap_to_canonical(tmp_claude):
    r = _create("Git Hunk", domain="vcs/git")
    assert r.ok, r.error
    assert r.path == tmp_claude["memory"] / "版控" / "Git" / "git-hunk.md"
    assert r.extra["category"] == "版控/Git"
    # 別名（大小寫混）→ 正名；Lv2 對既有兄弟 snap
    r2 = _create("Svn Thing", domain="VCS/svn")
    assert r2.ok, r2.error
    assert r2.path.parent == tmp_claude["memory"] / "版控" / "SVN"
    # index path 正名（Windows 不分大小寫下絕不能分岔）
    idx = load_atom_index_json(tmp_claude["memory"])
    paths = {a["name"]: a["path"] for a in idx["atoms"]}
    assert paths["git-hunk"] == "memory/版控/Git/git-hunk.md"
    assert paths["svn-thing"] == "memory/版控/SVN/svn-thing.md"


def test_new_lv1_requires_allow_new_category(tmp_claude):
    r = _create("Brand New", domain="量子運算")
    assert not r.ok and "unclassified core atom" in r.error
    r2 = _create("Brand New", domain="量子運算", allow_new_category=True)
    assert r2.ok, r2.error
    assert r2.path == tmp_claude["memory"] / "量子運算" / "brand-new.md"


def test_reserved_name_rejected_even_with_allow_new(tmp_claude):
    for bad in ("templates", "_meta", "personal", "failures", "shared", "memory"):
        r = _create("Reserved Probe", domain=bad, allow_new_category=True)
        assert not r.ok, f"{bad!r} 應拒"
    # Failures 家族不走 core_write_target（要用 feedback- 標題／topic）
    r = _create("Not Feedback", domain="Failures/驗證與實證")
    assert not r.ok and "failures routing" in r.error


# ─── 5：失敗家族主題 ─────────────────────────────────────────────────────────

def test_feedback_title_with_topic_lands_failures_topic(tmp_claude):
    r = _create("feedback-gate-probe", domain="驗證與實證")
    assert r.ok, r.error
    assert r.path == tmp_claude["memory"] / "Failures" / "驗證與實證" / "feedback-gate-probe.md"
    assert r.extra["category"] == "Failures/驗證與實證"
    # 別名 + 前導 Failures/ 皆可
    r2 = _create("feedback-gate-probe-2", domain="Failures/verify")
    assert r2.ok and r2.path.parent.name == "驗證與實證"
    # 無 domain → 拒並列主題
    r3 = _create("feedback-gate-probe-3")
    assert not r3.ok and "unclassified failures atom" in r3.error and "驗證與實證" in r3.error


# ─── 6：append/replace 忽略 domain ────────────────────────────────────────────

def test_append_replace_ignore_domain_with_stderr_note(tmp_claude):
    r = _create("Append Me", domain="設計通則")
    assert r.ok, r.error
    buf = io.StringIO()
    with redirect_stderr(buf):
        a = write_atom(title="Append Me", scope="global", confidence="[臨]", triggers=["a", "b", "c"],
                       knowledge=["more"], mode="append", source="test", skip_gate=True,
                       today=TODAY, domain="vcs")  # 錯的 domain 也不影響定位
    assert a.ok, a.error
    assert a.path == r.path
    assert "domain='vcs' ignored" in buf.getvalue()
    # append 不帶 domain 也通（閘只管 create）
    a2 = write_atom(title="Append Me", scope="global", confidence="[臨]", triggers=["a", "b", "c"],
                    knowledge=["more2"], mode="append", source="test", skip_gate=True, today=TODAY)
    assert a2.ok, a2.error


# ─── 7：詞庫命中 ─────────────────────────────────────────────────────────────

def test_hook_lexicon_hit_classifies(tmp_claude):
    r = aloc.classify_category("git-staging-hunk-選擇", ["上git", "staging"])
    assert r["status"] == "lex" and r["category"] == "版控", r
    # learned 詞庫補充 → 命中且可指到 Lv2
    aloc.append_learned_terms({"tortoisegit": "版控/Git"}, path=aloc.TAXONOMY_LEARNED_PATH)
    r2 = aloc.classify_category("tortoisegit-右鍵選單", ["gui"])
    assert r2["status"] == "lex" and r2["category"] == "版控/Git", r2
    # learned 指向不存在的 Lv1 → 忽略
    aloc.append_learned_terms({"zzzterm": "不存在範疇"}, path=aloc.TAXONOMY_LEARNED_PATH)
    r3 = aloc.classify_category("zzzterm-only", [], config={"taxonomy": {"llm_fallback": {"enabled": False}}})
    assert r3["status"] == "unsure", r3
    # failures 層：主題名同核心 Lv1
    r4 = aloc.classify_category("驗證腳本假通過", ["smoke"], layer="failures")
    assert r4["status"] == "lex" and r4["category"] == "驗證與實證", r4


# ─── 8：LLM stub unsure / error → 拒 ─────────────────────────────────────────

def test_llm_stub_unsure_and_error_rejected(tmp_claude, monkeypatch):
    cfg = {"taxonomy": {"llm_fallback": {"enabled": True, "max_per_session": 5, "min_confidence": 0.7}}}
    monkeypatch.setattr(aloc, "_LLM_CATEGORY_CALLS", 0)
    calls = []

    def stub_unsure(name, triggers, excerpt, cats, layer="core"):
        calls.append(name)
        return {"status": "unsure", "category": None, "confidence": 0.2, "terms": [], "reason": "no idea"}

    def stub_error(name, triggers, excerpt, cats, layer="core"):
        return {"status": "error", "category": None, "confidence": 0.0, "terms": [], "reason": "down"}

    def stub_low_conf(name, triggers, excerpt, cats, layer="core"):
        return {"status": "hit", "category": "版控", "confidence": 0.3, "terms": ["foo"], "reason": "weak"}

    def stub_hit(name, triggers, excerpt, cats, layer="core"):
        return {"status": "hit", "category": "版控", "confidence": 0.9, "terms": ["gitea-webhook"], "reason": "ok"}

    r = aloc.classify_category("無關名稱", ["xyz"], config=cfg, llm=stub_unsure)
    assert r["status"] == "unsure" and r["category"] is None and calls == ["無關名稱"]
    r = aloc.classify_category("無關名稱", ["xyz"], config=cfg, llm=stub_error)
    assert r["status"] == "error" and r["category"] is None
    r = aloc.classify_category("無關名稱", ["xyz"], config=cfg, llm=stub_low_conf)
    assert r["status"] == "unsure", r
    r = aloc.classify_category("無關名稱", ["xyz"], config=cfg, llm=stub_hit)
    assert r["status"] == "llm" and r["category"] == "版控", r
    # 命中回寫 learned → 下次詞庫直接命中、不再喚 LLM
    r2 = aloc.classify_category("gitea-webhook 設定", ["ci"], config=cfg, llm=stub_error)
    assert r2["status"] == "lex" and r2["category"] == "版控", r2
    # disabled → 不喚 LLM 直接 unsure
    off = {"taxonomy": {"llm_fallback": {"enabled": False}}}
    r3 = aloc.classify_category("無關名稱", ["xyz"], config=off, llm=stub_hit)
    assert r3["status"] == "unsure" and "disabled" in r3["reason"]
    # max_per_session 封頂
    monkeypatch.setattr(aloc, "_LLM_CATEGORY_CALLS", 5)
    r4 = aloc.classify_category("無關名稱", ["xyz"], config=cfg, llm=stub_hit)
    assert r4["status"] == "unsure" and "max_per_session" in r4["reason"]


# ─── 9：失敗回寫 fallback + index upsert ─────────────────────────────────────

def _load_extract_worker():
    spec = importlib.util.spec_from_file_location("extract_worker", CLAUDE / "hooks" / "extract-worker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_failure_writeback_fallback_topic_and_index_upsert(tmp_claude, monkeypatch):
    ew = _load_extract_worker()
    fdir = tmp_claude["memory"] / "Failures"
    monkeypatch.setattr(ew, "resolve_failures_dir", lambda cwd: fdir)
    (tmp_claude["memory"] / "_atom_index.json").write_text(
        json.dumps({"version": "1.0", "atoms": []}), encoding="utf-8")
    # (a) 詞庫 miss → failure_type_fallback：env → OS-Windows；永不拒
    item = {"content": "改設定沒重啟服務 → 設定沒生效 → 重啟後正常（根因: 啟動時讀快取）",
            "failure_type": "env", "domain_tags": []}
    ew._failure_writeback({"cwd": "", "config": {}}, [item])
    target = fdir / "OS-Windows" / "env-traps-os-windows.md"
    assert target.exists(), sorted(p.as_posix() for p in fdir.rglob("*"))
    idx = load_atom_index_json(tmp_claude["memory"])
    entry = next(a for a in idx["atoms"] if a["name"] == "env-traps-os-windows")
    assert entry["path"] == "memory/Failures/OS-Windows/env-traps-os-windows.md"
    assert entry["scope"] == "global" and entry["triggers"]
    # (b) 詞庫命中 → 主題＝命中範疇（silent 型但內容講 git）
    item2 = {"content": "git commit 前沒核對 staged 清單 → 掃進別人的檔 → 選擇性 staging（根因: git add -A）",
             "failure_type": "silent", "domain_tags": ["git"]}
    ew._failure_writeback({"cwd": "", "config": {}}, [item2])
    assert (fdir / "版控" / "silent-failures-版控.md").exists()
    # (c) 同條再寫 → 去重、index 不重複
    ew._failure_writeback({"cwd": "", "config": {}}, [item2])
    text = (fdir / "版控" / "silent-failures-版控.md").read_text(encoding="utf-8")
    assert text.count("**始末**") == 1
    idx = load_atom_index_json(tmp_claude["memory"])
    assert [a["name"] for a in idx["atoms"]].count("silent-failures-版控") == 1


# ─── 10–11：專案層 + 豁免 ────────────────────────────────────────────────────

def test_shared_create_requires_domain_and_lands_category(tmp_claude, tmp_path):
    proj = _mkproject(tmp_path)
    bad = _create("Proj Atom", scope="shared", project_cwd=str(proj))
    assert not bad.ok and "unclassified shared atom" in bad.error and "版控" in bad.error
    ok = _create("Proj Atom", scope="shared", project_cwd=str(proj), domain="workflow")
    assert ok.ok, ok.error
    assert ok.path == proj / ".claude" / "memory" / "shared" / "工作流" / "proj-atom.md"
    # subdir 分區 + 範疇
    sub = _create("Part Atom", scope="shared", project_cwd=str(proj), subdir="projects/x", domain="vcs/git")
    assert sub.ok, sub.error
    assert sub.path == proj / ".claude" / "memory" / "projects" / "x" / "版控" / "Git" / "part-atom.md"
    # 專案自訂 Lv1（shared/_taxonomy.json domains）也算閉合清單成員
    (proj / ".claude" / "memory" / "shared" / "_taxonomy.json").write_text(
        json.dumps({"domains": {"Billing": {"terms": ["invoice"]}}}), encoding="utf-8")
    custom = _create("Bill Atom", scope="shared", project_cwd=str(proj), domain="billing")
    assert custom.ok, custom.error
    assert custom.path.parent.name == "Billing"


def test_pending_review_and_role_personal_exempt(tmp_claude, tmp_path):
    proj = _mkproject(tmp_path)
    pend = _create("Decision Atom", scope="shared", project_cwd=str(proj), audience=["decision"])
    assert pend.ok and pend.routed_to_pending and "_pending_review" in str(pend.path)
    role = _create("Role Atom", scope="role", role="art", project_cwd=str(proj))
    assert role.ok and role.path.parent == proj / ".claude" / "memory" / "roles" / "art"
    pers = _create("Personal Atom", scope="personal", user="alice", project_cwd=str(proj))
    assert pers.ok and pers.path.parent == proj / ".claude" / "memory" / "personal" / "alice"
    # local realm：domain 是 _AIDocs/_atoms/ 階層 domain，不走核心閉合清單
    loc = _create("Local Note", realm="local", domain="MemDev/Probe")
    assert loc.ok, loc.error
    assert loc.path == tmp_claude["claude"] / "_AIDocs" / "_atoms" / "MemDev" / "Probe" / "local-note.md"


# ─── 12：gate 關 → 扁平相容分支（釘住只在 false 時生效）────────────────────────

def test_gate_disabled_falls_back_flat(tmp_claude, monkeypatch):
    monkeypatch.setattr(atom_io, "_category_gate_enabled", lambda: False)
    r = _create("Flat Legacy")
    assert r.ok, r.error
    assert r.path == tmp_claude["memory"] / "flat-legacy.md"
    # 關閘但給了合法 domain → 仍尊重範疇
    r2 = _create("Flat Legacy 2", domain="設計通則")
    assert r2.ok and r2.path.parent.name == "設計通則"
    # 開閘後同樣的無 domain 呼叫必拒（相容分支只在 false 時生效）
    monkeypatch.setattr(atom_io, "_category_gate_enabled", lambda: True)
    r3 = _create("Flat Legacy 3")
    assert not r3.ok


# ─── 13：locate(mode=create) 回 target_dir + create_atom 後盾 ──────────────────

def test_locate_mode_create_returns_target_dir(tmp_claude):
    r = locate_atom("Brand New Locate", "global", mode="create", domain="vcs/git")
    assert r.ok and r.path is None
    assert r.extra["found"] is False
    assert Path(r.extra["target_dir"]) == tmp_claude["memory"] / "版控" / "Git"
    assert r.extra["category"] == "版控/Git"
    bad = locate_atom("Brand New Locate", "global", mode="create")
    assert not bad.ok and "unclassified core atom" in bad.error
    # 無 mode（append/replace 定位）不開閘
    ok = locate_atom("Brand New Locate", "global")
    assert ok.ok and ok.path is None
    # create_atom（js 算好 file_path 才 spawn）後盾：平鋪／舊址 rel_path 一律拒
    build = dict(title="Backstop", scope="global", confidence="[臨]", triggers=["a", "b", "c"],
                 knowledge=["k"], created_at=TODAY)
    for rel in ("memory/backstop.md", "_AIDocs/Failures/feedback-backstop.md",
                "memory/Failures/feedback-backstop.md"):
        res = create_atom({"build": build, "file_path": str(tmp_claude["claude"] / rel), "today": TODAY,
                           "index": {"base_dir": str(tmp_claude["memory"]), "slug": "backstop",
                                     "rel_path": rel, "triggers": ["a"]}})
        assert not res.ok and "category gate" in res.error, (rel, res)
        assert not (tmp_claude["claude"] / rel).exists()
    good = create_atom({"build": build, "file_path": str(tmp_claude["memory"] / "設計通則" / "backstop.md"),
                        "today": TODAY,
                        "index": {"base_dir": str(tmp_claude["memory"]), "slug": "backstop",
                                  "rel_path": "memory/設計通則/backstop.md", "triggers": ["a"]}})
    assert good.ok, good.error


# ─── 14：episodic / _drafts 豁免 ─────────────────────────────────────────────

def test_episodic_and_drafts_exempt(tmp_claude):
    """episodic/ 與 _drafts/ 不是 atom：write_raw 直寫不經範疇閘、不進 index。"""
    from lib.atom_io import write_raw
    from lib.atom_spec import is_atom_file
    (tmp_claude["memory"] / "_atom_index.json").write_text(
        json.dumps({"version": "1.0", "atoms": []}), encoding="utf-8")
    epi = tmp_claude["memory"] / "episodic" / "episodic-20260826-probe.md"
    draft = tmp_claude["memory"] / "_drafts" / "auto-capture" / "some-draft.md"
    for p, src in ((epi, "hook:episodic"), (draft, "hook:extract-worker")):
        p.parent.mkdir(parents=True, exist_ok=True)
        res = write_raw(p, "# probe\n\n- Trigger: x\n\n## 知識\n\n- k\n", source=src)
        assert res.ok, res.error
        assert p.exists()
        assert not is_atom_file(p, tmp_claude["memory"]), f"{p} 不該被當 atom 掃"
    idx = load_atom_index_json(tmp_claude["memory"])
    assert idx["atoms"] == []
