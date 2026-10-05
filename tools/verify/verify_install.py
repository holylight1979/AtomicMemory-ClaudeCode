"""verify_install.py — tools/install.py 的安裝、升級、驗證流程測試。

做法：每個情境一個假家目錄（HOME 與 USERPROFILE 同時指過去），以本 repo 的 `git clone --bare`
當假上游、再 clone 出來源，然後以子程序跑來源裡的 install.py。真實的 ~/.claude 只被唯讀使用。
假上游在 HEAD 之上多疊一筆 commit，內容是工作目錄現況的 install.py 與 user-init.sh（受測檔）。
共用的 `adopted`（已安裝的假家）與假上游不被任何測試改動：會改動的測試用 `fork` 取得自己的一份，
或在測試結束前還原，所以測試順序不影響結果。

怎麼跑：python -m pytest tools/verify/verify_install.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
UNDER_TEST = ("tools/install.py", "hooks/user-init.sh")
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.longpaths=true"]

_spec = importlib.util.spec_from_file_location("install_under_test", REPO / "tools" / "install.py")
install = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install)

USER_SETTINGS = {
    "permissions": {"allow": ["Bash(ls *)"], "defaultMode": "default"},
    "model": "user-model",
    "hooks": {
        "Stop": [{"hooks": [
            {"type": "command", "command": "python C:/mine/notify.py"},
            {"type": "command", "command": "python \"$HOME/.claude/hooks/old-system-hook.py\""},
        ]}],
    },
}
# 純函式測試用的「repo 追蹤的 hooks/、tools/ 檔案」
TRACKED = frozenset({"hooks/a.py", "hooks/workflow-guardian.py", "tools/statusline.py"})
USER_CONFIG = {
    "dashboard_port": 4000,
    "vcs_sync": {"enabled": False},
    "vector_search": {"auto_start_service": False, "search_top_k": 9},
}


# ─── 小工具 ─────────────────────────────────────────────────────────────────

def fake_env(home: Path) -> dict:
    return {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "PYTHONIOENCODING": "utf-8"}


def git(*args: str, cwd: Path, home: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run([*GIT, *args], cwd=cwd, env=fake_env(home), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check, creationflags=NO_WINDOW)


def run_install(home: Path, script: Path, *args: str) -> subprocess.CompletedProcess:
    """在假家環境跑 install.py；先確認它認定的目標真的在假家裡。"""
    assert REPO.resolve() not in (home / ".claude").resolve().parents and (home / ".claude").resolve() != REPO.resolve()
    r = subprocess.run([sys.executable, str(script), *args], env=fake_env(home), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    assert f"目標目錄：{home / '.claude'}" in r.stdout, r.stdout + r.stderr
    return r


def make_home(base: Path, name: str, files: dict) -> Path:
    """建假家；files＝{相對 ~/.claude 的路徑: 文字或 dict（寫成 JSON）}。"""
    home = base / name
    (home / ".claude").mkdir(parents=True)
    for rel, content in files.items():
        path = home / ".claude" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2)
        path.write_text(text, encoding="utf-8", newline="\n")
    return home


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def only_backup(claude: Path, prefix: str) -> Path:
    dirs = sorted((claude / "backups").glob(prefix + "-*"))
    assert len(dirs) == 1, dirs
    return dirs[0]


def marks(claude: Path, home: Path) -> dict:
    out = git("ls-files", "-v", "--", "settings.json", "workflow/config.json", cwd=claude, home=home).stdout
    return {line[2:]: line[0] for line in out.splitlines()}


def tracked_changes(claude: Path, home: Path) -> list:
    out = git("status", "--porcelain", cwd=claude, home=home).stdout
    return [line for line in out.splitlines() if not line.startswith("??")]


def commands(settings: dict, event: str) -> list:
    return [h.get("command", "") for group in settings["hooks"].get(event, []) for h in group["hooks"]]


def overlay_bytes(claude: Path) -> dict:
    return {rel: (claude / rel).read_bytes() for rel in ("settings.json", "workflow/config.json")}


def state_of(claude: Path) -> dict:
    return load(claude / ".git" / "atom-install-state.json")


# ─── fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def base(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("i")


@pytest.fixture(scope="session")
def upstream(base) -> dict:
    """假上游（bare）＋來源 clone（只取出受測檔）；來源 HEAD 含工作目錄現況的受測檔。"""
    bare, source = base / "up.git", base / "src"
    git("clone", "--bare", str(REPO), str(bare), cwd=base, home=base)
    git("clone", "--no-checkout", str(bare), str(source), cwd=base, home=base)
    git("sparse-checkout", "set", "--no-cone", *("/" + rel for rel in UNDER_TEST), cwd=source, home=base)
    git("checkout", cwd=source, home=base)
    for rel in UNDER_TEST:
        (source / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, source / rel)
    git("add", "--", *UNDER_TEST, cwd=source, home=base)
    git("commit", "--allow-empty", "-m", "files under test", cwd=source, home=base)
    git("push", "origin", "HEAD", cwd=source, home=base)
    return {"bare": bare, "source": source, "script": source / "tools" / "install.py"}


@pytest.fixture
def fake_target(tmp_path, monkeypatch) -> Path:
    """純函式測試：把 install 模組認定的家目錄與 ~/.claude 換成暫存目錄。回假的 ~/.claude。"""
    target = tmp_path / "home" / ".claude"
    (target / "hooks").mkdir(parents=True)
    monkeypatch.setattr(install, "HOME", tmp_path / "home")
    monkeypatch.setattr(install, "TARGET", target)
    return target


@pytest.fixture(scope="session")
def adopted(base, upstream) -> dict:
    """典型新同事：用過 Claude Code、有自己的設定與個人檔，接管安裝一次。測試不得改動它。"""
    home = make_home(base, "h1", {
        "CLAUDE.md": "my own claude md\n",
        "USER.md": "# my custom USER\n",
        "settings.json": USER_SETTINGS,
        "workflow/config.json": USER_CONFIG,
        "projects/p1/session.jsonl": "{}\n",
        ".credentials.json": "{\"secret\": 1}\n",
        "my-notes.txt": "notes\n",
    })
    result = run_install(home, upstream["script"], "--apply")
    return {"home": home, "claude": home / ".claude", "result": result}


def fork(base: Path, adopted: dict, upstream: dict, name: str) -> dict:
    """已安裝的假家與假上游各複製一份，origin 指向複製出來的上游；測試可任意改動。"""
    home, bare = base / name, base / (name + ".git")
    shutil.copytree(adopted["home"], home, symlinks=True)
    git("clone", "--bare", str(upstream["bare"]), str(bare), cwd=base, home=base)
    claude = home / ".claude"
    git("remote", "set-url", "origin", str(bare), cwd=claude, home=home)
    return {"home": home, "claude": claude, "bare": bare, "script": claude / "tools" / "install.py"}


def push_change(base: Path, upstream: dict, name: str, edit) -> None:
    """在假上游多推一筆 commit；edit(clone 目錄) 負責改檔。只取出頂層與 workflow/。"""
    clone = base / name
    git("clone", "--sparse", str(upstream["bare"]), str(clone), cwd=base, home=base)
    git("sparse-checkout", "add", "workflow", cwd=clone, home=base)
    edit(clone)
    git("commit", "-am", name, cwd=clone, home=base)
    git("push", "origin", "HEAD", cwd=clone, home=base)


# ─── 合併規則（純函式） ─────────────────────────────────────────────────────

def test_merge_settings_keeps_user_keys_and_foreign_hooks(fake_target):
    system = {"permissions": {"defaultMode": "bypassPermissions"}, "model": "owner-model",
              "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "py \"$HOME/.claude/hooks/a.py\""}]}]},
              "statusLine": {"type": "command", "command": "py \"$HOME/.claude/tools/statusline.py\""}}
    merged, dropped = install.merge_settings(USER_SETTINGS, system, TRACKED)
    assert merged["permissions"] == USER_SETTINGS["permissions"] and merged["model"] == "user-model"
    assert commands(merged, "Stop") == ["py \"$HOME/.claude/hooks/a.py\"", "python C:/mine/notify.py"]
    assert merged["statusLine"] == system["statusLine"]
    assert dropped == ["python \"$HOME/.claude/hooks/old-system-hook.py\""]
    own = {"statusLine": {"type": "command", "command": "my-status"}}
    assert install.merge_settings(own, system, TRACKED)[0]["statusLine"] == own["statusLine"]
    assert set(install.merge_settings(None, system, TRACKED)[0]) == {"hooks", "statusLine"}
    # 重複合併不會讓使用者的 hook 變兩份；被系統版接手的條目不算被丟掉
    assert install.merge_settings(merged, system, TRACKED) == (merged, [])


def test_hook_ownership(fake_target):
    """只有「指向家目錄 .claude、且是追蹤檔或檔案已不存在」的指令才讓位給系統版。"""
    (fake_target / "hooks" / "my-own-guard.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    real_home = str(fake_target.parent)
    keep = [
        '"$CLAUDE_PROJECT_DIR"/.claude/hooks/lint.sh',
        "bash ~/.claude/hooks/my-own-guard.sh",
        "/work/other/.claude/hooks/custom.py",
        "bash /opt/x.sh",
    ]
    drop_tracked = [
        'py "$HOME/.claude/hooks/a.py"',
        "py ${HOME}/.claude/hooks/a.py",
        "py ~/.claude/hooks/a.py",
        r"py %USERPROFILE%\.claude\hooks\a.py",
        "py $USERPROFILE/.claude/hooks/a.py",
        "py -c \"import runpy,pathlib;runpy.run_path(str(pathlib.Path.home()/'.claude/hooks/a.py'))\"",
        f"py {real_home.upper()}\\.claude\\hooks\\a.py",
        f"py {Path(real_home).as_posix()}/.claude/hooks/a.py",
    ]
    drop_stale = ['python "$HOME/.claude/hooks/gone.py"']
    assert [c for c in keep if install.replaced_by_system({"command": c}, TRACKED)] == []
    assert [c for c in drop_tracked + drop_stale if not install.replaced_by_system({"command": c}, TRACKED)] == []

    user = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": c} for c in keep + drop_tracked[:1] + drop_stale]}]},
        "statusLine": {"type": "command", "command": "py ~/.claude/tools/old-status.py"}}
    system = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": drop_tracked[0]}]}]},
              "statusLine": {"type": "command", "command": 'py "$HOME/.claude/tools/statusline.py"'}}
    merged, dropped = install.merge_settings(user, system, TRACKED)
    assert commands(merged, "PreToolUse") == keep
    assert merged["hooks"]["PreToolUse"][0]["matcher"] == "Bash"
    assert merged["statusLine"] == system["statusLine"]
    assert dropped == drop_stale + ["py ~/.claude/tools/old-status.py"]


def test_config_three_way_merge():
    base_cfg = {"port": 1, "nested": {"a": 1, "b": 2}, "list": [1]}
    mine = {"port": 9, "nested": {"a": 1, "b": 5, "mine": True}, "list": [1]}
    new = {"port": 2, "nested": {"a": 7, "b": 3}, "list": [1, 2], "added": "x"}
    changed = install.changed_keys(mine, base_cfg)
    assert changed == {"port": 9, "nested": {"b": 5, "mine": True}}
    assert install.drop_type_conflicts(changed, base_cfg, new) == (changed, [])
    assert install.deep_merge(new, changed) == {
        "port": 9, "nested": {"a": 7, "b": 5, "mine": True}, "list": [1, 2], "added": "x"}


def test_config_three_way_merge_type_conflict():
    """使用者只改了物件的子鍵、新版該鍵已不是物件 → 以新版為準，回報鍵路徑；其餘改動照常保留。"""
    base_cfg = {"a": {"x": 1, "y": 2}, "deep": {"d": {"p": 1}, "q": 1}, "gone": {"k": 1}, "port": 1}
    mine = {"a": {"x": 1, "y": 5}, "deep": {"d": {"p": 2}, "q": 9}, "gone": {"k": 2}, "port": 9, "own": {"z": 1}}
    new = {"a": "off", "deep": {"d": [1], "q": 1}, "port": 2, "own": 3}
    changed = install.changed_keys(mine, base_cfg)
    kept, conflicts = install.drop_type_conflicts(changed, base_cfg, new)
    assert conflicts == ["a", "deep.d"]
    assert install.deep_merge(new, kept) == {
        "a": "off", "deep": {"d": [1], "q": 9}, "gone": {"k": 2}, "port": 9, "own": {"z": 1}}


def test_backup_copy_is_atomic(fake_target, tmp_path):
    backup = tmp_path / "backup"
    (fake_target / "plain.txt").write_text("plain\n", encoding="utf-8")
    (backup / "plain.txt.install-tmp").parent.mkdir(parents=True)
    (backup / "plain.txt.install-tmp").write_text("half", encoding="utf-8")  # 上次複製到一半留下的
    install.to_backup("plain.txt", backup, move=False)
    assert (backup / "plain.txt").read_text(encoding="utf-8") == "plain\n"
    assert not (backup / "plain.txt.install-tmp").exists()
    (fake_target / "plain.txt").write_text("changed later\n", encoding="utf-8")
    install.to_backup("plain.txt", backup, move=False)  # 已有備份不覆寫
    assert (backup / "plain.txt").read_text(encoding="utf-8") == "plain\n"


def test_backup_keeps_symlink_content(fake_target, tmp_path):
    backup = tmp_path / "backup"
    (fake_target / "real").mkdir()
    (fake_target / "real" / "data.txt").write_text("linked content\n", encoding="utf-8")
    try:
        os.symlink(os.path.join("real", "data.txt"), fake_target / "link.txt")
        os.symlink("real", fake_target / "linkdir", target_is_directory=True)
    except OSError as e:
        pytest.skip(f"這個環境不能建立 symlink：{e}")
    install.to_backup("link.txt", backup, move=True)
    assert not (backup / "link.txt").is_symlink()
    assert (backup / "link.txt").read_text(encoding="utf-8") == "linked content\n"
    assert not os.path.lexists(fake_target / "link.txt")
    assert (fake_target / "real" / "data.txt").is_file()
    install.to_backup("linkdir", backup, move=True)
    assert (backup / "linkdir").is_symlink() and not os.path.lexists(fake_target / "linkdir")


# ─── 接管 ───────────────────────────────────────────────────────────────────

def test_adopt_keeps_personal_files_and_installs_system(adopted):
    claude, result = adopted["claude"], adopted["result"]
    assert result.returncode == 0, result.stdout + result.stderr
    assert "接管" in result.stdout and "請重開 Claude Code" in result.stdout
    assert (claude / "projects/p1/session.jsonl").read_text(encoding="utf-8") == "{}\n"
    assert (claude / ".credentials.json").read_text(encoding="utf-8") == "{\"secret\": 1}\n"
    assert (claude / "my-notes.txt").read_text(encoding="utf-8") == "notes\n"
    for rel in ("hooks/workflow-guardian.py", "memory/MEMORY.md", "tools/install.py", "rules/core.md"):
        assert (claude / rel).is_file(), rel
    assert "@IDENTITY.md" in (claude / "CLAUDE.md").read_text(encoding="utf-8")
    backup = only_backup(claude, "install")
    assert (backup / "CLAUDE.md").read_text(encoding="utf-8") == "my own claude md\n"
    assert load(backup / "settings.json") == USER_SETTINGS
    assert "CLAUDE.md 的內容已不再載入" in result.stdout
    assert load(claude / ".git" / "atom-install-state.json")["phase"] == "done"
    upstream_ref = git("rev-parse", "--abbrev-ref", "@{u}", cwd=claude, home=adopted["home"]).stdout.strip()
    assert upstream_ref.startswith("origin/")


def test_adopt_merges_settings(adopted):
    claude = adopted["claude"]
    settings = load(claude / "settings.json")
    system = json.loads(git("show", "HEAD:settings.json", cwd=claude, home=adopted["home"]).stdout)
    assert settings["permissions"] == USER_SETTINGS["permissions"]
    assert settings["model"] == "user-model"
    assert set(system["hooks"]) <= set(settings["hooks"])
    stop = commands(settings, "Stop")
    assert "python C:/mine/notify.py" in stop
    assert not any("old-system-hook" in c for c in stop)
    assert any("workflow-guardian.py" in c for c in stop)
    assert "statusline.py" in settings["statusLine"]["command"]


def test_adopt_merges_config(adopted):
    config = load(adopted["claude"] / "workflow" / "config.json")
    assert config["dashboard_port"] == 4000
    assert config["vector_search"]["search_top_k"] == 9
    assert config["vector_search"]["embedding_model"]  # 巢狀新鍵補系統預設
    assert "stop_gate_max_blocks" in config and config["vcs_sync"]["root_pathspecs"]


def test_adopt_marks_overlays_and_tree_is_clean(adopted):
    claude, home = adopted["claude"], adopted["home"]
    assert marks(claude, home) == {"settings.json": "S", "workflow/config.json": "S"}
    assert tracked_changes(claude, home) == []


def test_adopt_keeps_custom_user_md(adopted):
    claude = adopted["claude"]
    assert (claude / "USER.md").read_text(encoding="utf-8") == "# my custom USER\n"
    assert [p.read_text(encoding="utf-8") for p in claude.glob("USER-*.md")] == ["# my custom USER\n"]
    assert (only_backup(claude, "install") / "USER.md").read_text(encoding="utf-8") == "# my custom USER\n"
    assert (claude / "IDENTITY.md").is_file()


def test_rerun_after_adopt_is_in_place(adopted, upstream):
    claude = adopted["claude"]
    before = {rel: (claude / rel).read_bytes() for rel in ("settings.json", "workflow/config.json")}
    result = run_install(adopted["home"], upstream["script"], "--apply")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "就地" in result.stdout
    assert before == {rel: (claude / rel).read_bytes() for rel in before}
    only_backup(claude, "install")


def test_type_conflicts_go_to_backup_and_no_settings_gets_no_permissions(base, upstream):
    home = make_home(base, "h2", {"hooks": "i am a file\n", "version.json/keep.txt": "keep\n"})
    claude = home / ".claude"
    result = run_install(home, upstream["script"], "--apply")
    assert result.returncode == 0, result.stdout + result.stderr
    backup = only_backup(claude, "install")
    assert (backup / "hooks").read_text(encoding="utf-8") == "i am a file\n"
    assert (backup / "version.json" / "keep.txt").read_text(encoding="utf-8") == "keep\n"
    assert (claude / "hooks" / "workflow-guardian.py").is_file()
    assert load(claude / "version.json")["guardian"]
    settings = load(claude / "settings.json")
    assert {"hooks"} <= set(settings) <= {"hooks", "statusLine"}
    assert "git -C ~/.claude show HEAD:settings.json" in result.stdout
    system_config = json.loads(git("show", "HEAD:workflow/config.json", cwd=claude, home=home).stdout)
    assert load(claude / "workflow" / "config.json") == system_config
    assert marks(claude, home) == {"settings.json": "S", "workflow/config.json": "S"}
    assert tracked_changes(claude, home) == []


CRASH_DRIVER = """
import importlib.util, sys
spec = importlib.util.spec_from_file_location("install", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
real_git, when = mod.git, sys.argv[2]
def crashing_git(*args, **kwargs):
    if args[:1] != ("checkout",):
        return real_git(*args, **kwargs)
    if when == "after":
        real_git(*args, **kwargs)
    raise RuntimeError("simulated crash")
mod.git = crashing_git
sys.argv = [sys.argv[1], "--apply"]
sys.exit(mod.main())
"""


def crash_apply(home: Path, script: Path, when: str) -> None:
    crashed = subprocess.run([sys.executable, "-c", CRASH_DRIVER, str(script), when],
                             env=fake_env(home), capture_output=True, text=True, encoding="utf-8",
                             errors="replace", creationflags=NO_WINDOW)
    assert crashed.returncode != 0 and "simulated crash" in crashed.stderr, crashed.stderr
    assert load(home / ".claude" / ".git" / "atom-install-state.json")["phase"] != "done"


def test_interrupted_adopt_resumes_without_touching_backup(base, upstream):
    """checkout 之前當掉、重跑又在 checkout 之後當掉（狀態檔沒前進）→ 再重跑完成，備份仍是使用者原檔。"""
    home = make_home(base, "h3", {"CLAUDE.md": "precious\n", "settings.json": USER_SETTINGS})
    claude = home / ".claude"
    crash_apply(home, upstream["script"], "before")
    backup = only_backup(claude, "install")
    assert (backup / "CLAUDE.md").read_text(encoding="utf-8") == "precious\n"
    assert (claude / "CLAUDE.md").read_text(encoding="utf-8") == "precious\n"
    crash_apply(home, upstream["script"], "after")
    assert "@IDENTITY.md" in (claude / "CLAUDE.md").read_text(encoding="utf-8")

    result = run_install(home, upstream["script"], "--apply")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "接管" in result.stdout
    assert only_backup(claude, "install") == backup
    assert (backup / "CLAUDE.md").read_text(encoding="utf-8") == "precious\n"
    assert load(backup / "settings.json") == USER_SETTINGS
    assert load(claude / "settings.json")["permissions"] == USER_SETTINGS["permissions"]
    assert load(claude / ".git" / "atom-install-state.json")["phase"] == "done"
    assert tracked_changes(claude, home) == []


# ─── 其他模式 ───────────────────────────────────────────────────────────────

def test_in_place_mode_leaves_overlays_alone(base, upstream):
    home = base / "h4"
    home.mkdir()
    claude = home / ".claude"
    git("clone", str(upstream["bare"]), str(claude), cwd=base, home=home)
    config_before = (claude / "workflow" / "config.json").read_bytes()
    permissions = load(claude / "settings.json")["permissions"]
    result = run_install(home, claude / "tools" / "install.py", "--apply")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "就地" in result.stdout
    assert (claude / "workflow" / "config.json").read_bytes() == config_before
    assert load(claude / "settings.json")["permissions"] == permissions
    assert marks(claude, home) == {"settings.json": "H", "workflow/config.json": "H"}
    assert not (claude / ".git" / "atom-install-state.json").exists()
    assert not (claude / "backups").exists()


def test_foreign_repo_exits_3_untouched(base, upstream):
    home = make_home(base, "h5", {"README.md": "someone else's repo\n", "settings.json": USER_SETTINGS})
    claude = home / ".claude"
    git("init", "-b", "main", cwd=claude, home=home)
    git("remote", "add", "origin", "https://example.invalid/other.git", cwd=claude, home=home)
    git("add", "-A", cwd=claude, home=home)
    git("commit", "-m", "theirs", cwd=claude, home=home)

    def snapshot() -> dict:
        return {p.relative_to(claude).as_posix(): p.read_bytes() for p in claude.rglob("*") if p.is_file()}

    before = snapshot()
    result = run_install(home, upstream["script"], "--apply")
    assert result.returncode == 3, result.stdout + result.stderr
    assert snapshot() == before


def test_missing_target_is_created_and_adopted(base, upstream):
    home = base / "h6"
    home.mkdir()
    claude = home / ".claude"
    assert run_install(home, upstream["script"], "--verify").returncode == 1
    assert not claude.exists()
    result = run_install(home, upstream["script"], "--apply")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "接管" in result.stdout
    settings = load(claude / "settings.json")
    assert "permissions" not in settings and {"hooks"} <= set(settings) <= {"hooks", "statusLine"}
    assert marks(claude, home) == {"settings.json": "S", "workflow/config.json": "S"}
    assert tracked_changes(claude, home) == []
    assert state_of(claude)["phase"] == "done"
    assert not (claude / "backups").exists()


def test_broken_user_settings_aborts_before_any_change(base, upstream):
    broken = '{\n  // my comment\n  "model": "mine",\n}\n'
    home = make_home(base, "h8", {"settings.json": broken, "CLAUDE.md": "x\n"})
    claude = home / ".claude"
    result = run_install(home, upstream["script"], "--apply")
    assert result.returncode == 1, result.stdout + result.stderr
    assert str(claude / "settings.json") in result.stderr
    assert sorted(p.name for p in claude.iterdir()) == ["CLAUDE.md", "settings.json"]
    assert (claude / "settings.json").read_bytes() == broken.encode("utf-8")


def test_check_exit_code(base, upstream):
    """結果隨機器環境而異：只驗 exit code 與每一項都有判定。"""
    home = base / "h7"
    home.mkdir()
    result = run_install(home, upstream["script"], "--check")
    assert result.returncode in (0, 2), result.stdout + result.stderr
    for name, *_ in install.PROBES:
        assert f"[OK] {name}：" in result.stdout or f"[缺] {name}：" in result.stdout, name
    assert ("可以安裝" in result.stdout) == (result.returncode == 0)
    assert not (home / ".claude").exists()


# ─── 升級 ───────────────────────────────────────────────────────────────────

def test_upgrade_remerges_overlays_then_restores_on_failed_pull(base, upstream, adopted):
    mine = fork(base, adopted, upstream, "u1")
    home, claude, upstream = mine["home"], mine["claude"], mine
    new_hook = "\"$LOCALAPPDATA/Python/bin/pythonw.exe\" \"$HOME/.claude/hooks/brand-new-hook.py\""

    def add_hook_and_defaults(clone: Path) -> None:
        settings = load(clone / "settings.json")
        settings["hooks"]["Notification"] = [{"hooks": [{"type": "command", "command": new_hook}]}]
        config = load(clone / "workflow" / "config.json")
        config["stop_gate_max_blocks"] = 77
        config["dashboard_port"] = 5555
        config["brand_new"] = {"x": 1}
        install.write_json(clone / "settings.json", settings)
        install.write_json(clone / "workflow" / "config.json", config)

    push_change(base, upstream, "p1", add_hook_and_defaults)
    script = claude / "tools" / "install.py"
    result = run_install(home, script, "--upgrade")
    assert result.returncode == 0, result.stdout + result.stderr
    settings, config = load(claude / "settings.json"), load(claude / "workflow" / "config.json")
    assert commands(settings, "Notification") == [new_hook]
    assert settings["permissions"] == USER_SETTINGS["permissions"]
    assert commands(settings, "Stop").count("python C:/mine/notify.py") == 1
    assert config["dashboard_port"] == 4000          # 使用者改過的鍵留著
    assert config["stop_gate_max_blocks"] == 77      # 沒改過的鍵跟新預設
    assert config["brand_new"] == {"x": 1}
    assert config["vcs_sync"]["enabled"] is False
    assert marks(claude, home) == {"settings.json": "S", "workflow/config.json": "S"}
    assert tracked_changes(claude, home) == []
    assert (only_backup(claude, "upgrade") / "settings.json").is_file()
    state = state_of(claude)
    assert state["phase"] == "done" and "saved_dir" not in state
    assert state["overlay_base"] == git("rev-parse", "HEAD", cwd=claude, home=home).stdout.strip()

    # pull 失敗：本機與上游各改 README.md 同一行 → rebase 衝突 → 中止並還原
    def edit_readme(clone: Path) -> None:
        (clone / "README.md").write_text("upstream side\n", encoding="utf-8", newline="\n")

    push_change(base, upstream, "p2", edit_readme)
    (claude / "README.md").write_text("local side\n", encoding="utf-8", newline="\n")
    git("config", "user.name", "t", cwd=claude, home=home)
    git("config", "user.email", "t@t", cwd=claude, home=home)
    git("commit", "-am", "local", cwd=claude, home=home)
    head = git("rev-parse", "HEAD", cwd=claude, home=home).stdout
    before = {rel: (claude / rel).read_bytes() for rel in ("settings.json", "workflow/config.json")}
    failed = run_install(home, script, "--upgrade")
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "還原" in failed.stdout
    assert before == {rel: (claude / rel).read_bytes() for rel in before}
    assert marks(claude, home) == {"settings.json": "S", "workflow/config.json": "S"}
    assert git("rev-parse", "HEAD", cwd=claude, home=home).stdout == head
    assert not (claude / ".git" / "rebase-merge").exists() and not (claude / ".git" / "rebase-apply").exists()
    assert tracked_changes(claude, home) == []
    assert state_of(claude)["phase"] == "done"


def test_upgrade_refuses_dirty_tree_and_broken_overlay(adopted):
    """有未提交的修改、或覆蓋檔不是合法 JSON → 零改動中止。"""
    home, claude = adopted["home"], adopted["claude"]
    script = claude / "tools" / "install.py"
    before, state_before = overlay_bytes(claude), state_of(claude)
    memory_md = claude / "memory" / "MEMORY.md"
    original = memory_md.read_bytes()
    memory_md.write_bytes(original + b"\nlocal edit\n")
    try:
        dirty = run_install(home, script, "--upgrade")
    finally:
        memory_md.write_bytes(original)
    assert dirty.returncode == 1, dirty.stdout + dirty.stderr
    assert "memory/MEMORY.md" in dirty.stderr and "關掉其他對話" in dirty.stderr
    (claude / "settings.json").write_text('{ "model": "x", }\n', encoding="utf-8")
    try:
        broken = run_install(home, script, "--upgrade")
    finally:
        (claude / "settings.json").write_bytes(before["settings.json"])
    assert broken.returncode == 1, broken.stdout + broken.stderr
    assert str(claude / "settings.json") in broken.stderr
    assert overlay_bytes(claude) == before and state_of(claude) == state_before
    assert marks(claude, home) == {"settings.json": "S", "workflow/config.json": "S"}
    assert tracked_changes(claude, home) == []
    assert not list((claude / "backups").glob("upgrade-*"))


KILL_DRIVER = """
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("install", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
real_git = mod.git
def killing_git(*args, **kwargs):
    if args[:1] == ("pull",):
        os._exit(9)
    return real_git(*args, **kwargs)
mod.git = killing_git
sys.argv = [sys.argv[1], "--upgrade"]
sys.exit(mod.main())
"""


def test_upgrade_killed_midway_recovers_on_next_upgrade(base, upstream, adopted):
    """升級在 pull 那一步被硬殺（收尾程式碼沒機會跑）→ 下一次 --upgrade 先還原再重來，使用者的值都在。"""
    mine = fork(base, adopted, upstream, "u2")
    home, claude, script = mine["home"], mine["claude"], mine["script"]
    before = overlay_bytes(claude)
    killed = subprocess.run([sys.executable, "-c", KILL_DRIVER, str(script)], env=fake_env(home),
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            creationflags=NO_WINDOW)
    assert killed.returncode == 9, killed.stdout + killed.stderr
    state = state_of(claude)
    assert state["phase"] == "upgrading" and state["marked"] == ["settings.json", "workflow/config.json"]
    assert marks(claude, home) == {"settings.json": "H", "workflow/config.json": "H"}
    assert "permissions" in load(claude / "settings.json") and overlay_bytes(claude) != before  # 此刻是系統整檔

    blocked = run_install(home, script, "--apply")
    assert blocked.returncode == 1 and "--upgrade" in blocked.stdout
    assert state_of(claude)["phase"] == "upgrading"

    result = run_install(home, script, "--upgrade")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "上次的升級沒有跑完" in result.stdout
    settings, config = load(claude / "settings.json"), load(claude / "workflow" / "config.json")
    assert settings["permissions"] == USER_SETTINGS["permissions"] and settings["model"] == "user-model"
    assert commands(settings, "Stop").count("python C:/mine/notify.py") == 1
    assert config["dashboard_port"] == 4000 and config["vcs_sync"]["enabled"] is False
    assert marks(claude, home) == {"settings.json": "S", "workflow/config.json": "S"}
    assert tracked_changes(claude, home) == []
    state = state_of(claude)
    assert state["phase"] == "done" and "saved_dir" not in state and "marked" not in state


# ─── 驗證 ───────────────────────────────────────────────────────────────────

def test_verify_exit_code_on_installed_home(adopted):
    home, claude = adopted["home"], adopted["claude"]
    script = claude / "tools" / "install.py"
    installed_at = (claude / ".git" / "atom-install-state.json").stat().st_mtime
    stale, opened = claude / "workflow" / "state-before-install.json", claude / "workflow" / "state-opened.json"
    user_md = (claude / "USER.md").read_bytes()
    try:
        stale.write_text("{}", encoding="utf-8")  # 安裝前留下的紀錄不算數
        os.utime(stale, (installed_at - 60, installed_at - 60))
        never_opened = run_install(home, script, "--verify")
        assert never_opened.returncode == 1 and "FAIL     hook 啟動紀錄" in never_opened.stdout
        opened.write_text("{}", encoding="utf-8")  # 模擬安裝後重開過 Claude Code
        result = run_install(home, script, "--verify")
        assert result.returncode == 0 and "：0 項 FAIL" in result.stdout, result.stdout + result.stderr
        assert "PASS     hook 啟動紀錄" in result.stdout and "有 1 個 session" in result.stdout
        assert "記憶三層現況" in result.stdout and "公司層" in result.stdout
        assert "DEGRADED MCP 註冊" in result.stdout  # 假家沒有 ~/.claude.json
        (claude / "USER.md").unlink()
        broken = run_install(home, script, "--verify")
        assert broken.returncode == 1 and "FAIL     個人啟動檔" in broken.stdout
    finally:
        (claude / "USER.md").write_bytes(user_md)
        stale.unlink(missing_ok=True)
        opened.unlink(missing_ok=True)
