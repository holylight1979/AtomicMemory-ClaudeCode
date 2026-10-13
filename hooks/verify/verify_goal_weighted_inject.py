"""verify_goal_weighted_inject.py：Q0 題組回放（H0 目的加權注入＋H1 固定句＋H4 閘一律擋）。

固定輸入 `hooks/verify/fixtures/v6/q0/<case>/`：overview-map.md（表）、hub.json（專案覆蓋）、cards/*.md（導讀卡）、
prompt.txt（{root} 佔位）、steps.jsonl（read／reply／edit 逐步）、expected.json（意圖、注入片序、最終 rec、log）。
三個歷史案例用化名（debug 不掉血、feature 存檔加欄位、refactor 工具鏈數彎）；反例一：定位三行格式全對但層填錯 → deny；反例三：填錯層後補交正確一組 → 放行；
反例二：前例填「無」且卡沒有病灶段 → 放行且 located_quality=none。以目錄參數化驅動 on_prompt／on_read／on_edit，不讀 live。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_goal_weighted_inject.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_overview as wo  # noqa: E402
from wg_atoms import classify_intent  # noqa: E402

Q0 = Path(__file__).resolve().parent / "fixtures" / "v6" / "q0"
CASES = sorted(p for p in Q0.iterdir() if p.is_dir())


@pytest.fixture(autouse=True)
def _temp_rules_off(monkeypatch):
    """假專案建在 pytest tmp 下：關掉規則 TEMP_COPY_NOT_PROJECT（否則暫存目錄下的專案不注入導讀卡）。"""
    monkeypatch.setenv("WG_TEMP_RULES", "off")


def _append(tp: Path, text: str, channel: str) -> None:
    if channel == "tool_input":
        block = {"type": "tool_use", "name": "Bash", "input": {"command": "# " + text.replace("\n", "\n# ") + "\ntrue"}}
    elif channel == "thinking":
        block = {"type": "thinking", "thinking": text}
    else:
        block = {"type": "text", "text": text}
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [block]}}, ensure_ascii=False) + "\n")


def _build(case: Path, tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    shutil.copy(case / "overview-map.md", proj / ".claude" / "overview-map.md")
    shutil.copy(case / "hub.json", proj / ".claude" / "overview-hub.json")
    for card in (case / "cards").glob("*.md"):
        shutil.copy(card, proj / ".claude" / "memory" / "shared" / card.name)
    for raw in (case / "steps.jsonl").read_text(encoding="utf-8").splitlines():
        step = json.loads(raw)
        if "path" in step:
            f = proj / step["path"]
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("// fixture\n", encoding="utf-8")
    return proj


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_q0_replay(case, tmp_path, monkeypatch):
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    proj = _build(case, tmp_path)
    root = str(proj).replace("\\", "/")
    tp = tmp_path / "t.jsonl"
    _append(tp, "開始。", "text")
    expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    prompt = (case / "prompt.txt").read_text(encoding="utf-8").replace("{root}", root)

    state = {"turn_seq": 1}
    intent = classify_intent(prompt)
    assert intent == expected["intent"], prompt
    state["turn_intent"] = intent
    txt = wo.on_prompt(state, "q0", prompt, str(tp), {}, intent=intent)
    assert txt, "提示詞提到部位檔必須注入"
    order = expected.get("inject_order", [])
    positions = [txt.index(tag) for tag in order]
    assert positions == sorted(positions), (order, positions)
    for s in expected.get("inject_contains", []):
        assert s in txt, s
    if expected.get("inject_rest_contains"):
        rest = txt.split("其餘段落只列標題")[1]
        for s in expected["inject_rest_contains"]:
            assert s in rest, s

    for raw in (case / "steps.jsonl").read_text(encoding="utf-8").splitlines():
        step = json.loads(raw)
        if step["op"] == "read":
            wo.on_read(state, "q0", "Read", {"file_path": str(proj / step["path"])}, str(proj), str(tp), {})
        elif step["op"] == "reply":
            _append(tp, step["text"], step.get("channel", "text"))
        elif step["op"] == "edit":
            warn, deny, changed = wo.on_edit(state, "q0", str(proj / step["path"]), str(tp), {})
            exp = step["expect"]
            assert bool(deny) == exp["deny"], (step, deny, warn)
            for s in exp.get("contains", []):
                assert s in (deny or warn or ""), s
            if not exp["deny"]:
                assert changed
        else:
            raise AssertionError(f"未知 op：{step}")

    rec = next(iter(state["overview_hub"].values()))
    for k, v in expected.get("final", {}).items():
        assert rec.get(k) == v, (k, rec.get(k), v)
    if expected.get("log_last"):
        last = json.loads((tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()[-1])
        for k, v in expected["log_last"].items():
            assert last.get(k) == v, (k, last.get(k), v)


def test_q0_has_three_replays_and_three_counterexamples():
    names = {c.name for c in CASES}
    assert {n for n in names if n.startswith("counter-")} == {"counter-wrong-layer", "counter-no-precedent", "counter-wrong-layer-then-fixed"}
    assert len([n for n in names if not n.startswith("counter-")]) == 3
