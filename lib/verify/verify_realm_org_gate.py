"""verify_realm_org_gate.py：公司層（org）寫入也過 realm 閘：帶專案名／專案路徑／「此專案」→ 擋；scrub 後過；shared 不受影響。

做什麼：lib/realm_gate.check_org_write、scrub_project_details；lib/atom_io_cli._realm_check 依 scope 分派
（org → check_org_write；shared → 放行；global → check_global_write）；CLI action=scrub 回 extra.text。
不碰 live：專案名靠 monkeypatch _load_registry；不讀真 registry。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_realm_org_gate.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude
if str(CLAUDE) not in sys.path:
    sys.path.insert(0, str(CLAUDE))

from lib import realm_gate as rg  # noqa: E402
from lib import atom_io_cli as cli  # noqa: E402

PROJECT_TEXT = "FooProj 的登入要先起假 Gate（StubGate 聽 21110）"
PATH_TEXT = r"正本在 D:\Work\FooProj\src\Net.cs"
LITERAL_TEXT = "此專案的表要 regen 後才生效"
GENERIC_TEXT = "hook 的 systemMessage 只給使用者看，模型讀不到，要回饋模型用 additionalContext"


@pytest.fixture(autouse=True)
def _registry(monkeypatch):
    monkeypatch.setattr(rg, "_load_registry", lambda: {
        "projects": {"a": {"root": r"D:\Work\FooProj", "aliases": ["fooproj"]}},
        "project_names": ["BarGame"],
    })
    monkeypatch.setattr(rg, "_org_root_names", lambda: {"CompanyAtomsMem"})


# ─── check_org_write ──────────────────────────────────────────────────────


@pytest.mark.parametrize("text", [PROJECT_TEXT, PATH_TEXT, LITERAL_TEXT, "BarGame 的合服八步驟"])
def test_org_write_with_project_details_blocked(text):
    errs = rg.check_org_write(text)
    assert errs, text
    assert "scope=org rejected" in errs[0]
    assert any("命中：" in e for e in errs)
    assert any("scrub" in e for e in errs)


def test_org_write_generic_passes():
    assert rg.check_org_write(GENERIC_TEXT) == []
    assert rg.check_org_write({"title": "hook-systemmessage", "triggers": ["systemMessage"],
                               "knowledge": [GENERIC_TEXT], "actions": ["用 additionalContext"]}) == []


def test_scrub_then_passes():
    for text in (PROJECT_TEXT, PATH_TEXT, LITERAL_TEXT):
        scrubbed = rg.scrub_project_details(text)
        assert "FooProj" not in scrubbed and "此專案" not in scrubbed
        assert rg.check_org_write(scrubbed) == [], scrubbed
    assert rg.scrub_project_details(PATH_TEXT) == "正本在 <專案路徑>"
    assert rg.scrub_project_details(LITERAL_TEXT).startswith("某專案的表")
    # 事實描述不走樣：非專案的字一字不動
    assert rg.scrub_project_details(GENERIC_TEXT) == GENERIC_TEXT


# ─── atom_io_cli 分派 ─────────────────────────────────────────────────────


def test_cli_realm_check_dispatch_by_scope():
    fields = {"title": "x", "triggers": ["登入"], "knowledge": [PROJECT_TEXT], "actions": []}
    org = cli._realm_check({"scope": "org", **fields})
    assert org and "scope=org rejected" in org
    # shared 不受影響：專案層本來就能寫專名
    assert cli._realm_check({"scope": "shared", **fields}) is None
    # global（根層 cwd）：已登記專案名照舊擋（既有 check_global_write 路徑）
    glob = cli._realm_check({"scope": "global", "project_cwd": None, **fields})
    assert glob and "scope=global rejected" in glob
    # scope 缺省＝global（舊呼叫端）
    assert cli._realm_check({**fields}) and "scope=global" in cli._realm_check({**fields})


def test_cli_scrub_action(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"action": "scrub", "text": PROJECT_TEXT})))
    rc = cli.main()
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0 and out["ok"] is True
    assert "FooProj" not in out["extra"]["text"] and "某專案" in out["extra"]["text"]


def test_cli_realm_check_action_org_via_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "action": "realm_check", "scope": "org", "title": "x", "triggers": ["登入"],
        "knowledge": [PROJECT_TEXT], "actions": [],
    })))
    rc = cli.main()
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 1 and out["ok"] is False and "scope=org rejected" in out["error"]


# ─── BLOCK 6：手列名單不分大小寫；短名／泛詞只整詞原樣比對、不進 scrub ───────────


def test_manual_project_name_case_insensitive(monkeypatch):
    monkeypatch.setattr(rg, "_load_registry", lambda: {"projects": {}, "project_names": ["BarGame"]})
    assert rg.check_org_write("bargame 的合服八步驟"), "手列名單要不分大小寫"
    assert rg.check_org_write("BARGAME 合服"), "全大寫也擋"
    assert rg.scrub_project_details("bargame 的合服") == "某專案 的合服"


def test_generic_manual_name_whole_word_only_and_not_scrubbed(monkeypatch):
    monkeypatch.setattr(rg, "_load_registry", lambda: {"projects": {}, "project_names": ["Game", "Qux"]})
    # 泛詞 Game：普通句（小寫／子字串）不擋、不 scrub
    sentence = "遊戲 game design 要先定 schema；GameZone 無關"
    assert rg.check_org_write(sentence) == []
    assert rg.scrub_project_details(sentence) == sentence
    # 原樣整詞命中才擋，但泛詞不進 scrub（換掉會把普通句改壞）
    assert rg.check_org_write("Game 的 schema 規則")
    assert rg.scrub_project_details("Game 的 schema 規則") == "Game 的 schema 規則"
    # 短名（≤4）非泛詞：原樣整詞比對（QUX 不擋），命中時照舊 scrub（沿用 verify_realm_project_term_gate 既有案）
    assert rg.check_org_write("QUX 協定解析") == [] and rg.check_org_write("Qux 戰役")
    assert rg.scrub_project_details("Qux 戰役") == "某專案 戰役"
