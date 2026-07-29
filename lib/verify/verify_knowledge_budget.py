"""verify_knowledge_budget.py — atom 瘦身規範（大小預算硬拒 + 樣式軟警 + Status build）守衛

覆蓋驗收：
  B1: 超額 atom 被拒且提示明確；合格 atom 通過；既有 atom 讀取（validate）不受影響
  B2(寫入半邊): build_atom_content 選填 status → `- Status:` 行
  write-gate: 大小硬拒排最前（explicit_user 不豁免）+ 樣式 warnings 附掛
  append: 拼接後超額被拒（肥大化實際路徑）
"""

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.atom_spec import (  # noqa: E402
    KNOWLEDGE_BUDGET_BYTES,
    build_atom_content,
    knowledge_budget_error,
    knowledge_sections_bytes,
    knowledge_style_warnings,
    validate_atom_content,
)
from lib.atom_io import append_atom_file  # noqa: E402
from lib.atom_io_cli import _budget_check  # noqa: E402


def _atom(knowledge_body: str) -> str:
    return (
        "# t\n\n- Scope: global\n- Confidence: [臨]\n- Trigger: a, b\n\n"
        f"## 知識\n\n{knowledge_body}\n\n## 行動\n\n- x\n"
    )


# ── 純函式 ──────────────────────────────────────────────────────


def test_sections_bytes_counts_knowledge_and_impression():
    body = "- 一二三"
    content = _atom(body)
    n = knowledge_sections_bytes(content)
    assert n == len(f"\n{body}\n\n".encode("utf-8"))
    with_impr = content.replace("## 知識", "## 印象\n\n- 印\n\n## 知識")
    assert knowledge_sections_bytes(with_impr) > n


def test_budget_error_boundary():
    assert knowledge_budget_error(KNOWLEDGE_BUDGET_BYTES) is None
    err = knowledge_budget_error(KNOWLEDGE_BUDGET_BYTES + 1)
    assert err and "個案事實移文件" in err
    assert knowledge_budget_error(10**6, budget=0) is None  # <=0 停用


def test_style_warnings():
    table = "\n".join("| a | b |" for _ in range(7))
    assert any("表格" in w for w in knowledge_style_warnings(table))
    paths = "\n".join(f"- hooks/handlers/f{i}.py 改了" for i in range(9))
    assert any("路徑" in w for w in knowledge_style_warnings(paths))
    assert knowledge_style_warnings("- 結論一句\n- 教訓一句") == []


def test_existing_fat_atom_read_unaffected():
    # B1 後半：大小預算只在寫入端；validate（讀取/heal 路徑）對肥 atom 照常通過
    fat = _atom("- " + "肥" * 4000)
    assert validate_atom_content(fat) is None


# ── build（create/replace 共用 floor）────────────────────────────


def test_cli_budget_check_rejects_fat_build():
    fat = _atom("- " + "肥" * 4000)
    err = _budget_check(fat)
    assert err and "超過預算" in err
    assert _budget_check(_atom("- 正常結論")) is None


def test_build_atom_content_status_line():
    kw = dict(title="t", scope="global", confidence="[臨]",
              triggers=["a"], knowledge=["k"])
    assert "- Status: 案結 2026-07-29" in build_atom_content(
        **kw, status="案結 2026-07-29")
    assert "- Status:" not in build_atom_content(**kw)  # 未給時 byte-identical


# ── append 路徑 ─────────────────────────────────────────────────


def test_append_over_budget_rejected(tmp_path):
    p = tmp_path / "a.md"
    p.write_text(_atom("- 起始"), encoding="utf-8")
    ok = append_atom_file(p, ["- 小追加"], source="mcp")
    assert ok.ok
    over = append_atom_file(p, ["- " + "肥" * 4000], source="mcp")
    assert not over.ok
    assert "Budget" in (over.error or "") and "個案事實移文件" in over.error
    # 被拒後檔案不變（write_raw 未被呼叫）
    assert "肥肥" not in p.read_text(encoding="utf-8")


# ── write-gate ──────────────────────────────────────────────────


def _load_write_gate():
    wg_path = Path(__file__).resolve().parent.parent.parent / "tools" / "memory-write-gate.py"
    spec = importlib.util.spec_from_file_location("memory_write_gate", wg_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_write_gate_size_reject_beats_explicit_user():
    wg = _load_write_gate()
    cfg = {"knowledge_budget_bytes": 3072}
    r = wg.evaluate("肥" * 4000, explicit_user=True, config=cfg)
    assert r["action"] == "skip"
    assert "個案事實移文件" in r["reason"]


def test_write_gate_small_explicit_user_passes_with_style_warning():
    wg = _load_write_gate()
    cfg = {"knowledge_budget_bytes": 3072}
    table = "\n".join("| a | b |" for _ in range(7))
    r = wg.evaluate(table, explicit_user=True, config=cfg)
    assert r["action"] == "add"
    assert r.get("warnings") and any("表格" in w for w in r["warnings"])
    r2 = wg.evaluate("記住這個結論", explicit_user=True, config=cfg)
    assert r2["action"] == "add" and "warnings" not in r2
