"""verify_atom_io_replace_old_format.py：atom_write replace 對舊格式卡只換呼叫者給的部分，檔頭其餘照舊卡。

舊格式卡＝標題與檔名不同、沒有 Created-at、沒有 Quote、檔頭有 build 不認得的鍵（Last-used／Confirmations／Type）。
replace 以前用參數重建整張檔：標題被換成檔名、Created-at 補當天、Related／Status 沒給就消失、舊鍵全掉。
兩條路都驗：py write_atom（程式寫手）與 atom_io_cli build＋existing_path（MCP js 的 replace 走這條）。
新格式卡 replace 的輸出與修前逐 byte 相同。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_atom_io_replace_old_format.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

LIB_PARENT = Path(__file__).resolve().parents[2]
if str(LIB_PARENT) not in sys.path:
    sys.path.insert(0, str(LIB_PARENT))

from lib import atom_io  # noqa: E402
from lib.atom_io import write_atom  # noqa: E402
from lib.atom_spec import build_atom_content  # noqa: E402

TODAY = "2026-10-14"
OLD_CARD = """# 全域決策

- Scope: global
- Confidence: [固]
- Trigger: 決策, 記憶系統, 原子記憶
- Status: 現行
- Last-used: 2026-04-23
- Confirmations: 10
- Type: procedural
- Related: decisions-architecture, toolchain, toolchain-ollama
- Depends: path:tools/x.py
- Source: commit:7deb043 2026-03-02（原對話已逾保留期）

## 知識

- [固] 舊知識

## 行動

- 舊行動
"""
NEW_KNOWLEDGE = ["[固] 新知識"]
NEW_ACTIONS = ["新行動"]


@pytest.fixture
def isolated_claude(tmp_path, monkeypatch):
    """atom_io 與落點函式的全域根改指 tmp，不碰現役 ~/.claude。"""
    fake_claude = tmp_path / ".claude"
    mem = fake_claude / "memory"
    mem.mkdir(parents=True)
    monkeypatch.setattr(atom_io, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(atom_io, "GLOBAL_MEMORY_DIR", mem)
    monkeypatch.setattr(atom_io, "AUDIT_LOG", mem / "_meta" / "atom_io_audit.jsonl")
    from lib import atom_locations as aloc
    monkeypatch.setattr(aloc, "CLAUDE_DIR", fake_claude)
    monkeypatch.setattr(aloc, "GLOBAL_MEMORY_DIR", mem)
    monkeypatch.setattr(aloc, "FAILURES_DIR", mem / "Failures")
    monkeypatch.setattr(aloc, "LOCAL_ATOMS_DIR", fake_claude / "_AIDocs" / "_atoms")
    monkeypatch.setattr(aloc, "TAXONOMY_LEARNED_PATH", mem / "_meta" / "taxonomy-lexicon-learned.json")
    return mem


def _old_format_card(mem: Path) -> Path:
    """先 create 一張 decisions（建索引），再把檔換成舊格式內容；sidecar 有 Confirmations／Last-used。"""
    r = write_atom(title="decisions", scope="global", confidence="[臨]", triggers=["決策", "記憶系統", "原子記憶"],
                   knowledge=["x"], domain="CC與原子記憶契約", mode="create", source="test", skip_gate=True, today=TODAY)
    assert r.ok, r.error
    r.path.write_text(OLD_CARD, encoding="utf-8", newline="\n")
    from lib.atom_access import write_access_field
    write_access_field(r.path, field="confirmations", value=10, source="test")
    write_access_field(r.path, field="last_used", value="2026-04-23", source="test")
    return r.path


def _assert_old_header_kept(text: str) -> None:
    lines = text.splitlines()
    assert lines[0] == "# 全域決策", f"標題被改：{lines[0]!r}"
    assert "- Created-at:" not in text, "舊卡沒有 Created-at，replace 不得補當天"
    assert "- Quote:" not in text, "舊卡沒有 Quote，replace 不得自己生一行"
    assert "- Related: decisions-architecture, toolchain, toolchain-ollama" in lines, "Related 沒給就要帶回"
    assert "- Status: 現行" in lines, "Status 沒給就要帶回"
    assert "- Last-used: 2026-04-23" in lines and "- Confirmations: 10" in lines, "舊檔頭的計數行要帶回"
    assert "- Type: procedural" in lines, "build 不認得的舊鍵要帶回"
    assert "- Depends: path:tools/x.py" in lines and "- Source: commit:7deb043 2026-03-02（原對話已逾保留期）" in lines
    assert "- [固] 新知識" in lines and "- 新行動" in lines, "知識與行動要換成新的"
    assert "舊知識" not in text and "舊行動" not in text
    # 帶回的行放在舊卡裡它前面那個鍵之後：Status → Last-used → Confirmations → Type 的相對順序不變
    order = [next(i for i, l in enumerate(lines) if l.startswith(f"- {k}:"))
             for k in ("Trigger", "Status", "Last-used", "Confirmations", "Type")]
    assert order == sorted(order), order


def test_003_replace_old_format_card_via_write_atom(isolated_claude):
    fp = _old_format_card(isolated_claude)
    r = write_atom(title="decisions", scope="global", confidence="[固]", triggers=["決策", "記憶系統", "原子記憶"],
                   knowledge=NEW_KNOWLEDGE, actions=NEW_ACTIONS, mode="replace", source="test", skip_gate=True,
                   today=TODAY)
    assert r.ok, r.error
    _assert_old_header_kept(fp.read_text(encoding="utf-8"))
    acc = json.loads(fp.with_suffix(".access.json").read_text(encoding="utf-8"))
    assert acc["confirmations"] == 10, "sidecar 的 Confirmations 不得被 replace 動到"


def test_003_replace_old_format_card_via_cli_build_used_by_mcp(isolated_claude):
    """MCP js 的 replace：spawn `atom_io_cli build`（帶 existing_path、created_at＝今天、related 沒給）。"""
    fp = _old_format_card(isolated_claude)
    payload = {"action": "build", "existing_path": str(fp), "title": "decisions", "scope": "global",
               "confidence": "[固]", "triggers": ["決策", "記憶系統", "原子記憶"], "knowledge": NEW_KNOWLEDGE,
               "actions": NEW_ACTIONS, "created_at": TODAY, "today": TODAY,
               "provenance": "commit:7deb043 2026-03-02（原對話已逾保留期）", "depends": ["path:tools/x.py"]}
    proc = subprocess.run([sys.executable, "-m", "lib.atom_io_cli"], input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True, encoding="utf-8", cwd=str(LIB_PARENT),
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=30)
    res = json.loads(proc.stdout)
    assert res["ok"], res.get("error")
    _assert_old_header_kept(res["extra"]["content"])


def test_003_mcp_replace_passes_existing_path_to_build():
    js = (LIB_PARENT / "tools" / "workflow-guardian-mcp" / "lib" / "atom-tools.js").read_text(encoding="utf-8")
    replace_part = js[js.index('if (mode === "replace")'):]
    build_call = replace_part[replace_part.index('spawnAtomCli("build"'):]
    assert "existing_path: filePath" in build_call[:400], "MCP replace 要把既有檔交給 py build，檔頭才會以舊卡為底"


def test_003_caller_given_fields_still_win(isolated_claude):
    """呼叫者明給的欄位照舊以呼叫者為準：related=[] 清掉、quote 給了就寫。"""
    fp = _old_format_card(isolated_claude)
    r = write_atom(title="decisions", scope="global", confidence="[固]", triggers=["決策"], knowledge=NEW_KNOWLEDGE,
                   related=[], quote="「使用者原句」", mode="replace", source="test", skip_gate=True, today=TODAY)
    assert r.ok, r.error
    text = fp.read_text(encoding="utf-8")
    assert "- Related:" not in text and "- Quote: 「使用者原句」" in text
    assert text.splitlines()[0] == "# 全域決策" and "- Last-used: 2026-04-23" in text


def test_003_fields_decided_before_build_are_not_carried_back(isolated_claude):
    """Source／Quote／Depends／Supersedes 在 build 前已有三態判定：空的 `- Depends:` 行算清空，帶回不得把它加回去；
    同一張卡的舊欄位（Type）照帶回。"""
    fp = _old_format_card(isolated_claude)
    fp.write_text(OLD_CARD.replace("- Depends: path:tools/x.py", "- Depends:"), encoding="utf-8", newline="\n")
    r = write_atom(title="decisions", scope="global", confidence="[固]", triggers=["決策"], knowledge=NEW_KNOWLEDGE,
                   mode="replace", source="test", skip_gate=True, today=TODAY)
    assert r.ok, r.error
    text = fp.read_text(encoding="utf-8")
    assert "- Depends:" not in text, "空的 Depends 行已判定清空，不得被帶回"
    assert "- Type: procedural" in text and text.splitlines()[0] == "# 全域決策"


def test_003_same_key_on_several_lines_is_all_carried(isolated_claude):
    """codex 審 cdac58d BLOCK 1：同一個鍵分兩行（中間夾空行）沒給時兩行都帶回、順序不變。"""
    fp = _old_format_card(isolated_claude)
    two = OLD_CARD.replace("- Related: decisions-architecture, toolchain, toolchain-ollama",
                           "- Related: first-card\n\n- Related: second-card")
    fp.write_text(two, encoding="utf-8", newline="\n")
    r = write_atom(title="decisions", scope="global", confidence="[固]", triggers=["決策"], knowledge=NEW_KNOWLEDGE,
                   mode="replace", source="test", skip_gate=True, today=TODAY)
    assert r.ok, r.error
    lines = fp.read_text(encoding="utf-8").splitlines()
    assert "- Related: first-card" in lines and "- Related: second-card" in lines
    assert lines.index("- Related: first-card") < lines.index("- Related: second-card")


def test_003_new_format_title_follows_caller_as_before(isolated_claude):
    """codex 審 cdac58d BLOCK 3：新格式卡（標題 slug＝檔名）replace 時標題照舊用 title 參數（大小寫變體也一樣），
    只有舊格式（標題 slug≠檔名）才沿用舊標題。"""
    r = write_atom(title="Fresh Card", scope="global", confidence="[臨]", triggers=["a", "b", "c"], knowledge=["v1"],
                   domain="設計通則", mode="create", source="test", skip_gate=True, today="2026-10-01")
    assert r.ok, r.error
    r2 = write_atom(title="fresh card", scope="global", confidence="[臨]", triggers=["a", "b", "c"], knowledge=["v2"],
                    mode="replace", source="test", skip_gate=True, today=TODAY)
    assert r2.ok, r2.error
    assert r2.path.read_text(encoding="utf-8").splitlines()[0] == "# fresh card"


def test_003_new_format_replace_is_byte_identical_to_before(isolated_claude):
    """新格式卡（標題＝建立時的 title、有 Created-at、沒有舊鍵）：replace 結果與修前（直接 build）逐 byte 相同。"""
    r = write_atom(title="Fresh Card", scope="global", confidence="[臨]", triggers=["a", "b", "c"], knowledge=["v1"],
                   author="orig", related=["x-card"], domain="設計通則", mode="create", source="test",
                   skip_gate=True, today="2026-10-01")
    assert r.ok, r.error
    r2 = write_atom(title="Fresh Card", scope="global", confidence="[臨]", triggers=["a", "b", "c"], knowledge=["v2"],
                    related=["x-card"], mode="replace", source="test", skip_gate=True, today=TODAY)
    assert r2.ok, r2.error
    expected = build_atom_content(title="Fresh Card", scope="global", confidence="[臨]", triggers=["a", "b", "c"],
                                  knowledge=["v2"], author="orig", related=["x-card"], created_at="2026-10-01",
                                  today=TODAY)
    assert r2.path.read_bytes() == expected.encode("utf-8")
