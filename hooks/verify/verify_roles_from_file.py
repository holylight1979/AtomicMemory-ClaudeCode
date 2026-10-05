"""verify_roles_from_file.py — 身份／職能／裁決資格（hooks/wg_roles.py）封閉。

- 身份 fallback 是 "unknown"，且 unknown 不進任何 personal
- 職能三層：role.md（缺／單／多角色）→ AD 群組（stub whoami csv，不真跑）→ []
- AD 對映結果直通 build_candidate_pool：programmer 進 roles/programmer/、無匹配不進
- Project-Code 只取該專案群組；whoami 失敗 → [] 且 stderr 一行
- 裁決：deciders 空→True、非空不含→False、含→True；config 壞→True 且 stderr；無參呼叫相容
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_ROOT = HOOKS_DIR.parent
for p in (HOOKS_DIR, HOOKS_DIR / "handlers", CLAUDE_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import wg_core  # noqa: E402
import wg_roles  # noqa: E402
import wg_atoms  # noqa: E402

USER = "holylight"
AD_MAP = {"核心程式": "programmer", "伺服器程式": "programmer", "程式": "programmer",
          "美術": "art", "企劃": "planner", "QA": "qa", "PM": "pm"}


def _csv(*groups: str) -> str:
    rows = ['"群組名稱","類型","SID","屬性"', '"Everyone","已知的群組","S-1-1-0","強制性群組"']
    rows += [f'"{g}","群組","S-1-5-21-{i}","強制性群組"' for i, g in enumerate(groups)]
    return "\r\n".join(rows) + "\r\n"


def _atom(path: Path, name: str, trigger: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {name}\n\n- Trigger: {trigger}\n\n## 知識\n\n- [臨] x\n", encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    """全域 memory + V4 專案（roles/programmer、roles/art、personal/holylight）；config 可控；AD 預設不可用。"""
    gmem = tmp_path / "claude" / "memory"
    gmem.mkdir(parents=True)
    (gmem / "MEMORY.md").write_text("# g\n", encoding="utf-8")
    (gmem / "_atom_index.json").write_text(json.dumps({"atoms": []}), encoding="utf-8")

    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    pmem = proj / ".claude" / "memory"
    pmem.mkdir(parents=True)
    (pmem / "MEMORY.md").write_text("# p\n", encoding="utf-8")
    _atom(pmem / "shared" / "s1.md", "s1", "zzzs")
    _atom(pmem / "roles" / "programmer" / "role-prog.md", "role-prog", "zzzrole")
    _atom(pmem / "roles" / "art" / "role-art.md", "role-art", "zzzrole")
    _atom(pmem / "personal" / USER / "mine.md", "mine", "zzzmine")

    cfg = {"review": {"deciders": []}, "roles": {"ad_group_map": dict(AD_MAP)}}
    monkeypatch.setattr(wg_core, "load_config", lambda: json.loads(json.dumps(cfg)))
    monkeypatch.setattr(wg_core, "MEMORY_DIR", gmem)
    monkeypatch.setattr(wg_atoms, "MEMORY_DIR", gmem)
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path / "wf")
    monkeypatch.setattr(wg_roles, "_ad_groups_cache", None)
    monkeypatch.setattr(wg_roles, "ad_available", lambda: False)
    return {"gmem": gmem, "proj": proj, "pmem": pmem, "cfg": cfg}


def _stub_ad(monkeypatch, text=None, fail=False):
    monkeypatch.setattr(wg_roles, "_ad_groups_cache", None)
    monkeypatch.setattr(wg_roles, "ad_available", lambda: True)

    def _run():
        if fail:
            raise RuntimeError("whoami exit 1")
        return [row.split('","')[0].strip('"') for row in text.splitlines()[1:] if row]
    monkeypatch.setattr(wg_roles, "_whoami_groups", _run)


def _pool_names(proj: Path, user: str, roles) -> set:
    pool = wg_atoms.build_candidate_pool(str(proj), user, roles)
    return {n for n, _p, _t in pool["project"]}


# ─── 身份 ────────────────────────────────────────────────────────────────────

def test_default_user_is_unknown_and_unknown_sees_no_personal(world, monkeypatch):
    assert wg_roles._DEFAULT_USER == "unknown"
    monkeypatch.delenv("CLAUDE_USER", raising=False)
    import getpass
    monkeypatch.setattr(getpass, "getuser", lambda: (_ for _ in ()).throw(OSError("no user")))
    assert wg_roles.get_current_user() == "unknown"
    names = _pool_names(world["proj"], "unknown", [])
    assert "mine" not in names and "s1" in names


# ─── 第 1 層 role.md ──────────────────────────────────────────────────────────

def test_role_md_missing_and_ad_unavailable_gives_empty(world):
    info = wg_roles.load_user_role(str(world["proj"]), USER)
    assert info["roles"] == [] and info["source"] == "none"
    assert info["management"] is True  # 鍵保留給呼叫端


def test_role_md_single_role(world):
    rd = world["pmem"] / "personal" / USER / "role.md"
    rd.write_text(f"- User: {USER}\n- Role: art\n", encoding="utf-8")
    info = wg_roles.load_user_role(str(world["proj"]), USER)
    assert info["roles"] == ["art"] and info["source"] == "role.md"
    names = _pool_names(world["proj"], USER, info["roles"])
    assert "role-art" in names and "role-prog" not in names


def test_role_md_multi_role_and_global_fallback(world):
    gl = world["gmem"] / "personal" / USER / "role.md"
    gl.parent.mkdir(parents=True)
    gl.write_text("- Role: programmer, art\n", encoding="utf-8")
    info = wg_roles.load_user_role(str(world["proj"]), USER)
    assert info["roles"] == ["programmer", "art"] and info["source"] == "role.md"
    assert _pool_names(world["proj"], USER, info["roles"]) >= {"role-prog", "role-art", "mine", "s1"}


def test_role_md_empty_file_falls_through_to_ad(world, monkeypatch):
    (world["pmem"] / "personal" / USER / "role.md").write_text("", encoding="utf-8")
    _stub_ad(monkeypatch, _csv(r"UJ\PJA146_TSLG_02_核心程式"))
    info = wg_roles.load_user_role(str(world["proj"]), USER)
    assert info["roles"] == ["programmer"] and info["source"] == "ad"


# ─── 第 2 層 AD 群組 ──────────────────────────────────────────────────────────

def test_ad_core_programmer_group_maps_and_enters_pool(world, monkeypatch):
    _stub_ad(monkeypatch, _csv("BUILTIN\\Users", r"UJ\PJA146_TSLG_02_核心程式", r"UJ\AkamaiEAA_SGI"))
    info = wg_roles.load_user_role(str(world["proj"]), USER)
    assert info["roles"] == ["programmer"] and info["source"] == "ad"
    names = _pool_names(world["proj"], USER, info["roles"])
    assert "role-prog" in names and "role-art" not in names


def test_ad_art_group_maps_to_art(world, monkeypatch):
    _stub_ad(monkeypatch, _csv(r"UJ\X_01_美術"))
    assert wg_roles.load_user_role(str(world["proj"]), USER)["roles"] == ["art"]


def test_ad_no_matching_group_gives_empty_and_no_role_atoms(world, monkeypatch):
    _stub_ad(monkeypatch, _csv("BUILTIN\\Users", r"UJ\B105事務部_各專案相關R", r"UJ\AkamaiEAA_SGI"))
    info = wg_roles.load_user_role(str(world["proj"]), USER)
    assert info["roles"] == [] and info["source"] == "none"
    names = _pool_names(world["proj"], USER, info["roles"])
    assert "role-prog" not in names and "role-art" not in names and "s1" in names


def test_ad_whoami_failure_gives_empty_and_stderr(world, monkeypatch, capsys):
    _stub_ad(monkeypatch, fail=True)
    info = wg_roles.load_user_role(str(world["proj"]), USER)
    assert info["roles"] == []
    err = capsys.readouterr().err
    assert "whoami" in err and err.count("[wg_roles]") == 1
    # 失敗已快取：再查不重跑、不重複告警
    wg_roles.load_user_role(str(world["proj"]), USER)
    assert "[wg_roles]" not in capsys.readouterr().err


def test_ad_project_code_filters_to_declared_project(world, monkeypatch):
    groups = _csv(r"UJ\PJA146_TSLG_02_核心程式", r"UJ\PJA999_OTHER_05_美術")
    _stub_ad(monkeypatch, groups)
    assert wg_roles.load_user_role(str(world["proj"]), USER)["roles"] == ["programmer", "art"]
    (world["pmem"] / "MEMORY.md").write_text("> Project-Code: PJA999\n# p\n", encoding="utf-8")
    monkeypatch.setattr(wg_roles, "_ad_groups_cache", None)
    assert wg_roles.load_user_role(str(world["proj"]), USER)["roles"] == ["art"]


def test_ad_query_cached_once_per_process(world, monkeypatch):
    calls = []
    monkeypatch.setattr(wg_roles, "_ad_groups_cache", None)
    monkeypatch.setattr(wg_roles, "ad_available", lambda: True)
    monkeypatch.setattr(wg_roles, "_whoami_groups", lambda: calls.append(1) or [r"UJ\A_01_程式"])
    wg_roles.load_user_role(str(world["proj"]), USER)
    wg_roles.load_user_role("", USER)
    assert len(calls) == 1


def test_map_groups_longest_key_first_and_dedupe():
    roles = wg_roles.map_groups_to_roles(
        [r"UJ\P_01_伺服器程式", r"UJ\P_02_核心程式", "nodomain_程式", r"UJ\P_03_QA"], AD_MAP)
    assert roles == ["programmer", "qa"]


# ─── 裁決資格 review.deciders ─────────────────────────────────────────────────

def test_deciders_empty_everyone_can_decide(world):
    assert wg_roles.is_management(str(world["proj"]), "anyone") is True
    assert wg_roles.load_management_roster(str(world["proj"])) == []


def test_deciders_nonempty_gates_by_user(world, monkeypatch):
    world["cfg"]["review"]["deciders"] = ["alice"]
    assert wg_roles.is_management(str(world["proj"]), "bob") is False
    assert wg_roles.is_management(str(world["proj"]), "alice") is True
    monkeypatch.setenv("CLAUDE_USER", "alice")
    assert wg_roles.is_management() is True  # 無參呼叫（heal-review）相容
    monkeypatch.setenv("CLAUDE_USER", "bob")
    assert wg_roles.is_management() is False


def test_config_broken_fails_open_with_stderr(world, monkeypatch, capsys):
    monkeypatch.setattr(wg_core, "load_config", lambda: {"_config_parse_failed": True})
    assert wg_roles.is_management(str(world["proj"]), "bob") is True
    assert "[wg_roles]" in capsys.readouterr().err
    monkeypatch.setattr(wg_core, "load_config", lambda: (_ for _ in ()).throw(OSError("boom")))
    assert wg_roles.is_management() is True
    assert "[wg_roles]" in capsys.readouterr().err


def test_load_user_role_when_pool_builder_consumes_it(world, monkeypatch):
    """SessionStart 路徑：load_user_role 回的 roles 直接餵 build_candidate_pool，不經任何預設補齊。"""
    _stub_ad(monkeypatch, _csv(r"UJ\PJA110_SGI_02_核心程式"))
    src = (HOOKS_DIR / "handlers" / "session_start.py").read_text(encoding="utf-8")
    assert 'or ["programmer"]' not in src
    assert "if v4_mgmt:" not in src
