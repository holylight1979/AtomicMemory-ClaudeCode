"""verify_knowledge_shape.py — 清單型內容不進 atom（形狀硬拒）＋接近預算預警 守衛

覆蓋驗收：
  S1: knowledge 區出現 >=3 個待辦標記 → 硬拒，訊息指向 memory/_staging + 指標 atom
  S2: 一般條列型 atom（通篇 `- `）不得誤判；未達門檻的 1~2 個標記放行
  S3: create/replace（CLI）與 append（atom_io）兩個寫入端都擋
  S4: 形狀硬拒排在大小預算之前（清單不必長到超額才被擋）
  S5: 達預算 80% 未超額 → append 成功但回 budget_warning
  S6: 預算錯誤訊息點出注入端上限（避免往「放寬預算」的錯方向解）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.atom_spec import (  # noqa: E402
    KNOWLEDGE_BUDGET_BYTES,
    knowledge_budget_error,
    knowledge_budget_warning,
    knowledge_task_list_error,
)
from lib.atom_io import append_atom_file  # noqa: E402
from lib.atom_io_cli import _shape_check  # noqa: E402


def _atom(knowledge_body: str) -> str:
    return (
        "# t\n\n- Scope: global\n- Confidence: [臨]\n- Trigger: a, b\n\n"
        f"## 知識\n\n{knowledge_body}\n\n## 行動\n\n- x\n"
    )


# ── 形狀判定（純函式）──────────────────────────────────────────


def test_task_list_rejected_and_points_to_staging():
    body = "\n".join(f"- [ ] 待辦 {i}" for i in range(3))
    err = knowledge_task_list_error(_atom(body))
    assert err and "_staging" in err and "指標" in err


def test_done_marks_count_too():
    body = "- [x] 已完成一\n- [X] 已完成二\n- [ ] 未完成三"
    assert knowledge_task_list_error(_atom(body)) is not None


def test_plain_bullet_atom_not_flagged():
    # atom 本來就通篇條列——不能用「條列多」當判準
    body = "\n".join(f"- [臨] 結論 {i}" for i in range(20))
    assert knowledge_task_list_error(_atom(body)) is None


def test_below_threshold_passes():
    body = "- [臨] 結論\n- [ ] 只有一條待辦，算個案不算清單"
    assert knowledge_task_list_error(_atom(body)) is None
    assert knowledge_task_list_error(_atom(body), min_items=0) is None  # <=0 停用


def test_marks_outside_knowledge_section_ignored():
    content = _atom("- [臨] 結論").replace(
        "## 行動\n\n- x\n",
        "## 行動\n\n- [ ] a\n- [ ] b\n- [ ] c\n",
    )
    assert knowledge_task_list_error(content) is None


# ── 兩個寫入端 ─────────────────────────────────────────────────


def test_cli_shape_check_rejects():
    body = "\n".join(f"- [ ] 待辦 {i}" for i in range(3))
    assert _shape_check(_atom(body)) is not None
    assert _shape_check(_atom("- [臨] 結論")) is None


def test_append_task_list_rejected(tmp_path):
    p = tmp_path / "a.md"
    p.write_text(_atom("- [臨] 起始結論"), encoding="utf-8")
    res = append_atom_file(p, ["- [ ] 一", "- [ ] 二", "- [ ] 三"], source="mcp")
    assert not res.ok
    assert "Shape" in (res.error or "") and "_staging" in res.error
    assert "- [ ] 一" not in p.read_text(encoding="utf-8")   # 被拒後檔案不變


def test_shape_beats_budget(tmp_path):
    # 短清單遠低於預算，仍要被擋（不必長到超額）
    body = "\n".join(f"- [ ] {i}" for i in range(3))
    content = _atom(body)
    assert knowledge_task_list_error(content) is not None
    from lib.atom_spec import knowledge_sections_bytes
    assert knowledge_budget_error(knowledge_sections_bytes(content)) is None


# ── 預警與訊息 ─────────────────────────────────────────────────


def test_budget_warning_band():
    assert knowledge_budget_warning(int(KNOWLEDGE_BUDGET_BYTES * 0.5)) is None
    warn = knowledge_budget_warning(int(KNOWLEDGE_BUDGET_BYTES * 0.9))
    assert warn and "_staging" in warn
    # 超額時交給 budget error 講，不重複預警
    assert knowledge_budget_warning(KNOWLEDGE_BUDGET_BYTES + 1) is None
    assert knowledge_budget_warning(10**6, budget=0) is None  # <=0 停用


def test_append_near_budget_warns(tmp_path):
    # 拼接後落在 [80% 預算, 預算] 這一段才會預警
    p = tmp_path / "a.md"
    p.write_text(_atom("- " + "肥" * 800), encoding="utf-8")   # 約 2.4KB
    res = append_atom_file(p, ["- " + "肥" * 100], source="mcp")
    assert res.ok
    from lib.atom_spec import knowledge_sections_bytes
    n = knowledge_sections_bytes(p.read_text(encoding="utf-8"))
    assert int(KNOWLEDGE_BUDGET_BYTES * 0.8) <= n <= KNOWLEDGE_BUDGET_BYTES
    assert "budget_warning" in (res.extra or {})


def test_budget_error_mentions_injection_cap():
    err = knowledge_budget_error(KNOWLEDGE_BUDGET_BYTES + 1)
    assert err and "200 tok" in err
