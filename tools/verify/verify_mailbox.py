"""verify_mailbox.py — skills/mailbox/scripts/mail.py 端到端驗證（全在 pytest 暫存目錄，不碰真實共用資料夾）。

每案建一個假專案 <tmp>/proj/.claude/skills/mailbox/config.json，mailbox_root 指向 <tmp>/share/MailBox，
cwd 進假專案跑 mail.py 子行程；身分用環境變數 MAILBOX_USER 切 alice／bob。
cases：
  1. 設定分層：專案層有 config → 印「設定層：專案層」、信箱路徑取自專案層；.claude 下沒有 mailbox config → 「skill 自帶」
  2. 帳號：沒記錄 → exit 4 [需要帳號]；config --account 寫進專案層的 .local/mailbox.json
  3. 不認得的收件者 → exit 5 [不認得收件者]，信沒寄出
  4. 完整流程：check → roster --add → send（單人、多人含 project、附件）→ list → read（領取）→ unlock
     → send --re 回信 → delete 預覽不刪、--yes 才刪 → overview 重產 Overview.md
  5. 兩個行程同時 read 同一封 project 信：只有一個領到，_archive 裡只有一份
  6. 信箱根被刪 → 一般指令提示 init；init 重建骨架
  7. 沒帳號時 delete --yes／roster --add 在動手前就停（exit 4）：不刪到一半、不先寫名單
  8. 名單檔被手改成不合規的帳號 → 寄信停下（exit 1），不在信箱外建資料夾
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent
MAIL = CLAUDE_DIR / "skills" / "mailbox" / "scripts" / "mail.py"


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    settings = project / ".claude" / "skills" / "mailbox"
    settings.mkdir(parents=True)
    root = tmp_path / "share" / "MailBox"
    root.mkdir(parents=True)
    (settings / "config.json").write_text(
        json.dumps({"mailbox_root": str(root), "log_keep_days": 30}), encoding="utf-8")
    return project


def mailbox_root(project: Path) -> Path:
    return project.parent / "share" / "MailBox"


def clean_env(user: str | None, env_root: str | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("MAILBOX_ROOT", "MAILBOX_USER")}
    env["PYTHONIOENCODING"] = "utf-8"
    if user:
        env["MAILBOX_USER"] = user
    if env_root:
        env["MAILBOX_ROOT"] = env_root
    return env


def run(cwd: Path, user: str | None, *args: str, env_root: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(MAIL), *args], cwd=str(cwd), env=clean_env(user, env_root),
                          capture_output=True, text=True, encoding="utf-8")


def write_body(folder: Path, name: str, text: str) -> str:
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def mail_files(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.glob("*.md")) if folder.is_dir() else []


# ---------------------------------------------------------------------------
# 1. 設定分層
# ---------------------------------------------------------------------------

def test_config_uses_project_layer_from_nested_cwd(proj: Path):
    nested = proj / "src" / "deep"
    nested.mkdir(parents=True)
    res = run(nested, "alice", "config")
    assert res.returncode == 0, res.stderr
    assert "設定層：專案層" in res.stdout
    assert str(proj / ".claude" / "skills" / "mailbox") in res.stdout
    assert f"信箱：{mailbox_root(proj)}" in res.stdout


def test_config_falls_back_to_skill_dir_without_project_config(tmp_path: Path):
    other = tmp_path / "other"
    (other / ".claude").mkdir(parents=True)
    res = run(other, "alice", "config", env_root=str(tmp_path / "anywhere"))
    assert res.returncode == 0, res.stderr
    assert "設定層：skill 自帶" in res.stdout
    assert "環境變數 MAILBOX_ROOT" in res.stdout


# ---------------------------------------------------------------------------
# 2. 帳號
# ---------------------------------------------------------------------------

def test_missing_account_exits_4_then_config_account_writes_project_local(proj: Path):
    res = run(proj, None, "list")
    assert res.returncode == 4 and "[需要帳號]" in res.stderr
    res = run(proj, None, "config", "--account", "alice")
    assert res.returncode == 0, res.stderr
    account_file = proj / ".claude" / "skills" / "mailbox" / ".local" / "mailbox.json"
    assert json.loads(account_file.read_text(encoding="utf-8")) == {"account": "alice"}
    assert run(proj, None, "list").returncode == 0


# ---------------------------------------------------------------------------
# 3. 不認得的收件者
# ---------------------------------------------------------------------------

def test_unknown_recipient_exits_5_and_sends_nothing(proj: Path, tmp_path: Path):
    assert run(proj, "alice", "check").returncode == 0
    body = write_body(tmp_path, "b.md", "# 哈囉\n內文\n")
    res = run(proj, "alice", "send", "--to", "Bob", "--body-file", body)
    assert res.returncode == 5 and "[不認得收件者]" in res.stderr
    assert not list(mailbox_root(proj).rglob("*_M0001_*"))


# ---------------------------------------------------------------------------
# 4. 完整流程
# ---------------------------------------------------------------------------

def test_full_flow(proj: Path, tmp_path: Path):
    root = mailbox_root(proj)
    assert "讀寫測試：建檔／讀回／刪除都成功" in run(proj, "alice", "check").stdout
    assert run(proj, "bob", "check").returncode == 0
    res = run(proj, "alice", "roster", "--add", "bob", "Bob")
    assert res.returncode == 0 and "[已記錄] bob（Bob）" in res.stdout

    # 單人
    body1 = write_body(tmp_path, "b1.md", "# 第一封\n請看一下\n")
    res = run(proj, "alice", "send", "--to", "Bob", "--body-file", body1)
    assert res.returncode == 0 and "[已寄出] M0001" in res.stdout

    # 多人＋project＋附件
    attach = write_body(tmp_path, "error.log", "boom\n")
    body2 = write_body(tmp_path, "b2.md", "# 第二封\n大家看\n")
    res = run(proj, "alice", "send", "--to", "Bob", "專案", "me", "--body-file", body2, "--attach", attach)
    assert res.returncode == 0 and "[已寄出] M0002" in res.stdout
    for box in ("bob", "project", "alice"):
        copy = next(name for name in mail_files(root / box) if "_M0002_" in name)
        assert (root / box / copy[:-3] / "error.log").is_file()

    # list：bob 兩封未讀
    assert "共 2 封未讀" in run(proj, "bob", "list").stdout

    # read：領取搬進 _archive，狀態紀錄寫上讀者
    res = run(proj, "bob", "read", "M1")
    assert res.returncode == 0 and "[已領取] M0001" in res.stdout
    archived = next(n for n in mail_files(root / "bob" / "_archive") if "_M0001_" in n)
    assert "已讀（bob）" in (root / "bob" / "_archive" / archived).read_text(encoding="utf-8")

    # 多人信各自已讀：bob 讀了不影響 alice 那份
    assert run(proj, "bob", "read", "M2").returncode == 0
    assert any("_M0002_" in n for n in mail_files(root / "alice"))

    # unlock 退回未讀
    res = run(proj, "bob", "unlock", "M1")
    assert res.returncode == 0 and "[已解鎖] M0001" in res.stdout
    assert any("_M0001_" in n for n in mail_files(root / "bob"))

    # 回信：收件者預設原寄件人、標題 Re:
    body3 = write_body(tmp_path, "b3.md", "收到\n")
    res = run(proj, "bob", "send", "--re", "M1", "--body-file", body3)
    assert res.returncode == 0 and "[已寄出] M0003" in res.stdout and "Re: 第一封" in res.stdout
    reply = next(n for n in mail_files(root / "alice") if "_M0003_" in n)
    assert "- 回覆：M0001（第一封）" in (root / "alice" / reply).read_text(encoding="utf-8")

    # delete：預覽不刪，--yes 才刪（整封收回含附件）
    assert "預覽（還沒刪" in run(proj, "alice", "delete", "M2").stdout
    assert any("_M0002_" in n for n in mail_files(root / "project"))
    res = run(proj, "alice", "delete", "M2", "--yes")
    assert res.returncode == 0 and res.stdout.count("[已刪除] M0002") == 3
    assert not list(root.rglob("*_M0002_*"))

    # overview 重產總覽，動作紀錄有寫
    res = run(proj, "alice", "overview")
    assert res.returncode == 0 and "[alice] 未讀 1" in res.stdout
    assert "M0003" in (root / "Overview.md").read_text(encoding="utf-8")
    assert list((root / "_log").glob("*.txt"))


# ---------------------------------------------------------------------------
# 5. 同時讀同一封：只有一人領到
# ---------------------------------------------------------------------------

def test_concurrent_read_only_one_claims(proj: Path, tmp_path: Path):
    root = mailbox_root(proj)
    for user in ("alice", "bob", "carol"):
        assert run(proj, user, "check").returncode == 0
    for round_no in range(1, 6):
        body = write_body(tmp_path, f"r{round_no}.md", f"# 搶單 {round_no}\n誰先拿\n")
        assert run(proj, "carol", "send", "--to", "project", "--body-file", body).returncode == 0
        procs = [subprocess.Popen([sys.executable, str(MAIL), "read", str(round_no)], cwd=str(proj),
                                  env=clean_env(user), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding="utf-8")
                 for user in ("alice", "bob")]
        outs = [proc.communicate(timeout=60) for proc in procs]
        assert all(proc.returncode == 0 for proc in procs), outs
        assert sum(out.count("[已領取]") for out, _ in outs) == 1, outs
        archived = [n for n in mail_files(root / "project" / "_archive") if f"_M{round_no:04d}_" in n]
        assert len(archived) == 1


# ---------------------------------------------------------------------------
# 6. 信箱根被刪 → init 重建
# ---------------------------------------------------------------------------

def test_deleted_root_hints_init_and_init_rebuilds(proj: Path):
    root = mailbox_root(proj)
    root.rmdir()
    res = run(proj, "alice", "list")
    assert res.returncode == 1 and "mail.py init" in res.stderr
    res = run(proj, "alice", "init")
    assert res.returncode == 0, res.stderr
    assert (root / "project").is_dir() and (root / "alice").is_dir()
    assert "alice" in json.loads((root / "_roster.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 7. 沒帳號：會改東西的指令在動手前就停
# ---------------------------------------------------------------------------

def test_delete_without_account_stops_before_deleting_any_copy(proj: Path, tmp_path: Path):
    root = mailbox_root(proj)
    assert run(proj, "alice", "check").returncode == 0
    body = write_body(tmp_path, "b.md", "# 多人信\n內文\n")
    assert run(proj, "alice", "send", "--to", "me", "專案", "--body-file", body).returncode == 0
    assert len(list(root.rglob("*_M0001_*.md"))) == 2
    res = run(proj, None, "delete", "M1", "--yes")
    assert res.returncode == 4 and "[需要帳號]" in res.stderr
    assert len(list(root.rglob("*_M0001_*.md"))) == 2


def test_roster_add_without_account_writes_nothing(proj: Path):
    roster_file = mailbox_root(proj) / "_roster.json"
    assert run(proj, "alice", "check").returncode == 0
    assert not roster_file.exists()
    res = run(proj, None, "roster", "--add", "bob", "Bob")
    assert res.returncode == 4 and "[需要帳號]" in res.stderr
    assert not roster_file.exists()


# ---------------------------------------------------------------------------
# 8. 名單檔被手改壞：帳號不合規就停，不變成信箱外的路徑
# ---------------------------------------------------------------------------

def test_roster_entry_with_bad_account_is_rejected(proj: Path, tmp_path: Path):
    root = mailbox_root(proj)
    assert run(proj, "alice", "check").returncode == 0
    (root / "_roster.json").write_text(json.dumps({"../outside": ["Bob"]}), encoding="utf-8")
    body = write_body(tmp_path, "b.md", "# 哈囉\n內文\n")
    res = run(proj, "alice", "send", "--to", "Bob", "--body-file", body)
    assert res.returncode == 1 and "../outside" in res.stderr
    assert not (root.parent / "outside").exists()
