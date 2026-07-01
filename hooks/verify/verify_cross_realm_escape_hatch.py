"""verify_cross_realm_escape_hatch.py — 跨 realm 逃逸閘守門（INV-CROSS-REALM-ESCAPE-HATCH）.

專案分類層無保護（TaxonomyStrategy protection 永 null）→ 逃進專案的核心跨專案規則 atom
（feedback-/atom-/decisions/workflow-…）會被歸進業務夾固化（如 SGI _unclassified 躺 feedback-*）。
修：分類『前』置跨 realm 邊界守，命中核心 PROTECTED → 送人工 /refile 而非業務夾。本守門驗：

1. is_core_protected_name 單一來源正確（EXACT + PREFIXES 命中、業務 atom 不誤命中）。
2. classify_realm 保護硬擋已退用 is_core_protected_name（DRY、不漂移）——source guard。
3. classify_project_atom 逃逸閘：命中 → _refile、未命中 → 照 classify_taxonomy。
4. 策略隔離：未注入 escape_protected → 行為 == 純 classify_taxonomy（taxonomy 不被污染）。

純邏輯 + source 讀取，無重依賴。formal 專案端 /refile 路由 = Phase B thin shim 接線（本檔備核心地基）。
"""

from __future__ import annotations

import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[2]  # hooks/verify/ → ~/.claude
if str(CLAUDE) not in sys.path:
    sys.path.insert(0, str(CLAUDE))

from lib.atom_locations import (  # noqa: E402
    is_core_protected_name,
    LOCAL_REALM_CORE_PROTECTED_PREFIXES, LOCAL_REALM_CORE_PROTECTED_EXACT,
)
from lib.atom_classify import classify_project_atom, classify_taxonomy  # noqa: E402


_TAX = {
    "domains": {
        "Server": {"terms": ["server", "tcp"], "priority": 1},
        "Client": {"terms": ["unity", "client"], "priority": 1},
    },
    "default_domain": "_unclassified",
}


# ─── 1. 單一來源保護判定 ──────────────────────────────────────────────────────


def test_is_core_protected_name_prefixes_and_exact():
    for p in LOCAL_REALM_CORE_PROTECTED_PREFIXES:
        assert is_core_protected_name(f"{p}whatever-x") is True, p
    assert is_core_protected_name("feedback-workflow-discipline") is True
    assert is_core_protected_name("atom-usefulness-loop") is True
    assert is_core_protected_name("decisions-architecture") is True
    assert is_core_protected_name("workflow-rules") is True
    for name in LOCAL_REALM_CORE_PROTECTED_EXACT:
        assert is_core_protected_name(name) is True, name
    # 業務 atom 不誤命中
    assert is_core_protected_name("server-startup-topology") is False
    assert is_core_protected_name("mapserver-manager-directory") is False
    assert is_core_protected_name("") is False


# ─── 2. classify_realm 退用單源（DRY、不漂移）source-guard ─────────────────────


def test_classify_realm_reuses_predicate_source_guard():
    src = (CLAUDE / "lib" / "atom_locations.py").read_text(encoding="utf-8")
    assert "if is_core_protected_name(name):" in src, "classify_realm 未退用單源保護判定"


# ─── 3. 逃逸閘路由：命中 → _refile，未命中 → 業務夾 ──────────────────────────


def test_escape_hatch_routes_protected_to_refile():
    dom, matched = classify_project_atom(
        "feedback-workflow-discipline", ["server", "tcp"], _TAX,
        escape_protected=is_core_protected_name)
    assert dom == "_refile" and matched == ["<cross-realm-escapee>"]
    # 真業務 atom（命中 taxonomy）→ 照常歸業務夾
    dom2, _ = classify_project_atom(
        "tcp-server-handshake", ["server", "tcp"], _TAX,
        escape_protected=is_core_protected_name)
    assert dom2 == "Server"


# ─── 4. 策略隔離：未注入閘 → 純 taxonomy（taxonomy 不被污染）─────────────────


def test_escape_hatch_off_equals_pure_taxonomy():
    name, trig = "feedback-x", ["unity", "client"]
    assert classify_project_atom(name, trig, _TAX)[0] == classify_taxonomy(name, trig, _TAX)[0]
    # 即使 protected 名，未注入閘 → 照 taxonomy（命中 Client）；證閘為正交可選層、非 strategy 內部
    assert classify_project_atom(name, trig, _TAX)[0] == "Client"
