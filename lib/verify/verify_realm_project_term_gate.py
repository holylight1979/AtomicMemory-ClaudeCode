"""verify_realm_project_term_gate.py — 「專案專屬內容不得落 global」realm 閘守門。

起因（實案）：在某多 repo 工作區的 session 以 scope=global（且 skip_gate=true）寫進
「此專案下 <伺服器 repo>/ <用戶端 repo>/ Tools/ …」的 feedback atom，create／replace 兩路都放行，
落到全域 memory/Failures/ 被所有專案注入。測試用虛構名 game_server／game_client 重現同一形狀。

不變式：
1. 專名機械化推導（lib/realm_gate.py）：頂層資料夾 / CLAUDE.md、Workspace_Map 成員表 /
   repo-paths `{代號}` / 專案絕對路徑 / 「此專案」字面；與 ~/.claude 頂層同名者與泛詞排除。
2. py funnel `write_atom`：scope=global 的 create/append/replace 帶專名 → 拒；skip_gate 不豁免；
   cwd∈~/.claude 只掃已登記專案名（見 5）；不帶專名的通則放行。
3. MCP js `toolAtomWrite`：原 payload create / replace / skip_gate=true 三者皆拒（缺 project_cwd
   退用進程 cwd 也拒）；同 payload scope=shared + project_cwd 放行、落 failures/版控/SVN/。
4. atom-move：搬後檔頭 `- Scope:` 對齊索引 scope；既有 validate 錯誤與本次分離（exit 0 +
   index_preexisting_issues）；目錄重生（catalog_sync）有跑。
5. 已登記專案名（registry 根資料夾名＋ASCII 別名＋project_names 手列）在根層 cwd 也擋；
   泛名與公司層 repo 名不擋；本人跨專案 personal 同受此閘；anonymize_projects 換掉名字與路徑。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude
sys.path.insert(0, str(CLAUDE))

from lib import atom_io  # noqa: E402
from lib.atom_io import write_atom, locate_atom  # noqa: E402
from lib.atom_index_json import load_atom_index_json  # noqa: E402
from lib import realm_gate  # noqa: E402
from lib.realm_gate import project_terms, scan_texts, check_global_write, anonymize_projects  # noqa: E402

ATOM_TOOLS_JS = CLAUDE / "tools" / "workflow-guardian-mcp" / "lib" / "atom-tools.js"
ATOM_MOVE = CLAUDE / "tools" / "atom-move.py"

# ── 實案 payload（原封不動）──
TITLE = "feedback-svn-commit-一律先問使用者確認-計畫核准不等於上版授權"
TRIGGERS = ["svn commit", "上SVN", "上版", "game_server", "game_client", "Tools/", "README"]
KNOWLEDGE = [
    "[臨] 此專案下，任何屬於 SVN 版控資料夾（game_server/ game_client/ Tools/）內的異動，"
    "一律要等使用者驗證、確認過，且明確說「上SVN」才可以 commit",
]
ACTIONS = ["改到 SVN 資料夾內任何檔案後：驗證 → svn status → 停在「以上待你確認後說『上SVN』」"]

ATOM_BODY = """# {slug}

- Scope: {scope}
- Author: tester
- Confidence: [臨]
- Trigger: {trigger}
- Created-at: 2026-08-28

## 知識

{knowledge}

## 行動

- probe
"""


def _mkproj(tmp_path: Path) -> Path:
    """仿多 repo 工作區：頂層資料夾 + CLAUDE.md/Workspace_Map 成員表 + repo-paths atom。"""
    root = tmp_path / "Projects"
    for d in ("game_server", "game_client", "Tools", "game_jenkins", "_AIDocs", "_tools", "web", ".git"):
        (root / d).mkdir(parents=True)
    (root / "CLAUDE.md").write_text(
        "| 成員 | VCS |\n|---|---|\n| `game_server/` | SVN |\n| `Tools/` | SVN |\n"
        "| `game_jenkins/` | git（`http://ci.example/job/GAME/`） |\n", encoding="utf-8")
    (root / "_AIDocs" / "Workspace_Map.md").write_text(
        "| 成員 | VCS |\n|---|---|\n| **`game_client/`** | SVN |\n| `_tools/` | git |\n",
        encoding="utf-8")
    mem = root / ".claude" / "memory"
    (mem / "shared" / "ProjectWorkflow").mkdir(parents=True)
    (mem / "MEMORY.md").write_text("# idx\n", encoding="utf-8")
    (mem / "shared" / "ProjectWorkflow" / "repo-paths.md").write_text(
        ATOM_BODY.format(slug="repo-paths", scope="shared", trigger="路徑代號",
                         knowledge=f"- [臨] {{game_server}} = {root}\\game_server\n- [臨] {{Tools}} = {root}\\Tools"),
        encoding="utf-8")
    (mem / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": [
        {"name": "repo-paths", "path": "memory/shared/ProjectWorkflow/repo-paths.md",
         "triggers": ["路徑代號"], "scope": "shared"},
    ]}, ensure_ascii=False), encoding="utf-8")
    return root


@pytest.fixture
def proj(tmp_path):
    return _mkproj(tmp_path)


@pytest.fixture(autouse=True)
def fake_registry(tmp_path, monkeypatch):
    """隔離本機 registry：一個已登記專案 GameZ（別名 gmz、泛詞別名 office／辦公）、
    一個泛名容器 tmp、手列名單 Qux 與 雙人協作實驗。"""
    reg = {
        "projects": {
            "gz": {"root": str(tmp_path / "GameZ"), "aliases": ["gmz", "office", "辦公"]},
            "tmp": {"root": str(tmp_path / "tmp")},
            "org": {"root": str(tmp_path / "CompanyAtomsMem")},
        },
        "project_names": ["Qux", "雙人協作實驗"],
    }
    path = tmp_path / "project-registry.json"
    path.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(realm_gate, "REGISTRY_PATH", path)
    return tmp_path


# ─── 1. 專名機械化 ─────────────────────────────────────────────────────────────


def test_project_terms_are_derived_not_hardcoded(proj):
    t = project_terms(proj)
    assert {"game_server", "game_client", "Tools", "game_jenkins", "_tools", "{game_server}", "{Tools}"} <= set(t)
    assert t["game_server"] == "頂層資料夾" and t["{game_server}"] == "repo-paths 路徑代號"
    assert ".git" not in t and "web" not in t, "點目錄 / 純小寫短泛詞不得成專名"
    assert not any("://" in k for k in t), "URL 不得成專名"
    if (CLAUDE / "_AIDocs").exists():
        assert "_AIDocs" not in t, "與 ~/.claude 頂層同名者不具辨識力，須排除"


def test_scan_word_boundary_literal_and_abs_path(proj):
    hit = lambda fields: {h["term"] for h in scan_texts(proj, fields)}  # noqa: E731
    assert "Tools" in hit({"triggers": ["Tools/"]})
    assert "Tools" not in hit({"knowledge": ["Toolsmith 是通用詞"]}), "ASCII 專名須字邊界比對"
    assert "本專案" in hit({"knowledge": ["本專案的慣例"]})
    assert any(h["source"] == "專案絕對路徑" for h in
               scan_texts(proj, {"knowledge": [f"見 {proj}\\game_server\\Foo.cs"]}))
    assert not hit({"knowledge": ["git 已 push 的 commit 不得 amend，用 revert"]})


# ─── 2. py funnel ──────────────────────────────────────────────────────────────


def _global_write(proj, mode, **kw):
    return write_atom(
        title=TITLE, scope="global", confidence="[臨]", triggers=TRIGGERS,
        knowledge=KNOWLEDGE, actions=ACTIONS, mode=mode, source="mcp",
        project_cwd=str(proj), domain="版控/SVN", dry_run=True, **kw)


@pytest.mark.parametrize("mode", ["create", "append", "replace"])
def test_py_global_rejected_all_modes(proj, mode):
    r = _global_write(proj, mode)
    assert not r.ok and "realm gate" in (r.error or "") and 'scope="shared"' in r.error
    assert "game_server" in r.error and str(proj) in r.error


def test_py_skip_gate_does_not_bypass_realm_gate(proj):
    r = _global_write(proj, "create", skip_gate=True)
    assert not r.ok and "realm gate" in (r.error or "")


def test_py_core_cwd_ignores_project_internal_terms_and_generic_knowledge(proj):
    """根層 cwd 不知道「目前專案」的內部資料夾名，只認已登記專案名；本 payload 全是內部名 → 放行。"""
    assert check_global_write(str(CLAUDE), title=TITLE, triggers=TRIGGERS, knowledge=KNOWLEDGE) is None
    assert check_global_write(None, title=TITLE, triggers=TRIGGERS, knowledge=KNOWLEDGE) is None
    assert check_global_write(str(proj), title="git 已 push commit 勿改寫", triggers=["git push"],
                              knowledge=["[臨] 已 push 的 commit 不得 amend；用 revert"]) is None


def test_py_shared_feedback_lands_in_project_failures(proj, monkeypatch):
    monkeypatch.setattr(atom_io, "_category_gate_enabled", lambda: True)
    lr = locate_atom(TITLE, "shared", project_cwd=str(proj), domain="版控/SVN", mode="create")
    assert lr.ok and lr.path is None
    target = Path(lr.extra["target_dir"])
    assert target == proj / ".claude" / "memory" / "failures" / "版控" / "SVN"
    assert lr.extra["category"] == "failures/版控/SVN"

    r = write_atom(title=TITLE, scope="shared", confidence="[臨]", triggers=TRIGGERS,
                   knowledge=KNOWLEDGE, actions=ACTIONS, mode="create", source="mcp",
                   project_cwd=str(proj), domain="版控/SVN")
    assert r.ok, r.error
    assert r.path.parent == target and "- Scope: shared" in r.path.read_text(encoding="utf-8")
    entry = next(a for a in load_atom_index_json(proj / ".claude" / "memory")["atoms"]
                 if a["name"] == r.path.stem)
    assert entry["scope"] == "shared" and entry["path"].startswith("memory/failures/版控/SVN/")


# ─── 3. MCP js ─────────────────────────────────────────────────────────────────

_NODE_DRIVER = r"""
const tools = require(process.argv[1]);
const base = JSON.parse(process.argv[2]);
const cases = JSON.parse(process.argv[3]);
const real = process.stdout.write.bind(process.stdout);
let buf = "";
process.stdout.write = (s) => { buf += String(s); return true; };
(async () => {
  const out = [];
  for (const c of cases) {
    buf = "";
    await tools.toolAtomWrite(1, { ...base, ...c });
    const line = buf.trim().split("\n").pop();
    out.push(JSON.parse(line).result);
  }
  process.stdout.write = real;
  real(JSON.stringify(out));
  process.exit(0);
})().catch((e) => { process.stdout.write = real; real(JSON.stringify([{ fatal: String(e) }])); process.exit(1); });
"""


def _run_js(cases, cwd=None):
    base = {"title": TITLE, "confidence": "[臨]", "triggers": TRIGGERS,
            "knowledge": KNOWLEDGE, "actions": ACTIONS, "domain": "版控/SVN"}
    cp = subprocess.run(
        ["node", "-e", _NODE_DRIVER, str(ATOM_TOOLS_JS), json.dumps(base, ensure_ascii=False),
         json.dumps(cases, ensure_ascii=False)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd or CLAUDE), timeout=180,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert cp.returncode == 0, f"node exit {cp.returncode}\n{cp.stdout}\n{cp.stderr}"
    return json.loads(cp.stdout.strip().splitlines()[-1])


def _text(res):
    return "".join(c.get("text", "") for c in res.get("content", []))


def test_js_original_payload_rejected_create_replace_skipgate(proj):
    pc = str(proj)
    res = _run_js([
        {"mode": "create", "scope": "global", "project_cwd": pc},
        {"mode": "replace", "scope": "global", "project_cwd": pc},
        {"mode": "create", "scope": "global", "project_cwd": pc, "skip_gate": True},
        {"mode": "append", "scope": "global", "project_cwd": pc},
    ])
    assert len(res) == 4
    for r in res:
        assert r.get("isError") is True, r
        t = _text(r)
        assert "realm gate" in t and 'scope="shared"' in t and "game_server" in t, t


def test_js_falls_back_to_process_cwd_when_project_cwd_missing(proj):
    res = _run_js([{"mode": "create", "scope": "global", "skip_gate": True}], cwd=proj)
    assert res[0].get("isError") is True and f"gate cwd={proj}" in _text(res[0]), _text(res[0])


def test_js_shared_with_project_cwd_passes_and_lands_in_failures(proj):
    res = _run_js([{"mode": "create", "scope": "shared", "project_cwd": str(proj),
                    "skip_gate": True, "dry_run": True}])
    r = res[0]
    t = _text(r).replace("\\", "/")
    assert not r.get("isError"), t
    assert "DRY-RUN" in t and "/.claude/memory/failures/版控/SVN/" in t, t


# ─── 4. atom-move：Scope 檔頭 / 既有錯誤分離 / 目錄重生 ─────────────────────────


def test_atom_move_syncs_scope_header_and_separates_preexisting_errors(proj):
    mem = proj / ".claude" / "memory"
    (mem / "shared" / "x.md").write_text(
        ATOM_BODY.format(slug="x", scope="global", trigger="probe", knowledge="- [臨] seed"),
        encoding="utf-8")
    data = load_atom_index_json(mem)
    data["atoms"] += [
        {"name": "x", "path": "memory/shared/x.md", "triggers": ["probe"], "scope": "shared"},
        {"name": "longtrig", "path": "memory/shared/longtrig.md",
         "triggers": ["Account_LoginFailed_UnderMaintenance"], "scope": "shared"},  # 既有 >30 錯誤
    ]
    (mem / "_atom_index.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    cp = subprocess.run(
        [sys.executable, str(ATOM_MOVE), "move", "x", "--from", str(mem / "shared"),
         "--to", str(mem / "failures" / "版控" / "SVN")],
        capture_output=True, text=True, encoding="utf-8", cwd=str(CLAUDE), timeout=180,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert cp.returncode == 0, f"exit {cp.returncode} 應為 0（既有錯誤不得拉低本次結果）\n{cp.stdout}\n{cp.stderr}"
    rep = json.loads(cp.stdout)
    assert rep["mode"] == "APPLIED" and rep["scope"] == "shared"
    assert rep["scope_header_synced"] is True
    assert rep["validate_errors"] == []
    assert any("longtrig" in e for e in rep["index_preexisting_issues"])
    assert rep["catalog_sync"]["dst"]["ok"] is True, rep["catalog_sync"]
    moved = mem / "failures" / "版控" / "SVN" / "x.md"
    assert moved.exists() and "- Scope: shared" in moved.read_text(encoding="utf-8")
    assert "<!-- atom-catalog -->" in (mem / "MEMORY.md").read_text(encoding="utf-8")


# ─── 5. 已登記專案名（根層 cwd 也擋）─────────────────────────────────────────


def _core(knowledge, **kw):
    return check_global_write(str(CLAUDE), title=kw.pop("title", "通則"), knowledge=knowledge, **kw)


def test_registered_names_rejected_in_core_cwd(fake_registry):
    err = _core(["[臨] 實證：GameZ 全掃 2806 筆命中"])
    assert err and "realm gate" in err and "GameZ" in err and "根層" in err
    assert "某專案" in err, "拒寫訊息要帶改寫原則"
    assert _core(["[臨] 實例（GMZ 戰鬥結算）"]), "registry 別名不分大小寫：gmz 擋 GMZ"
    assert _core(["[臨] 實例"], triggers=["gamez"]), "trigger 也掃"
    assert _core(["[臨] 實例（Qux 戰役）"]), "手列名單照寫法比對"
    assert _core(["[臨] 雙人協作實驗裡發現"]), "手列 CJK 名用子字串比對"


def test_generic_and_product_words_pass_in_core_cwd(fake_registry):
    assert _core(["[臨] QUX 協定解析 ANSI 色碼"]) is None, "手列 Qux 照寫法，不擋全大寫的 QUX"
    assert _core(["[臨] office 文件轉檔、辦公室流程"]) is None, "泛詞別名不當專名"
    assert _core(["[臨] tmp 目錄與 Client／Server 分層"]) is None, "泛名容器資料夾不當專名"
    assert _core(["[臨] 公司層 repo CompanyAtomsMem 的同步"]) is None, "公司層 repo 名不是專案"
    assert _core(["[臨] GameZone 這個詞不是專案名"]) is None, "字邊界比對"


def test_registered_name_as_prefix_is_caught(fake_registry):
    assert _core(["[臨] 熱修層 GameZ_Hotfix 的 shader"]), "專案名接底線當前綴也算命中"
    assert anonymize_projects("gmz_hotfix 與 GameZ_Client") == "某專案_hotfix 與 某專案_Client"


def test_registered_project_paths_rejected_in_core_cwd(fake_registry):
    tmp = fake_registry
    assert _core([f"[臨] 見 {tmp / 'GameZ' / 'Client' / 'A.cs'}"])
    assert _core([f"[臨] 暫存在 {tmp / 'tmp' / 'x' / 'b.txt'}"]), "容器資料夾底下的路徑也是專案路徑"
    assert _core(["[臨] 見 C:/Elsewhere/A.cs"]) is None


def test_project_cwd_also_catches_registered_names(proj, fake_registry):
    err = check_global_write(str(proj), title="通則", knowledge=["[臨] 實證：GameZ 全掃"])
    assert err and "GameZ" in err and 'scope="shared"' in err


def test_personal_cross_project_is_gated(fake_registry):
    r = write_atom(title="個人偏好測試", scope="personal", user="tester", cross_project=True,
                   confidence="[臨]", triggers=["偏好"], knowledge=["[臨] 在 GameZ 時偏好先問"],
                   actions=["先問"], mode="create", source="mcp", project_cwd=str(CLAUDE), dry_run=True)
    assert not r.ok and "realm gate" in (r.error or "")
    r = write_atom(title="個人偏好測試", scope="personal", user="tester", cross_project=True,
                   confidence="[臨]", triggers=["偏好"], knowledge=["[臨] 偏好先問再動手"],
                   actions=["先問"], mode="create", source="mcp", project_cwd=str(CLAUDE), dry_run=True)
    assert r.ok, r.error


def test_anonymize_projects_replaces_names_and_paths(fake_registry):
    tmp = fake_registry
    src = f"/continue {tmp / 'GameZ' / '.claude' / 'next.md'} 然後看 gmz 與 Qux 和 QUX 與 GameZone"
    out = anonymize_projects(src)
    assert "<專案路徑>" in out and "GameZ" + "\\" not in out
    assert "某專案 與 某專案 和 QUX 與 GameZone" in out
