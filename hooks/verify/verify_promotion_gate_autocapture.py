"""verify_promotion_gate_autocapture.py — 晉升閘漏洞修補守門（INV-PROMOTION-GATE-ON-SCAN-FACE）.

守住曾驗證的漏洞：`_self_iterate_atoms` 晉升掃描面對「未確認 auto-capture 碎片」**無**過濾
（該過濾原僅在 realm sweep 路徑 `_sweep_realm_auto_migrate`），故佔位符碎片 confirmations 達標
即被自動晉升 [臨]→[觀]。修：晉升條件串 `_autocapture_unconfirmed_from_text`，與 sweep 同源規則。

1. `_autocapture_unconfirmed_from_text` 規則正確（trigger 含 auto-capture / author=auto-captured+[臨]）。
2. 與 `_is_unconfirmed_autocapture`（index adapter）對同一 atom 等價（body↔index trigger byte-mirror）。
3. 晉升條件 source-level 已串 filter（wiring 不得靜默回退）——同 verify_promotion_gate_phase0 手法。
4. relocate freeze 不變式：`set_realm` 走 `move_atom_pair`（純 rename）→ body byte 不動 → Confidence
   凍結（搬實體檔 + 改 index path，不重寫 body）。formal `relocate_atom`（L3, Phase B）另立。

純邏輯 + source 讀取，無重依賴。
"""

from __future__ import annotations

import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[2]  # hooks/verify/ → ~/.claude
if str(CLAUDE) not in sys.path:
    sys.path.insert(0, str(CLAUDE))
HOOKS = CLAUDE / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from wg_atoms import (  # noqa: E402
    _autocapture_unconfirmed_from_text, _is_unconfirmed_autocapture,
)


def _atom(trigger: str, author: str = "holylight", conf: str = "[臨]") -> str:
    return (f"# x\n\n- Scope: global\n- Author: {author}\n- Confidence: {conf}\n"
            f"- Trigger: {trigger}\n- Created-at: 2026-06-30\n\n## 知識\n\n- [臨] x\n")


# ─── 1. text 規則正確 ─────────────────────────────────────────────────────────


def test_text_predicate_trigger_autocapture():
    assert _autocapture_unconfirmed_from_text(_atom("auto-capture, foo")) is True
    assert _autocapture_unconfirmed_from_text(_atom("foo, bar")) is False


def test_text_predicate_author_confidence():
    # author=auto-captured + [臨] → 未確認碎片（trigger 非預設但 frontmatter 揭露）
    assert _autocapture_unconfirmed_from_text(
        _atom("foo", author="auto-captured", conf="[臨]")) is True
    # 已晉升（[觀]）→ 不再 defer（晉升後 Confidence 變即脫離未確認態）
    assert _autocapture_unconfirmed_from_text(
        _atom("foo", author="auto-captured", conf="[觀]")) is False
    # 正常 curated atom（holylight + [臨]、trigger 無 auto-capture）→ 不 defer
    assert _autocapture_unconfirmed_from_text(
        _atom("foo", author="holylight", conf="[臨]")) is False


# ─── 2. text adapter ↔ index adapter 等價（規則單源、僅輸入不同）──────────────


def test_text_vs_index_adapter_equivalence():
    body = _atom("auto-capture, realm sweep", author="holylight", conf="[臨]")
    entry = {"triggers": ["auto-capture", "realm sweep"], "path": "<nonexistent>"}
    assert _autocapture_unconfirmed_from_text(body) is True
    assert _is_unconfirmed_autocapture(entry) is True

    body2 = _atom("foo, bar", author="holylight", conf="[臨]")
    entry2 = {"triggers": ["foo", "bar"], "path": "<nonexistent>"}
    assert _autocapture_unconfirmed_from_text(body2) is False
    assert _is_unconfirmed_autocapture(entry2) is False


# ─── 3. 晉升掃描面 wiring source-guard（不得靜默回退到無過濾）────────────────


def test_promotion_face_wires_autocapture_filter():
    src = (CLAUDE / "hooks" / "wg_atoms.py").read_text(encoding="utf-8")
    needle = "and not _autocapture_unconfirmed_from_text(text)"
    assert needle in src, "晉升掃描面未串 _autocapture_unconfirmed_from_text 過濾"
    # 且過濾與晉升條件（confirmations/util_eligible）同段——非孤立死碼
    idx = src.index(needle)
    window = src[max(0, idx - 220):idx]
    assert "confirmations >= promote_conf_threshold or util_eligible" in window, \
        "過濾未掛在晉升條件上"


# ─── 4. relocate freeze 不變式：搬移不動 body（→ Confidence 凍結）──────────────


def test_move_atom_pair_preserves_body_byte_identical(tmp_path):
    """set_realm 用 move_atom_pair（純 rename）搬 atom → body byte 不變 → Confidence 凍結。"""
    from lib.atom_access import move_atom_pair

    src = tmp_path / "frag.md"
    body = ("# frag\n\n- Scope: global\n- Author: auto-captured\n- Confidence: [臨]\n"
            "- Trigger: auto-capture\n\n## 知識\n\n- [臨] 半截\n")
    src.write_text(body, encoding="utf-8")
    dst = tmp_path / "MemDev" / "deep" / "frag.md"  # 深層 dst（mirror 真實 local 路由）

    move_atom_pair(src, dst)

    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == body  # body 全等 → Confidence 行原樣（凍結）


def test_set_realm_uses_physical_move_not_body_rewrite():
    """source-guard：set_realm 走實體搬移、不觸 body Confidence（freeze）。"""
    src = (CLAUDE / "tools" / "atom-set-realm.py").read_text(encoding="utf-8")
    assert "move_atom_pair" in src, "set_realm 應走實體搬移（move_atom_pair）"
    # set_realm 全檔不觸碰 Confidence（只搬檔 + 改 index path + 保留 Scope）——觸碰即破壞 freeze
    assert "Confidence" not in src, "set_realm 不應觸碰 body Confidence（freeze 不變式 tripwire）"
