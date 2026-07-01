"""verify_episodic_purge.py — SessionEnd 輕量 episodic purge + 注入曝光遙測。

守 P5-episodic 兩個新契約（atom-audit-2026-07-01-plan.md P5）：

purge（wg_episodic._purge_expired_episodic）：
- Expires-at < today → md + .access.json sidecar 搬 _distant/{year}_{month}/（走
  move_atom_pair funnel，可逆；計數不變孤兒）
- Expires-at >= today / 無 Expires-at 欄位 → 保留（保守不動）
- 目標同名已存在 → 跳過不覆蓋
- fail-open：回被搬走 stem list

exposure（ups_context._record_episodic_exposure）：
- 實際注入的 episodic → read_hits++（file_path 定位、is_file 驗證後才計數）
- 不存在/已搬走路徑 → 跳過，不憑空建 sidecar（防污染）

受控 tmp，不動磁碟既有 atom。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_episodic  # noqa: E402
from wg_episodic import _purge_expired_episodic  # noqa: E402
from lib.atom_access import read_access  # noqa: E402


def _write_episodic(ep_dir: Path, name: str, expires: str | None) -> Path:
    """建一顆 episodic .md（可選 Expires-at）+ 帶初始 read_hits 的 sidecar。"""
    ep_dir.mkdir(parents=True, exist_ok=True)
    md = ep_dir / f"{name}.md"
    head = (
        f"# Session: {name}\n\n"
        f"- Confidence: [臨]\n"
        f"- Type: episodic\n"
        f"- TTL: 24d\n"
    )
    if expires:
        head += f"- Expires-at: {expires}\n"
    head += "\n## 摘要\n\ntest\n"
    md.write_text(head, encoding="utf-8")
    # sidecar：帶可辨識計數，驗證搬移時 sidecar 一起走（計數不變孤兒）
    acc = md.with_suffix(".access.json")
    acc.write_text(json.dumps({
        "schema": "atom-access-v3", "read_hits": 7, "first_seen": "2026-05-01",
    }), encoding="utf-8")
    return md


TODAY = "2026-07-01"


def test_expired_moved_with_sidecar(tmp_path):
    ep = tmp_path / "episodic"
    _write_episodic(ep, "episodic-20260504-old", expires="2026-05-28")  # 過期
    moved = _purge_expired_episodic(episodic_dir=ep, today=TODAY)
    assert moved == ["episodic-20260504-old"]
    # 原位消失
    assert not (ep / "episodic-20260504-old.md").exists()
    assert not (ep / "episodic-20260504-old.access.json").exists()
    # 落 _distant/{year}_{month}/（memory/ 根 = episodic 上一層），md + sidecar 皆在
    dst = tmp_path / "_distant" / "2026_07" / "episodic-20260504-old.md"
    assert dst.exists()
    dst_acc = dst.with_suffix(".access.json")
    assert dst_acc.exists()
    # 計數不變孤兒：sidecar read_hits 保留
    assert read_access(dst)["read_hits"] == 7


def test_not_expired_kept(tmp_path):
    ep = tmp_path / "episodic"
    _write_episodic(ep, "episodic-20260630-fresh", expires="2026-07-24")  # 未過期
    moved = _purge_expired_episodic(episodic_dir=ep, today=TODAY)
    assert moved == []
    assert (ep / "episodic-20260630-fresh.md").exists()


def test_expires_equals_today_kept(tmp_path):
    ep = tmp_path / "episodic"
    _write_episodic(ep, "episodic-today", expires=TODAY)  # == today → 保留當天
    moved = _purge_expired_episodic(episodic_dir=ep, today=TODAY)
    assert moved == []
    assert (ep / "episodic-today.md").exists()


def test_missing_expires_field_kept(tmp_path):
    ep = tmp_path / "episodic"
    _write_episodic(ep, "episodic-noexp", expires=None)  # 無 Expires-at → 保守不動
    moved = _purge_expired_episodic(episodic_dir=ep, today=TODAY)
    assert moved == []
    assert (ep / "episodic-noexp.md").exists()


def test_distant_collision_skipped(tmp_path):
    ep = tmp_path / "episodic"
    _write_episodic(ep, "episodic-dup", expires="2026-05-01")
    # 預先在 _distant 佔位同名
    dst_dir = tmp_path / "_distant" / "2026_07"
    dst_dir.mkdir(parents=True, exist_ok=True)
    (dst_dir / "episodic-dup.md").write_text("preexisting", encoding="utf-8")
    moved = _purge_expired_episodic(episodic_dir=ep, today=TODAY)
    assert moved == []  # 同名已存在 → 跳過
    assert (ep / "episodic-dup.md").exists()  # 原檔仍在（未被吞）
    assert (dst_dir / "episodic-dup.md").read_text(encoding="utf-8") == "preexisting"


def test_missing_dir_returns_empty(tmp_path):
    moved = _purge_expired_episodic(episodic_dir=tmp_path / "nope", today=TODAY)
    assert moved == []


def test_exposure_increments_read_hits(tmp_path):
    """_record_episodic_exposure：實際注入 → read_hits++（file_path 定位）。"""
    import importlib
    ups = importlib.import_module("handlers.ups_context")
    ep = tmp_path / "episodic"
    md = _write_episodic(ep, "episodic-inj", expires="2026-07-24")
    before = read_access(md)["read_hits"]  # 7
    ups._record_episodic_exposure([{"atom_name": "episodic-inj", "file_path": str(md)}])
    assert read_access(md)["read_hits"] == before + 1


def test_exposure_skips_nonexistent_no_sidecar(tmp_path):
    """不存在/已搬走路徑 → 跳過，不憑空建 sidecar（防污染）。"""
    import importlib
    ups = importlib.import_module("handlers.ups_context")
    ghost_md = tmp_path / "episodic" / "episodic-ghost.md"  # 不存在
    ups._record_episodic_exposure([
        {"atom_name": "episodic-ghost", "file_path": str(ghost_md)}
    ])
    assert not ghost_md.with_suffix(".access.json").exists()
