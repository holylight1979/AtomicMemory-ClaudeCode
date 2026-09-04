"""verify_always_load_contracts.py — 必載檔硬契約守門。

memory/_meta/always-load-contracts.json 登記的契約句：
  - 版控中的 template／rules 檔必須含每一句 → 修剪必載檔刪掉契約句時本測試直接紅
  - handlers/session_start.check_always_load_contracts：live 檔缺句 → 告警行；齊全 → 空；登記表壞 → 一行告警
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))

from handlers.session_start import check_always_load_contracts  # noqa: E402

REG = CLAUDE_DIR / "memory" / "_meta" / "always-load-contracts.json"


def _contracts():
    return json.loads(REG.read_text(encoding="utf-8"))["contracts"]


def test_registry_shape():
    cs = _contracts()
    assert cs, "登記表不得為空"
    for c in cs:
        assert c["id"] and c["live"] and c["template"] and c["must_contain"] and c["fix"]


@pytest.mark.parametrize("contract", _contracts(), ids=lambda c: c["id"])
def test_template_keeps_contract_sentences(contract):
    text = (CLAUDE_DIR / contract["template"]).read_text(encoding="utf-8")
    missing = [m for m in contract["must_contain"] if m not in text]
    assert not missing, (
        f"{contract['template']} 缺硬契約句 {missing}——必載檔修剪不得只把契約搬去 atom；"
        f"why: {contract.get('why')}"
    )


def _fake_root(tmp_path, live_text: str):
    (tmp_path / "memory" / "_meta").mkdir(parents=True)
    (tmp_path / "memory" / "_meta" / "always-load-contracts.json").write_text(json.dumps({
        "contracts": [{
            "id": "t", "live": "USER.md", "template": "USER.md",
            "must_contain": ["上GIT", "一氣做完"], "fix": "回填",
        }]
    }, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "USER.md").write_text(live_text, encoding="utf-8")
    return tmp_path


def test_live_missing_sentence_warns(tmp_path):
    out = check_always_load_contracts(_fake_root(tmp_path, "「上GIT」定義見 preferences"))
    assert len(out) == 1
    assert "[Guardian:Contract⚠]" in out[0] and "一氣做完" in out[0] and "回填" in out[0]


def test_live_complete_is_silent(tmp_path):
    out = check_always_load_contracts(_fake_root(tmp_path, "上GIT＝commit→push 一氣做完"))
    assert out == []


def test_broken_registry_surfaces_not_silent(tmp_path):
    (tmp_path / "memory" / "_meta").mkdir(parents=True)
    (tmp_path / "memory" / "_meta" / "always-load-contracts.json").write_text("{bad", encoding="utf-8")
    out = check_always_load_contracts(tmp_path)
    assert len(out) == 1 and "登記表讀取失敗" in out[0]


def test_real_root_live_files_complete():
    """本機 live 檔（USER.md／IDENTITY.md／rules/core.md）目前齊全；缺句代表本機要回填。"""
    assert check_always_load_contracts(CLAUDE_DIR) == []
