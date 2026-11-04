"""verify_secret_cards.py — 個人隱私敏感資訊進 memory/personal/<user>/secret/ 的把關（lib/sensitive_gate 與各接點）。

做什麼：
- 判定：字眼命中要宣告（secret 或 not_sensitive 理由）；真實 token／私鑰 not_sensitive 也不放行；一般用語不誤判。
- 落點：secret 不管 cwd 在哪都落根層 personal/<user>/secret/；append 找得到既有的 secret 卡；登記不進共用索引。
- 寫檔入口：真實值在 secret/ 以外寫不進去，在 secret/ 裡可以。
- 版控：真的 .gitignore——放行名單上的個人卡進版控，secret/、別人的卡、本機登記、退役卡不進。
- 出口：secret 卡不送向量、卡名不進橋接檔；觸發詞取得到、只給本人；規則在必載檔。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_secret_cards.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "lib", ROOT / "hooks"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lib.atom_index_json import load_atom_index_json, upsert_atom  # noqa: E402
from lib.atom_locations import scope_from_index_path  # noqa: E402
from lib.sensitive_gate import check_write, is_secret_path, secret_value_found, sensitive_words  # noqa: E402

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
FAKE_TOKEN = "glpat-" + "a" * 20   # 拼起來才不會被掃描工具當真的
CARD = "# {name}\n\n- Scope: personal:u\n- Confidence: [臨]\n- Trigger: {name}\n\n## 知識\n\n- [臨] x\n\n## 行動\n\n- y\n"


@pytest.fixture
def mem(tmp_path, monkeypatch):
    monkeypatch.setenv("WG_CLAUDE_DIR", str(tmp_path))
    d = tmp_path / "memory"
    d.mkdir()
    return d


def _env(mem_dir: Path) -> dict:
    return {**os.environ, "WG_CLAUDE_DIR": str(mem_dir.parent), "PYTHONIOENCODING": "utf-8"}


def _write_card(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(CARD.format(name=path.stem), encoding="utf-8")
    return path


@pytest.mark.parametrize("text", ["git 存的是帳號密碼", "放在 credentials 檔", "私鑰在 ~/.ssh", "API key 要換", "身分證字號"])
def test_sensitive_word_needs_declaration(text):
    err = check_write({"knowledge": [text]})
    assert err and "secret=true" in err and "not_sensitive" in err


@pytest.mark.parametrize("text", ["task-notification 是背景通知", "這場用了多少 token", "risk-free-long-slug-with-many-words-here",
                                  "比對 passwordless 流程"])
def test_everyday_words_are_not_flagged(text):
    assert check_write({"knowledge": [text]}) is None and not secret_value_found(text)


@pytest.mark.parametrize("text,flagged", [
    (r"信箱在 \\server01\TSLG\MailBox 底下", True),
    ("信箱在 //server01/TSLG/MailBox 底下", True),
    ("主機是 192.168.199.130 這台", True),
    (r"named pipe 是 \\.\pipe\foo", False),
    ("參考 https://github.com/a/b/issues/1", False),
    (r"放在 C:\Users\someone\x.md", False),
    ("版本 1.10.2.3 的行為", False),
])
def test_internal_address_needs_declaration_but_ordinary_paths_do_not(text, flagged):
    assert bool(sensitive_words(text)) is flagged, text


def test_auto_filled_quote_skips_sensitive_user_words():
    """自動回填的使用者原話會進卡片、進版控，繞過寫入閘：命中就不填，一般原話照填。"""
    from lib.provenance import usable_quote
    assert usable_quote(r"同事回報，信箱在 \\server01\TSLG\MailBox 底下") == ""
    assert usable_quote("公司帳號密碼存在哪裡") == ""
    assert usable_quote(f"token 是 {FAKE_TOKEN} 這個") == ""
    assert usable_quote("這個做法我覺得不錯，照這樣做") == "這個做法我覺得不錯，照這樣做"


def test_declared_reason_passes_but_blank_reason_does_not():
    fields = {"knowledge": ["通用做法：憑證要存獨立檔"]}
    assert check_write(fields, "只是通用做法，沒有個人資訊") is None
    assert check_write(fields, "  。。 ") is not None


def test_real_value_cannot_be_declared_away_and_message_does_not_echo_it():
    err = check_write({"knowledge": [f"金鑰是 {FAKE_TOKEN}"]}, "我覺得沒關係")
    assert err and "真實值" in err and FAKE_TOKEN not in err


def test_gate_reads_title_and_triggers_too():
    assert check_write({"title": "公司密碼放哪"}) and check_write({"triggers": ["信用卡"]})
    assert sensitive_words("密碼、密碼、憑證") == ["密碼", "憑證"]


def _locate(mem_dir: Path, **kw):
    """在子行程裡跑：lib.atom_locations 的資料根在 import 時就定了。"""
    payload = {"action": "locate", "title": "key-card", "scope": "personal", "user": "u", "secret": True, **kw}
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "lib.atom_io_cli"], input=json.dumps(payload), cwd=str(ROOT),
                       env=_env(mem_dir), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                       creationflags=NO_WINDOW)
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_secret_lands_in_root_layer_from_any_cwd(mem, tmp_path):
    """就算 cwd 在專案裡也落根層：專案 repo 的 ignore 規則不一定擋得到。"""
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / ".claude" / "memory").mkdir(parents=True)
    for kw in ({}, {"project_cwd": str(proj)}):
        out = _locate(mem, mode="create", **kw)
        assert out["ok"], out
        target = Path(out["extra"]["target_dir"])
        assert target.resolve() == (mem / "personal" / "u" / "secret").resolve()
        assert out["extra"]["create_rel_path"] == "memory/personal/u/secret/key-card.md"


def test_append_finds_existing_secret_card(mem):
    card = _write_card(mem / "personal" / "u" / "secret" / "key-card.md")
    out = _locate(mem, mode="append")
    assert out["ok"] and Path(out["path"]).resolve() == card.resolve(), out


def test_existing_card_can_be_moved_into_secret_with_tool(mem):
    """寫錯地方的卡要搬得進 secret/：atom-move 不被範疇閘擋，登記跟著改、遙測檔跟著搬、共用索引不會多一列。"""
    owner = mem / "personal" / "u"
    _write_card(owner / "oops-card.md")
    (owner / "oops-card.access.json").write_text("{}", encoding="utf-8")
    upsert_atom(mem, "pub", "memory/x/pub.md", ["公開"], "global")
    upsert_atom(mem, "oops-card", "memory/personal/u/oops-card.md", ["oops-card"], "personal:u")
    r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / "atom-move.py"), "move", "oops-card",
                        "--from", str(owner), "--to", str(owner / "secret")], env=_env(mem), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60, creationflags=NO_WINDOW)
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    assert (owner / "secret" / "oops-card.md").is_file() and (owner / "secret" / "oops-card.access.json").is_file()
    assert not (owner / "oops-card.md").exists()
    row = next(a for a in load_atom_index_json(mem)["atoms"] if a["name"] == "oops-card")
    assert row["path"] == "memory/personal/u/secret/oops-card.md" and row["scope"] == "personal:u"
    assert "oops-card" not in (mem / "_atom_index.json").read_text(encoding="utf-8")


def test_secret_card_is_exempt_from_project_name_gate_but_plain_personal_is_not(mem, monkeypatch):
    """secret 不共享，內容提到專案名不要緊；一般個人卡會進版控，照舊過範疇閘。"""
    import lib.atom_io as aio
    import lib.realm_gate as rg
    monkeypatch.setattr(rg, "check_global_write", lambda *a, **k: "擋：提到專案名")
    monkeypatch.setattr(aio, "GLOBAL_MEMORY_DIR", mem)
    kw = dict(scope="personal", user="u", confidence="[臨]", triggers=["機密詞"], knowledge=["- [臨] x"], source="mcp",
              cross_project=True, skip_gate=True, dry_run=True)
    assert aio.write_atom(title="plain-pref", **kw).error == "擋：提到專案名"
    assert aio.write_atom(title="key-card", secret=True, **kw).error != "擋：提到專案名"


def test_secret_row_goes_to_local_index_and_scope_is_owner_only(mem):
    path = "memory/personal/u/secret/key-card.md"
    upsert_atom(mem, "pub", "memory/x/pub.md", ["公開"], "global")
    upsert_atom(mem, "key-card", path, ["機密詞"], "personal:u")
    assert "key-card" not in (mem / "_atom_index.json").read_text(encoding="utf-8")
    assert "key-card" in [a["name"] for a in load_atom_index_json(mem)["atoms"]]   # 觸發詞取得到
    assert scope_from_index_path(path, "global") == "personal:u"                   # 只給本人


def _write_raw(mem_dir: Path, rel: str, content: str) -> dict:
    code = ("import json, sys; from pathlib import Path; from lib.atom_io import write_raw;"
            "r = write_raw(Path(sys.argv[1]), sys.argv[2], source='mcp'); print(json.dumps({'ok': r.ok, 'error': r.error}))")
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", code, str(mem_dir / rel), content], cwd=str(ROOT), env=_env(mem_dir),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=NO_WINDOW)
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_write_funnel_refuses_real_value_outside_secret(mem):
    out = _write_raw(mem, "x/leaky.md", f"# 卡\n\n- {FAKE_TOKEN}\n")
    assert out["ok"] is False and "真實值" in out["error"] and not (mem / "x" / "leaky.md").exists()
    assert FAKE_TOKEN not in out["error"]
    out = _write_raw(mem, "personal/u/plain.md", f"# 卡\n\n- {FAKE_TOKEN}\n")   # 一般個人卡也會進版控
    assert out["ok"] is False
    assert _write_raw(mem, "personal/u/secret/key.md", f"# 卡\n\n- {FAKE_TOKEN}\n")["ok"] is True


@pytest.mark.parametrize("rel,ignored", [
    ("memory/personal/holylight/some-pref.md", False),
    ("memory/personal/holylight/secret/key.md", True),
    ("memory/personal/holylight/_distant/2026_10/old.md", True),
    ("memory/personal/holylight/some-pref.access.json", True),
    ("memory/personal/someone-else/their-pref.md", True),
    ("memory/personal/someone-else/secret/key.md", True),
    ("memory/personal/auto/u/candidate.md", True),
    ("memory/personal/_personal_index.json", True),
])
def test_real_gitignore_allows_only_listed_people_and_never_secret(rel, ignored):
    r = subprocess.run(["git", "check-ignore", "-q", "--no-index", rel], cwd=str(ROOT), capture_output=True, timeout=30,
                       creationflags=NO_WINDOW)
    assert (r.returncode == 0) is ignored, rel


READER_PROBE = r"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("probe_tool_mod", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
sys.modules["probe_tool_mod"] = mod
spec.loader.exec_module(mod)
print("PROBE_JSON " + json.dumps(eval(sys.argv[2], {"mod": mod, "Path": __import__("pathlib").Path, "root": sys.argv[3]}), ensure_ascii=False))
"""


def _probe(mem_dir: Path, tool: str, expr: str):
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", READER_PROBE, str(ROOT / "tools" / tool), expr, str(mem_dir)],
                       env=_env(mem_dir), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
                       creationflags=NO_WINDOW)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("PROBE_JSON ")), "")
    assert line, r.stdout + r.stderr[-1500:]
    return json.loads(line[len("PROBE_JSON "):])


def test_secret_card_is_not_sent_to_vector_index(mem):
    owner = mem / "personal" / "u"
    _write_card(owner / "plain-pref.md")
    _write_card(owner / "secret" / "key-card.md")
    got = _probe(mem, "memory-vector-service/indexer.py",
                 "[Path(a[1]).stem for a in mod.discover_atoms([('personal:global:u', Path(root) / 'personal' / 'u', 'recursive')])]")
    assert "plain-pref" in got and "key-card" not in got


def test_rule_is_in_always_loaded_file_and_guarded():
    """規則要在每個人每場都載入的必載檔，且登記成硬契約，修剪時不會無聲消失。"""
    core = (ROOT / "rules" / "core.md").read_text(encoding="utf-8")
    assert "個人隱私敏感資訊放 secret" in core and "memory/personal/<user>/secret/" in core and "secret=true" in core
    contracts = json.loads((ROOT / "memory" / "_meta" / "always-load-contracts.json").read_text(encoding="utf-8"))["contracts"]
    guarded = [c for c in contracts if c["live"] == "rules/core.md" and "個人隱私敏感資訊放 secret" in c["must_contain"]]
    assert guarded


def test_secret_path_recognised_in_every_spelling():
    assert is_secret_path("memory/personal/u/secret/a.md") and is_secret_path(r"C:\x\.claude\memory\personal\u\secret\a.md")
    assert is_secret_path(Path("memory") / "personal" / "u" / "secret" / "sub" / "a.md")
    assert not is_secret_path("memory/personal/u/a.md") and not is_secret_path("memory/secret/a.md") and not is_secret_path(None)
