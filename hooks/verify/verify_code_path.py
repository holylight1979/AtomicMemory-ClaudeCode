"""verify_code_path.py — 寫碼類判準（hooks/wg_code_path.py）：副檔名清單聯集、沒副檔名看 shebang。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_code_path.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_code_path as cp  # noqa: E402
import wg_verify_ledger as vl  # noqa: E402


def test_is_code_path_union_and_shebang(tmp_path, monkeypatch):
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    proj = tmp_path / "proj"
    proj.mkdir()
    script = proj / "deploy"
    script.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    plain = proj / "LICENSE"
    plain.write_text("MIT", encoding="utf-8")
    assert cp.is_code_path(str(script), {}) and not cp.is_code_path(str(plain), {})
    assert cp.is_code_path(str(proj / "a.py"), {"reconcile_gate": {"code_exts": []}})      # 設定清空也拿不掉
    cfg = {"reconcile_gate": {"code_exts": [".tbl"]}}
    assert cp.is_code_path(str(proj / "x.tbl"), cfg) and cp.is_code_path(str(proj / "a.py"), cfg)
    assert ".py" in vl.reconcile_cfg({"reconcile_gate": {"code_exts": [".tbl"]}})["code_exts"]
